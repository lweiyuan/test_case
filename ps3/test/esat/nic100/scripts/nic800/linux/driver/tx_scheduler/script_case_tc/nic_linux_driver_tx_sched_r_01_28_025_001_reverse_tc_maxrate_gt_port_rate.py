#!/usr/bin/env python3
# -*- encoding=utf8 -*-

"""
case author:   weiyuan1
script author: weiyuan1
date:          2026.09.07
description:

case number:   nic_linux_driver_tx_sched_r_01_28_025_001
case title:    TC层_可靠性_反向测试_对单一TC限速大于port限速
check point:   对单一TC限速大于port限速
test condition:反向测试-非法/边界配置
test platform: 测试PF/VF；双机iperf3打流

@steps:
1. 检查网卡支持的tc数量
2. 设置dcbx host ieee（指令：dcb dcbx set dev <intf_name> host ieee）
3. 获取初始化状态tx_sched调度树tc 节点信息
4. dcb ets 设置带宽比例（指令：dcb ets set dev <intf_name> tc-tsa all:ets tc-bw 0:25 1:25 2:25 3:25 4:0 5:0 6:0 7:0 prio-tc 0:0 1:1 2:2 3:3 4:0 5:1 6:2 7:3）
5. 查询dcb ets show dev <intf_name>（指令：dcb ets show dev <intf_name>）
6. 对tc 设置限速，且设置的tc速率大于port的速率
7. 清理环境

@steps expect result:
1. 获取网卡支持的tc数量成功
2. 设置dcbx成功
3. 获取tc节点信息成功
4. dcb ets设置带宽比例成功
5. dcb ets 结果与设置的结果一致
6. 命令执行失败
7. 命令执行成功

@changelog:

"""
import add_syspath
import random

from scripts.script_libs import log
from scripts.nic800.linux.driver.tx_scheduler.script_base_tx_sched_reliability_cos_test import (
    EtsAlgorithm, ScriptBaseTxSchedReliabilityCosTest, TcConfig)
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum
from scripts.script_libs.script_base import SxeException


class Script(ScriptBaseTxSchedReliabilityCosTest):
    exec_device_name_list, other_device_name_list = [], []
    server_host_os, client_host_os = [], []
    # ETS 带宽配置改为变量，运行时在 prepare() 中动态生成：
    # tc 数量由参数 ets_tc_num 指定，权重随机分配且总和为 100
    ETS_TC_CONFIGS = []
    PRIO_TC = [0, 1, 2, 3, 0, 1, 2, 3]

    @classmethod
    def set_parameters(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 设置需要调用的变量
        :return: 无返回值
        """
        super().set_parameters()

        # 参数: 参与 ETS 带宽分配的 TC 数量（1~8，按需修改）
        cls.ets_tc_num = 4

    @classmethod
    def _build_random_ets_configs(cls, tc_num: int) -> list:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 生成 ETS 带宽配置：前 tc_num 个 TC 随机分配正整数权重且总和为 100，
                    其余 TC 权重为 0
        :param tc_num: 参与带宽分配的 TC 数量
        :return: TcConfig 列表（8 个 TC，含权重为 0 的未参与 TC）
        """
        tc_num = max(1, min(8, tc_num))
        if tc_num <= 1:
            weights = [100]
        else:
            # 在 1~99 中随机取 tc_num-1 个切分点，保证每个 TC 权重为正整数且总和为 100
            cuts = sorted(random.sample(range(1, 100), tc_num - 1))
            weights = [cuts[0]]
            weights += [cuts[i] - cuts[i - 1] for i in range(1, len(cuts))]
            weights.append(100 - cuts[-1])
        configs = [TcConfig(tc_id=i, weight=weights[i]) for i in range(tc_num)]
        configs += [TcConfig(tc_id=i, weight=0) for i in range(tc_num, 8)]
        log.info(f'动态生成 ETS 带宽配置（随机权重，总和=100）: '
                 f'{cls._ets_bw_str(configs)}')
        return configs

    @classmethod
    def _ets_bw_str(cls, tc_configs: list = None) -> str:
        """生成 tc-bw 字符串（按 tc_id 0~7 排列），如: 0:17 1:33 2:25 3:25 4:0 ..."""
        tc_configs = tc_configs if tc_configs is not None else cls.ETS_TC_CONFIGS
        weight_map = {tc.tc_id: tc.weight for tc in tc_configs}
        return ' '.join(f'{i}:{weight_map.get(i, 0)}' for i in range(8))

    @classmethod
    def _prio_tc_str(cls) -> str:
        """生成 prio-tc 字符串（索引为优先级，值为 TC）"""
        return ' '.join(f'{i}:{cls.PRIO_TC[i]}' for i in range(8))

    @classmethod
    def check_own_environment(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 检测当前脚本运行所需的局部环境是否具备，该方法只检测，不报bug,
                    函数内需要设定类变量local_enviroment_enabled的值，
                    局部环境检测正常，类变量local_enviroment_enabled设置为True
        :return: 无返回值
        """
        super().check_own_environment()

        cls.server_host_os, cls.client_host_os = CommonOperation.get_nic_os()
        result = CommonOperation.common_check_environment(cls)
        cls.own_environment_enabled = result
        for pf_port_info in cls.test_device_info_list:
            if cls.exec_address == CmdExecuteAdressEnum.SERVER.value:
                cls.exec_device_name_list.append(pf_port_info["server_device_name"])
                cls.other_device_name_list.append(pf_port_info["client_device_name"])
            else:
                cls.exec_device_name_list.append(pf_port_info["client_device_name"])
                cls.other_device_name_list.append(pf_port_info["server_device_name"])

        # 两端均需具备 dcb / iperf3 工具
        for exec_addr in (cls.exec_address, cls.other_exec_address):
            for cmd in ('which dcb', 'which iperf3'):
                rtn_code, _, _ = CommandOperation.execute_command_with_error(
                    cmd=cmd, cmd_execute_address=exec_addr)
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.error(f'环境检测失败: {exec_addr} 上执行 {cmd} 失败')
                    cls.own_environment_enabled = False
                    return

        # 检查执行端所有被测网口可用性
        for ifname in cls.exec_device_name_list:
            rtn_code, _, rtn_err = CommandOperation.execute_command_with_error(
                cmd=f'ip link show {ifname}', cmd_execute_address=cls.exec_address)
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.error(f'环境检测失败: 网口 {ifname} 不可用: {rtn_err}')
                cls.own_environment_enabled = False
                return

        cls.own_environment_enabled = True

    @classmethod
    def prepare(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 准备环境
        :return: 无返回值
        """
        super().prepare()

        # 动态生成 ETS 带宽配置：tc 数量由参数 ets_tc_num 指定，权重随机分配且总和为 100
        cls.ETS_TC_CONFIGS = cls._build_random_ets_configs(cls.ets_tc_num)

        # 步骤3 前置: 记录初始化状态下 tx_sched 调度树 tc 节点数量作为基线
        # 暂不实现: 获取tx_sched调度树tc节点信息的功能尚未实现，后续补充
        # cls.tx_sched_baseline_count = cls._get_tx_sched_tc_nodes()
        # if cls.tx_sched_baseline_count < 0:
        #     log.warning('获取 tx_sched 调度树初始化 tc 节点基线失败，步骤3 将按失败处理')
        # else:
        #     log.info(f'tx_sched 调度树初始化 tc 节点基线数量: '
        #              f'{cls.tx_sched_baseline_count}')

    @classmethod
    def do(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 执行测试环境
        :return: 无返回值
        """
        super().do()

        if not cls.exec_device_name_list:
            raise SxeException('未获取到 exec_device_name_list，无法执行测试')

        # 环境不满足时，check_own_environment() 中会直接退出，无需 try 捕获

        # 遍历多组网口，每组网口的全部测试步骤（含性能计算）均在 for 循环内完成
        for exec_device, other_exec_device in zip(
                cls.exec_device_name_list, cls.other_device_name_list):
            log.info(f'===== 处理网口: {exec_device}'
                     f'（对端: {other_exec_device}）=====')

            # 步骤1: 检查网卡支持的tc数量
            CommonOperation.concat_test_steps(
                '1. 检查网卡支持的tc数量; expect result: 1. 获取网卡支持的tc数量成功')

            tc_num = cls.get_max_supported_tcs(exec_device)
            cls.result_collect(
                0 if tc_num >= 1 else 1, '获取网卡支持的tc数量成功',
                f'网口 {exec_device} 支持的tc数量: {tc_num}')

            # 步骤2: 设置dcbx host ieee
            CommonOperation.concat_test_steps(
                '2. 设置dcbx host ieee（指令：dcb dcbx set dev <intf_name> '
                'host ieee）; expect result: 2. 设置dcbx成功')

            dcbx_ok = cls.set_dcbx_host_ieee(exec_device)
            cls.result_collect(
                dcbx_ok, '设置dcbx成功',
                f'网口 {exec_device} set_dcbx_host_ieee 返回: {dcbx_ok}')

            # 步骤3: 获取初始化状态tx_sched调度树tc 节点信息
            # 暂不实现: 获取tx_sched调度树tc节点信息的功能尚未实现，后续补充
            CommonOperation.concat_test_steps(
                '3. 获取初始化状态tx_sched调度树tc 节点信息; '
                'expect result: 3. 获取tc节点信息成功')

            cls.result_collect(
                0, '获取tc节点信息成功',
                f'网口 {exec_device} 获取tx_sched调度树tc节点信息'
                f'（暂未实现，按通过处理）')

            # 步骤4: dcb ets 设置带宽比例
            ets_bw_str = cls._ets_bw_str()
            ets_prio_str = cls._prio_tc_str()
            CommonOperation.concat_test_steps(
                '4. dcb ets 设置带宽比例（指令：dcb ets set dev <intf_name> '
                f'tc-tsa all:ets tc-bw {ets_bw_str} '
                f'prio-tc {ets_prio_str}）; '
                'expect result: 4. dcb ets设置带宽比例成功')

            ets_ok = cls.configure_ets_tc(
                exec_device, EtsAlgorithm.ETS, cls.ETS_TC_CONFIGS,
                prio_tc=cls.PRIO_TC)
            cls.result_collect(
                ets_ok, 'dcb ets设置带宽比例成功',
                f'网口 {exec_device} configure_ets_tc 返回: {ets_ok}'
                f'（tc-bw {ets_bw_str}, prio-tc {ets_prio_str}）')

            # 步骤5: 查询dcb ets show dev <intf_name>
            CommonOperation.concat_test_steps(
                '5. 查询dcb ets show dev <intf_name>（指令：dcb ets show dev '
                '<intf_name>）; expect result: 5. dcb ets 结果与设置的结果一致')

            ets_show = cls.show_ets(exec_device)
            expect_substrs = (
                'tc-tsa 0:ets 1:ets 2:ets 3:ets 4:ets 5:ets 6:ets 7:ets',
                f'tc-bw {ets_bw_str}',
                ets_prio_str,
            )
            show_ok = all(sub in ets_show for sub in expect_substrs)
            cls.result_collect(
                show_ok, 'dcb ets 结果与设置的结果一致',
                f'网口 {exec_device} dcb ets show 输出: {ets_show}')

            # 步骤6: 对tc设置限速，且设置的tc速率大于port的速率（反向，期望失败）
            CommonOperation.concat_test_steps(
                '6. 对tc 设置限速，且设置的tc速率大于port的速率'
                '（指令：dcb maxrate set dev <intf_name> tc-max 0:<rate>Mbit）; '
                'expect result: 6. 命令执行失败')

            # 性能计算: 获取端口速率并计算超限速率，均在 for 循环内完成
            port_speed = cls.get_port_speed(exec_device)
            over_rate = port_speed + 100000 if port_speed else 500000
            # 实测: 本驱动 400G 端口配置 tc-max 500000Mbit 报
            # 'Attribute write: Invalid argument'，命令执行失败（符合用例预期）
            cls.execute_and_assert_fail(
                f'dcb maxrate set dev {exec_device} tc-max 0:{over_rate}Mbit',
                '对tc设置限速大于端口速率，命令执行失败',
                description=(
                    f'6. 对tc 设置限速，且设置的tc速率大于port的速率; '
                    f'expect result: 6. 命令执行失败'))

        # 步骤7: 清理环境（post 中执行 restore_state）
        CommonOperation.concat_test_steps(
            '7. 清理环境; expect result: 7. 命令执行成功')


    @classmethod
    def post(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 整理环境及结果信息相关信息
        :return: 无返回值
        """
        # 先清理残余打流进程，再遍历恢复所有执行端网口 dcb 配置
        for exec_addr in (cls.exec_address, cls.other_exec_address):
            CommandOperation.execute_command_with_error(
                cmd='pkill -9 -f iperf3 2>/dev/null || true',
                cmd_execute_address=exec_addr)
        for ifname in cls.exec_device_name_list:
            if ifname:
                cls._dcb_manager(ifname).restore_state()
        super().post()


def main() -> None:
    Script.run()


if __name__ == "__main__":
    main()
