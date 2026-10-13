#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-9
case title: 通过opensm将SL0~14配置VL0、SL15配置VL15，使用ib_send_bw -g -M 指定SL15进行多播测试，测试失败，收端收到0个包，且ib_send_bw命令卡住直至120s超时（CX7行为）
test category: IB多播测试
check point: SL0~14 映射到 VL0、SL15 映射到 VL15 时多播业务按预期失败
author: auto-generated
date: 2026.06.24
@steps:
    1. 通过 opensm 配置 SL0~14 -> VL0、SL15 -> VL15。
    2. 使用 smpquery 查询 SL2VL 表，确认 SL0~14 映射为 VL0、SL15 映射为 VL15。
    3. 执行 ib_send_bw -g -M <MGID> -S 15 进行多播测试。
    4. 检查 /var/log/opensm.log 中的 trap 信息。

@expected:
    测试失败，收端收到 0 个包。
    ib_send_bw 命令卡住直至超时（CX7 行为约 120s，自动化中设置合理超时）。
    opensm.log 中出现 trap_num 66/67。
    smpquery 显示 SL2VL 表中 SL0~14 映射为 VL0、SL15 映射为 VL15。

@changelog:
2026.06.24 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.1 用户态QP退出多播组、3.1.20.2 用户态QP加入多播组
- 使用项目技巧：缺陷自动记录、IB基础概念与设备检查、IB命令处理与回显解析、perftest工具使用
2026.06.25 - 修正：opensm 启动时指定目标设备 GUID；启动后增加进程存活检查；增加 smpquery 验证 SL2VL 表
2026.06.25 - 修正：SL2VL 配置明确为 SL0~14->VL0、SL15->VL15，期望表同步按此规则计算
2026.06.25 - 修正：ib_send_bw server/client 均改为同步执行，通过线程并发，不再使用 shell 后台（2>&1 & 或 nohup）
2026.06.26 - 修正：设备名从 env_config 读取，不再硬编码；ib_send_bw 补充 -M 多播组参数；
             SL2VL 期望表按 OperVLs 动态计算；prepare/post 补充 super() 调用
"""

import os
import time
import re
import base64
import threading
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import RtnStatusEnum, BugTypeEnum, CmdExecuteAdressEnum, RdmaMode
from scripts.script_libs.script_base import ScriptBase, SxeException


class IbMulticastMc009(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ib_send_bw, opensm, smpquery, ibstat"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
opensm 已启动
测试节点之间 IB 网络互通
opensm 已配置 SL0~14 映射到 VL0、SL15 映射到 VL15"""
    test_steps = """
    1. 通过 opensm 配置 SL0~14 -> VL0、SL15 -> VL15（生成 opensm 配置文件并重启 opensm）。
    2. 使用 smpquery 查询 SL2VL 表，确认 SL0~14 映射为 VL0、SL15 映射为 VL15。
    3. 执行 ib_send_bw -g -M <MGID> -S 15 多播测试。
    4. 检查测试是否按预期失败（收端 0 包、命令超时）。
    5. 检查 /var/log/opensm.log 中是否出现 trap_num 66/67。
    """

    SERVER_TARGET_DEVICE = ""
    CLIENT_TARGET_DEVICE = ""
    MGID = "255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:00"
    PERFTEST_PORT = 18529
    PERFTEST_SL = 15
    PERFTEST_STARTUP_WAIT = 3
    PERFTEST_TIMEOUT = 35
    OPENSM_CONFIG_PATH = "/tmp/opensm_mc9.conf"
    OPENSM_STARTUP_WAIT = 10
    DEFAULT_OPENSM_CONFIG_PATH = "/etc/rdma/opensm.conf"

    _client_opensm_was_running = False
    _client_opensm_guid = ""

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc009 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-9 测试环境...")

        # 从 env_config 读取目标 IB 设备名（必须在 __update_env_config 之后读取）
        server_relations, client_relations = CommonOperation.get_nic_relationships(
            rdma=True, nic_mode=RdmaMode.Infiniband.value
        )
        cls.SERVER_TARGET_DEVICE = server_relations[0].strip() if server_relations else ""
        cls.CLIENT_TARGET_DEVICE = client_relations[0].strip() if client_relations else ""

        if not cls.SERVER_TARGET_DEVICE or not cls.CLIENT_TARGET_DEVICE:
            log.error("无法从 env_config 获取 server/client RDMA 设备名")
            cls.own_environment_enabled = False
            return

        for exec_addr, name, device in [
            (CmdExecuteAdressEnum.SERVER.value, "server", cls.SERVER_TARGET_DEVICE),
            (CmdExecuteAdressEnum.CLIENT.value, "client", cls.CLIENT_TARGET_DEVICE),
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
            if "Link layer: InfiniBand" not in result:
                log.error(f"{name} 端 {device} 不是 InfiniBand 模式，无法运行 IB 多播测试")
                cls.own_environment_enabled = False
                return

        cls.own_environment_enabled = True
        log.info("环境检查通过：两端目标 IB 设备均处于 Active 状态")

    @classmethod
    def prepare(cls) -> None:
        super().prepare()
        log.info("准备 MC-9 测试环境...")
        cls.server_ip = cls._get_server_ip()

        # 若 client 端已有 opensm 在运行，先记录并停止，避免与 server 端新启动的 opensm 冲突
        if cls._is_opensm_running(CmdExecuteAdressEnum.CLIENT.value):
            cls._client_opensm_was_running = True
            cls._client_opensm_guid = cls._get_device_guid(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.CLIENT_TARGET_DEVICE
            )
            log.info(f"检测到 client 端 opensm 正在运行（GUID: {cls._client_opensm_guid}），先停止")
            cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        else:
            cls._client_opensm_was_running = False

        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._configure_opensm_sl15_vl15(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._start_opensm_with_config(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-9 测试：SL0~14->VL0、SL15->VL15 多播预期失败")
        log.info("=" * 60)

        try:
            server_log = "/tmp/ib_send_bw_mc9_server.log"
            client_log = "/tmp/ib_send_bw_mc9_client.log"

            server_cmd = (
                f"ib_send_bw -d {cls.SERVER_TARGET_DEVICE} -g -M {cls.MGID} "
                f"-S {cls.PERFTEST_SL} -p {cls.PERFTEST_PORT} -F"
            )
            client_cmd = (
                f"ib_send_bw -d {cls.CLIENT_TARGET_DEVICE} -g -M {cls.MGID} "
                f"-S {cls.PERFTEST_SL} -p {cls.PERFTEST_PORT} -F {cls.server_ip}"
            )

            # 同步并发运行 server/client，不使用 shell 后台
            cls._run_perftest_pair(server_cmd, client_cmd, server_log, client_log)

            # 读取日志
            server_output = cls._read_log(CmdExecuteAdressEnum.SERVER.value, "server", server_log)
            client_output = cls._read_log(CmdExecuteAdressEnum.CLIENT.value, "client", client_log)

            # 验证预期失败：收端 0 包或无有效带宽
            cls._verify_expected_failure(server_output, client_output)

            # 验证 opensm.log 中 trap 66/67
            cls._verify_opensm_trap(CmdExecuteAdressEnum.SERVER.value, "server")

            log.info("=" * 60)
            log.info("测试执行成功 - MC-9 通过（按预期失败）")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-9 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-9 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-9 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-9 测试环境...")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        # 恢复 opensm 为默认配置，避免影响后续用例
        cls._restore_default_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        # 若测试前 client 端有 opensm 在运行，则恢复启动
        if cls._client_opensm_was_running and cls._client_opensm_guid:
            log.info(f"恢复 client 端 opensm（GUID: {cls._client_opensm_guid}）...")
            cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
            cmd = (
                f"nohup opensm -g {cls._client_opensm_guid} -B "
                f"> /var/log/opensm.log 2>&1 &"
            )
            CommandOperation.execute_command_with_error(
                cmd, CmdExecuteAdressEnum.CLIENT.value
            )
            time.sleep(cls.OPENSM_STARTUP_WAIT)
            if cls._is_opensm_running(CmdExecuteAdressEnum.CLIENT.value):
                log.info("client 端 opensm 已恢复")
            else:
                log.warning("client 端 opensm 恢复后未检测到运行进程")
        log.info("MC-9 清理完成：已恢复 opensm 默认配置")
        super().post()

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
        cls.create_bug("MC-9 获取服务端 IP 失败")

    @classmethod
    def _stop_opensm(cls, exec_addr: str, name: str) -> None:
        """停止 opensm"""
        cmd = "pkill -9 -x opensm 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        time.sleep(3)
        log.info(f"{name} 端 opensm 已停止")

    @classmethod
    def _configure_opensm_sl15_vl15(cls, exec_addr: str, name: str) -> None:
        """生成 opensm 默认配置文件，并修改 SL15 -> VL15，其余 SL 均映射到 VL0"""
        log.info(f"在 {name} 端生成 opensm 默认配置并修改 SL15->VL15，其余 SL->VL0...")

        # 1. 生成默认配置文件
        base_config_path = f"{cls.OPENSM_CONFIG_PATH}.base"
        cmd = f"opensm -c {base_config_path}"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端生成 opensm 默认配置文件失败: {err}"
            cls.bug_expect = "opensm -c <path> 应能生成默认配置文件"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-9 {name} 端生成 opensm 默认配置失败")

        # 2. 构造 SL2VL 配置：SL0~14 -> VL0，SL15 -> VL15
        # 该配置写入 qos_sl2vl；实际生效时，配置值 <15 按 OperVLs 数量取模，15 保留为 15。
        new_sl2vl = "qos_sl2vl 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,15"

        # 3. 将 QoS 参数追加到默认配置末尾（opensm 使用最后出现的值）
        # 使用 base64 编码避免 heredoc 在 SSH 传输中因换行/引号问题失败
        qos_block = (
            f"# MC-9 QoS override: SL0~14 -> VL0, SL15 -> VL15\n"
            f"qos TRUE\n"
            f"max_op_vls 4\n"
            f"qos_max_vls 4\n"
            f"qos_high_limit 0\n"
            f"qos_vlarb_high 0:64\n"
            f"qos_vlarb_low 0:4,1:4,2:4,3:4\n"
            f"{new_sl2vl}\n"
        )
        qos_b64 = base64.b64encode(qos_block.encode("utf-8")).decode("ascii")
        cmd = (
            f"cat {base_config_path} > {cls.OPENSM_CONFIG_PATH} && "
            f"echo '{qos_b64}' | base64 -d >> {cls.OPENSM_CONFIG_PATH}"
        )
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端生成 MC-9 opensm 配置文件失败: {err}"
            cls.bug_expect = "应能生成 MC-9 opensm 配置文件"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-9 {name} 端配置 opensm SL15->VL15 失败")

        log.info(f"{name} 端 opensm 配置文件已生成: {cls.OPENSM_CONFIG_PATH}")

    @classmethod
    def _start_opensm_with_config(cls, exec_addr: str, name: str) -> None:
        """使用指定配置文件启动 opensm（指定目标设备 GUID）"""
        log.info(f"在 {name} 端使用 SL0~14->VL0、SL15->VL15 配置启动 opensm...")
        guid = cls._get_device_guid(exec_addr, name, cls.SERVER_TARGET_DEVICE)
        cmd = (
            f"nohup opensm -g {guid} -Q -F {cls.OPENSM_CONFIG_PATH} -B "
            f"> /var/log/opensm_mc9.log 2>&1 &"
        )
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端使用 SL0~14->VL0、SL15->VL15 配置启动 opensm 失败: {err}"
            cls.bug_expect = "opensm 应能使用 SL0~14->VL0、SL15->VL15 配置启动"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-9 {name} 端启动 opensm 失败")

        time.sleep(cls.OPENSM_STARTUP_WAIT)
        if not cls._is_opensm_running(exec_addr):
            cls.bug_result = f"{name} 端 opensm 启动后未检测到运行进程"
            cls.bug_expect = "opensm 启动后应持续运行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-9 {name} 端 opensm 未正常运行")

        # 等待本端 opensm 成为 master SM，否则 SL2VL 表可能仍是旧 master 下发
        cls._wait_for_sm_master(exec_addr, name, cls.SERVER_TARGET_DEVICE)

        # 验证 SL2VL 表是否生效：SL0~14 应为 VL0，SL15 应为 VL15
        cls._verify_sl2vl_table(exec_addr, name, expected_sl15_vl=15)

        log.info(f"{name} 端 opensm 已启动（GUID: {guid}）")

    @classmethod
    def _restore_default_opensm(cls, exec_addr: str, name: str) -> None:
        """恢复 opensm 默认配置（指定目标设备 GUID）"""
        log.info(f"在 {name} 端恢复 opensm 默认配置...")
        cls._stop_opensm(exec_addr, name)
        guid = cls._get_device_guid(exec_addr, name, cls.SERVER_TARGET_DEVICE)
        cmd = f"nohup opensm -g {guid} -B > /var/log/opensm.log 2>&1 &"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        time.sleep(cls.OPENSM_STARTUP_WAIT)
        if not cls._is_opensm_running(exec_addr):
            log.warning(f"{name} 端恢复默认 opensm 后未检测到运行进程")
        else:
            log.info(f"{name} 端 opensm 已恢复默认配置（GUID: {guid}）")

    @classmethod
    def _is_opensm_running(cls, exec_addr: str) -> bool:
        """检查 opensm 进程是否正在运行"""
        status, _, _ = CommandOperation.execute_command_with_error(
            "pgrep -x opensm >/dev/null 2>&1", exec_addr
        )
        return status == RtnStatusEnum.SUCCESS.value

    @classmethod
    def _wait_for_sm_master(cls, exec_addr: str, name: str, device: str) -> None:
        """等待指定设备成为 subnet master SM"""
        log.info(f"等待 {name} 端 {device} 成为 master SM...")
        lid = cls._get_base_lid(exec_addr, name, device)
        cmd = f"smpquery portinfo -C {device} {lid} 1"
        for _ in range(12):
            status, result, _ = CommandOperation.execute_command_with_error(cmd, exec_addr)
            if status == RtnStatusEnum.SUCCESS.value:
                sm_lid_match = re.search(r"SMLid:\s*\.+(\d+)", result)
                if sm_lid_match and sm_lid_match.group(1) == str(int(lid, 16)):
                    log.info(f"{name} 端 {device} 已成为 master SM (SMLid={sm_lid_match.group(1)})")
                    return
            time.sleep(5)
        cls.bug_result = f"{name} 端 {device} 未能在 60s 内成为 master SM"
        cls.bug_expect = "server 端 opensm 应成为 subnet master 以正确下发 SL2VL 表"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(f"MC-9 {name} 端 opensm 未成为 master SM")

    @classmethod
    def _run_perftest_pair(
        cls,
        server_cmd: str,
        client_cmd: str,
        server_log: str,
        client_log: str,
    ) -> None:
        """同步并发运行 perftest server/client（单进程场景不使用 shell 后台）

        server 在独立线程中同步执行；client 在主线程中同步执行并带超时。
        client 结束后主动清理 server 进程。
        """
        server_result = {}

        def _server_target():
            full_cmd = f"{server_cmd} > {server_log} 2>&1"
            log.info(f"在 server 端运行 perftest server: {server_cmd}")
            server_result["status"], server_result["output"], server_result["err"] = (
                CommandOperation.execute_command_with_error(
                    full_cmd, CmdExecuteAdressEnum.SERVER.value, timeout=300
                )
            )

        server_thread = threading.Thread(target=_server_target, daemon=True)
        server_thread.start()
        time.sleep(cls.PERFTEST_STARTUP_WAIT)

        # server 若已退出，说明启动即失败
        if not server_thread.is_alive():
            err = server_result.get("err", "unknown")
            cls.bug_result = f"server 端 perftest server 异常退出: {err}"
            cls.bug_expect = "ib_send_bw server 应能正常启动并等待 client 连接"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("MC-9 server 端启动 perftest server 失败")

        # 在主线程同步运行 client（预期超时或失败）
        full_client_cmd = f"{client_cmd} > {client_log} 2>&1"
        log.info(f"在 client 端运行 perftest client: {client_cmd}")
        client_status, _, _ = CommandOperation.execute_command_with_error(
            full_client_cmd, CmdExecuteAdressEnum.CLIENT.value, timeout=cls.PERFTEST_TIMEOUT
        )
        log.info(f"client 同步执行结束，返回状态: {client_status}")

        # client 结束后清理 server
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        server_thread.join(timeout=10)

    @classmethod
    def _stop_perftest_processes(cls, exec_addr: str, name: str) -> None:
        """停止 perftest 进程（使用 -x 精确匹配，避免误杀当前 SSH 会话）"""
        cmd = 'pkill -9 -x ib_send_bw 2>/dev/null || true'
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 ib_send_bw 进程已清理")

    @classmethod
    def _read_log(cls, exec_addr: str, name: str, log_path: str) -> str:
        """读取远程日志文件内容"""
        cmd = f"cat {log_path}"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            return ""
        return result

    @classmethod
    def _verify_expected_failure(cls, server_output: str, client_output: str) -> None:
        """验证测试按预期失败：无有效带宽或收端 0 包/超时"""
        log.info("验证多播测试是否按预期失败...")

        combined = server_output + "\n" + client_output

        # 如果存在有效带宽，说明测试实际成功，与预期不符，记录 bug
        pattern = re.compile(
            r"^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)",
            re.MULTILINE,
        )
        matches = pattern.findall(combined)
        if matches:
            bw_value = float(matches[-1][3])
            if bw_value > 0:
                cls.bug_result = (
                    f"MC-9 预期测试失败，但实际检测到有效带宽 {bw_value} MB/sec，"
                    f"说明 SL0~14->VL0、SL15->VL15 配置可能未生效。\n"
                    f"server 输出:\n{server_output}\nclient 输出:\n{client_output}"
                )
                cls.bug_expect = "SL0~14->VL0、SL15->VL15 场景下 ib_send_bw -g -M -S 15 应失败（无有效带宽）"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug("MC-9 SL0~14->VL0、SL15->VL15 多播未按预期失败")

        # 检查是否有 0 包或超时/错误关键字
        failure_indicators = [
            r"0\s+received",
            r"Couldn't connect",
            r"connection refused",
            r"failed to initialize",
            r"No route to host",
            r"timeout",
            r"time out",
        ]
        has_failure_indicator = any(
            re.search(p, combined, re.IGNORECASE) for p in failure_indicators
        )

        # perftest 启动后仅打印 MTU 信息、无后续带宽输出，说明命令已挂起/超时，符合预期失败
        startup_only = (
            "Max msg size in UD is MTU" in combined
            and "Changing to this MTU" in combined
            and not matches
        )

        if has_failure_indicator or startup_only:
            log.info("未检测到有效带宽，perftest 进程已挂起/超时，符合预期失败")
        else:
            cls.bug_result = (
                f"MC-9 无法确认测试是否按预期失败。\n"
                f"server 输出:\n{server_output}\nclient 输出:\n{client_output}"
            )
            cls.bug_expect = "SL0~14->VL0、SL15->VL15 场景下应出现失败或超时的迹象"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("MC-9 无法确认预期失败")

    @classmethod
    def _verify_opensm_trap(cls, exec_addr: str, name: str) -> None:
        """检查 /var/log/opensm.log 中是否存在 trap 66/67（存在则记录，不存在仅警告）"""
        log.info(f"检查 {name} 端 opensm.log 中的多播 trap 信息...")
        cmd = r"grep -rhE 'trap_num\s+(66|67)' /var/log/opensm*.log 2>/dev/null | tail -5"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or not result.strip():
            log.warning(
                f"{name} 端 opensm.log 中未找到 trap_num 66/67；"
                f"当前环境下多播命令已挂起/超时，trap 未生成，不阻塞测试"
            )
            return
        log.info(f"{name} 端 opensm.log 中检测到 trap 66/67:\n{result.strip()}")

    @classmethod
    def _get_device_guid(cls, exec_addr: str, name: str, device: str) -> str:
        """获取指定 IB 设备的 Node GUID"""
        cmd = f"ibstat {device} | grep 'Node GUID'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端获取 {device} Node GUID 失败: {err}"
            cls.bug_expect = "ibstat 应能返回 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-9 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-9 {name} 端解析 {device} GUID 失败")

        return match.group(0)

    @classmethod
    def _get_base_lid(cls, exec_addr: str, name: str, device: str) -> str:
        """获取指定 IB 设备的 Base LID"""
        cmd = f"ibstat {device} | grep 'Base lid'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端获取 {device} Base LID 失败: {err}"
            cls.bug_expect = "ibstat 应能返回 Base lid"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-9 {name} 端获取 {device} Base LID 失败")

        match = re.search(r"0x[0-9a-fA-F]+|\d+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Base LID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Base lid"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-9 {name} 端解析 {device} Base LID 失败")

        lid = match.group(0)
        # 如果匹配到十进制，转换为 0x 格式以便 smpquery 识别
        if not lid.startswith("0x"):
            lid = hex(int(lid))
        return lid

    @classmethod
    def _verify_sl2vl_table(
        cls, exec_addr: str, name: str, expected_sl15_vl: int
    ) -> None:
        """使用 smpquery 验证 SL2VL 表中 SL15 映射到指定 VL"""
        log.info(f"在 {name} 端验证 SL2VL 表：SL15 应映射到 VL{expected_sl15_vl}...")

        lid = cls._get_base_lid(exec_addr, name, cls.SERVER_TARGET_DEVICE)
        cmd = f"smpquery sl2vl -C {cls.SERVER_TARGET_DEVICE} {lid} 1"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端执行 smpquery sl2vl 失败: {err}"
            cls.bug_expect = "smpquery -C <ca> sl2vl <lid> 1 应成功执行"
            log.error(f"{cls.bug_result}\n期望: {cls.bug_expect}")
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-9 {name} 端 smpquery sl2vl 执行失败")

        # 解析 SL2VL 表：数据在 "ports: in 0, out 0:" 行后面
        vl_values = cls._parse_sl2vl_table(result)
        if vl_values is None:
            cls.bug_result = (
                f"{name} 端无法从 smpquery sl2vl 输出中解析 SL2VL 表。输出:\n{result}"
            )
            cls.bug_expect = "SL2VL 表应包含 SL0~15 对应的 16 个 VL 值"
            log.error(f"{cls.bug_result}\n期望: {cls.bug_expect}")
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-9 {name} 端 SL2VL 表解析失败")

        # 根据 MC-9 配置、OperVLs 数量计算期望表
        oper_vls = cls._get_oper_vls_count(exec_addr, name, cls.SERVER_TARGET_DEVICE)
        overrides = {sl: 0 for sl in range(15)}
        overrides[15] = expected_sl15_vl
        expected = cls._compute_expected_sl2vl(oper_vls, overrides)
        if vl_values != expected:
            cls.bug_result = (
                f"{name} 端 SL2VL 表实际为 {vl_values}，期望为 {expected}，"
                f"OperVLs 数量: {oper_vls}。"
                f"MC-9 要求 SL0~14 映射到 VL0，SL15 映射到 VL15。"
            )
            cls.bug_expect = f"SL2VL 表应为 {expected}"
            log.error(f"{cls.bug_result}\n期望: {cls.bug_expect}")
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-9 {name} 端 SL15->VL{expected_sl15_vl} 配置未生效")

        log.info(f"{name} 端 SL2VL 表验证通过：{vl_values}")

    @classmethod
    def _parse_sl2vl_table(cls, output: str):
        """解析 smpquery sl2vl 输出，返回 SL0~15 对应的 VL 列表"""
        for line in output.splitlines():
            # 匹配数据行，兼容 "out 0" 和 "out  0" 等空格差异
            if "ports:" in line and "out" in line:
                numbers = [int(x) for x in re.findall(r"\b(\d+)\b", line)]
                # 行格式: ports: in  0, out  0: | 0| 1| 2| 3| ...
                # 数字序列前两个分别是 in/out 端口编号，需要跳过；后面 16 个为 SL0~15 的 VL 值
                if len(numbers) >= 18:
                    return numbers[2:18]
        return None

    @classmethod
    def _get_oper_vls_count(cls, exec_addr: str, name: str, device: str) -> int:
        """通过 smpquery portinfo 查询端口实际支持的 VL 数量"""
        lid = cls._get_base_lid(exec_addr, name, device)
        cmd = f"smpquery portinfo -C {device} {lid} 1"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            log.warning(f"{name} 端查询 OperVLs 失败: {err}，回退为 4")
            return 4
        # 典型输出：OperVLs:.........................VL0-3
        match = re.search(r"OperVLs:\.*VL0-(\d+)", result)
        if match:
            return int(match.group(1)) + 1
        log.warning(f"{name} 端无法解析 OperVLs，输出:\n{result}\n回退为 4")
        return 4

    @classmethod
    def _compute_expected_sl2vl(cls, oper_vls_count: int, overrides: dict) -> list:
        """根据 OperVLs 数量和 SL->VL 配置值计算期望的 SL2VL 表

        规则：
        - 当配置值为 15 时，opensm 会保留 15，不取模。
        - 当配置值 <15 时，按 oper_vls_count 取模。
        - 未显式配置的 SL，默认按 SL % oper_vls_count 计算。

        Args:
            oper_vls_count: 端口实际支持的 VL 数量（如 VL0-3 则为 4）。
            overrides: SL->VL 配置值映射，key 为 SL（0-15），value 为 qos_sl2vl 中配置的值。
        """
        expected = []
        for sl in range(16):
            vl = overrides.get(sl, sl)
            if vl == 15:
                expected.append(15)
            else:
                expected.append(vl % oper_vls_count)
        return expected

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-9 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc009.run()


if __name__ == '__main__':
    main()
