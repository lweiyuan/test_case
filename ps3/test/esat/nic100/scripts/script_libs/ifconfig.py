import re
from typing import Union
from scripts.script_libs import log
import add_syspath
from scripts.script_libs import constants
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum, NicNameEnum
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse
import time


class IfConfig(object):

    @classmethod
    def get_all_device_name(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, ssh_ip: str = None) -> list:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        ifconfig中找到所有device name
        return: []
        """
        from scripts.script_libs.common_operation import CommonOperation
        result_list = []
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        # linux系统命令行处理
        if (cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and 'windows' not in host_os_client) or \
                (cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and 'windows' not in host_os_server):
            exec_command = constants.IFCONFIG + ' -a'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                pci_pattern = r'(\S+):\s+flags'
                result_list = re.findall(pci_pattern, rtn_outputs)
        # windows系统命令行处理
        else:
            exec_command = constants.IPCONFIG
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)

            if rtn_code == RtnStatusEnum.SUCCESS.value:
                pci_pattern = r'适配器\s+(.+):'
                result_list = re.findall(pci_pattern, rtn_outputs)

        return result_list

    @classmethod
    def set_device_down(cls, device_name: str,
                        cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                        ssh_ip: str = None
                        ) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        ifconfig关闭网口
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        """
        from scripts.script_libs.common_operation import CommonOperation
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        driver_name_server, driver_name_client = CommonOperation.get_nic_driver_name()
        if (host_os_server == 'windows' and cmd_execute_address == CmdExecuteAdressEnum.SERVER.value) or \
                (host_os_client == 'windows' and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value):
            return cls.set_netadapter_hard_disable(device_name, cmd_execute_address)

        else:
            # # todo vf 当前不支持ifconfig down/up操作
            # if cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and \
            #         driver_name_server in [NicNameEnum.SXE2.value, NicNameEnum.SCGBE.value] and "v" in device_name:
            #     log.warning("vf 当前不支持ifconfig down/up操作,不执行")
            #     return True
            rtn_status = False
            exec_command = constants.STR_SPACE.join([constants.IFCONFIG, device_name, constants.DOWN])
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
            log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                rtn_status = True
            else:
                log.error(f'command:{exec_command}执行失败')
            return rtn_status

    @classmethod
    def set_netadapter_disable(cls, device_name: str,
                               cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xiangyu.liu
        date:               2022-07-19
        description:        Disable-NetAdapter关闭网络适配器
        :param device_name:   网卡设备名称,如sxe-4
        :param cmd_execute_address:
        """
        rtn_status = False
        exec_command = "{} -name '{}' -ComponentID 'ms_tcpip'".format(constants.DISABLE_NET_ADAPTER_BINDING,
                                                                      device_name)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        log.info(f'command:{exec_command},rtn_code:{rtn_code} outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True

        return rtn_status

    @classmethod
    def set_device_soft_down(cls, device_name: str,
                             cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, test_port: int=None) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        ifconfig关闭网口
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        """
        from scripts.script_libs.common_operation import CommonOperation
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        exec_command = 'cat /etc/redhat-release'
        rtn_code, os_info, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address,
            ssh_port=str(test_port) if test_port is not None else None)
        log.info("rtn_code:{}, os_info:{}, rtn_err:{}".format(rtn_code, os_info, rtn_err))
        if (host_os_server == 'ubuntu' and cmd_execute_address == CmdExecuteAdressEnum.SERVER.value) or \
                (host_os_client == 'ubuntu' and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value) or \
                "ubuntu" in os_info:
            return cls.set_device_down(device_name, cmd_execute_address)
        elif (host_os_server == 'windows' and cmd_execute_address == CmdExecuteAdressEnum.SERVER.value) or \
                (host_os_client == 'windows' and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value) or \
                "ubuntu" in os_info:
            return cls.set_netadapter_disable(device_name, cmd_execute_address)
        else:
            rtn_status = False
            exec_command = constants.STR_SPACE.join([constants.IFDOWN, device_name])
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address,
                ssh_port=str(test_port) if test_port is not None else None)
            # log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
            if "command not found" in rtn_outputs + rtn_err or "unknown connection" in rtn_outputs + rtn_err:
                exec_command = "nmcli connection down {}".format(device_name)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                    exec_command, cmd_execute_address=cmd_execute_address,
                    ssh_port=str(test_port) if test_port is not None else None)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                rtn_status = True
            else:
                log.error(f'command:{exec_command}执行失败')

        return rtn_status

    @classmethod
    def set_device_up(cls, device_name: str,
                      cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                      ssh_ip: str = None) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        ifconfig打开网口
        :param device_name:   网卡设备名称,如ens1f0
        :param ssh_ip:
        :param cmd_execute_address:
        """
        from scripts.script_libs.common_operation import CommonOperation
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        driver_name_server, driver_name_client = CommonOperation.get_nic_driver_name()
        if (host_os_server == 'windows' and cmd_execute_address == CmdExecuteAdressEnum.SERVER.value) or \
                (host_os_client == 'windows' and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value):
            return cls.set_netadapter_hard_enable(device_name, cmd_execute_address)
        else:
            # # todo vf 当前不支持ifconfig down/up操作
            # if cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and \
            #         driver_name_server in [NicNameEnum.SXE2.value, NicNameEnum.SCGBE.value] and "v" in device_name:
            #     log.warning("vf 当前不支持ifconfig down/up操作,不执行")
            #     return True
            rtn_status = False
            exec_command = constants.STR_SPACE.join([constants.IFCONFIG, device_name, constants.UP])
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
            log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                rtn_status = True
            else:
                log.error(f'command:{exec_command}执行失败')
            return rtn_status

    @classmethod
    def set_netadapter_hard_enable(cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2024.02.28
        description: 设置网卡的硬启用
        """
        rtn_status = False
        exec_command = f"{constants.ENABLE_NET_ADAPTER} -name {device_name} -confirm:$false"
        log.info("执行命令：{}".format(exec_command))
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            rtn_status = False
        return rtn_status

    @classmethod
    def set_netadapter_hard_disable(cls, device_name: str,
                                    cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2024.02.28
        description: 设置网卡的硬启用
        """
        rtn_status = False

        exec_command = f"{constants.DISABLE_NET_ADAPTER} -name {device_name} -confirm:$false"
        log.info("执行命令：{}".format(exec_command))
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            rtn_status = False
        return rtn_status

    @classmethod
    def set_netadapter_enable(cls, device_name: str,
                              cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xiangyu.liu
        date:               2022-07-19
        description:        Disable-NetAdapter关闭网络适配器
        :param device_name:   网卡设备名称,如sxe-4
        :param cmd_execute_address:
        """
        rtn_status = False
        exec_command = "{} -name '{}'  -ComponentID 'ms_tcpip'".format(constants.ENABLE_NET_ADAPTER_BINDING,
                                                                       device_name)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_device_soft_up(cls, device_name: str,
                           cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, test_port: int=None) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        ifconfig打开网口
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        """
        rtn_status = False
        from scripts.script_libs.common_operation import CommonOperation
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        if (host_os_server == 'ubuntu' and cmd_execute_address == CmdExecuteAdressEnum.SERVER.value) or \
                (host_os_client == 'ubuntu' and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value):
            log.warning("ubuntu,set_device_soft_up use set_device_up!!!!")
            if cls.set_device_up(device_name, cmd_execute_address):
                exec_command = "netplan apply"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                    exec_command, cmd_execute_address=cmd_execute_address)
                log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
                if rtn_code == RtnStatusEnum.SUCCESS.value:
                    rtn_status = True
                else:
                    log.error(f'command:{exec_command}执行失败')
        elif (host_os_server == 'windows' and cmd_execute_address == CmdExecuteAdressEnum.SERVER.value) or \
             (host_os_client == 'windows' and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value):
            return cls.set_netadapter_enable(device_name, cmd_execute_address)
        else:
            exec_command = constants.STR_SPACE.join([constants.IFUP, device_name])
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address,
                ssh_port=str(test_port) if test_port is not None else None)
            # log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
            if (("command not found" in rtn_outputs + rtn_err) or ("unknown connection" in rtn_outputs + rtn_err) or
                    ("D-Bus" not in rtn_outputs + rtn_err)):
                exec_command = "nmcli connection up {}".format(device_name)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                    exec_command, cmd_execute_address=cmd_execute_address,
                    ssh_port=str(test_port) if test_port is not None else None)

            if rtn_code == RtnStatusEnum.SUCCESS.value:
                rtn_status = True
            else:
                log.error(f'command:{exec_command}执行失败')

        return rtn_status

    @classmethod
    def reset_device(cls, device_name: str,
                     cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        ifconfig关闭、打开网口
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        """
        rtn_status = False
        if cls.set_device_down(device_name, cmd_execute_address=cmd_execute_address):
            if cls.set_device_up(device_name, cmd_execute_address=cmd_execute_address):
                rtn_status = True

        return rtn_status

    @classmethod
    def analysis_ipconfig_info(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                               test_port: int = None) -> list:
        """
        author:             shaohui.wang
        date:               2022-12-05
        description:        ipconfig /all命令回显解析
        :param cmd_execute_address:   执行地址
        return:
        """
        net_card_data = list()
        temp_dict = dict(flag=True)
        is_first_nic = True
        exec_command = constants.IPCONFIG
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address, ssh_username="Administrator",
            ssh_port=str(test_port) if test_port is not None else None)
        # log.info("rtn_code:{}\nrtn_outputs:{}\nrtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        res = rtn_outputs.split('\r\n')
        for x in res:
            pattern_nic_name = re.compile(r'adapter\s*(.+):')
            pattern_ip = re.compile(constants.PATTERN_IP)
            pattern_ipv6 = re.compile(r': (.+)%')
            pattern_mac_addr = re.compile(r'(\w\w-){5}\w\w')

            if "adapter" in x or "适配器" in x:
                if not is_first_nic:
                    net_card_data.append(temp_dict)
                is_first_nic = False
                temp_dict = dict()
                temp_dict['nic_name'] = pattern_nic_name.search(x).group(1)
            elif "Media State" in x or "媒体状态" in x:
                temp_dict[constants.MEDIA_STATE] = x.split(':')[1].strip()
            elif "Description" in x or "描述" in x:
                temp_dict[constants.DESCRIPTION] = x.split(':')[1].strip()
            elif "Physical Address" in x or "物理地址" in x:
                temp_mac_addr = pattern_mac_addr.search(x).group()
                temp_dict[constants.ETHER] = temp_mac_addr.replace('-', ':').lower()
            elif "IPv6 Address" in x or "IPv6 地址" in x:
                if pattern_ipv6.search(x):
                    temp_dict[constants.INET6] = pattern_ipv6.search(x).group(1)
                else:
                    temp_dict[constants.INET6] = ""
            elif "IPv4 Address" in x or "IPv4 地址" in x:
                temp_dict[constants.INET] = pattern_ip.search(x).group()
            if x == res[-1]:
                net_card_data.append(temp_dict)
        return net_card_data

    @classmethod
    def analysis_ifconfig_info(cls, device_name: str,
                               cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                               ssh_ip: str = None, test_port: int = None, script_object: bool = False,
                               netns_name: str = None
                               ) -> dict:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        ifconfig device命令回显解析
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        return: {
                    'flags': '4163',
                    'mode': 'UP,BROADCAST,RUNNING,MULTICAST',
                    'mtu': '1500',
                    'inet': '192.168.100.253',
                    'netmask': '255.255.255.0',
                    'broadcast': '192.168.100.255',
                    'inet6': 'fe80::82d9:f8e9:2482:1979',
                    'prefixlen': '64',
                    'scopeid': '0x20<link>',
                    'ether': 'e8:61:1f:35:aa:8e',
                    'txqueuelen': '1000',
                    'dropped': '0',
                    'frame': '0',
                    'rx_packets': '2609',
                    'tx_packets': '2592',
                    'rx_errors': '0',
                    'tx_errors': '0',
                    'rx_overruns': '0',
                    'tx_overruns': '0',
                    'carrier': '0',
                    'rx_bytes': '154.1KiB',
                    'tx_bytes': '154.2KiB'
                }
        """
        from scripts.script_libs.common_operation import CommonOperation
        result_dict = {}
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        # linux系统命令行处理
        if (cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and 'windows' not in host_os_client) or \
                (cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and 'windows' not in host_os_server) or \
                (ssh_ip is not None):
            pattern = r'(\S+)\s{1}(\S+)\s{2}'
            exec_command = constants.STR_SPACE.join([constants.IFCONFIG, device_name])
            if netns_name:
                exec_command = f"ip netns exec {netns_name} {exec_command}"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip,
                ssh_port=str(test_port) if test_port is not None else None, script_object=script_object)
            # log.info("exec_command:{}\n,rtn_code:{}\nrtn_outputs:\n{}\nrtn_err:\n{}".
            #          format(exec_command, rtn_code, rtn_outputs, rtn_err))
            result = re.findall(pattern, rtn_outputs)
            for item in result[:]:
                # 以(开头的为rx和tx的流量信息,需要额外处理下
                if item[0].startswith('('):
                    result.append(('bytes', item[0][1:] + item[1][:-1]))
                    result.remove(item)

                # 以>结尾的是scopid字段，需要额外处理下
                if item[1].endswith('link>'):
                    result.append((item[0], item[1].split('<')[0]))
                    result.remove(item)

            for item in result:
                # 以device开头的是flag号、网卡模式,需要分开存放
                if item[0] == device_name + constants.STR_COLON:
                    result_dict['flags'] = re.findall(r'\d+', item[1])[0]
                    result_dict['mode'] = item[1].split(result_dict['flags'])[1][1:-1]

                # 如果插入元素时发现key值重复，是rx和tx的相同key值导致，对原有加rx前缀，新元素加tx前缀
                elif item[0] in result_dict and item[0] not in ['inet6', 'prefixlen', 'scopeid']:
                    value = result_dict[item[0]]
                    result_dict.pop(item[0])
                    result_dict['rx_' + item[0]] = value
                    result_dict['tx_' + item[0]] = item[1]

                elif item[0] not in ['inet6', 'prefixlen', 'scopeid']:
                    result_dict[item[0]] = item[1]
            # ipv6地址特殊处理
            from scripts.script_libs.ip_operation import IpOperation
            pattern_ipv6_link = r'inet6\s+(\S+)\s+prefixlen\s+(\d+)\s+scopeid\s+(\w+)<link>'
            # pattern_ipv6_global = r'inet6\s+(\S+)\s+prefixlen\s+(\d+)\s+scopeid\s+(\w+)<global>'
            result_ipv6_link = re.search(pattern_ipv6_link, rtn_outputs)
            if result_ipv6_link:
                result_dict['inet6'] = result_ipv6_link.group(1)
                result_dict['prefixlen'] = result_ipv6_link.group(2)
                result_dict['scopeid'] = result_ipv6_link.group(3)
            # else:
            #     result = IpOperation.add_ip_addr(device_name=device_name,
            #                                      ip_addr='2001::1/64',
            #                                      cmd_execute_address=cmd_execute_address)
            #     if result:
            #         result_ipv6_link = re.search(pattern_ipv6_link, rtn_outputs)
            #         if result_ipv6_link:
            #             result_dict['inet6'] = result_ipv6_link.group(1)
            #             result_dict['prefixlen'] = result_ipv6_link.group(2)
            #             result_dict['scopeid'] = result_ipv6_link.group(3)
            #     else:
            #         log.info('添加ipv6地址命令执行失败')

        # windows系统命令行处理
        else:
            all_nic_info = cls.analysis_ipconfig_info(cmd_execute_address=cmd_execute_address, test_port=test_port)
            for item in all_nic_info:
                # print("item:{}".format(item))
                if 'nic_name' in item.keys() and item['nic_name'] == device_name:
                    result_dict = item
        # 4.9.0-8-linx-security-MDA64
        if 'inet' in result_dict.keys():
            result_dict['inet'] = result_dict['inet'].replace("addr:", "")
        return result_dict

    @classmethod
    def get_device_media_state(cls, device_name: str,
                               cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> str or None:
        """
        author:             shaohui.wang
        date:               2022-12-05
        description:        从ipconfig /all信息中返回媒体状态, 仅用于windows环境
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        """
        return cls.analysis_ifconfig_info(device_name=device_name,
                                          cmd_execute_address=cmd_execute_address).get(constants.MEDIA_STATE)

    @classmethod
    def get_device_ipv4_addr(cls, device_name: str,
                             cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                             test_port: int = None, netns_name: str = None, ssh_ip: str = None) -> str or None:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        从ifconfig信息中返回ipv4地址
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        :param test_port:
        :param netns_name:
        """
        return cls.analysis_ifconfig_info(device_name=device_name,
                                          cmd_execute_address=cmd_execute_address,
                                          test_port=test_port, netns_name=netns_name,
                                          ssh_ip=ssh_ip).get(constants.INET)

    @classmethod
    def get_device_broadcast_addr(
            cls, device_name: str,
            cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, test_port: int = None) -> str or None:
        """
        author: wei.yuan1
        date: 2024-07-16
        description: 从ifconfig中返回广播地址
        :param device_name:
        :param cmd_execute_address:
        :param test_port:
        :return:
        """
        return cls.analysis_ifconfig_info(device_name=device_name,
                                          cmd_execute_address=cmd_execute_address,
                                          test_port=test_port).get(constants.BROADCAST)

    @classmethod
    def get_device_ipv6_addr(cls, device_name: str,
                             cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, netns_name: str = None,
                             ssh_ip: str = None
                             ) -> str or None:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        从ifconfig信息中返回ipv6地址
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        """
        return cls.analysis_ifconfig_info(device_name=device_name,
                                          cmd_execute_address=cmd_execute_address,
                                          netns_name=netns_name, ssh_ip=ssh_ip).get(constants.INET6)

    @classmethod
    def get_device_mac_addr(cls, device_name: str,
                            cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                            ssh_ip: str = None,
                            netns_name: str = None
                            ) -> str or None:
        """
        author:              weiyuan
        date:                2022-07-27
        description:         获取网卡port的mac地址
        :param device_name: 网卡名称
        :param ssh_ip: 输入端的可访问的IP地址
        :param cmd_execute_address:
        :param netns_name: 网络命名空间
        """
        return cls.analysis_ifconfig_info(device_name=device_name,
                                          ssh_ip=ssh_ip,
                                          cmd_execute_address=cmd_execute_address,
                                          netns_name=netns_name
                                          ).get(constants.ETHER)

    @classmethod
    def get_all_nic_name(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, ssh_ip: str = None):
        """

        """
        get_nic_command = "ifconfig -a | grep -o '^[^ ]*'"
        nic_name_list = []
        # get_nic_name = CommandOperation.concat_invoke_command(vm_name=vm_name, cmd=get_nic_command)
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            ssh_ip=ssh_ip,
            cmd=get_nic_command, cmd_execute_address=cmd_execute_address, script_object=True)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_stdout = rtn_stdout.replace("\r", "")
            for index in rtn_stdout.split("\n"):
                index = re.sub(":", "", index)
                if "lo" not in index or "usb" not in index:
                    nic_name_list.append(index)
            nic_name_list = [re.sub(r"\s+", "", index) for index in nic_name_list]
            nic_name_list = [index for index in nic_name_list if "eth" not in index and "vir" not in index]
        return nic_name_list

    @classmethod
    def get_device_mtu(cls, device_name: str,
                       cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, ssh_ip: str = None,
                       script_object: bool = False, netns_name: str = None) -> str or None:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        从ifconfig信息中返回MTU
        :param device_name:   网卡设备名称,如ens1f0
        :param ssh_ip:
        :param cmd_execute_address:
        """
        return cls.analysis_ifconfig_info(device_name=device_name,
                                          cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip,
                                          script_object=script_object, netns_name=netns_name).get(constants.MTU)

    @classmethod
    def get_tx_bytes(cls, device_name: str,
                     cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> str:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        从ifconfig信息中返回tx_bytes
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        """
        from scripts.script_libs.common_operation import CommonOperation
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        # linux系统
        if (cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and 'windows' not in host_os_client) or \
                (cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and 'windows' not in host_os_server):
            return cls.analysis_ifconfig_info(device_name=device_name,
                                              cmd_execute_address=cmd_execute_address)[constants.TX_BYTES]
        # windows系统
        else:
            exec_command = constants.GET_NET_ADAPTER_STATISTICS + " -name '{}'|fl *".format(device_name)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            CommonOperation.check_cmd_execute_success(cls, rtn_code, rtn_outputs, exec_command)
            return re.search(r'SentBytes\s*:\s*(\d+)', rtn_outputs).group(1)

    @classmethod
    def get_rx_bytes(cls, device_name: str,
                     cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> str:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        从ifconfig信息中返回rx_bytes
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        """
        from scripts.script_libs.common_operation import CommonOperation
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        # linux系统
        if (cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and 'windows' not in host_os_client) or \
                (cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and 'windows' not in host_os_server):
            return cls.analysis_ifconfig_info(device_name=device_name,
                                              cmd_execute_address=cmd_execute_address)[constants.RX_BYTES]
        # windows系统
        else:
            exec_command = constants.GET_NET_ADAPTER_STATISTICS + " -name '{}'|fl *".format(device_name)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            CommonOperation.check_cmd_execute_success(cls, rtn_code, rtn_outputs, exec_command)
            return re.search(r'ReceivedBytes\s*:\s*(\d+)', rtn_outputs).group(1)

    @classmethod
    def get_rx_errors(cls, device_name: str,
                      cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, win_vm_ip: str = None) -> str:
        """
        author:             shaohui.wang
        date:               2022-10-12
        description:        从ifconfig信息中返回rx_errors
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        """
        from scripts.script_libs.common_operation import CommonOperation
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        # linux系统
        if (cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and 'windows' not in host_os_client) or \
                (cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and 'windows' not in host_os_server):
            return cls.analysis_ifconfig_info(device_name=device_name,
                                              cmd_execute_address=cmd_execute_address)[constants.RX_ERRORS]
        # windows系统
        else:
            exec_command = constants.GET_NET_ADAPTER_STATISTICS + " -name '{}'|fl *".format(device_name)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)
            CommonOperation.check_cmd_execute_success(cls, rtn_code, rtn_outputs, exec_command)
            return re.search(r'ReceivedPacketErrors\s*:\s*(\d+)', rtn_outputs).group(1)

    @classmethod
    def get_rx_packet(cls, device_name: str,
                      cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, ssh_ip: str = None,
                      netns_name: str = None) -> str:
        """
        author:             shaohui.wang
        date:               2022-10-12
        description:        从ifconfig信息中返回rx_packet
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        :param netns_name: namespace
        """
        from scripts.script_libs.common_operation import CommonOperation
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        # linux系统
        if (cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and 'windows' not in host_os_client) or \
                (cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and 'windows' not in host_os_server):
            if netns_name:
                return cls.analysis_ifconfig_info(
                    device_name=device_name,
                    cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip, netns_name=netns_name)[constants.RX_PACKETS]
            else:
                return cls.analysis_ifconfig_info(
                    device_name=device_name,
                    cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)[constants.RX_PACKETS]
        # windows系统
        else:
            exec_command = constants.NETSTAT + constants.STR_SPACE + constants.ETHER_STATISTICS
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            CommonOperation.check_cmd_execute_success(cls, rtn_code, rtn_outputs, exec_command)
            return (re.search(r'[单播数据包Unicast packets]\s*(\d+)\s+(\d+)', rtn_outputs).group(1) +
                    re.search(r'[非单播数据包Non-unicast packets]\s*(\d+)\s+(\d+)', rtn_outputs).group(1))

    @classmethod
    def get_tx_packet(cls, device_name: str,
                      cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, netns_name: str = None) -> str:
        """
        author:             shaohui.wang
        date:               2022-10-12
        description:        从ifconfig信息中返回tx_packet
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        :param netns_name:namespace
        """
        from scripts.script_libs.common_operation import CommonOperation
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        # linux系统
        if (cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and 'windows' not in host_os_client) or \
                (cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and 'windows' not in host_os_server):
            if netns_name:
                return cls.analysis_ifconfig_info(device_name=device_name,
                                                  cmd_execute_address=cmd_execute_address,
                                                  netns_name=netns_name)[constants.TX_PACKETS]
            else:
                return cls.analysis_ifconfig_info(device_name=device_name,
                                                  cmd_execute_address=cmd_execute_address)[constants.TX_PACKETS]
        # windows系统
        else:
            exec_command = constants.NETSTAT + constants.STR_SPACE + constants.ETHER_STATISTICS
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            CommonOperation.check_cmd_execute_success(cls, rtn_code, rtn_outputs, exec_command)
            return (re.search(r'[单播数据包Unicast packets]\s*(\d+)\s+(\d+)', rtn_outputs).group(2) +
                    re.search(r'[非单播数据包Non-unicast packets]\s*(\d+)\s+(\d+)', rtn_outputs).group(2))

    @classmethod
    def get_frame(cls, device_name: str,
                  cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, win_vm_ip: str = None) -> str:
        """
        author:             shaohui.wang
        date:               2022-10-12
        description:        从ifconfig信息中返回frame
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        """
        from scripts.script_libs.common_operation import CommonOperation
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        # linux系统
        if (cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and 'windows' not in host_os_client) or \
                (cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and 'windows' not in host_os_server):
            return cls.analysis_ifconfig_info(device_name=device_name,
                                              cmd_execute_address=cmd_execute_address)[constants.FRAME]
        # windows系统 该字段暂时不知什么意义，用什么命令查看
        else:
            return '0'

    @classmethod
    def get_device_mode(cls, device_name: str,
                        cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                        namespace: str = None, ssh_ip: str = None) -> str:
        return cls.analysis_ifconfig_info(device_name=device_name,
                                          cmd_execute_address=cmd_execute_address,
                                          netns_name=namespace, ssh_ip=ssh_ip)[constants.MODE]

    @classmethod
    def set_device_mode(cls, device_name: str, mode: str,
                        cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                        ssh_ip: str = None, namespace: str = None
                        ) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        ifconfig打开网卡设备的multicast, allmuti, promisc模式
        :param device_name: 网卡设备名称,如ens1f0
        :param mode:        网卡模式，如multicast, allmuti, promisc
                            取值constants.multicast等
        :param namespace: 网络命名空间
        :param cmd_execute_address:
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IFCONFIG, device_name, mode])
        if namespace:
            exec_command = f"ip netns exec {namespace} {exec_command}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            if mode in cls.get_device_mode(device_name=device_name, cmd_execute_address=cmd_execute_address,
                                           namespace=namespace).lower():
                rtn_status = True
            elif constants.STR_MINUS in mode:
                rtn_status = True
            else:
                log.info(f'command:{exec_command}执行成功，但网卡模式未包含{mode}')
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def cancel_device_mode(cls, device_name: str, mode: str,
                           cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, ssh_ip: str = None,
                           namespace: str = None
                           ) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        ifconfig关闭网卡设备的多播模式
        :param device_name: 网卡设备名称,如ens1f0
        :param mode:        网卡模式，如multicast, allmuti, promisc
                            取值constants.multicast等
        :param cmd_execute_address:
        """

        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IFCONFIG, device_name,
                                                 constants.STR_MINUS + mode])
        if namespace:
            exec_command = f"ip netns exec {namespace} {exec_command}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            print(mode)
            # print(cls.get_device_mode(device_name=device_name, cmd_execute_address=cmd_execute_address).lower())
            if mode not in cls.get_device_mode(device_name=device_name,
                                               cmd_execute_address=cmd_execute_address, namespace=namespace).lower():
                rtn_status = True
            else:
                log.info(f'command:{exec_command}执行成功，但网卡模式包含{mode}')
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_device_mac_addr(cls, device_name: str, mac_addr: str,
                            cmd_exec_address: str = CmdExecuteAdressEnum.CLIENT.value,
                            ssh_ip: str = None, name_space: str = None) -> int:
        """
        author: wei.yuan1
        date: 2022.10.27
        description: 设置网卡的单播mac地址
        """
        exec_command = constants.STR_SPACE.join([constants.IFCONFIG, device_name,
                                                 constants.HW_ETHER, mac_addr])
        if name_space:
            exec_command = f"ip netns exec {name_space} {exec_command}"
        rtn_code, *_, = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_exec_address, ssh_ip=ssh_ip)
        return rtn_code

    @classmethod
    def set_virtual_device_addr(cls, device_name: str, ipv4_addr: str,
                                cmd_exec_address: str = CmdExecuteAdressEnum.CLIENT.value,
                                ssh_ip: str = None):
        exec_command = constants.STR_SPACE.join([constants.IFCONFIG, device_name,
                                                 ipv4_addr])
        rtn_code, *_, = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_exec_address, ssh_ip=ssh_ip)
        return rtn_code

    @classmethod
    def set_device_mtu(cls,
                       device_name: str,
                       mtu_value: Union[str, int],
                       cmd_exec_address: str = CmdExecuteAdressEnum.CLIENT.value,
                       ssh_ip: str = None,
                       win_vm_ip: str = "",
                       netns_name: str = None,
                       ):
        """
        author: wei.yuan1
        date: 2022.10.27
        description: 设置网卡的mtu值
        """
        if not device_name:
            log.info("未指定device_name, skip set_device_mtu")
            return 1
        exec_command = constants.STR_SPACE.join([constants.IFCONFIG, device_name,
                                                 constants.MTU, str(mtu_value)])
        if netns_name:
            exec_command = f"ip netns exec {netns_name} {exec_command}"
        rtn_code, rtn_outputs, rtn_stderr = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_exec_address, ssh_ip=ssh_ip, win_vm_ip=win_vm_ip)
        log.info('Command: {}, result: {}, error: {}'.format(exec_command, rtn_outputs, rtn_stderr))
        time.sleep(2)
        cmd = "ip a"
        CommandOperation.execute_command_with_error(
            cmd, cmd_execute_address=cmd_exec_address, ssh_ip=ssh_ip, win_vm_ip=win_vm_ip)

        return rtn_code

    @classmethod
    def set_device_cancel_mode(cls, device_name: str, mode: str,
                               cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        ifconfig打开网卡设备的multicast, allmuti, promisc模式
        :param device_name: 网卡设备名称,如ens1f0
        :param mode:        网卡模式，如multicast, allmuti, promisc
                            取值constants.multicast等
        :param cmd_execute_address:
        """

        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IFCONFIG, device_name, mode])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        return rtn_status

    @classmethod
    def show_interface_name(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        """
        author: wei.yuan1
        date: 2022.11.10
        description: 获取网卡的名称
        """
        rtn_status = False
        exec_command = f"{constants.IFCONFIG} -s |awk '{{print$1}}'"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
            rtn_outputs = rtn_outputs.split("\n")[1: -2]
        return rtn_status, rtn_outputs

    @classmethod
    def nmcli_create_nic_name(cls, device_name: str, ip_address: str,
                              cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value):
        """
        author: wei.yuan1
        date: 2022.11.22
        description: 在/etc目录下创建网卡信息，并重启NetworkManager服务
        """
        exec_command = f"nmcli con add ifname {device_name} type ethernet " \
            f"con-name {device_name} ipv4.address {ip_address} ipv4.method manual"
        rtn_code, _, rtn_err = CommandOperation.execute_command_with_error(cmd=exec_command,
                                                                           cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info('NetworkManager添加{}配置文件成功'.format(device_name))
            return True
        else:
            log.info('NetworkManager添加{}配置文件失败'.format(device_name))
            return False

    @classmethod
    def nmcli_delete_nic_name(cls, device_name: str, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value):
        """
        author: yuren
        date: 2023.11.30
        description:
        """
        exec_command = 'nmcli con delete {}'.format(device_name)
        rtn_code, _, _ = CommandOperation.execute_command_with_error(cmd=exec_command,
                                                                     cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info('NetworkManager删除{}配置文件成功'.format(device_name))
            return True
        else:
            log.info('NetworkManager删除{}配置文件失败'.format(device_name))
            return False

    @classmethod
    def change_ipv4_addr(cls, device_name: str, ipv4_addr: str, mask_len: str = '24',
                         cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author: shaohui.wang
        date: 2023.02.20
        description: 修改网卡ipv4地址
        """
        # 20250611 add by hejf 陈彦利建议修改 5.14内核版本以上通过ifconfig配置ip可能不生效，需添加nmcli connection down dev
        exec_command = 'nmcli connection down {}'.format(device_name)
        rtn_code, _, _ = CommandOperation.execute_command_with_error(cmd=exec_command,
                                                                     cmd_execute_address=cmd_execute_address)

        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IFCONFIG, device_name,
                                                 ipv4_addr + constants.STR_LEFT_SLASH + mask_len])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_device_mac(cls, device_name: str, mac_addr: str,
                         cmd_execute_address = CmdExecuteAdressEnum.SERVER.value) -> bool:
        """
        author: jianghe
        date: 2025.05.29
        description: 修改网卡mac地址
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IFCONFIG, device_name, 'hw ether', mac_addr])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def get_device_mac(cls, device_name: str, cmd_execute_address = CmdExecuteAdressEnum.SERVER.value,
                       name_space: str = None) -> str:
        """
        author: jianghe
        date: 2025.05.29
        description: 查询网卡mac地址
        """
        if name_space:
            exec_command = f'ip netns exec {name_space} {constants.IFCONFIG} {device_name}'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)

            found = re.findall('ether\s([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})',
                               rtn_outputs)
            if len(found) == 0:
                return ''
            else:
                return found[0]
        else:
            exec_command = f'{constants.IFCONFIG} {device_name}'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)

            found = re.findall('ether\s([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})',
                               rtn_outputs)
            if len(found) == 0:
                return ''
            else:
                return found[0]


if __name__ == '__main__':
    a = IfConfig.set_device_up(device_name='ens4f0', cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    print(a)
    # a = IfConfig.set_device_soft_up(device_name='enp6s0f1', cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
    # print(a)
    # pass
    # rtn_stdout = IfConfig.analysis_ifconfig_info('enp6s0f1', cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
    # print(rtn_stdout)
    # for key, value in rtn_stdout.items():
    #     print(key, ":", value)
    # print(rtn_stdout["mode"].strip().split(","))
