#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-26
case title: 带宽对比
test category: IB多播测试
check point: 天蝎多播带宽与 CX7 基准多播带宽的偏差在可接受范围内
author: auto-generated
date: 2026.06.25
@steps:
    1. 使用 CX7 在相同环境同插槽获得基准：
       使用 ib_send_bw -g -M <MGID>，包长从 2 倍增到 4096，记录多播带宽。
    2. 使用天蝎在相同环境同插槽重复步骤 1。
    3. 对比各包长下天蝎与 CX7 的多播带宽偏差。

@expected:
    天蝎与 CX7 的多播带宽偏差在 ±10% 范围内。

@changelog:
2026.06.25 - 根据 IB-MultiCast_ForAI-测试用例.xlsx（excel_dump.txt 第 21 行）生成
- 关联需求：3.1.20.1~3.1.20.5 IB多播支持
- CX7 基准可通过类常量 CX7_BASELINE_MC_BANDWIDTH 配置；未配置时仅记录并报告当前多播带宽
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


class IbMulticastMc026(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ib_send_bw"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
opensm 已启动
测试节点之间 IB 网络互通"""
    test_steps = """
    1. 使用 ib_send_bw -g -M <MGID> 测试包长 2/4/8/16/32/64/128/256/512/1024/2048/4096 的多播带宽。
    2. 若配置了 CX7 基准多播带宽，则计算天蝎与 CX7 的带宽偏差；否则仅报告当前多播带宽。
    """

    # 服务端/客户端 IB 设备名，在 check_own_environment() 中从 env_config 动态读取
    server_device = ""
    client_device = ""
    MGID = "255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:00"
    PERFTEST_PORT_MC = 18526
    PERFTEST_STARTUP_WAIT = 3
    # perftest 使用 -D 60 运行 60 秒；这里等待 65 秒，留 5 秒启动/收尾余量
    PERFTEST_DURATION = 65
    PERFTEST_STOP_WAIT = 2

    # 测试包长序列：从 2 倍增到 4096
    MSG_SIZES = [2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096]

    # CX7 基准多播带宽（单位 MB/s），key 为包长，value 为带宽。
    # 未配置时脚本仅记录并报告当前多播带宽。
    CX7_BASELINE_MC_BANDWIDTH = {
        2: 13.49,
        4: 27.25,
        8: 54.13,
        16: 86.37,
        32: 219.48,
        64: 438.95,
        128: 692.83,
        256: 1743.87,
        512: 3511.65,
        1024: 6881.83,
        2048: 10737.06,
        4096: 12485.80,
    }

    # 通过标准：带宽偏差在 ±10% 范围内
    ATTENUATION_THRESHOLD = 0.10

    # 双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport
    PPORT_COUNT = 2
    OPENSM_STARTUP_WAIT = 10

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc026 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-26 测试环境...")

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
        log.info("准备 MC-26 测试环境...")
        cls.server_ip = cls._get_server_ip()

        # 在两端为每个 pport 启动 opensm 并验证
        cls.server_pf_list, cls.server_pport_list = cls._ensure_opensm_for_side(
            CmdExecuteAdressEnum.SERVER.value, "server", "mc26"
        )
        cls.client_pf_list, cls.client_pport_list = cls._ensure_opensm_for_side(
            CmdExecuteAdressEnum.CLIENT.value, "client", "mc26"
        )
        # 保持 cls.pf_list / cls.pport_list 兼容单节点习惯
        cls.pf_list = cls.server_pf_list
        cls.pport_list = cls.server_pport_list

        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-26 测试：多播带宽对比")
        log.info("=" * 60)

        try:
            report = []
            fail_details = []

            for size in cls.MSG_SIZES:
                log.info(f"--- 测试包长 {size} ---")
                mc_bw = cls._measure_bandwidth(
                    mode="multicast", msg_size=size,
                    port=cls.PERFTEST_PORT_MC, log_prefix="mc26_mc"
                )

                entry = {"size": size, "mc_bw": mc_bw}

                # 与 CX7 基准多播带宽比较
                if size in cls.CX7_BASELINE_MC_BANDWIDTH:
                    baseline = cls.CX7_BASELINE_MC_BANDWIDTH[size]
                    deviation = abs(mc_bw - baseline) / baseline
                    entry["baseline"] = baseline
                    entry["deviation"] = deviation
                    log.info(
                        f"包长 {size}: 多播 {mc_bw:.3f} MB/s, "
                        f"基准 {baseline:.3f} MB/s, 偏差 {deviation:.2%}"
                    )
                    if deviation > cls.ATTENUATION_THRESHOLD:
                        detail = (
                            f"包长 {size}: 带宽偏差 {deviation:.2%} 超过阈值 "
                            f"{cls.ATTENUATION_THRESHOLD:.0%}"
                        )
                        log.error(detail)
                        fail_details.append(detail)
                else:
                    log.info(
                        f"包长 {size}: 多播 {mc_bw:.3f} MB/s（未配置 CX7 基准）"
                    )

                report.append(entry)

            # 打印汇总报告
            cls._print_report(report)

            if fail_details:
                cls.bug_result = "部分包长带宽偏差超过阈值:\n" + "\n".join(fail_details)
                cls.bug_expect = f"各包长带宽偏差应在 ±{cls.ATTENUATION_THRESHOLD:.0%} 范围内"
                cls.set_bug_type(BugTypeEnum.PERFORMANCE.value)
                cls.create_bug("MC-26 多播带宽对比偏差超标")

            log.info("=" * 60)
            log.info("测试执行成功 - MC-26 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-26 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-26 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-26 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-26 测试环境...")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        for size in cls.MSG_SIZES:
            prefix = "mc26_mc"
            cls._remove_log_files(
                CmdExecuteAdressEnum.SERVER.value, "server",
                f"/tmp/{prefix}_s{size}_server.log"
            )
            cls._remove_log_files(
                CmdExecuteAdressEnum.CLIENT.value, "client",
                f"/tmp/{prefix}_s{size}_client.log"
            )
        log.info("MC-26 清理完成")
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
        cls.create_bug("MC-26 获取服务端 IP 失败")

    @classmethod
    def _measure_bandwidth(cls, mode: str, msg_size: int, port: int, log_prefix: str) -> float:
        """测量指定模式/包长下的带宽，返回 MB/sec"""
        server_log = f"/tmp/{log_prefix}_s{msg_size}_server.log"
        client_log = f"/tmp/{log_prefix}_s{msg_size}_client.log"

        server_cmd = (
            f"ib_send_bw -d {cls.server_device} -g -M {cls.MGID} "
            f"-s {msg_size} -p {port} -D 60 -F"
        )
        client_cmd = (
            f"ib_send_bw -d {cls.client_device} -g -M {cls.MGID} "
            f"-s {msg_size} -p {port} -D 60 -F {cls.server_ip}"
        )

        cls._start_perftest_server(
            CmdExecuteAdressEnum.SERVER.value, "server", server_cmd, server_log
        )
        time.sleep(cls.PERFTEST_STARTUP_WAIT)
        cls._start_perftest_client(
            CmdExecuteAdressEnum.CLIENT.value, "client", client_cmd, client_log
        )

        time.sleep(cls.PERFTEST_DURATION)
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        time.sleep(cls.PERFTEST_STOP_WAIT)

        client_output = cls._read_log(CmdExecuteAdressEnum.CLIENT.value, "client", client_log)
        return cls._extract_bandwidth(client_output, mode, msg_size)

    @classmethod
    def _start_perftest_server(cls, exec_addr: str, name: str, cmd: str, log_path: str) -> None:
        log.info(f"在 {name} 端启动 perftest server: {cmd}")
        full_cmd = f"nohup {cmd} >\"{log_path}\" 2>&1 &"
        status, result, err = CommandOperation.execute_command_with_error(full_cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端启动 perftest server 失败: {err}"
            cls.bug_expect = "ib_send_bw server 应能后台启动"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-26 {name} 端启动 perftest server 失败")

    @classmethod
    def _start_perftest_client(cls, exec_addr: str, name: str, cmd: str, log_path: str) -> None:
        log.info(f"在 {name} 端启动 perftest client: {cmd}")
        full_cmd = f"nohup {cmd} >\"{log_path}\" 2>&1 &"
        status, result, err = CommandOperation.execute_command_with_error(full_cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端启动 perftest client 失败: {err}"
            cls.bug_expect = "ib_send_bw client 应能后台启动"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-26 {name} 端启动 perftest client 失败")

    @classmethod
    def _read_log(cls, exec_addr: str, name: str, log_path: str) -> str:
        cmd = f"cat \"{log_path}\""
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            return ""
        return result

    @classmethod
    def _extract_bandwidth(cls, output: str, mode: str, msg_size: int) -> float:
        """从 perftest 输出中提取带宽（MB/sec）"""
        pattern = re.compile(
            r"^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)",
            re.MULTILINE,
        )
        matches = pattern.findall(output)
        if not matches:
            cls.bug_result = (
                f"{mode} 包长 {msg_size} 未找到有效带宽输出。输出:\n{output}"
            )
            cls.bug_expect = "ib_send_bw 输出中应包含 BW average[MB/sec] 统计行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-26 {mode} 包长 {msg_size} 无有效带宽")

        bw_value = float(matches[-1][3])
        if bw_value < 0:
            cls.bug_result = (
                f"{mode} 包长 {msg_size} 带宽为负值: {bw_value}。输出:\n{output}"
            )
            cls.bug_expect = "ib_send_bw 带宽应大于等于 0"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-26 {mode} 包长 {msg_size} 带宽异常")

        return bw_value

    @classmethod
    def _print_report(cls, report: list) -> None:
        log.info("=" * 60)
        log.info("MC-26 多播带宽对比报告")
        log.info("=" * 60)
        for entry in report:
            size = entry["size"]
            mc = entry["mc_bw"]
            if "baseline" in entry:
                log.info(
                    f"包长 {size:5d}: 多播 {mc:10.3f} MB/s | "
                    f"基准 {entry['baseline']:10.3f} MB/s | 偏差 {entry['deviation']:.2%}"
                )
            else:
                log.info(
                    f"包长 {size:5d}: 多播 {mc:10.3f} MB/s | 基准未配置"
                )
        log.info("=" * 60)

    @classmethod
    def _stop_perftest_processes(cls, exec_addr: str, name: str) -> None:
        """停止 perftest 进程（使用 -x 精确匹配，避免误杀 SSH 会话）"""
        cmd = 'pkill -9 -x ib_send_bw 2>/dev/null || true'
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 ib_send_bw 进程已清理")

    @classmethod
    def _remove_log_files(cls, exec_addr: str, name: str, log_path: str) -> None:
        cmd = f"rm -f \"{log_path}\""
        CommandOperation.execute_command_with_error(cmd, exec_addr)

    @classmethod
    def _ensure_opensm_for_side(cls, exec_addr: str, name: str, case: str) -> tuple:
        """为指定端停止/启动/验证 opensm，返回 (pf_list, pport_list)"""
        cls._stop_opensm(exec_addr, name)
        pf_list = cls._get_pf_list(exec_addr, name)
        pport_list = cls._get_pport_list(pf_list)
        cls._start_opensm_for_pports(exec_addr, name, pport_list, case)
        cls._verify_opensm_for_pports(exec_addr, name, pport_list)
        cls._verify_all_pf_active(exec_addr, name, pf_list)
        return pf_list, pport_list

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
            cls.create_bug(f"MC-26 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-26 {name} 端 PF 列表为空")

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
                cls.create_bug(f"MC-26 {name} 端 pport {pport} opensm 启动失败")
            time.sleep(3)

        # 等待 opensm 完成子网扫描
        time.sleep(cls.OPENSM_STARTUP_WAIT)

    @classmethod
    def _verify_opensm_for_pports(
        cls, exec_addr: str, name: str, pport_list: list
    ) -> None:
        """验证每个 pport 上的 opensm 进程正在运行"""
        log.info(f"验证 {name} 端所有 pport 的 opensm 进程...")

        if not cls._is_opensm_running(exec_addr):
            cls.bug_result = f"{name} 端未检测到任何 opensm 进程"
            cls.bug_expect = "每个 pport 上应运行一个 opensm 实例"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-26 {name} 端 opensm 未运行")

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
            cls.create_bug(f"MC-26 {name} 端 opensm 进程数量不足")

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
                cls.create_bug(f"MC-26 {name} 端 PF {pf} 未 Active")
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
            cls.create_bug(f"MC-26 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-26 {name} 端解析 {device} GUID 失败")

        return match.group(0)

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
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-26 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc026.run()


if __name__ == '__main__':
    main()
