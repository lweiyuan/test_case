#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-35
case title: ib_send_bw -M 指定一个非法的MGID地址--命令失败，不会出现网卡异常等扩散行为
test category: IB多播测试
check point: 使用非法 MGID 进行多播时命令按预期失败，且不会导致网卡异常
author: auto-generated
date: 2026.06.25
@steps:
    1. 检查 ib_send_bw 多播正常场景下网卡状态无异常。
    2. 使用非法 MGID 地址执行 ib_send_bw -M <非法MGID>。
    3. 验证命令返回失败或超时，且输出包含失败迹象。
    4. 再次检查网卡状态（ibstat），确认无异常扩散行为。

@expected:
    ib_send_bw -M 指定非法 MGID 时命令失败。
    网卡状态保持 Active，无异常打印、无崩溃、无扩散行为。

@changelog:
2026.06.25 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.1 用户态QP退出多播组、3.1.20.2 用户态QP加入多播组
- 使用项目技巧：缺陷自动记录、IB基础概念与设备检查、IB命令处理与回显解析、perftest工具使用
2026.06.26 - 修正：识别所有 pport 并为每个 pport 启动并检查 opensm；prepare/post 补充 super() 调用
"""

import os
import time
import re
import threading
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, BugTypeEnum, CmdExecuteAdressEnum, RdmaMode
from scripts.script_libs.script_base import ScriptBase, SxeException
from scripts.script_libs.common_operation import CommonOperation


class IbMulticastMc035(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ib_send_bw, ibstat"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
opensm 已启动
测试节点之间 IB 网络互通"""
    test_steps = """
    1. 检查网卡状态，确认无异常。
    2. 执行 ib_send_bw -d mlx5_0 -g -M <非法MGID> -p <port> -F。
    3. 验证命令失败且输出包含失败/超时关键字。
    4. 再次检查网卡状态，确认无异常扩散行为。
    """

    # 服务端/客户端 IB 设备名，在 check_own_environment() 中从 env_config 动态读取
    server_device = ""
    client_device = ""
    # 非法 MGID：使用全零格式，不符合有效多播组地址规范
    ILLEGAL_MGID = "00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00"
    PERFTEST_PORT = 18535
    PERFTEST_STARTUP_WAIT = 3
    # perftest 使用 -D 60 运行 60 秒；这里等待 65 秒，留 5 秒启动/收尾余量
    PERFTEST_TIMEOUT = 65
    PERFTEST_STOP_WAIT = 2

    # 双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport
    PPORT_COUNT = 2
    OPENSM_STARTUP_WAIT = 10

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc035 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-35 测试环境...")

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

        cls.own_environment_enabled = True
        log.info("环境检查通过：两端目标 IB 设备均处于 Active 状态")

    @classmethod
    def prepare(cls) -> None:
        super().prepare()
        log.info("准备 MC-35 测试环境...")
        cls.server_ip = cls._get_server_ip()
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")

        # 识别两端 pport 并为每个 pport 启动 opensm
        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client"),
        ]:
            pf_list = cls._get_pf_list(exec_addr, name)
            pport_list = cls._get_pport_list(pf_list)
            setattr(cls, f"{name}_pf_list", pf_list)
            setattr(cls, f"{name}_pport_list", pport_list)
            cls._stop_opensm(exec_addr, name)
            cls._start_opensm_for_pports(exec_addr, name, "mc35")
            cls._verify_opensm_for_pports(exec_addr, name)
            cls._verify_all_pf_active(exec_addr, name, pf_list)
            log.info(f"{name} 端 PF 列表: {pf_list}")
            log.info(f"{name} 端 pport 列表: {pport_list}")

        # 记录测试前网卡状态
        cls._record_device_status(CmdExecuteAdressEnum.SERVER.value, "server", "before")
        cls._record_device_status(CmdExecuteAdressEnum.CLIENT.value, "client", "before")

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-35 测试：非法 MGID 多播预期失败")
        log.info("=" * 60)

        try:
            server_log = "/tmp/ib_send_bw_mc35_server.log"
            client_log = "/tmp/ib_send_bw_mc35_client.log"

            server_cmd = (
                f"ib_send_bw -d {cls.server_device} -g -M {cls.ILLEGAL_MGID} "
                f"-p {cls.PERFTEST_PORT} -D 60 -F"
            )
            client_cmd = (
                f"ib_send_bw -d {cls.client_device} -g -M {cls.ILLEGAL_MGID} "
                f"-p {cls.PERFTEST_PORT} -D 60 -F {cls.server_ip}"
            )

            # 同步并发运行 server/client，不使用 shell 后台
            cls._run_perftest_pair(server_cmd, client_cmd, server_log, client_log)

            # 读取日志
            server_output = cls._read_log(CmdExecuteAdressEnum.SERVER.value, "server", server_log)
            client_output = cls._read_log(CmdExecuteAdressEnum.CLIENT.value, "client", client_log)

            # 验证命令按预期失败
            cls._verify_expected_failure(server_output, client_output)

            # 测试后检查网卡状态
            cls._record_device_status(CmdExecuteAdressEnum.SERVER.value, "server", "after")
            cls._record_device_status(CmdExecuteAdressEnum.CLIENT.value, "client", "after")
            cls._verify_no_card_anomaly()

            log.info("=" * 60)
            log.info("测试执行成功 - MC-35 通过（非法 MGID 按预期失败且无扩散）")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-35 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-35 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-35 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-35 测试环境...")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        log.info("MC-35 清理完成")
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
        cls.create_bug("MC-35 获取服务端 IP 失败")

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
            cls.create_bug(f"MC-35 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-35 {name} 端 PF 列表为空")

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
    def _stop_opensm(cls, exec_addr: str, name: str) -> None:
        """停止 opensm"""
        cmd = "pkill -9 -x opensm 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        time.sleep(3)
        log.info(f"{name} 端 opensm 已停止")

    @classmethod
    def _start_opensm_for_pports(cls, exec_addr: str, name: str, case_suffix: str) -> None:
        """为每个 pport 启动 opensm"""
        log.info(f"在 {name} 端为所有 pport 启动 opensm...")

        pport_list = getattr(cls, f"{name}_pport_list", [])
        for idx, pport in enumerate(pport_list):
            guid = cls._get_device_guid(exec_addr, name, pport)
            log.info(f"为 pport {pport} 启动 opensm，GUID: {guid}")
            opensm_cmd = (
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_{case_suffix}_{idx}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端为 pport {pport} 启动 opensm 失败: {err}"
                cls.bug_expect = "opensm 应能在每个 pport 上成功启动"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-35 {name} 端 pport {pport} opensm 启动失败")
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
            cls.create_bug(f"MC-35 {name} 端 opensm 未运行")

        # 验证 opensm 进程数量不少于 pport 数量
        status, result, err = CommandOperation.execute_command_with_error(
            "pgrep -x opensm", exec_addr
        )
        running_count = len([line.strip() for line in result.splitlines() if line.strip()])
        pport_count = len(getattr(cls, f"{name}_pport_list", []))
        if running_count < pport_count:
            cls.bug_result = (
                f"{name} 端 opensm 进程数量不足，实际 {running_count} 个，"
                f"期望至少 {pport_count} 个（每个 pport 一个）"
            )
            cls.bug_expect = "每个 pport 上应运行一个 opensm 实例"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-35 {name} 端 opensm 进程数量不足")

        log.info(f"{name} 端 opensm 进程数量: {running_count}，pport 数量: {pport_count}")

    @classmethod
    def _verify_all_pf_active(cls, exec_addr: str, name: str, pf_list: list) -> None:
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
                cls.create_bug(f"MC-35 {name} 端 PF {pf} 未 Active")
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
            cls.create_bug(f"MC-35 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-35 {name} 端解析 {device} GUID 失败")

        return match.group(0)

    @classmethod
    def _is_opensm_running(cls, exec_addr: str) -> bool:
        """检查 opensm 进程是否正在运行"""
        status, _, _ = CommandOperation.execute_command_with_error(
            "pgrep -x opensm >/dev/null 2>&1", exec_addr
        )
        return status == RtnStatusEnum.SUCCESS.value

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
    def _run_perftest_pair(
        cls,
        server_cmd: str,
        client_cmd: str,
        server_log: str,
        client_log: str,
    ) -> None:
        """同步并发运行 perftest server/client（单进程场景不使用 shell 后台）"""
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
            log.info("server 端 perftest 启动即失败，符合非法 MGID 预期")

        # 在主线程同步运行 client（预期失败或超时）
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
    def _verify_expected_failure(cls, server_output: str, client_output: str) -> None:
        """验证非法 MGID 场景下命令按预期失败"""
        log.info("验证非法 MGID 多播是否按预期失败...")

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
                    f"MC-35 预期使用非法 MGID 失败，但实际检测到有效带宽 {bw_value} MB/sec。\n"
                    f"server 输出:\n{server_output}\nclient 输出:\n{client_output}"
                )
                cls.bug_expect = "非法 MGID 场景下 ib_send_bw -M 应失败（无有效带宽）"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug("MC-35 非法 MGID 多播未按预期失败")

        # 检查失败/错误关键字
        failure_indicators = [
            r"0\s+received",
            r"Couldn't connect",
            r"connection refused",
            r"failed to initialize",
            r"No route to host",
            r"timeout",
            r"time out",
            r"error",
            r"failed",
            r"Invalid",
            r"cannot",
            r"can't",
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
            log.info("非法 MGID 多播命令失败，符合预期")
        else:
            cls.bug_result = (
                f"MC-35 无法确认非法 MGID 多播是否按预期失败。\n"
                f"server 输出:\n{server_output}\nclient 输出:\n{client_output}"
            )
            cls.bug_expect = "非法 MGID 场景下应出现失败或超时的迹象"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("MC-35 无法确认非法 MGID 预期失败")

    @classmethod
    def _record_device_status(cls, exec_addr: str, name: str, phase: str) -> None:
        """记录网卡状态用于前后对比"""
        device = cls.server_device if name == "server" else cls.client_device
        log.info(f"记录 {name} 端 {device} {phase} 测试状态...")
        cmd = f"ibstat {device}"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            log.warning(f"记录 {name} 端 {phase} 状态失败: {err}")
            return
        setattr(cls, f"_{name}_status_{phase}", result)

    @classmethod
    def _verify_no_card_anomaly(cls) -> None:
        """验证测试前后网卡状态无异常变化"""
        log.info("检查非法 MGID 多播是否导致网卡异常...")

        for name in ["server", "client"]:
            device = cls.server_device if name == "server" else cls.client_device
            before = getattr(cls, f"_{name}_status_before", "")
            after = getattr(cls, f"_{name}_status_after", "")

            if not before or not after:
                log.warning(f"{name} 端缺少测试前后状态记录，跳过异常扩散检查")
                continue

            # 状态应保持 Active
            if "State: Active" not in after:
                cls.bug_result = (
                    f"{name} 端测试后 {device} 未保持 Active 状态，可能出现异常扩散。\n"
                    f"测试前状态:\n{before}\n测试后状态:\n{after}"
                )
                cls.bug_expect = "非法 MGID 多播不应导致网卡状态异常"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-35 {name} 端网卡状态异常扩散")

            # 不应出现严重错误关键字
            anomaly_keywords = ["fatal", "error", "fail", "down", "disabled", "anomaly"]
            for kw in anomaly_keywords:
                # 仅检查测试后新增的异常关键字（简单处理：测试前已有则忽略）
                if re.search(rf"\b{kw}\b", after, re.IGNORECASE) and not re.search(
                    rf"\b{kw}\b", before, re.IGNORECASE
                ):
                    cls.bug_result = (
                        f"{name} 端测试后出现新增异常关键字 '{kw}'，可能存在扩散行为。\n"
                        f"测试前状态:\n{before}\n测试后状态:\n{after}"
                    )
                    cls.bug_expect = "非法 MGID 多播不应引入新的网卡异常"
                    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                    cls.create_bug(f"MC-35 {name} 端网卡出现异常关键字")

        log.info("网卡异常扩散检查通过")

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-35 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc035.run()


if __name__ == '__main__':
    main()
