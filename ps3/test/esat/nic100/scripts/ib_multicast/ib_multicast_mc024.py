#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-24
case title: 某节点同时存在多播（服务端+客户端）和单播业务，业务成功（如服务器内存、cpu资源充裕）
test category: IB多播测试
check point: 多播与单播业务并发时两端均成功
author: auto-generated
date: 2026.06.25
@steps:
    1. 同时启动多播业务（服务端+客户端）：ib_send_bw -g。
    2. 同时启动单播业务：
       服务端：ib_read_bw --run_infinitely
       客户端：ib_read_bw --run_infinitely <server_ip>
    3. 运行一段时间后停止并检查两者是否均产生有效带宽。

@expected:
    多播和单播业务同时成功，均有有效带宽。

@changelog:
2026.06.25 - 根据 IB-MultiCast_ForAI-测试用例.xlsx（excel_dump.txt 第 19 行）生成
- 关联需求：3.1.20.1~3.1.20.5 IB多播支持
- 单进程场景使用 Python threading 同步运行 server/client，不再使用 shell 后台
- 使用 pkill -9 -x <process> 清理，避免误杀 SSH 会话
2026.06.26 - 修正：识别所有 pport 并为每个 pport 启动并检查 opensm；prepare/post 补充 super() 调用
"""

import os
import time
import re
import threading
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, BugTypeEnum, CmdExecuteAdressEnum
from scripts.script_libs.script_base import ScriptBase, SxeException


class IbMulticastMc024(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ib_send_bw, ib_read_bw, opensm, ibstat"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
opensm 已启动
测试节点之间 IB 网络互通
服务器内存、CPU 资源充裕"""
    test_steps = """
    1. 启动多播 server 与 client（ib_send_bw -g）。
    2. 同时启动单播 server 与 client（ib_read_bw --run_infinitely）。
    3. 并发运行一段时间后停止进程。
    4. 检查多播与单播日志中是否均有有效带宽。
    """

    TARGET_DEVICE = "mlx5_0"
    MGID = "255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:00"
    PERFTEST_MCAST_PORT = 18524
    PERFTEST_UCAST_PORT = 18525
    PERFTEST_STARTUP_WAIT = 3
    PERFTEST_DURATION = 20
    PERFTEST_STOP_WAIT = 2
    PERFTEST_CMD_TIMEOUT = 300

    # 双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport
    PPORT_COUNT = 2
    OPENSM_STARTUP_WAIT = 10

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc024 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-24 测试环境...")

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
        super().prepare()
        log.info("准备 MC-24 测试环境...")
        cls.server_ip = cls._get_server_ip()

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client"),
        ]:
            pf_list = cls._get_pf_list(exec_addr, name)
            pport_list = cls._get_pport_list(pf_list)
            setattr(cls, f"pf_list_{name}", pf_list)
            setattr(cls, f"pport_list_{name}", pport_list)

            cls._stop_opensm(exec_addr, name)
            cls._start_opensm_for_pports(exec_addr, name)
            cls._verify_opensm_for_pports(exec_addr, name)
            cls._verify_all_pf_active(exec_addr, name, pf_list)

        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-24 测试：多播与单播并发")
        log.info("=" * 60)

        try:
            # 多播 server/client 命令
            mcast_server_log = "/tmp/ib_send_bw_mc24_server.log"
            mcast_client_log = "/tmp/ib_send_bw_mc24_client.log"
            mcast_server_cmd = (
                f"ib_send_bw -d {cls.TARGET_DEVICE} -g -M {cls.MGID} "
                f"-p {cls.PERFTEST_MCAST_PORT} -F --run_infinitely"
            )
            mcast_client_cmd = (
                f"ib_send_bw -d {cls.TARGET_DEVICE} -g -M {cls.MGID} "
                f"-p {cls.PERFTEST_MCAST_PORT} -F --run_infinitely {cls.server_ip}"
            )

            # 单播 server/client 命令
            ucast_server_log = "/tmp/ib_read_bw_mc24_server.log"
            ucast_client_log = "/tmp/ib_read_bw_mc24_client.log"
            ucast_server_cmd = (
                f"ib_read_bw -d {cls.TARGET_DEVICE} "
                f"-p {cls.PERFTEST_UCAST_PORT} -F --run_infinitely"
            )
            ucast_client_cmd = (
                f"ib_read_bw -d {cls.TARGET_DEVICE} "
                f"-p {cls.PERFTEST_UCAST_PORT} -F --run_infinitely {cls.server_ip}"
            )

            # 使用线程同时启动多播对与单播对
            mcast_threads = cls._run_pair_in_threads(
                "多播",
                mcast_server_cmd,
                mcast_client_cmd,
                mcast_server_log,
                mcast_client_log,
            )
            ucast_threads = cls._run_pair_in_threads(
                "单播",
                ucast_server_cmd,
                ucast_client_cmd,
                ucast_server_log,
                ucast_client_log,
            )

            # 运行指定时长
            log.info(f"多播与单播并发运行 {cls.PERFTEST_DURATION}s...")
            time.sleep(cls.PERFTEST_DURATION)

            # 停止所有 perftest 进程
            cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
            cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
            time.sleep(cls.PERFTEST_STOP_WAIT)

            # 等待线程结束
            for t in mcast_threads + ucast_threads:
                t.join(timeout=10)

            # 读取日志并验证
            mcast_server_output = cls._read_log(
                CmdExecuteAdressEnum.SERVER.value, "server", mcast_server_log
            )
            mcast_client_output = cls._read_log(
                CmdExecuteAdressEnum.CLIENT.value, "client", mcast_client_log
            )
            ucast_server_output = cls._read_log(
                CmdExecuteAdressEnum.SERVER.value, "server", ucast_server_log
            )
            ucast_client_output = cls._read_log(
                CmdExecuteAdressEnum.CLIENT.value, "client", ucast_client_log
            )

            cls._verify_pair_output("多播", mcast_server_output, mcast_client_output)
            cls._verify_pair_output("单播", ucast_server_output, ucast_client_output)

            log.info("=" * 60)
            log.info("测试执行成功 - MC-24 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-24 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-24 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-24 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-24 测试环境...")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        log.info("MC-24 清理完成：opensm 已停止")
        super().post()

    @classmethod
    def _get_server_ip(cls) -> str:
        """获取服务端 IP"""
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

        cls.bug_result = "无法获取服务端 IP 地址"
        cls.bug_expect = "应能获取服务端可达 IP"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug("MC-24 获取服务端 IP 失败")

    @classmethod
    def _run_pair_in_threads(
        cls,
        name: str,
        server_cmd: str,
        client_cmd: str,
        server_log: str,
        client_log: str,
    ) -> list:
        """在独立线程中同步运行一对 server/client"""
        server_result = {}
        client_result = {}

        def _server_target():
            full_cmd = f"{server_cmd} > {server_log} 2>&1"
            log.info(f"在 server 端启动 {name} server: {server_cmd}")
            server_result["status"], server_result["output"], server_result["err"] = (
                CommandOperation.execute_command_with_error(
                    full_cmd, CmdExecuteAdressEnum.SERVER.value, timeout=cls.PERFTEST_CMD_TIMEOUT
                )
            )

        def _client_target():
            full_cmd = f"{client_cmd} > {client_log} 2>&1"
            log.info(f"在 client 端启动 {name} client: {client_cmd}")
            client_result["status"], client_result["output"], client_result["err"] = (
                CommandOperation.execute_command_with_error(
                    full_cmd, CmdExecuteAdressEnum.CLIENT.value, timeout=cls.PERFTEST_CMD_TIMEOUT
                )
            )

        server_thread = threading.Thread(target=_server_target, daemon=True)
        client_thread = threading.Thread(target=_client_target, daemon=True)

        server_thread.start()
        time.sleep(cls.PERFTEST_STARTUP_WAIT)
        client_thread.start()

        # 若 server 启动即退出，说明启动失败
        if not server_thread.is_alive():
            err = server_result.get("err", "unknown")
            cls.bug_result = f"{name} server 启动后异常退出: {err}"
            cls.bug_expect = f"{name} server 应能正常启动并等待 client 连接"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-24 {name} server 启动失败")

        return [server_thread, client_thread]

    @classmethod
    def _stop_perftest_processes(cls, exec_addr: str, name: str) -> None:
        """停止 perftest 进程（精确匹配，避免误杀 SSH 会话）"""
        for proc in ["ib_send_bw", "ib_read_bw"]:
            cmd = f'pkill -9 -x {proc} 2>/dev/null || true'
            CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 ib_send_bw/ib_read_bw 进程已清理")

    @classmethod
    def _read_log(cls, exec_addr: str, name: str, log_path: str) -> str:
        """读取远程日志文件内容"""
        cmd = f"cat {log_path}"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            log.warning(f"{name} 端读取日志 {log_path} 失败: {err}")
            return ""
        return result

    @classmethod
    def _verify_pair_output(cls, name: str, server_output: str, client_output: str) -> None:
        """验证一对 server/client 输出中是否存在有效带宽"""
        log.info(f"检查 {name} 业务结果...")
        combined = server_output + "\n" + client_output

        pattern = re.compile(
            r"^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)",
            re.MULTILINE,
        )
        matches = pattern.findall(combined)
        if not matches:
            cls.bug_result = f"{name} 业务未找到有效带宽输出。\nserver 输出:\n{server_output}\nclient 输出:\n{client_output}"
            cls.bug_expect = f"{name} 业务应产生有效带宽"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-24 {name} 业务无有效带宽")

        bw_value = float(matches[-1][3])
        if bw_value <= 0:
            cls.bug_result = f"{name} 业务带宽为 0。\nserver 输出:\n{server_output}\nclient 输出:\n{client_output}"
            cls.bug_expect = f"{name} 业务带宽应大于 0"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-24 {name} 业务带宽为 0")

        log.info(f"{name} 业务通过，带宽: {bw_value} MB/sec")

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
            cls.create_bug(f"MC-24 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-24 {name} 端 PF 列表为空")

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
    def _start_opensm_for_pports(cls, exec_addr: str, name: str) -> None:
        """为每个 pport 启动 opensm"""
        log.info(f"在 {name} 端为所有 pport 启动 opensm...")
        pport_list = getattr(cls, f"pport_list_{name}")

        for idx, pport in enumerate(pport_list):
            guid = cls._get_device_guid(exec_addr, name, pport)
            log.info(f"为 pport {pport} 启动 opensm，GUID: {guid}")
            opensm_cmd = (
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_mc24_{idx}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端为 pport {pport} 启动 opensm 失败: {err}"
                cls.bug_expect = "opensm 应能在每个 pport 上成功启动"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-24 {name} 端 pport {pport} opensm 启动失败")
            time.sleep(3)

        # 等待 opensm 完成子网扫描
        time.sleep(cls.OPENSM_STARTUP_WAIT)

    @classmethod
    def _verify_opensm_for_pports(cls, exec_addr: str, name: str) -> None:
        """验证每个 pport 上的 opensm 进程正在运行"""
        log.info(f"验证 {name} 端所有 pport 的 opensm 进程...")
        pport_list = getattr(cls, f"pport_list_{name}")

        if not cls._is_opensm_running(exec_addr):
            cls.bug_result = f"{name} 端未检测到任何 opensm 进程"
            cls.bug_expect = "每个 pport 上应运行一个 opensm 实例"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-24 {name} 端 opensm 未运行")

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
            cls.create_bug(f"MC-24 {name} 端 opensm 进程数量不足")

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
                cls.create_bug(f"MC-24 {name} 端 PF {pf} 未 Active")
        log.info(f"{name} 端所有 PF 均处于 Active 状态")

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
    def _get_device_guid(cls, exec_addr: str, name: str, device: str) -> str:
        """获取指定 IB 设备的 Node GUID"""
        cmd = f"ibstat {device} | grep 'Node GUID'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端获取 {device} Node GUID 失败: {err}"
            cls.bug_expect = "ibstat 应能返回 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-24 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-24 {name} 端解析 {device} GUID 失败")

        return match.group(0)

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-24 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc024.run()


if __name__ == '__main__':
    main()
