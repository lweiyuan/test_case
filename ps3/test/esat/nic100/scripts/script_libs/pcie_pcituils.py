#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      weifeng.meng
date:        2025/3/11
description: pciutils命令的版本检测，命令封装
"""

import re
from packaging.version import parse
from scripts.script_libs import pcie_constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum, BondModeEnum, MacVlanModeEnum, OpcodeEnum

class SetpciOperation(object):
    @classmethod
    def check_setpci_version(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> bool:
        """
        author:      weifeng.meng
        date:        2025/3/11
        description: 检测：setpci版本是否大于等于某个版本号,返回：True or False
        :param cmd_execute_address:
        """
        # check_flag = False
        exec_command = f'{pcie_constants.SETPCI} --version'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command, cmd_execute_address=cmd_execute_address)
        re_pattern = r'setpci\s+version\s+([\d.]+)'
        match = re.search(re_pattern, rtn_outputs)
        current_version = parse(match.group(1))
        min_required_version = parse(pcie_constants.SETPCI_VERSION)
        check_flag = current_version >= min_required_version
        log.info("setpci 当前版本：{}，测试要求版本大于等于：{}，结果：{}".format(current_version, min_required_version, check_flag))
        return check_flag

    @classmethod
    def setpci_cmd(cls, bdf: str, reg: str, offset: str, value: str,
                   cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/11
        description: 调用：setpci进行读取或者写入4k寄存器值
        :param       bdf：设备bdf
        :param       reg：4k寄存器
        :param       offset：偏移量
        :param       value：r：表示读取；值表示写入的值
        """
        if value == 'r':
            # 读取操作
            exec_command = f'setpci -s {bdf} {reg}+{offset}'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            return rtn_outputs
        else:
            # 写入操作
            exec_command = f'setpci -s {bdf} {reg}+{offset}={value}'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            return rtn_outputs

class LspciOperation(object):
    @classmethod
    def check_lspci_version(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> bool:
        """
        author:      weifeng.meng
        date:        2025/3/11
        description: 检测：lspci版本是否大于等于某个版本号,返回：True or False
        :param cmd_execute_address:
        """
        # check_flag = False
        exec_command = f'{pcie_constants.LSPCI} --version'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        re_pattern = r'lspci\s+version\s+([\d.]+)'
        match = re.search(re_pattern, rtn_outputs)
        current_version = parse(match.group(1))
        min_required_version = parse(pcie_constants.LSPCI_VERSION)
        check_flag = current_version >= min_required_version
        log.info("lspci 当前版本：{}，测试要求版本大于等于：{}，结果：{}".format(current_version, min_required_version, check_flag))
        return check_flag

    @classmethod
    def lspci_cmd(cls, option: str, bdf: str,
                   cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/11
        description: 调用：lspci进行读取4k空间
        :param       option：lspci自带参数
        :param       bdf：设备bdf
        """
        exec_command = f"{pcie_constants.LSPCI} {option} {bdf}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        return rtn_outputs

if __name__ == "__main__":
    SetpciOperation.check_setpci_version(CmdExecuteAdressEnum.SERVER.value)
    SetpciOperation.setpci_cmd("4c:00.0","VENDOR_ID","0.w",'r',CmdExecuteAdressEnum.SERVER.value)
    #SetpciOperation.setpci_cmd("4c:00.0", "CAP_EXP", "8.w", '595f', CmdExecuteAdressEnum.SERVER.value)
    #SetpciOperation.setpci_cmd("4c:00.0","CAP_EXP", "8.w", 'r',CmdExecuteAdressEnum.SERVER.value)
    LspciOperation.check_lspci_version(CmdExecuteAdressEnum.SERVER.value)
    LspciOperation.lspci_cmd("-vvvs","4c:00.0", CmdExecuteAdressEnum.SERVER.value)


