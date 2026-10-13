#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-29/30/31/32/33
case title: “并发测试”场景，将运行时长设置为7*24h
test category: IB多播测试
check point: 并发多播场景在长时间运行下保持稳定
author: auto-generated
date: 2026.06.25
@steps:
    1. 参考 MC-21/22/23 满规格并发思路，启动多组 ib_send_bw -g 多播 server/client 对。
    2. 将运行时长设置为 7×24h（默认可配置为较短时长用于冒烟）。
    3. 运行期间定期检查进程存活及日志输出。
    4. 运行结束后检查所有进程是否均产生有效带宽，无异常。

@expected:
    7×24h 运行期间无异常，业务稳定，所有进程均产生有效带宽。

@changelog:
2026.06.25 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.1~3.1.20.5 IB多播支持
- 使用项目技巧：缺陷自动记录、IB基础概念与设备检查、IB命令处理与回显解析、perftest工具使用
- 默认运行时长较短（60s），可通过 LONG_DURATION_SECONDS 配置为 7*24h
"""

import os
import time
import re
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, BugTypeEnum, CmdExecuteAdressEnum, RdmaMode
from scripts.script_libs.script_base import ScriptBase, SxeException
from scripts.script_libs.common_operation import CommonOperation


class IbMulticastMc029(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ib_send_bw, opensm, ibstat"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
opensm 已启动
测试节点之间 IB 网络互通
服务器内存、CPU 资源充裕"""
    test_steps = """
    1. 启动多组 ib_send_bw -g 多播 server/client 对（模拟满规格并发）。
    2. 将运行时长设置为 7×24h（默认可配置为较短时长用于冒烟）。
    3. 运行期间定期检查进程存活及日志输出。
    4. 运行结束后检查所有进程是否均产生有效带宽，无异常。
    """

    # 服务端/客户端 IB 设备名，在 check_own_environment() 中从 env_config 动态读取
    server_device = ""
    client_device = ""
    MGID = "255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:00"
    PERFTEST_PORT_BASE = 18529
    # 并发对数：可配置为实际满规格值
    CONCURRENT_PAIRS = 4
    PERFTEST_STARTUP_WAIT = 3
    PERFTEST_STOP_WAIT = 2
    # 默认运行时长 65s 用于冒烟（>= 60s perftest + 5s 启动/收尾余量）；实际稳定测试可配置为 7*24*3600 = 604800
    LONG_DURATION_SECONDS = 604800
    # 运行期间采样间隔（秒）
    SAMPLE_INTERVAL_SECONDS = 10
    # 双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport
    PPORT_COUNT = 2
    OPENSM_STARTUP_WAIT = 10

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc029 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-29/30/31/32/33 测试环境...")

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
        log.info("准备 MC-29/30/31/32/33 测试环境...")
        cls.server_ip = cls._get_server_ip()

        # 获取两端 PF 列表并识别 pport
        cls.server_pf_list = cls._get_pf_list(CmdExecuteAdressEnum.SERVER.value, "server")
        cls.server_pport_list = cls._get_pport_list(cls.server_pf_list)
        cls.client_pf_list = cls._get_pf_list(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls.client_pport_list = cls._get_pport_list(cls.client_pf_list)

        # 停止现有 opensm 并为每个 pport 重新启动
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._start_opensm_for_pports(
            CmdExecuteAdressEnum.SERVER.value, "server", cls.server_pport_list, "mc29"
        )
        cls._start_opensm_for_pports(
            CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_pport_list, "mc29"
        )
        cls._verify_opensm_for_pports(
            CmdExecuteAdressEnum.SERVER.value, "server", cls.server_pport_list
        )
        cls._verify_opensm_for_pports(
            CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_pport_list
        )
        cls._verify_all_pf_active(
            CmdExecuteAdressEnum.SERVER.value, "server", cls.server_pf_list
        )
        cls._verify_all_pf_active(
            CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_pf_list
        )

        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-29/30/31/32/33 测试：并发多播稳定测试")
        log.info(
            f"运行时长: {cls.LONG_DURATION_SECONDS}s "
            f"({cls.LONG_DURATION_SECONDS / 3600:.2f}h)"
        )
        log.info("=" * 60)

        try:
            server_logs = []
            client_logs = []

            # 启动多组 server/client 对
            for i in range(cls.CONCURRENT_PAIRS):
                port = cls.PERFTEST_PORT_BASE + i
                server_log = f"/tmp/ib_send_bw_mc29_server_{i}.log"
                client_log = f"/tmp/ib_send_bw_mc29_client_{i}.log"

                server_cmd = (
                    f"ib_send_bw -d {cls.server_device} -g -M {cls.MGID} "
                    f"--pkey_index=0 -S 1 -m 2048 -s 2048 -p {port} -F -D 60 --run_infinitely"
                )
                client_cmd = (
                    f"ib_send_bw -d {cls.client_device} -g -M {cls.MGID} "
                    f"--pkey_index=0 -S 1 -m 2048 -s 2048 -p {port} -F -D 60 "
                    f"--run_infinitely {cls.server_ip}"
                )

                cls._start_perftest_server(
                    CmdExecuteAdressEnum.SERVER.value, "server", server_cmd, server_log
                )
                server_logs.append(server_log)

                cls._start_perftest_client(
                    CmdExecuteAdressEnum.CLIENT.value, "client", client_cmd, client_log
                )
                client_logs.append(client_log)

            # 等待所有进程初始化
            time.sleep(cls.PERFTEST_STARTUP_WAIT)

            # 运行期间定期检查进程存活
            cls._monitor_during_run(
                cls.LONG_DURATION_SECONDS, cls.SAMPLE_INTERVAL_SECONDS
            )

            # 停止所有 perftest 进程
            cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
            cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
            time.sleep(cls.PERFTEST_STOP_WAIT)

            # 读取并验证每个 client 日志
            for i in range(cls.CONCURRENT_PAIRS):
                client_output = cls._read_log(
                    CmdExecuteAdressEnum.CLIENT.value, "client", client_logs[i]
                )
                cls._verify_bandwidth(i, client_output)

            log.info("=" * 60)
            log.info("测试执行成功 - MC-29/30/31/32/33 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-29/30/31/32/33 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-29/30/31/32/33 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-29/30/31/32/33 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-29/30/31/32/33 测试环境...")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        log.info("MC-29/30/31/32/33 清理完成")
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
        cls.create_bug("MC-29/30/31/32/33 获取服务端 IP 失败")

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
            cls.create_bug(f"MC-29/30/31/32/33 {name} 端启动 perftest server 失败")

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
            cls.create_bug(f"MC-29/30/31/32/33 {name} 端启动 perftest client 失败")

    @classmethod
    def _monitor_during_run(cls, duration: int, sample_interval: int) -> None:
        """运行期间定期检查进程是否存活"""
        log.info(f"开始稳定运行 {duration}s，每 {sample_interval}s 采样一次进程状态...")
        elapsed = 0
        while elapsed < duration:
            sleep_time = min(sample_interval, duration - elapsed)
            time.sleep(sleep_time)
            elapsed += sleep_time

            if not cls._is_perftest_alive(CmdExecuteAdressEnum.SERVER.value, "server"):
                cls.bug_result = f"运行 {elapsed}s 后 server 端 ib_send_bw 进程异常退出"
                cls.bug_expect = "稳定运行期间 server 端 ib_send_bw 进程应保持存活"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-29/30/31/32/33 运行 {elapsed}s 后 server 端进程异常")

            if not cls._is_perftest_alive(CmdExecuteAdressEnum.CLIENT.value, "client"):
                cls.bug_result = f"运行 {elapsed}s 后 client 端 ib_send_bw 进程异常退出"
                cls.bug_expect = "稳定运行期间 client 端 ib_send_bw 进程应保持存活"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-29/30/31/32/33 运行 {elapsed}s 后 client 端进程异常")

            log.info(f"已运行 {elapsed}s / {duration}s，进程存活正常")

        log.info(f"稳定运行 {duration}s 完成，进程均未异常退出")

    @classmethod
    def _is_perftest_alive(cls, exec_addr: str, name: str) -> bool:
        """检查 ib_send_bw 进程是否存活"""
        status, result, _ = CommandOperation.execute_command_with_error(
            "pgrep -x ib_send_bw", exec_addr
        )
        return status == RtnStatusEnum.SUCCESS.value and result.strip() != ""

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
            cls.bug_result = f"{name} 端读取日志 {log_path} 失败: {err}"
            cls.bug_expect = "perftest 日志文件应存在且可读"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-29/30/31/32/33 {name} 端读取 perftest 日志失败")
        return result

    @classmethod
    def _verify_bandwidth(cls, idx: int, output: str) -> None:
        """检查单个 client 输出中是否存在有效带宽"""
        log.info(f"检查第 {idx} 对 client 的带宽结果...")
        pattern = re.compile(
            r"^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)",
            re.MULTILINE,
        )
        matches = pattern.findall(output)
        if not matches:
            cls.bug_result = (
                f"第 {idx} 对 client 未找到有效带宽输出。输出:\n{output}"
            )
            cls.bug_expect = "ib_send_bw 输出中应包含 BW average[MB/sec] 统计行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-29/30/31/32/33 第 {idx} 对无有效带宽")

        bw_value = float(matches[-1][3])
        if bw_value <= 0:
            cls.bug_result = f"第 {idx} 对 client 带宽为 0。输出:\n{output}"
            cls.bug_expect = "多播业务带宽应大于 0"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-29/30/31/32/33 第 {idx} 对带宽为 0")

        log.info(f"第 {idx} 对带宽: {bw_value} MB/sec")

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
            cls.create_bug(f"MC-29/30/31/32/33 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-29/30/31/32/33 {name} 端 PF 列表为空")

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
    def _start_opensm_for_pports(
        cls, exec_addr: str, name: str, pport_list: list, case: str
    ) -> None:
        """为每个 pport 启动 opensm"""
        log.info(f"在 {name} 端为所有 pport 启动 opensm...")

        for idx, pport in enumerate(pport_list):
            guid = cls._get_device_guid(exec_addr, name, pport)
            log.info(f"为 pport {pport} 启动 opensm，GUID: {guid}")
            opensm_cmd = (
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_{case}_{idx}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端为 pport {pport} 启动 opensm 失败: {err}"
                cls.bug_expect = "opensm 应能在每个 pport 上成功启动"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-29/30/31/32/33 {name} 端 pport {pport} opensm 启动失败")
            time.sleep(3)

        # 等待 opensm 完成子网扫描
        time.sleep(cls.OPENSM_STARTUP_WAIT)

    @classmethod
    def _verify_opensm_for_pports(cls, exec_addr: str, name: str, pport_list: list) -> None:
        """验证每个 pport 上的 opensm 进程正在运行"""
        log.info(f"验证 {name} 端所有 pport 的 opensm 进程...")

        if not cls._is_opensm_running(exec_addr):
            cls.bug_result = f"{name} 端未检测到任何 opensm 进程"
            cls.bug_expect = "每个 pport 上应运行一个 opensm 实例"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-29/30/31/32/33 {name} 端 opensm 未运行")

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
            cls.create_bug(f"MC-29/30/31/32/33 {name} 端 opensm 进程数量不足")

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
                cls.create_bug(f"MC-29/30/31/32/33 {name} 端 PF {pf} 未 Active")
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
            cls.create_bug(f"MC-29/30/31/32/33 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-29/30/31/32/33 {name} 端解析 {device} GUID 失败")

        return match.group(0)

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-29/30/31/32/33 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc029.run()


if __name__ == '__main__':
    main()
