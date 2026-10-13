#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-17
case title: 2v2多对多多播测试+ibdump查看镜像包
test category: IB多播测试
check point: 多对多多播中 ibdump 只在一个节点捕获到镜像包
author: auto-generated
date: 2026.06.24
@steps:
    1. 服务器 A/B 均启动 iperf 多播服务端。
    2. 客户端向多播组发送流量。
    3. 两个节点都启动 ibdump。
    4. 检查 ibdump 捕获结果。

@expected:
    只有一个节点回收到镜像包。

@changelog:
2026.06.24 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.3 内核态QP加入多播组、3.1.20.4 内核态QP退出多播组
- 使用项目技巧：缺陷自动记录、IB基础概念与设备检查、IB命令处理与回显解析、IB多播与iperf测试
- 备注：CX7 不支持 ibdump；环境不满足时跳过
2026.06.26 - 修正：识别所有 pport 并为每个 pport 启动并检查 opensm；prepare/post 补充 super() 调用
"""

import os
import time
import re
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, BugTypeEnum, CmdExecuteAdressEnum
from scripts.script_libs.script_base import ScriptBase, SxeException


class IbMulticastMc017(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ip, iperf, ibdump, ibdev2netdev"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
已加载 ib_ipoib 驱动，opensm 已启动
已安装 iperf 2.x、ibdump"""
    test_steps = """
    1. 服务器 A/B 均启动 iperf 多播服务端（绑定 224.0.0.20）。
    2. 客户端启动 iperf 多播客户端向 224.0.0.20 发送流量。
    3. 两个节点均启动 ibdump 捕获多播镜像包。
    4. 检查 ibdump 结果，确认只有一个节点回收到镜像包。
    """

    MCAST_GROUP = "224.0.0.20"
    IPOIB_SERVER_A_IP = "192.168.100.1/24"
    IPOIB_SERVER_B_IP = "192.168.100.2/24"
    IPOIB_CLIENT_SRC = "192.168.100.3"
    IPOIB_IFACE = "ib0"
    IPERF_DURATION = 10
    IPERF_STARTUP_WAIT = 2

    # 双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport
    PPORT_COUNT = 2
    OPENSM_STARTUP_WAIT = 10

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc017 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-17 测试环境...")

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client"),
        ]:
            status, result, err = CommandOperation.execute_command_with_error("ibstat -l", exec_addr)
            if status != RtnStatusEnum.SUCCESS.value or not result.strip():
                log.error(f"{name} 端未找到 IB 设备")
                cls.own_environment_enabled = False
                return

            status, result, err = CommandOperation.execute_command_with_error("which iperf", exec_addr)
            if status != RtnStatusEnum.SUCCESS.value or not result.strip():
                log.error(f"{name} 端未找到 iperf")
                cls.own_environment_enabled = False
                return

            status, result, err = CommandOperation.execute_command_with_error("which ibdump", exec_addr)
            if status != RtnStatusEnum.SUCCESS.value or not result.strip():
                log.warning(f"{name} 端未找到 ibdump（CX7 不支持 ibdump）")
                cls.own_environment_enabled = False
                return

        cls.own_environment_enabled = True
        log.info("环境检查通过")

    @classmethod
    def prepare(cls) -> None:
        super().prepare()
        log.info("准备 MC-17 测试环境...")

        # 识别两端 pport 并确保每个 pport 均启动 opensm
        cls.server_pf_list = cls._get_pf_list(CmdExecuteAdressEnum.SERVER.value, "server")
        cls.client_pf_list = cls._get_pf_list(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls.server_pport_list = cls._get_pport_list(cls.server_pf_list)
        cls.client_pport_list = cls._get_pport_list(cls.client_pf_list)

        for exec_addr, name, pport_list_attr in [
            (CmdExecuteAdressEnum.SERVER.value, "server", "server_pport_list"),
            (CmdExecuteAdressEnum.CLIENT.value, "client", "client_pport_list"),
        ]:
            pport_list = getattr(cls, pport_list_attr)
            cls._stop_opensm(exec_addr, name)
            cls._start_opensm_for_pports(exec_addr, name, pport_list)
            cls._verify_opensm_for_pports(exec_addr, name, pport_list)
            cls._verify_all_pf_active(exec_addr, name, pport_list)

        cls.server_iface = cls._get_ipoib_iface(
            CmdExecuteAdressEnum.SERVER.value, "server"
        )
        cls.client_iface = cls._get_ipoib_iface(
            CmdExecuteAdressEnum.CLIENT.value, "client"
        )

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-17 测试：2v2 多对多 + ibdump")
        log.info("=" * 60)

        try:
            # 配置 IPv4 地址和多播路由
            cls._configure_ipv4(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface,
                cls.IPOIB_SERVER_A_IP
            )
            cls._configure_ipv4(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface,
                cls.IPOIB_SERVER_B_IP
            )

            # 启动两端 iperf 服务端
            cls.server_log_a = f"/tmp/mc17_server_a_{cls.server_iface}.log"
            cls.server_log_b = f"/tmp/mc17_server_b_{cls.client_iface}.log"
            cls._start_iperf_server(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface, cls.server_log_a
            )
            cls._start_iperf_server(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface, cls.server_log_b
            )

            # 启动 ibdump（两端同时）
            cls.ibdump_log_a = f"/tmp/mc17_ibdump_a_{cls.server_iface}.log"
            cls.ibdump_log_b = f"/tmp/mc17_ibdump_b_{cls.client_iface}.log"
            cls._start_ibdump(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface, cls.ibdump_log_a
            )
            cls._start_ibdump(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface, cls.ibdump_log_b
            )

            # 启动客户端
            cls.client_log = f"/tmp/mc17_client_{cls.client_iface}.log"
            cls._run_iperf_client(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface,
                cls.IPOIB_CLIENT_SRC, cls.client_log
            )

            # 停止 ibdump 并检查结果
            time.sleep(2)
            cls._stop_ibdump(CmdExecuteAdressEnum.SERVER.value, "server")
            cls._stop_ibdump(CmdExecuteAdressEnum.CLIENT.value, "client")

            count_a = cls._count_ibdump_packets(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.ibdump_log_a
            )
            count_b = cls._count_ibdump_packets(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.ibdump_log_b
            )

            log.info(f"ibdump 捕获包数 - 节点A: {count_a}, 节点B: {count_b}")
            if count_a > 0 and count_b > 0:
                cls.bug_result = f"两个节点均捕获到镜像包（节点A: {count_a}, 节点B: {count_b}），预期只有一个节点应捕获"
                cls.bug_expect = "ibdump 应只在一个节点回收到镜像包"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug("MC-17 ibdump 镜像包节点数量异常")

            if count_a == 0 and count_b == 0:
                cls.bug_result = "两个节点均未捕获到镜像包"
                cls.bug_expect = "ibdump 应至少在一个节点回收到镜像包"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug("MC-17 ibdump 未捕获到镜像包")

            log.info("=" * 60)
            log.info("测试执行成功 - MC-17 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-17 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-17 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-17 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-17 测试环境...")
        cls._stop_iperf(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_iperf(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._stop_ibdump(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_ibdump(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._remove_ipv4_config(CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface)
        cls._remove_ipv4_config(CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface)
        for log_path in [
            cls.server_log_a, cls.server_log_b, cls.client_log,
            cls.ibdump_log_a, cls.ibdump_log_b
        ]:
            cls._remove_log_files(CmdExecuteAdressEnum.SERVER.value, "server", log_path)
            cls._remove_log_files(CmdExecuteAdressEnum.CLIENT.value, "client", log_path)
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        log.info("MC-17 清理完成")
        super().post()

    @classmethod
    def _get_ipoib_iface(cls, exec_addr: str, name: str) -> str:
        log.info(f"获取 {name} 端 ipoib 网口...")
        cmd = "ibdev2netdev"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端执行 ibdev2netdev 失败: {err}"
            cls.bug_expect = "ibdev2netdev 应成功执行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-17 {name} 端 ibdev2netdev 执行失败")

        # 优先从该端 pport 列表中查找 ib* 网口
        pport_list = getattr(cls, f"{name}_pport_list", [])
        pf_list = getattr(cls, f"{name}_pf_list", [])
        search_devices = pport_list if pport_list else pf_list

        for device in search_devices:
            pattern = re.compile(rf"^{re.escape(device)}\s+port\s+\d+\s+==>\s+(\S+)")
            for line in result.splitlines():
                match = pattern.match(line.strip())
                if match:
                    iface = match.group(1)
                    if iface.startswith("ib"):
                        log.info(f"{name} 端 {device} 对应 ipoib 网口: {iface}")
                        return iface

        # fallback：返回第一个 ib* 接口
        fallback = re.search(r"==>\s+(ib\S+)", result)
        if fallback:
            iface = fallback.group(1)
            log.warning(f"{name} 端未从 pport 找到 ipoib 网口，fallback 为 {iface}")
            return iface

        cls.bug_result = f"{name} 端未找到 ipoib 网口。输出:\n{result}"
        cls.bug_expect = "ibdev2netdev 输出中应包含 ib* 开头的 ipoib 网口"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(f"MC-17 {name} 端获取 ipoib 网口失败")

    @classmethod
    def _configure_ipv4(cls, exec_addr: str, name: str, iface: str, ipv4_addr: str) -> None:
        log.info(f"在 {name} 端 {iface} 上配置 IPv4 地址和多播路由...")
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
                cls.create_bug(f"MC-17 {name} 端配置 IPv4/多播路由失败")
        log.info(f"{name} 端 {iface} IPv4 和多播路由配置完成")

    @classmethod
    def _start_iperf_server(cls, exec_addr: str, name: str, iface: str, log_path: str) -> None:
        log.info(f"在 {name} 端启动 iperf 多播服务端...")
        cls._stop_iperf(exec_addr, name)
        cmd = (
            f"nohup iperf -s -u -B {cls.MCAST_GROUP} -i 1 "
            f">\"{log_path}\" 2>&1 &"
        )
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        time.sleep(cls.IPERF_STARTUP_WAIT)

    @classmethod
    def _start_ibdump(cls, exec_addr: str, name: str, iface: str, log_path: str) -> None:
        log.info(f"在 {name} 端启动 ibdump...")
        cmd = f"nohup ibdump -i {iface} >\"{log_path}\" 2>&1 &"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        time.sleep(1)

    @classmethod
    def _stop_ibdump(cls, exec_addr: str, name: str) -> None:
        cmd = "pkill -9 -x ibdump 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 ibdump 进程已清理")

    @classmethod
    def _count_ibdump_packets(cls, exec_addr: str, name: str, log_path: str) -> int:
        cmd = f"cat \"{log_path}\" | wc -l"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            return 0
        try:
            return int(result.strip())
        except ValueError:
            return 0

    @classmethod
    def _run_iperf_client(cls, exec_addr: str, name: str, iface: str, src_ip: str, log_path: str) -> None:
        log.info(f"在 {name} 端启动 iperf 多播客户端...")
        cmd = (
            f"iperf -c {cls.MCAST_GROUP} -u -l 128 -i 1 "
            f"-t {cls.IPERF_DURATION} -B {src_ip} "
            f">\"{log_path}\" 2>&1"
        )
        CommandOperation.execute_command_with_error(cmd, exec_addr)

    @classmethod
    def _stop_iperf(cls, exec_addr: str, name: str) -> None:
        cmd = "pkill -9 -x iperf 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cmd, exec_addr)

    @classmethod
    def _remove_ipv4_config(cls, exec_addr: str, name: str, iface: str) -> None:
        cmds = [
            f"ip route del {cls.MCAST_GROUP} dev {iface} 2>/dev/null || true",
            f"ip addr flush dev {iface}",
        ]
        for cmd in cmds:
            CommandOperation.execute_command_with_error(cmd, exec_addr)

    @classmethod
    def _remove_log_files(cls, exec_addr: str, name: str, log_path: str) -> None:
        cmd = f"rm -f \"{log_path}\""
        CommandOperation.execute_command_with_error(cmd, exec_addr)

    @classmethod
    def _get_pf_list(cls, exec_addr: str, name: str) -> list:
        """获取所有 IB PF 名称列表"""
        log.info(f"获取 {name} 端 PF 列表...")
        cmd = "ibstat -l"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端执行 ibstat -l 失败: {err}"
            cls.bug_expect = "ibstat -l 应成功执行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-17 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-17 {name} 端 PF 列表为空")

        return pf_list

    @classmethod
    def _get_pport_list(cls, pf_list: list) -> list:
        """识别所有 pport

        双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport。
        通过 PPORT_COUNT 控制，默认取前 2 个（不足则取全部）。
        """
        count = min(cls.PPORT_COUNT, len(pf_list))
        pport_list = pf_list[:count]
        log.info(f"识别到的 pport 列表: {pport_list}")
        return pport_list

    @classmethod
    def _start_opensm_for_pports(cls, exec_addr: str, name: str, pport_list: list) -> None:
        """为每个 pport 启动 opensm"""
        log.info(f"在 {name} 端为所有 pport 启动 opensm...")

        for idx, pport in enumerate(pport_list):
            guid = cls._get_device_guid(exec_addr, name, pport)
            log.info(f"为 pport {pport} 启动 opensm，GUID: {guid}")
            opensm_cmd = (
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_mc17_{idx}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端为 pport {pport} 启动 opensm 失败: {err}"
                cls.bug_expect = "opensm 应能在每个 pport 上成功启动"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-17 {name} 端 pport {pport} opensm 启动失败")
            time.sleep(3)

        # 等待 opensm 完成子网扫描
        time.sleep(cls.OPENSM_STARTUP_WAIT)

    @classmethod
    def _verify_opensm_for_pports(cls, exec_addr: str, name: str, pport_list: list) -> None:
        """验证每个 pport 上的 opensm 进程正在运行"""
        log.info(f"验证 {name} 端所有 pport 的 opensm 进程...")

        if not cls._is_opensm_running(exec_addr):
            cls.bug_result = f"{name} 端未检测到任何 opensm 进程"
            cls.bug_expect = "每个 pport 上应运行一个 opensm 实例"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-17 {name} 端 opensm 未运行")

        # 验证 opensm 进程数量不少于 pport 数量
        status, result, err = CommandOperation.execute_command_with_error(
            "pgrep -x opensm", exec_addr
        )
        running_count = len([line.strip() for line in result.splitlines() if line.strip()])
        if running_count < len(pport_list):
            cls.bug_result = (
                f"{name} 端 opensm 进程数量不足，实际 {running_count} 个，"
                f"期望至少 {len(pport_list)} 个（每个 pport 一个）"
            )
            cls.bug_expect = "每个 pport 上应运行一个 opensm 实例"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-17 {name} 端 opensm 进程数量不足")

        log.info(f"{name} 端 opensm 进程数量: {running_count}，pport 数量: {len(pport_list)}")

    @classmethod
    def _verify_all_pf_active(cls, exec_addr: str, name: str, pport_list: list) -> None:
        """验证所有 pport 均处于 Active 状态"""
        log.info(f"验证 {name} 端所有 pport 状态...")
        for pf in pport_list:
            status, result, err = CommandOperation.execute_command_with_error(
                f"ibstat {pf}", exec_addr
            )
            if (
                status != RtnStatusEnum.SUCCESS.value
                or "State: Active" not in result
                or "Physical state: LinkUp" not in result
            ):
                cls.bug_result = f"{name} 端 PF {pf} 未处于 Active/LinkUp 状态"
                cls.bug_expect = "opensm 启动后所有 PF 应处于 Active/LinkUp 状态"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-17 {name} 端 PF {pf} 未 Active")
        log.info(f"{name} 端所有 pport 均处于 Active 状态")

    @classmethod
    def _get_device_guid(cls, exec_addr: str, name: str, device: str) -> str:
        """获取指定 IB 设备的 Node GUID"""
        cmd = f"ibstat {device} | grep 'Node GUID'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端获取 {device} Node GUID 失败: {err}"
            cls.bug_expect = "ibstat 应能返回 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-17 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-17 {name} 端解析 {device} GUID 失败")

        return match.group(0)

    @classmethod
    def _is_opensm_running(cls, exec_addr: str) -> bool:
        """检查 opensm 进程是否正在运行"""
        status, _, _ = CommandOperation.execute_command_with_error(
            "pgrep -x opensm >/dev/null 2>&1", exec_addr
        )
        return status == RtnStatusEnum.SUCCESS.value

    @classmethod
    def _stop_opensm(cls, exec_addr: str, name: str) -> None:
        """停止 opensm"""
        cmd = "pkill -9 -x opensm 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        time.sleep(3)
        log.info(f"{name} 端 opensm 已停止")

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-17 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc017.run()


if __name__ == '__main__':
    main()
