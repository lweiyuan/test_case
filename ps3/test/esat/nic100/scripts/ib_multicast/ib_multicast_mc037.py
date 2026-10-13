#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-37
case title: 多对多的多播（ipoib）业务期间，可以减少客户端（至0），然后新增客户端
test category: IB多播测试
check point: ipoib 多对多业务期间客户端全部退出后重新加入，业务可恢复
author: auto-generated
date: 2026.06.25
@steps:
    1. 两节点均配置 ipoib IPv4 地址和多播路由。
    2. 两节点均启动 iperf 多播服务端（绑定 224.0.0.20）。
    3. 两节点均启动 iperf 多播客户端，建立 2v2 多对多多播业务。
    4. 逐渐减少并停止所有客户端，业务流量应中断。
    5. 重新启动新的客户端加入多播组。
    6. 验证服务端再次收到多播流量，业务恢复。

@expected:
    客户端全部退出后，业务暂时中断；新增客户端可重新加入多播组，业务恢复。

@changelog:
2026.06.25 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.3 内核态QP加入多播组、3.1.20.4 内核态QP退出多播组
- 使用项目技巧：缺陷自动记录、IB基础概念与设备检查、IB命令处理与回显解析、IB多播与iperf测试
2026.06.30 - 参考 MC-38 代码结构重写
- 统一代码风格、方法命名与日志输出
- 服务端/客户端均通过 Python _thread 进行本地并发管理
- 远程 iperf 进程由 Python subprocess.Popen(start_new_session=True) 启动
- 为每个客户端分配独立端口（5001/5002），规避 iperf2 多播服务端单客户端模式限制
"""

import os
import re
import time
import base64
import _thread
import threading
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, BugTypeEnum, CmdExecuteAdressEnum, RdmaMode
from scripts.script_libs.script_base import ScriptBase, SxeException
from scripts.script_libs.common_operation import CommonOperation


class IbMulticastMc037(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ip, iperf, ibdev2netdev"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
已加载 ib_ipoib 驱动，opensm 已启动
同子网内两个节点均已配置 IPv4 地址
已安装 iperf 2.x"""
    test_steps = """
    1. 两节点配置多播路由：ip route add 224.0.0.20 dev ib0。
    2. 两节点启动 iperf 多播服务端：iperf -s -u -B 224.0.0.20 -i 1。
    3. 两节点启动 iperf 多播客户端，建立 2v2 业务。
    4. 停止所有客户端，验证业务中断。
    5. 重新启动新的客户端。
    6. 验证两节点服务端再次收到流量，业务恢复。
    """

    MCAST_GROUP = "224.0.0.20"
    IPOIB_SERVER_A_IP = "192.168.100.1/24"
    IPOIB_SERVER_B_IP = "192.168.100.2/24"
    IPOIB_CLIENT_SRC_A = "192.168.100.1"
    IPOIB_CLIENT_SRC_B = "192.168.100.2"
    IPOIB_IFACE = "ib0"

    # 服务端/客户端 IB 设备名，在 check_own_environment() 中从 env_config 动态读取
    server_device = ""
    client_device = ""

    IPERF_DURATION = 10
    IPERF_BACKGROUND_DURATION = 60
    IPERF_STARTUP_WAIT = 2
    IPERF_STOP_WAIT = 2
    IPERF_POLL_TIMEOUT = 30
    IPERF_VERIFY_WAIT = 5

    # iperf2 多播服务端为单客户端模式，每个客户端使用独立端口
    IPERF_PORT_A = 5001
    IPERF_PORT_B = 5002
    IPERF_PORTS = [IPERF_PORT_A, IPERF_PORT_B]

    # 双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport
    PPORT_COUNT = 2
    OPENSM_STARTUP_WAIT = 10

    # 通过 _thread 管理的 iperf 进程注册表
    _iperf_processes = {}
    _iperf_lock = threading.Lock()

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc037 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__
        cls._iperf_processes = {}
        cls._iperf_lock = threading.Lock()

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-37 测试环境...")

        server_relations, client_relations = CommonOperation.get_nic_relationships(
            rdma=True, nic_mode=RdmaMode.Infiniband.value
        )
        cls.server_device = server_relations[0].strip() if server_relations else ""
        cls.client_device = client_relations[0].strip() if client_relations else ""

        if not cls.server_device or not cls.client_device:
            log.error("无法从 env_config 获取服务端/客户端 IB 设备名")
            cls.own_environment_enabled = False
            return

        for exec_addr, name, device in [
            (CmdExecuteAdressEnum.SERVER.value, "server", cls.server_device),
            (CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_device),
        ]:
            status, result, err = CommandOperation.execute_command_with_error("ibstat -l", exec_addr)
            if status != RtnStatusEnum.SUCCESS.value or not result.strip():
                log.error(f"{name} 端未找到 IB 设备")
                cls.own_environment_enabled = False
                return

            status, result, err = CommandOperation.execute_command_with_error(
                f"ibstat {device}", exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value or "State: Active" not in result:
                log.error(f"{name} 端 {device} 未处于 Active 状态")
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
        log.info("环境检查通过：两端目标 IB 设备均处于 Active 状态")

    @classmethod
    def prepare(cls) -> None:
        super().prepare()
        log.info("准备 MC-37 测试环境...")

        # 先停止两端现有 opensm，再按 pport 重新启动
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")

        cls.server_pport_list = cls._get_pport_list(
            CmdExecuteAdressEnum.SERVER.value, "server"
        )
        cls.client_pport_list = cls._get_pport_list(
            CmdExecuteAdressEnum.CLIENT.value, "client"
        )

        cls._start_opensm_for_pports(
            CmdExecuteAdressEnum.SERVER.value, "server", cls.server_pport_list
        )
        cls._start_opensm_for_pports(
            CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_pport_list
        )
        cls._verify_opensm_for_pports(
            CmdExecuteAdressEnum.SERVER.value, "server", cls.server_pport_list
        )
        cls._verify_opensm_for_pports(
            CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_pport_list
        )
        cls._verify_all_pf_active(
            CmdExecuteAdressEnum.SERVER.value, "server", cls.server_pport_list
        )
        cls._verify_all_pf_active(
            CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_pport_list
        )

        cls.server_iface = cls._get_ipoib_iface(
            CmdExecuteAdressEnum.SERVER.value, "server"
        )
        cls.client_iface = cls._get_ipoib_iface(
            CmdExecuteAdressEnum.CLIENT.value, "client"
        )

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-37 测试：ipoib 多对多减少客户端至 0 后新增")
        log.info("=" * 60)

        try:
            # 配置 IPv4 地址和多播路由
            cls._configure_ipv4(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface, cls.IPOIB_SERVER_A_IP
            )
            cls._configure_ipv4(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface, cls.IPOIB_SERVER_B_IP
            )

            # 阶段1：启动服务端和客户端，建立 2v2 业务
            log.info("--- 阶段1：建立初始 2v2 多对多多播业务 ---")
            cls.server_log_a = f"/tmp/mc37_server_a_{cls.server_iface}.log"
            cls.server_log_a2 = f"/tmp/mc37_server_a2_{cls.server_iface}.log"
            cls.server_log_b = f"/tmp/mc37_server_b_{cls.client_iface}.log"
            cls.server_log_b2 = f"/tmp/mc37_server_b2_{cls.client_iface}.log"
            cls._stop_iperf(CmdExecuteAdressEnum.SERVER.value, "server")
            cls._stop_iperf(CmdExecuteAdressEnum.CLIENT.value, "client")
            cls._start_iperf_server(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface,
                cls.server_log_a, cls.IPERF_PORT_A
            )
            cls._start_iperf_server(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface,
                cls.server_log_a2, cls.IPERF_PORT_B
            )
            cls._start_iperf_server(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface,
                cls.server_log_b, cls.IPERF_PORT_A
            )
            cls._start_iperf_server(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface,
                cls.server_log_b2, cls.IPERF_PORT_B
            )

            cls.client_log_a = f"/tmp/mc37_client_a_{cls.server_iface}.log"
            cls.client_log_b = f"/tmp/mc37_client_b_{cls.client_iface}.log"
            pid_a = cls._start_iperf_client_background(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface,
                cls.IPOIB_CLIENT_SRC_A, cls.client_log_a, cls.IPERF_PORT_A
            )
            pid_b = cls._start_iperf_client_background(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface,
                cls.IPOIB_CLIENT_SRC_B, cls.client_log_b, cls.IPERF_PORT_B
            )

            time.sleep(cls.IPERF_STARTUP_WAIT)
            cls._verify_iperf_server_output(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_log_a
            )
            cls._verify_iperf_server_output(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_log_a2
            )
            cls._verify_iperf_server_output(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b
            )
            cls._verify_iperf_server_output(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b2
            )

            # 阶段2-1：停止 client A，验证 client 端业务仍可用
            log.info("--- 阶段2-1：停止 client A，验证业务仍可用 ---")
            cls._stop_iperf_client_by_pid(
                CmdExecuteAdressEnum.SERVER.value, "server", pid_a
            )
            cls._clear_server_log(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b
            )
            cls._clear_server_log(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b2
            )
            time.sleep(cls.IPERF_VERIFY_WAIT)
            cls._verify_iperf_server_output(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b2
            )

            # 阶段2-2：停止 client B，减少至 0，验证业务中断
            log.info("--- 阶段2-2：停止 client B，减少至 0，验证业务中断 ---")
            cls._stop_iperf_client_by_pid(
                CmdExecuteAdressEnum.CLIENT.value, "client", pid_b
            )
            cls._clear_server_log(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_log_a
            )
            cls._clear_server_log(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_log_a2
            )
            cls._clear_server_log(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b
            )
            cls._clear_server_log(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b2
            )
            time.sleep(cls.IPERF_VERIFY_WAIT)
            cls._verify_iperf_server_no_traffic(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_log_a
            )
            cls._verify_iperf_server_no_traffic(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_log_a2
            )
            cls._verify_iperf_server_no_traffic(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b
            )
            cls._verify_iperf_server_no_traffic(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b2
            )

            # 阶段3-1：新增 client A，验证业务开始恢复
            log.info("--- 阶段3-1：新增 client A，验证业务恢复 ---")
            cls.client_log_a_new = f"/tmp/mc37_client_a_new_{cls.server_iface}.log"
            pid_a_new = cls._start_iperf_client_background(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface,
                cls.IPOIB_CLIENT_SRC_A, cls.client_log_a_new, cls.IPERF_PORT_A
            )
            cls._clear_server_log(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_log_a
            )
            cls._clear_server_log(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_log_a2
            )
            cls._clear_server_log(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b
            )
            cls._clear_server_log(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b2
            )
            time.sleep(cls.IPERF_VERIFY_WAIT)
            cls._verify_iperf_server_output(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_log_a
            )
            cls._verify_iperf_server_output(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b
            )

            # 阶段3-2：新增 client B，验证业务完全恢复
            log.info("--- 阶段3-2：新增 client B，验证业务完全恢复 ---")
            cls.client_log_b_new = f"/tmp/mc37_client_b_new_{cls.client_iface}.log"
            pid_b_new = cls._start_iperf_client_background(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface,
                cls.IPOIB_CLIENT_SRC_B, cls.client_log_b_new, cls.IPERF_PORT_B
            )
            cls._clear_server_log(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_log_a
            )
            cls._clear_server_log(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_log_a2
            )
            cls._clear_server_log(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b
            )
            cls._clear_server_log(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b2
            )
            time.sleep(cls.IPERF_VERIFY_WAIT)
            cls._verify_iperf_server_output(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_log_a
            )
            cls._verify_iperf_server_output(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_log_a2
            )
            cls._verify_iperf_server_output(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b
            )
            cls._verify_iperf_server_output(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b2
            )

            # 记录新增客户端 PID，供清理使用
            cls.pid_a_new = pid_a_new
            cls.pid_b_new = pid_b_new

            log.info("=" * 60)
            log.info("测试执行成功 - MC-37 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-37 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-37 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-37 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-37 测试环境...")
        # 通过 _thread 并发停止所有已注册的 iperf 进程
        with cls._iperf_lock:
            registered_processes = list(cls._iperf_processes.values())
        if registered_processes:
            stop_infos = [
                (p["exec_addr"], p["name"], p["pid"])
                for p in registered_processes
            ]
            cls._stop_iperf_processes_with_thread(stop_infos)
        # 兜底清理
        cls._stop_iperf(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_iperf(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._remove_ipv4_config(CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface)
        cls._remove_ipv4_config(CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface)
        for log_path in [
            getattr(cls, "server_log_a", ""), getattr(cls, "server_log_a2", ""),
            getattr(cls, "server_log_b", ""), getattr(cls, "server_log_b2", ""),
            getattr(cls, "client_log_a", ""), getattr(cls, "client_log_b", ""),
            getattr(cls, "client_log_a_new", ""), getattr(cls, "client_log_b_new", ""),
        ]:
            if log_path:
                cls._remove_log_files(CmdExecuteAdressEnum.SERVER.value, "server", log_path)
                cls._remove_log_files(CmdExecuteAdressEnum.CLIENT.value, "client", log_path)
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        log.info("MC-37 清理完成")
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
            cls.create_bug(f"MC-37 {name} 端 ibdev2netdev 执行失败")

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
        cls.create_bug(f"MC-37 {name} 端获取 ipoib 网口失败")

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
                cls.create_bug(f"MC-37 {name} 端配置 IPv4/多播路由失败")
        log.info(f"{name} 端 {iface} IPv4 和多播路由配置完成")

    @classmethod
    def _build_remote_iperf_script(
        cls, process_type: str, iface: str, src_ip: str, log_path: str,
        duration: int = None, port: int = 5001
    ) -> str:
        """构造在远程节点上执行的 Python 脚本，使用 subprocess.Popen 启动 iperf。"""
        if process_type == "server":
            args = "['iperf','-s','-u','-B','{}','-i','1','-p','{}']".format(cls.MCAST_GROUP, port)
        else:
            args = (
                "['iperf','-c','{}','-u','-T','5','-l','128','-i','1',"
                "'-t','{}','-B','{}','-p','{}']"
            ).format(cls.MCAST_GROUP, duration, src_ip, port)
        script = (
            "import subprocess,sys\n"
            "log=open('{}','w')\n"
            "p=subprocess.Popen({},stdout=log,stderr=log,start_new_session=True)\n"
            "print(p.pid)\n"
        ).format(log_path, args)
        return script

    @classmethod
    def _remote_start_iperf(
        cls, exec_addr: str, name: str, process_type: str, iface: str,
        src_ip: str, log_path: str, duration: int = None, port: int = 5001
    ) -> str:
        """在远程节点通过 Python 子进程启动 iperf，并返回 PID。"""
        log.info(
            f"通过 _thread 管理：在 {name} 端启动 iperf {process_type} "
            f"(iface={iface}, port={port})..."
        )
        script = cls._build_remote_iperf_script(
            process_type, iface, src_ip, log_path, duration, port
        )
        encoded = base64.b64encode(script.encode("utf-8")).decode("utf-8")
        # 命令字符串中避免出现 "iperf -"/"iperf3 -"，防止 CommandOperation 自动替换 port
        cmd = f"echo '{encoded}' | base64 -d | python3"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or not result.strip():
            raise RuntimeError(f"{name} 端启动 iperf {process_type} 失败: {err}")
        pid = result.strip().splitlines()[-1].strip()
        if not pid.isdigit():
            raise RuntimeError(f"{name} 端解析 iperf {process_type} PID 失败: {result}")
        log.info(f"{name} 端 iperf {process_type} 已启动，PID: {pid}")
        return pid

    @classmethod
    def _start_iperf_processes_with_thread(cls, process_infos: list) -> list:
        """使用 Python _thread 在本地并发启动多个远程 iperf 进程。"""
        if not process_infos:
            return []

        results = [None] * len(process_infos)
        errors = [None] * len(process_infos)
        counter = [0]
        lock = threading.Lock()

        def worker(idx: int, info: dict):
            try:
                pid = cls._remote_start_iperf(
                    info["exec_addr"], info["name"], info["process_type"],
                    info["iface"], info.get("src_ip", ""), info["log_path"],
                    info.get("duration"), info.get("port", 5001)
                )
                with lock:
                    results[idx] = pid
                    cls._iperf_processes[info["log_path"]] = {
                        "exec_addr": info["exec_addr"],
                        "name": info["name"],
                        "pid": pid,
                        "log_path": info["log_path"],
                        "process_type": info["process_type"],
                    }
                    counter[0] += 1
            except Exception as e:
                with lock:
                    errors[idx] = str(e)
                    counter[0] += 1

        for idx, info in enumerate(process_infos):
            _thread.start_new_thread(worker, (idx, info))

        timeout = 30
        start = time.time()
        while time.time() - start < timeout:
            with lock:
                if counter[0] == len(process_infos):
                    break
            time.sleep(0.2)

        for err in errors:
            if err:
                cls.bug_result = err
                cls.bug_expect = "通过 Python _thread 并发启动 iperf 多播进程应成功"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug("MC-37 通过 _thread 启动 iperf 多播进程失败")

        return results

    @classmethod
    def _stop_iperf_processes_with_thread(cls, stop_infos: list) -> None:
        """使用 Python _thread 在本地并发停止多个远程 iperf 进程。"""
        if not stop_infos:
            return

        counter = [0]
        lock = threading.Lock()
        errors = []

        def worker(exec_addr: str, name: str, pid: str):
            try:
                log.info(f"通过 _thread 管理：停止 {name} 端 iperf 进程 PID={pid}...")
                cmd = f"kill -9 {pid} 2>/dev/null || true"
                CommandOperation.execute_command_with_error(cmd, exec_addr)
                with lock:
                    counter[0] += 1
            except Exception as e:
                with lock:
                    counter[0] += 1
                    errors.append(str(e))

        for exec_addr, name, pid in stop_infos:
            _thread.start_new_thread(worker, (exec_addr, name, pid))

        timeout = 20
        start = time.time()
        while time.time() - start < timeout:
            with lock:
                if counter[0] == len(stop_infos):
                    break
            time.sleep(0.2)

        if errors:
            log.warning(f"通过 _thread 停止部分 iperf 进程时出现异常: {errors}")

    @classmethod
    def _remove_iperf_process_by_pid(cls, pid: str) -> None:
        """从注册表中移除指定 PID 的 iperf 进程。"""
        with cls._iperf_lock:
            keys_to_remove = [
                key for key, proc in cls._iperf_processes.items()
                if proc.get("pid") == pid
            ]
            for key in keys_to_remove:
                del cls._iperf_processes[key]

    @classmethod
    def _start_iperf_server(
        cls, exec_addr: str, name: str, iface: str, log_path: str, port: int = 5001
    ) -> str:
        """通过 _thread 启动单个 iperf 多播服务端，并返回 PID。"""
        log.info(f"在 {name} 端启动 iperf 多播服务端（port={port}）...")
        process_infos = [
            {
                "exec_addr": exec_addr,
                "name": name,
                "process_type": "server",
                "iface": iface,
                "src_ip": "",
                "log_path": log_path,
                "port": port,
            }
        ]
        pids = cls._start_iperf_processes_with_thread(process_infos)
        time.sleep(cls.IPERF_STARTUP_WAIT)
        return pids[0] if pids else None

    @classmethod
    def _start_iperf_client_background(
        cls, exec_addr: str, name: str, iface: str, src_ip: str, log_path: str, port: int = 5001
    ) -> str:
        """通过 _thread 启动单个后台 iperf 多播客户端，并返回 PID。"""
        log.info(f"在 {name} 端后台启动 iperf 多播客户端（port={port}）...")
        process_infos = [
            {
                "exec_addr": exec_addr,
                "name": name,
                "process_type": "client",
                "iface": iface,
                "src_ip": src_ip,
                "log_path": log_path,
                "duration": cls.IPERF_BACKGROUND_DURATION,
                "port": port,
            }
        ]
        pids = cls._start_iperf_processes_with_thread(process_infos)
        time.sleep(1)
        return pids[0] if pids else None

    @classmethod
    def _stop_iperf_client_by_pid(cls, exec_addr: str, name: str, pid: str) -> None:
        """根据 PID 停止单个 iperf 客户端，并从注册表中移除。"""
        cls._stop_iperf_processes_with_thread([(exec_addr, name, pid)])
        cls._remove_iperf_process_by_pid(pid)
        time.sleep(cls.IPERF_STOP_WAIT)
        log.info(f"{name} 端 iperf 客户端 PID={pid} 已停止")

    @classmethod
    def _verify_iperf_server_output(cls, exec_addr: str, name: str, log_path: str) -> None:
        """检查单个 iperf 服务端日志中是否有有效多播带宽。"""
        log.info(f"检查 {name} 端 iperf 服务端输出 {log_path}...")
        cmd = f"cat \"{log_path}\""
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or not result.strip():
            cls.bug_result = f"{name} 端 iperf 服务端日志为空或读取失败: {err}"
            cls.bug_expect = "iperf 服务端应收到多播流量"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-37 {name} 端 iperf 服务端输出为空")

        if not re.search(r"\d+\s+(Mbits/sec|Kbits/sec)", result):
            cls.bug_result = (
                f"{name} 端 iperf 服务端未检测到有效多播带宽。输出:\n{result}"
            )
            cls.bug_expect = "iperf 服务端输出中应包含有效的 Mbits/sec/Kbits/sec 带宽"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-37 {name} 端 iperf 多播流量异常")

        log.info(f"{name} 端 iperf 多播流量正常")

    @classmethod
    def _verify_iperf_server_no_traffic(cls, exec_addr: str, name: str, log_path: str) -> None:
        """验证单个 iperf 服务端日志中无新增多播流量。"""
        log.info(f"检查 {name} 端 iperf 服务端无流量 {log_path}...")
        cmd = f"cat \"{log_path}\""
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端读取 iperf 服务端日志失败: {err}"
            cls.bug_expect = "应能读取 iperf 服务端日志"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-37 {name} 端读取 iperf 服务端日志失败")

        if re.search(r"\d+\s+(Mbits/sec|Kbits/sec)", result):
            cls.bug_result = (
                f"{name} 端 iperf 服务端在客户端全部退出后仍收到多播流量。输出:\n{result}"
            )
            cls.bug_expect = "客户端全部退出后，服务端应不再收到多播流量"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-37 {name} 端客户端全部退出后仍有流量")

        log.info(f"{name} 端 iperf 服务端无新增流量，符合预期")

    @classmethod
    def _clear_server_log(cls, exec_addr: str, name: str, log_path: str) -> None:
        """清空服务端日志，便于判断新增客户端是否恢复流量"""
        log.info(f"清空 {name} 端服务端日志 {log_path}...")
        cmd = f"> \"{log_path}\""
        CommandOperation.execute_command_with_error(cmd, exec_addr)

    @classmethod
    def _stop_iperf(cls, exec_addr: str, name: str) -> None:
        cmd = "pkill -9 -x iperf 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 iperf 进程已清理")

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
    def _remove_log_files(cls, exec_addr: str, name: str, log_path: str) -> None:
        cmd = f"rm -f \"{log_path}\""
        CommandOperation.execute_command_with_error(cmd, exec_addr)

    @classmethod
    def _get_pport_list(cls, exec_addr: str, name: str) -> list:
        """识别 pport（取前 PPORT_COUNT 个 PF，不足则取全部）"""
        log.info(f"获取 {name} 端 PF 列表并识别 pport...")
        cmd = "ibstat -l"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端执行 ibstat -l 失败: {err}"
            cls.bug_expect = "ibstat -l 应成功执行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-37 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-37 {name} 端 PF 列表为空")

        count = min(cls.PPORT_COUNT, len(pf_list))
        pport_list = pf_list[:count]
        log.info(f"{name} 端 pport 列表: {pport_list}")
        return pport_list

    @classmethod
    def _start_opensm_for_pports(
        cls, exec_addr: str, name: str, pport_list: list
    ) -> None:
        """为每个 pport 启动 opensm"""
        log.info(f"在 {name} 端为所有 pport 启动 opensm...")

        for idx, pport in enumerate(pport_list):
            guid = cls._get_device_guid(exec_addr, name, pport)
            log.info(f"为 pport {pport} 启动 opensm，GUID: {guid}")
            opensm_cmd = (
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_mc37_{idx}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端为 pport {pport} 启动 opensm 失败: {err}"
                cls.bug_expect = "opensm 应能在每个 pport 上成功启动"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-37 {name} 端 pport {pport} opensm 启动失败")
            time.sleep(3)

        # 等待 opensm 完成子网扫描
        time.sleep(cls.OPENSM_STARTUP_WAIT)

    @classmethod
    def _verify_opensm_for_pports(
        cls, exec_addr: str, name: str, pport_list: list
    ) -> None:
        """验证每个 pport 上的 opensm 进程正在运行"""
        log.info(f"验证 {name} 端所有 pport 的 opensm 进程...")

        status, result, err = CommandOperation.execute_command_with_error(
            "pgrep -x opensm", exec_addr
        )
        running_count = len(
            [line.strip() for line in result.splitlines() if line.strip()]
        )
        if running_count < len(pport_list):
            cls.bug_result = (
                f"{name} 端 opensm 进程数量不足，实际 {running_count} 个，"
                f"期望至少 {len(pport_list)} 个（每个 pport 一个）"
            )
            cls.bug_expect = "每个 pport 上应运行一个 opensm 实例"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-37 {name} 端 opensm 进程数量不足")

        log.info(
            f"{name} 端 opensm 进程数量: {running_count}，pport 数量: {len(pport_list)}"
        )

    @classmethod
    def _verify_all_pf_active(
        cls, exec_addr: str, name: str, pf_list: list
    ) -> None:
        """验证所有 PF 均处于 Active/LinkUp 状态"""
        log.info(f"验证 {name} 端所有 PF 状态...")
        for pf in pf_list:
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
                cls.create_bug(f"MC-37 {name} 端 PF {pf} 未 Active")
        log.info(f"{name} 端所有 PF 均处于 Active 状态")

    @classmethod
    def _get_device_guid(cls, exec_addr: str, name: str, device: str) -> str:
        """获取指定 IB 设备的 Node GUID"""
        cmd = f"ibstat {device} | grep 'Node GUID'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端获取 {device} Node GUID 失败: {err}"
            cls.bug_expect = "ibstat 应能返回 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-37 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = (
                f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            )
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-37 {name} 端解析 {device} GUID 失败")

        return match.group(0)

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
        cls.bug_expect = "MC-37 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc037.run()


if __name__ == '__main__':
    main()
