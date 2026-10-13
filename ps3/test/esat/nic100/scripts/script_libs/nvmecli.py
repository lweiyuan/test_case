import json
import random, re
from typing import List
from scripts.script_libs import log

import add_syspath
from scripts.script_libs import constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum, RxfhIndirEnum, SpeedEnum, NicNameEnum, \
    EthtoolParamShortenEnum


class Nvme():
    
    def __init__(self):
        self.Node = None
        self.Generic = None
        self.SN = None
        self.Model = None
        self.Namespace = None
        self.Usage = None
        self.Format = None
        self.FW_Rev = None
        pass
    
class Discovery_Log_Entry():
    
    def __init__(self, log_entry):
        
        self.index = None
        self.trtype = None
        self.adrfam = None
        self.subtype = None
        self.treq = None
        self.portid = None
        self.trsvcid = None
        self.subnqn = None
        self.traddr = None
        self.eflags = None
        self.rdma_prtype = None
        self.rdma_qptype = None
        self.rdma_cms = None
        self.rdma_pkey = None
        
        patterns = {
            'trtype': r'trtype:\s*(\S+)',
            'adrfam': r'adrfam:\s*(\S+)',
            'subtype': r'subtype:\s*(.*)',
            'treq': r'treq:\s*(.*)',
            'portid': r'portid:\s*(\d+)',
            'trsvcid': r'trsvcid:\s*(\d+)',
            'subnqn': r'subnqn:\s*(\S+)',
            'traddr': r'traddr:\s*([\d\.]+)',
            'eflags': r'eflags:\s*(.*)',
            'rdma_prtype': r'rdma_prtype:\s*(.*)',
            'rdma_qptype': r'rdma_qptype:\s*(\S+)',
            'rdma_cms': r'rdma_cms:\s*(\S+)',
            'rdma_pkey': r'rdma_pkey:\s*(\S+)'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, log_entry)
            if match:
                setattr(self, key, match.group(1).strip()) 

class NvmeOperation(object):

    @classmethod
    def nvme_list(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> List[Nvme]:
        nvme_nodes = []
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode("nvme list", cmd_execute_address)
        pattern = r"(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)\s+([\d\.]+)\s+GB\s+/([\d\.]+)\s+GB\s+(\d+)\s+B\s+\+\s+(\d+)\s+B\s+(\S+)"
        if rtn_code == 0:
            for line in rtn_outputs.split("\n")[2:]:
                nvme = Nvme()
                nvme.Node = line[0:20]
                nvme.Generic = line[22:42]
                nvme_nodes.append(nvme)
        return nvme_nodes
    
    @classmethod
    def nvme_list_ctrl(cls, device:str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, ) -> bool:
        command =  f"nvme list-ctrl {device}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        return rtn_code, rtn_outputs, rtn_err
    
    @classmethod
    def nvme_list_ns(cls, device:str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        command =  f"nvme list-ns {device}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        return rtn_code, rtn_outputs, rtn_err
    
    @classmethod
    def nvme_list_secondary(cls, device:str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        command =  f"nvme list-secondary {device}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        return rtn_code, rtn_outputs, rtn_err
    
    @classmethod
    def nvme_list_subsys(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        command =  "nvme list-subsys"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        return rtn_code, rtn_outputs, rtn_err
    
    @classmethod
    def nvme_reset(cls, device:str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        command =  f"nvme reset {device}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        return rtn_code, rtn_outputs, rtn_err

    @classmethod
    def nvme_fw_log(cls, device:str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        command =  f"nvme fw-log {device}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        return rtn_code, rtn_outputs, rtn_err
    
    @classmethod
    def nvme_smart_log(cls, device:str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        command =  f"nvme smart-log {device}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        return rtn_code, rtn_outputs, rtn_err
    
    @classmethod
    def nvme_ana_log(cls, device:str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        command =  f"nvme ana-log {device}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        return rtn_code, rtn_outputs, rtn_err
    
    @classmethod
    def nvme_error_log(cls, device:str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        command =  f"nvme error-log {device}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        return rtn_code, rtn_outputs, rtn_err

    @classmethod
    def nvme_self_test_log(cls, device:str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        command =  f"nvme self-test-log {device}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        return rtn_code, rtn_outputs, rtn_err
    
    @classmethod
    def nvme_get_property(cls, device:str, offset:str, val:str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        command =  f"nvme get-property {device} -o {offset} -v {val}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        return rtn_code, rtn_outputs, rtn_err
    
    @classmethod
    def nvme_set_property(cls, device:str, offset:str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        command =  f"nvme set-property {device} -o {offset}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        return rtn_code, rtn_outputs, rtn_err

    @classmethod
    def nvme_format(cls, device:str, timeout:str="", lbaf:str="", ses:str="", 
                    pi:str="", pil:str="", ms:str="", reset:bool=False, force:bool=False, block_size:str="", 
                    cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        command = f"nvme format {device} "
        command += f"-n {timeout} " if timeout else ""
        command += f"-t {lbaf} " if lbaf else ""
        command += f"-s {ses} " if ses else ""
        command += f"-i {pi} " if pi else ""
        command += f"-p {pil} " if pil else ""
        command += f"-m {ms} " if ms else ""
        command += f"--reset " if reset else ""
        command += f"--force " if force else ""
        command += f"-b {block_size} " if block_size else ""
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        return rtn_code, rtn_outputs, rtn_err


    @classmethod
    def get_new_nvme(cls, old_nvme_node: List[Nvme], cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> List[Nvme]:
        now_nvme_nodes = cls.nvme_list(cmd_execute_address)
        return [x for x in now_nvme_nodes if x not in old_nvme_node]
        

    @classmethod
    def discover_nvmeof_rdma_subsystem(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, subsystem:str = None, 
                                                 addr_traddr:str = None, addr_trsvcid:int = 4420, force:bool=False) :
        """
        author:      lei.he
        date:        2025-03-27
        description: nvme discover
        """       
        command = f"nvme discover -t rdma -a {addr_traddr} -s {addr_trsvcid} -q {subsystem}"
        log_entry_title = r'=====Discovery Log Entry \d+======'
        if force:
            command += " --force"
        cmd_code, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        if cmd_stderr:
            return cmd_code, cmd_output, cmd_stderr
        if cmd_output:
            entries = re.split(log_entry_title, cmd_output)
            summary = entries[0]
            log_entries = [ entry.strip() for entry in entries[1:] if entry.strip() ]
            log_entries_list = []
            for entry in log_entries:
                New = Discovery_Log_Entry(entry)
                New.index = log_entries.index(entry)
                log_entries_list.append(New)
            # return log_entries_list
        return cmd_code, log_entries_list, cmd_stderr

    @classmethod
    def connect_nvmeof_rdma_subsystem(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, subsystem:str = None, 
                                                 addr_traddr:str = None, addr_trsvcid:int = 4420,
                                                 nr_io_queues:int = 0,
                                                 nr_write_queues:int = 0,
                                                 nr_poll_queues:int = 0,
                                                 queue_size:int = 128,
                                                 tos:int = 0,
                                                 keep_alive_tmo:int = 0,
                                                 ctrl_loss_tmo:int = 0,
                                                 duplicate_connect:bool = False,
                                                 disable_sqflow:bool = False) -> str:
        """
        author:      lei.he
        date:        2025-03-27
        description: 连接rdma-cm
        """       
        command =  f"nvme connect -t rdma -a {addr_traddr} -s {addr_trsvcid} -n {subsystem} "
        if nr_io_queues != 0:
            command += f"--nr-io-queues={nr_io_queues} "
        if nr_write_queues != 0:
            command += f"--nr-write-queues={nr_write_queues} "
        if nr_poll_queues != 0:
            command += f"--nr-poll-queues={nr_poll_queues} "
        if queue_size != 128:
            command += f"--queue-size={queue_size} "
        if tos != 0:
            command += f"--tos={tos} "
        if keep_alive_tmo != 0:
            command += f"--keep-alive-tmo={keep_alive_tmo} "
        if ctrl_loss_tmo != 0:
            command += f"--ctrl-loss-tmo={ctrl_loss_tmo} "
        if duplicate_connect:
            command += f"--duplicate-connect "
        if disable_sqflow:
            command += f"--disable-sqflow "
        return CommandOperation.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
    
    @classmethod
    def disconnect_nvmeof_rdma_subsystem(cls, host: str, subsystem:str = None,
                                                 addr_traddr:str = None, addr_trsvcid:int = 4420):
        """
        author:      lei.he
        date:        2025-03-27
        description: 断开nvmeof 连接
        """       
        command = f"nvme disconnect -t rdma -a {addr_traddr} -s {addr_trsvcid} -q {subsystem}"
        return CommandOperation.execute_command_based_paramiko_with_rtncode(command, host)