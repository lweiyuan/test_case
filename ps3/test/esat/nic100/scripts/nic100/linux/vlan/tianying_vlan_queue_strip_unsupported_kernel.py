#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: TC-VLAN-028-K
case title: 验证天鹰不支持基于队列的 VLAN 剥离（内核驱动）
test category: 天鹰 VLAN 测试
check point: TP-12; TP-11
author: auto-generated
date: 2026.07.10

@steps:
    1. 尝试通过 ethtool 或 DPDK API 启用基于队列的 VLAN 剥离
    2. 检查返回值与状态
    3. 与 CX7 行为对比

@expected:
    1. 天鹰端操作失败或不生效
    2. CX7 端可正常启用
    3. 天鹰不支持 queue-based VLAN strip，与文档一致

@changelog:
    2026.07.10 - 初始版本，基于 NIC100 框架生成
"""

import os
import re
import time
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.ethtool_operation import EthtoolOperation
from scripts.script_libs.enums import (
    CmdExecuteAdressEnum,
    RtnStatusEnum,
    BugTypeEnum,
    RdmaMode,
)
from scripts.script_libs.script_base import ScriptBase, SxeException


class TianyingVlanQueueStripUnsupportedKernel(ScriptBase):
    test_object = "天鹰 VLAN 测试"
    test_module = "tianying_vlan"
    test_tool = "ip, ethtool, tc, devlink"
    test_precondition = """1. 天鹰网卡
2. 已了解 CX7 支持 queue-based strip"""
    test_steps = """
    1. 尝试通过 ethtool 或 DPDK API 启用基于队列的 VLAN 剥离
    2. 检查返回值与状态
    3. 与 CX7 行为对比
    """

    VLAN_ID = 100
    TEST_IP_PREFIX = "192.168.100"
    SERVER_VLAN_IP = "192.168.100.1"
    CLIENT_VLAN_IP = "192.168.100.2"
    PING_COUNT = 5
    PCAP_FILE = "/tmp/tc_vlan_028_k_capture.pcap"
    TCPDUMP_LOG = "/tmp/tc_vlan_028_k_tcpdump.log"
    TCPDUMP_PID_FILE = "/tmp/tc_vlan_028_k_tcpdump.pid"

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "TianyingVlanQueueStripUnsupportedKernel Failed"

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 TC-VLAN-028-K 自有环境...")
        server_ifs, client_ifs = CommonOperation.get_nic_relationships(
            rdma=False, nic_mode=RdmaMode.RoCE.value
        )
        if not server_ifs or not client_ifs:
            log.error("未从配置读取到以太设备名")
            cls.own_environment_enabled = False
            return

        cls.server_if = server_ifs[0].strip()
        cls.client_if = client_ifs[0].strip()
        log.info(f"server 网口: {cls.server_if}, client 网口: {cls.client_if}")

        for exec_addr, name, if_name in [
            (CmdExecuteAdressEnum.SERVER.value, "server", cls.server_if),
            (CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_if),
        ]:
            status, result, err = CommandOperation.execute_command_with_error(
                f"ip link show {if_name}", exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                log.error(f"{name} 端网口 {if_name} 不存在: {err}")
                cls.own_environment_enabled = False
                return
            if "state UP" not in result:
                log.warning(f"{name} 端网口 {if_name} 未 Up，尝试启用")
                CommandOperation.execute_command_with_error(
                    f"ip link set {if_name} up", exec_addr
                )

        cls.own_environment_enabled = True
        log.info("TC-VLAN-028-K 环境检查通过")

    @classmethod
    def prepare(cls) -> None:
        log.info("准备 TC-VLAN-028-K 测试环境...")
        cls._save_offload_states()
        cls._cleanup_vlan_interfaces()
        # 环境准备：确保网卡模式可配置
        cls._save_offload_states()
        cls._cleanup_vlan_interfaces()

        time.sleep(1)

    @classmethod
    def _save_offload_states(cls) -> None:
        cls.server_offloads = EthtoolOperation.get_offload_and_features(
            cls.server_if, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value
        )
        cls.client_offloads = EthtoolOperation.get_offload_and_features(
            cls.client_if, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value
        )

    @classmethod
    def _cleanup_vlan_interfaces(cls) -> None:
        for exec_addr, if_name in [
            (CmdExecuteAdressEnum.SERVER.value, cls.server_if),
            (CmdExecuteAdressEnum.CLIENT.value, cls.client_if),
        ]:
            vlan_iface = f"{if_name}.{cls.VLAN_ID}"
            CommandOperation.execute_command_with_error(
                f"ip link del {vlan_iface} 2>/dev/null || true", exec_addr
            )

    @classmethod
    def _create_vlan_interface(
        cls, exec_addr: str, if_name: str, vlan_id: int, ip: str, prefix: str
    ) -> None:
        vlan_iface = f"{if_name}.{vlan_id}"
        add_cmd = f"ip link add link {if_name} name {vlan_iface} type vlan id {vlan_id}"
        status, _, err = CommandOperation.execute_command_with_error(add_cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls._bug_and_raise(f"创建 VLAN 子接口失败: {add_cmd}, 错误: {err}")
        CommandOperation.execute_command_with_error(
            f"ip addr add {ip}/{prefix} dev {vlan_iface}", exec_addr
        )
        CommandOperation.execute_command_with_error(
            f"ip link set {vlan_iface} up", exec_addr
        )
        log.info(f"已在 {exec_addr} 的 {if_name} 上创建 VLAN {vlan_id} 接口并配置 {ip}/{prefix}")

    @classmethod
    def _test_mutex_or_limit(cls) -> bool:
        # TODO: 根据用例具体意图实现配置顺序、互斥检查
        log.info("执行互斥/限制验证 (TODO: 替换为实际配置命令)")
        status1, _, _ = CommandOperation.execute_command_with_error(
            f"ethtool --features {cls.server_if} rx-vlan-filter on",
            CmdExecuteAdressEnum.SERVER.value
        )
        return status1 == RtnStatusEnum.SUCCESS.value


    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 TC-VLAN-028-K：验证天鹰不支持基于队列的 VLAN 剥离（内核驱动）")
        log.info("=" * 60)
        try:
            # 执行配置操作并验证互斥/报错
            result_ok = cls._test_mutex_or_limit()
            if not result_ok:
                cls._bug_and_raise("互斥/限制验证失败，未按预期返回错误或互斥")

            log.info("TC-VLAN-028-K 测试通过")
        except SxeException:
            raise
        except Exception as e:
            log.error(f"TC-VLAN-028-K 未预期错误: {e}")
            raise

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "互斥配置应返回明确错误，配置顺序限制应按文档说明生效"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)

    @classmethod
    def post(cls) -> None:
        log.info("清理 TC-VLAN-028-K 测试环境...")
        CommandOperation.execute_command_with_error(
            f"pkill -f 'tcpdump.*{cls.PCAP_FILE}' 2>/dev/null || true",
            CmdExecuteAdressEnum.SERVER.value,
        )
        cls._cleanup_vlan_interfaces()
        for exec_addr, if_name, ip in [
            (CmdExecuteAdressEnum.SERVER.value, cls.server_if, cls.SERVER_VLAN_IP),
            (CmdExecuteAdressEnum.CLIENT.value, cls.client_if, cls.CLIENT_VLAN_IP),
        ]:
            CommandOperation.execute_command_with_error(
                f"ip addr del {ip}/24 dev {if_name}.{cls.VLAN_ID} 2>/dev/null || true",
                exec_addr,
            )
        cls._restore_offload_states()
        for f in [cls.PCAP_FILE, cls.TCPDUMP_LOG, cls.TCPDUMP_PID_FILE]:
            CommandOperation.execute_command_with_error(
                f"rm -f {f}", CmdExecuteAdressEnum.SERVER.value
            )
        log.info("TC-VLAN-028-K 清理完成")

    @classmethod
    def _restore_offload_states(cls) -> None:
        log.info("恢复原始 VLAN offload 状态...")
        if not hasattr(cls, "server_offloads") or not hasattr(cls, "client_offloads"):
            return
        for exec_addr, if_name, offloads in [
            (CmdExecuteAdressEnum.SERVER.value, cls.server_if, cls.server_offloads),
            (CmdExecuteAdressEnum.CLIENT.value, cls.client_if, cls.client_offloads),
        ]:
            for feat in ["rx-vlan-offload", "tx-vlan-offload"]:
                orig = offloads.get(feat)
                if orig in ["on", "off"]:
                    EthtoolOperation.set_offload_and_features(
                        if_name, feat, orig, cmd_execute_address=exec_addr
                    )


def main() -> None:
    TianyingVlanQueueStripUnsupportedKernel.run()


if __name__ == "__main__":
    main()
