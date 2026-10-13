#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-27
case title: 延时对比
test category: IB多播测试
check point: 天蝎与 CX7 在相同条件下的延时差异在可接受范围内
author: auto-generated
date: 2026.06.25
@steps:
    1. 使用 CX7 在相同环境同插槽获得延时基准（参考 excel_dump.txt 第 22 行）。
    2. 使用 ib_send_lat 在相同条件下测试天蝎。
    3. 对比两者延时差异。

@expected:
    天蝎与 CX7 延时差异在可接受范围内。

@changelog:
2026.06.25 - 根据 IB-MultiCast_ForAI-测试用例.xlsx（excel_dump.txt 第 22 行）生成
- 关联需求：3.1.20.1~3.1.20.5 IB多播支持
- CX7 基准延时可通过类常量 CX7_BASELINE_LATENCY_US 配置；未配置时仅记录并报告当前延时
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


class IbMulticastMc027(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ib_send_lat"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
opensm 已启动
测试节点之间 IB 网络互通"""
    test_steps = """
    1. 使用 ib_send_lat -g 测量多播延时。
    2. 使用 ib_send_lat（无 -g）测量相同包长的单播延时。
    3. 记录并报告各包长下的延时。
    4. 若配置了 CX7 基准延时，则计算差异；否则仅报告当前延时。
    """

    # 服务端/客户端 IB 设备名，在 check_own_environment() 中从 env_config 动态读取
    server_device = ""
    client_device = ""
    MGID = "255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:00"
    PERFTEST_PORT_MC = 18527
    PERFTEST_PORT_UC = 18528
    PERFTEST_STARTUP_WAIT = 3
    # perftest 使用 -D 60 运行 60 秒；这里等待 65 秒，留 5 秒启动/收尾余量
    PERFTEST_DURATION = 65
    PERFTEST_STOP_WAIT = 2

    # 双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport
    PPORT_COUNT = 2
    OPENSM_STARTUP_WAIT = 10

    # 测试包长序列（常用包长）
    MSG_SIZES = [2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096]

    # CX7 基准延时（微秒），key 为包长，value 为延时 us。
    # 实际测试前应根据同环境 CX7 实测数据填充；未配置时脚本仅报告当前延时。
    CX7_BASELINE_LATENCY_US = {
        # 示例：512: 2.5,
    }

    # 可接受的延时差异倍数（未配置基准时不生效）
    LATENCY_DIFFERENCE_FACTOR = 2.0

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc027 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-27 测试环境...")

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
        log.info("准备 MC-27 测试环境...")
        cls.server_ip = cls._get_server_ip()

        # 识别所有 pport 并确保 opensm 已启动（server/client 两端均需启动）
        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client"),
        ]:
            pf_list = cls._get_pf_list(exec_addr, name)
            pport_list = cls._get_pport_list(pf_list)
            cls._stop_opensm(exec_addr, name)
            cls._start_opensm_for_pports(exec_addr, name, pport_list)
            cls._verify_opensm_for_pports(exec_addr, name, pport_list)
            cls._verify_all_pf_active(exec_addr, name, pf_list)

        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-27 测试：延时对比")
        log.info("=" * 60)

        try:
            report = []
            fail_details = []

            for size in cls.MSG_SIZES:
                log.info(f"--- 测试包长 {size} ---")
                mc_lat = cls._measure_latency(
                    mode="multicast", msg_size=size,
                    port=cls.PERFTEST_PORT_MC, log_prefix="mc27_mc"
                )
                uc_lat = cls._measure_latency(
                    mode="unicast", msg_size=size,
                    port=cls.PERFTEST_PORT_UC, log_prefix="mc27_uc"
                )

                entry = {
                    "size": size,
                    "mc_lat": mc_lat,
                    "uc_lat": uc_lat,
                }

                # 与 CX7 基准比较
                if size in cls.CX7_BASELINE_LATENCY_US:
                    baseline = cls.CX7_BASELINE_LATENCY_US[size]
                    # 使用多播延时与基准比较
                    if baseline > 0:
                        diff_ratio = mc_lat / baseline
                    else:
                        diff_ratio = float('inf')
                    entry["baseline"] = baseline
                    entry["diff_ratio"] = diff_ratio
                    log.info(
                        f"包长 {size}: 多播延时 {mc_lat:.3f} us, 单播延时 {uc_lat:.3f} us, "
                        f"基准 {baseline:.3f} us, 差异倍数 {diff_ratio:.2f}"
                    )
                    if diff_ratio > cls.LATENCY_DIFFERENCE_FACTOR:
                        detail = (
                            f"包长 {size}: 延时差异倍数 {diff_ratio:.2f} 超过阈值 "
                            f"{cls.LATENCY_DIFFERENCE_FACTOR}"
                        )
                        log.error(detail)
                        fail_details.append(detail)
                else:
                    log.info(
                        f"包长 {size}: 多播延时 {mc_lat:.3f} us, 单播延时 {uc_lat:.3f} us "
                        f"（未配置 CX7 基准）"
                    )

                report.append(entry)

            cls._print_report(report)

            if fail_details:
                cls.bug_result = "部分包长延时差异超过阈值:\n" + "\n".join(fail_details)
                cls.bug_expect = f"各包长延时差异应在 {cls.LATENCY_DIFFERENCE_FACTOR} 倍以内"
                cls.set_bug_type(BugTypeEnum.PERFORMANCE.value)
                cls.create_bug("MC-27 延时对比差异超标")

            log.info("=" * 60)
            log.info("测试执行成功 - MC-27 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-27 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-27 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-27 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-27 测试环境...")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        for size in cls.MSG_SIZES:
            for prefix in ["mc27_mc", "mc27_uc"]:
                cls._remove_log_files(
                    CmdExecuteAdressEnum.SERVER.value, "server",
                    f"/tmp/{prefix}_s{size}_server.log"
                )
                cls._remove_log_files(
                    CmdExecuteAdressEnum.CLIENT.value, "client",
                    f"/tmp/{prefix}_s{size}_client.log"
                )
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        log.info("MC-27 清理完成")
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
        cls.create_bug("MC-27 获取服务端 IP 失败")

    @classmethod
    def _measure_latency(cls, mode: str, msg_size: int, port: int, log_prefix: str) -> float:
        """测量指定模式/包长下的延时，返回 us"""
        server_log = f"/tmp/{log_prefix}_s{msg_size}_server.log"
        client_log = f"/tmp/{log_prefix}_s{msg_size}_client.log"

        if mode == "multicast":
            server_cmd = (
                f"ib_send_lat -d {cls.server_device} -g -M {cls.MGID} "
                f"-s {msg_size} -p {port} -D 60 -F"
            )
            client_cmd = (
                f"ib_send_lat -d {cls.client_device} -g -M {cls.MGID} "
                f"-s {msg_size} -p {port} -D 60 -F {cls.server_ip}"
            )
        else:
            server_cmd = (
                f"ib_send_lat -d {cls.server_device} -s {msg_size} -p {port} -D 60 -F"
            )
            client_cmd = (
                f"ib_send_lat -d {cls.client_device} -s {msg_size} -p {port} -D 60 -F {cls.server_ip}"
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
        return cls._extract_latency(client_output, mode, msg_size)

    @classmethod
    def _start_perftest_server(cls, exec_addr: str, name: str, cmd: str, log_path: str) -> None:
        log.info(f"在 {name} 端启动 perftest server: {cmd}")
        full_cmd = f"nohup {cmd} >\"{log_path}\" 2>&1 &"
        status, result, err = CommandOperation.execute_command_with_error(full_cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端启动 perftest server 失败: {err}"
            cls.bug_expect = "ib_send_lat server 应能后台启动"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-27 {name} 端启动 perftest server 失败")

    @classmethod
    def _start_perftest_client(cls, exec_addr: str, name: str, cmd: str, log_path: str) -> None:
        log.info(f"在 {name} 端启动 perftest client: {cmd}")
        full_cmd = f"nohup {cmd} >\"{log_path}\" 2>&1 &"
        status, result, err = CommandOperation.execute_command_with_error(full_cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端启动 perftest client 失败: {err}"
            cls.bug_expect = "ib_send_lat client 应能后台启动"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-27 {name} 端启动 perftest client 失败")

    @classmethod
    def _read_log(cls, exec_addr: str, name: str, log_path: str) -> str:
        cmd = f"cat \"{log_path}\""
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            return ""
        return result

    @classmethod
    def _extract_latency(cls, output: str, mode: str, msg_size: int) -> float:
        """从 ib_send_lat 输出中提取延时（us）"""
        # ib_send_lat 输出格式：
        # 1) 默认 -n 模式：#bytes #iterations t_min[usec] t_max[usec] t_typical[usec]
        # 2) -D 模式：     #bytes #iterations t_avg[usec] tps average
        # 兼容以上两种格式，优先取 t_typical；使用 -D 时取 t_avg。
        pattern = re.compile(
            r"^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)(?:\s+(\d+\.\d+|\d+))?",
            re.MULTILINE,
        )
        matches = pattern.findall(output)
        if not matches:
            cls.bug_result = (
                f"{mode} 包长 {msg_size} 未找到有效延时输出。输出:\n{output}"
            )
            cls.bug_expect = "ib_send_lat 输出中应包含 t_typical/t_avg[usec] 统计行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-27 {mode} 包长 {msg_size} 无有效延时")

        last = matches[-1]
        # 5 列时 last[4] 为 t_typical；4 列(-D)时 last[4] 为空，取 last[2] 即 t_avg
        lat_value = float(last[4]) if last[4] else float(last[2])
        if lat_value < 0:
            cls.bug_result = (
                f"{mode} 包长 {msg_size} 延时为负值: {lat_value}。输出:\n{output}"
            )
            cls.bug_expect = "ib_send_lat 延时应大于等于 0"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-27 {mode} 包长 {msg_size} 延时异常")

        return lat_value

    @classmethod
    def _print_report(cls, report: list) -> None:
        log.info("=" * 60)
        log.info("MC-27 延时对比报告")
        log.info("=" * 60)
        for entry in report:
            size = entry["size"]
            mc = entry["mc_lat"]
            uc = entry["uc_lat"]
            if "baseline" in entry:
                log.info(
                    f"包长 {size:5d}: 多播 {mc:10.3f} us | 单播 {uc:10.3f} us | "
                    f"基准 {entry['baseline']:.3f} us | 差异倍数 {entry['diff_ratio']:.2f}"
                )
            else:
                log.info(
                    f"包长 {size:5d}: 多播 {mc:10.3f} us | 单播 {uc:10.3f} us | 基准未配置"
                )
        log.info("=" * 60)

    @classmethod
    def _stop_perftest_processes(cls, exec_addr: str, name: str) -> None:
        """停止 perftest 进程（使用 -x 精确匹配，避免误杀 SSH 会话）"""
        cmd = 'pkill -9 -x ib_send_lat 2>/dev/null || true'
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 ib_send_lat 进程已清理")

    @classmethod
    def _remove_log_files(cls, exec_addr: str, name: str, log_path: str) -> None:
        cmd = f"rm -f \"{log_path}\""
        CommandOperation.execute_command_with_error(cmd, exec_addr)

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
            cls.create_bug(f"MC-27 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-27 {name} 端 PF 列表为空")

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
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_mc27_{idx}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端为 pport {pport} 启动 opensm 失败: {err}"
                cls.bug_expect = "opensm 应能在每个 pport 上成功启动"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-27 {name} 端 pport {pport} opensm 启动失败")
            time.sleep(3)

        # 等待 opensm 完成子网扫描
        time.sleep(cls.OPENSM_STARTUP_WAIT)

    @classmethod
    def _verify_opensm_for_pports(cls, exec_addr: str, name: str, pport_list: list) -> None:
        """验证每个 pport 上的 opensm 进程正在运行"""
        log.info(f"验证 {name} 端所有 pport 的 opensm 进程...")

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
            cls.create_bug(f"MC-27 {name} 端 opensm 进程数量不足")

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
                cls.create_bug(f"MC-27 {name} 端 PF {pf} 未 Active")
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
            cls.create_bug(f"MC-27 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-27 {name} 端解析 {device} GUID 失败")

        return match.group(0)

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
        cls.bug_expect = "MC-27 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc027.run()


if __name__ == '__main__':
    main()
