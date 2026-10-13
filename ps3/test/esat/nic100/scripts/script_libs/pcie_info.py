#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      weifeng.meng
date:        2025/3/12
description: 获取测试网卡设备所在的host pcie tree，rp pf vf设备信息
"""
import re, json
from scripts.script_libs import pcie_constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum, BondModeEnum, MacVlanModeEnum, OpcodeEnum


class PcieDevice():
    def __init__(self, dbdf_number):
        self.Dbdf_Number = dbdf_number
        self.Express_Type = None
        self.Vendor_Id = None
        self.Device_Id = None
        self.Cur_Speed = None
        self.Cur_Width = None
        self.Capable_Speed = None
        self.Capable_Width = None
        self.Target_Speed = None
        self.Path = None


class PcieTreeOperation(object):
    """
    author:      weifeng.meng
    date:        2025/3/13
    description: 获取测试网卡设备所在的host pcie tree，rp pf vf设备信息
    """

    @classmethod
    def get_pcicrawler_tv(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        exec_command = f'{pcie_constants.PCICRAWLER} -tv'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        return rtn_outputs

    @classmethod
    def get_pcie_tree(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        exec_command = f'{pcie_constants.PCICRAWLER} -j -e'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        pciedevice_list: list[PcieDevice] = []
        res = json.loads(rtn_outputs)
        for dbdf_number, details in res.items():
            # print(f"dbdf_number的值为：{dbdf_number}")
            pcie_device = PcieDevice(dbdf_number)
            pcie_device.Express_Type = details.get("express_type")
            pcie_device.Vendor_Id = details.get("vendor_id")
            pcie_device.Device_Id = details.get("device_id")
            pcie_device.Cur_Speed = details.get("cur_speed")
            pcie_device.Cur_Width = details.get("cur_width")
            pcie_device.Capable_Speed = details.get("capable_speed")
            pcie_device.Capable_Width = details.get("capable_width")
            pcie_device.Target_Speed = details.get("target_speed")
            pcie_device.Path = details.get("path")
            pciedevice_list.append(pcie_device)
        return pciedevice_list

    @classmethod
    def host_rp(cls):
        pf_list = []
        rp_list = []
        pcietree_info = cls.get_pcie_tree(CmdExecuteAdressEnum.SERVER.value)
        for _ in pcietree_info:
            for tuple_item in pcie_constants.PF_ID:
                if tuple_item[0] in vars(_).values() and tuple_item[1] in vars(_).values() and tuple_item[2] in vars(
                        _).values():
                    pf_list.append(_)
        for pf_ in pf_list:
            for _ in pcietree_info:
                if pf_.Path[0] in vars(_).values() and "root_port" in vars(_).values():
                    rp_list.append(_)
        seen = set()
        unique_object = []
        for p in rp_list:
            if p.Dbdf_Number not in seen:
                seen.add(p.Dbdf_Number)
                unique_object.append(p)
        return unique_object

    @classmethod
    def host_pf(cls):
        pf_list = []
        pcietree_info = cls.get_pcie_tree(CmdExecuteAdressEnum.SERVER.value)
        for _ in pcietree_info:
            for tuple_item in pcie_constants.PF_ID:
                if tuple_item[0] in vars(_).values() and tuple_item[1] in vars(_).values() and tuple_item[2] in vars(
                        _).values():
                    pf_list.append(_)
        for _ in pf_list:
            if _.Target_Speed != 'null':
                pf_list.remove(_)
                pf_list.insert(0, _)
        return pf_list

    @classmethod
    def host_vf(cls):
        vf_list = []
        pcietree_info = cls.get_pcie_tree(CmdExecuteAdressEnum.SERVER.value)
        for _ in pcietree_info:
            for tuple_item in pcie_constants.VF_ID:
                if tuple_item[0] in vars(_).values() and tuple_item[1] in vars(_).values() and tuple_item[2] in vars(
                        _).values():
                    vf_list.append(_)
        print(type(vf_list))
        return vf_list

    @classmethod
    def get_pf_dbdf(cls):
        host_pf_dbdf = []
        host_pf_ = PcieTreeOperation.host_pf()
        for _ in host_pf_:
            host_pf_dbdf.append(_.Dbdf_Number)
        host_pf_dbdf.sort()
        return host_pf_dbdf

    @classmethod
    def get_vf_dbdf(cls):
        host_vf_dbdf = []
        host_vf_ = PcieTreeOperation.host_vf()
        for _ in host_vf_:
            host_vf_dbdf.append(_.Dbdf_Number)
        host_vf_dbdf.sort()
        return host_vf_dbdf



if __name__ == "__main__":
    # PcieTreeOperation.get_rpep_bdf(CmdExecuteAdressEnum.SERVER.value)
    # PcieTreeOperation.get_pcie_tree(CmdExecuteAdressEnum.SERVER.value)
    PcieTreeOperation.host_rp()
    print(var:=PcieTreeOperation.host_rp()[0].Dbdf_Number)
    # print(type(PcieTreeOperation.host_pf()[0]))
    # PcieTreeOperation.host_vf()
    # print(PcieTreeOperation.host_pf()[0].Dbdf_Number)
    # print(PcieTreeOperation.get_pf_dbdf()[0])
    # c = PcieTreeOperation.get_pf_dbdf()
    # for i in range(10):
    #     for _ in c:
    #         print(PcieTreeOperation.get_pf_dbdf()[0])
    #     print()
    # PcieTreeOperation.get_pcicrawler_tv(CmdExecuteAdressEnum.SERVER.value)


