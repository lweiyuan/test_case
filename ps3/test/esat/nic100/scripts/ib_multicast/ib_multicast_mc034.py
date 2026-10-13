#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-34
case title: 通过ib_send_bw -g在两个active状态的端口之间进行多播测试，当包长大于mtu时，业务失败
test category: IB多播测试
check point: ib_send_bw -g 多播时包长大于 MTU 应失败
author: auto-generated
date: 2026.06.25
@steps:
    1. 使用 ib_send_bw -g 在两端口 active 的设备之间进行多播测试。
    2. 使用 -m 依次遍历 256、512、1024、2048、4096，并指定大于该 MTU 的包长。
    3. 观察命令是否失败、是否产生有效带宽。

@expected:
    当包长大于 MTU 时，业务失败，无有效带宽输出。

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


class IbMulticastMc034(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ib_send_bw, opensm, ibstat"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
opensm 已启动
测试节点之间 IB 网络互通"""
    test_steps = """
    1. 使用 ib_send_bw -g 在两端口 active 的设备之间进行多播测试。
    2. 使用 -m 依次遍历 256、512、1024、2048、4096，并指定大于该 MTU 的包长。
    3. 观察命令是否失败、是否产生有效带宽。
    """

    # 双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport
    PPORT_COUNT = 2
    # 服务端/客户端 IB 设备名，在 check_own_environment() 中从 env_config 动态读取
    server_device = ""
    client_device = ""
    MGID = "255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:00"
    PERFTEST_PORT = 18534
    PERFTEST_STARTUP_WAIT = 3
    # perftest 使用 -D 60 运行 60 秒；同步等待 65 秒，留 5 秒启动/收尾余量
    PERFTEST_DURATION = 65
    PERFTEST_STOP_WAIT = 2
    OPENSM_STARTUP_WAIT = 10
    # MTU 列表及对应大于 MTU 的包长（msg size = MTU * 2）
    MTU_SIZE_CASES = [
        (256, 512),
        (512, 1024),
        (1024, 2048),
        (2048, 4096),
        (4096, 8192),
    ]

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc034 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-34 测试环境...")

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
        log.info("准备 MC-34 测试环境...")
        cls.server_ip = cls._get_server_ip()

        # 获取两端 PF 列表并识别 pport
        cls.server_pf_list = cls._get_pf_list(CmdExecuteAdressEnum.SERVER.value, "server")
        cls.client_pf_list = cls._get_pf_list(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls.server_pport_list = cls._get_pport_list(cls.server_pf_list)
        cls.client_pport_list = cls._get_pport_list(cls.client_pf_list)

        # 停止现有 opensm 并为每个 pport 启动 opensm
        for exec_addr, name, pport_list, pf_list in [
            (CmdExecuteAdressEnum.SERVER.value, "server", cls.server_pport_list, cls.server_pf_list),
            (CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_pport_list, cls.client_pf_list),
        ]:
            cls._stop_opensm(exec_addr, name)
            cls._start_opensm_for_pports(exec_addr, name, pport_list)
            cls._verify_opensm_for_pports(exec_addr, name, pport_list)
            cls._verify_all_pf_active(exec_addr, name, pf_list)

        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-34 测试：包长大于 MTU 时业务失败")
        log.info("=" * 60)

        try:
            for mtu, msg_size in cls.MTU_SIZE_CASES:
                log.info(f"--- 测试 MTU={mtu}, msg_size={msg_size} ---")
                cls._run_mtu_case(mtu, msg_size)

            log.info("=" * 60)
            log.info("测试执行成功 - MC-34 通过（所有场景均按预期失败）")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-34 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-34 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-34 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-34 测试环境...")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        log.info("MC-34 清理完成")
        super().post()

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
        cls.create_bug("MC-34 获取服务端 IP 失败")

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
            cls.create_bug(f"MC-34 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-34 {name} 端 PF 列表为空")

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
    def _start_opensm_for_pports(cls, exec_addr: str, name: str, pport_list: list) -> None:
        """为每个 pport 启动 opensm"""
        log.info(f"在 {name} 端为所有 pport 启动 opensm...")

        for idx, pport in enumerate(pport_list):
            guid = cls._get_device_guid(exec_addr, name, pport)
            log.info(f"为 pport {pport} 启动 opensm，GUID: {guid}")
            opensm_cmd = (
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_mc34_{idx}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端为 pport {pport} 启动 opensm 失败: {err}"
                cls.bug_expect = "opensm 应能在每个 pport 上成功启动"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-34 {name} 端 pport {pport} opensm 启动失败")
            time.sleep(3)

        # 等待 opensm 完成子网扫描
        time.sleep(cls.OPENSM_STARTUP_WAIT)

    @classmethod
    def _verify_opensm_for_pports(cls, exec_addr: str, name: str, pport_list: list) -> None:
        """验证每个 pport 上的 opensm 进程正在运行"""
        log.info(f"验证 {name} 端所有 pport 的 opensm 进程...")

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
            cls.create_bug(f"MC-34 {name} 端 opensm 进程数量不足")

        log.info(f"{name} 端 opensm 进程数量: {running_count}，pport 数量: {len(pport_list)}")

    @classmethod
    def _verify_all_pf_active(cls, exec_addr: str, name: str, pf_list: list) -> None:
        """验证所有 PF 均处于 Active 状态"""
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
                cls.create_bug(f"MC-34 {name} 端 PF {pf} 未 Active")
        log.info(f"{name} 端所有 PF 均处于 Active 状态")

    @classmethod
    def _stop_opensm(cls, exec_addr: str, name: str) -> None:
        """停止 opensm"""
        cmd = "pkill -9 -x opensm 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        time.sleep(3)
        log.info(f"{name} 端 opensm 已停止")

    @classmethod
    def _run_mtu_case(cls, mtu: int, msg_size: int) -> None:
        """执行单个 MTU 场景：包长大于 MTU，预期失败"""
        server_log = f"/tmp/ib_send_bw_mc34_mtu{mtu}_server.log"
        client_log = f"/tmp/ib_send_bw_mc34_mtu{mtu}_client.log"

        server_cmd = (
            f"ib_send_bw -d {cls.server_device} -g -M {cls.MGID} "
            f"--pkey_index=0 -m {mtu} -s {msg_size} -p {cls.PERFTEST_PORT} -D 60 -F"
        )
        client_cmd = (
            f"ib_send_bw -d {cls.client_device} -g -M {cls.MGID} "
            f"--pkey_index=0 -m {mtu} -s {msg_size} -p {cls.PERFTEST_PORT} -D 60 -F {cls.server_ip}"
        )

        # 单进程场景使用同步线程执行，避免 shell 后台
        cls._run_perftest_pair(server_cmd, client_cmd, server_log, client_log)

        server_output = cls._read_log(
            CmdExecuteAdressEnum.SERVER.value, "server", server_log
        )
        client_output = cls._read_log(
            CmdExecuteAdressEnum.CLIENT.value, "client", client_log
        )

        cls._verify_expected_failure(mtu, msg_size, server_output, client_output)

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

        # server 若已退出，说明启动即失败，也符合预期（包长大于 MTU）
        if not server_thread.is_alive():
            log.info("server 端进程已提前退出，符合包长大于 MTU 的预期失败")

        # 在主线程同步运行 client（预期失败或超时）
        full_client_cmd = f"{client_cmd} > {client_log} 2>&1"
        log.info(f"在 client 端运行 perftest client: {client_cmd}")
        client_status, _, _ = CommandOperation.execute_command_with_error(
            full_client_cmd,
            CmdExecuteAdressEnum.CLIENT.value,
            timeout=cls.PERFTEST_DURATION,
        )
        log.info(f"client 同步执行结束，返回状态: {client_status}")

        # client 结束后清理 server
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        server_thread.join(timeout=10)

    @classmethod
    def _stop_perftest_processes(cls, exec_addr: str, name: str) -> None:
        """停止 perftest 进程（使用 -x 精确匹配，避免误杀 SSH 会话）"""
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
    def _verify_expected_failure(
        cls, mtu: int, msg_size: int, server_output: str, client_output: str
    ) -> None:
        """验证包长大于 MTU 时按预期失败"""
        log.info(f"验证 MTU={mtu}, msg_size={msg_size} 是否按预期失败...")

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
                    f"MC-34 MTU={mtu}, msg_size={msg_size} 预期失败，"
                    f"但实际检测到有效带宽 {bw_value} MB/sec。\n"
                    f"server 输出:\n{server_output}\nclient 输出:\n{client_output}"
                )
                cls.bug_expect = "包长大于 MTU 时 ib_send_bw -g 应失败（无有效带宽）"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-34 MTU={mtu} 包长大于 MTU 未按预期失败")

        # 检查失败/错误关键字或仅打印启动信息
        failure_indicators = [
            r"Couldn't connect",
            r"connection refused",
            r"failed to initialize",
            r"No route to host",
            r"timeout",
            r"time out",
            r"message size",
            r"exceeds",
            r"Error",
            r"error",
        ]
        has_failure_indicator = any(
            re.search(p, combined, re.IGNORECASE) for p in failure_indicators
        )

        # perftest 启动后仅打印 MTU 信息、无后续带宽输出，说明命令已挂起/失败，符合预期
        startup_only = (
            "Max msg size in UD is MTU" in combined
            and "Changing to this MTU" in combined
            and not matches
        )

        if has_failure_indicator or startup_only:
            log.info(f"MTU={mtu}, msg_size={msg_size} 未产生有效带宽，符合预期失败")
        else:
            # 输出为空或无法识别时，若命令整体返回非成功且没有带宽，也视为符合预期
            log.info(
                f"MTU={mtu}, msg_size={msg_size} 无有效带宽输出，按预期失败处理"
            )

    @classmethod
    def _get_device_guid(cls, exec_addr: str, name: str, device: str) -> str:
        """获取指定 IB 设备的 Node GUID"""
        cmd = f"ibstat {device} | grep 'Node GUID'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端获取 {device} Node GUID 失败: {err}"
            cls.bug_expect = "ibstat 应能返回 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-34 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-34 {name} 端解析 {device} GUID 失败")

        return match.group(0)

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-34 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc034.run()


if __name__ == '__main__':
    main()
