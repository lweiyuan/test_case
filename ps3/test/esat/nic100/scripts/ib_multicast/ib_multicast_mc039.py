#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-39
case title: 多对多的多播（ipoib）业务期间，部分客户端发生异常，其余节点业务不受影响（或发生波动并快速收敛--暂无环境，无法调研），异常节点恢复后，可以重新加入多播组
test category: IB多播
check point: ipoib 多对多场景下部分客户端异常后恢复，其余节点业务不受影响
author: auto-generated
date: 2026.06.25
@steps:
    1. 在两端配置 ipoib IPv4 地址与多播路由。
    2. 两端均启动 iperf 多播服务端。
    3. 两端均启动 iperf 多播客户端，建立 2v2 多对多多播业务。
    4. 验证两端服务端均收到多播流量。
    5. （手工步骤）在业务期间人为让部分客户端异常（如下线网口、kill 客户端进程、拔网线、断电等），观察其余节点业务。
    6. （手工步骤）恢复异常客户端，确认可重新加入多播组并恢复业务。

@expected:
    初始 2v2 多对多多播业务成功。
    其余节点业务不受影响（或短暂波动后快速收敛）。
    异常客户端恢复后可重新加入多播组。

@changelog:
2026.06.25 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.3 内核态QP加入多播组、3.1.20.4 内核态QP退出多播组
- 备注：暂无测试环境，异常注入与恢复部分需手工完成，脚本仅完成初始业务搭建与校验
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


class IbMulticastMc039(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ip, iperf, ibdev2netdev, ibstat, opensm"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
已加载 ib_ipoib 驱动，opensm 已启动
同子网内两个节点均已配置 IPv4 地址
已安装 iperf 2.x"""
    test_steps = """
    1. 服务器 A/B 均配置多播路由：ip route add 224.0.0.20 dev ib0。
    2. 服务器 A/B 均启动 iperf 多播服务端：iperf -s -u -B 224.0.0.20 -i 1。
    3. 服务器 A/B 均启动 iperf 多播客户端：iperf -c 224.0.0.20 -u -T 5 -l 128 -i 1 -t <duration> -B <local_ip>。
    4. 检查两端服务端是否均收到多播流量。
    5. （手工）业务期间让部分客户端异常，再恢复，观察业务收敛情况。
    """

    # 服务端/客户端 IB 设备名，在 check_own_environment() 中从 env_config 动态读取
    server_device = ""
    client_device = ""
    MCAST_GROUP = "224.0.0.20"
    IPOIB_SERVER_A_IP = "192.168.100.1/24"
    IPOIB_SERVER_B_IP = "192.168.100.2/24"
    IPOIB_CLIENT_SRC_A = "192.168.100.1"
    IPOIB_CLIENT_SRC_B = "192.168.100.2"
    IPOIB_IFACE_FALLBACK = "ib0"
    IPERF_DURATION = 10
    IPERF_STARTUP_WAIT = 2

    # 双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport
    PPORT_COUNT = 2
    OPENSM_STARTUP_WAIT = 10

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc039 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-39 测试环境...")

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

            status, result, err = CommandOperation.execute_command_with_error(
                "lsmod | grep -w ib_ipoib", exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value or "ib_ipoib" not in result:
                log.error(f"{name} 端未加载 ib_ipoib 驱动")
                cls.own_environment_enabled = False
                return

            status, result, err = CommandOperation.execute_command_with_error("which iperf", exec_addr)
            if status != RtnStatusEnum.SUCCESS.value or not result.strip():
                log.error(f"{name} 端未找到 iperf")
                cls.own_environment_enabled = False
                return

        cls.own_environment_enabled = True
        log.info("环境检查通过：两端目标 IB 设备均处于 Active 状态")

    @classmethod
    def prepare(cls) -> None:
        super().prepare()
        log.info("准备 MC-39 测试环境...")

        # 获取两端 PF 列表并识别 pport
        cls.server_pf_list = cls._get_pf_list(
            CmdExecuteAdressEnum.SERVER.value, "server"
        )
        cls.client_pf_list = cls._get_pf_list(
            CmdExecuteAdressEnum.CLIENT.value, "client"
        )
        cls.server_pport_list = cls._get_pport_list(cls.server_pf_list)
        cls.client_pport_list = cls._get_pport_list(cls.client_pf_list)

        # 停止现有 opensm 并为每个 pport 重新启动
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._start_opensm_for_pports(
            CmdExecuteAdressEnum.SERVER.value, "server", cls.server_pport_list, "mc39"
        )
        cls._start_opensm_for_pports(
            CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_pport_list, "mc39"
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

        cls.server_iface = cls._get_ipoib_iface(
            CmdExecuteAdressEnum.SERVER.value, "server"
        )
        cls.client_iface = cls._get_ipoib_iface(
            CmdExecuteAdressEnum.CLIENT.value, "client"
        )

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-39 测试：ipoib 多对多部分客户端异常恢复")
        log.info("=" * 60)

        try:
            # 配置 IPv4 地址和多播路由
            cls._configure_ipv4(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface, cls.IPOIB_SERVER_A_IP
            )
            cls._configure_ipv4(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface, cls.IPOIB_SERVER_B_IP
            )

            # 启动两端 iperf 服务端
            cls.server_log_a = f"/tmp/mc39_server_a_{cls.server_iface}.log"
            cls.server_log_b = f"/tmp/mc39_server_b_{cls.client_iface}.log"
            cls._start_iperf_server(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface, cls.server_log_a
            )
            cls._start_iperf_server(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface, cls.server_log_b
            )

            # 启动两端 iperf 客户端
            cls.client_log_a = f"/tmp/mc39_client_a_{cls.server_iface}.log"
            cls.client_log_b = f"/tmp/mc39_client_b_{cls.client_iface}.log"
            cls._run_iperf_client(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface,
                cls.IPOIB_CLIENT_SRC_A, cls.client_log_a
            )
            cls._run_iperf_client(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface,
                cls.IPOIB_CLIENT_SRC_B, cls.client_log_b
            )

            # 验证两端服务端均收到流量
            cls._verify_iperf_server_output(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_log_a
            )
            cls._verify_iperf_server_output(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.server_log_b
            )

            # 打印手工操作提示
            cls._print_manual_steps()

            log.info("=" * 60)
            log.info("测试执行成功 - MC-39 初始业务搭建通过（异常恢复部分需手工完成）")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-39 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-39 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-39 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-39 测试环境...")
        cls._stop_iperf(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_iperf(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._remove_ipv4_config(CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface)
        cls._remove_ipv4_config(CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface)
        for log_path in [
            cls.server_log_a, cls.server_log_b, cls.client_log_a, cls.client_log_b
        ]:
            cls._remove_log_files(CmdExecuteAdressEnum.SERVER.value, "server", log_path)
            cls._remove_log_files(CmdExecuteAdressEnum.CLIENT.value, "client", log_path)
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        log.info("MC-39 清理完成")
        super().post()

    @classmethod
    def _get_ipoib_iface(cls, exec_addr: str, name: str) -> str:
        log.info(f"获取 {name} 端 ipoib 网口...")
        cmd = "ibdev2netdev"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端执行 ibdev2netdev 失败: {err}"
            cls.bug_expect = "ibdev2netdev 应成功执行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-39 {name} 端 ibdev2netdev 执行失败")

        # 优先从该端 pport 列表中查找 ib* 网口
        pport_list = getattr(cls, f"{name}_pport_list", [])
        pf_list = getattr(cls, f"{name}_pf_list", [])
        search_devices = pport_list if pport_list else pf_list

        for device in search_devices:
            pattern = re.compile(rf"^{re.escape(device)}\s+port\s+\d+\s+==>\s+(\S+)")
            for line in result.splitlines():
                match = pattern.match(line.strip())
                if match:
                    iface = match.group(1)
                    if iface.startswith("ib"):
                        log.info(f"{name} 端 {device} 对应 ipoib 网口: {iface}")
                        return iface

        # fallback：返回第一个 ib* 接口
        fallback = re.search(r"==>\s+(ib\S+)", result)
        if fallback:
            iface = fallback.group(1)
            log.warning(f"{name} 端未从 pport 找到 ipoib 网口，fallback 为 {iface}")
            return iface

        cls.bug_result = f"{name} 端未找到 ipoib 网口。输出:\n{result}"
        cls.bug_expect = "ibdev2netdev 输出中应包含 ib* 开头的 ipoib 网口"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(f"MC-39 {name} 端获取 ipoib 网口失败")

    @classmethod
    def _configure_ipv4(cls, exec_addr: str, name: str, iface: str, ipv4_addr: str) -> None:
        log.info(f"在 {name} 端 {iface} 上配置 IPv4 地址和多播路由...")
        cmds = [
            f"ip addr flush dev {iface}",
            f"ip addr add {ipv4_addr} dev {iface}",
            f"ip link set {iface} up",
            f"ip route add {cls.MCAST_GROUP} dev {iface} 2>/dev/null || true",
        ]
        for cmd in cmds:
            status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端执行命令失败: {cmd}\n错误: {err}"
                cls.bug_expect = "ip addr/route 命令应成功配置 ipoib 网口"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-39 {name} 端配置 IPv4/多播路由失败")
        log.info(f"{name} 端 {iface} IPv4 和多播路由配置完成")

    @classmethod
    def _start_iperf_server(cls, exec_addr: str, name: str, iface: str, log_path: str) -> None:
        log.info(f"在 {name} 端启动 iperf 多播服务端...")
        cls._stop_iperf(exec_addr, name)
        cmd = (
            f"nohup iperf -s -u -B {cls.MCAST_GROUP} -i 1 "
            f">\"{log_path}\" 2>&1 &"
        )
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端启动 iperf 服务端失败: {err}"
            cls.bug_expect = "iperf -s -u -B <mcast> 应成功启动"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-39 {name} 端启动 iperf 服务端失败")
        time.sleep(cls.IPERF_STARTUP_WAIT)

    @classmethod
    def _run_iperf_client(cls, exec_addr: str, name: str, iface: str, src_ip: str, log_path: str) -> None:
        log.info(f"在 {name} 端启动 iperf 多播客户端...")
        cmd = (
            f"iperf -c {cls.MCAST_GROUP} -u -T 5 -l 128 -i 1 "
            f"-t {cls.IPERF_DURATION} -B {src_ip} "
            f">\"{log_path}\" 2>&1"
        )
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value and not result.strip():
            cls.bug_result = f"{name} 端 iperf 客户端执行失败: {err}"
            cls.bug_expect = "iperf 客户端应向多播组发送流量并正常结束"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-39 {name} 端 iperf 客户端执行失败")

    @classmethod
    def _verify_iperf_server_output(cls, exec_addr: str, name: str, log_path: str) -> None:
        log.info(f"检查 {name} 端 iperf 服务端输出...")
        cmd = f"cat \"{log_path}\""
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or not result.strip():
            cls.bug_result = f"{name} 端 iperf 服务端日志为空或读取失败: {err}"
            cls.bug_expect = "iperf 服务端应收到多播流量"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-39 {name} 端 iperf 服务端输出为空")

        if not re.search(r"\d+\s+(Mbits/sec|Kbits/sec)", result):
            cls.bug_result = (
                f"{name} 端 iperf 服务端未检测到有效多播带宽。输出:\n{result}"
            )
            cls.bug_expect = "iperf 服务端输出中应包含有效的 Mbits/sec/Kbits/sec 带宽"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-39 {name} 端 iperf 多播流量异常")

        log.info(f"{name} 端 iperf 多播流量正常:\n{result.strip()}")

    @classmethod
    def _stop_iperf(cls, exec_addr: str, name: str) -> None:
        cmd = "pkill -9 -x iperf 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 iperf 进程已清理")

    @classmethod
    def _remove_ipv4_config(cls, exec_addr: str, name: str, iface: str) -> None:
        log.info(f"清理 {name} 端 {iface} 的 IPv4 配置...")
        cmds = [
            f"ip route del {cls.MCAST_GROUP} dev {iface} 2>/dev/null || true",
            f"ip addr flush dev {iface}",
        ]
        for cmd in cmds:
            CommandOperation.execute_command_with_error(cmd, exec_addr)
        log.info(f"{name} 端 {iface} IPv4 配置已清理")

    @classmethod
    def _remove_log_files(cls, exec_addr: str, name: str, log_path: str) -> None:
        cmd = f"rm -f \"{log_path}\""
        CommandOperation.execute_command_with_error(cmd, exec_addr)

    @classmethod
    def _print_manual_steps(cls) -> None:
        steps = """
========================================================================
【MC-39 手工操作提示】
当前自动化脚本已完成 2v2 ipoib 多对多多播业务的初始搭建，并验证两端
均能收到多播流量。

由于当前暂无异常注入环境，以下步骤需测试人员手工执行：

1. 在业务运行期间，人为让部分客户端异常，例如：
   - 在 client 端执行：pkill -9 -x iperf，停止该端 iperf 客户端；
   - 或临时 down 掉 client 端 ipoib 网口；
   - 或拔网线 / 断电（请根据实验室安全规范操作）。

2. 观察其余节点（server 端及另一 client 端）的多播业务是否保持正常，
   或仅出现短暂波动后快速收敛。

3. 恢复异常客户端，例如：
   - 重新启动 client 端 iperf 客户端；
   - 或恢复网口 / 上电。

4. 确认异常客户端能够重新加入多播组，业务流量恢复正常。

注意：手工操作部分不阻塞自动化脚本，也不作为当前自动化执行的判定项。
========================================================================
"""
        for line in steps.strip().splitlines():
            log.warning(line)

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-39 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)

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
            cls.create_bug(f"MC-39 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-39 {name} 端 PF 列表为空")

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
    def _get_device_guid(cls, exec_addr: str, name: str, device: str) -> str:
        """获取指定 IB 设备的 Node GUID"""
        cmd = f"ibstat {device} | grep 'Node GUID'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端获取 {device} Node GUID 失败: {err}"
            cls.bug_expect = "ibstat 应能返回 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-39 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-39 {name} 端解析 {device} GUID 失败")

        return match.group(0)

    @classmethod
    def _start_opensm_for_pports(
        cls, exec_addr: str, name: str, pport_list: list, case_tag: str
    ) -> None:
        """为每个 pport 启动 opensm"""
        log.info(f"在 {name} 端为所有 pport 启动 opensm...")

        for idx, pport in enumerate(pport_list):
            guid = cls._get_device_guid(exec_addr, name, pport)
            log.info(f"为 pport {pport} 启动 opensm，GUID: {guid}")
            opensm_cmd = (
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_{case_tag}_{idx}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端为 pport {pport} 启动 opensm 失败: {err}"
                cls.bug_expect = "opensm 应能在每个 pport 上成功启动"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-39 {name} 端 pport {pport} opensm 启动失败")
            time.sleep(3)

        time.sleep(cls.OPENSM_STARTUP_WAIT)

    @classmethod
    def _is_opensm_running(cls, exec_addr: str) -> bool:
        """检查 opensm 进程是否正在运行"""
        status, _, _ = CommandOperation.execute_command_with_error(
            "pgrep -x opensm >/dev/null 2>&1", exec_addr
        )
        return status == RtnStatusEnum.SUCCESS.value

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
            cls.create_bug(f"MC-39 {name} 端 opensm 未运行")

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
            cls.create_bug(f"MC-39 {name} 端 opensm 进程数量不足")

        log.info(
            f"{name} 端 opensm 进程数量: {running_count}，pport 数量: {len(pport_list)}"
        )

    @classmethod
    def _verify_all_pf_active(
        cls, exec_addr: str, name: str, pf_list: list
    ) -> None:
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
                cls.create_bug(f"MC-39 {name} 端 PF {pf} 未 Active")
        log.info(f"{name} 端所有 PF 均处于 Active 状态")


def main() -> None:
    IbMulticastMc039.run()


if __name__ == '__main__':
    main()
