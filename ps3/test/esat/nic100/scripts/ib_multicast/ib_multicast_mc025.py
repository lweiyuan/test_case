#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-25
case title: 多播业务、单播业务、CLI业务、SMA业务、PMA业务并发，业务成功
test category: IB多播测试
check point: 多播、单播、CLI、SMA、PMA 业务并发时均成功
author: auto-generated
date: 2026.06.25
@steps:
    1. 启动 ipoib 多播业务（参考 excel_dump.txt 第 20 行）。
    2. 启动 ib_send_bw -g 用户态多播业务。
    3. 启动 ib_read_bw 单播业务。
    4. 并发执行 CLI 业务（placeholder）。
    5. 并发执行 SMA 业务：smpquery -C mlx5_0 sl2vl 1 1。
    6. 并发执行 PMA 业务：perfquery -C mlx5_0。
    7. 检查各类业务是否均正常执行，无异常。

@expected:
    多播、单播、CLI、SMA、PMA 业务并发成功。

@changelog:
2026.06.25 - 根据 IB-MultiCast_ForAI-测试用例.xlsx（excel_dump.txt 第 20 行）生成
- 关联需求：3.1.20.1~3.1.20.5 IB多播支持
- CLI 部分目前为 ibstat 占位，待 CLI 转测后替换为实际 CLI 命令
"""

import os
import time
import re
import threading
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, BugTypeEnum, CmdExecuteAdressEnum
from scripts.script_libs.script_base import ScriptBase, SxeException


class IbMulticastMc025(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ib_send_bw, ib_read_bw, iperf, ibstat, smpquery, perfquery"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
已加载 ib_ipoib 驱动，opensm 已启动
测试节点之间 IB 网络互通
已安装 iperf 2.x"""
    test_steps = """
    1. 启动 ipoib 多播业务：iperf -s -u -B 224.0.0.20 / iperf -c 224.0.0.20 -u -T 5 -l 128 -i 1 -t <duration> -B <src_ip>。
    2. 启动 ib_send_bw -g 用户态多播业务。
    3. 启动 ib_read_bw 单播业务。
    4. 并发执行 CLI 业务（placeholder：ibstat）。
    5. 并发执行 SMA 业务：smpquery -C mlx5_0 sl2vl 1 1。
    6. 并发执行 PMA 业务：perfquery -C mlx5_0。
    7. 检查各类业务是否均正常执行。
    """

    TARGET_DEVICE = "mlx5_0"
    MGID = "255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:00"
    MCAST_GROUP = "224.0.0.20"
    IPOIB_SERVER_IP = "192.168.100.1/24"
    IPOIB_CLIENT_IP = "192.168.100.2/24"
    IPOIB_CLIENT_SRC = "192.168.100.2"
    IPOIB_DURATION = 15

    PERFTEST_PORT_MC = 18525
    PERFTEST_PORT_UC = 18526
    PERFTEST_DURATION = 10
    PERFTEST_STARTUP_WAIT = 3
    PERFTEST_STOP_WAIT = 2
    CONCURRENT_POLL_INTERVAL = 0.5

    # CLI 业务占位命令，待 CLI 转测后替换为实际 CLI 工具
    CLI_PLACEHOLDER_CMD = "ibstat"

    # 双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport
    PPORT_COUNT = 2
    OPENSM_STARTUP_WAIT = 10

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc025 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-25 测试环境...")

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
                f"ibstat {cls.TARGET_DEVICE}", exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value or "State: Active" not in result:
                log.error(f"{name} 端 {cls.TARGET_DEVICE} 未处于 Active 状态")
                cls.own_environment_enabled = False
                return

            status, result, err = CommandOperation.execute_command_with_error(
                "lsmod | grep -w ib_ipoib", exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value or "ib_ipoib" not in result:
                log.error(f"{name} 端未加载 ib_ipoib 驱动")
                cls.own_environment_enabled = False
                return

            status, result, err = CommandOperation.execute_command_with_error("which iperf", exec_addr)
            if status != RtnStatusEnum.SUCCESS.value or not result.strip():
                log.error(f"{name} 端未找到 iperf")
                cls.own_environment_enabled = False
                return

        cls.own_environment_enabled = True
        log.info("环境检查通过：两端 IB 设备 Active，已加载 ipoib 且存在 iperf")

    @classmethod
    def prepare(cls) -> None:
        super().prepare()
        log.info("准备 MC-25 测试环境...")
        cls.server_ip = cls._get_server_ip()

        # 识别两端 pport，供后续选择 ipoib 网口并启动 opensm
        cls.server_pf_list = cls._get_pf_list(CmdExecuteAdressEnum.SERVER.value, "server")
        cls.client_pf_list = cls._get_pf_list(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls.server_pport_list = cls._get_pport_list(cls.server_pf_list, "server")
        cls.client_pport_list = cls._get_pport_list(cls.client_pf_list, "client")

        cls.server_iface = cls._get_ipoib_iface(CmdExecuteAdressEnum.SERVER.value, "server")
        cls.client_iface = cls._get_ipoib_iface(CmdExecuteAdressEnum.CLIENT.value, "client")

        for exec_addr, name, pport_list in [
            (CmdExecuteAdressEnum.SERVER.value, "server", cls.server_pport_list),
            (CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_pport_list),
        ]:
            cls._stop_opensm(exec_addr, name)
            cls._start_opensm_for_pports(exec_addr, name, pport_list)
            cls._verify_opensm_for_pports(exec_addr, name, pport_list)
            cls._verify_all_pport_active(exec_addr, name, pport_list)

        cls._stop_iperf(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_iperf(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")

        cls._configure_ipv4(
            CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface, cls.IPOIB_SERVER_IP
        )
        cls._configure_ipv4(
            CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface, cls.IPOIB_CLIENT_IP
        )

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-25 测试：多播/单播/CLI/SMA/PMA 并发")
        log.info("=" * 60)

        try:
            results = {"ipoib": False, "mc_bw": False, "uc_bw": False}
            lock = threading.Lock()

            # 1. 启动 ipoib 多播服务端
            cls.server_log_a = f"/tmp/mc25_server_a_{cls.server_iface}.log"
            cls.server_log_b = f"/tmp/mc25_server_b_{cls.client_iface}.log"
            cls._start_iperf_server(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface, cls.server_log_a
            )
            cls._start_iperf_server(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface, cls.server_log_b
            )

            # 2. 启动 ib_send_bw 多播 server / ib_read_bw 单播 server
            cls.mc_server_log = "/tmp/mc25_mc_server.log"
            cls.uc_server_log = "/tmp/mc25_uc_server.log"
            cls._start_perftest_server(
                CmdExecuteAdressEnum.SERVER.value, "server",
                f"ib_send_bw -d {cls.TARGET_DEVICE} -g -M {cls.MGID} "
                f"-p {cls.PERFTEST_PORT_MC} -F",
                cls.mc_server_log,
            )
            cls._start_perftest_server(
                CmdExecuteAdressEnum.SERVER.value, "server",
                f"ib_read_bw -d {cls.TARGET_DEVICE} -p {cls.PERFTEST_PORT_UC} -F",
                cls.uc_server_log,
            )

            time.sleep(cls.PERFTEST_STARTUP_WAIT)

            # 3. 在独立线程中并发启动各类 client/查询业务
            threads = []
            threads.append(threading.Thread(
                target=cls._ipoib_client_worker,
                args=(results, lock),
                daemon=True,
            ))
            threads.append(threading.Thread(
                target=cls._mc_client_worker,
                args=(results, lock),
                daemon=True,
            ))
            threads.append(threading.Thread(
                target=cls._uc_client_worker,
                args=(results, lock),
                daemon=True,
            ))
            threads.append(threading.Thread(
                target=cls._cli_worker,
                args=(results, lock),
                daemon=True,
            ))
            threads.append(threading.Thread(
                target=cls._sma_worker,
                args=(results, lock),
                daemon=True,
            ))
            threads.append(threading.Thread(
                target=cls._pma_worker,
                args=(results, lock),
                daemon=True,
            ))

            for t in threads:
                t.start()

            # 等待各类业务完成（按最长时间等待）
            timeout = cls.IPOIB_DURATION + 20
            start = time.time()
            for t in threads:
                remaining = timeout - (time.time() - start)
                t.join(timeout=max(remaining, 1))

            # 4. 停止并读取日志验证
            cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
            cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")

            cls._verify_iperf_server_output(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_log_a
            )
            cls._verify_iperf_server_output(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b
            )

            mc_client_output = cls._read_log(
                CmdExecuteAdressEnum.CLIENT.value, "client", "/tmp/mc25_mc_client.log"
            )
            uc_client_output = cls._read_log(
                CmdExecuteAdressEnum.CLIENT.value, "client", "/tmp/mc25_uc_client.log"
            )
            cls._verify_perftest_bandwidth(mc_client_output, "多播")
            cls._verify_perftest_bandwidth(uc_client_output, "单播")

            log.info("=" * 60)
            log.info("测试执行成功 - MC-25 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-25 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-25 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-25 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-25 测试环境...")
        cls._stop_iperf(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_iperf(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._remove_ipv4_config(CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface)
        cls._remove_ipv4_config(CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface)
        for log_path in [
            cls.server_log_a, cls.server_log_b,
            "/tmp/mc25_mc_server.log", "/tmp/mc25_mc_client.log",
            "/tmp/mc25_uc_server.log", "/tmp/mc25_uc_client.log",
        ]:
            cls._remove_log_files(CmdExecuteAdressEnum.SERVER.value, "server", log_path)
            cls._remove_log_files(CmdExecuteAdressEnum.CLIENT.value, "client", log_path)
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        log.info("MC-25 清理完成")
        super().post()

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
            cls.create_bug(f"MC-25 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-25 {name} 端 PF 列表为空")

        return pf_list

    @classmethod
    def _get_pport_list(cls, pf_list: list, name: str) -> list:
        """识别所有 pport

        双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport。
        通过 PPORT_COUNT 控制，默认取前 2 个（不足则取全部）。
        """
        count = min(cls.PPORT_COUNT, len(pf_list))
        pport_list = pf_list[:count]
        log.info(f"{name} 端识别到的 pport 列表: {pport_list}")
        return pport_list

    @classmethod
    def _stop_opensm(cls, exec_addr: str, name: str) -> None:
        """停止 opensm"""
        cmd = "pkill -9 -x opensm 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        time.sleep(3)
        log.info(f"{name} 端 opensm 已停止")

    @classmethod
    def _start_opensm_for_pports(cls, exec_addr: str, name: str, pport_list: list) -> None:
        """为每个 pport 启动 opensm"""
        log.info(f"在 {name} 端为所有 pport 启动 opensm...")

        for idx, pport in enumerate(pport_list):
            guid = cls._get_device_guid(exec_addr, name, pport)
            log.info(f"为 {name} 端 pport {pport} 启动 opensm，GUID: {guid}")
            opensm_cmd = (
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_mc25_{idx}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端为 pport {pport} 启动 opensm 失败: {err}"
                cls.bug_expect = "opensm 应能在每个 pport 上成功启动"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-25 {name} 端 pport {pport} opensm 启动失败")
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
            cls.create_bug(f"MC-25 {name} 端 opensm 未运行")

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
            cls.create_bug(f"MC-25 {name} 端 opensm 进程数量不足")

        log.info(f"{name} 端 opensm 进程数量: {running_count}，pport 数量: {len(pport_list)}")

    @classmethod
    def _verify_all_pport_active(cls, exec_addr: str, name: str, pport_list: list) -> None:
        """验证所有 pport 均处于 Active/LinkUp 状态"""
        log.info(f"验证 {name} 端所有 pport 状态...")
        for pport in pport_list:
            status, result, err = CommandOperation.execute_command_with_error(
                f"ibstat {pport}", exec_addr
            )
            if (
                status != RtnStatusEnum.SUCCESS.value
                or "State: Active" not in result
                or "Physical state: LinkUp" not in result
            ):
                cls.bug_result = f"{name} 端 pport {pport} 未处于 Active/LinkUp 状态"
                cls.bug_expect = "opensm 启动后所有 pport 应处于 Active/LinkUp 状态"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-25 {name} 端 pport {pport} 未 Active")
        log.info(f"{name} 端所有 pport 均处于 Active/LinkUp 状态")

    @classmethod
    def _get_device_guid(cls, exec_addr: str, name: str, device: str) -> str:
        """获取指定 IB 设备的 Node GUID"""
        cmd = f"ibstat {device} | grep 'Node GUID'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端获取 {device} Node GUID 失败: {err}"
            cls.bug_expect = "ibstat 应能返回 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-25 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-25 {name} 端解析 {device} GUID 失败")

        return match.group(0)

    @classmethod
    def _is_opensm_running(cls, exec_addr: str) -> bool:
        """检查 opensm 进程是否正在运行"""
        status, _, _ = CommandOperation.execute_command_with_error(
            "pgrep -x opensm >/dev/null 2>&1", exec_addr
        )
        return status == RtnStatusEnum.SUCCESS.value

    @classmethod
    def _get_server_ip(cls) -> str:
        """获取服务端 IP"""
        if cls.server_logical_ip:
            return cls.server_logical_ip

        cmd = "ip route get 1.1.1.1 | awk '{print $7}' | head -1"
        status, result, err = CommandOperation.execute_command_with_error(
            cmd, CmdExecuteAdressEnum.SERVER.value
        )
        if status == RtnStatusEnum.SUCCESS.value and result.strip():
            return result.strip()

        cls.bug_result = "无法获取服务端 IP 地址"
        cls.bug_expect = "应能获取服务端可达 IP"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug("MC-25 获取服务端 IP 失败")

    @classmethod
    def _get_ipoib_iface(cls, exec_addr: str, name: str) -> str:
        log.info(f"获取 {name} 端 ipoib 网口...")
        cmd = "ibdev2netdev"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端执行 ibdev2netdev 失败: {err}"
            cls.bug_expect = "ibdev2netdev 应成功执行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-25 {name} 端 ibdev2netdev 执行失败")

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
        cls.create_bug(f"MC-25 {name} 端获取 ipoib 网口失败")

    @classmethod
    def _configure_ipv4(cls, exec_addr: str, name: str, iface: str, ipv4_addr: str) -> None:
        """配置 ipoib IPv4 地址和多播路由"""
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
                cls.create_bug(f"MC-25 {name} 端配置 IPv4/多播路由失败")
        log.info(f"{name} 端 {iface} IPv4 和多播路由配置完成")

    @classmethod
    def _remove_ipv4_config(cls, exec_addr: str, name: str, iface: str) -> None:
        log.info(f"清理 {name} 端 {iface} 的 IPv4 配置...")
        cmds = [
            f"ip route del {cls.MCAST_GROUP} dev {iface} 2>/dev/null || true",
            f"ip addr flush dev {iface}",
        ]
        for cmd in cmds:
            CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 {iface} IPv4 配置已清理")

    @classmethod
    def _start_iperf_server(cls, exec_addr: str, name: str, iface: str, log_path: str) -> None:
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
            cls.create_bug(f"MC-25 {name} 端启动 iperf 服务端失败")
        time.sleep(1)

    @classmethod
    def _ipoib_client_worker(cls, results: dict, lock: threading.Lock) -> None:
        """ipoib 多播客户端工作线程"""
        try:
            log_path = f"/tmp/mc25_client_{cls.client_iface}.log"
            cmd = (
                f"iperf -c {cls.MCAST_GROUP} -u -T 5 -l 128 -i 1 "
                f"-t {cls.IPOIB_DURATION} -B {cls.IPOIB_CLIENT_SRC} "
                f">\"{log_path}\" 2>&1"
            )
            log.info("启动 ipoib 多播客户端线程")
            CommandOperation.execute_command_with_error(
                cmd, CmdExecuteAdressEnum.CLIENT.value
            )
            with lock:
                results["ipoib"] = True
        except Exception as e:
            log.error(f"ipoib 多播客户端线程异常: {e}")

    @classmethod
    def _start_perftest_server(cls, exec_addr: str, name: str, cmd: str, log_path: str) -> None:
        log.info(f"在 {name} 端启动 perftest server: {cmd}")
        full_cmd = f"nohup {cmd} >\"{log_path}\" 2>&1 &"
        status, result, err = CommandOperation.execute_command_with_error(full_cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端启动 perftest server 失败: {err}"
            cls.bug_expect = "perftest server 应能后台启动"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-25 {name} 端启动 perftest server 失败")

    @classmethod
    def _mc_client_worker(cls, results: dict, lock: threading.Lock) -> None:
        """ib_send_bw 多播客户端工作线程"""
        try:
            time.sleep(cls.PERFTEST_STARTUP_WAIT)
            log_path = "/tmp/mc25_mc_client.log"
            cmd = (
                f"ib_send_bw -d {cls.TARGET_DEVICE} -g -M {cls.MGID} "
                f"-p {cls.PERFTEST_PORT_MC} -F {cls.server_ip} "
                f">\"{log_path}\" 2>&1"
            )
            log.info("启动 ib_send_bw 多播客户端线程")
            CommandOperation.execute_command_with_error(
                cmd, CmdExecuteAdressEnum.CLIENT.value, timeout=60
            )
            with lock:
                results["mc_bw"] = True
        except Exception as e:
            log.error(f"ib_send_bw 多播客户端线程异常: {e}")

    @classmethod
    def _uc_client_worker(cls, results: dict, lock: threading.Lock) -> None:
        """ib_read_bw 单播客户端工作线程"""
        try:
            time.sleep(cls.PERFTEST_STARTUP_WAIT + 1)
            log_path = "/tmp/mc25_uc_client.log"
            cmd = (
                f"ib_read_bw -d {cls.TARGET_DEVICE} -p {cls.PERFTEST_PORT_UC} "
                f"-F {cls.server_ip} >\"{log_path}\" 2>&1"
            )
            log.info("启动 ib_read_bw 单播客户端线程")
            CommandOperation.execute_command_with_error(
                cmd, CmdExecuteAdressEnum.CLIENT.value, timeout=60
            )
            with lock:
                results["uc_bw"] = True
        except Exception as e:
            log.error(f"ib_read_bw 单播客户端线程异常: {e}")

    @classmethod
    def _cli_worker(cls, results: dict, lock: threading.Lock) -> None:
        """CLI 业务工作线程（placeholder，待 CLI 转测后替换）"""
        log.warning("CLI 业务当前使用 ibstat 占位命令，待 CLI 转测后替换为实际 CLI 工具")
        try:
            status, result, err = CommandOperation.execute_command_with_error(
                cls.CLI_PLACEHOLDER_CMD, CmdExecuteAdressEnum.SERVER.value
            )
            if status != RtnStatusEnum.SUCCESS.value:
                log.warning(f"CLI 占位命令执行返回非 0: {err}；当前不阻塞测试")
            else:
                log.info("CLI 占位命令执行成功")
        except Exception as e:
            log.warning(f"CLI 占位命令执行异常: {e}；当前不阻塞测试")

    @classmethod
    def _sma_worker(cls, results: dict, lock: threading.Lock) -> None:
        """SMA 业务工作线程：循环执行 smpquery"""
        try:
            log.info("启动 SMA 业务线程")
            cmd = f"smpquery -C {cls.TARGET_DEVICE} sl2vl 1 1"
            for _ in range(5):
                status, result, err = CommandOperation.execute_command_with_error(
                    cmd, CmdExecuteAdressEnum.SERVER.value
                )
                if status != RtnStatusEnum.SUCCESS.value:
                    cls.bug_result = f"SMA 业务执行失败: {err}"
                    cls.bug_expect = "smpquery -C mlx5_0 sl2vl 1 1 应成功执行"
                    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                    cls.create_bug("MC-25 SMA 业务执行失败")
                time.sleep(2)
            log.info("SMA 业务线程执行完成")
        except Exception as e:
            log.error(f"SMA 业务线程异常: {e}")

    @classmethod
    def _pma_worker(cls, results: dict, lock: threading.Lock) -> None:
        """PMA 业务工作线程：循环执行 perfquery"""
        try:
            log.info("启动 PMA 业务线程")
            cmd = f"perfquery -C {cls.TARGET_DEVICE}"
            for _ in range(5):
                status, result, err = CommandOperation.execute_command_with_error(
                    cmd, CmdExecuteAdressEnum.SERVER.value
                )
                if status != RtnStatusEnum.SUCCESS.value:
                    cls.bug_result = f"PMA 业务执行失败: {err}"
                    cls.bug_expect = "perfquery -C mlx5_0 应成功执行"
                    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                    cls.create_bug("MC-25 PMA 业务执行失败")
                time.sleep(2)
            log.info("PMA 业务线程执行完成")
        except Exception as e:
            log.error(f"PMA 业务线程异常: {e}")

    @classmethod
    def _verify_iperf_server_output(cls, exec_addr: str, name: str, log_path: str) -> None:
        log.info(f"检查 {name} 端 iperf 服务端输出...")
        cmd = f"cat \"{log_path}\""
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or not result.strip():
            cls.bug_result = f"{name} 端 iperf 服务端日志为空或读取失败: {err}"
            cls.bug_expect = "iperf 服务端应收到多播流量"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-25 {name} 端 iperf 服务端输出为空")

        if not re.search(r"\d+\s+(Mbits/sec|Kbits/sec)", result):
            cls.bug_result = (
                f"{name} 端 iperf 服务端未检测到有效多播带宽。输出:\n{result}"
            )
            cls.bug_expect = "iperf 服务端输出中应包含有效的 Mbits/sec/Kbits/sec 带宽"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-25 {name} 端 iperf 多播流量异常")

        log.info(f"{name} 端 iperf 多播流量正常")

    @classmethod
    def _verify_perftest_bandwidth(cls, output: str, label: str) -> None:
        log.info(f"检查 {label} perftest 带宽结果...")
        pattern = re.compile(
            r"^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)",
            re.MULTILINE,
        )
        matches = pattern.findall(output)
        if not matches:
            cls.bug_result = f"{label} perftest 未找到有效带宽输出。输出:\n{output}"
            cls.bug_expect = f"{label} perftest 应产生有效带宽"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-25 {label} 无有效带宽")

        bw_value = float(matches[-1][3])
        if bw_value <= 0:
            cls.bug_result = f"{label} perftest 带宽为 0。输出:\n{output}"
            cls.bug_expect = f"{label} perftest 带宽应大于 0"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-25 {label} 带宽为 0")

        log.info(f"{label} perftest 带宽: {bw_value} MB/sec")

    @classmethod
    def _read_log(cls, exec_addr: str, name: str, log_path: str) -> str:
        cmd = f"cat \"{log_path}\""
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            return ""
        return result

    @classmethod
    def _stop_iperf(cls, exec_addr: str, name: str) -> None:
        cmd = "pkill -9 -x iperf 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 iperf 进程已清理")

    @classmethod
    def _stop_perftest_processes(cls, exec_addr: str, name: str) -> None:
        """停止 perftest 进程（使用 -x 精确匹配，避免误杀 SSH 会话）"""
        for proc in ["ib_send_bw", "ib_read_bw"]:
            cmd = f"pkill -9 -x {proc} 2>/dev/null || true"
            CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 perftest 进程已清理")

    @classmethod
    def _remove_log_files(cls, exec_addr: str, name: str, log_path: str) -> None:
        cmd = f"rm -f \"{log_path}\""
        CommandOperation.execute_command_with_error(cmd, exec_addr)

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-25 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc025.run()


if __name__ == '__main__':
    main()
