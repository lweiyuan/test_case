#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      xiangyu.liu
date:        2025.07.10
description: BMC公共方法
"""
import copy
import datetime
import json
import math
import os
import re
import time
from abc import ABC
from enum import Enum
from re import findall, finditer

import paramiko

import add_syspath
from scripts.script_libs import log, constants
from scripts.script_libs.cli_operation import CliOperation
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse
from scripts.script_libs.common_operation import CommonOperation, CommandOperation, EthtoolOperation
from scripts.script_libs.constants import BMC_PWD, BMC_NAME, BMC_TOOL_PATH, BMC_LOG_PATH, \
    PATTERN_UART_TABLE_CONTENT_SHOW_REG, VENDOR_ID_NAME, RELEASE_VERSION, NOR_FLASH_PKG_PATH, PS3_MAKE_PACKAGE, \
    XML_FOLDER, XML2BIN, UNLINK_REBOOT_FLAG, BOOTLOADER_TXT, ADD_HEADER_DIR, USER_ADD_HEADER, \
    BOOTLOADER_BIN, SCGBECLI64, BMC_NAME_INTEL, BMC_PWD_INTEL, BMC_TOOL_PATH_BUSCTL, BMC_TOOL_PATH_MCTPAPP, \
    DRV_SCGBE_PF, DRV_SCGBE_VF
from scripts.script_libs.constants import CHECK_ENCODE, BMC_EVT_FILE
from scripts.script_libs.constants import SERIAL_CLI_PY, NIC_BMC_OPERATION_SH  # UPGRADE_IMAGE_PACKAGE_PATH,
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum, RegionEnum, FwLogLevel
from scripts.script_libs.file_operation import FileOperation
from scripts.script_libs.host_operation import HostOperation
from scripts.script_libs.script_base import ScriptBase
import random
import functools
from collections import defaultdict

from scripts.script_libs.socket_operation import SocketOption

BUSCTL = False
DEBUG_NOT_SUPPORT_0609 = False
# 与bmc交互命令时，默认循环等待最大时间(s)
DEFAULT_TIME_WAIT_FOR_CMD_LOOP_RET = 300
# 与bmc交互命令时，默认等待超时时间(s)
DEFAULT_TIME_WAIT_FOR_CMD_RET = 300
mctp_cmd_para = "busctl call xyz.openbmc_project.MCTP-pcie /xyz/openbmc_project/mctp xyz.openbmc_project.MCTP.Base SendReceiveMctpMessagePayload yayq "

bmc_fw_state_dict = {
    '未初始化S': ["0x00", "0x00"],
    '先期初始化': ["0x10", "0x10001"],
    '设备扫描': ["0x20", "0x10020"],
    '初始化完成': ["0x30", "0x20000"],
    '升级中': ["0x31", "0x20001"],
    '运行异常,Core dump0': ["0x40", "0x30001"],
    '运行异常,Core dump1': ["0x50", "0x30002"],
    '运行异常,从核心跳': ["0x60", "0x30003"],
}
# soc fatal温度阈值范围
temp_limit_list = [82, 105]  # [50, 105]
temp_low_limit_list = [-40, 0]

class MctpMsgType(Enum):
    Control = '0x00'
    PLDM = '0x01'
    NCSI = '0x02'
    VendorPCI = '0x7E'
    VendorIANA = '0x7F'


class MctpCtlCmdNum(Enum):
    SetEID = '0x01'
    GetEID = '0x02'
    GetEUUID = '0x03'
    GetMCTPVerSupport = '0x04'
    GetMsgTypeSupport = '0x05'
    GetVDMSupport = '0x06'
    ResolveEID = '0x07'


class MctpCtlMsgCompCodes(Enum):
    SUCCESS = '0x00'
    ERROR = '0x01'
    ERROR_INVALID_DATA = '0x02'
    ERROR_INVALID_LENGTH = '0x03'
    ERROR_NOT_READY = '0x04'
    ERROR_UNSUPPORTED_CMD = '0x05'


class MctpMsgFieldName(Enum):
    IC = 'IC'
    MsgType = 'Message_type'
    Rq = 'Rq_bit'
    D = 'D_bit'
    InsId = 'Instance_ID'
    CmdCode = 'Command_Code'
    CompCode = 'Completion_Code'
    MsgData = 'Message_Data'

class PldmMsgFieldName(Enum):
    IC = 'IC'
    MsgType = 'Message_type'
    Rq = 'Rq_bit'
    D = 'D_bit'
    InsId = 'Instance_ID'
    HdrVer = 'Hdr_Ver'
    PLDMType = 'PLDM_Type'
    CmdCode = 'PLDM_Command_Code'
    CompCode = 'PLDM_Completion_Code'
    MsgData = 'Message_Data'

class PldmTypes(Enum):
    Type0 = 0
    Type2 = 2
    Type4 = 4
    Type5 = 5
    Type3f = 0x3f

class PldmType0CmdCodes(Enum):
    SetTID = '0x01'
    GetTID = '0x02'
    GetPLDMVersion = '0x03'
    GetPLDMTypes = '0x04'
    GetPLDMCommands = '0x05'


class PldmType2CmdCodes(Enum):
    SetTID = '0x01'
    GetTID = '0x02'
    GetTerminusUID = '0x03'
    SetEventReceiver = '0x04'
    GetEventReceiver = '0x05'
    PlatFormEventMessage = '0x0A'  # TODO 工具暂不支持
    # SetNumericSensorEnable = '0x10'  # 不支持
    GetSensorReading = '0x11'
    GetSensorThresholds = '0x12'
    SetSensorThresholds = '0x13'
    GetStateSensorReading = '0x21'
    SetNumericEffecterValue = '0x31'


class PldmType4CmdCodes(Enum):
    GetFRURecordTableMetadata = '0x01'
    GetFRURecordTable = '0x02'
    # SetFRURecordTable = '0x03'
    # SetFRURecordByOption = '0x04'


class PldmType5CmdCodes(Enum):
    FwUpgrade = '0x00'  # TODO 工具暂不支持


class PldmType3fCmdCodes(Enum):
    GetOemLog = '0x01'  # TODO 工具暂不支持


class ProductType(Enum):
    G50 = 'G50'
    G40 = 'G40'

class CpuType(Enum):
    INTEL = 'Intel'
    Teston = 'Teston'
    Testles = 'MDA'


class BmcEnvInfo(object):
    product_type = ''
    cpu_type= ''
    bmc_user_name= '*******'
    bmc_passwd= '*********'
    bmc_tool= ''
    info_dict = {}

    @classmethod
    def get_product_type(cls, exec_address):
        _, output_dmi, _ = CommandOperation.execute_command_with_error(
            cmd="dmidecode | grep 'Product Name'", cmd_execute_address=exec_address
        )
        if '50' in output_dmi:
            return ProductType.G50.value
        else:
            return ProductType.G40.value

    @classmethod
    def get_cpu_type(cls, exec_address):
        _, output_cpu, _ = CommandOperation.execute_command_with_error(
            cmd="lscpu | grep 'Model name'", cmd_execute_address=exec_address
        )
        if 'MDA' in output_cpu:
            return CpuType.MDA.value
        elif 'Intel' in output_cpu:
            return CpuType.INTEL.value
        elif 'INTEL' in output_cpu:
            return CpuType.INTEL.value
        elif 'Teston' in output_cpu:
            return CpuType.Teston.value
        else:
            # 未能识别的环境,默认为Teston环境，可测试
            return CpuType.Teston.value

    @classmethod
    def update_bmc_login_info(cls):
        if cls.product_type == ProductType.G50.value:
            if cls.cpu_type == CpuType.MDA.value:
                cls.bmc_user_name = BMC_NAME_INTEL
                cls.bmc_passwd = BMC_PWD_INTEL
            elif cls.cpu_type == CpuType.INTEL.value:
                cls.bmc_user_name = BMC_NAME_INTEL
                cls.bmc_passwd = BMC_PWD_INTEL
            elif cls.cpu_type == CpuType.Teston.value:
                cls.bmc_user_name = BMC_NAME
                cls.bmc_passwd = BMC_PWD
            else:
                cls.bmc_user_name = BMC_NAME
                cls.bmc_passwd = BMC_PWD
        else:
            cls.bmc_user_name = BMC_NAME
            cls.bmc_passwd = BMC_PWD

    @classmethod
    def update_bmc_tool(cls):
        if cls.product_type == ProductType.G50.value:
            if cls.cpu_type == CpuType.MDA.value:
                cls.bmc_tool = BMC_TOOL_PATH_MCTPAPP
            elif cls.cpu_type == CpuType.INTEL.value:
                cls.bmc_tool = BMC_TOOL_PATH_MCTPAPP
            elif cls.cpu_type == CpuType.Teston.value:
                cls.bmc_tool = BMC_TOOL_PATH_BUSCTL
            else:
                cls.bmc_tool = BMC_TOOL_PATH_BUSCTL
        else:
            cls.bmc_tool = BMC_TOOL_PATH_MCTPAPP
        _, output_cpu, _ = CommandOperation.execute_command_with_error(
            cmd=f"/bin/cp {cls.bmc_tool} {BMC_TOOL_PATH}", cmd_execute_address=CmdExecuteAdressEnum.SERVER.value
        )

    @classmethod
    def update_info_dict(cls, info_dict: dict):
        cls.info_dict = copy.deepcopy(info_dict)


def retry(para_eid, para_ip, para_exec):
    def decorator(method):
        @functools.wraps(method)
        def wrapper(cls, *args, **kwargs):
            status, value = method(cls, *args, **kwargs)
            if int(status) == -8:
                cmd = f'{BMC_TOOL_PATH} -e {kwargs[para_eid]} -m 1  -t 2 -c 3 --addr={kwargs[para_ip]} ' \
                      f'--name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
                _, rtn_output, _ = CommandOperation.execute_command_with_error(
                    cmd=cmd, cmd_execute_address=kwargs[para_exec])
                if findall(r'status:(\W*\w+)', rtn_output)[0] == '0':
                    return status, value
                depth = 5
                while depth:
                    log.info(f'BMC与卡建链异常，尝试重启BMC重连{6 - depth}次')
                    CommonTools.reboot_bmc(ip=kwargs[para_ip], execute_addr=kwargs[para_exec])
                    status, value = method(cls, *args, **kwargs)
                    if int(status) != '-8':
                        break
                    else:
                        depth -= 1
            return status, value

        return wrapper

    return decorator


class CommonTools(ScriptBase, ABC):
    bmc_ip = ''
    bmc_ssh_username = CommandLineArgsParse.get_server_bmc_uname()
    bmc_ssh_password = CommandLineArgsParse.get_server_bmc_passwd()

    @classmethod
    def get_bmc_ip(cls, execute_addr):
        if not cls.bmc_ip:
            cmd = 'ipmitool lan print 1'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'bmc IP 信息：\n{rtn_output}')
            bmc_ip = findall(r'IP Address\s*:\s*(\d+\.\d+\.\d+\.\d+)', rtn_output)
            if bmc_ip:
                cls.bmc_ip = bmc_ip[0]
                log.info(f'取得BMC IP：{cls.bmc_ip}')
                return cls.bmc_ip
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='获取BMC IP',
                    result_info='获取BMC IP失败',
                    expect_info='获取BMC IP成功',
                )
        else:
            log.info(f'取得BMC IP：{cls.bmc_ip}')
            return cls.bmc_ip

    @classmethod
    def get_bmc_eid_list(cls, ip, execute_addr, wait_max_count=5, interval=5) -> list:
        """
        author: gaoyb
        date  : 2025.11.06
        description: 获取BMC下所有上报的EID
        :param ip: bmc ip
        :param execute_addr: 命令下发地址
        :param wait_max_count: 最大搜索次数
        :param interval: 两次搜索之间的间隔时间
        :return: 获取到的eid列表, 16进制
        """
        bmc_user_name = BmcEnvInfo.bmc_user_name if BmcEnvInfo.bmc_user_name else constants.BMC_NAME
        bmc_passwd = BmcEnvInfo.bmc_passwd if BmcEnvInfo.bmc_passwd else constants.BMC_PWD

        _, output_cpu, _ = CommandOperation.execute_command_with_error(
            cmd="lscpu | grep 'Model name'", cmd_execute_address=execute_addr
        )

        # 外网环境,开启3322端口
        if CommandLineArgsParse.get_test_port() == 3322:
            log.info(f'配置bmc开放3322端口')
            cmd = f"sshpass -p {bmc_passwd} ssh -p 22 {bmc_user_name}@{ip} '/usr/sbin/dropbear -B -p 3322 -I 600'"
            CommandOperation.execute_command_with_error(cmd)

        eid_list = list()
        count = 0
        while count < wait_max_count:
            # 获取eid
            if 'Teston' in output_cpu:
                cmd = f'busctl tree xyz.openbmc_project.MCTP-pcie'
                status, rtn_output, _ = CommonTools.send_bmc_command(ip=ip, cmd=cmd)
                result_list = re.findall(r"/xyz/openbmc_project/mctp/device/(\d+)", rtn_output, flags=re.I)
                if status != RtnStatusEnum.SUCCESS.value or not rtn_output or not result_list:
                    log.error("本次获取bmc eid失败,cmd:{},status:{},result:\n{}".format(cmd, status, rtn_output))

                else:
                    eid_list = result_list

            elif 'Intel' in output_cpu or 'INTEL' in output_cpu:
                cmd = f'{BMC_TOOL_PATH} -m 0 -c 0xff --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
                _, rtn_output, _ = CommandOperation.execute_command_with_error(
                    cmd=cmd, cmd_execute_address=execute_addr)
                log.info(f'获取所有BMC EID 结果：\n{rtn_output}')
                if 'MCTP Device count' not in rtn_output:
                    CommonOperation.create_bug_problem(cls,
                                                       key_word='BMC',
                                                       description_word='获取所有BMC EID失败',
                                                       result_info='获取所有BMC EID失败',
                                                       expect_info='获取所有BMC EID成功')
                info_lst = findall(r'Medium Type[\s\S]*?Is Static EID', rtn_output)
                for info in info_lst:
                    msg_type = findall(r'Message Types\s*:\s*(\w*)', info)[0]
                    if 'MCTP' not in msg_type:
                        continue
                    else:
                        eid_list = findall(r'Endpoint ID\s*:\s*(\w*)', info)[0]
                        count = 5
                        log.info(f'检查eid是否可通信，若不可通信，尝试重启bmc')
                        while count:
                            for eid in eid_list:
                                status, uuid = PldmTool.get_uuid(eid=eid, ip=ip, execute_addr=execute_addr)
                                if status == '-8':
                                    CommonTools.reboot_bmc(ip=ip, execute_addr=execute_addr)
                                    CommonTools.time_sleep(5)
                                    count -= 1
                                else:
                                    break
            # 获取到eid
            if eid_list:
                log.info(f'获取到的eid:{eid_list}')
                eid_list = [hex(int(i)) for i in eid_list]
                log.info(f'转换成16进制的eid:{eid_list}')
                break
            # 未获取到eid
            else:
                CommonTools.time_sleep(interval)
                count += 1

        if not eid_list:
            log.info("未获取到eid, return empty list: []")
        return eid_list

    @classmethod
    def get_eid_by_uuid(cls, uuid, bmc_ip=CommandLineArgsParse.get_server_bmc_ip(),
                             execute_addr=CmdExecuteAdressEnum.SERVER.value,
                             wait_max_count=1, interval=5):
        bmc_eid_list = cls.get_bmc_eid_list(ip=bmc_ip, execute_addr=execute_addr, wait_max_count=wait_max_count,
                                            interval=interval)
        if not bmc_eid_list:
            MctpTools.restart_mctp_service(bmc_ip=cls.bmc_ip)
            log.info("未找到任何EID, 重启bmc_mctp服务,休眠90秒后,重新收集网卡集eid信息")
            time.sleep(90)
            bmc_eid_list = cls.get_bmc_eid_list(ip=bmc_ip, execute_addr=execute_addr, wait_max_count=wait_max_count,
                                                interval=interval)
            CommonOperation.create_bug_problem(cls,
                                               key_word='通过UUID与EID对应',
                                               description_word='没有获取到BMC EID',
                                               result_info='获取BMC EID失败',
                                               expect_info='获取BMC EID成功')
        for eid in bmc_eid_list:
            status_pldm, uuid_pldm = PldmTool.get_uuid(
                ip=bmc_ip, eid=eid, execute_addr=CmdExecuteAdressEnum.SERVER.value, create_bug=False)
            if uuid_pldm and uuid_pldm.strip() == uuid:
                return eid
        if len(bmc_eid_list) == 1:
            log.error(F"未能正确通过设备的uuid[{uuid}]获取BMC EID,当前为单卡环境,直接返回该EID[{bmc_eid_list[0]}]")
            CommonOperation.create_bug_problem(cls, block=False,
                                               key_word=f'单卡环境,通过设备的uuid[{uuid}]获取BMC EID',
                                               description_word='获取失败',
                                               result_info='获取到的EID:{}'.format(bmc_eid_list),
                                               expect_info='对应成功')
            return bmc_eid_list[0]
        CommonOperation.create_bug_problem(cls,
                                           key_word=f'通过设备的uuid[{uuid}]获取BMC EID',
                                           description_word='获取失败',
                                           result_info='获取到的EID:{}'.format(bmc_eid_list),
                                           expect_info='对应成功')
        return ""


    @classmethod
    def get_env_bmc_eid_info(cls, test_device_info_list: list,
                             bmc_ip=CommandLineArgsParse.get_server_bmc_ip(),
                             execute_addr=CmdExecuteAdressEnum.SERVER.value,
                             wait_max_count=1, interval=5) -> dict:
        """
        author: gaoyb
        date  : 2025.11.21
        description: 获取环境中的卡和bmc_eid的对应信息
        :param test_device_info_list:
        :param bmc_ip: bmc ip
        :param execute_addr: 命令下发地址
        :param wait_max_count: 最大搜索次数
        :param interval: 两次搜索之间的间隔时间
        :return: 获取环境中的卡和bmc_eid的对应信息,dict()
        """

        # 获取eid
        bmc_eid_list = cls.get_bmc_eid_list(ip=bmc_ip, execute_addr=execute_addr, wait_max_count=wait_max_count, interval=interval)

        # pf数量
        port_list = [i["server_pf_device_name"] for i in test_device_info_list]
        # 实际网卡数量,每个网卡只上报一个eid
        nic_list = set([i[:-1] for i in port_list])
        log.info(f'port列表: {port_list} 卡列表: {nic_list}')
        if not bmc_eid_list:
            MctpTools.restart_mctp_service(bmc_ip=cls.bmc_ip)
            log.info("未找到任何eid, 重启bmc_mctp服务,休眠90秒后,重新收集网卡集eid信息")
            time.sleep(90)
            bmc_eid_list = cls.get_bmc_eid_list(ip=bmc_ip, execute_addr=execute_addr, wait_max_count=wait_max_count,
                                                interval=interval)
            CommonOperation.create_bug_problem(cls,
                                               key_word='将卡与BMC_EID对应',
                                               description_word='没有获取到BMC EID',
                                               result_info='获取BMC EID失败',
                                               expect_info='获取BMC EID成功')
        default_eid = bmc_eid_list[-1]
        info_dict = {}
        # 单卡测试环境
        if len(nic_list) == 1:
            log.info("单卡环境")
            for device_info in test_device_info_list:
                bdf = device_info["server_bus_info"]
                info_dict[bdf] = dict()

                info_dict[bdf]['network_name'] = device_info["server_pf_device_name"]
                info_dict[bdf]['eid'] = default_eid
                info_dict[bdf]["pf_index"] = int(bdf.split(".")[-1])
                uuid = CliOperation.get_cli_show_fw_info(caller_class=cls, device=bdf)["Base UUID"].lower()
                info_dict[bdf]["uuid"] = uuid
                # 如果bmc_eid数量大于1
                if len(bmc_eid_list) > 1:
                    log.info("单卡测试环境,发现多个eid,进行UUID适配查找")
                    for eid in bmc_eid_list:
                        status_pldm, uuid_pldm = PldmTool.get_uuid(
                            ip=bmc_ip, eid=eid, execute_addr=CmdExecuteAdressEnum.SERVER.value, create_bug=False)
                        if uuid_pldm and uuid == uuid_pldm:
                            info_dict[bdf]['eid'] = eid
                            log.info(f"找到了,bdf[{bdf}]的eid为[{eid}]")
                            return info_dict
        # 多卡测试环境
        else:
            if len(bmc_eid_list) < len(nic_list):
                log.error(f"{len(nic_list)}个卡的测试环境,"
                         f"只在BMC侧找到{len(bmc_eid_list)}个eid:{bmc_eid_list},环境异常")
                CommonOperation.create_bug_problem(cls,
                                                   key_word='将卡与BMC_EID对应',
                                                   description_word=f"{len(nic_list)}个卡的测试环境,只在BMC侧找到{len(bmc_eid_list)}个eid:{bmc_eid_list},环境异常",
                                                   result_info='获取BMC EID失败',
                                                   expect_info='获取BMC EID成功')
            log.info("多卡环境")
            for device_info in test_device_info_list:
                bdf = device_info["server_bus_info"]
                info_dict[bdf] = dict()

                info_dict[bdf]['network_name'] = device_info["server_pf_device_name"]
                info_dict[bdf]["pf_index"] = int(bdf.split(".")[-1])
                uuid = CliOperation.get_cli_show_fw_info(caller_class=cls, device=bdf)["Base UUID"].lower()
                info_dict[bdf]["uuid"] = uuid
                info_dict[bdf]["eid"] = ""
            bmc_uuid_dict = dict()
            for eid in bmc_eid_list:
                status_pldm, uuid_pldm = PldmTool.get_uuid(
                    ip=bmc_ip, eid=eid, execute_addr=CmdExecuteAdressEnum.SERVER.value, create_bug=False)
                if uuid_pldm:
                    bmc_uuid_dict[eid] = uuid_pldm
                    log.info(f"bmc_eid:{eid}, uuid:{uuid_pldm}")
            for bdf in info_dict:
                cli_uuid = info_dict[bdf]["uuid"]
                for eid in bmc_uuid_dict:
                    if cli_uuid.lower() == bmc_uuid_dict[eid].lower():
                        info_dict[bdf]["eid"] = eid
                        log.info(f"bdf[{bdf}]根据uuid[{cli_uuid}]匹配,对应的bmc eid为[{eid}]")
                        break
                # 如果没找到对应eid, skip
                if not info_dict[bdf]["eid"]:
                    log.error(f"bdf[{bdf}]的cli_uuid:[{cli_uuid}],没有找到对应uuid的bmc eid,环境异常")
                    CommonOperation.create_bug_problem(cls,
                                                       key_word='将卡与BMC_EID对应',
                                                       description_word=f"多卡环境, bdf[{bdf}]的cli_uuid:[{cli_uuid}],没有找到对应uuid的bmc eid,环境异常",
                                                       result_info='获取BMC EID失败',
                                                       expect_info='获取BMC EID成功')
        return info_dict

    @classmethod
    def get_bmc_eid(cls, ip, execute_addr, wait_max_count=1, interval=5):
        bmc_user_name = BmcEnvInfo.bmc_user_name if BmcEnvInfo.bmc_user_name else constants.BMC_NAME
        bmc_passwd = BmcEnvInfo.bmc_passwd if BmcEnvInfo.bmc_passwd else constants.BMC_PWD

        _, output_cpu, _ = CommandOperation.execute_command_with_error(
            cmd="lscpu | grep 'Model name'", cmd_execute_address=execute_addr
        )

        # 外网环境,开启3322端口
        if CommandLineArgsParse.get_test_port() == 3322:
            log.info(f'配置bmc开放3322端口')
            cmd = f"sshpass -p {bmc_passwd} ssh -p 22 {bmc_user_name}@{ip} '/usr/sbin/dropbear -B -p 3322 -I 600'"
            CommandOperation.execute_command_with_error(cmd)

        eid = ''
        count = 0
        while count < wait_max_count:
            # 获取eid
            if 'Teston' in output_cpu:
                cmd = f'busctl tree xyz.openbmc_project.MCTP-pcie'
                status, rtn_output, _ = CommonTools.send_bmc_command(ip=ip, cmd=cmd)
                if status == status == RtnStatusEnum.SUCCESS.value:
                    last_line = rtn_output.split('\n')[-1]
                    elmts = last_line.split('/')
                    if elmts[-1] not in ['', 'xyz', 'openbmc_project', 'mctp', 'device']:
                        # @clangelog 2025.11.18: 此处只返回最后一个
                        eid = hex(int(elmts[-1]))
                    else:
                        eid = ''
                else:
                    log.error("查询bmc eid命令下发失败,cmd:{},status:{},result:\n{}".format(cmd, status, rtn_output))
            elif 'Intel' in output_cpu or 'INTEL' in output_cpu:
                cmd = f'{BMC_TOOL_PATH} -m 0 -c 0xff --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
                _, rtn_output, _ = CommandOperation.execute_command_with_error(
                    cmd=cmd, cmd_execute_address=execute_addr)
                log.info(f'获取所有BMC EID 结果：\n{rtn_output}')
                if 'MCTP Device count' not in rtn_output:
                    CommonOperation.create_bug_problem(cls,
                                                       key_word='BMC',
                                                       description_word='获取所有BMC EID失败',
                                                       result_info='获取所有BMC EID失败',
                                                       expect_info='获取所有BMC EID成功')
                info_lst = findall(r'Medium Type[\s\S]*?Is Static EID', rtn_output)
                for info in info_lst:
                    msg_type = findall(r'Message Types\s*:\s*(\w*)', info)[0]
                    if 'MCTP' not in msg_type:
                        continue
                    else:
                        eid = findall(r'Endpoint ID\s*:\s*(\w*)', info)[0]
                        count = 5
                        log.info(f'检查eid是否可通信，若不可通信，尝试重启bmc')
                        while count:
                            status, uuid = PldmTool.get_uuid(eid=eid, ip=ip, execute_addr=execute_addr)
                            if status == '-8':
                                CommonTools.reboot_bmc(ip=ip, execute_addr=execute_addr)
                                CommonTools.time_sleep(5)
                                count -= 1
                            else:
                                break
            # 获取到eid
            if eid:
                log.info(f'mctp eid: {eid}')
                break
            # 未获取到eid
            else:
                CommonTools.time_sleep(interval)
                count += 1
        return eid

    @classmethod
    def get_nic_list(cls, cmd_execute_address) -> list:
        nic_list = []
        server_relation_list, client_relation_list = CommonOperation.get_nic_relationships()
        server_drv, client_drv = CommonOperation.get_nic_driver_name()
        if cmd_execute_address == CmdExecuteAdressEnum.SERVER.value:
            if server_drv == DRV_SCGBE_PF:
                nic_list = server_relation_list.copy()
        else:
            if client_drv == DRV_SCGBE_PF:
                nic_list = client_relation_list.copy()
        # exec_command = 'lshw -c network -businfo'
        # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
        #     exec_command, cmd_execute_address)
        # if rtn_code == RtnStatusEnum.SUCCESS.value:
        #     all_nic_list = re.findall(r'pci\S+\s+(\w+)\s+network', rtn_outputs)
        #     for nic in all_nic_list:
        #         dict_temp = EthtoolOperation.show_driver_infomation(device_name=nic,
        #                                                             cmd_execute_address=cmd_execute_address)
        #         if dict_temp['driver'] == 'scgbe':
        #             nic_list.append(nic)
        return nic_list

    @classmethod
    def reboot_bmc(cls, ip, execute_addr):
        bmc_user_name = BmcEnvInfo.bmc_user_name if BmcEnvInfo.bmc_user_name else constants.BMC_NAME
        bmc_passwd = BmcEnvInfo.bmc_passwd if BmcEnvInfo.bmc_passwd else constants.BMC_PWD
        if DEBUG_NOT_SUPPORT_0609:
            return
        cmd_reboot = f"ipmitool -U {constants.BMC_NAME_NET} -I lan -H {ip} -P '{constants.BMC_PWD_NET}' bmc reset cold"
        # cmd_reboot = f"sshpass -p {BmcEnvInfo.bmc_passwd} ssh -p {cls.test_port} {BmcEnvInfo.bmc_user_name}@{ip} 'reboot'"
        CommandOperation.execute_command_with_error(cmd=cmd_reboot, cmd_execute_address=execute_addr)
        CommonTools.time_sleep(15)
        counter = 20
        while counter > 0:
            cmd_ping = f'ping {ip} -c 1'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd_ping, cmd_execute_address=execute_addr)
            if '0% packet loss' in rtn_output:
                log.info('reboot bmc success')
                cls.get_bmc_eid(ip=ip, execute_addr=execute_addr)
                counter_msgtype = 120
                while counter_msgtype > 0:
                    eid = cls.get_bmc_eid(ip=ip, execute_addr=execute_addr)
                    if eid:
                        log.info(f'find MCTP Device success, wait init...')
                        CommonTools.time_sleep(10)

                        if CommandLineArgsParse.get_test_port() == 3322:
                            log.info(f'配置bmc开放3322端口')
                            cmd = f"sshpass -p {bmc_passwd} ssh -p 22 {bmc_user_name}@{ip} '/usr/sbin/dropbear -B -p 3322 -I 600'"
                            CommandOperation.execute_command_with_error(cmd)

                        return True
                    else:
                        CommonTools.time_sleep(5)
                        counter_msgtype -= 1
                # while counter_msgtype > 0:
                #     cmd = f'{BMC_TOOL_PATH} -m 0 -c 0xff --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
                #     _, rtn_output, _ = CommandOperation.execute_command_with_error(
                #         cmd=cmd, cmd_execute_address=execute_addr)
                #     if 'MCTP Device count' in rtn_output:
                #         log.info(f'find MCTP Device count success, wait init...')
                #         CommonTools.time_sleep(30)
                #         return True
                #     else:
                #         CommonTools.time_sleep(5)
                #         counter_msgtype -= 1
            else:
                CommonTools.time_sleep(10)
                counter -= 1
        if cls.test_port in [3322]:
            log.info(f'外网环境，需要配置bmc开放3322端口')
            cmd = f"sshpass -p {bmc_passwd} ssh -p 22 {bmc_user_name}@{ip} '/usr/sbin/dropbear -B -p 3322 -I 600'"
            CommandOperation.execute_command_with_error(cmd)
        return False

    @classmethod
    def reset_server_host_and_bmc(cls, timeout: int = 900):
        # cmd_reboot = f"sshpass -p {} ssh -p 22 {BmcEnvInfo.bmc_user_name}@{cls.bmc_ip} '/usr/sbin/dropbear -B -p 3322 -I 600'"
        bmc_ip = CommandLineArgsParse.get_server_bmc_ip()
        execute_addr = CmdExecuteAdressEnum.SERVER.value
        cmd_reboot = f"ipmitool -U {cls.bmc_ssh_username} -I lan -H {bmc_ip} -P '{cls.bmc_ssh_password}' bmc reset cold"
        log.info("下发bmc重启命令,cmd:{}".format(cmd_reboot))
        status, result, _ = CommandOperation.execute_command_with_error(cmd=cmd_reboot, cmd_execute_address=execute_addr)
        log.info("status:{}, result:{}".format(status, result))
        if status != RtnStatusEnum.SUCCESS.value:
            log.error("bmc重启命令下发失败")
            CommonOperation.create_bug_problem(cls,
                                               key_word='主测端重启bmc',
                                               description_word='重启命令下发失败,bmc重启失败',
                                               result_info=f'status:{status}',
                                               expect_info='重启命令下发成功')
        log.info("bmc重启命令下发成功,开始主机重启")
        status = cls.reboot_host(ssh_ip=CmdExecuteAdressEnum.SERVER.value, timeout=timeout)
        if status != RtnStatusEnum.SUCCESS.value:
            CommonOperation.create_bug_problem(cls,
                                               key_word='主测端reboot重启',
                                               description_word='重启失败',
                                               result_info=f'status:{status}',
                                               expect_info='重启成功')
        log.info("主机重启成功,查看bmc状态")
        bmc_user_name = BmcEnvInfo.bmc_user_name if BmcEnvInfo.bmc_user_name else constants.BMC_NAME
        bmc_passwd = BmcEnvInfo.bmc_passwd if BmcEnvInfo.bmc_passwd else constants.BMC_PWD
        counter = 20
        bmc_reboot_success_flag = False
        while counter > 0:
            cmd_ping = f'ping {bmc_ip} -c 1'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd_ping, cmd_execute_address=execute_addr)
            if '0% packet loss' in rtn_output:
                if not bmc_reboot_success_flag:
                    log.info('bmc重启成功')
                    bmc_reboot_success_flag = True
                    break
            else:
                log.info("bmc环境未ping通,等待10秒后重试")
                CommonTools.time_sleep(10)
                counter -= 1
        if not bmc_reboot_success_flag:
            CommonOperation.create_bug_problem(cls,
                                               key_word='主测端重启bmc',
                                               description_word='bmc重启失败,重启后主测端未ping通bmc ip',
                                               result_info=f'bmc重启失败,重启后主测端未ping通bmc ip',
                                               expect_info='重启bmc成功')

        if cls.test_port in [3322]:
            log.info(f'外网环境，需要配置bmc开放3322端口')
            cmd = f"sshpass -p {bmc_passwd} ssh -p 22 {bmc_user_name}@{bmc_ip} '/usr/sbin/dropbear -B -p 3322 -I 600'"
            CommandOperation.execute_command_with_error(cmd)

        log.info("bmc重启完成,开始寻找卡上报的bmc eid")
        cls.get_bmc_eid(ip=bmc_ip, execute_addr=execute_addr)
        counter_msgtype = 120
        while counter_msgtype > 0:
            eid = cls.get_bmc_eid(ip=bmc_ip, execute_addr=execute_addr)
            if eid:
                log.info(f'bmc重启后找到eid,环境重启完成')
                CommonTools.time_sleep(5)
                return True
            else:
                log.info("bmc重启后未找到eid,休眠5秒后集训寻找")
                CommonTools.time_sleep(5)
                counter_msgtype -= 1

        CommonOperation.create_bug_problem(cls,
                                           key_word='主测端重启bmc',
                                           description_word='bmc重启后环境异常,未找到任何bmc eid',
                                           result_info='bmc重启后环境异常,未找到任何bmc eid',
                                           expect_info='重启bmc成功')
        return

    @classmethod
    def reboot_host(cls, ssh_ip: str, ssh_port: str = '22', timeout: int = 900) -> int:
        if DEBUG_NOT_SUPPORT_0609:
            return RtnStatusEnum.SUCCESS.value
        rtn_code = HostOperation.host_reboot(ssh_ip, ssh_port, timeout)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'reboot成功')
            log.info(f'reboot后重新记载驱动')
            CommonTools.time_sleep(20)
            cmd = f'lsmod|grep -w {DRV_SCGBE_PF}'
            status, result, _ = CommandOperation.execute_command_with_error(cmd=cmd, timeout=120)
            # 未加载驱动
            if not result:
                log.info(f'加载{DRV_SCGBE_PF}.ko')
                server_ip, client_ip = CommonOperation.get_nic_logical_ip()
                if ssh_ip == client_ip:
                    cmd_execute_address = CmdExecuteAdressEnum.CLIENT.value
                else:
                    cmd_execute_address = CmdExecuteAdressEnum.SERVER.value
                status = CommonOperation.modprobe_driver(DRV_SCGBE_PF, cmd_execute_address)  # , result, _
                # cmd = f'insmod /root/{DRV_SCGBE_PF}.ko'
                # status, result, _ = CommandOperation.execute_command_with_error(cmd=cmd, timeout=600)
                if status:  # == RtnStatusEnum.SUCCESS.value
                    log.info(f'加载{DRV_SCGBE_PF}.ko成功')
                    return RtnStatusEnum.SUCCESS.value
                else:
                    log.error(f'加载{DRV_SCGBE_PF}.ko失败')
                    return RtnStatusEnum.FAIL.value
            else:
                log.info(f'已加载{DRV_SCGBE_PF}.ko')
                return RtnStatusEnum.SUCCESS.value
        else:
            log.error(f'reboot失败')
            return RtnStatusEnum.FAIL.value

    @classmethod
    def send_bmc_command(cls, ip, cmd):
        bmc_name = BmcEnvInfo.bmc_user_name if BmcEnvInfo.bmc_user_name else constants.BMC_NAME
        bmc_passwd = BmcEnvInfo.bmc_passwd if BmcEnvInfo.bmc_passwd else constants.BMC_PWD
        command = f'sshpass -p {bmc_passwd} ssh -p {cls.test_port} {bmc_name}@{ip}'
        command += f' "{cmd}"'
        # print(command)
        status, rtn_output, err = CommandOperation.execute_command_with_error(cmd=command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)  # , local_execute_flag=False
        # log.info(f'指令执行结果：\n{rtn_output}')
        # _, _, _ = CommandOperation.execute_command_with_error(cmd="printf '\033[0m'", print_outputs=False)  # , local_execute_flag=False
        return status, rtn_output, err
        # return cls.retry_execute_command_in_bmc(cmd)

    @classmethod
    def custom_get_uuid(cls, px, execute_addr) -> str:
        cmd = f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} custom {DRV_SCGBE_PF} pldmuuid'
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd,
            cmd_execute_address=execute_addr)
        # log.info(f'指令执行结果：\n{rtn_output}')
        re_uuid = findall(r'pldm_uuid:(\w+)\s+(\w+)', rtn_output)
        if re_uuid:
            uuid = re_uuid[0][0].rjust(16, '0') + re_uuid[0][1].rjust(16, '0')
            return uuid
        else:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC',
                result_info='通过custom指令获取uuid失败',
                expect_info='通过custom指令获取uuid成功',
                description_word='通过custom指令获取uuid失败')

    @classmethod
    def check_sensor_reading_para(cls, key_word, eid, ip, sensor, execute_addr, exp_size, exp_op=0,
                                  exp_evt_enable=1, exp_pres=7, exp_evt_state=1) -> int:
        # @changlog 2025.10.31 gaoyb: exp_pres=10, exp_evt_state=9 打桩改为7, 1
        status, sensor_dict = PldmTool.get_sensor_reading(
            ip=ip, eid=eid, sensor=sensor, execute_addr=execute_addr)
        if status != '0':
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word=key_word,
                description_word='校验PLDM_GetSensorReading接口status参数',
                expect_info='0',
                result_info=status)
        data_size = int(sensor_dict.get('sensor_data_size'), 16)
        op_state = int(sensor_dict.get('sensor_op_state'), 16)
        evt_enable = int(sensor_dict.get('sensor_evt_msg_enable'), 16)
        pres_state = int(sensor_dict.get('pres_state'), 16)
        event_state = int(sensor_dict.get('evt_state'), 16)
        if data_size != exp_size and exp_size:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word=key_word,
                description_word='校验PLDM_GetSensorReading接口sensor_data_size参数',
                expect_info=str(exp_size),
                result_info=str(data_size))
        if op_state != exp_op and exp_op:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word=key_word,
                description_word='校验PLDM_GetSensorReading接口sensor_op_state参数',
                expect_info=str(exp_op),
                result_info=str(op_state))
        if evt_enable != exp_evt_enable and exp_evt_enable:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word=key_word,
                description_word='校验PLDM_GetSensorReading接口sensor_evt_msg_enable参数',
                expect_info=str(exp_evt_enable),
                result_info=str(evt_enable))
        if pres_state != exp_pres and exp_pres:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word=key_word,
                description_word='校验PLDM_GetSensorReading接口pres_state参数',
                expect_info=str(exp_pres),
                result_info=str(pres_state))
        # wangwt：暂定prev_state参数表示上次查询状态，不做校验，先屏蔽
        # if prev_state != exp_prev:
        #     CommonOperation.create_bug_problem(
        #         ScriptBase,
        #         key_word=key_word,
        #         description_word='校验PLDM_GetSensorReading接口prev_state参数',
        #         expect_info=str(exp_prev),
        #         result_info=str(prev_state))
        if event_state != exp_evt_state and exp_evt_state:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word=key_word,
                description_word='校验PLDM_GetSensorReading接口evt_state参数',
                expect_info=str(exp_evt_state),
                result_info=str(event_state))
        data = int(sensor_dict.get('data'))
        return data

    @classmethod
    def get_soc_fw_state(cls, eid, execute_addr):
        ip = CommandLineArgsParse.get_server_bmc_ip()
        status, state_dict = PldmTool.get_state_sensor_reading(
            eid=eid, ip=ip, sensor=constants.BMC_STATE_SOC, execute_addr=execute_addr)
        if status != '0':
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word="BMC_PLDM_获取固件当前状态",
                description_word='命令执行失败,结果获取失败',
                expect_info='status:0',
                result_info=f"status:{status}")
        # op_state = int(state_dict['sensor_op_state'], 16)
        pres_state = int(state_dict['pres_state'], 16)
        # evt_state = int(state_dict['evt_state'], 16)

        # return pres_state, evt_state
        return pres_state

    @classmethod
    def pldm_set_soc_core_reset(cls, eid, execute_addr, wait_time:int=3):
        """
        通过PLDM SetNumericEffectorValue 触发固件重启
        """
        set_value = wait_time - 3 if wait_time > 3 else 0
        cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c 31 --effecter=0 --numeric_value={hex(set_value)} '
               f'--addr={CommandLineArgsParse.get_server_bmc_ip()} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}')
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        # log.info(f'PLDM SetNumericEffectorValue 指令执行结果：\n{rtn_output}')
        if "status:0" in rtn_output.lower():
            log.info(f"PLDM设置固件重启成功, {set_value+3}秒后重启")
            return set_value+3
        else:
            log.error(f"error, PLDM设置固件重启失败")
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word="PLDM设置固件重启失败",
                description_word='PLDM设置固件重启失败',
                expect_info='设置命令status == 0',
                result_info="设置命令status != 0")
            return 0

    @classmethod
    def get_reset_reason_and_uptime_check(cls, device_info, uptime:int, execute_addr, reset_reason="core reset",
                                          up_limit:int=10, down_limit:int=5):
        start_time = time.time()
        cmd = f"{SCGBECLI64} -d {device_info} custom sxe2 fwinfo"
        rtn_code, rtn_out, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=execute_addr)
        end_time = time.time()
        add_time = int(end_time - start_time)
        uptime_match = re.search(
            r'uptime:\s*(\d+)\s*days?,?\s*(\d+)\s*hours?,?\s*(\d+)\s*minutes?,?\s*(\d+)\s*seconds?', rtn_out)
        log.info(f"cli命令执行时间:{add_time}秒")
        if not uptime_match:
            log.error(f"custom sxe2 fwinfo命令,正则表达式没有解析到uptime")
            CommonOperation.create_bug_problem(ScriptBase,
                                               key_word=f"custom sxe2 fwinfo命令,正则表达式没有解析到uptime",
                                               description_word=f"",
                                               result_info="",
                                               expect_info="")
        days = int(uptime_match.group(1))
        hours = int(uptime_match.group(2))
        minutes = int(uptime_match.group(3))
        seconds = int(uptime_match.group(4))
        total_seconds = days * 86400 + hours * 3600 + minutes * 60 + seconds
        log.info(f"uptime:{days}天{hours}小时{minutes}分钟{seconds}秒,合计为{total_seconds}秒")
        limit_time = uptime + up_limit + add_time
        min_limit_time = uptime - down_limit  # + add_time
        if total_seconds > limit_time:
            log.error(f"固件的uptime{total_seconds}秒, 大于验证限制的{limit_time}秒")
            CommonOperation.create_bug_problem(ScriptBase,
                                               key_word="重启后获取Uptime",
                                               description_word=f"固件的uptime{total_seconds}秒, 大于验证限制的{limit_time}秒",
                                               result_info=f"固件的uptime{total_seconds}秒, 大于验证限制的{limit_time}秒",
                                               expect_info=f"固件的uptime小于验证限制的{limit_time}秒")
        elif total_seconds < min_limit_time:
            log.error(f"固件的uptime{total_seconds}秒, 小于验证限制的最小值{min_limit_time}秒")
            CommonOperation.create_bug_problem(ScriptBase,
                                               key_word="重启后获取Uptime",
                                               description_word=f"固件的uptime{total_seconds}秒, 小于验证限制的最小值{min_limit_time}秒",
                                               result_info=f"固件的uptime{total_seconds}秒, 小于验证限制的最小值{min_limit_time}秒",
                                               expect_info=f"固件的uptime大于验证限制的{min_limit_time}秒", block=False)

        log.info(f"uptime小于[{limit_time}]秒,大于[{min_limit_time}]秒,验证通过")

        first_rst_cause_match = re.search(r'NIC RST CAUSE:\s*(.+?)(?:\n|$)', rtn_out)
        if not first_rst_cause_match:
            log.error(f"custom sxe2 fwinfo命令,正则表达式没有解析到NIC RST CAUSE")
            CommonOperation.create_bug_problem(ScriptBase,
                                               key_word="重启后获取启动原因",
                                               description_word=f"custom sxe2 fwinfo命令,正则表达式没有解析到NIC RST CAUSE",
                                               result_info=f"custom sxe2 fwinfo命令,正则表达式没有解析到NIC RST CAUSE",
                                               expect_info="")
        first_rst_cause_match = first_rst_cause_match.group(1).strip()

        if reset_reason.lower() not in first_rst_cause_match.lower():
            log.error(f"最新一次启动原因:{first_rst_cause_match}, 与预期的启动原因[{reset_reason}]不一致")
            CommonOperation.create_bug_problem(ScriptBase,
                                               key_word="重启后获取启动原因",
                                               description_word=f"最新一次启动原因:{first_rst_cause_match}, 与预期的启动原因[{reset_reason}]不一致",
                                               result_info=f"",
                                               expect_info=f"最新一次启动原因与预期的启动原因[{reset_reason}]一致")

        log.info(f"最新一次启动原因:{reset_reason},验证通过")

    @classmethod
    def pldm_set_core_reset_check_result(cls, device_info, eid, execute_addr, wait_time:int=3):
        """
        1.通过PLDM SetNumericEffectorValue 触发固件重启
        2.验证重启是否成功,重启时间是否正确,重启原因是否与预期一致
        """
        sleep_time = cls.pldm_set_soc_core_reset(eid=eid, execute_addr=execute_addr, wait_time=wait_time)
        if not sleep_time:
            return
        log.info(f"等待{sleep_time + 20}秒后,查看重启是否成功")
        cls.time_sleep(sleep_time + 20)

        cls.get_reset_reason_and_uptime_check(device_info=device_info, execute_addr=execute_addr, uptime=20)

    @classmethod
    def check_state_sensor_para(cls, key_word, eid, ip, sensor, execute_addr,
                                exp_prev=1, exp_op=0, exp_pres=0x30, exp_evt=1):
        status, state_dict = PldmTool.get_state_sensor_reading(
            eid=eid, ip=ip, sensor=sensor, execute_addr=execute_addr)
        if status != '0':
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word=key_word,
                description_word='校验PLDM_GetStateSensorReading接口status参数',
                expect_info='0',
                result_info=status)
        op_state = int(state_dict['sensor_op_state'], 16)
        pres_state = int(state_dict['pres_state'], 16)
        evt_state = int(state_dict['evt_state'], 16)
        if op_state != exp_op:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word=key_word,
                description_word='校验PLDM_GetStateSensorReading接口sensor_op_state参数',
                expect_info=hex(exp_op),
                result_info=hex(op_state))
        if pres_state != exp_pres:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word=key_word,
                description_word='校验PLDM_GetStateSensorReading接口pres_state参数',
                expect_info=hex(exp_pres),
                result_info=hex(pres_state))
        # if prev_state != exp_prev:
        #     CommonOperation.create_bug_problem(
        #         ScriptBase,
        #         key_word=key_word,
        #         description_word='校验PLDM_GetStateSensorReading接口prev_state参数',
        #         expect_info=str(exp_prev),
        #         result_info=str(prev_state))
        if evt_state != exp_evt:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word=key_word,
                description_word='校验PLDM_GetStateSensorReading接口evt_state参数',
                expect_info=hex(exp_evt),
                result_info=hex(evt_state))

    @classmethod
    def check_module_threshold_dict(cls, key_word, thold_dict, module_info_dict):
        def process_number(num):
            """
            负值计算
            否则返回原数
            """
            if num > 180:
                return num - 0x100
            return num
        result_thres_dict = {}
        expect_thres_dict = {}
        sensor_data_size = int(thold_dict.get('sensor_data_size'), 16)
        if sensor_data_size != 3:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word=key_word,
                description_word='校验PLDM_GetSensorThresholds接口sensor_data_size参数',
                expect_info='3',
                result_info=str(sensor_data_size))

        result_thres_dict['upper_thold_warning'] = float(
            thold_dict.get('upper_thold_warning'))
        result_thres_dict['upper_thold_fatal'] = float(
            thold_dict.get('upper_thold_fatal'))
        result_thres_dict['lower_thold_warning'] = float(
            thold_dict.get('lower_thold_warning'))
        result_thres_dict['lower_thold_fatal'] = float(
            thold_dict.get('lower_thold_fatal'))

        result_thres_dict['lower_thold_warning'] = process_number(result_thres_dict['lower_thold_warning'])
        result_thres_dict['lower_thold_fatal'] = process_number(result_thres_dict['lower_thold_fatal'])

        expect_thres_dict['upper_thold_warning'] = (float(
            module_info_dict['Module temperature high warning threshold'].split('degrees C')[0].strip()))
        expect_thres_dict['upper_thold_fatal'] = (float(
            module_info_dict['Module temperature high alarm threshold'].split('degrees C')[0].strip()))
        expect_thres_dict['lower_thold_warning'] = (float(
            module_info_dict['Module temperature low warning threshold'].split('degrees C')[0].strip()))
        expect_thres_dict['lower_thold_fatal'] = (float(
            module_info_dict['Module temperature low alarm threshold'].split('degrees C')[0].strip()))

        if expect_thres_dict != result_thres_dict:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word=key_word,
                description_word='校验PLDM_GetSensorThreshold接口返回阈值',
                expect_info=str(expect_thres_dict),
                result_info=str(result_thres_dict))

    @classmethod
    def get_soc_up_time(cls, px, execute_addr, serial_exec=CmdExecuteAdressEnum.CLIENT.value) -> int:
        log.info("input px:{}, type:{}".format(px, type(px)))
        if type(px) == int:
            cmd = f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} show uptime'
        else:
            cmd = f'{SCGBECLI64} -d {px} show uptime'
        _, custom_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        log.info(f'指令返回结果：\n{custom_output}')
        re_uptime_lst = findall(
            r'Device Up Time\s+\|(\d+):(\d+):(\d+)\.(\d+)', custom_output)
        if re_uptime_lst:
            uptime_lst = [int(s) for s in re_uptime_lst[0]]
            uptime = 60 * 60 * uptime_lst[0] + 60 * uptime_lst[1] + uptime_lst[2]
            log.info(f'soc启动时间：\n{uptime}')
            return uptime
        else:
            _, comm_output, _ = CommandOperation.execute_command_with_error(
                cmd=f"python3 {SERIAL_CLI_PY} '/comm show uptime'",
                cmd_execute_address=serial_exec
            )
            re_uptime_lst = findall(r'(\d+)\s*days,(\d+)\s*hours,(\d+)\s*minutes,(\d+)\s*seconds', comm_output)
            # log.info(f'指令执行结果：\n{comm_output}')
            if re_uptime_lst:
                uptime_lst = [int(s) for s in re_uptime_lst[0]]
                uptime = 60 * 60 * 24 * uptime_lst[0] + 60 * 60 * uptime_lst[1] + 60 * uptime_lst[2] + uptime_lst[3]
                log.info(f'soc启动时间：\n{uptime}')
                return uptime
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    result_info='通过custom指令获取uptime失败',
                    expect_info='通过custom指令获取uptime成功',
                    description_word='通过custom命令获取固件uptime失败')

    @classmethod
    def get_system_time_stamp(cls, execute_addr) -> int:
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd="date '+%d %T'", cmd_execute_address=execute_addr)
        re_time = findall(r"(\d+) (\d+):(\d+):(\d+)", output)
        time_lst = [int(s) for s in re_time[0]]
        stamp = 60 * 60 * 24 * time_lst[0] + 60 * 60 * time_lst[1] + 60 * time_lst[2] + time_lst[3]
        # log.info(f'指令执行结果：\n{output}，{time_lst}， {stamp}')
        return stamp

    @classmethod
    def check_cli_upgrade_success(cls, key_word, px, execute_addr):
        pkg_path = CommonOperation.get_image_upgrade_file_for_bdf(bdf_info=list(BmcEnvInfo.info_dict.keys())[px],
                                                                  exec_addr=execute_addr, caller_class=cls)
        # pkg_path = CommonOperation.get_full_path(UPGRADE_IMAGE_PACKAGE_PATH, execute_addr)
        if DEBUG_NOT_SUPPORT_0609:
            _, cli_output, _ = CommandOperation.execute_command_with_error(
                cmd=f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} upgrade file={pkg_path}',  #  noverchk
                cmd_execute_address=execute_addr)
        else:
            cmd = f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} upgrade file={pkg_path}'  #  noverchk
            stat, cli_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd,
                cmd_execute_address=execute_addr)
            # log.warning(f'暂不支持bmc升级，此处不执行cli升级')
            # cli_output = 'Fail'
            log.info(f'cli升级命令:[{cmd}], status:{stat}, result:\n{cli_output}')
            if 'Success' not in cli_output or stat != RtnStatusEnum.SUCCESS.value:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word=key_word,
                    description_word='cli进行image升级',
                    result_info=f'命令执行失败,status:{stat}',
                    expect_info='使用cli指令升级成功'
                )
            else:
                log.info("cli升级成功")

    @classmethod
    def pldm_event_message_enable_disable(cls, eid, execute_addr, enable=True):
        """
        开启或关闭 固件事件主动上报BMC的功能
        """
        ip = CommandLineArgsParse.get_server_bmc_ip()
        if enable:
            enable_para = "1"
            enable_str = "开启"
        else:
            enable_para = "0"
            enable_str = "关闭"

        log.info(f"eid[{eid}]{enable_str}事件主动上报bmc")
        cmd = (f"{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c 4 --evt_msg_global_enable={enable_para} --transport=0 --addr_info=1 "
               f"--addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}")
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        if "status:0" in rtn_output.lower():
            if enable:
                log.info(f"eid[{eid}]开启事件主动上报bmc成功")
            else:
                log.info(f"eid[{eid}]关闭事件主动上报bmc成功")
        else:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC',
                description_word=f"eid[{eid}]{enable_str}事件主动上报bmc,命令执行失败",
                result_info=f"eid[{eid}]{enable_str}事件主动上报bmc,命令执行失败",
                expect_info=f"eid[{eid}]{enable_str}事件主动上报bmc,命令执行成功"
            )

    @classmethod
    def fw_reset_type_0(cls, device_info=""):
        """
        触发nic的 fw重启, type=0, 不重启主机
        """
        if not device_info:
            device_info = list(BmcEnvInfo.info_dict.keys())[0]
        CommonOperation.fw_reset(caller_class=cls, device_bdf=device_info, type="0")

    @classmethod
    def reset_and_reboot(cls, execute_addr) -> None:
        """
        触发nic的 pcie+fw重启后,重启主机

        """
        if DEBUG_NOT_SUPPORT_0609:
            return

        reset_cmd = f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[0]} reset type=2'
        reset_code, _, _ = CommandOperation.execute_command_with_error(
            cmd=reset_cmd, cmd_execute_address=execute_addr)
        server_ip, _ = CommonOperation.get_nic_logical_ip()
        bmc_ip = CommandLineArgsParse.get_server_bmc_ip()
        if reset_code != RtnStatusEnum.SUCCESS.value:
            # bmc_ip = CommandLineArgsParse.get_server_bmc_ip()
            uname = CommandLineArgsParse.get_server_bmc_uname()
            passwd = CommandLineArgsParse.get_server_bmc_passwd()
            reboot_result = HostOperation.host_bmc_reboot(
                ssh_ip=server_ip, bmc_ip=bmc_ip, uname=uname, passwd=passwd, force_check=False)
            CommonOperation.modprobe_driver(driver_name=DRV_SCGBE_PF, cmd_execute_address=execute_addr)
        else:
            cmd_mctp_restart = f'sshpass -p {BmcEnvInfo.bmc_passwd} ssh -p {cls.test_port} {BmcEnvInfo.bmc_user_name}@{bmc_ip} systemctl restart xyz.openbmc_project.mctpd@pcie.service'
            status, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd_mctp_restart, cmd_execute_address=execute_addr)
            reboot_result = cls.reboot_host(ssh_ip=server_ip, timeout=1800)
        if reboot_result == RtnStatusEnum.SUCCESS.value:
            log.info('重启主机成功')
        else:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC',
                description_word='触发nic的 pcie+fw重启后,重启主机',
                result_info='触发nic的 pcie+fw重启后,Host重启失败',
                expect_info='触发nic的 pcie+fw重启后,Host重启成功'
            )
        # CommonOperation.modprobe_driver(driver_name='scgbe', cmd_execute_address=execute_addr)
        CommonTools.time_sleep(10)

    @classmethod
    def set_fw_state(cls, status, exec_addr, use_custom=True, dev_info=None):
        if use_custom:
            if dev_info:
                cmd = f'{SCGBECLI64} -d {dev_info} custom {DRV_SCGBE_PF} fwstatechg status={status}'
            else:
                cmd = f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[0]} custom {DRV_SCGBE_PF} fwstatechg status={status}'
            code, output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=exec_addr)
            log.info("cmd:{}, status:{}, result:\n{}".format(cmd, code, output))
            if 'fwstateset' in output.lower():
                return
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='使用custom命令设置片内设置固件状态失败')
                return

        CommandOperation.execute_command_with_error(
            cmd=f'insmod /root/pl2303.ko', cmd_execute_address=exec_addr)
        set_retry = 5
        while set_retry:
            cmd = f"python3 {SERIAL_CLI_PY} '/debug custom {DRV_SCGBE_PF} fwstatechg status={status}'"
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=exec_addr, timeout=30)
            re_status = re.findall(r'Status\s*=\s*Success', rtn_output)
            if re_status:
                log.info('设置固件状态成功')
                return
            else:
                log.info('设置固件状态失败')
                _, pid, _ = CommandOperation.execute_command_with_error(
                    cmd=f"ps -ef | grep '{SERIAL_CLI_PY}' " + "| grep -v grep | awk '{print $2}'",
                    cmd_execute_address=exec_addr)
                CommandOperation.execute_command_with_error(
                    cmd=f"kill -9 {pid}",
                    cmd_execute_address=exec_addr)
                set_retry -= 1
        CommonOperation.create_bug_problem(
            ScriptBase,
            key_word='BMC',
            description_word='片内设置固件状态失败')

    @classmethod
    def damage_fw(cls, px, dev_id, exec_addr):
        value = format(random.randint(0, 16 ** 16), '016X')
        cmd = f"{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} custom {DRV_SCGBE_PF} flashwrstr devid={dev_id} offset=0x1 len=0x10 value={value}"
        code, output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr)
        log.info(f'指令返回结果：{output}')
        if code != RtnStatusEnum.SUCCESS.value:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC',
                description_word='损坏分区失败'
            )

    @classmethod
    def close_monitor(cls, ip, execute_addr):
        _, output_dmi, _ = CommandOperation.execute_command_with_error(
            cmd="dmidecode | grep 'Product Name'", cmd_execute_address=execute_addr
        )
        _, output_cpu, _ = CommandOperation.execute_command_with_error(
            cmd="lscpu | grep 'Model name'"
        )
        ctr_file = ''
        if 'MDA' in output_cpu and '50' in output_dmi:
            ctr_file = '/var/FWmode'
        elif 'Intel' in output_cpu and '50' in output_dmi:
            ctr_file = '/var/MCTPFWUpdateFlag'
        elif 'Teston' in output_cpu and '50' in output_dmi:
            ctr_file = ''

        if ctr_file:
            _, ls_output, _ = cls.send_bmc_command(
                ip=ip ,cmd=f'ls {ctr_file}',
            )
            if ctr_file in ls_output:
                log.info('monitor 已关闭')
            else:
                log.warning(f'暂不执行 -> touch {ctr_file}')
                # _, ls_output, _ = cls.send_bmc_command(
                #     ip=ip, cmd=f'touch {ctr_file}',
                # )
                # CommonTools.time_sleep(25)
        else:
            _, result, _ = cls.send_bmc_command(
                ip=ip ,cmd=f'systemctl status bmc-nic-manager',
            )
            if "Active: inactive (dead)" in result:
                log.info('monitor 已关闭')
            else:
                _, ls_output, _ = cls.send_bmc_command(
                    ip=ip ,cmd=f'systemctl stop bmc-nic-manager',
                )
                _, ls_output, _ = cls.send_bmc_command(
                    ip=ip ,cmd=f'systemctl disable bmc-nic-manager',
                )
                _, result, _ = cls.send_bmc_command(
                    ip=ip, cmd=f'systemctl status bmc-nic-manager',
                )
                if "Active: inactive (dead)" in result:
                    log.info('monitor 已关闭')
                else:
                    log.warning('monitor 关闭失败，后续bmc命令执行时概率会受到monitor干扰导致失败')

    @classmethod
    def feed_log(cls, counter=300, exec_address=CmdExecuteAdressEnum.SERVER.value):
        # counter = 300
        while counter > 0:
            CommandOperation.execute_command_with_error(
                cmd=f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[0]} show mfginfo; '
                    f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[0]} show; '
                    f'{SCGBECLI64} show; '
                    f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[0]} show',
                cmd_execute_address=exec_address
            )
            counter -= 1

    @classmethod
    def execute_command_in_bmc(cls, cmd: str, update: bool = False, time_wait_ret: int = DEFAULT_TIME_WAIT_FOR_CMD_RET,
                               execute_timeout: int = DEFAULT_TIME_WAIT_FOR_CMD_LOOP_RET,
                               check_type: str = "BMC") -> tuple:
        """
        author: xiangyu.liu
        date  : 2022.06.08
        description: 在bmc中执行命令
        :return: status
        """
        if "export" not in cmd:
            if check_type == "BMC":
                cmd = cmd
            else:
                cmd = cmd

        if not update:
            status, result = InteractiveOperation.execute_command_with_invoke(cmd, ssh_ip=cls.bmc_ip, ssh_port=22,
                                                                              execute_in_host=False,
                                                                              ssh_username=cls.bmc_ssh_username,
                                                                              ssh_password=cls.bmc_ssh_password,
                                                                              ssh_password_other="Tianjian;123",
                                                                              time_wait_cmd_ret=time_wait_ret,
                                                                              cmd_execute_timeout=execute_timeout)
        else:
            status, result =\
                InteractiveOperation.execute_update_command_with_invoke(cmd, ssh_ip=cls.bmc_ip, ssh_port=22,
                                                                        execute_in_host=False,
                                                                        ssh_username=cls.bmc_ssh_username,
                                                                        ssh_password=cls.bmc_ssh_password,
                                                                        ssh_password_other="Tianjian;123",
                                                                        time_wait_cmd_ret=time_wait_ret,
                                                                        cmd_execute_timeout=execute_timeout)

        return status, result
        # status, result, error = PublicCommandOperation.execute_command_with_password(cmd, local_execute_flag=False,
        #                                                                          ssh_ip=cls.bmc_ip, ssh_port="22",
        #                                                                          ssh_username=cls.bmc_ssh_username,
        #                                                                          ssh_password=cls.bmc_ssh_password)
        # return status, result, error

    @classmethod
    def retry_execute_command_in_bmc(cls, cmd: str, update: bool = False,
                                     time_wait_ret: int = DEFAULT_TIME_WAIT_FOR_CMD_RET,
                                     execute_timeout: int = DEFAULT_TIME_WAIT_FOR_CMD_LOOP_RET, retry_count: int = 5,
                                     retry_interval: int = 3) -> tuple:
        """
        author: xiangyu.liu
        date  : 2022.06.08
        description: 在bmc中执行命令
        :return: status
        """
        if "export" not in cmd:
            cmd = "export BMCDRIVER=i2c;" + cmd

        if not update:
            retry_success_flag = False
            count_now = 0
            while True:
                status, result = InteractiveOperation.execute_command_with_invoke(cmd, ssh_ip=cls.bmc_ip, ssh_port=22,
                                                                                  execute_in_host=False,
                                                                                  ssh_username=cls.bmc_ssh_username,
                                                                                  ssh_password=cls.bmc_ssh_password,
                                                                                  ssh_password_other="Tianjian;123",
                                                                                  time_wait_cmd_ret=time_wait_ret,
                                                                                  cmd_execute_timeout=execute_timeout)
                # status = 0 并且 result == ""，则retry
                if status == RtnStatusEnum.SUCCESS.value and (not result or
                                                              "BMC transmission errors were detected" in result):
                    log.error("[{}]执行失败，重试...{}/{}".format(cmd, count_now, retry_count))
                    count_now += 1
                else:
                    retry_success_flag = True
                    break
                # 检查retry次数是否耗尽
                if count_now >= retry_count:
                    log.error("retry {} 次，重试次数耗尽，仍未成功".format(retry_count))
                # 等待retry间隔时间
                if retry_interval:
                    cls.sleep_time(retry_interval)
            # 判断retry是否成功
            if retry_success_flag:
                return RtnStatusEnum.SUCCESS.value, result
            else:
                return RtnStatusEnum.FAIL.value, result
        else:
            status, result =\
                InteractiveOperation.execute_update_command_with_invoke(cmd, ssh_ip=cls.bmc_ip, ssh_port=22,
                                                                        execute_in_host=False,
                                                                        ssh_username=cls.bmc_ssh_username,
                                                                        ssh_password=cls.bmc_ssh_password,
                                                                        ssh_password_other="Tianjian;123",
                                                                        time_wait_cmd_ret=time_wait_ret,
                                                                        cmd_execute_timeout=execute_timeout)

        return status, result

    @classmethod
    def sleep_time(cls, seconds: float):
        """
        author:                                 xiangyu.liu
        date:                                   2022.06.08
        description:                            等待指定时间（s）
        :param seconds:                         时间（s）,eg: 2.0s
        :return:                                status
        """
        if seconds:
            log.info("等待{}s...".format(seconds))
            CommonTools.time_sleep(seconds)

    @classmethod
    def enum_name(cls, enum_class, enum_value):
        for enum in enum_class:
            if hex(int(enum.value, 16)) == hex(int(enum_value, 16)):
                return enum.name
        return None  # 如果没有找到对应的枚举值，返回None

    @classmethod
    def time_sleep(cls, sleep_time, info='Waiting'):
        log.info_caller(f'sleep {sleep_time}s...[{info}]')
        time.sleep(sleep_time)


class MctpTools(ScriptBase, ABC):
    mctp_header_len = 5
    @classmethod
    def mctp_control_msg_header(cls, command_code: str):
        """
        根据传入的code,拼成mctp命令的header
        """
        ic_bit = 0
        msg_type = int(MctpMsgType.Control.value, 16)
        rq_bit = 1
        d_bit = 0
        instance_id = 1
        cmd_code = int(command_code, 16)
        # comp_code = 0
        byte1 = (ic_bit << 7) | msg_type
        byte2 = (rq_bit << 7) | (d_bit << 6) | instance_id
        byte3 = cmd_code
        # byte4 = comp_code
        bytes = copy.deepcopy([hex(byte1), hex(byte2), hex(byte3)])
        return bytes

    @classmethod
    def mctp_response_header_para(cls, response_bytes_list: list) -> dict:
        value = {}
        value['length'] = int(response_bytes_list[0])
        value[MctpMsgFieldName.IC.value] = int(response_bytes_list[1]) >> 7
        value[MctpMsgFieldName.MsgType.value] = int(response_bytes_list[1]) << 1 >> 1
        value[MctpMsgFieldName.Rq.value] = int(response_bytes_list[2]) >> 7
        value[MctpMsgFieldName.D.value] = int(response_bytes_list[2]) << 1 >> 7
        value[MctpMsgFieldName.InsId.value] = int(response_bytes_list[2]) << 3 >> 3
        value[MctpMsgFieldName.CmdCode.value] = int(response_bytes_list[3])
        value[MctpMsgFieldName.CompCode.value] = int(response_bytes_list[4])
        return value.copy()

    @classmethod
    def mctp_response_check(cls, command_code: str, response_bytes: str, nodata: bool=False) -> tuple:
        """
        根据mctp的命令code,对命令执行后返回的结果进行校验和分类获取
        返回校验结果的状态码,和 获取到的结果的字典
        """
        enum_name = CommonTools.enum_name(MctpCtlCmdNum, command_code)
        log.info(f'MCTP {enum_name} 指令执行结果：\n{response_bytes}')
        if response_bytes:
            status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
            response_bytes_list = response_bytes.split(' ')
            # 解析response头
            value = cls.mctp_response_header_para(response_bytes_list.copy())
            log.info(f'response头解析：\n{json.dumps(value, indent=4)}')
            # 解析response数据段
            if len(response_bytes_list) > cls.mctp_header_len:
                if command_code == MctpCtlCmdNum.GetEID.value:
                    value['eid'] = response_bytes_list[5]
                    value['eidType'] = str(int(response_bytes_list[6]) << 6 >> 6)
                    value['endpointType'] = str(int(response_bytes_list[6]) << 2 >> 6)
                    value['mediumSpecificInfo'] = response_bytes_list[7]
                elif command_code == MctpCtlCmdNum.GetEUUID.value:
                    value['uuid_bytes'] = response_bytes_list[5:]
                elif command_code == MctpCtlCmdNum.GetMCTPVerSupport.value:
                    value['Version_Number_Entry_count'] = response_bytes_list[5]
                    for i in range(int(value['Version_Number_Entry_count'])):
                        major_ver = format(int(response_bytes_list[6+i*4]), '02x')
                        minor_ver = format(int(response_bytes_list[7+i*4]), '02x')
                        update_ver = format(int(response_bytes_list[8+i*4]), '02x')
                        alpha_byte = format(int(response_bytes_list[9+i*4]), '02x')
                        value.update({f'Version_Number_Entry_{i}': '0x'+update_ver+minor_ver+major_ver})
                elif command_code == MctpCtlCmdNum.GetMsgTypeSupport.value:
                    value['MCTP_Message_Type_Count'] = response_bytes_list[5]
                    for i in range(int(value['MCTP_Message_Type_Count'])):
                        value.update({f'MCTP_Message_Type_{i}': response_bytes_list[6+i]})
                elif command_code == MctpCtlCmdNum.GetVDMSupport.value:
                    value['vendorIdSetSelector'] = format(int(response_bytes_list[5]), 'x')
                    value['vendorIdFormat'] = format(int(response_bytes_list[6]), 'x')
                    value['vendorIdData'] = format(int(response_bytes_list[8]), 'x') + format(int(response_bytes_list[7]), 'x')
                    value['vendorSpecificData'] = format(int(response_bytes_list[10]), 'x') + format(int(response_bytes_list[9]), 'x')
                log.info(f'response解析：\n{json.dumps(value, indent=4)}')
                return status, value
            else:
                if not nodata:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC',
                        result_info=f'未获取到Message Data',
                        expect_info=f'获取到Message Data',
                        description_word=f'MCTP {enum_name} 指令执行失败，未获取到Message Data，Completion Code:'
                                         f' {value[MctpMsgFieldName.CompCode.value]}')
                else:
                    return value[MctpMsgFieldName.CompCode.value], value
        else:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC',
                result_info='未获取到响应',
                expect_info='获取到响应',
                description_word=f'MCTP {enum_name} 指令执行失败，未获取到响应')
        return status, value

    @classmethod
    def restart_mctp_service(cls, bmc_ip):
        cmd = f'systemctl restart xyz.openbmc_project.mctpd@pcie.service'
        status, rtn_output, _ = CommonTools.send_bmc_command(ip=bmc_ip, cmd=cmd)
        # log.info(f'MCTP restart_mctp_pcie_service 指令执行结果：\n{rtn_output}')
        return status

    @classmethod
    def send_mctp_msg(cls, bmc_ip, eid, mctp_msg_bytes_list: list, mctp_msg_timeout: str='5000'):
        """
        根据mctp要执行的报文命令,拼接成bmc 的busctl工具命令, 并在bmc侧执行命令,获取返回结果
        """
        cmd = f'busctl call xyz.openbmc_project.MCTP-pcie /xyz/openbmc_project/mctp xyz.openbmc_project.MCTP.Base'\
              f' SendReceiveMctpMessagePayload yayq'
        cmd += f' {eid}'
        cmd += f' {len(mctp_msg_bytes_list)} {" ".join(mctp_msg_bytes_list)}'
        if mctp_msg_timeout:
            cmd += f' {mctp_msg_timeout}'
        status, rtn_output, _ = CommonTools.send_bmc_command(ip=bmc_ip, cmd=cmd)
        if 'ay' in rtn_output:
            response_bytes = rtn_output.replace('ay ', '')
        else:
            response_bytes = ''
        return response_bytes

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_eid(cls, eid, ip, execute_addr, nodata: bool=False):
        """
        运行bmccli CodeType 0x02 获取eid信息
        :param eid: 目标设备的eid
        :param ip: bmc ip
        :param execute_addr: 运行bmccli工具的地址,一般为主测端ip
        :param nodata: 是否有应该返回的数据
        :return: status, value
        status: 执行状态
        value: 返回状态码,和返回内容字典
        """
        if BUSCTL:
            mctp_cmd_code = MctpCtlCmdNum.GetEID.value
            header_bytes_list = cls.mctp_control_msg_header(mctp_cmd_code)
            request_data_list = []
            msg_byte_list = header_bytes_list + request_data_list
            response_bytes = cls.send_mctp_msg(ip, eid, msg_byte_list)
            status, value = cls.mctp_response_check(mctp_cmd_code, response_bytes, nodata)
            return status, value
        else:
            cmd = f'{BMC_TOOL_PATH} -e {eid} -m 0 -c 2 --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'MCTP GetEid 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\s*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                value = {}
                if status == '0':
                    value['eid'] = findall(r'eid:(\w+)', rtn_output)[0]
                    value['eidType'] = findall(r'eidType:(\w+)', rtn_output)[0]
                    value['endpointType'] = findall(r'endpointType:(\w+)', rtn_output)[0]
                    value['mediumSpecificInfo'] = findall(r'mediumSpecificInfo:(\w+)', rtn_output)[0]
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='MCTP GetEid 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_uuid(cls, eid, ip, execute_addr, nodata: bool=False):
        """
        运行bmccli CodeType 0x03 获取uuid信息
        :param eid: 目标设备的eid
        :param ip: bmc ip
        :param execute_addr: 运行bmccli工具的地址,一般为主测端ip
        :param nodata: 是否有应该返回的数据
        :return: status, value
        status: 执行状态
        value: 返回状态码,和uuid
        """
        if BUSCTL:
            mctp_cmd_code = MctpCtlCmdNum.GetEUUID.value
            header_bytes_list = cls.mctp_control_msg_header(mctp_cmd_code)
            request_data_list = []
            msg_byte_list = header_bytes_list + request_data_list
            response_bytes = cls.send_mctp_msg(ip, eid, msg_byte_list)
            status, value = cls.mctp_response_check(mctp_cmd_code, response_bytes, nodata)
            return status, value
        else:
            cmd = f'{BMC_TOOL_PATH} -e {eid} -m 0 -c 3 --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'MCTP GetUuid 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\s*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                reversed_str = ''
                if status == '0':
                    uuid_list = findall(r'uuid:(\w+)\s+(\w+)', rtn_output)[0]
                    # value = uuid_list[0].rjust(16, '0') + uuid_list[1].rjust(16, '0')
                    log.info("获取到的UUID:{}".format(" ".join(uuid_list)))
                    value = uuid_list[0].rjust(16, '0') + uuid_list[1].rjust(16, '0')
                    reversed_str = ''.join([value[i:i + 2] for i in range(0, len(value), 2)][::-1]).lower()
                    log.info("转换+补0后,实际获取到的UUID:{}".format(reversed_str))
                return status, reversed_str
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='MCTP GetUuid 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_msgtype_support(cls, eid, ip, execute_addr, nodata: bool=False):
        if BUSCTL:
            mctp_cmd_code = MctpCtlCmdNum.GetMsgTypeSupport.value
            header_bytes_list = cls.mctp_control_msg_header(mctp_cmd_code)
            request_data_list = []
            msg_byte_list = header_bytes_list + request_data_list
            response_bytes = cls.send_mctp_msg(ip, eid, msg_byte_list)
            status, value = cls.mctp_response_check(mctp_cmd_code, response_bytes, nodata)
            type_list = []
            if not nodata:
                for index in range(int(value['MCTP_Message_Type_Count'])):
                    type_list.append(value[f'MCTP_Message_Type_{index}'])
            return status, type_list
        else:
            cmd = f'{BMC_TOOL_PATH} -e {eid} -m 0 -c 5 --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'MCTP GetMsgTypeSupport 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\s*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                value = []
                if status == '0':
                    value = findall(r'Type\[\d]:\s*(\w+)', rtn_output)
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='MCTP GetMsgTypeSupport 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_version_support(cls, eid, ip, mctpmsgtype, execute_addr, nodata: bool=False):
        if BUSCTL:
            mctp_cmd_code = MctpCtlCmdNum.GetMCTPVerSupport.value
            header_bytes_list = cls.mctp_control_msg_header(mctp_cmd_code)
            request_data_list = [hex(int(mctpmsgtype, 16))]
            msg_byte_list = header_bytes_list + request_data_list
            response_bytes = cls.send_mctp_msg(ip, eid, msg_byte_list)
            status, value = cls.mctp_response_check(mctp_cmd_code, response_bytes, nodata)
            ver_list = []
            if not nodata:
                for index in range(int(value['Version_Number_Entry_count'])):
                    ver_list.append(value[f'Version_Number_Entry_{index}'])
            return status, ver_list
        else:
            cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 0 -c 4 --mctpmsgtype={mctpmsgtype} '
                   f'--addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}')
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'MCTP GetVersionSupport 指令执行结果：\n{rtn_output}')
            m = re.search(r"status:\s*(\w+)", rtn_output, flags=re.I)
            if m:
                return_status = m.group(1)
                log.info(f"status:{return_status}, type:{type(return_status)}")
                if return_status != "0":
                    log.error("返回status错误,不寻找版本信息字符串")
                    return return_status, []
                value_list = re.findall(r'ver\[\d]:\s*(\w+)', rtn_output, flags=re.I)
                log.info(f"value:{value_list}")
                return return_status, value_list
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='MCTP GetVersionSupport 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_vdm_support(cls, eid, ip, mctpidset, execute_addr, nodata: bool=False):
        if BUSCTL:
            mctp_cmd_code = MctpCtlCmdNum.GetVDMSupport.value
            header_bytes_list = cls.mctp_control_msg_header(mctp_cmd_code)
            request_data_list = [hex(int(mctpidset, 16))]
            msg_byte_list = header_bytes_list + request_data_list
            response_bytes = cls.send_mctp_msg(ip, eid, msg_byte_list)
            status, value = cls.mctp_response_check(mctp_cmd_code, response_bytes, nodata)
            return status, value
        else:
            cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 0 -c 6 --mctpIdSet={mctpidset} '
                   f'--addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}')
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'MCTP GetVdmSupport 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\s*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                value = {}
                if status == '0':
                    value['vendorIdSetSelector'] = findall(r'vendorIdSetSelector:(\w+)', rtn_output)[0]
                    value['vendorIdFormat'] = findall(r'vendorIdFormat:(\w+)', rtn_output)[0]
                    value['vendorIdData'] = findall(r'vendorIdData:(\w+)', rtn_output)[0]
                    value['vendorSpecificData'] = findall(r'vendorSpecificData:(\w+)', rtn_output)[0]
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='MCTP GetVdmSupport 指令执行失败')


class PldmTool(ScriptBase, ABC):
    pldm_header_len = 6
    @classmethod
    def pldm_request_msg_header(cls, type: int, cmd_code: int):
        ic_bit = 0
        msg_type = int(MctpMsgType.PLDM.value, 16)
        rq_bit = 1
        d_bit = 0
        instance_id = 1
        hdr_ver = 0
        pldm_type = type
        command_code = cmd_code
        byte0 = (ic_bit << 7) | msg_type
        byte1 = (rq_bit << 7) | (d_bit << 6) | instance_id
        byte2 = (hdr_ver << 6) | pldm_type
        byte3 = command_code
        bytes = copy.deepcopy([hex(byte0), hex(byte1), hex(byte2), hex(byte3)])
        return bytes

    @classmethod
    def pldm_response_header_para(cls, response_bytes_list: list) -> dict:
        value = {}
        value['length'] = int(response_bytes_list[0])

        value[PldmMsgFieldName.IC.value] = int(response_bytes_list[1]) >> 7
        value[PldmMsgFieldName.MsgType.value] = int(response_bytes_list[1]) << 1 >> 1

        value[PldmMsgFieldName.Rq.value] = int(response_bytes_list[2]) >> 7
        value[PldmMsgFieldName.D.value] = int(response_bytes_list[2]) << 1 >> 7
        value[PldmMsgFieldName.InsId.value] = int(response_bytes_list[2]) << 3 >> 3

        value[PldmMsgFieldName.HdrVer.value] = int(response_bytes_list[3])
        value[PldmMsgFieldName.PLDMType.value] = int(response_bytes_list[3])

        value[PldmMsgFieldName.CmdCode.value] = int(response_bytes_list[4])

        value[PldmMsgFieldName.CompCode.value] = int(response_bytes_list[5])

        return value.copy()

    @classmethod
    def pldm_response_check(cls, type: int, command_code: str, response_bytes: str, nodata: bool=False) -> tuple:
        if type == PldmTypes.Type0.value:
            enum_name = CommonTools.enum_name(PldmType0CmdCodes, command_code)
        elif type == PldmTypes.Type2.value:
            enum_name = CommonTools.enum_name(PldmType2CmdCodes, command_code)
        elif type == PldmTypes.Type4.value:
            enum_name = CommonTools.enum_name(PldmType4CmdCodes, command_code)
        elif type == PldmTypes.Type5.value:
            enum_name = CommonTools.enum_name(PldmType5CmdCodes, command_code)
        elif type == PldmTypes.Type3f.value:
            enum_name = CommonTools.enum_name(PldmType3fCmdCodes, command_code)
        else:
            enum_name = ''
            log.error(f'type值错误：{type}')
            return RtnStatusEnum.FAIL.value

        log.info(f'PLDM {enum_name} 指令执行结果：\n{response_bytes}')
        if response_bytes:
            status = MctpCtlMsgCompCodes.SUCCESS.value
            response_bytes_list = response_bytes.split(' ')

            # 解析response头
            value = cls.pldm_response_header_para(response_bytes_list.copy())
            log.info(f'response头解析：\n{json.dumps(value, indent=4)}')

            # 解析response数据段
            if len(response_bytes_list) > cls.pldm_header_len:
                log.info(f'type: {type}, command_code: {command_code}')
                start_i = cls.pldm_header_len
                if type == PldmTypes.Type0.value:
                    if command_code == PldmType0CmdCodes.SetTID.value:
                        pass
                    elif command_code == PldmType0CmdCodes.GetTID.value:
                        value['Tid'] = response_bytes_list[start_i]
                    elif command_code == PldmType0CmdCodes.GetPLDMVersion.value:
                        value['nextTransferHandle'] = str(int(''.join(response_bytes_list[start_i: start_i+4])))
                        value['transferFlag'] = str(int(''.join(response_bytes_list[start_i+4])))
                        temp_str = ''
                        temp_list = reversed(response_bytes_list[start_i+5:])
                        for index in temp_list:
                            temp_str += format(int(index), '02x')
                        value['version'] =  '0x' + temp_str
                    elif command_code == PldmType0CmdCodes.GetPLDMTypes.value:
                        value['types'] = []
                        for index, byte in enumerate(response_bytes_list[start_i:]):
                            ori_type_str = bin(int(byte)).replace('0b', '')
                            value['types'] += [format(i.start() + (8*index), '02x') for i in finditer('1', ori_type_str[::-1])]
                        # ori_type_lst = list(re.findall(
                        #     r'type\s*:\s*(\w+)\s*(\w+)\s*(\w+)\s*(\w+)\s*(\w+)\s*(\w+)\s*(\w+)\s*(\w+)', rtn_output)[0])
                        # ori_type_lst.reverse()
                        # ori_type_str = ''.join(format(int(i, 16), '08b') for i in ori_type_lst)
                        # value = [format(i.start(), '02x') for i in finditer('1', ori_type_str[::-1])]
                    elif command_code == PldmType0CmdCodes.GetPLDMCommands.value:
                        value['cmds'] = []
                        for index, byte in enumerate(response_bytes_list[start_i:]):
                            ori_code_str = bin(int(byte)).replace('0b', '')
                            value['cmds'] += [format(i.start() + (8*index), '02x') for i in finditer('1', ori_code_str[::-1])]
                elif type == PldmTypes.Type2.value:
                    if command_code == PldmType2CmdCodes.SetTID.value:
                        pass
                    elif command_code == PldmType2CmdCodes.GetTID.value:
                        value['Tid'] = response_bytes_list[start_i]
                    elif command_code == PldmType2CmdCodes.GetTerminusUID.value:
                        temp_str = ''
                        temp_list = reversed(response_bytes_list[start_i:])
                        for index in temp_list:
                            temp_str += format(int(index), '02x')
                        value['uuid'] =  '0x' + temp_str
                    elif command_code == PldmType2CmdCodes.SetEventReceiver.value:
                        pass
                    elif command_code == PldmType2CmdCodes.GetEventReceiver.value:
                        value['transport_protocol_type'] = response_bytes_list[start_i]
                        temp_str = ''
                        temp_list = reversed(response_bytes_list[start_i+1:])
                        for index in temp_list:
                            temp_str += format(int(index), '02x')
                        value['evt_receiver_addr'] =  '0x' + temp_str
                    elif command_code == PldmType2CmdCodes.PlatFormEventMessage.value:
                        # todo dft
                        pass
                    elif command_code == PldmType2CmdCodes.GetSensorReading.value:
                        value['sensor_data_size'] = format(int(response_bytes_list[start_i]), 'x')
                        value['sensor_op_state'] = format(int(response_bytes_list[start_i+1]), 'x')
                        value['sensor_evt_msg_enable'] = format(int(response_bytes_list[start_i+2]), 'x')
                        value['pres_state'] = format(int(response_bytes_list[start_i+3]), 'x')
                        value['prev_state'] = format(int(response_bytes_list[start_i+4]), 'x')
                        value['evt_state'] = format(int(response_bytes_list[start_i+5]), 'x')
                        temp_str = ''
                        temp_list = reversed(response_bytes_list[start_i+6:])
                        for index in temp_list:
                            temp_str += format(int(index), '02x')
                        value['data'] = int(temp_str, 16)
                    elif command_code == PldmType2CmdCodes.GetSensorThresholds.value:
                        value['sensor_data_size'] = response_bytes_list[start_i]
                        value['upper_thold_warning'] = response_bytes_list[start_i+1]
                        value['upper_thold_crit'] = response_bytes_list[start_i+2]
                        value['upper_thold_fatal'] = response_bytes_list[start_i+3]
                        value['lower_thold_warning'] = response_bytes_list[start_i+4]
                        value['lower_thold_crit'] = response_bytes_list[start_i+5]
                        value['lower_thold_fatal'] = response_bytes_list[start_i+6]
                    elif command_code == PldmType2CmdCodes.SetSensorThresholds.value:
                        pass
                    elif command_code == PldmType2CmdCodes.GetStateSensorReading.value:
                        value['compositeSensorCount'] = response_bytes_list[start_i]
                        value['sensor_op_state'] = response_bytes_list[start_i+1]
                        value['pres_state'] = response_bytes_list[start_i+2]
                        value['prev_state'] = response_bytes_list[start_i+3]
                        value['evt_state'] = response_bytes_list[start_i+4]
                    elif command_code == PldmType2CmdCodes.SetNumericEffecterValue.value:
                        pass
                elif type == PldmTypes.Type4.value:
                    if command_code == PldmType4CmdCodes.GetFRURecordTableMetadata.value:
                        value['fru_data_major_version'] = response_bytes_list[start_i]
                        value['fru_data_minor_version'] = response_bytes_list[start_i+1]

                        temp_str = ''
                        temp_list = reversed(response_bytes_list[start_i+2:start_i+6])
                        for index in temp_list:
                            temp_str += format(int(index), '02x')
                        value['fru_sbl_max_size'] = '0x' + temp_str

                        temp_str = ''
                        temp_list = reversed(response_bytes_list[start_i+6:start_i+10])
                        for index in temp_list:
                            temp_str += format(int(index), '02x')
                        value['fru_sbl_length'] = '0x' + temp_str

                        temp_str = ''
                        temp_list = reversed(response_bytes_list[start_i+10:start_i+12])
                        for index in temp_list:
                            temp_str += format(int(index), '02x')
                        value['total_number_of_record_set_ids_in_sbl'] = '0x' + temp_str

                        temp_str = ''
                        temp_list = reversed(response_bytes_list[start_i+12:start_i+14])
                        for index in temp_list:
                            temp_str += format(int(index), '02x')
                        value['total_number_of_records_in_sbl'] = '0x' + temp_str

                        temp_str = ''
                        temp_list = reversed(response_bytes_list[start_i+14:start_i+18])
                        for index in temp_list:
                            temp_str += format(int(index), '02x')
                        value['fru_data_structure_sbl_integrity_checksum'] = '0x' + temp_str
                    elif command_code == PldmType4CmdCodes.GetFRURecordTable.value:
                        value['Tid'] = response_bytes_list[start_i]
                log.info(f'response解析：\n{json.dumps(value, indent=4)}')
                return str(value[PldmMsgFieldName.CompCode.value]), value
            else:
                if not nodata:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC',
                        result_info=f'未获取到Message Data',
                        expect_info=f'获取到Message Data',
                        description_word=f'PLDM {enum_name} 指令执行失败，未获取到Message Data，Completion Code:'
                                         f' {value[PldmMsgFieldName.CompCode.value]}')
                else:
                    return str(value[PldmMsgFieldName.CompCode.value]), value
        else:
            status = MctpCtlMsgCompCodes.ERROR.value
            value = {}
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC',
                result_info='未获取到响应',
                expect_info='获取到响应',
                description_word=f'PLDM {enum_name} 指令执行失败，未获取到响应')
        return status, value

    @classmethod
    def send_pldm_msg(cls, bmc_ip, eid, pldm_msg_bytes_list: list, pldm_msg_timeout: str='5000'):
        cmd = f'busctl call xyz.openbmc_project.MCTP-pcie /xyz/openbmc_project/mctp xyz.openbmc_project.MCTP.Base'\
              f' SendReceiveMctpMessagePayload yayq'
        cmd += f' {eid}'
        cmd += f' {len(pldm_msg_bytes_list)} {" ".join(pldm_msg_bytes_list)}'
        if pldm_msg_timeout:
            cmd += f' {pldm_msg_timeout}'
        status, rtn_output, _ = CommonTools.send_bmc_command(ip=bmc_ip, cmd=cmd)
        if 'ay' in rtn_output:
            response_bytes = rtn_output.replace('ay ', '')
        else:
            response_bytes = ''
        return response_bytes

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def set_tid_code_0(cls, eid, ip, tid, execute_addr, nodata: bool=True):
        if BUSCTL:
            pldm_type = 0
            # 设置命令码
            pldm_cmd_code = PldmType0CmdCodes.SetTID.value
            # 待发送pldm请求命令的header
            header_bytes_list = cls.pldm_request_msg_header(pldm_type, int(pldm_cmd_code, 16))
            # 待发送pldm请求命令的body
            request_data_list = [hex(int(tid, 16))]
            # 组合待发送的pldm请求命令： header + body
            msg_byte_list = header_bytes_list + request_data_list
            # 发送
            response_bytes = cls.send_pldm_msg(ip, eid, msg_byte_list)
            # 解析response。status-完成码。value-字典
            status, value = cls.pldm_response_check(pldm_type, pldm_cmd_code, response_bytes, nodata)
            # 判断完成码是否正常
            if status == str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16)):
                status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word=f'PLDM {CommonTools.enum_name(PldmType0CmdCodes, pldm_cmd_code)} TypeCode:{pldm_type} 指令执行失败',
                    result_info=f'命令完成码为{str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))}',
                    expect_info=f'命令完成码为{status}',
                )
        else:
            cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 0 -c 1 --tid={tid} --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM SetTid TypeCode:0 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\W*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                value = None
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    result_info='PLDM SetTid TypeCode:0 指令执行失败',
                    expect_info='PLDM SetTid TypeCode:0 指令执行成功',
                    description_word='PLDM SetTid TypeCode:0 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_tid_code_0(cls, eid, ip, execute_addr, nodata: bool=False):
        if BUSCTL:
            pldm_type = 0
            # 设置命令码
            pldm_cmd_code = PldmType0CmdCodes.GetTID.value
            # 待发送pldm请求命令的header
            header_bytes_list = cls.pldm_request_msg_header(pldm_type, int(pldm_cmd_code, 16))
            # 待发送pldm请求命令的body
            request_data_list = ['0x1']
            # 组合待发送的pldm请求命令： header + body
            msg_byte_list = header_bytes_list + request_data_list
            # 发送
            response_bytes = cls.send_pldm_msg(ip, eid, msg_byte_list)
            # 解析response。status-完成码。value-字典
            status, value = cls.pldm_response_check(pldm_type, pldm_cmd_code, response_bytes, nodata)
            # 判断完成码是否正常
            if status == str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16)):
                status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
                return status, value['Tid']
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word=f'PLDM {CommonTools.enum_name(PldmType0CmdCodes, pldm_cmd_code)} TypeCode:{pldm_type} 指令执行失败',
                    result_info=f'命令完成码为{str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))}',
                    expect_info=f'命令完成码为{status}',
                )
        else:
            cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 0 -c 2 --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM GetTid TypeCode:0 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\s*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                value = ''
                if status == '0':
                    value = findall(r'Tid:(\W*\w+)', rtn_output)[0]
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    result_info='PLDM GetTid TypeCode:0 指令执行失败',
                    expect_info='PLDM GetTid TypeCode:0 指令执行成功',
                    description_word='PLDM GetTid TypeCode:0 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_pldm_version(cls, eid, ip, pldmtype, transferflag, execute_addr, nodata: bool=False):
        if BUSCTL:
            pldm_type = 0
            # 设置命令码
            pldm_cmd_code = PldmType0CmdCodes.GetPLDMVersion.value
            # 待发送pldm请求命令的header
            header_bytes_list = cls.pldm_request_msg_header(pldm_type, int(pldm_cmd_code, 16))
            # 待发送pldm请求命令的body
            request_data_list = ['0x0', '0x0', '0x0', '0x0', hex(int(transferflag)), hex(int(pldmtype, 16))]
            # 组合待发送的pldm请求命令： header + body
            msg_byte_list = header_bytes_list + request_data_list
            # 发送
            response_bytes = cls.send_pldm_msg(ip, eid, msg_byte_list)
            # 解析response。status-完成码。value-字典
            status, value = cls.pldm_response_check(pldm_type, pldm_cmd_code, response_bytes, nodata)
            # 判断完成码是否正常
            if status == str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16)):
                status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
                return status, value
            else:
                if not nodata:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC',
                        description_word=f'PLDM {CommonTools.enum_name(PldmType0CmdCodes, pldm_cmd_code)} TypeCode:{pldm_type} 指令执行失败',
                        result_info=f'命令完成码为{str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))}',
                        expect_info=f'命令完成码为{status}',
                    )
                else:
                    return status, value
        else:
            cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 0 -c 3 --pldmtype={pldmtype} --transferflag={transferflag}'
                   f' --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}')
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            print(cmd)
            log.info(f'PLDM GetPldmVersion 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\s*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                value = {}
                if status == '0':
                    value['transferFlag'] = findall(r'transferFlag:(\w+)', rtn_output)[0]
                    value['nextTransferHandle'] = findall(r'nextTransferHandle:(\w+)', rtn_output)[0]
                    value['version'] = findall(r'version:(\w+)', rtn_output)[0]
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM GetPldmVersion 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_pldm_types(cls, eid, ip, execute_addr, nodata: bool=False):
        if BUSCTL:
            pldm_type = 0
            # 设置命令码
            pldm_cmd_code = PldmType0CmdCodes.GetPLDMTypes.value
            # 待发送pldm请求命令的header
            header_bytes_list = cls.pldm_request_msg_header(pldm_type, int(pldm_cmd_code, 16))
            # 待发送pldm请求命令的body
            request_data_list = ['0x1']
            # 组合待发送的pldm请求命令： header + body
            msg_byte_list = header_bytes_list + request_data_list
            # 发送
            response_bytes = cls.send_pldm_msg(ip, eid, msg_byte_list)
            # 解析response。status-完成码。value-字典
            status, value = cls.pldm_response_check(pldm_type, pldm_cmd_code, response_bytes, nodata)
            # 判断完成码是否正常
            if status == str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16)):
                status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
                return status, value['types']
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word=f'PLDM {CommonTools.enum_name(PldmType0CmdCodes, pldm_cmd_code)} TypeCode:{pldm_type} 指令执行失败',
                    result_info=f'命令完成码为{str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))}',
                    expect_info=f'命令完成码为{status}',
                )
        else:
            cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 0 -c 4 --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            print(cmd)
            log.info(f'PLDM GetPldmTypes 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\W*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                value = []
                if status == '0':
                    ori_type_lst = list(re.findall(
                        r'type\s*:\s*(\w+)\s*(\w+)\s*(\w+)\s*(\w+)\s*(\w+)\s*(\w+)\s*(\w+)\s*(\w+)', rtn_output)[0])
                    ori_type_lst.reverse()
                    ori_type_str = ''.join(format(int(i, 16), '08b') for i in ori_type_lst)
                    value = [format(i.start(), '02x') for i in finditer('1', ori_type_str[::-1])]
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM GetPldmTypes 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_pldm_command(cls, eid, ip, pldmtype, typever, execute_addr, nodata: bool=False):
        if BUSCTL:
            pldm_type = 0
            pldm_cmd_code = PldmType0CmdCodes.GetPLDMCommands.value
            # 待发送pldm请求命令的header
            header_bytes_list = cls.pldm_request_msg_header(pldm_type, int(pldm_cmd_code, 16))
            # 待发送pldm请求命令的body
            request_data_list = [hex(int(pldmtype, 16))]
            request_data_list += [hex(int(match.group(0), 16)) for match in re.finditer(r'\w{2}', format(int(typever, 16), '08x'))][::-1]
            # 组合待发送的pldm请求命令： header + body
            msg_byte_list = header_bytes_list + request_data_list
            # 发送
            response_bytes = cls.send_pldm_msg(ip, eid, msg_byte_list)
            # 解析response。status-完成码。value-字典
            status, value = cls.pldm_response_check(pldm_type, pldm_cmd_code, response_bytes, nodata)
            # 判断完成码是否正常
            if status == str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16)):
                status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
                return status, value['cmds']
            else:
                if not nodata:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC',
                        description_word=f'PLDM {CommonTools.enum_name(PldmType0CmdCodes, pldm_cmd_code)} TypeCode:{pldm_type} 指令执行失败',
                        result_info=f'命令完成码为{str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))}',
                        expect_info=f'命令完成码为{status}',
                    )
                else:
                    return status, value
        else:
            cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 0 -c 5 --pldmtype={pldmtype} --typever={typever} '
                   f'--addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}')
            print(cmd)
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM GetPldmCommand 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\s*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                value = []
                if status == '0':
                    code_str = ''
                    for i in range(8):
                        code_re = re.findall(fr'cmd\[{i}]:(\w+)', rtn_output)
                        if code_re:
                            code_str = format(int(code_re[0], 16), '08b') + code_str
                        else:
                            code_str = '00000000' + code_str
                    value = [format(i.start(), '02x') for i in finditer('1', code_str[::-1])]
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM GetPldmCommand 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def set_tid_code_2(cls, eid, ip, tid, execute_addr, nodata: bool=True):
        if BUSCTL:
            pldm_type = 2
            # 设置命令码
            pldm_cmd_code = PldmType2CmdCodes.SetTID.value
            # 待发送pldm请求命令的header
            header_bytes_list = cls.pldm_request_msg_header(pldm_type, int(pldm_cmd_code, 16))
            # 待发送pldm请求命令的body
            request_data_list = [hex(int(tid, 16))]
            # 组合待发送的pldm请求命令： header + body
            msg_byte_list = header_bytes_list + request_data_list
            # 发送
            response_bytes = cls.send_pldm_msg(ip, eid, msg_byte_list)
            # 解析response。status-完成码。value-字典
            status, value = cls.pldm_response_check(pldm_type, pldm_cmd_code, response_bytes, nodata)
            # 判断完成码是否正常
            if status == str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16)):
                status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word=f'PLDM {CommonTools.enum_name(PldmType2CmdCodes, pldm_cmd_code)} TypeCode:{pldm_type} 指令执行失败',
                    result_info=f'命令完成码为{str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))}',
                    expect_info=f'命令完成码为{status}',
                )
        else:
            cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c 1 --tid={tid} --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM SetTid TypeCode:2 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\s*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                value = None
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM SetTid TypeCode:2 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_tid_code_2(cls, eid, ip, execute_addr=CmdExecuteAdressEnum.SERVER.value, nodata: bool=False):
        if BUSCTL:
            pldm_type = 2
            # 设置命令码
            pldm_cmd_code = PldmType2CmdCodes.GetTID.value
            # 待发送pldm请求命令的header
            header_bytes_list = cls.pldm_request_msg_header(pldm_type, int(pldm_cmd_code, 16))
            # 待发送pldm请求命令的body
            request_data_list = ['0x1']
            # 组合待发送的pldm请求命令： header + body
            msg_byte_list = header_bytes_list + request_data_list
            # 发送
            response_bytes = cls.send_pldm_msg(ip, eid, msg_byte_list)
            # 解析response。status-完成码。value-字典
            status, value = cls.pldm_response_check(pldm_type, pldm_cmd_code, response_bytes, nodata)
            # 判断完成码是否正常
            if status == str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16)):
                status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
                return status, value['Tid']
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word=f'PLDM {CommonTools.enum_name(PldmType2CmdCodes, pldm_cmd_code)} TypeCode:{pldm_type} 指令执行失败',
                    result_info=f'命令完成码为{str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))}',
                    expect_info=f'命令完成码为{status}',
                )
        else:
            cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c 2 --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM GetTid TypeCode:0 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\s*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                value = None
                if status == '0':
                    value = findall(r'Tid:(\w+)', rtn_output)[0]
                # return status, value
                if value != "0":
                    return status, value

                log.warning("返回的Tid为0,此处进行bmc功能重启,重新分配eid")
                CommonTools.reboot_bmc(ip=ip, execute_addr=execute_addr)
                # , cmd:{}, status:{},result:{}".format(cmd_mctp_restart, status, rtn_output)
                # cmd_mctp_restart = f'sshpass -p {BmcEnvInfo.bmc_passwd} ssh -p {cls.test_port} {BmcEnvInfo.bmc_user_name}@{ip} systemctl restart xyz.openbmc_project.mctpd@pcie.service'
                # status, rtn_output, _ = CommandOperation.execute_command_with_error(
                #     cmd=cmd_mctp_restart, cmd_execute_address=execute_addr)
                CommonTools.sleep_time(10)
                eid_list = CommonTools.get_bmc_eid_list(ip=ip, execute_addr=execute_addr)
                if eid not in eid_list:
                    log.warning("重启BMC后,eid[{}]消失,新的eid:[{}]".format(eid, eid_list[0]))
                    eid = eid_list[0]
                cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c 2 --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
                _, rtn_output, _ = CommandOperation.execute_command_with_error(
                    cmd=cmd, cmd_execute_address=execute_addr)
                status_lst = findall(r'status:(\s*\w+)', rtn_output)
                if status_lst:
                    status = status_lst[0]

                    if status == '0':
                        value = findall(r'Tid:(\w+)', rtn_output)[0]
                        return status, value
                else:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC',
                        description_word='PLDM GetTid TypeCode:0 指令执行失败')
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM GetTid TypeCode:0 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_uuid(cls, eid, ip, execute_addr=CmdExecuteAdressEnum.SERVER.value, nodata: bool=False,
                 create_bug: bool=True):
        if BUSCTL:
            pldm_type = 2
            # 设置命令码
            pldm_cmd_code = PldmType2CmdCodes.GetTerminusUID.value
            # 待发送pldm请求命令的header
            header_bytes_list = cls.pldm_request_msg_header(pldm_type, int(pldm_cmd_code, 16))
            # 待发送pldm请求命令的body
            request_data_list = ['0x1']
            # 组合待发送的pldm请求命令： header + body
            msg_byte_list = header_bytes_list + request_data_list
            # 发送
            response_bytes = cls.send_pldm_msg(ip, eid, msg_byte_list)
            # 解析response。status-完成码。value-字典
            status, value = cls.pldm_response_check(pldm_type, pldm_cmd_code, response_bytes, nodata)
            # 判断完成码是否正常
            if status == str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16)):
                status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
                return status, value['uuid']
            else:
                if create_bug:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC',
                        description_word=f'PLDM {CommonTools.enum_name(PldmType2CmdCodes, pldm_cmd_code)} TypeCode:{pldm_type} 指令执行失败',
                        result_info=f'命令完成码为{str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))}',
                        expect_info=f'命令完成码为{status}',
                    )
                log.info("MCTP GetUuid 指令执行失败")
                return -1, ""
        else:
            cmd = f'{BMC_TOOL_PATH} -e {eid} -m 0 -c 3 --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'MCTP GetUuid 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\s*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                reversed_str = ''
                if status == '0':
                    uuid_list = findall(r'uuid:(\w+)\s+(\w+)', rtn_output)[0]
                    log.info("获取到的UUID:{}".format(" ".join(uuid_list)))
                    value = uuid_list[0].rjust(16, '0') + uuid_list[1].rjust(16, '0')
                    reversed_str = ''.join([value[i:i + 2] for i in range(0, len(value), 2)][::-1]).lower()
                    log.info("转换+补0后,实际获取到的UUID:{}".format(reversed_str))
                return status, reversed_str
            else:
                if create_bug:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC',
                        description_word='MCTP GetUuid 指令执行失败')
                log.info("MCTP GetUuid 指令执行失败")
                return -1, ""

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def set_event_receiver(cls, eid, ip, evt_enable, addr_info, transport, execute_addr, nodata: bool=False):
        if BUSCTL:
            pldm_type = 2
            # 设置命令码
            pldm_cmd_code = PldmType2CmdCodes.SetEventReceiver.value
            # 待发送pldm请求命令的header
            header_bytes_list = cls.pldm_request_msg_header(pldm_type, int(pldm_cmd_code, 16))
            # 待发送pldm请求命令的body
            request_data_list = [hex(int(str(evt_enable), 16)), hex(int(transport, 16)), hex(int(addr_info, 16)), '0x00', '0x00', '0x00']
            # 组合待发送的pldm请求命令： header + body
            msg_byte_list = header_bytes_list + request_data_list
            # 发送
            response_bytes = cls.send_pldm_msg(ip, eid, msg_byte_list)
            # 解析response。status-完成码。value-字典
            status, value = cls.pldm_response_check(pldm_type, pldm_cmd_code, response_bytes, nodata)
            # 判断完成码是否正常
            if status == str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16)):
                status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
                value = None
                return status, value
            else:
                if not nodata:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC',
                        description_word=f'PLDM {CommonTools.enum_name(PldmType2CmdCodes, pldm_cmd_code)} TypeCode:{pldm_type} 指令执行失败',
                        result_info=f'命令完成码为{str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))}',
                        expect_info=f'命令完成码为{status}',
                    )
                else:
                    return status, value
        else:
            cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c 4 --evt_msg_global_enable={evt_enable} --transport={transport}'
                   f' --addr_info={addr_info} --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}')
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM SetEventReceiver 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\s*\S+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                value = None
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM SetEventReceiver 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_event_receiver(cls, eid, ip, execute_addr, nodata: bool=False):
        if BUSCTL:
            pldm_type = 2
            # 设置命令码
            pldm_cmd_code = PldmType2CmdCodes.GetEventReceiver.value
            # 待发送pldm请求命令的header
            header_bytes_list = cls.pldm_request_msg_header(pldm_type, int(pldm_cmd_code, 16))
            # 待发送pldm请求命令的body
            request_data_list = []
            # 组合待发送的pldm请求命令： header + body
            msg_byte_list = header_bytes_list + request_data_list
            # 发送
            response_bytes = cls.send_pldm_msg(ip, eid, msg_byte_list)
            # 解析response。status-完成码。value-字典
            status, value = cls.pldm_response_check(pldm_type, pldm_cmd_code, response_bytes, nodata)
            # 判断完成码是否正常
            if status == str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16)):
                status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word=f'PLDM {CommonTools.enum_name(PldmType2CmdCodes, pldm_cmd_code)} TypeCode:{pldm_type} 指令执行失败',
                    result_info=f'命令完成码为{str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))}',
                    expect_info=f'命令完成码为{status}',
                )
        else:
            cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1  -t 2 -c 5 --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM GetEventReceiver 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\W*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                value = {}
                if status == '0':
                    value['transport_protocol_type'] = findall(r'transport_protocol_type:(\w+)', rtn_output)[0]
                    value['evt_receiver_addr'] = findall(r'evt_receiver_addr:(\w+)', rtn_output)[0]

                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM GetEventReceiver 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def platform_event_message(cls, eid, ip, execute_addr, tid=0, num=1, nodata: bool=False):
        if BUSCTL:
            # todo bmccli
            pldm_type = 2
            # 设置命令码
            pldm_cmd_code = PldmType2CmdCodes.PlatFormEventMessage.value
            # 待发送pldm请求命令的header
            header_bytes_list = cls.pldm_request_msg_header(pldm_type, int(pldm_cmd_code, 16))
            # 待发送pldm请求命令的body
            request_data_list = ['0x01', tid, '', '']
            # 组合待发送的pldm请求命令： header + body
            msg_byte_list = header_bytes_list + request_data_list
            # 发送
            response_bytes = cls.send_pldm_msg(ip, eid, msg_byte_list)
            # 解析response。status-完成码。value-字典
            status, value = cls.pldm_response_check(pldm_type, pldm_cmd_code, response_bytes, nodata)
            # 判断完成码是否正常
            if status == str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16)):
                status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word=f'PLDM {CommonTools.enum_name(PldmType2CmdCodes, pldm_cmd_code)} TypeCode:{pldm_type} 指令执行失败',
                    result_info=f'命令完成码为{str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))}',
                    expect_info=f'命令完成码为{status}',
                )
        else:
            cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c a --pldmevtfile={BMC_EVT_FILE} '
                   f'--addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}')
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM PlatformEventMessage 指令执行结果：\n{rtn_output}')
            re_event = re.findall(r'\w{4}-\w+-\w+\s\w+:\w+:\w+\sEvtShow:.*?prev_evt_state:\w{3}', rtn_output, re.S)
            if re_event:
                event = re_event[-1 * num]
                evt_dict = dict()
                format_version = re.findall(r'format_version:(\w+)', event)[0]
                if int(format_version, 16) != 1:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC',
                        description_word='PLDM PlatformEventMessage 指令format_version参数错误',
                        expect_info='0x01', result_info=format_version)
                evt_class = re.findall(r'evtClass:(\w+)', event)[0]
                if int(evt_class) != 0:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC',
                        description_word='PLDM PlatformEventMessage 指令evt_class参数错误',
                        expect_info='0', result_info=evt_class)
                sensor_offset = re.findall(r'sensor_offset:(\w+)', event)[0]
                if int(sensor_offset, 16) != 1:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC',
                        description_word='PLDM PlatformEventMessage 指令sensor_offset参数错误',
                        expect_info='0x01', result_info=sensor_offset)

                evt_dict['evt_time'] = re.findall(r'(\w{4}-\w+-\w+\s\w+:\w+:\w+)\sEvtShow', event)[0]
                evt_dict['tid'] = re.findall(r'tid:(\w+)', event)[0]
                evt_dict['sensor_id'] = re.findall(r'sensor_id:(\w+)', event)[0]
                evt_dict['enum_sensor_evt_class'] = re.findall(r'enum_sensor_evt_class:(\w+)', event)[0]
                evt_dict['evt_state'] = re.findall(r'evt_state:(\w+)', event)[0]
                return evt_dict
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM PlatformEventMessage 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_sensor_reading(cls, eid, ip, sensor, execute_addr, nodata: bool=False):
        if BUSCTL:
            pldm_type = 2
            # 设置命令码
            pldm_cmd_code = PldmType2CmdCodes.GetSensorReading.value
            # 待发送pldm请求命令的header
            header_bytes_list = cls.pldm_request_msg_header(pldm_type, int(pldm_cmd_code, 16))
            # 待发送pldm请求命令的body
            request_data_list = [hex(int(match.group(0), 16)) for match in finditer(r'\w{2}', format(int(sensor, 16), '04x'))][::-1]
            request_data_list += ['0x00']
            # 组合待发送的pldm请求命令： header + body
            msg_byte_list = header_bytes_list + request_data_list
            # 发送
            response_bytes = cls.send_pldm_msg(ip, eid, msg_byte_list)
            # 解析response。status-完成码。value-字典
            status, value = cls.pldm_response_check(pldm_type, pldm_cmd_code, response_bytes, nodata)
            # 判断完成码是否正常
            if status == str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16)):
                status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
                return status, value
            else:
                if not nodata:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC',
                        description_word=f'PLDM {CommonTools.enum_name(PldmType2CmdCodes, pldm_cmd_code)} TypeCode:{pldm_type} 指令执行失败',
                        result_info=f'命令完成码为{status}',
                        expect_info=f'命令完成码为{str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))}',
                    )
                else:
                    return status, value
        else:
            if type(sensor) == int:
                sensor = hex(sensor)
            elif "0x" not in sensor.lower():
                sensor = hex(int(sensor))

            cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1  -t 2 -c 11 --sensor={sensor} '
                   f'--addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}')
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM GetSensorReading 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\W*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                value = {}
                if status == '0':
                    value['sensor_data_size'] = findall(r'sensor_data_size:(-?\w+)', rtn_output)[0]
                    value['sensor_op_state'] = findall(r'sensor_op_state:(-?\w+)', rtn_output)[0]
                    value['sensor_evt_msg_enable'] = findall(r'sensor_evt_msg_enable:(-\w+|\w+)', rtn_output)[0]
                    value['pres_state'] = findall(r'pres_state:(-\w+|\w+)', rtn_output)[0]
                    value['prev_state'] = findall(r'prev_state:(-\w+|\w+)', rtn_output)[0]
                    value['evt_state'] = findall(r'evt_state:(-\w+|\w+)', rtn_output)[0]
                    value['data'] = findall(r'data:(-\w+|\w+)', rtn_output)[0]
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM GetSensorReading 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_sensor_thresholds(cls, eid, ip, sensor, execute_addr, nodata: bool=False):
        if BUSCTL:
            pldm_type = 2
            # 设置命令码
            pldm_cmd_code = PldmType2CmdCodes.GetSensorThresholds.value
            # 待发送pldm请求命令的header
            header_bytes_list = cls.pldm_request_msg_header(pldm_type, int(pldm_cmd_code, 16))
            # 待发送pldm请求命令的body
            request_data_list = [hex(int(match.group(0), 16)) for match in finditer(r'\w{2}', format(int(sensor, 16), '04x'))]
            # 组合待发送的pldm请求命令： header + body
            msg_byte_list = header_bytes_list + request_data_list
            # 发送
            response_bytes = cls.send_pldm_msg(ip, eid, msg_byte_list)
            # 解析response。status-完成码。value-字典
            status, value = cls.pldm_response_check(pldm_type, pldm_cmd_code, response_bytes, nodata)
            # 判断完成码是否正常
            if status == str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16)):
                status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
                return status, value
            else:
                if not nodata:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC',
                        description_word=f'PLDM {CommonTools.enum_name(PldmType2CmdCodes, pldm_cmd_code)} TypeCode:{pldm_type} 指令执行失败',
                        result_info=f'命令完成码为{str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))}',
                        expect_info=f'命令完成码为{status}',
                    )
                else:
                    return status, value
        else:
            if type(sensor) == int:
                sensor = hex(sensor)
            elif "0x" not in sensor.lower():
                sensor = hex(int(sensor))

            cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1  -t 2 -c 12 --sensor={sensor} '
                   f'--addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}')
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM GetSensorThresHolds 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\W*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                value = {}
                if status == '0':
                    value['sensor_data_size'] = findall(r'sensor_data_size:(-?\w+)', rtn_output)[0]
                    value['upper_thold_warning'] = findall(r'upper_thold_warning:(-?\w+)', rtn_output)[0]
                    value['upper_thold_crit'] = findall(r'upper_thold_crit:(-?\w+)', rtn_output)[0]
                    value['upper_thold_fatal'] = findall(r'upper_thold_fatal:(-?\w+)', rtn_output)[0]
                    value['lower_thold_warning'] = findall(r'lower_thold_warning:(-?\w+)', rtn_output)[0]
                    value['lower_thold_crit'] = findall(r'lower_thold_crit:(-?\w+)', rtn_output)[0]
                    value['lower_thold_fatal'] = findall(r'lower_thold_fatal:(-?\w+)', rtn_output)[0]
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM GetSensorThresHolds 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def set_sensor_thresholds(cls, eid, ip, execute_addr, sensor, fatal_h, fatal_l=None, warn_h=None, warn_l=None,
                              nodata: bool=True):
        if BUSCTL:
            pldm_type = 2
            # 设置命令码
            pldm_cmd_code = PldmType2CmdCodes.SetSensorThresholds.value
            # 待发送pldm请求命令的header
            header_bytes_list = cls.pldm_request_msg_header(pldm_type, int(pldm_cmd_code, 16))
            # 待发送pldm请求命令的body
            if int(sensor, 16) == 0:
                # 芯片支持的数据长度为uint8
                sersor_data_size = '0'
            else:
                # 常规光模块支持的数据长度为uint16
                sersor_data_size = '2'
            request_data_list = [hex(int(match.group(0), 16)) for match in finditer(r'\w{2}', format(int(sensor, 16), '04x'))]
            request_data_list += ['0x00']
            # 默认值
            warn_h = 0
            # upperThresholdWarning
            if warn_h:
                request_data_list += [hex(int(match.group(0), 16))
                                      for match in finditer(r'\w{2}', format(int(warn_h, 16), f'0{pow(2, int(sersor_data_size)//2+1)}x'))][::-1]
            else:
                request_data_list += [hex(int(match.group(0), 16))
                                      for match in finditer(r'\w{2}', format(0, f'0{pow(2, int(sersor_data_size)//2+1)}x'))][::-1]
            # upperThresholdCritical
            request_data_list += [hex(int(match.group(0), 16))
                                  for match in finditer(r'\w{2}', format(0, f'0{pow(2, int(sersor_data_size) // 2+1)}x'))][::-1]
            # upperThresholdFatal
            if fatal_h:
                request_data_list += [hex(int(match.group(0), 16))
                                      for match in finditer(r'\w{2}', format(int(fatal_h, 16), f'0{pow(2, int(sersor_data_size)//2+1)}x'))][::-1]
            else:
                request_data_list += [hex(int(match.group(0), 16))
                                      for match in finditer(r'\w{2}', format(0, f'0{pow(2, int(sersor_data_size)//2+1)}x'))][::-1]
            # lowerThresholdWarning
            if warn_l:
                request_data_list += [hex(int(match.group(0), 16))
                                      for match in finditer(r'\w{2}', format(int(warn_l, 16), f'0{pow(2, int(sersor_data_size)//2+1)}x'))][::-1]
            else:
                request_data_list += [hex(int(match.group(0), 16))
                                      for match in finditer(r'\w{2}', format(0, f'0{pow(2, int(sersor_data_size)//2+1)}x'))][::-1]
            # lowerThresholdCritical
            request_data_list += [hex(int(match.group(0), 16))
                                  for match in finditer(r'\w{2}', format(0, f'0{pow(2, int(sersor_data_size) // 2+1)}x'))][::-1]
            # lowerThresholdFatal
            if fatal_l:
                request_data_list += [hex(int(match.group(0), 16))
                                      for match in finditer(r'\w{2}', format(int(fatal_l, 16), f'0{pow(2, int(sersor_data_size)//2+1)}x'))][::-1]
            else:
                request_data_list += [hex(int(match.group(0), 16))
                                      for match in finditer(r'\w{2}', format(0, f'0{pow(2, int(sersor_data_size)//2+1)}x'))][::-1]
            # 补齐27字节
            for index in range(len(request_data_list), 27):
                request_data_list.append('0x00')
            # 组合待发送的pldm请求命令： header + body
            msg_byte_list = header_bytes_list + request_data_list
            # 发送
            response_bytes = cls.send_pldm_msg(ip, eid, msg_byte_list)
            # 解析response。status-完成码。value-字典
            status, value = cls.pldm_response_check(pldm_type, pldm_cmd_code, response_bytes, nodata)
            # 判断完成码是否正常
            if status == str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16)):
                status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
                value = None
                return status, value
            else:
                if not nodata:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC',
                        description_word=f'PLDM {CommonTools.enum_name(PldmType2CmdCodes, pldm_cmd_code)} TypeCode:{pldm_type} 指令执行失败',
                        result_info=f'命令完成码为{str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))}',
                        expect_info=f'命令完成码为{status}',
                    )
                else:
                    return status, value
        else:
            if type(fatal_h) == int:
                log.info(f"设置温度阈值为{fatal_h}度")
                fatal_h = hex(fatal_h)
            if fatal_l and type(fatal_l) == int:
                log.info(f"设置低温温度阈值为{fatal_l}度")
                fatal_l = hex(fatal_l)

            para_fatal_h = f' --upper_fatal={fatal_h}'
            para_fatal_l = f' --lower_fatal={fatal_l}' if fatal_l else ''
            para_warn_h = f' --upper_warn={warn_h}' if warn_h else ''
            para_warn_l = f' --lower_warn={warn_l}' if warn_l else ''
            cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c 13 --sensor={sensor}{para_fatal_h}{para_fatal_l}'
                   f'{para_warn_h}{para_warn_l} --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}')
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM SetSensorThresHolds 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\W*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                # value = None
                return status, rtn_output
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM SetSensorThresHolds 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_state_sensor_reading(cls, eid, ip, sensor, execute_addr, nodata: bool=False, check_result: bool=True):
        if BUSCTL:
            pldm_type = 2
            # 设置命令码
            pldm_cmd_code = PldmType2CmdCodes.GetStateSensorReading.value
            # 待发送pldm请求命令的header
            header_bytes_list = cls.pldm_request_msg_header(pldm_type, int(pldm_cmd_code, 16))
            # 待发送pldm请求命令的body
            request_data_list = [hex(int(match.group(0), 16)) for match in finditer(r'\w{2}', format(sensor, '04x'))]
            request_data_list += ['0x00', '0x00']
            # 组合待发送的pldm请求命令： header + body
            msg_byte_list = header_bytes_list + request_data_list
            # 发送
            response_bytes = cls.send_pldm_msg(ip, eid, msg_byte_list)
            # 解析response。status-完成码。value-字典
            status, value = cls.pldm_response_check(pldm_type, pldm_cmd_code, response_bytes, nodata)
            # 判断完成码是否正常
            if status == str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16)):
                status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word=f'PLDM {CommonTools.enum_name(PldmType2CmdCodes, pldm_cmd_code)} TypeCode:{pldm_type} 指令执行失败',
                    result_info=f'命令完成码为{str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))}',
                    expect_info=f'命令完成码为{status}',
                )
        else:
            cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c 21 --sensor={sensor} '
                   f'--addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}')
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM GetStateSensorReading 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\W*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                value = {}
                if status == '0':
                    value['sensor_op_state'] = findall(r'sensor_op_state:(-?\w+)', rtn_output)[0]
                    value['pres_state'] = findall(r'pres_state:(-?\w+)', rtn_output)[0]
                    value['prev_state'] = findall(r'prev_state:(-?\w+)', rtn_output)[0]
                    value['evt_state'] = findall(r'evt_state:(-?\w+)', rtn_output)[0]
                elif check_result:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC',
                        description_word='PLDM GetStateSensorReading 指令执行失败,未能正常获取返回结果')

                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM GetStateSensorReading 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def set_numeric_effector_value(cls, eid, ip, effecter, numeric_value, execute_addr, nodata: bool=True):
        if BUSCTL:
            pldm_type = 2
            # 设置命令码
            pldm_cmd_code = PldmType2CmdCodes.SetNumericEffecterValue.value
            # 待发送pldm请求命令的header
            header_bytes_list = cls.pldm_request_msg_header(pldm_type, int(pldm_cmd_code, 16))
            # 待发送pldm请求命令的body
            request_data_list = [effecter, '0x00' '0x00', numeric_value]
            # 组合待发送的pldm请求命令： header + body
            msg_byte_list = header_bytes_list + request_data_list
            # 发送
            response_bytes = cls.send_pldm_msg(ip, eid, msg_byte_list)
            # 解析response。status-完成码。value-字典
            status, value = cls.pldm_response_check(pldm_type, pldm_cmd_code, response_bytes, nodata)
            # 判断完成码是否正常
            if status == str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16)):
                status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
                value = None
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word=f'PLDM {CommonTools.enum_name(PldmType2CmdCodes, pldm_cmd_code)} TypeCode:{pldm_type} 指令执行失败',
                    result_info=f'命令完成码为{str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))}',
                    expect_info=f'命令完成码为{status}',
                )
        else:
            cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c 31 --effecter={effecter} --numeric_value={numeric_value} '
                   f'--addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}')
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM SetNumericEffectorValue 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\W*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                log.info('status', status)
                value = None
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM SetNumericEffectorValue 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_fru_record_table_metadata(cls, eid, ip, execute_addr, nodata: bool=False):
        if BUSCTL:
            pldm_type = 4
            # 设置命令码
            pldm_cmd_code = PldmType4CmdCodes.GetFRURecordTableMetadata.value
            # 待发送pldm请求命令的header
            header_bytes_list = cls.pldm_request_msg_header(pldm_type, int(pldm_cmd_code, 16))
            # 待发送pldm请求命令的body
            request_data_list = []
            # 组合待发送的pldm请求命令： header + body
            msg_byte_list = header_bytes_list + request_data_list
            # 发送
            response_bytes = cls.send_pldm_msg(ip, eid, msg_byte_list)
            # 解析response。status-完成码。value-字典
            status, value = cls.pldm_response_check(pldm_type, pldm_cmd_code, response_bytes, nodata)
            # 判断完成码是否正常
            if status == str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16)):
                status = str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word=f'PLDM {CommonTools.enum_name(PldmType4CmdCodes, pldm_cmd_code)} TypeCode:{pldm_type} 指令执行失败',
                    result_info=f'命令完成码为{str(int(MctpCtlMsgCompCodes.SUCCESS.value, 16))}',
                    expect_info=f'命令完成码为{status}',
                )
        else:
            cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 4 -c 1 --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM GetFruRecordTableMetadata 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\s*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                value = {}
                if status == '0':
                    value['fru_data_major_version'] = findall(r'fru_data_major_version:(\w+)', rtn_output)[0]
                    value['fru_data_minor_version'] = findall(r'fru_data_minor_version:(\w+)', rtn_output)[0]
                    value['fru_sbl_max_size'] = findall(r'fru_sbl_max_size:(\w+)', rtn_output)[0]
                    value['fru_sbl_length'] = findall(r'fru_sbl_length:(\w+)', rtn_output)[0]
                    value['total_number_of_record_set_ids_in_sbl'] = (
                        findall(r'total_number_of_record_set_ids_in_sbl:(\w+)', rtn_output))[0]
                    value['total_number_of_records_in_sbl'] = (
                        findall(r'total_number_of_records_in_sbl:(\w+)', rtn_output))[0]
                    value['fru_data_structure_sbl_integrity_checksum'] = (
                        findall(r'fru_data_structure_sbl_integrity_checksum:(-?\w+|\w+)', rtn_output))[0]
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM GetFruRecordTableMetadata 指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_fru_record_table(cls, eid, ip, frusize, transferflag, execute_addr, check_result=True):
        if BUSCTL:
            pass
        else:
            cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 4 -c 2 --frusize={frusize} --transferflag={transferflag} '
                   f'--addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}')
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM GetFruRecordTable 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\W*\w+)', rtn_output)
            if status_lst:
                status = status_lst[0]
                value = {}
                if status == '0':
                    line_lst = findall('.+', rtn_output)
                    record_index = 0
                    field_index = 0
                    for line in line_lst:
                        re_record = re.findall(r'record\[(\w+)]', line)
                        if re_record:
                            record_index = re_record[0]
                            value[record_index] = {}
                            value[record_index]['Fields'] = {}
                            continue
                        re_record_set_id = re.findall(r'recordSetId::(\w+)', line)
                        if re_record_set_id:
                            value[record_index]['recordSetId'] = re_record_set_id[0]
                            continue
                        re_record_type = re.findall(r'recordType:(\w+)', line)
                        if re_record_type:
                            value[record_index]['recordType'] = re_record_type[0]
                            continue
                        re_fields_num = re.findall(r'fieldsNum:(\w+)', line)
                        if re_fields_num:
                            value[record_index]['fieldsNum'] = re_fields_num[0]
                            continue
                        re_encoding_type = re.findall(r'EncodingType:(\w+)', line)
                        if re_encoding_type:
                            value[record_index]['EncodingType'] = re_encoding_type[0]
                            continue
                        re_fields = re.findall(r'Fields\[(\w+)]', line)
                        if re_fields:
                            field_index = re_fields[0]
                            value[record_index]['Fields'][field_index] = {}
                            continue
                        re_field_type = re.findall(r'fieldType:(\w+)', line)
                        if re_field_type:
                            value[record_index]['Fields'][field_index]['fieldType'] = re_field_type[0]
                            continue
                        re_field_type = re.findall(r'fieldLength:(\w+)', line)
                        if re_field_type:
                            value[record_index]['Fields'][field_index]['fieldLength'] = re_field_type[0]
                            continue
                        re_field = re.findall(r'field:(.*)', line)
                        if re_field:
                            value[record_index]['Fields'][field_index]['field'] = re_field[0]
                            continue
                elif check_result:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC',
                        description_word='PLDM GetFruRecordTable 指令执行失败,未能正常获取返回结果')
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM GetFruRecordTable 指令执行失败')
            cmd_stop_monitor = f'sshpass -p {BmcEnvInfo.bmc_passwd} ssh -p {cls.test_port} {BmcEnvInfo.bmc_user_name}@{ip} touch /var/FWmode'
            CommandOperation.execute_command_with_error(cmd=cmd_stop_monitor, cmd_execute_address=execute_addr)
            CommonTools.time_sleep(25)

    @classmethod
    def excute_pldm_upgrade_cmd(cls, eid, pkg_path, execute_addr, only_get_cmd=False, check_result=True):  # ip, skip_ip
        """
        author: gaoyb
        date  : 2025.12.30
        description: 带外pldm升级的前置准备动作
        :param eid: bmc上报的设备id
        :param pkg_path: 升级.bin文件路径
        :param execute_addr: 命令执行位置
        :param only_get_cmd: 执行前置动作后,是否运行升级命令,不运行则 返回升级的cmd命令
        :param check_result: 执行前置动作,并运行升级命令后, 确定是否验证升级命令执行结果,验证升级命令是否执行成功
        :return: 不运行返回cmd, 运行则返回status和result
        """
        bmc_img_path = '/var/local/appfile'
        bmc_img_name = 'image.pldm'
        bmc_ip = CommandLineArgsParse.get_server_bmc_ip()
        status = '-1'
        pkg_name = pkg_path.split('/')[-1]
        _, client_ip = CommonOperation.get_nic_logical_ip()
        CommonTools.close_monitor(bmc_ip, execute_addr)
        # cmd_cp_sh = f'scp {NIC_BMC_OPERATION_SH} {client_ip}:/root/'
        re_try = 5
        while re_try:
            cmd_cp_pkg = f'sshpass -p {BmcEnvInfo.bmc_passwd} scp {pkg_path} {BmcEnvInfo.bmc_user_name}@{bmc_ip}:{bmc_img_path}'
            cmd_mv = f"sshpass -p {BmcEnvInfo.bmc_passwd} ssh -p {cls.test_port} {BmcEnvInfo.bmc_user_name}@{bmc_ip} 'cd {bmc_img_path}; mv {pkg_name} {bmc_img_name}'"
            # CommandOperation.execute_command_with_error(cmd=cmd_cp_sh, cmd_execute_address=execute_addr)
            CommandOperation.execute_command_with_error(cmd=cmd_cp_pkg, cmd_execute_address=execute_addr)
            CommonTools.time_sleep(3)
            CommandOperation.execute_command_with_error(cmd=cmd_mv, cmd_execute_address=execute_addr)
            _, ls_output, _ = CommandOperation.execute_command_with_error(
                cmd=f"sshpass -p {BmcEnvInfo.bmc_passwd} ssh -p {cls.test_port} {BmcEnvInfo.bmc_user_name}@{bmc_ip} 'cd {bmc_img_path}; ls | grep {bmc_img_name}'",
                cmd_execute_address=execute_addr
            )
            if bmc_img_name in ls_output:
                log.info(f'升级包传输成功')
                break
            else:
                log.info(f'升级包传输失败，重试')
                re_try -= 1
        uname = BmcEnvInfo.bmc_user_name
        passwd = BmcEnvInfo.bmc_passwd

        # INTEL CPU 暂不支持BMC升级测试
        if BmcEnvInfo.get_cpu_type(CmdExecuteAdressEnum.SERVER.value) == CpuType.INTEL.value:
            log.error("Intel环境暂不支持测试")
            return ""
            # if skip_ip:
            #     cmd_upgrade = (f"{BMC_TOOL_PATH} -e {eid} -m 1 -t 5 -c 0 --addr={bmc_ip} --name={uname} "
            #                    f"--passwd='{passwd}' -d {skip_ip}")
            # else:
            #     cmd_upgrade = (f"{BMC_TOOL_PATH} -e {eid} -m 1 -t 5 -c 0 --addr={bmc_ip} --name={uname} "
            #                    f"--passwd='{passwd}'")
        else:
            status, tid = cls.get_tid_code_2(ip=bmc_ip, eid=eid, execute_addr=execute_addr)
            cmd_upgrade = (
                f"{BMC_TOOL_PATH} -e {eid} -m 1 -t 5 -c 0 -b {bmc_img_path}/{bmc_img_name} -f {tid} --addr={bmc_ip} --name={uname} "
                f"--passwd='{passwd}'")

        # 修改日志等级为INFO，提高升级速度
        server_com_ip = constants.SERVER_COM_IP
        server_com_port = constants.SERVER_COM_PORT
        cmd = f'/log info set module=0 level={FwLogLevel.WARN.value} iscfg=1'  # INFO
        SocketOption.exec_socket_cmd(cmd, server_com_ip, server_com_port)
        SocketOption.exec_socket_cmd(cmd, server_com_ip, server_com_port)

        log.info(f'升级命令： {cmd_upgrade}')
        if only_get_cmd:
            return cmd_upgrade

        log.info(f'即将开始升级，倒计时3s...')
        time.sleep(3)
        status, output_upgrade, output_err = CommandOperation.execute_command_with_error(
            cmd=cmd_upgrade, cmd_execute_address=execute_addr)
        log.info(f'status:{status}')
        output_upgrade += output_err

        # log.info(f'指令执行结果：\n{output_upgrade}')
        # log.info(f"error_info:\n{output_err}")

        if "bad" in output_upgrade.lower() or "fail" in output_upgrade.lower():
            status = '1'
            if not check_result:
                return status, output_upgrade
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC',
                description_word='PLDM FwUpgrade 执行失败,命令返回错误')
        elif 'wait update' in output_upgrade:
            status = '0'
            log.info("PLDM升级命令执行成功,status=0,wait update")
            return status, output_upgrade
        elif '' in output_upgrade:
            status = '1'
            if not check_result:
                return status, output_upgrade
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC',
                description_word='PLDM FwUpgrade 执行失败,命令返回为空')
        else:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC',
                description_word='PLDM FwUpgrade 执行失败')
        return status, output_upgrade

    @classmethod
    def get_soc_upgrade_status(cls, dev_info, execute_addr, check_result=True, upgrade_status=True, set_log_level=True):
        """
        author: gaoyb
        date  : 2025.12.30
        description: 通过cli命令,查看pldm升级状态
        :param dev_info: 设备的bdf
        :param execute_addr: 命令执行位置
        :param check_result: 是否验证返回结果
        :param upgrade_status: 验证返回结果,True为升级中, False为未升级状态
        :param set_log_level: 如果验证结果为False,未升级状态,是否通过串口还原日志等级
        :return: 升级状态,bool值: True为升级中, False为未升级状态
        """
        cmd_upgrade_state = f'{SCGBECLI64} -d {dev_info} custom {DRV_SCGBE_PF} pldmupdatestate'
        _, output_upgrade_state, _ = CommandOperation.execute_command_with_error(
            cmd=cmd_upgrade_state,
            cmd_execute_address=execute_addr)

        re_upgrade_state = findall(r'pldm_update_state\s*:\s*(\d+)', output_upgrade_state)
        if not re_upgrade_state:
            log.error(f"未能正则获取到升级状态,result:\n{output_upgrade_state}")
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC-PLDM升级',
                description_word='使用cli命令查询升级状态,查询命令执行失败,获取结果失败')

        re_upgrade_state = re_upgrade_state[0]

        if re_upgrade_state == "1":
            log.info(f'获取的status: [{re_upgrade_state}], 当前不在升级状态')
            if set_log_level:
                # 恢复日志等级
                log.info("恢复日志等级为Info")
                server_com_ip = constants.SERVER_COM_IP
                server_com_port = constants.SERVER_COM_PORT
                cmd = f'/log info set module=0 level={FwLogLevel.INFO.value} iscfg=1'  # DEBU INFO
                SocketOption.exec_socket_cmd(cmd, server_com_ip, server_com_port)
                SocketOption.exec_socket_cmd(cmd, server_com_ip, server_com_port)

            if not check_result:
                return False
        else:
            if re_upgrade_state == "8":
                log.info(f'获取的status: [{re_upgrade_state}], 当前在升级中')
            elif re_upgrade_state == "4":
                log.info(f'获取的status: [{re_upgrade_state}], 当前在启动升级')
            elif re_upgrade_state == "10":
                log.info(f'获取的status: [{re_upgrade_state}], 当前在结束升级')
            else:
                log.info(f'获取的status: [{re_upgrade_state}], 当前在升级状态')
            if not check_result:
                return True

        if re_upgrade_state == '1' and upgrade_status:
            log.error(f'PF[{dev_info}]当前不在升级状态,status:{re_upgrade_state},期望在升级状态')
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC-PLDM升级升级状态查询',
                description_word=f'PF[{dev_info}]当前不在升级状态,期望应该在升级状态')
        elif re_upgrade_state != '1' and not upgrade_status:
            log.error(f'PF[{dev_info}]当前在升级状态,status:{re_upgrade_state},期望不在升级状态')
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC-PLDM升级升级状态查询',
                description_word=f'PF[{dev_info}]当前在升级状态,status:{re_upgrade_state},期望不在升级状态')

        return re_upgrade_state

    @classmethod
    def firmware_upgrade(cls, eid, ip, pkg_path, execute_addr, px, skip_ip):
        bmc_img_path = '/var/local/appfile'
        bmc_img_name = 'image.pldm'
        if BUSCTL:
            pass
        else:
            status = '-1'
            pkg_name = pkg_path.split('/')[-1]
            _, client_ip = CommonOperation.get_nic_logical_ip()
            CommonTools.close_monitor(ip, execute_addr)
            cmd_cp_sh = f'scp {NIC_BMC_OPERATION_SH} {client_ip}:/root/'
            re_try = 5
            while re_try:
                cmd_cp_pkg = f'sshpass -p {BmcEnvInfo.bmc_passwd} scp -P {cls.test_port} {pkg_path} {BmcEnvInfo.bmc_user_name}@{ip}:{bmc_img_path}'
                cmd_mv = f"sshpass -p {BmcEnvInfo.bmc_passwd} ssh -p {cls.test_port} {BmcEnvInfo.bmc_user_name}@{ip} 'cd {bmc_img_path}; mv {pkg_name} {bmc_img_name}'"
                CommandOperation.execute_command_with_error(cmd=cmd_cp_sh, cmd_execute_address=execute_addr)
                CommandOperation.execute_command_with_error(cmd=cmd_cp_pkg, cmd_execute_address=execute_addr)
                CommonTools.time_sleep(3)
                CommandOperation.execute_command_with_error(cmd=cmd_mv, cmd_execute_address=execute_addr)
                _, ls_output, _ = CommandOperation.execute_command_with_error(
                    cmd=f"sshpass -p {BmcEnvInfo.bmc_passwd} ssh -p {cls.test_port} {BmcEnvInfo.bmc_user_name}@{ip} 'cd {bmc_img_path}; ls | grep {bmc_img_name}'",
                    cmd_execute_address=execute_addr
                )
                if bmc_img_name in ls_output:
                    log.info(f'升级包传输成功')
                    break
                else:
                    log.info(f'升级包传输失败，重试')
                    re_try -= 1
            uname = BmcEnvInfo.bmc_user_name
            passwd = BmcEnvInfo.bmc_passwd

            # INTEL CPU 暂不支持BMC升级测试
            # INTEL CPU 暂不支持BMC升级测试
            # INTEL CPU 暂不支持BMC升级测试
            if BmcEnvInfo.get_cpu_type(CmdExecuteAdressEnum.SERVER.value) == CpuType.INTEL.value:
                if skip_ip:
                    cmd_upgrade = (f"{BMC_TOOL_PATH} -e {eid} -m 1 -t 5 -c 0 --addr={ip} --name={uname} "
                                   f"--passwd='{passwd}' -d {skip_ip}")
                else:
                    cmd_upgrade = (f"{BMC_TOOL_PATH} -e {eid} -m 1 -t 5 -c 0 --addr={ip} --name={uname} "
                                   f"--passwd='{passwd}'")
            else:
                status, tid = cls.get_tid_code_2(ip=ip, eid=eid, execute_addr=execute_addr)
                cmd_upgrade = (f"{BMC_TOOL_PATH} -e {eid} -m 1 -t 5 -c 0 -b {bmc_img_path}/{bmc_img_name} -f {tid} --addr={ip} --name={uname} "
                               f"--passwd='{passwd}'")

            # 修改日志等级为INFO，提高升级速度
            server_com_ip = constants.SERVER_COM_IP
            server_com_port = constants.SERVER_COM_PORT
            cmd = f'/log info set module=0 level={FwLogLevel.WARN.value} iscfg=1'  # INFO
            SocketOption.exec_socket_cmd(cmd, server_com_ip, server_com_port)
            SocketOption.exec_socket_cmd(cmd, server_com_ip, server_com_port)

            log.info(f'升级命令： {cmd_upgrade}')
            log.info(f'即将开始升级，倒计时3s...')
            time.sleep(3)
            status, output_upgrade, output_err = CommandOperation.execute_command_with_error(
                cmd=cmd_upgrade, cmd_execute_address=execute_addr)
            log.info(f'status:{status}')
            # log.info(f'指令执行结果：\n{output_upgrade}')
            # log.info(f"error_info:\n{output_err}")
            output_upgrade += output_err
            if "bad" in output_upgrade.lower() or "fail" in output_upgrade.lower():
                status = '1'
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM FwUpgrade 执行失败,命令返回错误')
            elif 'wait update' in output_upgrade:
                status = '0'
            elif '' in output_upgrade:
                status = '1'
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM FwUpgrade 执行失败,命令返回为空')
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM FwUpgrade 执行失败')
            cmd_upgrade_state = f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} custom {DRV_SCGBE_PF} pldmupdatestate'
            # 升级后进行一次查询,必须为升级状态
            CommonTools.time_sleep(3)
            _, output_upgrade_state, _ = CommandOperation.execute_command_with_error(
                cmd=cmd_upgrade_state,
                cmd_execute_address=execute_addr)
            log.info(f'{output_upgrade_state}')
            re_upgrade_state = findall(r'pldm_update_state\s*:\s*(\d+)', output_upgrade_state)
            if re_upgrade_state:
                if re_upgrade_state[0] == '1':
                    log.error('不在升级状态')
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC-PLDM升级',
                        description_word='升级命令下发后立即查询升级状态,显示state为1,不在升级状态')
                else:
                    log.info(f'升级中, status: {re_upgrade_state[0]}')
                    CommonTools.time_sleep(25)
            else:
                log.error(f"未能正则获取到升级状态,result:\n{output_upgrade_state}")
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC-PLDM升级',
                    description_word='升级命令下发后立即查询升级状态,未能获取到升级状态')

            while True:
                CommonTools.time_sleep(5)
                _, output_upgrade_state, _ = CommandOperation.execute_command_with_error(
                    cmd=cmd_upgrade_state,
                    cmd_execute_address=execute_addr)
                log.info(f'{output_upgrade_state}')
                re_upgrade_state = findall(r'pldm_update_state\s*:\s*(\d+)', output_upgrade_state)
                if re_upgrade_state:
                    if re_upgrade_state[0] == '1':
                        log.info('不在升级状态')
                        break
                    else:
                        log.info(f'升级中, status: {re_upgrade_state[0]}')
                        # CommonTools.time_sleep(10)
                else:
                    log.info(f'custom命令获取升级状态失败，固件重启')
                    break
            CommonTools.close_monitor(ip, execute_addr)

            # 恢复日志等级
            server_com_ip = constants.SERVER_COM_IP
            server_com_port = constants.SERVER_COM_PORT
            cmd = f'/log info set module=0 level={FwLogLevel.INFO.value} iscfg=1'  # DEBU INFO
            SocketOption.exec_socket_cmd(cmd, server_com_ip, server_com_port)
            SocketOption.exec_socket_cmd(cmd, server_com_ip, server_com_port)

            return status

    @classmethod
    def new_bmc_get_oem_log(cls, eid, bmc_ip, execute_addr, only_get_cmd=False):
        "仅执行日志导出命令"
        _, client_ip = CommonOperation.get_nic_logical_ip()
        if BmcEnvInfo.cpu_type != CpuType.Teston.value:
            cmd_cp_sh = f'scp {NIC_BMC_OPERATION_SH} {client_ip}:/root/'
            CommandOperation.execute_command_with_error(cmd=cmd_cp_sh, cmd_execute_address=execute_addr)
        CommonTools.close_monitor(bmc_ip, execute_addr)

        uname = BmcEnvInfo.bmc_user_name
        passwd = BmcEnvInfo.bmc_passwd

        if BmcEnvInfo.cpu_type == CpuType.Teston.value:
            cmd_log = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 3f -c 1 '
                       f'--addr={bmc_ip} --name={uname} --passwd={passwd}')
        else:
            cmd_log = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 3f -c 1 -d {client_ip} '
                       f'--addr={bmc_ip} --name={uname} --passwd={passwd}')
        if CommandLineArgsParse.get_test_port() == 3322:
            cmd_log += " -i 3322"
        if only_get_cmd:
            log.info("日志导出命令:{}".format(only_get_cmd))
            return only_get_cmd
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd_log, cmd_execute_address=execute_addr)
        log.info(f'PLDM GetOemLog 指令执行结果：\n{rtn_output}')
        return rtn_output

    @classmethod
    def new_bmc_get_oem_log_and_check(cls, eid, bmc_ip, execute_addr, caller_class=None, check_result=True):
        """
        测试的bmc日志导出,只验证bmc命令返回状态码,暂时不会生成日志文件,返回session_id
        """
        if caller_class is None:
            caller_class = cls
        _, client_ip = CommonOperation.get_nic_logical_ip()
        if BmcEnvInfo.cpu_type != CpuType.Teston.value:
            cmd_cp_sh = f'scp {NIC_BMC_OPERATION_SH} {client_ip}:/root/'
            CommandOperation.execute_command_with_error(cmd=cmd_cp_sh, cmd_execute_address=execute_addr)
        CommonTools.close_monitor(bmc_ip, execute_addr)

        uname = BmcEnvInfo.bmc_user_name
        passwd = BmcEnvInfo.bmc_passwd

        if BmcEnvInfo.cpu_type == CpuType.Teston.value:
            cmd_log = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 3f -c 1 '
                       f'--addr={bmc_ip} --name={uname} --passwd={passwd}')
        else:
            cmd_log = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 3f -c 1 -d {client_ip} '
                       f'--addr={bmc_ip} --name={uname} --passwd={passwd}')
        if CommandLineArgsParse.get_test_port() == 3322:
            cmd_log += " -i 3322"
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd_log, cmd_execute_address=execute_addr, print_outputs=False)
        log.info(f'PLDM GetOemLog 指令执行结果：\n{rtn_output}')

        # 不验证返回结果,则直接return
        if not check_result:
            return
        # 验证返回结果
        for i in range(3):
            res = re.findall(r'status:\s*0', rtn_output, flags=re.I)
            if res:
                break
            elif not res and i == 2:
                CommonOperation.create_bug_problem(
                    caller_class,
                    key_word='BMC-日志导出',
                    expect_info='PLDM GetOemLog 指令执行成功',
                    result_info='PLDM GetOemLog 连续三次命令执行失败',
                    description_word='PLDM 日志导出,连续三次命令执行失败, status不为0')
            else:
                log.warning(f"第{i+1}次执行PLDM GetOemLog命令失败,status不为0,休眠3秒后重新尝试")
                time.sleep(3)
                _, rtn_output, _ = CommandOperation.execute_command_with_error(
                    cmd=cmd_log, cmd_execute_address=execute_addr, print_outputs=False)
                log.info(f'PLDM GetOemLog 指令执行结果：\n{rtn_output}')

        res = re.search(r'curloglen:\s+(\d+)\s+isend:\s+(\d+)\s+pad:\s+(\d+)\s+sessionid:\s+(\d+)', rtn_output, flags=re.I)
        if not res:
            log.error("返回内容正则获取失败,正则表达式:curloglen:\s+(\d+)\s+isend:\s+(\d+)\s+pad:\s+(\d+)\s+sessionid:\s+(\d+)")
            CommonOperation.create_bug_problem(
                caller_class,
                key_word='BMC-日志导出',
                expect_info='PLDM GetOemLog 返回内容正则获取成功',
                result_info='PLDM GetOemLog 返回内容正则获取失败',
                description_word='PLDM GetOemLog 返回内容正则获取失败')
        cur_log_len = res.group(1)
        isend = res.group(2)
        pad = res.group(3)
        session_id = res.group(4)
        if int(cur_log_len) < 10:
            log.warning(f"BMC-日志导出, 获取的curloglen[{cur_log_len}]小于10")
            # CommonOperation.create_bug_problem(
            #     caller_class,
            #     key_word='BMC-日志导出',
            #     description_word=f'PLDM GetOemLog 获取的curloglen[{cur_log_len}]小于10',
            #     result_info=f'PLDM GetOemLog 获取的curloglen[{cur_log_len}]小于10',
            #     expect_info=f'PLDM GetOemLog 获取的curloglen大于10',)
        if int(isend) not in [0, 1]:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word='BMC-日志导出',
                description_word=f'PLDM GetOemLog isend[{isend}]不为预期值[0, 1]',
                result_info=f'PLDM GetOemLog isend为预期值[0, 1]',
                expect_info=f'PLDM GetOemLog isend[{isend}]不为预期值[0, 1]', )
        if int(pad) not in [0]:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word='BMC-日志导出',
                description_word=f'PLDM GetOemLog pad[{pad}]不为预期值0',
                result_info=f'PLDM GetOemLog pad为预期值0',
                expect_info=f'PLDM GetOemLog pad[{pad}]不为预期值0', )
        log.info(f"获取到的session_id:{session_id}")
        return int(session_id)

    @classmethod
    def get_oem_log(cls, eid, ip, log_type, execute_addr, check_code=True, check_file=True, caller_class=None):
        # if DEBUG_NOT_SUPPORT_0609:
        #     return 0
        if caller_class is None:
            caller_class = cls
        if BUSCTL:
            pass
        else:
            # todo: 0617暂时不校验日志缺失，等BMC修改完成后放开
            check_code = False
            _, client_ip = CommonOperation.get_nic_logical_ip()
            cmd_cp_sh = f'scp {NIC_BMC_OPERATION_SH} {client_ip}:/root/'
            CommandOperation.execute_command_with_error(cmd=cmd_cp_sh, cmd_execute_address=execute_addr)
            CommonTools.close_monitor(ip, execute_addr)
            uname = BmcEnvInfo.bmc_user_name
            passwd = BmcEnvInfo.bmc_passwd
            if log_type == 0:  # 导出4K日志
                if BmcEnvInfo.cpu_type == CpuType.Teston.value:
                    cmd_log = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 3f -c 1 '
                               f'--addr={ip} --name={uname} --passwd={passwd}')
                else:
                    cmd_log = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 3f -c 1 -d {client_ip} '
                               f'--addr={ip} --name={uname} --passwd={passwd}')
            else:  # 导出全部日志
                if BmcEnvInfo.cpu_type == CpuType.Teston.value:
                    cmd_log = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 3f -c 1 '
                               f'--addr={ip} --name={uname} --passwd={passwd}')
                else:
                    cmd_log = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 3f -c 1 -d {client_ip} '  # -A 1
                               f'--addr={ip} --name={uname} --passwd={passwd}')
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd_log, cmd_execute_address=execute_addr)
            log.info(f'PLDM GetOemLog 指令执行结果：\n{rtn_output}')
            res = re.findall(r'curloglen: (\d{2,}) isend: 0 pad: 0 sessionid: 0', rtn_output)
            if res:
                if BmcEnvInfo.cpu_type != CpuType.Teston.value:
                    if execute_addr == CmdExecuteAdressEnum.SERVER.value:
                        other_addr = CmdExecuteAdressEnum.CLIENT.value
                    else:
                        other_addr = CmdExecuteAdressEnum.SERVER.value
                    _, output_ps, _ = CommandOperation.execute_command_with_error(
                        cmd='ps -ef | grep minicom',
                        cmd_execute_address=other_addr
                    )
                    # log.info(f'指令执行结果：\n{output_ps}')
                    re_log = re.findall(r'/usr/bin/minicom\s+-w\s+-D\s+\S+\s+-C\s+(\S+)', output_ps)
                    if re_log:
                        # 循环查询minicom，检查日志导出是否完成
                        count = 0
                        empty_count = 0
                        equal_count = 0
                        if log_type == 0:
                            max_count = 3
                            empty_max_count = 5
                            equal_max_count = 5
                            interverl = 10
                        else:
                            max_count = 7200
                            empty_max_count = 5
                            equal_max_count = 5
                            interverl = 60
                        time_old = ''
                        cmd_grep = f"grep -n 'termlog' {re_log[0]} | tail -n 1"
                        while count < max_count:
                            _, output_grep, _ = CommandOperation.execute_command_with_error(
                                cmd=cmd_grep, cmd_execute_address=other_addr)
                            log.info(output_grep)
                            re_time_0 = re.findall(r'\w+-\w+-\w+ \w+:\w+:\w+', output_grep)
                            log.info(f're_time_0: {re_time_0}')
                            # 未获取到日志导出关键字
                            if not re_time_0:
                                CommonTools.time_sleep(interverl)
                                empty_count += 1
                                if empty_count >= empty_max_count:
                                    log.error(f'持续{empty_count*interverl}s未获取到日志')
                                    break
                            # 获取到日志导出关键字
                            else:
                                empty_count = 0
                                # 最新日志的时间戳
                                time_0 = re_time_0[0]
                                # 时间戳有变化
                                log.info(f'time_old: {time_old}')
                                if time_old != time_0:
                                    equal_count = 0
                                    time_old = time_0
                                # 时间戳连续n次无变化，认为导出完成
                                else:
                                    equal_count += 1
                                    if equal_count >= equal_max_count:
                                        log.info(f'检测到日志无变化，第{equal_count}次，日志导出结束')
                                        break
                                    else:
                                        log.info(f'检测到日志无变化，第{equal_count}次')
                                # while True:
                                #     CommonTools.time_sleep(600)
                                #     _, output_grep, _ = CommandOperation.execute_command_with_error(
                                #         cmd=cmd_grep, cmd_execute_address=other_addr)
                                #     time_1 = re.findall(r'\w+-\w+-\w+ \w+:\w+:\w+', output_grep)[0]
                                #     if time_0 == time_1:
                                #         break
                                #     else:
                                #         time_0 = time_1
                            CommonTools.time_sleep(interverl)
                    else:
                        if log_type == 0:
                            CommonTools.time_sleep(30)
                        else:
                            CommonTools.time_sleep(600)
                    # bmc中的日志scp到服务器
                    bmc_log = BMC_LOG_PATH.split('/')[-1]
                    _, output_ls, _ = CommandOperation.execute_command_with_error(
                        cmd=f'sshpass -p {BmcEnvInfo.bmc_passwd} ssh -p {cls.test_port} {BmcEnvInfo.bmc_user_name}@{ip} "ls {BMC_LOG_PATH}"',
                        cmd_execute_address=execute_addr)
                    # log.info(f'指令执行结果：{output_ls}')
                    CommandOperation.execute_command_with_error(
                        cmd=f'rm -rf /root/{bmc_log}',
                        cmd_execute_address=execute_addr)
                    _, output_scp, _ = CommandOperation.execute_command_with_error(
                        cmd=f'sshpass -p {BmcEnvInfo.bmc_passwd} scp -P {cls.test_port} {BmcEnvInfo.bmc_user_name}@{ip}:{BMC_LOG_PATH} /root/',
                        cmd_execute_address=execute_addr)
                    # log.info(f'指令执行结果：{output_scp}')
                    _, output_find, _ = CommandOperation.execute_command_with_error(
                        cmd=f'find /root/{bmc_log}', cmd_execute_address=execute_addr)
                    # log.info(f'指令执行结果：{output_find}')
                    if check_file is False:
                        return
                    if bmc_log not in output_find and check_file:
                        CommonOperation.create_bug_problem(
                            caller_class,
                            key_word='BMC',
                            expect_info='导出日志文件成功',
                            result_info='导出日志文件失败',
                            description_word='导出日志文件失败')
                    # 校验日志前备份日志到/root/scgbe_bmc_log 路径下
                    CommandOperation.execute_command_with_error(
                        cmd=f'mkdir -p /root/{DRV_SCGBE_PF}_bmc_log', cmd_execute_address=execute_addr)
                    _, sys_time, _ = CommandOperation.execute_command_with_error(
                        cmd="date '+%Y_%m_%d_%H_%M_%S'", cmd_execute_address=execute_addr
                    )
                    CommandOperation.execute_command_with_error(
                        cmd=f'cp /root/{bmc_log} /root/{DRV_SCGBE_PF}_bmc_log/bmc_log_{sys_time}.log'
                    )
                    _, output_check, _ = CommandOperation.execute_command_with_error(
                        cmd=f'python3 {CHECK_ENCODE} /root/{bmc_log}',
                        cmd_execute_address=execute_addr)
                    # log.info(f'指令执行结果：{output_check}')
                    re_code = re.findall(r'(\d+)', output_check)
                    code = int(re_code[0])
                    if code == 0:
                        log.info('日志文件没有缺失和乱码')
                    elif code & 0b01:
                        CommonOperation.create_bug_problem(
                            ScriptBase,
                            key_word='BMC',
                            expect_info='导出日志文件编码正常',
                            result_info='导出日志文件包含乱码',
                            description_word='导出日志文件包含乱码')
                    elif code & 0b10:
                        if check_code:
                            CommonOperation.create_bug_problem(
                                caller_class,
                                key_word='BMC',
                                expect_info='导出日志完整',
                                result_info='导出日志有缺失',
                                description_word='导出日志有缺失')
                        else:
                            log.info('导出日志有缺失')
                    else:
                        CommonOperation.create_bug_problem(
                            caller_class,
                            key_word='BMC',
                            expect_info='输出日志校验结果',
                            result_info='未输出日志校验结果，未知故障',
                            description_word='未输出日志校验结果，未知故障')
                    _, output_size, _ = CommandOperation.execute_command_with_error(
                        cmd=f'ls -l --block-size=k /root/{bmc_log}',
                        cmd_execute_address=execute_addr)
                    # log.info(f'指令执行结果：\n{output_size}')
                    re_size = re.findall(r'\s+(\d+)K', output_size)
                    if not re_size:
                        CommonOperation.create_bug_problem(
                            caller_class,
                            key_word='BMC',
                            expect_info='拷贝日志文件成功',
                            result_info='拷贝日志文件失败',
                            description_word='拷贝日志文件失败')
                    size = int(re_size[0])
                    return size
                else:
                    log.warning(f'Teston CPU, 日志导出的数据BMC没有解析, 只需要关注可不可以导出数据')
                    return int(res[0])/1024
            else:
                CommonOperation.create_bug_problem(
                    caller_class,
                    key_word='BMC',
                    expect_info='PLDM GetOemLog 指令执行成功',
                    result_info='PLDM GetOemLog 指令执行失败',
                    description_word='PLDM GetOemLog 指令执行失败')
            CommonTools.close_monitor(ip=ip, execute_addr=execute_addr)
            if BmcEnvInfo.cpu_type == CpuType.Teston.value:
                CommonTools.time_sleep(10)
            else:
                CommonTools.time_sleep(25)

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def get_lldp_state(cls, eid, ip, port, execute_addr, nodata: bool=False):
        if BUSCTL:
            pass
        else:
            cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 0x3f -c 3 -C {port}  --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM get_lldp_state 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\W*\w+)', rtn_output)
            value = {}
            if status_lst:
                status = status_lst[0]
                value['port'] = findall(r'port:\s*(\w+)', rtn_output)[0]
                value['lldpEnable'] = findall(r'lldpEnable:\s*(\w+)', rtn_output)[0]
                value['adminStatus'] = findall(r'adminStatus:\s*(\w+)', rtn_output)[0]
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM get_lldp_state指令执行失败')

    @classmethod
    def bmc_get_lldp_state_cmd(cls, eid, bmc_ip, port_num) -> str:
        """
        author: yibo.gao
        date  : 2025.11.18
        description: 获取BMC查询LLDP的命令
        :param eid: bmc eid
        :param bmc_ip: bmc ip
        :param port_num: pf编号, -C参数需要指定channel编号
        return: 在server侧执行的命令
        """
        if BUSCTL:
            log.error("BUSCTL模式未适配")
            return ""
        else:
            cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 0x3f -c 3 -C {port_num}  --addr={bmc_ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
            return cmd

    @classmethod
    def bmc_get_lldp_state_and_get_result(cls, eid, bmc_ip, port_num, execute_addr=CmdExecuteAdressEnum.SERVER.value):
        """
        author: yibo.gao
        date  : 2025.11.18
        description: 获取BMC查询LLDP的命令
        :param eid: bmc eid
        :param bmc_ip: bmc ip
        :param port_num: pf编号, -C参数需要指定channel编号
        :param execute_addr:命令执行位置
        return: 查询pf的LLDP开关和模式, 查询出问题则报Bug
        """
        cmd = cls.bmc_get_lldp_state_cmd(eid=eid, bmc_ip=bmc_ip, port_num=port_num)
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        # log.info(f'PLDM get_lldp_state 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\W*\w+)', rtn_output)
        if status_lst and status_lst[0] == "0":
            # status = status_lst[0]
            real_port = re.search(r'port:\s*(\w+)', rtn_output, flags=re.I)
            m = re.search(r'lldpEnable:\s*(\w+)', rtn_output, flags=re.I)
            n = re.search(r'adminStatus:\s*(\w+)', rtn_output, flags=re.I)
            if not m or not n or not real_port:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM get_lldp_state指令,从结果中正则获取port id/lldpEnable/adminStatus失败')
            real_port = real_port.group(1)
            if int(real_port) != int(port_num):
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word=f'PLDM get_lldp_state指令,从结果中正则获取的port id[{real_port}]与实际查询的id[{port_num}]不一致')

            status = m.group(1)
            if int(status) == 0:
                status = "Off"
            elif int(status) == 1:
                status = "On"
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word=f'PLDM get_lldp_state指令,从结果中正则获取的lldpEnable[{status}]不为0或1')
            if status == "Off":
                workmode = "Disabled"
            else:
                workmode = n.group(1)
                if int(workmode) == 0:
                    workmode = "TXRX"
                elif int(workmode) == 1:
                    workmode = "TX"
                elif int(workmode) == 2:
                    workmode = "RX"
                else:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='BMC',
                        description_word=f'PLDM get_lldp_state指令,从结果中正则获取的adminStatus[{status}]不为0/1/2')
            return status, workmode

        else:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC',
                description_word='PLDM get_lldp_state指令执行失败')

    @classmethod
    def bmc_set_lldp_state_cmd(cls, eid, bmc_ip, port_num, lldp_state="On", lldp_mode="TXRX") -> str:
        """
        author: yibo.gao
        date  : 2025.11.18
        description: 获取BMC设置LLDP的命令
        :param eid: bmc eid
        :param bmc_ip: bmc ip
        :param port_num: pf编号, -C参数需要指定channel编号
        :param lldp_state: 设置的lldp state开关
        :param lldp_mode: 设置的lldp 模式
        return: 在server侧执行的命令
        """
        state = lldp_state
        if type(state) == str:
            if state.lower() == "on":
                state = 1
            else:
                state = 0
        elif type(state) == bool:
            if state:
                state = 0
            else:
                state = 1
        workmode = lldp_mode
        if type(workmode) == str:
            if "tx" in workmode.lower() and "rx" in workmode.lower():
                workmode = 0
            elif "tx" in workmode.lower():
                workmode = 1
            else:
                workmode = 2

        if BUSCTL:
            log.error("BUSCTL模式未适配")
            return ""
        else:
            cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 0x3f -c 4 -C {port_num} -S {state} -M {workmode} --addr={bmc_ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
            return cmd

    @classmethod
    def bmc_set_lldp_state_and_check_result(cls, eid, bmc_ip, port_num,  lldp_state="On", lldp_mode="TXRX", execute_addr=CmdExecuteAdressEnum.SERVER.value):
        """
        author: yibo.gao
        date  : 2025.11.18
        description: 设置BMC的LLDP状态,并验证命令是否执行成功
        :param eid: bmc eid
        :param bmc_ip: bmc ip
        :param port_num: pf编号, -C参数需要指定channel编号
        :param lldp_state: 设置的lldp state开关
        :param lldp_mode: 设置的lldp 模式
        :param execute_addr:命令执行位置
        return: None, 执行出问题报bug
        """
        cmd = cls.bmc_set_lldp_state_cmd(eid=eid, bmc_ip=bmc_ip, port_num=port_num,
                                         lldp_state=lldp_state, lldp_mode=lldp_mode)
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        # log.info(f'PLDM set_lldp_state 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\W*\w+)', rtn_output)
        if status_lst and status_lst[0] == "0":
            # status = status_lst[0]
            real_port = re.search(r'port:\s*(\w+)', rtn_output, flags=re.I)
            if not real_port:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM set_lldp_state指令,从结果中正则获取port id失败')
            real_port = real_port.group(1)
            if int(real_port) != int(port_num):
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word=f'PLDM set_lldp_state指令,从结果中正则获取的port id[{real_port}]与实际输入的id[{port_num}]不一致')
        else:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC',
                description_word='PLDM set_lldp_state指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def set_lldp_state(cls, eid, ip, port, ena, execute_addr, nodata: bool=False):
        if BUSCTL:
            pass
        else:
            cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 0x3f -c 4 -C {port} -S {ena} --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM set_lldp_state 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\W*\w+)', rtn_output)
            value = None
            if status_lst:
                status = status_lst[0]
                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM set_lldp_state指令执行失败')

    @classmethod
    # @retry(para_eid='eid', para_ip='ip', para_exec='execute_addr')
    def oem_get_fru(cls, eid, ip, execute_addr, nodata: bool=False):
        if BUSCTL:
            pass
        else:
            cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 0x3f -c 5 --addr={ip} --name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            log.info(f'PLDM oem_get_fru 指令执行结果：\n{rtn_output}')
            status_lst = findall(r'status:(\W*\w+)', rtn_output)
            value = defaultdict(dict)
            if status_lst:
                status = status_lst[0]
                value['chipTemp'] = findall(r'chipTemp:\s*(\w+),', rtn_output)[0]
                value['channalNum'] = findall(r'channalNum:\s*(\w+),', rtn_output)[0]
                value['nicState'] = findall(r'nicState:\s*(\w+)', rtn_output)[0]
                value['pn'] = findall(r'pn:\s*(.*),\s*sn', rtn_output)[0]
                value['sn'] = findall(r'sn:\s*(.*)', rtn_output)[0]
                value['fw version'] = findall(r'fw version:\s*(.*),\s*op', rtn_output)[0]
                value['optionRom version'] = findall(r'ptionRom version:\s*(\w+)', rtn_output)[0]
                port_infos = findall(r'port\[\d+]\s+info.*linkState:\s+\d+', rtn_output, re.S)
                for port_info in port_infos:
                    port = findall(r'port\[(\d+)]', port_info)[0]
                    value[port]['isAbs'] = findall(r'isAbs:\s*(\d+)', rtn_output)[0]
                    value[port]['moduleType'] = findall(r'moduleType:\s*(\d+),\s*', rtn_output)[0]
                    value[port]['modulePn'] = findall(r'modulePn:\s*(.*),\s+', rtn_output)[0]
                    value[port]['specSpeed'] = findall(r'specSpeed:\s*(\d+)', rtn_output)[0]
                    value[port]['linkSpeed'] = findall(r'linkSpeed:\s*(\d+)', rtn_output)[0]
                    value[port]['portTemp'] = findall(r'portTemp:\s*(\d+)', rtn_output)[0]
                    value[port]['linkState'] = findall(r'linkState:\s*(\d+)', rtn_output)[0]

                return status, value
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word='PLDM oem_get_fru 指令执行失败')

    @classmethod
    def get_oem_fru_0x5_result(cls, eid, ip, execute_addr=None) -> dict:
        """
        author: gaoyb
        date  : 2026.02.12
        description: BMC PLDM OEM FRU 0x5接口,获取端口基础信息
        :param eid: mctp通路需要的eid
        :param ip: bmc_ip
        :param execute_addr: 执行命令位置
        :return: 将全部信息转换为字典格式
        """
        if type(eid) == str:
            if "0x" in eid.lower():
                eid = int(eid, 16)
            else:
                eid = int(eid)
        if not CommonOperation.get_full_path(BMC_TOOL_PATH, execute_addr):
            if BmcEnvInfo.cpu_type == CpuType.INTEL.value:
                cmd = "/bin/cp {} {}".format(constants.BMC_TOOL_PATH_MCTPAPP, constants.BMC_TOOL_PATH)
            else:
                cmd = "/bin/cp {} {}".format(constants.BMC_TOOL_PATH_BUSCTL, constants.BMC_TOOL_PATH)
            CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=execute_addr)

        cmd = (f'{BMC_TOOL_PATH} -e {hex(eid)} -m 1 -t 3f -c 5 --addr={ip} '
               f'--name={BmcEnvInfo.bmc_user_name} --passwd={BmcEnvInfo.bmc_passwd} -i {cls.test_port}')
        if execute_addr:
            _, result, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr, print_outputs=False)
        else:
            _, result, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, print_outputs=False)
        log.info(f'PLDM oem_get_fru 0x5 指令执行结果：\n{result}')
        if "status:0" not in result.lower():
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC',
                description_word='oem_fru_0x5, 命令执行失败, status != 0')
        return_dict = dict() # defaultdict(dict)
        m = re.search(f"chipTemp:\s*(\d+), channelNum:\s*(\d+), nicState:\s*(\d+)", result)
        if not m:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC',
                description_word='oem_fru_0x5, 正则表达式获取chipTemp等信息失败')
        chip_temp = int(m.group(1))
        pf_num = int(m.group(2))
        nic_state = int(m.group(3))
        log.info(f"芯片温度:[{chip_temp}]℃, pf数量:[{pf_num}], 网卡status:[{nic_state}]")

        n = re.search(f"pn:\s*(.+), sn:\s*(.+)", result)
        if not n:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC',
                description_word='oem_fru_0x5, 正则表达式获取pn/sn信息失败')
        pn = n.group(1).strip()
        sn = n.group(2).strip()
        log.info(f"Part Number:[{pn}], Serial Number:[{sn}]")

        o = re.search(f"fw version:\s*(.+), optionRom version:\s*(.+)", result)
        if not o:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC',
                description_word='oem_fru_0x5, 正则表达式获取fw version信息失败')
        fw_version, opt_version = o.group(1), o.group(2)
        log.info(f"fw_version:[{fw_version}], opt_version:[{opt_version}]")

        port_info_list = result.split("\n")

        for i in range(len(port_info_list)):
            if "port[0] info:" in port_info_list[i]:
                port_info_list = port_info_list[i:]
                break
        port_info_list = [i for i in port_info_list if "isAbs: " in i]
        # print(port_info_list)
        if len(port_info_list) != pf_num:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='BMC',
                description_word=f'oem_fru_0x5, pf_num:[{pf_num}]与实际获取的port_info数量[{len(port_info_list)}]不一致')

        # 与ncsi oem接口用相同的字典
        port_speed_dict = {0x00: "Reserved",
                           0x01: "100Mbps",
                           0x02: "1Gbps",
                           0x03: "10Gbps",
                           0x04: "25Gbps",
                           0x05: "40Gbps",
                           0x06: "50Gbps",
                           0x07: "100Gbps",
                           0xa0: "AUTO",
                           0xa1: "noLink"}

        return_dict["chip_temp"] = chip_temp
        return_dict["pf_num"] = pf_num
        return_dict["nic_state"] = nic_state
        return_dict["pn"] = pn
        return_dict["sn"] = sn
        return_dict["fw_version"] = fw_version
        return_dict["opt_version"] = opt_version

        for i in range(len(port_info_list)):
            k = re.search(f"isAbs:\s*(\d+), moduleType:\s*(.+), modulePn:\s*(.*), specSpeed:\s*(\d+),"
                          f" linkSpeed:\s*(\d+), portTemp:\s*(\d+), linkState:\s*(\d+)", port_info_list[i])
            if not k:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word=f'oem_fru_0x5,  pf[{i}]从port info中正则表达式获取信息失败')
            is_abs = int(k.group(1))
            module_type = k.group(2).strip()
            module_pn = k.group(3).strip()
            spec_speed = int(k.group(4))
            link_speed = int(k.group(5))
            port_temp = int(k.group(6))
            link_state = int(k.group(7))
            log.info(f"pf[{i}], 是否在位:[{is_abs}], 端口类型:[{module_type}], 型号规格:[{module_pn}],"
                     f" 规格速率:[{port_speed_dict.get(spec_speed)}],"
                     f" 实时速率:[{port_speed_dict.get(link_speed)}], 端口温度:[{port_temp}]℃, 连接状态:[{link_state}]")
            return_dict[str(i)] = dict()
            return_dict[str(i)]["module_type"] = module_type
            return_dict[str(i)]["module_pn"] = module_pn
            return_dict[str(i)]["spec_speed"] = port_speed_dict.get(spec_speed)
            return_dict[str(i)]["link_speed"] = port_speed_dict.get(link_speed)
            return_dict[str(i)]["port_temp"] = port_temp
            return_dict[str(i)]["link_state"] = link_state
            return_dict[str(i)]["is_abs"] = is_abs

        return return_dict

    @classmethod
    def excute_mctp_cmd(cls, cmd, ip, execute_addr=None, check_result=True):
        """
       author: gaoyb
       date  : 2026.02.12
       description: 通过sshpass工具,ssh到bmc下执行mctp命令,获取返回结果
       :param cmd: mctp命令
       :param ip: bmc_ip
       :param execute_addr: 执行命令位置
       :param check_result: 验证返回结果是否正常
       :return: 将全部信息转换为字典格式
       """
        excute_cmd = (f"sshpass -p {BmcEnvInfo.bmc_passwd} ssh -p {cls.test_port} {BmcEnvInfo.bmc_user_name}@{ip} "
                      f"'{mctp_cmd_para}{cmd}'")
        if execute_addr:
            status, result, _ = CommandOperation.execute_command_with_error(
                cmd=excute_cmd, cmd_execute_address=execute_addr)
        else:
            status, result, _ = CommandOperation.execute_command_with_error(
                cmd=excute_cmd)
        if check_result:
            if status != RtnStatusEnum.SUCCESS.value or "ay" not in result.lower():
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='BMC',
                    description_word=f'MCTP命令执行失败, status:{status}, {"未打印ay" if "ay" not in result.lower() else "打印ay"}')
        return result

    @classmethod
    def get_mctp_return_info_with_index(cls, info: str,
                                   index_a: int, index_b: int = None,
                                   reverse_flag: bool = False, space_join=True,
                                   hex_flag: bool = False, hex_head=False,
                                   print_flag=True, split_num=3):
        """
        author: gaoyb
        date  : 2026.02.12
        description: 对mctp返回的报文进行获取
        :param info: 返回的可过
        :param index_a: 获取的起始位置
        :param index_b: 获取的结束位置
        :param reverse_flag: 获取到的内容,是否反转顺序
        :param hex_flag: 获取到的内容,是否转换为16进制
        :param space_join: 是否以空格拼接
        :param hex_head: 是否以16进制开头
        :param print_flag: 是否打印获取到的内容
        :param split_num: 切除前几位数据的数量,mctp返回结果为3, 也可不切除
        :return: 返回获取到的内容
        """
        if not info:
            log.error(f"返回报文为空,无法获取内容")
            CommonOperation.create_bug_problem(cls, key_word='MCTP response packet内容获取',
                                               description_word=f'返回报文为空,无法获取内容',
                                               expect_info='MCTP response packet内容获取成功',
                                               result_info='MCTP response packet内容获取失败')
            return "IndexError"
        info_list = info.split(" ")[split_num:]
        if not index_b:
            index_b = index_a
        try:
            target_list = info_list[index_a:index_b + 1]
            if reverse_flag:
                target_list = target_list[::-1]

            if hex_flag:
                if hex_head:
                    new_list = ["0x" + "%02X" % int(i) for i in target_list]
                    if print_flag:
                        log.info(" ".join(new_list))
                    if space_join:
                        return " ".join(new_list)
                    else:
                        return "0x" + "".join(new_list).replace("0x", "")
                else:
                    new_list = ["%02X" % int(i) for i in target_list]
                    if print_flag:
                        log.info(" ".join(new_list))
                    if space_join:
                        return " ".join(new_list)
                    else:
                        return "".join(new_list)
            else:
                if print_flag:
                    log.info("获取到的内容:" + " ".join(target_list))
                if space_join:
                    return " ".join(target_list)
                else:
                    return "".join(target_list)

        except IndexError:
            log.error(f"列表Index[{index_a}:{index_b}]无效,IndexError")
            CommonOperation.create_bug_problem(cls, key_word='MCTP response packet内容获取',
                                               description_word=F'从返回结果列表中获取[{index_a}:{index_b}]错误,出现IndexError',
                                               expect_info='MCTP response packet内容获取成功',
                                               result_info='MCTP response packet内容获取失败')
            return "IndexError"

    @classmethod
    def get_oem_0x80_is_err_speed_result(cls, eid, ip, execute_addr=None) -> dict:
        """
        author: gaoyb
        date  : 2026.02.12
        description: BMC PLDM OEM FRU 0x80接口, 网络端口LINK速率监控, 当出现异常降速时, 主动上报warning事件
        :param eid: mctp通路需要的eid
        :param ip: bmc_ip
        :param execute_addr: 执行命令位置
        :return: 将全部信息转换为字典格式
        """
        if type(eid) == str:
            if "0x" in eid.lower():
                eid = int(eid, 16)
            else:
                eid = int(eid)
        cmd = f"{hex(eid)} 4 1 0x81 0x3f 0x80 1000"
        result_info = cls.excute_mctp_cmd(cmd=cmd, ip=ip, execute_addr=execute_addr)
        port_speed_dict = {0x00: "Reserved",  # Unknown
                           0x01: "1Gbps",
                           0x02: "10Gbps",
                           0x04: "25Gbps",
                           0x08: "50Gbps",
                           0x10: "100Gbps", }

        port0_speed = cls.get_mctp_return_info_with_index(info=result_info, index_a=4, index_b=7,
                                                          reverse_flag=True, hex_flag=True,
                                                          print_flag=False,
                                                          space_join=False, hex_head=True)
        port1_speed = cls.get_mctp_return_info_with_index(info=result_info, index_a=8, index_b=11,
                                                          reverse_flag=True, hex_flag=True,
                                                          print_flag=False,
                                                          space_join=False, hex_head=True)
        port2_speed = cls.get_mctp_return_info_with_index(info=result_info, index_a=12, index_b=15,
                                                          reverse_flag=True, hex_flag=True,
                                                          print_flag=False,
                                                          space_join=False, hex_head=True)
        port3_speed = cls.get_mctp_return_info_with_index(info=result_info, index_a=16, index_b=19,
                                                          reverse_flag=True, hex_flag=True,
                                                          print_flag=False,
                                                          space_join=False, hex_head=True)

        port0_is_err = cls.get_mctp_return_info_with_index(info=result_info, index_a=20, index_b=23,
                                                           reverse_flag=True, hex_flag=True,
                                                           print_flag=False,
                                                           space_join=False, hex_head=True)
        port1_is_err = cls.get_mctp_return_info_with_index(info=result_info, index_a=24, index_b=27,
                                                           reverse_flag=True, hex_flag=True,
                                                           print_flag=False,
                                                           space_join=False, hex_head=True)
        port2_is_err = cls.get_mctp_return_info_with_index(info=result_info, index_a=28, index_b=31,
                                                           reverse_flag=True, hex_flag=True,
                                                           print_flag=False,
                                                           space_join=False, hex_head=True)
        port3_is_err = cls.get_mctp_return_info_with_index(info=result_info, index_a=32, index_b=35,
                                                           reverse_flag=True, hex_flag=True,
                                                           print_flag=False,
                                                           space_join=False, hex_head=True)
        # print("0x80, 网络端口LINK速率监控, 当出现异常降速时, 主动上报warning事件")
        port0_current_speed_info = "对应失败" if not port_speed_dict.get(int(port0_speed, 16)) else port_speed_dict[
            int(port0_speed, 16)]
        log.info("port0_speed: {}, {}; is_error:{}".format(port0_speed, port0_current_speed_info, int(port0_is_err, 16)))

        port1_current_speed_info = "对应失败" if not port_speed_dict.get(int(port1_speed, 16)) else port_speed_dict[
            int(port1_speed, 16)]
        log.info("port1_speed: {}, {}; is_error:{}".format(port1_speed, port1_current_speed_info, int(port1_is_err, 16)))

        port2_current_speed_info = "对应失败" if not port_speed_dict.get(int(port2_speed, 16)) else port_speed_dict[
            int(port2_speed, 16)]
        log.info("port2_speed: {}, {}; is_error:{}".format(port2_speed, port2_current_speed_info, int(port2_is_err, 16)))

        port3_current_speed_info = "对应失败" if not port_speed_dict.get(int(port3_speed, 16)) else port_speed_dict[
            int(port3_speed, 16)]
        log.info("port3_speed: {}, {}; is_error:{}".format(port3_speed, port3_current_speed_info, int(port3_is_err, 16)))

        return_dict = dict()

        return_dict["0"] = {"current_speed": port0_current_speed_info,
                            "is_error": int(port0_is_err, 16)}
        return_dict["1"] = {"current_speed": port1_current_speed_info,
                            "is_error": int(port1_is_err, 16)}
        return_dict["2"] = {"current_speed": port2_current_speed_info,
                            "is_error": int(port2_is_err, 16)}
        return_dict["3"] = {"current_speed": port3_current_speed_info,
                            "is_error": int(port3_is_err, 16)}
        return return_dict

    @classmethod
    def get_oem_0x81_is_optical_mode_alarm_result(cls, eid, ip, execute_addr=None) -> dict:
        """
        author: gaoyb
        date  : 2026.02.12
        description: BMC PLDM OEM FRU 0x81接口, 光模块健康状态监控, BMC获取光模块健康信息
        :param eid: mctp通路需要的eid
        :param ip: bmc_ip
        :param execute_addr: 执行命令位置
        :return: 将全部信息转换为字典格式
        """
        if type(eid) == str:
            if "0x" in eid.lower():
                eid = int(eid, 16)
            else:
                eid = int(eid)
        cmd = f"{hex(eid)} 4 1 0x82 0x3f 0x81 1000"
        result_info = cls.excute_mctp_cmd(cmd=cmd, ip=ip, execute_addr=execute_addr)
        sfp_alarm_dict = {
            0x0: "无异常",
            0x1: "温度高告警",
            0x2: "温度低告警",
            0x4: "电压高告警",
            0x8: "电压低告警",
            0x10: "电流高告警",
            0x20: "电流低告警",
            0x40: "tx功率高告警",
            0x80: "tx功率低告警",
            0x100: "rx功率高告警",
            0x200: "rx功率低告警",
            0x400: "sfp读取失败",
            0xffff: "未识别告警类型",
        }

        qsfp_alarm_dict = {
            0x0: "无异常",
            0x1: "温度高告警",
            0x2: "温度低告警",
            0x4: "电压高告警",
            0x8: "电压低告警",
            0x10: "电流高告警",
            0x20: "电流低告警",
            0x40: "tx功率高告警",
            0x80: "tx功率低告警",
            0x100: "rx功率高告警",
            0x200: "rx功率低告警",
            0x400: "Qsfp读取失败",
            0xffff: "未识别告警类型",
        }
        index_num = 4
        port_qsfp_alarm_list = []
        port_sfp_alarm_list = []

        # print("0x81, 光模块健康状态监控, BMC获取光模块健康信息")
        for i in range(4):
            port_qsfp_alarm = cls.get_mctp_return_info_with_index(info=result_info, index_a=index_num,
                                                                  index_b=index_num + 3,
                                                                  reverse_flag=True, hex_flag=True,
                                                                  print_flag=False,
                                                                  space_join=False, hex_head=True)
            index_num += 4
            port_qsfp_alarm_list.append(int(port_qsfp_alarm, 16))
        for i in range(4):
            port_sfp_alarm = cls.get_mctp_return_info_with_index(info=result_info, index_a=index_num,
                                                                 index_b=index_num + 3,
                                                                 reverse_flag=True, hex_flag=True,
                                                                 print_flag=False,
                                                                 space_join=False, hex_head=True)
            index_num += 4
            port_sfp_alarm_list.append(int(port_sfp_alarm, 16))
        return_dict = dict()
        for i in range(4):
            port_sfp_info = "对应失败" if not sfp_alarm_dict.get(port_sfp_alarm_list[i]) else sfp_alarm_dict[
                port_sfp_alarm_list[i]]
            port_qsfp_info = "对应失败" if not qsfp_alarm_dict.get(port_qsfp_alarm_list[i]) else qsfp_alarm_dict[
                port_qsfp_alarm_list[i]]
            log.info(
                f"port{i}: sfp: {port_sfp_alarm_list[i]}, {port_sfp_info}; qsfp:{port_qsfp_alarm_list[i]}, {port_qsfp_info}")
            # 按照Port index返回对应port的sfp/qsfp告警信息
            return_dict[str(i)] = {"sfp":{"number": port_sfp_alarm_list[i],
                                          "info": port_sfp_info},
                                   "qsfp":{"number": port_qsfp_alarm_list[i],
                                           "info": port_qsfp_info},
                                   }
        return return_dict

    @classmethod
    def get_oem_0x82_optical_mode_status_result(cls, eid, ip, execute_addr=None) -> dict:
        """
        author: gaoyb
        date  : 2026.02.12
        description: BMC PLDM OEM FRU 0x82接口, 光模块在位信息监控, 当出现光模块插拔时, 主动上报事件
        :param eid: mctp通路需要的eid
        :param ip: bmc_ip
        :param execute_addr: 执行命令位置
        :return: 将全部信息转换为字典格式
        """
        if type(eid) == str:
            if "0x" in eid.lower():
                eid = int(eid, 16)
            else:
                eid = int(eid)
        cmd = f"{hex(eid)} 4 1 0x82 0x3f 0x82 1000"
        result_info = cls.excute_mctp_cmd(cmd=cmd, ip=ip, execute_addr=execute_addr)
        index_num = 4
        port_is_present_list = []
        port_is_report_list = []
        # print("0x82, 光模块在位信息监控, 当出现光模块插拔时, 主动上报事件")
        for i in range(4):
            port_is_present = cls.get_mctp_return_info_with_index(info=result_info, index_a=index_num,
                                                                  index_b=index_num,
                                                                  reverse_flag=True, hex_flag=True,
                                                                  print_flag=False,
                                                                  space_join=False, hex_head=True)
            index_num += 1
            port_is_present_list.append(int(port_is_present, 16))
        for i in range(4):
            port_is_report = cls.get_mctp_return_info_with_index(info=result_info, index_a=index_num, index_b=index_num,
                                                                 reverse_flag=True, hex_flag=True,
                                                                 print_flag=False,
                                                                 space_join=False, hex_head=True)
            index_num += 1
            port_is_report_list.append(int(port_is_report, 16))

        return_dict = dict()
        for i in range(4):
            log.info(
                f"port{i}: is_present: {port_is_present_list[i]}; is_report:{port_is_report_list[i]}")
            # 按照Port index返回对应port的在位/上报信息
            return_dict[str(i)] = {"is_present": port_is_present_list[i],
                                   "is_report": port_is_report_list[i]}
        return return_dict

    @classmethod
    def get_oem_0x83_txrx_buffer_usage_result(cls, eid, ip, execute_addr=None) -> dict:
        """
        author: gaoyb
        date  : 2026.02.12
        description: BMC PLDM OEM FRU 0x83接口, 端口TX/RX buffer占用率, 反馈链路拥塞情况, 供BMC定时查询监控
        :param eid: mctp通路需要的eid
        :param ip: bmc_ip
        :param execute_addr: 执行命令位置
        :return: 将全部信息转换为字典格式
        """
        if type(eid) == str:
            if "0x" in eid.lower():
                eid = int(eid, 16)
            else:
                eid = int(eid)
        cmd = f"{hex(eid)} 4 1 0x82 0x3f 0x83 1000"
        result_info = cls.excute_mctp_cmd(cmd=cmd, ip=ip, execute_addr=execute_addr)
        index_num = 4
        port_rx_buffer_list = []
        port_tx_buffer_list = []
        # print("0x83, 端口TX/RX buffer占用率, 反馈链路拥塞情况, 供BMC定时查询监控")
        for i in range(4):
            port_rx_buff = cls.get_mctp_return_info_with_index(info=result_info, index_a=index_num,
                                                               index_b=index_num + 3,
                                                               reverse_flag=True, hex_flag=True,
                                                               print_flag=False,
                                                               space_join=False, hex_head=True)
            index_num += 4
            port_rx_buffer_list.append(int(port_rx_buff, 16))
        for i in range(4):
            port_tx_buff = cls.get_mctp_return_info_with_index(info=result_info, index_a=index_num,
                                                               index_b=index_num + 3,
                                                               reverse_flag=True, hex_flag=True,
                                                               print_flag=False,
                                                               space_join=False, hex_head=True)
            index_num += 1
            port_tx_buffer_list.append(int(port_tx_buff, 16))
        return_dict = dict()
        for i in range(4):
            log.info(
                f"port{i}: tx_buffer_usage: {port_rx_buffer_list[i]}%; rx_buffer_usage:{port_tx_buffer_list[i]}%")

            return_dict[str(i)] = {"tx_buffer_usage": port_rx_buffer_list[i],
                                   "rx_buffer_usage": port_tx_buffer_list[i]}
        return return_dict

    @classmethod
    def get_oem_0x84_optical_mod_info_result(cls, eid, ip, execute_addr=None) -> dict:
        """
        author: gaoyb
        date  : 2026.02.12
        description: BMC PLDM OEM FRU 0x84接口, 光模块健康信息, 电压,电流,tx功率,rx功率,温度,健康信息只有光模块在位就一直上报
        :param eid: mctp通路需要的eid
        :param ip: bmc_ip
        :param execute_addr: 执行命令位置
        :return: 将全部信息转换为字典格式
        """
        if type(eid) == str:
            if "0x" in eid.lower():
                eid = int(eid, 16)
            else:
                eid = int(eid)
        cmd = f"{hex(eid)} 4 1 0x82 0x3f 0x84 1000"
        result_info = cls.excute_mctp_cmd(cmd=cmd, ip=ip, execute_addr=execute_addr)
        index_num = 4
        return_dict = {
            "0": {},
            "1": {},
            "2": {},
            "3": {},
        }

        def bytes_to_s32(input_info):
            if type(input_info) == str:
                if "0x" in input_info.lower():
                    input_info = int(input_info, 16)
                else:
                    input_info = int(input_info)
            # 处理有符号整数（补码转换）
            if input_info & 0x80000000:  # 检查符号位
                input_info = input_info - 0x100000000

            return input_info

        def mw_to_dbm(power_mw):
            if power_mw <= 0:
                # print(f"功率值不能为负数，收到: {power_mw} mW")
                return -99.999

            result = 10 * math.log10(power_mw)
            return round(result, 3)

        def get_info_and_print(add_list, print_name, unit_info, divided_info=0, index_width=4, print_flag=True):
            nonlocal index_num
            for k in range(4):
                # print("index_num:{}".format(index_num))
                port_info = cls.get_mctp_return_info_with_index(info=result_info, index_a=index_num,
                                                                index_b=index_num + index_width - 1,
                                                                reverse_flag=True, hex_flag=True,
                                                                print_flag=False,
                                                                space_join=False, hex_head=True)
                index_num += index_width
                if divided_info:
                    port_info = bytes_to_s32(int(port_info, 16)) / divided_info
                else:
                    port_info = bytes_to_s32(int(port_info, 16))
                add_list.append(port_info)
            if print_flag:
                log.info(f"{print_name}, port0: [{add_list[0]}]{unit_info}; port1: [{add_list[1]}]{unit_info};"
                      f" port2: [{add_list[2]}]{unit_info}; port3: [{add_list[3]}]{unit_info}")
                if "sfp" in print_name and "power" in print_name:
                    log.info(f"{print_name}, port0: [{mw_to_dbm(add_list[0])}]dBm; port1: [{mw_to_dbm(add_list[1])}]dBm;"
                          f" port2: [{mw_to_dbm(add_list[2])}]dBm; port3: [{mw_to_dbm(add_list[3])}]dBm")
            return_dict["0"][print_name] = add_list[0]
            return_dict["1"][print_name] = add_list[1]
            return_dict["2"][print_name] = add_list[2]
            return_dict["3"][print_name] = add_list[3]

        # print("0x84, 光模块健康信息, 电压,电流,tx功率,rx功率,温度,健康信息只有光模块在位就一直上报")
        port_qsfp_temp_list = []
        get_info_and_print(add_list=port_qsfp_temp_list, print_name="qsfp_temp", unit_info="℃", divided_info=256)

        port_qsfp_vcc_list = []
        get_info_and_print(add_list=port_qsfp_vcc_list, print_name="qsfp_vcc", unit_info="V", divided_info=10000)

        port_qsfp_tx1_bias_list = []
        get_info_and_print(add_list=port_qsfp_tx1_bias_list, print_name="qsfp_tx1_bias", unit_info="mA",
                           divided_info=1000)

        port_qsfp_tx2_bias_list = []
        get_info_and_print(add_list=port_qsfp_tx2_bias_list, print_name="qsfp_tx2_bias", unit_info="mA",
                           divided_info=1000)

        port_qsfp_tx3_bias_list = []
        get_info_and_print(add_list=port_qsfp_tx3_bias_list, print_name="qsfp_tx3_bias", unit_info="mA",
                           divided_info=1000)

        port_qsfp_tx4_bias_list = []
        get_info_and_print(add_list=port_qsfp_tx4_bias_list, print_name="qsfp_tx4_bias", unit_info="mA",
                           divided_info=1000)

        port_qsfp_tx1_power_list = []
        get_info_and_print(add_list=port_qsfp_tx1_power_list, print_name="qsfp_tx1_power", unit_info="mW",
                           divided_info=10000)

        port_qsfp_tx2_power_list = []
        get_info_and_print(add_list=port_qsfp_tx2_power_list, print_name="qsfp_tx2_power", unit_info="mW",
                           divided_info=10000)

        port_qsfp_tx3_power_list = []
        get_info_and_print(add_list=port_qsfp_tx3_power_list, print_name="qsfp_tx3_power", unit_info="mW",
                           divided_info=10000)

        port_qsfp_tx4_power_list = []
        get_info_and_print(add_list=port_qsfp_tx4_power_list, print_name="qsfp_tx4_power", unit_info="mW",
                           divided_info=10000)

        port_qsfp_rx1_power_list = []
        get_info_and_print(add_list=port_qsfp_rx1_power_list, print_name="qsfp_rx1_power", unit_info="mW",
                           divided_info=10000)

        port_qsfp_rx2_power_list = []
        get_info_and_print(add_list=port_qsfp_rx2_power_list, print_name="qsfp_rx2_power", unit_info="mW",
                           divided_info=10000)

        port_qsfp_rx3_power_list = []
        get_info_and_print(add_list=port_qsfp_rx3_power_list, print_name="qsfp_rx3_power", unit_info="mW",
                           divided_info=10000)

        port_qsfp_rx4_power_list = []
        get_info_and_print(add_list=port_qsfp_rx4_power_list, print_name="qsfp_rx4_power", unit_info="mW",
                           divided_info=10000)

        port_sfp_temp_list = []
        get_info_and_print(add_list=port_sfp_temp_list, print_name="sfp_temp", unit_info="℃",
                           divided_info=256)

        port_sfp_vcc_list = []
        get_info_and_print(add_list=port_sfp_vcc_list, print_name="sfp_vcc", unit_info="V",
                           divided_info=10000)

        port_sfp_tx_bias_list = []
        get_info_and_print(add_list=port_sfp_tx_bias_list, print_name="sfp_tx_bias", unit_info="mA",
                           divided_info=1000)

        port_sfp_tx_power_list = []
        get_info_and_print(add_list=port_sfp_tx_power_list, print_name="sfp_tx_power", unit_info="mW",
                           divided_info=10000)

        port_sfp_rx_power_list = []
        get_info_and_print(add_list=port_sfp_rx_power_list, print_name="sfp_rx_power", unit_info="mW",
                           divided_info=10000)

        port_is_report_list = []
        get_info_and_print(add_list=port_is_report_list, print_name="is_report", unit_info="", index_width=1,
                           divided_info=0)

        return return_dict

    @classmethod
    def get_oem_0x88_ras_status_result(cls, eid, ip, execute_addr=None) -> dict:
        """
        author: gaoyb
        date  : 2026.02.12
        description: BMC PLDM OEM FRU 0x88接口, 端口网络端口报文统计信息监控,包括总收包个数, 总丢包个数, LINKDown丢包个数,
        总错包个数, CRC错包个数, 发送Pause帧个数
        :param eid: mctp通路需要的eid
        :param ip: bmc_ip
        :param execute_addr: 执行命令位置
        :return: 将全部信息转换为字典格式
        """
        if type(eid) == str:
            if "0x" in eid.lower():
                eid = int(eid, 16)
            else:
                eid = int(eid)
        cmd = f"{hex(eid)} 4 1 0x82 0x3f 0x88 1000"
        result_info = cls.excute_mctp_cmd(cmd=cmd, ip=ip, execute_addr=execute_addr)
        index_num = 4
        rx_packets_list = list()
        rx_dropped_list = list()
        tx_link_down_dropped_list = list()
        rx_error_packet_list = list()
        rx_crc_error_packet_list = list()
        rx_pause_packet_list = list()
        return_dict = dict()
        # print("0x88, 网络端口报文统计信息监控,包括总收包个数, 总丢包个数, LINKDown丢包个数, 总错包个数, CRC错包个数, 发送Pause帧个数")
        for i in range(4):
            port_rx_packets = cls.get_mctp_return_info_with_index(info=result_info, index_a=index_num,
                                                                  index_b=index_num + 7,
                                                                  reverse_flag=True, hex_flag=True,
                                                                  print_flag=False,
                                                                  space_join=False, hex_head=True)
            index_num += 8
            rx_packets_list.append(int(port_rx_packets, 16))

            port_rx_dropped = cls.get_mctp_return_info_with_index(info=result_info, index_a=index_num,
                                                                  index_b=index_num + 7,
                                                                  reverse_flag=True, hex_flag=True,
                                                                  print_flag=False,
                                                                  space_join=False, hex_head=True)
            index_num += 8
            rx_dropped_list.append(int(port_rx_dropped, 16))

            port_tx_link_down_dropped = cls.get_mctp_return_info_with_index(info=result_info, index_a=index_num,
                                                                            index_b=index_num + 7,
                                                                            reverse_flag=True, hex_flag=True,
                                                                            print_flag=False,
                                                                            space_join=False, hex_head=True)
            index_num += 8
            tx_link_down_dropped_list.append(int(port_tx_link_down_dropped, 16))

            port_rx_error_packet = cls.get_mctp_return_info_with_index(info=result_info, index_a=index_num,
                                                                       index_b=index_num + 7,
                                                                       reverse_flag=True, hex_flag=True,
                                                                       print_flag=False,
                                                                       space_join=False, hex_head=True)
            index_num += 8
            rx_error_packet_list.append(int(port_rx_error_packet, 16))

            port_rx_crc_error_packet = cls.get_mctp_return_info_with_index(info=result_info, index_a=index_num,
                                                                           index_b=index_num + 7,
                                                                           reverse_flag=True, hex_flag=True,
                                                                           print_flag=False,
                                                                           space_join=False, hex_head=True)
            index_num += 8
            rx_crc_error_packet_list.append(int(port_rx_crc_error_packet, 16))

            port_rx_pause_packet = cls.get_mctp_return_info_with_index(info=result_info, index_a=index_num,
                                                                       index_b=index_num + 7,
                                                                       reverse_flag=True, hex_flag=True,
                                                                       print_flag=False,
                                                                       space_join=False, hex_head=True)
            index_num += 8
            rx_pause_packet_list.append(int(port_rx_pause_packet, 16))

            log.info(f"port{i}: rx_packets:[{rx_packets_list[i]}]; rx_dropped:[{rx_dropped_list[i]}];"
                     f" tx_link_down_dropped:[{tx_link_down_dropped_list[i]}]; rx_error_packet:[{rx_error_packet_list[i]}]"
                     f" rx_crc_error_packet:[{rx_crc_error_packet_list[i]}]; rx_pause_packet:[{rx_pause_packet_list[i]}]")

            return_dict[str(i)] = {
                "rx_packets": rx_packets_list[i],
                "rx_dropped": rx_dropped_list[i],
                "tx_link_down_dropped": tx_link_down_dropped_list[i],
                "rx_error_packet": rx_error_packet_list[i],
                "rx_crc_error_packet": rx_crc_error_packet_list[i],
                "rx_pause_packet": rx_pause_packet_list[i]
            }
        return return_dict

class CliCommonUtils(ScriptBase, ABC):

    @classmethod
    def check_nic_state(cls, device_name: str, cmd_execute_address: str, expect: bool):
        rtn_status = True
        # exec_command = f'ifconfig {device_name}'
        exec_command = f'ip a | grep {device_name}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info(f'指令返回结果：\n{rtn_outputs}')
        # if 'UP' in rtn_outputs and 'RUNNING' not in rtn_outputs:
        if 'state DOWN' in rtn_outputs:
            rtn_status = False
        if expect:
            if rtn_status:
                log.info('端口状态正常，符合预期')
            else:
                CommonOperation.create_bug_problem(cls,
                                                   key_word='cli命令',
                                                   description_word='端口状态异常，不符合预期',
                                                   expect_info='端口状态正常',
                                                   result_info='端口状态异常')
        else:
            if rtn_status:
                CommonOperation.create_bug_problem(cls,
                                                   key_word='cli命令',
                                                   description_word='端口状态正常，不符合预期',
                                                   expect_info='端口状态异常',
                                                   result_info='端口状态正常')
            else:
                log.info('端口状态异常，符合预期')

    @classmethod
    def get_system_time(cls, cmd_execute_address: str):
        _, rtn_time, _ = CommandOperation.execute_command_with_error(
            "date --rfc-3339=seconds", cmd_execute_address=cmd_execute_address)
        system_time = rtn_time[0:19]
        return system_time

    @classmethod
    def check_firmware_state(cls, cmd_execute_address: str):
        exec_command = "python3 /root/sagitta_serial_cli.py '/comm show reg type=A width=32 addr=0x5EB30004'"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            result = re.search(PATTERN_UART_TABLE_CONTENT_SHOW_REG, rtn_outputs)
            if result:
                if int(result.group(4), 16) == 48:
                    log.info('0x5EB30004寄存器值正确')
                else:
                    CommonOperation.create_bug_problem(cls, key_word='版本升级',
                                                       description_word=f'0x5EB30004寄存器值不正确')
            else:
                CommonOperation.create_bug_problem(cls, key_word='版本升级',
                                                   description_word=f'0x5EB30004寄存器查询结果格式不正确')
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(cls, key_word='版本升级',
                                               description_word=f'寄存器查询命令执行失败')

        exec_command = "python3 /root/sagitta_serial_cli.py '/comm show reg type=A width=32 addr=0x5EB30104'"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            result = re.search(PATTERN_UART_TABLE_CONTENT_SHOW_REG, rtn_outputs)
            if result:
                if int(result.group(4), 16) == 48:
                    log.info('0x5EB30104寄存器值正确')
                else:
                    CommonOperation.create_bug_problem(cls, key_word='版本升级',
                                                       description_word=f'0x5EB30104寄存器值不正确')
            else:
                CommonOperation.create_bug_problem(cls, key_word='版本升级',
                                                   description_word=f'0x5EB30104寄存器查询结果格式不正确')
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(cls, key_word='版本升级',
                                               description_word=f'寄存器查询命令执行失败')

    @classmethod
    def check_host_state(cls, cmd_execute_address: str):
        exec_command = 'ifconfig'
        rtn_code, _, _ = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info('主机状态检查通过')
        else:
            CommonOperation.create_bug_problem(cls, key_word='固件',
                                               description_word=f'主机状态异常')

    @classmethod
    def check_lspci(cls, cmd_execute_address: str):
        host_para = HostPara()
        exec_command = f"lspci | grep -E '{host_para.VENDOR_ID}|{VENDOR_ID_NAME}|Stars' | grep -v Virtual"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value and \
                ('net' in rtn_outputs):
            log.info('检查建链成功')
        else:
            CommonOperation.create_bug_problem(cls, key_word='版本升级',
                                               description_word=f'建链失败')

    @classmethod
    def check_ping(cls, dst_ip: str, src_ip: str, cmd_execute_address: str):
        exec_command = f'ping {dst_ip} -I {src_ip} -c 1'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            if ' 0%' in rtn_outputs or '(0% ' in rtn_outputs:
                pass
            else:
                CommonOperation.create_bug_problem(case_cls=cls, key_word="片外cli-reset soc",
                                                   description_word="ping丢包")
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

    @classmethod
    def unpack(cls, tar_path: str):
        CommonOperation.concat_test_steps(f'解压版本')
        ssh_ip, _ = CommonOperation.get_nic_logical_ip()
        file_name_list = FileOperation.get_files(file_path=tar_path, ip=ssh_ip)[1]
        for file in file_name_list:
            if 'tar.gz' in file:
                if file[-6:] == 'tar.gz':
                    untar_file_path = tar_path.replace('tar', 'version')
                    FileOperation.uncompress_file(tar_file_path=os.path.join(tar_path, file),
                                                  untar_file_path=untar_file_path,
                                                  ip=ssh_ip)
                    break

    @classmethod
    def add_header(cls, test_region: str, core_file_num: int = 0):
        rtn_code = False
        add_header_dir = ADD_HEADER_DIR
        add_header_script_path = USER_ADD_HEADER
        if test_region == RegionEnum.UBOOT.value:
            header_txt = BOOTLOADER_TXT
            region_type = 'uboot'
            no_header_file_path = BOOTLOADER_BIN
        else:
            region_type = 'ioc'
            if CommonOperation.is_fpga():

                header_txt = constants.FW_TXT
                no_header_file_path = constants.FW_BIN
            else:
                fw_txt_list = [constants.FW_TXT0, constants.FW_TXT1, constants.FW_TXT2, constants.FW_TXT3,
                               constants.FW_TXT4, constants.FW_TXT5,]
                no_header_file_list = [constants.FW_BIN, constants.FW_BIN1, constants.FW_BIN, constants.FW_BIN2,
                                       constants.FW_BIN3, constants.FW_BIN4, constants.FW_BIN5, ]
                header_txt = fw_txt_list[core_file_num]
                no_header_file_path = no_header_file_list[core_file_num]

        exec_command_bin_file_add_header = (
            f"cd {add_header_dir};sh {add_header_script_path} "
            f"{header_txt}"
            f" {no_header_file_path} {region_type}")
        rtn_code_bin_file_add_header, rtn_outputs_bin_file_add_header, rtn_err_bin_file_add_header = \
            CommandOperation.execute_command_with_error(
                exec_command_bin_file_add_header, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        if rtn_code_bin_file_add_header == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{exec_command_bin_file_add_header}执行成功')
            rtn_code = True
        else:
            log.info(f'command:{exec_command_bin_file_add_header}执行失败')
        return rtn_code

    @classmethod
    def get_region_version_from_flash(cls, region_id: str, cmd_execute_address: str,
                                      cli_path: str = SCGBECLI64, px: str = 'p0'):
        version = ''
        if type(px) == str:
            px = int(px.replace('p', ''))

        exec_command = f"{cli_path} -d {list(BmcEnvInfo.info_dict.keys())[px]} custom {DRV_SCGBE_PF} regionVer id={region_id}'"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{exec_command}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
            result = re.search(r'VERSION:\s*(.+)', rtn_outputs)
            if result:
                version_with_dot = result.group(1)
                version_list = version_with_dot.split('.')
                for item in version_list:
                    version = version + '{:0>2x}'.format(int(item))
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        return version

    @classmethod
    def insmod_pl2303(cls, cmd_execute_address: str):
        exec_command = 'insmod /root/pl2303.ko'
        rtn_code, _, _ = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

    @classmethod
    def get_nic_list(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> list:
        nic_list = []
        exec_command = 'lshw -c network -businfo'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            all_nic_list = re.findall(r'pci\S+\s+(\w+)\s+network', rtn_outputs)
            for nic in all_nic_list:
                dict_temp = EthtoolOperation.show_driver_infomation(device_name=nic,
                                                                    cmd_execute_address=cmd_execute_address)
                if dict_temp['driver'] == DRV_SCGBE_PF:
                    nic_list.append(nic)
        return nic_list

    @classmethod
    def flash_set(cls, region: str, offset: str, length: str, value: str, cmd_execute_address: str, px=0) -> bool:
        result = False
        devid = ''
        if region == RegionEnum.UBOOT.value:
            devid = '0x0000'
        elif region == RegionEnum.FW.value:
            devid = '0x000a'
        elif region == RegionEnum.NVDATA.value:
            devid = '0x000c'
        elif region == RegionEnum.USER_DEFAULT.value:
            devid = '0x001c'
        elif region == RegionEnum.OPTION_ROM.value:
            devid = '0x0002'
        elif region == RegionEnum.FW_BAK.value:
            devid = '0x0000b'
        # exec_command = f"python3 /root/sagitta_serial_cli.py '/flash set str devid={devid} offset={offset}" \
        #     f" len={length} value={value}'"
        exec_command = (f"{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} custom {DRV_SCGBE_PF} flashwrstr "
                        f"devid={devid} offset={offset} len={length} value={value}")
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{exec_command}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
            result = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        return result

    @classmethod
    def get_link_speed_from_cli_show(cls, rtn_outputs: str, device_name: str):
        link_speed = ''
        line_list = rtn_outputs.splitlines()
        for line in line_list:
            if '|' in line:
                temp_list = line.split('|')
                if temp_list[3].strip() == device_name:
                    if line.count('|') == 9:
                        link_speed = temp_list[6].strip()
                    else:
                        link_speed = temp_list[5].strip()
        return link_speed


class CommonCli(ScriptBase, ABC):

    @classmethod
    def insmod(cls, step, key_word, path, cmd_execute_address):
        cmd_insmod = f'insmod {path}'
        CommandOperation.execute_command_with_error(cmd=cmd_insmod, cmd_execute_address=cmd_execute_address)

        cmd_lsmod = f'lsmod | grep {DRV_SCGBE_PF}'
        _, lsmod_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd_lsmod, cmd_execute_address=cmd_execute_address)
        if DRV_SCGBE_PF not in lsmod_output:
            CommonOperation.create_bug_problem(
                ScriptBase, key_word=key_word,
                description_word=f'步骤{step}：执行指令 {cmd_lsmod} 检查驱动加载结果',
                result_info='网卡加载失败')

    @classmethod
    def cli_rest_soc(cls, step, key_word, input_cmd, cmd_execute_address):
        cmd_execute = f"{input_cmd} -d {list(BmcEnvInfo.info_dict.keys())[0]} reset soc"
        rtn_code, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd_execute, cmd_execute_address=cmd_execute_address)
        return rtn_code
        # if rtn_code != RtnStatusEnum.SUCCESS.value:
        #     CommonOperation.create_bug_problem(
        #         ScriptBase, key_word=key_word,
        #         description_word=f'步骤{step}：执行指令 {cmd_execute} 重启固件',
        #         result_info='指令执行失败')
        # status_line = re.findall('Status.*', rtn_output)[0]
        # status = status_line.split('=')[-1].strip()
        # if status != 'Success':
        #     CommonOperation.create_bug_problem(
        #         ScriptBase, key_word=key_word, description_word=f'步骤{step}：执行指令 {cmd_execute} 重启固件',
        #         result_info=str(status), expect_info='Success')

    @classmethod
    def set_threshold(cls, step, key_word, input_cmd, hthreshold, cmd_execute_address):
        cmd_set_soctemp = f"{input_cmd} -d {list(BmcEnvInfo.info_dict.keys())[0]} set soctemp hthreshold={hthreshold}"
        set_soctemp_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd_set_soctemp, cmd_execute_address=cmd_execute_address)[1]
        log.info(f'指令{cmd_set_soctemp}执行结果：\n{set_soctemp_output}')
        if 'Status' not in set_soctemp_output:
            CommonOperation.create_bug_problem(
                ScriptBase, key_word=key_word, description_word=f'步骤{step}：执行指令 {cmd_set_soctemp} 设置芯片高温阈值',
                result_info='未返回执行结果')
        status_line = re.findall('Status.*', set_soctemp_output)[0]
        status = status_line.split('=')[-1].strip()
        if status != 'Success':
            CommonOperation.create_bug_problem(
                ScriptBase, key_word=key_word, description_word=f'步骤{step}：执行指令 {cmd_set_soctemp} 设置芯片高温阈值',
                result_info=status, expect_info='Success')

    @classmethod
    def get_soc_threshold(cls, px, exec_addr):
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd=f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} custom {DRV_SCGBE_PF} socTempThds', cmd_execute_address=exec_addr
        )
        # log.info(f'指令执行结果：\n{output}')
        re_threshold = re.findall(r'SOC\s*TEMP\s*THRESHOLD:\s*(\d+)', output)
        if re_threshold:
            threshold = int(re_threshold[0])
            return threshold
        else:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='CLI',
                description_word='获取芯片温度阈值失败'
            )

    @classmethod
    def set_soc_threshold(cls, px, threshold, exec_addr):
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd=f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} set soctemp hthreshold={threshold}', cmd_execute_address=exec_addr
        )
        # log.info(f'指令执行结果：\n{output}')
        if re.findall(r'Status\s*=\s*Success', output):
            log.info('设置温度阈值成功')
        else:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='CLI',
                description_word='设置芯片温度阈值失败'
            )

    @classmethod
    def cli_upgrade_success(cls, step, input_cmd, key_word, upgrade_path, cmd_execute_address):
        cmd = f'{input_cmd} -d {list(BmcEnvInfo.info_dict.keys())[0]} upgrade file={upgrade_path}'  #  noverchk
        rtn_code, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd, cmd_execute_address=cmd_execute_address)
        rtn_status = re.findall('Status.*', rtn_output)
        log.info(f'指令{cmd} 执行结果：\n{rtn_output}')
        if len(rtn_status) == 0 or "Success" not in rtn_status[0]:
            CommonOperation.create_bug_problem(
                ScriptBase, key_word=key_word, description_word=f'步骤{step}: 执行升级指令{cmd}',
                expect_info='输出结果包含Success', result_info=rtn_status[0])
        return True

    @classmethod
    def cli_upgrade_fail(cls, step, input_cmd, key_word, upgrade_path, erro_code, cmd_execute_address):
        cmd = f'{input_cmd} -d {list(BmcEnvInfo.info_dict.keys())[0]} upgrade file={upgrade_path}'  #  noverchk
        rtn_code, rtn_output, _ = CommandOperation.execute_command_with_error(cmd,
                                                                              cmd_execute_address=cmd_execute_address)
        rtn_status = re.findall('Status.*', rtn_output)
        rtn_description = re.findall('Description.*', rtn_output)
        log.info(f'指令{cmd} 执行结果：\n{rtn_output}')
        if len(rtn_status) == 0 or "Failure" not in rtn_status[0]:
            CommonOperation.create_bug_problem(
                ScriptBase, key_word=key_word, description_word=f'步骤{step}: 执行升级指令{cmd}',
                expect_info='输出结果包含Failure', result_info=rtn_status[0])
        if len(rtn_description) == 0 or erro_code not in rtn_description[0]:
            CommonOperation.create_bug_problem(
                ScriptBase, key_word=key_word, description_word=f'步骤{step}: 执行升级指令{cmd}',
                expect_info=f'输出结果包含{erro_code}', result_info=rtn_description[0])
        return True

    @classmethod
    def csv2bin_success(cls, step, key_word, exec_folder, cmd_execute_address):
        """
        author:      xiangyu.liu
        date:        2025.07.10
        description: 将修改过的csv文件生成bin
        :param step: 步骤
        :param key_word: 测试脚本描述
        :param exec_folder: py脚本执行路径
        :param cmd_execute_address: 略
        """
        cmd_rm = 'rm -rf *.bin'
        CommandOperation.execute_command_with_error(cmd=cmd_rm, cmd_execute_address=cmd_execute_address)

        cmd_cd = f'cd {exec_folder}'
        CommandOperation.execute_command_with_error(cmd=cmd_cd, cmd_execute_address=cmd_execute_address)

        cmd_csv2bin = ('python2 csv2bin.py -t sxe -c csv/asic/sxe.csv,csv/sxeUser.csv -i ps3_cfg_sxe.h'
                       ' -f ps3_cfg_sxe.c -b nvdata.bin,userDefault.bin -s csv/asic/sxeSbr.csv -r sbrData.bin')
        csv2bin_output = CommandOperation.execute_command_with_error(
            cmd=cmd_csv2bin, cmd_execute_address=cmd_execute_address)[1]
        log.info(f'指令{cmd_csv2bin}执行结果：\n{csv2bin_output}')

        cmd_ls = 'ls *.bin'
        ls_output = CommandOperation.execute_command_with_error(
            cmd=cmd_ls, cmd_execute_address=cmd_execute_address)[1]
        for file in ['nvdata.bin', 'userDefault.bin', 'sbrData.bin']:
            if file not in ls_output:
                CommonOperation.create_bug_problem(
                    ScriptBase, key_word=key_word,
                    description_word=f'步骤{step}： 在{exec_folder}路径下执行csv2bin.py脚本生成配置后的bin文件',
                    result_info='bin文件生成失败')

    @classmethod
    def csv2bin_failure(cls, step, key_word, exec_folder, expect_err_result, cmd_execute_address):
        """
        author:      xiangyu.liu
        date:        2025.07.10
        description: 使用包含非法参数的csv文件执行csv2bin.py，校验报错是否符合预期
        :param step: 步骤
        :param key_word: 测试脚本描述
        :param exec_folder: py脚本执行路径
        :param expect_err_result: 预期报错
        :param cmd_execute_address: 略
        """
        cmd_csv2bin = (f'cd {exec_folder};python2 csv2bin.py -t sxe -c csv/asic/sxe.csv,csv/sxeUser.csv -i '
                       f'ps3_cfg_sxe.h -f ps3_cfg_sxe.c -b nvdata.bin,userDefault.bin -s '
                       f'csv/asic/sxeSbr.csv -r sbrData.bin')
        csv2bin_output = CommandOperation.execute_command_with_error(
            cmd=cmd_csv2bin, cmd_execute_address=cmd_execute_address)[1]
        log.info(f'指令{cmd_csv2bin}执行结果：\n{csv2bin_output}')
        if expect_err_result not in csv2bin_output:
            CommonOperation.create_bug_problem(
                ScriptBase, key_word=key_word,
                description_word=f'步骤{step}：使用包含非法参数的csv文件执行csv2bin.py脚本',
                result_info=f'返回指令中未包含 {expect_err_result} 报错信息')

    @classmethod
    def add_head_success(cls, step, key_word, shell_path: str, txt_path: str, bin_path: str, cmd_execute_address):
        """
        author:      xiangyu.liu
        date:        2025.07.10
        description: 将修改过的csv文件生成bin
        :param step: 步骤
        :param key_word: 测试脚本描述
        :param shell_path: shell脚本路径
        :param txt_path: txt配置文件路径
        :param bin_path: 生成后的bin文件所在路径
        :param cmd_execute_address: 略
        :return: 返回生成的加头文件的路径
        """
        shell_folder = shell_path[:shell_path.rfind('user_add_header.sh')]
        output_path = shell_folder + 'output'
        cmd_rm = f'rm -rf {output_path}'
        CommandOperation.execute_command_with_error(cmd=cmd_rm, cmd_execute_address=cmd_execute_address)

        opt_dict = {
            'userDefault.bin': 'userDefault',
            'nvdata.bin': 'nvdata',
            'sxe_fw_asic.bin': 'ioc',
            'sxe_oprom_debug.bin': 'optionrom',
            'sxe_oprom_release.bin': 'optionrom',
            'bootloader_sxe_fw_asic.bin': 'uboot'
        }
        bin_name = bin_path.split('/')[-1]
        opt = opt_dict.get(bin_name)
        cmd_add_head = f'cd {shell_folder}; ./user_add_header.sh {txt_path} {bin_path} {opt}'
        add_head_output = CommandOperation.execute_command_with_error(cmd=cmd_add_head,
                                                                      cmd_execute_address=cmd_execute_address)[1]
        log.info(f'指令 {cmd_add_head} 输出结果：\n{add_head_output}')
        ls_output = CommandOperation.execute_command_with_error(cmd=f'ls {output_path}',
                                                                cmd_execute_address=cmd_execute_address)[1]
        log.info(f'指令 ls {output_path} 输出结果：\n{ls_output}')
        if bin_name not in ls_output:
            CommonOperation.create_bug_problem(
                ScriptBase, key_word=key_word, description_word=f'步骤{step}：执行{cmd_add_head}给bin文件加头',
                result_info='生成加头的bin文件失败')
        return output_path + '/' + ls_output.strip('\n')

    @classmethod
    def make_package_success(cls, step, key_word, make_package_path, file_path, cmd_execute_address):
        """
        author:      xiangyu.liu
        date:        2025.07.10
        description: 将修改过的csv文件生成bin(已弃用)
        :param step: 步骤
        :param key_word: 测试脚本描述
        :param make_package_path: 打包脚本路径
        :param file_path: 要打包的文件路径
        :param cmd_execute_address: 略
        """
        cmd_rm = f'cd; rm -f ps3_image_package.bin'
        CommandOperation.execute_command_with_error(cmd=cmd_rm, cmd_execute_address=cmd_execute_address)

        cmd_package = f'cd; python2 {make_package_path} {file_path}'
        _, package_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd_package, cmd_execute_address=cmd_execute_address)
        log.info(f'指令{cmd_package}执行结果：\n{package_output}')

        cmd_ls = f'cd; ls | grep ps3_image_package.bin'
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd_ls, cmd_execute_address=cmd_execute_address)
        log.info(f'指令{cmd_ls}执行结果：\n{rtn_output}')

        if 'ps3_image_package.bin' not in rtn_output:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word=key_word,
                description_word=f'步骤{step} 执行指令{cmd_package}生成升级文件',
                result_info='升级文件生成失败')
        return '/root/ps3_image_package.bin'

    @classmethod
    def csv2bin_and_upgrade(cls,
            step: int, key_word, input_cmd,
            csv2bin_exec_folder: str = '/root/sxetest/publish_version/sxe_fw_asic/cfgTools/',
            add_header_path: str =
            '/root/sxetest/publish_version/sxe_fw_asic/pkgTools/tools/package/sm23Sign/user_add_header.sh',
            txt_path: str = '/root/sxetest/publish_version/sxe_fw_asic/pkgTools/header_config_sxe_fw.txt',
            make_package_path: str =
            '/root/sxetest/publish_version/sxe_fw_asic/pkgTools/tools/package/ps3_make_package.py',
            bin_name='userDefault.bin',
            cmd_execute_address=''):
        """
        author:xiangyu.liu
        date:2025.07.10
        description: 执行从通过csv文件生成bin文件到
        :param step: 步骤的二级标题编号，int类型
        :param key_word: 测试脚本描述
        :param input_cmd: 输入的cli指令
        :param csv2bin_exec_folder: csv2bin所在文件夹路径
        :param add_header_path: 加头脚本路径
        :param txt_path: 加头配置txt文件路径
        :param make_package_path: 打包脚本路径
        :param bin_name: 要打包的bin文件名
        :param cmd_execute_address: 略
        """
        CommonOperation.concat_test_steps(f'2.{step}. 将修改过的 csv 生成 bin')
        cls.csv2bin_success(f'2.{step}', key_word, csv2bin_exec_folder, cmd_execute_address)
        step += 1

        CommonOperation.concat_test_steps(f'2.{step}. 加头')
        bin_path = csv2bin_exec_folder + bin_name
        headed_bin_path = CommonCli.add_head_success(
            f'2.{step}', key_word, add_header_path, txt_path, bin_path, cmd_execute_address)
        step += 1

        CommonOperation.concat_test_steps(f'2.{step}. 生成升级包')
        upgrade_path = CommonCli.make_package_success(
            f'2.{step}', key_word, make_package_path, headed_bin_path, cmd_execute_address)
        step += 1

        CommonOperation.concat_test_steps(f'2.{step}. 使用该升级包升级')
        CommonCli.cli_upgrade_success(
            f'2.{step}', input_cmd, key_word, upgrade_path, cmd_execute_address)
        step += 1

        return step

    @classmethod
    def serial_cli(cls, serial_cli_path, command, cmd_execute_address):
        """
        author:      xiangyu.liu
        date:        2025.07.10
        description: 将修改过的csv文件生成bin
        :param serial_cli_path: mini_com脚本路径
        :param command: 要执行的片内指令
        :param cmd_execute_address: 略
        """
        CliCommonUtils.insmod_pl2303(cmd_execute_address)
        cmd_serial_cli = f"python3 {serial_cli_path} '{command}'"
        serial_cli_output = CommandOperation.execute_command_with_error(
            cmd=cmd_serial_cli, cmd_execute_address=cmd_execute_address)[1]
        log.info(f'指令{cmd_serial_cli}执行结果：\n{serial_cli_output}')
        return serial_cli_output

    @classmethod
    def analyze_custom_sxe_soctempthds(cls, step, key_word, serial_cli_path, cmd_execute_address) -> int:
        """
        author:      xiangyu.liu
        date:        2025.07.10
        description: 使用片内指令/debug custom sxe cfgShow mgrModule获取mgrModule参数，解析并以字典格式返回
        :param step: 步骤
        :param key_word: 测试脚本描述
        :param serial_cli_path: mini_com脚本路径
        :param cmd_execute_address: 略
        :return: 返回记录mgrModule参数的字典，{'isInitOob': _, 'logPersistOn': _}
        """
        command = f'/debug custom {DRV_SCGBE_PF} socTempThds'
        soctempthds_output = cls.serial_cli(serial_cli_path, command, cmd_execute_address)
        if 'SOC TEMP THRESHOLD:' not in soctempthds_output:
            CommonOperation.create_bug_problem(
                ScriptBase, key_word=key_word, description_word=f'步骤{step}：获取高温阈值', result_info='获取失败')

        threshold_line = re.findall('SOC TEMP THRESHOLD: .*', soctempthds_output)[0]
        threshold = threshold_line.split(':')[-1].strip()
        return int(threshold)

    @classmethod
    def analyze_custom_reg(cls):
        pass

    @classmethod
    def analyze_custom_mgr_module(cls, step: str, key_word, serial_cli_path, cmd_execute_address):
        """
        author:      xiangyu.liu
        date:        2025.07.10
        description: 使用片内指令/debug custom scgbe cfgShow mgrModule获取mgrModule参数，解析并以字典格式返回
        :param step: 步骤
        :param key_word: 测试脚本描述
        :param serial_cli_path: mini_com脚本路径
        :param cmd_execute_address: 略
        :return: 返回记录mgrModule参数的字典，{'isInitOob': _, 'logPersistOn': _}
        """
        mrg_module_dict = {}
        mgr_module_output = cls.serial_cli(serial_cli_path, f'/debug custom {DRV_SCGBE_PF} cfgShow mgrModule', cmd_execute_address)
        if '0x29b189c' not in mgr_module_output or '0x29b18a0' not in mgr_module_output:
            CommonOperation.create_bug_problem(
                ScriptBase, key_word=key_word,
                description_word=f'步骤{step}：片内 /debug custom {DRV_SCGBE_PF} cfgShow mgrModule 获取mgrModule参数',
                result_info='获取参数失败')
        reg_0x29b189c_line = re.findall('0x29b189c.*', mgr_module_output)[0]
        reg_0x29b18a0_line = re.findall('0x29b18a0.*', mgr_module_output)[0]
        reg_0x29b189c = reg_0x29b189c_line.split(':')[-1].strip()
        reg_0x29b18a0 = reg_0x29b18a0_line.split(':')[-1].strip()
        byte_lst = [int(x) for x in reg_0x29b189c.split(' ')] + [int(x) for x in reg_0x29b18a0.split(' ')]
        mrg_module_dict['isInitOob'] = int(format(byte_lst[0], '08b')[-1])  # 格式化为8位二进制字符串后后取最低位
        mrg_module_dict['logPersistOn'] = int(byte_lst[4])
        return mrg_module_dict

    @classmethod
    def analyze_custom_startup(cls):
        pass

    @classmethod
    def analyze_custom_support_feature(cls, step, key_word, serial_cli_path, cmd_execute_address):
        """
        author:      xiangyu.liu
        date:        2025.07.10
        description: 使用片内指令/debug custom {DRV_SCGBE_PF} cfgShow supportFeature获取supportFeature参数，解析并以字典格式返回
        :param step: 步骤
        :param key_word: 测试脚本描述
        :param serial_cli_path: mini_com脚本路径
        :param cmd_execute_address: 略
        :return: 返回记录supportFeature参数的字典，{'supportSfp': _, 'enableSfp0': _, 'enableSfp1': _, 'isOcpdev: _}
        """
        support_feature_dict = {}
        support_feature_output = cls.serial_cli(
            serial_cli_path, f'/debug custom {DRV_SCGBE_PF} cfgShow supportFeature', cmd_execute_address)
        if '0x29b187c' not in support_feature_output:
            CommonOperation.create_bug_problem(
                ScriptBase, key_word=key_word,
                description_word=f'步骤{step}：片内 /debug custom {DRV_SCGBE_PF} cfgShow supportFeature 获取support_feature参数',
                result_info='获取参数失败')
        reg_0x29b187c_line = re.findall('0x29b187c.*', support_feature_output)[0]
        reg_0x29b187c = reg_0x29b187c_line.split(':')[-1].strip()
        byte_lst = [int(x) for x in reg_0x29b187c.split(' ')]
        support_feature_dict['supportSfp'] = byte_lst[0]
        support_feature_dict['enableSfp0'] = byte_lst[1]
        support_feature_dict['enableSfp1'] = byte_lst[2]
        support_feature_dict['isOcpdev'] = byte_lst[3]
        return support_feature_dict

    @classmethod
    def analyze_custom_upgrade(cls):
        pass

    @classmethod
    def analyze_custom_temp_sensor_type(cls):
        pass

    @classmethod
    def reboot_and_check(cls, caller_class: object, reset_soc_flag=RtnStatusEnum.SUCCESS.value) -> int:
        CommonOperation.concat_test_steps('reboot主机')
        server_ip, client_ip = CommonOperation.get_nic_logical_ip()
        if not caller_class.exec_address:
            caller_class.exec_address = CmdExecuteAdressEnum.SERVER.value
        if UNLINK_REBOOT_FLAG:
            retry_max = 10
            retry = retry_max
            while retry:
                # 第一次尝试reboot，reboot不成功则直接使用bmc重启
                if reset_soc_flag == RtnStatusEnum.SUCCESS.value and retry == retry_max:
                    reboot_result = HostOperation.host_reboot(ssh_ip=server_ip)
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
                        ssh_ip=server_ip,
                        bmc_ip=bmc_ip,
                        uname=uname,
                        passwd=passwd)
                if reboot_result == RtnStatusEnum.SUCCESS.value:
                    log.info('重启操作完成，环境管理ip可重新ping通')
                else:
                    log.info('重启操作完成，环境管理ip仍重新ping通')
                    retry -= 1
                    continue
                log.warning("{}===============>重启当前存在lspci看不到设备问题，暂时添加重试".format(retry))
                host_para = HostPara()
                exec_command = f"lspci | grep -E '{host_para.VENDOR_ID}|{VENDOR_ID_NAME}|Stars' | grep -v Virtual"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                    exec_command, cmd_execute_address=caller_class.exec_address)
                log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
                if rtn_code == RtnStatusEnum.SUCCESS.value and 'net' in rtn_outputs:
                    CommonOperation.rmmod_driver(caller_class.server_driver_name,
                                                 caller_class.exec_address, force=True)
                    CommonOperation.modprobe_driver(caller_class.server_driver_name, caller_class.exec_address)
                    exec_command = f'{SCGBECLI64} show'
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                        exec_command, cmd_execute_address=caller_class.exec_address)
                    log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
                    if rtn_code == RtnStatusEnum.SUCCESS.value and 'Success' in rtn_outputs:
                        log.info('重启后设备已正常')
                        break
                retry -= 1
                log.info('重启后设备不正常，retry...')
        else:
            if reset_soc_flag == RtnStatusEnum.SUCCESS.value:
                reboot_result = HostOperation.host_reboot(ssh_ip=server_ip)
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
                    ssh_ip=server_ip,
                    bmc_ip=bmc_ip,
                    uname=uname,
                    passwd=passwd)
            if reboot_result == RtnStatusEnum.SUCCESS.value:
                log.info('重启操作完成，环境管理ip可重新ping通')
            else:
                CommonOperation.create_bug_problem(caller_class, key_word='重启主机', description_word=f'重启失败')

        CliCommonUtils.insmod_pl2303(cmd_execute_address=caller_class.server_serial_cli_exec_address)

        CommonOperation.concat_test_steps('查看建链是否正常')
        CliCommonUtils.check_lspci(cmd_execute_address=caller_class.exec_address)

        CommonOperation.concat_test_steps(f'加载网卡pf驱动')
        CommonOperation.modprobe_driver(caller_class.server_driver_name, caller_class.exec_address)

        CommonOperation.concat_test_steps(f'验证网卡和对端网卡是否可以Ping通')
        CliCommonUtils.check_ping(dst_ip=caller_class.client_device_ip,
                                  src_ip=caller_class.server_device_ip,
                                  cmd_execute_address=caller_class.exec_address)
        return RtnStatusEnum.SUCCESS.value

    @classmethod
    def xml2bin(cls, xml_path, input_bin, output_bin, exec_addr):
        cmd_xml2bin = f'cd {XML_FOLDER}; {XML2BIN} -i {xml_path} -o {output_bin} -c {input_bin}'
        _, rtn_xml2bin, _ = CommandOperation.execute_command_with_error(
            cmd=cmd_xml2bin, cmd_execute_address=exec_addr)
        log.info(f'指令返回结果:\n{rtn_xml2bin}')
        if '配置文件校验失败' in rtn_xml2bin or 'xml file is invalid' in rtn_xml2bin:
            return False, None
        elif '生成配置文件成功' in rtn_xml2bin:
            cmd_find = f'find {XML_FOLDER} -name {output_bin}'
            _, rtn_find, _ = CommandOperation.execute_command_with_error(
                cmd=cmd_find, cmd_execute_address=exec_addr)
            if output_bin in rtn_find:
                return True, XML_FOLDER + output_bin
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='CLI',
                    description_word=f'打印生成配置文件成功，实际无配置文件生成')
        else:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='CLI',
                description_word=f'xml2bin文件执行失败，无信息打印')

    @classmethod
    def make_package(cls, exec_addr, *paths):
        cmd_rm = f'cd; rm -f ps3_image_package.bin'
        CommandOperation.execute_command_with_error(cmd=cmd_rm, cmd_execute_address=exec_addr)

        cmd_package = f'cd; python2 {PS3_MAKE_PACKAGE}'
        for path in paths:
            cmd_package = cmd_package + ' ' + path
        _, package_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd_package, cmd_execute_address=exec_addr)
        log.info(f'指令{cmd_package}执行结果：\n{package_output}')

        cmd_ls = f'cd; ls | grep ps3_image_package.bin'
        _, ls_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd_ls, cmd_execute_address=exec_addr)
        log.info(f'指令{cmd_ls}执行结果：\n{ls_output}')
        if 'ps3_image_package.bin' not in ls_output:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='CLI',
                description_word=f'通过bin文件打升级包失败')
        return '/root/ps3_image_package.bin'

    @classmethod
    def termlog_and_check_empty(cls, px, exec_addr, para_all=True):
        log_path = '/root/test_termlog'
        cmd_rm = f'rm -rf {log_path}'
        CommandOperation.execute_command_with_error(cmd=cmd_rm, cmd_execute_address=exec_addr)
        if para_all:
            cmd_termlog = f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} show termlog all file={log_path}'
        else:
            cmd_termlog = f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} show termlog file={log_path}'
        _, output_termlog, _ = CommandOperation.execute_command_with_error(cmd=cmd_termlog,
                                                                           cmd_execute_address=exec_addr)
        # log.info(f'指令执行结果：\n{output_termlog}')

        cmd_du = f'du -sh {log_path}'
        _, output_du, _ = CommandOperation.execute_command_with_error(cmd=cmd_du,
                                                                      cmd_execute_address=exec_addr)
        # log.info(f'指令执行结果：\n{output_du}')

        re_size = re.findall(r'\d+', output_du)
        if re_size:
            if re_size[0] == '0':
                return 0
            else:
                return 1
        else:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='CLI',
                description_word=f'show termlog 指令执行失败')

    @classmethod
    def upgrade_nor_flash_pkg(cls, px, exec_addr):
        pkg_path = CommonOperation.get_full_path(NOR_FLASH_PKG_PATH, exec_addr)
        cmd = f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} debug upgrade packet {pkg_path}'
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd,
            cmd_execute_address=exec_addr
        )
        log.info(f'指令返回结果：\n{output}')
        if re.findall(r'\s*Status\s*=\s*Success', output):
            return True
        elif re.findall(r'\s*Status\s*=\s*Failure', output):
            return False
        else:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='CLI',
                description_word='执行32M打包升级失败'
            )

    @classmethod
    def upgrade_pkg(cls, pkg_path, px=0, exec_addr=CmdExecuteAdressEnum.SERVER.value):
        cmd = f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} upgrade file={pkg_path}'  #  noverchk
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd,
            cmd_execute_address=exec_addr
        )
        # log.info(f'指令执行结果：\n{output}')
        if re.findall(r'Status\s+=\s+Success', output):
            return True
        elif re.findall(r'Status\s+=\s+Success', output):
            return False
        else:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='CLI',
                description_word='升级未返回结果'
            )

    @classmethod
    def set_log_level(cls, px=0, moudle=0, level=6, exec_addr=CmdExecuteAdressEnum.SERVER.value):
        cmd = f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} custom {DRV_SCGBE_PF} loginfoset moudle={moudle} level={level}'
        _, output, _ = CommandOperation.execute_command_multi_times(
            cmd=cmd,
            cmd_execute_address=exec_addr
        )
        # log.info(f'指令执行结果：\n{output}')
        if re.findall(rf'level:{level}', output):
            log.info('设置日志等级成功')
        else:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='CLI',
                description_word='设置日志等级失败'
            )

    @classmethod
    def show_termlog_in_file(cls, px=0, all_flag=True, check_code=True, exec_addr=RtnStatusEnum.SUCCESS.value,
                             path='/root/termlog'):
        file_path = path
        CommandOperation.execute_command_with_error(
            cmd=f'rm -rf {file_path}',
            cmd_execute_address=exec_addr
        )
        if all_flag:
            _, output, _ = CommandOperation.execute_command_with_error(
                cmd=f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} show termlog all file={file_path}',
                cmd_execute_address=exec_addr
            )
        else:
            _, output, _ = CommandOperation.execute_command_with_error(
                cmd=f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} show termlog file={file_path}',
                cmd_execute_address=exec_addr
            )
        # log.info(f'指令执行结果：\n{output}')
        if re.findall(r'Status\s+=\s+Success', output):
            _, output_check, _ = CommandOperation.execute_command_with_error(
                cmd=f'python3 {CHECK_ENCODE} {file_path}',
                cmd_execute_address=exec_addr)
            # log.info(f'指令执行结果：{output_check}')
            code = int(re.findall(r'(\d+)', output_check)[0])
            print(code)
            if code == 0:
                log.info('日志文件没有缺失和乱码')
            elif code & 0b01:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='CLI',
                    description_word='导出日志文件包含乱码')
            elif code & 0b10:
                if check_code:
                    CommonOperation.create_bug_problem(
                        ScriptBase,
                        key_word='CLI',
                        description_word='导出日志有缺失')
                else:
                    log.info('导出日志有缺失')
            else:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='CLI',
                    description_word='未输出日志校验结果，未知故障')
            _, output_size, _ = CommandOperation.execute_command_with_error(
                cmd=f'ls -l --block-size=k {file_path}',
                cmd_execute_address=exec_addr)
            re_size = re.findall(r'\s+(\d+)K', output_size)
            if not re_size:
                CommonOperation.create_bug_problem(
                    ScriptBase,
                    key_word='CLI',
                    description_word='指令返回成功但没有日志文件输出')
            size = int(re_size[0])
            return size
        else:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='CLI',
                description_word='导出日志失败'
            )

    @classmethod
    def set_mfginfo(cls, px=0, exec_addr=CmdExecuteAdressEnum.SERVER.value,
                    pn=None, sn=None, mfg_date=None, revision=None, rework_date=None, mac0=None, mac1=None):
        cmd = f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} set mfginfo '
        if pn:
            cmd += f'PN={pn} '
        if sn:
            cmd += f'SN={sn} '
        if mfg_date:
            cmd += f'mfgDate={mfg_date} '
        if revision:
            cmd += f'revision={revision} '
        if rework_date:
            cmd += f'reworkDate={rework_date} '
        if mac0:
            cmd += f'macAddr0={mac0} '
        if mac1:
            cmd += f'macAddr1={mac1} '
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd,
            cmd_execute_address=exec_addr
        )
        log.info(f'指令返回结果：\n{output}')
        if re.findall(r'Status\s+=\s+Success', output):
            log.info('设置生产信息成功')
        else:
            CommonOperation.create_bug_problem(
                ScriptBase,
                key_word='CLI',
                description_word='设置生产信息指令执行失败'
            )

    @classmethod
    def reset_soc(cls, px, exec_addr):
        code, output, _ = CommandOperation.execute_command_with_error(
            cmd=f'{SCGBECLI64} -d {list(BmcEnvInfo.info_dict.keys())[px]} reset soc',
            cmd_execute_address=exec_addr
        )
        # log.info(f'指令执行结果：\n{output}')
        return code

class InteractiveOperation(object):
    # 默认循环接收cmd结果的最大时间
    default_cmd_loop_timeout = DEFAULT_TIME_WAIT_FOR_CMD_LOOP_RET
    # 默认单条命令超时时间
    default_cmd_timeout = DEFAULT_TIME_WAIT_FOR_CMD_RET

    @classmethod
    def execute_command_with_invoke(cls, cmd: str, ssh_ip: str = None, ssh_port: int = 22,
                                    ssh_username: str = None, ssh_password: str = None,
                                    ssh_password_other: str = None, execute_in_host: bool = True,
                                    time_wait_cmd_ret: int = None, cmd_execute_timeout: int = None):
        """
        author: xiangyu.liu
        date: 2022.06.08
        description: 需要输入对端密码时，交互方式执行cmd(host与bmc之间交互)
                    单次cmd超时时间60s，单次cmd最大接收1024byte数据
        :param cmd_execute_timeout: 等待cmd单次执行结果的超时时间，默认300s
        :param time_wait_cmd_ret: cmd持续返回结果，循环接收返回值的最大时间，默认60s
        :param execute_in_host: True-在host执行命令；False-在bmc执行命令
        :param ssh_password_other: 对端密码
        :param ssh_password: 本端密码
        :param ssh_username: 本端用户名
        :param ssh_port: 本端端口号
        :param ssh_ip: 本端ip
        :param cmd: 命令字符串
        :return: status, result
        """
        cmd_ret = ""
        # 默认执行失败
        cmd_status = -1

        # 未指定用户名，则采用默认
        if not ssh_username:
            if execute_in_host:
                ssh_username = "root"
            else:
                ssh_username = CommonTools.bmc_ssh_username
        # 未指定密码，则采用默认
        if not ssh_password:
            if execute_in_host:
                ssh_password = "Tianjian;123"
            else:
                ssh_password = CommonTools.bmc_ssh_password
        # 对端password必须指定
        if not ssh_password_other:
            log.error("ssh_password_other=None !")
            return cmd_status, cmd_ret
        # 未指定最大时间，则采用默认
        if not time_wait_cmd_ret:
            time_wait_cmd_ret = cls.default_cmd_loop_timeout
        # 未指定超时时间，则采用默认
        if not cmd_execute_timeout:
            cmd_execute_timeout = cls.default_cmd_timeout
        # ssh连接的ip
        ip_addr = "{}".format(ssh_ip)

        # 建立一个socket
        trans = paramiko.Transport("{}:{}".format(ip_addr, ssh_port), 22)  # 如果使用 paramiko.SSHClient() cd后会回到连接的初始状态
        # 启动一个客户端
        trans.start_client()
        # 如果使用用户名和密码登录
        trans.auth_password(username=ssh_username, password=ssh_password)
        # 打开一个通道
        channel = trans.open_session()
        # 获取一个终端
        channel.get_pty()
        # 激活终端
        channel.invoke_shell()
        channel.settimeout(cmd_execute_timeout)
        # 发送要执行的命令
        log.info("ssh: {}; username: {}; password: {}; cmd: {}".format(ip_addr, ssh_username, ssh_password, cmd))
        channel.send(cmd + "\r")

        # 设置等待cmd返回结果的最大等待时间
        time_limit = datetime.datetime.now() + datetime.timedelta(seconds=time_wait_cmd_ret)
        # 一次接收不完，循环接收直至cmd执行完成或达到最大等待cmd返回时间
        ret_str_list = []
        rst = ""
        rst_last_loop = " "
        while datetime.datetime.now() < time_limit and rst != rst_last_loop:
            # 默认执行超时
            cmd_status = -2

            CommonTools.time_sleep(0.5)
            rst_str = channel.recv(1024)
            rst_str = rst_str.decode('utf-8')

            # 若返回交互
            if 'password' in rst_str:
                channel.send('{}\r'.format(ssh_password_other))
                continue

            rst_last_loop = rst
            rst += rst_str

            # 若cmd执行完成
            # ret_str_list = rst.split("\n")
            # if ret_str_list[-1].split("#")[-1] == " ":
            #     # 执行成功
            #     cmd_status = 0
            #     break
            # 若cmd执行完成
            if rst.endswith("$ ") or rst.endswith("# "):
                # 执行成功
                cmd_status = 0
                break

        # # 删除空行
        # while "\n\n" in rst:
        #     rst.replace("\n\n", "\n")
        # print(rst)

        # 去除cmd执行记录，保留cmd返回值
        ret_str_list = rst.split("\n")
        ret_by_line_temp = ret_str_list.copy()
        for line in ret_str_list:
            if not execute_in_host:
                if ' # ' in line or cmd == line.strip():
                    ret_by_line_temp.remove(line)
            else:
                if ']# ' in line or cmd == line.strip():
                    ret_by_line_temp.remove(line)
        # print(ret_by_line_temp)

        # 列表转换为字符串，用\n连接
        cmd_ret = "\n".join(ret_by_line_temp)
        # for i in ret_by_line_temp:
        #     cmd_ret += i
        #     cmd_ret += "\n"

        # # 回显很长的命令可能执行较久，通过循环分批次取回回显
        # while True:
        #     CommonTools.time_sleep(0.2)
        #     rst = channel.recv(1024)
        #     rst = rst.decode('utf-8')
        #     print(rst)
        #     # 通过命令执行提示符来判断命令是否执行完成
        #     if 'yes/no' in rst:
        #         channel.send('yes\r')
        #         CommonTools.time_sleep(0.5)
        #         cmd_ret = channel.recv(1024)
        #         cmd_ret = cmd_ret.decode('utf-8')
        #         print(cmd_ret)
        #         break
        #     elif 'password' in rst:
        #         channel.send('{}\r'.format(BmcFunc.bmc_password))
        #         CommonTools.time_sleep(0.5)
        #         ret = channel.recv(1024)
        #         ret = ret.decode('utf-8')
        #         print(ret)
        #         break

        channel.close()
        trans.close()

        return cmd_status, cmd_ret

    @classmethod
    def execute_update_command_with_invoke(cls, cmd: str, ssh_ip: str = None, ssh_port: int = 22,
                                           ssh_username: str = None, ssh_password: str = None,
                                           ssh_password_other: str = None, execute_in_host: bool = True,
                                           time_wait_cmd_ret: int = None, cmd_execute_timeout: int = None):
        """
        author: xiangyu.liu
        date: 2022.06.08
        description: 需要输入对端密码时，交互方式执行cmd(host与bmc之间交互)
                    单次cmd超时时间60s，单次cmd最大接收1024byte数据
        :param cmd_execute_timeout: 等待cmd单次执行结果的超时时间，默认300s
        :param time_wait_cmd_ret: cmd持续返回结果，循环接收返回值的最大时间，默认60s
        :param execute_in_host: True-在host执行命令；False-在bmc执行命令
        :param ssh_password_other: 对端密码
        :param ssh_password: 本端密码
        :param ssh_username: 本端用户名
        :param ssh_port: 本端端口号
        :param ssh_ip: 本端ip
        :param cmd: 命令字符串
        :return: status, result
        """
        cmd_ret = ""
        # 默认执行失败
        cmd_status = -1

        # 未指定用户名，则采用默认
        if not ssh_username:
            if execute_in_host:
                ssh_username = "root"
            else:
                ssh_username = CommonTools.bmc_ssh_username
        # 未指定密码，则采用默认
        if not ssh_password:
            if execute_in_host:
                ssh_password = "Tianjian;123"
            else:
                ssh_password = CommonTools.bmc_ssh_password
        # 对端password必须指定
        if not ssh_password_other:
            log.error("ssh_password_other=None !")
            return cmd_status, cmd_ret
        # 未指定最大时间，则采用默认
        if not time_wait_cmd_ret:
            time_wait_cmd_ret = cls.default_cmd_loop_timeout
        # 未指定超时时间，则采用默认
        if not cmd_execute_timeout:
            cmd_execute_timeout = cls.default_cmd_timeout
        # ssh连接的ip
        ip_addr = "{}".format(ssh_ip)

        # 建立一个socket
        trans = paramiko.Transport("{}:{}".format(ip_addr, ssh_port), 22)  # 如果使用 paramiko.SSHClient() cd后会回到连接的初始状态
        # 启动一个客户端
        trans.start_client()
        # 如果使用用户名和密码登录
        trans.auth_password(username=ssh_username, password=ssh_password)
        # 打开一个通道
        channel = trans.open_session()
        # 获取一个终端
        channel.get_pty()
        # 激活终端
        channel.invoke_shell()
        channel.settimeout(cmd_execute_timeout)
        # 发送要执行的命令
        log.info("ssh: {}; username: {}; password: {}; cmd: {}".format(ip_addr, ssh_username, ssh_password, cmd))
        channel.send(cmd + "\r")

        # 设置等待cmd返回结果的最大等待时间
        time_limit = datetime.datetime.now() + datetime.timedelta(seconds=time_wait_cmd_ret)
        # 一次接收不完，循环接收直至cmd执行完成或达到最大等待cmd返回时间
        ret_str_list = []
        rst = ""
        while datetime.datetime.now() < time_limit:
            # 默认执行超时
            cmd_status = -2

            CommonTools.time_sleep(0.5)
            rst_str = channel.recv(1024)
            rst_str = rst_str.decode('utf-8')

            # 若返回交互
            if 'password' in rst_str:
                channel.send('{}\r'.format(ssh_password_other))
                continue

            rst += rst_str

            if "libtest" in cmd:
                execute_end_mark = "press Enter to continue"
            else:
                execute_end_mark = "Description"
            # 若cmd执行完成
            ret_str_list = rst.split("\n")
            if ret_str_list[-1].split("#")[-1] == " " and execute_end_mark in rst:
                # 执行成功
                cmd_status = 0
                break

            CommonTools.time_sleep(1)
            if "libtest" not in cmd:
                channel.send("\n")
        # # 删除空行
        # while "\n\n" in rst:
        #     rst.replace("\n\n", "\n")
        # print(rst)

        print(ret_str_list)
        # 去除cmd执行记录，保留cmd返回值
        ret_by_line_temp = ret_str_list.copy()
        for line in ret_str_list:
            if not execute_in_host:
                if '/var/test # \r' in line:
                    ret_by_line_temp.remove(line)
            else:
                if ']# ' in line:
                    ret_by_line_temp.remove(line)
        print(ret_by_line_temp)

        # 列表转换为字符串，用\n连接
        for i in ret_by_line_temp:
            cmd_ret += i
            cmd_ret += "\n"

        # # 回显很长的命令可能执行较久，通过循环分批次取回回显
        # while True:
        #     CommonTools.time_sleep(0.2)
        #     rst = channel.recv(1024)
        #     rst = rst.decode('utf-8')
        #     print(rst)
        #     # 通过命令执行提示符来判断命令是否执行完成
        #     if 'yes/no' in rst:
        #         channel.send('yes\r')
        #         CommonTools.time_sleep(0.5)
        #         cmd_ret = channel.recv(1024)
        #         cmd_ret = cmd_ret.decode('utf-8')
        #         print(cmd_ret)
        #         break
        #     elif 'password' in rst:
        #         channel.send('{}\r'.format(BmcFunc.bmc_password))
        #         CommonTools.time_sleep(0.5)
        #         ret = channel.recv(1024)
        #         ret = ret.decode('utf-8')
        #         print(ret)
        #         break

        channel.close()
        trans.close()

        return cmd_status, cmd_ret



class HostPara:
    def __init__(self, exec_addr=CmdExecuteAdressEnum.SERVER.value):
        _, output_dmi, _ = CommandOperation.execute_command_with_error(
            cmd='dmidecode -t 1', cmd_execute_address=exec_addr, print_steps=False, print_enable=False)
        _, output_branch, _ = CommandOperation.execute_command_with_error(
            cmd=f"cat {RELEASE_VERSION} | grep branch ", cmd_execute_address=exec_addr,
            print_steps=False, print_enable=False
        )

        if re.findall(r"Product Name:\s+TL", output_dmi) and 'TL' in output_branch:
            self._VENDOR_NAME = 'TL'
            self._PRODUCT_NAME = 'TL1160-2X'
            self._PF_AUTHOR = 'TLsxe'
            self._PF_DESC = 'TLsxe driver'
            self._VF_AUTHOR = 'TLsxevf'
            self._VF_DESC = 'TLsxevf driver'
            self._VENDOR_ID = '206f'
        elif 'Stars' in output_branch:
            self._VENDOR_NAME = 'Stars'
            self._PRODUCT_NAME = '1160-2X'
            self._PF_AUTHOR = DRV_SCGBE_PF
            self._PF_DESC = f'{DRV_SCGBE_PF} driver'
            self._VF_AUTHOR = DRV_SCGBE_VF
            self._VF_DESC = f'{DRV_SCGBE_VF} driver'
            self._VENDOR_ID = '1eb6'
        else:
            self._VENDOR_NAME = 'Linkdata'
            self._PRODUCT_NAME = '1160-2X'
            self._PF_AUTHOR = DRV_SCGBE_PF
            self._PF_DESC = f'{DRV_SCGBE_PF} driver'
            self._VF_AUTHOR = DRV_SCGBE_VF
            self._VF_DESC = f'{DRV_SCGBE_VF} driver'
            self._VENDOR_ID = '1eb6'


    @property
    def VENDOR_NAME(self):
        return self._VENDOR_NAME

    @property
    def PRODUCT_NAME(self):
        return self._PRODUCT_NAME

    @property
    def PF_AUTHOR(self):
        return self._PF_AUTHOR

    @property
    def PF_DESC(self):
        return self._PF_DESC

    @property
    def VF_AUTHOR(self):
        return self._VF_AUTHOR

    @property
    def VF_DESC(self):
        return self._VF_DESC

    @property
    def VENDOR_ID(self):
        return self._VENDOR_ID
