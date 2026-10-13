#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: TC-040
case title: 4个pf启动完全一样的rc send业务，性能数据应一致-双端口
test category: IB多PF测试
check point: 4个PF并发执行相同rc send业务，性能数据一致性（多轮采样+背景负载+标准差）
author: zhubo1
date: 2026.06.16
@steps:
    1. client和server端均先检查当前PF数量；若不等于4，则通过 mlxconfig -d mlx5_0 -y set NUM_OF_PF=4 设置PF数量为4，并重启服务器使配置生效；若已是4，则跳过设置和重启。重启后先等待约30秒让服务器进入重启流程，再通过命令输出动态检测服务器上线（超时300秒）。
    2. 通过 ibstat 分别获取两个pport（mlx5_0、mlx5_1）的Node GUID，为每个pport启动一个OpenSM实例：nohup opensm -g <GUID> -B -e -f /var/log/opensm_{i}.log > /dev/null 2>&1 &。启动后检查所有IB设备状态为Active。
    3. 启动背景负载：在server端运行CPU压力脚本，作为系统级背景压力。
    4. 在背景负载持续运行期间，对4个PF同时启动完全相同的rc send业务：server端执行 nohup ib_send_bw -d <dev> -p <port> -D {ROUND_DURATION} -b -F > log &；client端执行 ib_send_bw -d <dev> -p <port> -D {ROUND_DURATION} -b -F <server_ip> > log。共执行N轮（如10轮），每轮4个PF并发，记录每轮每个PF的带宽/耗时。
    5. 停止背景负载，汇总所有轮次的带宽数据，计算每轮的最小值、最大值、平均值以及所有轮次的标准差（std）、P95/P99分位数，确认4个PF的性能数据一致且稳定。

@expected:
    1. PF=4设置成功（如发生设置），服务器重启成功；PF数量为4。
    2. OpenSM启动成功，所有IB设备状态为Active（State: Active，Physical state: LinkUp）。
    3. 背景负载成功启动并持续运行。
    4. 每轮4个PF的rc send业务均成功执行，返回码为0，且每轮日志中均解析出有效带宽。
    5. 所有轮次中，4个PF的带宽/性能数据一致：单轮内最大最小差异不超过20%或100MB/s；多轮标准差不超过均值的15%；P95/P99与均值差异不超过30%。

@changelog:
2026.06.16 - 根据更新后的TC-040用例生成
- 使用项目技巧：PF数量相同跳过设置/重启、reboot后30秒再检测、双端口OpenSM按pport GUID启动
- 增加多轮采样（默认10轮）和背景CPU负载
- 增加标准差、P95/P99 分位数统计
- 单轮一致性与多轮稳定性双重判定
"""

import os
import time
import re
import math
import _thread
import add_syspath
from typing import List, Dict, Tuple
from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum, BugTypeEnum
from scripts.script_libs.script_base import ScriptBase, SxeException
from scripts.script_libs.common_operation import CommonOperation


class MultiPfTestTc040(ScriptBase):
    test_object = "Multi PF Test"
    test_module = "IB Multi PF Test"
    test_tool = "mlxconfig, ibstat, opensm, perftest"
    test_precondition = "天蝎网卡为双端口形态"
    test_steps = """
    1. client和server端均先检查当前PF数量；若不等于4则设置PF数量为4并重启服务器使配置生效，已是4则跳过
    2. 通过ibstat获取mlx5_0、mlx5_1的Node GUID，为每个pport启动OpenSM实例，并检查所有IB设备状态为Active
    3. 启动背景CPU负载
    4. 在背景负载下执行N轮rc send业务，每轮4个PF并发，记录每轮每个PF带宽
    5. 停止背景负载，汇总多轮数据，计算标准差、P95/P99，确认性能一致且稳定
    """

    REBOOT_WAIT_SECONDS = 30
    SERVER_AVAILABILITY_TIMEOUT = 300
    ROUND_DURATION = 10     # 每轮打流时长（秒）
    TRAFFIC_INSTANCES = 4   # 每轮并发PF数
    TRAFFIC_ROUNDS = 10     # 采样轮数
    ROUND_INTERVAL = 2      # 轮间间隔（秒）
    PORT_START = 20000      # 起始端口号

    # 一致性阈值
    ROUND_VARIANCE_THRESHOLD = 0.20     # 单轮内相对差异
    ROUND_ABS_THRESHOLD_MB = 100        # 单轮内绝对差异（MB/sec）
    STD_THRESHOLD = 0.15                # 多轮标准差 / 均值
    P95_THRESHOLD = 0.30                # P95 相对均值差异
    P99_THRESHOLD = 0.30                # P99 相对均值差异

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "MultiPfTestTc040 Failed"
        cls.test_results = {
            "total_steps": 0,
            "passed_steps": 0,
            "failures": []
        }

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 TC-040 测试环境...")
        server_driver, client_driver = CommonOperation.get_nic_driver_name()
        log.info(f"服务端驱动: {server_driver}, 客户端驱动: {client_driver}")

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client")
        ]:
            status, result, err = CommandOperation.execute_command_with_error("ibstat -l", exec_addr)
            if status != RtnStatusEnum.SUCCESS.value or not result.strip():
                log.error(f"{name} 端未找到 IB 设备")
                cls.own_environment_enabled = False
                return

        cls.own_environment_enabled = True
        log.info("环境检查通过")

    @classmethod
    def prepare(cls) -> None:
        log.info("准备 TC-040 测试环境...")
        cls.initial_pf_count_server = cls.get_pf_count(CmdExecuteAdressEnum.SERVER.value)
        cls.initial_pf_count_client = cls.get_pf_count(CmdExecuteAdressEnum.CLIENT.value)
        log.info(
            f"初始 PF 数量 - 服务端: {cls.initial_pf_count_server}, "
            f"客户端: {cls.initial_pf_count_client}"
        )

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 TC-040 测试：4个pf启动完全一样的rc send业务，性能数据应一致-双端口")
        log.info("=" * 60)

        try:
            cls.test_results["total_steps"] = 5

            # 步骤1：设置PF数量为4
            log.info("\n步骤1：设置 PF 数量为 4")
            cls.set_pf_and_reset(4)
            cls.verify_pf_count(4)
            cls.test_results["passed_steps"] += 1

            # 步骤2：启动OpenSM
            log.info("\n步骤2：启动 OpenSM 组网")
            cls.start_opensm_networking()
            cls.test_results["passed_steps"] += 1

            # 步骤3：启动背景负载
            log.info("\n步骤3：启动背景 CPU 负载")
            cls.start_background_load()
            cls.test_results["passed_steps"] += 1

            # 步骤4：多轮并发执行业务
            log.info("\n步骤4：多轮并发执行 rc send 业务")
            devices = cls.get_ib_devices(CmdExecuteAdressEnum.SERVER.value)
            if len(devices) < 4:
                cls.bug_result = f"Expected 4 IB devices, found {len(devices)}"
                cls.bug_expect = "Should have 4 IB devices for TC-040"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(cls.bug_result)

            test_devices = devices[:4]
            server_ip = cls.get_server_ip(CmdExecuteAdressEnum.SERVER.value)
            all_rounds_metrics = cls.run_traffic_multi_rounds(test_devices, server_ip)
            cls.test_results["passed_steps"] += 1

            # 步骤5：汇总统计并比较性能一致性
            log.info("\n步骤5：汇总多轮数据，计算标准差与分位数，确认一致性")
            cls.compare_performance_statistics(all_rounds_metrics)
            cls.test_results["passed_steps"] += 1

            cls.print_test_summary()
            log.info("测试执行成功 - TC-040 通过")
        except SxeException:
            cls.print_test_summary()
            raise
        except Exception as e:
            cls.print_test_summary()
            log.error(f"TC-040 测试失败（未预期错误）: {e}")
            raise

    @classmethod
    def get_pf_count(cls, exec_addr: str) -> int:
        lspci_cmd = "lspci | grep -i mellanox | wc -l"
        status, result, err = CommandOperation.execute_command_with_error(lspci_cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value:
            try:
                return int(result.strip())
            except ValueError:
                return 0
        return 0

    @classmethod
    def set_pf_and_reset(cls, pf_count: int) -> None:
        log.info(f"设置 PF 数量为 {pf_count} ...")
        need_reboot = False

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client")
        ]:
            current_pf = cls.get_pf_count(exec_addr)
            if current_pf == pf_count:
                log.info(f"{name} 端 PF 数量已经是 {pf_count}，跳过设置")
                continue

            mlxconfig_cmd = f"mlxconfig -d mlx5_0 -y set NUM_OF_PF={pf_count}"
            status, result, err = CommandOperation.execute_command_with_error(mlxconfig_cmd, exec_addr)
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"Failed to set PF count to {pf_count} on {name}: {err}"
                cls.bug_expect = "mlxconfig command should succeed with return code 0"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"mlxconfig command failed on {name}: {err}")
            log.info(f"在 {name} 端成功设置 PF 数量为 {pf_count}")
            need_reboot = True

        if need_reboot:
            cls.reboot_servers_for_pf_changes()
        else:
            log.info("配置未变更，跳过重启")

    @classmethod
    def reboot_servers_for_pf_changes(cls) -> None:
        log.info("重启服务器以应用 PF 数量变更...")

        for exec_addr, name in [
            (CmdExecuteAdressEnum.CLIENT.value, "client"),
            (CmdExecuteAdressEnum.SERVER.value, "server")
        ]:
            log.info(f"正在重启 {name} 服务器...")
            reboot_cmd = "nohup sh -c 'sleep 2 && reboot' > /dev/null 2>&1 &"
            CommandOperation.execute_command_with_error(reboot_cmd, exec_addr)

        log.info(f"等待服务器开始重启（{cls.REBOOT_WAIT_SECONDS} 秒）...")
        time.sleep(cls.REBOOT_WAIT_SECONDS)

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client")
        ]:
            if not cls.wait_for_server_availability(exec_addr, timeout=cls.SERVER_AVAILABILITY_TIMEOUT):
                cls.bug_result = f"Server {name} did not become available after reboot"
                cls.bug_expect = "Server should be available within 300 seconds"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"Server {name} unavailable after reboot")

        time.sleep(15)
        log.info("服务器重启后已就绪")

    @classmethod
    def wait_for_server_availability(cls, server_address: str, timeout: int = 300) -> bool:
        log.info(f"等待服务器 {server_address} 可用（超时: {timeout}秒）")

        start_time = time.time()
        while time.time() - start_time < timeout:
            status, result, err = CommandOperation.execute_command_with_error("echo ping", server_address)
            if status == RtnStatusEnum.SUCCESS.value and result and "ping" in result.strip():
                log.info(f"服务器 {server_address} 已可用（已通过命令输出验证）")
                return True
            time.sleep(5)

        log.error(f"等待服务器 {server_address} 超时")
        return False

    @classmethod
    def verify_pf_count(cls, expected_pf_count: int) -> None:
        log.info(f"验证 PF 数量是否为 {expected_pf_count} ...")

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client")
        ]:
            ibstat_cmd = "ibstat -l | wc -l"
            status, result, err = CommandOperation.execute_command_with_error(ibstat_cmd, exec_addr)
            if status != RtnStatusEnum.SUCCESS.value:
                cls._bug_and_raise(f"ibstat -l failed on {name}: {err}")

            try:
                actual_ibstat = int(result.strip())
            except ValueError:
                cls._bug_and_raise(f"Could not parse ibstat result on {name}: {result}")

            lspci_cmd = "lspci | grep -i mellanox | wc -l"
            status, result, err = CommandOperation.execute_command_with_error(lspci_cmd, exec_addr)
            if status != RtnStatusEnum.SUCCESS.value:
                cls._bug_and_raise(f"lspci failed on {name}: {err}")

            try:
                actual_lspci = int(result.strip())
            except ValueError:
                cls._bug_and_raise(f"Could not parse lspci result on {name}: {result}")

            log.info(f"{name} 端 ibstat={actual_ibstat}, lspci={actual_lspci}")

            if actual_ibstat != expected_pf_count or actual_lspci != expected_pf_count:
                cls.bug_result = (
                    f"PF count mismatch on {name}: expected {expected_pf_count}, "
                    f"ibstat={actual_ibstat}, lspci={actual_lspci}"
                )
                cls.bug_expect = f"PF count should be {expected_pf_count}"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(cls.bug_result)

        log.info(f"PF 数量验证通过: {expected_pf_count}")

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "Command should succeed and return parseable output"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)

    @classmethod
    def get_ib_devices(cls, exec_addr: str) -> List[str]:
        status, result, err = CommandOperation.execute_command_with_error("ibstat -l", exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            return []
        return [line.strip() for line in result.split('\n') if line.strip()]

    @classmethod
    def get_pport_guids(cls, exec_addr: str, pport_devices: List[str]) -> List[str]:
        guids = []
        for device in pport_devices:
            if not device:
                continue
            ibstat_cmd = f"ibstat {device}"
            status, result, err = CommandOperation.execute_command_with_error(ibstat_cmd, exec_addr)
            if status == RtnStatusEnum.SUCCESS.value:
                for line in result.split('\n'):
                    if "Node GUID:" in line:
                        guid = line.split("Node GUID:")[1].strip()
                        if guid:
                            if not guid.startswith('0x'):
                                guid = '0x' + guid
                            guids.append(guid)
                        break
        return guids

    @classmethod
    def start_opensm_networking(cls) -> None:
        log.info("启动 OpenSM 组网...")

        kill_cmd = "pkill -9 -f opensm 2>/dev/null || true"
        CommandOperation.execute_command_with_error(kill_cmd, CmdExecuteAdressEnum.SERVER.value)
        time.sleep(2)

        devices = cls.get_ib_devices(CmdExecuteAdressEnum.SERVER.value)
        if not devices:
            cls.bug_result = "No IB devices found for opensm networking"
            cls.bug_expect = "Should have at least one IB device"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("No IB devices available for opensm")

        pport_guids = cls.get_pport_guids(CmdExecuteAdressEnum.SERVER.value, devices[:2])
        if not pport_guids:
            cls.bug_result = "Could not get pport GUIDs for opensm"
            cls.bug_expect = "Should be able to get Node GUID from pport devices"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("Failed to get pport GUIDs")

        for i, guid in enumerate(pport_guids):
            log.info(f"为 pport {i+1} 启动 OpenSM，GUID: {guid}")
            opensm_cmd = (
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_{i}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, CmdExecuteAdressEnum.SERVER.value
            )
            if status != RtnStatusEnum.SUCCESS.value:
                log.warning(f"OpenSM 可能未正常启动（GUID: {guid}）: {err}")
            time.sleep(3)

        time.sleep(10)
        cls.check_ib_device_status()
        log.info("OpenSM 启动成功")

    @classmethod
    def check_ib_device_status(cls) -> None:
        log.info("检查 IB 设备状态...")

        devices = cls.get_ib_devices(CmdExecuteAdressEnum.SERVER.value)
        if not devices:
            cls.bug_result = "No IB devices found during status check"
            cls.bug_expect = "Should have IB devices available"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("No IB devices found")

        for device in devices:
            ibstat_cmd = f"ibstat {device}"
            status, result, err = CommandOperation.execute_command_with_error(
                ibstat_cmd, CmdExecuteAdressEnum.SERVER.value
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"Could not get status for device {device}: {err}"
                cls.bug_expect = "ibstat should succeed for all devices"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"ibstat failed for {device}")

            if "State: Active" not in result or "Physical state: LinkUp" not in result:
                cls.bug_result = f"Device {device} is not Active/LinkUp. Output: {result}"
                cls.bug_expect = "All devices should be in Active state after opensm starts"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"Device {device} not Active")

        log.info(f"所有 {len(devices)} 个 IB 设备均处于 Active/LinkUp 状态")

    @classmethod
    def get_server_ip(cls, exec_addr: str) -> str:
        ip_cmd = "ip route get 1.1.1.1 | awk '{print $7}' | head -1"
        status, result, err = CommandOperation.execute_command_with_error(ip_cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value and result.strip():
            return result.strip()

        ip_cmd = "ip -4 addr show | grep inet | grep -v '127.0.0.1' | head -1 | awk '{print $2}' | cut -d/ -f1"
        status, result, err = CommandOperation.execute_command_with_error(ip_cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value and result.strip():
            return result.strip()

        cls.bug_result = "Failed to get server IP address"
        cls.bug_expect = "Should be able to get server IP for perftest client connection"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(cls.bug_result)

    @classmethod
    def start_background_load(cls) -> None:
        log.info("启动背景 CPU 负载...")
        # 使用简单的 shell 循环产生 CPU 压力，不依赖 stress-ng
        cpu_load_cmd = (
            "nohup sh -c 'while true; do echo $(($(cat /proc/uptime | awk '{print $1}' | cut -d. -f1) % 2)); done' "
            "> /tmp/cpu_load.log 2>&1 &"
        )
        status, result, err = CommandOperation.execute_command_with_error(
            cpu_load_cmd, CmdExecuteAdressEnum.SERVER.value
        )
        if status != RtnStatusEnum.SUCCESS.value:
            log.warning(f"背景 CPU 负载启动可能异常: {err}")
        else:
            log.info("背景 CPU 负载已启动")

    @classmethod
    def stop_background_load(cls) -> None:
        log.info("停止背景 CPU 负载...")
        kill_cmd = "pkill -9 -f 'while true; do echo' 2>/dev/null || true"
        CommandOperation.execute_command_with_error(kill_cmd, CmdExecuteAdressEnum.SERVER.value)
        cleanup_cmd = "rm -f /tmp/cpu_load.log 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cleanup_cmd, CmdExecuteAdressEnum.SERVER.value)
        log.info("背景 CPU 负载已停止")

    @classmethod
    def run_traffic_multi_rounds(cls, devices: List[str], server_ip: str) -> List[List[Dict]]:
        log.info(
            f"开始执行 {cls.TRAFFIC_ROUNDS} 轮 ib_send_bw 测试，"
            f"每轮 {cls.TRAFFIC_INSTANCES} 个 PF 并发"
        )

        all_rounds = []
        for round_idx in range(cls.TRAFFIC_ROUNDS):
            log.info(f"\n第 {round_idx + 1}/{cls.TRAFFIC_ROUNDS} 轮 ib_send_bw 开始")
            metrics = cls.run_traffic_one_round(devices, server_ip, round_idx)
            all_rounds.append(metrics)

            bandwidths = [(m.get("server_bandwidth", 0) or m.get("client_bandwidth", 0)) for m in metrics if (m.get("server_bandwidth", 0) or m.get("client_bandwidth", 0)) > 0]
            if bandwidths:
                log.info(
                    f"第 {round_idx + 1} 轮完成，带宽统计: "
                    f"min={min(bandwidths):.2f}MB/s, "
                    f"max={max(bandwidths):.2f}MB/s, "
                    f"avg={sum(bandwidths)/len(bandwidths):.2f}MB/s"
                )

            if round_idx < cls.TRAFFIC_ROUNDS - 1:
                time.sleep(cls.ROUND_INTERVAL)

        return all_rounds

    @classmethod
    def run_traffic_one_round(cls, devices: List[str], server_ip: str, round_idx: int) -> List[Dict]:
        results = []
        completed = [0]
        lock = _thread.allocate_lock()

        # 启动 server
        for idx, device in enumerate(devices):
            port = cls.PORT_START + round_idx * 100 + idx
            server_log = f"/tmp/ib_send_bw_server_{device}_r{round_idx}.log"
            server_cmd = (
                f"nohup ib_send_bw -d {device} -p {port} -D {cls.ROUND_DURATION} -b -F "
                f"> {server_log} 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                server_cmd, CmdExecuteAdressEnum.SERVER.value
            )
            if status != RtnStatusEnum.SUCCESS.value:
                log.warning(f"设备 {device} 第 {round_idx} 轮 server 启动可能异常: {err}")

        time.sleep(3)

        # 并发启动 client
        for idx, device in enumerate(devices):
            port = cls.PORT_START + round_idx * 100 + idx
            client_log = f"/tmp/ib_send_bw_client_{device}_r{round_idx}.log"
            client_cmd = (
                f"ib_send_bw -d {device} -p {port} -D {cls.ROUND_DURATION} -b -F {server_ip} "
                f"> {client_log} 2>&1"
            )
            _thread.start_new_thread(
                cls._traffic_client_thread_entry,
                (device, round_idx, client_cmd, client_log, results, completed, lock)
            )

        timeout = cls.ROUND_DURATION + 60
        start_time = time.time()
        while completed[0] < len(devices):
            if time.time() - start_time > timeout:
                log.error(f"等待 ib_send_bw client 线程超时: {completed[0]}/{len(devices)}")
                break
            time.sleep(0.5)

        # 读取 server 端日志
        for idx, device in enumerate(devices):
            server_log = f"/tmp/ib_send_bw_server_{device}_r{round_idx}.log"
            status, output, err = CommandOperation.execute_command_with_error(
                f"cat {server_log}", CmdExecuteAdressEnum.SERVER.value
            )
            for res in results:
                if res["device"] == device and res["round"] == round_idx:
                    res["server_output"] = output if output else ""
                    res["server_bandwidth"] = cls.parse_bandwidth_from_output(output)
                    break

        results.sort(key=lambda x: x.get("device", ""))
        return results

    @staticmethod
    def _traffic_client_thread_entry(device: str, round_idx: int, client_cmd: str,
                                     client_log: str, results: List[Dict],
                                     completed: List[int], lock) -> None:
        start_time = time.time()
        status, result, err = CommandOperation.execute_command_with_error(
            client_cmd, CmdExecuteAdressEnum.CLIENT.value,
            timeout=MultiPfTestTc040.ROUND_DURATION + 30
        )
        elapsed_ms = (time.time() - start_time) * 1000

        res = {
            "round": round_idx,
            "device": device,
            "cmd": client_cmd,
            "status": status,
            "client_output": result if result else "",
            "client_error": err if err else "",
            "client_log": client_log,
            "client_bandwidth": MultiPfTestTc040.parse_bandwidth_from_output(result),
            "elapsed_ms": elapsed_ms
        }

        with lock:
            results.append(res)
            completed[0] += 1

    @classmethod
    def compare_performance_statistics(cls, all_rounds: List[List[Dict]]) -> None:
        total_instances = cls.TRAFFIC_ROUNDS * cls.TRAFFIC_INSTANCES
        all_metrics = [m for round_metrics in all_rounds for m in round_metrics]

        if len(all_metrics) < total_instances:
            cls.bug_result = (
                f"Only {len(all_metrics)} traffic results collected, expected {total_instances}"
            )
            cls.bug_expect = "Should collect all traffic results"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)

        # 使用 server 带宽（若解析失败则使用 client 带宽）
        for m in all_metrics:
            m["bandwidth"] = m.get("server_bandwidth", 0) or m.get("client_bandwidth", 0)

        failed_devices = []
        for m in all_metrics:
            if m["status"] != RtnStatusEnum.SUCCESS.value or m["bandwidth"] <= 0:
                failed_devices.append(f"round={m['round']},device={m['device']}")
                log.error(f"PF {m['device']} 第 {m['round']} 轮 ib_send_bw 失败或带宽无效")

        if failed_devices:
            cls.bug_result = f"ib_send_bw failed on: {', '.join(failed_devices)}"
            cls.bug_expect = "All traffic flows should succeed with valid bandwidth"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)

        log.info("=" * 60)
        log.info(f"单轮 ib_send_bw 一致性统计")
        log.info("=" * 60)

        round_failures = []
        for round_idx, metrics in enumerate(all_rounds):
            bandwidths = [(m.get("server_bandwidth", 0) or m.get("client_bandwidth", 0)) for m in metrics if (m.get("server_bandwidth", 0) or m.get("client_bandwidth", 0)) > 0]
            if not bandwidths:
                round_failures.append(f"round {round_idx + 1}: no valid bandwidth")
                continue
            min_bw = min(bandwidths)
            max_bw = max(bandwidths)
            avg_bw = sum(bandwidths) / len(bandwidths)
            variance = (max_bw - min_bw) / avg_bw if avg_bw > 0 else 0.0
            abs_diff = max_bw - min_bw

            log.info(
                f"第 {round_idx + 1} 轮: min={min_bw:.2f}MB/s, max={max_bw:.2f}MB/s, "
                f"avg={avg_bw:.2f}MB/s, variance={variance*100:.2f}%, abs_diff={abs_diff:.2f}MB/s"
            )

            if variance > cls.ROUND_VARIANCE_THRESHOLD and abs_diff > cls.ROUND_ABS_THRESHOLD_MB:
                round_failures.append(
                    f"round {round_idx + 1}: variance={variance*100:.2f}%, abs_diff={abs_diff:.2f}MB/s"
                )

        if round_failures:
            cls.bug_result = f"Single-round consistency check failed: {'; '.join(round_failures)}"
            cls.bug_expect = (
                f"Each round should have consistent bandwidth "
                f"(variance <= {cls.ROUND_VARIANCE_THRESHOLD*100}% "
                f"or abs diff <= {cls.ROUND_ABS_THRESHOLD_MB}MB/s)"
            )
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)

        log.info("=" * 60)
        log.info(f"多轮 ib_send_bw 稳定性统计")
        log.info("=" * 60)

        all_bandwidths = [m["bandwidth"] for m in all_metrics if m["bandwidth"] > 0]
        min_bw = min(all_bandwidths)
        max_bw = max(all_bandwidths)
        avg_bw = sum(all_bandwidths) / len(all_bandwidths)
        std = cls._calculate_std(all_bandwidths, avg_bw)
        p95 = cls._calculate_percentile(all_bandwidths, 95)
        p99 = cls._calculate_percentile(all_bandwidths, 99)

        std_ratio = std / avg_bw if avg_bw > 0 else 0.0
        p95_ratio = abs(p95 - avg_bw) / avg_bw if avg_bw > 0 else 0.0
        p99_ratio = abs(p99 - avg_bw) / avg_bw if avg_bw > 0 else 0.0

        log.info(f"样本总数: {len(all_bandwidths)}")
        log.info(f"最小带宽: {min_bw:.2f} MB/s")
        log.info(f"最大带宽: {max_bw:.2f} MB/s")
        log.info(f"平均带宽: {avg_bw:.2f} MB/s")
        log.info(f"标准差: {std:.2f} MB/s (std/avg={std_ratio*100:.2f}%)")
        log.info(f"P95: {p95:.2f} MB/s (diff/avg={p95_ratio*100:.2f}%)")
        log.info(f"P99: {p99:.2f} MB/s (diff/avg={p99_ratio*100:.2f}%)")
        log.info("=" * 60)

        stability_failures = []
        if std_ratio > cls.STD_THRESHOLD:
            stability_failures.append(f"std/avg={std_ratio*100:.2f}% > {cls.STD_THRESHOLD*100}%")
        if p95_ratio > cls.P95_THRESHOLD:
            stability_failures.append(f"p95 diff/avg={p95_ratio*100:.2f}% > {cls.P95_THRESHOLD*100}%")
        if p99_ratio > cls.P99_THRESHOLD:
            stability_failures.append(f"p99 diff/avg={p99_ratio*100:.2f}% > {cls.P99_THRESHOLD*100}%")

        if stability_failures:
            cls.bug_result = f"Multi-round stability check failed: {'; '.join(stability_failures)}"
            cls.bug_expect = (
                f"Multi-round bandwidth should be stable "
                f"(std/avg <= {cls.STD_THRESHOLD*100}%, "
                f"p95 diff <= {cls.P95_THRESHOLD*100}%, "
                f"p99 diff <= {cls.P99_THRESHOLD*100}%)"
            )
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)

        log.info("单轮一致性与多轮稳定性检查均通过")

    @staticmethod
    def parse_bandwidth_from_output(output: str) -> float:
        if not output:
            return 0.0
        pattern = re.compile(
            r'^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s*$',
            re.MULTILINE
        )
        matches = pattern.findall(output)
        if not matches:
            return 0.0
        try:
            if len(matches) == 1:
                return float(matches[0][3])
            recent_matches = matches[-11:-1]
            return sum(float(m[3]) for m in recent_matches) / len(recent_matches)
        except (ValueError, IndexError):
            return 0.0

    @staticmethod
    def _calculate_std(values: List[float], mean: float) -> float:
        if len(values) < 2:
            return 0.0
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)

    @staticmethod
    def _calculate_percentile(values: List[float], percentile: int) -> float:
        if not values:
            return 0.0
        sorted_values = sorted(values)
        k = (len(sorted_values) - 1) * (percentile / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_values[int(k)]
        d0 = sorted_values[int(f)] * (c - k)
        d1 = sorted_values[int(c)] * (k - f)
        return d0 + d1

    @classmethod
    def print_test_summary(cls) -> None:
        total = cls.test_results["total_steps"]
        passed = cls.test_results["passed_steps"]
        failed = total - passed
        log.info("=" * 60)
        log.info("测试执行结果摘要")
        log.info("=" * 60)
        log.info(f"总步骤: {total}")
        log.info(f"通过: {passed}")
        log.info(f"失败: {failed}")
        if cls.test_results["failures"]:
            log.info("失败步骤:")
            for failure in cls.test_results["failures"]:
                log.info(f"  - {failure}")
        log.info("=" * 60)
        log.info(f"测试结果: {'通过' if failed == 0 else '失败'}")
        log.info("=" * 60)

    @classmethod
    def restore_pf_count(cls) -> None:
        if not hasattr(cls, 'initial_pf_count_server') or not hasattr(cls, 'initial_pf_count_client'):
            return
        if cls.initial_pf_count_server <= 0 or cls.initial_pf_count_client <= 0:
            return

        current_server = cls.get_pf_count(CmdExecuteAdressEnum.SERVER.value)
        current_client = cls.get_pf_count(CmdExecuteAdressEnum.CLIENT.value)
        need_restore = False

        if current_server != cls.initial_pf_count_server:
            log.info(f"将服务端 PF 数量从 {current_server} 恢复为 {cls.initial_pf_count_server}")
            mlxconfig_cmd = f"mlxconfig -d mlx5_0 -y set NUM_OF_PF={cls.initial_pf_count_server}"
            status, result, err = CommandOperation.execute_command_with_error(
                mlxconfig_cmd, CmdExecuteAdressEnum.SERVER.value
            )
            if status != RtnStatusEnum.SUCCESS.value:
                log.error(f"恢复服务端 PF 数量失败: {err}")
                cls.test_results["failures"].append("恢复server PF数量失败")
            else:
                need_restore = True

        if current_client != cls.initial_pf_count_client:
            log.info(f"将客户端 PF 数量从 {current_client} 恢复为 {cls.initial_pf_count_client}")
            mlxconfig_cmd = f"mlxconfig -d mlx5_0 -y set NUM_OF_PF={cls.initial_pf_count_client}"
            status, result, err = CommandOperation.execute_command_with_error(
                mlxconfig_cmd, CmdExecuteAdressEnum.CLIENT.value
            )
            if status != RtnStatusEnum.SUCCESS.value:
                log.error(f"恢复客户端 PF 数量失败: {err}")
                cls.test_results["failures"].append("恢复client PF数量失败")
            else:
                need_restore = True

        if need_restore:
            log.info("重启服务器以恢复 PF 数量...")
            cls.reboot_servers_for_pf_changes()

    @classmethod
    def post(cls) -> None:
        log.info("清理测试环境...")

        cls.stop_background_load()

        kill_tool_cmd = f"pkill -9 -f 'ib_send_bw' 2>/dev/null || true"
        CommandOperation.execute_command_with_error(kill_tool_cmd, CmdExecuteAdressEnum.SERVER.value)
        CommandOperation.execute_command_with_error(kill_tool_cmd, CmdExecuteAdressEnum.CLIENT.value)

        kill_opensm_cmd = "pkill -9 -f opensm 2>/dev/null || true"
        CommandOperation.execute_command_with_error(kill_opensm_cmd, CmdExecuteAdressEnum.SERVER.value)

        cleanup_cmd = f"rm -f /var/log/opensm_*.log /tmp/ib_send_bw_*.log /tmp/cpu_load.log 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cleanup_cmd, CmdExecuteAdressEnum.SERVER.value)
        CommandOperation.execute_command_with_error(cleanup_cmd, CmdExecuteAdressEnum.CLIENT.value)

        cls.restore_pf_count()
        log.info("清理完成")


def main() -> None:
    MultiPfTestTc040.run()


if __name__ == '__main__':
    main()
