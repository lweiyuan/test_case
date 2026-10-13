#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-6/7/8
case title: 通过ib_send_bw -g，在active状态的端口之间进行多播测试，业务成功
test category: IB多播测试
check point: 用户态 QP 通过 ib_send_bw -g 可成功进行多播，支持指定/不指定 MGID、SRQ 等场景
author: auto-generated
date: 2026.06.24
@steps:
    1. 指定 MGID 进行多播测试。
    2. 不指定 MGID、不使用 SRQ 进行测试。
    3. 指定使用 SRQ 进行测试。
    4. 检查 /var/log/opensm.log 是否出现 trap 66/67。
    5. 检查命令回显中多播 LID 0xc006 及 QPN 0xffffff。

@expected:
    三种方式多播业务均成功。
    指定 MGID 时，回显 MGID 为指定值。
    使用 SRQ 时，回显包含 "using srq : on"。
    opensm.log 中出现 trap_num 66/67。
    多播 LID 0xc006，QPN 必须为 0xffffff。

@changelog:
2026.06.24 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.1 用户态QP退出多播组、3.1.20.2 用户态QP加入多播组
- 使用项目技巧：缺陷自动记录、IB基础概念与设备检查、IB命令处理与回显解析、perftest工具使用
2026.06.25 - 修正：opensm 启动时指定目标设备 GUID；ib_send_bw 多播命令移除 -x 参数；saquery 指定 -C/-P
2026.06.25 - 修正：移除 ib_send_bw 多播业务后的 saquery 多播组新增/消失检测
"""

import os
import time
import re
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, BugTypeEnum, CmdExecuteAdressEnum
from scripts.script_libs.script_base import ScriptBase, SxeException


class IbMulticastMc006(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ib_send_bw, opensm, ibstat"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
opensm 已启动
测试节点之间 IB 网络互通"""
    test_steps = """
    1. 指定 MGID 进行多播测试：ib_send_bw -g -M <MGID> --pkey_index=0 -S 1 -m 2048 -s 2048。
    2. 不指定 MGID、不使用 SRQ 进行测试：ib_send_bw -g --pkey_index=0 -S 1 -m 2048 -s 1024。
    3. 指定使用 SRQ 进行测试：ib_send_bw -g --use-srq。
    4. 检查 /var/log/opensm.log 是否出现 trap_num 66/67。
    5. 检查命令回显中多播 LID 0xc006 及 QPN 0xffffff。
    """

    TARGET_DEVICE = "mlx5_0"
    MGID = "255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:00"
    PERFTEST_PORT_BASE = 18520
    PERFTEST_DURATION = 5
    PERFTEST_STARTUP_WAIT = 3
    PERFTEST_STOP_WAIT = 2
    SAQUERY_WAIT = 2
    OPENSM_TRAP_WAIT = 3

    SCENARIOS = [
        {
            "name": "指定 MGID",
            "server_cmd": (
                "ib_send_bw -d {dev} -g -M {mgid} --pkey_index=0 -S 1 "
                "-m 2048 -s 2048 -p {port} -F"
            ),
            "client_cmd": (
                "ib_send_bw -d {dev} -g -M {mgid} --pkey_index=0 -S 1 "
                "-m 2048 -s 2048 -p {port} -F {server_ip}"
            ),
            "check_mgid": True,
            "check_srq": False,
        },
        {
            "name": "不指定 MGID，不使用 SRQ",
            "server_cmd": (
                "ib_send_bw -d {dev} -g --pkey_index=0 -S 1 "
                "-m 2048 -s 1024 -p {port} -F"
            ),
            "client_cmd": (
                "ib_send_bw -d {dev} -g --pkey_index=0 -S 1 "
                "-m 2048 -s 1024 -p {port} -F {server_ip}"
            ),
            "check_mgid": False,
            "check_srq": False,
        },
        {
            "name": "使用 SRQ",
            "server_cmd": (
                "ib_send_bw -d {dev} -g --use-srq --pkey_index=0 -S 1 "
                "-p {port} -F"
            ),
            "client_cmd": (
                "ib_send_bw -d {dev} -g --use-srq --pkey_index=0 -S 1 "
                "-p {port} -F {server_ip}"
            ),
            "check_mgid": False,
            "check_srq": True,
        },
    ]

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc006 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-6/7/8 测试环境...")

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

        cls.own_environment_enabled = True
        log.info("环境检查通过：两端目标 IB 设备均处于 Active 状态")

    @classmethod
    def prepare(cls) -> None:
        log.info("准备 MC-6/7/8 测试环境...")
        cls.server_ip = cls._get_server_ip()

        # 确保两端 opensm 已启动
        cls._ensure_opensm_running(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._ensure_opensm_running(CmdExecuteAdressEnum.CLIENT.value, "client")

        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-6/7/8 测试：ib_send_bw 用户态多播")
        log.info("=" * 60)

        try:
            for idx, scenario in enumerate(cls.SCENARIOS, 1):
                log.info(f"--- 执行场景 {idx}/3: {scenario['name']} ---")
                cls._run_multicast_scenario(idx, scenario)

            # 检查 opensm.log 中的 trap 66/67
            cls._verify_opensm_trap(CmdExecuteAdressEnum.SERVER.value, "server")

            log.info("=" * 60)
            log.info("测试执行成功 - MC-6/7/8 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-6/7/8 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-6/7/8 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-6/7/8 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-6/7/8 测试环境...")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        # 用户态多播后续用例依赖 opensm，保持 opensm 运行
        log.info("MC-6/7/8 清理完成：保持 opensm 运行")

    @classmethod
    def _get_server_ip(cls) -> str:
        """获取服务端 IP（用于 ib_send_bw client 连接）"""
        if cls.server_logical_ip:
            log.info(f"使用 server_logical_ip: {cls.server_logical_ip}")
            return cls.server_logical_ip

        cmd = "ip route get 1.1.1.1 | awk '{print $7}' | head -1"
        status, result, err = CommandOperation.execute_command_with_error(
            cmd, CmdExecuteAdressEnum.SERVER.value
        )
        if status == RtnStatusEnum.SUCCESS.value and result.strip():
            ip = result.strip()
            log.info(f"自动获取服务端 IP: {ip}")
            return ip

        cls.bug_result = "无法获取服务端 IP 地址供 ib_send_bw client 连接"
        cls.bug_expect = "应能获取服务端可达 IP"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug("MC-6/7/8 获取服务端 IP 失败")

    @classmethod
    def _run_multicast_scenario(cls, scenario_idx: int, scenario: dict) -> None:
        """执行单个多播场景"""
        port = cls.PERFTEST_PORT_BASE + scenario_idx
        server_log = f"/tmp/ib_send_bw_mc6_s{scenario_idx}_server.log"
        client_log = f"/tmp/ib_send_bw_mc6_s{scenario_idx}_client.log"

        # 启动 server
        server_cmd = scenario["server_cmd"].format(
            dev=cls.TARGET_DEVICE,
            mgid=cls.MGID,
            port=port,
        )
        cls._start_perftest_server(
            CmdExecuteAdressEnum.SERVER.value, "server", server_cmd, server_log
        )

        # 启动 client
        client_cmd = scenario["client_cmd"].format(
            dev=cls.TARGET_DEVICE,
            mgid=cls.MGID,
            port=port,
            server_ip=cls.server_ip,
        )
        cls._start_perftest_client(
            CmdExecuteAdressEnum.CLIENT.value, "client", client_cmd, client_log
        )

        # 等待测试完成
        time.sleep(cls.PERFTEST_DURATION)

        # 停止进程
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        time.sleep(cls.PERFTEST_STOP_WAIT)

        # 读取并解析日志
        server_output = cls._read_log(CmdExecuteAdressEnum.SERVER.value, "server", server_log)
        client_output = cls._read_log(CmdExecuteAdressEnum.CLIENT.value, "client", client_log)

        # 判定业务成功
        cls._verify_bandwidth(scenario_idx, scenario["name"], client_output)

        # 检查多播 LID / QPN
        cls._verify_multicast_details(scenario_idx, scenario["name"], client_output)

        # 检查 MGID / SRQ
        if scenario["check_mgid"]:
            cls._verify_mgid_in_output(scenario_idx, scenario["name"], client_output)
        if scenario["check_srq"]:
            cls._verify_srq_in_output(scenario_idx, scenario["name"], client_output)


    @classmethod
    def _start_perftest_server(cls, exec_addr: str, name: str, cmd: str, log_path: str) -> None:
        """后台启动 perftest server"""
        log.info(f"在 {name} 端启动 perftest server: {cmd}")
        full_cmd = f"nohup {cmd} > {log_path} 2>&1 &"
        status, result, err = CommandOperation.execute_command_with_error(full_cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端启动 perftest server 失败: {err}"
            cls.bug_expect = "ib_send_bw server 应能后台启动"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-6/7/8 {name} 端启动 perftest server 失败")
        time.sleep(cls.PERFTEST_STARTUP_WAIT)

    @classmethod
    def _start_perftest_client(cls, exec_addr: str, name: str, cmd: str, log_path: str) -> None:
        """后台启动 perftest client"""
        log.info(f"在 {name} 端启动 perftest client: {cmd}")
        full_cmd = f"nohup {cmd} > {log_path} 2>&1 &"
        status, result, err = CommandOperation.execute_command_with_error(full_cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端启动 perftest client 失败: {err}"
            cls.bug_expect = "ib_send_bw client 应能后台启动并连接 server"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-6/7/8 {name} 端启动 perftest client 失败")

    @classmethod
    def _stop_perftest_processes(cls, exec_addr: str, name: str) -> None:
        """停止 perftest 进程"""
        cmd = 'pkill -9 -f "ib_send_bw" 2>/dev/null || true'
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 ib_send_bw 进程已清理")

    @classmethod
    def _read_log(cls, exec_addr: str, name: str, log_path: str) -> str:
        """读取远程日志文件内容"""
        cmd = f"cat {log_path}"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端读取日志 {log_path} 失败: {err}"
            cls.bug_expect = "perftest 日志文件应存在且可读"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-6/7/8 {name} 端读取 perftest 日志失败")
        return result

    @classmethod
    def _verify_bandwidth(cls, scenario_idx: int, scenario_name: str, output: str) -> None:
        """检查 perftest 输出中是否存在有效带宽"""
        log.info(f"检查场景 {scenario_idx} ({scenario_name}) 的带宽结果...")
        pattern = re.compile(
            r"^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)",
            re.MULTILINE,
        )
        matches = pattern.findall(output)
        if not matches:
            cls.bug_result = f"场景 {scenario_idx} ({scenario_name}) 未找到有效带宽输出。输出:\n{output}"
            cls.bug_expect = "ib_send_bw 输出中应包含 BW average[MB/sec] 统计行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-6/7/8 场景 {scenario_idx} 无有效带宽")

        bw_value = float(matches[-1][3])
        if bw_value <= 0:
            cls.bug_result = f"场景 {scenario_idx} ({scenario_name}) 带宽为 0。输出:\n{output}"
            cls.bug_expect = "多播业务带宽应大于 0"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-6/7/8 场景 {scenario_idx} 带宽为 0")

        log.info(f"场景 {scenario_idx} ({scenario_name}) 带宽: {bw_value} MB/sec")

    @classmethod
    def _verify_multicast_details(cls, scenario_idx: int, scenario_name: str, output: str) -> None:
        """检查多播 LID 和 QPN"""
        log.info(f"检查场景 {scenario_idx} ({scenario_name}) 的多播 LID/QPN...")

        lid_match = re.search(r"LID\s+0xc006", output, re.IGNORECASE)
        qpn_match = re.search(r"QPN\s+0xffffff", output, re.IGNORECASE)

        if not lid_match:
            cls.bug_result = (
                f"场景 {scenario_idx} ({scenario_name}) 未检测到多播 LID 0xc006。输出:\n{output}"
            )
            cls.bug_expect = "ib_send_bw 多播输出中应包含 LID 0xc006"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-6/7/8 场景 {scenario_idx} 多播 LID 异常")

        if not qpn_match:
            cls.bug_result = (
                f"场景 {scenario_idx} ({scenario_name}) 未检测到多播 QPN 0xffffff。输出:\n{output}"
            )
            cls.bug_expect = "ib_send_bw 多播输出中应包含 QPN 0xffffff"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-6/7/8 场景 {scenario_idx} 多播 QPN 异常")

        log.info(f"场景 {scenario_idx} ({scenario_name}) 多播 LID/QPN 检查通过")

    @classmethod
    def _verify_mgid_in_output(cls, scenario_idx: int, scenario_name: str, output: str) -> None:
        """检查指定 MGID 场景输出中包含指定 MGID"""
        log.info(f"检查场景 {scenario_idx} ({scenario_name}) 的 MGID...")
        if cls.MGID not in output:
            cls.bug_result = (
                f"场景 {scenario_idx} ({scenario_name}) 输出中未找到指定 MGID {cls.MGID}。输出:\n{output}"
            )
            cls.bug_expect = "指定 MGID 场景输出中应包含指定 MGID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-6/7/8 场景 {scenario_idx} MGID 不匹配")
        log.info(f"场景 {scenario_idx} ({scenario_name}) MGID 检查通过")

    @classmethod
    def _verify_srq_in_output(cls, scenario_idx: int, scenario_name: str, output: str) -> None:
        """检查 SRQ 场景输出中包含 using srq : on"""
        log.info(f"检查场景 {scenario_idx} ({scenario_name}) 的 SRQ...")
        if "using srq : on" not in output.lower():
            cls.bug_result = (
                f"场景 {scenario_idx} ({scenario_name}) 输出中未找到 'using srq : on'。输出:\n{output}"
            )
            cls.bug_expect = "使用 SRQ 场景输出中应包含 'using srq : on'"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-6/7/8 场景 {scenario_idx} SRQ 未启用")
        log.info(f"场景 {scenario_idx} ({scenario_name}) SRQ 检查通过")

    @classmethod
    @classmethod
    @classmethod
    def _verify_opensm_trap(cls, exec_addr: str, name: str) -> None:
        """检查 /var/log/opensm.log 中是否存在 trap 66/67"""
        log.info(f"检查 {name} 端 opensm.log 中的多播 trap 信息...")
        cmd = r"grep -rhE 'trap_num\s+(66|67)' /var/log/opensm*.log 2>/dev/null | tail -5"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or not result.strip():
            cls.bug_result = f"{name} 端 /var/log/opensm.log 中未找到 trap_num 66/67"
            cls.bug_expect = "多播业务期间 opensm.log 应记录 trap_num 66/67"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-6/7/8 {name} 端 opensm.log 缺少 trap 66/67")
        log.info(f"{name} 端 opensm.log 中检测到 trap 66/67:\n{result.strip()}")

    @classmethod
    def _ensure_opensm_running(cls, exec_addr: str, name: str) -> None:
        """检查并在未启动时启动 opensm（指定目标设备 GUID）"""
        status, _, _ = CommandOperation.execute_command_with_error(
            "pgrep -x opensm >/dev/null 2>&1", exec_addr
        )
        if status == RtnStatusEnum.SUCCESS.value:
            log.info(f"{name} 端 opensm 已运行")
            return

        log.warning(f"{name} 端 opensm 未运行，准备启动...")

        # 获取目标设备 Node GUID，启动 opensm 时指定设备
        guid = cls._get_device_guid(exec_addr, name, cls.TARGET_DEVICE)
        cmd = f"nohup opensm -g {guid} -B > /var/log/opensm_mc6.log 2>&1 &"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端启动 opensm 失败: {err}"
            cls.bug_expect = "opensm -g <GUID> -B 应成功启动"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-6/7/8 {name} 端启动 opensm 失败")

        # 等待 opensm 初始化完成
        time.sleep(10)
        status, _, _ = CommandOperation.execute_command_with_error(
            "pgrep -x opensm >/dev/null 2>&1", exec_addr
        )
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端 opensm 启动后未检测到运行进程"
            cls.bug_expect = "opensm -g <GUID> -B 启动后应持续运行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-6/7/8 {name} 端 opensm 未正常运行")

        log.info(f"{name} 端 opensm 启动完成（GUID: {guid}）")

    @classmethod
    def _get_device_guid(cls, exec_addr: str, name: str, device: str) -> str:
        """获取指定 IB 设备的 Node GUID"""
        cmd = f"ibstat {device} | grep 'Node GUID'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端获取 {device} Node GUID 失败: {err}"
            cls.bug_expect = "ibstat 应能返回 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-6/7/8 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-6/7/8 {name} 端解析 {device} GUID 失败")

        return match.group(0)

    @classmethod
    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-6/7/8 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc006.run()


if __name__ == '__main__':
    main()
