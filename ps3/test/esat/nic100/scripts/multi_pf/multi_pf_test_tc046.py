#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: TC-046
case title: 通过cli对双端口所有pport设置非法pf数量，设置失败且配置不生效-双端口
test category: IB多PF测试
check point: 非法PF数量设置被拒绝，且非法配置不会生效
author: zhubo1
date: 2026.06.16
@steps:
    1. client和server端均先检查并记录当前PF数量作为基准值；若当前PF数量不是默认值（如4），则先通过 mlxconfig -d mlx5_0 -y set NUM_OF_PF=4 设置为合法值后重启服务器，使基准状态稳定。
    2. 对双端口所有pport（mlx5_0、mlx5_1）逐一执行非法PF数量设置，非法值包括：17、10000、-1、ab、1&、2|、&3、|4、5&&、6||、&&7、||8、#9、9#。命令格式为 mlxconfig -d <dev> -y set NUM_OF_PF=<value>，其中含shell特殊字符的值需用单引号包裹。
    3. 对每个非法值，验证mlxconfig命令返回码非0，且回显中包含error、failed、invalid、illegal等错误提示关键字。
    4. 所有非法值验证完成后，执行一次服务器重启。重启后先等待约30秒让服务器进入重启流程，再通过命令输出动态检测服务器上线（超时300秒）。
    5. 重启后通过 ibstat -l 和 lspci | grep Mell 检查PF数量，确认与步骤1的基准值一致。
    6. 对mlx5_0、mlx5_1分别执行 mlxconfig -d <dev> q，确认当前配置中NUM_OF_PF仍为原合法值。

@expected:
    1. 当前PF数量可正常获取并记录；若发生设置，合法值设置成功且服务器重启成功。
    2. 所有非法值的mlxconfig命令均执行失败（返回码非0）。
    3. 每个非法值执行后，命令回显均包含error/failed/invalid/illegal等错误提示关键字。
    4. 服务器重启成功。
    5. 重启后PF数量与测试前基准值一致；ibstat和lspci | grep Mell显示的设备数量相同且均未变化。
    6. mlxconfig -d mlx5_0 q 和 mlxconfig -d mlx5_1 q 显示NUM_OF_PF仍为原合法值，未被非法设置篡改。

@changelog:
2026.06.16 - 根据优化后的TC-046用例生成
- 参数化非法值列表，对每个值单独判定返回码和错误关键字
- 对shell特殊字符进行安全转义
- 记录PF数量基准值，reboot后对比确认配置未生效
- 失败时通过 create_bug 自动记录Bug
- 移除非法值 0（其为合法值），并在错误关键字中增加 mlxconfig 明确错误前缀 `-E-`
"""

import os
import time
import re
import add_syspath
from typing import List, Tuple
from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum, BugTypeEnum
from scripts.script_libs.script_base import ScriptBase, SxeException
from scripts.script_libs.common_operation import CommonOperation


class MultiPfTestTc046(ScriptBase):
    test_object = "Multi PF Test"
    test_module = "IB Multi PF Test"
    test_tool = "mlxconfig, ibstat, lspci"
    test_precondition = "天蝎网卡为双端口形态"
    test_steps = """
    1. 检查并记录当前PF数量作为基准值，必要时先设置为合法值并重启
    2. 对mlx5_0、mlx5_1逐一设置非法PF数量值（含超范围、负数、非数字、shell特殊字符）
    3. 验证每个非法值均返回非0且回显含错误关键字
    4. 执行服务器重启并检测上线
    5. 重启后检查PF数量与基准值一致
    6. 查询mlx5_0、mlx5_1配置，确认NUM_OF_PF仍为合法值
    """

    REBOOT_WAIT_SECONDS = 30
    SERVER_AVAILABILITY_TIMEOUT = 300
    DEFAULT_PF_COUNT = 4
    PPORT_DEVICES = ["mlx5_0", "mlx5_1"]

    INVALID_VALUES = [
        "17",      # 超过当前环境最大4
        "10000",   # 极大值
        "-1",      # 负数
        "ab",      # 非数字
        "1&",      # shell特殊字符
        "2|",
        "&3",
        "|4",
        "5&&",
        "6||",
        "&&7",
        "||8",
        "#9",
        "9#",
        "999999999",  # 超极大值
        "1.5",     # 浮点数
        "",        # 空字符串
        " ",       # 仅空格
    ]

    ERROR_KEYWORDS = ["error", "failed", "invalid", "illegal", "unsupported", "cannot", "-e-"]

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "MultiPfTestTc046 Failed"
        cls.test_results = {
            "total_steps": 0,
            "passed_steps": 0,
            "failures": []
        }

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 TC-046 测试环境...")
        server_driver, client_driver = CommonOperation.get_nic_driver_name()
        log.info(f"服务端驱动: {server_driver}, 客户端驱动: {client_driver}")

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client")
        ]:
            status, result, err = CommandOperation.execute_command_with_error("ibstat -l", exec_addr)
            if status != RtnStatusEnum.SUCCESS.value or not result.strip():
                log.error(f"{name} 端未找到 IB 设备")
                cls.own_environment_enabled = False
                return

        cls.own_environment_enabled = True
        log.info("环境检查通过")

    @classmethod
    def prepare(cls) -> None:
        log.info("准备 TC-046 测试环境...")
        cls.baseline_pf_count_server = cls.get_pf_count(CmdExecuteAdressEnum.SERVER.value)
        cls.baseline_pf_count_client = cls.get_pf_count(CmdExecuteAdressEnum.CLIENT.value)
        log.info(
            f"初始 PF 数量 - 服务端: {cls.baseline_pf_count_server}, "
            f"客户端: {cls.baseline_pf_count_client}"
        )

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 TC-046 测试：通过cli对双端口所有pport设置非法pf数量，设置失败且配置不生效-双端口")
        log.info("=" * 60)

        try:
            cls.test_results["total_steps"] = 6

            # 步骤1：确保基准状态为合法PF数量
            log.info("\n步骤1：检查并稳定 PF 数量基准值")
            cls.ensure_baseline_pf_count()
            cls.test_results["passed_steps"] += 1

            # 步骤2/3：对所有pport执行非法值设置并验证失败
            log.info("\n步骤2/3：对 pport 执行非法 PF 数量设置并验证失败")
            invalid_value_failures = cls.test_invalid_pf_values()
            if invalid_value_failures:
                cls.bug_result = f"Some invalid PF values were not rejected: {'; '.join(invalid_value_failures)}"
                cls.bug_expect = "All invalid PF values should be rejected by mlxconfig"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(cls.bug_result)
            cls.test_results["passed_steps"] += 2

            # 步骤4：执行一次服务器重启
            log.info("\n步骤4：执行服务器重启以验证非法配置不生效")
            cls.reboot_servers()
            cls.test_results["passed_steps"] += 1

            # 步骤5：验证PF数量与基准值一致
            log.info("\n步骤5：重启后验证 PF 数量未变化")
            cls.verify_pf_count_unchanged()
            cls.test_results["passed_steps"] += 1

            # 步骤6：查询mlxconfig配置确认未被篡改
            log.info("\n步骤6：查询 pport 配置，确认 NUM_OF_PF 仍为合法值")
            cls.verify_config_unchanged()
            cls.test_results["passed_steps"] += 1

            cls.print_test_summary()
            log.info("测试执行成功 - TC-046 通过")
        except SxeException:
            cls.print_test_summary()
            raise
        except Exception as e:
            cls.print_test_summary()
            log.error(f"TC-046 测试失败（未预期错误）: {e}")
            raise

    @classmethod
    def get_pf_count(cls, exec_addr: str) -> int:
        lspci_cmd = "lspci | grep -i mellanox | wc -l"
        status, result, err = CommandOperation.execute_command_with_error(lspci_cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value:
            try:
                return int(result.strip())
            except ValueError:
                return 0
        return 0

    @classmethod
    def get_ibstat_count(cls, exec_addr: str) -> int:
        ibstat_cmd = "ibstat -l | wc -l"
        status, result, err = CommandOperation.execute_command_with_error(ibstat_cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value:
            try:
                return int(result.strip())
            except ValueError:
                return 0
        return 0

    @classmethod
    def ensure_baseline_pf_count(cls) -> None:
        log.info(f"确保基准 PF 数量为 {cls.DEFAULT_PF_COUNT}")
        need_reboot = False

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client")
        ]:
            current_pf = cls.get_pf_count(exec_addr)
            if current_pf == cls.DEFAULT_PF_COUNT:
                log.info(f"{name} 端 PF 数量已经是 {cls.DEFAULT_PF_COUNT}，跳过设置")
                continue

            mlxconfig_cmd = f"mlxconfig -d mlx5_0 -y set NUM_OF_PF={cls.DEFAULT_PF_COUNT}"
            status, result, err = CommandOperation.execute_command_with_error(mlxconfig_cmd, exec_addr)
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"Failed to set baseline PF count on {name}: {err}"
                cls.bug_expect = "mlxconfig should accept valid PF count"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(cls.bug_result)
            log.info(f"在 {name} 端设置基准 PF 数量为 {cls.DEFAULT_PF_COUNT}")
            need_reboot = True

        if need_reboot:
            cls.reboot_servers()
        else:
            log.info("基准 PF 数量已稳定，无需重启")

    @classmethod
    def test_invalid_pf_values(cls) -> List[str]:
        failures = []

        for device in cls.PPORT_DEVICES:
            log.info(f"\n测试设备: {device}")
            for value in cls.INVALID_VALUES:
                # 对含shell特殊字符的值使用单引号包裹
                if re.search(r'[&|#\s]', value):
                    quoted_value = f"'{value}'"
                else:
                    quoted_value = value

                mlxconfig_cmd = f"mlxconfig -d {device} -y set NUM_OF_PF={quoted_value}"
                log.info(f"  测试非法值: '{value}'")

                status, result, err = CommandOperation.execute_command_with_error(
                    mlxconfig_cmd, CmdExecuteAdressEnum.SERVER.value
                )
                combined_output = f"{result if result else ''}\n{err if err else ''}"

                # 非法值应返回非0
                if status == RtnStatusEnum.SUCCESS.value:
                    failures.append(f"{device}={value}: command succeeded unexpectedly")
                    log.error(f"    非法值 '{value}' 在 {device} 上被错误接受")
                    continue

                # 回显应包含错误关键字
                has_error_keyword = any(
                    keyword in combined_output.lower() for keyword in cls.ERROR_KEYWORDS
                )
                if not has_error_keyword:
                    failures.append(f"{device}={value}: no error keyword in output")
                    log.error(f"    非法值 '{value}' 在 {device} 上失败但无错误关键字")
                    continue

                log.info(f"    非法值 '{value}' 被正确拒绝")

        return failures

    @classmethod
    def reboot_servers(cls) -> None:
        log.info("重启服务器...")

        for exec_addr, name in [
            (CmdExecuteAdressEnum.CLIENT.value, "client"),
            (CmdExecuteAdressEnum.SERVER.value, "server")
        ]:
            log.info(f"正在重启 {name} 服务器...")
            reboot_cmd = "nohup sh -c 'sleep 2 && reboot' > /dev/null 2>&1 &"
            CommandOperation.execute_command_with_error(reboot_cmd, exec_addr)

        log.info(f"等待服务器开始重启（{cls.REBOOT_WAIT_SECONDS} 秒）...")
        time.sleep(cls.REBOOT_WAIT_SECONDS)

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client")
        ]:
            if not cls.wait_for_server_availability(exec_addr, timeout=cls.SERVER_AVAILABILITY_TIMEOUT):
                cls.bug_result = f"Server {name} did not become available after reboot"
                cls.bug_expect = "Server should be available within 300 seconds"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"Server {name} unavailable after reboot")

        time.sleep(15)
        log.info("服务器重启后已就绪")

    @classmethod
    def wait_for_server_availability(cls, server_address: str, timeout: int = 300) -> bool:
        log.info(f"等待服务器 {server_address} 可用（超时: {timeout}秒）")

        start_time = time.time()
        while time.time() - start_time < timeout:
            status, result, err = CommandOperation.execute_command_with_error("echo ping", server_address)
            if status == RtnStatusEnum.SUCCESS.value and result and "ping" in result.strip():
                log.info(f"服务器 {server_address} 已可用（已通过命令输出验证）")
                return True
            time.sleep(5)

        log.error(f"等待服务器 {server_address} 超时")
        return False

    @classmethod
    def verify_pf_count_unchanged(cls) -> None:
        log.info("验证重启后 PF 数量与基准值一致...")

        for exec_addr, name, baseline in [
            (CmdExecuteAdressEnum.SERVER.value, "server", cls.baseline_pf_count_server),
            (CmdExecuteAdressEnum.CLIENT.value, "client", cls.baseline_pf_count_client)
        ]:
            lspci_count = cls.get_pf_count(exec_addr)
            ibstat_count = cls.get_ibstat_count(exec_addr)

            log.info(f"{name} 端 - lspci: {lspci_count}, ibstat: {ibstat_count}, 基准: {baseline}")

            if lspci_count != cls.DEFAULT_PF_COUNT or ibstat_count != cls.DEFAULT_PF_COUNT:
                cls.bug_result = (
                    f"PF count changed after reboot on {name}: "
                    f"lspci={lspci_count}, ibstat={ibstat_count}, expected={cls.DEFAULT_PF_COUNT}"
                )
                cls.bug_expect = "PF count should remain unchanged after invalid setting attempts"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(cls.bug_result)

        log.info("PF 数量未发生变化")

    @classmethod
    def verify_config_unchanged(cls) -> None:
        log.info("验证 pport 配置未被非法设置篡改...")

        for device in cls.PPORT_DEVICES:
            mlxconfig_cmd = f"mlxconfig -d {device} q"
            status, result, err = CommandOperation.execute_command_with_error(
                mlxconfig_cmd, CmdExecuteAdressEnum.SERVER.value
            )
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"Failed to query {device} config: {err}"
                cls.bug_expect = "mlxconfig query should succeed"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(cls.bug_result)

            output = result if result else ""
            # 查找 NUM_OF_PF 当前值
            match = re.search(r'NUM_OF_PF\s+\S*\s*(\d+)', output)
            if not match:
                cls.bug_result = f"Could not find NUM_OF_PF in {device} config output"
                cls.bug_expect = "mlxconfig q should show NUM_OF_PF"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(cls.bug_result)

            current_value = match.group(1)
            log.info(f"{device} 当前 NUM_OF_PF: {current_value}")

            if current_value != str(cls.DEFAULT_PF_COUNT):
                cls.bug_result = (
                    f"{device} NUM_OF_PF was tampered: current={current_value}, "
                    f"expected={cls.DEFAULT_PF_COUNT}"
                )
                cls.bug_expect = "NUM_OF_PF should remain at baseline value"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(cls.bug_result)

        log.info("pport 配置验证通过，NUM_OF_PF 未被篡改")

    @classmethod
    def print_test_summary(cls) -> None:
        total = cls.test_results["total_steps"]
        passed = cls.test_results["passed_steps"]
        failed = total - passed
        log.info("=" * 60)
        log.info("测试执行结果摘要")
        log.info("=" * 60)
        log.info(f"总步骤: {total}")
        log.info(f"通过: {passed}")
        log.info(f"失败: {failed}")
        if cls.test_results["failures"]:
            log.info("失败步骤:")
            for failure in cls.test_results["failures"]:
                log.info(f"  - {failure}")
        log.info("=" * 60)
        log.info(f"测试结果: {'通过' if failed == 0 else '失败'}")
        log.info("=" * 60)

    @classmethod
    def post(cls) -> None:
        log.info("清理测试环境...")

        cleanup_cmd = "rm -f /tmp/mlxconfig_invalid_*.log 2>/dev/null || true"
        CommandOperation.execute_command_with_error(cleanup_cmd, CmdExecuteAdressEnum.SERVER.value)

        log.info("清理完成")


def main() -> None:
    MultiPfTestTc046.run()


if __name__ == '__main__':
    main()
