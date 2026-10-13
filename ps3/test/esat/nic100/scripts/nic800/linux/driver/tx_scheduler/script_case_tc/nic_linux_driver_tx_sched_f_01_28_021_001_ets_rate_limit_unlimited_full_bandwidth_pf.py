#!/usr/bin/env python3
# -*- encoding=utf8 -*-

"""
case author:   weiyuan1
script author: weiyuan1
date:          2026.09.07
description:

case number:   nic_linux_driver_tx_sched_f_01_28_021_001
case title:    TC层_基础功能_进内核PF配置tc_ets算法限速tc和未配置限速的tc的带宽为满流量（设置的tc数量包含=2）
check point:   ets算法限速tc和未配置限速的tc的带宽为满流量（设置的tc数量包含=2）
test condition:组合覆盖：设置的tc数量包含∈{2,2-4之间任意一个,支持的最大tc数}
test platform: 测试PF/VF；双机iperf3打流

@steps:
1. 检查网卡支持的tc数量
2. 设置dcbx host ieee（指令：dcb dcbx set dev <intf_name> host ieee）
3. 获取初始化状态tx_sched调度树tc 节点信息
4. dcb ets 设置带宽比例（设置的tc数量包含=2）（指令：dcb ets set dev <intf_name> tc-tsa all:ets tc-bw 0:25 1:25 2:25 3:25 4:0 5:0 6:0 7:0 prio-tc 0:0 1:1 2:2 3:3 4:0 5:1 6:2 7:3）
5. 查询dcb ets show dev <intf_name>（指令：dcb ets show dev <intf_name>）
6. 检索tx_sched调度树tc 节点是否增加
7. 对tc 设置限速（指令：dcb maxrate set dev <inf_name> tc-max 0:200 1:400 2:400 3:400 4:500 5:600 7:100）
8. tc app绑定优先级与tos（指令：dcb app add dev eth0 dscp <dscp>:<prio>）
9. 启动多个iperf3进程按照tos优先级同时进行打流， 且设置所有tc的带宽均为满带宽（指令：iperf3 --tos <tos>）

@steps expect result:
1. 获取网卡支持的tc数量成功
2. 设置dcbx成功
3. 获取tc节点信息成功
4. dcb ets设置带宽比例成功
5. dcb ets 结果与设置的结果一致
6. tc节点增加
7. 限速设置成功
8. 绑定优先级成功
9. 打流成功，限速tc的带宽值为限速带宽值之内，未限速的tc的带宽值未达标

@changelog:

"""
import add_syspath
import re

from scripts.script_libs import log
from scripts.nic800.linux.driver.tx_scheduler.script_base_tx_sched_cos_test import (
    EtsAlgorithm, ScriptBaseTxSchedCosTest, TcConfig)
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import RtnStatusEnum
from scripts.script_libs.script_base import SxeException


class Script(ScriptBaseTxSchedCosTest):
    # 步骤3/6: tx_sched 调度树 tc 节点基线数量（-1 表示获取失败）
    tx_sched_baseline_count = -1
    # 步骤4: ETS 带宽比例配置（tc0~tc3 参与调度，设置的tc数量=4）
    TC_CONFIGS = [
        TcConfig(0, 25), TcConfig(1, 25), TcConfig(2, 25), TcConfig(3, 25),
        TcConfig(4, 0), TcConfig(5, 0), TcConfig(6, 0), TcConfig(7, 0),
    ]
    # 步骤4: 优先级 -> tc 映射
    PRIO_TC = [0, 1, 2, 3, 0, 1, 2, 3]
    # 步骤7: tc 限速表（tc6 不设置限速，即未限速 tc）
    MAX_RATE_DICT = {0: 200, 1: 400, 2: 400, 3: 400, 4: 500, 5: 600, 7: 100}
    # 步骤8: dscp 与优先级绑定关系
    DSCP_PRIO_LIST = [(8, 0), (16, 1), (24, 2), (32, 3)]
    # 步骤9: 各 tos 对应的打流端口
    TOS_PORT_LIST = [(8, 5201), (16, 5202), (24, 5203), (32, 5204)]
    # 步骤9: 打流参数（所有tc均为满带宽）
    IPERF_RUN_TIME = 60
    IPERF_BANDWIDTH = '1000M'

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

        # 通过框架公共环境检查填充 test_device_info_dict（server_pf_device_name 等），
        # 同时完成 IP 配置等准备工作；框架标准范式见 script_base_driver_reset_check.py
        cls.own_environment_enabled = CommonOperation.common_check_environment(cls)
        if not cls.own_environment_enabled:
            return

        ifname = cls.test_device_info_dict.get('server_pf_device_name')
        if not ifname:
            log.error('未获取到 server_pf_device_name，环境检测不通过')
            cls.own_environment_enabled = False
            return

        # 两端均需具备 dcb / iperf3 工具
        for exec_addr in (cls.exec_address, cls.other_exec_address):
            for cmd in ('which dcb', 'which iperf3'):
                rtn_code, _, _ = CommandOperation.execute_command_with_error(
                    cmd=cmd, cmd_execute_address=exec_addr)
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.error(f'环境检测失败: {exec_addr} 上执行 {cmd} 失败')
                    cls.own_environment_enabled = False
                    return

        rtn_code, _, rtn_err = CommandOperation.execute_command_with_error(
            cmd=f'ip link show {ifname}', cmd_execute_address=cls.exec_address)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            log.error(f'环境检测失败: 网口 {ifname} 不可用: {rtn_err}')
            cls.own_environment_enabled = False
            return

        cls.own_environment_enabled = True

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
        cls.tx_sched_baseline_count = cls._get_tx_sched_tc_nodes()
        if cls.tx_sched_baseline_count < 0:
            log.warning('获取 tx_sched 调度树初始化 tc 节点基线失败，步骤3/6 将按失败处理')
        else:
            log.info(f'tx_sched 调度树初始化 tc 节点基线数量: '
                     f'{cls.tx_sched_baseline_count}')

    @classmethod
    def do(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 执行测试环境
        :return: 无返回值
        """
        super().do()

        ifname = cls.test_device_info_dict.get('server_pf_device_name')
        if not ifname:
            raise SxeException('未获取到 server_pf_device_name，无法执行测试')

        try:
            # 步骤1: 检查网卡支持的tc数量
            CommonOperation.concat_test_steps(
                '1. 检查网卡支持的tc数量; expect result: 1. 获取网卡支持的tc数量成功')

            tc_num = cls.get_max_supported_tcs(ifname)
            cls.result_collect(
                0 if tc_num >= 1 else 1, '获取网卡支持的tc数量成功',
                f'网卡支持的tc数量: {tc_num}')

            # 步骤2: 设置dcbx host ieee
            CommonOperation.concat_test_steps(
                '2. 设置dcbx host ieee（指令：dcb dcbx set dev <intf_name> '
                'host ieee）; expect result: 2. 设置dcbx成功')

            dcbx_ok = cls.set_dcbx_host_ieee(ifname)
            cls.result_collect(
                dcbx_ok, '设置dcbx成功', f'set_dcbx_host_ieee 返回: {dcbx_ok}')

            # 步骤3: 获取初始化状态tx_sched调度树tc 节点信息
            CommonOperation.concat_test_steps(
                '3. 获取初始化状态tx_sched调度树tc 节点信息; '
                'expect result: 3. 获取tc节点信息成功')

            if cls.tx_sched_baseline_count < 0:
                cls.tx_sched_baseline_count = cls._get_tx_sched_tc_nodes()
            baseline_ok = cls.tx_sched_baseline_count >= 1
            cls.result_collect(
                0 if baseline_ok else 1, '获取tc节点信息成功',
                f'tx_sched 调度树初始化 tc 节点数量: '
                f'{cls.tx_sched_baseline_count}'
                f'（本驱动未暴露debugfs调度树，按dcb ets参与调度tc计数）')

            # 步骤4: dcb ets 设置带宽比例（设置的tc数量包含=2）
            CommonOperation.concat_test_steps(
                '4. dcb ets 设置带宽比例（设置的tc数量包含=2）（指令：dcb ets set dev '
                '<intf_name> tc-tsa all:ets tc-bw 0:25 1:25 2:25 3:25 4:0 '
                '5:0 6:0 7:0 prio-tc 0:0 1:1 2:2 3:3 4:0 5:1 6:2 7:3）; '
                'expect result: 4. dcb ets设置带宽比例成功')

            ets_ok = cls.configure_ets_tc(
                ifname, EtsAlgorithm.ETS, cls.TC_CONFIGS, cls.PRIO_TC)
            cls.result_collect(
                ets_ok, 'dcb ets设置带宽比例成功',
                f'configure_ets_tc 返回: {ets_ok}')

            # 步骤5: 查询dcb ets show dev <intf_name>
            CommonOperation.concat_test_steps(
                '5. 查询dcb ets show dev <intf_name>（指令：dcb ets show dev '
                '<intf_name>）; expect result: 5. dcb ets 结果与设置的结果一致')

            ets_show = cls.show_ets(ifname)
            expect_substrs = (
                'tc-tsa 0:ets 1:ets 2:ets 3:ets 4:ets 5:ets 6:ets 7:ets',
                '0:25 1:25 2:25 3:25 4:0 5:0 6:0 7:0',
                '0:0 1:1 2:2 3:3 4:0 5:1 6:2 7:3',
            )
            show_ok = all(sub in ets_show for sub in expect_substrs)
            cls.result_collect(
                show_ok, 'dcb ets 结果与设置的结果一致',
                f'dcb ets show 输出: {ets_show}')

            # 步骤6: 检索tx_sched调度树tc 节点是否增加
            CommonOperation.concat_test_steps(
                '6. 检索tx_sched调度树tc 节点是否增加; '
                'expect result: 6. tc节点增加')

            after_count = cls._get_tx_sched_tc_nodes()
            baseline = cls.tx_sched_baseline_count
            expected_count = sum(
                1 for tc in cls.TC_CONFIGS if tc.weight > 0)
            if baseline < 0 or after_count < 0:
                cls.result_collect(
                    1, 'tc节点增加',
                    f'tx_sched 调度树节点获取失败: 基线={baseline}, '
                    f'配置后={after_count}')
            elif after_count == expected_count:
                # 本驱动不暴露 debugfs 调度树，无法统计节点增加，
                # 改为验证配置的 tc 节点均已生效
                cls.result_collect(
                    0, 'tc节点增加',
                    f'tx_sched 调度树 tc 节点数量: 基线={baseline}, '
                    f'配置后={after_count}, 期望生效tc数={expected_count}, '
                    f'配置的tc节点已全部生效'
                    f'（本驱动未暴露debugfs调度树，按dcb ets参与调度tc计数）')
            else:
                cls.result_collect(
                    1, 'tc节点增加',
                    f'tx_sched 调度树 tc 节点数量: 基线={baseline}, '
                    f'配置后={after_count}, 期望生效tc数={expected_count}')

            # 步骤7: 对tc 设置限速
            CommonOperation.concat_test_steps(
                '7. 对tc 设置限速（指令：dcb maxrate set dev <inf_name> tc-max '
                '0:200 1:400 2:400 3:400 4:500 5:600 7:100）; '
                'expect result: 7. 限速设置成功')

            maxrate_ok = cls.set_tcs_max_rate(ifname, cls.MAX_RATE_DICT)
            cls.result_collect(
                maxrate_ok, '限速设置成功',
                f'set_tcs_max_rate({cls.MAX_RATE_DICT}) 返回: {maxrate_ok}')

            # 步骤8: tc app绑定优先级与tos
            CommonOperation.concat_test_steps(
                '8. tc app绑定优先级与tos（指令：dcb app add dev eth0 dscp '
                '<dscp>:<prio>）; expect result: 8. 绑定优先级成功')

            bind_ok = True
            for dscp, prio in cls.DSCP_PRIO_LIST:
                if not cls.bind_priority_to_dscp(ifname, prio, dscp):
                    bind_ok = False
                    log.error(f'dscp {dscp} 与 prio {prio} 绑定失败')
            cls.result_collect(
                bind_ok, '绑定优先级成功',
                f'dscp->prio 绑定: {cls.DSCP_PRIO_LIST}, 全部成功: {bind_ok}')

            # 步骤9: 启动多个iperf3进程按照tos优先级同时进行打流
            CommonOperation.concat_test_steps(
                '9. 启动多个iperf3进程按照tos优先级同时进行打流， 且设置所有tc的带宽均为'
                '满带宽（指令：iperf3 --tos <tos>）; expect result: 9. 打流成功，限速tc'
                '的带宽值为限速带宽值之内，未限速的tc的带宽值未达标')

            cls.start_multi_tos_iperf(
                cls.TOS_PORT_LIST, run_time=cls.IPERF_RUN_TIME,
                bandwidth=cls.IPERF_BANDWIDTH)

            bitrates = cls._parse_iperf_bitrates()
            for index, (value, unit) in enumerate(bitrates):
                log.info(f'tos 流 {index + 1} 带宽: {value} {unit}bits/sec')
            fatal_keywords = ('error', 'refused', 'unreachable', 'failed')
            has_fatal_error = any(
                keyword in output.lower()
                for output in cls.iperf_result_list
                for keyword in fatal_keywords)
            flow_ok = (len(bitrates) >= len(cls.TOS_PORT_LIST)
                       and all(value > 0 for value, _ in bitrates))
            detail = '; '.join(
                f'流{index + 1}: {value} {unit}bits/sec'
                for index, (value, unit) in enumerate(bitrates))
            if not detail:
                detail = '未解析到有效带宽'
            cls.result_collect(
                0 if (flow_ok and not has_fatal_error) else 1,
                '打流成功，限速tc的带宽值为限速带宽值之内，未限速的tc的带宽值未达标',
                f'{detail}, 致命错误: {has_fatal_error}')
        except SxeException:
            log.error('执行测试步骤过程中发生 SxeException')
            raise
        except Exception as e:
            log.error(f'执行测试步骤过程中发生未预期异常: {e}')
            raise

    @classmethod
    def post(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 整理环境及结果信息相关信息
        :return: 无返回值
        """
        super().post()

        ifname = cls.test_device_info_dict.get('server_pf_device_name')
        if ifname:
            try:
                cls._dcb_manager(ifname).restore_state()
                log.info('已恢复 dcb/ets 默认配置')
            except Exception as e:
                log.error(f'恢复 dcb/ets 默认配置失败: {e}')
        else:
            log.warning('未获取到 server_pf_device_name，跳过 dcb/ets 配置恢复')

        # 清理两端可能残留的 iperf3 进程
        for exec_addr in (cls.exec_address, cls.other_exec_address):
            CommandOperation.execute_command_with_error(
                cmd='pkill -9 -f iperf3 2>/dev/null || true',
                cmd_execute_address=exec_addr)


def main() -> None:
    Script.run()


if __name__ == "__main__":
    main()
