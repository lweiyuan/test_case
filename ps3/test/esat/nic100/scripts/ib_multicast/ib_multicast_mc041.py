#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-41
case title: 在“并发测试”-“多播满规格并发”过程时，创建大于规格的进程，该部分的进程会失败，未超规格的进程不受影响
test category: IB多播
check point: 多播满规格并发时，超出规格的进程失败且不影响已创建的进程
author: auto-generated
date: 2026.06.25
@steps:
    1. 查询或配置多播 QP 附着规格上限（max_mcast_qp_attach）。
    2. 启动等于规格数量的 ib_send_bw -g 多播 server/client 进程对，业务均成功。
    3. 在满规格运行期间，尝试再启动额外的 ib_send_bw -g 进程。
    4. 校验额外进程失败，且已运行的满规格进程不受影响。

@expected:
    等于规格数量的多播进程全部成功并有有效带宽。
    超出规格的进程启动失败。
    已运行进程的业务与进程状态不受影响。

@changelog:
2026.06.25 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.1~3.1.20.5 IB多播支持
- 默认 MAX_MCAST_QP_ATTACH 为 8（便于无真实满规格环境时快速验证），
  真实环境应通过 ibv_devinfo -d <device> -vvv | grep max_mcast_qp_attach 获取实际规格
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


class IbMulticastMc041(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ib_send_bw, opensm, ibstat, ibv_devinfo"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
opensm 已启动
测试节点之间 IB 网络互通
服务器内存、CPU 资源充裕"""
    test_steps = """
    1. 确定目标 IB 端口的多播 QP 附着规格上限 max_mcast_qp_attach。
    2. 在 server/client 两端启动等于规格数量的 ib_send_bw -g 进程对，每个进程 1 个 QP、同一 MGID、不同端口。
    3. 校验所有满规格进程均有有效带宽。
    4. 在满规格运行期间，尝试再启动 1 个额外的 ib_send_bw -g server 进程。
    5. 校验额外进程启动失败，且原有满规格进程仍然正常。
    """

    # 服务端/客户端 IB 设备名，在 check_own_environment() 中从 env_config 动态读取
    server_device = ""
    client_device = ""
    MGID = "255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:00"
    PERFTEST_PORT_BASE = 18541
    # 默认满规格 QP 数量，仅用于无真实满规格环境时快速验证。
    # 真实环境建议：ibv_devinfo -d <device> -vvv | grep max_mcast_qp_attach
    MAX_MCAST_QP_ATTACH = 8
    # 设为 True 时，脚本会尝试从 ibv_devinfo 读取真实规格（需要环境支持）。
    QUERY_REAL_LIMIT = False

    PERFTEST_STARTUP_WAIT = 5
    # perftest 使用 -D 60 运行 60 秒；这里等待 65 秒，留 5 秒启动/收尾余量
    PERFTEST_DURATION = 65
    PERFTEST_VERIFY_WAIT = 65
    PERFTEST_STOP_WAIT = 2
    EXTRA_ATTEMPT_TIMEOUT = 10
    OPENSM_STARTUP_WAIT = 10
    # 双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport
    PPORT_COUNT = 2

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc041 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-41 测试环境...")

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
        log.info("准备 MC-41 测试环境...")
        cls.server_ip = cls._get_server_ip()

        # 获取并记录两端 PF/pport 列表
        cls.server_pf_list = cls._get_pf_list(
            CmdExecuteAdressEnum.SERVER.value, "server"
        )
        cls.client_pf_list = cls._get_pf_list(
            CmdExecuteAdressEnum.CLIENT.value, "client"
        )
        cls.server_pport_list = cls._get_pport_list(cls.server_pf_list)
        cls.client_pport_list = cls._get_pport_list(cls.client_pf_list)

        # 停止已有 opensm，为每个 pport 重新启动并验证
        for exec_addr, name, pf_list, pport_list in [
            (CmdExecuteAdressEnum.SERVER.value, "server", cls.server_pf_list, cls.server_pport_list),
            (CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_pf_list, cls.client_pport_list),
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
        log.info("开始 MC-41 测试：多播满规格并发下超额进程失败")
        log.info("=" * 60)

        try:
            # 确定满规格数量
            max_qp = cls._resolve_max_mcast_qp_attach(
                CmdExecuteAdressEnum.SERVER.value, "server"
            )
            log.info(f"本次测试使用的多播 QP 满规格数量: {max_qp}")

            # 启动满规格 server/client 进程对
            cls._run_full_spec_pairs(max_qp)

            # 等待并校验满规格进程均有带宽
            time.sleep(cls.PERFTEST_VERIFY_WAIT)
            cls._verify_all_clients_bandwidth(max_qp)

            # 尝试启动额外进程，应失败
            cls._attempt_extra_process(max_qp)

            # 再次校验满规格进程未受影响
            time.sleep(2)
            cls._verify_all_clients_bandwidth(max_qp)

            log.info("=" * 60)
            log.info("测试执行成功 - MC-41 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-41 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-41 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-41 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-41 测试环境...")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        log.info("MC-41 清理完成")
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
        cls.create_bug("MC-41 获取服务端 IP 失败")

    @classmethod
    def _resolve_max_mcast_qp_attach(cls, exec_addr: str, name: str) -> int:
        """解析多播 QP 附着规格

        默认返回类常量 MAX_MCAST_QP_ATTACH；当 QUERY_REAL_LIMIT 为 True 时，
        尝试通过 ibv_devinfo 读取真实规格，失败则回退到默认值。
        """
        if not cls.QUERY_REAL_LIMIT:
            log.info(
                f"使用默认满规格数量 {cls.MAX_MCAST_QP_ATTACH}，"
                f"真实环境建议设置 QUERY_REAL_LIMIT=True 或通过类常量指定"
            )
            return cls.MAX_MCAST_QP_ATTACH

        cmd = f"ibv_devinfo -d {cls.server_device} -vvv | grep max_mcast_qp_attach"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value and result.strip():
            match = re.search(r"max_mcast_qp_attach\s*[:=]\s*(\d+)", result)
            if match:
                real_limit = int(match.group(1))
                log.info(f"从 ibv_devinfo 获取到真实满规格数量: {real_limit}")
                return real_limit
            log.warning(f"无法解析 ibv_devinfo 输出中的 max_mcast_qp_attach: {result}")
        else:
            log.warning(f"通过 ibv_devinfo 查询 max_mcast_qp_attach 失败: {err}")

        log.warning(f"回退使用默认满规格数量 {cls.MAX_MCAST_QP_ATTACH}")
        return cls.MAX_MCAST_QP_ATTACH

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
            cls.create_bug(f"MC-41 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-41 {name} 端 PF 列表为空")

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
    def _start_opensm_for_pports(cls, exec_addr: str, name: str, pport_list: list) -> None:
        """为每个 pport 启动 opensm"""
        log.info(f"在 {name} 端为所有 pport 启动 opensm...")

        for idx, pport in enumerate(pport_list):
            guid = cls._get_device_guid(exec_addr, name, pport)
            log.info(f"为 pport {pport} 启动 opensm，GUID: {guid}")
            opensm_cmd = (
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_mc41_{idx}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端为 pport {pport} 启动 opensm 失败: {err}"
                cls.bug_expect = "opensm 应能在每个 pport 上成功启动"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-41 {name} 端 pport {pport} opensm 启动失败")
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
            cls.create_bug(f"MC-41 {name} 端 opensm 进程数量不足")

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
                cls.create_bug(f"MC-41 {name} 端 PF {pf} 未 Active")
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
            cls.create_bug(f"MC-41 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-41 {name} 端解析 {device} GUID 失败")

        return match.group(0)

    @classmethod
    def _run_full_spec_pairs(cls, count: int) -> None:
        """启动 count 个 ib_send_bw -g server/client 进程对"""
        log.info(f"启动 {count} 个 ib_send_bw -g 多播进程对...")

        # 先启动所有 server
        for i in range(count):
            port = cls.PERFTEST_PORT_BASE + i
            server_log = f"/tmp/ib_send_bw_mc41_s{i}_server.log"
            server_cmd = (
                f"ib_send_bw -d {cls.server_device} -g -M {cls.MGID} "
                f"-p {port} -D 60 -F"
            )
            cls._start_perftest_process(
                CmdExecuteAdressEnum.SERVER.value, "server", server_cmd, server_log
            )
            time.sleep(0.2)

        time.sleep(cls.PERFTEST_STARTUP_WAIT)

        # 再启动所有 client
        for i in range(count):
            port = cls.PERFTEST_PORT_BASE + i
            client_log = f"/tmp/ib_send_bw_mc41_s{i}_client.log"
            client_cmd = (
                f"ib_send_bw -d {cls.client_device} -g -M {cls.MGID} "
                f"-p {port} -D 60 -F {cls.server_ip}"
            )
            cls._start_perftest_process(
                CmdExecuteAdressEnum.CLIENT.value, "client", client_cmd, client_log
            )
            time.sleep(0.2)

        time.sleep(cls.PERFTEST_STARTUP_WAIT)
        log.info(f"{count} 个多播进程对已启动")

    @classmethod
    def _start_perftest_process(cls, exec_addr: str, name: str, cmd: str, log_path: str) -> None:
        """后台启动 perftest 进程"""
        log.info(f"在 {name} 端启动 perftest 进程: {cmd}")
        full_cmd = f"nohup {cmd} > {log_path} 2>&1 &"
        status, result, err = CommandOperation.execute_command_with_error(full_cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端启动 perftest 进程失败: {err}"
            cls.bug_expect = "ib_send_bw 进程应能后台启动"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-41 {name} 端启动 perftest 进程失败")

    @classmethod
    def _verify_all_clients_bandwidth(cls, count: int) -> None:
        """校验所有 client 日志中均有有效带宽"""
        log.info(f"校验 {count} 个 client 进程的带宽...")
        for i in range(count):
            client_log = f"/tmp/ib_send_bw_mc41_s{i}_client.log"
            output = cls._read_log(
                CmdExecuteAdressEnum.CLIENT.value, "client", client_log
            )
            cls._verify_single_bandwidth(i, output)
        log.info(f"{count} 个 client 进程带宽校验通过")

    @classmethod
    def _read_log(cls, exec_addr: str, name: str, log_path: str) -> str:
        """读取远程日志文件内容"""
        cmd = f"cat {log_path}"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端读取日志 {log_path} 失败: {err}"
            cls.bug_expect = "perftest 日志文件应存在且可读"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-41 {name} 端读取 perftest 日志失败")
        return result

    @classmethod
    def _verify_single_bandwidth(cls, idx: int, output: str) -> None:
        """检查单个 client 日志中是否存在有效带宽"""
        pattern = re.compile(
            r"^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)",
            re.MULTILINE,
        )
        matches = pattern.findall(output)
        if not matches:
            cls.bug_result = (
                f"满规格进程 {idx} 未找到有效带宽输出。输出:\n{output}"
            )
            cls.bug_expect = "满规格 ib_send_bw client 应产生有效带宽"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-41 满规格进程 {idx} 无有效带宽")

        bw_value = float(matches[-1][3])
        if bw_value <= 0:
            cls.bug_result = f"满规格进程 {idx} 带宽为 0。输出:\n{output}"
            cls.bug_expect = "满规格 ib_send_bw client 带宽应大于 0"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-41 满规格进程 {idx} 带宽为 0")

        log.info(f"满规格进程 {idx} 带宽: {bw_value} MB/sec")

    @classmethod
    def _attempt_extra_process(cls, base_count: int) -> None:
        """尝试启动一个超出规格的 perftest server，应失败"""
        extra_port = cls.PERFTEST_PORT_BASE + base_count
        extra_server_log = "/tmp/ib_send_bw_mc41_extra_server.log"

        log.info(
            f"尝试启动超出规格的额外 ib_send_bw server（端口 {extra_port}），"
            f"预期在 {cls.EXTRA_ATTEMPT_TIMEOUT}s 内失败..."
        )
        server_cmd = (
            f"timeout {cls.EXTRA_ATTEMPT_TIMEOUT}s ib_send_bw -d {cls.server_device} "
            f"-g -M {cls.MGID} -p {extra_port} -D 60 -F "
            f"> {extra_server_log} 2>&1"
        )
        status, _, err = CommandOperation.execute_command_with_error(
            server_cmd, CmdExecuteAdressEnum.SERVER.value
        )
        extra_output = cls._read_log(
            CmdExecuteAdressEnum.SERVER.value, "server", extra_server_log
        )

        if status == RtnStatusEnum.SUCCESS.value:
            cls.bug_result = (
                f"超出规格的额外 ib_send_bw server 启动成功，未按预期失败。\n"
                f"输出:\n{extra_output}"
            )
            cls.bug_expect = "超出 max_mcast_qp_attach 规格的 ib_send_bw 进程应启动失败"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("MC-41 超出规格进程未按预期失败")

        if status == 124:
            cls.bug_result = (
                f"超出规格的额外 ib_send_bw server 运行至超时（{cls.EXTRA_ATTEMPT_TIMEOUT}s），"
                f"说明其可能已成功附着 QP，未按预期失败。\n输出:\n{extra_output}"
            )
            cls.bug_expect = "超出 max_mcast_qp_attach 规格的 ib_send_bw 进程应快速失败"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("MC-41 超出规格进程超时未失败")

        log.info(
            f"额外 ib_send_bw server 已按预期失败（exit code={status}），"
            f"符合超出规格的行为"
        )

    @classmethod
    def _stop_perftest_processes(cls, exec_addr: str, name: str) -> None:
        """停止 perftest 进程（使用 -x 精确匹配，避免误杀 SSH 会话）"""
        cmd = "pkill -9 -x ib_send_bw 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 ib_send_bw 进程已清理")

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-41 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc041.run()


if __name__ == '__main__':
    main()
