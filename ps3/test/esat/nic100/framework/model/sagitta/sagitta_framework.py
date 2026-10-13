#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      sunql
description: 定义常量
"""
import csv
import json
import os
import time
import datetime
import subprocess
import re
import configparser
import random
from itertools import islice

import openpyxl

from framework.count_code import whitelist
from framework.model.framework_model_base import FrameworkModelBase
from framework.model.sagitta.constants import Testles_CASE_FILE, Testles_FAILED_CASE_FILE, Testles_ZENTO_CASE_FILE
from scripts.nic100.linux.rdma.rdma_kfunc import server_driver
from scripts.script_libs import log
from framework.libs import constants
from framework.model.sagitta import constants as tj_constants
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum, TestEntryEnum, NicNameEnum
from scripts.script_libs.ethtool_operation import EthtoolOperation
from scripts.script_libs.dcbtool_operation import DcbtoolOperation
from scripts.script_libs.file_operation import FileOperation
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.host_operation import HostOperation
from framework.libs import utils_new as utils
from scripts.script_libs import constants as scripts_constants
from scripts.script_libs.socket_operation import SocketOption
from scripts.nic100.linux.dpdk.dpdk_common_utils import DpdkCommonUtils


# 暂时没有用，后续用到再修改
PS3_LOG_PATH = "/var/log/ps3_log/"  # 日志存放路径
FWLOG_PATH = "/var/log/"  # 日志存放路径
NEW_FWLOG_PATH = "/root/var/log/"  # 日志存放路径

FpgaBitfileClass = {
    'UNKNOW': '00',
    'A': '0a',
    'B': '0b',
    'C': '0c',
    'D': '0d',
    'E': '0e',
    'F': '0f',
    'G': '10',
    'H': '11',
    'I': '12',
    'J': '13',
    'K': '14',
    'L': '15',
    'M': '16',
    'N': '17',
    'O': '18',
}


class FrameworkModel(FrameworkModelBase):
    switch_label = None
    server_nic_model = None
    client_nic_model = None
    # 定义测试环境存储信息
    env_dict = None
    server_ip, server_nic_name, server_nic_ifdex = [], [], []
    test_port = 22
    # 存一个网口与其bdf的全局变量
    dev_bdf_list = [{},{}]
    # 仅发包仪环境标记(server仅和发包仪连接，不连接其他服务器)
    client_renix_only_flag = False
    log_check_start_time = None
    framework_log_check_start_time = None
    log_check_keyword = ""
    fw_log_check = {}
    framework_log_check_ignore = False
    nicg = scripts_constants.DRV_SCGBE_PF

    __host_info = [constants.ENV_HOST_LABEL, constants.HOST_OWNER,
                        constants.TEST_CONFIG_SERVER_IP, constants.TEST_CONFIG_SERVER_NIC_IP,
                        constants.TEST_CONFIG_CLIENT_IP, constants.TEST_CONFIG_CLIENT_NIC_IP,
                        constants.TEST_CONFIG_SERVER_BMC_IP,
                        constants.TEST_CONFIG_SUNAME, constants.TEST_CONFIG_SUPASSWD,
                        constants.TEST_CONFIG_CLIENT_BMC_IP,
                        constants.TEST_CONFIG_CUNAME, constants.TEST_CONFIG_CUPASSWD,
                        constants.TEST_CONFIG_SERVER_COM_IP, constants.TEST_CONFIG_SERVER_COM_PORT,
                        constants.TEST_CONFIG_CLIENT_COM_IP, constants.TEST_CONFIG_CLIENT_COM_PORT]

    @staticmethod
    def __isvalid(param=None) -> bool:
        """
        author:      haibin.xu
        date:        2021-06-08 15:34:55
        description: 检查参数的有效性

        :param param: 待定检查的参数
        :return:     参数有效返回True，否则返回False
        """
        if param is None:
            rtn_check_result = False
        elif isinstance(param, str) and ('' == param):
            rtn_check_result = False
        elif isinstance(param, list) and ([] == param):
            rtn_check_result = False
        elif isinstance(param, dict) and ({} == param):
            rtn_check_result = False
        elif isinstance(param, tuple) and (() == param):
            rtn_check_result = False
        elif isinstance(param, bool):
            rtn_check_result = param
        else:
            rtn_check_result = True

        return rtn_check_result

    @classmethod
    def get_project_parameters(cls, frame_run_dict: dict) -> None:
        """
        获取测试项目参数
        :return:
        """
        cls.frame_run_dict = frame_run_dict
        cls.test_entry = cls.frame_run_dict['config_dict'].get(constants.ENV_TEST_ENTRY)
        if not cls.__isvalid(cls.test_entry):
            log.error('Fail to get test entry.')
            exit(1)

        cls.test_object = cls.frame_run_dict['config_dict'].get(constants.ENV_TEST_OBJECT)
        if not cls.__isvalid(cls.test_object):
            log.error('Fail to get test object.')
            exit(1)

        cls.switch_label = cls.frame_run_dict['config_dict'].get(tj_constants.ENV_SWITCH_LABEL)
        if not cls.__isvalid(cls.switch_label):
            log.error('Fail to get switch_label.')
            exit(1)

        if cls.test_entry == 'switch' and (cls.switch_label in ['default', 'None']):
            log.error('switch_label value is fail')
            exit(1)

        cls.server_nic_model = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL)
        if not cls.__isvalid(cls.server_nic_model):
            log.error('Fail to get server_nic_model: {}.'.format(cls.server_nic_model))
            exit(1)

        cls.client_nic_model = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        if not cls.__isvalid(cls.client_nic_model):
            log.error('Fail to get client_nic_model: {}.'.format(cls.client_nic_model))
            exit(1)
        cls.test_port = cls.frame_run_dict['ip_dict'].get(constants.ENV_TEST_PORT)
        log.info("==>test_port:{}".format(cls.test_port))

    @classmethod
    def brefore_test(cls) -> None:
        """
        测试前操作
        :return:
        """
        if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.UEFI_MODE]:
            log.info("uefi测试模式，无需进行os下的配置与检查")
            return

        log.info("sagitta before test start")
        if cls.frame_run_dict["config_dict"]["test_platform"] == "simu_platform":
            log.info("当前选择的是模拟平台")
            cls.__sagitta_simu_check_and_recover()

        log.info("env tools update")
        cls.__sagitta_env_tools_update()

        if (cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) not in [tj_constants.SINGLE_MODE, tj_constants.DPDK_MODE, tj_constants.DPDK_AUTO_MODE] and
                cls.__get_framework_bug_stop_flag() == "1"):
            host_os_server, host_os_client = CommonOperation.get_nic_os()
            server_ip, client_ip = CommonOperation.get_nic_logical_ip()
            fpga_bit_version = CommonOperation.get_cli_fpga_bit_version(server_os_type=host_os_server,
                                                                        server_ip=server_ip, test_port=cls.test_port)
            CommonOperation.set_fpga_bit_version(value=fpga_bit_version)
            pf_device_name_server, pf_device_name_client, dev_dict = \
                CommonOperation.get_target_test_device(cls.test_port)
            if pf_device_name_client == '' or pf_device_name_server == '':
                cls.__check_link_status()
                log.warning(f'/root/sxetest/framework_bug_stop_flag.txt已置位，并且server和client pf不通!!!')
                log.warning("上次跑测两端已不通，已导致框架停止测试，并且当前检查也不通，为了避免破坏现场和日志丢失不再进行跑测！！")
                exit(1)
            else:
                log.warning(f'/root/sxetest/framework_bug_stop_flag已置位，但是server和client pf已通，继续测试...')

        if not cls.__check_env_config():
            log.error('################## env_config.ini 与 ps3server记录的节点信息不一致 ###################')
            exit(1)

        # 检查生产信息，如果没有mac，需要配置，重新加载驱动
        if not cls.__check_mac_is_available():
            log.error("################# 尝试自动回复后，环境仍然异常，不可进行测试，请手动确认并恢复环境 #################")
            exit(1)

        # 清除framework_bug_stop_flag
        cls.__set_framework_bug_stop_flag("0")
        cls.__dmesg_check_init()
        cls.__synchronize_ps3server_time()
        cls.framework_log_check_start_time, cls.log_check_start_time = cls.get_host_time()

        need_log_collect = cls.is_need_log_collect_before_test()
        if need_log_collect:
            log.info("#################### 检测到上次测试异常终止，开始收集环境日志 ###########################")
            cls.frame_run_dict['test_start_timestamp'] -= 600
            cls.frame_run_dict['collect_log'].make_log_root_directory_in_log_server()
            log_script_path = cls.frame_run_dict['collect_log'].make_script_directory_in_log_server(script_name="before_test_" + str(time.time()))
            collect_log_flag = cls.frame_run_dict['collect_log'].collect_log()
            log.info(f"==>上个测试单残留环境日志采集，collect_log_flag:{collect_log_flag}")

        log.info("开始清理server端日志")
        cls.frame_run_dict['collect_log'].clear_log(cls.frame_run_dict['ip_dict']['server_ip'], cls.test_port,
                                                    CmdExecuteAdressEnum.SERVER.value, cls.server_nic_model)

        if cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]:
            log.info('发包仪环境，server仅与client发包仪连接，跳过client日志清理')
        else:
            log.info("开始清理client端日志")
            cls.frame_run_dict['collect_log'].clear_log(cls.frame_run_dict['ip_dict']['client_ip'], cls.test_port,
                                                        CmdExecuteAdressEnum.CLIENT.value, cls.client_nic_model)

        server_ddp_switch, client_ddp_switch = CommonOperation.get_ddp_switch()
        if server_ddp_switch == 'on':
            log.info("set ddp on")
            cls.__sagitta_ddp_switch()


        log.info("firewalld policy update")
        cls.__firewalld_policy_update()

        log.info("config core dump")
        cls.__config_core_dump()

        log.info("测试先检查是否有之前已有fw core，仅记录不报bug")
        server_fw_core = cls.check_fw_core(CmdExecuteAdressEnum.SERVER.value, first=True)
        client_fw_core = cls.check_fw_core(CmdExecuteAdressEnum.CLIENT.value, first=True)

        log.info("串口日志重新打开")
        cls.__restart_serial_port_file()

        cls.__upgrade_version()

        cls.__update_com_mode()

        # 如果是release版本，则自动打开自动日志导出功能
        cls.auto_log_check()

        if not cls.__sagitta_check_physical_env():
            log.error('################## env check failed ###################')
            # exit(1)

    @classmethod
    def after_test(cls) -> None:
        """
        测试后操作
        :return:
        """
        if cls.frame_run_dict['config_dict'].get(constants.ENV_TEST_OBJECT) == constants.ENV_RUN_MODE_WITH_BG_TRAFFIC:
            server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
            client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
            cls.__enable_background_traffic(enable_bt=False, server_mgr_ip=server_mgr_ip,
                                            client_mgr_ip=client_mgr_ip)

    @classmethod
    def after_test_round(cls) -> None:
        """
        每轮测试后操作
        :return:
        """
        pass

    @classmethod
    def __force_clear_virtual_environment(cls):
        """
        清理环境
        """
        server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
        host_os_server = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL)
        host_os_client = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        if cls.server_nic_model == "windows":
            log.info_caller(f"检查{server_mgr_ip}环境中网卡信息是否初始化")
            CommonOperation.clean_virtual_info(ssh_ip=server_mgr_ip,
                                               host_os_server=host_os_server,
                                               host_os_client=host_os_client,
                                               cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                               test_port=cls.test_port)
            CommonOperation.clean_vm_switch(ssh_ip=server_mgr_ip,
                                            host_os_server=host_os_server,
                                            host_os_client=host_os_client,
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                            test_port=cls.test_port)
        if cls.client_nic_model == "windows":
            log.info_caller(f"检查{client_mgr_ip} 环境中的网卡信息是否初始化")
            CommonOperation.clean_virtual_info(ssh_ip=client_mgr_ip,
                                               host_os_server=host_os_server,
                                               host_os_client=host_os_client,
                                               cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                               test_port=cls.test_port)
            CommonOperation.clean_vm_switch(ssh_ip=client_mgr_ip,
                                            host_os_server=host_os_server,
                                            host_os_client=host_os_client,
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                            test_port=cls.test_port)

    @classmethod
    def __clean_scapy_screen(cls):
        """
        author：junfeng.he
        date: 2025.04.25
        description: 清除screen
        :return:
        """
        # 创建screen会话，在内部进行编译
        vm, rpc_port = CommonOperation.get_node_info_from_path()
        log.info("vm:{},rpc_port:{}".format(vm, rpc_port))
        scapy_screen_name = "scapy_{}".format(vm)

        server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)

        for target_host_info in [[server_mgr_ip, CmdExecuteAdressEnum.SERVER.value],
                                 [client_mgr_ip, CmdExecuteAdressEnum.CLIENT.value]]:
            target_host_ip = target_host_info[0]
            target_execute_address = target_host_info[1]

            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and target_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue

            exec_command = "screen -list"
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                cmd_execute_address=target_execute_address, print_steps=False, print_outputs=False)
            # 退出并清除dpdk_testpmd所在screen会话
            screen_scapys = re.findall(rf"(\d+.{scapy_screen_name})", cmd_output)
            for screen_scapy in screen_scapys:
                exec_command = "screen -S {} -X quit".format(screen_scapy)
                cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    cmd_execute_address=target_execute_address, print_steps=False, print_outputs=False)
            exec_command = "screen -wipe"
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                cmd_execute_address=target_execute_address, print_steps=False, print_outputs=False)

    @classmethod
    def __clean_vlan(cls):
        """
        author：wei.yuan1
        date: 2023.12.28
        description: 清除vlan
        :return:
        """
        server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
        host_os_server = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL)
        host_os_client = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        server_relation_list, client_relation_list = CommonOperation.get_nic_relationships(
            current_config=scripts_constants.NIC_CONFIG_BK_PATH)

        if 'none' in server_relation_list or 'none' in client_relation_list:
            log.warning("env_config.ini中网口关系配置中存在none，不做清理vlan的操作")
            return False
        for server_device, client_device in zip(server_relation_list, client_relation_list):
            if host_os_server == "windows":
                cls.clean_vlan(server_device, server_mgr_ip, cls.test_port, host_os_server, host_os_client,
                               CmdExecuteAdressEnum.SERVER.value)
            if host_os_client == "windows":
                cls.clean_vlan(client_device, client_mgr_ip, cls.test_port, host_os_server, host_os_client,
                               CmdExecuteAdressEnum.CLIENT.value)

    @staticmethod
    def clean_vlan(device_name, ssh_ip, test_port, os_server, os_client, execute_address):
        clean_vlan_command = f"set-netadapter -name {device_name} -VlanID 0 -confirm:$false"
        status, out, err = CommandOperation.execute_command_multi_times(
            cmd=clean_vlan_command, cmd_execute_address=execute_address, ssh_ip=ssh_ip, ssh_port=str(test_port),
            host_os_client=os_client, host_os_server=os_server, timeout=30)
        if status != RtnStatusEnum.SUCCESS.value:
            return False

    @classmethod
    def __set_rdma_so_log_level(cls):
        server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
        host_os_server = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL)
        host_os_client = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)

        # server
        cls.set_rdma_so_log_level(server_mgr_ip, cls.test_port, host_os_server, host_os_client,
                                   CmdExecuteAdressEnum.SERVER.value)
        # client
        if cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]:
            log.info('single mode或发包仪环境，跳过client命令执行')
            return
        else:
            cls.set_rdma_so_log_level(client_mgr_ip, cls.test_port, host_os_server, host_os_client,
                                       CmdExecuteAdressEnum.CLIENT.value)

    @staticmethod
    def set_rdma_so_log_level(ssh_ip, test_port, os_server, os_client, execute_address):
        cmd = f"cat /etc/profile|grep SXE2_RDMA_LOG_LEVEL|grep -v '#'"
        status, out, err = CommandOperation.execute_command_multi_times(
            cmd=cmd, cmd_execute_address=execute_address, ssh_ip=ssh_ip, ssh_port=str(test_port),
            host_os_client=os_client, host_os_server=os_server, test_times=1, timeout=5)
        res = re.findall(r'SXE2_RDMA_LOG_LEVEL=(\w+)', out)
        if res:
            log_level = res[-1]
            log.info(f'当前rdma驱动用户态日志等级为：{log_level}, 无需修改')
        else:
            log.info(f'修改rdma驱动用户态日志等级为：ERROR')
            cmd = f'grep -q "^export SXE2_RDMA_LOG_LEVEL=ERROR" /etc/profile || echo "export SXE2_RDMA_LOG_LEVEL=ERROR" | sudo tee -a /etc/profile'
            status, out, err = CommandOperation.execute_command_multi_times(
                cmd=cmd, cmd_execute_address=execute_address, ssh_ip=ssh_ip, ssh_port=str(test_port),
                host_os_client=os_client, host_os_server=os_server, timeout=30)
            cmd = f"source /etc/profile"
            status, out, err = CommandOperation.execute_command_multi_times(
                cmd=cmd, cmd_execute_address=execute_address, ssh_ip=ssh_ip, ssh_port=str(test_port),
                host_os_client=os_client, host_os_server=os_server, timeout=30)

    @classmethod
    def before_exec_script(cls) -> None:
        """
        每个用例执行前操作
        :return:
        """
        cls.log_collect_status_update(stage="start")
        if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.UEFI_MODE]:
            log.info("uefi测试模式，无需进行os下的配置与检查")
            return True
        # 同步对端时间
        cls.__dmesg_check_init()
        # cls.__synchronize_peer_time()
        cls.__force_clear_env_vf_vlan()
        cls.__force_clear_dcb()
        cls.__force_clear_virtual_environment()
        cls.__clean_vlan()
        cls.__check_adapter_number()
        cls.__clean_scapy_screen()
        cls.__set_rdma_so_log_level()
        # cls.__watchdog_enable()
        cls.__clean_pcie_status()
        if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) not in \
                [tj_constants.SINGLE_MODE, tj_constants.DPDK_MODE, tj_constants.DPDK_AUTO_MODE]:
            log.info("config nic eswitch mode")
            CommonOperation.set_device_switchdev(test_port=cls.test_port)
        # # 填充测试测试框架运行参数Testles_autotest/framework/libs/sagitta_test_parameters.json
        # cls.fill_Testles_test_parameters()
        # # 填充测试测试用例表格Testles_autotest/scripts/case_script_lists/ib_auto_tc.csv
        # cls.fill_Testles_test_case()
        pass

    @classmethod
    def after_exec_script(cls) -> None:
        """
        每个用例执行后操作
        :return:
        """
        cls.log_collect_status_update(stage = "after")

    @classmethod
    def log_collect_status_update(cls, stage: str = "start") -> None:
        """
        每个用例执行后操作
        :return:
        """
        if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.UEFI_MODE]:
            log.info("uefi测试模式，无需进行os下的配置与检查")
            return
        # 根据测试结果，设置日志采集状态，后续框架检查若发现日志没有完成采集[start or need]，则先采集一次
        current_timestamp = time.time()
        current_format_time = time.localtime(current_timestamp)
        readable_time = time.strftime('%Y%m%d%H%M%S', current_format_time)
        if cls.server_nic_model == 'windows':
            env_config_path = tj_constants.WINDOWS_FILE_PATH_ROOT
            root = "Administrator"
            bin_path = env_config_path
        else:
            env_config_path = tj_constants.LINUX_FILE_PATH_ROOT
            root = "root"
            bin_path = "/usr/bin/"
        target_host_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        if stage == "start":
            exec_command = f"echo 'start：{readable_time}' > /root/sxetest/log_collect_status.txt"
        else:
            if cls.frame_run_dict['script_rtn_code'] in [constants.RETURN_CODE_FAIL, constants.RETURN_CODE_TIMEOUT, constants.RETURN_CODE_EXCEPTION]:
                exec_command = f"echo 'need collect log：{readable_time}' > /root/sxetest/log_collect_status.txt"
            else:
                exec_command = f"echo 'skip collect log：{readable_time}' > /root/sxetest/log_collect_status.txt"
        rtn_code,  rtn_out, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command,
            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'{root}',
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_CLIENT_NIC_MODEL))

    @classmethod
    def is_need_log_collect_before_test(cls) -> bool:
        """
        每个测试单清理环境日志时检查
        :return:
        """
        if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.UEFI_MODE]:
            log.info("uefi测试模式，无需进行os下的配置与检查")
            return False
        # 检查若发现日志没有完成采集[start or need]
        if cls.server_nic_model == 'windows':
            env_config_path = tj_constants.WINDOWS_FILE_PATH_ROOT
            root = "Administrator"
            bin_path = env_config_path
        else:
            env_config_path = tj_constants.LINUX_FILE_PATH_ROOT
            root = "root"
            bin_path = "/usr/bin/"
        target_host_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)

        exec_command = f"cat /root/sxetest/log_collect_status.txt"
        rtn_code, rtn_out, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command,
            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'{root}',
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_CLIENT_NIC_MODEL))
        if "start" in rtn_out or "need" in rtn_out:
            return True
        return False


    @classmethod
    def after_check_bug(cls) -> None:
        """
        每个用例执行后 判断是否停止测试后 执行的操作
        :return:
        """
        pass

    @classmethod
    def before_framework_exit(cls) -> str:
        """
        框架退出前，还要作的步骤
        :return:
        """
        desc = ""
        if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.UEFI_MODE]:
            log.info("uefi测试模式，无需进行os下的配置与检查")
            return desc

        # 日志重复检查
        desc += cls.__check_log_repeat()
        return desc

    @classmethod
    def getstatusoutput(cls, exec_command) -> tuple:
        """
        每个用例执行后 判断是否停止测试后 执行的操作
        :return:
        """
        iretry = 5
        rtn_code, result = -1, "命令未执行"
        while iretry:
            rtn_code, result = subprocess.getstatusoutput(exec_command)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                return rtn_code, result
            else:
                iretry -= 1
                if "Connection closed by remote host" in result:
                    time.sleep(1)
        return rtn_code, result

    @classmethod
    def __check_memory_leak(cls) -> None:
        """
        通过串口命令检查打印内存信息
        /mm show statistic
        /mm show block
        :return:
        """
        server_host_ip, client_host_ip = CommonOperation.get_nic_logical_ip(
            scripts_constants.NIC_CONFIG_BK_PATH)
        server_serial_port_pos, client_serial_port_pos = CommonOperation.get_serial_port_pos(scripts_constants.NIC_CONFIG_BK_PATH)
        log.info(f"server_serial_port_pos:{server_serial_port_pos}")
        log.info(f"client_serial_port_pos:{client_serial_port_pos}")
        for index, infos in enumerate([server_serial_port_pos, client_serial_port_pos]):
            if "," in infos:
                info_list = infos.split(",")
                for index, temp in enumerate(info_list):
                    if len(temp) < 5:
                        info_list[index] = info_list[0][:-4] + temp
            else:
                info_list = [infos]
            for info in info_list:
                if "@" in info:
                    items = info.split("_")
                    log_server = items[0].replace("developer", "framework")
                    com_ip = items[1]
                    com_port = items[2]
                    if index == 0:
                        desc = f"server_{server_host_ip}_"
                    else:
                        desc = f"client_{client_host_ip}_"
                    log.info(f"{desc}串口命令打印==>")

                    cmd = f'/mm show statistic'
                    output = SocketOption.exec_socket_cmd(cmd, com_ip, com_port, retry_max=0)
                    if "Stack" not in output:
                        output = SocketOption.exec_socket_cmd(cmd, com_ip, com_port, retry_max=0)

                    cmd = f'/mm show block'
                    output = SocketOption.exec_socket_cmd(cmd, com_ip, com_port, retry_max=0)
                    if "Alloc_Type" not in output:
                        output = SocketOption.exec_socket_cmd(cmd, com_ip, com_port, retry_max=0)

    @classmethod
    def __relink_by_serial_port(cls) -> None:
        """
        通过串口命令重新建联
        :return:
        """
        server_host_ip, client_host_ip = CommonOperation.get_nic_logical_ip(
            scripts_constants.NIC_CONFIG_BK_PATH)
        server_serial_port_pos, client_serial_port_pos = CommonOperation.get_serial_port_pos(scripts_constants.NIC_CONFIG_BK_PATH)
        server_device_list, client_device_list = CommonOperation.get_nic_relationships(scripts_constants.NIC_CONFIG_BK_PATH)
        log.info(f"server_serial_port_pos:{server_serial_port_pos}")
        log.info(f"client_serial_port_pos:{client_serial_port_pos}")
        log.info(f"server_device_list:{server_device_list}")
        log.info(f"client_device_list:{client_device_list}")
        for index, infos in enumerate([server_serial_port_pos]):
            if "," in infos:
                info_list = infos.split(",")
                for index, temp in enumerate(info_list):
                    if len(temp) < 5:
                        info_list[index] = info_list[0][:-4] + temp
            else:
                info_list = [infos]
            for info in info_list:
                if "@" in info:
                    items = info.split("_")
                    log_server = items[0].replace("developer", "framework")
                    com_ip = items[1]
                    com_port = items[2]
                    if index == 0:
                        desc = f"server_{server_host_ip}_"
                    else:
                        desc = f"client_{client_host_ip}_"

                    for server_device in server_device_list:
                        exec_command = f'ip a show dev {server_device}'
                        rtn_code, outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                            ssh_username=f'root',
                            ssh_ip=cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP),
                            ssh_port=str(cls.test_port),
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL))
                        if 'state UP' not in outputs:
                            log.warning(f'{CmdExecuteAdressEnum.SERVER.value} {server_device} 状态为down, 尝试重新建联')
                            if server_device.endswith(f'f0'):
                                port_index = 3
                            elif server_device.endswith(f'f1'):
                                port_index = 2
                            elif server_device.endswith(f'f2'):
                                port_index = 1
                            elif server_device.endswith(f'f3'):
                                port_index = 0

                            log.info(f"{desc}串口命令打印==>")
                            cmd = f'/debug custom sxe2 linkset port={port_index} speed=1 fec=0 fc=0'
                            output = SocketOption.exec_socket_cmd(cmd, com_ip, com_port, retry_max=0)

    @classmethod
    def __core_reset(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        core reset
        :return:
        """
        server_command = f"{cls.nicg}cli show"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            server_command, cmd_execute_address=cmd_execute_address, ssh_port=str(cls.test_port))
        bdfs = re.findall(r"\s+\|(\S\S\S\S:\S\S:\S\S.\S)", rtn_outputs)
        if bdfs:
            server_command = f"{cls.nicg}cli -d {bdfs[0]} reset type=0"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, cmd_execute_address=cmd_execute_address, ssh_port=str(cls.test_port))

    @classmethod
    def __watchdog_enable(cls) -> None:
        """
        core reset
        :return:
        """
        for cmd_execute_address in [CmdExecuteAdressEnum.SERVER.value, CmdExecuteAdressEnum.CLIENT.value]:

            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue

            exec_command = f"cat /root/sxetest/publish_version/release_version.txt"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address, ssh_port=str(cls.test_port))
            if 'makemode:release' in rtn_outputs:
                log.warning(f"release版本不支持custom命令：{cls.nicg}cli -d <bdf> custom {cls.nicg} watchdog feed=2")
                continue

            server_command = f"{cls.nicg}cli show"
            rtn_code, show_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, cmd_execute_address=cmd_execute_address, ssh_port=str(cls.test_port))
            bdfs = re.findall(r"\s+\|(\S\S\S\S:\S\S:\S\S.\S)", show_outputs)
            if bdfs:
                server_command = f"{cls.nicg}cli -d {bdfs[0]} custom {cls.nicg} watchdog feed=2"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    server_command, cmd_execute_address=cmd_execute_address, ssh_port=str(cls.test_port))
                if 'Controller 1' in show_outputs or "Device 1" in show_outputs:
                    log.info("============> 多卡环境,最后一张卡也要配置")
                    server_command = f"{cls.nicg}cli -d {bdfs[-1]} custom {cls.nicg} watchdog feed=2"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        server_command, cmd_execute_address=cmd_execute_address, ssh_port=str(cls.test_port))

    @classmethod
    def __check_pcie_status(cls) -> tuple:
        """
        get pcie status
        :return:
        """
        log.info("==> check_pcie_status:")
        need_report = False
        res = ""
        ue_whitelist = ["UnsupReq"]
        ce_whitelist = ["NonFatalErr", "AdvNonFatalErr"]
        server_driver_name, client_sriver_name = CommonOperation.get_nic_driver_name(scripts_constants.NIC_CONFIG_PATH)
        for cmd_execute_address in [CmdExecuteAdressEnum.SERVER.value, CmdExecuteAdressEnum.CLIENT.value]:

            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [
                tj_constants.SINGLE_MODE]) and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue
            if (cls.nicg not in server_driver_name and CmdExecuteAdressEnum.SERVER.value) or (cls.nicg not in client_sriver_name and CmdExecuteAdressEnum.CLIENT.value):
                continue
            server_command = f"{cls.nicg}cli show"
            rtn_code, show_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, cmd_execute_address=cmd_execute_address, ssh_port=str(cls.test_port))
            bdfs = re.findall(r"\s+\|(\S\S\S\S:\S\S:\S\S.\S)", show_outputs)
            if bdfs:
                for bdf in bdfs:
                    status, ue_err_list, ce_err_list = CommonOperation.get_pcie_aer_ue_ce_status(bdf, cmd_execute_address)
                    if ue_err_list:
                        res += cmd_execute_address + f"-{bdf}-ue_err_list:{ue_err_list};"
                        for item in ue_err_list:
                            if item not in ue_whitelist:
                                need_report = True
                    if ce_err_list:
                        res += cmd_execute_address + f"-{bdf}-ce_err_list:{ce_err_list};"
                        for item in ce_err_list:
                            if item not in ce_whitelist:
                                need_report = True
        return need_report, res

    @classmethod
    def __clean_pcie_status(cls) -> None:
        """
        clean_pcie_status
        :return:
        """
        log.info("==> clean_pcie_status:")
        server_driver_name, client_sriver_name = CommonOperation.get_nic_driver_name(scripts_constants.NIC_CONFIG_PATH)
        for cmd_execute_address in [CmdExecuteAdressEnum.SERVER.value, CmdExecuteAdressEnum.CLIENT.value]:
            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [
                tj_constants.SINGLE_MODE]) and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue
            if (cls.nicg not in server_driver_name and CmdExecuteAdressEnum.SERVER.value) or (cls.nicg not in client_sriver_name and CmdExecuteAdressEnum.CLIENT.value):
                continue
            server_command = f"{cls.nicg}cli show"
            rtn_code, show_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, cmd_execute_address=cmd_execute_address, ssh_port=str(cls.test_port))
            bdfs = re.findall(r"\s+\|(\S\S\S\S:\S\S:\S\S.\S)", show_outputs)
            if bdfs:
                for bdf in bdfs:
                    rp_bdf = CommonOperation.get_rp_bdf_for_ep_bdf(bdf, exec_addr=cmd_execute_address)
                    if rp_bdf:
                        CommonOperation.clean_aer_status(rp_bdf, exec_addr=cmd_execute_address)
                        CommonOperation.disable_pcie_error_reporting(rp_bdf,exec_addr=cmd_execute_address)

                    CommonOperation.clean_aer_status(bdf, exec_addr=cmd_execute_address)


    @classmethod
    def __check_link_status(cls) -> bool:
        """
        通过串口命令检查链路状态
        /debug custom sxe2 linkstatusshow port=x
        :return:
        """
        have_link_issue = False
        server_host_ip, client_host_ip = CommonOperation.get_nic_logical_ip(
            scripts_constants.NIC_CONFIG_BK_PATH)
        server_serial_port_pos, client_serial_port_pos = CommonOperation.get_serial_port_pos(
            scripts_constants.NIC_CONFIG_BK_PATH)
        target_port_dict = {}
        server_platfroms, client_platfroms = CommonOperation.get_platform(scripts_constants.NIC_CONFIG_BK_PATH)
        if "," in server_platfroms:
            server_platfrom_list = server_platfroms.split(",")
        else:
            server_platfrom_list = [server_platfroms]

        if "," in client_platfroms:
            client_platfrom_list = client_platfroms.split(",")
        else:
            client_platfrom_list = [client_platfroms]

        # PCIE2*25 仅支持01口，OCP2口卡仅支持02口 OCP4口卡支持0123
        target_port_dict[0] = []
        for index, target_platfrom in enumerate(server_platfrom_list):
            target_port_list = []
            if "pciex2" in target_platfrom.lower():
                target_port_list = [0, 1]
            if "ocpx2" in target_platfrom.lower():
                target_port_list = [0, 2]
            if "ocpx4" in target_platfrom.lower():
                target_port_list = [0, 1, 2, 3]
            target_port_dict[0].append(target_port_list.copy())
        target_port_dict[1] = []
        for index, target_platfrom in enumerate(client_platfrom_list):
            target_port_list = []
            if "pciex2" in target_platfrom.lower():
                target_port_list = [0, 1]
            if "ocpx2" in target_platfrom.lower():
                target_port_list = [0, 2]
            if "ocpx4" in target_platfrom.lower():
                target_port_list = [0, 1, 2, 3]
            target_port_dict[1].append(target_port_list.copy())

        log.info(f"server_serial_port_pos:{server_serial_port_pos}")
        log.info(f"client_serial_port_pos:{client_serial_port_pos}")
        for index, infos in enumerate([server_serial_port_pos, client_serial_port_pos]):
            if "," in infos:
                info_list = infos.split(",")
                for index, temp in enumerate(info_list):
                    if len(temp) < 5:
                        info_list[index] = info_list[0][:-4] + temp
            else:
                info_list = [infos]
            for i, info in enumerate(info_list):
                if "@" in info:
                    items = info.split("_")
                    log_server = items[0].replace("developer", "framework")
                    com_ip = items[1]
                    com_port = items[2]
                    if index == 0:
                        exec_command = f"cat /root/sxetest/publish_version/release_version.txt"
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username="root",
                            ssh_ip=server_host_ip, ssh_port=str(cls.test_port),
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                        )
                        if 'release' in rtn_outputs:
                            log.warning("release版本不支持串口命令：/debug custom sxe2 linkstatusshow port=")
                            # for port_id in target_port_dict[index][i]:
                            #     log.info(f"release版本查询port{port_id} mac状态：/comm show reg type=A addr=0x8a00e05c width=32")
                            #     cmd = '/comm show reg type=A addr=0x8a00e05c width=32'
                            #     output = SocketOption.exec_socket_cmd(cmd, com_ip, com_port, filter=False, retry_max=0)
                            #     if output == '0':
                            #         log.info(f'port{port_id} mac状态为 UP')
                            #     else:
                            #         log.warning(f'port{port_id} mac状态为 DOWN')

                            continue
                        desc = f"server_{server_host_ip}_"
                    else:
                        exec_command = f"cat /root/sxetest/publish_version/release_version.txt"
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                            ssh_username="root",
                            ssh_ip=client_host_ip, ssh_port=str(cls.test_port),
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                        )
                        if 'release' in rtn_outputs:
                            log.warning("release版本不支持串口命令：/debug custom sxe2 linkstatusshow port=")
                            continue
                        desc = f"client_{client_host_ip}_"
                    log.info(f"{desc}串口命令打印==>")
                    try:
                        for port_id in target_port_dict[index][i]:
                            cmd = f'/debug custom sxe2 linkstatusshow port={port_id}'
                            output = SocketOption.exec_socket_cmd(cmd, com_ip, com_port, filter=False, retry_max=0)
                            if "SHOW DONE" not in output:
                                output = SocketOption.exec_socket_cmd(cmd, com_ip, com_port, filter=False, retry_max=0)
                            if "status=[1]pcs_status=[1]" in output:
                                log.info(f"{desc}port_{port_id}链路状态正常")
                            elif "pcs_status=" not in output:
                                log.warning(f"{desc}port_{port_id}链路状态未获取到")
                            else:
                                log.info(f"{desc}port_{port_id}链路状态异常！！")
                                have_link_issue = True

                        cmd = f'/debug custom sxe2 pcietrace cnt=64'
                        output = SocketOption.exec_socket_cmd(cmd, com_ip, com_port, filter=False, retry_max=0)
                        cmd = f'/debug custom sxe2 pcietrace cnt=32'
                        output = SocketOption.exec_socket_cmd(cmd, com_ip, com_port, filter=False, retry_max=0)

                    except Exception as e:
                        log.error(str(e))
        log.info("注意：PCIE2*25 仅支持port 0，1（对应pf1，0），OCP2卡仅支持port 0，2（对应pf1，0） OCP4卡支持port 0,1,2,3（对应pf3,2,1,0），请核对")
        return have_link_issue

    @classmethod
    def __excute_com_cmd(cls, execute_address, cmd, mark, all_port: bool=False) -> bool:
        """
        执行串口命令
        cmd = f'/debug custom sxe2  coredump trigger'
        mark = "SHOW DONE"
        :return:
        """
        result = False
        server_host_ip, client_host_ip = CommonOperation.get_nic_logical_ip(
            scripts_constants.NIC_CONFIG_BK_PATH)
        server_serial_port_pos, client_serial_port_pos = CommonOperation.get_serial_port_pos(
            scripts_constants.NIC_CONFIG_BK_PATH)
        target_port_dict = {}
        server_platfroms, client_platfroms = CommonOperation.get_platform(scripts_constants.NIC_CONFIG_BK_PATH)
        if "," in server_platfroms:
            server_platfrom_list = server_platfroms.split(",")
        else:
            server_platfrom_list = [server_platfroms]

        if "," in client_platfroms:
            client_platfrom_list = client_platfroms.split(",")
        else:
            client_platfrom_list = [client_platfroms]

        # PCIE2*25 仅支持01口，OCP2口卡仅支持02口 OCP4口卡支持0123
        target_port_dict[0] = []
        for index, target_platfrom in enumerate(server_platfrom_list):
            target_port_list = []
            if "pciex2" in target_platfrom.lower():
                target_port_list = [0, 1]
            if "ocpx2" in target_platfrom.lower():
                target_port_list = [0, 2]
            if "ocpx4" in target_platfrom.lower():
                target_port_list = [0, 1, 2, 3]
            target_port_dict[0].append(target_port_list.copy())
        target_port_dict[1] = []
        for index, target_platfrom in enumerate(client_platfrom_list):
            target_port_list = []
            if "pciex2" in target_platfrom.lower():
                target_port_list = [0, 1]
            if "ocpx2" in target_platfrom.lower():
                target_port_list = [0, 2]
            if "ocpx4" in target_platfrom.lower():
                target_port_list = [0, 1, 2, 3]
            target_port_dict[1].append(target_port_list.copy())

        log.info(f"server_serial_port_pos:{server_serial_port_pos}")
        log.info(f"client_serial_port_pos:{client_serial_port_pos}")
        if execute_address == CmdExecuteAdressEnum.SERVER.value:
            infos = server_serial_port_pos
        else:
            infos = client_serial_port_pos

        if "," in infos:
            info_list = infos.split(",")
            for index, temp in enumerate(info_list):
                if len(temp) < 5:
                    info_list[index] = info_list[0][:-4] + temp
        else:
            info_list = [infos]
        for i, info in enumerate(info_list):
            if "@" in info:
                items = info.split("_")
                log_server = items[0].replace("developer", "framework")
                com_ip = items[1]
                com_port = items[2]
                if index == 0:
                    desc = f"server_{server_host_ip}_"
                else:
                    desc = f"client_{client_host_ip}_"
                log.info(f"{desc}串口命令打印==>")
                try:
                    if all_port:
                        for port_id in target_port_dict[index][i]:
                            cmd = cmd.replace("port_id", port_id)
                            output = SocketOption.exec_socket_cmd(cmd, com_ip, com_port, filter=False, retry_max=0)
                            if mark not in output:
                                log.warning("第一次执行可能未成功，再执行一次")
                                output = SocketOption.exec_socket_cmd(cmd, com_ip, com_port, filter=False, retry_max=0)
                                if mark not in output:
                                    log.error("未获取到命令执行标识，可能执行失败了")
                                else:
                                    result = True
                            else:
                                result = True
                    else:
                        output = SocketOption.exec_socket_cmd(cmd, com_ip, com_port, filter=False, retry_max=0)
                        if mark not in output:
                            log.warning("第一次执行可能未成功，再执行一次")
                            output = SocketOption.exec_socket_cmd(cmd, com_ip, com_port, filter=False, retry_max=0)
                            if mark not in output:
                                log.error("未获取到命令执行标识，可能执行失败了")
                            else:
                                result = True
                        else:
                            result = True

                except Exception as e:
                    log.error(str(e))
            else:
                log.error("未配置串口信息，无法执行串口命令")
        return result


    @classmethod
    def check_fw_core(cls, execute_address, first: int=False) -> str:
        """
        备份固件core检测与导出文件到指定目录
        :return:
        """
        # code review 2025/9/25 jhe: 0.6.0.14版本，cliRegWrite32ByType变成了cliRegWrite32
        white_list = ["salRstTimerHandler", "cliRegWrite32ByType", "salRegWrite32"]
        new_core_info = None

        custom_params = cls.frame_run_dict['config_dict'].get(constants.ENV_CUSTOM_PARAMS, "None")
        if constants.CUSTOM_PARAMS_NOT_CHECK_LOG in custom_params or cls.framework_log_check_ignore:
            return new_core_info

        if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and execute_address == CmdExecuteAdressEnum.CLIENT.value:
            log.info('single mode或发包仪环境，跳过client命令执行')
            return new_core_info

        # 日志服务器ip
        log_server_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_LOG_SERVER_IP)
        # 日志服务器 用户
        log_server_account = cls.frame_run_dict['ip_dict'].get(constants.ENV_LOG_SERVER_ACCOUNT,
                                                               constants.ENV_LOG_SERVER_ACCOUNT_FRAMEWORK)
        # 串口
        server_com, client_com = CommonOperation.get_serial_port_pos()
        if '@' in server_com and '_' in server_com:
            server_com_ip = server_com.split('_')[1]
            server_com_port = server_com.split('_')[-1]
        else:
            server_com_ip = 'None'
            server_com_port = 'None'
        if '@' in client_com and '_' in client_com:
            client_com_ip = client_com.split('_')[1]
            client_com_port = client_com.split('_')[-1]
        else:
            client_com_ip = 'None'
            client_com_port = 'None'

        server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
        if execute_address == CmdExecuteAdressEnum.SERVER.value:
            target_ip = server_mgr_ip
            if cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL) == "windows":
                root = 'Administrator'
                bk_path = tj_constants.WINDOWS_ABNORMAL_BK_PATH
            else:
                root = 'root'
                bk_path = tj_constants.LINUX_ABNORMAL_BK_PATH
            # com_ip = cls.frame_run_dict['ip_dict'].get('server_com_ip', 'None')
            # com_port = cls.frame_run_dict['ip_dict'].get('server_com_port', 'None')
            com_ip = server_com_ip
            com_port = server_com_port
        else:
            target_ip = client_mgr_ip
            if cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL) == "windows":
                root = 'Administrator'
                bk_path = tj_constants.WINDOWS_ABNORMAL_BK_PATH
            else:
                root = 'root'
                bk_path = tj_constants.LINUX_ABNORMAL_BK_PATH
            # com_ip = cls.frame_run_dict['ip_dict'].get('client_com_ip', 'None')
            # com_port = cls.frame_run_dict['ip_dict'].get('client_com_port', 'None')
            com_ip = client_com_ip
            com_port = client_com_port
        if com_ip != "None" and com_port != "None":
            log.info(f"配置了串口交换机:{com_ip}-{com_port}，需要检测串口日志是否存在core")
        else:
            log.info(f"未配置串口交换机信息，无需检测串口日志是否存在core")
            return

        bitfile_version = CommonOperation.get_fpga_bitfile_class()
        chip_type = CommonOperation.get_chip_identification()
        if chip_type == 'f':
            elf_path = f"/root/sxetest/publish_version/debuginfo/{cls.nicg}_fw_fpga/debug/firmware/"
            if bitfile_version in [FpgaBitfileClass["I"]]:
                fw_elf = f"{elf_path}{cls.nicg}_fw_sym_fpgaI_F.elf"
            elif bitfile_version in [FpgaBitfileClass["M"]]:
                fw_elf = f"{elf_path}{cls.nicg}_fw_sym_fpgaM_F.elf"
            elif bitfile_version in [FpgaBitfileClass["A"]]:
                fw_elf = f"{elf_path}{cls.nicg}_fw_sym_fpgaA_F.elf"
            elif bitfile_version in [FpgaBitfileClass["C"]]:
                fw_elf = f"{elf_path}{cls.nicg}_fw_sym_fpgaC_F.elf"
            else:
                fw_elf = f"{elf_path}{cls.nicg}_fw_sym_fpgaBEFGHKLO_F.elf"
        else:
            log.info("获取make mode（debug or release）")
            exec_command = f"cat /root/sxetest/publish_version/release_version.txt"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=execute_address, ssh_username=f'{root}',
                ssh_ip=target_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            if 'release' in rtn_outputs:
                elf_path = f"/root/sxetest/publish_version/debuginfo/{cls.nicg}_fw_asic/release/firmware/"
            else:
                elf_path = f"/root/sxetest/publish_version/debuginfo/{cls.nicg}_fw_asic/debug/firmware/"
            fw_elf = f"{elf_path}{cls.nicg}_fw_sym_asic_0.elf"

        day = time.strftime("%Y-%m-%d", time.localtime(time.time()))
        com_log_path = f"{constants.COM_LOG_DIR}/{com_ip}/{com_port}/com_log_{com_ip}_{com_port}_{day}.log"
        # exec_command = f"""grep 'Beginning of core dump' {com_log_path} -B 34 | awk -F'[' '$2 >= "{start_time}" && $2 <= "{end_time}"'"""
        exec_command = f"grep 'Beginning of core dump' {com_log_path} -B 34"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, ssh_username=f'{log_server_account}',
            ssh_ip=log_server_ip, print_outputs=False)
        fw_core_infos = rtn_outputs.split("Beginning of core dump")
        key = f"{com_ip}_{com_port}_{day}"
        for info in fw_core_infos:
            if "Beginning of backtrace" not in info:
                continue
            time_check = re.findall(r"\[(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\].*?Beginning of backtrace", info)
            if time_check:
                happen_time = int(time.mktime(time.strptime(time_check[0], "%Y-%m-%d_%H-%M-%S")))
                current_time = int(time.time())
                if current_time - happen_time > 7200:
                    log.warning("时间相差超过2h，忽略")
                    continue
                else:
                    log.warning("时间相差小于2h，需确认是否是对应场景出现的有效core")

            info = info.split("End of backtrace")[0]
            if (key not in cls.fw_log_check.keys() or
                    (key in cls.fw_log_check.keys() and info not in cls.fw_log_check[key])):
                new_core_info = info
                log.warning("检查到新的fw core：\n{}".format(new_core_info))
                # addrline解析
                addr_list = []
                for i in range(10):
                    stack_info = re.findall(rf"#{i}  (\S+)", new_core_info)
                    if stack_info:
                        addr_list.append(stack_info[0])
                exec_command = f"addr2line -e {fw_elf} -f -s -C {' '.join(addr_list)}"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=execute_address, ssh_username=f'{root}',
                    ssh_ip=target_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                need_ignore = False
                for white_str in white_list:
                    if white_str in rtn_outputs:
                        need_ignore = True
                        log.warning(f"此core关键字{white_str}在白名单中，不报bug")
                        if new_core_info:
                            if key not in cls.fw_log_check.keys():
                                cls.fw_log_check[key] = set([new_core_info])
                            else:
                                cls.fw_log_check[key].add(new_core_info)
                        break
                if need_ignore:
                    new_core_info = None
                else:
                    if new_core_info:
                        if key not in cls.fw_log_check.keys():
                            cls.fw_log_check[key] = set([new_core_info])
                        else:
                            cls.fw_log_check[key].add(new_core_info)
                    new_core_info += rtn_outputs

                if first or need_ignore:
                    pass
                else:
                    # 尝试导出
                    exec_command = f"{scripts_constants.SCGBECLI64} show"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=execute_address, ssh_username=f'{root}',
                        ssh_ip=target_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    bdfs = re.findall(r"(\w\w\w\w:\w\w:\w\w.\w)", rtn_outputs)
                    for bdf in bdfs:
                        current_timestamp = time.time()
                        current_format_time = time.localtime(current_timestamp)
                        readable_time = time.strftime('%Y%m%d%H%M%S', current_format_time)
                        exec_command = f"{scripts_constants.SCGBECLI64} -d {bdf} upload coredump file=/home/nic_core/core-dumpfw-{readable_time}"
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command, cmd_execute_address=execute_address, ssh_username=f'{root}',
                            ssh_ip=target_ip, ssh_port=str(cls.test_port),
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                        )
                        break
                break

        if new_core_info or key in cls.fw_log_check.keys():
            # 当天日志文件中已有，无需翻看前一天日志文件
            pass
        else:
            # 避免因日志切割，而导致检测遗漏
            day = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
            com_log_path = f"{constants.COM_LOG_DIR}/{com_ip}/{com_port}/com_log_{com_ip}_{com_port}_{day}.log"
            exec_command = f"grep 'Beginning of core dump' {com_log_path} -B 34"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, ssh_username=f'{log_server_account}',
                ssh_ip=log_server_ip, print_outputs=False)

            if not rtn_outputs:
                log.info('not find: Beginning of core dump')

            fw_core_infos = rtn_outputs.split("Beginning of core dump")
            key = f"{com_ip}_{com_port}_{day}"

            for info in fw_core_infos:
                if "Beginning of backtrace" not in info:
                    log.info('not find: Beginning of backtrace')
                    continue
                else:
                    log.info('Beginning of backtrace found')

                time_check = re.findall(r"\[(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\].*?Beginning of backtrace", info)
                if time_check:
                    happen_time = int(time.mktime(time.strptime(time_check[0], "%Y-%m-%d_%H-%M-%S")))
                    current_time =int(time.time())
                    if current_time - happen_time > 7200:
                        log.warning("时间相差超过2h，忽略")
                        continue
                    else:
                        log.warning("时间相差小于2h，需确认是否是对应场景出现的有效core")
                info = info.split("End of backtrace")[0]
                if (key not in cls.fw_log_check.keys() or
                        (key in cls.fw_log_check.keys() and info not in cls.fw_log_check[key])):
                    new_core_info = info
                    log.warning("检查到新的fw core：\n{}".format(new_core_info))
                    # addrline解析
                    addr_list = []
                    for i in range(10):
                        stack_info = re.findall(rf"#{i}  (\S+)", new_core_info)
                        if stack_info:
                            addr_list.append(stack_info[0])
                    exec_command = f"addr2line -e {fw_elf} -f -s -C {' '.join(addr_list)}"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=execute_address, ssh_username=f'{root}',
                        ssh_ip=target_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    need_ignore = False
                    for white_str in white_list:
                        if white_str in rtn_outputs:
                            need_ignore = True
                            log.warning(f"此core关键字{white_str}在白名单中，不报bug")
                            if new_core_info:
                                if key not in cls.fw_log_check.keys():
                                    cls.fw_log_check[key] = set([new_core_info])
                                else:
                                    cls.fw_log_check[key].add(new_core_info)
                            break
                    if need_ignore:
                        new_core_info = None
                    else:
                        if new_core_info:
                            if key not in cls.fw_log_check.keys():
                                cls.fw_log_check[key] = set([new_core_info])
                            else:
                                cls.fw_log_check[key].add(new_core_info)
                        new_core_info += rtn_outputs
                    if first or need_ignore:
                        pass
                    else:
                        # 尝试导出
                        exec_command = f"{scripts_constants.SCGBECLI64} show"
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command, cmd_execute_address=execute_address, ssh_username=f'{root}',
                            ssh_ip=target_ip, ssh_port=str(cls.test_port),
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                        )
                        bdfs = re.findall(r"(\w\w\w\w:\w\w:\w\w.\w)", rtn_outputs)
                        for bdf in bdfs:
                            current_timestamp = time.time()
                            current_format_time = time.localtime(current_timestamp)
                            readable_time = time.strftime('%Y%m%d%H%M%S', current_format_time)
                            exec_command = f"{scripts_constants.SCGBECLI64} -d {bdf} upload coredump file=/home/nic_core/core-dumpfw-{readable_time}"
                            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command, cmd_execute_address=execute_address, ssh_username=f'{root}',
                                ssh_ip=target_ip, ssh_port=str(cls.test_port),
                                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                            )
                            break
                    break

        return new_core_info

    @classmethod
    def check_fw_keyword(cls) -> str:
        """
        备份固件core检测与导出文件到指定目录
        :return:
        """
        black_list = ["drian done timeout"]
        new_keyword_info = None

        custom_params = cls.frame_run_dict['config_dict'].get(constants.ENV_CUSTOM_PARAMS, "None")
        if constants.CUSTOM_PARAMS_NOT_CHECK_LOG in custom_params or cls.framework_log_check_ignore:
            return new_keyword_info
        
        for execute_address in [CmdExecuteAdressEnum.SERVER.value, CmdExecuteAdressEnum.CLIENT.value]:
            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [
                tj_constants.SINGLE_MODE]) and execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                return new_keyword_info

            # 日志服务器ip
            log_server_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_LOG_SERVER_IP)
            # 日志服务器 用户
            log_server_account = cls.frame_run_dict['ip_dict'].get(constants.ENV_LOG_SERVER_ACCOUNT,
                                                                   constants.ENV_LOG_SERVER_ACCOUNT_FRAMEWORK)
            # 串口
            server_com, client_com = CommonOperation.get_serial_port_pos()
            if '@' in server_com and '_' in server_com:
                server_com_ip = server_com.split('_')[1]
                server_com_port = server_com.split('_')[-1]
            else:
                server_com_ip = 'None'
                server_com_port = 'None'
            if '@' in client_com and '_' in client_com:
                client_com_ip = client_com.split('_')[1]
                client_com_port = client_com.split('_')[-1]
            else:
                client_com_ip = 'None'
                client_com_port = 'None'

            server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
            client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
            if execute_address == CmdExecuteAdressEnum.SERVER.value:
                target_ip = server_mgr_ip
                if cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL) == "windows":
                    root = 'Administrator'
                    bk_path = tj_constants.WINDOWS_ABNORMAL_BK_PATH
                else:
                    root = 'root'
                    bk_path = tj_constants.LINUX_ABNORMAL_BK_PATH
                # com_ip = cls.frame_run_dict['ip_dict'].get('server_com_ip', 'None')
                # com_port = cls.frame_run_dict['ip_dict'].get('server_com_port', 'None')
                com_ip = server_com_ip
                com_port = server_com_port
            else:
                target_ip = client_mgr_ip
                if cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL) == "windows":
                    root = 'Administrator'
                    bk_path = tj_constants.WINDOWS_ABNORMAL_BK_PATH
                else:
                    root = 'root'
                    bk_path = tj_constants.LINUX_ABNORMAL_BK_PATH
                # com_ip = cls.frame_run_dict['ip_dict'].get('client_com_ip', 'None')
                # com_port = cls.frame_run_dict['ip_dict'].get('client_com_port', 'None')
                com_ip = client_com_ip
                com_port = client_com_port
            if com_ip != "None" and com_port != "None":
                log.info(f"配置了串口交换机:{com_ip}-{com_port}，需要检测固件串口日志是否存在异常关键字：{black_list}")
            else:
                log.info(f"未配置串口交换机信息，无需检测固件串口日志是否存在异常关键字")
                return

            bitfile_version = CommonOperation.get_fpga_bitfile_class()
            chip_type = CommonOperation.get_chip_identification()
            if chip_type == 'f':
                elf_path = f"/root/sxetest/publish_version/debuginfo/{cls.nicg}_fw_fpga/debug/firmware/"
                if bitfile_version in [FpgaBitfileClass["I"]]:
                    fw_elf = f"{elf_path}{cls.nicg}_fw_sym_fpgaI_F.elf"
                elif bitfile_version in [FpgaBitfileClass["M"]]:
                    fw_elf = f"{elf_path}{cls.nicg}_fw_sym_fpgaM_F.elf"
                elif bitfile_version in [FpgaBitfileClass["A"]]:
                    fw_elf = f"{elf_path}{cls.nicg}_fw_sym_fpgaA_F.elf"
                elif bitfile_version in [FpgaBitfileClass["C"]]:
                    fw_elf = f"{elf_path}{cls.nicg}_fw_sym_fpgaC_F.elf"
                else:
                    fw_elf = f"{elf_path}{cls.nicg}_fw_sym_fpgaBEFGHKLO_F.elf"
            else:
                log.info("获取make mode（debug or release）")
                exec_command = f"cat /root/sxetest/publish_version/release_version.txt"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=execute_address, ssh_username=f'{root}',
                    ssh_ip=target_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                if 'release' in rtn_outputs:
                    elf_path = f"/root/sxetest/publish_version/debuginfo/{cls.nicg}_fw_asic/release/firmware/"
                else:
                    elf_path = f"/root/sxetest/publish_version/debuginfo/{cls.nicg}_fw_asic/debug/firmware/"
                fw_elf = f"{elf_path}{cls.nicg}_fw_sym_asic_0.elf"

            day = time.strftime("%Y-%m-%d", time.localtime(time.time()))
            com_log_path = f"{constants.COM_LOG_DIR}/{com_ip}/{com_port}/com_log_{com_ip}_{com_port}_{day}.log"
            if "test_start_timestamp" not in cls.frame_run_dict.keys():
                return new_keyword_info
            test_start_timestamp = int(cls.frame_run_dict['test_start_timestamp'])
            # fw_start_time = test_start_timestamp - 8*60*60
            # 此处使用的是串口交换机日志，时间戳使用的是串口交换机打上去的
            fw_start_time = test_start_timestamp
            start_time = datetime.datetime.fromtimestamp(fw_start_time).strftime("%Y-%m-%d_%H-%M-%S")

            if execute_address == CmdExecuteAdressEnum.SERVER.value:
                mark = "server"
            else:
                mark = "client"

            for keyword in black_list:
                exec_command = f"""grep '{keyword}' {com_log_path} | awk -F'[' '$2 >= "{start_time}"'"""
                # exec_command = f"grep '{keyword}' {com_log_path}"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, ssh_username=f'{log_server_account}',
                    ssh_ip=log_server_ip, print_outputs=True)
                if keyword in rtn_outputs:
                    if new_keyword_info:
                        new_keyword_info += f"{keyword},"
                    else:
                        new_keyword_info = f"{mark}端固件日志出现异常关键字：{keyword},"
        return new_keyword_info

    @classmethod
    def backup_file_init(cls, execute_address) -> None:
        """
        备份crash文件到指定目录
        :return:
        """
        if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE])and execute_address == CmdExecuteAdressEnum.CLIENT.value:
            log.info('single mode或发包仪环境，跳过client命令执行')
            return

        server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
        if execute_address == CmdExecuteAdressEnum.CLIENT.value:
            target_ip = client_mgr_ip
            if cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL) == "windows":
                root = 'Administrator'
                bk_path = tj_constants.WINDOWS_ABNORMAL_BK_PATH
            else:
                root = 'root'
                bk_path = tj_constants.LINUX_ABNORMAL_BK_PATH
        else:
            target_ip = server_mgr_ip
            if cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL) == "windows":
                root = 'Administrator'
                bk_path = tj_constants.WINDOWS_ABNORMAL_BK_PATH
            else:
                root = 'root'
                bk_path = tj_constants.LINUX_ABNORMAL_BK_PATH
        if (execute_address == CmdExecuteAdressEnum.SERVER.value) and \
                (cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL) == "windows"):
            exec_command = "Remove-Item {}/* -Recurse -Force".format(bk_path)
        elif (execute_address == CmdExecuteAdressEnum.CLIENT.value) and \
                (cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL) == "windows"):
            exec_command = "Remove-Item {}/* -Recurse -Force".format(bk_path)
        else:
            exec_command = "rm -rf {}".format(bk_path)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=execute_address, ssh_username=f'{root}',
            ssh_ip=target_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        if (execute_address == CmdExecuteAdressEnum.SERVER.value) and \
                (cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL) == "windows"):
            exec_command = "New-Item -ItemType Directory -Path {} -Force".format(bk_path)
        elif (execute_address == CmdExecuteAdressEnum.CLIENT.value) and \
                (cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL) == "windows"):
            exec_command = "New-Item -ItemType Directory -Path {} -Force".format(bk_path)
        else:
            exec_command = "mkdir -p {}".format(bk_path)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=execute_address, ssh_username=f'{root}',
            ssh_ip=target_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

    @classmethod
    def backup_core(cls, execute_address, cores: list) -> None:
        """
        备份core文件到指定目录
        :return:
        """
        if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and execute_address == CmdExecuteAdressEnum.CLIENT.value:
            log.info('single mode或发包仪环境，跳过client命令执行')
            return

        server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
        if execute_address == CmdExecuteAdressEnum.CLIENT.value:
            if cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL) == "windows":
                core_path = "C:/Windows/"
                root = 'Administrator'
                bk_path = tj_constants.WINDOWS_ABNORMAL_BK_PATH
                cp = "cp"
            else:
                core_path = "/home/nic_core/"
                root = 'root'
                bk_path = tj_constants.LINUX_ABNORMAL_BK_PATH
                cp = "/bin/cp -r"
            for file_name in cores:
                core_file = core_path + file_name
                exec_command = "{} {} {}".format(cp, core_file, bk_path)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=execute_address, ssh_username=f'{root}',
                    ssh_ip=client_mgr_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        if execute_address == CmdExecuteAdressEnum.SERVER.value:
            if cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL) == "windows":
                core_path = "C:/Windows/"
                root = 'Administrator'
                bk_path = tj_constants.WINDOWS_ABNORMAL_BK_PATH
                cp = "cp"
            else:
                core_path = "/home/nic_core/"
                root = 'root'
                bk_path = tj_constants.LINUX_ABNORMAL_BK_PATH
                cp = "/bin/cp -r"
            for file_name in cores:
                core_file = core_path + file_name
                exec_command = "{} {} {}".format(cp, core_file, bk_path)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=execute_address, ssh_username=f'{root}',
                    ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

    @classmethod
    def backup_crash(cls, execute_address, crashs: list) -> None:
        """
        备份crash文件到指定目录
        :return:
        """
        if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and execute_address == CmdExecuteAdressEnum.CLIENT.value:
            log.info('single mode或发包仪环境，跳过client命令执行')
            return

        server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
        if execute_address == CmdExecuteAdressEnum.CLIENT.value:
            if cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL) == "windows":
                crash_path = "C:/Windows/"
                root = 'Administrator'
                bk_path = tj_constants.WINDOWS_ABNORMAL_BK_PATH
                cp = "cp"
            else:
                crash_path = "/var/crash/"
                root = 'root'
                bk_path = tj_constants.LINUX_ABNORMAL_BK_PATH
                cp = "/bin/cp -r"
            for file_name in crashs:
                crash_file = crash_path + file_name
                exec_command = "{} {} {}".format(cp, crash_file, bk_path)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, ssh_username=f'{root}',
                    ssh_ip=client_mgr_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                # log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

                # 解析并添加打印
                exec_command = f"grep 'Call Trace' {crash_file}/vmcore-dmesg.txt -A 40 -B 25"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, ssh_username=f'{root}',
                    ssh_ip=client_mgr_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
            # 检查md工具是否已安装
            if not cls.__check_md_command_available(ssh_ip=client_mgr_ip, ssh_port=str(cls.test_port),
                                                    ssh_username=f'{root}'):
                log.error('md未安装，且重试失败')

        if execute_address == CmdExecuteAdressEnum.SERVER.value:
            if cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL) == "windows":
                crash_path = "C:/Windows/"
                root = 'Administrator'
                bk_path = tj_constants.WINDOWS_ABNORMAL_BK_PATH
                cp = "cp"
            else:
                crash_path = "/var/crash/"
                root = 'root'
                bk_path = tj_constants.LINUX_ABNORMAL_BK_PATH
                cp = "/bin/cp -r"
            for file_name in crashs:
                crash_file = crash_path + file_name
                exec_command = "{} {} {}".format(cp, crash_file, bk_path)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'{root}',
                    ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                # log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

                # 解析并添加打印
                exec_command = f"grep 'Call Trace' {crash_file}/vmcore-dmesg.txt -A 40 -B 25"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'{root}',
                    ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
            # 检查md工具是否已安装
            if not cls.__check_md_command_available(ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port),
                                                    ssh_username=f'{root}'):
                log.error('md未安装，且重试失败')

    @classmethod
    def env_abnormal_check(cls) -> dict:
        """
        获取当前状态下的core和crash信息
        :return:
        """
        abnormal_dict = {"core": {"server": [], "client": []}, "crash": {"server": [], "client": []}}
        if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.UEFI_MODE]:
            log.info("uefi测试模式，无需进行os下的配置与检查")
            return abnormal_dict
        server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
        if cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL) == "windows":
            exec_command = "Test-Path -Path C:\\Windows\\MEMORY.DMP"
            root = 'Administrator'
        else:
            exec_command = "ls /var/crash/ | grep 127"
            root = 'root'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'{root}',
            ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        # log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        file_list = rtn_outputs.replace("", "").split("\n")
        temp_list = []
        for item in file_list:
            if "127" in item:
                temp_list.append(item)
            elif 'DMP' in item:
                temp_list.append(item)

        abnormal_dict["crash"]["server"] = temp_list.copy()

        if cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL) == "windows":
            exec_command = "Test-Path -Path C:\\Windows\\MEMORY.DMP"
            root = 'Administrator'
        else:
            exec_command = "ls /var/crash/ | grep 127"
            root = 'root'
        if cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]:
            log.info('single mode或发包仪环境，跳过client命令执行')
        else:
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, ssh_username=f'{root}',
                ssh_ip=client_mgr_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
        # log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        file_list = rtn_outputs.replace("", "").split("\n")
        temp_list = []
        for item in file_list:
            if "127" in item:
                temp_list.append(item)
            elif 'DMP' in item:
                temp_list.append(item)
        abnormal_dict["crash"]["client"] = temp_list.copy()

        if cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL) == "windows":
            exec_command = "ls C:/Windows/ | grep core"
            root = 'Administrator'
        else:
            exec_command = "ls /home/nic_core/ | grep core"
            root = 'root'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'{root}',
            ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        # log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        file_list = rtn_outputs.replace("", "").split("\n")
        temp_list = []
        for item in file_list:
            if "core" in item:
                temp_list.append(item)
        abnormal_dict["core"]["server"] = temp_list.copy()

        if cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL) == "windows":
            exec_command = "ls C:/Windows/ | grep core"
            root = 'Administrator'
        else:
            exec_command = "ls /home/nic_core/ | grep core"
            root = 'root'
        if cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]:
            log.info('single mode或发包仪环境，跳过client命令执行')
        else:
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, ssh_username=f'{root}',
                ssh_ip=client_mgr_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
        # log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        file_list = rtn_outputs.replace("", "").split("\n")
        temp_list = []
        for item in file_list:
            if "core" in item:
                temp_list.append(item)
        abnormal_dict["core"]["client"] = temp_list.copy()
        return abnormal_dict

    @classmethod
    def env_status_check(cls, before_abnormal_dict: dict, script_rtn_code: int) -> tuple:
        """
        每个用例执行后 判断是否停止测试后 执行的操作
        :return:
        """
        log.info("脚本执行完成后，框架做环境检查:")
        cls.framework_log_check_ignore = CommonOperation.get_framework_log_check_ignore()
        bug_stop = False
        server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
        host_os_server = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL)
        host_os_client = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        desc = ""

        if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.UEFI_MODE]:
            log.info("uefi测试模式，无需进行os下的配置与检查")
            return bug_stop, desc

        log.info("执行串口命令，检查是否存在内存泄漏")
        # cls.__check_memory_leak()

        if script_rtn_code == constants.RETURN_CODE_FAIL and \
                cls.frame_run_dict['config_dict'].get(constants.ENV_BUG_STOP):
            log.info("测试已失败，且已设定bug stop，框架不再做存在操作环节的检查动作")
        else:
            if cls.frame_run_dict["config_dict"]["test_platform"] == "simu_platform":
                log.info("模拟平台节点状态检查")
                cls.__sagitta_simu_check_and_recover()

            if cls.server_nic_model == "windows":
                log.info_caller(f"检查{server_mgr_ip}环境中网卡信息是否初始化")
                CommonOperation.clean_virtual_info(ssh_ip=server_mgr_ip,
                                                   host_os_server=host_os_server,
                                                   host_os_client=host_os_client,
                                                   cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                   test_port=cls.test_port)
                CommonOperation.clean_vm_switch(ssh_ip=server_mgr_ip,
                                                host_os_server=host_os_server,
                                                host_os_client=host_os_client,
                                                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                test_port=cls.test_port)
            if cls.client_nic_model == "windows":
                log.info_caller(f"检查{client_mgr_ip} 环境中的网卡信息是否初始化")
                CommonOperation.clean_virtual_info(ssh_ip=client_mgr_ip,
                                                   host_os_server=host_os_server,
                                                   host_os_client=host_os_client,
                                                   cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                   test_port=cls.test_port)
                CommonOperation.clean_vm_switch(ssh_ip=client_mgr_ip,
                                                host_os_server=host_os_server,
                                                host_os_client=host_os_client,
                                                cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                test_port=cls.test_port)
                # rtn_code = CommonOperation.configure_nic_info(
                #     ifindex_list=cls.server_nic_ifdex,
                #     nic_name_list=cls.server_nic_name, nic_ip_list=cls.server_ip)
                # if rtn_code != RtnStatusEnum.SUCCESS.value:
                #     bug_stop = True
                time.sleep(5)

        # 清理rdma内核态脚本的资源残留
        log.info("清理rdma内核态脚本的资源残留:")
        exec_command = f'/opt/tools/netlink/{cls.nicg}_utest "cleanup" 54'
        for exec_addr in [CmdExecuteAdressEnum.SERVER.value, CmdExecuteAdressEnum.CLIENT.value]:

            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and exec_addr == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue

            rtn_code, outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=exec_addr, ssh_username=f'root',
                ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL))
            if rtn_code or 'fail' in outputs.lower():
                log.error(f'{exec_addr}清理rdma内核态资源失败')

        log.info("> 1.是否存在固件core检查:")
        server_fw_core = cls.check_fw_core(CmdExecuteAdressEnum.SERVER.value)
        client_fw_core = cls.check_fw_core(CmdExecuteAdressEnum.CLIENT.value)
        if server_fw_core:
            desc += "环境server中存在检测到新增fw core:{}.".format(server_fw_core)
            log.error(desc)
        if client_fw_core:
            desc += "环境client中存在检测到新增fw core:{}.".format(client_fw_core)
            log.error(desc)

        log.info("> 2.是否存在新增crash文件检查:")
        cls.backup_file_init(CmdExecuteAdressEnum.SERVER.value)
        cls.backup_file_init(CmdExecuteAdressEnum.CLIENT.value)
        current_abnormal_dict = cls.env_abnormal_check()
        server_crash = set(current_abnormal_dict["crash"]["server"]).difference(set(before_abnormal_dict["crash"]["server"]))
        client_crash = set(current_abnormal_dict["crash"]["client"]).difference(set(before_abnormal_dict["crash"]["client"]))
        if server_crash:
            desc += "环境server中存在新增crash文件:{}.".format(server_crash)
            log.error(desc)
            cls.backup_crash(CmdExecuteAdressEnum.SERVER.value, list(server_crash))
        if client_crash:
            desc += "环境client中存在新增crash文件:{}.".format(client_crash)
            log.error(desc)
            cls.backup_crash(CmdExecuteAdressEnum.CLIENT.value, list(client_crash))

        log.info("> 3.是否存在新增core文件检查:")
        server_core = set(current_abnormal_dict["core"]["server"]).difference(set(before_abnormal_dict["core"]["server"]))
        client_core = set(current_abnormal_dict["core"]["client"]).difference(set(before_abnormal_dict["core"]["client"]))
        white_core_list = ["core-gsettings-helpe", "core-vim", "core-lldpad", "core-pulseaudio",
                           "core-dnf", "core-PK-Backend", "core-hipsdaemon", "core-python3",
                           "core-ib_send_bw", "core-ib_read_bw", "core-ib_write_bw",
                           "core-ib_send_lat", "core-ib_read_lat", "core-ib_write_lat",
                           "core-dumpfw", "core-pktgen*",# 主动导出的不算
                           "d-anchor", "er_check", "er_daily", "ie_check", "ie_daily", "systemd-machine",
                           ]
        if server_core:
            log.info("环境server中存在新增core文件:{}.".format(server_core))
            log.info("去掉已知非网卡导致的core，或主动coredump导出的core：{}".format(white_core_list))
            ser_temp = server_core.copy()
            for core_name in ser_temp:
                for white_core in white_core_list:
                    if white_core in core_name:
                        server_core.remove(core_name)
            if server_core:
                desc += "环境server中存在新增core文件:{}.".format(server_core)
                log.error(desc)
                cls.backup_core(CmdExecuteAdressEnum.SERVER.value, list(server_core))
        if client_core:
            log.info("环境client中存在新增core文件:{}.".format(client_core))
            log.info("去掉已知非网卡导致的core：{}".format(white_core_list))
            cli_temp = client_core.copy()
            for core_name in cli_temp:
                for white_core in white_core_list:
                    if white_core in core_name:
                        client_core.remove(core_name)
            if client_core:
                desc += "环境client中存在新增core文件:{}.".format(client_core)
                log.error(desc)
                cls.backup_core(CmdExecuteAdressEnum.CLIENT.value, list(client_core))
        if len(current_abnormal_dict["crash"]["server"]) >= len(before_abnormal_dict["crash"]["server"]) or \
                len(current_abnormal_dict["crash"]["client"]) >= len(before_abnormal_dict["crash"]["client"]) or \
                len(current_abnormal_dict["core"]["server"]) >= len(before_abnormal_dict["core"]["server"]) or \
                len(current_abnormal_dict["core"]["client"]) >= len(before_abnormal_dict["core"]["client"]):
            before_abnormal_dict = current_abnormal_dict
        # 防止coredump配置时效
        cls.__config_core_dump()

        # 对端网卡是e810时，增加配置降速桥AN开关
        server_driver_name, client_driver_name = CommonOperation.get_nic_driver_name(
            current_config=scripts_constants.NIC_CONFIG_BK_PATH)
        config = configparser.ConfigParser()
        config.read(scripts_constants.NIC_CONFIG_BK_PATH)
        platform_server = config['platform']['server']
        if client_driver_name == NicNameEnum.E810.value and platform_server == 'FPGA':
            exec_command = f"{scripts_constants.SCGBECLI64} show"
            if cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL) == "windows":
                root = 'Administrator'
            else:
                root = 'root'
            rtn_code, sxecli_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'{root}',
                ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL))
            bdfs = re.findall(r"(\w\w\w\w:\w\w:\w\w.\w)", sxecli_outputs)
            for bdf in bdfs:
                cmd = f'{scripts_constants.SCGBECLI64} -d {bdf} custom {cls.nicg} speedbridge1ganset port=0 an=1'
                code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'{root}',
                    ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL))
                log.info(f'命令{cmd}的返回信息是{code}\n{out}\n{err}')

        log.info("> 4.检查env_config.ini中配置的所有pf对是否可正常ping通:")
        # renix_server_list, renix_locations_list = CommonOperation.get_renix()
        if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.DPDK_MODE, tj_constants.DPDK_AUTO_MODE]:
            log.info("dpdk mode:不检查主机驱动下pf设备是否联通")
        elif cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.SINGLE_MODE]:
            log.info("single mode:不检查主机驱动下pf设备是否联通")
        elif cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.UEFI_MODE]:
            log.info("uefi mode:不检查主机驱动下pf设备是否联通")
        elif cls.client_renix_only_flag:
            log.info("renix: client端是发包仪，不检查主机驱动下pf设备是否联通")
        else:
            pf_device_name_server, pf_device_name_client, dev_dict = \
                CommonOperation.get_target_test_device(cls.test_port)
            if pf_device_name_client == '' or pf_device_name_server == '':
                # todo sxe2-sxe2环境，当前存在pcs失效问题
                # sxe2cli -d <device> set reg type=<A|B|C|D> [width=<8|16|32|64>] addr=<value value1 [value2 ...]>
                # """
                # /comm set reg type=A addr=0x8a080240 width=32 value=0xc000
                # /comm set reg type=A addr=0x8a280240 width=32 value=0xc000
                # /comm set reg type=A addr=0x8a480240 width=32 value=0xc000
                # /comm set reg type=A addr=0x8a680240 width=32 value=0xc000
                # """
                # server_driver_name, client_driver_name = CommonOperation.get_nic_driver_name()
                # if server_driver_name == server_driver_name == cls.nicg:
                #     exec_command = f"{cls.nicg}cli -d all set reg type=A addr=0x8a080240 width=32 0xc000"
                #     rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                #         cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username="root",
                #         ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port),
                #         host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                #         host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                #     )
                #     exec_command = f"{cls.nicg}cli -d all set reg type=A addr=0x8a280240 width=32 0xc000"
                #     rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                #         cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username="root",
                #         ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port),
                #         host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                #         host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                #     )
                #     exec_command = f"{cls.nicg}cli -d all set reg type=A addr=0x8a480240 width=32 0xc000"
                #     rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                #         cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username="root",
                #         ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port),
                #         host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                #         host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                #     )
                #     exec_command = f"{cls.nicg}cli -d all set reg type=A addr=0x8a680240 width=32 0xc000"
                #     rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                #         cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username="root",
                #         ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port),
                #         host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                #         host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                #     )
                log.warning(f'server和client pf不通，等待30s再重试一次.')
                time.sleep(30)
                pf_device_name_server, pf_device_name_client, dev_dict = \
                    CommonOperation.get_target_test_device(cls.test_port)
                if pf_device_name_client == '' or pf_device_name_server == '':
                    if script_rtn_code == constants.RETURN_CODE_FAIL and \
                            cls.frame_run_dict['config_dict'].get(constants.ENV_BUG_STOP):
                        log.info("测试已失败，且已设定bug stop，框架不再做存在操作环节的检查动作")
                    else:
                        if cls.__env_check_and_recover_route():
                            log.warning(f'server和client pf不通，确认存在路由丢失问题，已尝试修复，等待10s再重试一次.')
                            time.sleep(10)
                            pf_device_name_server, pf_device_name_client, dev_dict = \
                                CommonOperation.get_target_test_device(cls.test_port)
                            if pf_device_name_client == '' or pf_device_name_server == '':
                                log.warning(f'server和client pf不通，路由丢失修复后仍ping不通，等待100s再重试一次.')
                                custom_params = cls.frame_run_dict['config_dict'].get(constants.ENV_CUSTOM_PARAMS,
                                                                                      "None")
                                if constants.CUSTOM_PARAMS_CORE_RESET_RECOVERY_LINK in custom_params and cls.__check_link_status():
                                    log.warning("两端ping不通，可能存在链路问题，尝试core reset来恢复")
                                    iretry = 3
                                    while iretry:
                                        cls.__core_reset()
                                        time.sleep(80)
                                        if not cls.__check_link_status():
                                            log.info("==>recovery：core reset后链路问题解决")
                                            break
                                        pf_device_name_server, pf_device_name_client, cls.env_dict = \
                                            CommonOperation.get_target_test_device(cls.test_port)
                                        if pf_device_name_client == '' or pf_device_name_server == '':
                                            pass
                                        else:
                                            log.info("==>recovery：core reset后ping不通问题解决")
                                            break
                                        iretry -= 1
                                        if iretry == 0:
                                            log.error("==>recovery：3次core reset后问题仍然未解决！！")
                                else:
                                    time.sleep(100)
                        else:
                            # 获取cpu架构
                            exec_command = f"arch"
                            if cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL) == "windows":
                                root = 'Administrator'
                            else:
                                root = 'root'
                            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                ssh_username=f'{root}',
                                ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port),
                                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL))
                            # # ARM环境执行建联命令
                            # if 'aarch64' in rtn_outputs:
                            #     log.warning(f'ARM环境临时修改： PF_NOT_UP, TRY RELINK')
                            #     cls.__relink_by_serial_port()
                            #     log.warning(f'ARM环境临时修改: server和client pf不通，已重新建联，等待30s再重试一次.')
                            #     time.sleep(30)
                            # else:
                            #     log.warning(f'server和client pf不通，未检测到路由丢失问题，等待100s再重试一次.')
                            #     time.sleep(100)
                            log.warning(f'server和client pf不通，未检测到路由丢失问题，等待100s再重试一次.')
                            custom_params = cls.frame_run_dict['config_dict'].get(constants.ENV_CUSTOM_PARAMS, "None")
                            if constants.CUSTOM_PARAMS_CORE_RESET_RECOVERY_LINK in custom_params and cls.__check_link_status():
                                log.warning("两端ping不通，可能存在链路问题，尝试core reset来恢复")
                                iretry = 3
                                while iretry:
                                    cls.__core_reset()
                                    time.sleep(80)
                                    if not cls.__check_link_status():
                                        log.info("==>recovery：core reset后链路问题解决")
                                        break
                                    pf_device_name_server, pf_device_name_client, cls.env_dict = \
                                        CommonOperation.get_target_test_device(cls.test_port)
                                    if pf_device_name_client == '' or pf_device_name_server == '':
                                        pass
                                    else:
                                        log.info("==>recovery：core reset后ping不通问题解决")
                                        break
                                    iretry -= 1
                                    if iretry == 0:
                                        log.error("==>recovery：3次core reset后问题仍然未解决！！")
                            else:
                                time.sleep(100)
                        pf_device_name_server, pf_device_name_client, dev_dict = \
                            CommonOperation.get_target_test_device(cls.test_port)
                        if pf_device_name_client == '' or pf_device_name_server == '':
                            # 获取cpu架构
                            exec_command = f"arch"
                            if cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL) == "windows":
                                root = 'Administrator'
                            else:
                                root = 'root'
                            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                ssh_username=f'{root}',
                                ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port),
                                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL))
                            # # ARM环境临时不退出
                            # if 'aarch64' in rtn_outputs:
                            #     log.warning(f'ARM环境临时修改: 当前建联问题较多，临时不退出框架，仅记录标记')
                            #     log.warning(f'ARM环境临时修改： PF_NOT_UP, TRY RELINK, NOT_UP')
                            # # 其他环境正常退出
                            # else:
                            #     cls.__check_link_status()
                            #     log.error(f'server和client pf不通，测试框架退出，请检查环境！')
                            #     desc += "环境中存在不可ping通的pf."
                            #     bug_stop = True
                            #     log.error(desc)
                            #     # 置位framework_bug_stop_flag
                            #     cls.__set_framework_bug_stop_flag("1")
                            cls.__check_link_status()
                            log.error(f'server和client pf不通，测试框架退出，请检查环境！')
                            desc += "环境中存在不可ping通的pf."
                            bug_stop = True
                            log.error(desc)

                            # # 检查是否存在相同mac
                            # # 20260123 add by liuxy 判断当前是否存在相同mac
                            # vm, rpc_port = CommonOperation.get_node_info_from_path()
                            # vm_info = cls.get_host_config_info(vm)
                            # mac_list = []
                            # for host_info in vm_subnet_host:
                            #     exec_command = f"ip a |grep link/ether"
                            #     rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            #         cmd=exec_command, cmd_execute_address=target_execute_address,
                            #         ssh_port=str(cls.test_port),
                            #         ssh_username=f'{root}',
                            #         host_os_server=cls.frame_run_dict['config_dict'].get(
                            #             tj_constants.EVN_SERVER_NIC_MODEL),
                            #         host_os_client=cls.frame_run_dict['config_dict'].get(
                            #             tj_constants.EVN_CLIENT_NIC_MODEL)
                            #     )
                            #     if rtn_outputs:
                            #         res = re.findall(r'link/ether ([\w:]+) ', rtn_outputs)
                            #         if res:
                            #             for mac in res:
                            #                 mac_list.append(mac)

                            # 置位framework_bug_stop_flag
                            cls.__set_framework_bug_stop_flag("1")

            if cls.frame_run_dict['config_dict'].get(
                    constants.ENV_TEST_OBJECT) == constants.ENV_RUN_MODE_WITH_BG_TRAFFIC:
                server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
                client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
                host_os_server = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL)
                host_os_client = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                if pf_device_name_client and pf_device_name_server:
                    # 此处需要使用绝对ip
                    if int(dev_dict["server_device_ip"].split('.')[-1]) < int(
                            dev_dict["client_device_ip"].split('.')[-1]):
                        server_device_ip = dev_dict["server_device_ip"]
                        client_device_ip = dev_dict["client_device_ip"]
                    else:
                        server_device_ip = dev_dict["client_device_ip"]
                        client_device_ip = dev_dict["server_device_ip"]
                    run_time = int(cls.frame_run_dict['config_dict'].get(constants.ENV_SCRIPT_TIMEOUT)) * 3600
                    cls.__enable_background_traffic(enable_bt=True, server_mgr_ip=server_mgr_ip,
                                                    client_mgr_ip=client_mgr_ip, server_device_ip=server_device_ip,
                                                    client_host_os=host_os_client, server_host_os=host_os_server,
                                                    client_device_ip=client_device_ip, run_time=run_time)
                else:
                    cls.__enable_background_traffic(enable_bt=False, server_mgr_ip=server_mgr_ip,
                                                    client_host_os=host_os_client, server_host_os=host_os_server,
                                                    client_mgr_ip=client_mgr_ip)

        '''        
        log.info("> 5.检查网口是否掉速")
        if cls.server_nic_model == "windows":
            exec_command = "sxecli show"
            root = 'Administrator'
        else:
            exec_command = f"{constants.SCGBECLI64} show"
            root = "root"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'{root}',
            ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        if "1 Gb/s" in rtn_outputs:
            # bug_stop = True
            # desc += "网口建链降速"
            log.error("网口建链降速")
        '''
        log.info("> 5.检查message关键字")
        res = cls.__dmesg_check_keyword()
        _, script_end_time = cls.get_host_time()
        res += cls.get_messages_unexpected_keywords(cls.log_check_start_time, script_end_time)
        cls.log_check_start_time = script_end_time
        if res and res != cls.log_check_keyword:
            cls.log_check_keyword = res
            desc += f"检查主机日志存在异常关键字:{res}"

        log.info("> 6.检查fw log关键字")
        res = cls.check_fw_keyword()
        if res:
            desc += f"{res}"

        log.info("> 8.检查pcie链路")
        need_report, res = cls.__check_pcie_status()
        if res:
            if need_report:
                # desc += f"{res}"
                # todo 当前不报bug，仅告警，后续稳定后再报
                CommonOperation.set_warn_message(f"检查pcie链路状态：{res}，可能是问题，请关注确认！")
        return bug_stop, desc

    @classmethod
    def get_host_time(cls) -> tuple:
        if cls.server_nic_model == 'windows':
            env_config_path = tj_constants.WINDOWS_FILE_PATH_ROOT
            root = "Administrator"
            bin_path = env_config_path
        else:
            env_config_path = tj_constants.LINUX_FILE_PATH_ROOT
            root = "root"
            bin_path = "/usr/bin/"
        target_host_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        # 当前时间戳
        # current_timestamp = time.time()
        cmd = f'date +%s | grep 1'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'{root}',
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL))

        try:
            current_timestamp = int(out)
        except Exception as e:
            current_timestamp = time.time()
            log.info("获取主机测时间失败，获取ps3server时间戳")
        # 格式化时间
        current_format_time = time.localtime(current_timestamp)
        # 可读时间
        readable_time = time.strftime('%Y%m%d%H%M%S', current_format_time)

        return current_timestamp, readable_time

    @classmethod
    def env_check_and_recover(cls) -> None:
        """
        每个用例执行后操作
        :return:
        """
        if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.UEFI_MODE]:
            log.info("uefi测试模式，无需进行os下的配置与检查")
            return
        if not cls.frame_run_dict['config_dict'].get(constants.ENV_BUG_STOP):
            # 测试脚本完成后，未设置bug_stop情况下，做环境清理与修复
            log.info("测试脚本完成后，未设置bug_stop情况下，做环境清理与修复:")
            cls.__env_check_and_recover_ko()
            cls.__env_check_and_recover_dpdk_taken()
            cls.__env_check_and_recover_rpc_process()
            cls.__env_check_and_recover_port_status()
            cls.__env_check_and_recover_route()
            cls.__force_clear_virtual_environment()
            cls.__clean_vlan()

    @classmethod
    def __set_framework_bug_stop_flag(cls, value: str = "0"):
        if cls.server_nic_model == 'windows':
            env_config_path = tj_constants.WINDOWS_FILE_PATH_ROOT
            root = "Administrator"
            bin_path = env_config_path
        else:
            env_config_path = tj_constants.LINUX_FILE_PATH_ROOT
            root = "root"
            bin_path = "/usr/bin/"
        target_host_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        exec_command = f"echo '{value}' > /root/sxetest/framework_bug_stop_flag.txt"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command,
            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'{root}',
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_CLIENT_NIC_MODEL))

    @classmethod
    def __get_framework_bug_stop_flag(cls):
        if cls.server_nic_model == 'windows':
            env_config_path = tj_constants.WINDOWS_FILE_PATH_ROOT
            root = "Administrator"
            bin_path = env_config_path
        else:
            env_config_path = tj_constants.LINUX_FILE_PATH_ROOT
            root = "root"
            bin_path = "/usr/bin/"
        target_host_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        exec_command = f"cat /root/sxetest/framework_bug_stop_flag.txt"
        rtn_code,  framework_bug_stop_flag, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command,
            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'{root}',
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_CLIENT_NIC_MODEL))
        return framework_bug_stop_flag

    @classmethod
    def __dmesg_check_bk(cls):
        if cls.server_nic_model == 'windows':
            env_config_path = tj_constants.WINDOWS_FILE_PATH_ROOT
            root = "Administrator"
            bin_path = env_config_path
        else:
            env_config_path = tj_constants.LINUX_FILE_PATH_ROOT
            root = "root"
            bin_path = "/usr/bin/"
        target_host_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)

        exec_command = f"rm -rf /var/log/dmesg_last1"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command,
            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'{root}',
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_CLIENT_NIC_MODEL), print_steps=True, print_outputs=False)

        exec_command = f"mv /var/log/dmesg_last /var/log/dmesg_last1"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command,
            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'{root}',
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_CLIENT_NIC_MODEL), print_steps=True, print_outputs=False)

    @classmethod
    def __dmesg_check_init(cls):
        custom_params = cls.frame_run_dict['config_dict'].get(constants.ENV_CUSTOM_PARAMS, "None")
        if constants.CUSTOM_PARAMS_NOT_CHECK_LOG in custom_params or cls.framework_log_check_ignore:
            return

        if cls.server_nic_model == 'windows':
            env_config_path = tj_constants.WINDOWS_FILE_PATH_ROOT
            root = "Administrator"
            bin_path = env_config_path
        else:
            env_config_path = tj_constants.LINUX_FILE_PATH_ROOT
            root = "root"
            bin_path = "/usr/bin/"
        target_host_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)

        exec_command = f"dmesg -xT >> /var/log/dmesg_last"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command,
            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'{root}',
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_CLIENT_NIC_MODEL), print_steps=True, print_outputs=False)

        exec_command = f"dmesg -c"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command,
            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'{root}',
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_CLIENT_NIC_MODEL), print_steps=True, print_outputs=False)

    @classmethod
    def __dmesg_check_keyword(cls, log_start_time: str = None, log_end_time: str = None) -> str:
        res = ""
        custom_params = cls.frame_run_dict['config_dict'].get(constants.ENV_CUSTOM_PARAMS, "None")
        if constants.CUSTOM_PARAMS_NOT_CHECK_LOG in custom_params or cls.framework_log_check_ignore:
            return res

        if cls.server_nic_model == 'windows':
            env_config_path = tj_constants.WINDOWS_FILE_PATH_ROOT
            root = "Administrator"
            bin_path = env_config_path
        else:
            env_config_path = tj_constants.LINUX_FILE_PATH_ROOT
            root = "root"
            bin_path = "/usr/bin/"
        target_host_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        mark_list = ["Call Trace", "DEADLOCK", "NO_PASID", 'IO_PAGE_FAULT', "detected Tx hang",
                     "WARNING: Nested lock was not taken",
                     "WARNING: possible circular locking dependency detected",
                     "WARNING: inconsistent lock state",
                     "WARNING: bad unlock balance detected",
                     "WARNING: bad contention detected",
                     "WARNING: possible recursive locking detected",
                     "WARNING: possible irq lock inversion dependency detected",
                     "WARNING: held lock freed",
                     "WARNING: lock held when returning to user space",
                     "WARNING: suspicious RCU usage",
                     # WARNING: %s/%d still has locks held
                     " still has locks held",
                     # WARNING: %s-safe -> %s-unsafe lock order detected
                     "-unsafe lock order detected",
                     ]
        white_mark_list = ["delay_halt.part", "lock(cpu_hotplug_lock)",
                           "BUG: sleeping function called from invalid context at",
                           "rapl_cpu_online",
                           "MQ: [SQ Base Access Error Error]", # 20251017,songyy
                           "BUG: KASAN: wild-memory-access in rcu_nmi_enter+0x8b/0xf0", # 20251118,jianghe
                           "parse_discovery_table.isra",
                           "BUG: MAX_STACK_TRACE_ENTRIES too low", # bug 3366645
                           "__alloc_pages_slowpath.constprop", # bug 3367820
                           "cacheline tracking EEXIST, overlapping mappings aren't supported" # bug 3426242,liuxy
                           ]
        for mark in mark_list:
            exec_command = f"dmesg -xT | grep '{mark}' -A 30 -B 20"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command,
                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'{root}',
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(
                    tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(
                    tj_constants.EVN_CLIENT_NIC_MODEL), print_steps=True, print_outputs=False)
            if mark in rtn_outputs:
                log.warning(f"================> 框架检查dmesg，发现异常日志{mark}：\n{rtn_outputs}")
                need_ignore = False
                for white_mark in white_mark_list:
                    if white_mark in rtn_outputs:
                        log.info(f"===============> 存在白名单关键字：{white_mark}，先忽略")
                        need_ignore = True
                if not need_ignore:
                    first_lines = re.findall(r'Call Trace.*?(\?\s*.*?)\r*\n', rtn_outputs, re.DOTALL)
                    if mark in "Call Trace" and first_lines:
                        res += f"[{mark}-{first_lines[0]}]"
                    else:
                        res += f"[{mark}]"
        return res

    @classmethod
    def change_time_format_to_host(cls, time_: str = None, messages_time: bool = False) -> tuple:
        """
        author:                 kaifeng.bi
        date:                   2021.11.15
        description:            把时间转化成host日志格式和文件名格式
        :param messages_time:   日志文件是否是messages
        :param time_:            时间
        """
        # log format 2021-09-28;02:12:17
        # filename format 2021-09-28_02:12:17
        if len(time_) < 14:
            log.error("the time is wrong")
            return '', ''

        if messages_time:
            a = datetime.datetime.strptime(time_, '%Y%m%d%H%M%S')
            return a.strftime('%b %-2d %H:%M:%S'), a.strftime('%Y%m%d')
        else:
            if cls.server_nic_model != 'windows':
                a = datetime.datetime.strptime(time_, '%Y%m%d%H%M%S') + datetime.timedelta(hours=-8)
            else:
                a = datetime.datetime.strptime(time_, '%Y%m%d%H%M%S')
            return a.strftime('%Y-%m-%d;%H:%M:%S'), a.strftime('%Y-%m-%d_%H:%M:%S')

    @classmethod
    def cat_log_by_time_with_keywords(cls, log_path: str, start_time: str,
                                      end_time: str, keyword: str = "\'\'",
                                      cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                                      local_execute_flag: bool = False,
                                      need_separator_flag: bool = False,
                                      separator: str = '',
                                      time_begin_loc: int = 0) -> tuple:
        """
        author: xianda.liu
        date  : 2020.12.11
        description: 根据时间段（最小粒度为1秒钟）截取一段日志
        :param log_path: 日志路径（包含文件名，支持*的模糊匹配）
        :param start_time: 截取开始时间 格式：23/Nov/2020:19:00:00 (format:%d/%b/%Y:%H:%M:%S)
        :param end_time: 截取结束时间 格式：23/Nov/2020:19:00:00
        :param keyword: 可利用关键字进行log筛选，目前支持 单个关键字、多个关键字取或、并 这三种情况（"a","a|b","a|grep b"）
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选,默认为SOC_NODE
        :param local_execute_flag: 判定是否在本地主机执行命令，True表示在本地执行，False表示在远程执行,默认为False
        :param need_separator_flag: 是否需要分割符,用在awk -F后,默认False
        :param separator: 分隔符
        :param time_begin_loc: 时间字段在日志中起始位置 ps3_log默认为0 如果用分隔符，从1开始计算
        :return: 返回输出结果，错误信息, 为二元素元组 rtn_info, rtn_err
        """
        target_host_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        if cls.server_nic_model == 'windows':
            env_config_path = tj_constants.WINDOWS_FILE_PATH_ROOT
            root = "Administrator"
            bin_path = env_config_path
        else:
            env_config_path = tj_constants.LINUX_FILE_PATH_ROOT
            root = "root"
            bin_path = "/usr/bin/"

        rtn_outputs, rtn_err = '', ''
        if log_path == '':
            return '', ''
        if cls.server_nic_model != 'windows':
            second_grep = ""
            keyword = '-aE ' + keyword
            if "|grep" in keyword.replace(" ",""):
                items_list = keyword.split('|grep')
                for index, item in enumerate(items_list):
                    if index == 0:
                        keyword = item
                        continue
                    second_grep += "|zgrep {}".format(item)
            else:
                second_grep = ""

            # if not need_separator_flag:
            #     if PS3_LOG_PATH in log_path or NEW_FWLOG_PATH in log_path:
            #         command = """cat {} | awk '${} >="[{}" && ${} <="[{}"' | zgrep {}"""
            #     else:
            #         command = """cat {} | awk '${} >="{}" && ${} <="{}"' | zgrep {}"""
            # else:
            #     command = """cat {} | awk -F""" + separator + """ '${} >="{}" && ${} <="{}"' | zgrep {}"""

            if not need_separator_flag:
                if PS3_LOG_PATH in log_path or NEW_FWLOG_PATH in log_path:
                    command = """zgrep {} {} {}| awk '${} >="[{}" && ${} <="[{}"' """
                else:
                    command = """zgrep {} {} {}| awk '${} >="{}" && ${} <="{}"' """
            else:
                command = """zgrep {} {} {}| awk -F""" + separator + """ '${} >="{}" && ${} <="{}"' """
            exec_command = command.format(keyword, log_path, second_grep, str(time_begin_loc), start_time,
                                          str(time_begin_loc), end_time)
            # 用本地子脚本执行
            # command = "esxe.py -awkt '{}','{}','{}','{}','{}' -p '{}'"
            # exec_command = command.format(str(time_begin_loc), start_time, str(time_begin_loc), end_time,
            #                               keyword, log_path)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command,
                cmd_execute_address=cmd_execute_address, ssh_username=f'{root}',
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(
                    tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(
                    tj_constants.EVN_CLIENT_NIC_MODEL), print_steps=True, print_outputs=True)
            return rtn_outputs, rtn_err
        else:
            # windows 2022和部分2019不支持grep部分参数，替换findstr
            if "|grep" in keyword:
                items_list = keyword.split('|grep')
                # keyword = "|grep ".join('\"' + i.strip() + '\"' for i in items_list)
                keyword = "|findstr /I ".join('\"' + i.strip() + '\"' for i in items_list)
            else:
                # keyword = '-aE \"' + keyword + '\"'
                keyword = '\"' + keyword + '\"'

            command = """cat {} | findstr /I {}"""
            exec_command = command.format(log_path, keyword)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command,
                cmd_execute_address=cmd_execute_address, ssh_username=f'{root}',
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(
                    tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(
                    tj_constants.EVN_CLIENT_NIC_MODEL), print_steps=True, print_outputs=False)
            for line in rtn_outputs.split('\r\n'):
                if PS3_LOG_PATH in log_path or NEW_FWLOG_PATH in log_path:
                    if line.startswith('['):
                        # print(line)
                        if start_time <= line[1:20] <= end_time:
                            print(start_time, line[1:20], end_time, line)
                            return rtn_outputs, rtn_err
                else:
                    if line.startswith('DBG['):
                        print(line)
                        if start_time <= line[4:23] <= end_time:
                            return rtn_outputs, rtn_err
            return rtn_outputs, rtn_err

    @classmethod
    def get_messages_unexpected_keywords(cls, log_start_time: str = None, log_end_time: str = None):
        """
        author:                 kaifeng.bi
        date:                   2023.09.22
        description:            获取messages异常日志
        :param controller_id:   controller_id
        :param log_start_time:  日志起始时间
        :param log_end_time:    日志结束时间
        """
        custom_params = cls.frame_run_dict['config_dict'].get(constants.ENV_CUSTOM_PARAMS, "None")
        if constants.CUSTOM_PARAMS_NOT_CHECK_LOG in custom_params or cls.framework_log_check_ignore:
            return ""

        log.info("########get Messages unexpected keywords########")
        res = ""

        if cls.server_nic_model != 'windows':
            # 查找对应时间段的日志文件
            log_start_time, _ = cls.change_time_format_to_host(log_start_time, messages_time=True)
            log_end_time, _ = cls.change_time_format_to_host(log_end_time, messages_time=True)
            keywords = ['"BUG: KASAN"', '"Hardware Error"|grep "1eb6:1260"', '"error"|grep "1eb6:1260"',
                        '"Entering Safe Mode"']
            # keywords = ['grep "BUG: KASAN"', 'grep "Hardware Error"|grep "1eb6:1260"', 'grep "error"|grep "1eb6:1260"']
            white_mark_list = ["rapl_cpu_online",
                               "BUG: KASAN: wild-memory-access in rcu_nmi_enter+0x8b/0xf0" # 20251118,jianghe
                               ]

            # '/var/log/messages /var/log/syslog'
            for keyword in keywords:
                log_rtn_info, log_rtn_err = cls. \
                    cat_log_by_time_with_keywords('/var/log/messages', log_start_time, log_end_time,
                                                  keyword=keyword,
                                                  cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                if log_rtn_info and '/var/log/messages' not in log_rtn_info:
                    log.warning(f"================> 框架检查messages，发现异常日志：{log_rtn_info}")
                    need_ignore = False
                    for white_mark in white_mark_list:
                        if white_mark in log_rtn_info:
                            log.info(f"===============> 存在白名单关键字：{white_mark}，先忽略")
                            need_ignore = True
                    if not need_ignore:
                        bug_info = log_rtn_info.split('\n')[0]
                        res += f"[{bug_info}]"

        return res

    @classmethod
    def __upgrade_version(cls) -> bool:
        """
        author:      junfeng.he
        date:        2023-08-02 15:34:55
        description: 版本升级，根据jenkins填入的路径拷包升级，优先去ps3server服务器上找包，找不到则在测试本机上找，
        若只填路径，不填包名，则找该文件夹里的第一个文件
        :return:     升级成功返回True，否则返回False
        """
        current_fw_version = '0.0.0.0'
        current_driver_version = '0.0.0.0'
        current_driver_vf_version = '0.0.0.0'
        current_cli_version = '0.0.0.0'
        # 检查是否需要升级环境版本
        target_server_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        target_client_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
        upgrade_flag = cls.frame_run_dict['config_dict'].get(constants.ENV_PACKAGE_INSTALL)
        upgrade_path = cls.frame_run_dict['config_dict'].get(constants.ENV_PACKAGE_PATH)
        job_directory_path = cls.frame_run_dict['job_directory_path']

        if "*force" in upgrade_path:
            upgrade_all = True
        else:
            upgrade_all = False
        if "*rdma" in upgrade_path:
            upgrade_rdma = True
        else:
            upgrade_rdma = False
        if "*check" in upgrade_path:
            upgrade_soc_check = True
        else:
            upgrade_soc_check = False
        if "*driver_only" in upgrade_path:
            upgrade_driver_only = True
            upgrade_fw_only = False
        else:
            upgrade_driver_only = False
            if "*fw_only" in upgrade_path:
                upgrade_fw_only = True
            else:
                upgrade_fw_only = False
        if "*host_reboot" in upgrade_path:
            host_op = "host_reboot"
        elif "*host_dc" in upgrade_path:
            host_op = "host_dc"
        else:
            host_op = "host_none"

        if "*runmode" in upgrade_path:
            runmod_value = re.findall(r'(runmod\d+)', upgrade_path)
            if runmod_value:
                runmod = runmod_value[0]
            else:
                log.error("填写胡runmode不正确！！")
                exit(1)
        else:
            runmod = "runmod6"

        versions = re.findall(r'dpdk([\.\d]+)', upgrade_path.replace(".tar.gz", ""))
        if "*dpdk24" in upgrade_path:
            if versions and "." in versions[0]:
                dpdk_version = versions[0]
            else:
                dpdk_version = "24.11.1"
        elif "*dpdk23" in upgrade_path:
            if versions and "." in versions[0]:
                dpdk_version = versions[0]
            else:
                dpdk_version = "23.11.1"
        elif "*dpdk22" in upgrade_path:
            if versions and "." in versions[0]:
                dpdk_version = versions[0]
            else:
                dpdk_version = "22.11.3"
        elif "*dpdk21" in upgrade_path:
            if versions and "." in versions[0]:
                dpdk_version = versions[0]
            else:
                dpdk_version = "21.11.5"
        elif "*dpdk19" in upgrade_path:
            if versions and "." in versions[0]:
                dpdk_version = versions[0]
            else:
                dpdk_version = "19.11.6"
        else:
            if versions and "." in versions[0]:
                dpdk_version = versions[0]
            else:
                dpdk_version = "23.11.1"

        if "*dpdk_build" in upgrade_path:
            dpdk_build = True
        else:
            dpdk_build = False

        if "*dpdk_l4" in upgrade_path:
            dpdk_l4 = True
        else:
            dpdk_l4 = False

        if "*dpdk_keep" in upgrade_path:
            dpdk_keep = True
        else:
            dpdk_keep = False

        if "*sxe_compile" in upgrade_path:
            sxe_compile = True
        else:
            sxe_compile = False
        if f"*{cls.nicg}_compile" in upgrade_path:
            scgbe_compile = True
        else:
            scgbe_compile = False

        if "*dpdk_build_make" in upgrade_path:
            dpdk_build_make = True
        else:
            dpdk_build_make = False

        if "*pktgen_build" in upgrade_path:
            pktgen_build = True
        else:
            pktgen_build = False

        if "*vc_cli" in upgrade_path:
            vc_mode = 'cli'
        elif "*vc_driver" in upgrade_path:
            # pf+vf & dpdk & rdma
            vc_mode = 'driver'
        elif "*vc_pf" in upgrade_path:
            vc_mode = 'pf'
        elif "*vc_vf" in upgrade_path:
            vc_mode = 'vf'
        elif "*vc_dpdk" in upgrade_path:
            vc_mode = 'dpdk'
        elif "*vc_rdma" in upgrade_path:
            vc_mode = 'rdma'
        elif "*vc_fw-all" in upgrade_path:
            vc_mode = 'fw-all'
        elif "*vc_fw" in upgrade_path:
            vc_mode = 'fw'
        elif "*vc_uboot" in upgrade_path:
            vc_mode = 'uboot'
        elif "*vc_nvdata" in upgrade_path:
            vc_mode = 'nvdata'
        elif "*vc_userconfig" in upgrade_path:
            vc_mode = 'userconfig'
        elif "*vc_optionrom" in upgrade_path:
            vc_mode = 'optionrom'
        else:
            vc_mode = None

        divide_num = 1
        divide_index = 0
        if "*divide" in upgrade_path:
            divides = re.findall(r'divide(\d+-\d+)', upgrade_path)
            if divides:
                divide_num = int(divides[0].split("-")[0])
                divide_index = int(divides[0].split("-")[1])

        if "*" in upgrade_path:
            upgrade_path = upgrade_path.split("*")[0]

        log.info(f"target_server_ip :{target_server_ip}")
        log.info(f"target_client_ip :{target_client_ip}")
        log.info(f"upgrade_flag :{upgrade_flag}")
        log.info(f"upgrade_path :{upgrade_path}")
        log.info(f"upgrade_driver_only :{upgrade_driver_only}")
        log.info(f"upgrade_fw_only :{upgrade_fw_only}")
        log.info(f"dpdk_version :{dpdk_version}")
        log.info(f"vc_mode :{vc_mode}")
        server_driver_name, client_driver_name = CommonOperation.get_nic_driver_name()
        server_platfroms, client_platfroms = CommonOperation.get_platform()
        if "," in server_platfroms:
            server_platfrom_list = server_platfroms.split(",")
        else:
            server_platfrom_list = [server_platfroms]

        if "," in client_platfroms:
            client_platfrom_list = client_platfroms.split(",")
        else:
            client_platfrom_list = [client_platfroms]

        # if 'tar.gz' in upgrade_path and client_board_type != server_board_type:
        #     log.error(f"当前指定tar.gz包:{upgrade_path}升级，两端都是sxe2，但是本端为{server_board_type}，对端为{client_board_type}，"
        #               f"不一致，禁止升级，请将对应升级包放置到同一个文件夹中，升级路径填该文件夹路径,让测试框架识别升级！")
        #     exit(1)

        target_server_dict = {target_server_ip: [server_driver_name, cls.server_nic_model,
                                                 CmdExecuteAdressEnum.SERVER.value, server_platfrom_list],
                              target_client_ip: [client_driver_name, cls.client_nic_model,
                                                 CmdExecuteAdressEnum.CLIENT.value, client_platfrom_list]}

        target_host_ip_driver_update_count_dict = {}
        for index, target_host_ip in enumerate(target_server_dict.keys()):
            log.info(f"target_host_ip :{target_host_ip}")
            target_nic_driver_name = target_server_dict[target_host_ip][0]
            target_nic_model = target_server_dict[target_host_ip][1]
            target_execute_address = target_server_dict[target_host_ip][2]
            target_platfrom_list = target_server_dict[target_host_ip][3]

            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and target_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue

            if target_nic_driver_name not in [f'{cls.nicg}']:
                log.info(f"target server driver name :{target_nic_driver_name},not {cls.nicg},skip upgrade.")

            if upgrade_flag and cls.__isvalid(upgrade_path) and target_nic_driver_name in [f'{cls.nicg}']:
                if target_nic_model == 'windows':
                    root = 'Administrator'
                    root_path = tj_constants.WINDOWS_FILE_PATH_ROOT
                    suffix = '.exe'
                    win_driver_path = "{}publish_version".format(root_path)
                    sxecli = '{}cli'.format(target_nic_driver_name)
                    cp = "cp"
                else:
                    root = 'root'
                    root_path = tj_constants.LINUX_FILE_PATH_ROOT
                    suffix = ''
                    win_driver_path = "{}publish_version".format(root_path)
                    sxecli = '{}cli'.format(target_nic_driver_name)
                    cp = "/bin/cp -r"

                # 待测版本升级包测试机本地路径
                dest_tar_path = '{}publish_tar'.format(root_path)
                nic_package_path = "{}publish_version".format(root_path)
                nic_package_last_path = "{}publish_version_last".format(root_path)

                skip_upgrade = 0
                need_upgrade_soc = True
                target_upgrade_pkt_new_struct_sub = False
                target_upgrade_pkt_new_struct = True
                # 最先判断是不是版本兼容性测试，传递路径优先去ps3ser找，没有则去测试机上找cat
                for target_platfrom in target_platfrom_list:

                    architecture = "x86_64"
                    if target_nic_model == 'windows':
                        exec_command = "Remove-Item {}/* -Recurse -Force".format(dest_tar_path)
                    else:
                        exec_command = "lscpu"
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                        )
                        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                        if "aarch64" in rtn_outputs:
                            architecture = "arm64"
                        elif "aarch32" in rtn_outputs:
                            architecture = "arm32"
                        log.info(f"architecture:{architecture}")
                        exec_command = "rm -rf {}/*".format(dest_tar_path)

                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    if target_nic_model == "windows":
                        exec_command = "New-Item -ItemType Directory -Path {} -Force".format(dest_tar_path)
                    else:
                        exec_command = "mkdir -p {}".format(dest_tar_path)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    if target_nic_model == "windows":
                        exec_command = "New-Item -ItemType Directory -Path {} -Force".format(nic_package_path)
                    else:
                        exec_command = "mkdir -p {}".format(nic_package_path)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    if target_nic_model == "windows":
                        exec_command = "New-Item -ItemType Directory -Path {} -Force".format(nic_package_last_path)
                    else:
                        exec_command = "mkdir -p {}".format(nic_package_last_path)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

                    target_evb_crb = ""
                    target_board_type = ""
                    target_board_type_mark = ""
                    if "ncd" in target_platfrom.lower():
                        log.warning("==> NCD模式，框架不进行升级")
                        continue
                    if "crb" in target_platfrom.lower():
                        target_evb_crb = "crb"
                    if "evb" in target_platfrom.lower():
                        target_evb_crb = "evb"
                    if "pciex2" in target_platfrom.lower():
                        target_board_type = "pcie-2-25"
                        target_board_type_mark = "1260-2A"
                    if "ocpx2" in target_platfrom.lower():
                        target_board_type = "ocp-2-25"
                        target_board_type_mark = "1263-2A"
                    if "ocpx4" in target_platfrom.lower():
                        target_board_type = "ocp-4-25"
                        target_board_type_mark = "1263-4A"
                    if "pcie10x2" in target_platfrom.lower():
                        target_board_type = "pcie-2-10"
                        target_board_type_mark = "1260C-2X"
                    if not target_board_type:
                        log.warning("未找到匹配的板卡类型，不升级")
                        continue
                    bdfs = re.findall(r"(\S{4}:\S{2}:\S{2}.\S)", target_platfrom)
                    if bdfs:
                        target_bdf = bdfs[0]
                    else:
                        target_bdf = ""
                    log.info(f'target_evb_crb: {target_evb_crb}')
                    log.info(f'target_board_type: {target_board_type}')
                    log.info(f"target_bdf :{target_bdf}")

                    if target_evb_crb not in ['evb', 'crb']:
                        log.info(f'target_platfrom: {target_platfrom}, skip upgrade')
                        skip_upgrade += 1
                        continue

                    log.info(f'获取升级包')
                    if ".csv" in upgrade_path:
                        log.info(f'vc_test> vc_mode:{vc_mode}')
                        if not vc_mode:
                            log.info(f'vc_mode未配置，不进行测试')
                            exit(1)
                        if target_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                            log.info(f'vc_mode，client端，不进行升级')
                            continue
                        log.info(f'vc_test> 当前路径模式为：版本兼容性测试')
                        log.info(f'vc_test> 1.获取版本兼容性测试的版本信息')
                        versions_list = FileOperation.read_csv_file(upgrade_path)
                        log.info("vc_test> versions_list:{}".format(versions_list))
                        log.info(f'vc_test> 2.将所有测试包拷贝到测试机并解压')
                        target_vc_path = "/home/vc_test"
                        nic_vc_packages_path = "{}/vc_packages".format(target_vc_path)
                        nic_vc_new_packages_path = "{}/vc_new_packages".format(target_vc_path)

                        exec_command = "mkdir -p {};mkdir -p {};mkdir -p {}".format(target_vc_path, nic_vc_packages_path, nic_vc_new_packages_path)
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                        )

                        target_pkgs_list = []
                        for pkg_path in versions_list:
                            upgrade_path = pkg_path[0]
                            exec_command = "ls {} | grep 'tar.gz'".format(upgrade_path)
                            rtn_code, result = cls.getstatusoutput(exec_command)
                            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
                            # 取这个路径下的第一个包
                            target_file_list = result.split("\n")
                            target_file_name = target_file_list[0]
                            found_flag = False
                            for file_name in target_file_list:
                                # 排除合封ncd、合封标卡、单封ncd
                                if "_D2D_" not in file_name and "_ncd_" not in file_name:
                                    target_file_name = file_name
                                    log.info(f"==>找到匹配的大包：{target_file_name}")
                                    found_flag = True
                                    break
                            if not found_flag:
                                log.error("==>未找到匹配的大包，不进行升级")
                                exit(1)

                            exec_command = "scp -P {} -r {}/{} {}@{}:{}/".format(
                                cls.test_port, upgrade_path, target_file_name, root, target_host_ip, nic_vc_packages_path)
                            rtn_code, result = cls.getstatusoutput(exec_command)
                            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
                            if rtn_code != RtnStatusEnum.SUCCESS.value:
                                log.info("拷包失败！")
                                exit(1)
                            else:
                                other_nic_vc_packages_path = "/root/sxetest/publish_other"
                                exec_command = "rm -rf {};mkdir -p {}".format(other_nic_vc_packages_path,
                                                                              other_nic_vc_packages_path)
                                CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=exec_command, cmd_execute_address=target_execute_address,
                                    ssh_username=f'{root}',
                                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                    host_os_server=cls.frame_run_dict['config_dict'].get(
                                        tj_constants.EVN_SERVER_NIC_MODEL),
                                    host_os_client=cls.frame_run_dict['config_dict'].get(
                                        tj_constants.EVN_CLIENT_NIC_MODEL))

                                if "debug" in upgrade_path:
                                    other_target_folder_path = upgrade_path.replace("debug", "release")
                                    log.info("拷贝release大包到/root/sxetest/publish_other/")
                                    exec_command = "scp -P {} -r {}/{} {}@{}:{}".format(
                                        cls.test_port, other_target_folder_path, target_file_name, root, target_host_ip, other_nic_vc_packages_path)
                                    rtn_code1, result1 = cls.getstatusoutput(exec_command)
                                    log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code1, result1))
                                elif "release" in upgrade_path:
                                    other_target_folder_path = upgrade_path.replace("release", "debug")
                                    log.info("拷贝debug大包到/root/sxetest/publish_other/")
                                    exec_command = "scp -P {} -r {}/{} {}@{}:{}".format(
                                        cls.test_port, other_target_folder_path, target_file_name, root, target_host_ip, other_nic_vc_packages_path)
                                    rtn_code1, result1 = cls.getstatusoutput(exec_command)
                                    log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code1, result1))
                                else:
                                    log.warning("非框架归档正规路径，无法拷贝other")

                            target_vc_pkg = target_file_name.split("/")[-1]
                            exec_command = "mkdir {}/{};tar -zxvf {}/{} -C {}/{}".format(
                                target_vc_path, target_vc_pkg.replace(".tar.gz", ""), nic_vc_packages_path, target_file_name,
                                target_vc_path, target_vc_pkg.replace(".tar.gz", ""))
                            rtn_code, rtn_outputs, rtn_err = \
                                CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=exec_command,
                                    cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                    host_os_server=cls.frame_run_dict['config_dict'].
                                        get(tj_constants.EVN_SERVER_NIC_MODEL),
                                    host_os_client=cls.frame_run_dict['config_dict'].
                                        get(tj_constants.EVN_CLIENT_NIC_MODEL),
                                    shiled_error=True, print_outputs=False
                                )
                            if rtn_code != RtnStatusEnum.SUCCESS.value:
                                log.error(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                                exit(1)
                            target_pkgs_list.append(nic_vc_packages_path + "/" + target_file_name.split("/")[-1])
                        log.info("vc_test> target_pkgs_list:{}".format(target_pkgs_list))
                        log.info(f'vc_test> 3.生成版本兼容性测试组合清单')
                        compatible_versions_test_file = job_directory_path + "/compatible_versions_test.csv"
                        cls.make_compatible_versions_test_list(target_pkgs_list, vc_mode,
                                                               compatible_versions_test_file,
                                                               nic_vc_new_packages_path, divide_num, divide_index,
                                                               target_execute_address,
                                                               target_host_ip, target_nic_model)
                        log.info(f'vc_test> 4.根据版本兼容性测试组合重组新包')
                        cls.make_compatible_versions_pkgs(target_pkgs_list, compatible_versions_test_file,
                                                          nic_vc_packages_path,
                                                          nic_vc_new_packages_path, vc_mode,
                                                          target_execute_address, target_host_ip, target_nic_model)

                        log.info(f'vc_test> 5.将首个版本兼容性测试组合新包路径作为此次升级路径')
                        pkgs_info_list = FileOperation.read_csv_file(compatible_versions_test_file)
                        upgrade_path = pkgs_info_list[1][0]
                        log.warning("vc_test> upgrade_path:{}".format(upgrade_path))

                    if 'tar.gz' not in upgrade_path or vc_mode:
                        exec_command = "ls {} | grep 'tar.gz'".format(upgrade_path)
                        rtn_code, result = cls.getstatusoutput(exec_command)
                        log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
                        if ('tar.gz' in result) and ("No such file or directory" not in result) and not vc_mode:
                            old_pkg_type = True
                            if "normal_" + target_board_type in result:
                                log.info("2.0.0.23之前命名格式")
                                old_pkg_type = True
                            elif "normal_pcie" not in result and "normal_ocp" not in result:
                                log.info("2.0.0.24之后命名格式")
                                old_pkg_type = False
                            else:
                                log.warning("未知道匹配大包! 此次不升级")
                                continue
                            # 取这个路径下的第一个包
                            target_file_list = result.split("\n")
                            target_file_name = target_file_list[0]
                            found_flag = False
                            for file_name in target_file_list:
                                if old_pkg_type and  target_board_type in file_name and "_ncd_" not in file_name:
                                    target_file_name = file_name
                                    log.info("==>找到匹配的old大包")
                                    found_flag = True
                                    break
                                # 排除合封ncd、合封标卡、单封ncd
                                elif not old_pkg_type and  "_D2D_" not in file_name and "_ncd_" not in file_name:
                                    target_file_name = file_name
                                    log.info("==>找到匹配的new大包")
                                    found_flag = True
                                    break
                            if not found_flag:
                                log.error("==>未找到匹配的大包，不进行升级")
                                exit(1)

                            exec_command = "scp -P {} {}/{} {}@{}:{}".format(
                                cls.test_port, upgrade_path, target_file_name, root, target_host_ip, dest_tar_path)
                            rtn_code, result = cls.getstatusoutput(exec_command)
                            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
                            if rtn_code != RtnStatusEnum.SUCCESS.value:
                                log.info("拷包失败！")
                                return False
                            else:
                                other_nic_vc_packages_path = "/root/sxetest/publish_other"
                                exec_command = "rm -rf {};mkdir -p {}".format(other_nic_vc_packages_path,
                                                                              other_nic_vc_packages_path)
                                CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=exec_command, cmd_execute_address=target_execute_address,
                                    ssh_username=f'{root}',
                                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                    host_os_server=cls.frame_run_dict['config_dict'].get(
                                        tj_constants.EVN_SERVER_NIC_MODEL),
                                    host_os_client=cls.frame_run_dict['config_dict'].get(
                                        tj_constants.EVN_CLIENT_NIC_MODEL))

                                if "debug" in upgrade_path:
                                    other_target_folder_path = upgrade_path.replace("debug", "release")
                                    log.info("拷贝release大包到/root/sxetest/publish_other/")
                                    exec_command = "scp -P {} {}/{} {}@{}:{}".format(
                                        cls.test_port, other_target_folder_path, target_file_name, root, target_host_ip,
                                        other_nic_vc_packages_path)
                                    rtn_code1, result1 = cls.getstatusoutput(exec_command)
                                    log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code1, result1))
                                elif "release" in upgrade_path:
                                    other_target_folder_path = upgrade_path.replace("release", "debug")
                                    log.info("拷贝debug大包到/root/sxetest/publish_other/")
                                    exec_command = "scp -P {} {}/{} {}@{}:{}".format(
                                        cls.test_port, other_target_folder_path, target_file_name, root, target_host_ip,
                                        other_nic_vc_packages_path)
                                    rtn_code1, result1 = cls.getstatusoutput(exec_command)
                                    log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code1, result1))
                                else:
                                    log.warning("非框架归档正规路径，无法拷贝other")
                        else:
                            # ps3_server上找不到，去本机上找
                            log.info("去本机上找升级包")
                            if 'tar.gz' not in upgrade_path:
                                if target_nic_model == 'windows':
                                    exec_command = "Get-ChildItem {} -Filter '*.tar.gz' " \
                                                   "| Select-Object -ExpandProperty FullName".format(upgrade_path)
                                else:
                                    exec_command = "ls {} | grep 'tar.gz'".format(upgrade_path)
                                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=exec_command,
                                    cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                    host_os_server=cls.frame_run_dict['config_dict'].get(
                                        tj_constants.EVN_SERVER_NIC_MODEL),
                                    host_os_client=cls.frame_run_dict['config_dict'].get(
                                        tj_constants.EVN_CLIENT_NIC_MODEL))
                                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                                # 取这个路径下的第一个包
                                if '/' not in rtn_outputs.split("\n")[0] and '\\' not in rtn_outputs.split("\n")[0]:
                                    upgrade_path = upgrade_path + "/" + rtn_outputs.split("\n")[0]
                                else:
                                    target_file_list = rtn_outputs.split("\n")
                                    target_file_name = target_file_list[0]
                                    found_flag = False
                                    for file_name in target_file_list:
                                        if target_board_type in file_name and "_ncd_" not in file_name and "_D2D_" not in file_name:
                                            target_file_name = file_name
                                            log.info("==>找到匹配的大包")
                                            found_flag = True
                                    if not found_flag:
                                        log.error("==>未找到匹配的大包，不进行升级")
                                        exit(1)
                                    upgrade_path = target_file_name
                                log.warning("取这个路径下的第一个包-> upgrade_path:{}".format(upgrade_path))
                            if 'tar.gz' in upgrade_path:
                                exec_command = "{} {} {}".format(cp, upgrade_path, dest_tar_path)
                                rtn_code, rtn_outputs, rtn_err = \
                                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                                        cmd=exec_command,
                                        cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                        host_os_server=cls.frame_run_dict['config_dict'].get(
                                            tj_constants.EVN_SERVER_NIC_MODEL),
                                        host_os_client=cls.frame_run_dict['config_dict'].get(
                                            tj_constants.EVN_CLIENT_NIC_MODEL))
                                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                                if rtn_code != RtnStatusEnum.SUCCESS.value:
                                    log.error(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                                    return False
                                else:
                                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                            else:
                                log.error(f'ps3server和本地都没有找到升级安装包，请检查路径是否正确！')
                                return False
                    else:
                        target_file_name = upgrade_path.split("/")[-1]
                        exec_command = "ls {} | grep 'tar.gz'".format(upgrade_path)
                        rtn_code, result = cls.getstatusoutput(exec_command)
                        log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
                        if ('tar.gz' in result) and ("No such file or directory" not in result):
                            exec_command = "scp -P {} {} {}@{}:{}".format(
                                cls.test_port, upgrade_path, root, target_host_ip, dest_tar_path)
                            rtn_code, result = cls.getstatusoutput(exec_command)
                            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
                            if rtn_code != RtnStatusEnum.SUCCESS.value:
                                log.info("拷包失败！")
                                return False
                        else:
                            if target_nic_model == 'windows':
                                exec_command = "Get-ChildItem {} -Filter '*.tar.gz' " \
                                               "| Select-Object -ExpandProperty FullName".format(upgrade_path)
                            else:
                                exec_command = "ls {} | grep 'tar.gz'".format(upgrade_path)
                            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command,
                                cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                host_os_server=cls.frame_run_dict['config_dict'].get(
                                    tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].get(
                                    tj_constants.EVN_CLIENT_NIC_MODEL))
                            log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                            if '/' not in rtn_outputs.split("\n")[0] and '\\' not in rtn_outputs.split("\n")[0]:
                                upgrade_path = upgrade_path + "/" + rtn_outputs.split("\n")[0]
                            else:
                                upgrade_path = rtn_outputs.split("\n")[0]
                            exec_command = "{} {} {}".format(cp, upgrade_path, dest_tar_path)
                            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command,
                                cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL))
                            if rtn_code != RtnStatusEnum.SUCCESS.value:
                                log.error(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                                return False
                            else:
                                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

                    if rtn_code == RtnStatusEnum.SUCCESS.value:
                        log.info("判断需要升级的包和publish_version中的包版本是否相同，相同则不替换publish_version_last")
                        exec_command = "cat {}/release_version.txt".format(nic_package_path)
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                        )
                        log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
                        last_versions = re.findall(r"branch:(\S+)", rtn_outputs)

                        exec_command = "ls {} | grep 'tar.gz'".format(dest_tar_path)
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                            shiled_error=False
                        )
                        new_versions = rtn_outputs
                        tar_pkg = "{}/{}".format(dest_tar_path, rtn_outputs.split("\n")[0].replace("\\", "/").split("/")[-1])
                        log.info(f"升级打包文件：{tar_pkg}")
                        if last_versions and last_versions[0] in new_versions:
                            log.info(f'新升级版本与上次一致，无需备份')
                        else:
                            log.info(f'新升级版本与上次不一致，备份为上一个版本')
                            if target_nic_model == 'windows':
                                exec_command = "Remove-Item {}/* -Recurse -Force".format(nic_package_last_path)
                            else:
                                exec_command = "rm -rf {}/*".format(nic_package_last_path)
                            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                            )
                            log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
                            if target_nic_model == 'windows':
                                exec_command = "Copy-Item {}/* {}/ -Recurse -Force".format(
                                    nic_package_path, nic_package_last_path)
                            else:
                                exec_command = "{} {}/* {}/".format(cp, nic_package_path, nic_package_last_path)
                            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                            )
                            log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')


                        if target_nic_driver_name in ["sxe2"]:
                            product_name = "1260-X"
                            fw_mark = "Sxe2"
                        else:
                            product_name = "1160-2X"
                            fw_mark = "Sxe"

                        if "tar.gz" in tar_pkg:
                            log.info(f'调用子脚本进行主机测组件升级更新')
                            if target_host_ip not in target_host_ip_driver_update_count_dict.keys():
                                exec_command = f"python3 /root/sxetest/install_all_version.py -t {tar_pkg} -km --board_type={target_platfrom.lower()}"
                                if upgrade_rdma:
                                    exec_command += f' --install_rdma'
                                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                                )
                                # log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
                                if 'ERROR_EXIT' in rtn_outputs and rtn_code:
                                    log.error(f'升级脚本出现阻塞问题，升级停止 ！！！，测试框架退出')
                                    exit(1)
                                if 'WARNING' in rtn_outputs:
                                    log.warning(f'升级脚本出现告警问题，不阻塞升级，但建议检查 WARNING 日志')
                                target_host_ip_driver_update_count_dict[target_host_ip] = 1
                            else:
                                log.info(f'该主机{target_host_ip}已经升级过一次驱动了，双卡不需要重复升级,仅解压大包')
                                exec_command = "tar -zxvf {} -C /root/sxetest/publish_version/".format(tar_pkg)
                                rtn_code, rtn_outputs, rtn_err = \
                                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                                        cmd=exec_command,
                                        cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                        host_os_server=cls.frame_run_dict['config_dict'].get(
                                            tj_constants.EVN_SERVER_NIC_MODEL),
                                        host_os_client=cls.frame_run_dict['config_dict'].get(
                                            tj_constants.EVN_CLIENT_NIC_MODEL), shiled_error=True, print_outputs=False)
                                if rtn_code != RtnStatusEnum.SUCCESS.value:
                                    log.error("新包解压失败，升级失败，框架退出")
                                    exit(1)

                            # 版本包release信息
                            exec_command = f"cat {nic_package_path}/release_version.txt"
                            rtn_code, rtn_outputs, rtn_err = \
                                CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=exec_command,
                                    cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                    host_os_server=cls.frame_run_dict['config_dict'].
                                    get(tj_constants.EVN_SERVER_NIC_MODEL),
                                    host_os_client=cls.frame_run_dict['config_dict'].
                                    get(tj_constants.EVN_CLIENT_NIC_MODEL),
                                    shiled_error=True
                                )
                            log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')

                            # 获取makemode
                            log.info("获取make mode（debug or release）")
                            res = re.findall(r'\bmakemode:(\w+)\b', rtn_outputs)
                            if res:
                                target_upgrade_makemode = res[0]
                            else:
                                target_upgrade_makemode = 'debug'
                            if 'release' in target_upgrade_makemode:
                                test_version = "release"
                                test_version_short = ""
                            else:
                                test_version = "debug"
                                test_version_short = "d"

                            # 获取version
                            log.info("获取version")
                            res = re.findall(r'\bversion:([\w\.]+)\b', rtn_outputs)
                            if res:
                                target_upgrade_version = res[0]
                            else:
                                target_upgrade_version = '0.0.0.0'
                            target_upgrade_version_set = tuple([int(i) for i in target_upgrade_version.split('.')])

                            # 获取commit_id
                            log.info("获取commit_id")
                            res = re.findall(r'\bcommit_id:(\w+)\b', rtn_outputs)
                            if res:
                                target_upgrade_commit_id = res[0]
                            else:
                                target_upgrade_commit_id = '0000000'

                            # 获取branch
                            log.info("获取branch")
                            res = re.findall(r'\bbranch:(\S+)\b', rtn_outputs)
                            if res:
                                target_upgrade_branch = res[0]
                            else:
                                target_upgrade_branch = 'develop_rc_tucana-0.0.0_B000'

                            # 获取buildmode
                            log.info("获取buildmode")
                            res = re.findall(r'\bbuildmode:(\S+)\b', rtn_outputs)
                            if res:
                                target_upgrade_buildmode = res[0]
                            else:
                                target_upgrade_buildmode = 'asic'

                            log.info(f'检查是否为新包结构')
                            exec_command = f'ls {nic_package_path}/products/Firmware/Standard-Products/1260-X'
                            rtn_code, rtn_outputs, rtn_err = \
                                CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=exec_command,
                                    cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                    host_os_server=cls.frame_run_dict['config_dict'].
                                        get(tj_constants.EVN_SERVER_NIC_MODEL),
                                    host_os_client=cls.frame_run_dict['config_dict'].
                                        get(tj_constants.EVN_CLIENT_NIC_MODEL),
                                    shiled_error=True
                                )
                            log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
                            # 1. 如果products/Firmware/Standard-Products/1260-X中存在不同板卡对应的固件bin
                            # 2. 如果待升级版本大于2.0.0.24
                            # 满足以上条件之一，认为是新包结构
                            target_upgrade_pkt_new_struct_sub = False
                            if (('pcie-2-25' in rtn_outputs and
                                 'ocp-4-25' in rtn_outputs and
                                 'ocp-2-25' in rtn_outputs and
                                 'pcie-2-10' in rtn_outputs)):
                                target_upgrade_pkt_new_struct = True
                            else:
                                target_upgrade_pkt_new_struct = False
                            log.info(f'===> 新包结构: {target_upgrade_pkt_new_struct}')

                            log.info("获取待升级版本包中的固件版本")
                            exec_command = f"ls {nic_package_path}/products/Firmware/Standard-Products/{product_name}/"
                            rtn_code, rtn_outputs, rtn_err = \
                                CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=exec_command,
                                    cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                    host_os_server=cls.frame_run_dict['config_dict'].
                                        get(tj_constants.EVN_SERVER_NIC_MODEL),
                                    host_os_client=cls.frame_run_dict['config_dict'].
                                        get(tj_constants.EVN_CLIENT_NIC_MODEL),
                                    shiled_error=True
                                )
                            log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
                            current_get_version = re.findall(r"(\d+\.\d+\.\d+\.\d+)", rtn_outputs)
                            if current_get_version:
                                current_fw_version = current_get_version[0]
                            log.info("current_fw_version:{}".format(current_fw_version))
                            if current_fw_version in ["2.0.0.11"]:
                                upgrade_all = True
                                log.warning(f"升级版本为：{current_fw_version}，分区表改变，强制升级大包！！")

                            log.info("获取待升级版本包中的驱动版本")
                            if not target_upgrade_pkt_new_struct:
                                exec_command = f"ls {nic_package_path}/products/Src/pkgs/"
                            else:
                                exec_command = f"ls {nic_package_path}/products/Src/Driver/"
                            rtn_code, rtn_outputs, rtn_err = \
                                CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=exec_command,
                                    cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                    host_os_server=cls.frame_run_dict['config_dict'].
                                        get(tj_constants.EVN_SERVER_NIC_MODEL),
                                    host_os_client=cls.frame_run_dict['config_dict'].
                                        get(tj_constants.EVN_CLIENT_NIC_MODEL),
                                    shiled_error=True
                                )
                            log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
                            # current_get_version = re.findall(r"{}-(\d+\.\d+\.\d+\.\d+)".format(
                            #     target_nic_driver_name), rtn_outputs)
                            current_get_version = re.findall(r"-(\d+\.\d+\.\d+\.\d+)", rtn_outputs)
                            if current_get_version:
                                current_driver_version = current_get_version[0]
                            elif not target_upgrade_pkt_new_struct:
                                exec_command = f"ls {nic_package_path}/products/Src/Driver/"
                                rtn_code, rtn_outputs, rtn_err = \
                                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                                        cmd=exec_command,
                                        cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                        host_os_server=cls.frame_run_dict['config_dict'].
                                        get(tj_constants.EVN_SERVER_NIC_MODEL),
                                        host_os_client=cls.frame_run_dict['config_dict'].
                                        get(tj_constants.EVN_CLIENT_NIC_MODEL),
                                        shiled_error=True
                                    )
                                log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
                                current_get_version = re.findall(r"-(\d+\.\d+\.\d+\.\d+)", rtn_outputs)
                                if current_get_version:
                                    current_driver_version = current_get_version[0]
                                    target_upgrade_pkt_new_struct_sub = True
                            log.info("current_driver_version:{}".format(current_driver_version))

                            # current_get_version = re.findall(r"{}vf-(\d+\.\d+\.\d+\.\d+)".format(target_nic_driver_name),
                            #                                  rtn_outputs)
                            current_get_version = re.findall(r"-(\d+\.\d+\.\d+\.\d+)",
                                                             rtn_outputs)
                            if current_get_version:
                                current_driver_vf_version = current_get_version[0]
                            log.info("current_driver_vf_version:{}".format(current_driver_vf_version))

                            log.info("获取待升级版本包中的cli版本")
                            exec_command = f"ls {nic_package_path}/debuginfo/{target_nic_driver_name}_cli" \
                                           f"/debug/{architecture}/"
                            rtn_code, rtn_outputs, rtn_err = \
                                CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=exec_command,
                                    cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                    host_os_server=cls.frame_run_dict['config_dict'].
                                        get(tj_constants.EVN_SERVER_NIC_MODEL),
                                    host_os_client=cls.frame_run_dict['config_dict'].
                                        get(tj_constants.EVN_CLIENT_NIC_MODEL),
                                    shiled_error=True
                                )
                            log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
                            current_get_version = re.findall(r"(\d+\.\d+\.\d+\.\d+)", rtn_outputs)
                            if current_get_version:
                                current_cli_version = current_get_version[0]
                            log.info("current_cli_version:{}".format(current_cli_version))

                            # log.info("获取make mode（debug or release）")
                            # exec_command = f"cat {nic_package_path}/release_version.txt"
                            # rtn_code, rtn_outputs, rtn_err = \
                            #     CommandOperation.execute_command_based_paramiko_with_rtncode(
                            #         cmd=exec_command,
                            #         cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                            #         ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                            #         host_os_server=cls.frame_run_dict['config_dict'].
                            #             get(tj_constants.EVN_SERVER_NIC_MODEL),
                            #         host_os_client=cls.frame_run_dict['config_dict'].
                            #             get(tj_constants.EVN_CLIENT_NIC_MODEL),
                            #         shiled_error=True
                            #     )
                            # log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
                            # if 'release' in rtn_outputs:
                            #     test_version = "release"
                            #     test_version_short = ""
                            # else:
                            #     test_version = "debug"
                            #     test_version_short = "d"
                        else:
                            log.error(f'没有找到tar.gz压缩包!!!')
                            return False

                        log.info(f'替换新版本组件')
                        if target_nic_model == 'windows':
                            exec_command = "Get-ChildItem {} -Filter '*win2022*{}.tar.gz' " \
                                           "| Select-Object -ExpandProperty FullName". \
                                format(nic_package_path + "/host_driver", test_version)
                            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                                shiled_error=False
                            )
                            log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
                            if "tar.gz" in rtn_outputs:
                                exec_command = "tar -zxvf {} -C {}".format(rtn_outputs.split("\n")[0], win_driver_path)
                                rtn_code, rtn_outputs, rtn_err = \
                                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                                        cmd=exec_command,
                                        cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                        host_os_server=cls.frame_run_dict['config_dict'].get(
                                            tj_constants.EVN_SERVER_NIC_MODEL),
                                        host_os_client=cls.frame_run_dict['config_dict'].get(
                                            tj_constants.EVN_CLIENT_NIC_MODEL), shiled_error=True, print_outputs=False)
                                if rtn_code != RtnStatusEnum.SUCCESS.value:
                                    log.error(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                                    return False

                            if test_version == "release":
                                dest_ko_path = \
                                    os.path.join(win_driver_path, 'products/Drivers/Windows/{}-{}_win.x86_64.exe'
                                                 .format(target_nic_driver_name, current_driver_version, test_version))
                            else:
                                dest_ko_path = \
                                    os.path.join(win_driver_path, 'products/Drivers/Windows/{}-{}_win.x86_64.{}.exe'
                                                 .format(target_nic_driver_name, current_driver_version, test_version))

                            dest_ko_path_history_version = [dest_ko_path]
                        else:
                            os_version = 'rhel_9.1'
                            # 判断是否是Ubuntu
                            exec_command = "uname -a"
                            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                            )
                            log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
                            uname_a_result = rtn_outputs.lower()
                            if 'ubuntu' in rtn_outputs.lower():
                                os_version = 'ubuntu_22.04'
                            else:
                                # 判断centos具体版本
                                exec_command = "cat /etc/redhat-release"
                                rtn_code, rtn_outputs, rtn_err = \
                                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                                        cmd=exec_command, cmd_execute_address=target_execute_address,
                                        ssh_username=f'{root}',
                                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                        host_os_server=cls.frame_run_dict['config_dict'].get(
                                            tj_constants.EVN_SERVER_NIC_MODEL),
                                        host_os_client=cls.frame_run_dict['config_dict'].get(
                                            tj_constants.EVN_CLIENT_NIC_MODEL))
                                log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
                                if "CentOS" in rtn_outputs:
                                    versions = re.findall(r'release (\d\.\d)', rtn_outputs.lower())
                                    if versions:
                                        os_version = "centos_{}".format(versions[0])
                                elif "Red Hat" in rtn_outputs:
                                    versions = re.findall(r'release (\d\.\d)', rtn_outputs.lower())
                                    if versions:
                                        os_version = "rhel_{}".format(versions[0])
                                elif "Rocky" in rtn_outputs:
                                    versions = re.findall(r'release (\d\.\d)', rtn_outputs.lower())
                                    if versions:
                                        os_version = "rocky_{}".format(versions[0])
                                elif "NFSChina" in rtn_outputs:
                                    versions = re.findall(r'release (\d\.\d)\.2\d(\d\d\d\d)', rtn_outputs.lower())
                                    if versions:
                                        ver, vdate = versions[0]
                                        os_version = "NFSChina_{}_{}".format(ver, vdate)
                                else:
                                    exec_command = 'cat /etc/os-release'
                                    rtn_code, rtn_outputs, rtn_err = \
                                        CommandOperation.execute_command_based_paramiko_with_rtncode(
                                            cmd=exec_command, cmd_execute_address=target_execute_address,
                                            ssh_username=f'{root}',
                                            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                            host_os_server=cls.frame_run_dict['config_dict'].get(
                                                tj_constants.EVN_SERVER_NIC_MODEL),
                                            host_os_client=cls.frame_run_dict['config_dict'].get(
                                                tj_constants.EVN_CLIENT_NIC_MODEL))
                                    if "Kylin Linux Advanced Server" in rtn_outputs:
                                        if "4.19.90-21.2.9.wa".lower() in uname_a_result:
                                            os_version = 'Kylin_0721'
                                        elif "4.19.90-vhulk2001.1.0.0026.ns7.15".lower() in uname_a_result:
                                            os_version = 'Kylin_0429'
                                        else:
                                            os_version = 'Kylin_V10_SP3'
                                    if "UnionTech OS Server" in rtn_outputs:
                                        os_version = 'UOS_V20_1050'
                                    if "Anolis OS" in rtn_outputs:
                                        os_version = 'AnolisOS_8.8'
                                    if "openEuler" in rtn_outputs:
                                        os_version = 'openEuler_22.03_LTS'

                            dest_ko_path = os.path.join(
                                nic_package_path, 'debuginfo/Drivers/x86_64/Linux/{}/ETH/ASIC/{}'.format(
                                    os_version, target_nic_driver_name))

                            dest_ko_path_history_version = [dest_ko_path]

                        if upgrade_fw_only:
                            log.warning(f'upgrade_fw_only,不进行驱动ko更新')
                        else:
                            log.info(f'build驱动ko更新')
                            build_ko_update_flag = False
                            if cls.frame_run_dict['config_dict'].get(
                                    constants.ENV_TEST_OBJECT) == constants.ENV_RUN_MODE_WITH_SRC_KO:
                                make_build_para = ""
                                build_ko_update_flag = cls.build_ko_and_update(
                                    os_version, target_host_ip, target_execute_address, make_build_para)
                            log.info("build_ko_update_flag:{}".format(build_ko_update_flag))

                        log.info("获取固件版本")
                        exec_command = f"ls {nic_package_path}/products/Firmware/Standard-Products/{product_name}/"
                        rtn_code, rtn_outputs, rtn_err = \
                            CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command,
                                cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                host_os_server=cls.frame_run_dict['config_dict'].
                                    get(tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].
                                    get(tj_constants.EVN_CLIENT_NIC_MODEL),
                                shiled_error=True
                            )
                        log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
                        current_get_version = re.findall(r"(\d+\.\d+\.\d+\.\d+)", rtn_outputs)
                        if current_get_version:
                            current_fw_version = current_get_version[0]
                        log.info("current_fw_version:{}".format(current_fw_version))

                        log.info("获取驱动版本")
                        if not target_upgrade_pkt_new_struct and not target_upgrade_pkt_new_struct_sub:
                            exec_command = f"ls {nic_package_path}/products/Src/pkgs/"
                        else:
                            exec_command = f"ls {nic_package_path}/products/Src/Driver/"
                        rtn_code, rtn_outputs, rtn_err = \
                            CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command,
                                cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                host_os_server=cls.frame_run_dict['config_dict'].
                                    get(tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].
                                    get(tj_constants.EVN_CLIENT_NIC_MODEL),
                                shiled_error=True
                            )
                        log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
                        current_get_version = re.findall(r"-(\d+\.\d+\.\d+\.\d+)", rtn_outputs)
                        if current_get_version:
                            current_driver_version = current_get_version[0]
                        log.info("current_driver_version:{}".format(current_driver_version))
                        current_get_version = re.findall(r"-(\d+\.\d+\.\d+\.\d+)",
                                                         rtn_outputs)
                        if current_get_version:
                            current_driver_vf_version = current_get_version[0]
                        log.info("current_driver_vf_version:{}".format(current_driver_vf_version))

                        log.info("获取cli版本")
                        exec_command = f"ls {nic_package_path}/debuginfo/{target_nic_driver_name}_cli" \
                                       f"/debug/{architecture}/"
                        rtn_code, rtn_outputs, rtn_err = \
                            CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command,
                                cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                host_os_server=cls.frame_run_dict['config_dict'].
                                    get(tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].
                                    get(tj_constants.EVN_CLIENT_NIC_MODEL),
                                shiled_error=True
                            )
                        log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
                        current_get_version = re.findall(r"(\d+\.\d+\.\d+\.\d+)", rtn_outputs)
                        if current_get_version:
                            current_cli_version = current_get_version[0]
                        log.info("current_cli_version:{}".format(current_cli_version))

                        log.info(f'更新cli')
                        cls.update_cli(root_path, nic_package_path, current_cli_version, architecture,
                                       suffix, test_version, test_version_short, target_nic_model, target_host_ip,
                                       target_nic_driver_name, target_execute_address, root)

                        log.info(f'升级固件')
                        need_upgrade_soc = True
                        if target_nic_model == 'windows':
                            need_upgrade_soc = False
                            log.warning("当前windows不测试固件，不进行固件升级")

                        exec_command = f"{sxecli} show"
                        rtn_code, sxecli_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command,
                            cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL))
                        bdfs = re.findall(r"(\w\w\w\w:\w\w:\w\w.\w)", sxecli_outputs)
                        if upgrade_soc_check:
                            if target_nic_driver_name == cls.nicg:
                                bdf = bdfs[0]
                                exec_command = f"{sxecli} -d {bdf} show | grep 'Firmware Version' " + "| awk '{print $NF}'"
                            else:
                                exec_command = f"{sxecli} /p0 show | grep 'Firmware Version' " + "| awk '{print $NF}'"
                            rtn_code, rtn_outputs, rtn_err = \
                                CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=exec_command,
                                    cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                    host_os_server=cls.frame_run_dict['config_dict'].get(
                                        tj_constants.EVN_SERVER_NIC_MODEL),
                                    host_os_client=cls.frame_run_dict['config_dict'].get(
                                        tj_constants.EVN_CLIENT_NIC_MODEL))
                            if rtn_outputs == current_fw_version or upgrade_driver_only:
                                need_upgrade_soc = False
                                log.warning("当前固件版本已为要升级版本：{},不升级固件，仅替换其他部件".format(current_fw_version))
                        elif upgrade_driver_only:
                            need_upgrade_soc = False
                            log.warning("当前参数设定不要求升级固件版本：仅替换其他部件")

                        if 'Controller 1' in sxecli_outputs or "Device 1" in sxecli_outputs:
                            log.info("============> 多卡环境")

                        if target_bdf:
                            ctrl_id = target_bdf
                        else:
                            if target_nic_driver_name == cls.nicg:
                                if bdfs:
                                    log.error(f"env_config.ini未指定bdf，取cli获取的第一个：{bdfs[0]}")
                                    ctrl_id = bdfs[0]
                                else:
                                    log.error("未获取到有效bdf，停止升级")
                                    exit(1)
                            else:
                                ctrl_id = 0

                        if not need_upgrade_soc:
                            break

                        # 旧的版本包目录结构
                        if not target_upgrade_pkt_new_struct and not target_upgrade_pkt_new_struct_sub:
                            # 网卡固件升级文件目录
                            if upgrade_all:
                                dest_file_path = os.path.join(
                                    nic_package_path, 'factory/Firmware/{}/NorflashRegion{}asic_{}.bin'.format(
                                        product_name, fw_mark, current_fw_version))
                            else:
                                dest_file_path = os.path.join(
                                    nic_package_path,
                                    'products/Firmware/Standard-Products/{}/Image_{}_{}_NIC-{}.bin'.format(
                                        product_name, current_fw_version, runmod, product_name))
                            # recover固件升级文件目录
                            recover_file_path = os.path.join(
                                    nic_package_path,
                                    f'debuginfo/sxe2_fw_asic/{test_version}/header_recovery_sxe2_fw.bin')
                        # 新的版本包目录结构
                        else:
                            # 网卡固件升级文件目录
                            if upgrade_all:
                                dest_file_path = os.path.join(
                                    nic_package_path,
                                    f'factory/Firmware/{product_name}/{target_board_type_mark}/NorflashRegion{fw_mark}asic_{current_fw_version}.bin')
                            else:
                                dest_file_path = os.path.join(
                                    nic_package_path,
                                    f'products/Firmware/Standard-Products/{product_name}/Image_{current_fw_version}_{runmod}_NIC_{target_board_type}-{product_name}.bin')
                            # recover固件升级文件目录
                            recover_file_path = os.path.join(
                                    nic_package_path,
                                    f'technical_support/Firmware/1260-X/Recovery/{target_board_type_mark}/header_config_eeprom_bl_recovery_{current_fw_version}.bin')

                        # if current_fw_version in ["2.0.0.15"]:
                        #     if host_op not in ["host_reboot", "host_dc"]:
                        #         host_op = "host_reboot"
                        #         log.warning(f"current_fw_version:{current_fw_version},必须重启主机，否则驱动不匹配")

                        # 2.0.0.12特殊要求，升级前执行cli -d <device> set config default
                        if current_fw_version in ["2.0.0.12", "2.0.0.17"]:
                            log.warning(f"升级版本为：{current_fw_version}，需要执行命令：cli -d <device> set config default")
                            exec_command = f"{sxecli} -d {ctrl_id} set config default"
                            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command,
                                cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                                timeout=1800)
                            if rtn_code != RtnStatusEnum.SUCCESS.value:
                                log.error(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                            else:
                                log.info(f'ASIC->command:{exec_command}, 执行成功')

                        # 先升级recover固件
                        log.info(f'先升级recover固件')
                        exec_command = f"{sxecli} -d {ctrl_id} upgrade eeprom file={recover_file_path}"
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command,
                            cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                            timeout=1800)
                        if rtn_code != RtnStatusEnum.SUCCESS.value:
                            log.error(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                        else:
                            log.info(f'ASIC->command:{exec_command}, 执行成功')

                        # 再升级固件
                        log.info(f'再升级固件')
                        if upgrade_all:
                            cmd_timeout = 3600
                            if target_nic_driver_name == cls.nicg:
                                bdf = ctrl_id
                                exec_command = f"{sxecli} -d {bdf} debug upgrade packet {dest_file_path}"
                            else:
                                exec_command = f"{sxecli} /p{ctrl_id} debug upgrade packet {dest_file_path}"
                            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command,
                                cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                                timeout=cmd_timeout)
                        else:
                            cmd_timeout = 1800
                            if target_nic_driver_name == cls.nicg:
                                bdf = ctrl_id
                                exec_command = f"{sxecli} -d {bdf} upgrade file={dest_file_path}"
                            else:
                                exec_command = f"{sxecli} /p{ctrl_id} upgrade file={dest_file_path}"
                            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command,
                                cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                                timeout=cmd_timeout)
                            if rtn_code != RtnStatusEnum.SUCCESS.value:
                                if target_nic_driver_name == cls.nicg:
                                    bdf = ctrl_id
                                    exec_command = f"{sxecli} -d {bdf} upgrade file={dest_file_path} noverchk"
                                else:
                                    exec_command = f"{sxecli} /p{ctrl_id} upgrade file={dest_file_path} noverchk"
                                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=exec_command,
                                    cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                                    timeout=cmd_timeout)
                        if rtn_code != RtnStatusEnum.SUCCESS.value:
                            log.error(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                            if "Controller not found" in rtn_outputs + rtn_err:
                                log.warning("可能是未加载驱动，尝试使用insmod重新加载.")
                                exec_command = "rmmod {}".format(target_nic_driver_name)
                                rtn_code, rtn_outputs, rtn_err = \
                                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                                        cmd=exec_command,
                                        cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                        host_os_server=cls.frame_run_dict['config_dict'].get(
                                            tj_constants.EVN_SERVER_NIC_MODEL),
                                        host_os_client=cls.frame_run_dict['config_dict'].get(
                                            tj_constants.EVN_CLIENT_NIC_MODEL))
                                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

                                command = f"insmod /root/{cls.nicg}_auxiliary.ko"
                                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=command, cmd_execute_address=target_execute_address,
                                    ssh_port=str(cls.test_port),
                                    ssh_username=f'root',
                                    host_os_server=cls.frame_run_dict['config_dict'].get(
                                        tj_constants.EVN_SERVER_NIC_MODEL),
                                    host_os_client=cls.frame_run_dict['config_dict'].get(
                                        tj_constants.EVN_CLIENT_NIC_MODEL)
                                )

                                # 此处不管是什么模式，均使用insmod修复环境来升级
                                exec_command = "insmod /root/{}.ko".format(target_nic_driver_name)
                                rtn_code, rtn_outputs, rtn_err = \
                                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                                        cmd=exec_command,
                                        cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                        host_os_server=cls.frame_run_dict['config_dict'].get(
                                            tj_constants.EVN_SERVER_NIC_MODEL),
                                        host_os_client=cls.frame_run_dict['config_dict'].get(
                                            tj_constants.EVN_CLIENT_NIC_MODEL))
                                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

                                exec_command = f"{sxecli} show"
                                rtn_code, rtn_outputs, rtn_err = CommandOperation. \
                                    execute_command_based_paramiko_with_rtncode(
                                    cmd=exec_command,
                                    cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                    host_os_server=cls.frame_run_dict['config_dict'].get(
                                        tj_constants.EVN_SERVER_NIC_MODEL),
                                    host_os_client=cls.frame_run_dict['config_dict'].get(
                                        tj_constants.EVN_CLIENT_NIC_MODEL))
                                if "Controller not found" in rtn_outputs + rtn_err or \
                                        ("Device 0" not in rtn_outputs + rtn_err and "Controller 0" not in rtn_outputs + rtn_err):
                                    if cls.frame_run_dict['config_dict'].get(
                                            constants.ENV_TEST_OBJECT) == constants.ENV_RUN_MODE_WITH_SRC:
                                        log.info("源码包测试，当前insmod {}.ko失败，尝试使用源码包安装驱动".
                                                 format(target_nic_driver_name))
                                        log.warning(f'卸载驱动rpm、源码包')
                                        cls.uninstall_driver_rpm_pkg(os_version, target_host_ip,
                                                                     target_execute_address)
                                        log.warning(f'安装驱动源码包')
                                        if not cls.__check_dkms_install(
                                                target_host_ip, target_execute_address,
                                                cls.frame_run_dict['config_dict'].get(
                                                    tj_constants.EVN_SERVER_NIC_MODEL),
                                                cls.frame_run_dict['config_dict'].get(
                                                    tj_constants.EVN_CLIENT_NIC_MODEL)):
                                            log.warning(f'安装驱动源码包必须安装dkms,当前无dkms无法继续测试，'
                                                        f'测试框架退出，请检查环境。')
                                            exit(1)
                                        cls.install_driver_rpm_pkg(constants.ENV_RUN_MODE_WITH_SRC, os_version,
                                                                   target_host_ip, target_execute_address, architecture)

                            # 升级固件
                            if upgrade_all:
                                cmd_timeout = 3600
                                if target_nic_driver_name == cls.nicg:
                                    bdf = ctrl_id
                                    exec_command = f"{sxecli} -d {bdf} debug upgrade packet {dest_file_path}"
                                else:
                                    exec_command = f"{sxecli} /p{ctrl_id} debug upgrade packet {dest_file_path}"
                                rtn_code, rtn_outputs, rtn_err = \
                                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                                        cmd=exec_command,
                                        cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                        host_os_server=cls.frame_run_dict['config_dict'].get(
                                            tj_constants.EVN_SERVER_NIC_MODEL),
                                        host_os_client=cls.frame_run_dict['config_dict'].get(
                                            tj_constants.EVN_CLIENT_NIC_MODEL), timeout=cmd_timeout)
                            else:
                                cmd_timeout = 1800
                                if target_nic_driver_name == cls.nicg:
                                    bdf = ctrl_id
                                    exec_command = f"{sxecli} -d {bdf} upgrade file={dest_file_path}"
                                else:
                                    exec_command = f"{sxecli} /p{ctrl_id} upgrade file={dest_file_path}"
                                rtn_code, rtn_outputs, rtn_err = \
                                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                                        cmd=exec_command,
                                        cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                        host_os_server=cls.frame_run_dict['config_dict'].get(
                                            tj_constants.EVN_SERVER_NIC_MODEL),
                                        host_os_client=cls.frame_run_dict['config_dict'].get(
                                            tj_constants.EVN_CLIENT_NIC_MODEL), timeout=cmd_timeout)
                                if rtn_code != RtnStatusEnum.SUCCESS.value:
                                    if target_nic_driver_name == cls.nicg:
                                        bdf = ctrl_id
                                        exec_command = f"{sxecli} -d {bdf} upgrade file={dest_file_path} noverchk"
                                    else:
                                        exec_command = f"{sxecli} /p{ctrl_id} upgrade file={dest_file_path} noverchk"
                                    rtn_code, rtn_outputs, rtn_err = \
                                        CommandOperation.execute_command_based_paramiko_with_rtncode(
                                            cmd=exec_command,
                                            cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                            host_os_server=cls.frame_run_dict['config_dict'].get(
                                                tj_constants.EVN_SERVER_NIC_MODEL),
                                            host_os_client=cls.frame_run_dict['config_dict'].get(
                                                tj_constants.EVN_CLIENT_NIC_MODEL), timeout=cmd_timeout)
                            if rtn_code != RtnStatusEnum.SUCCESS.value:
                                log.error(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                                log.warning(f'版本升级失败，测试框架退出！！')
                                exit(1)
                                # return False
                            else:
                                log.info(f'ASIC->command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                        else:
                            log.info(f'ASIC->command:{exec_command}, 执行成功')

                        if target_nic_model != 'windows':
                            if upgrade_fw_only:
                                log.warning(f'upgrade_fw_only,不进行卸载驱动rpm、源码包')
                                pass
                            else:
                                log.warning(f'卸载驱动rpm、源码包')
                                cls.uninstall_driver_rpm_pkg(os_version, target_host_ip, target_execute_address)
                                if cls.frame_run_dict['config_dict'].get(
                                        constants.ENV_TEST_OBJECT) == constants.ENV_RUN_MODE_WITH_SRC:
                                    log.warning(f'安装驱动源码包')
                                    if not cls.__check_dkms_install(
                                            target_host_ip, target_execute_address,
                                            cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                                            cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)):
                                        log.warning(f'安装驱动源码包必须安装dkms,当前无dkms无法继续测试，测试框架退出，请检查环境。')
                                        exit(1)
                                    cls.install_driver_rpm_pkg(constants.ENV_RUN_MODE_WITH_SRC, os_version,
                                                               target_host_ip, target_execute_address, architecture)

                                elif cls.frame_run_dict['config_dict'].get(
                                        constants.ENV_TEST_OBJECT) in [constants.ENV_RUN_MODE_WITH_RPM,
                                                                       constants.ENV_RUN_MODE_WITH_SRPM,
                                                                       constants.ENV_RUN_MODE_WITH_KMOD_SRPM]:
                                    rpm_type = cls.frame_run_dict['config_dict'].get(
                                        constants.ENV_TEST_OBJECT)
                                    log.warning('安装驱动rpm包, type:{}'.format(rpm_type))
                                    cls.install_driver_rpm_pkg(rpm_type, os_version,
                                                               target_host_ip, target_execute_address, architecture)

                        need_use_bmc_reboot = False
                        if need_upgrade_soc:
                            if target_nic_model == 'windows':
                                pass
                            else:
                                log.warning(f'通过core reset重启固件')
                                if target_nic_driver_name == cls.nicg:
                                    if current_fw_version in ["2.0.0.15", "2.1.0.1"]:
                                        log.warning(f"current_fw_version:{current_fw_version},需要先卸载旧驱动，再使用串口命令执行core reset,循环内不支持卸载驱动和core reset，放到循环外")
                                    else:
                                        bdf = ctrl_id
                                        exec_command = f"{sxecli} -d {bdf} reset type=0"
                                        rtn_code, rtn_outputs, rtn_err = \
                                            CommandOperation.execute_command_based_paramiko_with_rtncode(
                                                cmd=exec_command,
                                                cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                                host_os_server=cls.frame_run_dict['config_dict'].get(
                                                    tj_constants.EVN_SERVER_NIC_MODEL),
                                                host_os_client=cls.frame_run_dict['config_dict'].get(
                                                    tj_constants.EVN_CLIENT_NIC_MODEL))
                                        # log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                                        time.sleep(15)
                                        if rtn_code != RtnStatusEnum.SUCCESS.value:
                                            # need_use_bmc_reboot = True
                                            log.info("即便不执行soc reset，当前已无需bmc重启??? 待验证。。。")
                                            need_use_bmc_reboot = False
                                else:
                                    log.info("当前已无需执行reset soc")

                # 所有platform均跳过升级，则跳过后续升级步骤
                if skip_upgrade == len(target_platfrom_list):
                    log.info(f'所有platform均跳过升级，跳过后续升级步骤')
                    continue
                elif skip_upgrade == 0:
                    log.info(f'无platform跳过升级，继续执行后续升级步骤')
                else:
                    log.info(f'部分platform均跳过升级，继续执行后续升级步骤')

                if current_fw_version in ["2.0.0.15", "2.1.0.1"] and need_upgrade_soc:
                    log.warning(f"current_fw_version:{current_fw_version},需要先卸载旧驱动，再使用串口命令执行core reset")
                    # 循环内不支持卸载驱动和core reset，放到循环外
                    exec_command = 'rmmod {}'.format(target_nic_driver_name)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address,
                        ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    exec_command = 'rmmod {}vf'.format(target_nic_driver_name)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address,
                        ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

                    cmd = f'/debug custom sxe2 coredump trigger'
                    mark = "SHOW DONE"
                    result = cls.__excute_com_cmd(target_execute_address, cmd, mark, all_port=False)
                    time.sleep(60)
                    if not result:
                        log.error("串口执行coredump reset失败，请手动确认执行")
                        exit(1)

                cls.__check_mac_is_available()

                log.warning(f'备份上一个版本的dpdk工具')
                if target_nic_model == 'windows':
                    exec_command = f"Remove-Item {root_path}dpdk_bk -Recurse -Force;" \
                                   f"Rename-Item -Path {root_path}dpdk -NewName {root_path}dpdk_bk"
                else:
                    exec_command = f"rm -rf {root_path}dpdk_bk;mv {root_path}dpdk {root_path}dpdk_bk"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command,
                    cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(
                        tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(
                        tj_constants.EVN_CLIENT_NIC_MODEL))

                log.warning(f'更新当前版本的dpdk工具')
                if dpdk_build:
                    log.info("==>DPDK {} 源码包编译...".format(dpdk_version))
                    dpdk_src_path = "/home/test/ps3test/packages/nic_pkgs/dpdk-org/dpdk-org"
                    exec_command = "scp -P {} -r {} {}@{}:{}".format(
                        cls.test_port, dpdk_src_path, root, target_host_ip, nic_package_path)
                    rtn_code, result = cls.getstatusoutput(exec_command)
                    log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
                    if rtn_code != RtnStatusEnum.SUCCESS.value:
                        log.error("拷包失败！")
                        exit(0)
                    dpdk_src_path = "/home/test/ps3test/packages/nic_pkgs/dpdk-org/base/dpdk-{}.tar.gz". \
                        format(dpdk_version)
                    exec_command = "scp -P {} -r {} {}@{}:{}/dpdk-org/".format(
                        cls.test_port, dpdk_src_path, root, target_host_ip, nic_package_path)
                    rtn_code, result = cls.getstatusoutput(exec_command)
                    log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
                    if rtn_code != RtnStatusEnum.SUCCESS.value:
                        log.error("拷包失败！")
                        exit(0)
                    dpdksrc_path = nic_package_path + "/dpdk-org/dpdk-{}.tar.gz".format(dpdk_version)
                    # sxe-dpdk-1.2.1.5-src.tar.gz
                    if not target_upgrade_pkt_new_struct and not target_upgrade_pkt_new_struct_sub:
                        sxedpdksrc_path = nic_package_path + "/products/Src/pkgs/"
                        exec_command = f"ls {sxedpdksrc_path}| grep dpdk"
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command,
                            cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                            host_os_server=cls.frame_run_dict['config_dict'].get(
                                tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(
                                tj_constants.EVN_CLIENT_NIC_MODEL))
                        dpdk_current_driver_versions = re.findall(r"(\d+\.\d+\.\d+\.\d+)", rtn_outputs)
                        if dpdk_current_driver_versions:
                            dpdk_current_driver_version = dpdk_current_driver_versions[0]
                        else:
                            dpdk_current_driver_version = current_driver_version
                        sxedpdksrc_path = nic_package_path + \
                                          "/products/Src/pkgs/{}-dpdk-{}-src.tar.gz".format(
                                              target_nic_driver_name, dpdk_current_driver_version)
                    else:
                        sxedpdksrc_path = nic_package_path + "/products/Src/DPDK/"
                        exec_command = f"ls {sxedpdksrc_path}| grep dpdk"
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command,
                            cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                            host_os_server=cls.frame_run_dict['config_dict'].get(
                                tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(
                                tj_constants.EVN_CLIENT_NIC_MODEL))
                        dpdk_current_driver_versions = re.findall(r"(\d+\.\d+\.\d+\.\d+)", rtn_outputs)
                        if dpdk_current_driver_versions:
                            dpdk_current_driver_version = dpdk_current_driver_versions[0]
                        else:
                            dpdk_current_driver_version = current_driver_version
                        sxedpdksrc_path = nic_package_path + \
                                          "/products/Src/DPDK/{}-dpdk-{}-src.tar.gz".format(
                                              target_nic_driver_name, dpdk_current_driver_version)
                    if pktgen_build:
                        if "22." in dpdk_version or "23." in dpdk_version:
                            pktgen_build_cmd = " --pktgen {}". \
                                format(nic_package_path + "/dpdk-org/pktgen-dpdk-pktgen-24.07.0.tar.gz")
                        elif "24." in dpdk_version:
                            pktgen_build_cmd = " --pktgen {}".\
                                format(nic_package_path + "/dpdk-org/pktgen-dpdk-pktgen-24.10.3.tar.gz")
                        else:
                            pktgen_build_cmd = " --pktgen {}". \
                                format(nic_package_path + "/dpdk-org/pktgen-dpdk-pktgen-21.03.1.tar.gz")
                    else:
                        pktgen_build_cmd = ""

                    if dpdk_build_make:
                        make = "-make "
                    else:
                        make = ""
                    if dpdk_l4:
                        l4 = "-l4 "
                    else:
                        l4 = ""
                    if dpdk_keep:
                        modify = ""
                    else:
                        modify = "-m "

                    if scgbe_compile:
                        sc = "--scv {}_asic ".format(cls.nicg)
                        modify = ""
                    elif sxe_compile:
                        sc = "-sc "
                    else:
                        sc = ""

                    exec_command = "/usr/bin/esxe.py {}{}{}{}--dpdksrc {} -p {}{}". \
                        format(sc, modify, make, l4, dpdksrc_path, sxedpdksrc_path, pktgen_build_cmd)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, timeout=3600,
                        cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_CLIENT_NIC_MODEL))
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    if ".11." in dpdk_version:
                        dpdksrc_app_path = nic_package_path + "/dpdk-org/dpdk-stable-{}/dpdk".format(dpdk_version)
                    else:
                        dpdksrc_app_path = nic_package_path + "/dpdk-org/dpdk-{}/dpdk".format(dpdk_version)
                    exec_command = "cat {}/version.txt".format(dpdksrc_app_path)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command,
                        cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_CLIENT_NIC_MODEL))
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    if dpdk_version not in rtn_outputs:
                        log.error("DPDK编译失败！")
                        exit(0)
                    if pktgen_build:
                        if "22." in dpdk_version or "23." in dpdk_version:
                            pktgen_app_path = nic_package_path + "/dpdk-org/pktgen-dpdk-pktgen-24.07.0/pktgen"
                        elif "24." in dpdk_version:
                            pktgen_app_path = nic_package_path + "/dpdk-org/pktgen-dpdk-pktgen-24.10.3/pktgen"
                        else:
                            pktgen_app_path = nic_package_path + "/dpdk-org/pktgen-dpdk-pktgen-21.03.1/pktgen"
                        exec_command = "cat {}/version.txt".format(pktgen_app_path)
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command,
                            cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                            host_os_server=cls.frame_run_dict['config_dict'].get(
                                tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(
                                tj_constants.EVN_CLIENT_NIC_MODEL))
                        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                        if "pktgen-dpdk-pktgen" not in rtn_outputs:
                            log.error("pktgen编译失败！")
                            exit(0)

                        exec_command = f"{cp} {pktgen_app_path} {root_path}"
                        rtn_code, rtn_outputs, rtn_err = CommandOperation. \
                            execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command,
                            cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                            host_os_server=cls.frame_run_dict['config_dict'].get(
                                tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(
                                tj_constants.EVN_CLIENT_NIC_MODEL))
                        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

                    if target_nic_model == 'windows':
                        exec_command = f"Copy-Item -Path {dpdksrc_app_path} -Destination " \
                                       f"{root_path}dpdk -Force -Recurse"
                    else:
                        exec_command = f"{cp} {dpdksrc_app_path} {root_path}dpdk"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command,
                        cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_CLIENT_NIC_MODEL))
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                else:
                    log.info("确认dpdk app是否分架构文件夹")
                    exec_command = f"ls {root_path}publish_version/debuginfo/DPDK"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command,
                        cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_CLIENT_NIC_MODEL))

                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    if "x86_64_linux" in rtn_outputs and "x86_64" in architecture:
                        arc_path = "x86_64_linux/"
                    elif "x86_64" in rtn_outputs and "x86_64" in architecture:
                        arc_path = "x86_64/"
                    elif "arm64" in rtn_outputs and "arm64" in architecture:
                        arc_path = "arm64/"
                    elif "arm32" in rtn_outputs and "arm32" in architecture:
                        arc_path = "arm32/"
                    else:
                        arc_path = ""

                    dpdk_path = f"{root_path}publish_version/products/DPDK/{arc_path}{dpdk_version}/app"
                    exec_command = f"ls {dpdk_path}/dpdk-pdump"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command,
                        cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_CLIENT_NIC_MODEL))
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    if "No such file or directory".lower() in (rtn_outputs + rtn_err).lower() or "没有那个文件或目录" in (rtn_outputs + rtn_err):
                        dpdk_path = f"{root_path}publish_version/debuginfo/DPDK/{arc_path}{dpdk_version}/app"
                        log.warning(f"dpdk路径变更成{dpdk_path}")

                    if target_nic_model == 'windows':
                        exec_command = f"Copy-Item -Path {dpdk_path} -Destination " \
                                       f"{root_path}dpdk -Force -Recurse"
                    else:
                        exec_command = f"{cp} {dpdk_path} {root_path}dpdk"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command,
                        cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_CLIENT_NIC_MODEL))
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

                    exec_command = f"echo {dpdk_version} > {root_path}dpdk/version.txt"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command,
                        cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_CLIENT_NIC_MODEL))
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                log.info("dpdk app统一命名")
                cls.dpdk_app_uniform_name(f"{root_path}dpdk/", target_host_ip, target_execute_address,
                                          target_nic_model)

                if target_nic_model == 'windows':
                    exec_command = "sync"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command,
                        cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(
                            tj_constants.EVN_CLIENT_NIC_MODEL))
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    time.sleep(3)

                if host_op in ["host_reboot", "host_dc"]:
                    if host_op == "host_dc":
                        log.info("需要使用BMC重启")
                        if target_host_ip == cls.frame_run_dict['ip_dict'][constants.TEST_CONFIG_SERVER_IP]:
                            bmc_ip = cls.frame_run_dict['ip_dict'][constants.TEST_CONFIG_SERVER_BMC_IP]
                            uname = cls.frame_run_dict['ip_dict'][constants.TEST_CONFIG_SUNAME]
                            passwd = cls.frame_run_dict['ip_dict'][constants.TEST_CONFIG_SUPASSWD]
                        else:
                            bmc_ip = cls.frame_run_dict['ip_dict'][constants.TEST_CONFIG_CLIENT_BMC_IP]
                            uname = cls.frame_run_dict['ip_dict'][constants.TEST_CONFIG_CUNAME]
                            passwd = cls.frame_run_dict['ip_dict'][constants.TEST_CONFIG_CUPASSWD]
                        exec_command = f"ipmitool -U {uname} -I lan -H {bmc_ip} -P '{passwd}' power off"
                        status, result = subprocess.getstatusoutput(exec_command)
                        log.info("cmd:{}, status:{}, result:{}".format(exec_command, status, result))
                        time.sleep(10)
                        exec_command = f"ipmitool -U {uname} -I lan -H {bmc_ip} -P '{passwd}' power on"
                        status, result = subprocess.getstatusoutput(exec_command)
                        log.info("cmd:{}, status:{}, result:{}".format(exec_command, status, result))
                    else:
                        log.info(f'重启主机')
                        if target_nic_model == 'windows':
                            exec_command = "Restart-Computer -Force"
                        else:
                            exec_command = f"reboot"
                        rtn_code, rtn_outputs, rtn_err = \
                            CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command,
                                cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                host_os_server=cls.frame_run_dict['config_dict'].get(
                                    tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].get(
                                    tj_constants.EVN_CLIENT_NIC_MODEL))
                        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

                    # 等待主机重启
                    retry = 20
                    while retry:
                        log.info(f'等待重启:{retry}')
                        time.sleep(30)
                        is_ping = False
                        # if target_nic_model == 'windows':
                        #     is_ping = True
                        if RtnStatusEnum.SUCCESS.value == CommandOperation.check_ip_connect(
                                ip=target_host_ip, ssh_port=str(cls.test_port),
                                is_ping=is_ping, ssh_username=root):
                            break
                        retry -= 1
                    if retry <= 0:
                        log.warning("服务器reboot失败，尝试BMC重启")
                        if target_host_ip == cls.frame_run_dict['ip_dict'][constants.TEST_CONFIG_SERVER_IP]:
                            server_nic_ip = cls.frame_run_dict['ip_dict'][constants.TEST_CONFIG_SERVER_BMC_IP]
                            server_bmc_name = cls.frame_run_dict['ip_dict'][constants.TEST_CONFIG_SUNAME]
                            server_bmc_password = cls.frame_run_dict['ip_dict'][constants.TEST_CONFIG_SUPASSWD]
                        else:
                            server_nic_ip = cls.frame_run_dict['ip_dict'][constants.TEST_CONFIG_CLIENT_BMC_IP]
                            server_bmc_name = cls.frame_run_dict['ip_dict'][constants.TEST_CONFIG_CUNAME]
                            server_bmc_password = cls.frame_run_dict['ip_dict'][constants.TEST_CONFIG_CUPASSWD]
                        reboot_result = HostOperation.host_bmc_reboot(
                            ssh_ip=target_host_ip, ssh_port=str(cls.test_port), bmc_ip=server_nic_ip,
                            uname=server_bmc_name, passwd=server_bmc_password, force_check=False)
                        if reboot_result == RtnStatusEnum.SUCCESS.value:
                            log.error(f'服务器长时间无法启动，请检查环境！！！')
                            return False
                else:
                    exec_command = 'rmmod {}'.format(target_nic_driver_name)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    exec_command = 'rmmod {}vf'.format(target_nic_driver_name)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    if upgrade_rdma:
                        exec_command = 'rmmod {}_ktest'.format(target_nic_driver_name)
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                        )
                        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                        exec_command = 'rmmod {}rdma'.format(target_nic_driver_name)
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                        )
                        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

                if target_nic_model == 'windows':
                    log.info(f"固件已经升级并重启主机完成，windows驱动当前无法自动化更新，需要手动更新，路径为:"
                             f"{root_path}win_server_2022_{test_version}")
                    if index > 0:
                        exit(0)
                    else:
                        continue
                # 重新加载驱动
                log.info(f'重新加载驱动')
                # ko对dca有依赖, 每次重启后执行一次，防止后续insmod ko报
                # insmod: ERROR: could not insert module sxe.ko: Unknown symbol in module，可dmesg看报错信息
                exec_command = "modprobe dca"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )

                command = f"insmod /root/{cls.nicg}_auxiliary.ko"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                    ssh_username=f'root',
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )

                if cls.frame_run_dict['config_dict'].get(
                        constants.ENV_TEST_OBJECT) in [constants.ENV_RUN_MODE_WITH_SRC,
                                                       constants.ENV_RUN_MODE_WITH_RPM,
                                                       constants.ENV_RUN_MODE_WITH_SRPM,
                                                       constants.ENV_RUN_MODE_WITH_KMOD_SRPM]:
                    exec_command = 'modprobe {}'.format(target_nic_driver_name)
                else:
                    exec_command = 'insmod /root/{}.ko'.format(target_nic_driver_name)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, rtn_code：{rtn_code}, outputs:{rtn_outputs}, \nerror:{rtn_err}')

                if cls.frame_run_dict['config_dict'].get(
                        constants.ENV_TEST_OBJECT) in [constants.ENV_RUN_MODE_WITH_SRC,
                                                       constants.ENV_RUN_MODE_WITH_RPM,
                                                       constants.ENV_RUN_MODE_WITH_SRPM,
                                                       constants.ENV_RUN_MODE_WITH_KMOD_SRPM]:
                    exec_command = 'modprobe {}vf'.format(target_nic_driver_name)
                else:
                    exec_command = 'insmod /root/{}vf.ko'.format(target_nic_driver_name)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.error(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                else:
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

                exec_command = f'{scripts_constants.SCGBECLI64} -vv'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.error(f'command:{exec_command} 执行失败')
                else:
                    log.info(f'command:{exec_command} 执行成功')

                exec_command = f'{scripts_constants.SCGBECLI64} show'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.error(f'command:{exec_command} 执行失败')
                else:
                    log.info(f'command:{exec_command} 执行成功')

                if upgrade_rdma:
                    exec_command = 'modprobe ib_core && modprobe ib_uverbs'
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    if rtn_code != RtnStatusEnum.SUCCESS.value:
                        log.error(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                    else:
                        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

                    if cls.frame_run_dict['config_dict'].get(
                            constants.ENV_TEST_OBJECT) in [constants.ENV_RUN_MODE_WITH_SRC,
                                                           constants.ENV_RUN_MODE_WITH_RPM,
                                                           constants.ENV_RUN_MODE_WITH_SRPM,
                                                           constants.ENV_RUN_MODE_WITH_KMOD_SRPM]:
                        exec_command = 'modprobe {}rdma'.format(target_nic_driver_name)
                    else:
                        exec_command = 'insmod /root/{}rdma.ko resource_profile=1 fragment_count_limit=13'.format(target_nic_driver_name)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    if rtn_code != RtnStatusEnum.SUCCESS.value:
                        log.error(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                    else:
                        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
            else:
                log.info(f"非{cls.nicg}，或升级包路径未填写！")
                return False
        log.info(f"可能未升级成功！请检查环境")
        return False

    @classmethod
    def make_compatible_versions_test_list(cls, target_pkgs_list, vc_mode, compatible_versions_test_file,
                                           nic_vc_new_packages_path, divide_num, divide_index,
                                           target_execute_address, target_host_ip, target_nic_model) -> None:
        """
        author:      junfeng.he
        date:        2024-06-12 15:34:55
        description: 根据版本和模式生成测试清单
        """
        product_name = f"{cls.nicg}"
        table_header = ["path", "cli", "pf", "vf", "rdma", "dpdk", "ddp", "fw", "uboot", "nvdata", "userconfig", "optionrom",
                        "total", "pass", "skip", "fail", "except", "pass_rate"]
        table_data = []

        need_check_md5_item_list = ['uboot', 'nvdata', 'userconfig', 'optionrom']

        md5_dict = {}
        # driver：pf+vf
        # fw-all: fw+uboot+nvdata+userconfig+optionrom
        if vc_mode in ['cli', 'driver', 'fw-all', 'fw', "pf", "vf", "rdma", "dpdk", "ddp"]:
            pass
        elif vc_mode in need_check_md5_item_list:
            # 计算不加头组件的MD5，用于后续是否需要重复测试依据
            test_version = "release"
            for ver_main in target_pkgs_list:
                version_main = re.findall(r"(\d+\.\d+\.\d+\.\d+)", ver_main)[0]
                item_dict = {}
                for index, item in enumerate([f"bootloader_{product_name}_fw_asic.bin", "nvdata.bin",
                                              "userDefault.bin", f"header_{product_name}_oprom.bin"]):
                    item_path = ver_main + f"/debuginfo/{product_name}_fw_asic/{test_version}/" + item
                    if target_nic_model == "windows":
                        exec_command = "Get-FileHash -Path {} -Algorithm MD5|Select-Object Hash|fl".format(item_path)
                    else:
                        exec_command = "md5sum {}".format(item_path)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address,
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    if target_nic_model == "windows":
                        item_dict[need_check_md5_item_list[index]] = rtn_outputs
                    else:
                        item_dict[need_check_md5_item_list[index]] = rtn_outputs.strip().split(":")[-1].strip()
                    md5_dict[version_main] = item_dict

        # 根据测试模式确定全枚举模块
        for ver_main in target_pkgs_list:
            version_main = re.findall(r"(\d+\.\d+\.\d+\.\d+)", ver_main)[0]
            for ver_sub in target_pkgs_list:
                version_sub = re.findall(r"(\d+\.\d+\.\d+\.\d+)", ver_sub)[0]
                if version_main != version_sub:
                    if vc_mode in need_check_md5_item_list:
                        if md5_dict[version_main][vc_mode] == md5_dict[version_sub][vc_mode]:
                            log.info(f"vc_mode:{vc_mode},version_main:{version_main}"
                                     f",version_sub:{version_sub},md5相同,无需测试")
                            continue
                    pkgs_name = nic_vc_new_packages_path + "/rebuild_pkg_vc_mode_{}_main_{}_sub_{}.tar.gz". \
                        format(vc_mode, version_main, version_sub)
                    if vc_mode == "cli":
                        data = [pkgs_name, version_main, version_sub, version_sub, version_sub, version_sub, version_sub,
                                version_sub, version_sub, version_sub, version_sub, version_sub,
                                "0", "0", "0", "0", "0", "0%"]
                    elif vc_mode == "driver":
                        data = [pkgs_name, version_main, version_main, version_main, version_main, version_main, version_main,
                                version_sub, version_sub, version_sub, version_sub, version_sub,
                                "0", "0", "0", "0", "0", "0%"]
                    elif vc_mode == "pf":
                        # pf,rdma,ddp
                        data = [pkgs_name, version_sub, version_main, version_sub, version_main, version_sub, version_main,
                                version_sub, version_sub, version_sub, version_sub, version_sub,
                                "0", "0", "0", "0", "0", "0%"]
                    elif vc_mode == "vf":
                        data = [pkgs_name, version_sub, version_sub, version_main, version_sub, version_sub, version_sub,
                                version_sub, version_sub, version_sub, version_sub, version_sub,
                                "0", "0", "0", "0", "0", "0%"]
                    elif vc_mode == "rdma":
                        # pf,vf,rdma,ddp
                        data = [pkgs_name, version_sub, version_main, version_main, version_main, version_sub, version_main,
                                version_sub, version_sub, version_sub, version_sub, version_sub,
                                "0", "0", "0", "0", "0", "0%"]
                    elif vc_mode == "dpdk":
                        data = [pkgs_name, version_sub, version_sub, version_sub, version_sub, version_main, version_sub,
                                version_sub, version_sub, version_sub, version_sub, version_sub,
                                "0", "0", "0", "0", "0", "0%"]
                    elif vc_mode == "ddp":
                        data = [pkgs_name, version_sub, version_sub, version_sub, version_sub, version_sub, version_main,
                                version_sub, version_sub, version_sub, version_sub, version_sub,
                                "0", "0", "0", "0", "0", "0%"]
                    elif vc_mode == "fw-all":
                        data = [pkgs_name, version_sub, version_sub, version_sub, version_sub, version_sub, version_sub,
                                version_main, version_main, version_main, version_main, version_main,
                                "0", "0", "0", "0", "0", "0%"]
                    elif vc_mode == "fw":
                        data = [pkgs_name, version_sub, version_sub, version_sub, version_sub, version_sub, version_sub,
                                version_main, version_sub, version_sub, version_sub, version_sub,
                                "0", "0", "0", "0", "0", "0%"]
                    elif vc_mode == "uboot":
                        data = [pkgs_name, version_sub, version_sub, version_sub, version_sub, version_sub, version_sub,
                                version_sub, version_main, version_sub, version_sub, version_sub,
                                "0", "0", "0", "0", "0", "0%"]
                    elif vc_mode == "nvdata":
                        data = [pkgs_name, version_sub, version_sub, version_sub, version_sub, version_sub, version_sub,
                                version_sub, version_sub, version_main, version_sub, version_sub,
                                "0", "0", "0", "0", "0", "0%"]
                    elif vc_mode == "userconfig":
                        data = [pkgs_name, version_sub, version_sub, version_sub, version_sub, version_sub, version_sub,
                                version_sub, version_sub, version_sub, version_main, version_sub,
                                "0", "0", "0", "0", "0", "0%"]
                    elif vc_mode == "optionrom":
                        data = [pkgs_name, version_sub, version_sub, version_sub, version_sub, version_sub, version_sub,
                                version_sub, version_sub, version_sub, version_sub, version_main,
                                "0", "0", "0", "0", "0", "0%"]
                    else:
                        data = [pkgs_name, version_main, version_sub, version_main, version_sub, version_main, version_main,
                                version_sub, version_sub, version_sub, version_sub, version_sub,
                                "0", "0", "0", "0", "0", "0%"]
                    table_data.append(data)
        log.info("vc_test> 生成版本组合清单")
        if divide_num > 1:
            log.info("vc_test> table_data:\n{}".format(table_data))
            log.info("切割成{}份，取第{}份".format(divide_num, divide_index + 1))
            total_part = (len(table_data) // divide_num)
            table_data_part = []
            for i in range(total_part * divide_index, total_part * (divide_index + 1)):
                if i < len(table_data):
                    table_data_part.append(table_data[i])
            table_data = table_data_part
        FileOperation.write_csv_file(compatible_versions_test_file, table_header, table_data)
        log.info("vc_test> table_header:\n{}".format(table_header))
        log.info("vc_test> table_data:\n{}".format(table_data))

    @classmethod
    def make_compatible_versions_pkgs(cls, local_versions_list, compatible_versions_test_file, nic_vc_packages_path,
                                      nic_vc_new_packages_path, vc_mode,
                                      target_execute_address, target_host_ip, target_nic_model) -> None:
        """
        author:      junfeng.he
        date:        2024-06-12 15:34:55
        description: 根据测试清单中的版本组合重新组包
        """
        product_name = f"{cls.nicg}"
        infos = FileOperation.read_csv_file(compatible_versions_test_file)
        log.info("vc_test> local_versions_list:{}".format(local_versions_list))
        log.info("vc_test> nic_vc_packages_path:{}".format(nic_vc_packages_path))
        log.info("vc_test> nic_vc_new_packages_path:{}".format(nic_vc_new_packages_path))
        log.info("vc_test> vc_mode:{}, infos:{}".format(vc_mode, infos))
        if target_nic_model == "windows":
            exec_command = "Remove-Item -Path {} -Recurse -Force;" \
                           "New-Item -ItemType Directory -Path {} -Force" \
                .format(nic_vc_new_packages_path, nic_vc_new_packages_path)
        else:
            exec_command = "rm -rf {};mkdir -p {}".format(nic_vc_new_packages_path, nic_vc_new_packages_path)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        for info in infos:
            if "tar.gz" not in info[0]:
                continue

            # table_header = ["path", "cli", "pf", "vf", "rdma", "dpdk", "ddp", "fw", "uboot", "nvdata", "userconfig", "optionrom",
            #                 "total", "pass", "skip", "fail", "except", "pass_rate"]
            cli_target_ver = info[1]
            pf_target_ver = info[2]
            vf_target_ver = info[3]
            rdma_target_ver = info[4]
            dpdk_target_ver = info[5]
            ddp_target_ver = info[6]
            fw_target_ver = info[7]
            uboot_target_ver = info[8]
            nvdata_target_ver = info[9]
            userconfigtarget_ver = info[10]
            optionrom_target_ver = info[11]
            # 使用main包做base，替換sub组件
            if target_nic_model == "windows":
                exec_command = "Remove-Item -Path {}/temp -Recurse -Force;" \
                               "New-Item -ItemType Directory -Path {}/temp -Force" \
                    .format(nic_vc_new_packages_path, nic_vc_new_packages_path)
            else:
                exec_command = "rm -rf {}/temp;mkdir -p {}/temp; rm -rf {}/temp_sub;mkdir -p {}/temp_sub" \
                    .format(nic_vc_new_packages_path, nic_vc_new_packages_path, nic_vc_new_packages_path, nic_vc_new_packages_path)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=target_execute_address,
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
            base_tar = None
            target_folder_path = None
            target_file_name = None
            sub_base_tar = None
            sub_target_folder_path = None
            sub_target_file_name = None
            # 判断当前base包
            verinfos = re.findall(r"(\d+\.\d+\.\d+\.\d+)", info[0])
            main_ver, sub_ver = verinfos[0], verinfos[1]
            for pkg_path in local_versions_list:
                if main_ver in pkg_path:
                    target_folder_path = pkg_path.split("/")[-2]
                    target_file_name = pkg_path.split("/")[-1]
                    base_tar = pkg_path
                if sub_ver in pkg_path:
                    sub_target_folder_path = pkg_path.split("/")[-2]
                    sub_target_file_name = pkg_path.split("/")[-1]
                    sub_base_tar = pkg_path
            if not target_folder_path:
                log.info("vc_test> 未获取到测试模块的对应version_main包路径，无法继续")
                exit(1)
            log.info(f"==>base_tar:{base_tar}, sub_base_tar:{sub_base_tar}")
            path_mark = re.findall(r"(\d+\.\d+\.\d+\.\d+)", base_tar)[-1]
            target_folder_path = nic_vc_packages_path + "/" + target_folder_path
            log.info("vc_test> 将main基础包解压到temp")
            exec_command = "tar -zxvf {} -C {}/temp".format(base_tar, nic_vc_new_packages_path)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=target_execute_address,
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                print_outputs=False
            )
            log.info("vc_test> 将sub基础包解压到temp")
            exec_command = "tar -zxvf {} -C {}/temp_sub".format(sub_base_tar, nic_vc_new_packages_path)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=target_execute_address,
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                print_outputs=False
            )
            # 需替换 version_sub中组件
            if cli_target_ver not in main_ver:
                # cli相关
                log.info("vc_test> 替换cli相关组件")
                version_sub = info[1]
                exec_command = "rm -rf {}/temp/debuginfo/{}_cli;" \
                               "/bin/cp -r {}/temp_sub/debuginfo/{}_cli {}/temp/debuginfo/". \
                    format(nic_vc_new_packages_path, product_name, nic_vc_new_packages_path,
                           product_name, nic_vc_new_packages_path)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address,
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                for folder in ["products", "technical_support"]:
                    exec_command = "rm -rf {}/temp/{}/Tools;/bin/cp -r {}/temp_sub/{}/Tools {}/temp/{}/". \
                        format(nic_vc_new_packages_path, folder,
                               nic_vc_new_packages_path,
                               folder, nic_vc_new_packages_path, folder)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address,
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            if rdma_target_ver not in main_ver:
                # 驱动相关
                log.info("vc_test> 替换rdma驱动相关组件")
                exec_command = "rm -rf {}/temp/products/Src/Driver/*rdma*;/bin/cp -r {}/temp_sub/products/Src/Driver/*rdma* {}/temp/products/Src/Driver/". \
                    format(nic_vc_new_packages_path, nic_vc_new_packages_path,
                           nic_vc_new_packages_path)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address,
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )

                # 版本包中的rdma驱动目录 debuginfo/Drivers/{cpu_arch}/Linux/{os_version}/RDMA
                exec_command = "rm -rf {}/temp/debuginfo/Drivers/*;/bin/cp -r {}/temp_sub/debuginfo/Drivers/* {}/temp/debuginfo/Driver/". \
                    format(nic_vc_new_packages_path, nic_vc_new_packages_path,
                           nic_vc_new_packages_path)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address,
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )

            if dpdk_target_ver not in main_ver:
                # 驱动相关
                log.info("vc_test> 替换dpdk驱动相关组件")
                version_sub = info[2]
                for folder in ["debuginfo", "products/Src"]:
                    exec_command = "rm -rf {}/temp/{}/DPDK;/bin/cp -r {}/temp_sub/{}/DPDK {}/temp/{}/". \
                        format(nic_vc_new_packages_path, folder, target_folder_path.replace(path_mark, version_sub),
                               folder, nic_vc_new_packages_path, folder)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address,
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    exec_command = "rm -rf {}/temp/{}/Drivers;/bin/cp -r {}/temp_sub/{}/Drivers {}/temp/{}/". \
                        format(nic_vc_new_packages_path, folder, nic_vc_new_packages_path,
                               folder, nic_vc_new_packages_path, folder)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address,
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                exec_command = "rm -rf {}/temp/products/Src/DPDK;/bin/cp -r {}/temp_sub/products/Src/DPDK {}/temp/products/Src/". \
                    format(nic_vc_new_packages_path, nic_vc_new_packages_path,
                           nic_vc_new_packages_path)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address,
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
            if pf_target_ver not in main_ver:
                # 驱动相关
                log.info("vc_test> 替换pf驱动相关组件")
                exec_command = ("rm -rf {}/temp/products/Src/Driver/{}-{}*;"
                                "/bin/cp -r {}/temp_sub/products/Src/Driver/{}-{}* {}/temp/products/Src/Driver/"). \
                    format(nic_vc_new_packages_path, product_name, main_ver, nic_vc_new_packages_path, product_name, sub_ver,
                           nic_vc_new_packages_path)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address,
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            if vf_target_ver not in main_ver:
                # 驱动相关
                log.info("vc_test> 替换vf驱动相关组件")
                exec_command = ("rm -rf {}/temp/products/Src/Driver/{}vf-{}*;"
                                "/bin/cp -r {}/temp_sub/products/Src/Driver/{}vf-{}* {}/temp/products/Src/Driver/"). \
                    format(nic_vc_new_packages_path, product_name, main_ver, nic_vc_new_packages_path, product_name, sub_ver,
                           nic_vc_new_packages_path)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address,
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            if ddp_target_ver not in main_ver:
                # 驱动相关
                log.info("vc_test> 替换ddp相关组件")
                for vtype in ["debug", "release"]:
                    exec_command = (f"find {nic_vc_new_packages_path}/temp -name '{cls.nicg}.cfg'" + " | xargs -I {} cp -f" +
                                    f" {nic_vc_new_packages_path}/temp_sub/debuginfo/sxe2_fw_asic/{vtype}/ddp/{cls.nicg}.cfg" + " {}")
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address,
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            if fw_target_ver not in main_ver:
                # 驱动相关
                log.info("vc_test> 替换fw相关组件")
                version_sub = info[2]
                exec_command = ("rm -rf {}/temp/products/Firmware/Standard-Products/1260-X;"
                                "/bin/cp -r {}/temp_sub/products/Firmware/Standard-Products/1260-X {}/temp/products/Firmware/Standard-Products/"). \
                    format(nic_vc_new_packages_path, nic_vc_new_packages_path,
                           nic_vc_new_packages_path)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address,
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            # 打包
            log.info("vc_test> 打包")
            exec_command = "cd {};tar -zcvf {} -C ./temp .". \
                format(nic_vc_new_packages_path, info[0].split('/')[-1])
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=target_execute_address,
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                print_outputs=False
            )

    @classmethod
    def dpdk_app_uniform_name(cls, dpdk_psth, target_host_ip, target_execute_address, target_nic_model) -> None:
        """
        author:      junfeng.he
        date:        2024-03-02 15:34:55
        description: 防火墙策略根据jenkins选项更新
        :return:     None
        """
        if target_nic_model == 'windows':
            cp_head = 'cp'
        else:
            cp_head = '/bin/cp'
        exec_command = "{} {}/testpmd {}/dpdk-testpmd".format(cp_head, dpdk_psth, dpdk_psth)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        exec_command = "{} {}/ethtool {}/dpdk-ethtool".format(cp_head, dpdk_psth, dpdk_psth)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        exec_command = "{} {}/l3fwd {}/dpdk-l3fwd".format(cp_head, dpdk_psth, dpdk_psth)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        exec_command = "{} {}/ptpclient {}/dpdk-ptpclient".format(cp_head, dpdk_psth, dpdk_psth)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        exec_command = "{} {}/dpdk-procinfo {}/dpdk-proc-info".format(cp_head, dpdk_psth, dpdk_psth)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

    @classmethod
    def build_ko_and_update(cls, os_version, target_host_ip, target_execute_address, make_build_para) -> bool:
        """
        author:      junfeng.he
        date:        2024-03-02 15:34:55
        description: 防火墙策略根据jenkins选项更新
        :return:     None
        """
        product_name = f"{cls.nicg}"
        if "ubuntu" in os_version:
            log.info("==>ubuntu 需安装linux-headers-`uname -r`才支持源码包编译")
            exec_command = "apt-get install linux-headers-`uname -r`"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=target_execute_address,
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

        root_path = tj_constants.LINUX_FILE_PATH_ROOT + "publish_version/"
        sxe_pkg, _, _ = CommonOperation.get_rpm_package(
            root_path, False, 0, target_execute_address, False,
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
            test_port=cls.test_port, src_type=1)

        exec_command = "tar -zxvf {} -C {}".format(sxe_pkg, sxe_pkg.split(f"{product_name}-")[0])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

        exec_command = "cd {};make {}".format(sxe_pkg.replace(".tar.gz", ""), make_build_para)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

        exec_command = "ls {}".format(sxe_pkg.replace(".tar.gz", ""))
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        if f"{product_name}.ko" in rtn_outputs:
            exec_command = "/bin/cp {}/{}.ko /root/".format(sxe_pkg.replace(".tar.gz", ""), product_name)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=target_execute_address,
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        else:
            log.error(f"==>未成功编译出{product_name}.ko, 此次测试将使用包中自带的{product_name}.ko,{product_name}vf.ko")
            return False

        sxevf_pkg, _, _ = CommonOperation.get_rpm_package(
            root_path, False, 1, target_execute_address, False,
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
            test_port=cls.test_port, src_type=1)
        exec_command = "tar -zxvf {} -C {}".format(sxevf_pkg, sxevf_pkg.split(f"{product_name}vf-")[0])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

        exec_command = "cd {}; make {}".format(sxevf_pkg.replace(".tar.gz", ""), make_build_para)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

        exec_command = "ls {}".format(sxevf_pkg.replace(".tar.gz", ""))
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        if f"{product_name}vf.ko" in rtn_outputs:
            exec_command = "/bin/cp {}/{}vf.ko /root/".format(sxevf_pkg.replace(".tar.gz", ""), product_name)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=target_execute_address,
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        else:
            log.error(f"==>未成功编译出{product_name}vf.ko,此次测试将使用包中自带的{product_name}.ko,{product_name}vf.ko")
            return False
        """
        rdma_pkg, _, _ = CommonOperation.get_rpm_package(
            root_path, False, 2, target_execute_address, False,
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
            test_port=cls.test_port, src_type=1)
        exec_command = "tar -zxvf {} -C {}".format(rdma_pkg, sxevf_pkg.split(f"{product_name}_rdma-")[0])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

        exec_command = "cd {}; make {}".format(rdma_pkg.replace(".tar.gz", ""), make_build_para)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

        exec_command = "ls {}".format(rdma_pkg.replace(".tar.gz", ""))
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        if f"{product_name}_rdma.ko" in rtn_outputs:
            exec_command = "/bin/cp {}/{}_rdma.ko /root/".format(rdma_pkg.replace(".tar.gz", ""), product_name)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=target_execute_address,
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        else:
            log.error(
                f"==>未成功编译出{product_name}_rdma.ko,此次测试将使用包中自带的{product_name}_rdma.ko")
            return False
        """
        return True

    @classmethod
    def update_cli(cls, root_path, nic_package_path, current_version, architecture, suffix,
                   test_version, test_version_short, target_nic_model, target_host_ip, target_driver_name,
                   target_execute_address, root) -> None:
        """
        author:      junfeng.he
        date:        2024-02-19 15:34:55
        description: 更新cli
        :return:     None
        """
        log.warning(f'更新cli工具')
        exec_command = f"ls {nic_package_path}/debuginfo/{target_driver_name}_cli/debug/{architecture}/"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command,
            cmd_execute_address=target_execute_address, ssh_username=f'{root}',
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(
                tj_constants.EVN_CLIENT_NIC_MODEL))
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        cli_versions = re.findall(r"(\d+\.\d+\.\d+\.\d+)", rtn_outputs.split("\n")[0])
        if cli_versions:
            cli_version = cli_versions[0]
        else:
            cli_version = current_version

        # dest_cli_path_3b008 = os.path.join(
        #     nic_package_path, 'debuginfo/{}_cli/{}/{}/{}cli{}_{}_{}{}'.format(
        #         target_driver_name, test_version, architecture, target_driver_name,
        #         test_version_short, current_version, architecture, suffix))
        # todo 当前cli测试必须使用debug版本
        dest_cli_path_3b008 = os.path.join(
            nic_package_path, 'debuginfo/{}_cli/debug/{}/{}clid_{}_{}{}'.format(
                target_driver_name, architecture, target_driver_name, cli_version, architecture, suffix))
        dest_cli_path_history_version = [dest_cli_path_3b008]

        for dest_cli_path in dest_cli_path_history_version:
            if target_nic_model == 'windows':
                exec_command = f"Copy-Item -Path {dest_cli_path} -Destination " \
                               f"{root_path}{target_driver_name}cli.exe -Force -Recurse"
            else:
                exec_command = f"/bin/cp {dest_cli_path} /usr/bin/{scripts_constants.SCGBECLI64};/bin/cp {dest_cli_path} /usr/bin/cli"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command,
                cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(
                    tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(
                    tj_constants.EVN_CLIENT_NIC_MODEL))
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.error(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

    @classmethod
    def uninstall_driver_rpm_pkg(cls, os_version, target_host_ip, target_execute_address) -> None:
        """
        author:      junfeng.he
        date:        2023-08-08 15:34:55
        description: 防火墙策略根据jenkins选项更新
        :return:     None
        """
        product_name = f"{cls.nicg}"
        if "ubuntu" in os_version:
            exec_command = f'dpkg -r {product_name}'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=target_execute_address,
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            exec_command = f'dpkg -r {product_name}vf'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=target_execute_address,
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            exec_command = f'dpkg -r {product_name}-dkms'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=target_execute_address,
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            exec_command = f'dpkg -r {product_name}vf-dkms'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=target_execute_address,
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        else:
            exec_command = f"rpm -qa | grep {product_name}"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=target_execute_address,
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
            rpm_pkgs = rtn_outputs.split("\n")
            for rpm_pkg in rpm_pkgs:
                if f"{product_name}" in rpm_pkg:
                    exec_command = "rpm -e {}".format(rpm_pkg)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address,
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

    @classmethod
    def install_driver_rpm_pkg(cls, type, os_version, target_host_ip, target_execute_address,
                               architecture: str = "x86_64") -> None:
        """
        author:      junfeng.he
        date:        2023-08-08 15:34:55
        description: 防火墙策略根据jenkins选项更新
        :return:     None
        """
        root_path = tj_constants.LINUX_FILE_PATH_ROOT + "publish_version/"

        if type == constants.ENV_RUN_MODE_WITH_SRC_KO:
            src_type = 1
        elif type == constants.ENV_RUN_MODE_WITH_SRPM:
            src_type = 2
        elif type == constants.ENV_RUN_MODE_WITH_KMOD_SRPM:
            src_type = 3
        else:
            src_type = 0

        dkms_test = True if type == constants.ENV_RUN_MODE_WITH_SRC else False
        sxe_pkg, _, _ = CommonOperation.get_rpm_package(
            root_path, dkms_test, 0, target_execute_address, False,
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
            test_port=cls.test_port, src_type=src_type, architecture=architecture)
        if "ubuntu" in os_version:
            exec_command = "dpkg -i {}".format(sxe_pkg)
        else:
            exec_command = "rpm -ivh {}".format(sxe_pkg)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

        sxevf_pkg, _, _ = CommonOperation.get_rpm_package(
            root_path, dkms_test, 1, target_execute_address, False,
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
            test_port=cls.test_port, src_type=src_type, architecture=architecture)
        if "ubuntu" in os_version:
            exec_command = "dpkg -i {}".format(sxevf_pkg)
        else:
            exec_command = "rpm -ivh {}".format(sxevf_pkg)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

        if "ubuntu" in os_version:
            exec_command = f"dpkg -l | grep ii | grep {sxevf_pkg}"
        else:
            exec_command = f"rpm -qa | grep {sxevf_pkg}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address,
            ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

    @classmethod
    def __firewalld_policy_update(cls) -> None:
        """
        author:      junfeng.he
        date:        2023-08-08 15:34:55
        description: 防火墙策略根据jenkins选项更新
        :return:     None
        """
        firewalld_value = cls.frame_run_dict['config_dict'].get(constants.ENV_FIREWALLD)
        target_server_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        target_client_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        for target_info in [[target_server_ip, host_os_server, CmdExecuteAdressEnum.SERVER.value],
                            [target_client_ip, host_os_client, CmdExecuteAdressEnum.CLIENT.value]]:
            target_host_ip = target_info[0]
            target_host_model = target_info[1]
            target_execute_address = target_info[2]

            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and target_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue

            if firewalld_value == "on":
                if target_host_model == 'windows':
                    exec_command = "Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled True"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username='Administrator',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    exec_credential = \
                        '$credential = Import-Clixml -Path "C:\\Users\\Administrator\\sxetest\\credential.xml"'
                    code, outputs, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_credential, cmd_execute_address=target_execute_address, ssh_username='Administrator',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f"command:{exec_credential},\n outputs:{outputs}, \nerror:{err}")
                    continue
                elif target_host_model == 'ubuntu':
                    exec_command = "systemctl enable ufw"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username='root',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    exec_command = "systemctl start ufw"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username='root',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                else:
                    cls.iptables_setting()
                #     exec_command = "systemctl enable firewalld"
                #     rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                #         cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username='root',
                #         ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                #         host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                #         host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                #     )
                #     log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                #     exec_command = f'systemctl start firewalld'
                #     rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                #         cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username='root',
                #         ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                #         host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                #         host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                #     )
                #     log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                # exec_command = f'sh /root/iptables_set.sh'
                # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                #     cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username='root',
                #     ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                #     host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                #     host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                # )
                # log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                # # 重新启动刷新防火墙策略
                # exec_command = "cat /etc/rc.d/rc.local"
                # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                #     cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username='root',
                #     ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                #     host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                #     host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                # )
                # log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                # if 'sh /root/iptables_set.sh' not in rtn_outputs and '# sh /root/iptables_set.sh' in rtn_outputs:
                #     rtn_outputs = rtn_outputs.replace("# sh /root/iptables_set.sh", "sh /root/iptables_set.sh")
                #     FileOperation.write_local_file(scripts_constants.NIC_SCRIPT_PATH + "/rc.local", rtn_outputs)
                #     FileOperation.sftp_upload_file(
                #         scripts_constants.NIC_SCRIPT_PATH + "/rc.local", "/etc/rc.d/rc.local", ip=target_host_ip)
                #     exec_command = "chmod +x /etc/rc.d/rc.local"
                #     rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                #         cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username='root',
                #         ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                #         host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                #         host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                #     )
                #     log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
            elif firewalld_value == "off":
                if target_host_model == 'windows':
                    exec_command = "Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled False"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username='Administrator',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    continue
                elif target_host_model == 'ubuntu':
                    exec_command = f'systemctl stop ufw'
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username='root',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    exec_command = "systemctl disable ufw"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username='root',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                else:
                    exec_command = f'systemctl stop firewalld'
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username='root',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                    exec_command = "systemctl disable firewalld"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username='root',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                exec_command = f'iptables -F'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username='root',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )

                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd="iptables-save > /etc/sysconfig/iptables",
                    cmd_execute_address=target_execute_address, ssh_username='root',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                exec_command = f'iptables -L'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username='root',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                # 去除启动刷新防火墙策略
                exec_command = "cat /etc/rc.d/rc.local"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username='root',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                if '# sh /root/iptables_set.sh' not in rtn_outputs and 'sh /root/iptables_set.sh' in rtn_outputs:
                    rtn_outputs = rtn_outputs.replace("sh /root/iptables_set.sh", "# sh /root/iptables_set.sh")
                    FileOperation.write_local_file(scripts_constants.NIC_SCRIPT_PATH + "/rc.local", rtn_outputs)
                    FileOperation.sftp_upload_file(
                        scripts_constants.NIC_SCRIPT_PATH + "/rc.local", "/etc/rc.d/rc.local", ip=target_host_ip)
                    exec_command = "chmod +x /etc/rc.d/rc.local"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username='root',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
            else:
                log.info("选择 ignore，不进行防火墙策略更新")
                pass

    @classmethod
    def __sagitta_simu_check_and_recover(cls, force: bool = False) -> None:
        """
        author:      junfeng.he
        date:        2023-08-08 15:34:55
        description: 将工具脚本拷贝到测试机中，包含server和client
        :return:     None
        """
        log.info("检查当前模拟平台节点状态")
        physical_machine_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_SERVER_NIC_IP)
        target_server_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        target_client_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
        root = "root"

        exec_command = f"cd {tj_constants.SIMU_ROOT_PATH};python3 {tj_constants.SIMU_SCRIPT} --check | grep ':'"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, ssh_username=f'{root}',
            ssh_ip=physical_machine_ip, ssh_port=str(cls.test_port))

        items = rtn_outputs.split("\n")
        need_recover = False
        node_id = ""
        for item in items:
            if target_server_ip + " " in item:
                node_id = item.split(":")[0].replace("server", "")
                if "offline" in item:
                    need_recover = True
                    break
            if target_client_ip + " " in item and "offline" in item:
                need_recover = True
                break

        if not node_id:
            log.error("未获取到node_id,请检查环境配置，退出测试！！")
            exit(1)

        log.info("node_id:{}".format(node_id))

        if not need_recover:
            log.info("当前所有qemu都是online，无需执行恢复动作。")
            return

        iretry = 3
        online_flag = False
        while iretry:
            log.info("iretry:{}".format(iretry))
            if iretry == 1:
                log.warning("最后重试，先clear再restore")
                force = True
            iretry -= 1
            if force:
                need_recover = True
                exec_command = f"export LD_LIBRARY_PATH={tj_constants.SIMU_ROOT_PATH};" \
                               f"cd {tj_constants.SIMU_ROOT_PATH};" \
                               f"python3 {tj_constants.SIMU_SCRIPT} --clear {node_id}"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, ssh_username=f'{root}',
                    ssh_ip=physical_machine_ip, ssh_port=str(cls.test_port))
                time.sleep(5)

            if need_recover:
                exec_command = f"export LD_LIBRARY_PATH={tj_constants.SIMU_ROOT_PATH};" \
                               f"cd {tj_constants.SIMU_ROOT_PATH};" \
                               f"python3 {tj_constants.SIMU_SCRIPT} --restore {node_id}"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, ssh_username=f'{root}',
                    ssh_ip=physical_machine_ip, ssh_port=str(cls.test_port))

            iiretry = 20
            while iiretry:
                time.sleep(3)
                iiretry -= 1
                exec_command = f"cd {tj_constants.SIMU_ROOT_PATH};python3 {tj_constants.SIMU_SCRIPT} --check {node_id}"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, ssh_username=f'{root}',
                    ssh_ip=physical_machine_ip, ssh_port=str(cls.test_port))
                if "offline" in rtn_outputs:
                    continue
                elif "online" not in rtn_outputs:
                    continue
                else:
                    online_flag = True
                    break
            log.info("online_flag:{}".format(online_flag))
            if online_flag:
                break

        if not online_flag:
            log.error("模拟平台无法正常启动，请检查环境配置，退出测试！！")
            exit(1)

    @classmethod
    def __sagitta_env_tools_update(cls) -> None:
        """
        author:      junfeng.he
        date:        2023-08-08 15:34:55
        description: 将工具脚本拷贝到测试机中，包含server和client
        :return:     None
        """
        if cls.server_nic_model == 'windows':
            env_config_path = tj_constants.WINDOWS_FILE_PATH_ROOT
            root = "Administrator"
            bin_path = env_config_path
        else:
            env_config_path = tj_constants.LINUX_FILE_PATH_ROOT
            root = "root"
            bin_path = "/usr/bin/"
        log.warning("==> 更新环境配置信息文件env_config.ini：")
        target_host_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        for nic_paths in [[scripts_constants.NIC_CONFIG_PATH.replace("nic100/", "nic/"),
                           scripts_constants.NIC_CONFIG_BK_PATH.replace("nic100/", "nic/")],
                          [scripts_constants.NIC_CONFIG_PATH, scripts_constants.NIC_CONFIG_BK_PATH]]:
            nic_path = nic_paths[0]
            nic_bk_path = nic_paths[1]
            exec_command = \
                f'scp -P {cls.test_port} {root}@{target_host_ip}:{env_config_path + "env_config.ini"} ' \
                f'{nic_path}'
            log.info("exec_command::::{}".format(exec_command))
            status, result = cls.getstatusoutput(exec_command)
            if status != RtnStatusEnum.SUCCESS.value:
                log.error(f'command:{exec_command}执行失败, status:{status}, result:{result}')
                log.error(f'测试环境中可能未配置文件{env_config_path + "env_config.ini"}，请检查！')
                exit(1)
            else:
                log.info(f'command:{exec_command}, status:{status}, result:{result}')
            cls.transport_configure()
            exec_command = f'/bin/cp {nic_path} {nic_bk_path}'
            status, result = cls.getstatusoutput(exec_command)
            if status != RtnStatusEnum.SUCCESS.value:
                log.error(f'command:{exec_command}执行失败, status:{status}, result:{result}')
                log.error(f'备份env_config.ini失败，请检查！')
                exit(1)
            else:
                log.info(f'command:{exec_command}, status:{status}, result:{result}')
                log.warning("update env_config.ini finish")
            CommonOperation.show_env_config(nic_path)

        # 配置再更新一版
        from importlib import reload
        reload(scripts_constants)
        # config = configparser.ConfigParser()
        # config.read(scripts_constants.NIC_CONFIG_BK_PATH)
        # cls.nicg = config['nic_driver']['server'].split(",")[0]
        cls.nicg = scripts_constants.DRV_SCGBE_PF

        # 更新虚拟机配置文件
        log.warning("==> 更新环境配置信息文件env_config_vm.ini：")
        target_host_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        exec_command = \
            f'scp -P {cls.test_port} {root}@{target_host_ip}:{env_config_path + "env_config_vm.ini"} ' \
            f'{scripts_constants.NIC_WIN_VM_CONFIG_PATH}'
        status, result = cls.getstatusoutput(exec_command)
        if status != RtnStatusEnum.SUCCESS.value:
            log.error(f'command:{exec_command}执行失败, status:{status}, result:{result}')
            log.error(f'测试环境中可能未配置文件{env_config_path + "env_config_vm.ini"}，请检查！')
        else:
            log.info(f'command:{exec_command}, status:{status}, result:{result}')

        cls.client_renix_only_flag = CommonOperation.is_renix_only()
        log.info(f'当前为仅发包仪环境：{cls.client_renix_only_flag}')

        log.warning("==> 更新环境工具脚本：")
        exec_command = "ls -l {}".format(scripts_constants.NIC_SCRIPT_PATH)
        rtn_code, result = cls.getstatusoutput(exec_command)
        log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
        target_server_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        target_client_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)

        if "pytransform" in result or "pyarmor_runtime" in result:
            exec_command = "python3 {}".format(scripts_constants.NIC_SUB_SCRIPTS_MANEGER_PATH)
            rtn_code, result = cls.getstatusoutput(exec_command)
            log.info("exec_command:{}, rtn_code:{}, result:{}".format(exec_command, rtn_code, result))
            if "subscript_manager:success" in result:
                log.info("代码已加密，子脚本刷新成功")
                # return
            else:
                log.info("代码已加密，并且刷新失败，不进行子脚本拷贝")
                for target_host_info in [[target_server_ip, CmdExecuteAdressEnum.SERVER.value],
                                         [target_client_ip, CmdExecuteAdressEnum.CLIENT.value]]:
                    target_host_ip = target_host_info[0]
                    target_execute_address = target_host_info[1]
                    vm, rpc_port = CommonOperation.get_node_info_from_path()
                    log.info("vm:{},rpc_port:{}".format(vm, rpc_port))
                    vm_path = "{}{}".format(env_config_path, vm)
                    if root == "Administrator":
                        exec_command = "New-Item -Path {} -Name {} -Type directory".format(env_config_path, vm)
                    else:
                        exec_command = 'mkdir -p {}'.format(vm_path)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                return

        for target_host_info in [[target_server_ip, CmdExecuteAdressEnum.SERVER.value],
                                 [target_client_ip, CmdExecuteAdressEnum.CLIENT.value]]:
            target_host_ip = target_host_info[0]
            target_execute_address = target_host_info[1]

            if ((cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE])
                    and target_execute_address == CmdExecuteAdressEnum.CLIENT.value):
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue

            if (target_host_ip == target_server_ip and cls.server_nic_model == 'windows') or \
                    (target_host_ip == target_client_ip and cls.client_nic_model == 'windows'):
                env_config_path = tj_constants.WINDOWS_FILE_PATH_ROOT
                root = "Administrator"
                bin_path = env_config_path
                root_path = bin_path
            else:
                env_config_path = tj_constants.LINUX_FILE_PATH_ROOT
                root = "root"
                bin_path = "/usr/bin/"
                root_path = "/root/sxetest/"
            file_content = ""
            if root == "Administrator":
                # windows环境拷贝前需要去掉linux环境变量
                file_content = FileOperation.read_local_file(scripts_constants.NIC_ESXE_PATH)
                new_file_content = file_content.replace("#!/usr/bin/python3", ""). \
                    replace("# -*- encoding=utf8 -*-", "")
                FileOperation.write_local_file(scripts_constants.NIC_ESXE_PATH, new_file_content)

            exec_command = f'scp -P {cls.test_port} {scripts_constants.NIC_ESXE_PATH} {root}@{target_host_ip}:{bin_path}'
            rtn_code, result = cls.getstatusoutput(exec_command)
            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info("拷贝失败！")
            elif root != "Administrator":
                exec_command = f'chmod 777 {bin_path}esxe.py'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
            if root == "Administrator" and file_content:
                # 文件scp过后，需要还原
                FileOperation.write_local_file(scripts_constants.NIC_ESXE_PATH, file_content)

            exec_command = f'scp -P {cls.test_port} {scripts_constants.NIC_INSTALL_SCRIPT_PATH} {root}@{target_host_ip}:{root_path}'
            rtn_code, result = cls.getstatusoutput(exec_command)
            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info("拷贝失败！")
            elif root != "Administrator":
                exec_command = f'chmod 777 {root_path}install_all_version.py'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
            if root == "Administrator" and file_content:
                # 文件scp过后，需要还原
                FileOperation.write_local_file(scripts_constants.NIC_INSTALL_SCRIPT_PATH, file_content)

            exec_command = f'scp -P {cls.test_port} {scripts_constants.NIC_DPDK_BUILD_PATH} {root}@{target_host_ip}:{root_path}'
            rtn_code, result = cls.getstatusoutput(exec_command)
            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info("拷贝失败！")
            elif root != "Administrator":
                exec_command = f'chmod 777 {root_path}scgbe_dpdk_build.sh'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            file_content = ""
            if root == "Administrator":
                # windows环境拷贝前需要去掉linux环境变量
                file_content = FileOperation.read_local_file(scripts_constants.NIC_IPERF_BT_PATH)
                new_file_content = file_content.replace("#!/usr/bin/python3", ""). \
                    replace("# -*- encoding=utf8 -*-", "")
                FileOperation.write_local_file(scripts_constants.NIC_IPERF_BT_PATH, new_file_content)

            exec_command = f'scp -P {cls.test_port} {scripts_constants.NIC_IPERF_BT_PATH} ' \
                           f'{root}@{target_host_ip}:{env_config_path}'
            rtn_code, result = cls.getstatusoutput(exec_command)
            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info("拷贝失败！")
            elif root != "Administrator":
                exec_command = f'chmod 777 {env_config_path}iperf_bt_daemon.py'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL))
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            if root == "Administrator" and file_content:
                # 文件scp过后，需要还原
                FileOperation.write_local_file(scripts_constants.NIC_IPERF_BT_PATH, file_content)

            exec_command = f'scp -P {cls.test_port} {scripts_constants.NIC_SERIAL_DAEMON_PATH} ' \
                           f'{root}@{target_host_ip}:{env_config_path}'
            rtn_code, result = cls.getstatusoutput(exec_command)
            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info("拷贝失败！")
            elif root != "Administrator":
                exec_command = f'chmod 777 {env_config_path}ps3_serial_daemon.py'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            exec_command = f'scp -P {cls.test_port} {scripts_constants.NIC_SCLI_PATH} {root}@{target_host_ip}:{bin_path}'
            rtn_code, result = cls.getstatusoutput(exec_command)
            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info("拷贝失败！")
            elif root != "Administrator":
                exec_command = f'chmod 777 {bin_path}sagitta_serial_cli.py'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            exec_command = f'scp -P {cls.test_port} {scripts_constants.NIC_MODIFY_XML_PATH} ' \
                           f'{root}@{target_host_ip}:{env_config_path}'
            rtn_code, result = cls.getstatusoutput(exec_command)
            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info("拷贝失败！")

            vm, rpc_port = CommonOperation.get_node_info_from_path()
            log.info("vm:{},rpc_port:{}".format(vm, rpc_port))
            vm_path = "{}{}".format(env_config_path, vm)
            if root == "Administrator":
                exec_command = "New-Item -Path {} -Name {} -Type directory".format(env_config_path, vm)
            else:
                exec_command = 'rm -rf {};mkdir -p {}'.format(vm_path, vm_path)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            vm, rpc_port = CommonOperation.get_node_info_from_path()
            log.info("vm:{},rpc_port:{}".format(vm, rpc_port))
            vm_path = "{}{}".format(env_config_path, vm)
            exec_command = \
                f'scp -P {cls.test_port} {scripts_constants.NIC_PACKAGE_PROCESS_PATH} ' \
                f'{root}@{target_host_ip}:{vm_path}'
            rtn_code, result = cls.getstatusoutput(exec_command)
            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info("拷贝失败！")
            elif root != "Administrator":
                exec_command = f'chmod 777 {vm_path}/win_package_process.py'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            # 拷贝前需要更新对应环境的ip地址，由于有2个环境需要
            file_content = FileOperation.read_local_file(scripts_constants.NIC_RPC_SERVER_PATH)
            new_file_content = file_content.replace("ip = socket.gethostbyname(hostname)", "ip = '{}'".
                                                    format(target_host_ip))
            new_file_content = new_file_content.replace("rpc_port = 8888", "rpc_port = {}".
                                                        format(rpc_port))
            if root == "Administrator":
                # windows环境拷贝前需要去掉linux环境变量
                new_file_content = new_file_content.replace("#!/usr/bin/python3", ""). \
                    replace("# -*- encoding=utf8 -*-", "")

            FileOperation.write_local_file(scripts_constants.NIC_RPC_SERVER_PATH, new_file_content)

            exec_command = f'scp -P {cls.test_port} {scripts_constants.NIC_RPC_SERVER_PATH} ' \
                           f'{root}@{target_host_ip}:{vm_path}/'
            rtn_code, result = cls.getstatusoutput(exec_command)
            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info("拷贝失败！")
            elif root != "Administrator":
                exec_command = f'chmod 777 {vm_path}/rpc_server.py'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
            # 文件scp过后，需要还原
            FileOperation.write_local_file(scripts_constants.NIC_RPC_SERVER_PATH, file_content)

            file_content1 = FileOperation.read_local_file(scripts_constants.NIC_RPC_CLIENT_PATH)
            new_file_content1 = file_content1. \
                replace("current_ipv4 = socket.gethostbyname(hostname)", "current_ipv4 = '{}'".
                        format(target_host_ip))
            new_file_content1 = new_file_content1.replace("server_port = 8888", "server_port = {}".format(rpc_port))
            if root == "Administrator":
                # windows环境拷贝前需要去掉linux环境变量
                new_file_content1 = new_file_content1.replace("#!/usr/bin/python3", ""). \
                    replace("# -*- encoding=utf8 -*-", "")

            FileOperation.write_local_file(scripts_constants.NIC_RPC_CLIENT_PATH, new_file_content1)

            exec_command = f'scp -P {cls.test_port} {scripts_constants.NIC_RPC_CLIENT_PATH} ' \
                           f'{root}@{target_host_ip}:{vm_path}/'
            rtn_code, result = cls.getstatusoutput(exec_command)
            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info("拷贝失败！")
            elif root != "Administrator":
                exec_command = f'chmod 777 {vm_path}/rpc_client.py'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
            # 文件scp过后，需要还原
            FileOperation.write_local_file(scripts_constants.NIC_RPC_CLIENT_PATH, file_content1)

            file_content = ""
            if root == "Administrator":
                # windows环境拷贝前需要去掉linux环境变量
                file_content = FileOperation.read_local_file(scripts_constants.NIC_SEND_PACKET_PATH)
                new_file_content = file_content.replace("#!/usr/bin/python3", ""). \
                    replace("# -*- encoding=utf8 -*-", "")
                FileOperation.write_local_file(scripts_constants.NIC_SEND_PACKET_PATH, new_file_content)

            exec_command = f'scp -P {cls.test_port} {scripts_constants.NIC_SEND_PACKET_PATH} ' \
                           f'{root}@{target_host_ip}:{vm_path}/'
            rtn_code, result = cls.getstatusoutput(exec_command)
            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info("拷贝失败！")
            elif root != "Administrator":
                exec_command = f'chmod 777 {vm_path}/send_packet.py'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            if root == "Administrator" and file_content:
                # 文件scp过后，需要还原
                FileOperation.write_local_file(scripts_constants.NIC_SEND_PACKET_PATH, file_content)

            file_content = ""
            if root == "Administrator":
                # windows环境拷贝前需要去掉linux环境变量
                file_content = FileOperation.read_local_file(scripts_constants.NIC_RECEIVE_PACKET_PATH)
                new_file_content = file_content.replace("#!/usr/bin/python3", ""). \
                    replace("# -*- encoding=utf8 -*-", "")
                FileOperation.write_local_file(scripts_constants.NIC_RECEIVE_PACKET_PATH, new_file_content)

            exec_command = f'scp -P {cls.test_port} {scripts_constants.NIC_RECEIVE_PACKET_PATH} ' \
                           f'{root}@{target_host_ip}:{vm_path}/'
            rtn_code, result = cls.getstatusoutput(exec_command)
            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info("拷贝失败！")
            elif root != "Administrator":
                exec_command = f'chmod 777 {vm_path}/receive_packet.py'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            if root == "Administrator" and file_content:
                # 文件scp过后，需要还原
                FileOperation.write_local_file(scripts_constants.NIC_RECEIVE_PACKET_PATH, file_content)

            file_content = ""
            if root == "Administrator":
                # windows环境拷贝前需要去掉linux环境变量
                file_content = FileOperation.read_local_file(scripts_constants.NIC_SEND_UDP_PACKET_PATH)
                new_file_content = file_content.replace("#!/usr/bin/python3", ""). \
                    replace("# -*- encoding=utf8 -*-", "")
                FileOperation.write_local_file(scripts_constants.NIC_SEND_UDP_PACKET_PATH, new_file_content)

            exec_command = f'scp -P {cls.test_port} {scripts_constants.NIC_SEND_UDP_PACKET_PATH} ' \
                           f'{root}@{target_host_ip}:{vm_path}/'
            rtn_code, result = cls.getstatusoutput(exec_command)
            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info("拷贝失败！")
            elif root != "Administrator":
                exec_command = f'chmod 777 {vm_path}/send_udp_packet.py'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                    ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            if root == "Administrator" and file_content:
                # 文件scp过后，需要还原
                FileOperation.write_local_file(scripts_constants.NIC_SEND_UDP_PACKET_PATH, file_content)

            # scp ipvbs、ipvbs_s、ipvbs_execute_cmd_in_local到测试机
            for ipvbs_file in [scripts_constants.NIC_IPVBS_PATH, scripts_constants.NIC_IPVBS_S_PATH, scripts_constants.NIC_IPVBS_LOCAL_PATH]:
                exec_command = f'scp -P {cls.test_port} {ipvbs_file} {root}@{target_host_ip}:{vm_path}/'
                rtn_code, result = cls.getstatusoutput(exec_command)
                log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.info("拷贝失败！")
                elif root != "Administrator":
                    exec_command = f'chmod 777 {vm_path}/{os.path.basename(ipvbs_file)}'
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

            # scp set_irq_affinity到测试机
            for tool_file in [scripts_constants.NIC_SET_IRQ_AFFINITY_PATH]:
                exec_command = f'scp -P {cls.test_port} {tool_file} {root}@{target_host_ip}:{root_path}'
                rtn_code, result = cls.getstatusoutput(exec_command)
                log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.info("拷贝失败！")
                elif root != "Administrator":
                    exec_command = f'chmod 777 {root_path}{os.path.basename(tool_file)}'
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
            # 传容量检查和处理脚本
            for tool_file in [scripts_constants.NIC_CHECK_AND_FREE_DISK]:
                exec_command = f'scp -P {cls.test_port} {tool_file} {root}@{target_host_ip}:/root/'
                rtn_code, result = cls.getstatusoutput(exec_command)
                log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.info("拷贝失败！")
                elif root != "Administrator":
                    exec_command = f'chmod 777 /root/{os.path.basename(tool_file)}'
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                        ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

    @classmethod
    def __sagitta_ddp_switch__sagitta_ddp_switch(cls) -> None:
        """
        author:      xiangyu.liu
        date:        2023-08-08 15:34:55
        description: 处理ddp开关
        :return:     None
        """
        if cls.server_nic_model == 'windows':
            env_config_path = tj_constants.WINDOWS_FILE_PATH_ROOT
            root = "Administrator"
            bin_path = env_config_path
        else:
            env_config_path = tj_constants.LINUX_FILE_PATH_ROOT
            root = "root"
            bin_path = "/usr/bin/"

        # 清空dmesg
        target_host_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        exec_command = f'ssh -p {cls.test_port} {root}@{target_host_ip} "dmesg -C"'
        log.info("exec_command::::{}".format(exec_command))
        status, result = cls.getstatusoutput(exec_command)
        if status != RtnStatusEnum.SUCCESS.value:
            log.error(f'command:{exec_command}执行失败, status:{status}, result:{result}')
            exit(1)
        else:
            log.info(f'command:{exec_command}, status:{status}, result:{result}')

        # 重新加载驱动，设置ddp_sup=1
        log.info("==> 重新加载驱动，设置ddp_sup=1")
        target_host_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        exec_command = f'ssh -p {cls.test_port} {root}@{target_host_ip} "rmmod {cls.nicg}; insmod /root/{cls.nicg}.ko ddp_sup=1"'
        log.info("exec_command::::{}".format(exec_command))
        status, result = cls.getstatusoutput(exec_command)
        if status != RtnStatusEnum.SUCCESS.value:
            log.error(f'command:{exec_command}执行失败, status:{status}, result:{result}')
            exit(1)
        else:
            log.info(f'command:{exec_command}, status:{status}, result:{result}')

        # 检查message
        log.info("==> 检查设置ddp_sup=1是否成功")
        target_host_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        exec_command = f'ssh -p {cls.test_port} {root}@{target_host_ip} "dmesg |grep {cls.nicg}|grep DDP"'
        log.info("exec_command::::{}".format(exec_command))
        status, result = cls.getstatusoutput(exec_command)
        if status != RtnStatusEnum.SUCCESS.value:
            log.error(f'command:{exec_command}执行失败, status:{status}, result:{result}')
            exit(1)
        else:
            if 'The DDP package was successfully loaded' not in result:
                log.error(f'疑似BUG: ddp_sup开启失败！')
                exit(1)
            else:
                log.info("设置ddp_sup=1成功")

    @classmethod
    def __env_check_and_recover_rpc_process(cls) -> None:
        """
        author:      junfeng.he
        date:        2023-08-08 15:34:55
        description: 检查环境是否有残留的rpc脚本进程，kill掉
        :return:     None
        """
        target_server_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        target_client_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
        for target_info in [[target_server_ip, CmdExecuteAdressEnum.SERVER.value],
                            [target_client_ip, CmdExecuteAdressEnum.CLIENT.value]]:
            target_host_ip = target_info[0]
            target_execute_address = target_info[1]
            vm, rpc_port = CommonOperation.get_node_info_from_path()

            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and target_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue

            if (target_execute_address == CmdExecuteAdressEnum.SERVER.value and
                cls.server_nic_model == 'windows') or \
                    (target_execute_address == CmdExecuteAdressEnum.CLIENT.value and
                     cls.client_nic_model == 'windows'):
                env_config_path = tj_constants.WINDOWS_FILE_PATH_ROOT
                vm_path = "{}{}".format(env_config_path, vm)
                server_command_kill = "taskkill -f -t -im python3.exe"
            else:
                env_config_path = tj_constants.LINUX_FILE_PATH_ROOT
                vm_path = "{}{}".format(env_config_path, vm)
                server_command_kill = "ps -ef | grep -E 'python3 {}/rpc_server.py|python3 {}/rpc_client.py" \
                                      "|python3 {}/receive_packet.py|python3 {}/send_packet.py'".format(
                    vm_path, vm_path, vm_path, vm_path) + " | grep -v grep | awk '{print$2}' | xargs kill -9"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command_kill, cmd_execute_address=target_execute_address,
                ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f"{server_command_kill},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

    @classmethod
    def __env_check_and_recover_port_status(cls) -> None:
        """
        author:      junfeng.he
        date:        2023-08-08 15:34:55
        description: 检查环境中陪测网卡端口是否非预期down，则尝试恢复环境
        :return:     None
        """
        if cls.server_nic_model == 'windows' or cls.client_nic_model == 'windows':
            return

        if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.SINGLE_MODE, tj_constants.DPDK_MODE, tj_constants.DPDK_AUTO_MODE]:
            return
        # 如果陪测网卡端口非预期down，则尝试恢复环境,此处逻辑需要server和client的绝对值
        log.info("如果陪测网卡端口非预期down，则尝试恢复环境...")
        if not cls.env_dict:
            log.warning("当前还未获取到server和client的device_name,不操作")
            return
        log.info("初始环境信息为:{}".format(cls.env_dict))
        device_name_server = cls.env_dict['server_device_name']
        device_name_client = cls.env_dict['client_device_name']
        # 使用NIC_CONFIG_BK_PATH配置，为绝对配置
        driver_name_server, driver_name_client = \
            CommonOperation.get_nic_driver_name(current_config=scripts_constants.NIC_CONFIG_BK_PATH)
        server_ip, client_ip = \
            CommonOperation.get_nic_logical_ip(current_config=scripts_constants.NIC_CONFIG_BK_PATH)

        log.warning('检查测试physical server端口是否正常')
        if cls.server_nic_model == 'windows':
            root = "Administrator"
        else:
            root = "root"
        exec_command = 'ip a | grep {}'.format(device_name_server)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port),
            ssh_username=f'{root}',
            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        if "DOWN" in rtn_outputs and driver_name_server not in ['sxe', f'{cls.nicg}']:
            log.warning('server端{} DOWN，并且非sxe/{}驱动，则尝试ethtool -r {}'.
                        format(device_name_server, cls.nicg, device_name_server))
            exec_command = 'ethtool -r {}'.format(device_name_server)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port),
                ssh_username=f'{root}',
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        else:
            if driver_name_server in ['sxe', f'{cls.nicg}']:
                log.warning("server端{}，当前为sxe/{}，不操作.".format(device_name_server, cls.nicg))
            else:
                log.warning("server端{}，当前为非DOWN状态，不操作.".format(device_name_server))

        if cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]:
            log.info('single mode或发包仪环境，跳过client命令执行')
        else:
            log.warning('检查测试physical client端口是否正常')
            if cls.client_nic_model == 'windows':
                root = "Administrator"
            else:
                root = "root"
            exec_command = 'ip a | grep {}'.format(device_name_client)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, ssh_port=str(cls.test_port),
                ssh_username=f'{root}',
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
            if "DOWN" in rtn_outputs and driver_name_client not in ['sxe', f'{cls.nicg}']:
                log.warning('client端{} DOWN，并且非sxe/{}驱动，则尝试ethtool -r {}'.
                            format(device_name_client, cls.nicg, device_name_client))
                exec_command = 'ethtool -r {}'.format(device_name_client)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, ssh_port=str(cls.test_port),
                    ssh_username=f'{root}',
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
            else:
                if driver_name_client in ['sxe', f'{cls.nicg}']:
                    log.warning("client端{}，当前为sxe/{}，不操作.".format(device_name_client, cls.nicg))
                else:
                    log.warning("client端{}，当前非DOWN状态，不操作.".format(device_name_client))

    @classmethod
    def __env_check_and_recover_route(cls) -> bool:
        """
        author:      junfeng.he
        date:        2023-09-19 15:34:55
        description: 检查环境中是否非预期丢路由，尝试恢复环境
        :return:     None
        """
        have_route_loss = False
        if cls.server_nic_model == 'windows' or cls.client_nic_model == 'windows':
            return have_route_loss

        if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.SINGLE_MODE, tj_constants.DPDK_MODE, tj_constants.DPDK_AUTO_MODE]:
            return have_route_loss

        log.info("检查环境中是否无ip，尝试ifup恢复环境...")
        server_relation_list, client_relation_list = CommonOperation.get_nic_relationships()
        env_info_dict = {CmdExecuteAdressEnum.SERVER.value: server_relation_list,
                         CmdExecuteAdressEnum.CLIENT.value: client_relation_list}
        for target_cmd_execute_address, relation_list in env_info_dict.items():

            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and target_cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue

            for index, device_name in enumerate(relation_list):
                exec_cmd = "ip a | grep {}".format(device_name)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_cmd, cmd_execute_address=target_cmd_execute_address, ssh_port=str(cls.test_port),
                    ssh_username=f'root',
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f"{exec_cmd},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                route_ips = re.findall(r'inet (\d+\.\d+\.\d+\.)', rtn_outputs)
                if not route_ips:
                    log.warning("==> {}无ip，执行ifup尝试恢复".format(device_name, device_name))
                    exec_cmd = "ifup {}".format(device_name)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_cmd, cmd_execute_address=target_cmd_execute_address, ssh_port=str(cls.test_port),
                        ssh_username=f'root',
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f"{exec_cmd},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                    time.sleep(1)

        # 如果陪测网卡端口非预期down，则尝试恢复环境,此处逻辑需要server和client的绝对值
        log.info("检查环境中是否非预期丢路由，尝试恢复环境...")
        if 'none' in server_relation_list or 'none' in client_relation_list:
            log.warning("env_config.ini中网口关系配置中存在none，无法进行路由恢复")
            return have_route_loss

        for target_cmd_execute_address, relation_list in env_info_dict.items():

            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and target_cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue

            exec_cmd = "route -n"
            rtn_code, route_result, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_cmd, cmd_execute_address=target_cmd_execute_address, ssh_port=str(cls.test_port),
                ssh_username=f'root',
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f"{exec_cmd},rtn_code:{rtn_code}, route_result:{route_result}, rtn_err:{rtn_err}")
            for index, device_name in enumerate(relation_list):
                if device_name not in route_result:
                    log.warning("==> {}的路由丢失，添加路由尝试恢复".format(device_name, device_name))
                    have_route_loss = True
                    exec_cmd = "ip a | grep {}".format(device_name)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_cmd, cmd_execute_address=target_cmd_execute_address, ssh_port=str(cls.test_port),
                        ssh_username=f'root',
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f"{exec_cmd},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                    route_ips = re.findall(r'inet (\d+\.\d+\.\d+\.)', rtn_outputs)
                    if route_ips:
                        route_ip = route_ips[0] + "0"
                        exec_cmd = "route add -net {}/24 dev {}".format(route_ip, device_name)
                        rtn_code, rtn_outputs, rtn_err = \
                            CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_cmd,
                                cmd_execute_address=target_cmd_execute_address, ssh_port=str(cls.test_port),
                                ssh_username=f'root',
                                host_os_server=cls.frame_run_dict['config_dict'].get(
                                    tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].get(
                                    tj_constants.EVN_CLIENT_NIC_MODEL))
                        log.info(f"{exec_cmd},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                        time.sleep(5)
        return have_route_loss

    @classmethod
    def __env_check_and_recover_networkmanager(cls) -> None:
        """
        author:      junfeng.he
        date:        2024-05-10 15:34:55
        description: 检查环境NetworkManager
        :return:     None
        """
        if cls.server_nic_model == 'windows' or cls.client_nic_model == 'windows':
            return
        for target_execute_address in [CmdExecuteAdressEnum.SERVER.value, CmdExecuteAdressEnum.CLIENT.value]:

            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and target_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue

            command = "systemctl status NetworkManager"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                ssh_username=f'root',
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
            if "inactive (dead)" in rtn_outputs + rtn_err:
                command = "systemctl restart NetworkManager"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                    ssh_username=f'root',
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

            command = "systemctl enable NetworkManager"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                ssh_username=f'root',
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

            # 环境这个时间过短，容易出现超时问题
            command = "echo 120 > /proc/sys/kernel/hung_task_timeout_secs"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                ssh_username=f'root',
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")


    @classmethod
    def __env_check_and_recover_ko(cls) -> None:
        """
        author:      junfeng.he
        date:        2023-09-25 15:34:55
        description: 检查环境sxe.ko是否已加载
        :return:     None
        """
        if cls.server_nic_model == 'windows' or cls.client_nic_model == 'windows':
            return

        if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.DPDK_MODE, tj_constants.DPDK_AUTO_MODE]:
            return
        server_driver_name, client_driver_name = CommonOperation.get_nic_driver_name()
        for target_device_info in [[server_driver_name, CmdExecuteAdressEnum.SERVER.value],
                                   [client_driver_name, CmdExecuteAdressEnum.CLIENT.value]]:
            target_driver_name = target_device_info[0]
            target_execute_address = target_device_info[1]

            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and target_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue

            if target_driver_name == scripts_constants.DRV_SXE_PF:
                command = f"lsmod | grep -w {scripts_constants.DRV_SXE_PF}"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                    ssh_username=f'root',
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                if scripts_constants.DRV_SXE_PF not in rtn_outputs:
                    if cls.frame_run_dict['config_dict'].get(
                            constants.ENV_TEST_OBJECT) in [constants.ENV_RUN_MODE_WITH_SRC,
                                                           constants.ENV_RUN_MODE_WITH_RPM,
                                                           constants.ENV_RUN_MODE_WITH_SRPM,
                                                           constants.ENV_RUN_MODE_WITH_KMOD_SRPM]:
                        command = f'modprobe {scripts_constants.DRV_SXE_PF}'
                    else:
                        command = f"insmod /root/{scripts_constants.DRV_SXE_PF}.ko"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                        ssh_username=f'root',
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
            elif target_driver_name == cls.nicg:
                command = f"lsmod | grep -w {cls.nicg}"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                    ssh_username=f'root',
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                if cls.nicg not in rtn_outputs:
                    command = f"insmod /root/{cls.nicg}_auxiliary.ko"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                        ssh_username=f'root',
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )

                    if cls.frame_run_dict['config_dict'].get(
                            constants.ENV_TEST_OBJECT) in [constants.ENV_RUN_MODE_WITH_SRC,
                                                           constants.ENV_RUN_MODE_WITH_RPM,
                                                           constants.ENV_RUN_MODE_WITH_SRPM,
                                                           constants.ENV_RUN_MODE_WITH_KMOD_SRPM]:
                        command = f'modprobe {cls.nicg}'
                    else:
                        command = f"insmod /root/{cls.nicg}.ko"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                        ssh_username=f'root',
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )

                    # 环境这个时间过短，容易出现超时问题
                    command = "echo 120 > /proc/sys/kernel/hung_task_timeout_secs"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                        ssh_username=f'root',
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )

                    command = "ulimit -c unlimited"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                        ssh_username=f'root',
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )

                    command = "echo '/home/nic_core/core-%e-%p-%t' > /proc/sys/kernel/core_pattern"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                        ssh_username=f'root',
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )

            elif target_driver_name == scripts_constants.DRV_SCGBE_RDMA:
                command = f"lsmod | grep -w {scripts_constants.DRV_SCGBE_RDMA}"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                    ssh_username=f'root',
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                if scripts_constants.DRV_SCGBE_RDMA not in rtn_outputs:
                    # 先加载以太驱动
                    command = f"lsmod | grep -w {cls.nicg}"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                        ssh_username=f'root',
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                    if cls.nicg not in rtn_outputs:
                        command = f"insmod /root/{cls.nicg}_auxiliary.ko"
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                            ssh_username=f'root',
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                        )

                        if cls.frame_run_dict['config_dict'].get(
                                constants.ENV_TEST_OBJECT) in [constants.ENV_RUN_MODE_WITH_SRC,
                                                               constants.ENV_RUN_MODE_WITH_RPM,
                                                               constants.ENV_RUN_MODE_WITH_SRPM,
                                                               constants.ENV_RUN_MODE_WITH_KMOD_SRPM]:
                            command = f'modprobe {cls.nicg}'
                        else:
                            command = f"insmod /root/{cls.nicg}.ko"
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                            ssh_username=f'root',
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                        )
                        log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

                    # 加载rdma驱动
                    if cls.frame_run_dict['config_dict'].get(
                            constants.ENV_TEST_OBJECT) in [constants.ENV_RUN_MODE_WITH_SRC,
                                                           constants.ENV_RUN_MODE_WITH_RPM,
                                                           constants.ENV_RUN_MODE_WITH_SRPM,
                                                           constants.ENV_RUN_MODE_WITH_KMOD_SRPM]:
                        command = f'modprobe {scripts_constants.DRV_SCGBE_RDMA}'
                    else:
                        command = f"insmod /root/{scripts_constants.DRV_SCGBE_RDMA}.ko resource_profile=2 fragment_count_limit=13"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                        ssh_username=f'root',
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

    @classmethod
    def __env_check_and_recover_dpdk_taken(cls) -> None:
        """
        author:      junfeng.he
        date:        2023-08-24 15:34:55
        description: 检查环境是否有残留的dpdk脚本进程，kill掉,检查环境是否仍有dpdk驱动占用，如有则换绑
        :return:     None
        """
        # if '00' != CommonOperation.get_fpga_bitfile_class():
        #     log.warning("FPGA 当前不支持dpdk app退出，为了支持多人使用FPGA的多对口，先去掉这步检查")
        #     return
        if cls.server_nic_model == 'windows' or cls.client_nic_model == 'windows':
            return

        if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.DPDK_MODE, tj_constants.DPDK_AUTO_MODE]:
            return
        env_config_path = tj_constants.LINUX_FILE_PATH_ROOT
        vm, rpc_port = CommonOperation.get_node_info_from_path()
        log.info("vm:{},rpc_port:{}".format(vm, rpc_port))
        vm_path = "{}{}".format(env_config_path, vm)
        server_driver_name, client_driver_name = CommonOperation.get_nic_driver_name()
        for target_info in [[CmdExecuteAdressEnum.SERVER.value, server_driver_name],
                            [CmdExecuteAdressEnum.CLIENT.value, client_driver_name]]:
            target_cmd_execute_address = target_info[0]
            target_driver_name = target_info[1]

            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE])and target_cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue

            exec_cmd = f"cat {vm_path}/dpdktest_flag"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_cmd, cmd_execute_address=target_cmd_execute_address, ssh_port=str(cls.test_port),
                ssh_username=f'root',
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f"{exec_cmd},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
            if "clear" in rtn_outputs:
                continue

            server_command_kill = "ps -ef | grep -E 'dpdk-testpmd|dpdk-ethtool|dpdk-proc-info|dpdk-ptpclient|pktgen'" \
                                  " | grep {}".format(vm) + " | grep -v grep | awk '{print$2}' | xargs kill -9"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=server_command_kill, cmd_execute_address=target_cmd_execute_address, ssh_port=str(cls.test_port),
                ssh_username=f'root',
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f"{server_command_kill},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

            exec_cmd = f"{env_config_path}dpdk-devbind.py -s"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_cmd, cmd_execute_address=target_cmd_execute_address, ssh_port=str(cls.test_port),
                ssh_username=f'root',
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f"{exec_cmd},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
            if "Other Network devices" in rtn_outputs:
                """
                Other Network devices
                =====================
                0000:45:00.1 'Device 10a1' unused=igb_uio,vfio-pci
                """
                bus_info_list = re.findall(r"Other Network devices\n.*\n(\S*)", rtn_outputs)
                if bus_info_list:
                    bus_info = bus_info_list[0]
                    log.info("找到Other Network devices！先换绑回igb_uio驱动，再操作！")
                    if target_driver_name == "sxe":
                        log.warning("sxe当前存在BUG: 1647330,需要卸载再加载驱动才能恢复")
                        if cls.frame_run_dict['config_dict'].get(
                                constants.ENV_TEST_OBJECT) in [constants.ENV_RUN_MODE_WITH_SRC,
                                                               constants.ENV_RUN_MODE_WITH_RPM,
                                                               constants.ENV_RUN_MODE_WITH_SRPM,
                                                               constants.ENV_RUN_MODE_WITH_KMOD_SRPM]:
                            exec_cmd = 'rmmod sxe;modprobe sxe'
                        else:
                            exec_cmd = "rmmod sxe;insmod /root/sxe.ko"
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_cmd, cmd_execute_address=target_cmd_execute_address, ssh_port=str(cls.test_port),
                            ssh_username=f'root',
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                        )
                        log.info(f"{exec_cmd},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                        time.sleep(3)
                        exec_cmd = "{}dpdk-devbind.py -s | grep {}".format(env_config_path, bus_info)
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_cmd, cmd_execute_address=target_cmd_execute_address, ssh_port=str(cls.test_port),
                            ssh_username=f'root',
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                        )
                        log.info(f"{exec_cmd},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                        eth_info_list = re.findall(r"if=(\S*)", rtn_outputs)
                        if eth_info_list:
                            eth_info = eth_info_list[0]
                            exec_cmd = "ifup {}".format(eth_info)
                            rtn_code, rtn_outputs, rtn_err = \
                                CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=exec_cmd, cmd_execute_address=target_cmd_execute_address,
                                    ssh_port=str(cls.test_port), ssh_username=f'root',
                                    host_os_server=cls.frame_run_dict['config_dict'].get(
                                        tj_constants.EVN_SERVER_NIC_MODEL),
                                    host_os_client=cls.frame_run_dict['config_dict'].get(
                                        tj_constants.EVN_CLIENT_NIC_MODEL))
                            log.info(f"{exec_cmd},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                    else:
                        if target_cmd_execute_address == CmdExecuteAdressEnum.SERVER.value:
                            if bus_info not in cls.dev_bdf_list[0].values():
                                continue
                            exec_cmd = "{}dpdk-devbind.py -b igb_uio {}".format(env_config_path, bus_info)
                        else:
                            if bus_info not in cls.dev_bdf_list[1].values():
                                continue
                            exec_cmd = "{}dpdk-devbind.py -b igb_uio {}".format(env_config_path, bus_info)
                        rtn_code, rtn_outputs, rtn_err = \
                            CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_cmd, cmd_execute_address=target_cmd_execute_address,
                                ssh_port=str(cls.test_port),
                                ssh_username=f'root',
                                host_os_server=cls.frame_run_dict['config_dict'].get(
                                    tj_constants.EVN_SERVER_NIC_MODEL),
                                host_os_client=cls.frame_run_dict['config_dict'].get(
                                    tj_constants.EVN_CLIENT_NIC_MODEL))
                        log.info(f"{exec_cmd},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

                    exec_cmd = f"{env_config_path}dpdk-devbind.py -s"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_cmd, cmd_execute_address=target_cmd_execute_address, ssh_port=str(cls.test_port),
                        ssh_username=f'root',
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f"{exec_cmd},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

            if "Network devices using DPDK-compatible driver" in rtn_outputs:
                bus_info_list = re.findall(r"Network devices using DPDK-compatible driver\n.*\n(\S*)", rtn_outputs)
                if bus_info_list:
                    bus_info = bus_info_list[0]
                    if target_cmd_execute_address == CmdExecuteAdressEnum.SERVER.value:
                        if bus_info not in cls.dev_bdf_list[0].values():
                            continue
                        exec_cmd = "{}dpdk-devbind.py -b {} {}".format(env_config_path, server_driver_name, bus_info)
                    else:
                        if bus_info not in cls.dev_bdf_list[1].values():
                            continue
                        exec_cmd = "{}dpdk-devbind.py -b {} {}".format(env_config_path, client_driver_name, bus_info)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_cmd, cmd_execute_address=target_cmd_execute_address, ssh_port=str(cls.test_port),
                        ssh_username=f'root',
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f"{exec_cmd},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

                    exec_cmd = "{}dpdk-devbind.py -s | grep {}".format(env_config_path, bus_info)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_cmd, cmd_execute_address=target_cmd_execute_address, ssh_port=str(cls.test_port),
                        ssh_username=f'root',
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(
                        f"{exec_cmd},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                    eth_info_list = re.findall(r"if=(\S*)", rtn_outputs)
                    if eth_info_list:
                        eth_info = eth_info_list[0]
                        exec_cmd = "ifup {}".format(eth_info)
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_cmd, cmd_execute_address=target_cmd_execute_address, ssh_port=str(cls.test_port),
                            ssh_username=f'root',
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                        )
                        log.info(f"{exec_cmd},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                        log.info("找到绑定dpdk设备，换绑还原环境完成.")
                else:
                    log.info("未找到绑定dpdk的bus-info！无法换绑回原来驱动！")
            else:
                log.info("未找到绑定dpdk设备，无需换绑.")
            exec_cmd = f"echo 'clear' > {vm_path}/dpdktest_flag"
            log.info(f"执行{exec_cmd}，清除dpdktest_flag")
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_cmd, cmd_execute_address=target_cmd_execute_address, ssh_port=str(cls.test_port),
                ssh_username=f'root',
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            # log.info(f"{exec_cmd},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

            exec_cmd = f"ls /tmp/screens/S-root | grep {vm}" + r"| xargs rm -fr {}"
            log.info(f"执行{exec_cmd}，清除dpdk临时文件，防止出现该文件异常导致后续screen不可用问题")
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_cmd, cmd_execute_address=target_cmd_execute_address, ssh_port=str(cls.test_port),
                ssh_username=f'root',
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )


    @classmethod
    def __sagitta_check_physical_env(cls) -> bool:
        """
        author:      junfeng.he
        date:        2023-08-08 15:34:55
        description: 将测试主机中的入口主机配置文件scp过来,并对环境做基本检查
        :return:     None
        """
        enable_flag = True
        log.warning("==> 做环境清理与修复：")
        if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.UEFI_MODE]:
            log.info("uefi测试模式，无需进行os下的配置与检查")
            return enable_flag
        cls.__env_check_and_recover_networkmanager()
        cls.__env_check_and_recover_ko()
        cls.__env_check_and_recover_dpdk_taken()
        cls.__env_check_and_recover_rpc_process()
        cls.__env_check_and_recover_port_status()
        cls.__env_check_and_recover_route()
        cls.__force_clear_virtual_environment()
        cls.__clean_vlan()
        cls.__check_adapter_number()
        log.warning("==> 环境工具检查：")
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        server_ip, client_ip = CommonOperation.get_nic_logical_ip()
        server_dev, client_dev = CommonOperation.get_nic_relationships()
        server_driver_name, client_driver_name = CommonOperation.get_nic_driver_name()
        # renix_server_list, renix_locations_list = CommonOperation.get_renix()
        # linux需要检查工具是否已安装、版本是否符合要求、防火墙是否已放通测试预留端口
        if 'windows' != host_os_server:
            enable_flag = enable_flag & cls.__check_items(server_ip, True)
        if 'windows' != host_os_client and not cls.client_renix_only_flag and cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) not in [tj_constants.SINGLE_MODE]:
            enable_flag = enable_flag & cls.__check_items(client_ip, False)

        log.warning("==> 根据env_config.ini中的组网配置关系进行ip配置：")
        cls.__update_ip_config_by_env_config()

        log.warning("==> 检查环境是否server和client联通：")
        fpga_bit_version = CommonOperation.get_cli_fpga_bit_version(server_os_type=host_os_server,
                                                                    server_ip=server_ip, test_port=cls.test_port)
        CommonOperation.set_fpga_bit_version(value=fpga_bit_version)
        chip_identification = CommonOperation.get_chip_identification()
        skip_fpga_check = False
        fpga_bitfile_class = ''
        if chip_identification == 'f':
            fpga_bitfile_class = CommonOperation.get_fpga_bitfile_class()
            if fpga_bitfile_class in tj_constants.RDMA_BITFILES:
                # C/K/L bitfile FPGA，单端模式
                if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                     [tj_constants.SINGLE_MODE]:
                    log.warning('C/K/L bitfile FPGA，单端模式：C/K/L bitfile裁剪了部分以太功能，无法处理以太报文，必须在单端模式下ifdown对端网卡(BUGID-2600289)')
                    ps3server_client_ip = cls.frame_run_dict['ip_dict']['client_ip']

                    cmd = "nc -zv {} {}".format(ps3server_client_ip, cls.test_port)
                    cmd_rtn, cmd_output, cmd_stderr = CommandOperation. \
                        execute_command_based_paramiko_with_rtncode(cmd=cmd, local_execute_flag=True)
                    log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
                    # 如果对端管理ip连不同，不再ifdown对端
                    if "Connected" not in cmd_output + cmd_stderr:
                        pass
                    else:
                        # server被测设备的ip
                        cmd = f"ifconfig {server_dev[0]}|grep 'inet '|cut -d ' ' -f 10"
                        cmd_rtn, server_dev_ip, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        target_ip_header = '.'.join(server_dev_ip.split('.')[:-1])

                        # 根据ip获取client对联设备名称
                        need_ifdown_client_dev = True
                        if cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]:
                            log.info('single mode或发包仪环境，跳过client命令执行')
                        else:
                            cmd = f"ifconfig |grep -B 1 {target_ip_header}|grep -v 'inet '|cut -d ':' -f 1"
                            cmd_rtn, client_dev, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=cmd, ssh_ip=ps3server_client_ip, ssh_port=str(cls.test_port),
                                cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        if not client_dev:
                            if cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]:
                                log.info('single mode或发包仪环境，跳过client命令执行')
                            else:
                                # 根据rdma link获取对端物理连接的设备名
                                log.warning(f'根据[{server_ip}]的设备{server_dev}的ip:{server_dev_ip}获取[{ps3server_client_ip}]的设备名失败，'
                                            f'可能未配置IP, 继续使用rdma link获取[{ps3server_client_ip}]的设备名')
                                cmd = f"rdma link|grep LINK_UP|cut -d ' ' -f 8"
                                cmd_rtn, client_dev, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=cmd, ssh_ip=ps3server_client_ip, ssh_port=str(cls.test_port),
                                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                                client_dev_list = client_dev.split('\n')
                                if len(client_dev_list) > 1:
                                    # 根据env_config.ini.sc获取对端物理连接的设备名
                                    log.warning(f"client设备数大于1: {client_dev_list}，尝试通过env_config.ini.sc获取client设备")
                                    cmd = f"cat env_config.ini.sc|grep -A 2 relationships_rdma|grep client|cut -d '=' -f 2"
                                    cmd_rtn, client_dev, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                        cmd=cmd, ssh_ip=ps3server_client_ip, ssh_port=str(cls.test_port),
                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                                    if not client_dev:
                                        log.warning(f"获取client设备失败，无法ifdown对端以太设备。可能已经是ifdown状态，"
                                                    f"也可能没有ifdown(会存在以太报文影响自动化测试)。框架继续执行")
                                        need_ifdown_client_dev = False

                        if need_ifdown_client_dev:
                            if cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]:
                                log.info('single mode或发包仪环境，跳过client命令执行')
                            else:
                                # 防止直接ifdown失败，先ifup，再ifdown
                                cmd = f"ifup {client_dev}"
                                cmd_rtn, client_res, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=cmd, ssh_ip=ps3server_client_ip, ssh_port=str(cls.test_port),
                                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                                cmd = f"ifdown {client_dev}"
                                cmd_rtn, client_res, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=cmd, ssh_ip=ps3server_client_ip, ssh_port=str(cls.test_port),
                                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)

                                cmd = f"ip addr show dev {client_dev}"
                                cmd_rtn, client_res, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=cmd, ssh_ip=ps3server_client_ip, ssh_port=str(cls.test_port),
                                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                                if 'inet ' in client_res or 'inet6 ' in client_res:
                                    log.error(f"client: {ps3server_client_ip}, ifdown {client_dev} 失败，测试框架退出，请检查环境！")
                                    exit(1)
                        else:
                            log.warning('C/K/L bitfile FPGA，单端模式：当前没有执行ifdown对端网卡')

                # C/K/L bitfile FPGA，对联模式
                else:
                    if cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]:
                        log.info('single mode或发包仪环境，跳过client命令执行')
                    else:
                        skip_fpga_check = True
                        log.warning('C/K/L bitfile FPGA，对联模式：C/K/L bitfile裁剪了部分以太功能，导致os无法自动更新arp，因此需要手动配置arp')
                        # todo c bitfile裁剪了rx lan，导致os无法自动更新arp，因此需要手动配置arp
                        # server更新arp
                        cmd = f"ifconfig {client_dev[0]} |grep 'inet '|cut -c 14-26"
                        cmd_rtn, client_dev_ip, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=client_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        cmd = f'ifconfig {client_dev[0]}|grep ether|cut -c 15-31'
                        cmd_rtn, client_dev_mac, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=client_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        cmd = f'arp -d {client_dev_ip}'
                        cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        cmd = f'arp -s {client_dev_ip} {client_dev_mac}'
                        cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        # client更新arp
                        cmd = f"ifconfig {server_dev[0]} |grep 'inet '|cut -c 14-26"
                        cmd_rtn, server_dev_ip, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        cmd = f'ifconfig {server_dev[0]}|grep ether|cut -c 15-31'
                        cmd_rtn, server_dev_mac, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        cmd = f'arp -d {server_dev_ip}'
                        cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=client_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        cmd = f'arp -s {server_dev_ip} {server_dev_mac}'
                        cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=client_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        # 打印更新后的arp
                        cmd = f'arp -n |grep -w {server_dev[0]}'
                        cmd_rtn, cmd_res, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        if 'incomplete' in cmd_res:
                            log.error(f'server: {server_ip}, 更新arp失败，测试框架退出，请检查环境！')
                            exit(1)
                        cmd = f'arp -n |grep -w {client_dev[0]}'
                        cmd_rtn, cmd_res, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=client_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        if 'incomplete' in cmd_res:
                            log.error(f'client: {client_ip}, 更新arp失败，测试框架退出，请检查环境！')
                            exit(1)

                        # ipv6
                        # server更新arp
                        cmd = f"ifconfig {client_dev[0]} |grep 'inet6 '"
                        cmd_rtn, cmd_res, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=client_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        if cmd_res:
                            client_dev_ip = cmd_res.split()[1]
                            cmd = f'ifconfig {client_dev[0]}|grep ether'
                            cmd_rtn, cmd_res, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=cmd, ssh_ip=client_ip, ssh_port=str(cls.test_port),
                                cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                            client_dev_mac  = cmd_res.split()[1]
                            cmd = f'ip -6 neigh del {client_dev_ip} dev {server_dev[0]}'
                            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                            cmd = f'ip -6 neigh add {client_dev_ip} lladdr {client_dev_mac} dev {server_dev[0]}'
                            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        else:
                            log.warning(f'server配置arp失败: {client_ip}未找到{client_dev[0]} ipv6地址，不进行neigh配置')

                        # client更新arp
                        cmd = f"ifconfig {server_dev[0]} |grep 'inet6 '"
                        cmd_rtn, cmd_res, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        if cmd_res:
                            server_dev_ip = cmd_res.split()[1]
                            cmd = f'ifconfig {server_dev[0]}|grep ether'
                            cmd_rtn, cmd_res, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                            server_dev_mac  = cmd_res.split()[1]
                            cmd = f'ip -6 neigh del {server_dev_ip} dev {client_dev[0]}'
                            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=cmd, ssh_ip=client_ip, ssh_port=str(cls.test_port),
                                cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                            cmd = f'ip -6 neigh add {server_dev_ip} {server_dev_mac} dev {client_dev[0]}'
                            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=cmd, ssh_ip=client_ip, ssh_port=str(cls.test_port),
                                cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        else:
                            log.warning(f'client配置arp失败: {server_ip}未找到{server_dev[0]} ipv6地址，不进行neigh配置')

                        # 打印更新后的arp
                        cmd = f'ip -6 neigh show |grep -w {server_dev[0]}|grep -w {client_dev_ip}'
                        cmd_rtn, cmd_res, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        if 'FAILED' in cmd_res:
                            log.error(f'server: {server_ip}, 更新neigh失败，测试框架退出，请检查环境！')
                            exit(1)
                        cmd = f'ip -6 neigh show |grep -w {client_dev[0]}|grep -w {server_dev_ip}'
                        cmd_rtn, cmd_res, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=client_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        if 'FAILED' in cmd_res:
                            log.error(f'client: {client_ip}, 更新neigh失败，测试框架退出，请检查环境！')
                            exit(1)

        if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.DPDK_MODE, tj_constants.DPDK_AUTO_MODE]:
            log.warning("dpdk mode：不检查主机驱动下pf设备是否联通")
        elif cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.SINGLE_MODE]:
            log.warning("single mode：不检查主机驱动下pf设备是否联通")
        elif cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.UEFI_MODE]:
            log.warning("uefi mode：不检查主机驱动下pf设备是否联通")
        elif cls.client_renix_only_flag:
            log.warning("renix：仅存在发包仪，不检查主机驱动下pf设备是否联通")
        elif skip_fpga_check:
            log.warning(f"fpga bitfile-{fpga_bitfile_class}：不检查主机驱动下pf设备是否联通")
        else:
            pf_device_name_server, pf_device_name_client, cls.env_dict = \
                CommonOperation.get_target_test_device(cls.test_port)
            if pf_device_name_client == '' or pf_device_name_server == '':
                log.warning(f'server和client pf不通，等待30s再重试一次.')
                time.sleep(30)
                pf_device_name_server, pf_device_name_client, cls.env_dict = \
                    CommonOperation.get_target_test_device(cls.test_port)
                if pf_device_name_client == '' or pf_device_name_server == '':
                    log.warning(f'server和client pf不通，等待100s再重试一次.')
                    custom_params = cls.frame_run_dict['config_dict'].get(constants.ENV_CUSTOM_PARAMS, "None")
                    if constants.CUSTOM_PARAMS_CORE_RESET_RECOVERY_LINK in custom_params and cls.__check_link_status():
                        log.warning("两端ping不通，可能存在链路问题，尝试core reset来恢复")
                        iretry = 3
                        while iretry:
                            cls.__core_reset()
                            time.sleep(80)
                            if not cls.__check_link_status():
                                log.info("==>recovery：core reset后链路问题解决")
                                break
                            pf_device_name_server, pf_device_name_client, cls.env_dict = \
                                CommonOperation.get_target_test_device(cls.test_port)
                            if pf_device_name_client == '' or pf_device_name_server == '':
                                pass
                            else:
                                log.info("==>recovery：core reset后ping不通问题解决")
                                break
                            iretry -= 1
                            if iretry == 0:
                                log.error("==>recovery：3次core reset后问题仍然未解决！！")
                    else:
                        time.sleep(100)
                    pf_device_name_server, pf_device_name_client, cls.env_dict = \
                        CommonOperation.get_target_test_device(cls.test_port)
                    if pf_device_name_client == '' or pf_device_name_server == '':
                        cls.__check_link_status()
                        log.error(f'server和client pf不通，测试框架退出，请检查环境！')
                        # 置位framework_bug_stop_flag
                        cls.__set_framework_bug_stop_flag("1")
                        exit(1)
        return enable_flag

    @classmethod
    def __update_ip_config_by_env_config(cls) -> bool:
        """
        author:      junfeng.he
        date:        2023-08-24 15:34:55
        description: 根据env_config.ini中的组网配置关系进行ip配置,【192，168，C. D】
        每个vm测试节点C=(vm//10)%100,D=(vm%10)*10+id
        :return:     None
        """
        if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.UEFI_MODE]:
            log.info("uefi测试模式，无需进行os下的ip配置")
            return True

        server_ip, client_ip = CommonOperation.get_nic_logical_ip()
        server_relation_list, client_relation_list = CommonOperation.get_nic_relationships()
        server_driver_name, client_driver_name = CommonOperation.get_nic_driver_name()
        # renix_server_list, renix_locations_list = CommonOperation.get_renix()

        # 重新組合relation
        s_c_relation_dict = {}
        for server_dev, client_dev in zip(server_relation_list, client_relation_list):
            s_c_relation_dict[server_dev] = client_dev

        if 'none' in server_relation_list or 'none' in client_relation_list:
            log.warning("env_config.ini中网口关系配置中存在none，不做ip配置")
            return False

        server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
        if server_ip == server_mgr_ip and client_ip == client_mgr_ip:
            pass
        else:
            if server_ip != server_mgr_ip and cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                    [tj_constants.SINGLE_MODE]:
                log.error("env_config.ini中server ip配置与测试框架中记录不一致，请检查配置，框架退出!")
            else:
                log.warning("single mode: env_config.ini中client ip配置与测试框架中记录不一致，忽略，继续执行")
            return False

        cur_path = os.path.abspath(os.path.dirname(__file__))
        num_list = re.findall(r'm(\d+)', cur_path)
        if num_list and num_list[0].isdigit():
            vm = int(num_list[0])
        else:
            vm = 999
        log.info("vm:{}".format(vm))
        # ip_b = 160 + (vm // 100) % 10
        ip_b = (vm // 100) % 10
        ip_c = vm % 100
        ip_d = 0
        host_index = 0
        pbk_index = 10
        dbk_index = 10
        env_info_dict = {server_ip: [server_relation_list, CmdExecuteAdressEnum.SERVER.value],
                         client_ip: [client_relation_list, CmdExecuteAdressEnum.CLIENT.value]}
        for target_host_ip, relation_info in env_info_dict.items():
            relation_list = relation_info[0]
            target_execute_address = relation_info[1]

            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and target_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue

            if (target_host_ip == server_ip and cls.server_nic_model == 'windows') or \
                    (target_host_ip == client_ip and cls.client_nic_model == 'windows'):
                env_config_path = tj_constants.WINDOWS_FILE_PATH_ROOT
                root = "Administrator"
                bin_path = env_config_path
            else:
                env_config_path = tj_constants.LINUX_FILE_PATH_ROOT
                root = "root"
                bin_path = "/usr/bin/"

            host_index += 1
            multi_card_dict = {}
            port_index = 100
            for index, device_name in enumerate(relation_list):
                # start 20260122 add by liuxy: 修改ipv4地址第三段中port_index计算方式：设备名最后一个字符(数字) -> (设备名中所有数字+设备名中所有字母asc2码)%254
                # port_index都取server端device name编号
                res_1 = re.findall(r'\d+', server_relation_list[index])
                res_2 = re.findall(r'[a-zA-Z]+', server_relation_list[index])
                # 取所有数字的拼接
                if res_1:
                    number_str = ''.join(res_1)
                else:
                    number_str = server_relation_list[index][-1:]
                number_sum = int(number_str)

                # 取所有字母的asc2码求和
                if res_2:
                    asc2_str = ''.join([i for i in res_2])
                else:
                    asc2_str = ''.join([i for i in ['e', 'n', 'p']])
                asc2_sum = 0
                for str_i in asc2_str:
                    asc2_sum += ord(str_i)%65

                # （字母+数字）% 254
                mark = str((int(number_str) + int(asc2_sum)) % 244)
                # End 20260122 add by liuxy: 修改ipv4地址第三段中port_index计算方式：设备名最后一个字符(数字) -> (设备名中所有数字+设备名中所有字母asc2码)%254

                # 如果出现多卡情况，网口名称会不同，末尾可能一样，这里需要区分
                multi_card_dict[server_relation_list[index][:-1]] = 1
                # if str(mark).isdigit():
                #     port_index = int(mark) + 10 * (len(multi_card_dict) - 1)
                # else:
                #     port_index = pbk_index + 10 * (len(multi_card_dict) - 1)
                #     pbk_index += 1
                port_index += 1

                mark = device_name[-1:]
                if mark.isdigit():
                    device_index = int(mark)
                else:
                    device_index = dbk_index
                    dbk_index += 1

                ip = "192.{}.{}.{}".format(ip_b + port_index, ip_c, ip_d + host_index * 10 + device_index)
                cls.server_ip.append(ip)
                cls.server_nic_name.append(device_name)
                if target_host_ip == server_ip and cls.server_nic_model == 'windows':
                    cmd_code, cmd_outputs, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=f"(get-netadapter -name {device_name}).ifIndex",
                        cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                        ssh_username="Administrator",
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    if cmd_code == 0:
                        cls.server_nic_ifdex.append(re.sub(r"\s+", "", cmd_outputs))
                # 1. 非single mode,非DPDK_AUTO_MODE, server非发包仪
                # 2. 非single mode, client非发包仪
                # 3. single mode, server端
                # 4. 非ncd端口
                # 5. 满足上述条件之一，执行ip配置
                bdf_format = re.findall(r"(\S{2}:\S{2}.\S)", device_name)
                env_test_entry = cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY)
                if (env_test_entry not in [tj_constants.SINGLE_MODE] and target_execute_address == CmdExecuteAdressEnum.SERVER.value and not cls.client_renix_only_flag) or\
                        (env_test_entry not in [tj_constants.SINGLE_MODE] and target_execute_address == CmdExecuteAdressEnum.CLIENT.value and not cls.client_renix_only_flag) or\
                        (env_test_entry in [tj_constants.SINGLE_MODE] and target_execute_address == CmdExecuteAdressEnum.SERVER.value):
                    if bdf_format or device_name.lower() == "none":
                        log.info("NCD==> device_name：{}，不配置ip".format(device_name))
                        pass
                    # Server端设备=publicnet 或 Client端设备=publicnet
                    elif ((target_execute_address == CmdExecuteAdressEnum.SERVER.value) and ('publicnet' in s_c_relation_dict.get(device_name, "None")
                                                                                            or 'publicnet' in device_name)
                          or
                          (target_execute_address == CmdExecuteAdressEnum.CLIENT.value and ('publicnet' in device_name))):
                        log.info("公网设备 ==> device_name：{}，不配置ip".format(device_name))
                        pass
                    else:
                        # 20250611 add by hejf 陈彦利建议修改 5.14内核版本以上通过ifconfig配置ip可能不生效，需添加nmcli connection down dev
                        exec_command = 'nmcli connection down {}'.format(device_name)
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                            ssh_username=f'{root}',
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                        )

                        # 检查是否存在冲突ip
                        # 20260122 add by liuxy 判断当前是否存在同网段的其他IP
                        log.info(f'Start ==> check ip conflict')
                        # 获取当前host中所有网卡的mac、ip信息
                        exec_command = f"ip a"
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command, cmd_execute_address=target_execute_address,
                            ssh_port=str(cls.test_port),
                            ssh_username=f'{root}',
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                        )

                        # 提取当前host中所有网卡已存在的mac地址、ip地址
                        host_if_infos = {}
                        res = re.findall(r'(\S+): \<.*\n', rtn_outputs)
                        for if_name in res:
                            host_if_infos[if_name] = {}
                        for index, if_name in enumerate(host_if_infos.keys()):
                            res = re.findall(rf'{if_name}: \<.*\n\s+link/ether ([\w\:]+).*\n', rtn_outputs)
                            host_if_infos[if_name].update({'mac': []})
                            for mac_addr in res:
                                host_if_infos[if_name]['mac'].append(mac_addr)
                        for index, if_name in enumerate(host_if_infos.keys()):
                            if index+1 < len(list(host_if_infos.keys())):
                                next_if_name = list(host_if_infos.keys())[index+1]
                                res = re.findall(rf'{if_name}: \<.*?\n\s+inet ([\d\.]+).*{next_if_name}: \<', rtn_outputs, flags=re.DOTALL)
                            else:
                                res = re.findall(rf'{if_name}: \<.*?\n\s+inet ([\d\.]+).*', rtn_outputs, flags=re.DOTALL)
                            host_if_infos[if_name].update({'ip': []})
                            for ip_addr in res:
                                if target_execute_address == CmdExecuteAdressEnum.SERVER.value:
                                    if if_name not in server_relation_list:
                                        host_if_infos[if_name]['ip'].append(ip_addr)
                                    else:
                                        host_if_infos[if_name]['ip'].append('ignore')
                                if target_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                                    if if_name not in client_relation_list:
                                        host_if_infos[if_name]['ip'].append(ip_addr)
                                    else:
                                        host_if_infos[if_name]['ip'].append('ignore')
                        # 打印提取的信息
                        # log.info(json.dumps(host_if_infos, indent=4))
                        log.info(host_if_infos)

                        # 测试框架即将配置的ip网段
                        expect_ip_field = '.'.join(ip.split('.')[:-1]) + '.'
                        confilct_ip_list = []
                        # 检查即将配置的ip网段是否已存在
                        for if_name, if_infos in host_if_infos.items():
                            ip_list = if_infos.get('ip', [])
                            for exist_ip in ip_list:
                                if expect_ip_field in exist_ip:
                                    confilct_ip_list.append([if_name, exist_ip])
                        # 打印信息
                        log.info(f'测试框架即将配置的ip: {ip}')
                        log.info(f'环境中已存在的冲突ip: {confilct_ip_list}')

                        # 是否在配置ip后退出测试
                        if confilct_ip_list:
                            log.error(f'{target_execute_address} 存在与测试框架即将配置的ip地址<{ip}>同网段的其他ip地址<{confilct_ip_list}>')
                            stop_test_by_ip_conflict = True
                        else:
                            stop_test_by_ip_conflict = False
                        log.info(f'End ==> check ip conflict')
                        # END 20260122 add by liuxy 判断当前是否存在同网段的其他IP


                        exec_command = "python3 {}esxe.py --ip {} -d '{}'".format(bin_path, ip, device_name)
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                            ssh_username=f'{root}',
                            host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                            host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                        )
                        # log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
                        if "UPDATE_SUCCESS" not in rtn_outputs:
                            log.warning("host:{},{}的网口配置文件更新失败".format(target_host_ip, device_name))
                            return False
                        else:
                            if stop_test_by_ip_conflict:
                                log.error(f'{target_execute_address} 测试框架分配的ip地址<{ip}>与环境中其他ip地址冲突<{confilct_ip_list}>，测试框架退出，请检查环境并消除冲突！')
                                exit(1)

                # 这里获取网口与其BDF值
                exec_command = "ethtool -i '{}'".format(device_name)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=target_execute_address, ssh_port=str(cls.test_port),
                    ssh_username=f'{root}',
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                # bus-info: 0000:4c:00.0
                bdfs = re.findall(r'(\w\w\w\w:\w\w:\w\w.\w)', rtn_outputs)
                if target_execute_address == CmdExecuteAdressEnum.SERVER.value:
                    if bdfs:
                        cls.dev_bdf_list[0][device_name] = bdfs[0]
                    else:
                        cls.dev_bdf_list[0][device_name] = "unknow"
                else:
                    if bdfs:
                        cls.dev_bdf_list[1][device_name] = bdfs[0]
                    else:
                        cls.dev_bdf_list[1][device_name] = "unknow"
        return True

    @classmethod
    def __check_items(cls, test_ip, false_then_exit) -> bool:
        enable_flag = True
        # 检查ethtool工具版本是否满足测试需求
        if not cls.__check_ethtool_version(ssh_ip=test_ip, ssh_port=str(cls.test_port), ssh_username='root'):
            log.error('ethtool版本不满足测试需求')
            enable_flag = False

        # 检查dcbtool工具版本是否满足测试需求
        if not cls.__check_dcb_version(ssh_ip=test_ip, ssh_port=str(cls.test_port), ssh_username='root'):
            log.error('dcbtool版本不满足测试需求')
            enable_flag = False

        # 检查scapy工具版本是否满足测试需求
        if not cls.__check_scapy_version(ssh_ip=test_ip, ssh_port=str(cls.test_port), ssh_username='root'):
            log.error('scapy版本不满足测试需求')
            enable_flag = False

        # 检查md工具是否已安装
        if not cls.__check_md_command_available(ssh_ip=test_ip, ssh_port=str(cls.test_port), ssh_username='root'):
            log.error('md未安装，且重试失败')
            enable_flag = False

        # 检查iperf工具是否已安装
        if not cls.__check_iperf_version(ssh_ip=test_ip, ssh_port=str(cls.test_port), ssh_username='root'):
            log.error('iperf版本不符合预期')
            enable_flag = False

        # 检查iperf3工具是否已安装
        if not cls.__check_iperf3_version(ssh_ip=test_ip, ssh_port=str(cls.test_port), ssh_username='root'):
            log.error('iperf3版本不符合预期')
            enable_flag = False

        # 检查tcpreplay工具是否已安装
        if not cls.__check_tcpreplay_version(ssh_ip=test_ip, ssh_port=str(cls.test_port), ssh_username='root'):
            log.error('tcpreplay版本不符合预期')
            enable_flag = False

        # todo 当前非bug_stop下只做检查不拦截，bug_stop下会直接拦截
        if false_then_exit and cls.frame_run_dict['config_dict'].get(constants.ENV_BUG_STOP):
            log.warning("设置bug_stop情况下，主测环境判定测试工具版本不符合测试要求，后续可能拦截")
            # log.error("设置bug_stop情况下，如果主测环境测试工具版本不符合测试要求，会直接拦截退出测试.")
            # exit(1)
        else:
            enable_flag = True
        return enable_flag

    @classmethod
    def __restart_serial_port_file(cls) -> None:
        if cls.server_nic_model == 'windows':
            return
        server_serial_port_pos, client_serial_port_pos = CommonOperation.get_serial_port_pos()
        if server_serial_port_pos == 'server':
            server_command = "ps -ef | grep minicom | grep tty | grep -v grep | awk '{print $2}' | xargs kill -9"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port))
            log.info(f"{server_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
        elif server_serial_port_pos == 'client':
            if cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]:
                log.info('single mode或发包仪环境，跳过client命令执行')
                return
            client_command = "ps -ef | grep minicom | grep tty | grep -v grep | awk '{print $2}' | xargs kill -9"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                client_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, ssh_port=str(cls.test_port))
            log.info(f"{client_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

    @classmethod
    def __check_ethtool_version(cls, ssh_ip: str = None, ssh_port: str = None, ssh_username: str = None) -> bool:
        rtn_status = False

        exec_command = scripts_constants.STR_SPACE.join([scripts_constants.ETHTOOL, scripts_constants.VERSION])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)

        log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            if rtn_outputs.split('ethtool version ')[1] >= scripts_constants.ETHTOOL_VERSION:
                rtn_status = True
            else:
                log.error(f'ethtool当前版本{rtn_outputs},测试需要版本大于等于{scripts_constants.ETHTOOL_VERSION}')
        else:
            log.error("ethtool 未安装！！！")

        return rtn_status

    @classmethod
    def __check_dcb_version(cls, ssh_ip: str = None, ssh_port: str = None, ssh_username: str = None) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-21
        description:        校验dcbtool版本
        """
        rtn_status = False
        exec_command = scripts_constants.DCBTOOL + scripts_constants.STR_SPACE + '-v'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)

        log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            result_list = rtn_outputs.split('\n')
            if result_list[0].split('dcbtool v')[1] >= scripts_constants.DCBTOOL_VERSION:
                rtn_status = True
            else:
                log.error(f'dcbtool当前版本{result_list[0]},'f'测试需要版本大于等于{scripts_constants.DCBTOOL_VERSION}')
        else:
            log.error("dcbtool 未安装！！！")
            log.info(f'dcbtool安装命令:yum install lldpad')

        return rtn_status

    @classmethod
    def __check_scapy_version(cls, ssh_ip: str = None, ssh_port: str = None, ssh_username: str = None) -> bool:
        """
        author:             junfeng.he
        date:               2023-08-24
        description:        校验scapy版本
        """
        rtn_status = False
        exec_command = "echo 'quit()' | scapy"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)

        log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            if 'Version 2.4.5' in rtn_outputs or 'Version 2.4.5' in rtn_err:
                rtn_status = True
            else:
                log.error(f'scapy版本不是2.4.5，请检查环境重新安装！')
        else:
            log.error("scapy 未安装！！！")
        return rtn_status

    @classmethod
    def __check_md_command_available(cls, ssh_ip: str = None, ssh_port: str = None, ssh_username: str = None) -> bool:
        check_result = False
        exec_command = f'lsmod | grep mem_map'
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
        if rtn_code == RtnStatusEnum.SUCCESS.value and 'mem_map' in rtn_outputs:
            log.info(f'command:{exec_command}, outputs:{rtn_outputs}')
            check_result = True
        else:
            exec_command = 'cd /root/memmap/init_os;chmod +x init_os_env.sh;./init_os_env.sh'
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
            log.info(f'command:{exec_command}, rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
            exec_command = f'lsmod | grep mem_map'
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
            if rtn_code == RtnStatusEnum.SUCCESS.value and 'mem_map' in rtn_outputs:
                check_result = True
            else:
                log.error(f'mem_map不存在，编译失败')
        exec_command = 'md 0x000001'
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
        if "0x" not in rtn_outputs:
            exec_command = "ln -s /root/memmap/starsbox/starsbox /usr/bin/md"
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
            exec_command = "ln -s /root/memmap/starsbox/starsbox /usr/bin/mm"
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
            exec_command = 'md 0x000001'
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
            if "0x" not in rtn_outputs:
                check_result = False
                log.error(f'md不存在，安装失败')
            else:
                check_result = True
                log.info(f'md安装成功')
        else:
            check_result = True
            log.info(f'md安装成功')

        return check_result

    @classmethod
    def __check_iperf3_version(cls, ssh_ip: str = None, ssh_port: str = None, ssh_username: str = None) -> bool:
        """
        author:             xianda.liu
        date:               2022-09-03
        description:        iperf版本校验
        :return:            True/False
        """
        check_flag = False
        exec_command = scripts_constants.STR_SPACE.join([scripts_constants.IPERF, '-v'])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)

        if "iperf 3" in rtn_outputs + rtn_err:
            log.info("{}".format(rtn_outputs + rtn_err))
            check_flag = True
        else:
            log.error("iperf3 未安装！！！")
        return check_flag

    @classmethod
    def __check_iperf_version(cls, ssh_ip: str = None, ssh_port: str = None, ssh_username: str = None) -> bool:
        """
        author:             junfeng.he
        date:               2023-09-12
        description:        iperf版本校验
        :return:            True/False
        """
        check_flag = False
        exec_command = "iperf -v"
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)

        if "iperf version" in rtn_outputs + rtn_err:
            log.info("{}".format(rtn_outputs + rtn_err))
            check_flag = True
        else:
            log.error("iperf 未安装！！！")
        return check_flag

    @classmethod
    def __check_tcpreplay_version(cls, ssh_ip: str = None, ssh_port: str = None, ssh_username: str = None) -> bool:
        """
        author:             junfeng.he
        date:               2023-09-12
        description:        tcpreplay版本校验
        :return:            True/False
        """
        check_flag = False
        exec_command = "tcpreplay -V"
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)

        if "tcpreplay version" in rtn_outputs + rtn_err:
            log.info("{}".format(rtn_outputs + rtn_err))
            check_flag = True
        else:
            log.error("tcpreplay 未安装！！！")
        return check_flag

    @classmethod
    def __check_dkms_install(cls, ssh_ip, cmd_execute_address, host_os_server, host_os_client) -> bool:
        """
        author:             junfeng.he
        date:               2024-01-13
        description:        dkms版本校验
        :return:            True/False
        """
        check_flag = False
        exec_command = "dkms --version"
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, ssh_ip=ssh_ip, ssh_port=str(cls.test_port), cmd_execute_address=cmd_execute_address,
                host_os_server=host_os_server, host_os_client=host_os_client)
        log.info(f"{exec_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
        dkms_verions = re.findall(r"(dkms.+\d\.\d)", rtn_outputs + rtn_err)
        if dkms_verions:
            log.info("{}".format(dkms_verions))
            check_flag = True
        else:
            log.error("dkms 未安装！！！，尝试安装")
            exec_command = "yum install dkms -y"
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, ssh_ip=ssh_ip, ssh_port=str(cls.test_port),
                    cmd_execute_address=cmd_execute_address,
                    host_os_server=host_os_server, host_os_client=host_os_client)
            log.info(f"{exec_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
            exec_command = "dkms --version"
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, ssh_ip=ssh_ip, ssh_port=str(cls.test_port),
                    cmd_execute_address=cmd_execute_address,
                    host_os_server=host_os_server, host_os_client=host_os_client)
            log.info(f"{exec_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
            dkms_verions = re.findall(r"(dkms[:-]\d\.\d)", rtn_outputs + rtn_err)
            if dkms_verions:
                log.info("{}".format(dkms_verions))
                check_flag = True
            else:
                log.error("dkms 未安装成功！！！")

        return check_flag

    @classmethod
    def __update_com_mode(cls) -> None:
        """
        author:             junfeng.he
        date:               2026-03-26
        description:        融合模式测试: pf: 仅内核0，共存2；vf 仅内核0，仅dpdk1，共存2
                            以太测试时需遍历 pf 0 * vf 0， 2
                                          pf 2 * vf 0， 2
        :return:            True/False
        """
        custom_params = cls.frame_run_dict['config_dict'].get(constants.ENV_CUSTOM_PARAMS, "None")
        server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        server_driver_name, client_driver_name = CommonOperation.get_nic_driver_name()
        target_execute_address = CmdExecuteAdressEnum.SERVER.value
        # vf 不能取dpdk only
        normal_list = [0, 2]
        now = datetime.datetime.now()
        # 如果日期是 偶数则pf com_mode设成0仅内核模式；奇数则pf com_mode设成2共存模式
        pf_co_mode = normal_list[now.day % 2]
        # 如果当前小时是 偶数则vf com_mode设成0仅内核模式；奇数则vf com_mode设成2共存模式
        vf_co_mode = normal_list[now.hour % 2]
        if server_driver_name == NicNameEnum.SXE2.value:
            values = re.findall(rf"{constants.CUSTOM_PARAMS_PF_CO_MODE}=(\d+)", custom_params)
            if values:
                pf_co_mode = int(values[0])
            else:
                log.info(f"除了0,2的其他指定，则按触发日期{now.day}%2取值,pf_co_mode:{pf_co_mode}")

            values = re.findall(rf"{constants.CUSTOM_PARAMS_VF_CO_MODE}=(\d+)", custom_params)
            if values:
                vf_co_mode = int(values[0])
            else:
                log.info(f"除了0,2的指定，则按触发小时{now.hour}%2取值,vf_co_mode:{vf_co_mode}")

            if cls.frame_run_dict['config_dict'].get(
                    constants.ENV_TEST_OBJECT) in [constants.ENV_RUN_MODE_WITH_RPM,
                                                   constants.ENV_RUN_MODE_WITH_SRPM,
                                                   constants.ENV_RUN_MODE_WITH_KMOD_SRPM]:
                run_mode = 12
            else:
                run_mode = 10

            log.info(f"融合架构目标pf_co_mode:{pf_co_mode}， vf_co_mode：{vf_co_mode}")
            CommonOperation.set_com_mode("pf", pf_co_mode, target_execute_address)
            CommonOperation.set_once_com_mode("pf", pf_co_mode, target_execute_address)
            CommonOperation.set_com_mode("vf", vf_co_mode, target_execute_address)
            CommonOperation.set_once_com_mode("vf", vf_co_mode, target_execute_address)
            DpdkCommonUtils.driver_integration_check_and_ready(target_execute_address, server_driver_name,
                                                               pf_co_mode,
                                                               vf_co_mode, run_mode=run_mode)
            if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.VF_KEEP_MODE]:
                # server端每个pf创建6个vf
                vf_num = 6
                server_device_list, client_device_list = CommonOperation.get_nic_relationships(
                    scripts_constants.NIC_CONFIG_BK_PATH)
                for server_pf_device_name in server_device_list:
                    CommonOperation.generate_vf_device(pf_device_name=server_pf_device_name, vf_num=0,
                                                       cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    CommonOperation.generate_vf_device(pf_device_name=server_pf_device_name, vf_num=vf_num,
                                                       cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        else:
            CommonOperation.set_com_mode("pf", "", target_execute_address)
            CommonOperation.set_once_com_mode("pf", "", target_execute_address)
            CommonOperation.set_com_mode("vf", "", target_execute_address)
            CommonOperation.set_once_com_mode("vf", "", target_execute_address)
        # client当前都走共存
        CommonOperation.set_com_mode("pf", 2, CmdExecuteAdressEnum.CLIENT.value)
        CommonOperation.set_once_com_mode("pf", 2, CmdExecuteAdressEnum.CLIENT.value)
        CommonOperation.set_com_mode("vf", 2, CmdExecuteAdressEnum.CLIENT.value)
        CommonOperation.set_once_com_mode("vf", 2, CmdExecuteAdressEnum.CLIENT.value)


    @classmethod
    def __check_log_repeat(cls) -> str:
        """
        author:             junfeng.he
        date:               2024-01-13
        description:        dkms版本校验
        :return:            True/False
        """
        desc = ""
        custom_params = cls.frame_run_dict['config_dict'].get(constants.ENV_CUSTOM_PARAMS, "None")
        if constants.CUSTOM_PARAMS_NOT_CHECK_LOG in custom_params or cls.framework_log_check_ignore:
            return desc

        # 1. 重复日志检查
        # 时间窗 s
        repeat_time_window = 10
        # 重复条数阈值
        repeat_threshold = 10

        # 2.trace id检查
        trace_id_threshold = 100

        server_driver_name, client_driver_name = CommonOperation.get_nic_driver_name()
        server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)

        # 串口
        server_com, client_com = CommonOperation.get_serial_port_pos()
        if '@' in server_com and '_' in server_com:
            server_com_ip = server_com.split('_')[1]
            server_com_port = server_com.split('_')[-1]
        else:
            server_com_ip = 'None'
            server_com_port = 'None'
        if '@' in client_com and '_' in client_com:
            client_com_ip = client_com.split('_')[1]
            client_com_port = client_com.split('_')[-1]
        else:
            client_com_ip = 'None'
            client_com_port = 'None'

        for target_host_info in [[server_mgr_ip, CmdExecuteAdressEnum.SERVER.value, server_driver_name, "server"],
                                 [client_mgr_ip, CmdExecuteAdressEnum.CLIENT.value, client_driver_name, "client"]]:
            target_host_ip = target_host_info[0]
            target_execute_address = target_host_info[1]
            target_driver_name = target_host_info[2]
            target_mark = target_host_info[3]

            # release_version = False
            # exec_command = f'cat /root/sxetest/publish_version/release_version.txt'
            # cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            #     cmd=exec_command, ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
            #     cmd_execute_address=target_execute_address, print_steps=True, print_outputs=True)
            # if "makemode:release" in cmd_output:
            #     release_version = True
            # if not release_version:
            #     # todo 当前只检查release版本，后续需要修改
            #     continue
            for log_file in ["/var/log/messages", "/var/log/dmesg",
                             # "/home/minicom_log", # todo 待转测
                             # "/var/log/scgbe.log", "/var/log/scgbevf.log", # 20250909 与研发对齐，驱动日志非release给用户，不再作检查
                             # "/var/log/scgbepmd.log", "/var/log/scgbevfpmd.log", # todo 待转测
                             # "/var/log/scgbe_drv_rdma.log", "/var/log/scgbe_rdma_file", # 20250909 与研发对齐，驱动日志非release给用户，不再作检查
                            ]:
                if target_driver_name in [NicNameEnum.SXE2.value, NicNameEnum.SCGBE.value]:
                    if "minicom_log" in log_file:
                        # 日志服务器ip
                        log_server_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_LOG_SERVER_IP)
                        # 日志服务器 用户
                        log_server_account = cls.frame_run_dict['ip_dict'].get(constants.ENV_LOG_SERVER_ACCOUNT,
                                                                                    constants.ENV_LOG_SERVER_ACCOUNT_FRAMEWORK)
                        local_log = f"/home/minicom_log_{target_mark}/"
                        # com_ip = cls.frame_run_dict['ip_dict'].get(f'{target_mark}_com_ip', 'None')
                        # com_port = cls.frame_run_dict['ip_dict'].get(f'{target_mark}_com_port', 'None')
                        if target_mark == 'server':
                            com_ip = server_com_ip
                            com_port = server_com_port
                        else:
                            com_ip = client_com_ip
                            com_port = client_com_port
                        try:
                            exec_command = f"rm -rf {local_log};mkdir {local_log}"
                            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command, ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                cmd_execute_address=target_execute_address, print_steps=True, print_outputs=True)
                            days = 1 + (int(time.time()) - cls.framework_log_check_start_time)//86400
                            for i in range(days):
                                day = time.strftime("%Y-%m-%d", time.localtime(time.time() - i * 86400))
                                source_log_file = f"{constants.COM_LOG_DIR}/{com_ip}/{com_port}/com_log_{com_ip}_{com_port}_{day}.log"
                                log_file = f'{local_log}/{target_mark}_com_log_{com_ip}_{com_port}_{day}.log'
                                FileOperation.scp_file(source_file_path=source_log_file, target_file_path=log_file,
                                                       source_username=log_server_account, source_ip=log_server_ip,
                                                       target_ip=target_host_ip, target_port=str(cls.test_port))

                                exec_command = (f"python3 /usr/bin/esxe.py -p {log_file} "
                                                f"-a '{cls.framework_log_check_start_time}@{repeat_time_window}@{repeat_threshold}@{trace_id_threshold}'")
                                cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=exec_command, ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                    cmd_execute_address=target_execute_address, print_steps=True, print_outputs=True)
                                if "检测出问题" in cmd_output and "检测出问题 0 处" not in cmd_output:
                                    desc += f"{log_file}存在日志重复或超限打印问题；"
                        except:
                            log.error("固件日志解析失败！！")
                    elif (f"{cls.nicg}.log" in log_file or f"{cls.nicg}vf.log" in log_file or f"{cls.nicg}pmd.log" in log_file or
                          f"{cls.nicg}vfpmd.log" in log_file or f"{cls.nicg}_drv_rdma.log" in log_file or f"{cls.nicg}_rdma_file.log" in log_file):
                        # 获取时间窗内的日志文件列表
                        log_file_list = []
                        if f"{cls.nicg}.log" in log_file:
                            exec_command = f"ls /var/log/{cls.nicg}.log* | sort -nr"
                            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command, ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                cmd_execute_address=target_execute_address, print_steps=False, print_outputs=False)
                            file_list = cmd_output.split("\n")
                            for file_path in file_list:
                                # /var/log/scgbe.log.2025-07-22_07:48:16
                                time_infos = re.findall(r'(\d{4}-\d{2}-\d{2}_\d{2}:\d{2}:\d{2})', file_path)
                                if time_infos:
                                    log_file_list.append(file_path)
                                    try:
                                        time_stamp = int(
                                            datetime.datetime.strptime(time_infos[0], "%Y-%m-%d_%H:%M:%S").timestamp())
                                    except:
                                        log.error("日志时间解析失败，只取最后一个日志文件")
                                        time_stamp = cls.framework_log_check_start_time
                                    if cls.framework_log_check_start_time >= time_stamp:
                                        break
                        elif f"{cls.nicg}vf.log" in log_file:
                            exec_command = f"ls /var/log/{cls.nicg}vf.log* | sort -nr"
                            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command, ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                cmd_execute_address=target_execute_address, print_steps=False, print_outputs=False)
                            file_list = cmd_output.split("\n")
                            for file_path in file_list:
                                # /var/log/scgbevf.log.2025-07-22_08:22:04
                                time_infos = re.findall(r'(\d{4}-\d{2}-\d{2}_\d{2}:\d{2}:\d{2})', file_path)
                                if time_infos:
                                    log_file_list.append(file_path)
                                    try:
                                        time_stamp = int(
                                            datetime.datetime.strptime(time_infos[0], "%Y-%m-%d_%H:%M:%S").timestamp())
                                    except:
                                        log.error("日志时间解析失败，只取最后一个日志文件")
                                        time_stamp = cls.framework_log_check_start_time
                                    if cls.framework_log_check_start_time >= time_stamp:
                                        break
                        elif f"{cls.nicg}pmd.log" in log_file:
                            exec_command = f"ls /var/log/{cls.nicg}pmd.log* | sort -nr"
                            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command, ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                cmd_execute_address=target_execute_address, print_steps=False, print_outputs=False)
                            file_list = cmd_output.split("\n")
                            for file_path in file_list:
                                # /var/log/scgbepmd.log.2025-07-22-04:21:16
                                time_infos = re.findall(r'(\d{4}-\d{2}-\d{2}-\d{2}:\d{2}:\d{2})', file_path)
                                if time_infos:
                                    log_file_list.append(file_path)
                                    try:
                                        time_stamp = int(datetime.datetime.strptime(time_infos[0], "%Y-%m-%d-%H:%M:%S").timestamp())
                                    except:
                                        log.error("日志时间解析失败，只取最后一个日志文件")
                                        time_stamp = cls.framework_log_check_start_time
                                    if cls.framework_log_check_start_time >= time_stamp:
                                        break
                        elif f"{cls.nicg}vfpmd.log" in log_file:
                            exec_command = f"ls /var/log/{cls.nicg}vfpmd.log* | sort -nr"
                            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command, ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                cmd_execute_address=target_execute_address, print_steps=False, print_outputs=False)
                            file_list = cmd_output.split("\n")
                            for file_path in file_list:
                                # /var/log/scgbevfpmd.log.2025-07-22-04:21:16
                                time_infos = re.findall(r'(\d{4}-\d{2}-\d{2}-\d{2}:\d{2}:\d{2})', file_path)
                                if time_infos:
                                    log_file_list.append(file_path)
                                    try:
                                        time_stamp = int(datetime.datetime.strptime(time_infos[0], "%Y-%m-%d-%H:%M:%S").timestamp())
                                    except:
                                        log.error("日志时间解析失败，只取最后一个日志文件")
                                        time_stamp = cls.framework_log_check_start_time
                                    if cls.framework_log_check_start_time >= time_stamp:
                                        break
                        elif f"{cls.nicg}_drv_rdma.log" in log_file:
                            exec_command = f"ls /var/log/{cls.nicg}_drv_rdma.log* | sort -nr"
                            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command, ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                cmd_execute_address=target_execute_address, print_steps=False, print_outputs=False)
                            file_list = cmd_output.split("\n")
                            for file_path in file_list:
                                # /var/log/scgbe_drv_rdma.log.2025-07-24_12:55:12
                                time_infos = re.findall(r'(\d{4}-\d{2}-\d{2}_\d{2}:\d{2}:\d{2})', file_path)
                                if time_infos:
                                    log_file_list.append(file_path)
                                    try:
                                        time_stamp = int(
                                            datetime.datetime.strptime(time_infos[0], "%Y-%m-%d_%H:%M:%S").timestamp())
                                    except:
                                        log.error("日志时间解析失败，只取最后一个日志文件")
                                        time_stamp = cls.framework_log_check_start_time
                                    if cls.framework_log_check_start_time >= time_stamp:
                                        break
                        elif f"{cls.nicg}_rdma_file" in log_file:
                            exec_command = f"ls /var/log/{cls.nicg}_rdma_file_current.log"
                            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command, ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                cmd_execute_address=target_execute_address, print_steps=False, print_outputs=False)
                            if f"{cls.nicg}_rdma_file_current.log" in cmd_output:
                                log_file_list.append(f"/var/log/{cls.nicg}_rdma_file_current.log")

                                exec_command = f"ls /var/log/{cls.nicg}_rdma_file* | sort -nr"
                                cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=exec_command, ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                    cmd_execute_address=target_execute_address, print_steps=False, print_outputs=False)
                                file_list = cmd_output.split("\n")
                                for file_path in file_list:
                                    # /var/log/scgbe_rdma_file_2025_07_24-20_40_49.491894.log
                                    time_infos = re.findall(r'(\d{4}_\d{2}_\d{2}-\d{2}_\d{2}_\d{2})', file_path)
                                    if time_infos:
                                        log_file_list.append(file_path)
                                        try:
                                            time_stamp = int(
                                                datetime.datetime.strptime(time_infos[0], "%Y_%m_%d-%H_%M_%S").timestamp())
                                        except:
                                            log.error("日志时间解析失败，只取最后一个日志文件")
                                            time_stamp = cls.framework_log_check_start_time
                                        if cls.framework_log_check_start_time >= time_stamp:
                                            break


                        for cur_log_file in log_file_list:
                            exec_command = (f"python3 /usr/bin/esxe.py -p {cur_log_file} "
                                            f"-a '{cls.framework_log_check_start_time}@{repeat_time_window}@{repeat_threshold}@{trace_id_threshold}'")
                            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command, ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                cmd_execute_address=target_execute_address, print_steps=True, print_outputs=True)
                            if "检测出问题" in cmd_output and "检测出问题 0 处" not in cmd_output:
                                desc += f"{cur_log_file}存在日志重复或超限打印问题；"
                    else:
                        if "dmesg" in log_file:
                            exec_command = f"dmesg -xT > {log_file}"
                            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=exec_command, ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                                cmd_execute_address=target_execute_address, print_steps=True, print_outputs=True)

                        exec_command = (f"python3 /usr/bin/esxe.py -p {log_file} "
                                        f"-a '{cls.framework_log_check_start_time}@{repeat_time_window}@{repeat_threshold}@{trace_id_threshold}'")
                        cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=exec_command, ssh_ip=target_host_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=target_execute_address, print_steps=True, print_outputs=True)
                        if "检测出问题" in cmd_output and "检测出问题 0 处" not in cmd_output:
                            desc += f"{log_file}存在日志重复或超限打印问题；"

        return desc

    @classmethod
    def __synchronize_peer_time(cls) -> None:
        """
        author:      junfeng.he
        date:        2023-09-05 15:34:55
        description: 同步对端时间
        :return:     None
        """
        if cls.server_nic_model == 'windows' or cls.client_nic_model == 'windows':
            return
        if cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]:
            log.info('single mode或发包仪环境，跳过client命令执行')
            return
        log.info("脚本测试前->同步对端时间")
        server_command = "timedatectl set-timezone Asia/Shanghai"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port))
        log.info(f"{server_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

        client_command = "timedatectl set-timezone Asia/Shanghai"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            client_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, ssh_port=str(cls.test_port))
        log.info(f"{client_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

        server_command = "date +%s"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port))
        log.info(f"{server_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
        server_timestamp = rtn_outputs

        client_command = "date +%s"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            client_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, ssh_port=str(cls.test_port))
        log.info(f"{client_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
        client_timestamp = rtn_outputs

        if server_timestamp.isdigit() and client_timestamp.isdigit() and \
                ((int(server_timestamp) > int(client_timestamp) + 180) or
                 (int(server_timestamp) < int(client_timestamp) - 180)):
            log.warning("本端与对端时间差大于180s，执行本端同步对端时间。")

            client_command = "date"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                client_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, ssh_port=str(cls.test_port))
            log.info(f"{client_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
            client_time = rtn_outputs

            server_command = "date --set='{}'".format(client_time)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port))
            log.info(f"{server_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

    @classmethod
    def __check_env_config(cls) -> bool:
        """
        author:      junfeng.he
        date:        2025-11-14 15:34:55
        description: 检查env_config.ini 与 ps3server 配置的节点信息ip是否一致
        :return:     None
        """
        server_ip = cls.frame_run_dict["ip_dict"]["server_ip"]
        client_ip = cls.frame_run_dict["ip_dict"]["client_ip"]
        config = configparser.ConfigParser()
        config.read(scripts_constants.NIC_CONFIG_BK_PATH)
        server_nic_logical_ip, client_nic_logical_ip = config['logical_ip']['server'], config['logical_ip']['client']

        log.warning(f"     ps3server-server:{server_ip}")
        log.warning(f"env_config.ini-server:{server_nic_logical_ip}")
        log.warning(f"     ps3server-server:{client_ip}")
        log.warning(f"env_config.ini-server:{client_nic_logical_ip}")
        if server_ip != server_nic_logical_ip or client_nic_logical_ip not in [client_ip, server_ip]:
            return False
        return True

    @classmethod
    def auto_log_check(cls) -> None:
        """
        author:      junfeng.he
        date:        2026-03-11 15:34:55
        description: 检查是否是release版本，是则开启日志自动导出功能
        :return:     None
        """
        config = configparser.ConfigParser()
        config.read(scripts_constants.NIC_CONFIG_BK_PATH)
        server_serial_info, client_serial_info = config['serial_port_pos']['server'], config['serial_port_pos']['client']
        client_nic_driver = config['nic_driver']['client'].split(",")[0]
        for execute_address in [CmdExecuteAdressEnum.SERVER.value, CmdExecuteAdressEnum.CLIENT.value]:
            if ((("developer@" not in server_serial_info) and ("framework@" not in server_serial_info) and execute_address == CmdExecuteAdressEnum.SERVER.value) or
                    (("developer@" not in client_serial_info) and ("framework@" not in client_serial_info) and
                     execute_address == CmdExecuteAdressEnum.CLIENT.value and cls.nicg in client_nic_driver)):
                log.info("==> 未配置串口交换机信息，开启固件日志自动导出功能")
                server_command = f"{cls.nicg}cli -d all set autologoutput state=on"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    server_command, cmd_execute_address=execute_address, ssh_port=str(cls.test_port))
            elif ((execute_address == CmdExecuteAdressEnum.SERVER.value) or
                  (execute_address == CmdExecuteAdressEnum.CLIENT.value and cls.nicg in client_nic_driver)):
                server_command = f"{cls.nicg}cli -d all custom sxe2 fwinfo"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    server_command, cmd_execute_address=execute_address, ssh_port=str(cls.test_port))
                if "build mode = release" in rtn_outputs:
                    log.info("==> release版本，开启固件日志自动导出功能")
                    server_command = f"{cls.nicg}cli -d all set autologoutput state=on"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        server_command, cmd_execute_address=execute_address, ssh_port=str(cls.test_port))
                else:
                    server_command = f"{cls.nicg}cli -d all set autologoutput state=off"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        server_command, cmd_execute_address=execute_address, ssh_port=str(cls.test_port))


    @classmethod
    def __check_mac_is_available(cls) -> bool:
        """
        author:      junfeng.he
        date:        2025-11-14 15:34:55
        description: 检查env_config.ini 与 ps3server 配置的节点信息ip是否一致
        :return:     None
        """
        need_config = False
        config = configparser.ConfigParser()
        config.read(scripts_constants.NIC_CONFIG_BK_PATH)
        server_relations, client_relations = config['relationships']['server'], config['relationships']['client']
        server_platfrom, client_platfrom = config['platform']['server'], config['platform']['client']

        ncd_dev = re.findall(r"(\S{4}:\S{2}:\S{2}.\S)", server_relations)
        if ncd_dev:
            log.info("NCD不检查mac")
            return True

        server_nic_driver = config['nic_driver']['server'].split(",")[0]
        if server_nic_driver not in ['sxe2', 'sxe3']:
            log.info("非sxe2、sxe3不检查mac")
            return True

        server_command = f"{cls.nicg}cli show"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port))
        bdfs = re.findall(r"\s+\|(\S\S\S\S:\S\S:\S\S.\S)", rtn_outputs)
        cli_macs = re.findall(r"\s+\|(\S\S:\S\S:\S\S:\S\S:\S\S:\S\S)", rtn_outputs)
        if bdfs:
            server_command = f"{cls.nicg}cli -d {bdfs[0]} show mfginfo"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port))
            macs = re.findall(r"\|Mac Address \d\s+\|(\S\S:\S\S:\S\S:\S\S:\S\S:\S\S)", rtn_outputs)
            if macs:
                for mac in macs:
                    if mac == "00:00:00:00:00:00":
                        log.warning("mfg查询存在mac全0！！！")
                        need_config = True
                        break
                for mac in cli_macs:
                    if mac == "00:00:00:00:00:00":
                        log.warning("cli查询存在mac全0！！！")
                        need_config = True
                        break
            else:
                log.warning("未查询到mac信息！！！")
                need_config = True
        else:
            log.error("cli未查询到有效device，请检查环境！！！")
            return False

        if need_config:
            if bdfs:
                dev = bdfs[0]
            else:
                dev = "all"

            if 'fpga' in server_platfrom.lower():
                server_command = f"{cls.nicg}cli -d {dev} download mfg file=/root/sxetest/publish_version/debuginfo/{cls.nicg}_fw_fpga/debug/mfg.bin"
            else:
                server_command = f"{cls.nicg}cli -d {dev} download mfg file=/root/sxetest/publish_version/debuginfo/{cls.nicg}_fw_asic/debug/mfg.bin"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port))
            if "ERRNO_I2C_ADDR_NOACK" in rtn_outputs + rtn_err:
                log.warning("出现eeprom地址无响应问题，重新修正eeprom地址重试")
                if "evb" in server_platfrom.lower():
                    server_command = f"{cls.nicg}cli -d {dev} custom {cls.nicg} eepromaddrset addr=0x54"
                else:
                    server_command = f"{cls.nicg}cli -d {dev} custom {cls.nicg} eepromaddrset addr=0x51"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port))

                server_command = f"{cls.nicg}cli -d {dev} reset type=0"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port))
                time.sleep(30)

                server_command = f"rmmod {cls.nicg}"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port))
                time.sleep(1)
                server_command = f"insmod /root/{cls.nicg}_auxiliary.ko;insmod /root/{cls.nicg}.ko"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port))
                time.sleep(5)

                if 'fpga' in server_platfrom.lower():
                    server_command = f"{cls.nicg}cli -d {dev} download mfg file=/root/sxetest/publish_version/debuginfo/{cls.nicg}_fw_fpga/debug/mfg.bin"
                else:
                    server_command = f"{cls.nicg}cli -d {dev} download mfg file=/root/sxetest/publish_version/debuginfo/{cls.nicg}_fw_asic/debug/mfg.bin"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port))

            factor = str(random.randint(10, 99))
            if len(bdfs) == 1:
                server_command = f"{cls.nicg}cli -d {dev} set mfginfo  pv=pv macAddr0=12345678{factor}00"
            elif len(bdfs) == 2:
                server_command = f"{cls.nicg}cli -d {dev} set mfginfo  pv=pv macAddr0=12345678{factor}00 macAddr1=12345678{factor}11"
            else:
                server_command = f"{cls.nicg}cli -d {dev} set mfginfo  pv=pv macAddr0=12345678{factor}00 macAddr1=12345678{factor}11 macAddr2=12345678{factor}22 macAddr3=12345678{factor}33"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port))

            server_command = f"rmmod {cls.nicg}"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port))
            time.sleep(1)
            server_command = f"insmod /root/{cls.nicg}_auxiliary.ko；insmod /root/{cls.nicg}.ko"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port))
            time.sleep(3)

            server_command = f"{cls.nicg}cli -d {dev} show mfginfo"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port))
            macs = re.findall(r"|Mac Address \d   |(\S\S:\S\S:\S\S:\S\S:\S\S:\S\S)", rtn_outputs)
            if macs:
                for mac in macs:
                    if mac == "00:00:00:00:00:00":
                        log.error("升级mfg.bin和配置mfginfo后查询，仍然查询到全0mac信息")
                        return False
            else:
                log.error("升级mfg.bin和配置mfginfo后查询，仍然没有查询到mac信息")
                return False
        return True

    @classmethod
    def __synchronize_ps3server_time(cls) -> None:
        """
        author:      junfeng.he
        date:        2025-08-05 15:34:55
        description: 同步测试服务器时间
        :return:     None
        """
        if cls.server_nic_model == 'windows' or cls.client_nic_model == 'windows':
            return
        if cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]:
            log.info('single mode或发包仪环境，跳过client命令执行')
            return

        log.info("脚本测试前->同步ps3server时间")
        for execute_address in [CmdExecuteAdressEnum.SERVER.value, CmdExecuteAdressEnum.CLIENT.value]:

            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue

            server_command = "timedatectl set-timezone Asia/Shanghai"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, cmd_execute_address=execute_address, ssh_port=str(cls.test_port))
            log.info(f"{server_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

            server_command = "date +%s"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, local_execute_flag=True)
            log.info(f"{server_command},rtn_code:{rtn_code}, ps3server 时间戳:{rtn_outputs}, rtn_err:{rtn_err}")
            server_timestamp = rtn_outputs

            if server_timestamp.isdigit():
                server_command = "date -s '@{}'".format(server_timestamp)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    server_command, cmd_execute_address=execute_address, ssh_port=str(cls.test_port))
                log.info(f"{server_command},rtn_code:{rtn_code}, 更新时间:{rtn_outputs}, rtn_err:{rtn_err}")

    @classmethod
    def __force_clear_env_vf_vlan(cls) -> None:
        """
        author:      junfeng.he
        date:        2023-09-05 15:34:55
        description: 清理vf vlan
        :return:     None
        """
        # command = f"cat /root/sxetest/vf_support_status"
        # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
        #     cmd=command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'root',
        #     ssh_port=str(cls.test_port),
        #     host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
        #     host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        # )
        # if "support_vf_remove" not in rtn_outputs:
        #     log.warning("脚本测试前->强制进行vf，vlan清理, vf还不支持卸载，此步骤不执行！！")
        #     return
        # else:
        #     log.warning("vf支持卸载，但是需要卸载vf驱动！！")
        #     command = f"rmmod scgbevf"
        #     rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
        #         cmd=command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_username=f'root',
        #         ssh_port=str(cls.test_port),
        #         host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
        #         host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        #     )

        log.info("脚本测试前->强制进行vf，vlan清理")
        server_relation_list, client_relation_list = CommonOperation.get_nic_relationships()

        if 'none' in server_relation_list or 'none' in client_relation_list:
            log.warning("env_config.ini中网口关系配置中存在none，无法进行vf，vlan清理")
            return

        env_info_dict = {CmdExecuteAdressEnum.SERVER.value: server_relation_list,
                         CmdExecuteAdressEnum.CLIENT.value: client_relation_list}
        for cmd_execute_address, relation_list in env_info_dict.items():
            if cls.server_nic_model == 'windows' and cmd_execute_address == CmdExecuteAdressEnum.SERVER.value or \
                    cls.client_nic_model == 'windows' and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                continue
            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue
            for index, device_name in enumerate(relation_list):
                if cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) not in [tj_constants.VF_KEEP_MODE]:
                    log.info("删除{}的vf".format(device_name))
                    result_dict = EthtoolOperation.show_driver_infomation(device_name=device_name,
                                                                          cmd_execute_address=cmd_execute_address,
                                                                          test_port=cls.test_port)
                    if 'bus-info' not in result_dict.keys():
                        continue
                    pci_num = result_dict['bus-info']
                    command = f"echo 0 > /sys/bus/pci/devices/{pci_num}/sriov_numvfs"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                        ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                        timeout=300
                    )
                    log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                    log.info("删除{}的vf ip配置文件".format(device_name))
                    command = f"rm -rf /etc/sysconfig/network-scripts/ifcfg-{device_name}v*"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                        ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

                command = f"ip a | grep '@{device_name}:'"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                    ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                # log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                vlan_name_list = re.findall(r'(\S*)@{}:'.format(device_name), rtn_outputs)
                for vlan_name in vlan_name_list:
                    log.info("删除{}的vlan:{}".format(device_name, vlan_name))
                    command = f"ip link del {vlan_name}"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                        ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

                command = f"ip a | grep -w {device_name}"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                    ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                pf_ips = re.findall(r"(inet 192.)", rtn_outputs)
                if len(pf_ips) > 1:
                    log.info("清除pf临时ip")
                    command = f"ip addr flush dev {device_name}"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                        ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                    command = f"ifdown {device_name}"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                        ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                    command = f"ifup {device_name}"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                        ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

    @classmethod
    def __force_clear_dcb(cls) -> None:
        """
        author:      junfeng.he
        date:        2023-09-05 15:34:55
        description: 关闭dcb
        :return:     None
        """
        if cls.server_nic_model == 'windows' or cls.client_nic_model == 'windows':
            return
        log.info("脚本测试前->关闭dcb")
        server_relation_list, client_relation_list = CommonOperation.get_nic_relationships()

        if 'none' in server_relation_list or 'none' in client_relation_list:
            log.warning("env_config.ini中网口关系配置中存在none，无法进行dcb关闭")
            return

        env_info_dict = {CmdExecuteAdressEnum.SERVER.value: server_relation_list,
                         CmdExecuteAdressEnum.CLIENT.value: client_relation_list}
        for cmd_execute_address, relation_list in env_info_dict.items():

            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                continue

            command = "dcb -V"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
            if "iproute2" in rtn_outputs:
                log.info("环境已升级成dcb工具，无需再维护dcbtool配置，框架直接disable lldpad")
                command = "systemctl stop lldpad"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                    ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                command = "systemctl disable lldpad"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                    ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                continue

            command = "systemctl status lldpad"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            if "(running)" not in rtn_outputs:
                command = "systemctl restart lldpad"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                    ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                time.sleep(2)

            command = "dcbtool gc dcbx"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                ssh_port=str(cls.test_port),
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            if "DCBXVersion:CEE" not in rtn_outputs.replace(" ", ""):
                command = "dcbtool sc dcbx v:cee"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                    ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                command = "systemctl restart lldpad"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                    ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                time.sleep(2)
            for index, device_name in enumerate(relation_list):
                command = "dcbtool gc {} dcb".format(device_name)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                    ssh_port=str(cls.test_port),
                    host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                )
                log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                if "on" in rtn_outputs and "off" not in rtn_outputs:
                    log.info("关闭{}的dcb".format(device_name))
                    command = "lldptool -T  -i {} -V  ETS-CFG up2tc=0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0 " \
                              "tcbw=100,0,0,0,0,0,0,0".format(device_name)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                        ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                    command = "dcbtool sc {} dcb off".format(device_name)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root',
                        ssh_port=str(cls.test_port),
                        host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
                    )
                    log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

    @classmethod
    def __config_core_dump(cls, target: str = "all") -> None:
        """
        author:      junfeng.he
        date:        2023-09-013 15:34:55
        description: 同步对端时间
        :return:     None
        """
        server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)

        if cls.server_nic_model != 'windows' and target != "client":
            cmd_execute_address = CmdExecuteAdressEnum.SERVER.value
            cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
            server_command = "mkdir /home/nic_core/"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=server_command, cmd_execute_address=cmd_execute_address,
                ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port), ssh_username=f'root',
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )

            server_command = "ulimit -c unlimited"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=server_command, cmd_execute_address=cmd_execute_address,
                ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port), ssh_username=f'root',
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )

            server_command = "echo '/home/nic_core/core-%e-%p-%t' > /proc/sys/kernel/core_pattern"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=server_command, cmd_execute_address=cmd_execute_address,
                ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port), ssh_username=f'root',
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )

        if cls.client_nic_model != 'windows' and target != "server":
            cmd_execute_address = CmdExecuteAdressEnum.CLIENT.value

            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                return

            server_command = "mkdir /home/nic_core/"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=server_command, cmd_execute_address=cmd_execute_address,
                ssh_ip=client_mgr_ip, ssh_port=str(cls.test_port), ssh_username=f'root',
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f"{server_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

            server_command = "ulimit -c unlimited"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=server_command, cmd_execute_address=cmd_execute_address,
                ssh_ip=client_mgr_ip, ssh_port=str(cls.test_port), ssh_username=f'root',
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f"{server_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

            server_command = "echo '/home/nic_core/core-%e-%p-%t' > /proc/sys/kernel/core_pattern"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=server_command, cmd_execute_address=cmd_execute_address,
                ssh_ip=client_mgr_ip, ssh_port=str(cls.test_port), ssh_username=f'root',
                host_os_server=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
            )
            log.info(f"{server_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

    @classmethod
    def __enable_background_traffic(cls, enable_bt: bool = False,
                                    server_mgr_ip: str = "", client_mgr_ip: str = "",
                                    server_device_ip: str = "", client_device_ip: str = "",
                                    server_host_os: str = None, client_host_os: str = None,
                                    run_time: int = 1800) -> None:
        """
        author:      junfeng.he
        date:        2023-09-013 15:34:55
        description: 给第一个端口使用iperf打上背景流量
        :return:     None
        """
        log.info("__enable_background_traffic->enable_bt: {}".format(enable_bt))
        product_name = cls.nicg
        if enable_bt:
            # 删除只保留100个
            server_command = "df -h"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port))
            log.info(f"{server_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
            file_list = [
                f'/var/log/{product_name}.bin.*',
                f'/var/log/{product_name}.log.*',
                f'/var/log/{product_name}vf.bin.*',
                f'/var/log/{product_name}vf.log.*',
            ]
            for files in file_list:
                server_command = f"ls {files} | sort -nr |sed -n '50,$p' " + r"| xargs rm -fr {}"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    server_command, ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port))
                log.info(rtn_outputs)
            server_command = "df -h"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port))
            log.info(f"{server_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

        iperf_bt_daemon_path = "/root/sxetest/iperf_bt_daemon.py"
        server_command = "ps -ef | grep 'python3 {}' | grep -v grep".format(iperf_bt_daemon_path)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            server_command, ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port))
        log.info(f"{server_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

        if enable_bt and iperf_bt_daemon_path not in rtn_outputs:
            server_command = f"pkill -ef iperf"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, ssh_ip=client_mgr_ip, ssh_port=str(cls.test_port), timeout=10)
            log.info(f"{server_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
            server_command = f"pkill -ef iperf"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port), timeout=10)
            log.info(f"{server_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
            time.sleep(3)

            server_command = \
                f"timeout 5 ssh root@{server_mgr_ip} -p {cls.test_port} 'nohup python3 {iperf_bt_daemon_path} " \
                f"--sip {server_device_ip} --cip {client_device_ip} --cmgrip {client_mgr_ip} --run_time={run_time} " \
                f"--bandwidth 1M --parallel_num 4 --packet_length 88 &'"
            rtn_code, rtn_outputs = subprocess.getstatusoutput(server_command)
            log.info(f"{server_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}")
        if not enable_bt:
            server_command = f"pkill -ef iperf"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, ssh_ip=client_mgr_ip, ssh_port=str(cls.test_port), timeout=10)
            log.info(f"{server_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
            server_command = f"pkill -ef iperf"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                server_command, ssh_ip=server_mgr_ip, ssh_port=str(cls.test_port), timeout=10)
            log.info(f"{server_command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

    @classmethod
    def iptables_setting(cls):
        """
        linux 设置防火墙
        """

        def parse_iptables_configure():
            import json
            with open(scripts_constants.IPTABLES_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = f.read()
                parsed_data = json.loads(data)
                return parsed_data

        def judge_iptables_chain(chain, rule, ssh_ip, select_object, cmd_execute_address):
            """
            Args:
                chain: iptables中的链，包括：FORWARD, INPUT, OUTPUT
                rule:accept, drop，ets
                ssh_ip：测试端os的管理IP地址
                select_object:要添加的IP地址
                cmd_execute_address:执行端
            """
            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                return True

            exec_command = f"iptables -L {chain} -v -n|grep {rule}"
            _, show_stdout, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=cmd_execute_address,
                ssh_port=str(cls.test_port),
                ssh_ip=ssh_ip,
                ssh_username=f'root',
                host_os_client=host_os_server, host_os_server=host_os_server, timeout=30)
            show_stdout_list = show_stdout.split("\n")
            show_stdout_list = [index for index in show_stdout_list if index]
            result_list = []
            for show_stdout in show_stdout_list:
                result_code = True if select_object in re.sub(r"\s+", " ", show_stdout).split(" ") else False
                result_list.append(result_code)
            rtn_code = True if True in result_list else False
            print("iptables_setting~~~~~~~~~~~~~~~~~~~~~", rtn_code)
            return rtn_code

        def add_iptables_chain(chain, rule, ssh_ip, select_ip, cmd_execute_address):
            """
               Args:
                   chain: iptables中的链，包括：FORWARD, INPUT, OUTPUT
                   rule:accept, drop，ets
                   ssh_ip：测试端os的管理IP地址
                   select_ip:选择的对象
                   cmd_execute_address:执行端
           """
            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                return

            input_accept_command = f"iptables -I {chain} -s {select_ip} -j {rule}"
            log.info(f"IP为{ssh_ip}端添加防火墙规则：{input_accept_command}")
            server_int_status, *_ = CommandOperation.execute_command_multi_times(
                cmd=input_accept_command, cmd_execute_address=cmd_execute_address,
                ssh_port=str(cls.test_port),
                ssh_ip=ssh_ip,
                host_os_client=host_os_server, host_os_server=host_os_server, timeout=30)

        def add_protocol_chain(rule, ssh_ip, protocol, cmd_execute_address):
            """
            Args:
                   rule:accept, drop，ets
                   ssh_ip：测试端os的管理IP地址
                   protocol:要添加的协议类型
                   cmd_execute_address:执行端
            """
            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                return

            accept_icmp_command = \
                f"iptables -A INPUT -p {protocol} -j {rule};iptables -A OUTPUT -p {protocol} -j {rule}"
            log.info(f"对IP为：{ssh_ip}环境添加icmp通行：{accept_icmp_command}")
            CommandOperation.execute_command_multi_times(
                cmd=accept_icmp_command, cmd_execute_address=cmd_execute_address,
                ssh_port=str(cls.test_port),
                ssh_ip=ssh_ip,
                host_os_client=host_os_client, host_os_server=host_os_server, timeout=30)
            log.info(f"对IP为：{server_mgr_ip}环境添加icmp通行：{accept_icmp_command}")

        def save_iptables(ssh_ip, cmd_execute_address):
            """
            Args:
                ssh_ip:执行命令端的IP地址
                cmd_execute_address: 执行端
            """
            if (cls.client_renix_only_flag or cls.frame_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in [tj_constants.SINGLE_MODE]) and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                log.info('single mode或发包仪环境，跳过client命令执行')
                return

            exec_command = "iptables-save > /etc/sysconfig/iptables"
            log.info("对添加的iptables的规则进行持久化保存，重启不丢失")
            CommandOperation.execute_command_multi_times(
                cmd=exec_command, cmd_execute_address=cmd_execute_address,
                ssh_port=str(cls.test_port),
                ssh_ip=ssh_ip,
                host_os_client=host_os_client, host_os_server=host_os_server, timeout=30)

        iptables_dict = parse_iptables_configure()
        server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
        host_os_server = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL)
        host_os_client = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        assert iptables_dict["allow_ip"]
        for accept_ip in iptables_dict["allow_ip"]:
            rtn_code = judge_iptables_chain(chain="INPUT", rule="ACCEPT", ssh_ip=server_mgr_ip, select_object=accept_ip,
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            if not rtn_code:
                add_iptables_chain(chain="INPUT", rule="ACCEPT", ssh_ip=server_mgr_ip, select_ip=accept_ip,
                                   cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            rtn_code = judge_iptables_chain(chain="INPUT", rule="ACCEPT", ssh_ip=client_mgr_ip, select_object=accept_ip,
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
            if not rtn_code:
                add_iptables_chain(chain="INPUT", rule="ACCEPT", ssh_ip=client_mgr_ip, select_ip=accept_ip,
                                   cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)

            rtn_code = judge_iptables_chain(chain="OUTPUT", rule="ACCEPT", ssh_ip=server_mgr_ip,
                                            select_object=accept_ip,
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            if not rtn_code:
                add_iptables_chain(chain="OUTPUT", rule="ACCEPT", ssh_ip=server_mgr_ip, select_ip=accept_ip,
                                   cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            rtn_code = judge_iptables_chain(chain="OUTPUT", rule="ACCEPT", ssh_ip=client_mgr_ip,
                                            select_object=accept_ip,
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
            if not rtn_code:
                add_iptables_chain(chain="OUTPUT", rule="ACCEPT", ssh_ip=client_mgr_ip, select_ip=accept_ip,
                                   cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value
                                   )
        client_proto_rtn = judge_iptables_chain(
            chain="OUTPUT", rule="ACCEPT", ssh_ip=client_mgr_ip, select_object="icmp",
            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
        if not client_proto_rtn:
            add_protocol_chain(rule="ACCEPT", ssh_ip=client_mgr_ip, protocol="icmp",
                               cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
        server_proto_rtn = judge_iptables_chain(
            chain="OUTPUT", rule="ACCEPT", ssh_ip=server_mgr_ip, select_object="icmp",
            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        if not server_proto_rtn:
            add_protocol_chain(rule="ACCEPT", ssh_ip=server_mgr_ip, protocol="icmp",
                               cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        save_iptables(ssh_ip=server_mgr_ip, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        save_iptables(ssh_ip=client_mgr_ip, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)

    @classmethod
    def transport_configure(cls):
        WINDOWS_FILE_PATH_ROOT = 'C:/Users/Administrator/sxetest/'
        server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
        host_os_server = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL)
        host_os_client = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        # 如果server端是windows.則執行如下步驟：
        if host_os_server == "windows":
            cls.transport_file_remote(ssh_ip=server_mgr_ip, host_os=host_os_server,
                                      file_catalogue=WINDOWS_FILE_PATH_ROOT)
            rtn_code = CommonOperation.check_file_exist(
                directory_name=tj_constants.WINDOWS_FILE_PATH_ROOT,
                file_name=tj_constants.FIREWALL_FILE,
                ssh_ip=server_mgr_ip,
                host_os_server=host_os_server,
                host_os_client=host_os_client,
                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                ssh_port=str(cls.test_port))
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info("文件执行成功")
            else:
                cls.transport_file_remote(ssh_ip=server_mgr_ip, host_os=host_os_server,
                                          file_catalogue=WINDOWS_FILE_PATH_ROOT)
                CommonOperation.check_file_exist(
                    directory_name=WINDOWS_FILE_PATH_ROOT,
                    file_name=tj_constants.FIREWALL_FILE,
                    ssh_ip=server_mgr_ip,
                    host_os_server=host_os_server,
                    host_os_client=host_os_client,
                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                    ssh_port=str(cls.test_port))
        # 如果client端是windows系統，則執行如下步驟
        if host_os_client == "windows":
            cls.transport_file_remote(ssh_ip=client_mgr_ip, host_os=host_os_client,
                                      file_catalogue=WINDOWS_FILE_PATH_ROOT)
            rtn_code = CommonOperation.check_file_exist(
                directory_name=WINDOWS_FILE_PATH_ROOT,
                file_name=tj_constants.FIREWALL_FILE,
                ssh_ip=client_mgr_ip,
                host_os_server=host_os_server,
                host_os_client=host_os_client,
                cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                ssh_port=str(cls.test_port))
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info("文件执行成功")
            else:
                cls.transport_file_remote(ssh_ip=client_mgr_ip, host_os=host_os_client,
                                          file_catalogue=WINDOWS_FILE_PATH_ROOT)
                CommonOperation.check_file_exist(
                    directory_name=WINDOWS_FILE_PATH_ROOT,
                    file_name=tj_constants.FIREWALL_FILE,
                    ssh_ip=client_mgr_ip,
                    host_os_server=host_os_server,
                    host_os_client=host_os_client,
                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                    ssh_port=str(cls.test_port))

    @classmethod
    def transport_file_remote(cls, ssh_ip, host_os, file_catalogue):
        """
        author: wei.yuan1
        date: 2023.12.29
        description: 向远端传输文件
        :param ssh_ip:
        :param host_os:
        :param file_catalogue:
        :return:
        """
        if host_os == "windows":
            root = "Administrator"
            exec_command = \
                f'scp -P {cls.test_port} {scripts_constants.WINRM_CONFIG_PATH} ' \
                f'{root}@{ssh_ip}:{file_catalogue}/'
            rtn_code, result = cls.getstatusoutput(exec_command)
            log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f"{ssh_ip}:::拷贝失败！")
        else:
            pass

    @classmethod
    def __check_adapter_number(cls):
        """
        获取网卡的个数
        """
        server_driver_name, client_driver_name = CommonOperation.get_nic_driver_name()
        server_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_HOST_IP)
        client_mgr_ip = cls.frame_run_dict['ip_dict'].get(constants.ENV_CLIENT_IP)
        host_os_server = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL)
        host_os_client = cls.frame_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)

        exec_command = \
            '(Get-NetAdapter | Where-Object { $_.InterfaceDescription -like "*LD 1160-2X*" }).Count'
        if host_os_server == "windows" and server_driver_name.lower() == "sxe":
            status, out, err = CommandOperation.execute_command_multi_times(
                cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_port=str(cls.test_port),
                ssh_ip=server_mgr_ip,
                host_os_client=host_os_server, host_os_server=host_os_server, timeout=30)
            if status != RtnStatusEnum.SUCCESS.value or not out:
                return False
            else:
                count = int(re.sub(r"\s+", "", out))
                return False if count < 2 else True
        if host_os_client == "windows" and client_driver_name.lower() == "sxe":
            status, out, err = CommandOperation.execute_command_multi_times(
                cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, ssh_port=str(cls.test_port),
                ssh_ip=client_mgr_ip,
                host_os_client=host_os_server, host_os_server=host_os_server, timeout=30)
            if status != RtnStatusEnum.SUCCESS.value:
                return False
            else:
                count = int(re.sub(r"\s+", "", out))
                return False if count < 2 else True

    @classmethod
    def fill_Testles_test_parameters(cls, script_path: str):
        """
        填充测试测试框架运行参数Testles_autotest/framework/libs/sagitta_test_parameters.json
        """
        if "system_test_smoke" in script_path:
            log.info("fill_Testles_test_parameters")
            server_dev_name, client_dev_name = CommonOperation.get_nic_relationships(rdma=True)
            # print("sagitta: ", cls.frame_run_dict, "\n")
            Testles_autotest = \
                os.path.join(os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))), "Testles_autotest")
            Testles_framework_para_file = \
                os.path.join(Testles_autotest, "framework", "libs", "sagitta_test_parameters.json")
            if os.path.isfile(Testles_framework_para_file):
                log.info(f"Testles_framework_para_file exist: {Testles_framework_para_file}")
                server_ip = cls.frame_run_dict["ip_dict"]["server_ip"]
                client_ip = cls.frame_run_dict["ip_dict"]["client_ip"]
                # 从server上读取env_config.ini中的relationships_rdma
                with open(Testles_framework_para_file, 'r', encoding='utf-8') as file:
                    param_dict = json.load(file)
                param_dict["host_cpu"] = cls.frame_run_dict["config_dict"]["host_cpu"]
                param_dict["host_os"] = cls.frame_run_dict["config_dict"]["host_os"]
                param_dict["ip_list"] = f'{server_ip}, {client_ip}'
                real_platform_conf = {"ip_list": "{#" + server_ip + "#,#" + client_ip + "#}",
                                      "sn_ip": server_ip,
                                      "sn_hca_name": server_dev_name[0],
                                      "sn_hca_port": "1",
                                      "src_ip": client_ip,
                                      "src_hca_name": client_dev_name[0],
                                      "src_hca_port": "1",
                                      "des_ip": server_ip,
                                      "des_hca_name": server_dev_name[0],
                                      "des_hca_port": "1",
                                      "jenkins_server_ip": cls.frame_run_dict["config_dict"]["jenkins_ip"],
                                      "ib_server_ip": "",
                                      "log_server_ip": cls.frame_run_dict["ip_dict"]["log_server_ip"],
                                      "log_server_account": cls.frame_run_dict["ip_dict"]["log_server_account"],
                                      "test_port": cls.frame_run_dict["ip_dict"]["test_port"]}
                param_dict["real_platform"] = str(real_platform_conf).replace("'", '\"').replace("#", "'")
                # smoke/all
                param_dict["run_type"] = "all"
                # 无对应参数，固定""
                param_dict["module_select"] = ""
                param_dict["script_timeout"] = cls.frame_run_dict["config_dict"]["script_timeout"]
                param_dict["test_platform"] = cls.frame_run_dict["config_dict"]["test_platform"]
                param_dict["test_rounds"] = cls.frame_run_dict["config_dict"]["test_rounds"]
                # ascending_order/random_order
                param_dict["run_sequence"] = "random_order" \
                    if cls.frame_run_dict["config_dict"]["random_exec"] else "ascending_order"
            else:
                log.error(f"Testles_framework_para_file not exist: {Testles_framework_para_file}.")
                exit(1)

            with open(Testles_framework_para_file, 'w', encoding='utf-8') as file:
                json.dump(param_dict, file, indent=4)
            print("Testles: ", param_dict)
            log.info("fill_Testles_test_parameters success")

    @classmethod
    def clear_Testles_failed_test_case(cls):
        """
        清空测试fail测试用例表格Testles_autotest/scripts/case_script_lists/ib_failed_tc.csv
        """
        log.info(f"clear_Testles_failed_test_case_file")
        Testles_autotest = \
            os.path.join(os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))), "Testles_autotest")
        Testles_failed_case_file = \
            os.path.join(Testles_autotest, "scripts", "case_script_lists", Testles_FAILED_CASE_FILE)
        if os.path.isfile(Testles_failed_case_file):
            log.info(f"Testles_failed_case_file exist: {Testles_failed_case_file}")
            with open(Testles_failed_case_file, mode='w', newline='', encoding='utf-8') as file:
                row_title = ["caseId", "caseTitle", "caseVersion", "caseType", "caseLevel", "scriptLocation",
                             "branchId", "moduleId", "moduleName", "caseStep", "runId", "needRun"]
                writer = csv.writer(file)
                writer.writerows([row_title])
        log.info(f"clear_Testles_failed_test_case_file: {Testles_failed_case_file}, success")

    @classmethod
    def backup_Testles_zento_test_case(cls):
        """
        备份测试禅道用例表格/home/test/ps3test/pms/pm823/ps3/test/esat/nic100/Testles_autotest/framework/libs/sagitta_test_case_list.csv
        """
        log.info(f"backup_Testles_zento_test_case")
        Testles_autotest = \
            os.path.join(os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))), "Testles_autotest")
        Testles_zento_case_file = \
            os.path.join(Testles_autotest, "framework", "libs", Testles_ZENTO_CASE_FILE)
        if os.path.isfile(Testles_zento_case_file):
            log.info(f"Testles_zento_test_case file exist: {Testles_zento_case_file}")
            backup_file = f'{Testles_zento_case_file}_{str(time.time()).split(".")[0]}'
            cmd = f"/bin/cp -r {Testles_zento_case_file} {backup_file}"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, local_execute_flag=True)
            log.info(f"backup_Testles_zento_test_case: {Testles_zento_case_file} -> {backup_file}, success")

    @classmethod
    def fill_Testles_test_case(cls, script_path: str, case_title: str, run_type: str = "Y") -> tuple:
        """
        填充测试测试用例表格Testles_autotest/scripts/case_script_lists/ib_auto_tc.csv
        """
        # case_script_list = cls.frame_run_dict["script_case_dict"].keys()
        if "system_test_smoke" in script_path:
            log.info(f"fill_Testles_test_case: {run_type}")
            if run_type == "Y":
                # 测试框架待执行用例名称sagitta_case_name
                sagitta_case_name = []
                sagitta_case_file = cls.frame_run_dict["config_dict"]["case_script_list_path"]
                if os.path.isfile(sagitta_case_file):
                    log.info(f"sagitta_case_file exist: {sagitta_case_file}")
                    _, file_extension = os.path.splitext(sagitta_case_file)
                    if file_extension.lower() == '.xlsx':
                        data = openpyxl.load_workbook(sagitta_case_file)
                        table = data.active
                        # 在ps3用例表格中查找script_name对应的全部caseTitle
                        for row in table.iter_rows(min_row=1, max_row=table.max_row, min_col=1,
                                                   max_col=table.max_column):
                            if "caseTitle" != row[1].value and row[1].value in case_title and row[5].value in script_path:
                                sagitta_case_name.append(row[1].value)
                    else:
                        with open(sagitta_case_file, mode='r', newline='', encoding='utf-8') as file:
                            reader = csv.reader(file)
                            data = list(reader)
                            # 在ps3用例表格中查找script_name对应的全部caseTitle
                            for row_i, row in enumerate(data):
                                if "caseTitle" != row[1] and row[1] in case_title and row[5] in script_path:
                                    sagitta_case_name.append(row[1])
                else:
                    log.error(f"sagitta_case_file not exist: {sagitta_case_file}")
                    exit(1)
                if not sagitta_case_name:
                    log.error(f"{sagitta_case_file}: not find any case by {script_path} -> {sagitta_case_name}")
                    return "sagitta case not exist", ""
                else:
                    log.info(f"sagitta_case by {script_path}: {sagitta_case_name}")

                # 测试框架待执行用例名称Testles_case_name
                Testles_case_name = []
                Testles_case_id = []
                Testles_autotest = \
                    os.path.join(os.path.dirname(
                        os.path.dirname(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))),
                        "Testles_autotest")
                Testles_case_file = \
                    os.path.join(Testles_autotest, "scripts", "case_script_lists", Testles_CASE_FILE)
                if os.path.isfile(Testles_case_file):
                    # 测试框架待执行用例 添加到 测试框架待执行用例
                    log.info(f"Testles_case_file exist: {Testles_case_file}")
                    _, file_extension = os.path.splitext(Testles_case_file)
                    if file_extension.lower() == '.xlsx':
                        data = openpyxl.load_workbook(Testles_case_file)
                        table = data.active
                        for row_i, row in enumerate(table.iter_rows(min_row=1, max_row=table.max_row,
                                                                    min_col=1, max_col=table.max_column)):
                            if "caseTitle" != row[1].value and row[1].value and row[1].value in sagitta_case_name:
                                table.cell(row_i + 2, 12, "Y")
                                Testles_case_name.append(row[1].value)
                                Testles_case_id.append(row[0].value)
                    else:
                        # 测试框架执行用例的列表中，待执行的用例修改为Y
                        with open(Testles_case_file, mode='r+', newline='', encoding='utf-8') as file:
                            reader = csv.reader(file)
                            data = list(reader)
                            for sagitta_case in sagitta_case_name:
                                for row_i, row in enumerate(data):
                                    if "caseTitle" != row[1] and row[1] and row[1] == sagitta_case:
                                        row[11] = "Y"
                                        Testles_case_name.append(row[1])
                                        Testles_case_id.append(row[0])
                                        break
                            file.seek(0)
                            writer = csv.writer(file)
                            writer.writerows(data)
                    if not Testles_case_name:
                        log.error(f"{Testles_case_file}: not find these case -> {sagitta_case_name}")
                        return "Testles case not exist", ""
                    elif len(Testles_case_name) != len(sagitta_case_name):
                        log.info(f"Testles_case: {Testles_case_name}")
                        sagitta_case_set = set(sagitta_case_name)
                        Testles_case_set = set(Testles_case_name)
                        diff_set = list(sagitta_case_set - Testles_case_set)
                        log.error(f"{Testles_case_file}: not find case {diff_set}")
                        for diff_case in diff_set:
                            Testles_case_name.append(f"{diff_case}: sagitta case not exist in Testles")
                            Testles_case_id.append("")
                        log.info(f"Testles_case: {Testles_case_name}")
                        return Testles_case_name, Testles_case_id
                    else:
                        log.info(f"Testles_case: {Testles_case_name}")
                else:
                    log.error(f"Testles_case_file not exist: {Testles_case_file}.")
                    log.error(f"try following steps：")
                    log.error(f"1. create {Testles_case_file}")
                    log.error(f"2. set sagitta_test_parameters.json run_type='all'")
                    log.error(f"3. python3 run_all_test_ib.py, ")
                    exit(1)
            # run_type == N
            else:
                # 测试框架待执行用例名称Testles_case_name
                Testles_case_name = []
                Testles_case_id = []
                Testles_autotest = \
                    os.path.join(os.path.dirname(
                        os.path.dirname(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))),
                        "Testles_autotest")
                Testles_case_file = \
                    os.path.join(Testles_autotest, "scripts", "case_script_lists", Testles_CASE_FILE)
                if os.path.isfile(Testles_case_file):
                    # 测试框架待执行用例 添加到 测试框架待执行用例
                    log.info(f"Testles_case_file exist: {Testles_case_file}")
                    _, file_extension = os.path.splitext(Testles_case_file)
                    if file_extension.lower() == '.xlsx':
                        data = openpyxl.load_workbook(Testles_case_file)
                        table = data.active
                        for row_i, row in enumerate(table.iter_rows(min_row=1, max_row=table.max_row,
                                                                    min_col=1, max_col=table.max_column)):
                            if "caseTitle" != row[1].value and row[1].value:
                                table.cell(row_i + 2, 12, "N")
                                Testles_case_name.append(row[1].value)
                                Testles_case_id.append(row[0].value)
                    else:
                        # 测试框架执行用例的列表中，待执行的用例修改为Y
                        with open(Testles_case_file, mode='r+', newline='', encoding='utf-8') as file:
                            reader = csv.reader(file)
                            data = list(reader)
                            for row_i, row in enumerate(data):
                                if "caseTitle" != row[1] and row[1]:
                                    row[11] = "N"
                                    Testles_case_name.append(row[1])
                                    Testles_case_id.append(row[0])
                            file.seek(0)
                            writer = csv.writer(file)
                            writer.writerows(data)
                    if not Testles_case_name:
                        log.error(f"{Testles_case_file}: set N fail")
                        exit(1)
                    else:
                        log.info(f"{Testles_case_file}: set N success")
                else:
                    log.error(f"Testles_case_file not exist: {Testles_case_file}.")
                    log.error(f"try following steps：")
                    log.error(f"1. create {Testles_case_file}")
                    log.error(f"2. set sagitta_test_parameters.json run_type='all'")
                    log.error(f"3. python3 run_all_test_ib.py, ")
                    exit(1)
            # 测试框架执行用例的列表, 创建
            log.info(f"fill_Testles_test_case: {run_type} success")
            return Testles_case_name, Testles_case_id

    @classmethod
    def fill_Testles_executing_case_config(cls, case_title: str):
        """
        填充测试测试正在執行用例名稱
        """
        # case_script_list = cls.frame_run_dict["script_case_dict"].keys()
        log.info("fill_Testles_executing_case_config")
        nic100_root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(os.path.dirname(__file__)))))
        executing_case_file = os.path.join(nic100_root_path, "Testles_autotest", "scripts",
                                           "executing_case_by_sagitta.ini")
        if os.path.isfile(executing_case_file):
            cmd = f"echo {case_title} > {executing_case_file}"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, local_execute_flag=True)
        else:
            log.warning(f"executing_case_file not exist: {executing_case_file}")
            log.info(f"try to create file: {executing_case_file}")
            with open(executing_case_file, mode='w') as file:
                file.write(case_title)
            if os.path.isfile(executing_case_file):
                log.info(f"create file success: {executing_case_file}")
                cmd = f"cat {executing_case_file}"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, local_execute_flag=True)
                if rtn_outputs:
                    log.info(f"write file success: {executing_case_file}")
                else:
                    log.error(f"write file fail: {executing_case_file}")
                    exit(1)
            else:
                log.error(f"create file fail: {executing_case_file}")
                exit(1)
        # 测试框架执行用例的列表, 创建
        log.info("fill_Testles_executing_case_config success")

    # @classmethod
    # def manual_config_link(cls, case_title: str):

    @classmethod
    def get_host_config_info(cls, vm):
        wb = openpyxl.load_workbook(constants.HOST_CONFIG_FILE)
        ws = wb.active
        result = {}
        for line in islice(ws.rows, 1, None):
            row = {}
            for index, cell in enumerate(list(line)):
                if index < len(cls.__host_info):
                    row[cls.__host_info[index]] = str(cell.value)
                else:
                    break
            result[row.get(constants.ENV_HOST_LABEL)] = row
        print(f'--------------{result}')
        return result.get(vm, {})


if __name__ == '__main__':
    abnormal_dict = {}
    FrameworkModel.env_status_check(abnormal_dict, 0)
