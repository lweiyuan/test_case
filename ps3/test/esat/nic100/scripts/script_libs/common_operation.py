import os
import pdb
import random
import re
import subprocess
import sys
import json
import time
import copy
from datetime import datetime
import configparser
from typing import Union

import add_syspath
from scripts.script_libs import constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.constants import VM_NAME_DEF, V_SWITCH_SRIOV_NAME_DEF, NIC_WIN_VM_CONFIG_PATH, \
    V_SWITCH_VMQ_NAME_DEF, V_SWITCH_DEGVMQ_NAME_DEF, V_SWITCH_MANAGER_NAME_DEF, V_ADAPTER_TEST_NAME_DEF, \
    SXE_DEV_MARK_1, VENDOR_ID, SCGBE_CLI
from scripts.script_libs.enums import (RtnStatusEnum, CmdExecuteAdressEnum, MacVlanModeEnum, NicNameEnum, HostOsEnum,
                                       ComModeStr, CmdStatusEnum, ExitCodeEnum, QueueEnum, VirtualModeEnum, PFSwitchMode, VFSwitchMode,
                                       RunModeEnum, L2ProtoTypeEnum, SwitchEnum, FwResetType, BondModeEnum, RdmaMode)
from scripts.script_libs.enums import BugTypeEnum, TransportProtocal, TestObjectType, TestEntryEnum, ResetType, ChipIdentification
from scripts.script_libs import constants
from scripts.script_libs.ifconfig import IfConfig
from scripts.script_libs.ethtool_operation import EthtoolOperation
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse


# test/esat/scripts 目录绝对路径
SCRIPTS_DIRECTORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# test/esat 目录绝对路径
ESAT_DIRECTORY = os.path.dirname(SCRIPTS_DIRECTORY)

COLOR_LIST = [
    "\033[1;30;30m{}\033[0m",  # 黑色
    "\033[1;31;31m{}\033[0m",  # 红色
    "\033[1;32;32m{}\033[0m",  # 绿色
    "\033[1;33;33m{}\033[0m",  # 黄色
    "\033[1;34;34m{}\033[0m",  # 蓝色
    "\033[1;35;35m{}\033[0m",  # 洋红
    "\033[1;36;36m{}\033[0m",  # 青色
    "\033[1;37;37m{}\033[0m",  # 白色
    "\033[1;30;47m{}\033[0m",  # 白底黑字
]

PF_SRIOV = "PF SRIOV"
VMSWITCH_SRIOV = "VmSwitch SRIOV"
VMADAPTER_SRIOV = "VmAdapter SRIOV"
DISABLE = "disable"
ENABLE = "enable"
DEGVMQ_MODE = [{PF_SRIOV: DISABLE, VMSWITCH_SRIOV: ENABLE, VMADAPTER_SRIOV: ENABLE},
               {PF_SRIOV: ENABLE, VMSWITCH_SRIOV: DISABLE, VMADAPTER_SRIOV: ENABLE},
               {PF_SRIOV: ENABLE, VMSWITCH_SRIOV: ENABLE, VMADAPTER_SRIOV: DISABLE},
               {PF_SRIOV: DISABLE, VMSWITCH_SRIOV: DISABLE, VMADAPTER_SRIOV: ENABLE},
               {PF_SRIOV: DISABLE, VMSWITCH_SRIOV: ENABLE, VMADAPTER_SRIOV: DISABLE},
               {PF_SRIOV: ENABLE, VMSWITCH_SRIOV: DISABLE, VMADAPTER_SRIOV: DISABLE}]

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

global prefix_command


class CommonOperation(object):
    _is_invoke_cmd_para_confed = False
    vm_info_dict = {}
    """
        "vswitch_name":
        "vswitch_ip":
        "vswitch_submask":
        "vswitch_mac_addr":
        "vf_name":
        "vf_ip":
        "vf_sub_mask":
        "vf_mac_addr":
    """
    vm_env_conf_dict = {}
    vm_name = None
    vm_ip = {}
    vm_vf_ip = {}
    vm_vf_ipv6 = {}
    vm_vf_submask = {}
    vf_name = {}
    rpc_port = 0
    write_vm_env_conf_info = ""
    server_added_ip = ''
    client_added_ip = ''
    server_added_ipv6 = ''
    client_added_ipv6 = ''
    degvmq_mode = {}
    nic_base_address = {}
    bond_prepared_server = False
    bond_prepared_client = False


    @classmethod
    def modify_cpu_num_by_grub(cls, cpu_num: int, server_ip: str) -> bool:
        from scripts.script_libs.host_operation import HostOperation
        from scripts.script_libs.file_operation import FileOperation
        # 修改grub文件
        exec_command = f'cat {constants.REMOTE_GRUB_PATH}'
        rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
            exec_command, CmdExecuteAdressEnum.SERVER.value)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{exec_command}执行成功')
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            return False
        # 修改文件内容
        lines = rtn_outputs.splitlines(True)

        for i in range(len(lines)):
            if 'GRUB_CMDLINE_LINUX' in lines[i]:
                if 'nr_cpus' in lines[i]:
                    lines[i] = re.sub(r'nr_cpus=\d+', f'nr_cpus={cpu_num}', lines[i])
                    print(f'1 lines[i]: {lines[i]}')
                else:
                    lines[i] = lines[i].strip()[:-2] + f' nr_cpus={cpu_num}' + lines[i][-2:]
                    print(f'2 lines[i]: {lines[i]}')
        file_contents = ''.join(lines)
        print(f'file_contents: {file_contents}')

        FileOperation.write_local_file(file_path=constants.LOCAL_GRUB_PATH,
                                       contents=file_contents)
        FileOperation.sftp_upload_file(localfile_path=constants.LOCAL_GRUB_PATH,
                                       remotefile_path=constants.REMOTE_GRUB_PATH,
                                       ip=server_ip)

        # 使用grub2-mkconfig命令重新生成/boot/grub2/grub.cfg文件
        exec_command = 'grub2-mkconfig -o /boot/grub2/grub.cfg'
        rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
            exec_command, CmdExecuteAdressEnum.SERVER.value)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{exec_command}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        reboot_result = HostOperation.host_reboot(ssh_ip=server_ip)
        if reboot_result == RtnStatusEnum.SUCCESS.value:
            log.info('重启成功')

        cpu_num_modified = CommonOperation.get_logical_cpu_num(cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        if cpu_num_modified == cpu_num:
            log.info(f'cpu核数修改成功，当前cpu核数为{cpu_num_modified}')
        else:
            log.info(f'cpu核数修改失败，当前cpu核数为{cpu_num_modified}')
            # CommonOperation.create_bug_problem(cls, key_word=f'cpu核数修改失败',
            #                                    description_word=f'当前cpu核数为{cpu_num_modified}')
        return False

    @classmethod
    def get_nic_driver_name(cls, current_config: str = constants.NIC_CONFIG_PATH, rdma: bool = False) -> tuple:
        """
        从配置文件获取网卡驱动名称(PF)
        :return:
        """
        config = configparser.ConfigParser()
        config.read(current_config)
        if "nic_driver" not in config.keys():
            log.error("ini不存在，拷贝一个默认的过来用")
            temp_ini = constants.NIC_CONFIG_BK_PATH.replace('env_config.ini', 'env_config_166.ini')
            exec_command = f"/bin/cp {temp_ini} {constants.NIC_CONFIG_BK_PATH};/bin/cp {temp_ini} {constants.NIC_CONFIG_PATH}"
            rtn_code, result = subprocess.getstatusoutput(exec_command)
            log.info(f"exec_command:{exec_command},rtn_code:{rtn_code}, result:{result}")
            config.read(current_config)
        if not rdma:
            server_nic_driver, client_nic_driver = \
                config['nic_driver']['server'].split(",")[0], config['nic_driver']['client'].split(",")[0]
        else:
            server_nic_driver, client_nic_driver = \
                config['nic_driver_rdma']['server'].split(",")[0], config['nic_driver_rdma']['client'].split(",")[0]
        return server_nic_driver, client_nic_driver

    @classmethod
    def get_nic_vf_driver_name_by_pf(cls, pf_driver_name) -> str:
        """
        从配置文件获取网卡驱动名称(PF)
        :return:
        """
        config = configparser.ConfigParser()
        config.read(constants.NIC_CONFIG_PATH)
        server_nic_driver, client_nic_driver = \
            config['nic_driver']['server'].split(",")[0], config['nic_driver']['client'].split(",")[0]
        if pf_driver_name == server_nic_driver:
            if len(config['nic_driver']['server'].split(",")) > 1:
                return config['nic_driver']['server'].split(",")[1]
            else:
                return server_nic_driver + "vf"
        if pf_driver_name == client_nic_driver:
            if len(config['nic_driver']['client'].split(",")) > 1:
                return config['nic_driver']['client'].split(",")[1]
            else:
                return client_nic_driver + "vf"
        log.warning_caller("未获取到vf驱动名")
        return "unknow"

    @classmethod
    def get_nic_vf_driver_name(cls, current_config: str = constants.NIC_CONFIG_PATH) -> tuple:
        """
        从配置文件获取网卡驱动名称(PF)
        :return:
        """
        config = configparser.ConfigParser()
        config.read(current_config)
        server_nic_driver_info = config['nic_driver']['server'].split(",")
        client_nic_driver_info = config['nic_driver']['client'].split(",")
        if len(server_nic_driver_info) > 1:
            server_nic_vf_driver = server_nic_driver_info[1]
        else:
            server_nic_vf_driver = server_nic_driver_info[0] + "vf"
        if len(client_nic_driver_info) > 1:
            client_nic_vf_driver = client_nic_driver_info[1]
        else:
            client_nic_vf_driver = client_nic_driver_info[0] + "vf"
        return server_nic_vf_driver, client_nic_vf_driver

    # @classmethod
    # def get_nic_pf_num(cls, current_config: str = constants.NIC_CONFIG_PATH) -> tuple:
    #     config = configparser.ConfigParser()
    #     config.read(current_config)
    #     server_nic_pf_num, client_nic_pf_num = config['nic_pf_num']['server'], config['nic_pf_num']['client']
    #     return server_nic_pf_num, client_nic_pf_num

    @classmethod
    def get_nic_pf_num(cls, current_config: str = constants.NIC_CONFIG_BK_PATH) -> tuple:
        
        config = configparser.ConfigParser()
        config.read(current_config)

        try:
            server_nic = config['platform']['server']
            client_nic =  config['platform']['client']
        except KeyError as e:
            raise KeyError(f"配置文件'{current_config}中缺少必要的配置项：{e}")
        
        def _extract_pf_num(nic_name: str) -> int:
            pattern = r'(OCP|PCIE)[xX](\d+)'
            match = re.search(pattern, nic_name, re.IGNORECASE)
            if match:
                return int(match.group(2))
            else:
                pattern = r'(PCIE10)[xX](\d+)'
                match = re.search(pattern, nic_name, re.IGNORECASE)
                if match:
                    return int(match.group(2))
                else:
                    return None
        
        server_pf_num = _extract_pf_num(server_nic)
        client_pf_num = _extract_pf_num(client_nic)
        return server_pf_num, client_pf_num

    @classmethod
    def get_nic_os(cls, current_config: str = constants.NIC_CONFIG_PATH) -> tuple:
        """
        从配置文件获取网卡所在主机的os
        :return:
        """
        if not os.path.exists(current_config):
            log.warning(f"current_config：{current_config} 不存在！！")
            server_nic_os, client_nic_os = "linux", "linux"
        else:
            config = configparser.ConfigParser()
            config.read(current_config)
            server_nic_os, client_nic_os = config['nic_os']['server'], config['nic_os']['client']
        return server_nic_os, client_nic_os

    @classmethod
    def get_guest_os(cls, test_reverse: bool = False) -> tuple:
        """
        从配置文件获取网卡所在主机的os
        :return:
        """
        server_guest_os, client_guest_os = cls.get_nic_os()
        if not test_reverse:
            if "windows" in CommandLineArgsParse.get_host_os():
                server_guest_os = "windows"
        else:
            if "windows" in CommandLineArgsParse.get_host_os():
                client_guest_os = "windows"
        return server_guest_os, client_guest_os

    @classmethod
    def get_nic_logical_ip(cls, current_config: str = constants.NIC_CONFIG_PATH) -> tuple:
        """
        从配置文件获取网卡所在主机的os
        :return:
        """
        config = configparser.ConfigParser()
        config.read(current_config)
        server_nic_logical_ip, client_nic_logical_ip = config['logical_ip']['server'], config['logical_ip']['client']
        return server_nic_logical_ip, client_nic_logical_ip

    @classmethod
    def get_nic_relationships(cls, current_config: str = constants.NIC_CONFIG_PATH, rdma: bool = False, nic_mode: str = RdmaMode.RoCE.value,
                              rdma_cc: bool = False) -> tuple:
        """
        从配置文件获取网卡所在主机的os
        :return:
        """
        config = configparser.ConfigParser()
        config.read(current_config)
        # Ethernet模式（Roce）
        if nic_mode == RdmaMode.RoCE.value:
            # 以太设备名
            if not rdma:
                # 以太设备名
                if not rdma_cc:
                    server_relations, client_relations = config['relationships']['server'], config['relationships']['client']
                # cc测试-以太设备名
                else:
                    server_relations, client_relations = config['relationships_cc']['server'], config['relationships_cc']['client']
            # RDMA设备名
            else:
                # RDMA设备名
                if not rdma_cc:
                    server_relations, client_relations = config['relationships_rdma']['server'], config['relationships_rdma'][
                        'client']
                # cc测试-RDMA设备名
                else:
                    server_relations, client_relations = config['relationships_cc_rdma']['server'], config['relationships_cc_rdma'][
                        'client']
        # Infiniband模式（IB）
        else:
            # 以太设备名
            if not rdma:
                server_relations, client_relations = config['relationships_ipoib']['server'], config['relationships_ipoib']['client']
            # RDMA设备名
            else:
                server_relations, client_relations = config['relationships_rdma']['server'], config['relationships_rdma'][
                    'client']

        server_relation_list = server_relations.strip().split(",")
        client_relation_list = client_relations.strip().split(",")
        return server_relation_list, client_relation_list

    @classmethod
    def get_nic_generation(cls) -> str:
        """
        从配置文件获取网卡驱动名，sxe，sxe2，sxe3
        :return:
        """
        config = configparser.ConfigParser()
        config.read(constants.NIC_CONFIG_BK_PATH)
        server_nic_driver, client_nic_driver = \
            config['nic_driver']['server'].split(",")[0], config['nic_driver']['client'].split(",")[0]
        return server_nic_driver

    @classmethod
    def get_rdma_driver(cls):
        """
        从配置文件获取网卡驱动名，sxe，sxe2，sxe3
        :return:
        """
        config = configparser.ConfigParser()
        config.read(constants.NIC_CONFIG_BK_PATH)
        server_rdma_driver, client_rdma_driver = \
            config['nic_driver_rdma']['server'].split(",")[0], config['nic_driver_rdma']['client'].split(",")[0]
        return server_rdma_driver, client_rdma_driver

    @classmethod
    def get_subnet_nic_driver(cls) -> list:
        """
        从配置文件获取网卡驱动名，sxe，sxe2，sxe3
        :return:
        """
        config = configparser.ConfigParser()
        config.read(constants.NIC_CONFIG_BK_PATH)
        subnet_nic_driver_list = config['subnet']['nic_driver'].split("; ")
        return subnet_nic_driver_list

    @classmethod
    def get_subnet_logical_ip(cls) -> list:
        """
        从配置文件获取网卡驱动名，sxe，sxe2，sxe3
        :return:
        """
        config = configparser.ConfigParser()
        config.read(constants.NIC_CONFIG_BK_PATH)
        subnet_logical_ip_list = config['subnet']['logical_ip'].split("; ")
        return subnet_logical_ip_list

    @classmethod
    def get_subnet_platform(cls) -> list:
        """
        从配置文件获取网卡驱动名，sxe，sxe2，sxe3
        :return:
        """
        config = configparser.ConfigParser()
        config.read(constants.NIC_CONFIG_BK_PATH)
        subnet_platform_list = config['subnet']['platform'].split("; ")
        return subnet_platform_list

    @classmethod
    def get_subnet_serial_port_pos(cls) -> list:
        """
        从配置文件获取网卡驱动名，sxe，sxe2，sxe3
        :return:
        """
        config = configparser.ConfigParser()
        config.read(constants.NIC_CONFIG_BK_PATH)
        subnet_serial_port_pos_list = config['subnet']['serial_port_pos'].split("; ")
        return subnet_serial_port_pos_list

    @classmethod
    def get_subnet_relationships(cls, current_config: str = constants.NIC_CONFIG_PATH, rdma: bool = False, nic_mode: str = RdmaMode.RoCE.value) -> tuple:
        """
        从配置文件获取网卡所在主机的os
        :return:
        """
        config = configparser.ConfigParser()
        config.read(current_config)
        # Ethernet模式（Roce）
        if nic_mode == RdmaMode.RoCE.value:
            # 以太设备名
            if not rdma:
                relations = config['subnet']['relationships']
            # RDMA设备名
            else:
                relations = config['subnet']['relationships_rdma']
        # Infiniband模式（IB）
        else:
            # 以太设备名
            if not rdma:
                relations = config['subnet']['relationships_ipoib']
            # RDMA设备名
            else:
                relations = config['subnet']['relationships_rdma']

        relation_list = relations.strip().split("; ")
        return relation_list

    @classmethod
    def get_subnet_nic_driver_rdma(cls) -> list:
        """
        从配置文件获取网卡驱动名，sxe，sxe2，sxe3
        :return:
        """
        config = configparser.ConfigParser()
        config.read(constants.NIC_CONFIG_BK_PATH)
        subnet_nic_driver_rdma_list = config['subnet']['nic_driver_rdma'].split("; ")
        return subnet_nic_driver_rdma_list

    @classmethod
    def get_subnet_relationships_rdma(cls) -> list:
        """
        从配置文件获取网卡驱动名，sxe，sxe2，sxe3
        :return:
        """
        config = configparser.ConfigParser()
        config.read(constants.NIC_CONFIG_BK_PATH)
        subnet_relationships_rdma_list = config['subnet']['relationships_rdma'].split("; ")
        return subnet_relationships_rdma_list

    @classmethod
    def get_ddp_switch(cls, current_config: str = constants.NIC_CONFIG_PATH) -> tuple:
        """
        从配置文件获取网卡所在主机的os
        :return:
        """
        config = configparser.ConfigParser()
        config.read(current_config)
        if 'ddp_switch' in config:
            server_ddp_switch, client_ddp_switch = config['ddp_switch']['server'], config['ddp_switch']['client']
        else:
            server_ddp_switch, client_ddp_switch = 'off', 'off'
        return server_ddp_switch, client_ddp_switch

    @classmethod
    def get_renix(cls, current_config: str = constants.NIC_CONFIG_PATH, rdma: bool = False) -> tuple:
        """
        从配置文件获取发包仪的server ip、locations
        :return:
        """
        config = configparser.ConfigParser()
        config.read(current_config)

        # client存在renix
        client_renix = False
        if '/' in config['relationships']['client']:
            client_renix = True

        # 从env_config中获取renix信息
        if client_renix:
            client_relations = config['relationships']['client']
            # //172.17.1.1/1/1
            renix_ip_list = re.findall(r"//([\d\.]+)/\d+/\d+", client_relations)
            renix_server = ','.join(list(set(renix_ip_list)))
            renix_locations = client_relations
        else:
            return None, None
        renix_server_list = renix_server.strip().split(",")
        renix_locations_list = renix_locations.strip().split(",")
        return renix_server_list, renix_locations_list

    @classmethod
    def is_renix_only(cls) -> bool:
        """
        从配置文件获取发包仪的server ip、locations
        :return:
        """
        # 仅发包仪环境标记(server仅和发包仪连接，不连接其他服务器)
        client_renix_only_flag = False
        renix_server_list, renix_locations_list = cls.get_renix()
        server_ip, client_ip = cls.get_nic_logical_ip()
        # 存在发包仪
        if renix_server_list:
            # log.info_caller("发包仪环境")
            renix_server = renix_server_list[0]
            # 如果env_config.ini中的logic_ip-client的ip与relationships-client中ip相等，认为是单纯发包仪环境（跳过client命令执行），否则认为是发包仪与正常服务器混合环境（不跳过client命令执行）
            if renix_server == client_ip:
                client_renix_only_flag = True
        # log.info(f'当前是否为仅发包仪环境：{client_renix_only_flag}')
        return client_renix_only_flag

    @classmethod
    def get_platform(cls, current_config: str = constants.NIC_CONFIG_PATH) -> tuple:
        """
        从配置文件获取网卡所在主机的os
        :return:
        """
        config = configparser.ConfigParser()
        config.read(current_config)
        server_platform, client_platform = config['platform']['server'], config['platform']['client']
        return server_platform, client_platform

    @classmethod
    def set_device_switchdev(cls, test_port: int, current_config: str = constants.NIC_CONFIG_PATH):
        """
        author: wei.yuan1
        date: 2025年7月14日15:19:57
        description: 设置环境的eswitch mode为legacy
        :param current_config:
        :return:
        """
        config = configparser.ConfigParser()
        config.read(current_config)
        server_driver_name, _ = cls.get_nic_driver_name()
        if server_driver_name in [NicNameEnum.SXE.value, NicNameEnum.INTEL_82599.value]:
            return
        server_device_list, client_device_list = cls.get_nic_relationships()
        logical_server_ip, logical_client_ip = CommandOperation.get_logical_ip_form_config()
        for server_device in server_device_list:
            driver_info = EthtoolOperation.show_driver_infomation(
                server_device, CmdExecuteAdressEnum.SERVER.value, test_port=int(test_port))
            if driver_info:
                bus_id = driver_info["bus-info"]
                pci_addr = f"pci/{bus_id}"
                exec_cmd = f"devlink -j dev eswitch show {pci_addr}"
                rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                    cmd=exec_cmd, ssh_ip=logical_server_ip, ssh_port=test_port
                )
                try:
                    mode = json.loads(rtn_stdout).get("dev").get(pci_addr).get("mode")
                    if mode != "legacy":
                        exec_command = f" devlink dev eswitch set  pci/{bus_id} mode legacy"
                        CommandOperation.execute_command_with_error(
                            cmd=exec_command, ssh_ip=logical_server_ip, ssh_port=test_port)
                except Exception as e:
                    log.info(f"rtn_code error, description is {rtn_stderr}")


    @classmethod
    def get_serial_port_pos(cls, current_config: str = constants.NIC_CONFIG_PATH) -> tuple:
        """
        从配置文件获取串口插在位置
        :return:
        """
        config = configparser.ConfigParser()
        config.read(current_config)
        server_serial_port_pos, client_serial_port_pos = \
            config['serial_port_pos']['server'], config['serial_port_pos']['client']
        if "@" in server_serial_port_pos:
            # 配置信息格式如developer@10.17.22.134_10.17.137.116_5000，直接原样返回
            server_serial_cli_exec_address = server_serial_port_pos
        elif server_serial_port_pos == 'server':
            server_serial_cli_exec_address = CmdExecuteAdressEnum.SERVER.value
        else:
            server_serial_cli_exec_address = CmdExecuteAdressEnum.CLIENT.value
        if "@" in client_serial_port_pos:
            client_serial_cli_exec_address = client_serial_port_pos
        elif client_serial_port_pos == 'server':
            client_serial_cli_exec_address = CmdExecuteAdressEnum.SERVER.value
        else:
            client_serial_cli_exec_address = CmdExecuteAdressEnum.CLIENT.value
        return server_serial_cli_exec_address, client_serial_cli_exec_address

    @classmethod
    def show_env_config(cls, current_config: str = constants.NIC_CONFIG_PATH) -> None:
        """
        从配置文件获取网卡所在主机的os
        :return:
        """
        config = configparser.ConfigParser()
        config.read(current_config)
        log.info("nic_driver==> server:{},client:{}".format(config['nic_driver']['server'],
                                                            config['nic_driver']['client']))
        log.info("nic_os==> server:{},client:{}".format(config['nic_os']['server'], config['nic_os']['client']))
        log.info("logical_ip==> server:{},client:{}".format(config['logical_ip']['server'],
                                                            config['logical_ip']['client']))
        log.info("platform==> server:{},client:{}".format(config['platform']['server'],
                                                          config['platform']['client']))

    @classmethod
    def get_single_test_mode(cls, current_config: str = constants.SINGLE_TEST_MODE_PATH) -> bool:
        """
        从配置文件获取是否是单端测试模式
        :return:
        """
        if os.path.isfile(current_config):
            rtn_code = RtnStatusEnum.SUCCESS.value
            result = ''
            with open(current_config, 'r', encoding='utf-8') as file:
                result = file.read()
                print(f"{current_config}文件内容：{result}")
        else:
            rtn_code = RtnStatusEnum.FAIL.value
            result = ''
            print(f"{current_config}文件不存在")
        # exec_command = "cat {}".format(current_config)
        # log.info(exec_command)
        # rtn_code, result = subprocess.getstatusoutput(exec_command)
        if rtn_code == RtnStatusEnum.SUCCESS.value and ('1' in result or "yes" in result.lower()):
            return True
        else:
            return False

    @classmethod
    def set_single_test_mode(cls, current_config: str = constants.SINGLE_TEST_MODE_PATH, value: str = "no") -> None:
        """
        从配置文件获取是否是单端测试模式
        :return:
        """
        exec_command = "echo {} > {}".format(value, current_config)
        log.info(exec_command)
        rtn_code, result = subprocess.getstatusoutput(exec_command)

    @classmethod
    def set_fpga_bit_version(cls, current_config: str = constants.FPGA_BIT_VERSION_PATH, value: str = '') -> None:
        """
        从配置文件获取是否是单端测试模式
        :return:
        """
        if value:
            exec_command = "echo {} > {}".format(value, current_config)
            log.info(exec_command)
            rtn_code, result = subprocess.getstatusoutput(exec_command)
        else:
            log.warning(f"当前未获取到fpga bit verision信息，不进行设置，以环境上已有值为准，若确认不匹配，请手动修改：{current_config}")

    @classmethod
    def get_cli_fpga_bit_version(cls, server_os_type: str, server_ip: str, test_port: int) -> str:
        """
        从配置文件获取是否是单端测试模式
        :return:
        """
        fpga_bit_version = ""
        if server_os_type == "windows":
            cmd = f"{constants.SCGBECLI64} show list"
        else:
            cmd = f"{constants.SCGBECLI64} show list"
        cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, ssh_ip=server_ip, ssh_port=str(test_port) if test_port is not None else None,
            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        bdfs = re.findall(r'(\d\d\d\d)\s+\|(\w+:\w+.\w+)\s+', cmd_output)
        if bdfs:
            bdf = bdfs[0][0] + ":" + bdfs[0][1]
            cmd = f"{constants.SCGBECLI64} -d {bdf} get reg type=A width=32 addr=0xB800248C"
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, ssh_ip=server_ip, ssh_port=str(test_port) if test_port is not None else None,
                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            fpga_bit_versions = re.findall(r'0xb800248c \|(\S+)', cmd_output)
            if fpga_bit_versions:
                fpga_bit_version = fpga_bit_versions[0]
            else:
                fpga_bit_version = ""
        log.info("fpga_bit_version:{}".format(fpga_bit_version))
        return fpga_bit_version

    @classmethod
    def get_fpga_bitfile_version(cls, current_config: str = constants.FPGA_BIT_VERSION_PATH) -> str:
        """
        从配置文件获取是否是单端测试模式
        :return:
        """
        if os.path.isfile(current_config):
            rtn_code = RtnStatusEnum.SUCCESS.value
            with open(current_config, 'r', encoding='utf-8') as file:
                result = file.read()
                print(f"{current_config}文件内容：{result}")
        else:
            rtn_code = RtnStatusEnum.FAIL.value
            result = ''
            print(f"{current_config}文件不存在")
        # exec_command = "cat {}".format(current_config)
        # log.info(exec_command)
        # rtn_code, result = subprocess.getstatusoutput(exec_command)
        # print(result)
        values = re.findall(r"0x(\S+)", result)
        if values:
            fpga_bit_version = values[0][0:4]
        else:
            log.error("未获取到正确的fpga_bitfile_version！！！")
            fpga_bit_version = 'ec00'
        return fpga_bit_version

    @classmethod
    def get_fpga_bitfile_class(cls, current_config: str = constants.FPGA_BIT_VERSION_PATH) -> str:
        """
        从配置文件获取是否是单端测试模式
        :return:
        """
        if os.path.isfile(current_config):
            rtn_code = RtnStatusEnum.SUCCESS.value
            with open(current_config, 'r', encoding='utf-8') as file:
                result = file.read()
                print(f"{current_config}文件内容：{result}")
        else:
            rtn_code = RtnStatusEnum.FAIL.value
            result = ''
            print(f"{current_config}文件不存在")
        # exec_command = "cat {}".format(current_config)
        # log.info(exec_command)
        # rtn_code, result = subprocess.getstatusoutput(exec_command)
        # print(result)
        values = re.findall(r"0x(\S+)", result)
        if values:
            fpga_bit_version = values[0][-2:]
        else:
            log.error("未获取到正确的fpga_bitfile_class！！！")
            fpga_bit_version = FpgaBitfileClass['UNKNOW']
        return fpga_bit_version

    @classmethod
    def get_chip_identification(cls, current_config: str = constants.FPGA_BIT_VERSION_PATH) -> str:
        """
        author:      xiangyu.liu
        date:        2024-10-06 11:35:20
        description:
            ASIC = 'a'
            EMU = 'e'
            FPGA = 'f'
        :return:     None
        """
        if os.path.isfile(current_config):
            rtn_code = RtnStatusEnum.SUCCESS.value
            with open(current_config, 'r', encoding='utf-8') as file:
                result = file.read()
                print(f"{current_config}文件内容：{result}")
        else:
            rtn_code = RtnStatusEnum.FAIL.value
            result = ''
            print(f"{current_config}文件不存在")
        #exec_command = "cat {}".format(current_config)
        #log.info(exec_command)
        #rtn_code, result = subprocess.getstatusoutput(exec_command)
        #print(result)
        values = re.findall(r"0x(\S+)", result)
        if values:
            chip_identification = values[0][-4:-3]
            if chip_identification == '0':
                # log.error(f"chip_identification={chip_identification}！！！,当做是asic")
                chip_identification = 'a'
        else:
            # log.error("未获取到正确的chip_identification！！！,当做是asic")
            chip_identification = 'a'

        return chip_identification

    @classmethod
    def is_fpga(cls) -> bool:
        """
        从配置文件获取串口插在位置
        :return:
        """
        if ChipIdentification.FPGA.value == cls.get_chip_identification():
            return True
        return False


    @classmethod
    def get_node_info_from_path(cls) -> tuple:
        """
        从配置文件获取串口插在位置
        :return:
        """
        cur_path = os.path.abspath(os.path.dirname(__file__))
        num_list = re.findall(r'([vp]m\d+)', cur_path)
        if num_list and ('vm' in num_list[0] or 'pm' in num_list[0]):
            vm = num_list[0]
            if len(vm) < 2 + 4:
                port = "8" + vm.replace("vm", "").replace("pm", "")
            else:
                port = vm.replace("vm", "").replace("pm", "")
        else:
            vm = "vm999"
            port = "8888"
        return vm, port

    @classmethod
    def get_root_path(cls, os_type) -> str:
        """
        从配置文件获取串口插在位置
        :return:
        """
        if os_type == 'windows':
            return constants.WINDOWS_FILE_PATH_ROOT
        else:
            return constants.LINUX_FILE_PATH_ROOT

    @classmethod
    def pcap_file_path(cls) -> tuple:
        """
        返回pcap在测试环境上的生成路径
        :return:
        """
        server_os, client_os = CommonOperation.get_nic_os()
        vm, rpc_port = CommonOperation.get_node_info_from_path()
        server_vm_path = "{}{}".format(CommonOperation.get_root_path(server_os), vm)
        client_vm_path = "{}{}".format(CommonOperation.get_root_path(client_os), vm)

        pcap_file_path_client = '{}/client_packet.pcap'.format(client_vm_path)
        pcap_file_path_server = '{}/server_packet.pcap'.format(server_vm_path)
        return pcap_file_path_server, pcap_file_path_client

    @classmethod
    def check_driver_probe(cls, rdma: bool = False, recover: bool = True) -> bool:
        """
        检查网卡驱动是否已加载
        :return:
        """
        server_nic_driver, client_nic_driver = cls.get_nic_driver_name(rdma=rdma)
        host_os_server, host_os_client = cls.get_nic_os()
        result = True
        nicg = cls.get_nic_generation()
        # 如果有一侧是windows，本方法失效
        if 'windows' not in host_os_client and 'windows' not in host_os_server:
            if (CommandLineArgsParse.get_test_entry() not in [TestEntryEnum.SINGLE_MODE.value] and
                    cls.is_renix_only() == False):
                exec_command_server = 'lsmod | grep {}'.format(server_nic_driver)
                exec_command_client = 'lsmod | grep {}'.format(client_nic_driver)
                _, rtn_outputs_server, rtn_err_server= CommandOperation.execute_command_based_paramiko_with_rtncode(
                    exec_command_server, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                _, rtn_outputs_client, rtn_err_client= CommandOperation.execute_command_based_paramiko_with_rtncode(
                    exec_command_client, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)

                if rtn_outputs_client and rtn_outputs_server:
                    return True

                if recover:
                    kwargs_client = {}
                    kwargs_server = {}
                    if server_nic_driver in [f'{constants.DRV_SCGBE_RDMA}']:
                        # kwargs_server['rcms_mode'] = '1'
                        kwargs_server['resource_profile'] = '2'
                        # kwargs_server['max_rdma_vfs'] = '32'
                        # kwargs_server['kernel_llwqe_disable'] = '1'
                        kwargs_server['fragment_count_limit'] = '13'
                    if client_nic_driver in [f'{constants.DRV_SCGBE_RDMA}']:
                        # kwargs_client['rcms_mode'] = '1'
                        kwargs_client['resource_profile'] = '2'
                        # kwargs_client['max_rdma_vfs'] = '32'
                        # kwargs_client['kernel_llwqe_disable'] = '1'
                        kwargs_client['fragment_count_limit'] = '13'
                    if not rtn_outputs_client:
                        if kwargs_client:
                            driver_flag_client = cls.modprobe_driver(client_nic_driver,
                                                                     cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                                     kwargs=kwargs_client)
                        else:
                            driver_flag_client = cls.modprobe_driver(client_nic_driver,
                                                                     cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        result = result & driver_flag_client
                    if not rtn_outputs_server:
                        if kwargs_server:
                            driver_flag_server = cls.modprobe_driver(server_nic_driver,
                                                                     cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                                     kwargs=kwargs_server)
                        else:
                            driver_flag_server = cls.modprobe_driver(server_nic_driver,
                                                                     cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        result = result & driver_flag_server
            else:
                exec_command_server = 'lsmod | grep {}'.format(server_nic_driver)
                _, rtn_outputs_server, rtn_err_server= CommandOperation.execute_command_based_paramiko_with_rtncode(
                    exec_command_server, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)

                if rtn_outputs_server:
                    return True

                if recover:
                    if not rtn_outputs_server:
                        driver_flag_server = cls.modprobe_driver(server_nic_driver,
                                                                 cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        result = result & driver_flag_server
        return result

    @classmethod
    def rmmod_driver(cls, driver_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                     force: bool = False) -> bool:
        """
        卸载网卡驱动
        :param driver_name:
        :param cmd_execute_address:
        :param force: 一般情况下禁止卸载驱动，特定验证驱动卸载加载场景，才可卸载驱动
        :return:
        """
        if (CommandLineArgsParse.get_test_entry() == TestEntryEnum.VF_KEEP_MODE.value and
                cmd_execute_address==CmdExecuteAdressEnum.SERVER.value):
            log.warning("========> vf_keep_mode server端禁止卸载驱动，卸载操作目标为:{}驱动，不进行卸载！".format(driver_name))
            return True

        if not force:
            log.warning("========> 常规场景禁止卸载驱动，卸载操作目标为:{}驱动，不进行卸载！".format(driver_name))
            return True
        # driver_name in ["ixgbe", "ixgbevf", "igb"] and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value
        # if cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
        #     log.warning("========> 是client端，卸载操作目标为:{}驱动，不允许卸载！".format(driver_name))
        #     return True
        exec_command = f'rmmod {driver_name}'
        rtn_code, _, _= CommandOperation.execute_command_based_paramiko_with_rtncode(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.warning("========> 卸载{}驱动！".format(driver_name))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            return True
        else:
            return False

    @classmethod
    def get_device_bus_info(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> list:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        lspci -vvv | grep Ethernet找到所有网卡相关bus info
        return: []
        """
        result_list = []
        exec_command = 'lspci -vvv | grep Ethernet'

        rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            pci_pattern = r'\S{2}:\S{2}.\S'
            result_list = re.findall(pci_pattern, rtn_outputs)
        return result_list

    @classmethod
    def get_device_bus_info_sxe(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> list:
        """
        author:             shaohui.wang
        date:               2023-08-20
        description:        lspci | grep {VENDOR_ID}找到sxe网卡相关bus info
        return: []
        """
        result_list = []
        exec_command = f"lspci | grep -E '{constants.VENDOR_ID}|{constants.VENDOR_ID_NAME}' | grep -v Virtual"

        rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            pci_pattern = r'\S{2}:\S{2}\.\S'
            result_list = re.findall(pci_pattern, rtn_outputs)
        return result_list

    @classmethod
    def get_vf_device_name(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> list:
        """

        """
        result_list = []

        server_nic_driver, client_nic_driver = cls.get_nic_driver_name()
        server_nic_vf_driver, client_nic_vf_driver = cls.get_nic_vf_driver_name()
        server_nic_name, client_nic_name = cls.get_nic_relationships()

        all_device_name = IfConfig.get_all_device_name(cmd_execute_address=cmd_execute_address)

        for device in all_device_name:
            info_dict = EthtoolOperation.show_driver_infomation(device, cmd_execute_address)
            if (cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and
                    info_dict.get('driver') == client_nic_vf_driver):
                result_list.append(device)
            elif (cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and
                  info_dict.get('driver') == server_nic_vf_driver):
                result_list.append(device)

        if cmd_execute_address == CmdExecuteAdressEnum.SERVER.value:
            pf_nic_list = server_nic_name.copy()
        elif cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
            pf_nic_list = client_nic_name.copy()
        rtn_list = []
        for pf_nic in pf_nic_list:
            for vf_nic in result_list:
                if pf_nic in vf_nic:
                    rtn_list.append(vf_nic)
        return rtn_list

    @classmethod
    def get_vf_device_names_by_pf(cls, pf_device_name: str,
                                  cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> list:
        """
        author:             shaohui.wang
        date:               2023-09-21
        description:        获取测试网卡的设备名（端口名）
        return:             获取基于某一pf网卡创建的所有vf网卡名称
        """
        pf_device_info_dict = EthtoolOperation.show_driver_infomation(device_name=pf_device_name,
                                                                      cmd_execute_address=cmd_execute_address)
        # print(f"pf_device_name:{pf_device_name}")
        # print(f"pf_device_info_dict:{pf_device_info_dict}")

        result_list = []
        server_nic_driver, client_nic_driver = cls.get_nic_driver_name()
        server_nic_vf_driver, client_nic_vf_driver = cls.get_nic_vf_driver_name()
        log.info(
            "server_nic_vf_driver:{}, client_nic_vf_driver:{}".format(server_nic_vf_driver, client_nic_vf_driver))
        all_device_name = IfConfig.get_all_device_name(cmd_execute_address=cmd_execute_address)
        log.info("all_device_name:{}".format(all_device_name))
        for device in all_device_name:
            info_dict = EthtoolOperation.show_driver_infomation(device, cmd_execute_address)
            if (cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and
                    info_dict.get('driver') == client_nic_vf_driver):
                if client_nic_vf_driver in ["sxevf", "ixgbevf"]:
                    if pf_device_info_dict['bus-info'][-1] == '0':
                        if info_dict.get('bus-info')[-1] in ['0', '2', '4', '6', '8']:
                            result_list.append(device)
                    elif pf_device_info_dict['bus-info'][-1] == '1':
                        if info_dict.get('bus-info')[-1] in ['1', '3', '5', '7', '9']:
                            result_list.append(device)
                else:
                    if pf_device_name in device and pf_device_name != device:
                        result_list.append(device)
            elif (cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and
                  info_dict.get('driver') == server_nic_vf_driver):
                if server_nic_vf_driver in ["sxevf", "ixgbevf"]:
                    if pf_device_info_dict['bus-info'][-1] == '0':
                        if info_dict.get('bus-info')[-1] in ['0', '2', '4', '6', '8']:
                            result_list.append(device)
                    elif pf_device_info_dict['bus-info'][-1] == '1':
                        if info_dict.get('bus-info')[-1] in ['1', '3', '5', '7', '9']:
                            result_list.append(device)
                else:
                    if pf_device_name in device and pf_device_name != device:
                        result_list.append(device)
        log.info("pf: {}, vf_list:{}".format(pf_device_name, result_list))
        return result_list

    @classmethod
    def get_physical_device_name(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> list:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        获取测试网卡的设备名（端口名）
        return: ['ens1f0', 'ens1f1']
        """
        result_list = []

        server_nic_driver, client_nic_driver = cls.get_nic_driver_name()
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        # linux系统
        if (cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and 'windows' != host_os_client) or \
                (cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and 'windows' != host_os_server):
            all_device_name = IfConfig.get_all_device_name(cmd_execute_address=cmd_execute_address)

            for device in all_device_name:
                info_dict = EthtoolOperation.show_driver_infomation(device, cmd_execute_address)
                if cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and info_dict.get(
                        'driver') == client_nic_driver:
                    result_list.append(device)
                elif cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and info_dict.get(
                        'driver') == server_nic_driver:
                    result_list.append(device)
        # windows系统
        else:
            check_info = ''
            if cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                if 'ixgbe' in client_nic_driver:
                    check_info = '82599'
                    check_info_old = '82599'
                elif 'sxe' in client_nic_driver:
                    check_info_old = 'sxe'
                    check_info = 'LD'
                else:
                    pass
            if cmd_execute_address == CmdExecuteAdressEnum.SERVER.value:
                if 'ixgbe' in server_nic_driver:
                    check_info = '82599'
                    check_info_old = '82599'
                elif 'sxe' in server_nic_driver:
                    check_info_old = 'sxe'
                    check_info = 'LD'
                else:
                    pass
            all_nic_info = IfConfig.analysis_ipconfig_info(cmd_execute_address=cmd_execute_address)
            for item in all_nic_info:
                if check_info in item.get(constants.DESCRIPTION, '') or check_info_old \
                        in item.get(constants.DESCRIPTION, ''):
                    result_list.append(item['nic_name'])

        return result_list

    @classmethod
    def configure_nic_info(cls, ifindex_list, nic_name_list, nic_ip_list):
        """
        author: wei.yuan1
        date: 2023.12.22
        descroiption: 检查并配置网卡的名称和ip
        :param ifindex_list:
        :param nic_name_list:
        :param nic_ip_list:
        :return:
        """
        host_os_server, host_os_client = cls.get_nic_os()
        rtn_code = RtnStatusEnum.SUCCESS.value

        def rename_adapter_name(device_name, interface_index, cmd_execute_address):
            """
            author: wei.yuan1
            date: 2023.12.13
            description: 修改网络适配器的名称
            :param device_name: 新命名的网络适配器的名称
            :param interface_index: 网卡序号
            :return:
            """
            rename_command = \
                f"Get-NetAdapter | Where-Object {{$_.InterfaceIndex " \
                f" -eq {interface_index}}} | Rename-NetAdapter -NewName '{device_name}'"
            rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_multi_times(
                cmd=rename_command, cmd_execute_address=cmd_execute_address, timeout=180)
            return rtn_code

        def check_nic_name(if_index, nic_name, execute_address):
            rename_code = RtnStatusEnum.SUCCESS.value
            interface_name = ""
            if host_os_server == "windows":
                get_command = f"(Get-NetAdapter -ifIndex {if_index}).Name"
                cmd_code, cmd_outputs, cmd_err = CommandOperation.execute_command_multi_times(
                    cmd=get_command, cmd_execute_address=execute_address, timeout=180)
                if cmd_code == RtnStatusEnum.SUCCESS.value:
                    interface_name = cmd_outputs
                else:
                    rename_code = cmd_code
                if interface_name != nic_name:
                    rename_code = rename_adapter_name(
                        device_name=nic_name, interface_index=if_index, cmd_execute_address=execute_address)
            return rename_code

        def check_nic_address(if_index, ip_address, execute_address):
            ip_address_list = []
            cmd_code = RtnStatusEnum.SUCCESS.value
            if host_os_server == "windows":
                get_ip_command = \
                    f"(Get - NetIPAddress - InterfaceIndex {if_index} -AddressFamily IPv4).IPAddress"
                cmd_code, cmd_outputs, cmd_err = CommandOperation.execute_command_multi_times(
                    cmd=get_ip_command, cmd_execute_address=execute_address, timeout=180)
                if cmd_code == RtnStatusEnum.SUCCESS.value:
                    outputs = cmd_outputs.replace("\r", "")
                    ip_address_list = outputs.split("\n")
                if ip_address not in ip_address_list:
                    exec_command = (f"New-NetIPAddress --InterfaceIndex {if_index} -IPAddress '{ip_address}' "
                                    f"-PrefixLength 24")
                    rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_multi_times(
                        cmd=exec_command, cmd_execute_address=execute_address, timeout=180)
                    cmd_code = rtn_code
            return cmd_code

        if host_os_server == "windows":
            rtn_code_list = []
            for if_index, nic_name in zip(ifindex_list, nic_name_list):
                rename_code = check_nic_name(if_index, nic_name, CmdExecuteAdressEnum.SERVER.value)
                rtn_code_list.append(rename_code)
            for if_index, ip_addr in zip(ifindex_list, nic_ip_list):
                ip_check_code = check_nic_address(if_index, ip_addr, CmdExecuteAdressEnum.SERVER.value)
                rtn_code_list.append(ip_check_code)
            rtn_code_list = list(set(rtn_code_list))
            rtn_code = RtnStatusEnum.SUCCESS.value \
                if len(rtn_code_list) == 1 and rtn_code_list[0] == RtnStatusEnum.SUCCESS.value \
                else RtnStatusEnum.FAIL.value
        return rtn_code

    @classmethod
    def get_active_vm(cls, ssh_ip: str = None, host_os_server: str = None, host_os_client: str = None,
                      cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, test_port: int = 22):
        def get_vm(test_port: int = 22):
            """
            获取所有虚机的名称
            """
            exist_vm_list = []
            exist_vm_command = "get-vm |select-object Name|FL"
            # 查看当前环境中的所有的vm虚拟机
            rtn_code, rtn_stdout, rtn_stderr= CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exist_vm_command,
                cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip, ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server,
                host_os_client=host_os_client)
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

        def check_vm_state(vm_name: str, test_port: int = 22):
            """
            author:      haibin.xu
            date:        2023-12-13 17:24:57
            description: 检查虚拟机状态
            :param vm_name:
            :return:
            """
            rtn_state = None
            check_cmd = 'get-vm -name {} | Select-Object State | FL'.format(vm_name)
            rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_multi_times(
                cmd=check_cmd, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip, ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server, host_os_client=host_os_client, timeout=180)
            if RtnStatusEnum.SUCCESS.value == rtn_code:
                match_list = re.findall(r'State\s*:\s*(Off|Running)', rtn_stdout)
                if match_list:
                    rtn_state = match_list[0]

            return rtn_state

        vm_list = get_vm(test_port=str(test_port))
        running_vm_list = [index for index in vm_list if check_vm_state(
            index, test_port=test_port).title() == "Running"]
        return running_vm_list

    @classmethod
    def clean_virtual_info(cls, ssh_ip, host_os_server, host_os_client,
                           cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, test_port: int = 22):

        def uninstall_vm_adapter(vm_name: str, test_port: int = 22) \
                -> int:
            """
            author:      wei.yuan1
            date:        2023-11-30 11:38:57
            description: 使用invoke命令在虚拟机侧卸载网卡设备

            :param vm_name: 虚拟机 name
            :return:     卸载成功返回0，失败返回-1
            """
            rtn_uninstall_code = RtnStatusEnum.FAIL.value
            get_adapter_device_id_cmd = CommandOperation.concat_invoke_command(
                vm_name=vm_name, cmd="devcon findall *VMBUS*")
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
                cmd=get_adapter_device_id_cmd,
                cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip, ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server, host_os_client=host_os_client, timeout=180)
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
                    cmd=uninstall_adapt_cmd, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip,
                    ssh_port=str(test_port) if test_port is not None else None,
                    host_os_server=host_os_server, host_os_client=host_os_client, timeout=180)
                log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                    uninstall_adapt_cmd, cmd_code, cmd_stdout, cmd_stderr))
                if RtnStatusEnum.SUCCESS.value != cmd_code:
                    log.error('命令: {}，执行失败'.format(uninstall_adapt_cmd))
                    return rtn_uninstall_code

            rtn_uninstall_code = RtnStatusEnum.SUCCESS.value

            return rtn_uninstall_code

        def uninstall_vm_vf_adapter(vm_name: str, test_port: int = 22) -> int:
            """
            author:      wei.yuan1
            date:        2023-11-30 11:38:57
            description: 使用invoke命令在虚拟机侧卸载vf网卡设备

            :param vm_name: 虚拟机 name
            :return:     卸载成功返回0，失败返回-1
            """
            rtn_uninstall_code = RtnStatusEnum.FAIL.value
            get_adapter_device_id_cmd = CommandOperation.concat_invoke_command(
                vm_name=vm_name, cmd=f"devcon findall {SXE_DEV_MARK_1}")
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
                cmd=get_adapter_device_id_cmd, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip,
                ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server, host_os_client=host_os_client, timeout=180)
            log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                get_adapter_device_id_cmd, cmd_code, cmd_stdout, cmd_stderr))
            if RtnStatusEnum.SUCCESS.value != cmd_code:
                log.error('命令: {}，执行失败'.format(get_adapter_device_id_cmd))
                return rtn_uninstall_code

            match_list = re.findall(r'(PCI\\\S*REV_01)\S*\s*:\s*LD 1160-2X.*', cmd_stdout)
            if not match_list:
                log.error('命令: {}，执行成功，但是输出中未发现VF网卡的deviceid'.format(get_adapter_device_id_cmd))
                return rtn_uninstall_code

            match_list = list(set(match_list))
            for adapt_devid in match_list:
                uninstall_adapt_cmd = CommandOperation.concat_invoke_command(
                    vm_name=vm_name, cmd="pnputil /remove-device /deviceid '{}'".format(adapt_devid))
                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
                    cmd=uninstall_adapt_cmd, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip,
                    ssh_port=str(test_port) if test_port is not None else None,
                    host_os_server=host_os_server, host_os_client=host_os_client, timeout=180)
                log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                    uninstall_adapt_cmd, cmd_code, cmd_stdout, cmd_stderr))
                if RtnStatusEnum.SUCCESS.value != cmd_code:
                    log.error('命令: {}，执行失败'.format(uninstall_adapt_cmd))
                    return rtn_uninstall_code

            rtn_uninstall_code = RtnStatusEnum.SUCCESS.value

            return rtn_uninstall_code

        def check_vm_state(vm_name: str, test_port: int = 22):
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
                cmd=check_cmd, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip, ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server, host_os_client=host_os_client, timeout=180)
            if RtnStatusEnum.SUCCESS.value == rtn_code:
                match_list = re.findall(r'State\s*:\s*(Off|Running)', rtn_stdout)
                if match_list:
                    rtn_state = match_list[0]

            return rtn_state

        def stop_vm(vm_name: str = constants.VM_NAME_DEF, test_port: int = 22) -> tuple:
            """
            author:      haibin.xu
            date:        2023-11-25 16:52:12
            description: 关闭虚拟机

            :param vm_name: 虚拟机name
            :return:     None
            """
            stop_cmd = "Stop-VM -Name '{}' —Force".format(vm_name)
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
                cmd=stop_cmd, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip, ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server, host_os_client=host_os_client, timeout=180)
            # log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            #     stop_cmd, cmd_code, cmd_stdout, cmd_stderr))
            if RtnStatusEnum.SUCCESS.value == cmd_code:
                time.sleep(2)
                if 'Off' != check_vm_state(vm_name, test_port=test_port):
                    log.error('关闭虚拟机命令执行成功，但是检查失败')
                    cmd_code = RtnStatusEnum.FAIL.value

            return stop_cmd, cmd_code, cmd_stdout, cmd_stderr

        def get_adapter_name(vm_name: str, test_port: int = 22):
            """
            获取虚机上所有的网络适配器
            :param vm_name:
            :return:
            """
            vm_adapter_name = []
            exec_command = f"(Get-VMNetworkAdapter -VMName {vm_name}).Name"
            rtn_code, rtn_stdout, rtn_stderr= CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip, ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server, host_os_client=host_os_client
            )
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                stdout_string = rtn_stdout.replace("\r", "")
                stdout_list = stdout_string.split("\n")
                vm_adapter_name = [index for index in stdout_list if index != ""]
            return vm_adapter_name

        def delete_hidden_vmbus(vm_name: str, test_port: int = 22) -> int:
            """
            author:      xiangyu.liu
            date:        2023-11-30 11:38:57
            description: 删除隐藏的VMBUS设备

            :param vm_name: 虚拟机 name
            :return:     卸载成功返回0，失败返回-1
            """
            rtn_uninstall_code = RtnStatusEnum.FAIL.value
            findall_cmd = CommandOperation.concat_invoke_command(
                vm_name=vm_name, cmd="devcon findall *VMBUS*")
            cmd_code, findall_res, cmd_stderr = CommandOperation.execute_command_multi_times(
                cmd=findall_cmd,
                cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip, ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server, host_os_client=host_os_client, timeout=180)
            log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                findall_cmd, cmd_code, findall_res, cmd_stderr))
            if RtnStatusEnum.SUCCESS.value != cmd_code:
                log.error('命令: {}，执行失败'.format(findall_cmd))
                return rtn_uninstall_code

            find_cmd = CommandOperation.concat_invoke_command(
                vm_name=vm_name, cmd="devcon find *VMBUS*")
            cmd_code, find_res, cmd_stderr = CommandOperation.execute_command_multi_times(
                cmd=find_cmd,
                cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip, ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server, host_os_client=host_os_client, timeout=180)
            log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                find_cmd, cmd_code, find_res, cmd_stderr))
            if RtnStatusEnum.SUCCESS.value != cmd_code:
                log.error('命令: {}，执行失败'.format(find_cmd))
                return rtn_uninstall_code

            for vmbus_info in findall_res.split("\n"):
                if vmbus_info not in find_res and "Hyper-V Virtual PCI Bus" in vmbus_info:
                    dev_ins_id = vmbus_info.split(":", 1)[0]
                    dev_ins_id = re.sub(r'(["])', r'\\\1', dev_ins_id)
                    del_hidden_cmd = CommandOperation.concat_invoke_command(
                        vm_name=vm_name, cmd=f"devcon remove \\\"@{dev_ins_id}\\\"")
                    cmd_code, find_res, cmd_stderr = CommandOperation.execute_command_multi_times(
                        cmd=del_hidden_cmd,
                        cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip, ssh_port=str(test_port) if test_port is not None else None,
                        host_os_server=host_os_server, host_os_client=host_os_client, timeout=180, test_times=1)
                    log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                        del_hidden_cmd, cmd_code, find_res, cmd_stderr))
                    if RtnStatusEnum.SUCCESS.value != cmd_code:
                        log.error('命令: {}，执行失败'.format(del_hidden_cmd))
                        return rtn_uninstall_code

            rtn_uninstall_code = RtnStatusEnum.SUCCESS.value

            return rtn_uninstall_code

        vm_list = cls.get_active_vm(ssh_ip=ssh_ip, host_os_client=host_os_client, host_os_server=host_os_server,
                                    cmd_execute_address=cmd_execute_address, test_port=test_port)
        for vm_name_index in vm_list:
            vm_adapter_list = get_adapter_name(
                vm_name=vm_name_index, test_port=test_port)
            log.info_caller(f"@@@@@@@@@@@@@@@@@{vm_adapter_list}")
            uninstall_vm_adapter(vm_name=vm_name_index, test_port=test_port)
            uninstall_vm_vf_adapter(vm_name=vm_name_index, test_port=test_port)
            delete_hidden_vmbus(vm_name=vm_name_index, test_port=test_port)
            stop_vm(vm_name=vm_name_index, test_port=test_port)
            cls.remove_vmnetworkadapter(vm_name=vm_name_index, vm_adapter_name_list=vm_adapter_list,
                                        ssh_ip=ssh_ip, host_os_server=host_os_server, host_os_client=host_os_client,
                                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, test_port=test_port)
            log.info_caller("&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&& test finish")

    @classmethod
    def show_all_switch(cls, ssh_ip: str = None, host_os_server: str = None, host_os_client: str = None,
                        cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, test_port: int = 22):
        switch_list = []
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd="(Get-VMSwitch).Name", cmd_execute_address=cmd_execute_address,
            ssh_ip=ssh_ip, ssh_port=str(test_port) if test_port is not None else None, host_os_server=host_os_server, host_os_client=host_os_client,
            timeout=180)
        if cmd_code == RtnStatusEnum.SUCCESS.value:
            switch_list = [index for index in cmd_stdout.replace("\r", "").split("\n") if index != ""]
        return switch_list

    @classmethod
    def clean_vm_switch(cls, ssh_ip: str = None, host_os_server: str = None, host_os_client: str = None,
                        cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, test_port: int = 22):
        vm_switch_list = cls.show_all_switch(
            ssh_ip=ssh_ip, host_os_server=host_os_server, host_os_client=host_os_client,
            cmd_execute_address=cmd_execute_address, test_port=test_port)
        for vm_switch in vm_switch_list:
            cls.remove_vm_switch(vmswitch_name=vm_switch, execute_address=cmd_execute_address,
                                 ssh_ip=ssh_ip, host_os_client=host_os_client, host_os_server=host_os_server,
                                 test_port=test_port)

    @classmethod
    def remove_vmnetworkadapter(
            cls, vm_name: str, vm_adapter_name_list: list = None, ssh_ip: str = None,
            host_os_server: str = None, host_os_client: str = None,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, test_port: int = 22) -> bool:
        """
        author:      haibin.xu
        date:        2023-11-28 12:04:12
        description: 移除虚拟机网络适配器

        :param vm_name: 虚拟机name
        :param ssh_ip:
        :param host_os_client:
        :param host_os_server:
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
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
                cmd=remove_cmd, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip, ssh_port=str(test_port) if test_port is not None else None,
                host_os_client=host_os_client, host_os_server=host_os_server, timeout=180)
            log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                remove_cmd, cmd_code, cmd_stdout, cmd_stderr))
            if not cls.check_vmadapter_exist(
                    vm_name=vm_name, vm_adapter_name=adapter_name,
                    cmd_execute_address=cmd_execute_address,
                    ssh_ip=ssh_ip, host_os_client=host_os_client, host_os_server=host_os_server, test_port=test_port,
            ):
                log.info('虚拟机：{}，移除网络适配器：{}，成功'.format(vm_name, adapter_name))
            else:
                log.error('虚拟机：{}，移除网络适配器：{}，失败'.format(vm_name, adapter_name))
                rtn_remove_flag = False
                break

        return rtn_remove_flag

    @classmethod
    def remove_vm_switch(cls, vmswitch_name: str, ssh_ip: str = None,
                         host_os_server: str = None, host_os_client: str = None,
                         execute_address: str = CmdExecuteAdressEnum.SERVER.value, test_port: int = 22):
        log.info(f"{execute_address}: 移除{vmswitch_name}")
        vms_name_para = f'\'{vmswitch_name}\'' if vmswitch_name != '*' else '*'
        cmd = f"Remove-VMSwitch -Name {vms_name_para} -Force"
        status, out, err = CommandOperation.execute_command_multi_times(
            cmd=cmd, cmd_execute_address=execute_address, ssh_ip=ssh_ip, ssh_port=str(test_port) if test_port is not None else None,
            host_os_client=host_os_client, host_os_server=host_os_server, timeout=180)
        log.info("status:{}, out:{}, err:{}".format(status, out, err))

    @classmethod
    def check_file_exist(cls, directory_name: str, file_name: str, ssh_ip: str = None,
                         host_os_server: str = None, host_os_client: str = None,
                         cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, ssh_port: str = '22'):
        """
        author: wei.yuan1
        date: 2023.12.29
        description: 检查文件是否存在
        :param directory_name:
        :param file_name:
        :param ssh_ip:
        :param host_os_server:
        :param host_os_client:
        :param cmd_execute_address:
        :return:
        """
        result_code = RtnStatusEnum.FAIL.value
        absolute_path = directory_name + file_name
        exec_command = f"Test-Path {absolute_path}"
        rtn_code, rtn_stdout, rtn_stderr= CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port,
            host_os_server=host_os_server, host_os_client=host_os_client,
            cmd_execute_address=cmd_execute_address, timeout=180)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # 执行运行代码
            exec_command = f'& "{absolute_path}"'
            rtn_code, rtn_stdout, rtn_stderr= CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=absolute_path, ssh_ip=ssh_ip, ssh_port=ssh_port,
                host_os_server=host_os_server, host_os_client=host_os_client,
                cmd_execute_address=cmd_execute_address)
            log.info(f"{absolute_path}文件运行的结果为：{rtn_stdout}\n\n{rtn_stderr}")
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                result_code = RtnStatusEnum.SUCCESS.value
        return result_code

    @classmethod
    def check_vmadapter_exist(
            cls, vm_name: str, vm_adapter_name: str = None, vm_adapter_bind_switch_name: str = None,
            ssh_ip: str = None, host_os_server: str = None, host_os_client: str = None,
            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, test_port: int = 22) -> bool:
        """
        author:      haibin.xu
        date:        2023-11-28 13:42:56
        description: 在物理机侧检查虚拟机适配器是否存在

        :param host_os_client:
        :param ssh_ip:
        :param host_os_server:
        :param vm_name: 虚拟机name
        :param vm_adapter_name: 检查的虚拟机网络适配器name
        :param vm_adapter_bind_switch_name: 检查的虚拟机网络适配器绑定的虚拟交换机name
        :param cmd_execute_address: 命令执行地址信息
        :return:     存在返回True，不存在返回False
        """
        rtn_exist_flag = True
        adapter_param = " -Name '{}'".format(vm_adapter_name) if vm_adapter_name is not None else ''
        check_adapter_cmd = "Get-VMNetworkAdapter -VMName {}{}".format(vm_name, adapter_param)
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
            cmd=check_adapter_cmd, ssh_ip=ssh_ip, ssh_port=str(test_port) if test_port is not None else None,
            host_os_server=host_os_server, host_os_client=host_os_client,
            cmd_execute_address=cmd_execute_address, timeout=180, test_times=1)
        # log.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
        #     check_adapter_cmd, cmd_code, cmd_stdout, cmd_stderr))

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
    def get_target_test_device(cls, test_port: int = None) -> tuple:
        """
        author:             xianda.liu
        date:               2022-09-02
        description:        获取满足连接的server client端测试网卡的子接口名称、ipv4、ipv6、mac地址
        :return: pf_device_name_server,
                 pf_device_name_client,
                {
                    client_device_ip:
                    server_device_ip:
                    client_device_ipv6:
                    server_device_ipv6:
                    client_device_mac:
                    server_device_mac:
                    client_device_name:
                    server_device_name:
                    ---当client_device_name、server_device_name不是pf时，会生成下面键值对
                    server_pf_device_name:
                    client_pf_device_name:
                    ---当client_device_name、server_device_name不是pf时，os为windows，会生成下面键值对
                    server_vf_device_name:
                    client_vf_device_name:

                }
        """
        host_os_server, host_os_client = cls.get_nic_os()
        nicg = CommonOperation.get_nic_generation()
        # step 1 获取相连的连段子接口名称
        test_device_info_dict = dict()
        # todo 可以直接从配置文件准确获取，无需再去环境遍历
        # client_device_name = cls.get_physical_device_name(cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
        # server_device_name = cls.get_physical_device_name(cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        server_device_name, client_device_name = cls.get_nic_relationships()
        server_drv_name, client_drv_name = cls.get_nic_driver_name()
        # log.info("server_device_name:{}".format(server_device_name))
        # log.info("client_device_name:{}".format(client_device_name))

        # 重新組合relation
        s_c_relation_dict = {}
        for server_dev, client_dev in zip(server_device_name, client_device_name):
            s_c_relation_dict[server_dev] = client_dev

        pf_device_name_client, pf_device_name_server = '', ''
        ping_pass_info_list = []

        # 首先剔除client server两端未处于连接状态的网卡子接口
        # for device_name in client_device_name[:]:
        #     if 'windows' != host_os_client:
        #         dict_temp = EthtoolOperation.get_standard_info(
        #             device_name, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
        #         if 'Link detected' not in dict_temp.keys():
        #             client_device_name.remove(device_name)
        #         elif dict_temp['Link detected'] != 'yes':
        #             client_device_name.remove(device_name)
        #     else:
        #         media_state = IfConfig.get_device_media_state(
        #             device_name, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
        #         if media_state:
        #             client_device_name.remove(device_name)
        #
        # for device_name in server_device_name[:]:
        #     if 'windows' != host_os_server:
        #         dict_temp = EthtoolOperation.get_standard_info(
        #             device_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        #         if 'Link detected' not in dict_temp.keys():
        #             server_device_name.remove(device_name)
        #         elif dict_temp['Link detected'] != 'yes':
        #             server_device_name.remove(device_name)
        #     else:
        #         media_state = IfConfig.get_device_media_state(
        #             device_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        #         if media_state:
        #             server_device_name.remove(device_name)

        _, host_os_client = cls.get_nic_os()
        return_flag = False
        # 如果两端都有处于连接状态的子接口，进入是否同链路判断
        pf_device_name_client, pf_device_name_server = '', ''
        if client_device_name and server_device_name:
            # 遍历link status为yes的server client的子接口名称，使用ping命令验证是否可以ping通，如通则认为是同一链路
            result_index = 0
            for index, device_name_s in enumerate(server_device_name):
                condition_server = (device_name_s, CmdExecuteAdressEnum.SERVER.value)
                device_name_c = client_device_name[index]
                condition_client = (device_name_c, CmdExecuteAdressEnum.CLIENT.value)
                ipv4_s = IfConfig.get_device_ipv4_addr(*condition_server,
                                                       test_port=test_port)
                ipv4_c = IfConfig.get_device_ipv4_addr(*condition_client,
                                                       test_port=test_port) if not cls.is_renix_only() else ''
                log.info(f"ipv4_s: {ipv4_s}")
                log.info(f"ipv4_c: {ipv4_c}")
                if result_index == 0:
                    key_mark = ""
                else:
                    key_mark = str(result_index)
                if ipv4_s:
                    if ((server_drv_name not in [NicNameEnum.SXE2.value, NicNameEnum.SCGBE.value] and NicNameEnum.SCE.value not in server_drv_name) and
                            (client_drv_name not in [NicNameEnum.SXE2.value, NicNameEnum.SCGBE.value] and NicNameEnum.SCE.value not in client_drv_name)):
                        log.warning(f'当前非{nicg}环境：[{server_drv_name}]-[{client_drv_name}]，'
                                    f'强制赋值fpag_bit_version={FpgaBitfileClass["A"]}, chip_identification=a')
                        fpag_bit_version = FpgaBitfileClass['A']
                        chip_identification = 'a'
                    else:
                        fpag_bit_version = cls.get_fpga_bitfile_class()
                        chip_identification = cls.get_chip_identification()

                    if 'windows' in host_os_client:
                        ping_success_mark = 'TTL='
                        ping_package_mark = 'Lost = 0 (0% loss)'
                        command = f'ping {ipv4_s} -S {ipv4_c} -n 1'
                    else:
                        ping_success_mark = 'ttl='
                        ping_package_mark = ' 0% packet loss'
                        command = f'ping {ipv4_s} -I {device_name_c} -c 1 -w 5'

                    # 获取当前环境模式，如果是Infiniband,则无需验证ipoib IP是否ping通
                    server_dev_name, client_dev_name = cls.get_nic_relationships()
                    server_bdf = cls.get_bdf_of_nic(server_dev_name[0])
                    nic_mode = cls.get_rdma_mode(server_bdf)
                    if nic_mode == RdmaMode.Infiniband.value:
                        ib_mode = True
                    else:
                        ib_mode = False

                    single_test_mode = cls.get_single_test_mode()

                    # Server端设备=publicnet 或 Client端设备=publicnet
                    if (('publicnet' in s_c_relation_dict.get(device_name_s, "None") or 'publicnet' in device_name_s)
                          or ('publicnet' in device_name_c)):
                        publicnet = True
                    else:
                        publicnet = False

                    # (非RDMA 或 非FPGA) 并且 非renix
                    if (((fpag_bit_version != FpgaBitfileClass['C'] and
                          fpag_bit_version != FpgaBitfileClass['K'] and
                          fpag_bit_version != FpgaBitfileClass['L']) or chip_identification != 'f')
                            and (cls.is_renix_only() == False)
                            and not single_test_mode
                            and not publicnet
                            and (ib_mode == False)):
                        rtn_code, rtn_outputs, rtn_err = \
                            CommandOperation.execute_command_with_error(
                                cmd=command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                ssh_port=str(test_port) if test_port is not None else None)
                    else:
                        if ((fpag_bit_version == FpgaBitfileClass['C']) or
                            (fpag_bit_version == FpgaBitfileClass['K']) or
                            (fpag_bit_version == FpgaBitfileClass['L'])) and chip_identification == 'f':
                            log.warning('C/K/L bitfile FPGA: C/K/L bitfile裁剪了部分以太功能，无法处理icmp报文，跳过ping执行')
                        elif cls.is_renix_only():
                            log.warning('发包仪环境: 跳过ping执行')
                        elif single_test_mode:
                            log.warning('single_mode: 跳过ping执行')
                        elif ib_mode:
                            log.warning('IB模式: 跳过ping执行')
                        elif publicnet:
                            log.warning("公网设备device_name：{}，跳过ping执行".format(device_name_s))

                        rtn_code, rtn_outputs, rtn_err = 1, '', ''

                    # CommonOperation.check_cmd_execute_success(cls, rtn_code, rtn_outputs, command)
                    # log.info("command:{},rtn_code:{}, rtn_outputs:{}, rtn_err:{}".
                    #          format(command, rtn_code, rtn_outputs, rtn_err))
                    log.info("ping_success_mark:{}, ping_package_mark:{}, res:{},{}".
                             format(ping_success_mark, ping_package_mark,
                                    ping_success_mark in rtn_outputs, ping_package_mark in rtn_outputs))
                    # if ' 0%' in rtn_outputs or '(0% ' in rtn_outputs:
                    fpga_c = False
                    renix_env = False
                    if ping_package_mark not in rtn_outputs:
                        # ping不通，检查是否是单端测试模式
                        if single_test_mode:
                            log.warning("当前两端ping不通，但设置为单端测试模式，将返回配置在env_config.ini内的网口信息")
                        if ((fpag_bit_version == FpgaBitfileClass['C']) or
                            (fpag_bit_version == FpgaBitfileClass['K']) or
                            (fpag_bit_version == FpgaBitfileClass['L'])) and chip_identification == 'f':
                            fpga_c = True
                            log.warning("当前两端ping不通，但是FPGA-C/K/L bitfile，将返回配置在env_config.ini内的网口信息")
                        if cls.is_renix_only():
                            renix_env = True
                            log.warning("当前两端ping不通，但是发包仪环境，将返回配置在env_config.ini内的网口信息")
                        if publicnet:
                            log.warning("公网环境，将返回配置在env_config.ini内的网口信息")

                    if (ping_success_mark in rtn_outputs and ping_package_mark in rtn_outputs) or single_test_mode or fpga_c or renix_env or ib_mode or publicnet:
                        # pf_device_name_client，pf_device_name_server用于vf、vlan、macvlan创建
                        # 此处赋值需只赋值第一个ping通端口信息，否则用于vf、vlan、macvlan会错位
                        if pf_device_name_client == '' or pf_device_name_server == '':
                            pf_device_name_client = device_name_c
                            pf_device_name_server = device_name_s

                        if not renix_env and not publicnet:
                            client_info_dict = IfConfig.analysis_ifconfig_info(*condition_client, test_port=test_port)
                        else:
                            client_info_dict = {}
                        server_info_dict = IfConfig.analysis_ifconfig_info(*condition_server, test_port=test_port)

                        test_device_info_dict['server{}_device_ip'.format(key_mark)] = \
                            server_info_dict.get(constants.INET)
                        test_device_info_dict['server{}_device_mac'.format(key_mark)] = \
                            server_info_dict.get(constants.ETHER)
                        test_device_info_dict['server{}_device_name'.format(key_mark)] = device_name_s
                        test_device_info_dict['server{}_pf_device_name'.format(key_mark)] = device_name_s
                        if not renix_env and not single_test_mode and not publicnet:
                            test_device_info_dict['client{}_device_ip'.format(key_mark)] = \
                                client_info_dict.get(constants.INET)
                            test_device_info_dict['client{}_device_mac'.format(key_mark)] = \
                                client_info_dict.get(constants.ETHER)
                            test_device_info_dict['client{}_device_name'.format(key_mark)] = device_name_c
                            test_device_info_dict['client{}_pf_device_name'.format(key_mark)] = device_name_c
                        else:
                            test_device_info_dict['client{}_device_ip'.format(key_mark)] = 'unrealized'
                            test_device_info_dict['client{}_device_mac'.format(key_mark)] = 'unrealized'
                            test_device_info_dict['client{}_device_name'.format(key_mark)] = 'unrealized'
                            test_device_info_dict['client{}_pf_device_name'.format(key_mark)] = 'unrealized'
                        # 获取bdf
                        if 'windows' in host_os_server:
                            test_device_info_dict['server{}_bus_info'.format(key_mark)] = "unrealized"
                        else:
                            device_info_dict = EthtoolOperation.show_driver_infomation(
                                device_name=device_name_s, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                test_port=test_port)
                            test_device_info_dict['server{}_bus_info'.format(key_mark)] = device_info_dict['bus-info']

                        if 'windows' in host_os_client:
                            test_device_info_dict['client{}_bus_info'.format(key_mark)] = "unrealized"
                        elif cls.is_renix_only() or single_test_mode or publicnet:
                            test_device_info_dict['client{}_bus_info'.format(key_mark)] = "unrealized"
                        else:
                            device_info_dict = EthtoolOperation.show_driver_infomation(
                                device_name=device_name_c, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                test_port=test_port)
                            test_device_info_dict['client{}_bus_info'.format(key_mark)] = device_info_dict['bus-info']

                        # 更新Infiniband地址
                        server_dev_name, client_dev_name = cls.get_nic_relationships()
                        server_bdf = cls.get_bdf_of_nic(server_dev_name[0], cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        rdma_mode_server = cls.get_rdma_mode(server_bdf, CmdExecuteAdressEnum.SERVER.value)
                        client_bdf = cls.get_bdf_of_nic(client_dev_name[0], cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        rdma_mode_client = cls.get_rdma_mode(client_bdf, CmdExecuteAdressEnum.CLIENT.value)
                        if RdmaMode.Infiniband.value == rdma_mode_server:
                            test_device_info_dict['server{}_device_mac'.format(key_mark)] = \
                                'unrealized'
                        if RdmaMode.Infiniband.value == rdma_mode_client:
                            test_device_info_dict['client{}_device_mac'.format(key_mark)] = \
                                'unrealized'
                        # rdma_mode_server = cls.get_rdma_mode(test_device_info_dict['server{}_bus_info'.format(key_mark)], CmdExecuteAdressEnum.SERVER.value)
                        # rdma_mode_client = cls.get_rdma_mode(test_device_info_dict['client{}_bus_info'.format(key_mark)], CmdExecuteAdressEnum.CLIENT.value)
                        # if RdmaMode.Infiniband.value == rdma_mode_server:
                        #     test_device_info_dict['server{}_device_mac'.format(key_mark)] = \
                        #         server_info_dict.get(constants.INFINIBAND)
                        # if RdmaMode.Infiniband.value == rdma_mode_client:
                        #     test_device_info_dict['client{}_device_mac'.format(key_mark)] = \
                        #         client_info_dict.get(constants.INFINIBAND)

                        # 如果ipv6地址为空，则尝试ifup接口
                        if client_info_dict.get(constants.INET6):
                            test_device_info_dict['client{}_device_ipv6'.format(key_mark)] = \
                                client_info_dict.get(constants.INET6)
                        elif cls.is_renix_only() or single_test_mode or publicnet:
                            test_device_info_dict['client{}_device_ipv6'.format(key_mark)] = "unrealized"
                        else:
                            IfConfig.set_device_soft_down(
                                device_name=device_name_c,
                                cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, test_port=test_port)
                            IfConfig.set_device_soft_up(device_name=device_name_c,
                                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                        test_port=test_port)
                            client_info_dict = IfConfig.analysis_ifconfig_info(*condition_client,
                                                                               test_port=test_port)
                            test_device_info_dict['client{}_device_ipv6'.format(key_mark)] = \
                                client_info_dict.get(constants.INET6)
                        if server_info_dict.get(constants.INET6):
                            test_device_info_dict['server{}_device_ipv6'.format(key_mark)] = \
                                server_info_dict.get(constants.INET6)
                        else:
                            IfConfig.set_device_soft_down(
                                device_name=device_name_s,
                                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, test_port=test_port)
                            IfConfig.set_device_soft_up(device_name=device_name_s,
                                                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                        test_port=test_port)
                            server_info_dict = IfConfig.analysis_ifconfig_info(*condition_server,
                                                                               test_port=test_port)
                            test_device_info_dict['server{}_device_ipv6'.format(key_mark)] = \
                                server_info_dict.get(constants.INET6)

                        return_flag = True
                        result_index += 1
                        # break
                        ping_pass_info_list.append([device_name_s, device_name_c])
                    else:
                        log.error(f"本端{device_name_s}与对端{device_name_c}之间ping不通!!")

            if len(ping_pass_info_list) != len(server_device_name):
                for item in ping_pass_info_list:
                    log.info(f"本端{item[0]}与对端{item[1]}之间可ping通.")
                # 重新赋空
                pf_device_name_client = ""
                pf_device_name_server = ""

            # 如果没有可以Ping通的pf接口,则返回空字典
            if pf_device_name_client == '' or pf_device_name_server == '':
                log.error('存在不可ping通的pf接口')
        return pf_device_name_server, pf_device_name_client, test_device_info_dict

    @classmethod
    def get_test_device_info(cls, caller_class) -> tuple:
        """
        author:             xianda.liu
        date:               2022-09-02
        description:        获取满足连接的server client端测试网卡的子接口名称、ipv4、ipv6、mac地址
        :param caller_class: 调用此方法的二级基类，用于拿到基类中的测试设备种类，如PF,VF,vlan,macvlan等
        :return: [{
                    client_device_ip:
                    server_device_ip:
                    client_device_ipv6:
                    server_device_ipv6:
                    client_device_mac:
                    server_device_mac:
                    client_device_name:
                    server_device_name:
                    ---当client_device_name、server_device_name不是pf时，会生成下面键值对
                    server_pf_device_name:
                    client_pf_device_name:
                }]
        @changelog:
        1. 2024.7.24：liuxy:
            1. 为适配多port测试以及现有脚本，返回类型由dict修改为dict, list;
            2. 内部处理适配多port测试，对每个pf按照test_object创建vf、macvlan、vlan等
        """
        # 物理机OS
        host_os_server, host_os_client = cls.get_nic_os()
        # 虚拟机os
        guest_os_server, guest_os_client = cls.get_guest_os(caller_class.test_direction_reverse)

        pf_device_name_server, pf_device_name_client, test_device_info_dict = cls.get_target_test_device()
        if caller_class.test_port_reverse and "server1_device_ip" in test_device_info_dict.keys():
            log.warning("****将两网口信息对调，当存在2个以上端口时将网口信息逆序，即最后一个网卡会作为目标网口****")
            test_device_info_list = cls.get_test_device_info_list(test_device_info_dict)
            temp_dict = {}
            test_device_info_list.reverse()
            for port_index, info_dict in enumerate(test_device_info_list):
                if port_index == 0:
                    key_mark = ""
                else:
                    key_mark = str(port_index)
                for k, v in info_dict.items():
                    new_key = k.replace("client_", "client{}_".format(key_mark)). \
                        replace("server_", "server{}_".format(key_mark))
                    test_device_info_dict[new_key] = v

            pf_device_name_server = test_device_info_dict['server_device_name']
            pf_device_name_client = test_device_info_dict['client_device_name']

        # 2024.7.24: 为适配多port测试，将dict转换为list
        test_device_info_list = cls.get_test_device_info_list(test_device_info_dict)
        org_test_device_info_dict = test_device_info_dict.copy()

        # 2025.02.25 如果是发包仪环境，直接返回列表，不再创建设备
        if CommonOperation.is_renix_only():
            log.warning('发包仪环境，直接返回配置在env_config.ini中的信息，不再创建设备')
            return org_test_device_info_dict, test_device_info_list

        # 如果没有可以Ping通的pf接口,则返回空列表
        if pf_device_name_client == '' or pf_device_name_server == '':
            return org_test_device_info_dict, test_device_info_list

        from scripts.script_libs.ip_operation import IpOperation
        # 2024.7.24: 内部处理适配多port测试，对每个pf按照test_object创建vf、macvlan、vlan等
        for port, test_device_info_dict in enumerate(test_device_info_list):
            pf_device_name_client = test_device_info_list[port]['client_pf_device_name']
            pf_device_name_server = test_device_info_list[port]['server_pf_device_name']
            condition_client_renew, condition_server_renew = '', ''
            client_vf0_bus_info, server_vf0_bus_info = '', ''
            # 如果都是windows环境，就不乱搞了
            if 'windows' in host_os_server and 'windows' in host_os_client:
                # 处理server端
                state = cls.prepare_test_device_before_run_script(caller_class,
                                                                  device_name_server=pf_device_name_server)
                if state == RtnStatusEnum.FAIL.value:
                    log.error("prepare_test_device_before_run_script fail !")
                    return {}, []
                if caller_class.server_test_object == TestObjectType.VF.value:
                    test_device_name = f"vEthernet ({V_SWITCH_SRIOV_NAME_DEF})"
                    condition_server_renew = (test_device_name, CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.VLAN.value:
                    pass
                elif caller_class.server_test_object == TestObjectType.MACVLAN.value:
                    test_device_name = f"vEthernet ({V_SWITCH_VMQ_NAME_DEF})"
                    condition_server_renew = (test_device_name, CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.VFVLAN.value:
                    test_device_name = f"vEthernet ({V_SWITCH_SRIOV_NAME_DEF})"
                    condition_server_renew = (test_device_name, CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.VFMACVLAN.value:
                    pass
                elif caller_class.server_test_object == TestObjectType.VFVMQ.value:
                    test_device_name = f"vEthernet ({V_SWITCH_VMQ_NAME_DEF})"
                    condition_server_renew = (test_device_name, CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.DEGVMQ.value:
                    test_device_name = f"vEthernet ({V_SWITCH_DEGVMQ_NAME_DEF})"
                    condition_server_renew = (test_device_name, CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.VFVMQVLAN.value:
                    test_device_name = f"vEthernet ({V_SWITCH_VMQ_NAME_DEF})"
                    condition_server_renew = (test_device_name, CmdExecuteAdressEnum.SERVER.value)
                else:
                    pass
                # 处理client端
                state = cls.prepare_test_device_before_run_script(caller_class,
                                                                  device_name_client=pf_device_name_client)
                if state == RtnStatusEnum.FAIL.value:
                    log.error("prepare_test_device_before_run_script fail !")
                    return {}, []
                if caller_class.client_test_object == TestObjectType.VF.value:
                    test_device_name = f"vEthernet ({V_SWITCH_SRIOV_NAME_DEF})"
                    condition_client_renew = (test_device_name, CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.VLAN.value:
                    pass
                elif caller_class.client_test_object == TestObjectType.MACVLAN.value:
                    test_device_name = f"vEthernet ({V_SWITCH_VMQ_NAME_DEF})"
                    condition_client_renew = (test_device_name, CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.VFVLAN.value:
                    test_device_name = f"vEthernet ({V_SWITCH_SRIOV_NAME_DEF})"
                    condition_client_renew = (test_device_name, CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.VFMACVLAN.value:
                    pass
                elif caller_class.client_test_object == TestObjectType.DEGVMQ.value:
                    test_device_name = f"vEthernet ({V_SWITCH_DEGVMQ_NAME_DEF})"
                    condition_client_renew = (test_device_name, CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.VFVMQ.value:
                    test_device_name = f"vEthernet ({V_SWITCH_VMQ_NAME_DEF})"
                    condition_client_renew = (test_device_name, CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.VFVMQVLAN.value:
                    test_device_name = f"vEthernet ({V_SWITCH_VMQ_NAME_DEF})"
                    condition_client_renew = (test_device_name, CmdExecuteAdressEnum.CLIENT.value)
                else:
                    pass
            # server端是windows，处理client端
            elif 'windows' in host_os_server:
                if caller_class.client_test_object == TestObjectType.DEGVMQ.value:
                    log.error(f"client是{host_os_client}系统, 不支持VMQ测试, skip...")
                    return {}, []
                elif caller_class.client_test_object == TestObjectType.VFVMQ.value:
                    log.error(f"client是{host_os_client}系统, 不支持VMQ测试, skip...")
                    return {}, []
                elif caller_class.client_test_object == TestObjectType.VFVMQVLAN.value:
                    log.error(f"client是{host_os_client}系统, 不支持VMQ测试, skip...")
                    return {}, []
                else:
                    pass

                # 处理server端
                state = cls.prepare_test_device_before_run_script(caller_class,
                                                                  device_name_server=pf_device_name_server)
                if state == RtnStatusEnum.FAIL.value:
                    log.error("prepare_test_device_before_run_script fail !")
                    return {}, []
                if caller_class.server_test_object == TestObjectType.VF.value:
                    test_device_name = f"vEthernet ({V_SWITCH_SRIOV_NAME_DEF})"
                    condition_server_renew = (test_device_name, CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.VLAN.value:
                    pass
                elif caller_class.server_test_object == TestObjectType.MACVLAN.value:
                    test_device_name = f"vEthernet ({V_SWITCH_VMQ_NAME_DEF})"
                    condition_server_renew = (test_device_name, CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.VFVLAN.value:
                    test_device_name = f"vEthernet ({V_SWITCH_SRIOV_NAME_DEF})"
                    condition_server_renew = (test_device_name, CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.VFMACVLAN.value:
                    pass
                elif caller_class.server_test_object == TestObjectType.DEGVMQ.value:
                    test_device_name = f"vEthernet ({V_SWITCH_DEGVMQ_NAME_DEF})"
                    condition_server_renew = (test_device_name, CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.VFVMQ.value:
                    test_device_name = f"vEthernet ({V_SWITCH_VMQ_NAME_DEF})"
                    condition_server_renew = (test_device_name, CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.VFVMQVLAN.value:
                    test_device_name = f"vEthernet ({V_SWITCH_VMQ_NAME_DEF})"
                    condition_server_renew = (test_device_name, CmdExecuteAdressEnum.SERVER.value)
                else:
                    pass
                # 处理client端
                state = cls.prepare_test_device_before_run_script(caller_class,
                                                                  device_name_client=pf_device_name_client)
                if state == RtnStatusEnum.FAIL.value:
                    log.error("prepare_test_device_before_run_script fail !")
                    return {}, []
                if caller_class.client_test_object == TestObjectType.VF.value:
                    test_device_name = cls.get_vf_device_names_by_pf(
                        pf_device_name=pf_device_name_client,
                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)[0]
                    condition_client_renew = (test_device_name, CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.VLAN.value:
                    condition_client_renew = (pf_device_name_client + '.1', CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.MACVLAN.value:
                    condition_client_renew = ('p' + pf_device_name_client[-1] + 'macvlan1', CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.VFVLAN.value:
                    test_device_name = cls.get_vf_device_names_by_pf(
                        pf_device_name=pf_device_name_client,
                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)[0]
                    condition_client_renew = (test_device_name + '.1', CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.VFMACVLAN.value:
                    condition_client_renew = ('p' + pf_device_name_client[-1] + 'v0' + 'macvlan1', CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.DEGVMQ.value:
                    log.error(f"client是{host_os_client}系统, 不支持VMQ测试, skip...")
                    return {}, []
                elif caller_class.client_test_object == TestObjectType.VFVMQ.value:
                    log.error(f"client是{host_os_client}系统, 不支持VMQ测试, skip...")
                    return {}, []
                elif caller_class.client_test_object == TestObjectType.VFVMQVLAN.value:
                    log.error(f"client是{host_os_client}系统, 不支持VMQ测试, skip...")
                    return {}, []
                else:
                    pass
            # client端是windows，处理server端
            elif 'windows' in host_os_client:
                # server不是windows，提前处理vmq退出
                if caller_class.server_test_object == TestObjectType.DEGVMQ.value:
                    log.error(f"server是{host_os_server}系统, 不支持VMQ, skip...")
                    return {}, []
                elif caller_class.server_test_object == TestObjectType.VFVMQ.value:
                    log.error(f"server是{host_os_server}系统, 不支持VMQ, skip...")
                    return {}, []
                elif caller_class.server_test_object == TestObjectType.VFVMQVLAN.value:
                    log.error(f"server是{host_os_server}系统, 不支持VMQ, skip...")
                    return {}, []
                else:
                    pass

                # 处理client端
                state = cls.prepare_test_device_before_run_script(caller_class,
                                                                  device_name_client=pf_device_name_client)
                if state == RtnStatusEnum.FAIL.value:
                    log.error("prepare_test_device_before_run_script fail !")
                    return {}, []
                if caller_class.client_test_object == TestObjectType.VF.value:
                    test_device_name = f"vEthernet ({V_SWITCH_SRIOV_NAME_DEF})"
                    condition_client_renew = (test_device_name, CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.VLAN.value:
                    pass
                elif caller_class.client_test_object == TestObjectType.MACVLAN.value:
                    test_device_name = f"vEthernet ({V_SWITCH_VMQ_NAME_DEF})"
                    condition_client_renew = (test_device_name, CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.VFVLAN.value:
                    test_device_name = f"vEthernet ({V_SWITCH_SRIOV_NAME_DEF})"
                    condition_client_renew = (test_device_name, CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.VFMACVLAN.value:
                    pass
                elif caller_class.client_test_object == TestObjectType.DEGVMQ.value:
                    test_device_name = f"vEthernet ({V_SWITCH_DEGVMQ_NAME_DEF})"
                    condition_client_renew = (test_device_name, CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.VFVMQ.value:
                    test_device_name = f"vEthernet ({V_SWITCH_VMQ_NAME_DEF})"
                    condition_client_renew = (test_device_name, CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.VFVMQVLAN.value:
                    test_device_name = f"vEthernet ({V_SWITCH_VMQ_NAME_DEF})"
                    condition_client_renew = (test_device_name, CmdExecuteAdressEnum.CLIENT.value)
                else:
                    pass

                # 处理server端
                state = cls.prepare_test_device_before_run_script(caller_class,
                                                                  device_name_server=pf_device_name_server)
                if state == RtnStatusEnum.FAIL.value:
                    log.error("prepare_test_device_before_run_script fail !")
                    return {}, []
                if caller_class.server_test_object == TestObjectType.VF.value:
                    test_device_name = cls.get_vf_device_names_by_pf(
                        pf_device_name=pf_device_name_server,
                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)[0]
                    condition_server_renew = (test_device_name, CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.VLAN.value:
                    condition_server_renew = (pf_device_name_server + '.1', CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.MACVLAN.value:
                    condition_server_renew = ('p' + pf_device_name_server[-1] + 'macvlan1', CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.VFVLAN.value:
                    test_device_name = cls.get_vf_device_names_by_pf(
                        pf_device_name=pf_device_name_server,
                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)[0]
                    condition_server_renew = (test_device_name + '.1', CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.VFMACVLAN.value:
                    condition_server_renew = ('p' + pf_device_name_server[-1] + 'v0' + 'macvlan1', CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.DEGVMQ.value:
                    log.error(f"server是{host_os_server}系统, 不支持VMQ, skip...")
                    return {}, []
                elif caller_class.server_test_object == TestObjectType.VFVMQ.value:
                    log.error(f"server是{host_os_server}系统, 不支持VMQ, skip...")
                    return {}, []
                elif caller_class.server_test_object == TestObjectType.VFVMQVLAN.value:
                    log.error(f"server是{host_os_server}系统, 不支持VMQ, skip...")
                    return {}, []
                else:
                    pass
            # 两端都是linux
            else:
                # 下面代码需要按client和server拆出两块
                # step 2 根据基类需要，完成vf、vlan、macvlan创建, 如果是PF无影响
                state = cls.prepare_test_device_before_run_script(caller_class,
                                                                  device_name_client=pf_device_name_client)
                if state == RtnStatusEnum.FAIL.value:
                    log.error("prepare_test_device_before_run_script fail !")
                    return {}, []
                state = cls.prepare_test_device_before_run_script(caller_class,
                                                                  device_name_server=pf_device_name_server)
                if state == RtnStatusEnum.FAIL.value:
                    log.error("prepare_test_device_before_run_script fail !")
                    return {}, []
                # step 3 统一生成test_device_info_dict字典
                if caller_class.server_test_object == TestObjectType.VF.value:
                    if "windows" not in guest_os_server:
                        test_device_name = cls.get_vf_device_names_by_pf(
                            pf_device_name=pf_device_name_server,
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)[0]
                        device_info_dict = EthtoolOperation.show_driver_infomation(
                            device_name=test_device_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        server_vf0_bus_info = device_info_dict['bus-info']
                    else:
                        test_device_name = \
                            CommonOperation.get_vf_name(CmdExecuteAdressEnum.SERVER.value, constants.KVM_VM_NAME)
                    condition_server_renew = (test_device_name, CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.VLAN.value:
                    # if len(pf_device_name_server + '.1.10') > 15:
                    #     condition_server_renew = (
                    #     (pf_device_name_server + '.1.10')[-15:], CmdExecuteAdressEnum.SERVER.value)
                    # else:
                    #     condition_server_renew = (pf_device_name_server + '.1', CmdExecuteAdressEnum.SERVER.value)
                    condition_server_renew = (IpOperation.create_vlan_name(pf_device_name_server, '1'), CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.DVLAN.value:
                    # if len(pf_device_name_server + '.1.10') > 15:
                    #     condition_server_renew = (
                    #     (pf_device_name_server + '.1.10')[-15:], CmdExecuteAdressEnum.SERVER.value)
                    # else:
                    #     condition_server_renew = (pf_device_name_server + '.1.10', CmdExecuteAdressEnum.SERVER.value)
                    condition_server_renew = (IpOperation.create_vlan_name(pf_device_name_server, '1.10'), CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.MACVLAN.value:
                    condition_server_renew = ('p' + pf_device_name_server[-1] + 'macvlan1', CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.VFVLAN.value:
                    if "windows" not in guest_os_server:
                        test_device_name = cls.get_vf_device_names_by_pf(
                            pf_device_name=pf_device_name_server,
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)[0]
                    else:
                        test_device_name = \
                            CommonOperation.get_vf_name(CmdExecuteAdressEnum.SERVER.value, constants.KVM_VM_NAME)
                    # if len(pf_device_name_server + '.1.10') > 15:
                    #     condition_server_renew = (
                    #     (test_device_name + '.1.10')[-15:], CmdExecuteAdressEnum.SERVER.value)
                    # else:
                    #     condition_server_renew = (test_device_name + '.1', CmdExecuteAdressEnum.SERVER.value)
                    condition_server_renew = (IpOperation.create_vlan_name(test_device_name, '1'), CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.VFDVLAN.value:
                    if "windows" not in guest_os_server:
                        test_device_name = cls.get_vf_device_names_by_pf(
                            pf_device_name=pf_device_name_server,
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)[0]
                    else:
                        test_device_name = \
                            CommonOperation.get_vf_name(CmdExecuteAdressEnum.SERVER.value, constants.KVM_VM_NAME)
                    # if len(test_device_name + '.1.10') > 15:
                    #     condition_server_renew = (
                    #     (test_device_name + '.1.10')[-15:], CmdExecuteAdressEnum.SERVER.value)
                    # else:
                    #     condition_server_renew = (test_device_name + '.1.10', CmdExecuteAdressEnum.SERVER.value)
                    condition_server_renew = (IpOperation.create_vlan_name(test_device_name, '1.10'), CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.VFMACVLAN.value:
                    condition_server_renew = ('p' + pf_device_name_server[-1] + 'v0' + 'macvlan1', CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.BOND1.value:
                    condition_server_renew = ('bond0m1', CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.BOND2.value:
                    condition_server_renew = ('bond0m2', CmdExecuteAdressEnum.SERVER.value)
                elif caller_class.server_test_object == TestObjectType.BOND4.value:
                    condition_server_renew = ('bond0m4', CmdExecuteAdressEnum.SERVER.value)
                else:
                    pass

                if caller_class.client_test_object == TestObjectType.VF.value:
                    if "windows" not in guest_os_client:
                        test_device_name = cls.get_vf_device_names_by_pf(
                            pf_device_name=pf_device_name_client,
                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)[0]
                        device_info_dict = EthtoolOperation.show_driver_infomation(
                            device_name=test_device_name, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        client_vf0_bus_info = device_info_dict['bus-info']
                    else:
                        test_device_name = \
                            CommonOperation.get_vf_name(CmdExecuteAdressEnum.CLIENT.value, constants.KVM_VM_NAME)
                    condition_client_renew = (test_device_name, CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.VLAN.value:
                    # condition_client_renew = (pf_device_name_client + '.1', CmdExecuteAdressEnum.CLIENT.value)
                    condition_client_renew = (IpOperation.create_vlan_name(pf_device_name_client, '1'), CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.DVLAN.value:
                    # if len(pf_device_name_client + '.1.10') > 15:
                    #     condition_client_renew = (
                    #     (pf_device_name_client + '.1.10')[-15:], CmdExecuteAdressEnum.CLIENT.value)
                    # else:
                    #     condition_client_renew = (pf_device_name_client + '.1.10', CmdExecuteAdressEnum.CLIENT.value)
                    condition_client_renew = (IpOperation.create_vlan_name(pf_device_name_client, '1.10'), CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.MACVLAN.value:
                    condition_client_renew = ('p' + pf_device_name_client[-1] + 'macvlan1', CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.VFVLAN.value:
                    if "windows" not in guest_os_client:
                        test_device_name = cls.get_vf_device_names_by_pf(
                            pf_device_name=pf_device_name_client,
                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)[0]
                    else:
                        test_device_name = \
                            CommonOperation.get_vf_name(CmdExecuteAdressEnum.CLIENT.value, constants.KVM_VM_NAME)
                    # if len(pf_device_name_client + '.1.10') > 15:
                    #     condition_client_renew = (
                    #     (test_device_name + '.1')[-15:], CmdExecuteAdressEnum.CLIENT.value)
                    # else:
                    #     condition_client_renew = (test_device_name + '.1', CmdExecuteAdressEnum.CLIENT.value)
                    condition_client_renew = (IpOperation.create_vlan_name(test_device_name, '1'), CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.VFDVLAN.value:
                    if "windows" not in guest_os_client:
                        test_device_name = cls.get_vf_device_names_by_pf(
                            pf_device_name=pf_device_name_client,
                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)[0]
                    else:
                        test_device_name = \
                            CommonOperation.get_vf_name(CmdExecuteAdressEnum.CLIENT.value, constants.KVM_VM_NAME)
                    # if len(test_device_name + '.1.10') > 15:
                    #     condition_client_renew = (
                    #     (test_device_name + '.1.10')[-15:], CmdExecuteAdressEnum.CLIENT.value)
                    # else:
                    #     condition_client_renew = (test_device_name + '.1.10', CmdExecuteAdressEnum.CLIENT.value)
                    condition_client_renew = (IpOperation.create_vlan_name(test_device_name, '1.10'), CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.VFMACVLAN.value:
                    condition_client_renew = ('p' + pf_device_name_client[-1] + 'v0' + 'macvlan1', CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.BOND1.value:
                    condition_client_renew = ('bond0m1', CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.BOND2.value:
                    condition_client_renew = ('bond0m2', CmdExecuteAdressEnum.CLIENT.value)
                elif caller_class.client_test_object == TestObjectType.BOND4.value:
                    condition_client_renew = ('bond0m4', CmdExecuteAdressEnum.CLIENT.value)
                else:
                    pass

            log.info(
                f"condition_server_renew:{condition_server_renew}, condition_client_renew:{condition_client_renew}")
            if condition_server_renew:
                # Linux
                if 'windows' not in host_os_server:
                    server_info_dict = IfConfig.analysis_ifconfig_info(*condition_server_renew)
                    test_device_info_dict['server_win_vm_ip'] = ""
                    test_device_info_dict['server_device_ip'] = server_info_dict.get(constants.INET)
                    test_device_info_dict['server_device_ipv6'] = server_info_dict.get(constants.INET6)
                    test_device_info_dict['server_device_mac'] = server_info_dict.get(constants.ETHER)
                    test_device_info_dict['server_device_name'] = condition_server_renew[0]
                    test_device_info_dict['server_pf_device_name'] = pf_device_name_server
                    if caller_class.server_test_object == TestObjectType.VF.value:
                        test_device_info_dict['server_bus_info'] = server_vf0_bus_info
                    # linux下windows虚拟机
                    if "windows" in guest_os_server:
                        status, server_info_dict = \
                            CommonOperation.check_kvm_stats(cls.vm_name, execute_address=condition_server_renew[1],
                                                            check_running=False,
                                                            device_name_server=condition_server_renew[0],
                                                            device_name_client="")
                        if not status:
                            log.error("check_vm_stats failed, skip...")
                            return {}, []
                        test_device_info_dict['server_win_vm_ip'] = server_info_dict["vm_ip"]
                        test_device_info_dict['server_device_ip'] = server_info_dict["vf_ip"]
                        test_device_info_dict['server_device_ipv6'] = server_info_dict["vf_ipv6"]
                        test_device_info_dict['server_device_mac'] = server_info_dict["vf_mac_addr"]
                        test_device_info_dict['server_device_name'] = server_info_dict["vf_name"]
                        test_device_info_dict['server_vf_device_name'] = server_info_dict["vf_name"]
                        test_device_info_dict['server_pf_device_name'] = pf_device_name_server
                # windows pf
                elif "vEthernet" not in condition_server_renew[0] and ('windows' in host_os_server):
                    server_info_dict = IfConfig.analysis_ifconfig_info(*condition_server_renew)
                    test_device_info_dict['server_win_vm_ip'] = ""
                    test_device_info_dict['server_device_ip'] = server_info_dict.get(constants.INET)
                    test_device_info_dict['server_device_ipv6'] = server_info_dict.get(constants.INET6)
                    test_device_info_dict['server_device_mac'] = server_info_dict.get(constants.ETHER)
                    test_device_info_dict['server_device_name'] = condition_server_renew[0]
                    test_device_info_dict['server_pf_device_name'] = pf_device_name_server
                # windows vf
                elif "sriov" in condition_server_renew[0].lower():
                    status, server_info_dict = \
                        CommonOperation.check_vm_stats(cls.vm_name, condition_server_renew[1], check_running=False)
                    if not status:
                        log.error("check_vm_stats failed, skip...")
                        return {}, []
                    test_device_info_dict['server_win_vm_ip'] = server_info_dict["vm_ip"]
                    test_device_info_dict['server_device_ip'] = server_info_dict["vf_ip"]
                    test_device_info_dict['server_device_ipv6'] = server_info_dict["vf_ipv6"]
                    test_device_info_dict['server_device_mac'] = server_info_dict["vf_mac_addr"]
                    test_device_info_dict['server_device_name'] = server_info_dict["hyperv_adapter_name"]
                    test_device_info_dict['server_vf_device_name'] = server_info_dict["vf_name"]
                    test_device_info_dict['server_pf_device_name'] = pf_device_name_server
                # windows vf degvmq
                elif "degvmq" in condition_server_renew[0].lower():
                    status, server_info_dict = \
                        CommonOperation.check_vm_stats(cls.vm_name, condition_server_renew[1], check_running=False,
                                                       virtual_mode=VirtualModeEnum.DEGVMQ.value)
                    if not status:
                        log.error("check_vm_stats failed, skip...")
                        return {}, []
                    test_device_info_dict['server_win_vm_ip'] = server_info_dict["vm_ip"]
                    test_device_info_dict['server_device_ip'] = server_info_dict["vf_ip"]
                    test_device_info_dict['server_device_ipv6'] = server_info_dict["vf_ipv6"]
                    test_device_info_dict['server_device_mac'] = server_info_dict["vf_mac_addr"]
                    test_device_info_dict['server_device_name'] = server_info_dict["hyperv_adapter_name"]
                    test_device_info_dict['server_vf_device_name'] = server_info_dict["vf_name"]
                    test_device_info_dict['server_pf_device_name'] = pf_device_name_server
                # windows vf vmq
                else:
                    status, server_info_dict = \
                        CommonOperation.check_vm_stats(cls.vm_name, condition_server_renew[1], check_running=False,
                                                       virtual_mode=VirtualModeEnum.VMQ.value)
                    if not status:
                        log.error("check_vm_stats failed, skip...")
                        return {}, []
                    test_device_info_dict['server_win_vm_ip'] = server_info_dict["vm_ip"]
                    test_device_info_dict['server_device_ip'] = server_info_dict["vf_ip"]
                    test_device_info_dict['server_device_ipv6'] = server_info_dict["vf_ipv6"]
                    test_device_info_dict['server_device_mac'] = server_info_dict["vf_mac_addr"]
                    test_device_info_dict['server_device_name'] = server_info_dict["hyperv_adapter_name"]
                    test_device_info_dict['server_vf_device_name'] = server_info_dict["vf_name"]
                    test_device_info_dict['server_pf_device_name'] = pf_device_name_server
            else:
                test_device_info_dict['server_win_vm_ip'] = ""

            if condition_client_renew:
                # Linux
                if 'windows' not in host_os_client:
                    client_info_dict = IfConfig.analysis_ifconfig_info(*condition_client_renew)
                    test_device_info_dict['client_win_vm_ip'] = ""
                    test_device_info_dict['client_device_ip'] = client_info_dict.get(constants.INET)
                    test_device_info_dict['client_device_ipv6'] = client_info_dict.get(constants.INET6)
                    test_device_info_dict['client_device_mac'] = client_info_dict.get(constants.ETHER)
                    test_device_info_dict['client_device_name'] = condition_client_renew[0]
                    test_device_info_dict['client_pf_device_name'] = pf_device_name_client
                    if caller_class.client_test_object == TestObjectType.VF.value:
                        test_device_info_dict['client_bus_info'] = client_vf0_bus_info
                    # linux下windows虚拟机
                    if "windows" in guest_os_client:
                        status, client_info_dict = \
                            CommonOperation.check_kvm_stats(cls.vm_name, execute_address=condition_client_renew[1],
                                                            check_running=False,
                                                            device_name_server="",
                                                            device_name_client=condition_client_renew[0])
                        if not status:
                            log.error("check_vm_stats failed, skip...")
                            return {}, []
                        test_device_info_dict['client_win_vm_ip'] = client_info_dict["vm_ip"]
                        test_device_info_dict['client_device_ip'] = client_info_dict["vf_ip"]
                        test_device_info_dict['client_device_ipv6'] = client_info_dict["vf_ipv6"]
                        test_device_info_dict['client_device_mac'] = client_info_dict["vf_mac_addr"]
                        test_device_info_dict['client_device_name'] = client_info_dict["vf_name"]
                        test_device_info_dict['client_vf_device_name'] = client_info_dict["vf_name"]
                        test_device_info_dict['client_pf_device_name'] = pf_device_name_client
                # windows pf
                elif "vEthernet" not in condition_client_renew[0] and ('windows' in host_os_client):
                    client_info_dict = IfConfig.analysis_ifconfig_info(*condition_client_renew)
                    test_device_info_dict['client_win_vm_ip'] = ""
                    test_device_info_dict['client_device_ip'] = client_info_dict.get(constants.INET)
                    test_device_info_dict['client_device_ipv6'] = client_info_dict.get(constants.INET6)
                    test_device_info_dict['client_device_mac'] = client_info_dict.get(constants.ETHER)
                    test_device_info_dict['client_device_name'] = condition_client_renew[0]
                    test_device_info_dict['client_pf_device_name'] = pf_device_name_client
                # windows vf
                elif "sriov" in condition_client_renew[0].lower():
                    status, client_info_dict = \
                        CommonOperation.check_vm_stats(cls.vm_name, condition_client_renew[1], check_running=False)
                    if not status:
                        log.error("check_vm_stats failed, skip...")
                        return {}, []
                    test_device_info_dict['client_win_vm_ip'] = client_info_dict["vm_ip"]
                    test_device_info_dict['client_device_ip'] = client_info_dict["vf_ip"]
                    test_device_info_dict['client_device_ipv6'] = client_info_dict["vf_ipv6"]
                    test_device_info_dict['client_device_mac'] = client_info_dict["vf_mac_addr"]
                    test_device_info_dict['client_device_name'] = client_info_dict["hyperv_adapter_name"]
                    test_device_info_dict['client_vf_device_name'] = client_info_dict["vf_name"]
                    test_device_info_dict['client_pf_device_name'] = pf_device_name_client
                # windows vf degvmq
                elif "degvmq" in condition_client_renew[0].lower():
                    status, client_info_dict = \
                        CommonOperation.check_vm_stats(cls.vm_name, condition_client_renew[1], check_running=False,
                                                       virtual_mode=VirtualModeEnum.DEGVMQ.value)
                    if not status:
                        log.error("check_vm_stats failed, skip...")
                        return {}, []
                    test_device_info_dict['client_win_vm_ip'] = client_info_dict["vm_ip"]
                    test_device_info_dict['client_device_ip'] = client_info_dict["vf_ip"]
                    test_device_info_dict['client_device_ipv6'] = client_info_dict["vf_ipv6"]
                    test_device_info_dict['client_device_mac'] = client_info_dict["vf_mac_addr"]
                    test_device_info_dict['client_device_name'] = client_info_dict["hyperv_adapter_name"]
                    test_device_info_dict['client_vf_device_name'] = client_info_dict["vf_name"]
                    test_device_info_dict['client_pf_device_name'] = pf_device_name_client
                # windows vf vmq
                else:
                    status, client_info_dict = \
                        CommonOperation.check_vm_stats(cls.vm_name, condition_client_renew[1], check_running=False,
                                                       virtual_mode=VirtualModeEnum.VMQ.value)
                    if not status:
                        log.error("check_vm_stats failed, skip...")
                        return {}, []
                    test_device_info_dict['client_win_vm_ip'] = client_info_dict["vm_ip"]
                    test_device_info_dict['client_device_ip'] = client_info_dict["vf_ip"]
                    test_device_info_dict['client_device_ipv6'] = client_info_dict["vf_ipv6"]
                    test_device_info_dict['client_device_mac'] = client_info_dict["vf_mac_addr"]
                    test_device_info_dict['client_device_name'] = client_info_dict["hyperv_adapter_name"]
                    test_device_info_dict['client_vf_device_name'] = client_info_dict["vf_name"]
                    test_device_info_dict['client_pf_device_name'] = pf_device_name_client
            else:
                test_device_info_dict['client_win_vm_ip'] = ""

            # 若测试vlan，则对端网卡添加同网段ip
            def add_one(matched):
                value_1 = int(matched.group('pos1'))
                value_2 = int(matched.group('pos2'))
                value_3 = int(matched.group('pos3'))
                value_4 = int(matched.group('pos4')) + 10
                return ".".join([str(value_1), str(value_2), str(value_3), str(value_4)])

            def ip_v4_to_v6(matched):
                value_1 = matched.group('pos1')
                value_2 = matched.group('pos2')
                value_3 = matched.group('pos3')
                value_4 = matched.group('pos4')
                return ":".join(["fe80", "", constants.VENDOR_ID, str(value_2), str(value_3), str(value_4)])

            # 1. server-windows vlan, vfvlan, vf。配置对端IP
            if 'windows' in host_os_server and \
                    ("vlan" in caller_class.server_test_object or "vf" in caller_class.server_test_object):
                # server设备ip最低位 + 1 ，作为对端ip
                oppsite_ip = re.sub('(?P<pos1>\d+)\.(?P<pos2>\d+)\.(?P<pos3>\d+)\.(?P<pos4>\d+)',
                                    add_one, test_device_info_dict['server_device_ip'])
                # 对端ip转换为ipv6
                oppsite_ipv6 = re.sub('(?P<pos1>\d+)\.(?P<pos2>\d+)\.(?P<pos3>\d+)\.(?P<pos4>\d+)',
                                      ip_v4_to_v6, oppsite_ip)
                from scripts.script_libs.ip_operation import IpOperation
                # client设备添加ip
                if 'windows' in host_os_client:
                    IpOperation.add_ip_addr(test_device_info_dict['client_device_name'],
                                            oppsite_ip,
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                            win_vm_ip=test_device_info_dict['client_win_vm_ip'])
                    IpOperation.add_ip_addr(test_device_info_dict['client_device_name'],
                                            oppsite_ipv6, address_family="IPv6",
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                            win_vm_ip=test_device_info_dict['client_win_vm_ip'])
                else:
                    IpOperation.add_ip_addr(test_device_info_dict['client_device_name'],
                                            oppsite_ip + constants.STR_LEFT_SLASH + '24',
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    IpOperation.add_ip_addr(test_device_info_dict['client_device_name'],
                                            oppsite_ipv6 + constants.STR_LEFT_SLASH + '64',
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                test_device_info_dict['client_device_ip'] = oppsite_ip
                test_device_info_dict['client_device_ipv6'] = oppsite_ipv6
                CommonOperation.client_added_ip = (test_device_info_dict['client_device_name'], oppsite_ip)
                CommonOperation.client_added_ipv6 = (test_device_info_dict['client_device_name'], oppsite_ipv6)
                # ping一下，规避第一包丢包的问题
                if "vf" in caller_class.server_test_object:
                    win_vm_ip = CommonOperation.get_win_vm_ip(CmdExecuteAdressEnum.SERVER.value, vm_name=cls.vm_name)
                else:
                    win_vm_ip = None
                rtn_code, rtn_stdout, rtn_stderr= CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=f"ping {CommonOperation.client_added_ip[1]} -S {test_device_info_dict['server_device_ip']} -n 2",
                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, win_vm_ip=win_vm_ip)
                log.info("status:{}, result:{}".format(rtn_code, rtn_stdout))
            # 2. client-windows vlan, vfvlan, vf。配置对端IP
            elif 'windows' in host_os_client and \
                    ("vlan" in caller_class.client_test_object or "vf" in caller_class.client_test_object):
                # client设备ip最低位 + 1 ，作为对端ip
                oppsite_ip = re.sub('(?P<pos1>\d+)\.(?P<pos2>\d+)\.(?P<pos3>\d+)\.(?P<pos4>\d+)',
                                    add_one, test_device_info_dict['client_device_ip'])
                # 对端ip转换为ipv6
                oppsite_ipv6 = re.sub('(?P<pos1>\d+)\.(?P<pos2>\d+)\.(?P<pos3>\d+)\.(?P<pos4>\d+)',
                                      ip_v4_to_v6, oppsite_ip)
                from scripts.script_libs.ip_operation import IpOperation
                # server设备添加ip
                if 'windows' in host_os_server:
                    IpOperation.add_ip_addr(test_device_info_dict['server_device_name'],
                                            oppsite_ip,
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                            win_vm_ip=test_device_info_dict['server_win_vm_ip'])
                    IpOperation.add_ip_addr(test_device_info_dict['server_device_name'],
                                            oppsite_ipv6, address_family="IPv6",
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                            win_vm_ip=test_device_info_dict['server_win_vm_ip'])
                else:
                    IpOperation.add_ip_addr(test_device_info_dict['server_device_name'],
                                            oppsite_ip + constants.STR_LEFT_SLASH + '24',
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    IpOperation.add_ip_addr(test_device_info_dict['server_device_name'],
                                            oppsite_ipv6 + constants.STR_LEFT_SLASH + '64',
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                test_device_info_dict['server_device_ip'] = oppsite_ip
                test_device_info_dict['server_device_ipv6'] = oppsite_ipv6
                CommonOperation.server_added_ip = (test_device_info_dict['server_device_name'], oppsite_ip)
                CommonOperation.server_added_ipv6 = (test_device_info_dict['server_device_name'], oppsite_ipv6)
                # ping一下，规避第一包丢包的问题
                if "vf" in caller_class.client_test_object:
                    client_win_vm_ip = CommonOperation.get_win_vm_ip(CmdExecuteAdressEnum.CLIENT.value,
                                                                     vm_name=cls.vm_name)
                else:
                    client_win_vm_ip = None
                rtn_code, rtn_stdout, rtn_stderr= CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=f"ping {CommonOperation.server_added_ip[1]} -S {test_device_info_dict['client_device_ip']} -n 2",
                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, win_vm_ip=client_win_vm_ip)
                # log.info("status:{}, result:{}".format(rtn_code, rtn_stdout))
            # 3. server-linux KVM windows虚拟机 vlan, vfvlan, vf。配置对端IP
            elif ('windows' not in host_os_server and 'windows' in guest_os_server) and \
                    ("vlan" in caller_class.server_test_object or "vf" in caller_class.server_test_object):
                # server设备ip最低位 + 1 ，作为对端ip
                oppsite_ip = re.sub('(?P<pos1>\d+)\.(?P<pos2>\d+)\.(?P<pos3>\d+)\.(?P<pos4>\d+)',
                                    add_one, test_device_info_dict['server_device_ip'])
                # 对端ip转换为ipv6
                oppsite_ipv6 = re.sub('(?P<pos1>\d+)\.(?P<pos2>\d+)\.(?P<pos3>\d+)\.(?P<pos4>\d+)',
                                      ip_v4_to_v6, oppsite_ip)
                from scripts.script_libs.ip_operation import IpOperation
                # client设备添加ip
                if 'windows' in host_os_client:
                    IpOperation.add_ip_addr(test_device_info_dict['client_device_name'],
                                            oppsite_ip,
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                            win_vm_ip=test_device_info_dict['client_win_vm_ip'])
                    IpOperation.add_ip_addr(test_device_info_dict['client_device_name'],
                                            oppsite_ipv6, address_family="IPv6",
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                            win_vm_ip=test_device_info_dict['client_win_vm_ip'])
                else:
                    IpOperation.add_ip_addr(test_device_info_dict['client_device_name'],
                                            oppsite_ip + constants.STR_LEFT_SLASH + '24',
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    IpOperation.add_ip_addr(test_device_info_dict['client_device_name'],
                                            oppsite_ipv6 + constants.STR_LEFT_SLASH + '64',
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                test_device_info_dict['client_device_ip'] = oppsite_ip
                test_device_info_dict['client_device_ipv6'] = oppsite_ipv6
                CommonOperation.client_added_ip = (test_device_info_dict['client_device_name'], oppsite_ip)
                CommonOperation.client_added_ipv6 = (test_device_info_dict['client_device_name'], oppsite_ipv6)
                # ping一下，规避第一包丢包的问题
                if "vf" in caller_class.server_test_object:
                    server_win_vm_ip = CommonOperation.get_win_vm_ip(CmdExecuteAdressEnum.SERVER.value,
                                                                     vm_name=cls.vm_name)
                else:
                    server_win_vm_ip = None
                rtn_code, rtn_stdout, rtn_stderr= CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=f"ping {CommonOperation.client_added_ip[1]} -S {test_device_info_dict['server_device_ip']} -n 2",
                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, win_vm_ip=server_win_vm_ip)
                # log.info("status:{}, result:{}".format(rtn_code, rtn_stdout))
            # 4. client-linux KVM windows虚拟机 vlan, vfvlan, vf。配置对端IP
            elif ('windows' not in host_os_client and 'windows' in guest_os_client) and \
                    ("vlan" in caller_class.client_test_object or "vf" in caller_class.client_test_object):
                # client设备ip最低位 + 1 ，作为对端ip
                oppsite_ip = re.sub('(?P<pos1>\d+)\.(?P<pos2>\d+)\.(?P<pos3>\d+)\.(?P<pos4>\d+)',
                                    add_one, test_device_info_dict['client_device_ip'])
                # 对端ip转换为ipv6
                oppsite_ipv6 = re.sub('(?P<pos1>\d+)\.(?P<pos2>\d+)\.(?P<pos3>\d+)\.(?P<pos4>\d+)',
                                      ip_v4_to_v6, oppsite_ip)
                from scripts.script_libs.ip_operation import IpOperation
                # server设备添加ip
                if 'windows' in host_os_server:
                    IpOperation.add_ip_addr(test_device_info_dict['server_device_name'],
                                            oppsite_ip,
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                            win_vm_ip=test_device_info_dict['server_win_vm_ip'])
                    IpOperation.add_ip_addr(test_device_info_dict['server_device_name'],
                                            oppsite_ipv6, address_family="IPv6",
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                            win_vm_ip=test_device_info_dict['server_win_vm_ip'])
                else:
                    IpOperation.add_ip_addr(test_device_info_dict['server_device_name'],
                                            oppsite_ip + constants.STR_LEFT_SLASH + '24',
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    IpOperation.add_ip_addr(test_device_info_dict['server_device_name'],
                                            oppsite_ipv6 + constants.STR_LEFT_SLASH + '64',
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                test_device_info_dict['server_device_ip'] = oppsite_ip
                test_device_info_dict['server_device_ipv6'] = oppsite_ipv6
                CommonOperation.server_added_ip = (test_device_info_dict['server_device_name'], oppsite_ip)
                CommonOperation.server_added_ipv6 = (test_device_info_dict['server_device_name'], oppsite_ipv6)
                # ping一下，规避第一包丢包的问题
                if "vf" in caller_class.client_test_object:
                    client_win_vm_ip = CommonOperation.get_win_vm_ip(CmdExecuteAdressEnum.CLIENT.value,
                                                                     vm_name=cls.vm_name)
                else:
                    client_win_vm_ip = None
                rtn_code, rtn_stdout, rtn_stderr= CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=f"ping {CommonOperation.server_added_ip[1]} -S {test_device_info_dict['client_device_ip']} -n 2",
                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, win_vm_ip=client_win_vm_ip)
                # log.info("status:{}, result:{}".format(rtn_code, rtn_stdout))
            # 5. server-linux vlan, vfvlan, vf。配置对端IP
            elif 'windows' not in host_os_server and \
                    ("vlan" in caller_class.server_test_object or "vf" in caller_class.server_test_object):
                # server设备ip最低位 + 1 ，作为对端ip
                oppsite_ip = re.sub('(?P<pos1>\d+)\.(?P<pos2>\d+)\.(?P<pos3>\d+)\.(?P<pos4>\d+)',
                                    add_one, test_device_info_dict['server_device_ip'])
                # 对端ip转换为ipv6
                oppsite_ipv6 = re.sub('(?P<pos1>\d+)\.(?P<pos2>\d+)\.(?P<pos3>\d+)\.(?P<pos4>\d+)',
                                      ip_v4_to_v6, oppsite_ip)
                from scripts.script_libs.ip_operation import IpOperation
                # client设备添加ip
                if 'windows' in host_os_client:
                    IpOperation.add_ip_addr(test_device_info_dict['client_device_name'],
                                            oppsite_ip,
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                            win_vm_ip=test_device_info_dict['client_win_vm_ip'])
                    IpOperation.add_ip_addr(test_device_info_dict['client_device_name'],
                                            oppsite_ipv6, address_family="IPv6",
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                            win_vm_ip=test_device_info_dict['client_win_vm_ip'])
                else:
                    # 将当前ip清除
                    IpOperation.flush_ip_addr(test_device_info_dict['client_device_name'],
                                              cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    IpOperation.flush_ipv6_addr(test_device_info_dict['client_device_name'],
                                                cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    # 将持久化ip恢复
                    IfConfig.set_device_soft_up(device_name=test_device_info_dict['client_device_name'],
                                                cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    IpOperation.add_ip_addr(test_device_info_dict['client_device_name'],
                                            oppsite_ip + constants.STR_LEFT_SLASH + '24',
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    IpOperation.add_ip_addr(test_device_info_dict['client_device_name'],
                                            oppsite_ipv6 + constants.STR_LEFT_SLASH + '64',
                                            address_family="IPv6",
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                test_device_info_dict['client_device_ip'] = oppsite_ip
                test_device_info_dict['client_device_ipv6'] = oppsite_ipv6
                CommonOperation.client_added_ip = (test_device_info_dict['client_device_name'], oppsite_ip)
                CommonOperation.client_added_ipv6 = (test_device_info_dict['client_device_name'], oppsite_ipv6)
                # # ping一下，规避第一包丢包的问题
                # rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                #     cmd=f"ping {CommonOperation.client_added_ip[1]} -S {test_device_info_dict['server_device_ip']} -n 2",
                #     cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                # log.info("status:{}, result:{}".format(rtn_code, rtn_stdout))
            # 4. client-linux vlan, vfvlan, vf。配置对端IP
            elif 'windows' not in host_os_client and \
                    ("vlan" in caller_class.client_test_object or "vf" in caller_class.client_test_object):
                # client设备ip最低位 + 1 ，作为对端ip
                oppsite_ip = re.sub('(?P<pos1>\d+)\.(?P<pos2>\d+)\.(?P<pos3>\d+)\.(?P<pos4>\d+)',
                                    add_one, test_device_info_dict['client_device_ip'])
                # 对端ip转换为ipv6
                oppsite_ipv6 = re.sub('(?P<pos1>\d+)\.(?P<pos2>\d+)\.(?P<pos3>\d+)\.(?P<pos4>\d+)',
                                      ip_v4_to_v6, oppsite_ip)
                from scripts.script_libs.ip_operation import IpOperation
                # server设备添加ip
                if 'windows' in host_os_server:
                    IpOperation.add_ip_addr(test_device_info_dict['server_device_name'],
                                            oppsite_ip,
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                            win_vm_ip=test_device_info_dict['server_win_vm_ip'])
                    IpOperation.add_ip_addr(test_device_info_dict['server_device_name'],
                                            oppsite_ipv6, address_family="IPv6",
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                            win_vm_ip=test_device_info_dict['server_win_vm_ip'])
                else:
                    # 将当前ip清除
                    IpOperation.flush_ip_addr(test_device_info_dict['server_device_name'],
                                              cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    IpOperation.flush_ipv6_addr(test_device_info_dict['server_device_name'],
                                                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    # 将持久化ip恢复
                    IfConfig.set_device_soft_up(device_name=test_device_info_dict['server_device_name'],
                                                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    IpOperation.add_ip_addr(test_device_info_dict['server_device_name'],
                                            oppsite_ip + constants.STR_LEFT_SLASH + '24',
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    IpOperation.add_ip_addr(test_device_info_dict['server_device_name'],
                                            oppsite_ipv6 + constants.STR_LEFT_SLASH + '64',
                                            address_family="IPv6",
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                test_device_info_dict['server_device_ip'] = oppsite_ip
                test_device_info_dict['server_device_ipv6'] = oppsite_ipv6
                CommonOperation.server_added_ip = (test_device_info_dict['server_device_name'], oppsite_ip)
                CommonOperation.server_added_ipv6 = (test_device_info_dict['server_device_name'], oppsite_ipv6)
                # # ping一下，规避第一包丢包的问题
                # rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                #     cmd=f"ping {CommonOperation.server_added_ip[1]} -S {test_device_info_dict['client_device_ip']} -n 2",
                #     cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                # log.info("status:{}, result:{}".format(rtn_code, rtn_stdout))

            # 添加可選項，虚机的操作系统
            test_device_info_dict['virtual_system'] = CommandLineArgsParse.get_host_os()
        org_test_device_info_dict = cls.get_test_device_info_list(test_device_info_list, dict_to_list=False)
        return org_test_device_info_dict, test_device_info_list

    @classmethod
    def get_test_device_info_list(cls, test_device_info: [dict, list], dict_to_list: bool = True) -> tuple:
        # 将test_device_info按port重新整理成list
        if dict_to_list:
            test_device_info_list = []
            for port_index in range(8):
                if port_index == 0:
                    key_mark = ""
                else:
                    key_mark = str(port_index)

                info_dict = {}
                if 'server{}_win_vm_ip'.format(key_mark) in test_device_info.keys():
                    info_dict["server_win_vm_ip"] = test_device_info['server{}_win_vm_ip'.format(key_mark)]
                if 'server{}_device_ip'.format(key_mark) in test_device_info.keys():
                    info_dict["server_device_ip"] = test_device_info['server{}_device_ip'.format(key_mark)]
                if 'server{}_device_ipv6'.format(key_mark) in test_device_info.keys():
                    info_dict["server_device_ipv6"] = test_device_info['server{}_device_ipv6'.format(key_mark)]
                if 'server{}_device_mac'.format(key_mark) in test_device_info.keys():
                    info_dict["server_device_mac"] = test_device_info['server{}_device_mac'.format(key_mark)]
                if 'server{}_device_name'.format(key_mark) in test_device_info.keys():
                    info_dict["server_device_name"] = test_device_info['server{}_device_name'.format(key_mark)]
                if 'server{}_vf_device_name'.format(key_mark) in test_device_info.keys():
                    info_dict["server_vf_device_name"] = test_device_info['server{}_vf_device_name'.format(key_mark)]
                if 'server{}_pf_device_name'.format(key_mark) in test_device_info.keys():
                    info_dict["server_pf_device_name"] = test_device_info['server{}_pf_device_name'.format(key_mark)]
                if 'server{}_bus_info'.format(key_mark) in test_device_info.keys():
                    info_dict["server_bus_info"] = test_device_info['server{}_bus_info'.format(key_mark)]

                if 'client{}_win_vm_ip'.format(key_mark) in test_device_info.keys():
                    info_dict["client_win_vm_ip"] = test_device_info['client{}_win_vm_ip'.format(key_mark)]
                if 'client{}_device_ip'.format(key_mark) in test_device_info.keys():
                    info_dict["client_device_ip"] = test_device_info['client{}_device_ip'.format(key_mark)]
                if 'client{}_device_ipv6'.format(key_mark) in test_device_info.keys():
                    info_dict["client_device_ipv6"] = test_device_info['client{}_device_ipv6'.format(key_mark)]
                if 'client{}_device_mac'.format(key_mark) in test_device_info.keys():
                    info_dict["client_device_mac"] = test_device_info['client{}_device_mac'.format(key_mark)]
                if 'client{}_device_name'.format(key_mark) in test_device_info.keys():
                    info_dict["client_device_name"] = test_device_info['client{}_device_name'.format(key_mark)]
                if 'client{}_vf_device_name'.format(key_mark) in test_device_info.keys():
                    info_dict["client_vf_device_name"] = test_device_info['client{}_vf_device_name'.format(key_mark)]
                if 'client{}_pf_device_name'.format(key_mark) in test_device_info.keys():
                    info_dict["client_pf_device_name"] = test_device_info['client{}_pf_device_name'.format(key_mark)]
                if 'client{}_bus_info'.format(key_mark) in test_device_info.keys():
                    info_dict["client_bus_info"] = test_device_info['client{}_bus_info'.format(key_mark)]
                if info_dict:
                    test_device_info_list.append(info_dict)
            return test_device_info_list
        # 将test_device_info按port重新整理成dict
        else:
            # list转为dict
            info_dict = {}
            # 遍历list中的每一个dict
            for port, temp_dict in enumerate(test_device_info):
                # dict中的key添加port信息
                for k, v in temp_dict.items():
                    if port == 0:
                        info_dict[k] = v
                    else:
                        if "server_" in k:
                            k_2 = k.replace("server_", f"server{port}_")
                        elif "client_" in k:
                            k_2 = k.replace("client_", f"client{port}_")
                        else:
                            k_2 = k.replace("server_", f"server{port}_")
                        info_dict[k_2] = v
            return info_dict

    @classmethod
    def result_collect(cls, case_cls, expect_rtn, rtn_code, description, expect_info, result,
                       create_bug: bool = True, keyword: str = None):
        if "检查寄存器" in description:
            create_bug = False
        if not keyword:
            try:
                keyword = case_cls.test_module
            except:
                keyword = description
        if isinstance(expect_rtn, bool):
            if expect_rtn is True:
                expect_rtn = RtnStatusEnum.SUCCESS.value
            else:
                expect_rtn = RtnStatusEnum.FAIL.value
        if isinstance(rtn_code, bool):
            if rtn_code is True:
                rtn_code = RtnStatusEnum.SUCCESS.value
            else:
                rtn_code = RtnStatusEnum.FAIL.value
        if rtn_code == expect_rtn:
            log.info_caller(f"{description}: {expect_info}")
        else:
            # log.error_caller("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$")
            log.error_caller(f"结果是为：{description} {result}， 预期为：{expect_info}")
            if create_bug:
                cls.create_bug_problem(
                    case_cls=case_cls, key_word=f"{keyword}",
                    description_word=f" {description}{result}",
                    expect_info=f" {description}{expect_info}",
                    result_info=f"{description}{result}")

    @classmethod
    def create_bug_problem(cls, case_cls, key_word: str, description_word: str,
                           result_info: str = '', expect_info: str = '', ignore: bool = False, block: bool = True,
                           level=-1):
        """
        author: weiyuan
        date: 2022年7月26日20:49:11
        description: 描述bug信息
        :param case_cls:
        :param key_word: 功能模块
        :param description_word: 异常描述信息
        :param result_info: 实际结果
        :param expect_info: 预期结果
        :param ignore: 是否忽略报bug
        :param block: 是否阻塞式报bug，如果设置成false，将不会立即报bug，将在下次报阻塞式bug时或执行完do后再一起抛bug
        """

        case_cls.bug_title = f'BUG->[{key_word}]->描述信息:{description_word}'
        case_cls.bug_result = f'{result_info}'
        case_cls.bug_expect = f'{expect_info}'
        case_cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        desc = f"{case_cls.bug_title}。预期:{expect_info}。结果:{result_info}"
        log.error_caller(desc, level=level)
        if ignore:
            log.warning("=>此BUG当前设定为忽略，不抛BUG去停止测试")
        elif not block:
            case_cls.non_blocking_bug_dict[1 + len(case_cls.non_blocking_bug_dict)] = desc
            log.warning("=>此BUG当前设定为非阻塞，不立即抛BUG去停止测试，先记录，后续再报BUG")
        else:
            desc = ""
            for k, v in case_cls.non_blocking_bug_dict.items():
                desc += "BUG-{}=>{};".format(k, v)
            if desc:
                case_cls.bug_title = desc + " => BLOCK-" + case_cls.bug_title
            case_cls.create_bug(case_cls.bug_title)

    @classmethod
    def concat_test_steps(cls, step_info, level: int = -1, pre_add_line: bool = False) -> None:
        """
        author: xianda.liu
        date: 2022.08.02
        description: 拼接script_base中的测试步骤
        :param step_info: 执行的命令描述
        :param pre_add_line: 是否需要在前面添加换行符
        :return:
        """
        from scripts.script_libs.script_base import ScriptBase

        execute_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        test_step = f'{execute_time}, 步骤描述: {step_info}'
        log.info_caller(f'{test_step}', level=level, pre_add_line=pre_add_line)
        ScriptBase.test_steps += test_step + ';'
        return

    @classmethod
    def file_location(cls, spcify_file_name: str):
        """
        author: wei.yuan
        date: 2022.09.01
        description: 指定文件定位
        :param spcify_file_name: 指定文件名称
        """
        specify_file_location = os.path.abspath(spcify_file_name)
        print("~~~~~~~~~~~")
        print(specify_file_location)

    @classmethod
    def common_check_environment(cls, caller_class, ip_version_check_flag: bool = False,
                                 ip_version: str = constants.IPV4, update_rpc_server_file: bool = True,
                                 rdma: bool = False) -> bool:
        """
        author:                 xianda.liu
        date:                   2022.8.31
        description:            功能测试常用环境检查,检查是否有符合
        :param caller_class:    传二级基类即可
        :param ip_version_check_flag: 是否检查网卡子接口的IP version, 默认False不检查
        :param ip_version: 网卡子接口ip version, 默认IPv4，当ip_verison_check_flag为False，不做检查
        :return: True/False
        """
        check_result = True
        nicg = CommonOperation.get_nic_generation()
        # windows清理环境
        from scripts.script_libs.windows_hyperv_manage_vm import VmOp
        host_os_server, host_os_client = cls.get_nic_os()
        guest_os_server, guest_os_client = cls.get_guest_os(caller_class.test_direction_reverse)
        if host_os_server == "windows":
            log.info("server 尝试清理windows环境")
            vm_list = VmOp.get_vm(cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            log.info(f"server vm_list: {vm_list}")
            for vm_name in vm_list:
                cls.clean_hyper_v(CmdExecuteAdressEnum.SERVER.value, vm_name=vm_name)
        if host_os_client == "windows":
            log.info("client 尝试清理windows环境")
            vm_list = VmOp.get_vm(cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
            log.info(f"client vm_list: {vm_list}")
            for vm_name in vm_list:
                cls.clean_hyper_v(CmdExecuteAdressEnum.CLIENT.value, vm_name=vm_name)
        # 如果是dpdk mode，FPGA阶段还不能去加载主机驱动，防止多pf跨驱动
        if CommandLineArgsParse.get_test_entry() in [TestEntryEnum.DPDK_MODE.value,
                                                     TestEntryEnum.DPDK_AUTO_MODE.value]:
            recover = False
        else:
            recover = True
        # 如果server、client两侧的驱动有一侧未加载，则检查环境失败
        if not cls.check_driver_probe(rdma, recover):
            if rdma:
                # rdma脚本：
                # 由于部分环境reboot后不会自动加载模块ib_core、ib_uvers，此处尝试加载该模块与rdma驱动
                # 若加载成功，则环境检查通过
                # 若加载失败，则环境检查失败
                log.info(f'rdma脚本：由于部分环境reboot后不会自动加载模块ib_core、ib_uvers，此处尝试加载该模块与rdma驱动，若加载成功，则环境检查通过')
                server_dev_name, client_dev_name = cls.get_nic_relationships(rdma=rdma)
                server_driver_name, client_driver_name = cls.get_nic_driver_name(rdma=rdma)

                if not caller_class.test_direction_reverse:
                    current_addr = CmdExecuteAdressEnum.SERVER.value
                    current_dev = server_dev_name
                    opposite_addr = CmdExecuteAdressEnum.CLIENT.value
                    opposite_dev = client_dev_name
                else:
                    current_addr = CmdExecuteAdressEnum.CLIENT.value
                    current_dev = client_dev_name
                    opposite_addr = CmdExecuteAdressEnum.SERVER.value
                    opposite_dev = server_dev_name

                if CommandLineArgsParse.get_test_object() in [RunModeEnum.RUN_MODE_WITH_SRC.value,
                                                              RunModeEnum.RUN_MODE_WITH_RPM.value,
                                                              RunModeEnum.RUN_MODE_WITH_SRPM.value,
                                                              RunModeEnum.RUN_MODE_WITH_KMOD_SRPM.value]:
                    use_ko = False
                else:
                    use_ko = True

                cmd_list = [
                    f'modprobe ib_core',
                    f'modprobe ib_uverbs',
                ]
                if use_ko:
                    modprobe_cmd = f'timeout 60 insmod /root/{constants.DRV_SCGBE_RDMA}.ko resource_profile=1 fragment_count_limit=13'
                    cmd_list.append(modprobe_cmd)
                else:
                    modprobe_para = f'echo "options {constants.DRV_SCGBE_RDMA} resource_profile=1 fragment_count_limit=13" > /etc/modprobe.d/{constants.DRV_SCGBE_RDMA}.conf'
                    cmd_list.append(modprobe_para)
                    modprobe_cmd = f'timeout 60 modprobe {constants.DRV_SCGBE_RDMA}'
                    cmd_list.append(modprobe_cmd)

                # 加载必要的驱动，驱动参数使用典型值，满足大部分测试需要
                log.info(f'加载必要的驱动')
                for cmd in cmd_list:
                    status, result, err = CommandOperation.execute_command_with_error(cmd, current_addr)
                    if status != RtnStatusEnum.SUCCESS.value:
                        return False
                status, result, err = CommandOperation.execute_command_with_error(f'lsmod|grep -w {constants.DRV_SCGBE_RDMA}', current_addr)
                if not result:
                    log.error(f'{constants.DRV_SCGBE_RDMA}驱动加载失败')
                    return False
                # 配置arp
                if opposite_dev and current_dev and CommonOperation.get_chip_identification() != 'a':
                    status = cls.set_arp(opposite_dev, current_dev, 'IPv4', current_addr)
                    if status != RtnStatusEnum.SUCCESS.value:
                        log.error(f'{current_addr}： {current_dev}配置arp失败')
                        return False
                    status = cls.check_arp(opposite_dev, current_dev, 'IPv4', current_addr)
                    if status != RtnStatusEnum.SUCCESS.value:
                        log.error(f'{current_addr}： {current_dev}配置arp后检查失败')
                        return False
                    status = cls.set_arp(current_dev, opposite_dev, 'IPv4', opposite_addr)
                    if status != RtnStatusEnum.SUCCESS.value:
                        log.error(f'{opposite_addr}： {opposite_dev}配置arp失败')
                        return False
                    status = cls.check_arp(current_dev, opposite_dev, 'IPv4', opposite_addr)
                    if status != RtnStatusEnum.SUCCESS.value:
                        log.error(f'{opposite_addr}： {opposite_dev}配置arp后检查失败')
                        return False
                log.info(f'rdma脚本：尝试加载模块与rdma驱动成功')
            else:
                log.error("如果server、client两侧的驱动有一侧未加载，则检查环境失败")
                check_result = False
                return check_result

        # 两侧网卡均不是intel82599或sxe，则环境检查失败
        server_driver_name, client_driver_name = cls.get_nic_driver_name(rdma=rdma)
        if (server_driver_name not in [NicNameEnum.INTEL_82599.value, NicNameEnum.SXE.value,
                                       NicNameEnum.E810.value, NicNameEnum.CX6.value, NicNameEnum.MLX5_IB.value,
                                       NicNameEnum.SXE2.value, NicNameEnum.SCGBE.value, NicNameEnum.SXE2_RDMA.value, NicNameEnum.SCGBE_RDMA.value,
                                       NicNameEnum.SCE.value, NicNameEnum.SCE_RDMA.value,
                                       NicNameEnum.IRDMA.value, NicNameEnum.Testca.value,] and
                client_driver_name not in [NicNameEnum.INTEL_82599.value, NicNameEnum.SXE.value,
                                           NicNameEnum.E810.value, NicNameEnum.CX6.value, NicNameEnum.MLX5_IB.value,
                                           NicNameEnum.SXE2.value, NicNameEnum.SCGBE.value, NicNameEnum.SXE2_RDMA.value, NicNameEnum.SCGBE_RDMA.value,
                                           NicNameEnum.SCE.value, NicNameEnum.SCE_RDMA.value,
                                           NicNameEnum.RENIX.value,
                                           NicNameEnum.IRDMA.value, NicNameEnum.Testca.value]):
            log.info(f"如果收发两侧网卡均不是intel82599或sxe、sce、E810、CX6、{nicg}，则环境检查失败")
            check_result = False
            return check_result

        # 如果设备数大于1，认为是规格测试或队列分配测试，不支持基于功能测试的common_check_environment检查
        if caller_class.client_test_object_num > 1 or caller_class.server_test_object_num > 1:
            log.info("如果设备数大于1，认为是规格测试或队列分配测试，不支持基于功能测试的common_check_environment检查")
            check_result = False
            return check_result

        test_device_info_dict, test_device_info_list = CommonOperation.get_test_device_info(caller_class)
        log.info('test_device_info_dict： {}'.format(test_device_info_dict))
        log.info('test_device_info_list： {}'.format(test_device_info_list))
        if not test_device_info_dict:
            log.error("如果test_device_info_dict为空，则环境检查失败")
            check_result = False
            return check_result
        if not test_device_info_list:
            log.error("如果test_device_info_list为空，则环境检查失败")
            check_result = False
            return check_result

        caller_class.client_device_name = test_device_info_dict['client_device_name']
        caller_class.server_device_name = test_device_info_dict['server_device_name']
        caller_class.client_device_mac = test_device_info_dict['client_device_mac']
        caller_class.server_device_mac = test_device_info_dict['server_device_mac']

        # 获取client和server端的所有被测网卡的子接口名称，如:ens1f0, ens1f1
        if not caller_class.client_device_name or not caller_class.server_device_name:
            log.info("获取client和server端的首个被测网卡的子接口名称任意一个失败，则环境检查失败")
            check_result = False
            return check_result

        # 检查获取到的子接口是否已配置所需要的ip, 如: ipv4地址或ipv6地址, 如果脚本不指定就不进行此项检查
        if ip_version_check_flag and ip_version == constants.IPV4:
            caller_class.client_device_ip = test_device_info_dict['client_device_ip']
            caller_class.server_device_ip = test_device_info_dict['server_device_ip']
            if not caller_class.client_device_ip or not caller_class.server_device_ip:
                log.info("获取client和server端的首个被测网卡的子接口ipv4任意一个失败，则环境检查失败")
                check_result = False
                return check_result

        elif ip_version_check_flag and ip_version == constants.IPV6:
            caller_class.client_device_ip = test_device_info_dict['client_device_ipv6']
            caller_class.server_device_ip = test_device_info_dict['server_device_ipv6']
            if not caller_class.client_device_ip or not caller_class.server_device_ip:
                log.info("获取client和server端的首个被测网卡的子接口ipv6任意一个失败，则环境检查失败")
                check_result = False
                return check_result

        else:
            caller_class.client_device_ip = test_device_info_dict['client_device_ip']
            caller_class.server_device_ip = test_device_info_dict['server_device_ip']

        # 检查是否有mac地址应该是必要的操作
        if (
                not caller_class.client_device_mac and cls.is_renix_only() == False) or not caller_class.server_device_mac:
            log.warning('client或server端的mac地址为空')
            # check_result = False
            # return check_result

        caller_class.test_device_info_dict = test_device_info_dict
        caller_class.test_device_info_list = test_device_info_list
        # log.info('test_device_info_list： {}'.format(caller_class.test_device_info_list))

        # 补充更新vm rpc_server.py
        if update_rpc_server_file:
            host_os_server, host_os_client = cls.get_nic_os()
            # server是windows 或 server是linux且虚拟机是windows
            if 'windows' in host_os_server or ('windows' not in host_os_server and "windows" in guest_os_server):
                if "vf" in caller_class.server_test_object.lower():
                    # 获取vm ip
                    vm_ip = caller_class.test_device_info_dict["server_win_vm_ip"]
                    # 更新vm rpc_server.py
                    cls.update_vm_rpc_server_file(caller_class, vm_ip, CmdExecuteAdressEnum.SERVER.value)
                else:
                    pass
            if 'windows' in host_os_client or ('windows' not in host_os_client and "windows" in guest_os_client):
                if "vf" in caller_class.client_test_object.lower():
                    # 获取vm ip
                    vm_ip = caller_class.test_device_info_dict["client_win_vm_ip"]
                    # 更新vm rpc_server.py
                    cls.update_vm_rpc_server_file(caller_class, vm_ip, CmdExecuteAdressEnum.CLIENT.value)
                else:
                    pass

        return check_result

    @classmethod
    def clean_hyper_v(cls, execute_address: str, vm_name: str = "sxevm001") -> None:
        """
        author:                 xiangyu.liu
        date:                   2022.8.31
        description:            删除环境上残留的虚拟交换机
        :return:
        """
        from scripts.script_libs.windows_hyperv_manage_vm import VmSwitch, VmAdapter, VmOp
        host_os_server, host_os_client = cls.get_nic_os()

        # windows环境继续执行
        if (execute_address == CmdExecuteAdressEnum.SERVER.value and
            host_os_server == HostOsEnum.WINDOWS.value) or \
                (execute_address == CmdExecuteAdressEnum.CLIENT.value and
                 host_os_client == HostOsEnum.WINDOWS.value):
            # 若vm网络适配器连接sriov交换机
            if VmAdapter.get_vmnetworkadapter_connection(vm_name=vm_name, cmd_execute_address=execute_address):
                # 断联sriov交换机
                VmAdapter.disconnect_vmnetworkadapter(vm_name=vm_name,
                                                      manager_vmswitch_name=V_SWITCH_MANAGER_NAME_DEF,
                                                      vmswitch_name=V_SWITCH_SRIOV_NAME_DEF,
                                                      execute_address=execute_address)
            # 若存在sriov交换机
            if VmSwitch.find_vmswitch(execute_address=execute_address):
                # 删除sriov交换机
                VmSwitch.remove_vmswitch(vmswitch_name=V_SWITCH_SRIOV_NAME_DEF, execute_address=execute_address)

    @classmethod
    def clean_pcap_file(cls) -> None:
        """
        author:                 xianda.liu
        date:                   2022.8.31
        description:            删除环境上可能存在的测试出的pcap包
        :return:
        """
        pacp_file_path_server, pcap_file_path_client = cls.pcap_file_path()
        host_os_server, host_os_client = cls.get_nic_os()
        if host_os_client != HostOsEnum.WINDOWS.value:
            command_client = 'rm -rf {}'.format(pcap_file_path_client)
        else:
            command_client = 'del /f/s/q {}'.format(pcap_file_path_client)

        if host_os_server != HostOsEnum.WINDOWS.value:
            command_server = 'rm -rf {}'.format(pacp_file_path_server)
        else:
            command_server = 'del /f/s/q {}'.format(pacp_file_path_server)

        _, _, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=command_client, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
        _, _, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=command_server, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        return

    @classmethod
    def send_protocol_data_packet(cls, ip_version: str, src_ip: str, dst_ip: str,
                                  src_port: str = None, dst_port: str = None,
                                  data: str = None,
                                  protocol: str = TransportProtocal.TRANSPORT_TCP.value,
                                  cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value
                                  ):
        """
        author: wei.yuan1
        date: 2022.09.26
        description: 发送协议数据包
        [root@test254 ~]# sendip -p ipv4 -is 192.168.100.254 -id 192.168.100.253 -d r5 -p udp 192.168.100.253
        [root@test254 ~]# sendip -p ipv4 -is 192.168.100.254 -id 192.168.100.253 -d abcdefg -p udp 192.168.100.253
        :param ip_version: IP数据报的类型
        :param src_port:发送端的的端口号
        :param src_ip: 发送端需要发送数据的指定IP地址
        :param dst_ip: 接收端指定的要接收数据的IP地址
        :param dst_port: 接收端指定的要接收数据的IP端口
        :param data: 需要传输的数据
        :param protocol: 需要传输的协议内容
        :param cmd_execute_address:需要指定从哪端进行发送数据
        """
        rtn_status = False
        if protocol == TransportProtocal.TRANSPORT_TCP.value:
            if data is not None:
                exec_command = constants.STR_SPACE.join([
                    constants.SENDIP, constants.MODULE, ip_version, constants.SRC_IP,
                    src_ip, constants.DST_IP, dst_ip, constants.MODULE, protocol,
                    constants.SRC_PORT, src_port, constants.DST_PORT, dst_port,
                    constants.DATA, data, dst_ip])
            else:
                exec_command = constants.STR_SPACE.join([
                    constants.SENDIP, constants.MODULE, ip_version, constants.SRC_IP,
                    src_ip, constants.DST_IP, dst_ip, constants.MODULE, protocol,
                    constants.SRC_PORT, src_port, constants.DST_PORT, dst_port,
                    dst_ip])
        else:
            if data is not None:
                exec_command = constants.STR_SPACE.join([
                    constants.SENDIP, constants.MODULE, ip_version, constants.SRC_IP,
                    src_ip, constants.DST_IP, dst_ip, constants.MODULE, protocol,
                    constants.DATA, data, dst_ip])
            else:
                exec_command = constants.STR_SPACE.join([
                    constants.SENDIP, constants.MODULE, ip_version, constants.SRC_IP,
                    src_ip, constants.DST_IP, dst_ip, constants.MODULE, protocol,
                    dst_ip])

        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        return rtn_status

    @classmethod
    def dictcut(cls, dict_cut, start, end):
        """
        author: wei.yuan1
        date: 2022.09.26
        description: 对字典进行切片划分
        """
        # 临时存放字典的key
        temp = list(dict_cut.keys())
        # 返回一个字典
        result = {}
        # 分两个分支 1.start和end在可切片范围内 2.不在范围内
        if len(temp) - 1 >= start >= -len(temp) and len(temp) - 1 >= end >= -len(temp):
            # start大于end,且下标不重叠
            if start > end and start - 1 != len(temp) + end:
                # start和end同时为大于等于0
                if start >= 0 and end >= 0:
                    # (4,2) 4 0 1
                    for i in range(start, len(temp)):
                        result[temp[i]] = dict_cut.get(temp[i])
                    for i in range(0, end):
                        result[temp[i]] = dict_cut.get(temp[i])
                # start和end同时小等于0
                if start <= 0 and end <= 0:
                    # (-1,-3) 4 0 1
                    for i in range(len(temp) + start, len(temp)):
                        result[temp[i]] = dict_cut.get(temp[i])
                    for i in range(0, len(temp) + end):
                        result[temp[i]] = dict_cut.get(temp[i])
                # start大于0,end小于0
                if start >= 0 and end < 0:
                    # (1,-2) 1 2
                    for i in range(start, len(temp) + end):
                        result[temp[i]] = dict_cut.get(temp[i])

            # end大于start,且下标不重叠
            elif end > start and start + len(temp) != end - 1:
                # start和end同时为大于等于0
                if start >= 0 and end >= 0:
                    # (0,3) 0 1 2
                    for i in range(start, end):
                        result[temp[i]] = dict_cut.get(temp[i])
                # start和end同时大小等于0
                if start <= 0 and end <= 0:
                    # (-4,-1) 1 2 3
                    for i in range(len(temp) + start, len(temp) + end):
                        result[temp[i]] = dict_cut.get(temp[i])
                # end大等于0,start小于0
                if end >= 0 and start < 0:
                    # (-1,3) 4 0 1 2
                    for i in range(len(temp) + start, len(temp)):
                        result[temp[i]] = dict_cut.get(temp[i])
                    for i in range(end):
                        result[temp[i]] = dict_cut.get(temp[i])
            # start等于end,或者下标重叠
            elif end == start or start + len(temp) == end - 1 or end <= 0 and start - 1 == len(temp) + end:
                raise ValueError("切了个寂寞！")

        # start或者end不在范围内
        else:
            raise ValueError("传入参数错误")
        return result

    @classmethod
    def check_md_command_available(cls, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value) -> bool:
        check_result = False
        exec_command = f'md {str(hex(constants.base_address))}'
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            check_result = True
        else:
            'cd /root/memmap/init_os;chmod +x init_os_env.sh;./init_os_env.sh'
            exec_command = f'md {str(hex(constants.base_address))}'
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_with_error(cmd=exec_command,
                                                            cmd_execute_address=cmd_execute_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                check_result = True
        return check_result

    @classmethod
    def get_register_value(cls, caller_class, register_offset_address: [hex, str], register_length: int,
                           cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                           base_address=None, is_driver_probe=True, reverse_flag: bool = True) -> str:
        """
        使用md命令获取寄存器值
        :param caller_class: 调用类
        :param register_offset_address:寄存器偏移地址
        :param register_length: 获取数据长度，单位字节
        :param cmd_execute_address: 命令执行位置
        :param base_address: 基地址，默认获取测试对象的基地址，如需要另一个PF，可自行传入
        :param is_driver_probe: 是否驱动加载时查寄存器，如果不是，则方法内部先加载再卸载
        :return:
        """
        # server_base_address, client_base_address = None, None
        # if caller_class.test_device_info_dict['client_pf_device_name'] in list(cls.nic_base_address.keys()):
        #     if cls.nic_base_address[caller_class.test_device_info_dict['client_pf_device_name']]:
        #         client_base_address = cls.nic_base_address[caller_class.test_device_info_dict['client_pf_device_name']]
        #     else:
        #         client_base_address = None
        # if caller_class.test_device_info_dict['server_pf_device_name'] in list(cls.nic_base_address.keys()):
        #     if cls.nic_base_address[caller_class.test_device_info_dict['server_pf_device_name']]:
        #         server_base_address = cls.nic_base_address[caller_class.test_device_info_dict['server_pf_device_name']]
        #     else:
        #         server_base_address = None
        # if cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and base_address is None:
        #     base_address = server_base_address
        # elif cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and base_address is None:
        #     base_address = client_base_address
        # else:
        #     base_address = base_address

        if type(register_offset_address) == str:
            if register_offset_address.startswith('0x'):
                register_offset_address = int(register_offset_address, 16)
            else:
                register_offset_address = int(register_offset_address)
        server_nic, client_nic = CommonOperation.get_nic_driver_name()

        # 如果拿不到任何测试信息，默认取PF0的寄存器基地址
        if not caller_class.test_device_info_dict:
            if cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                if client_nic == NicNameEnum.SXE.value:
                    base_address = constants.fpga_base_address_PF_0
                else:
                    base_address = constants.intel_base_address_PF_0
            else:
                if server_nic == NicNameEnum.SXE.value:
                    base_address = constants.fpga_base_address_PF_0
                else:
                    base_address = constants.intel_base_address_PF_0
        # 如果可以找到测试对象子接口，用f0/f1判断选取基地址
        else:
            if cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                if not is_driver_probe:
                    cls.modprobe_driver(driver_name=caller_class.client_driver_name,
                                        cmd_execute_address=cmd_execute_address)
                if not base_address:
                    if caller_class.test_device_info_dict.get('client_pf_device_name'):
                        base_address = cls.get_base_address(
                            caller_class.test_device_info_dict['client_pf_device_name'],
                            cmd_execute_address)
                    else:
                        base_address = cls.get_base_address(caller_class.test_device_info_dict['client_device_name'],
                                                            cmd_execute_address)
                else:
                    base_address = base_address

                if not is_driver_probe:
                    cls.rmmod_driver(driver_name=caller_class.client_driver_name,
                                     cmd_execute_address=cmd_execute_address, force=True)
            else:
                if not is_driver_probe:
                    cls.modprobe_driver(driver_name=caller_class.server_driver_name,
                                        cmd_execute_address=cmd_execute_address)
                if not base_address:
                    if caller_class.test_device_info_dict.get('server_pf_device_name'):
                        base_address = cls.get_base_address(
                            caller_class.test_device_info_dict['server_pf_device_name'],
                            cmd_execute_address)
                    else:
                        base_address = cls.get_base_address(caller_class.test_device_info_dict['server_device_name'],
                                                            cmd_execute_address)
                else:
                    base_address = base_address

                if not is_driver_probe:
                    cls.rmmod_driver(driver_name=caller_class.server_driver_name,
                                     cmd_execute_address=cmd_execute_address, force=True)

        if base_address:
            times = register_length // 256 + 1
            rtn_str = ''
            for j in range(times):
                find_address = base_address + register_offset_address + 256 * j
                exec_command = f'md {str(hex(find_address))}'
                rtn_code, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_with_error(cmd=exec_command,
                                                                cmd_execute_address=cmd_execute_address)

                result = ''
                result_final = ''
                if rtn_code == RtnStatusEnum.SUCCESS.value:
                    item_list = rtn_outputs.split('\n')
                    for item in item_list:
                        result += ''.join(item.split(':')[1].replace(' ', ''))

                    if reverse_flag:
                        # 根据寄存器高低位，重新组合寄存器值
                        """
                        按字节实现转换:
                        高 --> 低    转换   低 --> 高
                        ab cd ef gh    ====>  gh ef cd ab
                        根据转换后的结果，返回指定长度的寄存器值， 比如指定1字节，则返回gh而不是ab
                        注意字节内部仍为高 --> 低, 字节间为低 --> 高
                        """
                        for i in range(0, int(len(result) / 8)):
                            result_final += result[8 * i + 6:8 * i + 8] + \
                                            result[8 * i + 4:8 * i + 6] + \
                                            result[8 * i + 2:8 * i + 4] + \
                                            result[8 * i + 0:8 * i + 2]
                    rtn_str += result_final if reverse_flag else result
                else:
                    pass
            log.info("{}".format(rtn_str[0:2 * register_length] if len(rtn_str) >= 2 * register_length else rtn_str))
            return rtn_str[0:2 * register_length] if len(rtn_str) >= 2 * register_length else rtn_str
        else:
            return ''

    @classmethod
    def windows_register_value(cls, caller_class, driver_id: str, offset_addr: str, register_length: int = 1,
                               cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                               reverse_flag: bool = True):
        """
        author: wei.yuan1
        date: 2023.10.20
        description: 获取寄存器中的值
        """
        # 在读取寄存器的值时，先等待3s,确保寄存器值存在
        time.sleep(3)
        times = register_length // 256 + 1
        rtn_str = ''
        # register_length = str(register_length)
        for j in range(times):
            exec_command = f'{constants.SXECLI64} driver {driver_id} read_reg {offset_addr} {register_length}'
            log.info(f"执行命令：{exec_command}")
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_with_error(cmd=exec_command,
                                                            cmd_execute_address=cmd_execute_address)
            result = ''
            temp = []
            result_final = ''
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                item_list = rtn_outputs.split('\r\n')
                item_list = [index for index in item_list if index != ""]
                for item in item_list[3:]:
                    if ":" not in item:
                        temp.append(item.replace(" ", ''))
                    else:
                        temp.append(item.split(":")[1].replace(" ", ''))
                result = "".join(temp)

                if reverse_flag:
                    # 根据寄存器高低位，重新组合寄存器值
                    """
                    按字节实现转换:
                    高 --> 低    转换   低 --> 高
                    ab cd ef gh    ====>  gh ef cd ab
                    根据转换后的结果，返回指定长度的寄存器值， 比如指定1字节，则返回gh而不是ab
                    注意字节内部仍为高 --> 低, 字节间为低 --> 高
                    """
                    for i in range(0, int(len(result) / 8)):
                        result_final += result[8 * i + 6:8 * i + 8] + \
                                        result[8 * i + 4:8 * i + 6] + \
                                        result[8 * i + 2:8 * i + 4] + \
                                        result[8 * i + 0:8 * i + 2]
                rtn_str += result_final if reverse_flag else result
                print("!!!!!!!!!!")
                print(rtn_str)
                print(rtn_str[0:2 * register_length * 4] if len(rtn_str) >= 8 * register_length else rtn_str)
            # if register_length < 4:
            #     register_length = 4
            return rtn_str[0:2 * register_length * 4] if len(rtn_str) >= 8 * register_length else rtn_str
        else:
            return ''

    @staticmethod
    def set_bit(value, bit):
        """
        author：wei.yuan1
        date: 2023.12.25
        description: 将对应的bit置1
        :param value:待修改的bit值
        :param bit: 需要修改的bit位
        :return:
        """
        value = eval(value)
        fixed_value = value | (1 << bit)
        # 转为长度为8的16进制数据
        fixed_value = hex(int(fixed_value, 2))[2:].zfill(8)
        return fixed_value

    @staticmethod
    def clear_bit(value, bit):
        """
        author: wei.yuan1
        date: 2023.12.25
        description: 将对应的bit置0
        :param value:
        :param bit:
        :return:
        """
        value = eval(value)
        fixed_value = value & ~(1 << bit)
        # 转为长度为8的16进制数据
        fixed_value = hex(int(fixed_value, 2))[2:].zfill(8)
        return fixed_value

    @classmethod
    def windows_register_write(cls, dirver_id: str, offset_addr: str, bit_place: int, setting_flag: bool,
                               register_length: int = 1,
                               cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                               reverse_flag: bool = False):
        """
        author: wei. yuan1
        date: 2023.12.25
        description: 写寄存器操作
        :param bit_place:
        :param dirver_id:
        :param offset_addr:
        :param register_length:
        :param cmd_execute_address:
        :param reverse_flag:
        :return:
        """
        register_value = cls.windows_register_value(caller_class=cls, driver_id=dirver_id, offset_addr=offset_addr,
                                                    register_length=register_length,
                                                    cmd_execute_address=cmd_execute_address,
                                                    reverse_flag=reverse_flag
                                                    )
        bin_register_value = bin(int(register_value, 16))[2:]
        bin_register_value = bin_register_value.zfill(32)
        if setting_flag:
            setting_value = cls.set_bit(bin_register_value, bit_place)
        else:
            setting_value = cls.clear_bit(bin_register_value, bit_place)
        exec_command = f'{constants.SXECLI64} driver {dirver_id} write_reg {offset_addr} {setting_value}'
        log.info(f"执行命令：{exec_command}")
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command,
                                                        cmd_execute_address=cmd_execute_address)
        return rtn_code

    @classmethod
    def get_adapter_statics(cls, driver_id: str = "0", cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2023.01.13
        description: 获取网卡的pf_adapter的统计信息
        获取
        :param cmd_execute_address:
        :param driver_id:
        :return:
        """
        exec_command = f'{constants.SXECLI64} driver {driver_id} pf_adapter_stats'
        log.info(f"执行命令：{exec_command}")
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command,
                                                        cmd_execute_address=cmd_execute_address)
        result = ''
        temp = []
        result_final = ''
        pf_adapter_dict = {}
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            item_list = rtn_outputs.split('\r\n')
            item_list = [index for index in item_list if index != ""]
            item_list = item_list[3:]
            for index in item_list:
                value_list = [index for index in re.sub(r"\s+", "", index.split(":")[1]).split(",")]
                value_info = value_list[0] if len(value_list) <= 1 else value_list
                pf_adapter_dict[re.sub(r"\s+", "", index.split(":")[0])] = value_info
        return pf_adapter_dict

    @classmethod
    def get_vf_list(cls, pf_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> list:
        """
        author: shanshan.du
        date: 2024.07.17
        description: 获取 PF下的VF
        :param pf_name: PF设备名称
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: 返回创建vf device name
        """
        # echo 1 > num_sri
        vf_name_list = []
        get_vf_name_cmd = f"ifconfig|grep {pf_name}v |awk -F : '{{print $1}}'"
        rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=get_vf_name_cmd, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            vf_name_list = re.findall(rf'({pf_name}v\S+)'.format(pf_name), rtn_outputs)
        return vf_name_list

    @classmethod
    def watch_virtual_driver(cls, nic_driver: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2022.11.8
        description: 检查添加VF网卡
        """
        exec_command = 'lsmod | grep {}'.format(nic_driver)
        _, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
            exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_outputs:
            return True
        else:
            return False

    @classmethod
    def prepare_test_device_before_run_script(cls, caller_class, device_name_client: str = '',
                                              device_name_server: str = '') -> int:
        """
        非PF测试，可以直接调用此接口，根据基类需要，可以完成
            1.基于PF的vf创建
            2.基于PF/VF的vlan创建
            3.基于PF/VF的macvlan创建，其中macvlan默认bridge模式
        :param caller_class: 调用类
        :param device_name_client: client端PF子接口名称，如ens1f0
        :param device_name_server: server端PF子接口名称，如ens1f0
        :return:
        """
        from scripts.script_libs.ip_operation import IpOperation
        # 物理机OS
        host_os_server, host_os_client = cls.get_nic_os()
        guest_os_server, guest_os_client = cls.get_guest_os(caller_class.test_direction_reverse)
        server_driver_name, client_driver_name = cls.get_nic_driver_name()
        server_vf_driver_name, client_vf_driver_name = cls.get_nic_vf_driver_name()
        # linux物理机
        if device_name_client and 'windows' not in host_os_client and cls.is_renix_only() == False:
            # step 2.1 如果是VF,加载VF驱动、echo 数量、get_vf_device_name获取子接口名称
            if caller_class.client_test_object == TestObjectType.VF.value:
                # linux虚拟机
                if "windows" not in guest_os_client:
                    if client_driver_name in [NicNameEnum.INTEL_82599.value,
                                              NicNameEnum.SXE.value, NicNameEnum.SXE2.value, NicNameEnum.SCGBE.value, NicNameEnum.SCE.value,
                                              NicNameEnum.E810.value, NicNameEnum.CX6.value]:
                        result_generate_0 = CommonOperation.generate_vf_device(
                            pf_device_name=device_name_client,
                            vf_num=0,
                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        if not result_generate_0:
                            log.info('修改vf数量为0命令执行失败')
                        rtn_code = cls.watch_virtual_driver(nic_driver=client_vf_driver_name,
                                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        if not rtn_code:
                            result_modprobe = cls.modprobe_driver(driver_name=client_vf_driver_name)
                        result_generate = cls.generate_vf_device(
                            pf_device_name=device_name_client,
                            vf_num=caller_class.client_test_object_num,
                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        if not result_generate:
                            log.info(f'修改vf数量为{caller_class.client_test_object_num}命令执行失败')
                            caller_class.set_bug_type(BugTypeEnum.FUNCTION.value)
                            caller_class.bug_title = '创建vf失败'
                            caller_class.bug_result = '创建vf失败'
                            caller_class.bug_expect = '创建vf成功'
                            caller_class.create_bug('创建vf失败')
                        vf_device_names = CommonOperation.get_vf_device_names_by_pf(
                            pf_device_name=device_name_client,
                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        # add by wangwt start:
                        for vf_device_name in vf_device_names:
                            info_dict = IfConfig.analysis_ifconfig_info(
                                device_name=vf_device_name,
                                cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value
                            )
                            while 'inet' in info_dict.keys():
                                IpOperation.del_ip_addr(device_name=vf_device_name,
                                                        ip_addr=info_dict['inet'],
                                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                                info_dict = IfConfig.analysis_ifconfig_info(
                                    device_name=vf_device_name,
                                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        # add by wangwt start:
                        for i in range(len(vf_device_names)):
                            ip_header = CommonOperation.generate_ip_header(
                                pf_device_name=device_name_client,
                                target_device_type=TestObjectType.VF.value,
                                cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                offset=i)
                            ipv6_header = CommonOperation.generate_ipv6_header(
                                pf_device_name=device_name_client,
                                target_device_type=TestObjectType.VF.value,
                                cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                offset=i)
                            log.info("添加vf ipv4")
                            IpOperation.add_ip_addr(device_name=vf_device_names[i],
                                                    ip_addr=(ip_header + str(i + 1) +
                                                             constants.STR_LEFT_SLASH + '24'),
                                                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                            log.info("添加vf ipv6")
                            IpOperation.add_ipv6_addr(device_name=vf_device_names[i],
                                                      ipv6_addr=(ipv6_header + "{:04x}".format(i + 1) +
                                                                 constants.STR_LEFT_SLASH + '64'),
                                                      cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                # windows虚拟机
                else:
                    from scripts.script_libs.windows_hyperv_manage_vm import KvmOp
                    # 获取配置文件中虚拟机名称
                    vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    # 检查虚拟机状态并配置为正确状态
                    status, _ = CommonOperation.check_kvm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                                execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                                device_name_server="",
                                                                device_name_client=device_name_client,
                                                                vf_num=caller_class.client_test_object_num)
                    log.info("vm status:{}".format(status))
                    if not status:
                        log.error("check_kvm_stats fail !")
                        return RtnStatusEnum.FAIL.value
                    if status:
                        # 若check_kvm_stats执行成功 ，但vm未启动，则再启动一次
                        if "shut off" == KvmOp.check_vm_state(vm_name,
                                                              cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value):
                            KvmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
                            KvmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)

            # step 2.2 如果vlan，创建、启用vlan、配置IP地址、获取子接口名称
            elif caller_class.client_test_object == TestObjectType.VLAN.value:
                ip_header = CommonOperation.generate_ip_header(pf_device_name=device_name_client,
                                                               target_device_type=TestObjectType.VLAN.value,
                                                               cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                for i in range(caller_class.client_test_object_num):
                    vlan_name = IpOperation.create_vlan_name(device_name_client, str(i + 1))
                    # vlan_name = device_name_client + '.' + str(i + 1)
                    if len(vlan_name) > 15:
                        vlan_name = vlan_name[-15:]
                    IpOperation.add_vlan(device_name=device_name_client,
                                         vlan_name=vlan_name,
                                         vlan_id=str(i + 1),
                                         vlan_addr=ip_header + str(i + 1),
                                         cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                         level=-1)

            # step 2.3 如果vlan，创建、启用vlan、配置IP地址、获取子接口名称
            elif caller_class.client_test_object == TestObjectType.DVLAN.value:
                ip_header = CommonOperation.generate_ip_header(pf_device_name=device_name_client,
                                                               target_device_type=TestObjectType.DVLAN.value,
                                                               cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                for i in range(caller_class.client_test_object_num):
                    # dvlan_name = device_name_client + '.' + str(i + 1) + '.' + str(i + 10)
                    dvlan_name = IpOperation.create_vlan_name(device_name_client, str(i + 1)) + '.' + str(i + 10)
                    if len(dvlan_name) > 15:
                        dvlan_name = dvlan_name[-15:]
                    vlan_name = '.'.join(dvlan_name.split('.')[:-1])
                    IpOperation.add_vlan(device_name=device_name_client,
                                         vlan_name=vlan_name,
                                         vlan_id=str(i + 1),
                                         vlan_addr='',
                                         cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                         level=-1)
                    IpOperation.add_vlan(device_name=vlan_name,
                                         vlan_name=dvlan_name,
                                         vlan_id=str(i + 10),
                                         vlan_addr=ip_header + str(i + 110 + caller_class.client_test_object_num),
                                         cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                         level=-1)

            # step 2.4 如果macvlan，创建、启动macvlan、默认bridge模式
            elif caller_class.client_test_object == TestObjectType.MACVLAN.value:
                for i in range(caller_class.client_test_object_num):
                    macvlan_name = 'p' + device_name_client[-1] + 'macvlan' + str(i + 1)
                    macvlan_ip = (constants.RESERVED_MACVLAN_IP_HEADER.split('.')[0] + '.' +
                                  constants.RESERVED_MACVLAN_IP_HEADER.split('.')[1] + '.' +
                                  str(int(constants.RESERVED_MACVLAN_IP_HEADER.split('.')[2]) + int(device_name_client[-1])*10) + '.' +
                                  str(i + 1 + caller_class.client_test_object_num + int(device_name_client[-1])*10))
                    IpOperation.add_macvlan(device_name=device_name_client, macvlan_name=macvlan_name,
                                            macvlan_mode=MacVlanModeEnum.BRIDGE.value,
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    IpOperation.add_ip_addr(device_name=macvlan_name,
                                            ip_addr=(macvlan_ip +
                                                     constants.STR_LEFT_SLASH + '24'),
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)

            # step 2.5 如果vf-macvlan，加载vf驱动、echo、创建、启动macvlan、默认bridge模式，数量一对一
            elif caller_class.client_test_object == TestObjectType.VFMACVLAN.value:
                result_generate_0 = CommonOperation.generate_vf_device(
                    pf_device_name=device_name_client,
                    vf_num=0,
                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                if not result_generate_0:
                    log.info('修改vf数量为0命令执行失败')
                rtn_code = cls.watch_virtual_driver(nic_driver=client_vf_driver_name,
                                                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                if not rtn_code:
                    result_modprobe = cls.modprobe_driver(driver_name=client_vf_driver_name)
                    if not result_modprobe:
                        log.info('vf驱动加载失败')
                result_generate = cls.generate_vf_device(pf_device_name=device_name_client,
                                                         vf_num=caller_class.client_test_object_num,
                                                         cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                if not result_generate:
                    log.info(f'修改vf数量为{caller_class.client_test_object_num}命令执行失败')
                for i in range(caller_class.client_test_object_num):
                    macvlan_name = 'p' + device_name_client[-1] + 'v' + str(i) + 'macvlan' + str(i + 1)
                    macvlan_ip = (constants.RESERVED_MACVLAN_IP_HEADER.split('.')[0] + '.' + 
                                  constants.RESERVED_MACVLAN_IP_HEADER.split('.')[1] + '.' +
                                  str(int(constants.RESERVED_MACVLAN_IP_HEADER.split('.')[2]) + int(device_name_client[-1])*10 + i*20) + '.' +
                                  str(i + 1 + caller_class.client_test_object_num + int(device_name_client[-1])*10 + i*20))
                    IpOperation.add_macvlan(device_name=device_name_client + 'v' + str(i),
                                            macvlan_name=macvlan_name,
                                            macvlan_mode=MacVlanModeEnum.BRIDGE.value,
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    IpOperation.add_ip_addr(device_name=macvlan_name,
                                            ip_addr=(macvlan_ip +
                                                     constants.STR_LEFT_SLASH + '24'),
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)

            # step 2.6 如果vf-vlan，加载vf驱动、echo、创建、启动vlan、配置vlan ip，数量一对一
            elif caller_class.client_test_object == TestObjectType.VFVLAN.value:
                # linux虚拟机
                if "windows" not in guest_os_client:
                    result_generate_0 = CommonOperation.generate_vf_device(
                        pf_device_name=device_name_client,
                        vf_num=0,
                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    if not result_generate_0:
                        log.info('修改vf数量为0命令执行失败')
                    rtn_code = cls.watch_virtual_driver(nic_driver=client_vf_driver_name,
                                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    if not rtn_code:
                        result_modprobe = cls.modprobe_driver(driver_name=client_vf_driver_name)
                    result_generate = cls.generate_vf_device(pf_device_name=device_name_client,
                                                             vf_num=caller_class.client_test_object_num,
                                                             cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    if not result_generate:
                        log.info(f'修改vf数量为{caller_class.client_test_object_num}命令执行失败')
                    vf_device_names = CommonOperation.get_vf_device_names_by_pf(
                        pf_device_name=device_name_client,
                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    for i in range(len(vf_device_names)):
                        IpOperation.flush_dev_ip(
                            vf_device_names[i], cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        ip_header = CommonOperation.generate_ip_header(pf_device_name=device_name_client,
                                                                       target_device_type=TestObjectType.VFVLAN.value,
                                                                       cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                                       offset=i)
                        # vlan_name = vf_device_names[i] + '.' + str(i + 1)
                        vlan_name = IpOperation.create_vlan_name(vf_device_names[i], str(i + 1))
                        if len(vlan_name) > 15:
                            vlan_name = vlan_name[-15:]
                        IpOperation.add_vlan(device_name=vf_device_names[i],
                                             vlan_name=vlan_name,
                                             vlan_id=str(i + 1),
                                             vlan_addr=ip_header + str(i + 1),
                                             cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                             level=-1)
                # windows虚拟机
                else:
                    from scripts.script_libs.windows_hyperv_manage_vm import KvmOp
                    # 获取配置文件中虚拟机名称
                    vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    # 检查虚拟机状态并配置为正确状态
                    status, _ = CommonOperation.check_kvm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                                execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                                device_name_server="",
                                                                device_name_client=device_name_client,
                                                                vf_num=caller_class.client_test_object_num)
                    log.info("vm status:{}".format(status))
                    if not status:
                        log.error("check_kvm_stats fail !")
                        return RtnStatusEnum.FAIL.value
                    if status:
                        # 若check_kvm_stats执行成功 ，但vm未启动，则再启动一次
                        if "shut off" == KvmOp.check_vm_state(vm_name,
                                                              cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value):
                            KvmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
                            KvmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    # vf添加vlan
                    vf_name = CommonOperation.get_vf_name(execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                          vm_name=constants.KVM_VM_NAME)
                    KvmOp.set_vf_vlan(vf_name, str(int(vf_name.split("v")[1]) + 10),
                                      execute_address=CmdExecuteAdressEnum.CLIENT.value)

            # step 2.7 如果vf-dvlan，加载vf驱动、echo、创建、启动dvlan、配置dvlan ip，数量一对一
            elif caller_class.client_test_object == TestObjectType.VFDVLAN.value:
                # linux虚拟机
                if "windows" not in guest_os_client:
                    result_generate_0 = CommonOperation.generate_vf_device(
                        pf_device_name=device_name_client,
                        vf_num=0,
                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    if not result_generate_0:
                        log.info('修改vf数量为0命令执行失败')
                    rtn_code = cls.watch_virtual_driver(nic_driver=client_vf_driver_name,
                                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    if not rtn_code:
                        result_modprobe = cls.modprobe_driver(driver_name=client_vf_driver_name)
                    result_generate = cls.generate_vf_device(pf_device_name=device_name_client,
                                                             vf_num=caller_class.client_test_object_num,
                                                             cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    if not result_generate:
                        log.info(f'修改vf数量为{caller_class.client_test_object_num}命令执行失败')
                    vf_device_names = CommonOperation.get_vf_device_names_by_pf(
                        pf_device_name=device_name_client,
                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    for i in range(len(vf_device_names)):
                        IpOperation.flush_dev_ip(
                            vf_device_names[i], cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        ip_header = CommonOperation.generate_ip_header(pf_device_name=device_name_client,
                                                                       target_device_type=TestObjectType.VFDVLAN.value,
                                                                       cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                                       offset=i)
                        # dvlan_name = vf_device_names[i] + '.' + str(i + 1) + '.' + str(i + 10)
                        dvlan_name = IpOperation.create_vlan_name(vf_device_names[i], str(i + 1)) + '.' + str(i + 10)
                        if len(dvlan_name) > 15:
                            dvlan_name = dvlan_name[-15:]
                        vlan_name = '.'.join(dvlan_name.split('.')[:-1])
                        IpOperation.add_vlan(device_name=vf_device_names[i],
                                             vlan_name=vlan_name,
                                             vlan_id=str(i + 1),
                                             vlan_addr='',
                                             cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                             level=-1)
                        IpOperation.add_vlan(device_name=vlan_name,
                                             vlan_name=dvlan_name,
                                             vlan_id=str(i + 10),
                                             vlan_addr=ip_header + str(i + 110 + caller_class.client_test_object_num),
                                             cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                             level=-1)
                # windows虚拟机
                else:
                    from scripts.script_libs.windows_hyperv_manage_vm import KvmOp
                    # 获取配置文件中虚拟机名称
                    vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    # 检查虚拟机状态并配置为正确状态
                    status, _ = CommonOperation.check_kvm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                                execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                                device_name_server="",
                                                                device_name_client=device_name_client,
                                                                vf_num=caller_class.client_test_object_num)
                    log.info("vm status:{}".format(status))
                    if not status:
                        log.error("check_kvm_stats fail !")
                        return RtnStatusEnum.FAIL.value
                    if status:
                        # 若check_kvm_stats执行成功 ，但vm未启动，则再启动一次
                        if "shut off" == KvmOp.check_vm_state(vm_name,
                                                              cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value):
                            KvmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
                            KvmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    # vf添加vlan
                    vf_name = CommonOperation.get_vf_name(execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                          vm_name=constants.KVM_VM_NAME)
                    KvmOp.set_vf_vlan(vf_name, str(int(vf_name.split("v")[1]) + 10),
                                      execute_address=CmdExecuteAdressEnum.CLIENT.value)

            # step 2.8 如果bond1，创建、启用bond、配置IP地址、获取子接口名称
            elif caller_class.client_test_object == TestObjectType.BOND1.value:
                if cls.bond_prepared_client:
                    return RtnStatusEnum.SUCCESS.value

                exec_addr = CmdExecuteAdressEnum.CLIENT.value
                server_devices, client_devices = cls.get_nic_relationships()
                for device in client_devices:
                    if device == device_name_client:
                        master_device = device
                        break
                client_devices.remove(master_device)
                slave_device = client_devices[0]

                for i in range(caller_class.client_test_object_num):
                    bond_name = f'bond{i}m1'
                    # 添加bond设备
                    IpOperation.add_bond(device_name=master_device,
                                         backup_device_name=slave_device,
                                         bond_name=bond_name,
                                         bond_mode=BondModeEnum.ACTIVE_BACKUP.value,
                                         cmd_execute_address=exec_addr)
                    # bond添加ip
                    ip_header = CommonOperation.generate_ip_header(
                        pf_device_name=device_name_client,
                        target_device_type=TestObjectType.BOND1.value,
                        cmd_execute_address=exec_addr,
                        offset=i)
                    ipv6_header = CommonOperation.generate_ipv6_header(
                        pf_device_name=device_name_client,
                        target_device_type=TestObjectType.BOND1.value,
                        cmd_execute_address=exec_addr,
                        offset=i)
                    IpOperation.add_ip_addr(device_name=bond_name,
                                            ip_addr=(ip_header + str(i + 20) +
                                                     constants.STR_LEFT_SLASH + '24'),
                                            cmd_execute_address=exec_addr)
                    IpOperation.add_ipv6_addr(device_name=bond_name,
                                              ipv6_addr=(ipv6_header + "{:04x}".format(i + 1) +
                                                         constants.STR_LEFT_SLASH + '64'),
                                              cmd_execute_address=exec_addr)
                    # 启用bond接口
                    IpOperation.set_bond(bond_name=bond_name, stats=constants.UP,
                                         cmd_execute_address=exec_addr)
                    # 查看bond状态
                    IpOperation.show_bond(bond_name=bond_name,
                                          cmd_execute_address=exec_addr)

                cls.bond_prepared_client = True
            # step 2.9 如果bond2，创建、启用bond、配置IP地址、获取子接口名称
            elif caller_class.client_test_object == TestObjectType.BOND2.value:
                if cls.bond_prepared_client:
                    return RtnStatusEnum.SUCCESS.value

                exec_addr = CmdExecuteAdressEnum.CLIENT.value
                server_devices, client_devices = cls.get_nic_relationships()
                for device in client_devices:
                    if device == device_name_client:
                        master_device = device
                        break
                client_devices.remove(master_device)
                slave_device = client_devices[0]

                for i in range(caller_class.client_test_object_num):
                    bond_name = f'bond{i}m2'
                    # 添加bond设备
                    IpOperation.add_bond(device_name=master_device,
                                         backup_device_name=slave_device,
                                         bond_name=bond_name,
                                         bond_mode=BondModeEnum.BALANCE_XOR.value,
                                         cmd_execute_address=exec_addr)
                    # bond添加ip
                    ip_header = CommonOperation.generate_ip_header(
                        pf_device_name=device_name_client,
                        target_device_type=TestObjectType.BOND2.value,
                        cmd_execute_address=exec_addr,
                        offset=i)
                    ipv6_header = CommonOperation.generate_ipv6_header(
                        pf_device_name=device_name_client,
                        target_device_type=TestObjectType.BOND2.value,
                        cmd_execute_address=exec_addr,
                        offset=i)
                    IpOperation.add_ip_addr(device_name=bond_name,
                                            ip_addr=(ip_header + str(i + 1) +
                                                     constants.STR_LEFT_SLASH + '24'),
                                            cmd_execute_address=exec_addr)
                    IpOperation.add_ipv6_addr(device_name=bond_name,
                                              ipv6_addr=(ipv6_header + "{:04x}".format(i + 1) +
                                                         constants.STR_LEFT_SLASH + '64'),
                                              cmd_execute_address=exec_addr)
                    # 启用bond接口
                    IpOperation.set_bond(bond_name=bond_name, stats=constants.UP,
                                         cmd_execute_address=exec_addr)
                    # 查看bond状态
                    IpOperation.show_bond(bond_name=bond_name,
                                          cmd_execute_address=exec_addr)
                cls.bond_prepared_client = True

            # step 2.10 如果bond4，创建、启用bond、配置IP地址、获取子接口名称
            elif caller_class.client_test_object == TestObjectType.BOND4.value:
                if cls.bond_prepared_client:
                    return RtnStatusEnum.SUCCESS.value

                exec_addr = CmdExecuteAdressEnum.CLIENT.value
                server_devices, client_devices = cls.get_nic_relationships()
                for device in client_devices:
                    if device == device_name_client:
                        master_device = device
                        break
                client_devices.remove(master_device)
                slave_device = client_devices[0]

                for i in range(caller_class.client_test_object_num):
                    bond_name = f'bond{i}m4'
                    # 添加bond设备
                    IpOperation.add_bond(device_name=master_device,
                                         backup_device_name=slave_device,
                                         bond_name=bond_name,
                                         bond_mode=BondModeEnum.AD_8023.value,
                                         cmd_execute_address=exec_addr)
                    # bond添加ip
                    ip_header = CommonOperation.generate_ip_header(
                        pf_device_name=device_name_client,
                        target_device_type=TestObjectType.BOND4.value,
                        cmd_execute_address=exec_addr,
                        offset=i)
                    ipv6_header = CommonOperation.generate_ipv6_header(
                        pf_device_name=device_name_client,
                        target_device_type=TestObjectType.BOND4.value,
                        cmd_execute_address=exec_addr,
                        offset=i)
                    IpOperation.add_ip_addr(device_name=bond_name,
                                            ip_addr=(ip_header + str(i + 1) +
                                                     constants.STR_LEFT_SLASH + '24'),
                                            cmd_execute_address=exec_addr)
                    IpOperation.add_ipv6_addr(device_name=bond_name,
                                              ipv6_addr=(ipv6_header + "{:04x}".format(i + 1) +
                                                         constants.STR_LEFT_SLASH + '64'),
                                              cmd_execute_address=exec_addr)
                    # 启用bond接口
                    IpOperation.set_bond(bond_name=bond_name, stats=constants.UP,
                                         cmd_execute_address=exec_addr)
                    # 查看bond状态
                    IpOperation.show_bond(bond_name=bond_name,
                                          cmd_execute_address=exec_addr)
                cls.bond_prepared_client = True

        if device_name_server and 'windows' not in host_os_server:
            # step 2.8 如果是VF,加载VF驱动、echo 数量、get_vf_device_name获取子接口名称
            if caller_class.server_test_object == TestObjectType.VF.value:
                # linux虚拟机
                if 'windows' not in guest_os_server:
                    if server_driver_name in [NicNameEnum.INTEL_82599.value, NicNameEnum.SXE.value,
                                              NicNameEnum.E810.value, NicNameEnum.CX6.value, NicNameEnum.SXE2.value, NicNameEnum.SCGBE.value,
                                              NicNameEnum.SCE.value]:
                        log.info("========================device_name_server:{}".format(device_name_server))
                        result_generate_0 = CommonOperation.generate_vf_device(
                            pf_device_name=device_name_server,
                            vf_num=0,
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        if not result_generate_0:
                            log.info('修改vf数量为0命令执行失败')
                        rtn_code = cls.watch_virtual_driver(nic_driver=server_vf_driver_name,
                                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        if not rtn_code:
                            result_modprobe = cls.modprobe_driver(driver_name=server_vf_driver_name,
                                                                  cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        result_generate = cls.generate_vf_device(
                            pf_device_name=device_name_server,
                            vf_num=caller_class.server_test_object_num,
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        if not result_generate:
                            log.info(f'修改vf数量为{caller_class.server_test_object_num}命令执行失败')
                        vf_device_names = CommonOperation.get_vf_device_names_by_pf(
                            pf_device_name=device_name_server,
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        # add by wangwt start:
                        for vf_device_name in vf_device_names:
                            info_dict = IfConfig.analysis_ifconfig_info(
                                device_name=vf_device_name,
                                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value
                            )
                            while 'inet' in info_dict.keys():
                                IpOperation.del_ip_addr(device_name=vf_device_name,
                                                        ip_addr=info_dict['inet'],
                                                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                                info_dict = IfConfig.analysis_ifconfig_info(
                                    device_name=vf_device_name,
                                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        # add by wangwt end
                        for i in range(len(vf_device_names)):
                            ip_header = CommonOperation.generate_ip_header(
                                pf_device_name=device_name_server,
                                target_device_type=TestObjectType.VF.value,
                                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                offset=i)
                            ipv6_header = CommonOperation.generate_ipv6_header(
                                pf_device_name=device_name_server,
                                target_device_type=TestObjectType.VF.value,
                                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                offset=i)
                            log.info("清除vf ip")
                            IpOperation.flush_dev_ip(
                                vf_device_names[i], cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                            log.info("添加vf ipv4")
                            IpOperation.add_ip_addr(device_name=vf_device_names[i],
                                                    ip_addr=(ip_header +
                                                             str(i + 1 + caller_class.client_test_object_num) +
                                                             constants.STR_LEFT_SLASH + '24'),
                                                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                            log.info("添加vf ipv6")
                            IpOperation.add_ipv6_addr(
                                device_name=vf_device_names[i],
                                ipv6_addr=(ipv6_header + "{:04x}".format(
                                    i + 1 + caller_class.client_test_object_num) +
                                           constants.STR_LEFT_SLASH + '64'),
                                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                # windows虚拟机
                else:
                    from scripts.script_libs.windows_hyperv_manage_vm import KvmOp
                    # 获取配置文件中虚拟机名称
                    vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.SERVER.value)
                    CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    # 检查虚拟机状态并配置为正确状态
                    status, _ = CommonOperation.check_kvm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                                execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                                device_name_server=device_name_server,
                                                                device_name_client="",
                                                                vf_num=caller_class.server_test_object_num)
                    log.info("vm status:{}".format(status))
                    if not status:
                        log.error("check_kvm_stats fail !")
                        return RtnStatusEnum.FAIL.value
                    if status:
                        # 若check_kvm_stats执行成功 ，但vm未启动，则再启动一次
                        if "shut off" == KvmOp.check_vm_state(vm_name,
                                                              cmd_execute_address=CmdExecuteAdressEnum.SERVER.value):
                            KvmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
                            KvmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)

            # step 2.9 如果vlan，创建、启用vlan、配置IP地址、获取子接口名称
            elif caller_class.server_test_object == TestObjectType.VLAN.value:
                ip_header = CommonOperation.generate_ip_header(pf_device_name=device_name_server,
                                                               target_device_type=TestObjectType.VLAN.value,
                                                               cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                for i in range(caller_class.server_test_object_num):
                    # vlan_name = device_name_server + '.' + str(i + 1)
                    vlan_name = IpOperation.create_vlan_name(device_name_server, str(i + 1))
                    if len(vlan_name) > 15:
                        vlan_name = vlan_name[-15:]
                    IpOperation.add_vlan(device_name=device_name_server,
                                         vlan_name=vlan_name,
                                         vlan_id=str(i + 1),
                                         vlan_addr=ip_header + str(i + 1 + caller_class.client_test_object_num),
                                         cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                         level=-1)

            # step 2.10 如果vlan，创建、启用vlan、配置IP地址、获取子接口名称
            elif caller_class.server_test_object == TestObjectType.DVLAN.value:
                ip_header = CommonOperation.generate_ip_header(pf_device_name=device_name_server,
                                                               target_device_type=TestObjectType.DVLAN.value,
                                                               cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                for i in range(caller_class.server_test_object_num):
                    # dvlan_name = device_name_server + '.' + str(i + 1) + '.' + str(i + 10)
                    dvlan_name = IpOperation.create_vlan_name(device_name_server, str(i + 1)) + '.' + str(i + 10)
                    if len(dvlan_name) > 15:
                        dvlan_name = dvlan_name[-15:]
                    vlan_name = '.'.join(dvlan_name.split('.')[:-1])
                    IpOperation.add_vlan(device_name=device_name_server,
                                         vlan_name=vlan_name,
                                         vlan_id=str(i + 1),
                                         vlan_addr='',
                                         cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                         level=-1)
                    IpOperation.add_vlan(device_name=vlan_name,
                                         vlan_name=dvlan_name,
                                         vlan_id=str(i + 10),
                                         vlan_addr=ip_header + str(i + 100 + caller_class.client_test_object_num),
                                         cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                         level=-1)

            # step 2.11 如果macvlan，创建、启动macvlan、默认bridge模式
            elif caller_class.server_test_object == TestObjectType.MACVLAN.value:
                for i in range(caller_class.server_test_object_num):
                    macvlan_name = 'p' + device_name_server[-1] + 'macvlan' + str(i + 1)
                    macvlan_ip = (constants.RESERVED_MACVLAN_IP_HEADER.split('.')[0] + '.' +
                                  constants.RESERVED_MACVLAN_IP_HEADER.split('.')[1] + '.' +
                                  str(int(constants.RESERVED_MACVLAN_IP_HEADER.split('.')[2]) + int(device_name_server[-1])*10) + '.' +
                                  str(i + 1 + caller_class.server_test_object_num + int(device_name_server[-1])*10))
                    IpOperation.add_macvlan(device_name=device_name_server, macvlan_name=macvlan_name,
                                            macvlan_mode=MacVlanModeEnum.BRIDGE.value,
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    IpOperation.add_ip_addr(device_name=macvlan_name,
                                            ip_addr=(macvlan_ip +
                                                     constants.STR_LEFT_SLASH + '24'),
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)

            # step 2.12 如果vf-macvlan，加载vf驱动、echo、创建、启动macvlan、默认bridge模式，数量一对一
            elif caller_class.server_test_object == TestObjectType.VFMACVLAN.value:
                result_generate_0 = CommonOperation.generate_vf_device(
                    pf_device_name=device_name_server,
                    vf_num=0,
                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                if not result_generate_0:
                    log.info('修改vf数量为0命令执行失败')
                rtn_code = cls.watch_virtual_driver(nic_driver=server_vf_driver_name,
                                                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                if not rtn_code:
                    result_modprobe = cls.modprobe_driver(driver_name=server_vf_driver_name,
                                                          cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    if not result_modprobe:
                        log.info('vf驱动加载失败')
                result_generate = cls.generate_vf_device(pf_device_name=device_name_server,
                                                         vf_num=caller_class.server_test_object_num,
                                                         cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                if not result_generate:
                    log.info(f'修改vf数量为{caller_class.server_test_object_num}命令执行失败')
                for i in range(caller_class.server_test_object_num):
                    macvlan_name = 'p' + device_name_server[-1] + 'v' + str(i) + 'macvlan' + str(i + 1)
                    macvlan_ip = (constants.RESERVED_MACVLAN_IP_HEADER.split('.')[0] + '.' + 
                                  constants.RESERVED_MACVLAN_IP_HEADER.split('.')[1] + '.' +
                                  str(int(constants.RESERVED_MACVLAN_IP_HEADER.split('.')[2]) + int(device_name_server[-1])*10 + i*20) + '.' +
                                  str(i + 1 + caller_class.server_test_object_num + int(device_name_server[-1])*10 + i*20))
                    IpOperation.add_macvlan(device_name=device_name_server + 'v' + str(i),
                                            macvlan_name=macvlan_name,
                                            macvlan_mode=MacVlanModeEnum.BRIDGE.value,
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    IpOperation.add_ip_addr(device_name=macvlan_name,
                                            ip_addr=(macvlan_ip +
                                                     constants.STR_LEFT_SLASH + '24'),
                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)

            # step 2.13 如果vf-vlan，加载vf驱动、echo、创建、启动vlan、配置vlan ip，数量一对一
            elif caller_class.server_test_object == TestObjectType.VFVLAN.value:
                # linux虚拟机
                if "windows" not in guest_os_server:
                    result_generate_0 = CommonOperation.generate_vf_device(
                        pf_device_name=device_name_server,
                        vf_num=0,
                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    if not result_generate_0:
                        log.info('修改vf数量为0命令执行失败')
                    rtn_code = cls.watch_virtual_driver(nic_driver=server_vf_driver_name,
                                                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    if not rtn_code:
                        result_modprobe = cls.modprobe_driver(driver_name=server_vf_driver_name,
                                                              cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    result_generate = cls.generate_vf_device(pf_device_name=device_name_server,
                                                             vf_num=caller_class.server_test_object_num,
                                                             cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    if not result_generate:
                        log.info(f'修改vf数量为{caller_class.server_test_object_num}命令执行失败')
                    vf_device_names = CommonOperation.get_vf_device_names_by_pf(
                        pf_device_name=device_name_server,
                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    for i in range(len(vf_device_names)):
                        IpOperation.flush_dev_ip(
                            vf_device_names[i], cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        ip_header = CommonOperation.generate_ip_header(pf_device_name=device_name_server,
                                                                       target_device_type=TestObjectType.VFVLAN.value,
                                                                       cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                                       offset=i)
                        vlan_addr = ip_header + str(i + 1 + caller_class.client_test_object_num)
                        # vlan_name = vf_device_names[i] + '.' + str(i + 1)
                        vlan_name = IpOperation.create_vlan_name(vf_device_names[i], str(i + 1))
                        if len(vlan_name) > 15:
                            vlan_name = vlan_name[-15:]
                        IpOperation.add_vlan(device_name=vf_device_names[i],
                                             vlan_name=vlan_name,
                                             vlan_id=str(i + 1),
                                             vlan_addr=vlan_addr,
                                             cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, level=-1
                                             )
                # windows虚拟机
                else:
                    from scripts.script_libs.windows_hyperv_manage_vm import KvmOp
                    # 获取配置文件中虚拟机名称
                    vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.SERVER.value)
                    CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    # 检查虚拟机状态并配置为正确状态
                    status, _ = CommonOperation.check_kvm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                                execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                                device_name_client="",
                                                                device_name_server=device_name_server,
                                                                vf_num=caller_class.server_test_object_num)
                    log.info("vm status:{}".format(status))
                    if not status:
                        log.error("check_kvm_stats fail !")
                        return RtnStatusEnum.FAIL.value
                    if status:
                        # 若check_kvm_stats执行成功 ，但vm未启动，则再启动一次
                        if "shut off" == KvmOp.check_vm_state(vm_name,
                                                              cmd_execute_address=CmdExecuteAdressEnum.SERVER.value):
                            KvmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
                            KvmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
                    # vf添加vlan
                    vf_name = CommonOperation.get_vf_name(execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                          vm_name=constants.KVM_VM_NAME)
                    KvmOp.set_vf_vlan(vf_name, str(int(vf_name.split("v")[1]) + 10),
                                      cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)

            # step 2.14 如果vf-dvlan，加载vf驱动、echo、创建、启动dvlan、配置dvlan ip，数量一对一
            elif caller_class.server_test_object == TestObjectType.VFDVLAN.value:
                # linux虚拟机
                if "windows" not in guest_os_server:
                    result_generate_0 = CommonOperation.generate_vf_device(
                        pf_device_name=device_name_server,
                        vf_num=0,
                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    if not result_generate_0:
                        log.info('修改vf数量为0命令执行失败')
                    rtn_code = cls.watch_virtual_driver(nic_driver=server_vf_driver_name,
                                                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    if not rtn_code:
                        result_modprobe = cls.modprobe_driver(driver_name=server_vf_driver_name)
                    result_generate = cls.generate_vf_device(pf_device_name=device_name_server,
                                                             vf_num=caller_class.server_test_object_num,
                                                             cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    if not result_generate:
                        log.info(f'修改vf数量为{caller_class.server_test_object_num}命令执行失败')
                    vf_device_names = CommonOperation.get_vf_device_names_by_pf(
                        pf_device_name=device_name_server,
                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    for i in range(len(vf_device_names)):
                        IpOperation.flush_dev_ip(
                            vf_device_names[i], cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        ip_header = CommonOperation.generate_ip_header(pf_device_name=device_name_server,
                                                                       target_device_type=TestObjectType.VFDVLAN.value,
                                                                       cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                                       offset=i)
                        # dvlan_name = vf_device_names[i] + '.' + str(i + 1) + '.' + str(i + 10)
                        dvlan_name = IpOperation.create_vlan_name(vf_device_names[i], str(i + 1)) + '.' + str(i + 10)
                        if len(dvlan_name) > 15:
                            dvlan_name = dvlan_name[-15:]
                        vlan_name = '.'.join(dvlan_name.split('.')[:-1])
                        IpOperation.add_vlan(device_name=vf_device_names[i],
                                             vlan_name=vlan_name,
                                             vlan_id=str(i + 1),
                                             vlan_addr='',
                                             cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                             level=-1)
                        IpOperation.add_vlan(device_name=vlan_name,
                                             vlan_name=dvlan_name,
                                             vlan_id=str(i + 10),
                                             vlan_addr=ip_header + str(i + 100 + caller_class.client_test_object_num),
                                             cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                             level=-1)
                # windows虚拟机
                else:
                    from scripts.script_libs.windows_hyperv_manage_vm import KvmOp
                    # 获取配置文件中虚拟机名称
                    vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.SERVER.value)
                    CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    # 检查虚拟机状态并配置为正确状态
                    status, _ = CommonOperation.check_kvm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                                execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                                device_name_client="",
                                                                device_name_server=device_name_server,
                                                                vf_num=caller_class.server_test_object_num)
                    log.info("vm status:{}".format(status))
                    if not status:
                        log.error("check_kvm_stats fail !")
                        return RtnStatusEnum.FAIL.value
                    if status:
                        # 若check_kvm_stats执行成功 ，但vm未启动，则再启动一次
                        if "shut off" == KvmOp.check_vm_state(vm_name,
                                                              cmd_execute_address=CmdExecuteAdressEnum.SERVER.value):
                            KvmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
                            KvmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
                    # vf添加vlan
                    vf_name = CommonOperation.get_vf_name(execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                          vm_name=constants.KVM_VM_NAME)
                    KvmOp.set_vf_vlan(vf_name, str(int(vf_name.split("v")[1]) + 10),
                                      cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)

            # step 2.8 如果bond1，创建、启用bond、配置IP地址、获取子接口名称
            elif caller_class.server_test_object == TestObjectType.BOND1.value:
                if cls.bond_prepared_server:
                    return RtnStatusEnum.SUCCESS.value

                exec_addr = CmdExecuteAdressEnum.SERVER.value
                server_devices, client_devices = cls.get_nic_relationships()
                for device in server_devices:
                    if device == device_name_server:
                        master_device = device
                        break
                server_devices.remove(master_device)
                slave_device = server_devices[0]

                for i in range(caller_class.server_test_object_num):
                    bond_name = f'bond{i}m1'
                    # 添加bond设备
                    IpOperation.add_bond(device_name=master_device,
                                         backup_device_name=slave_device,
                                         bond_name=bond_name,
                                         bond_mode=BondModeEnum.ACTIVE_BACKUP.value,
                                         cmd_execute_address=exec_addr)
                    # bond添加ip
                    ip_header = CommonOperation.generate_ip_header(
                        pf_device_name=device_name_server,
                        target_device_type=TestObjectType.BOND1.value,
                        cmd_execute_address=exec_addr,
                        offset=i)
                    ipv6_header = CommonOperation.generate_ipv6_header(
                        pf_device_name=device_name_server,
                        target_device_type=TestObjectType.BOND1.value,
                        cmd_execute_address=exec_addr,
                        offset=i)
                    IpOperation.add_ip_addr(device_name=bond_name,
                                            ip_addr=(ip_header + str(i + 1) +
                                                     constants.STR_LEFT_SLASH + '24'),
                                            cmd_execute_address=exec_addr)
                    IpOperation.add_ipv6_addr(device_name=bond_name,
                                              ipv6_addr=(ipv6_header + "{:04x}".format(i + 1) +
                                                         constants.STR_LEFT_SLASH + '64'),
                                              cmd_execute_address=exec_addr)
                    # 启用bond接口
                    IpOperation.set_bond(bond_name=bond_name, stats=constants.UP,
                                         cmd_execute_address=exec_addr)
                    # 查看bond状态
                    IpOperation.show_bond(bond_name=bond_name,
                                          cmd_execute_address=exec_addr)
                cls.bond_prepared_server = True

            # step 2.9 如果bond2，创建、启用bond、配置IP地址、获取子接口名称
            elif caller_class.server_test_object == TestObjectType.BOND2.value:
                if cls.bond_prepared_server:
                    return RtnStatusEnum.SUCCESS.value

                exec_addr = CmdExecuteAdressEnum.SERVER.value
                server_devices, client_devices = cls.get_nic_relationships()
                for device in server_devices:
                    if device == device_name_server:
                        master_device = device
                        break
                server_devices.remove(master_device)
                slave_device = server_devices[0]

                for i in range(caller_class.server_test_object_num):
                    bond_name = f'bond{i}m2'
                    # 添加bond设备
                    IpOperation.add_bond(device_name=master_device,
                                         backup_device_name=slave_device,
                                         bond_name=bond_name,
                                         bond_mode=BondModeEnum.BALANCE_XOR.value,
                                         cmd_execute_address=exec_addr)
                    # bond添加ip
                    ip_header = CommonOperation.generate_ip_header(
                        pf_device_name=device_name_server,
                        target_device_type=TestObjectType.BOND2.value,
                        cmd_execute_address=exec_addr,
                        offset=i)
                    ipv6_header = CommonOperation.generate_ipv6_header(
                        pf_device_name=device_name_server,
                        target_device_type=TestObjectType.BOND2.value,
                        cmd_execute_address=exec_addr,
                        offset=i)
                    IpOperation.add_ip_addr(device_name=bond_name,
                                            ip_addr=(ip_header + str(i + 1) +
                                                     constants.STR_LEFT_SLASH + '24'),
                                            cmd_execute_address=exec_addr)
                    IpOperation.add_ipv6_addr(device_name=bond_name,
                                              ipv6_addr=(ipv6_header + "{:04x}".format(i + 1) +
                                                         constants.STR_LEFT_SLASH + '64'),
                                              cmd_execute_address=exec_addr)
                    # 启用bond接口
                    IpOperation.set_bond(bond_name=bond_name, stats=constants.UP,
                                         cmd_execute_address=exec_addr)
                    # 查看bond状态
                    IpOperation.show_bond(bond_name=bond_name,
                                          cmd_execute_address=exec_addr)
                cls.bond_prepared_server = True

            # step 2.10 如果bond4，创建、启用bond、配置IP地址、获取子接口名称
            elif caller_class.server_test_object == TestObjectType.BOND4.value:
                if cls.bond_prepared_server:
                    return RtnStatusEnum.SUCCESS.value

                exec_addr = CmdExecuteAdressEnum.SERVER.value
                server_devices, client_devices = cls.get_nic_relationships()
                for device in server_devices:
                    if device == device_name_server:
                        master_device = device
                        break
                server_devices.remove(master_device)
                slave_device = server_devices[0]

                for i in range(caller_class.server_test_object_num):
                    bond_name = f'bond{i}m4'
                    # 添加bond设备
                    IpOperation.add_bond(device_name=master_device,
                                         backup_device_name=slave_device,
                                         bond_name=bond_name,
                                         bond_mode=BondModeEnum.AD_8023.value,
                                         cmd_execute_address=exec_addr)
                    # bond添加ip
                    ip_header = CommonOperation.generate_ip_header(
                        pf_device_name=device_name_server,
                        target_device_type=TestObjectType.BOND4.value,
                        cmd_execute_address=exec_addr,
                        offset=i)
                    ipv6_header = CommonOperation.generate_ipv6_header(
                        pf_device_name=device_name_server,
                        target_device_type=TestObjectType.BOND4.value,
                        cmd_execute_address=exec_addr,
                        offset=i)
                    IpOperation.add_ip_addr(device_name=bond_name,
                                            ip_addr=(ip_header + str(i + 1) +
                                                     constants.STR_LEFT_SLASH + '24'),
                                            cmd_execute_address=exec_addr)
                    IpOperation.add_ipv6_addr(device_name=bond_name,
                                              ipv6_addr=(ipv6_header + "{:04x}".format(i + 1) +
                                                         constants.STR_LEFT_SLASH + '64'),
                                              cmd_execute_address=exec_addr)
                    # 启用bond接口
                    IpOperation.set_bond(bond_name=bond_name, stats=constants.UP,
                                         cmd_execute_address=exec_addr)
                    # 查看bond状态
                    IpOperation.show_bond(bond_name=bond_name,
                                          cmd_execute_address=exec_addr)
                cls.bond_prepared_server = True

        # windows物理机
        if device_name_server and 'windows' in host_os_server:
            from scripts.script_libs.windows_hyperv_manage_vm import VmSwitch, VmAdapter, VmOp
            if caller_class.server_test_object == TestObjectType.VF.value:
                # 获取配置文件中虚拟机名称
                vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                # 检查虚拟机状态并配置为正确状态
                status, _ = CommonOperation.check_vm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                           execute_address=CmdExecuteAdressEnum.SERVER.value)
                log.info("vm status:{}".format(status))
                if not status:
                    log.error("check_vm_stats fail !")
                    return RtnStatusEnum.FAIL.value

                if V_SWITCH_SRIOV_NAME_DEF not in CommonOperation.get_vm_switch_name(
                        execute_address=CmdExecuteAdressEnum.SERVER.value):
                    VmSwitch.new_vmswitch(vmswitch_name=V_SWITCH_SRIOV_NAME_DEF, adapter_name=device_name_server,
                                          enable_iov=True,
                                          execute_address=CmdExecuteAdressEnum.SERVER.value)
                VmAdapter.connect_vmnetworkadapter(vm_name="sxevm001",
                                                   manager_vmswitch_name=V_SWITCH_MANAGER_NAME_DEF,
                                                   vmswitch_name=V_SWITCH_SRIOV_NAME_DEF,
                                                   execute_address=CmdExecuteAdressEnum.SERVER.value)

                if status:
                    # 若check_vm_stats执行成功 ，但vm未启动，则再启动一次
                    if "Off" == VmOp.get_vm_running_state(vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value):
                        VmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
                        VmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
            elif caller_class.server_test_object == TestObjectType.VLAN.value:
                cmd = "set-NetAdapter -name '{}' -vlanid '{}' -confirm:$false".format(device_name_server, 1)
                status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                log.info("status:{}, out:{}, err:{}".format(status, out, err))
                cmd = "Get-NetAdapterAdvancedProperty -name '{}' | grep VLAN".format(device_name_server)
                status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                log.info("status:{}, out:{}, err:{}".format(status, out, err))
            elif caller_class.server_test_object == TestObjectType.MACVLAN.value:
                # 获取配置文件中虚拟机名称
                vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                # 检查虚拟机状态并配置为正确状态
                status, _ = CommonOperation.check_vm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                           execute_address=CmdExecuteAdressEnum.SERVER.value)
                log.info("vm status:{}".format(status))
                if not status:
                    log.error("check_vm_stats fail !")
                    return RtnStatusEnum.FAIL.value

                if V_SWITCH_VMQ_NAME_DEF not in CommonOperation.get_vm_switch_name(
                        execute_address=CmdExecuteAdressEnum.SERVER.value):
                    VmSwitch.new_vmswitch(vmswitch_name=V_SWITCH_VMQ_NAME_DEF, adapter_name=device_name_server,
                                          enable_iov=False,
                                          execute_address=CmdExecuteAdressEnum.SERVER.value)
                VmAdapter.connect_vmnetworkadapter(vm_name="sxevm001",
                                                   vmswitch_name=V_SWITCH_VMQ_NAME_DEF,
                                                   manager_vmswitch_name=V_SWITCH_MANAGER_NAME_DEF,
                                                   execute_address=CmdExecuteAdressEnum.SERVER.value)
                if status:
                    # 若check_vm_stats执行成功 ，但vm未启动，则再启动一次
                    if "Off" == VmOp.get_vm_running_state(vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value):
                        VmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
                        VmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
            elif caller_class.server_test_object == TestObjectType.VFVLAN.value:
                # 获取配置文件中虚拟机名称
                vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                # 检查虚拟机状态并配置为正确状态
                status, _ = CommonOperation.check_vm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                           execute_address=CmdExecuteAdressEnum.SERVER.value)
                log.info("vm status:{}".format(status))
                if not status:
                    log.error("check_vm_stats fail !")
                    return RtnStatusEnum.FAIL.value

                if V_SWITCH_SRIOV_NAME_DEF not in CommonOperation.get_vm_switch_name(
                        execute_address=CmdExecuteAdressEnum.SERVER.value):
                    VmSwitch.new_vmswitch(vmswitch_name=V_SWITCH_SRIOV_NAME_DEF, adapter_name=device_name_server,
                                          enable_iov=True,
                                          execute_address=CmdExecuteAdressEnum.SERVER.value)
                VmAdapter.connect_vmnetworkadapter(vm_name="sxevm001",
                                                   vmswitch_name=V_SWITCH_SRIOV_NAME_DEF,
                                                   manager_vmswitch_name=V_SWITCH_MANAGER_NAME_DEF,
                                                   execute_address=CmdExecuteAdressEnum.SERVER.value)
                if status:
                    # 若check_vm_stats执行成功 ，但vm未启动，则再启动一次
                    if "Off" == VmOp.get_vm_running_state(vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value):
                        VmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
                        VmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
                VmAdapter.set_vmnetworkadapter_vlan(vm_name="sxevm001", vlan_id="1",
                                                    vmswitch_name=V_SWITCH_SRIOV_NAME_DEF,
                                                    manager_vmswitch_name=V_SWITCH_MANAGER_NAME_DEF,
                                                    execute_address=CmdExecuteAdressEnum.SERVER.value)
            elif caller_class.server_test_object == TestObjectType.DEGVMQ.value:
                # 获取配置文件中虚拟机名称
                vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                # 检查虚拟机状态并配置为正确状态
                status, _ = CommonOperation.check_vm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                           execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                           virtual_mode=VirtualModeEnum.DEGVMQ.value)
                log.info("vm status:{}".format(status))
                if not status:
                    log.error("check_vm_stats fail !")
                    return RtnStatusEnum.FAIL.value

                # 设置PF网卡VMQ enable
                from scripts.script_libs.windows_adapter_operation import SetAdapterOperation
                vmq_setting = {"Enabled": str(1)}
                set_adapter = SetAdapterOperation(device_name=device_name_server,
                                                  cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                  **vmq_setting
                                                  )
                rtn_code = set_adapter.set_adapter_vmq()

                # 设置PF网卡SRIOV
                if CommonOperation.get_degvmq_mode_value(PF_SRIOV):
                    sriov_setting = {"Enabled": str(1)}
                else:
                    sriov_setting = {"Enabled": str(0)}
                set_adapter = SetAdapterOperation(device_name=device_name_server,
                                                  cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                  **sriov_setting
                                                  )
                rtn_code = set_adapter.set_adapter_sriov()

                # 新建虚拟交换机
                vm_name = "sxevm001"
                vm_switch_name = V_SWITCH_DEGVMQ_NAME_DEF
                manager_vm_switch_name = V_SWITCH_MANAGER_NAME_DEF
                if vm_switch_name not in CommonOperation.get_vm_switch_name(
                        execute_address=CmdExecuteAdressEnum.SERVER.value):
                    VmSwitch.new_vmswitch(vmswitch_name=vm_switch_name, adapter_name=device_name_server,
                                          enable_iov=CommonOperation.get_degvmq_mode_value(VMSWITCH_SRIOV),
                                          execute_address=CmdExecuteAdressEnum.SERVER.value)
                VmAdapter.connect_vmnetworkadapter(vm_name=vm_name, manager_vmswitch_name=manager_vm_switch_name,
                                                   vmswitch_name=vm_switch_name,
                                                   execute_address=CmdExecuteAdressEnum.SERVER.value)

                if status:
                    # 若check_vm_stats执行成功 ，但vm未启动，则再启动一次
                    if "Off" == VmOp.get_vm_running_state(vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value):
                        VmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
                        VmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
            elif caller_class.server_test_object == TestObjectType.VFVMQ.value:
                # 获取配置文件中虚拟机名称
                vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                # 检查虚拟机状态并配置为正确状态
                status, _ = CommonOperation.check_vm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                           execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                           virtual_mode=VirtualModeEnum.VMQ.value)
                log.info("vm status:{}".format(status))
                if not status:
                    log.error("check_vm_stats fail !")
                    return RtnStatusEnum.FAIL.value

                # 设置PF网卡VMQ enable
                from scripts.script_libs.windows_adapter_operation import SetAdapterOperation
                vmq_setting = {"Enabled": str(1)}
                set_adapter = SetAdapterOperation(device_name=device_name_server,
                                                  cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                  **vmq_setting
                                                  )
                rtn_code = set_adapter.set_adapter_vmq()

                # 设置PF网卡SRIOV disable
                sriov_setting = {"Enabled": str(0)}
                set_adapter = SetAdapterOperation(device_name=device_name_server,
                                                  cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                  **sriov_setting
                                                  )
                rtn_code = set_adapter.set_adapter_sriov()

                vm_name = "sxevm001"
                vm_switch_name = V_SWITCH_VMQ_NAME_DEF
                manager_vm_switch_name = V_SWITCH_MANAGER_NAME_DEF
                if vm_switch_name not in CommonOperation.get_vm_switch_name(
                        execute_address=CmdExecuteAdressEnum.SERVER.value):
                    VmSwitch.new_vmswitch(vmswitch_name=vm_switch_name, adapter_name=device_name_server,
                                          enable_iov=False,
                                          execute_address=CmdExecuteAdressEnum.SERVER.value)
                VmAdapter.connect_vmnetworkadapter(vm_name=vm_name, manager_vmswitch_name=manager_vm_switch_name,
                                                   vmswitch_name=vm_switch_name,
                                                   execute_address=CmdExecuteAdressEnum.SERVER.value)

                if status:
                    # 若check_vm_stats执行成功 ，但vm未启动，则再启动一次
                    if "Off" == VmOp.get_vm_running_state(vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value):
                        VmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
                        VmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
            elif caller_class.server_test_object == TestObjectType.VFVMQVLAN.value:
                # 获取配置文件中虚拟机名称
                vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                # 检查虚拟机状态并配置为正确状态
                status, _ = CommonOperation.check_vm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                           execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                           virtual_mode=VirtualModeEnum.VMQ.value)
                log.info("vm status:{}".format(status))
                if not status:
                    log.error("check_vm_stats fail !")
                    return RtnStatusEnum.FAIL.value

                vm_name = "sxevm001"
                vm_switch_name = V_SWITCH_VMQ_NAME_DEF
                manager_vm_switch_name = V_SWITCH_MANAGER_NAME_DEF
                if vm_switch_name not in CommonOperation.get_vm_switch_name(
                        execute_address=CmdExecuteAdressEnum.SERVER.value):
                    VmSwitch.new_vmswitch(vmswitch_name=vm_switch_name, adapter_name=device_name_server,
                                          enable_iov=True,
                                          execute_address=CmdExecuteAdressEnum.SERVER.value)
                VmAdapter.connect_vmnetworkadapter(vm_name=vm_name,
                                                   vmswitch_name=vm_switch_name,
                                                   manager_vmswitch_name=manager_vm_switch_name,
                                                   execute_address=CmdExecuteAdressEnum.SERVER.value)
                if status:
                    # 若check_vm_stats执行成功 ，但vm未启动，则再启动一次
                    if "Off" == VmOp.get_vm_running_state(vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value):
                        VmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
                        VmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
                VmAdapter.set_vmnetworkadapter_vlan(vm_name=vm_name, vlan_id="1",
                                                    vmswitch_name=vm_switch_name,
                                                    manager_vmswitch_name=manager_vm_switch_name,
                                                    execute_address=CmdExecuteAdressEnum.SERVER.value)
            else:
                pass
        if device_name_client and 'windows' in host_os_client and cls.is_renix_only() == False:
            from scripts.script_libs.windows_hyperv_manage_vm import VmSwitch, VmAdapter, VmOp
            if caller_class.client_test_object == TestObjectType.VF.value:
                # 获取配置文件中虚拟机名称
                vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                # 检查虚拟机状态并配置为正确状态
                status, _ = CommonOperation.check_vm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                           execute_address=CmdExecuteAdressEnum.CLIENT.value)
                log.info("vm status:{}".format(status))
                if not status:
                    log.error("check_vm_stats fail !")
                    return RtnStatusEnum.FAIL.value

                if V_SWITCH_SRIOV_NAME_DEF not in CommonOperation.get_vm_switch_name(
                        execute_address=CmdExecuteAdressEnum.CLIENT.value):
                    VmSwitch.new_vmswitch(vmswitch_name=V_SWITCH_SRIOV_NAME_DEF, adapter_name=device_name_client,
                                          enable_iov=True,
                                          execute_address=CmdExecuteAdressEnum.CLIENT.value)
                VmAdapter.connect_vmnetworkadapter(vm_name="sxevm001",
                                                   manager_vmswitch_name=V_SWITCH_MANAGER_NAME_DEF,
                                                   vmswitch_name=V_SWITCH_SRIOV_NAME_DEF,
                                                   execute_address=CmdExecuteAdressEnum.CLIENT.value)
                if status:
                    # 若check_vm_stats执行成功 ，但vm未启动，则再启动一次
                    if "Off" == VmOp.get_vm_running_state(vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value):
                        VmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        VmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
            elif caller_class.client_test_object == TestObjectType.VLAN.value:
                cmd = "set-NetAdapter -name '{}' -vlanid '{}' -confirm:$false".format(device_name_client, 1)
                status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                log.info("status:{}, out:{}, err:{}".format(status, out, err))
                cmd = "Get-NetAdapterAdvancedProperty -name '{}' | grep VLAN".format(device_name_client)
                status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                log.info("status:{}, out:{}, err:{}".format(status, out, err))
            elif caller_class.client_test_object == TestObjectType.MACVLAN.value:
                # 获取配置文件中虚拟机名称
                vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                # 检查虚拟机状态并配置为正确状态
                status, _ = CommonOperation.check_vm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                           execute_address=CmdExecuteAdressEnum.CLIENT.value)
                log.info("vm status:{}".format(status))
                if not status:
                    log.error("check_vm_stats fail !")
                    return RtnStatusEnum.FAIL.value

                if V_SWITCH_VMQ_NAME_DEF not in CommonOperation.get_vm_switch_name(
                        execute_address=CmdExecuteAdressEnum.CLIENT.value):
                    VmSwitch.new_vmswitch(vmswitch_name=V_SWITCH_VMQ_NAME_DEF, adapter_name=device_name_client,
                                          enable_iov=False,
                                          execute_address=CmdExecuteAdressEnum.CLIENT.value)
                VmAdapter.connect_vmnetworkadapter(vm_name="sxevm001",
                                                   vmswitch_name=V_SWITCH_VMQ_NAME_DEF,
                                                   manager_vmswitch_name=V_SWITCH_MANAGER_NAME_DEF,
                                                   execute_address=CmdExecuteAdressEnum.CLIENT.value)
                if status:
                    # 若check_vm_stats执行成功 ，但vm未启动，则再启动一次
                    if "Off" == VmOp.get_vm_running_state(vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value):
                        VmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        VmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
            elif caller_class.client_test_object == TestObjectType.VFVLAN.value:
                # 获取配置文件中虚拟机名称
                vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                # 检查虚拟机状态并配置为正确状态
                status, _ = CommonOperation.check_vm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                           execute_address=CmdExecuteAdressEnum.CLIENT.value)
                log.info("vm status:{}".format(status))
                if not status:
                    log.error("check_vm_stats fail !")
                    return RtnStatusEnum.FAIL.value

                if V_SWITCH_SRIOV_NAME_DEF not in CommonOperation.get_vm_switch_name(
                        execute_address=CmdExecuteAdressEnum.CLIENT.value):
                    VmSwitch.new_vmswitch(vmswitch_name=V_SWITCH_SRIOV_NAME_DEF, adapter_name=device_name_client,
                                          enable_iov=True,
                                          execute_address=CmdExecuteAdressEnum.CLIENT.value)
                VmAdapter.connect_vmnetworkadapter(vm_name="sxevm001",
                                                   vmswitch_name=V_SWITCH_SRIOV_NAME_DEF,
                                                   manager_vmswitch_name=V_SWITCH_MANAGER_NAME_DEF,
                                                   execute_address=CmdExecuteAdressEnum.CLIENT.value)
                if status:
                    # 若check_vm_stats执行成功 ，但vm未启动，则再启动一次
                    if "Off" == VmOp.get_vm_running_state(vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value):
                        VmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        VmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
                VmAdapter.set_vmnetworkadapter_vlan(vm_name="sxevm001", vlan_id="1",
                                                    vmswitch_name=V_SWITCH_SRIOV_NAME_DEF,
                                                    manager_vmswitch_name=V_SWITCH_MANAGER_NAME_DEF,
                                                    execute_address=CmdExecuteAdressEnum.CLIENT.value)
            elif caller_class.client_test_object == TestObjectType.DEGVMQ.value:
                # 获取配置文件中虚拟机名称
                vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                # 检查虚拟机状态并配置为正确状态
                status, _ = CommonOperation.check_vm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                           execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                           virtual_mode=VirtualModeEnum.DEGVMQ.value)
                log.info("vm status:{}".format(status))
                if not status:
                    log.error("check_vm_stats fail !")
                    return RtnStatusEnum.FAIL.value

                # 设置PF网卡VMQ enable
                from scripts.script_libs.windows_adapter_operation import SetAdapterOperation
                vmq_setting = {"Enabled": str(1)}
                set_adapter = SetAdapterOperation(device_name=device_name_client,
                                                  cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                  **vmq_setting
                                                  )
                rtn_code = set_adapter.set_adapter_vmq()

                # 设置PF网卡SRIOV
                if CommonOperation.get_degvmq_mode_value(PF_SRIOV):
                    sriov_setting = {"Enabled": str(1)}
                else:
                    sriov_setting = {"Enabled": str(0)}
                set_adapter = SetAdapterOperation(device_name=device_name_client,
                                                  cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                  **sriov_setting
                                                  )
                rtn_code = set_adapter.set_adapter_sriov()

                # 新建虚拟交换机
                vm_name = "sxevm001"
                vm_switch_name = V_SWITCH_DEGVMQ_NAME_DEF
                manager_vm_switch_name = V_SWITCH_MANAGER_NAME_DEF
                if vm_switch_name not in CommonOperation.get_vm_switch_name(
                        execute_address=CmdExecuteAdressEnum.CLIENT.value):
                    VmSwitch.new_vmswitch(vmswitch_name=vm_switch_name, adapter_name=device_name_client,
                                          enable_iov=CommonOperation.get_degvmq_mode_value(VMSWITCH_SRIOV),
                                          execute_address=CmdExecuteAdressEnum.CLIENT.value)
                VmAdapter.connect_vmnetworkadapter(vm_name=vm_name, manager_vmswitch_name=manager_vm_switch_name,
                                                   vmswitch_name=vm_switch_name,
                                                   execute_address=CmdExecuteAdressEnum.CLIENT.value)

                if status:
                    # 若check_vm_stats执行成功 ，但vm未启动，则再启动一次
                    if "Off" == VmOp.get_vm_running_state(vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value):
                        VmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        VmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
            elif caller_class.client_test_object == TestObjectType.VFVMQ.value:
                # 获取配置文件中虚拟机名称
                vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                # 检查虚拟机状态并配置为正确状态
                status, _ = CommonOperation.check_vm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                           execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                           virtual_mode=VirtualModeEnum.VMQ.value)
                log.info("vm status:{}".format(status))
                if not status:
                    log.error("check_vm_stats fail !")
                    return RtnStatusEnum.FAIL.value

                # 设置PF网卡VMQ enable
                from scripts.script_libs.windows_adapter_operation import SetAdapterOperation
                vmq_setting = {"Enabled": str(1)}
                set_adapter = SetAdapterOperation(device_name=device_name_client,
                                                  cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                  **vmq_setting
                                                  )
                rtn_code = set_adapter.set_adapter_vmq()

                # 设置PF网卡SRIOV disable
                sriov_setting = {"Enabled": str(0)}
                set_adapter = SetAdapterOperation(device_name=device_name_client,
                                                  cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                  **sriov_setting
                                                  )
                rtn_code = set_adapter.set_adapter_sriov()

                vm_name = "sxevm001"
                vm_switch_name = V_SWITCH_VMQ_NAME_DEF
                manager_vm_switch_name = V_SWITCH_MANAGER_NAME_DEF
                if vm_switch_name not in CommonOperation.get_vm_switch_name(
                        execute_address=CmdExecuteAdressEnum.CLIENT.value):
                    VmSwitch.new_vmswitch(vmswitch_name=vm_switch_name, adapter_name=device_name_client,
                                          enable_iov=False,
                                          execute_address=CmdExecuteAdressEnum.CLIENT.value)
                VmAdapter.connect_vmnetworkadapter(vm_name=vm_name, manager_vmswitch_name=manager_vm_switch_name,
                                                   vmswitch_name=vm_switch_name,
                                                   execute_address=CmdExecuteAdressEnum.CLIENT.value)

                if status:
                    # 若check_vm_stats执行成功 ，但vm未启动，则再启动一次
                    if "Off" == VmOp.get_vm_running_state(vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value):
                        VmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        VmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
            elif caller_class.client_test_object == TestObjectType.VFVMQVLAN.value:
                # 获取配置文件中虚拟机名称
                vm_name = CommonOperation.get_conf_vm_name(execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.set_vm_name(vm_name, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                # 检查虚拟机状态并配置为正确状态
                status, _ = CommonOperation.check_vm_stats(CommonOperation.get_vm_name(), collect_info=False,
                                                           execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                           virtual_mode=VirtualModeEnum.VMQ.value)
                log.info("vm status:{}".format(status))
                if not status:
                    log.error("check_vm_stats fail !")
                    return RtnStatusEnum.FAIL.value

                vm_name = "sxevm001"
                vm_switch_name = V_SWITCH_VMQ_NAME_DEF
                manager_vm_switch_name = V_SWITCH_MANAGER_NAME_DEF
                if vm_switch_name not in CommonOperation.get_vm_switch_name(
                        execute_address=CmdExecuteAdressEnum.CLIENT.value):
                    VmSwitch.new_vmswitch(vmswitch_name=vm_switch_name, adapter_name=device_name_client,
                                          enable_iov=True,
                                          execute_address=CmdExecuteAdressEnum.CLIENT.value)
                VmAdapter.connect_vmnetworkadapter(vm_name=vm_name,
                                                   vmswitch_name=vm_switch_name,
                                                   manager_vmswitch_name=manager_vm_switch_name,
                                                   execute_address=CmdExecuteAdressEnum.CLIENT.value)
                if status:
                    # 若check_vm_stats执行成功 ，但vm未启动，则再启动一次
                    if "Off" == VmOp.get_vm_running_state(vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value):
                        VmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
                        VmOp.wait_vm_init_complete(vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
                VmAdapter.set_vmnetworkadapter_vlan(vm_name=vm_name, vlan_id="1",
                                                    vmswitch_name=vm_switch_name,
                                                    manager_vmswitch_name=manager_vm_switch_name,
                                                    execute_address=CmdExecuteAdressEnum.CLIENT.value)
            else:
                pass

    @classmethod
    def post_test_device_after_run_script(cls, caller_class, device_name_client: str = '',
                                          device_name_server: str = '',
                                          init_info_dict: dict = None, test_info_dict: dict = None) -> None:
        """
        非PF测试，可以直接调用此接口，根据基类需要，可以完成
            1.基于PF的vf创建
            2.基于PF/VF的vlan创建
            3.基于PF/VF的macvlan创建，其中macvlan默认bridge模式
        :param caller_class: 调用类
        :param device_name_client: client端PF子接口名称，如ens1f0
        :param device_name_server: server端PF子接口名称，如ens1f0
        :return:
        """
        from scripts.script_libs.ip_operation import IpOperation
        host_os_server, host_os_client = cls.get_nic_os()
        guest_os_server, guest_os_client = cls.get_guest_os(caller_class.test_direction_reverse)
        server_driver_name, client_driver_name = cls.get_nic_driver_name()
        server_vf_driver_name, client_vf_driver_name = cls.get_nic_vf_driver_name()
        # linux
        if device_name_client and (('windows' not in host_os_client) and (
                'windows' not in guest_os_client)) and cls.is_renix_only() == False:
            if caller_class.client_test_object == TestObjectType.VLAN.value:
                IpOperation.delete_vlan(vlan_name=test_info_dict["client_device_name"],
                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.client_added_ip = ""
            elif caller_class.client_test_object == TestObjectType.DVLAN.value:
                vlan_name = '.'.join(test_info_dict["client_device_name"].split('.')[:-1])
                IpOperation.delete_vlan(vlan_name=vlan_name,
                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.client_added_ip = ""
            elif caller_class.client_test_object == TestObjectType.MACVLAN.value:
                IpOperation.delete_macvlan(macvlan_name=test_info_dict["client_device_name"],
                                           cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.client_added_ip = ""
            elif caller_class.client_test_object == TestObjectType.VF.value or \
                    caller_class.client_test_object == TestObjectType.VFMACVLAN.value:
                CommonOperation.generate_vf_device(
                    pf_device_name=test_info_dict["client_pf_device_name"],
                    vf_num=0,
                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.rmmod_driver(driver_name=client_vf_driver_name,
                                             cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.client_added_ip = ""
            elif caller_class.client_test_object == TestObjectType.VFVLAN.value:
                # 删除vlan
                IpOperation.delete_vlan(vlan_name=test_info_dict["client_device_name"],
                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                # 删除vf
                CommonOperation.generate_vf_device(
                    pf_device_name=test_info_dict["client_pf_device_name"],
                    vf_num=0,
                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.rmmod_driver(driver_name=client_vf_driver_name,
                                             cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.client_added_ip = ""
            elif caller_class.client_test_object == TestObjectType.VFDVLAN.value:
                # 删除vlan
                vlan_name = '.'.join(test_info_dict["client_device_name"].split('.')[:-1])
                IpOperation.delete_vlan(vlan_name=vlan_name,
                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                # 删除vf
                CommonOperation.generate_vf_device(
                    pf_device_name=test_info_dict["client_pf_device_name"],
                    vf_num=0,
                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.rmmod_driver(driver_name=client_vf_driver_name,
                                             cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.client_added_ip = ""
            elif caller_class.client_test_object == TestObjectType.BOND1.value:
                # 删除bond
                bond_name = 'bond0m1'
                exec_addr = CmdExecuteAdressEnum.CLIENT.value
                server_devices, client_devices = cls.get_nic_relationships()
                for device in client_devices:
                    if device == device_name_client:
                        master_device = device
                        break
                client_devices.remove(master_device)
                slave_device = client_devices[0]

                IpOperation.delete_bond(bond_name=bond_name,
                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                        pf_name=master_device,
                                        backup_pf_name=slave_device)
                CommonOperation.client_added_ip = ""
            elif caller_class.client_test_object == TestObjectType.BOND2.value:
                # 删除bond
                bond_name = 'bond0m2'
                exec_addr = CmdExecuteAdressEnum.CLIENT.value
                server_devices, client_devices = cls.get_nic_relationships()
                for device in client_devices:
                    if device == device_name_client:
                        master_device = device
                        break
                client_devices.remove(master_device)
                slave_device = client_devices[0]

                IpOperation.delete_bond(bond_name=bond_name,
                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                        pf_name=master_device,
                                        backup_pf_name=slave_device)
                CommonOperation.client_added_ip = ""
            elif caller_class.client_test_object == TestObjectType.BOND4.value:
                # 删除bond
                bond_name = 'bond0m4'
                exec_addr = CmdExecuteAdressEnum.CLIENT.value
                server_devices, client_devices = cls.get_nic_relationships()
                for device in client_devices:
                    if device == device_name_client:
                        master_device = device
                        break
                client_devices.remove(master_device)
                slave_device = client_devices[0]

                IpOperation.delete_bond(bond_name=bond_name,
                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                        pf_name=master_device,
                                        backup_pf_name=slave_device)
                CommonOperation.client_added_ip = ""
        # linux
        if device_name_server and (('windows' not in host_os_server) and ('windows' not in guest_os_server)):
            if caller_class.server_test_object == TestObjectType.VLAN.value:
                IpOperation.delete_vlan(vlan_name=test_info_dict["server_device_name"],
                                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.server_added_ip = ""
            elif caller_class.server_test_object == TestObjectType.DVLAN.value:
                vlan_name = '.'.join(test_info_dict["server_device_name"].split('.')[:-1])
                IpOperation.delete_vlan(vlan_name=vlan_name,
                                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.server_added_ip = ""
            elif caller_class.server_test_object == TestObjectType.MACVLAN.value:
                IpOperation.delete_macvlan(macvlan_name=test_info_dict["server_device_name"],
                                           cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.server_added_ip = ""
            elif caller_class.server_test_object == TestObjectType.VF.value or \
                    caller_class.server_test_object == TestObjectType.VFMACVLAN.value:
                CommonOperation.generate_vf_device(
                    pf_device_name=test_info_dict['server_pf_device_name'],
                    vf_num=0,
                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.rmmod_driver(driver_name=server_vf_driver_name,
                                             cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.server_added_ip = ""
            elif caller_class.server_test_object == TestObjectType.VFVLAN.value:
                # 删除vlan
                IpOperation.delete_vlan(vlan_name=test_info_dict["server_device_name"],
                                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                # 删除vf
                CommonOperation.generate_vf_device(
                    pf_device_name=test_info_dict["server_pf_device_name"],
                    vf_num=0,
                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.rmmod_driver(driver_name=server_vf_driver_name,
                                             cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.server_added_ip = ""
            elif caller_class.server_test_object == TestObjectType.VFDVLAN.value:
                # 删除vlan
                vlan_name = '.'.join(test_info_dict["server_device_name"].split('.')[:-1])
                IpOperation.delete_vlan(vlan_name=vlan_name,
                                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                # 删除vf
                CommonOperation.generate_vf_device(
                    pf_device_name=test_info_dict["server_pf_device_name"],
                    vf_num=0,
                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.rmmod_driver(driver_name=server_vf_driver_name,
                                             cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.server_added_ip = ""
            elif caller_class.server_test_object == TestObjectType.BOND1.value:
                # 删除bond
                bond_name = 'bond0m1'
                exec_addr = CmdExecuteAdressEnum.SERVER.value
                server_devices, server_devices = cls.get_nic_relationships()
                for device in server_devices:
                    if device == device_name_server:
                        master_device = device
                        break
                server_devices.remove(master_device)
                slave_device = server_devices[0]

                IpOperation.delete_bond(bond_name=bond_name,
                                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                        pf_name=master_device,
                                        backup_pf_name=slave_device)
                CommonOperation.server_added_ip = ""
            elif caller_class.server_test_object == TestObjectType.BOND2.value:
                # 删除bond
                bond_name = 'bond0m2'
                exec_addr = CmdExecuteAdressEnum.SERVER.value
                server_devices, server_devices = cls.get_nic_relationships()
                for device in server_devices:
                    if device == device_name_server:
                        master_device = device
                        break
                server_devices.remove(master_device)
                slave_device = server_devices[0]

                IpOperation.delete_bond(bond_name=bond_name,
                                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                        pf_name=master_device,
                                        backup_pf_name=slave_device)
                CommonOperation.server_added_ip = ""
            elif caller_class.server_test_object == TestObjectType.BOND4.value:
                # 删除bond
                bond_name = 'bond0m4'
                exec_addr = CmdExecuteAdressEnum.SERVER.value
                server_devices, server_devices = cls.get_nic_relationships()
                for device in server_devices:
                    if device == device_name_server:
                        master_device = device
                        break
                server_devices.remove(master_device)
                slave_device = server_devices[0]

                IpOperation.delete_bond(bond_name=bond_name,
                                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                        pf_name=master_device,
                                        backup_pf_name=slave_device)
                CommonOperation.server_added_ip = ""

        # kvm windows
        if device_name_client and (('windows' not in host_os_client) and (
                'windows' in guest_os_client)) and cls.is_renix_only() == False:
            if caller_class.client_test_object == TestObjectType.VLAN.value:
                IpOperation.delete_vlan(vlan_name=test_info_dict["client_device_name"],
                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.client_added_ip = ""
            elif caller_class.client_test_object == TestObjectType.MACVLAN.value:
                IpOperation.delete_macvlan(macvlan_name=test_info_dict["client_device_name"],
                                           cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.client_added_ip = ""
            elif caller_class.client_test_object == TestObjectType.VF.value or \
                    caller_class.client_test_object == TestObjectType.VFVLAN.value or \
                    caller_class.client_test_object == TestObjectType.VFDVLAN.value or \
                    caller_class.client_test_object == TestObjectType.VFMACVLAN.value:
                CommonOperation.generate_vf_device(
                    pf_device_name=test_info_dict['client_pf_device_name'],
                    vf_num=0,
                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.rmmod_driver(driver_name=client_vf_driver_name,
                                             cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                CommonOperation.client_added_ip = ""

        # kvm windows
        if device_name_server and (('windows' not in host_os_server) and ('windows' in guest_os_server)):
            if caller_class.server_test_object == TestObjectType.VLAN.value:
                IpOperation.delete_vlan(vlan_name=test_info_dict["server_device_name"],
                                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.server_added_ip = ""
            elif caller_class.server_test_object == TestObjectType.MACVLAN.value:
                IpOperation.delete_macvlan(macvlan_name=test_info_dict["server_device_name"],
                                           cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.server_added_ip = ""
            elif caller_class.server_test_object == TestObjectType.VF.value or \
                    caller_class.server_test_object == TestObjectType.VFVLAN.value or \
                    caller_class.server_test_object == TestObjectType.VFDVLAN.value or \
                    caller_class.server_test_object == TestObjectType.VFMACVLAN.value:
                CommonOperation.generate_vf_device(
                    pf_device_name=test_info_dict['server_pf_device_name'],
                    vf_num=0,
                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.rmmod_driver(driver_name=server_vf_driver_name,
                                             cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                CommonOperation.server_added_ip = ""

        # windows
        if device_name_server and (('windows' in host_os_server) and ('windows' in guest_os_server)):
            from scripts.script_libs.windows_hyperv_manage_vm import VmSwitch, VmAdapter, VmOp
            if caller_class.server_test_object == TestObjectType.VF.value:
                VmAdapter.disconnect_vmnetworkadapter(vm_name="sxevm001", vmswitch_name=V_SWITCH_SRIOV_NAME_DEF,
                                                      vadapter_name=V_ADAPTER_TEST_NAME_DEF,
                                                      execute_address=CmdExecuteAdressEnum.SERVER.value)
                VmSwitch.remove_vmswitch(vmswitch_name=V_SWITCH_SRIOV_NAME_DEF,
                                         execute_address=CmdExecuteAdressEnum.SERVER.value)
                # 还原pf ip
                IpOperation.add_ip_addr(init_info_dict['server_device_name'],
                                        init_info_dict['server_device_ip'], CmdExecuteAdressEnum.SERVER.value)
                IpOperation.add_ip_addr(init_info_dict['server_device_name'],
                                        init_info_dict['server_device_ipv6'], CmdExecuteAdressEnum.SERVER.value,
                                        address_family="IPv6")
            elif caller_class.server_test_object == TestObjectType.VLAN.value:
                cmd = "set-NetAdapter -name '{}' -vlanid '{}' -confirm:$false".format(device_name_server, 0)
                status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                log.info("status:{}, out:{}, err:{}".format(status, out, err))
                cmd = "Get-NetAdapterAdvancedProperty -name '{}' | findstr /i VLAN".format(device_name_server)
                status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                log.info("status:{}, out:{}, err:{}".format(status, out, err))
            elif caller_class.server_test_object == TestObjectType.MACVLAN.value:
                VmAdapter.disconnect_vmnetworkadapter(vm_name="sxevm001",
                                                      manager_vmswitch_name=V_SWITCH_MANAGER_NAME_DEF,
                                                      vmswitch_name=V_SWITCH_VMQ_NAME_DEF,
                                                      execute_address=CmdExecuteAdressEnum.SERVER.value)
                VmSwitch.remove_vmswitch(vmswitch_name=V_SWITCH_VMQ_NAME_DEF,
                                         execute_address=CmdExecuteAdressEnum.SERVER.value)
            elif caller_class.server_test_object == TestObjectType.VFVLAN.value:
                VmAdapter.set_vmnetworkadapter_vlan(vm_name="sxevm001", vlan_id="0",
                                                    vmswitch_name=V_SWITCH_SRIOV_NAME_DEF,
                                                    manager_vmswitch_name=V_SWITCH_MANAGER_NAME_DEF,
                                                    execute_address=CmdExecuteAdressEnum.SERVER.value)
                VmAdapter.disconnect_vmnetworkadapter(vm_name="sxevm001", vmswitch_name=V_SWITCH_SRIOV_NAME_DEF,
                                                      vadapter_name=V_ADAPTER_TEST_NAME_DEF,
                                                      execute_address=CmdExecuteAdressEnum.SERVER.value)
                VmSwitch.remove_vmswitch(vmswitch_name=V_SWITCH_SRIOV_NAME_DEF,
                                         execute_address=CmdExecuteAdressEnum.SERVER.value)
            elif caller_class.server_test_object == TestObjectType.DEGVMQ.value:
                vm_name = "sxevm001"
                vmswitch_name = V_SWITCH_DEGVMQ_NAME_DEF
                vadapter_name = V_ADAPTER_TEST_NAME_DEF
                VmAdapter.disconnect_vmnetworkadapter(vm_name=vm_name, vmswitch_name=vmswitch_name,
                                                      vadapter_name=vadapter_name,
                                                      execute_address=CmdExecuteAdressEnum.SERVER.value)
                VmSwitch.remove_vmswitch(vmswitch_name=vmswitch_name,
                                         execute_address=CmdExecuteAdressEnum.SERVER.value)

                # 设置PF网卡VMQ enable
                from scripts.script_libs.windows_adapter_operation import SetAdapterOperation
                vmq_setting = {"Enabled": str(1)}
                set_adapter = SetAdapterOperation(device_name=init_info_dict['server_device_name'],
                                                  cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                  **vmq_setting
                                                  )
                rtn_code = set_adapter.set_adapter_vmq()

                # 设置PF网卡SRIOV enable
                sriov_setting = {"Enabled": str(1)}
                set_adapter = SetAdapterOperation(device_name=init_info_dict['server_device_name'],
                                                  cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                  **sriov_setting
                                                  )
                rtn_code = set_adapter.set_adapter_sriov()

                # 还原pf ip
                IpOperation.add_ip_addr(init_info_dict['server_device_name'],
                                        init_info_dict['server_device_ip'], CmdExecuteAdressEnum.SERVER.value)
                IpOperation.add_ip_addr(init_info_dict['server_device_name'],
                                        init_info_dict['server_device_ipv6'], CmdExecuteAdressEnum.SERVER.value,
                                        address_family="IPv6")
            elif caller_class.server_test_object == TestObjectType.VFVMQ.value:
                vm_name = "sxevm001"
                vmswitch_name = V_SWITCH_VMQ_NAME_DEF
                vadapter_name = V_ADAPTER_TEST_NAME_DEF
                VmAdapter.disconnect_vmnetworkadapter(vm_name=vm_name, vmswitch_name=vmswitch_name,
                                                      vadapter_name=vadapter_name,
                                                      execute_address=CmdExecuteAdressEnum.SERVER.value)
                VmSwitch.remove_vmswitch(vmswitch_name=vmswitch_name,
                                         execute_address=CmdExecuteAdressEnum.SERVER.value)

                # 设置PF网卡VMQ enable
                from scripts.script_libs.windows_adapter_operation import SetAdapterOperation
                vmq_setting = {"Enabled": str(1)}
                set_adapter = SetAdapterOperation(device_name=init_info_dict['server_device_name'],
                                                  cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                  **vmq_setting
                                                  )
                rtn_code = set_adapter.set_adapter_vmq()

                # 设置PF网卡SRIOV enable
                sriov_setting = {"Enabled": str(1)}
                set_adapter = SetAdapterOperation(device_name=init_info_dict['server_device_name'],
                                                  cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                  **sriov_setting
                                                  )
                rtn_code = set_adapter.set_adapter_sriov()

                # 还原pf ip
                IpOperation.add_ip_addr(init_info_dict['server_device_name'],
                                        init_info_dict['server_device_ip'], CmdExecuteAdressEnum.SERVER.value)
                IpOperation.add_ip_addr(init_info_dict['server_device_name'],
                                        init_info_dict['server_device_ipv6'], CmdExecuteAdressEnum.SERVER.value,
                                        address_family="IPv6")
            elif caller_class.server_test_object == TestObjectType.VFVMQVLAN.value:
                vm_name = "sxevm001"
                vmswitch_name = V_SWITCH_VMQ_NAME_DEF
                manager_vmswitch_name = V_SWITCH_MANAGER_NAME_DEF
                vadapter_name = V_ADAPTER_TEST_NAME_DEF
                VmAdapter.set_vmnetworkadapter_vlan(vm_name=vm_name, vlan_id="0",
                                                    vmswitch_name=vmswitch_name,
                                                    manager_vmswitch_name=manager_vmswitch_name,
                                                    execute_address=CmdExecuteAdressEnum.SERVER.value)
                VmAdapter.disconnect_vmnetworkadapter(vm_name=vm_name, vmswitch_name=vmswitch_name,
                                                      vadapter_name=vadapter_name,
                                                      execute_address=CmdExecuteAdressEnum.SERVER.value)
                VmSwitch.remove_vmswitch(vmswitch_name=vmswitch_name,
                                         execute_address=CmdExecuteAdressEnum.SERVER.value)
            else:
                pass
            # # todo 清理虚拟机（暂不开放）
            # if "vf" in caller_class.server_test_object:
            #     vm_name = constants.VM_NAME_DEF
            #     log.info('step-post1: 虚拟机内部，卸载网卡设备;')
            #     VmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
            #     time.sleep(5)
            #   VmAdapter.uninstall_vm_adapter(vm_name=vm_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            #     log.info('step-post3: 关闭虚拟机;')
            #     VmOp.stop_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
            #     CommonOperation.concat_test_steps('step-post4: PF侧，移除所有虚拟机网卡适配器;')
            #     VmAdapter.remove_vmnetworkadapter(vm_name=vm_name)
            #     CommonOperation.concat_test_steps('step-post5: 移除所有虚拟交换机;')
            #     VmSwitch.remove_vmswitch(vmswitch_name=constants.V_SWITCH_MANAGER_NAME_DEF,
            #                              execute_address=CmdExecuteAdressEnum.SERVER.value)
            #     CommonOperation.concat_test_steps('step-post6: 重启PF网卡，并重新配置ip，掩码，以及网卡名;')
            #     from scripts.script_libs.windows_adapter_operation import AdapterDataTool
            #     windows_adapt_data_tool_obj = AdapterDataTool(cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            #     windows_adapt_data_tool_obj.vm_name = None
            #     windows_adapt_data_tool_obj.virtual_ip = None
            #     windows_adapt_data_tool_obj.cmd_execute_address = CmdExecuteAdressEnum.SERVER.value
            #     adapter_ip = {init_info_dict["server_device_ip"]: "24"}
            #     windows_adapt_data_tool_obj.restart_driver(device_name=init_info_dict["server_device_name"],
            #                                                adapter_ip=adapter_ip)

        # windows
        if device_name_client and (
                ('windows' in host_os_client) and ('windows' in guest_os_client)) and cls.is_renix_only() == False:
            from scripts.script_libs.windows_hyperv_manage_vm import VmSwitch, VmAdapter, VmOp
            if caller_class.client_test_object == TestObjectType.VF.value:
                VmAdapter.disconnect_vmnetworkadapter(vm_name="sxevm001", vmswitch_name=V_SWITCH_SRIOV_NAME_DEF,
                                                      vadapter_name=V_ADAPTER_TEST_NAME_DEF,
                                                      execute_address=CmdExecuteAdressEnum.CLIENT.value)
                VmSwitch.remove_vmswitch(vmswitch_name=V_SWITCH_SRIOV_NAME_DEF,
                                         execute_address=CmdExecuteAdressEnum.CLIENT.value)
                # 还原pf ip
                IpOperation.add_ip_addr(init_info_dict['client_device_name'],
                                        init_info_dict['client_device_ip'], CmdExecuteAdressEnum.CLIENT.value)
                IpOperation.add_ip_addr(init_info_dict['client_device_name'],
                                        init_info_dict['client_device_ipv6'], CmdExecuteAdressEnum.CLIENT.value,
                                        address_family="IPv6")
            elif caller_class.client_test_object == TestObjectType.VLAN.value:
                cmd = "set-NetAdapter -name '{}' -vlanid '{}' -confirm:$false".format(device_name_client, 0)
                status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                log.info("status:{}, out:{}, err:{}".format(status, out, err))
                cmd = "Get-NetAdapterAdvancedProperty -name '{}' | findstr /i VLAN".format(device_name_client)
                status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                log.info("status:{}, out:{}, err:{}".format(status, out, err))
            elif caller_class.client_test_object == TestObjectType.MACVLAN.value:
                VmAdapter.disconnect_vmnetworkadapter(vm_name="sxevm001",
                                                      manager_vmswitch_name=V_SWITCH_MANAGER_NAME_DEF,
                                                      vmswitch_name=V_SWITCH_VMQ_NAME_DEF,
                                                      execute_address=CmdExecuteAdressEnum.CLIENT.value)
                VmSwitch.remove_vmswitch(vmswitch_name=V_SWITCH_VMQ_NAME_DEF,
                                         execute_address=CmdExecuteAdressEnum.CLIENT.value)
            elif caller_class.client_test_object == TestObjectType.VFVLAN.value:
                VmAdapter.set_vmnetworkadapter_vlan(vm_name="sxevm001", vlan_id="0",
                                                    vmswitch_name=V_SWITCH_SRIOV_NAME_DEF,
                                                    manager_vmswitch_name=V_SWITCH_MANAGER_NAME_DEF,
                                                    execute_address=CmdExecuteAdressEnum.CLIENT.value)
                VmAdapter.disconnect_vmnetworkadapter(vm_name="sxevm001", vmswitch_name=V_SWITCH_SRIOV_NAME_DEF,
                                                      vadapter_name=V_ADAPTER_TEST_NAME_DEF,
                                                      execute_address=CmdExecuteAdressEnum.CLIENT.value)
                VmSwitch.remove_vmswitch(vmswitch_name=V_SWITCH_SRIOV_NAME_DEF,
                                         execute_address=CmdExecuteAdressEnum.CLIENT.value)
            elif caller_class.client_test_object == TestObjectType.DEGVMQ.value:
                vm_name = "sxevm001"
                vmswitch_name = V_SWITCH_VMQ_NAME_DEF
                vadapter_name = V_ADAPTER_TEST_NAME_DEF
                VmAdapter.disconnect_vmnetworkadapter(vm_name=vm_name, vmswitch_name=vmswitch_name,
                                                      vadapter_name=vadapter_name,
                                                      execute_address=CmdExecuteAdressEnum.CLIENT.value)
                VmSwitch.remove_vmswitch(vmswitch_name=vmswitch_name,
                                         execute_address=CmdExecuteAdressEnum.CLIENT.value)

                # 设置PF网卡VMQ enable
                from scripts.script_libs.windows_adapter_operation import SetAdapterOperation
                vmq_setting = {"Enabled": str(1)}
                set_adapter = SetAdapterOperation(device_name=init_info_dict['client_device_name'],
                                                  cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                  **vmq_setting
                                                  )
                rtn_code = set_adapter.set_adapter_vmq()

                # 设置PF网卡SRIOV enable
                sriov_setting = {"Enabled": str(1)}
                set_adapter = SetAdapterOperation(device_name=init_info_dict['client_device_name'],
                                                  cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                  **sriov_setting
                                                  )
                rtn_code = set_adapter.set_adapter_sriov()

                # 还原pf ip
                IpOperation.add_ip_addr(init_info_dict['client_device_name'],
                                        init_info_dict['client_device_ip'], CmdExecuteAdressEnum.CLIENT.value)
                IpOperation.add_ip_addr(init_info_dict['client_device_name'],
                                        init_info_dict['client_device_ipv6'], CmdExecuteAdressEnum.CLIENT.value,
                                        address_family="IPv6")
            elif caller_class.client_test_object == TestObjectType.VFVMQ.value:
                vm_name = "sxevm001"
                vmswitch_name = V_SWITCH_VMQ_NAME_DEF
                vadapter_name = V_ADAPTER_TEST_NAME_DEF
                VmAdapter.disconnect_vmnetworkadapter(vm_name=vm_name, vmswitch_name=vmswitch_name,
                                                      vadapter_name=vadapter_name,
                                                      execute_address=CmdExecuteAdressEnum.CLIENT.value)
                VmSwitch.remove_vmswitch(vmswitch_name=vmswitch_name,
                                         execute_address=CmdExecuteAdressEnum.CLIENT.value)

                # 设置PF网卡VMQ enable
                from scripts.script_libs.windows_adapter_operation import SetAdapterOperation
                vmq_setting = {"Enabled": str(1)}
                set_adapter = SetAdapterOperation(device_name=init_info_dict['client_device_name'],
                                                  cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                  **vmq_setting
                                                  )
                rtn_code = set_adapter.set_adapter_vmq()

                # 设置PF网卡SRIOV disable
                sriov_setting = {"Enabled": str(1)}
                set_adapter = SetAdapterOperation(device_name=init_info_dict['client_device_name'],
                                                  cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                  **sriov_setting
                                                  )
                rtn_code = set_adapter.set_adapter_sriov()

                # 还原pf ip
                IpOperation.add_ip_addr(init_info_dict['client_device_name'],
                                        init_info_dict['client_device_ip'], CmdExecuteAdressEnum.CLIENT.value)
                IpOperation.add_ip_addr(init_info_dict['client_device_name'],
                                        init_info_dict['client_device_ipv6'], CmdExecuteAdressEnum.CLIENT.value,
                                        address_family="IPv6")
            elif caller_class.client_test_object == TestObjectType.VFVMQVLAN.value:
                vm_name = "sxevm001"
                vmswitch_name = V_SWITCH_VMQ_NAME_DEF
                manager_vmswitch_name = V_SWITCH_MANAGER_NAME_DEF
                vadapter_name = V_ADAPTER_TEST_NAME_DEF
                VmAdapter.set_vmnetworkadapter_vlan(vm_name=vm_name, vlan_id="0",
                                                    vmswitch_name=vmswitch_name,
                                                    manager_vmswitch_name=manager_vmswitch_name,
                                                    execute_address=CmdExecuteAdressEnum.CLIENT.value)
                VmAdapter.disconnect_vmnetworkadapter(vm_name=vm_name, vmswitch_name=vmswitch_name,
                                                      vadapter_name=vadapter_name,
                                                      execute_address=CmdExecuteAdressEnum.CLIENT.value)
                VmSwitch.remove_vmswitch(vmswitch_name=vmswitch_name,
                                         execute_address=CmdExecuteAdressEnum.CLIENT.value)
            else:
                pass
            # # todo 清理虚拟机（暂不开放）
            # if "vf" in caller_class.client_test_object:
            #     vm_name = constants.VM_NAME_DEF
            #     log.info('step-post1: 虚拟机内部，卸载网卡设备;')
            #     VmOp.start_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
            #     time.sleep(5)
            #   VmAdapter.uninstall_vm_adapter(vm_name=vm_name, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
            #     log.info('step-post3: 关闭虚拟机;')
            #     VmOp.stop_vm(vm_name=vm_name, execute_address=CmdExecuteAdressEnum.CLIENT.value)
            #     CommonOperation.concat_test_steps('step-post4: PF侧，移除所有虚拟机网卡适配器;')
            #     VmAdapter.remove_vmnetworkadapter(vm_name=vm_name)
            #     CommonOperation.concat_test_steps('step-post5: 移除所有虚拟交换机;')
            #     VmSwitch.remove_vmswitch(vmswitch_name=constants.V_SWITCH_MANAGER_NAME_DEF,
            #                              execute_address=CmdExecuteAdressEnum.CLIENT.value)
            #     CommonOperation.concat_test_steps('step-post6: 重启PF网卡，并重新配置ip，掩码，以及网卡名;')
            #     from scripts.script_libs.windows_adapter_operation import AdapterDataTool
            #     windows_adapt_data_tool_obj = AdapterDataTool(cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
            #     windows_adapt_data_tool_obj.vm_name = None
            #     windows_adapt_data_tool_obj.virtual_ip = None
            #     windows_adapt_data_tool_obj.cmd_execute_address = CmdExecuteAdressEnum.CLIENT.value
            #     adapter_ip = {init_info_dict["client_device_ip"]: "24"}
            #     windows_adapt_data_tool_obj.restart_driver(device_name=init_info_dict["client_device_name"],
            #                                                adapter_ip=adapter_ip)

        # 删除添加的ip
        if test_info_dict:
            server_win_vm_ip = test_info_dict.get('server_win_vm_ip', None)
            client_win_vm_ip = test_info_dict.get('client_win_vm_ip', None)
        else:
            server_win_vm_ip = None
            client_win_vm_ip = None
        if CommonOperation.server_added_ip:
            IpOperation.del_ip_addr(CommonOperation.server_added_ip[0], CommonOperation.server_added_ip[1],
                                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                    recover_ip=init_info_dict['server_device_ip'],
                                    win_vm_ip=server_win_vm_ip)
        # 删除添加的ip
        if CommonOperation.client_added_ip and cls.is_renix_only() == False:
            IpOperation.del_ip_addr(CommonOperation.client_added_ip[0], CommonOperation.client_added_ip[1],
                                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                    recover_ip=init_info_dict['client_device_ip'],
                                    win_vm_ip=client_win_vm_ip)

    @classmethod
    def generate_ipv6_header(cls, pf_device_name: str, target_device_type, cmd_execute_address: str, offset=0) -> str:
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
            elif target_device_type == TestObjectType.DVLAN.value:
                diff = diff_base + 8
            elif target_device_type == TestObjectType.VFDVLAN.value:
                diff = diff_base + 9
            else:
                diff = diff_base + 10

            diff += offset

            temp_list[-2] = "{:04x}".format(diff)
            ip_header = ':'.join(temp_list[:-1]) + ':'
        else:
            ip_header = "fe80::0000:0000:0000:"
            log.warning("当前未获取到ipv6地址，给默认值：{}，仅仅是为了不报异常。".format(ip_header))
        return ip_header

    @classmethod
    def generate_ip_header(cls, pf_device_name: str, target_device_type, cmd_execute_address: str,
                           offset: int = 0) -> str:
        pf_device_ip = IfConfig.get_device_ipv4_addr(device_name=pf_device_name,
                                                     cmd_execute_address=cmd_execute_address)
        if pf_device_ip is None:
            log.error(f'{cmd_execute_address}：获取{pf_device_name} ip失败')
            return ''
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
        elif target_device_type == TestObjectType.DVLAN.value:
            diff = diff_base + 8
        elif target_device_type == TestObjectType.VFDVLAN.value:
            diff = diff_base + 9
        elif target_device_type == TestObjectType.BOND1.value:
            diff = diff_base + 11
        elif target_device_type == TestObjectType.BOND2.value:
            diff = diff_base + 12
        elif target_device_type == TestObjectType.BOND4.value:
            diff = diff_base + 13
        else:
            diff = diff_base + 10

        diff += offset

        temp_list[2] = str(int(temp_list[2]) + diff)
        ip_header = '.'.join(temp_list[:-1]) + '.'
        return ip_header

    @classmethod
    def modprobe_driver(cls, driver_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                        **kwargs) -> bool:
        """
        加载网卡VF/PF驱动
        :param driver_path: 驱动路径
        :param cmd_execute_address:
        :return:
        """
        nicg = cls.get_nic_generation()
        host_os_server, host_os_client = cls.get_nic_os()
        run_mode_need_ko = True
        log.info(f"kwargs:{kwargs.items()}")
        for key, value in kwargs.items():
            if key == "run_mode" and value in [RunModeEnum.RUN_MODE_WITH_SRC.value,
                                               RunModeEnum.RUN_MODE_WITH_RPM.value,
                                               RunModeEnum.RUN_MODE_WITH_SRPM.value,
                                               RunModeEnum.RUN_MODE_WITH_KMOD_SRPM.value]:
                run_mode_need_ko = False
                break

        if cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and 'windows' in host_os_client:
            return True
        elif cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and 'windows' in host_os_server:
            return True
        else:
            server_driver_name, client_driver_name = cls.get_nic_driver_name()
            # 测试网卡测试阶段，驱动不会放在内核下，需要insmod命令
            if not run_mode_need_ko or CommandLineArgsParse.get_test_object() in [RunModeEnum.RUN_MODE_WITH_SRC.value,
                                                                              RunModeEnum.RUN_MODE_WITH_RPM.value,
                                                                              RunModeEnum.RUN_MODE_WITH_SRPM.value,
                                                                              RunModeEnum.RUN_MODE_WITH_KMOD_SRPM.value]:
                use_ko = False
            else:
                use_ko = True

            com_mode_set_key = ""

            if cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and use_ko:
                command = f'insmod /root/{nicg}_auxiliary.ko'
                rtn_code, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=command, cmd_execute_address=cmd_execute_address)

                command = f'insmod /root/{driver_name}.ko'
                if kwargs:
                    para = ''
                    for key, value in kwargs.items():
                        log.info(f"key:{key}, value:{value}")
                        if key == "debugfs_com_mode":
                            com_mode_set_key = key
                        elif key == "run_mode":
                            pass
                        else:
                            if isinstance(value, dict):
                                for ikey, ivalue in value.items():
                                    para += str(ikey) + '=' + str(ivalue) + ' '
                            else:
                                para += str(key) + '=' + str(value) + ' '
                                if key == "drv_mode":
                                    com_mode_set_key = key

                    command = command + ' ' + para
            elif cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and use_ko:
                command = f'insmod /root/{nicg}_auxiliary.ko'
                rtn_code, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=command, cmd_execute_address=cmd_execute_address)

                command = f'insmod /root/{driver_name}.ko'
                if kwargs:
                    para = ''
                    for key, value in kwargs.items():
                        if key == "debugfs_com_mode":
                            com_mode_set_key = key
                        elif key == "run_mode":
                            pass
                        else:
                            if isinstance(value, dict):
                                for ikey, ivalue in value.items():
                                    para += str(ikey) + '=' + str(ivalue) + ' '
                            else:
                                para += str(key) + '=' + str(value) + ' '
                                if key == "drv_mode":
                                    com_mode_set_key = key

                    command = command + ' ' + para
            elif not kwargs:
                command = f'modprobe {driver_name}'
            else:
                para = ''
                for key, value in kwargs.items():
                    if key == "debugfs_com_mode":
                        com_mode_set_key = key
                    elif key == "run_mode":
                        pass
                    else:
                        if isinstance(value, dict):
                            for ikey, ivalue in value.items():
                                para += str(ikey) + '=' + str(ivalue) + ' '
                        else:
                            para += str(key) + '=' + str(value) + ' '
                            if key == "drv_mode":
                                com_mode_set_key = key
                command = f'modprobe {driver_name} {para}'
            log.info(f"command:{command}")

            log.info(f"com_mode_set_key:{com_mode_set_key},driver_name:{driver_name}")
            use_func_config = True
            if driver_name in [NicNameEnum.SXE2.value, NicNameEnum.SXE2VF.value]:
                if driver_name in [NicNameEnum.SXE2.value]:
                    com_mode = cls.get_once_com_mode("pf", cmd_execute_address)
                    if com_mode < PFSwitchMode.MAX.value:
                        use_func_config = False
                else:
                    com_mode = cls.get_once_com_mode("vf", cmd_execute_address)
                    if com_mode < VFSwitchMode.MAX.value:
                        use_func_config = False

            need_change_com_mode = False
            # 0:仅内核，1：仅dpdk， 2：共存，10:0-1-2-0...，11:1-2-0-1...，12:2-1-0-2...
            # 如果debugfs_com_mode传过来，说明前面已经配置过了，这里就不用重新配置
            log.info(f"com_mode_set_key:{com_mode_set_key}")
            # 如果com_mode_set_key为com_mode，是旧的模式，不处理
            # 如果com_mode_set_key是debugfs_com_mode，是新模式，但是前面已经进行过配置，此处仅需进行加卸载动作
            # 如果没有传参，则需要根据once_com_mode进行配置
            if (com_mode_set_key != "debugfs_com_mode") and driver_name in [NicNameEnum.SXE2.value] and use_func_config:
                need_change_com_mode = True

            # need_change_com_mode = False
            log.info(f"need_change_com_mode: {need_change_com_mode}")
            rtn_code = RtnStatusEnum.SUCCESS.value
            for com_state in [0, 1]:
                if com_state == 0:
                    rtn_code, rtn_outputs, rtn_err = \
                        CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=command, cmd_execute_address=cmd_execute_address)
                    if not use_func_config and driver_name in [NicNameEnum.SXE2.value]:
                        cmd = f"ls /sys/kernel/debug/{driver_name}/ | grep ':'"
                        rtn_code1, rtn_outputs1, rtn_err1 = \
                            CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd,
                                                                        cmd_execute_address=cmd_execute_address)
                        pf_bdfs = rtn_outputs1.split("\n")
                        need_reload_driver = False
                        for index, bdf in enumerate(pf_bdfs):
                            cmd = f"cat /sys/kernel/debug/{driver_name}/{bdf}/drv_mode"
                            rtn_code1, rtn_outputs1, rtn_err1 = \
                                CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd,
                                                                            cmd_execute_address=cmd_execute_address)
                            if "undefined" not in rtn_outputs1:
                                cmd = f"echo undefined > /sys/kernel/debug/{driver_name}/{bdf}/drv_mode"
                                rtn_code1, rtn_outputs1, rtn_err1 = \
                                    CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd,
                                                                                cmd_execute_address=cmd_execute_address)
                                need_reload_driver = True
                        if need_reload_driver:
                            rtn_code1, rtn_outputs1, rtn_err1 = \
                                CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=f"rmmod {driver_name}",
                                                                            cmd_execute_address=cmd_execute_address)
                            rtn_code, rtn_outputs, rtn_err = \
                                CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=command,
                                                                            cmd_execute_address=cmd_execute_address)

                            cmd = f"cat /sys/module/{driver_name}/parameters/drv_mode"
                            rtn_code1, rtn_outputs1, rtn_err1 = \
                                CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd,
                                                                            cmd_execute_address=cmd_execute_address)
                            for index, bdf in enumerate(pf_bdfs):
                                cmd = f"cat /sys/kernel/debug/{driver_name}/{bdf}/drv_mode"
                                rtn_code1, rtn_outputs1, rtn_err1 = \
                                    CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd,
                                                                                cmd_execute_address=cmd_execute_address)

                elif com_state == 1 and need_change_com_mode and driver_name in [NicNameEnum.SXE2.value]:
                    default_com_mode = cls.get_com_mode("pf", cmd_execute_address)
                    com_mode = cls.get_once_com_mode("pf", cmd_execute_address)
                    log.info(f"default_com_mode:{default_com_mode}, com_mode:{com_mode}")
                    time.sleep(1)
                    cmd = f"ls /sys/kernel/debug/{driver_name}/ | grep ':'"
                    rtn_code1, rtn_outputs1, rtn_err1 = \
                        CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd,
                                                                    cmd_execute_address=cmd_execute_address)
                    pf_bdfs = rtn_outputs1.split("\n")
                    # 0:仅内核，1：仅dpdk， 2：共存，10:0-2-0...，11:2-0-2...，12:0-2-0...，
                    log.info(
                        f"com_mode:{com_mode}, driver_name:{driver_name}, cmd_execute_address:{cmd_execute_address}, pf_bdfs:{pf_bdfs}")
                    com_mode_list = cls.create_com_mode_list("pf", com_mode, len(pf_bdfs))
                    log.info(f"com_mode_list:{com_mode_list}")
                    need_reload_driver = False
                    for index, bdf in enumerate(pf_bdfs):
                        cmd = f"cat /sys/kernel/debug/{driver_name}/{bdf}/drv_mode"
                        rtn_code1, rtn_outputs1, rtn_err1 = \
                            CommandOperation.execute_command_with_error(cmd=cmd,
                                                                        cmd_execute_address=cmd_execute_address)
                        if f"current mode:{com_mode_list[index]}" not in rtn_outputs1:
                            cmd = f"echo {com_mode_list[index]} > /sys/kernel/debug/{driver_name}/{bdf}/drv_mode"
                            rtn_code1, rtn_outputs1, rtn_err1 = \
                                CommandOperation.execute_command_with_error(cmd=cmd,
                                                                            cmd_execute_address=cmd_execute_address)
                            cmd = f"cat /sys/kernel/debug/{driver_name}/{bdf}/drv_mode"
                            rtn_code1, rtn_outputs1, rtn_err1 = \
                                CommandOperation.execute_command_with_error(cmd=cmd,
                                                                            cmd_execute_address=cmd_execute_address)
                            need_reload_driver = True
                    if need_reload_driver:
                        rtn_code1, rtn_outputs1, rtn_err1 = \
                            CommandOperation.execute_command_with_error(cmd=f"rmmod {driver_name}",
                                                                        cmd_execute_address=cmd_execute_address)
                        rtn_code, rtn_outputs, rtn_err = \
                            CommandOperation.execute_command_with_error(cmd=command,
                                                                        cmd_execute_address=cmd_execute_address)

                        for index, bdf in enumerate(pf_bdfs):
                            cmd = f"cat /sys/kernel/debug/{driver_name}/{bdf}/drv_mode"
                            rtn_code1, rtn_outputs1, rtn_err1 = \
                                CommandOperation.execute_command_with_error(cmd=cmd,
                                                                            cmd_execute_address=cmd_execute_address)

                    com_mode = cls.get_com_mode("pf", cmd_execute_address)
                    cls.set_once_com_mode("pf", com_mode, cmd_execute_address)

            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info("驱动加载后，等待3s，防止出现概率性网口还未UP就去操作问题")
                time.sleep(3)
                _, os_info, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd='cat /etc/os-release', cmd_execute_address=cmd_execute_address, print_outputs=False)
                # log.info(f'当前os信息: {rtn_outputs}')
                if 'linx' in os_info.lower():
                    log.info("当前系统为Linx, 重新加载驱动后需要启动网卡")
                    _, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd='systemctl restart networking', cmd_execute_address=cmd_execute_address)
                    # log.info(f'执行命令: , 标准输出: {rtn_outputs}, 错误输出: {rtn_err}')
                    time.sleep(2)

                if "ubuntu" in os_info.lower():
                    log.info("当前系统为ubuntu需要重新ifconfig up")
                    server_relation_list, client_relation_list = CommonOperation.get_nic_relationships()
                    for index, device_name in enumerate(server_relation_list):
                        if cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                            cmd = "ifconfig {} up".format(device_name)
                        else:
                            cmd = "netplan apply"
                        _, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, cmd_execute_address=cmd_execute_address)
                return True
            elif "could not insert module" in rtn_err and "File exists" in rtn_err:
                log.info("驱动已存在")
                return True
            else:
                return False

    @classmethod
    def generate_vf_device(cls, pf_device_name: str, vf_num: int,
                           cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, bus_info: str = None,
                           cleanup_ktest_resource: bool = True) -> bool:
        """
        对应PF下生成一定数量的VF pci设备
        :param pf_device_name: PF设备名，如ens1f0
        :param vf_num: VF数量
        :param cmd_execute_address: 命令执行位置
        :param bus_info
        :return:
        """
        if (CommandLineArgsParse.get_test_entry() == TestEntryEnum.VF_KEEP_MODE.value and
                cmd_execute_address==CmdExecuteAdressEnum.SERVER.value):
            log.warning("========> vf_keep_mode server端禁止创建删除vf，不进行操作！")
            return True

        vf_need_change_name = False
        server_nic_driver, client_nic_driver = cls.get_nic_driver_name()
        server_vf_nic_driver, client_vf_nic_driver = cls.get_nic_vf_driver_name()
        fpga_bitfile_class = cls.get_fpga_bitfile_class()

        # rdma内核态测试，删除vf前清理资源
        if cleanup_ktest_resource:
            nicg = cls.get_nic_generation()
            if fpga_bitfile_class in [FpgaBitfileClass['C'], FpgaBitfileClass['K'], FpgaBitfileClass['L'], FpgaBitfileClass['M']]:
                exec_command = f'lsmod|grep -w {nicg}_ktest'
                rtn_code, rtn_res, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, cmd_execute_address=cmd_execute_address)
                # 内核态测试 且 删除vf
                if rtn_res and (vf_num==0):
                    utest_dir = f'/opt/tools/netlink/{nicg}_utest'
                    log.info(f'清理{nicg}_ktest的资源')
                    cmd = f'{utest_dir} "cleanup" 54'
                    rtn_code, rtn_res, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=cmd, cmd_execute_address=cmd_execute_address)

        # # server是scgbe且echo 0，client是scgbe且echo 0，则不执行
        # if (server_nic_driver in [NicNameEnum.SXE2.value, NicNameEnum.SCGBE.value] and vf_num == 0 and
        #     cmd_execute_address == CmdExecuteAdressEnum.SERVER.value) or\
        #         (client_nic_driver in [NicNameEnum.SXE2.value, NicNameEnum.SCGBE.value] and vf_num == 0 and
        #          cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value):
        #     log.warning(f"当前是驱动 = {server_nic_driver} vf_num = 0 时, 不执行")
        #     return True
        exec_command = 'cat /etc/os-release'
        rtn_code, os_info, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        exec_command = 'cat /etc/redhat-release'
        rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if ("CentOS" in rtn_outputs or "Red Hat" in rtn_outputs) and "release 7." in rtn_outputs:
            log.warning("当前os版本是CentOS或Red Hat 7.x，vf创建后需改名pfdevicename+vx")
            vf_need_change_name = True
        elif (cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and server_nic_driver in [
            NicNameEnum.CX6.value]) or \
                (cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and client_nic_driver in [
                    NicNameEnum.CX6.value, NicNameEnum.MLX5_IB.value]):
            log.warning("当前为cx6网卡，vf创建后需改名pfdevicename+vx")
            vf_need_change_name = True
        else:
            if "Kylin".lower() in os_info.lower():
                log.warning("当前os版本是Kylin，vf创建后需改名pfdevicename+vx")
                vf_need_change_name = True
            elif 'Linx' in os_info and 'jessie' in os_info:
                log.warning("当前os版本是Linx 8，vf创建后需要改名pfdevicename+vx")
                vf_need_change_name = True
            elif 'openEuler 24.03' in os_info:
                log.warning("当前os版本是openEuler 24.03，vf创建后需要改名pfdevicename+vx")
                vf_need_change_name = True
            elif 'NFS' in os_info:
                log.warning("当前os版本是NFS，vf创建后需要改名pfdevicename+vx")
                vf_need_change_name = True
            elif 'Anolis' in os_info:
                log.warning("当前os版本是Anolis，vf创建后需要改名pfdevicename+vx")
                vf_need_change_name = True
            else:
                log.info("当前os无需更改vf名称")
            # if "UnionTech OS Server" in rtn_outputs:
            #     log.warning("当前os版本是UOS，vf创建后需改名pfdevicename+vx")
            #     vf_need_change_name = True
        driver_name = server_nic_driver
        vf_driver_name = server_vf_nic_driver
        if cmd_execute_address == CmdExecuteAdressEnum.SERVER.value:
            exec_command_server = 'lsmod | grep {}'.format(server_vf_nic_driver)
            _, rtn_outputs_server1, rtn_err_server= CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command_server, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            exec_command_server = 'rpm -qa | grep {}'.format(server_vf_nic_driver)
            _, rtn_outputs_server2, rtn_err_server = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command_server, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            # 安装vf rpm不创建vf时不会主动加载驱动，需要创建时才加载，此处避免影响rpm测试而去主动insmod vf ko
            if not rtn_outputs_server1 and not rtn_outputs_server2:
                driver_flag_server = cls.modprobe_driver(server_vf_nic_driver,
                                                         cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            driver_name = server_nic_driver
            vf_driver_name = server_vf_nic_driver
        elif cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
            exec_command_client = 'lsmod | grep {}'.format(client_vf_nic_driver)
            _, rtn_outputs_server, rtn_err_server= CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command_client, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
            if not rtn_outputs_server:
                driver_flag_client = cls.modprobe_driver(client_vf_nic_driver,
                                                         cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
            driver_name = client_nic_driver
            vf_driver_name = client_vf_nic_driver
        if vf_num:
            # echo 非0值之前，若已存在vf，则返回错误
            if cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                exec_command_client = 'ifconfig -a'
                _, rtn_outputs_client, rtn_err_client= CommandOperation.execute_command_based_paramiko_with_rtncode(
                    exec_command_client, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                if f'{pf_device_name}v' in rtn_outputs_client:
                    log.warning(f"已存在{pf_device_name}的vf设备，不再执行vf创建")
                    return True
            elif cmd_execute_address == CmdExecuteAdressEnum.SERVER.value:
                exec_command_server = 'ifconfig -a'
                _, rtn_outputs_server, rtn_err_server= CommandOperation.execute_command_based_paramiko_with_rtncode(
                    exec_command_server, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                if f'{pf_device_name}v' in rtn_outputs_server:
                    log.warning(f"已存在{pf_device_name}的vf设备，不再执行vf创建")
                    return True

        result_dict = {}
        if not bus_info:
            result_dict = EthtoolOperation.show_driver_infomation(device_name=pf_device_name,
                                                                  cmd_execute_address=cmd_execute_address)
        else:
            result_dict["bus-info"] = bus_info

        start_timestamp, start_time = CommandOperation.get_time()
        all_device_name_list_before = []
        if result_dict.get('bus-info'):
            pci_num = result_dict['bus-info']
            if vf_num:
                # 获取当前网口列表
                all_device_name_list_before = IfConfig.get_all_device_name(cmd_execute_address=cmd_execute_address)
                log.info(f"all_device_name_list_before:{all_device_name_list_before}")
            need_change_com_mode = False
            com_mode = cls.get_once_com_mode("vf", cmd_execute_address)
            # com_mode = cls.get_com_mode("vf", cmd_execute_address)
            # 0:仅内核，1：仅dpdk， 2：共存，10:0-1-2-0...，11:1-2-0-1...，12:2-1-0-2...
            log.info(
                f"com_mode:{com_mode}, server_vf_nic_driver:{server_vf_nic_driver}, cmd_execute_address:{cmd_execute_address}, vf_num:{vf_num}")
            # vf默认用于是2
            if com_mode != 2 and com_mode > VFSwitchMode.MAX.value and server_vf_nic_driver in [NicNameEnum.SXE2VF.value] and vf_num:
                need_change_com_mode = True
            log.info(f"need_change_com_mode:{need_change_com_mode}")
            for com_state in [0, 1]:
                if com_state == 0:
                    command = f'echo {vf_num} > /sys/bus/pci/devices/{pci_num}/sriov_numvfs'
                    rtn_code, outputs, err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=cmd_execute_address, timeout=600)

                    if "Device or resource busy" in outputs + err:
                        wait_time = 30
                        command = f'dmesg | grep "pf ready" | wc -l'
                        rtn_code, outputs, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=command, cmd_execute_address=cmd_execute_address, timeout=600)
                        before = int(outputs)
                        while wait_time:
                            time.sleep(3)
                            command = f"echo 'pf state' > /sys/kernel/debug/{driver_name}/{pci_num}/command"
                            rtn_code, outputs, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=command, cmd_execute_address=cmd_execute_address, timeout=600)
                            command = f'dmesg | grep "pf ready" | wc -l'
                            rtn_code, outputs, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=command, cmd_execute_address=cmd_execute_address, timeout=600)
                            after = int(outputs)
                            if after > before:
                                log.info("pf ready,可以创建vf了")
                                break
                            wait_time -= 1
                        command = f'echo {vf_num} > /sys/bus/pci/devices/{pci_num}/sriov_numvfs'
                        rtn_code, outputs, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=command, cmd_execute_address=cmd_execute_address, timeout=600)
                        if rtn_code != RtnStatusEnum.SUCCESS.value:
                            return False

                    if vf_driver_name in [constants.VF_DRIVER_SXE2]:
                        command = f"cat /sys/module/{constants.VF_DRIVER_SXE2}/parameters/drv_mode"
                        rtn_code, outputs, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=command, cmd_execute_address=cmd_execute_address, timeout=600)

                        if not need_change_com_mode and outputs.isdigit() and com_mode % 10 != int(outputs):
                            cls.rmmod_driver(driver_name=vf_driver_name,
                                             cmd_execute_address=cmd_execute_address, force=True)
                            cls.modprobe_driver(vf_driver_name, cmd_execute_address=cmd_execute_address,
                                                drv_mode=com_mode % 10)
                elif com_state == 1 and need_change_com_mode:
                    # 创建完成后，需要将永久配置刷回
                    com_mode_list = cls.create_com_mode_list("vf", com_mode, vf_num)
                    log.info(f"com_mode_list:{com_mode_list}")
                    default_com_mode = cls.get_com_mode("vf", cmd_execute_address)
                    cls.set_once_com_mode("vf", default_com_mode, cmd_execute_address)

                    iretry = 150
                    vf_bdf_list = []
                    while iretry:
                        command = f"ls /sys/kernel/debug/{constants.PF_DRIVER_SCGBE}vf/ | grep ':'"
                        rtn_code, outputs, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=command, cmd_execute_address=cmd_execute_address, timeout=600)
                        vf_bdf_list = outputs.split("\n")
                        log.info(f"vf_bdf_list:{vf_bdf_list}")
                        iretry -= 1
                        time.sleep(3)
                        if len(vf_bdf_list) >= vf_num:
                            break

                    if len(vf_bdf_list) != vf_num:
                        log.error("创建vf数量不等于目标数量")
                    for index in range(vf_num):
                        vf_bdf = vf_bdf_list[index]
                        vf_com_mode = com_mode_list[index]
                        command = f"echo '{vf_com_mode}' > /sys/kernel/debug/{server_vf_nic_driver}/{vf_bdf}/drv_mode"
                        rtn_code, outputs, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=command, cmd_execute_address=cmd_execute_address, timeout=600)

                    cls.rmmod_driver(driver_name=vf_driver_name,
                                     cmd_execute_address=cmd_execute_address, force=True)
                    cls.modprobe_driver(vf_driver_name, cmd_execute_address=cmd_execute_address, debugfs_drv_mode=com_mode % 10)

                time.sleep(5)
                dev_increase_num = 0
                bdf_increase_num = 0
                all_device_name_list_after = []
                if vf_num:
                    # 获取新增网口列表
                    # 麒麟系统创建vf后，获取网口名称存在暂态，导致后续脚本出错
                    iretry = 150
                    while iretry:
                        time.sleep(3)
                        all_device_name_list_after = IfConfig.get_all_device_name(cmd_execute_address=cmd_execute_address)
                        log.info("all_device_name_list_after:{}".format(all_device_name_list_after))
                        dev_increase_num = len(set(all_device_name_list_after).difference(set(all_device_name_list_before)))

                        if vf_driver_name in [NicNameEnum.SXE2VF.value]:
                            get_vfbdf_cmd = f'ls /sys/kernel/debug/{vf_driver_name}/'
                            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=get_vfbdf_cmd, cmd_execute_address=cmd_execute_address)
                            all_vf_bdf_list = re.findall(r'([0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}.[0-9a-fA-F])', cmd_stdout)
                            log.info('all vf bdf: {}'.format(all_vf_bdf_list))
                            bdf_increase_num = len(all_vf_bdf_list)

                        if dev_increase_num >= vf_num:
                            break

                        if bdf_increase_num >= vf_num:
                            break
                        iretry -= 1

                    # 确认vf设备已不再更新
                    while True:
                        before_num = len(all_device_name_list_after)
                        time.sleep(5)
                        all_device_name_list_after = IfConfig.get_all_device_name(
                            cmd_execute_address=cmd_execute_address)
                        log.info("all_device_name_list_after:{}".format(all_device_name_list_after))
                        if before_num == len(all_device_name_list_after):
                            break

                    if vf_driver_name in [NicNameEnum.SXE2VF.value]:
                        if bdf_increase_num < vf_num:
                            log.error("新增的vf设备数量：{}小于创建数量：{}!!!".format(bdf_increase_num, vf_num))
                            return False
                    else:
                        if dev_increase_num < vf_num:
                            log.error("新增的vf设备数量：{}小于创建数量：{}!!!".format(bdf_increase_num, vf_num))
                            return False

                    if dev_increase_num and pf_device_name + "v0" not in all_device_name_list_after:
                        log.warning("新增vf名称未预期出现，判定是否存在对应pf下的vf设备")
                        have_flag = False
                        for device_name in all_device_name_list_after:
                            cmd = f"readlink -f /sys/class/net/{device_name}/device/physfn"
                            rtn_code, outputs, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=cmd, cmd_execute_address=cmd_execute_address)
                            if pci_num not in outputs or device_name == pf_device_name:
                                all_device_name_list_after.remove(device_name)
                            else:
                                have_flag = True

                        dev_increase_num = len(all_device_name_list_after)
                        if dev_increase_num < vf_num:
                            log.error("新增的以太vf设备数量：{}小于创建数量：{}!!!".format(dev_increase_num, vf_num))
                            return False

                        if have_flag:
                            log.warning("新增以太vf名称还是未预期出现，命名需要修改")
                            vf_need_change_name = True

                    if vf_need_change_name:
                        index = 0
                        for device_name in all_device_name_list_after:
                            if device_name not in all_device_name_list_before:
                                cmd = f"readlink -f /sys/class/net/{device_name}/device/physfn"
                                rtn_code, outputs, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=cmd, cmd_execute_address=cmd_execute_address)
                                if pci_num not in outputs:
                                    log.error("新增的设备：{}并不是当前pf：{}的vf，可能和相邻节点冲突了，判定创建vf失败!!!".format(device_name, pci_num))
                                    return False

                                # ovs 中 representer 设备不重命名
                                ovs_cmd = f'devlink -j dev eswitch show pci/{pci_num}'
                                rtn_code, outputs, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=ovs_cmd, cmd_execute_address=cmd_execute_address)
                                log.info(
                                    "command:{},rtn_code:{},outputs:{},err:{}".format(command, rtn_code, outputs,
                                                                                      err))
                                if 'switchdev' in outputs and 'nr' in device_name:
                                    log.warning(f'当前是 switch 模式, representer 设备不做重命名')
                                    continue
                                iretry = 10
                                while iretry:
                                    iretry -= 1
                                    command = f'ifconfig {device_name} down'
                                    rtn_code, outputs, err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                                        cmd=command, cmd_execute_address=cmd_execute_address)
                                    log.info(
                                        "command:{},rtn_code:{},outputs:{},err:{}".format(command, rtn_code, outputs,
                                                                                          err))
                                    if index >= vf_num:
                                        command = f'ip link set {device_name} name {pf_device_name}nr{index % vf_num}'
                                    else:
                                        command = f'ip link set {device_name} name {pf_device_name}v{index}'
                                    rtn_code, outputs, err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                                        cmd=command, cmd_execute_address=cmd_execute_address)
                                    log.info(
                                        "command:{},rtn_code:{},outputs:{},err:{}".format(command, rtn_code, outputs,
                                                                                          err))
                                    if rtn_code != RtnStatusEnum.SUCCESS.value:
                                        if iretry:
                                            log.warning("存在部分os成功ifconfig down后又被协议栈up，导致更名失败，添加重试")
                                            time.sleep(1)
                                        else:
                                            return False
                                    else:
                                        break
                                if index < vf_num:
                                    command = f'ifconfig {pf_device_name}v{index} up'
                                else:
                                    command = f'ifconfig {pf_device_name}nr{index % vf_num} up'
                                rtn_code, outputs, err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=command, cmd_execute_address=cmd_execute_address)
                                log.info(
                                    "command:{},rtn_code:{},outputs:{},err:{}".format(command, rtn_code, outputs, err))
                                if rtn_code != RtnStatusEnum.SUCCESS.value:
                                    return False
                                index += 1


                log.info(f"os_info: {os_info}")
                host_os_server, host_os_client = cls.get_nic_os()
                if (host_os_server == 'ubuntu' and cmd_execute_address == CmdExecuteAdressEnum.SERVER.value) or \
                        (host_os_client == 'ubuntu' and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value) or \
                        "ubuntu" in os_info.lower() or \
                        "opencloudos" in os_info.lower():
                    for dev in all_device_name_list_after:
                        log.info(f'特殊os需要执行vf up: {dev}')
                        # ubuntu系统创建完vf后，vf默认为down状态，此处适配需进行up
                        command = f'ip link set {dev} up'
                        rtn_code, outputs, err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=command, cmd_execute_address=cmd_execute_address)
                        log.info("command:{},rtn_code:{},outputs:{},err:{}".format(command, rtn_code, outputs, err))
                        if rtn_code != RtnStatusEnum.SUCCESS.value:
                            return False

        end_timestamp, end_time = CommandOperation.get_time()
        if vf_num == 0:
            if end_timestamp - start_timestamp > 120:
                cls.set_warn_message(f"在{start_time}-{end_time}删除vf，耗时{end_timestamp - start_timestamp}，时间偏长！可能是问题，请关注确认！")
        else:
            if end_timestamp - start_timestamp > 60 + vf_num * 10:
                cls.set_warn_message(f"在{start_time}-{end_time}创建{vf_num}个vf，耗时{end_timestamp - start_timestamp}，时间偏长！可能是问题，请关注确认！")
        return True


    @classmethod
    def vf_com_mode_config(cls, cmd_execute_address, server_vf_nic_driver, vf_num, force: int=False):
        need_change_com_mode = False
        com_mode = cls.get_once_com_mode("vf", cmd_execute_address)
        # 创建完成后，需要将永久配置刷回
        per_com_mode = cls.get_com_mode("vf", cmd_execute_address)
        cls.set_once_com_mode("vf", per_com_mode, cmd_execute_address)
        # 0:仅内核，1：仅dpdk， 2：共存，10:0-1-2-0...，11:1-2-0-1...，12:2-1-0-2...
        log.info(
            f"com_mode:{com_mode}, server_vf_nic_driver:{server_vf_nic_driver}, cmd_execute_address:{cmd_execute_address}, vf_num:{vf_num}")
        if (force or com_mode > VFSwitchMode.MAX.value) and server_vf_nic_driver in [NicNameEnum.SXE2VF.value] and vf_num:
            need_change_com_mode = True
        log.info(f"need_change_com_mode:{need_change_com_mode}")
        if need_change_com_mode:
            com_mode_list = cls.create_com_mode_list("vf", com_mode, vf_num)
            log.info(f"com_mode_list:{com_mode_list}")
            iretry = 20
            vf_bdf_list = []
            while iretry:
                time.sleep(3)
                command = f"ls /sys/kernel/debug/{constants.PF_DRIVER_SCGBE}vf/ | grep ':'"
                rtn_code, outputs, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=command, cmd_execute_address=cmd_execute_address, timeout=600)
                vf_bdf_list = outputs.split("\n")
                log.info(f"vf_bdf_list:{vf_bdf_list}")
                if len(vf_bdf_list) == vf_num:
                    break
                iretry -= 1
            if len(vf_bdf_list) != vf_num:
                log.error("创建vf数量不等于目标数量")
            else:
                for index in range(vf_num):
                    vf_bdf = vf_bdf_list[index]
                    vf_com_mode = com_mode_list[index]
                    command = f"echo '{vf_com_mode}' > /sys/kernel/debug/{server_vf_nic_driver}/{vf_bdf}/drv_mode"
                    rtn_code, outputs, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=cmd_execute_address, timeout=600)

                cls.rmmod_driver(driver_name=server_vf_nic_driver,
                                 cmd_execute_address=cmd_execute_address, force=True)
                cls.modprobe_driver(server_vf_nic_driver, cmd_execute_address=cmd_execute_address, debugfs_drv_mode=com_mode % 10)


    @classmethod
    def create_com_mode_list(cls, dev_type, com_mode, dev_num) -> list:
        """
        author: junfeng.he
        date: 2026.02.12
        description:
        0:仅内核，1：仅dpdk， 2：共存
        10:0-1-2-0...，11:1-2-0-1...，12:2-1-0-2...
        20:0-0-0-0...，21:1-1-1-1...，22:2-2-2-2...
        """
        if dev_type == "pf":
            mode_list = [ComModeStr.KERNEL.value, ComModeStr.COMMON.value]
        else:
            mode_list = [ComModeStr.KERNEL.value, ComModeStr.DPDK.value, ComModeStr.COMMON.value]
        com_mode_list = []
        if com_mode == 0 or com_mode == 20:
            for i in range(dev_num):
                com_mode_list.append(ComModeStr.KERNEL.value)
        elif com_mode == 1 or com_mode == 21:
            for i in range(dev_num):
                com_mode_list.append(ComModeStr.DPDK.value)
        elif com_mode == 2 or com_mode == 21:
            for i in range(dev_num):
                com_mode_list.append(ComModeStr.COMMON.value)
        elif com_mode == 10:
            for i in range(dev_num):
                com_mode_list.append(mode_list[(i+0)%len(mode_list)])
        elif com_mode == 11:
            for i in range(dev_num):
                com_mode_list.append(mode_list[(i+1)%len(mode_list)])
        elif com_mode == 12:
            for i in range(dev_num):
                com_mode_list.append(mode_list[(i+2)%len(mode_list)])
        return com_mode_list


    @classmethod
    def set_warn_message(cls, warn_message) -> None:
        """
        author: junfeng.he
        date: 2026.02.12
        description: 设置要告警的信息
        """
        log_default_path = os.path.join(ESAT_DIRECTORY, constants.LOG_DEFAULT_PATH_NAME)
        exec_command = f"echo '{warn_message}' >> {log_default_path}/warn_message"
        rtn_code, result = subprocess.getstatusoutput(exec_command)
        log.warning(f"【告警信息】==> {warn_message}")

    @classmethod
    def set_framework_log_check_ignore(cls) -> None:
        """
        author: junfeng.he
        date: 2026.03.11
        description: 设置忽略框架日志检查flag
        """
        log_default_path = os.path.join(ESAT_DIRECTORY, constants.LOG_DEFAULT_PATH_NAME)
        exec_command = f"echo 'ignore' > {log_default_path}/framework_log_check_ignore"
        rtn_code, result = subprocess.getstatusoutput(exec_command)
        log.warning(f"【设置忽略框架日志检查】")

    @classmethod
    def get_framework_log_check_ignore(cls) -> bool:
        """
        author: junfeng.he
        date: 2026.03.11
        description: 获取忽略框架日志检查flag
        """
        log_default_path = os.path.join(ESAT_DIRECTORY, constants.LOG_DEFAULT_PATH_NAME)
        exec_command = f"cat {log_default_path}/framework_log_check_ignore"
        rtn_code, result = subprocess.getstatusoutput(exec_command)
        log.info("获取忽略框架日志标识，rtn_code:{}, result:{}".format(rtn_code, result))
        if "ignore" in result and "framework_log_check_ignore" not in result:
            exec_command = f"echo 'none' > {log_default_path}/framework_log_check_ignore"
            subprocess.getstatusoutput(exec_command)
            log.warning(f"【清除忽略框架日志检查】")
            return True
        return False

    @classmethod
    def get_com_mode(cls, dev_type, cmd_execute_address: str=CmdExecuteAdressEnum.SERVER.value) -> int:
        """
        author: junfeng.he
        date: 2026.03.26
        description: 获取框架下发的com_mode
        """
        if cmd_execute_address == CmdExecuteAdressEnum.SERVER.value:
            mark = "server"
        else:
            mark = "client"

        log_default_path = os.path.join(ESAT_DIRECTORY, constants.LOG_DEFAULT_PATH_NAME)
        if dev_type == "pf":
            exec_command = f"cat {log_default_path}/pf_{mark}_com_mode"
        else:
            exec_command = f"cat {log_default_path}/vf_{mark}_com_mode"
        rtn_code, result = subprocess.getstatusoutput(exec_command)
        log.info(f"获取{dev_type}，exec_command:{exec_command}, rtn_code:{rtn_code}, result:{result}")
        if result.isdigit():
            return int(result)
        else:
            return 2

    @classmethod
    def set_com_mode(cls, dev_type, value, cmd_execute_address: str=CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author: junfeng.he
        date: 2026.03.26
        description: 获取框架下发的com_mode
        """
        if cmd_execute_address == CmdExecuteAdressEnum.SERVER.value:
            mark = "server"
        else:
            mark = "client"

        log_default_path = os.path.join(ESAT_DIRECTORY, constants.LOG_DEFAULT_PATH_NAME)
        if dev_type == "pf":
            exec_command = f"echo '{value}' > {log_default_path}/pf_{mark}_com_mode"
        else:
            exec_command = f"echo '{value}' > {log_default_path}/vf_{mark}_com_mode"
        rtn_code, result = subprocess.getstatusoutput(exec_command)
        log.info(f"设置{dev_type}，exec_command:{exec_command}, rtn_code:{rtn_code}, result:{result}")

    @classmethod
    def get_once_com_mode(cls, dev_type, cmd_execute_address: str=CmdExecuteAdressEnum.SERVER.value) -> int:
        """
        author: junfeng.he
        date: 2026.03.26
        description: 获取框架下发的com_mode
        """
        if cmd_execute_address == CmdExecuteAdressEnum.SERVER.value:
            mark = "server"
        else:
            mark = "client"

        log_default_path = os.path.join(ESAT_DIRECTORY, constants.LOG_DEFAULT_PATH_NAME)
        if dev_type == "pf":
            exec_command = f"cat {log_default_path}/pf_once_{mark}_com_mode"
        else:
            exec_command = f"cat {log_default_path}/vf_once_{mark}_com_mode"
        rtn_code, result = subprocess.getstatusoutput(exec_command)
        log.info(f"获取{dev_type}，exec_command:{exec_command}, rtn_code:{rtn_code}, result:{result}")
        if result.isdigit():
            return int(result)
        else:
            return 2

    @classmethod
    def set_once_com_mode(cls, dev_type, value, cmd_execute_address: str=CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author: junfeng.he
        date: 2026.03.26
        description: 获取框架下发的com_mode
        """
        if cmd_execute_address == CmdExecuteAdressEnum.SERVER.value:
            mark = "server"
        else:
            mark = "client"

        log_default_path = os.path.join(ESAT_DIRECTORY, constants.LOG_DEFAULT_PATH_NAME)
        if dev_type == "pf":
            exec_command = f"echo '{value}' > {log_default_path}/pf_once_{mark}_com_mode"
        else:
            exec_command = f"echo '{value}' > {log_default_path}/vf_once_{mark}_com_mode"
        rtn_code, result = subprocess.getstatusoutput(exec_command)
        log.info(f"设置{dev_type}，exec_command:{exec_command}, rtn_code:{rtn_code}, result:{result}")

    @classmethod
    def driver_mode_check_and_ready(cls, cmd_execute_address, driver_name, drv_mode):
        """
        # 融合判断,若是/root/sxe2.ko是融合版本，检查是否支持指定的DPDK模式，若不支持则重新加载驱动
        """
        if driver_name in [constants.PF_DRIVER_SXE2]:
            if drv_mode < PFSwitchMode.MAX.value:
                log.info(f"{cmd_execute_address}：pf融合架构,使用整卡级别drv_mode")
                exec_command = f"cat /sys/module/{constants.PF_DRIVER_SXE2}/parameters/drv_mode"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                    exec_command, cmd_execute_address=cmd_execute_address)
                log.info(f"当前：{rtn_outputs}，目标：{drv_mode}")
                if rtn_outputs.isdigit() and drv_mode % 10 != int(rtn_outputs):
                    CommonOperation.rmmod_driver(constants.PF_DRIVER_SXE2, cmd_execute_address, force=True)
                    CommonOperation.modprobe_driver(constants.PF_DRIVER_SXE2, cmd_execute_address,
                                                    drv_mode=drv_mode % 10)
                else:
                    log.info(f"{cmd_execute_address}：融合架构，未获取到pf drv_mode无需进行操作")
            else:
                log.info(f"{cmd_execute_address}：pf融合架构,使用func级别drv_mode")
                CommonOperation.set_once_com_mode("pf", drv_mode, cmd_execute_address)
                log.info(
                    f"{cmd_execute_address}：debugfs融合架构，pf配置改到创建动作中，此处不进行操作,后续驱动重新加载会处理")
                CommonOperation.modprobe_driver(constants.PF_DRIVER_SXE2, cmd_execute_address)

        if driver_name in [constants.VF_DRIVER_SXE2]:
            if drv_mode < VFSwitchMode.MAX.value:
                log.info(f"{cmd_execute_address}：vf融合架构,使用整卡级别drv_mode")
                exec_command = f"cat /sys/module/{constants.VF_DRIVER_SXE2}/parameters/drv_mode"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                    exec_command, cmd_execute_address=cmd_execute_address)
                log.info(f"当前：{rtn_outputs}，目标：{drv_mode}")
                if rtn_outputs.isdigit() and drv_mode % 10 != int(rtn_outputs):
                    CommonOperation.rmmod_driver(constants.VF_DRIVER_SXE2, cmd_execute_address, force=True)
                    CommonOperation.modprobe_driver(constants.VF_DRIVER_SXE2, cmd_execute_address,
                                                    drv_mode=drv_mode % 10)
                    CommonOperation.set_once_com_mode("vf", drv_mode, cmd_execute_address)
                    log.info(f"{cmd_execute_address}：融合架构，vf配置需要保持到创建vf时生效")
                else:
                    log.info(f"{cmd_execute_address}：融合架构，未获取到vf drv_mode无需进行操作")
            else:
                log.info(f"{cmd_execute_address}：vf融合架构,使用func级别drv_mode")
                CommonOperation.set_once_com_mode("vf", drv_mode, cmd_execute_address)
                log.info(f"{cmd_execute_address}：debugfs融合架构，vf配置改到创建动作中，此处不进行操作")

                exec_command = f"ls /sys/kernel/debug/{constants.PF_DRIVER_SXE2}/ | grep :"
                rtn_code2, rtn_outputs2, rtn_err2 = CommandOperation.execute_command_with_error(
                    exec_command, cmd_execute_address=cmd_execute_address)

                pf_bdfs = rtn_outputs2.split("\n")
                need_reload_vf = False
                vf_num = 0
                for pf_bdf in pf_bdfs:
                    command = f'cat /sys/bus/pci/devices/{pf_bdf}/sriov_numvfs'
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                        command, cmd_execute_address=cmd_execute_address)
                    if rtn_outputs.isdigit() and int(rtn_outputs):
                        need_reload_vf = True
                        vf_num += int(rtn_outputs)
                log.info(f"need_reload_vf:{need_reload_vf}, vf_num:{vf_num}")
                if need_reload_vf:
                    CommonOperation.vf_com_mode_config(cmd_execute_address, constants.VF_DRIVER_SXE2, vf_num,
                                                       force=True)

    @classmethod
    def get_device_vendor_device_id(cls, pci_address: str,
                                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value) -> Union[str, int]:
        """
        author: wei.yuan1
        date: 2022.10.20
        description: 获取网卡的vendor:device
        """
        exec_cmd = f"lspci -n -s {pci_address}"
        rtn_code, rtn_output, err= CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_cmd,
            cmd_execute_address=cmd_execute_address)
        log.info("exec_cmd:{},rtn_code:{},rtn_output:{},err:{}".format(exec_cmd, rtn_code, rtn_output, err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            vendor_device_temp = re.sub(u"\\(.*?\\)|\\<.*?\\>", "", rtn_output)
            vendor_device_id = vendor_device_temp.rstrip().split(" ")[-1]
            return vendor_device_id
        else:
            return rtn_code

    @classmethod
    def get_system_core_num(cls, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value):
        """
        author：wei.yuan1
        date: 2022.10.24
        description: 获取CPU的核数
        """
        system_cpu_dict = {}
        rtn_code, rtn_output, _= CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd="lscpu",
            cmd_execute_address=cmd_execute_address
        )
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            if 'CPU(s)' not in rtn_output and 'CPU' in rtn_output:
                rtn_output = rtn_output.replace("CPU", "CPU(s)")
            cpu_info = rtn_output.split("\n")
            for cpu_item in cpu_info:
                system_cpu_dict[cpu_item.split(":")[0]] = cpu_item.split(":")[1].strip()

        return system_cpu_dict

    @classmethod
    def interrupts_happen_num(cls, cpus_total: int, driver_name: str,
                              cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        """
        author: wei.yuan1
        date: 2022.10.24
        description: 获取中断发生的个数
        """
        cpu_irq_dict = {}
        cpus_total = int(cpus_total)
        exec_command = f"cat /proc/interrupts|grep {driver_name}"
        rtn_code, rtn_output, rtn_stderr= CommandOperation.execute_command_based_paramiko_with_rtncode(
            exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            split_output = rtn_output.split("\n")
            irq_list = []
            for index_output in split_output:
                index_output = re.sub(" +", " ", index_output)
                b_list = index_output.lstrip().split(" ")
                irq_list.append(b_list[1:cpus_total])
            a = [index for index in irq_list if index != []]
            cpu_irq = list(zip(*irq_list))
            for cpu_irq_index in range(len(cpu_irq)):
                cpu_irq_dict[f"CPU{cpu_irq_index}"] = set(cpu_irq[cpu_irq_index])
        return cpu_irq_dict

    @classmethod
    def get_now_time(cls) -> str:
        now = datetime.now().strftime('%Y-%m-%d;%H:%M:%S')
        return now

    @classmethod
    def analysis_skb_bin_file(cls, start_time, end_time,
                              cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> str:
        exec_command = """cat /root/sxe.bin* | awk '$0 >="[{}" && $0 <= "[{}"' """.format(start_time, end_time)
        rtn_code, outputs, err_code = CommandOperation.execute_command_based_paramiko_with_rtncode(
            exec_command, cmd_execute_address)
        linear_list, nonlinear_list = [], []
        outputs_list = outputs.split('\n')

        for line_num in range(len(outputs_list) - 1):
            if ' linear' in outputs_list[line_num] and 'nonlinear' in outputs_list[line_num + 1]:
                header_len = eval(outputs_list[line_num].split('size:')[1])
                data_len = eval(outputs_list[line_num + 1].split('size:')[1])
                line_num += 2
            elif ' linear' in outputs_list[line_num] and ' linear' in outputs_list[line_num + 1]:
                header_len = eval(outputs_list[line_num].split('size:')[1])
                data_len = 0
                line_num += 1
            elif ' linear' in outputs_list[line_num + 1]:
                header_len = eval(outputs_list[line_num].split('size:')[1])
                data_len = 0
            else:
                header_len = 0
                data_len = 0
            linear_list.append(header_len)
            nonlinear_list.append(data_len)

        import math

        seq = 0
        result_dict = {}
        for size_linear in linear_list:
            exec_command = """cat /root/sxe.bin* | grep -A {} \"{}\" | grep -v \"{}\""""
            result_dict[linear_list.index(size_linear)] = {}
            if nonlinear_list[linear_list.index(size_linear)] != 0:
                exec_command_line = exec_command.format(math.ceil(size_linear / 16),
                                                        outputs_list[seq].split('addr:')[1],
                                                        outputs_list[seq].split('addr:')[1])
                exec_command_nonline = exec_command.format(
                    math.ceil(nonlinear_list[linear_list.index(size_linear)] / 16),
                    (outputs_list[seq + 1].split('addr:')[1]),
                    outputs_list[seq + 1].split('addr:')[1])
                seq += 2
                a, outputs, b= CommandOperation.execute_command_based_paramiko_with_rtncode(exec_command_line, cmd_execute_address)
                temp_result = ''
                for item in outputs.split('\n'):
                    temp_result += item.split(':')[1].replace(',')
                result_dict[linear_list.index(size_linear)]['packet_header'] = temp_result
                _, outputs, _= CommandOperation.execute_command_based_paramiko_with_rtncode(exec_command_nonline,
                                                                            cmd_execute_address)
                temp_result = ''
                for item in outputs.split('\n'):
                    temp_result += item.split(':')[1].replace(',')
                result_dict[linear_list.index(size_linear)]['packet_data'] = temp_result

            else:
                exec_command.format(size_linear, outputs_list[seq])
                exec_command_line = exec_command.format(math.ceil(size_linear / 16),
                                                        outputs_list[seq].split('addr:')[1],
                                                        outputs_list[seq].split('addr:')[1])
                seq += 1
                _, outputs, _= CommandOperation.execute_command_based_paramiko_with_rtncode(exec_command_line, cmd_execute_address)
                temp_result = ''
                for item in outputs.split('\n'):
                    temp_result += item.split(':')[1].replace(',')
                result_dict[linear_list.index(size_linear)]['packet_header'] = temp_result
        print(result_dict)

    @classmethod
    def random_num_product(cls, length: int):
        """
        author: wei.yuan1
        date: 2022.10.29
        """
        import random
        result = hex(random.randint(0, 16 ** length - 1)).replace('0x', '').upper()
        if len(result) < length:
            result = '0' * (length - len(result)) + result
        return str(result).lower()

    @classmethod
    def write_register(cls, device_name: str, offset_address: hex, register_value: hex,
                       cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                       name_space: str = None) -> bool:
        """
        修改寄存器
        :param device_name: 网卡子接口名称
        :param offset_address: 寄存器偏移地址
        :param register_value: 寄存器改写值
        :param cmd_execute_address: 执行位置
        :return:
        """
        if name_space:
            exec_command = f'ip netns exec {name_space} ./mw {device_name} {str(hex(offset_address))} {str(hex(register_value))}'
            rtn_code, _, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=cmd_execute_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                return True
            else:
                log.info('本次修改寄存器失败')
                return False
        else:
            exec_command = f'./mw {device_name} {str(hex(offset_address))} {str(hex(register_value))}'
            rtn_code, _, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=cmd_execute_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                return True
            else:
                log.info('本次修改寄存器失败')
                return False

    @classmethod
    def get_base_address(cls, device_name: str, cmd_execute_address: CmdExecuteAdressEnum.CLIENT.value) -> hex:
        info_dict = EthtoolOperation.show_driver_infomation(device_name=device_name,
                                                            cmd_execute_address=cmd_execute_address)
        pci_addr = info_dict.get('bus-info')
        driver = info_dict.get('driver')
        # bus-info不为空，且是82599或sxe才去查基地址
        # if pci_addr and (
        #         NicNameEnum.INTEL_82599.value in driver or NicNameEnum.SXE.value in driver or NicNameEnum.E810):
        if pci_addr:
            rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd='lspci -vvs {}'.format(pci_addr), cmd_execute_address=cmd_execute_address)
            pattern = 'Region 0: \S*\s*Memory at (\S+)'
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                import re
                result = re.findall(pattern, rtn_outputs)
                cls.nic_base_address[device_name] = int(result[0], 16)
                return int(result[0], 16)
        return 0

    @classmethod
    def get_logical_cpu_num(cls, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, ssh_ip=None):
        """
        author：shaohui.wang
        date: 2023.03.09
        description: 获取逻辑cpu的个数
        """
        num = 0
        exec_command = 'cat /proc/cpuinfo| grep processor| wc -l'
        rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command,
            cmd_execute_address=cmd_execute_address,
            ssh_ip=ssh_ip
        )
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            num = int(rtn_outputs)
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        return num

    @classmethod
    def get_physical_cpu_num(cls, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value):
        """
        author：shaohui.wang
        date: 2023.03.09
        description: 获取物理cpu的个数
        """
        num = 0
        # 必须外面用双引号，里面用单引号
        exec_command = "cat /proc/cpuinfo| grep 'physical id'| sort| uniq| wc -l"
        rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command,
            cmd_execute_address=cmd_execute_address
        )
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            num = int(rtn_outputs)
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        return num

    @classmethod
    def get_core_num_per_physical_cpu(cls, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value):
        """
        author：shaohui.wang
        date: 2023.03.09
        description: 获取每个物理CPU中core的个数(即核数)
        """
        num = 0
        # 必须外面用双引号，里面用单引号
        exec_command = "cat /proc/cpuinfo| grep 'cpu cores'| uniq"
        rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command,
            cmd_execute_address=cmd_execute_address
        )
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            result = re.search(r'\d+', rtn_outputs)
            if result:
                num = int(result.group())
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        return num

    @classmethod
    def restart_network_service(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> int:
        """
        author: shaohui.wang
        date: 2023.03.14
        description: 重启网络服务
        """
        rtn_status = False
        exec_command = '/etc/init.d/network-manager restart'
        rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
            exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        return rtn_status

    @classmethod
    def get_sensitive_word(cls, key_word, execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author: junfeng.he
        date: 2023.10.11
        description: 根据驱动类型获取敏感词替换(key[ixgbe],value[sxe])
        """
        sdict = {
            "Flow Director": "Flow navigator",
            "fdir": "fnav",
            "Fdir": "Fnav",
            "FDIR": "FNAV",
            "fdir_match": "fnav_match",
            "fdir_miss": "fnav_miss",
            "fdir_overflow": "fnav_overflow",

            "Software-Definable Pins": "Software programmable pins",
            "SDP": "SPP",

            "Receive Side Coalescing": "Large Receive Offload",
            "RSC": "LRO",

            "Application Targeting Routing": "APP_TR",
            "ATR": "sample",

            "Externally Programmed Mode": "EPM",
            "EP": "specific",
        }

        server_nic_driver, client_nic_driver = cls.get_nic_driver_name()
        log.info("key_word:{}, execute_address:{}, server_driver:{}, client_driver:{}".format(
            key_word, execute_address, server_nic_driver, client_nic_driver))
        if execute_address == CmdExecuteAdressEnum.CLIENT.value:
            if client_nic_driver in ["sxe"] and key_word in sdict.keys():
                log.info("=> key_word:{}".format(sdict[key_word]))
                return sdict[key_word]
            else:
                return key_word
        else:
            if server_nic_driver in ["sxe"] and key_word in sdict.keys():
                log.info("=> key_word:{}".format(sdict[key_word]))
                return sdict[key_word]
            else:
                return key_word

    @classmethod
    def get_ipconfig_info(cls, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                          win_vm_ip: str = None) -> dict:
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 获取ipconfig
        """
        rtn_dict = {}
        cmd = "ipconfig /all|select -Skip 9"
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, win_vm_ip=win_vm_ip, cmd_execute_address=execute_address)
        log.info("status:{}\nout:{}\nerr:{}".format(status, out, err))
        if not out:
            return rtn_dict
        info_list = out.split("\n")
        net_adapter_name = ""
        for info in info_list:
            if "以太网适配器" in info or "Ethernet adapter" in info:
                res = re.findall(r"(以太网适配器|Ethernet adapter) (.+):", info)
                net_adapter_name = res[0][1]
                rtn_dict[net_adapter_name] = {}
            elif re.findall(r"\S+", info):
                res = re.findall(r"\s+(.+?)[\.*\s*]+:(.*)", info)
                if res:
                    if "Ipv6" in res[0][0]:
                        if VENDOR_ID in res[0][1]:
                            rtn_dict[net_adapter_name][res[0][0]] = res[0][1]
                        else:
                            rtn_dict[net_adapter_name][res[0][0]] = ""
                    else:
                        rtn_dict[net_adapter_name][res[0][0]] = res[0][1]
            else:
                pass
        # log.info("get_ipconfig_info:{}".format(rtn_dict))
        return rtn_dict

    @classmethod
    def get_net_adapter_info(cls, execute_address: str = CmdExecuteAdressEnum.SERVER.value, is_all: bool = False,
                             win_vm_ip: str = None) -> list:
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 获取get-netadapter信息。[{adapter_info}, {adapter_info}, ...]
        """
        rtn_list = []
        if is_all:
            cmd = "Get-NetAdapter |Format-List *"
        else:
            cmd = "Get-NetAdapter |Format-List"
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, win_vm_ip=win_vm_ip, cmd_execute_address=execute_address)
        if not out:
            return rtn_list
        info_list = out.lstrip().split("\n")
        temp_dict = {}
        for info in info_list:
            if not re.findall(r"\S+", info):
                rtn_list.append(temp_dict.copy())
                temp_dict.clear()
            else:
                res = re.findall(r"(\w+)\s+:(.*)", info)
                if res:
                    temp_dict[res[0][0]] = res[0][1].strip()
        log.info("get_net_adapter_info:{}".format(rtn_list))
        return rtn_list

    @classmethod
    def get_net_adapter_name(cls, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                             win_vm_ip: str = None) -> list:
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 获取网络适配器名称
        """
        rtn_list = []
        net_adapter_list = CommonOperation.get_net_adapter_info(execute_address=execute_address,
                                                                win_vm_ip=win_vm_ip)
        if not net_adapter_list:
            log.warning("未查询到net_adapter")
            return rtn_list
        for info_dict in net_adapter_list:
            rtn_list.append(info_dict["Name"])
        return rtn_list

    @classmethod
    def get_net_adapter_ipv4(cls, net_adapter_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                             win_vm_ip: str = None) -> str:
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 获取网络适配器IPv4地址
        """
        net_adapter_ipv4 = ""
        ipconfig_dict = CommonOperation.get_ipconfig_info(execute_address=execute_address, win_vm_ip=win_vm_ip)
        if not ipconfig_dict:
            log.warning("未查询到ipconfig")
            return net_adapter_ipv4
        net_adapter_ipv4 = ipconfig_dict[net_adapter_name]["IPv4 Address"].replace("(Preferred)", "").strip()
        return net_adapter_ipv4

    @classmethod
    def get_net_adapter_ipv6(cls, net_adapter_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                             win_vm_ip: str = None) -> str:
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 获取网络适配器IPv4地址
        """
        net_adapter_ipv6 = ""
        ipconfig_dict = CommonOperation.get_ipconfig_info(execute_address=execute_address, win_vm_ip=win_vm_ip)
        if not ipconfig_dict:
            log.warning("未查询到ipconfig")
            return net_adapter_ipv6
        get_info = ipconfig_dict[net_adapter_name]["Link-local IPv6 Address"].strip()
        get_info = get_info.replace("(Preferred)", "")
        net_adapter_ipv6 = re.sub(r"%(\S+)", r'', get_info)
        log.info("net_adapter_ipv6:{}".format(net_adapter_ipv6))
        return net_adapter_ipv6

    @classmethod
    def get_net_adapter_mac(cls, net_adapter_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                            win_vm_ip: str = None) -> str:
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 获取网络适配器MAC地址
        """
        net_adapter_mac = ""
        ipconfig_dict = CommonOperation.get_ipconfig_info(execute_address=execute_address, win_vm_ip=win_vm_ip)
        if not ipconfig_dict:
            log.warning("未查询到ipconfig")
            return net_adapter_mac
        net_adapter_mac = ipconfig_dict[net_adapter_name]["Physical Address"].strip().replace("-", ":").lower()
        return net_adapter_mac

    @classmethod
    def get_net_adapter_mac_by_cmdlet(cls, net_adapter_name: str,
                                      execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                                      win_vm_ip: str = None) -> str:
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 使用get-netadapter获取网络适配器MAC地址
        """
        rtn_str = ''
        net_adapter_list = CommonOperation.get_net_adapter_info(execute_address=execute_address,
                                                                win_vm_ip=win_vm_ip)
        if not net_adapter_list:
            log.warning("未查询到net_adapter")
            return ""
        for info_dict in net_adapter_list:
            if info_dict["Name"] == net_adapter_name:
                rtn_str = info_dict["MacAddress"].replace("-", ":").lower()
                break
        return rtn_str

    @classmethod
    def get_net_adapter_submask(cls, net_adapter_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                                win_vm_ip: str = None) -> str:
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 获取网络适配器子网掩码
        """
        net_adapter_mask = ""
        ipconfig_dict = CommonOperation.get_ipconfig_info(execute_address=execute_address, win_vm_ip=win_vm_ip)
        if not ipconfig_dict:
            log.warning("未查询到ipconfig")
            return net_adapter_mask
        net_adapter_mask = ipconfig_dict[net_adapter_name]["Subnet Mask"].strip()
        return net_adapter_mask

    @classmethod
    def set_net_adapter_name(cls, old_adapter_name: str, new_adapter_name: str,
                             execute_address: str = CmdExecuteAdressEnum.SERVER.value, win_vm_ip: str = None):
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 修改网络适配器名称
        """
        cmd = "Rename-NetAdapter -name \"{}\" -newname \"{}\"".format(old_adapter_name, new_adapter_name)
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, win_vm_ip=win_vm_ip, cmd_execute_address=execute_address)

    @classmethod
    def set_net_adapter_static_ip(cls, adapter_name: str, static_ip: str, subnet_mask: str,
                                  execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                                  win_vm_ip: str = None):
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 修改网络适配器静态ip
        """
        cmd = "netsh interface ipv4 set address name={} source=static address={} mask={}" \
            .format(adapter_name, static_ip, subnet_mask)
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, win_vm_ip=win_vm_ip, cmd_execute_address=execute_address)

    @classmethod
    def get_vm_info(cls, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                    is_all: bool = False) -> list:
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 获取Get-VM信息
        """
        rtn_list = []
        if is_all:
            cmd = "Get-VM |Format-List *"
        else:
            cmd = "Get-VM |Format-List"
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=execute_address)
        if not out:
            return rtn_list
        info_list = out.lstrip().split("\n")
        temp_dict = {}
        for info in info_list:
            if not re.findall(r"\S+", info):
                rtn_list.append(temp_dict.copy())
                temp_dict.clear()
            else:
                res = re.findall(r"(\w+)\s+:(.*)", info)
                if res:
                    temp_dict[res[0][0]] = res[0][1].strip()
        log.info("get_vm_info:{}".format(rtn_list))
        return rtn_list

    @classmethod
    def get_vm_memory_demand(cls, vm_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 获取Get-VM信息
        """
        vm_memory_demand = ""
        vm_info_list = CommonOperation.get_vm_info(execute_address=execute_address)
        if not vm_info_list:
            log.warning("未查询到vm")
            return vm_memory_demand
        for vm_info_dict in vm_info_list:
            if vm_info_dict["Name"] == vm_name:
                vm_memory_demand = vm_info_dict["MemoryDemand"]
                break
        if vm_memory_demand:
            log.info("MemoryDeman:{}".format(vm_memory_demand))
        else:
            log.error("未找到MemoryDemand，请检查vm_name")
        return vm_memory_demand

    @classmethod
    def check_vm_stats(cls, vm_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                       check_running: bool = True, collect_info: bool = True,
                       virtual_mode: str = VirtualModeEnum.SR_IOV.value,
                       device_name_server: str = "", device_name_client: str = "") -> tuple:
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 检查vm是否已启动。若启动，返回(true,vm信息字典)；若未启动，返回(false, {})
        """
        from scripts.script_libs.windows_hyperv_manage_vm import VmOp, VmAdapter, VmSwitch
        rtn_status = True
        rtn_dict = {}

        if check_running:
            # 检查虚拟机是否存在
            vm_name_list = VmOp.get_vm(cmd_execute_address=execute_address)
            if vm_name in vm_name_list:
                log.info(f"虚拟机{vm_name}存在")
            elif vm_name_list:
                log.info(f"虚拟机{vm_name}不存在，尝试修改{vm_name_list[0]}名称为{vm_name}")
                vm_name_new = VmOp.rename_vm(old_name=vm_name_list[0], new_name=vm_name,
                                             cmd_execute_address=execute_address)
                vm_name_list.append(vm_name_new)
                if vm_name in vm_name_list:
                    log.info(f"修改名称成功，虚拟机{vm_name}已存在")
                else:
                    log.error(f"虚拟机修改名称失败")
                    rtn_status = False
                    return rtn_status, rtn_dict
            else:
                log.info(f"虚拟机{vm_name}不存在，尝试创建")
                vm_list = VmOp.create_vm(count=1 - len(vm_name_list), cmd_execute_address=execute_address)
                vm_name_list = vm_name_list + vm_list
                if vm_name in vm_name_list:
                    log.info(f"虚拟机创建成功，虚拟机{vm_name}已存在")
                else:
                    log.error(f"虚拟机创建失败")
                    rtn_status = False
                    return rtn_status, rtn_dict

            # 建立虚拟机管理通路
            success_flag = CommonOperation.establish_win_vm_manage_channel(vm_name, execute_address=execute_address,
                                                                           adapter_config=False)
            log.info(f"establish_win_vm_manage_channel success_flag:{success_flag}")
            if not success_flag:
                rtn_status = False
                return rtn_status, rtn_dict

            # 建立虚拟机测试通路
            success_flag = CommonOperation.establish_win_vm_test_channel(vm_name, execute_address=execute_address,
                                                                         adapter_config=False,
                                                                         virtual_mode=virtual_mode,
                                                                         device_name_server=device_name_server,
                                                                         device_name_client=device_name_client)
            log.info(f"establish_win_vm_test_channel success_flag:{success_flag}")
            if not success_flag:
                rtn_status = False
                return rtn_status, rtn_dict

            # 启动虚拟机，检查虚拟机是否已启动
            if VmOp.get_vm_running_state(vm_name, execute_address=execute_address) == "Running":
                init_success = VmOp.wait_vm_init_complete(vm_name, execute_address=execute_address)
                if init_success:
                    log.info(f"{vm_name}已启动")
                else:
                    log.error(f"{vm_name}启动失败")
                    rtn_status = False
                    return rtn_status, rtn_dict
            else:
                VmOp.start_vm(vm_name, execute_address=execute_address)
                log.info(f"等待{vm_name}启动...")
                init_success = VmOp.wait_vm_init_complete(vm_name, execute_address=execute_address)
                if init_success:
                    log.info(f"{vm_name}已启动")
                else:
                    log.error(f"{vm_name}启动失败")
                    rtn_status = False
                    return rtn_status, rtn_dict

            # 检查虚拟机管理通路是否配置正确，若不正确，重新配置一次
            success_flag = CommonOperation.check_win_vm_manage_channel(vm_name, execute_address=execute_address)
            log.info(f"check_win_vm_manage_channel success_flag:{success_flag}")
            if not success_flag:
                rtn_status = False
                return rtn_status, rtn_dict

        if collect_info:
            # 配置虚拟机测试适配器ip、submask、gateway、名称
            success_flag = CommonOperation.establish_win_vm_test_channel(vm_name, execute_address=execute_address,
                                                                         adapter_config=True,
                                                                         virtual_mode=virtual_mode)
            log.info(f"establish_win_vm_test_channel, adapter_config, success_flag:{success_flag}")
            if not success_flag:
                rtn_status = False
                return rtn_status, rtn_dict

            # 获取pm vswitch name
            if virtual_mode == VirtualModeEnum.SR_IOV.value:
                vswitch_name = f"vEthernet ({V_SWITCH_SRIOV_NAME_DEF})"
            elif virtual_mode == VirtualModeEnum.VMQ.value:
                vswitch_name = f"vEthernet ({V_SWITCH_VMQ_NAME_DEF})"
            else:
                vswitch_name = f"vEthernet ({V_SWITCH_DEGVMQ_NAME_DEF})"
            # 获取pm vmswitch ip
            vswitch_ip = CommonOperation.get_net_adapter_ipv4(vswitch_name, execute_address=execute_address)
            # 获取pm vmswitch submask
            vswitch_submask = CommonOperation.get_net_adapter_submask(vswitch_name, execute_address=execute_address)
            # 获取pm vmswitch mac_addr
            vswitch_mac_addr = CommonOperation.get_net_adapter_mac(vswitch_name, execute_address=execute_address)
            # 获取vm管理ip
            vm_ip = CommonOperation.get_win_vm_ip(execute_address=execute_address, vm_name=vm_name)
            # 获取vf ip
            vf_ip = cls.vm_vf_ip.get(vm_name)
            # 获取vf ipv6
            vf_ipv6 = CommonOperation.get_net_adapter_ipv6(constants.VM_ADAPTER_TEST_NAME_DEF, win_vm_ip=vm_ip,
                                                           execute_address=execute_address)
            # 获取vf submask
            vf_sub_mask = cls.vm_vf_submask.get(vm_name)
            # 获取vf mac_addr
            vf_mac_addr = CommonOperation.get_net_adapter_mac_by_cmdlet(constants.VM_ADAPTER_TEST_NAME_DEF,
                                                                        execute_address=execute_address,
                                                                        win_vm_ip=vm_ip)
            rtn_dict["vswitch_name"] = vswitch_name
            rtn_dict["vswitch_ip"] = vswitch_ip
            rtn_dict["vswitch_submask"] = vswitch_submask
            rtn_dict["vswitch_mac_addr"] = vswitch_mac_addr
            rtn_dict["vm_name"] = vm_name
            rtn_dict["vm_ip"] = vm_ip
            rtn_dict["hyperv_adapter_name"] = constants.VM_ADAPTER_TEST_NAME_DEF
            rtn_dict["vf_name"] = constants.VM_ADAPTER_VF_NAME_DEF
            rtn_dict["vf_ip"] = vf_ip
            rtn_dict["vf_ipv6"] = vf_ipv6
            rtn_dict["vf_sub_mask"] = vf_sub_mask
            rtn_dict["vf_mac_addr"] = vf_mac_addr
        return rtn_status, rtn_dict

    @classmethod
    def check_kvm_stats(cls, vm_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                        check_running: bool = True, collect_info: bool = True,
                        virtual_mode: str = VirtualModeEnum.SR_IOV.value,
                        device_name_server: str = "", device_name_client: str = "", vf_num: int = 0) -> tuple:
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 检查vm是否已启动。若启动，返回(true,vm信息字典)；若未启动，返回(false, {})
        """
        from scripts.script_libs.windows_hyperv_manage_vm import KvmOp, VmAdapter, VmSwitch
        rtn_status = True
        rtn_dict = {}

        if check_running:
            # 检查虚拟机是否存在
            vm_name_list = KvmOp.get_vm(cmd_execute_address=execute_address)
            if vm_name in vm_name_list:
                log.info(f"虚拟机{vm_name}存在")
            else:
                log.info(f"虚拟机{vm_name}不存在，尝试创建")
                vm_list = KvmOp.create_vm(count=1 - len(vm_name_list), exist_vm_list=vm_name_list,
                                          cmd_execute_address=execute_address)
                vm_name_list = vm_name_list + vm_list
                if vm_name in vm_name_list:
                    log.info(f"虚拟机创建成功，虚拟机{vm_name}已存在")
                else:
                    log.error(f"虚拟机创建失败")
                    rtn_status = False
                    return rtn_status, rtn_dict

            # 建立虚拟机管理通路
            success_flag = CommonOperation.establish_win_vm_manage_channel(vm_name, execute_address=execute_address,
                                                                           adapter_config=False,
                                                                           physical_host_os="linux")
            log.info(f"establish_win_vm_manage_channel success_flag:{success_flag}")
            if not success_flag:
                rtn_status = False
                return rtn_status, rtn_dict

            # 建立虚拟机测试通路
            success_flag = \
                CommonOperation.establish_win_vm_test_channel(vm_name, execute_address=execute_address,
                                                              adapter_config=False, virtual_mode=virtual_mode,
                                                              physical_host_os="linux",
                                                              device_name_server=device_name_server,
                                                              device_name_client=device_name_client,
                                                              vf_num=constants.KVM_MAX_VF_NUM)
            log.info(f"establish_win_vm_test_channel success_flag:{success_flag}")
            if not success_flag:
                rtn_status = False
                return rtn_status, rtn_dict

            # 启动虚拟机，检查虚拟机是否已启动
            if KvmOp.check_vm_state(vm_name, cmd_execute_address=execute_address) == "running":
                init_success = KvmOp.wait_vm_init_complete(vm_name, execute_address=execute_address)
                if init_success:
                    log.info(f"{vm_name}已启动")
                else:
                    log.error(f"{vm_name}启动失败")
                    rtn_status = False
                    return rtn_status, rtn_dict
            else:
                KvmOp.start_vm(vm_name, execute_address=execute_address)
                log.info(f"等待{vm_name}启动...")
                init_success = KvmOp.wait_vm_init_complete(vm_name, execute_address=execute_address)
                if init_success:
                    log.info(f"{vm_name}已启动")
                else:
                    log.error(f"{vm_name}启动失败")
                    rtn_status = False
                    return rtn_status, rtn_dict

            # 检查虚拟机管理通路是否配置正确，若不正确，重新配置一次
            success_flag = CommonOperation.check_win_vm_manage_channel(vm_name, execute_address=execute_address,
                                                                       physical_host_os="linux")
            log.info(f"check_win_vm_manage_channel success_flag:{success_flag}")
            if not success_flag:
                rtn_status = False
                return rtn_status, rtn_dict

        if collect_info:
            # 配置虚拟机测试适配器ip、submask、gateway、名称
            success_flag = CommonOperation.establish_win_vm_test_channel(vm_name, execute_address=execute_address,
                                                                         adapter_config=True,
                                                                         virtual_mode=virtual_mode,
                                                                         physical_host_os="linux",
                                                                         device_name_server=device_name_server,
                                                                         device_name_client=device_name_client)
            log.info(f"establish_win_vm_test_channel, adapter_config, success_flag:{success_flag}")
            if not success_flag:
                rtn_status = False
                return rtn_status, rtn_dict

            # 获取vm管理ip
            win_vm_ip = CommonOperation.get_win_vm_ip(execute_address=execute_address, vm_name=vm_name)
            # 获取vf ip
            vf_ip = cls.vm_vf_ip.get(vm_name)
            # 获取vf ipv6
            vf_ipv6 = CommonOperation.get_net_adapter_ipv6(constants.VM_ADAPTER_VF_NAME_DEF, win_vm_ip=win_vm_ip,
                                                           execute_address=execute_address)
            # 获取vf submask
            vf_sub_mask = cls.vm_vf_submask.get(vm_name)
            # 获取vf mac_addr
            vf_mac_addr = CommonOperation.get_net_adapter_mac_by_cmdlet(constants.VM_ADAPTER_VF_NAME_DEF,
                                                                        execute_address=execute_address,
                                                                        win_vm_ip=win_vm_ip)
            # rtn_dict["vswitch_name"] = vswitch_name
            # rtn_dict["vswitch_ip"] = vswitch_ip
            # rtn_dict["vswitch_submask"] = vswitch_submask
            # rtn_dict["vswitch_mac_addr"] = vswitch_mac_addr
            rtn_dict["vm_name"] = vm_name
            rtn_dict["vm_ip"] = win_vm_ip  #
            rtn_dict["hyperv_adapter_name"] = constants.VM_ADAPTER_TEST_NAME_DEF  #
            rtn_dict["vf_name"] = constants.VM_ADAPTER_VF_NAME_DEF  #
            rtn_dict["vf_ip"] = vf_ip  #
            rtn_dict["vf_ipv6"] = vf_ipv6  #
            rtn_dict["vf_sub_mask"] = vf_sub_mask
            rtn_dict["vf_mac_addr"] = vf_mac_addr  #
        return rtn_status, rtn_dict

    @classmethod
    def establish_win_vm_manage_channel(cls, vm_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                                        adapter_config: bool = False, physical_host_os: str = "windows") -> bool:
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 建立windows虚拟机的管理通路
        """
        if physical_host_os == "windows":
            from scripts.script_libs.windows_hyperv_manage_vm import VmOp, VmAdapter, VmSwitch
            rtn_status = True
            manage_vmswitch_name = constants.V_SWITCH_MANAGER_NAME_DEF
            v_adapter_name = constants.V_ADAPTER_MANAGER_NAME_DEF
            vm_adapter_name = constants.VM_ADAPTER_MANAGER_NAME_DEF

            if not adapter_config:
                log.info("************establish_win_vm_manage_channel***************")
                # 1. 管理通路-创建管理交换机
                if not VmSwitch.find_vmswitch(manage_vmswitch_name, execute_address):
                    # 获取用来创建管理交换机的网卡名称
                    from scripts.script_libs.windows_adapter_operation import GetAdapterOperation
                    logical_server_ip, logical_client_ip = CommandOperation.get_logical_ip_form_config()
                    get_adapter = GetAdapterOperation(device_name="", cmd_execute_address=execute_address)
                    if execute_address == CmdExecuteAdressEnum.CLIENT.value:
                        manager_nic_info = get_adapter.get_switch_pf_adapter_ipv4_address(
                            manager_address=logical_client_ip)
                    else:
                        manager_nic_info = get_adapter.get_switch_pf_adapter_ipv4_address(
                            manager_address=logical_server_ip)
                    if len(list(manager_nic_info.keys())) == 0 or len(list(manager_nic_info.keys())) > 1:
                        log.error("环境不满足测试vf场景和vmq网卡的场景,脚本退出,请对机器添加管理网络")
                        rtn_status = False
                        return rtn_status
                    manager_adapter_name = "".join(list(manager_nic_info.keys()))
                    log.info(f"使用{manager_adapter_name}创建管理交换机")

                    # 创建管理交换机
                    cmd, status, out, err = \
                        VmSwitch.new_vmswitch(vmswitch_name=manage_vmswitch_name,
                                              adapter_name=manager_adapter_name,
                                              enable_iov=False, execute_address=execute_address)
                    if status:
                        log.error("创建管理交换机失败")
                        rtn_status = False
                        return rtn_status
                else:
                    log.info(f"{vm_name}已存在管理交换机{manage_vmswitch_name}")

                # 2. 管理通路-虚拟机添加网络适配器
                if not VmAdapter.check_vmnetworkadapter_exist(vm_name=vm_name, vm_adapter_name=v_adapter_name,
                                                              cmd_execute_address=execute_address):
                    # 先关虚拟机
                    if VmOp.get_vm_running_state(vm_name, execute_address=execute_address) == "Off":
                        log.info(f"{vm_name}已关闭")
                    else:
                        stop_cmd, cmd_code, cmd_stdout, cmd_stderr = VmOp.stop_vm(vm_name,
                                                                                  execute_address=execute_address)
                        if cmd_code:
                            log.error(f"{vm_name}关闭失败")
                            rtn_status = False
                            return rtn_status
                        if VmOp.wait_vm_stop_complete(vm_name, execute_address=execute_address):
                            log.info(f"{vm_name}已关闭")
                        else:
                            log.error(f"{vm_name}关闭失败")
                            rtn_status = False
                            return rtn_status

                    # 添加网络适配器
                    rtn_add_code, rtn_vm_adapter_switch_dict = VmAdapter.add_vmnetworkadapter_with_connect_switch(
                        vm_name=vm_name, add_adapter_count=1, vm_adapter_name_list=[v_adapter_name],
                        connect_switch_name_list=[], cmd_execute_address=execute_address)
                    if rtn_add_code == RtnStatusEnum.FAIL.value:
                        log.error(f"{execute_address}:虚拟机{vm_name}添加网络适配器{v_adapter_name}失败！")
                        rtn_status = False
                        return rtn_status
                else:
                    log.info(f"{vm_name}已存在网络适配器{v_adapter_name}")

                # 3. 管理通路-虚拟机网络适配器连接管理交换机
                status, result = \
                    VmAdapter.connect_vmnetworkadapter(vm_name=vm_name, v_adapter_name=v_adapter_name,
                                                       vmswitch_name=manage_vmswitch_name,
                                                       execute_address=execute_address)
                if status == RtnStatusEnum.FAIL.value:
                    log.error(f"{execute_address}:虚拟机{vm_name}网络适配器{v_adapter_name}连接虚拟交换机{manage_vmswitch_name}失败！")
                    rtn_status = False
                    return rtn_status
            else:
                log.info("************establish_win_vm_manage_channel, adapter_config***************")
                # 4. 管理通路-配置虚拟机网络适配器ip、submask、gateway、名称
                vm_conf_ip = CommonOperation.get_conf_vm_ip(vm_name, execute_address=execute_address)
                vm_conf_submask = CommonOperation.get_conf_vm_submask(vm_name, execute_address=execute_address)
                vm_conf_gateway = CommonOperation.get_conf_vm_gateway(vm_name, execute_address=execute_address)
                # 备注：该函数的适配器名称(内)与适配器名称(外) ，形参与实参相反
                rtn_code, _, _, new_ip = VmAdapter.update_vm_adapter_name_ip_gateway_address(
                    vm_name=vm_name, vm_adapter_name=v_adapter_name, v_adapter_name=vm_adapter_name,
                    new_ip=vm_conf_ip, prefix_length=vm_conf_submask, new_gateway=vm_conf_gateway,
                    vm_adapter_ifdesc_kw="LD 1160-2X", cmd_execute_address=execute_address)
                cls.save_vm_ip(vm_ip=new_ip, vm_name=vm_name, execute_address=execute_address)
                if rtn_code:
                    log.error(f"{execute_address}: 虚拟机管理通路适配器配置ip、submask、gateway、名称失败")
                    rtn_status = False
                    return rtn_status
                # 配置完成后打印ipconfig
                status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd="ipconfig", win_vm_ip=CommonOperation.get_win_vm_ip(execute_address, vm_name),
                    cmd_execute_address=execute_address)
                if not status:
                    log.info(out)
        else:
            log.info("physical_host_os: linux")
            from scripts.script_libs.windows_hyperv_manage_vm import KvmOp, VmAdapter, VmSwitch
            rtn_status = True
            vm_adapter_name = constants.VM_ADAPTER_MANAGER_NAME_DEF

            if not adapter_config:
                log.info("************establish_win_vm_manage_channel***************")
                # 1. 若虚拟机未关机，先关闭
                vm_status = KvmOp.check_vm_state(vm_name=constants.KVM_VM_NAME, cmd_execute_address=execute_address)
                log.info(f"{constants.KVM_VM_NAME}: {vm_status}")
                if vm_status == "running":
                    status = KvmOp.stop_vm(vm_name=constants.KVM_VM_NAME, execute_address=execute_address)
                    if status == RtnStatusEnum.FAIL.value:
                        log.error("关闭虚拟机失败")
                        rtn_status = False
                        return rtn_status
                    log.info("关闭虚拟机成功")
                # 2. 管理通路-物理机创建管理网卡的vf
                logical_server_ip, logical_client_ip = CommandOperation.get_logical_ip_form_config()
                if execute_address == CmdExecuteAdressEnum.CLIENT.value:
                    manage_nic_name = KvmOp.get_nic_name_by_ip(logical_client_ip, cmd_execute_address=execute_address)
                else:
                    manage_nic_name = KvmOp.get_nic_name_by_ip(logical_server_ip, cmd_execute_address=execute_address)
                if not manage_nic_name:
                    log.error("环境不满足测试vf场景的场景,脚本退出,请对机器添加管理网络")
                    rtn_status = False
                    return rtn_status
                # 创建管理vf
                log.info(f"使用{manage_nic_name}创建管理vf")
                vf_num = constants.KVM_MAX_MANAGE_VF_NUM
                status = KvmOp.create_vf_of_nic(manage_nic_name, vf_num, cmd_execute_address=execute_address)
                if status:
                    vf_nic_name, vf_nic_bdf = status
                else:
                    log.error("创建管理vf失败:1")
                    rtn_status = False
                    return rtn_status
                vf_prop_dict = KvmOp.get_vf_prop_of_nic(manage_nic_name, cmd_execute_address=execute_address)
                for i in range(vf_num):
                    vf_id = vf_prop_dict[str(i)]['vf']
                    vf_nic_name = vf_prop_dict[str(i)]['vf_device']
                    vf_nic_bdf = vf_prop_dict[str(i)]['bdf']
                    if not vf_nic_name:
                        log.error("创建管理vf失败:2")
                        rtn_status = False
                        return rtn_status
                    else:
                        log.info(f"创建管理vf成功：{vf_nic_name}, {vf_nic_bdf}")

                # 3. 管理通路-虚拟机添加管理网卡PCI设备
                if not KvmOp.check_vm_nic_pci_exist(vm_name=constants.KVM_VM_NAME, vf_nic_bdf=vf_nic_bdf,
                                                    cmd_execute_address=execute_address):
                    # 添加网络适配器
                    status = \
                        KvmOp.add_vm_nic_pci(vm_name=constants.KVM_VM_NAME, vf_nic_bdf=vf_nic_bdf, domain_id="0x0000",
                                             cmd_execute_address=execute_address)
                    if status == RtnStatusEnum.FAIL.value:
                        log.error(f"{execute_address}:虚拟机{vm_name}添加网卡PCI设备失败！")
                        rtn_status = False
                        return rtn_status
                else:
                    log.info(f"{vm_name}已存在网卡PCI设备")

            else:
                log.info("************establish_win_vm_manage_channel, adapter_config***************")
                # 4. 管理通路-配置虚拟机网络适配器ip、submask、gateway、名称
                vm_conf_ip = CommonOperation.get_conf_vm_ip(vm_name, execute_address=execute_address)
                vm_conf_submask = CommonOperation.get_conf_vm_submask(vm_name, execute_address=execute_address)
                vm_conf_gateway = CommonOperation.get_conf_vm_gateway(vm_name, execute_address=execute_address)
                # todo KVM windows虚拟机内部的ip设置，待完成
                # rtn_code, _, _, new_ip = VmAdapter.update_vm_adapter_name_ip_gateway_address(
                #     vm_name=vm_name, vm_adapter_name=v_adapter_name, v_adapter_name=vm_adapter_name,
                #     new_ip=vm_conf_ip, prefix_length=vm_conf_submask, new_gateway=vm_conf_gateway,
                #     vm_adapter_ifdesc_kw="LD 1160-2X", cmd_execute_address=execute_address)
                # cls.save_vm_ip(vm_ip=new_ip, vm_name=vm_name, execute_address=execute_address)
                # if rtn_code:
                #     log.error(f"{execute_address}: 虚拟机管理通路适配器配置ip、submask、gateway、名称失败")
                #     rtn_status = False
                #     return rtn_status
                # # 配置完成后打印ipconfig
                # status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                #     cmd="ipconfig", win_vm_ip=CommonOperation.get_vm_ip(execute_address, vm_name),
                #     cmd_execute_address=execute_address)
                # if not status:
                #     log.info(out)

        return rtn_status

    @classmethod
    def check_win_vm_manage_channel(cls, vm_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                                    physical_host_os: str = "windows") \
            -> bool:
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 检查windows虚拟机的管理通路
        """
        if physical_host_os == "windows":
            log.info("************check_win_vm_manage_channel***************")
            rtn_status = True
            configured_count = 0
            while configured_count < 2:
                vm_ip = CommonOperation.get_win_vm_ip(execute_address=execute_address, vm_name=vm_name)
                if "win" in sys.platform:
                    cmd = f"ping {vm_ip} -n 1"
                else:
                    cmd = f"timeout 5s ping {vm_ip} -c 1"
                ping_status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, local_execute_flag=True, cmd_execute_address=execute_address)
                log.info("status:{}, result:{}".format(ping_status, out))
                # ping通
                if not ping_status:
                    status, ipconfig_out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd="ipconfig", cmd_execute_address=execute_address, win_vm_ip=vm_ip)
                    log.info("status:{}, result:{}".format(status, ipconfig_out))
                    # vm_ip存在
                    if vm_ip in ipconfig_out:
                        log.info(f"虚拟机{vm_name} 管理ip：{vm_ip}配置正确")
                        break
                    # vm_ip不存在
                    else:
                        log.error(f"虚拟机{vm_name} 管理ip：{vm_ip}被占用，请检查环境！")
                        rtn_status = False
                        return rtn_status
                # ping不通
                else:
                    # 未配置过
                    if configured_count < 1:
                        # 重新配置管理适配器
                        log.warning(f"ping 虚拟机{vm_name}管理ip:{vm_ip}失败，尝试重新配置管理适配器")
                        success_flag = CommonOperation.establish_win_vm_manage_channel(vm_name,
                                                                                       execute_address=execute_address,
                                                                                       adapter_config=True)
                        log.info(f"{execute_address}: establish_win_vm_manage_channel, adapter_config,"
                                 f" success_flag:{success_flag}")
                        if not success_flag:
                            rtn_status = False
                            return rtn_status
                        else:
                            configured_count += 1
                    # 已配置过
                    else:
                        log.error(f"重新配置{execute_address}:{vm_name}的管理适配器后，ip未生效，请检查环境！")
                        rtn_status = False
                        return rtn_status
            return rtn_status
        else:
            log.info("************check_win_vm_manage_channel***************")
            # 首先获取kvm本地ip
            if not CommandOperation.kvm_localnet:
                # 获取kvm本地ip
                cmd_code, cmd_stdout, cmd_stderr= CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=f"virsh domifaddr {vm_name} |tail -n +3", cmd_execute_address=execute_address)
                log.info("cmd_code: {}\ncmd_stdout: {}\ncmd_stderr: {}".format(cmd_code, cmd_stdout, cmd_stderr))
                res = re.findall(r"\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)/\d+", cmd_stdout)
                if res:
                    CommandOperation.kvm_localnet = res[0][3]
                else:
                    log.error(f"获取kvm本地ip失败, 请检查环境")
                    rtn_status = False
                    return rtn_status
            # check_win_vm_manage_channel
            rtn_status = True
            configured_count = 0
            while configured_count < 2:
                vm_ip = CommonOperation.get_win_vm_ip(execute_address=execute_address, vm_name=vm_name)
                if "win" in sys.platform:
                    cmd = f"ping {vm_ip} -n 1"
                else:
                    cmd = f"timeout 5s ping {vm_ip} -c 1"
                ping_status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, local_execute_flag=True, cmd_execute_address=execute_address)
                log.info("status:{}, result:{}".format(ping_status, out))
                # ping通
                if not ping_status:
                    status, ipconfig_out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd="ipconfig", cmd_execute_address=execute_address, win_vm_ip=vm_ip)
                    log.info("status:{}, result:{}".format(status, ipconfig_out))
                    # vm_ip存在
                    if vm_ip in ipconfig_out:
                        log.info(f"虚拟机{vm_name} 管理ip：{vm_ip}配置正确")
                        break
                    # vm_ip不存在
                    else:
                        log.error(f"虚拟机{vm_name} 管理ip：{vm_ip}被占用，请检查环境！")
                        rtn_status = False
                        return rtn_status
                # ping不通
                else:
                    # 未配置过
                    if configured_count < 1:
                        # 重新配置管理适配器
                        log.warning(f"ping 虚拟机{vm_name}管理ip:{vm_ip}失败，尝试重新配置管理适配器")
                        success_flag = CommonOperation.establish_win_vm_manage_channel(vm_name,
                                                                                       execute_address=execute_address,
                                                                                       adapter_config=True,
                                                                                       physical_host_os=physical_host_os)
                        log.info(f"{execute_address}: establish_win_vm_manage_channel, adapter_config,"
                                 f" success_flag:{success_flag}")
                        if not success_flag:
                            rtn_status = False
                            return rtn_status
                        else:
                            configured_count += 1
                    # 已配置过
                    else:
                        log.error(f"重新配置{execute_address}:{vm_name}的管理适配器后，ip未生效，请检查环境！")
                        rtn_status = False
                        return rtn_status
            return rtn_status

    @classmethod
    def establish_win_vm_test_channel(cls, vm_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                                      v_adapter_name: str = constants.V_ADAPTER_TEST_NAME_DEF,
                                      virtual_mode: str = VirtualModeEnum.SR_IOV.value,
                                      adapter_config: bool = False, physical_host_os: str = "windows",
                                      device_name_server: str = "", device_name_client: str = "",
                                      vf_num: int = 0) -> bool:
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 建立windows虚拟机的测试通路
        """
        if physical_host_os == "windows":
            from scripts.script_libs.windows_hyperv_manage_vm import VmOp, VmAdapter, VmSwitch
            rtn_status = True

            if not adapter_config:
                log.info("************establish_win_vm_test_channel***************")
                # 1. 测试通路-虚机添加网络适配器
                if not VmAdapter.check_vmnetworkadapter_exist(vm_name=vm_name, vm_adapter_name=v_adapter_name,
                                                              cmd_execute_address=execute_address):
                    # 先关虚拟机
                    if VmOp.get_vm_running_state(vm_name, execute_address=execute_address) == "Off":
                        log.info(f"{vm_name}已关闭")
                    else:
                        stop_cmd, cmd_code, cmd_stdout, cmd_stderr = VmOp.stop_vm(vm_name,
                                                                                  execute_address=execute_address)
                        if cmd_code:
                            log.error(f"{vm_name}关闭失败")
                            rtn_status = False
                            return rtn_status
                        if VmOp.wait_vm_stop_complete(vm_name, execute_address=execute_address):
                            log.info(f"{vm_name}已关闭")
                        else:
                            log.error(f"{vm_name}关闭失败")
                            rtn_status = False
                            return rtn_status

                    # 添加网络适配器
                    rtn_add_code, rtn_vm_adapter_switch_dict = VmAdapter.add_vmnetworkadapter_with_connect_switch(
                        vm_name=vm_name, add_adapter_count=1, vm_adapter_name_list=[v_adapter_name],
                        connect_switch_name_list=[], cmd_execute_address=execute_address)
                    if rtn_add_code == RtnStatusEnum.FAIL.value:
                        log.error(f"{execute_address}:虚拟机{vm_name}添加网络适配器{v_adapter_name}失败！")
                        rtn_status = False
                        return rtn_status
                else:
                    log.info(f"{vm_name}已存在网络适配器{v_adapter_name}")

                # 2. 测试通路-设置虚拟网络适配器的虚拟化模式
                log.info(f"{execute_address}:虚拟机{vm_name}网络适配器{v_adapter_name}配置虚拟化模式为:{virtual_mode}")
                if virtual_mode == VirtualModeEnum.SR_IOV.value:
                    # 设置网卡的SR-IOV模式
                    iov_weight_setting = random.randint(1, 100)
                    rtn_code = VmAdapter.set_vmnetworkadapter_sriov(vm_name=vm_name, iov_weight=iov_weight_setting,
                                                                    cmd_execute_address=execute_address,
                                                                    vm_adapter_name=v_adapter_name)
                    if rtn_code == RtnStatusEnum.FAIL.value:
                        log.error(f"{execute_address}:设置{vm_name}的网络适配器{v_adapter_name}虚拟化模式{virtual_mode}失败！")
                        rtn_status = False
                        return rtn_status
                elif virtual_mode == VirtualModeEnum.VMQ.value:
                    # 设置网卡的VMQ模式
                    iov_weight_setting = 0
                    rtn_code = VmAdapter.set_vmnetworkadapter_sriov(vm_name=vm_name, iov_weight=iov_weight_setting,
                                                                    cmd_execute_address=execute_address,
                                                                    vm_adapter_name=v_adapter_name)
                    if rtn_code == RtnStatusEnum.FAIL.value:
                        log.error(f"{execute_address}:设置{vm_name}的网络适配器{v_adapter_name}虚拟化模式{virtual_mode}失败！")
                        rtn_status = False
                        return rtn_status
                elif virtual_mode == VirtualModeEnum.DEGVMQ.value:
                    # 设置网卡(外)是否SRIOV使能
                    if CommonOperation.get_degvmq_mode_value(VMADAPTER_SRIOV):
                        iov_weight_setting = random.randint(1, 100)
                    else:
                        iov_weight_setting = 0
                    rtn_code = VmAdapter.set_vmnetworkadapter_sriov(vm_name=vm_name, iov_weight=iov_weight_setting,
                                                                    cmd_execute_address=execute_address,
                                                                    vm_adapter_name=v_adapter_name)
                    if rtn_code == RtnStatusEnum.FAIL.value:
                        log.error(f"{execute_address}:设置{vm_name}的网络适配器{v_adapter_name}虚拟化模式{virtual_mode}失败！")
                        rtn_status = False
                        return rtn_status
            else:
                log.info("************establish_win_vm_test_channel, adapter_config***************")
                # 3. 测试通路--配置虚拟机网络适配器ip、submask、gateway、名称
                # 获取pm vswitch name
                if virtual_mode == VirtualModeEnum.SR_IOV.value:
                    vswitch_name = f"vEthernet ({V_SWITCH_SRIOV_NAME_DEF})"
                elif virtual_mode == VirtualModeEnum.VMQ.value:
                    vswitch_name = f"vEthernet ({V_SWITCH_VMQ_NAME_DEF})"
                else:
                    vswitch_name = f"vEthernet ({V_SWITCH_DEGVMQ_NAME_DEF})"
                # 获取pm vmswitch ip
                vswitch_ip = CommonOperation.get_net_adapter_ipv4(vswitch_name, execute_address=execute_address)
                # 获取pm vmswitch submask
                vswitch_submask = CommonOperation.get_net_adapter_submask(vswitch_name,
                                                                          execute_address=execute_address)
                # 获取pm vmswitch mac_addr
                vswitch_mac_addr = CommonOperation.get_net_adapter_mac(vswitch_name, execute_address=execute_address)

                # 获取vm管理ip
                win_vm_ip = CommonOperation.get_win_vm_ip(execute_address=execute_address, vm_name=vm_name)

                def add_one(matched):
                    # 定义函数：将匹配的数字加 1
                    value_1 = int(matched.group('pos1'))
                    value_2 = int(matched.group('pos2'))
                    value_3 = int(matched.group('pos3')) + 1
                    value_4 = int(matched.group('pos4')) + 1
                    return ".".join([str(value_1), str(value_2), str(value_3), str(value_4)])

                # vf ip = vswitch ip最低位+1
                cls.vm_vf_ip[vm_name] = re.sub('(?P<pos1>\d+)\.(?P<pos2>\d+)\.(?P<pos3>\d+)\.(?P<pos4>\d+)',
                                               add_one, vswitch_ip)
                # vf submask = vswitch submask
                cls.vm_vf_submask[vm_name] = vswitch_submask
                v_adapter_name = constants.V_ADAPTER_TEST_NAME_DEF
                vm_adapter_name = constants.VM_ADAPTER_TEST_NAME_DEF
                vm_vf_name = constants.VM_ADAPTER_VF_NAME_DEF

                # 备注：该函数的适配器名称(内)与适配器名称(外) ，形参与实参相反
                rtn_code, _, _, new_ip = VmAdapter.update_vm_adapter_name_ip_gateway_address(
                    vm_name=vm_name, vm_adapter_name=v_adapter_name, v_adapter_name=vm_adapter_name,
                    new_ip=cls.vm_vf_ip[vm_name], prefix_length=cls.vm_vf_submask[vm_name], new_gateway="",
                    vm_adapter_ifdesc_kw="LD 1160-2X", cmd_execute_address=execute_address)
                if rtn_code:
                    log.error(f"{execute_address}: 虚拟机测试通路适配器配置ip、submask、gateway、名称失败")
                    rtn_status = False
                    return rtn_status
                # 修改vf网卡名称(仅SRIOV)
                if virtual_mode == VirtualModeEnum.SR_IOV.value:
                    rtn_set = \
                        VmAdapter.update_vf_adapter_name(vm_name=vm_name, vm_adapter_name=v_adapter_name,
                                                         vf_name=vm_vf_name, cmd_execute_address=execute_address)
                    log.info(rtn_set)
                    if len(rtn_set) >= 3:
                        log.error("修改vf网卡名称(仅SRIOV)失败")
                        rtn_status = False
                        return rtn_status
                    else:
                        status = rtn_set[0]
                        if RtnStatusEnum.SUCCESS.value != status:
                            log.error("修改vf网卡名称(仅SRIOV)失败")
                            rtn_status = False
                            return rtn_status
                        else:
                            log.info("修改vf网卡名称(仅SRIOV)成功")
                # 配置完成后打印ipconfig
                status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd="ipconfig", win_vm_ip=CommonOperation.get_win_vm_ip(execute_address, vm_name),
                    cmd_execute_address=execute_address)
                if not status:
                    log.info(out)

                # # 获取vf name(old)
                # old_name_list = CommonOperation.get_net_adapter_name(win_vm_ip=vm_ip, execute_address=execute_address)
                # # 设置vf name(若vf名称不符合预定格式，否则保持原样)
                # new_name_list = []
                # for i, name in enumerate(old_name_list):
                #     res = CommonOperation.set_vm_vf_name_format(name, vm_name, vm_ip, i,
                #                                                 cmd_execute_address=execute_address)
                #     if res:
                #         new_name_list.append(res)
                # # 设置vf ip和submask
                # for name in new_name_list:
                #     CommonOperation.set_vm_vf_ip_subnetmask(vswitch_ip, vswitch_submask, name, vm_name, vm_ip,
                #                                             cmd_execute_address=execute_address)
            return rtn_status
        else:
            from scripts.script_libs.windows_hyperv_manage_vm import KvmOp, VmAdapter, VmSwitch
            rtn_status = True

            if not adapter_config:
                log.info("************establish_win_vm_test_channel***************")
                # 1. 若虚拟机未关机，先关闭
                vm_status = KvmOp.check_vm_state(vm_name=constants.KVM_VM_NAME, cmd_execute_address=execute_address)
                log.info(f"{constants.KVM_VM_NAME}: {vm_status}")
                if vm_status == "running":
                    status = KvmOp.stop_vm(vm_name=constants.KVM_VM_NAME, execute_address=execute_address)
                    if status == RtnStatusEnum.FAIL.value:
                        log.error("关闭虚拟机失败")
                        rtn_status = False
                        return rtn_status
                    log.info("关闭虚拟机成功")

                # 2. 测试通路-物理机创建测试网卡的vf
                if execute_address == CmdExecuteAdressEnum.CLIENT.value:
                    test_nic_name = device_name_client
                else:
                    test_nic_name = device_name_server
                log.info(f"使用{test_nic_name}创建测试vf")
                # 创建测试vf
                vf_nic_name, vf_nic_bdf = KvmOp.create_vf_of_nic(test_nic_name, vf_num,
                                                                 cmd_execute_address=execute_address)
                vf_prop_dict = KvmOp.get_vf_prop_of_nic(test_nic_name, cmd_execute_address=execute_address)
                for i in range(vf_num):
                    vf_id = vf_prop_dict[str(i)]['vf']
                    vf_nic_name = vf_prop_dict[str(i)]['vf_device']
                    vf_nic_bdf = vf_prop_dict[str(i)]['bdf']
                    if not vf_nic_name:
                        log.error("创建测试vf失败")
                        rtn_status = False
                        return rtn_status
                    else:
                        log.info(f"创建测试vf成功：{vf_nic_name}, {vf_nic_bdf}")
                CommonOperation.save_vf_name(constants.KVM_VM_NAME, execute_address, vf_prop_dict["0"]['vf_device'])

                # 3. 测试通路-虚拟机添加测试网卡PCI设备
                if not KvmOp.check_vm_nic_pci_exist(vm_name=constants.KVM_VM_NAME, vf_nic_bdf=vf_nic_bdf):
                    # 添加网络适配器
                    status = KvmOp.add_vm_nic_pci(vm_name=constants.KVM_VM_NAME, vf_nic_bdf=vf_nic_bdf,
                                                  domain_id="0x0000")
                    if status == RtnStatusEnum.FAIL.value:
                        log.error(f"{execute_address}:虚拟机{vm_name}添加网卡PCI设备失败！")
                        rtn_status = False
                        return rtn_status
                else:
                    log.info(f"{vm_name}已存在网卡PCI设备")
            else:
                log.info("************establish_win_vm_test_channel, adapter_config***************")
                # 3. 测试通路--配置虚拟机网络适配器ip、submask、gateway、名称
                # 获取pf name
                if execute_address == CmdExecuteAdressEnum.SERVER.value:
                    res = re.findall(r"(\w+)v\d+", device_name_server)
                    if res:
                        pf_name = res[0]
                    else:
                        pf_name = device_name_server
                else:
                    res = re.findall(r"(\w+)v\d+", device_name_client)
                    if res:
                        pf_name = res[0]
                    else:
                        pf_name = device_name_client
                pf_prop_dict = KvmOp.get_pf_prop_of_nic(pf_name, cmd_execute_address=execute_address)
                # 获取pf ip
                pf_ip = pf_prop_dict.get("ipv4")
                # 获取pf submask
                pf_submask = pf_prop_dict.get("ipv4_submask")
                # 获取pf mac_addr
                pf_mac_addr = pf_prop_dict.get("macaddr")

                # 获取vm管理ip
                win_vm_ip = CommonOperation.get_win_vm_ip(vm_name=vm_name, execute_address=execute_address)

                def add_one(matched):
                    # 定义函数：将匹配的数字加 1
                    value_1 = int(matched.group('pos1')) + 1
                    value_2 = int(matched.group('pos2'))
                    value_3 = int(matched.group('pos3'))
                    value_4 = int(matched.group('pos4')) + 1
                    return ".".join([str(value_1), str(value_2), str(value_3), str(value_4)])

                # vf ip = pf ip最低位+1
                cls.vm_vf_ip[vm_name] = re.sub('(?P<pos1>\d+)\.(?P<pos2>\d+)\.(?P<pos3>\d+)\.(?P<pos4>\d+)',
                                               add_one, pf_ip)
                # cls.vm_vf_ip[vm_name] = "193.172.10.15"
                # vf submask = pf submask
                cls.vm_vf_submask[vm_name] = pf_submask
                # cls.vm_vf_submask[vm_name] = "255.255.255.0"
                v_adapter_name = constants.KVM_VF_ADAPTER_NAME
                vm_adapter_name = constants.KVM_VF_ADAPTER_NAME
                vm_vf_name = constants.KVM_VF_ADAPTER_NAME

                # todo KVM windows虚拟机内部的ip设置，待完成
                rtn_code, _, _, new_ip = VmAdapter.update_vm_adapter_name_ip_gateway_address(
                    vm_name='', vm_adapter_name=v_adapter_name, v_adapter_name=vm_adapter_name,
                    new_ip=cls.vm_vf_ip[vm_name], prefix_length=cls.vm_vf_submask[vm_name], new_gateway="",
                    vm_adapter_ifdesc_kw=None, cmd_execute_address=execute_address, virtual_ip=win_vm_ip)
                if rtn_code:
                    log.error(f"{execute_address}: 虚拟机测试通路适配器配置ip、submask、gateway、名称失败")
                    rtn_status = False
                    return rtn_status
                # 修改vf网卡名称(仅SRIOV)
                if virtual_mode == VirtualModeEnum.SR_IOV.value:
                    rtn_set = \
                        VmAdapter.update_vf_adapter_name(vm_name='', vm_adapter_name=v_adapter_name,
                                                         vf_name=vm_vf_name, cmd_execute_address=execute_address,
                                                         win_vm_ip=win_vm_ip)
                    log.info(rtn_set)
                    if len(rtn_set) >= 3:
                        log.error("修改vf网卡名称(仅SRIOV)失败")
                        rtn_status = False
                        return rtn_status
                    else:
                        status = rtn_set[0]
                        if RtnStatusEnum.SUCCESS.value != status:
                            log.error("修改vf网卡名称(仅SRIOV)失败")
                            rtn_status = False
                            return rtn_status
                        else:
                            log.info("修改vf网卡名称(仅SRIOV)成功")
                # 配置完成后打印ipconfig
                status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd="ipconfig", win_vm_ip=win_vm_ip, cmd_execute_address=execute_address)
                if not status:
                    log.info(out)
            return rtn_status

    @classmethod
    def get_vm_switch_info(cls, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                           is_all: bool = False) -> list:
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 获取Get-VMSwitch信息
        """
        rtn_list = []
        if is_all:
            cmd = "Get-VMSwitch |Format-List *"
        else:
            cmd = "Get-VMSwitch |Format-List"
        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=execute_address)
        if not out:
            return rtn_list
        info_list = out.lstrip().split("\n")
        temp_dict = {}
        for info in info_list:
            if not re.findall(r"\S+", info):
                rtn_list.append(temp_dict.copy())
                temp_dict.clear()
            else:
                res = re.findall(r"(\w+)\s+:(.*)", info)
                if res:
                    temp_dict[res[0][0]] = res[0][1].strip()
        log.info("get_vm_switch_info:{}".format(rtn_list))
        return rtn_list

    @classmethod
    def get_vm_switch_name(cls, execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> list:
        """
        author: xiangyu.liu
        date: 2023.10.31
        description: 获取vm_switch名称
        """
        rtn_list = []
        vm_switch_list = CommonOperation.get_vm_switch_info(execute_address=execute_address)
        if not vm_switch_list:
            log.warning("未查询到vm_switch")
            return rtn_list
        for info_dict in vm_switch_list:
            rtn_list.append(info_dict["Name"])
        return rtn_list

    @classmethod
    def dict_compare(cls, dict1, dict2):
        different_desc = []
        rtn_code = RtnStatusEnum.SUCCESS.value
        for key, value in dict2.items():
            if key not in dict1 or dict1[key] != value:
                different_desc.append(key)
                rtn_code = RtnStatusEnum.FAIL.value
        return rtn_code, different_desc

    @classmethod
    def nic_information_presistence(cls, caller_cls, ip_addr: str,
                                    interface: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2023.11.07
        description:网卡信息持久化
        """
        # 需删除已有的配置文件
        delete_file = "/etc/sysconfig/network-scripts/ifcfg-{}".format(interface)
        cmd = "rm -rf {}".format(delete_file)
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_stdout:{}, rtn_stderr:{}".format(rtn_code, rtn_stdout, rtn_stderr))
        delete_file_other = "/etc/sysconfig/network-scripts/ifcfg-{}-*".format(interface)
        cmd = "rm -rf {}".format(delete_file_other)
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_stdout:{}, rtn_stderr:{}".format(rtn_code, rtn_stdout, rtn_stderr))
        create_interface = \
            f"{constants.NMCLI} con add ifname {interface} con-name {interface} type ethernet ipv4.addresses " \
            f"{ip_addr} ipv4.method manual autoconnect yes"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=create_interface, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f"执行创建网卡的持久化文件命令，{create_interface}")
        else:
            log.error(f"执行创建网卡的持久化文件命令，{create_interface}失败")
            exit(ExitCodeEnum.EXIT_FAIL.value)
        # activate_interface = "systemctl restart NetworkManager"
        # rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
        #     cmd=activate_interface, cmd_execute_address=cmd_execute_address)
        # log.info("rtn_code:{}, rtn_stdout:{}, rtn_stderr:{}".format(rtn_code, rtn_stdout, rtn_stderr))
        # 从软件关闭网卡
        rtn_down, down_stdout, down_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=f"{constants.IFDOWN} {interface}", cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_stdout:{}, rtn_stderr:{}".format(rtn_code, rtn_stdout, rtn_stderr))
        if "command not found" in down_stdout + down_stderr or "unknown connection" in down_stdout + down_stderr:
            command = "nmcli connection down {}".format(interface)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root'
            )
            log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

        rtn_up, up_stdout, up_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=f"{constants.IFUP} {interface}", cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_stdout:{}, rtn_stderr:{}".format(rtn_code, rtn_stdout, rtn_stderr))

        if "command not found" in up_stdout + up_stderr or "unknown connection" in up_stdout + up_stderr:
            command = "nmcli connection down {}".format(interface)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root'
            )
            log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

    @classmethod
    def delete_interface_information(cls, caller_cls, interface: str,
                                     cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2023.11.07
        description: 删除网卡的持久化文件
        """
        exec_command = f"{constants.NMCLI} connection delete {interface}"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        cls.check_cmd_execute_success(caller_class=caller_cls, status=rtn_code, result=rtn_stderr,
                                      cmd=exec_command
                                      )

    @classmethod
    def check_cmd_execute_success(cls, caller_class, status: int, result: str, cmd: str):
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 检查指令是否执行成功
        :return: 无返回值
        """
        if CmdStatusEnum.SUCCESS.value == status:
            log.info_caller('cmd execute success [{}]'.format(cmd))
            log.info_caller('get result:\n{}'.format(result))
        else:
            log.info_caller('cmd execute fail [{}]'.format(cmd))
            log.info_caller('get result:\n{}'.format(result))
            # 如果是环境检查完成前进行命令检查，则不报bug
            if caller_class.own_environment_enabled:
                caller_class.set_bug_type(BugTypeEnum.FUNCTION.value)
                caller_class.bug_title = '指令执行失败[{}]'.format(cmd)
                caller_class.bug_result = "指令执行返回status = {}".format(status)
                caller_class.bug_expect = "指令执行返回status = {}".format(CmdStatusEnum.SUCCESS.value)
                caller_class.create_bug("cmd execute fail [{}]".format(cmd))

    @classmethod
    def write_vm_env_conf(cls, conf_info: str, vm_name: str,
                          vm_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 內容寫入配置文件vm_env_conf(client和server各scp一份)
        :return: str
        """
        from scripts.script_libs.file_operation import FileOperation
        server_ip, client_ip = CommandOperation.get_logical_ip_form_config()
        if vm_address == CmdExecuteAdressEnum.SERVER.value:
            vm_vf_ip = CommonOperation.get_vm_vf_ip()
            if vm_vf_ip:
                server_ip = vm_vf_ip
        else:
            vm_vf_ip = CommonOperation.get_vm_vf_ip()
            if vm_vf_ip:
                client_ip = vm_vf_ip

        FileOperation.write_file_base_scp(
            client_ip, CommonOperation.get_vm_env_conf_path(cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value),
            conf_info, match_flag=False, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
        FileOperation.write_file_base_scp(
            server_ip, CommonOperation.get_vm_env_conf_path(cmd_execute_address=CmdExecuteAdressEnum.SERVER.value),
            conf_info, match_flag=False, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)

    @classmethod
    def set_vm_name(cls, vm_name: str = "", cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 设置虚拟机名称
        :return: 无返回值
        """
        cls.vm_name = vm_name

    @classmethod
    def get_vm_name(cls, execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 获取虚拟机名称
        :return: 无返回值
        """
        return cls.vm_name

    @classmethod
    def save_vm_ip(cls, vm_name: str, execute_address: str, vm_ip: str):
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 获取虚拟机名称
        :return: 无返回值
        """
        cls.vm_ip[execute_address] = {vm_name: vm_ip}
        log.info(f"after save_vm_ip, all vm ip :\n{cls.vm_ip}")

    @classmethod
    def get_win_vm_ip(cls, execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value, vm_name: str = None):
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 获取虚拟机名称
        :return: 无返回值
        """

        def get_win_vm_manage_ip(execute_address: str, vm_name: str, kvm_windows: bool = False) -> str:
            cmd = "Get-NetIPAddress|?{$_.AddressFamily -like 'IPv4'}|?{$_.InterfaceAlias -like '" + \
                  constants.VM_ADAPTER_MANAGER_NAME_DEF + "'}"
            get_ip_cmd = CommandOperation.concat_invoke_command(vm_name=vm_name, cmd=cmd, kvm_windows=kvm_windows)
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_multi_times(
                cmd=get_ip_cmd, cmd_execute_address=execute_address, timeout=30)
            log.info("cmd_code: {}, cmd_stdout: {}".format(cmd_code, cmd_stdout))
            if RtnStatusEnum.SUCCESS.value == cmd_code:
                res = re.findall(r"IPAddress\s+:\s+(\S+)", cmd_stdout)
                if res:

                    vm_ip = res[0]
                    return vm_ip
                else:
                    return ""
            else:
                return ""

        vm_ip = ""
        if vm_name is None:
            vm_name = cls.vm_name
        if vm_name is not None:
            host_os_server, host_os_client = CommonOperation.get_nic_os()
            # windows物理机
            if (HostOsEnum.WINDOWS.value in host_os_client and
                execute_address == CmdExecuteAdressEnum.CLIENT.value) or \
                    (HostOsEnum.WINDOWS.value in host_os_server and
                     execute_address == CmdExecuteAdressEnum.SERVER.value):
                # ip已保存
                if cls.vm_ip.get(execute_address):
                    # ip未保存
                    if not cls.vm_ip.get(execute_address).get(vm_name):
                        # 获取vm 管理网卡的ip
                        # vm_ip = CommonOperation.get_conf_vm_ip(vm_name=vm_name, execute_address=execute_address)
                        vm_ip = get_win_vm_manage_ip(execute_address, vm_name)
                        cls.save_vm_ip(vm_name=vm_name, execute_address=execute_address, vm_ip=vm_ip)
                    # ip已保存
                    else:
                        vm_ip = cls.vm_ip.get(execute_address).get(vm_name)
                # ip未保存
                else:
                    # 获取vm 管理网卡的ip
                    vm_ip = get_win_vm_manage_ip(execute_address, vm_name)
                    cls.save_vm_ip(vm_name=vm_name, execute_address=execute_address, vm_ip=vm_ip)
                log.info("win_vm_ip:{}".format(vm_ip))
            # Linux物理机
            elif (((HostOsEnum.CENTOS.value in host_os_client) or ('linux' in host_os_client)) and
                  execute_address == CmdExecuteAdressEnum.CLIENT.value) or \
                    (((HostOsEnum.CENTOS.value in host_os_server) or ('linux' in host_os_server)) and
                     execute_address == CmdExecuteAdressEnum.SERVER.value):
                # ip已保存
                if cls.vm_ip.get(execute_address):
                    # ip未保存
                    if not cls.vm_ip.get(execute_address).get(vm_name):
                        # 获取vm 管理网卡的ip
                        # vm_ip = CommonOperation.get_conf_vm_ip(vm_name=vm_name, execute_address=execute_address)
                        vm_ip = get_win_vm_manage_ip(execute_address, vm_name, kvm_windows=True)
                        cls.save_vm_ip(vm_name=vm_name, execute_address=execute_address, vm_ip=vm_ip)
                    # ip已保存
                    else:
                        vm_ip = cls.vm_ip.get(execute_address).get(vm_name)
                # ip未保存
                else:
                    # 获取vm 管理网卡的ip
                    vm_ip = get_win_vm_manage_ip(execute_address, vm_name, kvm_windows=True)
                    cls.save_vm_ip(vm_name=vm_name, execute_address=execute_address, vm_ip=vm_ip)
                log.info("win_vm_ip:{}".format(vm_ip))
            else:
                log.warning("未识别的 host_os_server:{}, host_os_client:{}".format(host_os_server, host_os_client))
            return vm_ip
        else:
            log.error(f"vm_name: {vm_name}")
            return ""

    @classmethod
    def save_vf_name(cls, vm_name: str, execute_address: str, vf_name: str):
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 获取虚拟机名称
        :return: 无返回值
        """
        cls.vf_name[execute_address] = {vm_name: vf_name}
        log.info(f"after save_vf_name, all vf name :\n{cls.vf_name}")

    @classmethod
    def get_vf_name(cls, execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value, vm_name: str = None):
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 获取虚拟机名称
        :return: 无返回值
        """
        return cls.vf_name.get(execute_address).get(vm_name)

    @classmethod
    def get_conf_vm_name(cls, execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 获取虚拟机名称
        :return: 无返回值
        """
        vm_name = ""
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        vm_os = CommandLineArgsParse.get_host_os()
        if (HostOsEnum.WINDOWS.value in host_os_client and execute_address == CmdExecuteAdressEnum.CLIENT.value) or \
                (
                        HostOsEnum.WINDOWS.value in host_os_server and execute_address == CmdExecuteAdressEnum.SERVER.value) or \
                (
                        HostOsEnum.WINDOWS.value not in host_os_client and execute_address == CmdExecuteAdressEnum.CLIENT.value and "windows" in vm_os) or \
                (
                        HostOsEnum.WINDOWS.value not in host_os_server and execute_address == CmdExecuteAdressEnum.SERVER.value and "windows" in vm_os):
            cls.vm_env_conf_dict = CommonOperation.analysis_vm_env_conf_info()
            vm_name = list(cls.vm_env_conf_dict.keys())[0]
            log.info(f"vm_name:{vm_name}")
        return vm_name

    @classmethod
    def get_conf_vm_ip(cls, vm_name: str, execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 获取虚拟机管理ip
        :return: 无返回值
        """
        vm_ip = ""
        if not vm_name:
            return vm_ip
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        if (HostOsEnum.WINDOWS.value in host_os_client and execute_address == CmdExecuteAdressEnum.CLIENT.value) or \
                (HostOsEnum.WINDOWS.value in host_os_server and execute_address == CmdExecuteAdressEnum.SERVER.value):
            cls.vm_env_conf_dict = CommonOperation.analysis_vm_env_conf_info()
            vm_ip = cls.vm_env_conf_dict[vm_name]["ip"].strip()
            log.info(f"{vm_name} vm_ip:{vm_ip}")
        return vm_ip

    @classmethod
    def get_conf_vm_submask(cls, vm_name: str, execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 获取虚拟机管理ip子网掩码
        :return: 无返回值
        """
        vm_submask = ""
        if not vm_name:
            return vm_submask
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        if (HostOsEnum.WINDOWS.value in host_os_client and execute_address == CmdExecuteAdressEnum.CLIENT.value) or \
                (HostOsEnum.WINDOWS.value in host_os_server and execute_address == CmdExecuteAdressEnum.SERVER.value):
            cls.vm_env_conf_dict = CommonOperation.analysis_vm_env_conf_info()
            vm_submask = cls.vm_env_conf_dict[vm_name]["submask"].strip()
            log.info(f"{vm_name} vm_submask:{vm_submask}")
        return vm_submask

    @classmethod
    def get_conf_vm_gateway(cls, vm_name: str, execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 获取虚拟机管理ip网关
        :return: 无返回值
        """
        vm_gateway = ""
        if not vm_name:
            return vm_gateway
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        if (HostOsEnum.WINDOWS.value in host_os_client and execute_address == CmdExecuteAdressEnum.CLIENT.value) or \
                (HostOsEnum.WINDOWS.value in host_os_server and execute_address == CmdExecuteAdressEnum.SERVER.value):
            cls.vm_env_conf_dict = CommonOperation.analysis_vm_env_conf_info()
            vm_gateway = cls.vm_env_conf_dict[vm_name]["gateway"].strip()
            log.info(f"{vm_name} vm_gateway:{vm_gateway}")
        return vm_gateway

    @classmethod
    def set_vm_vf_name_format(cls, old_name: str, vm_name: str, vm_ip: str, vf_index: int,
                              cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> str:
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 若虚拟机【vm_name】VF网卡的【old_name】不符合规范，修改为规范名称并返回新名称
                     若虚拟机【vm_name】VF网卡的【old_name】符合规范，返回【old_name】
                     若虚拟机【vm_name】VF网卡的【old_name】含hyper-v，则认为不是vf网卡，不处理并返回空
        :return: str
        """
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        if (HostOsEnum.WINDOWS.value in host_os_client and
            cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value) or \
                (HostOsEnum.WINDOWS.value in host_os_server and
                 cmd_execute_address == CmdExecuteAdressEnum.SERVER.value):
            from scripts.script_libs.file_operation import FileOperation
            vf_index_min = 1
            if not re.findall(r"{}(\d+)".format(constants.VM_ADAPTER_TEST_PREFIX_DEF), old_name):
                if constants.VM_ADAPTER_VF_PREFIX_DEF not in old_name and \
                        constants.VM_ADAPTER_MANAGER_NAME_DEF not in old_name:
                    new_name = "{}{}".format(constants.VM_ADAPTER_TEST_PREFIX_DEF, vf_index_min + vf_index)
                    CommonOperation.set_net_adapter_name(old_name, new_name, win_vm_ip=vm_ip)
                    # vm vf信息写入配置文件
                    # cls.write_vm_env_conf_info += f"VF_NAME {new_name}\n"
                    # CommonOperation.write_vm_env_conf(cls.write_vm_env_conf_info, vm_name,
                    # vm_address=cmd_execute_address)
                    log.info(f"set adapter name {old_name} -> {new_name}")
                    return new_name
                else:
                    # sxe-vf-和hyper-v-manager不纳入统计
                    log.warning(f"not {constants.VM_ADAPTER_TEST_PREFIX_DEF}[number] and"
                                f" ({constants.VM_ADAPTER_VF_PREFIX_DEF} in old_name or"
                                f" {constants.VM_ADAPTER_MANAGER_NAME_DEF} in old_name)")
                    return ""
            else:
                # 不修改，返回原name
                log.info(f"already right name {old_name}, return")
                return old_name

    @classmethod
    def set_vm_vf_ip_subnetmask(cls, vswitch_ip: str, vswitch_submask: str, adapter_name: str,
                                vm_name: str, vm_ip: str,
                                cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 根据物理机虚拟交换机的IP【vswitch_ip】和子网掩码【vswitch_submask】，
        修改虚拟机【vm_name】VF网卡【adapter_name】的IP和子网掩码
        :return: 无返回值
        """
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        if (HostOsEnum.WINDOWS.value in host_os_client and
            cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value) or \
                (HostOsEnum.WINDOWS.value in host_os_server and
                 cmd_execute_address == CmdExecuteAdressEnum.SERVER.value):
            from scripts.script_libs.file_operation import FileOperation
            # 定义函数：将匹配的数字加 1

            def add_one(matched):
                value_1 = int(matched.group('pos1'))
                value_2 = int(matched.group('pos2'))
                value_3 = int(matched.group('pos3')) + 1
                value_4 = int(matched.group('pos4')) + 1
                return ".".join([str(value_1), str(value_2), str(value_3), str(value_4)])

            # vswitch ip最低位 + 1 ，作为vf ip
            cls.vm_vf_ip[vm_name] = re.sub('(?P<pos1>\d+)\.(?P<pos2>\d+)\.(?P<pos3>\d+)\.(?P<pos4>\d+)',
                                           add_one, vswitch_ip)
            # vswitch submask = vf submask
            cls.vm_vf_submask[vm_name] = vswitch_submask

            CommonOperation.set_net_adapter_static_ip(adapter_name, cls.vm_vf_ip[vm_name], cls.vm_vf_submask[vm_name],
                                                      win_vm_ip=vm_ip, execute_address=cmd_execute_address)
            # cls.write_vm_env_conf_info += f"VF_IP {cls.vm_vf_ip[vm_name]}\n"\
            #                               f"VF_SUBMASK {cls.vm_vf_submask[vm_name]}\n"
            # CommonOperation.write_vm_env_conf(cls.write_vm_env_conf_info, vm_name, vm_address=cmd_execute_address)

    @classmethod
    def get_vm_vf_ip(cls) -> dict:
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 在虚拟机上获取VF网卡的IP
        :return: 无返回值
        """
        return cls.vm_vf_ip

    @classmethod
    def get_vm_vf_ipv6(cls) -> dict:
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 在虚拟机上获取VF网卡的IP
        :return: 无返回值
        """
        return cls.vm_vf_ip

    @classmethod
    def set_rpc_port(cls, port: int):
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 在虚拟机上获取VF网卡的IP
        :return: 无返回值
        """
        cls.rpc_port = port

    @classmethod
    def get_rpc_port(cls) -> int:
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 在虚拟机上获取VF网卡的IP
        :return: 无返回值
        """
        return cls.rpc_port

    @classmethod
    def analysis_vm_env_conf_info(cls, current_config: str = NIC_WIN_VM_CONFIG_PATH) -> dict:
        """
        author:      xiangyu.liu
        date:        2020-10-14 15:24:08
        description: 读取本地文件
        :param current_config: 本地文件
        :return:     返回文件内容
        """
        rtn_dict = {}
        # 读取配置文件vm_env_conf
        config = configparser.ConfigParser()
        config.read(current_config)
        try:
            vm_os_options = config.options('vm_os')
        except:
            log.warning(f"在{current_config}中获取vm_os字段失败, 赋默认值vm_os: sxevm001 = 'windows'")
            vm_os_options = ['sxevm001']
        submask_options = config.options('submask')
        gateway_options = config.options('gateway')
        vm_ip_options = config.options('vm_ip')
        vf_ip_options = config.options('vf_ip')

        # 初始化返回字典
        for key in vm_ip_options:
            rtn_dict[key] = {}

        # 填写配置文件内容到返回字典
        for vm_name in rtn_dict.keys():
            # 填写vm_os
            try:
                if vm_name in vm_os_options:
                    rtn_dict[vm_name]["os"] = config['vm_os'][vm_name].replace('"', '')
                else:
                    rtn_dict[vm_name]["os"] = ''
            except:
                log.warning(f"在{current_config}中获取vm_os字段失败, 赋默认值vm_os: sxevm001 = 'windows'")
                rtn_dict[vm_name]["os"] = 'windows'
            # 填写vm_ip
            if vm_name in vm_ip_options:
                rtn_dict[vm_name]["ip"] = config['vm_ip'][vm_name]
            else:
                rtn_dict[vm_name]["ip"] = ""
            # 填写submask
            if vm_name in submask_options:
                rtn_dict[vm_name]["submask"] = config["submask"][vm_name]
            else:
                rtn_dict[vm_name]["submask"] = config["submask"]['default']
            # 填写gateway
            if vm_name in gateway_options:
                rtn_dict[vm_name]["gateway"] = config["gateway"][vm_name]
            else:
                rtn_dict[vm_name]["gateway"] = config["gateway"]["default"]
            # 填写vf_ip
            if vm_name in vf_ip_options:
                rtn_dict[vm_name]["vf_ip"] = config["vf_ip"][vm_name]
            else:
                rtn_dict[vm_name]["vf_ip"] = ""
        return rtn_dict

    @classmethod
    def get_vm_env_conf_path(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> str:
        """
        author: xiangyu.liu
        date  : 2020.08.17
        description: 获取虚拟机配置文件目录
        :return: 无返回值
        """
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        if (HostOsEnum.WINDOWS.value in host_os_client and
            cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value) or (
                HostOsEnum.WINDOWS.value in host_os_server and
                cmd_execute_address == CmdExecuteAdressEnum.SERVER.value):
            vm_conf_path = 'C:/Users/Administrator/sxetest/' + 'vm_env_config'
        else:
            vm_conf_path = '/root/sxetest/' + 'vm_env_config'
        return vm_conf_path

    @classmethod
    def attach_test_steps_info(cls, caller_class, msg: str):
        """
        author: junfeng.he
        date  : 2020.08.17
        description: 打印并且添加测试步骤信息
        :return: 无返回值
        """
        log.info_caller(msg)
        msg = time.strftime("%Y-%m-%d %H:%M:%S ", time.localtime()) + msg
        caller_class.test_steps += msg

    @classmethod
    def get_dpdk_version(cls, execute_address: str = "", ssh_ip: str = "") -> str:
        """
        author: junfeng.he
        date  : 2023.11.16
        description: 获取环境中当前使用的dpdk工具版本
        :return: dpdk_version
        """
        dpdk_version = "20.11.5"
        exec_command = f"cat {constants.LINUX_FILE_PATH_ROOT}/dpdk/version.txt"
        if ssh_ip:
            status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, ssh_ip=ssh_ip)
        elif execute_address:
            status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=execute_address)
        else:
            status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        dpdk_versions = re.findall(r'dpdk_version:([\.\d]+)', out)
        if dpdk_versions:
            dpdk_version = dpdk_versions[0]
        log.info("获取环境中当前使用的dpdk工具版本：{}".format(dpdk_version))
        return dpdk_version

    @classmethod
    def is_os_support_xdp(cls, exec_address) -> bool:
        """
        author: junfeng.he
        date  : 2023.11.16
        description: 获取环境中当前使用的dpdk工具版本
        :return: dpdk_version
        """
        not_support_xdp_os_list = ["NFSChina_4.0_0612", "NFSChina_4.0_0613", "NFSChina_4.0_0801", "NFSChina_4.0_0408",
                                   "rhel_7.", "centos_7.",
                                   "UOS_V20_1050", "UOS_SERVER_20",
                                   "Kylin_V10_NOT_SP3", "KylinSec"]
        os_version = "unknow"
        # 判断是否是Ubuntu
        exec_command = "uname -a"
        rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
            exec_command, cmd_execute_address=exec_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
        kylin_not_ps3_os_version = False
        if 'KylinSP3' not in rtn_outputs and 'Kylin03' not in rtn_outputs:
            kylin_not_ps3_os_version = True
        if 'ubuntu' in rtn_outputs.lower():
            os_version = 'ubuntu_22.04'
        else:
            # 判断centos具体版本
            exec_command = "cat /etc/redhat-release"
            rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=exec_address)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
            log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
            if "CentOS" in rtn_outputs:
                versions = re.findall(r'release (\d\.)', rtn_outputs.lower())
                if versions:
                    os_version = "centos_{}".format(versions[0])
            elif "Red Hat" in rtn_outputs:
                versions = re.findall(r'release (\d\.)', rtn_outputs.lower())
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
                rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                    exec_command, cmd_execute_address=exec_address)
                log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
                if "Kylin Linux Advanced Server" in rtn_outputs:
                    if kylin_not_ps3_os_version:
                        # 非SP3版本麒麟，当前不支持XDP
                        os_version = 'Kylin_V10_NOT_SP3'
                    else:
                        os_version = 'Kylin_V10_SP3'
                if "KylinSec" in rtn_outputs:
                    os_version = 'KylinSec'
                if "UnionTech OS Server" in rtn_outputs:
                    os_version = 'UOS_V20_1050'
                if "UOS Server 20" in rtn_outputs:
                    os_version = 'UOS_SERVER_20'
                if "Anolis OS" in rtn_outputs:
                    os_version = 'AnolisOS_8.8'
                if "openEuler" in rtn_outputs:
                    os_version = 'openEuler_22.03_LTS'

        if os_version in not_support_xdp_os_list:
            log.warning("os_version:{},暂时不支持xdp测试".format(os_version))
            return False
        else:
            log.info("os_version:{},支持xdp测试".format(os_version))
            return True

    @classmethod
    def get_full_path(cls, ori_path, exec_addr):
        cmd = f'find {ori_path}'
        _, out_put, _= CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd, cmd_execute_address=exec_addr)
        if out_put:
            return out_put
        else:
            log.info('获取文件路径失败')
            return ""

    @classmethod
    def update_vm_rpc_server_file(cls, caller_class, vm_ip: str, exec_address: str) -> bool:
        """
        author: xiangyu.liu
        date  : 2023.11.16
        description: 更新虚拟机中的rpc_server.py、rpc_client.py
        :return: bool
        """
        from scripts.script_libs.file_operation import FileOperation
        from scripts.script_libs import constants as scripts_constants
        from framework.model.sagitta import constants as tj_constants

        # 定义函数
        def getstatusoutput(exec_command) -> tuple:
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

        if not vm_ip:
            return False
        log.info(f"更新{exec_address}虚拟机[{vm_ip}]中的rpc_server.py、rpc_client.py")

        rtn_status = True
        # 获取os、ip信息
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        guest_os_server, guest_os_client = CommonOperation.get_guest_os(caller_class.test_direction_reverse)

        # 整理env_config_path、root值
        target_host_ip = vm_ip
        target_execute_address = exec_address
        # 目标vm是server且是windows 或 目标vm是client且是windows
        if (target_execute_address == CmdExecuteAdressEnum.SERVER.value and
            host_os_server == HostOsEnum.WINDOWS.value) or \
                (target_execute_address == CmdExecuteAdressEnum.CLIENT.value and
                 host_os_client == HostOsEnum.WINDOWS.value) or \
                (target_execute_address == CmdExecuteAdressEnum.SERVER.value and
                 guest_os_server == HostOsEnum.WINDOWS.value) or \
                (target_execute_address == CmdExecuteAdressEnum.CLIENT.value and
                 guest_os_client == HostOsEnum.WINDOWS.value):
            env_config_path = tj_constants.WINDOWS_FILE_PATH_ROOT
            root = "Administrator"
            bin_path = env_config_path
        else:
            env_config_path = tj_constants.LINUX_FILE_PATH_ROOT
            root = "root"
            bin_path = "/usr/bin/"

        # 创建文件夹
        vm, rpc_port = CommonOperation.get_node_info_from_path()
        log.info("vm:{},rpc_port:{}".format(vm, rpc_port))
        vm_path = "{}{}".format(env_config_path, vm)
        if root == "Administrator":
            exec_command = "New-Item -Path {} -Name {} -Type directory".format(env_config_path, vm)
        else:
            exec_command = 'mkdir -p {}'.format(vm_path)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
            ssh_ip=target_host_ip,
            host_os_server=host_os_server,
            host_os_client=host_os_client,
            win_vm_ip=vm_ip
        )
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

        # 拷贝前需要更新对应环境的ip地址，由于有2个环境需要
        file_content = ""
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

        exec_command = f'scp {scripts_constants.NIC_RPC_SERVER_PATH} {root}@{target_host_ip}:{vm_path}/'
        rtn_code, result = getstatusoutput(exec_command)
        log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            log.info("拷贝失败！")
        elif root != "Administrator":
            exec_command = f'chmod 777 {vm_path}/rpc_server.py'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                ssh_ip=target_host_ip,
                host_os_server=host_os_server,
                host_os_client=host_os_client,
                win_vm_ip=vm_ip
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

        exec_command = f'scp {scripts_constants.NIC_RPC_CLIENT_PATH} {root}@{target_host_ip}:{vm_path}/'
        rtn_code, result = getstatusoutput(exec_command)
        log.info("cmd:{}, status:{}, result:{}".format(exec_command, rtn_code, result))
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            log.info("拷贝失败！")
        elif root != "Administrator":
            exec_command = f'chmod 777 {vm_path}/rpc_client.py'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=target_execute_address, ssh_username=f'{root}',
                ssh_ip=target_host_ip,
                host_os_server=host_os_server,
                host_os_client=host_os_client,
                win_vm_ip=vm_ip
            )
            log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        # 文件scp过后，需要还原
        FileOperation.write_local_file(scripts_constants.NIC_RPC_CLIENT_PATH, file_content1)

    @classmethod
    def check_driver_irq_mode(cls, mode: int, device_name: str, cmd_execute_address: str) -> bool:
        info_dict = EthtoolOperation.show_driver_infomation(device_name=device_name,
                                                            cmd_execute_address=cmd_execute_address)
        if mode not in [0, 1, 2]:
            log.error(f'中断类型取值范围为[0, 2], {mode}超出范围')
            return False
        bus_info = info_dict.get('bus-info')
        if mode == 0:
            irq_mode = 'MSI-X'
        elif mode == 1:
            irq_mode = 'MSI'
        else:
            irq_mode = 'DisINTx'
        if mode == 2:
            exec_cmd = f'lspci -vvs {bus_info} | grep {irq_mode}'
            rtn_code, rtn_output, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_cmd, cmd_execute_address=cmd_execute_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'lspci查询结果: {rtn_output}')
                enable_flag = re.search(r"DisINTx(\S)", rtn_output).group(1)
            else:
                log.error(f'pci查询命令执行失败, 失败信息: {rtn_err}')
                return False
        else:
            exec_cmd = f"lspci -vvs {bus_info} | grep \'{irq_mode}: Enable\'"
            rtn_code, rtn_output, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_cmd, cmd_execute_address=cmd_execute_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'lspci查询结果: {rtn_output}')
                enable_flag = re.search(r"Enable(\S)", rtn_output).group(1)
            else:
                log.error(f'pci查询命令执行失败, 失败信息: {rtn_err}')
                return False
        if enable_flag == '+' and (mode == 0 or mode == 1):
            return True
        elif enable_flag == '-' and mode == 2:
            return True
        else:
            return False

    @classmethod
    def wait_seconds(cls, seconds: int):
        log.info_caller(f"等待{seconds}s")
        time.sleep(seconds)

    @classmethod
    def get_rpm_package(cls, root_path: str, dkms_test: bool, rpm_type: int, exec_address: str, other: bool,
                        host_os_server: str = None, host_os_client: str = None, test_port: int = 22,
                        src_type: int = 0, architecture: str = "x86_64") -> tuple:
        """
        author:         junfeng.he
        date:           2023.11.15
        description: 获取rpm包
        Centos8
            └── rpms
            ├── sxe-0.3.3.5_el8.2-1.x86_64.rpm
        """
        nicg = cls.get_nic_generation()
        product_name = nicg
        if rpm_type == 2:
            vf = "rdma"
        elif rpm_type == 1:
            vf = "vf"
        else:
            vf = ""
        fw_version = ""
        is_ubuntu = False
        if dkms_test:
            # 获取包中的版本信息
            exec_command = f"ls {root_path}/products/Src/dkms/*"
            rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=exec_address, ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server, host_os_client=host_os_client)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
            pf_versions = re.findall(rf"{product_name}-(\d+\.\d+\.\d+\.\d+)", rtn_outputs)
            if pf_versions:
                driver_versions = pf_versions[0]
            else:
                return '', '', is_ubuntu

            if rpm_type:
                vf_versions = re.findall(rf"{product_name}vf-(\d+\.\d+\.\d+\.\d+)", rtn_outputs)
                if vf_versions:
                    driver_versions = vf_versions[0]
                else:
                    return '', '', is_ubuntu

            # 判断是否是Ubuntu
            exec_command = "uname -a"
            rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=exec_address, ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server, host_os_client=host_os_client)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
            log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
            if 'ubuntu' in rtn_outputs.lower():
                target_path = root_path + f"products/Src/dkms/{product_name}{vf}-{driver_versions}-1dkms.noarch.deb"
                is_ubuntu = True
            else:
                target_path = root_path + f"products/Src/dkms/{product_name}{vf}-{driver_versions}-1dkms.noarch.rpm"
            exec_command = f'ls {target_path}'
            rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=exec_address, ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server, host_os_client=host_os_client)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                return target_path, driver_versions, is_ubuntu
        elif src_type:
            if src_type == 3:
                prefix = "kmod-"
                suffix = "1.src.rpm"
                src_path = "technical_support"
            elif src_type == 2:
                prefix = ""
                suffix = "1.src.rpm"
                src_path = "technical_support"
            else:
                prefix = ""
                suffix = "src.tar.gz"
                src_path = "products/Src/pkgs"

            exec_command = f"ls {root_path}/{src_path}/*"
            rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=exec_address, ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server, host_os_client=host_os_client)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
            pf_versions = re.findall(rf"{product_name}-(\d+\.\d+\.\d+\.\d+)", rtn_outputs)
            if pf_versions:
                driver_versions = pf_versions[0]
            else:
                return '', '', is_ubuntu

            if rpm_type:
                vf_versions = re.findall(rf"{product_name}vf-(\d+\.\d+\.\d+\.\d+)", rtn_outputs)
                if vf_versions:
                    driver_versions = vf_versions[0]
                else:
                    return '', '', is_ubuntu

            # 判断是否是Ubuntu
            exec_command = "uname -a"
            rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=exec_address, ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server, host_os_client=host_os_client)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
            log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
            if 'ubuntu' in rtn_outputs.lower():
                target_path = root_path + f"{src_path}/{prefix}{product_name}{vf}-{driver_versions}-{suffix}"
                is_ubuntu = True
            else:
                target_path = root_path + f"{src_path}/{prefix}{product_name}{vf}-{driver_versions}-{suffix}"
            exec_command = f'ls {target_path}'
            rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=exec_address, ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server, host_os_client=host_os_client)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                # 进行本地编译
                if src_type == 3 or src_type == 2:
                    exec_command = f'rpm -ivvh {target_path}'
                    rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                        exec_command, cmd_execute_address=exec_address, ssh_port=str(test_port) if test_port is not None else None,
                        host_os_server=host_os_server, host_os_client=host_os_client)
                    log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))

                    exec_command = f"cd /root/rpmbuild/SPECS/;rpmbuild -ba {product_name}{vf}.spec"
                    rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                        exec_command, cmd_execute_address=exec_address, ssh_port=str(test_port) if test_port is not None else None,
                        host_os_server=host_os_server, host_os_client=host_os_client)
                    log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))

                    exec_command = f"ls /root/rpmbuild/RPMS/{architecture}/"
                    rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                        exec_command, cmd_execute_address=exec_address, ssh_port=str(test_port) if test_port is not None else None,
                        host_os_server=host_os_server, host_os_client=host_os_client)
                    log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
                    subfix_strs = re.findall(re.compile(r'^{}{}{}-{}-1.(\S+)'.format(prefix, product_name, vf, driver_versions), re.MULTILINE), rtn_outputs)
                    if subfix_strs:
                        subfix_str = subfix_strs[0]
                    else:
                        subfix_str = f"{architecture}.rpm"
                    target_path = f"/root/rpmbuild/RPMS/{architecture}/" \
                                  f"{prefix}{product_name}{vf}-{driver_versions}-1.{subfix_str}"

                return target_path, driver_versions, is_ubuntu
            else:
                log.error("未获取到安装包，请检查大包文件！！！！")
                exit(1)
        else:
            # 获取包中的版本信息
            exec_command = f"ls {root_path}/products/Drivers/RHEL9/rpms/ETH/*"
            rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=exec_address, ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server, host_os_client=host_os_client)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
            pf_versions = re.findall(rf"{product_name}-(\d+\.\d+\.\d+\.\d+)_el9", rtn_outputs)
            log.info(f"product_name={product_name},pf_versions={pf_versions}")
            if pf_versions:
                driver_versions = pf_versions[0]
            else:
                return '', '', is_ubuntu

            if rpm_type:
                vf_versions = re.findall(rf"{product_name}vf-(\d+\.\d+\.\d+\.\d+)_el9", rtn_outputs)
                if vf_versions:
                    driver_versions = vf_versions[0]
                else:
                    return '', '', is_ubuntu

            os_version = ''
            os_rpm = ""
            # 判断是否是Ubuntu
            exec_command = "uname -a"
            rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=exec_address, ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server, host_os_client=host_os_client)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
            log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
            uname_a_res = rtn_outputs.lower()
            if 'ubuntu' in uname_a_res:
                if other:
                    log.warning("指定取内核不匹配rpm包,ubuntu当前没有")
                elif "Linux ubuntu 5.15.0-78-generic".lower() in uname_a_res:
                    os_version = 'ubuntu_22.04'
                    os_rpm = f"Ubuntu22.04.3-x86_64/deb/{product_name}{vf}-{driver_versions}-1.MDA64.deb"
                else:
                    log.warning("其他ubuntu内核版本，当前没有rpm包")

                is_ubuntu = True
            else:
                # 判断centos具体版本
                exec_command = "cat /etc/redhat-release"
                rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                    exec_command, cmd_execute_address=exec_address, ssh_port=str(test_port) if test_port is not None else None,
                    host_os_server=host_os_server, host_os_client=host_os_client)
                log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
                log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
                if other:
                    log.warning("指定取内核不匹配rpm包")
                    if "NFSChina" in rtn_outputs:
                        os_version = 'rocky_9.1'
                        os_rpm = f"Rocky/rpms/{product_name}{vf}-{driver_versions}_el9.1-1.x86_64.rpm"
                    else:
                        os_version = "NFSChina_4.0_0612"
                        os_rpm = f"NFSChina_4.0_0612/rpms/{product_name}{vf}-{driver_versions}_el4.0_0612-1.x86_64.rpm"
                else:
                    # os_rpm = f"Centos8/rpms/sxe{vf}-{driver_versions}_el8.2-1.x86_64.rpm"
                    if "CentOS" in rtn_outputs:
                        versions = re.findall(r'release (\d\.\d)', rtn_outputs.lower())
                        if versions:
                            os_version = "centos_{}".format(versions[0])
                            os_rpm = f"Centos{versions[0][0]}/rpms/{product_name}{vf}-{driver_versions}_el{versions[0]}-1." \
                                     f"x86_64.rpm"
                    elif "Red Hat" in rtn_outputs:
                        versions = re.findall(r'release (\d\.\d)', rtn_outputs.lower())
                        if versions:
                            os_version = "rhel_{}".format(versions[0])
                            os_rpm = f"RHEL{versions[0][0]}/rpms/{product_name}{vf}-{driver_versions}_el{versions[0]}-1." \
                                     f"x86_64.rpm"
                    elif "Rocky" in rtn_outputs:
                        versions = re.findall(r'release (\d\.\d)', rtn_outputs.lower())
                        if versions:
                            os_version = "rocky_{}".format(versions[0])
                            os_rpm = f"Rocky/rpms/{product_name}{vf}-{driver_versions}_el{versions[0]}-1.x86_64.rpm"
                    elif "NFSChina" in rtn_outputs:
                        versions = re.findall(r'release (\d\.\d)\.2\d(\d\d\d\d)', rtn_outputs.lower())
                        if versions:
                            ver, vdate = versions[0]
                            # "NFSChina_4.0_0801   NFSChina Server release 4.0.240408 (RTM3 OEM-S)"
                            if vdate == "0408":
                                vdate = "0801"
                            os_version = "NFSChina_{}_{}".format(ver, vdate)
                            os_rpm = f"NFSChina_{ver}_{vdate}/rpms/{product_name}{vf}-{driver_versions}_el{ver}_{vdate}-1." \
                                     f"x86_64.rpm"
                    else:
                        exec_command = 'cat /etc/os-release'
                        rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                            exec_command, cmd_execute_address=exec_address, ssh_port=str(test_port) if test_port is not None else None,
                            host_os_server=host_os_server, host_os_client=host_os_client)
                        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
                        if "Kylin Linux Advanced Server" in rtn_outputs:
                            if "4.19.90-21.2.9.wa".lower() in uname_a_res:
                                os_version = '9.wa'
                                os_rpm = f"Kylin_0721/rpms/{product_name}{vf}-{driver_versions}-{os_version}.x86_64.rpm"
                            elif "4.19.90-vhulk2001.1.0.0026.ns7.15".lower() in uname_a_res:
                                os_version = 'vhulk2001.1.0.0026.ns7.15'
                                os_rpm = f"Kylin_0429/rpms/{product_name}{vf}-{driver_versions}-{os_version}.x86_64.rpm"
                            elif "Linux Kylin03 4.19.90-52.22".lower() in uname_a_res:
                                os_version = 'v2207.ky10'
                                os_rpm = f"Kylin/rpms/{product_name}{vf}-{driver_versions}-{os_version}.x86_64.rpm"
                            elif "4.19.90-89.11.v2401.ky10".lower() in uname_a_res:
                                os_version = 'v2401.ky10'
                                os_rpm = f"Kylin/rpms/{product_name}{vf}-{driver_versions}-{os_version}.x86_64.rpm"
                            else:
                                os_version = "unknow"
                        if "UOS Server 20" in rtn_outputs or "UnionTech OS Server" in rtn_outputs:
                            if "4.19.90-2403.3.0.0270.84.uel20" in uname_a_res:
                                os_version = 'elUOS_V20_1070e_4_19-1'
                            elif "5.10.0-74.uel20" in uname_a_res:
                                os_version = 'elUOS_V20_1070e_5_10-1'
                            elif "4.19.90-2305" in uname_a_res:
                                os_version = 'elUOS_V20_1060e_4_19-1'
                            elif "5.10.0" in uname_a_res:
                                os_version = 'elUOS_V20_1060e_5_10-1'
                            elif "4.19.90" in uname_a_res:
                                os_version = "elUOS_V20_1050e-1"
                            else:
                                os_version = "unknow"
                            os_rpm = f"UOS/rpms/{product_name}{vf}-{driver_versions}_{os_version}.x86_64.rpm"
                        if "Anolis OS" in rtn_outputs:
                            os_version = 'el8.8-1'
                            os_rpm = f"AnolisOS/rpms/{product_name}{vf}-{driver_versions}_{os_version}.x86_64.rpm"
                        if "openEuler" in rtn_outputs:
                            if "5.10.0-60" in uname_a_res:
                                os_version = 'el22.03_LTS-1'
                            elif "5.10.0-216.0.0.115.oe2203sp4" in uname_a_res:
                                os_version = 'el22.03_LTS_SP4-1'
                            else:
                                os_version = "unknow"
                            os_rpm = f"openEular/rpms/{product_name}{vf}-{driver_versions}_{os_version}.x86_64.rpm"
                        if "Tencent" in rtn_outputs or "TK" in rtn_outputs:
                            if "5.4.119" in uname_a_res:
                                os_version = 'el3.1_TK4_22_9.3-1'
                            else:
                                os_version = "unknow"
                            os_rpm = f"TencentOS/rpms/{product_name}{vf}-{driver_versions}_{os_version}.x86_64.rpm"
                        if "culinux" in rtn_outputs:
                            if "5.10.0-60" in uname_a_res:
                                os_version = 'el3.0-1'
                            else:
                                os_version = "unknow"
                            os_rpm = f"culinux/rpms/{product_name}{vf}-{driver_versions}_{os_version}.x86_64.rpm"
                        if "BCLinux".lower() in rtn_outputs.lower():
                            if "kernel-4.19.90-2107.6.0.0208.16" in uname_a_res:
                                os_version = 'el21.10_230731-1'
                            elif "kernel-4.19.0-240.23.11" in uname_a_res:
                                os_version = 'elR8_U2_231017-1'
                            elif "kernel-5.10.0-200.0.0.113.25" in uname_a_res:
                                os_version = 'el21.10U4_240627-1'
                            else:
                                os_version = "unknow"
                            os_rpm = f"BCLinux/rpms/{product_name}{vf}-{driver_versions}_{os_version}.x86_64.rpm"

            log.info("os_version:{}".format(os_version))

            target_path = root_path + f"products/Drivers/{os_rpm}"
            exec_command = f'ls {target_path}'
            rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=exec_address, ssh_port=str(test_port) if test_port is not None else None,
                host_os_server=host_os_server, host_os_client=host_os_client)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
            if rtn_code == RtnStatusEnum.SUCCESS.value and os_rpm:
                return target_path, driver_versions, is_ubuntu
        return '', '', is_ubuntu

    @classmethod
    def force_clear_env_vf_vlan(cls) -> None:
        """
        author:      junfeng.he
        date:        2023-09-05 15:34:55
        description: 清理vf vlan
        :return:     None
        """
        log.info("强制进行vf，vlan清理")
        server_relation_list, client_relation_list = CommonOperation.get_nic_relationships()
        host_os_server, host_os_client = cls.get_nic_os()
        if 'none' in server_relation_list or 'none' in client_relation_list:
            log.warning("env_config.ini中网口关系配置中存在none，无法进行vf，vlan清理")
            return

        env_info_dict = {CmdExecuteAdressEnum.SERVER.value: server_relation_list,
                         CmdExecuteAdressEnum.CLIENT.value: client_relation_list}
        for cmd_execute_address, relation_list in env_info_dict.items():
            if host_os_server == 'windows' and cmd_execute_address == CmdExecuteAdressEnum.SERVER.value or \
                    host_os_client == 'windows' and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                continue
            for index, device_name in enumerate(relation_list):
                log.info("删除{}的vf".format(device_name))
                result_dict = EthtoolOperation.show_driver_infomation(device_name=device_name,
                                                                      cmd_execute_address=cmd_execute_address)
                if 'bus-info' not in result_dict.keys():
                    continue
                pci_num = result_dict['bus-info']
                command = f"echo 0 > /sys/bus/pci/devices/{pci_num}/sriov_numvfs"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=command, cmd_execute_address=cmd_execute_address
                )
                log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

                command = f"ip a | grep '@{device_name}:'"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=command, cmd_execute_address=cmd_execute_address
                )
                # log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                vlan_name_list = re.findall(r'(\S*)@{}:'.format(device_name), rtn_outputs)
                for vlan_name in vlan_name_list:
                    log.info("删除{}的vlan:{}".format(device_name, vlan_name))
                    command = f"ip link del {vlan_name}"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=cmd_execute_address
                    )
                    log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

                command = f"ip a | grep {device_name}"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=command, cmd_execute_address=cmd_execute_address
                )
                log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                pf_ips = re.findall(r"(inet 192.)", rtn_outputs)
                if len(pf_ips) > 1:
                    log.info("清除pf临时ip")
                    command = f"ip addr flush dev {device_name}"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=cmd_execute_address
                    )
                    log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                    # 麒麟系统需要ifdown再ifup，ip才能恢复，20260108-jhe
                    command = f"ifdown {device_name}"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root'
                    )
                    log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                    command = f"ifup {device_name}"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root'
                    )
                    log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
                    if "command not found" in rtn_outputs + rtn_err or "unknown connection" in rtn_outputs + rtn_err:
                        command = "nmcli connection down {}".format(device_name)
                        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root'
                        )
                        log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")

    @classmethod
    def get_degvmq_mode_value(cls, target_value: str) -> bool:
        """
        author:      xiangyu.liu
        date:        2023-09-05 15:34:55
        description: 获取降级vmq模式的值
        :return:     None
        """
        if not cls.degvmq_mode:
            cls.degvmq_mode = random.choice(DEGVMQ_MODE)
        log.info("degvmq_mode:{}".format(cls.degvmq_mode))
        value = cls.degvmq_mode.get(target_value)
        if value == ENABLE:
            log.info(f"获取到降级vmq {target_value}预设使能状态{value}")
            target_value_enable = True
        elif value == DISABLE:
            log.info(f"获取到降级vmq {target_value}预设使能状态{value}")
            target_value_enable = False
        else:
            log.error(f"未获取到降级vmq {target_value}预设使能状态, 默认False")
            target_value_enable = False
        return target_value_enable

    @classmethod
    def is_release_package_version(cls, cmd_execute_address: str) -> bool:
        """
        author:      junfeng.he
        date:        2024-02-03 15:34:55
        description: 获取当前升级的包是否是release版本
        :return:     bool
        """
        version_file = "/root/sxetest/publish_version/release_version.txt"
        command = f"cat {version_file}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=command, cmd_execute_address=cmd_execute_address, ssh_username=f'root'
        )
        log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
        if "makemode:debug" in rtn_outputs:
            return False
        return True

    @classmethod
    def check_tool_existence(cls, tool_name: str, cmd_name: str,
                             execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> bool:
        """
        author:      yuren
        date:        2024-04-03 15:34:55
        description: 获取当前环节是否存在指定的工具，如果没有，则尝试安装
        :return:     bool
        """
        is_ubuntu = False
        check_cmd_existence_cmd = 'which {}'.format(cmd_name)
        rtn_code, _, _,= CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=check_cmd_existence_cmd, cmd_execute_address=execute_address
        )
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info('当前系统中已经安装{}工具'.format(tool_name))
            return True
        else:
            log.info('当前系统中未安装{}工具'.format(tool_name))
            check_os_release_cmd = 'cat /etc/os-release'
            _, rtn_outputs, _,= CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=check_os_release_cmd, cmd_execute_address=execute_address
            )
            if 'Ubuntu' in rtn_outputs or 'debian' in rtn_outputs:
                is_ubuntu = True
            if not is_ubuntu:
                install_tool_cmd = 'yum install -y {}'.format(tool_name)
            else:
                install_tool_cmd = 'apt install -y {}'.format(tool_name)
            _, rtn_outputs, rtn_err,= CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=install_tool_cmd, cmd_execute_address=execute_address
            )
            log.info('执行命令: {}, 标准回显: {}, 错误信息: {}'.format(install_tool_cmd, rtn_outputs, rtn_err))
            log.info('检查{}工具是否安装成功'.format(tool_name))
            rtn_code, _, _,= CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=check_cmd_existence_cmd, cmd_execute_address=execute_address
            )
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info('{}工具安装成功'.format(tool_name))
                return True
            else:
                log.info('{}工具安装失败, 退出方法, 返回错误'.format(tool_name))
                return False

    @classmethod
    def check_current_numa_node(cls, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                                null_memory_flag: bool = False):
        """
        author:      yunren
        date:        2024-04-03 15:34:55
        description: 获取当前numa节点
        :return:     bool
        """
        node_dict = {}
        exist_flag = cls.check_tool_existence(tool_name='numactl', cmd_name='numactl',
                                              execute_address=execute_address)
        if not exist_flag:
            log.info('未安装numactl工具, 无法检查numa信息')
            return node_dict
        check_numa_node_cmd = 'numactl --hardware'
        _, rtn_outputs, _= CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=check_numa_node_cmd, cmd_execute_address=execute_address
        )
        log.info('numa节点信息: \n{}'.format(rtn_outputs))
        node_list = re.findall(r'node\s+\d+\s+cpus:\s+([\s\d]*)', rtn_outputs)
        # node_list = re.findall(r'node\s+\d+\s+cpus:\s+(.*)', rtn_outputs)
        log.info("node_list:{}".format(node_list))
        for i in range(len(node_list)):
            node_dict[str(i)] = node_list[i]
        if not null_memory_flag:
            memory_list = re.findall(r'node\s+\d+\s+size:\s+(\d+)\s+', rtn_outputs)
            log.info("memory_list:{}".format(memory_list))
            for i in range(len(memory_list)):
                if int(memory_list[i]) == 0 or len(node_list[i]) == 0:
                    node_dict.pop(str(i))
            for i in node_dict:
                log.info('非空numa节点{}下cpu核列表: {}'.format(i, node_dict[i]))
        else:
            for i in node_dict:
                log.info('全部numa节点{}下cpu核列表: {}'.format(i, node_dict[i]))
        return node_dict

    @classmethod
    def check_nic_numa(cls, device_name: str, execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      yunren
        date:        2024-04-03 15:34:55
        description: 获取当前网口所在numa
        :return:     str
        """
        bdf_format = re.findall(r"(\S{2}:\S{2}.\S)", device_name)
        if bdf_format:
            log.info(f"NCD==> device_name为bdf：{device_name}")
            bus_info = device_name
        else:
            bus_info = EthtoolOperation.show_driver_infomation(
                device_name=device_name, cmd_execute_address=execute_address)['bus-info']
        numa_node_path = '/sys/bus/pci/devices/{}/numa_node'.format(bus_info)
        cmd = 'cat \'{}\''.format(numa_node_path)
        rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=execute_address)
        log.info('执行命令: {}, 标准回显: {}, 错误信息: {}'.format(cmd, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info("当前nic位于numa {}".format(rtn_outputs))
            return rtn_outputs
        else:
            log.error("未获取到当前nic所位于的numa")
            return "-1"

    @classmethod
    def select_core_cross_numa(cls, nic_numa_node, numa_node_dict, core_num,
                               cross_numa_flag: bool = True, execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                               remove_odd_numbers_flag: bool = False):
        """
        author:      yuren
        date:        2024-04-03 15:34:55
        description: 获取与网卡同numa或不同numa的core列表,remove_odd_numbers为去掉奇数核数，因为top只能显示偶数核
        :return:     list
        """
        distance = 0
        selected_numa_node = 0
        cross_cpu_core_list = []
        if nic_numa_node == '-1':
            if cross_numa_flag:
                log.info('当前环境不满足跨numa测试条件')
                return cross_cpu_core_list
            else:
                nic_numa_node = "0"

        check_numa_node_cmd = "ps -ef | grep -E 'dpdk-testpmd|dpdk-l3fwd|dpdk-l2fwd'"
        _, taken_cpu_info, _= CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=check_numa_node_cmd, cmd_execute_address=execute_address
        )
        if cross_numa_flag:
            for i in numa_node_dict:
                if abs(int(i) - int(nic_numa_node)) > distance:
                    distance = abs(int(i) - int(nic_numa_node))
                    selected_numa_node = int(i)
            log.info('选定的numa节点编号: {}'.format(selected_numa_node))
            cpu_core_list = re.split(r'\s+', numa_node_dict[str(selected_numa_node)])
            cpu_core_list = [element for element in cpu_core_list if element != '']
            # 去掉已经被占用的cpu核
            lcores = re.findall(r"-l (\d+)-(\d+)", taken_cpu_info)
            log.info("lcores:{}".format(lcores))
            if lcores:
                lcore_start, lcore_end = lcores[0]
                for i in range(int(lcore_start), int(lcore_end) + 1):
                    if str(i) in cpu_core_list:
                        log.info("去掉已经被占用的cpu核:{}".format(i))
                        cpu_core_list.remove(str(i))
            lcores = re.findall(r"-l ([\d,]+)", taken_cpu_info)
            log.info("lcores:{}".format(lcores))
            if lcores:
                for lcore in lcores:
                    core_num_list = lcore.split(",")
                    for i in core_num_list:
                        if str(i) in cpu_core_list:
                            log.info("去掉已经被占用的cpu核:{}".format(i))
                            cpu_core_list.remove(str(i))
            if len(cpu_core_list) <= core_num:
                log.info('选定的numa节点下cpu核数{}小于等于期望获取的cpu核数{}, 返回numa下全部cpu核心列表'.format(len(cpu_core_list), core_num))
                return cpu_core_list
            for _ in range(core_num):
                # selected_cpu_core = random.choice(cpu_core_list)
                selected_cpu_core = cpu_core_list[0]
                cross_cpu_core_list.append(selected_cpu_core)
                cpu_core_list.pop(cpu_core_list.index(selected_cpu_core))
            cross_cpu_core_list.sort()
            log.info('选定的跨numa的cpu核列表: {}'.format(cross_cpu_core_list))
        else:
            if nic_numa_node not in numa_node_dict.keys():
                log.warning(f"==》当前卡所在numa：{nic_numa_node}，无内存，需要使用有内存numa：{numa_node_dict.keys()}")
                nic_numa_node_list = list(numa_node_dict.keys())
                if len(nic_numa_node_list):
                    nic_numa_node = nic_numa_node_list[0]
                    cpu_core_list = re.split(r'\s+', numa_node_dict[nic_numa_node])
                else:
                    cpu_core_list = []
                    return cpu_core_list
            else:
                cpu_core_list = re.split(r'\s+', numa_node_dict[nic_numa_node])
            cpu_core_list = [element for element in cpu_core_list if element != '']
            # 去掉已经被占用的cpu核
            lcores = re.findall(r"-l (\d+)-(\d+)", taken_cpu_info)
            log.info("lcores:{}".format(lcores))
            if lcores:
                lcore_start, lcore_end = lcores[0]
                for i in range(int(lcore_start), int(lcore_end) + 1):
                    if str(i) in cpu_core_list:
                        log.info("去掉已经被占用的cpu核:{}".format(i))
                        cpu_core_list.remove(str(i))
            lcores = re.findall(r"-l ([\d,]+)", taken_cpu_info)
            log.info("lcores:{}".format(lcores))
            if lcores:
                for lcore in lcores:
                    core_num_list = lcore.split(",")
                    for i in core_num_list:
                        if str(i) in cpu_core_list:
                            log.info("去掉已经被占用的cpu核:{}".format(i))
                            cpu_core_list.remove(str(i))
            if remove_odd_numbers_flag:
                # 去掉奇数核
                new_cpu_core_list = copy.deepcopy(cpu_core_list)
                for core_info in new_cpu_core_list:
                    if int(core_info) % 2 == 1:
                        cpu_core_list.remove(core_info)
            if len(cpu_core_list) <= core_num:
                log.info('选定的numa节点下cpu核数{}小于等于期望获取的cpu核数{}, 返回numa下全部cpu核心列表'.format(len(cpu_core_list), core_num))
                return cpu_core_list
            for _ in range(core_num):
                # selected_cpu_core = random.choice(cpu_core_list)
                selected_cpu_core = cpu_core_list[0]
                cross_cpu_core_list.append(selected_cpu_core)
                cpu_core_list.pop(cpu_core_list.index(selected_cpu_core))
            cross_cpu_core_list.sort()
            log.info('选定的同numa的cpu核列表: {}'.format(cross_cpu_core_list))
        return cross_cpu_core_list

    @classmethod
    def check_cpu_utilization(cls, cpu_core_list: list, cmd_execute_address: str, log_path: str,
                              report_interval: int = 1) -> None:
        """
        author:      yuren
        date:        2024-04-12 11:35:20
        description: 监测指定cpu核心的利用率
        :return:     bool
        """
        result = cls.check_tool_existence(tool_name='sysstat', cmd_name='mpstat', execute_address=cmd_execute_address)
        if not result:
            log.info('当前系统中未安装sysstat, 不检查cpu利用率')
            return
        log.info('开启监测cpu利用率')
        cpu_core_str = ','.join(cpu_core_list)
        exec_cmd = 'mpstat -P {} {} > {}'.format(cpu_core_str, report_interval, log_path)
        _, rtn_outputs, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_cmd, cmd_execute_address=cmd_execute_address)

    @classmethod
    def stop_check_cpu_utilization(cls, cmd_execute_address: str) -> None:
        ps_cmd = 'ps -ef | grep -w mpstat | grep -v grep'
        _, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=ps_cmd, cmd_execute_address=cmd_execute_address)
        log.info('执行命令: {}, 标准输出: {}, 错误信息: {}'.format(ps_cmd, rtn_outputs, rtn_err))
        if not re.search(r'mpstat', rtn_outputs):
            log.info('当前系统中没有mpstat进程')
            return
        process_id = re.search(r'\s+\d+\s+', rtn_outputs).group().strip()
        log.info('停止监测cpu利用率')
        kill_cmd = 'kill -2 {}'.format(process_id)
        _, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=kill_cmd, cmd_execute_address=cmd_execute_address)
        log.info('执行命令: {}, 标准输出: {}, 错误信息: {}'.format(ps_cmd, rtn_outputs, rtn_err))

    @classmethod
    def ping_status_check(cls, ipv4_s, device_name_c, cmd_execute_address, host_os_client: str = 'linux') -> bool:
        if ipv4_s:
            if 'windows' in host_os_client:
                # windows  device_name_c传ipv4_c
                ipv4_c = device_name_c
                ping_success_mark = 'TTL='
                ping_package_mark = 'Lost = 0 (0% loss)'
                command = f'ping {ipv4_s} -S {ipv4_c} -n 1'
            else:
                ping_success_mark = 'ttl='
                ping_package_mark = ' 0% packet loss'
                command = f'ping {ipv4_s} -I {device_name_c} -c 1'

            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_with_error(
                    cmd=command, cmd_execute_address=cmd_execute_address)
            log.info("ping_success_mark:{}, ping_package_mark:{}, res:{},{}".
                     format(ping_success_mark, ping_package_mark,
                            ping_success_mark in rtn_outputs, ping_package_mark in rtn_outputs))
            if ping_success_mark in rtn_outputs and ping_package_mark in rtn_outputs:
                return True
        return False

    @classmethod
    def function_level_reset(cls, cmd_execute_address: str, device: str = "", bdf: str = "",
                             name_space: str = None) -> bool:
        """
        author:      junfeng.he
        date:        2024-12-21 11:35:20
        description: PFLR
        :return:     None
        """
        if name_space:
            result = False
            if not bdf:
                exec_command = f"ip netns exec {name_space} ethtool -i {device}"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    exec_command, cmd_execute_address=cmd_execute_address)
                # bus-info: 0000:31:00.0
                bdfs = re.findall(r"bus-info: (\S\S\S\S:\S\S:\S\S.\S)", rtn_outputs)
                if bdfs:
                    bdf = bdfs[0]
                else:
                    log.error("未找到设备bdf，无法进行flr操作！！")
                    return result
            # exec_command = f"find / -name reset | grep {bdf}"
            # rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
            #     exec_command, cmd_execute_address=cmd_execute_address)
            # if "reset" in rtn_outputs:
            rtn_outputs = f'/sys/bus/pci/devices/{bdf}/reset'
            exec_command = f"ip netns exec {name_space} echo 1 > {rtn_outputs}"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                result = True
            else:
                log.error("执行flr操作异常，return code：{}！！".format(rtn_code))
            # else:
            #     log.error("未找到可操作设备，无法进行flr操作！！")
            return result
        else:
            result = False
            if not bdf:
                exec_command = "ethtool -i '{}'".format(device)
                rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                    exec_command, cmd_execute_address=cmd_execute_address)
                # bus-info: 0000:31:00.0
                bdfs = re.findall(r"bus-info: (\S\S\S\S:\S\S:\S\S.\S)", rtn_outputs)
                if bdfs:
                    bdf = bdfs[0]
                else:
                    log.error("未找到设备bdf，无法进行flr操作！！")
                    return result
            # exec_command = "find / -name reset | grep '{}'".format(bdf)
            # rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
            #     exec_command, cmd_execute_address=cmd_execute_address)
            # if "reset" in rtn_outputs:
            rtn_outputs = f'/sys/bus/pci/devices/{bdf}/reset'
            exec_command = "echo 1 > {}".format(rtn_outputs)
            rtn_code, rtn_outputs, rtn_err= CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                result = True
            else:
                log.error("执行flr操作异常，return code：{}！！".format(rtn_code))
            # else:
            #     log.error("未找到可操作设备，无法进行flr操作！！")
            return result

    @classmethod
    def scapy_send_packets_screen_exit(cls, cmd_execute_address: str, sub_mark: str = ""):
        """
        author:      junfeng.he
        date:        2024-07-23 11:35:20
        description: 退出scapy的screen
        :return:     None
        """
        # 创建screen会话，在内部进行编译
        vm, rpc_port = CommonOperation.get_node_info_from_path()
        log.info("vm:{},rpc_port:{}".format(vm, rpc_port))
        vm_path = "{}{}".format(constants.LINUX_FILE_PATH_ROOT, vm)
        scapy_screen_name = "scapy_{}{}".format(vm, sub_mark)
        exec_command = "screen -list"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            exec_command, cmd_execute_address=cmd_execute_address, print_steps=False, print_outputs=False)
        screen_scapys = re.findall(rf"(\s+\.{scapy_screen_name})", rtn_outputs)
        for screen_scapy in screen_scapys:
            exec_command = "screen -S {} -X quit".format(screen_scapy)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address, print_steps=True, print_outputs=True)
        exec_command = "screen -wipe"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            exec_command, cmd_execute_address=cmd_execute_address, print_steps=True, print_outputs=True)

    @classmethod
    def scapy_send_packets(cls, cmd_execute_address: str, scapy_cmd: str = "", test_packet_type: str = "",
                           iface: str = "", src_mac: str = "", dst_mac: str = "",
                           src_ip: str = "", dst_ip: str = "", src_port: str = "", dst_port: str = "",
                           vlan: str = "", prio: int = 1, vlan_type: int = 0x0800, data_len: int = 100,
                           count: int = 1,
                           ip_chksum: str = "", tcp_chksum: str = "", udp_chksum: str = "", sctp_chksum: str = "",
                           icmp_chksum: str = "",
                           ipv6: bool = False, ether_type: str = '', l4proto: str = '', tos: str = '',
                           enable_tcpdump: bool = True, keep_enable: bool = False, netns_name: str = None,
                           store_file: str = None, inter: float = 0.0, params_value: str = None,
                           double_vlan: bool = False, sub_mark: str = "", ssh_ip: str = None) -> None:
        """
        author:      junfeng.he
        date:        2024-07-23 11:35:20
        description: 直接构造scapy命令进行发包,默认带tcpdump抓包，如果传参scapy_cmd，将使用传递的命令，如果传递参数，将使用传递的参数拼接
                     此方法当前仅是基础实现，后续可根据需求进一步优化
        params inter: 每隔多少时间发一个包
        params params_values: tcpdump参数
        params sub_mark: 用于起多个scapy screen
        @changelog:
            新增inter参数：可以实现控制多长时间进行一个包
        :return:     None
        """
        inter = str(inter)
        from scripts.script_libs.script_base import SxeThread

        if netns_name:
            prefix_command = f"ip netns exec {netns_name} "
        else:
            prefix_command = ""

        def run_tcpdump(cmd_execute_address, device_name, store_file, extra_vlaue, ssh_ip):
            """
            author: junfeng.he
            date: 2023.08.21
            description: 在指定端拉起tcpdmup抓包
            """
            if extra_vlaue is None:
                exec_command = f"{prefix_command} tcpdump -i {device_name} -w {store_file} -p"
            else:
                exec_command = f"{prefix_command} tcpdump -i {device_name} -w {store_file} -p '{extra_vlaue}'"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
            log.info("exec_command:{}, rtn_code:{}, rtn_outputs:{}, rtn_err:{}".
                     format(exec_command, rtn_code, rtn_outputs, rtn_err))

        # 创建screen会话，在内部进行操作
        vm, rpc_port = CommonOperation.get_node_info_from_path()
        log.info("vm:{},rpc_port:{}".format(vm, rpc_port))
        vm_path = "{}{}".format(constants.LINUX_FILE_PATH_ROOT, vm)
        scapy_screen_name = "scapy_{}{}".format(vm, sub_mark)
        screen_log_path = vm_path + sub_mark
        screen_log_name = "screenlog.0"
        if sub_mark:
            # 当用多线程时，命令只执行一次即退出screen
            keep_enable = False
        if not store_file:
            store_file = "{}/client_packet.pcap".format(vm_path)

        if not scapy_cmd:
            if ipv6:
                ip_func = "IPv6"
                len_para = "plen"
                # ipv6中的plen，不包含自身header长度，虽然自身header长度为40，但此处取0
                ip_header_len = 0
            else:
                ip_func = "IP"
                len_para = "len"
                ip_header_len = 20

            if ip_chksum:
                ip_chksum = f",chksum={ip_chksum}"
            if tcp_chksum:
                tcp_chksum = f",chksum={tcp_chksum}"
            if udp_chksum:
                udp_chksum = f",chksum={udp_chksum}"
            if sctp_chksum:
                sctp_chksum = f",chksum={sctp_chksum}"
            if icmp_chksum:
                icmp_chksum = f"chksum={icmp_chksum}"

            if ether_type:
                l2proto = f",type={ether_type}"
            else:
                l2proto = ""

            if l4proto:
                l4proto = f",proto={l4proto}"
            else:
                l4proto = ""

            inner_data_length = 0
            if test_packet_type.upper() in ["IPV6", "IP", "UDP", "TCP", "SCTP", "ICMP"]:
                packet_type = test_packet_type.upper()
                # 计算的是ip中的len,与下一层的长度，ipv4占20, ipv6占40, tcp占20，udp占8，sctp占12
                if test_packet_type.upper() == "TCP":
                    inner_data_length = data_len - (ip_header_len + 20)
                elif test_packet_type.upper() == "UDP":
                    inner_data_length = data_len - (ip_header_len + 8)
                elif test_packet_type.upper() == "SCTP":
                    inner_data_length = data_len - (ip_header_len + 12)
                elif test_packet_type.upper() == "ICMP":
                    inner_data_length = data_len - (ip_header_len + 8)
                else:
                    inner_data_length = data_len - (ip_header_len + 0)
            elif test_packet_type.upper() == 'ETHER':
                inner_data_length = data_len
            elif test_packet_type:
                log.warning("指定类型为：{}，可能未适配".format(test_packet_type))
                packet_type = ""
            else:
                packet_type = "UDP"
                log.warning("未指定使用UDP还是TCP，默认赋值UDP")
                inner_data_length = data_len - (ip_header_len + 8)

            if test_packet_type.upper() == TransportProtocal.ETHER_II.value.upper():
                if L2ProtoTypeEnum.IPV4.value in l2proto and src_ip and dst_ip:
                    scapy_cmd = f"sendp(Ether(src='{src_mac}', dst='{dst_mac}'{l2proto})" \
                                f"/{ip_func}({len_para}={data_len}, src='{src_ip}',dst='{dst_ip}')" \
                                f"/Raw(load='8'*{data_len}),iface='{iface}',count={count}, inter={inter})"
                else:
                    scapy_cmd = f"sendp(Ether(src='{src_mac}', dst='{dst_mac}'{l2proto})" \
                                f"/Raw(load='8'*{data_len}),iface='{iface}',count={count}, inter={inter})"
            elif src_mac and dst_mac and not src_ip and not dst_ip and not src_port and not dst_port and not vlan and not tos:
                scapy_cmd = "sendp(Ether(src='{}', dst='{}')/IP()/ Raw(load='8'*{}), iface='{}', count={}, inter={})". \
                    format(src_mac, dst_mac, data_len, iface, count, inter)
            elif src_mac and dst_mac and not src_ip and not dst_ip and not src_port and not dst_port and not tos and vlan:
                if double_vlan:
                    if l2proto.split("=")[1] == "0x8100":
                        # 如果输入的类型为0x8100（802.1Q类型）
                        scapy_cmd = \
                            f"sendp(Ether(src='{src_mac}', dst='{dst_mac}',type=0x8100) /Dot1Q(vlan={vlan})" \
                            f"/Dot1Q(vlan={vlan}) /Raw(load='8'*{data_len}), iface='{iface}', count={count}, " \
                            f"inter={inter})"
                else:
                    # 如果输入的类型为0x88a8（Q-in-Q类型）
                    if l2proto.split("=")[1] == "0x88a8":
                        scapy_cmd = \
                            f"sendp(Ether(src='{src_mac}', dst='{dst_mac}',type=0x88a8) /Dot1AD(vlan={vlan})/IP() / " \
                            f"Raw(load='8'*{data_len}), iface='{iface}', count={count}, inter={inter})"
                    elif l2proto.split("=")[1] == "0x8100":
                        # 如果输入的类型为0x8100（802.1Q类型）
                        scapy_cmd = \
                            f"sendp(Ether(src='{src_mac}', dst='{dst_mac}',type=0x8100) /Dot1Q(vlan={vlan})/IP() / " \
                            f"Raw(load='8'*{data_len}), iface='{iface}', count={count}, inter={inter})"
                    else:
                        # 默认情况为802.1Q的vlan tag
                        scapy_cmd = \
                            f"sendp(Ether(src='{src_mac}', dst='{dst_mac}',type=0x8100) /Dot1Q(vlan={vlan}) /IP() / " \
                            f"Raw(load='8'*{data_len}), iface='{iface}', count={count}, inter={inter})"
            elif not src_mac and not dst_mac and src_ip and dst_ip and src_port and dst_port and not vlan:
                scapy_cmd = "sendp(Ether({})/{}({}={},src='{}',dst='{}'{}{})/{}(sport={}," \
                            "dport={}{}{}{})/Raw(load='8'*{}),iface='{}',count={}, inter={})".format(
                    l2proto, ip_func, len_para, data_len, src_ip, dst_ip, l4proto, ip_chksum,
                    packet_type,
                    src_port, dst_port, udp_chksum, tcp_chksum, sctp_chksum, inner_data_length, iface, count, inter)
            elif not src_mac and not dst_mac and src_ip and dst_ip and not src_port and not dst_port and not vlan and not tos:
                scapy_cmd = "sendp(Ether({})/{}({}={},src='{}',dst='{}'{}{})" \
                            "/Raw(load='8'*{}),iface='{}',count={}, inter={})".format(
                    l2proto, ip_func, len_para, data_len, src_ip, dst_ip, l4proto, ip_chksum,
                    inner_data_length, iface, count, inter)
            elif src_mac and dst_mac and src_ip and dst_ip and not src_port and not dst_port and not vlan and not tos:
                if test_packet_type.upper() == "ICMP":
                    scapy_cmd = "sendp(Ether(src='{}', dst='{}'{})/{}({}={},src='{}',dst='{}'{}{})/" \
                                "ICMP({})/Raw(load='8'*{})," \
                                "iface='{}',count={}, inter={})". \
                        format(src_mac, dst_mac, l2proto, ip_func, len_para, data_len, src_ip, dst_ip, l4proto,
                               ip_chksum, icmp_chksum,
                               inner_data_length, iface, count, inter)
                else:
                    scapy_cmd = "sendp(Ether(src='{}', dst='{}'{})/{}({}={},src='{}',dst='{}'{}{})/Raw(load='8'*{})," \
                                "iface='{}',count={}, inter={})". \
                        format(src_mac, dst_mac, l2proto, ip_func, len_para, data_len, src_ip, dst_ip, l4proto,
                               ip_chksum,
                               inner_data_length, iface, count, inter)
            elif src_mac and dst_mac and src_ip and dst_ip and src_port and dst_port and not vlan and not tos:
                scapy_cmd = "sendp(Ether(src='{}', dst='{}'{})/{}({}={},src='{}',dst='{}'{}{})/{}(sport={}," \
                            "dport={}{}{}{})/Raw(load='8'*{}),iface='{}',count={}, inter={})".format(
                    src_mac, dst_mac, l2proto, ip_func, len_para, data_len, src_ip, dst_ip, l4proto, ip_chksum,
                    packet_type,
                    src_port, dst_port, udp_chksum, tcp_chksum, sctp_chksum, inner_data_length, iface, count, inter)
            elif src_mac and dst_mac and src_ip and dst_ip and src_port and dst_port and vlan and not tos:
                if data_len == 0:
                    scapy_cmd = "sendp(Ether(src='{}', dst='{}'{})/Dot1Q(prio={}, id=0, vlan={}, type={})/" \
                                "{}(src='{}',dst='{}'{}{})/{}(sport={}," \
                                "dport={}{}{}{})," \
                                "iface='{}',count={}, inter={})". \
                        format(src_mac, dst_mac, l2proto, prio, vlan, vlan_type, ip_func, src_ip,
                               dst_ip, l4proto, ip_chksum, packet_type,
                               src_port, dst_port, udp_chksum, tcp_chksum, sctp_chksum, iface, count, inter)
                else:
                    scapy_cmd = "sendp(Ether(src='{}', dst='{}'{})/Dot1Q(prio={}, id=0, vlan={}, type={})/" \
                                "{}({}={},src='{}',dst='{}'{}{})/{}(sport={}," \
                                "dport={}{}{}{})/Raw(load='8'*{})," \
                                "iface='{}',count={}, inter={})". \
                        format(src_mac, dst_mac, l2proto, prio, vlan, vlan_type, ip_func, len_para, data_len, src_ip,
                               dst_ip, l4proto, ip_chksum, packet_type,
                               src_port, dst_port, udp_chksum, tcp_chksum, sctp_chksum,
                               inner_data_length, iface, count, inter)
            elif src_mac and dst_mac and src_ip and dst_ip and not src_port and not dst_port and not vlan and not tos:
                scapy_cmd = "sendp(Ether(src='{}', dst='{}'{}) / {}({}={},src='{}',dst='{}'{}{})/ " \
                            "Raw(load='8'*{}), iface='{}', count={}, inter={})". \
                    format(src_mac, dst_mac, l2proto, ip_func, len_para, data_len, src_ip, dst_ip, l4proto,
                           data_len, iface, count, inter)
            elif src_mac and dst_mac and vlan and not tos:
                scapy_cmd = "sendp(Ether(src='{}', dst='{}'{}) / Dot1Q(prio={}, id=0, vlan={}, type={})," \
                            "iface='{}',count={}, inter={})". \
                    format(src_mac, dst_mac, l2proto, prio, vlan, vlan_type, iface, count, inter)

            # elif src_mac and dst_mac and
            elif src_mac and dst_mac and src_ip and dst_ip and src_port and dst_port and not vlan:
                log.info(f'打印发送参数')
                scapy_cmd = f"from scapy.contrib.geneve import GENEVE;" \
                    f"sendp(Ether(src='{src_mac}', dst='{dst_mac}'{l2proto})/{ip_func}({len_para}={data_len}," \
                            f"src='{src_ip}',dst='{dst_ip}'{l4proto}{ip_chksum}," \
                            f"tos={tos})/{packet_type}(sport={src_port}," \
                            f"dport={dst_port}{udp_chksum}{tcp_chksum}{sctp_chksum})/Raw(load='8'*{inner_data_length})," \
                            f"iface='{iface}',count={count})"
            else:
                log.error("未匹配到scapy命令，请确认！！")
        # 获取scapy cmd中的包数量，用于后续retry等待次数
        re_count = re.findall(r'count=(\d+)', scapy_cmd)
        if re_count:
            count = int(re_count[0])
        if not scapy_cmd:
            log.error("传递参数无法拼接到可用命令，请确认")
            return

        if enable_tcpdump and iface:
            # 创建远程拉起server端的线程
            run_tcpdump_thread = SxeThread(run_tcpdump, cmd_execute_address, iface, store_file, params_value, ssh_ip)
            run_tcpdump_thread.start()

        no_need_operate_screen = False
        if keep_enable:
            exec_command = prefix_command + "screen -wipe"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address, print_steps=False, print_outputs=False, ssh_ip=ssh_ip)
            # exec_command = "screen -list".format(scapy_screen_name)
            exec_command = prefix_command + "screen -list"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address, print_steps=False, print_outputs=False, ssh_ip=ssh_ip)
            screen_scapys = re.findall(rf"(\d+.{scapy_screen_name})", rtn_outputs)
            if screen_scapys and len(screen_scapys) > 1:
                for screen_scapy in screen_scapys:
                    exec_command = "screen -S {} -X quit".format(screen_scapy)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        exec_command, cmd_execute_address=cmd_execute_address, print_steps=True, print_outputs=True, ssh_ip=ssh_ip)
                exec_command = "screen -wipe"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    exec_command, cmd_execute_address=cmd_execute_address, print_steps=True, print_outputs=True, ssh_ip=ssh_ip)
            else:
                if scapy_screen_name in rtn_outputs:
                    no_need_operate_screen = True

        if no_need_operate_screen:
            pass
        else:
            exec_command = prefix_command + "screen -list"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address, print_steps=True, print_outputs=True, ssh_ip=ssh_ip)
            screen_scapys = re.findall(rf"(\d+.{scapy_screen_name})", rtn_outputs)
            if screen_scapys:
                for screen_scapy in screen_scapys:
                    exec_command = prefix_command + "screen -S {} -X quit".format(screen_scapy)
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        exec_command, cmd_execute_address=cmd_execute_address, print_steps=True, print_outputs=True, ssh_ip=ssh_ip)
                exec_command = prefix_command + "screen -wipe"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    exec_command, cmd_execute_address=cmd_execute_address, print_steps=True, print_outputs=True, ssh_ip=ssh_ip)

            exec_command = prefix_command + "mkdir {}".format(screen_log_path)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address, print_steps=False, print_outputs=False, ssh_ip=ssh_ip)

            exec_command = prefix_command + "echo '' > {}/{}".format(screen_log_path, screen_log_name)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address, print_steps=False, print_outputs=False, ssh_ip=ssh_ip)

            # 创建screen会话
            exec_command = "cd {};{} screen -L -dmS {}".format(screen_log_path, prefix_command, scapy_screen_name)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address, print_steps=True, print_outputs=True, ssh_ip=ssh_ip)

            # 修改screen日志刷新时间间隔为1s
            exec_command = prefix_command + "screen -S {} -X colon 'logfile flush 0.3^M'".format(scapy_screen_name)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address, print_steps=False, print_outputs=False, ssh_ip=ssh_ip)

            # screen内启动scapy
            exec_command = prefix_command + "screen -x -S {} -p 0 -X stuff 'scapy^M'".format(
                scapy_screen_name)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address, print_outputs=True, ssh_ip=ssh_ip)
            time.sleep(3)
            if keep_enable:
                no_need_operate_screen = True
        # 【注意：若使用execute_command_based_paramiko_with_rtncode 【长连接模式 - 推荐，可解决跨地域访问被拦截问题】，用下面这种方式，
        #  若使用execute_command_with_error 【短连接模式】,则用
        #  exec_command = prefix_command + "screen -x -S {} -p 0 -X stuff \\\"{}\\\"".format】
        exec_command = prefix_command + """screen -x -S {} -p 0 -X stuff "{}" """.format(
            scapy_screen_name, scapy_cmd)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            exec_command, cmd_execute_address=cmd_execute_address, print_steps=False, print_outputs=False, ssh_ip=ssh_ip)
        exec_command = prefix_command + "screen -x -S {} -p 0 -X stuff '^M'".format(
            scapy_screen_name)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            exec_command, cmd_execute_address=cmd_execute_address, print_steps=False, print_outputs=False, ssh_ip=ssh_ip)
        if ssh_ip is None:
            CommonOperation.concat_test_steps(f'{cmd_execute_address}端执行scapy_cmd->[{scapy_cmd}]', level=-2)
        else:
            CommonOperation.concat_test_steps(f'在{ssh_ip}端执行scapy_cmd->[{scapy_cmd}]', level=-2)
        iretry = 30 + count // 1000
        while iretry:
            time.sleep(1)
            exec_command = "grep -n 'sendp' {}/{}".format(screen_log_path, screen_log_name) + \
                           " | tail -1 | cut -d: -f1 | xargs -I{{}} tail -n +{{}} " + \
                           "{}/{}".format(screen_log_path, screen_log_name)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address, print_steps=False, print_outputs=False, ssh_ip=ssh_ip)
            if 'packets.' in rtn_outputs + rtn_err:
                log.info("========sendp finish log:" + rtn_outputs + "\n" + rtn_err)
                break
            iretry -= 1

        if no_need_operate_screen:
            pass
        else:
            time.sleep(1)
            # 退出并清除dpdk_testpmd所在screen会话
            exec_command = prefix_command + "screen -S {} -X quit".format(scapy_screen_name)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address, print_steps=False, print_outputs=False, ssh_ip=ssh_ip)

        if enable_tcpdump and iface:
            vm, rpc_port = CommonOperation.get_node_info_from_path()
            log.info("vm:{},rpc_port:{}".format(vm, rpc_port))
            vm_path = "{}{}".format(constants.LINUX_FILE_PATH_ROOT, vm)
            # exec_command = "pkill -ef tcpdump"
            exec_command = f"ps -ef | grep tcpdump | grep '{vm_path}'" + \
                           " | grep -v grep | awk '{print $2}' | xargs kill -s 2"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)

    @classmethod
    def set_arp(cls, opposite_dev: str, current_dev: str = '', address_family: str = "IPv4",
                exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> int:
        """
        author: xiangyu.liu
        date: 2024.10.21
        description: 设置本端环境设备的arp信息，可用于pf、vf
        :param current_dev: 本端设备名(ipv6需要)
        :param opposite_dev: 对端设备名
        :param opposite_ip: 对端设备ip
        :param opposite_mac: 对端设备mac地址
        :param address_family: 地址族，IPv4/IPv6
        :param exec_addr: 执行环境（即本端）
        :return: 返回 status
        """
        if exec_addr == CmdExecuteAdressEnum.SERVER.value:
            current_addr = CmdExecuteAdressEnum.SERVER.value
            opposite_addr = CmdExecuteAdressEnum.CLIENT.value
        else:
            current_addr = CmdExecuteAdressEnum.CLIENT.value
            opposite_addr = CmdExecuteAdressEnum.SERVER.value

        if CommandLineArgsParse.get_test_entry() == TestEntryEnum.SINGLE_MODE.value:
            log.info('single mode, skip set arp')
            return RtnStatusEnum.SUCCESS.value

        if address_family.lower() == 'ipv4':
            log.info(f'{exec_addr.title()}：开始设置{current_dev}的arp')

            # 获取对端设备ip
            cmd = f"ip addr show dev {opposite_dev} |grep 'inet '|cut -d ' ' -f 6"
            cmd_rtn, all_opposite_ip, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=opposite_addr)
            if cmd_rtn != RtnStatusEnum.SUCCESS.value:
                return cmd_rtn
            # 获取对端设备mac地址
            cmd = f'ifconfig {opposite_dev}|grep ether|cut -c 15-31'
            cmd_rtn, opposite_dev_mac, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=opposite_addr)
            if cmd_rtn != RtnStatusEnum.SUCCESS.value:
                return cmd_rtn

            for opposite_ip in all_opposite_ip.split('\n'):
                # 获取设备的全部arp
                cmd = f'arp -n |grep -w {current_dev}|grep {opposite_ip.split("/")[0]}'
                cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, cmd_execute_address=current_addr)
                # 清理本端arp
                if cmd_output:
                    for line in cmd_output.split('\n'):
                        ip = line.split()[0]
                        cmd = f'arp -d {ip}'
                        cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, cmd_execute_address=current_addr)
                        if cmd_rtn != RtnStatusEnum.SUCCESS.value and "No ARP entry for" not in cmd_output:
                            return cmd_rtn
                # 设置本端arp
                cmd = f'arp -s {opposite_ip.split("/")[0]} {opposite_dev_mac}'
                cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, cmd_execute_address=current_addr)
                if cmd_rtn != RtnStatusEnum.SUCCESS.value:
                    return cmd_rtn
            log.info(f'{exec_addr.title()}：完成设置{current_dev}的arp')

        else:
            if not current_dev:
                log.error('IPv6设置neigh需要指定本端设备名称！')
                return RtnStatusEnum.FAIL.value

            log.info(f'{exec_addr.title()}：开始设置{current_dev}的neigh')
            # 获取对端设备ip
            cmd = f"ip addr show dev {opposite_dev} |grep 'inet6 '|grep -v fe80|cut -d ' ' -f 6"
            cmd_rtn, all_opposite_ip, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=opposite_addr)
            if cmd_rtn != RtnStatusEnum.SUCCESS.value:
                return cmd_rtn
            # 获取对端设备mac地址
            cmd = f'ifconfig {opposite_dev}|grep ether|cut -c 15-31'
            cmd_rtn, opposite_dev_mac, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=opposite_addr)
            if cmd_rtn != RtnStatusEnum.SUCCESS.value:
                return cmd_rtn

            for opposite_ip in all_opposite_ip.split('\n'):
                # 获取设备的全部neigh
                cmd = f'ip -6 neigh show dev {current_dev}|grep {opposite_ip.split("/")[0]}'
                cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, cmd_execute_address=current_addr)
                # 清理本端neigh
                if cmd_output:
                    for line in cmd_output.split('\n'):
                        ip = line.split()[0]
                        cmd = f'ip -6 neigh del {ip} dev {current_dev}'
                        cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, cmd_execute_address=current_addr)
                        if cmd_rtn != RtnStatusEnum.SUCCESS.value and "RTNETLINK answers: No such file or directory" not in cmd_stderr:
                            return cmd_rtn
                # 设置本端neigh
                cmd = f'ip -6 neigh add {opposite_ip.split("/")[0]} lladdr {opposite_dev_mac} dev {current_dev}'
                cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, cmd_execute_address=current_addr)
                if cmd_rtn != RtnStatusEnum.SUCCESS.value:
                    return cmd_rtn
                # 获取设备的全部neigh
                cmd = f'ip -6 neigh show dev {current_dev}'
                cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, cmd_execute_address=current_addr)
                if cmd_rtn != RtnStatusEnum.SUCCESS.value:
                    return cmd_rtn

                log.info(f'{exec_addr.title()}：完成设置{current_dev}的neigh')

    @classmethod
    def check_arp(cls, opposite_dev: str, current_dev: str = '', address_family: str = "IPv4",
                  exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> int:
        """
        author: xiangyu.liu
        date: 2024.10.21
        description: 设置本端环境设备的arp信息，可用于pf、vf
        :param current_dev: 本端设备名(ipv6需要)
        :param opposite_dev: 对端设备名
        :param opposite_ip: 对端设备ip
        :param opposite_mac: 对端设备mac地址
        :param address_family: 地址族，IPv4/IPv6
        :param exec_addr: 执行环境（即本端）
        :return: 返回 status
        """
        if exec_addr == CmdExecuteAdressEnum.SERVER.value:
            current_addr = CmdExecuteAdressEnum.SERVER.value
            opposite_addr = CmdExecuteAdressEnum.CLIENT.value
        else:
            current_addr = CmdExecuteAdressEnum.CLIENT.value
            opposite_addr = CmdExecuteAdressEnum.SERVER.value

        if CommandLineArgsParse.get_test_entry() == TestEntryEnum.SINGLE_MODE.value:
            log.info('single mode, skip check arp')
            return RtnStatusEnum.SUCCESS.value

        if address_family.lower() == 'ipv4':
            log.info(f'开始检查{current_dev}的arp')
            # 获取对端设备ip
            cmd = f"ip addr show dev {opposite_dev} |grep 'inet '|cut -d ' ' -f 6"
            cmd_rtn, all_opposite_ip, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=opposite_addr)
            if cmd_rtn != RtnStatusEnum.SUCCESS.value:
                return cmd_rtn

            for opposite_ip in all_opposite_ip.split('\n'):
                cmd = f'arp -n |grep -w {current_dev}|grep -w {opposite_ip.split("/")[0]}'
                cmd_rtn, cmd_res, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, cmd_execute_address=current_addr)
                if 'incomplete' in cmd_res or not cmd_res:
                    log.error(f'{current_addr.title()}: {current_dev}, arp有错误！')
                    return RtnStatusEnum.FAIL.value
                else:
                    log.info(f'{current_addr.title()}: {current_dev}, arp正确')
            log.info(f'完成检查{current_dev}的arp')
        else:
            log.info(f'开始检查{current_dev}的neigh')
            # 获取对端设备ip
            cmd = f"ip addr show dev {opposite_dev} |grep 'inet6 '|grep -v fe80|cut -d ' ' -f 6"
            cmd_rtn, all_opposite_ip, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=opposite_addr)
            if cmd_rtn != RtnStatusEnum.SUCCESS.value:
                return cmd_rtn

            for opposite_ip in all_opposite_ip.split('\n'):
                cmd = f'ip -6 neigh show |grep -w {current_dev}|grep -w {opposite_ip.split("/")[0]}'
                cmd_rtn, cmd_res, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, cmd_execute_address=current_addr)
                if 'FAILED' in cmd_res or not cmd_res:
                    log.error(f'{current_addr.title()}: {current_dev}, neigh有错误！')
                    return RtnStatusEnum.FAIL.value
                else:
                    log.info(f'{current_addr.title()}: {current_dev}, neigh正确')
            log.info(f'完成检查{current_dev}的neigh')

    @classmethod
    def reset_driver_by_flr(cls, caller_class, device_name: str,
                            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, nets_name: str = ''):
        """
        author: wei.yuan1
        date: 2024.11.25
        description: 对驱动进行FLR复位
        :param device_name: 网口名称
        :param cmd_execute_address: 执行环境
        :param nets_name: namespace
        :return: None
        @changelog:
            1. 2025.06.13：shanshan.du 适配namespace
        """
        CommonOperation.concat_test_steps(f"对设备{device_name}的驱动进行复位")
        bus_info = EthtoolOperation.show_driver_infomation(device_name, cmd_execute_address,
                                                           nets_name=nets_name)['bus-info']
        exec_cmd = f'echo 1 > /sys/bus/pci/devices/{bus_info}/reset'
        if nets_name:
            exec_cmd = f'ip netns exec {nets_name} {exec_cmd}'
        rtn_code, *_ = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=exec_cmd, cmd_execute_address=cmd_execute_address)
        CommonOperation.result_collect(case_cls=caller_class, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                       rtn_code=rtn_code, description=f"对{device_name}的驱动进行复位",
                                       expect_info="成功", result="失败")

    @classmethod
    def reset_driver_by_pfr(cls, caller_class, device_name: str,
                            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, check_ignore: bool = False,
                            bus_info: str = ""):
        """
        author: shanshan.du
        date: 2025.03.11
        description: 对驱动进行PFR复位
        :param device_name: 网口名称
        :param cmd_execute_address: 执行环境
        :return: None
        """
        nicg = cls.get_nic_generation()
        CommonOperation.concat_test_steps(f"对设备{device_name}的驱动进行复位")
        if not bus_info:
            bus_info = EthtoolOperation.show_driver_infomation(device_name, cmd_execute_address)['bus-info']
        rtn_code, *_ = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=f'echo "pfr trigger" > /sys/kernel/debug/{nicg}/{bus_info}/command',
            cmd_execute_address=cmd_execute_address)
        # time.sleep(6)
        if check_ignore:
            return
        CommonOperation.result_collect(case_cls=caller_class, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                       rtn_code=rtn_code, description=f"对{device_name}的驱动进行复位",
                                       expect_info="成功", result="失败"
                                       )

    @classmethod
    def get_vf_trust_state(cls, pf_device, vf_id,
                           cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author:      jianghe
        date:        2025.04.29
        description: 获取开关状态
        :return:     None
        """
        cmd = f"ip link show {pf_device} |grep 'vf {vf_id}'"
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address=cmd_execute_address)
        if 'trust off' in out:
            return SwitchEnum.SWITCH_OFF.value
        else:
            return SwitchEnum.SWITCH_ON.value

    @classmethod
    def reset_driver_by_vfr(cls, cmd_execute_address: str, eth_device: str = "", bdf: str = "",
                            state: str = None, name_space: str = None) -> bool:
        """
        author:      lizhuang.xu
        date:        2025-03-21 11:35:20
        description: rdma_reset
        :return:     None
        """
        if name_space:
            result = False
            if not eth_device:
                exec_command = f"ip netns exec {name_space} ls /sys/bus/pci/devices/{bdf}/net"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    exec_command, cmd_execute_address=cmd_execute_address)
                # bus-info: 0000:31:00.0
                if rtn_outputs:
                    eth_device = rtn_outputs
                else:
                    log.error("未找到设备device，无法进行vfr_reset操作！！")
                    return result
            vf_num = eth_device.split("v")[1]
            pf_device = eth_device.split("v")[0]
            if state is None:
                before_state = cls.get_vf_trust_state(pf_device, vf_num)
                state = SwitchEnum.SWITCH_ON.value if before_state == SwitchEnum.SWITCH_OFF.value else SwitchEnum.SWITCH_OFF.value
            exec_command = f"ip link set {pf_device} vf {vf_num} trust {state}"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                result = True
            else:
                log.error("执行vfr复位操作异常，return code：{}！！".format(rtn_code))
            return result
        else:
            result = False
            if not eth_device:
                exec_command = "ls /sys/bus/pci/devices/{}/net".format(bdf)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    exec_command, cmd_execute_address=cmd_execute_address)
                # bus-info: 0000:31:00.0
                if rtn_outputs:
                    eth_device = rtn_outputs
                else:
                    log.error("未找到设备device，无法进行vfr_reset操作！！")
                    return result
            vf_num = eth_device.split("v")[1]
            pf_device = eth_device.split("v")[0]
            if state is None:
                before_state = cls.get_vf_trust_state(pf_device, vf_num)
                state = SwitchEnum.SWITCH_ON.value if before_state == SwitchEnum.SWITCH_OFF.value else SwitchEnum.SWITCH_OFF.value
            exec_command = f"ip link set {pf_device} vf {vf_num} trust {state}"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                result = True
            else:
                log.error("执行vfr复位操作异常，return code：{}！！".format(rtn_code))
            return result

    @classmethod
    def rdma_reset(cls, cmd_execute_address: str, eth_device: str = "", bdf: str = "") -> bool:
        """
        author:      lizhuang.xu
        date:        2025-03-21 11:35:20
        description: rdma_reset
        :return:     None
        """
        nicg = cls.get_nic_generation()
        result = False
        if not bdf:
            exec_command = "ethtool -i '{}'".format(eth_device)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=cmd_execute_address)
            # bus-info: 0000:31:00.0
            bdfs = re.findall(r"bus-info: (\S\S\S\S:\S\S:\S\S.\S)", rtn_outputs)
            if bdfs:
                bdf = bdfs[0]
            else:
                log.error("未找到设备bdf，无法进行rdma_reset操作！！")
                return result
        exec_command = f"echo 1 >  /sys/kernel/debug/{nicg}rdma/{bdf}/COMMON/reset_en"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            result = True
        else:
            log.error("执行rdma复位操作异常，return code：{}！！".format(rtn_code))
        return result

    @classmethod
    def start_reset(cls, caller_class, device_name: str, device_bdf: str, reset_type: str,
                    exec_addr = CmdExecuteAdressEnum.SERVER.value,
                    check_ignore: bool = False, name_space: str = None) -> None:
        """
        author: jianghe
        date  : 2025.04.25
        description: 执行复位，支持PFR PFLR VFR VFLR，
        说明，pfr pflr写pf_device_name pf_device_bdf，vfr vflr写vf_device_name vf_device_bdf
        return: 无返回值
        """
        if reset_type == ResetType.PFLR.value:
            result = CommonOperation.function_level_reset(exec_addr, device_name, device_bdf)
            if not check_ignore:
                if result:
                    log.info(f'device:{device_name}执行PFLR复位成功')
                else:
                    CommonOperation.create_bug_problem(caller_class, key_word=f"PFLR复位执行失败",
                                                       description_word='PFLR复位执行失败',
                                                       expect_info='PFLR复位执行成功',
                                                       result_info='PFLR复位执行失败')
        elif reset_type == ResetType.PFR.value:
            CommonOperation.reset_driver_by_pfr(caller_class, device_name, check_ignore=check_ignore, bus_info=device_bdf)
        elif reset_type == ResetType.VFLR.value:
            result = CommonOperation.function_level_reset(exec_addr, device_name, device_bdf, name_space=name_space)
            if not check_ignore:
                if result:
                    log.info(f'device:{device_name}执行VFLR复位成功')
                else:
                    CommonOperation.create_bug_problem(caller_class, key_word=f"VFLR复位执行失败",
                                                       description_word='VFLR复位执行失败',
                                                       expect_info='VFLR复位执行成功',
                                                       result_info='VFLR复位执行失败')
        elif reset_type == ResetType.VFR.value:
            result = CommonOperation.reset_driver_by_vfr(exec_addr, device_name, device_bdf, name_space=name_space)
            if not check_ignore:
                if result:
                    log.info(f'device:{device_name}执行vfr复位成功')
                else:
                    CommonOperation.create_bug_problem(caller_class, key_word=f"vfr复位执行失败",
                                                       description_word='vfr复位执行失败',
                                                       expect_info='vfr复位执行成功',
                                                       result_info='vfr复位执行失败')
        elif reset_type == ResetType.RDMA.value:
            result = CommonOperation.rdma_reset(exec_addr, device_name, device_bdf)
            if not check_ignore:
                if result:
                    log.info(f'device:{device_name}执行rdma主动复位成功')
                else:
                    CommonOperation.create_bug_problem(caller_class, key_word=f"rdma主动复位执行失败",
                                                       description_word='rdma主动复位执行失败',
                                                       expect_info='rdma主动复位执行成功',
                                                       result_info='rdma主动复位执行失败')
        elif reset_type == ResetType.CORER.value:
            CommonOperation.fw_reset(caller_class, device_bdf, FwResetType.Core_Reset.value, exec_addr, check_ignore)
        elif reset_type == ResetType.SYS.value:
            CommonOperation.fw_reset(caller_class, device_bdf, FwResetType.Sys_Reset.value, exec_addr, check_ignore)
        elif reset_type == ResetType.PCIE.value:
            CommonOperation.fw_reset(caller_class, device_bdf, FwResetType.PCIe_Reset.value, exec_addr, check_ignore)
        else:
            log.error(f'{reset_type}不支持，请检查复位方式是否正确')
            CommonOperation.create_bug_problem(caller_class, key_word=f"不支持{reset_type}复位",
                                               description_word=f'不支持{reset_type}复位',
                                               expect_info='复位方式填写正确',
                                               result_info='复位方式填写错误')

    @classmethod
    def wait_cli_resume_normal(cls, caller_class, dev_para, timeout = 30,
                               cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: jianghe
        date  : 2025.07.18
        description: 等待cli恢复正常
        return: 无返回值
        """
        nicg = cls.get_nic_generation()
        cmd = f'{constants.SCGBECLI64} -d {dev_para} show'
        ind = 0
        while ind < timeout:
            code, output, stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=cmd_execute_address)
            if 'Status      = Success' in output:
                log.info(f'第{ind}秒，命令{cmd}执行成功')
                break
            else:
                log.info(f'第{ind}秒，命令{cmd}执行失败')
            ind += 1
            time.sleep(1)
        if ind == timeout:
            CommonOperation.create_bug_problem(caller_class, key_word='cli',
                                               description_word=f'等待{timeout}s，命令{cmd}仍然执行失败')

    @classmethod
    def wait_link_detected_yes(cls, caller_class, device_name, timeout=180,
                               cmd_execute_address = CmdExecuteAdressEnum.SERVER.value):
        """
        author: jianghe
        date  : 2026.04.01
        description: 等待链路状态恢复yes
        return: 无返回值
        """
        ind = 0
        retry = 0
        while ind < timeout:
            ethtool = EthtoolOperation.get_standard_info(device_name, cmd_execute_address)
            if ethtool['Link detected'] == 'yes':
                retry = retry + 1
                log.info(f'第{ind}秒，端口{device_name}的link detected是yes')
                # corereset后一开始能ping通，因此，改为持续前2s都能ping通才break
                # 建链会出现先up后再down，重新建链的过程，需要连续3次ping通才算最终状态
                # 问下刚才会上说的，本端先切速10G，对端再切速10G，
                # 对端是先按照上次的速率15，fec 15，建链，等建链up后对端会按照10G的配置再进行一次10G建链，
                # 这个流程能优化吗，在15 15建链过程中收到10G配置，直接按照10G走建链流程
                if ind > 2 and retry > 3:
                    break
            else:
                log.info(f'第{ind}秒，端口{device_name}的link detected不是yes')
                retry = 0
            ind += 1
            time.sleep(1)
        if ind == timeout:
            CommonOperation.create_bug_problem(caller_class, key_word='网口连通性检查',
                                               description_word=f'等待{timeout}s，端口{device_name}的link detected仍然不是yes')

    @classmethod
    def wait_ping_resume_normal(cls, caller_class, device_ip, timeout=180,
                                cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: jianghe
        date  : 2025.08.15
        description: 等待ping通对端，用于复位恢复正常检查，用于建链成功检查
        return: 无返回值
        """
        cmd = f"ping {device_ip} -c 1 -W 0.1"
        ind = 0
        retry = 0
        while ind < timeout:
            code, output, stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, cmd_execute_address=cmd_execute_address)
            if code == RtnStatusEnum.SUCCESS.value:
                retry = retry + 1
                log.info(f'第{ind}秒，能ping通对端')
                # corereset后一开始能ping通，因此，改为持续前2s都能ping通才break
                # 建链会出现先up后再down，重新建链的过程，需要连续3次ping通才算最终状态
                # 问下刚才会上说的，本端先切速10G，对端再切速10G，
                # 对端是先按照上次的速率15，fec 15，建链，等建链up后对端会按照10G的配置再进行一次10G建链，
                # 这个流程能优化吗，在15 15建链过程中收到10G配置，直接按照10G走建链流程
                if ind > 2 and retry > 3:
                    break
            else:
                log.info(f'第{ind}秒，不能ping通对端')
                retry = 0
            ind += 1
            time.sleep(1)
        if ind == timeout:
            CommonOperation.create_bug_problem(caller_class, key_word='网口连通性检查',
                                               description_word=f'等待{timeout}s，命令{cmd}仍然执行失败')

    @classmethod
    def check_ping_loss(cls, caller_class, device_ip, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: jianghe
        date  : 2025.08.15
        description: 等待ping通对端，用于复位恢复正常检查，用于建链成功检查
        return: 无返回值
        """
        cmd = f"ping {device_ip} -c 10 -W 0.1"
        code, output, stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=cmd_execute_address)
        if ' 0% packet loss' not in output:
            log.info(f'命令{cmd}的返回结果{code}\n{output}\n{stderr}')
            CommonOperation.create_bug_problem(caller_class, key_word='网口连通性检查',
                                               description_word=f'命令{cmd}有丢包')

    @classmethod
    def cli_dev_show(cls, caller_class, dev_para, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: jianghe
        date  : 2025.04.25
        description: 检查cli -d $dev show，是否执行成功
        return: 无返回值
        """
        nicg = cls.get_nic_generation()
        cmd = f'{constants.SCGBECLI64} -d {dev_para} show'
        code, output, stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=cmd_execute_address)
        if 'Status      = Success' in output:
            log.info(f'命令{cmd}执行成功')
        else:
            log.error(f'命令{cmd}执行失败，返回信息是{code}\n{output}\n{stderr}')
            CommonOperation.create_bug_problem(caller_class, key_word=f"CLI",
                                               description_word=f'命令{cmd}执行失败',
                                               expect_info=f'命令{cmd}执行成功')

    @classmethod
    def execute_commond_and_check_result(cls, caller_class, cmd, exp_rtn,
                                         cmd_execute_address = CmdExecuteAdressEnum.SERVER.value):
        """
        author: jianghe
        date  : 2025.04.25
        description: 执行命令，是否有期望的返回结果
        return: 无返回值
        """
        code, output, stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=cmd_execute_address)
        if type(exp_rtn) == str:  # 字符串
            if exp_rtn in output or exp_rtn in stderr:
                log.info(f'命令{cmd}执行，有期望的返回结果{exp_rtn}')
            else:
                log.error(f'命令{cmd}执行，没有期望的返回结果{exp_rtn}，返回信息是{code}\n{output}\n{stderr}')
                CommonOperation.create_bug_problem(caller_class, key_word=f"CLI",
                                                   description_word=f'命令{cmd}执行，没有期望的返回结果{exp_rtn}',
                                                   expect_info=f'命令{cmd}执行，期望的返回结果{exp_rtn}')
        if type(exp_rtn) == list:  # 字符串列表
            found = False
            for key in exp_rtn:
                if key in output.strip() or key in stderr.strip() or re.findall(key, output) or re.findall(key, stderr):
                    log.info(f'命令{cmd}执行，有期望的返回结果{key}')
                    found = True
            if not found:
                log.error(f'命令{cmd}执行，没有期望的返回结果{exp_rtn}，返回信息是{code}\n{output}\n{stderr}')
                CommonOperation.create_bug_problem(caller_class, key_word=f"CLI",
                                                   description_word=f'命令{cmd}执行，没有期望的返回结果{exp_rtn}')

    @classmethod
    def get_bdf_of_nic(cls, nic_name: str, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author:         jianghe
        date:           2025.04.23
        description:    获取bdf
        """
        # client端是发包仪，直接返回
        if cls.is_renix_only() and cmd_execute_address==CmdExecuteAdressEnum.CLIENT.value:
            return ''

        cmd = "ethtool -i {} |grep 'bus-info'".format(nic_name)
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=cmd_execute_address)
        log.info(rtn_stdout)
        bdf_info = rtn_stdout.split(": ")[-1]
        return bdf_info

    @classmethod
    def get_nic_by_bdf(cls, bdf: str, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author:         xiangyu.liu
        date:           2025.04.23
        description:    获取bdf
        """
        cmd = f"ls /sys/bus/pci/devices/{bdf}/net"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=cmd_execute_address)
        log.info(rtn_stdout)
        lan_dev = rtn_stdout
        return lan_dev

    @classmethod
    def set_eth_ip(cls, caller_class, device_name: str, ipv4_ip: str, ipv6_ip: str,
                   exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jinbo.zhang
        date  : 2024.12.30
        description: 根据device_name设置ip
        return: 无返回值
        """
        if len(ipv4_ip) != 0:
            cmd = f'ip addr add {ipv4_ip}/24 dev {device_name}'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd,
                                                                                         cmd_execute_address=exec_addr)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'设置ip地址成功，{device_name} ipv4 ip 为{ipv4_ip}')
            else:
                log.info(f'设置ip地址失败')
                CommonOperation.create_bug_problem(caller_class, key_word='设置ip地址失败',
                                                   description_word=f'设置ip地址失败',
                                                   expect_info=f'设置ip地址成功',
                                                   result_info=f'设置ip地址失败')
        if len(ipv6_ip) != 0:
            cmd = f'ip -6 addr add {ipv6_ip} dev {device_name}'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd,
                                                                                         cmd_execute_address=exec_addr)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'设置ip地址成功，{device_name} ipv6 ip 为{ipv6_ip}')
            else:
                log.info(f'设置ip地址失败')
                CommonOperation.create_bug_problem(caller_class, key_word='设置ip地址失败',
                                                   description_word=f'设置ip地址失败',
                                                   expect_info=f'设置ip地址成功',
                                                   result_info=f'设置ip地址失败')

    @classmethod
    def delete_eth_ip(cls, caller_class, device_name: str, ipv4_ip: str, ipv6_ip: str,
                   exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jianghe
        date  : 2025.07.08
        description: 删除IP
        return: 无返回值
        """
        if len(ipv4_ip) != 0:
            cmd = f'ip addr delete {ipv4_ip} dev {device_name}'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd,
                                                                                         cmd_execute_address=exec_addr)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'删除ip地址成功，{device_name} ipv4 ip 为{ipv4_ip}')
            else:
                log.info(f'删除ip地址失败')
                CommonOperation.create_bug_problem(caller_class, key_word='删除ip地址失败',
                                                   description_word=f'删除ip地址失败',
                                                   expect_info=f'删除ip地址成功',
                                                   result_info=f'删除ip地址失败')
        if len(ipv6_ip) != 0:
            cmd = f'ip -6 addr delete {ipv6_ip} dev {device_name}'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd,
                                                                                         cmd_execute_address=exec_addr)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'删除ip地址成功，{device_name} ipv6 ip 为{ipv6_ip}')
            else:
                log.info(f'删除ip地址失败')
                CommonOperation.create_bug_problem(caller_class, key_word='删除ip地址失败',
                                                   description_word=f'删除ip地址失败',
                                                   expect_info=f'删除ip地址成功',
                                                   result_info=f'删除ip地址失败')

    @classmethod
    def fw_reset(cls, caller_class, device_bdf: str = '', type: str = '',
                 exec_addr = CmdExecuteAdressEnum.CLI_DEFAULT.value, check_ignore: bool = False) -> None:
        """
        author:      jianghe
        date:        2025.04.23
        description: cli命令触发fw reset
        """
        cmd = f"{constants.SCGBECLI64} -d {device_bdf} reset type={type}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd,
                                                                                     cmd_execute_address=exec_addr)
        if check_ignore:
            return
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'命令{cmd}执行成功')
        else:
            CommonOperation.create_bug_problem(caller_class, key_word=f'reset',
                                               description_word=f'命令{cmd}执行失败，'
                                                                f'返回信息是{rtn_code}\n{rtn_outputs}\n{rtn_err}')

    @classmethod
    def check_vf_exist(cls, caller_class, vf_device_name: str = '',
                       exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author:      jianghe
        date:        2025.05.06
        description: 检查vf是否存在
        """
        pf_device_name, _ = vf_device_name.split('v')
        sec = 0
        vf_list = []
        while sec < 60:
            log.info(f'循环查询30秒，当前第{sec}秒')
            vf_list = CommonOperation.get_vf_list(pf_device_name, exec_addr)
            if vf_device_name in vf_list:
                log.info(f'{vf_device_name}存在')
                break
            else:
                sec += 1
                time.sleep(1)
        if sec == 60:
            CommonOperation.create_bug_problem(caller_class, key_word=f'VF',
                                               description_word=f'{vf_device_name}不存在，查询到的vf_list: {vf_list}')

    @classmethod
    def qemu_inject_err(cls, err_cmd, host_ip, inject_port) -> None:
        """
        author:      jianghe
        date:        2025.05.06
        description: 注入故障，host_ip是宿主机IP，inject_port是故障注入端口
        """
        cmd = f'echo {err_cmd} | nc {host_ip} {inject_port}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
        log.info(f'命令{cmd}的执行结果是{code}\n{out}\n{err}')

    @classmethod
    def execute_command_with_check(cls, caller_class, cmd,
                                   cmd_execute_address = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jianghe
        date  : 2025.07.12
        description: 执行命令并检查结果
        """
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd, cmd_execute_address=cmd_execute_address)
        log.info(f'命令{cmd}的返回信息是{code}\n{out}\n{err}')
        if code == RtnStatusEnum.SUCCESS.value:
            log.info(f'命令{cmd}执行成功')
        else:
            log.error(f'命令{cmd}执行失败')
            CommonOperation.create_bug_problem(caller_class, key_word=f'FW', description_word=f'命令执行失败')

    @classmethod
    def get_scgbe_num(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> int:
        """
        author: jianghe
        date  : 2025.08.15
        description: 执行命令并检查结果
        """
        _, output, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=f'lspci -Dn | grep {constants.PRODUCT_FLAG}', cmd_execute_address=cmd_execute_address)
        domain_lst = re.findall(rf'(\d+):.*{constants.PRODUCT_FLAG}', output)
        domain_set = set(domain_lst)
        return len(domain_set)

    @classmethod
    def get_nic_and_pf_count(cls, exec_addr=CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author:      jianghe
        date:        2025.11.15
        description: 通过cli命令查询网卡和pf个数，返回信息如下：2, [['0000:2a:00.0'], ['0000:61:00.0', '0000:61:00.1']]
        """
        cmd = f"{constants.SCGBECLI64} show"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd, cmd_execute_address=exec_addr)

        found = re.findall('Controller [0-9]', rtn_outputs)
        nic_count = len(found)
        nic_pf_list = []
        controller_ind_list = []
        for i in range(nic_count):
            controller_ind_list.append(rtn_outputs.index(f'Controller {i}:'))

        for i, controller_ind in enumerate(controller_ind_list):
            if i == len(controller_ind_list) - 1:
                found = re.findall(
                    '\|([0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}.[0-9a-f]{1})\s\|.*\|.*\|.*\|.*\|.*\|.*\|.*\|',
                    rtn_outputs[controller_ind_list[i]:])
                nic_pf_list.append(list(found))
            else:
                found = re.findall(
                    '\|([0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}.[0-9a-f]{1})\s\|.*\|.*\|.*\|.*\|.*\|.*\|.*\|',
                    rtn_outputs[controller_ind_list[i]: controller_ind_list[i + 1]])
                nic_pf_list.append(list(found))
        return nic_count, nic_pf_list

        # cmd = f"{constants.SCGBECLI64} show j"
        # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
        #     cmd, cmd_execute_address=exec_addr)
        # found = re.findall('Controller [0-9]', rtn_outputs)
        # nic_count = len(found)
        # nic_pf_list = []
        # out_dict = eval(rtn_outputs)
        # for ind in range(nic_count):
        #     pf_list = out_dict['System']['System Overview'][f'Controller {ind}']
        #     pf_bus_info_list = []
        #     for pf in pf_list:
        #         pf_bus_info_list.append(pf['Device'])
        #     nic_pf_list.append(pf_bus_info_list)
        # return nic_count, nic_pf_list

    @classmethod
    def get_max_vf_count(cls, bus_info, exec_addr=CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author:      jianghe
        date:        2025.12.19
        description: 获取当前网口允许创建的最大vf数
        """
        nic_count, all_pf_list = CommonOperation.get_nic_and_pf_count(exec_addr)
        for pf_list in all_pf_list:
            if bus_info in pf_list:
                return int(constants.MAX_VF_NUM / len(pf_list))

    @classmethod
    def print_host_time(cls):
        """
        author:      jianghe
        date:        2025.12.19
        description: 获取当前网口允许创建的最大vf数
        """
        cmd = 'date'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd,
                                                                                      CmdExecuteAdressEnum.SERVER.value)
        log.info(f'本端主机侧时间是{out}')
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd,
                                                                                      CmdExecuteAdressEnum.CLIENT.value)
        log.info(f'对端主机侧时间是{out}')

    @classmethod
    def get_rdma_mode(cls, bdf, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> str:
        # client端是发包仪，直接返回
        if cls.is_renix_only() and cmd_execute_address==CmdExecuteAdressEnum.CLIENT.value:
            return ''

        if bdf.count(':') > 1:
            bdf = ':'.join(bdf.split(':')[1:])
        cmd = f'lspci |grep {bdf}'
        _, output, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=cmd_execute_address)
        if RdmaMode.Infiniband.value in output:
            rdma_mode = RdmaMode.Infiniband.value
        else:
            rdma_mode = RdmaMode.RoCE.value
        return rdma_mode

    @classmethod
    def get_pcie_aer_ue_ce_status(cls, bdf_info, exec_addr=CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author:      yibo.gao
        date:        2026.03.04
        description: 通过lspci命令获取aer中是否有ce/ue错误
        return 方法status, ue错误列表, ce错误列表   bool, list, list
        """
        if not bdf_info:
            return False, list(), list()

        cmd = "lspci -vvvs {} |grep 'Advanced Error Reporting' -A 20".format(bdf_info)

        status, result, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=exec_addr)

        aer_info = list()
        for i in result.split("Capabilities: "):
            if "Advanced Error Reporting".lower() in i.lower():
                aer_info = i.split("\n")[1:]
                # aer_info = "\n".join(i.split("\n")[1:])
                break
        # if not result or status != RtnStatusEnum.SUCCESS.value:
        if not aer_info:
            log.error(f"查询[{bdf_info}]的lspci AER信息失败, status:{status}")
            return False, list(), list()

        # print(f"aer_info:{aer_info}")

        ue_list, ce_list = list(), list()

        for i in range(len(aer_info)):
            if "UESta:" in aer_info[i]:
                ue_list += aer_info[i].split(":")[1].strip().split(" ")
                for k in aer_info[i+1:]:
                    if "UEMsk:" not in k:
                        ue_list += k.strip().split(" ")
                    else:
                        break
                break

        for i in range(len(aer_info)):
            if "CESta:" in aer_info[i]:
                ce_list += aer_info[i].split(":")[1].strip().split(" ")
                for k in aer_info[i+1:]:
                    if "CEMsk:" not in k:
                        ce_list += k.strip().split(" ")
                    else:
                        break
                break

        aercap_count, headerlog_info = "", ""
        for i in aer_info:
            if "aercap:" in i.lower():
                func_m = re.search(r"First Error Pointer:\s*([0-9a-f]+),", i, flags=re.I)
                if func_m:
                    aercap_count = func_m.group(1)  # int(m.group(1))
                else:
                    log.warning("未能从lspci AER信息中获取AERCap_Pointer数量")
            elif "headerlog:" in i.lower():
                headerlog_info = i.split(":")[1].strip()

        # ue = re.search(f"UESta:\s*(.+)", result, flags=re.I)
        # ce = re.search(f"CESta:\s*(.+)", result, flags=re.I)
        #
        # if not ue or not ce:
        #     log.error(f"通过正则获取[{bdf_info}]的UESta和CESta信息失败")
        #     return False, list(), list()
        #
        # ue_list = ue.group(1).split(' ')
        # ce_list = ce.group(1).split(' ')
        log.info(f"获取到的UESta: {ue_list}")
        log.info(f"获取到的CESta: {ce_list}")

        ue_err_list, ce_err_list = list(), list()
        for i in ue_list:
            if "+" in i:
                ue_err_list.append(i[:-1])
        for i in ce_list:
            if "+" in i:
                ce_err_list.append(i[:-1])

        if ue_err_list:
            log.warning(f"[{bdf_info}]出现的UE错误:{ue_err_list}")
        if ce_err_list:
            log.warning(f"[{bdf_info}]出现的CE错误:{ce_err_list}")

        if headerlog_info and "00000000 00000000 00000000 00000000" not in headerlog_info:
            log.warning(f"[{bdf_info}]的HeaderLog: {headerlog_info}; AERCap Pointer: {aercap_count}")
            # 临时放入ce_err_list中
            # ce_err_list.append("HeaderLog:{}, AERCap Pointer: {}".format(headerlog_info, aercap_count))
        # else:
        #     log.info("HeaderLog: {}, AERCap Pointer: {}".format(headerlog_info, aercap_count))

        if not ue_err_list and not ce_err_list:
            log.info(f"[{bdf_info}]的UESta和CESta检查通过,无异常")

        return True, ue_err_list, ce_err_list

    @classmethod
    def get_rp_bdf_for_ep_bdf(cls, bdf_info, exec_addr=CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author:      yibo.gao
        date:        2026.03.04
        description: 通过网卡的EP,获取网卡RP的BDF
        return RP_BDF字符串,获取失败则返回空
        """
        if not bdf_info:
            return ""
        cmd = f"readlink /sys/bus/pci/devices/{bdf_info}"

        status, result, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, cmd_execute_address=exec_addr)
        if not result or status != RtnStatusEnum.SUCCESS.value:
            log.error(f"查询EP[{bdf_info}]的RP_BDF失败, status:{status}")
            return ""
        try:
            rp_bdf = result.split("/")[-2]
        except IndexError:
            log.error(f"从返回的结果中, 获取EP[{bdf_info}]的RP_BDF失败")
            return ""

        log.info(f"获取到EP[{bdf_info}]的RP_BDF:{rp_bdf}")
        return rp_bdf

    @classmethod
    def disable_pcie_error_reporting(cls, bdf_info, exec_addr=CmdExecuteAdressEnum.SERVER.value) -> bool:
        """
        author:      yibo.gao
        date:        2026.03.04
        description: 通过BDF,关闭pcie错误处理功能
        return 关闭结果status
        """
        if not bdf_info:
            return False

        cmd_1 = f"setpci -s {bdf_info} cap_exp+08.b=0:f"
        cmd_2 = f"setpci -s {bdf_info} 04.w=0:100"

        status, result, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd_1, cmd_execute_address=exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            log.error(f"[{bdf_info}]关闭PCIe错误处理,命令执行失败, status:{status}")
            return False

        status, result, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd_2, cmd_execute_address=exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            log.error(f"[{bdf_info}]关闭PCIe错误处理,命令执行失败, status:{status}")
            return False

        log.info(f"[{bdf_info}]关闭PCIe错误处理,命令执行成功")
        return True

    @classmethod
    def clean_aer_status(cls, bdf_info, exec_addr=CmdExecuteAdressEnum.SERVER.value) -> bool:
        """
        author:      yibo.gao
        date:        2026.03.04
        description: 通过BDF,清除AER错误统计信息
        return 关闭结果status
        """
        if not bdf_info:
            return False

        cmd_1 = f"setpci -s {bdf_info} ECAP_AER+0x4.l=ffffffff"
        cmd_2 = f"setpci -s {bdf_info} ECAP_AER+0x10.l=ffffffff"

        status, result, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd_1, cmd_execute_address=exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            log.error(f"[{bdf_info}]清除AER错误统计信息命令,命令执行失败, status:{status}")
            return False

        status, result, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd_2, cmd_execute_address=exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            log.error(f"[{bdf_info}]清除AER错误统计信息命令,命令执行失败, status:{status}")
            return False

        log.info(f"[{bdf_info}]清除AER错误统计信息,命令执行成功")
        return True

    @classmethod
    def get_sub_device_id_for_bdf(cls, bdf_info, exec_addr=CmdExecuteAdressEnum.SERVER.value,
                                  caller_class=None) -> str:
        """
        author:      yibo.gao
        date:        2026.03.06
        description: 通过BDF,获取设备sub_device_id,确定网卡设备类型
        :param bdf_info: 设备bdf, device_info
        :param exec_addr: 执行命令位置
        :param caller_class: 未确定设备类型时,报bug, 传入调用类
        return: 关闭结果status
        """
        cmd = "lspci -vvvs {} | grep -i 'subsystem'".format(bdf_info)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd, cmd_execute_address=exec_addr)

        if constants.SUB_DEVICE_ID_OCP_X2.lower() in rtn_outputs.lower():
            log.info(f"识别到[{bdf_info}]的sub_device_id是[{constants.SUB_DEVICE_ID_OCP_X2}],设备类型:OCP_x2")
            return constants.SUB_DEVICE_ID_OCP_X2
        elif constants.SUB_DEVICE_ID_OCP_X4.lower() in rtn_outputs.lower():
            log.info(f"识别到[{bdf_info}]的sub_device_id是[{constants.SUB_DEVICE_ID_OCP_X4}],设备类型:OCP_x4")
            return constants.SUB_DEVICE_ID_OCP_X4
        elif constants.SUB_DEVICE_ID_PCIE_X2.lower() in rtn_outputs.lower():
            log.info(f"识别到[{bdf_info}]的sub_device_id是[{constants.SUB_DEVICE_ID_PCIE_X2}],设备类型:PCIE_x2_25G")
            return constants.SUB_DEVICE_ID_PCIE_X2
        elif constants.SUB_DEVICE_ID_PCIE_X2_10G.lower() in rtn_outputs.lower():
            log.info(f"识别到[{bdf_info}]的sub_device_id是[{constants.SUB_DEVICE_ID_PCIE_X2_10G}],设备类型:PCIE_x2_10G")
            return constants.SUB_DEVICE_ID_PCIE_X2_10G
        else:
            log.error(f"未识别到[{bdf_info}]的sub_device_id, 不是已知NIC设备类型")
            if caller_class:
                cls.create_bug_problem(
                    case_cls=caller_class, key_word=f"通过lspci获取[{bdf_info}]的sub_device_id",
                    description_word=f"获取失败,未识别到[{bdf_info}]的sub_device_id,不是已知NIC设备类型",
                    expect_info=f"获取成功",
                    result_info=f"获取失败")
            return ""

    @classmethod
    def get_image_upgrade_file_for_bdf(cls, bdf_info, exec_addr=CmdExecuteAdressEnum.SERVER.value,
                                       caller_class=None):
        """
        author:      yibo.gao
        date:        2026.03.06
        description: 通过BDF确定设备类型,拿到Cli升级用的默认Image包
        :param bdf_info: 设备bdf, device_info
        :param exec_addr: 执行命令位置
        :param caller_class: 未找到升级文件时,报bug, 传入调用类
        return: Image文件路径
        """
        sub_did = cls.get_sub_device_id_for_bdf(bdf_info=bdf_info, exec_addr=exec_addr, caller_class=caller_class)
        if not sub_did:
            return ""
        old_find_path = constants.UPGRADE_IMAGE_PACKAGE_PATH
        if sub_did == constants.SUB_DEVICE_ID_OCP_X2:
            find_path = constants.OCP_X2_25G_IMAGE_PACKAGE_PATH
        elif sub_did == constants.SUB_DEVICE_ID_OCP_X4:
            find_path = constants.OCP_X4_25G_IMAGE_PACKAGE_PATH
        elif sub_did == constants.SUB_DEVICE_ID_PCIE_X2:
            find_path = constants.PCIE_X2_25G_IMAGE_PACKAGE_PATH
        elif sub_did == constants.SUB_DEVICE_ID_PCIE_X2_10G:
            find_path = constants.PCIE_X2_10G_IMAGE_PACKAGE_PATH
        else:
            log.error(f"没有找到[{bdf_info}]对应的Image升级文件,没有指定寻找路径")
            if caller_class:
                cls.create_bug_problem(
                    case_cls=caller_class, key_word=f"没有找到[{bdf_info}]对应的Image升级文件,没有指定寻找路径",
                    description_word=f"寻找默认升级文件失败",
                    expect_info=f"获取成功",
                    result_info=f"获取失败")
            return ""

        file_path = cls.get_full_path(find_path, exec_addr)
        if not file_path:
            file_path = cls.get_full_path(old_find_path, exec_addr)
            if not file_path:
                log.error(f"没有找到[{bdf_info}]对应的Image升级文件,寻找路径:{find_path} 和{old_find_path}")
                if caller_class:
                    cls.create_bug_problem(
                        case_cls=caller_class, key_word=f"没有找到[{bdf_info}]对应的Image升级文件",
                        description_word=f"寻找默认升级文件失败",
                        expect_info=f"获取成功",
                        result_info=f"获取失败")
                return ""
            else:
                # 此处之后需要结合实际测试需求,新增判断,目前只取第一个
                file_path = file_path.split("\n")[0]
                log.warning(f"通过旧的路径,找到Image升级文件:{file_path}")
                return file_path

        # 此处之后需要结合实际测试需求,新增判断,目前只取第一个
        file_path = file_path.split("\n")[0]
        log.info(f"找到[{bdf_info}]对应的Image升级文件:{file_path}")
        return file_path

    @classmethod
    def get_bmc_pldm_upgrade_file_for_bdf(cls, bdf_info, exec_addr=CmdExecuteAdressEnum.SERVER.value,
                                          noverchk_flag=True, caller_class=None):
        """
        author:      yibo.gao
        date:        2026.03.06
        description: 通过BDF确定设备类型,拿到bmc pldm升级用的升级包
        :param bdf_info: 设备bdf, device_info
        :param noverchk_flag: 是否拿noverchk标识的升级包
        :param exec_addr: 执行命令位置
        :param caller_class: 未找到升级文件时,报bug, 传入调用类
        return: pldm升级文件路径
        """
        sub_did = cls.get_sub_device_id_for_bdf(bdf_info=bdf_info, exec_addr=exec_addr, caller_class=caller_class)
        if not sub_did:
            return ""
        old_find_path = constants.PLDM_IMAGE_NOVERCHK if noverchk_flag else constants.PLDM_IMAGE_VERCHK
        if sub_did == constants.SUB_DEVICE_ID_OCP_X2:
            if noverchk_flag:
                find_path = constants.OCP_X2_25G_PLDM_NOVERCHK_PACKAGE_PATH
            else:
                find_path = constants.OCP_X2_25G_PLDM_PACKAGE_PATH
        elif sub_did == constants.SUB_DEVICE_ID_OCP_X4:
            if noverchk_flag:
                find_path = constants.OCP_X4_25G_PLDM_NOVERCHK_PACKAGE_PATH
            else:
                find_path = constants.OCP_X4_25G_PLDM_PACKAGE_PATH
        elif sub_did == constants.SUB_DEVICE_ID_PCIE_X2:
            if noverchk_flag:
                find_path = constants.PCIE_X2_25G_PLDM_NOVERCHK_PACKAGE_PATH
            else:
                find_path = constants.PCIE_X2_25G_PLDM_PACKAGE_PATH
        elif sub_did == constants.SUB_DEVICE_ID_PCIE_X2_10G:
            if noverchk_flag:
                find_path = constants.PCIE_X2_10G_PLDM_NOVERCHK_PACKAGE_PATH
            else:
                find_path = constants.PCIE_X2_10G_PLDM_PACKAGE_PATH
        else:
            log.error(f"没有找到[{bdf_info}]对应的bmc_pldm升级文件,没有指定寻找路径")
            if caller_class:
                cls.create_bug_problem(
                    case_cls=caller_class, key_word=f"没有找到[{bdf_info}]对应的bmc_pldm升级文件,没有指定寻找路径",
                    description_word=f"寻找默认升级文件失败",
                    expect_info=f"获取成功",
                    result_info=f"获取失败")
            return ""

        file_path = cls.get_full_path(find_path, exec_addr)
        if not file_path:
            file_path = cls.get_full_path(old_find_path, exec_addr)
            if not file_path:
                log.error(f"没有找到[{bdf_info}]对应的bmc_pldm升级文件,寻找路径:{find_path} 和{old_find_path}")
                if caller_class:
                    cls.create_bug_problem(
                        case_cls=caller_class, key_word=f"没有找到[{bdf_info}]对应的bmc_pldm升级文件",
                        description_word=f"寻找默认升级文件失败",
                        expect_info=f"获取成功",
                        result_info=f"获取失败")
                return ""
            else:
                # 此处之后需要结合实际测试需求,新增判断,目前只取第一个
                file_path = file_path.split("\n")[0]
                log.warning(f"通过旧的路径,找到bmc_pldm升级文件:{file_path}")
                return file_path

        # 此处之后需要结合实际测试需求,新增判断,目前只取第一个
        file_path = file_path.split("\n")[0]
        log.info(f"找到[{bdf_info}]对应的bmc_pldm升级文件:{file_path}")
        return file_path

    @classmethod
    def debug_auto_update_env_config(cls) -> None:
        server_ip = CommandLineArgsParse.get_server_ip()
        client_ip = CommandLineArgsParse.get_client_ip()
        root_path = os.path.dirname((os.path.dirname(os.path.abspath(__file__))))
        target_env_config_name = os.path.join(root_path, 'env_config.ini')
        target_nic_driver_config_name = os.path.join(root_path, 'nic_driver_config.ini')

        exec_command = f"scp root@{server_ip}:/root/sxetest/env_config.ini {target_env_config_name}"
        log.info(exec_command)
        rtn_code, result = subprocess.getstatusoutput(exec_command)
        log.info(f'rtn_code: {rtn_code}\nresult: {result}')
        exec_command = f"scp root@{server_ip}:/root/sxetest/env_config.ini {target_nic_driver_config_name}"
        log.info(exec_command)
        rtn_code, result = subprocess.getstatusoutput(exec_command)
        log.info(f'rtn_code: {rtn_code}\nresult: {result}')


if __name__ == '__main__':
    # pass
    # print(bin(int(a, 16))[2:])
    # b = CommonOperation.get_adapter_statics(driver_id="0", cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    # c = CommonOperation.set_device_switchdev(test_port="22")
    # rp_bdf = CommonOperation.get_rp_bdf_for_ep_bdf(bdf_info="0000:21:00.3")
    # CommonOperation.get_pcie_aer_ue_ce_status(bdf_info=rp_bdf)
    # CommonOperation.get_pcie_aer_ue_ce_status(bdf_info="0000:21:00.3")
    image_file_path = CommonOperation.get_image_upgrade_file_for_bdf(bdf_info="0000:21:00.3")
    bmc_file_path = CommonOperation.get_bmc_pldm_upgrade_file_for_bdf(bdf_info="0000:21:00.3")
    # print(f"image文件:{image_file_path}")
    # print(f"pldm文件:{bmc_file_path}")
    # CommonOperation.clean_aer_status(bus_info="0000:21:00.3")
    # CommonOperation.disable_pcie_error_reporting(bus_info=rp_bdf)
    # c = CommonOperation.get_system_core_num()
    # d = CommonOperation.interrupts_happen_num(cpus_total=16, driver_name="ens1f0")
    # print(d)
    # print(c)
    # print(b)
    # b.split(" ")
    # print(a[4:])
    # print(bin(int(a[4:], 16))[2:])
    # CommonOperation.analysis_skb_bin_file('2022-10-24;04:59:40', '2022-10-24;04:59:43')
