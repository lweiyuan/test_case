#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-14
case title: 单节点进行多播测试，自发自收
test category: IB多播测试
check point: 单节点 IB 多播自发自收成功
author: auto-generated
date: 2026.06.24
@steps:
    1. 在单节点上启动 ib_send_bw 多播服务端。
    2. 在同一节点上启动 ib_send_bw 多播客户端连接本机。
    3. 观察收发包是否成功。

@expected:
    收发包成功。可接受 CX7 类似的异常打印。

@changelog:
2026.06.24 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.1 用户态QP退出多播组、3.1.20.2 用户态QP加入多播组
- 使用项目技巧：缺陷自动记录、IB基础概念与设备检查、IB命令处理与回显解析、perftest工具使用
"""

import os
import time
import re
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, BugTypeEnum, CmdExecuteAdressEnum
from scripts.script_libs.script_base import ScriptBase, SxeException


class IbMulticastMc014(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ib_send_bw, ibstat"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
opensm 已启动
测试节点 IB 设备可用"""
    test_steps = """
    1. 在单节点上启动 ib_send_bw 多播服务端：ib_send_bw -d mlx5_0 -g -M <MGID> --run_infinitely。
    2. 在同一节点上启动 ib_send_bw 多播客户端连接本机：ib_send_bw -d mlx5_0 -g -M <MGID> <local_ip> --run_infinitely。
    3. 观察收发包是否成功。
    """

    TARGET_DEVICE = "mlx5_0"
    PPORT_COUNT = 2
    OPENSM_STARTUP_WAIT = 10
    MGID = "255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:00"
    PERFTEST_PORT = 18540
    PERFTEST_STARTUP_WAIT = 3
    PERFTEST_DURATION = 10
    PERFTEST_STOP_WAIT = 2

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc014 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-14 测试环境...")

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
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
        log.info("环境检查通过：目标 IB 设备处于 Active 状态")

    @classmethod
    def prepare(cls) -> None:
        super().prepare()
        log.info("准备 MC-14 测试环境...")
        cls.pf_list = cls._get_pf_list(CmdExecuteAdressEnum.SERVER.value, "server")
        cls.pport_list = cls._get_pport_list(cls.pf_list)
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._start_opensm_for_pports(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._verify_opensm_for_pports(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._verify_all_pport_active(CmdExecuteAdressEnum.SERVER.value, "server")
        cls.local_ip = cls._get_local_ip(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-14 测试：单节点多播自发自收")
        log.info("=" * 60)

        try:
            server_log = f"/tmp/mc14_server_{cls.TARGET_DEVICE}.log"
            client_log = f"/tmp/mc14_client_{cls.TARGET_DEVICE}.log"

            # 启动 server
            server_cmd = (
                f"ib_send_bw -d {cls.TARGET_DEVICE} -g -M {cls.MGID} "
                f"-p {cls.PERFTEST_PORT} -F --run_infinitely"
            )
            cls._start_perftest_server(
                CmdExecuteAdressEnum.SERVER.value, "server", server_cmd, server_log
            )

            # 启动 client（连接本机）
            client_cmd = (
                f"ib_send_bw -d {cls.TARGET_DEVICE} -g -M {cls.MGID} "
                f"-p {cls.PERFTEST_PORT} -F --run_infinitely {cls.local_ip}"
            )
            cls._start_perftest_client(
                CmdExecuteAdressEnum.SERVER.value, "server", client_cmd, client_log
            )

            # 等待测试运行
            time.sleep(cls.PERFTEST_DURATION)

            # 停止进程
            cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
            time.sleep(cls.PERFTEST_STOP_WAIT)

            # 读取并验证结果
            server_output = cls._read_log(CmdExecuteAdressEnum.SERVER.value, "server", server_log)
            client_output = cls._read_log(CmdExecuteAdressEnum.SERVER.value, "server", client_log)
            cls._verify_bandwidth(client_output)

            log.info("=" * 60)
            log.info("测试执行成功 - MC-14 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-14 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-14 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-14 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-14 测试环境...")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        for log_path in [
            f"/tmp/mc14_server_{cls.TARGET_DEVICE}.log",
            f"/tmp/mc14_client_{cls.TARGET_DEVICE}.log",
        ]:
            cls._remove_log_files(CmdExecuteAdressEnum.SERVER.value, "server", log_path)
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        log.info("MC-14 清理完成")
        super().post()

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
            cls.create_bug(f"MC-14 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-14 {name} 端 PF 列表为空")

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
    def _start_opensm_for_pports(cls, exec_addr: str, name: str) -> None:
        """为每个 pport 启动 opensm"""
        log.info(f"在 {name} 端为所有 pport 启动 opensm...")

        for idx, pport in enumerate(cls.pport_list):
            guid = cls._get_device_guid(exec_addr, name, pport)
            log.info(f"为 pport {pport} 启动 opensm，GUID: {guid}")
            opensm_cmd = (
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_mc14_{idx}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端为 pport {pport} 启动 opensm 失败: {err}"
                cls.bug_expect = "opensm 应能在每个 pport 上成功启动"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-14 {name} 端 pport {pport} opensm 启动失败")
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
            cls.create_bug(f"MC-14 {name} 端 opensm 未运行")

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
            cls.create_bug(f"MC-14 {name} 端 opensm 进程数量不足")

        log.info(f"{name} 端 opensm 进程数量: {running_count}，pport 数量: {len(cls.pport_list)}")

    @classmethod
    def _verify_all_pport_active(cls, exec_addr: str, name: str) -> None:
        """验证所有 pport 均处于 Active 状态"""
        log.info(f"验证 {name} 端所有 pport 状态...")
        for pf in cls.pport_list:
            status, result, err = CommandOperation.execute_command_with_error(
                f"ibstat {pf}", exec_addr
            )
            if (
                status != RtnStatusEnum.SUCCESS.value
                or "State: Active" not in result
                or "Physical state: LinkUp" not in result
            ):
                cls.bug_result = f"{name} 端 PF {pf} 未处于 Active/LinkUp 状态"
                cls.bug_expect = "opensm 启动后所有 pport 应处于 Active/LinkUp 状态"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-14 {name} 端 PF {pf} 未 Active")
        log.info(f"{name} 端所有 pport 均处于 Active 状态")

    @classmethod
    def _get_device_guid(cls, exec_addr: str, name: str, device: str) -> str:
        """获取指定 IB 设备的 Node GUID"""
        cmd = f"ibstat {device} | grep 'Node GUID'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端获取 {device} Node GUID 失败: {err}"
            cls.bug_expect = "ibstat 应能返回 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-14 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-14 {name} 端解析 {device} GUID 失败")

        return match.group(0)

    @classmethod
    def _is_opensm_running(cls, exec_addr: str) -> bool:
        """检查 opensm 进程是否正在运行"""
        status, _, _ = CommandOperation.execute_command_with_error(
            "pgrep -x opensm >/dev/null 2>&1", exec_addr
        )
        return status == RtnStatusEnum.SUCCESS.value

    @classmethod
    def _get_local_ip(cls, exec_addr: str, name: str) -> str:
        """获取本机 IP 用于自发自收"""
        if cls.server_logical_ip:
            return cls.server_logical_ip

        cmd = "ip route get 1.1.1.1 | awk '{print $7}' | head -1"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value and result.strip():
            return result.strip()

        cls.bug_result = "无法获取本机 IP 地址"
        cls.bug_expect = "应能获取本机可达 IP"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug("MC-14 获取本机 IP 失败")

    @classmethod
    def _start_perftest_server(cls, exec_addr: str, name: str, cmd: str, log_path: str) -> None:
        log.info(f"在 {name} 端启动 perftest server: {cmd}")
        full_cmd = f"nohup {cmd} >\"{log_path}\" 2>&1 &"
        status, result, err = CommandOperation.execute_command_with_error(full_cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端启动 perftest server 失败: {err}"
            cls.bug_expect = "ib_send_bw server 应能后台启动"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-14 {name} 端启动 perftest server 失败")
        time.sleep(cls.PERFTEST_STARTUP_WAIT)

    @classmethod
    def _start_perftest_client(cls, exec_addr: str, name: str, cmd: str, log_path: str) -> None:
        log.info(f"在 {name} 端启动 perftest client: {cmd}")
        full_cmd = f"nohup {cmd} >\"{log_path}\" 2>&1 &"
        status, result, err = CommandOperation.execute_command_with_error(full_cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端启动 perftest client 失败: {err}"
            cls.bug_expect = "ib_send_bw client 应能后台启动"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-14 {name} 端启动 perftest client 失败")

    @classmethod
    def _stop_perftest_processes(cls, exec_addr: str, name: str) -> None:
        cmd = 'pkill -9 -f "ib_send_bw" 2>/dev/null || true'
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 ib_send_bw 进程已清理")

    @classmethod
    def _read_log(cls, exec_addr: str, name: str, log_path: str) -> str:
        cmd = f"cat \"{log_path}\""
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            return ""
        return result

    @classmethod
    def _verify_bandwidth(cls, output: str) -> None:
        log.info("检查自发自收带宽结果...")
        pattern = re.compile(
            r"^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)",
            re.MULTILINE,
        )
        matches = pattern.findall(output)
        if not matches:
            cls.bug_result = f"MC-14 未找到有效带宽输出。输出:\n{output}"
            cls.bug_expect = "ib_send_bw 自发自收应产生有效带宽"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("MC-14 自发自收无有效带宽")

        bw_value = float(matches[-1][3])
        if bw_value <= 0:
            cls.bug_result = f"MC-14 带宽为 0。输出:\n{output}"
            cls.bug_expect = "自发自收带宽应大于 0"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("MC-14 自发自收带宽为 0")

        log.info(f"MC-14 自发自收带宽: {bw_value} MB/sec")

    @classmethod
    def _remove_log_files(cls, exec_addr: str, name: str, log_path: str) -> None:
        cmd = f"rm -f \"{log_path}\""
        CommandOperation.execute_command_with_error(cmd, exec_addr)

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-14 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc014.run()


if __name__ == '__main__':
    main()
