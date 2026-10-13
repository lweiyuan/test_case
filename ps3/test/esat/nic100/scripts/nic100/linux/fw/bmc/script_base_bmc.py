#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      xiangyu.liu
date:        2025.07.10
description: BMC基类
"""

import json
import os
import re
import subprocess
import time
from random import choices, randint
from re import findall
from string import ascii_letters, digits, hexdigits
from traceback import format_exc
import add_syspath
from collections import defaultdict

from scripts.script_libs.cli_operation import CliOperation, AnalyzeCli
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse
from scripts.script_libs import constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.constants import BMC_SPEED_P0, BMC_SPEED_P1, BMC_SPEC_SPEED_P0, BMC_SPEC_SPEED_P1
from scripts.script_libs.constants import BMC_STATE_P0, BMC_STATE_P1, BMC_STATE_ABS_P0, BMC_STATE_ABS_P1
from scripts.script_libs.constants import BMC_TEMP_P0, BMC_TEMP_P1, BMC_THRES_P0, BMC_THRES_P1, BMC_THRES_SOC
from scripts.script_libs.constants import SCGBECLI64, PRODUCT_NAME, VENDOR_NAME, CHECK_ENCODE
from scripts.script_libs.enums import NicNameEnum, CmdExecuteAdressEnum, RtnStatusEnum, RegionEnum, BmcFwState, \
    CliStatusEnum
from scripts.script_libs.ethtool_operation import EthtoolOperation
from scripts.script_libs.host_operation import HostOperation
from scripts.script_libs.ifconfig import IfConfig
from scripts.script_libs.script_base import ScriptBase
from scripts.nic100.linux.fw.bmc.common_bmc import PldmTool, CommonTools, CliCommonUtils, CommonCli, HostPara, \
    BmcEnvInfo, ProductType, CpuType, temp_limit_list, MctpTools


class BmcScriptBase(ScriptBase):
    # 原始参数
    server_driver_name, client_driver_name = CommonOperation.get_nic_driver_name()
    server_ip, client_ip = CommonOperation.get_nic_logical_ip()
    exec_address = CmdExecuteAdressEnum.SERVER.value
    exec_address_other = CmdExecuteAdressEnum.CLIENT.value
    bmc_ip = ''
    info_dict = {}
    nic_list = []
    port_list = []
    do_step = 1
    post_step = 1
    case_title = 'BMC'
    soc_threshold = 50
    time_stamp_ori = 0
    duration = 60 * 10
    ori_mfginfo = {}
    bmc_eid = ""
    bmc_eid_list = list()

    # 片外cli可配置生产信息
    pn = ''
    sn = ''
    mfg_date = ''
    revision = ''
    rework_date = ''
    mac_addr0 = ''
    mac_addr1 = ''
    ori_version = ''

    # 公共输入参数
    check_nic_num = False  # 是否进行网卡数量校验，默认False，不校验
    multi_nic_flag = True  # 当check_nic_num为True时，校验环境是否为多张网卡，True时预期为多张网卡

    reboot_bmc_flag = False  # 对于有重启固件的脚本，此开关置True，do函数结束后关闭，防止固件重启后没有重启主机影响其他脚本跑测
    reboot_host_flag = False  # 对于有重启固件的脚本，此开关置True，do函数结束后关闭，防止固件重启后没有重启主机影响其他脚本跑测
    recover_link_flag = False  # 恢复链路状态，防止ifconfig down后出bug导致链路不通
    upgrade_flag = False  # 验证升级可能会回退小版本，置True在post函数中恢复大版本
    upgrade_bak_flag = False
    recover_mfginfo_flag = False
    recover_fw_state = False

    # 调试代码
    debug = True

    @classmethod
    def set_parameters(cls) -> None:
        """
        author:
        date:
        description:设置参数
        """
        super().set_parameters()
        cls.test_object = 'nic'
        cls.test_module = 'cli'
        cls.test_tool = constants.SCGBECLI64  # 默认值constants.SCGBECLI64, 为cli
        cls.test_precondition = ''

        if cls.debug:
            cls.ipvbs_screen_mark = 'liuxy'
            current_path = os.path.abspath(__file__)
            if 'Y:\\new_test' in current_path or 'liuxy2/new_test' in current_path:
                server_ip = CommandLineArgsParse.get_server_ip()
                client_ip = CommandLineArgsParse.get_client_ip()
                root_path = os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
                target_env_config_name = os.path.join(root_path, 'env_config.ini')
                if server_ip == '10.22.66.227' and client_ip == '10.22.66.227':
                    src_env_config_name = os.path.join(root_path, 'env_config_227.ini')
                elif server_ip == '10.22.66.227' and client_ip == '10.22.66.229':
                    src_env_config_name = os.path.join(root_path, 'env_config_227_sc.ini')
                elif server_ip == '10.22.65.222' and client_ip == '10.22.65.222':
                    src_env_config_name = os.path.join(root_path, 'env_config_222.ini')
                elif server_ip == '10.22.65.222' and client_ip == '10.22.66.229':
                    src_env_config_name = os.path.join(root_path, 'env_config_222_sc.ini')
                elif server_ip == '10.22.114.212' and client_ip == '10.22.114.212':
                    src_env_config_name = os.path.join(root_path, 'env_config_212.ini')
                elif server_ip == '10.22.114.212' and client_ip == '10.22.114.213':
                    src_env_config_name = os.path.join(root_path, 'env_config_212_sc.ini')
                elif server_ip == '10.22.114.169' and client_ip == '10.22.114.169':
                    src_env_config_name = os.path.join(root_path, 'env_config_169.ini')
                elif server_ip == '10.22.114.169' and client_ip == '10.22.114.168':
                    src_env_config_name = os.path.join(root_path, 'env_config_169_sc.ini')
                elif server_ip == '10.22.116.161' and client_ip == '10.22.116.161':
                    src_env_config_name = os.path.join(root_path, 'env_config_161.ini')
                elif server_ip == '10.22.116.161' and client_ip == '10.22.116.162':
                    src_env_config_name = os.path.join(root_path, 'env_config_161_sc.ini')
                elif server_ip == '10.17.136.245' and client_ip == '10.17.136.245':
                    src_env_config_name = os.path.join(root_path, 'env_config_245.ini')
                elif server_ip == '10.17.136.245' and client_ip == '10.17.136.27':
                    src_env_config_name = os.path.join(root_path, 'env_config_245_sc.ini')
                elif server_ip == '10.17.137.240' and client_ip == '10.17.137.240':
                    src_env_config_name = os.path.join(root_path, 'env_config_240.ini')
                elif server_ip == '10.17.137.240' and client_ip == '10.17.136.93':
                    src_env_config_name = os.path.join(root_path, 'env_config_240_sc.ini')
                elif server_ip == '10.22.66.228':
                    src_env_config_name = os.path.join(root_path, 'env_config_228.ini')
                elif server_ip == '10.17.136.93' and client_ip == '10.17.136.93':
                    src_env_config_name = os.path.join(root_path, 'env_config_93.ini')
                elif server_ip == '10.17.136.93' and client_ip == '10.17.137.208':
                    src_env_config_name = os.path.join(root_path, 'env_config_93_sc.ini')

                exec_command = f"cp {src_env_config_name} {target_env_config_name}"
                log.info(exec_command)
                rtn_code, result = subprocess.getstatusoutput(exec_command)

                fpga_bitversion = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_path))))), 'fpga_bit_version.txt')
                with open(fpga_bitversion, 'w') as f:
                    f.write('0xb302f00c')

    @classmethod
    def check_own_environment(cls) -> None:
        """
        author:
        date:
        description:环境
        """
        log.info('\n' + f" 环境检查".center(100, "*"))
        result = CommonOperation.common_check_environment(
            cls, ip_version_check_flag=True)
        info_json = json.dumps(cls.test_device_info_list, indent=2)
        log.info(
            "待测网卡信息:\n%s" % info_json)
        # cls.nic_list = CommonTools.get_nic_list(
        #     cmd_execute_address=cls.exec_address)
        cls.port_list = [i["server_pf_device_name"] for i in cls.test_device_info_list]
        cls.nic_list = set([i[:-1] for i in cls.port_list])
        log.info(f'cls.port_list: {cls.port_list}    cls.nic_list: {cls.nic_list}')
        if cls.check_nic_num:
            CommonOperation.concat_test_steps('0.1 涉及链路操作，检查网卡数量')
            nic_num = len(cls.nic_list)
            log.info('当前主机网卡数量：%d' % nic_num)
            log.info(f'用例需要多网卡环境：{cls.multi_nic_flag}')
            if cls.multi_nic_flag:
                if nic_num > 1:
                    cls.own_environment_enabled = result
                else:
                    cls.own_environment_enabled = False
            else:
                if nic_num > 1:
                    cls.own_environment_enabled = False
                else:
                    cls.own_environment_enabled = result
        else:
            CommonOperation.concat_test_steps('0.1 不涉及链路操作，不检查网卡数量')
            cls.own_environment_enabled = result

        CommonOperation.concat_test_steps('0.2 检查port数量')
        # server_dev_list, client_dev_list = CommonOperation.get_nic_relationships()
        # cls.port_list = server_dev_list
        log.info(f'测试port数量：{len(cls.port_list)}')

        BmcEnvInfo.product_type = BmcEnvInfo.get_product_type(cls.exec_address)
        BmcEnvInfo.cpu_type = BmcEnvInfo.get_cpu_type(cls.exec_address)
        # _, output_dmi, _ = CommandOperation.execute_command_with_error(
        #     cmd="dmidecode | grep 'Product Name'", cmd_execute_address=cls.exec_address
        # )
        # _, output_cpu, _ = CommandOperation.execute_command_with_error(
        #     cmd="lscpu | grep 'Model name'", cmd_execute_address=cls.exec_address
        # )

        # if (((CpuType.MDA.value != BmcEnvInfo.cpu_type and CpuType.INTEL.value != BmcEnvInfo.cpu_type) or ProductType.G50.value != BmcEnvInfo.product_type) and
        #         ((CpuType.Teston.value != BmcEnvInfo.cpu_type) or ProductType.G50.value != BmcEnvInfo.product_type)):
        #     cls.own_environment_enabled = False
        #     log.skip(cls, "当前主机环境不符合测试要求,即Teston G50环境, skip.....")
        #     return
        # else:
        #     BmcEnvInfo.update_bmc_login_info()
        #     BmcEnvInfo.update_bmc_tool()
        BmcEnvInfo.update_bmc_login_info()
        BmcEnvInfo.update_bmc_tool()

        # 如果是外网环境，需要配置bmc开放3322端口
        if cls.test_port in [3322]:
            log.info(f'外网环境，需要配置bmc开放3322端口')
            cls.bmc_ip = CommandLineArgsParse.get_server_bmc_ip()
            cmd = f"sshpass -p {BmcEnvInfo.bmc_passwd} ssh -p 22 {BmcEnvInfo.bmc_user_name}@{cls.bmc_ip} '/usr/sbin/dropbear -B -p 3322 -I 600'"
            CommandOperation.execute_command_with_error(cmd)

            cmd = f'python3 /opt/tools/config_bmc_ssh.py -p {cls.test_port} -ip {cls.bmc_ip} -u {BmcEnvInfo.bmc_user_name} -pwd {BmcEnvInfo.bmc_passwd}'
            status, result, _ = CommandOperation.execute_command_with_error(cmd)
            if 'success' not in result.split('\n')[-1]:
                log.skip(cls, f'外网环境，配置bmc:{cls.bmc_ip}开放{cls.test_port}端口失败，ps3server必须使用{cls.test_port}端口连接bmc')
                cls.own_environment_enabled = False
                return

        # 工具覆盖
        if BmcEnvInfo.cpu_type == CpuType.INTEL.value:
            cmd = "/bin/cp {} {}".format(constants.BMC_TOOL_PATH_MCTPAPP, constants.BMC_TOOL_PATH)
        else:
            cmd = "/bin/cp {} {}".format(constants.BMC_TOOL_PATH_BUSCTL, constants.BMC_TOOL_PATH)
        log.info("当前环境CPU为{},进行BMC工具覆盖,cmd:{}".format(BmcEnvInfo.cpu_type, cmd))
        CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=cls.exec_address)
        cmd = "{} -v".format(constants.BMC_TOOL_PATH)
        _, res, _ = CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=cls.exec_address)
        log.info("BMC工具版本信息:\n{}".format(res))

        # @changlog 2025.10.23 获取eid的动作前移,获取失败则skip
        # if cls.server_driver_name in [NicNameEnum.SXE2.value, NicNameEnum.SCGBE.value]:
        log.info('本次测试为sxe2网卡')
        cls.test_object = 'sxe2'
        cls.exec_address = CmdExecuteAdressEnum.SERVER.value
        cls.exec_address_other = CmdExecuteAdressEnum.CLIENT.value
        # elif cls.client_driver_name in [NicNameEnum.SXE2.value, NicNameEnum.SCGBE.value]:
        #     log.info('本次测试为sxe2网卡')
        #     cls.test_object = 'sxe2'
        #     cls.exec_address = CmdExecuteAdressEnum.CLIENT.value
        #     cls.exec_address_other = CmdExecuteAdressEnum.SERVER.value
        # elif cls.server_driver_name == NicNameEnum.INTEL_82599.value:
        #     log.info('本次测试为Intel82599网卡')
        #     cls.test_object = 'intel82599'
        #     cls.exec_address = CmdExecuteAdressEnum.SERVER.value
        #     cls.exec_address_other = CmdExecuteAdressEnum.CLIENT.value
        # else:
        #     log.info('本次测试为Intel82599网卡')
        #     cls.test_object = 'intel82599'
        #     cls.exec_address = CmdExecuteAdressEnum.CLIENT.value
        #     cls.exec_address_other = CmdExecuteAdressEnum.SERVER.value

        CommonOperation.concat_test_steps(f'1.1 关闭monitor')
        cls.bmc_ip = CommandLineArgsParse.get_server_bmc_ip()
        CommonTools.close_monitor(cls.bmc_ip, cls.exec_address)

        CommonOperation.concat_test_steps('1.2 收集网卡集eid信息')
        # cls.bmc_eid = CommonTools.get_bmc_eid(cls.bmc_ip, cls.exec_address)
        cls.bmc_eid_list = CommonTools.get_bmc_eid_list(ip=cls.bmc_ip, execute_addr=cls.exec_address)
        if not cls.bmc_eid_list:
            log.warning("获取当前环境网卡的bmc eid失败, 尝试重新获取mctp设备id")
            MctpTools.restart_mctp_service(bmc_ip=cls.bmc_ip)
            log.info("休眠90秒后,重新收集网卡集eid信息")
            time.sleep(90)
            cls.bmc_eid_list = CommonTools.get_bmc_eid_list(ip=cls.bmc_ip, execute_addr=cls.exec_address, wait_max_count=10)
            if not cls.bmc_eid_list:
                log.skip(cls, "获取当前环境网卡的bmc eid失败,测试未开始")
                cls.own_environment_enabled = False
                return
        # 初始化,默认eid
        cls.bmc_eid = cls.bmc_eid_list[-1]

        CommonOperation.concat_test_steps('1.3 通过uuid,将网卡port和bmc侧的eid进行对应')
        # 单卡测试环境
        if len(cls.nic_list) == 1:
            log.info("单卡环境")
            for device_info in cls.test_device_info_list:
                bdf = device_info["server_bus_info"]
                cls.info_dict[bdf] = dict()
                cmd = "lspci -vvvs {} | grep -i 'subsystem'".format(bdf)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                    cmd, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                pf_index = int(bdf.split(".")[-1])
                cls.info_dict[bdf]["pf_index"] = pf_index
                # 确定卡类型,和Port id
                if constants.SUB_DEVICE_ID_OCP_X2.lower() in rtn_outputs.lower():
                    cls.info_dict[bdf]["device_type"] = constants.SUB_DEVICE_ID_OCP_X2
                    cls.info_dict[bdf]["port_index"] = [1, 0][pf_index]
                elif constants.SUB_DEVICE_ID_OCP_X4.lower() in rtn_outputs.lower():
                    cls.info_dict[bdf]["device_type"] = constants.SUB_DEVICE_ID_OCP_X4
                    cls.info_dict[bdf]["port_index"] = [3, 2, 1, 0][pf_index]
                elif constants.SUB_DEVICE_ID_PCIE_X2.lower() in rtn_outputs.lower():
                    cls.info_dict[bdf]["device_type"] = constants.SUB_DEVICE_ID_PCIE_X2
                    cls.info_dict[bdf]["port_index"] = [1, 0][pf_index]
                # 确定芯片厂商
                if constants.SUB_VENDOR_ID_LINKDATA.lower() in rtn_outputs.lower():
                    cls.info_dict[bdf]["vendor_id"] = constants.SUB_VENDOR_ID_LINKDATA
                else:
                    cls.info_dict[bdf]["vendor_id"] = constants.SUB_VENDOR_ID_TL

                cls.info_dict[bdf]['network_name'] = device_info["server_pf_device_name"]
                cls.info_dict[bdf]['eid'] = cls.bmc_eid
                uuid = CliOperation.get_cli_show_fw_info(caller_class=cls, device=bdf)["Base UUID"].lower()
                cls.info_dict[bdf]["uuid"] = uuid
                if len(cls.bmc_eid_list) > 1:
                    log.info("单卡测试环境,发现多个eid,进行UUID适配查找")
                    for eid in cls.bmc_eid_list:
                        status_pldm, uuid_pldm = PldmTool.get_uuid(
                            ip=cls.bmc_ip, eid=eid, execute_addr=cls.exec_address, create_bug=False)
                        if uuid_pldm and uuid == uuid_pldm:
                            cls.info_dict[bdf]['eid'] = eid
                            log.info(f"找到了,bdf[{bdf}]的eid为[{eid}]")
                            break
        # 多卡测试环境
        else:
            if len(cls.bmc_eid_list) < len(cls.nic_list):
                log.skip(
                    cls, f"{len(cls.nic_list)}个卡的测试环境,"
                         f"只在BMC侧找到{len(cls.bmc_eid_list)}个eid:{cls.bmc_eid_list},环境异常,测试未开始")
                cls.own_environment_enabled = False
                return
            log.info("多卡环境")
            for device_info in cls.test_device_info_list:
                bdf = device_info["server_bus_info"]
                cls.info_dict[bdf] = dict()

                cls.info_dict[bdf]['network_name'] = device_info["server_pf_device_name"]
                cls.info_dict[bdf]["pf_index"] = int(bdf.split(".")[-1])
                # cls.info_dict[bdf]['eid'] = cls.bmc_eid
                uuid = CliOperation.get_cli_show_fw_info(caller_class=cls, device=bdf)["Base UUID"].lower()
                cls.info_dict[bdf]["uuid"] = uuid
                cls.info_dict[bdf]["eid"] = ""
            bmc_uuid_dict = dict()
            for eid in cls.bmc_eid_list:
                status_pldm, uuid_pldm = PldmTool.get_uuid(
                    ip=cls.bmc_ip, eid=eid, execute_addr=cls.exec_address, create_bug=False)
                if uuid_pldm:
                    bmc_uuid_dict[eid] = uuid_pldm
                    log.info(f"bmc_eid:{eid}, uuid:{uuid_pldm}")
            for bdf in cls.info_dict:
                cli_uuid = cls.info_dict[bdf]["uuid"]
                for eid in bmc_uuid_dict:
                    if cli_uuid.lower() == bmc_uuid_dict[eid].lower():
                        cls.info_dict[bdf]["eid"] = eid
                        log.info(f"bdf[{bdf}]根据uuid[{cli_uuid}]匹配,对应的bmc eid为[{eid}]")

                        cmd = "lspci -vvvs {} | grep -i 'subsystem'".format(bdf)
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                            cmd, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        pf_index = int(bdf.split(".")[-1])
                        cls.info_dict[bdf]["pf_index"] = pf_index
                        # 确定卡类型
                        if constants.SUB_DEVICE_ID_OCP_X2.lower() in rtn_outputs.lower():
                            cls.info_dict[bdf]["device_type"] = constants.SUB_DEVICE_ID_OCP_X2
                        elif constants.SUB_DEVICE_ID_OCP_X4.lower() in rtn_outputs.lower():
                            cls.info_dict[bdf]["device_type"] = constants.SUB_DEVICE_ID_OCP_X4
                        elif constants.SUB_DEVICE_ID_PCIE_X2.lower() in rtn_outputs.lower():
                            cls.info_dict[bdf]["device_type"] = constants.SUB_DEVICE_ID_PCIE_X2
                        # 确定芯片厂商
                        if constants.SUB_VENDOR_ID_LINKDATA in rtn_outputs.lower():
                            cls.info_dict[bdf]["vendor_id"] = constants.SUB_VENDOR_ID_LINKDATA
                        else:
                            cls.info_dict[bdf]["vendor_id"] = constants.SUB_VENDOR_ID_TL
                        break
                # 如果没找到对应eid, skip
                if not cls.info_dict[bdf]["eid"]:
                    log.skip(cls, f"bdf[{bdf}]的cli_uuid:[{cli_uuid}],没有找到对应uuid的bmc eid,测试未开始")
                    cls.own_environment_enabled = False
                    return

    @classmethod
    def prepare(cls) -> None:
        """
        author:
        date:
        description:前置条件
        """
        # 这里写测试前的准备工作，一般对应用例里的前提条件
        log.info('\n' + f"测试准备".center(100, "*"))
        # _, cli_output, _ = CommandOperation.execute_command_with_error(
        #     cmd=f'{SCGBECLI64} show', cmd_execute_address=cls.exec_address)
        # log.info(f'指令执行结果：\n{cli_output}')
        # for nic in cls.nic_list:
        #     port_re = re.findall(rf'\|([\w:\.]+)\s+\|[\w:]+\s+\|{nic}', cli_output)
        #     if port_re:
        #         # port = int(port_re[0].split('.')[-1])
        #         port = port_re[0]
        #         cls.info_dict[port] = {}
        #         cls.info_dict[port]['network_name'] = nic
        #         # uuid = CommonTools.custom_get_uuid(port, cls.exec_address)
        #         cls.info_dict[port]['eid'] = cls.bmc_eid
        if not cls.info_dict:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word='获取网卡信息失败',
                expect_info='获取网卡信息成功',
                result_info='获取网卡信息失败')

        BmcEnvInfo.update_info_dict(cls.info_dict)
        info_json = json.dumps(cls.info_dict, indent=2)
        log.info(
            "网卡名及eid信息,格式：{px：{'eid': '***', 'network_name': '***'}}\n%s" % info_json)

        if cls.recover_mfginfo_flag:
            CommonOperation.concat_test_steps('1.3 收集mfginfo')
            for px in cls.nic_list:
                _, info, _ = CommandOperation.execute_command_with_error(
                    cmd=f'{SCGBECLI64} -d {list(cls.info_dict.keys())[px]} show mfginfo',
                    cmd_execute_address=cls.exec_address
                )
                tmp_lst = re.findall(r'\++-+\++-+\+(.*)\+-+\+', info, re.S)
                info_lst = re.findall(r'\|.*\|(\S+)', tmp_lst[0])
                cls.ori_mfginfo[px] = [info.replace('|', '') for info in info_lst]

    @classmethod
    def do(cls) -> None:
        """
        author:
        date:
        description:
        """
        log.info('Success: 完成所有测试步骤')

    @classmethod
    def post(cls) -> None:
        """
        author:
        date:
        description:恢复测试环境
        """
        log.info('\n' + f"复原环境".center(100, "*"))
        if cls.reboot_bmc_flag:
            CommonOperation.concat_test_steps(f'3.{cls.post_step} 重启bmc和主机')
            cls.post_step += 1
            CommonTools.reboot_bmc(cls.bmc_ip, cls.exec_address)
            CommonTools.reboot_host(cls.server_ip)
            CommonOperation.modprobe_driver('sxe2', cls.exec_address)
            CommonTools.time_sleep(20)
        elif cls.reboot_host_flag:
            CommonOperation.concat_test_steps(f'3.{cls.post_step} 重启主机')
            cls.post_step += 1
            CommonTools.reboot_host(cls.server_ip)
            CommonOperation.modprobe_driver('sxe2', cls.exec_address)
            CommonTools.time_sleep(20)

        if cls.recover_link_flag:
            CommonOperation.concat_test_steps(f'3.{cls.post_step} 加载驱动')
            cls.post_step += 1
            CommonOperation.modprobe_driver('sxe2', cmd_execute_address=cls.exec_address)
            CommonOperation.concat_test_steps(
                f'3.{cls.post_step} 对所有device执行ifconfig up 恢复链路状态')
            cls.post_step += 1
            for port_info in cls.info_dict.values():
                dev_name = port_info['network_name']
                IfConfig.set_device_up(
                    device_name=dev_name,
                    cmd_execute_address=cls.exec_address)

        reboot = False
        if cls.upgrade_flag:
            cls.info_dict = CommonTools.get_env_bmc_eid_info(cls.test_device_info_list)
            eid_list = list()
            bdf_list = list()
            for px, bdf in enumerate(cls.info_dict.keys()):
                eid = cls.info_dict[bdf]['eid']
                if eid in eid_list:
                    continue
                else:
                    eid_list.append(eid)
                    bdf_list.append(bdf)

            for j in range(len(eid_list)):
                eid = eid_list[j]
                bdf = bdf_list[j]
                if CommonTools.get_soc_fw_state(eid=eid, execute_addr=cls.exec_address) == 0x31:
                    log.info(f"Eid[{eid}]的固件在升级状态,等待固件升级完成")
                    updateing_flag = True
                    try_time = 0
                    if updateing_flag:
                        while try_time < 200:
                            try_time += 1
                            CommonTools.sleep_time(15)
                            if CommonTools.get_soc_fw_state(eid=eid, execute_addr=cls.exec_address) != 0x31:
                                log.info(f"Eid[{eid}]固件升级状态解除")
                                updateing_flag = False
                                break
                            else:
                                log.info(f"Eid[{eid}]的固件在升级状态,第{try_time}次查询,等待固件升级完成")
                    if updateing_flag:
                        CommonOperation.create_bug_problem(
                            cls,
                            key_word=cls.case_title,
                            description_word=f'还原环境时,Eid[{eid}]始终为升级状态,无法重新升级还原环境',
                            result_info='升级失败,还原环境失败')

                CommonOperation.concat_test_steps(f'3.{cls.post_step} 升级默认的Image包,还原环境')
                cls.post_step += 1
                CommonOperation.modprobe_driver('sxe2', cls.exec_address)
                # pkg_path = CommonOperation.get_full_path(
                #     UPGRADE_IMAGE_PACKAGE_PATH, cls.exec_address)
                pkg_path = CommonOperation.get_image_upgrade_file_for_bdf(
                    bdf_info=bdf, exec_addr=cls.exec_address, caller_class=cls)
                _, output_upgrade, output_error = CommandOperation.execute_command_with_error(
                    cmd=f'{SCGBECLI64} -d {bdf} upgrade file={pkg_path}',  #  noverchk
                    cmd_execute_address=cls.exec_address)
                output_upgrade += output_error
                if 'Success' in output_upgrade:
                    reboot = True
                else:
                    CommonOperation.create_bug_problem(
                        cls,
                        key_word=cls.case_title,
                        description_word=f'还原环境时,Eid[{eid}]_bdf[{bdf}],通过cli升级Image包失败,还原环境失败',
                        result_info='升级失败')
        if cls.upgrade_bak_flag:
            # CommonOperation.concat_test_steps(f'3.{cls.post_step} 升级备分区到最新版本')
            # cls.post_step += 1
            # pkg_path = CommonOperation.get_full_path(
            #     constants.UPGRADE_IMAGE_PACKAGE_BAK_PATH, cls.exec_address)
            # _, output_upgrade, _ = CommandOperation.execute_command_with_error(
            #     cmd=f'{SCGBECLI64} -d {list(cls.info_dict.keys())[0]} upgrade file={pkg_path} noverchk',
            #     cmd_execute_address=cls.exec_address)
            # if 'Success' in output_upgrade:
            #     reboot = True
            # else:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word='待修改的脚本,不应进入该方法',
                result_info='备份分区升级方法')
        if reboot:
            CommonTools.reset_and_reboot(cls.exec_address)
            CommonTools.reboot_bmc(
                ip=cls.bmc_ip, execute_addr=cls.exec_address)
            CommonOperation.modprobe_driver('sxe2', cls.exec_address)

        if cls.recover_mfginfo_flag:
            CommonOperation.concat_test_steps(f'3.{cls.post_step} 将mfginfo恢复为原值')
            cls.post_step += 1
            for px, port_info in cls.info_dict.items():
                CommonCli.set_mfginfo(
                    px=px,
                    pn=port_info[0],
                    sn=port_info[1],
                    mfg_date=port_info[2],
                    rework_date=port_info[3],
                    revision=port_info[4],
                    mac0=port_info[5],
                    mac1=port_info[6]
                )
            CommonOperation.rmmod_driver('sxe2', cls.exec_address, True)
            CommonOperation.modprobe_driver('sxe2', cls.exec_address)

        if cls.recover_fw_state:
            CommonOperation.concat_test_steps(f'3.{cls.post_step} 将固件状态改为正常')
            cls.post_step += 1
            CommonTools.set_fw_state(status=BmcFwState.START_STATE_FINISHED.value, exec_addr=CmdExecuteAdressEnum.SERVER.value)

        eid_list = []
        for px, bdf in enumerate(cls.info_dict.keys()):
            eid = cls.info_dict[bdf]['eid']
            if eid in eid_list:
                continue
            else:
                eid_list.append(eid)
            cmd = f"sxe2cli -d {bdf} custom sxe2 upgrdsyncstate versionlineswitch=0"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                cmd, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            if "open:1" not in rtn_outputs:
                continue
            log.info("当前分区覆盖标识open:1,代表会进行分区覆盖,此处需要")
            time.sleep(30)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                cmd, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            count = 40
            if "run state: 1" in rtn_outputs:
                log.warning("正在进行分区覆盖,需要等待分区覆盖完成")
                while count:
                    time.sleep(10)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                        cmd, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    if "run state: 1" in rtn_outputs:
                        log.info("还在分区覆盖,等待10秒查看是否还有分区覆盖")
                    else:
                        log.info("分区覆盖完成, 脚本退出")
                        return
                    count -= 1
            if "run state: 1" in rtn_outputs:
                CommonOperation.create_bug_problem(
                    cls,
                    key_word=cls.case_title,
                    description_word='测试完成后,依旧长时间还在分区覆盖中',
                    result_info='分区覆盖run state: 1')

    @classmethod
    def get_all_module_temp_and_threshold(cls, nic_num=2, port_num=1):
        temp_lst = []
        threshold_lst = []
        for px in range(nic_num * port_num):
            sensor_temp = BMC_TEMP_P0 if px % 2 == 0 else BMC_TEMP_P1
            sensor_threshold = BMC_THRES_P0 if px % 2 == 0 else BMC_THRES_P1
            temp = CommonTools.check_sensor_reading_para(
                key_word=cls.case_title,
                ip=cls.bmc_ip,
                eid=cls.info_dict[list(cls.info_dict.keys())[px]]['eid'],
                sensor=sensor_temp,
                exp_size=1,
                execute_addr=cls.exec_address)
            _, threshold = PldmTool.get_sensor_thresholds(
                ip=cls.bmc_ip,
                eid=cls.info_dict[list(cls.info_dict.keys())[px]]['eid'],
                sensor=sensor_threshold,
                execute_addr=cls.exec_address)
            temp_lst.append(temp)
            threshold_lst.append(threshold)
        return temp_lst, threshold_lst

    @classmethod
    def get_all_module_speed(cls, nic_num=2, port_num=1):
        speed_lst = []
        for px in range(nic_num * port_num):
            CommonTools.time_sleep(1)
            sensor = BMC_SPEED_P0 if px % 2 == 0 else BMC_SPEED_P1
            _, rtn_cli, _ = CommandOperation.execute_command_with_error(
                cmd=f'{SCGBECLI64} -d {list(cls.info_dict.keys())[px]} show', cmd_execute_address=cls.exec_address)
            link_speed = findall(r'\s*Link Speed\s*=\s*(.*)', rtn_cli)[0]
            # log.info(f'指令执行结果{rtn_cli}')
            if 'No Link' in link_speed:
                exp_pres = 3
                exp_evt = 3
            else:
                exp_pres = 1
                exp_evt = 1
            speed = CommonTools.check_sensor_reading_para(
                key_word=cls.case_title,
                ip=cls.bmc_ip,
                eid=cls.info_dict[list(cls.info_dict.keys())[px]]['eid'],
                sensor=sensor,
                exp_size=0,
                exp_evt_enable=2,
                exp_pres=exp_pres,
                exp_evt_state=exp_evt,
                execute_addr=cls.exec_address)
            speed_lst.append(speed)
        return speed_lst

    @classmethod
    def get_all_spec_speed(cls, nic_num=2, port_num=1):
        spec_speed_lst = []
        for px in range(nic_num * port_num):
            sensor = BMC_SPEC_SPEED_P0 if px % 2 == 0 else BMC_SPEC_SPEED_P1
            spec_speed = CommonTools.check_sensor_reading_para(
                key_word=cls.case_title,
                ip=cls.bmc_ip,
                eid=cls.info_dict[list(cls.info_dict.keys())[px]]['eid'],
                sensor=sensor,
                exp_size=0,
                exp_evt_enable=0,
                execute_addr=cls.exec_address)
            spec_speed_lst.append(spec_speed)
        return spec_speed_lst

    @classmethod
    def get_all_link_state(cls, nic_num=2, port_num=1):
        port_state_lst = []
        for px in range(nic_num * port_num):
            sensor = BMC_STATE_P0 if px % 2 == 0 else BMC_STATE_P1
            state_dict = PldmTool.get_state_sensor_reading(
                ip=cls.bmc_ip,
                eid=cls.info_dict[list(cls.info_dict.keys())[px]]['eid'],
                sensor=sensor,
                execute_addr=cls.exec_address)
            port_state_lst.append(state_dict)
        return port_state_lst

    @classmethod
    def get_all_abs_state(cls, nic_num=2, port_num=1):
        abs_state_lst = []
        for px in range(nic_num * port_num):
            sensor = BMC_STATE_ABS_P0 if px % 2 == 0 else BMC_STATE_ABS_P1
            state_dict = PldmTool.get_state_sensor_reading(
                ip=cls.bmc_ip,
                eid=cls.info_dict[list(cls.info_dict.keys())[px]]['eid'],
                sensor=sensor,
                execute_addr=cls.exec_address)
            abs_state_lst.append(state_dict)
        return abs_state_lst

    @classmethod
    def cli_set_soc_threshold_continuous(cls, timeout=300):
        # soc_threshold_exp = cls.get_soc_temp() + 15
        while True:
            log.info('cli设置高温阈值')
            # if soc_threshold_exp == 120:
            #     soc_threshold_exp = cls.get_soc_temp() + 15
            # else:
            #     soc_threshold_exp += 1
            # threshold_s = format(soc_threshold_exp, 'd')
            _, result, _ = CommandOperation.execute_command_with_error(
                cmd=f'{SCGBECLI64} -d {list(cls.info_dict.keys())[0]} set soctempthreshold warninghigh={temp_limit_list[1]-15} warninglow=-6 '
                    f'criticalhigh={temp_limit_list[1]-10} criticallow=-11 fatalhigh={temp_limit_list[1]} fatallow=-16',
                cmd_execute_address=cls.exec_address)
            # log.info(f'指令执行结果：\n{result}')
            cls.soc_threshold = temp_limit_list[1]
            CommonTools.time_sleep(0.1)
            time_stamp_new = CommonTools.get_system_time_stamp(
                cls.exec_address)
            if time_stamp_new - cls.time_stamp_ori > timeout:
                break

    @classmethod
    def bmc_set_soc_threshold_continuous(cls, timeout=300):
        # soc_threshold_exp = cls.get_soc_temp() + 15
        while True:
            current_temp = cls.get_soc_temp()
            if current_temp + 10 <= temp_limit_list[1]:
                if current_temp + 10 < temp_limit_list[0]:
                    soc_threshold_exp = temp_limit_list[0]
                else:
                    soc_threshold_exp = current_temp + 10
            else:
                soc_threshold_exp = temp_limit_list[1]
            log.info(f'bmc设置高温阈值为{soc_threshold_exp}度')
            status, _ = PldmTool.set_sensor_thresholds(
                eid=cls.info_dict[list(cls.info_dict.keys())[0]]['eid'],
                ip=cls.bmc_ip,
                sensor=BMC_THRES_SOC,
                fatal_h=soc_threshold_exp,
                execute_addr=cls.exec_address)
            if status != '0':
                # CommonOperation.create_bug_problem(
                #     cls,
                #     key_word=cls.case_title,
                #     description_word='校验并发设置温度阈值PLDM接口status参数',
                #     expect_info='0',
                #     result_info=status)
                log.warning('设置温度阈值失败')
            cls.soc_threshold = soc_threshold_exp
            CommonTools.time_sleep(5)
            time_stamp_new = CommonTools.get_system_time_stamp(
                cls.exec_address)
            if time_stamp_new - cls.time_stamp_ori > timeout:
                break

    @classmethod
    def cli_get_soc_threshold_continuous(cls, timeout=300, check_flag=True):
        while True:
            log.info('cli获取高温阈值')
            _, output, _ = CommandOperation.execute_command_with_error(
                # cmd=f'{SCGBECLI64} -d {list(cls.info_dict.keys())[0]} custom sxe socTempThds',
                cmd=f'{SCGBECLI64} -d {list(cls.info_dict.keys())[0]} get soctempthreshold',
                cmd_execute_address=cls.exec_address)
            fatal_high = re.search(r"Temperature Fatal High\s+\|(\d+)\s+C", output, flags=re.I)
            # threshold_re = findall(r'SOC TEMP THRESHOLD:\s*(\d+)', output)
            if not fatal_high:
                CommonOperation.create_bug_problem(
                    cls, key_word=cls.bug_title,
                    description_word='cli指令获取soc高温阈值', result_info='获取失败')
            fatal_high_temp = int(fatal_high.group(1))
            if check_flag:
                # threshold_cli = int(threshold_re[0])
                if fatal_high_temp != cls.soc_threshold:
                    CommonOperation.create_bug_problem(
                        cls,
                        key_word=cls.bug_title,
                        description_word='检查并发执行时cli获取的soc高温阈值',
                        result_info=str(fatal_high_temp),
                        expect_info=str(cls.soc_threshold))
            time_stamp_new = CommonTools.get_system_time_stamp(
                cls.exec_address)
            if time_stamp_new - cls.time_stamp_ori > timeout:
                break

    @classmethod
    def bmc_get_soc_threshold_continuous(cls, timeout=300, check_flag=True):
        while True:
            log.info('bmc获取高温阈值')
            status, threshold_bmc = PldmTool.get_sensor_thresholds(
                ip=cls.bmc_ip, eid=cls.info_dict[list(cls.info_dict.keys())[0]]['eid'], sensor=BMC_THRES_SOC, execute_addr=cls.exec_address)
            # if status != '0':
            #     CommonOperation.create_bug_problem(
            #         cls,
            #         key_word=cls.case_title,
            #         description_word='校验PLDM_SetSensorThresholds接口status参数',
            #         expect_info='0',
            #         result_info=status)
            if check_flag:
                soc_threshold_bmc = int(threshold_bmc['upper_thold_fatal'])
                if soc_threshold_bmc != cls.soc_threshold:
                    CommonOperation.create_bug_problem(
                        cls,
                        key_word=cls.bug_title,
                        description_word='检查并发执行时bmc获取的soc高温阈值',
                        result_info=str(soc_threshold_bmc),
                        expect_info=str(cls.soc_threshold))
            time_stamp_new = CommonTools.get_system_time_stamp(
                cls.exec_address)
            if time_stamp_new - cls.time_stamp_ori > timeout:
                break

    @classmethod
    def cli_get_mfg_info_continuous(cls, timeout=300):
        while True:
            log.info('cli获取mfg info')
            _, output, _ = CommandOperation.execute_command_with_error(
                cmd=f'{SCGBECLI64} -d {list(cls.info_dict.keys())[0]} show mfginfo',
                cmd_execute_address=cls.exec_address)
            if 'Success' not in output:
                CommonOperation.create_bug_problem(
                    cls,
                    key_word=cls.bug_title,
                    description_word='cli指令获取生产信息',
                    result_info='获取失败')
            time_stamp_new = CommonTools.get_system_time_stamp(
                cls.exec_address)
            if time_stamp_new - cls.time_stamp_ori > timeout:
                break

    @classmethod
    def bmc_get_fru_info_continuous(cls, timeout=300, check_flag=True):
        eid = cls.info_dict[list(cls.info_dict.keys())[0]]['eid']
        _, fru_metadata_dict = PldmTool.get_fru_record_table_metadata(
            ip=cls.bmc_ip, eid=eid, execute_addr=cls.exec_address)
        fru_size = fru_metadata_dict['fru_sbl_length']
        while True:
            log.info('bmc获取mfg info')
            status, fru_dict = PldmTool.get_fru_record_table(
                ip=cls.bmc_ip, eid=eid, frusize=fru_size, transferflag='1', execute_addr=cls.exec_address)
            if status != '0':
                CommonOperation.create_bug_problem(
                    cls,
                    key_word=cls.case_title,
                    description_word='校验PLDM_GetFruRecordTable接口status参数',
                    expect_info='0',
                    result_info=status)
            if check_flag:
                cls.new_check_fru_info(fru_dict, list(cls.info_dict.keys())[0])
                # cls.check_fru_info(fru_dict=fru_dict, px=0)
            time_stamp_new = CommonTools.get_system_time_stamp(
                cls.exec_address)
            if time_stamp_new - cls.time_stamp_ori > timeout:
                break

    @classmethod
    def cli_export_log_continuous(cls, timeout=300):
        while True:
            log.info('cli 执行show termlog')
            cls.cli_show_termlog(px=0, check_code=False)
            time_stamp_new = CommonTools.get_system_time_stamp(
                cls.exec_address)
            if time_stamp_new - cls.time_stamp_ori > timeout:
                break

    @classmethod
    def bmc_export_log_continuous(cls, timeout=300):
        eid = cls.info_dict[list(cls.info_dict.keys())[0]]['eid']
        while True:
            log.info('bmc 执行show termlog')
            PldmTool.new_bmc_get_oem_log_and_check(
                caller_class=cls,
                eid=eid,
                bmc_ip=cls.bmc_ip,
                execute_addr=cls.exec_address
            )

            # size = PldmTool.get_oem_log(
            #     eid=eid,
            #     ip=cls.bmc_ip,
            #     log_type=0,
            #     execute_addr=cls.exec_address,
            #     check_code=False,
            #     caller_class=cls
            # )
            # if size > 4:
            #     CommonOperation.create_bug_problem(
            #         cls,
            #         key_word='BMC',
            #         description_word='检查导出日志大小',
            #         expect_info='日志小于4K',
            #         result_info=f'{size}K'
            #     )
            time_stamp_new = CommonTools.get_system_time_stamp(
                cls.exec_address)
            if time_stamp_new - cls.time_stamp_ori > timeout:
                break
            time.sleep(5)

    @classmethod
    def set_mfg_info(cls, px=0):
        cls.pn = ''.join(choices(digits + ascii_letters, k=8))
        cls.sn = ''.join(choices(digits + ascii_letters, k=16))
        cls.mfg_date = '%04d-%02d-%02d' % (randint(2000, 2100),
                                           randint(1, 12), randint(1, 28))
        cls.revision = ''.join(choices(digits, k=4))
        cls.rework_date = '%04d-%02d-%02d' % (
            randint(2000, 2100), randint(1, 12), randint(1, 28))
        cls.mac_addr0 = 'e4b633' + ''.join(choices(hexdigits, k=6)).lower()
        cls.mac_addr1 = 'e4b633' + ''.join(choices(hexdigits, k=6)).lower()
        cli_cmd = (
            f'{SCGBECLI64} -d {list(cls.info_dict.keys())[px]} set mfginfo PN={cls.pn} SN={cls.sn} mfgDate={cls.mfg_date} '
            f'reworkDate={cls.rework_date} macAddr0={cls.mac_addr0} '
            f'macAddr1={cls.mac_addr1}')
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cli_cmd, cmd_execute_address=cls.exec_address)
        # log.info(f'指令执行结果：\n{rtn_output}')

    @classmethod
    def check_fru_header(
            cls,
            exp_set_id,
            exp_type,
            exp_fields_num,
            exp_encoding,
            rst_dict):
        rst_set_id = int(rst_dict['recordSetId'], 16)
        rst_type = int(rst_dict['recordType'], 16)
        rst_fields_num = int(rst_dict['fieldsNum'], 16)
        rst_encoding = int(rst_dict['EncodingType'], 16)
        if rst_set_id != exp_set_id:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word='校验PLDM_GetFruRecordTable接口recordSetId参数',
                expect_info=str(exp_set_id),
                result_info=str(rst_set_id))
        if rst_type != exp_type:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word='校验PLDM_GetFruRecordTable接口recordType参数',
                expect_info=str(exp_type),
                result_info=str(rst_type))
        if rst_fields_num != exp_fields_num:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word='校验PLDM_GetFruRecordTable接口fieldsNum参数',
                expect_info=str(exp_fields_num),
                result_info=str(rst_fields_num))
        if rst_encoding != exp_encoding:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word='校验PLDM_GetFruRecordTable接口EncodingType参数',
                expect_info=str(exp_encoding),
                result_info=str(rst_encoding))

    @classmethod
    def new_check_fru_info(cls, fru_dict, device_info):
        block_flag = False
        status, return_dict, res = AnalyzeCli.analyze_show(exec_addr=cls.exec_address)
        if status != CliStatusEnum.SUCCESS.value or not return_dict:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word=f'sxe2cli show命令获取信息失败',
                expect_info=f'获取成功',
                result_info=f'获取失败')
        device_list = list()

        for k, v in return_dict.items():
            if type(v) == list:
                for i in v:
                    dev_info = i.get("Device", "")
                    if dev_info:
                        if device_info.lower()[:-1] == dev_info.lower()[:-1]:
                            device_list.append(dev_info)

        device_list = sorted(device_list, key=lambda x: int(x.split('.')[-1]))
        log.info("准备验证的Device:{}".format(device_list))

        if len(device_list) not in [2, 4]:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word=f'sxe2cli show命令获取的网卡Device信息,数量错误',
                expect_info=f'数量为2 or 4',
                result_info=f'{device_list}, 数量为{len(device_list)}')

        device_0 = device_list[0]
        cls.check_fru_header(
            exp_set_id=0x01,
            exp_type=0x01,
            exp_encoding=0x01,
            exp_fields_num=0x0f,
            rst_dict=fru_dict['0'])
        cls.check_fru_header(
            exp_set_id=0x02,
            exp_type=0xfe,
            exp_encoding=0x01,
            exp_fields_num=0x19,
            rst_dict=fru_dict['1'])
        prop_dict = {"Product Info": {"Product Name": None,
                                      "Part Number": None,
                                      "Serial Number": None,
                                      "Vendor Name": None,
                                      "Mfg Date": None,
                                      "Asset Tag": None,
                                      "Part Version": None,
                                      }
                     }
        prop_dict = CliOperation.cli_get_mfginfo_prop_list(cls, device_0, prop_dict)
        print("mfginfo:{}".format(prop_dict))
        product_name = prop_dict["Product Info"]["Product Name"]
        part_number = prop_dict["Product Info"]["Part Number"]
        serial_number = prop_dict["Product Info"]["Serial Number"]
        vendor_name = prop_dict["Product Info"]["Vendor Name"]
        mfg_date = prop_dict["Product Info"]["Mfg Date"]
        asset_tag = prop_dict["Product Info"]["Asset Tag"]
        part_version = prop_dict["Product Info"]["Part Version"]

        vesion_dict = cls.get_version(px=None, pf_bdf=device_0)
        fw_version = vesion_dict['Firmware Version']
        optionrom_version = vesion_dict['OptionRom Version']


        show_info_list = list()
        # show_module_list = list()
        for bdf in device_list:
            status, dev_show_info, _ = AnalyzeCli.analyze_dev_show(dev_para=bdf, exec_addr=cls.exec_address)
            if status != CliStatusEnum.SUCCESS.value:
                log.error("dev_show_info:{}".format(dev_show_info))
                CommonOperation.create_bug_problem(
                    cls,
                    key_word=cls.case_title,
                    description_word=f'sxe2cli获取pf[{bdf}]的show信息失败',
                    expect_info=f'获取成功',
                    result_info=f'获取失败')
            show_info_list.append(dev_show_info)
            # module_info = CliOperation.get_cli_show_module(dev_para=bdf, check_ignore=False)
            # if not module_info:
            #     log.warning(f"sxe2cli获取pf[{bdf}]的module信息失败")
            #     # CommonOperation.create_bug_problem(
            #     #     cls,
            #     #     key_word=cls.case_title,
            #     #     description_word=f'sxe2cli获取pf[{bdf}]的module信息失败',
            #     #     expect_info=f'获取成功',
            #     #     result_info=f'获取失败')
            # show_module_list.append(module_info)
        exp_dict = dict()
        exp_dict['record 0'] = {
                '0': {'field': 'Ethernet Card', 'len': 16, 'fieldType': 1, 'description': 'Chassis Type'},
                '1': {'field': '', 'len': 0, 'fieldType': 2, 'description': 'Model'},
                '2': {'field': part_number, 'len': 8 if len(part_number) <= 8 else 16, 'fieldType': 3,
                      'description': 'Part Number'},
                '3': {'field': serial_number, 'len': 8 if len(serial_number) <= 8 else 16, 'fieldType': 4,
                      'description': 'Serial Number'},
                '4': {'field': vendor_name, 'len': 8 if len(vendor_name) <= 8 else 16, 'fieldType': 5,
                      'description': 'Manufacturer(同Vendor Name)'},
                '5': {'field': mfg_date, 'len': 13, 'fieldType': 6, 'description': 'Manufacture Date'},
                '6': {'field': vendor_name, 'len': 8 if len(vendor_name) <= 8 else 16, 'fieldType': 7,
                      'description': 'Vendor Name'},
                '7': {'field': product_name, 'len': 8 if len(product_name) <= 8 else 16, 'fieldType': 8,
                      'description': 'Product Name'},
                '8': {'field': '', 'len': 0, 'fieldType': 9, 'description': 'SKU'},
                '9': {'field': part_version, 'len': len(part_version), 'fieldType': 10, 'description': 'Version'},
                '10': {'field': asset_tag, 'len': len(asset_tag), 'fieldType': 11, 'description': 'Asset Tag'},
                '11': {'field': '', 'len': 0, 'fieldType': 12, 'description': 'Description'},
                '12': {'field': '', 'len': 0, 'fieldType': 13, 'description': 'Eng Change Lvl'},
                '13': {'field': '', 'len': 0, 'fieldType': 14, 'description': 'Other_Info'},
                '14': {'field': '', 'len': 0, 'fieldType': 15, 'description': 'Vendor IANA'},}
        exp_dict['record 1'] = {
            '0': {'field': '', 'len': 0, 'fieldType': 1, 'description': 'Vendor IANA'},
            '1': {'field': product_name, 'len': 64, 'fieldType': 2, 'description': '型号'},
            '2': {'field': fw_version, 'len': 32, 'fieldType': 3, 'description': 'FW version'},
            '3': {'field': optionrom_version, 'len': 32, 'fieldType': 4, 'description': 'OptionRom version'},
            '4': {'field': str(len(device_list)), 'len': 1, 'fieldType': 5, 'description': 'port num'},}

        for record_key, record_dict in exp_dict.items():
            for field_index, field_dict in record_dict.items():
                description = field_dict['description']
                exp_value = field_dict['field']
                exp_len = field_dict['len']
                exp_type = field_dict['fieldType']
                record_index = record_key.split(' ')[1]
                rst_value = fru_dict[record_index]['Fields'][field_index]['field'].strip(
                )
                rst_len = int(
                    fru_dict[record_index]['Fields'][field_index]['fieldLength'], 16)
                rst_type = int(
                    fru_dict[record_index]['Fields'][field_index]['fieldType'], 16)
                if rst_type != exp_type or rst_value != exp_value:  # rst_len != exp_len or
                    CommonOperation.create_bug_problem(
                        # @changelog 2025.12.25 验证失败后,最后报错
                        cls, block=block_flag,
                        key_word=cls.case_title,
                        description_word=f'校验PLDM_GetFruRecordTable接口{record_index} {description}参数与期望不一致',
                        expect_info=f'期望fieldType: {exp_type}; fieldLength: {exp_len}; field: {exp_value};',
                        result_info=f'实际fieldType: {rst_type}; fieldLength: {rst_len}; field: {rst_value};')
                else:
                    log.info(f"fieldType: {rst_type}; fieldLength: {rst_len}; field: {rst_value}; 验证通过")

        field_num = 0
        for i in range(len(device_list)):
            field_num += 5
            port_link = show_info_list[i]["Port Link"]
            link_status = show_info_list[i]["Link Status"]
            sfp_status = show_info_list[i]["SFP Information Acquisition Status"]
            if sfp_status == "Successful":
                module_info = CliOperation.get_cli_show_module(dev_para=device_list[i], check_ignore=False)
                identifier = module_info.get("Identifier", "")
            else:
                identifier = ""
            fru_identifier = fru_dict["1"]['Fields'][str(field_num)]["field"]

            vendor_name = show_info_list[i].get("Vendor Name", "")
            fru_vendor_name = fru_dict["1"]['Fields'][str(field_num + 1)]["field"]

            vendor_pn = show_info_list[i].get("Vendor PN", "")
            fru_vendor_pn = fru_dict["1"]['Fields'][str(field_num + 2)]["field"].strip()

            if constants.OPTICAL_INFO_DICT.get(vendor_pn.strip()):
                link_speed = str(constants.OPTICAL_INFO_DICT[vendor_pn.strip()]["spec_speed"]) + "G"
            else:
                link_speed = show_info_list[i].get("Link Speed", "").replace("Gb/s", "G").strip()
            fru_opt_spec_speed = fru_dict["1"]['Fields'][str(field_num + 3)]["field"]

            mac_address = show_info_list[i].get("Mac Address", "")
            fru_mac_address = fru_dict["1"]['Fields'][str(field_num + 4)]["field"]

            if mac_address != fru_mac_address:
                CommonOperation.create_bug_problem(
                    # @changelog 2025.12.25 验证失败后,最后报错
                    cls, block=block_flag,
                    key_word=cls.case_title,
                    description_word=f'PLDM_GetFru, pf{i}的mac地址与cli显示不一致, field_num:{hex(field_num + 4)}',
                    expect_info=f'期望field: {mac_address};',
                    result_info='实际field: {};'.format(fru_mac_address))
            else:
                log.info(f"pf{i}的mac地址[{mac_address}]验证通过")
            # 建链状态
            if port_link == "1":
                if not fru_identifier or fru_identifier.strip() not in identifier.split(" "):
                    CommonOperation.create_bug_problem(
                        # @changelog 2025.12.25 验证失败后,最后报错
                        cls, block=block_flag,
                        key_word=cls.case_title,
                        description_word=f'PLDM_GetFru, pf{i}的identifier与cli显示不一致, field_num:{hex(field_num)}',
                        expect_info=f'期望field: {identifier};',
                        result_info='实际field: {};'.format(fru_identifier))
                else:
                    log.info(f"pf{i}的identifier[{fru_identifier.strip()}]验证通过")

                if not fru_vendor_name or fru_vendor_name.strip() != vendor_name.strip():
                    CommonOperation.create_bug_problem(
                        # @changelog 2025.12.25 验证失败后,最后报错
                        cls, block=block_flag,
                        key_word=cls.case_title,
                        description_word=f'PLDM_GetFru, pf{i}的光模块vendor_name与cli显示不一致, field_num:{hex(field_num + 1)}',
                        expect_info=f'期望field: {vendor_name};',
                        result_info='实际field: {};'.format(fru_vendor_name))
                else:
                    log.info(f"pf{i}的光模块vendor_name[{fru_vendor_name.strip()}]验证通过")

                if not fru_vendor_pn or fru_vendor_pn.strip() != vendor_pn.strip():
                    CommonOperation.create_bug_problem(
                        # @changelog 2025.12.25 验证失败后,最后报错
                        cls, block=block_flag,
                        key_word=cls.case_title,
                        description_word=f'PLDM_GetFru, pf{i}的光模块vendor_pn与cli显示不一致, field_num:{hex(field_num + 2)}',
                        expect_info=f'期望field: {vendor_pn};',
                        result_info='实际field: {};'.format(fru_vendor_pn.strip()))
                else:
                    log.info(f"pf{i}的光模块vendor_pn[{fru_vendor_pn}]验证通过")

                # if link_status == "1":
                #     link_speed = link_speed.split(" ")[0] + "G"
                # else:
                #     link_speed = "Unknow"

                if not fru_opt_spec_speed or fru_opt_spec_speed.lower() != link_speed.lower():
                    CommonOperation.create_bug_problem(
                        # @changelog 2025.12.25 验证失败后,最后报错
                        cls, block=block_flag,
                        key_word=cls.case_title,
                        description_word=f'PLDM_GetFru, pf{i}的光模块[{fru_vendor_pn}]规格速率与期望不一致, field_num:{hex(field_num + 3)}',
                        expect_info=f'期望field: {link_speed};',
                        result_info='实际field: {};'.format(fru_opt_spec_speed))
                else:
                    log.info(f"pf{i}的光模块规格速率[{fru_opt_spec_speed}]验证通过")

            else:
                if fru_identifier:
                    CommonOperation.create_bug_problem(
                        # @changelog 2025.12.25 验证失败后,最后报错
                        cls, block=block_flag,
                        key_word=cls.case_title,
                        description_word=f'PLDM_GetFru, pf{i}的identifier与cli显示不一致, field_num:{hex(field_num)}',
                        expect_info=f'期望field: 未接光模块,为空 {identifier};',
                        result_info='实际field: {};'.format(fru_identifier))
                else:
                    log.info(f"pf{i}的identifier[空]验证通过")

                if fru_vendor_name:
                    CommonOperation.create_bug_problem(
                        # @changelog 2025.12.25 验证失败后,最后报错
                        cls, block=block_flag,
                        key_word=cls.case_title,
                        description_word=f'PLDM_GetFru, pf{i}的vendor_name与cli显示不一致, field_num:{hex(field_num + 1)}',
                        expect_info=f'期望field: 未接光模块,为空 {vendor_name};',
                        result_info='实际field: {};'.format(fru_identifier))
                else:
                    log.info(f"pf{i}的vendor_name[空]验证通过")

                if fru_vendor_pn:
                    CommonOperation.create_bug_problem(
                        # @changelog 2025.12.25 验证失败后,最后报错
                        cls, block=block_flag,
                        key_word=cls.case_title,
                        description_word=f'PLDM_GetFru, pf{i}的光模块vendor_pn与cli显示不一致, field_num:{hex(field_num + 2)}',
                        expect_info=f'期望field: 未接光模块,为空 {vendor_pn}',
                        result_info='实际field: {}'.format(fru_vendor_pn))
                else:
                    log.info(f"pf{i}的vendor_pn[空]验证通过")

                if fru_opt_spec_speed.lower() != "Unknow".lower():
                    CommonOperation.create_bug_problem(
                        # @changelog 2025.12.25 验证失败后,最后报错
                        cls, block=block_flag,
                        key_word=cls.case_title,
                        description_word=f'PLDM_GetFru, pf{i}的光模块link_speed与cli显示不一致, field_num:{hex(field_num + 3)}',
                        expect_info=f'期望field: Unknow',
                        result_info='实际field: {};'.format(fru_opt_spec_speed))
                else:
                    log.info(f"pf{i}的link_speed[Unknow]验证通过")

    @classmethod
    def check_fru_info(cls, fru_dict, px=0):
        cls.check_fru_header(
            exp_set_id=0x01,
            exp_type=0x01,
            exp_encoding=0x01,
            exp_fields_num=0x0f,
            rst_dict=fru_dict['0'])
        cls.check_fru_header(
            exp_set_id=0x02,
            exp_type=0xfe,
            exp_encoding=0x01,
            exp_fields_num=0x19,
            rst_dict=fru_dict['1'])

        vesion_dict = cls.get_version(px=px)
        module_info_p0 = cls.get_module_info(px)
        module_info_p1 = cls.get_module_info(px + 1)

        product_name = cls.get_product_name(px=px)
        fw_ver = vesion_dict['Firmware Version']
        option_rom_ver = vesion_dict['OptionRom Version']
        identifier_p0 = module_info_p0['Identifier']
        vendor_name_p0 = module_info_p0['Vendor name']
        vendor_pn_p0 = module_info_p0['Vendor PN']
        vendor_speed_p0 = module_info_p0['speed']
        if module_info_p1:
            identifier_p1 = module_info_p1['Identifier']
            vendor_name_p1 = module_info_p1['Vendor name']
            vendor_pn_p1 = module_info_p1['Vendor PN']
            vendor_speed_p1 = module_info_p1['speed']

        exp_addr0 = ':'.join(findall(r'.{2}', cls.mac_addr0))
        exp_addr1 = ':'.join(findall(r'.{2}', cls.mac_addr1))

        # 注：cls.mfg_date长度13是根据接口特意修改的
        host_para = HostPara()
        exp_dict = {
            'record 0': {
                '0': {'field': 'Ethernet Card', 'len': 16, 'fieldType': 1, 'description': 'Chassis Type'},
                '1': {'field': '', 'len': 0, 'fieldType': 2, 'description': 'Model'},
                '2': {'field': cls.pn, 'len': 8, 'fieldType': 3, 'description': 'Part Number'},
                '3': {'field': cls.sn, 'len': 16, 'fieldType': 4, 'description': 'Serial Number'},
                '4': {'field': host_para.VENDOR_NAME, 'len': 8, 'fieldType': 5,
                      'description': 'Manufacturer(同Vendor Name)'},
                '5': {'field': cls.mfg_date, 'len': 13, 'fieldType': 6, 'description': 'Manufacture Date'},
                '6': {'field': host_para.VENDOR_NAME, 'len': 8, 'fieldType': 7, 'description': 'Vendor Name'},
                '7': {'field': host_para.PRODUCT_NAME, 'len': 16, 'fieldType': 8, 'description': 'Product Name'},
                '8': {'field': '', 'len': 0, 'fieldType': 9, 'description': 'SKU'},
                '9': {'field': '', 'len': 0, 'fieldType': 10, 'description': 'Version'},
                '10': {'field': '', 'len': 0, 'fieldType': 11, 'description': 'Asset Tag'},
                '11': {'field': '', 'len': 0, 'fieldType': 12, 'description': 'Description'},
                '12': {'field': '', 'len': 0, 'fieldType': 13, 'description': 'Eng Change Lvl'},
                '13': {'field': '', 'len': 0, 'fieldType': 14, 'description': 'Other_Info'},
                '14': {'field': '', 'len': 0, 'fieldType': 15, 'description': 'Vendor IANA'},
            },
        }
        if module_info_p1:
            exp_dict['record 1'] = {
                '0': {'field': '', 'len': 0, 'fieldType': 1, 'description': 'Vendor IANA'},
                '1': {'field': product_name, 'len': 64, 'fieldType': 2, 'description': '型号'},
                '2': {'field': fw_ver, 'len': 32, 'fieldType': 3, 'description': 'FW version'},
                '3': {'field': option_rom_ver, 'len': 32, 'fieldType': 4, 'description': 'OptionRom version'},
                '4': {'field': '2', 'len': 1, 'fieldType': 5, 'description': 'port num'},
                '5': {'field': identifier_p0, 'len': 16, 'fieldType': 6, 'description': 'p0类型'},
                '6': {'field': vendor_name_p0, 'len': 16, 'fieldType': 7, 'description': 'p0 vend0r Name'},
                '7': {'field': vendor_pn_p0, 'len': 16, 'fieldType': 8, 'description': 'p0型号规格'},
                '8': {'field': vendor_speed_p0, 'len': 8, 'fieldType': 9, 'description': 'p0连接速率'},
                '9': {'field': exp_addr0, 'len': 6, 'fieldType': 10, 'description': 'p0物理地址'},
                '10': {'field': identifier_p1, 'len': 16, 'fieldType': 11, 'description': 'p1类型'},
                '11': {'field': vendor_name_p1, 'len': 16, 'fieldType': 12, 'description': 'p1 vendor Name'},
                '12': {'field': vendor_pn_p1, 'len': 16, 'fieldType': 13, 'description': 'p1型号规格'},
                '13': {'field': vendor_speed_p1, 'len': 8, 'fieldType': 14, 'description': 'p1连接速率'},
                '14': {'field': exp_addr1, 'len': 6, 'fieldType': 15, 'description': 'p1物理地址'}
                }

        for record_key, record_dict in exp_dict.items():
            for field_index, field_dict in record_dict.items():
                description = field_dict['description']
                exp_value = field_dict['field']
                exp_len = field_dict['len']
                exp_type = field_dict['fieldType']
                record_index = record_key.split(' ')[1]
                rst_value = fru_dict[record_index]['Fields'][field_index]['field'].strip(
                )
                rst_len = int(
                    fru_dict[record_index]['Fields'][field_index]['fieldLength'], 16)
                rst_type = int(
                    fru_dict[record_index]['Fields'][field_index]['fieldType'], 16)
                if rst_len != exp_len or rst_type != exp_type or rst_value != exp_value:
                    CommonOperation.create_bug_problem(
                        # @changelog 2025.12.25 验证失败后,最后报错
                        cls, block=False,
                        key_word=cls.case_title,
                        description_word=f'校验PLDM_GetFruRecordTable接口{record_index} {description}参数',
                        expect_info=f'fieldType: {exp_type}; fieldLength: {exp_len}; field: {exp_value}',
                        result_info=f'fieldType: {rst_type}; fieldLength: {rst_len}; field: {rst_value}')

    @classmethod
    def get_product_name(cls, px):
        bus_info = EthtoolOperation.show_driver_infomation(
            cls.info_dict[list(cls.info_dict.keys())[px]]['network_name'], cls.exec_address)['bus-info']
        cmd = f"lspci -vvs {bus_info}"
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=cls.exec_address)
        log.info(f'执行结果：\n{output}')
        re_product_name = re.findall(
            r'\s*Product Name:\s*(.*)', output)
        if not re_product_name:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word='lspci获取Product Name',
                result_info='获取失败')
        product_name = re_product_name[0]
        return product_name

    @classmethod
    def get_version(cls, px, pf_bdf=None):
        if pf_bdf:
            cmd = f"{SCGBECLI64} -d {pf_bdf} show"
        else:
            cmd = f"{SCGBECLI64} -d {list(cls.info_dict.keys())[px]} show"
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=cls.exec_address)
        log.info(f'执行结果：\n{output}')
        rtn_dict = {}
        if 'Success' in output:
            rtn_dict['Firmware Version'] = re.findall(
                r'\s*Firmware Version\s*=\s*(.*)', output)[0].strip()
            rtn_dict['OptionRom Version'] = re.findall(
                r'\s*OptionRom Version\s*=\s*(.*)', output)[0].strip()
            return rtn_dict
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word='通过sxe2cli获取Fw和OptionRom的版本信息',
                result_info='获取失败')

    @classmethod
    def get_module_info(cls, px):
        try:
            module_info = {}
            # log.info(f'cls.info_dict:\n{json.dumps(cls.info_dict, indent=4)}')
            if px<len(list(cls.info_dict.keys())) and list(cls.info_dict.keys())[px] in cls.info_dict.keys():
                module_dict = EthtoolOperation.get_module_info(
                    cls.info_dict[list(cls.info_dict.keys())[px]]['network_name'], cls.exec_address)
                log.info(f'module_dict:\n{json.dumps(module_dict, indent=4)}')

                res_1 = re.findall(
                    r'\s*\w+\s*\((.*)\)', module_dict.get('Identifier', ''))
                if res_1:
                    module_info['Identifier'] = res_1[0]
                else:
                    module_info['Identifier'] = ''

                module_info['Vendor name'] = module_dict.get('Vendor name', '')
                module_info['Vendor PN'] = module_dict.get('Vendor PN', '')


                # res_2 = re.findall(
                #     r'\s*(\w+)', module_dict.get('Transceiver type', ''))
                transceiver = module_dict.get('Transceiver type', '')
                if type(module_dict.get('Transceiver type', '')) == list:
                    transceiver = ";".join(transceiver)
                res_2 = re.findall(r'\s*(\w+)', transceiver)
                if res_2:
                    module_info['speed'] = res_2[0]
                else:
                    module_info['speed'] = ''

                if module_info['Identifier'] == 'SFP':
                    module_info['Identifier'] = 'SFP+'
                return module_info
            else:
                return module_info
        except Exception:
            tracback_info = format_exc()
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word='ethtool -m 获取光模块信息失败',
                result_info=f'获取失败,错误信息：\n{tracback_info}')

    @classmethod
    def get_fw_version(cls, px=0):
        _, output_ori, _ = CommandOperation.execute_command_with_error(
            cmd=f'{SCGBECLI64} -d {list(cls.info_dict.keys())[px]} show', cmd_execute_address=cls.exec_address)
        # log.info(f'指令执行结果：\n{output_ori}')
        fw_version = re.findall(
            r'\s*Firmware Version\s*=\s*(.*)',
            output_ori)[0]
        return fw_version

    @classmethod
    def iperf(cls):
        server_ip = cls.test_device_info_dict['server_device_ip']
        client_ip = cls.test_device_info_dict['client_device_ip']
        cmd_s = f'iperf3 -s -D -B {server_ip} -p 5001'
        cmd_c = f'iperf3 -c {server_ip} -B {client_ip} -b 50G -P 10 -t 10000 -p 5001'

        log.info(f'server端执行指令：{cmd_s}')
        log.info(f'client端执行指令：{cmd_c}')
        rtn_code0, _, _ = CommandOperation.execute_command_with_error(
            cmd=cmd_s, cmd_execute_address=cls.exec_address)
        if rtn_code0 == RtnStatusEnum.FAIL.value:
            CommonOperation.create_bug_problem(
                cls, key_word=cls.case_title, description_word='启动server端iperf失败')

        rtn_code1, _, _ = CommandOperation.execute_command_with_error(
            cmd=cmd_c, cmd_execute_address=cls.exec_address_other)
        if rtn_code1 == RtnStatusEnum.FAIL.value:
            CommonOperation.create_bug_problem(
                cls, key_word=cls.case_title, description_word='启动client端iperf失败')
        log.info('打流完成')

    @classmethod
    def get_bootloader_active_area(cls, px_index=0):
        """
        根据 sxe2cli -d 0000:61:00.0 custom sxe2 version bootload命令,获取bootloader启动分区

        port 0000:61:00.0
        image ver   = 0.6.0.17
        boot ver    = V0.1.3
        commit id   = 214d7d3
        build time  = 2025-09-15 10:22
        sys run Region: MASTER
        """
        pf_bdf = list(cls.info_dict.keys())[px_index]
        cmd = f"{SCGBECLI64} -d {pf_bdf} custom sxe2 version bootload"  # | grep 'sys run Region:'
        status, output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=cls.exec_address)
        if status != RtnStatusEnum.SUCCESS.value or not output:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word='查看bootloader启动使用分区失败',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
        if "master" in output.lower():
            log.info(f"Device[{pf_bdf}]的bootloader当前使用分区:master")
            return 0
        elif "slave" in output.lower():
            log.info(f"Device[{pf_bdf}]的bootloader当前使用分区:slave")
            return 1
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word='查看bootloader启动使用分区失败,未能识别到当前使用分区',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
            return -1

    @classmethod
    def get_bootloader_next_area(cls, px_index=0):
        """
        根据 sxe2cli -d 0000:61:00.0 custom sxe2 version bootload命令,获取bootloader Flash存放的启动分区
        """
        pf_bdf = list(cls.info_dict.keys())[px_index]
        cmd = f"{SCGBECLI64} -d {pf_bdf} custom sxe2 version bootload"  # | grep 'flag from flash:'
        status, output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=cls.exec_address)
        if status != RtnStatusEnum.SUCCESS.value or not output:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word='查看bootloader下次启动使用分区失败',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
        if "0xa5a5" in output.lower():
            log.info(f"Device[{pf_bdf}]的bootloader下次启动使用分区:slave")
            return 1
        else:
            log.info(f"Device[{pf_bdf}]的bootloader下次启动使用分区:master")
            return 0

    @classmethod
    def get_fw_active_area(cls, px_index=0):
        """
        根据 scgbecli -d 0000:61:00.0 custom scgbe fwinfo命令,获取固件启动分区

        port 0000:61:00.0
        version    = 0.6.0.17
        commit id  = 7e93a32
        branch     = develop/rc/tucana-0.6.0_B017
        build time = 2025-10-11 15:27:02
        arch       = arm32
        build mode = debug
        current time: 2025-10-15 15:28:18
        uptime: 0 days,0 hours,2 minutes,10 seconds
        sys run Region: MASTER
        FW RST CNT: 19
        TERMLOG EXPORT STATUS: 0
        NIC RST CAUSE: PWR_RST
        NIC RST SECOND CAUSE: COREDUMP
        """
        pf_bdf = list(cls.info_dict.keys())[px_index]
        cmd = f"{SCGBECLI64} -d {pf_bdf} custom sxe2 fwinfo | grep 'sys run Region:'"
        status, output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=cls.exec_address)
        if status != RtnStatusEnum.SUCCESS.value or not output:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word='查看fw启动使用分区失败',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
        if "master" in output.lower():
            log.info(f"Device[{pf_bdf}]的固件当前使用分区:master")
            return 0
        else:
            log.info(f"Device[{pf_bdf}]的固件当前使用分区:slave")
            return 1

    @classmethod
    def get_fw_next_area(cls, px_index=0):
        """
        根据 sxe2cli -d 0000:61:00.0 custom sxe2 fwinfo命令,获取固件 Flash存放的启动分区
        """
        pf_bdf = list(cls.info_dict.keys())[px_index]
        cmd = f"{SCGBECLI64} -d {pf_bdf} custom sxe2 fwinfo | grep 'flag from flash:'"
        status, output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=cls.exec_address)
        if status != RtnStatusEnum.SUCCESS.value or not output:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word='查看固件下次启动使用分区失败',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
        if "0xa5a5" in output.lower():
            log.info(f"Device[{pf_bdf}]的固件下次启动使用分区:slave")
            return 1
        else:
            log.info(f"Device[{pf_bdf}]的固件下次启动使用分区:master")
            return 0

    @classmethod
    def check_startup(cls, px=0):
        # cmd = f'{SCGBECLI64} -d {list(cls.info_dict.keys())[px]} get reg type=A width=32 addr=0x02800040'
        # _, output, _ = CommandOperation.execute_command_with_error(
        #     cmd=cmd, cmd_execute_address=cls.exec_address)
        # # log.info(f'指令执行结果：\n{output}')
        # re_value = findall(r'0x02800040\s*\|\s*(\w+)\s*\|', output)
        # if re_value:
        #     value = int(re_value[0], 16)
        #     if value == 0x11:  # 11：主分区启动， 22：备份区启动
        #         return 0
        #     elif value == 0x22:
        #         return 1
        #     else:
        #         CommonOperation.create_bug_problem(
        #             cls,
        #             key_word=cls.case_title,
        #             description_word='查看fw启动分区',
        #             result_info=f'寄存器返回值非0x11或0x22')
        # else:
        CommonOperation.create_bug_problem(
            cls,
            key_word=cls.case_title,
            description_word='调用了错误的获取当前启动分区方法,需要修改脚本',
            result_info=f'查看相关寄存器失败')

    @classmethod
    def coredump(cls, px=0, dev_info=""):
        if dev_info:
            pass
        else:
            dev_info = list(cls.info_dict.keys())[px]
        cmd = f'{SCGBECLI64} -d {dev_info} custom sxe2 coredump trigger'
        _, outputs, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=cls.exec_address)
        # log.info(f'指令执行结果：\n{outputs}')
        if 'coredump status is:0' in outputs.lower():
            log.info(f"[{dev_info}]触发coredump成功")
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word=f'[{dev_info}]触发coredump失败')

    @classmethod
    def get_soc_temp(cls, px=0, bdf="") -> int:
        if not bdf:
            _, output, _ = CommandOperation.execute_command_with_error(
                cmd=f'{SCGBECLI64} -d {list(cls.info_dict.keys())[px]} show',
                cmd_execute_address=cls.exec_address)
        else:
            _, output, _ = CommandOperation.execute_command_with_error(
                cmd=f'{SCGBECLI64} -d {bdf} show',
                cmd_execute_address=cls.exec_address)
        log.info(f'指令返回结果:\n{output}')
        re_temp = findall(
            r'\s*SOC Temperature \(Degree Celsius\)\s*=\s*(\w+)', output)
        if not re_temp:
            CommonOperation.create_bug_problem(
                cls, key_word=cls.bug_title,
                description_word='cli指令获取芯片温度失败')
        return int(re_temp[0])

    @classmethod
    def cli_show_termlog(cls, px, check_code=True):
        termlog_path = '/root/termlog'
        CommandOperation.execute_command_with_error(
            cmd=fr'rm -rf {termlog_path}',
            cmd_execute_address=cls.exec_address
        )
        _, termlog_output, _ = CommandOperation.execute_command_with_error(
            cmd=f'{SCGBECLI64} -d {list(cls.info_dict.keys())[px]} show termlog all file={termlog_path}',
            cmd_execute_address=cls.exec_address
        )
        # log.info(f'指令执行结果：\n{termlog_output}')
        if not re.findall(r'Status\s+=\s+Success', termlog_output):
            CommonOperation.create_bug_problem(
                cls, key_word=cls.bug_title,
                description_word='show termlog all 指令执行失败')
        _, output_check, _ = CommandOperation.execute_command_with_error(
            cmd=f'python3 {CHECK_ENCODE} {termlog_path}',
            cmd_execute_address=cls.exec_address)
        # log.info(f'指令执行结果：{output_check}')
        code = int(re.findall(r'\d+', output_check)[0])
        if code == 0:
            log.info('日志文件没有缺失和乱码')
        elif code & 0b01:
            CommonOperation.create_bug_problem(
                cls,
                key_word='CLI',
                description_word='导出日志文件包含乱码')
        elif code & 0b10:
            if check_code:
                CommonOperation.create_bug_problem(
                    cls,
                    key_word='CLI',
                    description_word='导出日志有缺失')
            else:
                log.info('导出日志有缺失')

    @classmethod
    def modify_xml(cls, xml_path, tags, value):
        cmd_xml = f'python3 {constants.MODIFY_XML} {xml_path} {tags} {value}'
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd_xml, cmd_execute_address=cls.exec_address)
        # log.info(f'指令执行结果：\n{rtn_output}')
        re_status = re.findall(r'status:\s*(\d+)', rtn_output)
        if re_status:
            log.info('xml文件修改成功')
            _, rtn_cat, _ = CommandOperation.execute_command_with_error(
                cmd=f'cat {xml_path}', cmd_execute_address=cls.exec_address)
            print(rtn_cat)
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word='修改xml文件失败')

    @classmethod
    def modify_xml_and_make_pkg(cls, xml_path, tags, value, input_bin_path, no_ver_chk):
        CommonOperation.concat_test_steps(f'2.{cls.do_step} 修改xml文件')
        cls.do_step += 1
        cmd_xml = f'python3 {constants.MODIFY_XML} {xml_path} {tags} {value}'
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd_xml, cmd_execute_address=cls.exec_address)
        # log.info(f'指令执行结果：\n{rtn_output}')
        re_status = re.findall(r'status:\s*(\d+)', rtn_output)
        if re_status:
            log.info('xml文件修改成功')
            _, rtn_cat, _ = CommandOperation.execute_command_with_error(
                cmd=f'cat {xml_path}', cmd_execute_address=cls.exec_address)
            print(rtn_cat)
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word=cls.case_title,
                description_word='修改xml文件失败')

        CommonOperation.concat_test_steps(
            f'2.{cls.do_step} 使用改后的xml文件生成加头的 .bin文件')
        cls.do_step += 1
        status, bin_path = CommonCli.xml2bin(xml_path=xml_path, input_bin=input_bin_path,
                                             output_bin='header_pkg.bin', exec_addr=cls.exec_address)
        if status is False:
            CommonOperation.create_bug_problem(
                cls,
                key_word='CLI',
                description_word=f'使用合法的xml文件生成bin文件，生成失败')

        CommonOperation.concat_test_steps(
            f'2.{cls.do_step} 使用加头的.bin文件生成cli升级包')
        cls.do_step += 1
        cli_pkg_path = CommonCli.make_package(
            cls.exec_address,
            bin_path)

        return cls.cli_pkg_to_pldm_pkg(cli_pkg_path, no_ver_chk)

    @classmethod
    def check_log_persistence(cls, px, value, eid=None, input_bin_path=constants.HEADER_USERDEFAULT_BIN):
        if not eid:
            eid = cls.bmc_eid
        pkg_path = cls.modify_xml_and_make_pkg(
            xml_path=constants.SXEOEM_XML,
            tags=constants.XML_PARA_LOGPERSISTON,
            value=value,
            input_bin_path=input_bin_path,
            no_ver_chk=1
        )

        CommonOperation.concat_test_steps(f'2.{cls.do_step} 通过pldm升级')
        cls.do_step += 1
        PldmTool.firmware_upgrade(
            eid=eid,
            ip=cls.bmc_ip,
            pkg_path=pkg_path,
            px=px,
            skip_ip=cls.client_ip,
            execute_addr=cls.exec_address
        )

        CommonOperation.concat_test_steps(f'2.{cls.do_step} 重启固件，重启主机，重启BMC')
        cls.do_step += 1
        CommonTools.reset_and_reboot(cls.exec_address)
        CommonTools.reboot_bmc(ip=cls.bmc_ip, execute_addr=cls.exec_address)

        CommonOperation.concat_test_steps(f'2.{cls.do_step} 执行导出全部日志指令')
        cls.do_step += 1
        # PldmTool.get_oem_log(
        #     eid=eid,
        #     ip=cls.bmc_ip,
        #     log_type=1,
        #     execute_addr=cls.exec_address,
        #     caller_class=cls
        # )
        PldmTool.new_bmc_get_oem_log_and_check(
            caller_class=cls,
            eid=eid,
            bmc_ip=cls.bmc_ip,
            execute_addr=cls.exec_address
        )

        CommonOperation.concat_test_steps(f'2.{cls.do_step} 执行20次cli show指令')
        cls.do_step += 1
        count = 20
        while count:
            CommandOperation.execute_command_with_error(
                cmd=f"{SCGBECLI64} show", cmd_execute_address=cls.exec_address
            )
            count -= 1

        CommonOperation.concat_test_steps(f'2.{cls.do_step} 执行导出全部日志指令')
        cls.do_step += 1
        # size = PldmTool.get_oem_log(
        #     eid=eid,
        #     ip=cls.bmc_ip,
        #     log_type=1,
        #     execute_addr=cls.exec_address,
        #     caller_class=cls
        # )
        PldmTool.new_bmc_get_oem_log_and_check(
            caller_class=cls,
            eid=eid,
            bmc_ip=cls.bmc_ip,
            execute_addr=cls.exec_address
        )
        return None

    @classmethod
    def modify_txt(cls, deversion):
        _, cat_output, _ = CommandOperation.execute_command_with_error(
            cmd=f'cat {constants.BOOTLOADER_TXT} | grep image_version',
            cmd_execute_address=cls.exec_address
        )
        # log.info(f'指令执行结果：\n{cat_output}')
        re_ori_version = re.findall(r'image_version\s*=\s*(\w+)', cat_output)
        if not re_ori_version:
            CommonOperation.create_bug_problem(
                cls, key_word='BMC',
                description_word='未找到header_config_sxe_fw_bootloader.txt或文件中不包含image_version'
            )
        ori_version = re_ori_version[0]
        if deversion:
            cls.ori_version = ori_version
            new_version = '0x' + format(int(ori_version, 16) - 0x100, '06x')
        else:
            new_version = cls.ori_version
        CommandOperation.execute_command_with_error(
            cmd=f"sed -i 's/{ori_version}/{new_version}/g' {constants.BOOTLOADER_TXT}",
            cmd_execute_address=cls.exec_address
        )
        _, cat_output, _ = CommandOperation.execute_command_with_error(
            cmd=f"cat {constants.BOOTLOADER_TXT}",
            cmd_execute_address=cls.exec_address
        )
        # log.info(f'指令执行结果：\n{cat_output}')

    @classmethod
    def make_degrade_pkg(cls, no_ver_chk):
        # 修改txt文件版本号
        CommonOperation.concat_test_steps(f'2.{cls.do_step} 查看当前bootloader主分区版本号')
        cls.do_step += 1
        _, ver_output, _ = CommandOperation.execute_command_with_error(
            cmd=f'{SCGBECLI64} -d {list(cls.info_dict.keys())[0]} custom sxe regionVer id=0'
        )

        CommonOperation.concat_test_steps(f'2.{cls.do_step} 修改txt文件版本号')
        cls.do_step += 1
        cls.modify_txt(deversion=True)

        CommonOperation.concat_test_steps(f'2.{cls.do_step} 加头')
        cls.do_step += 1
        CliCommonUtils.add_header(RegionEnum.UBOOT.value)
        _, find_output, _ = CommandOperation.execute_command_with_error(
            cmd=f'find {constants.HEADER_UBOOT_OUTPUT}',
            cmd_execute_address=cls.exec_address
        )
        if constants.HEADER_UBOOT_OUTPUT not in find_output:
            CommonOperation.create_bug_problem(
                cls, key_word='BMC', description_word='生成加头bin文件失败'
            )

        CommonOperation.concat_test_steps(f'2.{cls.do_step} 打包')
        cls.do_step += 1
        cli_pkg_path = CommonCli.make_package(
            cls.exec_address,
            constants.HEADER_UBOOT_OUTPUT,
            constants.HEADER_NVDATA_BIN,
            constants.HEADER_USERDEFAULT_BIN,
            constants.HEADER_FW_BIN,
            constants.HEADER_OPROM_BIN
        )

        return cls.cli_pkg_to_pldm_pkg(cli_pkg_path, no_ver_chk)

    @classmethod
    def cli_pkg_to_pldm_pkg(cls, cli_pkg_path, no_ver_chk):
        return '/root/sxe_pldm_image.bin'
        # CommonOperation.concat_test_steps(f'2.{cls.do_step} 使用cli升级包生成pldm升级包')
        # cls.do_step += 1
        # CommandOperation.execute_command_with_error(
        #     cmd='rm -rf /root/sxe_pldm_image.bin',
        #     cmd_execute_address=cls.exec_address
        # )
        # image_path = CommonOperation.get_full_path(
        #     UPGRADE_IMAGE_PACKAGE_PATH, cls.exec_address)
        # version = re.findall(r'Image_(.*)_NIC-1160-2X', image_path)[0]
        # host_para = HostPara()
        # cmd_pldm_pkg = (
        #     f'cd; python3 {constants.SXE_PLDM_PACKAGE_PY} {cli_pkg_path} sxe_pldm_image.bin '
        #     f'{no_ver_chk} {version} {host_para.VENDOR_ID} {constants.DEVICE_ID1}')
        # _, pldm_pkg_output, _ = CommandOperation.execute_command_with_error(
        #     cmd=cmd_pldm_pkg, cmd_execute_address=cls.exec_address)
        # # log.info(f'指令执行结果：\n{pldm_pkg_output}')
        # _, find_pkg, _ = CommandOperation.execute_command_with_error(
        #     cmd='find /root/sxe_pldm_image.bin',
        #     cmd_execute_address=cls.exec_address
        # )
        # if 'sxe_pldm_image.bin' in find_pkg:
        #     log.info('生成pldm升级包成功')
        #     return '/root/sxe_pldm_image.bin'
        # else:
        #     CommonOperation.create_bug_problem(
        #         cls,
        #         key_word='BMC',
        #         description_word='生成pldm升级包失败'
        #     )

    @classmethod
    def check_oem_fru(cls, eid):
        status, rtn_dict = PldmTool.oem_get_fru(eid, ip=cls.bmc_ip, execute_addr=cls.exec_address)
        if status != '0':
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='获取OEM_FRU 失败'
            )
        exp_chann_num = '2'
        exp_nic_state = '48'
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd=f'{SCGBECLI64} -d {list(cls.info_dict.keys())[0]} show mfginfo', cmd_execute_address=cls.exec_address
        )
        exp_pn = re.findall(fr'Part Number\s+\|(\S+)\s+\|', output)[0]
        exp_sn = re.findall(fr'Serial Number\s+\|(\S+)\s+\|', output)[0]
        exp_port_dict = defaultdict(dict)
        exp_fw_ver = ''
        exp_opt_ver = ''
        for px in 'range(2)':
            _, output, _ = CommandOperation.execute_command_with_error(
                cmd=f'{SCGBECLI64} -d {list(cls.info_dict.keys())[0]} show mfginfo', cmd_execute_address=cls.exec_address
            )
            exp_fw_ver = re.findall(fr'Firmware Version\s+=\s+(\S+)', output)[0]
            exp_opt_ver = re.findall(fr'OptionRom Version\s+=\s+(\S+)', output)[0]
            if re.findall(r'SFP Information Acquisition Status\s+=\s+Successful', output):
                exp_port_dict[px]['isAbs'] = '1'
                module_info = cls.get_module_info(px)
                exp_port_dict[px]['moduleType'] = module_info['Identifier']
                exp_port_dict[px]['modulePn'] = module_info['Vendor PN']
                exp_port_dict[px]['specSpeed'] = '3'
                exp_port_dict[px]['linkSpeed'] = '3'
                exp_port_dict[px]['linkState'] = re.findall(fr'Link Status\s+=\s+(\d+)', output)[0]
        rtn_chann_num = rtn_dict['channalNum']
        rtn_nic_state = rtn_dict['nicState']
        rtn_pn = rtn_dict['pn']
        rtn_sn = rtn_dict['sn']
        rtn_fw_ver = rtn_dict['fw version']
        rtn_opt_ver = rtn_dict['optionRom version']
        rtn_port_dict = defaultdict(dict)
        rtn_port_dict[0] = rtn_dict['0']
        rtn_port_dict[1] = rtn_dict['1']
        del rtn_port_dict[0]['portTemp']
        del rtn_port_dict[1]['portTemp']

        if rtn_chann_num != exp_chann_num:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='OEM_FRU channal num 不符合预期',
                expect_info=exp_chann_num, result_info=rtn_chann_num
            )
        if rtn_nic_state != exp_nic_state:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='OEM_FRU nic_state 不符合预期',
                expect_info=exp_nic_state, result_info=rtn_nic_state
            )
        if rtn_pn != exp_pn or rtn_sn != exp_sn:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='OEM_FRU pn/sn 不符合预期',
                expect_info=str([exp_pn, exp_sn]), result_info=str([rtn_pn, rtn_sn])
            )
        if rtn_fw_ver != exp_fw_ver or rtn_opt_ver != exp_opt_ver:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='OEM_FRU version 不符合预期',
                expect_info=str([exp_fw_ver, exp_opt_ver]), result_info=str([rtn_fw_ver, rtn_opt_ver])
            )
        if rtn_port_dict != exp_port_dict:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='OEM_FRU port info 不符合预期',
                expect_info=str(rtn_port_dict), result_info=str(exp_port_dict)
            )


if __name__ == '__main__':
    BmcScriptBase.run()
    # BmcScriptBase.new_check_fru_info(device_info="0000:21:00.0", fru_dict="")
