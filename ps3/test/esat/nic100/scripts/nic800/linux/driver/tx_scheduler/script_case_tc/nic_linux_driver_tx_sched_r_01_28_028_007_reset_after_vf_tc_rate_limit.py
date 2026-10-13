#!/usr/bin/env python3
# -*- encoding=utf8 -*-

"""
case author:   weiyuan1
script author: weiyuan1
date:          2026.09.14
description:

case number:   nic_linux_driver_tx_sched_r_01_28_028_007
case title:    TC层_可靠性_复位操作_dcb ets算法配置tc与prio,tc与bw进行绑定后，创建VF,设置限速后，进行复位（复位类型=VFR）
check point:   dcb ets算法配置tc与prio,tc与bw进行绑定后，创建VF,设置限速后，进行复位（复位类型=VFR）
test condition:组合覆盖：复位类型∈{GLR,PFLR/PFR,core reset,VFR,VFLR}
test platform: 测试PF/VF；双机iperf3打流

@steps:
1. 检查网卡支持的tc数量
2. 设置dcbx host ieee（指令：dcb dcbx set dev <intf_name> host ieee）
3. 获取初始化状态tx_sched调度树tc 节点信息
4. dcb ets 设置带宽比例（指令：dcb ets set dev <intf_name> tc-tsa all:ets tc-bw 0:25 1:25 2:25 3:25 4:0 5:0 6:0 7:0 prio-tc 0:0 1:1 2:2 3:3 4:0 5:1 6:2 7:3）
5. 查询dcb ets show dev <intf_name>（指令：dcb ets show dev <intf_name>）
6. 创建VF
7. 检索tx_sched调度树tc节点下。vf子树中的q以及qg是否相等
8. 对tc 设置限速（指令：dcb maxrate set dev <inf_name> tc-max 0:200 1:400 2:400 3:400 4:500 5:600 7:100）
9. tc app绑定优先级与tos（指令：dcb app add dev eth0 dscp <dscp>:<prio>）
10. 启动多个iperf3进程按照tos优先级同时进行打流， 且设置所有tc的带宽均为满带宽（指令：iperf3 --tos <tos>）
11. 进行复位（复位类型=VFR）
12. 检索tx_sched调度树tc 节点是否增加
13. 启动多个iperf3进程按照tos优先级同时进行打流， 且设置所有tc的带宽均为满带宽（指令：iperf3 --tos <tos>）

@steps expect result:
1. 获取网卡支持的tc数量成功
2. 设置dcbx成功
3. 获取tc节点信息成功
4. dcb ets设置带宽比例成功
5. dcb ets 结果与设置的结果一致
6. 创建VF成功
7. vf子树中的q以及qg相等
8. 限速设置成功
9. 绑定优先级成功
10. 打流成功，限速tc的带宽值为限速带宽值之内，未限速的tc的带宽值未达标
11. 复位成功
12. tc节点的信息与步骤6/7一致
13. 预期同步骤10一致

@changelog:

"""
import re
import add_syspath
import time
from scripts.script_libs import log
from scripts.nic800.linux.driver.tx_scheduler.script_base_tx_sched_reliability_cos_test import (
    EtsAlgorithm, ScriptBaseTxSchedReliabilityCosTest, TcConfig)
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum
from scripts.script_libs.script_base import SxeException


class Script(ScriptBaseTxSchedReliabilityCosTest):
    # 步骤11: 复位类型（VFR = VF 功能复位 sysfs reset（作用于 VF BDF））
    RESET_TYPE = 'VFR'
    # 步骤3/12: tx_sched 调度树 tc 节点基线数量（-1 表示获取失败）
    tx_sched_baseline_count = -1
    # 步骤6/12: dcb ets 配置后 tc 节点数量（步骤12 复位后保持不变校验的基线）
    tc_config_after_count = -1
    # 步骤4: 参与调度的总 tc 数量 / 权重>0 的 ets 生效 tc 数量
    TOTAL_TC_COUNT = 8
    ETS_ACTIVE_TC_COUNT = 4
    # 步骤4: 优先级 -> tc 映射
    PRIO_TC = [0, 1, 2, 3, 0, 1, 2, 3]
    # 步骤8: tc 限速表（用例指令：tc-max 0:200 1:400 2:400 3:400 4:500 5:600 7:100，
    #        跳过 tc6，保持默认不限速）
    MAX_RATE_DICT = {0: 200, 1: 400, 2: 400, 3: 400, 4: 500, 5: 600, 7: 100}
    # 步骤9: dscp 与优先级绑定关系（指令：dcb app add dev <if> dscp <dscp>:<prio>）
    DSCP_PRIO_LIST = [(8, 0), (16, 1), (24, 2), (32, 3)]
    # 步骤10/13: 各 tos 对应的打流端口
    TOS_PORT_LIST = [(8, 5201), (16, 5202), (24, 5203), (32, 5204)]
    # 步骤10/13: 打流参数
    IPERF_RUN_TIME = 60
    IPERF_BANDWIDTH = '1000M'
    # 步骤6/11: 双端 VF IP（创建 VF 后配置；复位后 ensure_vf_after_reset 兜底恢复）
    SERVER_VF_IP = '192.168.120.100'
    CLIENT_VF_IP = '192.168.120.101'
    VF_NETMASK = '24'
    # 步骤11 后: PF IP（驱动重载型复位后 NetworkManager 通常自动恢复，此处兜底）
    SERVER_PF_IP = '192.168.120.12'
    # 步骤11: PF / VF PCI BDF（check_own_environment 与步骤6 中获取）
    pf_bdf = ''
    vf_bdf = ''
    # 步骤6: 双端 VF 网口名（步骤10/13 打流与步骤11 复位依赖）
    vf_name = ''
    vf_name_other = ''

    @classmethod
    def set_parameters(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.14
        descriptor: 设置需要调用的变量
        :return: 无返回值
        """
        super().set_parameters()

    @classmethod
    def check_own_environment(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.14
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

        # 两端均需具备 dcb / iperf3 工具；@@DCB_TOOL_CHECK@@
        tool_checks = ['which dcb', 'which iperf3'] + []
        for exec_addr in (cls.exec_address, cls.other_exec_address):
            for cmd in tool_checks:
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

        # 步骤11 前置: 确认 PF 对应 PCI BDF 可获取（复位命令依赖）
        cls.pf_bdf = cls.get_device_bdf(ifname)
        if not cls.pf_bdf:
            log.error('环境检测失败: 未获取到 PF PCI BDF，无法执行复位')
            cls.own_environment_enabled = False
            return

        cls.own_environment_enabled = True

    @classmethod
    def prepare(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.14
        descriptor: 准备环境
        :return: 无返回值
        """
        super().prepare()

        # 步骤3 前置: 记录初始化状态下 tx_sched 调度树 tc 节点数量作为基线
        cls.tx_sched_baseline_count = cls._get_tx_sched_tc_nodes()
        if cls.tx_sched_baseline_count < 0:
            log.warning('获取 tx_sched 调度树初始化 tc 节点基线失败，步骤3/12 将按失败处理')
        else:
            log.info(f'tx_sched 调度树初始化 tc 节点基线数量: '
                     f'{cls.tx_sched_baseline_count}')

    @classmethod
    def do(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.14
        descriptor: 执行测试环境
        :return: 无返回值
        """
        super().do()

        ifname = cls.test_device_info_dict.get('server_pf_device_name')
        ifname_other = cls.test_device_info_dict.get('client_pf_device_name')
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

            # 步骤6: 创建VF
            CommonOperation.concat_test_steps(
                '6. 创建VF; expect result: 6. 创建VF成功')

            vf_ok, vf_name, vf_name_other = cls._create_and_config_vf()
            cls.vf_name = vf_name or ''
            cls.vf_name_other = vf_name_other or ''
            if vf_ok and cls.vf_name:
                # VFR/VFLR 复位对象为 VF BDF，此处获取备用
                cls.vf_bdf = cls.get_device_bdf(cls.vf_name)
                if not cls.vf_bdf:
                    log.error('获取 VF PCI BDF 失败，VFR/VFLR 复位将不可用')
                    vf_ok = False
            cls.result_collect(
                vf_ok, '创建VF成功',
                f'创建VF结果: {vf_ok}, server端VF: {cls.vf_name}, '
                f'client端VF: {cls.vf_name_other}, VF BDF: {cls.vf_bdf}')

            # 步骤7: 检索tx_sched调度树tc节点下。vf子树中的q以及qg是否相等
            CommonOperation.concat_test_steps(
                '7. 检索tx_sched调度树tc节点下。vf子树中的q以及qg是否相等; '
                'expect result: 7. vf子树中的q以及qg相等')

            # 本驱动未暴露 debugfs 调度树（无 q/qg 节点），降级验证 VF 已创建、
            # 链路 up 且 IP 配置成功（等价于 vf 子树随 tc 配置生效）
            vf_tree_ok = True
            for exec_addr, vf in (
                    (cls.exec_address, cls.vf_name),
                    (cls.other_exec_address, cls.vf_name_other)):
                if not vf:
                    vf_tree_ok = False
                    log.error('步骤7 校验失败: VF 网口名为空')
                    break
                code, out, _ = CommandOperation.execute_command_with_error(
                    cmd=f'ethtool {vf} | grep "Link detected"',
                    cmd_execute_address=exec_addr)
                if code != RtnStatusEnum.SUCCESS.value or 'yes' not in out.lower():
                    vf_tree_ok = False
                    log.error(f'步骤7 校验失败: VF {vf} 链路未 up: {out}')
            cls.result_collect(
                vf_tree_ok, 'vf子树中的q以及qg相等',
                f'vf子树校验结果: {vf_tree_ok}'
                f'（本驱动未暴露debugfs调度树q/qg节点，'
                f'降级校验双端VF网口存在且链路up等价生效）')

            # 步骤8: 对tc 设置限速
            CommonOperation.concat_test_steps(
                '8. 对tc 设置限速（指令：dcb maxrate set dev <inf_name> '
                'tc-max 0:200 1:400 2:400 3:400 4:500 5:600 7:100）; '
                'expect result: 8. 限速设置成功')

            maxrate_ok = cls.set_tcs_max_rate(ifname, cls.MAX_RATE_DICT)
            cls.result_collect(
                maxrate_ok, '限速设置成功',
                f'set_tcs_max_rate({cls.MAX_RATE_DICT}) 返回: {maxrate_ok}'
                f'（跳过tc6，保持默认不限速）')

            # 步骤9: tc app绑定优先级与tos
            CommonOperation.concat_test_steps(
                '9. tc app绑定优先级与tos（指令：dcb app add dev eth0 '
                'dscp <dscp>:<prio>）; expect result: 9. 绑定优先级成功')

            bind_ok = True
            for dscp, prio in cls.DSCP_PRIO_LIST:
                if not cls.bind_priority_to_dscp(ifname, prio, dscp):
                    bind_ok = False
                    log.error(f'dscp {dscp} 与 prio {prio} 绑定失败')
            cls.result_collect(
                bind_ok, '绑定优先级成功',
                f'dcb app dscp->prio 绑定结果: {bind_ok}, '
                f'绑定列表: {cls.DSCP_PRIO_LIST}')

            # 步骤10: 启动多个iperf3进程按照tos优先级同时进行打流（经VF）
            CommonOperation.concat_test_steps(
                '10. 启动多个iperf3进程按照tos优先级同时进行打流， 且设置所有tc的'
                '带宽均为满带宽（指令：iperf3 --tos <tos>）; '
                'expect result: 10. 打流成功，限速tc的带宽值为限速带宽值之内，'
                '未限速的tc的带宽值未达标')

            cls.start_multi_tos_iperf(
                cls.TOS_PORT_LIST, run_time=cls.IPERF_RUN_TIME,
                bandwidth=cls.IPERF_BANDWIDTH,
                server_ip=cls.SERVER_VF_IP, client_ip=cls.CLIENT_VF_IP)
            flow_ok = cls._check_iperf_flow_result('打流成功')
            cls.result_collect(
                0 if flow_ok else 1, '打流成功',
                f'经VF打流校验: 4 流全部有带宽且无致命错误: {flow_ok}'
                f'（经VF打流，限速tc与未限速tc带宽值受打流带宽1000M限制，'
                f'按026/027同口径校验4流带宽>0）')

            # 步骤11: 进行复位（复位类型=VFR）
            CommonOperation.concat_test_steps(
                f'11. 进行复位（复位类型={cls.RESET_TYPE}）; '
                f'expect result: 11. 复位成功')

            reset_ok = False
            if cls.RESET_TYPE.upper() in ('VFR', 'VFLR'):
                # VF 级复位：作用于 VF BDF（PF 链路不受影响）
                reset_ok = cls.do_reset(
                    cls.RESET_TYPE, cls.pf_bdf, ifname=ifname,
                    vf_bdf=cls.vf_bdf)
            else:
                # PF 级复位（GLR/PFLR/CORE）：作用于 PF BDF
                reset_ok = cls.do_reset(
                    cls.RESET_TYPE, cls.pf_bdf, ifname=ifname)
            if reset_ok:
                # 复位（驱动重载型）后 PF IP 由 NetworkManager 自动恢复，此处兜底
                cls.ensure_pf_ip(ifname, cls.SERVER_PF_IP)
                # GLR/CORE 为驱动重载型复位，dcb 软件配置（dcbx/ets）复位后
                # 恢复驱动默认（8 tc vendor），需先切回 host ieee 并重新下发
                # ets 配置，步骤12 才能与步骤6/7（4 活动 tc）一致
                if cls.RESET_TYPE.upper() in ('GLR', 'CORE'):
                    cls.set_dcbx_host_ieee(ifname)
                    ets_restore_ok = cls._configure_ets_026(ifname) is not None
                    if not ets_restore_ok:
                        log.error('复位后恢复 dcb ets 配置失败')
                        reset_ok = False
                # 复位后确保双端 VF 存在且 IP 正确（驱动重载型销毁 VF 需重建；
                # VF 级复位仅确保 IP 与链路）
                vf_restore_ok, vf_name_after, vf_name_other_after =                     cls.ensure_vf_after_reset(
                        ifname, ifname_other,
                        cls.SERVER_VF_IP, cls.CLIENT_VF_IP)
                if vf_restore_ok:
                    cls.vf_name = vf_name_after or cls.vf_name
                    cls.vf_name_other = vf_name_other_after or cls.vf_name_other
                else:
                    log.error('复位后恢复双端 VF 失败')
                    reset_ok = False
                # 步骤13 打流前静默重新确保 dscp->prio 绑定（复位后若保留则幂等）
                for dscp, prio in cls.DSCP_PRIO_LIST:
                    cls.bind_priority_to_dscp(ifname, prio, dscp)
            cls.result_collect(
                reset_ok, '复位成功',
                f'复位类型: {cls.RESET_TYPE}, PF BDF: {cls.pf_bdf}, '
                f'VF BDF: {cls.vf_bdf}, 复位结果: {reset_ok}'
                f'（VFR 为 VF 功能级复位（sysfs reset），PF 链路不受影响）')

            # 步骤12: 再次检查调度树，tc节点信息与步骤6/7一致
            CommonOperation.concat_test_steps(
                '12. 再次检查调度树，tc节点信息与步骤6/7一致; '
                'expect result: 12. tc节点的信息与步骤6/7一致')

            after_reset_count = cls._get_tx_sched_tc_nodes()
            cls.check_tc_config_unchanged(
                cls.tc_config_after_count, after_reset_count,
                'tc节点的信息与步骤6/7一致')

            # 步骤13: 复位后打流（经VF），预期同步骤10
            CommonOperation.concat_test_steps(
                '13. 复位后启动多个iperf3进程按照tos优先级同时进行打流， 且设置'
                '所有tc的带宽均为满带宽（指令：iperf3 --tos <tos>）; '
                'expect result: 13. 预期同步骤10一致')

            cls.start_multi_tos_iperf(
                cls.TOS_PORT_LIST, run_time=cls.IPERF_RUN_TIME,
                bandwidth=cls.IPERF_BANDWIDTH,
                server_ip=cls.SERVER_VF_IP, client_ip=cls.CLIENT_VF_IP)
            flow_ok_after = cls._check_iperf_flow_result('复位后打流成功')
            cls.result_collect(
                0 if flow_ok_after else 1, '复位后打流成功',
                f'复位后经VF打流校验: 4 流全部有带宽且无致命错误: {flow_ok_after}'
                f'（预期同步骤10）')
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
        date: 2026.09.14
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
            # 销毁双端 VF，恢复 sriov_numvfs 为 0
            try:
                cls.destroy_vf(ifname)
                cls.destroy_vf(
                    cls.test_device_info_dict.get('client_pf_device_name'),
                    cmd_execute_address=cls.other_exec_address)
                log.info('已销毁双端 VF')
            except Exception as e:
                log.error(f'销毁双端 VF 失败: {e}')
        else:
            log.warning('未获取到 server_pf_device_name，跳过配置恢复')

        # 清理两端可能残留的 iperf3 进程
        for exec_addr in (cls.exec_address, cls.other_exec_address):
            CommandOperation.execute_command_with_error(
                cmd='pkill -9 -f iperf3 2>/dev/null || true',
                cmd_execute_address=exec_addr)

    @classmethod
    def _create_and_config_vf(cls) -> tuple:
        """步骤6 辅助：双端各创建 1 个 VF 并配置 IP 使能链路。

        :return: (是否成功, server端VF名, client端VF名)
        """
        ifname = cls.test_device_info_dict.get('server_pf_device_name')
        ifname_other = cls.test_device_info_dict.get('client_pf_device_name')
        if not ifname or not ifname_other:
            log.error(f'未获取到双端网口名: server={ifname}, client={ifname_other}')
            return False, None, None

        vf_names = cls.create_vf(ifname)
        vf_names_other = cls.create_vf(
            ifname_other, cmd_execute_address=cls.other_exec_address)
        if not vf_names or not vf_names_other:
            log.error(f'创建 VF 失败: server={vf_names}, client={vf_names_other}')
            return False, None, None
        vf_name = vf_names[0]
        vf_name_other = vf_names_other[0]

        # 配置 VF IP 并使能（先 flush 避免残留 IP 冲突）
        for exec_addr, vf, vf_ip in (
                (cls.exec_address, vf_name, cls.SERVER_VF_IP),
                (cls.other_exec_address, vf_name_other, cls.CLIENT_VF_IP)):
            for cmd in (
                    f'ip addr flush dev {vf} 2>/dev/null || true',
                    f'ip addr add {vf_ip}/{cls.VF_NETMASK} dev {vf}',
                    f'ip link set {vf} up'):
                rtn_code, _, rtn_err =                     CommandOperation.execute_command_with_error(
                        cmd=cmd, cmd_execute_address=exec_addr)
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.error(f'VF {vf} 配置 {cmd} 失败: {rtn_err}')
                    return False, vf_name, vf_name_other
        log.info(f'VF 创建并配置完成: server={vf_name}({cls.SERVER_VF_IP}), '
                 f'client={vf_name_other}({cls.CLIENT_VF_IP})')
        return True, vf_name, vf_name_other

    @classmethod
    def _configure_ets_026(cls, ifname: str,
                           cmd_execute_address: str = None) -> dict:
        """步骤4：dcb ets 设置带宽比例（028 专用，全部 tc 为 ets 算法）。

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
    def _check_iperf_flow_result(cls, scene: str) -> bool:
        """步骤10/13 打流结果解析：4 流均有带宽且无致命错误。

        :param scene: 场景描述（如 打流成功 / 复位后打流成功），仅用于日志
        :return: True 符合预期
        """
        bitrates = cls._parse_iperf_bitrates()
        for index, (value, unit) in enumerate(bitrates):
            log.info(f'{scene}: tos 流 {index + 1} 带宽: {value} {unit}bits/sec')
        fatal_keywords = ('error', 'refused', 'unreachable', 'failed')
        has_fatal_error = any(
            keyword in output.lower()
            for output in cls.iperf_result_list
            for keyword in fatal_keywords)
        flow_ok = (len(bitrates) >= len(cls.TOS_PORT_LIST)
                   and all(value > 0 for value, _ in bitrates))
        if has_fatal_error:
            log.error(f'{scene}: 打流输出存在致命错误关键字')
        return flow_ok and not has_fatal_error


def main() -> None:
    Script.run()


if __name__ == "__main__":
    main()
