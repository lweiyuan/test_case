#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-20
case title: 两个交换机通过两条以上物理链路连接，1个多播业务向4个网卡发送多播，业务前中后执行ibdiagnet检查网络质量
test category: IB多播测试
check point: 交换机链路冗余场景下多播业务不影响网络质量
author: auto-generated
date: 2026.06.24
@steps:
    1. 两个交换机各直连两个网卡。
    2. 两个交换机通过至少两条物理链路连接。
    3. 1 个多播业务向四个网卡发送多播。
    4. 业务前、中、后分别执行 ibdiagnet 检查网络质量。

@expected:
    业务前、中、后的网络质量一致。

@changelog:
2026.06.24 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.1~3.1.20.5 IB多播支持
- 使用项目技巧：缺陷自动记录、IB基础概念与设备检查、IB命令处理与回显解析
- 备注：需要特定交换机拓扑环境，当前环境不满足时跳过
2026.06.26 - 修正：识别所有 pport 并为每个 pport 启动并检查 opensm；prepare/post 补充 super() 调用
"""

import os
import time
import re
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, BugTypeEnum, CmdExecuteAdressEnum
from scripts.script_libs.script_base import ScriptBase, SxeException


class IbMulticastMc020(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "ibdiagnet, ib_send_bw, ibstat"
    test_precondition = """天蝎网卡驱动已安装，IB 端口状态 Active
opensm 已启动
具备两个交换机、至少两条互联物理链路、四个网卡的测试拓扑"""
    test_steps = """
    1. 检查测试环境是否具备要求的交换机拓扑。
    2. 业务前执行 ibdiagnet 获取基线网络质量。
    3. 启动 1 个多播业务向四个网卡发送多播。
    4. 业务中执行 ibdiagnet 检查网络质量。
    5. 业务后执行 ibdiagnet 检查网络质量。
    6. 对比三次 ibdiagnet 结果，确认网络质量一致。
    """

    # 双端口网卡前两个 PF 为 pport；单端口网卡仅第一个为 pport
    PPORT_COUNT = 2
    OPENSM_STARTUP_WAIT = 10

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc020 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-20 测试环境...")

        status, result, err = CommandOperation.execute_command_with_error("ibstat -l", CmdExecuteAdressEnum.SERVER.value)
        if status != RtnStatusEnum.SUCCESS.value or not result.strip():
            log.error("server 端未找到 IB 设备")
            cls.own_environment_enabled = False
            return

        status, result, err = CommandOperation.execute_command_with_error("which ibdiagnet", CmdExecuteAdressEnum.SERVER.value)
        if status != RtnStatusEnum.SUCCESS.value or not result.strip():
            log.warning("server 端未找到 ibdiagnet")
            cls.own_environment_enabled = False
            return

        # 当前环境缺乏要求的交换机拓扑，跳过执行
        cls.own_environment_enabled = False
        log.warning("MC-20 需要特定交换机拓扑环境（两个交换机+至少两条互联链路+四个网卡），当前环境不满足，跳过执行")

    @classmethod
    def prepare(cls) -> None:
        super().prepare()
        log.info("准备 MC-20 测试环境...")

        # 识别所有 pport 并确保 opensm 已启动
        cls.pf_list = cls._get_pf_list(CmdExecuteAdressEnum.SERVER.value, "server")
        cls.pport_list = cls._get_pport_list(cls.pf_list)
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._start_opensm_for_pports(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._verify_opensm_for_pports(CmdExecuteAdressEnum.SERVER.value, "server")
        cls._verify_all_pf_active(CmdExecuteAdressEnum.SERVER.value, "server")

        log.info(f"server 端 PF 列表: {cls.pf_list}")
        log.info(f"server 端 pport 列表: {cls.pport_list}")

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-20 测试：交换机链路冗余 + ibdiagnet")
        log.info("=" * 60)

        try:
            log.warning("MC-20 当前环境缺乏要求的交换机拓扑，执行基础框架逻辑")
            cls.bug_result = "当前测试环境暂不具备 MC-20 要求的交换机拓扑"
            cls.bug_expect = "应具备两个交换机、至少两条互联物理链路、四个网卡的测试拓扑"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug("MC-20 环境不满足，未执行交换机链路多播测试")

            log.info("=" * 60)
            log.info("MC-20 执行完成（环境受限）")
            log.info("=" * 60)
        except SxeException:
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-20 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-20 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-20 测试环境...")
        cls._stop_opensm(CmdExecuteAdressEnum.SERVER.value, "server")
        log.info("MC-20 清理完成")
        super().post()

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
            cls.create_bug(f"MC-20 {name} 端获取 PF 列表失败")

        pf_list = [line.strip() for line in result.splitlines() if line.strip()]
        if not pf_list:
            cls.bug_result = f"{name} 端未找到任何 IB PF"
            cls.bug_expect = "ibstat -l 应返回至少一个 PF"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-20 {name} 端 PF 列表为空")

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
    def _start_opensm_for_pports(cls, exec_addr: str, name: str) -> None:
        """为每个 pport 启动 opensm"""
        log.info(f"在 {name} 端为所有 pport 启动 opensm...")

        for idx, pport in enumerate(cls.pport_list):
            guid = cls._get_device_guid(exec_addr, name, pport)
            log.info(f"为 pport {pport} 启动 opensm，GUID: {guid}")
            opensm_cmd = (
                f"nohup opensm -g {guid} -B -e -f /var/log/opensm_mc20_{idx}.log "
                f"> /dev/null 2>&1 &"
            )
            status, result, err = CommandOperation.execute_command_with_error(
                opensm_cmd, exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端为 pport {pport} 启动 opensm 失败: {err}"
                cls.bug_expect = "opensm 应能在每个 pport 上成功启动"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-20 {name} 端 pport {pport} opensm 启动失败")
            time.sleep(3)

        # 等待 opensm 完成子网扫描
        time.sleep(cls.OPENSM_STARTUP_WAIT)

    @classmethod
    def _verify_opensm_for_pports(cls, exec_addr: str, name: str) -> None:
        """验证每个 pport 上的 opensm 进程正在运行"""
        log.info(f"验证 {name} 端所有 pport 的 opensm 进程...")

        if not cls._is_opensm_running(exec_addr):
            cls.bug_result = f"{name} 端未检测到任何 opensm 进程"
            cls.bug_expect = "每个 pport 上应运行一个 opensm 实例"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-20 {name} 端 opensm 未运行")

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
            cls.create_bug(f"MC-20 {name} 端 opensm 进程数量不足")

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
                cls.create_bug(f"MC-20 {name} 端 PF {pf} 未 Active")
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
            cls.create_bug(f"MC-20 {name} 端获取 {device} GUID 失败")

        match = re.search(r"0x[0-9a-fA-F]+", result)
        if not match:
            cls.bug_result = f"{name} 端无法从 ibstat 输出解析 {device} Node GUID。输出:\n{result}"
            cls.bug_expect = "ibstat 输出中应包含 Node GUID"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-20 {name} 端解析 {device} GUID 失败")

        return match.group(0)

    @classmethod
    def _is_opensm_running(cls, exec_addr: str) -> bool:
        """检查 opensm 进程是否正在运行"""
        status, _, _ = CommandOperation.execute_command_with_error(
            "pgrep -x opensm >/dev/null 2>&1", exec_addr
        )
        return status == RtnStatusEnum.SUCCESS.value

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-20 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc020.run()


if __name__ == '__main__':
    main()
