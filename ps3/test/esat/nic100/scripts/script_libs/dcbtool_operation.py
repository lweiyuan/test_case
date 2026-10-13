
import re

import add_syspath
from scripts.script_libs import constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum


class DcbtoolOperation(object):

    @classmethod
    def check_dcb_version(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-21
        description:        校验dcbtool版本
        """
        rtn_status = False
        exec_command = constants.DCBTOOL + constants.STR_SPACE + '-v'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            result_list = rtn_outputs.split('\n')
            if result_list[0].split('dcbtool v')[1] >= constants.DCBTOOL_VERSION:
                rtn_status = True

        else:
            log.error_caller(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def get_dcbx_version(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> str:
        """
        author:             xianda.liu
        date:               2022-07-21
        description:        dcbtool gc dcbx dcb命令获取dcbx版本
        :param cmd_execute_address: 网卡设备名称,如ens1f0
        return:             返回值可能为force-cin/force-cee/cee/cin
        """

        dcbx_version = None
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.GET_CONFIG, constants.DCBX])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{exec_command}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        exec_command_with_condition = exec_command + ' | grep \'DCBX Version:\' | awk \'{print $3$4}\''
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command_with_condition, cmd_execute_address=cmd_execute_address)

        log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # 对获取的值改为小写
            log.info(f'command:{exec_command_with_condition}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
            dcbx_version = rtn_outputs.strip().lower()
            if dcbx_version.startswith('forced'):
                dcbx_version = dcbx_version[0:5] + constants.STR_MINUS + dcbx_version[6:]
        else:
            log.info(f'command:{exec_command_with_condition}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return dcbx_version

    @classmethod
    def set_dcbx_version(cls, version: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-25
        description:        dcbtool sc dcbx设置dcbx
        :param version:     dcbx version, 取值cee cin force-cin force-cee
        :param cmd_execute_address:
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, constants.DCBX,
                                                 'v:{}'.format(version)])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def check_if_use_dcbtool(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        rtn_code, rtn_outputs, _ = CommandOperation.execute_command_with_error(cmd="dcb -V",
                                                                               cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info("当前操作系统中已安装dcb工具, 工具信息为: {}".format(rtn_outputs))
            return False
        else:
            log.info("当前系统中没有安装dcb工具, 默认使用dcbtool")
            return True

    @classmethod
    def get_dcb_state(cls, device_name: str,
                      cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool or None:
        """
        author:             xianda.liu
        date:               2022-07-21
        description:        dcbtool gc ens1f0 dcb命令获取dcb使能状态
        :param device_name: 网卡设备名称,如ens1f0
        :param cmd_execute_address:   来自于哪个方向进行修改
        """

        dcb_state_flag = None
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.GET_CONFIG,
                                                 device_name, constants.DCB])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info(f'outputs:{rtn_outputs}, error:{rtn_err}')
        exec_command += ' | grep \'DCB State:\' | awk \'{print $3}\''
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:

            if rtn_outputs.strip() == constants.ON:
                dcb_state_flag = True
            else:
                dcb_state_flag = False
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return dcb_state_flag

    @classmethod
    def set_dcb_state(cls, device_name: str, state: str,
                      cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-21
        description:        dcbtool gc ens1f0 dcb命令使能、失能dcb
        :param device_name: 网卡设备名称,如ens1f0
        :param state:       dcb状态 on/off
        :param cmd_execute_address:
        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG,
                                                 device_name, constants.DCB, state])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def get_pg_state(cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> dict:
        """
        author:             shaohui.wang
        date:               2022-09-02
        description:        dcbtool gc ens1f0 pg获取pg使能状态
        :param device_name: 网卡设备名称,如ens1f0
        :param cmd_execute_address:
        return: {
                    'Command': 'Get Config',
                    'Feature': 'Priority Groups',
                    'Port': 'ens1f1',
                    'Status': 'Successful',
                    'Enable': 'true',
                    'Advertise': 'true',
                    'Willing': 'true',
                    'up2tc': ['0', '1', '2', '3', '4', '5', '6', '7'],
                    'pgpct': ['13', '13', '13', '13', '12', '12', '12', '12'],
                    'pgid': ['0', '1', '2', '3', '4', '5', '6', '7'],
                    'uppct': ['100', '100', '100', '100', '100', '100', '100', '100'],
                    'pg strict': ['0', '0', '0', '0', '0', '0', '0', '0'],
                    "num TC's": '8'
                }
        """
        result_dict = dict()
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.GET_CONFIG, device_name,
                                                 constants.PG])

        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            result_list = rtn_outputs.split('\n')

            for item in result_list:
                if item.strip():
                    key, value = item.split(':')
                    result_dict[key.strip()] = value.strip()
            for key in result_dict:
                if key in ['up2tc', 'pgid', 'pg strict']:
                    result_dict[key] = result_dict[key].split()
                if key in ['pgpct', 'uppct']:
                    result_dict[key] = result_dict[key].replace('%', '').split()
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return result_dict

    @classmethod
    def set_pg_state(cls, device_name: str, state: bool,
                     cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2022-09.02
        description:        dcbtool sc ens1f0 pg e:<0|1>设置pg使能状态
        :param device_name: 网卡设备名称,如ens1f0
        :param state:       pg使能状态,可取'1'或者'0'
        :param cmd_execute_address:
        """
        rtn_status = False
        state = '1' if state else '0'
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.PG, constants.ENABLE + constants.STR_COLON + state])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_pg_advertise(cls, device_name: str, state: bool,
                         cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2022-09.02
        description:        dcbtool sc ens1f0 pg e:<0|1>设置pg advertise状态
        :param device_name: 网卡设备名称,如ens1f0
        :param state:       pg advertise状态,可取'1'或者'0'
        :param cmd_execute_address:
        """
        rtn_status = False
        state = '1' if state else '0'
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.PG, constants.ADVERTISE + constants.STR_COLON + state])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_pg_willing(cls, device_name: str, state: bool,
                       cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2022-09.02
        description:        dcbtool sc ens1f0 pg e:<0|1>设置pg willing状态
        :param device_name: 网卡设备名称,如ens1f0
        :param state:       pg willing状态,可取'1'或者'0'
        :param cmd_execute_address:
        """
        rtn_status = False
        state = '1' if state else '0'
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.PG, constants.WILLING + constants.STR_COLON + state])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_pg_up2tc(cls, device_name: str, up2tc_list: list,
                     cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2022-10.13
        description:        dcbtool sc ens1f0 pg up2tc:     命令设置优先级到traffic class的映射
        :param device_name: 网卡设备名称,如ens1f0
        :param up2tc_list:  优先级到traffic class的映射，如['0','1','2','3','4','5','6','7']
        :param cmd_execute_address:
        """
        rtn_status = False
        up2tc_list = [str(i) for i in up2tc_list]
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.PG,
                                                 constants.PGID + constants.STR_COLON + ''.join(up2tc_list)])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_pg_strict(cls, device_name: str, strict_list: list,
                      cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2022-10.13
        description:        dcbtool sc ens1f0 pg strict:
        :param device_name: 网卡设备名称,如ens1f0
        :param strict_list:  Strict priority setting.  From left to right (priorities 0-7), x is 0 or 1.
                            1 indicates that the priority may utilize all of the bandwidth allocated to its priority
                            group.    如['0','1','2','3','4','5','6','7']
        :param cmd_execute_address:
        """
        rtn_status = False
        strict_list = [str(i) for i in strict_list]
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.PG,
                                                 constants.PGID + constants.STR_COLON + ''.join(strict_list)])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_pg_pgid(cls, device_name: str, pgid_list: list,
                    cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2022-10.13
        description:        dcbtool sc ens1f0 pg pgid:     命令设置TC分组
        :param device_name: 网卡设备名称,如ens1f0
        :param pgid_list:   TC分组的列表，如['0','0','0','0','1','1','2','2']
        :param cmd_execute_address:
        """
        rtn_status = False
        pgid_list = [str(i) for i in pgid_list]
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.PG,
                                                 constants.PGID + constants.STR_COLON + ''.join(pgid_list)])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_pg_pgpct(cls, device_name: str, pgpct_list: list,
                     cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2022-10-13
        description:        dcbtool sc ens1f0 pg pgpct: 命令设置TC分组占link的带宽比例
        :param device_name: 网卡设备名称,如ens1f0
        :param pgpct_list:  带宽比例列表，如['30','30','40','0','0','0','0','0']
        :param cmd_execute_address:
        """
        rtn_status = False
        pgpct_list = [str(i) for i in pgpct_list]
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.PG,
                                                 constants.PGPCT + constants.STR_COLON + ','.join(pgpct_list)])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_pg_uppct(cls, device_name: str, uppct_list: list,
                     cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2022-10-13
        description:        dcbtool sc ens1f0 pg pgpct: 命令设置TC分组占link的带宽比例
        :param device_name: 网卡设备名称,如ens1f0
        :param uppct_list:  带宽比例列表，如['30','30','40','0','0','0','0','0']
        :param cmd_execute_address:
        """
        rtn_status = False
        uppct_list = [str(i) for i in uppct_list]
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.PG,
                                                 constants.PGPCT + constants.STR_COLON + ','.join(uppct_list)])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_priority_groups_pgpct(cls, device_name: str, pgid_list: list, pgpct_list: list,
                                  cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-21
        description:        dcbtool sc ens1f0 pg pgid: pgpct: 命令设置TC分组及分组占link的带宽比例
        :param device_name: 网卡设备名称,如ens1f0
        :param pgid_list:   TC分组的列表，如['0','0','0','0','1','1','2','2']
        :param pgpct_list:  带宽比例列表，如['30','30','40','0','0','0','0','0']
        :param cmd_execute_address:
        """
        rtn_status = False
        pgid_list = [str(i) for i in pgid_list]
        pgpct_list = [str(i) for i in pgpct_list]
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.PG,
                                                 constants.PGID + constants.STR_COLON + ''.join(pgid_list),
                                                 constants.PGPCT + constants.STR_COLON + ','.join(pgpct_list)])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_priority_groups_uppct(cls, device_name: str, pgid_list: list, uppct_list: list,
                                  cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-25
        description:        dcbtool sc ens1f0 pg pgid: pgpct: 命令设置TC分组及分组占link的带宽比例
        :param device_name: 网卡设备名称,如ens1f0
        :param pgid_list:   TC分组的列表，如['0','0','0','0','1','1','2','2']
        :param uppct_list:  带宽比例列表，如['30','30','40','0','0','0','0','0']
        :param cmd_execute_address:
        """
        rtn_status = False
        pgid_list = [str(i) for i in pgid_list]
        uppct_list = [str(i) for i in uppct_list]
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.PG,
                                                 constants.PGID + constants.STR_COLON + ''.join(pgid_list),
                                                 constants.PGPCT + constants.STR_COLON + ','.join(uppct_list)])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def get_pfc_state(cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> dict:
        """
        author:             xianda.liu
        date:               2022-07-25
        description:        dcbtool gc ens1f0 pfc获取pfc使能状态
        :param device_name: 网卡设备名称,如ens1f0
        :param cmd_execute_address:
        return: {
                    'Command': 'Get Config',
                    'Feature': 'Priority Flow Control',
                    'Port': 'ens1f0',
                    'Status': 'Successful',
                    'Enable': 'true',
                    'Advertise': 'true',
                    'Willing': 'true',
                    'pfcup': ['0', 0       0       0       0       0       0       0']
                    "num TC's": '8'
                }
        """
        result_dict = dict()
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.GET_CONFIG, device_name,
                                                 constants.PFC])

        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            result_list = rtn_outputs.split('\n')

            for item in result_list:
                if item.strip():
                    key, value = item.split(':')
                    result_dict[key.strip()] = value.strip()
            result_dict['pfcup'] = result_dict['pfcup'].split()
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return result_dict

    @classmethod
    def set_pfc_state(cls, device_name: str, state: bool,
                      cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-25
        description:        dcbtool sc ens1f0 pfc on/off设置pfc使能状态
        :param device_name: 网卡设备名称,如ens1f0
        :param state:       pfc使能状态,取值为 1或0
        :param cmd_execute_address:
        """
        rtn_status = False
        state = '1' if state else '0'
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.PFC, constants.ENABLE + constants.STR_COLON + state])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_pfc_advertise(cls, device_name: str, state: bool,
                          cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-25
        description:        dcbtool sc ens1f0 pfc e: 设置pfc advertise状态
        :param device_name: 网卡设备名称,如ens1f0
        :param state:       pfc advertise状态,取值为 1或0
        :param cmd_execute_address:
        """
        rtn_status = False
        state = '1' if state else '0'
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.PFC, constants.ADVERTISE + constants.STR_COLON + state])

        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_pfc_willing(cls, device_name: str, state: bool,
                        cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-25
        description:        dcbtool sc ens1f0 pfc e: 设置pfc willing状态
        :param device_name: 网卡设备名称,如ens1f0
        :param state:       pfc willing状态,取值为 1或0
        :param cmd_execute_address:
        """
        rtn_status = False
        state = '1' if state else '0'
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.PFC, constants.WILLING + constants.STR_COLON + state])

        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_pfcup(cls, device_name: str, pfcup_list: list,
                  cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2022-09-02
        description:        dcbtool sc eth2 pfc pfcup:00010000: 使能/失能pfc
        :param device_name: 网卡设备名称,如ens1f0
        :param pfcup_list:  使能/使能pfc，如['0','0','0','0','1','1','0','0']，从左到右（优先级0-7），1表示对应优先级使能pfc
        :param cmd_execute_address:
        """
        rtn_status = False

        pfcup_list = [str(i) for i in pfcup_list]
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.PFC,
                                                 constants.PFCUP + constants.STR_COLON + ''.join(pfcup_list)])

        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def get_tc_num(cls, device_name: str,
                   cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> int or None:
        """
        author:             xianda.liu
        date:               2022-07-25
        description:        dcbtool gc ens1f0 pfc获取tc个数
        :param device_name: 网卡设备名称,如ens1f0
        :param cmd_execute_address:
        """
        tc_num = None
        result_dict = cls.get_pfc_state(device_name=device_name, cmd_execute_address=cmd_execute_address)

        if result_dict.get('num TC\'s'):
            tc_num = int(result_dict['num TC\'s'])

        return tc_num

    @classmethod
    def get_app_state(cls, device_name: str, app_type: str,
                      cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> dict:
        """
        author:             shaohui.wang
        date:               2022-10-16
        description:        dcbtool gc ens1f0 app:   获取pg使能状态
                            [root@test254 ~]# dcbtool gc ens1f1 app:fcoe
                            Command:        Get Config
                            Feature:        Application FCoE
                            Port:           ens1f1
                            Status:         Successful
                            Enable:         true
                            Advertise:      true
                            Willing:        true
                            appcfg:         08

        :param device_name: 网卡设备名称,如ens1f0
        :param app_type:  取值如下:
                           0|fcoe Fiber Channel over Ethernet (FCoE)
                           1|iscsi
                                  Internet Small Computer System Interface (iSCSI)
                           2|fip  FCoE Initialization Protocol (FIP)
        :param cmd_execute_address:

        return: {

                }
        """
        result_dict = dict()
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.GET_CONFIG, device_name,
                                                 constants.APP + constants.STR_COLON + app_type])

        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            result_list = rtn_outputs.split('\n')

            for item in result_list:
                if item.strip():
                    key, value = item.split(':')
                    result_dict[key.strip()] = value.strip()
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return result_dict

    @classmethod
    def set_app_state(cls, device_name: str, app_type: str, state: bool,
                      cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2022-11-10
        description:        dcbtool sc ens1f0 app:0 e:1设置app:0使能状态
        :param device_name: 网卡设备名称,如ens1f0
        :param app_type:    取值为'0', '1', '2' 或者 ‘fcoe', 'iscsi', 'fip'
        :param state:       使能状态
        :param cmd_execute_address:
        """
        rtn_status = False
        state = '1' if state else '0'
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.APP + constants.STR_COLON + app_type,
                                                 constants.ENABLE + constants.STR_COLON + state])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_app_advertise(cls, device_name: str, app_type: str, state: bool,
                          cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2022-11-10
        description:        dcbtool sc ens1f0 app:0 e:1设置app:0 advertise状态
        :param device_name: 网卡设备名称,如ens1f0
        :param app_type:    取值为'0', '1', '2' 或者 ‘fcoe', 'iscsi', 'fip'
        :param state:       使能状态
        :param cmd_execute_address:
        """
        rtn_status = False
        state = '1' if state else '0'
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.APP + constants.STR_COLON + app_type,
                                                 constants.ADVERTISE + constants.STR_COLON + state])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_app_willing(cls, device_name: str, app_type: str, state: bool,
                        cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2022-11-10
        description:        dcbtool sc ens1f0 app:0 e:1设置app:0 willing状态
        :param device_name: 网卡设备名称,如ens1f0
        :param app_type:    取值为'0', '1', '2' 或者 ‘fcoe', 'iscsi', 'fip'
        :param state:       使能状态
        :param cmd_execute_address:
        """
        rtn_status = False
        state = '1' if state else '0'
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.APP + constants.STR_COLON + app_type,
                                                 constants.WILLING + constants.STR_COLON + state])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_app_priority(cls, device_name: str, app_type: str, app_priority: str,
                         cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2022-10-16
        description:        例如：dcbtool sc eth2 app:0 appcfg:08
        :param device_name: 网卡设备名称,如ens1f0
        :param app_type:   取值如下:
                           0|fcoe Fiber Channel over Ethernet (FCoE)
                           1|iscsi
                                  Internet Small Computer System Interface (iSCSI)
                           2|fip  FCoE Initialization Protocol (FIP)
        :param app_priority: xx,十六进制.如08表示优先级为3.
        :param cmd_execute_address:
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.DCBTOOL, constants.SET_CONFIG, device_name,
                                                 constants.APP + constants.STR_COLON + app_type,
                                                 constants.APPCFG + constants.STR_COLON + app_priority])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def launch_lldp_sevice(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> int:
        """
        author: wei.yuan1
        date: 2022.09.27
        description: 启动lldp服务
        """
        command_rtn = RtnStatusEnum.FAIL.value
        exec_command = constants.STR_SPACE.join([constants.SYSTEM, constants.START, "lldpad.service"])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value and "active (running) " in rtn_outputs:
            command_rtn = RtnStatusEnum.SUCCESS.value
        return command_rtn

    @classmethod
    def close_dcb_character(cls, dcb_switch_status: str, device_name: str,
                            cmd_exeute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                            use_dcbtool_flag: bool = True):
        """
        author: wei.yuan1
        date: 2022.09.27
        description: 关闭dcb特性
        :param dcb_switch_status: dcb状态是否使能
        :param device_name: 网卡接口名称
        :param cmd_exeute_address: 命令执行环境
        :param use_dcbtool_flag: 是否使用dcbtool命令，如果为False，则使用iproute2提供的dcb命令
        """
        if use_dcbtool_flag:
            rtn_code = False
            # 启动lldp.service服务
            DcbtoolOperation.launch_lldp_sevice(cmd_execute_address=cmd_exeute_address)
            # 查看网卡的dcb特性是否使能
            dcb_flag = DcbtoolOperation.get_dcb_state(
                device_name=device_name,
                cmd_execute_address=cmd_exeute_address)
            if not dcb_flag:
                # 关闭网卡的dcb使能
                rtn_status = DcbtoolOperation.set_dcb_state(
                    device_name=device_name,
                    state=dcb_switch_status,
                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value
                )
                if not rtn_status:
                    rtn_code = False
                else:
                    rtn_code = True
            return rtn_code
        else:
            dcbx_cmd = r"dcb dcbx set dev {} host ieee".format(device_name)
            dcb_cmd = r"dcb ets set dev {} tc-tsa all:ets tc-bw 0:100 1:0 2:0 3:0 4:0 5:0 6:0 7:0 " \
                      r"prio-tc 0:0 1:0 2:0 3:0 4:0 5:0 6:0 7:0".format(device_name)
            rtn_code, rtn_output, rtn_err = CommandOperation.execute_command_with_error(
                cmd=dcbx_cmd, cmd_execute_address=cmd_exeute_address)
            log.info(f'执行命令: {dcbx_cmd}, 标准输出: {rtn_output}, 错误输出: {rtn_err}')
            rtn_code, rtn_output, rtn_err = CommandOperation.execute_command_with_error(
                cmd=dcb_cmd, cmd_execute_address=cmd_exeute_address)
            log.info(f'执行命令: {dcb_cmd}, 标准输出: {rtn_output}, 错误输出: {rtn_err}')
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                return True
            else:
                return False

    @classmethod
    def get_ets_info(cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> dict:
        """
       author:             shaohui.wang
       date:               2022-10-16
       description:

       :param device_name: 网卡设备名称,如ens1f0
       :param cmd_execute_address:
       return: {

               }
       """
        pass
        # result_dict = dict()
        # exec_command = constants.STR_SPACE.join([constants.LLDPTOOL, constants.GET_TLV, '-i', device_name,
        #                                          '-V', constants.ETS_CFG])
        #
        # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
        #     exec_command, cmd_execute_address=cmd_execute_address)
        #
        # if rtn_code == RtnStatusEnum.SUCCESS.value:
        #     result_list = rtn_outputs.split('\n')
        #
        #     for item in result_list:
        #         if item.strip():
        #             key, value = item.split(':')
        #             result_dict[key.strip()] = value.strip()
        # else:
        #     log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        #
        # return result_dict

    # @classmethod
    # def set_ets_feature(cls):


if __name__ == '__main__':
    DcbtoolOperation.get_dcbx_version(CmdExecuteAdressEnum.SERVER.value)
