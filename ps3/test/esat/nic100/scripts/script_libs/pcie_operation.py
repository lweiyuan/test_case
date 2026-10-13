
#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      weifeng.meng
date:        2025/3/13
description: 检测host上aer错误情况，检测速率和带宽
"""
import re
import time
from enum import Enum
from pickletools import bytes8

from scripts.script_libs import pcie_constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum, BondModeEnum, MacVlanModeEnum, OpcodeEnum
from scripts.script_libs.pcie_constants import VENDOR_SPEC_CAP
from scripts.script_libs.pcie_pcituils import SetpciOperation, LspciOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.script_base import ScriptBase, SxeThread
from scripts.script_libs.iperf_operation import IperfOperation
from scripts.script_libs.pcie_info import PcieTreeOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum, BondModeEnum, MacVlanModeEnum, OpcodeEnum
from scripts.script_libs.socket_operation import SocketOption
from scripts.script_libs.ifconfig import IfConfig

class AerCheckOperation(object):
    @classmethod
    def enable_base_report(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        output = SetpciOperation.setpci_cmd(dbdf_number, 'COMMAND', '0.w', 'r', cmd_execute_address)
        output = int(output, 16) | 0x100
        output = SetpciOperation.setpci_cmd(dbdf_number, 'COMMAND', '0.w', hex(output), cmd_execute_address)
        output = SetpciOperation.setpci_cmd(dbdf_number, 'COMMAND', '0.w', 'r', cmd_execute_address)
        serr = int(output, 16) & 0x100
        if serr == 0x100:
            log.info(f"serr_aer上报状态值:{output}，serr_aer开启成功success!")
            return True
        else:
            log.info(f"serr_aer上报状态值:{output}，serr_aer开启失败failed!")
            CommonOperation.create_bug_problem(
            cls,
            key_word='serr_aer开启失败failed!',
            description_word=f'',
            expect_info=f'',
            result_info=f''
            )
            return False
        # assert serr == 0

    @classmethod
    def enable_aer_report(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: enableaer两种错误上报
        """
        check_flag: bool = False
        output = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '8.w', 'r', cmd_execute_address)
        output = int(output, 16) | 0xf
        output = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '8.w', hex(output), cmd_execute_address)
        output = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '8.w', 'r', cmd_execute_address)
        dev_ctr = int(output, 16) & 0xf
        if dev_ctr == 0xf:
            log.info(f"devctl_aer上报状态值:{output}，devctl_aer开启成功success!")
            return True
        else:
            log.info(f"devctl_aer上报状态值:{output}，devctl_aer开启失败failed!")
            CommonOperation.create_bug_problem(
            cls,
            key_word='devctl_aer开启失败failed!',
            description_word=f'',
            expect_info=f'',
            result_info=f''
            )
            return False
        # assert dev_ctr == 0
    @classmethod
    def close_base_report(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        output = SetpciOperation.setpci_cmd(dbdf_number, 'COMMAND', '0.w', 'r', cmd_execute_address)
        output = int(output, 16) & 0xfeff
        output = SetpciOperation.setpci_cmd(dbdf_number, 'COMMAND', '0.w', hex(output), cmd_execute_address)
        output = SetpciOperation.setpci_cmd(dbdf_number, 'COMMAND', '0.w', 'r', cmd_execute_address)
        serr = int(output, 16) & 0x100
        if serr == 0:
            log.info(f"serr_aer上报状态值:{output}，serr_aer关闭成功success!")
            return True
        else:
            log.info(f"serr_aer上报状态值:{output}，serr_aer关闭失败failed!")
            CommonOperation.create_bug_problem(
            cls,
            key_word='serr_aer关闭失败failed!',
            description_word=f'',
            expect_info=f'',
            result_info=f''
            )
            return False
        # assert serr == 0

    @classmethod
    def close_aer_report(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 关闭aer两种错误上报
        """
        check_flag: bool = False
        output = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '8.w', 'r', cmd_execute_address)
        output = int(output, 16) & 0xfff0
        output = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '8.w', hex(output), cmd_execute_address)
        output = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '8.w', 'r', cmd_execute_address)
        dev_ctr = int(output, 16) & 0xf
        if dev_ctr == 0:
            log.info(f"devctl_aer上报状态值:{output}，devctl_aer关闭成功success!")
            return True
        else:
            log.info(f"devctl_aer上报状态值:{output}，devctl_aer关闭失败failed!")
            CommonOperation.create_bug_problem(
            cls,
            key_word='devctl_aer关闭失败failed!',
            description_word=f'',
            expect_info=f'',
            result_info=f''
            )
            return False
        # assert dev_ctr == 0

    @classmethod
    def set_aer_ue_mask(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 关闭ue mask
        """
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', '8.l', 'ffffffff', cmd_execute_address)
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', '8.l', 'r', cmd_execute_address)
        ue_mask = int(output, 16) & 0x005ff010
        if ue_mask == 0x005ff010:
            log.info(f"ue的mask位值:{output}，ue的mask开启成功success!")
            return True
        else:
            log.info(f"ue的mask位值:{output}，ue的mask开启失败failed!")
            CommonOperation.create_bug_problem(
            cls,
            key_word='ue的mask开启失败failed!',
            description_word=f'',
            expect_info=f'',
            result_info=f''
            )    
            
            return False

    @classmethod
    def close_aer_ue_mask(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 开启ue mask
        """
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', '8.l', '0', cmd_execute_address)
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', '8.l', 'r', cmd_execute_address)
        ue_mask = int(output, 16) & 0x7fff030
        if ue_mask == 0:
            log.info(f"ue的mask位值:{output}，ue的mask关闭成功success!")
            return True
        else:
            log.info(f"ue的mask位值:{output}，ue的mask关闭失败failed!")
            CommonOperation.create_bug_problem(
            cls,
            key_word='ue的mask关闭失败failed!',
            description_word=f'',
            expect_info=f'',
            result_info=f''
            )    
            return False

    @classmethod
    def set_aer_ce_mask(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 开启ce mask
        """
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', '14.w', 'ffff', cmd_execute_address)
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', '14.w', 'r', cmd_execute_address)
        ce_mask = int(output, 16) & 0xf1c1
        if ce_mask == 0xf1c1:
            log.info(f"ce的mask位值:{output}，ce的mask开启成功success!")
            return True
        else:
            log.info(f"ce的mask位值:{output}，ce的mask开启失败failed!")
            return False

    @classmethod
    def close_aer_ce_mask(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 关闭ce mask
        """
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', '14.w', '0', cmd_execute_address)
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', '14.w', 'r', cmd_execute_address)
        ce_mask = int(output, 16) & 0xf1c1
        if ce_mask == 0:
            log.info(f"ce的mask位值:{output}，ce的mask关闭成功success!")
            return True
        else:
            log.info(f"ce的mask位值:{output}，ce的mask关闭失败failed!")
            return False

    @classmethod
    def close_aer_ue_severity(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 关闭severity
        """
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', 'c.l', '0', cmd_execute_address)
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', 'c.l', 'r', cmd_execute_address)
        ue_severity = int(output, 16) & 0xffffffdf
        if ue_severity == 0:
            log.info(f"ue_severity位值:{output}，ue_severity关闭成功success!")
            return True
        else:
            log.info(f"ue_severity位值:{output}，ue_severity关闭失败failed!")
            return False

    @classmethod
    def set_aer_ue_severity(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: set severity
        """
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', 'c.l', '0xffffffff', cmd_execute_address)
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', 'c.l', 'r', cmd_execute_address)
        ue_severity = int(output, 16) & 0x005ff030
        if ue_severity == 0x005ff030:
            log.info(f"ue_severity位值:{output}，ue_severity开启成功success!")
            return True
        else:
            log.info(f"ue_severity位值:{output}，ue_severity开启失败failed!")
            return False

    @classmethod
    def get_devdet_status(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 获取device status
        """
        output = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', 'a.b', 'r', cmd_execute_address)
        devdet_sta = int(output, 16) & 0xf
        if devdet_sta == 0:
            log.info(f"devdet_sta状态值:{output}，devdet_sta测试成功success!")
            return True
        else:
            log.info(f"devdet_sta状态值:{output}，devdet_sta测试失败failed!")
            return False

    @classmethod
    def get_aer_ue_status(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 获取ue status
        """
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', '4.l', 'r', cmd_execute_address)
        ue_sta = int(output, 16) & 0x7effffe
        if ue_sta == 0:
            log.info(f"ue_sta状态值:{output}，ue_sta测试成功success!")
            return True
        else:
            log.info(f"ue_sta状态值:{output}，ue_sta测试失败failed!")
            return False
        # assert ue_sta == 0

    @classmethod
    def get_aer_ce_status(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 获取ce status
        """
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', '10.l', 'r', cmd_execute_address)
        ce_sta = int(output, 16) & 0xffff
        if ce_sta == 0:
            log.info(f"ce_sta状态值:{output}，ce_sta测试成功success!")
            return True
        else:
            log.info(f"ce_sta状态值:{output}，ce_sta测试失败failed!")
            return False
        # assert ce_sta == 0

    @classmethod
    def clear_devdet_status(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 清除device status
        """
        output = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', 'a.b', 'f', cmd_execute_address)
        output = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', 'a.b', 'r', cmd_execute_address)
        devdet_sta = int(output, 16) & 0xf
        if devdet_sta == 0:
            log.info(f"devdet_sta状态值:{output}，devdet_sta清除成功success!")
            return True
        else:
            log.info(f"devdet_sta状态值:{output}，devdet_sta清除失败failed!")
            return False

    @classmethod
    def clear_aer_ue_status(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 清除ue status
        """
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', '4.l', 'ffffffff', cmd_execute_address)
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', '4.l', 'r', cmd_execute_address)
        ue_sta = int(output, 16) & 0x7fffffe
        if ue_sta == 0:
            log.info(f"ue_sta状态值:{output}，ue_sta清除成功success!")
            return True
        else:
            log.info(f"ue_sta状态值:{output}，ue_sta清除失败failed!")
            return False
        # assert ue_sta == 0

    @classmethod
    def clear_aer_ce_status(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 清除ce status
        """
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', '10.l', 'ffffffff', cmd_execute_address)
        output = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_AER', '10.l', 'r', cmd_execute_address)
        ce_sta = int(output, 16) & 0xffff
        if ce_sta == 0:
            log.info(f"ce_sta状态值:{output}，ce_sta清除成功success!")
            return True
        else:
            log.info(f"ce_sta状态值:{output}，ce_sta清除失败failed!")
            return False
        # assert ce_sta == 0

    @classmethod
    def get_lspci(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 获取lspci -vvvs空间信息
        """
        output = LspciOperation.lspci_cmd('-vvvs', dbdf_number, cmd_execute_address)
        log.info(f"lspci -vvvs信息:{output}")

    @classmethod
    def all_aer_clear(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 设置aer上报，开启mask，开启severity 清除status
        """






class LinkCheckOperation(object):
    """
    author:      weifeng.meng
    date:        2025/3/13
    description: 判断速率和带宽
    """

    @classmethod
    def judge_speed(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        output = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', 'c.w', 'r', cmd_execute_address)
        max_link_speed = int(output, 16) & 0xf
        output = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '12.w', 'r', cmd_execute_address)
        cur_link_speed = int(output, 16) & 0xf
        if max_link_speed == cur_link_speed:
            log.info(f"最大速率与当前速率一致:{cur_link_speed}，速率测试成功success!")
            return True
        else:
            log.info(f"最大速率与当前速率不一致:最大速率{max_link_speed}，当前速率{cur_link_speed}，速率测试失败failed!")
            CommonOperation.create_bug_problem(
            cls,
            key_word='最大速率与当前速率不一致',
            description_word=f'',
            expect_info=f'',
            result_info=f''
            )    
            return False

    @classmethod
    def judge_width(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        output = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', 'c.w', 'r', cmd_execute_address)
        output = int(output, 16)
        output = (output >> 4) & 0x3f
        max_link_width = output & 0x3f
        output = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '12.w', 'r', cmd_execute_address)
        output = int(output, 16)
        output = (output >> 4) & 0x3f
        cur_link_width = output & 0x3f
        if max_link_width == cur_link_width:
            log.info(f"最大带宽与当前带宽一致:{cur_link_width}，带宽测试成功success!")
            return True
        else:
            log.info(f"最大带宽与当前带宽不一致:最大带宽{max_link_width}，当前带宽{cur_link_width}，带宽测试失败failed!")
            CommonOperation.create_bug_problem(
            cls,
            key_word='最大带宽与当前带宽不一致',
            description_word=f'',
            expect_info=f'',
            result_info=f''
            )    
            return False

    @classmethod
    def jude_lane_width_rppf(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        # LinkCheckOperation.judge_speed(PcieTreeOperation.host_rp()[0].Dbdf_Number, cmd_execute_address)
        # LinkCheckOperation.judge_width(PcieTreeOperation.host_rp()[0].Dbdf_Number, cmd_execute_address)
        LinkCheckOperation.judge_speed(PcieTreeOperation.get_pf_dbdf()[0], cmd_execute_address)
        LinkCheckOperation.judge_width(PcieTreeOperation.get_pf_dbdf()[0], cmd_execute_address)

class AllPcieCheckOperation(object):
    @classmethod
    def all_aer_check(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 二次封装上面aer和link检查，方便调用
        """
        if AerCheckOperation.close_base_report(dbdf_number, CmdExecuteAdressEnum.SERVER.value) == True:
            log.info(f"aer base错误上报关闭正常，符合预期")
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='aer base错误上报关闭失败',
                description_word=f'请检查aer base错误上报是否能关闭',
                expect_info=f'',
                result_info=f''
            )
        if AerCheckOperation.close_aer_report(dbdf_number, CmdExecuteAdressEnum.SERVER.value) == True:
            log.info(f"aer base错误上报关闭正常，符合预期")
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='aer dev错误上报关闭失败',
                description_word=f'请检查aer dev错误上报是否能关闭',
                expect_info=f'',
                result_info=f''
            )
        # if AerCheckOperation.get_devdet_status(dbdf_number, CmdExecuteAdressEnum.SERVER.value) == True:
        #     log.info(f"aer devdet获取正常，符合预期")
        # else:
        #     CommonOperation.create_bug_problem(
        #         cls,
        #         key_word='aer devdet获取失败，符合预期',
        #         description_word=f'请检查aer devdet是否能读取',
        #         expect_info=f'',
        #         result_info=f''
        #     )
        if AerCheckOperation.get_aer_ce_status(dbdf_number, CmdExecuteAdressEnum.SERVER.value) == True:
            log.info(f"aer ce sta获取正常，符合预期")
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='aer ce sta获取失败，符合预期',
                description_word=f'请检查aer ce sta是否能读取',
                expect_info=f'',
                result_info=f''
            )
        if AerCheckOperation.get_aer_ue_status(dbdf_number, CmdExecuteAdressEnum.SERVER.value) == True:
            log.info(f"aer ue sta获取正常，符合预期")
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='aer ue sta获取失败，符合预期',
                description_word=f'请检查aer ue sta是否能读取',
                expect_info=f'',
                result_info=f''
            )

        if AerCheckOperation.close_aer_ce_mask(dbdf_number, CmdExecuteAdressEnum.SERVER.value) == True:
            log.info(f"aer ce mask正常，符合预期")
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='aer ce mask失败',
                description_word=f'请检查aer ce是否能mask',
                expect_info=f'',
                result_info=f''
            )
        if AerCheckOperation.close_aer_ue_mask(dbdf_number, CmdExecuteAdressEnum.SERVER.value) == True:
            log.info(f"aer ue mask正常，符合预期")
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='aer ue mask失败',
                description_word=f'请检查aer ue是否能mask',
                expect_info=f'',
                result_info=f''
            )
        if AerCheckOperation.close_aer_ue_severity(dbdf_number, CmdExecuteAdressEnum.SERVER.value) == True:
            log.info(f"aer ue serverity关闭正常，符合预期")
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='aer ue serverity关闭失败',
                description_word=f'请检查aer ue serverity是否能关闭',
                expect_info=f'',
                result_info=f''
            )
        if AerCheckOperation.clear_devdet_status(dbdf_number, CmdExecuteAdressEnum.SERVER.value) == True:
            log.info(f"aer devdet 清理正常，符合预期")
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='aer devdet 清理失败',
                description_word=f'请检查aer devdet是否能清除',
                expect_info=f'',
                result_info=f''
            )
        if AerCheckOperation.clear_aer_ce_status(dbdf_number, CmdExecuteAdressEnum.SERVER.value) == True:
            log.info(f"aer ce sta 清理正常，符合预期")
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='aer ce sta 清理失败',
                description_word=f'请检查aer ce sta是否能清除',
                expect_info=f'',
                result_info=f''
            )
        if AerCheckOperation.clear_aer_ue_status(dbdf_number, CmdExecuteAdressEnum.SERVER.value) == True:
            log.info(f"aer ue sta 清理正常，符合预期")
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='aer ue sta 清理失败',
                description_word=f'请检查aer ue sta是否能清除',
                expect_info=f'',
                result_info=f''
            )
    @classmethod
    def all_aer_check_rppf(cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        rp_bdf = PcieTreeOperation.host_rp()
        for _ in rp_bdf:
            AllPcieCheckOperation.all_aer_check(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
        pf_bdf = PcieTreeOperation.host_pf()
        for _ in pf_bdf:
            AllPcieCheckOperation.all_aer_check(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
            #AllPcieCheckOperation.all_link_check(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)




    @classmethod
    def all_link_check(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 二次封装上面aer和link检查，方便调用
        """
        if LinkCheckOperation.judge_width(dbdf_number, cmd_execute_address) == True:
            log.info(f"link 带宽检查正常，符合预期")
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='link 带宽检查异常，符合预期',
                description_word=f'请检查link 带宽',
                expect_info=f'',
                result_info=f''
            )
        if LinkCheckOperation.judge_speed(dbdf_number, cmd_execute_address) == True:
            log.info(f"link 速率检查正常，符合预期")
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='link 速率检查异常，符合预期',
                description_word=f'请检查link 速率',
                expect_info=f'',
                result_info=f''
            )
class DmesgCheckOperation(object):
    @classmethod
    def dmesg_check_clear(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        exec_command = "dmesg -C"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        return rtn_outputs
    @classmethod
    def dmesg_check_judge(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        exec_command = "dmesg | grep -E -i 'error|fail' "
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        lower_rtn_outputs = rtn_outputs.lower()
        if ("error" in lower_rtn_outputs) or ("fail" in lower_rtn_outputs):
            log.info("dmesg check fail", rtn_outputs)
        else:
            log.info("dmesg check success", rtn_outputs)
        return rtn_outputs

    def dmesg_check_clear_judge(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        exec_command = "dmesg -C"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        exec_command = "dmesg | grep -E -i 'error|fail' "
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        lower_rtn_outputs = rtn_outputs.lower()
        if ("error" in lower_rtn_outputs) or ("fail" in lower_rtn_outputs):
            log.info("dmesg check fail", rtn_outputs)
        else:
            log.info("dmesg check success", rtn_outputs)
        return rtn_outputs





class LinkChangeOpeation(object):
    @classmethod
    def link_speed_change(cls, dbdf_number: str, link_speed: str,
                          cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '30.b', 'r', cmd_execute_address)
        time.sleep(0.1)
        SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '30.b', link_speed, cmd_execute_address)
        time.sleep(0.1)
        res_read = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '30.b', 'r', cmd_execute_address)
        time.sleep(0.1)
        return res_read

    @classmethod
    def link_width_change(cls, link_width:int, dbdf_number: str,
                          cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        exec_command = f'{pcie_constants.SXECLID} -d {dbdf_number} set reg type=A width=8 addr={pcie_constants.REG_LANE} 0xc{link_width}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        time.sleep(0.1)
        return rtn_outputs

    @classmethod
    def echo_function_level_reset(cls,dbdf_number:str,cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        log.info(dbdf_number)
        dbdf_number_list = dbdf_number.split(":")
        exec_command = "echo 1 >/sys/bus/pci/devices/0000\:"+ dbdf_number_list[1] + "\:"+ dbdf_number_list[2]+"/reset"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        # time.sleep(10)
        # exec_command = f'pkill -ef iperf3 ; sleep 1'
        # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
        #     exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        # exec_command = f'ps -ef|grep iperf3'
        # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
        #     exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        # count = rtn_outputs.count('iperf3')
        # if count > 2:
        #     log.info("run io 在后台", rtn_outputs)
        # else:
        #     log.info("无 io 在后台", rtn_outputs)
        # time.sleep(15)

    @classmethod
    def get_host_ltssm(cls,dbdf_number:str,cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        log.info(dbdf_number)
        exec_command = "./scgbeclid_0.6.0.7_x86_64  -d " + dbdf_number + " custom scgbe pcietrace cnt=16"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        log.info(f"result = {rtn_outputs}")
        return rtn_outputs

    @classmethod
    def get_uart_ltssm(cls,socket_ip,socket_port):
        out = SocketOption.exec_socket_cmd('/debug custom sxe2 pcietrace cnt=64', socket_ip,socket_port)
        log.info(f'result = {out}')
        return out

    @classmethod
    def set_bdf_ASPMl0enable(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        exec_command = "setpci -s " + dbdf_number + " cap_exp+10.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)

        exec_command = "setpci -s " + dbdf_number + f" cap_exp+10.w=0x0:0x3"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        time.sleep(1)
        exec_command = "setpci -s " + dbdf_number + " cap_exp+10.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        exec_command = "lspci -vvs " + dbdf_number + " |grep LnkCap: -A3"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        result = rtn_outputs
        if "ASPM Disabled" in result:
            log.info(f"#######################-配置{dbdf_number} ASPM L0 success!!!-#######################")
        else:
            log.info(
                f"#######################-配置{dbdf_number} ASPM L0 fail,请查看具体原因!!!-#######################")
            # assert False



    @classmethod
    def set_bdf_ASPMl1enable(cls,dbdf_number:str,cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        exec_command = "setpci -s " + dbdf_number + " cap_exp+10.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        value = rtn_outputs
        set_value = hex(int(value, 16) | 0x0002)

        exec_command = "setpci -s " + dbdf_number + f" cap_exp+10.w=0x2:0x3"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        time.sleep(1)
        exec_command = "setpci -s " + dbdf_number + " cap_exp+10.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        exec_command = "lspci -vvs " + dbdf_number + " |grep LnkCap: -A3"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                          cmd_execute_address=cmd_execute_address)
        result = rtn_outputs
        if "ASPM L1 Enabled" in result:
            log.info(f"#######################-配置{dbdf_number} ASPM L1 enable success!!!-#######################")
        else:
            log.info(
                f"#######################-配置{dbdf_number} ASPM L1 enable fail,请查看具体原因!!!-#######################")
            #assert False


    @classmethod
    def set_bdf_ASPMl1disable(cls,dbdf_number:str,cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        exec_command = "setpci -s " + dbdf_number + " cap_exp+10.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        value = rtn_outputs
        set_value = hex(int(value, 16) & 0xfffd)

        exec_command = "setpci -s " + dbdf_number + f" cap_exp+10.w={set_value}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        time.sleep(1)
        exec_command = "setpci -s " + dbdf_number + " cap_exp+10.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        exec_command = "lspci -vvs " + dbdf_number + " |grep LnkCap: -A3"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                          cmd_execute_address=cmd_execute_address)
        result = rtn_outputs
        if "ASPM L1 Enabled" in result:
            log.info(
                f"#######################-配置{dbdf_number} ASPM L1 disable fail,请查看具体原因!!!-#######################")
        else:
            log.info(f"#######################-配置{dbdf_number} ASPM L1 disable success!!!-#######################")

    @classmethod
    def set_bdf_ASPMl0senable(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        exec_command = "setpci -s " + dbdf_number + " cap_exp+10.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        # value = rtn_outputs
        # set_value = hex(int(value, 16) | 0x0001)

        exec_command = "setpci -s " + dbdf_number + f" cap_exp+10.w=0x1:0x3"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        time.sleep(1)
        exec_command = "setpci -s " + dbdf_number + " cap_exp+10.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        exec_command = "lspci -vvs " + dbdf_number + " |grep LnkCap: -A3"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        result = rtn_outputs
        if "ASPM L0s Enabled" in result:
            log.info(f"#######################-配置{dbdf_number} ASPM L0s enable success!!!-#######################")
        else:
            log.info(
                f"#######################-配置{dbdf_number} ASPM L0s enable fail,请查看具体原因!!!-#######################")


    @classmethod
    def set_bdf_ASPMl0sdisable(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        exec_command = "setpci -s " + dbdf_number + " cap_exp+10.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        value = rtn_outputs
        set_value = hex(int(value, 16) & 0xfffe)

        exec_command = "setpci -s " + dbdf_number + f" cap_exp+10.w={set_value}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        time.sleep(1)
        exec_command = "setpci -s " + dbdf_number + " cap_exp+10.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        exec_command = "lspci -vvs " + dbdf_number + " |grep LnkCap: -A3"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        result = rtn_outputs
        if "ASPM L0s Enabled" in result:
            log.info(
                f"#######################-配置{dbdf_number} ASPM L1 disable fail,请查看具体原因!!!-#######################")
        else:
            log.info(f"#######################-配置{dbdf_number} ASPM L1 disable success!!!-#######################")

    @classmethod
    def set_bdf_ASPMl0sandl1enable(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        exec_command = "setpci -s " + dbdf_number + " cap_exp+10.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        value = rtn_outputs
        set_value = hex(int(value, 16) | 0x0003)

        exec_command = "setpci -s " + dbdf_number + f" cap_exp+10.w={set_value}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        time.sleep(1)
        exec_command = "setpci -s " + dbdf_number + " cap_exp+10.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        exec_command = "lspci -vvs " + dbdf_number + " |grep LnkCap: -A3"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        result = rtn_outputs
        if "ASPM L0s L1 Enabled" in result:
            log.info(f"#######################-配置{dbdf_number} ASPM L0s L1 Enabled success!!!-#######################")
        else:
            log.info(
                f"#######################-配置{dbdf_number} ASPM L0s L1 Enabled fail,请查看具体原因!!!-#######################")
            # assert False

    @classmethod
    def set_bdf_ASPMl0sdisabletol1enable(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        exec_command = "setpci -s " + dbdf_number + " cap_exp+10.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        value = rtn_outputs
        set_value1 = int(value,16) & 0xfffe
        set_value = hex(set_value1 | 0x0002)

        exec_command = "setpci -s " + dbdf_number + f" cap_exp+10.w={set_value}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        time.sleep(1)
        exec_command = "setpci -s " + dbdf_number + " cap_exp+10.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        exec_command = "lspci -vvs " + dbdf_number + " |grep LnkCap: -A3"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        result = rtn_outputs
        if "ASPM L1 Enabled" not in result:
            log.info(
                f"#######################-配置{dbdf_number} ASPM L1 enable fail,请查看具体原因!!!-#######################")
        else:
            log.info(f"#######################-配置{dbdf_number} ASPM L1 enable success!!!-#######################")

    @classmethod
    def set_bdf_ASPMl1disabletol0senable(cls, dbdf_number: str,
                                         cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        exec_command = "setpci -s " + dbdf_number + " cap_exp+10.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        value = rtn_outputs
        set_value1 = int(value, 16) & 0xfffd
        set_value = hex(set_value1 | 0x0001)

        exec_command = "setpci -s " + dbdf_number + f" cap_exp+10.w={set_value}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        time.sleep(1)
        exec_command = "setpci -s " + dbdf_number + " cap_exp+10.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        exec_command = "lspci -vvs " + dbdf_number + " |grep LnkCap: -A3"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        result = rtn_outputs
        if "ASPM L0s Enabled" in result:
            log.info(f"#######################-配置{dbdf_number} ASPM L0s enable success!!!-#######################")
        else:
            log.info(
                f"#######################-配置{dbdf_number} ASPM L0s enable fail,请查看具体原因!!!-#######################")

    @classmethod
    def set_bdf_D3hotenable(cls, dbdf_number: str,
                            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        exec_command = "setpci -s " + dbdf_number + " cap_pm+4.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        # value = rtn_outputs
        # set_value = hex(int(value, 16) | 0x0003)
        exec_command = "setpci -s " + dbdf_number + f" cap_pm+4.w=0x3:0x3"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        exec_command = "setpci -s " + dbdf_number + " cap_pm+4.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        exec_command = "lspci -vvs " + dbdf_number + " |grep 'Power Management' -A3"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)

        time.sleep(1)
        result = rtn_outputs
        if "Status: D3" in result:
            log.info(f"#######################-配置 {dbdf_number} D3hot enable success!!!-#######################")
        else:
            log.info(f"#######################-配置 {dbdf_number} D3hot enable fail!!!-#######################")

    @classmethod
    def set_bdf_D3hotdisable(cls, dbdf_number: str,
                            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        exec_command = "setpci -s " + dbdf_number + " cap_pm+4.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        value = rtn_outputs
        set_value = hex(int(value, 16) & 0xfffc)
        exec_command = "setpci -s " + dbdf_number + f" cap_pm+4.w=0x0:0x3"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        exec_command = "setpci -s " + dbdf_number + " cap_pm+4.w"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)

        exec_command = "lspci -vvs " + dbdf_number + " |grep 'Power Management' -A3"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        result =  rtn_outputs
        if "Status: D3" in result:
            log.info(f"#######################-配置{dbdf_number} D3hot enable success!!!-#######################")
        else:
            log.info(f"#######################-配置{dbdf_number} D3hot enable fail!!!-#######################")

    @classmethod
    def judge_trace_ifL0(cls, dbdf_number:str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        result_trace_ifl0 = 1
        log.info("#######################-进行L0状态机的判断 start!!!-#######################")
        trace = LinkChangeOpeation.get_uart_ltssm(socket_ip='10.100.194.222',socket_port='5600')
        # last_trace = trace.strip().split('\n')[
        #     -1]  # last_trace_L1为：[31]   0x00000000_0b623450    S_RCVRY_IDLE            S_L0                 GEN4          X4

        """
        [32]   0x00000000_0c624450    S_RCVRY_IDLE            S_L0                 GEN5          X4
        """
        last_trace = trace.strip().split('\n')[
            -6]  # last_trace_L1为：[31]   0x00000000_0b623450    S_RCVRY_IDLE            S_L0                 GEN4          X4
        # log.info("#######################-trace打印中最后一行为{last_trace}L0状态################11111111111")
        # log.info(f"lalalalaall!!!last_trace={last_trace},lalalaalalalal!")
        start_index = last_trace.find('[') + 1  # 找到 '[' 的位置并加 1，即 '[' 后面的位置
        end_index = last_trace.find(']')  # 找到 ']' 的位置
        number_0 = last_trace[start_index:end_index]
        if "S_L0" in last_trace:
            log.info(
                f"#######################-trace打印中最后一行为{last_trace}L0状态，success !!!-#######################")
        else:
            log.info("#######################-trace打印中最后一行为非L0状态，fail !!!-#######################")
            result_trace_ifl0 = 0
            CommonOperation.create_bug_problem(cls,
                                               key_word='ASPM&PM测试',
                                               description_word=f'请检查测试log',
                                               expect_info='ASPM&PM测试成功',
                                               result_info='ASPM&PM测试失败')
            
            #assert False

        # 延迟5s判断第二次
        log.info("#######################-延迟5s进行第二次trace判断 !!!-#######################")
        time.sleep(5)

        trace = LinkChangeOpeation.get_uart_ltssm(socket_ip='10.100.194.222',socket_port='5600')
        last_trace = trace.strip().split('\n')[
            -6]  # last_trace_L1为：[31]   0x00000000_0b623450    S_RCVRY_IDLE            S_L0                 GEN4          X4
        start_index = last_trace.find('[') + 1  # 找到 '[' 的位置并加 1，即 '[' 后面的位置
        end_index = last_trace.find(']')  # 找到 ']' 的位置
        number_1 = last_trace[start_index:end_index]
        if "S_L0" in last_trace:
            log.info("#######################-trace打印中最后一行为L0状态，success !!!-#######################")
        else:
            log.info("#######################-trace打印中最后一行为非L0状态，fail !!!-#######################")
            result_trace_ifl0 = 0
            CommonOperation.create_bug_problem(cls,
                                               key_word='ASPM&PM测试',
                                               description_word=f'请检查测试log',
                                               expect_info='ASPM&PM测试成功',
                                               result_info='ASPM&PM测试失败')
            #assert False

        if number_1 == number_0:
            log.info(
                f"#######################-trace打印中最后一行前后两个数字都为{number_1}，success !!!-#######################")
        else:
            log.info("#######################-trace打印中最后一行数字前后不一致，fail !!!-#######################")
            result_trace_ifl0 = 0
            CommonOperation.create_bug_problem(cls,
                                               key_word='ASPM&PM测试',
                                               description_word=f'请检查测试log',
                                               expect_info='ASPM&PM测试成功',
                                               result_info='ASPM&PM测试失败')
            #assert False
        time.sleep(1)
        log.info("#######################-进行L0状态机的判断 end!!!-#######################")
        return result_trace_ifl0

    @classmethod
    def judge_trace_ifL0S(cls, dbdf_number:str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        result_trace_ifl0s = 1
        log.info("#######################-进行L0s状态机的判断 start!!!-#######################")
        trace = LinkChangeOpeation.get_uart_ltssm(socket_ip='10.100.194.222',socket_port='5600')
        last_trace = trace.strip().split('\n')[
            -6] #示例：串口中最后一行为：[42]02000006-0007fb452 S_L0S              ->S_L0                (g4,X8), D_NORM                ts:00, dur:16us
        log.info(f"串口中最后一行为：{last_trace}")
        start_index = last_trace.find('[') + 1  # 找到 '[' 的位置并加 1，即 '[' 后面的位置
        end_index = last_trace.find(']')  # 找到 ']' 的位置
        number_0 = last_trace[start_index:end_index]
        if "S_L0S" in last_trace and "S_L0" in last_trace:
            log.info("#######################-第一次判断L0S success !!!-#######################")
            result_trace_ifl0s = 1
        else:
            log.info("#######################-第一次判断L0S fail !!!-#######################")
            result_trace_ifl0s = 0
            CommonOperation.create_bug_problem(cls,
                                               key_word='ASPM&PM测试',
                                               description_word=f'请检查测试log',
                                               expect_info='ASPM&PM测试成功',
                                               result_info='ASPM&PM测试失败')
            #assert False

        # 延迟5s判断第二次
        log.info("#######################-延迟5s进行第二次trace判断 !!!-#######################")
        time.sleep(5)

        trace = LinkChangeOpeation.get_uart_ltssm(socket_ip='10.100.194.222',socket_port='5600')
        last_trace = trace.strip().split('\n')[
            -6]  # last_trace_L1为：[31]   0x00000000_0b623450    S_RCVRY_IDLE            S_L0                 GEN4          X4
        start_index = last_trace.find('[') + 1  # 找到 '[' 的位置并加 1，即 '[' 后面的位置
        end_index = last_trace.find(']')  # 找到 ']' 的位置
        number_1 = last_trace[start_index:end_index]
        if ("S_L0S" in last_trace) and ("S_L0 " in last_trace):
            log.info("#######################-第二次判断L0S success !!!-#######################")
            result_trace_ifl0s = 1
        else:
            log.info("#######################-第二次判断L0S fail !!!-#######################")
            result_trace_ifl0s = 0
            CommonOperation.create_bug_problem(cls,
                                               key_word='ASPM&PM测试',
                                               description_word=f'请检查测试log',
                                               expect_info='ASPM&PM测试成功',
                                               result_info='ASPM&PM测试失败')
            #assert False

        if number_1 != number_0:
            log.info(
                f"#######################-trace打印中最后一行前后两个数字不一致，测试success !!!-#######################")
        else:
            log.info("#######################-trace打印中最后一行数字前后一致,判断是否停在L0!!!-#######################")
            time.sleep(2)
            trace = LinkChangeOpeation.get_uart_ltssm(socket_ip='10.100.194.222',socket_port='5600')
            last_trace = trace.strip().split('\n')[
                -6]
            start_index = last_trace.find('[') + 1  # 找到 '[' 的位置并加 1，即 '[' 后面的位置
            end_index = last_trace.find(']')  # 找到 ']' 的位置
            number_2 = last_trace[start_index:end_index]
            if number_2 == number_1 == number_0:
                log.info(f"第1,2,3次的数字分别为:[{number_0},{number_1},{number_2}],值相等")
                if "S_L0S              ->S_L0" in last_trace:
                    log.info("#######################-状态机此时停在L0，测试fail!!!-#######################")
                    result_trace_ifl0s = 0
                    CommonOperation.create_bug_problem(cls,
                                                       key_word='ASPM&PM测试',
                                                       description_word=f'请检查测试log',
                                                       expect_info='ASPM&PM测试成功',
                                                       result_info='ASPM&PM测试失败')
                    # assert False
        time.sleep(1)
        log.info("#######################-进行L0s状态机的判断 end!!!-#######################")
        return result_trace_ifl0s

    """
           judge_trace_ifL1() 函数用来判断最后一行：
           1.最后一行数字是否刷新
           2.最后一行状态机是否为L1
           有错直接中断测试进程
    """
    @classmethod
    def judge_trace_ifL1(cls, dbdf_number:str,cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        log.info("#######################-进行L1状态机的判断 start!!!-#######################")
        trace = LinkChangeOpeation.get_uart_ltssm(socket_ip='10.100.194.222',socket_port='5600')
        last_trace = trace.strip().split('\n')[
            -6]  # last_trace_L1为：[31]   0x00000000_0b623450    S_RCVRY_IDLE            S_L0                 GEN4          X4
        start_index = last_trace.find('[') + 1  # 找到 '[' 的位置并加 1，即 '[' 后面的位置
        end_index = last_trace.find(']')  # 找到 ']' 的位置
        number_0 = last_trace[start_index:end_index]
        if "S_L1_IDLE" in last_trace:
            log.info("#######################-trace打印中最后一行为L1状态，success !!!-#######################")
        else:
            log.info("#######################-trace打印中最后一行为非L1状态，fail !!!-#######################")
            # assert False
            CommonOperation.create_bug_problem(cls,
                                               key_word='ASPM&PM测试',
                                               description_word=f'请检查测试log',
                                               expect_info='ASPM&PM测试成功',
                                               result_info='ASPM&PM测试失败')
        log.info("#######################-延迟5s进行第二次trace判断 !!!-#######################")
        time.sleep(5)
        # 判断第二次

        trace = LinkChangeOpeation.get_uart_ltssm(socket_ip='10.100.194.222',socket_port='5600')
        last_trace = trace.strip().split('\n')[
            -6]  # last_trace_L1为：[31]   0x00000000_0b623450    S_RCVRY_IDLE            S_L0                 GEN4          X4
        start_index = last_trace.find('[') + 1  # 找到 '[' 的位置并加 1，即 '[' 后面的位置
        end_index = last_trace.find(']')  # 找到 ']' 的位置
        number_1 = last_trace[start_index:end_index]
        if "S_L1_IDLE" in last_trace:
            log.info("#######################-trace打印中最后一行为L1状态，success !!!-#######################")
        else:
            log.info("#######################-trace打印中最后一行为非L1状态，fail !!!-#######################")
            CommonOperation.create_bug_problem(cls,
                                               key_word='ASPM&PM测试',
                                               description_word=f'请检查测试log',
                                               expect_info='ASPM&PM测试成功',
                                               result_info='ASPM&PM测试失败')
            # assert False

        if number_1 == number_0:
            log.info(
                f"#######################-trace打印中最后一行前后两个数字都为{number_1}，success !!!-#######################")
        else:
            log.info("#######################-trace打印中最后一行数字前后不一致，fail !!!-#######################")
            # assert False
            CommonOperation.create_bug_problem(cls,
                                               key_word='ASPM&PM测试',
                                               description_word=f'请检查测试log',
                                               expect_info='ASPM&PM测试成功',
                                               result_info='ASPM&PM测试失败')
        time.sleep(1)
        log.info("#######################-进行L1状态机的判断 end!!!-#######################")

    @classmethod
    def performance_eq_enable(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        res_read = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_SECPCI', '4.b', 'r', cmd_execute_address)
        SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_SECPCI', '4.b', hex(int(res_read, 16) | 0x01),
                                   cmd_execute_address)
        res_read = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_SECPCI', '4.b', 'r', cmd_execute_address)
        return res_read

    @classmethod
    def performance_eq_disable(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        res_read = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_SECPCI', '4.b', 'r', cmd_execute_address)
        SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_SECPCI', '4.b', hex(int(res_read, 16) & 0xfe),
                                   cmd_execute_address)
        res_read = SetpciOperation.setpci_cmd(dbdf_number, 'ECAP_SECPCI', '4.b', 'r', cmd_execute_address)
        return res_read

    @classmethod
    def link_retrain(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        res_read = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '10.w', 'r', cmd_execute_address)
        SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '10.w', hex(int(res_read, 16) | 0x20), cmd_execute_address)
        res_read = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '10.w', 'r', cmd_execute_address)
        return res_read

    @classmethod
    def link_secondary_bus_reset(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        res_read = SetpciOperation.setpci_cmd(dbdf_number, 'BRIDGE_CONTROL', '0.w', 'r', cmd_execute_address)
        SetpciOperation.setpci_cmd(dbdf_number, 'BRIDGE_CONTROL', '0.w', hex(int(res_read, 16) | 0x40),
                                   cmd_execute_address)
        res_read = SetpciOperation.setpci_cmd(dbdf_number, 'BRIDGE_CONTROL', '0.w', 'r', cmd_execute_address)
        time.sleep(1)
        SetpciOperation.setpci_cmd(dbdf_number, 'BRIDGE_CONTROL', '0.w', hex(int(res_read, 16) & 0xffbf),
                                   cmd_execute_address)
        res_read = SetpciOperation.setpci_cmd(dbdf_number, 'BRIDGE_CONTROL', '0.w', 'r', cmd_execute_address)
        time.sleep(1)
        return res_read

    @classmethod
    def link_disable(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        res_read = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '10.w', 'r', cmd_execute_address)
        SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '10.w', hex(int(res_read, 16) | 0x10), cmd_execute_address)
        res_read = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '10.w', 'r', cmd_execute_address)
        time.sleep(1)
        SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '10.w', hex(int(res_read, 16) & 0xffef), cmd_execute_address)
        res_read = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '10.w', 'r', cmd_execute_address)
        return res_read

    @classmethod
    def link_enable(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        res_read = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '10.w', 'r', cmd_execute_address)
        SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '10.w', hex(int(res_read, 16) & 0xffef), cmd_execute_address)
        res_read = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '10.w', 'r', cmd_execute_address)
        return res_read


class DriverOperation(object):
    @classmethod
    def rmmod_scgbe(cls,cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      yi.zhang
        date:        2025/7/11
        description: 卸载驱动
        """
        exec_command = "rmmod scgbe"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        time.sleep(1)
        exec_command = "rmmod scgbevf"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
    @classmethod
    def rmmod_sxe2(cls,cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
            """
            author:      yi.zhang
            date:        2025/7/11
            description: 卸载驱动
            """
            exec_command = "rmmod sxe2"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                        cmd_execute_address=cmd_execute_address)
            time.sleep(1)
            exec_command = "rmmod sxe2vf"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                        cmd_execute_address=cmd_execute_address)

    @classmethod
    def insmod_scgbe(self,cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
                author:      yi.zhang
                date:        2025/7/11
                description: 加载驱动
                """
        exec_command = "insmod /root/scgbe.ko"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        time.sleep(1)
        exec_command = "rmmod /root/scgbevf.ko"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        exec_command = "lsmod | grep scgbe"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        if "scgbe" in rtn_outputs:
            CommonOperation.concat_test_steps('驱动加载完成')
        else:
            CommonOperation.concat_test_steps('error!!!驱动加载失败')
            
    @classmethod
    def insmod_sxe2(self,cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
                author:      yi.zhang
                date:        2025/7/11
                description: 加载驱动
                """
        exec_command = "insmod /root/sxe2.ko"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        time.sleep(1)
        exec_command = "insmod /root/sxe2vf.ko"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        exec_command = "lsmod | grep sxe2"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        if "sxe2" in rtn_outputs:
            CommonOperation.concat_test_steps('驱动加载完成')
        else:
            CommonOperation.concat_test_steps('error!!!驱动加载失败')
    @classmethod
    def remove(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2026/2/9
        description: remove设备
        """
        pf_bdf = PcieTreeOperation.host_pf()
        for _ in reversed(pf_bdf):
            exec_command = f"echo 1 > /sys/bus/pci/devices/{_.Dbdf_Number}/remove"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        time.sleep(1)
        return rtn_outputs
    @classmethod
    def rescan(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2026/2/9
        description: rescan设备
        """
        exec_command = f"echo 1 > /sys/bus/pci/rescan"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        time.sleep(1)
        exec_command = f"sxe2cli show"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)        
        return rtn_outputs
    @classmethod
    def command_enable(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2026/2/9
        description: enable io/mem/busmaster
        """
        pf_bdf = PcieTreeOperation.host_pf()
        for _ in pf_bdf:
            output = SetpciOperation.setpci_cmd(_.Dbdf_Number, 'COMMAND', '0.w', 'r', cmd_execute_address)
            output = int(output, 16) | 0x507
            output = SetpciOperation.setpci_cmd(_.Dbdf_Number, 'COMMAND', '0.w', hex(output), cmd_execute_address)
            output = SetpciOperation.setpci_cmd(_.Dbdf_Number, 'COMMAND', '0.w', 'r', cmd_execute_address)
            command_en = int(output, 16) & 0x507
            if command_en != 0x507:
                log.info("command_enable io/mem/bus失败", _.Dbdf_Number,str(command_en))
                CommonOperation.create_bug_problem(
                cls,
                key_word='command_enable io/mem/bus失败',
                description_word=f'',
                expect_info=f'',
                result_info=f''
                ) 


class Pcie4KOperation(object):
    @classmethod
    def get_link_speed_sta(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 获取link speed status信息
        """
        res_read = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '12.b', 'r', cmd_execute_address)
        # speed_dict = {
        #     '1': '2.5GT/s',
        #     '2': '5GT/s',
        #     '3': '8GT/s',
        #     '4': '16GT/s',
        #     '5': '32GT/s',
        # }
        speed_value = int(res_read, 16) & 0x7
        time.sleep(0.1)
        return speed_value

    @classmethod
    def get_link_lane_sta(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      weifeng.meng
        date:        2025/3/13
        description: 获取link speed status信息
        """
        res_read = SetpciOperation.setpci_cmd(dbdf_number, 'CAP_EXP', '12.b', 'r', cmd_execute_address)
        lane_value = (int(res_read, 16) >> 4) & 0xf
        time.sleep(0.1)
        return lane_value

   
    @classmethod
    def create_vf(cls, ethname, vf_number, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author:      zhangyi3
        date:        2026/2/13
        description: 创建vf信息
        """
        exec_command = f"echo {vf_number} > /sys/class/net/{ethname}/device/sriov_numvfs"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(exec_command,
                                                                                     cmd_execute_address=cmd_execute_address)
        return rtn_outputs
    
class IOperation(object):
    @classmethod
    def iperf_tunnel_queues(cls, client_ip, server_ip,log_file_path, run_time):
        """
        author:      zhaohan.zheng
        date:        2025-02-25
        description: 待侧网卡与配测网卡启动多线程iperf3服务
        """
        cls.log_file_path = log_file_path
        
        exec_command = f'pkill -ef iperf3'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        count = rtn_outputs.count('iperf3')
        if count > 2:
            log.info("run io 在后台", rtn_outputs)
        else:
            log.info("无 io 在后台", rtn_outputs)

        server_service = SxeThread(IperfOperation(rpc_server_ip=server_ip).server_iperf, bind=server_ip)

        client_service = SxeThread(IperfOperation(
            run_time=run_time,  # 86400
            parallel_num=20,
            bandwidth="100G",
            packet_length=2000,  # (1, 1400),
            udp_flag=False,
            log_file=True,
            log_file_path=log_file_path,
            rpc_client_ip=client_ip).client_iperf, bind=client_ip, client=server_ip)

        server_service.daemon = True
        log.info("before iperf -s")
        server_service.start()
        log.info("after iperf -s")
        time.sleep(1)
        client_service.start()
        time.sleep(1)

    @classmethod
    def iperf_check(cls, log_file_path,exec_addr):
        cls.log_file_path = log_file_path
        log.info("检查iperf结果无异常")
        result = ''
        bitrate_pattern = r"\[SUM\].*?\s+(\d+\.?\d*)\s+(?:([GMK])?bits/sec)"
        check_iperf = f"grep SUM {cls.log_file_path}"
        rtn_code, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=check_iperf, cmd_execute_address=exec_addr)
        # 提取每个阶段的速率数值，查看是否存在明显降速的情况
        results = re.findall(bitrate_pattern, rtn_output)
        bitrate_values = []
        # 所有数据的单位统一为Mbits，然后进行比较
        for val, unit in results:
            val = float(val)
            if unit == 'G':
                val = val * 1000
            elif unit == 'K':
                val = val / 1000
            bitrate_values.append(val)
        float_results = [float(num) for num in bitrate_values]
        log.info(f"iperf 存在打流过程：{float_results}")
        # 判断没有跌0，或者测试过程没有明显降速
        min_val = min(float_results)
        max_val = max(float_results)
        # print(min_val,max_val,'######',float_results)
        if float_results[-2] > 0 and float_results[-1] > 0:
            log.info(f"iperf 存在打流过程：{float_results}")
            if float_results[-3] > 0 :
                log.info(f"iperf 打流能恢复起来：{float_results}")
            else:
                CommonOperation.create_bug_problem(
                cls,
                key_word='iperf3存在打流，但是未恢复成功',
                description_word=f'',
                expect_info=f'',
                result_info=f''
                ) 
        else:
            log.info(f"iperf 未存在打流：{float_results}")
            CommonOperation.create_bug_problem(
            cls,
            key_word='iperf3存在打流，但是未恢复成功',
            description_word=f'',
            expect_info=f'',
            result_info=f''
            ) 







    
class LinkParameterOperation(object):
    @classmethod
    def set_link_parameter(cls, paramete_list: list, speed_change_befored, speed_change_afterd,lane_change_befored,lane_change_afterd,cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        #time.sleep(30)
        CommonOperation.concat_test_steps(f'3.1 开始进行link切换测试：{paramete_list},speed_change_befored{speed_change_befored}, speed_change_afterd{speed_change_afterd},lane_change_befored{lane_change_befored},lane_change_afterd{lane_change_afterd}')
        if paramete_list[2] == 0:
            CommonOperation.concat_test_steps('3.1.3 测试条件,切lane')
            # 测试前统一带宽 lane_change_befored
            LinkChangeOpeation.link_width_change(lane_change_befored, PcieTreeOperation.get_pf_dbdf()[0],cmd_execute_address)
            # 判断统一参数是否切成功
            CommonOperation.concat_test_steps('3.1.3.1 判断lane change befored是否成功')
            if Pcie4KOperation.get_link_lane_sta(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                  cmd_execute_address) == Pcie4KOperation.get_link_lane_sta(
                PcieTreeOperation.get_pf_dbdf()[0],
                cmd_execute_address) == lane_change_befored:
                CommonOperation.concat_test_steps('3.1.3.1 lane change befored success成功')
            else:
                CommonOperation.concat_test_steps('3.1.3.1 lane change befored fail失败')
                CommonOperation.create_bug_problem(
                cls,
                key_word='3.1.3.1 lane change befored fail失败',
                description_word=f'',
                expect_info=f'',
                result_info=f''
                )
            # 测试切lane
            CommonOperation.concat_test_steps('3.1.4 进行lane change afterd测试')
            LinkChangeOpeation.link_width_change(lane_change_afterd, PcieTreeOperation.get_pf_dbdf()[0],cmd_execute_address)
            CommonOperation.concat_test_steps('3.1.4.1 判断lane change afterd是否成功')
            if Pcie4KOperation.get_link_lane_sta(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                 cmd_execute_address) == Pcie4KOperation.get_link_lane_sta(
                PcieTreeOperation.get_pf_dbdf()[0],
                cmd_execute_address) == lane_change_afterd:
                CommonOperation.concat_test_steps('3.1.4.1 lane change afterd success成功')
            else:
                CommonOperation.concat_test_steps('3.1.4.1 lane change afterd fail失败')
                CommonOperation.create_bug_problem(
                cls,
                key_word='3.1.4.1 lane change afterd fail失败',
                description_word=f'',
                expect_info=f'',
                result_info=f''
                )
        elif paramete_list[2] == 1:
            CommonOperation.concat_test_steps('3.1.3 测试条件,切speed')
            # 测试前统一速率 speed_change_befored
            LinkChangeOpeation.link_speed_change(PcieTreeOperation.host_rp()[0].Dbdf_Number, speed_change_befored,
                                                 cmd_execute_address)
            # LinkChangeOpeation.link_speed_change(PcieTreeOperation.get_pf_dbdf()[0], speed_change_befored,
            #                                      cmd_execute_address)
            LinkChangeOpeation.link_retrain(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                            cmd_execute_address)
            # 判断统一参数是否切成功
            CommonOperation.concat_test_steps('3.1.3.1 判断speed change befored是否成功')
            if Pcie4KOperation.get_link_speed_sta(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                 cmd_execute_address) == Pcie4KOperation.get_link_speed_sta(PcieTreeOperation.get_pf_dbdf()[0],
                                                 cmd_execute_address) == speed_change_befored:
                CommonOperation.concat_test_steps('3.1.3.1 speed change befored success成功')
            else:
                CommonOperation.concat_test_steps('3.1.3.1 speed change befored fail失败')
                CommonOperation.create_bug_problem(
                cls,
                key_word='3.1.3.1 speed change befored fail失败',
                description_word=f'',
                expect_info=f'',
                result_info=f''
                )
            # eq
            if paramete_list[1] == 0:
                CommonOperation.concat_test_steps('3.1.3.2 测试条件,performanceEQ关闭')
                LinkChangeOpeation.performance_eq_disable(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                          cmd_execute_address)
                
            elif paramete_list[1] == 1:
                CommonOperation.concat_test_steps('3.1.3.2 测试条件,performanceEQ开启')
                LinkChangeOpeation.performance_eq_enable(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                               cmd_execute_address)
            else:
                CommonOperation.concat_test_steps('3.1.3.2 测试条件,performanceEQ fail异常')
                CommonOperation.create_bug_problem(
                cls,
                key_word='3.1.3.2 测试条件,performanceEQ fail异常',
                description_word=f'',
                expect_info=f'',
                result_info=f''
                )
           # 切速
            CommonOperation.concat_test_steps('3.1.4 进行speed change after测试')
            # if paramete_list[5] == 1:
            LinkChangeOpeation.link_speed_change(PcieTreeOperation.host_rp()[0].Dbdf_Number, speed_change_afterd,
                                                     cmd_execute_address)
                # LinkChangeOpeation.link_speed_change(PcieTreeOperation.get_pf_dbdf()[0], speed_change_afterd,
                #                                      cmd_execute_address)
            # else:
            #     LinkChangeOpeation.link_speed_change(PcieTreeOperation.get_pf_dbdf()[0], speed_change_afterd,
            #                                          cmd_execute_address)
            # linkdisable
            if paramete_list[3] == 0:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,linkdisble关闭')
                # LinkChangeOpeation.link_enable(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                #                                cmd_execute_address)
            elif paramete_list[3] == 1:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,linkdisble开启')
                LinkChangeOpeation.link_disable(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                cmd_execute_address)
                DriverOperation.command_enable(CmdExecuteAdressEnum.SERVER.value)
                DriverOperation.remove(CmdExecuteAdressEnum.SERVER.value)
                DriverOperation.rescan(CmdExecuteAdressEnum.SERVER.value)

            else:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,linkdisable fail异常')
                CommonOperation.create_bug_problem(
                cls,
                key_word='3.1.4.1 复位方式,linkdisable fail异常',
                description_word=f'',
                expect_info=f'',
                result_info=f''
                )
            # sbr
            if paramete_list[4] == 0:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,sbr关闭')
                pass
            elif paramete_list[4] == 1:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,sbr开启')
                LinkChangeOpeation.link_secondary_bus_reset(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                            cmd_execute_address)
                DriverOperation.command_enable(CmdExecuteAdressEnum.SERVER.value)
                DriverOperation.remove(CmdExecuteAdressEnum.SERVER.value)
                DriverOperation.rescan(CmdExecuteAdressEnum.SERVER.value)
            else:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,sbr fail异常')
                CommonOperation.create_bug_problem(
                cls,
                key_word='3.1.4.1 复位方式,sbr fail异常',
                description_word=f'',
                expect_info=f'',
                result_info=f''
                )
            # retrain
            if paramete_list[5] == 0:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,retrain关闭')
                pass
            elif paramete_list[5] == 1:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,retrain开启')
                LinkChangeOpeation.link_retrain(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                               cmd_execute_address)
            else:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,retrain fail异常')
                CommonOperation.create_bug_problem(
                cls,
                key_word='3.1.4.1 复位方式,retrain fail异常',
                description_word=f'',
                expect_info=f'',
                result_info=f''
                )
            # 判断是否切成功
            CommonOperation.concat_test_steps('3.1.5 判断speed change after是否成功')
            if Pcie4KOperation.get_link_speed_sta(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                 cmd_execute_address) == Pcie4KOperation.get_link_speed_sta(PcieTreeOperation.get_pf_dbdf()[0],
                                                 cmd_execute_address) == speed_change_afterd:
                CommonOperation.concat_test_steps('3.1.5.1 speed change after成功')
            else:
                CommonOperation.concat_test_steps('3.1.5.1 speed change after失败')
                CommonOperation.create_bug_problem(
                cls,
                key_word='3.1.5.1 speed change after失败',
                description_word=f'',
                expect_info=f'',
                result_info=f''
                )
        
        # exec_command = f'pkill -ef iperf3 ; sleep 1'
        # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
        #     exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        # exec_command = f'ps -ef|grep iperf3'
        # rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
        #     exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        # count = rtn_outputs.count('iperf3')
        # if count > 2:
        #     log.info("run io 在后台", rtn_outputs)
        # else:
        #     log.info("无 io 在后台", rtn_outputs)
        # time.sleep(15)
    
    @classmethod
    def set_link_parameter_str_mode(cls, paramete_list: list, SPEED_VALUES: list, LANE_VALUES: list,cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        # paramete_list的bit2为1则先测速后切lane，否则先切lane后切speed
        # 预计算长度
        cls.paramete_list=paramete_list
        cls.SPEED_VALUES=SPEED_VALUES
        cls.LANE_VALUES=LANE_VALUES

        SPEED_LEN = len(cls.SPEED_VALUES)
        LANE_LEN = len(cls.LANE_VALUES)
        #先切speed
        if cls.paramete_list[2] == 1:
            # 切speed
            CommonOperation.concat_test_steps('正在进行外部循环遍历切speed')
            for i in range(SPEED_LEN):  # 外层循环5次
                # 速度切换
                speed_idx = i % SPEED_LEN
                next_speed_idx = (i + 1) % SPEED_LEN
                cls.speed_change_befored = cls.SPEED_VALUES[speed_idx]
                cls.speed_change_afterd = cls.SPEED_VALUES[next_speed_idx]
                # 设置速度参数
                cls.lane_change_befored=max(cls.LANE_VALUES)
                cls.lane_change_afterd=max(cls.LANE_VALUES)
                LinkParameterOperation.set_link_parameter(
                    cls.paramete_list,
                    cls.speed_change_befored,
                    cls.speed_change_afterd,
                    cls.lane_change_befored,
                    cls.lane_change_afterd,
                    CmdExecuteAdressEnum.SERVER.value
                )
                # print("循环体1")
                # print(cls.speed_change_befored,  cls.speed_change_afterd,cls.lane_change_befored,cls.lane_change_afterd)
                # 切lane 重置参数列表
                cls.paramete_list[2]=0
                CommonOperation.concat_test_steps('正在进行内部循环遍历切lane')
                for j in range(LANE_LEN):  # 内层循环LANE_LEN次 x1/x2/x4/x8
                    lane_idx = j % LANE_LEN
                    next_lane_idx = (j + 1) % LANE_LEN
                    cls.lane_change_befored = cls.LANE_VALUES[lane_idx]
                    cls.lane_change_afterd = cls.LANE_VALUES[next_lane_idx]
                    cls.speed_change_befored = max(SPEED_VALUES)
                    cls.speed_change_afterd = max(SPEED_VALUES)
                    LinkParameterOperation.set_link_parameter(
                        cls.paramete_list,
                        cls.speed_change_befored,  # 使用当前速度值
                        cls.speed_change_afterd,
                        cls.lane_change_befored,
                        cls.lane_change_afterd,
                        CmdExecuteAdressEnum.SERVER.value
                    )
                    # print("循环体2")
                    # print(cls.speed_change_befored, cls.speed_change_afterd,cls.lane_change_befored,cls.lane_change_afterd)
                cls.paramete_list[2]=1
        # 先切lane
        if cls.paramete_list[2] == 0:
            CommonOperation.concat_test_steps('正在进行外部循环遍历切lane')
            # 切lane
            for j in range(LANE_LEN):  # 内层循环LANE_LEN次 x1/x2/x4/x8
                lane_idx = j % LANE_LEN
                next_lane_idx = (j + 1) % LANE_LEN
                cls.lane_change_befored = cls.LANE_VALUES[lane_idx]
                cls.lane_change_afterd = cls.LANE_VALUES[next_lane_idx]
                cls.speed_change_befored = max(SPEED_VALUES)
                cls.speed_change_afterd = max(SPEED_VALUES)
                LinkParameterOperation.set_link_parameter(
                    cls.paramete_list,
                    cls.speed_change_befored,  # 使用当前速度值
                    cls.speed_change_afterd,
                    cls.lane_change_befored,
                    cls.lane_change_afterd,
                    CmdExecuteAdressEnum.SERVER.value
                )
                # print("循环体1")
                # print(cls.speed_change_befored,  cls.speed_change_afterd,cls.lane_change_befored,cls.lane_change_afterd)
                # 切speed重置参数
                cls.paramete_list[2] = 1
                CommonOperation.concat_test_steps('正在进行内部循环遍历切speed')
                for i in range(SPEED_LEN):  # 外层循环5次
                    # 速度切换
                    speed_idx = i % SPEED_LEN
                    next_speed_idx = (i + 1) % SPEED_LEN
                    cls.speed_change_befored = cls.SPEED_VALUES[speed_idx]
                    cls.speed_change_afterd = cls.SPEED_VALUES[next_speed_idx]
                    cls.lane_change_befored=max(cls.LANE_VALUES)
                    cls.lane_change_afterd=max(cls.LANE_VALUES)
                    # 设置速度参数
                    LinkParameterOperation.set_link_parameter(
                        cls.paramete_list,
                        cls.speed_change_befored,
                        cls.speed_change_afterd,
                        cls.lane_change_befored,
                        cls.lane_change_afterd,
                        CmdExecuteAdressEnum.SERVER.value
                    )
                #     print("循环体2")
                #     print(cls.speed_change_befored,  cls.speed_change_afterd,cls.lane_change_befored,cls.lane_change_afterd)
                cls.paramete_list[2]=0
    
    
    
    
    @classmethod
    def set_link_parameter_str(cls, paramete_list: list, SPEED_VALUES: list, LANE_VALUES: list,cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        if paramete_list[0] == 0 and paramete_list[0] == 0 and paramete_list[2] == 1:
            CommonOperation.concat_test_steps('测试条件,io关闭,eq关闭,外层循环切speed,内层循环切lane')
            LinkParameterOperation.set_link_parameter_str_mode(paramete_list, SPEED_VALUES, LANE_VALUES, CmdExecuteAdressEnum.SERVER.value)
        elif paramete_list[0] == 0 and paramete_list[0] == 0 and paramete_list[2] == 0:
            CommonOperation.concat_test_steps('测试条件,io关闭,eq关闭,外层循环切lane,内层循环切speed')
            LinkParameterOperation.set_link_parameter_str_mode(paramete_list, SPEED_VALUES, LANE_VALUES, CmdExecuteAdressEnum.SERVER.value)   
        elif paramete_list[0] == 0 and paramete_list[0] == 1 and paramete_list[2] == 1:
            CommonOperation.concat_test_steps('测试条件,io关闭,eq开启,外层循环切speed,内层循环切lane')    
            LinkParameterOperation.set_link_parameter_str_mode(paramete_list, SPEED_VALUES, LANE_VALUES, CmdExecuteAdressEnum.SERVER.value)           
        elif paramete_list[0] == 0 and paramete_list[0] == 1 and paramete_list[2] == 0:
            CommonOperation.concat_test_steps('测试条件,io关闭,eq开启,外层循环切lane,内层循环切speed')   
            LinkParameterOperation.set_link_parameter_str_mode(paramete_list, SPEED_VALUES, LANE_VALUES, CmdExecuteAdressEnum.SERVER.value)              
        elif paramete_list[0] == 1 and paramete_list[0] == 1 and paramete_list[2] == 1:
            CommonOperation.concat_test_steps('测试条件,io开启,eq开启,外层循环切speed,内层循环切lane')  
            LinkParameterOperation.set_link_parameter_str_mode(paramete_list, SPEED_VALUES, LANE_VALUES, CmdExecuteAdressEnum.SERVER.value)             
        elif paramete_list[0] == 1 and paramete_list[0] == 1 and paramete_list[2] == 0:
            CommonOperation.concat_test_steps('测试条件,io开启,eq开启,外层循环切lane,内层循环切speed')   
            LinkParameterOperation.set_link_parameter_str_mode(paramete_list, SPEED_VALUES, LANE_VALUES, CmdExecuteAdressEnum.SERVER.value)            
        elif paramete_list[0] == 1 and paramete_list[0] == 0 and paramete_list[2] == 1:
            CommonOperation.concat_test_steps('测试条件,io开启,eq关闭,外层循环切speed,内层循环切lane')    
            LinkParameterOperation.set_link_parameter_str_mode(paramete_list, SPEED_VALUES, LANE_VALUES, CmdExecuteAdressEnum.SERVER.value)           
        elif paramete_list[0] == 1 and paramete_list[0] == 0 and paramete_list[2] == 0:
            CommonOperation.concat_test_steps('测试条件,io开启,eq关闭,外层循环切lane,内层循环切speed')    
            LinkParameterOperation.set_link_parameter_str_mode(paramete_list, SPEED_VALUES, LANE_VALUES, CmdExecuteAdressEnum.SERVER.value)  
            
            
                
    @classmethod
    def set_link_parameter_changelaneandspeed(cls, paramete_list: list, speed_change_befored, speed_change_afterd,lane_change_befored,lane_change_afterd,cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        #time.sleep(30)
        if paramete_list[2] == 0 :
            CommonOperation.concat_test_steps('3.1.3 测试条件,切lane')
            # 测试前统一带宽 lane_change_befored
            LinkChangeOpeation.link_width_change(lane_change_befored, PcieTreeOperation.get_pf_dbdf()[0],cmd_execute_address)
            # 判断统一参数是否切成功
            CommonOperation.concat_test_steps('3.1.3.1 判断lane change befored是否成功')
            if Pcie4KOperation.get_link_lane_sta(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                  cmd_execute_address) == Pcie4KOperation.get_link_lane_sta(
                PcieTreeOperation.get_pf_dbdf()[0],
                cmd_execute_address) == lane_change_befored:
                CommonOperation.concat_test_steps('3.1.3.1 lane change befored success成功')
            else:
                CommonOperation.concat_test_steps('3.1.3.1 lane change befored fail失败')
            # 测试切lane
            CommonOperation.concat_test_steps('3.1.4 进行lane change afterd测试')
            LinkChangeOpeation.link_width_change(lane_change_afterd, PcieTreeOperation.get_pf_dbdf()[0],cmd_execute_address)
            CommonOperation.concat_test_steps('3.1.4.1 判断lane change afterd是否成功')
            if Pcie4KOperation.get_link_lane_sta(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                 cmd_execute_address) == Pcie4KOperation.get_link_lane_sta(
                PcieTreeOperation.get_pf_dbdf()[0],
                cmd_execute_address) == lane_change_afterd:
                CommonOperation.concat_test_steps('3.1.4.1 lane change afterd success成功')
            else:
                CommonOperation.concat_test_steps('3.1.4.1 lane change afterd fail失败')
            # 在切速lane加入切速
            if  (speed_change_befored != speed_change_afterd) and paramete_list[5] == 1:
                CommonOperation.concat_test_steps('3.1.4.2 测试条件,speed前后不等，需要在切lane后直接retrain切speed')
                # 测试前统一速率 speed_change_befored
                LinkChangeOpeation.link_speed_change(PcieTreeOperation.host_rp()[0].Dbdf_Number, speed_change_befored,
                                                        cmd_execute_address)
                LinkChangeOpeation.link_retrain(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                cmd_execute_address)
                # 判断统一参数是否切成功
                CommonOperation.concat_test_steps('3.1.4.3 判断speed change befored是否成功')
                if Pcie4KOperation.get_link_speed_sta(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                        cmd_execute_address) == Pcie4KOperation.get_link_speed_sta(PcieTreeOperation.get_pf_dbdf()[0],
                                                        cmd_execute_address) == speed_change_befored:
                    CommonOperation.concat_test_steps('3.1.4.3 speed change befored success成功')
                else:
                    CommonOperation.concat_test_steps('3.1.4.3 speed change befored success失败')

                # 切速
                CommonOperation.concat_test_steps('3.1.4.4 进行speed change after测试')
                # if paramete_list[5] == 1:
                LinkChangeOpeation.link_speed_change(PcieTreeOperation.host_rp()[0].Dbdf_Number, speed_change_afterd,
                                                            cmd_execute_address)
                    # LinkChangeOpeation.link_speed_change(PcieTreeOperation.get_pf_dbdf()[0], speed_change_afterd,
                    #                                      cmd_execute_address)
                # else:
                #     LinkChangeOpeation.link_speed_change(PcieTreeOperation.get_pf_dbdf()[0], speed_change_afterd,
                #                                          cmd_execute_address)
                # retrain
                if paramete_list[5] == 0:
                    CommonOperation.concat_test_steps('3.1.4.5 复位方式,retrain关闭')
                    pass
                elif paramete_list[5] == 1:
                    CommonOperation.concat_test_steps('3.1.4.5 复位方式,retrain开启')
                    LinkChangeOpeation.link_retrain(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                    cmd_execute_address)
                else:
                    CommonOperation.concat_test_steps('3.1.4.5 复位方式,retrain fail异常')
                # 判断是否切成功
                CommonOperation.concat_test_steps('3.1.5 判断speed change after是否成功')
                if Pcie4KOperation.get_link_speed_sta(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                        cmd_execute_address) == Pcie4KOperation.get_link_speed_sta(PcieTreeOperation.get_pf_dbdf()[0],
                                                        cmd_execute_address) == speed_change_afterd:
                    CommonOperation.concat_test_steps('3.1.5.1 speed change after成功')
                else:
                    CommonOperation.concat_test_steps('3.1.5.1 speed change after失败')
                          
        elif paramete_list[2] == 1:
            CommonOperation.concat_test_steps('3.1.3 测试条件,切speed')
            # 测试前统一速率 speed_change_befored
            LinkChangeOpeation.link_speed_change(PcieTreeOperation.host_rp()[0].Dbdf_Number, speed_change_befored,
                                                 cmd_execute_address)
            # LinkChangeOpeation.link_speed_change(PcieTreeOperation.get_pf_dbdf()[0], speed_change_befored,
            #                                      cmd_execute_address)
            LinkChangeOpeation.link_retrain(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                            cmd_execute_address)
            # 判断统一参数是否切成功
            CommonOperation.concat_test_steps('3.1.3.1 判断speed change befored是否成功')
            if Pcie4KOperation.get_link_speed_sta(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                 cmd_execute_address) == Pcie4KOperation.get_link_speed_sta(PcieTreeOperation.get_pf_dbdf()[0],
                                                 cmd_execute_address) == speed_change_befored:
                CommonOperation.concat_test_steps('3.1.3.1 speed change befored success成功')
            else:
                CommonOperation.concat_test_steps('3.1.3.1 speed change befored success失败')
            # eq
            if paramete_list[1] == 0:
                CommonOperation.concat_test_steps('3.1.3.2 测试条件,performanceEQ关闭')
                LinkChangeOpeation.performance_eq_disable(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                          cmd_execute_address)
            elif paramete_list[1] == 1:
                CommonOperation.concat_test_steps('3.1.3.2 测试条件,performanceEQ开启')
                LinkChangeOpeation.performance_eq_enable(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                               cmd_execute_address)
            else:
                CommonOperation.concat_test_steps('3.1.3.2 测试条件,performanceEQ fail异常')
           # 切速
            CommonOperation.concat_test_steps('3.1.4 进行speed change after测试')
            # if paramete_list[5] == 1:
            LinkChangeOpeation.link_speed_change(PcieTreeOperation.host_rp()[0].Dbdf_Number, speed_change_afterd,
                                                     cmd_execute_address)
                # LinkChangeOpeation.link_speed_change(PcieTreeOperation.get_pf_dbdf()[0], speed_change_afterd,
                #                                      cmd_execute_address)
            # else:
            #     LinkChangeOpeation.link_speed_change(PcieTreeOperation.get_pf_dbdf()[0], speed_change_afterd,
            #                                          cmd_execute_address)
            # linkdisable
            if paramete_list[3] == 0:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,linkdisble关闭')
                # LinkChangeOpeation.link_enable(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                #                                cmd_execute_address)
            elif paramete_list[3] == 1:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,linkdisble开启')
                LinkChangeOpeation.link_disable(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                cmd_execute_address)

            else:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,linkdisable fail异常')
            # sbr
            if paramete_list[4] == 0:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,sbr关闭')
                pass
            elif paramete_list[4] == 1:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,sbr开启')
                LinkChangeOpeation.link_secondary_bus_reset(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                            cmd_execute_address)
            else:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,sbr fail异常')
            # retrain
            if paramete_list[5] == 0:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,retrain关闭')
                pass
            elif paramete_list[5] == 1:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,retrain开启')
                LinkChangeOpeation.link_retrain(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                               cmd_execute_address)
            else:
                CommonOperation.concat_test_steps('3.1.4.1 复位方式,retrain fail异常')
            # 判断是否切成功
            CommonOperation.concat_test_steps('3.1.5 判断speed change after是否成功')
            if Pcie4KOperation.get_link_speed_sta(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                 cmd_execute_address) == Pcie4KOperation.get_link_speed_sta(PcieTreeOperation.get_pf_dbdf()[0],
                                                 cmd_execute_address) == speed_change_afterd:
                CommonOperation.concat_test_steps('3.1.5.1 speed change after成功')
            else:
                CommonOperation.concat_test_steps('3.1.5.1 speed change after失败')
            #判断切速后切lame
            if lane_change_befored != lane_change_afterd:
                CommonOperation.concat_test_steps('3.1.5.2 测试条件,lane前后不等，需要在切speed后直接切lane')
                # 测试前统一带宽 lane_change_befored
                LinkChangeOpeation.link_width_change(lane_change_befored, PcieTreeOperation.get_pf_dbdf()[0],cmd_execute_address)
                # 判断统一参数是否切成功
                CommonOperation.concat_test_steps('3.1.5.2  判断lane change befored是否成功')
                if Pcie4KOperation.get_link_lane_sta(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                    cmd_execute_address) == Pcie4KOperation.get_link_lane_sta(
                    PcieTreeOperation.get_pf_dbdf()[0],
                    cmd_execute_address) == lane_change_befored:
                    CommonOperation.concat_test_steps('3.1.5.3  lane change befored success成功')
                else:
                    CommonOperation.concat_test_steps('3.1.5.3 lane change befored fail失败')
                # 测试切lane
                CommonOperation.concat_test_steps('3.1.5.4 进行lane change afterd测试')
                LinkChangeOpeation.link_width_change(lane_change_afterd, PcieTreeOperation.get_pf_dbdf()[0],cmd_execute_address)
                CommonOperation.concat_test_steps('3.1.5.4 判断lane change afterd是否成功')
                if Pcie4KOperation.get_link_lane_sta(PcieTreeOperation.host_rp()[0].Dbdf_Number,
                                                    cmd_execute_address) == Pcie4KOperation.get_link_lane_sta(
                    PcieTreeOperation.get_pf_dbdf()[0],
                    cmd_execute_address) == lane_change_afterd:
                    CommonOperation.concat_test_steps('3.1.5.4 lane change afterd success成功')
                else:
                    CommonOperation.concat_test_steps('3.1.5.4 lane change afterd fail失败')
        
        DriverOperation.remove(CmdExecuteAdressEnum.SERVER.value)
        DriverOperation.rescan(CmdExecuteAdressEnum.SERVER.value)
        
        exec_command = f'pkill -ef iperf3 ; sleep 1'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        exec_command = f'ps -ef|grep iperf3'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        count = rtn_outputs.count('iperf3')
        if count > 2:
            log.info("run io 在后台", rtn_outputs)
        else:
            log.info("无 io 在后台", rtn_outputs)
        time.sleep(15)



class IpErrorInject(object):
    @classmethod
    def rp_bad_tlp_inject(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        # EP无置位 RP置位BadTLP+
        CommonOperation.concat_test_steps("开始对RP端注入Bad_tlp:EINJ0_0x0 (TLP_LCRC_ERR): (TX Path) New TLP's LCRC error injection")
        CommonOperation.concat_test_steps("EINJ0_COUNT注入次数为10次")
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '34.b', 'a', cmd_execute_address)
        time.sleep(0.1)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '1', cmd_execute_address)
        time.sleep(1)
        CommonOperation.concat_test_steps("开始对RP端注入Bad_tlp:EINJ1 0x0 (TLP_ERR): Insertion of New TLP's SEQ# error")
        CommonOperation.concat_test_steps("EINJ1_COUNT注入次数为10次")
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '38.l', '1000a', cmd_execute_address)
        time.sleep(0.1)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '2', cmd_execute_address)
        time.sleep(1)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '0', cmd_execute_address)
    @classmethod
    def rp_bad_dllp_injection(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        # EP无置位 RP置位BadDLLP+
        CommonOperation.concat_test_steps("开始对RP端注入Bad_dllp:EINJ0_0x2 (_16b_CRC_ERR_UPD_FC): (TX Path) 16bCRC error injection of Update-FC DLLP")
        CommonOperation.concat_test_steps("EINJ0_COUNT注入次数为10次")
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '34.w', '20a', cmd_execute_address)
        time.sleep(0.1)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '1', cmd_execute_address)
        time.sleep(1)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '0', cmd_execute_address)

    @classmethod
    def rp_reply_timer_rollover_injection(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        # EP无置位 RP置位Rollover +
        CommonOperation.concat_test_steps("开始对RP端注入reply_timer_rollover:EINJ2_0x2 (NAK_DLLP): Always Transmission for NAK DLLP")
        CommonOperation.concat_test_steps("EINJ2_COUNT注入次数为10次")
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '3C.w', '20a', cmd_execute_address)
        time.sleep(0.1)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '4', cmd_execute_address)
        time.sleep(1)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '0', cmd_execute_address)

    @classmethod
    def rp_bad_dllp_timeout_rollover_injection(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        # EP无置位 RP置位BadDLLP + Timeout +
        CommonOperation.concat_test_steps("开始对RP端注入Bad_dllp同时触发reply_timeout_rollover:EINJ0_0x1 (_16b_CRC_ERR_ACK_NAK_DLLP): (TX Path) 16bCRC error injection of ACK/NAK DLLP")
        CommonOperation.concat_test_steps("EINJ0_COUNT注入次数为10次")
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '34.w', '10a', cmd_execute_address)
        time.sleep(0.1)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '1', cmd_execute_address)
        time.sleep(1)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '0', cmd_execute_address)

    @classmethod
    def rp_data_link_protocol_injection(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        # EP无置位 RP置位DLP+
        CommonOperation.concat_test_steps("开始对RP端注入DLP_error:EINJ1,0x1 (ACK_NAK_DLLP_ERR): Insertion of ACK/NAK DLLP's SEQ# Error")
        CommonOperation.concat_test_steps("EINJ1_COUNT注入次数为1次")
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '38.l', '200101', cmd_execute_address)
        time.sleep(0.1)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '2', cmd_execute_address)
        time.sleep(5)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '0', cmd_execute_address)

    @classmethod
    def rp_ecrc_error_injection(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        ## EP无置位 RP无置位？？？？？？？？？？？
        CommonOperation.concat_test_steps("开始对RP端注入ECRC:EINJ0_0x3 (TLP_ECRC_ERR): (TX Path) New TLP's ECRC error injection")
        CommonOperation.concat_test_steps("EINJ0_COUNT注入次数为1次")
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '34.w', '301', cmd_execute_address)
        time.sleep(0.1)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '1', cmd_execute_address)
        time.sleep(5)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '0', cmd_execute_address)

    @classmethod
    def ep_reply_timer_timeout_rollover_injection(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        # EP Rollover+ Timeout+
        CommonOperation.concat_test_steps("开始对EP端注入reply_timer_timeout_rollover:EINJ0_0x4 (FCRC_ERR_TLP): (TX Path) TLP's FCRC error injection (128b/130b)")
        CommonOperation.concat_test_steps("EINJ0_COUNT注入次数为10次")
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '34.w', '40a', cmd_execute_address)
        time.sleep(0.1)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '1', cmd_execute_address)
        time.sleep(1)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '0', cmd_execute_address)

    @classmethod
    def ep_bad_tlp_injection(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        # EP BadTLP+
        CommonOperation.concat_test_steps("开始对EP端注入bad_tlp:EINJ0_0x8 (LCRC_ERR): (RX Path) LCRC error injection")
        CommonOperation.concat_test_steps("EINJ0_COUNT注入次数为10次")
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '34.w', '80a', cmd_execute_address)
        time.sleep(0.1)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '1', cmd_execute_address)
        time.sleep(1)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '0', cmd_execute_address)

    @classmethod
    def ep_ecrc_error_injection(cls, dbdf_number: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        # tianjian 未成功置位
        CommonOperation.concat_test_steps("开始对EP端注入ECRC:EINJ0_0xb (ECRC_ERR): (RX Path) ECRC error injection")
        CommonOperation.concat_test_steps("EINJ0_COUNT注入次数为1次")
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '34.w', 'b01', cmd_execute_address)
        time.sleep(0.1)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '1', cmd_execute_address)
        time.sleep(6)
        SetpciOperation.setpci_cmd(dbdf_number, VENDOR_SPEC_CAP, '30.b', '0', cmd_execute_address)

    @classmethod
    def set_error_parameter_str(cls, error_paramete_list: list,cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        # io 0 severity 0 type 0/1/2/3/4/5/6/7/8
        pf_bdf = PcieTreeOperation.host_pf()
        for _ in pf_bdf:
            # AerCheckOperation.enable_base_report(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
            # AerCheckOperation.enable_aer_report(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
            #
            # AerCheckOperation.set_aer_ce_mask(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
            # AerCheckOperation.set_aer_ue_mask(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
            # AerCheckOperation.close_aer_ce_mask(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
            # AerCheckOperation.close_aer_ue_mask(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)

            if error_paramete_list[1]==0:
                # AerCheckOperation.close_aer_ue_severity(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 0:
                    IpErrorInject.rp_bad_tlp_inject(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 1:
                    IpErrorInject.rp_bad_dllp_injection(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 2:
                    IpErrorInject.rp_reply_timer_rollover_injection(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 3:
                    IpErrorInject.rp_bad_dllp_timeout_rollover_injection(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 4:
                    IpErrorInject.rp_data_link_protocol_injection(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 5:
                    IpErrorInject.rp_ecrc_error_injection(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 6:
                    IpErrorInject.ep_reply_timer_timeout_rollover_injection(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 7:
                    IpErrorInject.ep_bad_tlp_injection(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 8:
                    IpErrorInject.ep_ecrc_error_injection(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
            if error_paramete_list[1]==1:
                # AerCheckOperation.set_aer_ue_severity(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 0:
                    IpErrorInject.rp_bad_tlp_inject(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 1:
                    IpErrorInject.rp_bad_dllp_injection(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 2:
                    IpErrorInject.rp_reply_timer_rollover_injection(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 3:
                    IpErrorInject.rp_bad_dllp_timeout_rollover_injection(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 4:
                    IpErrorInject.rp_data_link_protocol_injection(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 5:
                    IpErrorInject.rp_ecrc_error_injection(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 6:
                    IpErrorInject.ep_reply_timer_timeout_rollover_injection(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 7:
                    IpErrorInject.ep_bad_tlp_injection(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)
                if error_paramete_list[2] == 8:
                    IpErrorInject.ep_ecrc_error_injection(_.Dbdf_Number, CmdExecuteAdressEnum.SERVER.value)

class GetPFIpName(object):
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
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        nicg = CommonOperation.get_nic_generation()
        # step 1 获取相连的连段子接口名称
        test_device_info_dict = dict()
        # todo 可以直接从配置文件准确获取，无需再去环境遍历
        # client_device_name = cls.get_physical_device_name(cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
        # server_device_name = cls.get_physical_device_name(cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        server_device_name, client_device_name = CommonOperation.get_nic_relationships()
        server_drv_name, client_drv_name = CommonOperation.get_nic_driver_name()
        # log.info("server_device_name:{}".format(server_device_name))
        # log.info("client_device_name:{}".format(client_device_name))

        # 重新組合relation
        s_c_relation_dict = {}
        for server_dev, client_dev in zip(server_device_name, client_device_name):
            s_c_relation_dict[server_dev] = client_dev

        # pf_device_name_client, pf_device_name_server = '', ''
        # ping_pass_info_list = []

        # _, host_os_client = cls.get_nic_os()
        # return_flag = False
        # 如果两端都有处于连接状态的子接口，进入是否同链路判断
        pf_device_name_client, pf_device_name_server = '', ''
        if client_device_name and server_device_name:
            # 遍历link status为yes的server client的子接口名称，使用ping命令验证是否可以ping通，如通则认为是同一链路
            result_index = 0
            ipv4_server = []
            ipv4_client = []
            for index, device_name_s in enumerate(server_device_name):
                condition_server = (device_name_s, CmdExecuteAdressEnum.SERVER.value)
                device_name_c = client_device_name[index]
                condition_client = (device_name_c, CmdExecuteAdressEnum.CLIENT.value)
                ipv4_server.append(IfConfig.get_device_ipv4_addr(*condition_server,test_port=test_port))
                # ipv4_s = IfConfig.get_device_ipv4_addr(*condition_server,
                #                                        test_port=test_port)
                ipv4_client.append(IfConfig.get_device_ipv4_addr(*condition_client,
                                                       test_port=test_port))
                # ipv4_c = IfConfig.get_device_ipv4_addr(*condition_client,
                #                                        test_port=test_port) 
            log.info(f"ipv4_s: {ipv4_server}")
            log.info(f"ipv4_c: {ipv4_client}")
            log.info(f"condition_server: {condition_server}")
            log.info(f"condition_client: {condition_client}")
            return ipv4_server,ipv4_client,condition_server





if __name__ == "__main__":
    # AerCheckOperation.close_base_report('0000:4c:00.0', CmdExecuteAdressEnum.SERVER.value)
    # AerCheckOperation.close_aer_report('0000:4c:00.0', CmdExecuteAdressEnum.SERVER.value)
    # AerCheckOperation.get_devdet_status('0000:4c:00.0', CmdExecuteAdressEnum.SERVER.value)
    # AerCheckOperation.get_aer_ue_status('0000:4c:00.0', CmdExecuteAdressEnum.SERVER.value)
    # AerCheckOperation.get_aer_ce_status('0000:4c:00.0', CmdExecuteAdressEnum.SERVER.value)
    # AerCheckOperation.close_aer_ue_mask('0000:4c:00.0', CmdExecuteAdressEnum.SERVER.value)
    # AerCheckOperation.close_aer_ce_mask('0000:4c:00.0', CmdExecuteAdressEnum.SERVER.value)
    # AerCheckOperation.close_aer_ue_severity('0000:4c:00.0', CmdExecuteAdressEnum.SERVER.value)
    # AerCheckOperation.clear_devdet_status('0000:4c:00.0', CmdExecuteAdressEnum.SERVER.value)
    # AerCheckOperation.clear_aer_ce_status('0000:4c:00.0', CmdExecuteAdressEnum.SERVER.value)
    # AerCheckOperation.clear_aer_ue_status('0000:4c:00.0', CmdExecuteAdressEnum.SERVER.value)

    # AllPcieCheckOperation.all_aer_check('0000:4a:04.0', CmdExecuteAdressEnum.SERVER.value)
    # AllPcieCheckOperation.all_aer_check('0000:4c:00.0', CmdExecuteAdressEnum.SERVER.value)
    # LinkCheckOperation.judge_width('0000:4c:00.0', CmdExecuteAdressEnum.SERVER.value)
    # LinkCheckOperation.judge_speed('0000:4c:00.0', CmdExecuteAdressEnum.SERVER.value)
    # LinkChangeOpeation.performance_eq_change('0000:4a:04.0', False, CmdExecuteAdressEnum.SERVER.value)
    # LinkChangeOpeation.link_retrain('0000:4a:04.0',CmdExecuteAdressEnum.SERVER.value)
    # LinkChangeOpeation.link_secondary_bus_reset('0000:4a:04.0', CmdExecuteAdressEnum.SERVER.value)
    # LinkChangeOpeation.link_disable('0000:4a:04.0', CmdExecuteAdressEnum.SERVER.value)
    # LinkChangeOpeation.link_enable('0000:4a:04.0', CmdExecuteAdressEnum.SERVER.value)
    # Pcie4KOperation.get_link_speed_sta('0000:4a:04.0', CmdExecuteAdressEnum.SERVER.value)
    # Pcie4KOperation.get_link_lane_sta('0000:4a:04.0', CmdExecuteAdressEnum.SERVER.value)
    # IOperation.iperf_tunnel_queues('192.168.1.198', '192.168.1.38')
    # DmesgCheckOperation.dmesg_check_clear()
    #DmesgCheckOperation.dmesg_check_judge()
    #error_paramete_list=[0,1,3]
    #IpErrorInject.rp_bad_tlp_inject('0000:4c:00.0', CmdExecuteAdressEnum.SERVER.value)
    # AllPcieCheckOperation.all_aer_check_rppf()
    LinkCheckOperation.jude_lane_width_rppf()