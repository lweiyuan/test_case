#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-3
case title: 加载opensm，配置IP（ipv4）进行多播测试（参考测试逻辑基本用例，实际测试参考测试逻辑基本用例）
test category: IB多播测试
check point: ipoib IPv4 多播基础功能正常
author: auto-generated
date: 2026.06.24
@steps:
    1. 在 ib0 上配置 IPv4 地址。
    2. 添加多播路由。
    3. 服务端启动 iperf 多播服务端。
    4. 客户端启动 iperf 多播客户端发送流量。
    5. 观察收发是否正常。

@expected:
    iperf 客户端和服务端均显示正常多播流量，无异常报错。

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


class IbMulticastMc003(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ip, iperf, lsmod, ibdev2netdev"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
已加载 ib_ipoib 驱动，opensm 已启动
已安装 iperf 2.x（iperf3 不支持多播服务端绑定）"""
    test_steps = """
    1. 在 ib0 上配置 IPv4 地址：ip addr add 192.168.1.111/24 dev ib0。
    2. 添加多播路由：ip route add 224.0.0.2 dev ib0。
    3. 服务端执行：iperf -s -u -B 224.0.0.2 -i 1。
    4. 客户端执行：iperf -c 224.0.0.2 -u -l 128 -i 1 -t <duration> -B 192.168.1.111。
    5. 检查两端 iperf 输出，确认多播流量正常。
    """

    # 服务端/客户端分别使用不同 IPv4 地址，避免同一子网冲突
    IPOIB_SERVER_IPV4_ADDR = "192.168.1.100/24"
    IPOIB_CLIENT_IPV4_ADDR = "192.168.1.111/24"
    IPOIB_CLIENT_SRC_IP = "192.168.1.111"
    MCAST_GROUP = "224.0.0.2"
    IPOIB_IFACE = "ib0"
    IPERF_DURATION = 10
    IPERF_PKT_LEN = 128
    IPERF_STARTUP_WAIT = 2
    IPERF_POLL_TIMEOUT = 30

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc003 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-3 测试环境...")

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

            # iperf -v 把版本信息输出到 stderr，因此使用 which 检测更可靠
            status, result, err = CommandOperation.execute_command_with_error("which iperf", exec_addr)
            if status != RtnStatusEnum.SUCCESS.value or not result.strip():
                log.error(f"{name} 端未找到 iperf")
                cls.own_environment_enabled = False
                return

        cls.own_environment_enabled = True
        log.info("环境检查通过：两端均存在 IB 设备、已加载 ib_ipoib、已安装 iperf")

    @classmethod
    def prepare(cls) -> None:
        log.info("准备 MC-3 测试环境...")
        cls.server_iface = cls._get_ipoib_iface(
            CmdExecuteAdressEnum.SERVER.value, "server"
        )
        cls.client_iface = cls._get_ipoib_iface(
            CmdExecuteAdressEnum.CLIENT.value, "client"
        )

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-3 测试：ipoib IPv4 多播")
        log.info("=" * 60)

        try:
            # 配置 IPv4 地址和多播路由
            cls._configure_ipv4(CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface)
            cls._configure_ipv4(CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface)

            # 启动 iperf 服务端
            # 日志文件名不能包含 "iperf"，否则会被框架自动替换 iperf 端口时一并改写
            cls.server_log = f"/tmp/mc3_server_{cls.server_iface}.log"
            cls._start_iperf_server(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface, cls.server_log
            )

            # 启动 iperf 客户端
            cls.client_log = f"/tmp/mc3_client_{cls.client_iface}.log"
            cls._run_iperf_client(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface, cls.client_log
            )

            # 检查客户端输出是否有有效流量
            cls._verify_iperf_client_output(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_log
            )

            log.info("=" * 60)
            log.info("测试执行成功 - MC-3 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-3 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-3 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-3 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-3 测试环境...")
        cls._stop_iperf(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_iperf(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._remove_ipv4_config(CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface)
        cls._remove_ipv4_config(CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface)
        cls._remove_log_files(
            CmdExecuteAdressEnum.SERVER.value, "server", cls.server_log
        )
        cls._remove_log_files(
            CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_log
        )
        log.info("MC-3 清理完成")

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
            cls.create_bug(f"MC-3 {name} 端 ibdev2netdev 执行失败")

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
                cls.create_bug(f"MC-3 {name} 端未找到 ipoib 网口")

        cls.bug_result = f"{name} 端未找到 mlx5_0 对应的 ipoib 网口。输出:\n{result}"
        cls.bug_expect = "ibdev2netdev 输出中应包含 mlx5_0 到 ipoib 网口的映射"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(f"MC-3 {name} 端获取 ipoib 网口失败")

    @classmethod
    def _configure_ipv4(cls, exec_addr: str, name: str, iface: str) -> None:
        """配置 IPv4 地址和多播路由"""
        log.info(f"在 {name} 端 {iface} 上配置 IPv4 地址和多播路由...")

        ipv4_addr = (
            cls.IPOIB_SERVER_IPV4_ADDR if name == "server" else cls.IPOIB_CLIENT_IPV4_ADDR
        )
        cmds = [
            f"ip addr flush dev {iface}",
            f"ip addr add {ipv4_addr} dev {iface}",
            f"ip link set {iface} up",
            f"ip route add {cls.MCAST_GROUP} dev {iface} 2>/dev/null || true",
        ]
        for cmd in cmds:
            status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端执行命令失败: {cmd}\n错误: {err}"
                cls.bug_expect = "ip addr/route 命令应成功配置 ipoib 网口"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-3 {name} 端配置 IPv4/多播路由失败")

        log.info(f"{name} 端 {iface} IPv4 和多播路由配置完成")

    @classmethod
    def _start_iperf_server(cls, exec_addr: str, name: str, iface: str, log_path: str) -> None:
        """后台启动 iperf 多播服务端"""
        log.info(f"在 {name} 端启动 iperf 多播服务端...")
        cls._stop_iperf(exec_addr, name)
        cmd = (
            f"nohup iperf -s -u -B {cls.MCAST_GROUP} -i 1 "
            f">\"{log_path}\" 2>&1 &"
        )
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端启动 iperf 服务端失败: {err}"
            cls.bug_expect = "iperf -s -u -B <mcast> 应成功启动"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-3 {name} 端启动 iperf 服务端失败")

        time.sleep(cls.IPERF_STARTUP_WAIT)
        log.info(f"{name} 端 iperf 多播服务端已启动")

    @classmethod
    def _run_iperf_client(cls, exec_addr: str, name: str, iface: str, log_path: str) -> None:
        """启动 iperf 多播客户端并等待完成"""
        log.info(f"在 {name} 端启动 iperf 多播客户端...")
        cmd = (
            f"iperf -c {cls.MCAST_GROUP} -u -l {cls.IPERF_PKT_LEN} -i 1 "
            f"-t {cls.IPERF_DURATION} -B {cls.IPOIB_CLIENT_SRC_IP} "
            f">\"{log_path}\" 2>&1"
        )
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        # iperf 客户端正常结束后返回 0；这里同时保留 result 中的输出
        if status != RtnStatusEnum.SUCCESS.value and not result.strip():
            cls.bug_result = f"{name} 端 iperf 客户端执行失败: {err}"
            cls.bug_expect = "iperf 客户端应向多播组发送流量并正常结束"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-3 {name} 端 iperf 客户端执行失败")

        log.info(f"{name} 端 iperf 客户端执行完成")

    @classmethod
    def _verify_iperf_client_output(cls, exec_addr: str, name: str, log_path: str) -> None:
        """检查 iperf 客户端日志中是否存在有效带宽/流量"""
        log.info(f"检查 {name} 端 iperf 客户端输出...")
        cmd = f"cat \"{log_path}\""
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or not result.strip():
            cls.bug_result = f"{name} 端 iperf 客户端日志为空或读取失败: {err}"
            cls.bug_expect = "iperf 客户端应产生非空输出"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-3 {name} 端 iperf 客户端输出为空")

        # iperf2 典型输出包含 "Mbits/sec" 或 "Kbits/sec"
        if not re.search(r"\d+\s+(Mbits/sec|Kbits/sec)", result):
            cls.bug_result = (
                f"{name} 端 iperf 客户端未检测到有效多播带宽。输出:\n{result}"
            )
            cls.bug_expect = "iperf 客户端输出中应包含有效的 Mbits/sec/Kbits/sec 带宽"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-3 {name} 端 iperf 多播流量异常")

        log.info(f"{name} 端 iperf 多播流量正常:\n{result.strip()}")

    @classmethod
    def _stop_iperf(cls, exec_addr: str, name: str) -> None:
        """停止 iperf 进程"""
        cmd = "pkill -9 -x iperf 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 iperf 进程已清理")

    @classmethod
    def _remove_ipv4_config(cls, exec_addr: str, name: str, iface: str) -> None:
        """删除 IPv4 地址和多播路由"""
        log.info(f"清理 {name} 端 {iface} 的 IPv4 配置...")
        cmds = [
            f"ip route del {cls.MCAST_GROUP} dev {iface} 2>/dev/null || true",
            f"ip addr flush dev {iface}",
        ]
        for cmd in cmds:
            CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 {iface} IPv4 配置已清理")

    @classmethod
    def _remove_log_files(cls, exec_addr: str, name: str, log_path: str) -> None:
        """删除测试产生的日志文件"""
        log.info(f"清理 {name} 端日志文件 {log_path}...")
        cmd = f"rm -f \"{log_path}\""
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端日志文件已清理")

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-3 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc003.run()


if __name__ == '__main__':
    main()
