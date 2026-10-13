#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      haibin.xu
date:        2020.07.09 12:06
description: 定义命令行操作类

@changelog      2020-12-10 16:45:19  haibin.xu
                1. 命令执行操作方法（execute_command_based_paramiko， execute_command_based_paramiko_with_rtncode，
                   transport_file_with_paramiko， execute_command_with_error，execute_command_interactive）添加
                   ssh_ip, ssh_port参数，用于在给定的ip:port下执行命令
"""
import os
import re
import time
import copy
import socket
import signal
import paramiko
import platform
import subprocess
import configparser
from typing import Generator
from scripts.script_libs import constants, log
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum, TestObjectEnum, \
    TestEntryEnum, CaseRunPhaseEnum, CmdStatusEnum, HostOsEnum, TestPlatformEnum, TestObjectStrEnum, BugTypeEnum
from scripts.script_libs.ssh_operation import SSHConnectionPool

PD_SET_OFFLINE_PATTERN = r'set +offline'
PD_SET_ONLINE_PATTERN = r'set +online'
PD_SET_READY_PATTERN = r'set +ready'
PD_SET_JBOD_PATTERN = r'set +jbod( +trace)*$'
JBOD_SWITCH_OFF_PATTERN = r'set +jbod=off'
PD_SET_MISSING_PATTERN = r'set +missing'
ADD_HOTSPARE_PATTERN = r'add +hotsparedrive'
DEL_HOTSPARE_PATTERN = r'delete +hotsparedrive'
INSERT_PATTERN = r'insert'
ADD_VD_PATTERN = r'add +vd'
DEL_VD_PATTERN = r'/v(\d+|all) +del'
INJECT_DALIO_ERROR_PATTERN = r'dalio +injecterr +diskID=[0-9]+ +active=1'
DALIO_OPERATE_DISK_PATTERN = r'dalio +operatedisk'
CUSTOM_INJECT_PATTER = r'custom +inject +active'

INJECT_DISK_ERROR_PATTERN = r'injectErr'
ADD_DISK_PATTERN = r'addDisk'
DEL_DISK_PATTERN = r'delDisk'
ONLINE_DISK_PATTERN = r'onlineDisk'
OFFLINE_DISK_PATTERN = r'offlineDisk'
EXCHANGE_DISK_PATTERN = r'exchangeDisk'
CREATE_NVME_PATTERN = r'createNvme'
CONTROLLER_SHOW_PATTERN = r'/c(\d+|all) +show'

WRITE_CACHE_PATTERN = r'WT|WB|AWB'
# PURPLE = '\033[35m'
# RESET = '\033[0m'


class CommandOperation(object):
    # 测试入口
    test_entry = None
    # 编译对象
    compile_object = None
    # 测试对象
    test_object = None
    # 获取server ip
    server_ip = None
    # 获取server node ip
    server_node_ip = constants.SERVER_NODE_IP
    # 获取server port
    server_port = constants.SERVER_PORT
    # 定义host 宿主机port
    server_default_port = 728
    # 获取soc ip
    client_ip = None
    # 获取soc node ip
    client_node_ip = constants.CLIENT_NODE_IP
    # 获取soc port
    client_port = constants.CLIENT_PORT
    # 定义soc 宿主机port
    client_default_port = 728
    # no trace flag
    no_trace_flag = constants.NO_TRACE_FLAG
    # ssh登陆用户名
    ssh_username = 'root'
    # 本地操作系统平台
    local_platform = platform.system()
    scripts_end_keyword = 'result_dict:'
    # 保存windows session
    saved_session = []
    # 保存kvm本地ip
    kvm_localnet = ""
    pool = {}

    @classmethod
    def __get_match_parameter(cls, param_pattern: str, params_list: list = None, params_dict: dict = None) -> str:
        """
        author:      haibin.xu
        date:        2020-09-09 15:26:18
        description: 从参数列表中获取指定匹配模式的参数
        :param param_pattern: 参数匹配模式
        :param params_list: 参数列表
        :param params_dict: 关键字参数
        :return:     返回匹配的参数，没有的话，返回''
        """
        rtn_param = constants.STR_EMPTY

        if params_list is not None:
            for param in params_list:
                if re.match(param_pattern, param):
                    rtn_param = param
                    break
        if (constants.STR_EMPTY == rtn_param) and (params_dict is not None):
            for key_pa in params_dict:
                if re.match(param_pattern, key_pa):
                    rtn_param = key_pa
                    break

        return rtn_param

    @classmethod
    def sort_parameters(cls, priority_params_list: list, *args: tuple, **kwargs: dict) -> tuple:
        """
        author:      haibin.xu
        date:        2020-08-26 16:21:03
        description: 根据参数优先级列表（类变量cli_cmd_args_list中已定义）调整输入参数顺序
        :param priority_params_list: 优先级参数列表
        :param args:  独立参数信息，以元组形式给出
        :param kwargs: 参数信息，以字典形式给出
        :return:     返回优先级调整后的列表

        @changelog      2020-11-13 10:53:00  haibin.xu
                        1. 优化函数实现, 实现独立参数、关键字参数严格按照优先级列表排序的功能，如果同一个参数即出现在
                           独立参数列表中又出现在关键字参数字典中（一般不会有这种情况），则独立参数形式排在关键字参数
                           形式之前
        """
        rtn_param_list = []
        remain_args_list = [ar for ar in list(args) if ar != constants.STR_EMPTY]
        remain_kwargs_dict = copy.deepcopy(kwargs)
        for param in priority_params_list:
            param_in_args = cls.__get_match_parameter(param_pattern=param, params_list=remain_args_list)
            param_in_kwargs = cls.__get_match_parameter(param_pattern=param, params_dict=kwargs)
            if param_in_args:
                rtn_param_list.append(param_in_args)
                remain_args_list.remove(param_in_args)
            if param_in_kwargs:
                rtn_param_list.append(param_in_kwargs + '=' + str(kwargs[param_in_kwargs]))
                del remain_kwargs_dict[param_in_kwargs]

        return rtn_param_list, remain_args_list, remain_kwargs_dict

    @classmethod
    def concat_parameters(cls, *args: tuple, **kwargs: dict) -> str:
        """
        author:         wei.yuan
        date:           2020.07.06
        description:    拼接可选参数与关键字参数
        :param args:    可选参数
        :param kwargs:  关键字参数
        :return:        返回拼接结果
        """
        concat_args_list, remain_args_list, remain_kwargs_dict = cls.sort_parameters(*args, **kwargs)
        concat_args_list.extend(remain_args_list)
        for key in remain_kwargs_dict:
            concat_args_list.append(key + '=' + str(remain_kwargs_dict[key]))
        concat_args_str = constants.STR_SPACE.join(concat_args_list)

        return concat_args_str

    @classmethod
    def get_logical_ip_form_config(cls) -> tuple:
        """
       從配置文件nic_driver_config.ini中获取server和client logical ip
       :return:
       """
        config = configparser.ConfigParser()
        config.read(constants.NIC_CONFIG_PATH)

        logical_server_ip = config['logical_ip']['server']
        logical_client_ip = config['logical_ip']['client']

        # log.warning("get_logical_ip_form_config => cls.server_logical_ip：{}，cls.client_logical_ip：{}".
        #             format(logical_server_ip, logical_client_ip))
        return logical_server_ip, logical_client_ip


    @classmethod
    def __check_ignore_release_conn_cmd(cls, cmd):

        if '_' in cmd:
            return False

        if 'reboot' in cmd:
            return True

        if 'shutdown' in cmd:
            return True

        if 'power off' in cmd:
            return True

        if 'power reset' in cmd:
            return True

        if 'power cycle' in cmd:
            return True

        if 'init 0' in cmd:
            return True

    @classmethod
    def close_ssh_pool(cls):
        for k, v in cls.pool.items():
            log.info(f"关闭 {k} SSH 连接")
            try:
                v.close_all()
            except Exception as e:
                log.error(e)

    @classmethod
    def write_cmd(cls, cmd):
        try:
            if isinstance(cmd, list):
                cmd = ' '.join(cmd)
            _, now = cls.get_time()
            cmd = f"[{now}] " + cmd + ' \r\n'
            file_path = os.path.join(constants.ESAT_PATH_OUT_PUTS_SCRIPTS_PATH, 'exec_cli.log')
            try:
                with open(file_path, 'a', encoding='utf-8') as fp:
                    fp.write(cmd)
            except UnicodeEncodeError:
                with open(file_path, 'a', encoding='gbk') as fp:
                    fp.write(cmd)
        except Exception as e:
            cmd = f"mkdir -p {constants.ESAT_PATH_OUT_PUTS_SCRIPTS_PATH}"
            subprocess.getstatusoutput(cmd)
            log.info(e)

    @classmethod
    def execute_command_based_paramiko_with_rtncode(cls, cmd: str,
                                                    cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
                                                    local_execute_flag: bool = False, ssh_ip: str = None,
                                                    ssh_port: str = None, ssh_username: str = None,
                                                    ssh_password: str = None,
                                                    timeout: int = 900, print_enable: bool = True,
                                                    host_os_server: str = None,
                                                    host_os_client: str = None,
                                                    win_vm_ip: str = None, shiled_error: bool = False,
                                                    print_steps: bool = True, print_outputs: bool = True,
                                                    level: int=-2) -> tuple:
        """
        author:      haibin.xu
        date:        2020-09-12 12:14:22
        description: 执行给定的命令
        :param cmd:  执行的命令字符串
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :param local_execute_flag: 是否在本地执行命令的标志位
        :param ssh_ip:  指定 ssh 连接的 ip， 需与ssh_port同时定义，只定义其中一个，不起作用，同时local_execute_flag需为False
        :param ssh_port:指定 ssh 连接的 port， 需与ssh_ip同时定义，只定义其中一个，不起作用，同时local_execute_flag需为False
        :param ssh_username: 指定ssh连接的username，不指定时，使用root
        :param print_enable: 是否打印执行指令到控制台，默认为True
        :param shiled_error: 是否屏蔽错误信息
        :param windows_vm_name: 指定VM名称，若不为None，在VM机执行cmd；否则在物理机执行
        :return:     返回命令执行状态和输出结果, 为三元素元组 cmd_code, cmd_output, cmd_stderr
                     cmd_code    shell 执行的输出错误码
                     cmd_output  shell 执行的"标准输出" stdout
                     cmd_stderr  shell 执行的"标准错误" stderr

        @changelog      2021-03-16 11:02:28  haibin.xu
                        1. 优化函数实现, 添加ssh_username参数
                        2021-10-13 10:26:10  haibin.xu
                        1. 优化函数实现，添加print_enable参数，实现是否打印执行命令到控制台，默认打印
        """
        cmd_code, cmd_output, cmd_stderr = "", "", ""
        if not host_os_server or not host_os_client :
            from scripts.script_libs.common_operation import CommonOperation
            host_os_server, host_os_client = CommonOperation.get_nic_os()

        if ("iperf -" in cmd or "iperf3 -" in cmd) and "iperf -v" not in cmd and "iperf3 -v" not in cmd:
            """
            多对一拓扑存在冲突场景	控制变量	计算公式(vm为jenkins的测试节点编号)
            iperf	port	port = 20000 + vm%1000 + 传递port%100
            iperf3	port	port = 30000 + vm%1000 + 传递port%100
            """
            cur_path = os.path.abspath(os.path.dirname(__file__))
            num_list = re.findall(r'm(\d+)', cur_path)
            if num_list and num_list[0].isdigit():
                vm = int(num_list[0])
            else:
                vm = 999
            port_list = re.findall(r'-p (\d+)', cmd)
            if port_list and port_list[0].isdigit():
                port_offset = int(port_list[0])
            else:
                port_offset = 0
            if "iperf3" in cmd:
                use_port = 30000 + vm % 1000 + port_offset % 100
                log.info("iperf3:vm:{}, port_offset:{}, use_port：{}".format(vm, port_offset, use_port))
                if port_offset:
                    cmd = cmd.replace("-p {}".format(port_offset), "-p {}".format(use_port))
                else:
                    cmd = cmd.replace("iperf3".format(port_offset), "iperf3 -p {}".format(use_port))
            else:
                use_port = 20000 + vm % 1000 + port_offset % 100
                log.info("iperf:vm:{}, port_offset:{}, use_port：{}".format(vm, port_offset, use_port))
                if port_offset:
                    cmd = cmd.replace("-p {}".format(port_offset), "-p {}".format(use_port))
                else:
                    cmd = cmd.replace("iperf".format(port_offset), "iperf -p {}".format(use_port))

        # # client-发包仪:跳过
        # if cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
        #     from scripts.script_libs.common_operation import CommonOperation
        #     server_drv_name, client_drv_name = CommonOperation.get_nic_driver_name()
        #     server_ip, client_ip = CommonOperation.get_nic_logical_ip()
        #     if 'renix' in client_drv_name:
        #         client_is_renix = True
        #     else:
        #         client_is_renix = False
        #     if client_is_renix:
        #         log.warning(f'{cmd_execute_address}:{client_ip}为发包仪，跳过[{cmd}]执行')
        #         cmd_code = RtnStatusEnum.FAIL.value
        #         cmd_output = ''
        #         cmd_stderr = ''
        #         return cmd_code, cmd_output, cmd_stderr

        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            ssh_port = str(test_port)

        # 传ip，也必须传cmd_execute_address
        if ((
                (HostOsEnum.WINDOWS.value in host_os_client and
                 cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value) or
                (HostOsEnum.WINDOWS.value in host_os_server and
                 cmd_execute_address == CmdExecuteAdressEnum.SERVER.value)
        ) or win_vm_ip) and not local_execute_flag:
            check_host_ip = ssh_ip
            if check_host_ip is None:
                check_host_ip, _ = cls.__get_ip_port(cmd_execute_address)
            return cls.execute_command_for_windows(cmd=cmd, vm_ip=win_vm_ip,
                                                   ssh_ip=check_host_ip, ssh_port=ssh_port, timeout=timeout)

        cmd_code = None
        # 如果是cli命令则增加time获取
        cmd = cmd.lstrip()
        if cmd.startswith(constants.SXE2CLI64):
            cmd = 'time ' + cmd

        if local_execute_flag:
            # 本地执行，不需要指定ip, port
            ip = None
            port = None
        # 获取ssh要连接的ip, port
        elif (ssh_ip is None) or (ssh_port is None):
            # 非本地执行，且未指定ssh_ip/ssh_port，则需要根据cmd_execute_address获取ip, port
            ip, resolved_port = cls.__get_ip_port(cmd_execute_address)
            if ip is None:
                return RtnStatusEnum.FAIL.value, '', 'Can not get valid ip and port.'
            # 已由命令行 --tp 显式指定端口时保持该端口，否则使用配置的默认端口
            if ssh_port is None:
                ssh_port = str(resolved_port)
        else:
            # 非本地执行，但指定了ssh_ip，ssh_port，则ip, port 使用指定的ssh_ip，ssh_port
            ip = ssh_ip
            port = ssh_port
        if ssh_username is None:
            ssh_username = cls.ssh_username
        if cls.__execute_local_command_enabled(ip, local_execute_flag):
            # 执行命令并获取返回结果
            cls.__print_message(message='execute in local, cmd: {}'.format(cmd), print_enable=print_enable,
                                level=level)
            log.info('execute in local, cmd: {}'.format(cmd))
            cmd_code, cmd_output, cmd_stderr = cls.__execute_command(cmd, timeout=timeout)
        else:
            """
            from scripts.script_libs.common_operation import CommonOperation
            if print_steps:
                CommonOperation.concat_test_steps(f'{ssh_username}@{ip}端执行->[{cmd}]', level=level)
            # 首先打印cmd信息，以帮助定位
            # cls.__print_message(message='ssh host: {}@{}:{}, cmd: {}'.format(ssh_username, ip, ssh_port, cmd),
            #                     print_enable=print_enable)
            # 创建SSH对象
            ssh = paramiko.SSHClient()
            # 允许连接不在know_hosts文件中的主机，否则可能报错：paramiko.ssh_exception.SSHException:
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            for i in range(3):
                try:
                    if i > 0:
                        time.sleep(2)
                        log.info(f"ssh connect failed , try again current num {i}...")
                    # 连接服务器
                    ssh.connect(hostname=ip, port=int(ssh_port), username=ssh_username, banner_timeout=30)
                    # if ip in ["10.22.114.212", "10.22.114.213"]:
                    #     ssh.connect(hostname=ip, port=int(ssh_port), username=ssh_username, banner_timeout=30,
                    #                 password="Tianjian;123")
                    # else:
                    #     ssh.connect(hostname=ip, port=int(ssh_port), username=ssh_username, banner_timeout=30)
                    log.debug('Success connect server: {}@{}, port: {}'.format(ssh_username, cls.server_ip, ssh_port))
                    # 命令执行
                    _, cmd_output, cmd_stderr = ssh.exec_command(cmd, timeout=timeout)
                    if cmd_output:
                        # 当cmd_output有效时，获取返回错误码
                        # 增加缓冲区大小, 好像没有效果，先不加
                        # buffer_size = 1024  # 可以适当增加这个值
                        # output = b''
                        # while not cmd_output.channel.exit_status_ready():
                        #     all_data = cmd_output.read(buffer_size)
                        #     cmd_code = cmd_output.channel.recv_exit_status()
                        #     while all_data:
                        #         output += all_data
                        #         all_data = cmd_output.read(buffer_size)

                        output = cmd_output.read()
                        cmd_code = cmd_output.channel.recv_exit_status()
                        cmd_output = output.decode(errors='ignore')
                    if cmd_stderr:
                        cmd_stderr = cmd_stderr.read()
                    # 如果命令错误输出不为空，表明该指令执行失败，打印error信息
                    if isinstance(cmd_stderr, bytes):
                        cmd_stderr = cmd_stderr.decode().rstrip('\n')
                    if isinstance(cmd_output, str):
                        # 此处去除命令返回结果中最后一个换行符
                        cmd_output = cmd_output.rstrip('\n')
                    break
                except Exception as e:
                    log.exception('Found exception during execute command, exception stack info: {}'.format(e))
                    cmd_code = RtnStatusEnum.FAIL.value
                    cmd_output = ''
                    cmd_stderr = 'Found exception during execute command.'
                finally:
                    ssh.close()
            """
            from scripts.script_libs.common_operation import CommonOperation
            if print_steps:
                CommonOperation.concat_test_steps(f'{ssh_username}@{ip}端执行->[{cmd}]', level=level)
            # cmd = cls.choose_cli(cmd)
            cls.write_cmd(cmd)
            # # 首先打印cmd信息，以帮助定位
            # cls.__print_message(message='ssh host: {}@{}:{}, cmd: {}'.format(ssh_username, ip, port, cmd),
            #                     print_enable=print_enable)

            # 参数
            if ('scp' in cmd and '-o' in cmd and 'grep' not in cmd) or "esxe.py" in cmd:
                timeout = 5400

            current_pid = os.getpid()
            # log.debug(f"当前进程ID: {current_pid}")
            # log.debug(f"当前进程连接池: {cls.pool}")

            ssh_pool = cls.pool.get(f"{ip}-{ssh_username}-{current_pid}", None)
            retry_times = 3
            # 执行命令
            for i in range(retry_times):
                try:
                    # 创建连接池
                    if not ssh_pool:
                        # 密钥登录 + 自动信任新主机
                        ssh_pool = SSHConnectionPool(
                            host=ip,
                            port=int(ssh_port),
                            username=ssh_username,
                            password=ssh_password,
                            max_connections=15
                        )
                        cls.pool[f"{ip}-{ssh_username}-{current_pid}"] = ssh_pool
                except Exception as e:
                    log.error(e)
                    if RtnStatusEnum.SUCCESS.value != cls.check_ip_connect(ip, int(ssh_port), ssh_username, is_ping=True):
                        cmd_code = RtnStatusEnum.SUCCESS.value
                        log.info(f"连接失败,连接池构造失败")
                        break
                    continue

                if i > 0:
                    log.info(f"开始第{i}次重新执行：{cmd}")
                    time.sleep(i * 10)

                # 执行命令
                try:
                    conn = ssh_pool.get_connection()
                    cmd_code, cmd_output, cmd_stderr = ssh_pool.execute_command(conn, cmd, timeout)

                    # log.info(f"命令执行结果:{cmd_output}")

                    # 非关机、重启动作时归还conn到连接池
                    try:
                        if not cls.__check_ignore_release_conn_cmd(cmd):
                            ssh_pool.release_connection(conn)
                        else:
                            log.info(f"检测到重启动作,清空连接池")
                            ssh_pool.close_all()
                            ssh_pool = None
                            cls.pool[f"{ip}-{ssh_username}-{current_pid}"] = None

                    except Exception as e:
                        ssh_pool.close_conn(conn)
                        log.error(f"连接归还出错 {str(e)}")

                    break

                except Exception as e:

                    if cls.__check_ignore_release_conn_cmd(cmd):
                        if RtnStatusEnum.SUCCESS.value != cls.check_ip_connect(ip, int(ssh_port), ssh_username, is_ping=True):
                            cmd_code = RtnStatusEnum.SUCCESS.value
                            log.info(f"检测到重启动作,且连接失败,修改执行结果为：成功")
                            break

                    log.error(f"发生错误: {str(e)},开始连接测试 ...")
                    conn_flag = False
                    for j in range(8):
                        if RtnStatusEnum.SUCCESS.value == cls.check_ip_connect(ip, int(ssh_port), ssh_username, is_ping=True):
                            conn_flag = True
                            break
                        log.error(f"连接失败，等待{(j + 1) * (j + 1) * 10}秒后重试")
                        time.sleep((j + 1) * (j + 1) * 10)

                    if conn_flag:
                        ssh_pool.close_all()

                        # 补充命令卡死栈打印
                        check_cmd = f"ps -ef | grep '{cmd}' | grep -v grep"
                        _, out, err = cls.execute_command_with_error(check_cmd, ssh_ip=ip, timeout=10)
                        pids = re.findall(r"\S+\s+(\S+)\s+", out)
                        if pids:
                            pid = pids[0]
                            check_cmd = f"cat /proc/{pid}/stack"
                            _, out, err = cls.execute_command_with_error(check_cmd, ssh_ip=ip, timeout=10)
                            log.warning(f"check_cmd:{check_cmd},out:\n{out}, err:\n{err}")
                        continue
                    else:
                        log.error(f"连接失败,,清空连接池,命令执行失败")
                        ssh_pool.close_all()
                        ssh_pool = None
                        cls.pool[f"{ip}-{ssh_username}-{current_pid}"] = None
                        break

        try:
            if 'cli' in cmd:
                cls.__save_cmd_exec_time(cmd, cmd_code, cmd_output, cmd_stderr)
        except Exception as e:
            log.error(e)

        if RtnStatusEnum.SUCCESS.value != cmd_code and constants.SXE2CLI64 in cmd:
            cmd_code = cls.__check_cli_failure_output(cmd, cmd_code, cmd_output, cmd_stderr)

        if ((cmd_code == RtnStatusEnum.SUCCESS.value) and
                ((HostOsEnum.WINDOWS.value in host_os_client and
                  cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value) or
                 (HostOsEnum.WINDOWS.value in host_os_server and
                  cmd_execute_address == CmdExecuteAdressEnum.SERVER.value)) and not local_execute_flag):
            if shiled_error:
                cmd_stderr = ""
            else:
                # 不进行屏蔽
                pass
        if print_outputs:
            log.info_caller("rtn_code:{}, output:\n{}\nstderr:\n{}".format(cmd_code, cmd_output, cmd_stderr))
        return cmd_code, cmd_output, cmd_stderr

    @classmethod
    def concat_invoke_command(cls, vm_name: str, cmd: str, kvm_windows: bool = False) -> str:
        """
        author:      haibin.xu
        date:        2023-11-29 13:33:40
        description: 拼接Invoke-Command命令

        :param cmd: 在虚拟机侧执行的命令
        :param vm_name: 虚拟机name，与invoke_flag配合使用
        :return:
        """
        if not kvm_windows:
            if (("devcon" in cmd) or ("pnputil" in cmd) or ("New-NetRoute" in cmd)) and\
                    ("Unknown" not in cmd):
                pass
            else:
                if 'Windows' != cls.local_platform:
                    cmd = re.sub(r'([$"])', r'\\\1', cmd)
            if 'Windows' != cls.local_platform:
                return 'Invoke-Command -VMName {} -ScriptBlock {{{}}} -Credential \$credential'.format(vm_name, cmd)
            else:
                return 'Invoke-Command -VMName {} -ScriptBlock {{{}}} -Credential $credential'.format(vm_name, cmd)
        else:
            if (("devcon" in cmd) or ("pnputil" in cmd) or ("New-NetRoute" in cmd)) and \
                    ("Unknown" not in cmd):
                pass
            else:
                cmd = re.sub(r'\?{\$_.([^}]+)}', r'Where-Object \1', cmd)
                cmd = re.sub(r'(["])', r'\\\1', cmd)
            return 'ssh Administrator@{} \'{}\''.format(cls.kvm_localnet, cmd)

    @classmethod
    def concat_powershell_command(cls, cmd: str) -> str:
        """
        author:      haibin.xu
        date:        2023-11-29 13:33:40
        description: 拼接powershell命令

        :param cmd: 在虚拟机侧执行的命令
        :return:
        """
        return 'PowerShell -Command "& {{{}}}"'.format(cmd)

    @classmethod
    def execute_command_for_windows(cls, cmd, vm_ip: str = None,
                                    ssh_ip: str = None, ssh_port: str = None,
                                    ssh_username: str = 'Administrator', pwd: str = 'Perseus;1234',
                                    print_enable: bool = True, timeout: int = 600,
                                    print_steps: bool = True, print_outputs: bool = True,
                                    level: int=-2) -> tuple:
        """
        window qemu exec cmd function
        :param cmd:
        :param vm_name: 指定VM名称，若不为None，在VM机执行cmd；否则在物理机执行
        :param ssh_ip:
        :param ssh_port:
        :param ssh_username:
        :param pwd:
        :param print_enable:
        :param timeout:
        :return:
        """
        import winrm
        import datetime
        from winrm.exceptions import WinRMTransportError, WinRMOperationTimeoutError
        physical_passwd = pwd

        class Protocol(winrm.protocol.Protocol):
            def get_command_output(self, shell_id, command_id):
                """
                Get the Output of the given shell and command
                @param string shell_id: The shell id on the remote machine.
                 See #open_shell
                @param string command_id: The command id on the remote machine.
                 See #run_command
                #@return [Hash] Returns a Hash with a key :exitcode and :data.
                 Data is an Array of Hashes where the cooresponding key
                #   is either :stdout or :stderr.  The reason it is in an Array so so
                 we can get the output in the order it ocurrs on
                #   the console.
                """
                stdout_buffer, stderr_buffer = [], []
                command_done = False

                return_code = -1
                limited_seconds = self.exec_time_out
                start_time = datetime.datetime.now()
                while not command_done:
                    # print('get the response from windows...')
                    try:
                        stdout, stderr, return_code, command_done = self._raw_get_command_output(shell_id, command_id)
                        stdout_buffer.append(stdout)
                        stderr_buffer.append(stderr)
                    except WinRMOperationTimeoutError as e:
                        # this is an expected error when waiting for a long-running process, just silently retry
                        pass

                    end_time = datetime.datetime.now()
                    delta_time = end_time - start_time
                    total_seconds = delta_time.total_seconds()
                    if total_seconds > limited_seconds:
                        raise WinRMOperationTimeoutError()
                return b''.join(stdout_buffer), b''.join(stderr_buffer), return_code

        class Session(winrm.Session):
            # TODO implement context manager methods
            def __init__(self, target, auth, timeout, **kwargs):
                username, password = auth
                self.url = self._build_url(target, kwargs.get('transport', 'plaintext'))
                self.protocol = Protocol(self.url,
                                         username=username, password=password, **kwargs)
                setattr(self.protocol, 'exec_time_out', timeout)

        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            ssh_port = str(test_port)

        # 未指定ssh_ip/ssh_port，则需要根据cmd_execute_address获取ip, port
        if (ssh_ip is None) or (ssh_port is None):
            ssh_ip, _ = cls.__get_ip_port(CmdExecuteAdressEnum.CLI_DEFAULT.value)
            if (ssh_ip is None) or (ssh_port is None):
                return RtnStatusEnum.FAIL.value, '', 'Can not get valid ip and port.'
        for i in range(3):
            try:
                if vm_ip:
                    ssh_ip = vm_ip
                    pwd = "123456"
                print('pwd', pwd, cmd)
                s = Session(ssh_ip, auth=(ssh_username, pwd), timeout=timeout, transport='ntlm',
                            server_cert_validation='ignore')
                if "Invoke-Command" in cmd:
                    # cls.saved_session.append(s)
                    s_cmd = None
                    from scripts.script_libs.common_operation import CommonOperation
                    if isinstance(cmd, list) and (1 < len(cmd)):
                        # 交互界面执行的命令，ssh前缀只添加到cmd[0]前面
                        s_cmd = cmd[1:]
                        if print_steps:
                            CommonOperation.concat_test_steps(f'{ssh_username}@{ssh_ip}端执行->[{cmd}]', level=level)
                        # import re
                        # escaped_string = re.sub(r'([$"\'])', r'\\\1', cmd[0])
                        cmd = constants.SSH_PREFIX.format(ssh_username, ssh_port, ssh_ip, cmd[0])

                    else:
                        if print_steps:
                            CommonOperation.concat_test_steps(f'{ssh_username}@{ssh_ip}端执行->[{cmd}]', level=level)
                        # cls.__print_message(message='user:{} ip:{} port:{}, cmd: {}'.
                        #                     format(ssh_username, ssh_ip, ssh_port, cmd),
                        #                     print_enable=print_enable)
                        # import re
                        # escaped_string = re.sub(r'([$"\'])', r'\\\1', cmd)
                        cmd = constants.SSH_PREFIX.format(ssh_username, ssh_port, ssh_ip, cmd)
                    #   避免出現 系統上報System.Security問題，使用明文密码格式传输命令
                    if 'Windows' != cls.local_platform:  # 在Windows调试代码时无法使用sshpass
                        cmd = f"sshpass -p '{physical_passwd}' {cmd}"
                    cls.__print_message(message='user:{} ip:{} port:{}, cmd: {}'.format(
                        ssh_username, ssh_ip, ssh_port, cmd),
                        print_enable=print_enable)
                    rtn_code, rtn_out, rtn_err = cls.__execute_command(cmd=cmd, s_cmd=s_cmd,
                                                                       interactive_flag=False,
                                                                       timeout=timeout)
                    rtn_err = rtn_err.replace(
                        "\nAuthorized users only. All activities may be monitored and reported.", "")
                    rtn_err = rtn_err.replace("UnionTech OS Server 20 1050e", "")
                    rtn_err = rtn_err.replace("UOS Server 20 1060e", "")
                    rtn_err = rtn_err.replace("UOS Server 20 1070e", "")
                    # 若执行命令时存在Import-Clixml错误，执行以下命令
                    if "Import-Clixml : Key not valid for use in specified state." in rtn_err:
                        cmd = '$credential = Import-Clixml -Path "C:/Users/Administrator/sxetest/credential.xml"'
                        rtn_code, rtn_out, rtn_err = cls.__execute_command(cmd=cmd, s_cmd=None,
                                                                           interactive_flag=False,
                                                                           timeout=timeout)
                else:
                    # # 首先打印cmd信息，以帮助定位
                    # cls.__print_message(message='winrm host: {}@{}:{}, cmd: {}'.format(ssh_username,
                    #                                                                    ssh_ip, ssh_port, cmd),
                    #                     print_enable=print_enable)
                    #
                    import re
                    if "devcon" in cmd or "pnputil" in cmd or "New-NetRoute" in cmd:
                        pass
                    else:
                        # 单引号不转义
                        if 'Windows' != cls.local_platform:
                            cmd = re.sub(r'([$"])', r'\\\1', cmd)
                    cmd = constants.SSH_PREFIX.format(ssh_username, ssh_port, ssh_ip, cmd)
                    if 'Windows' != cls.local_platform:  # 在Windows调试代码时无法使用sshpass
                        cmd = f"sshpass -p '{pwd}' {cmd}"
                    cls.__print_message(message='user:{} ip:{} port:{}, cmd: {}'.format(
                        ssh_username, ssh_ip, ssh_port, cmd),

                        print_enable=print_enable)
                    rtn_code, rtn_out, rtn_err = cls.__execute_command(cmd=cmd, s_cmd=None,
                                                                       interactive_flag=False,
                                                                       timeout=timeout)
                    rtn_err = rtn_err.replace(
                        "\nAuthorized users only. All activities may be monitored and reported.", "")
                    rtn_err = rtn_err.replace("UnionTech OS Server 20 1050e", "")
                    rtn_err = rtn_err.replace("UOS Server 20 1060e", "")
                    rtn_err = rtn_err.replace("UOS Server 20 1070e", "")
                    # 若执行命令时存在Import-Clixml错误，执行以下命令
                    if "Import-Clixml : Key not valid for use in specified state." in rtn_err:
                        cmd = '$credential = Import-Clixml -Path "C:/Users/Administrator/sxetest/credential.xml'
                        rtn_code, rtn_out, rtn_err = cls.__execute_command(cmd=cmd, s_cmd=None,
                                                                           interactive_flag=False,
                                                                           timeout=timeout)
                    # r = s.run_cmd(cmd)
                    # print('r====', r)

                    # rtn_code = r.status_code
                    # # 返回结果添加rstrip()去除最后多余的换行符
                    # rtn_out = r.std_out.decode('gbk', "ignore")
                    # rtn_err = r.std_err.decode('gbk', "ignore")

                if '\n\r\n\r' in rtn_out or '\r\n\r\n' in rtn_out:
                    rtn_out = rtn_out.rstrip() + '\r\n'
                elif '\n\r' in rtn_out or '\r\n' in rtn_out:
                    rtn_out = rtn_out.rstrip()
                if rtn_code == RtnStatusEnum.SUCCESS.value:
                    rtn_err = ""
                if print_outputs:
                    log.info_caller(
                        "rtn_code:{}, output:\n{}\nstderr:\n{}".format(rtn_code, rtn_out, rtn_err))
                return rtn_code, rtn_out, rtn_err

            except Exception as e:
                print(e)
                log.debug(e)
        return RtnStatusEnum.FAIL.value, '', 'cmd not exec'

    @classmethod
    def execute_command_for_windows_vm(cls, cmd, ssh_ip: str = None, ssh_port: str = None,
                                       ssh_username: str = 'Administrator', pwd: str = 'Perseus;1234',
                                       print_enable: bool = True, timeout: int = 600,
                                       ssh_force: bool = False,
                                       print_steps: bool = True, print_outputs: bool = True,
                                       level: int=-2) -> tuple:
        """
        windows vm qemu exec cmd function
        :param cmd:
        :param ssh_ip:
        :param ssh_port:
        :param ssh_username:
        :param pwd:
        :param print_enable:
        :return:
        """
        import winrm
        import datetime
        from winrm.exceptions import WinRMTransportError, WinRMOperationTimeoutError

        class Protocol(winrm.protocol.Protocol):
            def get_command_output(self, shell_id, command_id):
                """
                Get the Output of the given shell and command
                @param string shell_id: The shell id on the remote machine.
                 See #open_shell
                @param string command_id: The command id on the remote machine.
                 See #run_command
                #@return [Hash] Returns a Hash with a key :exitcode and :data.
                 Data is an Array of Hashes where the cooresponding key
                #   is either :stdout or :stderr.  The reason it is in an Array so so
                 we can get the output in the order it ocurrs on
                #   the console.
                """
                stdout_buffer, stderr_buffer = [], []
                command_done = False

                return_code = -1
                limited_seconds = self.exec_time_out
                start_time = datetime.datetime.now()
                while not command_done:
                    # print('get the response from windows...')
                    try:
                        stdout, stderr, return_code, command_done = self._raw_get_command_output(shell_id, command_id)
                        stdout_buffer.append(stdout)
                        stderr_buffer.append(stderr)
                    except WinRMOperationTimeoutError as e:
                        # this is an expected error when waiting for a long-running process, just silently retry
                        pass

                    end_time = datetime.datetime.now()
                    delta_time = end_time - start_time
                    total_seconds = delta_time.total_seconds()
                    if total_seconds > limited_seconds:
                        raise WinRMOperationTimeoutError()
                return b''.join(stdout_buffer), b''.join(stderr_buffer), return_code

        class Session(winrm.Session):
            # TODO implement context manager methods
            def __init__(self, target, auth, timeout, **kwargs):
                username, password = auth
                self.url = self._build_url(target, kwargs.get('transport', 'plaintext'))
                self.protocol = Protocol(self.url,
                                         username=username, password=password, **kwargs)
                setattr(self.protocol, 'exec_time_out', timeout)

        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            ssh_port = str(test_port)

        # 未指定ssh_ip/ssh_port，则需要根据cmd_execute_address获取ip, port
        if (ssh_ip is None) or (ssh_port is None):
            ssh_ip, _ = cls.__get_ip_port(CmdExecuteAdressEnum.CLI_DEFAULT.value)
            if (ssh_ip is None) or (ssh_port is None):
                return RtnStatusEnum.FAIL.value, '', 'Can not get valid ip and port.'
        for i in range(3):
            try:
                if ssh_force:
                    s_cmd = None
                    from scripts.script_libs.common_operation import CommonOperation
                    if isinstance(cmd, list) and (1 < len(cmd)):
                        # 交互界面执行的命令，ssh前缀只添加到cmd[0]前面
                        s_cmd = cmd[1:]
                        if print_steps:
                            CommonOperation.concat_test_steps(f'{ssh_username}@{ssh_ip}端执行->[{cmd}]', level=level)
                        # cls.__print_message(message='user:{} ip:{} port:{}, cmd: {}'.format(
                        #     ssh_username, ssh_ip, ssh_port, cmd),
                        #     print_enable=print_enable)
                        cmd = constants.SSH_PREFIX.format(ssh_username, ssh_port, ssh_ip, cmd[0])
                    else:
                        if print_steps:
                            CommonOperation.concat_test_steps(f'{ssh_username}@{ssh_ip}端执行->[{cmd}]', level=level)
                        # cls.__print_message(message='user:{} ip:{} port:{}, cmd: {}'.
                        #                     format(ssh_username, ssh_ip, ssh_port, cmd),
                        #                     print_enable=print_enable)
                        cmd = constants.SSH_PREFIX.format(ssh_username, ssh_port, ssh_ip, cmd, cmd)
                    rtn_code, rtn_out, rtn_err = cls.__execute_command(cmd=cmd, s_cmd=s_cmd,
                                                                       interactive_flag=False,
                                                                       timeout=timeout)
                    rtn_err = rtn_err.replace(
                        "\nAuthorized users only. All activities may be monitored and reported.", "")
                    rtn_err = rtn_err.replace("UnionTech OS Server 20 1050e", "")
                    rtn_err = rtn_err.replace("UOS Server 20 1060e", "")
                    rtn_err = rtn_err.replace("UOS Server 20 1070e", "")
                else:
                    s = Session(ssh_ip, auth=(ssh_username, pwd), timeout=timeout, transport='ntlm')

                    # 首先打印cmd信息，以帮助定位
                    cls.__print_message(message='winrm host: {}@{}:{}, cmd: {}'.format(ssh_username,
                                                                                       ssh_ip, ssh_port, cmd),
                                        print_enable=print_enable)

                    r = s.run_ps(cmd)

                    rtn_code = r.status_code
                    # 返回结果添加rstrip()去除最后多余的换行符
                    rtn_out = r.std_out.decode('gbk', "ignore")
                    rtn_err = r.std_err.decode('gbk', "ignore")

                if '\n\r\n\r' in rtn_out or '\r\n\r\n' in rtn_out:
                    rtn_out = rtn_out.rstrip() + '\r\n'
                elif '\n\r' in rtn_out or '\r\n' in rtn_out:
                    rtn_out = rtn_out.rstrip()
                if print_outputs:
                    log.info_caller("rtn_code:{}, output:\n{}\nstderr:\n{}".format(rtn_code, rtn_out, rtn_err))
                return rtn_code, rtn_out, rtn_err

            except Exception as e:
                print('这有异常:', f'{e}')
                print('?')
                log.debug(e)
        return RtnStatusEnum.FAIL.value, '', 'cmd not exec'

    @classmethod
    def transport_file_with_paramiko(cls, local_path: str, remote_path: str, transport_type: str,
                                     cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
                                     ssh_ip: str = None, ssh_port: str = None, ssh_username: str = None) -> int:
        """
        author:      haibin.xu
        date:        2020-09-18 10:18:57
        description: 使用paramiko库在本地和远程之间传输文件
        :param local_path: 本地路径，必须为文件路径
        :param remote_path: 远程路径， 必须为文件路径
        :param transport_type: 传输类型，上传或下载
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :param ssh_ip:  指定 ssh 连接的 ip， 需与ssh_port同时定义，只定义其中一个，不起作用
        :param ssh_port:指定 ssh 连接的 port， 需与ssh_ip同时定义，只定义其中一个，不起作用
        :param ssh_username: 指定ssh连接的username，不指定时，使用root
        :return:     文件传输成功返回0，失败返回-1

        @changelog      2021-03-16 11:05:50  haibin.xu
                        1. 优化函数实现, 添加ssh_username参数
        """
        transport_flag = RtnStatusEnum.FAIL.value
        # 创建SSH对象
        ssh = paramiko.SSHClient()
        # 获取ssh要连接的ip, port
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            ssh_port = str(test_port)

        # 获取ssh要连接的ip, port
        if (ssh_ip is None) or (ssh_port is None):
            ip, _ = cls.__get_ip_port(cmd_execute_address)
            if (ip is None) or (ssh_port is None):
                return RtnStatusEnum.FAIL.value
        else:
            ip = ssh_ip
            port = ssh_port

        if ssh_username is None:
            ssh_username = cls.ssh_username

        # 连接服务器
        ssh.connect(hostname=ip, port=int(ssh_port), username=ssh_username, banner_timeout=300)
        # 获取sftp客户端
        sftp = ssh.open_sftp()
        try:
            if 'upload' == transport_type:
                sftp.put(local_path, remote_path)
            elif 'download' == transport_type:
                sftp.get(remote_path, local_path)
            transport_flag = RtnStatusEnum.SUCCESS.value
        except Exception as e:
            log.exception('Error transport file, Reason: {}.'.format(e))
        finally:
            ssh.close()

        return transport_flag

    @classmethod
    def execute_windows_invoke_command(
            cls, cmd: (str, list), cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
            win_vm_ip: str = None, timeout: int = 90, test_times: int = 3) -> tuple:
        """
        author:      haibin.xu
        date:        2022-04-21 10:22:46
        description:    执行给定次数的给定命令，并检查返回状态和结果
        :param cmd:     执行的命令字符串
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :param win_vm_ip: 虚拟机管理ip
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
        rtn_code, cmd_stdout, cmd_stderr = cls.execute_command_multi_times(
            cmd=cmd, cmd_execute_address=cmd_execute_address, timeout=timeout, test_times=test_times)
        if RtnStatusEnum.SUCCESS.value != rtn_code:
            log.error(f'命令: {cmd}, 多次执行均失败，\ncmd_code: {rtn_code}\ncmd_stdout: {cmd_stdout}\n'
                      f'cmd_stderr: {cmd_stderr}')
            if 'Invoke-Command' in cmd and win_vm_ip is not None:
                log.info(f'当前命令为Incoke-Command格式命令，解析出其虚拟内部直接执行的命令，在虚拟机测直接执行')
                match_list = re.findall(r'-ScriptBlock \{(.*)} -Credential', cmd)
                if match_list:
                    raw_cmd = match_list[0]
                    log.info('虚拟内部直接执行命令：{}'.format(raw_cmd))
                    rtn_code, cmd_stdout, cmd_stderr = cls.execute_command_multi_times(
                        cmd=raw_cmd, timeout=timeout, test_times=test_times, win_vm_ip=win_vm_ip)
                    if RtnStatusEnum.SUCCESS.value != rtn_code:
                        log.error(f'命令: {raw_cmd}, 多次执行均失败，\ncmd_code: {rtn_code}\ncmd_stdout: {cmd_stdout}\n'
                                  f'cmd_stderr: {cmd_stderr}')
                    else:
                        log.info(f'命令: {raw_cmd}, 执行成功：\ncmd_code: {rtn_code}\ncmd_stdout:\n{cmd_stdout}\n'
                                 f'cmd_stderr:\n{cmd_stderr}\n')
        else:
            log.info(f'命令: {cmd}, 执行成功：\ncmd_code: {rtn_code}\ncmd_stdout:\n{cmd_stdout}\n'
                     f'cmd_stderr:\n{cmd_stderr}\n')

        return rtn_code, cmd_stdout, cmd_stderr

    @classmethod
    def execute_command_multi_times(
            cls, cmd: (str, list), cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
            local_execute_flag: bool = False, ssh_ip: str = None, ssh_port: str = None, win_vm_ip: str = None,
            interactive_flag: bool = False, ssh_username: str = None, timeout: int = 1800, test_times: int = 5,
            sleep_time: int = 5, host_os_server: str = None, host_os_client: str = None,
            script_object: bool = False) -> tuple:
        """
        author:      haibin.xu
        date:        2022-04-21 10:22:46
        description:    执行给定次数的给定命令，并检查返回状态和结果
        :param cmd:     执行的命令字符串
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :param local_execute_flag: 判定是否在本地主机执行命令，True表示在本地执行，False表示在远程执行
        :param ssh_ip:  指定 ssh 连接的 ip， 需与ssh_port同时定义，只定义其中一个，不起作用，同时local_execute_flag需为False
        :param ssh_port:指定 ssh 连接的 port， 需与ssh_ip同时定义，只定义其中一个，不起作用，同时local_execute_flag需为False
        :param interactive_flag: 交互命令执行标志位，默认为False，为True时，cmd参数必须为list类型
        :param ssh_username: 指定ssh连接的username，不指定时，使用root
        :param timeout  单独指令执行时常限制
        :param exit_flag  耗尽重试次数是否退出，默认退出当前脚本及测试框架
        :return:        返回命令执行状态和输出结果, 为三元素元组 cmd_code, cmd_output, cmd_stderr
                        cmd_code    当执行错误时返回-1, 执行成功时为0
                                    执行错误, 指的是远程执行cmd所遇到的"技术错误", 比如连接丢失, 参数不合法
                                    这里不会去管 "业务逻辑错误/语义错误",
                                    比如试图删掉不存在的VD, 此时 storcli 会返回 Status=Failure,
                                    但是该命令从技术上是执行成功了的, 于是返回cmd_code=0
                        cmd_output  shell 执行的"标准输出" stdout
                        cmd_stderr  shell 执行的"标准错误" stderr
        """
        rtn_code = RtnStatusEnum.FAIL.value
        cmd_stdout = None
        cmd_stderr = None
        max_test_times = test_times

        while test_times != 0:
            # if 'Invoke-Command' not in cmd:
            cmd_code, cmd_stdout, cmd_stderr = cls.execute_command_with_error(
                cmd=cmd, cmd_execute_address=cmd_execute_address, local_execute_flag=local_execute_flag,
                ssh_ip=ssh_ip, ssh_port=ssh_port, interactive_flag=interactive_flag, ssh_username=ssh_username,
                timeout=timeout, win_vm_ip=win_vm_ip, host_os_client=host_os_client, script_object=script_object,
                host_os_server=host_os_server)
            # else:
            #     if "'" in cmd:
            #         cmd = cmd.replace("'", '"')
            #     cmd_ps = """echo '$output=%s\r\necho $?\r\necho $output' > %sabc.ps1""" % (
            #         cmd, constants.WINDOWS_FILE_PATH_ROOT)
            #     _, _, _ = cls.execute_command_with_error(cmd_ps, cmd_execute_address=cmd_execute_address,
            #                                              local_execute_flag=local_execute_flag,
            #                                              ssh_ip=ssh_ip, ssh_port=ssh_port,
            #                                              interactive_flag=interactive_flag,
            #                                              ssh_username=ssh_username,
            #                                              timeout=timeout, win_vm_ip=win_vm_ip,
            #                                              host_os_client=host_os_client,
            #                                              host_os_server=host_os_server)
            #     cmd_code, cmd_outputs, cmd_err = cls.execute_command_with_error(
            #         'abc.ps1', cmd_execute_address=cmd_execute_address, local_execute_flag=local_execute_flag,
            #         ssh_ip=ssh_ip, ssh_port=ssh_port, interactive_flag=interactive_flag,
            #         ssh_username=ssh_username, timeout=timeout, win_vm_ip=win_vm_ip, host_os_client=host_os_client,
            #         host_os_server=host_os_server)
            #     print('===========', cmd_code)
            #     print('=====0======', cmd_outputs)
            #     print('=====1======', cmd_err)
            #     if 'True' in cmd_outputs:
            #         cmd_code = 0
            #     else:
            #         cmd_code = -1
            #     if int(cmd_code) == RtnStatusEnum.SUCCESS.value:
            #         cmd_stdout, cmd_stderr = cmd_outputs.replace('True', '').strip(), ''
            #     else:
            #         # 向宇建议命令返错时，返回的信息同时赋值输出、错误中
            #         cmd_stdout, cmd_stderr = cmd_outputs.replace('False', '').strip(), \
            #                                  cmd_outputs.replace('False', '').strip()
            if RtnStatusEnum.SUCCESS.value != cmd_code:
                if test_times > 1:
                    log.error(f'命令: {cmd}, 执行失败，需要再次执行：\ncmd_code: {cmd_code}\ncmd_stdout: {cmd_stdout}\n'
                              f'cmd_stderr: {cmd_stderr}')
                else:
                    log.error(f'命令: {cmd}, 执行失败，不再尝试执行：\ncmd_code: {cmd_code}\ncmd_stdout: {cmd_stdout}\n'
                              f'cmd_stderr: {cmd_stderr}')
                # 20231216：windows Invoke命令，执行失败后尝试清理命令session。规避连续失败的问题
                # if "Invoke-Command" in cmd:
                #     # TODO
                #     # 1. cmd --> 写文件$output=cmd\r\n echo $output保存abc.ps1, 路径在sxetest下
                #     # 2. 执行脚本 abc.ps1
                #     for s in cls.saved_session:
                #         s.protocol.transport.close_session()
                #     cls.saved_session.clear()
                test_times -= 1
                # # winrm服务默认在异常后，等待120s重启服务，因此此处等待120 + 2s, 再次重试
                # if "Invoke-Command" in cmd:
                #     sleep_time = 122
                #     log.error(f"Invoke-Command命令执行失败，等待{sleep_time}s后重试")
                time.sleep(sleep_time)
                # 若重试到最大次数一半时仍失败，尝试kill power、ssh进程，然后继续重试
                if test_times == (int(max_test_times)//2) and test_times:
                    log.info("清除残留ssh进程")
                    if host_os_server == "windows":
                        kill_cmd = f"taskkill /t /f /FI \"IMAGENAME eq ssh*\""
                        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=kill_cmd, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                            ssh_username="Administrator", ssh_ip=ssh_ip, win_vm_ip=win_vm_ip, timeout=90)
                        if status:
                            log.warning("清除残留ssh进程失败！")
                    if host_os_client == "windows":
                        log.info("清除残留powershell进程")
                        kill_cmd = f"taskkill /t /f /FI \"IMAGENAME eq powershell*\""
                        status, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=kill_cmd, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                            ssh_username="Administrator", ssh_ip=ssh_ip, win_vm_ip=win_vm_ip, timeout=90)
                        if status:
                            log.warning("清除残留powershell进程失败！")
                continue
            # 如果一直有成功的invoke-command命令投递，saved_session会一直追加，需要及时清理
            if cls.saved_session:
                cls.saved_session.clear()
            rtn_code = RtnStatusEnum.SUCCESS.value
            break
        # # 若在windows执行Invoke-Command命令时，重试次数耗尽仍失败
        # if test_times == 0 and "Invoke-Command" in cmd and \
        #         ((cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and
        #           HostOsEnum.WINDOWS.value in host_os_server) or
        #          (cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and
        #           HostOsEnum.WINDOWS.value in host_os_client)) and exit_flag:
        #     log.error(f'！！！！！ 命令: {cmd}, 重试{max_test_times}轮仍失败，为避免长时间阻塞，测试即将停止！！！！！')
        #     log.error(f'！！！！！ 请检查环境中winrm配置、ps3server pywinrm版本0.4.3，并重启测试环境后重试！！！！！')
        #     # 配置测试框架停止测试
        #     ESAT_DIRETCORY = os.path.dirname(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
        #     SCRIPTS_DIRECTORY = os.path.join(ESAT_DIRETCORY, 'scripts')
        #     scripts_directory = CommandOperation.format_linux_path_sep(SCRIPTS_DIRECTORY)
        #     log.info('scripts common directory: {}'.format(scripts_directory))
        #     exit_file = "{}/exit_test.txt".format(scripts_directory)
        #     cmd = f"echo 'exit' > {exit_file}"
        #     exit_cmd_code, exit_cmd_stdout, exit_cmd_stderr = \
        #         cls.execute_command_with_error(cmd=cmd, local_execute_flag=True)
        #     # 退出当前脚本的执行s
        #     exit(1)

        return rtn_code, cmd_stdout, cmd_stderr

    @classmethod
    def execute_command_with_error(cls, cmd: (str, list),
                                   cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
                                   local_execute_flag: bool = False, ssh_ip: str = None, ssh_port: str = None,
                                   interactive_flag: bool = False, ssh_username: str = None, timeout: int = 1800,
                                   print_enable: bool = True,
                                   host_os_server: str = None, host_os_client: str = None,
                                   win_vm_ip: str = None, script_object: bool = False,
                                   print_steps: bool = True, print_outputs: bool = True,
                                   level: int=-2, setting_iperf_flag: bool = True) -> tuple:
        """
        author:         haibin.xu
        date:           2020.07.06
        description:    执行给定的命令，并检查返回状态和结果
        :param cmd:     执行的命令字符串
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :param local_execute_flag: 判定是否在本地主机执行命令，True表示在本地执行，False表示在远程执行
        :param ssh_ip:  指定 ssh 连接的 ip， 需与ssh_port同时定义，只定义其中一个，不起作用，同时local_execute_flag需为False
        :param ssh_port:指定 ssh 连接的 port， 需与ssh_ip同时定义，只定义其中一个，不起作用，同时local_execute_flag需为False
        :param ssh_username: 指定ssh连接的username，不指定时，使用root
        :param script_object: 执行对象为脚本或框架，如果执行对象为脚本，则置为True，否则置为False
        :param print_enable: 是否打印log
        :param setting_iperf_flag: 是否需要设置函数中的内容重新生成port
        :return:        返回命令执行状态和输出结果, 为三元素元组 cmd_code, cmd_output, cmd_stderr
                        cmd_code    当执行错误时返回-1, 执行成功时为0
                                    执行错误, 指的是远程执行cmd所遇到的"技术错误", 比如连接丢失, 参数不合法
                                    这里不会去管 "业务逻辑错误/语义错误",
                                    比如试图删掉不存在的VD, 此时 storcli 会返回 Status=Failure,
                                    但是该命令从技术上是执行成功了的, 于是返回cmd_code=0
                        cmd_output  shell 执行的"标准输出" stdout
                        cmd_stderr  shell 执行的"标准错误" stderr
        @changelog      2021-06-07 20:33:35  haibin.xu
                        1. 优化函数实现, 增加print_enable参数
                        2021-08-16          sunql
                        1、增加cli命令 time执行时间获取
        """
        virtual_system = CommandLineArgsParse.get_host_os()
        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            ssh_port = str(test_port)

        cli_pattern = "^cli$"
        if not host_os_server or not host_os_client:
            from scripts.script_libs.common_operation import CommonOperation
            host_os_server, host_os_client = CommonOperation.get_nic_os()
        if setting_iperf_flag:
            if ("iperf -" in cmd or "iperf3 -" in cmd) and "iperf -v" not in cmd and "iperf3 -v" not in cmd:
                """
                多对一拓扑存在冲突场景	控制变量	计算公式(vm为jenkins的测试节点编号)
                iperf	port	port = 20000 + vm%1000 + 传递port%100
                iperf3	port	port = 30000 + vm%1000 + 传递port%100
                """
                cur_path = os.path.abspath(os.path.dirname(__file__))
                num_list = re.findall(r'm(\d+)', cur_path)
                if num_list and num_list[0].isdigit():
                    vm = int(num_list[0])
                else:
                    vm = 999
                port_list = re.findall(r'-p (\d+)', cmd)
                if port_list and port_list[0].isdigit():
                    port_offset = int(port_list[0])
                else:
                    port_offset = 0
                if "iperf3" in cmd:
                    use_port = 30000 + vm % 1000 + port_offset % 100
                    log.info("iperf3:vm:{}, port_offset:{}, use_port：{}".format(vm, port_offset, use_port))
                    if port_offset:
                        cmd = cmd.replace("-p {}".format(port_offset), "-p {}".format(use_port))
                    else:
                        cmd = cmd.replace("iperf3".format(port_offset), "iperf3 -p {}".format(use_port))
                else:
                    use_port = 20000 + vm % 1000 + port_offset % 100
                    log.info("iperf:vm:{}, port_offset:{}, use_port：{}".format(vm, port_offset, use_port))
                    if port_offset:
                        cmd = cmd.replace("-p {}".format(port_offset), "-p {}".format(use_port))
                    else:
                        cmd = cmd.replace("iperf".format(port_offset), "iperf -p {}".format(use_port))

        # # client-发包仪:跳过
        # if cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
        #     from scripts.script_libs.common_operation import CommonOperation
        #     server_drv_name, client_drv_name = CommonOperation.get_nic_driver_name()
        #     server_ip, client_ip = CommonOperation.get_nic_logical_ip()
        #     if 'renix' in client_drv_name:
        #         client_is_renix = True
        #     else:
        #         client_is_renix = False
        #     if client_is_renix:
        #         log.warning(f'{cmd_execute_address}:{client_ip}为发包仪，跳过[{cmd}]执行')
        #         cmd_code = RtnStatusEnum.FAIL.value
        #         cmd_output = ''
        #         cmd_stderr = ''
        #         return cmd_code, cmd_output, cmd_stderr

        # log.info("host_os_server:{}, host_os_client:{}, local_execute_flag:{}"
        #          .format(host_os_server, host_os_client, local_execute_flag))
        if ((
                (HostOsEnum.WINDOWS.value in host_os_client and
                 cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value) or
                (HostOsEnum.WINDOWS.value in host_os_server and
                 cmd_execute_address == CmdExecuteAdressEnum.SERVER.value)
        ) or win_vm_ip) and not local_execute_flag:

            # 新增判断，如果虚拟为linux,不进去
            if virtual_system != "windows" and (win_vm_ip is not None or ssh_ip is not None) and script_object:
                pass
            else:
                # cmd = cmd.replace("cli", f"{constants.SXE2CLI64_WIN}") \
                #     if "cli " in cmd and constants.SXE2CLI64_WIN not in cmd else cmd
                if ssh_ip is not None and script_object:
                    cmd = cmd.replace(f"{constants.IFCONFIG}", f"{constants.IPCONFIG}") \
                        if f"{constants.IFCONFIG}" in cmd else cmd
                check_host_ip = ssh_ip
                if check_host_ip is None:
                    check_host_ip, _ = cls.__get_ip_port(cmd_execute_address)
                return cls.execute_command_for_windows(cmd=cmd, vm_ip=win_vm_ip, ssh_ip=check_host_ip,
                                                       ssh_port=ssh_port, timeout=timeout)

        s_cmd = None
        # 如果是cli命令则增加time获取
        if type(cmd) == str:
            cmd = cmd.lstrip()
            # if cmd.startswith(constants.SXE2CLI64):
            #     cmd = 'time ' + cmd
        # cmd 处理
        if ('"' in cmd and cmd.count('"') != cmd.count('\\\"')) and ("'" in cmd):
            log.error("""cmd: {}, Can not contain both " and ' .""".format(cmd))
            # return RtnStatusEnum.FAIL.value, '', 'Command Can not contain both \" and \'.'
        if ('$' in cmd) and ('awk' in cmd) and ('Linux' == cls.local_platform):
            cmd = cmd.replace('$', r'\$')

        if local_execute_flag:
            # 本地执行，不需要指定ip, port
            ip = None
            ssh_port = None
        # 获取ssh要连接的ip, port
        elif (ssh_ip is None) or (ssh_port is None):
            # 非本地执行，且未指定ssh_ip/ssh_port，则需要根据cmd_execute_address获取ip, port
            ip, resolved_port = cls.__get_ip_port(cmd_execute_address)
            if ip is None:
                return RtnStatusEnum.FAIL.value, '', 'Can not get valid ip and port.'
            # 已由命令行 --tp 显式指定端口时保持该端口，否则使用配置的默认端口
            if ssh_port is None:
                ssh_port = str(resolved_port)
        else:
            # 非本地执行，但指定了ssh_ip，ssh_port，则ip, port 使用指定的ssh_ip，ssh_port
            ip = ssh_ip

        if ssh_username is None:
            ssh_username = cls.ssh_username

        # 如果不在本地执行，则命令前需添加ssh前缀
        if not cls.__execute_local_command_enabled(ip, local_execute_flag):
            from scripts.script_libs.common_operation import CommonOperation
            if interactive_flag and isinstance(cmd, list) and (1 < len(cmd)):
                # 交互界面执行的命令，ssh前缀只添加到cmd[0]前面
                s_cmd = cmd[1:]
                if print_steps:
                    CommonOperation.concat_test_steps(f"{ssh_username}@{ip}端执行->[{cmd}]", level=level)
                        # CommonOperation.concat_test_steps(f"{PURPLE}{ssh_username}@{ip}端执行->[{cmd}]{RESET}", level=level)
                # cls.__print_message(message='user:{} ip:{} port:{}, cmd: {}'.format(ssh_username, ip, port, cmd),
                #                     print_enable=print_enable)
                cmd = constants.SSH_PREFIX.format(ssh_username, ssh_port, ip, cmd[0])
            else:
                if print_steps:
                    CommonOperation.concat_test_steps(f'{ssh_username}@{ip}端执行>[{cmd}]', level=level)
                    # CommonOperation.concat_test_steps(f'{PURPLE}{ssh_username}@{ip}端执行>[{cmd}]{RESET}', level=level)
                # cls.__print_message(message='user:{} ip:{} port:{}, cmd: {}'.format(ssh_username, ip, port, cmd),
                #                     print_enable=print_enable)
                cmd = constants.SSH_PREFIX.format(ssh_username, ssh_port, ip, cmd)

        else:
            cls.__print_message(message='execute in local, {}cmd: {}'.format('\033[35m', cmd),
                                print_enable=print_enable)

        # 执行命令并获取返回结果
        cmd_code, cmd_output, cmd_stderr = cls.__execute_command(cmd=cmd, s_cmd=s_cmd,
                                                                 interactive_flag=interactive_flag, timeout=timeout)

        # 处理命令执行time
        # cls.__save_cmd_exec_time(cmd, cmd_code, cmd_output, cmd_stderr)
        # openeuler os执行命令时会打印\nAuthorized users only. All activities may be monitored and reported.，这里删除
        cmd_stderr = cmd_stderr.replace("\nAuthorized users only. All activities may be monitored and reported.", "")
        # UnionTech os执行命令时会打印UnionTech OS Server 20 1050e，这里删除
        cmd_stderr = cmd_stderr.replace("UnionTech OS Server 20 1050e", "")
        cmd_stderr = cmd_stderr.replace("UOS Server 20 1060e", "")
        cmd_stderr = cmd_stderr.replace("UOS Server 20 1070e", "")
        if ((cmd_code == RtnStatusEnum.SUCCESS.value) and
                ((HostOsEnum.WINDOWS.value in host_os_client and
                  cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value) or
                 (HostOsEnum.WINDOWS.value in host_os_server and
                  cmd_execute_address == CmdExecuteAdressEnum.SERVER.value)) and not local_execute_flag):
            cmd_stderr = ""

        if print_outputs:
            log.info_caller('Cmd code: {}\nCmd Stdout:\n{}\nCmd Stderr:\n{}'.format(
                cmd_code, cmd_output, cmd_stderr), level=level+1)

        return cmd_code, cmd_output, cmd_stderr

    # 2020.10.21 该方法以后尽量不用，使用execute_command_with_error替换
    @classmethod
    def execute_command(cls, cmd: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> tuple:
        """
        author:         haibin.xu
        date:           2020.08.31
        description:    封装execute_command_with_error，差异是只返回 cmd_code, cmd_output
        :param cmd:     执行的命令字符串
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return:        返回命令执行状态和输出结果, 为二元素元组 cmd_code, cmd_output
                        cmd_code    当执行错误时返回-1, 执行成功时为0
                                    执行错误, 指的是远程执行cmd所遇到的"技术错误", 比如连接丢失, 参数不合法
                                    这里不会去管 "业务逻辑错误/语义错误",
                                    比如试图删掉不存在的VD, 此时 storcli 会返回 Status=Failure,
                                    但是该命令从技术上是执行成功了的, 于是返回cmd_code=0
                        cmd_output  shell 执行的"标准输出" stdout
        """
        # 调用execute_command_with_error
        cmd_code, cmd_out, _ = cls.execute_command_with_error(cmd, cmd_execute_address)

        return cmd_code, cmd_out

    @classmethod
    def execute_command_interactive(cls, cmd: str, timeout: int = 10, verbose: bool = False,
                                    cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
                                    local_execute_flag: bool = False, ssh_ip: str = None,
                                    ssh_port: str = None) -> Generator:
        """
        author:         cheng.peng, haibin.xu
        date:           2020.08.31
        description:    执行给定的命令，并"实时的"返回命令的 stdout 和 stderr 输出,
                        但是不返回成功失败, 测试者需要拿到 stdout 和 stderr 后自己解释
                        usage:
                            exe = CommandOperation.execute_command_interactive
                            for type_, line in exe(cmd='ping 127.0.0.1 -c 5', host_ip=host_ip,
                                timeout=10, verbose=True): print(f'{type_}: {line!r}')
                            # >>> INFO    : Connecting server: 10.2.16.120
                            # >>> INFO    : Connected to: 10.2.16.120 (0.16 seconds)
                            # >>> INFO    : Prepare running shell cmd `ping 127.0.0.1 -c 5`
                            # >>> stdout 'PING 127.0.0.1 (127.0.0.1) 56(84) bytes of data.\n'
                            # >>> stdout '64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=0.087 ms\n'
                            # >>> stdout '64 bytes from 127.0.0.1: icmp_seq=2 ttl=64 time=0.036 ms\n'
                            # >>> ...具体的执行输出
                            # >>> stdout 'rtt min/avg/max/mdev = 0.029/0.145/0.543/0.200 ms\n'
                            # >>> INFO    : running shell cmd done `ping 127.0.0.1 -c 5`
                            # >>> INFO    : excution: 4.33 seconds, total: 4.49 seconds
                        usage2:
                            cmd = 'echo -e "123"; echo -e "456" 1>&2'  # 其余都跟usage1 相同
                            # >>> stdout: '123\n'
                            # >>> stderr: '456\n'   # 注意这里显示输出到stderr
        :param cmd:      执行的命令字符串
        :param timeout:  默认超时10秒, 对于长时间测试, 应设置较大的超时时间
        :param verbose:  设为True会显示更详尽的日志
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :param local_execute_flag: 判定是否在本地主机执行命令，True表示在本地执行，False表示在远程执行
        :param ssh_ip:  指定 ssh 连接的 ip， 需与ssh_port同时定义，只定义其中一个，不起作用，同时local_execute_flag需为False
        :param ssh_port:指定 ssh 连接的 port， 需与ssh_ip同时定义，只定义其中一个，不起作用，同时local_execute_flag需为False
        :return:         None

        """
        ssh = None

        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            ssh_port = str(test_port)

        # 原为使用者指定 ip port username, 改成从公共库取得这三元素
        username = cls.ssh_username
        cls.__set_ip_parameters()
        if (ssh_ip is None) or (ssh_port is None):
            host_ip, _ = cls.__get_ip_port(cmd_execute_address)
            if (host_ip is None) or (ssh_port is None):
                return RtnStatusEnum.FAIL.value, '', 'Can not get valid ip and port.'
        else:
            host_ip = ssh_ip

        start_time = time.time()
        if not cls.__execute_local_command_enabled(host_ip, local_execute_flag):
            ssh = paramiko.SSHClient()
            # 允许连接不在know_hosts文件中的主机，否则可能报错：paramiko.ssh_exception.SSHException:
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if verbose:
                log.info('Connecting server: {}'.format(cls.server_ip))
            ssh.connect(hostname=host_ip, port=ssh_port, username=username, timeout=timeout)  # 连接服务器
            connect_time = time.time()
            if verbose:
                log.info('Connected to: {} ({:.2f} seconds)'.format(cls.server_ip, connect_time - start_time))
                log.info('Prepare running shell cmd `{}`'.format(cmd))
            _, cmd_stdout, cmd_stderr = ssh.exec_command(cmd, timeout=timeout)
            cmd_stdout = cmd_stdout.read().decode()
            cmd_stderr = cmd_stderr.read().decode()
        else:
            # 如果在本地执行，连接时间置为0，直接执行代码
            connect_time = 0
            log.info('No need to connect server, in local host, execute cmd: {}'.format(cmd))
            _, cmd_stdout, cmd_stderr = cls.__execute_command(cmd, timeout=timeout)

        try:
            for line in iter(cmd_stdout.readline, ''):  # 实时显示出 stdout, 不使用 iter 会导致执行完了一并显示
                yield 'stdout', line
            for line in iter(cmd_stderr.readline, ''):
                yield 'stderr', line
        except Exception as e:
            # 这里如果超时, 使用了全局 Exception 去拦截, 因为socket.timeout在python2/3的类型是不确定的,
            # 在python2是IOError, 在python3是OSError, 首先都拦下来, 但只处理相关于socket.timeout的异常, 剩下的异常再抛出
            if type(e) == socket.timeout:
                log.error('execute_command_interactive: socket.timeout on {} executing `{}`'.format(host_ip, cmd))
            else:
                raise e
        finally:
            if ssh is not None:
                ssh.close()
        execution_time = time.time()
        if verbose:
            log.info('running cmd done `{}`'.format(cmd))
            log.info('execution: {:.2f} seconds, total: {:.2f} seconds'.format(execution_time - connect_time,
                                                                               execution_time - start_time))

    @classmethod
    def __get_ip_port(cls, cmd_execute_address: str) -> tuple:
        """
        author:      haibin.xu
        date:        2020-10-17 16:57:51
        description: 根据cmd_execute_address参数值从host_ip, host_default_port, host_port, soc_ip, soc_default_port,
                     soc_port类变量中挑选获取ssh连接的ip、port。
        :param cmd_execute_address: 该值从CmdExecuteAdressEnum中挑选。枚举值具体映射如下：
                     1. cmd_execute_address 为HOST_DEFAULT时，获取 host_ip, host_default_port
                     2. cmd_execute_address 为HOST_NODE时，获取 host_ip, host_port
                     3. cmd_execute_address 为SOC_DEFAULT时，获取 soc_ip, soc_default_port
                     4. cmd_execute_address 为SOC_NODE时，获取 soc_ip, soc_port
        :return:     返回所需要的 ip, port
        """
        cls.__set_ip_parameters()
        rtn_ip = None
        rtn_port = None
        soc_flag = re.match(constants.PATTERN_IP, cls.client_ip)
        host_flag = re.match(constants.PATTERN_IP, cls.server_ip)
        soc_node_flag = re.match(constants.PATTERN_IP, cls.client_node_ip)
        host_node_flag = re.match(constants.PATTERN_IP, cls.server_node_ip)

        if CmdExecuteAdressEnum.CLI_DEFAULT.value == cmd_execute_address:
            if (TestObjectEnum.EXPANDER.value == cls.test_object) and (TestEntryEnum.SOC.value == cls.test_entry) \
                    and (soc_flag):
                rtn_ip = cls.client_ip
                rtn_port = cls.client_port
            elif (TestEntryEnum.HOST.value == cls.test_entry) and (host_node_flag):
                rtn_ip = cls.server_node_ip
                rtn_port = cls.server_default_port
                if TestObjectEnum.PCIE_SWITCH.value == constants.test_obj:
                    rtn_port = cls.server_port
            elif (TestEntryEnum.SOC.value == cls.test_entry) and (soc_node_flag):
                rtn_ip = cls.client_node_ip
                rtn_port = cls.client_default_port
            elif (cls.test_entry in [TestEntryEnum.SINGLE_MODE.value,
                                     TestEntryEnum.DPDK_MODE.value,
                                     TestEntryEnum.DPDK_AUTO_MODE.value,
                                     TestEntryEnum.VF_KEEP_MODE.value]) and (host_node_flag):
                rtn_ip = cls.server_node_ip
                rtn_port = cls.server_default_port
            else:
                log.error('Not found valid test entry, can not make sure cli execute address.')
        elif CmdExecuteAdressEnum.SERVER.value == cmd_execute_address:
            # 如果是在host 宿主机下执行命令，此时需要获取host ip, default port
            if host_flag:
                rtn_ip = cls.server_ip
                rtn_port = cls.server_default_port
            else:
                log.error('Not found valid host ip when execute command in host address, Please config it.')
        elif CmdExecuteAdressEnum.SERVER_NODE.value == cmd_execute_address:
            # 如果是在host节点下执行命令，此时需要获取host ip, node port
            if host_node_flag:
                rtn_ip = cls.server_node_ip
                rtn_port = cls.server_default_port
                if TestObjectEnum.PCIE_SWITCH.value == constants.test_obj:
                    rtn_port = cls.server_port
            else:
                log.error('Not found host ip when execute command in host node address, Please config it.')
        elif CmdExecuteAdressEnum.CLIENT.value == cmd_execute_address:
            # 如果是在soc 宿主机下执行命令，此时需要获取soc ip, default port
            if soc_flag:
                rtn_ip = cls.client_ip
                rtn_port = cls.client_default_port
            else:
                log.error('Not found valid soc ip when execute command in soc address, Please config it.')
        elif CmdExecuteAdressEnum.CLIENT_NODE.value == cmd_execute_address:
            # 如果是在soc节点下执行命令，此时需要获取soc node ip, node port
            if soc_node_flag:
                rtn_ip = cls.client_node_ip
                rtn_port = cls.client_default_port
            else:
                log.error('Not found valid soc ip when execute command in soc node address, Please config it.')
        else:
            log.error('No found any one of soc and host address information. !!!')

        return rtn_ip, rtn_port

    @classmethod
    def __set_ip_parameters(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-03-08 10:01:13
        description: 设置host ip, host node ip, ioc ip, ioc node ip参数

        :return:     None
        """
        # 获取logical ip
        cls.server_ip, cls.client_ip = cls.get_logical_ip_form_config()
        # 获取host node ip
        cls.server_node_ip = constants.SERVER_NODE_IP
        # 获取soc node ip
        cls.client_node_ip = constants.CLIENT_NODE_IP

        # cls.compile_object = constants.COMPILE_OBJECT
        cls.test_entry = constants.TEST_ENTRY
        cls.test_object = constants.test_obj

        # 若命令行指定了非默认 SSH 端口，同步到默认端口，使后续所有命令执行地址都能使用该端口
        # 命令行 --sp/--cp 显式指定了非默认端口时，同步到默认端口，使后续所有命令执行地址都能使用该端口
        if cls.server_port and int(cls.server_port) != cls.server_default_port:
            cls.server_default_port = int(cls.server_port)
        if cls.client_port and int(cls.client_port) != cls.client_default_port:
            cls.client_default_port = int(cls.client_port)

    @classmethod
    def __execute_local_command_enabled(cls, ip: str, execute_local_flag: bool = False) -> bool:
        """
        author:      haibin.xu
        date:        2020-11-02 12:01:17
        description: 根据给定的ip和execute_local_flag判定命令是否是在本地执行，如果是在本地执行，后续就不必再进行ssh连接操作

        :param ip:   ip地址
        :param execute_local_flag: 是否在本地执行标志位，True表示在本地执行，False表示在远程执行
        :return:     如果本地ip与参数中ip一致, 或者execute_local_flag为True，返回True,否则返回False
        """
        rtn_local = True if execute_local_flag else False

        # 因脚本中报没有找到ifconfig命令，暂时注释掉该段代码判断，
        # local_ip_list = cls.__get_local_host_ip()
        # if (ip in local_ip_list) or execute_local_flag:
        #     rtn_local = True

        return rtn_local

    @classmethod
    def __print_message(cls, message: str = None, print_enable: bool = True, level: int = -1) -> None:
        """
        author:      haibin.xu
        date:        2021-07-06 14:42:09
        description: 打印日志，print_enable为True时，打印info等级日志，为False时打印debug等级日志

        :param message: 待打印日志
        :param print_enable: 打印开关
        :return:     None
        """
        if print_enable:
            log.info_caller(message, level=level)
        else:
            log.debug_caller(message, level=level)

    @classmethod
    def __execute_command(cls, cmd: str, s_cmd: list = None, interactive_flag: bool = False,
                          timeout: int = 1800) -> tuple:
        """
        author:      haibin.xu
        date:        2020-11-02 13:37:00
        description: 封装命令执行方法

        :param cmd:  待执行的命令
        :param interactive_flag: 交互命令执行标志位，默认为False，为True时，cmd参数必须为list类型
        :return:     返回命令执行的状态码，标准输出，标准错误输出
        """
        # 在交互界面下执行命令，interactive_flag必须为True, cmd必须为list类型，且长度必须大于1
        if interactive_flag and cmd and isinstance(s_cmd, list) and (1 <= len(s_cmd)):
            # 执行cmd命令进入交互界面
            obj = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, close_fds=False, start_new_session=True)
            # 在交互界面依次输入s_cmd列表中的命令
            for i in range(len(s_cmd)):
                obj.stdin.write(s_cmd[i].encode(encoding='utf-8'))
        elif (not interactive_flag) and (s_cmd is None):
            obj = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=False,
                                   start_new_session=True)
        else:
            log.error('Invalid command format, interactive_flag: {}. cmd: {}.'.format(interactive_flag, cmd))
            return RtnStatusEnum.FAIL.value, '', 'Invalid command format'

        try:
            cmd_output, cmd_stderr = obj.communicate(timeout=timeout)
            ret_code = obj.poll()
            # cmd_output, cmd_stderr解码
            try:
                if isinstance(cmd_output, bytes):
                    cmd_output = cmd_output.decode('utf-8').rstrip()
            except UnicodeDecodeError:
                if isinstance(cmd_output, bytes):
                    try:
                        cmd_output = cmd_output.decode('gbk').rstrip()
                    except UnicodeDecodeError:
                        log.warning('Found UnicodeDecodeError!!!!!!!!!!!!!!!!!')
                        log.debug('cmd_output: {}'.format(cmd_output))
                        cmd_output = cmd_output.decode('utf-8', 'ignore').rstrip()
            try:
                if isinstance(cmd_stderr, bytes):
                    cmd_stderr = cmd_stderr.decode('utf-8').rstrip()
            except UnicodeDecodeError:
                if isinstance(cmd_stderr, bytes):
                    try:
                        cmd_stderr = cmd_stderr.decode('gbk').rstrip()
                    except UnicodeDecodeError:
                        log.warning('Found UnicodeDecodeError!!!!!!!!!!!!!!!!!')
                        log.debug('cmd_stderr: {}'.format(cmd_stderr))
                        cmd_stderr = cmd_stderr.decode('utf-8', 'ignore').rstrip()
        except subprocess.TimeoutExpired:
            # 注意：不能只使用p.kill和p.terminate，无法杀干净所有的子进程，需要使用os.killpg
            obj.kill()
            obj.terminate()
            try:
                os.killpg(obj.pid, signal.SIGTERM)
            except AttributeError:
                # Windows 不支持 os.killpg / POSIX signal，依赖 Popen.kill() 结束本地进程
                pass

            ret_code = RtnStatusEnum.FAIL.value
            cmd_output = ''
            cmd_stderr = '[ERROR]Timeout Error : Command "{}", timed out after {} seconds'.format(cmd, timeout)
        return ret_code, cmd_output, cmd_stderr

    @classmethod
    def __save_cmd_exec_time(cls, cmd: str, cmd_code: str, cmd_output: str, cmd_stderr: str) -> None:
        """
        author:      sunql
        date:        2021-08-16
        description:记录cmd命令执行时间至time.process_id
        :param cmd:
        :param cmd_code:cmd执行返回码
        :param cmd_output:cmd执行结果
        :param cmd_stderr:cmd执行错误信息，time cmd 后，时间信息会返回到cmd_stderr中
        :return:None
        """
        if 'time' not in cmd:
            return False

        process_id = os.getpid()
        log_file_name = 'success_cmd_time.' + str(process_id)
        if cmd_code != CmdStatusEnum.SUCCESS.value:
            log_file_name = 'err_cmd_time.' + str(process_id)

        time_log_path = os.path.join(constants.SCRIPT_CMD_TIME_LOG_DIR, log_file_name)
        fo = None
        try:
            fo = open(time_log_path, 'a')
            fo.write(cmd + cmd_stderr + '\n\n')
        except Exception as e:
            log.error(f"can not create file {time_log_path},error:\n")
        finally:
            try:
                fo.close()
            except Exception as e:
                pass

    @classmethod
    def check_windows_cmd(cls, ssh_ip: str = None, local_execute_flag: bool = False,
                          cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
                          host_os_server: str = None, host_os_client: str = None) -> bool:
        """
        判断命令是否在windows os 中执行
        author:     sunql
        :param ssh_ip:  指定 ssh 连接的 ip， 需与ssh_port同时定义，
        :param local_execute_flag: 是否在本地执行命令的标志位
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选
        :param host_os_server
        :param host_os_client
        :return: bool
        """
        if not host_os_server or not host_os_client:
            from scripts.script_libs.common_operation import CommonOperation
            host_os_server, host_os_client = CommonOperation.get_nic_os()

        if ((HostOsEnum.WINDOWS.value in host_os_client and
             cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value) or (
                    HostOsEnum.WINDOWS.value in host_os_server and
                    cmd_execute_address == CmdExecuteAdressEnum.SERVER.value)) and \
                not local_execute_flag:
            check_host_ip = ssh_ip
            if check_host_ip is None:
                check_host_ip, _ = cls.__get_ip_port(cmd_execute_address)
            if check_host_ip == cls.server_node_ip:
                return True
        return False

    @classmethod
    def check_cli_output(cls, cmd: (str, list), cmd_code: int, cmd_output: str, cmd_stderr: str = '',
                         print_enable: bool = True) -> int:
        """
        author:             haibin.xu
        date:               2020.07.10
        description:        检查命令执行后返回的状态和输出，log打印输出结果
                            包含业务逻辑的检查, 当cli命令执行输出中包含Status = Failure时，则判定命令执行失败
        :param cmd:         指定的命令
        :param cmd_code:    命令执行后返回的错误码
        :param cmd_output:  命令执行后返回的标准输出stdout
        :param cmd_stderr:  命令执行后的标准错误输出stderr
        :param print_enable: 是否打印
        :return:            命令执行成功，返回0，执行失败，返回-1
        """

        status_success_pattern = r'\s*Status\s*=\s*Success'
        status_success_json_pattern = r'\s*"Status":\s*"Success"'
        status_fail_pattern = r'\s*Status\s*=\s*Failure'
        status_fail_json_pattern = r'\s*"Status":\s*"Failure"'

        if RtnStatusEnum.SUCCESS.value != cmd_code:
            if (re.search(status_success_pattern, cmd_output)) or (re.search(
                    status_success_json_pattern, cmd_output)):
                rtn = RtnStatusEnum.SUCCESS.value
                if print_enable:
                    log.debug('Command: {}, execute success. Return code: {}, is not 0, But found success '
                              'keywords: [{}, or, {}], '
                              'Execute result:\nStdout: {}.\nStderr: {}.'.format(cmd, cmd_code,
                                                                                 status_success_pattern,
                                                                                 status_success_json_pattern,
                                                                                 cmd_output, cmd_stderr))
            else:
                rtn = cls.__check_cli_failure_output(cmd, cmd_code, cmd_output, cmd_stderr)
                if RtnStatusEnum.SUCCESS.value == rtn:
                    pass
                elif print_enable:
                    log.error('Command: {}, execute failed. Return code: {}, is not 0, And not found success '
                              'keywords:[{}, or, {}].\nExecute result:\n'
                              'Stdout: {}.\nStderr: {}.'.format(cmd, cmd_code, status_success_pattern,
                                                                status_success_json_pattern, cmd_output,
                                                                cmd_stderr))
        elif re.search(status_success_pattern, cmd_output) or re.search(status_success_json_pattern, cmd_output):
            rtn = RtnStatusEnum.SUCCESS.value
            if print_enable:
                log.debug(
                    'Command: {}, execute success. Return code: {}, And found success keywords: [{}, or, {}].\n'
                    'Execute result:\nStdout: {}.\nStderr: {}.'.format(cmd, cmd_code, status_success_pattern,
                                                                       status_success_json_pattern, cmd_output,
                                                                       cmd_stderr))
        elif re.search(status_fail_pattern, cmd_output) or re.search(status_fail_json_pattern, cmd_output):
            rtn = cls.__check_cli_failure_output(cmd, cmd_code, cmd_output, cmd_stderr)
            if RtnStatusEnum.SUCCESS.value == rtn:
                pass
            elif print_enable:
                log.error('Command: {}, execute failed. Return code: {}, But found failed keywords: '
                          '[{}, or, {}].\n'
                          'Execute result:\nStdout: {}.\nStderr: {}.'.format(cmd, cmd_code, status_fail_pattern,
                                                                             status_fail_json_pattern, cmd_output,
                                                                             cmd_stderr))
        elif 'syntax error' in cmd_output:
            rtn = RtnStatusEnum.FAIL.value
            if print_enable:
                log.error('Command: {}, execute failed. Return code: {}, But found error keywords: '
                          'syntax error.\n'
                          'Execute result:\nStdout: {}.\nStderr: {}.'.format(cmd, cmd_code, cmd_output,
                                                                             cmd_stderr))
        else:
            rtn = RtnStatusEnum.SUCCESS.value
            if print_enable:
                log.debug('Command: {}, execute success. Return code: {}, Not found any success/fail/error '
                          'keywords.\nExecute result:\nStdout: {}.\nStderr: {}.'.format(cmd, cmd_code, cmd_output,
                                                                                        cmd_stderr))

        # 如果 查到core 直接返回失败
        # if cls.check_cli_core():
        #     rtn = RtnStatusEnum.FAIL.value
        #     log.error("Command: {cmd}, execute failed. find core ")

        return rtn

    @classmethod
    def __check_cli_failure_output(cls, cmd: (str, list), cmd_code: int, cmd_output: str,
                                   cmd_stderr: str = '') -> int:
        """
        author:             zhilong.zhang
        date:               2021.10.15
        description:        由于管理命令返回的status做调整，为了不修改脚本，公共库做此兼容
                            当Status=Failure && Decription包含“Not Found” && cmd为/xall action时,
                            将return_code映射为Success
        :param cmd:         指定的命令
        :param cmd_code:    命令执行后返回的错误码
        :param cmd_output:  命令执行后返回的标准输出stdout
        :param cmd_stderr:  命令执行后的标准错误输出stderr
        :return:            命令执行成功，返回0，执行失败，返回-1
        """
        rtn = RtnStatusEnum.FAIL.value
        output_lines = cmd_output.splitlines()
        description_line = None
        for line in output_lines:
            if 'Description' in line:
                description_line = line
                break
        if not description_line or 'Controller not found' in description_line:
            return RtnStatusEnum.FAIL.value
        couldnot_find_keyword = "couldn't find"

        not_found_flag = False
        not_found_keyword = ["not found", "invalid vd id"]
        for keyword in not_found_keyword:
            if keyword in description_line.lower():
                not_found_flag = True
                break

        if couldnot_find_keyword in description_line.lower() or not_found_flag:
            if isinstance(cmd, str):
                if re.search(CONTROLLER_SHOW_PATTERN, cmd, re.I):
                    rtn = RtnStatusEnum.SUCCESS.value
                cmd_components = cmd.split(' ')[::-1]
                for cmd_component in cmd_components:
                    cmd_component = cmd_component.lower()
                    if '/' in cmd_component and str(cmd_component).endswith('all'):
                        rtn = RtnStatusEnum.SUCCESS.value
                        break

        if RtnStatusEnum.SUCCESS.value == rtn and RtnStatusEnum.SUCCESS.value != cmd_code:
            log.info('Command: {}, is disguised by the public library as a successful execution, cmd_code: 0. \n'
                     'Actual Execute result:\ncmd_code: {}.\n Stdout: {}.\nStderr: {}.'.format(cmd, cmd_code,
                                                                                               cmd_output,
                                                                                               cmd_stderr))
        return rtn

    @staticmethod
    def get_time(time_format: str = constants.TIME_FORMAT) -> tuple:
        """
        author:             xianda.liu
        date:               2022.07.29
        :param time_format: 时间格式
        :return:            以时间格式返回当前时间戳
        """
        # 当前时间戳
        current_timestamp = time.time()
        # 格式化时间
        current_format_time = time.localtime(current_timestamp)
        # 可读时间
        readable_time = time.strftime(time_format, current_format_time)

        return current_timestamp, readable_time

    @staticmethod
    def get_file_info(file_path: str = None) -> tuple:
        """
        author:             xianda.liu
        date:               2022.07.29
        :param file_path:   文件路径
        :return:            文件名，文件扩展名
        """
        file_name_with_no_extension = ''
        file_extension = ''

        if isinstance(file_path, str):
            file_name_with_extension = os.path.basename(file_path)
            file_name_with_no_extension, file_extension = os.path.splitext(file_name_with_extension)

        return file_name_with_no_extension, file_extension

    @staticmethod
    def format_linux_path_sep(path: str = None) -> str:
        """
        author:             xianda.liu
        date:               2022.07.29
        :param path:        文件或目录路径
        :return:            返回格式化的linux路径格式
        """
        rtn_path = path.replace('\\', '/')
        rtn_path = rtn_path.replace(os.sep, '/')

        return rtn_path

    @staticmethod
    def format_windows_path_sep(path: str = None) -> str:
        """
        author:      haibin.xu
        date:        2023-11-20 17:27:58
        description:
        :param path:        文件或目录路径
        :return:            返回格式化的linux路径格式
        """
        rtn_path = path.replace('/', '\\')
        rtn_path = rtn_path.replace(os.sep, '\\')

        return rtn_path

    @classmethod
    def execute_script_command(cls, script_cmd: str):
        """
        author:             xianda.liu
        date:               2022.07.29
        :param script_cmd:  执行脚本的命令
        :return:
        """
        log.info('Start to execute script: {}...\n\n'.format(script_cmd))
        rtn_stdout = ''
        format = 'utf-8' if 'Windows' != cls.local_platform else 'gbk'
        obj = subprocess.Popen(script_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               encoding=format)
        while True:
            try:
                cmd_stdout = obj.stdout.readline()
            except UnicodeDecodeError:
                cmd_stdout = '字符解析错误'
            finally:
                log.info(cmd_stdout.rstrip(), format_flag=False)
            if cls.scripts_end_keyword in cmd_stdout:
                rtn_stdout = cmd_stdout
            elif '' == cmd_stdout:
                log.info('\n', format_flag=False)
                break

        obj.wait()
        return obj.returncode, rtn_stdout

    @classmethod
    def check_ip_connect(cls, ip: str = None, ssh_port: str = None, ssh_username: str = 'root', connect_times: int = 3,
                         is_ping: bool = False, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> int:

        def ping_node(ip):
            ping_flag = True
            cmd = 'ping -c 2 {}'.format(ip)
            _, out, _ = CommandOperation.execute_command_with_error(cmd, local_execute_flag=True, timeout=5)
            if ', 0 received' in out or "已接收 0 个包" in out or not len(out.strip()):
                ping_flag = False
            log.info(f"ping node is {ping_flag}, {cmd} result: {out}")
            return ping_flag

        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            ssh_port = str(test_port)

        rtn_connect_ip = RtnStatusEnum.SUCCESS.value

        if ip is None and cmd_execute_address is not None:
            ip, resolved_port = cls.__get_ip_port(cmd_execute_address)
            if ssh_port is None:
                ssh_port = str(resolved_port)

        if is_ping or (ip == cls.client_ip and HostOsEnum.WINDOWS.value in constants.HOST_OS):
            if not ping_node(ip):
                rtn_connect_ip = RtnStatusEnum.FAIL.value
            return rtn_connect_ip

        if ssh_username is None:
            ssh_username = cls.ssh_username

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        while (0 != connect_times):
            try:
                ssh.connect(hostname=ip, port=int(ssh_port), username=ssh_username, banner_timeout=30)
                rtn_connect_ip = RtnStatusEnum.SUCCESS.value
                break
            except Exception as e:
                rtn_connect_ip = RtnStatusEnum.FAIL.value
                log.error('Fail to connect: {}@{}:{}, reason: {}'.format(ssh_username, ip, ssh_port, e))
                connect_times -= 1
            finally:
                ssh.close()

        return rtn_connect_ip

    @classmethod
    def get_process_id(cls, process_name: str = None, ssh_ip: str = None, ssh_port: str = None,
                       ssh_username: str = 'root', execute_times: int = 3) -> str:
        """
        author:      haibin.xu
        date:        2021-06-15 14:57:25
        description: 根据进程名获取进程id

        :param process_name: 进程名
        :param ssh_ip: 指定server ip
        :param ssh_port: 指定server port
        :param ssh_username: 指定server 登录用户名
        :param execute_times: 执行获取进程id命令次数
        :return:     返回进程的pid
        """
        process_id = None

        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            ssh_port = str(test_port)

        if process_name:
            get_pid_cmd = 'ps -A | grep {} |  awk \'{{print $1}}\''.format(process_name)

            while (0 != execute_times):
                cmd_code, cmd_stdout, cmd_stderr = cls.execute_command_with_error(
                    cmd=get_pid_cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
                rtn_code = cls.check_cli_output(get_pid_cmd, cmd_code, cmd_stdout, cmd_stderr)
                if RtnStatusEnum.SUCCESS.value == rtn_code:
                    if cmd_stdout:
                        out_list = [pid.strip() for pid in cmd_stdout.split() if pid.strip()]
                        if 1 <= len(out_list):
                            process_id = ','.join(out_list)
                    break
                else:
                    execute_times -= 1

        return process_id

    @classmethod
    def get_process_data(cls, process_kwname: str = None, ssh_ip: str = None, ssh_port: str = None,
                         ssh_username: str = 'root', column_list: list = None,
                         cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> tuple:
        """
        author:      haibin.xu
        date:        2021-07-22 16:30:50
        description: 获取进程信息

        :param process_kwname: 进程名关键字
        :param ssh_ip: 指定server ip
        :param ssh_port: 指定server port
        :param ssh_username: 指定server 登录用户名
        :param column_list: 指定获取进程信息的哪些列
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return:     返回进程信息

        @changelog      2021-11-29 15:38:38  haibin.xu
                        1. 优化函数实现, 添加参数cmd_execute_address
        """
        rtn_code = RtnStatusEnum.FAIL.value
        rtn_process_data = None
        column_info = ''

        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            ssh_port = str(test_port)

        if process_kwname:
            get_process_info_cmd = 'ps -ef | grep {} | grep -v grep'.format(process_kwname)
            if isinstance(column_list, list) and (1 <= len(column_list)):
                for i in range(len(column_list)):
                    column_info += '${}'.format(str(column_list[i]))
                    if i != (len(column_list) - 1):
                        column_info += ', '
            if column_info:
                get_process_info_cmd += ' | awk \'{{print {}}}\''.format(column_info)

            cmd_code, rtn_process_data, cmd_stderr = cls.execute_command_with_error(
                cmd=get_process_info_cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username,
                cmd_execute_address=cmd_execute_address)
            rtn_code = cls.check_cli_output(get_process_info_cmd, cmd_code, rtn_process_data, cmd_stderr)

        return rtn_code, rtn_process_data

    @classmethod
    def get_process_id_with_kw(cls, process_kwname: str = None, ssh_ip: str = None, ssh_port: str = None,
                               ssh_username: str = 'root', execute_times: int = 3) -> str:
        """
        author:      haibin.xu
        date:        2021-07-07 15:40:46
        description: 根据进程名关键字获取进程id

        :param process_kwname: 进程名关键字
        :param ssh_ip: 指定server ip
        :param ssh_port: 指定server port
        :param ssh_username: 指定server 登录用户名
        :param execute_times: 执行获取进程id命令次数
        :return:     返回进程的pid

        @changelog      2021-12-19 09:49:32  haibin.xu
                        1. 优化函数实现,根据关键字搜索进程id,可能有多个进程，所以修正获取进程号只等于1的情况，当有多个进程是，返回值为
                           多个进程号以逗号拼接的字符串，该修改，不改变返回类型，兼容以前的功能
        """
        process_id = None

        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            ssh_port = str(test_port)

        if process_kwname:
            while (0 != execute_times):
                rtn_code, cmd_stdout = cls.get_process_data(process_kwname, ssh_ip, ssh_port, ssh_username, [2])
                if RtnStatusEnum.SUCCESS.value == rtn_code:
                    if cmd_stdout:
                        out_list = [pid.strip() for pid in cmd_stdout.split() if pid.strip()]
                        if 1 <= len(out_list):
                            process_id = ','.join(out_list)
                    break
                else:
                    execute_times -= 1

        return process_id

    @classmethod
    def kill_process(cls, process_id: str = None, process_kwname: str = None, process_name: str = None,
                     ssh_ip: str = None, ssh_port: str = None, ssh_username: str = 'root', execute_times: int = 3) \
            -> int:
        """
        author:      haibin.xu
        date:        2021-07-07 15:59:08
        description: 杀死进程

        :param process_id: 待要杀死进程的id
        :param process_kwname: 待要杀死进程的进程名关键字
        :param process_name: 待要杀死进程的进程名
        :param ssh_ip: 指定server ip
        :param ssh_port: 指定server port
        :param ssh_username: 指定server 登录用户名
        :return: 成功杀死进程返回0， 否则返回-1
        """
        rtn_kill_process = RtnStatusEnum.SUCCESS.value
        kill_pid_flag = False

        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            ssh_port = str(test_port)

        if process_id is None:
            log.warning('Invalid process id: {}, not need to kill.'.format(process_id))
            return rtn_kill_process

        kill_pid_cmd = 'kill -9 {}'.format(process_id)
        while (0 != execute_times):
            cmd_code, cmd_stdout, cmd_stderr = cls.execute_command_with_error(
                cmd=kill_pid_cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
            rtn_code = cls.check_cli_output(kill_pid_cmd, cmd_code, cmd_stdout, cmd_stderr)
            if RtnStatusEnum.SUCCESS.value == rtn_code:
                kill_pid_flag = True
                break
            else:
                execute_times -= 1

        if kill_pid_flag:
            if (process_kwname is not None) and (process_name is None):
                pid = cls.get_process_id_with_kw(process_kwname=process_kwname, ssh_ip=ssh_ip, ssh_port=ssh_port,
                                                 ssh_username=ssh_username, execute_times=1)
                if pid is None:
                    rtn_kill_process = RtnStatusEnum.SUCCESS.value
            elif (process_kwname is None) and (process_name is not None):
                pid = cls.get_process_id(process_name=process_name, ssh_ip=ssh_ip, ssh_port=ssh_port,
                                         ssh_username=ssh_username, execute_times=1)
                if pid is None:
                    rtn_kill_process = RtnStatusEnum.SUCCESS.value
            else:
                check_pid_cmd = 'kill -0 {}'.format(process_id)
                cmd_code, _, _ = cls.execute_command_with_error(cmd=check_pid_cmd, ssh_ip=ssh_ip,
                                                                ssh_port=ssh_port, ssh_username=ssh_username)
                if RtnStatusEnum.SUCCESS.value != cmd_code:
                    rtn_kill_process = RtnStatusEnum.SUCCESS.value

        return rtn_kill_process
