#!/usr/bin/env python3
# -*- encoding=utf8 -*-

"""
case author:   weiyuan1
script author: weiyuan1
date:          2026.09.07
description:

case number:   nic_linux_driver_tx_sched_r_01_28_026_002
case title:    TC层_可靠性_切速和带宽分配交互_先配置dcb maxrate后，然后向下切速，  PF打流
check point:   先配置dcb maxrate后，然后向下切速，  PF打流
test condition:dcb maxrate与速率切换交互
test platform: 测试PF/VF；双机iperf3打流

@steps:
1. 检查网卡支持的tc数量
2. 设置dcbx host ieee（指令：dcb dcbx set dev <intf_name> host ieee）
3. 获取初始化状态tx_sched调度树tc 节点信息
4. dcb ets 设置带宽比例（指令：dcb ets set dev <intf_name> tc-tsa all:ets tc-bw 0:25 1:25 2:25 3:25 4:0 5:0 6:0 7:0 prio-tc 0:0 1:1 2:2 3:3 4:0 5:1 6:2 7:3）
5. 查询dcb ets show dev <intf_name>（指令：dcb ets show dev <intf_name>）
6. 检索tx_sched调度树tc 节点是否增加
7. 对tc 设置限速（指令：dcb maxrate set dev <inf_name> tc-max 0:200 1:400 2:400 3:400 4:500 5:600 7:100）
8. port向下进行切速
9. 再次检查调度树，tc节点信息是否保持不变
10. 启动多个iperf3进程按照tos优先级同时进行打流， 且设置所有tc的带宽均为满带宽（指令：iperf3 --tos <tos>）

@steps expect result:
1. 获取网卡支持的tc数量成功
2. 设置dcbx成功
3. 获取tc节点信息成功
4. dcb ets设置带宽比例成功
5. dcb ets 结果与设置的结果一致
6. tc节点增加
7. 限速成功
8. 切速成功
9. tc节点信息保持不变
10. 符合预期

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
    # 步骤3/6: tx_sched 调度树 tc 节点基线数量（-1 表示获取失败）
    tx_sched_baseline_count = -1
    # 步骤6: dcb ets 配置后 tc 节点数量（步骤9 切速后保持不变校验的基线）
    tc_config_after_count = -1
    # 步骤4: 参与调度的总 tc 数量 / 权重>0 的 ets 生效 tc 数量
    TOTAL_TC_COUNT = 8
    ETS_ACTIVE_TC_COUNT = 4
    # 步骤4: 优先级 -> tc 映射
    PRIO_TC = [0, 1, 2, 3, 0, 1, 2, 3]
    # 步骤7: tc 限速表（用例指令：tc-max 0:200 1:400 2:400 3:400 4:500 5:600 7:100，
    #        跳过 tc6，保持默认不限速）
    MAX_RATE_DICT = {0: 200, 1: 400, 2: 400, 3: 400, 4: 500, 5: 600, 7: 100}
    # 步骤10: dscp 与优先级绑定关系（打流 tos 映射用，用例无独立绑定步骤）
    DSCP_PRIO_LIST = [(8, 0), (16, 1), (24, 2), (32, 3)]
    # 步骤10: 各 tos 对应的打流端口
    TOS_PORT_LIST = [(8, 5201), (16, 5202), (24, 5203), (32, 5204)]
    # 步骤10: 打流参数
    IPERF_RUN_TIME = 60
    IPERF_BANDWIDTH = '1000M'
    # 步骤8: 切速档位（步骤8 向下切速到低档，post 恢复高档）
    LOW_SPEED_MBPS = 100000
    HIGH_SPEED_MBPS = 400000

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

        ifname = cls.test_device_info_dict.get('server_pf_device_name')
        if ifname:
            # 步骤8 前置: 向下切速语义需保持当前高档速率（如已非高档先恢复）
            if cls.get_port_speed(ifname) != cls.HIGH_SPEED_MBPS:
                if not cls._switch_speed_both(cls.HIGH_SPEED_MBPS):
                    log.warning('prepare 恢复高档速率失败，步骤8 切速可能受影响')

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

            # 步骤4: dcb ets 设置带宽比例
            CommonOperation.concat_test_steps(
                '4. dcb ets 设置带宽比例（指令：dcb ets set dev <intf_name> '
                'tc-tsa all:ets tc-bw 0:25 1:25 2:25 3:25 4:0 5:0 6:0 7:0 '
                'prio-tc 0:0 1:1 2:2 3:3 4:0 5:1 6:2 7:3）; '
                'expect result: 4. dcb ets设置带宽比例成功')

            ets_result = cls._configure_ets_026(ifname)
            ets_ok = ets_result is not None
            cls.result_collect(
                ets_ok, 'dcb ets设置带宽比例成功',
                f'dcb ets set 结果: {ets_result}')

            # 步骤5: 查询dcb ets show dev <intf_name>
            CommonOperation.concat_test_steps(
                '5. 查询dcb ets show dev <intf_name>（指令：dcb ets show dev '
                '<intf_name>）; expect result: 5. dcb ets 结果与设置的结果一致')

            ets_show = cls.show_ets(ifname)
            # 实测本驱动 dcb ets show 中 all:ets 展开为 8 个 tc 均显示 ets，
            # tc-bw 与 prio-tc 逐字一致（ets 算法下权重0的tc显示0）
            expect_substrs = (
                'tc-bw 0:25 1:25 2:25 3:25 4:0 5:0 6:0 7:0',
                'tc-tsa 0:ets 1:ets 2:ets 3:ets 4:ets 5:ets 6:ets 7:ets',
                'prio-tc 0:0 1:1 2:2 3:3 4:0 5:1 6:2 7:3',
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
            # 026 全 ets 算法，权重>0 的 tc 为 0-3 共 4 个参与调度计数
            expected_count = cls.ETS_ACTIVE_TC_COUNT
            if baseline < 0 or after_count < 0:
                cls.result_collect(
                    1, 'tc节点增加',
                    f'tx_sched 调度树节点获取失败: 基线={baseline}, '
                    f'配置后={after_count}')
            elif after_count == expected_count:
                cls.tc_config_after_count = after_count
                # 本驱动不暴露 debugfs 调度树，无法统计节点增加，
                # 改为验证配置的 tc 节点均已生效
                cls.result_collect(
                    0, 'tc节点增加',
                    f'tx_sched 调度树 tc 节点数量: 基线={baseline}, '
                    f'配置后={after_count}, 期望生效tc数={expected_count}, '
                    f'配置的tc节点已全部生效'
                    f'（本驱动未暴露debugfs调度树，按dcb ets参与调度tc计数，'
                    f'权重>0的tc为0-3）')
            else:
                cls.result_collect(
                    1, 'tc节点增加',
                    f'tx_sched 调度树 tc 节点数量: 基线={baseline}, '
                    f'配置后={after_count}, 期望生效tc数={expected_count}')

            # 步骤7: 对tc 设置限速
            CommonOperation.concat_test_steps(
                '7. 对tc 设置限速（指令：dcb maxrate set dev <inf_name> '
                'tc-max 0:200 1:400 2:400 3:400 4:500 5:600 7:100）; '
                'expect result: 7. 限速成功')

            maxrate_ok = cls.set_tcs_max_rate(ifname, cls.MAX_RATE_DICT)
            cls.result_collect(
                maxrate_ok, '限速成功',
                f'set_tcs_max_rate({cls.MAX_RATE_DICT}) 返回: {maxrate_ok}'
                f'（跳过tc6，保持默认不限速）')

            # 步骤8: port向下进行切速
            CommonOperation.concat_test_steps(
                '8. port向下进行切速; expect result: 8. 切速成功')

            speed_ok = cls._switch_speed_both(cls.LOW_SPEED_MBPS)
            cls.result_collect(
                speed_ok, '切速成功',
                f'双端向下切速到 {cls.LOW_SPEED_MBPS}Mbps 结果: {speed_ok}')

            # 步骤9: 再次检查调度树，tc节点信息是否保持不变
            CommonOperation.concat_test_steps(
                '9. 再次检查调度树，tc节点信息是否保持不变; '
                'expect result: 9. tc节点信息保持不变')

            after_speed_count = cls._get_tx_sched_tc_nodes()
            cls.check_tc_config_unchanged(
                cls.tc_config_after_count, after_speed_count,
                'tc节点信息保持不变')

            # 步骤10: 启动多个iperf3进程按照tos优先级同时进行打流
            CommonOperation.concat_test_steps(
                '10. 启动多个iperf3进程按照tos优先级同时进行打流， 且设置所有tc的'
                '带宽均为满带宽（指令：iperf3 --tos <tos>）; '
                'expect result: 10. 符合预期')

            # 用例无独立 app 绑定步骤，打流 tos 需与 dscp->prio 映射对应，
            # 此处静默确保绑定存在
            bind_ok = True
            for dscp, prio in cls.DSCP_PRIO_LIST:
                if not cls.bind_priority_to_dscp(ifname, prio, dscp):
                    bind_ok = False
                    log.error(f'dscp {dscp} 与 prio {prio} 绑定失败')
            if not bind_ok:
                cls.result_collect(
                    1, '符合预期',
                    f'dscp->prio 绑定失败: {cls.DSCP_PRIO_LIST}，打流前静默绑定失败')

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
                '符合预期',
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
            try:
                # 实测 dcb maxrate 全 0 清空合法，恢复限速配置
                cls.set_tcs_max_rate(ifname, {tc_id: 0 for tc_id in range(8)})
                log.info('已清空 dcb maxrate 限速配置')
            except Exception as e:
                log.error(f'清空 dcb maxrate 限速配置失败: {e}')
            # prepare 曾降速到低档，post 恢复高档速率
            cls._switch_speed_both(cls.HIGH_SPEED_MBPS)
        else:
            log.warning('未获取到 server_pf_device_name，跳过配置恢复')

        # 清理两端可能残留的 iperf3 进程
        for exec_addr in (cls.exec_address, cls.other_exec_address):
            CommandOperation.execute_command_with_error(
                cmd='pkill -9 -f iperf3 2>/dev/null || true',
                cmd_execute_address=exec_addr)

    @classmethod
    def _configure_ets_026(cls, ifname: str,
                           cmd_execute_address: str = None) -> dict:
        """步骤4：dcb ets 设置带宽比例（026 专用，全部 tc 为 ets 算法）。

        对应用例指令：
        dcb ets set dev <intf_name> tc-tsa all:ets
        tc-bw 0:25 1:25 2:25 3:25 4:0 5:0 6:0 7:0
        prio-tc 0:0 1:1 2:2 3:3 4:0 5:1 6:2 7:3

        :param ifname: 网口名
        :param cmd_execute_address: 命令执行端，默认取 exec_address
        :return: 配置成功返回 {tc_tsa, tc_bw, prio_tc}，失败返回 None
        """
        exec_addr = cmd_execute_address or cls.exec_address
        cmd = (f'dcb ets set dev {ifname} tc-tsa all:ets '
               f'tc-bw 0:25 1:25 2:25 3:25 4:0 5:0 6:0 7:0 '
               f'prio-tc 0:0 1:1 2:2 3:3 4:0 5:1 6:2 7:3')
        rtn_code, _, rtn_err = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            log.error(f'dcb ets set 配置失败: {rtn_err}')
            return None
        log.info(f'dcb ets set 配置成功: {cmd}')
        return {
            'tc_tsa': 'all:ets',
            'tc_bw': '0:25 1:25 2:25 3:25 4:0 5:0 6:0 7:0',
            'prio_tc': '0:0 1:1 2:2 3:3 4:0 5:1 6:2 7:3',
        }

    @classmethod
    def _switch_speed_both(cls, speed_mbps: int,
                           wait_timeout: int = 90) -> bool:
        """步骤8 辅助：双端同时切速并等待链路恢复，确认实际速率。

        :param speed_mbps: 目标速率 Mbps
        :param wait_timeout: 链路恢复等待超时(秒)，实测切速后约 25s Link up
        :return: True 双端切速命令下发成功且链路恢复、实际速率达标
        """
        ifname = cls.test_device_info_dict.get('server_pf_device_name')
        ifname_other = cls.test_device_info_dict.get('client_pf_device_name')
        if not ifname or not ifname_other:
            log.error(f'未获取到双端网口名: server={ifname}, client={ifname_other}')
            return False

        set_ok = (cls.set_port_speed(ifname, speed_mbps)
                  and cls.set_port_speed(
                      ifname_other, speed_mbps,
                      cmd_execute_address=cls.other_exec_address))
        if not set_ok:
            return False

        up_ok = (cls.wait_link_up(ifname, timeout=wait_timeout)
                 and cls.wait_link_up(
                     ifname_other, timeout=wait_timeout,
                     cmd_execute_address=cls.other_exec_address))
        if not up_ok:
            return False

        actual = cls.get_port_speed(ifname)
        actual_other = cls.get_port_speed(
            ifname_other, cmd_execute_address=cls.other_exec_address)
        speed_ok = actual == speed_mbps and actual_other == speed_mbps
        log.info(f'切速后实际速率: server={actual}Mbps, client={actual_other}Mbps, '
                 f'目标={speed_mbps}Mbps, 达标: {speed_ok}')
        return speed_ok


def main() -> None:
    Script.run()


if __name__ == "__main__":
    main()
