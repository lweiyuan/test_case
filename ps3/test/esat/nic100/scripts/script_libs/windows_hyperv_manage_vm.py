#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      xiangyu.liu
date:        2023.11.17
description: 在windows hyper-v中对vm的管理
"""
import copy
import os
import pdb
import string
import ctypes
import ipaddress
import sys
from os import rename
import re
import uuid
import time

from typing import Union
import xml.etree.ElementTree as ET
from datetime import datetime

import add_syspath
import json
import random
import socket

from scripts.script_libs import constants, log
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.constants import VM_NAME_DEF, SXE_DEV_MARK_1
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum, ExitCodeEnum, TestObjectType

test_port = CommandLineArgsParse.get_test_port()
ssh_port = str(test_port)

class VmOp(object):
    @classmethod
    def get_vm(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        获取所有虚机的名称
        """
        exist_vm_list = []
        exist_vm_command = "get-vm |select-object Name|FL"
        # 查看当前环境中的所有的vm虚拟机
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exist_vm_command,
            cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_outputs = rtn_stdout.replace("\r", "")
            result = re.sub(r'\n\s*\n', '\n', rtn_outputs)
            lines = result.split('\n')
            lines = [index for index in lines if index != ""]
            for line in lines:
                line = re.sub(r"\s+", "", line)
                key, value = line.split(":", 1)
                exist_vm_list.append(value)
        return exist_vm_list

    @classmethod
    def check_vm_state(cls, vm_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      haibin.xu
        date:        2023-12-13 17:24:57
        description: 检查虚拟机状态

        :param vm_name:
        :param execute_address:
        :return:
        """
        rtn_state = None
        check_cmd = 'get-vm -name {} | Select-Object State | FL'.format(vm_name)
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_multi_times(
            cmd=check_cmd, cmd_execute_address=execute_address)
        if RtnStatusEnum.SUCCESS.value == rtn_code:
            match_list = re.findall(r'State\s*:\s*(Off|Running)', rtn_stdout)
            if match_list:
                rtn_state = match_list[0]

        return rtn_state

    @classmethod
    def get_runnig_vm(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2024.01.16
        description: 获取所有运行的虚机
        :param cmd_execute_address:
        :return:
        """
        vm_list = cls.get_vm(cmd_execute_address=cmd_execute_address)
        running_vm_list = [index for index in vm_list if cls.check_vm_state(index).title() == "Running"]
        return running_vm_list

    @classmethod
    def start_vm(cls, vm_name: str = VM_NAME_DEF, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                 virtual_system: str = "windows"):
        """
        author: xiangyu.liu
        date: 2023.11.04
        description: 启动vm
        """
        virtual_system = CommandLineArgsParse.get_host_os()
        cmd = "Start-VM -Name '{}'".format(vm_name)
        # 虚拟机Running状态下，等待初始化完成
        retry_max = 24
        retry_count = 0
        retry_interval_s = 5
        retry_flag = RtnStatusEnum.FAIL.value
        status, out, err = CommandOperation.execute_command_multi_times(
            cmd=cmd, cmd_execute_address=execute_address)
        log.info("status:{}, out:{}".format(status, out))
        if RtnStatusEnum.SUCCESS.value == status:
            time.sleep(2)
            if 'Running' != cls.check_vm_state(vm_name, execute_address):
                log.error('打开虚拟机命令执行成功，但是检查失败')
                status = RtnStatusEnum.FAIL.value
            cmd = f"get-vm -name {vm_name}|fl *|findstr /i \'MemoryDemand\'"
            while retry_count < retry_max:
                cmd_code, out, err = CommandOperation.execute_command_multi_times(
                    cmd=cmd, cmd_execute_address=execute_address)
                log.info("status:{}, result:{}".format(cmd_code, out))
                # 有值
                if out.split(":")[1].strip() != "0":
                    retry_flag = RtnStatusEnum.SUCCESS.value
                    break
                # 为0
                else:
                    retry_count += 1
                time.sleep(retry_interval_s)
            if retry_flag == RtnStatusEnum.SUCCESS.value:
                if retry_count > 0:
                    time.sleep(30)
                log.info(f"虚拟机{vm_name}初始化完成")
                retry_flag = RtnStatusEnum.SUCCESS.value
                # 清理隐藏设备
                if virtual_system == "windows":
                    cls.delete_hidden_vmbus(vm_name=vm_name, cmd_execute_address=execute_address)
                # if virtual_system == "windows":
                #     cls.clean_hidden_machine(vm_name=vm_name, cmd_execute_address=execute_address)
            else:
                log.error(f"在{retry_max * retry_interval_s}s内，虚拟机{vm_name}没有完成初始化")
                retry_flag = RtnStatusEnum.FAIL.value
        status = RtnStatusEnum.SUCCESS.value if retry_flag == status == RtnStatusEnum.SUCCESS.value \
            else RtnStatusEnum.FAIL.value
        return cmd, status, out, err

    def delete_hidden_vmbus(vm_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> int:
        """
        author:      xiangyu.liu
        date:        2023-11-30 11:38:57
        description: 删除隐藏的VMBUS设备

        :param vm_name: 虚拟机 name
        :return:     卸载成功返回0，失败返回-1
        """
        # 删除隐藏的VMBUS Network Adapter
        rtn_uninstall_code = RtnStatusEnum.FAIL.value
        findall_cmd = CommandOperation.concat_invoke_command(
            vm_name=vm_name, cmd="devcon findall *VMBUS*")
        cmd_code, findall_res, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=findall_cmd,
            cmd_execute_address=cmd_execute_address, timeout=180)
        log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            findall_cmd, cmd_code, findall_res, cmd_stderr))
        if RtnStatusEnum.SUCCESS.value != cmd_code:
            log.error('命令: {}，执行失败'.format(findall_cmd))
            return rtn_uninstall_code

        find_cmd = CommandOperation.concat_invoke_command(
            vm_name=vm_name, cmd="devcon find *VMBUS*")
        cmd_code, find_res, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=find_cmd,
            cmd_execute_address=cmd_execute_address, timeout=180)
        log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            find_cmd, cmd_code, find_res, cmd_stderr))
        if RtnStatusEnum.SUCCESS.value != cmd_code:
            log.error('命令: {}，执行失败'.format(find_cmd))
            return rtn_uninstall_code

        for vmbus_info in findall_res.split("\n"):
            # if vmbus_info not in find_res and "Hyper-V Virtual PCI Bus" in vmbus_info:
            if (vmbus_info not in find_res) and 'Network Adapter' in vmbus_info:
                dev_ins_id = vmbus_info.split(":", 1)[0]
                dev_ins_id = re.sub(r'(["])', r'\\\1', dev_ins_id)
                del_hidden_cmd = CommandOperation.concat_invoke_command(
                    vm_name=vm_name, cmd=f"devcon remove \\\"@{dev_ins_id}\\\"")
                cmd_code, find_res, cmd_stderr = CommandOperation.execute_command_multi_times(
                    cmd=del_hidden_cmd,
                    cmd_execute_address=cmd_execute_address, timeout=180, test_times=1)
                log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                    del_hidden_cmd, cmd_code, find_res, cmd_stderr))
                if RtnStatusEnum.SUCCESS.value != cmd_code:
                    log.error('命令: {}，执行失败'.format(del_hidden_cmd))
                    return rtn_uninstall_code

        # 删除隐藏的1ff2
        findall_cmd = CommandOperation.concat_invoke_command(
            vm_name=vm_name, cmd=f"devcon findall {SXE_DEV_MARK_1}")
        cmd_code, findall_res, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=findall_cmd,
            cmd_execute_address=cmd_execute_address, timeout=180)
        log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            findall_cmd, cmd_code, findall_res, cmd_stderr))
        if RtnStatusEnum.SUCCESS.value != cmd_code:
            log.error('命令: {}，执行失败'.format(findall_cmd))
            return rtn_uninstall_code

        find_cmd = CommandOperation.concat_invoke_command(
            vm_name=vm_name, cmd=f"devcon find {SXE_DEV_MARK_1}")
        cmd_code, find_res, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=find_cmd,
            cmd_execute_address=cmd_execute_address, timeout=180)
        log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            find_cmd, cmd_code, find_res, cmd_stderr))
        if RtnStatusEnum.SUCCESS.value != cmd_code:
            log.error('命令: {}，执行失败'.format(find_cmd))
            return rtn_uninstall_code

        for vmbus_info in findall_res.split("\n"):
            # if vmbus_info not in find_res and "Hyper-V Virtual PCI Bus" in vmbus_info:
            if (vmbus_info not in find_res) and ("matching device" not in vmbus_info):
                dev_ins_id = vmbus_info.split(":", 1)[0].strip()
                dev_ins_id = re.sub(r'(["])', r'\\\1', dev_ins_id)
                del_hidden_cmd = CommandOperation.concat_invoke_command(
                    vm_name=vm_name, cmd=f"devcon remove \\\"@{dev_ins_id}\\\"")
                cmd_code, find_res, cmd_stderr = CommandOperation.execute_command_multi_times(
                    cmd=del_hidden_cmd,
                    cmd_execute_address=cmd_execute_address, timeout=180, test_times=1)
                log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                    del_hidden_cmd, cmd_code, find_res, cmd_stderr))
                if RtnStatusEnum.SUCCESS.value != cmd_code:
                    log.error('命令: {}，执行失败'.format(del_hidden_cmd))
                    return rtn_uninstall_code

        # 重新扫描设备
        find_cmd = CommandOperation.concat_invoke_command(
            vm_name=vm_name, cmd="devcon rescan")
        cmd_code, find_res, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=find_cmd,
            cmd_execute_address=cmd_execute_address, timeout=180)
        log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            find_cmd, cmd_code, find_res, cmd_stderr))
        if RtnStatusEnum.SUCCESS.value != cmd_code:
            log.error('命令: {}，执行失败'.format(find_cmd))
            return rtn_uninstall_code

        rtn_uninstall_code = RtnStatusEnum.SUCCESS.value

        return rtn_uninstall_code

    @classmethod
    def clean_hidden_machine(cls, vm_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        清除虚机中所有的隐藏设备
        """
        log.info("清理所有的隐藏设备")
        exec_command = \
            "(Get-PnpDevice | Where-Object {$_.Status -eq 'Unknown'}).InstanceId|ForEach-Object { & 'devcon.exe' " \
            "remove '@$_' } "
        clean_hidden_cmd = CommandOperation.concat_invoke_command(
            vm_name=vm_name, cmd=exec_command)
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=clean_hidden_cmd, cmd_execute_address=cmd_execute_address)
        str_count = cmd_stdout.count("No devices were removed.")
        # 相同打印过多时，合并，并打印数量
        if str_count > 5:
            cmd_newout = cmd_stdout.replace("No devices were removed.", "")
            while "\n\n" in cmd_newout:
                cmd_newout = cmd_newout.replace("\n\n", "\n")
            while "\t\t" in cmd_newout:
                cmd_newout = cmd_newout.replace("\t\t", "\t")
            log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\n{} No devices were removed.\nCmd Stderr:\n{}'.format(
                clean_hidden_cmd, cmd_code, cmd_newout.strip(), str_count, cmd_stderr))
        else:
            log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                clean_hidden_cmd, cmd_code, cmd_stdout, cmd_stderr))

    @classmethod
    def stop_vm(cls, vm_name: str = VM_NAME_DEF, execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author:      haibin.xu
        date:        2023-11-25 16:52:12
        description: 关闭虚拟机

        :param vm_name: 虚拟机name
        :param execute_address: 命令执行地址信息
        :return:     None
        """
        stop_cmd = "Stop-VM -Name '{}' —Force".format(vm_name)
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=stop_cmd, cmd_execute_address=execute_address)
        # log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
        #     stop_cmd, cmd_code, cmd_stdout, cmd_stderr))
        if RtnStatusEnum.SUCCESS.value == cmd_code:
            time.sleep(5)
            if 'Off' != cls.check_vm_state(vm_name, execute_address):
                log.error('关闭虚拟机命令执行成功，但是检查失败')
                cmd_code = RtnStatusEnum.FAIL.value

        return stop_cmd, cmd_code, cmd_stdout, cmd_stderr

    @classmethod
    def create_directory(cls, vm_name, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                         virtual_system: str = "windows"):
        """
        author: wei.yuan1
        date: 2023.11.28
        description: 创建文件并进行拷贝
        """
        exist_path = "Test-Path 'D:'"
        code, stdout, stderr = CommandOperation.execute_command_with_error(
            cmd=exist_path, cmd_execute_address=execute_address)
        log.info("code:{}\nstdout:{}\nstderr:{}".format(code, stdout, stderr))
        if virtual_system == "windows":
            if int(code) == RtnStatusEnum.SUCCESS.value:
                dest_directory = f"D:\\Users\\Administrator\\{vm_name}\\"
            else:
                dest_directory = f"C:\\Users\\Administrator\\{vm_name}\\"
        else:
            if int(code) == RtnStatusEnum.SUCCESS.value:
                dest_directory = f"D:\\Users\\Administrator_centos\\{vm_name}\\"
            else:
                dest_directory = f"C:\\Users\\Administrator_centos\\{vm_name}\\"
        new_directory = f"New-Item -ItemType Directory -Path {dest_directory} -Force"
        CommonOperation.concat_test_steps(f"创建文件夹：{dest_directory}")
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=new_directory, cmd_execute_address=execute_address)
        log.info("cmd_code:{}\ncmd_stdout:{}\ncmd_stderr:{}".format(cmd_code, cmd_stdout, cmd_stderr))
        if virtual_system == "windows":
            source_diectory = "C:\\Users\\Administrator\\sxevm002-export\\sxevm002\\sxevm002\\*"
        else:
            source_diectory = "C:\\Users\\Administrator\\sxevm-centos\\*"
        copy_command = f"Copy-Item -Path {source_diectory} -Destination {dest_directory} -Recurse -Force"
        CommonOperation.concat_test_steps(f"拷贝系统镜像源命令为：{copy_command}")
        copy_cmd_code, copy_stdout, copy_stderr = CommandOperation.execute_command_with_error(
            cmd=copy_command, cmd_execute_address=execute_address)
        log.info("cmd_code:{}\ncmd_stdout:{}\ncmd_stderr:{}".format(cmd_code, cmd_stdout, cmd_stderr))
        if cmd_code == RtnStatusEnum.FAIL.value or copy_cmd_code == RtnStatusEnum.FAIL.value:
            log.error_caller("磁盘容量不足，程序退出")
            exit(ExitCodeEnum.EXIT_SKIP.value)
        if virtual_system == "windows":
            return f"{dest_directory}\\Virtual Hard Disks\\002.vhdx"
        else:
            return f"{dest_directory}\\Virtual Hard Disks\\sxe-centos.vhdx"

    @classmethod
    def clean_all_vm(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        :param cmd_execute_address: 执行端
        :return:
        """
        CommonOperation.concat_test_steps(step_info="清除所有的虛機環境")
        vm_list = cls.get_vm(cmd_execute_address=cmd_execute_address)
        active_vm_list = cls.get_runnig_vm(cmd_execute_address=cmd_execute_address)
        for vm_name in active_vm_list:
            cls.stop_vm(vm_name=vm_name, execute_address=cmd_execute_address)
        time.sleep(5)
        for vm_name in vm_list:
            log.info("删除网卡的挂载镜像")
            exec_command = f"Get-VM -Name {vm_name} | Get-VMHardDiskDrive | Remove-Item -Force"
            log.info_caller(f"执行命令：{exec_command}")
            cmd_code, exec_stdout, exec_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=cmd_execute_address)
            log.info_caller(f"删除网卡的信息的结果为：{exec_stdout}\n\n, 错误信息为{exec_stderr}\n")
            cls.delete_all_vmadapter(vm_name=vm_name, cmd_execute_address=cmd_execute_address)
            cls.remove_vm(vm_name=vm_name, cmd_execute_address=cmd_execute_address)

    @classmethod
    def remove_vm(cls, vm_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2024.01.16
        description: 删除虚机
        :param vm_name:
        :param cmd_execute_address:
        :return:
        """
        log.info(f"删除虚机{vm_name}")
        remove_command = f"Remove-VM -Name {vm_name} -Force"
        log.info_caller(f"执行命令：{remove_command}")
        cmd_code, exec_stdout, exec_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=remove_command, cmd_execute_address=cmd_execute_address)
        log.info_caller(f"删除网卡的信息的结果为：{exec_stdout}\n\n, 错误信息为{exec_stderr}\n")

    @classmethod
    def create_vm(cls, count: int, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                  virtual_system: str = "windows"):
        """
        author: wei.yuan1
        date: 2023.11.21
        description: 创建vm虚拟机器
        """
        # 查找vm机器名称是否被占用
        vm_prefix = "sxevm"
        exist_vm_list = []
        new_vm_list = []
        exist_vm_command = "get-vm |select-object Name|FL"
        # 查看当前环境中的所有的vm虚拟机
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exist_vm_command,
            cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}\nrtn_stdout:{}\nrtn_stderr:{}".format(rtn_code, rtn_stdout, rtn_stderr))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_outputs = rtn_stdout.replace("\r", "")
            result = re.sub(r'\n\s*\n', '\n', rtn_outputs)
            lines = result.split('\n')
            lines = [index for index in lines if index != ""]
            for line in lines:
                line = re.sub(r"\s+", "", line)
                key, value = line.split(":", 1)
                exist_vm_list.append(value)
        vm_list_num = [re.sub(r"\D", "", index) for index in exist_vm_list]
        try:
            max_num = max(vm_list_num, key=str)
        except Exception as e:
            max_num = 0
            log.info(f"当前环境中没有虚机,{e}")
        # 当前环境中添加虚拟机，并配置镜像文件
        start_num = int(max_num) + 100
        for index in range(start_num, count + start_num):
            vm_name = vm_prefix + str(index).zfill(3)
            # if vm_name in exist_vm_list:
            #     vm_name = vm_prefix + str(index).zfill(3)
            CommonOperation.concat_test_steps(f"创建vm节点{vm_name}")
            # cmd = f" New-VM -name {vm_name} -MemoryStartupBytes 2GB -ProcessorCount 2|Select-Object Name|FL"
            cmd = f" New-VM -name {vm_name} -MemoryStartupBytes 2GB |Select-Object Name|FL"
            rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                cmd=cmd,
                cmd_execute_address=cmd_execute_address)
            log.info("rtn_code:{}\nrtn_stdout:{}\nrtn_stderr:{}".format(rtn_code, rtn_stdout, rtn_stderr))
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                rtn_outputs = rtn_stdout.replace("\r", "")
                result = re.sub(r'\n\s*\n', '\n', rtn_outputs)
                lines = result.split('\n')
                for line in lines:
                    line = re.sub(r"\s+", "", line)
                    # haibin.xu 2023-11-27 12:01:17 modify: 空字符串跳过
                    if (not line) or (':' not in line):
                        continue
                    key, value = line.split(":", 1)
                    # 创建虚机后，删除所有的虚拟网络适配器
                    remove_netadapter = \
                        f" Get-VMNetworkAdapter -VMName '{value}'| Remove-VMNetworkAdapter -Confirm:$false"
                    rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                        cmd=remove_netadapter, cmd_execute_address=cmd_execute_address)
                    log.info("rtn_code:{}\nrtn_stdout:{}\nrtn_stderr:{}".format(rtn_code, rtn_stdout, rtn_stderr))
                    img_vhdx = cls.create_directory(vm_name=value, execute_address=cmd_execute_address,
                                                    virtual_system=virtual_system)
                    new_vm = f"Add-VMHardDiskDrive -VMName {value} -Path '{img_vhdx}'"
                    CommonOperation.concat_test_steps(f"对虚拟节点添加镜像,命令为：{new_vm}")
                    # new_vm = f"Add-VMDvdDrive -VMName {value} -Path '{constants.windows_iso_file}'"
                    rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                        cmd=new_vm, cmd_execute_address=cmd_execute_address)
                    log.info("rtn_code:{}\nrtn_stdout:{}\nrtn_stderr:{}".format(rtn_code, rtn_stdout, rtn_stderr))
                    if rtn_code == RtnStatusEnum.SUCCESS.value:
                        new_vm_list.append(value)
        return new_vm_list

    @classmethod
    def delete_all_vmadapter(cls, vm_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2024.01.12
        description: 删除虚机中所有的网络适配器
        :param vm_name:
        :param cmd_execute_address:
        :return:
        """
        log.info(f"获取虚机中的虚拟网络适配器的数量，如果不等于0，则删除{vm_name}中的网络适配器")
        get_netadapter_command = f"(Get-VMNetworkAdapter -VMName {vm_name}).count"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=get_netadapter_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_stdout = rtn_stdout.replace("\r", "")
            vm_adapter_num = int(re.sub(r"\s+", "", rtn_stdout)) if re.sub(r"\s+", "", rtn_stdout).isdigit() else 0
            if vm_adapter_num != 0:
                remove_netadapter = \
                    f" Get-VMNetworkAdapter -VMName '{vm_name}'| Remove-VMNetworkAdapter -Confirm:$false"
                CommandOperation.execute_command_with_error(
                    cmd=remove_netadapter, cmd_execute_address=cmd_execute_address)

    @classmethod
    def rename_vm(cls, old_name: str, new_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: xiangyu.liu
        date: 2023.11.21
        description: 重命名vm虚拟机器
        """
        log.info(f"重命名vm虚拟机：{old_name} -> {new_name}")
        cmd = f"Set-VM -Name \'{old_name}\' -NewVmName \'{new_name}\'"
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=cmd_execute_address)
        log.info("status:{}, out:{}, err:{}".format(status, out, err))
        if not status:
            return old_name
        else:
            return new_name

    @classmethod
    def get_vm_running_state(cls, vm_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                             vm_type: str = "hyper-v"):
        """
        author: xiangyu.liu
        date: 2023.11.21
        description: 重命名vm虚拟机器
        """
        log.info(f"获取vm虚拟机运行状态")
        if vm_type == "hyper-v":
            cmd = f"Get-VM -name \'{vm_name}\'|select -Property State|fl"
            status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=execute_address)
            log.info("status:{}, out:{}".format(status, out))
            if not status:
                running_state = out.strip().split(":")[1].strip()
            else:
                log.error("命令执行失败!")
                running_state = ""
        elif vm_type == "kvm":
            cmd = f"virsh domstate {vm_name}"
            status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=execute_address)
            log.info("status:{}, out:{}".format(status, out))
            if not status:
                running_state = out
            else:
                log.error("命令执行失败!")
                running_state = ""
        return running_state

    @classmethod
    def wait_vm_init_complete(cls, vm_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: xiangyu.liu
        date: 2023.11.21
        description: 等待虚拟机完成初始化
        """
        log.info(f"获取vm虚拟机初始化状态")
        cmd = f"Get-VM -name \'{vm_name}\'|select -Property State|fl"
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=execute_address)
        log.info("status:{}, out:{}".format(status, out))
        if RtnStatusEnum.SUCCESS.value == status:
            running_state = out.strip().split(":")[1].strip()
        else:
            log.error("命令执行失败!")
            running_state = ""
        if running_state != "Running":
            log.error(f"虚拟机{vm_name}未启动")
            return False

        # 虚拟机Running状态下，等待初始化完成
        retry_max = 24
        retry_count = 0
        retry_interval_s = 5
        retry_flag = False
        # vm_ip = CommonOperation.get_win_vm_ip(execute_address, vm_name)
        cmd = "get-vm -name sxevm001|fl *|findstr /i \'MemoryDemand\'"
        while retry_count < retry_max:
            status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=execute_address)
            log.info("status:{}, result:{}".format(status, out))
            # 有值
            if out.split(":")[1].strip() != "0":
                retry_flag = True
                break
            # 为0
            else:
                retry_count += 1
            time.sleep(retry_interval_s)
        if retry_flag:
            if retry_count > 0:
                time.sleep(30)
            log.info(f"虚拟机{vm_name}初始化完成")
            return True
        else:
            log.error(f"在{retry_max * retry_interval_s}s内，虚拟机{vm_name}没有完成初始化")
            return False

    @classmethod
    def wait_vm_stop_complete(cls, vm_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: xiangyu.liu
        date: 2023.11.21
        description: 等待虚拟机完成关机
        """
        log.info(f"获取vm虚拟机关机状态")
        cmd = f"Get-VM -name \'{vm_name}\'|select -Property State|fl"

        # 虚拟机Running状态下，等待初始化完成
        retry_max = 12
        retry_count = 0
        retry_interval_s = 5
        retry_flag = False
        while retry_count < retry_max:
            status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=execute_address)
            log.info("status:{}, out:{}".format(status, out))
            if RtnStatusEnum.SUCCESS.value == status:
                running_state = out.strip().split(":")[1].strip()
            else:
                log.error("命令执行失败!")
                running_state = ""
            if running_state == "Off":
                retry_flag = True
                break
            else:
                retry_count += 1
            time.sleep(retry_interval_s)
        if retry_flag:
            log.info(f"虚拟机{vm_name}已关闭完成")
            return True
        else:
            log.error(f"在{retry_max * retry_interval_s}s内，虚拟机{vm_name}没有完成关闭")
            return False

    @classmethod
    def copy_file_from_pf_to_vf(cls, vm_name: str, source_file_path: str, dest_file_path: str,
                                cmd_exec_address: str = CmdExecuteAdressEnum.CLIENT.value,
                                win_vm_ip: str = None) -> int:
        """
        author:      haibin.xu
        date:        2023-12-19 13:56:03
        description: 从物理机（测试机）侧拷贝文件到虚拟机侧

        :param vm_name:
        :param source_file_path:
        :param dest_file_path:
        :return:
        """
        if win_vm_ip:
            copy_cmd = f"scp -P {ssh_port} {source_file_path} Administrator@{win_vm_ip}:'{dest_file_path}'"
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
                cmd=copy_cmd, cmd_execute_address=cmd_exec_address, win_vm_ip=None)
            return cmd_code

        copy_cmd = ("Copy-Item -Path '{}' -Destination '{}' -ToSession (New-PSSession -VMName '{}' -Credential "
                    "$credential)").format(source_file_path, dest_file_path, vm_name)
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=copy_cmd, cmd_execute_address=cmd_exec_address)
        log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            copy_cmd, cmd_code, cmd_stdout, cmd_stderr))

        return cmd_code


class VmAdapter(object):

    @classmethod
    def get_adapter_name(cls, vm_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        获取虚机上所有的网络适配器
        :param vm_name:
        :param cmd_execute_address:
        :return:
        """
        vm_adapter_name = []
        exec_command = f"(Get-VMNetworkAdapter -VMName {vm_name}).Name"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address
        )
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            stdout_string = rtn_stdout.replace("\r", "")
            stdout_list = stdout_string.split("\n")
            vm_adapter_name = [index for index in stdout_list if index != ""]
        return vm_adapter_name

    @classmethod
    def get_vm_adapter_vlanId(cls, vm_name: str, adapter_name: str,
                              execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei,yuan1
        date: 2024年3月18日11:23:09
        description: 获取虚拟网卡的vlan id信息
        """
        exec_command = \
            f"Get-VMNetworkAdapterVlan -vmname {vm_name} -VMNetworkAdapterName {adapter_name}|Select-Object " \
            f"AccessVlanId|FL "
        log.info(f"执行命令：{execute_address}: 获取虚机为：{vm_name}的虚拟网卡{adapter_name}, 命令为{exec_command}")
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=execute_address
        )
        vlan_id_list = []
        rtn_stdout = rtn_stdout.replace("\r", "").split("\n")
        stdout_list = [index for index in rtn_stdout if re.sub(r"\s+", "", index) != ""]
        for line in stdout_list:
            vlan_id_list.append(re.sub(r"\s+", "", line.split(":")[1]))
        if len(vlan_id_list) > 1:
            raise EOFError(f"vlan id的长度超限:{str(len(vlan_id_list))}")
        else:
            return "".join(vlan_id_list)

    @classmethod
    def connect_vm_adapter(cls, vm_name: str,
                           adapter_name: str,
                           switch_name: str = constants.V_SWITCH_MANAGER_NAME_DEF,
                           execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2023.11.27
        description: 虚机的网络适配器连接虚拟交换机
        Args:
            vm_name: 虚机名称
            adapter_name: 网络虚拟适配器的名称
            switch_name: 虚拟交换机的名称
            execute_address: 执行端
        """
        log.info(f"{execute_address}: 创建虚机{vm_name}的管理网络适配器{adapter_name}并连接管理虚拟交换机{switch_name}")
        exec_command = \
            f"Add-VMNetworkAdapter -VMName {vm_name} -Name {adapter_name} -SwitchName {switch_name}"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=execute_address
        )
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            return rtn_code, rtn_stdout
        else:
            return rtn_code, rtn_stderr

    @classmethod
    def connect_vmnetworkadapter(cls, vm_name: str, v_adapter_name: str = None,
                                 vmswitch_name: str = None, manager_vmswitch_name: str = "sxeVmSwitch-manager1",
                                 execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: xiangyu.liu
        date: 2023.11.04
        description: vm网络适配器连接vmswitch
        """
        if not v_adapter_name:
            log.info(f"{execute_address}: {vm_name}网络适配器连接虚拟交换机{vmswitch_name}")
            cmd = \
                f"Get-VMNetworkAdapter -VMName {vm_name} " + \
                "| Where-Object {$_.SwitchName -ne '" + manager_vmswitch_name + "'} " + \
                f"| Connect-VMNetworkAdapter -SwitchName '{vmswitch_name}'"
            status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=execute_address)
            log.info("status:{}, out:{}".format(status, out))
        else:
            log.info(f"{execute_address}: {vm_name}网络适配器{v_adapter_name}连接虚拟交换机{vmswitch_name}")
            cmd = \
                f"Get-VMNetworkAdapter -VMName {vm_name} " + \
                "| Where-Object {$_.Name -eq '" + v_adapter_name + "'} " + \
                f"| Connect-VMNetworkAdapter -SwitchName '{vmswitch_name}'"
            status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=execute_address)
            log.info("status:{}, out:{}".format(status, out))
        return status, out

    @classmethod
    def disconnect_vmnetworkadapter(cls, vm_name: str,
                                    vmswitch_name: str = None, vadapter_name: str = None,
                                    manager_vmswitch_name: str = "sxeVmSwitch-manager1",
                                    execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: xiangyu.liu
        date: 2023.11.04
        description: vm网络适配器断连vmswitch
        """
        log.info(f"{execute_address}: {vm_name}网络适配器断连虚拟交换机")
        if vadapter_name and vmswitch_name:
            cmd = \
                f"Get-VMNetworkAdapter -VMName {vm_name} " + \
                "| Where-Object {$_.SwitchName -eq '" + vmswitch_name + "'} " + \
                f"| Disconnect-VMNetworkAdapter"
        else:
            cmd = \
                f"Get-VMNetworkAdapter -VMName {vm_name} " + \
                "| Where-Object {$_.SwitchName -ne '" + manager_vmswitch_name + "'} " + \
                f"| Disconnect-VMNetworkAdapter"
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=execute_address)
        log.info("status:{}, out:{}, err:{}".format(status, out, err))

    @classmethod
    def set_vmnetworkadapter_vlan(cls, vm_name: str, vlan_id: str,
                                  vmswitch_name: str = None, manager_vmswitch_name: str = "sxeVmSwitch-manager1",
                                  execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: xiangyu.liu
        date: 2023.11.04
        description: vm网络适配器连接vmswitch
        """
        log.info(f"{execute_address}: {vm_name}网络适配器(连接{vmswitch_name})设置Vlanid:{vlan_id}")
        cmd = f"Get-VMNetworkAdapter -VMName {vm_name} "
        if manager_vmswitch_name:
            cmd += "| Where-Object {$_.SwitchName -ne '" + manager_vmswitch_name + "'} "
        if vmswitch_name:
            cmd += "| Where-Object {$_.SwitchName -eq '" + vmswitch_name + "'} "
        cmd += f" |Set-VMNetworkAdapterVlan -Access -VlanId {vlan_id}"
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=execute_address)
        log.info("status:{}, out:{}, err:{}".format(status, out, err))

    @classmethod
    def get_vmnetworkadapter_vlan(cls, vm_name: str,
                                  vmswitch_name: str = None, manager_vmswitch_name: str = "sxeVmSwitch-manager1",
                                  execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> int:
        """
        author: xiangyu.liu
        date: 2023.11.04
        description: vm网络适配器连接vmswitch
        """
        log.info(f"{execute_address}: {vm_name}网络适配器(连接{vmswitch_name})获取Vlanid")
        cmd = f"Get-VMNetworkAdapter -VMName {vm_name} "
        if manager_vmswitch_name:
            cmd += "| Where-Object {$_.SwitchName -ne '" + manager_vmswitch_name + "'} "
        if vmswitch_name:
            cmd += "| Where-Object {$_.SwitchName -eq '" + vmswitch_name + "'} "
        cmd += f" |Get-VMNetworkAdapterVlan|Select-Object -Property AccessVlanId"
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=execute_address)
        log.info("status:{}, out:{}, err:{}".format(status, out, err))
        res = re.findall(r"\s+(\d+)", out)
        if res:
            return res[0]
        else:
            log.info("获取vlanid失败")
            return 0

    @classmethod
    def get_vmnetworkadapter_connection(cls, vm_name: str, vm_switch_name: str = "*sriov*",
                                        cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> bool:
        """
        author:      xiangyu.liu
        date:        2023-11-22 15:26:04
        description: vm网络适配器连接交换机状态查询
        :param vm_name: 虚拟机名称
        :param vm_switch_name: 虚拟交换机名称
        :param cmd_execute_address: 命令执行地址信息
        :return:     vm网络适配器SR-IOV查询成功返回(0, 状态值)，失败返回(-1, None)
        """
        log.info(f"{cmd_execute_address}: 查询{vm_name}中是否存在网络适配器连接交换机{vm_switch_name}")
        cmd = "Get-VMNetworkAdapter -VMName " + vm_name + "|?{$_.SwitchName -like \'" + vm_switch_name + \
              "\'}|select switchName"
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=cmd_execute_address)
        log.info("status:{}, out:{}, err:{}".format(status, out, err))
        if out:
            log.info(f"{vm_name}中存在网络适配器连接交换机{vm_switch_name}")
            return True
        else:
            log.info(f"{vm_name}中不存在网络适配器连接交换机{vm_switch_name}")
            return False

    @classmethod
    def get_vmnetworkadapter_sriov(
            cls, vm_name: str, vm_switch_name: str = None, vm_adapter_name: str = None,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author:      haibin.xu
        date:        2023-11-22 15:26:04
        description: vm网络适配器SR-IOV状态查询

        :param vm_name: 虚拟机名称
        :param vm_switch_name: 虚拟交换机名称
        :param vm_adapter_name: 虚拟机网络适配器名称
        :param cmd_execute_address: 命令执行地址信息
        :return:     vm网络适配器SR-IOV查询成功返回(0, 状态值)，失败返回(-1, None)
        """
        vm_adap_para = ' -Name {}'.format(vm_adapter_name) if vm_adapter_name is not None else ''
        vm_swit_para = " | Where-Object {{$_.SwitchName -eq '{}'}}".format(vm_switch_name) \
            if vm_switch_name is not None else ''
        get_sriov_cmd = f"(Get-VMNetworkAdapter -VMName {vm_name}{vm_adap_para}{vm_swit_para}).IovWeight"

        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
            cmd=get_sriov_cmd, cmd_execute_address=cmd_execute_address)
        log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            get_sriov_cmd, cmd_code, cmd_stdout, cmd_stderr))
        if RtnStatusEnum.SUCCESS.value == cmd_code:
            log.info('Command: {}，执行成功'.format(get_sriov_cmd))
        else:
            log.error('Command: {}，执行失败'.format(get_sriov_cmd))

        return get_sriov_cmd, cmd_code, cmd_stdout.strip(), cmd_stderr.strip()

    @classmethod
    def set_vmnetworkadapter_sriov(
            cls, vm_name: str, vm_switch_name: str = None, vm_adapter_name: str = None, iov_weight: int = 1,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> int:
        """
        author:      haibin.xu
        date:        2023-11-22 15:26:04
        description: vm网络适配器SR-IOV使能与关闭

        :param vm_name: 虚拟机名称
        :param vm_switch_name: 虚拟交换机名称
        :param vm_adapter_name: 虚拟机网络适配器名称
        :param iov_weight: 0为关闭sriov，[1-100]为启用SR-IOV，默认值为1
        :param cmd_execute_address: 命令执行地址信息
        :return:     vm网络适配器SR-IOV设置成功返回0，失败返回-1
        """
        set_code = RtnStatusEnum.FAIL.value

        if vm_adapter_name is None:
            set_sriov_cmd = "Set-VMNetworkAdapter -VMName {} -IovWeight {}".format(vm_name, iov_weight)
        else:
            set_sriov_cmd = "Set-VMNetworkAdapter -VMName {} -Name '{}' -IovWeight {}".format(
                vm_name, vm_adapter_name, iov_weight)
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
            cmd=set_sriov_cmd, cmd_execute_address=cmd_execute_address)
        log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            set_sriov_cmd, cmd_code, cmd_stdout, cmd_stderr))

        if RtnStatusEnum.SUCCESS.value == cmd_code:
            log.info('Command: {}，执行成功'.format(set_sriov_cmd))
            get_sriov_cmd, cmd_code, cmd_stdout, cmd_stderr = VmAdapter.get_vmnetworkadapter_sriov(
                vm_name=vm_name, vm_switch_name=vm_switch_name, vm_adapter_name=vm_adapter_name,
                cmd_execute_address=cmd_execute_address)
            out_list = [out.strip() for out in cmd_stdout.split()]
            if RtnStatusEnum.SUCCESS.value == cmd_code and all(str(iov_weight) == out for out in out_list):
                log.info('虚拟机网卡启用SRIOV命令，执行成功，且查询SRIOV值与设置值一致')
                set_code = RtnStatusEnum.SUCCESS.value
            else:
                log.error('虚拟机网卡启用SRIOV命令，执行成功，但是查询失败')
        else:
            log.error('Command: {}，执行失败'.format(set_sriov_cmd))

        return set_code

    @classmethod
    def check_vmnetworkadapter_exist(
            cls, vm_name: str, vm_adapter_name: str = None, vm_adapter_bind_switch_name: str = None,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> bool:
        """
        author:      haibin.xu
        date:        2023-11-28 13:42:56
        description: 在物理机侧检查虚拟机适配器是否存在

        :param vm_name: 虚拟机name
        :param vm_adapter_name: 检查的虚拟机网络适配器name
        :param vm_adapter_bind_switch_name: 检查的虚拟机网络适配器绑定的虚拟交换机name
        :param cmd_execute_address: 命令执行地址信息
        :return:     存在返回True，不存在返回False
        """
        rtn_exist_flag = True
        adapter_param = " -Name '{}'".format(vm_adapter_name) if vm_adapter_name is not None else ''
        check_adapter_cmd = "Get-VMNetworkAdapter -VMName {}{}".format(vm_name, adapter_param)
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
            cmd=check_adapter_cmd, cmd_execute_address=cmd_execute_address)
        log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            check_adapter_cmd, cmd_code, cmd_stdout, cmd_stderr))

        if (RtnStatusEnum.SUCCESS.value != cmd_code) or \
                ((RtnStatusEnum.SUCCESS.value == cmd_code) and (not cmd_stdout.strip())):
            log.info('虚拟机网络适配器：{}，不存在'.format(vm_adapter_name))
            rtn_exist_flag = False
        else:
            log.info('虚拟机网络适配器：{}，存在'.format(vm_adapter_name))
            if (vm_adapter_name is not None) and (vm_adapter_bind_switch_name is not None):
                if vm_adapter_bind_switch_name not in cmd_stdout:
                    log.info('虚拟机网络适配器：{}，存在，但是绑定的虚拟交换机：{}，不存在'.format(
                        vm_adapter_name, vm_adapter_bind_switch_name))
                    rtn_exist_flag = False

        return rtn_exist_flag

    @classmethod
    def add_vmnetworkadapter_with_connect_switch(
            cls, vm_name: str, add_adapter_count: int = 1, vm_adapter_name_header: str = 'Network-Adapter',
            vm_adapter_name_list: list = None, connect_switch_name_list: list = None,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author:      haibin.xu
        date:        2023-11-28 12:04:12
        description: 创建虚拟机网络适配器并绑定交换机

        :param vm_name: 虚拟机name
        :param add_adapter_count: 增加的虚拟机网络适配器个数
        :param vm_adapter_name_header: 虚拟机网络适配器name
        :param vm_adapter_name_list: 虚拟机网络适配器name 列表，优先使用该列表中的name命名虚拟机适配器
        :param connect_switch_name_list: 绑定的交换机
        :param cmd_execute_address: 命令执行地址信息
        :return:     None
        """
        rtn_add_code = RtnStatusEnum.SUCCESS.value
        rtn_vm_adapter_switch_dict = {}
        if vm_adapter_name_list is None:
            vm_adapter_name_list = []
        raw_add_adapter_cmd = 'Add-VMNetworkAdapter -VMName {} -Name'.format(vm_name)
        for i in range(add_adapter_count):
            if not connect_switch_name_list:
                switch_name = None
            elif i < len(connect_switch_name_list):
                switch_name = connect_switch_name_list[i]
            else:
                switch_name = connect_switch_name_list[-1]

            if i < len(vm_adapter_name_list):
                adapter_name = vm_adapter_name_list[i]
            else:
                adapter_name = '{}{}'.format(vm_adapter_name_header, i) + '-{}'.format(
                    ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(6)))

            switch_param = ' -SwitchName {}'.format(switch_name) if switch_name is not None else ''
            add_adapter_cmd = "{} '{}'{}".format(raw_add_adapter_cmd, adapter_name, switch_param)
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                cmd=add_adapter_cmd, cmd_execute_address=cmd_execute_address)
            log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                add_adapter_cmd, cmd_code, cmd_stdout, cmd_stderr))
            if cls.check_vmnetworkadapter_exist(
                    vm_name=vm_name, vm_adapter_name=adapter_name, vm_adapter_bind_switch_name=switch_name,
                    cmd_execute_address=cmd_execute_address):
                log.info('虚拟机：{}，添加网络适配器：{}，成功'.format(vm_name, adapter_name))
                rtn_vm_adapter_switch_dict.update({adapter_name: switch_name})
            else:
                log.error('虚拟机：{}，添加网络适配器：{}，失败'.format(vm_name, adapter_name))
                rtn_add_code = RtnStatusEnum.FAIL.value

        return rtn_add_code, rtn_vm_adapter_switch_dict

    @classmethod
    def uninstall_vm_adapter(cls, vm_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                             virtual_system: str = "windows") -> int:
        """
        author:      haibin.xu
        date:        2023-11-30 11:38:57
        description: 使用invoke命令在虚拟机侧卸载网卡设备

        :param vm_name: 虚拟机 name
        :param cmd_execute_address: 命令执行地址信息
        :param virtual_system:虚机的类型
        :return:     卸载成功返回0，失败返回-1
        """
        rtn_uninstall_code = RtnStatusEnum.FAIL.value
        if virtual_system == "windows":
            get_adapter_device_id_cmd = CommandOperation.concat_invoke_command(
                vm_name=vm_name, cmd="devcon find *VMBUS*")
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
                cmd=get_adapter_device_id_cmd, cmd_execute_address=cmd_execute_address)
            log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                get_adapter_device_id_cmd, cmd_code, cmd_stdout, cmd_stderr))
            if RtnStatusEnum.SUCCESS.value != cmd_code:
                log.error('命令: {}，执行失败'.format(get_adapter_device_id_cmd))
                return rtn_uninstall_code
            match_list = re.findall(r'(VMBUS\\\{.*})\\.*?Network Adapter.*', cmd_stdout)
            if not match_list:
                log.error('命令: {}，执行成功，但是输出中未发现网卡的deviceid'.format(get_adapter_device_id_cmd))
                return rtn_uninstall_code

            match_list = list(set(match_list))
            for adapt_devid in match_list:
                uninstall_adapt_cmd = CommandOperation.concat_invoke_command(
                    vm_name=vm_name, cmd="pnputil /remove-device /deviceid '{}'".format(adapt_devid))
                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
                    cmd=uninstall_adapt_cmd, cmd_execute_address=cmd_execute_address)
                log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                    uninstall_adapt_cmd, cmd_code, cmd_stdout, cmd_stderr))
                if RtnStatusEnum.SUCCESS.value != cmd_code:
                    log.error('命令: {}，执行失败'.format(uninstall_adapt_cmd))
                    return rtn_uninstall_code
            # VmOp.clean_hidden_machine(vm_name=vm_name, cmd_execute_address=cmd_execute_address)
        else:
            rtn_uninstall_code = RtnStatusEnum.SUCCESS.value

        return rtn_uninstall_code

    @classmethod
    def get_vm_ip_addr_property(
            cls, vm_name: str = None, property_list: list = None, invoke_flag: bool = False,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, win_vm_ip: str = None) -> dict:
        """
        author:      haibin.xu
        date:        2023-11-29 11:02:05
        description: 获取虚拟机网络适配器属性值

        :param vm_name: 虚拟机name
        :param property_list: 要获取的网络适配器属性列表
        :param invoke_flag: 是否使用invoke命令直接在虚拟机内部执行获取网络适配器属性信息
        :param cmd_execute_address: 命令执行地址信息
        :return: 以字典形式返回对应的网卡属性值
        """
        rtn_property_dict = {}

        if invoke_flag and vm_name is None:
            log.error('invoke flag is True, but vm_name not defined.')
            return rtn_property_dict

        if not property_list:
            parmeters = '| Select-Object -Property *'
        else:
            parmeters = '| Select-Object '
        for i, prop in enumerate(property_list):
            if 0 == i:
                parmeters += prop
            else:
                parmeters += ', {}'.format(prop)

        if not invoke_flag and vm_name:
            get_adap_cmd = '{} {} | {}'.format(
                constants.GET_NETIPADDRESS, parmeters, constants.FORMAT_LIST)
        else:
            get_adap_cmd = '{} {} | {}'.format(
                constants.GET_NETIPADDRESS, parmeters, constants.FORMAT_LIST)
            if vm_name:
                get_adap_cmd = CommandOperation.concat_invoke_command(vm_name=vm_name, cmd=get_adap_cmd)

        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=get_adap_cmd, cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)

        if RtnStatusEnum.SUCCESS.value == cmd_code:
            temp_adap_prop_dict = {}
            temp_adap_prop_list = []
            match_list = re.findall(r'(.*?)\s*:(.*)', cmd_stdout)
            for i, prop_info in enumerate(match_list):
                if prop_info[0].strip() not in temp_adap_prop_dict.keys():
                    temp_adap_prop_dict.update({prop_info[0].strip(): prop_info[1].strip()})
                else:
                    temp_adap_prop_list.append(temp_adap_prop_dict)
                    temp_adap_prop_dict = {prop_info[0].strip(): prop_info[1].strip()}
                if i == (len(match_list) - 1):
                    temp_adap_prop_list.append(temp_adap_prop_dict)

            for j, temp_adap_prop_dict in enumerate(temp_adap_prop_list):
                rtn_property_dict.update({f'fake_key_{j}': temp_adap_prop_dict})

        return rtn_property_dict

    @classmethod
    def get_vm_adapter_vlan_property(
            cls, vm_name: str, vm_adapter_name: str = None, invoke_flag: bool = False,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author:      haibin.xu
        date:        2023-12-23 16:51:58
        description: 获取虚拟机网络适配器vlan相关属性值

        :param vm_name: 虚拟机name
        :param vm_adapter_name: 虚拟机网络适配器name
        :param property_value_dict: 要获取的网络适配器属性-值字典，如果非key=value参数，value置None
        :param invoke_flag: 是否使用invoke命令直接在虚拟机内部执行获取网络适配器属性信息
        :param cmd_execute_address: 命令执行地址信息
        :return: 以字典形式返回对应的网卡属性值
        """
        param_str = ''
        get_adap_cmd_header = 'Get-VMNetworkAdapterVlan -VMName {}'.format(vm_name)
        if vm_adapter_name is not None:
            get_adap_cmd_header += ' -VMNetworkAdapterName {}'.format(vm_adapter_name)

        get_adap_cmd = get_adap_cmd_header + param_str + ' | FL'

        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=get_adap_cmd, cmd_execute_address=cmd_execute_address, timeout=90)
        log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            get_adap_cmd, cmd_code, cmd_stdout, cmd_stderr))

        return cmd_code, cmd_stdout, cmd_stderr, get_adap_cmd

    @classmethod
    def set_vm_adapter_vlan_property(
            cls, vm_name: str, vm_adapter_name: str = None, property_value_dict: dict = None,
            invoke_flag: bool = False,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author:      haibin.xu
        date:        2023-12-23 16:51:58
        description: 设置虚拟机网络适配器vlan属性值

        :param vm_name: 虚拟机name
        :param vm_adapter_name: 虚拟机网络适配器name
        :param property_value_dict: 要获取的网络适配器属性-值字典，如果非key=value参数，value置None
        :param invoke_flag: 是否使用invoke命令直接在虚拟机内部执行获取网络适配器属性信息
        :param cmd_execute_address: 命令执行地址信息
        :return: 以字典形式返回对应的网卡属性值
        """
        param_str = ''
        set_adap_cmd_header = 'Set-VMNetworkAdapterVlan -VMName {}'.format(vm_name)
        if vm_adapter_name is not None:
            set_adap_cmd_header += ' -VMNetworkAdapterName {}'.format(vm_adapter_name)
        for key, value in property_value_dict.items():
            if value is not None:
                param_str += ' -{} {}'.format(key, value)
            else:
                param_str += ' -{} '.format(key)
        set_adap_cmd = set_adap_cmd_header + param_str

        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=set_adap_cmd, cmd_execute_address=cmd_execute_address, timeout=90)
        log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            set_adap_cmd, cmd_code, cmd_stdout, cmd_stderr))

        return cmd_code, cmd_stdout, cmd_stderr, set_adap_cmd

    @classmethod
    def get_vm_adapter_property(
            cls, vm_name: str, vm_adapter_name: str = None, property_list: list = None, invoke_flag: bool = False,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, virtual_system: str = "windows",
            win_vm_ip: str = '') -> dict:
        """
        author:      haibin.xu
        date:        2023-11-29 11:02:05
        description: 获取虚拟机网络适配器属性值

        :param vm_name: 虚拟机name
        :param vm_adapter_name: 虚拟机网络适配器name
        :param property_list: 要获取的网络适配器属性列表
        :param invoke_flag: 是否使用invoke命令直接在虚拟机内部执行获取网络适配器属性信息
        :param virtual_system: 虚拟机系统
        :param cmd_execute_address: 命令执行地址信息
        :return: 以字典形式返回对应的网卡属性值
        {
        Name                       : hyper-v-1
        InterfaceDescription       : Microsoft Hyper-V Network Adapter #7
        InterfaceIndex             : 3
        MacAddress                 : 00-15-5D-84-E2-18
        MediaType                  : 802.3
        PhysicalMediaType          : Unspecified
        InterfaceOperationalStatus : Up
        AdminStatus                : Up
        LinkSpeed(Gbps)            : 10
        MediaConnectionState       : Connected
        ConnectorPresent           : True
        VlanID                     : 0
        DriverInformation          : Driver Date 2006-06-21 Version 10.0.20348.859 NDIS 6.70
        }
        """
        rtn_property_dict = {}

        if not property_list:
            parmeters = '| Select-Object -Property *'
        else:
            parmeters = '| Select-Object '
        for i, prop in enumerate(property_list):
            if 0 == i:
                parmeters += prop
            else:
                parmeters += ', {}'.format(prop)

        vm_adap_name_para = ' -Name {} '.format(vm_adapter_name) if vm_adapter_name is not None else ''

        if not invoke_flag and vm_name:
            get_adap_cmd = '{} -VMName {}{}{} | {}'.format(
                constants.GET_VMNETWORKADAPTER, vm_name, vm_adap_name_para, parmeters, constants.FORMAT_LIST)
        else:
            get_adap_cmd = '{}{}{} | {}'.format(
                constants.GET_NET_ADAPTER, vm_adap_name_para, parmeters, constants.FORMAT_LIST)
            if vm_name:
                get_adap_cmd = CommandOperation.concat_invoke_command(vm_name=vm_name, cmd=get_adap_cmd)
            # get_adap_cmd = CommandOperation.concat_powershell_command(cmd=get_adap_cmd)

        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=get_adap_cmd, cmd_execute_address=cmd_execute_address, timeout=90, win_vm_ip=win_vm_ip)
        log.info("cmd_code:{}\ncmd_stdout:{}\ncmd_stderr:{}".format(cmd_code, cmd_stdout, cmd_stderr))

        if RtnStatusEnum.SUCCESS.value == cmd_code:
            # log.info(f"cmd_stdout:{cmd_stdout}")
            temp_adap_prop_dict = {}
            temp_adap_prop_list = []
            match_list = re.findall(r'(.*?)\s*:(.*)', cmd_stdout)
            for i, prop_info in enumerate(match_list):
                if prop_info[0].strip() not in temp_adap_prop_dict.keys():
                    temp_adap_prop_dict.update({prop_info[0].strip(): prop_info[1].strip()})
                else:
                    temp_adap_prop_list.append(temp_adap_prop_dict)
                    temp_adap_prop_dict = {prop_info[0].strip(): prop_info[1].strip()}
                if i == (len(match_list) - 1):
                    temp_adap_prop_list.append(temp_adap_prop_dict)

            for j, temp_adap_prop_dict in enumerate(temp_adap_prop_list):
                if vm_adapter_name:
                    rtn_property_dict = temp_adap_prop_dict
                    break
                else:
                    rtn_property_dict.update({f'fake_key_{j}': temp_adap_prop_dict})

        return rtn_property_dict

    @classmethod
    def check_adapter_ipaddress(
            cls, vm_name: str = None, ifindex: str = None, check_ip: str = None, invoke_flag: bool = False,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, virtual_system: str = "windows",
            virtual_ip: str = None
    ) -> tuple:
        """
        author:      haibin.xu
        date:        2023-12-01 09:12:23
        description: 检查网络适配器的ip是否存在或与给定ip是否一致

        :param vm_name: 虚拟机name
        :param ifindex:  虚拟机适配器的interfaceIndex
        :param check_ip: 配置的ip，该值有效时，检查获取的适配器ip是否与该值一致，该值无效时，检查获取的ip是否有效
        :param invoke_flag: 是否使用invoke命令直接在虚拟机内部执行获取网络适配器属性信息
        :param virtual_system: 虚拟机系统
        :param virtual_ip: 虚机的IP地址
        :param cmd_execute_address: 命令执行地址信息
        :return:     返回网络适配器的ip是否存在或与给定ip是否一致，以及ip信息
        """
        rtn_ipaddr = None
        target_ip_list = []
        rtn_check_code = RtnStatusEnum.FAIL.value
        if virtual_system == "windows":
            ipaddr_info_dict = cls.get_vm_ip_addr_property(
                vm_name=vm_name, property_list=['IPAddress', 'InterfaceIndex'], invoke_flag=invoke_flag,
                cmd_execute_address=cmd_execute_address, win_vm_ip=virtual_ip)

            for _, ipaddr_info in ipaddr_info_dict.items():
                ipaddr = ipaddr_info.get('IPAddress')
                ifidx = ipaddr_info.get('InterfaceIndex')
                if ifidx == str(ifindex) and re.match(constants.PATTERN_IP, ipaddr.strip()):
                    target_ip_list.append(ipaddr.strip())

            log.info('VM: {}, Adapter InterfaceIndex: {}, IPAddress: {}'.format(vm_name, ifindex, target_ip_list))
            target_ip_list = [index for index in target_ip_list if not index.startswith("169.")]
            if check_ip is not None:
                if (1 == len(target_ip_list)) and (check_ip == target_ip_list[0]):
                    rtn_ipaddr = check_ip
                    rtn_check_code = RtnStatusEnum.SUCCESS.value
            else:
                if (1 == len(target_ip_list)):
                    rtn_ipaddr = target_ip_list[0]
                    rtn_check_code = RtnStatusEnum.SUCCESS.value
                elif 1 < len(target_ip_list):
                    rtn_ipaddr = target_ip_list
                    rtn_check_code = RtnStatusEnum.SUCCESS.value
        else:
            # 获取linux系统的网口名称
            nic_name_list = []
            get_nic_command = "ifconfig | grep -Eo '^[a-zA-Z0-9]*'"
            # get_nic_name = CommandOperation.concat_invoke_command(vm_name=vm_name, cmd=get_nic_command)
            rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                cmd=get_nic_command, cmd_execute_address=cmd_execute_address, ssh_ip=virtual_ip, script_object=True)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                rtn_stdout = rtn_stdout.replace("\r", "")
                nic_name_list = []
                for index in rtn_stdout.split("\n"):
                    if "lo" not in index:
                        nic_name_list.append(index)
                nic_name_list = [re.sub(r"\s+", "", index) for index in nic_name_list]
                nic_ip_addr_dict = {}
                nic_mac_addr_dict = {}
                for nic_name in nic_name_list:
                    # linux 系统下获取网卡的ip地址
                    get_ipaddr_command = f"ip addr show {nic_name} |grep 'inet '|cut -d ':' -f 2|awk '{{print $2}}'"
                    # get_ipaddr_command = CommandOperation.concat_invoke_command(
                    #     vm_name=vm_name, cmd=get_ipaddr_command)
                    rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                        cmd=get_ipaddr_command, cmd_execute_address=cmd_execute_address, ssh_ip=virtual_ip,
                        script_object=True)
                    if rtn_code == RtnStatusEnum.SUCCESS.value:
                        ip_addr = rtn_stdout.replace("\r", "")
                        ip_addr_list = [re.sub(r"\s+", "", index) for index in ip_addr.split("\n")]
                        nic_ip_addr_dict[nic_name] = ip_addr_list
                for nic_name in nic_name_list:
                    get_macaddr_command = f"ip addr show {nic_name} |grep 'ether'|awk '{{print $2}}'"
                    rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                        cmd=get_macaddr_command, cmd_execute_address=cmd_execute_address, ssh_ip=virtual_ip,
                        script_object=True
                    )
                    if rtn_code == RtnStatusEnum.SUCCESS.value:
                        mac_addr = rtn_stdout.replace("\r", "")
                        mac_addr_list = [re.sub(r"\s+", "", index) for index in mac_addr.split("\n")]
                        nic_mac_addr_dict[nic_name] = mac_addr_list
                ip_addr_double_list = list(nic_ip_addr_dict.values())
                ip_addr_list = [num for sublist in ip_addr_double_list for num in sublist]
                ip_addr_list = [num.split("/")[0] for num in ip_addr_list if num != ""]
                if check_ip is not None:
                    if (1 == len(ip_addr_list)) and (check_ip == ip_addr_list[0]):
                        rtn_ipaddr = check_ip
                        rtn_check_code = RtnStatusEnum.SUCCESS.value
                else:
                    if 1 == len(ip_addr_list):
                        rtn_ipaddr = ip_addr_list[0]
                        rtn_check_code = RtnStatusEnum.SUCCESS.value
                    elif 1 < len(ip_addr_list):
                        rtn_ipaddr = ip_addr_list[0]
                        rtn_check_code = RtnStatusEnum.SUCCESS.value
                    else:
                        rtn_check_code = RtnStatusEnum.FAIL.value
                        rtn_ipaddr = ""
            else:
                # 当无法获取到网卡的名称时，说明系统未1启动，或者系统不是linux系统
                rtn_check_code = RtnStatusEnum.FAIL.value
                rtn_ipaddr = None

        return rtn_check_code, rtn_ipaddr

    @classmethod
    def get_nic_addr_dict(cls, vm_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                          virtual_ip: str = None, sr_iov_flag: bool = False):
        """
        author: wei,yuan1
        date: 2024. 01.10
        description: 在linux 系统下得到网卡的信息
        :param vm_name:
        :param cmd_execute_address:
        :param virtual_ip: 虚机的IP
        :param sr_iov_flag: 判断是否为sriov模式
        :return:
        """
        nic_ip_addr_dict = {}
        nic_mac_addr_dict = {}
        get_nic_command = "ifconfig | grep -Eo '^[a-zA-Z0-9]*'"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=get_nic_command, ssh_ip=virtual_ip, ssh_port="22", script_object=True)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_stdout = rtn_stdout.replace("\r", "")
            nic_name_list = []
            for index in rtn_stdout.split("\n"):
                if "lo" not in index:
                    nic_name_list.append(index)

            nic_name_list = [re.sub(r"\s+", "", index) for index in nic_name_list]
            if sr_iov_flag:
                nic_name_list = [index for index in nic_name_list if "eth" not in index]
            nic_name_list.remove("virbr0")
            for nic_name in nic_name_list:
                # linux 系统下获取网卡的ip地址
                get_ipaddr_command = f"ip addr show {nic_name} |grep 'inet '|cut -d ':' -f 2|awk '{{print $2}}'"
                # get_ipaddr_command = CommandOperation.concat_invoke_command(
                #     vm_name=vm_name, cmd=get_ipaddr_command)
                rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                    cmd=get_ipaddr_command, cmd_execute_address=cmd_execute_address, ssh_ip=virtual_ip, ssh_port="22",
                    script_object=True
                )
                if rtn_code == RtnStatusEnum.SUCCESS.value:
                    ip_addr = rtn_stdout.replace("\r", "")
                    ip_addr_list = [re.sub(r"\s+", "", index) for index in ip_addr.split("\n")]
                    nic_ip_addr_dict[nic_name] = ip_addr_list
            for nic_name in nic_name_list:
                # 获取网卡的mac地址
                get_macaddr_command = f"ip addr show {nic_name} |grep 'ether'|awk '{{print $2}}'"
                # get_macaddr_command = CommandOperation.concat_invoke_command(
                #     vm_name=vm_name, cmd=get_macaddr_command)
                rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                    cmd=get_macaddr_command, cmd_execute_address=cmd_execute_address, ssh_ip=virtual_ip,
                    script_object=True
                )
                if rtn_code == RtnStatusEnum.SUCCESS.value:
                    mac_addr = rtn_stdout.replace("\r", "")
                    mac_addr_value = re.sub(r"\s+", "", mac_addr)
                    nic_mac_addr_dict[nic_name] = mac_addr_value.lower()
        return nic_ip_addr_dict, nic_mac_addr_dict

    @classmethod
    def get_virtual_adapter_name(cls, vm_name: str, vm_adapter_name: str,
                                 cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, virtual_ip: str = None,
                                 sr_iov_flag: bool = False
                                 ):
        """
        author: wei.yuan1
        date: 2024.01.16
        description：获取虚机内适配器的名称
        :param vm_name:
        :param vm_adapter_name:
        :param cmd_execute_address:
        :param virtual_ip: 虚机的管理IP地址
        :param sr_iov_flag:
        :return: 虚机内的网卡名称
        """
        virtual_nic_name = ''
        _, adapter_mac_dict = cls.get_nic_addr_dict(vm_name=vm_name, cmd_execute_address=cmd_execute_address,
                                                    virtual_ip=virtual_ip, sr_iov_flag=sr_iov_flag
                                                    )
        vm_adapter_mac_addr = cls.get_vm_adapter_macaddr(
            vm_name=vm_name, vm_adapter_name=vm_adapter_name, invoke_flag=False,
            cmd_execute_address=cmd_execute_address)
        vm_adapter_mac_addr = ":".join(vm_adapter_mac_addr[i:i + 2] for i in range(0, len(vm_adapter_mac_addr), 2)).lower()
        for vm_adapter, mac_addr in adapter_mac_dict.items():
            if mac_addr == vm_adapter_mac_addr:
                virtual_nic_name = vm_adapter
                break
        return virtual_nic_name

    @classmethod
    def ip_address_valid_verify(cls, vm_name: str, vm_adapter_name,
                                vm_adapter_ifdesc_kw: str = None,
                                cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                                virtual_system: str = "windows"):
        """
        author: wei.yuan1
        date: 2023.11.30
        description: 判断网卡的管理IP是否为有效的IP地址
        :return:
        """
        ipv4_address = []

        # vm_adapter_ifindex_value = None

        def is_prefix_dhcp(ip: str) -> bool:
            # 无网络状态下动态获取的IP， 不可使用
            prefix = "169.254"
            ip_obj = ipaddress.ip_interface(ip)
            ip_rtn_code = str(ip_obj.network.network_address).startswith(prefix)
            # 在联网状态下，动态获取的IP
            valid_ip = ipaddress.IPv4Address(ip)
            ip_network = ipaddress.IPv4Network("10.0.0.0/7")
            valid_ip_code = valid_ip in ip_network
            return not ip_rtn_code or valid_ip_code

        # 获取网卡的IP地址
        get_adap_cmd = \
            f" Get-VMNetworkAdapter -VMName {vm_name} | Where-Object {{$_.IPAddresses -like '*.*.*.*'}}" \
            " | Select-Object @{n='IPv4Address';e={$_.IPAddresses | Select-Object -First 1}}|FL"
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=get_adap_cmd, cmd_execute_address=cmd_execute_address)
        log.info(cmd_stdout)
        if cmd_code == RtnStatusEnum.SUCCESS.value:
            cmd_stdout = cmd_stdout.replace("\r", "")
            lines = cmd_stdout.split("\n")
            lines = [line for line in lines if line != ""]
            for line in lines:
                ip_address = re.sub(r"\s+", "", line).split(":")[1]
                if is_prefix_dhcp(ip_address) and "127.0.0.1" not in ip_address:
                    ipv4_address.append(ip_address)
        manager_ip = []
        for address in ipv4_address:
            if not address.startswith("192"):
                manager_ip.append(address)
        if len(manager_ip) > 1:
            log.error_caller(f"{vm_name}中存在多个管理IP地址， ip地址信息为{'  ip地址:  '.join(manager_ip)}")
            raise IOError(f"{vm_name}中存在多个管理IP地址")
            # exit(ExitCodeEnum.EXIT_FAIL.value)
            # return
        elif len(manager_ip) < 1:
            log.error_caller(f"{vm_name}中不存在管理IP地址")
            raise IOError(f"{vm_name}中不存在管理IP地址")
            # exit(ExitCodeEnum.EXIT_FAIL.value)
            # return
        else:
            log.info(str(manager_ip))
            return "".join(manager_ip)

    @classmethod
    def check_vm_adapter_exist(
            cls, vm_name: str, vm_adapter_name: str,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, virtual_system: str = "windows",
            virtual_ip: str = None
    ) \
            -> int:
        """
        author:      haibin.xu
        date:        2023-11-30 23:00:12
        description: 检查虚拟机网络适配器是否存在

        :param vm_name: 虚拟机
        :param vm_adapter_name: 网络适配器
        :param cmd_execute_address: 命令执行地址
        :return:    存在返回0，不存在返回-1
        """
        if virtual_system == "windows":
            vm_adapt_prop_dict = cls.get_vm_adapter_property(
                vm_name=vm_name, vm_adapter_name=vm_adapter_name, property_list=['Name'], invoke_flag=True,
                cmd_execute_address=cmd_execute_address, win_vm_ip=virtual_ip)

            return RtnStatusEnum.SUCCESS.value if vm_adapt_prop_dict.get('Name').strip() == vm_adapter_name else \
                RtnStatusEnum.FAIL.value
        else:
            rtn_code = RtnStatusEnum.FAIL.value
            get_nic_command = "ifconfig | grep -Eo '^[a-zA-Z0-9]*'"
            # get_nic_name = CommandOperation.concat_invoke_command(vm_name=vm_name, cmd=get_nic_command)
            rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                cmd=get_nic_command, ssh_ip=virtual_ip, script_object=True)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                rtn_stdout = rtn_stdout.replace("\r", "")
                nic_name_list = []
                for index in rtn_stdout.split("\n"):
                    if "lo" not in index:
                        nic_name_list.append(index)
                nic_name_list = [re.sub(r"\s+", "", index) for index in nic_name_list]
                rtn_code =\
                    RtnStatusEnum.SUCCESS.value if vm_adapter_name in nic_name_list else RtnStatusEnum.FAIL.value
            return rtn_code

    @classmethod
    def get_vm_adapter_macaddr(cls, vm_name: str, vm_adapter_name: str, invoke_flag: bool = True,
                               cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                               virtual_system: str = "windows", virtual_ip: str = None) -> str:
        """
        author:      haibin.xu
        date:        2023-11-30 23:00:12
        description: 获取虚拟机网络适配器mac地址
        :param virtual_system: 虚机的操作系统
        :param vm_name: 虚拟机
        :param vm_adapter_name: 网络适配器
        :param invoke_flag: 为True时，表示在虚拟机内部执行，则vm_adapter_name为虚拟机上显示的网卡名，
                            为False时，表示在物理机上执行，则vm_adapter_name为物理机上显示的网卡名
        :param virtual_ip:虚机的IP地址
        :param cmd_execute_address: 命令执行地址
        :return:    返回虚拟机内部网络适配器mac地址
        """
        rtn_vm_adp_mac_addr = None
        log.info('获取虚拟机：{}，网络适配器：{}，的mac addr'.format(vm_name, vm_adapter_name))

        if virtual_system != "windows" and not invoke_flag:
            get_macaddr_command = f"ip addr show {vm_adapter_name} |grep 'ether'|awk '{{print $2}}'"
            # get_macaddr_command = CommandOperation.concat_invoke_command(
            #     vm_name=vm_name, cmd=get_macaddr_command)
            rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                cmd=get_macaddr_command, ssh_ip=virtual_ip, script_object=True
            )
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                mac_addr = rtn_stdout.replace("\r", "")
                mac_addr_list = [re.sub(r"\s+", "", index) for index in mac_addr.split("\n")]
                if 0 < len(mac_addr_list) < 2:
                    rtn_vm_adp_mac_addr = "".join(mac_addr_list).replace(":", "").strip()
        else:
            vm_adapter_info = cls.get_vm_adapter_property(
                vm_name, vm_adapter_name, ['MacAddress'], invoke_flag, cmd_execute_address, win_vm_ip=virtual_ip)

            if vm_adapter_info.get('MacAddress') is not None:
                rtn_vm_adp_mac_addr = vm_adapter_info.get('MacAddress').replace('-', '').strip()
                if '000000000000' == rtn_vm_adp_mac_addr:
                    rtn_vm_adp_mac_addr = None
        return rtn_vm_adp_mac_addr

    @classmethod
    def rename_vm_adapter(cls, vm_name: str, new_vm_adapter_name: str, ifindex: str,
                          cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, win_vm_ip: str = None) -> int:
        """
        author:      haibin.xu
        date:        2023-11-30 21:00:13
        description: 重命名虚拟机网卡

        :param vm_name: 虚拟机name
        :param new_vm_adapter_name: 虚拟机new name
        :param ifindex:  虚拟机适配器的interfaceIndex
        :param cmd_execute_address: 命令执行地址
        :return:     重命名成功返回0，失败返回-1
        """
        rtn_rename_code = RtnStatusEnum.SUCCESS.value
        log.info('修改虚拟机：{}，内部适配器名称为：{}'.format(vm_name, new_vm_adapter_name))
        rename_vm_adapter_cmd = 'Rename-NetAdapter -Name (Get-NetAdapter -InterfaceIndex {}).Name -NewName {}'.format(
            ifindex, new_vm_adapter_name)
        if vm_name:
            rename_vm_adapter_cmd = CommandOperation.concat_invoke_command(vm_name=vm_name, cmd=rename_vm_adapter_cmd)
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=rename_vm_adapter_cmd, cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)
        # log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
        #     rename_vm_adapter_cmd, cmd_code, cmd_stdout, cmd_stderr))
        if RtnStatusEnum.SUCCESS.value == cmd_code:
            log.info('命令: {}，执行成功'.format(rename_vm_adapter_cmd))
            if RtnStatusEnum.SUCCESS.value == cls.check_vm_adapter_exist(
                    vm_name, new_vm_adapter_name, cmd_execute_address, virtual_ip=win_vm_ip):
                log.info('虚拟机：{}，内部适配器重命名为：{}，成功'.format(vm_name, new_vm_adapter_name))
            else:
                log.error('虚拟机：{}，内部适配器重命名为：{}，失败'.format(vm_name, new_vm_adapter_name))
                rtn_rename_code = RtnStatusEnum.FAIL.value
        else:
            log.error('命令: {}，执行失败'.format(rename_vm_adapter_cmd))
            rtn_rename_code = RtnStatusEnum.FAIL.value

        return rtn_rename_code

    @classmethod
    def check_adapter_gateway(
            cls, vm_name: str = None, ifindex: str = None, check_gateway: str = None, invoke_flag: bool = False,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, win_vm_ip: str = None) -> int:
        """
        author:      haibin.xu
        date:        2023-12-01 09:12:23
        description: 检查网络适配器的网关是否与给定网关一致

        :param vm_name: 虚拟机name
        :param ifindex:  虚拟机适配器的interfaceIndex
        :param check_gateway: 配置的网关
        :param invoke_flag: 是否使用invoke命令直接在虚拟机内部执行获取网络适配器属性信息
        :param cmd_execute_address: 命令执行地址信息
        :return:     返回网络适配器的网关是否与给定网关一致
        """
        rtn_check_code = RtnStatusEnum.FAIL.value

        check_gateway_cmd = ' Get-NetRoute -ifindex {} | Select-Object DestinationPrefix, NextHop | {}'.format(
            ifindex, constants.FORMAT_LIST)
        if invoke_flag:
            if vm_name:
                check_gateway_cmd = CommandOperation.concat_invoke_command(vm_name=vm_name, cmd=check_gateway_cmd)

        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=check_gateway_cmd, cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)

        if RtnStatusEnum.SUCCESS.value == cmd_code:
            match_list = re.findall(r'DestinationPrefix\s*:\s*(.*)\r*\nNextHop\s*:\s*(.*)', cmd_stdout)
            for gateway_info in match_list:
                dst_prefix, next_hop = gateway_info
                if ('0.0.0.0/0' == dst_prefix.strip()) and (next_hop.strip() == check_gateway):
                    rtn_check_code = RtnStatusEnum.SUCCESS.value
                    break

        return rtn_check_code

    @classmethod
    def update_vm_adapter_gateway(
            cls, vm_name: str, ifindex: str, new_gateway: str = None, invoke_flag: bool = False,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, win_vm_ip: str = None) -> int:
        """
        author:      haibin.xu
        date:        2023-12-01 00:23:42
        description: 更新虚拟机适配器ip地址

        :param vm_name: 虚拟机name
        :param new_gateway: 需要配置的网关
        :param ifindex:  虚拟机适配器的interfaceIndex
        :param invoke_flag: 是否使用invoke命令直接在虚拟机内部执行获取网络适配器属性信息
        :param cmd_execute_address: 命令执行地址信息
        :return:     配置成功返回True，失败返回False
        """
        rtn_update_code = RtnStatusEnum.FAIL.value

        # 若网关已存在，则不更新
        if RtnStatusEnum.SUCCESS.value == cls.check_adapter_gateway(
                vm_name=vm_name, ifindex=ifindex, check_gateway=new_gateway, invoke_flag=invoke_flag,
                cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip):
            log.info(f"网关 {new_gateway}已配置")
            return RtnStatusEnum.SUCCESS.value

        # 若网关不存在，则更新网关
        update_gateway_cmd = "New-NetRoute -ifIndex {} -DestinationPrefix 0.0.0.0/0 -NextHop {}".format(
            ifindex, new_gateway)

        if not new_gateway:
            log.info('没有给定配置的网关地址，不再配置网关')
            rtn_update_code = RtnStatusEnum.SUCCESS.value
            return rtn_update_code

        if invoke_flag:
            if vm_name:
                update_gateway_cmd = CommandOperation.concat_invoke_command(vm_name=vm_name, cmd=update_gateway_cmd)
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=update_gateway_cmd, cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)
        # log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
        #     update_gateway_cmd, cmd_code, cmd_stdout, cmd_stderr))
        if RtnStatusEnum.SUCCESS.value == cmd_code:
            log.info('命令: {}，执行成功'.format(update_gateway_cmd))
            if RtnStatusEnum.SUCCESS.value == cls.check_adapter_gateway(
                    vm_name=vm_name, ifindex=ifindex, check_gateway=new_gateway, invoke_flag=invoke_flag,
                    cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip):
                log.info('网关配置成功')
                rtn_update_code = RtnStatusEnum.SUCCESS.value
            else:
                log.error('命令: {}，执行成功，但是查询未找到配置的网关'.format(update_gateway_cmd))
        else:
            log.info('命令: {}，执行失败'.format(update_gateway_cmd))

        return rtn_update_code

    @staticmethod
    def create_random_macaddress() -> str:
        """
        author:      haibin.xu
        date:        2023-12-02 10:46:56
        description: 生成一个随机mac地址

        :return: 一个随机mac地址
        """
        # random_uuid = uuid.uuid4()
        # mac = random_uuid.hex[:12].upper()
        par_mac = '{}:{}:{}'.format(
            hex(random.randint(1, 255))[2:].rjust(2, '0'), hex(random.randint(1, 255))[2:].rjust(2, "0"),
            hex(random.randint(1, 255))[2:].rjust(2, "0"))
        mac = (constants.MAC_HEADER_SXE + par_mac).replace(':', '').upper()
        # mac_with_colon = ':'.join(mac[i:i + 2] for i in range(0, 12, 2))
        # mac_with_hyphen = '-'.join(mac[i:i + 2] for i in range(0, 12, 2))

        return mac

    @classmethod
    def update_vm_adapter_macaddress(
            cls, vm_name: str, vm_adapter_name: str, new_macaddress: str = None, uninclude_macaddr_list: list = None,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, win_vm_ip: str = "") -> tuple:
        """
        author:      haibin.xu
        date:        2023-12-02 10:33:25
        description: 更新虚拟机网卡驱动地址

        :param vm_name: 虚拟机name
        :param vm_adapter_name: pf侧看到的虚拟机网卡名称
        :param new_macaddress: 指定配置的网卡mac地址，如果未指定，则使用随机生成的值
        :param cmd_execute_address: 命令执行地址信息
        :return:
        """
        test_idx = 1
        test_times = 10
        invalid_mac_addr_list = []
        uninclude_macaddr_list = [] if uninclude_macaddr_list is None else uninclude_macaddr_list

        if new_macaddress is None:
            while True:
                new_macaddress = cls.create_random_macaddress()
                if (new_macaddress not in invalid_mac_addr_list) and (new_macaddress not in uninclude_macaddr_list):
                    break

        while test_idx < test_times:
            set_vm_adap_mac_cmd = "Set-VMNetworkAdapter -VMName {} -Name {} -StaticMacAddress '{}'".format(
                vm_name, vm_adapter_name, new_macaddress)

            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                cmd=set_vm_adap_mac_cmd, cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)
            log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                set_vm_adap_mac_cmd, cmd_code, cmd_stdout, cmd_stderr))
            if RtnStatusEnum.SUCCESS.value == cmd_code:
                log.info('命令: {}，执行成功'.format(set_vm_adap_mac_cmd))
                mac_addr = cls.get_vm_adapter_macaddr(
                    vm_name=vm_name, vm_adapter_name=vm_adapter_name, invoke_flag=False,
                    cmd_execute_address=cmd_execute_address)
                if mac_addr == new_macaddress:
                    log.info('网卡mac地址设置成功')
                    break
                else:
                    log.error('网卡mac地址设置命令执行成功，但是查询失败')
            else:
                log.error('命令: {}，执行失败'.format(set_vm_adap_mac_cmd))

            if test_idx < test_times:
                invalid_mac_addr_list.append(new_macaddress)
                while True:
                    new_macaddress = cls.create_random_macaddress()
                    if (new_macaddress not in invalid_mac_addr_list) and (
                            new_macaddress not in uninclude_macaddr_list):
                        break
                test_idx += 1

        return set_vm_adap_mac_cmd, cmd_code, cmd_stdout, cmd_stderr, new_macaddress

    @classmethod
    def delete_invalid_ip_address(cls, vm_name: str, ifindex: str, invoke_flag: bool = False,
                                  cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                                  virtual_system: str = "windows", win_vm_ip: str = None):
        """
        author: wei.yuan1
        date: 2024.03.01
        description: 删除无效的IP
        """
        rtn_add_code = RtnStatusEnum.SUCCESS.value
        delete_ip_address = f"Get-NetIPAddress -InterfaceIndex  {ifindex} -AddressFamily IPv4 | Where-Object {{ " \
                            f"$_.InterfaceAlias -ne 'Loopback Pseudo-Interface 1' }} | Remove-NetIPAddress " \
                            f"-Confirm:$false "
        if invoke_flag and virtual_system == "windows":
            if vm_name:
                delete_ip_address = CommandOperation.concat_invoke_command(vm_name=vm_name, cmd=delete_ip_address)
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=delete_ip_address, cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)
        # log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
        #     add_static_ip_cmd, cmd_code, cmd_stdout, cmd_stderr))
        if RtnStatusEnum.SUCCESS.value == cmd_code:
            log.info('命令: {}，执行成功'.format(delete_ip_address))

    @classmethod
    def update_vm_adapter_ip_address(
            cls, vm_name: str, new_ip: str, ifindex: str, prefix_length: Union[str, int], invoke_flag: bool = False,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, virtual_system: str = "windows",
            win_vm_ip: str = None) -> int:
        """
        author:      haibin.xu
        date:        2023-12-01 00:23:42
        description: 更新虚拟机适配器ip地址

        :param vm_name: 虚拟机name
        :param new_ip:  给虚拟机配置的ip
        :param ifindex:  虚拟机适配器的interfaceIndex
        :param virtual_system:虚拟机系统
        :param prefix_length: 给虚拟机配置的掩码信息
        :param invoke_flag: 是否使用invoke命令直接在虚拟机内部执行获取网络适配器属性信息
        :param cmd_execute_address: 命令执行地址信息
        :return:     配置成功返回True，失败返回False
        """
        rtn_add_code = RtnStatusEnum.SUCCESS.value

        # 若ip已存在，则不更新
        check_code, _ = cls.check_adapter_ipaddress(
            vm_name=vm_name, ifindex=ifindex, check_ip=new_ip, invoke_flag=invoke_flag,
            cmd_execute_address=cmd_execute_address, virtual_system=virtual_system, virtual_ip=win_vm_ip)
        if RtnStatusEnum.SUCCESS.value == check_code:
            log.info(f"ip {new_ip}已配置")
            return rtn_add_code
        # 若ip不存在，则更新ip
        cls.delete_invalid_ip_address(vm_name=vm_name, invoke_flag=invoke_flag, ifindex=ifindex,
                                      cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)
        add_static_ip_cmd = 'New-NetIPAddress -InterfaceIndex {} -IPAddress {} -PrefixLength {}'.format(
            ifindex, new_ip, prefix_length)
        if invoke_flag and virtual_system == "windows":
            if vm_name:
                add_static_ip_cmd = CommandOperation.concat_invoke_command(vm_name=vm_name, cmd=add_static_ip_cmd)
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=add_static_ip_cmd, cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)
        # log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
        #     add_static_ip_cmd, cmd_code, cmd_stdout, cmd_stderr))
        if RtnStatusEnum.SUCCESS.value == cmd_code:
            log.info('命令: {}，执行成功'.format(add_static_ip_cmd))
            check_code, _ = cls.check_adapter_ipaddress(
                vm_name=vm_name, ifindex=ifindex, check_ip=new_ip, invoke_flag=invoke_flag,
                cmd_execute_address=cmd_execute_address, virtual_ip=win_vm_ip)
            if RtnStatusEnum.SUCCESS.value != check_code:
                log.error('ip配置命令: {}，执行成功，但是检查环境，未发现配置的ip'.format(add_static_ip_cmd))
                rtn_add_code = RtnStatusEnum.FAIL.value
            else:
                log.info('Ip更新成功')
        else:
            log.error('命令: {}，执行失败，ip配置失败'.format(add_static_ip_cmd))
            rtn_add_code = RtnStatusEnum.FAIL.value

        return rtn_add_code

    @classmethod
    def nmcli_create_nic_name(cls, device_name: str, ip_address: str,
                              virtual_ip: str = None):
        """
        author: wei.yuan1
        date: 2022.11.22
        description: 在/etc目录下创建网卡信息，并重启NetworkManager服务
        """
        exec_command = f"nmcli con add ifname {device_name} type ethernet " \
                       f"con-name {device_name} ipv4.address {ip_address} ipv4.method manual"
        rtn_code, _, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, ssh_ip=virtual_ip, script_object=True)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info('NetworkManager添加{}配置文件成功'.format(device_name))
            return True
        else:
            log.info('NetworkManager添加{}配置文件失败'.format(device_name))
            return False

    @classmethod
    def get_vm_adapter_ifidx_with_macaddr(
            cls, vm_name: str, vm_adapter_macaddr: str, invoke_flag: bool = False,
            uninclude_info: (str, list) = None, include_info: (str, list) = None,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, win_vm_ip: str = '') -> Union[str, list]:
        """
        author:      haibin.xu
        date:        2023-12-01 09:51:10
        description: 根据mac地址，确定虚拟机适配器InterfaceIndex

        :param vm_name: 虚拟机name
        :param vm_adapter_macaddr: 虚拟机适配器mac addr
        :param not_include_info: 是否使用invoke命令直接在虚拟机内部执行获取网络适配器属性信息
        :param include_info: 其他用于帮助确定适配器InterfaceIndex的信息
        :param cmd_execute_address: 命令执行地址信息
        :return:     返回虚拟机适配器InterfaceIndex
        """
        rtn_vm_adap_ifidx = None

        temp_list = []
        uninclude_info_list = []
        include_info_list = []

        vm_adapter_info = cls.get_vm_adapter_property(
            vm_name=vm_name, property_list=['MacAddress', 'IfIndex', 'InterfaceDescription'],
            invoke_flag=invoke_flag, cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)
        if isinstance(uninclude_info, str):
            uninclude_info_list.append(uninclude_info)
        elif isinstance(uninclude_info, list):
            uninclude_info_list += uninclude_info

        if isinstance(include_info, str):
            include_info_list.append(include_info)
        elif isinstance(include_info, list):
            include_info_list += include_info

        for _, vm_adap_prop in vm_adapter_info.items():
            match_flag = False
            mac_addr = vm_adap_prop.get('MacAddress')
            ifidx = vm_adap_prop.get('ifIndex')
            ifdesc = vm_adap_prop.get('InterfaceDescription')
            if mac_addr.strip().replace('-', '') == vm_adapter_macaddr:
                if not ((not uninclude_info_list) or (uninclude_info_list and all(
                        uninclu_info not in ifdesc for uninclu_info in uninclude_info_list))):
                    continue
                if (not include_info_list) or \
                        (include_info_list and
                         any(inclu_info in ifdesc for inclu_info in include_info_list)):
                    temp_list.append(ifidx.strip())

        if 1 == len(temp_list):
            rtn_vm_adap_ifidx = temp_list[0]
        else:
            rtn_vm_adap_ifidx = temp_list

        return rtn_vm_adap_ifidx

    @staticmethod
    def get_ip_prefixlength(ip_mask: str) -> int:
        return sum(bin(int(i)).count('1') for i in ip_mask.split('.'))

    @classmethod
    def update_vf_adapter_name(
            cls, vm_name: str, vm_adapter_name: str, vm_adapter_ifdesc_kw: str = "LD 1160-2X",
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, vf_name: str = None, win_vm_ip: str = None
    ):
        """
        author: wei.yuan1
        date: 2023.12.21
        description: 修改网卡名称
        :param vf_name: vf网卡的名称
        :param vm_name: 虚机名称
        :param vm_adapter_name: 网络适配器的名称
        :param vm_adapter_ifdesc_kw: 网卡的描述信息
        :param cmd_execute_address:
        :return:
        """
        if vf_name is None:
            vf_name = "vf-" + vm_adapter_name
        vm_adapter_mac_addr = cls.get_vm_adapter_macaddr(
            vm_name=vm_name, vm_adapter_name=vm_adapter_name, invoke_flag=False,
            cmd_execute_address=cmd_execute_address, virtual_ip=win_vm_ip)
        if vm_adapter_mac_addr is None:
            rtn_oper_code = RtnStatusEnum.FAIL.value
            return rtn_oper_code, vm_adapter_mac_addr
        log.info('在物理机侧获取虚拟机：{}，网卡：{}，的macaddr：{}'.format(vm_name, vm_adapter_name, vm_adapter_mac_addr))

        log.info('在虚拟机侧，获取虚拟机：{}，适配器：{}，mac addr：{}，对应的IfIndex属性值'.format(
            vm_name, vm_adapter_name, vm_adapter_mac_addr))
        vm_adapter_ifindex_value = cls.get_vm_adapter_ifidx_with_macaddr(
            vm_name=vm_name, vm_adapter_macaddr=vm_adapter_mac_addr, invoke_flag=True,
            include_info=vm_adapter_ifdesc_kw, cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)
        log.info("vm_adapter_ifindex_value:{}".format(vm_adapter_ifindex_value))
        if not isinstance(vm_adapter_ifindex_value, str):
            log.error('在虚拟机侧，获取虚拟机：{}，适配器：{}，mac addr：{}，对应的IfIndex属性值失败'.format(
                vm_name, vm_adapter_name, vm_adapter_mac_addr))
            rtn_oper_code = RtnStatusEnum.FAIL.value
            return rtn_oper_code, vm_adapter_mac_addr, vm_adapter_ifindex_value
        log.info('在虚拟机侧，重命名虚拟机：{}，适配器名称为：{}'.format(vm_name, vf_name))
        rtn_oper_code = cls.rename_vm_adapter(
            vm_name=vm_name, new_vm_adapter_name=vf_name, ifindex=vm_adapter_ifindex_value,
            cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)
        if RtnStatusEnum.SUCCESS.value != rtn_oper_code:
            log.error('在虚拟机侧，重命名虚拟机：{}，适配器名称为：{}，失败'.format(vm_name, vf_name))
            return rtn_oper_code, vf_name

        log.info('在虚拟机侧，虚拟机：{}，适配器：{}，重命名成功'.format(vm_name, vf_name))
        return RtnStatusEnum.SUCCESS.value, vf_name

    @classmethod
    def update_vm_vf_apapter_name(
            cls, vm_name: str, vm_vf_adapter_name: str, vm_hyper_v_adapter_name: str = None,
            vm_vf_adapter_mac_addr: str = None, vm_adapter_ifdesc_include_kw: str = None,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author:      haibin.xu
        date:        2023-12-25 11:36:15
        description: 配置虚拟机vf网卡 相关信息

        :param vm_name: 虚拟机名称
        :param vm_vf_adapter_name: 待要配置的虚拟机vf网卡名称
        :param vm_hyper_v_adapter_name: 与虚拟机vf网卡mac地址相同的虚拟机hyper-v网卡名称，改网卡名称为测试机hyper-v 虚拟机设置界面
               显示的网卡名称
        :param vm_vf_adapter_mac_addr: 虚拟机vf网卡mac地址
        :param vm_adapter_ifdesc_include_kw: 识别虚拟机vf网卡InterfaceDescription关键字
        :param cmd_execute_address: 命令执行地址信息
        :return:
        """
        rtn_oper_code = RtnStatusEnum.FAIL.value
        vm_vf_adapter_ifindex_value = None

        if vm_vf_adapter_mac_addr is None:
            if vm_hyper_v_adapter_name is None:
                log.warning('在没有给定虚拟机vf网卡Mac地址情况下，也没有指定虚拟机hyper-v网卡名称，无法获取虚拟机VF网卡mac地址')
                return rtn_oper_code, vm_vf_adapter_mac_addr, vm_vf_adapter_ifindex_value
            else:
                log.info('在物理机侧获取虚拟机：{}，根据hyper-v网卡：{}，获取VF网卡的macaddr'.format(
                    vm_name, vm_hyper_v_adapter_name))
                vm_vf_adapter_mac_addr = cls.get_vm_adapter_macaddr(
                    vm_name=vm_name, vm_adapter_name=vm_hyper_v_adapter_name, invoke_flag=False,
                    cmd_execute_address=cmd_execute_address)
                if vm_vf_adapter_mac_addr is None:
                    return rtn_oper_code, vm_vf_adapter_mac_addr, vm_vf_adapter_ifindex_value
                log.info('在物理机侧获取虚拟机：{}，根据hyper-v网卡：{}，获取VF网卡的的macaddr：{}'.format(
                    vm_name, vm_hyper_v_adapter_name, vm_vf_adapter_mac_addr))

        log.info('在虚拟机侧，获取虚拟机：{}，vf网卡：{}，mac addr：{}，对应的IfIndex属性值'.format(
            vm_name, vm_vf_adapter_name, vm_vf_adapter_mac_addr))
        vm_vf_adapter_ifindex_value = cls.get_vm_adapter_ifidx_with_macaddr(
            vm_name=vm_name, vm_adapter_macaddr=vm_vf_adapter_mac_addr, invoke_flag=True,
            include_info=vm_adapter_ifdesc_include_kw, cmd_execute_address=cmd_execute_address)
        if not isinstance(vm_vf_adapter_ifindex_value, str):
            log.error('在虚拟机侧，获取是虚拟机：{}，适配器：{}，mac addr：{}，对应的IfIndex属性值失败'.format(
                vm_name, vm_vf_adapter_name, vm_vf_adapter_mac_addr))
            return rtn_oper_code, vm_vf_adapter_mac_addr, vm_vf_adapter_ifindex_value
        log.info('在虚拟机侧，获取虚拟机：{}，适配器：{}，mac addr：{}，对应的IfIndex属性值：{}'.format(
            vm_name, vm_vf_adapter_name, vm_vf_adapter_mac_addr, vm_vf_adapter_ifindex_value))

        log.info('在虚拟机侧，重命名虚拟机：{}，vf适配器名称为：{}'.format(vm_name, vm_vf_adapter_name))
        rtn_oper_code = cls.rename_vm_adapter(
            vm_name=vm_name, new_vm_adapter_name=vm_vf_adapter_name, ifindex=vm_vf_adapter_ifindex_value,
            cmd_execute_address=cmd_execute_address)
        if RtnStatusEnum.SUCCESS.value != rtn_oper_code:
            log.error('在虚拟机侧，重命名虚拟机：{}，vf适配器名称为：{}，失败'.format(vm_name, vm_vf_adapter_name))
            return rtn_oper_code, vm_vf_adapter_mac_addr, vm_vf_adapter_ifindex_value

        log.info('在虚拟机侧，虚拟机：{}，适配器：{}，重命名成功'.format(vm_name, vm_vf_adapter_name))

        return rtn_oper_code, vm_vf_adapter_mac_addr, vm_vf_adapter_ifindex_value

    @classmethod
    def virtual_system_windows_setting(
            cls, vm_name: str, vm_adapter_name: str, new_ip: str, prefix_length: Union[str, int],
            new_gateway: str = None, vm_adapter_ifdesc_kw: str = None,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, v_adapter_name: str = None,
            vm_adapter_ifdesc_include_kw: str = None, win_vm_ip: str = None):
        """
        author:      wei.yuan1
        date:        2024-01-10 10:43:01
        description: 从PF端配置虚拟机hyper-v ip地址信息

        :param vm_name: 虚拟机name
        :param vm_adapter_name: 从pf虚拟机适配器(外)name
        :param v_adapter_name: 虚拟机适配器(内)name
        :param new_ip:  给虚拟机配置的ip
        :param new_gateway: 给虚拟机配置的网关
        :param prefix_length: 给虚拟机配置的掩码信息
        :param vm_adapter_ifdesc_kw: 指定虚拟机内部适配器不需要包含的InterfaceDescription keywords
        :param cmd_execute_address: 命令执行地址信息
        :param vm_adapter_ifdesc_include_kw: 指定虚拟机内部适配器InterfaceDescription需要包含的关键字
        :return:     配置成功返回True，失败返回False
        """
        vm_adapter_ifindex_value = None
        if not v_adapter_name:
            v_adapter_name = vm_adapter_name
        # 获取掩码信息
        if isinstance(prefix_length, int):
            prefix_length = str(prefix_length)
        else:
            prefix_length = cls.get_ip_prefixlength(prefix_length)

        log.info('在物理机侧获取虚拟机：{}，网卡：{}，的macaddr'.format(vm_name, vm_adapter_name))
        # 获取网卡的mac地址
        vm_adapter_mac_addr = cls.get_vm_adapter_macaddr(
            vm_name=vm_name, vm_adapter_name=vm_adapter_name, invoke_flag=False,
            cmd_execute_address=cmd_execute_address, virtual_ip=win_vm_ip)
        if vm_adapter_mac_addr is None:
            rtn_oper_code = RtnStatusEnum.FAIL.value
            return rtn_oper_code, vm_adapter_mac_addr, vm_adapter_ifindex_value, new_ip
        log.info('在物理机侧获取虚拟机：{}，网卡：{}，的macaddr：{}'.format(vm_name, vm_adapter_name, vm_adapter_mac_addr))

        log.info('在虚拟机侧，获取虚拟机：{}，适配器：{}，mac addr：{}，对应的IfIndex属性值'.format(
            vm_name, vm_adapter_name, vm_adapter_mac_addr))
        time.sleep(5)
        vm_adapter_ifindex_value = cls.get_vm_adapter_ifidx_with_macaddr(
            vm_name=vm_name, vm_adapter_macaddr=vm_adapter_mac_addr, invoke_flag=True,
            uninclude_info=vm_adapter_ifdesc_kw, include_info=vm_adapter_ifdesc_include_kw,
            cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)
        if not isinstance(vm_adapter_ifindex_value, str):
            log.error('在虚拟机侧，获取是虚拟机：{}，适配器：{}，mac addr：{}，对应的IfIndex属性值失败'.format(
                vm_name, vm_adapter_name, vm_adapter_mac_addr))
            rtn_oper_code = RtnStatusEnum.FAIL.value
            return rtn_oper_code, vm_adapter_mac_addr, vm_adapter_ifindex_value, new_ip
        log.info('在虚拟机侧，获取虚拟机：{}，适配器：{}，mac addr：{}，对应的IfIndex属性值：{}'.format(
            vm_name, vm_adapter_name, vm_adapter_mac_addr, vm_adapter_ifindex_value))

        log.info('获取当前虚拟机：{}，适配器：{}，ip，检查ip是否为有效ip'.format(vm_name, vm_adapter_name))
        rtn_check_code, rtn_ipaddr = cls.check_adapter_ipaddress(
            vm_name=vm_name, ifindex=vm_adapter_ifindex_value, invoke_flag=True,
            cmd_execute_address=cmd_execute_address, virtual_ip=win_vm_ip)
        if isinstance(rtn_ipaddr, str) and rtn_ipaddr.startswith('10.'):
            log.info('获取当前虚拟机：{}，适配器：{}，ip：{}，为有效ip，不再配置新的ip，网关'.format(
                vm_name, vm_adapter_name, rtn_ipaddr))
            new_ip = rtn_ipaddr
        else:
            log.info("在{}虚机侧，删除网卡{}无效的IPV4地址".format(vm_name, vm_adapter_name))
            log.info('在虚拟机侧，更新虚拟机：{}，适配器：{}，ip地址'.format(vm_name, vm_adapter_name))
            rtn_oper_code = cls.update_vm_adapter_ip_address(
                vm_name=vm_name, new_ip=new_ip, ifindex=vm_adapter_ifindex_value, prefix_length=prefix_length,
                invoke_flag=True, cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)
            if RtnStatusEnum.SUCCESS.value != rtn_oper_code:
                log.error('在虚拟机侧，更新虚拟机：{}，适配器：{}，ip地址为：{}，失败'.format(vm_name, vm_adapter_name, new_ip))
                return rtn_oper_code, vm_adapter_mac_addr, vm_adapter_ifindex_value, new_ip

            log.info('在虚拟机侧，更新虚拟机：{}，适配器：{}，网关地址'.format(vm_name, vm_adapter_name))
            rtn_oper_code = cls.update_vm_adapter_gateway(
                vm_name=vm_name, new_gateway=new_gateway, ifindex=vm_adapter_ifindex_value, invoke_flag=True,
                cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)
            if RtnStatusEnum.SUCCESS.value != rtn_oper_code:
                log.error('在虚拟机侧，更新虚拟机：{}，适配器：{}，网关地址为：{}，失败'.format(
                    vm_name, vm_adapter_name, new_gateway))
                return rtn_oper_code, vm_adapter_mac_addr, vm_adapter_ifindex_value, new_ip

        log.info('在虚拟机侧，重命名虚拟机：{}，适配器名称为：{}'.format(vm_name, v_adapter_name))
        rtn_oper_code = cls.rename_vm_adapter(
            vm_name=vm_name, new_vm_adapter_name=v_adapter_name, ifindex=vm_adapter_ifindex_value,
            cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)
        if RtnStatusEnum.SUCCESS.value != rtn_oper_code:
            log.error('在虚拟机侧，重命名虚拟机：{}，适配器名称为：{}，失败'.format(vm_name, v_adapter_name))
            return rtn_oper_code, vm_adapter_mac_addr, vm_adapter_ifindex_value, new_ip

        log.info('在虚拟机侧，虚拟机：{}，适配器：{}，ip更新成功，网关更新成功，重命名成功'.format(vm_name, v_adapter_name))

        return rtn_oper_code, vm_adapter_mac_addr, vm_adapter_ifindex_value, new_ip

    @classmethod
    def virtual_system_linux_setting(
            cls, vm_name: str, vm_adapter_name: str, new_ip: str, prefix_length: Union[str, int],
            new_gateway: str = None, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
            v_adapter_name: str = None, virtual_ip: str = None, sr_iov_flag: bool = False):
        """
        author: wei.yuan1
        date: 2024.01.10
        description: 如果虚机系统为linux系统，进行处理
        :param vm_adapter_name:
        :param vm_name: 虚机名称
        :param new_ip: 新添加的ip地址信息
        :param prefix_length: 掩码信息
        :param new_gateway: 网关信息
        :param cmd_execute_address:命令执行
        :param v_adapter_name: 虚机内的网卡名称
        :param virtual_ip: 虚机的IP
        :return:
        """
        rtn_code = RtnStatusEnum.SUCCESS.value
        if isinstance(prefix_length, int):
            prefix_length = str(prefix_length)
        else:
            prefix_length = cls.get_ip_prefixlength(prefix_length)
        log.info('在物理机侧获取虚拟机：{}，网卡：{}，的macaddr'.format(vm_name, vm_adapter_name))
        # 获取网卡的mac地址
        vm_adapter_mac_addr = cls.get_vm_adapter_macaddr(
            vm_name=vm_name, vm_adapter_name=vm_adapter_name, invoke_flag=False,
            cmd_execute_address=cmd_execute_address)
        if vm_adapter_mac_addr is None:
            rtn_oper_code = RtnStatusEnum.FAIL.value
            return rtn_oper_code, vm_adapter_mac_addr, None, new_ip
        log.info('在物理机侧获取虚拟机：{}，网卡：{}，的macaddr：{}'.format(vm_name, vm_adapter_name, vm_adapter_mac_addr))

        log.info('在虚拟机侧，获取虚拟机：{}，适配器：{}，mac addr：{}'.format(
            vm_name, vm_adapter_name, vm_adapter_mac_addr))
        vm_adapter_addr_dict, vm_adapter_mac_dict = cls.get_nic_addr_dict(
            vm_name=vm_name, cmd_execute_address=cmd_execute_address, virtual_ip=virtual_ip, sr_iov_flag=sr_iov_flag)
        # 根据虚机侧和虚机内的网卡进行对比映射
        for nic_key, mac_addr_value in vm_adapter_mac_dict.items():
            if vm_adapter_mac_addr.lower().replace("-", ":") == mac_addr_value.replace(":", ""):
                v_adapter_name = nic_key
        log.info('在虚拟机内，获取虚拟机：{}，适配器：{}，mac addr：{}'.format(
            vm_name, v_adapter_name, vm_adapter_mac_addr))

        log.info('获取当前虚拟机：{}，适配器：{}，ip，检查ip是否为有效ip'.format(vm_name, vm_adapter_name))
        rtn_ipaddr_list = vm_adapter_addr_dict[v_adapter_name]
        rtn_ipaddr = rtn_ipaddr_list[0]
        # rtn_check_code, rtn_ipaddr = cls.check_adapter_ipaddress(
        #     vm_name=vm_name, invoke_flag=True, cmd_execute_address=cmd_execute_address, virtual_system="Linux",
        #     virtual_ip=virtual_ip)
        if isinstance(rtn_ipaddr, str) and rtn_ipaddr.startswith('10.'):
            log.info('获取当前虚拟机：{}，适配器：{}，ip：{}，为有效ip，不再配置新的ip，网关'.format(
                vm_name, vm_adapter_name, rtn_ipaddr))
            new_ip = rtn_ipaddr
        else:
            log.info('在虚拟机侧，更新虚拟机：{}，适配器：{}，ip地址'.format(vm_name, vm_adapter_name))
            rtn_code = cls.setting_virtual_linux_setting(
                vm_name=vm_name, new_ip=new_ip, prefix_length=prefix_length,
                v_adapter_name=v_adapter_name, cmd_execute_address=cmd_execute_address, virtual_ip=virtual_ip,
                sr_iov_flag=sr_iov_flag
            )
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.error("在虚机侧，更新虚拟机：{}， 适配器：{}， ip地址为：{},失败".format(vm_name, vm_adapter_name, new_ip))
                return rtn_code, vm_adapter_mac_addr, v_adapter_name, new_ip

        # rtn_code = cls.virtual_linux_route_setting(
        #     vm_name=vm_name, route_addr=new_gateway, v_adapter_name=v_adapter_name,
        #     cmd_execute_address=cmd_execute_address, virtual_ip=virtual_ip)
        # if rtn_code != RtnStatusEnum.SUCCESS.value:
        #     log.error('在虚拟机侧，更新虚拟机：{}，适配器：{}，网关地址为：{}，失败'.format(
        #         vm_name, vm_adapter_name, new_gateway))
        #     return rtn_code, vm_adapter_mac_addr, v_adapter_name, new_ip

        return rtn_code, vm_adapter_mac_addr, v_adapter_name, new_ip

    @classmethod
    def check_virtual_linux_route_addr(cls, vm_name: str, v_adapter_name: str,
                                       cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                                       virtual_ip: str = None
                                       ):
        """
        author: wei.yuan1
        date: 2024.01.11
        description: 虚拟机系统为linux系统时，对系统进行设置
        :param vm_name:
        :param v_adapter_name:
        :param cmd_execute_address:
        :param virtual_ip: 虚机的IP
        :return:
        """
        rtn_code = RtnStatusEnum.FAIL.value
        get_route_cmd = f"netstat -nr|grep {v_adapter_name}| tr -s ' ' | cut -d' ' -f2"
        # get_route_cmd = CommandOperation.concat_invoke_command(vm_name=vm_name, cmd=get_route_cmd)
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
            cmd=get_route_cmd, cmd_execute_address=cmd_execute_address, ssh_ip=virtual_ip, script_object=True)
        if RtnStatusEnum.SUCCESS.value == cmd_code:
            cmd_stdout = cmd_stdout.replace("\r", "")
            match_list = cmd_stdout.split("\n")
            match_list = [index for index in match_list if index != "0.0.0.0"]
            if len(match_list) != 0:
                rtn_code = RtnStatusEnum.SUCCESS.value
        return rtn_code

    @classmethod
    def virtual_linux_route_setting(cls, vm_name: str, route_addr: str, v_adapter_name: str,
                                    cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                                    virtual_ip: str = None):
        """
        author: wei.yuan1
        date: 2024.01.11
        description: 虚机为linux时，网关的适配
        :param vm_name:
        :param route_addr:
        :param v_adapter_name:
        :param cmd_execute_address:
        :return:
        """
        if route_addr is None:
            route_addr = "0.0.0.0"
        rtn_update_code = RtnStatusEnum.FAIL.value
        rtn_code = cls.check_virtual_linux_route_addr(vm_name=vm_name, v_adapter_name=v_adapter_name,
                                                      cmd_execute_address=cmd_execute_address,
                                                      virtual_ip=virtual_ip)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f"虚机：{vm_name}中的网卡{v_adapter_name} 网关 {route_addr}已配置")
            return rtn_code

        add_route_cmd = f"ip route add default via {route_addr} dev {v_adapter_name}"
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
            cmd=add_route_cmd, cmd_execute_address=cmd_execute_address, ssh_ip=virtual_ip, script_object=True)
        if cmd_code == RtnStatusEnum.SUCCESS.value:
            log.info(f"命令：{add_route_cmd} 执行成功")
            if RtnStatusEnum.SUCCESS.value == cls.check_virtual_linux_route_addr(
                    vm_name=vm_name, v_adapter_name=v_adapter_name, cmd_execute_address=cmd_execute_address,
                    virtual_ip=virtual_ip):
                log.info_caller("网关配置成功")
                rtn_update_code = RtnStatusEnum.SUCCESS.value
            else:
                log.error_caller(f"命令：{add_route_cmd}执行成功，但是未找到配置的网关")
        else:
            log.info('命令: {}，执行失败'.format(add_route_cmd))
        return rtn_update_code

    @classmethod
    def setting_virtual_linux_setting(cls, vm_name: str, new_ip: str, prefix_length: str,
                                      v_adapter_name, cmd_execute_address, virtual_ip: str = None,
                                      sr_iov_flag: bool = False):
        """
        author: wei.yuan1
        date: 2024.01.11
        description: 虚机为linux 时，进行环境配置
        :param vm_name:
        :param new_ip:
        :param prefix_length:
        :param v_adapter_name:
        :param virtual_ip: 虚机的IP地址
        :param cmd_execute_address:
        :return:
        """
        rtn_add_code = RtnStatusEnum.SUCCESS.value
        ip_addr = new_ip + f"/{prefix_length}"
        add_static_ip_cmd = constants.STR_SPACE.join([constants.IP, constants.ADDRESS, constants.ADD,
                                                      ip_addr, constants.DEV, v_adapter_name])
        # add_static_ip_cmd = CommandOperation.concat_invoke_command(vm_name=vm_name, cmd=add_static_ip_cmd)
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
            cmd=add_static_ip_cmd, cmd_execute_address=cmd_execute_address, ssh_ip=virtual_ip, ssh_port="22",
            script_object=True)
        if RtnStatusEnum.SUCCESS.value == cmd_code:
            log.info('命令: {}，执行成功'.format(add_static_ip_cmd))
            nic_addr_dict, _ = cls.get_nic_addr_dict(
                vm_name=vm_name, cmd_execute_address=cmd_execute_address, virtual_ip=virtual_ip,
                sr_iov_flag=sr_iov_flag
            )
            if ip_addr not in nic_addr_dict[v_adapter_name]:
                log.error('ip配置命令: {}，执行成功，但是检查环境，未发现配置的ip'.format(add_static_ip_cmd))
                rtn_add_code = RtnStatusEnum.FAIL.value
            else:
                log.info('Ip更新成功')
        else:
            log.error('命令: {}，执行失败，ip配置失败'.format(add_static_ip_cmd))
        return rtn_add_code

    @classmethod
    def update_vm_adapter_name_ip_gateway_address(
            cls, vm_name: str, vm_adapter_name: str, new_ip: str, prefix_length: Union[str, int],
            new_gateway: str = None, vm_adapter_ifdesc_kw: str = None,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, v_adapter_name: str = None,
            vm_adapter_ifdesc_include_kw: str = None, virtual_system: str = "windows",
            virtual_ip: str = None, sr_iov_flag: bool = False) -> tuple:
        """
        author:      wei.yuan1
        date:        2023-11-29 10:43:01
        description: 从PF端配置虚拟机hyper-v ip地址信息

        :param vm_name: 虚拟机name
        :param vm_adapter_name: 从pf虚拟机适配器(外)name
        :param v_adapter_name: 虚拟机适配器(内)name
        :param new_ip:  给虚拟机配置的ip
        :param new_gateway: 给虚拟机配置的网关
        :param prefix_length: 给虚拟机配置的掩码信息
        :param vm_adapter_ifdesc_kw: 指定虚拟机内部适配器不需要包含的InterfaceDescription keywords
        :param cmd_execute_address: 命令执行地址信息
        :param virtual_system: 测试机的虚拟机系统版本
        :param vm_adapter_ifdesc_include_kw: 指定虚拟机内部适配器InterfaceDescription需要包含的关键字
        :param virtual_ip: 虚机的IP地址
        :return:     配置成功返回True，失败返回False
        :change author: wei.yuan1
        :change description: 虚机为linux时进行适配
        """
        if "/24" in new_ip:
            new_ip = new_ip.replace("/24", "")
        if virtual_system == "windows":
            rtn_description_list = cls.virtual_system_windows_setting(
                vm_name=vm_name, vm_adapter_name=vm_adapter_name, new_ip=new_ip, prefix_length=prefix_length,
                new_gateway=new_gateway, vm_adapter_ifdesc_include_kw=vm_adapter_ifdesc_include_kw,
                cmd_execute_address=cmd_execute_address, v_adapter_name=v_adapter_name,
                vm_adapter_ifdesc_kw=vm_adapter_ifdesc_kw, win_vm_ip=virtual_ip
            )
            rtn_oper_code, vm_adapter_mac_addr, vm_adapter_ifindex_value, new_ip = rtn_description_list
            return rtn_oper_code, vm_adapter_mac_addr, vm_adapter_ifindex_value, new_ip
        else:
            rtn_description_list = cls.virtual_system_linux_setting(
                vm_name=vm_name, vm_adapter_name=vm_adapter_name, new_ip=new_ip, prefix_length=prefix_length,
                new_gateway=new_gateway, cmd_execute_address=cmd_execute_address, v_adapter_name=v_adapter_name,
                virtual_ip=virtual_ip, sr_iov_flag=sr_iov_flag
            )
            # vm_adapter_ifindex_value值信息在linux虚机中为虚机内网卡的名称
            rtn_oper_code, vm_adapter_mac_addr, vm_adapter_ifindex_value, new_ip = rtn_description_list
            return rtn_oper_code, vm_adapter_mac_addr, vm_adapter_ifindex_value, new_ip

    @classmethod
    def get_netadapter_switch_name(cls, vm_name: str, vm_adapter_name: str,
                                   cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2024.01.18
        description: 獲取指定网络适配器绑定的交换机
        :param vm_name:
        :param vm_adapter_name:
        :param cmd_execute_address:
        :return:
        """
        stdout = ""
        exec_commnad = f'(get-VMNetworkAdapter -VMName "{vm_name}" -Name "{vm_adapter_name}").SwitchName'
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                cmd=exec_commnad, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_stdout = rtn_stdout.replace("\r","")
            stdout = re.sub(r"\s+", "", rtn_stdout)
        return stdout

    @classmethod
    def remove_vmnetworkadapter(
            cls, vm_name: str, vm_adapter_name_list: list = None,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> bool:
        """
        author:      haibin.xu
        date:        2023-11-28 12:04:12
        description: 移除虚拟机网络适配器

        :param vm_name: 虚拟机name
        :param vm_adapter_name_list: 虚拟机网络适配器name list
        :param cmd_execute_address: 命令执行地址信息
        :return:     None
        """
        rtn_remove_flag = True
        remove_cmd_list = []
        if vm_adapter_name_list is None:
            vm_adapter_name_list = [None]
            remove_cmd_list.append('Remove-VMNetworkAdapter -VMName {}'.format(vm_name))
        else:
            for adapter_name in vm_adapter_name_list:
                remove_cmd_list.append("Remove-VMNetworkAdapter -VMName {} -Name '{}'".format(vm_name, adapter_name))
        for adapter_name, remove_cmd in zip(vm_adapter_name_list, remove_cmd_list):
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                cmd=remove_cmd, cmd_execute_address=cmd_execute_address)
            log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                remove_cmd, cmd_code, cmd_stdout, cmd_stderr))
            if not cls.check_vmnetworkadapter_exist(vm_name=vm_name, vm_adapter_name=adapter_name,
                                                    cmd_execute_address=cmd_execute_address):
                log.info('虚拟机：{}，移除网络适配器：{}，成功'.format(vm_name, adapter_name))
            else:
                log.error('虚拟机：{}，移除网络适配器：{}，失败'.format(vm_name, adapter_name))
                rtn_remove_flag = False
                break

        return rtn_remove_flag

    @classmethod
    def vm_insmod_ko(cls, file_path: str, virtual_ip: str):
        """
        author: wei.yuan1
        date: 2024.01.17
        description: 对虚机添加驱动
        :param file_path:
        :param virtual_ip: 虚机的ip
        :return:
        """
        exec_commnad = f"insmod {file_path}"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_commnad, ssh_ip=virtual_ip, ssh_username="root", script_object=True)
        return rtn_code, rtn_stdout, rtn_stderr

    @classmethod
    def get_vm_virtual_netadapter(cls, vm_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        获取虚机的网络适配器的名称
        """
        vm_adapter_list = []
        exec_command = f"({constants.GET_VMNETWORKADAPTER} -VMname {vm_name}).Name"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_stdout = rtn_stdout.replace("\r", "")
            adapter_list = rtn_stdout.split("\n")
            for adapter in adapter_list:
                vm_adapter_list.append(re.sub(r"\s+", "", adapter))
        return vm_adapter_list


class VmSwitch(object):
    @classmethod
    def new_vmswitch(cls, vmswitch_name: str, adapter_name: str = None, enable_iov: bool = True,
                     execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author: xiangyu.liu
        date: 2023.11.04
        description: 新建vm switch，并检查状态
        """
        log.info(f"{execute_address}: 使用适配器{adapter_name}新建{vmswitch_name}，使能sriov:{enable_iov}")
        if enable_iov:
            enable_iov_field = 1
        else:
            enable_iov_field = 0
        apapter_param = f" -NetAdapterName '{adapter_name}'" if adapter_name is not None else ''
        cmd = f"New-VMSwitch -Name '{vmswitch_name}'{apapter_param} -EnableIov {enable_iov_field}"
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=execute_address)
        log.info("status:{}, out:{}, err:{}".format(status, out, err))
        if RtnStatusEnum.SUCCESS.value == status:
            log.info('命令: {}，执行成功，进一步检查虚拟交换机：{}，是否被创建'.format(cmd, vmswitch_name))
            time.sleep(5)
            if not cls.find_vmswitch(vmswitch_name=vmswitch_name, execute_address=execute_address):
                log.error('命令: {}，执行成功，但是虚拟交换机：{}，创建失败'.format(cmd, vmswitch_name))
                status = RtnStatusEnum.FAIL.value
            prop_dict = VmSwitch.get_vmswitch_prop(vmswitch_name=vmswitch_name, execute_address=execute_address,
                                                   prop_list=["IovEnabled"])
            if enable_iov and (prop_dict.get("IovEnabled") == "True"):
                log.info(f"{execute_address}: 虚拟交换机{vmswitch_name}，sriov使能状态:{enable_iov}, 正确")
            elif (not enable_iov) and (prop_dict.get("IovEnabled") == "False"):
                log.info(f"{execute_address}: 虚拟交换机{vmswitch_name}，sriov使能状态:{enable_iov}, 正确")
            else:
                log.error(f"{execute_address}: 虚拟交换机{vmswitch_name}，sriov使能状态:{enable_iov}, 错误")
                status = RtnStatusEnum.FAIL.value

        return cmd, status, out, err

    @classmethod
    def remove_vmswitch(cls, vmswitch_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: xiangyu.liu
        date: 2023.11.04
        description: 移除vm switch
        """
        log.info(f"{execute_address}: 移除{vmswitch_name}")
        vms_name_para = f'\'{vmswitch_name}\'' if vmswitch_name != '*' else '*'
        cmd = f"Remove-VMSwitch -Name {vms_name_para} -Force"
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=execute_address)
        log.info("status:{}, out:{}, err:{}".format(status, out, err))

    @classmethod
    def find_vmswitch(cls, vmswitch_name: str = "*sriov*", execute_address: str = CmdExecuteAdressEnum.SERVER.value) \
            -> bool:
        """
        author: xiangyu.liu
        date: 2023.11.04
        description: 查询vm switch是否存在
        """
        log.info(f"{execute_address}: 查询{vmswitch_name}是否存在")
        cmd = f"Get-VMSwitch" + "|?{$_.Name -like \'" + vmswitch_name + "\'}"
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=execute_address)
        log.info("status:{}, out:{}".format(status, out))
        if out:
            log.info(f"{vmswitch_name}存在")
            return True
        else:
            log.info(f"{vmswitch_name}不存在")
            return False

    @classmethod
    def findstr_sxepf_switch(cls, nic_keyword: str = "sxepf",
                             execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2023.11.27
        description: 查找是否绑定的测试网卡的信息
        """
        sxe_switch = []
        exec_command = "Get-VMSwitch |Select-Object name,NetAdapterInterfaceDescription|FL"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            cleaned_string = rtn_stdout.replace("\r", "")
            cleaned_string = cleaned_string.strip()
            # 去除空行
            result = '\n'.join(line for line in cleaned_string.splitlines() if line.strip())
            pattern = r'name\s*:\s*([\w*]+)\nNetAdapterInterfaceDescription\s*:\s*{(\w+)}'
            matches = re.findall(pattern, result)
            for match in matches:
                dict_key = match[0]
                if nic_keyword in match[1]:
                    sxe_switch.append(re.sub(r"\s+", "", dict_key))
                else:
                    pass
        return sxe_switch

    @classmethod
    def check_vmswitch_exist(cls, vmswitch_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) \
            -> bool:
        """
        author:      haibin.xu
        date:        2023-11-27 10:58:35
        description: 检查当前环境是否包含指定的虚拟交换机

        :param vmswitch_name: 目标虚拟交换机 name
        :param cmd_execute_address: 命令执行地址信息
        :return:     包含返回True，否则返回False
        """
        log.info('{}侧，检查是否包含虚拟交换机：{}'.format(cmd_execute_address, vmswitch_name))
        check_cmd = 'Get-VMSwitch -name "{}"'.format(vmswitch_name)
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
            cmd=check_cmd, cmd_execute_address=cmd_execute_address)
        log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            check_cmd, cmd_code, cmd_stdout, cmd_stderr))

        return True if RtnStatusEnum.SUCCESS.value == cmd_code else False

    @classmethod
    def get_vmswitch_prop(cls, vmswitch_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                          prop_list: list = None) \
            -> dict:
        """
        author:      haibin.xu
        date:        2023-11-27 10:58:35
        description: 获取指定虚拟交换机的指定属性值

        :param vmswitch_name: 目标虚拟交换机 name
        :param execute_address: 命令执行地址信息
        :return:     包含返回True，否则返回False
        """
        rtn_dict = {}
        if prop_list is None:
            prop_list = ["IovEnabled"]
        log.info('{}侧，获取虚拟交换机{}的属性值：{}'.format(execute_address, vmswitch_name, prop_list))
        all_prop = ", ".join(prop_list)
        check_cmd = 'Get-VMSwitch -SwitchType External -Name {}|select {}|fl'.format(vmswitch_name, all_prop)
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
            cmd=check_cmd, cmd_execute_address=execute_address)
        log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            check_cmd, cmd_code, cmd_stdout, cmd_stderr))

        for line in cmd_stdout.split("\n"):
            if line.strip():
                rtn_dict[line.split(":")[0].strip()] = line.split(":")[1].strip()
        return rtn_dict

    @classmethod
    def get_all_switch(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 获取所有的虚拟交换机
        :param cmd_execute_address:
        :return:
        """
        switch_list = []
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
            cmd="(Get-VMSwitch).Name", cmd_execute_address=cmd_execute_address)
        if cmd_code == RtnStatusEnum.SUCCESS.value:
            switch_list = [index for index in cmd_stdout.replace("\r", "").split("\n") if index != ""]
        return switch_list

# todo 待完成
# expander cli 存放的根路径，子路径文件夹是expander_port端口号命名的，以区分不同环境
PS3_EXP_CLI_ROOT = '/root/exp_simu_cli/'
PS3SIM_EXP_ROOT = "/opt/ps3sim/iocnode{}_expander/"
RMT_DIR_PATH = "/root/ps3test/upgrade_test"  # 升级包存放路径
RMT_EXP_PATH = PS3_EXP_CLI_ROOT
RMT_EXP_PATH_HOST = PS3SIM_EXP_ROOT
# expander 存放 nvdata测试文件的 文件夹名称(模拟平台 FPGA 通用)
EXP_RMT_NVDATA_DIR_NAME = "nvdata_dir"
# 模拟平台 expander soc 存放 nvdata测试文件的 文件夹存放路径
EXP_RMT_NVDATA_PATH = "{}/{}".format(RMT_EXP_PATH, EXP_RMT_NVDATA_DIR_NAME)
# 模拟平台 expander host + ioc 存放 nvdata测试文件的 文件夹存放路径
EXP_RMT_NVDATA_PATH_HOST = "{}/{}".format(RMT_EXP_PATH_HOST, EXP_RMT_NVDATA_DIR_NAME)

# FPGA expander 运行路径
FPGA_RMT_EXP_PATH = RMT_DIR_PATH  # /root/ps3test/upgrade_test
# 原先为"/opt/upgrade_dir"
# FPGA expander 存放 nvdata测试文件的 文件夹存放路径
FPGA_EXP_RMT_NVDATA_PATH = "{}/{}".format(FPGA_RMT_EXP_PATH, EXP_RMT_NVDATA_DIR_NAME)

# ----nvdata 相关路径、名称---
# 本地nvdata配置文件名（文件内容可修改）
EXP_NVDATA_CONF_SOURCE_FILE = "exp.csv"
# 是否使用xml文件类型的nvdata文件
XML_NVDATA_FLAG = True
EXP_NVDATA_CONF_SOURCE_XML_FILE = "expCfg.xml"
EXP_NVDATA_XML_DIR = "cfgXml"
# 远程nvdata header 文件名
EXP_NVDATA_CONF_CHANGE_FILE = "exp_change.csv"
EXP_NVDATA_CONF_CHANGE_XML_FILE = "exp_change.xml"
# 本地nvdata配置文件所在路径 ps3\test\esat\scripts\expander\nvdata\
EXP_NVDATA_CONF_PATH = os.path.abspath(os.path.dirname(__file__))
EXP_XML_DIR_NAME = "cfgXml"  # 所需文件 必须放在该文件夹下，否则找不到!


class KvmOp(object):

    remote_pci_xml = None
    bridge_pci_xml = None

    @classmethod
    def check_vm_state(cls, vm_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                       ssh_ip: str = None):
        """
        获取所有虚机的名称
        """
        exist_vm_command = f"virsh domstate {vm_name}"
        # 查看当前环境中的vm状态
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exist_vm_command,
            cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
        log.info("rtn_stdout: {}".format(rtn_stdout))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_outputs = rtn_stdout.strip()
        else:
            rtn_outputs = ""
        return rtn_outputs

    @classmethod
    def get_vm(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        获取所有虚机的名称
        """
        exist_vm_list = []
        exist_vm_command = "virsh list --all|tail -n +3"
        # 查看当前环境中的所有的vm虚拟机
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exist_vm_command,
            cmd_execute_address=cmd_execute_address)
        log.info("rtn_stdout: {}".format(rtn_stdout))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_outputs = rtn_stdout.replace("\r", "")
            vm_info_list = re.findall(r"\s+([\d-]*)\s+(\S*)\s+(\S*)", rtn_outputs)
            for vm_info in vm_info_list:
                exist_vm_list.append(vm_info[1])
        return exist_vm_list

    @classmethod
    def get_vf_prop_of_nic(cls, nic_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                           get_bdf: bool = True):
        """
        获取管理网卡的vf属性
        """
        vf_prop_dict = {}
        cmd = f"ip link show {nic_name}"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=cmd_execute_address)
        res = re.findall(r"\s+vf (\d+)\s+link/ether ([\S]+) brd ([\S]+), [vlan]*\s*(\d*)[, ]*spoof checking (\w+),"
                         r" link-state (\w+), trust (\w+)", rtn_stdout)
        if res:
            for i in range(len(res)):
                temp_dict = {
                    "vf": res[i][0],
                    "vf_device": nic_name + 'v' + res[i][0],
                    "link/ether": res[i][1],
                    "brd": res[i][2],
                    "vlan": res[i][3] if res[i][3] else "0",
                    "spoof checking": res[i][4],
                    "link-state": res[i][5],
                    "query_rss": res[i][6]
                }
                if get_bdf:
                    nic_bdf = cls.get_bdf_of_nic(temp_dict['vf_device'], cmd_execute_address=cmd_execute_address)
                    temp_dict['bdf'] = nic_bdf
                else:
                    temp_dict['bdf'] = ''
                vf_prop_dict[str(i)] = temp_dict.copy()

        return vf_prop_dict

    @classmethod
    def set_vf_prop_of_nic(cls, nic_name: str, vf_id: str, prop_name: str, prop_value: str,
                           cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        获取管理网卡的vf属性
        """
        cmd = f"ip link set {nic_name} vf {vf_id} {prop_name} {prop_value}"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=cmd_execute_address)

        return rtn_code, rtn_stdout, rtn_stderr

    @classmethod
    def create_new_mac(cls, old_mac_addr: str):
        if ":" in old_mac_addr:
            split_str = ":"
        if "-" in old_mac_addr:
            split_str = "-"
        else:
            split_str = ":"

        def add_one(matched):
            # 定义函数：将匹配的数字加 1
            value_1 = "{:0>2}".format(hex(int(matched.group('pos1'), 16)).replace("0x", ""))
            value_2 = "{:0>2}".format(hex(int(matched.group('pos2'), 16)).replace("0x", ""))
            value_3 = "{:0>2}".format(hex(int(matched.group('pos3'), 16)).replace("0x", ""))
            value_4 = "{:0>2}".format(hex(int(matched.group('pos4'), 16)).replace("0x", ""))
            value_5 = "{:0>2}".format(hex(int(matched.group('pos5'), 16)).replace("0x", ""))
            value_6 = "{:0>2}".format(hex(int(matched.group('pos6'), 16)+1).replace("0x", ""))
            return split_str.join([str(value_1), str(value_2), str(value_3), str(value_4), str(value_5), str(value_6)])

        # new_mac_addr = mac_addr最低位+1
        new_mac_addr = re.sub('(?P<pos1>\w+)[:-](?P<pos2>\w+)[:-](?P<pos3>\w+)[:-]'
                              '(?P<pos4>\w+)[:-](?P<pos5>\w+)[:-](?P<pos6>\w+)',
                              add_one, old_mac_addr)
        return new_mac_addr

    @classmethod
    def set_vf_prop_mac_of_nic(cls, nic_name: str, vf_id: str, old_mac_addr: str,
                               cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        # new_mac_addr = mac_addr最低位+1
        new_mac_addr = cls.create_new_mac(old_mac_addr)
        log.info("old_mac:{}, new_mac: {}".format(old_mac_addr, new_mac_addr))
        rtn_code, rtn_stdout, rtn_stderr =\
            cls.set_vf_prop_of_nic(nic_name, vf_id, "mac", new_mac_addr, cmd_execute_address)
        return rtn_code, rtn_stdout, rtn_stderr, new_mac_addr

    @classmethod
    def get_bdf_of_nic(cls, nic_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        获取管理网卡的vf属性
        """
        cmd = "ethtool -i {} |grep 'bus-info'".format(nic_name)
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=cmd_execute_address)
        log.info(rtn_stdout)
        bdf_info = rtn_stdout.split(": ")[-1]
        return bdf_info

    @classmethod
    def get_mac_of_vf_nic(cls, vf_nic_name: str,  win_vm_ip: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        获取vf网卡的mac
        """
        cmd = f"Get-Netadapter -name {vf_nic_name}|fl"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)
        log.info("rtn_code:{}\nrtn_stdout:{}\nrtn_stderr:{}".format(rtn_code, rtn_stdout, rtn_stderr))
        res = re.findall(r"MacAddress\s+:\s+(.*)", rtn_stdout)
        if res:
            return res[0].strip()
        else:
            return ""

    @classmethod
    def get_nic_name_by_ip(cls, nic_ip: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        根据ip获取网卡的名称
        """
        nic_name = ""
        cmd = "ifconfig |grep -B 1 inet|grep -v inet6"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=cmd_execute_address)
        log.info("rtn_stdout: {}".format(rtn_stdout))
        all_nic_info = rtn_stdout.split("--\n")
        for nic_info in all_nic_info:
            if nic_ip in nic_info:
                nic_name = nic_info.split(":")[0]
                break
        log.info(f"get_nic_name: {nic_name}")
        return nic_name

    @classmethod
    def get_pf_prop_of_nic(cls, nic_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        获取网卡的ipv4地址
        """
        pf_prop_dict = {}
        cmd = f"ip addr show {nic_name}"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=cmd_execute_address)
        ipv4_res = re.findall(r"\s+inet\s+([\d.]+)/(\d+)", rtn_stdout)
        if ipv4_res:
            pf_prop_dict["ipv4"] = ipv4_res[0][0]
            pf_prop_dict["ipv4_submask"] = ipv4_res[0][1]
        ipv6_res = re.findall(r"\s+inet6\s+([\w:]+)/(\d+)", rtn_stdout)
        if ipv6_res:
            pf_prop_dict["ipv6"] = ipv6_res[0][0]
            pf_prop_dict["ipv6_submask"] = ipv6_res[0][1]
        mac_res = re.findall(r"\s+link/ether\s+([\w:]+)\s+", rtn_stdout)
        if mac_res:
            pf_prop_dict["macaddr"] = mac_res[0]
        return pf_prop_dict

    @classmethod
    def get_vm_local_net_ip(cls, vm_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        获取网卡的ipv4地址
        """
        retry_max = 3
        retry_count = 0
        retry_interval_s = 5
        retry_flag = False
        net_local_ip = ''
        cmd = f"virsh domifaddr {vm_name}|tail -n +3"
        while retry_count < retry_max:
            status, out, err = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_address)
            log.info("status:{}, result:{}".format(status, out))
            res = re.findall(r"([\d./]+)", out)
            if res:
                net_local_ip = res[-1].split("/")[-2]
            # 获取net_local_ip成功
            if net_local_ip:
                retry_flag = True
                break
            time.sleep(retry_interval_s)
            retry_count += 1
        if retry_flag:
            log.info(f"获取虚拟机{vm_name}本地IP成功：{net_local_ip}")
            return net_local_ip
        else:
            log.error(f"在{retry_max * retry_interval_s}s内，获取虚拟机{vm_name}本地IP失败")
            return net_local_ip

    @classmethod
    def show_vm_net_device(cls, vm_name, execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        description: 获取虚机下的所有的网口设备，除lo设备外
        :param vm_name:
        :param execute_address:
        :return:
        """
        vm_name = f"{vm_name}"
        json_command = '{"execute": "guest-network-get-interfaces"}'
        exec_command = f'virsh qemu-agent-command {vm_name} \'{json_command}\''
        # 将字符串写入文件中，并将文件传输到测试服务器上
        current_path = os.path.abspath(os.path.dirname(__file__))
        root_path = os.path.dirname(current_path)
        if "scripts" == os.path.basename(root_path):
            sys.path.append(root_path)
        elif root_path == "/":
            raise ValueError
        else:
            root_path = os.path.dirname(root_path)
            sys.path.append(root_path)
        local_file_save_path = os.path.join(root_path, constants.FILE_TEMP_PATH_NAME)
        server_ip, client_ip = CommandOperation.get_logical_ip_form_config()
        if execute_address == CmdExecuteAdressEnum.SERVER.value:
            ssh_ip = server_ip
        else:
            ssh_ip = client_ip
        remote_file_name = f"{vm_name}_print_vm_ipaddr.sh"
        exec_command_file = os.path.join(local_file_save_path, remote_file_name)

        remote_address = os.path.join("/tmp/", remote_file_name)
        with open(exec_command_file, "w+") as file:
            file.write(exec_command)

        scp_file_cmd = f"scp -P {ssh_port} {exec_command_file} root@{ssh_ip}:{remote_address}"
        rtn_code, output, stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=scp_file_cmd,
            local_execute_flag=True
        )
        log.info(f"返回值为{str(rtn_code)}, output:{output}, error:{stderr}")
        retry_max = 60
        retry_count = 0
        interface_list = []
        while retry_count < retry_max:
            status, out, err = CommandOperation.execute_command_with_error(cmd=f"sh {remote_address}",
                                                                           cmd_execute_address=execute_address)
            log.info(out)
            data = json.loads(out)
            interfaces_dict = data.get('return', [])
            for index in interfaces_dict:
                interface_list.append(index["name"])
            if interface_list:
                break
        if os.path.exists(exec_command_file):
            os.remove(exec_command_file)
        interface_list = [index for index in interface_list if "lo" not in index]
        return interface_list


    @classmethod
    def get_vm_interface(cls, vm_name, execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        description: 获取VM的管理地址
        :param vm_name:
        :param execute_address:
        :return:
        """
        vm_name = f"{vm_name}"
        json_command = '{"execute": "guest-network-get-interfaces"}'
        exec_command = f'virsh qemu-agent-command {vm_name} \'{json_command}\''
        # 将字符串写入文件中，并将文件传输到测试服务器上
        current_path = os.path.abspath(os.path.dirname(__file__))
        root_path = os.path.dirname(current_path)
        if "scripts" == os.path.basename(root_path):
            sys.path.append(root_path)
        elif root_path == "/":
            raise ValueError
        else:
            root_path = os.path.dirname(root_path)
            sys.path.append(root_path)
        local_file_save_path = os.path.join(root_path, constants.FILE_TEMP_PATH_NAME)
        server_ip, client_ip = CommandOperation.get_logical_ip_form_config()
        if execute_address == CmdExecuteAdressEnum.SERVER.value:
            ssh_ip = server_ip
        else:
            ssh_ip = client_ip
        remote_file_name = f"{vm_name}_print_vm_ipaddr.sh"
        exec_command_file = os.path.join(local_file_save_path, remote_file_name)

        remote_address = os.path.join("/tmp/", remote_file_name)
        with open(exec_command_file, "w+") as file:
            file.write(exec_command)
        test_port = CommandLineArgsParse.get_test_port()

        scp_file_cmd = f"scp -P {ssh_port} {exec_command_file} root@{ssh_ip}:/tmp"
        rtn_code, output, stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=scp_file_cmd,
            local_execute_flag=True
        )
        log.info(f"返回值为{str(rtn_code)}, output:{output}, error:{stderr}")
        retry_max = 60
        retry_count = 0
        ip_addresses = []

        def is_ipv6(ip_addr):
            try:
                ipaddress.IPv6Interface(ip_addr)
                return True
            except ValueError:
                return False
        while retry_count < retry_max:
            status, out, err = CommandOperation.execute_command_with_error(cmd=f"sh {remote_address}",
                                                                           cmd_execute_address=execute_address)
            log.info(out)
            data = json.loads(out)
            ip_addresses = []
            interfaces = data.get('return', [])
            for interface in interfaces:
                for ip_info in interface.get('ip-addresses', []):
                    if ip_info.get('ip-address'):
                        ip_addresses.append(ip_info['ip-address'])
            ip_addresses = [index for index in ip_addresses if "127.0.0.1" not in index and "::1" not in index and not is_ipv6(index)]
            if ip_addresses:
                break
        if os.path.exists(exec_command_file):
            os.remove(exec_command_file)
        CommandOperation.execute_command_with_error(cmd=f"rm -rf {remote_address}", cmd_execute_address=execute_address)
        return ip_addresses[0]

    @classmethod
    def create_bridge_node(cls, vm_name, bridge_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                           bridge_pci_xml: str = None, bridge_type: str = "macvlan"):
        """
        author: wei.yuan1
        description: 创建网桥,在虚机中添加macvlan设备
        :param vm_name:
        :param bridge_name:
        :param cmd_execute_address:
        :param bridge_pci_xml:网桥bridge的文件名称
        :return:
        """
        rtn_code = RtnStatusEnum.SUCCESS.value
        if not bridge_pci_xml:
            bridge_pci_xml = f"/tmp/{bridge_name}.xml"
        all_interface_list = []
        def get_vm_status():
            log.info(f"获取vm虚拟机初始化状态")
            cmd = f"virsh domstate {vm_name}"
            status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=cmd_execute_address)
            log.info("status:{}, out:{}".format(status, out))
            if RtnStatusEnum.SUCCESS.value == status:
                running_state = out.strip()
            else:
                log.error("命令执行失败!")
                running_state = ""
            if running_state != "running":
                log.error(f"虚拟机{vm_name}未启动")
                return False
            else:
                log.error(f"虚拟机{vm_name}启动")
                return True
        vm_status = get_vm_status()
        if not vm_status:
            status = cls.start_vm(vm_name=vm_name, execute_address=cmd_execute_address)
            all_interface_list = cls.show_vm_net_device(vm_name=vm_name, execute_address=cmd_execute_address)
            if status == RtnStatusEnum.SUCCESS.value:
                exec_cmd = \
                    (f"virsh attach-interface --domain {vm_name} --type {bridge_type}"
                     f" --source {bridge_name} --model virtio --config --live")
                rtn_code, rtn_out, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_cmd, cmd_execute_address=cmd_execute_address)
        else:

            all_interface_list = cls.show_vm_net_device(vm_name=vm_name, execute_address=cmd_execute_address)
            exec_cmd = \
                (f"virsh attach-interface --domain {vm_name} --type {bridge_type}"
                 f" --source {bridge_name} --model virtio --config --live")
            rtn_code, rtn_out, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_cmd, cmd_execute_address=cmd_execute_address)

        new_all_interface_list = cls.show_vm_net_device(vm_name=vm_name, execute_address=cmd_execute_address)
        diff_interface_list = [index for index in new_all_interface_list if index not in all_interface_list]
        rtn_code = RtnStatusEnum.SUCCESS.value \
            if len(diff_interface_list) != 0 and rtn_code == RtnStatusEnum.SUCCESS.value else RtnStatusEnum.FAIL.value
        log.info(f"新增的设备为{diff_interface_list}")

        return rtn_code, bridge_pci_xml, diff_interface_list

    @classmethod
    def insert_node(cls, vm_name, bridge_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                           bridge_pci_xml: str = None):
        """
        author: wei.yuan1
        description: 创建网桥,在虚机中添加macvlan设备
        :param vm_name:
        :param bridge_name:
        :param cmd_execute_address:
        :param bridge_pci_xml:网桥bridge的文件名称
        :return:
        """
        rtn_code = RtnStatusEnum.SUCCESS.value
        if not bridge_pci_xml:
            bridge_pci_xml = f"/tmp/{bridge_name}.xml"
        all_interface_list = []

        def get_vm_status():
            log.info(f"获取vm虚拟机初始化状态")
            cmd = f"virsh domstate {vm_name}"
            status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=cmd_execute_address)
            log.info("status:{}, out:{}".format(status, out))
            if RtnStatusEnum.SUCCESS.value == status:
                running_state = out.strip()
            else:
                log.error("命令执行失败!")
                running_state = ""
            if running_state != "running":
                log.error(f"虚拟机{vm_name}未启动")
                return False
            else:
                log.error(f"虚拟机{vm_name}启动")
                return True

        exec_command = f"sh /root/sxetest/creat_bridge.sh {vm_name} {bridge_name} {bridge_pci_xml}"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            bridge_pci_xml = rtn_stdout.strip()
            vm_status = get_vm_status()

            if not vm_status:
                status = cls.start_vm(vm_name=vm_name, execute_address=cmd_execute_address)
                all_interface_list = cls.show_vm_net_device(vm_name=vm_name, execute_address=cmd_execute_address)
                if status:
                    exec_cmd = f"virsh attach-device {vm_name} {bridge_pci_xml}"
                    rtn_code, rtn_out, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_cmd, cmd_execute_address=cmd_execute_address)
            else:

                all_interface_list = cls.show_vm_net_device(vm_name=vm_name, execute_address=cmd_execute_address)
                exec_cmd = f"virsh attach-device {vm_name} {bridge_pci_xml}"
                rtn_code, rtn_out, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_cmd, cmd_execute_address=cmd_execute_address)

            new_all_interface_list = cls.show_vm_net_device(vm_name=vm_name, execute_address=cmd_execute_address)
            diff_interface_list = [index for index in new_all_interface_list if index not in all_interface_list]
            rtn_code = RtnStatusEnum.SUCCESS.value \
                if len(
                diff_interface_list) != 0 and rtn_code == RtnStatusEnum.SUCCESS.value else RtnStatusEnum.FAIL.value
            log.info(f"新增的设备为{diff_interface_list}")
        else:
            rtn_code = RtnStatusEnum.FAIL
            bridge_pci_xml = ""
            diff_interface_list = []
        return rtn_code, bridge_pci_xml, diff_interface_list

    @classmethod
    def get_all_non_sriov(cls, vm_name: str, nic_name: str = None,
                             cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """

        :param vm_name:
        :param nic_name: 透传到虚机的网口的名称
        :param cmd_execute_address:
        :return:
        """
        result = RtnStatusEnum.SUCCESS.value
        nic_device_dict = {}

        exec_command = f"virsh domiflist {vm_name}"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            device_list = rtn_stdout.splitlines()
            device_list = device_list[2:]
            for index in device_list:
                parts = index.split()
                if nic_name:
                    if len(parts) >= 5 and parts[2] == nic_name and parts[1] != "bridge":
                         nic_device_dict[parts[2]] = {"mac_addr":parts[-1], "type": parts[1]}
                else:
                    if len(parts) >= 5 and parts[1] != "bridge":
                         nic_device_dict[parts[2]] = {"mac_addr":parts[-1], "type": parts[1]}
        else:
            result = RtnStatusEnum.FAIL.value
        return result, nic_device_dict

    @classmethod
    def get_vm_non_sriov(cls, vm_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        descripton: 获取虚机内所有非sirov 设备
        :param vm_name:
        :param cmd_execute_address:
        :return:
        """
        nic_device_list = []
        exec_command = f"virsh domiflist {vm_name}"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            device_list = rtn_stdout.splitlines()
            for index in device_list:
                parts = index.split()
                if len(parts) > 2:
                    nic_device_list.append(parts[2])
        return nic_device_list

    @classmethod
    def detach_non_sriov_device_vm(cls, vm_name: str, device_dict: dict = {}, need_delete_device: str = None,
                         cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """

        :param vm_name:
        :param device_list: virsh domilst vm_name中获取到的
        :param cmd_execute_address:
        :return:
        """
        result = RtnStatusEnum.SUCCESS.value
        def get_vm_status():
            log.info(f"获取vm虚拟机初始化状态")
            cmd = f"virsh domstate {vm_name}"
            status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=cmd_execute_address)
            log.info("status:{}, out:{}".format(status, out))
            if RtnStatusEnum.SUCCESS.value == status:
                running_state = out.strip()
            else:
                log.error("命令执行失败!")
                running_state = ""
            if running_state != "running":
                log.error(f"虚拟机{vm_name}未启动")
                return False
            else:
                log.error(f"虚拟机{vm_name}启动")
                return True

        mac_addr, type = None, None
        if device_dict:
            for device, values in device_dict.items():
                if device == need_delete_device:
                    mac_addr = values["mac_addr"]
                    type = values["type"]
                    break
        vm_status = get_vm_status()
        if vm_status:
            if mac_addr:
                exec_command = \
                    f"virsh detach-interface --domain {vm_name} --type {type} --mac {mac_addr} --live --config"
            else:
                exec_command = \
                    f"virsh detach-interface --domain {vm_name} --type {type} --live --config"
            rtn_code, *_ = CommandOperation.execute_command_with_error(
                cmd=exec_command, cmd_execute_address=cmd_execute_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                non_sriov_device = cls.get_vm_non_sriov(vm_name=vm_name, cmd_execute_address=cmd_execute_address)
                result = RtnStatusEnum.SUCCESS.value if need_delete_device not in non_sriov_device else RtnStatusEnum.FAIL.value
        else:
            log.error(f"{vm_name}状态为未启动的状态")
            result = RtnStatusEnum.FAIL.value
        return result

    @classmethod
    def create_vf_of_nic(cls, nic_name: str, vf_num: int,
                         cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        创建vf
        """
        # nic_name = cls.get_nic_name_by_ip(nic_ip, cmd_execute_address=cmd_execute_address)

        if nic_name:
            bdf_info = cls.get_bdf_of_nic(nic_name, cmd_execute_address=cmd_execute_address)
        else:
            return ""
        if bdf_info:
            vf_num_0 = 0
            cmd = f"echo {vf_num_0} > /sys/bus/pci/devices/{bdf_info}/sriov_numvfs"
            rtn_code, outputs, err = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=cmd_execute_address)
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.error("command:{},rtn_code:{},outputs:{},err:{}".format(cmd, rtn_code, outputs, err))
                return ""
            cmd = f"echo {vf_num} > /sys/bus/pci/devices/{bdf_info}/sriov_numvfs"
            rtn_code, outputs, err = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=cmd_execute_address)
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.error("command:{},rtn_code:{},outputs:{},err:{}".format(cmd, rtn_code, outputs, err))
                return ""
        else:
            return ""

        vf_nic_name = nic_name + "v0"
        if vf_nic_name:
            vf_bdf_info = cls.get_bdf_of_nic(vf_nic_name, cmd_execute_address=cmd_execute_address)
        else:
            return ""

        return vf_nic_name, vf_bdf_info

    @classmethod
    def create_macvlan_of_nic(cls, nic_name: str, macvlan_num: int,
                              cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                              config_macvlan_ip: bool = False, pf_nic_ip: str = ""):
        """
        创建macvlan
        """
        temp_ip = pf_nic_ip
        macvlan_name_list = [f"macvlan{i}" for i in range(macvlan_num)]
        for macvlan_name in macvlan_name_list:
            cmd = f"ip link add link {nic_name} name {macvlan_name} type macvlan mode bridge"
            rtn_code, outputs, err = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=cmd_execute_address)
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.error(f"命令执行失败{cmd}")
                return []
            time.sleep(3)

            if config_macvlan_ip:
                def add_one(matched):
                    # 定义函数：将匹配的数字加 1
                    value_1 = int(matched.group('pos1'))
                    value_2 = int(matched.group('pos2'))
                    value_3 = int(matched.group('pos3'))
                    value_4 = int(matched.group('pos4')) + 1
                    return ".".join([str(value_1), str(value_2), str(value_3), str(value_4)])
                # vf ip = vswitch ip最低位+1
                macvlan_ip = re.sub('(?P<pos1>\d+)\.(?P<pos2>\d+)\.(?P<pos3>\d+)\.(?P<pos4>\d+)', add_one, temp_ip)
                cmd = f"ip addr add {macvlan_ip}/24 dev {macvlan_name}"
                rtn_code, outputs, err = CommandOperation.execute_command_with_error(
                    cmd=cmd, cmd_execute_address=cmd_execute_address)
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.error(f"命令执行失败{cmd}")
                    return []
                temp_ip = macvlan_ip
                time.sleep(3)

            cmd = f"ip link set dev {macvlan_name} up"
            rtn_code, outputs, err = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=cmd_execute_address)
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.error(f"命令执行失败{cmd}")
                return []

        return macvlan_name_list

    @classmethod
    def check_vm_nic_pci_exist(cls, vm_name: str, vf_nic_bdf: str,
                               cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        检查KVM虚拟机中是否存在指定PCI设备
        """
        # todo 待完成
        return RtnStatusEnum.SUCCESS.value

    @classmethod
    def upload_nvdata_conf_file(cls, local_path: str, rmt_base_path: str, dev_sg=None) -> int:
        """
        author: peibao.wang
        date: 2021.04.14
        description: 上传本地配置文件到远端
        :param local_path:本地文件路径
        :param rmt_base_path: 远端基础路径，为时间戳格式化的字符串
        :param dev_sg: 设备sg,区分设备类型，exp or switch
        :return: RtnStatusEnum
        @changelog:xiangyu.liu添加expander host适配
        """
        # todo 待完成
        # 检查远程Expander运行目录下是否有有nvdata文件夹，如果没有，创建该文件夹
        cmd = "ls {}".format(FPGA_EXP_RMT_NVDATA_PATH)
        status, res = CommandOperation.execute_command(cmd)
        if RtnStatusEnum.SUCCESS.value != status:  # 没有nvdata存放路径，创建该路径
            cmd_mk = "mkdir {}".format(FPGA_EXP_RMT_NVDATA_PATH)
            status_mk, res_mk = CommandOperation.execute_command(cmd_mk)
            if RtnStatusEnum.SUCCESS.value != status_mk:  # 创建nvdata文件夹失败
                log.error("创建nvdata文件夹失败，status:{} res:{}".format(status_mk, res_mk))
                return RtnStatusEnum.FAIL.value
        # 根据传入的时间对象，创建对应的文件夹
        cmd = "mkdir {}/{}".format(FPGA_EXP_RMT_NVDATA_PATH, rmt_base_path)
        status, res = CommandOperation.execute_command(cmd)
        if RtnStatusEnum.SUCCESS.value != status:  # 创建存放配置文件的路径失败
            log.error("创建配置文件路径失败，status:{} res:{}".format(status, res))
        log.info("创建配置文件路径，{}".format(rmt_base_path))

        # 将本地修改的nvdata配置文件复制到远端
        # local_path = os.path.join(EXP_NVDATA_CONF_PATH,
        #                           exp_constants.EXP_NVDATA_CONF_CHANGE_FILE)
        if local_path.endswith(".csv"):
            rmt_path = "{}/{}/{}".format(FPGA_EXP_RMT_NVDATA_PATH,
                                         rmt_base_path,
                                         EXP_NVDATA_CONF_CHANGE_FILE)
        else:
            rmt_path = "{}/{}/{}".format(FPGA_EXP_RMT_NVDATA_PATH,
                                         rmt_base_path,
                                         EXP_NVDATA_CONF_CHANGE_XML_FILE)
        # status = CliUtils.scp_to_remote_target(local_path, rmt_path, CommandLineArgsParse.get_host_ip())
        if RtnStatusEnum.SUCCESS.value != status:  # 文件上传失败
            log.error("nvdata配置文件上传失败")
            return RtnStatusEnum.FAIL.value
        return RtnStatusEnum.SUCCESS.value  # 文件上传成功

    @classmethod
    def change_nvdata_list_value(cls, nvdata_list, change_value_list: list, check_value: bool = True,
                                 print_info: bool = True, caller_class=None):
        """
        author: xiangyu.liu
        date: 2021.10.24
        description: 对传入的nvdata_list 进行值的修改，返回修改后的新nvdata_list
        :param nvdata_list: nvdata数据信息，list格式
        :param change_value_list: 要修改的数据，必须为list嵌套list格式。
        :param check_value: 是否对格式检查
        :param print_info: 是否打印日志信息
        :param caller_class: 调用类
        例如:[["arrDevType", "Info", "desc", "this is change value"], ["upsType", "ups0", "highCrit", "0x22"]]。
        四个值分别对应csv文件里边的 module--submodule--filed--defaultvalue
        :return: 修改后的nvdata数据信息，list格式
        """
        # todo 待完成
        def find_nodes(tree, path):
            """
            查找某个路径匹配的所有节点
            tree: xml树
            path: 节点路径
            """
            return_tree = tree.findall(path)
            if not return_tree:
                log.error("没找到指定内容")
            return tree.findall(path)

        def change_node_text(nodelist, text, is_add=False, is_delete=False):
            """
            改变/增加/删除一个节点的文本
            nodelist:节点列表
            text : 更新后的文本
            """
            for node in nodelist:
                if is_add:
                    node.text += text
                elif is_delete:
                    node.text = ""
                else:
                    node.text = text

        def if_type_u(node):
            """
            判断某个节点是否为U8 U32类型
            node: 节点
            """
            if "u" in node.get("type").lower():
                return True
            return False

        def if_type_u_more_multiple(node):
            """
            判断节点允许输入的u8数的数量
            node: 节点
            """
            type_name = node.get("type").lower()
            m = re.search(r"u8_(\d+)", type_name)
            if m:
                return m.group(1)
            else:
                return None

        def change_u_more_mutiple(input_info, type_count_num):
            """
            根据节点允许的u8数量，对传入的值进行修改
            node: 节点
            """
            return_info = input_info
            if type(input_info) == str:
                # todo 如果传入为字符串类型的数字，则不判断进制，仅将开头的0x删除
                # log.info("将字符串中的0x删除")
                input_list = input_info.split(",")
                return_list = list()
                if len(input_list) > 1:
                    # changelog 2022.05.18: 这里对传入的值进行了补零
                    for k in input_list:
                        try:
                            return_list.append("%02X" % int(k, 16))
                        except ValueError:
                            if print_info:
                                log.info("{}不为16进制数，未对传入的值进行修改".format(k))
                            return_list.append(k)
                    return_info = "".join(return_list)
                else:
                    return_info = input_info.replace("0x", "")
                # return_info = input_info.replace("0x", "").replace(",", "")

            elif type(input_info) == int:
                # todo 不确定传入的值的进制 是否会再次修改 目前为十六进制
                return_info = "%02X" % input_info

            if len(return_info) < (int(type_count_num) * 2):
                if print_info:
                    log.info("进行补零操作")
                return_info += "0" * int(int(type_count_num) * 2 - len(return_info))
                return return_info
            elif len(return_info) > (int(type_count_num) * 2):
                if print_info:
                    log.info("需要进行去零操作")
                m = re.search(r"(0*)", return_info[::-1])
                if not m:
                    return return_info
                zero_num = len(m.group(1))
                if zero_num < 2:
                    return return_info
                while True:
                    zero_num -= 1
                    return_info = return_info[:-1]
                    if len(return_info) == (int(type_count_num) * 2) or zero_num <= 1:
                        return return_info
            else:
                return return_info

        # 验证传入的修改数据 格式是否正确
        if type(change_value_list[0]) != list or len(change_value_list[0]) != 4:
            log.error("传入的修改数据格式错误，请检查！{}".format(change_value_list))
            return False
        # 遍历change_list，获取要修改的目标参数
        for i in change_value_list:
            # if CommandLineArgsParse.get_test_object() == TestObjectEnum.PCIE_SWITCH.value:
            target_node = "exp/" + i[0] + "/" + i[1] + "/" + i[2]

            nodes = find_nodes(nvdata_list, target_node)
            if not nodes:
                log.error("nvdata数据修改失败，请检查‘{}’是否存在！".format(target_node))
                # if caller_class:
                #     caller_class.set_bug_type(BugTypeEnum.FUNCTION.value)
                #     caller_class.bug_title = "nvdata数据修改失败，请检查‘{}’是否存在！".format(target_node)
                #     caller_class.bug_result = "nvdata数据修改失败，请检查‘{}’是否存在！".format(target_node)
                #     caller_class.bug_expect = "nvdata数据修改成功"
                #     caller_class.create_bug(caller_class.bug_title)

                return False
            # xml的value没有逗号和十六进制标识符0x,需要再适配
            if not if_type_u(nodes[0]):
                change_value = i[3]
            elif not check_value:
                change_value = i[3]
            else:
                type_count = if_type_u_more_multiple(nodes[0])
                if not type_count:
                    if type(i[3]) == str:
                        if print_info:
                            log.info("将字符串中的0x删除")
                        change_value = i[3].replace("0x", "").replace(",", "")
                    elif type(i[3]) == int:
                        # todo 不确定传入的值的进制 是否会再次修改 目前为十六进制
                        change_value = hex(i[3])[2:]
                    else:
                        log.error("传入的值得类型错误，修改失败！type:{}".format(type(i[3])))
                        return False
                else:
                    change_value = change_u_more_mutiple(i[3], type_count)
            change_node_text(nodes, change_value)
            if print_info:
                log.info("修改完成, [{}]的值改为[{}]".format(target_node.replace("/", "-"), change_value))
        if print_info:
            log.info("xml文件修改完成!")
        return nvdata_list

    @classmethod
    def update_nvdata_config(cls, dev_sn: str, conf_list=None, userdefault_list=None,
                             need_return_path=False, return_new_sg_flag: bool = False,
                             need_down_load: bool = True, need_exp_reset: bool = True,
                             target_sas_addr: str = None,
                             if_compile_defensive_test: bool = False,
                             sw_reboot_host: bool = False) -> tuple:
        """
        author: xiangyu.liu
        date: 2021.04.26
        description: 进行nvdata的升级
        :param if_compile_defensive_test: 是否为编译防守测试,如果为True,则验证是否编译不通过,默认为False,验证编译成功
        :param need_down_load: FPGA/EVB 物理环境,expander,是否需要烧写flash，默认True
        :param need_exp_reset: FPGA/EVB 物理环境,expander,是否需要重启，默认True
        :param dev_sn: 要升级的Expander dev_sn
        :param conf_list: 修改之后的nvdata配置文件列表
        :param userdefault_list: switch 修改之后的userDefault配置文件列表
        :param need_return_path: 是否需要返回远端 保存目录的路径
        :param return_new_sg_flag: 是否返回重启后新的sg号 （物理环境新增）
        :param target_sas_addr: 指定重启后的sas地址
        :param sw_reboot_host: switch_cs100是否必须强制重启主机来重启环境，比如sbr 端口配置修改的验证
        :return: RtnStatusEnum
        """
        # todo 待完成
        rmt_path = datetime.now().strftime("%Y%m%d_%H%M%S_%f")  # 作为区分不同配置文件的文件夹
        log.info("配置文件保存文件夹：{}".format(rmt_path))
        retun_dir_path = FPGA_EXP_RMT_NVDATA_PATH + "/" + rmt_path

        # changelog 2022.04.03 如果传入的conf_list 或者userdefault_list为False，则直接返回错误
        if type(conf_list) == bool:
            if need_return_path:
                return RtnStatusEnum.FAIL.value, retun_dir_path
            else:
                return RtnStatusEnum.FAIL.value

        if not conf_list:
            log.info("没有传入expander修改后的nvdata，无法开始编译过程")
            if need_return_path:
                return RtnStatusEnum.FAIL.value, ""
            else:
                return RtnStatusEnum.FAIL.value

        # 将配置文件写入到对应文件下
        conf_list.write(os.path.join(EXP_NVDATA_CONF_PATH,
                                     EXP_NVDATA_CONF_CHANGE_XML_FILE),
                        encoding="utf-8", xml_declaration=True)
        local_path = os.path.join(EXP_NVDATA_CONF_PATH, EXP_NVDATA_CONF_CHANGE_XML_FILE)
        log.info("本地配置文件生成成功")
        # 复制到远端指定路径下
        status = cls.upload_nvdata_conf_file(local_path, rmt_path, dev_sg=dev_sn)
        if RtnStatusEnum.SUCCESS.value != status:
            log.error("复制本地配置文件到远端配置文件失败")
            if need_return_path:
                return RtnStatusEnum.FAIL.value, retun_dir_path
            else:
                return RtnStatusEnum.FAIL.value
        log.info("将本地配置文件复制到远端成功")

    @classmethod
    def read_source_config_file(cls, dev_sg=None):
        """
        author: yibo.gao
        date: 2021.05.18
        description: 读取nvdata默认的配置文件
        :param dev_sg: 根据sg确定设备类型,exp or switch
        :return: 文件对象
        """
        # todo 待完成
        # host_ip = CommandLineArgsParse.get_host_ip()
        # 本地保存 exp.csv，在脚本的 expander/nvdata/  目录下
        local_path = os.path.join(EXP_NVDATA_CONF_PATH,
                                  EXP_NVDATA_CONF_SOURCE_XML_FILE)

        # exp.xml 放在 /root/ps3test/upgrade_test/cfgXml/exp.xml
        rmt_path = "{}/{}/{}".format(RMT_DIR_PATH, EXP_XML_DIR_NAME,
                                     EXP_NVDATA_CONF_SOURCE_XML_FILE)
        # status = CliUtils.scp_remote_to_local(local_path, rmt_path, host_ip)
        # if RtnStatusEnum.SUCCESS.value != status:
        #     log.error("nvdata配置文件下载失败")
        #     return None
        log.info("nvdata配置文件下载成功")
        tree = ET()
        tree.parse(local_path)
        return tree

    @classmethod
    def change_vm_nic_pci(cls, vm_name: str, vf_nic_bdf: str, domain_id: str,
                       cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        KVM虚拟机中添加PCI设备
        """
        # todo 待完成
        # csv_module = cls.target_module.MODULE.value
        # csv_submodule = cls.target_submodule
        # csv_filed = cls.target_field
        # csv_desclen = cls.tagert_desclen
        # 准备测试数据
        # test_list = [[csv_module, csv_submodule, csv_filed, cls.change_value],
        #              [csv_module, csv_submodule, csv_desclen, cls.change_value_len]]
        # # 准备测试数据
        # test_list = [[csv_module, csv_submodule, csv_filed, cls.change_value],
        #              [csv_module, csv_submodule, csv_desclen, cls.change_value_len]]
        # 1.获取原始nvdata list
        # origin_nvdata_list = cls.read_source_config_file()
        # 2.根据change_list，准备修改数据
        # change_nvdata_list = test_list
        # 3.对原始nvdata_list，根据change_list 进行修改
        # new_nvdata_list = cls.change_nvdata_list_value(origin_nvdata_list, change_nvdata_list,
        #                                                       caller_class=cls)
        # if new_nvdata_list == RtnStatusEnum.FAIL.value:
        #     log.error("修改csv文件失败，请检查数据是否有问题！")
        # 4.生成新的xml文件
        # update_code, dir_path = cls.update_nvdata_config(cls.target_dev_sn, new_nvdata_list,
        #                                                         need_return_path=True, return_new_sg_flag=True)

    @classmethod
    def crate_pci_xml(cls, vf_nic_bdf, cmd_execute_address = CmdExecuteAdressEnum.SERVER.value):
        """
        author： weiyun1
        description: 创建pci地址的xml文件
        :param vf_nic_bdf:网卡的bpf地址，可根据ethtool -i ethx中获取
        :param cmd_execute_address: 执行端
        :return:
        """
        domain = vf_nic_bdf.split(":")[0]
        bus = vf_nic_bdf.split(":")[1]
        slot, function = vf_nic_bdf.split(":")[-1].split(".")
        # 创建根元素 hostdev
        hostdev = ET.Element('hostdev', mode='subsystem', type='pci', managed='yes')
        # 创建 source 子元素
        source = ET.SubElement(hostdev, 'source')
        # model = ET.SubElement(hostdev, "model")
        address = ET.SubElement(source, 'address', domain="0x" + domain, bus="0x" + bus,
                                slot="0x" + slot, function="0x" + function)
        # ET.SubElement(hostdev, 'model', type='virtio')
        tree = ET.ElementTree(hostdev)
        # xml_string = ET.tostring(hostdev, encoding='utf-8').decode('utf-8')
        # print(xml_string)
        # ET.indent(tree)
        current_path = os.path.abspath(os.path.dirname(__file__))
        root_path = os.path.dirname(current_path)
        if "scripts" == os.path.basename(root_path):
            sys.path.append(root_path)
        elif root_path == "/":
            raise ValueError
        else:
            root_path = os.path.dirname(root_path)
            sys.path.append(root_path)
        local_file_save_path = os.path.join(root_path, constants.FILE_TEMP_PATH_NAME)
        server_ip, client_ip = CommandOperation.get_logical_ip_form_config()
        if cmd_execute_address == CmdExecuteAdressEnum.SERVER.value:
            ssh_ip = server_ip
        else:
            ssh_ip = client_ip
        file_name = f"{bus}_{slot}_{function}.xml"
        vm_pci_xml = os.path.join(local_file_save_path, file_name)
        remote_address = "/tmp/"
        remote_pci_xml = os.path.join("/tmp/", file_name)
        tree.write(vm_pci_xml, encoding="utf-8", xml_declaration=True)

        scp_file_cmd = f"scp -P {ssh_port} {vm_pci_xml} root@{ssh_ip}:{remote_address}"
        rtn_code, output, stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=scp_file_cmd,
            local_execute_flag=True
        )
        log.info(f"返回值为{str(rtn_code)}, output:{output}, error:{stderr}")
        log.info("xml文件传输成功，文件路径为：{}".format(cls.remote_pci_xml))
        return remote_pci_xml

    @classmethod
    def add_vm_nic_pci(cls, vm_name: str, vf_nic_bdf: str,
                       cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                       vm_manager_ip: str = None,
                       driver_name: str = constants.DRV_SCGBE_VF
                       ):
        """
        KVM虚拟机中添加PCI设备
        """
        from scripts.script_libs.ifconfig import IfConfig
        rtn_code = RtnStatusEnum.SUCCESS.value

        def get_vm_status():
            log.info(f"获取vm虚拟机初始化状态")
            cmd = f"virsh domstate {vm_name}"
            status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=cmd_execute_address)
            log.info("status:{}, out:{}".format(status, out))
            if RtnStatusEnum.SUCCESS.value == status:
                running_state = out.strip()
            else:
                log.error("命令执行失败!")
                running_state = ""
            if running_state != "running":
                log.error(f"虚拟机{vm_name}未启动")
                return False
            else:
                log.error(f"虚拟机{vm_name}启动")
                return True
        # 0000:4b:00.0

        remote_pci_xml = cls.crate_pci_xml(vf_nic_bdf=vf_nic_bdf, cmd_execute_address=cmd_execute_address)
        vm_status = get_vm_status()
        if not vm_status:
            status = cls.start_vm(vm_name=vm_name, execute_address=cmd_execute_address)
            if status:
                exec_cmd = f"virsh attach-device {vm_name} {remote_pci_xml} --live --config"
                rtn_code, rtn_out, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_cmd, cmd_execute_address=cmd_execute_address)
        else:
            exec_cmd = f"virsh attach-device {vm_name} {remote_pci_xml} --live --config"
            rtn_code, rtn_out, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_cmd, cmd_execute_address=cmd_execute_address)
        time.sleep(5)
        if not vm_manager_ip or "192.192.168" in vm_manager_ip:
            vm_manager_ip = cls.get_vm_interface(vm_name=vm_name, execute_address=cmd_execute_address)
        before_nic_interface = IfConfig.get_all_nic_name(cmd_execute_address=cmd_execute_address, ssh_ip=vm_manager_ip)
        stdout = ""
        if driver_name in ["sxe2vf", "scgbevf", "sxe2"]:
            rtn_code, stdout, stderr = CommandOperation.execute_command_with_error(
                cmd="lspci|grep '1ff2'", cmd_execute_address=cmd_execute_address,  ssh_ip=vm_manager_ip,
                host_os_client="linux")
        elif "iavf" in driver_name:
            rtn_code, stdout, stderr = CommandOperation.execute_command_with_error(
                cmd="lspci|grep ' Intel Corporation Ethernet Adaptive Virtual Function'",
                cmd_execute_address=cmd_execute_address, ssh_ip=vm_manager_ip,
                host_os_client="linux")
        aux_scp = f"scp -P {ssh_port} /root/sxe2_auxiliary.ko {vm_manager_ip}:/root/"
        CommandOperation.execute_command_with_error(cmd=aux_scp,cmd_execute_address=cmd_execute_address)
        scp_command = \
            (f"scp -P {ssh_port} /root/{driver_name}.ko "
             f"{vm_manager_ip}:/root/")
        scp_rtn_code, *_ = CommandOperation.execute_command_with_error(cmd=scp_command,
                                                                   cmd_execute_address=cmd_execute_address)
        if scp_rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f"将驱动文件：{driver_name}拷贝到{vm_manager_ip}成功")
        else:
            log.info(f"将驱动文件：{driver_name}拷贝到{vm_manager_ip}失败")
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f"设备存在,信息为{stdout}")
            rtn_code = cls.check_driver_exist(driver_name=driver_name, ssh_ip=vm_manager_ip, execute_operation="modprobe")
            log.info(stdout)
        else:
            rtn_code = RtnStatusEnum.FAIL.value
        test_device_list = []

        return rtn_code, remote_pci_xml, test_device_list

    @classmethod
    def get_vm_sriov_device(cls, driver_name: str, cmd_execute_address: str, ssh_ip: str):

        from scripts.script_libs.ifconfig import IfConfig
        from scripts.script_libs.ethtool_operation import EthtoolOperation
        nic_interface, test_device_list = [], []
        aux_scp = f"scp -P {ssh_port} /root/sxe2_auxiliary.ko {ssh_ip}:/root/"
        rtn_code, *_ = CommandOperation.execute_command_with_error(cmd=aux_scp,
                                                                   cmd_execute_address=cmd_execute_address)
        scp_command = f"scp -P {ssh_port} /root/{driver_name}.ko {ssh_ip}:/root/"
        rtn_code, *_ = CommandOperation.execute_command_with_error(cmd=scp_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f"将驱动文件：{driver_name}拷贝到{ssh_ip}成功")
        else:
            log.info(f"将驱动文件：{driver_name}拷贝到{ssh_ip}失败")
        rtn_code = cls.check_driver_exist(driver_name, ssh_ip, "modprobe")
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            nic_interface = IfConfig.get_all_nic_name(cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
            nic_interface = [index for index in nic_interface if "lo" not in index]
        for device in nic_interface:
            current_driver_name = EthtoolOperation.show_driver_infomation(
                device_name=device, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)["driver"]
            if driver_name.lower() == current_driver_name.lower():
                test_device_list.append(device)
        return test_device_list

    @classmethod
    def check_driver_exist(cls, driver_name: str, ssh_ip: str, execute_operation: str):
        driver = driver_name.split(".")[0]
        rtn_stdcode = RtnStatusEnum.SUCCESS.value
        rtn_code, *_ = CommandOperation.execute_command_with_error(cmd=f"lsmod|grep {driver}", ssh_ip=ssh_ip)
        if rtn_code != RtnStatusEnum.SUCCESS.value and execute_operation == "modprobe":
            log.info(f"加载驱动：{driver_name}")
            CommandOperation.execute_command_with_error(cmd=f"insmod /root/sxe2_auxiliary.ko",
                                                        ssh_ip=ssh_ip)
            rtn_code, *_ = CommandOperation.execute_command_with_error(cmd=f"insmod /root/{driver_name}.ko",
                                                                       ssh_ip=ssh_ip)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f"insmod {driver_name} successed")
            else:
                log.error(f"insmod {driver_name} failed")
                rtn_stdcode = RtnStatusEnum.FAIL.value
        elif rtn_code == RtnStatusEnum.SUCCESS.value and execute_operation == "rmmod":
            rtn_code, *_ = CommandOperation.execute_command_with_error(cmd=f"rmmod {driver}",
                                                                       ssh_ip=ssh_ip)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f"rmmod {driver_name} successed")
            else:
                log.error(f"rmmod {driver_name} failed")
                rtn_stdcode = RtnStatusEnum.FAIL.value
        return rtn_stdcode

    @classmethod
    def remove_vm_nic_pci(cls, vm_name: str, vf_nic_bdf: str = None, remote_pci_xml: str = None,
                       cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        KVM虚拟机中添加PCI设备
        """
        exec_command = f"ls -l {remote_pci_xml}"
        rtn_code, rtn_out, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            remote_pci_xml = cls.crate_pci_xml(vf_nic_bdf=vf_nic_bdf, cmd_execute_address=cmd_execute_address)
        exec_command = f"virsh detach-device {vm_name} {remote_pci_xml} --config --live"
        rtn_code, rtn_out, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        return rtn_code

    @classmethod
    def check_vm_bond_dev_exist(cls, vm_name: str, host_dev_name: str,
                                cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        检查KVM虚拟机中是否存在指定PCI设备
        """
        return RtnStatusEnum.SUCCESS.value

    @classmethod
    def add_vm_bond_dev(cls, vm_name: str, host_dev_name: str,
                       cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        KVM虚拟机中添加虚拟NIC设备并绑定
        """
        return RtnStatusEnum.SUCCESS.value

    @classmethod
    def wait_vm_init_complete(cls, vm_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: xiangyu.liu
        date: 2023.11.21
        description: 等待虚拟机完成初始化
        """
        log.info(f"获取vm虚拟机初始化状态")
        cmd = f"virsh domstate {vm_name}"
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=execute_address)
        log.info("status:{}, out:{}".format(status, out))
        if RtnStatusEnum.SUCCESS.value == status:
            running_state = out.strip()
        else:
            log.error("命令执行失败!")
            running_state = ""
        if running_state != "running":
            log.error(f"虚拟机{vm_name}未启动")
            return False

        # 虚拟机Running状态下，等待初始化完成
        retry_max = 60
        retry_count = 0
        retry_interval_s = 5
        retry_flag = False
        # vm_ip = CommonOperation.get_win_vm_ip(execute_address, vm_name)
        net_local_ip = cls.get_vm_interface(vm_name, execute_address)
        if not net_local_ip:
            log.error(f"获取虚拟机{vm_name}本地ip失败")
            return False
        cmd = f'ping {net_local_ip} -c 1 -W 1'
        while retry_count < retry_max:
            status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=execute_address)
            log.info("status:{}, result:{}".format(status, out))
            # ping成功
            if status == RtnStatusEnum.SUCCESS.value:
                retry_flag = True
                break
            time.sleep(retry_interval_s)
            retry_count += 1
        if retry_flag:
            if retry_count > 0:
                time.sleep(10)
            log.info(f"虚拟机{vm_name}初始化完成")
            return True
        else:
            log.error(f"在{retry_max * retry_interval_s}s内，虚拟机{vm_name}没有完成初始化")
            return False

    @classmethod
    def wait_vm_stop_complete(cls, vm_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: xiangyu.liu
        date: 2023.11.21
        description: 等待虚拟机完成初始化
        """
        log.info(f"获取vm虚拟机停止状态")
        cmd = f"virsh domstate {vm_name}"

        # 虚拟机等待shut off
        retry_max = 60
        retry_count = 0
        retry_interval_s = 2
        retry_flag = False
        while retry_count < retry_max:
            status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=execute_address)
            log.info("status:{}, result:{}".format(status, out))
            if out.strip() == "shut off":
                retry_flag = True
                break
            elif out.strip() == "关闭":
                retry_flag = True
                break
            time.sleep(retry_interval_s)
            retry_count += 1
        if retry_flag:
            log.info(f"虚拟机{vm_name} shut off")
            return True
        else:
            log.error(f"在{retry_max * retry_interval_s}s内，虚拟机{vm_name}没有shut off")
            return False

    @classmethod
    def start_dct_vm(cls, vm_name: str = VM_NAME_DEF, execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        description: 只获取虚机的状态
        :param vm_name:
        :param execute_address:
        :return:
        """
        cmd = "virsh start '{}'".format(vm_name)
        status, out, err = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_address)
        log.info("status:{}, out:{}".format(status, out))
        if RtnStatusEnum.SUCCESS.value == status:
            time.sleep(10)
            if 'running' != cls.check_vm_state(vm_name, execute_address):
                log.error('打开虚拟机命令执行成功，但是检查失败')
                return False
            else:
                return  True
        else:
            rtn_status = cls.check_vm_state(vm_name=vm_name, cmd_execute_address=execute_address)
            if 'running' == rtn_status:
                return True
            else:
                return False

    @classmethod
    def start_vm(cls, vm_name: str = VM_NAME_DEF, execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: xiangyu.liu
        date: 2023.11.04
        description: 启动vm
        """
        retry_max = 60
        retry_count = 0
        retry_interval_s = 5
        retry_flag = False
        status = RtnStatusEnum.FAIL.value
        rtn_status = cls.check_vm_state(vm_name=vm_name, cmd_execute_address=execute_address)
        if 'running' != rtn_status:
            cmd = "virsh start '{}'".format(vm_name)
            status, out, err = CommandOperation.execute_command_multi_times(
                cmd=cmd, cmd_execute_address=execute_address)
            log.info("status:{}, out:{}".format(status, out))
        else:
            status = RtnStatusEnum.SUCCESS.value
        if RtnStatusEnum.SUCCESS.value == status :
            time.sleep(10)
            if 'running' != cls.check_vm_state(vm_name, execute_address):
                log.error('打开虚拟机命令执行成功，但是检查失败')
                status = RtnStatusEnum.FAIL.value
                return False

            # 虚拟机Running状态下，等待初始化完成
            net_local_ip = cls.get_vm_local_net_ip(vm_name, execute_address)

            if not net_local_ip or "192.168" in net_local_ip:
                net_local_ip = cls.get_vm_interface(vm_name=vm_name, execute_address=execute_address)
                if not net_local_ip:
                    log.error(f"获取虚拟机{vm_name}本地ip失败")
                    return False
            cmd = f'ping {net_local_ip} -c 1 -W 1'
            while retry_count < retry_max:
                status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, cmd_execute_address=execute_address)
                log.info("status:{}, result:{}".format(out, err))
                # ping成功
                if status == RtnStatusEnum.SUCCESS.value:
                    retry_flag = True
                    break
                time.sleep(retry_interval_s)
                retry_count += 1
            if retry_flag:
                if retry_count > 0:
                    time.sleep(10)
                log.info(f"虚拟机{vm_name}初始化完成")
                return True
            else:
                log.error(f"在{retry_max * retry_interval_s}s内，虚拟机{vm_name}没有完成初始化")
                return False
        else:
            return  False
        # status = RtnStatusEnum.SUCCESS.value if retry_flag == status == RtnStatusEnum.SUCCESS.value \
        #     else RtnStatusEnum.FAIL.value
        # return cmd, status, out, err

    @classmethod
    def stop_vm(cls, vm_name: str = VM_NAME_DEF, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                force: bool = True) -> int:
        """
        author:      xiangyu.liu
        date:        2023-11-25 16:52:12
        description: 关闭虚拟机
        :param vm_name: 虚拟机name
        :param execute_address: 命令执行地址信息
        :return:     None
        """
        if not force:
            stop_cmd = f"virsh shutdown {vm_name}"
        else:
            stop_cmd = f"virsh destroy {vm_name}"

        # 查看当前环境中的vm状态
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
            cmd=stop_cmd, cmd_execute_address=execute_address)
        log.info("cmd_code:{}\ncmd_stdout:{}".format(cmd_code, cmd_stdout, cmd_stderr))
        if RtnStatusEnum.SUCCESS.value == cmd_code:
            status = cls.wait_vm_stop_complete(vm_name=vm_name, execute_address=execute_address)
            if not status:
                log.error(f"虚拟机{vm_name} shutdown失败")
                log.info(f"虚拟机{vm_name} ，尝试强制关闭")
                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                    cmd=f"virsh destroy {vm_name}", cmd_execute_address=execute_address)
                status = cls.wait_vm_stop_complete(vm_name=vm_name, execute_address=execute_address)
                if not status:
                    log.error(f"虚拟机{vm_name} destroy失败")
                    rtn_code = RtnStatusEnum.FAIL.value
                else:
                    log.info(f"虚拟机{vm_name} destroy成功")
                    rtn_code = RtnStatusEnum.SUCCESS.value
            else:
                log.info(f"虚拟机{vm_name} shutdown成功")
                rtn_code = RtnStatusEnum.SUCCESS.value
        else:
            log.error('关闭虚拟机命令执行失败')
            rtn_code = RtnStatusEnum.FAIL.value
        return rtn_code

    # @classmethod
    # def set_vf_vlan(cls, vf_name: str, vlan_id: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value):
    #     """
    #     author: xiangyu.liu
    #     date: 2023.11.04
    #     description: 启动vm
    #     """
    #     state = RtnStatusEnum.FAIL.value
    #     pf_name, vf_id = vf_name.split("v")
    #     cmd = f"ip link set {pf_name} vf {vf_id} vlan {vlan_id}"
    #     status, out, err = CommandOperation.execute_command_multi_times(
    #         cmd=cmd, cmd_execute_address=execute_address)
    #     log.info("status:{}, out:{}".format(status, out))
    #     if RtnStatusEnum.SUCCESS.value == status:
    #         log.info(f"设置{vf_name} vlan为{vlan_id}成功")
    #         state = RtnStatusEnum.SUCCESS.value
    #     return state

    @classmethod
    def generate_ipv6_header(cls, pf_device_name: str, target_device_type, cmd_execute_address: str) -> str:
        from scripts.script_libs.ifconfig import IfConfig
        pf_device_ip = IfConfig.get_device_ipv6_addr(device_name=pf_device_name,
                                                     cmd_execute_address=cmd_execute_address)
        if pf_device_ip:
            temp_list = pf_device_ip.split(':')
            diff_base = 0x1000
            if target_device_type == TestObjectType.VF.value:
                diff = diff_base
            elif target_device_type == TestObjectType.VLAN.value:
                diff = diff_base + 1
            elif target_device_type == TestObjectType.MACVLAN.value:
                diff = diff_base + 2
            elif target_device_type == TestObjectType.VFVLAN.value:
                diff = diff_base + 3
            elif target_device_type == TestObjectType.VFMACVLAN.value:
                diff = diff_base + 4
            elif target_device_type == TestObjectType.DEGVMQ.value:
                diff = diff_base + 5
            elif target_device_type == TestObjectType.VFVMQ.value:
                diff = diff_base + 6
            elif target_device_type == TestObjectType.VFVMQVLAN.value:
                diff = diff_base + 7
            else:
                diff = diff_base + 8
            temp_list[-2] = "{:04x}".format(diff)
            ip_header = ':'.join(temp_list[:-1]) + ':'
        else:
            ip_header = "fe80::0000:0000:0000:"
            log.warning("当前未获取到ipv6地址，给默认值：{}，仅仅是为了不报异常。".format(ip_header))
        return ip_header

    @classmethod
    def generate_ip_header(cls, pf_device_name: str, target_device_type, cmd_execute_address: str) -> str:
        from scripts.script_libs.ifconfig import IfConfig
        pf_device_ip = IfConfig.get_device_ipv4_addr(device_name=pf_device_name,
                                                     cmd_execute_address=cmd_execute_address)
        temp_list = pf_device_ip.split('.')
        diff_base = 100
        if target_device_type == TestObjectType.VF.value:
            diff = diff_base
        elif target_device_type == TestObjectType.VLAN.value:
            diff = diff_base + 1
        elif target_device_type == TestObjectType.MACVLAN.value:
            diff = diff_base + 2
        elif target_device_type == TestObjectType.VFVLAN.value:
            diff = diff_base + 3
        elif target_device_type == TestObjectType.VFMACVLAN.value:
            diff = diff_base + 4
        elif target_device_type == TestObjectType.DEGVMQ.value:
            diff = diff_base + 5
        elif target_device_type == TestObjectType.VFVMQ.value:
            diff = diff_base + 6
        elif target_device_type == TestObjectType.VFVMQVLAN.value:
            diff = diff_base + 7
        else:
            diff = diff_base + 8
        temp_list[2] = str(int(temp_list[2]) + diff)
        ip_header = '.'.join(temp_list[:-1]) + '.'
        return ip_header

    @classmethod
    def flush_dev_ip(cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        """
        :param device_name:网卡名称
        :param cmd_execute_address: 执行端
        :return:
        """
        # 清空网卡缓存
        execute_command = constants.STR_SPACE.join([constants.IP, constants.ADDRESS, constants.FLUSH,
                                                    constants.DEV, device_name])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            execute_command, cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info('清空临时ip地址成功')
            rtn_status = True
        else:
            log.info(f'command:{execute_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            rtn_status = False
        execute_down_command = constants.STR_SPACE.join([constants.IFDOWN, device_name])
        code_code, code_outputs, code_err = CommandOperation.execute_command_with_error(
            execute_down_command, cmd_execute_address)
        execute_command = constants.STR_SPACE.join([constants.IFUP, device_name])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            execute_command, cmd_execute_address)
        if rtn_code == code_code == RtnStatusEnum.SUCCESS.value:
            log.info('加载ip成功')
            cmd_status = True
        else:
            log.info(f'command:{execute_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            cmd_status = False
        return cmd_status and rtn_status

    @classmethod
    def get_runnig_vm(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2024.01.16
        description: 获取所有运行的虚机
        :param cmd_execute_address:
        :return:
        """
        vm_list = cls.get_vm(cmd_execute_address=cmd_execute_address)
        running_vm_list = [index for index in vm_list if cls.check_vm_state(index, cmd_execute_address) == "running"]
        return running_vm_list

    @classmethod
    def set_vf_vlan(cls, vlan_id: str, vf_name: str = "", pf_name: str = "", vf_id: str = "",
                    cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2024.01.16
        description: 获取所有运行的虚机
        :param cmd_execute_address:
        :return:
        """
        rtn_state = RtnStatusEnum.FAIL.value
        if vf_name:
            pf_name, vf_id = vf_name.split("v")
        elif pf_name and vf_id:
            pass
        else:
            log.error("未指定vf_name或（pf_name、vf_id）,请检查")
            return rtn_state, "", ""

        cmd = f"ip link set {pf_name} vf {vf_id} vlan {vlan_id}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address)
        return rtn_code, rtn_outputs, rtn_err

    @classmethod
    def get_vf_vlan(cls, vf_name: str = "", pf_name: str = "", vf_id: str = "", get_bdf: bool = True,
                    cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2024.01.16
        description: 获取所有运行的虚机
        :param cmd_execute_address:
        :return:
        """
        rtn_state = RtnStatusEnum.FAIL.value
        if vf_name:
            pf_name, vf_id = vf_name.split("v")
        elif pf_name and vf_id:
            pass
        else:
            log.error("未指定vf_name或（pf_name、vf_id）,请检查")
            return rtn_state, "", ""

        vf_prop = cls.get_vf_prop_of_nic(pf_name, cmd_execute_address=cmd_execute_address, get_bdf=get_bdf)
        return vf_prop[vf_id]["vlan"]

    # todo 以下暂未适配linux KVM windows
    @classmethod
    def clean_hidden_machine(cls, vm_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        清除虚机中所有的隐藏设备
        """
        log.info("清理所有的隐藏设备")
        exec_command = \
            "(Get-PnpDevice | Where-Object {$_.Status -eq 'Unknown'}).InstanceId|ForEach-Object { & 'devcon.exe' " \
            "remove '@$_' } "
        clean_hidden_cmd = CommandOperation.concat_invoke_command(
            vm_name=vm_name, cmd=exec_command)
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=clean_hidden_cmd, cmd_execute_address=cmd_execute_address)
        str_count = cmd_stdout.count("No devices were removed.")
        # 相同打印过多时，合并，并打印数量
        if str_count > 5:
            cmd_newout = cmd_stdout.replace("No devices were removed.", "")
            while "\n\n" in cmd_newout:
                cmd_newout = cmd_newout.replace("\n\n", "\n")
            while "\t\t" in cmd_newout:
                cmd_newout = cmd_newout.replace("\t\t", "\t")
            log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\n{} No devices were removed.\nCmd Stderr:\n{}'.format(
                clean_hidden_cmd, cmd_code, cmd_newout.strip(), str_count, cmd_stderr))
        else:
            log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                clean_hidden_cmd, cmd_code, cmd_stdout, cmd_stderr))

    @classmethod
    def create_directory(cls, vm_name, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                         virtual_system: str = "windows"):
        """
        author: wei.yuan1
        date: 2023.11.28
        description: 创建文件并进行拷贝
        """
        exist_path = "Test-Path 'D:'"
        code, stdout, stderr = CommandOperation.execute_command_with_error(
            cmd=exist_path, cmd_execute_address=execute_address)
        log.info("code:{}\nstdout:{}\nstderr:{}".format(code, stdout, stderr))
        if virtual_system == "windows":
            if int(code) == RtnStatusEnum.SUCCESS.value:
                dest_directory = f"D:\\Users\\Administrator\\{vm_name}\\"
            else:
                dest_directory = f"C:\\Users\\Administrator\\{vm_name}\\"
        else:
            if int(code) == RtnStatusEnum.SUCCESS.value:
                dest_directory = f"D:\\Users\\Administrator_centos\\{vm_name}\\"
            else:
                dest_directory = f"C:\\Users\\Administrator_centos\\{vm_name}\\"
        new_directory = f"New-Item -ItemType Directory -Path {dest_directory} -Force"
        CommonOperation.concat_test_steps(f"创建文件夹：{dest_directory}")
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=new_directory, cmd_execute_address=execute_address)
        log.info("cmd_code:{}\ncmd_stdout:{}\ncmd_stderr:{}".format(cmd_code, cmd_stdout, cmd_stderr))
        if virtual_system == "windows":
            source_diectory = "C:\\Users\\Administrator\\sxevm002-export\\sxevm002\\sxevm002\\*"
        else:
            source_diectory = "C:\\Users\\Administrator\\sxevm-centos\\*"
        copy_command = f"Copy-Item -Path {source_diectory} -Destination {dest_directory} -Recurse -Force"
        CommonOperation.concat_test_steps(f"拷贝系统镜像源命令为：{copy_command}")
        copy_cmd_code, copy_stdout, copy_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=copy_command, cmd_execute_address=execute_address)
        log.info("cmd_code:{}\ncmd_stdout:{}\ncmd_stderr:{}".format(cmd_code, cmd_stdout, cmd_stderr))
        if cmd_code == RtnStatusEnum.FAIL.value or copy_cmd_code == RtnStatusEnum.FAIL.value:
            log.error_caller("磁盘容量不足，程序退出")
            exit(ExitCodeEnum.EXIT_SKIP.value)
        if virtual_system == "windows":
            return f"{dest_directory}\\Virtual Hard Disks\\002.vhdx"
        else:
            return f"{dest_directory}\\sxevm-centos.vhdx"

    @classmethod
    def clean_all_vm(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        :param cmd_execute_address: 执行端
        :return:
        """
        CommonOperation.concat_test_steps(step_info="清除所有的虛機環境")
        vm_list = cls.get_vm(cmd_execute_address=cmd_execute_address)
        active_vm_list = cls.get_runnig_vm(cmd_execute_address=cmd_execute_address)
        for vm_name in active_vm_list:
            cls.stop_vm(vm_name=vm_name, execute_address=cmd_execute_address)
        time.sleep(5)
        for vm_name in vm_list:
            log.info("删除网卡的挂载镜像")
            exec_command = f"Get-VM -Name {vm_name} | Get-VMHardDiskDrive | Remove-Item -Force"
            log.info_caller(f"执行命令：{exec_command}")
            cmd_code, exec_stdout, exec_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=cmd_execute_address)
            log.info_caller(f"删除网卡的信息的结果为：{exec_stdout}\n\n, 错误信息为{exec_stderr}\n")
            cls.delete_all_vmadapter(vm_name=vm_name, cmd_execute_address=cmd_execute_address)
            cls.remove_vm(vm_name=vm_name, cmd_execute_address=cmd_execute_address)

    @classmethod
    def remove_vm(cls, vm_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2024.01.16
        description: 删除虚机
        :param vm_name:
        :param cmd_execute_address:
        :return:
        """
        log.info(f"删除虚机{vm_name}")
        remove_command = f"Remove-VM -Name {vm_name} -Force"
        log.info_caller(f"执行命令：{remove_command}")
        cmd_code, exec_stdout, exec_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=remove_command, cmd_execute_address=cmd_execute_address)
        log.info_caller(f"删除网卡的信息的结果为：{exec_stdout}\n\n, 错误信息为{exec_stderr}\n")

    @classmethod
    def create_vm(cls, count: int, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                  virtual_system: str = "windows", exist_vm_list: list = []):
        """
        author: xiangyu.liu
        date: 2023.11.21
        description: 创建vm虚拟机器
        return: 新创建的虚拟机名称
        """
        # 查找vm机器名称是否被占用
        vm_prefix = "sxevm"
        vm_list_num = [re.sub(r"\D", "", index) for index in exist_vm_list]
        try:
            max_num = max(vm_list_num, key=str)
        except Exception as e:
            max_num = 0
            log.info(f"当前环境中没有虚机,{e}")
        # 当前环境中添加虚拟机，并配置镜像文件
        if max_num == 0:
            log.error("请手动创建虚拟机sxevm001")
            new_vm_list = []
        else:
            log.info(f"当前环境存在虚拟机")
            new_vm_list = []
        return new_vm_list

    @classmethod
    def delete_all_vmadapter(cls, vm_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2024.01.12
        description: 删除虚机中所有的网络适配器
        :param vm_name:
        :param cmd_execute_address:
        :return:
        """
        log.info(f"获取虚机中的虚拟网络适配器的数量，如果不等于0，则删除{vm_name}中的网络适配器")
        get_netadapter_command = f"(Get-VMNetworkAdapter -VMName {vm_name}).count"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=get_netadapter_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_stdout = rtn_stdout.replace("\r", "")
            vm_adapter_num = int(re.sub(r"\s+", "", rtn_stdout)) if re.sub(r"\s+", "", rtn_stdout).isdigit() else 0
            if vm_adapter_num != 0:
                remove_netadapter = \
                    f" Get-VMNetworkAdapter -VMName '{vm_name}'| Remove-VMNetworkAdapter -Confirm:$false"
                CommandOperation.execute_command_with_error(
                    cmd=remove_netadapter, cmd_execute_address=cmd_execute_address)

    @classmethod
    def rename_vm(cls, old_name: str, new_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: xiangyu.liu
        date: 2023.11.21
        description: 重命名vm虚拟机器
        """
        log.info(f"重命名vm虚拟机：{old_name} -> {new_name}")
        cmd = f"Set-VM -Name \'{old_name}\' -NewVmName \'{new_name}\'"
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=cmd_execute_address)
        log.info("status:{}, out:{}, err:{}".format(status, out, err))
        if not status:
            return old_name
        else:
            return new_name

    @classmethod
    def get_vm_running_state(cls, vm_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: xiangyu.liu
        date: 2023.11.21
        description: 重命名vm虚拟机器
        """
        log.info(f"获取vm虚拟机运行状态")
        cmd = f"Get-VM -name \'{vm_name}\'|select -Property State|fl"
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=execute_address)
        log.info("status:{}, out:{}".format(status, out))
        if not status:
            running_state = out.strip().split(":")[1].strip()
        else:
            log.error("命令执行失败!")
            running_state = ""
        return running_state

    @classmethod
    def copy_file_from_pf_to_vf(cls, vm_name: str, source_file_path: str, dest_file_path: str,
                                cmd_exec_address: str = CmdExecuteAdressEnum.CLIENT.value) -> int:
        """
        author:      haibin.xu
        date:        2023-12-19 13:56:03
        description: 从物理机（测试机）侧拷贝文件到虚拟机侧32

        :param vm_name:
        :param source_file_path:
        :param dest_file_path:
        :return:
        """
        copy_cmd = ("Copy-Item -Path '{}' -Destination '{}' -ToSession (New-PSSession -VMName '{}' -Credential "
                    "$credential)").format(source_file_path, dest_file_path, vm_name)
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=copy_cmd, cmd_execute_address=cmd_exec_address)
        log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            copy_cmd, cmd_code, cmd_stdout, cmd_stderr))

        return cmd_code

    @classmethod
    def send_packet(cls, count, rx_device_ip: str, tx_device_ip: str, mtu_size: str = '1500',
                    ssh_ip: str = None,
                    subcontract: bool = False, timeout: int = None, exec_host_os: str = "linux",
                    cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, ping_packet_len: int = None,
                    tx_device_name: str = '', ip_type: str = "ipv4"):
        """
        author: wei.yuan1
        date: 2025.06.20
        description: 发送包
        Args:
            exec_host_os: exec host os system
            count: send packet numbers
            rx_device_ip: receive points ip address
            tx_device_ip:send points interface address
            mtu_size: interface jumbo packet size
            subcontract:是否需要拆分包
        """
        frame_len = 0
        if subcontract:
            frame_len = int(mtu_size) * 2
        else:
            if ip_type == "ipv4":
                frame_len = int(mtu_size) - 46
            else:
                frame_len = int(mtu_size) - 100

        if ping_packet_len == 0:
            frame_len = 64
        elif ping_packet_len is not None:
            frame_len = ping_packet_len

        time_para = f' -t {timeout}' if timeout is not None else ''

        if exec_host_os == 'windows':
            if subcontract:
                ping_cmd = f'ping {rx_device_ip} -n {count} -l {frame_len} -S {tx_device_ip}'
            else:
                ping_cmd = f'ping {rx_device_ip} -n {count} -l {frame_len} -S {tx_device_ip} -f'
        else:
            if ip_type == "ipv4":
                if subcontract:
                    if not tx_device_name:
                        ping_cmd = f'ping -f {rx_device_ip} -c {count} -s {frame_len} -I {tx_device_ip}'
                    else:
                        ping_cmd = f'ping -f {rx_device_ip} -c {count} -s {frame_len} -I {tx_device_name}'
                else:
                    if not tx_device_name:
                        ping_cmd = f'ping {rx_device_ip} -c {count} -s {frame_len} -I {tx_device_ip} -M do'
                    else:
                        ping_cmd = f'ping {rx_device_ip} -c {count} -s {frame_len} -I {tx_device_name} -M do'
            else:
                if subcontract:
                    if not tx_device_name:
                        ping_cmd = f'ping -6 {rx_device_ip} -c {count} -s {frame_len} -I {tx_device_ip}'
                    else:
                        ping_cmd = f'ping -6 {rx_device_ip} -c {count} -s {frame_len} -I {tx_device_name}'
                else:
                    if not tx_device_name:
                        ping_cmd = f'ping -6 {rx_device_ip} -c {count} -s {frame_len} -I {tx_device_ip} -M do'
                    else:
                        ping_cmd = f'ping -6 {rx_device_ip} -c {count} -s {frame_len} -I {tx_device_name} -M do'

        ping_cmd += time_para
        rtn_code, rtn_outputs, _ = \
            CommandOperation.execute_command_with_error(
                ping_cmd, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(rtn_outputs)
            try:
                pattrn = r"(\d+) packets transmitted.*?(\d+) received.*?(\d+(?:\.\d+)?)% packet loss.*?"
                matches = re.search(pattrn, rtn_outputs)
                if int(float(matches[3])) > 80:
                    rtn_code = RtnStatusEnum.FAIL.value
            except Exception as e:
                pattrn = r"已发送.*?(\d+) 个包.*?(\d+) 个包.*?(\d+(?:\.\d+)?)% packet loss.*?"
                matches = re.search(pattrn, rtn_outputs)
                if int(matches[3]) > 80:
                    rtn_code = RtnStatusEnum.FAIL.value
        else:
            log.error(rtn_outputs)
            rtn_code = RtnStatusEnum.FAIL.value
        return rtn_code


class VirshMigrate(object):
    def __init__(self, vm_name: str, migrate_type: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                 dct_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, dct_ssh_ip: str = None,
                 dct_exec_device: str = None
                 ):
        """
        description: 进行虚机的迁移操作
        :param vm_name:
        :param migrate_type: cool_migrate 静态迁移、 hot_migrate 动态迁移
        """
        self.vm_name = vm_name
        self.migrate = migrate_type
        self.cmd_execute_address = cmd_execute_address
        self.dct_exec_device = dct_exec_device
        if dct_execute_address == CmdExecuteAdressEnum.CLIENT.value:
            self.destination_host = CommandLineArgsParse.get_client_ip()
        else:
            self.destination_host = CommandLineArgsParse.get_server_ip()
        self.dst_ipaddr = dct_ssh_ip
        self.dct_execute_address = dct_execute_address
        CommandOperation.execute_command_with_error(cmd=f"hostname {self.vm_name}",
                                                    cmd_execute_address=self.dct_execute_address)
        self.check_bridge()
        if self.dst_ipaddr:
            self.destination_host = self.dst_ipaddr
        self.dct_url = self.setting_hostname()

    def get_dct_machine_hostname(self):
        from scripts.script_libs.ifconfig import IfConfig
        if self.dct_exec_device:
            rtn_code = RtnStatusEnum.SUCCESS.value
            rtn_stdout = IfConfig.get_device_ipv4_addr(
                device_name=self.dct_exec_device, cmd_execute_address=self.dct_execute_address,
                ssh_ip=self.destination_host)
        else:
            rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                cmd=f"cat /etc/hosts |grep '{self.destination_host}'|awk -F ' ' '{{print $2}}'",
                cmd_execute_address=self.dct_execute_address, ssh_ip=self.destination_host)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            dct_url = re.sub(r"\s+", "", rtn_stdout)
        else:
            dct_url = ""
        return dct_url

    def check_bridge(self):
        """
        检查环境中是否有br0网桥
        :return:

        """
        from scripts.script_libs.ifconfig import IfConfig
        device_name_list = IfConfig.get_all_nic_name(ssh_ip=self.destination_host, cmd_execute_address=self.cmd_execute_address)
        if "br0" not in device_name_list:
            exec_command = "ip link add br0 type bridge"
            CommandOperation.execute_command_with_error(
                cmd=exec_command, cmd_execute_address=self.cmd_execute_address, ssh_ip=self.destination_host)

    def setting_hostname(self):
        """
        配置迁移侧的hosts和 被迁移侧的hostname与hosts的配置
        :return:
        """
        # 在发送侧进行配置
        from scripts.script_libs.ifconfig import IfConfig
        if self.dct_exec_device:
            ip_addr = IfConfig.get_device_ipv4_addr(
                device_name=self.dct_exec_device, cmd_execute_address=self.dct_execute_address,
                ssh_ip=self.destination_host)
        else:
            ip_addr = self.destination_host
        exec_command = f"cat /etc/hosts |grep {ip_addr} |grep {self.vm_name}.com"
        rtn_code, *_ = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.cmd_execute_address)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            test_attach_hosts = f'echo "{ip_addr} {self.vm_name}.com" >> /etc/hosts'
            rtn_code, *_ = CommandOperation.execute_command_with_error(
                cmd=test_attach_hosts, cmd_execute_address=self.cmd_execute_address)
        # 在接受侧进行配置
        exec_command = f"cat /etc/hosts |grep {ip_addr} |grep {self.vm_name}.com"
        rtn_code, *_ = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.dct_execute_address, ssh_ip=self.destination_host)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            test_attach_hosts = f'echo "{ip_addr} {self.vm_name}.com {self.vm_name}" >> /etc/hosts'
            rtn_code, *_ = CommandOperation.execute_command_with_error(
                cmd=test_attach_hosts, cmd_execute_address=self.dct_execute_address, ssh_ip=self.destination_host)
        exec_command = f"hostname {self.vm_name}.com"
        rtn_code, *_ = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.dct_execute_address, ssh_ip=self.destination_host)
        return f"{self.vm_name}.com"

    def virsh_migrate(self):
        self.setting_hostname()
        if self.migrate == "hot_migrate":
            exec_command = \
                (f"virsh migrate --live --unsafe --verbose --persistent {self.vm_name} "
                 f"qemu+ssh://{self.dct_url}/system --postcopy-bandwidth 1 &")

        elif self.migrate == "cool_migrate":
            # 设置虚机的状态为offline
            KvmOp.stop_vm(vm_name=self.vm_name, execute_address=self.cmd_execute_address)
            exec_command = (f"virsh migrate --offline --unsafe --verbose --persistent {self.vm_name} "
             f"qemu+ssh://{self.dct_url}/system &")
        else:
            exec_command = "ls -l"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(cmd=exec_command,
                                                                   cmd_execute_address=self.cmd_execute_address)
        return rtn_code, rtn_stdout, rtn_stderr

    def virsh_listen_domjobinfo(self):
        exec_command = f"virsh domjobinfo {self.vm_name}"
        rtn_code, *_ = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.cmd_execute_address)

    def judge_domjobinfo_completion(self):
        """
        判读任务是否完成
        :return:
        """
        if self.migrate == "hot_migrate":
            source_vm_status = KvmOp.check_vm_state(vm_name=self.vm_name, cmd_execute_address=self.cmd_execute_address)
            dst_vm_status = KvmOp.check_vm_state(vm_name=self.vm_name, cmd_execute_address=self.dct_execute_address,
                                                 ssh_ip=self.destination_host)
            if source_vm_status == "shut off" and dst_vm_status == "running":
                return True
            else:
                return False
        else:
            exec_command = "ps -ef|grep 'virsh migrate offline' |grep -v -- '--color=auto'"
            rtn_code, *_ = CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=self.cmd_execute_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                return True
            else:
                return False



    def destination_machine_create_device(self):
        current_path = os.path.abspath(os.path.dirname(__file__))
        root_path = os.path.dirname(current_path)
        if "scripts" == os.path.basename(root_path):
            sys.path.append(root_path)
        elif root_path == "/":
            raise ValueError
        else:
            root_path = os.path.dirname(root_path)
            sys.path.append(root_path)
        local_file_save_path = os.path.join(root_path, constants.FILE_TEMP_PATH_NAME)
        server_ip, client_ip = CommandOperation.get_logical_ip_form_config()
        file_name = f"search_nic_name.sh"
        local_ssh_file = os.path.join(local_file_save_path, file_name)
        remote_address = "/tmp/"
        remote_ssh = os.path.join("/tmp/", file_name)
        search_cmd = f"ifconfig | awk -v ip='{self.dst_ipaddr}' '$1 == \"inet\" && $2 == ip {{print prev}} {{prev=$1}}'"
        with open(local_ssh_file, 'a', encoding="utf-8") as file:
            file.write(search_cmd)
        scp_file_cmd = f"scp -P {ssh_port} {local_ssh_file} root@{self.dst_ipaddr}:{remote_address}"
        rtn_code, output, stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=scp_file_cmd,
            local_execute_flag=True
        )
        log.info(f"返回值为{str(rtn_code)}, output:{output}, error:{stderr}")
        if self.dst_ipaddr:
            exec_command = f"sh {remote_ssh}"
            rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                cmd=exec_command, ssh_ip=self.dst_ipaddr)
            device = rtn_stdout.replace(":", "")
            return device


if __name__ == '__main__':
    rtn_stdout = KvmOp.crate_pci_xml(vf_nic_bdf="0000:4b:01.0", cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    # VmOp.clean_hidden_machine(vm_name="sxevm001", cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    # adapter_name = VmAdapter.get_vm_adapter_vlanId(vm_name="sxevm001", adapter_name="hyper-v-1-7ZygqK", execute_address=CmdExecuteAdressEnum.SERVER.value)
    # ip_address = KvmOp.get_vm_interface(vm_name="scgbevm001", execute_address=CmdExecuteAdressEnum.SERVER.value)
    # KvmOp.add_vm_nic_pci(vm_name="scgbevm001", vf_nic_bdf="0000:4b:01.0", cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    # list_a = KvmOp.get_vm(cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    # rtn_code, bridge_pci_xml, bridge_interface = KvmOp.create_bridge_node(
    #     vm_name="scgbevm001", bridge_name="ens_macvlan0", cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    # KvmOp.start_vm(vm_name="scgbevm003", execute_address=CmdExecuteAdressEnum.SERVER.value)
    # a = VirshMigrate(vm_name="scgbevm003", migrate_type="hot_migrate", cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
    #              dct_execute_address=CmdExecuteAdressEnum.CLIENT.value, dct_exec_device="ens4f1")
    # a.virsh_migrate()
    # a.judge_domjobinfo_completion()

    # a.destination_machine_create_device()
    # print(bridge_pci_xml)
    # print(bridge_interface)
    # a = CommandOperation.execute_command_with_error(cmd="ls /tmp/*.xml", cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    # # print(a[1])
    # a = a[1].splitlines()
    # print(a)
    # print(list_a)
    # print(ip_address)
    # print(adapter_name)
    # running_list = VmOp.get_runnig_vm(cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    # vm_adapter_name = VmAdapter.get_adapter_name(vm_name=running_list[0],
    #                                              cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    #
    # a = VmAdapter.update_vf_adapter_name(vm_name=running_list[0], vm_adapter_name=vm_adapter_name[0])
    # for i in list(a):
    #     print(i)
    # switch_list = VmSwitch.get_all_switch()
    # print("~~~~~~~~~~~~~~~~~~~", switch_list)
    # print(running_list)
    # for vm in running_list:
    #     vm_adapter = VmAdapter.get_adapter_name(vm_name=vm, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    #     print("@@@@@@@@@@@@@@@@@@@@")
    #     print(vm_adapter)
    # VmOp.start_vm(vm_name="sxevm014", execute_address=CmdExecuteAdressEnum.SERVER.value)
