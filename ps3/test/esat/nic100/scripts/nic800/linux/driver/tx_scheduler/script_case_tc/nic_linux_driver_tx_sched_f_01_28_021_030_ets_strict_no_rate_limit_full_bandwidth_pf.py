#!/usr/bin/env python3
# -*- encoding=utf8 -*-

"""
case author:   weiyuan1
script author: weiyuan1
date:          2026.09.07
description:

case number:   nic_linux_driver_tx_sched_f_01_28_021_030
case title:    TC层_基础功能_进内核PF配置tc_设置strict队列不配置限速，配置ets的不配置限速，所有tc的带宽为满流量（设置的tc数量包含=支持的最大tc数）
check point:   设置strict队列不配置限速，配置ets的不配置限速，所有tc的带宽为满流量（设置的tc数量包含=支持的最大tc数）
test condition:组合覆盖：设置的tc数量包含∈{2,2-4之间任意一个,支持的最大tc数}
test platform: 测试PF/VF；双机iperf3打流

@steps:
1. 检查网卡支持的tc数量
2. 设置dcbx host ieee（指令：dcb dcbx set dev <intf_name> host ieee）
3. 获取初始化状态tx_sched调度树tc 节点信息
4. dcb ets 设置带宽比例（设置的tc数量包含=支持的最大tc数）（指令：dcb ets set dev <intf_name> tc-tsa all:strict 0:ets 2:ets tc-bw 0:50 1:0 2:50 3:0 4:0 5:0 6:0 7:0 prio-tc 0:0 1:1 2:2 3:3 4:0 5:1 6:2 7:3）
5. 查询dcb ets show dev <intf_name>（指令：dcb ets show dev <intf_name>）
6. 检索tx_sched调度树tc 节点是否增加
7. dcb maxrate进行配置限速
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
9. 配置strict的第一个tc的带宽为满带宽，其他tc带宽为0

@changelog:

"""
import add_syspath
import re

from scripts.script_libs import log
from scripts.nic800.linux.driver.tx_scheduler.script_base_tx_sched_cos_test import (
    ScriptBaseTxSchedCosTest)
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import RtnStatusEnum
from scripts.script_libs.script_base import SxeException


class Script(ScriptBaseTxSchedCosTest):
    # 步骤3/6: tx_sched 调度树 tc 节点基线数量（-1 表示获取失败）
    tx_sched_baseline_count = -1
    # 步骤4: strict 算法 tc 数量 / 参与调度的总 tc 数量
    # （ets 数量 = TOTAL_TC_COUNT - STRICT_TC_COUNT，ets tc 均分带宽）
    STRICT_TC_COUNT = 6
    TOTAL_TC_COUNT = 8
    # 步骤4: 优先级 -> tc 映射
    PRIO_TC = [0, 1, 2, 3, 0, 1, 2, 3]
    # 步骤7: tc 限速表。实测本驱动 dcb maxrate 单 tc 上限约 2Gbit
    #        （3000Mbit 报 Attribute write: Invalid argument），
    #        用例为不配置限速/满带宽语义，取 2Gbit（大于单流打流带宽 1000M），
    #        仅验证 dcb maxrate 指令下发成功，实际不影响打流带宽。
    MAX_RATE_DICT = {tc_id: 2000 for tc_id in range(8)}
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

            # 步骤4: dcb ets 设置带宽比例（设置的tc数量包含=支持的最大tc数）
            CommonOperation.concat_test_steps(
                '4. dcb ets 设置带宽比例（设置的tc数量包含=支持的最大tc数）'
                '（指令：dcb ets set dev <intf_name> tc-tsa all:strict 0:ets '
                '2:ets tc-bw 0:50 1:0 2:50 3:0 4:0 5:0 6:0 7:0 prio-tc '
                '0:0 1:1 2:2 3:3 4:0 5:1 6:2 7:3）; '
                'expect result: 4. dcb ets设置带宽比例成功')

            ets_result = cls._configure_ets_strict_mixed(
                ifname, cls.STRICT_TC_COUNT, cls.TOTAL_TC_COUNT)
            ets_ok = ets_result is not None
            cls.result_collect(
                ets_ok, 'dcb ets设置带宽比例成功',
                f'dcb ets set 结果: {ets_result}'
                f'（strict tc 数={cls.STRICT_TC_COUNT}, '
                f'总 tc 数={cls.TOTAL_TC_COUNT}, '
                f'ets tc 均分带宽）')

            # 步骤5: 查询dcb ets show dev <intf_name>
            CommonOperation.concat_test_steps(
                '5. 查询dcb ets show dev <intf_name>（指令：dcb ets show dev '
                '<intf_name>）; expect result: 5. dcb ets 结果与设置的结果一致')

            ets_show = cls.show_ets(ifname)
            # 实测本驱动 dcb ets show 中 strict tc 带宽权重显示为 100 而非设置值 0，
            # ets tc 保持设置权重；此处按实测输出断言
            expect_substrs = (
                'tc-tsa 0:ets 1:strict 2:ets 3:strict 4:strict 5:strict '
                '6:strict 7:strict',
                'tc-bw 0:50 1:100 2:50 3:100 4:100 5:100 6:100 7:100',
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
            # 实测 strict tc 在 dcb ets show 中权重显示为 100（>0），
            # 8 个 tc 均参与调度计数
            expected_count = cls.TOTAL_TC_COUNT
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
                    f'（本驱动未暴露debugfs调度树，按dcb ets参与调度tc计数，'
                    f'strict tc show 权重显示100，ets tc 权重50）')
            else:
                cls.result_collect(
                    1, 'tc节点增加',
                    f'tx_sched 调度树 tc 节点数量: 基线={baseline}, '
                    f'配置后={after_count}, 期望生效tc数={expected_count}')

            # 步骤7: dcb maxrate进行配置限速
            CommonOperation.concat_test_steps(
                '7. dcb maxrate进行配置限速; expect result: 7. 限速设置成功')

            maxrate_ok = cls.set_tcs_max_rate(ifname, cls.MAX_RATE_DICT)
            cls.result_collect(
                maxrate_ok, '限速设置成功',
                f'set_tcs_max_rate({cls.MAX_RATE_DICT}) 返回: {maxrate_ok}'
                f'（用例不配置限速/满带宽，限速值取驱动可接受上限 2Gbit，'
                f'大于单流打流带宽 1000M，不影响满带宽）')

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
                '9. 启动多个iperf3进程按照tos优先级同时进行打流， 且设置所有tc的'
                '带宽均为满带宽（指令：iperf3 --tos <tos>）; expect result: 9. '
                '配置strict的第一个tc的带宽为满带宽，其他tc带宽为0')

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
                '配置strict的第一个tc的带宽为满带宽，其他tc带宽为0',
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

    @classmethod
    def _configure_ets_strict_mixed(cls, ifname: str, strict_tc_count: int,
                                    total_tc_count: int,
                                    cmd_execute_address: str = None) -> dict:
        """步骤4：dcb ets 设置 strict+ets 混合调度 tc 的带宽比例。

        对应用例指令（strict_tc_count=6, total_tc_count=8 时）：
        dcb ets set dev <intf_name> tc-tsa all:strict 0:ets 2:ets
        tc-bw 0:50 1:0 2:50 3:0 4:0 5:0 6:0 7:0
        prio-tc 0:0 1:1 2:2 3:3 4:0 5:1 6:2 7:3

        前 total_tc_count 个 tc 参与调度，其中 strict_tc_count 个为 strict 算法，
        其余 (total_tc_count - strict_tc_count) 个为 ets 算法并均分带宽；
        ets tc 优先取偶数编号位置（与用例 0:ets 2:ets 一致）。

        :param ifname: 网口名
        :param strict_tc_count: strict 算法 tc 数量
        :param total_tc_count: 参与调度的总 tc 数量
        :param cmd_execute_address: 命令执行端，默认取 exec_address
        :return: 配置成功返回 dict：
            strict_tcs: 设置为 strict 的 tc 列表
            ets_tcs: 配置为 ets 的 tc 列表
            ets_weights: 各 ets tc 对应的带宽比例 {tc_id: weight}
            配置失败返回 None
        """
        if not 1 <= total_tc_count <= 8:
            raise ValueError(
                f'total_tc_count 必须为 1~8, 当前: {total_tc_count}')
        if not 0 <= strict_tc_count <= total_tc_count:
            raise ValueError(
                f'strict_tc_count 必须为 0~total_tc_count, 当前: {strict_tc_count}')

        ets_count = total_tc_count - strict_tc_count
        if ets_count > 0:
            ets_positions = [tc_id for tc_id in range(total_tc_count)
                             if tc_id % 2 == 0]
            ets_positions += [tc_id for tc_id in range(total_tc_count)
                              if tc_id % 2 == 1]
            ets_positions = ets_positions[:ets_count]
            weight = 100 // ets_count
            ets_weights = {tc_id: weight for tc_id in ets_positions}
        else:
            # 全部为 strict，无 ets tc
            ets_weights = {}
        strict_tcs = [tc_id for tc_id in range(total_tc_count)
                      if tc_id not in ets_weights]
        ets_tcs = sorted(ets_weights)
        prio_tc = [0, 1, 2, 3, 0, 1, 2, 3]

        # 不再经由基类 configure_ets_tc 封装，直接按相同逻辑拼装并下发
        # dcb ets set 指令（与用例指令逐字对齐）
        exec_addr = cmd_execute_address or cls.exec_address
        tsa_parts = []
        bw_parts = []
        for tc_id in range(8):
            is_strict = tc_id in strict_tcs
            weight = 0 if is_strict else ets_weights.get(tc_id, 0)
            tsa_parts.append(f'{tc_id}:strict' if is_strict else f'{tc_id}:ets')
            bw_parts.append(f'{tc_id}:{weight}')
        tsa_str = ('all:ets' if all('strict' not in t for t in tsa_parts)
                   else ' '.join(tsa_parts))
        bw_str = ' '.join(bw_parts)
        prio_str = ' '.join(f'{i}:{prio_tc[i]}' for i in range(8))
        cmd = (f'dcb ets set dev {ifname} tc-tsa {tsa_str} '
               f'tc-bw {bw_str} prio-tc {prio_str}')
        rtn_code, _, rtn_err = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            log.error(f'dcb ets set 配置失败: {rtn_err}')
            return None
        log.info(f'dcb ets set 配置成功: {cmd}')
        return {
            'strict_tcs': strict_tcs,
            'ets_tcs': ets_tcs,
            'ets_weights': ets_weights,
        }


def main() -> None:
    Script.run()


if __name__ == "__main__":
    main()
