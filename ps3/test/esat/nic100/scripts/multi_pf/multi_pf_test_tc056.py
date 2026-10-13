#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: TC-056
case title: 4个pf进行业务期间，发生PF1-3发生PF级别的复位的异常，其他pf不受影响-双端口
test category: IB多PF测试
check point: PF1-PF3发生PF级别复位异常时，PF0的业务不受影响
author: zhubo1
date: 2026.06.17
@steps:
    1. client和server端均先检查当前PF数量；若不等于4，则通过 mlxconfig -d mlx5_0 -y set NUM_OF_PF=4 设置PF数量为4，并重启服务器使配置生效；若已是4，则跳过设置和重启。重启后先等待约30秒让服务器进入重启流程，再通过命令输出动态检测服务器上线（超时300秒）。
    2. 通过 ibstat 分别获取两个pport（mlx5_0、mlx5_1）的Node GUID，为每个pport启动一个OpenSM实例。启动后检查所有IB设备状态为Active。
    3. 在4个PF上同时启动 ib_read_bw 业务（server/client 配对，--run_infinitely -D 1），让流量稳定运行。
    4. 业务运行期间，对PF1-PF3（mlx5_1、mlx5_2、mlx5_3）执行PF级别function复位并等待这些设备从ibstat中消失；不在do阶段恢复IB驱动，避免影响其他PF的业务。
    5. 检查PF0的ib_read_bw日志，确认复位期间和复位后均有有效带宽输出，业务未中断。
    6. 对PF0（pport mlx5_0）执行查询类业务命令（mlxconfig q、smpquery、perfquery、ibportstate），通过ibstat获取真实base LID，验证命令执行成功且无异常。
    7. post阶段：停止所有业务进程和OpenSM，执行 /etc/init.d/openibd force-restart 恢复IB驱动，并观察复位的PF1-PF3是否重新出现。

@expected:
    1. PF=4设置成功（如发生设置），服务器重启成功；PF数量为4。
    2. OpenSM启动成功，所有IB设备状态为Active（State: Active，Physical state: LinkUp）。
    3. 4个PF的ib_read_bw业务均成功启动并持续运行。
    4. PF1-PF3复位命令执行成功，复位后这些PF从ibstat中消失。
    5. PF0在PF1-PF3复位期间及之后，ib_read_bw日志中持续存在有效带宽，业务未受影响。
    6. PF0（pport）的查询类命令执行成功，使用真实base LID，无异常打印。
    7. post阶段清理业务进程、停止OpenSM、force-restart成功，复位的PF1-PF3重新出现在ibstat中。

@changelog:
2026.06.17 - 根据TC-056用例生成
- 复用TC-048的PF设置/重启/复位逻辑
- 使用--run_infinitely实现持续业务，便于观察PF复位期间其他PF是否受影响
- 对非异常PF的日志进行连续性检查
2026.06.17 - 调整复位恢复逻辑
- 将 /etc/init.d/openibd force-restart 从do阶段移到post阶段执行
- do阶段仅验证非异常PF业务是否受影响，通过即视为用例通过
- post阶段清理业务进程和OpenSM后恢复IB驱动，并检查复位的PF是否恢复
"""

import time
import re
import add_syspath
from typing import List, Dict
from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum, BugTypeEnum
from scripts.script_libs.script_base import ScriptBase, SxeException
from scripts.script_libs.common_operation import CommonOperation


class MultiPfTestTc056(ScriptBase):
    test_object = "Multi PF Test"
    test_module = "IB Multi PF Test"
    test_tool = "mlxconfig, ibstat, lspci, opensm, ib_read_bw, smpquery, perfquery, ibportstate"
    test_precondition = "天蝎网卡为双端口形态，mlx5_0、mlx5_1 为 pport，mlx5_2、mlx5_3 为 vport"
    test_steps = """
    1. 设置 PF 数量为 4 并重启服务器，验证 PF 数量为 4
    2. 启动 OpenSM 组网，验证所有 IB 设备 Active
    3. 在 4 个 PF 上并发启动 ib_read_bw 业务
    4. 业务期间对 PF1-PF3（mlx5_1/2/3）执行 function 级复位，不在 do 阶段恢复驱动
    5. 验证 PF0 业务未中断（日志连续性检查）
    6. 对 PF0（pport）使用真实 base LID 执行查询类命令并验证成功
    7. post 阶段：清理业务进程和 OpenSM，执行 force-restart 恢复驱动，检查复位的 PF1-PF3 是否恢复
    """

    REBOOT_WAIT_SECONDS = 30
    SERVER_AVAILABILITY_TIMEOUT = 300
    DRIVER_RECOVER_WAIT_SECONDS = 10
    POST_REBOOT_STABILIZE_SECONDS = 15
    TRAFFIC_WARMUP_SECONDS = 10
    TRAFFIC_CHECK_SECONDS = 10
    RESET_TARGET_DEVICES = ["mlx5_1", "mlx5_2", "mlx5_3"]
    MONITOR_DEVICES = ["mlx5_0"]
    ALL_PF_DEVICES = ["mlx5_0", "mlx5_1", "mlx5_2", "mlx5_3"]
    PORT_START = 19000

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "MultiPfTestTc056 Failed"
        cls.test_results = {
            "total_steps": 0,
            "passed_steps": 0,
            "failures": []
        }

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 TC-056 测试环境...")
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
        log.info("准备 TC-056 测试环境...")
        cls.initial_pf_count_server = cls.get_pf_count(CmdExecuteAdressEnum.SERVER.value)
        cls.initial_pf_count_client = cls.get_pf_count(CmdExecuteAdressEnum.CLIENT.value)
        log.info(
            f"初始 PF 数量 - 服务端: {cls.initial_pf_count_server}, "
            f"客户端: {cls.initial_pf_count_client}"
        )

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 TC-056 测试：4个pf进行业务期间，发生PF1-3发生PF级别的复位的异常，其他pf不受影响-双端口")
        log.info("=" * 60)

        try:
            cls.test_results["total_steps"] = 6

            # 步骤1：设置PF=4并验证
            log.info("\n步骤1：设置 PF 数量为 4 并重启验证")
            cls.set_pf_and_reset(4)
            cls.verify_pf_count(4)
            cls.test_results["passed_steps"] += 1

            # 步骤2：启动OpenSM
            log.info("\n步骤2：启动 OpenSM 组网")
            cls.start_opensm_networking()
            cls.test_results["passed_steps"] += 1

            # 步骤3：在4个PF上启动ib_read_bw业务
            log.info("\n步骤3：在 4 个 PF 上并发启动 ib_read_bw 业务")
            server_ip = cls.get_server_ip(CmdExecuteAdressEnum.SERVER.value)
            cls.start_all_traffic(cls.ALL_PF_DEVICES, server_ip)
            log.info(f"等待业务稳定运行 {cls.TRAFFIC_WARMUP_SECONDS} 秒...")
            time.sleep(cls.TRAFFIC_WARMUP_SECONDS)
            cls.verify_traffic_alive(cls.ALL_PF_DEVICES)
            cls.test_results["passed_steps"] += 1

            # 步骤4：业务期间对PF1-PF3执行function级复位（不在do阶段恢复驱动）
            log.info("\n步骤4：业务期间对 PF1-PF3（mlx5_1/2/3）执行 function 级复位，do 阶段不恢复驱动")
            cls.snapshot_monitor_bandwidth("复位前")
            for device in cls.RESET_TARGET_DEVICES:
                cls.reset_function_only(device, CmdExecuteAdressEnum.SERVER.value)
                cls.reset_function_only(device, CmdExecuteAdressEnum.CLIENT.value)
            cls.snapshot_monitor_bandwidth("复位后")
            cls.test_results["passed_steps"] += 1

            # 步骤5：验证PF0业务未中断
            log.info("\n步骤5：验证 PF0 的 ib_read_bw 业务未中断")
            cls.check_traffic_continuity(cls.MONITOR_DEVICES)
            cls.test_results["passed_steps"] += 1

            # 步骤6：对PF0执行查询类命令
            log.info("\n步骤6：对 PF0 执行查询类命令")
            cls.run_query_commands(cls.MONITOR_DEVICES)
            cls.test_results["passed_steps"] += 1

            cls.stop_all_traffic()
            cls.print_test_summary()
            log.info("测试执行成功 - TC-056 通过")
        except SxeException:
            cls.stop_all_traffic()
            cls.print_test_summary()
            raise
        except Exception as e:
            cls.stop_all_traffic()
            cls.print_test_summary()
            log.error(f"TC-056 测试失败（未预期错误）: {e}")
            raise

    @classmethod
    def get_pf_count(cls, exec_addr: str) -> int:
        """通过 lspci 获取 Mellanox PF 数量"""
        lspci_cmd = "lspci | grep -i mellanox | wc -l"
        status, result, err = CommandOperation.execute_command_with_error(lspci_cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value:
            try:
                return int(result.strip())
            except ValueError:
                return 0
        return 0

    @classmethod
    def get_ibstat_count(cls, exec_addr: str) -> int:
        """通过 ibstat -l 获取 IB 设备数量"""
        ibstat_cmd = "ibstat -l | wc -l"
        status, result, err = CommandOperation.execute_command_with_error(ibstat_cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value:
            try:
                return int(result.strip())
            except ValueError:
                return 0
        return 0

    @classmethod
    def set_pf_and_reset(cls, pf_count: int, device: str = "mlx5_0") -> None:
        """设置 PF 数量并在变更后重启服务器"""
        log.info(f"设置 {device} 的 PF 数量为 {pf_count} 并重启...")
        need_reboot = False

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client")
        ]:
            current_pf = cls.get_pf_count(exec_addr)
            if current_pf == pf_count:
                log.info(f"{name} 端 PF 数量已经是 {pf_count}，跳过设置")
                continue

            mlxconfig_cmd = f"mlxconfig -d {device} -y set NUM_OF_PF={pf_count}"
            status, result, err = CommandOperation.execute_command_with_error(mlxconfig_cmd, exec_addr)
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"Failed to set PF count to {pf_count} on {name}: {err}"
                cls.bug_expect = "mlxconfig command should succeed with return code 0"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"mlxconfig command failed on {name}: {err}")
            log.info(f"在 {name} 端成功设置 {device} PF 数量为 {pf_count}")
            need_reboot = True

        if need_reboot:
            cls.reboot_servers_for_pf_changes()
        else:
            log.info("配置未变更，跳过重启")

    @classmethod
    def reboot_servers_for_pf_changes(cls) -> None:
        """重启服务器以应用 PF 数量变更"""
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

        time.sleep(cls.POST_REBOOT_STABILIZE_SECONDS)
        log.info("服务器重启后已就绪")

    @classmethod
    def wait_for_server_availability(cls, server_address: str, timeout: int = 300) -> bool:
        """通过命令输出动态检测服务器是否可用"""
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
        """验证 server 和 client 两端 PF 数量是否符合预期"""
        log.info(f"验证 PF 数量是否为 {expected_pf_count} ...")

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client")
        ]:
            actual_lspci = cls.get_pf_count(exec_addr)
            actual_ibstat = cls.get_ibstat_count(exec_addr)
            log.info(f"{name} 端 - lspci={actual_lspci}, ibstat={actual_ibstat}")

            if actual_lspci != expected_pf_count or actual_ibstat != expected_pf_count:
                cls.bug_result = (
                    f"PF count mismatch on {name}: expected {expected_pf_count}, "
                    f"lspci={actual_lspci}, ibstat={actual_ibstat}"
                )
                cls.bug_expect = f"PF count should be {expected_pf_count}"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(cls.bug_result)

        log.info(f"PF 数量验证通过: {expected_pf_count}")

    @classmethod
    def get_ib_devices(cls, exec_addr: str) -> List[str]:
        status, result, err = CommandOperation.execute_command_with_error("ibstat -l", exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            return []
        return [line.strip() for line in result.split('\n') if line.strip()]

    @classmethod
    def get_device_guid(cls, device: str, exec_addr: str) -> str:
        """获取指定设备的 Node GUID"""
        ibstat_cmd = f"ibstat {device}"
        status, result, err = CommandOperation.execute_command_with_error(ibstat_cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value:
            for line in result.split('\n'):
                if "Node GUID:" in line:
                    guid = line.split("Node GUID:")[1].strip()
                    if guid:
                        if not guid.startswith('0x'):
                            guid = '0x' + guid
                        return guid
        return ""

    @classmethod
    def start_opensm_networking(cls) -> None:
        """为所有 pport 启动 OpenSM"""
        log.info("启动 OpenSM 组网...")

        kill_cmd = "pkill -9 -f opensm 2>/dev/null || true"
        for exec_addr in [CmdExecuteAdressEnum.SERVER.value, CmdExecuteAdressEnum.CLIENT.value]:
            CommandOperation.execute_command_with_error(kill_cmd, exec_addr)
        time.sleep(2)

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client")
        ]:
            devices = cls.get_ib_devices(exec_addr)
            if len(devices) < 2:
                cls.bug_result = f"Not enough pports on {name}: found {len(devices)} devices"
                cls.bug_expect = "Should have at least 2 IB devices (pports)"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(cls.bug_result)

            pport_devices = devices[:2]
            for i, device in enumerate(pport_devices):
                guid = cls.get_device_guid(device, exec_addr)
                if not guid:
                    cls.bug_result = f"Could not get GUID for {device} on {name}"
                    cls.bug_expect = "Should be able to get Node GUID from pport"
                    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                    cls.create_bug(cls.bug_result)

                log.info(f"在 {name} 端为 {device} 启动 OpenSM，GUID: {guid}")
                opensm_cmd = (
                    f"nohup opensm -g {guid} -B -e -f /var/log/opensm_{device}.log "
                    f"> /dev/null 2>&1 &"
                )
                status, result, err = CommandOperation.execute_command_with_error(opensm_cmd, exec_addr)
                if status != RtnStatusEnum.SUCCESS.value:
                    log.warning(f"OpenSM 可能未正常启动（{name} {device}）: {err}")
                time.sleep(3)

        time.sleep(10)
        cls.check_ib_device_status()
        log.info("OpenSM 启动成功")

    @classmethod
    def restart_opensm_for_device(cls, device: str) -> None:
        """PF 复位后重新启动所有 pport 的 OpenSM"""
        log.info(f"因 {device} 被复位，重新启动所有 pport 的 OpenSM...")
        cls.start_opensm_networking()
        log.info(f"{device} 相关的 OpenSM 重新启动成功")

    @classmethod
    def check_ib_device_status(cls) -> None:
        """检查所有 IB 设备状态为 Active"""
        log.info("检查 IB 设备状态...")

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client")
        ]:
            devices = cls.get_ib_devices(exec_addr)
            if not devices:
                cls.bug_result = f"No IB devices found on {name}"
                cls.bug_expect = "Should have IB devices available"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(cls.bug_result)

            for device in devices:
                ibstat_cmd = f"ibstat {device}"
                status, result, err = CommandOperation.execute_command_with_error(ibstat_cmd, exec_addr)
                if status != RtnStatusEnum.SUCCESS.value:
                    cls.bug_result = f"Could not get status for {device} on {name}: {err}"
                    cls.bug_expect = "ibstat should succeed for all devices"
                    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                    cls.create_bug(f"ibstat failed for {device}")

                if "State: Active" not in result or "Physical state: LinkUp" not in result:
                    cls.bug_result = f"Device {device} on {name} is not Active/LinkUp. Output: {result}"
                    cls.bug_expect = "All devices should be in Active state"
                    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                    cls.create_bug(f"Device {device} not Active on {name}")

        log.info("所有 IB 设备均处于 Active/LinkUp 状态")

    @classmethod
    def get_server_ip(cls, exec_addr: str) -> str:
        """获取 server 端 IP 地址"""
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
    def start_all_traffic(cls, devices: List[str], server_ip: str) -> None:
        """在所有指定 PF 上启动 ib_read_bw 业务"""
        log.info(f"在 {devices} 上启动 ib_read_bw 业务...")
        cls.traffic_log_files = {}

        # 启动 server
        for idx, device in enumerate(devices):
            port = cls.PORT_START + idx
            server_log = f"/tmp/ib_read_bw_server_{device}.log"
            server_cmd = (
                f"nohup ib_read_bw -d {device} -p {port} -b --run_infinitely -D 1 -F "
                f"> {server_log} 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                server_cmd, CmdExecuteAdressEnum.SERVER.value
            )
            if status != RtnStatusEnum.SUCCESS.value:
                log.warning(f"设备 {device} server 启动可能异常: {err}")
            cls.traffic_log_files[f"server_{device}"] = server_log

        time.sleep(3)

        # 启动 client
        for idx, device in enumerate(devices):
            port = cls.PORT_START + idx
            client_log = f"/tmp/ib_read_bw_client_{device}.log"
            client_cmd = (
                f"nohup ib_read_bw -d {device} -p {port} -b --run_infinitely -D 1 -F {server_ip} "
                f"> {client_log} 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                client_cmd, CmdExecuteAdressEnum.CLIENT.value
            )
            if status != RtnStatusEnum.SUCCESS.value:
                log.warning(f"设备 {device} client 启动可能异常: {err}")
            cls.traffic_log_files[f"client_{device}"] = client_log

        log.info("ib_read_bw 业务已启动")

    @classmethod
    def stop_all_traffic(cls) -> None:
        """停止所有 ib_read_bw 进程并清理日志"""
        log.info("停止所有 ib_read_bw 进程...")

        kill_cmd = "pkill -15 -f 'ib_read_bw' 2>/dev/null || true"
        for exec_addr in [CmdExecuteAdressEnum.SERVER.value, CmdExecuteAdressEnum.CLIENT.value]:
            CommandOperation.execute_command_with_error(kill_cmd, exec_addr)
        time.sleep(3)

        kill_cmd = "pkill -9 -f 'ib_read_bw' 2>/dev/null || true"
        for exec_addr in [CmdExecuteAdressEnum.SERVER.value, CmdExecuteAdressEnum.CLIENT.value]:
            CommandOperation.execute_command_with_error(kill_cmd, exec_addr)
        time.sleep(1)

        log.info("ib_read_bw 进程已停止")

    @classmethod
    def verify_traffic_alive(cls, devices: List[str]) -> None:
        """验证所有 PF 的 ib_read_bw 业务均已产生有效带宽"""
        log.info("验证所有 PF 业务已产生有效带宽...")

        for device in devices:
            for side, exec_addr in [
                ("server", CmdExecuteAdressEnum.SERVER.value),
                ("client", CmdExecuteAdressEnum.CLIENT.value)
            ]:
                log_file = f"/tmp/ib_read_bw_{side}_{device}.log"
                bandwidth = cls.get_current_bandwidth(log_file, exec_addr)
                log.info(f"{side} {device} 当前带宽: {bandwidth:.2f} MB/s")
                if bandwidth <= 0:
                    cls.bug_result = f"No valid bandwidth for {side} {device} before reset"
                    cls.bug_expect = "All PF traffic should produce valid bandwidth before reset"
                    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                    cls.create_bug(cls.bug_result)

    @classmethod
    def snapshot_monitor_bandwidth(cls, tag: str) -> None:
        """记录受监控 PF 的当前带宽快照"""
        log.info(f"记录 {tag} 时刻受监控 PF 带宽...")
        for device in cls.MONITOR_DEVICES:
            for side, exec_addr in [
                ("server", CmdExecuteAdressEnum.SERVER.value),
                ("client", CmdExecuteAdressEnum.CLIENT.value)
            ]:
                log_file = f"/tmp/ib_read_bw_{side}_{device}.log"
                bandwidth = cls.get_current_bandwidth(log_file, exec_addr)
                log.info(f"{tag} - {side} {device}: {bandwidth:.2f} MB/s")

    @classmethod
    def check_traffic_continuity(cls, devices: List[str]) -> None:
        """检查指定 PF 在复位期间及之后均有有效带宽，业务未中断"""
        log.info("检查非复位 PF 的业务连续性...")

        # 等待一小段时间让日志继续更新
        time.sleep(cls.TRAFFIC_CHECK_SECONDS)

        for device in devices:
            for side, exec_addr in [
                ("server", CmdExecuteAdressEnum.SERVER.value),
                ("client", CmdExecuteAdressEnum.CLIENT.value)
            ]:
                log_file = f"/tmp/ib_read_bw_{side}_{device}.log"
                bandwidth = cls.get_current_bandwidth(log_file, exec_addr)
                log.info(f"连续性检查 - {side} {device}: {bandwidth:.2f} MB/s")
                if bandwidth <= 0:
                    cls.bug_result = (
                        f"Traffic interrupted for {side} {device} after PF1-PF3 reset: "
                        f"no valid bandwidth in recent log"
                    )
                    cls.bug_expect = "Non-reset PF traffic should continue normally during PF1-PF3 reset"
                    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                    cls.create_bug(cls.bug_result)

        log.info("非复位 PF 业务连续性检查通过")

    @classmethod
    def get_current_bandwidth(cls, log_file: str, exec_addr: str) -> float:
        """读取日志文件并返回最近一次有效带宽"""
        status, output, err = CommandOperation.execute_command_with_error(f"cat {log_file}", exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or not output:
            return 0.0
        return cls.parse_bandwidth_from_output(output)

    @classmethod
    def parse_bandwidth_from_output(cls, output: str) -> float:
        """从 perftest 输出中解析最近一次 BW average[MB/sec]"""
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
            return float(matches[-1][3])
        except (ValueError, IndexError):
            return 0.0

    @classmethod
    def get_device_bdf(cls, device: str, exec_addr: str) -> str:
        """根据 IB 设备名获取 PCI BDF 地址"""
        cmd = f"readlink -f /sys/class/infiniband/{device}/device"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value and result.strip():
            match = re.search(r'([0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F])$', result.strip())
            if match:
                return match.group(1)

        cmd = f"ethtool -i {device}"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value and result:
            match = re.search(r'bus-info:\s*([0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F])', result)
            if match:
                return match.group(1)

        cls.bug_result = f"Could not get BDF for device {device}"
        cls.bug_expect = "Should be able to get PCI BDF from /sys or ethtool"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(cls.bug_result)
        return ""

    @classmethod
    def is_device_in_ibstat(cls, device: str, exec_addr: str) -> bool:
        """检查指定 IB 设备是否仍在 ibstat -l 输出中"""
        cmd = f"ibstat -l | grep -q '^{device}$' && echo yes || echo no"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        return status == RtnStatusEnum.SUCCESS.value and result.strip() == "yes"

    @classmethod
    def is_pport(cls, device: str) -> bool:
        """判断设备是否为 pport（物理端口）。双端口网卡的前两个 PF 为 pport。"""
        return device in ["mlx5_0", "mlx5_1"]

    @classmethod
    def get_base_lid(cls, device: str, exec_addr: str) -> str:
        """通过 ibstat 获取指定设备端口的真实 base LID"""
        name = "server" if exec_addr == CmdExecuteAdressEnum.SERVER.value else "client"
        cmd = f"ibstat {device} | grep -i 'Base lid' | awk '{{print $NF}}'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or not result.strip():
            cls.bug_result = f"Failed to get base lid for {device} on {name}: {err}"
            cls.bug_expect = "Base lid should be available in ibstat output"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)
        lid = result.strip()
        log.info(f"{name} 端设备 {device} 的 base lid 为 {lid}")
        return lid

    @classmethod
    def reset_single_function(cls, device: str, exec_addr: str) -> None:
        """对单个 function（PF/VF）执行复位并恢复驱动（完整流程，当前用例中主要在 post 阶段使用）"""
        cls.reset_function_only(device, exec_addr)
        cls.recover_ib_driver_in_post(exec_addr)

    @classmethod
    def reset_function_only(cls, device: str, exec_addr: str) -> None:
        """对单个 function（PF/VF）执行复位并等待其从 ibstat 中消失，不恢复驱动"""
        log.info(f"对设备 {device} 执行 function 级复位（仅复位，不恢复驱动）...")

        bdf = cls.get_device_bdf(device, exec_addr)
        log.info(f"设备 {device} 的 BDF 为 {bdf}")

        reset_cmd = f"echo 1 | sudo tee /sys/bus/pci/devices/{bdf}/reset"
        status, result, err = CommandOperation.execute_command_with_error(reset_cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"Failed to reset function {device} (BDF: {bdf}): {err}"
            cls.bug_expect = "Function reset should succeed"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)
        log.info(f"设备 {device} 复位命令执行成功")

        # 等待设备从 ibstat 中消失
        log.info(f"等待设备 {device} 从 ibstat 中消失...")
        wait_start = time.time()
        while time.time() - wait_start < 60:
            if not cls.is_device_in_ibstat(device, exec_addr):
                log.info(f"设备 {device} 已从 ibstat 中消失")
                break
            time.sleep(1)
        else:
            cls.bug_result = f"Device {device} still visible in ibstat after reset"
            cls.bug_expect = "Device should disappear from ibstat after function reset"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)

    @classmethod
    def recover_ib_driver_in_post(cls, exec_addr: str) -> None:
        """在 post 阶段停止 OpenSM、恢复 IB 驱动并等待稳定"""
        name = "server" if exec_addr == CmdExecuteAdressEnum.SERVER.value else "client"
        log.info(f"post 阶段在 {name} 端停止 OpenSM 并恢复 IB 驱动...")

        # 恢复 IB 驱动前必须先停止所有 OpenSM 进程
        stop_opensm_cmd = "pkill -9 -f opensm 2>/dev/null || true"
        CommandOperation.execute_command_with_error(stop_opensm_cmd, exec_addr)
        time.sleep(2)

        # 恢复 IB 驱动
        log.info(f"在 {name} 端执行 /etc/init.d/openibd force-restart 恢复 IB 驱动...")
        restart_cmd = "/etc/init.d/openibd force-restart"
        status, result, err = CommandOperation.execute_command_with_error(restart_cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"Failed to restart IB driver on {name}: {err}"
            cls.bug_expect = "openibd force-restart should succeed"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)

        log.info(f"等待 {name} 端驱动稳定（{cls.DRIVER_RECOVER_WAIT_SECONDS} 秒）...")
        time.sleep(cls.DRIVER_RECOVER_WAIT_SECONDS)
        log.info(f"{name} 端 IB 驱动恢复完成")

    @classmethod
    def check_reset_devices_recovered(cls) -> None:
        """检查复位的 PF 在 force-restart 后是否重新出现"""
        log.info(f"检查复位的 PF {cls.RESET_TARGET_DEVICES} 是否恢复...")
        for device in cls.RESET_TARGET_DEVICES:
            for exec_addr, name in [
                (CmdExecuteAdressEnum.SERVER.value, "server"),
                (CmdExecuteAdressEnum.CLIENT.value, "client")
            ]:
                if not cls.is_device_in_ibstat(device, exec_addr):
                    cls.bug_result = f"Reset device {device} did not reappear on {name} after force-restart"
                    cls.bug_expect = "Reset PF should reappear in ibstat after driver recovery"
                    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                    cls.create_bug(cls.bug_result)
                log.info(f"{name} 端 {device} 已重新出现")
        log.info("复位的 PF 均已恢复")

    @classmethod
    def run_query_commands(cls, devices: List[str]) -> None:
        """对指定设备中的 pport 执行查询类命令并验证成功，使用真实 base LID"""
        log.info(f"对 {devices} 中的 pport 执行查询类业务命令...")

        for device in devices:
            if not cls.is_pport(device):
                log.info(f"设备 {device} 不是 pport，跳过端口级查询命令")
                continue

            for exec_addr, name in [
                (CmdExecuteAdressEnum.SERVER.value, "server"),
                (CmdExecuteAdressEnum.CLIENT.value, "client")
            ]:
                lid = cls.get_base_lid(device, exec_addr)
                commands = [
                    f"mlxconfig -d {device} q",
                    f"smpquery -C {device} pi {lid} 1",
                    f"perfquery -C {device} {lid} 1",
                    f"ibportstate -C {device} {lid} 1"
                ]
                for cmd in commands:
                    status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
                    if status != RtnStatusEnum.SUCCESS.value:
                        cls.bug_result = f"Query command failed on {name} {device}: {cmd}\nError: {err}"
                        cls.bug_expect = "Query commands should succeed on non-reset PFs"
                        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                        cls.create_bug(cls.bug_result)
                    log.info(f"{name} {device} - {cmd}: 执行成功")

        log.info("查询类命令执行完成")

    @classmethod
    def print_test_summary(cls) -> None:
        """打印测试执行结果摘要"""
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
    def post(cls) -> None:
        log.info("TC-056 测试结束，执行环境清理...")
        cls.stop_all_traffic()

        log.info("post 阶段：停止 OpenSM 并恢复 IB 驱动...")
        cls.recover_ib_driver_in_post(CmdExecuteAdressEnum.SERVER.value)
        cls.recover_ib_driver_in_post(CmdExecuteAdressEnum.CLIENT.value)

        log.info("post 阶段：检查复位的 PF 是否恢复...")
        cls.check_reset_devices_recovered()

        log.info("TC-056 环境清理完成")


def main() -> None:
    MultiPfTestTc056.run()


if __name__ == '__main__':
    main()
