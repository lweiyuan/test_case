import re

import add_syspath
from scripts.script_libs import constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum, BondModeEnum, MacVlanModeEnum
import time


class NetshOperation(object):

    @classmethod
    def set_device_up(cls, device_name: str,
                      cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2023-02-09
        description:        Enable-NetAdapter -Name "以太网 5" 或者
                            netsh interface set interface name="以太网 5" admin=ENABLE
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        """
        rtn_status = False
        exec_command = f'netsh interface set interface name="{device_name}" admin=ENABLE'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_device_down(cls, device_name: str,
                        cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2023-02-09
        description:        禁用网卡
                            Disable-NetAdapter -Name "以太网 5" 或者
                            netsh interface set interface name="以太网 5" admin=DISABLE
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        """
        rtn_status = False
        exec_command = f'netsh interface set interface name="{device_name}" admin=DISABLE'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def add_ip_addr(cls, device_name: str, ip_addr: str, mask: str,
                    cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        """
        author: shaohui.wang
        date：2023-02-09
        description: 对网卡设备添加IP地址，例如
        netsh interface ip set address "以太网 5" static 192.168.1.1 255.255.255.0
        目前该命令的效果是修改原先的IP地址
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join(['netsh interface ip set address',
                                                 constants.STR_QUOTE + device_name + constants.STR_QUOTE,
                                                 'static', ip_addr,
                                                 mask])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code != RtnStatusEnum.FAIL.value:
            rtn_status = True

        return rtn_status

    @classmethod
    def extra_add_ip_addr(cls, device_name: str, ip_addr: str, mask: str,
                          cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        """
        author: wei.yuan1
        date: 2023-11-02
        description: 在网卡原来的基础上，增加额外的IP信息
        netsh interface ipv4 add address index=2 address=192.168.0.10 mask=255.255.255.0
        """
        rtn_status = False
        exec_command = f"netsh interface ipv4 add address name={device_name} address={ip_addr} mask={mask}"
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code != RtnStatusEnum.FAIL.value:
            rtn_status = True

        return rtn_status

    @classmethod
    def del_ip_addr(cls, device_name: str, ip_addr: str, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value):
        """
        author: shaohui.wang
        date：2023-02-09
        description: 对网卡设备删除IP地址
        netsh interface ip delete address "以太网 5" 192.168.1.1
        """

        rtn_status = False
        exec_command = constants.STR_SPACE.join(['netsh interface ipv4 delete address',
                                                 device_name, f"address={ip_addr}"])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code:
            rtn_status = True

        return rtn_status

    @classmethod
    def modiffy_interface_multi_forwarding(cls, device_name: str, forwarding: str,
                                           cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        """
        author: wei.yuan1
        date: 2023.10.24
        description: 设置网卡的组播开关
        netsh interface ipv4 set interface "接口名称" forwarding=enabled
        """
        forward_switch = f"{constants.FORWARD}={forwarding}"
        exec_command = constants.STR_SPACE.join([constants.NETSH, constants.INTERFACE,
                                                 constants.IPV4, constants.SET, constants.INTERFACE,
                                                 device_name, forward_switch])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        return rtn_code

    @classmethod
    def modiffy_interface_ipv6_state(cls, device_name: str, state: str,
                                     cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        """
        author: wei.yuan1
        date: 2023.10.24
        description: 控制ipv6开关
        netsh interface ipv6 set interface "接口名称" state=disabled
        """
        state_switch = f"{constants.STATE}={state}"
        exec_command = constants.STR_SPACE.join([constants.NETSH, constants.INTERFACE,
                                                 constants.IPV6, constants.SET, constants.INTERFACE,
                                                 device_name, state_switch])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        return rtn_code

    @classmethod
    def show_interface_mtu_value(cls, device_name: str, virtual_ip: str = None,
                                 cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        """
        author: wei.yuan1
        date: 2023.11.17
        description: 显示网卡的真正的mtu值
        命令为：netsh interface ipv4 show interface |findstr sxe-4
        """
        interface_mtu = None
        exec_command = \
            f"{constants.NETSH} {constants.INTERFACE} {constants.IPV6} {constants.SHOW}" \
            f" {constants.INTERFACE}|findstr {device_name}"
        rtn_code, rtn_output, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address, win_vm_ip=virtual_ip)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            interface_info = re.sub(r"\s+", " ", rtn_output)
            info_list = interface_info.split(" ")
            info_list = [index for index in info_list if index != ""]
            interface_mtu = info_list[2]
        return interface_mtu


if __name__ == '__main__':
    NetshOperation.set_device_down(device_name='以太网 5', cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
