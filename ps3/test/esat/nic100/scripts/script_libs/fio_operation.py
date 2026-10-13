
import add_syspath

from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum


class FioOperation(object):
    
    @classmethod
    def fio(cls, dev:str, rw:str, engine:str = "libaio", time=60, 
            cmdaddress: CmdExecuteAdressEnum = CmdExecuteAdressEnum.CLI_DEFAULT.value,  *args, **kwargs) -> str:
        """
        author: lei.he
        date:   2025.04.09
        description: fio运行命令
        :param dev: 存储设备名称
        :param rw:
        :return:
        """
        if time != 0:
            command = f"fio --name=test --filename={dev} --ioengine={engine} --runtime={time} --rw={rw} "
        else:
            command = f"fio --name=test --filename={dev} --ioengine={engine}  --rw={rw} "
        for arg in args:
            command += f"--{arg} "
        for key, val in kwargs.items():
            if key == "ioengine" and val == "libaio":
                command += f"--ioengine=libaio --direct=1"
            else:
                command += f"--{key}={val} "
        return CommandOperation.execute_command_based_paramiko_with_rtncode(command, cmdaddress)

        
        
    