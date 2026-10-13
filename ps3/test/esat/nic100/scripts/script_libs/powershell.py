import re

import add_syspath
from scripts.script_libs import constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum, BondModeEnum, MacVlanModeEnum
import time


class PowerShell(object):

    @classmethod
    def set_device_up(cls, device_name: str,
                      cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2023-02-09
        description:        Enable-NetAdapter -Name "以太网 5"
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.ENABLE_NET_ADAPTER, constants.NAME1,
                                                 constants.STR_QUOTE + device_name + constants.STR_QUOTE])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_offload_and_features(cls, device_name: str, para_key: str, para_value: str,
                                 cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2023-02-09
        description:        Set-NetAdapterAdvancedProperty命令，例如
        Set-NetAdapterAdvancedProperty -Name "MyAdapter" -DisplayName "Flow Control"
         -DisplayValue "Rx and Tx Enabled"
        :param device_name:   网卡设备名称,如ens1f0
        :param para_key:      修改的参数名
        :param para_value:    修改的参数值
        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.SET_NET_ADAPTER_ADVANCED_PROPERTY,
                                                 constants.NAME1,
                                                 constants.STR_QUOTE + device_name + constants.STR_QUOTE,
                                                 constants.DISPLAY_NAME,
                                                 constants.STR_QUOTE + para_key + constants.STR_QUOTE,
                                                 constants.DISPLAY_VALUE,
                                                 constants.STR_QUOTE + para_value + constants.STR_QUOTE])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def get_offload_and_features(cls, device_name: str,
                                 cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> dict:
        """
        author:             shaohui.wang
        date:               2023-02-09
        description:        Get-NetAdapterAdvancedProperty命令，
                            Get-NetAdapterAdvancedProperty -Name "以太网 5" | Format-Table
        :param device_name:   网卡设备名称,如ens1f0
        """
        key = None
        result_dict = dict()

        exec_command = constants.STR_SPACE.join([constants.GET_NET_ADAPTER_ADVANCED_PROPERTY, constants.NAME1,
                                                 constants.STR_QUOTE + device_name + constants.STR_QUOTE,
                                                 constants.PIPE, 'Format-List -Property DisplayName, DisplayValue'])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            lines = rtn_outputs.split('\r\n')
            for item in lines:
                re_display_name = re.match('\s*DisplayName\s*:\s*(.*)', item)
                re_display_value = re.match('\s*DisplayValue\s*:\s*(.*)', item)
                if re_display_name:
                    key = re_display_name.group(1).strip()
                elif re_display_value:
                    result_dict[key] = re_display_value.group(1).strip()

        return result_dict


if __name__ == '__main__':
    PowerShell.set_device_up(device_name='以太网 5', cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
