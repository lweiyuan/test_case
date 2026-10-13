"""
case_title:reset基类
test_category:
author: jinbo.zhang
date:2024.12.06
"""

import add_syspath
import re
import time
import random
import json

from scripts.script_libs.command_line_args_parse import CommandLineArgsParse
from scripts.script_libs.host_operation import HostOperation
from scripts.script_libs import log, constants
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import (CmdExecuteAdressEnum, RtnStatusEnum, NicNameEnum, CoreResetType, FwResetType,
                                       ResetType, SleepTime)
from scripts.script_libs.script_base import ScriptBase, SxeThread
from scripts.script_libs.command_operation import CommandOperation
from scripts.nic100.linux.driver.reset.common_operation_reset import CommonOperationReset
from scripts.script_libs.cli_operation import CliOperation


class ScriptBaseResetCheck(ScriptBase):
    server_driver_name, client_driver_name = CommonOperation.get_nic_driver_name()
    server_bus_info, client_bus_info = None, None
    server_device_name, client_device_name = None, None
    server_device_mac, client_device_mac = None, None
    server_device_ip, client_device_ip = None, None
    server_device_name_vf, server_bus_info_vf, server_device_ip_vf = None, None, None
    server_exec = CmdExecuteAdressEnum.SERVER.value
    client_exec = CmdExecuteAdressEnum.CLIENT.value
    original_feature_list = []
    original_feature_dict = {}
    original_feature_list_vf = []
    original_feature_dict_vf = {}
    # 测试轮数
    test_round = 1
    # 主动修改的配置
    config_list = [['tx-checksumming', 'off']]
    # 会修改的配置：主动+被动
    modified_list = [['tx-checksumming', ' off'], ['tx-checksum-ipv4', ' off'], ['tx-checksum-ipv6', ' off'],
                     ['tx-checksum-sctp', ' off'], ['tcp-segmentation-offload', ' off'],
                     ['tx-tcp-segmentation', ' off [requested on]'], ['tx-tcp-ecn-segmentation', ' off [requested on]'],
                     ['tx-tcp6-segmentation', ' off [requested on]']]
    feature_test = True
    serial_operation = True
    serial_operation_vf = False
    serial_operation_vf_mul_features = False
    parallel_operation = False
    parallel_operation_vf = False
    parallel_operation_vf_mul_features = False
    para_op_result = 0
    output_result = ''
    reset_type = ResetType.PFLR.value
    test_time = 30
    if constants.is_hf:
        pf_reset_type_list = [ResetType.PFLR.value, ResetType.PFR.value]
    else:
        pf_reset_type_list = [ResetType.PFLR.value, ResetType.PFR.value, ResetType.CORER.value]
    vf_reset_type_list = [ResetType.VFLR.value, ResetType.VFR.value]
    all_reset_type_list = pf_reset_type_list + vf_reset_type_list
    random.shuffle(pf_reset_type_list)
    skip_flag = False
    # set_fail_show_success_list = ['rx-gro-list',
    #                               'rx-vlan-stag-hw-parse',
    #                               'tx-vlan-stag-hw-insert',
    #                               'tx-nocache-copy',
    #                               'tx-udp-segmentation',
    #                               'tx-udp_tnl-csum-segmentation',
    #                               'tx-udp_tnl-segmentation',
    #                               'tx-ipxip6-segmentation',
    #                               'tx-ipxip4-segmentation',
    #                               'tx-gre-csum-segmentation',
    #                               'tx-gre-segmentation',
    #                               'highdma',
    #                               'tx-vlan-offload',
    #                               'generic-receive-offload',
    #                               'generic-segmentation-offload',
    #                               'tx-tcp6-segmentation',
    #                               'tx-tcp-mangleid-segmentation',
    #                               'tx-tcp-ecn-segmentation',
    #                               'tx-tcp-segmentation',
    #                               ]
    iperf3_ports = [i for i in range(1, 1000)]

    @classmethod
    def set_parameters(cls) -> None:
        """
        author:      jinbo.zhang
        date:        2024.12.06
        description: 参数设置
        """
        super().set_parameters()

    @classmethod
    def check_own_environment(cls) -> None:
        """
        author:      jinbo.zhang
        date:        2024.12.23
        descriptor: 检测当前脚本运行所需的局部环境是否具备
        :return: 无返回值
        """
        CommonOperation.concat_test_steps('1.1 环境检查')
        cls.own_environment_enabled = CommonOperation.common_check_environment(cls)
        # 合封标卡配置vf开关和vf个数
        if constants.is_hf:
            nic_count, _ = CommonOperation.get_nic_and_pf_count()
            log.info(f'合封环境，网卡个数是{nic_count}')
            for nic_ind in range(nic_count):
                cmd = f'/home/SCULNX_v1.13/SCULNX -o -q \\"Nic{nic_ind} Sriov Control\\"'
                code, out, err = CommandOperation.execute_command_with_error(cmd, cls.server_exec)
                log.info(f'命令{cmd}返回的信息是{code}/n{out}/n{err}')
                if '"Value":	1' not in out:
                    cmd = f'/home/SCULNX_v1.13/SCULNX -i -q \\"Nic{nic_ind} Sriov Control=1\\"'
                    code, out, err = CommandOperation.execute_command_with_error(cmd, cls.server_exec)
                    log.info(f'命令{cmd}返回的信息是{code}/n{out}/n{err}')
                    CommonOperationReset.host_reboot_with_check(cls, cls.server_logical_ip)
                    CommonOperation.modprobe_driver(cls.server_driver_name, CmdExecuteAdressEnum.SERVER.value)

                    cmd = f'/home/SCULNX_v1.13/SCULNX -i -q  \\"Nic{nic_ind} Pf0 Vf Number=128\\"'
                    code, out, err = CommandOperation.execute_command_with_error(cmd, cls.server_exec)
                    log.info(f'命令{cmd}返回的信息是{code}/n{out}/n{err}')
                    CommonOperationReset.host_reboot_with_check(cls, cls.server_logical_ip)
                    CommonOperation.modprobe_driver(cls.server_driver_name, CmdExecuteAdressEnum.SERVER.value)
                else:
                    cmd = f'/home/SCULNX_v1.13/SCULNX -o -q  \\"Nic{nic_ind} Pf0 Vf Number\\"'
                    code, out, err = CommandOperation.execute_command_with_error(cmd, cls.server_exec)
                    log.info(f'命令{cmd}返回的信息是{code}/n{out}/n{err}')
                    if '"Value":	0' in out:
                        cmd = f'/home/SCULNX_v1.13/SCULNX -i -q  \\"Nic{nic_ind} Pf0 Vf Number=128\\"'
                        code, out, err = CommandOperation.execute_command_with_error(cmd, cls.server_exec)
                        log.info(f'命令{cmd}返回的信息是{code}/n{out}/n{err}')
                        CommonOperationReset.host_reboot_with_check(cls, cls.server_logical_ip)
                        CommonOperation.modprobe_driver(cls.server_driver_name, CmdExecuteAdressEnum.SERVER.value)

    @classmethod
    def prepare(cls) -> None:
        """
        author:      jinbo.zhang
        date:        2024.12.23
        description: 环境准备
        """
        CommonOperation.concat_test_steps('2.1 环境准备,获取初始状态并记录')
        log.info('\n' + f"测试执行".center(100, "*"))
        CommonOperation.print_host_time()
        info_json = json.dumps(cls.test_device_info_list, indent=2)
        log.info(
            "待测网卡信息:\n%s" % info_json)
        for device_info in cls.test_device_info_list:
            cls.server_bus_info = device_info.get('server_bus_info')
            cls.client_bus_info = device_info.get('client_bus_info')
            cls.server_device_name = device_info.get('server_device_name')
            cls.client_device_name = device_info.get('client_device_name')
            cls.server_device_ip = device_info.get('server_device_ip')
            cls.client_device_ip = device_info.get('client_device_ip')
            log.info(cls.server_device_name)
            log.info(cls.client_device_name)
            log.info(cls.server_bus_info)
            log.info(cls.client_bus_info)
            log.info(cls.server_device_ip)
            log.info(cls.client_device_ip)
            # 获取初始配置信息
            if cls.feature_test:
                cls.original_feature_list, cls.original_feature_dict = \
                    cls.get_device_feature_info(cls.server_device_name)
                log.info('初始配置信息为:')
                log.info(cls.original_feature_list)
                log.info(cls.original_feature_dict)

    @classmethod
    def do(cls) -> None:
        """
        author:      jinbo.zhang
        date:        2024.12.23
        description: 测试步骤执行
        """
        for device_info in cls.test_device_info_list:
            cls.server_bus_info = device_info.get('server_bus_info')
            cls.client_bus_info = device_info.get('client_bus_info')
            cls.server_device_name = device_info.get('server_device_name')
            cls.client_device_name = device_info.get('client_device_name')
            cls.client_device_ip = device_info.get('client_device_ip')
            log.info(f'========当前测试端口：{cls.server_device_name} {cls.server_bus_info}')
            if cls.serial_operation:
                cmd = f'ethtool --show-features {cls.server_device_name} |grep fixed'
                code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd,
                                                                                              CmdExecuteAdressEnum.SERVER.value)
                for item in cls.config_list:
                    set_key = item[0]
                    set_value = item[1]
                    if set_key in out:
                        log.info(f'pf不支持配置{set_key}，直接pass')
                        return
                    CommonOperation.concat_test_steps(f'2.2 执行执行ethtool --features {cls.server_device_name} '
                                                      f'{set_key} {set_value}')
                    cls.set_device_feature_switch(cls.server_device_name, set_key, set_value)
                feature_list_before, feature_dict_before = cls.get_device_feature_info(cls.server_device_name)
                for item in cls.modified_list:
                    set_key = item[0]
                    expect_value = item[1]
                    get_value = feature_dict_before.get(set_key)
                    CommonOperation.concat_test_steps(f'{set_key}配置信息检查')
                    cls.check_info_is_same(get_value, expect_value)
                i = 3
                for reset_type in cls.pf_reset_type_list:
                    CommonOperation.concat_test_steps(f'2.{i}: 执行{reset_type}复位')
                    cls.start_reset(cls.server_device_name, cls.server_bus_info, reset_type=reset_type)
                    if reset_type == ResetType.CORER.value:
                        time.sleep(SleepTime.CHECK_FEATURE_AFTER_CORER.value)
                        CommonOperation.wait_cli_resume_normal(cls, cls.server_bus_info)
                        server_driver_name, client_driver_name = CommonOperation.get_nic_driver_name()
                        if client_driver_name == NicNameEnum.E810.value:
                            CommonOperationReset.custom_scgbe_speedbridge1ganset(cls.server_bus_info)
                    else:
                        time.sleep(SleepTime.CHECK_FEATURE_AFTER_FR.value)
                    CommonOperation.wait_ping_resume_normal(cls, cls.client_device_ip)
                    feature_list_after, feature_dict_after = cls.get_device_feature_info(cls.server_device_name)
                    for item in feature_list_before:
                        set_key = item[0]
                        expect_value = item[1]
                        get_value = feature_dict_after.get(set_key)
                        CommonOperation.concat_test_steps(f'{reset_type}复位后的{set_key}配置信息检查')
                        cls.check_info_is_same(get_value, expect_value)
                    i += 1
            if cls.serial_operation_vf:
                CommonOperationReset.create_vf_device_and_driver(cls.server_device_name, 1, CmdExecuteAdressEnum.SERVER.value)
                cls.server_device_name_vf = cls.server_device_name + "v0"
                cls.server_bus_info = CommonOperation.get_bdf_of_nic(cls.server_device_name_vf)
                cls.server_bus_info_vf = CommonOperation.get_bdf_of_nic(cls.server_device_name_vf)

                cmd = f'ethtool --show-features {cls.server_device_name_vf} |grep fixed'
                code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd,
                                                                                              CmdExecuteAdressEnum.SERVER.value)

                for item in cls.config_list:
                    set_key = item[0]
                    set_value = item[1]
                    for line in out.split('\n'):
                        left, _ = line.split(':')
                        if set_key.strip() == left.strip():
                            log.info(f'vf不支持配置{set_key}，直接pass')
                            return
                    CommonOperation.concat_test_steps(f'2.2 执行执行ethtool --features {cls.server_device_name_vf} '
                                                      f'{set_key} {set_value}')
                    cls.set_device_feature_switch(cls.server_device_name_vf, set_key, set_value)
                feature_list_before, feature_dict_before = cls.get_device_feature_info(cls.server_device_name_vf)
                for item in cls.modified_list:
                    set_key = item[0]
                    expect_value = item[1]
                    get_value = feature_dict_before.get(set_key)
                    CommonOperation.concat_test_steps(f'{set_key}配置信息检查')
                    cls.check_info_is_same(get_value, expect_value)

                i = 3
                for reset_type in cls.vf_reset_type_list:
                    CommonOperation.concat_test_steps(f'2.{i}: 执行{reset_type}复位')
                    cls.start_reset(cls.server_device_name_vf, cls.server_bus_info_vf, reset_type=reset_type)
                    time.sleep(5)
                    feature_list_after, feature_dict_after = cls.get_device_feature_info(cls.server_device_name_vf)
                    for item in feature_list_before:
                        set_key = item[0]
                        expect_value = item[1]
                        get_value = feature_dict_after.get(set_key)
                        CommonOperation.concat_test_steps(f'{reset_type}复位后的{set_key}配置信息检查')
                        cls.check_info_is_same(get_value, expect_value)
                    i += 1
            if cls.serial_operation_vf_mul_features:
                CommonOperationReset.create_vf_device_and_driver(cls.server_device_name, 1,
                                                                 CmdExecuteAdressEnum.SERVER.value)
                cls.server_device_name_vf = cls.server_device_name + "v0"
                cls.server_bus_info = CommonOperation.get_bdf_of_nic(cls.server_device_name_vf)
                cls.server_bus_info_vf = CommonOperation.get_bdf_of_nic(cls.server_device_name_vf)

                cmd = f'ethtool --show-features {cls.server_device_name_vf} |grep fixed'
                code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd,
                                                                                              CmdExecuteAdressEnum.SERVER.value)
                feature_dict_1 = {}
                feature_dict_2 = {}
                for item in cls.config_list:
                    set_key = item[0]
                    set_value = item[1]
                    for line in out.split('\n'):
                        left, _ = line.split(':')
                        if set_key.strip() == left.strip():
                            log.info(f'vf不支持配置{set_key}，直接pass')
                            return
                    feature_dict_1.update({set_key: set_value})
                CommonOperation.concat_test_steps(f'2.2 执行执行ethtool --features {cls.server_device_name_vf} '
                                                  f'{feature_dict_1}')
                cls.set_device_mul_features(cls.server_device_name_vf, feature_dict_1)
                feature_list_before, feature_dict_before = cls.get_device_feature_info(cls.server_device_name_vf)
                for item in cls.modified_list:
                    set_key = item[0]
                    expect_value = item[1]
                    get_value = feature_dict_before.get(set_key)
                    CommonOperation.concat_test_steps(f'{set_key}配置信息检查')
                    cls.check_info_is_same(get_value, expect_value)

                i = 3
                for reset_type in cls.vf_reset_type_list:
                    CommonOperation.concat_test_steps(f'2.{i}: 执行{reset_type}复位')
                    cls.start_reset(cls.server_device_name_vf, cls.server_bus_info_vf, reset_type=reset_type)
                    time.sleep(5)
                    feature_list_after, feature_dict_after = cls.get_device_feature_info(cls.server_device_name_vf)
                    for item in feature_list_before:
                        set_key = item[0]
                        expect_value = item[1]
                        get_value = feature_dict_after.get(set_key)
                        CommonOperation.concat_test_steps(f'{reset_type}复位后的{set_key}配置信息检查')
                        cls.check_info_is_same(get_value, expect_value)
                    i += 1
            if cls.parallel_operation:
                cmd = f'ethtool --show-features {cls.server_device_name} |grep fixed'
                code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd,
                                                                                              CmdExecuteAdressEnum.SERVER.value)
                for item in cls.config_list:
                    set_key = item[0]
                    set_value1 = item[1]
                    if set_value1 == 'off':
                        set_value2 = 'on'
                    else:
                        set_value2 = 'off'
                    if set_key in out:
                        log.info(f'pf不支持配置{set_key}，直接pass')
                        return
                    for reset_type in cls.pf_reset_type_list:
                        log.info(f'当前的复位类型{reset_type}')
                        cls.para_op_result = 0
                        CommonOperation.concat_test_steps(f'2.2 执行执行ethtool --features {cls.server_device_name} '
                                                          f'{set_key} {set_value1}并发{reset_type}复位')
                        start_time = time.time()
                        thread2 = SxeThread(cls.do_reset, cls.server_device_name, cls.server_bus_info, reset_type)
                        thread2.start()
                        while True:
                            cls.set_device_feature_switch(cls.server_device_name, set_key, set_value1, operation=True)
                            if cls.para_op_result != RtnStatusEnum.SUCCESS.value:
                                flag = 1
                                log.info('并发成功，检查设备信息')
                                if reset_type == ResetType.CORER.value:
                                    time.sleep(SleepTime.CHECK_FEATURE_AFTER_CORER.value)
                                else:
                                    time.sleep(SleepTime.CHECK_FEATURE_AFTER_FR.value)
                                _, feature_dict = cls.get_device_feature_info(cls.server_device_name)
                                log.info(f'检查特性{set_key}')
                                get_value = feature_dict.get(set_key)
                                cls.check_info_is_same(get_value, set_value2, contain=True)
                                break
                            cls.set_device_feature_switch(cls.server_device_name, set_key, set_value2, operation=True)
                            if cls.para_op_result != RtnStatusEnum.SUCCESS.value:
                                flag = 2
                                log.info('并发成功，检查设备信息')
                                if reset_type == ResetType.CORER.value:
                                    time.sleep(SleepTime.CHECK_FEATURE_AFTER_CORER.value)
                                else:
                                    time.sleep(SleepTime.CHECK_FEATURE_AFTER_FR.value)
                                _, feature_dict = cls.get_device_feature_info(cls.server_device_name)
                                log.info(f'检查特性{set_key}')
                                get_value = feature_dict.get(set_key)
                                cls.check_info_is_same(get_value, set_value1, contain=True)
                                break
                            end_time = time.time()
                            duration = end_time - start_time
                            if duration > cls.test_time:
                                flag = 0
                                log.info(f'已测试{cls.test_time}s，停止测试')
                                break
                        thread2.join()
                        # 等待位结束
                        if reset_type == ResetType.CORER.value:
                            time.sleep(SleepTime.CHECK_FEATURE_AFTER_CORER.value)
                        else:
                            time.sleep(SleepTime.CHECK_FEATURE_AFTER_FR.value)
                        log.info('复位过程中配置设置失败符合预期，复位结束后再次设置')
                        # expect_value = cls.original_feature_dict.get(set_key)
                        # if flag == 1:
                        #     cls.set_device_feature_switch(cls.server_device_name, set_key, expect_value)
                        # cls.set_device_feature_switch(cls.server_device_name, set_key, set_value1)
                        _, feature_dict = cls.get_device_feature_info(cls.server_device_name)
                        get_value = feature_dict.get(set_key)
                        set_list = ['tcp-segmentation-offload']
                        if flag == 1:
                            log.info(f'flag == 1')
                            if 'requested' in get_value or set_key in set_list:
                                cls.set_device_feature_switch(cls.server_device_name, set_key, set_value2)
                            cls.set_device_feature_switch(cls.server_device_name, set_key, set_value1)
                        if flag == 2:
                            log.info(f'flag == 2')
                            if 'requested' in get_value or set_key in set_list:
                                cls.set_device_feature_switch(cls.server_device_name, set_key, set_value1)
                            cls.set_device_feature_switch(cls.server_device_name, set_key, set_value2)
                            cls.set_device_feature_switch(cls.server_device_name, set_key, set_value1)
                        if flag == 0:
                            log.info(f'flag == 0')
                            cls.set_device_feature_switch(cls.server_device_name, set_key, set_value1)
                        feature_list, feature_dict = cls.get_device_feature_info(cls.server_device_name)
                        for item in cls.modified_list:
                            set_key_modify = item[0]
                            expect_value = item[1]
                            get_value = feature_dict.get(set_key_modify)
                            CommonOperation.concat_test_steps(f'{set_key_modify}配置信息检查')
                            cls.check_info_is_same(get_value, expect_value)
                        log.info(f'本轮复位{reset_type}完成，恢复成默认值')
                        cls.set_device_feature_switch(cls.server_device_name, set_key, set_value2)
                        result_list = cls.original_feature_list[:]
                        for item in cls.modified_list:
                            key = item[0]
                            for a in result_list:
                                if key == a[0]:
                                    result_list.remove(a)
                        log.info(f'需要检查的其他特性信息是{result_list}')
                        for item in result_list:
                            set_key_other = item[0]
                            expect_value = item[1]
                            get_value = feature_dict.get(set_key_other)
                            CommonOperation.concat_test_steps(f'{set_key_other}配置信息检查')
                            cls.check_info_is_same(get_value, expect_value)
                        log.info('===========================================================')
            if cls.parallel_operation_vf:
                CommonOperationReset.create_vf_device_and_driver(cls.server_device_name, 1, CmdExecuteAdressEnum.SERVER.value)
                cls.server_device_name_vf = cls.server_device_name + "v0"
                cls.server_bus_info_vf = CommonOperation.get_bdf_of_nic(cls.server_device_name_vf)
                cmd = f'ethtool --show-features {cls.server_device_name_vf} |grep fixed'
                code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd,
                                                                                              CmdExecuteAdressEnum.SERVER.value)
                cls.original_feature_list_vf, cls.original_feature_dict_vf = \
                    cls.get_device_feature_info(cls.server_device_name_vf)
                log.info(f'vf初始配置信息为:\n{cls.original_feature_list_vf}\n{cls.original_feature_dict_vf}')
                for item in cls.config_list:
                    set_key = item[0]
                    set_value1 = item[1]
                    if set_value1 == 'off':
                        set_value2 = 'on'
                    else:
                        set_value2 = 'off'
                    for line in out.split('\n'):
                        left, _ = line.split(':')
                        if set_key.strip() == left.strip():
                            log.info(f'vf不支持配置{set_key}，直接pass')
                            return
                    if set_key in ['rx-vlan-stag-hw-parse', 'tx-vlan-stag-hw-insert']:
                        cls.set_device_feature_switch(cls.server_device_name_vf, 'rx-vlan-offload', 'off')
                        cls.set_device_feature_switch(cls.server_device_name_vf, 'tx-vlan-offload', 'off')
                        time.sleep(3)
                    for reset_type in cls.vf_reset_type_list:
                        log.info(f'复位类型{reset_type}')
                        cls.para_op_result = 0
                        CommonOperation.concat_test_steps(f'2.2 执行执行ethtool --features {cls.server_device_name_vf} '
                                                          f'{set_key} {set_value1}并发{reset_type}复位')
                        start_time = time.time()
                        thread2 = SxeThread(cls.do_reset, cls.server_device_name_vf, cls.server_bus_info_vf, reset_type)
                        thread2.start()
                        while True:
                            cls.set_device_feature_switch(cls.server_device_name_vf, set_key, set_value1, operation=True)
                            if cls.para_op_result != RtnStatusEnum.SUCCESS.value:
                                flag = 1
                                # if set_key not in cls.set_fail_show_success_list:
                                #     time.sleep(10)
                                #     log.info('并发成功，检查设备信息')
                                #     _, feature_dict = cls.get_device_feature_info(cls.server_device_name_vf)
                                #     log.info(f'检查特性{set_key}')
                                #     get_value = feature_dict.get(set_key)
                                #     cls.check_info_is_same(get_value, set_value2, contain=True)
                                break
                            cls.set_device_feature_switch(cls.server_device_name_vf, set_key, set_value2, operation=True)
                            if cls.para_op_result != RtnStatusEnum.SUCCESS.value:
                                flag = 2
                                # if set_key not in cls.set_fail_show_success_list:
                                #     time.sleep(10)
                                #     log.info('并发成功，检查设备信息')
                                #     _, feature_dict = cls.get_device_feature_info(cls.server_device_name_vf)
                                #     log.info(f'检查特性{set_key}')
                                #     get_value = feature_dict.get(set_key)
                                #     cls.check_info_is_same(get_value, set_value1, contain=True)
                                break
                            end_time = time.time()
                            duration = end_time - start_time
                            if duration > cls.test_time:
                                flag = 0
                                log.info(f'已测试{cls.test_time}s，停止测试')
                                break
                        thread2.join()
                        # 等待最后一轮复位结束
                        time.sleep(30)  # lro，复位并发设置on失败后，一开始查是off(request on)，等待大概15s后是on
                        log.info('复位过程中配置设置失败符合预期，复位结束后再次设置')
                        # expect_value = cls.original_feature_dict.get(set_key)
                        # if flag == 1:
                        #     cls.set_device_feature_switch(cls.server_device_name_vf, set_key, expect_value)
                        # cls.set_device_feature_switch(cls.server_device_name_vf, set_key, set_value1)
                        _, feature_dict = cls.get_device_feature_info(cls.server_device_name_vf)
                        get_value = feature_dict.get(set_key)
                        if flag == 1:
                            log.info(f'flag == 1')
                            if 'requested' in get_value:
                                cls.set_device_feature_switch(cls.server_device_name_vf, set_key, set_value2)
                                time.sleep(1)
                            cls.set_device_feature_switch(cls.server_device_name_vf, set_key, set_value1)
                            time.sleep(1)
                            cls.set_device_feature_switch(cls.server_device_name_vf, set_key, set_value2)
                            time.sleep(1)
                            cls.set_device_feature_switch(cls.server_device_name_vf, set_key, set_value1)
                        if flag == 2:
                            log.info(f'flag == 2')
                            if 'requested' in get_value:
                                cls.set_device_feature_switch(cls.server_device_name_vf, set_key, set_value1)
                                time.sleep(5)
                            cls.set_device_feature_switch(cls.server_device_name_vf, set_key, set_value2)
                            time.sleep(5)
                            cls.set_device_feature_switch(cls.server_device_name_vf, set_key, set_value1)
                        if flag == 0:
                            log.info(f'flag == 0')
                            cls.set_device_feature_switch(cls.server_device_name_vf, set_key, set_value1)
                        time.sleep(1)
                        feature_list, feature_dict = cls.get_device_feature_info(cls.server_device_name_vf)
                        for item in cls.modified_list:
                            set_key_modify = item[0]
                            expect_value = item[1]
                            get_value = feature_dict.get(set_key_modify)
                            CommonOperation.concat_test_steps(f'{set_key_modify}配置信息检查')
                            cls.check_info_is_same(get_value, expect_value)
                        log.info(f'本轮复位{reset_type}完成，恢复成默认值')
                        cls.set_device_feature_switch(cls.server_device_name_vf, set_key, set_value2)
                        result_list = cls.original_feature_list_vf[:]
                        for item in cls.modified_list:
                            key = item[0]
                            for a in result_list:
                                if key == a[0]:
                                    result_list.remove(a)
                        log.info(f'需要检查的其他特性是{result_list}')
                        for item in result_list:
                            set_key_other = item[0]
                            expect_value = item[1]
                            get_value = feature_dict.get(set_key_other)
                            CommonOperation.concat_test_steps(f'{set_key_other}配置信息检查')
                            cls.check_info_is_same(get_value, expect_value)
                        log.info('===========================================================')
            if cls.parallel_operation_vf_mul_features:
                for device_info in cls.test_device_info_list:
                    cls.server_bus_info = device_info.get('server_bus_info')
                    cls.client_bus_info = device_info.get('client_bus_info')
                    cls.server_device_name = device_info.get('server_device_name')
                    cls.client_device_name = device_info.get('client_device_name')
                    log.info(f'========当前测试端口：{cls.server_device_name} {cls.server_bus_info}')
                    CommonOperationReset.create_vf_device_and_driver(cls.server_device_name, 1,
                                                                     CmdExecuteAdressEnum.SERVER.value)
                    cls.server_device_name_vf = cls.server_device_name + "v0"
                    cls.server_bus_info_vf = CommonOperation.get_bdf_of_nic(cls.server_device_name_vf)
                    cls.original_feature_list_vf, cls.original_feature_dict_vf = \
                        cls.get_device_feature_info(cls.server_device_name_vf)
                    log.info(f'vf初始配置信息为:\n{cls.original_feature_list_vf}\n{cls.original_feature_dict_vf}')
                    cmd = f'ethtool --show-features {cls.server_device_name_vf} |grep fixed'
                    code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd,
                                                                                                  CmdExecuteAdressEnum.SERVER.value)
                    feature_dict_1 = {}
                    feature_dict_2 = {}
                    for item in cls.config_list:
                        set_key = item[0]
                        set_value1 = item[1]
                        if set_value1 == 'off':
                            set_value2 = 'on'
                        else:
                            set_value2 = 'off'
                        for line in out.split('\n'):
                            left, _ = line.split(':')
                            if set_key.strip() == left.strip():
                                log.info(f'vf不支持配置{set_key}，直接pass')
                                return
                        feature_dict_1.update({set_key: set_value1})
                        feature_dict_2.update({set_key: set_value2})
                    for reset_type in cls.vf_reset_type_list:
                        log.info(f'当前的复位类型{reset_type}')
                        cls.para_op_result = 0
                        CommonOperation.concat_test_steps(f'2.2 执行执行ethtool --features {cls.server_device_name_vf} '
                                                          f'并发{reset_type}复位')
                        start_time = time.time()
                        thread2 = SxeThread(cls.do_reset, cls.server_device_name_vf, cls.server_bus_info_vf, reset_type)
                        thread2.start()
                        while True:
                            cls.set_device_mul_features(cls.server_device_name_vf, feature_dict_1, operation=True)
                            if cls.para_op_result != RtnStatusEnum.SUCCESS.value:
                                flag = 1
                                log.info('并发成功，检查设备信息')
                                # if reset_type == ResetType.CORER.value:
                                #     time.sleep(SleepTime.CHECK_FEATURE_AFTER_CORER.value)
                                # else:
                                #     time.sleep(SleepTime.CHECK_FEATURE_AFTER_FR.value)
                                # _, feature_dict = cls.get_device_feature_info(cls.server_device_name_vf)
                                # for key, value in feature_dict_2.items():
                                #     log.info(f'检查特性{key}')
                                #     get_value = feature_dict.get(key)
                                #     cls.check_info_is_same(get_value, value, contain=True)
                                break
                            cls.set_device_mul_features(cls.server_device_name_vf, feature_dict_2, operation=True)
                            if cls.para_op_result != RtnStatusEnum.SUCCESS.value:
                                flag = 2
                                log.info('并发成功，检查设备信息')
                                # if reset_type == ResetType.CORER.value:
                                #     time.sleep(SleepTime.CHECK_FEATURE_AFTER_CORER.value)
                                # else:
                                #     time.sleep(SleepTime.CHECK_FEATURE_AFTER_FR.value)
                                # _, feature_dict = cls.get_device_feature_info(cls.server_device_name_vf)
                                # for key, value in feature_dict_1.items():
                                #     log.info(f'检查特性{key}')
                                #     get_value = feature_dict.get(key)
                                #     cls.check_info_is_same(get_value, value, contain=True)
                                break
                            end_time = time.time()
                            duration = end_time - start_time
                            if duration > cls.test_time:
                                flag = 0
                                log.info(f'已测试{cls.test_time}s，停止测试')
                                break
                        thread2.join()
                        # 等待位结束
                        if reset_type == ResetType.CORER.value:
                            time.sleep(SleepTime.CHECK_FEATURE_AFTER_CORER.value)
                        else:
                            time.sleep(SleepTime.CHECK_FEATURE_AFTER_FR.value)
                        log.info('复位过程中配置设置失败符合预期，复位结束后再次设置')

                        _, feature_dict = cls.get_device_feature_info(cls.server_device_name_vf)
                        get_value = feature_dict.get(list(feature_dict_1.keys())[0])
                        set_list = ['tcp-segmentation-offload']
                        if flag == 1:
                            log.info(f'flag == 1')
                            if 'requested' in get_value or list(feature_dict_1.keys())[0] in set_list:
                                cls.set_device_mul_features(cls.server_device_name_vf, feature_dict_2)
                            cls.set_device_mul_features(cls.server_device_name_vf, feature_dict_1)
                        if flag == 2:
                            log.info(f'flag == 2')
                            if 'requested' in get_value or list(feature_dict_1.keys())[0] in set_list:
                                cls.set_device_mul_features(cls.server_device_name_vf, feature_dict_1)
                            cls.set_device_mul_features(cls.server_device_name_vf, feature_dict_2)
                            cls.set_device_mul_features(cls.server_device_name_vf, feature_dict_1)
                        if flag == 0:
                            log.info(f'flag == 0')
                            cls.set_device_mul_features(cls.server_device_name_vf, feature_dict_1)
                        feature_list, feature_dict = cls.get_device_feature_info(cls.server_device_name_vf)
                        for item in cls.modified_list:
                            set_key_modify = item[0]
                            expect_value = item[1]
                            get_value = feature_dict.get(set_key_modify)
                            CommonOperation.concat_test_steps(f'{set_key_modify}配置信息检查')
                            cls.check_info_is_same(get_value, expect_value)
                        log.info(f'本轮复位{reset_type}完成，恢复成默认值')
                        cls.set_device_mul_features(cls.server_device_name_vf, feature_dict_2)
                        result_list = cls.original_feature_list_vf[:]
                        for item in cls.modified_list:
                            key = item[0]
                            for a in result_list:
                                if key == a[0]:
                                    result_list.remove(a)
                        log.info(f'需要检查的其他特性信息是{result_list}')
                        for item in result_list:
                            set_key_other = item[0]
                            expect_value = item[1]
                            get_value = feature_dict.get(set_key_other)
                            CommonOperation.concat_test_steps(f'{set_key_other}配置信息检查')
                            cls.check_info_is_same(get_value, expect_value)
                        log.info('===========================================================')
        log.info('do验证通过')

    @classmethod
    def do_reset(cls, device_name, bdf, reset_type) -> None:
        start_time = time.time()
        while True:
            cls.start_reset(device_name, bdf, reset_type)
            if reset_type == ResetType.CORER.value:
                return
            if cls.para_op_result != RtnStatusEnum.SUCCESS.value:
                log.info('测试结束，不再进行复位')
                break
            end_time = time.time()
            duration = end_time - start_time
            if duration > cls.test_time:
                log.info(f'已复位{cls.test_time}s，停止复位')
                break

    @classmethod
    def post(cls) -> None:
        """
        author:      jinbo.zhang
        date:        2024.12.23
        description: 还原环境
        """
        log.info('\n' + f"post".center(100, "*"))
        server_driver_name, client_driver_name = CommonOperation.get_nic_driver_name()
        # if client_driver_name == NicNameEnum.E810.value:
        #     CommonOperationReset.custom_scgbe_speedbridge1ganset(cls.server_bus_info)
        for device_info in cls.test_device_info_list:
            cls.server_device_name = device_info.get('server_device_name')
            cls.server_device_ip = device_info.get('server_device_ip')
            cls.client_device_ip = device_info.get('client_device_ip')
            # log.info(cls.server_device_name)
            log.info(cls.server_device_ip)
            log.info(cls.client_device_ip)
            CommonOperation.concat_test_steps(f'3.0:验证网口对端是否可ping通')
            CommonOperation.wait_ping_resume_normal(cls, cls.client_device_ip)
            # cls.check_ping_status(cls.server_device_ip, CmdExecuteAdressEnum.SERVER.value)

            CommonOperation.concat_test_steps(f'3.1:恢复环境，修改配置信息为初始值')
            # cls.driver_insmod_or_rmmod(cls.server_driver_name, True, True)
            if cls.feature_test:
                log.info(f'特性初始值是{cls.original_feature_list}')
                for item in cls.original_feature_list:
                    _, feature_dict = cls.get_device_feature_info(cls.server_device_name)
                    set_key = item[0]
                    expect_value = item[1]
                    get_value = feature_dict.get(set_key)
                    if get_value != expect_value:
                        if 'off' in expect_value:
                            expect_value = 'off'
                        else:
                            expect_value = 'on'
                        cls.set_device_feature_switch(cls.server_device_name, set_key, expect_value)
                _, feature_dict = cls.get_device_feature_info(cls.server_device_name)
                for item in cls.original_feature_list:
                    set_key = item[0]
                    expect_value = item[1]
                    get_value = feature_dict.get(set_key)
                    log.info(f'{set_key}配置信息检查')
                    cls.check_info_is_same(get_value, expect_value)
        CommonOperation.force_clear_env_vf_vlan()
        log.info('post验证通过')

    @classmethod
    def check_ping_status(cls, device_ip: str, exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author: jinbo.zhang
        date  : 2025.1.22
        description: 检查本端和对端是否能ping通
        :param device_ip:
        :param exec_addr:
        return: 无返回值
        """
        CommonOperationReset.check_ping_status(cls, device_ip, exec_addr)

    @classmethod
    def start_reset(cls, device_name: str, device_bdf: str, reset_type: str = ResetType.PFLR.value,
                    exec_addr: str = CmdExecuteAdressEnum.SERVER.value,
                    check_ignore: bool = False) -> None:
        """
        author: jinbo.zhang
        date  : 2024.12.23
        description: 执行复位PFLR
        :param device_name:
        :param device_bdf:
        :param reset_type: 默认PFLR
        :param exec_addr: in
        :param check_ignore: 是否忽略结果判断，默认不忽略
        return: 无返回值
        """
        CommonOperation.start_reset(cls, device_name, device_bdf, reset_type, exec_addr, check_ignore)

    @classmethod
    def core_reset_host_active(cls, caller_class, device: str = "", bdf: str = "", command_path: str = '',
                               exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
                               check_ignore: bool=False) -> None:
        """
        author:      jianghe
        date:        2025.04.23
        description: core_reset_host_active
        """
        CommonOperationReset.core_reset_host_active(caller_class, device, bdf, command_path, exec_addr,
                                                    check_ignore=check_ignore)

    @classmethod
    def core_reset_host_passive(cls, caller_class, device: str = "",
                               exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author:      jianghe
        date:        2025.04.23
        description: core_reset_host_passive
        """
        CommonOperationReset.core_reset_host_passive(caller_class, device, exec_addr)

    @classmethod
    def core_reset(cls, caller_class, device: str = "", bdf: str = "", reset_types: list = None) -> None:
        """
        author:      jianghe
        date:        2025.04.28
        description: core reset，选择core reset的方式
        :return:     None
        """
        CommonOperationReset.core_reset(caller_class, device, bdf, reset_types)

    @classmethod
    def get_device_feature_info(cls, device_name: str,
                                exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author: jinbo.zhang
        date  : 2024.12.23
        description: ethtool --show-features ens1f0获取信息
        :param device_name:
        :param exec_addr:
        return: 无返回值
        """
        cmd = f'ethtool --show-features {device_name} |grep -v fixed'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr,
                                                                                     print_outputs=False)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{cmd}执行成功')
            feature_list = rtn_outputs.splitlines()
            feature_list.pop(0)
            feature_list = [s.strip() for s in feature_list]
            feature_dict = dict(item.split(":") for item in feature_list)
            feature_list = [item.split(':') for item in feature_list]
            log.info(f'feature_list: {feature_list}，feature_dict: {feature_dict}')
            return feature_list, feature_dict
        else:
            log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(cls, key_word=f'获取{device_name}配置信息失败',
                                               description_word=f'获取{device_name}配置信息失败',
                                               expect_info=f'获取{device_name}配置信息成功',
                                               result_info=f'获取{device_name}配置信息失败')

    @classmethod
    def set_device_feature_switch(cls, device_name: str, feature_name: str, switch: str, operation: bool = False,
                                  exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author: jinbo.zhang
        date  : 2024.12.23
        description: ethtool --features ens1f0 tx on
        :param device_name:
        :param feature_name：配置名字
        :param switch: 配置开关 True:on, False:off
        :param operation: Ture->并发操作
        :param exec_addr:
        return: 无返回值
        """
        cmd = f'ethtool --features {device_name} {feature_name} {switch}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}')
        else:
            log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            if operation:
                cls.para_op_result = rtn_code
            else:
                CommonOperation.create_bug_problem(cls, key_word=f'设置{device_name}配置信息{feature_name}失败',
                                                   description_word=f'设置{device_name}配置信息{feature_name}失败',
                                                   expect_info=f'设置{device_name}配置信息{feature_name}成功',
                                                   result_info=f'设置{device_name}配置信息{feature_name}失败')

    @classmethod
    def set_device_mul_features(cls, device_name: str, feature_dict: dict, operation: bool = False,
                                exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author: jinbo.zhang
        date  : 2024.12.23
        description: ethtool --features ens1f0 tx on
        :param device_name:
        :param feature_name：配置名字
        :param switch: 配置开关 True:on, False:off
        :param operation: Ture->并发操作
        :param exec_addr:
        return: 无返回值
        """
        cmd = f'ethtool --features {device_name}'
        for key, value in feature_dict.items():
            cmd += f' {key} {value}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}')
        else:
            log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            if operation:
                cls.para_op_result = rtn_code
            else:
                CommonOperation.create_bug_problem(cls, key_word=f'ethtool',
                                                   description_word=f'设置{device_name}配置信息{feature_dict}失败')

    @classmethod
    def execute_ethtool_command(cls, operation: str, device_name: str, command: str = None, result: bool = True,
                                flag: bool = False, exec_addr=CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author: jinbo.zhang
        date  : 2025.1.11
        description: ethtool -operation ens1f0 command
        :param operation:
        :param device_name:
        :param command:命令
        :param result: 命令执行结果
        :param flag:
        :param exec_addr:
        return: 无返回值
        """
        return CommonOperationReset.execute_ethtool_command(cls, operation, device_name, command, result, flag, exec_addr)

    @classmethod
    def execute_ip_link_command(cls, operation: str, device_name: str, command: str = None, result: bool = True,
                                flag: bool = False, exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author: jinbo.zhang
        date  : 2025.1.11
        description: ip link set/show ens1f0 command
        :param operation:
        :param device_name:
        :param command:命令
        :param result: 命令执行结果
        :param flag:
        :param exec_addr:
        return: 无返回值
        """
        cmd = f'ip link {operation} {device_name}'
        if command is not None:
            cmd += ' ' + command
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功, 符合预期')
                cls.output_result = rtn_outputs
                return rtn_outputs
            else:
                log.info(f'command:{cmd}执行失败, 不符合预期，outputs:{rtn_outputs}')
                if flag:
                    cls.para_op_result = rtn_code
                else:
                    CommonOperation.create_bug_problem(cls, key_word=f'设置{device_name}配置信息{command}失败',
                                                       description_word=f'设置{device_name}配置信息{command}失败',
                                                       expect_info=f'设置{device_name}配置信息{command}成功',
                                                       result_info=f'设置{device_name}配置信息{command}失败')
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败, 符合预期')
                cls.output_result = rtn_outputs
                return rtn_outputs
            else:
                log.info(f'command:{cmd}执行成功, 不符合预期，outputs:{rtn_outputs}')
                if flag:
                    cls.para_op_result = rtn_code
                else:
                    CommonOperation.create_bug_problem(cls, key_word=f'设置{device_name}配置信息{command}成功',
                                                       description_word=f'设置{device_name}配置信息{command}成功',
                                                       expect_info=f'设置{device_name}配置信息{command}成功',
                                                       result_info=f'设置{device_name}配置信息{command}成功')

    @classmethod
    def execute_bridge_link_command(cls, operation: str, device_name: str, command: str = None, result: bool = True,
                                    flag: bool = False, exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author: jinbo.zhang
        date  : 2025.1.16
        description: bridge link show/set dev eth_name hwmode
        :param operation:
        :param device_name:
        :param command:命令
        :param result: 命令执行结果
        :param flag:
        :param exec_addr:
        return: 无返回值
        """
        cmd = f'bridge link {operation} dev {device_name} {command}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功, 符合预期')
                cls.output_result = rtn_outputs
                return rtn_outputs
            else:
                log.info(f'command:{cmd}执行失败, 不符合预期，outputs:{rtn_outputs}')
                if flag:
                    cls.para_op_result = rtn_code
                else:
                    CommonOperation.create_bug_problem(cls, key_word=f'设置{device_name}配置信息{command}失败',
                                                       description_word=f'设置{device_name}配置信息{command}失败',
                                                       expect_info=f'设置{device_name}配置信息{command}成功',
                                                       result_info=f'设置{device_name}配置信息{command}失败')
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败, 符合预期')
                cls.output_result = rtn_outputs
                return rtn_outputs
            else:
                log.info(f'command:{cmd}执行成功, 不符合预期')
                if flag:
                    cls.para_op_result = rtn_code
                else:
                    CommonOperation.create_bug_problem(cls, key_word=f'设置{device_name}配置信息{command}成功',
                                                       description_word=f'设置{device_name}配置信息{command}成功',
                                                       expect_info=f'设置{device_name}配置信息{command}成功',
                                                       result_info=f'设置{device_name}配置信息{command}成功')

    @classmethod
    def set_eth_mac(cls, caller_class, device_name: str, mac: str,
                    exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据device_name修改pf mac地址
        :param caller_class: 调用者的类
        :param device_name: 设备名称ens4f0
        :param mac: mac地址
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        cmd = f'ifconfig {device_name} hw ether {mac}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}')
        else:
            log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(caller_class, key_word='设置pf mac地址失败',
                                               description_word=f'{cmd}执行失败',
                                               expect_info=f'{cmd}执行成功',
                                               result_info=f'{rtn_outputs}')

    @classmethod
    def get_eth_mac(cls, device_name: str, exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据device_name获取pf mac地址
        :param device_name: 设备名称ens4f0
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        cmd = f"ifconfig {device_name} |grep ether |awk {{'print $2'}}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}')
            return rtn_outputs
        else:
            log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(cls, key_word='获取pf mac地址失败',
                                               description_word=f'{cmd}执行失败',
                                               expect_info=f'{cmd}执行成功',
                                               result_info=f'{rtn_outputs}')

    @classmethod
    def get_eth_ip(cls, caller_class, device_name: str, exec_addr: str = CmdExecuteAdressEnum.SERVER.value) ->list:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据device_name获取pf ip地址
        :param caller_class: 调用者的类
        :param device_name: 设备名称ens4f0
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        ip_list = []
        cmd = f"ifconfig {device_name} |grep inet |awk {{'print $2'}}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}')
            lines = rtn_outputs.splitlines()
            for line in lines:
                ip_list.append(line)
            return ip_list
        else:
            log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(caller_class, key_word='获取pf mac地址失败',
                                               description_word=f'{cmd}执行失败',
                                               expect_info=f'{cmd}执行成功',
                                               result_info=f'{rtn_outputs}')

    @classmethod
    def clear_eth_ip(cls, device_name: str, exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author: jinbo.zhang
        date  : 2024.12.30
        description: 根据device_name清除ip
        :param device_name: 设备名称ens4f0
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        cmd = f'ip -6 addr flush dev {device_name}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd,
                                                                                     cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'清除ipv6地址成功')
        else:
            log.info(f'清除ipv6地址失败')
            CommonOperation.create_bug_problem(cls, key_word='清除ipv6地址失败',
                                               description_word=f'清除ipv6地址失败',
                                               expect_info=f'清除ipv6地址成功',
                                               result_info=f'清除ipv6地址失败')
        cmd = f'ip addr flush dev {device_name}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd,
                                                                                     cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'清除ipv4地址成功')
        else:
            log.info(f'清除ipv4地址失败')
            CommonOperation.create_bug_problem(cls, key_word='清除ipv4地址失败',
                                               description_word=f'清除ipv4地址失败',
                                               expect_info=f'清除ipv4地址成功',
                                               result_info=f'清除ipv4地址失败')

    @classmethod
    def set_device_ifconfig(cls, device_name: str, status: str = 'down',
                            exec_addr: str = CmdExecuteAdressEnum.SERVER.value, check_ignore=False) -> None:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据device_name设置ifconfig
        :param device_name: 设备名称ens4f0
        :param status:
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        ifconfig_cmd = f'ifconfig {device_name} {status}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(ifconfig_cmd,
                                                                                     cmd_execute_address=exec_addr)
        if check_ignore:
            return
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{ifconfig_cmd}执行成功, outputs:{rtn_outputs}')
        else:
            log.info(f'command:{ifconfig_cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(cls, key_word=f'执行{ifconfig_cmd}命令',
                                               description_word=f'{ifconfig_cmd}执行失败',
                                               expect_info=f'{ifconfig_cmd}执行成功',
                                               result_info=f'{rtn_outputs}')

    @classmethod
    def get_device_link_status(cls, device_name: str,  exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author: jinbo.zhang
        date  : 2024.12.30
        description: 根据device_name获取link状态 ethtool ens1f0
        :param device_name: 设备名称ens4f0
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        cmd = f"ethtool {device_name} |grep 'Link detected' |awk {{'print $NF'}}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}')
            return rtn_outputs
        else:
            log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(cls, key_word=f'执行{cmd}命令',
                                               description_word=f'{cmd}执行失败',
                                               expect_info=f'{cmd}执行成功',
                                               result_info=f'{rtn_outputs}')

    @classmethod
    def driver_insmod_or_rmmod(cls, device_driver: str, insmod: bool = False, rmmod: bool = False,
                               exec_addr: str = CmdExecuteAdressEnum.SERVER.value, check_ignore: bool = False) -> None:
        if rmmod:
            rtn = CommonOperation.rmmod_driver(device_driver, exec_addr, force=True)
            if not check_ignore:
                if rtn:
                    log.info(f'驱动卸载成功')
                else:
                    log.info(f'驱动卸载失败')
                    CommonOperation.create_bug_problem(cls, key_word=f'驱动卸载',
                                                       description_word=f'驱动卸载',
                                                       expect_info=f'驱动卸载成功',
                                                       result_info=f'驱动卸载失败')
        if insmod:
            rtn = CommonOperation.modprobe_driver(device_driver, exec_addr)
            if not check_ignore:
                if rtn:
                    log.info(f'驱动加载成功')
                else:
                    log.info(f'驱动加载失败')
                    CommonOperation.create_bug_problem(cls, key_word=f'驱动加载',
                                                       description_word=f'驱动加载',
                                                       expect_info=f'驱动加载成功',
                                                       result_info=f'驱动加载失败')

    @classmethod
    def check_info_is_same(cls, result_info: str, expect_info: str, contain: bool = False,
                           result: bool = True) -> None:
        """
        author: jinbo.zhang
        date  : 2024.10.26
        description: 检查前后信息是否一致
        :param result_info:
        :param expect_info:
        :param contain: in
        :param result: result=Ture,info1和info2相同，result=False ,info1和info2不同
        return: 无返回值
        """
        if result:
            if contain:
                if expect_info in result_info:
                    log.info(f"实际值:{result_info}和预期信息:{expect_info}相同")
                else:
                    log.info(f"实际值:{result_info}和预期信息:{expect_info}不同")
                    CommonOperation.create_bug_problem(cls, key_word=f"配置信息检查失败",
                                                       description_word='配置信息检查失败',
                                                       expect_info='配置信息实际与预期一致',
                                                       result_info=f'result_info:{result_info}, '
                                                                   f'expect_info:{expect_info}')
            else:
                if result_info == expect_info:
                    log.info(f"实际值:{result_info}和预期信息:{expect_info}相同")
                else:
                    log.info(f"实际值:{result_info}和预期信息:{expect_info}不同")
                    CommonOperation.create_bug_problem(cls, key_word=f"配置信息检查失败",
                                                       description_word='配置信息检查失败',
                                                       expect_info='配置信息实际与预期一致',
                                                       result_info=f'result_info:{result_info}, '
                                                                   f'expect_info:{expect_info}')
        else:
            if contain:
                if expect_info not in result_info:
                    log.info(f"实际值:{result_info}和预期信息:{expect_info}不同，符合预期")
                else:
                    log.info(f"实际值:{result_info}和预期信息:{expect_info}一致，不符合预期")
                    CommonOperation.create_bug_problem(cls, key_word=f"LLDP信息检查成功",
                                                       description_word='LLDP信息检查成功',
                                                       expect_info='LLDP信息检查实际与预期不同',
                                                       result_info=f'result_info:{result_info}, '
                                                                   f'expect_info:{expect_info}')
            else:
                if result_info != expect_info:
                    log.info(f"实际值:{result_info}和预期信息:{expect_info}不同，符合预期")
                else:
                    log.info(f"实际值:{result_info}和预期信息:{expect_info}一致，不符合预期")
                    CommonOperation.create_bug_problem(cls, key_word=f"LLDP信息检查成功",
                                                       description_word='LLDP信息检查成功',
                                                       expect_info='LLDP信息检查实际与预期不同',
                                                       result_info=f'result_info:{result_info}, '
                                                                   f'expect_info:{expect_info}')

    @classmethod
    def reboot_and_check(cls) -> None:
        """
        author:         junfeng.he
        date:           2023.11.15
        description: 重启和检查
        """
        CommonOperation.concat_test_steps('reboot主机')
        server_ip, client_ip = CommonOperation.get_nic_logical_ip()
        reboot_result = HostOperation.host_reboot(ssh_ip=server_ip)
        if reboot_result == RtnStatusEnum.SUCCESS.value:
            log.info('重启操作完成，环境管理ip可重新ping通')
        else:
            if cls.test_direction_reverse:
                bmc_ip = CommandLineArgsParse.get_client_bmc_ip()
                uname = CommandLineArgsParse.get_client_bmc_uname()
                passwd = CommandLineArgsParse.get_client_bmc_passwd()
            else:
                bmc_ip = CommandLineArgsParse.get_server_bmc_ip()
                uname = CommandLineArgsParse.get_server_bmc_uname()
                passwd = CommandLineArgsParse.get_server_bmc_passwd()
            reboot_result = HostOperation.host_bmc_reboot(
                ssh_ip=server_ip, bmc_ip=bmc_ip, uname=uname, passwd=passwd)
            if reboot_result != RtnStatusEnum.SUCCESS.value:
                CommonOperation.create_bug_problem(
                    cls, key_word="bmc重启",
                    description_word=f'bmc重启失败，请检查环境')
        cls.driver_insmod_or_rmmod(cls.server_driver_name, insmod=True, exec_addr=CmdExecuteAdressEnum.SERVER.value)

    @classmethod
    def create_vf_device_and_driver(cls, server_device_name: str, vf_num: int = 1,
                                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author:         jianghe
        date:           2025.03.20
        description: 创建vf设备并加载驱动
        """
        pass

    @classmethod
    def open_watch_dog(cls, bdf, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value):
        # value =format(random.randint(0, 16 ** 320 - 1), '0100X')

        cmd = f"{constants.SCGBECLI64} -d {bdf}  custom sxe2 watchdog feed=2"
        code, out, err = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=cmd_execute_address)
        CliOperation.check_cli_success(cls, cmd, code, out, err)



if __name__ == '__main__':
    ScriptBaseResetCheck.run()
