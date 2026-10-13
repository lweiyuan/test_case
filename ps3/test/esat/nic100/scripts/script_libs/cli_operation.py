import os.path
import random
import time

import add_syspath
import functools
import re
from scripts.script_libs import log
from scripts.script_libs import constants
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse
from scripts.script_libs.host_operation import HostOperation
from scripts.script_libs.script_base import ScriptBase
from scripts.script_libs.file_operation import FileOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import (RtnStatusEnum, CmdExecuteAdressEnum, CliStatusEnum, ExitCodeEnum, RegionEnum,
                                       FpgaBitfileClass, CompareType, RegionNumEnum, MfgCheckType)
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.ifconfig import IfConfig
from re import findall, S
from collections import defaultdict

from scripts.script_libs.socket_operation import SocketOption


class ExecCli(object):
    @classmethod
    def exec_cli_show(cls, exec_addr):
        cmd = f'{constants.SCGBECLI64} show'
        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr
        )
        return code, output, stderr

    @classmethod
    def exec_cli_show_list(cls, exec_addr):
        cmd = f'{constants.SCGBECLI64} show list'
        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr
        )
        return code, output, stderr

    @classmethod
    def exec_cli_dev_show(cls, dev_para, exec_addr):
        cmd = f'{constants.SCGBECLI64} -d {dev_para} show'
        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr
        )
        return code, output, stderr

    @classmethod
    def exec_cli_dev_show_fw(cls, dev_para, exec_addr):
        cmd = f'{constants.SCGBECLI64} -d {dev_para} show fw'
        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr
        )
        return code, output, stderr

    @classmethod
    def exec_cli_dev_reset(cls, dev_para, exec_addr, level=None, para_type=None, sync=None):
        cmd = f'{constants.SCGBECLI64} -d {dev_para} reset'
        if isinstance(para_type, int):
            cmd += f' type={para_type}'

        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr
        )
        return code, output, stderr

    @classmethod
    def exec_cli_dev_reset_soc(cls, dev_para, exec_addr, time=None):
        cmd = f'{constants.SCGBECLI64} -d {dev_para} reset soc '
        if time:
            cmd += f'resetTime={time}'
        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr
        )
        return code, output, stderr

    @classmethod
    def exec_cli_dev_upgrade(cls, dev_para, file, exec_addr, noverchk=False):
        if ';' in file:
            filter_path = file.split(';')[0]
            relative_path = file.split(';')[1]
            cmd = f'cd {filter_path}; {constants.SCGBECLI64} -d {dev_para} upgrade file={relative_path}'
        else:
            cmd = f'{constants.SCGBECLI64} -d {dev_para} upgrade file={file}'
        if noverchk:
            cmd += ' noverchk'
        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr
        )
        return code, output, stderr

    @classmethod
    def exec_cli_dev_debug_upgrade(cls, dev_para, file, exec_addr):
        if ';' in file:
            filter_path = file.split(';')[0]
            relative_path = file.split(';')[1]
            cmd = f'cd {filter_path}; {constants.SCGBECLI64} -d {dev_para} debug upgrade packet {relative_path}'
        else:
            cmd = f'{constants.SCGBECLI64} -d {dev_para} debug upgrade packet {file}'

        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr, timeout=3600
        )
        if code != RtnStatusEnum.SUCCESS.value:
            CommonOperation.create_bug_problem(cls, key_word='bootloader',
                                               description_word=f'升级32M包失败')
        return code, output, stderr

    @classmethod
    def exec_cli_dev_custom_fwinfo(cls, dev_para, exec_addr):
        # todo:补充指令
        cmd = f'{constants.SCGBECLI64} -d {dev_para} '

        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr
        )
        return code, output, stderr

    @classmethod
    def exec_cli_dev_custom_coredump(cls, dev_para, exec_addr, coredump):
        # todo:补充指令
        cmd = f'{constants.SCGBECLI64} -d {dev_para} custom sxe2 coredump {coredump}'

        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr
        )
        return code, output, stderr

    @classmethod
    def exec_cli_dev_custom_cfgShow(cls, dev_para, exec_addr, module):
        cmd = f'{constants.SCGBECLI64} -d {dev_para} custom sxe2 cfgShow {module}'
        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr
        )
        return code, output, stderr

    @classmethod
    def exec_cli_dev_get_reg(cls, dev_para, exec_addr, reg_addr, reg_type='A', width=32, count=None):
        if isinstance(reg_addr, int) is True:
            addr = '0x%x' % reg_addr
        else:
            addr = reg_addr
        if count:
            cmd = f'{constants.SCGBECLI64} -d {dev_para} get reg type={reg_type} width={width} addr={addr} count={count}'
        else:
            cmd = f'{constants.SCGBECLI64} -d {dev_para} get reg type={reg_type} width={width} addr={addr}'
        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr
        )
        return code, output, stderr

    @classmethod
    def exec_cli_dev_set_reg(cls, dev_para, exec_addr, reg_addr, value, reg_type='A', width=32):
        cmd = f'{constants.SCGBECLI64} -d {dev_para} get reg type={reg_type} width={width} '
        if isinstance(reg_addr, int) is True:
            addr = '0x%x' % reg_addr
        else:
            addr = reg_addr
        cmd += f'addr={addr} '
        if isinstance(value, list) is True:
            for v in value:
                if isinstance(v, int) is True:
                    cmd += 'value=0x%x ' % v
                else:
                    cmd += f'value={v}'
        else:
            if isinstance(value, int) is True:
                cmd += 'value=0x%x ' % value
            else:
                cmd += f'value={value}'
        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr
        )
        return code, output, stderr

    @classmethod
    def exec_cli_dev_show_termlog(cls, dev_para, exec_addr, show_all=False, file=None, reverse=False):
        cmd = f'{constants.SCGBECLI64} -d {dev_para} show termlog '
        if show_all and not reverse:
            cmd += 'all '
        if file:
            if ';' in file:
                filter_path = file.split(';')[0].strip()
                relative_path = file.split(';')[1].strip()
                cmd = f'cd {filter_path}; {cmd} file={relative_path}'
                rtn = FileOperation.make_directory(filter_path, match_flag=False, delete_flag=False)
                log.info(f'路径{filter_path}创建结果{rtn}')
            else:
                cmd += f'file={file} '
        if show_all and reverse:
            cmd += 'all '
        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr
        )
        return code, output, stderr

    @classmethod
    def exec_cli_dev_upload_coredump(cls, dev_para, exec_addr, file):
        if ';' in file:
            filter_path = file.split(';')[0].strip()
            relative_path = file.split(';')[1].strip()
            cmd = f'cd {filter_path}; {constants.SCGBECLI64} -d {dev_para} upload coredump file={relative_path}'
        else:
            cmd = f'{constants.SCGBECLI64} -d {dev_para} upload coredump file={file}'
        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr
        )
        return code, output, stderr

    @classmethod
    def exec_cli_dev_show_device(cls, dev_para, exec_addr):
        cmd = f'{constants.SCGBECLI64} -d {dev_para} show device'
        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr
        )
        return code, output, stderr

    @classmethod
    def exec_cli_dev_show_status(cls, dev_para, exec_addr):
        cmd = f'{constants.SCGBECLI64} -d {dev_para} show status'
        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr
        )
        return code, output, stderr

    @classmethod
    def exec_cli_dev_show_link_base(cls, dev_para, exec_addr):
        cmd = f'{constants.SCGBECLI64} -d {dev_para} show link base'
        code, output, stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr
        )
        return code, output, stderr


class AnalyzeCli(object):

    @classmethod
    def analyze_show(cls, exec_addr):
        code, rtn_output, stderr = ExecCli.exec_cli_show(exec_addr=exec_addr)
        re_status = findall(r'Status\s+=\s+(\w+)', rtn_output)
        rtn_dict = defaultdict(list)
        if re_status:
            if re_status[0] == CliStatusEnum.SUCCESS.value:
                rtn_status = CliStatusEnum.SUCCESS.value
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
                re_devices = findall(r'(Controller \d+).*\+-+\+-+\+-+\+-+\+-+\+-+\+-+\+-+\+(.*)\+-+\+', rtn_output, S)
                # print(re_devices)
                # [('Controller 0', '\n        |0000:8a:00.0 |22:11:00:33:44:aa |ens6f0       |0000      |8a:00.0            |10 Gb/s    |0.6.0.3          |0.6.0.3          |\n        ')]
                for re_device in re_devices:
                    nic = re_device[0]
                    nic_info = re_device[1]
                    re_info = findall(
                        r'\|(.*)\|(.*)\|(.*).*\|(.*).*\|(.*).*\|(.*).*\|(.*).*\|(.*).*\|', nic_info)
                    for info in re_info:
                        rtn_dict[nic].append({
                            'Device': info[0].strip(),
                            'Mac Address': info[1].strip(),
                            'Network Name': info[2].strip(),
                            'Domain ID': info[3].strip(),
                            'BDF': info[4].strip(),
                            'Link Speed': info[5].strip(),
                            'Firmware Version': info[6].strip(),
                            'OptionRom Version': info[7].strip()
                        })
        elif re_status[0] == CliStatusEnum.FAILURE.value:
            rtn_status = CliStatusEnum.FAILURE.value
            rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
            rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
            rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
            rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
            rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
            rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
        else:
            rtn_status = CliStatusEnum.ERROR.value
            rtn_dict = {
                "key_word": "CLI",
                "description_word": f"指令返回Status不为Success或Failure，\n"
                                    f"code:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                "expect_info": "",
                "result_info": ""
            }
        return rtn_status, rtn_dict, rtn_output

    @classmethod
    def analyze_show_list(cls, exec_addr):
        code, rtn_output, stderr = ExecCli.exec_cli_show_list(exec_addr=exec_addr)
        re_status = findall(r'Status\s+=\s+(\w+)', rtn_output)
        rtn_dict = defaultdict(list)
        if re_status:
            if re_status[0] == CliStatusEnum.SUCCESS.value:
                rtn_status = CliStatusEnum.SUCCESS.value
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                dev_info_lists = findall(r'\|(\S+)\s+\|(\S+)\s+\|(\S+)\s*\|(\S+)\s*\|(\S+)\s*\|', rtn_output)
                # print(dev_info_lists)
                for dev_info_lst in dev_info_lists:
                    rtn_dict[f'Device List'].append({
                        'Rdma Name': dev_info_lst[0],
                        'Ethernet Name': dev_info_lst[1],
                        'Domain ID': dev_info_lst[2],
                        'BDF': dev_info_lst[3],
                        'Mac Adderess': dev_info_lst[4]
                    })
            elif re_status[0] == CliStatusEnum.FAILURE.value:
                rtn_status = CliStatusEnum.FAILURE.value
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
            else:
                rtn_status = CliStatusEnum.ERROR.value
                rtn_dict = {
                    "key_word": "CLI",
                    "description_word": f"指令返回Status不为Success或Failure，\n"
                                        f"code:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                    "expect_info": "",
                    "result_info": ""
                }
        else:
            rtn_status = CliStatusEnum.ERROR.value
            rtn_dict = {
                "key_word": "CLI",
                "description_word": f"指令执行失败，\ncode:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                "expect_info": "",
                "result_info": ""
            }

        return rtn_status, rtn_dict, rtn_output

    @classmethod
    def analyze_dev_show_fw(cls, dev_para, exec_addr) -> (str, dict, str):
        code, rtn_output, stderr = ExecCli.exec_cli_dev_show_fw(dev_para=dev_para, exec_addr=exec_addr)
        re_status = findall(r'Status\s+=\s+(\w+)', rtn_output)
        rtn_dict = defaultdict(dict)
        if re_status:
            if re_status[0] == CliStatusEnum.SUCCESS.value:
                rtn_status = CliStatusEnum.SUCCESS.value
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
                # rtn_dict['Image Type'] = findall(r'Image Type\s*\|(\S+)', rtn_output)[0].strip()
                rtn_dict['FW Version'] = findall(r'FW Version\s*\|(\S+)', rtn_output)[0].strip()
                rtn_dict['FW Release Date'] = findall(r'FW Release Date\s*\|(\S+)', rtn_output)[0].strip()
                if findall(r'Product Version\s*\|(\S+)\s*\|', rtn_output):
                    rtn_dict['Product Version'] = findall(r'Product Version\s*\|(\S+)\s*\|', rtn_output)[0].strip()
                if findall(r'UEFI\s*\|(\S+)\s*\|', rtn_output):
                    rtn_dict['UEFI']['Version'] = findall(r'UEFI\s*\|(\S+)\s*\|', rtn_output)[0].strip()
                if findall(r'UEFI\s*\|.*|(\S+)', rtn_output):
                    rtn_dict['UEFI']['Cpu'] = findall(r'UEFI\s*\|.*|(\S+)', rtn_output)[0].strip()
                # rtn_dict['PXE']['Version'] = findall(r'PXE\s*\|(\S+)\s*\|', rtn_output)[0].strip()
                # rtn_dict['PXE']['Cpu'] = findall(r'PXE\s*\|.*|(\S+)', rtn_output)[0].strip()
                rtn_dict['Base UUID'] = findall(r'Base UUID\s*\|(\S+)\s*\|', rtn_output)[0].strip()
                rtn_dict['Base MAC'] = findall(r'Base MAC\s*\|(\S+)\s*\|', rtn_output)[0].strip()
            elif re_status[0] == CliStatusEnum.FAILURE.value:
                rtn_status = CliStatusEnum.FAILURE.value
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
            else:
                rtn_status = CliStatusEnum.ERROR.value
                rtn_dict = {
                    "key_word": "CLI",
                    "description_word": f"指令返回Status不为Success或Failure，\n"
                                        f"code:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                    "expect_info": "",
                    "result_info": ""
                }
        else:
            rtn_status = CliStatusEnum.ERROR.value
            rtn_dict = {
                "key_word": "CLI",
                "description_word": f"指令执行失败，\ncode:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                "expect_info": "",
                "result_info": ""
            }

        return rtn_status, rtn_dict, rtn_output

    @classmethod
    def analyze_dev_show(cls, dev_para, exec_addr=CmdExecuteAdressEnum.SERVER.value) -> (str, dict, str):
        code, rtn_output, stderr = ExecCli.exec_cli_dev_show(dev_para=dev_para, exec_addr=exec_addr)
        re_status = findall(r'Status\s+=\s+(\w+)', rtn_output)
        rtn_dict = defaultdict(dict)
        if re_status:
            if re_status[0] == CliStatusEnum.SUCCESS.value:
                rtn_status = CliStatusEnum.SUCCESS.value
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['SOC Status'] = findall(r'SOC Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['SOC Temperature'] = findall(r'SOC Temperature \(Degree Celsius\)\s*=\s*(.*)', rtn_output)[
                    0].strip()
                rtn_dict['Firmware Version'] = findall(r'Firmware Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['OptionRom Version'] = findall(r'OptionRom Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Mac Address'] = findall(r'Mac Address\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Port Link'] = findall(r'Port Link\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Link Status'] = findall(r'Link Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Link Speed'] = findall(r'Link Speed\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['SFP Information Acquisition Status'] = \
                    findall(r'SFP Information Acquisition Status\s*=\s*(.*)', rtn_output)[0].strip()
                if rtn_dict['SFP Information Acquisition Status'] == "Successful":
                    rtn_dict['Optical Mod Temperature'] = \
                        findall(r'Optical Mod Temperature \(Degree Celsius\)\s*=\s*(.*)', rtn_output)[0].strip()
                    rtn_dict['Transceiver Type'] = findall(r'Transceiver Type\s*=\s*(.*)', rtn_output)[0].strip()
                    rtn_dict['Vendor Name'] = findall(r'Vendor Name\s*=\s*(.*)', rtn_output)[0].strip()
                    rtn_dict['Vendor PN'] = findall(r'Vendor PN\s*=\s*(.*)', rtn_output)[0].strip()
                else:
                    rtn_dict['Optical Mod Temperature'] = ""
                    rtn_dict['Transceiver Type'] = ""
                    rtn_dict['Vendor Name'] = ""
                    rtn_dict['Vendor PN'] = ""
            elif re_status[0] == CliStatusEnum.FAILURE.value:
                rtn_status = CliStatusEnum.FAILURE.value
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
            else:
                rtn_status = CliStatusEnum.ERROR.value
                rtn_dict = {
                    "key_word": "CLI",
                    "description_word": f"指令返回Status不为Success或Failure，\n"
                                        f"code:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                    "expect_info": "",
                    "result_info": ""
                }
        else:
            rtn_status = CliStatusEnum.ERROR.value
            rtn_dict = {
                "key_word": "CLI",
                "description_word": f"指令执行失败，\ncode:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                "expect_info": "",
                "result_info": ""
            }

        return rtn_status, rtn_dict, rtn_output

    @classmethod
    def analyze_dev_reset(cls, dev_para, exec_addr, level=None, para_type=None, sync=None):
        code, rtn_output, stderr = ExecCli.exec_cli_dev_reset(
            dev_para=dev_para, exec_addr=exec_addr, level=level, para_type=para_type, sync=sync)
        re_status = findall(r'Status\s+=\s+(\w+)', rtn_output)
        rtn_dict = {}
        if re_status:
            if re_status[0] in [CliStatusEnum.SUCCESS.value, CliStatusEnum.FAILURE.value]:
                rtn_status = re_status[0]
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
            else:
                rtn_status = CliStatusEnum.ERROR.value
                rtn_dict = {
                    "key_word": "CLI",
                    "description_word": f"指令返回Status不为Success或Failure，\n"
                                        f"code:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                    "expect_info": "",
                    "result_info": ""
                }
        else:
            rtn_status = CliStatusEnum.ERROR.value
            rtn_dict = {
                "key_word": "CLI",
                "description_word": f"指令执行失败，\ncode:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                "expect_info": "",
                "result_info": ""
            }

        return rtn_status, rtn_dict, rtn_output

    @classmethod
    def analyze_dev_reset_soc(cls, dev_para, exec_addr, time=None):
        code, rtn_output, stderr = ExecCli.exec_cli_dev_reset_soc(
            dev_para=dev_para, exec_addr=exec_addr, time=time)
        re_status = findall(r'Status\s+=\s+(\w+)', rtn_output)
        rtn_dict = {}
        if re_status:
            if re_status[0] in [CliStatusEnum.SUCCESS.value, CliStatusEnum.FAILURE.value]:
                rtn_status = re_status[0]
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
            else:
                rtn_status = CliStatusEnum.ERROR.value
                rtn_dict = {
                    "key_word": "CLI",
                    "description_word": f"指令返回Status不为Success或Failure，\n"
                                        f"code:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                    "expect_info": "",
                    "result_info": ""
                }
        else:
            rtn_status = CliStatusEnum.ERROR.value
            rtn_dict = {
                "key_word": "CLI",
                "description_word": f"指令执行失败，\ncode:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                "expect_info": "",
                "result_info": ""
            }

        return rtn_status, rtn_dict, rtn_output

    @classmethod
    def analyze_dev_upgrade(cls, dev_para, file, exec_addr, noverchk=False):
        code, rtn_output, stderr = ExecCli.exec_cli_dev_upgrade(
            dev_para=dev_para, file=file, exec_addr=exec_addr, noverchk=noverchk)
        re_status = findall(r'Status\s+=\s+(\w+)', rtn_output)
        rtn_dict = {}
        if re_status:
            if re_status[0] in [CliStatusEnum.SUCCESS.value]:
                rtn_status = re_status[0]
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                # if re_status[0] in [CliStatusEnum.SUCCESS.value]:
                if 'Device' in rtn_output:
                    rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
            else:
                rtn_status = CliStatusEnum.FAILURE.value
                rtn_dict = {
                    "key_word": "CLI",
                    "description_word": f"指令返回Status不为Success或Failure，\n"
                                        f"code:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                    "expect_info": "",
                    "result_info": ""
                }
        else:
            rtn_status = CliStatusEnum.ERROR.value
            rtn_dict = {
                "key_word": "CLI",
                "description_word": f"指令执行失败，\ncode:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                "expect_info": "",
                "result_info": ""
            }
        return rtn_status, rtn_dict, rtn_output

    @classmethod
    def analyze_dev_debug_upgrade(cls, dev_para, file, exec_addr):
        code, rtn_output, stderr = ExecCli.exec_cli_dev_debug_upgrade(
            dev_para=dev_para, file=file, exec_addr=exec_addr)
        re_status = findall(r'Status\s+=\s+(\w+)', rtn_output)
        rtn_dict = {}
        if re_status:
            if re_status[0] in [CliStatusEnum.SUCCESS.value, CliStatusEnum.FAILURE.value]:
                rtn_status = re_status[0]
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
            else:
                rtn_status = CliStatusEnum.ERROR.value
                rtn_dict = {
                    "key_word": "CLI",
                    "description_word": f"指令返回Status不为Success或Failure，\n"
                                        f"code:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                    "expect_info": "",
                    "result_info": ""
                }
        else:
            rtn_status = CliStatusEnum.ERROR.value
            rtn_dict = {
                "key_word": "CLI",
                "description_word": f"指令执行失败，\ncode:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                "expect_info": "",
                "result_info": ""
            }
        return rtn_status, rtn_dict, rtn_output

    @classmethod
    def analyze_dev_custom_fwinfo(cls, dev_para, exec_addr):
        code, rtn_output, stderr = ExecCli.exec_cli_dev_custom_fwinfo(dev_para, exec_addr)
        re_status = findall(r'Status\s+=\s+(\w+)', rtn_output)
        rtn_dict = {}
        if re_status:
            if re_status[0] in [CliStatusEnum.SUCCESS.value, CliStatusEnum.FAILURE.value]:
                rtn_status = re_status[0]
                # todo: 待补充获取参数
                pass
            else:
                rtn_status = CliStatusEnum.ERROR.value
                rtn_dict = {
                    "key_word": "CLI",
                    "description_word": f"指令返回Status不为Success或Failure，\n"
                                        f"code:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                    "expect_info": "",
                    "result_info": ""
                }
        else:
            rtn_status = CliStatusEnum.ERROR.value
            rtn_dict = {
                "key_word": "CLI",
                "description_word": f"指令执行失败，\ncode:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                "expect_info": "",
                "result_info": ""
            }
        return rtn_status, rtn_dict, rtn_output

    @classmethod
    def analyze_dev_custom_cfgShow(cls, dev_para, exec_addr, module):
        code, rtn_output, stderr = ExecCli.exec_cli_dev_custom_cfgShow(dev_para, exec_addr, module)
        re_output = findall(r'0x\w+:(\w+)\s(\w+)\s(\w+)\s(\w+)', rtn_output)
        reg_lst = []
        for re_reg in re_output:
            for reg in re_reg:
                reg_lst.append(reg)
        if reg_lst:
            rtn_status = CliStatusEnum.SUCCESS.value
            return rtn_status, reg_lst, rtn_output
        else:
            rtn_status = CliStatusEnum.ERROR.value
            rtn_dict = {
                "key_word": "CLI",
                "description_word": f"指令执行失败，\ncode:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                "expect_info": "",
                "result_info": ""
            }

            return rtn_status, rtn_dict, rtn_output

    @classmethod
    def analyze_dev_get_reg(cls, dev_para, exec_addr, reg_addr, reg_type='A', width=32, count=None):
        code, rtn_output, stderr = ExecCli.exec_cli_dev_get_reg(dev_para, exec_addr, reg_addr, reg_type, width, count)
        re_status = findall(r'Status\s+=\s+(\w+)', rtn_output)
        rtn_dict = defaultdict(dict)
        if re_status:
            if re_status[0] == CliStatusEnum.SUCCESS.value:
                rtn_status = CliStatusEnum.SUCCESS.value
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
                re_reg_info = findall(rf'{reg_type}\s+\|(\w+)\s+\|(\w+)\s+\|(\w+)\s+\|(\w+)\s+\|', rtn_output)
                for reg_info in re_reg_info:
                    addr = reg_info[0]
                    rtn_dict[addr]['Reg Type'] = reg_type
                    rtn_dict[addr]['Value'] = reg_info[1]
                    rtn_dict[addr]['Errcd'] = reg_info[2]
                    rtn_dict[addr]['Message'] = reg_info[3]
            elif re_status[0] == CliStatusEnum.FAILURE.value:
                rtn_status = CliStatusEnum.FAILURE.value
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
            else:
                rtn_status = CliStatusEnum.ERROR.value
                rtn_dict = {
                    "key_word": "CLI",
                    "description_word": f"指令返回Status不为Success或Failure，\n"
                                        f"code:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                    "expect_info": "",
                    "result_info": ""
                }
        else:
            rtn_status = CliStatusEnum.ERROR.value
            rtn_dict = {
                "key_word": "CLI",
                "description_word": f"指令执行失败，\ncode:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                "expect_info": "",
                "result_info": ""
            }

        return rtn_status, rtn_dict, rtn_output

    @classmethod
    def analyze_dev_set_reg(cls, dev_para, exec_addr, reg_addr, value, reg_type='A', width=32):
        code, rtn_output, stderr = ExecCli.exec_cli_dev_set_reg(dev_para, exec_addr, reg_addr, value, reg_type, width)
        re_status = findall(r'Status\s+=\s+(\w+)', rtn_output)
        rtn_dict = {}
        if re_status:
            if re_status[0] in [CliStatusEnum.SUCCESS.value, CliStatusEnum.FAILURE.value]:
                rtn_status = re_status[0]
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
            else:
                rtn_status = CliStatusEnum.ERROR.value
                rtn_dict = {
                    "key_word": "CLI",
                    "description_word": f"指令返回Status不为Success或Failure，\n"
                                        f"code:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                    "expect_info": "",
                    "result_info": ""
                }
        else:
            rtn_status = CliStatusEnum.ERROR.value
            rtn_dict = {
                "key_word": "CLI",
                "description_word": f"指令执行失败，\ncode:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                "expect_info": "",
                "result_info": ""
            }
        return rtn_status, rtn_dict, rtn_output

    @classmethod
    def analyze_dev_show_termlog(cls, dev_para, exec_addr, show_all=False, file=None, reverse=False):
        code, rtn_output, stderr = ExecCli.exec_cli_dev_show_termlog(dev_para, exec_addr, show_all, file, reverse)
        re_status = findall(r'Status\s+=\s+(\w+)', rtn_output)
        rtn_dict = {}
        if re_status:
            if re_status[0] in [CliStatusEnum.SUCCESS.value, CliStatusEnum.FAILURE.value]:
                rtn_status = re_status[0]
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
                if re_status[0] in [CliStatusEnum.SUCCESS.value]:
                    # CommandOperation.execute_command_with_error(
                    #     cmd='mkdir -p /root/scgbe_termlog', cmd_execute_address=exec_addr)
                    _, sys_time, _ = CommandOperation.execute_command_with_error(
                        cmd="date '+%Y_%m_%d_%H_%M_%S'", cmd_execute_address=exec_addr
                    )
                    if file:
                        if ';' in file:
                            file = file.replace(';', '/').replace(' ', '')
                        _, output, _ = CommandOperation.execute_command_with_error(
                            cmd=f'find {file}', cmd_execute_address=exec_addr)
                        if file not in output and rtn_status == CliStatusEnum.SUCCESS.value:
                            rtn_status = CliStatusEnum.ERROR.value
                            rtn_dict = {
                                "key_word": "CLI",
                                "description_word": f"未找到导出的日志",
                                "expect_info": "",
                                "result_info": ""
                            }
                        else:
                            CommandOperation.execute_command_with_error(
                                cmd=f'cp {file} /root/scgbe_termlog/cli_log_{sys_time}.log')
                            cmd = f'python3 {constants.CHECK_ENCODE} {file}'
                            _, output, _ = CommandOperation.execute_command_with_error(cmd=cmd,
                                                                                       cmd_execute_address=exec_addr)
                            re_code = findall(r'(\d+)', output)
                            code = int(re_code[0])
                            rtn_dict['garbled'] = False
                            rtn_dict['missing'] = False
                            if code & 0b01:
                                rtn_dict['garbled'] = True
                            if code & 0b10:
                                rtn_dict['missing'] = True
                            if rtn_dict['garbled'] or rtn_dict['missing']:
                                CommonOperation.create_bug_problem(ScriptBase, key_word=f'termlog',
                                                                   description_word=f'termlog里有乱码或者缺失')
                            _, rtn_size, _ = CommandOperation.execute_command_with_error(
                                cmd=f'ls -l --block-size=k {file}',
                                cmd_execute_address=exec_addr)
                            rtn_dict['size'] = int(findall(r'\s+(\d+)K', rtn_size)[0])
                    else:
                        rtn_lines = rtn_output.splitlines()
                        rtn_dict['garbled'] = False
                        rtn_dict['missing'] = False
                        # for line in rtn_lines:
                        #     if line == "":
                        #         continue
                        #     result_dict = chardet.detect(line)
                        #     result = result_dict['encoding']
                        #     if result is None:
                        #         rtn_dict['garbled'] = True
                        #         CommandOperation.execute_command_with_error(
                        #             cmd=f'echo /root/sxe_termlog/cli_log_{sys_time}.log')
                        #     if b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' in line:
                        #         rtn_dict['missing'] = True
            else:
                rtn_status = CliStatusEnum.ERROR.value
                rtn_dict = {
                    "key_word": "CLI",
                    "description_word": f"指令返回Status不为Success或Failure，\n"
                                        f"code:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                    "expect_info": "",
                    "result_info": ""
                }
        else:
            rtn_status = CliStatusEnum.ERROR.value
            rtn_dict = {
                "key_word": "CLI",
                "description_word": f"指令执行失败，\ncode:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                "expect_info": "",
                "result_info": ""
            }

        return rtn_status, rtn_dict, rtn_output

    @classmethod
    def analyze_dev_upload_coredump(cls, dev_para, exec_addr, file):
        code, rtn_output, stderr = ExecCli.exec_cli_dev_upload_coredump(dev_para, exec_addr, file)
        re_status = findall(r'Status\s+=\s+(\w+)', rtn_output)
        rtn_dict = {}
        if re_status:
            if re_status[0] in [CliStatusEnum.SUCCESS.value, CliStatusEnum.FAILURE.value]:
                rtn_status = re_status[0]
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                if f'Device {dev_para}' in rtn_output:
                    rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
                if rtn_status == CliStatusEnum.SUCCESS.value:
                    if ';' in file:
                        file = file.replace(';', '/').replace(' ', '')
                    _, output, _ = CommandOperation.execute_command_with_error(
                        cmd=f'find {file}', cmd_execute_address=exec_addr)
                    if file not in output:
                        rtn_status = CliStatusEnum.ERROR.value
                        rtn_dict = {
                            "key_word": "CLI",
                            "description_word": f"未找到导出的coredump文件",
                            "expect_info": "",
                            "result_info": ""
                        }
                    _, rtn_size, _ = CommandOperation.execute_command_with_error(
                        cmd=f'ls -l --block-size=k {file}',
                        cmd_execute_address=exec_addr)
                    size = int(findall(r'\s+(\d+)K', rtn_size)[0])
                    if size != constants.COREDUMP_SIZE:
                        rtn_status = CliStatusEnum.ERROR.value
                        rtn_dict = {
                            "key_word": "CLI",
                            "description_word": f"导出的core文件大小不等于{constants.COREDUMP_SIZE}K",
                            "expect_info": "",
                            "result_info": ""
                        }
            else:
                rtn_status = CliStatusEnum.ERROR.value
                rtn_dict = {
                    "key_word": "CLI",
                    "description_word": f"指令返回Status不为Success或Failure，\n"
                                        f"code:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                    "expect_info": "",
                    "result_info": ""
                }
        else:
            rtn_status = CliStatusEnum.ERROR.value
            rtn_dict = {
                "key_word": "CLI",
                "description_word": f"指令执行失败，\ncode:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                "expect_info": "",
                "result_info": ""
            }
        return rtn_status, rtn_dict, rtn_output

    @classmethod
    def analyze_dev_show_device(cls, dev_para, exec_addr) -> (str, dict, str):
        code, rtn_output, stderr = ExecCli.exec_cli_dev_show_device(dev_para=dev_para, exec_addr=exec_addr)
        re_status = findall(r'Status\s+=\s+(\w+)', rtn_output)
        rtn_dict = dict()
        if re_status:
            if re_status[0] == CliStatusEnum.SUCCESS.value:
                rtn_status = CliStatusEnum.SUCCESS.value
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Product Number'] = findall(r'Product Number\s*\|(.*)\|', rtn_output)[0].strip()
                rtn_dict['Product Name'] = findall(r'Product Name\s*\|(.*)\|', rtn_output)[0].strip()
                rtn_dict['Serial Number'] = findall(r'Serial Number\s*\|(.*)\|', rtn_output)[0].strip()
                rtn_dict['Revision'] = findall(r'Revision\s*\|(.*)\|', rtn_output)[0].strip()
                rtn_dict['FW Version'] = findall(r'FW Version\s*\|(.*)\|', rtn_output)[0].strip()
            elif re_status[0] == CliStatusEnum.FAILURE.value:
                rtn_status = CliStatusEnum.FAILURE.value
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
            else:
                rtn_status = CliStatusEnum.ERROR.value
                rtn_dict = {
                    "key_word": "CLI",
                    "description_word": f"指令返回Status不为Success或Failure，\n"
                                        f"code:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                    "expect_info": "",
                    "result_info": ""
                }
        else:
            rtn_status = CliStatusEnum.ERROR.value
            rtn_dict = {
                "key_word": "CLI",
                "description_word": f"指令执行失败，\ncode:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                "expect_info": "",
                "result_info": ""
            }

        return rtn_status, rtn_dict, rtn_output

    @classmethod
    def analyze_dev_show_status(cls, dev_para, exec_addr):
        code, rtn_output, stderr = ExecCli.exec_cli_dev_show_status(dev_para=dev_para, exec_addr=exec_addr)
        re_status = findall(r'Status\s+=\s+(\w+)', rtn_output)
        rtn_dict = dict()
        if re_status:
            if re_status[0] == CliStatusEnum.SUCCESS.value:
                rtn_status = CliStatusEnum.SUCCESS.value
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Firmware Version'] = findall(r'Firmware Version\s*\|(\S+)\|', rtn_output)[0].strip()
                rtn_dict['Hardware Version'] = findall(r'Hardware Version\s*\|(\S+)\|', rtn_output)[0].strip()
                rtn_dict['State'] = findall(r'State\s*\|(\S+)', rtn_output)[0].strip()
                rtn_dict['Physical State'] = findall(r'Physical State\s*\|(\w+\s+\w+)', rtn_output)[0].strip()
                rtn_dict['Rate'] = findall(r'Rate\s*\|(\S+)', rtn_output)[0].strip()
            elif re_status[0] == CliStatusEnum.FAILURE.value:
                rtn_status = CliStatusEnum.FAILURE.value
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
            else:
                rtn_status = CliStatusEnum.ERROR.value
                rtn_dict = {
                    "key_word": "CLI",
                    "description_word": f"指令返回Status不为Success或Failure，\n"
                                        f"code:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                    "expect_info": "",
                    "result_info": ""
                }
        else:
            rtn_status = CliStatusEnum.ERROR.value
            rtn_dict = {
                "key_word": "CLI",
                "description_word": f"指令执行失败，\ncode:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                "expect_info": "",
                "result_info": ""
            }

        return rtn_status, rtn_dict, rtn_output

    @classmethod
    def analyze_dev_show_link_base(cls, dev_para, exec_addr):
        code, rtn_output, stderr = ExecCli.exec_cli_dev_show_link_base(dev_para=dev_para, exec_addr=exec_addr)
        re_status = findall(r'Status\s+=\s+(\w+)', rtn_output)
        rtn_dict = dict()
        if re_status:
            if re_status[0] == CliStatusEnum.SUCCESS.value:
                rtn_status = CliStatusEnum.SUCCESS.value
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['State'] = findall(r'State\s*\|(.*)\|', rtn_output)[0].strip()
                rtn_dict['Physical State'] = findall(r'Physical State\s*\|(.*)\|', rtn_output)[0].strip()
                rtn_dict['Speed'] = findall(r'Speed\s*\|(.*)\|', rtn_output)[0].strip()
                rtn_dict['Width'] = findall(r'Width\s*\|(.*)\|', rtn_output)[0].strip()
                rtn_dict['FEC'] = findall(r'FEC\s*\|(.*)\|', rtn_output)[0].strip()
                rtn_dict['Loopback Mode'] = findall(r'Loopback Mode\s*\|(.*)\|', rtn_output)[0].strip()
                rtn_dict['Auto Negotiation'] = findall(r'Auto Negotiation\s*\|(.*)\|', rtn_output)[0].strip()
                rtn_dict['Enabled Link Speed'] = \
                    findall(r'Enabled Link Speed \(Ext\.\)\s*\|(.*)\|', rtn_output)[0].strip()
                rtn_dict['Supported Cable Speed'] = \
                    findall(r'upported Cable Speed \(Ext\.\)\s*\|(.*)\|', rtn_output)[0].strip()
                # rtn_dict['Status Opcode'] = findall(r'Status Opcode\s*\|(\S+)\|', rtn_output)[0].strip()
                # rtn_dict['Group Opcode'] = findall(r'Group Opcode\s*\|(\S+)', rtn_output)[0].strip()
                # rtn_dict['Recommendation'] = findall(r'Recommendation\s*\|(\S+)', rtn_output)[0].strip()
                rtn_dict['Firmware Version'] = findall(r'Firmware Version\s*\|(.*)\|', rtn_output)[0].strip()
                rtn_dict['Cli Version'] = findall(r'Cli Version\s*\|(.*)\|', rtn_output)[0].strip()
            elif re_status[0] == CliStatusEnum.FAILURE.value:
                rtn_status = CliStatusEnum.FAILURE.value
                rtn_dict['CLI Version'] = findall(r'CLI Version\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Operating System'] = findall(r'Operating System\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['System Time'] = findall(r'System Time\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Device'] = findall(r'Device\s+(\S+)', rtn_output)[0].strip()
                rtn_dict['Status'] = findall(r'Status\s*=\s*(.*)', rtn_output)[0].strip()
                rtn_dict['Description'] = findall(r'Description\s*=\s*(.*)', rtn_output)[0].strip()
            else:
                rtn_status = CliStatusEnum.ERROR.value
                rtn_dict = {
                    "key_word": "CLI",
                    "description_word": f"指令返回Status不为Success或Failure，\n"
                                        f"code:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                    "expect_info": "",
                    "result_info": ""
                }
        else:
            rtn_status = CliStatusEnum.ERROR.value
            rtn_dict = {
                "key_word": "CLI",
                "description_word": f"指令执行失败，\ncode:{code}, \noutput:{rtn_output}, \nstderr:{stderr}",
                "expect_info": "",
                "result_info": ""
            }

        return rtn_status, rtn_dict, rtn_output


class CommonTool:
    @classmethod
    def modify_bin(cls, byte_type, offset, length, ori_bin, new_bin='tmp.bin',
                   exec_addr=CmdExecuteAdressEnum.SERVER.value):
        # 复制升级包
        CommandOperation.execute_command_with_error(
            cmd=f"mkdir {constants.TMP_PKG_PATH}; cp {ori_bin} {constants.TMP_PKG_PATH}{new_bin}",
            cmd_execute_address=exec_addr
        )
        # byte_type为0时修改的内容为0，为1时修改的内容为随机数
        if byte_type == 0:
            if_path = '/dev/zero'
        else:
            if_path = '/dev/urandom'
        # 将二进制文件dd到要修改的bin文件
        CommandOperation.execute_command_with_error(
            cmd=f"dd if={if_path} bs=1 count={length} seek={offset} of={constants.TMP_PKG_PATH}{new_bin}",
            cmd_execute_address=exec_addr
        )

    @classmethod
    def modify_config_sxe_txt(cls, path, para, new_data, exec_addr):
        CommandOperation.execute_command_with_error(
            cmd=f"sed -i 's/{para} = 0x[0-9a-fA-F]*/{para} = {new_data}/' {path}", cmd_execute_address=exec_addr
        )
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd=f'cat {path} | grep {new_data}', cmd_execute_address=exec_addr
        )
        if new_data in output:
            return True
        else:
            return False

    @classmethod
    def create_bin(cls, byte_type, length, path, exec_addr):
        # byte_type为0时生成全0的二进制文件，为1时生成随机字节构成的二进制文件
        if int(byte_type) == 0:
            cmd = f'dd if=/dev/zero of={path} bs=1 count={length}'
        else:
            cmd = f'dd if=/dev/urandom of={path} bs=1 count={length}'
        CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=exec_addr)
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd=f'stat {path}', cmd_execute_address=exec_addr
        )
        re_size = re.findall(fr'Size: (\d+)', output)
        if re_size and re_size[0] == length:
            return True
        else:
            return False

    @classmethod
    def modify_sign_pack(cls, mode, exec_addr):
        cmd_lst = []
        if mode == 'sign':
            cmd_lst.append(
                f"sed -i 's/sign = lines\[[0-9]\+\].strip()/sign = lines[1].strip()/g' {constants.SIGNPACK_PY}")
        elif mode == 'key':
            cmd_lst.append(f"sed -i 's/key = keyFile.strip() + lines\[[0-9]\+\].strip()/"
                           f"key = keyFile.strip() + lines[3].strip()/g' {constants.SIGNPACK_PY}")
        elif mode == 'ori':
            cmd_lst.append(
                f"sed -i 's/sign = lines\[[0-9]\+\].strip()/sign = lines[2].strip()/g' {constants.SIGNPACK_PY}")
            cmd_lst.append(f"sed -i 's/key = keyFile.strip() + lines\[[0-9]\+\].strip()/"
                           f"key = keyFile.strip() + lines[4].strip()/g' {constants.SIGNPACK_PY}")
        else:
            log.info('MODE NOT SUPPORT')
            return
        for cmd in cmd_lst:
            CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=exec_addr)

    @classmethod
    def add_header(cls, zone, exec_addr, bin_path=None, bus_num=None):
        cmd = f'lspci -vvs {bus_num}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
        if '1ff2:0c22' in out:  # ocpx2
            subdeviceid = '0x0c22'
            deviceid = '0x10b1'
        elif '1ff2:0c21' in out:  # pciex2
            subdeviceid = '0x0c21'
            deviceid = '0x10b1'
        elif '1ff2:0c24' in out:  # 10G衍生卡
            subdeviceid = '0x0c24'
            deviceid = '0x10b3'
        elif '1ff2:0c23' in out:  # ocpx4
            subdeviceid = '0x0c23'
            deviceid = '0x10b1'
        else:
            CommonOperation.create_bug_problem(ScriptBase, key_word=f'FW',
                                               description_word=f'{bus_num}是不支持的卡类型，命令{cmd}返回的信息是{out}')
        if zone == RegionEnum.UBOOT.value and bin_path is None:

            cmd = f"cd {constants.SM23SIGN_DIR}; sh {constants.USER_ADD_HEADER} {constants.BOOTLOADER_TXT} {constants.BOOTLOADER_BIN} ioc sxe2_x86 {subdeviceid} { deviceid} 0x4116177F"
            CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=exec_addr)
            _, output, _ = CommandOperation.execute_command_with_error(
                cmd=f'ls {constants.HEADER_BIN_OUTPUT}', cmd_execute_address=exec_addr
            )
            if 'header' in output:
                file = output.strip('\n').strip()
                return f'{constants.HEADER_BIN_OUTPUT}{file}'
            else:
                log.info('加头失败')
        elif bin_path is None:
            if CommonOperation.is_fpga():
                fpga_bit_class = CommonOperation.get_fpga_bitfile_class()
                if fpga_bit_class == FpgaBitfileClass.A.value:
                    fw_bin = constants.FW_BIN.format('A_F')
                elif fpga_bit_class == FpgaBitfileClass.C.value:
                    fw_bin = constants.FW_BIN.format('C_F')
                elif fpga_bit_class == FpgaBitfileClass.F.value:
                    fw_bin = constants.FW_BIN.format('F')
                elif fpga_bit_class == FpgaBitfileClass.I.value:
                    fw_bin = constants.FW_BIN.format('I_F')
                elif fpga_bit_class == FpgaBitfileClass.M.value:
                    fw_bin = constants.FW_BIN.format('M_F')
                elif fpga_bit_class == FpgaBitfileClass.Q.value:
                    fw_bin = constants.FW_BIN.format('Q_F')
                else:
                    fw_bin = constants.FW_BIN.format('BEFGHKLO_F')
                cmd = f"cd {constants.SM23SIGN_DIR}; sh {constants.USER_ADD_HEADER} {constants.FW_TXT} {fw_bin} ioc"
                CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=exec_addr)
                _, output, _ = CommandOperation.execute_command_with_error(
                    cmd=f'ls {constants.HEADER_BIN_OUTPUT}', cmd_execute_address=exec_addr
                )
                if 'header' in output:
                    file = output.strip('\n').strip()
                    return f'{constants.HEADER_BIN_OUTPUT}{file}'
                else:
                    log.info('加头失败')
            else:
                if "_fw.txt" in constants.FW_TXT0:
                    fw_bin = constants.FW_BIN
                    cmd = f"cd {constants.SM23SIGN_DIR}; sh {constants.USER_ADD_HEADER} {constants.FW_TXT0} {fw_bin} ioc sxe2_x86 {subdeviceid} { deviceid} 0x4116177F"
                if "_fw2.txt" in constants.FW_TXT1:
                    fw_bin = constants.FW_BIN1
                    cmd2 = f"cd {constants.SM23SIGN_DIR}; sh {constants.USER_ADD_HEADER} {constants.FW_TXT1} {fw_bin} ioc sxe2_x86 {subdeviceid} { deviceid} 0x4116177F"
                if "_fw3.txt" in constants.FW_TXT2:
                    fw_bin = constants.FW_BIN2
                    cmd3 = f"cd {constants.SM23SIGN_DIR}; sh {constants.USER_ADD_HEADER} {constants.FW_TXT2} {fw_bin} ioc sxe2_x86 {subdeviceid} { deviceid} 0x4116177F"
                if "_fw4.txt" in constants.FW_TXT3:
                    fw_bin = constants.FW_BIN3
                    cmd4 = f"cd {constants.SM23SIGN_DIR}; sh {constants.USER_ADD_HEADER} {constants.FW_TXT3} {fw_bin} ioc sxe2_x86 {subdeviceid} { deviceid} 0x4116177F"
                if "_fw5.txt" in constants.FW_TXT4:
                    fw_bin = constants.FW_BIN4
                    cmd5 = f"cd {constants.SM23SIGN_DIR}; sh {constants.USER_ADD_HEADER} {constants.FW_TXT4} {fw_bin} ioc sxe2_x86 {subdeviceid} { deviceid} 0x4116177F"
                if "_fw6.txt" in constants.FW_TXT5:
                    fw_bin = constants.FW_BIN5
                    cmd6 = f"cd {constants.SM23SIGN_DIR}; sh {constants.USER_ADD_HEADER} {constants.FW_TXT5} {fw_bin} ioc sxe2_x86 {subdeviceid} { deviceid} 0x4116177F"
                cmd_list = [cmd, cmd2, cmd3, cmd4, cmd5, cmd6]
                for cmd in cmd_list:
                    CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=exec_addr)
                    _, output, _ = CommandOperation.execute_command_with_error(
                        cmd=f'ls {constants.HEADER_BIN_OUTPUT}', cmd_execute_address=exec_addr
                    )
                    if 'header' in output:
                        file = output.strip('\n').strip()
                        return f'{constants.HEADER_BIN_OUTPUT}{file}'
                    else:
                        log.info('加头失败')

        else:
            cmd = f"cd {constants.SM23SIGN_DIR}; sh {constants.USER_ADD_HEADER} {constants.FW_TXT} {bin_path} ioc sxe2_x86 {subdeviceid} { deviceid} 0x4116177F"
            CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=exec_addr)
            _, output, _ = CommandOperation.execute_command_with_error(
                cmd=f'ls {constants.HEADER_BIN_OUTPUT}', cmd_execute_address=exec_addr
            )
            if 'header' in output:
                file = output.strip('\n').strip()
                return f'{constants.HEADER_BIN_OUTPUT}{file}'
            else:
                log.info('加头失败')


    @classmethod
    def make_pkg(cls, header_bin_lst, exec_addr):
        CommandOperation.execute_command_with_error(
            cmd=f'mkdir {constants.TMP_PKG_PATH}', cmd_execute_address=exec_addr
        )
        if len(header_bin_lst) == 1:
            bin_path_all = ''.join(header_bin_lst)
        else:
            bin_path_all = ' '.join(header_bin_lst)
        CommandOperation.execute_command_with_error(
            cmd=f'cd {constants.TMP_PKG_PATH}; python2 {constants.PS3_MAKE_PACKAGE} {bin_path_all}',
            cmd_execute_address=exec_addr
        )
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd=f'find {constants.TMP_PKG_PATH}{constants.PS3_IMAGE_PACKAGE}', cmd_execute_address=exec_addr
        )
        if 'No such file or directory' in output:
            return
        else:
            return constants.TMP_PKG_PATH + constants.PS3_IMAGE_PACKAGE

    @classmethod
    def modify_xml(cls, para, value, path, exec_addr):
        cmd = rf"sed -i 's/\(<{para}[^>]*>\)[^<]*\(<\/{para}>\)/\1{value}\2/' {path}"
        CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=exec_addr)
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd=f'cat {path} | grep {value}', cmd_execute_address=exec_addr
        )
        if value in output:
            return True
        else:
            return False

    @classmethod
    def modify_xml_new(cls, para, value, path, exec_addr):
        """
       author: qiaopy
       date: 2025.11.10
       description: 对传入的para 进行值的修改
       :param para: 字符串类型，类似“sxe2User-reg-reginfo-cfgreg1”
       :param value: 要修改的数据
       :param path:
       :param exec_addr
       例如修改“sxe2User-reg-reginfo-cfgreg1”为1，传参为改para=“sxe2User-reg-reginfo-cfgreg1”,value=1,path,.exec_addr
       四
       :return: 修改后的nvdata数据信息，list格式
       """
        para_list = para.split('-')
        cmd = rf"""sed -i '/<{para_list[0]}>/,/<\/{para_list[0]}>/{{ /<{para_list[1]}>/,/<\/{para_list[1]}>/{{ /<{para_list[2]}>/,/<\/{para_list[2]}>/{{ s/\(<{para_list[3]}[^>]*>\)[^<]*\(<\/{para_list[3]}>\)/\1{value}\2/ }} }} }}' {path}"""
        CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=exec_addr)
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd=f'cat {path} | grep {value}', cmd_execute_address=exec_addr
        )
        if value in output:
            return True
        else:
            return False

    @classmethod
    def bmc_dc_reset_host(cls, caller_class, insmod_pf_ko=True):
        """
        author: yibo.gao
        date  : 2026.04.16
        description: dc重启主机,加载驱动
        :param caller_class: 调用类
        :param insmod_pf_ko: 重启后,是否加载主机驱动
        """
        server_ip, _ = CommonOperation.get_nic_logical_ip()
        bmc_ip = CommandLineArgsParse.get_server_bmc_ip()
        # CommonOperation.concat_test_steps("通过BMC执行DC 重启动作")
        uname = CommandLineArgsParse.get_server_bmc_uname()
        passwd = CommandLineArgsParse.get_server_bmc_passwd()
        log.info("准备进行DC重启")
        reboot_result = HostOperation.host_bmc_reboot(
            ssh_ip=server_ip, bmc_ip=bmc_ip, uname=uname, passwd=passwd, force_check=False)
        if reboot_result != RtnStatusEnum.SUCCESS.value:
            CommonOperation.create_bug_problem(
                caller_class, key_word="通过BMC对主机进行DC重启",
                description_word=f'DC重启失败，请检查环境')
        log.info("主机DC重启成功")
        if insmod_pf_ko:
            log.info("加载PF驱动")
            status = CommonOperation.modprobe_driver(constants.DRV_SCGBE_PF, CmdExecuteAdressEnum.SERVER.value)
            if not status:
                CommonOperation.create_bug_problem(
                    caller_class, key_word="主机DC重启后,加载PF驱动",
                    description_word=f'驱动加载失败,请检查环境')
            log.info("驱动加载成功")
        return

    @classmethod
    def reboot_host(cls, caller_class, insmod_pf_ko=True):
        """
        author: yibo.gao
        date  : 2026.04.16
        description: reboot 重启主机,加载驱动
        :param caller_class: 调用类
        :param insmod_pf_ko: 重启后,是否加载主机驱动
        """
        server_ip, _ = CommonOperation.get_nic_logical_ip()
        log.info("准备进行OS Reboot")
        reboot_result = HostOperation.host_reboot(ssh_ip=server_ip)

        if reboot_result != RtnStatusEnum.SUCCESS.value:
            CommonOperation.create_bug_problem(
                caller_class, key_word="OS Reboot对主机重启",
                description_word=f'重启失败，请检查环境')
        log.info("主机Reboot成功")
        if insmod_pf_ko:
            log.info("加载PF驱动")
            status = CommonOperation.modprobe_driver(constants.DRV_SCGBE_PF, CmdExecuteAdressEnum.SERVER.value)
            if not status:
                CommonOperation.create_bug_problem(
                    caller_class, key_word="主机Reboot后,加载PF驱动",
                    description_word=f'驱动加载失败,请检查环境')
            log.info("驱动加载成功")
        return

class CliOperation(object):
    rtn_code = 0
    server_exec = CmdExecuteAdressEnum.SERVER.value
    new_version = ''

    @classmethod
    def cli_command_execute(cls, caller_class, device: str, cmd: str, result: bool = True, rtn_flag: bool = False,
                            exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> str:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据device 执行cli命令
        :param caller_class: 调用者的类
        :param device: 设备名称BDF or ib_dev_name
        :param cmd: cli命令
        :param result: 命令执行结果
        :param rtn_flag: True,返回执行结果，False,不返回执行结果
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        if device is not None:
            cmd = f'{constants.SCGBECLI64} -d {device} {cmd}'
        else:
            cmd = cmd
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                if rtn_flag:
                    return rtn_outputs
            else:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                if rtn_flag:
                    return rtn_outputs
                CommonOperation.create_bug_problem(caller_class, key_word='cli命令',
                                                   description_word=f'{cmd}执行失败',
                                                   expect_info=f'{cmd}执行成功',
                                                   result_info=f'{rtn_outputs}')
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                if rtn_flag:
                    return rtn_outputs
            else:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                if rtn_flag:
                    return rtn_outputs
                CommonOperation.create_bug_problem(caller_class, key_word='cli命令',
                                                   description_word=f'{cmd}执行成功',
                                                   expect_info=f'{cmd}执行失败',
                                                   result_info=f'{rtn_outputs}')

    @classmethod
    def kill_ps(cls, caller_class, ps_name: str, exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jinbo.zhang
        date  : 2024.10.31
        description: 执行kill -9 ps_id
        :param caller_class: 调用者的类
        :param ps_name: 线程名称
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        # 获取名为ps_name的程序的pid
        cmd_ps = f"ps -elf |grep {ps_name}|grep -v grep |head -n 1 |awk {{'printf $4'}}"
        while True:
            _, ps_s, _ = CommandOperation.execute_command_with_error(
                cmd=cmd_ps, cmd_execute_address=exec_addr)
            ps_s.strip('\n')
            if ps_s == '':
                break
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd=f"kill -9 {ps_s}",
                                                                                         cmd_execute_address=exec_addr)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:kill -9 {ps_s}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:kill -9 {ps_s}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='执行kill -9命令',
                                                   description_word=f'kill -9 {ps_s}执行失败',
                                                   expect_info=f'kill -9 {ps_s}执行成功',
                                                   result_info=f'{rtn_outputs}')

    @classmethod
    def create_vf(cls, caller_class, device_bdf: str, vf_count: int = 1, result: bool = True,
                  exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jinbo.zhang
        date  : 2024.10.31
        description: 根据pf创建vf
        :param caller_class: 调用者的类
        :param device_bdf: 设备名称dev_bdf
        :param vf_count: vf数量
        :param result: 命令执行结果
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        bus_info = cls.get_cli_show_info(caller_class, device_bdf, 'BDF(bus/dev/func)')
        cmd = f'echo {vf_count} > /sys/bus/pci/devices/{bus_info}/sriov_numvfs'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='创建VF',
                                                   description_word=f'{cmd}执行失败',
                                                   expect_info=f'{cmd}执行成功',
                                                   result_info=f'{rtn_outputs}')
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='创建VF',
                                                   description_word=f'{cmd}执行成功',
                                                   expect_info=f'{cmd}执行失败',
                                                   result_info=f'{rtn_outputs}')

    @classmethod
    def ethtool_S(cls, caller_class, device: str, result: bool = True, exec_count: int = 1,
                  exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jinbo.zhang
        date  : 2024.10.31
        description: 执行ethtool -S <device_name>
        :param caller_class: 调用者的类
        :param device: 设备名称dev_name
        :param result: 命令执行结果
        :param exec_count: 命令执行次数，默认1次
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        cmd = f'ethtool -S {device}'
        for i in range(exec_count):
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd,
                                                                                         cmd_execute_address=exec_addr)
            if result:
                if rtn_code == RtnStatusEnum.SUCCESS.value:
                    log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                else:
                    log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                    CommonOperation.create_bug_problem(caller_class, key_word='执行ethtool -S命令',
                                                       description_word=f'{cmd}执行失败',
                                                       expect_info=f'{cmd}执行成功',
                                                       result_info=f'{rtn_outputs}')
            else:
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                else:
                    log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                    CommonOperation.create_bug_problem(caller_class, key_word='执行ethtool -S命令',
                                                       description_word=f'{cmd}执行成功',
                                                       expect_info=f'{cmd}执行失败',
                                                       result_info=f'{rtn_outputs}')

    @classmethod
    def ethtool_s_advertise(cls, caller_class, device: str, key: str, result: bool = True, exec_count: int = 1,
                            exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jinbo.zhang
        date  : 2024.10.31
        description: 执行ethtool -S <device_name>
        :param caller_class: 调用者的类
        :param device: 设备名称dev_name
        :param key: 设置配置值
        :param result: 命令执行结果
        :param exec_count: 命令执行次数，默认1次
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        cmd = f'ethtool -s {device} advertise {key}'
        for i in range(exec_count):
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd,
                                                                                         cmd_execute_address=exec_addr)
            if result:
                if rtn_code == RtnStatusEnum.SUCCESS.value:
                    log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                else:
                    log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                    CommonOperation.create_bug_problem(caller_class, key_word='执行ethtool -s advertise命令',
                                                       description_word=f'{cmd}执行失败',
                                                       expect_info=f'{cmd}执行成功',
                                                       result_info=f'{rtn_outputs}')
            else:
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                else:
                    log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                    CommonOperation.create_bug_problem(caller_class, key_word='执行ethtool -s advertise命令',
                                                       description_word=f'{cmd}执行成功',
                                                       expect_info=f'{cmd}执行失败',
                                                       result_info=f'{rtn_outputs}')

    @classmethod
    def cli_show_mfg_info(cls, caller_class, device: str, result: bool = True,
                          exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> dict:
        """
        author: jinbo.zhang
        date  : 2024.10.25
        description: 根据device show mfginfo
        :param caller_class: 调用者的类
        :param device: 设备名称BDF or ib_dev_name
        :param result: 命令执行结果
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        cmd = f'{constants.SCGBECLI64} -d {device} show mfginfo'
        result_dict = {}
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                line_list = rtn_outputs.splitlines()
                for line in line_list:
                    if '=' not in line and 'Key' not in line:
                        re_result = re.fullmatch(r'\s*\|(.+)\|(.+)\|\s*', line)
                        if re_result:
                            if 'Mac Address 0' in re_result.group(1):
                                result_dict['Mac Address 0'] = re_result.group(2).strip()
                            elif 'Mac Address 1' in re_result.group(1):
                                result_dict['Mac Address 1'] = re_result.group(2).strip()
                            else:
                                result_dict[re_result.group(1).strip()] = re_result.group(2).strip()
            else:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli获取vpd信息',
                                                   description_word='cli show mfginfo失败',
                                                   expect_info=f'cli show mfginfo成功',
                                                   result_info=f'{rtn_outputs}')
            return result_dict
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli获取vpd信息',
                                                   description_word='cli show mfginfo成功',
                                                   expect_info=f'cli show mfginfo失败',
                                                   result_info=f'{rtn_outputs}')

    @classmethod
    def cli_set_autologpoutput_switch(cls, caller_class, device: str, switch: bool = True, result: bool = True,
                                      exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
                                      check_ignore: bool = False) -> None:
        """
        author: jinbo.zhang
        date  : 2024.10.25
        description: 根据device show mfginfo
        :param caller_class: 调用者的类
        :param device: 设备名称BDF or ib_dev_name
        :param switch: 设置日志自动导出开关状态，True为on, False为off
        :param result: 命令执行结果
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        if switch:
            cmd = f'{constants.SCGBECLI64} -d {device} set autologoutput state=on'
        else:
            cmd = f'{constants.SCGBECLI64} -d {device} set autologoutput state=off'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if check_ignore:
            return
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功')
            else:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli命令设置autologoutput开关',
                                                   description_word=f'{cmd}执行失败',
                                                   expect_info=f'{cmd}执行成功',
                                                   result_info=f'{rtn_outputs}')
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli命令设置autologoutput开关',
                                                   description_word=f'{cmd}执行成功',
                                                   expect_info=f'{cmd}执行失败',
                                                   result_info=f'{rtn_outputs}')

    @classmethod
    def cli_set_mfginfo(cls, caller_class, device: str, pn: str = None, sn: str = None, mfgDate: str = None,
                        reworkDate: str = None, pv: str = None, vn: str = None, pdn: str = None, AssetTag: str = None,
                        macAddr0: str = None, macAddr1: str = None, macAddr2: str = None, macAddr3: str = None,
                        macAddr4: str = None, mainMode: str = None, auxmode: str = None, Hotpc: str = None,
                        Coldpc: str = None, Hotaisle: str = None, Coldaisle: str = None, Hotac: str = None,
                        Coldac: str = None, PowerLevel: str = None, TempLevel: str = None,
                        result: bool = True, exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jinbo.zhang
        date  : 2024.10.25
        description: 根据scgbecli -d <device> set mfginfo <[PN=<value>] | [SN=<value>] | [mfgDate=<yyyy-mm-dd>] |
                                                        [reworkDate=<yyyy-mm-dd>] | [PV=<value>] |
                                                        [VN=<value>] | [PDN=<value>] |
                                                        [AssetTag=<value>] | [macAddr0=<value>] |
                                                        [macAddr1=<value>] | [macAddr2=<value>] |
                                                        [macAddr3=<value>] | [macAddr4=<value>] |
                                                        [mainMode=<value>] | [auxmode=<value>] |
                                                        [Hotpc=<value>] | [Coldpc=<value>] |
                                                        [Hotaisle=<value>] | [Coldaisle=<value>] |
                                                        [Hotac=<value>] | [Coldac=<value>] |
                                                        [PowerLevel=<value>] | [TempLevel=<value>]>
        """
        cmd = f'{constants.SCGBECLI64} -d {device} set mfginfo '
        if pn:
            cmd += f'PN={pn} '
        if sn:
            cmd += f'SN={sn} '
        if mfgDate:
            cmd += f'mfgDate={mfgDate} '
        if reworkDate:
            cmd += f'reworkDate={reworkDate} '
        if pv:
            cmd += f'PV={pv} '
        if vn:
            cmd += f'VN={vn} '
        if pdn:
            cmd += f'PDN={pdn} '
        if AssetTag:
            cmd += f'AssetTag={AssetTag} '
        if macAddr0:
            cmd += f'macAddr0={macAddr0} '
        if macAddr1:
            cmd += f'macAddr1={macAddr1} '
        if macAddr2:
            cmd += f'macAddr2={macAddr2} '
        if macAddr3:
            cmd += f'macAddr3={macAddr3} '
        if macAddr4:
            cmd += f'macAddr4={macAddr4} '
        if mainMode:
            cmd += f'mainMode={mainMode} '
        if auxmode:
            cmd += f'auxmode={auxmode} '
        if Hotpc:
            cmd += f'Hotpc={Hotpc} '
        if Coldpc:
            cmd += f'Coldpc={Coldpc} '
        if Hotaisle:
            cmd += f'Hotaisle={Hotaisle} '
        if Coldaisle:
            cmd += f'Coldaisle={Coldaisle} '
        if Hotac:
            cmd += f'Hotac={Hotac} '
        if Coldac:
            cmd += f'Coldac={Coldac} '
        if PowerLevel:
            cmd += f'PowerLevel={PowerLevel} '
        if TempLevel:
            cmd += f'TempLevel={TempLevel} '
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli命令设置mfginfo',
                                                   description_word=f'{cmd}执行失败',
                                                   expect_info=f'{cmd}执行成功',
                                                   result_info=f'{rtn_outputs}')
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli命令设置mfginfo',
                                                   description_word=f'{cmd}执行成功',
                                                   expect_info=f'{cmd}执行失败',
                                                   result_info=f'{rtn_outputs}')

    @classmethod
    def cli_show_fwreset(cls, caller_class, device: str, result: bool = True,
                         exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jinbo.zhang
        date  : 2024.10.25
        description: 根据device show fwreset
        :param caller_class: 调用者的类
        :param device: 设备名称BDF or ib_dev_name
        :param result: 命令执行结果
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        cmd = f'{constants.SCGBECLI64} -d {device} show fwreset'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli show fwreset',
                                                   description_word=f'{cmd}执行失败',
                                                   expect_info=f'{cmd}执行成功',
                                                   result_info=f'{rtn_outputs}')
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli show fwreset',
                                                   description_word=f'{cmd}执行成功',
                                                   expect_info=f'{cmd}执行失败',
                                                   result_info=f'{rtn_outputs}')

    @classmethod
    def cli_show_termlog(cls, caller_class, device: str, show_all: bool = False, filepath: str = None,
                         result: bool = True, rtn_flag: bool = False,
                         exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
                         check_ignore: bool = False) -> str:
        """
        author: jinbo.zhang
        date  : 2024.10.26
        description: scgbecli -d <device> show termlog [all] [file=<filepath>]
        :param caller_class: 调用者的类
        :param device: 设备名称BDF or ib_dev_name
        :param show_all: 导出日志大小， show_all = True,导出全部日志， show_all = False,导出部分日志
        :param filepath: 导出到文件
        :param result: 命令执行结果
        :param rtn_flag: 是否返回返回值
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        cmd = f'{constants.SCGBECLI64} -d {device} show termlog'
        if show_all:
            cmd += ' all'
        if filepath is not None:
            if ';' in filepath:
                filter_path = filepath.split(';')[0].strip()
                relative_path = filepath.split(';')[1].strip()
                cmd = f'cd {filter_path}; ' + cmd + f'file={relative_path}'
            else:
                cmd += f' file={filepath}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if check_ignore:
            return ''
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功')
            else:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli show termlog',
                                                   description_word=f'{cmd}执行失败',
                                                   expect_info=f'{cmd}执行成功',
                                                   result_info=f'{rtn_outputs}')
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败')
                if rtn_flag:
                    return rtn_outputs
            else:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli show termlog',
                                                   description_word=f'{cmd}执行成功',
                                                   expect_info=f'{cmd}执行失败',
                                                   result_info=f'{rtn_outputs}')

    @classmethod
    def get_termlog_last_time(cls, caller_class, bus_info: str) -> str:
        """
        author: jianghe
        date  : 2025.09.30
        return: 查询termlog的最新时间
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} show termlog'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
        found = re.findall('([0-9]{4}/[0-9]{2}/[0-9]{2}\.[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6})', out)
        if not found:
            CommonOperation.create_bug_problem(caller_class, key_word='termlog',
                                               description_word=f'termlog没有正确的时间格式，返回的信息是{out}')
        log.info(f'termlog中找到的时间戳是{found[-1]}')
        return found[-1]

    @classmethod
    def check_termlog_keywords(cls, caller_class, bus_info: str, filter_time, keywords, check_exist: bool = True):
        """
        author: jianghe
        date  : 2025.09.30
        return: 检查termlog在filter_time之后是否存在预期的关键字
        """
        file = f'termlog_all_' + time.strftime('%y%m%d%H%M%S')
        cls.cli_show_termlog(cls, bus_info, show_all=True, filepath=file)
        cmd = f'cat {file}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
        lines = out.strip().split('\n')
        found_flag = False
        for line in lines:
            found = re.findall('([0-9]{4}/[0-9]{2}/[0-9]{2}\.[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6})', line)
            if found:
                if found[0] > filter_time:
                    if keywords in line:
                        log.info(f'在{line}找到了关键字{keywords}')
                        found_flag = True
                        break
            else:
                log.error(f'没有正确的时间格式：{line}')
                # CommonOperation.create_bug_problem(caller_class, key_word='termlog',
                #                                    description_word=f'没有找到正确的时间格式')
        if not found_flag:
            CommonOperation.create_bug_problem(caller_class, key_word='termlog',
                                               description_word=f'termlog在{filter_time}后没有找到预期的关键字{keywords}，'
                                                                f'检查的文件是{file}')
        else:
            FileOperation.delete_file(file, match_flag=False)

    @classmethod
    def cli_upload_coredump(cls, caller_class, device: str, filepath: str = None, result: bool = True,
                            rtn_flag: bool = False, exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
                            check_ignore: bool = False) -> str:
        """
        author: jinbo.zhang
        date  : 2024.10.31
        description: scgbecli -d <device> upload coredump file=<filename>
        :param caller_class: 调用者的类
        :param device: 设备名称BDF or ib_dev_name
        :param filepath: 导出到文件
        :param result: 命令执行结果
        :param rtn_flag: 是否返回返回值
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        if filepath is None:
            filepath = '/root/coredump.log'
        if ';' in filepath:
            filter_path = filepath.split(';')[0].strip()
            relative_path = filepath.split(';')[1].strip()
            cmd = f'cd {filter_path}; {constants.SCGBECLI64} -d {device} upload coredump file={relative_path}'
        else:
            cmd = f'{constants.SCGBECLI64} -d {device} upload coredump file={filepath}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if check_ignore:
            return ''
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli upload coredump',
                                                   description_word=f'{cmd}执行失败',
                                                   expect_info=f'{cmd}执行成功',
                                                   result_info=f'{rtn_outputs}')
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                if rtn_flag:
                    return rtn_outputs
            else:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli upload coredump',
                                                   description_word=f'{cmd}执行成功',
                                                   expect_info=f'{cmd}执行失败',
                                                   result_info=f'{rtn_outputs}')

    @classmethod
    def wait_upgrdsyncstate(cls, caller_class, device: str,
                            exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2026.04.08
        return: 无返回值
        """
        update_flag = False
        for i in range(60):
            cmd = f'{constants.SCGBECLI64} -d {device} custom sxe2 upgrdsyncstate versionlineswitch=0'
            rtn_code, rtn_upgrade_utputs, rtn_err = CommandOperation.execute_command_with_error(cmd,
                                                                                                cmd_execute_address=exec_addr)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_upgrade_utputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_upgrade_utputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli upgrade fw',
                                                   description_word=f'{cmd}执行失败',
                                                   expect_info=f'{cmd}执行成功',
                                                   result_info=f'{rtn_upgrade_utputs}')
            if "run state: 0" in rtn_upgrade_utputs:
                update_flag = True
                break
            else:
                time.sleep(5)
        if not update_flag:
            CommonOperation.create_bug_problem(caller_class, key_word='300s内重复检查分区同步，仍然显示正在覆盖中，报bug',
                                               description_word=f'300s内，分区一直显示覆盖中',
                                               expect_info=f'300s内，分区覆盖完成',
                                               result_info=f'300s内，分区一直显示覆盖中')

    @classmethod
    def cli_upgrade_fw(cls, caller_class, device: str, is_relative_path: bool = False, upgrade_file_path: str = None,
                       noverchk: bool = False, result: bool = True, rtn_flag: bool = False,
                       exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value, check_ignore: bool = False,
                       need_update_flag=True) -> str:
        """
        author: jinbo.zhang
        date  : 2024.10.31
        description: scgbecli -d <device> upgrade file=<filepath> [noverchk]
        return: 无返回值
        """
        if need_update_flag:
            update_flag = False
            for i in range(60):
                cmd = f'{constants.SCGBECLI64} -d {device} custom sxe2 upgrdsyncstate versionlineswitch=0'
                rtn_code, rtn_upgrade_utputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
                if rtn_code == RtnStatusEnum.SUCCESS.value:
                    log.info(f'command:{cmd}执行成功, outputs:{rtn_upgrade_utputs}, error:{rtn_err}')
                else:
                    log.info(f'command:{cmd}执行失败, outputs:{rtn_upgrade_utputs}, error:{rtn_err}')
                    CommonOperation.create_bug_problem(caller_class, key_word='cli upgrade fw',
                                                       description_word=f'{cmd}执行失败',
                                                       expect_info=f'{cmd}执行成功',
                                                       result_info=f'{rtn_upgrade_utputs}')
                if "run state: 0" in rtn_upgrade_utputs:
                    update_flag = True
                    break
                else:
                    time.sleep(5)
            if update_flag:
                if upgrade_file_path is None:
                    upgrade_file_path = CliOperation.get_pkg_path(device)
                filepath, file_name = upgrade_file_path.rsplit('/', 1)
                if RtnStatusEnum.SUCCESS.value != FileOperation.file_path_exists(upgrade_file_path):
                    log.info(f"升级包{upgrade_file_path}不存在，请在固定路径下放置对应升级包")
                    caller_class.bug_title = f'升级包{upgrade_file_path}不存在，请在固定路径下放置对应升级包"'
                    exit(ExitCodeEnum.EXIT_SKIP.value)
                if is_relative_path:
                    cmd = f'cd {filepath}; {constants.SCGBECLI64} -d {device} upgrade file={file_name}'
                else:
                    cmd = f'{constants.SCGBECLI64} -d {device} upgrade file={upgrade_file_path}'
                if noverchk:
                    cmd += ' noverchk'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
                if check_ignore:
                    return
                if result:
                    if rtn_code == RtnStatusEnum.SUCCESS.value:
                        log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                    else:
                        log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                        CommonOperation.create_bug_problem(caller_class, key_word='cli upgrade fw',
                                                           description_word=f'{cmd}执行失败',
                                                           expect_info=f'{cmd}执行成功',
                                                           result_info=f'{rtn_outputs}')
                else:
                    if rtn_code != RtnStatusEnum.SUCCESS.value:
                        log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                        if rtn_flag:
                            return rtn_outputs
                    else:
                        log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                        CommonOperation.create_bug_problem(caller_class, key_word='cli upgrade fw',
                                                           description_word=f'{cmd}执行成功',
                                                           expect_info=f'{cmd}执行失败',
                                                           result_info=f'{rtn_outputs}')
            else:
                CommonOperation.create_bug_problem(caller_class, key_word='300s内重复检查分区同步，仍然显示正在覆盖中，报bug',
                                                   description_word=f'300s内，分区一直显示覆盖中',
                                                   expect_info=f'300s内，分区覆盖完成',
                                                   result_info=f'300s内，分区一直显示覆盖中')
        else:
            if upgrade_file_path is None:
                upgrade_file_path = CliOperation.get_pkg_path(device)
            filepath, file_name = upgrade_file_path.rsplit('/', 1)
            if RtnStatusEnum.SUCCESS.value != FileOperation.file_path_exists(upgrade_file_path):
                log.info(f"升级包{upgrade_file_path}不存在，请在固定路径下放置对应升级包")
                caller_class.bug_title = f'升级包{upgrade_file_path}不存在，请在固定路径下放置对应升级包"'
                exit(ExitCodeEnum.EXIT_SKIP.value)
            if is_relative_path:
                cmd = f'cd {filepath}; {constants.SCGBECLI64} -d {device} upgrade file={file_name}'
            else:
                cmd = f'{constants.SCGBECLI64} -d {device} upgrade file={upgrade_file_path}'
            if noverchk:
                cmd += ' noverchk'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd,
                                                                                         cmd_execute_address=exec_addr)
            if check_ignore:
                return
            if result:
                if rtn_code == RtnStatusEnum.SUCCESS.value:
                    log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                else:
                    log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                    CommonOperation.create_bug_problem(caller_class, key_word='cli upgrade fw',
                                                       description_word=f'{cmd}执行失败',
                                                       expect_info=f'{cmd}执行成功',
                                                       result_info=f'{rtn_outputs}')
            else:
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                    if rtn_flag:
                        return rtn_outputs
                else:
                    log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                    CommonOperation.create_bug_problem(caller_class, key_word='cli upgrade fw',
                                                       description_word=f'{cmd}执行成功',
                                                       expect_info=f'{cmd}执行失败',
                                                       result_info=f'{rtn_outputs}')

    @classmethod
    def get_keyword_value(cls, dict_info: dict, keyword: str = None) -> dict:
        """
        author: jinbo.zhang
        date  : 2024.10.28
        description: 获取字典中 keyword 对应的 value 内容
        :param dict_info: 要获取的内容所在的字典
        :param keyword: 要获取的内容的key
        return: 元组
        """
        dict_none = {}
        if keyword is None:
            keyword = 'System Overview'
        for key in dict_info:
            if key == keyword:
                # print(dict_info[key])
                return dict_info[key]
            else:
                if isinstance(dict_info[key], dict) and keyword in str(dict_info[key]):
                    return cls.get_keyword_value(dict_info[key], keyword)
        return dict_none

    @classmethod
    def get_all_devices_from_cli_show(cls, caller_class, exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> list:
        """
        author: jianghe
        date  : 20250904
        description: 获取卡下的device信息
        """
        device_list = []
        cmd = f'{constants.SCGBECLI64} show'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, rtn_code, rtn_outputs, rtn_err)
        for line in rtn_outputs.splitlines():
            found = re.findall('\|([0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}.[0-9a-f]{1})\s\|(.*)\|(.*)\|(.*)\|(.*)\|(.*)\|(.*)\|(.*)\|',line)
            if found:
                dev_info = {'Device': found[0][0].strip(),
                            'Mac Address': found[0][1].strip(),
                            'Network Name': found[0][2].strip(),
                            'Domain ID': found[0][3].strip(),
                            'BDF (bus/dev/func)': found[0][4].strip(),
                            'Link Speed': found[0][5].strip(),
                            'Firmware Version': found[0][6].strip(),
                            'OptionRom Version': found[0][7].strip()}
                device_list.append(dev_info)
        return device_list

        # device_list = []
        # cmd = f'{constants.SCGBECLI64} show j'
        # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        # CliOperation.check_cli_success(caller_class, cmd, rtn_code, rtn_outputs, rtn_err)
        # output_dict = eval(rtn_outputs)
        # response_dict = cls.get_keyword_value(output_dict, 'System Overview')
        # for key in response_dict.keys():
        #     if 'Controller' in key:
        #         device_list.extend(response_dict.get(key))
        # return device_list

    @classmethod
    def get_cli_show_info(cls, caller_class, device: str, prop: str = '', para: str = 'Device',
                          exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value, not_get: bool = False) -> str:
        """
       author: jinbo.zhang
       date  : 2024.10.28
       description: 执行/cx show 获取device 0 某一属性值
       :param caller_class: 调用者的类
       :param device: device name
       :param prop: 属性key
       :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
       :return: 返回属性值
       """
        device_list = []
        cmd = f'{constants.SCGBECLI64} show'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, rtn_code, rtn_outputs, rtn_err)
        for line in rtn_outputs.splitlines():
            found = re.findall(
                '\|([0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}.[0-9a-f]{1})\s\|(.*)\|(.*)\|(.*)\|(.*)\|(.*)\|(.*)\|(.*)\|',
                line)
            if found:
                dev_info = {'Device': found[0][0].strip(),
                            'Mac Address': found[0][1].strip(),
                            'Network Name': found[0][2].strip(),
                            'Domain ID': found[0][3].strip(),
                            'BDF (bus/dev/func)': found[0][4].strip(),
                            'Link Speed': found[0][5].strip(),
                            'Firmware Version': found[0][6].strip(),
                            'OptionRom Version': found[0][7].strip()}
                device_list.append(dev_info)
        get_value = ''
        for key in device_list:
            if device == key.get(para):
                get_value = key.get(prop)
        log.info(f'{device}: {prop} 的值 {get_value}获取成功')
        return get_value

        # cmd = f'{constants.SCGBECLI64} show j'
        # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        # CliOperation.check_cli_success(caller_class, cmd, rtn_code, rtn_outputs, rtn_err)
        # if not_get:
        #     return ''
        # output_dict = eval(rtn_outputs)
        # response_dict = cls.get_keyword_value(output_dict, 'System Overview')
        # # Device 0
        # device_list = response_dict.get('Controller 0')
        # get_value = ''
        # for key in device_list:
        #     if device == key.get(para):
        #         get_value = key.get(prop)
        # log.info(f'{device}: {prop} 的值 {get_value}获取成功')
        # return get_value

    @classmethod
    def check_cli_show_info(cls, caller_class, device: str, prop: str, exp: str,
                            exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,para: str = 'Device') -> str:
        """
       author: jianghe
       date  : 2025.05.29
       description: 检查cli show的字段值
       """
        cur = CliOperation.get_cli_show_info(caller_class, device, prop,exec_addr=exec_addr,para=para)
        if cur == exp:
            log.info(f'查询的{prop}与预期一致，是{exp}')
        else:
            log.error(f'查询的{prop}不符合预期，查出来是{cur}，期望是{exp}')
            CommonOperation.create_bug_problem(caller_class, key_word=f'FW',
                                               description_word=f'查询的{prop}不符合预期，查出来是{cur}，期望是{exp}')

    @classmethod
    def get_cli_show_device_list(cls, caller_class, exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> list:
        """
        author: jinbo.zhang
        date  : 2024.10.28
        description: 执行/cx show 获取device name
        :param caller_class: 调用者的类
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: 返回属性值
        """
        cmd = f'{constants.SCGBECLI64} show'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, rtn_code, rtn_outputs, rtn_err)
        found = re.findall('\|([0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}.[0-9a-f]{1})\s\|', rtn_outputs)
        return list(found)

        # cmd = f'{constants.SCGBECLI64} show j'
        # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        # if rtn_code == RtnStatusEnum.SUCCESS.value:
        #     log.info(f'命令{cmd}执行成功')
        #     output_dict = eval(rtn_outputs)
        #     response_dict = cls.get_keyword_value(output_dict, 'System Overview')
        #     bus_info_list = []
        #     for key in response_dict.keys():
        #         if 'Controller' in key:
        #             device_list = response_dict.get(key)
        #             for device_info in device_list:
        #                 bus_info_list.append(device_info.get('Device'))
        #     return bus_info_list
        # else:
        #     CommonOperation.create_bug_problem(caller_class, key_word='cli show 属性值获取',
        #                                        description_word=f'cli show 属性值获取失败',
        #                                        expect_info=f'cli show 属性值获取获取失败',
        #                                        result_info=f'{rtn_outputs}')

    @classmethod
    def get_cli_show_list_info(cls, caller_class, eth_name: str, prop: str,
                               exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> str:
        """
       author: jinbo.zhang
       date  : 2024.10.28
       description: 执行/cx show list获取Device List某一属性值
       :param caller_class: 调用者的类
       :param eth_name : port name ,eg:ens4f1
       :param prop: 属性key
       :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
       :return: 返回属性值
       """
        device_list = []
        cmd = f'{constants.SCGBECLI64} show list'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, rtn_code, rtn_outputs, rtn_err)
        for line in rtn_outputs.splitlines():
            found = re.findall('\|(.*)\|(.*)\|([0-9a-f]{2}:[0-9a-f]{2}.[0-9a-f]{1})\s\|(.*)\|', line)
            if found:
                dev_info = {'Ethernet Name': found[0][0].strip(),
                            'Domain ID': found[0][1].strip(),
                            'BDF': found[0][2].strip(),
                            'Mac Address': found[0][3].strip()}
                device_list.append(dev_info)
        get_value = ''
        for key in device_list:
            if eth_name == key.get('Ethernet Name'):
                get_value = key.get(prop)
        log.info(f'{eth_name}: {prop} 的值 {get_value}获取成功')
        return get_value

        # cmd = f'{constants.SCGBECLI64} show list j'
        # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        # log.info(rtn_outputs)
        # if rtn_code == RtnStatusEnum.SUCCESS.value:
        #     log.info(f'命令{cmd}执行成功')
        #     output_dict = eval(rtn_outputs)
        #     response_dict = cls.get_keyword_value(output_dict, 'Response Data')
        #     # Device 0
        #     device_list = response_dict.get('Device List')
        #     get_value = ''
        #     for key in device_list:
        #         if eth_name == key.get('Ethernet Name'):
        #             get_value = key.get(prop)
        #     log.info(f'{eth_name}: {prop} 的值 {get_value}获取成功')
        #     return get_value
        # else:
        #     CommonOperation.create_bug_problem(caller_class, key_word='cli show list属性值获取',
        #                                        description_word=f'cli show list属性值获取成功',
        #                                        expect_info=f'cli show list属性值获取获取失败',
        #                                        result_info=f'{rtn_outputs}')

    @classmethod
    def get_cli_show_flashinfo(cls, caller_class, device: str, prop: str,
                               exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> str:
        """
        author: jinbo.zhang
        date  : 2024.10.28
        description: 执行/cx show flashinfo获取Device flashinfo某一属性值
        :param caller_class: 调用者的类
        :param device: device
        :param prop: 属性key
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: 返回属性值
        """
        cmd = f'{constants.SCGBECLI64} -d {device} show flashinfo'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, rtn_code, rtn_outputs, rtn_err)
        return re.findall(f'\|{prop}\s*\|(.*)\|', rtn_outputs)[0].strip()

        # cmd = f'{constants.SCGBECLI64} -d {device} show flashinfo j'
        # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        # log.info(rtn_outputs)
        # if rtn_code == RtnStatusEnum.SUCCESS.value:
        #     log.info(f'命令{cmd}执行成功')
        #     output_dict = eval(rtn_outputs)
        #     response_dict = cls.get_keyword_value(output_dict, 'Response Data')
        #     # Device 0
        #     flashinfo = response_dict.get('Flash Info')
        #     get_value = ''
        #     for key in flashinfo:
        #         # log.info(key)
        #         if prop == key.get('Key'):
        #             get_value = key.get('Value')
        #     log.info(f'{prop}: value 的值 {get_value}获取成功')
        #     return get_value
        # else:
        #     CommonOperation.create_bug_problem(caller_class, key_word='CLI',
        #                                        description_word=f'cli show flashinfo属性值获取失败，返回信息是{rtn_outputs}')

    @classmethod
    def get_cli_show_uptime(cls, caller_class, device: str, prop: str,
                            exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> str:
        """
        author: jinbo.zhang
        date  : 2024.10.28
        description: 执行/cx show uptime获取Device uptime某一属性值
        :param caller_class: 调用者的类
        :param device: device
        :param prop: 属性key
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: 返回属性值
        """
        cmd = f'{constants.SCGBECLI64} -d {device} show uptime'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, rtn_code, rtn_outputs, rtn_err)
        return re.findall(f'\|{prop}\s*\|(.*)\|', rtn_outputs)[0].strip()

        # cmd = f'{constants.SCGBECLI64} -d {device} show uptime j'
        # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        # if rtn_code == RtnStatusEnum.SUCCESS.value:
        #     log.info(f'命令{cmd}执行成功')
        #     output_dict = eval(rtn_outputs)
        #     response_dict = cls.get_keyword_value(output_dict, 'Response Data')
        #     # Device 0
        #     uptimeinfo = response_dict.get('Time & Core Frequency')
        #     get_value = ''
        #     for key in uptimeinfo:
        #         # log.info(key)
        #         if prop == key.get('Key'):
        #             get_value = key.get('Value')
        #     get_value = get_value.replace('[h:m:s.usec]', '')
        #     log.info(f'{prop}: value 的值 {get_value}获取成功')
        #     return get_value
        # else:
        #     CommonOperation.create_bug_problem(caller_class, key_word='cli show uptime属性值获取',
        #                                        description_word=f'cli show uptime属性值获取失败',
        #                                        expect_info=f'cli show uptime属性值获取获取成功',
        #                                        result_info=f'{rtn_outputs}')

    @classmethod
    def check_sys_uptime(cls, caller_class, device: str, exp_time, type) -> None:
        """
       author: jianghe
       date  : 2025.05.19
       description: 检查网卡uptime，exp_time的格式是 0:08:14，MORE-期望时间大于卡uptime时间，LESS-期望时间小于卡uptime时间
       """
        cli_uptime = CliOperation.get_cli_show_uptime(cls, device, 'Device Up Time')
        cli_uptime = cli_uptime.strip(' [h:m:s.usec]').strip()
        cur_h, cur_m, cur_s = cli_uptime.split(':')
        exp_h, exp_m, exp_s = exp_time.split(':')

        if type == CompareType.More.value:
            if ((int(cur_h) < int(exp_h)) or
                    (int(cur_h) == int(exp_h) and int(cur_m) < int(exp_m)) or
                    (int(cur_h) == int(exp_h) and int(cur_m) == int(exp_m) and float(cur_s) < float(exp_s))):
                log.info(f'uptime检查成功，cli获取时间:{cli_uptime}, 小于期望时间:{exp_time}')
            else:
                CommonOperation.create_bug_problem(caller_class, key_word='uptime',
                                                   description_word=f'uptime检查成功，cli获取时间:{cli_uptime}, '
                                                                    f'不小于期望时间:{exp_time}')
        elif type == CompareType.Less.value:
            if ((int(exp_h) < int(cur_h)) or
                    (int(exp_h) == int(cur_h) and int(exp_m) < int(cur_m)) or
                    (int(exp_h) == int(cur_h) and int(exp_m) == int(cur_m) and float(exp_s) < float(cur_s))):
                log.info(f'uptime检查成功，cli获取时间:{cli_uptime}, 大于期望时间:{exp_time}')
            else:
                CommonOperation.create_bug_problem(caller_class, key_word='uptime',
                                                   description_word=f'uptime检查成功，cli获取时间:{cli_uptime}, '
                                                                    f'小于期望时间:{exp_time}')

    @classmethod
    def cli_show_fw_info(cls, caller_class, device: str, result: bool = True, rtn_flag: bool = False,
                         exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> str:
        """
        author: jinbo.zhang
        date  : 2024.10.29
        description: scgbecli -d <device> show fw
        :param caller_class: 调用者的类
        :param device: 设备名称BDF or ib_dev_name
        :param result: 命令执行结果
        :param rtn_flag: 是否返回返回值
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        cmd = f'{constants.SCGBECLI64} -d {device} show  fw '
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                if rtn_flag:
                    return rtn_outputs
            else:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli show fw',
                                                   description_word=f'{cmd}执行失败',
                                                   expect_info=f'{cmd}执行成功',
                                                   result_info=f'{rtn_outputs}')
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                if rtn_flag:
                    return rtn_outputs
            else:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli show termlog',
                                                   description_word=f'{cmd}执行成功',
                                                   expect_info=f'{cmd}执行失败',
                                                   result_info=f'{rtn_outputs}')

    @classmethod
    def get_cli_show_fw_info(cls, caller_class, device: str,
                             exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> dict:
        """
        author: jianghe
        date  : 2025.06.10
        description: 执行/cx show fw 获取属性值
        """
        prop_dict = {}
        # code review 2025/6/10 jhe: Rom Info的内容没有获取
        # prop_dict = {"FW Version": 0, "FW Release Date": 1, "Product Version": 2,
        #              "LEGACY": 0, "UEFI": 1,
        #              "Base GUID": 0, "Base MAC": 1}
        prop_list = ["FW Version", "FW Release Date", "Product Version", "Base UUID", "Base MAC"]
        cmd = f'{constants.SCGBECLI64} -d {device} show fw '
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, rtn_code, rtn_outputs, rtn_err)
        for prop in prop_list:
            prop_dict.update({prop: re.findall(f'\|{prop}\s*\|(.*)\|', rtn_outputs)[0].strip()})
        return prop_dict

    @classmethod
    def check_cli_show_fw_info(cls, caller_class, device: str, check_prop_dict,
                               exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jianghe
        date  : 2025.06.10
        description: 执行/cx show fw 获取属性值
        """
        fw_info = CliOperation.get_cli_show_fw_info(caller_class, device, exec_addr)
        for prop, exp in check_prop_dict.items():
            cur = fw_info.get(prop)
            if exp != cur:
                log.error(f'show fw中属性{prop}查出来与预期不一致，查出来是{cur}，期望是{exp}')
                CommonOperation.create_bug_problem(caller_class, key_word=f'FW',
                                                   description_word=f'查询的{prop}不符合预期，查出来是{cur}，期望是{exp}')
            else:
                log.info(f'show fw中属性{prop}查出来与预期一致，是{cur}')

    @classmethod
    def get_cli_show_fwreset_info(cls, caller_class, device: str,
                                  exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jianghe
        date  : 2025.06.09
        description: 执行/cx show fwreset
        """
        cmd = f'{constants.SCGBECLI64} -d {device} show fwreset '
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, rtn_code, rtn_outputs, rtn_err)
        exp_info_list = ['|0    |Core reset                     |Y       |N      |',
                         '|1    |PCIe reset                     |N       |N      |',
                         '|2    |Sys reset(PCIe and core reset) |Y       |Y      |']
        for exp_info in exp_info_list:
            if exp_info not in rtn_outputs:
                CommonOperation.create_bug_problem(caller_class, key_word='cli show fwreset属性值获取',
                                                   description_word=f'期望返回信息包含{exp_info}，但是实际没有，'
                                                                    f'返回信息是{rtn_outputs}')

        # cmd = f'{constants.SCGBECLI64} -d {device} show fwreset j '
        # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        # # print(rtn_outputs)
        # if rtn_code == RtnStatusEnum.SUCCESS.value:
        #     output_dict = eval(rtn_outputs)
        #     response_dict = cls.get_keyword_value(output_dict, 'Response Data')
        #     level_list = response_dict.get('Reset Types')
        #     exp_info_list = [{"Type": "0", "Info": "Core reset", "Support": "Y", "Default": "N"},
        #                      {"Type": "1", "Info": "PCIe reset", "Support": "N", "Default": "N"},
        #                      {"Type": "2", "Info": "Sys reset(PCIe and core reset)", "Support": "Y", "Default": "Y"}, ]
        #     if len(exp_info_list) != len(level_list):
        #         log.info(f'期望行数是{len(exp_info_list)}，实际是{len(level_list)}')
        #         CommonOperation.create_bug_problem(caller_class, key_word='cli show fwreset属性值获取',
        #                                            description_word=f'cli show fwreset属性值获取成功',
        #                                            expect_info=f'cli show fwreset属性值获取获取失败',
        #                                            result_info=f'{rtn_outputs}')
        #     for level_info in level_list:
        #         for exp_info in exp_info_list:
        #             if exp_info.get('Type') == level_info.get('Type'):
        #                 log.info(f"Type: {level_info.get('Type')}比较")
        #                 CliOperation.check_info_is_same(cls, level_info.get('Info'), exp_info.get('Info'))
        #                 CliOperation.check_info_is_same(cls, level_info.get('Support'), exp_info.get('Support'))
        #                 CliOperation.check_info_is_same(cls, level_info.get('Default'), exp_info.get('Default'))
        # else:
        #     CommonOperation.create_bug_problem(caller_class, key_word='cli show fwreset属性值获取',
        #                                        description_word=f'cli show fwreset属性值获取成功',
        #                                        expect_info=f'cli show fwreset属性值获取获取失败',
        #                                        result_info=f'{rtn_outputs}')

    @classmethod
    def cli_reset(cls, caller_class, device: str, para: str = 'type', reset_type: str = None, result: bool = True,
                  rtn_flag: bool = False, exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> str:
        """
        author: jinbo.zhang
        date  : 2024.10.26
        description: scgbecli -d <device> reset type=0/1/2
        :param caller_class: 调用者的类
        :param device: 设备名称BDF or ib_dev_name
        :param reset_type: Reset types: 0:Full chip reset
                                        1:Phy-less reset (keep network port active during reset)
                                        2: NIC only reset (for SoC devices)
        :param para: 参数
        :param result: 命令执行结果
        :param rtn_flag: 是否返回返回值
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        if reset_type is None:
            cmd = f'{constants.SCGBECLI64} -d {device} reset '
        else:
            cmd = f'{constants.SCGBECLI64} -d {device} reset {para}={reset_type} '
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli reset',
                                                   description_word=f'{cmd}执行失败',
                                                   expect_info=f'{cmd}执行成功',
                                                   result_info=f'{rtn_outputs}')
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                if rtn_flag:
                    return rtn_outputs
            else:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli reset',
                                                   description_word=f'{cmd}执行成功',
                                                   expect_info=f'{cmd}执行失败',
                                                   result_info=f'{rtn_outputs}')

    @classmethod
    def cli_show_flashinfo(cls, caller_class, device: str, result: bool = True, rtn_flag: bool = False,
                           exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value, check_ignore: bool = False) -> str:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据device show flashinfo
        :param caller_class: 调用者的类
        :param device: 设备名称BDF or ib_dev_name
        :param result: 命令执行结果
        :param rtn_flag
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        cmd = f'{constants.SCGBECLI64} -d {device} show flashinfo'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if check_ignore:
            return
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli show flashinfo',
                                                   description_word=f'{cmd}执行失败',
                                                   expect_info=f'{cmd}执行成功',
                                                   result_info=f'{rtn_outputs}')
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli show flashinfo',
                                                   description_word=f'{cmd}执行成功',
                                                   expect_info=f'{cmd}执行失败',
                                                   result_info=f'{rtn_outputs}')
        if rtn_flag:
            return rtn_outputs

    @classmethod
    def get_core_frequency(cls, bus_info: str) -> str:
        """
        author: jinbo.zhang
        date  : 2025.12.11
        description: 根据卡类型确定频率
        return: 无返回值
        """
        cmd = f'lspci -vvs {bus_info}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
        if '1ff2:0c22' in out or '1ff2:0c21' in out:  # ocpx2和pciex2
            return '1000.000000 MHz'
        elif '1ff2:0c24' in out:  # 10G衍生卡
            return '400.000000 MHz'
        else:
            return '1000.000000 MHz'

        # pf_count = 0
        # cmd = f'{constants.SCGBECLI64} show j'
        # code, out, err = CommandOperation.execute_command_with_error(cmd, cls.server_exec)
        # found = re.findall('\"Device\":\s*\"(.*)\"', out)
        # for bus_info_elem in found:
        #     if bus_info[:7] in bus_info_elem:
        #         pf_count += 1
        # if pf_count == 1:
        #     core_frequency = '1000.000000 MHz'
        # elif pf_count == 2:
        #     core_frequency = '666.000000 MHz'
        # elif pf_count == 4:
        #     core_frequency = '1000.000000 MHz'
        # else:
        #     core_frequency = ''
        #     CommonOperation.create_bug_problem(ScriptBase, key_word='cli show',
        #                                        description_word=f'没有获取到正确的pf个数，当前是{pf_count}')
        # return core_frequency

    @classmethod
    def cli_show_uptime(cls, caller_class, device: str, result: bool = True, rtn_flag: bool = False,
                        exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value, check_ignore=False) -> str:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据device show uptime
        :param caller_class: 调用者的类
        :param device: 设备名称BDF or ib_dev_name
        :param result: 命令执行结果
        :param rtn_flag
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        cmd = f'{constants.SCGBECLI64} -d {device} show uptime'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if check_ignore:
            return
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli show uptime',
                                                   description_word=f'{cmd}执行失败',
                                                   expect_info=f'{cmd}执行成功',
                                                   result_info=f'{rtn_outputs}')
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli show uptime',
                                                   description_word=f'{cmd}执行成功',
                                                   expect_info=f'{cmd}执行失败',
                                                   result_info=f'{rtn_outputs}')
        if rtn_flag:
            return rtn_outputs

    @classmethod
    def cli_get_cable(cls, caller_class, device: str, pageindex: int = None, offset: int = None, length: int = None,
                      result: bool = True, rtn_flag: bool = False,
                      exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value, check_ignore: bool = False) -> str:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据device show uptime
        :param caller_class: 调用者的类
        :param device: 设备名称BDF or ib_dev_name
        :param pageindex:
        :param offset:
        :param length:
        :param result: 命令执行结果
        :param rtn_flag
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        if pageindex is None and offset is None:
            cmd = f'{constants.SCGBECLI64} -d {device} get cable'
        else:
            if length is None:
                cmd = f'{constants.SCGBECLI64} -d {device} get cable pageindex={pageindex} offset={offset}'
            else:
                cmd = f'{constants.SCGBECLI64} -d {device} get cable pageindex={pageindex} offset={offset} length={length}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if check_ignore:
            return
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli get cable info',
                                                   description_word=f'{cmd}执行失败',
                                                   expect_info=f'{cmd}执行成功',
                                                   result_info=f'{rtn_outputs}')
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli get cable info',
                                                   description_word=f'{cmd}执行成功',
                                                   expect_info=f'{cmd}执行失败',
                                                   result_info=f'{rtn_outputs}')
        if rtn_flag:
            return rtn_outputs

    @classmethod
    def get_cli_get_cable(cls, caller_class, device: str, pageindex: int = None, offset: int = None, length: int = None,
                          exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.10.27
        description: 获取光模块信息
        """
        out = CliOperation.cli_get_cable(caller_class, device, pageindex, offset, length,
                                         rtn_flag=True, exec_addr=exec_addr)
        cable_read_dict = {}
        for line in out.split('\n'):
            found = re.findall('\|(.*)\s*\|(.*)\s*\|', line)
            if found:
                cable_read_dict.update({found[0][0].strip(): found[0][1].strip()})
        cable_read_dict.pop('Index')
        return cable_read_dict

    @classmethod
    def cli_set_lldp_switch(cls, caller_class, device: str, switch: bool = True, result: bool = True,
                            exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
                            check_ignore: bool = False, workmode: str = 'txrx') -> None:
        """
        author: jinbo.zhang
        date  : 2025.1.6
        description: 根据device set lldp state
        :param caller_class: 调用者的类
        :param device: 设备名称BDF or ib_dev_name
        :param switch: 设置lldp状态，True为on value=1, False为off value=0
        :param result: 命令执行结果
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        if switch:
            cmd = f'{constants.SCGBECLI64} -d {device} set lldp state=on workmode={workmode}'
        else:
            cmd = f'{constants.SCGBECLI64} -d {device} set lldp state=off workmode={workmode}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if check_ignore:
            return
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli命令设置lldp开关',
                                                   description_word=f'{cmd}执行失败',
                                                   expect_info=f'{cmd}执行成功',
                                                   result_info=f'{rtn_outputs}')
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            else:
                log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli命令设置lldp开关',
                                                   description_word=f'{cmd}执行成功',
                                                   expect_info=f'{cmd}执行失败',
                                                   result_info=f'{rtn_outputs}')

    @classmethod
    def cli_show_lldp(cls, caller_class, device: str, result: bool = True, get_state: bool = False,
                      exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> str:
        """
        author: jinbo.zhang
        date  : 2025.1.6
        description: 根据device show lldp
        :param caller_class: 调用者的类
        :param device: 设备名称BDF or ib_dev_name
        :param result: 命令执行结果
        :param get_state: True 返回ll状态value
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        cmd = f'{constants.SCGBECLI64} -d {device} show lldp'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功,符合预期')
            else:
                log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word='cli show lldp',
                                                   description_word=f'{cmd}执行失败',
                                                   expect_info=f'{cmd}执行成功',
                                                   result_info=f'{rtn_outputs}')
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败, 符合预期')
            else:
                log.info(f'command:{cmd}执行成功, 不符合预期')
                CommonOperation.create_bug_problem(caller_class, key_word='cli show lldp',
                                                   description_word=f'{cmd}执行成功',
                                                   expect_info=f'{cmd}执行失败',
                                                   result_info=f'{rtn_outputs}')
        if get_state:
            return rtn_outputs

    @classmethod
    def get_lldp_state(cls, caller_class, device: str, exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> dict:
        """
        author: jinbo.zhang
        date  : 2025.1.6
        description: 根据device 获取 lldp状态
        :param caller_class: 调用者的类
        :param device: 设备名称BDF or ib_dev_name
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: {"State": "On", "Workmode": "TXRX"}
        """
        props = {}
        cmd = f'{constants.SCGBECLI64} -d {device} show lldp'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd,
                                                                                     cmd_execute_address=exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, rtn_code, rtn_outputs, rtn_err)
        props.update({'State': re.findall('\|State\s*\|(.*)\|', rtn_outputs)[0].strip()})
        props.update({'Workmode': re.findall('\|Workmode\s*\|(.*)\|', rtn_outputs)[0].strip()})
        return props

        # props = {}
        # cmd = f'{constants.SCGBECLI64} -d {device} show lldp j'
        # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd,
        #                                                                              cmd_execute_address=exec_addr)
        # if rtn_code == RtnStatusEnum.SUCCESS.value:
        #     log.info(f'命令{cmd}执行成功')
        #     output_dict = eval(rtn_outputs)
        #     response_dict = cls.get_keyword_value(output_dict, 'Response Data')
        #     # Device 0
        #     lldpinfo = response_dict.get('Lldp')
        #     get_value = ''
        #     for key in lldpinfo:
        #         # log.info(key)
        #         get_value = key.get('Value')
        #         get_key = key.get('Key')
        #         props.update({get_key: get_value})
        #     return props
        # else:
        #     CommonOperation.create_bug_problem(caller_class, key_word='cli show lldp状态获取',
        #                                        description_word=f'cli show lldp状态获取成功',
        #                                        expect_info=f'cli show lldp状态获取获取失败',
        #                                        result_info=f'{rtn_outputs}')

    @classmethod
    def cls_get_lldp_state_and_workmode(cls, caller_class, device: str, exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: yibo.gao
        date  : 2025.11.18
        description: 根据device 获取 lldp状态
        :param caller_class: 调用者的类
        :param device: 设备名称BDF or ib_dev_name
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: "On", "TXRX"
        """
        res_dict = cls.get_lldp_state(caller_class=caller_class, device=device, exec_addr=exec_addr)
        return res_dict["State"], res_dict["Workmode"]

    @classmethod
    def check_lldp_state(cls, caller_class, device: str, switch:[str, bool] = False, workmode: str = 'TXRX',
                         exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jinbo.zhang
        date  : 2025.1.6
        description: 根据device show lldp
        :param caller_class: 调用者的类
        :param device: 设备名称BDF or ib_dev_name
        :param switch: lldp开关情况
        :param workmode: LLDP工作模式, tx, rx, txrx
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        lldp_dict = cls.get_lldp_state(caller_class, device, exec_addr=exec_addr)
        lldp_state = lldp_dict['State']
        lldp_mode = lldp_dict['Workmode']
        if lldp_state == 'On':
            result = True
        else:
            result = False
        if type(switch) == str:
            if switch.lower() == "on":
                switch = True
            else:
                switch = False
        if switch == result and workmode.lower() == lldp_mode.lower():
            log.info(f"lldp 符合预期为{lldp_state} {lldp_mode}")
        else:
            CommonOperation.create_bug_problem(caller_class, key_word='lldp',
                                               description_word=f'lldp期望是{switch}，{workmode}，'
                                                                f'实际是{lldp_state} {lldp_mode}')

    @classmethod
    def check_value_diff(cls, caller_class, cur_value, expect_value, diff) -> None:
        """
        author: jinbo.zhang
        date  : 2024.10.26
        description: 检查两个值的差值
        return: 无返回值
        """
        if (abs(float(cur_value)) - abs(float(expect_value))) < diff:
            log.info(f'cur是{cur_value}，exp是{expect_value}，差值小于{diff}，符合预期')
        else:
            CommonOperation.create_bug_problem(caller_class, key_word=f"cli命令检查失败",
                                               description_word=f'cur是{cur_value}，exp是{expect_value}，差值大于{diff}')

    @classmethod
    def check_info_is_same(cls, caller_class, result_info, expect_info, contain: bool = False,
                           result: bool = True) -> None:
        """
        author: jinbo.zhang
        date  : 2024.10.26
        description: 检查前后信息是否一致
        :param caller_class: 调用者的类
        :param result_info:
        :param expect_info:
        :param contain: in
        :param result: result=Ture,info1和info2相同，result=False ,info1和info2不同
        return: 无返回值
        """
        if result:
            if contain:
                if expect_info in result_info or result_info in expect_info:
                    log.info(f"实际值:{result_info}和预期信息:{expect_info}相同")
                else:
                    log.info(f"实际值:{result_info}和预期信息:{expect_info}不同")
                    CommonOperation.create_bug_problem(caller_class, key_word=f"cli命令检查失败",
                                                       description_word='cli命令检查失败',
                                                       expect_info='cli命令返回值实际与预期一致',
                                                       result_info=f'result_info：{result_info}, '
                                                                   f'expect_info: {expect_info}')
            else:
                if type(expect_info) == list:
                    if result_info in expect_info:
                        log.info(f"实际值:{result_info}和预期信息:{expect_info}相同")
                    else:
                        log.info(f"实际值:{result_info}和预期信息:{expect_info}不同")
                        CommonOperation.create_bug_problem(caller_class, key_word=f"cli命令检查失败",
                                                           description_word='cli命令检查失败',
                                                           expect_info='cli命令返回值实际与预期一致',
                                                           result_info=f'result_info：{result_info}, '
                                                                       f'expect_info: {expect_info}')
                else:
                    if result_info == expect_info:
                        log.info(f"实际值:{result_info}和预期信息:{expect_info}相同")
                    else:
                        log.info(f"实际值:{result_info}和预期信息:{expect_info}不同")
                        CommonOperation.create_bug_problem(caller_class, key_word=f"cli命令检查失败",
                                                           description_word='cli命令检查失败',
                                                           expect_info='cli命令返回值实际与预期一致',
                                                           result_info=f'result_info：{result_info}, '
                                                                       f'expect_info: {expect_info}')
        else:
            if result_info != expect_info:
                log.info(f"实际值:{result_info}和预期信息:{expect_info}不同，符合预期")
            else:
                log.info(f"实际值:{result_info}和预期信息:{expect_info}一致，不符合预期")
                CommonOperation.create_bug_problem(caller_class, key_word=f"cli命令检查成功",
                                                   description_word='cli命令检查成功',
                                                   expect_info='cli命令返回值实际与预期不同',
                                                   result_info=f'result_info：{result_info}, expect_info: {expect_info}')

    @classmethod
    def check_error_message(cls, caller_class, error_message: str, cmd_output: str) -> None:
        """
        author: jinbo.zhang
        date  : 2024.10.26
        description: 检查error message是否正确
        :param caller_class: 调用者的类
        :param error_message: error message 描述
        :param cmd_output: 命令回显
        return: 无返回值
        """
        if error_message in cmd_output:
            log.info(f"error message '{error_message}' is right")
        else:
            log.info(f"error message '{error_message}' is wrong")
            CommonOperation.create_bug_problem(caller_class, key_word=f"error message '{cmd_output}' is wrong",
                                               description_word='错误提示信息有误',
                                               expect_info='错误提示信息正确',
                                               result_info='错误提示信息有误')

    @classmethod
    def cli_get_soctempthreshold(cls, caller_class, device: str, result: bool = True, rtn_flag: bool = False,
                                 prop: str = None, check_result: bool = True,
                                 exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> str:
        """
        author: jinbo.zhang
        date  : 2025.3.5
        description: 执行/cx get soctempthreshold获取Device soc温度阈值
        :param caller_class: 调用者的类
        :param device: bdf or rdma_name
        :param prop: 属性key
        :param result: 命令执行结果预期
        :param rtn_flag: 是否返回结果
        :param prop: 属性key
        :param check_result: 是否检查结果，默认检查
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: 返回属性值
        """
        cmd = f'{constants.SCGBECLI64} -d {device} get soctempthreshold'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd,
                                                                                     cmd_execute_address=exec_addr)
        if prop is None:
            if check_result:
                if result:
                    if rtn_code == RtnStatusEnum.SUCCESS.value:
                        log.info(f'command:{cmd}执行成功符合预期')
                    else:
                        log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                        CommonOperation.create_bug_problem(caller_class, key_word='cli get soctempthreshold',
                                                           description_word=f'{cmd}执行失败',
                                                           expect_info=f'{cmd}执行成功',
                                                           result_info=f'{rtn_outputs}')
                else:
                    if rtn_code != RtnStatusEnum.SUCCESS.value:
                        log.info(f'command:{cmd}执行失败符合预期')
                    else:
                        log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                        CommonOperation.create_bug_problem(caller_class, key_word='cli get soctempthreshold',
                                                           description_word=f'{cmd}执行成功',
                                                           expect_info=f'{cmd}执行失败',
                                                           result_info=f'{rtn_outputs}')
            else:
                # 如果不做命令结果判断，会返回rtn_code
                cls.rtn_code = rtn_code
            if rtn_flag:
                return rtn_outputs
        else:
            CliOperation.check_cli_success(cls, cmd, rtn_code, rtn_outputs, rtn_err)
            return re.findall(f'\|{prop}\s*\|(.*)\|', rtn_outputs)[0].strip()

        # cmd = f'{constants.SCGBECLI64} -d {device} get soctempthreshold'
        # cmd_j = f'{constants.SCGBECLI64} -d {device} get soctempthreshold j'
        # if prop is None:
        #     rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd,
        #                                                                                  cmd_execute_address=exec_addr)
        #     if check_result:
        #         if result:
        #             if rtn_code == RtnStatusEnum.SUCCESS.value:
        #                 log.info(f'command:{cmd}执行成功符合预期')
        #             else:
        #                 log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        #                 CommonOperation.create_bug_problem(caller_class, key_word='cli get soctempthreshold',
        #                                                    description_word=f'{cmd}执行失败',
        #                                                    expect_info=f'{cmd}执行成功',
        #                                                    result_info=f'{rtn_outputs}')
        #         else:
        #             if rtn_code != RtnStatusEnum.SUCCESS.value:
        #                 log.info(f'command:{cmd}执行失败符合预期')
        #             else:
        #                 log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
        #                 CommonOperation.create_bug_problem(caller_class, key_word='cli get soctempthreshold',
        #                                                    description_word=f'{cmd}执行成功',
        #                                                    expect_info=f'{cmd}执行失败',
        #                                                    result_info=f'{rtn_outputs}')
        #     else:
        #         # 如果不做命令结果判断，会返回rtn_code
        #         cls.rtn_code = rtn_code
        #     if rtn_flag:
        #         return rtn_outputs
        # else:
        #     rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd_j,
        #                                                                                  cmd_execute_address=exec_addr)
        #     if rtn_code == RtnStatusEnum.SUCCESS.value:
        #         log.info(f'命令{cmd}执行成功')
        #         output_dict = eval(rtn_outputs)
        #         response_dict = cls.get_keyword_value(output_dict, 'Response Data')
        #         # Device 0
        #         soctempthreshold = response_dict.get('Soc Temp Threshold')
        #         get_value = ''
        #         for key in soctempthreshold:
        #             if prop == key.get('Key'):
        #                 get_value = key.get('Value')
        #         log.info(f'{prop}: value 的值 {get_value}获取成功')
        #         return get_value
        #     else:
        #         CommonOperation.create_bug_problem(caller_class, key_word='cli get soctempthreshold属性值获取',
        #                                            description_word=f'cli get soctempthreshold属性值获取成功',
        #                                            expect_info=f'cli get soctempthreshold属性值获取获取失败',
        #                                            result_info=f'{rtn_outputs}')

    @classmethod
    def cli_set_soctempthreshold(cls, caller_class, device: str, warning_high: str, warning_low: str,
                                 critical_high: str, critical_low: str, fatal_high: str, fatal_low: str,
                                 result: bool = True, check_result: bool = True,
                                 exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> str:
        """
       author: jinbo.zhang
       date  : 2025.3.5
       description: 执行/cx set soctempthreshold设置Device soc温度阈值
       :param caller_class: 调用者的类
       :param device: bdf or rdma_name
       :param warning_high:
       :param warning_low:
       :param critical_high:
       :param critical_low:
       :param fatal_high:
       :param fatal_low:
       :param result: 命令执行结果预期
       :param check_result: 是否检查结果，默认检查
       :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
       :return: 返回属性值
       """
        warning_high = warning_high.replace(' C', '')
        warning_low = warning_low.replace(' C', '')
        critical_high = critical_high.replace(' C', '')
        critical_low = critical_low.replace(' C', '')
        fatal_high = fatal_high.replace(' C', '')
        fatal_low = fatal_low.replace(' C', '')
        cmd = f'{constants.SCGBECLI64} -d {device} set soctempthreshold warninghigh={warning_high} warninglow={warning_low} ' \
              f'criticalhigh={critical_high} criticallow={critical_low} fatalhigh={fatal_high} fatallow={fatal_low}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if check_result:
            if result:
                if rtn_code == RtnStatusEnum.SUCCESS.value:
                    log.info(f'command:{cmd}执行成功')
                else:
                    log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                    CommonOperation.create_bug_problem(caller_class, key_word='cli命令设置soc温度阈值',
                                                       description_word=f'{cmd}执行失败',
                                                       expect_info=f'{cmd}执行成功',
                                                       result_info=f'{rtn_outputs}')
            else:
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.info(f'command:{cmd}执行失败符合预期')
                else:
                    log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                    CommonOperation.create_bug_problem(caller_class, key_word='cli命令设置soc温度阈值成功',
                                                       description_word=f'{cmd}执行成功',
                                                       expect_info=f'{cmd}执行失败',
                                                       result_info=f'{rtn_outputs}')
        else:
            # 如果不做命令结果判断，会返回rtn_code
            cls.rtn_code = rtn_code

    @classmethod
    def cli_set_sfptempthreshold(cls, caller_class, device: str, warning_high: str, warning_low: str,
                                 critical_high: str, critical_low: str, result: bool = True, check_result: bool = True,
                                 exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> str:
        """
       author: jinbo.zhang
       date  : 2025.3.5
       description: 执行/cx set sfptempthreshold设置Device sfp温度阈值
       :param caller_class: 调用者的类
       :param device: bdf or rdma_name
       :param warning_high:
       :param warning_low:
       :param critical_high:
       :param critical_low:
       :param result: 命令执行结果预期
       :param check_result: 是否检查结果，默认检查
       :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
       :return: 返回属性值
       """
        cmd = f'{constants.SCGBECLI64} -d {device} set sfptempthreshold warninghigh={warning_high} warninglow={warning_low} ' \
              f'criticalhigh={critical_high} criticallow={critical_low}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if check_result:
            if result:
                if rtn_code == RtnStatusEnum.SUCCESS.value:
                    log.info(f'command:{cmd}执行成功')
                else:
                    log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                    CommonOperation.create_bug_problem(caller_class, key_word='cli命令设置sfp温度阈值',
                                                       description_word=f'{cmd}执行失败',
                                                       expect_info=f'{cmd}执行成功',
                                                       result_info=f'{rtn_outputs}')
            else:
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.info(f'command:{cmd}执行失败符合预期')
                else:
                    log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
                    CommonOperation.create_bug_problem(caller_class, key_word='cli命令设置sfp温度阈值成功',
                                                       description_word=f'{cmd}执行成功',
                                                       expect_info=f'{cmd}执行失败',
                                                       result_info=f'{rtn_outputs}')
        else:
            # 如果不做命令结果判断，会返回rtn_code
            cls.rtn_code = rtn_code

    @classmethod
    def cli_get_sfptempthreshold(cls, caller_class, device: str, prop: str = None,
                                 exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> str:
        """
       author: jinbo.zhang
       date  : 2025.3.5
       description: 执行/cx show cable ddm获取sfp温度阈值
       :param caller_class: 调用者的类
       :param device: bdf or rdma_name
       :param prop: 属性key
       :param result: 命令执行结果预期
       :param rtn_flag: 是否返回结果
       :param prop: 属性key
       :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
       :return: 返回属性值
       """
        cmd = f"{constants.SCGBECLI64} -d {device} show cable ddm"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, rtn_code, rtn_outputs, rtn_err)
        found = re.findall(f'\|{prop}\s*\|([0-9-]*)\sC\s*\|', rtn_outputs)
        if found:
            return found[0].strip()
        else:
            return ''

    @classmethod
    def driver_insmod_or_rmmod(cls, device_driver: str, insmod: bool = False, rmmod: bool = False,
                               exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        if rmmod:
            rtn = CommonOperation.rmmod_driver(device_driver, exec_addr, force=True)
            if rtn:
                log.info(f'驱动卸载成功')
            else:
                log.info(f'驱动卸载失败')
                CommonOperation.create_bug_problem(cls, key_word=f'驱动卸载',
                                                   description_word=f'驱动卸载',
                                                   expect_info=f'驱动卸载成功',
                                                   result_info=f'驱动卸载失败')
        if insmod:
            rtn = CommonOperation.modprobe_driver(device_driver, exec_addr)
            if rtn:
                log.info(f'驱动加载成功')
            else:
                log.info(f'驱动加载失败')
                CommonOperation.create_bug_problem(cls, key_word=f'驱动加载',
                                                   description_word=f'驱动加载',
                                                   expect_info=f'驱动加载成功',
                                                   result_info=f'驱动加载失败')

    @classmethod
    def cli_get_show_prop(cls, caller_class, bdf, prop: str = '',
                          exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> str:
        """
        author: jianghe
        date  : 2025.05.12
        description: 获取show的属性值
        """
        cmd = f"{constants.SCGBECLI64} -d {bdf} show"
        code, out, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        found = re.findall(f'{prop}\s*=\s*(.*)', out)
        if found:
            return found[0]
        else:
            return ''

    @classmethod
    def cli_get_mfginfo_prop(cls, caller_class, bdf, prop: str = '',
                             exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
                             not_get: bool = False, check_ignore: bool = False) -> str:
        """
        author: jianghe
        date  : 2025.05.09
        description: 获取mfginfo的属性值，例子CliOperation.cli_get_mfginfo_prop(cls, cls.server_bus_info, 'Mac Address 0')
        """
        cmd = f"{constants.SCGBECLI64} -d {bdf} show mfginfo"
        code, out, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if check_ignore:
            return None
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        if not_get:
            return None
        found = re.findall(f'\|{prop}\s*\|(.*)\|', out)
        if found:
            return found[0].strip()
        else:
            return ''

    @classmethod
    def cli_get_mfginfo_prop_list(cls, caller_class, bdf, prop_dict: dict,
                                  exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> dict:
        """
        author: jianghe
        date  : 2025.06.11
        description: 获取mfginfo的属性值
        """
        cmd = f"{constants.SCGBECLI64} -d {bdf} show mfginfo"
        code, out, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        if 'Board Info' not in out:
            return None
        part_com_header = out[:out.index('Board Info')]
        part_board_info = out[out.index('Board Info'): out.index('Product Info')]
        if 'Record Info' in out:
            part_product_info = out[out.index('Product Info'): out.index('Record Info')]
            part_record_info = out[out.index('Record Info'):]
        else:
            part_product_info = out[out.index('Product Info'):]
            part_record_info = ""
        for part, key_values in prop_dict.items():
            for key in key_values.keys():
                if part == 'CommonHeader Info':
                    found = re.findall(f'\|{key}\s*\|(.*)\|', part_com_header)
                    if found:
                        prop_dict[part][key] = found[0].strip()
                    else:
                        prop_dict[part][key] = None
                if part == 'Board Info':
                    found = re.findall(f'\|{key}\s*\|(.*)\|', part_board_info)
                    if found:
                        prop_dict[part][key] = found[0].strip()
                    else:
                        prop_dict[part][key] = None
                if part == 'Product Info':
                    found = re.findall(f'\|{key}\s*\|(.*)\|', part_product_info)
                    if found:
                        prop_dict[part][key] = found[0].strip()
                    else:
                        prop_dict[part][key] = None
                if part == 'Record Info':
                    find_str = key.replace("(", "\(")
                    find_str = find_str.replace(")", "\)")
                    found = re.findall(f'\|{find_str}\s*\|(.*)\|', part_record_info)
                    if found:
                        prop_dict[part][key] = found[0].strip()
                    else:
                        # print(f"error, [{key}] 没获取到")
                        prop_dict[part][key] = None
        return prop_dict

    @classmethod
    def check_mfginfo_prop(cls, caller_class, bdf, prop, exp_value,
                           exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jianghe
        date  : 2025.05.09
        description: 检查mfginfo的属性值
        """
        cur = cls.cli_get_mfginfo_prop(caller_class, bdf, prop, exec_addr)
        if cur == exp_value:
            log.info(f'show mfginfo中属性{prop}的值与期望一致，是{cur}')
        else:
            log.error(f'show mfginfo中属性{prop}的值与期望不一致，期望是{exp_value}，实际是{cur}')
            CommonOperation.create_bug_problem(
                caller_class, key_word=f'CLI',
                description_word=f'show mfginfo中属性{prop}的值与期望不一致，期望是{exp_value}，实际是{cur}')

    @classmethod
    def check_mfginfo_mul_props(cls, caller_class, bdf, prop_exp_value_dict: dict,
                                exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jianghe
        date  : 2025.05.09
        description: 检查mfginfo的属性值
        """
        cmd = f"{constants.SCGBECLI64} -d {bdf} show mfginfo"
        code, out, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        for prop, exp_value in prop_exp_value_dict.items():
            found = re.findall(f'\|{prop}\s*\|(.*)\|', out)
            if found:
                if prop == 'UUID' or prop == 'Controller 1 UDID \(if applicable\)':
                    if found[0].strip().endswith(exp_value):
                        log.info(f'show mfginfo中属性{prop}的值与期望一致，是{exp_value}')
                    else:
                        log.error(f'show mfginfo中属性{prop}的值与期望不一致，期望是{exp_value}，实际是{found}')
                        CommonOperation.create_bug_problem(
                            caller_class, key_word=f'CLI',
                            description_word=f'show mfginfo中属性{prop}的值与期望不一致，期望是{exp_value}，实际是{found}')
                else:
                    if len(found) == 1 and found[0].strip() == exp_value:
                        log.info(f'show mfginfo中属性{prop}的值与期望一致，是{exp_value}')
                    # elif len(found) > 1 and found[0].strip() == exp_value and found[1].strip() == exp_value:
                    #     log.info(f'show mfginfo中属性{prop}的值与期望一致，是{exp_value}')
                    elif len(found) > 1:
                        if prop == 'Serial Number':
                            if ((found[0].strip() == exp_value and found[1].strip() == exp_value) or
                                    (found[0].strip() == 'Serial' and found[1].strip() == 'Serialn')):
                                log.info(f'show mfginfo中属性{prop}的值与期望一致，是{exp_value}')
                        else:
                            if found[0].strip() == exp_value and found[1].strip() == exp_value:
                                log.info(f'show mfginfo中属性{prop}的值与期望一致，是{exp_value}')
                    else:
                        log.info(f'命令{cmd}的返回信息是{code}\n{out}\n{err}')
                        log.error(f'show mfginfo中属性{prop}的值与期望不一致，期望是{exp_value}，实际是{found}')
                        CommonOperation.create_bug_problem(
                            caller_class, key_word=f'CLI',
                            description_word=f'show mfginfo中属性{prop}的值与期望不一致，期望是{exp_value}，实际是{found}')
            else:
                log.info(f'命令{cmd}的返回信息是{code}\n{out}\n{err}')
                log.error(f'show mfginfo中没找到属性{prop}')
                CommonOperation.create_bug_problem(
                    caller_class, key_word=f'CLI',
                    description_word=f'show mfginfo中没找到属性{prop}')

    @classmethod
    def check_cli_success(cls, caller_class, cmd, code, out, err, reverse: bool = False) -> None:
        """
        author: jianghe
        date:   2025.05.10
        description: 校验cli的命令是否执行成功
        :return: 无返回值
        """
        if not reverse:
            if code == RtnStatusEnum.SUCCESS.value:
                log.info(f'{cmd}命令执行成功')
            else:
                log.error(f'{cmd}返回的错误信息是{code}\n{out}\n{err}')
                CommonOperation.create_bug_problem(caller_class, key_word=f'CLI',
                                                   description_word=f'{cmd}命令执行失败')
        else:
            if code != RtnStatusEnum.SUCCESS.value:
                log.info(f'{cmd}命令执行失败，符合预期')
            else:
                log.error(f'{cmd}命令执行成功，预期失败，返回的信息是{code}\n{out}\n{err}')
                CommonOperation.create_bug_problem(caller_class, key_word=f'CLI',
                                                   description_word=f'{cmd}命令执行成功')

    @classmethod
    def make_mfg_bin(cls, caller_class, mfg_csv, new_mfg_bin, exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.09.11
        description: 升级mfg.bin
        """
        if CommonOperation.is_fpga():
            csv2bin_py_path = f'/root/sxetest/publish_version/debuginfo/sxe2_fw_fpga/cfgTools/'
            mfg_h = '/root/sxetest/publish_version/debuginfo/sxe2_fw_fpga/cfgTools/mfg.h'
        else:
            csv2bin_py_path = f'/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/cfgTools/'
            mfg_h = '/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/cfgTools/mfg.h'
        cmd = f'cd {csv2bin_py_path};python2 csv2bin.py -t sxe2 -R {mfg_csv} -B {new_mfg_bin} -H {mfg_h}  -v 300 -A 8'
        CommonOperation.execute_command_with_check(caller_class, cmd, exec_addr)

    @classmethod
    def download_mfg(cls, caller_class, bdf, file: str = None, exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
                     check_ignore: bool = False) -> None:
        """
        author: jianghe
        date  : 2025.05.12
        description: 升级mfg.bin
        """
        if file is None:
            # file = constants.MFG_BIN
            file = CliOperation.get_mfg_bin_file(bdf)
        cmd = f"{constants.SCGBECLI64} -d {bdf} download mfg file={file}"
        code, out, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if check_ignore:
            return
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)

    @classmethod
    def get_exp_mfginfo(cls, exp_type: int = 0) -> dict:
        """
        author: jianghe
        date  : 2025.05.12
        description: 获取mfginfo配置，0-标卡默认值，1-OCP卡默认值，2-修改配置后期望值-OCP，3-修改配置后期望值-非OCP
        """
        default_mfg_info = {'Language Code': '0x19',
                            'Vendor Name': 'manu',
                            'Product Name': 'prdu',
                            'Part Number': 'pn',
                            'Serial Number': 'Serial',
                            'Part Version': '',
                            'Asset Tag': 'at',
                            'Mfg Date': '1995-12-31',
                            'Rework Date': '1995-12-31',
                            'Board Trace Num': '',
                            'Board Assembly': '',
                            'UUID': '0000000000000000',
                            'Mac Address 0': ''}
        default_mfg_info_ocp = {'Language Code': '0x19',
                                'Vendor Name': 'manu',
                                'Product Name': 'prdu',
                                'Part Number': 'pn',
                                'Serial Number': 'Serial',
                                'Part Version': '',
                                'Asset Tag': 'at',
                                'Mfg Date': '1995-12-31',
                                'Rework Date': '1995-12-31',
                                'Board Trace Num': '',
                                'Board Assembly': '',
                                'UUID': '0000000000000000',
                                'Mac Address 0': '',
                                'Is End': '0x1',
                                'Record Len': '0x80',
                                'Record Type': '0xC0',
                                'Manufacturer ID': '7FA60',
                                'OCP NIC 3.0 FRU OEM record version': '0x1',
                                'Card max power \(in watts\) in main \(S0\) mode': '0x19',
                                'Card max power \(in watts\) in aux \(S5\) mode': '0x9',
                                'Hot aisle card cooling tier with passive cables or RJ45': '0x8',
                                'Cold aisle card cooling tier with passive cables or RJ45': '0x8',
                                'Card active/passive cooling': '0x0',
                                'Hot aisle standby airflow requirement': '0xFA',
                                'Cold aisle standby airflow requirement': '0xC8',
                                'UART configuration 1 secondary connector': '0x0 0x0 0x0',
                                'UART configuration 2 secondary connector': '0x0 0x0 0x0',
                                'USB present primary connector': '0x0',
                                'Manageability Type': 'RBT + MCTP Type',
                                'FRU write protection mechanism': '0x20',
                                'Programming mode power state supported': '0x1',
                                'Hot aisle card cooling tier with active cables': '0x8',
                                'Cold aisle card cooling tier with active cables': '0x8',
                                'Transceiver reference power level': '0x1',
                                'Transceiver reference temperature level': '0x46',
                                'Card thermal tier with local fan fail': '0x0',
                                'Number of physical controllers \(N\)': '0x1',
                                'Controller 1 UDID \(if applicable\)': '0100000000000000000000000000000A',
                                'Controller 2 UDID \(if applicable\)': '0200000000000000000000000000000B',
                                'Controller 3 UDID \(if applicable\)': '0300000000000000000000000000000C',
                                'Controller 4 UDID \(if applicable\)': '0400000000000000000000000000000D',
                                'Controller 5 UDID \(if applicable\)': '0500000000000000000000000000000E',
                                'Controller 6 UDID \(if applicable\)': '060A0C0D000000000000000000070809'}
        test_mfg_info_ocp = {'Language Code': '0x19',
                             'Vendor Name': 'vn',
                             'Product Name': 'pdn',
                             'Part Number': 'pn',
                             'Serial Number': 'sn',
                             'Part Version': 'pv',
                             'Asset Tag': 'AssetTag',
                             'Mfg Date': '2025-01-01',
                             'Rework Date': '2025-01-01',
                             'Board Trace Num': '',
                             'Board Assembly': '',
                             'UUID': '122233445512',
                             'Mac Address 0': '12:22:33:44:55:12',
                             'Mac Address 1': '12:22:33:44:55:11',
                             'Mac Address 2': '12:22:33:44:55:22',
                             'Mac Address 3': '12:22:33:44:55:33',
                             'Mac Address 4': '12:22:33:44:55:44',
                             'Is End': '0x1',
                             'Record Len': '0x80',
                             'Record Type': '0xC0',
                             'Manufacturer ID': '7FA60',
                             'OCP NIC 3.0 FRU OEM record version': '0x1',  # 特殊字符.不需要特殊处理
                             'Card max power \(in watts\) in main \(S0\) mode': '0x0',  # 特殊字符(需要加\
                             'Card max power \(in watts\) in aux \(S5\) mode': '0xFF',
                             'Hot aisle card cooling tier with passive cables or RJ45': '0xA',
                             'Cold aisle card cooling tier with passive cables or RJ45': '0x14',
                             'Card active/passive cooling': '0x0',
                             'Hot aisle standby airflow requirement': '0x1E',
                             'Cold aisle standby airflow requirement': '0x28',
                             'UART configuration 1 secondary connector': '0x0 0x0 0x0',
                             'UART configuration 2 secondary connector': '0x0 0x0 0x0',
                             'USB present primary connector': '0x0',
                             'Manageability Type': 'RBT + MCTP Type',
                             'FRU write protection mechanism': '0x20',
                             'Programming mode power state supported': '0x1',
                             'Hot aisle card cooling tier with active cables': '0x32',
                             'Cold aisle card cooling tier with active cables': '0x3C',
                             'Transceiver reference power level': '0x46',
                             'Transceiver reference temperature level': '0x50',
                             'Card thermal tier with local fan fail': '0x0',
                             'Number of physical controllers \(N\)': '0x1',
                             'Controller 1 UDID \(if applicable\)': '122233445512',
                             'Controller 2 UDID \(if applicable\)': '0200000000000000000000000000000B',
                             'Controller 3 UDID \(if applicable\)': '0300000000000000000000000000000C',
                             'Controller 4 UDID \(if applicable\)': '0400000000000000000000000000000D',
                             'Controller 5 UDID \(if applicable\)': '0500000000000000000000000000000E',
                             'Controller 6 UDID \(if applicable\)': '060A0C0D000000000000000000070809'}
        test_mfg_info = {'Language Code': '0x19',
                         'Vendor Name': 'vn',
                         'Product Name': 'pdn',
                         'Part Number': 'pn',
                         'Serial Number': 'sn',
                         'Part Version': 'pv',
                         'Asset Tag': 'AssetTag',
                         'Mfg Date': '2025-01-01',
                         'Rework Date': '2025-01-01',
                         'Board Trace Num': '',
                         'Board Assembly': '',
                         'UUID': '122233445512',
                         'Mac Address 0': '12:22:33:44:55:12',
                         'Mac Address 1': '12:22:33:44:55:11',
                         'Mac Address 2': '12:22:33:44:55:22',
                         'Mac Address 3': '12:22:33:44:55:33',
                         'Mac Address 4': '12:22:33:44:55:44'}
        max_mfg_info_ocp = {'Language Code': '0xFF',
                            'Vendor Name': 'manu',
                            'Product Name': 'prdn',
                            'Part Number': 'pn',
                            'Serial Number': 'Serialn',
                            'Part Version': '~ Aa',
                            'Asset Tag': '~!',
                            'Mfg Date': '10162-02-14',
                            'Rework Date': '10162-02-14',
                            'Board Trace Num': 'Aa~ AAAAAAAAAAAA',
                            'Board Assembly': 'Aa~ AAAAAAAAAAAA',
                            'UUID': 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF',
                            'Mac Address 0': 'ff:ff:ff:ff:ff:ff',
                            'Mac Address 1': 'ff:ff:ff:ff:ff:fe',
                            'Mac Address 2': 'ff:ff:ff:ff:ff:fd',
                            'Mac Address 3': 'ff:ff:ff:ff:ff:fc',
                            'Mac Address 4': 'ff:ff:ff:ff:ff:fb',
                            'Is End': '0x1',
                            'Record Len': '0x80',
                            'Record Type': '0xC0',
                            'Manufacturer ID': 'FFFFFF',
                            'OCP NIC 3.0 FRU OEM record version': '0xFF',  # 特殊字符.不需要特殊处理
                            'Card max power \(in watts\) in main \(S0\) mode': '0xFF',  # 特殊字符(需要加\
                            'Card max power \(in watts\) in aux \(S5\) mode': '0xFF',
                            'Hot aisle card cooling tier with passive cables or RJ45': '0xFF',
                            'Cold aisle card cooling tier with passive cables or RJ45': '0xFF',
                            'Card active/passive cooling': '0xFF',
                            'Hot aisle standby airflow requirement': '0xFFFF',
                            'Cold aisle standby airflow requirement': '0xFFFF',
                            'UART configuration 1 secondary connector': '0x7 0x3 0x7',
                            'UART configuration 2 secondary connector': '0x3 0x3 0xF',
                            'USB present primary connector': '0xFF',
                            'Manageability Type': 'N/A',
                            'FRU write protection mechanism': '0xFF',
                            'Programming mode power state supported': '0xFF',
                            'Hot aisle card cooling tier with active cables': '0xFF',
                            'Cold aisle card cooling tier with active cables': '0xFF',
                            'Transceiver reference power level': '0xFF',
                            'Transceiver reference temperature level': '0xFF',
                            'Card thermal tier with local fan fail': '0xFF',
                            'Number of physical controllers \(N\)': '0xFF',
                            'Controller 1 UDID \(if applicable\)': 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF',
                            'Controller 2 UDID \(if applicable\)': 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF',
                            'Controller 3 UDID \(if applicable\)': 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF',
                            'Controller 4 UDID \(if applicable\)': 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF',
                            'Controller 5 UDID \(if applicable\)': 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF',
                            'Controller 6 UDID \(if applicable\)': 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'}
        middle_mfg_info_ocp = {'Language Code': '0x55',
                               'Vendor Name': 'ma',
                               'Product Name': 'pr',
                               'Part Number': 'p',
                               'Serial Number': 'Ser',
                               'Part Version': '~ Aa',
                               'Asset Tag': "'\\",
                               'Mfg Date': '4718-01-16',
                               'Rework Date': '4718-01-16',
                               'Board Trace Num': 'Aa~ AAAAAAAAAAAA',
                               'Board Assembly': 'Aa~ AAAAAAAAAAAA',
                               'UUID': '55555555555555555555555555555555',
                               'Mac Address 0': '',
                               'Is End': '0x1',
                               'Record Len': '0x80',
                               'Record Type': '0xC0',
                               'Manufacturer ID': '555555',
                               'OCP NIC 3.0 FRU OEM record version': '0x55',  # 特殊字符.不需要特殊处理
                               'Card max power \(in watts\) in main \(S0\) mode': '0x55',  # 特殊字符(需要加\
                               'Card max power \(in watts\) in aux \(S5\) mode': '0x55',
                               'Hot aisle card cooling tier with passive cables or RJ45': '0x55',
                               'Cold aisle card cooling tier with passive cables or RJ45': '0x55',
                               'Card active/passive cooling': '0x55',
                               'Hot aisle standby airflow requirement': '0x5555',
                               'Cold aisle standby airflow requirement': '0x5555',
                               'UART configuration 1 secondary connector': '0x5 0x2 0x2',
                               'UART configuration 2 secondary connector': '0x1 0x1 0x5',
                               'USB present primary connector': '0x55',
                               'Manageability Type': 'N/A',
                               'FRU write protection mechanism': '0x55',
                               'Programming mode power state supported': '0x55',
                               'Hot aisle card cooling tier with active cables': '0x55',
                               'Cold aisle card cooling tier with active cables': '0x55',
                               'Transceiver reference power level': '0x55',
                               'Transceiver reference temperature level': '0x55',
                               'Card thermal tier with local fan fail': '0x55',
                               'Number of physical controllers \(N\)': '0x55',
                               'Controller 1 UDID \(if applicable\)': '55555555555555555555555555555555',
                               'Controller 2 UDID \(if applicable\)': '55555555555555555555555555555555',
                               'Controller 3 UDID \(if applicable\)': '55555555555555555555555555555555',
                               'Controller 4 UDID \(if applicable\)': '55555555555555555555555555555555',
                               'Controller 5 UDID \(if applicable\)': '55555555555555555555555555555555',
                               'Controller 6 UDID \(if applicable\)': '55555555555555555555555555555555'}
        min_mfg_info_ocp = {'Language Code': '0x0',
                            'Vendor Name': 'm',
                            'Product Name': 'p',
                            'Part Number': 'p',
                            'Serial Number': 'S',
                            'Part Version': 'A',
                            'Asset Tag': '!',
                            'Mfg Date': '1995-12-31',
                            'Rework Date': '1995-12-31',
                            'Board Trace Num': 'Aa~ AAAAAAAAAAAA',
                            'Board Assembly': 'Aa~ AAAAAAAAAAAA',
                            'UUID': '00000000000000000000000000000000',
                            'Mac Address 0': '',
                            'Is End': '0x1',
                            'Record Len': '0x80',
                            'Record Type': '0xC0',
                            'Manufacturer ID': '000',
                            'OCP NIC 3.0 FRU OEM record version': '0x0',  # 特殊字符.不需要特殊处理
                            'Card max power \(in watts\) in main \(S0\) mode': '0x0',  # 特殊字符(需要加\
                            'Card max power \(in watts\) in aux \(S5\) mode': '0x0',
                            'Hot aisle card cooling tier with passive cables or RJ45': '0x0',
                            'Cold aisle card cooling tier with passive cables or RJ45': '0x0',
                            'Card active/passive cooling': '0x0',
                            'Hot aisle standby airflow requirement': '0x0',
                            'Cold aisle standby airflow requirement': '0x0',
                            'UART configuration 1 secondary connector': '0x0 0x0 0x0',
                            'UART configuration 2 secondary connector': '0x0 0x0 0x0',
                            'USB present primary connector': '0x0',
                            'Manageability Type': 'No manageability',
                            'FRU write protection mechanism': '0x0',
                            'Programming mode power state supported': '0x0',
                            'Hot aisle card cooling tier with active cables': '0x0',
                            'Cold aisle card cooling tier with active cables': '0x0',
                            'Transceiver reference power level': '0x0',
                            'Transceiver reference temperature level': '0x0',
                            'Card thermal tier with local fan fail': '0x0',
                            'Number of physical controllers \(N\)': '0x0',
                            'Controller 1 UDID \(if applicable\)': '00000000000000000000000000000000',
                            'Controller 2 UDID \(if applicable\)': '00000000000000000000000000000000',
                            'Controller 3 UDID \(if applicable\)': '00000000000000000000000000000000',
                            'Controller 4 UDID \(if applicable\)': '00000000000000000000000000000000',
                            'Controller 5 UDID \(if applicable\)': '00000000000000000000000000000000',
                            'Controller 6 UDID \(if applicable\)': '00000000000000000000000000000000'}
        if exp_type == MfgCheckType.MFG_DEF_OCP.value:
            return default_mfg_info_ocp
        elif exp_type == MfgCheckType.MFG_DEF.value:
            return default_mfg_info
        elif exp_type == MfgCheckType.MFG_TEST.value:
            return test_mfg_info
        elif exp_type == MfgCheckType.MFG_TEST_OCP.value:
            return test_mfg_info_ocp
        elif exp_type == MfgCheckType.MFG_MAX_OCP.value:
            return max_mfg_info_ocp
        elif exp_type == MfgCheckType.MFG_MIDDLE_OCP.value:
            return middle_mfg_info_ocp
        elif exp_type == MfgCheckType.MFG_MIN_OCP.value:
            return min_mfg_info_ocp
        else:
            log.error(f'非法的类型{exp_type}')
            return {}

    @classmethod
    def get_set_all_props(cls, ocp: bool = False) -> tuple:
        """
        author: jianghe
        date  : 2025.05.12
        description: 获取要设置的所有的mfginfo属性
        """
        if ocp:
            props = ('pn=pn', 'sn=sn', 'mfgDate=2025-01-01', 'reworkDate=2025-01-01', 'pv=pv', 'vn=vn', 'pdn=pdn',
                     'AssetTag=AssetTag', 'macAddr0=122233445512', 'macAddr1=122233445511', 'macAddr2=122233445522',
                     'macAddr3=122233445533', 'macAddr4=122233445544', 'mainMode=0', 'auxmode=255',
                     'Hotpc=10', 'Coldpc=20', 'Hotaisle=30', 'Coldaisle=40', 'Hotac=50',
                     'Coldac=60', 'PowerLevel=70', 'TempLevel=80')
        else:
            props = ('pn=pn', 'sn=sn', 'mfgDate=2025-01-01', 'reworkDate=2025-01-01', 'pv=pv', 'vn=vn', 'pdn=pdn',
                     'AssetTag=AssetTag', 'macAddr0=122233445512', 'macAddr1=122233445511', 'macAddr2=122233445522',
                     'macAddr3=122233445533', 'macAddr4=122233445544')
        return props

    @classmethod
    def is_tl(cls, bus_info) -> bool:
        """
        author: jianghe
        date  : 2026.04.13
        description: 检查是否是TL
        """
        cmd = f'lspci -vvs {bus_info}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
        if '206f:' in out:
            return True
        else:
            return False

    @classmethod
    def is_ocp(cls, bus_info) -> bool:
        """
        author: jianghe
        date  : 2025.06.26
        description: 检查是否是OCP
        """
        cmd = f'lspci -vvs {bus_info}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
        if '1ff2:0c22' in out or '1ff2:0c23' in out:  # OCPx2, OCPx4
            return True
        elif '1ff2:0c21' in out or '1ff2:0c24' in out or '206f:0c21' in out:  # PCIex2, 衍生卡，腾龙卡
            return False
        else:
            log.info(f'命令{cmd}的返回信息是{code}\n{out}\n{err}')
            CommonOperation.create_bug_problem(ScriptBase, key_word=f'FW',
                                               description_word=f'命令{cmd}的返回里没有正确的sub deviceid')
            return False
        # cmd = f'{constants.SCGBECLI64} -d {bus_info} show mfginfo'
        # code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
        # if 'Record Info' in out:
        #     return True
        # else:
        #     return False

    @classmethod
    def check_cmd_result(cls, caller_class, cmd, exp_value) -> None:
        """
        author: jianghe
        date  : 2025.05.27
        description: 检查命令的返回值是否符合预期
        """
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
        log.info(f'命令{cmd}的返回信息是{code}\n{out}{err}')
        if out.strip() == exp_value:
            log.info(f'命令{cmd}的返回值是{exp_value}，符合预期')
        else:
            log.error(f'命令{cmd}的返回值是{out.strip()}，期望是{exp_value}，不符合预期')
            CommonOperation.create_bug_problem(caller_class, key_word=f'FW',
                                               description_word=f'命令{cmd}的返回值是{out.strip()}，期望是{exp_value}，不符合预期')

    @classmethod
    def get_test_string(cls):
        """
        author: jianghe
        date  : 2025.05.27
        description: 字符串特殊字符检查，获取参数
        """
        all_params_set = [r'azAZ', r'12345678', r'12345678azAZ', r'1234-abCD', r'1\!2\"3#4\$a%b\&C\'D',
                          r'1\(2\)3*4+a,b-C.D', r'1/2:3\;4\<a=b\>C?D',
                          r'1@2\[3\\4]a^b_C\`D',
                          r'1\{2\|3\}4~abCD']
        all_params_show_lspci = [r'azAZ', r'12345678', r'12345678azAZ', r'1234-abCD', r"""1!2"3#4$a%b&C'D""",
                                 r'1(2)3*4+a,b-C.D', r'1/2:3;4<a=b>C?D',
                                 r'1@2[3\\4]a^b_C`D',  # show mfginfo查询是一个\，lspci查询有两个\\
                                 r'1{2|3}4~abCD']
        all_params_show_cli = [r'azAZ', r'12345678', r'12345678azAZ', r'1234-abCD', r"""1!2"3#4$a%b&C'D""",
                               r'1(2)3*4+a,b-C.D', r'1/2:3;4<a=b>C?D',
                               r'1@2[3\4]a^b_C`D',  # show mfginfo查询是一个\，lspci查询有两个\\
                               r'1{2|3}4~abCD']
        return all_params_set, all_params_show_cli, all_params_show_lspci

    @classmethod
    def check_file_exist(cls, caller_class, file) -> None:
        """
        author: jianghe
        date  : 2025.05.28
        description: 字符串特殊字符检查，获取参数
        """
        rtn_filepath_exits = FileOperation.file_path_exists(file)
        if rtn_filepath_exits == RtnStatusEnum.FAIL.value:
            log.error(f'文件{file}不存在')
            CommonOperation.create_bug_problem(caller_class, key_word=f'FW',
                                               description_word=f'文件{file}不存在，不符合预期')

    @classmethod
    def check_file_size(cls, caller_class, file, exp_size) -> None:
        """
        author: jianghe
        date  : 2025.05.28
        description: 字符串特殊字符检查，获取参数
        """
        CliOperation.check_file_exist(caller_class, file)
        file_size = FileOperation.get_file_size(file)
        if int(file_size) < exp_size:
            log.error(f'文件size {file_size}小于{exp_size}，不符合预期')
            CommonOperation.create_bug_problem(caller_class, key_word=f'FW',
                                               description_word=f'文件size {file_size}小于{exp_size}，不符合预期')

    @classmethod
    def get_recovery_file(cls, bus_info, version_last=False) -> str:
        """
        author: jianghe
        date  : 2026.03.16
        description: 获取测试机上升级包的路径
        """
        cmd = f'lspci -vvs {bus_info}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
        if '1ff2:0c22' in out:  # ocpx2
            file = f'ocp-2-25/header_recovery_sxe2_fw.bin'
        elif '1ff2:0c21' in out:  # pciex2
            file = f'pcie-2-25/header_recovery_sxe2_fw.bin'
        elif '1ff2:0c24' in out:  # 10G衍生卡
            file = f'pcie-2-10/header_recovery_sxe2_fw.bin'
        else:  # ocpx4
            file = f'ocp-4-25/header_recovery_sxe2_fw.bin'
        if version_last:
            filepath = '/root/sxetest/publish_version_last/debuginfo/sxe2_fw_asic/debug/'
            cmd = f'ls {filepath}{file}'
            code, file_name, _ = CommandOperation.execute_command_with_error(cmd, cls.server_exec)
            if code != RtnStatusEnum.SUCCESS.value:
                cmd = f'ls /root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/header_recovery_sxe2_fw.bin'
                _, file_name, _ = CommandOperation.execute_command_with_error(cmd, cls.server_exec)
            upgrade_file_path = file_name
            return upgrade_file_path
        else:
            filepath = '/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/'
            cmd = f'ls {filepath}{file}'
            code, file_name, _ = CommandOperation.execute_command_with_error(cmd, cls.server_exec)
            if code != RtnStatusEnum.SUCCESS.value:
                cmd = f'ls /root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/header_recovery_sxe2_fw.bin'
                _, file_name, _ = CommandOperation.execute_command_with_error(cmd, cls.server_exec)
            upgrade_file_path = file_name
            return upgrade_file_path

    @classmethod
    def get_pkg_path(cls, bus_info, sxe=False, version_last=False) -> str:
        """
        author: jianghe
        date  : 2025.05.28
        description: 获取测试机上升级包的路径
        """
        if sxe:
            if version_last:
                image_path = '/root/sxetest/publish_version_last/products/Firmware/Standard-Products/1160-2X/Image_*.*.*.*_NIC-1160-2X.bin'
                return CommonOperation.get_full_path(image_path, CmdExecuteAdressEnum.CLI_DEFAULT.value)
            else:
                image_path = '/root/sxetest/publish_version/products/Firmware/Standard-Products/1160-2X/Image_*.*.*.*_NIC-1160-2X.bin'
                return CommonOperation.get_full_path(image_path, CmdExecuteAdressEnum.CLI_DEFAULT.value)
        else:
            fw_version = CliOperation.get_cli_show_fw_info(cls, bus_info).get('FW Version')
            cmd = f'lspci -vvs {bus_info}'
            code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
            if '1ff2:0c22' in out: # ocpx2
                file = f'Image_{fw_version}_runmod6_NIC_ocp-2-25-1260-X.bin'
            elif '1ff2:0c21' in out:  # pciex2
                file = f'Image_{fw_version}_runmod6_NIC_pcie-2-25-1260-X.bin'
            elif '1ff2:0c24' in out:  # 10G衍生卡
                file = f'Image_{fw_version}_runmod6_NIC_pcie-2-10-1260-X.bin'
            else: # ocpx4
                file = f'Image_{fw_version}_runmod6_NIC_ocp-4-25-1260-X.bin'
            if version_last:
                filepath = '/root/sxetest/publish_version_last/products/Firmware/Standard-Products/1260-X/'
                cmd = f'ls {filepath}{file}'
                code, file_name, _ = CommandOperation.execute_command_with_error(cmd, cls.server_exec)
                if code != RtnStatusEnum.SUCCESS.value:
                    cmd = f'ls {filepath}' + 'Image_'+ fw_version + '_runmod*.bin'
                    _, file_name, _ = CommandOperation.execute_command_with_error(cmd, cls.server_exec)
                upgrade_file_path = file_name
                return upgrade_file_path
            else:
                filepath = '/root/sxetest/publish_version/products/Firmware/Standard-Products/1260-X/'
                cmd = f'ls {filepath}{file}'
                code, file_name, _ = CommandOperation.execute_command_with_error(cmd, cls.server_exec)
                if code != RtnStatusEnum.SUCCESS.value:
                    cmd = f'ls {filepath}' + 'Image_'+ fw_version + '_runmod*.bin'
                    _, file_name, _ = CommandOperation.execute_command_with_error(cmd, cls.server_exec)
                upgrade_file_path = file_name
                return upgrade_file_path

    @classmethod
    def get_pkg_version(cls, version_last=False) -> str:
        """
        author: jianghe
        date  : 2025.10.09
        description: 获取测试机上升级包的版本
        """
        if version_last:
            filepath = '/root/sxetest/publish_version_last/products/Firmware/Standard-Products/1260-X/'
        else:
            filepath = '/root/sxetest/publish_version/products/Firmware/Standard-Products/1260-X/'
        if CommonOperation.is_fpga():
            bitfile = CommonOperation.get_fpga_bitfile_class()
            if bitfile in [FpgaBitfileClass.A.value]:
                file_name = 'Image_*_runmod1A_NIC-1260-X.bin'
            elif bitfile in [FpgaBitfileClass.C.value]:
                file_name = 'Image_*_runmod1C_NIC-1260-X.bin'
            elif bitfile in [FpgaBitfileClass.F.value]:
                file_name = 'Image_*_runmod1F_NIC-1260-X.bin'
            elif bitfile in [FpgaBitfileClass.I.value]:
                file_name = 'Image_*_runmod1I_NIC-1260-X.bin'
            elif bitfile in [FpgaBitfileClass.M.value]:
                file_name = 'Image_*_runmod1M_NIC-1260-X.bin'
            elif bitfile in [FpgaBitfileClass.Q.value]:
                file_name = 'Image_*_runmod1Q_NIC-1260-X.bin'
            else:
                file_name = 'Image_*_runmod1BEFGHKLO_NIC-1260-X.bin'
        else:
            file_name = 'Image_*_runmod6_NIC-1260-X.bin'
        cmd = f'ls {filepath}{file_name}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
        found = re.findall('_(\d+.\d+.\d+.\d+)_', out)
        if not found:
            CommonOperation.create_bug_problem(ScriptBase, key_word=f'FW',
                                               description_word=f'命令{cmd}没有获取到版本号，返回的信息是{code}\n{out}\n{err}')
        return found[0]

    @classmethod
    def get_pkg_path_32m(cls, bus_info) -> str:
        """
        author: jianghe
        date  : 2025.05.28
        description: 获取测试机上升级包的路径
        """
        fw_version = CliOperation.get_cli_show_fw_info(cls, bus_info).get('FW Version')
        if CommonOperation.is_fpga():
            bitfile = CommonOperation.get_fpga_bitfile_class()
            if bitfile in [FpgaBitfileClass.A.value]:
                file_name = 'NorflashRegionSxe2fpgaA_' + fw_version + '.bin'
            elif bitfile in [FpgaBitfileClass.C.value]:
                file_name = 'NorflashRegionSxe2fpgaC_' + fw_version + '.bin'
            elif bitfile in [FpgaBitfileClass.I.value]:
                file_name = 'NorflashRegionSxe2fpgaI_' + fw_version + '.bin'
            elif bitfile in [FpgaBitfileClass.M.value]:
                file_name = 'NorflashRegionSxe2fpgaM_' + fw_version + '.bin'
            elif bitfile in [FpgaBitfileClass.Q.value]:
                file_name = 'NorflashRegionSxe2fpgaQ_' + fw_version + '.bin'
            else:
                file_name = 'NorflashRegionSxe2fpgaBEFGHKLO_' + fw_version + '.bin'
            filepath = '/root/sxetest/publish_version/factory/Firmware/1260-X/'
        else:
            cmd = f'lspci -vvs {bus_info}'
            code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
            if '1ff2:0c22' in out:  # ocpx2
                filepath = '/root/sxetest/publish_version/factory/Firmware/1260-X/1263-2A/'
            elif '1ff2:0c21' in out:  # pciex2
                filepath = '/root/sxetest/publish_version/factory/Firmware/1260-X/1260-2A/'
            elif '1ff2:0c24' in out:  # 10G衍生卡
                filepath = '/root/sxetest/publish_version/factory/Firmware/1260-X/1260C-2X/'
            elif '1ff2:0c23' in out:  # ocpx4
                filepath = '/root/sxetest/publish_version/factory/Firmware/1260-X/1263-4A/'
            else:
                CommonOperation.create_bug_problem(ScriptBase, key_word=f'FW',
                                                   description_word=f'{bus_info}是不支持的卡类型，命令{cmd}返回的信息是{out}')
                filepath = ''
            file_name = 'NorflashRegionSxe2asic_' + fw_version + '.bin'
        # filepath = '/root/sxetest/publish_version/factory/Firmware/1260-X/'
        upgrade_file_path = filepath + file_name
        return upgrade_file_path

    @classmethod
    def get_recovery_bin_file(cls, bus_info):
        """
        author: jianghe
        date  : 2025.05.28
        description: 获取测试机上升级包的路径
        """
        file = None
        cmd = f'lspci -vvs {bus_info}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
        if '1ff2:0c22' in out:  # ocpx2
            file = '/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/ocp-2-25/header_recovery_sxe2_fw.bin'
        elif '1ff2:0c21' in out:  # pciex2
            file = '/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/pcie-2-25/header_recovery_sxe2_fw.bin'
        elif '1ff2:0c24' in out:  # 10G衍生卡
            file = '/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/pcie-2-10/header_recovery_sxe2_fw.bin'
        elif '1ff2:0c23' in out:  # ocpx4
            file = '/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/ocp-4-25/header_recovery_sxe2_fw.bin'
        else:
            CommonOperation.create_bug_problem(ScriptBase, key_word=f'FW',
                                               description_word=f'{bus_info}是不支持的卡类型，命令{cmd}返回的信息是{out}')
        if file:
            cmd = f'ls {file}'
            code, out, err = CommandOperation.execute_command_with_error(cmd)
            if code != RtnStatusEnum.SUCCESS.value:
                log.info(f'24版本的新路径{file}没找到，尝试找旧路径')
                file = f'/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/header_recovery_sxe2_fw.bin'
                cmd = f'ls {file}'
                code, out, err = CommandOperation.execute_command_with_error(cmd)
                if code != RtnStatusEnum.SUCCESS.value:
                    log.info(f'旧路径{file}也没有找到')
                    return None
        return file

    @classmethod
    def get_mfg_bin_file(cls, bus_info):
        """
        author: jianghe
        date  : 2025.05.28
        description: 获取测试机上升级包的路径
        """
        file = None
        cmd = f'lspci -vvs {bus_info}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
        if '1ff2:0c22' in out:  # ocpx2
            file = '/root/sxetest/publish_version/factory/Firmware/1260-X/1263-2A/mfg_ocp.bin'
        elif '1ff2:0c21' in out or '206f:0c21' in out:  # pciex2, 腾龙卡
            file = '/root/sxetest/publish_version/factory/Firmware/1260-X/1260-2A/mfg.bin'
        elif '1ff2:0c24' in out:  # 10G衍生卡
            file = '/root/sxetest/publish_version/factory/Firmware/1260-X/1260C-2X/mfg.bin'
        elif '1ff2:0c23' in out:  # ocpx4
            file = '/root/sxetest/publish_version/factory/Firmware/1260-X/1263-4A/mfg_ocp.bin'
        else:
            CommonOperation.create_bug_problem(ScriptBase, key_word=f'FW',
                                               description_word=f'{bus_info}是不支持的卡类型，命令{cmd}返回的信息是{out}')
        if file:
            cmd = f'ls {file}'
            code, out, err = CommandOperation.execute_command_with_error(cmd)
            if code != RtnStatusEnum.SUCCESS.value:
                log.info(f'24版本的新路径{file}没找到，尝试找旧路径')
                if 'ocp' in file:
                    file = '/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/mfg_ocp.bin'
                else:
                    file = '/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/mfg.bin'
                cmd = f'ls {file}'
                code, out, err = CommandOperation.execute_command_with_error(cmd)
                if code != RtnStatusEnum.SUCCESS.value:
                    log.info(f'旧路径{file}也没有找到')
                    return None
        return file

    @classmethod
    def get_test_mac_addr(cls) -> str:
        """
        author: jianghe
        date  : 2025.05.28
        description: 获取测试机上升级包的路径
        """
        tail = random.choices(['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f'], k=2)
        return '12:34:87:65:90:' + ''.join(tail)

    @classmethod
    def get_test_mac_addr_list(cls, count=1) -> list:
        """
        author: jianghe
        date  : 2025.05.28
        description: 获取测试机上升级包的路径
        """
        get_list = []
        import itertools
        combinations = list(itertools.combinations('0123456789abcdef', 2))
        tail_list = [''.join(comb) for comb in combinations]
        random.shuffle(tail_list)
        for ind in range(count):
            tail = tail_list[ind]
            get_list.append('12:34:87:65:90:' + ''.join(tail))
        return get_list

    @classmethod
    def check_device_mac_from_ifconfig(cls, caller_class, device_name: str, exp_mac: str,
                                       cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author: jianghe
        date  : 2025.05.29
        description: 检查ifconfig查出来的mac地址
        """
        cur_mac = IfConfig.get_device_mac(device_name, cmd_execute_address)
        if cur_mac == exp_mac:
            log.info(f'查询的mac与预期一致，是{exp_mac}')
        else:
            CommonOperation.create_bug_problem(caller_class, key_word=f'FW',
                                               description_word=f'查询的mac不符合预期，查出来是{cur_mac}，期望是{exp_mac}')

    @classmethod
    def custom_scgbe_fwinfo(cls, caller_class, bus_info) -> tuple:
        """
        author: jianghe
        date  : 2025.06.04
        description: 获取custom sxe2 fwinfo中信息
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} custom sxe2 fwinfo'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        run_region = re.findall('sys run Region:\s*([a-zA-Z]+)', out)[0]
        rst_cause = re.findall('NIC RST CAUSE:\s*([a-zA-Z_]+)', out)[0]
        build_mode = re.findall('build mode =\s*([a-zA-Z_]+)', out)[0]
        return (run_region, rst_cause, build_mode)

    @classmethod
    def custom_scgbe_version_bootload(cls, caller_class, bus_info) -> tuple:
        """
        author: jianghe
        date  : 2025.10.10
        description: 获取custom sxe2 version bootload中信息
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} custom sxe2 version bootload'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        image_ver = re.findall('image ver\s*=\s*(.*)', out)[0].strip()
        boot_ver = re.findall('boot ver\s*=\s*(.*)', out)[0].strip()
        run_region = re.findall('sys run Region:\s*([A-Z]+)', out)[0].strip()
        return (image_ver, boot_ver, run_region)

    @classmethod
    def custom_scgbe_flashwrstr(cls, caller_class, bus_info, devid, offset, len, value) -> None:
        """
        author: jianghe
        date  : 2025.06.04
        description: 执行custom sxe2 flashwrstr，例子，
        scgbecli -d 0000:31:00.0 custom sxe2 flashwrstr devid=10 offset=0x0 len=4 value=0x11223344
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} custom sxe2 flashwrstr devid={devid} offset={offset} len={len} value={value}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)

    @classmethod
    def damage_region(cls, caller_class, bus_info, region):
        """
        author: jianghe
        date  : 2025.06.04
        description: 损坏flash分区
        """
        value = '0xBE88E5AECE449E1FBE88E5AECE449E1FBE88E5AECE449E1FBE88E5AECE449E1FBE88E5AECE449E1FBE88E5AECE449E1FBE'
        if region == RegionEnum.FW.value:
            CliOperation.custom_scgbe_flashwrstr(caller_class, bus_info, RegionNumEnum.FW.value, '1', '100',
                                                 f'{value}')
        elif region == RegionEnum.FW_BAK.value:
            CliOperation.custom_scgbe_flashwrstr(caller_class, bus_info, RegionNumEnum.FW_BAK.value, '1', '100',
                                                 f'{value}')
        else:
            CommonOperation.create_bug_problem(caller_class, key_word=f'FW',
                                               description_word=f'不支持的分区{region}，报bug')

    @classmethod
    def get_run_region(cls, bus_info):
        """
        author: jianghe
        date: 20250606
        description: 获取运行分区
        """
        fwinfo = CliOperation.custom_scgbe_fwinfo(ScriptBase, bus_info)
        cur_region = RegionEnum.FW.value if fwinfo[0] == constants.REGION_MASTER else RegionEnum.FW_BAK.value
        next_region = RegionEnum.FW_BAK.value if cur_region == RegionEnum.FW.value else RegionEnum.FW.value
        return (cur_region, next_region)

    @classmethod
    def check_run_region(cls, caller_class, bus_info, exp_region, fw: bool = True) -> None:
        """
        author: jianghe
        date: 20250606
        description: 获取当前运行分区
        """
        if fw:
            cur_region, _ = cls.get_run_region(bus_info)
            if cur_region == exp_region:
                log.info(f'当前的启动分区跟预期一致，是{cur_region}')
            else:
                CommonOperation.create_bug_problem(
                    caller_class,
                    key_word='FW',
                    description_word=f'当前的启动分区跟预期不一致，当前是{cur_region}，期望是{exp_region}')
        else:
            _, _, cur_region = cls.custom_scgbe_version_bootload(cls, bus_info)
            if cur_region == exp_region:
                log.info(f'bootload当前的启动分区跟预期一致，是{cur_region}')
            else:
                CommonOperation.create_bug_problem(caller_class,
                                                   key_word='FW',
                                                   description_word=f'bootload当前的启动分区跟预期不一致，'
                                                                    f'当前是{cur_region}，期望是{exp_region}')

    @classmethod
    def cli_get_region_version(cls, bus_info, region_id):
        """
        author: jianghe
        date: 2025.09.30
        description: 检查分区版本
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} custom sxe2 regionVer id={region_id}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
        version = out.split("VERSION: ")[1].split()[0]
        return version

    @classmethod
    def check_region_version(cls, caller_class, bus_info, region_id, exp_ver) -> None:
        """
        author: jianghe
        date: 2025.09.30
        description: 检查分区版本
        """
        cur_ver = cls.cli_get_region_version(bus_info, region_id)
        if cur_ver == exp_ver:
            log.info(f'分区{region_id}的版本符合预期，是{cur_ver}')
        else:
            CommonOperation.create_bug_problem(caller_class, key_word='FW',
                                               description_word=f'分区{region_id}的版本跟预期不一致，'
                                                                f'当前是{cur_ver}，期望是{exp_ver}')

    @classmethod
    def add_header(cls, test_region: str):
        """
        author: jianghe
        date: 2025.09.30
        description: 修改版本号
        """
        rtn_code = False
        add_header_dir = constants.ADD_HEADER_DIR
        add_header_script_path = constants.USER_ADD_HEADER
        if test_region == RegionEnum.UBOOT.value:
            header_txt = constants.BOOTLOADER_TXT
            region_type = 'uboot'
            no_header_file_path = constants.BOOTLOADER_BIN_SCGBE
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
                CommonOperation.create_bug_problem(ScriptBase, key_word='FW',
                                                   description_word=f'command:{exec_command_bin_file_add_header}执行失败')
            return rtn_code
        else:
            region_type = 'ioc'
            header_txt = constants.FW_TXT
            if CommonOperation.is_fpga():
                fpga_bit_class = CommonOperation.get_fpga_bitfile_class()
                if fpga_bit_class == FpgaBitfileClass.A.value:
                    no_header_file_path = constants.FW_BIN.format('A_F')
                elif fpga_bit_class == FpgaBitfileClass.C.value:
                    no_header_file_path = constants.FW_BIN.format('C_F')
                elif fpga_bit_class == FpgaBitfileClass.F.value:
                    no_header_file_path = constants.FW_BIN.format('F')
                elif fpga_bit_class == FpgaBitfileClass.I.value:
                    no_header_file_path = constants.FW_BIN.format('I_F')
                elif fpga_bit_class == FpgaBitfileClass.M.value:
                    no_header_file_path = constants.FW_BIN.format('M_F')
                elif fpga_bit_class == FpgaBitfileClass.Q.value:
                    no_header_file_path = constants.FW_BIN.format('Q_F')
                else:
                    no_header_file_path = constants.FW_BIN.format('BEFGHKLO_F')
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
                    CommonOperation.create_bug_problem(ScriptBase, key_word='FW',
                                                       description_word=f'command:{exec_command_bin_file_add_header}执行失败')
                return rtn_code
            else:
                header_txt0 = constants.FW_TXT0
                header_txt1 = constants.FW_TXT1
                header_txt2 = constants.FW_TXT2
                header_txt3 = constants.FW_TXT3
                header_txt4 = constants.FW_TXT4
                header_txt5 = constants.FW_TXT5
                no_header_file_path_dict = {
                    header_txt0:constants.FW_BIN,
                    header_txt1: constants.FW_BIN1,
                    header_txt2: constants.FW_BIN2,
                    header_txt3: constants.FW_BIN3,
                    header_txt4: constants.FW_BIN4,
                    header_txt5: constants.FW_BIN5,
                }
                # no_header_file_path_list = [constants.FW_BIN,constants.FW_BIN1,
                #                             constants.FW_BIN2,constants.FW_BIN3,constants.FW_BIN4,constants.FW_BIN5]
                for header_txt, no_header_file_path in no_header_file_path_dict.items():
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
                        CommonOperation.create_bug_problem(ScriptBase, key_word='FW',
                                                           description_word=f'command:{exec_command_bin_file_add_header}执行失败')
                return rtn_code

    @classmethod
    def modify_version_and_pack(cls, region, modify_big: bool = True):
        """
        author: jianghe
        date: 2025.09.30
        description: 修改版本号
        """
        CommonOperation.concat_test_steps(f'修改版本号，修改{region}的版本号')
        cls.modify_version(test_region=region, modify_big=modify_big)

        CommonOperation.concat_test_steps(f'加头')
        rtn_code = cls.add_header(test_region=region)

        CommonOperation.concat_test_steps(f'打包')
        header_bin_file_path = constants.HEADER_BIN_OUTPUT
        ssh_server_ip, _ = CommonOperation.get_nic_logical_ip()
        header_file_name = FileOperation.get_files(file_path=header_bin_file_path, ip=ssh_server_ip)[1][0]
        header_bin_file = f'{header_bin_file_path}{header_file_name}'
        # fpga_bit_class = CommonOperation.get_fpga_bitfile_class()
        # if fpga_bit_class == FpgaBitfileClass.A.value:
        #     constants.HEADER_FW_BIN_SCGBE = constants.HEADER_FW_BIN_SCGBE.format('A_F')
        # elif fpga_bit_class == FpgaBitfileClass.C.value:
        #     constants.HEADER_FW_BIN_SCGBE = constants.HEADER_FW_BIN_SCGBE.format('C_F')
        # elif fpga_bit_class == FpgaBitfileClass.F.value:
        #     constants.HEADER_FW_BIN_SCGBE = constants.HEADER_FW_BIN_SCGBE.format('F')
        # elif fpga_bit_class == FpgaBitfileClass.I.value:
        #     constants.HEADER_FW_BIN_SCGBE = constants.HEADER_FW_BIN_SCGBE.format('I_F')
        # elif fpga_bit_class == FpgaBitfileClass.M.value:
        #     constants.HEADER_FW_BIN_SCGBE = constants.HEADER_FW_BIN_SCGBE.format('M_F')
        # elif fpga_bit_class == FpgaBitfileClass.Q.value:
        #     constants.HEADER_FW_BIN_SCGBE = constants.HEADER_FW_BIN_SCGBE.format('Q_F')
        # else:
        #     constants.HEADER_FW_BIN_SCGBE = constants.HEADER_FW_BIN_SCGBE.format('BEFGHKLO_F')
        # header_bin_file_all = constants.STR_SPACE.join([header_bin_file,
        #                                                 constants.HEADER_NVDATA_BIN_SCGBE,
        #                                                 constants.HEADER_USERDEFAULT_BIN_SCGBE,
        #                                                 constants.HEADER_OPROM_BIN_SCGBE,
        #                                                 constants.HEADER_FW_BIN_SCGBE])
        header_bin_file_all = constants.STR_SPACE.join([header_bin_file])

        if rtn_code:
            exec_command_image_package_create = (
                f"cd /root/sxetest/upgrade_dir/; python2 {constants.PS3_MAKE_PACKAGE} {header_bin_file_all}")
            rtn_code_pack, rtn_outputs_pack, rtn_err_pack = CommandOperation.execute_command_with_error(
                exec_command_image_package_create, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            if rtn_code_pack == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{exec_command_image_package_create}执行成功')
            else:
                CommonOperation.create_bug_problem(ScriptBase, key_word='FW',
                                                   description_word=f'command:{exec_command_image_package_create}执行失败')

    @classmethod
    def modify_version(cls, test_region: str, modify_big: bool = True):
        """
        author: jianghe
        date: 20250930
        description: 修改版本号
        """
        current_path = os.path.dirname(__file__)
        local_file_temp = os.path.join(current_path, 'sxe_temp.txt')
        if test_region == RegionEnum.UBOOT.value:
            header_txt = constants.BOOTLOADER_TXT
        elif test_region == RegionEnum.OPTION_ROM.value:
            header_txt = constants.OPTIONROM_TXT
        elif test_region == RegionEnum.NVDATA.value:
            header_txt = constants.NVDATA_TXT
        elif test_region == RegionEnum.USER_DEFAULT.value:
            header_txt = constants.USERDEFAULT_TXT
        else:
            header_txt = constants.FW_TXT
        exec_command = f'cat {header_txt}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cls.server_exec)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # log.info(f'command:{exec_command}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
            log.info(f'修改前txt：\n{rtn_outputs}')
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        # 修改文件内容 image_version = 0x020f;
        result = re.search(r'image_version\s*=\s*0x(\w+)', rtn_outputs)
        curr_version = ''
        if result:
            curr_version = result.group(1)
            log.info('curr_version:', curr_version)
        # if cls.upgrade_type == UpgradeTypeEnum.UPGRADE.value:
        #     cls.new_version = format(int(curr_version, 16) + 0x100, '08x')
        # elif cls.upgrade_type == UpgradeTypeEnum.DEGRADE.value:
        #     if int(curr_version, 16) >= 0x100:
        #         cls.new_version = format(int(curr_version, 16) - 0x100, '08x')
        if modify_big:
            new_version = format(int(curr_version, 16) - 0x10000, '08x')
        else:
            new_version = format(int(curr_version, 16) - 0x1, '08x')
        file_contents = re.sub(r'image_version = 0x\w+', f'image_version = 0x{new_version}', rtn_outputs)
        cls.new_version = f'{int(new_version[0:2], 16)}.{int(new_version[2:4], 16)}.{int(new_version[4:6], 16)}.{int(new_version[6:], 16)}'
        log.info(f'file_contents: {file_contents}')
        FileOperation.write_local_file(file_path=local_file_temp,
                                       contents=file_contents)
        server_ip, _ = CommonOperation.get_nic_logical_ip()
        FileOperation.sftp_upload_file(localfile_path=local_file_temp,
                                       remotefile_path=header_txt,
                                       ip=server_ip)
        # 查看修改结果
        exec_command = f'cat {header_txt}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cls.server_exec)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'修改后txt:\n{rtn_outputs}')
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

    @classmethod
    def get_device_state_from_ifconfig(cls, dev_name,
                                       cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.06.04
        description: 损坏flash分区
        """
        state = None
        cmd = f'{constants.IFCONFIG} {dev_name}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
        out_list = out.split('\n')
        for out_line in out_list:
            if f'{dev_name}' in out_line:
                if 'UP' in out_line:
                    state = constants.UP
                else:
                    state = constants.DOWN
        return state

    @classmethod
    def cli_set_speed(cls, caller_class, bus_info, speed,
                      cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.06.04
        description: 执行scgbecli -d <device> set speed speed=<25G>
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} set speed speed={speed}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)

    @classmethod
    def cli_get_show_device_info(cls, caller_class, bus_info,
                                 cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.06.11
        description: 执行scgbecli -d <device> show device
        """
        prop_dict = {}
        prop_list = ['Product Number', 'Product Name', 'Serial Number', 'Revision', 'FW Version']
        cmd = f'{constants.SCGBECLI64} -d {bus_info} show device'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        for prop in prop_list:
            prop_dict.update({prop: re.findall(f'\|{prop}\s*\|(.*)\|', out)[0].strip()})
        return prop_dict

    @classmethod
    def check_cli_show_device_info(cls, caller_class, bus_info, check_prop_dict,
                                   cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.06.11
        description: 执行scgbecli -d <device> show device，检查信息
        """
        device_info = CliOperation.cli_get_show_device_info(caller_class, bus_info, cmd_execute_address)
        for prop, exp in check_prop_dict.items():
            cur = device_info.get(prop)
            if exp != cur:
                log.error(f'show device中属性{prop}查出来与预期不一致，查出来是{cur}，期望是{exp}')
                CommonOperation.create_bug_problem(caller_class, key_word=f'FW',
                                                   description_word=f'查询的{prop}不符合预期，查出来是{cur}，期望是{exp}')
            else:
                log.info(f'show device中属性{prop}查出来与预期一致，是{cur}')

    @classmethod
    def cli_get_dev_show_info(cls, caller_class, bus_info,
                              cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.06.11
        description: 执行scgbecli -d <device> show
        """
        prop_dict = {}
        prop_list = ['SOC Status', 'SOC Temperature', 'Firmware Version', 'OptionRom Version', 'Mac Address',
                     'Port Link', 'Link Status', 'Link Speed', 'SFP Information Acquisition Status',
                     'Optical Mod Temperature', 'Transceiver Type', 'Vendor Name', 'Vendor PN']
        cmd = f'{constants.SCGBECLI64} -d {bus_info} show'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        for prop in prop_list:
            if prop not in out:
                continue
            if prop == 'SOC Temperature':
                if re.findall(f'{prop}\s*\(Degree Celsius\)\s*=(.*)', out):
                    prop_dict.update({prop: re.findall(f'{prop}\s*\(Degree Celsius\)\s*=(.*)', out)[0].strip()})
                else:
                    prop_dict.update({prop: None})
            elif prop == 'Optical Mod Temperature':
                if re.findall(f'{prop}\s*\(Degree Celsius\)\s*=(.*)', out):
                    prop_dict.update({prop: re.findall(f'{prop}\s*\(Degree Celsius\)\s*=(.*)', out)[0].strip()})
                else:
                    prop_dict.update({prop: None})
            else:
                if re.findall(f'{prop}\s*=(.*)', out):
                    prop_dict.update({prop: re.findall(f'{prop}\s*=(.*)', out)[0].strip()})
                else:
                    prop_dict.update({prop: None})
        return prop_dict

    @classmethod
    def check_cli_dev_show_info(cls, caller_class, bus_info, check_prop_dict,
                                cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.06.11
        description: 执行scgbecli -d <device> show，检查信息
        """
        device_info = CliOperation.cli_get_dev_show_info(caller_class, bus_info, cmd_execute_address)
        for prop, exp in check_prop_dict.items():
            cur = device_info.get(prop)
            if prop == 'Optical Mod Temperature' or prop == 'SOC Temperature':
                CliOperation.check_value_diff(cls, cur, exp, 5)
            else:
                if exp != cur:
                    log.error(f'show中属性{prop}查出来与预期不一致，查出来是{cur}，期望是{exp}')
                    CommonOperation.create_bug_problem(caller_class, key_word=f'FW',
                                                       description_word=f'查询的{prop}不符合预期，查出来是{cur}，期望是{exp}')
                else:
                    log.info(f'show中属性{prop}查出来与预期一致，是{cur}')

    @classmethod
    def cli_get_dev_show_link_base_info(cls, caller_class, bus_info,
                                        cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.06.17
        description: 执行scgbecli -d <device> show link base
        """
        prop_dict = {}
        prop_list = ['State', 'Physical State', 'Speed', 'Width', 'FEC',
                     'Loopback Mode', 'Auto Negotiation', 'Enabled Link Speed', 'Supported Cable Speed',
                     'Firmware Version', 'Cli Version']
        cmd = f'{constants.SCGBECLI64} -d {bus_info} show link base'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        for prop in prop_list:
            if prop == 'Enabled Link Speed':
                prop_dict.update({prop: re.findall(f'\|{prop}\s*\(Ext\.\)\s*\|(.*)\|', out)[0].strip()})
            elif prop == 'Supported Cable Speed':
                prop_dict.update({prop: re.findall(f'\|{prop}\s*\\(Ext\.\)\s*\|(.*)\|', out)[0].strip()})
            else:
                prop_dict.update({prop: re.findall(f'\|{prop}\s*\|(.*)\|', out)[0].strip()})
        return prop_dict

    @classmethod
    def check_cli_dev_show_link_base_info(cls, caller_class, bus_info, check_prop_dict,
                                          cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.06.17
        description: 执行scgbecli -d <device> show link base，检查信息
        """
        device_info = CliOperation.cli_get_dev_show_link_base_info(caller_class, bus_info, cmd_execute_address)
        for prop, exp in check_prop_dict.items():
            cur = device_info.get(prop)
            if exp != cur:
                log.error(f'show link base中属性{prop}查出来与预期不一致，查出来是{cur}，期望是{exp}')
                CommonOperation.create_bug_problem(caller_class, key_word=f'FW',
                                                   description_word=f'查询的{prop}不符合预期，查出来是{cur}，期望是{exp}')
            else:
                log.info(f'show link base中属性{prop}查出来与预期一致，是{cur}')

    @classmethod
    def get_all_cmd_list(cls, server_bdf_list):
        """
        author: jianghe
        date  : 2025.06.17
        description: 获取要测试的所有的cli命令
        """
        pkg_file = CliOperation.get_pkg_path(server_bdf_list[0])
        # recovery_file = CliOperation.get_pkg_path(cls.server_bus_info)
        all_cmd_list = [f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} upgrade file={pkg_file}',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} upgrade eeprom file={pkg_file}',
                        f'{constants.SCGBECLI64} show',
                        f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show',
                        f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show termlog all',
                        f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show mfginfo',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} set cable',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} clear rx fec histogram',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} set loopback loopback=',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} set portState portState=',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} set fec fec=',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} set speed speed=',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} set config ...',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} set config default',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} reset type=0',
                        f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show cable ddm',
                        f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show module',
                        f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} get cable pageindex=0 offset=0 length=256',
                        f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} get cable pageindex=1 offset=255 length=1',
                        f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show device',
                        f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show uptime',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show temp',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show rx fec histogram',
                        f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show link base',
                        f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show fw',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show counters',
                        f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show flashinfo',
                        f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show fwreset',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show serdes tx portType=<NETWORK(Default)/PCIE>',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show config',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show config...',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show config verbosity',
                        # f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show dev2netdev',
                        f'{constants.SCGBECLI64} show list',
                        f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} set lldp state=on workmode=tx',
                        f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} show lldp',
                        f'{constants.SCGBECLI64} -d {random.choice(server_bdf_list)} get soctempthreshold'
                        ]
        return all_cmd_list

    @classmethod
    def check_call_key_value(cls, caller_class, output: str, key: str, obj_list: list) -> None:
        """
        author: jianghe
        date:   2021.12.01
        description: 检查多卡的命令返回格式，例子
        ScriptBaseMethod.check_call_key_value(cls, output, '\|CurrentMode \|([A-Za-z]+)', ctrl_object_list)
        :return: 无返回值
        """
        if len(obj_list) == 0:
            return
        if not re.split('Device [\w]+:[\w]+:[\w]+.[\w]:', output):
            log.error(f'没找到卡信息，返回的信息是{output}')
            CommonOperation.create_bug_problem(caller_class, key_word=f'CLI',
                                               description_word=f'没找到卡信息，返回的信息是{output}')
        get_obj_list = re.split('Device [\w]+:[\w]+:[\w]+.[\w]:', output)
        if len(get_obj_list) != len(obj_list) + 1:
            CommonOperation.create_bug_problem(caller_class, key_word=f'CLI',
                                               description_word=f'卡pf个数不正确，期望是{obj_list}，返回的信息是{output}')
        else:
            for i in range(len(obj_list)):
                if re.findall(key, get_obj_list[i + 1]) is None:
                    CommonOperation.create_bug_problem(caller_class, key_word=f'CLI',
                                                       description_word=f'第{i}个pf信息不正确，返回的信息是{output}')
                get_status = re.findall(key, get_obj_list[i + 1])[0]
                if obj_list[i] == get_status:
                    log.info(f'第{i}个pf检查通过')
                else:
                    CommonOperation.create_bug_problem(caller_class, key_word=f'CLI',
                                                       description_word=f'第{i}个pf检查不通过，期望是{obj_list[i]}，'
                                                                        f'返回的信息是{output}')

    @classmethod
    def cli_add_quirklist(cls, caller_class, bus_info, vendor, vendorpn, sup_txdar=None, check_loscnt=None,
                          linktime=None, abslevel=None, loslevel=None, filtertime=None,
                          cmd_execute_address=CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.07.21
        description: 执行scgbecli -d <device> add quirklist
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} add quirklist vendor={vendor} vendorpn={vendorpn}'
        if sup_txdar:
            cmd += f' supporttxdar={sup_txdar}'
        if check_loscnt:
            cmd += f' checkloscnt={check_loscnt}'
        if linktime:
            cmd += f' linktime={linktime}'
        if abslevel:
            cmd += f' abslevel={abslevel}'
        if loslevel:
            cmd += f' loslevel={loslevel}'
        if filtertime:
            cmd += f' filtertime={filtertime}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)

    @classmethod
    def cli_show_allquirklist(cls, caller_class, bus_info, get_info: bool = True,
                              cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.07.21
        description: 执行scgbecli -d <device> show allquirklist
        返回信息是[('No', 'vendor', 'vendorpn', '10', '10', '10', '10')]
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} show allquirklist'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        if not get_info:
            return
        quirk_list_dict = {}
        rtn = re.findall('Device ([0-9a-z]{4}:[0-9a-z]{2}:[0-9a-z]{2}.[0-9a-z]{1}):', out)
        device_ind_list = []
        for device in rtn:
            device_ind_list.append(out.find(device))
        for ind in range(len(device_ind_list)):
            if ind == len(device_ind_list) - 1:
                info = out[device_ind_list[ind]:]
            else:
                info = out[device_ind_list[ind]:device_ind_list[ind + 1]]
            invalid = re.findall('\|Invalid\s*\|(.*)\|', info)
            vendor = re.findall('\|Vendor\s*\|(.*)\|', info)
            vendorpn = re.findall('\|Vendor PN\s*\|(.*)\|', info)
            sup_tx_dar = re.findall('\|Support TxDar\s*\|(.*)\|', info)
            check_los_cnt = re.findall('\|Check LosCnt\s*\|(.*)\|', info)
            link = re.findall('\|Link Time\s*\|(.*)\|', info)
            abs = re.findall('\|ABS Level\s*\|(.*)\|', info)
            los = re.findall('\|LOS Level\s*\|(.*)\|', info)
            filter = re.findall('\|Fiter Time\s*\|(.*)\|', info)
            invalid = [info.strip() for info in invalid]
            vendor = [info.strip() for info in vendor]
            vendorpn = [info.strip() for info in vendorpn]
            sup_tx_dar = [info.strip() for info in sup_tx_dar]
            check_los_cnt = [info.strip() for info in check_los_cnt]
            link = [info.strip() for info in link]
            abs = [info.strip() for info in abs]
            los = [info.strip() for info in los]
            filter = [info.strip() for info in filter]
            quirk_list_dict.update({rtn[ind]: list(zip(invalid, vendor, vendorpn, sup_tx_dar, check_los_cnt, link, abs, los, filter))})
        return quirk_list_dict

    @classmethod
    def cli_show_quirklist(cls, caller_class, bus_info, vendor, vendorpn,
                           cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.07.21
        description: 执行scgbecli -d <device> show quirklist
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} show quirklist vendor={vendor} vendorpn={vendorpn}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        return ()

    @classmethod
    def check_cli_show_quirklist(cls, caller_class, bus_info, quirk_list, reverse: bool = False,
                                 cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.07.21
        description: 执行scgbecli -d <device> show quirklist
        """
        allquirklist = CliOperation.cli_show_allquirklist(caller_class, bus_info,
                                                          cmd_execute_address=cmd_execute_address)
        if not reverse:
            for quirk in quirk_list:
                if quirk not in allquirklist.get(bus_info):
                    CommonOperation.create_bug_problem(caller_class, key_word=f'CLI',
                                                       description_word=f'{quirk}不在怪癖列表{allquirklist.get(bus_info)}内，报bug')
        else:
            for quirk in quirk_list:
                if quirk in allquirklist.get(bus_info):
                    CommonOperation.create_bug_problem(caller_class, key_word=f'CLI',
                                                       description_word=f'{quirk}在怪癖列表{allquirklist.get(bus_info)}内，报bug')

    @classmethod
    def cli_delete_quirklist(cls, caller_class, bus_info, vendor, vendorpn,
                             cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
                             check_ignore: bool = False):
        """
        author: jianghe
        date  : 2025.07.21
        description: 执行scgbecli -d <device> delete quirklist
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} delete quirklist vendor={vendor} vendorpn={vendorpn}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
        if check_ignore:
            return
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)

    @classmethod
    def cli_add_whitelist(cls, caller_class, bus_info, vendor, vendorpn,
                          cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.07.21
        description: 执行scgbecli -d <device> add whitelist
        """
        if ' ' in vendor:
            vendor = vendor.replace(' ', '\ ')
        cmd = (f'{constants.SCGBECLI64} -d {bus_info} add whitelist vendor={vendor} vendorpn={vendorpn}')
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)

    @classmethod
    def cli_show_allwhitelist(cls, caller_class, bus_info, get_info: bool = True,
                              cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.07.21
        description: 执行scgbecli -d <device> show allwhitelist，返回信息格式
        返回信息格式[('No', 'vendor', 'vendorpn')]
        """
        white_list_dict = {}
        cmd = f'{constants.SCGBECLI64} -d {bus_info} show allwhitelist'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        if not get_info:
            return
        rtn = re.findall('Device ([0-9a-z]{4}:[0-9a-z]{2}:[0-9a-z]{2}.[0-9a-z]{1}):', out)
        device_ind_list = []
        for device in rtn:
            device_ind_list.append(out.find(device))
        for ind in range(len(device_ind_list)):
            if ind == len(device_ind_list) - 1:
                info = out[device_ind_list[ind]:]
            else:
                info = out[device_ind_list[ind]:device_ind_list[ind + 1]]
            invalid = re.findall('\|Invalid\s*\|(.*)\|', info)
            vendor = re.findall('\|Vendor\s*\|(.*)\|', info)
            vendorpn = re.findall('\|Vendor PN\s*\|(.*)\|', info)
            invalid = [info.strip() for info in invalid]
            vendor = [info.strip() for info in vendor]
            vendorpn = [info.strip() for info in vendorpn]
            white_list_dict.update({rtn[ind]: list(zip(invalid, vendor, vendorpn))})
        return white_list_dict

    @classmethod
    def cli_show_whitelist(cls, caller_class, bus_info, vendor, vendorpn,
                           cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.07.21
        description: 执行scgbecli -d <device> show whitelist
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} show whitelist vendor={vendor} vendorpn={vendorpn}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        get_vendor = re.findall('\|Vendor\s*\|(.*)\|', out)[0].strip()
        get_vendorpn = re.findall('\|Vendor PN\s*\|(.*)\|', out)[0].strip()
        if get_vendor != vendor or get_vendorpn != vendorpn:
            CommonOperation.create_bug_problem(caller_class, key_word=f'CLI',
                                               description_word=f'命令返回{get_vendor} {get_vendorpn}跟预期{vendor} {vendorpn}不一致，报bug')

    @classmethod
    def check_cli_show_whitelist(cls, caller_class, bus_info, white_list, reverse: bool = False,
                                 cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.07.21
        description: 检查白名单是否在列表内
        """
        allwhitelist = CliOperation.cli_show_allwhitelist(caller_class, bus_info,
                                                          cmd_execute_address=cmd_execute_address)
        if not reverse:
            for white in white_list:
                if white not in allwhitelist.get(bus_info):
                    CommonOperation.create_bug_problem(caller_class, key_word=f'CLI',
                                                       description_word=f'{white}不在怪癖列表{allwhitelist.get(bus_info)}内，报bug')
        else:
            for white in white_list:
                if white in allwhitelist.get(bus_info):
                    CommonOperation.create_bug_problem(caller_class, key_word=f'CLI',
                                                       description_word=f'{white}在怪癖列表{allwhitelist.get(bus_info)}内，报bug')

    @classmethod
    def cli_delete_whitelist(cls, caller_class, bus_info, vendor, vendorpn,
                             cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2025.07.21
        description: 执行scgbecli -d <device> delete whitelist
        """
        if ' ' in vendor:
            vendor = vendor.replace(' ', '\ ')
        cmd = f'{constants.SCGBECLI64} -d {bus_info} delete whitelist vendor={vendor} vendorpn={vendorpn}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)

    @classmethod
    def check_output_format(cls, caller_class, output: str):
        info_lst = output.split('\n')
        info_lst = [info.rstrip() for info in info_lst]
        record_flag = True
        total_len = 0
        check_lst = []
        equals_flag = True
        front_space = 0
        front_len = 0
        for info in info_lst:
            if equals_flag is True:
                if '=' in info:
                    front_space = info.find(findall(r'(\w)', info)[0])
                    front_len = info.find('=')
                    equals_flag = False
                    continue
            else:
                pattern = r'^\s{%d}\w' % front_space
                if '=' not in info:
                    equals_flag = True
                    continue
                if not findall(pattern, info) or info.find('=') != front_len:
                    CommonOperation.create_bug_problem(
                        caller_class,
                        key_word='CLI',
                        description_word=f"CLI指令回显格式错误, 等号未对齐",
                        expect_info=str(front_len),
                        result_info=str(info.find('='))
                    )
        for info in info_lst:
            if record_flag is True:
                if findall(r'\s+\+-+\+$', info):
                    total_len = len(info)
                    record_flag = False
                    continue
            else:
                if findall(r'\s+\+-+\+$', info):
                    record_flag = True
                    bug_flag = False
                    for i in range(len(check_lst) - 1):
                        bug_check_0 = False if check_lst[i] == check_lst[i + 1] else True
                        bug_check_1 = False if sum(check_lst[i]) + len(check_lst[i]) - 1 == total_len else True
                        bug_flag = all([bug_check_0, bug_check_1])
                    log.info(f'check_list: {str(check_lst)}')
                    if bug_flag:
                        CommonOperation.create_bug_problem(
                            caller_class,
                            key_word='CLI',
                            description_word='CLI指令回显格式错误，框图未对齐'
                        )

                para_list = re.split(r'[\|\+]', info)
                if not para_list:
                    CommonOperation.create_bug_problem(
                        caller_class,
                        key_word='CLI',
                        description_word='CLI指令回显格式错误,框图中间存在空行'
                    )
                para_num_list = [len(para) for para in para_list]
                check_lst.append(para_num_list)

    @classmethod
    def get_reg_value(cls, device_bdf, width, addr, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author:         jianghe
        date:           2025.05.06
        description:    获取寄存器的值，例如，scgbecli -d 0000:31:00.0 get reg type=A width=32 addr=0x8B071004
        """
        cmd = f'{constants.SCGBECLI64} -d {device_bdf} get reg type=A width={width} addr={addr}'
        code, out, err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address)
        CliOperation.check_cli_success(ScriptBase, cmd, code, out, err)
        found = re.findall(f'\|A\s*\|{addr}\s*\|(.*)\|0\s*\|None\s*\|', out)
        if len(found) > 0:
            return found[0].strip()
        else:
            CommonOperation.create_bug_problem(ScriptBase, key_word='CLI',
                                               description_word=f'命令{cmd}的返回信息没有预期值，'
                                                                f'返回信息是{code}\n{out}\n{err}')
            return ''

        # cmd = f'{constants.SCGBECLI64} -d {device_bdf} get reg type=A width={width} addr={addr} j'
        # code, out, err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address)
        # CliOperation.check_cli_success(ScriptBase, cmd, code, out, err)
        # found = re.findall('"Value":\s*"(0x[0-9a-f]+)"', out)
        # if len(found) > 0:
        #     return found[0]
        # else:
        #     CommonOperation.create_bug_problem(ScriptBase, key_word='CLI',
        #                                        description_word=f'命令{cmd}的返回信息没有预期值，'
        #                                                         f'返回信息是{code}\n{out}\n{err}')
        #     return ''

    @classmethod
    def modify_bin(cls, filename, position, new_byte):
        """
        author: jianghe
        date  : 20250906
        description: 修改二进制文件，例如position=0x1A3，new_byte='\x62\x18'
        """
        # 备份
        new_file = f"/root/image_modify_{time.strftime('%y%m%d%H%M%S')}"
        cmd = f"cp {filename} {new_file}"
        CommonOperation.execute_command_with_check(cls, cmd)
        cmd = f"echo -n -e '{new_byte}' | dd of={new_file} bs=1 seek=$(({position})) conv=notrunc"
        CommonOperation.execute_command_with_check(cls, cmd)
        return new_file

    @classmethod
    def debug_upgrde_packet(cls, caller_class, dev_para, file, exec_addr=CmdExecuteAdressEnum.SERVER.value):
        """
        author: jianghe
        date  : 2025.10.23
        description: debug命令升级32m大包
        """
        cmd = f'{constants.SCGBECLI64} -d {dev_para} debug upgrade packet {file}'
        code, output, stderr = CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=exec_addr,
                                                                           timeout=3600)
        CliOperation.check_cli_success(caller_class, cmd, code, output, stderr)

    @classmethod
    def get_config_all_key_value(cls):
        """
        author: jianghe
        date  : 2025.10.23
        description: 获取show config
        """
        key_list = ['isInitOob', 'isInitC2C', 'isInitLan', 'isInitRdma', 'isInitLldp', 'isInitHeartBeat', 'isInitFlm',
                    'isSupportOpt', 'reserved0', 'logPersistOn', 'core0LogLevel', 'core1LogLevel', 'core2LogLevel',
                    'core3LogLevel', 'core4LogLevel', 'core5LogLevel', 'logSerial', 'logCfg', 'timeout', 'retryThresh',
                    'fragThresh', 'fwType', 'fwPackage', 'reserved1', 'fwType', 'packMagicNum', 'fwCount', 'packTime',
                    'packLen', 'packChecksum', 'packVersion', 'packName', 'reserved2', 'socThresholdWarnh',
                    'socThresholdWarnl', 'socThresholdCriticalh', 'socThresholdCriticall', 'socThresholdAlarmh',
                    'socThresholdAlarml', 'boardThresholdWarnh', 'boardThresholdWarnl', 'boardThresholdCriticalh',
                    'boardThresholdCriticall', 'boardThresholdAlarmh', 'boardThresholdAlarml', 'isActiveRst',
                    'evtMsgeGlobalEnable', 'pldmTid', 'reserved3', 'slaveAddr', 'reserved4', 'supportEidPersist', 'eid',
                    'addr', 'isDiscoveryNotify', 'maxRecvReqMsgNum', 'maxSendReqMsgNum', 'maxSendReqMsgNumPerPoint',
                    'recvPacketTimeOutMs', 'maxMsgDataLen', 'maxPacketDataLen', 'isDiscoverd', 'destEid', 'destphyAddr',
                    'reserved5', 'supportEidPersist', 'eid', 'addr', 'isDiscoveryNotify', 'maxRecvReqMsgNum',
                    'maxSendReqMsgNum', 'maxSendReqMsgNumPerPoint', 'recvPacketTimeOutMs', 'maxMsgDataLen',
                    'maxPacketDataLen', 'isDiscoverd', 'destEid', 'destphyAddr', 'reserved6', 'workMode',
                    'mctpPciePayload', 'mctpSmbusPayload', 'mctpPcieLimit', 'pcieEndian', 'mctpPcieVer',
                    'mctpPcieRoute', 'usedFp', 'bpOnthreshlod', 'bpOffthreshlod', 'ptIsNoDrop', 'rsvdIsNoDrop',
                    'proxyNoDrop', 'lldpNoDrop', 'portTcId', 'l2bDescCnt', 'm2xDescCnt', 'x2mDescCnt', 'bannerMesTime',
                    'bootRetryCount', 'vlanMode', 'vlanId', 'reserved7', 'bannerMesTime', 'bootRetryCount', 'vlanMode',
                    'vlanId', 'reserved8', 'bannerMesTime', 'bootRetryCount', 'vlanMode', 'vlanId', 'reserved9',
                    'bannerMesTime', 'bootRetryCount', 'vlanMode', 'vlanId', 'reserved10', 'entrynum', 'valid',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'entrynum', 'valid',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'isvalid', 'extinfo', 'vendor', 'vendorPn', 'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime',
                    'warnSwitch', 'warnSwitch', 'warnSwitch', 'warnSwitch', 'entrynum', 'valid', 'isvalid', 'rsv',
                    'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor',
                    'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'isvalid', 'rsv', 'vendor', 'vendorPn', 'entrynum', 'valid', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime', 'isvalid', 'rsv', 'vendor', 'vendorPn',
                    'linkTime', 'absleve', 'losleve', 'rsv2', 'filterTime', 'isvalid', 'warnSwitch', 'isvalid',
                    'warnSwitch', 'isvalid', 'warnSwitch', 'isvalid', 'warnSwitch', 'isvalid', 'fec', 'speed', 'status',
                    'fctx', 'fcrx', 'defextinfo', 'linktime', 'abslevel', 'loslevel', 'rsv2', 'filterTime', 'isvalid',
                    'fec', 'speed', 'status', 'fctx', 'fcrx', 'defextinfo', 'linktime', 'abslevel', 'loslevel', 'rsv2',
                    'filterTime', 'isvalid', 'fec', 'speed', 'status', 'fctx', 'fcrx', 'defextinfo', 'linktime',
                    'abslevel', 'loslevel', 'rsv2', 'filterTime', 'isvalid', 'fec', 'speed', 'status', 'fctx', 'fcrx',
                    'defextinfo', 'linktime', 'abslevel', 'loslevel', 'rsv2', 'filterTime', 'userAnEn', 'userAnEn',
                    'userAnEn', 'userAnEn', 'portstatus0', 'portstatus1', 'portstatus2', 'portstatus3', 'chan', 'addr',
                    'chan', 'addr', 'chan', 'rsv1', 'smbusmatch', 'eepWP', 'addr1', 'addr2', 'isvalid', 'tx_pre_10G',
                    'tx_main_10G', 'tx_post_10G', 'tx_pre_25G', 'tx_main_25G', 'tx_post_25G', 'isvalid', 'tx_pre_10G',
                    'tx_main_10G', 'tx_post_10G', 'tx_pre_25G', 'tx_main_25G', 'tx_post_25G', 'isvalid', 'tx_pre_10G',
                    'tx_main_10G', 'tx_post_10G', 'tx_pre_25G', 'tx_main_25G', 'tx_post_25G', 'isvalid', 'tx_pre_10G',
                    'tx_main_10G', 'tx_post_10G', 'tx_pre_25G', 'tx_main_25G', 'tx_post_25G']
        default_value_list = ['1', '1', '1', '1', '1', '1', '1', '1', '0', '1', '4', '4', '4', '4', '4', '4', '1', '0',
                              '20000', '2', '65535', '268423164', '268423164', '0', '2683961340', '0', '0', '0', '0',
                              '0', '0', '0', '0', '90', '5', '95', '10', '105', '15', '105', '5', '108', '10', '120',
                              '15', '0', '0', '0', '0', '50', '0', '1', '0', '0', '0', '1', '8', '8', '1000', '5120',
                              '64', '0', '0', '0', '0', '1', '0', '0', '0', '1', '8', '8', '100', '5120', '64', '0',
                              '0', '0', '0', '10', '1', '1', '0', '1', '1', '2', '0', '20480', '18432', '0', '0', '0',
                              '0', '0', '5', '5', '5', '0', '0', '0', '1', '0', '0', '0', '0', '1', '0', '0', '0', '0',
                              '1', '0', '0', '0', '0', '1', '0', '254', '1', '1', '0', 'SONT', 'S2185-BD1C', '1', '0',
                              'LINKTEL', 'LX6501CDH', '1', '0', 'WTD', 'RTXM330-551', '1', '0', 'Hisense',
                              'LTF8505-BC+', '1', '0', 'HG GENUINE', 'MTRA-3A90A', '1', '0', 'ACCELINK',
                              'OEO-M100-6485Q28', '1', '0', 'LUXSHARE-TECH', 'L9ZQF012-SD-R', '1', '0', 'INNOLIGHT',
                              'TR-FC85S-N00-H3C', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '',
                              '', '0', '0', '', '', '0', '0', '', '', '40', '0', '1', '1', 'Hisense', 'LTF8505-BC+',
                              '300', '0', '0', '0', '1000', '1', '19', 'INNOLIGHT', 'TR-FC85S-N00-H3C', '300', '0', '1',
                              '0', '1000', '0', '17', '', '', '300', '0', '1', '0', '1000', '0', '17', '', '', '300',
                              '0', '1', '0', '1000', '0', '17', '', '', '300', '0', '1', '0', '1000', '0', '17', '', '',
                              '300', '0', '1', '0', '1000', '0', '17', '', '', '300', '0', '1', '0', '1000', '0', '17',
                              '', '', '300', '0', '1', '0', '1000', '0', '17', '', '', '300', '0', '1', '0', '1000',
                              '0', '17', '', '', '300', '0', '1', '0', '1000', '0', '17', '', '', '300', '0', '1', '0',
                              '1000', '0', '17', '', '', '300', '0', '1', '0', '1000', '0', '17', '', '', '300', '0',
                              '1', '0', '1000', '0', '17', '', '', '300', '0', '1', '0', '1000', '0', '17', '', '',
                              '300', '0', '1', '0', '1000', '0', '17', '', '', '300', '0', '1', '0', '1000', '0', '17',
                              '', '', '300', '0', '1', '0', '1000', '0', '17', '', '', '300', '0', '1', '0', '1000',
                              '0', '17', '', '', '300', '0', '1', '0', '1000', '0', '17', '', '', '300', '0', '1', '0',
                              '1000', '0', '17', '', '', '300', '0', '1', '0', '1000', '0', '17', '', '', '300', '0',
                              '1', '0', '1000', '0', '17', '', '', '300', '0', '1', '0', '1000', '0', '17', '', '',
                              '300', '0', '1', '0', '1000', '0', '17', '', '', '300', '0', '1', '0', '1000', '0', '17',
                              '', '', '300', '0', '1', '0', '1000', '0', '17', '', '', '300', '0', '1', '0', '1000',
                              '0', '17', '', '', '300', '0', '1', '0', '1000', '0', '17', '', '', '300', '0', '1', '0',
                              '1000', '0', '17', '', '', '300', '0', '1', '0', '1000', '0', '17', '', '', '300', '0',
                              '1', '0', '1000', '0', '17', '', '', '300', '0', '1', '0', '1000', '0', '17', '', '',
                              '300', '0', '1', '0', '1000', '0', '17', '', '', '300', '0', '1', '0', '1000', '0', '17',
                              '', '', '300', '0', '1', '0', '1000', '0', '17', '', '', '300', '0', '1', '0', '1000',
                              '0', '17', '', '', '300', '0', '1', '0', '1000', '0', '17', '', '', '300', '0', '1', '0',
                              '1000', '0', '17', '', '', '300', '0', '1', '0', '1000', '0', '17', '', '', '300', '0',
                              '1', '0', '1000', '1', '1', '1', '1', '6', '1', '1', '0', 'LUXSHARE-ICT',
                              'P9Z0SMB01-SD-T', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '',
                              '0', '0', '', '', '5', '0', '0', '0', '', '', '0', '0', '0', '0', '0', '0', '0', '', '',
                              '0', '0', '0', '0', '0', '0', '0', '', '', '0', '0', '0', '0', '0', '0', '0', '', '', '0',
                              '0', '0', '0', '0', '0', '0', '', '', '0', '0', '0', '0', '0', '1', '1', '1', '1', '1',
                              '1', '1', '1', '1', '15', '15', '0', '0', '0', '17', '300', '0', '1', '0', '1000', '1',
                              '15', '15', '0', '0', '0', '17', '300', '0', '1', '0', '1000', '1', '15', '15', '0', '0',
                              '0', '17', '300', '0', '1', '0', '1000', '1', '15', '15', '0', '0', '0', '17', '300', '0',
                              '1', '0', '1000', '1', '1', '1', '1', '0', '0', '0', '0', '4', '80', '4', '81', '14', '0',
                              '52', '49', '50', '51', '1', '0', '16', '8', '0', '21', '12', '1', '0', '16', '8', '0',
                              '21', '12', '1', '0', '16', '8', '0', '21', '12', '1', '0', '16', '8', '0', '21', '12']
        return key_list, default_value_list

    @classmethod
    def get_config_set_key_value(cls, type=0, choose_one=False):
        """
        author: jianghe
        date  : 2025.10.23
        description: 获取show config
        """
        key_list, default_value_list = CliOperation.get_config_all_key_value()
        other_value_list = ['1', '1', '1', '1', '1', '1', '1', '1', '0', '1', '4', '4', '4', '4', '4', '4', '1', '0',
                            '20000', '2',
                            '65535', '268423164', '268423164', '0', '2683961340', '0', '0', '0', '0', '0', '0', '0',
                            '0', '90', '5', '95',
                            '10', '105', '15', '105', '5', '108', '10', '120', '15', '0', '0', '0', '0', '50', '0',
                            '1', '10', '0', '0',
                            '1', '8', '8', '1000', '5120', '64', '1', '8', '37376', '0', '1', '0', '0', '0', '1', '8',
                            '8', '100', '5120',
                            '64', '0', '0', '0', '0', '10', '1', '1', '0', '1', '1', '2', '0', '20480', '18432', '0',
                            '0', '0', '0', '0',
                            '5', '5', '5', '0', '0', '0', '1', '0', '0', '0', '0', '1', '0', '0', '0', '0', '1', '0',
                            '0', '0', '0', '1',
                            '0', '254', '1', '1', '0', 'LUXSHARE-ICT', 'P9Z0SMB01-SD-T', '1', '0', 'SONT',
                            'S2185-BD1C', '1', '0',
                            'LINKTEL', 'LX6501CDH', '1', '0', 'WTD', 'RTX330-551', '1', '0', 'Hisense', 'LTF8505-BC+',
                            '1', '0',
                            'HG GENUINE', 'MTRA-3A90A', '0', '0', 'ACCELINK', 'OEO-M100-6485Q28', '0', '0',
                            'LUXSHARE-TECH',
                            'L9ZQF012-SD-R', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '',
                            '0', '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0', '0', '', '', '0',
                            '0', '', '', '0',
                            '0', '', '', '40', '0', '0', '0', '', '', '300', '0', '0', '0', '1000', '0', '0', '', '',
                            '300', '0', '0', '0',
                            '1000', '0', '0', '', '', '300', '0', '0', '0', '1000', '0', '0', '', '', '300', '0', '0',
                            '0', '1000', '0',
                            '0', '', '', '300', '0', '0', '0', '1000', '0', '0', '', '', '300', '0', '0', '0', '1000',
                            '0', '0', '', '',
                            '300', '0', '0', '0', '1000', '0', '0', '', '', '300', '0', '0', '0', '1000', '0', '0',
                            '', '', '300', '0',
                            '0', '0', '1000', '0', '0', '', '', '300', '0', '0', '0', '1000', '0', '0', '', '', '300',
                            '0', '0', '0',
                            '1000', '0', '0', '', '', '300', '0', '0', '0', '1000', '0', '0', '', '', '300', '0', '0',
                            '0', '1000', '0',
                            '0', '', '', '300', '0', '0', '0', '1000', '0', '0', '', '', '300', '0', '0', '0', '1000',
                            '0', '0', '', '',
                            '300', '0', '0', '0', '1000', '0', '0', '', '', '300', '0', '0', '0', '1000', '0', '0',
                            '', '', '300', '0',
                            '0', '0', '1000', '0', '0', '', '', '300', '0', '0', '0', '1000', '0', '0', '', '', '300',
                            '0', '0', '0',
                            '1000', '0', '0', '', '', '300', '0', '0', '0', '1000', '0', '0', '', '', '300', '0', '0',
                            '0', '1000', '0',
                            '0', '', '', '300', '0', '0', '0', '1000', '0', '0', '', '', '300', '0', '0', '0', '1000',
                            '0', '0', '', '',
                            '300', '0', '0', '0', '1000', '0', '0', '', '', '300', '0', '0', '0', '1000', '0', '0',
                            '', '', '300', '0',
                            '0', '0', '1000', '0', '0', '', '', '300', '0', '0', '0', '1000', '0', '0', '', '', '300',
                            '0', '0', '0',
                            '1000', '0', '0', '', '', '300', '0', '0', '0', '1000', '0', '0', '', '', '300', '0', '0',
                            '0', '1000', '0',
                            '0', '', '', '300', '0', '0', '0', '1000', '0', '0', '', '', '300', '0', '0', '0', '1000',
                            '0', '0', '', '',
                            '300', '0', '0', '0', '1000', '0', '0', '', '', '300', '0', '0', '0', '1000', '0', '0',
                            '', '', '300', '0',
                            '0', '0', '1000', '0', '0', '', '', '300', '0', '0', '0', '1000', '0', '0', '', '', '300',
                            '0', '0', '0',
                            '1000', '0', '0', '', '', '300', '0', '0', '0', '1000', '0', '0', '', '', '300', '0', '0',
                            '0', '1000', '1',
                            '1', '1', '1', '6', '1', '1', '0', 'LUXSHARE-ICT', 'P9Z0SMB01-SD-T', '0', '0', '', '',
                            '0', '0', '', '', '0',
                            '0', '', '', '0', '0', '', '', '0', '0', '', '', '5', '0', '0', '0', '', '', '0', '0',
                            '0', '0', '0', '0', '0',
                            '', '', '0', '0', '0', '0', '0', '0', '0', '', '', '0', '0', '0', '0', '0', '0', '0', '',
                            '', '0', '0', '0',
                            '0', '0', '0', '0', '', '', '0', '0', '0', '0', '0', '1', '1', '1', '1', '1', '1', '1',
                            '1', '1', '15', '15',
                            '0', '0', '0', '0', '300', '0', '0', '0', '1000', '1', '15', '15', '0', '0', '0', '0',
                            '300', '0', '0', '0',
                            '1000', '1', '15', '15', '0', '0', '0', '0', '300', '0', '0', '0', '1000', '1', '15',
                            '15', '0', '0', '0', '0',
                            '300', '0', '0', '0', '1000', '1', '1', '1', '1', '0', '0', '0', '0', '4', '80', '4',
                            '81', '14', '0', '52',
                            '49', '50', '51']
        key_value_default = {'cfgreg1': '1', 'cfgreg2': '2', 'cfgreg3': '3', 'cfgreg4': '4',
                             'isInitOob': '1', 'isInitC2C': '1', 'isInitLan': '1', 'isInitRdma': '1',
                             'isInitLldp': '1', 'isInitHeartBeat': '1', 'isInitFlm': '1', 'isSupportOpt': '0',
                             'reserved0': '0', 'logPersistOn': '1', 'core0LogLevel': '4', 'core1LogLevel': '4',
                             'core2LogLevel': '4', 'core3LogLevel': '4', 'core4LogLevel': '4', 'core5LogLevel': '4',
                             'logSerial': '1', 'logCfg': '0', 'slaveUart': '60', 'timeout': '20000',
                             'retryThresh': '2', 'fragThresh': '65535', 'fwType': '2683961340',
                             'fwPackage': '18158513697557872980', 'reserved1': '0', 'packMagicNum': '847210701',
                             'fwCount': '5', 'packTime': '1762593088', 'packLen': '2795072',
                             'packChecksum': '1741318575', 'packVersion': '393236',
                             'packName': 'ps3_image_package.bin', 'reserved2': '0', 'socThresholdWarnh': '105',
                             'socThresholdWarnl': '5', 'socThresholdCriticalh': '108', 'socThresholdCriticall': '10',
                             'socThresholdAlarmh': '120', 'socThresholdAlarml': '15', 'boardThresholdWarnh': '105',
                             'boardThresholdWarnl': '5', 'boardThresholdCriticalh': '108',
                             'boardThresholdCriticall': '10', 'boardThresholdAlarmh': '120',
                             'boardThresholdAlarml': '15', 'isActiveRst': '0', 'evtMsgeGlobalEnable': '0',
                             'reserved3': '0', 'slaveAddr': '50', 'reserved4': '0', 'supportEidPersist': '1',
                             'eid': '0', 'addr': '81', 'isDiscoveryNotify': '0', 'maxRecvReqMsgNum': '1',
                             'maxSendReqMsgNum': '1', 'maxSendReqMsgNumPerPoint': '1', 'recvPacketTimeOutMs': '100',
                             'maxMsgDataLen': '5120', 'maxPacketDataLen': '64', 'reserved5': '0', 'reserved6': '0',
                             'workMode': '10', 'mctpPciePayload': '1', 'mctpSmbusPayload': '1', 'mctpPcieLimit': '0',
                             'pcieEndian': '1', 'mctpPcieVer': '1', 'mctpPcieRoute': '2', 'usedFp': '0',
                             'bpOnthreshlod': '0', 'bpOffthreshlod': '0', 'ptIsNoDrop': '0', 'rsvdIsNoDrop': '0',
                             'proxyNoDrop': '0', 'lldpNoDrop': '0', 'portTcId': '0', 'l2bDescCnt': '5',
                             'm2xDescCnt': '5', 'x2mDescCnt': '5', 'port0': '0', 'port1': '0', 'port2': '0',
                             'port3': '0', 'bannerMesTime': '0', 'bootRetryCount': '0', 'vlanMode': '0',
                             'vlanId': '1', 'reserved7': '0', 'reserved8': '0', 'reserved9': '0', 'reserved10': '0',
                             'active': '1', 'vfCount': '64', 'entrynum': '5', 'valid': '0', 'isvalid': '1',
                             'rsv': '0', 'vendor': '', 'vendorPn': '', 'linkTime': '0', 'absleve': '0', 'losleve': '0',
                             'rsv2': '0', 'filterTime': '1000', 'warnSwitch': '1', 'fec': '15', 'speed': '15',
                             'status': '0', 'fctx': '0', 'fcrx': '0', 'rsv1': '0', 'linktime': '300', 'abslevel': '0',
                             'loslevel': '0', 'userAnEn': '1', 'isdrop': '1', 'portstatus0': '0', 'portstatus1': '0',
                             'portstatus2': '0', 'portstatus3': '0', 'chan': '14', 'smbusmatch': '48', 'eepWP': '49',
                             'addr1': '50', 'addr2': '51'}
        # code review 2025/11/12 jhe: key_value_1当前是默认值
        key_value_1 = {'cfgreg1': '1', 'cfgreg2': '2', 'cfgreg3': '3', 'cfgreg4': '4',
                       'isInitOob': '1', 'isInitC2C': '1', 'isInitLan': '1', 'isInitRdma': '1',
                       'isInitLldp': '1', 'isInitHeartBeat': '1', 'isInitFlm': '1', 'isSupportOpt': '0',
                       'reserved0': '0', 'logPersistOn': '1', 'core0LogLevel': '4', 'core1LogLevel': '4',
                       'core2LogLevel': '4', 'core3LogLevel': '4', 'core4LogLevel': '4', 'core5LogLevel': '4',
                       'logSerial': '1', 'logCfg': '0', 'slaveUart': '60', 'timeout': '20000',
                       'retryThresh': '2', 'fragThresh': '65535', 'fwType': '2683961340',
                       'fwPackage': '18158513697557872980', 'reserved1': '0', 'packMagicNum': '847210701',
                       'fwCount': '5', 'packTime': '1762593088', 'packLen': '2795072',
                       'packChecksum': '1741318575', 'packVersion': '393236',
                       'packName': 'ps3_image_package.bin', 'reserved2': '0', 'socThresholdWarnh': '105',
                       'socThresholdWarnl': '5', 'socThresholdCriticalh': '108', 'socThresholdCriticall': '10',
                       'socThresholdAlarmh': '120', 'socThresholdAlarml': '15', 'boardThresholdWarnh': '105',
                       'boardThresholdWarnl': '5', 'boardThresholdCriticalh': '108',
                       'boardThresholdCriticall': '10', 'boardThresholdAlarmh': '120',
                       'boardThresholdAlarml': '15', 'isActiveRst': '0', 'evtMsgeGlobalEnable': '0',
                       'reserved3': '0', 'slaveAddr': '50', 'reserved4': '0', 'supportEidPersist': '1',
                       'eid': '0', 'addr': '81', 'isDiscoveryNotify': '0', 'maxRecvReqMsgNum': '1',
                       'maxSendReqMsgNum': '1', 'maxSendReqMsgNumPerPoint': '1', 'recvPacketTimeOutMs': '100',
                       'maxMsgDataLen': '5120', 'maxPacketDataLen': '64', 'reserved5': '0', 'reserved6': '0',
                       'workMode': '10', 'mctpPciePayload': '1', 'mctpSmbusPayload': '1', 'mctpPcieLimit': '0',
                       'pcieEndian': '1', 'mctpPcieVer': '1', 'mctpPcieRoute': '2', 'usedFp': '0',
                       'bpOnthreshlod': '0', 'bpOffthreshlod': '0', 'ptIsNoDrop': '0', 'rsvdIsNoDrop': '0',
                       'proxyNoDrop': '0', 'lldpNoDrop': '0', 'portTcId': '0', 'l2bDescCnt': '5',
                       'm2xDescCnt': '5', 'x2mDescCnt': '5', 'port0': '0', 'port1': '0', 'port2': '0',
                       'port3': '0', 'bannerMesTime': '0', 'bootRetryCount': '0', 'vlanMode': '0',
                       'vlanId': '1', 'reserved7': '0', 'reserved8': '0', 'reserved9': '0', 'reserved10': '0',
                       'active': '1', 'vfCount': '64', 'entrynum': '5', 'valid': '0', 'isvalid': '1',
                       'rsv': '0', 'vendor': '', 'vendorPn': '', 'linkTime': '0', 'absleve': '0', 'losleve': '0',
                       'rsv2': '0', 'filterTime': '1000', 'warnSwitch': '1', 'fec': '15', 'speed': '15',
                       'status': '0', 'fctx': '0', 'fcrx': '0', 'rsv1': '0', 'linktime': '300', 'abslevel': '0',
                       'loslevel': '0', 'userAnEn': '1', 'isdrop': '1', 'portstatus0': '0', 'portstatus1': '0',
                       'portstatus2': '0', 'portstatus3': '0', 'chan': '14', 'smbusmatch': '48', 'eepWP': '49',
                       'addr1': '50', 'addr2': '51'}
        not_get_list = ['rsv']
        if type == 0 and choose_one:
            while True:
                ind = random.randint(0, len(key_list))
                if default_value_list[ind] != '' and key_list[ind] not in not_get_list:
                    break
            occurrence = key_list[:ind].count(key_list[ind]) + 1
            log.info(f'选择的字段{key_list[ind]}，字段值{default_value_list[ind]}，次数{occurrence}')
            return key_list[ind], default_value_list[ind], occurrence
        elif type == 0 and not choose_one:
            key_value_list = []
            for ind in range(len(key_list)):
                if default_value_list[ind] != '' and default_value_list[ind] not in not_get_list:
                    occurrence = key_list[:ind].count(key_list[ind]) + 1
                    key_value_list.append([key_list[ind], default_value_list[ind], occurrence])
            log.info(f'选择的字段列表是{key_value_list}')
            return key_value_list
        elif type != 0 and choose_one:
            return [key_list, default_value_list]
        else:
            return [key_list, other_value_list]

    @classmethod
    def get_cli_show_config(cls, dev_para, exec_addr=CmdExecuteAdressEnum.SERVER.value, not_get=False,
                            check_ignore=False):
        """
        author: jianghe
        date  : 2025.10.23
        description: 获取show config
        """
        cmd = f'{constants.SCGBECLI64} -d {dev_para} show config'
        code, output, stderr = CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=exec_addr)
        if check_ignore:
            return
        CliOperation.check_cli_success(ScriptBase, cmd, code, output, stderr)
        if not_get:
            return
        ind_1 = output.find('Device Info:')
        ind_2 = output.find('Configuration Info:')

        device_info_key_list = []
        device_info_value_list = []
        cfg_info_key_list = []
        cfg_info_value_list = []

        device_info = output[ind_1:ind_2]
        conf_info = output[ind_2:]
        for line in device_info.split('\n'):
            found = re.findall('\|(.*)\s*\|(.*)\s*\|', line)
            if found:
                device_info_key_list.append(found[0][0].strip())
                device_info_value_list.append(found[0][1].strip())
        for line in conf_info.split('\n'):
            found = re.findall('\|(.*)\s*\|(.*)\s*\|', line)
            if found:
                cfg_info_key_list.append(found[0][0].strip())
                cfg_info_value_list.append(found[0][1].strip())

        device_info_key_list = device_info_key_list[1:]
        device_info_value_list = device_info_value_list[1:]
        cfg_info_key_list = cfg_info_key_list[1:]
        cfg_info_value_list = cfg_info_value_list[1:]

        return {'Device Info': [device_info_key_list, device_info_value_list],
                'Configuration Info': [cfg_info_key_list, cfg_info_value_list]}

    @classmethod
    def get_cli_show_config_verbosity(cls, dev_para, exec_addr=CmdExecuteAdressEnum.SERVER.value, not_get=False,
                                      check_ignore=False):
        """
        author: jianghe
        date  : 2025.10.23
        description: 获取show config
        """
        cmd = f'{constants.SCGBECLI64} -d {dev_para} show config verbosity'
        code, output, stderr = CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=exec_addr)
        if check_ignore:
            return
        CliOperation.check_cli_success(ScriptBase, cmd, code, output, stderr)
        if not_get:
            return

        device_info_key_list = []
        device_info_dft_list = []
        device_info_cur_list = []
        device_info_next_list = []

        for line in output.split('\n'):
            found = re.findall('\|(.*)\s*\|(.*)\s*\|(.*)\s*\|(.*)\s*\|', line)
            if found:
                device_info_key_list.append(found[0][0].strip())
                device_info_cur_list.append(found[0][1].strip())
                device_info_dft_list.append(found[0][2].strip())
                device_info_next_list.append(found[0][3].strip())

        device_info_key_list = device_info_key_list[1:]
        device_info_dft_list = device_info_dft_list[1:]
        device_info_cur_list = device_info_cur_list[1:]
        device_info_next_list = device_info_next_list[1:]

        return [device_info_key_list, device_info_cur_list, device_info_dft_list, device_info_next_list]

    @classmethod
    def get_cli_show_config_key(cls, dev_para, key, exec_addr=CmdExecuteAdressEnum.SERVER.value, not_get=False,
                                check_ignore=False):
        """
        author: jianghe
        date  : 2025.10.23
        description: 获取show config <key>
        """
        cmd = f'{constants.SCGBECLI64} -d {dev_para} show config {key}'
        code, output, stderr = CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=exec_addr)
        if check_ignore:
            return
        CliOperation.check_cli_success(ScriptBase, cmd, code, output, stderr)
        if not_get:
            return
        value_list = []
        for param in key.split(' '):
            if param:
                found = re.findall(f'\|{param}\s*\|(.*)\s*\|\n', output)
                value_list.append(found[0].strip())
        return value_list

    @classmethod
    def cli_set_config_key(cls, dev_para, key, value, type, occurnum='0',
                           exec_addr=CmdExecuteAdressEnum.SERVER.value, check_ignore=False):
        """
        author: jianghe
        date  : 2025.10.23
        description: set config <key>
        """
        cmd = f'{constants.SCGBECLI64} -d {dev_para} set config name={key} value={value} type={type} occurnum={occurnum}'
        code, output, stderr = CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=exec_addr)
        if check_ignore:
            return
        CliOperation.check_cli_success(ScriptBase, cmd, code, output, stderr)

    @classmethod
    def cli_set_config_default(cls, dev_para, exec_addr=CmdExecuteAdressEnum.SERVER.value, check_ignore=False):
        """
        author: jianghe
        date  : 2025.10.23
        description: set config <key>
        """
        cmd = f'{constants.SCGBECLI64} -d {dev_para} set config default'
        code, output, stderr = CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=exec_addr)
        if check_ignore:
            return
        CliOperation.check_cli_success(ScriptBase, cmd, code, output, stderr)

    @classmethod
    def get_cli_show_module(cls, dev_para: str, exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
                            not_get=False, check_ignore=False):
        """
        author: jianghe
        date  : 2025.10.27
        description: 执行/cx show module 获取属性值
        """
        prop_dict = {}
        prop_list = ['Identifier', 'Compliance', 'Cable Technology', 'Cable Type', 'OUI', 'Vendor Name',
                    'Vendor Part Number', 'Vendor Serial Number', 'Rev', 'Wave Length', 'Transfer Distance',
                    'Attenuation', 'FW Version', 'Digital Diagnostic Monitoring', 'Power Class', 'CDR TX', 'CDR RX',
                    'LOS Alarm', 'Temperature', 'Voltage', 'Bias Current', 'Rx Power Current', 'Tx Power Current']
        cmd = f'{constants.SCGBECLI64} -d {dev_para} show module'
        code, out, err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if check_ignore:
            return
        CliOperation.check_cli_success(ScriptBase, cmd, code, out, err)
        if not_get:
            return
        for prop in prop_list:
            if prop == 'Wave Length':
                if re.findall(f'{prop}\s*\(nm\)\s*\|(.*)\|', out):
                    prop_dict.update({prop: re.findall(f'{prop}\s*\(nm\)\s*\|(.*)\|', out)[0].strip()})
                else:
                    prop_dict.update({prop: None})
            elif prop == 'Transfer Distance':
                if re.findall(f'{prop}\s*\(m\)\s*\|(.*)\|', out):
                    prop_dict.update({prop: re.findall(f'{prop}\s*\(m\)\s*\|(.*)\|', out)[0].strip()})
                else:
                    prop_dict.update({prop: None})
            elif prop == 'Attenuation':
                if re.findall(f'{prop}\s*\(dB\)\s*\|(.*)\|', out):
                    prop_dict.update({prop: re.findall(f'{prop}\s*\(dB\)\s*\|(.*)\|', out)[0].strip()})
                else:
                    prop_dict.update({prop: None})
            elif prop == 'Temperature':
                if re.findall(f'{prop}\s*\(C\)\s*\|(.*)\|', out):
                    prop_dict.update({prop: re.findall(f'{prop}\s*\(C\)\s*\|(.*)\|', out)[0].strip()})
                else:
                    prop_dict.update({prop: None})
            elif prop == 'Voltage':
                if re.findall(f'{prop}\s*\(mV\)\s*\|(.*)\|', out):
                    prop_dict.update({prop: re.findall(f'{prop}\s*\(mV\)\s*\|(.*)\|', out)[0].strip()})
                else:
                    prop_dict.update({prop: None})
            elif prop == 'Bias Current':
                if re.findall(f'{prop}\s*\(mA\)\s*\|(.*)\|', out):
                    prop_dict.update({prop: re.findall(f'{prop}\s*\(mA\)\s*\|(.*)\|', out)[0].strip()})
                else:
                    prop_dict.update({prop: None})
            elif prop == 'Rx Power Current':
                if re.findall(f'{prop}\s*\(dBm\)\s*\|(.*)\|', out):
                    prop_dict.update({prop: re.findall(f'{prop}\s*\(dBm\)\s*\|(.*)\|', out)[0].strip()})
                else:
                    prop_dict.update({prop: None})
            elif prop == 'Tx Power Current':
                if re.findall(f'{prop}\s*\(dBm\)\s*\|(.*)\|', out):
                    prop_dict.update({prop: re.findall(f'{prop}\s*\(dBm\)\s*\|(.*)\|', out)[0].strip()})
                else:
                    prop_dict.update({prop: None})
            else:
                if re.findall(f'\|{prop}\s*\|(.*)\|', out):
                    prop_dict.update({prop: re.findall(f'\|{prop}\s*\|(.*)\|', out)[0].strip()})
                else:
                    prop_dict.update({prop: None})
        return prop_dict

    @classmethod
    def check_cli_show_module(cls, dev_para: str, check_prop_dict,
                              exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jianghe
        date  : 2025.10.27
        description: 执行/cx show fw 获取属性值
        """
        prop_dict = CliOperation.get_cli_show_module(dev_para, exec_addr)
        for prop, exp in check_prop_dict.items():
            cur = prop_dict.get(prop)
            if exp != cur:
                CommonOperation.create_bug_problem(ScriptBase, key_word=f'FW',
                                                   description_word=f'show module查询的{prop}不符合预期，'
                                                                    f'查出来是{cur}，期望是{exp}')
            else:
                log.info(f'show module中属性{prop}查出来与预期一致，是{cur}')

    @classmethod
    def get_cli_show_cable_ddm(cls, dev_para: str, exec_addr=CmdExecuteAdressEnum.CLI_DEFAULT.value,
                               not_get=False, check_ignore=False):
        """
        author: jianghe
        date  : 2025.10.27
        description: 执行/cx show cable ddm 获取属性值
        """
        cmd = f'{constants.SCGBECLI64} -d {dev_para} show cable ddm'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if check_ignore:
            return
        CliOperation.check_cli_success(ScriptBase, cmd, rtn_code, rtn_outputs, rtn_err)
        if not_get:
            return
        ind_cable_ddm_info = rtn_outputs.find('Cable DDM Information:')
        ind_ddm_flags = rtn_outputs.find('DDM Flags:')
        ind_channel_flags = rtn_outputs.find('Channel Flags:')
        ind_ddm_thresholds = rtn_outputs.find('DDM Thresholds:')

        cable_ddm_info = rtn_outputs[ind_cable_ddm_info:ind_ddm_flags]
        ddm_flags = rtn_outputs[ind_ddm_flags:ind_channel_flags]
        channel_flags = rtn_outputs[ind_channel_flags:ind_ddm_thresholds]
        ddm_thresholds = rtn_outputs[ind_ddm_thresholds:]

        cable_ddm_dict = {}
        for info in [cable_ddm_info, ddm_flags, channel_flags, ddm_thresholds]:
            prop_dict = {}
            if info != ddm_thresholds:
                for line in info.split('\n'):
                    found = re.findall(f'\|(.*)\s*\|(.*)\|', line)
                    if found:
                        key, value = found[0]
                        prop_dict.update({key.strip(): value.strip()})
            else:
                for line in info.split('\n'):
                    found = re.findall(f'\|(.*)\s*\|(.*)\|(.*)\|(.*)\|(.*)\|(.*)\|', line)
                    if found:
                        key = found[0][0]
                        value = found[0][1:]
                        new_value = []
                        for elem in value:
                            new_value.append(elem.strip())
                        prop_dict.update({key.strip(): new_value})
            if info == cable_ddm_info:
                prop_dict.pop('Key')
                cable_ddm_dict.update({'Cable DDM Information': prop_dict})
            if info == ddm_flags:
                prop_dict.pop('Key')
                cable_ddm_dict.update({'DDM Flags': prop_dict})
            if info == channel_flags:
                prop_dict.pop('Key')
                cable_ddm_dict.update({'Channel Flags': prop_dict})
            if info == ddm_thresholds:
                prop_dict.pop('Thresholds')
                cable_ddm_dict.update({'DDM Thresholds': prop_dict})

        return cable_ddm_dict

    @classmethod
    def cli_set_cable(cls, dev_para: str, page, offset, length, value,
                      exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value, check_ignore=False):
        """
        author: jianghe
        date  : 2025.10.27
        description: 执行/cx set cable
        """
        prop_dict = {}
        cmd = f'{constants.SCGBECLI64} -d {dev_para} set cable page={page} offset={offset} length={length} value={value}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if check_ignore:
            return
        CliOperation.check_cli_success(ScriptBase, cmd, rtn_code, rtn_outputs, rtn_err)

    @classmethod
    def cli_upgrade_eeprom(cls, dev_para: str, file_path: str = None,
                           exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value, check_ignore: bool = False):
        """
        author: jianghe
        date  : 2025.10.27
        description: scgbecli -d <device> upgrade eeprom file=<filepath>
        return: 无返回值
        """
        cmd = f'{constants.SCGBECLI64} -d {dev_para} upgrade eeprom file={file_path}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if check_ignore:
            return
        CliOperation.check_cli_success(ScriptBase, cmd, rtn_code, rtn_outputs, rtn_err)

    @classmethod
    def is_sup_hotplug(cls, bus_info: str, exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2026.01.09
        description: 查询是否支持热拔插
        return: 无返回值
        """
        cmd = f"find /sys/devices/ -name '{bus_info}' |grep pci"
        code, out, err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        log.info(f'命令{cmd}的执行结果{code}\n{out}\n{err}')
        switch = out.split('/')[-2]
        cmd = f"lspci -vvs {switch}"
        code, out, err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        log.info(f'命令{cmd}的执行结果{code}\n{out}\n{err}')
        if 'HotPlug+' in out:
            return True
        else:
            return False

    @classmethod
    def show_temp(cls, caller_class, bus_info, exec_addr=CmdExecuteAdressEnum.CLI_DEFAULT.value, not_get=False):
        """
        author: jianghe
        date  : 2026.01.13
        description: 查询板卡温度
        return: 无返回值
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} show temp'
        code, out, err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        if not_get:
            return
        found = re.findall('\|Temperature \|(\d+) C \|', out)
        return found[0]

    @classmethod
    def cli_set_loopback(cls, caller_class, bus_info, mode, exec_addr=CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2026.01.13
        description: 执行scgbecli -d <device> set loopback
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} set loopback loopback={mode}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)

    @classmethod
    def cli_set_filtertime(cls, caller_class, bus_info, time,
                         exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2026.01.13
        description: 执行scgbecli -d <device> set filtertime time=x
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} set filtertime time={time}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)

    @classmethod
    def cli_show_rx_fec(cls, caller_class, bus_info, exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2026.01.13
        description: 执行scgbecli -d <device> show rx fec symbol count
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} show rx fec symbol count'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        fec_histogram = {}
        found = re.findall('\|Corrective count\s*\|(\d+)\s*\|', out)
        fec_histogram.update({'Corrective count': found[0]})
        found = re.findall('\|Non correctable count\s*\|(\d+)\s*\|', out)
        fec_histogram.update({'Non correctable count': found[0]})
        found = re.findall('\|Number of symbol errors\s*\|(\d+)\s*\|', out)
        fec_histogram.update({'Number of symbol errors': found[0]})
        return fec_histogram

    @classmethod
    def cli_show_serdes_tx(cls, caller_class, bus_info, exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2026.01.13
        description: 执行scgbecli -d <device> show serdes tx
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} show serdes tx'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)

    @classmethod
    def cli_set_testmod(cls, caller_class, bus_info, mode, speed, connectmod,
                        exec_addr=CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2026.05.06
        description: 执行scgbecli -d <device> set testmode
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} set testmod mod={mode} speed={speed} connectmod={connectmod}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)

    @classmethod
    def cli_show_testmod(cls, caller_class, bus_info, exec_addr=CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2026.05.06
        description: 执行scgbecli -d <device> set testmode
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} show testmod'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        testmod = {}
        found = re.findall('\|Mod\s*\|([a-zA-Z0-9]+)\s*\|', out)
        testmod.update({'Mod': found[0]})
        found = re.findall('\|Speed\s*\|([a-zA-Z0-9]+)\s*\|', out)
        testmod.update({'Speed': found[0]})
        found = re.findall('\|ConnectMod\s*\|([a-zA-Z0-9]+)\s*\|', out)
        testmod.update({'ConnectMod': found[0]})
        return testmod

    @classmethod
    def check_cli_show_testmod(cls, caller_class, dev_para: str, check_prop_dict,
                               exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jianghe
        date  : 2026.05.06
        description: 执行show testmod 检查属性值
        """
        prop_dict = CliOperation.cli_show_testmod(caller_class, dev_para, exec_addr)
        for prop, exp in check_prop_dict.items():
            cur = prop_dict.get(prop)
            if exp != cur:
                CommonOperation.create_bug_problem(ScriptBase, key_word=f'FW',
                                                   description_word=f'show testmod查询的{prop}不符合预期，'
                                                                    f'查出来是{cur}，期望是{exp}')

    @classmethod
    def cli_set_prbs(cls, caller_class, bus_info, mode, lane,
                        exec_addr=CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2026.05.06
        description: 执行scgbecli -d <device> set prbs
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} set prbs mod={mode} lane={lane}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)

    @classmethod
    def cli_show_prbs(cls, caller_class, bus_info, exec_addr=CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2026.05.06
        description: 执行scgbecli -d <device> show prbs
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} show prbs'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        prbs = {}
        found = re.findall('\|Lane0 mode\s*\|([a-zA-Z0-9]+)\s*\|', out)
        prbs.update({'Lane0 mode': found[0]})
        found = re.findall('\|Lane1 mode\s*\|([a-zA-Z0-9]+)\s*\|', out)
        prbs.update({'Lane1 mode': found[0]})
        found = re.findall('\|Lane2 mode\s*\|([a-zA-Z0-9]+)\s*\|', out)
        prbs.update({'Lane2 mode': found[0]})
        found = re.findall('\|Lane3 mode\s*\|([a-zA-Z0-9]+)\s*\|', out)
        prbs.update({'Lane3 mode': found[0]})
        return prbs

    @classmethod
    def check_cli_show_prbs(cls, caller_class, dev_para: str, check_prop_dict,
                               exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jianghe
        date  : 2026.05.06
        description: 执行show prbs 检查属性值
        """
        prop_dict = CliOperation.cli_show_prbs(caller_class, dev_para, exec_addr)
        for prop, exp in check_prop_dict.items():
            cur = prop_dict.get(prop)
            if exp != cur:
                CommonOperation.create_bug_problem(ScriptBase, key_word=f'FW',
                                                   description_word=f'show prbs查询的{prop}不符合预期，'
                                                                    f'查出来是{cur}，期望是{exp}')

    @classmethod
    def cli_set_eq(cls, caller_class, bus_info, lane, pre, main, post, exec_addr=CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2026.05.06
        description: 执行scgbecli -d <device> set eq
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} set eq lane={lane} pre={pre} main={main} post={post}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)

    @classmethod
    def cli_show_eq(cls, caller_class, bus_info, exec_addr=CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2026.05.06
        description: 执行scgbecli -d <device> show eq
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} show eq'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        eq = {}
        found = re.findall('\|Lane0\s*\|(\d+)\s*\|(\d+)\s*\|(\d+)\s*\|', out)
        eq.update({'Lane0': found[0]})
        found = re.findall('\|Lane1\s*\|(\d+)\s*\|(\d+)\s*\|(\d+)\s*\|', out)
        eq.update({'Lane1': found[0]})
        found = re.findall('\|Lane2\s*\|(\d+)\s*\|(\d+)\s*\|(\d+)\s*\|', out)
        eq.update({'Lane2': found[0]})
        found = re.findall('\|Lane3\s*\|(\d+)\s*\|(\d+)\s*\|(\d+)\s*\|', out)
        eq.update({'Lane3': found[0]})
        return eq

    @classmethod
    def check_cli_show_eq(cls, caller_class, dev_para: str, check_prop_dict,
                            exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jianghe
        date  : 2026.05.06
        description: 执行show eq 检查属性值
        """
        prop_dict = CliOperation.cli_show_eq(caller_class, dev_para, exec_addr)
        for prop, exp in check_prop_dict.items():
            cur = prop_dict.get(prop)
            if exp != cur:
                CommonOperation.create_bug_problem(ScriptBase, key_word=f'FW',
                                                   description_word=f'show eq查询的{prop}不符合预期，'
                                                                    f'查出来是{cur}，期望是{exp}')

    @classmethod
    def cli_set_rx2tx(cls, caller_class, bus_info, state, lanemask,
                   exec_addr=CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2026.05.06
        description: 执行scgbecli -d <device> set rx2tx
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} set rx2tx state={state} lanemask={lanemask}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)

    @classmethod
    def cli_show_rx2tx(cls, caller_class, bus_info, exec_addr=CmdExecuteAdressEnum.CLI_DEFAULT.value):
        """
        author: jianghe
        date  : 2026.05.06
        description: 执行scgbecli -d <device> show rx2tx
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} show rx2tx'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, exec_addr)
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        rx2tx = {}
        found = re.findall('\|Lane0 mode\s*\|([a-zA-Z0-9]+)\s*\|', out)
        rx2tx.update({'Lane0 mode': found[0]})
        found = re.findall('\|Lane1 mode\s*\|([a-zA-Z0-9]+)\s*\|', out)
        rx2tx.update({'Lane1 mode': found[0]})
        found = re.findall('\|Lane2 mode\s*\|([a-zA-Z0-9]+)\s*\|', out)
        rx2tx.update({'Lane2 mode': found[0]})
        found = re.findall('\|Lane3 mode\s*\|([a-zA-Z0-9]+)\s*\|', out)
        rx2tx.update({'Lane3 mode': found[0]})
        return rx2tx

    @classmethod
    def check_cli_show_rx2tx(cls, caller_class, dev_para: str, check_prop_dict,
                          exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jianghe
        date  : 2026.05.06
        description: 执行show rx2tx 检查属性值
        """
        prop_dict = CliOperation.cli_show_rx2tx(caller_class, dev_para, exec_addr)
        for prop, exp in check_prop_dict.items():
            cur = prop_dict.get(prop)
            if exp != cur:
                CommonOperation.create_bug_problem(ScriptBase, key_word=f'FW',
                                                   description_word=f'show rx2tx查询的{prop}不符合预期，'
                                                                    f'查出来是{cur}，期望是{exp}')

    @classmethod
    def cli_set_ipsec(cls, caller_class, bus_info, state, exec_addr=CmdExecuteAdressEnum.CLI_DEFAULT.value,
                      check_ignore=False):
        """
        author: jianghe
        date  : 2026.05.06
        description: 执行scgbecli -d <device> set ipsec
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} set ipsec state={state}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, exec_addr)
        if check_ignore:
            return
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)

    @classmethod
    def cli_show_ipsec(cls, caller_class, bus_info, exec_addr=CmdExecuteAdressEnum.CLI_DEFAULT.value, check_ignore=False):
        """
        author: jianghe
        date  : 2026.05.06
        description: 执行scgbecli -d <device> show ipsec
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} show ipsec'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, exec_addr)
        if check_ignore:
            return
        CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        ipsec = {}
        found = re.findall('\|Curstate\s*\|([a-zA-Z0-9]+)\s*\|', out)
        ipsec.update({'Curstate': found[0]})
        found = re.findall('\|Nextstate\s*\|([a-zA-Z0-9]+)\s*\|', out)
        ipsec.update({'Nextstate': found[0]})
        return ipsec

    @classmethod
    def check_cli_show_ipsec(cls, caller_class, dev_para: str, check_prop_dict,
                             exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jianghe
        date  : 2026.05.06
        description: 执行show ipsec 检查属性值
        """
        prop_dict = CliOperation.cli_show_ipsec(caller_class, dev_para, exec_addr)
        for prop, exp in check_prop_dict.items():
            cur = prop_dict.get(prop)
            if exp != cur:
                CommonOperation.create_bug_problem(ScriptBase, key_word=f'FW',
                                                   description_word=f'show ipsec查询的{prop}不符合预期，'
                                                                    f'查出来是{cur}，期望是{exp}')

    @classmethod
    def get_mac_id_from_dev_name(cls, dev_name):
        """
        author: jianghe
        date  : 2026.01.13
        description: 根据dev name获取mac id
        """
        if 'en' in dev_name:
            return int(dev_name.split('f')[-1])  # ens5s0
        else:
            return (int(dev_name.split('p')[-1]) - 1)  # p29p1

    @classmethod
    def get_upgrade_syncstate_info(cls, bus_info, caller_class=None, switch_info="0",
                                   exec_addr: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: yibo.gao
        date  : 2026.04.04
        description: 执行版本组状态查询命令, 0时查询,1时切分区
        """
        cmd = f'{constants.SCGBECLI64} -d {bus_info} custom sxe2 upgrdsyncstate versionlineswitch={switch_info}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, exec_addr)
        if caller_class:
            CliOperation.check_cli_success(caller_class, cmd, code, out, err)
        elif code != RtnStatusEnum.SUCCESS.value:
            log.error(f'{cmd}返回的错误信息是{code}\n{out}\n{err}')
            return {}

        m = re.search(f"run state:\s*(\d),\s*switch:\s*(\d),\s*region flash flag:\s*(0x[0-9a-f]+),\s*region uboot flag:\s*(0x[0-9a-f]+),\s*open:\s*(\d)",
                  out, flags=re.I)
        if not m:
            log.error(f'正则获取结果错误, [{cmd}]返回的错误信息是\n{out}')
            CommonOperation.create_bug_problem(caller_class, key_word=f'CLI',
                                               description_word=f'查询版本组状态命令,正则获取结果失败')
        run_state = int(m.group(1))
        switch_state = int(m.group(2))
        # 主分区为0, 备份分区为1
        fw_flash_flag = 1 if int(m.group(3), 16) == 0 else 0
        boot_flash_flag = 1 if int(m.group(4), 16) == 0 else 0
        open_state = int(m.group(5))
        return_dict = {
            "run_state": run_state,
            "switch_state": switch_state,
            "fw_flash_flag": fw_flash_flag,
            "boot_flash_flag": boot_flash_flag,
            "open_state": open_state
        }
        return return_dict

    @classmethod
    def change_flash_flag(cls, bus_info, caller_class=None, exec_addr: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: yibo.gao
        date  : 2026.04.07
        description: 执行切分区命令,下次使用另一分区启动,并验证结果
        """
        log.info(f"对[{bus_info}]进行切分区操作")
        res_dict = cls.get_upgrade_syncstate_info(bus_info=bus_info, caller_class=caller_class, exec_addr=exec_addr,
                                                  switch_info="1")
        if res_dict["switch_state"] != 1:
            CommonOperation.create_bug_problem(caller_class, key_word=f'执行切分区操作',
                                               description_word=f'switch_state参数输入为1,结果返回为[{res_dict["switch_state"]}]',
                                               result_info="",
                                               expect_info="")

        # log.info(f"查询分区Flag是否设置成功")
        # get_dict = cls.get_upgrade_syncstate_info(bus_info=bus_info, caller_class=caller_class, exec_addr=exec_addr,
        #                                           switch_info="0")
        #
        # log.info(f'[{bus_info}]Flash 固件原分区:{res_dict["fw_flash_flag"]},切分区后:{get_dict["fw_flash_flag"]};'
        #          f' bootloader原分区:{res_dict["boot_flash_flag"]},切分区后:{get_dict["boot_flash_flag"]}')
        # if res_dict["fw_flash_flag"] == get_dict["fw_flash_flag"]:
        #     CommonOperation.create_bug_problem(caller_class, key_word=f'执行切分区操作',
        #                                        description_word=f'Flash中的固件 原分区[{res_dict["fw_flash_flag"]}],执行切分区命令后没有变化',
        #                                        result_info="",
        #                                        expect_info="")
        # if res_dict["boot_flash_flag"] == get_dict["boot_flash_flag"]:
        #     CommonOperation.create_bug_problem(caller_class, key_word=f'执行切分区操作',
        #                                        description_word=f'Flash中的bootloader 原分区[{res_dict["fw_flash_flag"]}],执行切分区命令后没有变化',
        #                                        result_info="",
        #                                        expect_info="")
        log.info(f"[{bus_info}]切分区成功")
        return

    @classmethod
    def check_version_line_info(cls, bus_info, caller_class, fw_flash_flag="", boot_flash_flag="", open_state="",
                                exec_addr: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: yibo.gao
        date  : 2026.04.07
        description: 执行版本组状态检查命令,验证结果是否与预期一致
        :param bus_info: device_info
        :param caller_class: 调用类
        :param fw_flash_flag: 固件Flash 分区Flag, str(0/1)
        :param boot_flash_flag: bootlaoder Flash 分区Flag, str(0/1)
        :param open_state: open 参数, str(0/1)
        :param exec_addr: cmd命令执行位置
        """
        return_dict = cls.get_upgrade_syncstate_info(bus_info=bus_info, caller_class=caller_class, exec_addr=exec_addr)
        if fw_flash_flag:
            if int(fw_flash_flag) != return_dict["fw_flash_flag"]:
                CommonOperation.create_bug_problem(caller_class, key_word=f'固件Flash分区标识符校验',
                                                   description_word=f'固件分区期望为[{return_dict["fw_flash_flag"]}], 实际为[{fw_flash_flag}]',
                                                   result_info="",
                                                   expect_info="")
            else:
                log.info(f"固件Flash分区标识符校验通过,为[{fw_flash_flag}]")
        if boot_flash_flag:
            if int(boot_flash_flag) != return_dict["boot_flash_flag"]:
                CommonOperation.create_bug_problem(caller_class, key_word=f'bootloader Flash分区标识符校验',
                                                   description_word=f'uboot分区期望为[{return_dict["boot_flash_flag"]}], 实际为[{boot_flash_flag}]',
                                                   result_info="",
                                                   expect_info="")
            else:
                log.info(f"bootloader Flash分区标识符校验通过,为[{boot_flash_flag}]")

        if open_state:
            if int(open_state) != return_dict["open_state"]:
                CommonOperation.create_bug_problem(caller_class, key_word=f'版本覆盖open_state标识符校验',
                                                   description_word=f'open_state期望为[{return_dict["open_state"]}], 实际为[{open_state}]',
                                                   result_info="",
                                                   expect_info="")
            else:
                log.info(f"版本覆盖open_state校验通过,为[{boot_flash_flag}]")

    # @classmethod
    # def get_version_line(cls, bus_info, caller_class, exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value):
    #     """
    #     author: yibo.gao
    #     date  : 2026.04.07
    #     description: 执行show config命令,获取版本线
    #     """
    #     cmd = f"{constants.SCGBECLI64} -d {bus_info} show config | grep 'versionLine'"
    #     code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, exec_addr)
    #
    #     CliOperation.check_cli_success(caller_class, cmd, code, out, err)
    #     m = re.search(r"\|versionLine\s+\|(\d+)\s*|", out, flags=re.I)
    #     if not m:
    #         CommonOperation.create_bug_problem(caller_class, key_word=f'[{bus_info}]执行show config命令,获取版本线失败',
    #                                            description_word=f'status:{code}, result:{out}',
    #                                            result_info="",
    #                                            expect_info="")
    #     version_line = int(m.group(1))
    #     log.info(f"[{bus_info}]的版本线为[{version_line}]")
    #     return version_line

    @classmethod
    def check_version_line(cls, bus_info, version_line:int, caller_class, exec_addr: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: yibo.gao
        date  : 2026.04.07
        description: 验证版本线是否与预期一致
        """
        real_version_line = cls.get_fw_flag(bus_info=bus_info, caller_class=caller_class, exec_addr=exec_addr)[2]
        if real_version_line != version_line:
            CommonOperation.create_bug_problem(caller_class, key_word=f'[{bus_info}]版本线校验失败,实际与期望不一致',
                                               description_word=f'实际版本线:[{real_version_line}],期望版本线:[{version_line}]',
                                               result_info="",
                                               expect_info="")
        log.info(f"[{bus_info}]版本线校验通过,实际与期望一致为[{real_version_line}]")

    @classmethod
    def make_version_line_pkg(cls, image_version:int, version_line:int, dev_type, caller_class,
                              exec_addr: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: yibo.gao
        date  : 2026.04.07
        description: 按照指定的版本线和版本,生成新的升级包
        :param image_version: 文件header存放的版本
        :param version_line: nvdata中存放的版本线
        :param caller_class: 调用类
        :param dev_type: 设备的sub device id, constants.py中定义的常量
        :param exec_addr: cmd命令执行位置
        """
        script_path = "/root/sxetest/fw_test/change_header_version.py"
        if not CommonOperation.get_full_path(script_path, exec_addr):
            CommonOperation.create_bug_problem(caller_class, key_word=f'修改版本线并重新打包,未找到工具脚本{script_path}',
                                              description_word=f'寻找位置:{script_path}',
                                              result_info="",
                                              expect_info="")

        cmd = f"cd /root/sxetest/fw_test && python3 {script_path} -l {hex(version_line)} -v {hex(image_version)} -t {dev_type}"
        log.info(f"执行重新打包命令,cmd:[{cmd}]")
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, exec_addr)
        out_list = out.split("\n")
        if code != 0 or "success" not in out_list[-1]:
            CommonOperation.create_bug_problem(caller_class,
                                               key_word=f'修改版本线并重新打包,打包失败',
                                               description_word=f'cmd:{cmd}, status:{code}',
                                               result_info="",
                                               expect_info="")

        image_file_path = out_list[-3]
        pldm_file_path = out_list[-2]

        if (".bin" not in image_file_path or ".bin" not in pldm_file_path or
                not CommonOperation.get_full_path(image_file_path, exec_addr) or
                not CommonOperation.get_full_path(pldm_file_path, exec_addr)):
            CommonOperation.create_bug_problem(caller_class,
                                              key_word=f'修改版本线并重新打包,打包失败',
                                              description_word=f'打包命令执行成功后,未找到文件[{image_file_path}]或[{pldm_file_path}]',
                                              result_info="",
                                              expect_info="")
        log.info(f"新image文件:{image_file_path}")
        log.info(f"新pldm文件:{pldm_file_path}")

        return [image_file_path, pldm_file_path, ]  # os.path.dirname(image_file_path)

    @classmethod
    def get_fw_flag(cls, bus_info, caller_class, exec_addr: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: yibo.gao
        date  : 2026.04.11
        description: 执行fwinfo命令,获取固件使用分区和版本线信息
        :param bus_info: 设备bdf
        :param caller_class: 调用类
        :param exec_addr: cmd命令执行位置
        """
        cmd = f"{constants.SCGBECLI64} -d {bus_info} custom sxe2 fwinfo"
        status, output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or not output:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word="获取固件使用分区",
                description_word='命令执行失败',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
        m = re.search(r"sys run Region:\s*(.+)", output, flags=re.I)
        n = re.search(r"fw boot up flag from flash:\s*(.+)", output, flags=re.I)
        if not m or not n:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word="获取固件使用分区",
                description_word='从返回结果中,正则匹配分区信息失败',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
        if "master" in m.group(1).lower():
            log.info(f"Device[{bus_info}]的固件当前使用分区:master")
            active_flag = 0
        else:
            log.info(f"Device[{bus_info}]的固件当前使用分区:slave")
            active_flag = 1

        if "0xa5a5" in n.group(1).lower():
            log.info(f"Device[{bus_info}]的固件下次启动使用分区:slave")
            flash_flag = 1
        else:
            log.info(f"Device[{bus_info}]的固件下次启动使用分区:master")
            flash_flag = 0
        o = re.search(r"VERLINE:\s*([0-9a-f]+)", output, flags=re.I)
        if not o:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word="获取版本线",
                description_word='从返回结果中,正则匹配版本线信息失败',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
        version_line = int(o.group(1), 16)

        return [active_flag, flash_flag, version_line]

    @classmethod
    def get_bootloader_flag(cls, bus_info, caller_class, exec_addr: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: yibo.gao
        date  : 2026.04.11
        description: 执行version bootload命令,获取bootloader使用分区信息
        :param bus_info: 设备bdf
        :param caller_class: 调用类
        :param exec_addr: cmd命令执行位置
        """
        cmd = f"{constants.SCGBECLI64} -d {bus_info} custom sxe2 version bootload"
        status, output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or not output:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word="获取bootloader使用分区",
                description_word='命令执行失败',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
        m = re.search(r"sys run Region:\s*(.+)", output, flags=re.I)
        n = re.search(r"uboot boot up flag from flash:\s*(.+)", output, flags=re.I)
        if not m or not n:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word="获取bootloader使用分区",
                description_word='从返回结果中,正则匹配分区信息失败',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
        if "master" in m.group(1).lower():
            log.info(f"Device[{bus_info}]的bootloader当前使用分区:master")
            active_flag = 0
        else:
            log.info(f"Device[{bus_info}]的bootloader当前使用分区:slave")
            active_flag = 1

        if "0xa5a5" in n.group(1).lower():
            log.info(f"Device[{bus_info}]的bootloader下次启动使用分区:slave")
            flash_flag = 1
        else:
            log.info(f"Device[{bus_info}]的bootloader下次启动使用分区:master")
            flash_flag = 0

        return [active_flag, flash_flag]

    @classmethod
    def get_fw_boot_header_version(cls, bus_info, caller_class, exec_addr: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: yibo.gao
        date  : 2026.04.11
        description: 获取当前运行的固件和bootloader的header version, 16进制
        :param bus_info: 设备bdf
        :param caller_class: 调用类
        :param exec_addr: cmd命令执行位置
        """
        status, dev_show_info, _ = AnalyzeCli.analyze_dev_show(dev_para=bus_info,
                                                               exec_addr=exec_addr)
        if status != CliStatusEnum.SUCCESS.value or not dev_show_info.get("OptionRom Version"):
            log.error("dev_show_info:{}".format(dev_show_info))
            CommonOperation.create_bug_problem(
                caller_class,
                key_word=f"sxe2cli -d {bus_info} show获取OptionRom Version",
                description_word=f'获取show信息失败,status:{status}',
                expect_info=f'获取成功',
                result_info=f'获取失败')
        fw_version = dev_show_info["OptionRom Version"].split(".")
        if len(fw_version) != 4:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word="获取固件当前版本",
                description_word=f'从返回结果获取固件的版本信息错误,[{fw_version}]格式有问题',)
        fw_version = ["{:02X}".format(int(i)) for i in fw_version]
        fw_version = int("".join(fw_version), 16)

        cmd = f"{constants.SCGBECLI64} -d {bus_info} custom sxe2 version bootload"
        status, output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or not output:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word="获取bootloader使用分区和当前版本",
                description_word='命令执行失败',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
        m = re.search(r"image ver\s*=\s*(.+)", output, flags=re.I)
        if not m:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word="获取bootloader当前版本",
                description_word='从返回结果中,正则匹配版本信息失败',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
        boot_version = m.group(1).split(".")
        if len(boot_version) != 4:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word="获取固件当前版本",
                description_word=f'从返回结果获取bootloader的版本信息错误,[{boot_version}]格式有问题', )
        boot_version = ["{:02X}".format(int(i)) for i in boot_version]
        boot_version = int("".join(boot_version), 16)

        return boot_version, fw_version

    @classmethod
    def check_syncstate_change(cls, bus_info, caller_class, target_status=True, check_count=20, continue_check=False,
                               exec_addr: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: yibo.gao
        date  : 2026.04.11
        description: 执行分区覆盖查询命令,查看是否进入/退出分区覆盖状态
        :param bus_info: 设备bdf
        :param caller_class: 调用类
        :param target_status: True 期望进入分区覆盖状态, False 期望退出分区覆盖状态
        :param check_count: 检查次数，每隔5秒一检查,
        :param continue_check: 验证是否不会进入分区覆盖状态,按照检查次数进行多轮检查
        :param exec_addr: cmd命令执行位置
        """
        if not continue_check:
            check_count = 50
        count = 1
        log.info("开始检查分区覆盖是否[{}]".format("开始"if target_status else "完成"))
        res_dict = dict()
        while count <= check_count:
            res_dict = cls.get_upgrade_syncstate_info(bus_info=bus_info, caller_class=caller_class, exec_addr=exec_addr)
            if target_status:
                if res_dict["open_state"] != 1:
                    CommonOperation.create_bug_problem(
                        caller_class,
                        key_word="检查分区覆盖是否开始",
                        description_word=f'open_state为{res_dict["open_state"]},本次不会进行分区覆盖',
                        result_info=f'run_state:{res_dict["run_state"]}')
                if res_dict["run_state"] == 1:
                    log.info("已经开始分区覆盖,退出检查")
                    return
                else:
                    log.info("还未开始分区覆盖,休眠5秒后再次检查")

            else:
                if not continue_check:
                    if res_dict["open_state"] == 0 and res_dict["run_state"] == 0:
                        log.info("分区覆盖检查已经结束,退出检查")
                        return

                    else:
                        log.info(f'open_state:{res_dict["open_state"]},run_state:{res_dict["run_state"]},'
                                 f' 分区覆盖还未结束,休眠5秒后再次检查')
                else:
                    if res_dict["open_state"] == 1:
                        CommonOperation.create_bug_problem(
                            caller_class,
                            key_word="检查分区覆盖是否开始",
                            description_word=f'open_state为{res_dict["open_state"]},期望不进行分区覆盖,结果进行了分区覆盖',
                            result_info=f'run_state:{res_dict["run_state"]}')
                    elif count == check_count:
                        log.info(f"分区覆盖检查已经结束,持续检查{count}次,未进行分区覆盖,退出检查")
                        return
            time.sleep(5)
            count += 1

        if target_status:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word=f"分区覆盖验证{check_count}轮后,依旧未开始",
                description_word=f'open_state:{res_dict["open_state"]},run_state:{res_dict["run_state"]}',
                result_info=f'')
        else:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word=f"分区覆盖验证{check_count}轮后,依旧未结束",
                description_word=f'open_state:{res_dict["open_state"]},run_state:{res_dict["run_state"]}',
                result_info=f'')
        return

    @classmethod
    def check_fw_sycstate_status(cls, bus_info, caller_class, target_status=True,
                                 exec_addr: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: yibo.gao
        date  : 2026.04.11
        description: 执行cli -d bdf show命令,查看soc状态是否为期望的分区覆盖状态 or 初始化完成状态
        :param bus_info: 设备bdf
        :param caller_class: 调用类
        :param target_status: True 期望为分区覆盖状态, False 期望初始化完成状态
        :param exec_addr: cmd命令执行位置
        """
        status, dev_show_info, _ = AnalyzeCli.analyze_dev_show(dev_para=bus_info,
                                                               exec_addr=exec_addr)
        if status != CliStatusEnum.SUCCESS.value or not dev_show_info.get("SOC Status"):
            log.error("dev_show_info:{}".format(dev_show_info))
            CommonOperation.create_bug_problem(
                caller_class,
                key_word=f"sxe2cli -d {bus_info} show获取固件状态",
                description_word=f'获取show信息失败,status:{status}',
                expect_info=f'获取成功',
                result_info=f'获取失败')
        if target_status:
            if dev_show_info["SOC Status"].lower() != "UPGRADSYNC".lower():
                CommonOperation.create_bug_problem(
                    caller_class,
                    key_word=f"sxe2cli -d {bus_info} show获取固件状态",
                    description_word=f'期望为[分区覆盖状态],实际为[{dev_show_info["SOC Status"]}]',
                    expect_info=f'',
                    result_info=f'')
            else:
                log.info("与预期一致,为分区覆盖状态")

        else:
            if dev_show_info["SOC Status"].lower() != "INIT_FINISHED".lower():
                CommonOperation.create_bug_problem(
                    caller_class,
                    key_word=f"sxe2cli -d {bus_info} show获取固件状态",
                    description_word=f'期望为[初始化完整状态],实际为[{dev_show_info["SOC Status"]}]',
                    expect_info=f'',
                    result_info=f'')
            else:
                log.info("与预期一致,为初始化完整状态")
        return

    @classmethod
    def cli_upgrade_file_check_result(cls, bus_info, caller_class, file_path, target_status=True, resetnow=False,
                                      check_info="", exec_addr: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: yibo.gao
        date  : 2026.04.11
        description: 执行cli image升级命令
        :param bus_info: 设备bdf
        :param caller_class: 调用类
        :param file_path: 升级文件,image包
        :param target_status: True 期望升级命令执行成功 or 失败
        :param resetnow: 是否添加 resetnow参数
        :param check_info: 是否验证命令返回内容
        :param exec_addr: cmd命令执行位置
        """
        cmd = f"{constants.SCGBECLI64} -d {bus_info} upgrade file={file_path}"
        if resetnow:
            cmd += " resetnow"
        log.info(f"执行升级命令:{cmd}")
        status, output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr)

        if target_status and (status != RtnStatusEnum.SUCCESS.value or not output):
            CommonOperation.create_bug_problem(
                caller_class,
                key_word="执行cli image升级命令",
                description_word='期望命令执行成功,结果执行失败',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
        elif not target_status and status == RtnStatusEnum.SUCCESS.value:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word="执行cli image升级命令",
                description_word='期望命令执行失败,结果执行成功',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
        if check_info and check_info.lower() not in output.lower():
            CommonOperation.create_bug_problem(
                caller_class,
                key_word="执行cli image升级命令",
                description_word=f'期望命令返回结果中包含[{check_info}],结果未找到',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
        if target_status:
            log.info("升级命令执行成功,与预期一致")
        else:
            log.info("升级命令执行失败,与预期一致")
        return

    @classmethod
    def etntool_upgrade_file_check_result(cls, device_name, caller_class, file_path, target_status=True,
                                          exec_addr: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: yibo.gao
        date  : 2026.04.11
        description: 执行ethtool升级命令
        :param device_name: 设备PF名称
        :param caller_class: 调用类
        :param file_path: 升级文件,image包
        :param target_status: True 验证升级是否成功, False 验证升级是否失败
        :param exec_addr: cmd命令执行位置
        """
        cmd = f"/bin/cp {file_path} /usr/lib/firmware/"
        log.info(f"ethtool升级,将升级文件先放在/usr/lib/firmware下,cmd:{cmd}")
        status, output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word="ethtool升级,将升级文件先放在/usr/lib/firmware下",
                description_word='cp命令执行失败,未升级',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
        file_name = os.path.basename(file_path)
        cmd = f"ethtool -f {device_name} {file_name}"
        log.info(f"执行ethtool升级命令,cmd:{cmd}")
        status, output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr)
        if target_status and status != RtnStatusEnum.SUCCESS.value:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word="执行ethtool升级命令",
                description_word='期望命令执行成功,结果执行失败',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
        elif not target_status and status == RtnStatusEnum.SUCCESS.value:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word="执行ethtool升级命令",
                description_word='期望命令执行失败,结果执行成功',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')
        if target_status:
            log.info("升级命令执行成功,与预期一致")
        else:
            log.info("升级命令执行失败,与预期一致")
        return

    @classmethod
    def close_versionline_check(cls, bus_info, caller_class, close_check=True,
                                exec_addr: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: yibo.gao
        date  : 2026.04.15
        description: 关闭/开启版本组校验
        :param bus_info: 设备bdf
        :param close_check: 是否关闭版本组校验
        :param caller_class: 调用类
        :param exec_addr: cmd命令执行位置
        """
        cmd = f"{constants.SCGBECLI64} -d {bus_info} custom sxe2 upgrddebug versionlineon="
        if close_check:
            cmd += "0"
            log.info(f"关闭版本组校验,cmd:{cmd}")
        else:
            cmd += "1"
            log.info(f"开启版本组校验,cmd:{cmd}")
        status, output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or not output:
            CommonOperation.create_bug_problem(
                caller_class,
                key_word="关闭/开启版本组校验",
                description_word='命令执行失败',
                result_info=f'cmd:{cmd},status:{status}, result:{output}')

    @classmethod
    def check_flag_versionline(cls, bus_info, caller_class,
                               fw_active="", fw_flag="",
                               boot_active="", boot_flag="",
                               version_line="",
                               fw_version="", boot_version="",
                               exec_addr: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: yibo.gao
        date  : 2026.04.11
        description: 对当前使用分区/下次使用分区/版本线进行验证
        :param bus_info: 设备bdf
        :param caller_class: 调用类
        :param fw_active: 固件当前使用分区
        :param fw_flag: 固件下次使用分区
        :param boot_active: bootloader当前使用分区
        :param boot_flag: bootloader下次使用分区
        :param version_line: 当前版本线
        :param fw_version: 固件当前版本
        :param boot_version: bootloader当前版本
        :param exec_addr: cmd命令执行位置
        """
        fw_real_list = cls.get_fw_flag(bus_info=bus_info, caller_class=caller_class, exec_addr=exec_addr)
        boot_real_list = cls.get_bootloader_flag(bus_info=bus_info, caller_class=caller_class, exec_addr=exec_addr)
        if type(fw_active) == int:
            log.info(f"固件当前使用分区:{fw_real_list[0]},预期为:{fw_active}")
            if fw_active != fw_real_list[0]:
                CommonOperation.create_bug_problem(
                    caller_class,
                    key_word="固件当前使用分区与期望不一致",
                    description_word=f'期望为{fw_active},实际为{fw_real_list[0]}',
                    result_info=f'')
        if type(fw_flag) == int:
            log.info(f"固件下次使用分区:{fw_real_list[1]},预期为:{fw_flag}")
            if fw_flag != fw_real_list[1]:
                CommonOperation.create_bug_problem(
                    caller_class,
                    key_word="固件下次使用分区与期望不一致",
                    description_word=f'期望为{fw_flag},实际为{fw_real_list[1]}',
                    result_info=f'')
        if type(boot_active) == int:
            log.info(f"bootloader当前使用分区:{boot_real_list[0]},预期为:{boot_active}")
            if boot_active != boot_real_list[0]:
                CommonOperation.create_bug_problem(
                    caller_class,
                    key_word="bootloader当前使用分区与期望不一致",
                    description_word=f'期望为{boot_active},实际为{boot_real_list[0]}',
                    result_info=f'')
        if type(boot_flag) == int:
            log.info(f"bootloader下次使用分区:{boot_real_list[1]},预期为:{boot_flag}")
            if boot_flag != boot_real_list[1]:
                CommonOperation.create_bug_problem(
                    caller_class,
                    key_word="bootloader下次使用分区与期望不一致",
                    description_word=f'期望为{boot_flag},实际为{boot_real_list[1]}',
                    result_info=f'')

        if type(version_line) == int:
            log.info(f"实际版本线:{cls.get_str_version_for_int(fw_real_list[2])},预期为:{cls.get_str_version_for_int(version_line)}")
            if version_line != fw_real_list[2]:
                CommonOperation.create_bug_problem(
                    caller_class,
                    key_word="当前版本线与期望不一致",
                    description_word=f'期望为{version_line},实际为{fw_real_list[2]}',
                    result_info=f'')

        if type(fw_version) == int or type(boot_version) == int:
            version_list = cls.get_fw_boot_header_version(
                caller_class=caller_class, bus_info=bus_info, exec_addr=exec_addr)
        else:
            version_list = []

        if type(fw_version) == int:
            real_fw_version = version_list[1]
            log.info(f"实际固件版本:{cls.get_str_version_for_int(real_fw_version)},"
                     f"预期为:{cls.get_str_version_for_int(fw_version)}")
            if real_fw_version != fw_version:
                CommonOperation.create_bug_problem(
                    caller_class,
                    key_word="当前固件版本与期望不一致",
                    description_word=f'期望为{fw_version},实际为{real_fw_version}',
                    result_info=f'')
        if type(boot_version) == int:
            real_boot_version = version_list[0]
            log.info(f"实际bootloader版本:{cls.get_str_version_for_int(real_boot_version)},"
                     f"预期为:{cls.get_str_version_for_int(boot_version)}")
            if real_boot_version != boot_version:
                CommonOperation.create_bug_problem(
                    caller_class,
                    key_word="当前bootloader版本与期望不一致",
                    description_word=f'期望为{boot_version},实际为{real_boot_version}',
                    result_info=f'')

        log.info("对当前使用分区/下次使用分区/版本线进行验证, 验证通过")
        return

    @classmethod
    def inject_error_in_fw_bootloader(cls, bus_info, caller_class,
                               fw_flag="", boot_flag="",
                               exec_addr: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: yibo.gao
        date  : 2026.04.16
        description: 对选定的固件/bootloader分区进行错误注入, 触发启动失败,切分区启动
        :param bus_info: 设备bdf
        :param caller_class: 调用类
        :param fw_flag: 固件要注入错误的分区id
        :param boot_flag: bootloader要注入错误的分区id
        :param exec_addr: cmd命令执行位置
        """
        if type(fw_flag) == int:
            dev_id = 10 if fw_flag == 0 else 11
            cmd = (f"{constants.SCGBECLI64} -d {bus_info} custom sxe2 flashwrstr devid={dev_id}"
                   f" offset=0x40 len=16 value=aaaaaaaaaaaaaaaa")
            log.info(f"对固件分区{fw_flag}注入错误,cmd:{cmd}")
            status, output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=exec_addr)
            if status != RtnStatusEnum.SUCCESS.value:
                CommonOperation.create_bug_problem(
                    caller_class,
                    key_word=f"对固件分区{fw_flag}注入错误",
                    description_word='命令执行失败',
                    result_info=f'cmd:{cmd},status:{status}, result:{output}')
        if type(boot_flag) == int:
            dev_id = 0 if boot_flag == 0 else 1
            cmd = (f"{constants.SCGBECLI64} -d {bus_info} custom sxe2 flashwrstr devid={dev_id}"
                   f" offset=0x40 len=16 value=aaaaaaaaaaaaaaaa")
            log.info(f"对bootloader分区{boot_flag}注入错误,cmd:{cmd}")
            status, output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=exec_addr)
            if status != RtnStatusEnum.SUCCESS.value:
                CommonOperation.create_bug_problem(
                    caller_class,
                    key_word=f"对bootloader分区{boot_flag}注入错误",
                    description_word='命令执行失败',
                    result_info=f'cmd:{cmd},status:{status}, result:{output}')
        log.info("分区注入错误完成")
        return

    @classmethod
    def get_str_version_for_int(cls, version):
        """
        author: yibo.gao
        date  : 2026.04.16
        description: 将int格式版本信息,转化为4段字符串
        :param version: int格式版本信息
        """
        if type(version) == str:
            if "0x" in version.lower():
                version = int(version, 16)
            else:
                version = int(version)
        hex_str = "{:08X}".format(version)
        version_list = [str(int(hex_str[i:i+2], 16)) for i in range(0, 8, 2)]
        return ".".join(version_list)

    @classmethod
    def socket_cmd_coredump_trigger(cls):
        """
        author: yibo.gao
        date: 2026.04.16
        description: 在串口执行coredump trigger,触发core0 coredump
        """
        server_com_ip = constants.SERVER_COM_IP
        server_com_port = constants.SERVER_COM_PORT
        cmd = " /debug custom sxe2 coredump trigger"
        log.info(f"在串口,触发core0dump,cmd:{cmd}")
        SocketOption.exec_socket_cmd(cmd, server_com_ip, server_com_port)
        SocketOption.exec_socket_cmd(cmd, server_com_ip, server_com_port)

def lldp_check(method):
    import datetime
    import time
    def time_sleep(sleep_time, info='Waiting'):
        log.info_caller(f'sleep {sleep_time}s...[{info}]')
        time.sleep(sleep_time)

    def check_lldp_status(px, mini_addr):
        rst_status = False
        log.info(f'串口配置： {mini_addr}')
        if mini_addr in [CmdExecuteAdressEnum.SERVER.value, CmdExecuteAdressEnum.CLIENT.value]:
            _, time_str_now, _ = CommandOperation.execute_command_with_error(
                cmd=f"date '+%Y-%m-%d %H:%M:%S'", cmd_execute_address=mini_addr)
            log.info(f'当前时间：{time_str_now}')

            server_serial_port, client_serial_port = CommonOperation.get_serial_port_pos()
            if mini_addr == CmdExecuteAdressEnum.SERVER.value:
                res = re.findall(r'(\w+)@([\d\.]+)_([\d\.]+)_(\d+)', server_serial_port)
            else:
                res = re.findall(r'(\w+)@([\d\.]+)_([\d\.]+)_(\d+)', client_serial_port)
            if res:
                log.info(f'串口位于串口交换机')
                log_server_user = res[0]
                log_server_ip = res[1]
                log_server_serial_switch_ip = res[3]
                log_server_serial_switch_port = res[4]
                test_port = CommandLineArgsParse.get_test_port()
                save_log_dir = '/home/minicom_log_bmc'
                cmd = f'mkdir -p {save_log_dir}'
                _, result, _ = CommandOperation.execute_command_with_error(
                    cmd=cmd,
                    cmd_execute_address=mini_addr
                )
                cmd = f"scp -P {test_port} {log_server_user}@{log_server_ip}:/home/framework/other/{log_server_serial_switch_ip}/{log_server_serial_switch_port}/*.log {save_log_dir}"
                _, result, _ = CommandOperation.execute_command_with_error(
                    cmd=cmd,
                    cmd_execute_address=mini_addr
                )
                cmd = f'll -tr {save_log_dir}/*.log|tail -n 1'
                _, result, _ = CommandOperation.execute_command_with_error(
                    cmd=cmd,
                    cmd_execute_address=mini_addr
                )
                log_path = f'{save_log_dir}/{result}'
                _, output_time, _ = CommandOperation.execute_command_with_error(
                    cmd=rf"grep -n 'lldp tx process success, frame size' {log_path} | tail -n 1",
                    cmd_execute_address=mini_addr
                )
            else:
                log.info(f'串口不在串口交换机')
                _, output_ps, _ = CommandOperation.execute_command_with_error(
                    cmd='ps -ef | grep minicom',
                    cmd_execute_address=mini_addr
                )
                log.info(f'指令执行结果：\n {output_ps}')
                log_path = re.findall(r'/usr/bin/minicom\s+-w\s+-D\s+\S+\s+-C\s+(\S+)', output_ps)
                if not log_path:
                    time_sleep(60, '等待minicom自动启动')
                    _, output_ps, _ = CommandOperation.execute_command_with_error(
                        cmd='ps -ef | grep minicom',
                        cmd_execute_address=mini_addr
                    )
                    log_path = re.findall(r'/usr/bin/minicom\s+-w\s+-D\s+\S+\s+-C\s+(\S+)', output_ps)

                _, output_time, _ = CommandOperation.execute_command_with_error(
                    cmd=rf"grep -n 'lldp tx process success, frame size' {log_path} | tail -n 1",
                    cmd_execute_address=mini_addr
                )
            re_time = re.findall(r'\d+-\d+-\d+ \d+:\d+:\d+', output_time)
            if re_time:
                time_str_lldp = re_time[0]
                log.info(f'lldp最后执行时间：{time_str_lldp}')
                stamp_now = datetime.datetime.strptime(time_str_now, '%Y-%m-%d %H:%M:%S').timestamp()
                stamp_lldp = datetime.datetime.strptime(time_str_lldp, '%Y-%m-%d %H:%M:%S').timestamp()
                if stamp_now - stamp_lldp < 45:
                    rst_status = True
            else:
                time_sleep(40, '等待lldp日志刷新')
                _, output_ps, _ = CommandOperation.execute_command_with_error(
                    cmd='ps -ef | grep minicom',
                    cmd_execute_address=mini_addr
                )
                log_path = re.findall(r'/usr/bin/minicom\s+-w\s+-D\s+\S+\s+-C\s+(\S+)', output_ps)
                _, output_time, _ = CommandOperation.execute_command_with_error(
                    cmd=rf"grep -n 'lldp tx process success, frame size' {log_path} | tail -n 1",
                    cmd_execute_address=mini_addr
                )
                re_time = re.findall(r'\d+-\d+-\d+ \d+:\d+:\d+', output_time)
                if re_time:
                    time_str_lldp = re_time[0]
                    log.info(f'lldp最后执行时间：{time_str_lldp}')
                    stamp_now = datetime.datetime.strptime(time_str_now, '%Y-%m-%d %H:%M:%S').timestamp()
                    stamp_lldp = datetime.datetime.strptime(time_str_lldp, '%Y-%m-%d %H:%M:%S').timestamp()
                    if stamp_now - stamp_lldp < 45:
                        rst_status = True
        else:
            res = re.findall(r'(\w+)@(\d+\.\d+\.\d+\.\d+)_(\d+\.\d+\.\d+\.\d+)_(\d+)', mini_addr)
            if res:
                log_server_name = res[0][0]
                log_server_ip = res[0][1]
                serial_switch_ip = res[0][2]
                serial_switch_port = res[0][3]
            else:
                log.error(f'串口配置错误：{mini_addr}')
                return rst_status
            _, time_str_now, _ = CommandOperation.execute_command_with_error(
                cmd=f"date '+%Y-%m-%d %H:%M:%S'", ssh_ip=log_server_ip, ssh_username=log_server_name)
            log.info(f'当前时间：{time_str_now}')

            log_path = f'/home/framework/other/{serial_switch_ip}/{serial_switch_port}'
            _, log_files, _ = CommandOperation.execute_command_with_error(
                cmd=f"ls {log_path}", ssh_ip=log_server_ip, ssh_username=log_server_name)
            log_path = os.path.join(log_path, log_files.split('\n')[-1])
            log.info(f'串口日志：{log_path}')

            _, output_time, _ = CommandOperation.execute_command_with_error(
                cmd=rf"grep -n 'lldp tx process success, frame size' {log_path} | tail -n 1",
                ssh_ip=log_server_ip, ssh_username=log_server_name
            )
            re_time = re.findall(r'\d+-\d+-\d+ \d+:\d+:\d+', output_time)
            if re_time:
                time_str_lldp = re_time[0]
                log.info(f'lldp最后执行时间：{time_str_lldp}')
                stamp_now = datetime.datetime.strptime(time_str_now, '%Y-%m-%d %H:%M:%S').timestamp()
                stamp_lldp = datetime.datetime.strptime(time_str_lldp, '%Y-%m-%d %H:%M:%S').timestamp()
                if stamp_now - stamp_lldp < 45:
                    rst_status = True
            else:
                time_sleep(40, '等待lldp日志刷新')
                _, output_time, _ = CommandOperation.execute_command_with_error(
                    cmd=rf"grep -n 'lldp tx process success, frame size' {log_path} | tail -n 1",
                    ssh_ip=log_server_ip, ssh_username=log_server_name
                )
                re_time = re.findall(r'\d+-\d+-\d+ \d+:\d+:\d+', output_time)
                if re_time:
                    time_str_lldp = re_time[0]
                    log.info(f'lldp最后执行时间：{time_str_lldp}')
                    stamp_now = datetime.datetime.strptime(time_str_now, '%Y-%m-%d %H:%M:%S').timestamp()
                    stamp_lldp = datetime.datetime.strptime(time_str_lldp, '%Y-%m-%d %H:%M:%S').timestamp()
                    if stamp_now - stamp_lldp < 45:
                        rst_status = True
        if rst_status:
            log.info('lldp开启状态正常')

        return rst_status

    @functools.wraps(method)
    def wrapper(cls, *args, **kwargs):
        log.info('\n' + f"检查lldp支持情况".center(100, "*"))
        mini_addr = cls.server_serial_cli_exec_address
        exec_addr = CmdExecuteAdressEnum.SERVER.value
        CommonOperation.concat_test_steps(f'lldp-check-1: 查看当前版本是否支持lldp')
        _, output_usage, _ = CommandOperation.execute_command_with_error(
            cmd=f'{constants.SCGBECLI64} help', cmd_execute_address=exec_addr
        )
        if 'set lldp state' not in output_usage:
            CommonOperation.concat_test_steps('lldp-check-2: 当前版本不支持lldp，执行一次do函数')
            method(cls, *args, **kwargs)
        else:
            status, result, _ = CommandOperation.execute_command_with_error(
                cmd=f'{constants.SCGBECLI64} show',
                cmd_execute_address=exec_addr
            )
            res = re.findall(r'(\d+:\d+:\d+\.\d)', result)
            if res:
                bdf_list = res
            else:
                bdf_list = []
            CommandOperation.execute_command_with_error(
                cmd=f'{constants.SCGBECLI64} -d {bdf_list[0]} set lldp state=on workmode=TXRX',
                cmd_execute_address=exec_addr
            )
            if len(bdf_list) > 1:
                CommandOperation.execute_command_with_error(
                    cmd=f'{constants.SCGBECLI64} -d {bdf_list[1]} set lldp state=on workmode=TXRX',
                    cmd_execute_address=exec_addr
                )
            time_sleep(40)
            link_state_p0 = check_lldp_status(px=0, mini_addr=mini_addr)
            if len(bdf_list) > 1:
                link_state_p1 = check_lldp_status(px=1, mini_addr=mini_addr)
            else:
                link_state_p1 = True

            if link_state_p0 & link_state_p1:
                CommonOperation.concat_test_steps(f'lldp-check-2: 关闭p1打开p0的lldp开关，执行do函数')
                CommandOperation.execute_command_with_error(
                    cmd=f'{constants.SCGBECLI64} -d {bdf_list[0]} set lldp state=on workmode=TXRX',
                    cmd_execute_address=exec_addr
                )
                if len(bdf_list) > 1:
                    CommandOperation.execute_command_with_error(
                        cmd=f'{constants.SCGBECLI64} -d {bdf_list[1]} set lldp state=off workmode=TXRX',
                        cmd_execute_address=exec_addr
                    )
                method(cls, *args, **kwargs)
                time_sleep(60)
                if check_lldp_status(px=0, mini_addr=mini_addr) is False:
                    CommonOperation.create_bug_problem(cls, key_word=f'lldp', description_word='lldp状态变化')
                if len(bdf_list) > 1:
                    if check_lldp_status(px=1, mini_addr=mini_addr) is True:
                        CommonOperation.create_bug_problem(cls, key_word=f'lldp', description_word='lldp状态变化')

                CommonOperation.concat_test_steps(f'lldp-check-3: 关闭p1和p0的lldp开关，执行do函数')
                CommandOperation.execute_command_with_error(
                    cmd=f'{constants.SCGBECLI64} -d {bdf_list[1]} set lldp state=off workmode=TXRX',
                    cmd_execute_address=exec_addr
                )
                if len(bdf_list) > 1:
                    CommandOperation.execute_command_with_error(
                        cmd=f'{constants.SCGBECLI64} -d {bdf_list[0]} set lldp state=off workmode=TXRX',
                        cmd_execute_address=exec_addr
                    )
                method(cls, *args, **kwargs)
                time_sleep(35)
                if check_lldp_status(px=0, mini_addr=mini_addr) is True:
                    CommonOperation.create_bug_problem(cls, key_word=f'lldp', description_word='lldp状态变化')
                if len(bdf_list) > 1:
                    if check_lldp_status(px=1, mini_addr=mini_addr) is True:
                        CommonOperation.create_bug_problem(cls, key_word=f'lldp', description_word='lldp状态变化')

                CommonOperation.concat_test_steps(f'lldp-check-4: 打开p1和p0的lldp开关，执行do函数')
                CommandOperation.execute_command_with_error(
                    cmd=f'{constants.SCGBECLI64} -d {bdf_list[1]} set lldp state=on workmode=TXRX',
                    cmd_execute_address=exec_addr
                )
                if len(bdf_list) > 1:
                    CommandOperation.execute_command_with_error(
                        cmd=f'{constants.SCGBECLI64} -d {bdf_list[0]} set lldp state=on workmode=TXRX',
                        cmd_execute_address=exec_addr
                    )
                method(cls, *args, **kwargs)
                time_sleep(35)
                if check_lldp_status(px=0, mini_addr=mini_addr) is False:
                    CommonOperation.create_bug_problem(cls, key_word=f'lldp', description_word='lldp状态变化')
                if len(bdf_list) > 1:
                    if check_lldp_status(px=1, mini_addr=mini_addr) is False:
                        CommonOperation.create_bug_problem(cls, key_word=f'lldp', description_word='lldp状态变化')
            elif link_state_p0 | link_state_p1:
                px = 0 if link_state_p0 is True else 1
                if px <= (len(bdf_list) - 1):
                    CommonOperation.concat_test_steps(f'lldp-check-2: 关闭p{px}的lldp开关，执行do函数')
                    CommandOperation.execute_command_with_error(
                        cmd=f'{constants.SCGBECLI64} -d bdf_list{px} set lldp state=off workmode=TXRX',
                        cmd_execute_address=exec_addr
                    )
                    method(cls, *args, **kwargs)
                    time_sleep(35)
                    if check_lldp_status(px=px, mini_addr=mini_addr) is True:
                        CommonOperation.create_bug_problem(cls, key_word=f'lldp', description_word='lldp状态变化')

                    CommonOperation.concat_test_steps(f'lldp-check-3: 打开p{px}的lldp开关，执行do函数')
                    CommandOperation.execute_command_with_error(
                        cmd=f'{constants.SCGBECLI64} -d bdf_list{px} set lldp state=on workmode=TXRX',
                        cmd_execute_address=exec_addr
                    )
                    method(cls, *args, **kwargs)
                    time_sleep(35)
                    if check_lldp_status(px=px, mini_addr=mini_addr) is False:
                        CommonOperation.create_bug_problem(cls, key_word=f'lldp', description_word='lldp状态变化')
            else:
                CommonOperation.concat_test_steps('lldp-check-2: 当前卡1 无link up链路，无lldp包，执行一次do函数')
                method(cls, *args, **kwargs)
        return

    return wrapper


def open_lldp_down_link(method):
    import datetime
    import time
    import configparser

    @functools.wraps(method)
    def wrapper(cls, *args, **kwargs):
        log.info('\n' + f"检查lldp支持情况".center(100, "*"))
        exec_addr = CmdExecuteAdressEnum.SERVER.value
        CommonOperation.concat_test_steps(f'lldp-check-1: 查看当前版本是否支持lldp')
        _, output_usage, _ = CommandOperation.execute_command_with_error(
            cmd=f'{constants.SCGBECLI64} help', cmd_execute_address=exec_addr
        )
        if 'set lldp state' not in output_usage:
            CommonOperation.concat_test_steps('lldp-check-2: 当前版本不支持lldp，执行一次do函数')
            method(cls, *args, **kwargs)
        else:
            config = configparser.ConfigParser()
            config.read(constants.NIC_CONFIG_PATH)
            dev_lst = config['relationships']['server'].split(',')

            status, result, _ = CommandOperation.execute_command_with_error(
                cmd=f'{constants.SCGBECLI64} show',
                cmd_execute_address=exec_addr
            )
            res = re.findall(r'(\d+:\d+:\d+\.\d)', result)
            if res:
                bdf_list = res
            else:
                bdf_list = []
            CommonOperation.concat_test_steps(f'lldp-check-2：打开lldp开关，link down，执行do函数')
            CommandOperation.execute_command_with_error(
                cmd=f'{constants.SCGBECLI64} -d {bdf_list[0]} set lldp state=on workmode=TXRX',
                cmd_execute_address=exec_addr
            )
            if len(bdf_list) > 1:
                CommandOperation.execute_command_with_error(
                    cmd=f'{constants.SCGBECLI64} -d {bdf_list[1]} set lldp state=on workmode=TXRX',
                    cmd_execute_address=exec_addr
                )

            for dev in dev_lst:
                CommandOperation.execute_command_with_error(
                    cmd=f'ifconfig {dev} down', cmd_execute_address=exec_addr
                )
            method(cls, *args, **kwargs)

            CommonOperation.concat_test_steps(f'lldp-check-3: 打开lldp开关，link up，执行do函数')
            for dev in dev_lst:
                CommandOperation.execute_command_with_error(
                    cmd=f'ifconfig {dev} up', cmd_execute_address=exec_addr
                )
