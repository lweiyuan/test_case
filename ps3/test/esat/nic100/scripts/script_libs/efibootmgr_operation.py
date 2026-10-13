import re
import sys

from scripts.script_libs import log
import os

import add_syspath
from scripts.script_libs import constants
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum, RxfhIndirEnum


class EfibootmgrOperation(object):

    @classmethod
    def list_boot_entries(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> dict:
        """
        author:             shaohui.wang
        date:               2023-02-15
        description:        获取启动顺序
                            回显格式:
        [root@localhost ~]# efibootmgr
        BootCurrent: 0000
        Timeout: 1 seconds
        BootOrder: 0000,0014,0006,0007,0015,0016,000A,000B,0017,0018,000E,000F,0019,001A,0012,0013,001B,001C,0002
        Boot0000* CentOS Linux
        Boot0002* Windows Boot Manager
        Boot0006* UEFI: PXE IPv4 Intel(R) I350 Gigabit Network Connection
        Boot0007* UEFI: PXE IPv4 Intel(R) I350 Gigabit Network Connection
        Boot000A* UEFI: PXE IPv6 Intel(R) I350 Gigabit Network Connection
        Boot000B* UEFI: PXE IPv6 Intel(R) I350 Gigabit Network Connection
        Boot000E* UEFI: HTTP IPv4 Intel(R) I350 Gigabit Network Connection
        Boot000F* UEFI: HTTP IPv4 Intel(R) I350 Gigabit Network Connection
        Boot0012* UEFI: HTTP IPv6 Intel(R) I350 Gigabit Network Connection
        Boot0013* UEFI: HTTP IPv6 Intel(R) I350 Gigabit Network Connection
        Boot0014* UEFI: Built-in EFI Shell
        Boot0015* UEFI: PXE IPv4 test 10 Gigabit Dual Port Network Connection
        Boot0016* UEFI: PXE IPv4 test 10 Gigabit Dual Port Network Connection
        Boot0017* UEFI: PXE IPv6 test 10 Gigabit Dual Port Network Connection
        Boot0018* UEFI: PXE IPv6 test 10 Gigabit Dual Port Network Connection
        Boot0019* UEFI: HTTP IPv4 test 10 Gigabit Dual Port Network Connection
        Boot001A* UEFI: HTTP IPv4 test 10 Gigabit Dual Port Network Connection
        Boot001B* UEFI: HTTP IPv6 test 10 Gigabit Dual Port Network Connection
        Boot001C* UEFI: HTTP IPv6 test 10 Gigabit Dual Port Network Connection
        MirrorStatus: Platform does not support address range mirror
        DesiredMirroredPercentageAbove4G: 0.00
        DesiredMirrorMemoryBelow4GB: false
        """
        result_dict = {}
        exec_command = constants.EFIBOOTMGR
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        print('dayin efibootmgr')
        print(rtn_outputs)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            lines = rtn_outputs.split('\n')
            for line in lines:
                if 'BootCurrent' in line:
                    result_dict['BootCurrent'] = line.split(':')[1].strip()
                elif 'BootOrder' in line:
                    result_dict['BootOrder'] = re.findall(r'[0-9A-F]{4}', line)
                else:
                    line = line.replace('*', '')
                    result = re.search(r'Boot([0-9A-F]{4})\s*(.*)', line)
                    if result:
                        result_dict[result.group(1)] = result.group(2)
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return result_dict

    @classmethod
    def change_boot_order(cls, boot_order: list,
                          cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2023-02-15
        description:        修改启动顺序
                            efibootmgr -o 0000,0014,0006,0007,0015,0016
        """
        rtn_status = False
        boot_order_str = constants.STR_COMMA.join(boot_order)
        exec_command = constants.STR_SPACE.join([constants.EFIBOOTMGR, '-o', boot_order_str])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def restart_tftp_service(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> int:
        """
        author: shaohui.wang
        date: 2023.03.03
        description: 重启tftp服务
        """
        command_rtn = RtnStatusEnum.FAIL.value
        exec_command = constants.STR_SPACE.join([constants.SYSTEM, constants.RESTART, "tftp.service"])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            exec_command = constants.STR_SPACE.join([constants.SYSTEM, constants.STATUS, "tftp.service"])
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value and "active (running)" in rtn_outputs:
                command_rtn = RtnStatusEnum.SUCCESS.value
        return command_rtn

    @classmethod
    def restart_dhcpd(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> int:
        """
        author: shaohui.wang
        date: 2023.03.03
        description: 重启dhcpd服务
        """
        command_rtn = RtnStatusEnum.FAIL.value
        exec_command = constants.STR_SPACE.join([constants.SYSTEM, constants.RESTART, "dhcpd"])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            exec_command = constants.STR_SPACE.join([constants.SYSTEM, constants.STATUS, "dhcpd"])
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value and "active (running)" in rtn_outputs:
                command_rtn = RtnStatusEnum.SUCCESS.value
        return command_rtn

    @classmethod
    def restart_nfs_server(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> int:
        """
        author: shaohui.wang
        date: 2023.03.03
        description: 重启nfs_server服务
        """
        command_rtn = RtnStatusEnum.FAIL.value
        exec_command = constants.STR_SPACE.join([constants.SYSTEM, constants.RESTART, "nfs-server"])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            exec_command = constants.STR_SPACE.join([constants.SYSTEM, constants.STATUS, "nfs-server"])
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value and "active (exited)" in rtn_outputs:
                command_rtn = RtnStatusEnum.SUCCESS.value
        return command_rtn


if __name__ == '__main__':
    pass
