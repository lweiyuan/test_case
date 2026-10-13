import json
import re
import time
from random import *
from re import findall, finditer
from string import ascii_letters, digits, hexdigits
import subprocess

from threading import Thread
import paramiko
import logging

# 配置日志记录器
import logging

# 配置日志记录器
# 设置日志格式
log_format = '%(asctime)s - %(message)s'
# 创建日志记录器
logger = logging.getLogger('my_logger')
logger.setLevel(logging.INFO)  # 设置日志级别

# 创建文件处理器，用于将日志写入文件
file_handler = logging.FileHandler('./test_log.txt')
file_handler.setLevel(logging.INFO)  # 设置处理器的日志级别

# 创建日志格式器，并将其添加到文件处理器
formatter = logging.Formatter(log_format)
file_handler.setFormatter(formatter)

# 将文件处理器添加到日志记录器
logger.addHandler(file_handler)

IP = '10.22.115.228'
EID = 'b'
HOST = '10.22.114.228'
BMC_PWD = "superuser"
BMC_NAME = "sysadmin"
BMC_TOOL_PATH = '/root/sxetest/publish_version/debuginfo/sxebmctest/sxebmccli_*'


class CommandOperation:
    @classmethod
    def execute_command_with_error(cls, cmd, cmd_execute_address):
        # 创建SSH对象
        # with open('./test_log.txt', 'w') as f:
        #     print(cmd)
        #     print(cmd, file=f)
        # print(cmd)
        # logger.info(cmd)
        ssh = paramiko.SSHClient()
        # 允许连接不在know_hosts文件中的主机
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # 连接服务器
        ssh.connect(hostname=HOST, port=22, username='root', password='Tianjian;123')
        # ssh.connect(hostname='10.17.132.223', port=22, username='root', password='Tianjian;123')
        # 执行命令
        stdin, stdout, stderr = ssh.exec_command(cmd)
        # 获取命令结果
        result = stdout.read()

        result_str = result.decode("utf-8")
        # with open('./test_log.txt', 'w') as f:
        #     print(result_str)
        #     print(result_str, file=f)
        log_str = cmd + '\n' + result_str + '\n'
        print(log_str)
        logger.info(log_str)

        # 关闭连接
        ssh.close()
        return 0, result_str, 0


class PldmTool:

    @classmethod
    def set_sensor_thres_holds(cls, ip, sensor, fatal_h, fatal_l=None, warn_h=None, warn_l=None,
                               eid=EID, execute_addr="SERVER"):
        times = 10
        while times:
            fatal_h = randint(60, 70)
            para_fatal_h = f' --upper_fatal={fatal_h}'
            para_fatal_l = f' --lower_fatal={fatal_l}' if fatal_l else ''
            para_warn_h = f' --upper_warn={warn_h}' if warn_h else ''
            para_warn_l = f' --lower_warn={warn_l}' if warn_l else ''
            cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c 13 --sensor={sensor}{para_fatal_h}{para_fatal_l}'
                   f'{para_warn_h}{para_warn_l} --addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}')
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd, cmd_execute_address=execute_addr)
            # print(cmd)
            # print(f'PLDM SetSensorThresHolds 指令执行结果：\n{rtn_output}')
            time.sleep(0.5)
            times -= 1

    @classmethod
    def set_cli_threshold(cls):
        times = 10
        while times:
            _, output, _ = CommandOperation.execute_command_with_error(
                cmd=f'cli /p1 set soctemp hthreshold={choice(range(66, 80))}',
                cmd_execute_address=''
            )
            # print(output)
            times -= 1

    @classmethod
    def set_cli_lldp(cls):
        times = 10
        while times:
            _, output, _ = CommandOperation.execute_command_with_error(
                cmd=f'cli /p0 custom sxe lldpenable port=1 enable={choice([0, 1])}',
                cmd_execute_address=''
            )
            # print(output)
            times -= 1

    @classmethod
    def reboot(cls):
        CommandOperation.execute_command_with_error(
            cmd=f'reboot',
            cmd_execute_address='server'
        )
        times = 600
        while times:
            response = subprocess.run(
                ['ping', '-c', '1', '-W', '10', HOST], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if response.returncode == 0:
                break
            else:
                times -= 1
                time.sleep(1)

    @classmethod
    def upgrade_image(cls):
        # print('cli /p0 upgrade file=/home/wangwt/Image_0.0.0.0_NIC-1160-2X-1213-1916-debug.bin noverchk')
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd=f'cli /p0 upgrade file=/home/wangwt/Image_0.0.0.0_NIC-1160-2X-1213-1916-debug.bin noverchk',
            cmd_execute_address='server'
        )
        # print(output)
        cls.reboot()

    @classmethod
    def upgrade_nor(cls):
        # print(
        #     'cli /p0 debug upgrade packet /home/wangwt/publish_version/factory/Firmware/
        #     1160-2X/norflashRegionSxeFw_1.3.1.7.bin')
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd=f'cli /p0 debug upgrade packet '
                f'/home/wangwt/publish_version/factory/Firmware/1160-2X/norflashRegionSxeFw_1.3.1.7.bin',
            cmd_execute_address='server'
        )
        # print(output)
        cls.reboot()


if __name__ == '__main__':
    count = 10000
    while count:
        PldmTool.upgrade_nor()
        PldmTool.reboot()
        CommandOperation.execute_command_with_error(cmd='insmod /root/sxe.ko', cmd_execute_address='')
        PldmTool.upgrade_image()
        PldmTool.reboot()
        CommandOperation.execute_command_with_error(cmd='insmod /root/sxe.ko', cmd_execute_address='')

        thread_lst = []
        # for i in range(10):
        # thread_lst.append(Thread(target=PldmTool.set_cli_threshold))
        # thread_lst.append(Thread(target=PldmTool.set_cli_lldp))

        # if '228' in HOST:
        #     thread_lst.append(Thread(target=PldmTool.set_sensor_thres_holds, args=(IP, '0', '66')))

        # for t in thread_lst:
        #     t.start()
        #
        # for t in thread_lst:
        #     t.join()

        t = Thread(target=PldmTool.set_sensor_thres_holds, args=(IP, '0', str(randint(60, 70))))
        t.start()
        t.join()
        count -= 1

    while True:
        k = input()
        if k == 'exit':
            break
