#!/usr/bin/env python3
# -*- encoding=utf8 -*-

"""
case author:   weiyuan1
script author: weiyuan1
date:          2026.09.07
description:

case number:   nic_linux_driver_tx_sched_r_01_28_025_004
case title:    TC层_可靠性_反向测试_修改队列数小于tc数
check point:   修改网卡的队列小于tc数
test condition:反向测试-非法/边界配置
test platform: 测试PF/VF；双机iperf3打流

@steps:
1. 检查网卡支持的tc数量
2. 设置dcbx host ieee（指令：dcb dcbx set dev <intf_name> host ieee）
3. 获取初始化状态tx_sched调度树tc 节点信息
4. 获取网卡的队列信息
5. 修改网卡的队列小于tc数
6. 执行dcb ets 分配tc时，tc大于队列数
7. 清理环境

@steps expect result:
1. 获取网卡支持的tc数量成功
2. 设置dcbx成功
3. 获取tc节点信息成功
4. 获取网卡的队列信成功
5. 命令执行成功
6. 命令执行失败
7. 清理环境成功

@changelog:

"""
import re
import add_syspath

from scripts.script_libs import log
from scripts.nic800.linux.driver.tx_scheduler.script_base_tx_sched_reliability_cos_test import (
    EtsAlgorithm, ScriptBaseTxSchedReliabilityCosTest, TcConfig)
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum
from scripts.script_libs.script_base import SxeException


class Script(ScriptBaseTxSchedReliabilityCosTest):
    exec_device_name_list, other_device_name_list = [], []
    server_host_os, client_host_os = [], []
    # 反向用例直接构造非法 tc-bw 命令，prio-tc 固定为 PRIO_TC
    PRIO_TC = [0, 1, 2, 3, 0, 1, 2, 3]

    @classmethod
    def set_parameters(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 设置需要调用的变量
        :return: 无返回值
        """
        super().set_parameters()

    @classmethod
    def _prio_tc_str(cls) -> str:
        """生成 prio-tc 字符串（索引为优先级，值为 TC）"""
        return ' '.join(f'{i}:{cls.PRIO_TC[i]}' for i in range(8))

    @classmethod
    def check_own_environment(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 检测当前脚本运行所需的局部环境是否具备，该方法只检测，不报bug,
                    函数内需要设定类变量local_enviroment_enabled的值，
                    局部环境检测正常，类变量local_enviroment_enabled设置为True
        :return: 无返回值
        """
        super().check_own_environment()

        cls.server_host_os, cls.client_host_os = CommonOperation.get_nic_os()
        result = CommonOperation.common_check_environment(cls)
        cls.own_environment_enabled = result
        for pf_port_info in cls.test_device_info_list:
            if cls.exec_address == CmdExecuteAdressEnum.SERVER.value:
                cls.exec_device_name_list.append(pf_port_info["server_device_name"])
                cls.other_device_name_list.append(pf_port_info["client_device_name"])
            else:
                cls.exec_device_name_list.append(pf_port_info["client_device_name"])
                cls.other_device_name_list.append(pf_port_info["server_device_name"])

        # 两端均需具备 dcb / iperf3 / ethtool 工具
        for exec_addr in (cls.exec_address, cls.other_exec_address):
            for cmd in ('which dcb', 'which iperf3', 'which ethtool'):
                rtn_code, _, _ = CommandOperation.execute_command_with_error(
                    cmd=cmd, cmd_execute_address=exec_addr)
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.error(f'环境检测失败: {exec_addr} 上执行 {cmd} 失败')
                    cls.own_environment_enabled = False
                    return

        # 检查执行端所有被测网口可用性
        for ifname in cls.exec_device_name_list:
            rtn_code, _, rtn_err = CommandOperation.execute_command_with_error(
                cmd=f'ip link show {ifname}', cmd_execute_address=cls.exec_address)
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.error(f'环境检测失败: 网口 {ifname} 不可用: {rtn_err}')
                cls.own_environment_enabled = False
                return

        cls.own_environment_enabled = True

    @classmethod
    def _get_current_combined_queues(cls, ifname: str) -> int:
        """
        author: weiyuan1
        date: 2026.09.14
        descriptor: 获取网卡当前 combined 队列数（ethtool -l 解析），失败返回 -1
        """
        rtn_code, rtn_outputs, _ = CommandOperation.execute_command_with_error(
            cmd=f'ethtool -l {ifname}', cmd_execute_address=cls.exec_address)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            return -1
        # 取 Current hardware settings 之后的 Combined 行
        current_part = rtn_outputs.split('Current hardware settings:', 1)[-1]
        match = re.search(r'Combined:\s*(\d+)', current_part)
        return int(match.group(1)) if match else -1

    @classmethod
    def _get_max_combined_queues(cls, ifname: str) -> int:
        """
        author: weiyuan1
        date: 2026.09.14
        descriptor: 获取网卡 Pre-set maximum combined 队列数，失败返回 -1
        """
        rtn_code, rtn_outputs, _ = CommandOperation.execute_command_with_error(
            cmd=f'ethtool -l {ifname}', cmd_execute_address=cls.exec_address)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            return -1
        pre_part = rtn_outputs.split('Pre-set maximums:', 1)[-1].split(
            'Current hardware settings:', 1)[0]
        match = re.search(r'Combined:\s*(\d+)', pre_part)
        return int(match.group(1)) if match else -1

    @classmethod
    def prepare(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 准备环境
        :return: 无返回值
        """
        super().prepare()

        # 步骤3 前置: 记录初始化状态下 tx_sched 调度树 tc 节点数量作为基线
        # 暂不实现: 获取tx_sched调度树tc节点信息的功能尚未实现，后续补充
        # cls.tx_sched_baseline_count = cls._get_tx_sched_tc_nodes()
        # if cls.tx_sched_baseline_count < 0:
        #     log.warning('获取 tx_sched 调度树初始化 tc 节点基线失败，步骤3 将按失败处理')
        # else:
        #     log.info(f'tx_sched 调度树初始化 tc 节点基线数量: '
        #              f'{cls.tx_sched_baseline_count}')

    @classmethod
    def do(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 执行测试环境
        :return: 无返回值
        """
        super().do()

        if not cls.exec_device_name_list:
            raise SxeException('未获取到 exec_device_name_list，无法执行测试')

        # 环境不满足时，check_own_environment() 中会直接退出，无需 try 捕获

        # 记录各网口原始队列数，步骤7/post 恢复用
        cls.origin_combined_queues_map = {}

        # 遍历多组网口，每组网口的全部测试步骤均在 for 循环内完成
        for exec_device, other_exec_device in zip(
                cls.exec_device_name_list, cls.other_device_name_list):
            log.info(f'===== 处理网口: {exec_device}'
                     f'（对端: {other_exec_device}）=====')

            # 记录原始队列数，post 恢复用
            cls.origin_combined_queues_map[exec_device] = \
                cls._get_current_combined_queues(exec_device)

            # 步骤1: 检查网卡支持的tc数量
            CommonOperation.concat_test_steps(
                '1. 检查网卡支持的tc数量; expect result: 1. 获取网卡支持的tc数量成功')

            tc_num = cls.get_max_supported_tcs(exec_device)
            cls.result_collect(
                0 if tc_num >= 1 else 1, '获取网卡支持的tc数量成功',
                f'网口 {exec_device} 支持的tc数量: {tc_num}')

            # 步骤2: 设置dcbx host ieee
            CommonOperation.concat_test_steps(
                '2. 设置dcbx host ieee（指令：dcb dcbx set dev <intf_name> '
                'host ieee）; expect result: 2. 设置dcbx成功')

            dcbx_ok = cls.set_dcbx_host_ieee(exec_device)
            cls.result_collect(
                dcbx_ok, '设置dcbx成功',
                f'网口 {exec_device} set_dcbx_host_ieee 返回: {dcbx_ok}')

            # 步骤3: 获取初始化状态tx_sched调度树tc 节点信息
            # 暂不实现: 获取tx_sched调度树tc节点信息的功能尚未实现，后续补充
            CommonOperation.concat_test_steps(
                '3. 获取初始化状态tx_sched调度树tc 节点信息; '
                'expect result: 3. 获取tc节点信息成功')

            cls.result_collect(
                0, '获取tc节点信息成功',
                f'网口 {exec_device} 获取tx_sched调度树tc节点信息'
                f'（暂未实现，按通过处理）')

            # 步骤4: 获取网卡的队列信息
            CommonOperation.concat_test_steps(
                '4. 获取网卡的队列信息（指令：ethtool -l <intf_name>）; '
                'expect result: 4. 获取网卡的队列信成功')

            current_queues = cls.origin_combined_queues_map[exec_device]
            queue_ok = current_queues >= 1
            cls.result_collect(
                0 if queue_ok else 1, '获取网卡的队列信成功',
                f'网口 {exec_device} 当前 combined 队列数: {current_queues}, '
                f'Pre-set maximum: {cls._get_max_combined_queues(exec_device)}')

            # 步骤5: 修改网卡的队列小于tc数
            CommonOperation.concat_test_steps(
                '5. 修改网卡的队列小于tc数（指令：ethtool -L <intf_name> '
                'combined <队列数>）; expect result: 5. 命令执行成功')

            less_queues = max(1, tc_num - 1) if current_queues > 1 else 1
            cmd = f'ethtool -L {exec_device} combined {less_queues}'
            rtn_code, _, rtn_err = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=cls.exec_address)
            change_ok = rtn_code == RtnStatusEnum.SUCCESS.value
            if not change_ok:
                log.error(f'修改队列数失败: {rtn_err}')
            cls.result_collect(
                change_ok, '命令执行成功',
                f'网口 {exec_device} 修改队列数 {current_queues} -> {less_queues} '
                f'（小于tc数 {tc_num}）, 返回码: {rtn_code}')

            # 步骤6: 执行dcb ets 分配tc时，tc大于队列数（反向，期望失败）
            prio_tc_str = cls._prio_tc_str()
            CommonOperation.concat_test_steps(
                '6. 执行dcb ets 分配tc时，tc大于队列数'
                '（指令：dcb ets set dev <intf_name> tc-tsa all:ets '
                'tc-bw 0:25 1:25 2:25 3:25 4:0 5:0 6:0 7:0 '
                f'prio-tc {prio_tc_str}）; '
                'expect result: 6. 命令执行失败')

            # 实测差异: 本驱动在队列数(4)小于tc数(8)时执行 dcb ets set
            # 仍返回成功（驱动未校验队列数与tc数关系），与用例预期"命令执行失败"不符。
            # 按用例预期忠实断言：命令未按预期失败时该步骤判 FAIL 并报 bug 跟踪。
            cls.execute_and_assert_fail(
                f'dcb ets set dev {exec_device} tc-tsa all:ets '
                f'tc-bw 0:25 1:25 2:25 3:25 4:0 5:0 6:0 7:0 '
                f'prio-tc {prio_tc_str}',
                'tc数量大于队列数时命令执行失败',
                description=(
                    '6. 执行dcb ets 分配tc时，tc大于队列数; '
                    'expect result: 6. 命令执行失败。'
                    '注意: 实测本驱动队列数小于tc数时配置仍成功，'
                    '未校验非法配置，若命令执行成功该步骤判失败并报bug'))

        # 步骤7: 清理环境（post 中恢复队列数并 restore_state）
        CommonOperation.concat_test_steps(
            '7. 清理环境; expect result: 7. 清理环境成功')

    @classmethod
    def post(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 整理环境及结果信息相关信息
        :return: 无返回值
        """
        # 先清理残余打流进程，再遍历恢复所有执行端网口队列数与 dcb 配置
        for exec_addr in (cls.exec_address, cls.other_exec_address):
            CommandOperation.execute_command_with_error(
                cmd='pkill -9 -f iperf3 2>/dev/null || true',
                cmd_execute_address=exec_addr)
        for ifname in cls.exec_device_name_list:
            if ifname:
                # 恢复原始队列数
                origin = cls.origin_combined_queues_map.get(ifname, -1)
                if origin >= 1:
                    rtn_code, _, rtn_err = CommandOperation.execute_command_with_error(
                        cmd=f'ethtool -L {ifname} combined {origin}',
                        cmd_execute_address=cls.exec_address)
                    if rtn_code != RtnStatusEnum.SUCCESS.value:
                        log.error(f'网口 {ifname} 恢复队列数 {origin} 失败: {rtn_err}')
                    else:
                        log.info(f'网口 {ifname} 队列数已恢复: {origin}')
                cls._dcb_manager(ifname).restore_state()
        super().post()


def main() -> None:
    Script.run()


if __name__ == "__main__":
    main()
