#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-11/12/13
case title: 16个PF均进行多播测试
test category: IB多播测试
check point: 多 PF 场景下多播业务均成功
author: auto-generated
date: 2026.06.24
@steps:
    场景1：16 个 PF 均使用 ib_send_bw -g 进行多播。
    场景2：16 个 PF 均使用 ipoib 进行多播。
    场景3：8 个 PF 使用 ib_send_bw 多播，8 个 PF 使用 ipoib 多播。

@expected:
    三种情况下 16 个 PF 的多播业务均成功。

@changelog:
2026.06.24 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.1 用户态QP退出多播组、3.1.20.2 用户态QP加入多播组、3.1.20.3 内核态QP加入多播组、3.1.20.4 内核态QP退出多播组
- 使用项目技巧：缺陷自动记录、IB基础概念与设备检查、IB命令处理与回显解析、perftest工具使用、IB多播与iperf测试
2026.06.26 - 修正：识别所有 pport 并为每个 pport 启动并检查 opensm；prepare/post 补充 super() 调用
"""

import os
import time
import re
import _thread
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, BugTypeEnum, CmdExecuteAdressEnum
from scripts.script_libs.script_base import ScriptBase, SxeException


class IbMulticastMc011(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ib_send_bw, iperf, ip, ibstat, ibdev2netdev, opensm"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
opensm 已启动
已创建 16 个 PF（脚本会动态获取实际 PF 列表）
已安装 iperf 2.x"""
    test_steps = """
    1. 获取节点上所有 IB PF 列表，识别所有 pport。
    2. 为每个 pport 启动 opensm 并确认运行。
    3. 场景1：每个 PF 使用 ib_send_bw -g 进行自发自收多播。
    4. 场景2：每个 PF 使用 ipoib 进行自发自收多播。
    5. 场景3：前半 PF 使用 ib_send_bw，后半 PF 使用 ipoib 进行多播。
    6. 检查每个 PF 是否均产生有效带宽。
    """

    # 双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport
    PPORT_COUNT = 2
    MGID_BASE = "255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:"
    PERFTEST_PORT_BASE = 18600
    IPERF_PORT_BASE = 19600
    IPOIB_IP_BASE = "192.168."
    MCAST_GROUP_BASE = "224.0.0."
    PERFTEST_DURATION = 5
    IPERF_DURATION = 5
    CONCURRENT_TIMEOUT = 180
    OPENSM_STARTUP_WAIT = 10

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc011 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-11/12/13 测试环境...")

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
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

        cls.own_environment_enabled = True
        log.info("环境检查通过")

    @classmethod
    def prepare(cls) -> None:
        super().prepare()
        log.info("准备 MC-11/12/13 测试环境...")
        cls.pf_list = cls._get_pf_list(CmdExecuteAdressEnum.SERVER.value, "server")
        if len(cls.pf_list) < 2:
            cls.bug_result = f"server 端 PF 数量不足，实际只有 {len(cls.pf_list)} 个"
            cls.bug_expect = "应至少存在 2 个 IB PF 以执行多播并发测试"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("MC-11/12/13 PF 数量不足")

        # 识别所有 pport 并确保 opensm 已启动
        cls.pport_list = cls._get_pport_list(cls.pf_list)
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._start_opensm_for_pports(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._verify_opensm_for_pports(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._verify_all_pf_active(CmdExecuteAdressEnum.SERVER.value, "server")

        cls.pf_iface_map = cls._get_pf_iface_map(
            CmdExecuteAdressEnum.SERVER.value, "server", cls.pf_list
        )
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_iperf(CmdExecuteAdressEnum.SERVER.value, "server")
        log.info(f"server 端 PF 列表: {cls.pf_list}")
        log.info(f"server 端 pport 列表: {cls.pport_list}")
        log.info(f"PF -> iface 映射: {cls.pf_iface_map}")

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-11/12/13 测试：多 PF 多播并发")
        log.info("=" * 60)

        try:
            # 场景1：全部 PF 使用 ib_send_bw -g
            log.info("--- 场景 1/3: 全部 PF 使用 ib_send_bw -g ---")
            cls._run_ib_send_bw_for_all_pf()

            # 场景2：全部 PF 使用 ipoib
            log.info("--- 场景 2/3: 全部 PF 使用 ipoib ---")
            cls._run_ipoib_for_all_pf()

            # 场景3：混合
            log.info("--- 场景 3/3: 前半 PF 使用 ib_send_bw，后半 PF 使用 ipoib ---")
            mid = len(cls.pf_list) // 2
            cls._run_mixed_for_all_pf(cls.pf_list[:mid], cls.pf_list[mid:])

            log.info("=" * 60)
            log.info("测试执行成功 - MC-11/12/13 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-11/12/13 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-11/12/13 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-11/12/13 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-11/12/13 测试环境...")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_iperf(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._remove_ipoib_config_for_all_pf()
        cls._remove_log_files()
        log.info("MC-11/12/13 清理完成")
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
            cls.create_bug(f"MC-11/12/13 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-11/12/13 {name} 端 PF 列表为空")

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
    def _get_pf_iface_map(cls, exec_addr: str, name: str, pf_list: list) -> dict:
        """一次性获取所有 PF 对应的 ipoib 网口映射"""
        log.info(f"获取 {name} 端 PF -> ipoib 网口映射...")
        cmd = "ibdev2netdev"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端执行 ibdev2netdev 失败: {err}"
            cls.bug_expect = "ibdev2netdev 应成功执行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-11/12/13 {name} 端 ibdev2netdev 执行失败")

        mapping = {}
        for pf in pf_list:
            pattern = re.compile(rf"^{re.escape(pf)}\s+port\s+\d+\s+==>\s+(\S+)")
            found = False
            for line in result.splitlines():
                match = pattern.match(line.strip())
                if match:
                    iface = match.group(1)
                    if iface.startswith("ib"):
                        mapping[pf] = iface
                        found = True
                        break
            if not found:
                # fallback：按索引推断
                idx = int(re.search(r'\d+', pf).group()) if re.search(r'\d+', pf) else 0
                mapping[pf] = f"ib{idx}"
                log.warning(f"无法从 ibdev2netdev 获取 {pf} 的 ipoib 网口，fallback 为 {mapping[pf]}")
        return mapping

    @classmethod
    def _start_opensm_for_pports(cls, exec_addr: str, name: str) -> None:
        """为每个 pport 启动 opensm"""
        log.info(f"在 {name} 端为所有 pport 启动 opensm...")

        for idx, pport in enumerate(cls.pport_list):
            guid = cls._get_device_guid(exec_addr, name, pport)
            log.info(f"为 pport {pport} 启动 opensm，GUID: {guid}")
            opensm_cmd = (
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_mc11_{idx}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端为 pport {pport} 启动 opensm 失败: {err}"
                cls.bug_expect = "opensm 应能在每个 pport 上成功启动"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-11/12/13 {name} 端 pport {pport} opensm 启动失败")
            time.sleep(3)

        # 等待 opensm 完成子网扫描
        time.sleep(cls.OPENSM_STARTUP_WAIT)

    @classmethod
    def _verify_opensm_for_pports(cls, exec_addr: str, name: str) -> None:
        """验证每个 pport 上的 opensm 进程正在运行"""
        log.info(f"验证 {name} 端所有 pport 的 opensm 进程...")

        if not cls._is_opensm_running(exec_addr):
            cls.bug_result = f"{name} 端未检测到任何 opensm 进程"
            cls.bug_expect = "每个 pport 上应运行一个 opensm 实例"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-11/12/13 {name} 端 opensm 未运行")

        # 验证 opensm 进程数量不少于 pport 数量
        status, result, err = CommandOperation.execute_command_with_error(
            "pgrep -x opensm", exec_addr
        )
        running_count = len([line.strip() for line in result.splitlines() if line.strip()])
        if running_count < len(cls.pport_list):
            cls.bug_result = (
                f"{name} 端 opensm 进程数量不足，实际 {running_count} 个，"
                f"期望至少 {len(cls.pport_list)} 个（每个 pport 一个）"
            )
            cls.bug_expect = "每个 pport 上应运行一个 opensm 实例"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-11/12/13 {name} 端 opensm 进程数量不足")

        log.info(f"{name} 端 opensm 进程数量: {running_count}，pport 数量: {len(cls.pport_list)}")

    @classmethod
    def _verify_all_pf_active(cls, exec_addr: str, name: str) -> None:
        """验证所有 PF 均处于 Active 状态"""
        log.info(f"验证 {name} 端所有 PF 状态...")
        for pf in cls.pf_list:
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
                cls.create_bug(f"MC-11/12/13 {name} 端 PF {pf} 未 Active")
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
            cls.create_bug(f"MC-11/12/13 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-11/12/13 {name} 端解析 {device} GUID 失败")

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
    def _run_ib_send_bw_for_all_pf(cls) -> None:
        """场景1：每个 PF 使用 ib_send_bw -g 自发自收"""
        results = []
        completed = [0]
        lock = _thread.allocate_lock()

        for idx, pf in enumerate(cls.pf_list):
            port = cls.PERFTEST_PORT_BASE + idx
            mgid = f"{cls.MGID_BASE}{idx:02x}"
            _thread.start_new_thread(
                cls._ib_send_bw_self_thread,
                (pf, mgid, port, results, completed, lock)
            )

        cls._wait_for_completion(completed, len(cls.pf_list))
        cls._verify_results(results, "ib_send_bw -g")

    @classmethod
    def _run_ipoib_for_all_pf(cls) -> None:
        """场景2：每个 PF 使用 ipoib 自发自收"""
        # 为每个 PF 配置 IP 并启动自发自收 iperf
        results = []
        completed = [0]
        lock = _thread.allocate_lock()

        for idx, pf in enumerate(cls.pf_list):
            mcast_idx = 30 + idx
            port = cls.IPERF_PORT_BASE + idx
            _thread.start_new_thread(
                cls._ipoib_self_thread,
                (pf, mcast_idx, port, results, completed, lock)
            )

        cls._wait_for_completion(completed, len(cls.pf_list))
        cls._verify_results(results, "ipoib iperf")

    @classmethod
    def _run_mixed_for_all_pf(cls, pf_bw: list, pf_ipoib: list) -> None:
        """场景3：混合"""
        results = []
        completed = [0]
        lock = _thread.allocate_lock()

        for idx, pf in enumerate(pf_bw):
            port = cls.PERFTEST_PORT_BASE + 100 + idx
            mgid = f"{cls.MGID_BASE}{200 + idx:02x}"
            _thread.start_new_thread(
                cls._ib_send_bw_self_thread,
                (pf, mgid, port, results, completed, lock)
            )

        for idx, pf in enumerate(pf_ipoib):
            mcast_idx = 60 + idx
            port = cls.IPERF_PORT_BASE + 100 + idx
            _thread.start_new_thread(
                cls._ipoib_self_thread,
                (pf, mcast_idx, port, results, completed, lock)
            )

        cls._wait_for_completion(completed, len(pf_bw) + len(pf_ipoib))
        cls._verify_results(results, "mixed ib_send_bw + ipoib")

    @staticmethod
    def _ib_send_bw_self_thread(pf: str, mgid: str, port: int, results: list, completed: list, lock) -> None:
        """单个 PF 的 ib_send_bw 自发自收线程"""
        exec_addr = CmdExecuteAdressEnum.SERVER.value
        server_log = f"/tmp/mc11_bw_server_{pf}.log"
        client_log = f"/tmp/mc11_bw_client_{pf}.log"
        local_ip = IbMulticastMc011._get_local_ip_static(exec_addr)

        try:
            # 启动 server
            server_cmd = (
                f"nohup ib_send_bw -d {pf} -g -M {mgid} -p {port} -F "
                f">\"{server_log}\" 2>&1 &"
            )
            CommandOperation.execute_command_with_error(server_cmd, exec_addr)
            time.sleep(2)

            # 启动 client
            client_cmd = (
                f"nohup ib_send_bw -d {pf} -g -M {mgid} -p {port} -F {local_ip} "
                f">\"{client_log}\" 2>&1 &"
            )
            CommandOperation.execute_command_with_error(client_cmd, exec_addr)
            time.sleep(IbMulticastMc011.PERFTEST_DURATION + 2)

            # 停止该 PF 的进程
            CommandOperation.execute_command_with_error(
                f'pkill -9 -f "ib_send_bw -d {pf}" 2>/dev/null || true', exec_addr
            )

            # 读取 client 日志
            cat_status, output, _ = CommandOperation.execute_command_with_error(
                f"cat \"{client_log}\"", exec_addr
            )
            res = {
                "pf": pf,
                "type": "ib_send_bw",
                "output": output if cat_status == RtnStatusEnum.SUCCESS.value else "",
            }
        except Exception as e:
            res = {"pf": pf, "type": "ib_send_bw", "output": "", "err": str(e)}

        with lock:
            results.append(res)
            completed[0] += 1

    @staticmethod
    def _ipoib_self_thread(pf: str, mcast_idx: int, port: int, results: list, completed: list, lock) -> None:
        """单个 PF 的 ipoib 自发自收线程"""
        exec_addr = CmdExecuteAdressEnum.SERVER.value
        mcast_group = f"{IbMulticastMc011.MCAST_GROUP_BASE}{mcast_idx}"
        server_ip = f"{IbMulticastMc011.IPOIB_IP_BASE}{mcast_idx}.1/24"
        client_ip = f"{IbMulticastMc011.IPOIB_IP_BASE}{mcast_idx}.2/24"
        iface = IbMulticastMc011.pf_iface_map.get(pf, f"ib{pf[-1]}")
        server_log = f"/tmp/mc11_ipoib_server_{pf}.log"
        client_log = f"/tmp/mc11_ipoib_client_{pf}.log"

        try:
            # 配置 IP
            cmds = [
                f"ip addr flush dev {iface}",
                f"ip addr add {server_ip} dev {iface}",
                f"ip addr add {client_ip} dev {iface}",
                f"ip link set {iface} up",
                f"ip route add {mcast_group} dev {iface} 2>/dev/null || true",
            ]
            for cmd in cmds:
                CommandOperation.execute_command_with_error(cmd, exec_addr)

            # 启动 iperf server
            server_cmd = (
                f"nohup iperf -s -u -B {mcast_group} -i 1 -p {port} "
                f">\"{server_log}\" 2>&1 &"
            )
            CommandOperation.execute_command_with_error(server_cmd, exec_addr)
            time.sleep(2)

            # 启动 iperf client
            client_cmd = (
                f"iperf -c {mcast_group} -u -l 128 -i 1 -p {port} "
                f"-t {IbMulticastMc011.IPERF_DURATION} -B {client_ip[:-3]} "
                f">\"{client_log}\" 2>&1"
            )
            CommandOperation.execute_command_with_error(client_cmd, exec_addr)
            time.sleep(IbMulticastMc011.IPERF_DURATION + 2)

            # 停止进程
            CommandOperation.execute_command_with_error(
                f'pkill -9 -f "iperf -s -u -B {mcast_group}" 2>/dev/null || true', exec_addr
            )

            # 读取 client 日志
            cat_status, output, _ = CommandOperation.execute_command_with_error(
                f"cat \"{client_log}\"", exec_addr
            )
            res = {
                "pf": pf,
                "type": "ipoib",
                "output": output if cat_status == RtnStatusEnum.SUCCESS.value else "",
            }
        except Exception as e:
            res = {"pf": pf, "type": "ipoib", "output": "", "err": str(e)}

        with lock:
            results.append(res)
            completed[0] += 1

    @classmethod
    def _wait_for_completion(cls, completed: list, total: int) -> None:
        """等待所有线程完成"""
        start_time = time.time()
        while completed[0] < total:
            if time.time() - start_time > cls.CONCURRENT_TIMEOUT:
                log.error(f"Timeout: {completed[0]}/{total} tasks completed")
                break
            time.sleep(0.5)
        log.info(f"完成任务数: {completed[0]}/{total}")

    @classmethod
    def _verify_results(cls, results: list, scenario: str) -> None:
        """验证每个 PF 的结果"""
        log.info(f"验证场景: {scenario}")
        for res in results:
            pf = res["pf"]
            output = res.get("output", "")
            test_type = res.get("type", "")

            if test_type == "ib_send_bw":
                pattern = re.compile(
                    r"^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)",
                    re.MULTILINE,
                )
                matches = pattern.findall(output)
                if not matches or float(matches[-1][3]) <= 0:
                    cls.bug_result = f"场景 {scenario} 中 PF {pf} 的 ib_send_bw 无有效带宽。输出:\n{output}"
                    cls.bug_expect = f"PF {pf} 的 ib_send_bw 多播应产生有效带宽"
                    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                    cls.create_bug(f"MC-11/12/13 场景 {scenario} PF {pf} 无有效带宽")
            else:
                if not re.search(r"\d+\s+(Mbits/sec|Kbits/sec)", output):
                    cls.bug_result = f"场景 {scenario} 中 PF {pf} 的 ipoib iperf 无有效带宽。输出:\n{output}"
                    cls.bug_expect = f"PF {pf} 的 ipoib 多播应产生有效带宽"
                    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                    cls.create_bug(f"MC-11/12/13 场景 {scenario} PF {pf} 无有效带宽")

            log.info(f"PF {pf} ({test_type}) 验证通过")

    @classmethod
    def _remove_ipoib_config_for_all_pf(cls) -> None:
        """清理所有 PF 的 ipoib IP 配置"""
        exec_addr = CmdExecuteAdressEnum.SERVER.value
        for idx, pf in enumerate(cls.pf_list):
            try:
                iface = cls.pf_iface_map.get(pf, f"ib{pf[-1]}")
                mcast_group = f"{cls.MCAST_GROUP_BASE}{30 + idx}"
                cmds = [
                    f"ip route del {mcast_group} dev {iface} 2>/dev/null || true",
                    f"ip addr flush dev {iface}",
                ]
                for cmd in cmds:
                    CommandOperation.execute_command_with_error(cmd, exec_addr)
            except Exception as e:
                log.warning(f"清理 PF {pf} 的 ipoib 配置时出错: {e}")

    @classmethod
    def _remove_log_files(cls) -> None:
        """清理所有日志文件"""
        exec_addr = CmdExecuteAdressEnum.SERVER.value
        for pf in cls.pf_list:
            for log_path in [
                f"/tmp/mc11_bw_server_{pf}.log",
                f"/tmp/mc11_bw_client_{pf}.log",
                f"/tmp/mc11_ipoib_server_{pf}.log",
                f"/tmp/mc11_ipoib_client_{pf}.log",
            ]:
                CommandOperation.execute_command_with_error(
                    f"rm -f \"{log_path}\"", exec_addr
                )

    @staticmethod
    def _get_local_ip_static(exec_addr: str) -> str:
        """静态方法获取本地 IP"""
        cmd = "ip route get 1.1.1.1 | awk '{print $7}' | head -1"
        status, result, _ = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value and result.strip():
            return result.strip()
        return "127.0.0.1"

    @classmethod
    def _stop_perftest_processes(cls, exec_addr: str, name: str) -> None:
        cmd = 'pkill -9 -f "ib_send_bw" 2>/dev/null || true'
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 ib_send_bw 进程已清理")

    @classmethod
    def _stop_iperf(cls, exec_addr: str, name: str) -> None:
        cmd = "pkill -9 -x iperf 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 iperf 进程已清理")

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-11/12/13 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc011.run()


if __name__ == '__main__':
    main()
