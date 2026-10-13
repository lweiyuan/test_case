import os
import re
import datetime

import add_syspath
from scripts.script_libs import constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum, PacketType
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.script_base import ScriptBase


class IperfOperation(object):

    def __init__(self, udp_flag: bool = False, run_time: int = 60, caller_class=ScriptBase,
                 packet_length: int = 64, bandwidth: str = '10M', parallel_num: int = 8,
                 ip_version=constants.IPV4, rpc_server_ip='', rpc_client_ip='', dualtest_flag: bool = False,
                 log_file: str = None, iperf_port: int = None, max_bandwidth: str = None, interval: str = '5',
                 nbytes: int = None, log_file_path: str = None, reverse: bool = False,
                 tos: int = None):
        """
        入参
        :param caller_class:     调用基类, 默认一级基类
        :param packet_length:  发送包个数, 默认10个
        :param udp_flag:         是否使用UDP发送, 默认关闭
        :param ip_version:       ipversion, 默认ipv4
        :param run_time:         iperf发包时长，默认60s
        :param dualtest_flag:    是否双向打流
        :param log_file:    是否输出日志
        :param log_file_path:    指定输出日志文件名
        :param iperf_port:  端口号
        :param max_bandwidth:  是否支持最大带宽
        :param interval:  打印日志间隔
        :param nbytes:  使用发送数据包总量代替-t,传入参数为100000000
        :param reverse:  是否反向打流 server->client
        :param tos:  IP TOS 值, 设置后 client 指令追加 --tos <tos>, 默认 None 不追加
        iperf3 -p 30854 -l 1500 -n $((100000000*1500)) -b 800M -i 2 -P 1 -B 192.169.5.21 -c 192.169.5.11 -u -4 --bidir
        """

        self.udp_flag = udp_flag
        self.run_time = run_time
        self.test_device_info_dict = caller_class.test_device_info_dict
        self.caller_class = caller_class
        self.packet_length = packet_length
        self.bandwidth = bandwidth
        self.parallel_num = parallel_num
        self.server_os, self.client_os = CommonOperation.get_nic_os()
        self.ip_version = "4" if ip_version == constants.IPV4 else "6"
        self.rpc_server_ip = rpc_server_ip
        self.rpc_client_ip = rpc_client_ip
        self.dualtest_flag = dualtest_flag
        self.log_file = log_file
        self.log_file_path = log_file_path
        self.iperf_port = iperf_port
        self.max_bandwidth = max_bandwidth
        self.interval = interval
        self.nbytes = nbytes
        self.reverse = reverse
        self.tos = tos

    @staticmethod
    def check_iperf_version(cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-09-03
        description:        iperf版本校验
        :param cmd_execute_address: 命令执行位置
        :return:            True/False
        """
        check_flag = False
        exec_command = constants.STR_SPACE.join([constants.IPERF, '-v'])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            re_pattern = r'iperf (\S+) '
            version = re.findall(re_pattern, rtn_outputs)[0]
            log.info("iperf3当前版本：{}，测试要求版本大于等于：{}".format(version, constants.IPERF_VERSION))
            if version >= constants.IPERF_VERSION:
                check_flag = True

        return check_flag

    def client_iperf(self, bind: str = "", client: str = "") -> tuple or None:
        """
        author:             xianda.liu
        date:               2022-09-03
        description:        iperf client命令执行
        :param: bind        server端设备IP
        :param: client      client端设备IP  iperf -c 192.160.6.10 -B 192.160.6.20 -t 300 -b 1G -l 64 -d -i 2
        """
        para_b, para_c = None, None
        if self.iperf_port is None:
            self.iperf_port = constants.IPERF_PORT

        if 'windows' not in self.client_os:
            iperf_head = constants.IPERF
        else:
            iperf_head = constants.IPERF_WIN
        if self.max_bandwidth:
            self.bandwidth = '1000M'
        if self.nbytes:
            exec_command = iperf_head + ' -p {} -l {} -n $(({}*{})) -b {} -i {} -P {}'.format(
                str(self.iperf_port), str(self.packet_length), str(self.nbytes), str(self.packet_length),
                self.bandwidth, self.interval, str(self.parallel_num))
        else:
            exec_command = iperf_head + ' -p {} -t {} -l {} -b {} -i {} -P {}'.format(
                str(self.iperf_port), str(self.run_time), str(self.packet_length),
                self.bandwidth, self.interval, str(self.parallel_num))
        print('iperf==', self.test_device_info_dict)
        # -B, --bind      <host>
        if not bind:
            if self.test_device_info_dict.get('client_device_ip'):
                para_b = ' -B {}'.format(self.test_device_info_dict['client_device_ip'])
        else:
            para_b = ' -B {}'.format(bind)
        # -c, --client    <host>
        if not client:
            if self.test_device_info_dict.get('server_device_ip'):
                para_c = ' -c {}'.format(self.test_device_info_dict['server_device_ip'])
        else:
            para_c = ' -c {}'.format(client)

        if not para_b or not para_c:
            log.error(f'iperf参数有误，client_ip:{para_b}, server_ip:{para_c}, 不符合测试条件')
            return
        else:
            exec_command += para_b
            exec_command += para_c
            para_udp = '' if not self.udp_flag else ' -u'
            exec_command += ' {}  -{}'.format(para_udp, str(self.ip_version))
            if self.tos is not None:
                exec_command += ' --tos {}'.format(self.tos)
            if self.dualtest_flag:
                exec_command += ' --bidir'
            if not self.dualtest_flag and self.reverse:
                exec_command += ' --reverse'
            if self.log_file:
                if self.log_file_path is None:
                    mkdir_command = 'mkdir -p /home/iperf_log'
                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=mkdir_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                    log_file_path = f"/home/iperf_log/iperf_log_{self.iperf_port}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}.log"
                    # exec_command += f"| tee -a {log_file_path}"
                    exec_command += f" --logfile {log_file_path}"
                else:
                    exec_command += f" --logfile {self.log_file_path}"
            if 'windows' not in self.client_os:
                print_log = False if self.log_file else True
                rtn_code, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                        print_outputs=print_log)
            else:
                from scripts.script_libs.windows_command_operation import WindowsCommandOperation
                if self.rpc_client_ip == self.test_device_info_dict['client_device_ip']:
                    win_vm_ip = None
                else:
                    win_vm_ip = self.rpc_client_ip
                rtn_code, rtn_outputs, rtn_err = \
                    WindowsCommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                        win_vm_ip=win_vm_ip)

            if rtn_code == RtnStatusEnum.SUCCESS.value:
                self.caller_class.iperf_result_list.append(rtn_outputs)

    def server_iperf(self, bind: str = "") -> None:
        """
        author:             xianda.liu
        date:               2022-09-03
        description:        iperf server命令执行
        """
        if self.iperf_port is None:
            self.iperf_port = constants.IPERF_PORT
        if 'windows' not in self.server_os:
            iperf_head = constants.IPERF
        else:
            iperf_head = constants.IPERF_WIN
        exec_command = iperf_head + ' -s -i {} -p {}'.format(self.interval, str(self.iperf_port))

        # -B, --bind      <host>
        if bind:
            para_b = ' -B {}'.format(bind)
            exec_command += para_b

        if 'windows' not in self.server_os:
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        else:
            from scripts.script_libs.windows_command_operation import WindowsCommandOperation
            if self.rpc_server_ip == self.test_device_info_dict['client_device_ip']:
                win_vm_ip = None
            else:
                win_vm_ip = self.rpc_server_ip
            WindowsCommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                win_vm_ip=win_vm_ip)

    @classmethod
    def iperf3_test(cls, port: str, second: int, client_device_ip,
                    packet_length: int,
                    test_direction: str = 'rx') -> None:
        """
        author:      junfeng.he
        date:        2024-07-26
        description: iperf3 打流
        :param port: iperf3 port
        :param second: 打流时间
        :param client_device_ip: client ip
        :param packet_length: 发包大小
        :param test_direction: 打流方向
        """
        cpu_num = CommonOperation.get_logical_cpu_num(cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        cmd = "ps -ef | grep 'iperf3 -s -D -p {}'".format(port) + " | grep -v grep | awk '{print $2}' | xargs kill 9"
        CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        if test_direction == 'rx':
            cmd = 'iperf3 -s -D -p {}'.format(port)
            CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            iperf_cmd = f"iperf3 -c {client_device_ip} -u -t {second} -i 10 -b 1G " \
                        f"-l {packet_length} -P {cpu_num} -p {port}"
            CommandOperation.execute_command_with_error(
                iperf_cmd, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
        # tx
        else:
            cmd = 'iperf3 -s -D -p {}'.format(port)
            CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
            iperf_cmd = f"iperf3 -c {client_device_ip} -u -t {second} -i 10 -b 1G " \
                        f"-l {packet_length} -P {cpu_num} -p {port}"
            CommandOperation.execute_command_with_error(
                iperf_cmd, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)

    @classmethod
    def iperf3_test_exit(cls, port: str) -> None:
        """
        author:      junfeng.he
        date:        2024-07-26
        description: 重定向表检查
        """
        cmd = "ps -ef | grep 'iperf3 -s -D -p {}'".format(port) + " | grep -v grep | awk '{print $2}' | xargs kill 9"
        CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        cmd = "ps -ef | grep 'iperf3 -c' | grep '-p {}'".format(port) + \
              " | grep -v grep | awk '{print $2}' | xargs kill 9"
        CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)

        cmd = "ps -ef | grep 'iperf3 -s -D -p {}'".format(port) + " | grep -v grep | awk '{print $2}' | xargs kill 9"
        CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
        cmd = "ps -ef | grep 'iperf3 -c' | grep '-p {}'".format(port) + \
              " | grep -v grep | awk '{print $2}' | xargs kill 9"
        CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)

    @classmethod
    def get_iperf3_port(cls, port: int) -> int:
        """
        author:      junfeng.he
        date:        2025-08-05
        description: 为了避免冲突,根据 vm & port 生成实际 port
        :param port: 输入 port
        :return 返回生成 port
        """
        cur_path = os.path.abspath(os.path.dirname(__file__))
        num_list = re.findall(r'm(\d+)', cur_path)
        if num_list and num_list[0].isdigit():
            vm = int(num_list[0])
        else:
            vm = 999
        port_list = re.findall(r'-p (\d+)', f'-p {port}')
        if port_list and port_list[0].isdigit():
            port_offset = int(port_list[0])
        else:
            port_offset = 0
        use_port = 30000 + vm % 1000 + port_offset % 100
        return use_port


class Iperf2Operation(object):

    def __init__(self, server_mgr_ip, client_mgr_ip, server_device_ip, client_device_ip,
                 bandwidth: str = '10M', udp_flag: bool = False,
                 packet_length: int = 64, run_time: int = 60, parallel_num: int = 8):
        """
        入参
        :param server_device_ip:
        :param client_device_ip:
        :param bandwidth:
        :param udp_flag:         是否使用UDP发送, 默认关闭
        :param packet_length:
        :param run_time:         iperf发包时长，默认60s
        :param parallel_num:     线程数
        """

        self.udp_flag = udp_flag
        self.run_time = run_time
        self.server_device_ip = server_device_ip
        self.client_device_ip = client_device_ip
        self.server_mgr_ip = server_mgr_ip
        self.client_mgr_ip = client_mgr_ip
        self.bandwidth = bandwidth
        self.packet_length = packet_length
        self.parallel_num = parallel_num

    def client_iperf2(self) -> tuple or None:
        """
        author:             junfeng.he
        date:               2023-11-07
        description:        iperf client命令执行
        """
        exec_command = "iperf -c {} -B {} -p {} -t {} -l {} -b {} -P {}".format(
            self.server_device_ip, self.client_device_ip, str(constants.IPERF2_PORT), str(self.run_time),
            self.packet_length, self.bandwidth, self.parallel_num)
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                exec_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, ssh_ip=self.server_mgr_ip)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        exit(0)

    def server_iperf2(self) -> None:
        """
        author:             junfeng.he
        date:               2023-11-07
        description:        iperf server命令执行
        """
        exec_command = 'iperf -s -i 5 -p {}'.format(str(constants.IPERF2_PORT))
        CommandOperation.execute_command_based_paramiko_with_rtncode(
            exec_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, ssh_ip=self.client_mgr_ip)
        exit(0)


if __name__ == '__main__':
    pass
