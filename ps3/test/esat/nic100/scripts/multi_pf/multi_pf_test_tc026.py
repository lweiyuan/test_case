#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: TC-026
case title: 设置sl2vl和vlarb后进行线网打流，带宽符合配置-双端口
test category: IB多PF测试
check point: qos
author: zhubo1
date: 2026.06.15
@steps:
1. client和server端都通过cli（mlxconfig -d mlx5_0 sNUM_OF_PF=4）命令设置pf数量为4后复位(重启服务器，下同)网卡（如果pf已经是4了，则不需要设置，也不需要复位了，直接使用）
2. 使用执行opensm -c opensm.conf在执行目录下生成一个默认的配置文件，然后修改该文件中的参数改为：
   qos_max_vls 4
   qos_high_limit 1
   qos_vlarb_high 0:1,1:2,2:4,3:255
   qos_vlarb_low 0:1,1:2,2:4,3:255
   qos_sl2vl 0,1,2,3
3. 启动opensm（使用-Q参数启用QoS）
4. 对所有PF的SL0~SL3进行并发ib_read_bw打流
5. 等待带宽稳定后观察SL0~3的带宽比例是否为1:2:4:255

@expected:
1. 设置成功，复位成功
2. NA
3. 启动成功
4. 打流成功
5. 无论哪个pf，其内部的sl0~3的带宽比例为1:2:4:255

@changelog:
2026.06.15 - 基于opensm-manager和perftest-tools skill更新
- 使用opensm -Q启用QoS，使用-F指定配置文件
- 正确使用ib_read_bw命令（server端先启动，client端后连接）
- 使用-S参数指定SL（Service Level）
2026.06.15 - 优化
- 使用唯一opensm.conf路径，避免并发冲突
- 清理已有QoS配置避免重复
- server端ib_read_bw补充-q参数
- 使用ibstat -l统计PF数量
- 增加测试结果汇总报告
- post阶段恢复原始PF数量
- 脚本自身异常不再误提Bug
- 优雅停止ib_read_bw以flush日志
2026.06.15 - 并发模型改为 _thread.start_new_thread
- client端ib_read_bw改用 _thread 低层级线程并发执行
- 使用 _thread.allocate_lock() 保护共享结果列表和完成计数器
2026.06.15 - 结合 infiniband-rdma-test 内存估算规则
- 打流前检查server/client空闲内存
- 根据可用内存动态调整 -q 和 -s
- 线网业务内存估算：N * 2 * qp * packet_size
2026.06.15 - 结合 infiniband-rdma-test perftest 多线程日志规则
- client 端也使用 nohup + 重定向到独立日志文件
- 不再以 timeout 作为失败判定
- 并发结束后检查收发两端日志内容判定成功/失败
2026.06.16 - 结合 perftest-tools skill 更新
- ib_read_bw 命令增加 -D 1（每秒打印一次回显）和 -F（禁用 CPU 频率提示）
- 带宽解析改为取除最后一次之外的最近 10 次统计求平均值，降低末尾统计失真误差
"""

import os
import time
import re
import _thread
import add_syspath
from typing import List, Dict, Tuple
from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum, BugTypeEnum
from scripts.script_libs.script_base import ScriptBase, SxeException
from scripts.script_libs.common_operation import CommonOperation


class MultiPfTestTc026(ScriptBase):
    test_object = "Multi PF Test"
    test_module = "IB Multi PF Test"
    test_tool = "mlxconfig, ibstat, opensm, ib_read_bw"
    test_precondition = "天蝎网卡为双端口形态"
    test_steps = """
    1. client和server端都通过cli设置pf数量为4后复位网卡
    2. 生成opensm.conf配置文件，配置QoS参数
    3. 使用opensm -Q启动（启用QoS）
    4. 对所有PF的SL0~SL3进行并发ib_read_bw打流
    5. 验证SL0~3的带宽比例是否为1:2:4:255
    """

    # 流量参数配置
    TARGET_PF_COUNT = 4
    TARGET_QP_COUNT = 1
    TARGET_PACKET_SIZE = 65536  # 64KB，perftest 默认包长
    TRAFFIC_DURATION = 60       # 默认打流时长（秒）
    REBOOT_WAIT_SECONDS = 30    # reboot 后等待开始检测的时间
    SERVER_AVAILABILITY_TIMEOUT = 300
    THREAD_START_TIMEOUT = 30
    BANDWIDTH_RATIO_TOLERANCE = 0.2

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "Multi PF Test TC-026 Failed"
        cls.opensm_conf_path = f"/tmp/opensm_tc026_{os.getpid()}.conf"
        cls.traffic_processes = []
        cls.test_results = {
            "total_steps": 5,
            "passed_steps": 0,
            "failed_steps": 0,
            "failures": []
        }

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 TC-026 测试环境...")
        server_driver, client_driver = CommonOperation.get_nic_driver_name()
        log.info(f"服务端驱动: {server_driver}, 客户端驱动: {client_driver}")

        status, result, err = CommandOperation.execute_command_with_error(
            "ibstat -l", CmdExecuteAdressEnum.SERVER.value
        )
        if status != RtnStatusEnum.SUCCESS.value or not result.strip():
            log.error("服务端未找到 IB 设备")
            cls.own_environment_enabled = False
            return

        status, result, err = CommandOperation.execute_command_with_error(
            "ibstat -l", CmdExecuteAdressEnum.CLIENT.value
        )
        if status != RtnStatusEnum.SUCCESS.value or not result.strip():
            log.error("客户端未找到 IB 设备")
            cls.own_environment_enabled = False
            return

        cls.own_environment_enabled = True
        log.info("环境检查通过")

    @classmethod
    def prepare(cls) -> None:
        log.info("准备 TC-026 测试环境...")
        cls.initial_pf_count_server = cls.get_pf_count(CmdExecuteAdressEnum.SERVER.value)
        cls.initial_pf_count_client = cls.get_pf_count(CmdExecuteAdressEnum.CLIENT.value)
        log.info(
            f"Initial PF count - Server: {cls.initial_pf_count_server}, "
            f"Client: {cls.initial_pf_count_client}"
        )

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 TC-026 测试：双端口网卡 SL2VL 和 VLArb 带宽测试")
        log.info("=" * 60)

        step_methods = [
            ("设置PF数量并复位", cls.set_pf_and_reset, cls.TARGET_PF_COUNT),
            ("生成OpenSM QoS配置", cls.generate_opensm_config),
            ("启动OpenSM并检查设备状态", cls.start_opensm_with_qos),
            ("执行并发ib_read_bw打流", cls.perform_concurrent_traffic_test),
            ("验证SL0~SL3带宽比例", cls.verify_bandwidth_ratio),
        ]

        try:
            for step_name, step_func, *step_args in step_methods:
                log.info(f"[步骤] {step_name}")
                step_func(*step_args)
                cls.test_results["passed_steps"] += 1

            cls.print_test_summary()
            log.info("测试执行成功 - TC-026 QoS带宽比例测试通过")
        except SxeException:
            cls.print_test_summary()
            raise
        except Exception as e:
            cls.print_test_summary()
            log.error(f"TC-026 测试失败（未预期错误）: {e}")
            raise

    @classmethod
    def set_pf_and_reset(cls, pf_count: int) -> None:
        log.info(f"设置 PF 数量为 {pf_count} 并重启...")

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
    def get_pf_count(cls, exec_addr: str) -> int:
        """获取PF数量 - 使用ibstat -l统计IB设备数"""
        status, result, err = CommandOperation.execute_command_with_error("ibstat -l", exec_addr)
        if status == RtnStatusEnum.SUCCESS.value:
            devices = [line.strip() for line in result.split('\n') if line.strip()]
            return len(devices)
        return 0

    @classmethod
    def generate_opensm_config(cls) -> None:
        log.info("生成包含 QoS 配置的 opensm.conf...")

        gen_cmd = f"opensm -c {cls.opensm_conf_path}"
        status, result, err = CommandOperation.execute_command_with_error(gen_cmd, CmdExecuteAdressEnum.SERVER.value)
        log.info(f"opensm -c 执行结果: status={status}, err={err}")

        # 按 opensm-manager skill 要求：QoS 参数直接追加到配置文件尾部
        update_cmd = (
            f"cat >> {cls.opensm_conf_path} << 'EOF'\n\n"
            "# QoS default options\n"
            "# max_op_vls is REQUIRED for this product - must be set to 4\n"
            "max_op_vls 4\n"
            "qos_max_vls 4\n"
            "qos_high_limit 1\n"
            "qos_vlarb_high 0:1,1:2,2:4,3:255\n"
            "qos_vlarb_low 0:1,1:2,2:4,3:255\n"
            "qos_sl2vl 0,1,2,3\n"
            "EOF"
        )
        CommandOperation.execute_command_with_error(update_cmd, CmdExecuteAdressEnum.SERVER.value)

        cat_cmd = f"cat {cls.opensm_conf_path} | grep -E 'qos_|max_op_vls'"
        status, result, err = CommandOperation.execute_command_with_error(cat_cmd, CmdExecuteAdressEnum.SERVER.value)
        log.info(f"opensm.conf 中的 QoS 配置:\n{result}")

        if "qos_max_vls" not in result or "qos_sl2vl" not in result:
            cls.bug_result = "QoS parameters not found in opensm.conf"
            cls.bug_expect = "opensm.conf should contain qos_max_vls, qos_vlarb_high, qos_vlarb_low, qos_sl2vl"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)

        log.info("QoS 配置完成")

    @classmethod
    def start_opensm_with_qos(cls) -> None:
        log.info("使用 QoS 配置启动 OpenSM...")

        kill_cmd = "pkill -9 -f opensm 2>/dev/null || true"
        CommandOperation.execute_command_with_error(kill_cmd, CmdExecuteAdressEnum.SERVER.value)
        time.sleep(2)

        devices = cls.get_ib_devices(CmdExecuteAdressEnum.SERVER.value)
        if not devices:
            cls.bug_result = "No IB devices found for opensm networking"
            cls.bug_expect = "Should have at least one IB device"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("No IB devices available for opensm")

        log.info(f"发现 {len(devices)} 个 IB 设备: {devices}")

        pport_guids = cls.get_pport_guids(CmdExecuteAdressEnum.SERVER.value, devices[:2])

        if not pport_guids:
            cls.bug_result = "Could not get pport GUIDs for opensm"
            cls.bug_expect = "Should be able to get Node GUID from pport devices"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("Failed to get pport GUIDs")

        for i, guid in enumerate(pport_guids):
            log.info(f"为 pport {i+1} 启动 OpenSM，GUID: {guid}")
            opensm_cmd = (
                f"nohup opensm -g {guid} -B -e -Q -F {cls.opensm_conf_path} "
                f"-f /var/log/opensm_{i}.log > /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, CmdExecuteAdressEnum.SERVER.value
            )
            if status != RtnStatusEnum.SUCCESS.value:
                log.warning(f"OpenSM 可能未正常启动（GUID: {guid}）: {err}")
            time.sleep(3)

        time.sleep(10)
        cls.check_ib_device_status()
        log.info("OpenSM 已使用 QoS 配置成功启动")

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

            if "State: Active" not in result:
                cls.bug_result = f"Device {device} is not in Active state. Output: {result}"
                cls.bug_expect = "All devices should be in Active state after opensm starts"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"Device {device} not Active")

        log.info(f"所有 {len(devices)} 个 IB 设备均处于 Active 状态")

    # ------------------------------------------------------------------
    # 内存估算相关方法（infiniband-rdma-test Skill 第 18 条）
    # ------------------------------------------------------------------

    @classmethod
    def get_available_memory_mb(cls, exec_addr: str) -> int:
        """获取节点 available 空闲内存（MB），优先使用 free -m 的 available 列"""
        cmd = "free -m | awk '/Mem:/ {print $7}'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value and result.strip():
            try:
                return int(result.strip())
            except ValueError:
                log.warning(f"无法从以下输出解析可用内存: {result}")
        return 0

    @classmethod
    def calculate_safe_parameters(
        cls,
        exec_addr: str,
        flow_count: int,
        desired_qp: int,
        desired_packet_size: int,
        is_loopback: bool = False
    ) -> Tuple[int, int]:
        """
        根据单节点空闲内存计算安全的 -q 和 -s

        内存估算：
        - 线网业务：单节点总内存 ≈ flow_count * 2 * qp * packet_size
        - 自发自收业务：单节点总内存 ≈ flow_count * 4 * qp * packet_size
        """
        available_mb = cls.get_available_memory_mb(exec_addr)
        log.info(
            f"Memory check on {exec_addr}: available={available_mb}MB, "
            f"flows={flow_count}, desired_qp={desired_qp}, "
            f"desired_packet_size={desired_packet_size}"
        )

        if available_mb <= 0:
            log.warning("无法获取可用内存，使用期望参数")
            return desired_qp, desired_packet_size

        # 预留 30% 安全余量
        usable_bytes = available_mb * 1024 * 1024 * 0.7
        multiplier = 4 if is_loopback else 2

        # 单条流单个 QP 所需内存
        memory_per_qp_per_flow = multiplier * desired_packet_size

        # 可用总 QP 数（所有流共享）
        total_qps = int(usable_bytes / (flow_count * memory_per_qp_per_flow))
        safe_qp = max(1, total_qps)

        if safe_qp >= desired_qp:
            log.info(f"{exec_addr} 内存充足: 使用 -q {desired_qp}, -s {desired_packet_size}")
            return desired_qp, desired_packet_size

        log.warning(
            f"Memory insufficient on {exec_addr} for desired parameters. "
            f"Safe qp={safe_qp} with packet_size={desired_packet_size}"
        )

        # 如果 QP 降到 1 仍不足，尝试降低包长
        if safe_qp < 1:
            safe_qp = 1
            safe_packet_size = int(usable_bytes / (flow_count * multiplier * safe_qp))
            # 限制最小包长为 64 字节，避免过小失去测试意义
            safe_packet_size = max(64, safe_packet_size)
            log.warning(
                f"Packet size reduced on {exec_addr}: using -q {safe_qp}, -s {safe_packet_size}"
            )
            return safe_qp, safe_packet_size

        return safe_qp, desired_packet_size

    @classmethod
    def determine_traffic_parameters(
        cls,
        flow_count: int,
        is_loopback: bool = False
    ) -> Tuple[int, int]:
        """综合server和client内存，取更保守的参数"""
        server_qp, server_ps = cls.calculate_safe_parameters(
            CmdExecuteAdressEnum.SERVER.value,
            flow_count,
            cls.TARGET_QP_COUNT,
            cls.TARGET_PACKET_SIZE,
            is_loopback
        )
        client_qp, client_ps = cls.calculate_safe_parameters(
            CmdExecuteAdressEnum.CLIENT.value,
            flow_count,
            cls.TARGET_QP_COUNT,
            cls.TARGET_PACKET_SIZE,
            is_loopback
        )

        final_qp = min(server_qp, client_qp)
        final_ps = min(server_ps, client_ps)

        log.info(
            f"Final traffic parameters: -q {final_qp}, -s {final_ps} "
            f"(server: -q {server_qp}/-s {server_ps}, client: -q {client_qp}/-s {client_ps})"
        )
        return final_qp, final_ps

    # ------------------------------------------------------------------
    # 并发打流相关方法（infiniband-rdma-test Skill 第 17、19 条）
    # ------------------------------------------------------------------

    @classmethod
    def perform_concurrent_traffic_test(cls) -> None:
        log.info("=" * 60)
        log.info("开始 SL0~SL3 带宽比例并发测试")
        log.info("=" * 60)

        server_devices = cls.get_ib_devices(CmdExecuteAdressEnum.SERVER.value)
        client_devices = cls.get_ib_devices(CmdExecuteAdressEnum.CLIENT.value)

        if not server_devices or not client_devices:
            cls.bug_result = "No IB devices found for traffic test"
            cls.bug_expect = "Should have IB devices on both server and client"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("No IB devices for traffic test")

        log.info(f"服务端设备: {server_devices}")
        log.info(f"客户端设备: {client_devices}")

        server_ip = cls.get_server_ip(CmdExecuteAdressEnum.SERVER.value)
        log.info(f"打流测试服务端 IP: {server_ip}")

        port_start = 18000
        sl_values = [0, 1, 2, 3]
        processes = []

        for device in server_devices:
            for sl in sl_values:
                port = port_start + len(processes)
                processes.append({
                    "device": device,
                    "sl": sl,
                    "port": port,
                    "server_ip": server_ip
                })

        flow_count = len(processes)
        log.info(f"待启动的打流进程总数: {flow_count}")

        # 根据内存确定 -q 和 -s（TC-026 是线网业务，is_loopback=False）
        qp_count, packet_size = cls.determine_traffic_parameters(flow_count, is_loopback=False)

        # 估算总内存占用并打印
        multiplier = 2  # 线网业务
        estimated_memory_bytes = flow_count * multiplier * qp_count * packet_size
        estimated_memory_mb = estimated_memory_bytes / (1024 * 1024)
        log.info(
            f"Estimated memory per node: {estimated_memory_mb:.2f} MB "
            f"(formula: {flow_count} * 2 * {qp_count} * {packet_size})"
        )

        log.info(f"步骤 1: 启动 {flow_count} 个服务端 ib_read_bw 进程...")
        for proc in processes:
            server_cmd = (
                f"nohup ib_read_bw -d {proc['device']} -q {qp_count} -s {packet_size} "
                f"-p {proc['port']} -S {proc['sl']} -b --run_infinitely -D 1 -F "
                f"> /tmp/ib_read_bw_server_{proc['port']}.log 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                server_cmd, CmdExecuteAdressEnum.SERVER.value
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"Failed to start server ib_read_bw on port {proc['port']}: {err}"
                cls.bug_expect = "Server ib_read_bw should start successfully"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(cls.bug_result)

        log.info("等待服务端进程启动（5 秒）...")
        time.sleep(5)

        log.info(f"步骤 2: 通过 _thread 启动 {flow_count} 个客户端 ib_read_bw 进程...")

        # 使用 _thread 进行低层级并发管理
        # client 端也使用 nohup + 重定向到独立日志文件（perftest 多线程结果重定向规则）
        client_results = []
        completed = [0]
        lock = _thread.allocate_lock()

        for proc in processes:
            _thread.start_new_thread(
                cls._client_thread_entry,
                (proc, qp_count, packet_size, client_results, completed, lock)
            )

        # 轮询等待所有 client 启动完成（_thread 没有 join，需手动同步）
        log.info(f"等待 {flow_count} 个客户端线程启动...")
        start_time = time.time()
        while completed[0] < flow_count:
            if time.time() - start_time > cls.THREAD_START_TIMEOUT:
                log.error(f"等待客户端线程启动超时: {completed[0]}/{flow_count}")
                break
            time.sleep(0.5)

        log.info(f"客户端线程已启动: {completed[0]}/{flow_count}")

        # 让流量持续运行一段时间（默认 60s，与 perftest 默认执行时长一致）
        log.info(f"让流量运行 {cls.TRAFFIC_DURATION} 秒...")
        time.sleep(cls.TRAFFIC_DURATION)

        # 停止所有 ib_read_bw 进程（先 SIGTERM flush 日志，再 SIGKILL 确保退出）
        log.info("停止所有 ib_read_bw 进程...")
        cls.stop_ib_read_bw_gracefully(CmdExecuteAdressEnum.SERVER.value)
        cls.stop_ib_read_bw_gracefully(CmdExecuteAdressEnum.CLIENT.value)

        # 稍等日志 flush
        time.sleep(2)

        # 检查收发两端日志，判定每条流是否成功
        cls._check_perftest_logs(processes, qp_count, packet_size)

        cls.traffic_processes = processes
        log.info(f"所有 {flow_count} 个打流进程已完成")

    @staticmethod
    def _client_thread_entry(
        proc: Dict,
        qp_count: int,
        packet_size: int,
        client_results: List[Dict],
        completed: List[int],
        lock
    ) -> None:
        """
        _thread 启动的 client 打流入口函数

        注意：
        - _thread 线程内未捕获的异常会直接打印到 stderr 并终止线程，必须 try/except
        - 所有对共享状态的访问都需要加锁
        - client 端也使用 nohup + 重定向，--run_infinitely 不需要 timeout
        """
        try:
            client_cmd = (
                f"nohup ib_read_bw -d {proc['device']} -q {qp_count} -s {packet_size} "
                f"-b --run_infinitely -D 1 -F -p {proc['port']} -S {proc['sl']} {proc['server_ip']} "
                f"> /tmp/ib_read_bw_client_{proc['port']}.log 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                client_cmd, CmdExecuteAdressEnum.CLIENT.value
            )
            res = {
                "device": proc['device'],
                "sl": proc['sl'],
                "port": proc['port'],
                "status": status,
                "result": result,
                "err": err
            }
        except Exception as e:
            res = {
                "device": proc['device'],
                "sl": proc['sl'],
                "port": proc['port'],
                "status": -1,
                "result": "",
                "err": str(e)
            }

        with lock:
            client_results.append(res)
            completed[0] += 1

    @classmethod
    def _check_perftest_logs(cls, processes: List[Dict], qp_count: int, packet_size: int) -> None:
        """
        检查收发两端日志，判定 perftest 是否成功

        规则（infiniband-rdma-test Skill 第 19 条）：
        - 不能依赖命令返回码（--run_infinitely 被 kill 后返回码通常非 0）
        - 必须通过日志内容判断：是否包含有效带宽、是否包含致命连接错误
        """
        log.info("检查服务端和客户端 perftest 日志...")

        failed_flows = []

        for proc in processes:
            port = proc['port']
            sl = proc['sl']
            device = proc['device']

            # 检查 server 端日志：是否有有效带宽
            server_log = f"/tmp/ib_read_bw_server_{port}.log"
            status, server_output, err = CommandOperation.execute_command_with_error(
                f"cat {server_log}", CmdExecuteAdressEnum.SERVER.value
            )
            server_bandwidth = cls.parse_bandwidth_from_output(server_output) if server_output else 0.0

            # 检查 client 端日志：是否有有效带宽或致命错误
            client_log = f"/tmp/ib_read_bw_client_{port}.log"
            status, client_output, err = CommandOperation.execute_command_with_error(
                f"cat {client_log}", CmdExecuteAdressEnum.CLIENT.value
            )
            client_bandwidth = cls.parse_bandwidth_from_output(client_output) if client_output else 0.0

            log.info(
                f"Port {port}, SL{sl}, device {device}: "
                f"server_bw={server_bandwidth:.2f} Mb/s, client_bw={client_bandwidth:.2f} Mb/s"
            )

            # 判定失败：任意一端没有有效带宽，或者出现致命连接错误
            fatal_keywords = [
                "couldn't connect",
                "unable to connect",
                "connection refused",
                "connection timed out",
                "no route to host",
                "failed to initialize",
                "couldn't read remote address",
                "unable to read to socket/rdma_cm",
                "failed to exchange data between server and clients",
            ]

            has_fatal_error = False
            checked_outputs = []
            if server_output:
                checked_outputs.append(("server", server_output))
            if client_output:
                checked_outputs.append(("client", client_output))

            for side, text in checked_outputs:
                lower_output = text.lower()
                for keyword in fatal_keywords:
                    if keyword in lower_output:
                        has_fatal_error = True
                        error_side = side
                        break
                if has_fatal_error:
                    break

            if server_bandwidth <= 0 or client_bandwidth <= 0 or has_fatal_error:
                error_detail = f"server_bw={server_bandwidth:.2f}, client_bw={client_bandwidth:.2f}"
                if has_fatal_error:
                    error_detail += f" / fatal {error_side} error"
                failed_flows.append(f"port={port}, sl={sl}, device={device}: {error_detail}")

        if failed_flows:
            errors = "; ".join(failed_flows)
            cls.bug_result = f"Some perftest flows failed: {errors}"
            cls.bug_expect = "All perftest flows should produce valid bandwidth and no connection errors"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)
        else:
            log.info("所有 perftest 日志检查通过")

    @classmethod
    def get_server_ip(cls, exec_addr: str) -> str:
        """获取server端IP，支持多种fallback方式"""
        # 方式1: 通过默认路由获取本机IP
        ip_cmd = "ip route get 1.1.1.1 | awk '{print $7}' | head -1"
        status, result, err = CommandOperation.execute_command_with_error(ip_cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value and result.strip():
            return result.strip()

        # 方式2: 获取第一个非lo网卡的IPv4地址
        ip_cmd = "ip -4 addr show | grep inet | grep -v '127.0.0.1' | head -1 | awk '{print $2}' | cut -d/ -f1"
        status, result, err = CommandOperation.execute_command_with_error(ip_cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value and result.strip():
            return result.strip()

        cls.bug_result = "Failed to get server IP address"
        cls.bug_expect = "Should be able to get server IP for ib_read_bw client connection"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(cls.bug_result)

    @classmethod
    def verify_bandwidth_ratio(cls) -> None:
        log.info("=" * 60)
        log.info("验证 SL0~SL3 带宽比例")
        log.info("期望比例: SL0:SL1:SL2:SL3 = 1:2:4:255")
        log.info("=" * 60)

        # ib_read_bw 已在 perform_concurrent_traffic_test 中停止并 flush 日志
        # 此处直接读取 server 端日志解析带宽
        sl_bandwidths = {0: [], 1: [], 2: [], 3: []}

        for proc in cls.traffic_processes:
            port = proc['port']
            sl = proc['sl']

            log_file = f"/tmp/ib_read_bw_server_{port}.log"
            cat_cmd = f"cat {log_file}"
            status, result, err = CommandOperation.execute_command_with_error(
                cat_cmd, CmdExecuteAdressEnum.SERVER.value
            )

            if status == RtnStatusEnum.SUCCESS.value and result:
                bandwidth = cls.parse_bandwidth_from_output(result)
                if bandwidth > 0:
                    sl_bandwidths[sl].append(bandwidth)
                    log.info(f"端口 {port}, SL{sl}: {bandwidth:.2f} Mb/s")

        sl_avg_bandwidths = {}
        for sl in [0, 1, 2, 3]:
            if sl_bandwidths[sl]:
                sl_avg_bandwidths[sl] = sum(sl_bandwidths[sl]) / len(sl_bandwidths[sl])
            else:
                sl_avg_bandwidths[sl] = 0

        log.info("各 SL 平均带宽:")
        for sl in [0, 1, 2, 3]:
            log.info(f"  SL{sl}: {sl_avg_bandwidths[sl]:.2f} Mb/s")

        expected_ratios = {0: 1, 1: 2, 2: 4, 3: 255}

        if sl_avg_bandwidths[0] > 0:
            actual_ratios = {}
            for sl in [0, 1, 2, 3]:
                if sl_avg_bandwidths[sl] > 0:
                    actual_ratios[sl] = sl_avg_bandwidths[sl] / sl_avg_bandwidths[0]
                else:
                    actual_ratios[sl] = 0

            log.info("实际带宽比例（以 SL0=1 归一化）:")
            for sl in [0, 1, 2, 3]:
                log.info(f"  SL{sl}: {actual_ratios[sl]:.2f} (期望: {expected_ratios[sl]})")

            all_passed = True
            failed_sl = []
            for sl in [0, 1, 2, 3]:
                expected = expected_ratios[sl]
                actual = actual_ratios[sl]
                if expected > 0:
                    ratio_diff = abs(actual - expected) / expected
                    if ratio_diff > cls.BANDWIDTH_RATIO_TOLERANCE:
                        all_passed = False
                        failed_sl.append(sl)
                        log.error(
                            f"SL{sl} bandwidth ratio mismatch: expected {expected}, "
                            f"got {actual:.2f} (diff: {ratio_diff*100:.1f}%)"
                        )

            if not all_passed:
                cls.bug_result = (
                    f"Bandwidth ratio mismatch for SL{failed_sl}. "
                    f"Actual: {actual_ratios}, Expected: {expected_ratios}"
                )
                cls.bug_expect = "Bandwidth ratio should be approximately 1:2:4:255 for SL0~SL3"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(cls.bug_result)
            else:
                log.info("带宽比例验证通过")
        else:
            cls.bug_result = "No bandwidth data collected for SL0"
            cls.bug_expect = "Should be able to collect bandwidth data from all SLs"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)

    @classmethod
    def stop_ib_read_bw_gracefully(cls, exec_addr: str) -> None:
        """先发送SIGTERM让ib_read_bw flush日志并打印最终统计，再强制kill"""
        log.info("优雅停止 ib_read_bw 进程...")
        term_cmd = "pkill -15 -f 'ib_read_bw' 2>/dev/null || true"
        CommandOperation.execute_command_with_error(term_cmd, exec_addr)
        time.sleep(3)
        kill_cmd = "pkill -9 -f 'ib_read_bw' 2>/dev/null || true"
        CommandOperation.execute_command_with_error(kill_cmd, exec_addr)

    @classmethod
    def parse_bandwidth_from_output(cls, output: str) -> float:
        """
        从 perftest 输出中解析有效带宽，统一返回 Mb/s。

        匹配 perftest 标准统计表：
          #bytes  #iterations  BW peak[MB/sec]  BW average[MB/sec]  MsgRate[Mpps]

        对 --run_infinitely 场景，取除最后一次之外的最近 10 次 BW average[MB/sec]
        求平均值并转换为 Mb/s（×8），避免进程停止时末尾统计失真带来的误差。
        对 -D / -n 场景只有一条统计行时，直接返回该值。
        """
        if not output:
            return 0.0

        # 匹配统计行：5 列数字，第 4 列为 BW average[MB/sec]
        pattern = re.compile(
            r'^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s*$',
            re.MULTILINE
        )
        matches = pattern.findall(output)
        if not matches:
            return 0.0

        try:
            if len(matches) == 1:
                # -D / -n 场景只有一条统计行，直接取值
                bw_average_mb_per_sec = float(matches[0][3])
            else:
                # --run_infinitely 场景：取除最后一次之外的最近 10 次求平均
                recent_matches = matches[-11:-1]
                bw_average_mb_per_sec = sum(float(m[3]) for m in recent_matches) / len(recent_matches)
            # 转换为 Mb/s
            return bw_average_mb_per_sec * 8.0
        except (ValueError, IndexError):
            return 0.0

    @classmethod
    def print_test_summary(cls) -> None:
        """按infiniband-rdma-test skill要求输出测试结果汇总"""
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
        log.info("清理测试环境...")

        cls.stop_ib_read_bw_gracefully(CmdExecuteAdressEnum.SERVER.value)
        cls.stop_ib_read_bw_gracefully(CmdExecuteAdressEnum.CLIENT.value)

        kill_opensm_cmd = "pkill -9 -f opensm 2>/dev/null || true"
        CommandOperation.execute_command_with_error(kill_opensm_cmd, CmdExecuteAdressEnum.SERVER.value)

        # 清理 server 端日志
        cleanup_server_log = (
            f"rm -f /tmp/ib_read_bw_server_*.log {cls.opensm_conf_path} "
            f"/tmp/opensm*.log 2>/dev/null || true"
        )
        CommandOperation.execute_command_with_error(cleanup_server_log, CmdExecuteAdressEnum.SERVER.value)

        # 清理 client 端日志
        cleanup_client_log = "rm -f /tmp/ib_read_bw_client_*.log 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cleanup_client_log, CmdExecuteAdressEnum.CLIENT.value)

        # 恢复原始PF数量
        cls.restore_pf_count()

        log.info("清理完成")

    @classmethod
    def restore_pf_count(cls) -> None:
        """恢复原始PF数量"""
        if not hasattr(cls, 'initial_pf_count_server') or not hasattr(cls, 'initial_pf_count_client'):
            return

        if cls.initial_pf_count_server <= 0 or cls.initial_pf_count_client <= 0:
            return

        current_server = cls.get_pf_count(CmdExecuteAdressEnum.SERVER.value)
        current_client = cls.get_pf_count(CmdExecuteAdressEnum.CLIENT.value)

        need_restore = False

        if current_server != cls.initial_pf_count_server:
            log.info(
                f"Restoring server PF count from {current_server} to {cls.initial_pf_count_server}"
            )
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
            log.info(
                f"Restoring client PF count from {current_client} to {cls.initial_pf_count_client}"
            )
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


def main() -> None:
    MultiPfTestTc026.run()


if __name__ == '__main__':
    main()
