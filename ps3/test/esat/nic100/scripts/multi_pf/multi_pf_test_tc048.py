#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: TC-048
case title: 对网卡设置 PF 数量后，vport/单个 PF 复位不会使 PF 数量配置生效-双端口
test category: IB多PF测试
check point: 仅网卡级复位使 PF 数量配置生效；vport 级、PF 级复位均不生效
author: zhubo1
date: 2026.06.17
@steps:
    1. 在 server 端执行 mlxconfig -d mlx5_0 -y set NUM_OF_PF=2，然后重启服务器；等待 30 秒后循环检测服务器上线（超时 300 秒），验证 PF 数量为 2。
    2. 执行 mlxconfig -d mlx5_0 -y set NUM_OF_PF=4，获取 vport1（pf 1，对应 mlx5_1）的 PCI BDF，执行 function 级复位；等待该设备从 ibstat 中消失后执行 /etc/init.d/openibd force-restart，等待 10 秒，验证 PF 数量仍为 2。
    3. 对网卡执行重启，等待 30 秒后循环检测服务器上线（超时 300 秒），验证 PF 数量为 4。
    4. 执行 mlxconfig -d mlx5_0 -y set NUM_OF_PF=1，依次获取当前所有 PF（mlx5_0~mlx5_3）的 PCI BDF，对每个 BDF 执行 function 级复位；等待所有设备从 ibstat 中消失后执行 /etc/init.d/openibd force-restart，等待 10 秒，验证 PF 数量仍为 4。
    5. 对网卡执行重启，等待 30 秒后循环检测服务器上线（超时 300 秒），验证 PF 数量为 1。

@expected:
    1. mlxconfig 返回 0；服务器重启成功；ibstat -l | wc -l 和 lspci | grep Mell 均显示 PF 数量为 2。
    2. function 复位命令成功；设备从 ibstat 中消失并恢复驱动后，PF 数量仍为 2，说明 vport 级复位不会使 PF 数量配置生效。
    3. 服务器重启成功；PF 数量变为 4，说明网卡级复位使 PF 数量配置生效。
    4. 所有 PF 级复位命令成功；设备从 ibstat 中消失并恢复驱动后，PF 数量仍为 4，说明 PF 级复位不会使 PF 数量配置生效。
    5. 服务器重启成功；PF 数量变为 1，证明网卡级复位最终能使 PF=1 配置生效。

@changelog:
2026.06.17 - 根据优化后的 TC-048 用例生成
- 使用项目技巧：PF 数量相同跳过设置/重启、reboot 后 30 秒再检测、function 复位后等待设备从 ibstat 中消失并恢复 IB 驱动
- 明确 vport 级复位（mlx5_1）与 PF 级复位（mlx5_0~mlx5_3）的具体命令
- 增加 PF=1 最终生效验证，覆盖配置生效边界
- 失败时通过 create_bug 自动记录 Bug
- 不强制还原 PF 数量
"""

import time
import re
import add_syspath
from typing import List
from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum, BugTypeEnum
from scripts.script_libs.script_base import ScriptBase, SxeException
from scripts.script_libs.common_operation import CommonOperation


class MultiPfTestTc048(ScriptBase):
    test_object = "Multi PF Test"
    test_module = "IB Multi PF Test"
    test_tool = "mlxconfig, ibstat, lspci, ethtool, openibd"
    test_precondition = "天蝎网卡为双端口形态，mlx5_0、mlx5_1 为 pport，mlx5_2、mlx5_3 为 vport"
    test_steps = """
    1. 设置 PF 数量为 2 并重启服务器，验证 PF 数量为 2
    2. 设置 PF 数量为 4，仅对 vport1（mlx5_1）执行 function 复位，验证 PF 数量仍为 2
    3. 重启服务器，验证 PF 数量变为 4
    4. 设置 PF 数量为 1，对所有 PF 执行 function 级复位，验证 PF 数量仍为 4
    5. 重启服务器，验证 PF 数量变为 1
    """

    REBOOT_WAIT_SECONDS = 30
    SERVER_AVAILABILITY_TIMEOUT = 300
    DRIVER_RECOVER_WAIT_SECONDS = 10
    POST_REBOOT_STABILIZE_SECONDS = 15
    DEFAULT_PF_COUNT = 4
    PPORT_DEVICES = ["mlx5_0", "mlx5_1"]

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "MultiPfTestTc048 Failed"
        cls.test_results = {
            "total_steps": 0,
            "passed_steps": 0,
            "failures": []
        }

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 TC-048 测试环境...")
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
        log.info("准备 TC-048 测试环境...")
        cls.initial_pf_count_server = cls.get_pf_count(CmdExecuteAdressEnum.SERVER.value)
        cls.initial_pf_count_client = cls.get_pf_count(CmdExecuteAdressEnum.CLIENT.value)
        log.info(
            f"初始 PF 数量 - 服务端: {cls.initial_pf_count_server}, "
            f"客户端: {cls.initial_pf_count_client}"
        )

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 TC-048 测试：对网卡设置 PF 数量后，vport/单个 PF 复位不会使 PF 数量配置生效-双端口")
        log.info("=" * 60)

        try:
            cls.test_results["total_steps"] = 5

            # 步骤1：设置 PF=2 并验证
            log.info("\n步骤1：设置 PF 数量为 2 并重启验证")
            cls.set_pf_and_reset(2)
            cls.verify_pf_count(2)
            cls.test_results["passed_steps"] += 1

            # 步骤2：设置 PF=4，仅复位 vport1（mlx5_1），验证 PF 仍为 2
            log.info("\n步骤2：设置 PF 数量为 4，仅复位 vport1（mlx5_1），验证 PF 数量未变化")
            cls.set_pf_without_reboot(4)
            for exec_addr, name in [
                (CmdExecuteAdressEnum.SERVER.value, "server"),
                (CmdExecuteAdressEnum.CLIENT.value, "client")
            ]:
                log.info(f"在 {name} 端复位 vport1（mlx5_1）")
                cls.reset_single_function("mlx5_1", exec_addr)
            cls.verify_pf_count(2)
            cls.test_results["passed_steps"] += 1

            # 步骤3：网卡级复位，验证 PF=4 生效
            log.info("\n步骤3：网卡级复位，验证 PF 数量为 4")
            cls.reboot_servers_for_pf_changes()
            cls.verify_pf_count(4)
            cls.test_results["passed_steps"] += 1

            # 步骤4：设置 PF=1，对所有 PF 执行 function 级复位，验证 PF 仍为 4
            log.info("\n步骤4：设置 PF 数量为 1，对所有 PF 执行 function 级复位，验证 PF 数量未变化")
            cls.set_pf_without_reboot(1)
            for exec_addr, name in [
                (CmdExecuteAdressEnum.SERVER.value, "server"),
                (CmdExecuteAdressEnum.CLIENT.value, "client")
            ]:
                log.info(f"在 {name} 端对所有 PF 执行 function 级复位")
                cls.reset_all_pfs(["mlx5_0", "mlx5_1", "mlx5_2", "mlx5_3"], exec_addr)
            cls.verify_pf_count(4)
            cls.test_results["passed_steps"] += 1

            # 步骤5：网卡级复位，验证 PF=1 最终生效
            log.info("\n步骤5：网卡级复位，验证 PF 数量为 1")
            cls.reboot_servers_for_pf_changes()
            cls.verify_pf_count(1)
            cls.test_results["passed_steps"] += 1

            cls.print_test_summary()
            log.info("测试执行成功 - TC-048 通过")
        except SxeException:
            cls.print_test_summary()
            raise
        except Exception as e:
            cls.print_test_summary()
            log.error(f"TC-048 测试失败（未预期错误）: {e}")
            raise

    @classmethod
    def get_pf_count(cls, exec_addr: str) -> int:
        """通过 lspci 获取 Mellanox PF 数量"""
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
        """通过 ibstat -l 获取 IB 设备数量"""
        ibstat_cmd = "ibstat -l | wc -l"
        status, result, err = CommandOperation.execute_command_with_error(ibstat_cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value:
            try:
                return int(result.strip())
            except ValueError:
                return 0
        return 0

    @classmethod
    def set_pf_and_reset(cls, pf_count: int, device: str = "mlx5_0") -> None:
        """设置 PF 数量并在变更后重启服务器"""
        log.info(f"设置 {device} 的 PF 数量为 {pf_count} 并重启...")
        need_reboot = False

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client")
        ]:
            current_pf = cls.get_pf_count(exec_addr)
            if current_pf == pf_count:
                log.info(f"{name} 端 PF 数量已经是 {pf_count}，跳过设置")
                continue

            mlxconfig_cmd = f"mlxconfig -d {device} -y set NUM_OF_PF={pf_count}"
            status, result, err = CommandOperation.execute_command_with_error(mlxconfig_cmd, exec_addr)
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"Failed to set PF count to {pf_count} on {name}: {err}"
                cls.bug_expect = "mlxconfig command should succeed with return code 0"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"mlxconfig command failed on {name}: {err}")
            log.info(f"在 {name} 端成功设置 {device} PF 数量为 {pf_count}")
            need_reboot = True

        if need_reboot:
            cls.reboot_servers_for_pf_changes()
        else:
            log.info("配置未变更，跳过重启")

    @classmethod
    def set_pf_without_reboot(cls, pf_count: int, device: str = "mlx5_0") -> None:
        """仅设置 PF 数量，不执行重启（用于后续验证复位不会使配置生效）"""
        log.info(f"设置 {device} 的 PF 数量为 {pf_count}（暂不重启）...")

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client")
        ]:
            mlxconfig_cmd = f"mlxconfig -d {device} -y set NUM_OF_PF={pf_count}"
            status, result, err = CommandOperation.execute_command_with_error(mlxconfig_cmd, exec_addr)
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"Failed to set PF count to {pf_count} on {name}: {err}"
                cls.bug_expect = "mlxconfig command should succeed with return code 0"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(f"mlxconfig command failed on {name}: {err}")
            log.info(f"在 {name} 端成功设置 {device} PF 数量为 {pf_count}")

    @classmethod
    def reboot_servers_for_pf_changes(cls) -> None:
        """重启服务器以应用 PF 数量变更"""
        log.info("重启服务器以应用 PF 数量变更...")

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

        time.sleep(cls.POST_REBOOT_STABILIZE_SECONDS)
        log.info("服务器重启后已就绪")

    @classmethod
    def wait_for_server_availability(cls, server_address: str, timeout: int = 300) -> bool:
        """通过命令输出动态检测服务器是否可用"""
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
    def get_device_bdf(cls, device: str, exec_addr: str) -> str:
        """根据 IB 设备名获取 PCI BDF 地址"""
        # 方法1：通过 /sys/class/infiniband/{device}/device 的符号链接获取 BDF
        cmd = f"readlink -f /sys/class/infiniband/{device}/device"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value and result.strip():
            match = re.search(r'([0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F])$', result.strip())
            if match:
                return match.group(1)

        # 方法2：通过 ethtool -i 获取 bus-info
        cmd = f"ethtool -i {device}"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status == RtnStatusEnum.SUCCESS.value and result:
            match = re.search(r'bus-info:\s*([0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F])', result)
            if match:
                return match.group(1)

        cls.bug_result = f"Could not get BDF for device {device}"
        cls.bug_expect = "Should be able to get PCI BDF from /sys or ethtool"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(cls.bug_result)
        return ""

    @classmethod
    def is_device_in_ibstat(cls, device: str, exec_addr: str) -> bool:
        """检查指定 IB 设备是否仍在 ibstat -l 输出中"""
        cmd = f"ibstat -l | grep -q '^{device}$' && echo yes || echo no"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        return status == RtnStatusEnum.SUCCESS.value and result.strip() == "yes"

    @classmethod
    def reset_single_function(cls, device: str, exec_addr: str) -> None:
        """对单个 function（PF/VF）执行复位并恢复驱动"""
        log.info(f"对设备 {device} 执行 function 级复位...")

        bdf = cls.get_device_bdf(device, exec_addr)
        log.info(f"设备 {device} 的 BDF 为 {bdf}")

        reset_cmd = f"echo 1 | sudo tee /sys/bus/pci/devices/{bdf}/reset"
        status, result, err = CommandOperation.execute_command_with_error(reset_cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"Failed to reset function {device} (BDF: {bdf}): {err}"
            cls.bug_expect = "Function reset should succeed"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)
        log.info(f"设备 {device} 复位命令执行成功")

        # 等待设备从 ibstat 中消失（PCI 设备不会消失）
        log.info(f"等待设备 {device} 从 ibstat 中消失...")
        wait_start = time.time()
        while time.time() - wait_start < 60:
            if not cls.is_device_in_ibstat(device, exec_addr):
                log.info(f"设备 {device} 已从 ibstat 中消失")
                break
            time.sleep(1)
        else:
            cls.bug_result = f"Device {device} still visible in ibstat after reset"
            cls.bug_expect = "Device should disappear from ibstat after function reset"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)

        # 恢复 IB 驱动
        log.info("执行 /etc/init.d/openibd force-restart 恢复 IB 驱动...")
        restart_cmd = "/etc/init.d/openibd force-restart"
        status, result, err = CommandOperation.execute_command_with_error(restart_cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"Failed to restart IB driver after resetting {device}: {err}"
            cls.bug_expect = "openibd force-restart should succeed"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)

        log.info(f"等待驱动稳定（{cls.DRIVER_RECOVER_WAIT_SECONDS} 秒）...")
        time.sleep(cls.DRIVER_RECOVER_WAIT_SECONDS)
        log.info(f"设备 {device} function 复位及驱动恢复完成")

    @classmethod
    def reset_all_pfs(cls, devices: List[str], exec_addr: str) -> None:
        """对所有指定 PF 依次执行 function 级复位并恢复驱动"""
        log.info(f"对以下设备依次执行 function 级复位: {devices}")

        bdfs = []
        for device in devices:
            bdf = cls.get_device_bdf(device, exec_addr)
            bdfs.append((device, bdf))
            log.info(f"设备 {device} 的 BDF 为 {bdf}")

        # 依次执行复位
        for device, bdf in bdfs:
            reset_cmd = f"echo 1 | sudo tee /sys/bus/pci/devices/{bdf}/reset"
            status, result, err = CommandOperation.execute_command_with_error(reset_cmd, exec_addr)
            if status != RtnStatusEnum.SUCCESS.value:
                cls.bug_result = f"Failed to reset function {device} (BDF: {bdf}): {err}"
                cls.bug_expect = "Function reset should succeed"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(cls.bug_result)
            log.info(f"设备 {device} 复位命令执行成功")

        # 等待所有设备从 ibstat 中消失（PCI 设备不会消失）
        log.info("等待所有复位设备从 ibstat 中消失...")
        wait_start = time.time()
        while time.time() - wait_start < 120:
            all_gone = True
            for device, bdf in bdfs:
                if cls.is_device_in_ibstat(device, exec_addr):
                    all_gone = False
                    break
            if all_gone:
                log.info("所有复位设备已从 ibstat 中消失")
                break
            time.sleep(1)
        else:
            cls.bug_result = "Some reset devices still visible in ibstat within 120 seconds"
            cls.bug_expect = "All reset devices should disappear from ibstat after function reset"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)

        # 恢复 IB 驱动
        log.info("执行 /etc/init.d/openibd force-restart 恢复 IB 驱动...")
        restart_cmd = "/etc/init.d/openibd force-restart"
        status, result, err = CommandOperation.execute_command_with_error(restart_cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            cls.bug_result = f"Failed to restart IB driver after resetting all PFs: {err}"
            cls.bug_expect = "openibd force-restart should succeed"
            cls.set_bug_type(BugTypeEnum.FUNCTION.value)
            cls.create_bug(cls.bug_result)

        log.info(f"等待驱动稳定（{cls.DRIVER_RECOVER_WAIT_SECONDS} 秒）...")
        time.sleep(cls.DRIVER_RECOVER_WAIT_SECONDS)
        log.info("所有 PF function 复位及驱动恢复完成")

    @classmethod
    def verify_pf_count(cls, expected_pf_count: int) -> None:
        """验证 server 和 client 两端 PF 数量是否符合预期"""
        log.info(f"验证 PF 数量是否为 {expected_pf_count} ...")

        for exec_addr, name in [
            (CmdExecuteAdressEnum.SERVER.value, "server"),
            (CmdExecuteAdressEnum.CLIENT.value, "client")
        ]:
            actual_lspci = cls.get_pf_count(exec_addr)
            actual_ibstat = cls.get_ibstat_count(exec_addr)
            log.info(f"{name} 端 - lspci={actual_lspci}, ibstat={actual_ibstat}")

            if actual_lspci != expected_pf_count or actual_ibstat != expected_pf_count:
                cls.bug_result = (
                    f"PF count mismatch on {name}: expected {expected_pf_count}, "
                    f"lspci={actual_lspci}, ibstat={actual_ibstat}"
                )
                cls.bug_expect = f"PF count should be {expected_pf_count}"
                cls.set_bug_type(BugTypeEnum.FUNCTION.value)
                cls.create_bug(cls.bug_result)

        log.info(f"PF 数量验证通过: {expected_pf_count}")

    @classmethod
    def print_test_summary(cls) -> None:
        """打印测试执行结果摘要"""
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
        log.info("TC-048 测试结束，不强制还原 PF 数量")


def main() -> None:
    MultiPfTestTc048.run()


if __name__ == '__main__':
    main()
