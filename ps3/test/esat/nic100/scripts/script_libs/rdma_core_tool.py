import os.path

import add_syspath
from typing import Union
import functools
import re, time
from scripts.script_libs import log
from scripts.script_libs import constants
from scripts.script_libs.script_base import ScriptBase
from scripts.script_libs.file_operation import FileOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum, CliStatusEnum, ExitCodeEnum, RegionEnum
from scripts.script_libs.constants import *
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.script_base import SxeThread
from collections import defaultdict


class rdma_link():
    
    def __init__(self):
        self.link = None
        self.state = None
        self.physical_state = None
        self.netdev = None

class RdmacoreTool(object):
    
    @classmethod
    def ib_interactive_commcheck(cls, server_ip, oper:str, device_server:str, device_client:str, 
                              sever_cmd_address: str = CmdExecuteAdressEnum.SERVER.value,
                              client_cmd_address: str = CmdExecuteAdressEnum.CLIENT.value,
                              *args, **kwargs) -> tuple:
        
        def server_rping(*args, **kwargs):
            command = f"{oper} -d {device_server} "
            for arg in args:
                command += f"--{arg} "
            for key, val in kwargs.items():
                command += f"--{key}={val} "            
            return cls.execute_command_based_paramiko_with_rtncode(command, sever_cmd_address)
                
        def client_rping(*args, **kwargs):
            command = f"{oper} -d {device_client} {server_ip}"
            for arg in args:
                command += f"--{arg} "
            for key, val in kwargs.items():
                command += f"--{key}={val} "            
            return cls.execute_command_based_paramiko_with_rtncode(command, client_cmd_address)
                
        S = SxeThread(server_rping)
        C = SxeThread(client_rping)
        S.start() ; time.sleep(3) ; C.start()
        C.join() ; S.join()
        # cmd_code, cmd_output, cmd_stderr = C.join() ; cmd_code, cmd_output, cmd_stderr = S.join()
        return S.ret, C.ret

    ##################上面是perftest工具集，下面是rdma-core工具集##################
    
    @classmethod
    def rping_interactive_commcheck(cls, server_ip, 
                              sever_cmd_address: str = CmdExecuteAdressEnum.SERVER.value,
                              client_cmd_address: str = CmdExecuteAdressEnum.CLIENT.value,
                              *args, **kwargs) -> tuple:
        def server_rping(*args, **kwargs):
            command = f"rping -s -a {server_ip} -C 10 -v "
            for arg in args:
                command += f"--{arg} "
            for key, val in kwargs.items():
                command += f"--{key}={val} "            
            return cls.execute_command_based_paramiko_with_rtncode(command, sever_cmd_address)
                
        def client_rping(*args, **kwargs):
            command = f"rping -c -a {server_ip} -C 10 -v "
            for arg in args:
                command += f"--{arg} "
            for key, val in kwargs.items():
                command += f"--{key}={val} "            
            return cls.execute_command_based_paramiko_with_rtncode(command, client_cmd_address)
                
        S = SxeThread(server_rping)
        C = SxeThread(client_rping)
        S.start() ; time.sleep(3) ; C.start()
        C.join() ; S.join()
        # cmd_code, cmd_output, cmd_stderr = C.join() ; cmd_code, cmd_output, cmd_stderr = S.join()
        return S.ret, C.ret

    @classmethod
    def rdma_link(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        command = "rdma link"
        _, cmd_output, _ = cls.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        all = []
        rdmas = cmd_output.split('\n')
        for rdma in rdmas:
            new = rdma_link() ; data = rdma.split()
            data[1] = new.link
            data[3] = new.state
            data[5] = new.physical_state
            data[7] = new.netdev
            all.append(new)
        return all