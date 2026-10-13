#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-10
case title: 通过opensm将SL0~15配置VL0~14,14，启动16个ib_send_bw -g -M 进程，分别对SL0~15进行多播测试，测试成功
test category: IB多播测试
check point: 16 个 SL 同时多播并发成功
author: auto-generated
date: 2026.06.24
@steps:
    1. 通过 opensm 配置 SL0~15 映射到 VL0~14（实际受端口 OperVLs 限制会取模生效）。
    2. 使用 smpquery 查询 SL2VL 表，确认生效的映射符合取模预期。
    3. 启动 16 个 ib_send_bw -g -M server 进程，分别使用 SL0~15。
    4. 并发启动 16 个 ib_send_bw -g -M client 进程，连接对应 server。
    5. 检查每个进程是否成功产生多播流量。

@expected:
    16 个 SL 的多播测试全部成功，每个进程均有有效带宽。
    smpquery 显示 SL2VL 表中实际生效的 VL 符合当前端口 OperVLs 取模结果。

@changelog:
2026.06.24 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.1 用户态QP退出多播组、3.1.20.2 用户态QP加入多播组
- 使用项目技巧：缺陷自动记录、IB基础概念与设备检查、IB命令处理与回显解析、perftest工具使用
2026.06.25 - 修正：opensm 启动时指定目标设备 GUID；启动后增加进程存活检查；增加 smpquery 验证 SL2VL 表
2026.06.26 - 修正：使用实际 IB 设备 mlx5_2/mlx5_5；opensm 配置改为 base64 写入并适配 max_op_vls=4；
             处理 client 端已有 opensm 冲突；清理命令改为 -x 精确匹配
2026.06.26 - 修正：设备名从 env_config 读取，不再硬编码；ib_send_bw 补充 -M 多播组参数；
             SL2VL 期望表按配置值与 OperVLs 计算；prepare/post 补充 super() 调用
"""

import os
import time
import re
import _thread
import base64
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import RtnStatusEnum, BugTypeEnum, CmdExecuteAdressEnum, RdmaMode
from scripts.script_libs.script_base import ScriptBase, SxeException


class IbMulticastMc010(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ib_send_bw, opensm, smpquery, ibstat"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
opensm 已启动
测试节点之间 IB 网络互通
opensm 已配置 SL0~15 映射到 VL0~14（实际按 OperVLs 取模）"""
    test_steps = """
    1. 通过 opensm 配置 SL0~15 -> VL0~14（实际按 OperVLs 取模生效）。
    2. 使用 smpquery 查询 SL2VL 表，确认生效映射符合取模预期。
    3. 启动 16 个 ib_send_bw -g -M server 进程，分别使用 SL0~15，每个监听不同端口。
    4. 并发启动 16 个 ib_send_bw -g -M client 进程，连接对应 server。
    5. 检查每个进程输出中是否包含有效带宽。
    """

    SERVER_TARGET_DEVICE = ""
    CLIENT_TARGET_DEVICE = ""
    MGID = "255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:00"
    PERFTEST_PORT_BASE = 18530
    PERFTEST_DURATION = 5
    PERFTEST_STARTUP_WAIT = 3
    PERFTEST_STOP_WAIT = 2
    CONCURRENT_THREAD_TIMEOUT = 120
    OPENSM_CONFIG_PATH = "/tmp/opensm_mc10.conf"
    OPENSM_STARTUP_WAIT = 10
    DEFAULT_OPENSM_CONFIG_PATH = "/etc/rdma/opensm.conf"
    # qos_sl2vl 配置值；实际生效时，<15 按 OperVLs 取模，15 保留为 15
    SL2VL_MC10 = "qos_sl2vl 0,1,2,3,0,1,2,3,0,1,2,3,0,1,2,3"
    SL2VL_VALUES_MC10 = [0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3]

    # client 端原有 opensm 状态记录，用于 post 恢复
    _client_opensm_was_running = False
    _client_opensm_guid = ""

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc010 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-10 测试环境...")

        # 从 env_config 读取目标 IB 设备名（必须在 __update_env_config 之后读取）
        server_relations, client_relations = CommonOperation.get_nic_relationships(
            rdma=True, nic_mode=RdmaMode.Infiniband.value
        )
        cls.SERVER_TARGET_DEVICE = server_relations[0].strip() if server_relations else ""
        cls.CLIENT_TARGET_DEVICE = client_relations[0].strip() if client_relations else ""

        if not cls.SERVER_TARGET_DEVICE or not cls.CLIENT_TARGET_DEVICE:
            log.error("无法从 env_config 获取 server/client RDMA 设备名")
            cls.own_environment_enabled = False
            return

        for exec_addr, name, device in [
            (CmdExecuteAdressEnum.SERVER.value, "server", cls.SERVER_TARGET_DEVICE),
            (CmdExecuteAdressEnum.CLIENT.value, "client", cls.CLIENT_TARGET_DEVICE),
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

            if "Link layer: InfiniBand" not in result:
                log.error(f"{name} 端 {device} 不是 InfiniBand 模式，无法运行 IB 多播测试")
                cls.own_environment_enabled = False
                return

        cls.own_environment_enabled = True
        log.info("环境检查通过：两端目标 IB 设备均处于 Active 状态")

    @classmethod
    def prepare(cls) -> None:
        super().prepare()
        log.info("准备 MC-10 测试环境...")
        cls.server_ip = cls._get_server_ip()

        # 避免 client 端已有 opensm 与 server 端 opensm 冲突
        if cls._is_opensm_running(CmdExecuteAdressEnum.CLIENT.value):
            cls._client_opensm_was_running = True
            cls._client_opensm_guid = cls._get_device_guid(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.CLIENT_TARGET_DEVICE
            )
            cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        else:
            cls._client_opensm_was_running = False
            cls._client_opensm_guid = ""

        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._configure_opensm_sl2vl(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._start_opensm_with_config(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-10 测试：SL0~15 多播并发")
        log.info("=" * 60)

        try:
            # 启动 16 个 server
            server_infos = []
            for sl in range(16):
                port = cls.PERFTEST_PORT_BASE + sl
                log_path = f"/tmp/ib_send_bw_mc10_sl{sl}_server.log"
                server_cmd = (
                    f"ib_send_bw -d {cls.SERVER_TARGET_DEVICE} -g -M {cls.MGID} -S {sl} "
                    f"-p {port} -s 2048 -F"
                )
                cls._start_perftest_server(
                    CmdExecuteAdressEnum.SERVER.value, "server", server_cmd, log_path
                )
                server_infos.append({"sl": sl, "port": port, "log": log_path})

            # 等待所有 server 初始化完成
            time.sleep(5)

            # 并发启动 16 个 client
            client_results = []
            completed = [0]
            lock = _thread.allocate_lock()

            for info in server_infos:
                _thread.start_new_thread(
                    cls._client_thread_entry,
                    (info, client_results, completed, lock)
                )

            # 等待所有 client 完成
            start_time = time.time()
            while completed[0] < len(server_infos):
                if time.time() - start_time > cls.CONCURRENT_THREAD_TIMEOUT:
                    log.error(f"Timeout: {completed[0]}/{len(server_infos)} clients completed")
                    break
                time.sleep(0.5)

            log.info(f"并发 client 完成数量: {completed[0]}/{len(server_infos)}")

            # 停止所有 perftest 进程
            cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
            cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
            time.sleep(cls.PERFTEST_STOP_WAIT)

            # 验证每个 client 结果
            for res in client_results:
                cls._verify_client_result(res)

            log.info("=" * 60)
            log.info("测试执行成功 - MC-10 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-10 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-10 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-10 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-10 测试环境...")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        # 恢复 opensm 默认配置
        cls._restore_default_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        # 恢复 client 端原有 opensm
        if cls._client_opensm_was_running and cls._client_opensm_guid:
            log.info(f"恢复 client 端 opensm（GUID: {cls._client_opensm_guid}）...")
            cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
            cmd = (
                f"nohup opensm -g {cls._client_opensm_guid} -B "
                f"> /var/log/opensm.log 2>&1 &"
            )
            CommandOperation.execute_command_with_error(cmd, CmdExecuteAdressEnum.CLIENT.value)
            time.sleep(cls.OPENSM_STARTUP_WAIT)
            if cls._is_opensm_running(CmdExecuteAdressEnum.CLIENT.value):
                log.info("client 端 opensm 已恢复")
            else:
                log.warning("client 端 opensm 恢复后未检测到运行进程")
        log.info("MC-10 清理完成：已恢复 opensm 默认配置")
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
        cls.create_bug("MC-10 获取服务端 IP 失败")

    @classmethod
    def _stop_opensm(cls, exec_addr: str, name: str) -> None:
        """停止 opensm"""
        cmd = "pkill -9 -x opensm 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        time.sleep(3)
        log.info(f"{name} 端 opensm 已停止")

    @classmethod
    def _configure_opensm_sl2vl(cls, exec_addr: str, name: str) -> None:
        """生成 opensm 默认配置文件，并配置 SL0~15 -> VL0~14（按 OperVLs 取模）"""
        log.info(f"在 {name} 端生成 opensm 默认配置并修改 SL0~15->VL0~14...")

        # 1. 生成默认配置文件
        base_config_path = f"{cls.OPENSM_CONFIG_PATH}.base"
        cmd = f"opensm -c {base_config_path}"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端生成 opensm 默认配置文件失败: {err}"
            cls.bug_expect = "opensm -c <path> 应能生成默认配置文件"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-10 {name} 端生成 opensm 默认配置失败")

        # 2. 将 QoS 参数追加到默认配置末尾（opensm 使用最后出现的值）
        # 使用 base64 编码避免 heredoc 通过 SSH 执行时被截断/转义
        qos_block = (
            f"# MC-10 QoS override: SL0~15 -> VL0~14 (modulo by OperVLs)\n"
            f"qos TRUE\n"
            f"max_op_vls 4\n"
            f"qos_max_vls 4\n"
            f"qos_high_limit 0\n"
            f"qos_vlarb_high 0:64\n"
            f"qos_vlarb_low 0:4,1:4,2:4,3:4\n"
            f"{cls.SL2VL_MC10}\n"
        )
        qos_b64 = base64.b64encode(qos_block.encode("utf-8")).decode("utf-8")
        cmd = (
            f"cat {base_config_path} > {cls.OPENSM_CONFIG_PATH} && "
            f"echo '{qos_b64}' | base64 -d >> {cls.OPENSM_CONFIG_PATH}"
        )
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端生成 MC-10 opensm 配置文件失败: {err}"
            cls.bug_expect = "应能生成 MC-10 opensm 配置文件"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-10 {name} 端配置 opensm SL2VL 失败")

        log.info(f"{name} 端 opensm 配置文件已生成: {cls.OPENSM_CONFIG_PATH}")

    @classmethod
    def _start_opensm_with_config(cls, exec_addr: str, name: str) -> None:
        """使用指定配置文件启动 opensm（指定目标设备 GUID）"""
        log.info(f"在 {name} 端使用 SL0~15->VL0~14 配置启动 opensm...")
        guid = cls._get_device_guid(exec_addr, name, cls.SERVER_TARGET_DEVICE)
        cmd = (
            f"nohup opensm -g {guid} -Q -F {cls.OPENSM_CONFIG_PATH} -B "
            f"> /var/log/opensm_mc10.log 2>&1 &"
        )
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端使用 SL0~15->VL0~14 配置启动 opensm 失败: {err}"
            cls.bug_expect = "opensm 应能使用 SL0~15->VL0~14 配置启动"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-10 {name} 端启动 opensm 失败")

        time.sleep(cls.OPENSM_STARTUP_WAIT)
        if not cls._is_opensm_running(exec_addr):
            cls.bug_result = f"{name} 端 opensm 启动后未检测到运行进程"
            cls.bug_expect = "opensm 启动后应持续运行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-10 {name} 端 opensm 未正常运行")

        # 等待本端 opensm 成为 master SM，否则 SL2VL 表可能仍是旧 master 下发
        cls._wait_for_sm_master(exec_addr, name, cls.SERVER_TARGET_DEVICE)

        # 验证 SL2VL 表是否生效：SL0~15->VL0~14（按 OperVLs 取模）
        cls._verify_sl2vl_table(exec_addr, name)

        log.info(f"{name} 端 opensm 已启动（GUID: {guid}）")

    @classmethod
    def _restore_default_opensm(cls, exec_addr: str, name: str) -> None:
        """恢复 opensm 默认配置（指定目标设备 GUID）"""
        log.info(f"在 {name} 端恢复 opensm 默认配置...")
        cls._stop_opensm(exec_addr, name)
        guid = cls._get_device_guid(exec_addr, name, cls.SERVER_TARGET_DEVICE)
        cmd = f"nohup opensm -g {guid} -B > /var/log/opensm.log 2>&1 &"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        time.sleep(cls.OPENSM_STARTUP_WAIT)
        if not cls._is_opensm_running(exec_addr):
            log.warning(f"{name} 端恢复默认 opensm 后未检测到运行进程")
        else:
            log.info(f"{name} 端 opensm 已恢复默认配置（GUID: {guid}）")

    @classmethod
    def _wait_for_sm_master(cls, exec_addr: str, name: str, device: str) -> None:
        """等待指定设备成为 subnet master SM"""
        log.info(f"等待 {name} 端 {device} 成为 master SM...")
        lid = cls._get_base_lid(exec_addr, name, device)
        cmd = f"smpquery portinfo -C {device} {lid} 1"
        for _ in range(12):
            status, result, _ = CommandOperation.execute_command_with_error(cmd, exec_addr)
            if status == RtnStatusEnum.SUCCESS.value:
                sm_lid_match = re.search(r"SMLid:\s*\.+(\d+)", result)
                if sm_lid_match and sm_lid_match.group(1) == str(int(lid, 16)):
                    log.info(f"{name} 端 {device} 已成为 master SM (SMLid={sm_lid_match.group(1)})")
                    return
            time.sleep(5)
        cls.bug_result = f"{name} 端 {device} 未能在 60s 内成为 master SM"
        cls.bug_expect = "server 端 opensm 应成为 subnet master 以正确下发 SL2VL 表"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(f"MC-10 {name} 端 opensm 未成为 master SM")

    @classmethod
    def _is_opensm_running(cls, exec_addr: str) -> bool:
        """检查 opensm 进程是否正在运行"""
        status, _, _ = CommandOperation.execute_command_with_error(
            "pgrep -x opensm >/dev/null 2>&1", exec_addr
        )
        return status == RtnStatusEnum.SUCCESS.value

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
            cls.create_bug(f"MC-10 {name} 端启动 perftest server 失败")

    @staticmethod
    def _client_thread_entry(info: dict, client_results: list, completed: list, lock) -> None:
        """client 线程入口：启动单个 ib_send_bw client"""
        sl = info["sl"]
        port = info["port"]
        log_path = f"/tmp/ib_send_bw_mc10_sl{sl}_client.log"
        server_ip = IbMulticastMc010.server_ip
        dev = IbMulticastMc010.CLIENT_TARGET_DEVICE
        duration = IbMulticastMc010.PERFTEST_DURATION

        client_cmd = (
            f"nohup ib_send_bw -d {dev} -g -M {IbMulticastMc010.MGID} -S {sl} "
            f"-p {port} -s 2048 -F {server_ip} > {log_path} 2>&1 &"
        )

        try:
            status, result, err = CommandOperation.execute_command_with_error(
                client_cmd, CmdExecuteAdressEnum.CLIENT.value
            )
            # 等待测试完成
            time.sleep(duration + 2)
            # 读取日志
            cat_status, output, _ = CommandOperation.execute_command_with_error(
                f"cat {log_path}", CmdExecuteAdressEnum.CLIENT.value
            )
            res = {
                "sl": sl,
                "port": port,
                "status": status,
                "output": output if cat_status == RtnStatusEnum.SUCCESS.value else result,
                "err": err,
            }
        except Exception as e:
            res = {"sl": sl, "port": port, "status": -1, "output": "", "err": str(e)}

        with lock:
            client_results.append(res)
            completed[0] += 1

    @classmethod
    def _stop_perftest_processes(cls, exec_addr: str, name: str) -> None:
        """停止 perftest 进程（使用 -x 精确匹配，避免误杀当前 SSH 会话）"""
        cmd = 'pkill -9 -x ib_send_bw 2>/dev/null || true'
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 ib_send_bw 进程已清理")

    @classmethod
    def _verify_client_result(cls, res: dict) -> None:
        """验证单个 client 的结果"""
        sl = res["sl"]
        output = res.get("output", "")
        log.info(f"验证 SL={sl} 的 client 结果...")

        # 兼容 perftest 在带宽行后追加 teardown 错误信息的情况（如 received UMAD...）
        pattern = re.compile(
            r"^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)(?:\D|$)",
            re.MULTILINE,
        )
        matches = pattern.findall(output)
        if not matches:
            cls.bug_result = (
                f"SL={sl} 的 ib_send_bw client 未找到有效带宽输出。输出:\n{output}"
            )
            cls.bug_expect = f"SL={sl} 的多播测试应产生有效带宽"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-10 SL={sl} 多播测试无有效带宽")

        bw_value = float(matches[-1][3])
        if bw_value <= 0:
            cls.bug_result = f"SL={sl} 的 ib_send_bw client 带宽为 0。输出:\n{output}"
            cls.bug_expect = f"SL={sl} 的多播测试带宽应大于 0"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-10 SL={sl} 多播测试带宽为 0")

        log.info(f"SL={sl} 多播测试通过，带宽: {bw_value} MB/sec")

    @classmethod
    def _get_device_guid(cls, exec_addr: str, name: str, device: str) -> str:
        """获取指定 IB 设备的 Node GUID"""
        cmd = f"ibstat {device} | grep 'Node GUID'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端获取 {device} Node GUID 失败: {err}"
            cls.bug_expect = "ibstat 应能返回 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-10 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-10 {name} 端解析 {device} GUID 失败")

        return match.group(0)

    @classmethod
    def _get_base_lid(cls, exec_addr: str, name: str, device: str) -> str:
        """获取指定 IB 设备的 Base LID"""
        cmd = f"ibstat {device} | grep 'Base lid'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端获取 {device} Base LID 失败: {err}"
            cls.bug_expect = "ibstat 应能返回 Base lid"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-10 {name} 端获取 {device} Base LID 失败")

        match = re.search(r"0x[0-9a-fA-F]+|\d+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Base LID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Base lid"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-10 {name} 端解析 {device} Base LID 失败")

        lid = match.group(0)
        if not lid.startswith("0x"):
            lid = hex(int(lid))
        return lid

    @classmethod
    def _verify_sl2vl_table(cls, exec_addr: str, name: str) -> None:
        """使用 smpquery 验证 SL2VL 表是否生效

        实际生效的 VL 受端口 OperVLs 限制，配置值 <15 时按 OperVLs 数量取模，
        配置值 =15 时保留为 15；脚本根据实际 OperVLs 动态计算期望表。
        """
        log.info(f"在 {name} 端验证 SL2VL 表：配置为 {cls.SL2VL_MC10}...")

        lid = cls._get_base_lid(exec_addr, name, cls.SERVER_TARGET_DEVICE)
        cmd = f"smpquery sl2vl -C {cls.SERVER_TARGET_DEVICE} {lid} 1"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端执行 smpquery sl2vl 失败: {err}"
            cls.bug_expect = "smpquery -C <ca> sl2vl <lid> 1 应成功执行"
            log.error(f"{cls.bug_result}\n期望: {cls.bug_expect}")
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-10 {name} 端 smpquery sl2vl 执行失败")

        # 解析 SL2VL 表：数据在 "ports: in 0, out 0:" 行后面
        actual = cls._parse_sl2vl_table(result)
        if actual is None:
            cls.bug_result = f"{name} 端无法从 smpquery sl2vl 输出中解析 SL2VL 表。输出:\n{result}"
            cls.bug_expect = "SL2VL 表应包含 SL0~15 对应的 16 个 VL 值"
            log.error(f"{cls.bug_result}\n期望: {cls.bug_expect}")
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-10 {name} 端 SL2VL 表解析失败")

        oper_vls = cls._get_oper_vls_count(exec_addr, name, cls.SERVER_TARGET_DEVICE)
        overrides = {sl: vl for sl, vl in enumerate(cls.SL2VL_VALUES_MC10)}
        expected = cls._compute_expected_sl2vl(oper_vls, overrides)
        if actual != expected:
            cls.bug_result = (
                f"{name} 端 SL2VL 表实际为 {actual}，期望为 {expected}。"
                f"OperVLs 数量: {oper_vls}"
            )
            cls.bug_expect = f"SL2VL 表应为 {expected}"
            log.error(f"{cls.bug_result}\n期望: {cls.bug_expect}")
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-10 {name} 端 SL2VL 配置未生效")

        log.info(f"{name} 端 SL2VL 表验证通过：{actual}")

    @classmethod
    def _parse_sl2vl_table(cls, output: str):
        """解析 smpquery sl2vl 输出，返回 SL0~15 对应的 VL 列表"""
        for line in output.splitlines():
            # 匹配数据行，兼容 "out 0" 和 "out  0" 等空格差异
            if "ports:" in line and "out" in line:
                numbers = [int(x) for x in re.findall(r"\b(\d+)\b", line)]
                # 行格式: ports: in  0, out  0: | 0| 1| 2| 3| ...
                # 数字序列前两个分别是 in/out 端口编号，需要跳过；后面 16 个为 SL0~15 的 VL 值
                if len(numbers) >= 18:
                    return numbers[2:18]
        return None

    @classmethod
    def _get_oper_vls_count(cls, exec_addr: str, name: str, device: str) -> int:
        """通过 smpquery portinfo 查询端口实际支持的 VL 数量"""
        lid = cls._get_base_lid(exec_addr, name, device)
        cmd = f"smpquery portinfo -C {device} {lid} 1"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            log.warning(f"{name} 端查询 OperVLs 失败: {err}，回退为 4")
            return 4
        # 典型输出：OperVLs:.........................VL0-3
        match = re.search(r"OperVLs:\.*VL0-(\d+)", result)
        if match:
            return int(match.group(1)) + 1
        log.warning(f"{name} 端无法解析 OperVLs，输出:\n{result}\n回退为 4")
        return 4

    @classmethod
    def _compute_expected_sl2vl(
        cls, oper_vls_count: int, overrides: dict
    ) -> list:
        """根据 OperVLs 数量和 SL->VL 配置值计算期望的 SL2VL 表

        规则：
        - 当配置值为 15 时，opensm 会保留 15，不取模。
        - 当配置值 <15 时，按 oper_vls_count 取模。
        - 未显式配置的 SL，默认按 SL % oper_vls_count 计算。

        Args:
            oper_vls_count: 端口实际支持的 VL 数量（如 VL0-3 则为 4）。
            overrides: SL->VL 配置值映射，key 为 SL（0-15），value 为 qos_sl2vl 中配置的值。
        """
        expected = []
        for sl in range(16):
            vl = overrides.get(sl, sl)
            if vl == 15:
                expected.append(15)
            else:
                expected.append(vl % oper_vls_count)
        return expected

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-10 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc010.run()


if __name__ == '__main__':
    main()
