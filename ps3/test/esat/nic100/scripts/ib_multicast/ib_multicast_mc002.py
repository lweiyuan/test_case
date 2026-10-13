#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-2
case title: 观察加载opensm（opensm -g <GUID> -B）前/后网口状态是否为down/up（ip a 查看IB网卡对应ipoib网口，如mlx5_0对应 ibs3f1）
test category: IB多播测试
check point: OpenSM启动能够正确激活ipoib网口
author: auto-generated
date: 2026.06.24
@steps:
    1. 在 opensm 未启动时，通过 ip a 查看 mlx5_0 对应 ipoib 网口状态，记录为 down。
    2. 通过 ibstat mlx5_0 | grep "Node GUID" 获取 GUID。
    3. 执行 opensm -g <GUID> -B 启动 OpenSM。
    4. 等待 OpenSM 初始化完成后，再次通过 ip a 查看该网口状态，应变为 up。

@expected:
    1. 启动 opensm 前，ipoib 网口状态为 DOWN。
    2. 启动 opensm 后，ipoib 网口状态变为 UP。

@changelog:
2026.06.24 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.3 内核态QP加入多播组、3.1.20.4 内核态QP退出多播组
- 使用项目技巧：缺陷自动记录、IB基础概念与设备检查、IB命令处理与回显解析、IB多播与iperf测试
2026.06.24 - 修正：opensm 启动前先复位 IB 网卡（重新加载 mlx5 驱动），确保观察到网卡初始 DOWN 状态
2026.06.25 - 修正：opensm 启动时指定目标设备 GUID（opensm -g <GUID> -B）
"""

import os
import time
import re
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, BugTypeEnum, CmdExecuteAdressEnum
from scripts.script_libs.script_base import ScriptBase, SxeException


class IbMulticastMc002(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ip, ibdev2netdev, opensm, ibstat, lsmod, modprobe, rmmod"
    test_precondition = """天蝎网卡驱动已安装
已加载 ib_ipoib 驱动
已安装 opensm"""
    test_steps = """
    1. 停止已运行的 opensm。
    2. 复位 IB 网卡（重新加载 mlx5 驱动），使其回到未受 SM 管理状态。
    3. 重新加载 ib_ipoib 驱动，通过 ip a 查看 mlx5_0 对应 ipoib 网口状态（应为 DOWN）。
    4. 通过 ibstat mlx5_0 | grep "Node GUID" 获取 GUID。
    5. 执行 opensm -g <GUID> -B 启动 OpenSM。
    6. 等待 OpenSM 初始化完成后，再次通过 ip a 查看该网口状态（应为 UP）。
    """

    TARGET_IB_DEVICE = "mlx5_0"
    OPENSM_STARTUP_WAIT = 15
    OPENSM_POLL_INTERVAL = 2
    OPENSM_POLL_TIMEOUT = 60

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc002 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-2 测试环境...")

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client"),
        ]:
            status, result, err = CommandOperation.execute_command_with_error("ibstat -l", exec_addr)
            if status != RtnStatusEnum.SUCCESS.value or not result.strip():
                log.error(f"{name} 端未找到 IB 设备")
                cls.own_environment_enabled = False
                return

            status, result, err = CommandOperation.execute_command_with_error(
                f"lsmod | grep -w ib_ipoib", exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value or "ib_ipoib" not in result:
                log.error(f"{name} 端未加载 ib_ipoib 驱动")
                cls.own_environment_enabled = False
                return

        cls.own_environment_enabled = True
        log.info("环境检查通过：两端均存在 IB 设备且已加载 ib_ipoib 驱动")

    @classmethod
    def prepare(cls) -> None:
        log.info("准备 MC-2 测试环境...")

        # 1. 停止 opensm，确保当前没有 SM 管理子网
        cls._stop_opensm_if_running(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm_if_running(CmdExecuteAdressEnum.CLIENT.value, "client")

        # 2. 复位 IB 网卡：重新加载 mlx5 驱动，使其回到刚上电/未受 SM 管理状态
        cls._reset_ib_nic(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._reset_ib_nic(CmdExecuteAdressEnum.CLIENT.value, "client")

        # 3. 重新加载 ipoib 驱动（复位过程中会被卸载）
        cls._load_ipoib_driver(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._load_ipoib_driver(CmdExecuteAdressEnum.CLIENT.value, "client")

        # 4. 等待驱动/设备稳定
        time.sleep(3)

        # 5. 获取 ipoib 网口名
        cls.server_iface = cls._get_ipoib_iface(
            CmdExecuteAdressEnum.SERVER.value, "server"
        )
        cls.client_iface = cls._get_ipoib_iface(
            CmdExecuteAdressEnum.CLIENT.value, "client"
        )

        # 6. 记录 opensm 启动前的网口状态（应为 DOWN）
        cls.server_state_before = cls._get_iface_state(
            CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface
        )
        cls.client_state_before = cls._get_iface_state(
            CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface
        )
        log.info(
            f"opensm 启动前网口状态 - 服务端({cls.server_iface}): {cls.server_state_before}, "
            f"客户端({cls.client_iface}): {cls.client_state_before}"
        )

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-2 测试：OpenSM 启动前后 ipoib 网口状态检查")
        log.info("=" * 60)

        try:
            # 步骤1：确认 opensm 启动前网口状态为 DOWN
            cls._verify_iface_state(
                CmdExecuteAdressEnum.SERVER.value,
                "server",
                cls.server_iface,
                cls.server_state_before,
                expected_state="DOWN",
                phase="opensm 启动前",
            )
            cls._verify_iface_state(
                CmdExecuteAdressEnum.CLIENT.value,
                "client",
                cls.client_iface,
                cls.client_state_before,
                expected_state="DOWN",
                phase="opensm 启动前",
            )

            # 步骤2：在服务端启动 opensm
            cls._start_opensm(CmdExecuteAdressEnum.SERVER.value, "server")

            # 步骤3：等待 opensm 初始化完成并检查网口状态变为 UP
            cls._wait_for_opensm_ready(CmdExecuteAdressEnum.SERVER.value, "server")

            cls.server_state_after = cls._get_iface_state(
                CmdExecuteAdressEnum.SERVER.value, "server", cls.server_iface
            )
            cls.client_state_after = cls._get_iface_state(
                CmdExecuteAdressEnum.CLIENT.value, "client", cls.client_iface
            )
            log.info(
                f"opensm 启动后网口状态 - 服务端({cls.server_iface}): {cls.server_state_after}, "
                f"客户端({cls.client_iface}): {cls.client_state_after}"
            )

            cls._verify_iface_state(
                CmdExecuteAdressEnum.SERVER.value,
                "server",
                cls.server_iface,
                cls.server_state_after,
                expected_state="UP",
                phase="opensm 启动后",
            )
            cls._verify_iface_state(
                CmdExecuteAdressEnum.CLIENT.value,
                "client",
                cls.client_iface,
                cls.client_state_after,
                expected_state="UP",
                phase="opensm 启动后",
            )

            log.info("=" * 60)
            log.info("测试执行成功 - MC-2 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-2 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-2 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-2 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-2 测试环境...")
        # MC-3/MC-4 等后续用例依赖 opensm 保持运行，因此本用例不停止 opensm
        cls._log_opensm_status()
        log.info("MC-2 清理完成：保持 opensm 运行状态供后续用例使用")

    @classmethod
    def _get_ipoib_iface(cls, exec_addr: str, name: str) -> str:
        """通过 ibdev2netdev 获取目标 IB 设备对应的 ipoib 网口名"""
        log.info(f"获取 {name} 端 {cls.TARGET_IB_DEVICE} 对应的 ipoib 网口...")

        cmd = "ibdev2netdev"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端执行 ibdev2netdev 失败: {err}"
            cls.bug_expect = "ibdev2netdev 应成功执行并返回 IB 设备与网口映射"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-2 {name} 端 ibdev2netdev 执行失败")

        # 解析形如 "mlx5_0 port 1 ==> ib0 (Up)" 的行
        pattern = re.compile(
            rf"^{re.escape(cls.TARGET_IB_DEVICE)}\s+port\s+\d+\s+==>\s+(\S+)\s+\((\w+)\)"
        )
        for line in result.splitlines():
            match = pattern.match(line.strip())
            if match:
                iface = match.group(1)
                if iface.startswith("ib"):
                    log.info(f"{name} 端 {cls.TARGET_IB_DEVICE} 对应 ipoib 网口: {iface}")
                    return iface
                else:
                    cls.bug_result = (
                        f"{name} 端 {cls.TARGET_IB_DEVICE} 对应的网口 {iface} 不是 ipoib 网口，"
                        f"当前 Link layer 可能为 Ethernet。ibdev2netdev 输出:\n{result}"
                    )
                    cls.bug_expect = f"{cls.TARGET_IB_DEVICE} 应对应 ib* 开头的 ipoib 网口"
                    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                    cls.create_bug(f"MC-2 {name} 端未找到 ipoib 网口")

        cls.bug_result = (
            f"{name} 端未找到 {cls.TARGET_IB_DEVICE} 对应的 ipoib 网口。"
            f"ibdev2netdev 输出:\n{result}"
        )
        cls.bug_expect = f"ibdev2netdev 输出中应包含 {cls.TARGET_IB_DEVICE} 到 ipoib 网口的映射"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(f"MC-2 {name} 端获取 ipoib 网口失败")

    @classmethod
    def _get_iface_state(cls, exec_addr: str, name: str, iface: str) -> str:
        """获取指定网口的状态（UP/DOWN/UNKNOWN）"""
        cmd = f"ip a show {iface}"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端获取网口 {iface} 状态失败: {err}"
            cls.bug_expect = f"ip a show {iface} 应成功执行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-2 {name} 端获取网口状态失败")

        match = re.search(r"state\s+(\w+)", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ip a 输出中解析网口 {iface} 状态。输出:\n{result}"
            cls.bug_expect = f"ip a show {iface} 输出中应包含 state UP/DOWN"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-2 {name} 端解析网口状态失败")

        return match.group(1).upper()

    @classmethod
    def _verify_iface_state(
        cls,
        exec_addr: str,
        name: str,
        iface: str,
        actual_state: str,
        expected_state: str,
        phase: str,
    ) -> None:
        """验证网口状态是否符合预期"""
        log.info(f"验证 {name} 端 {iface} 在 {phase} 的状态为 {expected_state}...")
        if actual_state != expected_state:
            cls.bug_result = (
                f"{name} 端网口 {iface} 在 {phase} 状态异常，"
                f"期望: {expected_state}，实际: {actual_state}"
            )
            cls.bug_expect = f"{phase} {name} 端 {iface} 应处于 {expected_state} 状态"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-2 {name} 端 {iface} 在 {phase} 状态不符合预期")
        log.info(f"{name} 端 {iface} 在 {phase} 状态符合预期: {actual_state}")

    @classmethod
    def _is_opensm_running(cls, exec_addr: str) -> bool:
        """检查 opensm 是否正在运行"""
        cmd = "pgrep -x opensm >/dev/null 2>&1"
        status, _, _ = CommandOperation.execute_command_with_error(cmd, exec_addr)
        return status == RtnStatusEnum.SUCCESS.value

    @classmethod
    def _stop_opensm_if_running(cls, exec_addr: str, name: str) -> None:
        """如果 opensm 正在运行则停止，确保能观察到 DOWN 状态"""
        if not cls._is_opensm_running(exec_addr):
            log.info(f"{name} 端 opensm 未运行，无需停止")
            return

        log.warning(f"{name} 端 opensm 已运行，准备停止以观察 DOWN 状态")
        cmd = "pkill -9 -x opensm 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        # 等待 opensm 完全退出，网口恢复 DOWN 状态
        time.sleep(5)
        log.info(f"{name} 端 opensm 已停止")

    @classmethod
    def _reset_ib_nic(cls, exec_addr: str, name: str) -> None:
        """复位 IB 网卡：卸载并重新加载 mlx5 相关驱动，使其回到初始状态"""
        log.info(f"在 {name} 端复位 IB 网卡（重新加载 mlx5 驱动）...")

        # 停止可能依赖 mlx5 的用户态进程
        CommandOperation.execute_command_with_error(
            'pkill -9 -f "ib_send_bw" 2>/dev/null || true', exec_addr
        )

        unload_cmds = [
            "rmmod ib_ipoib 2>/dev/null || true",
            "rmmod mlx5_ib 2>/dev/null || true",
            "rmmod mlx5_core 2>/dev/null || true",
        ]
        for cmd in unload_cmds:
            CommandOperation.execute_command_with_error(cmd, exec_addr)
            time.sleep(1)

        load_cmds = [
            "modprobe mlx5_core",
            "modprobe mlx5_ib",
        ]
        for cmd in load_cmds:
            status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端加载 mlx5 驱动失败: {cmd}\n错误: {err}"
                cls.bug_expect = "modprobe mlx5_core / mlx5_ib 应成功执行"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-2 {name} 端复位 IB 网卡失败")
            time.sleep(1)

        # 等待设备重新出现
        time.sleep(3)

        # 确认 IB 设备可见
        status, result, err = CommandOperation.execute_command_with_error("ibstat -l", exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or not result.strip():
            cls.bug_result = f"{name} 端复位后未找到 IB 设备"
            cls.bug_expect = "复位后 ibstat -l 应能列出 IB 设备"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-2 {name} 端复位后无 IB 设备")

        log.info(f"{name} 端 IB 网卡复位完成，设备: {result.strip()}")

    @classmethod
    def _load_ipoib_driver(cls, exec_addr: str, name: str) -> None:
        """加载 ib_ipoib 驱动"""
        log.info(f"在 {name} 端加载 ib_ipoib 驱动...")
        cmd = "modprobe ib_ipoib"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端加载 ib_ipoib 驱动失败: {err}"
            cls.bug_expect = "modprobe ib_ipoib 应成功执行"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-2 {name} 端加载 ib_ipoib 失败")
        time.sleep(2)
        log.info(f"{name} 端 ib_ipoib 驱动加载完成")

    @classmethod
    def _start_opensm(cls, exec_addr: str, name: str) -> None:
        """在指定端启动 opensm（指定目标设备 GUID）"""
        log.info(f"在 {name} 端启动 opensm...")

        guid = cls._get_device_guid(exec_addr, name, cls.TARGET_IB_DEVICE)
        cmd = f"nohup opensm -g {guid} -B > /var/log/opensm_mc2.log 2>&1 &"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端启动 opensm 失败: {err}"
            cls.bug_expect = "opensm -g <GUID> -B 应成功启动"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-2 {name} 端启动 opensm 失败")

        log.info(f"{name} 端 opensm 启动命令已执行（GUID: {guid}），等待初始化...")

    @classmethod
    def _wait_for_opensm_ready(cls, exec_addr: str, name: str) -> None:
        """轮询等待 opensm 完成初始化"""
        log.info(f"等待 {name} 端 opensm 初始化完成...")
        time.sleep(cls.OPENSM_STARTUP_WAIT)

        start_time = time.time()
        while time.time() - start_time < cls.OPENSM_POLL_TIMEOUT:
            if cls._is_opensm_running(exec_addr):
                log.info(f"{name} 端 opensm 已处于运行状态")
                return
            time.sleep(cls.OPENSM_POLL_INTERVAL)

        cls.bug_result = f"{name} 端 opensm 启动后未检测到运行进程"
        cls.bug_expect = "opensm -B 启动后应持续运行"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(f"MC-2 {name} 端 opensm 未正常运行")

    @classmethod
    def _log_opensm_status(cls) -> None:
        """记录 opensm 运行状态（清理阶段使用，不判定失败）"""
        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client"),
        ]:
            if cls._is_opensm_running(exec_addr):
                log.info(f"{name} 端 opensm 仍在运行")
            else:
                log.warning(f"{name} 端 opensm 未运行")

    @classmethod
    def _get_device_guid(cls, exec_addr: str, name: str, device: str) -> str:
        """获取指定 IB 设备的 Node GUID"""
        cmd = f"ibstat {device} | grep 'Node GUID'"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端获取 {device} Node GUID 失败: {err}"
            cls.bug_expect = "ibstat 应能返回 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-2 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-2 {name} 端解析 {device} GUID 失败")

        return match.group(0)

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-2 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc002.run()


if __name__ == '__main__':
    main()
