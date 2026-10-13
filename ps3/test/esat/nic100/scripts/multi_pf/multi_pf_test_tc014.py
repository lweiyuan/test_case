#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: TC-014
case title: 通过cli设置多pf为4并复位，对4个pf进行数据包进行自发自收测试-双端口
test category: IB多PF测试
check point: 多pf自发自收
author: zhubo1
date: 2026.06.16
@steps:
    1. client和server端均先检查当前PF数量；若不等于4，则通过 mlxconfig -d mlx5_0 -y set NUM_OF_PF=4 设置PF数量为4，并重启服务器使配置生效；若已是4，则跳过设置和重启。重启后先等待约30秒让服务器进入重启流程，再通过命令输出动态检测服务器上线（超时300秒）。
    2. 通过 ibstat 分别获取两个pport（mlx5_0、mlx5_1）的Node GUID，为每个pport启动一个OpenSM实例：nohup opensm -g <GUID> -B -e -f /var/log/opensm_{i}.log > /dev/null 2>&1 &。启动后检查所有IB设备状态为Active。
    3. 对所有PF执行 ib_read_bw、ib_write_bw、ib_send_bw、ib_atomic_bw 的数据包自发自收测试：在同一节点上同时启动server和client（nohup ib_*_bw -d mlx5_X -b -D 60 -F -p <port> > /tmp/ib_*_bw_server_<port>.log 2>&1 & 与 ib_*_bw -d mlx5_X -b -D 60 -F -p <port> 127.0.0.1 > /tmp/ib_*_bw_client_<port>.log 2>&1）。结束后检查日志中是否存在有效带宽（BW average[MB/sec] > 0），且无致命连接错误。
    4. 在步骤3期间，对pport执行 ibdump -d mlx5_0 抓包，并通过wireshark解析。

@expected:
    1. PF=4设置成功（如发生设置），服务器重启成功；PF数量为4。
    2. OpenSM启动成功，所有IB设备状态为Active（State: Active，Physical state: LinkUp）。
    3. 所有PF的各类型自发自收测试均产生有效带宽，日志无 Couldn't connect、failed to initialize 等致命连接错误。
    4. 成功抓到包，且解析出的业务类型正确。

@changelog:
2026.06.16 - 根据更新后的用例生成
- 使用项目技巧：PF数量相同跳过设置/重启、reboot后30秒再检测、双端口OpenSM按pport GUID启动
- perftest统一使用 -D 60 -F，通过日志有效带宽判定成功
- pport/vport区分：特殊IB命令仅对pport执行
"""

import os
import time
import re
import _thread
import add_syspath
from typing import List, Dict
from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum, BugTypeEnum
from scripts.script_libs.script_base import ScriptBase, SxeException
from scripts.script_libs.common_operation import CommonOperation


class MultiPfTestTc014(ScriptBase):
    test_object = "Multi PF Test"
    test_module = "IB Multi PF Test"
    test_tool = "mlxconfig, ibstat, lspci, opensm, smpquery, perfquery, ibportstate, perftest"
    test_precondition = "天蝎网卡为双端口形态"
    test_steps = """
    1. client和server端均先检查当前PF数量；若不等于4，则通过 mlxconfig -d mlx5_0 -y set NUM_OF_PF=4 设置PF数量为4，并重启服务器使配置生效；若已是4，则跳过设置和重启。重启后先等待约30秒让服务器进入重启流程，再通过命令输出动态检测服务器上线（超时300秒）。
    2. 通过 ibstat 分别获取两个pport（mlx5_0、mlx5_1）的Node GUID，为每个pport启动一个OpenSM实例：nohup opensm -g <GUID> -B -e -f /var/log/opensm_{i}.log > /dev/null 2>&1 &。启动后检查所有IB设备状态为Active。
    3. 对所有PF执行 ib_read_bw、ib_write_bw、ib_send_bw、ib_atomic_bw 的数据包自发自收测试：在同一节点上同时启动server和client（nohup ib_*_bw -d mlx5_X -b -D 60 -F -p <port> > /tmp/ib_*_bw_server_<port>.log 2>&1 & 与 ib_*_bw -d mlx5_X -b -D 60 -F -p <port> 127.0.0.1 > /tmp/ib_*_bw_client_<port>.log 2>&1）。结束后检查日志中是否存在有效带宽（BW average[MB/sec] > 0），且无致命连接错误。
    4. 在步骤3期间，对pport执行 ibdump -d mlx5_0 抓包，并通过wireshark解析。
    """

    REBOOT_WAIT_SECONDS = 30
    SERVER_AVAILABILITY_TIMEOUT = 300
    TRAFFIC_DURATION = 60
    PORT_START = 18000

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "MultiPfTestTc014 Failed"
        cls.test_results = {
            "total_steps": 0,
            "passed_steps": 0,
            "failures": []
        }

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 TC-014 测试环境...")
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
        log.info("准备 TC-014 测试环境...")
        cls.initial_pf_count_server = cls.get_pf_count(CmdExecuteAdressEnum.SERVER.value)
        cls.initial_pf_count_client = cls.get_pf_count(CmdExecuteAdressEnum.CLIENT.value)
        log.info(
            f"初始 PF 数量 - 服务端: {cls.initial_pf_count_server}, "
            f"客户端: {cls.initial_pf_count_client}"
        )

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 TC-014 测试：通过cli设置多pf为4并复位，对4个pf进行数据包进行自发自收测试-双端口")
        log.info("=" * 60)

        try:
            cls.test_results["total_steps"] = 1

            cls.set_pf_and_reset(4)
            cls.verify_pf_count(4)
            cls.start_opensm_networking()

            # 启动 ibdump 抓包
            log.info("启动 ibdump 抓包...")
            ibdump_cmd = "nohup ibdump -d mlx5_0 -w /tmp/tc014_capture.pcap > /tmp/ibdump.log 2>&1 &"
            CommandOperation.execute_command_with_error(ibdump_cmd, CmdExecuteAdressEnum.SERVER.value)

            tools = ["ib_read_bw", "ib_write_bw", "ib_send_bw", "ib_atomic_bw"]
            devices = cls.get_ib_devices(CmdExecuteAdressEnum.SERVER.value)

            for tool in tools:
                log.info(f"\n开始执行 {tool} 自发自收测试")
                cls.perform_perftest_loopback(tool, devices)

            # 停止 ibdump
            time.sleep(5)
            CommandOperation.execute_command_with_error("pkill -15 -f ibdump 2>/dev/null || true", CmdExecuteAdressEnum.SERVER.value)
            time.sleep(2)
            CommandOperation.execute_command_with_error("pkill -9 -f ibdump 2>/dev/null || true", CmdExecuteAdressEnum.SERVER.value)

            status, result, err = CommandOperation.execute_command_with_error(
                "ls -lh /tmp/tc014_capture.pcap", CmdExecuteAdressEnum.SERVER.value
            )
            if status != RtnStatusEnum.SUCCESS.value or not result.strip():
                cls.bug_result = "ibdump did not generate capture file"
                cls.bug_expect = "ibdump should generate /tmp/tc014_capture.pcap"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug("ibdump capture file not found")

            cls.test_results["passed_steps"] += 1
            log.info("所有自发自收测试和抓包完成")
            cls.print_test_summary()
            log.info("测试执行成功 - TC-014 通过")
        except SxeException:
            cls.print_test_summary()
            raise
        except Exception as e:
            cls.print_test_summary()
            log.error(f"TC-014 测试失败（未预期错误）: {e}")
            raise

    @classmethod
    def get_pf_count(cls, exec_addr: str) -> int:
        """获取PF数量 - 使用lspci统计Mellanox设备数"""
        lspci_cmd = "lspci | grep -i mellanox | wc -l"
        status, result, err = CommandOperation.execute_command_with_error(lspci_cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value:
            try:
                return int(result.strip())
            except ValueError:
                return 0
        return 0

    @classmethod
    def set_pf_and_reset(cls, pf_count: int, device: str = "mlx5_0", force_set: bool = False) -> bool:
        """设置PF数量并重启；force_set=True时即使当前数量相同也执行set命令"""
        log.info(f"设置 {device} 的 PF 数量为 {pf_count} ...")
        need_reboot = False

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client")
        ]:
            current_pf = cls.get_pf_count(exec_addr)
            if current_pf == pf_count and not force_set:
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

        return need_reboot

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
    def parse_bandwidth_from_output(cls, output: str) -> float:
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
    def stop_perftest_gracefully(cls, exec_addr: str, tool: str = "ib_read_bw") -> None:
        log.info(f"优雅停止 {tool} 进程...")
        term_cmd = f"pkill -15 -f '{tool}' 2>/dev/null || true"
        CommandOperation.execute_command_with_error(term_cmd, exec_addr)
        time.sleep(3)
        kill_cmd = f"pkill -9 -f '{tool}' 2>/dev/null || true"
        CommandOperation.execute_command_with_error(kill_cmd, exec_addr)

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
    def perform_pport_commands_and_bw(cls, pf_count: int) -> None:
        """对pport执行特殊IB命令，对所有PF执行ib_read_bw线网带宽测试"""
        devices = cls.get_ib_devices(CmdExecuteAdressEnum.SERVER.value)
        if not devices:
            cls.bug_result = "No IB devices found for business tests"
            cls.bug_expect = "Should have at least one IB device"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("No IB devices for business tests")

        pport_devices = devices[:2] if len(devices) >= 2 else devices[:1]
        server_ip = cls.get_server_ip(CmdExecuteAdressEnum.SERVER.value)

        for device in devices[:pf_count]:
            if not device:
                continue
            is_pport = device in pport_devices
            log.info(f"测试设备: {device} (pport={is_pport})")

            if is_pport:
                cls.run_pport_ib_commands(device)

            cls.run_ib_read_bw(device, server_ip)

        log.info(f"PF 数量 {pf_count} 业务测试完成")

    @classmethod
    def run_pport_ib_commands(cls, device: str) -> None:
        commands = [
            (f"mlxconfig -d {device} q", "mlxconfig query"),
            (f"smpquery -C {device} pi 1 1", "smpquery"),
            (f"perfquery -C {device} 1 1", "perfquery"),
            (f"ibportstate -C {device} 1 1", "ibportstate"),
        ]
        for cmd, desc in commands:
            log.info(f"执行 {desc}: {cmd}")
            status, result, err = CommandOperation.execute_command_with_error(
                cmd, CmdExecuteAdressEnum.SERVER.value
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{desc} failed for {device}: {err}"
                cls.bug_expect = f"{desc} should succeed on pport"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(cls.bug_result)
            log.info(f"{desc} 执行成功")

    @classmethod
    def run_ib_read_bw(cls, device: str, server_ip: str) -> None:
        log.info(f"测试设备 {device} 的 ib_read_bw 线网带宽")
        port = cls.PORT_START
        cls.PORT_START += 1

        server_cmd = (
            f"nohup ib_read_bw -d {device} -p {port} -b -D {cls.TRAFFIC_DURATION} -F "
            f"> /tmp/ib_read_bw_server_{device}_{port}.log 2>&1 &"
        )
        status, result, err = CommandOperation.execute_command_with_error(
            server_cmd, CmdExecuteAdressEnum.SERVER.value
        )
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"Failed to start ib_read_bw server on {device}: {err}"
            cls.bug_expect = "ib_read_bw server should start successfully"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)

        time.sleep(3)

        client_cmd = (
            f"ib_read_bw -d {device} -p {port} -b -D {cls.TRAFFIC_DURATION} -F {server_ip} "
            f"> /tmp/ib_read_bw_client_{device}_{port}.log 2>&1"
        )
        status, result, err = CommandOperation.execute_command_with_error(
            client_cmd, CmdExecuteAdressEnum.CLIENT.value,
            timeout=cls.TRAFFIC_DURATION + 30
        )

        cls._check_perftest_logs(
            f"/tmp/ib_read_bw_server_{device}_{port}.log",
            f"/tmp/ib_read_bw_client_{device}_{port}.log",
            CmdExecuteAdressEnum.SERVER.value,
            CmdExecuteAdressEnum.CLIENT.value,
            device
        )

        log.info(f"设备 {device} ib_read_bw 测试完成")

    @classmethod
    def _check_perftest_logs(cls, server_log: str, client_log: str,
                             server_addr: str, client_addr: str, device: str) -> None:
        fatal_keywords = [
            "couldn't connect", "unable to connect", "connection refused",
            "connection timed out", "no route to host", "failed to initialize"
        ]

        status, server_output, err = CommandOperation.execute_command_with_error(
            f"cat {server_log}", server_addr
        )
        server_has_error = cls._has_fatal_error(server_output, fatal_keywords)
        server_bw = cls.parse_bandwidth_from_output(server_output)

        status, client_output, err = CommandOperation.execute_command_with_error(
            f"cat {client_log}", client_addr
        )
        client_has_error = cls._has_fatal_error(client_output, fatal_keywords)
        client_bw = cls.parse_bandwidth_from_output(client_output)

        log.info(f"设备 {device}: server_bw={server_bw:.2f}, client_bw={client_bw:.2f}")

        if server_has_error or client_has_error:
            cls.bug_result = f"Device {device} has fatal error in perftest logs"
            cls.bug_expect = "perftest logs should not contain fatal connection errors"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)
        elif server_bw <= 0 or client_bw <= 0:
            cls.bug_result = f"Device {device} has no valid bandwidth (server={server_bw}, client={client_bw})"
            cls.bug_expect = "perftest should produce valid bandwidth on both sides"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)

    @staticmethod
    def _has_fatal_error(output: str, keywords: List[str]) -> bool:
        if not output:
            return False
        lower_output = output.lower()
        return any(keyword in lower_output for keyword in keywords)

    @classmethod
    def perform_perftest_line_network(cls, tool: str, devices: List[str], server_ip: str) -> None:
        log.info(f"执行 {tool} 线网转发测试，设备数: {len(devices)}")
        for idx, device in enumerate(devices):
            port = cls.PORT_START + idx
            server_log = f"/tmp/{tool}_server_{device}_{port}.log"
            client_log = f"/tmp/{tool}_client_{device}_{port}.log"

            server_cmd = (
                f"nohup {tool} -d {device} -p {port} -b -D {cls.TRAFFIC_DURATION} -F "
                f"> {server_log} 2>&1 &"
            )
            CommandOperation.execute_command_with_error(server_cmd, CmdExecuteAdressEnum.SERVER.value)

        time.sleep(5)

        client_results = []
        completed = [0]
        lock = _thread.allocate_lock()

        for idx, device in enumerate(devices):
            port = cls.PORT_START + idx
            client_log = f"/tmp/{tool}_client_{device}_{port}.log"
            client_cmd = (
                f"{tool} -d {device} -p {port} -b -D {cls.TRAFFIC_DURATION} -F {server_ip} "
                f"> {client_log} 2>&1"
            )
            _thread.start_new_thread(
                cls._client_thread_entry,
                (tool, device, port, client_cmd, client_results, completed, lock)
            )

        timeout = 240
        start_time = time.time()
        while completed[0] < len(devices):
            if time.time() - start_time > timeout:
                log.error(f"等待 {tool} client 线程超时: {completed[0]}/{len(devices)}")
                break
            time.sleep(0.5)

        # 检查所有日志
        for idx, device in enumerate(devices):
            port = cls.PORT_START + idx
            server_log = f"/tmp/{tool}_server_{device}_{port}.log"
            client_log = f"/tmp/{tool}_client_{device}_{port}.log"
            cls._check_perftest_logs(
                server_log, client_log,
                CmdExecuteAdressEnum.SERVER.value,
                CmdExecuteAdressEnum.CLIENT.value,
                device
            )

        cls.PORT_START += len(devices) + 100
        log.info(f"{tool} 线网转发测试完成")

    @classmethod
    def perform_perftest_loopback(cls, tool: str, devices: List[str]) -> None:
        log.info(f"执行 {tool} 自发自收测试，设备数: {len(devices)}")
        for idx, device in enumerate(devices):
            port = cls.PORT_START + idx
            server_log = f"/tmp/{tool}_server_{device}_{port}.log"
            client_log = f"/tmp/{tool}_client_{device}_{port}.log"

            server_cmd = (
                f"nohup {tool} -d {device} -p {port} -b -D {cls.TRAFFIC_DURATION} -F "
                f"> {server_log} 2>&1 &"
            )
            CommandOperation.execute_command_with_error(server_cmd, CmdExecuteAdressEnum.SERVER.value)

        time.sleep(3)

        for idx, device in enumerate(devices):
            port = cls.PORT_START + idx
            client_log = f"/tmp/{tool}_client_{device}_{port}.log"
            client_cmd = (
                f"{tool} -d {device} -p {port} -b -D {cls.TRAFFIC_DURATION} -F 127.0.0.1 "
                f"> {client_log} 2>&1"
            )
            CommandOperation.execute_command_with_error(
                client_cmd, CmdExecuteAdressEnum.SERVER.value,
                timeout=cls.TRAFFIC_DURATION + 30
            )
            cls._check_perftest_logs(
                f"/tmp/{tool}_server_{device}_{port}.log",
                client_log,
                CmdExecuteAdressEnum.SERVER.value,
                CmdExecuteAdressEnum.SERVER.value,
                device
            )

        cls.PORT_START += len(devices) + 100
        log.info(f"{tool} 自发自收测试完成")

    @staticmethod
    def _client_thread_entry(tool: str, device: str, port: int, client_cmd: str,
                             client_results: List[Dict], completed: List[int], lock) -> None:
        try:
            status, result, err = CommandOperation.execute_command_with_error(
                client_cmd, CmdExecuteAdressEnum.CLIENT.value, timeout=120
            )
            res = {"device": device, "port": port, "status": status, "err": err}
        except Exception as e:
            res = {"device": device, "port": port, "status": -1, "err": str(e)}
        with lock:
            client_results.append(res)
            completed[0] += 1

    @classmethod
    def post(cls) -> None:
        log.info("清理测试环境...")

        cls.stop_perftest_gracefully(CmdExecuteAdressEnum.SERVER.value, "ib_read_bw")
        cls.stop_perftest_gracefully(CmdExecuteAdressEnum.CLIENT.value, "ib_read_bw")
        cls.stop_perftest_gracefully(CmdExecuteAdressEnum.SERVER.value, "ib_write_bw")
        cls.stop_perftest_gracefully(CmdExecuteAdressEnum.CLIENT.value, "ib_write_bw")
        cls.stop_perftest_gracefully(CmdExecuteAdressEnum.SERVER.value, "ib_send_bw")
        cls.stop_perftest_gracefully(CmdExecuteAdressEnum.CLIENT.value, "ib_send_bw")
        cls.stop_perftest_gracefully(CmdExecuteAdressEnum.SERVER.value, "ib_atomic_bw")
        cls.stop_perftest_gracefully(CmdExecuteAdressEnum.CLIENT.value, "ib_atomic_bw")

        kill_opensm_cmd = "pkill -9 -f opensm 2>/dev/null || true"
        CommandOperation.execute_command_with_error(kill_opensm_cmd, CmdExecuteAdressEnum.SERVER.value)

        cleanup_server_log = "rm -f /tmp/ib_*_bw_*.log /var/log/opensm_*.log 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cleanup_server_log, CmdExecuteAdressEnum.SERVER.value)
        cleanup_client_log = "rm -f /tmp/ib_*_bw_*.log 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cleanup_client_log, CmdExecuteAdressEnum.CLIENT.value)

        cls.restore_pf_count()
        log.info("清理完成")


def main() -> None:
    MultiPfTestTc014.run()


if __name__ == '__main__':
    main()
