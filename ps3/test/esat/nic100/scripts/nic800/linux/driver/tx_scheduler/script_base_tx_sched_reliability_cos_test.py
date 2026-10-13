#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      weiyuan1
date:        2026.09.07
description: tx_sched cos 测试基类，nic800 linux driver tx_scheduler 模块 cos 类用例脚本的二级基类
             基于公共库 CommandOperation 实现真实指令下发，全部指令使用 iproute2 的 dcb 命令，
             与测试用例中的指令逐字对齐，不依赖 DcbtoolOperation 公共库
"""

import add_syspath
import re
import time

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from scripts.script_libs import log
from scripts.script_libs.script_base import ScriptBase, SxeThread
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum
from scripts.script_libs.iperf_operation import IperfOperation


class EtsAlgorithm(Enum):
    """ETS 调度算法类型"""
    ETS = auto()                # 全 ETS 模式 (WRR 加权轮询)
    STRICT = auto()             # 全 Strict Priority 模式 (严格优先级)
    HYBRID_ETS_STRICT = auto()  # 混合模式 (部分 Strict, 部分 ETS)


@dataclass
class TcConfig:
    """单个 TC (Traffic Class) 的配置模型"""
    tc_id: int              # TC 编号 (0-7)
    weight: int             # ETS 带宽权重 (0-100)
    is_strict: bool = False  # 是否开启 Strict Priority
    max_rate_kbps: int = 0  # 速率限制 (Kbps, 0 表示无限制)


class DcbEtsTcManager(ABC):
    """
    DCB / ETS 修改 TC 的通用虚基类 (抽象基类)

    模板方法 dcb_ets_modify_tc 固化了完整流程：
        dcbx host ieee -> 检查网卡支持的最大 TC 数量 -> 配置 ETS/Strict 带宽 ->
        批量设置 TC 限速 -> 绑定 Priority 与 DSCP
    任一环节失败时自动触发 restore_state 恢复默认配置
    """

    def __init__(self, interface_name: str, cmd_execute_address: str, dcbx_mode: str = "ieee"):
        """
        :param interface_name:        网卡接口名称, 如 eth0
        :param cmd_execute_address:   指令执行环境, 从 CmdExecuteAdressEnum 中取值
        :param dcbx_mode:             dcbx 模式, 默认 ieee
        """
        self.__interface_name = interface_name
        self.__cmd_execute_address = cmd_execute_address
        self.__dcbx_mode = dcbx_mode

        self.init_tc_bw = "0:100 1:0 2:0 3:0 4:0 5:0 6:0 7:0"
        self.init_prio_tc = "0:0 1:0 2:0 3:0 4:0 5:0 6:0 7:0"

    # =========================================================================
    # 属性访问器 (Getters)
    # =========================================================================
    @property
    def interface_name(self) -> str:
        return self.__interface_name

    @property
    def cmd_execute_address(self) -> str:
        return self.__cmd_execute_address

    @property
    def dcbx_mode(self) -> str:
        return self.__dcbx_mode

    # =========================================================================
    # 模板方法 (Template Method Pattern): 核心执行与回滚流程
    # =========================================================================
    def dcb_ets_modify_tc(self, algo: EtsAlgorithm, tc_configs: list,
                          prio: int, dscp: int) -> bool:
        """
        步骤1/2/4/5/7/8 全流程：dcbx host ieee -> 校验TC数 -> 配置ETS带宽 -> 限速 -> prio/dscp绑定
        任一步骤失败时自动回滚恢复默认配置
        """
        try:
            if not self.set_dcbx_host_ieee():
                raise RuntimeError("设置 dcbx host ieee 失败")

            max_supported = self.get_max_supported_tcs()
            if max_supported and len(tc_configs) > max_supported:
                raise ValueError(f"配置的 TC 数量 ({len(tc_configs)}) 超过网卡支持上限 ({max_supported})")

            if not self.configure_ets_tc(algo, tc_configs):
                raise RuntimeError("ETS/Strict TC 算法及带宽配置失败")

            tc_max_dict = {tc.tc_id: tc.max_rate_kbps for tc in tc_configs if tc.max_rate_kbps > 0}
            if tc_max_dict and not self.set_tc_max_rate_bulk(tc_max_dict):
                raise RuntimeError(f"TC 限速设置失败: {tc_max_dict}")

            if not self.bind_priority_to_dscp(prio, dscp):
                raise RuntimeError(f"Priority {prio} 与 DSCP {dscp} 绑定失败")

            log.info(f"网卡 [{self.interface_name}] DCB ETS 配置下发成功")
            return True

        except Exception as e:
            log.error(f"配置过程中发生异常: {e}，开始恢复默认配置")
            if not self.restore_state():
                log.error("恢复默认配置失败")
            return False

    # =========================================================================
    # 抽象方法: 由具体实现类负责真实指令下发
    # =========================================================================
    @abstractmethod
    def set_dcbx_host_ieee(self) -> bool:
        """步骤2: 设置 dcbx host ieee"""
        pass

    @abstractmethod
    def get_max_supported_tcs(self) -> int:
        """步骤1: 获取网卡支持的最大 TC 数量"""
        pass

    @abstractmethod
    def configure_ets_tc(self, algo: EtsAlgorithm, tc_configs: list,
                         prio_tc: Optional[list] = None) -> bool:
        """步骤4: 配置 ETS/Strict 带宽与优先级到 TC 的映射"""
        pass

    @abstractmethod
    def show_ets(self) -> str:
        """步骤5: 查询 dcb ets show dev <intf>"""
        pass

    @abstractmethod
    def set_tc_max_rate(self, tc_id: int, max_rate_kbps: int) -> bool:
        """步骤7: 对单个 TC 设置限速"""
        pass

    @abstractmethod
    def set_tc_max_rate_bulk(self, tc_max_dict: dict) -> bool:
        """步骤7: 一条命令批量设置多个 TC 的限速"""
        pass

    @abstractmethod
    def bind_priority_to_dscp(self, prio: int, dscp: int) -> bool:
        """步骤8: dcb app 绑定优先级与 dscp"""
        pass

    @abstractmethod
    def restore_state(self) -> bool:
        """回滚: 恢复默认 dcb/ets 配置"""
        pass


class LinuxDcbCmdManager(DcbEtsTcManager):
    """
    Linux 真实命令实现类

    全部指令使用 iproute2 的 dcb 命令（与测试用例指令逐字对齐），
    不依赖 dcbtool / DcbtoolOperation 公共库
    """

    def _exec(self, cmd: str) -> tuple:
        """执行命令并打印日志，返回 (rtn_code, rtn_outputs, rtn_err)"""
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=self.cmd_execute_address)
        log.info(f"执行命令: {cmd}, 返回码: {rtn_code}, 标准输出: {rtn_outputs}, 错误输出: {rtn_err}")
        return rtn_code, rtn_outputs, rtn_err

    @staticmethod
    def _is_success(rtn_code: int) -> bool:
        return rtn_code == RtnStatusEnum.SUCCESS.value

    # -------------------------------------------------------------------------
    # 步骤2: dcbx host ieee
    # -------------------------------------------------------------------------
    def set_dcbx_host_ieee(self) -> bool:
        cmd = f"dcb dcbx set dev {self.interface_name} host ieee"
        rtn_code, _, _ = self._exec(cmd)
        return self._is_success(rtn_code)

    # -------------------------------------------------------------------------
    # 步骤1: 网卡支持的最大 TC 数量
    # -------------------------------------------------------------------------
    def get_max_supported_tcs(self) -> int:
        rtn_code, rtn_outputs, _ = self._exec(f"dcb ets show dev {self.interface_name}")
        if self._is_success(rtn_code):
            for line in rtn_outputs.splitlines():
                if "tc-bw" in line:
                    tc_num = len(re.findall(r"\d+:\d+", line))
                    if tc_num:
                        log.info(f"网卡 [{self.interface_name}] 支持的最大 TC 数量: {tc_num}")
                        return tc_num
        # 解析失败兜底为内核 ETS 支持的最大 TC 数（TC_BW_MAX）
        log.info(f"网卡 [{self.interface_name}] 支持的最大 TC 数量: 8")
        return 8

    # -------------------------------------------------------------------------
    # 步骤4: 配置 ETS/Strict 带宽与 prio-tc 映射
    # -------------------------------------------------------------------------
    def configure_ets_tc(self, algo: EtsAlgorithm, tc_configs: list,
                         prio_tc: Optional[list] = None) -> bool:
        tc_map = {tc.tc_id: tc for tc in tc_configs}
        strict_flag = (algo == EtsAlgorithm.STRICT)
        tsa_parts = []
        bw_parts = []
        for tc_id in range(8):
            tc = tc_map.get(tc_id)
            is_strict = strict_flag or (tc is not None and tc.is_strict)
            weight = 0 if is_strict else (tc.weight if tc else 0)
            tsa_parts.append(f"{tc_id}:strict" if is_strict else f"{tc_id}:ets")
            bw_parts.append(f"{tc_id}:{weight}")

        tsa_str = "all:ets" if all("strict" not in t for t in tsa_parts) else " ".join(tsa_parts)
        bw_str = " ".join(bw_parts)

        if prio_tc is None:
            prio_tc = list(range(8))
        if len(prio_tc) != 8:
            raise ValueError(f"prio_tc 长度必须为 8 (索引为优先级, 值为 TC), 当前: {len(prio_tc)}")
        prio_str = " ".join(f"{i}:{prio_tc[i]}" for i in range(8))

        cmd = (f"dcb ets set dev {self.interface_name} tc-tsa {tsa_str} "
               f"tc-bw {bw_str} prio-tc {prio_str}")
        rtn_code, _, _ = self._exec(cmd)
        return self._is_success(rtn_code)

    # -------------------------------------------------------------------------
    # 步骤5: 查询 dcb ets show
    # -------------------------------------------------------------------------
    def show_ets(self) -> str:
        cmd = f"dcb ets show dev {self.interface_name}"
        rtn_code, rtn_outputs, _ = self._exec(cmd)
        return rtn_outputs if self._is_success(rtn_code) else ""

    # -------------------------------------------------------------------------
    # 步骤7: TC 限速
    # -------------------------------------------------------------------------
    def set_tc_max_rate(self, tc_id: int, max_rate_kbps: int) -> bool:
        """兼容单 TC 配置场景"""
        return self.set_tc_max_rate_bulk({tc_id: max_rate_kbps})

    def set_tc_max_rate_bulk(self, tc_max_dict: dict) -> bool:
        """一条命令批量设置多个 TC 限速，如 tc-max 0:200Mbit 1:400Mbit ...
        限速值必须携带速率单位(Mbit)，否则 dcb 会按最低粒度(8Kbit)错误换算"""
        rate_str = " ".join(f"{k}:{v}Mbit" for k, v in tc_max_dict.items())
        cmd = f"dcb maxrate set dev {self.interface_name} tc-max {rate_str}"
        rtn_code, _, _ = self._exec(cmd)
        return self._is_success(rtn_code)

    # -------------------------------------------------------------------------
    # 步骤8: 绑定优先级与 dscp
    # -------------------------------------------------------------------------
    def bind_priority_to_dscp(self, prio: int, dscp: int) -> bool:
        cmd = f"dcb app replace dev {self.interface_name} dscp-prio {dscp}:{prio}"
        rtn_code, _, _ = self._exec(cmd)
        return self._is_success(rtn_code)

    # -------------------------------------------------------------------------
    # 回滚: 恢复默认 dcb/ets 配置
    # -------------------------------------------------------------------------
    def restore_state(self) -> bool:
        dcbx_cmd = f"dcb dcbx set dev {self.interface_name} host ieee"
        dcb_cmd = (f"dcb ets set dev {self.interface_name} tc-tsa all:ets "
                   f"tc-bw {self.init_tc_bw} prio-tc {self.init_prio_tc}")
        app_cmd = f"dcb app flush dev {self.interface_name}"
        rtn_code, _, _ = self._exec(dcbx_cmd)
        if not self._is_success(rtn_code):
            return False
        rtn_code, _, _ = self._exec(dcb_cmd)
        if not self._is_success(rtn_code):
            return False
        rtn_code, _, _ = self._exec(app_cmd)
        return self._is_success(rtn_code)


class ScriptBaseTxSchedReliabilityCosTest(ScriptBase):
    """nic800 linux driver tx_scheduler 模块 cos 类用例脚本的二级基类"""

    # 测试机业务ip
    server_ip, client_ip = CommonOperation.get_nic_logical_ip()
    # 指令执行端
    exec_address = CmdExecuteAdressEnum.SERVER.value
    other_exec_address = CmdExecuteAdressEnum.CLIENT.value
    do_step = 1
    post_step = 1

    @classmethod
    def set_parameters(cls) -> None:
        """
        author:      weiyuan1
        date:        2026.09.07
        description: 设置配置环境需要的参数
        """
        super().set_parameters()
        cls.test_object = 'nic800'
        cls.test_module = 'driver'
        cls.test_tool = ''
        cls.test_precondition = ''

    # ---------------------------------------------------------------------
    # dcb ets 修改 tc 便捷入口：供用例 do() 直接调用
    # ---------------------------------------------------------------------
    @classmethod
    def _dcb_manager(cls, ifname: str, cmd_execute_address: str = None) -> LinuxDcbCmdManager:
        return LinuxDcbCmdManager(ifname, cmd_execute_address or cls.exec_address)

    @classmethod
    def dcb_ets_modify_tc(cls, ifname: str, algo: EtsAlgorithm, tc_configs: list,
                          prio: int, dscp: int, cmd_execute_address: str = None) -> bool:
        """步骤1/2/4/5/7/8 全流程：dcbx host ieee → 检查tc数 → ets带宽 → 限速 → prio/dscp绑定"""
        return cls._dcb_manager(ifname, cmd_execute_address).dcb_ets_modify_tc(algo, tc_configs, prio, dscp)

    @classmethod
    def set_dcbx_host_ieee(cls, ifname: str, cmd_execute_address: str = None) -> bool:
        """步骤2：设置 dcbx host ieee"""
        return cls._dcb_manager(ifname, cmd_execute_address).set_dcbx_host_ieee()

    @classmethod
    def get_max_supported_tcs(cls, ifname: str, cmd_execute_address: str = None) -> int:
        """步骤1：检查网卡支持的 tc 数量"""
        return cls._dcb_manager(ifname, cmd_execute_address).get_max_supported_tcs()

    @classmethod
    def configure_ets_tc(cls, ifname: str, algo: EtsAlgorithm, tc_configs: list,
                         prio_tc: list = None, cmd_execute_address: str = None) -> bool:
        """步骤4：配置 ETS/Strict 带宽与 prio-tc 映射"""
        return cls._dcb_manager(ifname, cmd_execute_address).configure_ets_tc(algo, tc_configs, prio_tc)

    @classmethod
    def show_ets(cls, ifname: str, cmd_execute_address: str = None) -> str:
        """步骤5：查询 dcb ets show dev <ifname>，返回输出文本"""
        return cls._dcb_manager(ifname, cmd_execute_address).show_ets()

    @classmethod
    def set_tc_max_rate(cls, ifname: str, tc_id: int, max_rate_kbps: int,
                        cmd_execute_address: str = None) -> bool:
        """步骤7：对单个 tc 设置限速"""
        return cls._dcb_manager(ifname, cmd_execute_address).set_tc_max_rate(tc_id, max_rate_kbps)

    @classmethod
    def set_tcs_max_rate(cls, ifname: str, tc_max_dict: dict,
                         cmd_execute_address: str = None) -> bool:
        """步骤7：一条命令批量设置多个 tc 的限速，如 {0: 200, 1: 400}"""
        return cls._dcb_manager(ifname, cmd_execute_address).set_tc_max_rate_bulk(tc_max_dict)

    @classmethod
    def bind_priority_to_dscp(cls, ifname: str, prio: int, dscp: int,
                              cmd_execute_address: str = None) -> bool:
        """步骤8：dcb app 绑定优先级与 dscp"""
        return cls._dcb_manager(ifname, cmd_execute_address).bind_priority_to_dscp(prio, dscp)

    @classmethod
    def result_collect(cls, rtn_code: int, expect_info: str, result: str,
                       description: str = None, create_bug: bool = True,
                       keyword: str = None) -> None:
        """
        author:      weiyuan1
        date:        2026.09.07
        description: 收集测试结果并校验，description 默认取 concat_test_steps 累计的测试步骤内容
        """
        if description is None:
            description = ScriptBase.test_steps
        CommonOperation.result_collect(
            case_cls=cls, expect_rtn=True, rtn_code=rtn_code,
            description=description, expect_info=expect_info, result=result,
            create_bug=create_bug, keyword=keyword)

    # ---------------------------------------------------------------------
    # 可靠性用例公共方法（r_025~029）：反向断言 / 链路状态 / 切速 / 复位 / VF
    # ---------------------------------------------------------------------
    @classmethod
    def execute_and_assert_fail(cls, cmd: str, expect_info: str,
                                cmd_execute_address: str = None,
                                description: str = None) -> bool:
        """
        author:      weiyuan1
        date:        2026.09.14
        description: 执行命令并断言其失败（反向用例），命令返回非 0 视为预期达成(PASS)。
                     内部通过 result_collect 收集结果，反向断言通过时 rtn_code 传 0。
        :param cmd:                  待执行命令
        :param expect_info:          期望结果描述（如 '命令执行失败'）
        :param cmd_execute_address:  执行端，默认 exec_address
        :param description:          测试步骤描述，默认取 concat_test_steps 累计内容
        :return: True 表示命令按预期失败，False 表示命令意外成功
        """
        exec_addr = cmd_execute_address or cls.exec_address
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr)
        passed = rtn_code != RtnStatusEnum.SUCCESS.value
        detail = f'命令: {cmd}, 返回码: {rtn_code}（期望非 0 即失败）'
        if rtn_outputs and rtn_outputs.strip():
            detail += f', 标准输出: {rtn_outputs.strip()[:300]}'
        if rtn_err and rtn_err.strip():
            detail += f', 错误输出: {rtn_err.strip()[:300]}'
        cls.result_collect(
            0 if passed else 1, expect_info, detail,
            description=description)
        return passed

    @classmethod
    def set_link_state(cls, ifname: str, state: str,
                       cmd_execute_address: str = None) -> bool:
        """
        author:      weiyuan1
        date:        2026.09.14
        description: 设置端口链路状态 up/down（ip link set dev <ifname> [up|down]）。
                     注意：业务口与管理口分离时该操作不影响 ssh 管理连接。
        :param ifname: 网口名
        :param state:  'up' 或 'down'
        :return: True 设置成功
        """
        if state not in ('up', 'down'):
            raise ValueError(f'state 必须为 up/down, 当前: {state}')
        exec_addr = cmd_execute_address or cls.exec_address
        rtn_code, _, rtn_err = CommandOperation.execute_command_with_error(
            cmd=f'ip link set dev {ifname} {state}',
            cmd_execute_address=exec_addr)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            log.error(f'设置链路 {ifname} {state} 失败: {rtn_err}')
            return False
        log.info(f'链路 {ifname} 已设置 {state}')
        return True

    @classmethod
    def wait_link_up(cls, ifname: str, timeout: int = 60,
                     cmd_execute_address: str = None) -> bool:
        """
        author:      weiyuan1
        date:        2026.09.14
        description: 轮询等待端口 Link detected 变为 yes（复位/切速/链路恢复后使用）
        :return: True 在超时前恢复
        """
        exec_addr = cmd_execute_address or cls.exec_address
        import time as _time
        for _ in range(timeout):
            rtn_code, rtn_outputs, _ = CommandOperation.execute_command_with_error(
                cmd=f'ethtool {ifname}', cmd_execute_address=exec_addr)
            if rtn_code == RtnStatusEnum.SUCCESS.value and \
                    'Link detected: yes' in rtn_outputs:
                log.info(f'链路 {ifname} 已恢复 up')
                return True
            _time.sleep(1)
        log.error(f'等待 {timeout}s 链路 {ifname} 未恢复 up')
        return False

    @classmethod
    def wait_dcb_ready(cls, ifname: str, timeout: int = 30,
                       cmd_execute_address: str = None) -> bool:
        """
        author:      weiyuan1
        date:        2026.09.14
        description: 轮询等待 dcb 子系统就绪。PFLR(syfs reset) 复位后 dcb 软件
                     对象短暂不可用（dcb ets show 报 'Attribute not found: Success'，
                     实测约 5s 恢复），在复位后恢复 dcb 配置前调用，避免恢复命令落空。
        :return: True 在超时前 dcb 子系统就绪
        """
        exec_addr = cmd_execute_address or cls.exec_address
        import time as _time
        for _ in range(timeout):
            rtn_code, _, rtn_err = CommandOperation.execute_command_with_error(
                cmd=f'dcb ets show dev {ifname}', cmd_execute_address=exec_addr)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'dcb 子系统 {ifname} 已就绪')
                return True
            log.info(f'等待 dcb 子系统 {ifname} 就绪（第 {_ + 1} 秒）: '
                     f'{rtn_err.strip()[:80]}')
            _time.sleep(1)
        log.error(f'等待 {timeout}s dcb 子系统 {ifname} 未就绪')
        return False

    @classmethod
    def set_port_speed(cls, ifname: str, speed_mbps: int,
                       cmd_execute_address: str = None) -> bool:
        """
        author:      weiyuan1
        date:        2026.09.14
        description: 切速：ethtool -s <ifname> speed <speed> duplex full，
                     链路自动协商由对端配合（双端需同时切到同一速率）。
        :param speed_mbps: 目标速率 Mbps，如 50000 / 100000
        :return: True 切速命令下发成功
        """
        exec_addr = cmd_execute_address or cls.exec_address
        cmd = f'ethtool -s {ifname} speed {speed_mbps} duplex full'
        rtn_code, _, rtn_err = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            log.error(f'切速 {ifname} 到 {speed_mbps}Mbps 失败: {rtn_err}')
            return False
        log.info(f'切速 {ifname} 到 {speed_mbps}Mbps 成功')
        return True

    @classmethod
    def get_port_speed(cls, ifname: str,
                       cmd_execute_address: str = None) -> int:
        """
        author:      weiyuan1
        date:        2026.09.14
        description: 获取端口当前速率(Mbps)，解析 ethtool 输出 Speed 字段，失败返回 0
        """
        exec_addr = cmd_execute_address or cls.exec_address
        rtn_code, rtn_outputs, _ = CommandOperation.execute_command_with_error(
            cmd=f'ethtool {ifname}', cmd_execute_address=exec_addr)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            return 0
        match = re.search(r'Speed:\s*([\d.]+)Mb/s', rtn_outputs)
        return int(float(match.group(1))) if match else 0

    @classmethod
    def do_reset(cls, reset_type: str, device_bdf: str,
                 ifname: str = None, cmd_execute_address: str = None,
                 vf_bdf: str = None, wait_timeout: int = 180) -> bool:
        """
        author:      weiyuan1
        date:        2026.09.14
        description: 按复位类型执行复位（028 系列）。
                     支持类型：
                       GLR      - 固件全局复位（mlxfwreset -d <bdf> reset）
                       core     - core reset（mlxfwreset level=3）
                       PFLR     - PCIe 功能级复位（echo 1 > /sys/bus/pci/devices/<bdf>/reset）
                       VFLR     - VF 功能级复位（echo 1 > /sys/bus/pci/devices/<vf_bdf>/reset）
                       VFR      - VF 复位（devlink port function / ethtool 替代，先尝试 sysfs reset）
        :param reset_type: 复位类型（GLR/core/PFLR/VFLR/VFR）
        :param device_bdf: PF 的 BDF（如 0000:a8:00.0）
        :param ifname:     PF 网口名（等待链路恢复用，可空）
        :param vf_bdf:     VF 的 BDF（VFLR/VFR 需要）
        :return: True 复位成功且（若提供 ifname）链路恢复
        """
        exec_addr = cmd_execute_address or cls.exec_address
        rtype = reset_type.upper()
        # GLR/CORE 经 mlxfwreset 执行，会重载驱动（复位期间 SSH 会话可能被重置，本机 ssh 返回非 0 属预期）
        driver_reload = rtype in ('GLR', 'CORE')
        if rtype == 'GLR':
            # 固件级复位（默认 level 3: Driver restart + PCI reset），-y 跳过交互确认，重载驱动，需等待链路恢复
            cmd = f'mlxfwreset -d {device_bdf} -y reset'
        elif rtype == 'CORE':
            # core reset = Full chip reset（mlxfwreset --type 0，实测 type 0 支持且默认），-y 跳过交互确认
            cmd = f'mlxfwreset -d {device_bdf} -y --type 0 reset'
        elif rtype == 'PFLR':
            cmd = f'echo 1 > /sys/bus/pci/devices/{device_bdf}/reset'
        elif rtype == 'VFLR':
            if not vf_bdf:
                log.error('VFLR 复位需要提供 vf_bdf')
                return False
            cmd = f'echo 1 > /sys/bus/pci/devices/{vf_bdf}/reset'
        elif rtype == 'VFR':
            if not vf_bdf:
                log.error('VFR 复位需要提供 vf_bdf')
                return False
            cmd = f'echo 1 > /sys/bus/pci/devices/{vf_bdf}/reset'
        else:
            log.error(f'不支持的复位类型: {reset_type}')
            return False
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'复位({reset_type})命令下发成功: {cmd}, 输出: {rtn_outputs}')
        elif driver_reload:
            # 驱动重载型复位：复位生效瞬间远端驱动卸载/PCI reset，SSH 连接可能被重置导致本机 ssh 返回非 0。
            # 仅当输出含明确失败标志时判定失败，否则视为复位已触发，靠链路恢复来验证。
            combined = f'{rtn_outputs} {rtn_err}'
            fail_pattern = re.compile(
                r'EOF when reading|Failed|ERROR|Aborted|not supported|unsupported|'
                r'Cannot|cannot|Unable|unable', re.IGNORECASE)
            if fail_pattern.search(combined):
                log.error(f'复位({reset_type})执行失败: {rtn_err}')
                return False
            if not ifname:
                # 无 ifname 时缺少链路佐证，保守判定失败
                log.error(f'复位({reset_type})命令返回码 {rtn_code} 且未提供 ifname，无法确认复位成功: {rtn_err}')
                return False
            log.warning(f'复位({reset_type})命令返回码 {rtn_code}（驱动重载/SSH 断开预期内），'
                        f'输出: {rtn_outputs} {rtn_err}；等待链路恢复确认')
        else:
            log.error(f'复位({reset_type})执行失败: {rtn_err}')
            return False
        if ifname:
            link_ok = cls.wait_link_up(ifname, timeout=wait_timeout,
                                       cmd_execute_address=exec_addr)
            if not link_ok:
                log.error(f'复位({reset_type})后等待链路 {ifname} 恢复失败')
                return False
        return True

    @classmethod
    def get_device_bdf(cls, ifname: str,
                       cmd_execute_address: str = None) -> str:
        """
        author:      weiyuan1
        date:        2026.09.14
        description: 获取网口对应 PCI BDF（如 0000:a8:00.0），用于复位操作。
        :param ifname: 网口名（PF 或 VF 均可）
        :return: BDF 字符串，获取失败返回空串
        """
        exec_addr = cmd_execute_address or cls.exec_address
        rtn_code, rtn_outputs, _ = CommandOperation.execute_command_with_error(
            cmd=f'basename $(readlink -f /sys/class/net/{ifname}/device)',
            cmd_execute_address=exec_addr)
        bdf = rtn_outputs.strip() if rtn_code == RtnStatusEnum.SUCCESS.value else ''
        if not re.match(r'^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F]$', bdf):
            log.error(f'获取网口 {ifname} 的 PCI BDF 失败: {rtn_outputs}')
            return ''
        log.info(f'网口 {ifname} 对应 PCI BDF: {bdf}')
        return bdf

    @classmethod
    def ensure_pf_ip(cls, ifname: str, ip: str, netmask: str = '24',
                     cmd_execute_address: str = None) -> bool:
        """
        author:      weiyuan1
        date:        2026.09.14
        description: 确保网口 IP 存在（复位/驱动重载后若 IP 丢失则重新配置）。
        :return: True 表示 IP 已存在或恢复成功
        """
        exec_addr = cmd_execute_address or cls.exec_address
        rtn_code, rtn_outputs, _ = CommandOperation.execute_command_with_error(
            cmd=f'ip addr show {ifname}', cmd_execute_address=exec_addr)
        if f'inet {ip}/' in rtn_outputs:
            log.info(f'网口 {ifname} IP {ip} 已存在，无需恢复')
            return True
        for cmd in (f'ip addr flush dev {ifname} 2>/dev/null || true',
                    f'ip addr add {ip}/{netmask} dev {ifname}',
                    f'ip link set {ifname} up'):
            code, _, err = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=exec_addr)
            if code != RtnStatusEnum.SUCCESS.value:
                log.error(f'恢复网口 {ifname} 执行 {cmd} 失败: {err}')
                return False
        log.info(f'网口 {ifname} 已恢复 IP {ip}/{netmask}')
        return True

    @classmethod
    def _list_vf_names(cls, ifname: str,
                       cmd_execute_address: str = None) -> list:
        """列出当前已创建的 VF 网口名（virtfn* 下 net 目录）。"""
        exec_addr = cmd_execute_address or cls.exec_address
        rtn_code, rtn_outputs, _ = CommandOperation.execute_command_with_error(
            cmd=f'ls /sys/class/net/{ifname}/device/virtfn*/net/ 2>/dev/null',
            cmd_execute_address=exec_addr)
        vf_names = []
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            vf_names = [line.strip() for line in rtn_outputs.splitlines()
                        if line.strip()]
        return vf_names

    @classmethod
    def ensure_vf_after_reset(cls, ifname: str, ifname_other: str,
                              server_vf_ip: str, client_vf_ip: str,
                              netmask: str = '24') -> tuple:
        """
        author:      weiyuan1
        date:        2026.09.14
        description: 复位后确保双端 VF 存在且 IP 正确（GLR/PFLR/core 复位会销毁 VF，
                     VFR/VFLR 只复位 VF 本身；VF netdev 丢失时重建，IP 丢失时重配）。
        :return: (是否成功, server端VF名, client端VF名)
        """
        results = []
        for exec_addr, pf, vf_ip in (
                (cls.exec_address, ifname, server_vf_ip),
                (cls.other_exec_address, ifname_other, client_vf_ip)):
            vf_names = cls._list_vf_names(pf, cmd_execute_address=exec_addr)
            if not vf_names:
                log.warning(f'{pf} 复位后 VF 不存在，重新创建')
                vf_names = cls.create_vf(pf, cmd_execute_address=exec_addr)
            if not vf_names:
                log.error(f'{pf} 复位后 VF 恢复失败')
                results.append((False, None))
                continue
            vf_name = vf_names[0]
            vf_ok = cls.ensure_pf_ip(
                vf_name, vf_ip, netmask=netmask, cmd_execute_address=exec_addr)
            results.append((vf_ok, vf_name))
        server_ok, server_vf = results[0] if len(results) > 0 else (False, None)
        client_ok, client_vf = results[1] if len(results) > 1 else (False, None)
        ok = server_ok and client_ok
        log.info(f'复位后 VF 恢复结果: {ok}, server={server_vf}({server_vf_ip}), '
                 f'client={client_vf}({client_vf_ip})')
        return ok, server_vf, client_vf

    @classmethod
    def create_vf(cls, ifname: str, vf_count: int = 1,
                  cmd_execute_address: str = None) -> list:
        """
        author:      weiyuan1
        date:        2026.09.14
        description: 创建 VF（echo <n> > /sys/class/net/<ifname>/device/sriov_numvfs），
                     返回创建的 VF 网口名列表。
        :return: VF 网口名列表（如 ['ens25f0np0v0', ...]）
        """
        exec_addr = cmd_execute_address or cls.exec_address
        cmd = f'echo {vf_count} > /sys/class/net/{ifname}/device/sriov_numvfs'
        rtn_code, _, rtn_err = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            log.error(f'创建 VF 失败: {rtn_err}')
            return []
        time.sleep(5)
        # 获取实际创建的 VF 网口名
        rtn_code, rtn_outputs, _ = CommandOperation.execute_command_with_error(
            cmd=f'ls /sys/class/net/{ifname}/device/virtfn*/net/ 2>/dev/null',
            cmd_execute_address=exec_addr)
        vf_names = []
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            vf_names = [line.strip() for line in rtn_outputs.splitlines() if line.strip()]
        log.info(f'创建 VF 数量: {vf_count}, VF 网口: {vf_names}')
        return vf_names

    @classmethod
    def destroy_vf(cls, ifname: str, cmd_execute_address: str = None) -> bool:
        """
        author:      weiyuan1
        date:        2026.09.14
        description: 销毁 VF（echo 0 > sriov_numvfs）
        """
        exec_addr = cmd_execute_address or cls.exec_address
        cmd = f'echo 0 > /sys/class/net/{ifname}/device/sriov_numvfs'
        rtn_code, _, rtn_err = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            log.error(f'销毁 VF 失败: {rtn_err}')
            return False
        log.info(f'VF 已销毁: {ifname}')
        return True

    @classmethod
    def check_tc_config_unchanged(cls, baseline: int, after: int,
                                  expect_info: str) -> bool:
        """
        author:      weiyuan1
        date:        2026.09.14
        description: 校验复位/切速/链路切换后调度树 tc 节点配置是否保持不变。
                     本驱动未暴露 debugfs 调度树时按 021_030 约定回退 dcb ets 计数。
        :return: True 表示保持不变（节点数相同且均非 -1）
        """
        if baseline < 0 or after < 0:
            cls.result_collect(
                1, expect_info,
                f'tx_sched 调度树节点获取失败: 基线={baseline}, 之后={after}')
            return False
        unchanged = baseline == after
        cls.result_collect(
            0 if unchanged else 1, expect_info,
            f'tx_sched 调度树 tc 节点数量: 之前={baseline}, 之后={after}, '
            f'保持不变: {unchanged}'
            f'（本驱动未暴露debugfs调度树，按dcb ets参与调度tc计数）')
        return unchanged

    # ---------------------------------------------------------------------
    # 多 TOS 异步打流：每个 (tos, port) 组合一个 iperf3 client 并发打流
    # ---------------------------------------------------------------------
    @classmethod
    def start_multi_tos_iperf(cls, tos_port_list: list, run_time: int = 60,
                              bandwidth: str = '1000M', packet_length: int = 64,
                              parallel_num: int = 8, interval: str = '5',
                              udp_flag: bool = False, server_ip: str = None,
                              client_ip: str = None) -> None:
        """
        author:      weiyuan1
        date:        2026.09.08
        description: 启动多个 iperf3 进程按 tos 优先级同时打流，不同 tos 使用不同端口，
                     与用例步骤「启动多个iperf3进程按照tos优先级同时进行打流（指令：iperf3 --tos <tos>）」对应。
                     每个 port 先在 server 端后台守护启动 iperf3 server，再为每个 (tos, port)
                     创建一个异步线程并发执行 iperf3 client 打流，结束后统一清理 iperf3 进程。
        :param tos_port_list:  [(tos, port), ...]，如 [(46, 5201), (26, 5202)]，tos 值须与
                               dcb app 绑定的 dscp 对应，port 为各 tos 使用的不同端口号
        :param run_time:       打流时长(秒)，默认 60
        :param bandwidth:      client 带宽，默认 1000M
        :param packet_length:  发包大小，默认 64
        :param parallel_num:   并发流数，默认 8
        :param interval:       日志打印间隔，默认 5
        :param udp_flag:       是否 UDP 打流，默认 False(TCP)
        :param server_ip:      iperf3 client 的目标(server)IP，默认取 test_device_info_dict
                               的 server_device_ip；VF 打流时传入 VF IP
        :param client_ip:      iperf3 client 的本端(bind)IP，默认取 test_device_info_dict
                               的 client_device_ip；VF 打流时传入 VF IP
        """
        for _, port in tos_port_list:
            IperfOperation.iperf3_test_exit(port)

        # 每个 port 在 server 端后台守护启动 iperf3 server（-D 便于后续按 port 清理）
        for _, port in tos_port_list:
            CommandOperation.execute_command_with_error(
                cmd='iperf3 -s -D -p {}'.format(port),
                cmd_execute_address=cls.exec_address)
        time.sleep(3)

        # 每个 (tos, port) 组合一个异步线程并发打流
        threads = []
        for tos, port in tos_port_list:
            iperf_op = IperfOperation(
                caller_class=cls, iperf_port=port, tos=tos, run_time=run_time,
                bandwidth=bandwidth, packet_length=packet_length,
                parallel_num=parallel_num, interval=interval, udp_flag=udp_flag)
            thread = SxeThread(
                iperf_op.client_iperf, client_ip or '', server_ip or '')
            thread.setDaemon(True)
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        # 打流结束后清理所有 iperf3 进程
        for _, port in tos_port_list:
            IperfOperation.iperf3_test_exit(port)

    # ---------------------------------------------------------------------
    # 调度节点统计与结果解析：用例 do() 中步骤6/9 共用（由 021_001/021_030 提取上移）
    # ---------------------------------------------------------------------
    @classmethod
    def _get_tx_sched_tc_nodes(cls) -> int:
        """统计 tx_sched 调度树 tc 节点数量，获取失败返回 -1。

        优先读取 debugfs 下名称含 sched 的节点文件；本驱动未暴露调度树
        (debugfs 无 sched 节点文件或缺少 bdf 信息)时，回退为解析
        dcb ets show 中带宽权重>0 的 tc 数量作为参与调度的 tc 节点数。
        """
        ifname = cls.test_device_info_dict.get('server_pf_device_name')
        if not ifname:
            log.error('未获取到 server_pf_device_name，无法统计 tx_sched 调度树')
            return -1
        try:
            bdf = cls.test_device_info_dict.get('server_bus_info')
            if bdf:
                server_driver, _ = CommonOperation.get_nic_driver_name()
                base_dir = f'/sys/kernel/debug/{server_driver}/{bdf}'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                    cmd=f'find {base_dir} -iname "*sched*" -type f 2>/dev/null',
                    cmd_execute_address=cls.exec_address)
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.error(f'查找 tx_sched 调度树节点失败: {rtn_err}')
                else:
                    node_files = [line.strip() for line in rtn_outputs.splitlines()
                                  if line.strip()]
                    if node_files:
                        tc_node_count = 0
                        for node_file in node_files:
                            code, content, err = CommandOperation.execute_command_with_error(
                                cmd=f'cat {node_file}',
                                cmd_execute_address=cls.exec_address)
                            if code != RtnStatusEnum.SUCCESS.value:
                                log.warning(f'读取 tx_sched 节点文件失败: {node_file}: {err}')
                                continue
                            tc_node_count += len(
                                re.findall(r'tc[0-7]', content, re.IGNORECASE))
                        log.info(f'tx_sched 调度树 tc 节点数量(debugfs): {tc_node_count}')
                        return tc_node_count
                    log.warning(f'{base_dir} 下未找到名称含 sched 的节点文件，'
                                f'回退解析 dcb ets show 统计参与调度的 tc 数量')
            else:
                log.warning('未获取到 server_bus_info，回退解析 dcb ets show '
                            '统计参与调度的 tc 数量')
            return cls._count_ets_active_tcs(ifname)
        except Exception as e:
            log.error(f'读取 tx_sched 调度树 tc 节点信息异常: {e}')
            return -1

    @classmethod
    def _count_ets_active_tcs(cls, ifname: str) -> int:
        """解析 dcb ets show 输出，返回带宽权重>0 的 tc 数量，解析失败返回 -1"""
        rtn_code, rtn_outputs, _ = CommandOperation.execute_command_with_error(
            cmd=f'dcb ets show dev {ifname}', cmd_execute_address=cls.exec_address)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            log.error(f'dcb ets show dev {ifname} 执行失败，无法统计 tc 数量')
            return -1
        for line in rtn_outputs.splitlines():
            if 'tc-bw' not in line:
                continue
            weights = re.findall(r'(\d+):(\d+)', line)
            if not weights:
                continue
            active = sum(1 for _, weight in weights if int(weight) > 0)
            log.info(f'dcb ets show 参与调度的 tc 数量(权重>0): {active}')
            return active
        log.error(f'dcb ets show 输出中未找到 tc-bw 行，无法统计 tc 数量')
        return -1

    @classmethod
    def _parse_iperf_bitrates(cls) -> list:
        """解析 iperf_result_list 中每条流 [SUM] 行末尾带宽，返回 [(value, unit)]"""
        bitrates = []
        for rtn_outputs in cls.iperf_result_list:
            matches = re.findall(
                r'\[SUM\].*?([\d.]+) ([GMK]?)bits/sec', rtn_outputs,
                re.DOTALL)
            if matches:
                value, unit = matches[-1]
                try:
                    bitrates.append((float(value), unit))
                except ValueError:
                    bitrates.append((0.0, unit))
            else:
                bitrates.append((0.0, ''))
        return bitrates
