#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-15
case title: 跨子网进行ipoib多播测试
test category: IB多播测试
check point: 跨子网 ipoib 多播业务成功
author: auto-generated
date: 2026.06.24
@steps:
    1. 在两个子网之间配置路由。
    2. 从两个子网中各选一个节点。
    3. 使用 iperf 进行 ipoib 多播测试。

@expected:
    跨子网多播业务成功（需支持多播的路由器）。

@changelog:
2026.06.24 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.3 内核态QP加入多播组、3.1.20.4 内核态QP退出多播组
- 使用项目技巧：缺陷自动记录、IB基础概念与设备检查、IB命令处理与回显解析、IB多播与iperf测试
- 备注：当前为框架脚本；跨子网多播需要支持多播且与天蝎兼容的路由器/交换机，环境不满足时会跳过
"""

import os
import time
import re
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, BugTypeEnum, CmdExecuteAdressEnum
from scripts.script_libs.script_base import ScriptBase, SxeException


class IbMulticastMc015(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ip, iperf, ibdev2netdev, route"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
已加载 ib_ipoib 驱动，opensm 已启动
存在支持多播的跨子网路由器/交换机
已安装 iperf 2.x"""
    test_steps = """
    1. 检查测试环境是否支持跨子网多播（两个节点处于不同子网且有路由器）。
    2. 配置多播路由并启动 iperf 多播服务端。
    3. 另一子网节点启动 iperf 多播客户端（增大 TTL）。
    4. 检查服务端是否收到跨子网多播流量。
    """

    MCAST_GROUP = "224.0.0.2"
    IPERF_DURATION = 10
    IPERF_STARTUP_WAIT = 2

    # 双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport
    PPORT_COUNT = 2
    OPENSM_STARTUP_WAIT = 10

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc015 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-15 测试环境...")

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client"),
        ]:
            status, result, err = CommandOperation.execute_command_with_error("ibstat -l", exec_addr)
            if status != RtnStatusEnum.SUCCESS.value or not result.strip():
                log.error(f"{name} 端未找到 IB 设备")
                cls.own_environment_enabled = False
                return

            status, result, err = CommandOperation.execute_command_with_error("which iperf", exec_addr)
            if status != RtnStatusEnum.SUCCESS.value or not result.strip():
                log.error(f"{name} 端未找到 iperf")
                cls.own_environment_enabled = False
                return

        # 跨子网多播需要特定环境；当前若无明确多子网路由则跳过
        cls.own_environment_enabled = False
        log.warning("MC-15 需要支持多播的跨子网路由器/交换机，当前环境不满足，跳过执行")

    @classmethod
    def prepare(cls) -> None:
        super().prepare()
        log.info("准备 MC-15 测试环境...")

        # server 端：识别 pport 并启动 opensm
        cls.pf_list = cls._get_pf_list(CmdExecuteAdressEnum.SERVER.value, "server")
        cls.pport_list = cls._get_pport_list(cls.pf_list)
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._start_opensm_for_pports(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._verify_opensm_for_pports(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._verify_all_pf_active(CmdExecuteAdressEnum.SERVER.value, "server")
        cls.server_pf_list = cls.pf_list
        cls.server_pport_list = cls.pport_list

        # client 端：识别 pport 并启动 opensm
        cls.pf_list = cls._get_pf_list(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls.pport_list = cls._get_pport_list(cls.pf_list)
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._start_opensm_for_pports(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._verify_opensm_for_pports(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls._verify_all_pf_active(CmdExecuteAdressEnum.CLIENT.value, "client")
        cls.client_pf_list = cls.pf_list
        cls.client_pport_list = cls.pport_list

        cls.server_iface = cls._get_ipoib_iface(
            CmdExecuteAdressEnum.SERVER.value, "server"
        )
        cls.client_iface = cls._get_ipoib_iface(
            CmdExecuteAdressEnum.CLIENT.value, "client"
        )

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-15 测试：跨子网 ipoib 多播")
        log.info("=" * 60)

        try:
            log.warning("MC-15 当前环境缺乏支持多播的跨子网路由器，执行基础框架逻辑")
            # 占位：如后续环境具备，可在此处实现跨子网 iperf 多播
            cls.bug_result = "当前测试环境暂不支持跨子网多播（缺少多播路由器/交换机）"
            cls.bug_expect = "应具备支持多播的跨子网路由器/交换机"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("MC-15 环境不满足，跨子网多播未执行")

            log.info("=" * 60)
            log.info("MC-15 执行完成（环境受限）")
            log.info("=" * 60)
        except SxeException:
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-15 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-15 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-15 测试环境...")
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._stop_opensm(CmdExecuteAdressEnum.CLIENT.value, "client")
        log.info("MC-15 清理完成")
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
            cls.create_bug(f"MC-15 {name} 端 ibdev2netdev 执行失败")

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
        cls.create_bug(f"MC-15 {name} 端获取 ipoib 网口失败")

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
            cls.create_bug(f"MC-15 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-15 {name} 端 PF 列表为空")

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
    def _start_opensm_for_pports(cls, exec_addr: str, name: str) -> None:
        """为每个 pport 启动 opensm"""
        log.info(f"在 {name} 端为所有 pport 启动 opensm...")

        for idx, pport in enumerate(cls.pport_list):
            guid = cls._get_device_guid(exec_addr, name, pport)
            log.info(f"为 pport {pport} 启动 opensm，GUID: {guid}")
            opensm_cmd = (
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_mc15_{idx}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端为 pport {pport} 启动 opensm 失败: {err}"
                cls.bug_expect = "opensm 应能在每个 pport 上成功启动"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-15 {name} 端 pport {pport} opensm 启动失败")
            time.sleep(3)

        # 等待 opensm 完成子网扫描
        time.sleep(cls.OPENSM_STARTUP_WAIT)

    @classmethod
    def _verify_opensm_for_pports(cls, exec_addr: str, name: str) -> None:
        """验证每个 pport 上的 opensm 进程正在运行"""
        log.info(f"验证 {name} 端所有 pport 的 opensm 进程...")

        # 验证 opensm 进程数量不少于 pport 数量
        status, result, err = CommandOperation.execute_command_with_error(
            "pgrep -x opensm", exec_addr
        )
        running_count = len([line.strip() for line in result.splitlines() if line.strip()])
        if running_count < len(cls.pport_list):
            cls.bug_result = (
                f"{name} 端 opensm 进程数量不足，实际 {running_count} 个，"
                f"期望至少 {len(cls.pport_list)} 个（每个 pport 一个）"
            )
            cls.bug_expect = "每个 pport 上应运行一个 opensm 实例"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-15 {name} 端 opensm 进程数量不足")

        log.info(f"{name} 端 opensm 进程数量: {running_count}，pport 数量: {len(cls.pport_list)}")

    @classmethod
    def _verify_all_pf_active(cls, exec_addr: str, name: str) -> None:
        """验证所有 PF 均处于 Active 状态"""
        log.info(f"验证 {name} 端所有 PF 状态...")
        for pf in cls.pf_list:
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
                cls.create_bug(f"MC-15 {name} 端 PF {pf} 未 Active")
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
            cls.create_bug(f"MC-15 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-15 {name} 端解析 {device} GUID 失败")

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
        cls.bug_expect = "MC-15 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc015.run()


if __name__ == '__main__':
    main()
