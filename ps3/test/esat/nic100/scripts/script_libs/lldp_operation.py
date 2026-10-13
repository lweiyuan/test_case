import datetime
import os.path

import add_syspath
from typing import Union
import functools
import re
from enum import Enum, unique
from scripts.script_libs import log
from scripts.script_libs import constants
from scripts.script_libs.script_base import ScriptBase
from scripts.script_libs.file_operation import FileOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum, CliStatusEnum, ExitCodeEnum
from scripts.script_libs.constants import CHECK_ENCODE, COREDUMP_SIZE
from scripts.script_libs.command_operation import CommandOperation
from re import findall, S
from scripts.nic100.linux.driver.lldp.script_base_driver_lldp_check import ScriptBaseLLDPCheck
from collections import defaultdict
from scripts.script_libs.script_base import ScriptBase


@unique
class LLDPMode(Enum):
    RXTX = 'rxtx'
    RX = 'rx'
    TX = 'tx'
    Disabled = 'disabled'


@unique
class LLDPTLV(Enum):
    Chassis_ID_TLV = 'Chassis ID TLV'
    Port_ID_TLV = 'Port ID TLV'
    Time_to_Live_TLV = 'Time to Live TLV'
    End_TLV = 'End TLV'
    ETS_CFG = 'ETS Configuration Subtype'
    PFC_CFG = 'Priority Flow Control Configuration Subtype'
    ETS_REC = 'ETS Recommendation Subtype'


class LLDPOperation(ScriptBaseLLDPCheck):

    @classmethod
    def set_lldp_mode(cls, caller_class, device_name: str, mode: str,
                      exec_addr: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据device 执行cli命令
        :param caller_class: 调用者的类
        :param device_name: 设备名称ens4f0
        :param mode: lldp工作模式
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        cmd = f'lldptool set-lldp -i {device_name} adminStatus={mode}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}, error:{rtn_err}')
        else:
            log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(caller_class, key_word='设置LLDP工作模式',
                                               description_word=f'{cmd}执行失败',
                                               expect_info=f'{cmd}执行成功',
                                               result_info=f'{rtn_outputs}')

    @classmethod
    def get_lldp_mode(cls, caller_class, device_name: str, exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据device获取lldp工作模式
        :param caller_class: 调用者的类
        :param device_name: 设备名称ens4f0
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        cmd = f'lldptool get-lldp -i {device_name} adminStatus'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}')
            return rtn_outputs
        else:
            log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(caller_class, key_word='获取LLDP工作模式失败',
                                               description_word=f'{cmd}执行失败',
                                               expect_info=f'{cmd}执行成功',
                                               result_info=f'{rtn_outputs}')

    @classmethod
    def lldp_time_check(cls, caller_class, lldp_list: list, time_expect: int,
                        exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据lldp_list检查lldp报文发送间隔
        :param caller_class: 调用者的类
        :param lldp_list: lldp报文列表
        :param time_expect: 期望的lldp报文发送间隔
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        if len(lldp_list) < 2:
            log.info(f'LLDP报文获取数量太少, 预期至少获取2条lldp报文, 实际lldp报文数量：{len(lldp_list)}')
            CommonOperation.create_bug_problem(caller_class, key_word='获取的LLDP报文数量不符合预期',
                                               description_word='获取的LLDP报文数量不符合预期',
                                               expect_info='至少获取2条lldp报文',
                                               result_info=f'实际lldp报文数量：{len(lldp_list)}')
        time0 = lldp_list[-2].split(' ')[0]
        time1 = lldp_list[-1].split(' ')[0]
        log.info(time0)
        log.info(time1)
        time_0 = int(time0.split(".")[0][6:8])
        time_1 = int(time1.split(".")[0][6:8])
        if time_1 < time_0:
            time_1 += 60

        # if 0 <= abs(time_1 - time_0 - time_expect) <= 2:
        #     log.info('LLDP报文发送间隔符合预期，time=' + str(time_1 - time_0))
        # else:
        #     CommonOperation.create_bug_problem(caller_class, key_word='LLDP',
        #                                        description_word=f'两条lldp报文间隔不等于{time_expect}s(允许1s误差)',
        #                                        expect_info=f'{time_expect}',
        #                                        result_info=str(time_1 - time_0))

    @classmethod
    def get_lldp_list(cls, caller_class, mac: str, exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 获取lldp list
        :param caller_class: 调用者的类
        :param mac
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        if exec_addr == CmdExecuteAdressEnum.SERVER.value:
            read_pcap_cmd = f'tcpdump -r {cls.server_file} -n -v '
        else:
            read_pcap_cmd = f'tcpdump -r {cls.client_file} -n -v '
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(read_pcap_cmd,
                                                                                     cmd_execute_address=exec_addr,
                                                                                     print_outputs=False)
        # 分割成行
        lines = rtn_outputs.splitlines()
        # 将行重新组合，两个特定字符串之间视为一个分割的部分
        parts = []
        server_list = []
        client_list = []
        current_part = []
        for line in lines:
            if "End TLV (0), length 0" in line:
                if current_part:
                    parts.append("\n".join(current_part))
                    current_part = []
            else:
                current_part.append(line)
        # 添加最后一部分
        if current_part:
            parts.append("\n".join(current_part))
        for part in parts:
            part = part.split('\n')
            for i in range(len(part)):
                if 'LLDP' not in part[0]:
                    part.pop(0)
                else:
                    break
            part = '\n'.join(part)
            if len(part) != 0:
                if mac in part:
                    part += '\n\t' + 'End TLV (0), length 0'
                    server_list.append(part)
                else:
                    part += '\n\t' + 'End TLV (0), length 0'
                    client_list.append(part)
        log.info('server_list:')
        print(server_list)
        log.info('client_list:')
        print(client_list)
        return server_list, client_list

    @classmethod
    def get_lldp_list_other(cls, caller_class, mac: str, exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author: liuding
        date  : 2025.07.09
        description: 获取lldp list
        :param caller_class: 调用者的类
        :param mac
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        if exec_addr == CmdExecuteAdressEnum.SERVER.value:
            read_pcap_cmd = f'tcpdump -r {cls.server_file_other} -n -v '
        else:
            read_pcap_cmd = f'tcpdump -r {cls.client_file} -n -v '
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(read_pcap_cmd,
                                                                                     cmd_execute_address=exec_addr,
                                                                                     print_outputs=False)
        # 分割成行
        lines = rtn_outputs.splitlines()
        # 将行重新组合，两个特定字符串之间视为一个分割的部分
        parts = []
        server_list = []
        client_list = []
        current_part = []
        for line in lines:
            if "End TLV (0), length 0" in line:
                if current_part:
                    parts.append("\n".join(current_part))
                    current_part = []
            else:
                current_part.append(line)
        # 添加最后一部分
        if current_part:
            parts.append("\n".join(current_part))
        for part in parts:
            part = part.split('\n')
            for i in range(len(part)):
                if 'LLDP' not in part[0]:
                    part.pop(0)
                else:
                    break
            part = '\n'.join(part)
            if len(part) != 0:
                if mac in part:
                    part += '\n\t' + 'End TLV (0), length 0'
                    server_list.append(part)
                else:
                    part += '\n\t' + 'End TLV (0), length 0'
                    client_list.append(part)
        log.info('server_list:')
        print(server_list)
        log.info('client_list:')
        print(client_list)
        return server_list, client_list

    @classmethod
    def get_lldp_info(cls, caller_class, lldp_list: list,  expect_tlv: str,
                      exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> list:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据lldp_list获取对应字段信息
        :param caller_class: 调用者的类
        :param lldp_list:lldp报文列表
        :param expect_tlv:目标TLV
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        if len(lldp_list) < 1:
            log.info(f'LLDP报文获取数量太少, 预期至少获取1条lldp报文, 实际lldp报文数量：{len(lldp_list)}')
            CommonOperation.create_bug_problem(caller_class, key_word='获取的LLDP报文数量不符合预期',
                                               description_word='获取的LLDP报文数量不符合预期',
                                               expect_info='至少获取1条lldp报文',
                                               result_info=f'实际lldp报文数量：{len(lldp_list)}')
        lldp_list[-1].split('\n\t')
        if expect_tlv == LLDPTLV.Chassis_ID_TLV.value:
            if LLDPTLV.Chassis_ID_TLV.value in lldp_list[-1]:
                return lldp_list[-1].split('\n\t')[1:3]
            else:
                CommonOperation.create_bug_problem(caller_class, key_word='获取的LLDP报文信息失败',
                                                   description_word='获取的LLDP报文信息失败',
                                                   expect_info=f'获取的LLDP报文信息包含：{LLDPTLV.Chassis_ID_TLV.value}',
                                                   result_info=f'实际lldp报文：{lldp_list[-1]}')
        if expect_tlv == LLDPTLV.Port_ID_TLV.value:
            if LLDPTLV.Port_ID_TLV.value in lldp_list[-1]:
                return lldp_list[-1].split('\n\t')[3:5]
            else:
                CommonOperation.create_bug_problem(caller_class, key_word='获取的LLDP报文信息失败',
                                                   description_word='获取的LLDP报文信息失败',
                                                   expect_info=f'获取的LLDP报文信息包含：{LLDPTLV.Port_ID_TLV.value}',
                                                   result_info=f'实际lldp报文：{lldp_list[-1]}')
        if expect_tlv == LLDPTLV.Time_to_Live_TLV.value:
            if LLDPTLV.Time_to_Live_TLV.value in lldp_list[-1]:
                return lldp_list[-1].split('\n\t')[5:6]
            else:
                CommonOperation.create_bug_problem(caller_class, key_word='获取的LLDP报文信息失败',
                                                   description_word='获取的LLDP报文信息失败',
                                                   expect_info=f'获取的LLDP报文信息包含：{LLDPTLV.Time_to_Live_TLV.value}',
                                                   result_info=f'实际lldp报文：{lldp_list[-1]}')
        if expect_tlv == LLDPTLV.End_TLV.value:
            if LLDPTLV.End_TLV.value in lldp_list[-1]:
                return lldp_list[-1].split('\n\t')[-1:]
            else:
                CommonOperation.create_bug_problem(caller_class, key_word='获取的LLDP报文信息失败',
                                                   description_word='获取的LLDP报文信息失败',
                                                   expect_info=f'获取的LLDP报文信息包含：{LLDPTLV.End_TLV.value}',
                                                   result_info=f'实际lldp报文：{lldp_list[-1]}')
        if expect_tlv == LLDPTLV.ETS_CFG.value:
            if LLDPTLV.ETS_CFG.value in lldp_list[-1]:
                return lldp_list[-1].split('\n\t')[7:18]
            else:
                CommonOperation.create_bug_problem(caller_class, key_word='获取的LLDP报文信息失败',
                                                   description_word='获取的LLDP报文信息失败',
                                                   expect_info=f'获取的LLDP报文信息包含：{LLDPTLV.ETS_CFG.value}',
                                                   result_info=f'实际lldp报文：{lldp_list[-1]}')
        if expect_tlv == LLDPTLV.PFC_CFG.value:
            if LLDPTLV.PFC_CFG.value in lldp_list[-1]:
                return lldp_list[-1].split('\n\t')[-6:-1]
            else:
                CommonOperation.create_bug_problem(caller_class, key_word='获取的LLDP报文信息失败',
                                                   description_word='获取的LLDP报文信息失败',
                                                   expect_info=f'获取的LLDP报文信息包含：{LLDPTLV.PFC_CFG.value}',
                                                   result_info=f'实际lldp报文：{lldp_list[-1]}')
        if expect_tlv == LLDPTLV.ETS_REC.value:
            if LLDPTLV.ETS_REC.value in lldp_list[-1]:
                return lldp_list[-1].split('\n\t')[19:30]
            else:
                CommonOperation.create_bug_problem(caller_class, key_word='获取的LLDP报文信息失败',
                                                   description_word='获取的LLDP报文信息失败',
                                                   expect_info=f'获取的LLDP报文信息包含：{LLDPTLV.ETS_REC.value}',
                                                   result_info=f'实际lldp报文：{lldp_list[-1]}')

    @classmethod
    def get_lldp_info_fw(cls, caller_class, lldp_list: list, expect_tlv: str,
                      exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> list:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据lldp_list获取对应字段信息
        :param caller_class: 调用者的类
        :param lldp_list:lldp报文列表
        :param expect_tlv:目标TLV
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 提取的TLV信息列表
        """
        if len(lldp_list) < 1:
            log.info(f'LLDP报文获取数量太少, 预期至少获取1条lldp报文, 实际lldp报文数量：{len(lldp_list)}')
            CommonOperation.create_bug_problem(caller_class, key_word='获取的LLDP报文数量不符合预期',
                                               description_word='获取的LLDP报文数量不符合预期',
                                               expect_info='至少获取1条lldp报文',
                                               result_info=f'实际lldp报文数量：{len(lldp_list)}')
            return []

        # 分割报文为行列表，避免重复分割
        tlv_lines = lldp_list[-1].split('\n\t')

        # 通用错误处理函数
        def handle_error():
            CommonOperation.create_bug_problem(
                caller_class,
                key_word='获取的LLDP报文信息失败',
                description_word='获取的LLDP报文信息失败',
                expect_info='获取的LLDP报文信息成功',
                result_info=f'实际lldp报文：{lldp_list[-1]}'
            )
            return []

        if expect_tlv == LLDPTLV.Chassis_ID_TLV.value:
            if LLDPTLV.Chassis_ID_TLV.value in lldp_list[-1]:
                return [line for line in tlv_lines if "Chassis ID TLV" in line or "Subtype MAC address" in line]
            else:
                return handle_error()

        if expect_tlv == LLDPTLV.Port_ID_TLV.value:
            if LLDPTLV.Port_ID_TLV.value in lldp_list[-1]:
                return [line for line in tlv_lines if "Port ID TLV" in line or "Subtype MAC address" in line]
            else:
                return handle_error()

        if expect_tlv == LLDPTLV.Time_to_Live_TLV.value:
            if LLDPTLV.Time_to_Live_TLV.value in lldp_list[-1]:
                return [line for line in tlv_lines if "Time to Live TLV" in line]
            else:
                return handle_error()

        if expect_tlv == LLDPTLV.End_TLV.value:
            if LLDPTLV.End_TLV.value in lldp_list[-1]:
                return [line for line in tlv_lines if "End TLV" in line]
            else:
                return handle_error()

        if expect_tlv == LLDPTLV.ETS_CFG.value:
            if LLDPTLV.ETS_CFG.value in lldp_list[-1]:
                # 查找ETS Configuration起始行
                start_index = None
                for i, line in enumerate(tlv_lines):
                    if "ETS Configuration Subtype" in line:
                        start_index = i
                        break
                if start_index is not None:
                    result = []
                    for line in tlv_lines[start_index:]:
                        result.append(line)
                        if line.startswith("TSA Assignment Table"):
                            # 找到TSA Assignment Table后再收集两行（表格内容）
                            next_idx = tlv_lines.index(line) + 2
                            if next_idx < len(tlv_lines):
                                result.extend(tlv_lines[tlv_lines.index(line) + 1:next_idx + 1])
                            break
                    return result
                return handle_error()
            else:
                return handle_error()

        if expect_tlv == LLDPTLV.PFC_CFG.value:
            if LLDPTLV.PFC_CFG.value in lldp_list[-1]:
                # 查找PFC Configuration起始行
                start_index = None
                for i, line in enumerate(tlv_lines):
                    if "Priority Flow Control Configuration Subtype (11)" in line:
                        start_index = i
                        break
                if start_index is not None:
                    result = []
                    for line in tlv_lines[start_index:]:
                        result.append(line)
                        # 遇到Value行则停止
                        if line.startswith("Value    :"):
                            break
                    return result
                return handle_error()
            else:
                return handle_error()

        if expect_tlv == LLDPTLV.ETS_REC.value:
            if LLDPTLV.ETS_REC.value in lldp_list[-1]:
                # 查找ETS Recommendation起始行
                start_index = None
                for i, line in enumerate(tlv_lines):
                    if "ETS Recommendation Subtype" in line:
                        start_index = i
                        break
                if start_index is not None:
                    result = []
                    for line in tlv_lines[start_index:]:
                        result.append(line)
                        if line.startswith("TSA Assignment Table"):
                            # 找到TSA Assignment Table后再收集两行（表格内容）
                            next_idx = tlv_lines.index(line) + 2
                            if next_idx < len(tlv_lines):
                                result.extend(tlv_lines[tlv_lines.index(line) + 1:next_idx + 1])
                            break
                    return result
                return handle_error()
            else:
                return handle_error()

        # 未匹配到任何TLV类型
        log.info(f'未找到匹配的TLV类型: {expect_tlv}')
        return []

    @classmethod
    def set_eth_mac(cls, caller_class, device_name: str, mac: str,
                    exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据device_name修改pf mac地址
        :param caller_class: 调用者的类
        :param device_name: 设备名称ens4f0
        :param mac: mac地址
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        cmd = f'ifconfig {device_name} hw ether {mac}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}')
        else:
            log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(caller_class, key_word='设置pf mac地址失败',
                                               description_word=f'{cmd}执行失败',
                                               expect_info=f'{cmd}执行成功',
                                               result_info=f'{rtn_outputs}')

    @classmethod
    def get_eth_mac(cls, caller_class, device_name: str, exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据device_name获取pf mac地址
        :param caller_class: 调用者的类
        :param device_name: 设备名称ens4f0
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        cmd = f"ifconfig {device_name} |grep ether |awk {{'print $2'}}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}')
            return  rtn_outputs
        else:
            log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(caller_class, key_word='获取pf mac地址失败',
                                               description_word=f'{cmd}执行失败',
                                               expect_info=f'{cmd}执行成功',
                                               result_info=f'{rtn_outputs}')

    @classmethod
    def set_lldp_pfc_info(cls, caller_class, device_name: str, willing: bool = True, enabled: str = 'none',
                          exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据device_name设置PFC信息
        :param caller_class: 调用者的类
        :param device_name: 设备名称ens4f0
        :param willing:
        :param enabled:
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        if willing:
            willing_value = 'yes'
        else:
            willing_value = 'no'
        cmd = f'lldptool -T -i {device_name} -V PFC willing={willing_value} enabled={enabled}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}')
        else:
            log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(caller_class, key_word='设置pfc 配置信息失败',
                                               description_word=f'{cmd}执行失败',
                                               expect_info=f'{cmd}执行成功',
                                               result_info=f'{rtn_outputs}')

    @classmethod
    def set_lldp_ets_cfg_info(cls, caller_class, device_name: str, willing: bool = True, tsa: str = None,
                              up2tc: str = None, tcbw: str = None,
                              exec_addr: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> None:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据device_name设置ETS-CFG信息
        :param caller_class: 调用者的类
        :param device_name: 设备名称ens4f0
        :param willing:
        :param tsa:
        :param up2tc:
        :param tcbw:
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        if willing:
            willing_value = 'yes'
        else:
            willing_value = 'no'
        cmd = f'lldptool -T -i {device_name} -V ETS-CFG willing={willing_value} '
        if tsa is not None:
            cmd += f' tsa={tsa}'
        if up2tc is not None:
            cmd += f' up2tc={up2tc} '
        if tcbw is not None:
            cmd += f' tcbw={tcbw} '
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}')
        else:
            log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(caller_class, key_word='设置ets-cfg配置信息失败',
                                               description_word=f'{cmd}执行失败',
                                               expect_info=f'{cmd}执行成功',
                                               result_info=f'{rtn_outputs}')

    @classmethod
    def set_lldp_ets_rec_info(cls, caller_class, device_name: str, enable: bool = True, tsa: str = None,
                              up2tc: str = None, tcbw: str = None,
                              exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据device_name设置ETS-REC信息
        :param caller_class: 调用者的类
        :param device_name: 设备名称ens4f0
        :param enable:
        :param tsa:
        :param up2tc:
        :param tcbw:
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        if enable:
            enabletx = 'yes'
        else:
            enabletx = 'no'
        cmd = f'lldptool -T -i {device_name} -V ETS-REC enableTx={enabletx} '
        if tsa is not None:
            cmd += f' tsa={tsa}'
        if up2tc is not None:
            cmd += f' up2tc={up2tc} '
        if tcbw is not None:
            cmd += f' tcbw={tcbw} '
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}')
        else:
            log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(caller_class, key_word='设置ets-rec配置信息失败',
                                               description_word=f'{cmd}执行失败',
                                               expect_info=f'{cmd}执行成功',
                                               result_info=f'{rtn_outputs}')

    @classmethod
    def set_lldp_app_info(cls, caller_class, device_name: str, enable: bool = True,
                          exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author: jinbo.zhang
        date  : 2025.2.15
        description: 根据device_name设置App信息
        :param caller_class: 调用者的类
        :param device_name: 设备名称ens4f0
        :param enable:
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        if enable:
            enabletx = 'yes'
        else:
            enabletx = 'no'
        cmd = f'lldptool -T -i {device_name} -V App enableTx={enabletx} '
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(cmd, cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{cmd}执行成功, outputs:{rtn_outputs}')
        else:
            log.info(f'command:{cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(caller_class, key_word='设置App配置信息失败',
                                               description_word=f'{cmd}执行失败',
                                               expect_info=f'{cmd}执行成功',
                                               result_info=f'{rtn_outputs}')

    @classmethod
    def set_device_ifconfig(cls, caller_class, device_name: str, status: str = 'down',
                            exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author: jinbo.zhang
        date  : 2024.11.06
        description: 根据device_name设置ifconfig
        :param caller_class: 调用者的类
        :param device_name: 设备名称ens4f0
        :param status:
        :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        return: 无返回值
        """
        ifconfig_cmd = f'ifconfig {device_name} {status}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(ifconfig_cmd,
                                                                                     cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{ifconfig_cmd}执行成功, outputs:{rtn_outputs}')
        else:
            log.info(f'command:{ifconfig_cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(caller_class, key_word=f'执行{ifconfig_cmd}命令',
                                               description_word=f'{ifconfig_cmd}执行失败',
                                               expect_info=f'{ifconfig_cmd}执行成功',
                                               result_info=f'{rtn_outputs}')

    @classmethod
    def check_info_is_same(cls, caller_class, result_info: str, expect_info: str, contain: bool = False,
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
                if expect_info in result_info:
                    log.info(f"实际值:{result_info}和预期信息:{expect_info}相同")
                else:
                    log.info(f"实际值:{result_info}和预期信息:{expect_info}不同")
                    CommonOperation.create_bug_problem(caller_class, key_word=f"LLDP信息检查失败",
                                                       description_word='LLDP信息检查失败',
                                                       expect_info='LLDP信息实际与预期一致',
                                                       result_info=f'result_info：{result_info}, '
                                                                   f'expect_info: {expect_info}')
            else:
                if result_info == expect_info:
                    log.info(f"实际值:{result_info}和预期信息:{expect_info}相同")
                else:
                    log.info(f"实际值:{result_info}和预期信息:{expect_info}不同")
                    CommonOperation.create_bug_problem(caller_class, key_word=f"LLDP信息检查失败",
                                                       description_word='LLDP信息检查失败',
                                                       expect_info='LLDP信息实际与预期一致',
                                                       result_info=f'result_info：{result_info}, expect_info: {expect_info}')
        else:
            if result_info != expect_info:
                log.info(f"实际值:{result_info}和预期信息:{expect_info}不同，符合预期")
            else:
                log.info(f"实际值:{result_info}和预期信息:{expect_info}一致，不符合预期")
                CommonOperation.create_bug_problem(caller_class, key_word=f"LLDP信息检查成功",
                                                   description_word='LLDP信息检查成功',
                                                   expect_info='LLDP信息检查实际与预期不同',
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
    def create_lldp_frame(cls, mac_address: str, ttl_seconds: int, pfc_flag: bool = True, pfc_willing: bool = True,
                          pfc_priority: int = 0b00000001, ets_cfg_flag: bool = True, ets_willing: bool = True,
                          ets_rec_flag: bool = True, rec_priority: bytes = bytes([0b00000000]) * 4,
                          rec_tc_bandwidth: str = '100,0,0,0,0,0,0,0', rec_tsa_assignment: str = 'ets') -> bytes:
        """
        author: jinbo.zhang
        date  : 2025.2.14
        description: 构造lldp报文
        :param mac_address: mac地址
        :param ttl_seconds: time to live
        :param pfc_flag: tlv是否添加pfc tlv
        :param pfc_willing:
        :param pfc_priority:
        :param ets_cfg_flag:
        :param ets_willing:
        :param ets_rec_flag:
        :param rec_priority:
        :param rec_tc_bandwidth:
        :param rec_tsa_assignment:
        return: 返回payload数值
        """
        mac_bytes = bytes(int(x, 16) for x in mac_address.split(":"))
        chassis_id_type = 1
        chassis_id_subtype = 4
        chassis_id_value = bytes([chassis_id_subtype]) + mac_bytes
        chassis_id_tlv = cls.build_tlv(chassis_id_type, chassis_id_value, 'chassis_id')
        port_id_type = 2
        port_id_subtype = 3
        port_id_value = bytes([port_id_subtype]) + mac_bytes
        port_id_tlv = cls.build_tlv(port_id_type, port_id_value, 'port_id')
        ttl_type = 3
        ttl_value = ttl_seconds.to_bytes(2, byteorder='big')
        ttl_tlv = cls.build_tlv(ttl_type, ttl_value, 'ttl')
        lldpdu = chassis_id_tlv + port_id_tlv + ttl_tlv
        if ets_cfg_flag:
            org_specific_type = 127
            oui = bytes.fromhex('0080c2')
            # OUI 子类型为 9
            oui_subtype = 9
            if ets_willing:
                willing = 0b10000000
            else:
                willing = 0b00000000
            ets_cfg_info = bytes([willing])
            # 四个字节表示ets-priority,一个字节的四位表示一个tc
            # bytes([0b00010000]) * 4
            # Priority : 0   1   2   3   4   5   6   7
            # Value    : 1   0   1   0   1   0   1   0
            # 两个8个字节分别表示TC Bandwidth Table，TSA Assignment Table
            ets_cfg_info += bytes([0b00000000]) * 4 + bytes([0b01100100]) + bytes([0b00000000]) * 7 + bytes([0b00000000]) * 8
            ets_cfg_org_specific_value = oui + bytes([oui_subtype]) + ets_cfg_info
            ets_cfg_org_specific_tlv = cls.build_tlv(org_specific_type, ets_cfg_org_specific_value, 'ets-cfg')
            lldpdu += ets_cfg_org_specific_tlv
        if ets_rec_flag:
            org_specific_type = 127
            oui = bytes.fromhex('0080c2')
            # OUI 子类型为 10
            oui_subtype = 10
            ets_rec_cfg_info = bytes([0b00000000])  # REC
            if rec_tc_bandwidth == '100,0,0,0,0,0,0,0':
                rec_tc_band_info = bytes([0b01100100]) + bytes([0b00000000]) * 7
            elif rec_tc_bandwidth == '50,50,0,0,0,0,0,0':
                rec_tc_band_info = bytes([0b00110010]) + bytes([0b00110010]) + bytes([0b00000000]) * 6
            else:
                rec_tc_band_info = bytes([0b00000000]) * 8
            if rec_tsa_assignment == 'ets':
                rec_tsa_info = bytes([0b00000010]) * 8
            else:
                rec_tsa_info = bytes([0b00000000]) * 8
            ets_rec_cfg_info += rec_priority + rec_tc_band_info + rec_tsa_info
            ets_rec_org_specific_value = oui + bytes([oui_subtype]) + ets_rec_cfg_info
            ets_rec_org_specific_tlv = cls.build_tlv(org_specific_type, ets_rec_org_specific_value, 'ets-rec')
            lldpdu += ets_rec_org_specific_tlv
        if pfc_flag:
            org_specific_type = 127
            oui = bytes.fromhex('0080c2')
            # OUI 子类型为 11
            oui_subtype = 11
            if pfc_willing:
                willing = 0b10001000
            else:
                willing = 0b00001000
            pfc_info = bytes([willing]) + bytes([pfc_priority])
            pfc_org_specific_value = oui + bytes([oui_subtype]) + pfc_info
            pfc_org_specific_tlv = cls.build_tlv(org_specific_type, pfc_org_specific_value, tlv_name='pfc')
            lldpdu += pfc_org_specific_tlv
        end_tlv = cls.build_tlv(0, b'', 'end')
        lldpdu += end_tlv
        lldpdu_str = lldpdu.decode('latin-1')
        if '\n' in lldpdu_str:
            lldpdu_str = lldpdu_str.replace('\n', '\\\n')
        if '\t' in lldpdu_str:
            lldpdu_str = lldpdu_str.replace('\t', '\\\t')
        lldpdu = lldpdu_str.encode('latin-1')
        print('lldpdu tlv bytes:', lldpdu)
        return lldpdu

    @classmethod
    def build_tlv(cls, type_val, value, tlv_name):
        # 计算长度
        # print('value:', value)
        length = len(value)
        # print('length:', length)
        # 组合类型和长度
        type_length = (type_val << 9) | length
        # print('type_length:', type_length)
        # 将类型和长度转换为 2 字节的字节对象
        type_length_bytes = type_length.to_bytes(2, byteorder='big')
        # print('type_length_bytes:', type_length_bytes)
        # 组合类型长度和值
        tlv_bytes = type_length_bytes + value
        print(tlv_name, ' tlv_bytes:', tlv_bytes)
        print('*************************************')
        return tlv_bytes

    @classmethod
    def get_lldp_by_lldptool(cls, caller_class, device_name, expect_info,
                             exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> list:
        """
        author: jinbo.zhang
        date  : 2025.2.17
        description: lldptool -t -i ens1f0获取lldp信息
        :param caller_class: 调用者的类
        :param device_name: 设备名称
        :param expect_info: 期待获取的值
        :param exec_addr: :param exec_addr: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选
        return: 返回信息
        """
        lldptool_cmd = f'lldptool -t -i {device_name}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(lldptool_cmd,
                                                                                     cmd_execute_address=exec_addr)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f'command:{lldptool_cmd}执行成功')
            lldp_list = rtn_outputs.splitlines()
            if expect_info == LLDPTLV.Chassis_ID_TLV.value:
                info = [line.strip() for line in lldp_list[:2]]
                return info
            elif expect_info == LLDPTLV.Port_ID_TLV.value:
                info = [line.strip() for line in lldp_list[2:4]]
                return info
            elif expect_info == LLDPTLV.Time_to_Live_TLV.value:
                info = [line.strip() for line in lldp_list[4:6]]
                return info
            elif expect_info == LLDPTLV.ETS_CFG.value:
                info = [line.strip() for line in lldp_list[6:13]]
                return info
            elif expect_info == LLDPTLV.PFC_CFG.value:
                info = [line.strip() for line in lldp_list[13:18]]
                return info
        else:
            log.info(f'command:{lldptool_cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
            CommonOperation.create_bug_problem(caller_class, key_word=f'执行{lldptool_cmd}命令',
                                               description_word=f'{lldptool_cmd}执行失败',
                                               expect_info=f'{lldptool_cmd}执行成功',
                                               result_info=f'{rtn_outputs}')


    
    