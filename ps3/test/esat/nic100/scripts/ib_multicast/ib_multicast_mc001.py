#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: MC-1
case title: 加载ipoib（modprobe ib_ipoib 或者 insmod  ib_ipoib.ko）驱动成功（lsmod|grep ipoib 可以看到该驱动）
test category: IB多播测试
check point: 内核态QP加入多播组之前置条件——ipoib驱动可正常加载
author: auto-generated
date: 2026.06.24
@steps:
    1. 检查测试节点上 IB 设备状态为 Active。
    2. 执行 modprobe ib_ipoib 加载 ipoib 驱动（如 modprobe 不可用则尝试 insmod ib_ipoib.ko）。
    3. 执行 lsmod | grep ipoib 查看驱动是否加载成功。

@expected:
    1. IB 设备状态为 Active。
    2. ipoib 驱动加载命令返回成功。
    3. lsmod 输出中包含 ib_ipoib。

@changelog:
2026.06.24 - 根据 IB-MultiCast_ForAI-测试用例.xlsx 生成
- 关联需求：3.1.20.3 内核态QP加入多播组、3.1.20.4 内核态QP退出多播组
- 使用项目技巧：缺陷自动记录、perftest工具使用、IB多播与iperf测试、IB基础概念与设备检查、IB命令处理与回显解析
2026.06.24 - 根据框架与通用能力/IB模块测试技巧审查修正
- 补充 bug_test_module、bug_case 字段
- 明确 time.sleep 等待驱动加载的异步原因
"""

import os
import time
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, BugTypeEnum, CmdExecuteAdressEnum
from scripts.script_libs.script_base import ScriptBase, SxeException


class IbMulticastMc001(ScriptBase):
    test_object = "IB Multicast Test"
    test_module = "IB Multicast Test"
    test_tool = "modprobe, insmod, lsmod, ibstat"
    test_precondition = "天蝎网卡驱动已安装，IB 端口状态 Active"
    test_steps = """
    1. 检查测试节点上 IB 设备状态为 Active。
    2. 执行 modprobe ib_ipoib 加载 ipoib 驱动（如 modprobe 不可用则尝试 insmod ib_ipoib.ko）。
    3. 执行 lsmod | grep ipoib 查看驱动是否加载成功。
    """

    IPoIB_MODULE_NAME = "ib_ipoib"

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IbMulticastMc001 Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 MC-1 测试环境...")

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client"),
        ]:
            status, result, err = CommandOperation.execute_command_with_error("ibstat -l", exec_addr)
            if status != RtnStatusEnum.SUCCESS.value or not result.strip():
                log.error(f"{name} 端未找到 IB 设备")
                cls.own_environment_enabled = False
                return

        cls.own_environment_enabled = True
        log.info("环境检查通过：两端均存在 IB 设备")

    @classmethod
    def prepare(cls) -> None:
        log.info("准备 MC-1 测试环境...")
        cls.initial_loaded_server = cls._is_ipoib_loaded(CmdExecuteAdressEnum.SERVER.value)
        cls.initial_loaded_client = cls._is_ipoib_loaded(CmdExecuteAdressEnum.CLIENT.value)
        log.info(
            f"初始 ipoib 加载状态 - 服务端: {cls.initial_loaded_server}, "
            f"客户端: {cls.initial_loaded_client}"
        )

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 MC-1 测试：加载 ipoib 驱动并验证")
        log.info("=" * 60)

        try:
            # 步骤1：检查 IB 设备状态
            cls._check_ib_device_active(CmdExecuteAdressEnum.SERVER.value, "server")
            cls._check_ib_device_active(CmdExecuteAdressEnum.CLIENT.value, "client")

            # 步骤2：加载 ipoib 驱动
            cls._load_ipoib_driver(CmdExecuteAdressEnum.SERVER.value, "server")
            cls._load_ipoib_driver(CmdExecuteAdressEnum.CLIENT.value, "client")

            # 步骤3：验证驱动已加载
            cls._verify_ipoib_loaded(CmdExecuteAdressEnum.SERVER.value, "server")
            cls._verify_ipoib_loaded(CmdExecuteAdressEnum.CLIENT.value, "client")

            log.info("=" * 60)
            log.info("测试执行成功 - MC-1 通过")
            log.info("=" * 60)
        except SxeException:
            log.error("测试执行失败 - MC-1 失败（框架已记录 Bug）")
            raise
        except Exception as e:
            log.error(f"测试执行失败 - MC-1 失败（未预期错误）: {e}")
            cls._bug_and_raise(f"MC-1 执行过程中出现未预期错误: {e}")

    @classmethod
    def post(cls) -> None:
        log.info("清理 MC-1 测试环境...")
        # MC-1 是加载驱动用例，后续 MC-2~MC-4 依赖 ipoib 驱动保持加载状态。
        # 因此本用例不在 post 阶段卸载驱动，避免破坏后续用例前置条件。
        # 如测试前驱动未加载且需严格恢复环境，可在此补充 rmmod ib_ipoib。
        log.info("MC-1 清理完成：保持 ipoib 驱动当前状态")

    @classmethod
    def _is_ipoib_loaded(cls, exec_addr: str) -> bool:
        """检查 ipoib 驱动是否已加载"""
        cmd = f"lsmod | grep -w {cls.IPoIB_MODULE_NAME}"
        status, result, _ = CommandOperation.execute_command_with_error(cmd, exec_addr)
        return status == RtnStatusEnum.SUCCESS.value and cls.IPoIB_MODULE_NAME in result

    @classmethod
    def _check_ib_device_active(cls, exec_addr: str, name: str) -> None:
        """检查至少有一个 IB 设备处于 Active/LinkUp 状态"""
        log.info(f"检查 {name} 端 IB 设备状态...")

        status, result, err = CommandOperation.execute_command_with_error("ibstat", exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"{name} 端执行 ibstat 失败: {err}"
            cls.bug_expect = "ibstat 应成功执行并返回设备状态"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-1 {name} 端 ibstat 执行失败")

        if "State: Active" not in result or "Physical state: LinkUp" not in result:
            cls.bug_result = f"{name} 端 IB 设备未处于 Active/LinkUp 状态。输出:\n{result}"
            cls.bug_expect = "至少有一个 IB 设备应处于 State: Active 且 Physical state: LinkUp"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-1 {name} 端 IB 设备状态异常")

        log.info(f"{name} 端 IB 设备状态正常")

    @classmethod
    def _load_ipoib_driver(cls, exec_addr: str, name: str) -> None:
        """加载 ipoib 驱动，优先 modprobe，失败后尝试 insmod"""
        log.info(f"在 {name} 端加载 ipoib 驱动...")

        # 优先使用 modprobe
        modprobe_cmd = f"modprobe {cls.IPoIB_MODULE_NAME}"
        status, result, err = CommandOperation.execute_command_with_error(modprobe_cmd, exec_addr)

        if status != RtnStatusEnum.SUCCESS.value:
            log.warning(f"{name} 端 modprobe 失败，尝试 insmod: {err}")

            # 查找 ib_ipoib.ko 路径
            find_cmd = f"find /lib/modules/$(uname -r) -name '{cls.IPoIB_MODULE_NAME}.ko' 2>/dev/null | head -1"
            status, ko_path, err = CommandOperation.execute_command_with_error(find_cmd, exec_addr)

            if status != RtnStatusEnum.SUCCESS.value or not ko_path.strip():
                cls.bug_result = f"{name} 端未找到 {cls.IPoIB_MODULE_NAME}.ko 文件"
                cls.bug_expect = f"应能在 /lib/modules 下找到 {cls.IPoIB_MODULE_NAME}.ko"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-1 {name} 端找不到 ipoib ko 文件")

            insmod_cmd = f"insmod {ko_path.strip()}"
            status, result, err = CommandOperation.execute_command_with_error(insmod_cmd, exec_addr)

            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"{name} 端加载 ipoib 驱动失败。modprobe/insmod 均失败: {err}"
                cls.bug_expect = "modprobe ib_ipoib 或 insmod ib_ipoib.ko 应成功执行"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"MC-1 {name} 端加载 ipoib 驱动失败")

        # 等待驱动加载完成（内核模块加载为异步过程，预留 2 秒确保模块状态稳定）
        time.sleep(2)
        log.info(f"{name} 端 ipoib 驱动加载命令执行完成")

    @classmethod
    def _verify_ipoib_loaded(cls, exec_addr: str, name: str) -> None:
        """验证 lsmod 输出中包含 ib_ipoib"""
        log.info(f"验证 {name} 端 ipoib 驱动是否加载成功...")

        cmd = f"lsmod | grep -w {cls.IPoIB_MODULE_NAME}"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)

        if status != RtnStatusEnum.SUCCESS.value or cls.IPoIB_MODULE_NAME not in result:
            cls.bug_result = f"{name} 端 lsmod 未找到 {cls.IPoIB_MODULE_NAME}。输出: {result}"
            cls.bug_expect = f"lsmod 输出中应包含 {cls.IPoIB_MODULE_NAME}"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(f"MC-1 {name} 端 ipoib 驱动加载验证失败")

        log.info(f"{name} 端 ipoib 驱动已加载:\n{result.strip()}")

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "MC-1 测试应正常执行完成"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)


def main() -> None:
    IbMulticastMc001.run()


if __name__ == '__main__':
    main()
