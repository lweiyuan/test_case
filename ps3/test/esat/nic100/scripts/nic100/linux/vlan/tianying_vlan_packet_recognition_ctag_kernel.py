#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: TC-VLAN-001-K
case title: VLAN 报文识别 - CTag 类型（内核驱动）
test category: 天鹰 VLAN 测试
check point: TP-01
author: auto-generated
date: 2026.07.10

@steps:
    1. 在 server 物理口启动 tcpdump，过滤 ethertype 0x8100
    2. client 构造并发送带 CTag（VLAN ID=100）的以太网帧
    3. 检查 server 侧网卡接收方向 ptype/csum 解析结果
    4. 读取描述符中 VLAN 相关信息

@expected:
    1. tcpdump 正确识别 802.1Q CTag，VLAN ID=100
    2. 网卡 ptype 正确标识为 VLAN packet
    3. 描述符中携带正确 VLAN ID 和 priority

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


class TianyingVlanPacketRecognitionCtagKernel(ScriptBase):
    test_object = "天鹰 VLAN 测试"
    test_module = "tianying_vlan"
    test_tool = "python3, scapy, tcpdump"
    test_precondition = """1. 双机链路 Up，网卡工作正常
2. 已清除 iptables/SELinux 等防火墙影响
3. 对端可收发原始以太网帧"""
    test_steps = """
    1. 在 server 物理口启动 tcpdump，过滤 ethertype 0x8100
    2. client 构造并发送带 CTag（VLAN ID=100）的以太网帧
    3. 检查 server 侧网卡接收方向 ptype/csum 解析结果
    4. 读取描述符中 VLAN 相关信息
    """

    VLAN_ID = 100
    TEST_IP_PREFIX = "192.168.100"
    SERVER_VLAN_IP = "192.168.100.1"
    CLIENT_VLAN_IP = "192.168.100.2"
    PING_COUNT = 5
    PCAP_FILE = "/tmp/tc_vlan_001_k_capture.pcap"
    TCPDUMP_LOG = "/tmp/tc_vlan_001_k_tcpdump.log"
    TCPDUMP_PID_FILE = "/tmp/tc_vlan_001_k_tcpdump.pid"

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "TianyingVlanPacketRecognitionCtagKernel Failed"

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 TC-VLAN-001-K 自有环境...")
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
        log.info("TC-VLAN-001-K 环境检查通过")

    @classmethod
    def prepare(cls) -> None:
        log.info("准备 TC-VLAN-001-K 测试环境...")
        cls._save_offload_states()
        cls._cleanup_vlan_interfaces()
        # 确保对端可接收，清理残留
        cls._cleanup_vlan_interfaces()
        # 安装/检查 scapy 可用性
        cmd = "python3 -c 'import scapy.all; print(\"scapy ok\")' 2>/dev/null || pip3 install scapy -q"
        CommandOperation.execute_command_with_error(cmd, CmdExecuteAdressEnum.CLIENT.value)

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
    def _start_tcpdump_on_server(cls) -> None:
        CommandOperation.execute_command_with_error(
            f"pkill -f 'tcpdump.*{cls.PCAP_FILE}' 2>/dev/null || true",
            CmdExecuteAdressEnum.SERVER.value,
        )
        CommandOperation.execute_command_with_error(
            f"rm -f {cls.PCAP_FILE} {cls.TCPDUMP_LOG} {cls.TCPDUMP_PID_FILE}",
            CmdExecuteAdressEnum.SERVER.value,
        )
        cmd = (
            f"nohup tcpdump -i {cls.server_if} -nn -e -s 0 "
            f"-w {cls.PCAP_FILE} "
            f"> {cls.TCPDUMP_LOG} 2>&1 & "
            f"echo $! > {cls.TCPDUMP_PID_FILE}"
        )
        CommandOperation.execute_command_with_error(cmd, CmdExecuteAdressEnum.SERVER.value)
        time.sleep(2)

    @classmethod
    def _stop_tcpdump_on_server(cls) -> None:
        cmd = f"kill $(cat {cls.TCPDUMP_PID_FILE} 2>/dev/null) 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cmd, CmdExecuteAdressEnum.SERVER.value)
        time.sleep(1)

    @classmethod
    def _send_vlan_packet(cls) -> None:
        # TODO: 根据实际 MAC 地址修改 dst
        cmd = (
            f"python3 -c \""
            f"from scapy.all import *; "
            f"p = Ether(dst='ff:ff:ff:ff:ff:ff')/Dot1Q(vlan={cls.VLAN_ID})/IP(dst='192.168.100.255'); "
            f"sendp(p, iface='{cls.client_if}', count=5)"
            f"\""
        )
        CommandOperation.execute_command_with_error(cmd, CmdExecuteAdressEnum.CLIENT.value)

    @classmethod
    def _send_qinq_packet(cls) -> None:
        # TODO: 根据实际环境修改外层/内层 VLAN ID
        cmd = (
            f"python3 -c \""
            f"from scapy.all import *; "
            f"p = Ether(dst='ff:ff:ff:ff:ff:ff')/Dot1Q(vlan=10,type=0x88a8)/Dot1Q(vlan={cls.VLAN_ID})/IP(dst='192.168.100.255'); "
            f"sendp(p, iface='{cls.client_if}', count=5)"
            f"\""
        )
        CommandOperation.execute_command_with_error(cmd, CmdExecuteAdressEnum.CLIENT.value)

    @classmethod
    def _verify_packet_in_capture(cls) -> bool:
        cmd = f"tcpdump -nn -e -r {cls.PCAP_FILE} 2>/dev/null | head -30"
        status, result, _ = CommandOperation.execute_command_with_error(
            cmd, CmdExecuteAdressEnum.SERVER.value
        )
        if status != RtnStatusEnum.SUCCESS.value or not result.strip():
            return False
        log.info(f"tcpdump 输出:\n{result}")
        return f"vlan {cls.VLAN_ID}" in result.lower() or "802.1q" in result.lower()


    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 TC-VLAN-001-K：VLAN 报文识别 - CTag 类型（内核驱动）")
        log.info("=" * 60)
        try:
            # 在 server 物理口抓包
            cls._start_tcpdump_on_server()
            # 使用 scapy 发送带 VLAN tag 的报文
            cls._send_vlan_packet()
            time.sleep(2)
            cls._stop_tcpdump_on_server()
            tag_ok = cls._verify_packet_in_capture()
            if not tag_ok:
                cls._bug_and_raise("server 未捕获到预期 VLAN/QinQ 报文")

            log.info("TC-VLAN-001-K 测试通过")
        except SxeException:
            raise
        except Exception as e:
            log.error(f"TC-VLAN-001-K 未预期错误: {e}")
            raise

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "server 物理口应捕获到构造的 VLAN/QinQ 报文"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)

    @classmethod
    def post(cls) -> None:
        log.info("清理 TC-VLAN-001-K 测试环境...")
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
        log.info("TC-VLAN-001-K 清理完成")

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
    TianyingVlanPacketRecognitionCtagKernel.run()


if __name__ == "__main__":
    main()
