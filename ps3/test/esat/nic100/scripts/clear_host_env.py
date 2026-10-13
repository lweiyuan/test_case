#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
author:      haibin.xu
date:        2025.08.15 15:33

case number:
case title:
test object:
check point:
test platform: 物理平台/模拟平台

@steps:


@changelog:

"""
import json
import os
import re
import time
import shutil
import signal
import logging
import argparse
import subprocess

from enum import Enum

RTN_FAIL = -1
RTN_SUCCESS = 0
SSH_PREFIX = 'ssh -q -o StrictHostKeyChecking=no -o TcpKeepAlive=yes -o ServerAliveInterval=30 \
-o ServerAliveCountMax=5 -l {} -p {} {} "{}"'

# 设置log输出级别
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(funcName)s %(lineno)d [%(levelname)s] %(message)s')


class CommandLineArgsParse(object):
    """命令行参数解析"""
    parser = argparse.ArgumentParser(description="NIC Test.")
    # 添加命令行参数中的list选项
    parser.add_argument('-l', '--list', action='store_true', help='列出当前已注册的测试主机信息')
    # 添加命令行参数中的list选项
    parser.add_argument('-s', '--sub_device', action='store_true', help='指定当前是陪测端主机信息')
    # 添加命令行参数中的list选项
    parser.add_argument('-d', '--dpdk', action='store_true', help='指定当前是否为dpdk测试')
    # 添加命令行参数中的cli tool选项
    parser.add_argument('--cm', default=10000, type=int, help='指定card module， 即板卡类型， 0： RAID, 1： HBA, '
                                                              '默认 不指定')
    # 添加命令行参数中的host label选项
    parser.add_argument('--hl', default='00000', type=str, help='指定 host label, 必选参数, 内网可用 pmxxx 或 xxx, '
                                                                '外网可用 vmxxx, 默认不指定')
    # 添加命令行参数中的test object选项
    parser.add_argument('--to', default=10000, type=int, help='指定 test object, 0: SXE, 1: e810, 2: mlx5, 默认 10000 '
                                                              '即不指定')

    args = parser.parse_args()

    @classmethod
    def get_test_object(cls) -> str:
        """
        author:      haibin.xu
        date:        2020-09-03 19:07:48
        description: 获取命令行参数中的 host label
        :return:     返回命令行中的host label
        """
        rtn_test_obj = None

        if cls.args.to == 0:
            rtn_test_obj = 'sxe2'
        elif cls.args.to == 1:
            rtn_test_obj = 'e810'
        elif cls.args.to == 2:
            rtn_test_obj = 'mlx5'

        return rtn_test_obj

    @classmethod
    def get_subdevice_flag(cls) -> bool:
        """
        author:      haibin.xu
        date:        2026-03-30 17:18:02
        description: 获取是否为陪测端标志位

        :return:
        """
        return cls.args.sub_device

    @classmethod
    def get_dpdk_flag(cls) -> bool:
        """
        author:      haibin.xu
        date:        2026-03-30 17:18:02
        description: 获取是否为陪测端标志位

        :return:
        """
        return cls.args.dpdk

    @classmethod
    def get_host_label(cls) -> str:
        """
        author:      haibin.xu
        date:        2020-09-03 19:07:48
        description: 获取命令行参数中的 host label
        :return:     返回命令行中的host label

        """
        if cls.args.hl == '00000':
            rtn_label = None
        elif cls.args.hl.isdigit():
            rtn_label = 'pm{}'.format(cls.args.hl)
        else:
            rtn_label = cls.args.hl

        return rtn_label

    @classmethod
    def get_list_host_info(cls) -> bool:
        """
        author:      haibin.xu
        date:        2020-09-03 19:07:48
        description: 获取命令行参数中的 host label
        :return:     返回命令行中的host label
        """
        return cls.args.list


class CommonFunc(object):
    """
    author:      haibin.xu
    date:        2022-12-09 17:19:11
    description: 定义公共方法
    """
    timeout = 30

    @classmethod
    def execute_command(cls, cmd: str, local_execute_flag: bool = True, ssh_ip: str = None,
                        ssh_port: str = None, ssh_username: str = 'root', timeout: int = 300) -> tuple:
        """
        author:      haibin.xu
        date:        2021-09-14 12:03:28
        description: 执行给定的命令，并检查返回状态和结果
        :param cmd:     执行的命令字符串
        :param timeout: 命令执行超时
        :return:  返回命令执行状态和输出结果
        """
        if not local_execute_flag:
            # ssh命令拼接前缀
            cmd = SSH_PREFIX.format(ssh_username, ssh_port, ssh_ip, cmd)

        logging.info('execute command: {}'.format(cmd))

        # 执行命令并获取返回结果
        obj = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
                               start_new_session=True)

        try:
            cmd_output, cmd_stderr = obj.communicate(timeout=timeout)
            rtn_code = obj.poll()
            # cmd_output, cmd_stderr解码
            try:
                if isinstance(cmd_output, bytes):
                    cmd_output = cmd_output.decode('utf-8').rstrip()
            except UnicodeDecodeError:
                if isinstance(cmd_output, bytes):
                    cmd_output = cmd_output.decode('gbk').rstrip()
            try:
                if isinstance(cmd_stderr, bytes):
                    cmd_stderr = cmd_stderr.decode('utf-8').rstrip()
            except UnicodeDecodeError:
                if isinstance(cmd_stderr, bytes):
                    cmd_stderr = cmd_stderr.decode('gbk').rstrip()
        except subprocess.TimeoutExpired:
            # 注意：不能只使用p.kill和p.terminate，无法杀干净所有的子进程，需要使用os.killpg
            obj.kill()
            obj.terminate()
            os.killpg(obj.pid, signal.SIGTERM)

            rtn_code = RTN_FAIL
            cmd_output = ''
            cmd_stderr = '[ERROR]Timeout Error : Command "{}", timed out after {} seconds'.format(cmd, timeout)
        except Exception as e:
            rtn_code = RTN_FAIL
            cmd_output = ''
            cmd_stderr = 'Exception Error : Command "{}", found exception:\n{}'.format(cmd, e)
            logging.exception(cmd_stderr)

        return rtn_code, cmd_output, cmd_stderr

    @classmethod
    def execute_command_multi_times(cls, cmd: str, timeout: int = 30, test_times: int = 10, sleep_time: int = 15) \
            -> tuple:
        """
        author:      haibin.xu
        date:        2022-04-21 10:22:46
        description:    执行给定次数的给定命令，并检查返回状态和结果
        :param cmd:     执行的命令字符串
        :param timeout  单独指令执行时常限制
        :return:        返回命令执行状态和输出结果, 为三元素元组 cmd_code, cmd_output, cmd_stderr
                        cmd_code    当执行错误时返回-1, 执行成功时为0
                                    执行错误, 指的是远程执行cmd所遇到的"技术错误", 比如连接丢失, 参数不合法
                                    这里不会去管 "业务逻辑错误/语义错误",
                                    比如试图删掉不存在的VD, 此时 storcli 会返回 Status=Failure,
                                    但是该命令从技术上是执行成功了的, 于是返回cmd_code=0
                        cmd_output  shell 执行的"标准输出" stdout
                        cmd_stderr  shell 执行的"标准错误" stderr
        """
        rtn_code = RTN_FAIL
        cmd_stdout = None
        cmd_stderr = None

        while test_times != 0:
            cmd_code, cmd_stdout, cmd_stderr = cls.execute_command(cmd=cmd, timeout=timeout)
            if RTN_SUCCESS != cmd_code:
                logging.error(f'命令: {cmd}, 执行失败，需要再次执行：\ncmd_code: {cmd_code}\ncmd_stdout: {cmd_stdout}\n'
                              f'cmd_stderr: {cmd_stderr}')
                test_times -= 1
                time.sleep(sleep_time)
                continue
            logging.info(f'命令: {cmd}, 执行成功：\ncmd_code: {cmd_code}\ncmd_stdout:\n{cmd_stdout}\n'
                         f'cmd_stderr:\n{cmd_stderr}\n')
            rtn_code = RTN_SUCCESS
            break

        return rtn_code, cmd_stdout, cmd_stderr

    @classmethod
    def make_directory(cls, dir_parh: str = None) -> int:
        """
        author:      haibin.xu
        date:        2022-12-12 11:19:56
        description: 创建目录，如果目录已存在，删除后创建
        """
        mk_c = 0
        rm_c = 0
        while os.path.exists(dir_parh) and rm_c < 10:
            shutil.rmtree(dir_parh)
            rm_c += 1

        if os.path.exists(dir_parh):
            logging.error('新建目录前，删除旧目录：{}，失败'.format(dir_parh))
            return RTN_FAIL

        while not os.path.exists(dir_parh) and mk_c < 10:
            os.makedirs(dir_parh)
            mk_c += 1

        if not os.path.exists(dir_parh):
            logging.error('新建目录：{}，失败'.format(dir_parh))
            return RTN_FAIL

        return RTN_SUCCESS

    @classmethod
    def copy_file(cls, sorce_file_path: str = None, target_path: str = None) -> tuple:
        """
        author:      haibin.xu
        date:        2022-12-12 11:31:16
        description: 拷贝文件
        """
        copy_cmd = '/usr/bin/cp -rf {} {}'.format(sorce_file_path, target_path)
        cmd_code, cmd_output, cmd_stderr = cls.execute_command(cmd=copy_cmd)

        return cmd_code, cmd_output, cmd_stderr

    @classmethod
    def write_file(cls, file_path: str = None, write_content: str = None, write_mode: str = 'a') -> None:
        """
        author:      haibin.xu
        date:        2022-12-12 15:40:45
        description: 写文件
        """
        with open(file_path, write_mode) as fp:
            fp.write(write_content)
            fp.write('\n')

    @classmethod
    def find_file(cls, file_path: str) -> tuple:
        """
        author:      haibin.xu
        date:        2025-08-15 16:35:35
        description: 检查文件是否存在

        :param file_path: 文件路径
        :return: 存在返回0， 不存在返回-1
        """
        find_cmd = 'ls {}'.format(file_path)
        rtn_code, cmd_output, cmd_stderr = CommonFunc.execute_command(find_cmd)
        logging.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            find_cmd, rtn_code, cmd_output, cmd_stderr))
        if rtn_code == RTN_SUCCESS and 1 == len(cmd_output.splitlines()):
            logging.info('目标文件: {}, 存在\n'.format(file_path))
            return RTN_SUCCESS, cmd_output.strip()
        else:
            logging.error('目标文件： {}， 不存在'.format(file_path))
            return RTN_FAIL, None

    @classmethod
    def read_file(cls, file_path: str = None) -> str:
        """
        author:      haibin.xu
        date:        2022-12-12 15:40:45
        description: 读文件

        :param file_path: 文件路径
        """
        all_lines = []
        if file_path and os.path.exists(file_path):
            with open(file_path, 'r') as fp:
                all_lines = fp.readlines()
            logging.info('Get content of file[{}]:\n{}\n'.format(file_path, ''.join(all_lines)))
        else:
            logging.error('Not found file: {}'.format(file_path))

        return ''.join(all_lines)


class Script(object):
    # 版本包路径
    package_tarfile = ''
    # test object
    ctrl_id_test_obj = {}
    # Product Name
    ctrl_id_prod_name = {}
    # specify untar flag
    specify_untar_flag = False
    # specify clear flag
    specify_clear_flag = False
    # specify test object
    specify_test_object = None
    # specify product name
    specify_prod_name = None
    # specify install driver type
    specify_drive_type = None
    # specify cli tool type
    specify_cli_tool = None
    # specify card module
    specify_card_module = None
    # specify not upgrade cpld
    specify_not_upgrade_cpld_flag = None
    # specify host os
    specify_host_os = None
    # specify profile value
    specify_profile_value = None
    # 本端网卡的bdf设备
    specify_bdf_list = []
    # 本端以太设备
    specify_eth_dev_list = []
    # 陪测端标志位
    specify_subdev_flag = False
    # 解压目录
    untarfile_dir = '/opt/ps3sim/{}/tar_package/'
    # host label
    host_label = ''
    # 需要清理的文件
    clear_host_file = '/var/log/* /root/*.log.* /root/*.pcap /root/*.lock /log/nic_log/* /log/var_log/*'

    # 环境信息
    env_info_dict = {
        'pm1801': {
            # 本端ip
            'local_ip': '10.22.180.76',
            # bmc ip
            'local bmp ip': '10.22.181.76 Admin Admin@5000',
            # nic type
            'nic_type': 'sxe2',
            # 串口信息
            'com port': '10.22.181.7 5300',
            # 以太设备
            'eth_device': 'p5p1,p5p2',
            # ps3server
            'ps3server': '10.22.180.88',
            # 机型
            'server module': 'R620G40',
            # 陪测端ip
            'sub_ip': '10.22.180.90',
            # 陪测端bmc ip
            'sub bmp ip': '10.22.181.90 Admin Admin@5000',
            # 陪测端nic type
            'sub_nic_type': 'sxe2',
            # 陪测端串口信息
            'sub_com port': '10.22.181.7 5500',
            # 陪测端以太设备
            'sub_eth_device': 'ens1f1,ens1f0',
            # 陪测端ps3server
            'sub_ps3server': '10.22.180.88',
            # 陪测端机型
            'sub_server module': 'R620G40',
        },
        'pm1802': {
            # 本端ip
            'local_ip': '10.22.180.52',
            # bmc ip
            'local bmp ip': '10.22.181.52 Admin Admin@5000',
            # nic type
            'nic_type': 'sxe2',
            # 串口信息
            'com port': '10.22.181.7 5400',
            # 以太设备
            'eth_device': 'ens1f0,ens1f1',
            # ps3server
            'ps3server': '10.22.180.88',
            # 机型
            'server module': 'R620G40',
            # 陪测端ip
            'sub_ip': '10.22.180.90',
            # 陪测端bmc ip
            'sub bmp ip': '10.22.181.90 Admin Admin@5000',
            # 陪测端nic type
            'sub_nic_type': 'e810',
            # 陪测端串口信息
            'sub_com port': '',
            # 陪测端以太设备
            'sub_eth_device': 'ens6f0,ens6f1',
            # 陪测端ps3server
            'sub_ps3server': '10.22.180.88',
            # 陪测端机型
            'sub_server module': 'R620G40',
        },
        'pm831': {
            # 本端ip
            'local_ip': '10.22.116.156',
            # bmc ip
            'local bmp ip': '10.22.117.156 Admin Admin@5000',
            # nic type
            'nic_type': 'mlx5 cx7',
            # 串口信息
            'com port': '',
            # 以太设备
            'eth_device': 'ens29f0np0,ens29f1np1',
            # ps3server
            'ps3server': '10.22.67.146',
            # 机型
            'server module': 'R6240H0',
            # 陪测端ip
            'sub_ip': '10.22.116.157',
            # 陪测端bmc ip
            'sub bmp ip': '10.22.117.157 Admin Admin@5000',
            # 陪测端nic type
            'sub_nic_type': 'mlx5 cx7',
            # 陪测端串口信息
            'sub_com port': '',
            # 陪测端以太设备
            'sub_eth_device': 'ens4f0np0,ens4f1np1',
            # 陪测端ps3server
            'sub_ps3server': '10.22.67.146',
            # 陪测端机型
            'sub_server module': 'R620G40',
        },
        'pm347': {
            # 本端ip
            'local_ip': '10.22.112.4',
            # bmc ip
            'local bmp ip': '10.22.113.4 Admin Admin@5000',
            # nic type
            'nic_type': 'mlx5 cx7',
            # 串口信息
            'com port': '',
            # 以太设备
            'eth_device': 'ens4f0np0',
            # ps3server
            'ps3server': '10.22.67.146',
            # 机型
            'server module': 'R620G40',
            # 陪测端ip
            'sub_ip': '10.22.112.3',
            # 陪测端bmc ip
            'sub bmp ip': '10.22.113.3 Admin Admin@5000',
            # 陪测端nic type
            'sub_nic_type': 'mlx5 cx7',
            # 陪测端串口信息
            'sub_com port': '',
            # 陪测端以太设备
            'sub_eth_device': 'ens4f0np0',
            # 陪测端ps3server
            'sub_ps3server': '10.22.67.146',
            # 陪测端机型
            'sub_server module': 'R620G40',
        },
    }

    @classmethod
    def get_clishow(cls) -> None:
        """
        author:      haibin.xu
        date:        2026-03-30 14:46:04
        description: sxecli show信息

        :return:
        """
        if 'sxe' in cls.specify_test_object:
            cli_cmd = '{}cli -vv'.format(cls.specify_test_object)
            cmd_code, cmd_stdout, cmd_stderr = CommonFunc.execute_command(cmd=cli_cmd)
            logging.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}\n'.format(
                cli_cmd, cmd_code, cmd_stdout, cmd_stderr))

            cli_cmd = '{}cli show'.format(cls.specify_test_object)
            cmd_code, cmd_stdout, cmd_stderr = CommonFunc.execute_command(cmd=cli_cmd)
            logging.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}\n'.format(
                cli_cmd, cmd_code, cmd_stdout, cmd_stderr))

    @classmethod
    def get_rdma_device(cls) -> None:
        """
        author:      haibin.xu
        date:        2026-03-30 14:53:36
        description: rdma link信息

        :return:
        """
        rdma_cmd = 'rdma link'
        cmd_code, cmd_stdout, cmd_stderr = CommonFunc.execute_command(cmd=rdma_cmd)
        logging.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}\n'.format(
            rdma_cmd, cmd_code, cmd_stdout, cmd_stderr))

    @classmethod
    def get_env_config(cls) -> None:
        """
        author:      haibin.xu
        date:        2025-08-30 13:52:58
        description: 获取设定的profile值

        :return:
        """
        get_cmd = 'cat /root/sxetest/env_config.ini'
        cmd_code, cmd_stdout, cmd_stderr = CommonFunc.execute_command(cmd=get_cmd)
        logging.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}\n'.format(
            get_cmd, cmd_code, cmd_stdout, cmd_stderr))

    @classmethod
    def get_bdf_info(cls) -> None:
        """
        author:      haibin.xu
        date:        2026-03-30 15:49:49
        description: 获取以太设备的bdf地址

        :return:
        """
        cls.specify_eth_dev_list = cls.env_info_dict.get(cls.host_label).get('eth_device').split(',') if not \
            cls.specify_subdev_flag else cls.env_info_dict.get(cls.host_label).get('sub_eth_device').split(',')
        for eth_dev in cls.specify_eth_dev_list:
            get_cmd = 'ethtool -i {}'.format(eth_dev)
            cmd_code, cmd_stdout, cmd_stderr = CommonFunc.execute_command(cmd=get_cmd)
            logging.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}\n'.format(
                get_cmd, cmd_code, cmd_stdout, cmd_stderr))

            match_list = re.findall(r'bus-info:\s*(.*)', cmd_stdout)
            if match_list:
                cls.specify_bdf_list.append(match_list[0])

        logging.info('获取到当前环境测试的以太设备: {}, 对应的bdf信息: {}\n'.format(cls.specify_eth_dev_list, cls.specify_bdf_list))

    @classmethod
    def get_host_label(cls) -> None:
        """
        author:      haibin.xu
        date:        2025-08-25 14:16:46
        description: 获取当前环境的host label

        :return:
        """
        cls.host_label = CommandLineArgsParse.get_host_label()
        if cls.host_label is None:
            logging.error('当前环境未指定 host label 信息， 不再继续执行')
            exit(1)

        cls.specify_subdev_flag = CommandLineArgsParse.get_subdevice_flag()

        logging.info('获取到当前 host label: {}, 是否为陪测端: {}, 配置信息:\n{}\n'.format(
            cls.host_label, cls.specify_subdev_flag, json.dumps(cls.env_info_dict.get(cls.host_label), indent=2)))

        cls.get_bdf_info()

    @classmethod
    def get_ip_info(cls) -> None:
        """
        author:      haibin.xu
        date:        2026-03-30 16:02:56
        description: 获取当前设备的ip 信息

        :return:
        """
        logging.info('获取当前环境 IP 信息')
        get_cmd = 'ip a'
        cmd_code, cmd_stdout, cmd_stderr = CommonFunc.execute_command(cmd=get_cmd)
        logging.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}\n'.format(
            get_cmd, cmd_code, cmd_stdout, cmd_stderr))

    @classmethod
    def get_test_object(cls) -> None:
        """
        author:      haibin.xu
        date:        2026-03-30 16:36:35
        description: 获取测试对象

        :return:
        """
        cls.specify_test_object = CommandLineArgsParse.get_test_object()
        if cls.specify_test_object is None:
            nic_type = cls.env_info_dict.get(cls.host_label).get('nic_type') if not cls.specify_subdev_flag else \
                cls.env_info_dict.get(cls.host_label).get('sub_nic_type')
            if 'sxe2' == nic_type:
                cls.specify_test_object = 'sxe2'
            elif 'e810' == nic_type:
                cls.specify_test_object = 'e810'
            elif 'mlx5' in nic_type:
                cls.specify_test_object = 'mlx5'

        logging.info('test_object: {}\n'.format(cls.specify_test_object))

    @classmethod
    def init(cls):
        if CommandLineArgsParse.get_list_host_info():
            logging.info('当前已注册的可自动清理环境的的主机信息:\n')
            for host_label, host_info in cls.env_info_dict.items():
                print('{:<6}: {}\n'.format(host_label, json.dumps(host_info, indent=2)))
            exit(0)

        cls.get_host_label()

        cls.get_ip_info()

        cls.get_test_object()

        cls.get_env_config()

        cls.get_clishow()

        cls.get_rdma_device()

    @classmethod
    def clean_logfile(cls):
        """
        author:      haibin.xu
        date:        2026-03-30 15:00:33
        description: 清理日志

        :return:
        """
        logging.info('清理日志: {}'.format(cls.clear_host_file))
        clear_log_cmd = 'rm -rf {}'.format(cls.clear_host_file)
        cmd_code, cmd_stdout, cmd_stderr = CommonFunc.execute_command(cmd=clear_log_cmd)
        logging.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            clear_log_cmd, cmd_code, cmd_stdout, cmd_stderr))

        logging.info('获取环境内存信息')
        get_memory_cmd = 'df -h'
        cmd_code, cmd_stdout, cmd_stderr = CommonFunc.execute_command(cmd=get_memory_cmd)
        logging.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
            get_memory_cmd, cmd_code, cmd_stdout, cmd_stderr))

    @classmethod
    def clear_process(cls):
        """
        author:      haibin.xu
        date:        2026-03-30 16:15:26
        description: 清理进程

        :return:
        """
        proc_name_list = ['ipvbs_s.py']
        logging.info('清理进程: {}'.format(proc_name_list))

        for proc_name in proc_name_list:
            kill_cmd = 'pgrep -af "{}"; pkill -f "{}"; pgrep -af "{}"'.format(proc_name, proc_name, proc_name)
            cmd_code, cmd_stdout, cmd_stderr = CommonFunc.execute_command(cmd=kill_cmd)
            logging.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                kill_cmd, cmd_code, cmd_stdout, cmd_stderr))

    @classmethod
    def clear_vf(cls):
        """
        author:      haibin.xu
        date:        2026-03-30 15:13:47
        description: 清理vf

        :return:
        """
        logging.info('清理环境中的vf')
        for bdf in cls.specify_bdf_list:
            clean_vf_cmd = 'echo 0 > /sys/bus/pci/devices/{}/sriov_numvfs'.format(bdf)
            cmd_code, cmd_stdout, cmd_stderr = CommonFunc.execute_command(cmd=clean_vf_cmd)
            logging.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                clean_vf_cmd, cmd_code, cmd_stdout, cmd_stderr))

    @classmethod
    def clear_bond(cls) -> None:
        """
        author:      haibin.xu
        date:        2026-03-30 16:01:43
        description: 清理bond信息

        :return:
        """
        logging.info('清除当前环境中的bond信息（如果存在）')
        cmd_list = ['pkill -f "ib_.*_bw"', 'ip link del bond0']
        for eth_dev in cls.specify_eth_dev_list:
            cmd_list.append('ip link set {} up'.format(eth_dev))

        for cmd in cmd_list:
            cmd_code, cmd_stdout, cmd_stderr = CommonFunc.execute_command(cmd=cmd)
            logging.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                cmd, cmd_code, cmd_stdout, cmd_stderr))

    @classmethod
    def reset_rdma_driver(cls) -> None:
        """
        author:      haibin.xu
        date:        2026-03-30 16:21:49
        description: rdma 驱动加卸载

        :return:
        """
        com_mode = 0
        if CommandLineArgsParse.get_dpdk_flag():
            com_mode = 2
        if 'sxe' in cls.specify_test_object:
            cmd_list = ['rmmod sxe2rdma; sleep 1', 'rmmod sxe2vf; sleep 1', 'rmmod sxe2; sleep 1',
                        'insmod /root/sxe2.ko drv_mode={}; sleep 2'.format(com_mode),
                        'modprobe ib_core; modprobe ib_uverbs',
                        'insmod /root/sxe2rdma.ko resource_profile=1 fragment_count_limit=13; sleep 1',
                        'insmod /root/sxe2vf.ko; sleep 1', 'rdma link']
        elif 'e810' in cls.specify_test_object:
            cmd_list = ['rmmod irdma; sleep 1', 'rmmod iavf; sleep 1', 'rmmod ice; sleep 1',
                        'insmod /root/ice.ko; sleep 2',
                        'insmod /root/irdma.ko resource_profile=1 roce_ena=1; sleep 1',
                        'insmod /root/iavf.ko; sleep 1',
                        'rdma link']
        elif 'mlx5' in cls.specify_test_object:
            return

        for cmd in cmd_list:
            cmd_code, cmd_stdout, cmd_stderr = CommonFunc.execute_command(cmd=cmd)
            logging.info('Command: {}\nCmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                cmd, cmd_code, cmd_stdout, cmd_stderr))

    @classmethod
    def run(cls):
        cls.init()
        cls.clean_logfile()
        cls.clear_vf()
        cls.clear_bond()
        cls.clear_process()
        cls.reset_rdma_driver()

        logging.info('环境信息及处理完毕')


def main():
    Script.run()


if __name__ == '__main__':
    main()
