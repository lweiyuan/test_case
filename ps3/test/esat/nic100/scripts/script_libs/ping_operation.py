import re

import add_syspath
from scripts.script_libs import constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum, PacketType
from scripts.script_libs.common_operation import CommonOperation


class PingOperation(object):

    def __init__(self, ip_version: PacketType = PacketType.PACKET_IPV4.value, interface: str = '',
                 run_time: int = 60):
        """
        入参
        :param send_packet_num:  发送包个数, 默认10个
        :param udp_flag:         是否使用UDP发送, 默认关闭
        :param ip_version:       ipversion, 默认ipv4
        :param run_time:         iperf发包时长，默认60s
        """

        self.send_packet_num = send_packet_num
        self.v6_flag = v6_flag
        self.ip_version = ip_version
        self.run_time = run_time

    def ping(self) -> None:
        """
        author:             xianda.liu
        date:               2022-09-03
        description:        iperf client命令执行
        :param run_time:    打流时间
        """
        exec_command = 'ping'
        para_v6 = '' if not self.v6_flag else ' -6'


if __name__ == '__main__':
    pass
