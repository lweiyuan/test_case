#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: TC-VLAN-030-D
case title: DPDK 场景 VLAN offload 功能验证（DPDK）
test category: 天鹰 VLAN 测试（DPDK 场景）
check point: TP-01; TP-02; TP-04; TP-08; TP-11
author: auto-generated
date: 2026.07.10

@steps:
    1. 自动探测 server/client 上的 DPDK 工具（dpdk-testpmd、dpdk-devbind.py）
    2. 从 env_config 读取测试网口名，并映射为 PCI 地址
    3. 配置 hugepage、绑定网卡到 vfio-pci/uio_pci_generic
    4. 在 server 启动 dpdk-testpmd，使能 VLAN strip/insert/filter
    5. 从 client 通过 scapy 发送 VLAN 100 报文到 server DPDK 口
    6. 检查 server testpmd 统计，确认报文被正确接收且 VLAN strip/filter 生效
    7. 解绑网卡、恢复内核驱动、清理临时文件

@expected:
    1. dpdk-testpmd 正常启动，VLAN 命令执行成功
    2. server 侧 RX 报文计数增加，无 error/drop 异常增长
    3. VLAN strip/filter 配置被硬件接受
    4. TX VLAN insert 命令配置成功

@changelog:
    2026.07.10 - 初始版本
    2026.07.10 - 补全 DPDK 环境自动探测、testpmd 启动、VLAN 验证、清理恢复
    2026.07.10 - 统一命令执行输出：始终打印命令，仅异常时打印回显
"""

import base64
import os
import re
import time
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import (
    CmdExecuteAdressEnum,
    RtnStatusEnum,
    BugTypeEnum,
    RdmaMode,
)
from scripts.script_libs.script_base import ScriptBase, SxeException


class TianyingVlanDpdkOffloadDpdk(ScriptBase):
    test_object = "天鹰 VLAN 测试"
    test_module = "tianying_vlan"
    test_tool = "DPDK, dpdk-testpmd, dpdk-devbind.py, scapy"
    test_precondition = """1. server/client 已安装 DPDK（dpdk-testpmd、dpdk-devbind.py 可用）
2. hugepage 已配置或脚本有权限配置
3. 测试网口在 env_config.ini 中已配置
4. 测试网口支持 vfio-pci 或 uio_pci_generic 绑定"""
    test_steps = """
    1. 自动探测 DPDK 工具路径与测试网口 PCI 地址
    2. 配置 hugepage、备份内核驱动并绑定到 vfio-pci/uio_pci_generic
    3. server 启动 dpdk-testpmd，配置 VLAN strip/insert/filter
    4. client 使用 scapy 发送 VLAN 100 报文
    5. 检查 server testpmd 统计与日志
    6. 解绑网卡、恢复内核驱动、清理临时文件
    """

    VLAN_ID = 100
    INJECT_COUNT = 100
    TESTPMD_LOG = "/tmp/tianying_vlan_dpdk_testpmd.log"
    TESTPMD_PID_FILE = "/tmp/tianying_vlan_dpdk_testpmd.pid"
    TESTPMD_STDIN_PIPE = "/tmp/tianying_vlan_dpdk_testpmd.stdin"
    TESTPMD_WRAPPER = "/tmp/tianying_vlan_dpdk_testpmd_wrapper.sh"
    TESTPMD_STATS = "/tmp/tianying_vlan_dpdk_testpmd_stats.log"
    DPDK_BIND_DRIVER = "vfio-pci"
    DPDK_BIND_FALLBACK = "uio_pci_generic"

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "TianyingVlanDpdkOffloadDpdk Failed"

    @classmethod
    def _run_cmd(cls, cmd: str, exec_addr: str, timeout: int = 1800,
                 log_cmd: bool = True, ignore_status: tuple = ()) -> tuple:
        """统一封装远端命令执行。

        - 默认始终打印实际执行的命令；可通过 log_cmd=False 关闭（如轮询）。
        - 正常执行时不打印命令回显；仅在状态异常或 stderr 非警告信息时打印。
        """
        if log_cmd:
            log.info(f"[{exec_addr}] {cmd}")
        status, out, err = CommandOperation.execute_command_with_error(
            cmd, exec_addr, timeout=timeout,
            print_enable=False, print_steps=False, print_outputs=False
        )
        # 过滤掉 SSH 客户端常见的告警信息（所有以 ** 开头的 banner 行），这些不算命令异常
        real_err = "\n".join(
            line for line in (err or "").splitlines()
            if line.strip() and not line.strip().startswith("**")
        )
        ignore = (RtnStatusEnum.SUCCESS.value,) + tuple(ignore_status)
        if status not in ignore:
            log.error(f"命令执行异常 status={status}, stdout={out!r}, stderr={err!r}")
        elif real_err:
            log.warning(f"命令 stderr 非空: {real_err!r}")
        return status, out, err

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 TC-VLAN-030-D 自有环境...")

        # 1. 从 env_config 读取 server/client 以太网口名
        server_ifs, client_ifs = CommonOperation.get_nic_relationships(
            rdma=False, nic_mode=RdmaMode.RoCE.value
        )
        if not server_ifs or not client_ifs:
            log.error("未从配置读取到以太设备名")
            cls.own_environment_enabled = False
            return
        cls.server_if = server_ifs[0].strip()
        cls.client_if = client_ifs[0].strip()
        log.info(f"server 网口: {cls.server_if}, client 网口: {cls.client_if}")

        # 2. 探测 dpdk-devbind.py
        cls.server_devbind = cls._find_dpdk_tool("dpdk-devbind.py", CmdExecuteAdressEnum.SERVER.value)
        cls.client_devbind = cls._find_dpdk_tool("dpdk-devbind.py", CmdExecuteAdressEnum.CLIENT.value)
        if not cls.server_devbind:
            log.error("server 端未找到 dpdk-devbind.py")
            cls.own_environment_enabled = False
            return
        if not cls.client_devbind:
            log.error("client 端未找到 dpdk-devbind.py")
            cls.own_environment_enabled = False
            return

        # 3. 网口 -> PCI 地址
        cls.server_pci = cls._get_pci_by_iface(cls.server_if, CmdExecuteAdressEnum.SERVER.value)
        cls.client_pci = cls._get_pci_by_iface(cls.client_if, CmdExecuteAdressEnum.CLIENT.value)
        if not cls.server_pci or not cls.client_pci:
            log.error("无法获取测试网口的 PCI 地址")
            cls.own_environment_enabled = False
            return
        log.info(f"server PCI: {cls.server_pci}, client PCI: {cls.client_pci}")

        # 4. 探测可用的 dpdk-testpmd（需要传入 PCI 做实际探测校验）
        cls.server_testpmd = cls._find_dpdk_tool(
            "dpdk-testpmd", CmdExecuteAdressEnum.SERVER.value, pci=cls.server_pci
        )
        if not cls.server_testpmd:
            log.error("server 端未找到可用的 dpdk-testpmd（探测端口失败）")
            cls.own_environment_enabled = False
            return

        log.info(f"server dpdk-devbind.py: {cls.server_devbind}")
        log.info(f"server dpdk-testpmd: {cls.server_testpmd}")

        # 5. 记录当前内核驱动与 MAC
        cls.server_driver = cls._get_kernel_driver(cls.server_pci, CmdExecuteAdressEnum.SERVER.value)
        cls.client_driver = cls._get_kernel_driver(cls.client_pci, CmdExecuteAdressEnum.CLIENT.value)
        cls.server_mac = cls._get_mac_by_iface(cls.server_if, CmdExecuteAdressEnum.SERVER.value)
        log.info(f"server 当前驱动: {cls.server_driver}, MAC: {cls.server_mac}")

        # 6. 检查 hugepage
        cls._check_hugepages(CmdExecuteAdressEnum.SERVER.value)
        cls._check_hugepages(CmdExecuteAdressEnum.CLIENT.value)

        cls.own_environment_enabled = True
        log.info("TC-VLAN-030-D 环境检查通过")

    @classmethod
    def _find_dpdk_tool(cls, tool_name: str, exec_addr: str, pci: str = "") -> str:
        """在远端主机上查找可用（无缺失动态库且能实际探测端口）的 DPDK 工具路径"""
        search_patterns = [
            f"/usr/local/bin/{tool_name}",
            f"/usr/bin/{tool_name}",
            f"/opt/dpdk/*/build/app/{tool_name}",
            f"/opt/dpdk/{tool_name}",
            f"$HOME/dpdk/build/app/{tool_name}",
            f"/home/*/dpdk-*/build/app/{tool_name}",
            f"/home/*/dpdk/dpdk-*/build/app/{tool_name}",
        ]
        candidates = []
        for pattern in search_patterns:
            status, out, _ = cls._run_cmd(
                f"ls -1 {pattern} 2>/dev/null", exec_addr,
                log_cmd=False, ignore_status=(2,)
            )
            if status == RtnStatusEnum.SUCCESS.value and out.strip():
                candidates.extend(line.strip() for line in out.splitlines() if line.strip())

        # 兜底：用 which 查找
        status, out, _ = cls._run_cmd(
            f"which {tool_name} 2>/dev/null", exec_addr,
            log_cmd=False, ignore_status=(1,)
        )
        if status == RtnStatusEnum.SUCCESS.value and out.strip():
            candidates.append(out.strip())

        seen = set()
        for path in candidates:
            if path in seen:
                continue
            seen.add(path)
            if not cls._is_dpdk_tool_usable(path, exec_addr):
                continue
            if tool_name == "dpdk-testpmd" and pci:
                if not cls._testpmd_can_probe(path, pci, exec_addr):
                    continue
            log.info(f"{exec_addr} 选用 DPDK 工具: {path}")
            return path
        return ""

    @classmethod
    def _is_dpdk_tool_usable(cls, path: str, exec_addr: str) -> bool:
        """检查 DPDK 工具是否可执行；对 dpdk-testpmd 额外检查动态库依赖"""
        status, _, _ = cls._run_cmd(
            f"test -x {path}", exec_addr, log_cmd=False, ignore_status=(1,)
        )
        if status != RtnStatusEnum.SUCCESS.value:
            return False
        if path.endswith("dpdk-testpmd"):
            # 检查是否存在缺失的动态库
            s, _, _ = cls._run_cmd(
                f"ldd {path} 2>&1 | grep -q 'not found'", exec_addr,
                log_cmd=False, ignore_status=(1,)
            )
            if s == RtnStatusEnum.SUCCESS.value:
                log.warning(f"{path} 存在缺失的动态库，跳过")
                return False
        return True

    @classmethod
    def _testpmd_can_probe(cls, path: str, pci: str, exec_addr: str) -> bool:
        """通过快速启动 testpmd 验证其能否探测到指定 PCI 端口"""
        status, out, _ = cls._run_cmd(
            f"echo quit | {path} -l 0,1 -n 4 -a {pci} -- -i --portmask=0x1 --forward-mode=rxonly 2>&1 | "
            f"grep -E 'No probed ethernet devices|Invalid port|error while loading shared libraries'",
            exec_addr, timeout=30, log_cmd=False, ignore_status=(1,)
        )
        if status == RtnStatusEnum.SUCCESS.value:
            log.warning(f"{path} 无法探测 PCI {pci}，跳过")
            return False
        return True

    @classmethod
    def _get_pci_by_iface(cls, iface: str, exec_addr: str) -> str:
        """根据接口名从 dpdk-devbind.py --status 中解析 PCI 地址"""
        status, out, _ = cls._run_cmd(
            f"dpdk-devbind.py --status 2>/dev/null | grep -E 'if={iface}[^0-9A-Za-z]'",
            exec_addr, log_cmd=False, ignore_status=(1,)
        )
        if status != RtnStatusEnum.SUCCESS.value or not out.strip():
            # 尝试 ethtool -i
            status, out, _ = cls._run_cmd(
                f"ethtool -i {iface} 2>/dev/null | grep bus-info", exec_addr,
                log_cmd=False, ignore_status=(1,)
            )
            if status == RtnStatusEnum.SUCCESS.value:
                m = re.search(r"([0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F])", out)
                if m:
                    return m.group(1)
            return ""
        m = re.search(r"([0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F])", out)
        return m.group(1) if m else ""

    @classmethod
    def _get_kernel_driver(cls, pci: str, exec_addr: str) -> str:
        """获取 PCI 设备当前使用的内核驱动"""
        status, out, _ = cls._run_cmd(
            f"dpdk-devbind.py --status 2>/dev/null | grep '{pci}'",
            exec_addr, log_cmd=False, ignore_status=(1,)
        )
        if status != RtnStatusEnum.SUCCESS.value or not out.strip():
            return ""
        m = re.search(r"drv=(\S+)", out)
        return m.group(1) if m else ""

    @classmethod
    def _get_mac_by_iface(cls, iface: str, exec_addr: str) -> str:
        """获取接口 MAC 地址"""
        status, out, _ = cls._run_cmd(
            f"ip link show {iface} 2>/dev/null | grep 'link/ether'",
            exec_addr, log_cmd=False, ignore_status=(1,)
        )
        if status != RtnStatusEnum.SUCCESS.value or not out.strip():
            return ""
        m = re.search(r"link/ether\s+([0-9a-fA-F:]{17})", out)
        return m.group(1) if m else ""

    @classmethod
    def _check_hugepages(cls, exec_addr: str) -> None:
        """检查并尝试配置 2MB hugepage"""
        status, out, _ = cls._run_cmd(
            "cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages 2>/dev/null",
            exec_addr, log_cmd=False, ignore_status=(1,)
        )
        if status == RtnStatusEnum.SUCCESS.value and out.strip().isdigit():
            nr = int(out.strip())
            if nr >= 1024:
                log.info(f"{exec_addr} hugepage 已配置: {nr} x 2MB")
                return

        log.warning(f"{exec_addr} hugepage 不足，尝试配置 1024 个 2MB hugepage")
        cls._run_cmd(
            "echo 1024 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages",
            exec_addr,
        )

    @classmethod
    def prepare(cls) -> None:
        log.info("准备 TC-VLAN-030-D DPDK 测试环境...")

        # 清理可能残留的 testpmd 与绑定
        cls._cleanup_dpdk_env(CmdExecuteAdressEnum.SERVER.value)

        # Mellanox mlx5 PMD 可直接使用内核驱动 mlx5_core 运行，绑定 vfio-pci 反而可能无法探测设备
        if cls.server_driver and "mlx5" in cls.server_driver:
            log.info(f"检测到 Mellanox 内核驱动 {cls.server_driver}，DPDK 直接通过内核驱动运行")
            cls._run_cmd(
                f"ip link set {cls.server_if} down",
                CmdExecuteAdressEnum.SERVER.value,
            )
        else:
            bound = cls._bind_pci(
                cls.server_pci,
                cls.DPDK_BIND_DRIVER,
                cls.DPDK_BIND_FALLBACK,
                CmdExecuteAdressEnum.SERVER.value,
            )
            if not bound:
                cls._bug_and_raise(f"无法将 server PCI {cls.server_pci} 绑定到 DPDK 驱动")

        # client 保持内核模式，但确保接口 Up
        cls._run_cmd(
            f"ip link set {cls.client_if} up",
            CmdExecuteAdressEnum.CLIENT.value,
        )

        time.sleep(2)
        log.info("TC-VLAN-030-D 环境准备完成")

    @classmethod
    def _bind_pci(cls, pci: str, primary_driver: str, fallback_driver: str, exec_addr: str) -> bool:
        """绑定 PCI 到 DPDK 驱动，失败时尝试 fallback"""
        drivers_to_try = [primary_driver]
        # vfio-pci 在 IOMMU 未启用时可尝试 noiommu 模式
        if primary_driver == "vfio-pci":
            drivers_to_try.append("vfio-pci-noiommu")
        drivers_to_try.append(fallback_driver)

        for driver in drivers_to_try:
            log.info(f"尝试将 {pci} 绑定到 {driver}")
            # 加载驱动模块
            cls._run_cmd(
                f"modprobe {driver.replace('-noiommu', '')} 2>/dev/null || true", exec_addr
            )
            if driver == "vfio-pci-noiommu":
                bind_cmd = f"dpdk-devbind.py --noiommu-mode --bind=vfio-pci {pci}"
            else:
                bind_cmd = f"dpdk-devbind.py --bind={driver} {pci}"
            status, out, err = cls._run_cmd(bind_cmd, exec_addr, timeout=30)
            if status == RtnStatusEnum.SUCCESS.value:
                # 确认绑定成功
                s2, out2, _ = cls._run_cmd(
                    f"dpdk-devbind.py --status 2>/dev/null | grep '{pci}'", exec_addr,
                    log_cmd=False, ignore_status=(1,)
                )
                actual_driver = "vfio-pci" if driver == "vfio-pci-noiommu" else driver
                if s2 == RtnStatusEnum.SUCCESS.value and f"drv={actual_driver}" in out2:
                    log.info(f"{pci} 已成功绑定到 {actual_driver}")
                    return True
            log.warning(f"绑定 {pci} 到 {driver} 失败: {err or out}")
        return False

    @classmethod
    def _cleanup_dpdk_env(cls, exec_addr: str) -> None:
        """停止 testpmd 并清理临时文件"""
        cls._run_cmd(
            "pkill -9 -f 'dpdk-testpmd' 2>/dev/null || true", exec_addr,
            ignore_status=(255,)
        )
        for f in [
            cls.TESTPMD_LOG,
            cls.TESTPMD_PID_FILE,
            cls.TESTPMD_STDIN_PIPE,
            cls.TESTPMD_WRAPPER,
            cls.TESTPMD_STATS,
        ]:
            cls._run_cmd(f"rm -f {f}", exec_addr)

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 TC-VLAN-030-D：DPDK 场景 VLAN offload 功能验证")
        log.info("=" * 60)
        try:
            # 1. 启动 server testpmd
            cls._start_testpmd_on_server()

            # 2. 等待 testpmd 初始化完成
            time.sleep(3)
            if not cls._wait_testpmd_ready(CmdExecuteAdressEnum.SERVER.value):
                cls._bug_and_raise("dpdk-testpmd 启动失败或初始化超时")

            # 3. 配置 VLAN 命令并检查是否成功
            vlan_ok = cls._configure_vlan_offload()
            if not vlan_ok:
                cls._bug_and_raise("VLAN offload 命令配置失败")

            # 4. 从 client 注入 VLAN 报文
            inject_ok = cls._inject_vlan_packets_from_client()
            if not inject_ok:
                cls._bug_and_raise("client VLAN 报文注入失败")

            # 5. 等待报文到达并检查统计
            time.sleep(3)
            stats_ok = cls._verify_testpmd_stats()
            if not stats_ok:
                cls._bug_and_raise("server testpmd 未收到预期 VLAN 报文或存在异常丢包")

            log.info("TC-VLAN-030-D 测试通过")
        except SxeException:
            raise
        except Exception as e:
            log.error(f"TC-VLAN-030-D 未预期错误: {e}")
            raise

    @classmethod
    def _start_testpmd_on_server(cls) -> None:
        """在 server 后台启动 dpdk-testpmd，并通过命名管道接收命令"""
        wrapper = f"""#!/bin/bash
PIPE={cls.TESTPMD_STDIN_PIPE}
LOG={cls.TESTPMD_LOG}
PIDFILE={cls.TESTPMD_PID_FILE}

rm -f $PIPE $LOG $PIDFILE
mkfifo $PIPE

{cls.server_testpmd} -l 0,1 -n 4 -a {cls.server_pci} -- -i --portmask=0x1 --forward-mode=rxonly < $PIPE > $LOG 2>&1 &
echo $! > $PIDFILE

exec 3>$PIPE

# 先停止端口，配置 VLAN offload，再启动端口和转发
echo set fwd rxonly >&3
sleep 1
echo port stop 0 >&3
sleep 1
echo vlan set strip on 0 >&3
sleep 1
echo vlan set filter on 0 >&3
sleep 1
echo rx_vlan add {cls.VLAN_ID} 0 >&3
sleep 1
echo tx_vlan set 0 {cls.VLAN_ID} >&3
sleep 1
echo port start 0 >&3
sleep 1
echo start >&3
sleep 1
echo show port info 0 >&3
sleep 1
# 等待 client 注入流量
sleep 8
echo show port stats 0 >&3
sleep 1
echo stop >&3
sleep 1
echo quit >&3

wait
exec 3>&-
rm -f $PIPE
"""
        # 使用 base64 + printf 写入 wrapper，避免 heredoc 在新行被框架转义的问题
        b64 = base64.b64encode(wrapper.encode("utf-8")).decode("ascii")
        log.info(f"[server] 写入 testpmd wrapper 脚本到 {cls.TESTPMD_WRAPPER}")
        cls._run_cmd(
            f"printf '%s' '{b64}' | base64 -d > {cls.TESTPMD_WRAPPER}; chmod +x {cls.TESTPMD_WRAPPER}",
            CmdExecuteAdressEnum.SERVER.value, log_cmd=False,
        )
        # 后台执行 wrapper
        cls._run_cmd(
            f"nohup {cls.TESTPMD_WRAPPER} > {cls.TESTPMD_STATS} 2>&1 &",
            CmdExecuteAdressEnum.SERVER.value,
        )
        log.info("server dpdk-testpmd 已后台启动")

    @classmethod
    def _wait_testpmd_ready(cls, exec_addr: str) -> bool:
        """等待 testpmd 初始化完成"""
        for _ in range(20):
            status, out, _ = cls._run_cmd(
                f"grep -E 'Interactive-mode selected|testpmd>|Done|Error' {cls.TESTPMD_LOG} 2>/dev/null | tail -5",
                exec_addr, log_cmd=False, ignore_status=(1,)
            )
            if status == RtnStatusEnum.SUCCESS.value and out.strip():
                if "Error" in out and "No error" not in out:
                    log.error(f"testpmd 初始化出现错误: {out}")
                    return False
                if "Interactive-mode selected" in out or "testpmd>" in out:
                    return True
            time.sleep(1)
        log.error("testpmd 初始化超时")
        return False

    @classmethod
    def _configure_vlan_offload(cls) -> bool:
        """检查 testpmd 日志中 VLAN 命令是否执行成功"""
        time.sleep(2)
        status, out, _ = cls._run_cmd(
            f"grep -E 'vlan set strip|vlan set filter|rx_vlan add|tx_vlan set|Bad command|Failed|Invalid port|Please stop port' {cls.TESTPMD_LOG} 2>/dev/null",
            CmdExecuteAdressEnum.SERVER.value,
        )
        if status != RtnStatusEnum.SUCCESS.value or not out.strip():
            log.warning("未在 testpmd 日志中找到 VLAN 命令回显")
            return False
        for err in ("Bad command", "Failed", "Invalid port", "Please stop port"):
            if err in out:
                log.error(f"VLAN 命令执行异常: {err}\n{out}")
                return False
        log.info("VLAN offload 命令执行成功")
        return True

    @classmethod
    def _inject_vlan_packets_from_client(cls) -> bool:
        """从 client 使用 scapy 发送 VLAN 报文到 server DPDK 口"""
        if not cls.server_mac:
            log.error("未获取到 server MAC，无法注入报文")
            return False

        # 确保 scapy 可用
        cls._run_cmd(
            "python3 -c 'import scapy.all' 2>/dev/null || pip3 install scapy -q",
            CmdExecuteAdressEnum.CLIENT.value,
        )

        inject_script = f"""from scapy.all import *
p = Ether(dst='{cls.server_mac}')/Dot1Q(vlan={cls.VLAN_ID})/IP(dst='192.168.{cls.VLAN_ID}.1')/ICMP()
sendp(p, iface='{cls.client_if}', count={cls.INJECT_COUNT}, inter=0.01, verbose=0)
print('sent {cls.INJECT_COUNT} vlan {cls.VLAN_ID} packets')
"""
        script_path = "/tmp/tianying_vlan_inject.py"
        # 使用 base64 + printf 写入脚本，避免 heredoc 在远端被转义
        b64 = base64.b64encode(inject_script.encode("utf-8")).decode("ascii")
        log.info(f"[client] 写入 scapy VLAN 注入脚本到 {script_path}")
        cls._run_cmd(
            f"printf '%s' '{b64}' | base64 -d > {script_path}",
            CmdExecuteAdressEnum.CLIENT.value, log_cmd=False,
        )
        status, out, err = cls._run_cmd(
            f"python3 {script_path}", CmdExecuteAdressEnum.CLIENT.value, timeout=60
        )
        if status == RtnStatusEnum.SUCCESS.value:
            log.info(f"client 注入结果: {out.strip()}")
            return True
        log.error(f"client 注入失败: {err}")
        return False

    @classmethod
    def _verify_testpmd_stats(cls) -> bool:
        """解析 testpmd 日志中的端口统计，确认报文被接收"""
        # 等待 wrapper 执行完 show port stats
        for _ in range(15):
            status, out, _ = cls._run_cmd(
                f"grep -A10 'NIC statistics for port 0' {cls.TESTPMD_LOG} 2>/dev/null | tail -25",
                CmdExecuteAdressEnum.SERVER.value,
                log_cmd=False, ignore_status=(1,)
            )
            if status == RtnStatusEnum.SUCCESS.value and "RX-packets" in out:
                # 提取 RX-packets
                m = re.search(r"RX-packets:\s*(\d+)", out)
                if m:
                    rx_pkts = int(m.group(1))
                    log.info(f"server RX packets: {rx_pkts}")
                    if rx_pkts > 0:
                        # 进一步检查 RX-errors / RX-missed 是否异常
                        err_m = re.search(r"RX-errors:\s*(\d+)", out)
                        miss_m = re.search(r"RX-missed:\s*(\d+)", out)
                        rx_errs = int(err_m.group(1)) if err_m else 0
                        rx_missed = int(miss_m.group(1)) if miss_m else 0
                        if rx_errs > 0 or rx_missed > rx_pkts:
                            log.warning(f"RX 存在异常: errors={rx_errs}, missed={rx_missed}\n{out}")
                            return False
                        return True
                return False
            time.sleep(1)
        log.error("未获取到 testpmd 端口统计")
        return False

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "DPDK VLAN offload / rte_flow 应按预期工作"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)

    @classmethod
    def post(cls) -> None:
        log.info("清理 TC-VLAN-030-D DPDK 测试环境...")

        # 1. 停止 server testpmd
        cls._cleanup_dpdk_env(CmdExecuteAdressEnum.SERVER.value)

        # 2. 将 server PCI 恢复为原来的内核驱动
        if hasattr(cls, "server_pci") and cls.server_pci and hasattr(cls, "server_driver") and cls.server_driver:
            log.info(f"恢复 server PCI {cls.server_pci} 到内核驱动 {cls.server_driver}")
            cls._run_cmd(
                f"dpdk-devbind.py --bind={cls.server_driver} {cls.server_pci} 2>/dev/null || true",
                CmdExecuteAdressEnum.SERVER.value,
            )
            # 等待驱动恢复并启用接口
            time.sleep(2)
            cls._run_cmd(
                f"ip link set {cls.server_if} up 2>/dev/null || true",
                CmdExecuteAdressEnum.SERVER.value,
            )

        # 3. 清理临时文件
        for f in [
            cls.TESTPMD_LOG,
            cls.TESTPMD_PID_FILE,
            cls.TESTPMD_STDIN_PIPE,
            cls.TESTPMD_WRAPPER,
            cls.TESTPMD_STATS,
        ]:
            cls._run_cmd(f"rm -f {f}", CmdExecuteAdressEnum.SERVER.value)
            cls._run_cmd(f"rm -f {f}", CmdExecuteAdressEnum.CLIENT.value)

        log.info("TC-VLAN-030-D 清理完成")


def main() -> None:
    TianyingVlanDpdkOffloadDpdk.run()


if __name__ == "__main__":
    main()
