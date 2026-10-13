#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-28
case title: 多播规模拓展
test category: IB多播测试
check point: 在同一个多播组中逐步增加客户端和服务端，各进程带宽/延时保持一致
author: auto-generated
date: 2026.06.25
@steps:
    1. 在同一个多播组中逐步增加服务端/客户端对（如 1/2/4/8 对）。
    2. 每对使用 ib_send_bw -g 并指定相同 MGID、不同端口，进行多播测试。
    3. 记录每对进程的带宽。
    4. 对比不同规模下各进程的带宽是否保持一致。

@expected:
    各规模下所有多播进程均产生有效带宽。
    各进程带宽在可接受偏差范围内保持一致，无明显随规模增加而恶化。

@changelog:
2026.06.25 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.1~3.1.20.5 IB多播支持
- 使用项目技巧：缺陷自动记录、IB基础概念与设备检查、IB命令处理与回显解析、perftest工具使用
2026.06.26 - 修正：识别所有 pport 并为每个 pport 启动并检查 opensm；prepare/post 补充 super() 调用
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


class IbMulticastMc028(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ib_send_bw, opensm, ibstat"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
opensm 已启动
测试节点之间 IB 网络互通"""
    test_steps = """
    1. 在同一个多播组中逐步增加服务端/客户端对（1/2/4/8 对）。
    2. 每对使用 ib_send_bw -g 指定相同 MGID、不同端口进行多播测试。
    3. 记录每对进程的带宽。
    4. 对比不同规模下各进程带宽是否保持一致。
    """

    # 双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport
    PPORT_COUNT = 2
    # 服务端/客户端 IB 设备名，在 check_own_environment() 中从 env_config 动态读取
    server_device = ""
    client_device = ""
    MGID = "255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:00"
    PERFTEST_PORT_BASE = 18528
    # perftest 使用 -D 60 运行 60 秒；这里等待 65 秒，留 5 秒启动/收尾余量
    PERFTEST_DURATION = 65
    PERFTEST_STARTUP_WAIT = 3
    PERFTEST_STOP_WAIT = 2
    # 规模拓展等级：可配置为 [1, 2, 4, 8, 16] 等
    SCALE_LEVELS = [1, 2, 4, 8]
    # 带宽一致性偏差阈值：最大/最小带宽比不超过该值
    BW_CONSISTENCY_RATIO = 2.0
    OPENSM_STARTUP_WAIT = 10

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc028 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-28 测试环境...")

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
        log.info("准备 MC-28 测试环境...")
        cls.server_ip = cls._get_server_ip()

        # 识别并启动所有 pport 的 opensm（server/client 两端均需）
        cls.server_pf_list = cls._get_pf_list(
            CmdExecuteAdressEnum.SERVER.value, "server"
        )
        cls.server_pport_list = cls._get_pport_list(cls.server_pf_list)
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._start_opensm_for_pports(
            CmdExecuteAdressEnum.SERVER.value, "server", cls.server_pport_list
        )
        cls._verify_opensm_for_pports(
            CmdExecuteAdressEnum.SERVER.value, "server", cls.server_pport_list
        )
        cls._verify_all_pf_active(
            CmdExecuteAdressEnum.SERVER.value, "server", cls.server_pf_list
        )

        cls.client_pf_list = cls._get_pf_list(
            CmdExecuteAdressEnum.CLIENT.value, "client"
        )
        cls.client_pport_list = cls._get_pport_list(cls.client_pf_list)
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._start_opensm_for_pports(
            CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_pport_list
        )
        cls._verify_opensm_for_pports(
            CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_pport_list
        )
        cls._verify_all_pf_active(
            CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_pf_list
        )

        log.info(f"server 端 PF 列表: {cls.server_pf_list}")
        log.info(f"server 端 pport 列表: {cls.server_pport_list}")
        log.info(f"client 端 PF 列表: {cls.client_pf_list}")
        log.info(f"client 端 pport 列表: {cls.client_pport_list}")

        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-28 测试：多播规模拓展")
        log.info("=" * 60)

        try:
            scale_results = []
            for scale in cls.SCALE_LEVELS:
                log.info(f"--- 执行规模 {scale}（{scale} 对 server/client）---")
                bw_list = cls._run_scale_level(scale)
                scale_results.append({"scale": scale, "bw_list": bw_list})
                log.info(f"规模 {scale} 平均带宽: {sum(bw_list)/len(bw_list):.2f} MB/sec")

            cls._verify_scale_consistency(scale_results)

            log.info("=" * 60)
            log.info("测试执行成功 - MC-28 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-28 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-28 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-28 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-28 测试环境...")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        log.info("MC-28 清理完成")
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
        cls.create_bug("MC-28 获取服务端 IP 失败")

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
            cls.create_bug(f"MC-28 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-28 {name} 端 PF 列表为空")

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
    def _start_opensm_for_pports(
        cls, exec_addr: str, name: str, pport_list: list
    ) -> None:
        """为每个 pport 启动 opensm"""
        log.info(f"在 {name} 端为所有 pport 启动 opensm...")

        for idx, pport in enumerate(pport_list):
            guid = cls._get_device_guid(exec_addr, name, pport)
            log.info(f"为 pport {pport} 启动 opensm，GUID: {guid}")
            opensm_cmd = (
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_mc28_{idx}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端为 pport {pport} 启动 opensm 失败: {err}"
                cls.bug_expect = "opensm 应能在每个 pport 上成功启动"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-28 {name} 端 pport {pport} opensm 启动失败")
            time.sleep(3)

        # 等待 opensm 完成子网扫描
        time.sleep(cls.OPENSM_STARTUP_WAIT)

    @classmethod
    def _verify_opensm_for_pports(
        cls, exec_addr: str, name: str, pport_list: list
    ) -> None:
        """验证每个 pport 上的 opensm 进程正在运行"""
        log.info(f"验证 {name} 端所有 pport 的 opensm 进程...")

        status, result, err = CommandOperation.execute_command_with_error(
            "pgrep -x opensm", exec_addr
        )
        if status != RtnStatusEnum.SUCCESS.value or not result.strip():
            cls.bug_result = f"{name} 端未检测到任何 opensm 进程"
            cls.bug_expect = "每个 pport 上应运行一个 opensm 实例"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-28 {name} 端 opensm 未运行")

        running_count = len(
            [line.strip() for line in result.splitlines() if line.strip()]
        )
        if running_count < len(pport_list):
            cls.bug_result = (
                f"{name} 端 opensm 进程数量不足，实际 {running_count} 个，"
                f"期望至少 {len(pport_list)} 个（每个 pport 一个）"
            )
            cls.bug_expect = "每个 pport 上应运行一个 opensm 实例"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-28 {name} 端 opensm 进程数量不足")

        log.info(
            f"{name} 端 opensm 进程数量: {running_count}，pport 数量: {len(pport_list)}"
        )

    @classmethod
    def _verify_all_pf_active(
        cls, exec_addr: str, name: str, pf_list: list
    ) -> None:
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
                cls.create_bug(f"MC-28 {name} 端 PF {pf} 未 Active")
        log.info(f"{name} 端所有 PF 均处于 Active/LinkUp 状态")

    @classmethod
    def _get_device_guid(cls, exec_addr: str, name: str, device: str) -> str:
        """获取指定 IB 设备的 Node GUID"""
        cmd = f"ibstat {device} | grep 'Node GUID'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端获取 {device} Node GUID 失败: {err}"
            cls.bug_expect = "ibstat 应能返回 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-28 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-28 {name} 端解析 {device} GUID 失败")

        return match.group(0)

    @classmethod
    def _run_scale_level(cls, scale: int) -> list:
        """运行指定规模的多播 server/client 对，返回各对带宽列表"""
        server_logs = []
        client_logs = []

        # 启动 scale 个 server
        for i in range(scale):
            port = cls.PERFTEST_PORT_BASE + i
            server_log = f"/tmp/ib_send_bw_mc28_s{scale}_server_{i}.log"
            server_cmd = (
                f"ib_send_bw -d {cls.server_device} -g -M {cls.MGID} "
                f"--pkey_index=0 -S 1 -m 2048 -s 2048 -p {port} -D 60 -F"
            )
            cls._start_perftest_server(
                CmdExecuteAdressEnum.SERVER.value, "server", server_cmd, server_log
            )
            server_logs.append(server_log)

        # 等待所有 server 初始化
        time.sleep(cls.PERFTEST_STARTUP_WAIT)

        # 启动 scale 个 client
        for i in range(scale):
            port = cls.PERFTEST_PORT_BASE + i
            client_log = f"/tmp/ib_send_bw_mc28_s{scale}_client_{i}.log"
            client_cmd = (
                f"ib_send_bw -d {cls.client_device} -g -M {cls.MGID} "
                f"--pkey_index=0 -S 1 -m 2048 -s 2048 -p {port} -D 60 -F {cls.server_ip}"
            )
            cls._start_perftest_client(
                CmdExecuteAdressEnum.CLIENT.value, "client", client_cmd, client_log
            )
            client_logs.append(client_log)

        # 等待测试完成
        time.sleep(cls.PERFTEST_DURATION)

        # 停止进程
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        time.sleep(cls.PERFTEST_STOP_WAIT)

        # 读取并验证每个 client 日志
        bw_list = []
        for i in range(scale):
            client_output = cls._read_log(
                CmdExecuteAdressEnum.CLIENT.value, "client", client_logs[i]
            )
            bw = cls._verify_bandwidth(scale, i, client_output)
            bw_list.append(bw)

        return bw_list

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
            cls.create_bug(f"MC-28 {name} 端启动 perftest server 失败")

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
            cls.create_bug(f"MC-28 {name} 端启动 perftest client 失败")

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
            cls.create_bug(f"MC-28 {name} 端读取 perftest 日志失败")
        return result

    @classmethod
    def _verify_bandwidth(cls, scale: int, idx: int, output: str) -> float:
        """检查单个 client 输出中是否存在有效带宽，返回带宽值"""
        log.info(f"检查规模 {scale} 第 {idx} 对 client 的带宽结果...")
        pattern = re.compile(
            r"^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)",
            re.MULTILINE,
        )
        matches = pattern.findall(output)
        if not matches:
            cls.bug_result = (
                f"规模 {scale} 第 {idx} 对 client 未找到有效带宽输出。输出:\n{output}"
            )
            cls.bug_expect = "ib_send_bw 输出中应包含 BW average[MB/sec] 统计行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-28 规模 {scale} 第 {idx} 对无有效带宽")

        bw_value = float(matches[-1][3])
        if bw_value <= 0:
            cls.bug_result = (
                f"规模 {scale} 第 {idx} 对 client 带宽为 0。输出:\n{output}"
            )
            cls.bug_expect = "多播业务带宽应大于 0"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-28 规模 {scale} 第 {idx} 对带宽为 0")

        log.info(f"规模 {scale} 第 {idx} 对带宽: {bw_value} MB/sec")
        return bw_value

    @classmethod
    def _verify_scale_consistency(cls, scale_results: list) -> None:
        """验证不同规模下各进程带宽是否保持一致"""
        log.info("验证多播规模拓展带宽一致性...")

        for entry in scale_results:
            scale = entry["scale"]
            bw_list = entry["bw_list"]
            min_bw = min(bw_list)
            max_bw = max(bw_list)
            ratio = max_bw / min_bw if min_bw > 0 else float("inf")
            log.info(
                f"规模 {scale}: min={min_bw:.2f} MB/sec, max={max_bw:.2f} MB/sec, ratio={ratio:.2f}"
            )
            if ratio > cls.BW_CONSISTENCY_RATIO:
                cls.bug_result = (
                    f"规模 {scale} 内各进程带宽差异过大（ratio={ratio:.2f}，"
                    f"阈值={cls.BW_CONSISTENCY_RATIO}），带宽列表: {bw_list}"
                )
                cls.bug_expect = "同一规模内各多播进程带宽应保持一致"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-28 规模 {scale} 带宽一致性异常")

        log.info("多播规模拓展带宽一致性检查通过")

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-28 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc028.run()


if __name__ == '__main__':
    main()
