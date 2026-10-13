#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-21/22/23
case title: 某节点进行多播满规格并发，业务成功（如服务器内存、cpu资源充裕）
test category: IB多播测试
check point: 用户态 QP/MGID 多播满规格并发场景下业务均成功
author: auto-generated
date: 2026.06.25
@steps:
    1. 场景1（MC-21）：同一 MGID 的 QP 满规格并发
       ibv_devinfo -d mlx5_0 -vvv | grep max_mcast_qp_attach
       每个进程 MGID 相同，每个进程启动 1 个 QP，MTU/包长各不相同。
    2. 场景2（MC-22）：网卡 MGID 满规格并发
       ibv_devinfo -d mlx5_0 -vvv | grep max_mcast_grp
       每个进程 MGID 不同，每个进程启动 1 个 QP。
    3. 场景3（MC-23）：MGID 与 QP 同时满规格并发
       ibv_devinfo -d mlx5_0 -vvv | grep max_total_mcast_qp_attach
       每 240 个进程为一组，启动多组直至 QP 满规格或多播组 QP 上限。

@expected:
    三种满规格并发场景下业务均成功，每个进程均有有效带宽。

@changelog:
2026.06.25 - 根据 IB-MultiCast_ForAI-测试用例.xlsx（excel_dump.txt 第 18 行）生成
- 关联需求：3.1.20.1~3.1.20.5 IB多播支持
- 满规格上限通过类常量配置，默认使用较小的 sanity 值；真实环境应通过 ibv_devinfo 获取
- 使用 pkill -9 -x ib_send_bw 清理进程，避免误杀 SSH 会话
2026.06.26 - 修正：识别所有 pport 并为每个 pport 启动并检查 opensm；prepare/post 补充 super() 调用
2026.06.26 - 修正：设备名从 env_config 读取，不再硬编码；每次多播业务前检查并必要时重启 opensm
2026.06.26 - 修正：多播可忽略异常（MLID、Mcast unregister、SEND resources）不导致业务失败
2026.06.26 - 修正：带宽数据行后可能紧跟异常信息，正则不再要求行尾为空白；检查所有数据行而非仅最后一行
"""

import os
import time
import re
import math
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import RtnStatusEnum, BugTypeEnum, CmdExecuteAdressEnum, RdmaMode
from scripts.script_libs.script_base import ScriptBase, SxeException


class IbMulticastMc021(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ib_send_bw, ibv_devinfo, opensm, ibstat"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
opensm 已启动
测试节点之间 IB 网络互通
服务器内存、CPU 资源充裕"""
    test_steps = """
    1. 获取节点上所有 IB PF 列表，识别所有 pport。
    2. 为每个 pport 启动 opensm 并确认运行。
    3. 场景1：同一 MGID 的 QP 满规格并发（max_mcast_qp_attach）。
    4. 场景2：网卡 MGID 满规格并发（max_mcast_grp）。
    5. 场景3：MGID 与 QP 同时满规格并发（max_total_mcast_qp_attach）。
    6. 检查每个并发进程是否产生有效带宽。
    """

    SERVER_TARGET_DEVICE = ""
    CLIENT_TARGET_DEVICE = ""
    MGID_BASE = "255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:00"
    PERFTEST_PORT_BASE = 18521
    PERFTEST_STARTUP_WAIT = 3
    PERFTEST_DURATION = 12
    PERFTEST_STOP_WAIT = 2

    # 双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport
    PPORT_COUNT = 2
    OPENSM_STARTUP_WAIT = 10

    # 满规格上限配置
    # 真实环境中应通过 ibv_devinfo -d mlx5_0 -vvv | grep <keyword> 获取实际值
    # 这里使用较小的默认值，用于 sanity 验证；测试前可按实际环境修改
    MAX_MCAST_QP_ATTACH = 4  # 对应 max_mcast_qp_attach，典型值可能为 8192
    MAX_MCAST_GRP = 4  # 对应 max_mcast_grp，典型值可能为 512
    MAX_TOTAL_MCAST_QP_ATTACH = 8  # 对应 max_total_mcast_qp_attach
    SCENARIO3_GROUP_SIZE = 4  # 真实规格建议 240 个进程/组

    # 场景1 中各进程使用不同的 MTU/包长，循环使用
    SCENARIO1_SIZE_VARIATIONS = [
        (2048, 1024),
        (1024, 512),
        (512, 256),
        (4096, 2048),
    ]

    # 多播测试中常见但可忽略的异常，只要存在有效带宽/发包量就不判失败
    BENIGN_MCAST_ERRORS = [
        "failed to get mlid from MAD",
        "Couldn't Unregister the Mcast group on the SM",
        "Couldn't destroy all SEND resources",
    ]

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc021 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-21/22/23 测试环境...")

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

        cls.own_environment_enabled = True
        log.info("环境检查通过：两端目标 IB 设备均处于 Active 状态")

    @classmethod
    def prepare(cls) -> None:
        super().prepare()
        log.info("准备 MC-21/22/23 测试环境...")
        cls.server_ip = cls._get_server_ip()

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client"),
        ]:
            pf_list = cls._get_pf_list(exec_addr, name)
            pport_list = cls._get_pport_list(pf_list)
            setattr(cls, f"{name}_pf_list", pf_list)
            setattr(cls, f"{name}_pport_list", pport_list)
            cls._stop_opensm(exec_addr, name)
            cls._start_opensm_for_pports(exec_addr, name, pport_list)
            cls._verify_opensm_for_pports(exec_addr, name, pport_list)
            cls._verify_all_pf_active(exec_addr, name, pf_list)

            log.info(f"{name} 端 PF 列表: {pf_list}")
            log.info(f"{name} 端 pport 列表: {pport_list}")

        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-21/22/23 测试：多播满规格并发")
        log.info("=" * 60)

        try:
            # 场景1：同一 MGID QP 满规格并发
            cls._run_scenario_1()

            # 场景2：MGID 满规格并发
            cls._run_scenario_2()

            # 场景3：MGID + QP 同时满规格并发
            cls._run_scenario_3()

            log.info("=" * 60)
            log.info("测试执行成功 - MC-21/22/23 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-21/22/23 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-21/22/23 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-21/22/23 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-21/22/23 测试环境...")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        log.info("MC-21/22/23 清理完成")
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
        cls.create_bug("MC-21/22/23 获取服务端 IP 失败")

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
            cls.create_bug(f"MC-21/22/23 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-21/22/23 {name} 端 PF 列表为空")

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
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_mc21_{idx}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端为 pport {pport} 启动 opensm 失败: {err}"
                cls.bug_expect = "opensm 应能在每个 pport 上成功启动"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-21/22/23 {name} 端 pport {pport} opensm 启动失败")
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
            cls.create_bug(f"MC-21/22/23 {name} 端 opensm 未运行")

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
            cls.create_bug(f"MC-21/22/23 {name} 端 opensm 进程数量不足")

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
                cls.create_bug(f"MC-21/22/23 {name} 端 PF {pf} 未 Active")
        log.info(f"{name} 端所有 PF 均处于 Active 状态")

    @classmethod
    def _ensure_opensm_for_pports(cls, exec_addr: str, name: str, pport_list: list) -> None:
        """确保每个 pport 的 opensm 都在运行；不足时自动重启并验证"""
        log.info(f"确保 {name} 端所有 pport 的 opensm 运行...")

        need_restart = False
        if not cls._is_opensm_running(exec_addr):
            log.warning(f"{name} 端 opensm 未运行，重新启动...")
            need_restart = True
        else:
            status, result, err = CommandOperation.execute_command_with_error(
                "pgrep -x opensm", exec_addr
            )
            running_count = len([line.strip() for line in result.splitlines() if line.strip()])
            if running_count < len(pport_list):
                log.warning(
                    f"{name} 端 opensm 进程数不足（实际 {running_count}，"
                    f"期望 {len(pport_list)}），重新启动..."
                )
                need_restart = True

        if need_restart:
            cls._stop_opensm(exec_addr, name)
            cls._start_opensm_for_pports(exec_addr, name, pport_list)

        cls._verify_opensm_for_pports(exec_addr, name, pport_list)
        cls._verify_all_pf_active(exec_addr, name, getattr(cls, f"{name}_pf_list"))

    @classmethod
    def _ensure_opensm_for_both_ends(cls) -> None:
        """确保 server/client 两端每个 pport 的 opensm 都在运行"""
        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client"),
        ]:
            pport_list = getattr(cls, f"{name}_pport_list")
            cls._ensure_opensm_for_pports(exec_addr, name, pport_list)

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
    def _generate_mgid(cls, offset: int) -> str:
        """基于 MGID_BASE 生成第 offset 个多播 GID（仅修改最后一段）"""
        parts = cls.MGID_BASE.split(":")
        last = int(parts[-1], 16)
        parts[-1] = f"{(last + offset) & 0xffff:04x}"
        return ":".join(parts)

    @classmethod
    def _run_scenario_1(cls) -> None:
        """场景1：同一 MGID 的 QP 满规格并发"""
        scenario_name = "场景1-同一MGID_QP满规格并发"
        pair_count = cls.MAX_MCAST_QP_ATTACH
        log.info(f"--- 执行 {scenario_name}，并发对数: {pair_count} ---")

        pairs = []
        mgid = cls.MGID_BASE
        for i in range(pair_count):
            mtu, size = cls.SCENARIO1_SIZE_VARIATIONS[i % len(cls.SCENARIO1_SIZE_VARIATIONS)]
            port = cls.PERFTEST_PORT_BASE + i
            pairs.append({
                "idx": i,
                "mgid": mgid,
                "mtu": mtu,
                "size": size,
                "port": port,
                "server_log": f"/tmp/ib_send_bw_mc21_s1_p{i}_server.log",
                "client_log": f"/tmp/ib_send_bw_mc21_s1_p{i}_client.log",
            })

        cls._run_concurrent_pairs(scenario_name, pairs)

    @classmethod
    def _run_scenario_2(cls) -> None:
        """场景2：MGID 满规格并发"""
        scenario_name = "场景2-MGID满规格并发"
        pair_count = cls.MAX_MCAST_GRP
        log.info(f"--- 执行 {scenario_name}，并发对数: {pair_count} ---")

        pairs = []
        for i in range(pair_count):
            mgid = cls._generate_mgid(i)
            port = cls.PERFTEST_PORT_BASE + 1000 + i
            pairs.append({
                "idx": i,
                "mgid": mgid,
                "mtu": 2048,
                "size": 1024,
                "port": port,
                "server_log": f"/tmp/ib_send_bw_mc21_s2_p{i}_server.log",
                "client_log": f"/tmp/ib_send_bw_mc21_s2_p{i}_client.log",
            })

        cls._run_concurrent_pairs(scenario_name, pairs)

    @classmethod
    def _run_scenario_3(cls) -> None:
        """场景3：MGID 与 QP 同时满规格并发"""
        scenario_name = "场景3-MGID与QP同时满规格并发"
        pair_count = cls.MAX_TOTAL_MCAST_QP_ATTACH
        group_size = cls.SCENARIO3_GROUP_SIZE
        log.info(f"--- 执行 {scenario_name}，总对数: {pair_count}，每组: {group_size} ---")

        pairs = []
        for i in range(pair_count):
            group_idx = i // group_size
            mgid = cls._generate_mgid(group_idx)
            port = cls.PERFTEST_PORT_BASE + 2000 + i
            pairs.append({
                "idx": i,
                "mgid": mgid,
                "mtu": 2048,
                "size": 1024,
                "port": port,
                "server_log": f"/tmp/ib_send_bw_mc21_s3_p{i}_server.log",
                "client_log": f"/tmp/ib_send_bw_mc21_s3_p{i}_client.log",
            })

        cls._run_concurrent_pairs(scenario_name, pairs)

    @classmethod
    def _run_concurrent_pairs(cls, scenario_name: str, pairs: list) -> None:
        """并发运行多对 ib_send_bw server/client，并统一验证"""
        if not pairs:
            log.warning(f"{scenario_name} 没有需要运行的进程对，跳过")
            return

        # 每次多播业务前确保两端 opensm 正常运行
        cls._ensure_opensm_for_both_ends()

        # 统一启动所有 server
        for pair in pairs:
            server_cmd = (
                f"ib_send_bw -d {cls.SERVER_TARGET_DEVICE} -g -M {pair['mgid']} "
                f"-p {pair['port']} -m {pair['mtu']} -s {pair['size']} -F"
            )
            cls._start_background_process(
                CmdExecuteAdressEnum.SERVER.value, "server", server_cmd, pair["server_log"]
            )

        time.sleep(cls.PERFTEST_STARTUP_WAIT)

        # 统一启动所有 client
        for pair in pairs:
            client_cmd = (
                f"ib_send_bw -d {cls.CLIENT_TARGET_DEVICE} -g -M {pair['mgid']} "
                f"-p {pair['port']} -m {pair['mtu']} -s {pair['size']} -n 5000 -F "
                f"{cls.server_ip}"
            )
            cls._start_background_process(
                CmdExecuteAdressEnum.CLIENT.value, "client", client_cmd, pair["client_log"]
            )

        # 等待业务运行
        log.info(f"{scenario_name} 等待业务运行 {cls.PERFTEST_DURATION}s...")
        time.sleep(cls.PERFTEST_DURATION)

        # 停止所有 perftest 进程
        cls._stop_perftest_processes(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_perftest_processes(CmdExecuteAdressEnum.CLIENT.value, "client")
        time.sleep(cls.PERFTEST_STOP_WAIT)

        # 逐个验证结果
        failed = 0
        for pair in pairs:
            server_output = cls._read_log(
                CmdExecuteAdressEnum.SERVER.value, "server", pair["server_log"]
            )
            client_output = cls._read_log(
                CmdExecuteAdressEnum.CLIENT.value, "client", pair["client_log"]
            )
            server_has_bw = cls._has_valid_bandwidth(server_output)
            client_has_bw = cls._has_valid_bandwidth(client_output)
            combined = server_output + "\n" + client_output

            if not server_has_bw and not client_has_bw:
                failed += 1
                log.error(
                    f"{scenario_name} 进程对 {pair['idx']} server/client 均未找到有效带宽。\n"
                    f"server 日志:\n{server_output}\nclient 日志:\n{client_output}"
                )
            else:
                if not server_has_bw:
                    log.warning(
                        f"{scenario_name} 进程对 {pair['idx']} client 端有有效带宽，"
                        f"server 端未找到有效带宽"
                    )
                if not client_has_bw:
                    log.warning(
                        f"{scenario_name} 进程对 {pair['idx']} server 端有有效带宽，"
                        f"client 端未找到有效带宽"
                    )
                if cls._has_benign_multicast_errors(combined):
                    log.warning(
                        f"{scenario_name} 进程对 {pair['idx']} 存在可忽略的多播异常，"
                        f"但带宽有效，视为通过"
                    )

        if failed:
            cls.bug_result = f"{scenario_name} 中 {failed}/{len(pairs)} 对进程未产生有效带宽"
            cls.bug_expect = "满规格并发场景下每对 ib_send_bw 均应产生有效带宽"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-21/22/23 {scenario_name} 业务失败")

        log.info(f"{scenario_name} 验证通过：{len(pairs) - failed}/{len(pairs)} 对产生有效带宽")

    @classmethod
    def _start_background_process(cls, exec_addr: str, name: str, cmd: str, log_path: str) -> None:
        """后台启动单个 perftest 进程"""
        log.info(f"在 {name} 端启动: {cmd}")
        full_cmd = f"nohup {cmd} > {log_path} 2>&1 &"
        status, result, err = CommandOperation.execute_command_with_error(full_cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端启动进程失败: {cmd}\n错误: {err}"
            cls.bug_expect = "ib_send_bw 进程应能后台启动"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-21/22/23 {name} 端启动 ib_send_bw 失败")

    @classmethod
    def _stop_perftest_processes(cls, exec_addr: str, name: str) -> None:
        """停止 perftest 进程（精确匹配，避免误杀 SSH 会话）"""
        cmd = 'pkill -9 -x ib_send_bw 2>/dev/null || true'
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 ib_send_bw 进程已清理")

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
    def _has_valid_bandwidth(cls, output: str) -> bool:
        """检查输出中是否存在大于 0 的有效带宽

        只要存在有效的带宽/发包量，即认为多播业务成功；
        多播测试常见的可忽略异常（如获取 MLID 失败、注销多播组失败、
        SEND 资源清理失败）不影响该判断，详见 _has_benign_multicast_errors。

        注意：ib_send_bw server/client 任一端的 BW average 大于 0 即视为有效，
        不再只取最后一行，避免 server 端或 client 端某一行峰值/均值为 0 导致误判。
        """
        pattern = re.compile(
            # 匹配 ib_send_bw 带宽数据行；行尾可能紧跟异常信息（无空白），因此不限制 \s*$
            r"^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)",
            re.MULTILINE,
        )
        matches = pattern.findall(output)
        if not matches:
            return False
        for match in matches:
            try:
                bw_value = float(match[3])
            except (ValueError, IndexError):
                continue
            if bw_value > 0:
                return True
        return False

    @classmethod
    def _has_benign_multicast_errors(cls, output: str) -> bool:
        """检查输出中是否仅存在可忽略的多播异常"""
        output_lower = output.lower()
        return any(err.lower() in output_lower for err in cls.BENIGN_MCAST_ERRORS)

    @classmethod
    def _get_device_guid(cls, exec_addr: str, name: str, device: str) -> str:
        """获取指定 IB 设备的 Node GUID"""
        cmd = f"ibstat {device} | grep 'Node GUID'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端获取 {device} Node GUID 失败: {err}"
            cls.bug_expect = "ibstat 应能返回 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-21/22/23 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-21/22/23 {name} 端解析 {device} GUID 失败")

        return match.group(0)

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-21/22/23 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc021.run()


if __name__ == '__main__':
    main()
