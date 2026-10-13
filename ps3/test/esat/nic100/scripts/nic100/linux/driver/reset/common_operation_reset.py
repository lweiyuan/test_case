#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import add_syspath
import re
import random

from scripts.script_libs import log, constants
from scripts.script_libs.script_base import ScriptBase
from scripts.script_libs.cli_operation import CliOperation
from scripts.script_libs.enums import (CmdExecuteAdressEnum, ResetType, NicNameEnum, RtnStatusEnum, CoreResetType,
                                       FwResetType, MacVlanModeEnum)
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.host_operation import HostOperation
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse


class CommonOperationReset(object):
    core_reset_sleep_time = 10
    sys_reset_sleep_time = 30
    fr_reset_sleep_time = 1
    if constants.is_hf:
        pf_reset_type_list = [ResetType.PFLR.value, ResetType.PFR.value]
    else:
        pf_reset_type_list = [ResetType.PFLR.value, ResetType.PFR.value, ResetType.CORER.value]
    vf_reset_type_list = [ResetType.VFLR.value, ResetType.VFR.value]
    random.shuffle(pf_reset_type_list)
    random.shuffle(vf_reset_type_list)

    @classmethod
    def custom_scgbe_speedbridge1ganset(cls, pf_device_name: str = '',
                                        exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author:      jianghe
        date:        2025.05.06
        description: 设置an开关
        """
        if CommonOperation.is_fpga():
            cmd = f'{constants.SCGBECLI64} -d all custom sxe2 speedbridge1ganset port=0 an=1'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, exec_addr)
            log.info(f'命令{cmd}的返回信息是{rtn_code}\n{rtn_outputs}\n{rtn_err}')
            cmd = f'{constants.SCGBECLI64} -d all custom sxe2 speedbridge1ganset port=1 an=1'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, exec_addr)
            log.info(f'命令{cmd}的返回信息是{rtn_code}\n{rtn_outputs}\n{rtn_err}')

    @classmethod
    def check_reset_count(cls, caller_class, reset_type, device_bdf, exp_count=None,
                          cmd_execute_address=CmdExecuteAdressEnum.SERVER.value) -> int:
        """
        author:         jianghe
        date:           2025.05.06
        description:    获取复位计数，说明，不管是pf还是vf，device_bdf是pf的
        """
        width = '32'
        if reset_type == ResetType.PFR.value:
            addr = '0x8b071004'
        elif reset_type == ResetType.CORER.value:
            addr = '0xb8000144'
        elif reset_type == ResetType.PFLR.value:
            addr = '0x8b071410'
        elif reset_type == ResetType.VFR.value:
            addr = '0x8b071008'
        elif reset_type == ResetType.VFLR.value:
            addr = '0x8b071410'
        elif reset_type == ResetType.SYS.value:
            addr = '0xb8000144'
        else:
            log.warning(f'不支持的复位类型{reset_type}')
            return None
        value = CliOperation.get_reg_value(device_bdf, width, addr, cmd_execute_address)
        cur_count = int(value, 16)
        if reset_type == ResetType.VFLR.value:
            cur_count = cur_count >> 16
        if reset_type == ResetType.PFLR.value:
            cur_count = cur_count & 0xffff
        if exp_count is None:
            return cur_count
        else:
            if cur_count == exp_count:
                log.info(f'复位{reset_type}计数符合预期，是{exp_count}')
            else:
                log.error(f'复位{reset_type}计数不符合预期，期望是{exp_count}，实际是{int(value, 16)}')
                CommonOperation.create_bug_problem(caller_class, key_word='RESET',
                                                   description_word=f'复位{reset_type}计数不符合预期，'
                                                                    f'期望是{exp_count}，实际是{int(value, 16)}')
                return None

    @classmethod
    def check_host_driver_log(cls, caller_class, key: str, count: int = None, check_file: str = None,
                              cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> tuple:
        """
        author:      jianghe
        date:        2025.04.25
        description: 检查主机驱动日志
        """
        cmd = 'ls -t /var/log/sxe2.log.* |head -n 1'
        _, latest_file, _ = CommandOperation.execute_command_with_error(cmd, cmd_execute_address)
        if latest_file == '':
            return (None, 0)
        cmd = f"grep -aiE '{key}' {latest_file}"
        _, out, _ = CommandOperation.execute_command_with_error(cmd, cmd_execute_address)
        log.info(f'主机{latest_file}路径下查找关键字{key}，日志是{out}')
        if count is None:
            if out == '':
                return (latest_file, 0)
            else:
                return (latest_file, len(out.split('\n')))
        else:
            cmd = 'ls -t /var/log/sxe2.log.*'
            _, all_file, _ = CommandOperation.execute_command_with_error(cmd, cmd_execute_address)
            all_file_list = all_file.split('\n')
            check_files = []
            for file in all_file_list:
                if file == check_file:
                    check_files.append(file)
                    break
                else:
                    check_files.append(file)
            log.info(f'需要检查的主机驱动日志文件有: {check_files}')
            cmd = f"grep -aiE '{key}' {' '.join(check_files)}"
            _, out, _ = CommandOperation.execute_command_with_error(cmd, cmd_execute_address)
            if out == '':
                log.error(f'主机驱动日志没找到新的关键字{key}，预期是{count}个，实际是0个')
                CommonOperation.create_bug_problem(caller_class, key_word='RESET',
                                                   description_word=f'主机驱动日志没找到关键字{key}',
                                                   expect_info=f'主机驱动日志找到关键字{key}')
            else:
                cur_count = len(out.split('\n'))
                if count == cur_count:
                    log.info(f'主机驱动日志找到关键字{key}，是{out}')
                else:
                    log.error(f'主机驱动日志没找到新的关键字{key}，预期是{count}个，实际是{cur_count}个')
                    CommonOperation.create_bug_problem(caller_class, key_word='RESET',
                                                       description_word=f'主机驱动日志没找到关键字{key}',
                                                       expect_info=f'主机驱动日志找到关键字{key}')
            return None

    @classmethod
    def check_host_reg_value(cls, caller_class, device_name, offset_address, register_value=None,
                             cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author:         jianghe
        date:           2025.05.06
        description:    获取，检查主机寄存器值
        """
        cmd = f'./md {device_name} {offset_address}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
        log.info(f'命令{cmd}返回信息为\n{code}\n{out}\n{err}')
        rtn = out.split(':')
        if register_value is None:
            if len(rtn) == 1:
                return None
            else:
                return re.findall('([0-9a-f]+)', rtn[1])[0]
        else:
            if len(rtn) == 1:
                log.error(f'读主机寄存器异常')
                CommonOperation.create_bug_problem(caller_class, key_word='RESET',
                                                   description_word=f'读主机寄存器异常',
                                                   expect_info=f'读主机寄存器正常')
                return None
            else:
                cur = re.findall('([0-9a-f]+)', rtn[1])[0]
                if cur == register_value:
                    log.info(f'主机寄存器的值与期望的一致，是{cur}')
                else:
                    log.error(f'主机寄存器的值与期望的不一致，期望是{register_value}，实际是{cur}')
                    CommonOperation.create_bug_problem(caller_class, key_word='RESET',
                                                       description_word=f'主机寄存器的值与期望的不一致，期望是{register_value}，实际是{cur}',
                                                       expect_info=f'主机寄存器的值与期望的不一致，期望是{register_value}，实际是{cur}')

    @classmethod
    def check_reset_done_with_host_reg(cls, caller_class, device_name, device_bdf, reset_type) -> None:
        """
        author:         jianghe
        date:           2025.05.06
        description:    检查复位结束标记位
        """
        if reset_type == ResetType.CORER.value:
            cmd = f'setpci -s {device_bdf} 38c.w'
            code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd)
            log.info(f'命令{cmd}的返回信息是{code}\n{out}\n{err}')
            bit = (int(out, 16) >> 3) & 1
            if bit == 1:
                log.info(f'core reset复位完成标记正确')
            else:
                err_info = f'core reset复位完成标记不正确，期望bit3是1，实际是{bit}'
                log.error(err_info)
                CommonOperation.create_bug_problem(caller_class, key_word='RESET',
                                                   description_word=err_info,
                                                   expect_info=err_info)
            return
        elif reset_type == ResetType.PFR.value or reset_type == ResetType.PFLR.value:
            addr = '0x336000'
            value = cls.check_host_reg_value(cls, device_name, addr)
            cur_bit = int(value, 16) & 1
            if cur_bit == 0:
                log.info(f'pfr复位完成标记正确')
            else:
                err_info = f'pfr复位完成标记不正确，期望bit0是0，实际是{cur_bit}'
                log.error(err_info)
                CommonOperation.create_bug_problem(caller_class, key_word='RESET',
                                                   description_word=err_info,
                                                   expect_info=err_info)
        elif reset_type == ResetType.VFR.value or reset_type == ResetType.VFLR.value:
            addr = '0x337000'
            pf_device_name, vf_num = device_name.split('v')
            addr = hex(int(addr, 16) + 4 * int(vf_num))
            value = cls.check_host_reg_value(cls, pf_device_name, addr)
            cur_bit = int(value, 16) & 1
            if cur_bit == 0:
                log.info(f'vfr复位完成标记正确')
            else:
                err_info = f'vfr复位完成标记不正确，期望bit0是0，实际是{cur_bit}'
                log.error(err_info)
                CommonOperation.create_bug_problem(caller_class, key_word='RESET',
                                                   description_word=err_info,
                                                   expect_info=err_info)
        else:
            log.error(f'不支持的复位类型')

    @classmethod
    def create_vf_device_and_driver(cls, device_name: str, vf_num: int = 1,
                                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author:         jianghe
        date:           2025.03.20
        description: 创建vf设备并加载驱动
        """
        result_generate_vf = CommonOperation.generate_vf_device(
            pf_device_name=device_name,
            vf_num=vf_num,
            cmd_execute_address=cmd_execute_address)
        if not result_generate_vf:
            from scripts.script_libs.script_base import ScriptBase
            CommonOperation.create_bug_problem(ScriptBase, key_word='创建vf', description_word='创建vf命令执行失败')
        # server_driver_name, client_driver_name = CommonOperation.get_nic_driver_name()
        # driver_name = server_driver_name if cmd_execute_address == CmdExecuteAdressEnum.SERVER.value else client_driver_name
        # CommonOperation.modprobe_driver(
        #     CommonOperation.get_nic_vf_driver_name_by_pf(driver_name),
        #     CmdExecuteAdressEnum.SERVER.value)


    @classmethod
    def hot_reset(cls, pf_device_bdf: str, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author:         jianghe
        date:           2025.03.20
        description:    热复位
        """
        cmd = f'find /sys/devices/ -name {pf_device_bdf} |grep -v virtual'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
        log.info(f'命令返回结果是{code}\n{out}\n{err}')
        # vm5006的返回是/sys/devices/pci0000:98/0000:98:05.0/0000:99:00.0
        pci_bridge = out.split('/')[4]
        cmd = f'setpci -s {pci_bridge} 3E.B=40:40; sleep 0.0002; setpci -s {pci_bridge} 3E.B=00:40'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
        log.info(f'命令返回结果是{code}\n{out}\n{err}')

    @classmethod
    def get_host_product_name(cls, server_ip) -> str:
        """
        author:      jianghe
        date:        2025.06.24
        description: 查询机型
        """
        cmd = f"dmidecode -t system |grep 'Product Name'"
        code, out, err = CommandOperation.execute_command_with_error(cmd, ssh_ip=server_ip)
        log.info(f'命令{cmd}的返回信息是{code}\n{out}\n{err}')
        return out

    @classmethod
    def host_reboot_with_check(cls, caller_class, server_ip) -> None:
        """
        author:      jianghe
        date:        2025.3.25
        description: 环境准备
        """
        reboot_result = HostOperation.host_reboot(ssh_ip=server_ip)
        if reboot_result != RtnStatusEnum.SUCCESS.value:
            CommonOperation.create_bug_problem(caller_class, key_word=f"主机reboot",
                                               description_word='主机reboot失败')

    @classmethod
    def host_bmc_reboot_with_check(cls, caller_class, server_ip) -> None:
        """
        author:      jianghe
        date:        2025.3.25
        description: 环境准备
        """
        bmc_ip = CommandLineArgsParse.get_server_bmc_ip()
        uname = CommandLineArgsParse.get_server_bmc_uname()
        passwd = CommandLineArgsParse.get_server_bmc_passwd()
        reboot_result = HostOperation.host_bmc_reboot(ssh_ip=server_ip, bmc_ip=bmc_ip, uname=uname, passwd=passwd)
        if reboot_result != RtnStatusEnum.SUCCESS.value:
            CommonOperation.create_bug_problem(
                caller_class, key_word="主机bmc重启",
                description_word=f'主机bmc重启失败，请检查环境')

    @classmethod
    def host_reboot_after_sys_reset(cls, caller_class, server_ip) -> None:
        """
        author:      jianghe
        date:        2025.06.24
        description: 环境准备
        """
        # g50机型reboot不能重新建链，暂时先改成ipmitool方式
        host_product_name = CommonOperationReset.get_host_product_name(server_ip)
        if 'R620 G50' in host_product_name or 'R6250H0' in host_product_name:
            bmc_ip = CommandLineArgsParse.get_server_bmc_ip()
            uname = CommandLineArgsParse.get_server_bmc_uname()
            passwd = CommandLineArgsParse.get_server_bmc_passwd()
            reboot_result = HostOperation.host_bmc_reboot(
                ssh_ip=server_ip, bmc_ip=bmc_ip, uname=uname, passwd=passwd)
            if reboot_result != RtnStatusEnum.SUCCESS.value:
                CommonOperation.create_bug_problem(
                    cls, key_word="bmc重启",
                    description_word=f'bmc重启失败，请检查环境')
        else:
            reboot_type = random.choice([0, 1])
            if reboot_type == 0:
                reboot_result = HostOperation.host_reboot(ssh_ip=server_ip)
                if reboot_result == RtnStatusEnum.SUCCESS.value:
                    log.info('重启成功')
                else:
                    log.error(f"主机reboot失败")
                    CommonOperation.create_bug_problem(caller_class, key_word=f"主机reboot失败",
                                                       description_word='主机reboot失败',
                                                       expect_info='主机reboot成功',
                                                       result_info=f'主机reboot失败')
            else:
                bmc_ip = CommandLineArgsParse.get_server_bmc_ip()
                uname = CommandLineArgsParse.get_server_bmc_uname()
                passwd = CommandLineArgsParse.get_server_bmc_passwd()
                reboot_result = HostOperation.host_bmc_reboot(
                    ssh_ip=server_ip, bmc_ip=bmc_ip, uname=uname, passwd=passwd)
                if reboot_result != RtnStatusEnum.SUCCESS.value:
                    CommonOperation.create_bug_problem(
                        cls, key_word="bmc重启",
                        description_word=f'bmc重启失败，请检查环境')

    @classmethod
    def get_command_path_from_bdf(cls, caller_class, device: str = "", bdf: str = "",
                                  exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> str:
        """
        author:      jianghe
        date:        2025.04.23
        description: core_reset_host_active
        """
        if not bdf:
            exec_command = "ethtool -i '{}'".format(device)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=exec_addr)
            # bus-info: 0000:31:00.0
            bdfs = re.findall(r"bus-info: (\S\S\S\S:\S\S:\S\S.\S)", rtn_outputs)
            if bdfs:
                bdf = bdfs[0]
            else:
                log.error("未找到设备bdf，无法进行core reset操作！！")
        exec_command = "find / -name command | grep '{}'".format(bdf)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=exec_addr)
        if "command" in rtn_outputs:
            return 'echo "corer trigger" > {}'.format(rtn_outputs)
        else:
            log.error(f'根据device参数{device}和bdf参数{bdf}没有找到有效的command路径')
            CommonOperation.create_bug_problem(caller_class, key_word=f'FW',
                                               description_word=f'根据device参数{device}和bdf参数{bdf}没有找到有效的command路径')
            return ''

    @classmethod
    def core_reset_host_active(cls, caller_class, device: str = "", bdf: str = "", command_path: str = '',
                               exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
                               check_ignore: bool = False) -> None:
        """
        author:      jianghe
        date:        2025.04.23
        description: core_reset_host_active
        """
        if command_path == '':
            if not bdf:
                exec_command = "ethtool -i '{}'".format(device)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                    exec_command, cmd_execute_address=exec_addr)
                # bus-info: 0000:31:00.0
                bdfs = re.findall(r"bus-info: (\S\S\S\S:\S\S:\S\S.\S)", rtn_outputs)
                if bdfs:
                    bdf = bdfs[0]
                else:
                    log.error("未找到设备bdf，无法进行core reset操作！！")
            exec_command = "find / -name command | grep '{}'".format(bdf)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=exec_addr)
            if "command" in rtn_outputs:
                cmd = 'echo "corer trigger" > {}'.format(rtn_outputs)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                    cmd, cmd_execute_address=exec_addr)
                if check_ignore:
                    return
                if rtn_code == RtnStatusEnum.SUCCESS.value:
                    pass
                else:
                    log.error(f'命令{cmd}执行失败，返回信息是{rtn_code}\n{rtn_outputs}\n{rtn_err}')
                    CommonOperation.create_bug_problem(caller_class, key_word=f'命令{cmd}执行失败',
                                                       description_word=f'命令{cmd}执行失败',
                                                       expect_info=f'命令{cmd}执行成功',
                                                       result_info=f'命令{cmd}执行失败')
            else:
                log.error("未找到可操作设备，无法进行core reset操作！！")
        else:
            cmd = 'echo "corer trigger" > {}'.format(command_path)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                cmd, cmd_execute_address=exec_addr)
            if check_ignore:
                return
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                pass
            else:
                log.error(f'命令{cmd}执行失败，返回信息是{rtn_code}\n{rtn_outputs}\n{rtn_err}')
                CommonOperation.create_bug_problem(caller_class, key_word=f'命令{cmd}执行失败',
                                                   description_word=f'命令{cmd}执行失败',
                                                   expect_info=f'命令{cmd}执行成功',
                                                   result_info=f'命令{cmd}执行失败')

    @classmethod
    def core_reset_host_passive(cls, caller_class, device: str = "",
                               exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author:      jianghe
        date:        2025.04.23
        description: core_reset_host_passive
        """
        cmd = f"./mw {device} 0x292630 0x09FBD586"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        log.info(f'命令{cmd}执行返回信息是{rtn_code}\n{rtn_outputs}\n{rtn_err}')

    @classmethod
    def core_reset_fw_core(cls, caller_class, device_bdf: str = '',
                           exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author:      jianghe
        date:        2025.06.24
        description: cli命令写非法地址触发固件core
        """
        cmd = f"{constants.SCGBECLI64} -d {device_bdf} set reg type=A width=32 addr=0x292630 0x09FBD586"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd,
                                                                                     cmd_execute_address=exec_addr)
        log.info(f'命令{cmd}的返回信息是{rtn_code}\n{rtn_outputs}\n{rtn_err}')

    @classmethod
    def core_reset(cls, caller_class, device: str = "", bdf: str = "", reset_types: list = None,
                   check_ignore: bool = False) -> None:
        """
        author:      jianghe
        date:        2025.04.28
        description: core reset，选择core reset的方式
        :return:     None
        """
        if reset_types is None:
            reset_type = random.choice([CoreResetType.CLI.value, CoreResetType.HOST_ACTIVE.value,
                                        CoreResetType.HOST_PASSIVE.value])
        else:
            reset_type = random.choice(reset_types)
        if reset_type == CoreResetType.CLI.value:
            CommonOperation.fw_reset(caller_class, bdf, FwResetType.Core_Reset.value, check_ignore=check_ignore)
        if reset_type == CoreResetType.HOST_ACTIVE.value:
            cls.core_reset_host_active(caller_class, device, bdf)
        if reset_type == CoreResetType.HOST_PASSIVE.value:
            cls.core_reset_host_passive(caller_class, device, bdf)
        if reset_type == CoreResetType.HW_CORE.value:
            cls.core_reset_fw_core(caller_class, bdf)

    @classmethod
    def execute_ethtool_command(cls, caller_class, operation: str, device_name: str, command: str = None,
                                result: bool = True, flag: bool = False,
                                exec_addr=CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author: jinbo.zhang
        date  : 2025.1.11
        description: ethtool -operation ens1f0 command
        :param operation:
        :param device_name:
        :param command:命令
        :param result: 命令执行结果
        :param flag:
        :param exec_addr:
        return: 无返回值
        """
        cmd = 'ethtool '
        if operation is None:
            cmd += device_name
        else:
            cmd += operation + ' ' + device_name
        if command is not None:
            cmd += ' ' + command
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if result:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行成功, 符合预期')
                caller_class.output_result = rtn_outputs
                return rtn_outputs
            else:
                log.info(f'command:{cmd}执行失败, 不符合预期，返回结果{rtn_code}\n{rtn_outputs}\n{rtn_err}')
                if flag:
                    caller_class.para_op_result = rtn_code
                else:
                    CommonOperation.create_bug_problem(caller_class, key_word=f'设置{device_name}配置信息{command}失败',
                                                       description_word=f'设置{device_name}配置信息{command}失败',
                                                       expect_info=f'设置{device_name}配置信息{command}成功',
                                                       result_info=f'设置{device_name}配置信息{command}失败')
        else:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'command:{cmd}执行失败, 符合预期')
                caller_class.output_result = rtn_outputs
                return rtn_outputs
            else:
                log.info(f'command:{cmd}执行成功, 不符合预期')
                if flag:
                    caller_class.para_op_result = rtn_code
                else:
                    CommonOperation.create_bug_problem(caller_class, key_word=f'设置{device_name}配置信息{command}成功',
                                                       description_word=f'设置{device_name}配置信息{command}成功',
                                                       expect_info=f'设置{device_name}配置信息{command}成功',
                                                       result_info=f'设置{device_name}配置信息{command}成功')

    @classmethod
    def check_ping_status(cls, caller_class, device_ip: str, exec_addr: str = CmdExecuteAdressEnum.SERVER.value,
                          reverse: bool = False) -> None:
        """
        author: jinbo.zhang
        date  : 2025.1.22
        description: 检查本端和对端是否能ping通
        :param device_ip:
        :param exec_addr:
        return: 无返回值
        """
        command = f"ping {device_ip} -c 2"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            command, cmd_execute_address=exec_addr)
        log.info(f"{command},rtn_code:{rtn_code}, rtn_outputs:{rtn_outputs}, rtn_err:{rtn_err}")
        if reverse:
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.info(f'ip地址{device_ip}不可ping通')
            else:
                CommonOperation.create_bug_problem(caller_class, key_word='网口连通性检查',
                                                   description_word=f'对端ip地址{device_ip}能ping通，期望是ping不通，报bug')
        else:
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info(f'ip地址{device_ip}可ping通')
            else:
                CommonOperation.create_bug_problem(caller_class, key_word='网口连通性检查',
                                                   description_word=f'对端ip地址{device_ip}无法ping通')

    @classmethod
    def function_remove(cls, caller_class, device_bdf: str, exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author: jianghe
        date  : 2025.07.24
        description: 移除设备，echo 1 > /sys/bus/pci/devices/0000:99:00.0/remove
        """
        cmd = f'echo 1 > /sys/bus/pci/devices/{device_bdf}/remove'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd, cmd_execute_address=exec_addr)
        log.info(f'命令{cmd}的返回信息是{code}\n{out}\n{err}')
        if code != RtnStatusEnum.SUCCESS.value:
            CommonOperation.create_bug_problem(caller_class, key_word='RESET',
                                               description_word=f'命令{cmd}执行失败')

    @classmethod
    def function_rescan(cls, caller_class, exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author: jianghe
        date  : 2025.07.24
        description: 扫描设备，echo 1 > /sys/bus/pci/rescan
        """
        cmd = f'echo 1 > /sys/bus/pci/rescan'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd, cmd_execute_address=exec_addr)
        log.info(f'命令{cmd}的返回信息是{code}\n{out}\n{err}')
        if code != RtnStatusEnum.SUCCESS.value:
            CommonOperation.create_bug_problem(caller_class, key_word='RESET',
                                               description_word=f'命令{cmd}执行失败')

    @classmethod
    def add_macvlan(cls, caller_class, device_name: str, macvlan_name: str,
                    macvlan_mode: str = MacVlanModeEnum.VEPA.value,
                    cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                    macvlan_type: str = constants.MACVLAN):
        """
        author: jianghe
        date:   20250909
        description: 添加macvlan
        """
        # 增加macvlan
        exec_command_add_macvlan = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.ADD,
                                                             constants.LINK, device_name, constants.NAME,
                                                             macvlan_name, constants.TYPE, macvlan_type,
                                                             constants.MODE, macvlan_mode])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command_add_macvlan,
                                                        cmd_execute_address=cmd_execute_address)

        log.info(f'命令{exec_command_add_macvlan}返回结果是{rtn_code}\n{rtn_outputs}\n{rtn_err}')
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            CommonOperation.create_bug_problem(caller_class, key_word='MACVLAN',
                                               description_word=f'命令{exec_command_add_macvlan}执行失败')
        # 启动macvlan
        exec_command_enable_macvlan = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.SET,
                                                                macvlan_name, constants.UP])

        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command_enable_macvlan,
                                                        cmd_execute_address=cmd_execute_address)
        log.info(f'命令{exec_command_enable_macvlan}返回结果是{rtn_code}\n{rtn_outputs}\n{rtn_err}')
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            CommonOperation.create_bug_problem(caller_class, key_word='MACVLAN',
                                               description_word=f'命令{exec_command_enable_macvlan}执行失败')

    @classmethod
    def is_rpm_installed(cls, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value):
        """
        author: jianghe
        date:   2025.11.10
        description: 检查rpm包是否已经安装
        """
        cmd = f'rpm -qa |grep sxe2'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd, cmd_execute_address=cmd_execute_address)
        log.info(f'命令{cmd}的返回信息是{code}\n{out}\n{err}')
        if 'sxe2' in out:
            return True
        else:
            return False

    @classmethod
    def get_rpm_file(cls, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value):
        """
        author: jianghe
        date:   2025.11.10
        description: 安装rpm
        """
        file = None
        os_file = None
        os_rpm_dict = {
            '5.14.0-162.6.1.el9_1.x86_64': '/root/sxetest/publish_version/products/Drivers/X86_64/Linux/RHEL9/sxe2-*_rhel_9.1.x86_64.rpm'}
        cmd = 'uname -a'
        code, out, err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address)
        for os, rpm in os_rpm_dict.items():
            if os in out:
                os_file = rpm
        if not os_file:
            return None
        cmd = f'ls {os_file}'
        code, out, err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address)
        if code == RtnStatusEnum.SUCCESS.value:
            file = out
        return file

    @classmethod
    def install_rpm(cls, file=None, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value):
        """
        author: jianghe
        date:   2025.11.10
        description: 安装rpm
        """
        if file is None:
            file = CommonOperationReset.get_rpm_file(cmd_execute_address)
        cmd = f'rpm -ivh {file}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd, cmd_execute_address=cmd_execute_address)
        log.info(f'命令{cmd}的返回信息是{code}\n{out}\n{err}')
        if 'sxe2' in out:
            return True
        else:
            return False

    @classmethod
    def erase_rpm(cls, file=None, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value):
        """
        author: jianghe
        date:   2026.01.05
        description: 卸载rpm
        """
        os_rpm_dict = {
            '5.14.0-162.6.1.el9_1.x86_64': 'sxe2-*_elrhel_9.1-1.x86_64'}
        if file is None:
            cmd = 'uname -a'
            code, out, err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address)
            for os, rpm in os_rpm_dict.items():
                if os in out:
                    file = rpm
        if not file:
            CommonOperation.create_bug_problem(ScriptBase, key_word='rpm',
                                               description_word=f'没有找到正确的rpm包')
        cmd = f'rpm -e {file}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd, cmd_execute_address=cmd_execute_address)
        log.info(f'命令{cmd}的返回信息是{code}\n{out}\n{err}')
        if 'sxe2' in out:
            return True
        else:
            return False

    @classmethod
    def get_default_queue_num(cls, bus_info, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value):
        """
        author: jianghe
        date:   2026.03.07
        description: 获取默认的队列数
        """
        cmd = f'lspci -vvs {bus_info}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address=cmd_execute_address)
        if '1ff2:0c22' in out or '1ff2:0c23' in out:  # OCPx2, OCPx4
            return True
        elif '1ff2:0c21' in out or '1ff2:0c24' in out:  # PCIex2, 衍生卡
            return False

    @classmethod
    def get_max_vf_num(cls, bus_info, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value):
        """
        author: jianghe
        date:   2026.03.07
        description: 获取默认的队列数
        """
        cmd = f'lspci -vvs {bus_info}'
        code, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address=cmd_execute_address)
        if  '1ff2:0c23' in out:  # OCPx4
            return int(constants.MAX_VF_NUM / 4)
        # elif '1ff2:0c21' in out or '1ff2:0c24' in out or '1ff2:0c22' in out:  # PCIex2, 衍生卡, ocpx2
        else:  # PCIex2, 衍生卡, ocpx2
            return int(constants.MAX_VF_NUM / 2)

