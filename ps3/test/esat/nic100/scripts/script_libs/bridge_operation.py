#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import datetime
import hashlib
import json
import ipaddress
import pdb
import re
import time
from collections import Counter
import random

import add_syspath
from scapy import *
from scapy.all import *
from scapy.layers.inet import IP, TCP, UDP
from scapy.layers.l2 import Dot1AD, Dot1Q, Ether

from scripts.script_libs import constants, log
from scripts.script_libs.file_operation import FileOperation
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.ip_operation import IpOperation
from scripts.script_libs.windows_adapter_operation import AdapterDataTool
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum
from scripts.script_libs.ethtool_operation import EthtoolOperation
from scripts.script_libs.ifconfig import IfConfig
from scripts.script_libs.log import *
from scripts.script_libs.script_base import SxeThread, ScriptBase


class BridgeOperation(object):

    def __init__(self, device_name: str, cmd_execute_address: str):
        self.device_name = device_name
        self.cmd_execute_address = cmd_execute_address

    def __get_bridge_properties(self, object_name: str):
        """
        author: wei.yuan1
        date:2024.1
        :return:
        """
        exec_command = "bridge -j {} show dev {}".format(object_name, self.device_name)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=self.cmd_execute_address)
        info_caller(f"在{self.cmd_execute_address}端执行命令：{exec_command}")
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_outputs = rtn_outputs.replace("'", '"')
            rtn_outputs = json.loads(rtn_outputs)
            return RtnStatusEnum.SUCCESS.value, rtn_outputs
        else:
            return RtnStatusEnum.FAIL.value, rtn_err

    def __set_bridge_properties(self, object_name, key, value):
        """
        author: wei.yuan1
        :param key:
        :param value:
        :return:
        """
        exec_command = "bridge {} set dev {} {} {}".format(object_name, self.device_name, key, value)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=self.cmd_execute_address)
        info_caller(f"在{self.cmd_execute_address}端执行命令：{exec_command}")
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            info_caller(f"{exec_command}执行成功")
            return RtnStatusEnum.SUCCESS.value, rtn_outputs
        else:
            error_caller(f"{exec_command}执行失败")
            return RtnStatusEnum.FAIL.value, rtn_err

    def show_nic_link_attribute(self):
        """
        获取网口的属性信息，格式如下：
        {
        "ifindex":2042,
        "ifname":"ens4f0",
        "flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],
        "mtu":1500,
        "hwmode":"VEB"}
        :return:
        """

        rtn_code, rtn_stdout = self.__get_bridge_properties(object_name="link")
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            hw_mode = rtn_stdout[0].get("hwmode")
            return hw_mode
        else:
            CommonOperation.result_collect(
                case_cls=self.__class__.__name__, expect_rtn=RtnStatusEnum.FAIL.value,
                rtn_code=rtn_code, description=f"获取网口：{self.device_name}信息", result="失败", expect_info="成功"

            )

    def set_nic_link_attribute(self, attribute_dict: dict):
        """
        设置网口的属性信息
        :return:
        """
        for key, value in attribute_dict.items():
            rtn_code, rtn_stdout = self.__set_bridge_properties(object_name="link", key=key, value=value)
            CommonOperation.result_collect(
                case_cls=self.__class__.__name__, expect_rtn=RtnStatusEnum.SUCCESS.value,
                rtn_code=rtn_code, description=f"获取网口：{self.device_name}信息", result="失败", expect_info="成功"
            )

    def add_nic_fdb_to_bridge(self, mac_address: str):
        """
        author: wei.yuan1
        date: 2024.07.12
        description: 添加网口到网桥
        :param mac_address: 网口的mac地址
        :return:
        """
        exec_command = "bridge fdb add dev {} {}".format(self.device_name, mac_address)
        info_caller(f"在{self.cmd_execute_address}执行命令：{exec_command}")
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=self.cmd_execute_address)
        return rtn_code, rtn_outputs, rtn_err

    def delete_nic_fdb_to_bridge(self, mac_address: str):
        """
        author: wei.yuan1
        date: 2024.07.12
        description: 删除网口到网桥
        :param mac_address: 网口的mac地址
        :param devie_name: 网口名称
        :return:
        """
        exec_command = "bridge fdb del dev {} {}".format(self.device_name, mac_address)
        info_caller(f"在{self.cmd_execute_address}执行命令：{exec_command}")
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=self.cmd_execute_address)
        return rtn_code, rtn_outputs, rtn_err

    def get_nic_fdb_to_bridge(self):
        """
        author: wei.yuan1
        date: 2024.07.12
        description: 获取网口到网桥的mac地址
        :param devie_name: 网口名称
        :return:
        """
        exec_command = "bridge -j fdb show dev {}".format(self.device_name)
        info_caller(f"在{self.cmd_execute_address}执行命令：{exec_command}")
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=self.cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_outputs = rtn_outputs.replace("'", '"')
            rtn_outputs = json.loads(rtn_outputs)
            mac_address = []
            for index in rtn_outputs:
                mac_address.append(index["mac"])

            return mac_address
        else:
            return rtn_err

def times_tcpdump_caught(device_name: str, pcap_file: str,
                         cmd_exec_address: str = CmdExecuteAdressEnum.SERVER.value,
                         use_promisc: bool = True, times_count: int = 50,
                         name_space: str = None, tcpdump_extra_vlaue: str = "",
                         protocol_type: str = "", ssh_ip: str = None):
    """
    author: wei.yuan1
    desc: 通过tcpdump抓包，抓到指定次数后结束抓包，返回抓到的包的列表
    :param device_name:
    :param pcap_file:
    :param cmd_exec_address:
    :param use_promisc:
    :param times_count:
    :param name_space:
    :param tcpdump_extra_vlaue:
    :param protocol_type:
    :param ssh_ip:
    :return:
    """
    if name_space:
        prefix_command = "ip netns exec {}".format(name_space)
    else:
        prefix_command = ""
    if not tcpdump_extra_vlaue:
        tcpdump_extra_vlaue = "!(udp port 5353 and (dst host 224.0.0.251 or dst host ff02::fb))"
    else:
        tcpdump_extra_vlaue = f"!(udp port 5353 and (dst host 224.0.0.251 or dst host ff02::fb)) and {tcpdump_extra_vlaue}"
    def tcpdump_caught_packet():
        if use_promisc:
            exec_command = \
                f"nohup {prefix_command} " \
                f"tcpdump -i {device_name} -c {str(times_count)} {protocol_type} -w {pcap_file} '{tcpdump_extra_vlaue}' &"
        else:
            exec_command = \
                (f"nohup {prefix_command} tcpdump -i {device_name} -c {str(times_count)} "
                 f"{protocol_type} -w {pcap_file}  -p '{tcpdump_extra_vlaue}' &")
        info_caller(f"在{cmd_exec_address}执行命令:{exec_command}")
        CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_exec_address,
                                                    ssh_ip=ssh_ip)

    tcpdump_caught_packet()

def timeout_tcpdump_caught(device_name: str, pcap_file: str,
                           cmd_exec_address: str = CmdExecuteAdressEnum.SERVER.value, use_promisc: bool = True,
                           name_space: str = None, tcpdump_extra_vlaue: str = "", timeout: int = 60,
                           protocol_type: str = "", ssh_ip: str = None
                           ):
    """
    author: wei.yuan1
    date: 2024.07.12
    description: 进行抓包
    :param protocol_type: 对抓包类型的筛选
    :param device_name: 监控的网口
    :param pcap_file: 抓包的文件
    :param cmd_exec_address:执行端
    :param use_promisc:是否开混杂
    :param name_space:命名空间
    :return:
    """
    time_out = timeout
    global prefix_command
    if name_space:
        prefix_command = "ip netns exec {}".format(name_space)
    else:
        prefix_command = ""
    if not tcpdump_extra_vlaue:
        tcpdump_extra_vlaue = "!(udp port 5353 and (dst host 224.0.0.251 or dst host ff02::fb))"
    else:
        tcpdump_extra_vlaue = f"!(udp port 5353 and (dst host 224.0.0.251 or dst host ff02::fb)) and {tcpdump_extra_vlaue}"
    def tcpdump_caught_packet():
        if use_promisc:
            exec_command = \
                f"timeout {str(time_out)} nohup {prefix_command} " \
                f"tcpdump -i {device_name} {protocol_type} -w {pcap_file} '{tcpdump_extra_vlaue}' &"
        else:
            exec_command = \
                f"timeout {str(time_out)} nohup {prefix_command} " \
                f"tcpdump -i {device_name} {protocol_type} -w {pcap_file}  -p '{tcpdump_extra_vlaue}' &"
        info_caller(f"在{cmd_exec_address}执行命令:{exec_command}")
        CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_exec_address,
                                                    ssh_ip=ssh_ip)

    tcpdump_packet_thread1 = SxeThread(tcpdump_caught_packet)
    tcpdump_packet_thread1.start()
    # time.sleep(time_out)
    # tcpdump_packet_thread1.join()


def function_lrest(case_cls, device_name: str, cmd_execute_address: str, ssh_ip: str = None, netns: str = None):
    """
    author: wei,yuan1
    date: 2025.03.19
    description: 设备执行pflr操作
    """
    reset_command = f'echo 1 |tee  /sys/class/net/{device_name}/device/reset > /dev/null'
    if netns:
        reset_command = f"ip netns exec {netns} bash -c '{reset_command}'"
    rtn_code, *_ = CommandOperation.execute_command_with_error(
        cmd=reset_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
    CommonOperation.result_collect(case_cls=case_cls, description=f"执行PFLR复位：{reset_command}",
                                   rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                   expect_info="成功", result="失败"
                                   )
    time.sleep(15)

def spoofchk_statistic(case_cls, device_name: str, cmd_execute_address: str):
    """
    Args:
        device_name: 设备名称
        cmd_execute_address: 执行端
    """
    device_dict = EthtoolOperation.show_driver_infomation(
        device_name=device_name, cmd_execute_address=cmd_execute_address)
    pci_address = device_dict["bus-info"]
    driver_name = device_dict["driver"]
    rtn_code, *_ = CommandOperation.execute_command_with_error(cmd="dmesg -C", cmd_execute_address=cmd_execute_address,
                                                               ssh_port=str(CommandLineArgsParse.get_test_port()))
    CommonOperation.result_collect(case_cls=case_cls, description="清理dmesg日志",
                                   rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                   expect_info="成功", result="失败"
                                   )
    check_file = f"ls -l /sys/kernel/debug/{driver_name.upper()}/{pci_address}/command"
    rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
        cmd=check_file,
        cmd_execute_address=cmd_execute_address,
        ssh_port=str(
            CommandLineArgsParse.get_test_port()))
    if rtn_code != RtnStatusEnum.SUCCESS.value:
        check_file = f"ls -l /sys/kernel/debug/{driver_name.lower()}/{pci_address}/command"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=check_file, cmd_execute_address=cmd_execute_address,
            ssh_port=str(
                CommandLineArgsParse.get_test_port()))
        CommonOperation.result_collect(case_cls=case_cls, description=f"检查文件目录{check_file}是否存在",
                                       result="不存在", expect_info="存在", expect_rtn=RtnStatusEnum.SUCCESS.value,
                                       rtn_code=rtn_code)
        driver_name = driver_name.lower()
    else:
        driver_name = driver_name.upper()
        log.info_caller(f"文件目录{check_file}存在")
    debugfs_location = f"echo 'spoof stats' > /sys/kernel/debug/{driver_name}/{pci_address}/command"
    rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
        cmd=debugfs_location,
        cmd_execute_address=cmd_execute_address,
        ssh_port=str(
            CommandLineArgsParse.get_test_port()))
    CommonOperation.result_collect(case_cls=case_cls, description=f"执行debugfs命令:{debugfs_location}",
                                   rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                   expect_info="成功", result="失败", create_bug=False
                                   )

def physical_function_reset(case_cls, device_name: str, cmd_execute_address: str):
    """
    Args:
        device_name: 设备名称
        cmd_execute_address: 执行端
    """
    device_dict = EthtoolOperation.show_driver_infomation(
        device_name=device_name, cmd_execute_address=cmd_execute_address)
    pci_address = device_dict["bus-info"]
    driver_name = device_dict["driver"]
    rtn_code, *_ = CommandOperation.execute_command_with_error(cmd="dmesg -C", cmd_execute_address=cmd_execute_address,
                                                               ssh_port=str(CommandLineArgsParse.get_test_port()))
    CommonOperation.result_collect(case_cls=case_cls, description="清理dmesg日志",
                                   rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                   expect_info="成功", result="失败"
                                   )
    check_file = f"ls -l /sys/kernel/debug/{driver_name.upper()}/{pci_address}/command"
    rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
        cmd=check_file,
        cmd_execute_address=cmd_execute_address,
        ssh_port=str(
            CommandLineArgsParse.get_test_port()))
    if rtn_code != RtnStatusEnum.SUCCESS.value:
        check_file = f"ls -l /sys/kernel/debug/{driver_name.lower()}/{pci_address}/command"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=check_file, cmd_execute_address=cmd_execute_address,
            ssh_port=str(
                CommandLineArgsParse.get_test_port()))
        CommonOperation.result_collect(case_cls=case_cls, description=f"检查文件目录{check_file}是否存在",
                                       result="不存在", expect_info="存在", expect_rtn=RtnStatusEnum.SUCCESS.value,
                                       rtn_code=rtn_code)
        driver_name = driver_name.lower()
    else:
        driver_name = driver_name.upper()
        log.info_caller(f"文件目录{check_file}存在")
    debugfs_location = f"echo 'pfr trigger' > /sys/kernel/debug/{driver_name}/{pci_address}/command"
    rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
        cmd=debugfs_location,
        cmd_execute_address=cmd_execute_address,
        ssh_port=str(
            CommandLineArgsParse.get_test_port()))
    if driver_name.lower() in ["sxe2"]:
        if "Invalid argument" in rtn_stderr:
            dmesg_info = CommandOperation.execute_command_with_error(cmd='dmesg', cmd_execute_address=cmd_execute_address)[1]
            log.warning(f"debugfs命令执行失败，返回信息为：{rtn_stderr}, dmesg 信息为：{dmesg_info}")
            CommonOperation.result_collect(case_cls=case_cls, description=f"执行debugfs命令:{debugfs_location}",
                                           rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                           expect_info="成功", result=f"失败, dmesg 信息为：{dmesg_info}"
                                           )
        else:
            CommonOperation.result_collect(case_cls=case_cls, description=f"执行debugfs命令:{debugfs_location}",
                                           rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                           expect_info="成功", result="失败"
                                           )
    time.sleep(120)


def system_hot_reset(case_cls, device_name: str, cmd_execute_address: str):
    """
    Args:
        case_cls:传入的类名
        device_name: 设备名称
        cmd_execute_address： 执行端
    """
    device_dict = EthtoolOperation.show_driver_infomation(
        device_name=device_name, cmd_execute_address=cmd_execute_address)
    pci_address = device_dict["bus-info"]
    driver_name = device_dict["driver"]
    rtn_code, *_ = CommandOperation.execute_command_with_error(cmd="dmesg -C", cmd_execute_address=cmd_execute_address,
                                                               ssh_port=str(CommandLineArgsParse.get_test_port()))
    CommonOperation.result_collect(case_cls=case_cls, description="清理dmesg日志",
                                   rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                   expect_info="成功", result="失败"
                                   )
    bus_info = re.sub(r"\s+", "", EthtoolOperation.show_driver_infomation(
        device_name=device_name, cmd_execute_address=cmd_execute_address)["bus-info"])
    # 对固件下发Sys reset(PCIe and core reset)
    exec_command = f"{constants.SCGBECLI64} -d {bus_info} reset type=0"
    rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
        cmd=exec_command, cmd_execute_address=cmd_execute_address)
    CommonOperation.result_collect(case_cls=case_cls,
                                   description=f"对设备{device_name}所在的固件进行pcie and core reset复位",
                                   expect_info=f"成功，信息为{rtn_stdout}", result=f"失败，reason is {rtn_stderr}",
                                   expect_rtn=RtnStatusEnum.SUCCESS.value, rtn_code=rtn_code
                                   )
    time.sleep(60)


def core_reset(case_cls, device_name: str, cmd_execute_address: str):
    """
    author: wei,yuan1
    date: 2024.12.10
    description： 进行core reset
    """
    device_dict = EthtoolOperation.show_driver_infomation(
        device_name=device_name, cmd_execute_address=cmd_execute_address)
    pci_address = device_dict["bus-info"]
    driver_name = device_dict["driver"]
    rtn_code, *_ = CommandOperation.execute_command_with_error(cmd="dmesg -C", cmd_execute_address=cmd_execute_address,
                                                               ssh_port=str(CommandLineArgsParse.get_test_port()))
    CommonOperation.result_collect(case_cls=case_cls, description="清理dmesg日志",
                                   rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                   expect_info="成功", result="失败"
                                   )
    bus_info = re.sub(r"\s+", "", EthtoolOperation.show_driver_infomation(
        device_name=device_name, cmd_execute_address=cmd_execute_address)["bus-info"])
    # 对固件下发Sys reset(PCIe and core reset)
    exec_command = f"{constants.SCGBECLI64} -d {bus_info} reset type=0"
    rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
        cmd=exec_command, cmd_execute_address=cmd_execute_address)
    CommonOperation.result_collect(case_cls=case_cls,
                                   description=f"对设备{device_name}所在的固件进行pcie and core reset复位",
                                   expect_info=f"成功，信息为{rtn_stdout}", result=f"失败，reason is {rtn_stderr}",
                                   expect_rtn=RtnStatusEnum.SUCCESS.value, rtn_code=rtn_code
                                   )
    time.sleep(60)


def create_vf_device(device_name: str, sriov_numvfs: int, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
    """
    __sumary__: 创建VF设备，不加载VF驱动
    Args:
        device_name: pf的设备名称
        sriov_numvfs: 创建的sriov 的数目
        cmd_execute_address: 命令执行方
    """
    driver_dict = EthtoolOperation.show_driver_infomation(
        device_name=device_name, cmd_execute_address=cmd_execute_address)
    pci_num = driver_dict["bus-info"]
    print_sriov_cmd = f"cat /sys/class/net/{device_name}/device/sriov_numvfs"
    rtn_code, output, err = CommandOperation.execute_command_with_error(
        cmd=print_sriov_cmd, cmd_execute_address=cmd_execute_address
    )
    assert rtn_code == RtnStatusEnum.SUCCESS.value, "command return vlaue is error"
    if int(output) == 0:
        command = f"echo {str(sriov_numvfs)} > /sys/class/net/{device_name}/device/sriov_numvfs"
        rtn_code, output, err = CommandOperation.execute_command_with_error(
            cmd=command, cmd_execute_address=cmd_execute_address
        )
        log.info(f"command:{command}, rtn_code: {str(rtn_code)}, outputs:{output}, error:{err}")
    device_name_list = IfConfig.get_all_nic_name(cmd_execute_address=cmd_execute_address)
    test_device_list = []
    for device_name_index in device_name_list:
        if device_name in device_name_index and device_name_index != device_name:
            test_device_list.append(device_name_index)
    if len(test_device_list) == 0:
        log.info_caller(f"{device_name}的驱动未添加")
    else:
        vf_info_dict = EthtoolOperation.show_driver_infomation(
            device_name=test_device_list[0], cmd_execute_address=cmd_execute_address)
        CommonOperation.rmmod_driver(driver_name=vf_info_dict["driver"],
                                     cmd_execute_address=cmd_execute_address, force=True)
    return test_device_list


def get_interface_broadcast_address(device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
    """_summary_
    获取网口的广播地址
    Args:
        device_name (str): _description_
        cmd_execute_address (str, optional): _description_. Defaults to CmdExecuteAdressEnum.CLIENT.value.
    """
    import json
    exec_command = constants.STR_SPACE.join([constants.IP, "-j", constants.LINK, constants.SHOW, device_name])
    rtn_code, rtn_stdout, rtn_err = CommandOperation.execute_command_with_error(cmd=exec_command,
                                                                                cmd_execute_address=cmd_execute_address)
    if rtn_code == RtnStatusEnum.SUCCESS.value:
        # rtn_outputs = rtn_stdout.replace("'", '"')
        rtn_list = json.loads(rtn_stdout)
        # print(rtn_list[0].get("broadcast"))
        return rtn_list[0].get("broadcast")


def show_string_hashlib(string):
    """
    根据传入的字符串计算md5
    :param string:
    :return:
    """
    md5 = hashlib.md5()
    md5.update(string.encode("utf-8"))
    md5_digest = md5.hexdigest()
    return md5_digest


def print_duplicates(lst):
    counts = Counter(lst)
    duplicates = [item for item, count in counts.items() if count > 1]
    if duplicates:
        return duplicates
    else:
        return None


def str_to_dict(data: str, driver_name: str = "ice"):
    """
    author: wei.yuan1
    date: 2024.07.19
    description:将字符串转换为字典
    Args:
        data (str): 字符串

    Returns:
        dict: 字典
    """
    if driver_name == "ice":
        pattern = r"mac: ([0-9a-fA-F:]+), vsi_count = (\d+), fw_act_flag = (\d+), lb_en = (\d+), lan_en = (\d+), " \
                  r"filt_act = (\d+), filt_rule_id = (\d+)"
    else:
        pattern = r"recipe (\d+), rule_id (\d+), act ([0-9a-fA-F]+), full_key ([0-9a-fA-F:]+), vsi_cnt (\d+), lb_en (\d+), " \
                  r"lan_en (\d+), mac ([0-9a-fA-F:]+).*?"
    match = re.match(pattern, data)
    # 将提取的数据转换为字典
    if match:
        if driver_name == "ice":
            mac, vsi_count, fw_act_flag, lb_en, lan_en, filt_act, filt_rule_id = match.groups()
            full_key, recipe = "", ""
        else:
            recipe, filt_rule_id, filt_act, full_key, vsi_count, lb_en, lan_en, mac = match.groups()
            fw_act_flag = 0
        result = {
            mac: {
                "vsi_cnt": int(vsi_count),
                "fw_act_flag": int(fw_act_flag),
                "lb_en": int(lb_en),
                "lan_en": int(lan_en),
                "filt_act": int(filt_act, 16),
                "filt_rule_id": int(filt_rule_id),
                "full_key": full_key,
                "recipe": recipe
            }
        }

        return result
    else:
        log.warning_caller("数据格式不匹配")
        return {}


def vlan_str_to_dict(data: str):
    """
    author: wei.yuan1
    date: 2024.10.10
    description:将字符串转换为字典
    """
    pattern = (r"recipe (\d+), rule_id (\d+), act (\d+), full_key ([0-9a-fA-F:]+), vsi_cnt (\d+), lb_en (\d+), "
               r"lan_en (\d+), tpid ([0-9a-fA-F]), vid (\d+)")
    match = re.match(pattern, data)
    if match:
        recipe, filt_rule_id, filt_act, full_key, vsi_count, lb_en, lan_en, tpid, vid = match.groups()
        fw_act_flag = 0
        result = {
            vid: {
                "vsi_cnt": int(vsi_count),
                "fw_act_flag": int(fw_act_flag),
                "lb_en": int(lb_en),
                "lan_en": int(lan_en),
                "filt_act": int(filt_act),
                "filt_rule_id": int(filt_rule_id),
                "full_key": full_key,
                "recipe": recipe,
                "tpid": tpid
            }
        }
        return result
    else:
        log.warning_caller("数据格式不匹配")
        return {}


def parse_data(data: str, key_info: str = "mac:"):
    """
    author: wei.yuan1
    date: 2024.07.19
    description:解析数据
    Args:
        data (str): 数据

    Returns:
        dict: 解析后的数据
    """
    mac_in_info = []
    for line in data.replace("\r", "").split("\n"):
        if key_info in line and "mac:" in key_info:
            match = re.search(r'mac: .*', line)
        else:
            match = re.search(r'recipe .*', line)
        if match:
            mac_in_info.append(match.group(0))
    return mac_in_info


def parse_vlan_data(data: str, key_info: str = "vid"):
    """
    author: wei.yuan1
    date: 2024.07.19
    description:解析数据
    Args:
        data (str): 数据

    Returns:
        dict: 解析后的数据
    """
    mac_in_info = []
    vlan_list = []
    for line in data.replace("\r", "").split("\n"):
        if key_info in line and "tpid" in line:
            vlan_list.append(line)
    for line in vlan_list:
        if key_info in line and "vid " in key_info:
            match = re.search(r'mac: .*', line)
        else:
            match = re.search(r'recipe .*', line)
        if match:
            mac_in_info.append(match.group(0))
    return mac_in_info

def debugfs_interface_vsi_dump(case_cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
    """
    author: wei.yuan1
    date: 2026年2月2日10:36:13
    description: debugfs接口中vsi dump的查看关键字信息
    :param case_cls:
    :param device_name:
    :param cmd_execute_address:
    :return:
    """
    pci_address = EthtoolOperation.show_driver_infomation(
        device_name=device_name, cmd_execute_address=cmd_execute_address)["bus-info"]
    driver_name = EthtoolOperation.show_driver_infomation(
        device_name=device_name, cmd_execute_address=cmd_execute_address)["driver"]
    if driver_name in ["sxe2", "scgbe"]:
        debug_command = "vsi dump"
        # debug -C命令清除dmesg日志
        rtn_code, *_ = CommandOperation.execute_command_with_error(cmd="dmesg -C",
                                                                   cmd_execute_address=cmd_execute_address,
                                                                   ssh_port=str(CommandLineArgsParse.get_test_port()))
        CommonOperation.result_collect(case_cls=case_cls, description="清理dmesg日志",
                                       rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                       expect_info="成功", result="失败"
                                       )
        check_file = f"ls -l /sys/kernel/debug/{driver_name.upper()}/{pci_address}/command"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=check_file,
            cmd_execute_address=cmd_execute_address,
            ssh_port=str(
                CommandLineArgsParse.get_test_port()))
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            check_file = f"ls -l /sys/kernel/debug/{driver_name.lower()}/{pci_address}/command"
            rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(cmd=check_file,
                                                                                           cmd_execute_address=cmd_execute_address,
                                                                                           ssh_port=str(
                                                                                               CommandLineArgsParse.get_test_port()))
            CommonOperation.result_collect(case_cls=case_cls, description=f"检查文件目录{check_file}是否存在",
                                           result="不存在", expect_info="存在", expect_rtn=RtnStatusEnum.SUCCESS.value,
                                           rtn_code=rtn_code)
            driver_name = driver_name.lower()
        else:
            driver_name = driver_name.upper()
            log.info_caller(f"文件目录{check_file}存在")
        debugfs_location = f"echo '{debug_command}' > /sys/kernel/debug/{driver_name}/{pci_address}/command"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(cmd=debugfs_location,
                                                                                       cmd_execute_address=cmd_execute_address,
                                                                                       ssh_port=str(
                                                                                           CommandLineArgsParse.get_test_port()))
        CommonOperation.result_collect(case_cls=case_cls, description=f"执行debugfs命令:{debugfs_location}",
                                       rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                       expect_info="成功", result="失败", create_bug=False
                                       )
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            dmesg_command = "dmesg|grep 'netdev st=1'"
            rtn_code, dmesg_result, dmesg_error = CommandOperation.execute_command_with_error(
                cmd=dmesg_command, cmd_execute_address=cmd_execute_address,
                ssh_port=str(CommandLineArgsParse.get_test_port()))
            CommonOperation.result_collect(case_cls=case_cls, expect_rtn=abs(RtnStatusEnum.FAIL.value), rtn_code=rtn_code,
                                           description="vsi dump信息检查", expect_info="netdev st=0",result=dmesg_result,)

    else:
        log.info(f"{driver_name}驱动不支持，跳过后续步骤")


def debugfs_interface_mmcat(case_cls, device_name: str, debug_command: str = None,
                            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                            driver_name: str = "ice"):
    """
    author: wei.yuan1
    date: 2024.07.19
    description:debugfs接口中的查看
    :param device_name: 网口名
    :param cmd_execute_address:
    :return:
    """
    lut_list = []
    mac_key_list = []
    pci_address = EthtoolOperation.show_driver_infomation(
        device_name=device_name, cmd_execute_address=cmd_execute_address)["bus-info"]
    driver_name = EthtoolOperation.show_driver_infomation(
        device_name=device_name, cmd_execute_address=cmd_execute_address)["driver"]
    if driver_name in ["sxe2", "scgbe"]:
        debug_command = "switch rule dump"
    else:
        debug_command = "dump mmcast"
    # debug -C命令清除dmesg日志
    rtn_code, *_ = CommandOperation.execute_command_with_error(cmd="dmesg -C", cmd_execute_address=cmd_execute_address,
                                                               ssh_port=str(CommandLineArgsParse.get_test_port()))
    CommonOperation.result_collect(case_cls=case_cls, description="清理dmesg日志",
                                   rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                   expect_info="成功", result="失败"
                                   )
    check_file = f"ls -l /sys/kernel/debug/{driver_name.upper()}/{pci_address}/command"
    rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
        cmd=check_file,
        cmd_execute_address=cmd_execute_address,
        ssh_port=str(
            CommandLineArgsParse.get_test_port()))
    if rtn_code != RtnStatusEnum.SUCCESS.value:
        check_file = f"ls -l /sys/kernel/debug/{driver_name.lower()}/{pci_address}/command"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(cmd=check_file,
                                                                                       cmd_execute_address=cmd_execute_address,
                                                                                       ssh_port=str(
                                                                                           CommandLineArgsParse.get_test_port()))
        CommonOperation.result_collect(case_cls=case_cls, description=f"检查文件目录{check_file}是否存在",
                                       result="不存在", expect_info="存在", expect_rtn=RtnStatusEnum.SUCCESS.value,
                                       rtn_code=rtn_code)
        driver_name = driver_name.lower()
    else:
        driver_name = driver_name.upper()
        log.info_caller(f"文件目录{check_file}存在")
    debugfs_location = f"echo '{debug_command}' > /sys/kernel/debug/{driver_name}/{pci_address}/command"
    rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(cmd=debugfs_location,
                                                                                   cmd_execute_address=cmd_execute_address,
                                                                                   ssh_port=str(
                                                                                       CommandLineArgsParse.get_test_port()))
    CommonOperation.result_collect(case_cls=case_cls, description=f"执行debugfs命令:{debugfs_location}",
                                   rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                   expect_info="成功", result="失败", create_bug=False
                                   )
    if rtn_code == RtnStatusEnum.SUCCESS.value:
        dmesg_command = "dmesg|grep -v 'recipe 7'|grep -v 'recipe 8'"
        rtn_code, dmesg_result, dmesg_error = CommandOperation.execute_command_with_error(
            cmd=dmesg_command, cmd_execute_address=cmd_execute_address,
            ssh_port=str(CommandLineArgsParse.get_test_port()))
        CommonOperation.result_collect(case_cls=case_cls, description=f"执行dmesg命令:{dmesg_command}",
                                       rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                       expect_info="成功", result=f"{dmesg_error}", create_bug=False
                                       )
        if driver_name.lower() in ["scgbe", "sxe2"]:
            dmesg_result = parse_data(dmesg_result, key_info="mac")
        else:
            dmesg_result = parse_data(dmesg_result)
        lut_description = dmesg_result
        for lut_index in lut_description:
            str_to_dict_result = str_to_dict(lut_index, driver_name=driver_name)
            lut_list.append(str_to_dict_result)
        for lut in lut_list:
            if lut:
                mac_key_list.append(list(lut.keys())[0])
                log.info_caller(f"lut信息:{lut}")
        duplicates = print_duplicates(mac_key_list)

        rtn_code = RtnStatusEnum.SUCCESS.value if duplicates is None else RtnStatusEnum.FAIL.value
        CommonOperation.result_collect(case_cls=case_cls, description=f"dmesg日志中存在相同mac地址信息:{duplicates}",
                                       expect_info="成功", result="失败", rtn_code=rtn_code,
                                       expect_rtn=RtnStatusEnum.SUCCESS.value

                                       )
    else:
        log.error_caller(f"dmesg命令执行失败")
    return lut_list


def debugfs_interface_vlan_form(case_cls, device_name: str, debug_command: str = None,
                                cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                                driver_name: str = "ice"):
    """_summary_
    author: wei.yuan1
    date: 2024.07.19
    description:debugfs接口中的查看
    :param device_name: 网口名
    :param cmd_execute_address:
    :return:
    Args:
        case_cls (_type_): _description_
        device_name (str): 网口名
        debug_command (str): debugfs的 命令
        cmd_execute_address (str, optional): 执行端. Defaults to CmdExecuteAdressEnum.SERVER.value.
        driver_name (str, optional): 驱动名. Defaults to "ice".
    """
    vlan_list = []
    vlanid_key_list = []
    pci_address = EthtoolOperation.show_driver_infomation(
        device_name=device_name, cmd_execute_address=cmd_execute_address)["bus-info"]
    driver_name = EthtoolOperation.show_driver_infomation(
        device_name=device_name, cmd_execute_address=cmd_execute_address)["driver"]
    if driver_name.lower() in ["scgbe", "sxe2"]:
        debug_command = "switch rule dump"
    else:
        debug_command = " dump vlan"
    # debug -C命令清除dmesg日志
    rtn_code, *_ = CommandOperation.execute_command_with_error(cmd="dmesg -C", cmd_execute_address=cmd_execute_address,
                                                               ssh_port=str(CommandLineArgsParse.get_test_port()))
    CommonOperation.result_collect(case_cls=case_cls, description="清理dmesg日志",
                                   rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                   expect_info="成功", result="失败"
                                   )
    check_file = f"ls -l /sys/kernel/debug/{driver_name.upper()}/{pci_address}/command"
    rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
        cmd=check_file, cmd_execute_address=cmd_execute_address, ssh_port=str(CommandLineArgsParse.get_test_port()))
    if rtn_code != RtnStatusEnum.SUCCESS.value:
        check_file = f"ls -l /sys/kernel/debug/{driver_name.lower()}/{pci_address}/command"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=check_file,
            cmd_execute_address=cmd_execute_address,
            ssh_port=str(CommandLineArgsParse.get_test_port()))
        CommonOperation.result_collect(case_cls=case_cls, description=f"检查文件目录{check_file}是否存在",
                                       result="不存在", expect_info="存在", expect_rtn=RtnStatusEnum.SUCCESS.value,
                                       rtn_code=rtn_code)
        driver_name = driver_name.lower()
    else:
        driver_name = driver_name.upper()
        log.info_caller(f"文件目录{check_file}存在")
    debugfs_location = f"echo '{debug_command}' > /sys/kernel/debug/{driver_name}/{pci_address}/command"
    rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
        cmd=debugfs_location, cmd_execute_address=cmd_execute_address,
        ssh_port=str(CommandLineArgsParse.get_test_port())
    )
    CommonOperation.result_collect(case_cls=case_cls, description=f"执行debugfs命令:{debugfs_location}",
                                   rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                   expect_info="成功", result="失败", create_bug=False
                                   )
    if rtn_code == RtnStatusEnum.SUCCESS.value:
        dmesg_command = "dmesg|grep -v 'recipe 7'"
        rtn_code, dmesg_result, dmesg_error = CommandOperation.execute_command_with_error(
            cmd=dmesg_command, cmd_execute_address=cmd_execute_address,
            ssh_port=str(CommandLineArgsParse.get_test_port()))
        CommonOperation.result_collect(case_cls=case_cls, description=f"执行dmesg命令:{dmesg_command}",
                                       rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                       expect_info="成功", result=f"{dmesg_error}", create_bug=False
                                       )
        dmesg_result_list = dmesg_result.replace("\r", "").split("\n")
        dmesg_result_list = [i for i in dmesg_result_list if len(i) > 0]
        end_flag = [dmesg_result_list.index(i) for i in dmesg_result_list if "switch rule dump end" in i][0]
        dmesg_result_list = dmesg_result_list[:end_flag]
        # 取多个空格作为分隔符
        # pattern = re.compile(r':\s{4,}(.*)')
        pattern = re.compile(r':\s\t')
        if driver_name.lower() in ["scgbe", "sxe2"]:
            vlan_list = parse_vlan_data(data=dmesg_result, key_info="vid")
        else:
            for dmesg_result in dmesg_result_list:
                if "tpid" in dmesg_result:
                    result = dmesg_result.split("\t")[1]
                    vlan_list.append(result)

        for index in vlan_list:
            if driver_name.lower() in ["scgbe", "sxe2"]:
                pairs = re.findall(r'(\w+)\s* \s*([^,]+)', index)
                vid = pairs[-2][1].strip()
                pairs.remove(pairs[-2])
                # tpid = pairs[-2][1].strip()
                # pairs.remove(pairs[-2])
                vlan_dict = {vid: {pair[0].strip(): pair[1].strip() for pair in pairs[:-1]}}
            else:
                pairs = re.findall(r'(\w+)\s*=\s*([^,]+)', index)
                vlan_dict = {pairs[0][1].strip(): {pair[0].strip(): pair[1].strip() for pair in pairs[1:]}}
            vlanid_key_list.append(vlan_dict)
        merged_dict = {}
        for index in vlanid_key_list:
            for key, value in index.items():
                if key in merged_dict:
                    merged_dict[key].append(value)
                else:
                    merged_dict[key] = [value]
        return merged_dict


def check_vlanid_in_debugfs(case_cls, vlan_id: str, vlan_info_dict: dict,
                            expect_rtn: int = RtnStatusEnum.SUCCESS.value):
    """
        author: wei.yuan1
        date: 2024.07.15
        description: 检查网卡设备的vlan id所绑定项的信息是否在vlan debugfs中

        Args:
            vlan_id (str): vlanid
            vlan_info_dict: debufs中获取到的vlan的信息
            expect_rtn: 期望值
        """

    CommonOperation.concat_test_steps(f"检查网卡设备的vlan id所绑定项的信息是否在vlan debugfs中")
    vlanid_list = list(vlan_info_dict.keys())
    rtn_code = RtnStatusEnum.SUCCESS.value if vlan_id in vlanid_list else RtnStatusEnum.FAIL.value
    CommonOperation.result_collect(
        case_cls=case_cls, rtn_code=rtn_code, expect_rtn=expect_rtn,
        description="检查网卡设备的vlan id所绑定项的信息是否在vlan debugfs中",
        expect_info=f"vlan id:{vlan_id}在debugfs:{str(vlanid_list)}中",
        result=f"vlan id:{vlan_id}不在debugfs:{str(vlanid_list)}中"
    )


def create_different_network_ip(given_ip):
    try:
        # 将输入的 IP 地址转换为 IPv4 地址对象
        given_ip_obj = ipaddress.IPv4Address(given_ip)
        # 获取给定 IP 地址的整数表示
        given_ip_int = int(given_ip_obj)
        # 选择一个不同的网段，这里简单地将 IP 地址的第一个字节加 1
        new_network_int = (given_ip_int & 0x00FFFFFF) | ((given_ip_int >> 24 + 1) % 256 << 24)
        # 将新的整数表示转换为 IPv4 地址对象
        new_ip_obj = ipaddress.IPv4Address(new_network_int)
        return str(new_ip_obj)
    except ValueError:
        print("输入的 IP 地址格式不正确，请输入有效的 IPv4 地址。")
        return None


def environment_build_ip(case_cls, exec_device: str, other_exec_device: str,
                         exec_address: str, other_exec_address: str, ip_version: str = "ipv4",
                         exec_netns: str = None, other_netns: str = None, loopback_flag: bool = False):
    """
    author: wei.yuan1
    date: 2023.11.29
    :param exec_device: 测试网口名称
    :param other_exec_device:陪测端网口名称
    :param exec_address:执行端
    :param other_exec_address: 陪测端
    :param exec_netns:
    :param other_netns
    :return:
    """
    import ipaddress
    import random

    random.seed(float(time.time()))
    time.sleep(5)

    # 定义一个 IPv6 网络
    if ip_version == "ipv6":
        network = ipaddress.IPv6Network("2001:db8::/64")
    else:
        network = ipaddress.IPv4Network("199.162.1.0/24")

    # 生成随机的 IPv4 地址
    def generate_random_ipv4_addresses(network, count):
        addresses = []
        for _ in range(count):
            # 生成随机的 8 位整数（对于 /24 网络，主机部分为 8 位）
            random_host_part = random.randint(0, 2 ** (32 - network.prefixlen) - 2)  # 避开网络地址和广播地址
            # 将随机整数转换为 IPv4 地址的主机部分
            random_host_address = ipaddress.IPv4Address(network.network_address + random_host_part)
            addresses.append(str(random_host_address))
        return addresses

    # 生成随机的 IPv6 地址
    def generate_random_ipv6_addresses(network, count):
        addresses = []
        for _ in range(count):
            # 生成随机的 64 位整数
            random_host_part = random.randint(1, 2 ** 64 - 2)
            # 将随机整数转换为 IPv6 地址的主机部分
            random_host_address = ipaddress.IPv6Address(network.network_address + random_host_part)
            addresses.append(str(random_host_address))
        return addresses

    if ip_version == "ipv4":
        ip_address_list = generate_random_ipv4_addresses(network=network, count=2)
    else:
        ip_address_list = generate_random_ipv6_addresses(network=network, count=2)
    server_test_ip = ip_address_list[0]
    client_test_ip = ip_address_list[1]

    def configure_address(execute_device, ipaddress, execute_address, name_space, version):
        """
        :param execute_device: 添加IP的网卡对象
        :param ipaddress: IP地址
        :param execute_address: 执行端
        :return:
        """
        if version == "ipv4":
            ipaddress = ipaddress + f"/24"

            rtn_code = IpOperation.add_ip_addr(
                device_name=execute_device, ip_addr=ipaddress,
                cmd_execute_address=execute_address, netns_name=name_space)
        else:
            ipaddress = ipaddress + f"/64"
            rtn_code = IpOperation.add_ipv6_addr(
                device_name=execute_device, ipv6_addr=ipaddress,
                cmd_execute_address=execute_address, netns_name=name_space
            )
        CommonOperation.result_collect(
            case_cls=case_cls, description=f"{exec_address}:{exec_device}添加IP地址:{ipaddress}",
            expect_info="成功", result="失败", rtn_code=rtn_code, expect_rtn=True)

    # 清除IP，为了防止在后续的操作中，存在发包时候使用默认优先IP发送，导致ping包有问题
    if not exec_netns:
        IpOperation.add_netns(case_cls=case_cls, device_name=exec_device, netns_name=exec_netns,
                              cmd_execute_address=exec_address)
    if not other_netns:
        IpOperation.add_netns(case_cls=case_cls, device_name=other_exec_device, cmd_execute_address=other_exec_address,
                              netns_name=other_netns)
    IpOperation.flush_dev_ip(device_name=exec_device, cmd_execute_address=exec_address, netns=exec_netns)
    IpOperation.flush_dev_ip(device_name=other_exec_device,
                             cmd_execute_address=other_exec_address, netns=other_netns)

    # 添加server端的IP地址
    configure_address(execute_device=exec_device, ipaddress=server_test_ip, execute_address=exec_address,
                      name_space=exec_netns, version=ip_version)

    if loopback_flag:
        configure_address(execute_device=other_exec_device, ipaddress=client_test_ip,
                          execute_address=exec_address, name_space=other_netns, version=ip_version)
        time.sleep(5)
        send_object = AdapterDataTool(cmd_execute_address=exec_address)
        send_object.send_packet(
            exec_host_os="linux", rx_device_ip=server_test_ip, count=2,
            ip_type=ip_version,
            tx_device_ip=client_test_ip, netns_name=other_netns)
    else:
        configure_address(execute_device=other_exec_device, ipaddress=client_test_ip,
                          execute_address=other_exec_address, name_space=other_netns, version=ip_version)
        time.sleep(5)
        send_object = AdapterDataTool(cmd_execute_address=other_exec_address)
        send_object.send_packet(
            exec_host_os="linux", rx_device_ip=server_test_ip, count=2,
            ip_type=ip_version,
            tx_device_ip=client_test_ip, netns_name=other_netns)
    return server_test_ip, client_test_ip


def exec_command_function(logical_ip, exec_command, exec_address):
    # exec_command = """TZ='UTC-0' date +'"%Y-%m-%d-%H:%M:%S"'"""
    current_path = os.path.abspath(os.path.dirname(__file__))
    root_path = os.path.dirname(current_path)
    while True:
        if "scripts" == os.path.basename(root_path):
            sys.path.append(root_path)
            break
        elif root_path == "/":
            raise ValueError
        else:
            root_path = os.path.dirname(root_path)
            sys.path.append(root_path)

    local_file_save_path = os.path.join(root_path, constants.FILE_TEMP_PATH_NAME)
    remote_file_name = f"time_stamp.sh"
    exec_command_file = os.path.join(local_file_save_path, remote_file_name)

    with open(exec_command_file, "w") as file:
        file.write(exec_command)
    test_port = CommandLineArgsParse.get_test_port()
    ssh_port = str(test_port)

    scp_file_cmd = f"scp -P {ssh_port} {exec_command_file} root@{logical_ip}:/tmp"
    rtn_code, output, stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
        cmd=scp_file_cmd,
        local_execute_flag=True
    )

    rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
        cmd="sh /tmp/time_stamp.sh", cmd_execute_address=exec_address)
    os.remove(exec_command_file)
    CommandOperation.execute_command_with_error(cmd="rm -rf /tmp/time_stamp.sh", cmd_execute_address=exec_address)
    return rtn_stdout


def parse_packet(protocol_type, packet):
    def ip_parse():
        """
        ip报的解析
        :return src_ip:源IP、dst_ip:目的ip.ip 负载
        """
        # Extract the IP source and destination addresses
        src_ip = packet[IP].src
        dst_ip = packet[IP].dst
        # if packet.haslayer(IP):
        #     ip_raw = packet.getlayer(IP).load

        # else:
        ip_raw = ""
        raw_md5 = show_string_hashlib(ip_raw)

        return src_ip, dst_ip, raw_md5

    def ether_parse():
        """以太帧报文解析"""
        # Extract the MAC source and destination addresses
        src_mac = packet[Ether].src
        dst_mac = packet[Ether].dst

        # if packet.haslayer(Ether):
        #     ether_raw = packet.getlayer(Ether).load
        #     # ether_raw = packet.getlayer(Ether).load
        # else:
        ether_raw = ""
        raw_md5 = show_string_hashlib(ether_raw)
        return src_mac, dst_mac, raw_md5

    def Dot1q_parse():  # -> tuple[Any, Any, Any, str]:
        """
        vlan报文解析
        :return:
        """
        vlan_list = []
        vlanid_key_list = []
        vlan_prio = packet[Dot1Q].prio
        vlan_tyid = packet[Dot1Q].type
        vlan_vid = packet[Dot1Q].vlan
        # vlan_raw = packet.getlayer(Dot1Q).load
        # raw_md5 = show_string_hashlib(vlan_raw)
        return vlan_prio, vlan_tyid, vlan_vid

    def Dot1ad_parse():
        """
        QinQ报文解析
        :return:
        """
        qinq_list = []
        qinqid_key_list = []

        qinq_prio = packet[Dot1Q].prio
        qing_tyid = packet[Dot1Q].type
        qing_tyid = hex(qing_tyid)
        qinq_vid = packet[Dot1Q].vlan
        # qinq_raw = packet.getlayer(Dot1Q).load
        # raw_md5 = show_string_hashlib(qinq_raw)
        return qinq_prio, qing_tyid, qinq_vid

    def udp_parse():
        """
        UDP消息解析
        :return:
        """
        src_port = packet[UDP].sport
        dst_port = packet[UDP].dport
        # if packet.haslayer(UDP):
        #     udp_raw = packet.getlayer(UDP).load
        # else:
        udp_raw = ""
        raw_md5 = show_string_hashlib(udp_raw)
        return src_port, dst_port, raw_md5

    packet_format_dict = {}
    if protocol_type is Ether:

        packet_format_dict["src_mac"] = ether_parse()[0]
        packet_format_dict["dst_mac"] = ether_parse()[1]
    elif Dot1Q is protocol_type:
        packet_format_dict["src_mac"] = ether_parse()[0]
        packet_format_dict["dst_mac"] = ether_parse()[1]
        packet_format_dict["vlan_prio"] = Dot1q_parse()[0]
        packet_format_dict["vlan_tyid"] = Dot1q_parse()[1]
        packet_format_dict["vlan_vid"] = Dot1q_parse()[2]
        # packet_format_dict["raw"] = Dot1q_parse()[3]
    elif Dot1AD is protocol_type:
        packet_format_dict["src_mac"] = ether_parse()[0]
        packet_format_dict["dst_mac"] = ether_parse()[1]
        packet_format_dict["vlan_prio"] = Dot1ad_parse()[0]
        packet_format_dict["vlan_tyid"] = Dot1ad_parse()[1]
        packet_format_dict["vlan_vid"] = Dot1ad_parse()[2]
        # packet_format_dict["raw"] = Dot1ad_parse()[3]
    elif IP is protocol_type:
        packet_format_dict["src_mac"] = ether_parse()[0]
        packet_format_dict["dst_mac"] = ether_parse()[1]
        packet_format_dict["src_ip"] = ip_parse()[0]
        packet_format_dict["dst_ip"] = ip_parse()[1]
        # packet_format_dict["raw"] = ip_parse()[2]
    elif UDP is protocol_type:
        packet_format_dict["src_mac"] = ether_parse()[0]
        packet_format_dict["dst_mac"] = ether_parse()[1]
        packet_format_dict["src_ip"] = ip_parse()[0]
        packet_format_dict["dst_ip"] = ip_parse()[1]
        packet_format_dict["src_port"] = udp_parse()[0]
        packet_format_dict["dst_port"] = udp_parse()[1]
        # packet_format_dict["raw"] = udp_parse()[2]
    else:
        packet_format_dict = {}
    return packet_format_dict


class ParsePacket(object):

    def __init__(self, protocol_type: str, remote_file: str = None,
                 cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, ssh_ip: str = None):
        """
        :param remote_file: 测试端要传入的文件
        :param protocol_type: 协议类型
        """
        self.remote_file = remote_file
        self.protocol_type = protocol_type
        self.cmd_execute_address = cmd_execute_address
        self.local_file = None
        self.ssh_ip = ssh_ip
        self.full_local_file_path = None

    def transport_file_local_path(self, ssh_ip: str = None):
        """
        author: wei.yuan1
        date: 2024.07.20
        description: 文件传输
        """
        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            test_port = test_port
        else:
            test_port = 22
        current_path = os.path.abspath(os.path.dirname(__file__))
        root_path = os.path.dirname(current_path)
        server_ip, client_ip = CommandOperation.get_logical_ip_form_config()
        if not self.ssh_ip:
            if not ssh_ip:
                if self.cmd_execute_address == CmdExecuteAdressEnum.SERVER.value:
                    ssh_ip = server_ip
                else:
                    ssh_ip = client_ip
        else:
            ssh_ip = self.ssh_ip
        while True:
            if "scripts" == os.path.basename(root_path):
                sys.path.append(root_path)
                break
            elif root_path == "/":
                raise ValueError
            else:
                root_path = os.path.dirname(root_path)
                sys.path.append(root_path)
        local_file_save_path = os.path.join(root_path, constants.FILE_TEMP_PATH_NAME)
        if "/" in self.remote_file:
            file_basename = self.remote_file.split("/")[-1]
        elif "\\" in self.remote_file:
            file_basename = self.remote_file.split("\\")[-1]
        else:
            file_basename = ""
        full_local_file_path = os.path.join(local_file_save_path, file_basename)
        scp_file_cmd = f"scp -P {test_port} root@{ssh_ip}:" \
                       f"{self.remote_file} {local_file_save_path}"
        rtn_code, output, stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=scp_file_cmd,
            local_execute_flag=True
        )
        log.info(output)
        self.local_file = full_local_file_path
        log.info(f"local_file:{self.local_file}")
        self.full_local_file_path = full_local_file_path
        return full_local_file_path

    def packet_file_parse(self, ssh_ip: str = None):
        """
        :return:
        """
        file_name = self.transport_file_local_path(ssh_ip=ssh_ip)
        packet_list = rdpcap(file_name)
        parse_list = []
        for packet_index in packet_list:
            packet_dict = parse_packet(self.protocol_type, packet_index)
            parse_list.append(packet_dict)
        return parse_list

    def __del__(self):
        if os.path.exists(self.local_file):
            os.remove(self.local_file)
            exec_cmd = f"rm -rf {self.full_local_file_path}"
            rtn_code, output, stderr = CommandOperation.execute_command_with_error(
                cmd=exec_cmd, cmd_execute_address=self.cmd_execute_address)
        else:
            log.info(f"{self.local_file}文件已删除")
        # from scripts.script_libs.file_operation import FileOperation
        # FileOperation.delete_file(path=self.local_file, localpath_flag=True,
        #                           cmd_execute_address=self.cmd_execute_address)


class PacketAssembly(object):
    def __init__(self, cmd_execute_address: str, test_packet_type: str = "",
                 iface: str = "", src_mac: str = "", dst_mac: str = "",
                 src_ip: str = "", dst_ip: str = "", src_port: str = "", dst_port: str = "",
                 vlan: str = "", prio: str = None, vlan_type: int = 0x0800, data_len: int = 100, count: int = 1,
                 ip_chksum: str = "", tcp_chksum: str = "", udp_chksum: str = "", sctp_chksum: str = "",
                 ipv6: bool = False, ether_type: str = '', l4proto: str = '', tos: str = '',
                 enable_tcpdump: bool = False, keep_enable: bool = False, netns_name: str = None,
                 store_file: str = None, inter: float = 0.0, params_value: str = None, cvlan_id: str = None,
                 cvlan_type: str = None, ip_ttl: str = None, cvlan_prio: str = None, ssh_ip: str = None):
        """
        Args:
            cmd_execute_address: 命令执行方向
            test_packet_type:
            iface:源网口名称
            src_mac:源mac地址
            dst_mac: 目标mac地址
            src_ip: 源IP地址
            dst_ip: 目标IP地址
            src_port:源端口号
            dst_port:目标端口号
            vlan: 单层vlan id
            prio: vlan优先级
            vlan_type: 单层vlan的VLAN type
            data_len: 发送报文的数据段长度
            count: 发送报文个数
            ip_chksum: ip 层的checksum值
            tcp_chksum: tcp的checksum值
            udp_chksum
        """
        self.cmd_execute_address = cmd_execute_address
        self.ssh_ip = ssh_ip
        self.test_packet_type, self.iface, self.data_len, self.count, self.inter = \
            test_packet_type, iface, data_len, count, inter

        self.src_mac, self.dst_mac, self.ether_type = src_mac, dst_mac, ether_type
        self.vlan, self.vlan_type, self.prio = vlan, vlan_type, prio
        self.cvlan_id, self.cvlan_type, self.cvlan_prio = cvlan_id, cvlan_type, cvlan_prio
        self.src_ip, self.dst_ip, self.tos, self.ipv6_flag, self.ip_ttl = \
            src_ip, dst_ip, tos, ipv6, ip_ttl

        self.src_port, self.dst_port, self.l4_proto = src_port, dst_port, l4proto
        self.tcp_chksum, self.udp_chksum, self.sctp_chksum = tcp_chksum, udp_chksum, sctp_chksum
        self.ip_chksum = ip_chksum
        self.enable_tcpdump, self.params_vlaue, self.store_file = enable_tcpdump, params_value, store_file
        self.keep_enable = keep_enable
        self.netns_name = netns_name
        self.netns_prefix = self.__netns_exec_prefix_command()
        self.__create_screen_name()
        self.no_need_operate_screen = self.check_screen()
        self.__sum_data_len()

    def __sum_data_len(self):
        ip_header_len = 20
        if self.test_packet_type.upper() in ["IP", "UDP", "TCP", "SCTP", "ICMP", "ICMPV6"]:
            # 计算的是ip中的len,与下一层的长度，ipv4占20, ipv6占40, tcp占20，udp占8，sctp占12
            if self.test_packet_type.upper() == "TCP":
                self.data_len = self.data_len - (ip_header_len + 20)
            elif self.test_packet_type.upper() == "UDP":
                self.data_len = self.data_len - (ip_header_len + 8)
            elif self.test_packet_type.upper() == "SCTP":
                self.data_len = self.data_len - (ip_header_len + 12)
            elif self.test_packet_type.upper() == "ICMP" or self.test_packet_type.upper() == "ICMPV6":
                self.data_len = self.data_len - (ip_header_len + 8)

            else:
                self.data_len = self.data_len - (ip_header_len + 0)
        else:
            log.warning("未指定使用协议类型时，默认使用Ether")
            self.data_len = self.data_len

    def __execute_command(self, cmd):
        log.info(f"execute command is: {cmd}")
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=self.cmd_execute_address, ssh_ip=self.ssh_ip)

        log.info("exec_command:{}, rtn_code:{}, rtn_outputs:{}, rtn_err:{}".
                 format(cmd, rtn_code, rtn_outputs, rtn_err))
        return rtn_code, rtn_outputs, rtn_err

    def __netns_exec_prefix_command(self):
        if self.netns_name:
            prefix_command = f"ip netns exec {self.netns_name} "
        else:
            prefix_command = ""
        return prefix_command

    def __create_ether_packet(self):
        if not self.ether_type:
            ether_packet = f"Ether(src='{self.src_mac}', dst='{self.dst_mac}')/"
        else:
            ether_packet = f"Ether(src='{self.src_mac}', dst='{self.dst_mac}', type={self.ether_type})/"
        if self.vlan and self.ether_type == "0x88a8" and not self.prio:
            svlan_packet = f"Dot1AD(vlan={self.vlan})/"
        elif self.vlan and self.ether_type == "0x88a8" and self.prio:
            svlan_packet = f"Dot1AD(vlan={self.vlan}, prio={self.prio})/"
        elif self.vlan and self.ether_type == "0x8100" and self.prio:
            svlan_packet = f"Dot1Q(vlan={self.vlan}, prio={self.prio})/"
        elif self.vlan and self.ether_type == "0x8100" and not self.prio:
            svlan_packet = f"Dot1Q(vlan={self.vlan})/"
        else:
            svlan_packet = ""
        if self.cvlan_id and self.cvlan_type == "0x88a8" and not self.prio:
            cvlan_packet = f"Dot1AD(vlan={self.cvlan_id})/"
        elif self.cvlan_id and self.cvlan_type == "0x88a8" and self.prio:
            cvlan_packet = f"Dot1AD(vlan={self.cvlan_id}, prio={self.cvlan_prio})/"
        elif self.cvlan_id and self.cvlan_type == "0x8100" and not self.prio:
            cvlan_packet = f"Dot1Q(vlan={self.cvlan_id})/"
        elif self.cvlan_id and self.cvlan_type == "0x8100" and self.prio:
            cvlan_packet = f"Dot1Q(vlan={self.cvlan_id}, prio={self.cvlan_prio})/"
        else:
            cvlan_packet = ""
        return ether_packet + svlan_packet + cvlan_packet

    def __create_nwtwork_datagram(self):
        if self.ipv6_flag:
            ip_version = "IPv6"
        else:
            ip_version = "IP"
        if self.src_ip and not self.dst_ip:
            ip_desc = f"src='{self.src_ip}'"
        elif not self.src_ip and self.dst_ip:
            ip_desc = f"dst='{self.dst_ip}'"
        elif self.src_ip and self.dst_ip:
            ip_desc = f"src='{self.src_ip}', dst='{self.dst_ip}'"
        else:
            ip_desc = ""
        if self.ip_chksum:
            check_sum = f"chksum={self.ip_chksum}"
        else:
            check_sum = ""
        if self.ip_ttl:
            if self.ipv6_flag:
                ttl = f"hlim={self.ip_ttl}"
            else:
                ttl = f"ttl={self.ip_ttl}"
        else:
            ttl = ""
        if self.tos:
            if self.ipv6_flag:
                tos = f"tc={self.tos}"
            else:
                tos = f"tos={self.tos}"
        else:
            tos = self.tos
        ip_packet_list = [ip_desc, check_sum, ttl, tos]

        packet_list = [index for index in ip_packet_list if index != ""]
        if len(packet_list) > 0:
            packet_str = ",".join(packet_list)
            ip_packet = f"{ip_version}({packet_str})/"
        else:
            ip_packet = "IP()/"

        return ip_packet

    def __create_transport_packet(self):
        if self.src_port and not self.dst_port:
            port = f"sport={self.src_port}"
        elif self.dst_port and not self.src_port:
            port = f"dport={self.dst_port}"
        elif self.dst_port and self.src_port:
            port = f"sport={self.src_port}, dport={self.dst_port}"
        else:
            port = ""
        if port and self.l4_proto:
            if self.l4_proto.lower() == "tcp":
                if self.tcp_chksum:
                    transport_packet = f"TCP({port}, checksum={self.tcp_chksum})/"
                else:
                    transport_packet = f"TCP({port})/"
            elif self.l4_proto.lower() == "udp":
                if self.udp_chksum:
                    transport_packet = f"UDP({port}, checksum={self.udp_chksum})/"
                else:
                    transport_packet = f"UDP({port})/"
            elif self.l4_proto.lower() == "sctp":
                if self.sctp_chksum:
                    transport_packet = f"SCTP({port}, checksum={self.sctp_chksum})/"
                else:
                    transport_packet = f"SCTP({port})/"
            elif self.l4_proto.lower() == "icmpv6":
                transport_packet = f"ICMPv6EchoRequest({port})/"
            else:
                transport_packet = self.l4_proto.upper() + f"({port})/"
        elif not port and self.l4_proto:
            if self.l4_proto.lower() == "icmpv6":
                transport_packet = f"ICMPv6EchoRequest()/"
            else:
                transport_packet = self.l4_proto.upper() + "()/"
        else:
            transport_packet = ""

        return transport_packet

    def create_packet_send(self):
        desc_packet = self.__create_ether_packet() + self.__create_nwtwork_datagram() + self.__create_transport_packet()
        data_packet = f"Raw(load='8' * {self.data_len})"
        packet = desc_packet + data_packet
        send_packet_command = f"sendp({packet}, iface='{self.iface}', count={self.count}, inter={self.inter})"
        log.info(f"scapy构报文内容为：{send_packet_command}")
        return send_packet_command

    def run_tcpdump(self):
        if self.params_vlaue:
            tcpdump_command = \
                f"{self.netns_prefix} tcpdump -i {self.iface} -w {self.store_file} -p '{self.params_vlaue}'"
        else:
            tcpdump_command = f"{self.netns_prefix} tcpdump -i {self.iface} -w {self.store_file} -p"
        tcpdump_command = f"nohup timeout 60 {tcpdump_command} & "
        self.__execute_command(cmd=tcpdump_command)

    def start_tcpdump(self):
        run_tcpdump_thread = SxeThread(self.run_tcpdump)
        run_tcpdump_thread.start()
        # run_tcpdump_thread.join(timeout=60)

    def __create_screen_name(self):
        vm, rpc_port = CommonOperation.get_node_info_from_path()
        log.info("vm:{},rpc_port:{}".format(vm, rpc_port))
        vm_path = "{}{}".format(constants.LINUX_FILE_PATH_ROOT, vm)
        self.scapy_screen_name = "scapy_{}".format(vm)
        self.screen_log_path = vm_path
        self.screen_log_name = "screenlog.0"
        if not self.store_file:
            self.store_file = "{}/client_packet.pcap".format(vm_path)

    def check_screen(self):
        if self.keep_enable:
            exec_command = self.netns_prefix + "screen -wipe"
            rtn_code, *_ = self.__execute_command(cmd=exec_command)
            list_screen = self.netns_prefix + "screen -list"
            rtn_code, rtn_stdout, _ = self.__execute_command(cmd=exec_command)
            if self.scapy_screen_name in rtn_stdout:
                return True
            else:
                return False

    def __start_screen(self):
        screen_flag = self.check_screen()
        if not screen_flag:
            # 退出并清除dpdk_testpmd所在screen会话
            exec_command = self.netns_prefix + f"screen -S {self.scapy_screen_name} -X quit"
            self.__execute_command(cmd=exec_command)
            wipe_command = self.netns_prefix + f"screen -wipe"
            self.__execute_command(cmd=wipe_command)
            echo_cmd = self.netns_prefix + f"echo '' > {self.screen_log_path}/{self.screen_log_name}"
            self.__execute_command(cmd=echo_cmd)
            create_screen = f"cd {self.screen_log_path};{self.netns_prefix} screen -L -dmS {self.scapy_screen_name}"
            self.__execute_command(cmd=create_screen)
            # fix_screen = f"cd {self.screen_log_path};{self.netns_prefix} screen -L -dmS {self.scapy_screen_name}"
            # self.__execute_command(cmd=fix_screen)
            # 修改screen日志刷新时间间隔为1s
            fix_screen_time = self.netns_prefix + f"screen -S {self.scapy_screen_name} -X colon 'logfile flush 0.3^M'"
            self.__execute_command(cmd=fix_screen_time)
            # screen内启动scapy
            start_screen_cmd = self.netns_prefix + "screen -x -S {} -p 0 -X stuff 'scapy^M'".format(
                self.scapy_screen_name)
            self.__execute_command(cmd=start_screen_cmd)
            if self.keep_enable:
                self.no_need_operate_screen = True

    def screen_exec_command(self):
        self.__start_screen()
        if self.enable_tcpdump:
            self.start_tcpdump()
        time.sleep(10)
        packet = self.create_packet_send()
        exec_command = self.netns_prefix + f"screen -x -S {self.scapy_screen_name} -p 0 -X stuff \\\"{packet}\\\""
        self.__execute_command(cmd=exec_command)
        finish_exec_command = self.netns_prefix + f"screen -x -S {self.scapy_screen_name} -p 0 -X stuff '^M'"
        self.__execute_command(cmd=finish_exec_command)
        CommonOperation.concat_test_steps(f"{self.cmd_execute_address}:执行命令：{packet}", level=-2)
        iretry = 2 + self.count // 1000
        while iretry:
            time.sleep(1)
            exec_command = "grep -n 'sendp' {}/{}".format(self.screen_log_path, self.screen_log_name) + \
                           " | tail -1 | cut -d: -f1 | xargs -I{{}} tail -n +{{}} " + \
                           "{}/{}".format(self.screen_log_path, self.screen_log_name)
            rtn_code, rtn_stdout, rtn_stderr = self.__execute_command(cmd=exec_command)
            if 'packet.' in rtn_stdout + rtn_stderr:
                log.info("~~~~~~~~~~~send finish log:" + rtn_stdout + f"\n{rtn_stderr}")
                break
            iretry -= 1
        self.__clean_screen__()

    def __clean_screen__(self):
        if not self.no_need_operate_screen:
            time.sleep(1)
            exec_command = self.netns_prefix + f"screen -S {self.scapy_screen_name} -X quit"
            self.__execute_command(cmd=exec_command)
        if self.enable_tcpdump:
            exec_command = f"ps -ef | grep tcpdump | grep '{self.screen_log_path}'" + \
                           " | grep -v grep | awk '{print $2}' | xargs kill -s 2"
            self.__execute_command(cmd=exec_command)


def check_numa_ctl_existence(execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> bool:
    """
    检查numactl是否安装
    """
    is_ubuntu = False
    check_numa_ctl_cmd = 'which numactl'
    rtn_code, _, _, = CommandOperation.execute_command_with_error(
        cmd=check_numa_ctl_cmd, cmd_execute_address=execute_address
    )
    if rtn_code == RtnStatusEnum.SUCCESS.value:
        log.info('当前已经安装numactl工具')
        return True
    else:
        log.info('当前未安装numactl工具')
        check_os_release_cmd = 'cat /etc/os-release'
        _, rtn_outputs, _, = CommandOperation.execute_command_with_error(
            cmd=check_os_release_cmd, cmd_execute_address=execute_address
        )
        if 'Ubuntu' in rtn_outputs or 'debian' in rtn_outputs:
            is_ubuntu = True
        if not is_ubuntu:
            install_numa_ctl_cmd = 'yum install -y numactl'
        else:
            install_numa_ctl_cmd = 'apt install -y numactl'
        _, rtn_outputs, rtn_err, = CommandOperation.execute_command_with_error(
            cmd=install_numa_ctl_cmd, cmd_execute_address=execute_address
        )
        log.info('执行命令: {}, 标准回显: {}, 错误信息: {}'.format(install_numa_ctl_cmd, rtn_outputs, rtn_err))
        log.info('检查numactl工具是否安装成功')
        rtn_code, *_ = CommandOperation.execute_command_with_error(
            cmd=check_numa_ctl_cmd, cmd_execute_address=execute_address
        )
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info('numactl工具安装成功')
            return True
        else:
            log.info('numactl工具安装失败, 退出方法, 返回错误')
            return False


def scgbe_log_check(execute_address: str = CmdExecuteAdressEnum.SERVER.value):
    date = """date +'"%Y-%m-%d;%H:%M:%S.%N"'"""
    rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
        cmd=date, cmd_execute_address=execute_address)
    return rtn_stdout

class IperfOperation(object):
    def __init__(self, case_cls, iperf_version: int, test_device_name: str, cmd_execute_address: str,
                 dct_device_name: str, dct_cmd_execute_address: str, send_time: int,
                 time_sleep: int, parallel_num: int = 1,
                 multicast_address: str = None,
                 fgpa_flag: bool = False,
                 ssh_ip: str = None, dct_ssh_ip: str = None, packet_length: str = None,
                 dualtest_flag: bool = False, port_num: int = 65536, use_tcp: bool = True,
                 cross_numa_flag: bool = False, test_netns: str = None, dct_netns: str = None,
                 iperf_log_file: str = None, back_flag:bool = False, priority: int = 0, bond_flag: bool = False,
                 ):
        """
        Args:
            case_cls: 测试脚本的类名
            iperf_version: iperf的版本.2或者3
            test_device_name: 测试端设备
            cmd_execute_address: 测试端的地址
            dct_device_name:陪测端的设备
            dct_cmd_execute_address: 陪测端地址：CmdExecuteAdressEnum中选择
            multicast_address: 组播地址，如果组播地址不为空，则进行组播测试
            send_time: 运行时间
            parallel_num: 运行的线程数
            time_sleep: 间隔时间，每隔多长时间输出一次iperf日志
            fgpa_flag:表示是否支持查看网口的速率，如果支持设置为True, 否则设置为False
            ssh_ip：测试端的管理IP地址
            dct_ssh_ip:陪测端的管理IP地址
            dualtest_flag: 是否需要设置为双端打流[仅使用于iperf,iperf3不适用]
            packet_length: 发送的包长度
            iperf_log_file: iperf日志文件的路径
            back_flag:是否放到后台执行
        """
        self.case_cls = case_cls
        self.cross_numa_flag = cross_numa_flag
        self.iperf_version = iperf_version
        self.test_device_name = test_device_name
        self.cmd_execute_address = cmd_execute_address
        self.ssh_ip = ssh_ip
        self.dct_device_name = dct_device_name
        self.send_time = send_time
        self.time_sleep = time_sleep
        self.parallel_num = parallel_num
        self.dct_cmd_execute_address = dct_cmd_execute_address
        self.dct_ssh_ip = dct_ssh_ip
        self.null_memory_flag = True
        self.multicast_address = multicast_address
        self.fpga_flag = fgpa_flag
        if not iperf_log_file:
            self.iperf_log_file = "/root/sxetest/iperf_log.log"
        else:
            self.iperf_log_file = iperf_log_file
        self.packet_length = packet_length
        self.bond_flag = bond_flag
        self.port_num = port_num
        self.dualtest_flag = dualtest_flag
        self.use_tcp = use_tcp
        self.test_netns = test_netns
        self.dct_netns = dct_netns
        self.back_flag = back_flag
        self.tos = self.get_iperf_tos(priority=priority)
        if self.multicast_address:
            self.server_params = f" -B {multicast_address} -u dev {self.dct_device_name}"
        else:
            self.server_params = ""
        CommandOperation.execute_command_with_error(cmd="rm -rf /tmp/status.txt",
                                                    cmd_execute_address=self.cmd_execute_address)
        CommandOperation.execute_command_with_error(cmd="rm -rf /tmp/status.txt",
                                                    cmd_execute_address=self.dct_cmd_execute_address)

    def __del__(self):
        # CommandOperation.execute_command_with_error(cmd=f"rm -rf {self.iperf_log_file}",
        #                                             cmd_execute_address=self.cmd_execute_address)
        # CommandOperation.execute_command_with_error(cmd=f"rm -rf {self.iperf_log_file}",
        #                                             cmd_execute_address=self.dct_cmd_execute_address)
        if self.back_flag:
            CommandOperation.execute_command_with_error(cmd="rm -rf /tmp/status.txt", cmd_execute_address=self.cmd_execute_address)
            CommandOperation.execute_command_with_error(cmd="rm -rf /tmp/status.txt",
                                                        cmd_execute_address=self.dct_cmd_execute_address)
            CommandOperation.execute_command_with_error(cmd=f"rm -rf {self.iperf_log_file}", cmd_execute_address=self.cmd_execute_address)
            CommandOperation.execute_command_with_error(cmd=f"rm -rf {self.iperf_log_file}",
                                                        cmd_execute_address=self.dct_cmd_execute_address)
        if self.iperf_version == 2:
            exec_command = f"pkill -ef 'iperf -s -D -p {self.connect_port}'"
        else:
            pass
            # 暂时不执行
            # exec_command = f"pkill -ef 'iperf3 -s -D -p {self.connect_port}'
            # "
        try:
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=self.dct_cmd_execute_address,
                                 ssh_ip=self.dct_ssh_ip)
        except Exception:
            pass

    def get_iperf_tos(cls, priority):
        """
        根据输入的优先级 (0-7) 获取 iperf3 --tos 的十进制值
        逻辑: Priority -> DSCP (CS类别) -> ToS Byte
        """
        if not (0 <= priority <= 7):
            return "错误: 优先级范围必须在 0-7 之间"

        # 1. 映射优先级到 DSCP (Class Selector 模式)
        # 标准公式: DSCP = Priority * 8
        dscp = priority * 8

        # 2. 转换为 ToS 十进制值
        # ToS 字节中，DSCP 占据前 6 位，后 2 位是 ECN (通常为 0)
        # 计算公式: tos = dscp << 2 (等同于 dscp * 4)
        tos = dscp << 2
        return tos

    @staticmethod
    def check_nic_numa(device_name: str, cmd_execute_address: str, ssh_ip, netns:str=None) -> str:
        device_dict = IpOperation.show_ip_link(
            device_name=device_name, cmd_execute_address=cmd_execute_address, netns=netns)
        bus_info = None
        if "link" in list(device_dict.keys()):
            device_name = device_dict.get("link")
        else:
            if "parentbus" not in list(device_dict.keys()) or "parentdev" not in list(device_dict.keys()):
                parent_dev_cmd = f"ip -d link show {device_name} | grep -oP '(?<=dev )[^ ]+'"
                rtn_code, parent_device_name, _ = CommandOperation.execute_command_with_error(cmd=parent_dev_cmd,
                                                                                cmd_execute_address=cmd_execute_address,
                                                                                ssh_ip=ssh_ip)
                if rtn_code == RtnStatusEnum.SUCCESS.value:
                    device_name = re.sub(r"\s+", "", parent_device_name)
        try:
            bus_info = EthtoolOperation.show_driver_infomation(
                device_name=device_name, cmd_execute_address=cmd_execute_address,
                ssh_ip=ssh_ip, nets_name=netns)['bus-info']
        except Exception as e:
            father_device_dict = IpOperation.show_ip_link(
                device_name=device_name, cmd_execute_address=cmd_execute_address, netns=netns)
            if "link" in list(father_device_dict.keys()):
                device_name = father_device_dict.get("link")
            bus_infos = EthtoolOperation.show_driver_infomation(
                device_name=device_name, cmd_execute_address=cmd_execute_address,
                ssh_ip=ssh_ip, nets_name=netns)
            if bus_infos:
                bus_info = bus_infos['bus-info']
        if not bus_info:
            log.info(f'未获取到当前设备{device_name}所属numa节点信息')
            return '-1'
        numa_node_path = '/sys/bus/pci/devices/{}/numa_node'.format(bus_info)
        cmd = 'cat \'{}\''.format(numa_node_path)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
        log.info('执行命令: {}, 标准回显: {}, 错误信息: {}'.format(cmd, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info("当前nic位于numa {}".format(rtn_outputs))
            return rtn_outputs
        else:
            log.info('未获取到当前网卡所属numa节点信息')
            return '-1'

    def check_current_numa_node(self, execute_address: str = CmdExecuteAdressEnum.SERVER.value, ssh_ip: str = None) -> dict:
        node_dict = {}
        exist_flag = check_numa_ctl_existence(execute_address=execute_address)
        if not exist_flag:
            log.info('未安装numactl工具, 无法检查numa信息')
            return node_dict
        check_numa_node_cmd = 'numactl --hardware'
        _, rtn_outputs, _ = CommandOperation.execute_command_with_error(
            cmd=check_numa_node_cmd, cmd_execute_address=execute_address, ssh_ip=ssh_ip
        )
        log.info('numa节点信息: \n{}'.format(rtn_outputs))
        node_list = re.findall(r'node\s+\d+\s+cpus:\s+(.+)', rtn_outputs)
        # log.info('node_list: \n{}'.format(node_list))
        for i in range(len(node_list)):
            node_dict[str(i)] = node_list[i]
        if not self.null_memory_flag:
            memory_list = re.findall(r'node\s+\d+\s+size:\s+(\d+)\s+', rtn_outputs)
            for i in range(len(memory_list)):
                if int(memory_list[i]) == 0:
                    node_dict.pop(str(i))
            for i in node_dict:
                log.info('非空numa节点{}下cpu核列表: {}'.format(i, node_dict[i]))
        else:
            for i in node_dict:
                log.info('全部numa节点{}下cpu核列表: {}'.format(i, node_dict[i]))
        log.info('node_dict: \n{}'.format(node_dict))
        return node_dict

    def select_core_cross_numa(self, nic_numa_node: str, numa_node_dict: dict, core_num: int) -> list:
        """
        author: wei.yuan1
        date: 2024.09.03
        选择跨numa的cpu核心
        """
        distance = 0
        selected_numa_node = 0
        cross_cpu_core_list = []
        if not nic_numa_node or len(numa_node_dict) < 2:
            log.info('当前环境不满足跨numa测试条件')
            self.cross_numa_flag = False
            return cross_cpu_core_list
        if self.cross_numa_flag:
            log.info('计算跨numa节点并获取numa下cpu核心列表')
            for i in numa_node_dict:
                if abs(int(i) - int(nic_numa_node)) > distance:
                    distance = abs(int(i) - int(nic_numa_node))
                    selected_numa_node = int(i)
            log.info('选定的numa节点编号: {}'.format(selected_numa_node))
            cpu_core_list = re.split(r'\s+', numa_node_dict[str(selected_numa_node)])
            if len(cpu_core_list) <= core_num:
                log.info(
                    '选定的numa节点下cpu核数小于等于期望获取的cpu核数{}, 返回numa下全部cpu核心列表'.format(core_num))
                return cpu_core_list
            for _ in range(core_num):
                selected_cpu_core = random.choice(cpu_core_list)
                cross_cpu_core_list.append(selected_cpu_core)
                cpu_core_list.pop(cpu_core_list.index(selected_cpu_core))
            log.info('选定的跨numa的cpu核列表: {}'.format(cross_cpu_core_list))
        else:
            log.info('计算同numa节点并获取numa下cpu核心列表')
            if "-1" == nic_numa_node:
                log.info(f"获取的numa node为-1，取numa_node_dict[0]：{numa_node_dict['0']}")
                cpu_core_list = re.split(r'\s+', numa_node_dict['0'])
            else:
                cpu_core_list = re.split(r'\s+', numa_node_dict[nic_numa_node])
            if len(cpu_core_list) <= core_num:
                log.info(
                    '选定的numa节点下cpu核数小于等于期望获取的cpu核数{}, 返回numa下全部cpu核心列表'.format(core_num))
                return cpu_core_list
            for _ in range(core_num):
                selected_cpu_core = random.choice(cpu_core_list)
                cross_cpu_core_list.append(selected_cpu_core)
                cpu_core_list.pop(cpu_core_list.index(selected_cpu_core))
            log.info('选定的同numa的cpu核列表: {}'.format(cross_cpu_core_list))
        return cross_cpu_core_list

    def set_iperf_demon(self, iperf_version: int, connect_port: str,
                        cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, ssh_ip: str =None):
        """
        设置iperf服务端
        Args:
            iperf_version: iperf版本
            cmd_execute_address: 执行命令的地址
            connect_port: 连接端口
        Returns:

        """
        task_set_exec_cmd = ""
        if self.parallel_num == 1:
            core_num =1
        else:
            core_num = self.parallel_num
        if not self.ssh_ip:
            if not self.bond_flag:
                nic_numa_node = IperfOperation.check_nic_numa(self.dct_device_name, self.dct_cmd_execute_address, self.ssh_ip,
                                                              self.dct_netns)
                numa_node_dict = self.check_current_numa_node(self.dct_cmd_execute_address, self.ssh_ip)
                cross_cpu_core_list = self.select_core_cross_numa(nic_numa_node, numa_node_dict, core_num)
                cross_cpu_core_str = ','.join(cross_cpu_core_list)
            else:
                cross_cpu_core_list = []
                cross_cpu_core_str = ""
        else:
            cross_cpu_core_list = []
            cross_cpu_core_str = ""
        CommonOperation.concat_test_steps("查看当前环境中是否还有活跃的iperf 进程")
        rtn_code, *_ = CommandOperation.execute_command_with_error(
            cmd="pgrep iperf", cmd_execute_address=self.dct_cmd_execute_address, ssh_ip=self.dct_ssh_ip)
        if not self.ssh_ip:
            if len(cross_cpu_core_list) == 1:
                task_set_exec_cmd = 'taskset -c {} '.format(cross_cpu_core_str)
        if iperf_version == 2:
            exec_command = f"{task_set_exec_cmd} iperf -s -D -p {connect_port} {self.server_params}"
            if not self.use_tcp:
                exec_command = exec_command + "-u"
        else:
            exec_command = f"{task_set_exec_cmd} iperf3 -s -D -p {connect_port} {self.server_params}"

        rtn_code, _, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
        CommonOperation.result_collect(
            case_cls=self.case_cls, description=f"server端启动程序：{exec_command}", rtn_code=rtn_code,
            result=f"失败，原因为：{rtn_err}", expect_rtn=RtnStatusEnum.SUCCESS.value,
            expect_info="成功")

    def __iperf_start_demon(self):
        """
        启动iperf服务端
        Args:


        Returns:

        """
        CommonOperation.concat_test_steps("启动iperf服务端")

        random.seed(float(time.time()))
        if self.port_num == 65536:
            self.connect_port = str(random.randint(6000, 10000))
        else:
            self.connect_port = str(self.port_num)
        self.set_iperf_demon(iperf_version=self.iperf_version, cmd_execute_address=self.dct_cmd_execute_address,
                             ssh_ip=self.dct_ssh_ip, connect_port=self.connect_port)

    def udp_flow_bandwidth(self, dst_address: str, bandwidth: str,
                           parallel_num: int, cmd_execute_address: str, iperf_log_file: str, ssh_ip: str = None):
        """
        author: wei.yuan1
        date: 2024.09.03
        description: tcp流量带宽测试
        Args:
            dst_address: 目标地址
            bandwidth: 带宽
            iperf_version: iperf版本
            send_time: 发送时间
            parallel_num: 并行数
            cmd_execute_address: 执行命令的地址
            exec_device: 执行命令的设备
            iperf_log_file: iperf日志文件
        """
        task_set_exec_command = ''
        if not self.ssh_ip:
            if not self.bond_flag:
                nic_numa_node = self.check_nic_numa(device_name=self.test_device_name,
                                                    cmd_execute_address=self.cmd_execute_address, ssh_ip=self.ssh_ip,
                                                    netns=self.test_netns)
                nic_node_dict = self.check_current_numa_node(execute_address=cmd_execute_address)
                cross_cpu_core_list = self.select_core_cross_numa(
                    nic_numa_node=nic_numa_node, numa_node_dict=nic_node_dict, core_num=1)
            else:
                cross_cpu_core_list = []
        else:
            cross_cpu_core_list = []
        if len(cross_cpu_core_list) == 1:
            task_set_exec_command = 'taskset -c {}'.format(cross_cpu_core_list[0])
        elif len(cross_cpu_core_list) > 1:
            task_set_exec_command = 'taskset -c {}'.format(','.join(cross_cpu_core_list))
        else:
            log.info_caller("获取的跨numa节点的core数量小于1，本次测试不绑核")
        local_ip_address = IfConfig.get_device_ipv4_addr(
            device_name=self.test_device_name, cmd_execute_address=self.cmd_execute_address, ssh_ip=self.ssh_ip,
            netns_name=self.test_netns)
        current_bandwidth = ""
        drop_rate = ""
        if self.packet_length:
            packet_desc = f"-l {self.packet_length}"
        else:
            packet_desc = ""
        if self.dualtest_flag:
            if self.iperf_version == 2:
                dualtest = "-d"
            else:
                dualtest = "--bidir"
        else:
            dualtest = ""
        if self.iperf_version == 2:

            exec_command = "{} iperf -u -c {}  -b {}M -t {} -P {} -i {} -p {} -B {} {} {} --tos {}|tee {}".format(
                task_set_exec_command, dst_address, bandwidth, self.send_time,
                parallel_num, self.time_sleep, self.connect_port, local_ip_address, packet_desc, dualtest,
                str(self.tos), iperf_log_file)
        else:
            exec_command = "{} iperf3 -u -c {} -b {}M -t {} -P {} -i {} -p {} -B {} {} --tos {}|tee {}".format(
                task_set_exec_command, dst_address,
                bandwidth, self.send_time, parallel_num, self.time_sleep, self.connect_port, local_ip_address,
                packet_desc, str(self.tos), iperf_log_file)
        if self.test_netns:
            exec_command = "ip netns exec {} {}".format(self.test_netns, exec_command)

        log.info_caller("执行命令：{}".format(exec_command))
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address
        )
        log.info_caller("执行命令返回值：{}".format(rtn_code))
        log.info_caller("标准输出为：{}".format(rtn_stdout))
        if "SUM" in rtn_stdout and rtn_code == RtnStatusEnum.SUCCESS.value:
            if self.iperf_version == 2:
                pattern = r".*?0\.00-.*?(([\d\.]+)\s+[KMGT]?bits/sec).*?\s+([\d\.]+)\s+ms.*?\(([\d\.e\+\-]+)%\)"
                all_info = re.findall(pattern, rtn_stdout)
                log.info(f"all_info:{all_info}")
                if all_info:
                    current_bandwidth, _, jitter, drop_rate = all_info[-1]
            else:
                pattern = r"\[SUM\].*?0\.00-.*?(([\d\.]+)\s+[KMGT]?bits/sec).*?\s+([\d\.]+)\s+ms.*?\(([\d\.e\+\-]+)%\).*?receiver"
                current_bandwidth, bandwidth_value,jitter, drop_rate = re.findall(pattern, rtn_stdout)[-1]
        elif "SUM" not in rtn_stdout and rtn_code == RtnStatusEnum.SUCCESS.value:
            if self.iperf_version == 2:
                pattern = r".*?0\.00-.*?\s+([\d\.]+).*?(([\d\.]+)\s+[KMGT]?bits/sec).*?\s+([\d\.]+)\s+ms.*?\(([\d\.e\+\-]+)%\)"
                # bandwidth_value, bandwidth_unit, jitter, drop_rate= re.findall(pattern, rtn_stdout)[-1]
                # current_bandwidth = bandwidth_value + bandwidth_unit
                if not self.multicast_address:
                    _, current_bandwidth, _, jitter, drop_rate = re.findall(pattern, rtn_stdout)[-1]
                else:
                    try:
                        bandwidth_value, bandwidth_unit, drop_rate = re.findall(pattern, rtn_stdout)[-1]
                    except IndexError as e:
                        pattern = r".*?0\.00-.*?\s+([\d\.]+).*?(([\d\.]+)\s+[KMGT]?bits/sec).*?"
                        current_bandwidth = re.findall(pattern, rtn_stdout)[-1][1]
                        current_bandwidth = current_bandwidth.replace(" ", "")

            else:
                pattern = r".*?0\.00-.*?\s+[\d\.]+.*?([\d\.]+)\s+([KMGT]?bits/sec).*?\(([\d\.e\+\-]+)%\).*?receiver"
                infos = re.findall(pattern, rtn_stdout)
                if not infos:
                    current_bandwidth = ""
                    drop_rate = ""
                    log.info_caller("打流失败")
                    CommonOperation.result_collect(
                        case_cls=self.case_cls, description="使用iperf打流",
                        result=f"Fail, error_message:{rtn_stderr}", rtn_code=rtn_code,
                        expect_rtn=RtnStatusEnum.SUCCESS.value,
                        expect_info="SUCCESS"
                    )
                else:
                    bandwidth_value, bandwidth_unit, drop_rate = infos[-1]
                    current_bandwidth = bandwidth_value + bandwidth_unit

        # if "SUM" in rtn_stdout and rtn_code == RtnStatusEnum.SUCCESS.value:
        #     log.info_caller("打流成功")
        #     log.info_caller(rtn_stdout)
        #     rtn_output = rtn_stdout.replace("\r", "")
        #     for index in rtn_output.split("\n"):
        #         pattern = fr'\b({str(self.send_time - 1)}\.5|{str(self.send_time)}(\.0)?|{str(self.send_time + 1)}(\.0)?|\
        #                 {str(self.send_time + 2)}(\.0)?|{str(self.send_time + 3)}\.9)\b'
        #         matches = re.findall(pattern, index)
        #         # 过滤掉捕获组中的空字符串
        #         filtered_matches = [match[0] for match in matches]
        #         if self.iperf_version == 2:
        #             if "SUM" in index and "0.00" in index and len(filtered_matches) != 0 and (
        #                     f"{str(self.send_time - self.time_sleep)}.0") not in index:
        #                 current_bandwidth = re.search(r"([0-9]+\.?[0-9]*)\s*([KMGT]?bits/sec)", index).group()
        #                 drop_rate = re.search(r"\(([\d.]+)%\)", index).group(1)
        #                 break
        #             else:
        #                 current_bandwidth = ""
        #                 drop_rate = ""
        #         else:
        #             try:
        #                 pattern = re.compile(r"\[SUM\].*?(\d+(?:\.\d+)?\s[KMGT]?bits/sec).*?\((\d+)%\)\s+receiver",
        #                                      re.VERBOSE)
        #                 current_bandwidth = pattern.search(index)[1]
        #                 drop_rate = pattern.search(index)[2]
        #             except Exception as e:
        #                 pass
        #     else:
        #         if not current_bandwidth:
        #             pattern = re.compile(r"\[SUM\].*?(\d+(?:\.\d+)?\s[KMGT]?bits/sec).*?\((\d+)%\)\s+receiver",
        #                                  re.VERBOSE)
        #             current_bandwidth = pattern.search(rtn_output)[1]
        #             drop_rate = pattern.search(rtn_output)[2]
                    #     if ("SUM" in index and "0.00" in index and
                    #             f"{str(self.send_time - self.time_sleep)}.0" not in index and
                    #             len(filtered_matches) != 0 and "receiver" in index):
                    #         current_bandwidth = re.search(r"([0-9]+\.?[0-9]*)\s*([KMGT]bits/sec)", index).group()
                    #         drop_rate = re.search(r"\(([\d.]+)%\)", index).group(1)
                    #         break
                    #     else:
                    #         current_bandwidth = ""
                    #         drop_rate = ""
                    # except Exception as e:
                    #     pattern = re.compile(r"\[SUM\].*?(\d+\.\d+\s[KMGT]bits/sec).*?\((\d+)%\)\s+receiver", re.VERBOSE)
                    #     current_bandwidth = pattern.search(index)[1]
                    #     drop_rate = pattern.search(index)[2]
        # elif "SUM" not in rtn_stdout and rtn_code == RtnStatusEnum.SUCCESS.value:
        #     log.info_caller("打流成功")
        #     log.info_caller(rtn_stdout)
        #     if self.iperf_version == 2:
        #         try:
        #             pattern = re.compile(r"\[\s+\d+\].*?(\d+(?:\.\d+)?\s[KMGT]?bits/sec).*?\((\d+)%\)\s+receiver", re.VERBOSE)
        #             matches = pattern.search(rtn_stdout)
        #             current_bandwidth = matches[1]
        #             drop_rate = matches[2]
        #         except Exception as e:
        #             rtn_output = rtn_stdout.replace("\r", "")
        #             for index in rtn_output.split("\n"):
        #                 pattern = fr'^(0\.\d+)-({str(self.send_time)}\.\d+) sec$'
        #                 if self.iperf_version == 2:
        #                     if ("0.00" in index and f"{str(self.send_time)}.0" in index
        #                             and f"{str(self.send_time - self.time_sleep)}.0" not in index):
        #                         pattern = re.compile(r"\[\s+\d+\].*?(\d+(?:\.\d+)?\s[KMGT]?bits/sec).*?", re.VERBOSE)
        #                         matches = pattern.search(index)
        #                         current_bandwidth = matches[1]
        #                         try:
        #                             drop_rate = matches[2]
        #                         except Exception as e:
        #                             drop_rate = ""
        #                         break
        #             else:
        #                 current_bandwidth = ""
        #                 drop_rate = ""
        #     else:
        #         pattern = re.compile(r"\[\s+\d+\].*?([\d+\.]\d+\s[KMGT]?bits/sec).*?\(([\d.eE-]+)%\)\s+receiver", re.VERBOSE)
        #         matches = pattern.search(rtn_stdout)
        #         current_bandwidth = matches[1]
        #         drop_rate = matches[2]

        else:
            current_bandwidth = ""
            drop_rate = ""
            log.info_caller("打流失败")
            CommonOperation.result_collect(
                case_cls=self.case_cls, description="使用iperf打流",
                result=f"Fail, error_message:{rtn_stderr}", rtn_code=rtn_code,
                expect_rtn=RtnStatusEnum.SUCCESS.value,
                expect_info="SUCCESS"
            )
        return current_bandwidth.replace(" ", ""), drop_rate

    def tcp_flow_bandwidth(self, dst_address: str, bandwidth: str,
                           parallel_num: int, cmd_execute_address: str, iperf_log_file: str, ssh_ip: str = None):
        """
        author: wei.yuan1
        date: 2024.09.03
        description: tcp流量带宽测试
        Args:
            dst_address: 目标地址
            bandwidth: 带宽
            parallel_num: 并行数
            cmd_execute_address: 执行命令的地址
            iperf_log_file: iperf日志文件
        """
        task_set_exec_command = ''
        if not self.ssh_ip:
            if not self.bond_flag:
                nic_numa_node = IperfOperation.check_nic_numa(
                    device_name=self.test_device_name, cmd_execute_address=self.cmd_execute_address, ssh_ip=self.ssh_ip,
                    netns=self.test_netns)
                nic_node_dict = self.check_current_numa_node(execute_address=cmd_execute_address)
                cross_cpu_core_list = self.select_core_cross_numa(
                    nic_numa_node=nic_numa_node, numa_node_dict=nic_node_dict, core_num=1)
            else:
                cross_cpu_core_list = []
        else:
            cross_cpu_core_list = []
        if len(cross_cpu_core_list) == 1:
            task_set_exec_command = 'taskset -c {}'.format(cross_cpu_core_list[0])
        elif len(cross_cpu_core_list) > 1:
            task_set_exec_command = 'taskset -c {}'.format(','.join(cross_cpu_core_list))
        else:
            log.info_caller("获取的跨numa节点的core数量小于1，本次测试不绑核")
        local_ip_address = IfConfig.get_device_ipv4_addr(
            device_name=self.test_device_name, cmd_execute_address=self.cmd_execute_address, ssh_ip=self.ssh_ip,
            netns_name=self.test_netns)
        current_bandwidth = ""
        if self.packet_length:
            packet_desc = f"-l {self.packet_length}"
        else:
            packet_desc = ""
        if self.dualtest_flag:
            if self.iperf_version == 2:
                dualtest = "-d"
            else:
                dualtest = "--bidir"
        else:
            dualtest = ""

        if self.back_flag:
            if self.iperf_version == 2:
                if task_set_exec_command:
                    exec_command = (f"nohup stdbuf -oL '{task_set_exec_command} iperf -c {dst_address}  -b {bandwidth}M"
                                    f" -t {self.send_time} -P {parallel_num} -i {self.time_sleep} -p {self.connect_port}"
                                    f" -B {local_ip_address} --tos {str(self.tos)} {packet_desc} {dualtest} 2>&1 >{iperf_log_file} &&"
                                    f" echo SUCCESS > /tmp/status.txt' > /dev/null 2>&1 < /dev/null &")
                else:
                    exec_command = (f"nohup stdbuf -oL 'iperf -c {dst_address}  -b {bandwidth}M"
                                    f" -t {self.send_time} -P {parallel_num} -i {self.time_sleep} -p {self.connect_port}"
                                    f" -B {local_ip_address} --tos {str(self.tos)} {packet_desc} {dualtest} 2>&1 >{iperf_log_file} &&"
                                    f" echo SUCCESS > /tmp/status.txt' > /dev/null 2>&1 < /dev/null &")
            else:
                if task_set_exec_command:
                    exec_command = (f" nohup sh -c '{task_set_exec_command} iperf3 -c {dst_address} -b {bandwidth}M"
                                    f" -t {self.send_time} -P {parallel_num} -i {self.time_sleep} -p {self.connect_port}"
                                    f" -B {local_ip_address}  {packet_desc} --tos {str(self.tos)}  {dualtest} --forceflush 2>&1 |tee -a {iperf_log_file}"
                                    f" && echo SUCCESS > /tmp/status.txt' > /dev/null 2>&1 < /dev/null &")
                else:
                    exec_command = (f" nohup sh -c 'iperf3 -c {dst_address} -b {bandwidth}M"
                                    f" -t {self.send_time} -P {parallel_num} -i {self.time_sleep} -p {self.connect_port}"
                                    f" -B {local_ip_address}  {packet_desc} --tos {str(self.tos)}  {dualtest} --forceflush 2>&1 |tee -a {iperf_log_file}"
                                    f" && echo SUCCESS > /tmp/status.txt' > /dev/null 2>&1 < /dev/null &")
        else:
            if self.iperf_version == 2:
                # 当用户选择为iperf2时,默认选择为双端打流
                exec_command = "{} iperf -c {}  -b {}M -t {} -P {} -i {} -p {} -B {} {} {} --tos {} {}|tee {}".format(
                    task_set_exec_command, dst_address, bandwidth, self.send_time,
                    parallel_num, self.time_sleep, self.connect_port, local_ip_address, packet_desc, dualtest,
                    str(self.tos), dualtest, iperf_log_file)
            else:
                exec_command = "{} iperf3 -c {} -b {}M -t {} -P {} -i {} -p {} -B {} {} --tos {} {}|tee {}".format(
                    task_set_exec_command, dst_address,
                    bandwidth, self.send_time, parallel_num, self.time_sleep, self.connect_port, local_ip_address,
                    packet_desc, str(self.tos), dualtest, iperf_log_file)

        if self.test_netns:
            exec_command = f"ip netns exec {self.test_netns} {exec_command}"
        log.info_caller("执行命令：{}".format(exec_command))
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip
        )
        log.info_caller("执行命令返回值：{}".format(rtn_code))
        log.info_caller("标准输出为：{}".format(rtn_stdout))
        if not self.back_flag:
            if rtn_code == RtnStatusEnum.SUCCESS.value and "SUM" in rtn_stdout:
                if self.iperf_version == 2:
                    regex_pattern = r'\[SUM\].*?0\.00-.*?(([\d\.]+)\s+[KMG]?bits/sec).*?'
                else:
                    regex_pattern = r'\[SUM\].*?0\.00-.*?(([\d\.]+)\s+[KMG]?bits/sec).*?receiver'
                current_bandwidth_list = re.findall(regex_pattern, rtn_stdout)
                if current_bandwidth_list:
                    current_bandwidth, current_bandwidth_val = current_bandwidth_list[-1]
            elif "SUM" not in rtn_stdout and rtn_code == RtnStatusEnum.SUCCESS.value:
                if self.iperf_version == 2:
                    regex_pattern = r'.*?0\.00-.*?(([\d\.]+)\s+[KMG]?bits/sec).*?'
                else:
                    regex_pattern = r'.*?0\.00-.*?(([\d\.]+)\s+[KMG]?bits/sec).*?receiver'
                current_bandwidth_list = re.findall(regex_pattern, rtn_stdout)
                if current_bandwidth_list:
                    current_bandwidth, current_bandwidth_val = current_bandwidth_list[-1]
            else:
                current_bandwidth = ""
                log.info_caller("打流失败")
                CommonOperation.result_collect(
                    case_cls=self.case_cls, description="使用iperf打流",
                    result=f"Fail, error_message:{rtn_stderr}", rtn_code=rtn_code,
                    expect_rtn=RtnStatusEnum.SUCCESS.value,
                    expect_info="SUCCESS"
                )
            # if "SUM" in rtn_stdout and rtn_code == RtnStatusEnum.SUCCESS.value:
            #     log.info_caller("打流成功")
            #     log.info_caller(rtn_stdout)
            #     rtn_output = rtn_stdout.replace("\r", "")
            #     for index in rtn_output.split("\n"):
            #         pattern = fr'\b({str(self.send_time - 1)}\.5|{str(self.send_time)}(\.0)?|{str(self.send_time + 1)}(\.0)?|\
            #                 {str(self.send_time + 2)}(\.0)?|{str(self.send_time + 3)}\.9)\b'
            #         matches = re.findall(pattern, index)
            #         # 过滤掉捕获组中的空字符串
            #         filtered_matches = [match[0] for match in matches]
            #         if self.iperf_version == 2:
            #             if "SUM" in index and "0.00" in index and len(filtered_matches) != 0 and (
            #                     f"{str(self.send_time - self.time_sleep)}.0") not in index:
            #                 current_bandwidth = re.search(r"([0-9]+\.?[0-9]*)\s*([KMGT]?bits/sec)", index).group()
            #                 break
            #             else:
            #                 current_bandwidth = ""
            #         else:
            #             if ("SUM" in index and "0.00" in index and
            #                     f"{str(self.send_time - self.time_sleep)}.0" not in index and
            #                     len(filtered_matches) != 0 and "receiver" in index):
            #                 current_bandwidth = re.search(r"([SUM]\s+[0.0*]+\.?[0-9]*)\s*([KMGT]?bits/sec)", index).group()
            #                 break
            #             else:
            #                 current_bandwidth = ""
            #
            # elif "SUM" not in rtn_stdout and rtn_code == RtnStatusEnum.SUCCESS.value:
            #     log.info_caller("打流成功")
            #     log.info_caller(rtn_stdout)
            #     rtn_output = rtn_stdout.replace("\r", "")
            #     for index in rtn_output.split("\n"):
            #         pattern = fr'^(0\.\d+)-({str(self.send_time)}\.\d+) sec$'
            #         if self.iperf_version == 2:
            #             if ("0.00" in index and f"{str(self.send_time)}.0" in index
            #                     and f"{str(self.send_time - self.time_sleep)}.0" not in index):
            #                 current_bandwidth = re.search(r"([0-9]+\.?[0-9]*)\s*([KMGT]?bits/sec)", index).group()
            #                 break
            #             else:
            #                 current_bandwidth = ""
            #         else:
            #             show_time = self.send_time - self.time_sleep
            #
            #             if ("0.00" in index and bool(re.search(pattern=fr"{str(self.send_time)}.?[0-9]*", string=index))
            #                     and not bool(re.search(pattern=fr"{str(show_time)}.?[0-9]*", string=index)) and "receiver" in index):
            #                 current_bandwidth = re.search(r"([0-9]+\.?[0-9]*)\s*([KMGT]?bits/sec)", index).group()
            #                 break
            #             else:
            #                 current_bandwidth = ""

        else:
            count = self.send_time // self.time_sleep
            while count >= 0:
                time.sleep(5)
                count -= 1
                grep_rtn_code, *_ = CommandOperation.execute_command_with_error(
                    cmd="grep SUCCESS /tmp/status.txt", cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
                if grep_rtn_code == RtnStatusEnum.SUCCESS.value:
                    break
                else:
                    continue
            else:
                log.error_caller("打流失败")
                CommonOperation.result_collect(
                    case_cls=self.case_cls, description="使用iperf打流",
                    result=f"Fail, error_message: iperf打流失败", rtn_code=rtn_code,
                    expect_rtn=RtnStatusEnum.SUCCESS.value,
                    expect_info="SUCCESS")
            _, iperf_result_context, _ = CommandOperation.execute_command_with_error(
                cmd=f"cat {iperf_log_file}", cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
            # iperf_result_context = iperf_result_context.decode()
            if self.iperf_version == 3:
                if int(self.parallel_num) != 1:
                    regex_pattern = r'\[SUM\].*?0\.00-.*?(([\d\.]+)\s+[KMG]?bits/sec).*?receiver'
                else:
                    regex_pattern = r'.*?0\.00-.*?(([\d\.]+)\s+[KMG]?bits/sec).*?receiver'
            else:
                if int(self.parallel_num) != 1:
                    regex_pattern =  r'\[SUM\].*?0\.00-.*?(([\d\.]+)\s+[KMG]?bits/sec).*?'
                else:
                    regex_pattern = r'.*?0\.00-.*?(([\d\.]+)\s+[KMG]?bits/sec).*?'
            current_bandwidth_list = re.findall(regex_pattern, iperf_result_context)
            if current_bandwidth_list:
                current_bandwidth, current_bandwidth_val = current_bandwidth_list[-1]
            else:
                current_bandwidth = ""

        return current_bandwidth.replace(" ", "")

    def iperf_tcp_test(self, create_bug:bool = True):
        """
        进行tcp 带宽测试
        """
        drop_rate = ""
        self.__iperf_start_demon()
        test_speed = 0
        if not self.fpga_flag:
            try:
                interface_speed = EthtoolOperation.show_driver_setting(
                    device_name=self.test_device_name,
                    cmd_execute_address=self.cmd_execute_address, ssh_ip=self.ssh_ip)["Speed"].strip()
                interface_speed = re.findall(r"([0-9]+\.?[0-9]*)", interface_speed)
            except KeyError:
                interface_speed = ["25000", "M"]
        else:
            interface_speed = ["1000", "M"]
        if not self.multicast_address:
            origin_dst_addr = IfConfig.get_device_ipv4_addr(
                device_name=self.dct_device_name, cmd_execute_address=self.dct_cmd_execute_address, ssh_ip=self.dct_ssh_ip)
            dst_addr_list = IpOperation.show_device_addr(device_name=self.dct_device_name, cmd_execute_address=self.dct_cmd_execute_address, ssh_ip=self.dct_ssh_ip)["inet"]
            origin_source_addr = IfConfig.get_device_ipv4_addr(device_name=self.test_device_name, cmd_execute_address=self.cmd_execute_address, ssh_ip=self.ssh_ip, netns_name=self.test_netns)
            if len(dst_addr_list) > 1:
                dst_addr = [addr for addr in dst_addr_list if ".".join(origin_source_addr.split(".")[:-1]) in addr ][0]
                # dst_addr = dst_addr_list[1]
            else:
                dst_addr = origin_dst_addr
        else:
            dst_addr = self.multicast_address
        if self.use_tcp:
            current_speed = self.tcp_flow_bandwidth(
                dst_address=dst_addr, bandwidth=interface_speed[0],
                parallel_num=self.parallel_num, cmd_execute_address=self.cmd_execute_address, ssh_ip=self.ssh_ip,
                iperf_log_file=self.iperf_log_file
            )

        else:
            current_speed, drop_rate = self.udp_flow_bandwidth(
                dst_address=dst_addr, bandwidth=interface_speed[0],
                parallel_num=self.parallel_num, cmd_execute_address=self.cmd_execute_address, ssh_ip=self.ssh_ip,
                iperf_log_file=self.iperf_log_file
            )
        log.info(f"当前速率current_speed：{current_speed}")
        if "." in current_speed:
            match = re.match(r"([0-9]*\.?[0-9]+)([A-Za-z\/]+)", current_speed)
        else:
            match = re.match(r'(\d+)([A-Za-z/]+)', current_speed)
            # match = re.match(r"([0-9]*\.?[0-9]+)([A-Za-z\/]+)", current_speed)

        speed_value = ''
        speed_unit = ''

        if create_bug:
            if match is not None:
                speed_value, speed_unit = match[1], match[2]
            else:
                log.info_caller("打流失败")
                CommonOperation.result_collect(
                    case_cls=self.case_cls, description="使用iperf打流",
                    result=f"Fail, error_message: iperf打流失败", rtn_code=False,
                    expect_rtn=RtnStatusEnum.SUCCESS.value,
                    expect_info="SUCCESS")

            if speed_unit == "Gbits/sec":
                test_speed = float(speed_value) * 1000
            elif speed_unit == "Mbits/sec":
                test_speed = float(speed_value)
            elif speed_unit == "Kbits/sec":
                test_speed = float(speed_value) / 1000
            else:
                test_speed = float(speed_value) / 1000 / 1000
            if self.use_tcp:
                return test_speed, "Mbps"
            else:
                return test_speed, drop_rate
        else:
            return 0, "Mbps"

    def udp_throughput_test(self):
        self.__iperf_start_demon()
        test_speed = 0
        if not self.fpga_flag:
            interface_speed = EthtoolOperation.show_driver_setting(
                device_name=self.test_device_name,
                cmd_execute_address=self.cmd_execute_address, ssh_ip=self.ssh_ip)["Speed"].strip()
            interface_speed = re.findall(r"([0-9]+\.?[0-9]*)", interface_speed)
        else:
            interface_speed = ["1000", "M"]
        dst_addr = IfConfig.get_device_ipv4_addr(
            device_name=self.dct_device_name, cmd_execute_address=self.dct_cmd_execute_address, ssh_ip=self.dct_ssh_ip)

    def transport_file_local_path(self, cmd_execute_address, ssh_ip: str = None):
        """
        author: wei.yuan1
        date: 2024.07.20
        description: 文件传输
        """
        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            test_port = test_port
        else:
            test_port = 22
        current_path = os.path.abspath(os.path.dirname(__file__))
        root_path = os.path.dirname(current_path)
        if not ssh_ip:
            server_ip, client_ip = CommandOperation.get_logical_ip_form_config()
            if cmd_execute_address == CmdExecuteAdressEnum.SERVER.value:
                ssh_ip = server_ip
            else:
                ssh_ip = client_ip
        while True:
            if "scripts" == os.path.basename(root_path):
                sys.path.append(root_path)
                break
            elif root_path == "/":
                raise ValueError
            else:
                root_path = os.path.dirname(root_path)
                sys.path.append(root_path)
        local_file_save_path = os.path.join(root_path, constants.FILE_TEMP_PATH_NAME)
        if "/" in self.iperf_log_file:
            file_basename = self.iperf_log_file.split("/")[-1]
        elif "\\" in self.iperf_log_file:
            file_basename = self.iperf_log_file.split("\\")[-1]
        else:
            file_basename = ""
        full_local_file_path = os.path.join(local_file_save_path, file_basename)
        scp_file_cmd = f"scp -P {test_port} root@{ssh_ip}:" \
                       f"{self.iperf_log_file} {local_file_save_path}"
        rtn_code, output, stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=scp_file_cmd,
            local_execute_flag=True
        )
        log.info(output)
        return full_local_file_path

    def parse_file(self):
        """
        author: wei.yuan1
        date: 2024.07.26
        description: 解析测试结果
        """

        # local_path = cls.transport_file_local_path(cmd_execute_address=cls.exec_address)
        local_path = self.transport_file_local_path(cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_ip=self.ssh_ip)
        data_list = []
        with open(local_path, "r") as f:
            data = f.readlines()
            for line in data:
                if self.parallel_num != 1:
                    if "SUM" in line:
                        data_list.append(line)
                else:
                    if "sec" in line:
                        data_list.append(line)
        for line_data in data_list:
            try:
                current_bandwidth = re.search(r"[0-9]+\.?\d+\s*([KMGT]?bits/sec)", line_data).group()
            except AttributeError as e:
                current_bandwidth = re.search(r"\d+\s*([KMGT]?bps)", line_data).group()
            current_bandwidth = current_bandwidth.replace(" ", "")
            if "." in current_bandwidth:
                match = re.match(r"([0-9]*\.?[0-9]+)([A-Za-z\/]+)", current_bandwidth)
            else:
                match = re.match(r'(\d+)([A-Za-z/]+)', current_bandwidth)
            speed_value, speed_unit = match[1], match[2]
            time_match = re.search(r'(\d+\.\d+-\d+\.\d+) sec', line_data)
            if time_match:
                time_value = time_match.group(1)
            else:
                time_value = ""
            rtn_code = False if float(speed_value) <= float(1) else True
            CommonOperation.result_collect(
                case_cls=self.case_cls, description=f"在時間段{time_value}中，网口的带宽值是否跌0",
                result=f"当前时间段内网卡的带宽值为{current_bandwidth}",
                expect_rtn=True,
                expect_info=f"当前时间段内网卡的带宽值为{current_bandwidth}",
                rtn_code=rtn_code
            )
        # 删除本地的iperf log 日志
        FileOperation.delete_file(path=local_path, localpath_flag=True)
        FileOperation.delete_file(
            path=self.iperf_log_file, localpath_flag=False, cmd_execute_address=self.cmd_execute_address)


class QPerf(object):
    def __init__(self, case_cls, rx_device_name: str,
                 msg_size: str, ether_type: str = "ipv4",
                 server_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                 client_execute_address: str = CmdExecuteAdressEnum.SERVER.value
                 ):
        self.case_cls = case_cls
        self.rx_device_name = rx_device_name
        self.server_exec_address = server_execute_address
        self.client_exec_address = client_execute_address
        self.msg_size = msg_size
        self.ether_type = ether_type
        if self.ether_type == "ipv4":
            self.rx_device_ip = IfConfig.get_device_ipv4_addr(
                device_name=self.rx_device_name, cmd_execute_address=self.server_exec_address
            )
        else:
            self.rx_device_ip = IfConfig.get_device_ipv6_addr(
                device_name=self.rx_device_name, cmd_execute_address=self.server_exec_address
            )

    def __del__(self):
        CommandOperation.execute_command_with_error(cmd="pkill -ef qperf", cmd_execute_address=self.server_exec_address)
        CommandOperation.execute_command_with_error(cmd="pkill -ef qperf", cmd_execute_address=self.client_exec_address)
        CommandOperation.execute_command_with_error(
            cmd=f"rm -rf {constants.vm_path}/qperf.log", cmd_execute_address=self.client_exec_address)

    def __server_process(self):
        exec_command = "nohup qperf &"
        CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.server_exec_address)
        # CommonOperation.result_collect(case_cls=self.case_cls, expect_rtn=RtnStatusEnum.SUCCESS.value,
        #                                rtn_code=rtn_code, description="server端启动qperf", result=f"失败,reason:{rtn_err}",
        #                                expect_info="成功"
        #                                )

    def __client_process(self):
        exec_command = f" nohup qperf {self.rx_device_ip} -oo msg_size:{self.msg_size} -vu tcp_lat udp_lat > {constants.vm_path}/qperf.log &"
        rtn_code, *_ = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.client_exec_address
        )
        while True:
            time.sleep(2)
            exec_cmd = f"ps -ef|grep 'qperf {self.rx_device_ip}'|grep -v 'color'"
            rtn_code, *_ = CommandOperation.execute_command_with_error(
                cmd=exec_cmd, cmd_execute_address=self.client_exec_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                break
            else:
                continue

    def start_qperf_test(self):
        """
        进行qperf测试
        :return:
        """
        server_thread = SxeThread(self.__server_process)
        client_thread = SxeThread(self.__client_process)
        server_thread.start()
        time.sleep(2)
        client_thread.start()

        client_thread.join()
        exec_cmd = f"pkill -ef qperf"
        rtn_code, *_ = CommandOperation.execute_command_with_error(
            cmd=exec_cmd, cmd_execute_address=self.server_exec_address)
        server_thread.join(timeout=10)
        rtn_code, rtn_stdout, _ = CommandOperation.execute_command_with_error(
            cmd=f"cat {constants.vm_path}/qperf.log", cmd_execute_address=self.client_exec_address)
        result_dict = {}
        current_section = None
        current_bw = None
        current_msg_rate = None
        lines = rtn_stdout.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line.endswith(':'):
                # 识别新的测试部分
                current_section = line[:-1]
                if current_section not in result_dict:
                    result_dict[current_section] = {}
            elif line.startswith('bw'):
                # 提取带宽值
                current_bw = line.split('=')[1].strip().split(" ")[0]
            elif line.startswith('latency'):
                # 提取延迟值
                current_bw = line.split('=')[1].strip().split(" ")[0]

            elif line.startswith('msg_size'):
                # 提取消息速率值
                current_msg_rate = line.split('=')[1].strip().split(" ")[0]
                if current_section and current_bw and current_msg_rate:
                    result_dict[current_section][current_msg_rate] = current_bw
                    current_bw = None
                    current_msg_rate = None
        return result_dict

    def create_file(self, result_dict):
        current_path = os.path.abspath(os.path.dirname(__file__))
        root_path = os.path.dirname(current_path)
        while True:
            if "scripts" == os.path.basename(root_path):
                sys.path.append(root_path)
                break
            elif root_path == "/":
                raise ValueError
            else:
                root_path = os.path.dirname(root_path)
                sys.path.append(root_path)

        local_file_save_path = os.path.join(root_path, constants.FILE_TEMP_PATH_NAME)
        now_time = datetime.datetime.strftime(datetime.datetime.today(),"%Y_%m_%d_%H")
        remote_file_name =  os.path.join(local_file_save_path, f"perf_result_{now_time}.json")

        with open(remote_file_name, "w+") as json_file:
            json.dump(result_dict, json_file, indent=4)
        server_ip, client_ip = CommandOperation.get_logical_ip_form_config()
        if self.client_exec_address == CmdExecuteAdressEnum.SERVER.value:
            target_ip = server_ip
        else:
            target_ip = client_ip

        FileOperation.scp_file(source_file_path=remote_file_name, target_file_path=f"{constants.vm_path}/",
                               target_ip=target_ip,local_execute=True)



if __name__ == '__main__':
    # qperf = QPerf(case_cls=ScriptBase, rx_device_name="ens4f1", msg_size="64:1518:*2", ether_type="ipv4",
    #       server_execute_address=CmdExecuteAdressEnum.CLIENT.value, client_execute_address=CmdExecuteAdressEnum.SERVER.value)
    # qperf_dict = qperf.start_qperf_test()
    # a = qperf_dict
    # print(a)
    # qperf.create_file(result_dict=qperf_dict)
    # del qperf
    # a = scgbe_log_check(CmdExecuteAdressEnum.SERVER.value)
    # print(a)
    # packet_object = PacketAssembly(cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, iface="ens1f0",
    #                                src_mac="50:7c:6f:05:95:22", dst_mac="50:7c:6f:07:1d:c9",
    #                                vlan="100", prio=1, count=100, ether_type="0x88a8")
    # packet_object.screen_exec_command()
    # del packet_object
    #
    iperf_object = IperfOperation(case_cls=ScriptBase, iperf_version=3, test_device_name="ens6f1",
                                  dct_device_name="ens6f1", dct_cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                  cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, fgpa_flag=False,
                                  send_time=60, time_sleep=5, parallel_num=16, packet_length="1518", use_tcp=True,
                                  back_flag=True)
    current_speed, unit = iperf_object.iperf_tcp_test()
    print(current_speed, unit)
    del iperf_object
    # a = create_different_network_ip("192.145.16.70")
    # print(a)
    # all_info_list = debugfs_interface_mmcat(case_cls=BridgeOperation, device_name="ens4f0",
    #                                         cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)

    # rtn_dict = get_interface_broadcast_address("ens4f1", cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    # ether_type = 0x900
    # print(json.dumps(rtn_dict))
    # packet = Ether(dst="ff:ff:ff:ff:ff:ff", src="00:0c:29:3f:5f:8c", type=ether_type)/Raw(load="1234567890")
    # sendp(packet, iface="ens4f0")
    # vlan_info_dict = debugfs_interface_vlan_form(
    #     case_cls=BridgeOperation,
    #     device_name="ens4f0", debug_command="dump vlan", cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    # # print(vlan_info_dict)
    # test_list = []
    # for key, vlaue in vlan_info_dict.items():
    #     if key == str(200):
    #         for value_index in vlaue:
    #             print(value_index["vlan_tpid"])
    # import json
    # print(json.dumps(vlan_info_dict, indent=4, ensure_ascii=False))
    # server_pcap_location = "/root/server_ens4f1_2024-08-05.pcap"
    # server_parse_object = ParsePacket(
    #         protocol_type=Dot1AD, remote_file=server_pcap_location,
    #         cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    # server_parse_list = server_parse_object.packet_file_parse()
    # print(server_parse_list)
