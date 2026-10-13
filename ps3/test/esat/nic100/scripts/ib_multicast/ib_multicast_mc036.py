#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-36
case title: ib_send_bw -c RC指定RC进行多播，实际为UD多播（回显可以看到UD）
test category: IB多播测试
check point: 显式指定 -c RC 时，ib_send_bw 多播实际仍为 UD 并输出 UD 信息
author: auto-generated
date: 2026.06.25
@steps:
    1. 在两节点 Active 端口上启动 ib_send_bw -c RC -g 多播 server。
    2. 启动 ib_send_bw -c RC -g 多播 client 连接 server。
    3. 检查命令回显中是否包含 "UD" 或 "Unreliable Datagram" 字样，确认实际传输类型为 UD。
    4. 验证业务成功产生有效带宽。

@expected:
    多播业务成功。
    命令回显可见 UD（或提示多播强制使用 UD），说明 -c RC 不影响多播实际传输类型。

@changelog:
2026.06.25 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.1 用户态QP退出多播组、3.1.20.2 用户态QP加入多播组
- 使用项目技巧：缺陷自动记录、IB基础概念与设备检查、IB命令处理与回显解析、perftest工具使用
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


class IbMulticastMc036(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ib_send_bw, ibstat"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
opensm 已启动
测试节点之间 IB 网络互通"""
    test_steps = """
    1. 启动 ib_send_bw -d mlx5_0 -c RC -g -M <MGID> -p <port> -F server。
    2. 启动 ib_send_bw -d mlx5_0 -c RC -g -M <MGID> -p <port> -F client <server_ip>。
    3. 检查输出中是否包含 UD 关键字。
    4. 验证有效带宽输出。
    """

    # 服务端/客户端 IB 设备名，在 check_own_environment() 中从 env_config 动态读取
    server_device = ""
    client_device = ""
    MGID = "255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:00"
    PERFTEST_PORT = 18536
    PERFTEST_STARTUP_WAIT = 3
    # perftest 使用 -D 60 运行 60 秒；这里等待 65 秒，留 5 秒启动/收尾余量
    PERFTEST_DURATION = 65
    # client 同步执行，timeout 需覆盖 60 秒测试 + 启动余量
    PERFTEST_TIMEOUT = 70
    PERFTEST_STOP_WAIT = 2

    # 双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport
    PPORT_COUNT = 2
    OPENSM_STARTUP_WAIT = 10

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc036 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-36 测试环境...")

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
        log.info("准备 MC-36 测试环境...")
        cls.server_ip = cls._get_server_ip()

        # 识别两端 pport 并确保每个 pport 都启动 opensm
        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client"),
        ]:
            cls.pf_list = cls._get_pf_list(exec_addr, name)
            cls.pport_list = cls._get_pport_list(cls.pf_list)
            cls._stop_opensm(exec_addr, name)
            cls._start_opensm_for_pports(exec_addr, name)
            cls._verify_opensm_for_pports(exec_addr, name)
            cls._verify_all_pf_active(exec_addr, name)
            log.info(f"{name} 端 PF 列表: {cls.pf_list}")
            log.info(f"{name} 端 pport 列表: {cls.pport_list}")

        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-36 测试：-c RC 多播实际为 UD")
        log.info("=" * 60)

        try:
            server_log = "/tmp/ib_send_bw_mc36_server.log"
            client_log = "/tmp/ib_send_bw_mc36_client.log"

            server_cmd = (
                f"ib_send_bw -d {cls.server_device} -c RC -g -M {cls.MGID} "
                f"-p {cls.PERFTEST_PORT} -D 60 -F"
            )
            client_cmd = (
                f"ib_send_bw -d {cls.client_device} -c RC -g -M {cls.MGID} "
                f"-p {cls.PERFTEST_PORT} -D 60 -F {cls.server_ip}"
            )

            # 同步并发运行 server/client，不使用 shell 后台
            cls._run_perftest_pair(server_cmd, client_cmd, server_log, client_log)

            # 读取日志
            server_output = cls._read_log(CmdExecuteAdressEnum.SERVER.value, "server", server_log)
            client_output = cls._read_log(CmdExecuteAdressEnum.CLIENT.value, "client", client_log)
            combined = server_output + "\n" + client_output

            # 验证输出中包含 UD 关键字
            cls._verify_ud_in_output(combined)

            # 验证业务成功
            cls._verify_bandwidth(client_output)

            log.info("=" * 60)
            log.info("测试执行成功 - MC-36 通过（-c RC 实际为 UD 多播）")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-36 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-36 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-36 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-36 测试环境...")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        log.info("MC-36 清理完成")
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
        cls.create_bug("MC-36 获取服务端 IP 失败")

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
            err = server_result.get("err", "unknown")
            cls.bug_result = f"server 端 perftest server 异常退出: {err}"
            cls.bug_expect = "ib_send_bw -c RC -g server 应能正常启动并等待 client 连接"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("MC-36 server 端启动 perftest server 失败")

        # 在主线程同步运行 client
        full_client_cmd = f"{client_cmd} > {client_log} 2>&1"
        log.info(f"在 client 端运行 perftest client: {client_cmd}")
        client_status, _, _ = CommandOperation.execute_command_with_error(
            full_client_cmd, CmdExecuteAdressEnum.CLIENT.value, timeout=cls.PERFTEST_TIMEOUT
        )
        log.info(f"client 同步执行结束，返回状态: {client_status}")

        # 等待测试数据稳定
        time.sleep(cls.PERFTEST_DURATION)

        # client 结束后清理 server
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        server_thread.join(timeout=10)

    @classmethod
    def _verify_ud_in_output(cls, output: str) -> None:
        """验证输出中包含 UD 关键字"""
        log.info("检查命令回显中是否包含 UD 传输类型...")

        ud_patterns = [
            r"\bUD\b",
            r"Unreliable Datagram",
            r"unreliable datagram",
            r"Transport :\s*UD",
            r"transport.*UD",
        ]
        has_ud = any(re.search(p, output, re.IGNORECASE) for p in ud_patterns)

        if not has_ud:
            cls.bug_result = (
                f"MC-36 指定 -c RC 进行多播，但输出中未找到 UD 相关关键字。\n"
                f"输出:\n{output}"
            )
            cls.bug_expect = "-c RC 多播实际应为 UD，输出中应包含 UD 或 Unreliable Datagram"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("MC-36 -c RC 多播未显示 UD")

        log.info("输出中检测到 UD 关键字，-c RC 实际为 UD 多播")

    @classmethod
    def _verify_bandwidth(cls, output: str) -> None:
        """验证业务产生有效带宽"""
        log.info("检查 MC-36 带宽结果...")
        pattern = re.compile(
            r"^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)",
            re.MULTILINE,
        )
        matches = pattern.findall(output)
        if not matches:
            cls.bug_result = f"MC-36 未找到有效带宽输出。输出:\n{output}"
            cls.bug_expect = "ib_send_bw -c RC -g 应产生有效带宽"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("MC-36 无有效带宽")

        bw_value = float(matches[-1][3])
        if bw_value <= 0:
            cls.bug_result = f"MC-36 带宽为 0。输出:\n{output}"
            cls.bug_expect = "-c RC -g 多播带宽应大于 0"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("MC-36 带宽为 0")

        log.info(f"MC-36 带宽: {bw_value} MB/sec")

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
            cls.create_bug(f"MC-36 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-36 {name} 端 PF 列表为空")

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
    def _is_opensm_running(cls, exec_addr: str) -> bool:
        """检查 opensm 进程是否正在运行"""
        status, _, _ = CommandOperation.execute_command_with_error(
            "pgrep -x opensm >/dev/null 2>&1", exec_addr
        )
        return status == RtnStatusEnum.SUCCESS.value

    @classmethod
    def _get_device_guid(cls, exec_addr: str, name: str, device: str) -> str:
        """获取指定 IB 设备的 Node GUID"""
        cmd = f"ibstat {device} | grep 'Node GUID'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端获取 {device} Node GUID 失败: {err}"
            cls.bug_expect = "ibstat 应能返回 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-36 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-36 {name} 端解析 {device} GUID 失败")

        return match.group(0)

    @classmethod
    def _start_opensm_for_pports(cls, exec_addr: str, name: str) -> None:
        """为每个 pport 启动 opensm"""
        log.info(f"在 {name} 端为所有 pport 启动 opensm...")

        for idx, pport in enumerate(cls.pport_list):
            guid = cls._get_device_guid(exec_addr, name, pport)
            log.info(f"为 pport {pport} 启动 opensm，GUID: {guid}")
            opensm_cmd = (
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_mc36_{idx}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端为 pport {pport} 启动 opensm 失败: {err}"
                cls.bug_expect = "opensm 应能在每个 pport 上成功启动"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-36 {name} 端 pport {pport} opensm 启动失败")
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
            cls.create_bug(f"MC-36 {name} 端 opensm 未运行")

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
            cls.create_bug(f"MC-36 {name} 端 opensm 进程数量不足")

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
                cls.create_bug(f"MC-36 {name} 端 PF {pf} 未 Active")
        log.info(f"{name} 端所有 PF 均处于 Active 状态")

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-36 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc036.run()


if __name__ == '__main__':
    main()
