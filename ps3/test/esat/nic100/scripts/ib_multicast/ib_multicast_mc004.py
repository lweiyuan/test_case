#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-4
case title: 加载opensm，配置IP（ipv6）进行多播测试（参考测试逻辑基本用例，实际测试参考测试逻辑基本用例）
test category: IB多播测试
check point: ipoib IPv6 多播基础功能正常
author: auto-generated
date: 2026.06.24
@steps:
    1. 在 ib0 上配置 IPv6 地址。
    2. 执行 ping6 -I ib0 ff02::1 给所有节点发送多播。
    3. 执行 perfquery -r 查看收发计数。

@expected:
    ping6 能收到回应，perfquery 显示发端有发包、收端有收包。

@changelog:
2026.06.24 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.3 内核态QP加入多播组、3.1.20.4 内核态QP退出多播组
- 使用项目技巧：缺陷自动记录、IB基础概念与设备检查、IB命令处理与回显解析、IB多播与iperf测试
"""

import os
import time
import re
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, BugTypeEnum, CmdExecuteAdressEnum
from scripts.script_libs.script_base import ScriptBase, SxeException


class IbMulticastMc004(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ip, ping6, perfquery, ibdev2netdev"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
已加载 ib_ipoib 驱动，opensm 已启动"""
    test_steps = """
    1. 在 ib0 上配置 IPv6 地址：ip -6 addr add 2001:db8::1/64 dev ib0。
    2. 在客户端执行 ping6 -I ib0 ff02::1 给所有节点发送多播。
    3. 在服务端和客户端分别执行 perfquery -C mlx5_0 -P 1 -r 查看收发计数。
    """

    # 服务端/客户端分别使用不同 IPv6 地址，避免同一子网冲突
    IPOIB_SERVER_IPV6_ADDR = "2001:db8::1/64"
    IPOIB_CLIENT_IPV6_ADDR = "2001:db8::2/64"
    MCAST_IPV6_ALL_NODES = "ff02::1"
    IPOIB_IFACE = "ib0"
    PING6_COUNT = 5
    PING6_TIMEOUT = 10
    PERFQUERY_TIMEOUT = 10
    # 多设备环境下必须指定 perfquery 目标 CA 与端口
    PERFQUERY_DEVICE = "mlx5_0"
    PERFQUERY_PORT = "1"

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc004 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-4 测试环境...")

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client"),
        ]:
            status, result, err = CommandOperation.execute_command_with_error("ibstat -l", exec_addr)
            if status != RtnStatusEnum.SUCCESS.value or not result.strip():
                log.error(f"{name} 端未找到 IB 设备")
                cls.own_environment_enabled = False
                return

            status, result, err = CommandOperation.execute_command_with_error(
                "lsmod | grep -w ib_ipoib", exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value or "ib_ipoib" not in result:
                log.error(f"{name} 端未加载 ib_ipoib 驱动")
                cls.own_environment_enabled = False
                return

        cls.own_environment_enabled = True
        log.info("环境检查通过：两端均存在 IB 设备且已加载 ib_ipoib")

    @classmethod
    def prepare(cls) -> None:
        log.info("准备 MC-4 测试环境...")
        cls.server_iface = cls._get_ipoib_iface(
            CmdExecuteAdressEnum.SERVER.value, "server"
        )
        cls.client_iface = cls._get_ipoib_iface(
            CmdExecuteAdressEnum.CLIENT.value, "client"
        )

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-4 测试：ipoib IPv6 多播")
        log.info("=" * 60)

        try:
            # 配置 IPv6 地址
            cls._configure_ipv6(CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface)
            cls._configure_ipv6(CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface)

            # 获取 perfquery 基线（先重置计数器）
            cls._reset_perfquery_counters(CmdExecuteAdressEnum.SERVER.value, "server")
            cls._reset_perfquery_counters(CmdExecuteAdressEnum.CLIENT.value, "client")

            # 客户端发送 IPv6 多播 ping
            cls._send_ping6_multicast(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface
            )

            # 检查服务端是否收到多播包
            cls._verify_perfquery_received(
                CmdExecuteAdressEnum.SERVER.value, "server"
            )

            log.info("=" * 60)
            log.info("测试执行成功 - MC-4 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-4 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-4 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-4 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-4 测试环境...")
        cls._remove_ipv6_config(CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface)
        cls._remove_ipv6_config(CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface)
        log.info("MC-4 清理完成")

    @classmethod
    def _get_ipoib_iface(cls, exec_addr: str, name: str) -> str:
        """通过 ibdev2netdev 获取 mlx5_0 对应的 ipoib 网口名"""
        log.info(f"获取 {name} 端 mlx5_0 对应的 ipoib 网口...")
        cmd = "ibdev2netdev"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端执行 ibdev2netdev 失败: {err}"
            cls.bug_expect = "ibdev2netdev 应成功执行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-4 {name} 端 ibdev2netdev 执行失败")

        pattern = re.compile(r"^mlx5_0\s+port\s+\d+\s+==>\s+(\S+)\s+\((\w+)\)")
        for line in result.splitlines():
            match = pattern.match(line.strip())
            if match:
                iface = match.group(1)
                if iface.startswith("ib"):
                    log.info(f"{name} 端 mlx5_0 对应 ipoib 网口: {iface}")
                    return iface
                cls.bug_result = (
                    f"{name} 端 mlx5_0 对应网口 {iface} 不是 ipoib 网口。输出:\n{result}"
                )
                cls.bug_expect = "mlx5_0 应对应 ib* 开头的 ipoib 网口"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-4 {name} 端未找到 ipoib 网口")

        cls.bug_result = f"{name} 端未找到 mlx5_0 对应的 ipoib 网口。输出:\n{result}"
        cls.bug_expect = "ibdev2netdev 输出中应包含 mlx5_0 到 ipoib 网口的映射"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(f"MC-4 {name} 端获取 ipoib 网口失败")

    @classmethod
    def _configure_ipv6(cls, exec_addr: str, name: str, iface: str) -> None:
        """配置 IPv6 地址"""
        log.info(f"在 {name} 端 {iface} 上配置 IPv6 地址...")
        ipv6_addr = (
            cls.IPOIB_SERVER_IPV6_ADDR if name == "server" else cls.IPOIB_CLIENT_IPV6_ADDR
        )
        cmds = [
            f"ip -6 addr flush dev {iface}",
            f"ip -6 addr add {ipv6_addr} dev {iface}",
            f"ip link set {iface} up",
        ]
        for cmd in cmds:
            status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端执行命令失败: {cmd}\n错误: {err}"
                cls.bug_expect = "ip -6 addr 命令应成功配置 ipoib 网口"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-4 {name} 端配置 IPv6 地址失败")
        log.info(f"{name} 端 {iface} IPv6 配置完成")

    @classmethod
    def _reset_perfquery_counters(cls, exec_addr: str, name: str) -> None:
        """执行 perfquery -r 重置并读取计数器（多设备环境指定 CA 与端口）"""
        log.info(f"在 {name} 端重置并读取 perfquery 计数器...")
        cmd = f"perfquery -C {cls.PERFQUERY_DEVICE} -P {cls.PERFQUERY_PORT} -r"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端执行 perfquery -r 失败: {err}"
            cls.bug_expect = "perfquery -C <ca> -P <port> -r 应成功执行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-4 {name} 端 perfquery -r 执行失败")
        log.info(f"{name} 端 perfquery -r 执行完成")

    @classmethod
    def _send_ping6_multicast(cls, exec_addr: str, name: str, iface: str) -> None:
        """执行 ping6 多播"""
        log.info(f"在 {name} 端执行 ping6 多播...")
        cmd = (
            f"ping6 -I {iface} -c {cls.PING6_COUNT} "
            f"{cls.MCAST_IPV6_ALL_NODES}"
        )
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端执行 ping6 多播失败: {err}\n输出: {result}"
            cls.bug_expect = "ping6 -I ib0 ff02::1 应收到回应"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-4 {name} 端 ping6 多播失败")

        # ping6 成功时应显示 "X received"
        if not re.search(r"\d+\s+received", result):
            cls.bug_result = f"{name} 端 ping6 未收到回应。输出:\n{result}"
            cls.bug_expect = "ping6 ff02::1 应收到来自其他节点的回应"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-4 {name} 端 ping6 多播无回应")

        log.info(f"{name} 端 ping6 多播结果:\n{result.strip()}")

    @classmethod
    def _verify_perfquery_received(cls, exec_addr: str, name: str) -> None:
        """检查 perfquery 显示有收包（多设备环境指定 CA 与端口）"""
        log.info(f"检查 {name} 端 perfquery 多播收包计数...")
        cmd = f"perfquery -C {cls.PERFQUERY_DEVICE} -P {cls.PERFQUERY_PORT}"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端执行 perfquery 失败: {err}"
            cls.bug_expect = "perfquery -C <ca> -P <port> 应成功执行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-4 {name} 端 perfquery 执行失败")

        # perfquery 输出通常包含 PortRcvData / RcvData 计数
        if not re.search(r"RcvData\s*[:\.]\s*\d+", result):
            cls.bug_result = (
                f"{name} 端 perfquery 输出中未找到 RcvData 计数。输出:\n{result}"
            )
            cls.bug_expect = "服务端 perfquery 应显示收到多播包（RcvData > 0）"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-4 {name} 端未检测到多播收包")

        log.info(f"{name} 端 perfquery 显示已收到多播包:\n{result.strip()}")

    @classmethod
    def _remove_ipv6_config(cls, exec_addr: str, name: str, iface: str) -> None:
        """删除 IPv6 地址"""
        log.info(f"清理 {name} 端 {iface} 的 IPv6 配置...")
        cmd = f"ip -6 addr flush dev {iface}"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 {iface} IPv6 配置已清理")

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-4 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc004.run()


if __name__ == '__main__':
    main()
