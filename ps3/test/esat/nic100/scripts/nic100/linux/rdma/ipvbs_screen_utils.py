#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      wanting.wang
date:        2024.08.29
description:
"""
import json
import os
import random
import sys
import time
import re
import add_syspath
import datetime
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs import constants, log
from scripts.script_libs.enums import IpvbsStatusEnum, CmdExecuteAdressEnum, IpvbsCommuEnum, RtnStatusEnum
from scripts.script_libs.common_operation import CommonOperation
import socket
import select

from scripts.script_libs.script_base import SxeException

IPVBS_SCREEN_NAME = "ipvbstest"
SCREEN_LOG_PATH = "/home/rdma_screenlog/"
SCREEN_LOG_COLLECT_PATH = "/root/sxetest/"
SCREEN_LOG_NAME = "screenlog_rdma"
PKTGEN_AVAILABLE_CORE_INFO = "/root/sxetest/pktgen/available_core_info.txt"
RESULT_LOG_FOLDER = '/root/result_log/'

IPVBS_PATH = ''

RDMA_CORE_PATH_DEF = '/opt/tools/rdma-core-51.0'

NOT_SUPPORT_ROCE_DRV = ['ixgbe']


class IpvbsScreen(object):

    def __init__(self, caller_class, exec_addr, screen_name: str = "", commu=IpvbsCommuEnum.SCREEN.value, screen_mark: str = ''):
        self.screen_name = ''
        self.screen_mark = screen_mark
        self.log_folder = RESULT_LOG_FOLDER
        self.log_path = ''
        self.caller_class = caller_class
        self.exec_addr = exec_addr
        self.commu = commu
        self.ori_ipvbs_path = ''
        self.ori_ipvbs_socket_path = ''
        self.ori_ipvbs_local_path = ''
        self.ipvbs_path = ''
        self.ipvbs_socket_path = ''
        self.ipvbs_local_path = ''
        self.client_socket = None
        self.init_socket_success = False

        # 对端是82599，强制进行回环测试
        drv_s, drv_c = CommonOperation.get_nic_driver_name()
        if drv_c in NOT_SUPPORT_ROCE_DRV and (self.exec_addr == CmdExecuteAdressEnum.CLIENT.value):
            self.exec_addr = CmdExecuteAdressEnum.SERVER.value

        if self.commu == IpvbsCommuEnum.SOCKET.value:
            self.__init_socket__()
            # socket初始化失败
            if not self.init_socket_success:
                # 获取已启动的ipvbs_s进程
                vm, rpc_port = CommonOperation.get_node_info_from_path()
                exec_command = f"ps -ef|grep python3 |grep ipvbs_s.py |grep {vm} | grep -v grep"
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                    cmd=exec_command, cmd_execute_address=exec_addr)
                res = re.findall(
                    r'(\w+)\s+(\d+)\s+(\d+)\s+\d+\s+[\d:]+\s+\S+\s+[\d:]+\s.*?--ip\s+([\d\.]+)\s+--port\s+(\d+)\s+--addr\s+(\w+)',
                    rtn_outputs)
                pid_list = []
                if res:
                    for pid_info in res:
                        pid_list.append(pid_info[1])
                # 强制退出远端的所有ipvbs_s
                for pid in pid_list:
                    exec_command = f"kill -9 {pid}"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                        cmd=exec_command, cmd_execute_address=exec_addr)

        # socket初始化失败 或 指定screen： 初始化screnn
        if (self.commu == IpvbsCommuEnum.SOCKET.value and not self.init_socket_success) or (self.commu == IpvbsCommuEnum.SCREEN.value):
            self.__init_screen__()

    def __init_screen__(self):
        drv_s, drv_c = CommonOperation.get_nic_driver_name()

        # 若对端是82599等，强制进行回环测试
        if drv_c in NOT_SUPPORT_ROCE_DRV:
            drv_c = drv_s

        # 查看全部screen
        pre_screen = IPVBS_SCREEN_NAME
        if self.exec_addr == CmdExecuteAdressEnum.SERVER.value:
            pre_screen += 'S'
            drv = drv_s
        else:
            pre_screen += 'C'
            drv = drv_c

        if self.screen_mark:
            pre_screen += f'_{self.screen_mark}'

        vm, rpc_port = CommonOperation.get_node_info_from_path()
        self.ori_ipvbs_path = "{}{}/{}".format(constants.LINUX_FILE_PATH_ROOT, vm, 'ipvbs.py')
        self.ori_ipvbs_socket_path = "{}{}/{}".format(constants.LINUX_FILE_PATH_ROOT, vm, 'ipvbs_s.py')
        self.ori_ipvbs_local_path = "{}{}/{}".format(constants.LINUX_FILE_PATH_ROOT, vm, 'ipvbs_execute_cmd_in_local.py')

        # 从环境变量中获取rdma-core目录
        exec_command = f'echo \$PYTHONPATH'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.exec_addr)
        if '/' in rtn_outputs:
            rdma_core_root_path = re.findall(r'(/.*?/rdma-core-.*?)/', rtn_outputs)[0]
        else:
            log.warning(f'获取$PYTHONPATH环境变量值失败，使用默认rdma-core目录：{RDMA_CORE_PATH_DEF}')
            rdma_core_root_path = RDMA_CORE_PATH_DEF

        if drv == constants.DRV_SCGBE_PF:
            self.ipvbs_path = constants.IPVBS_PATH_SCGBE.format(rdma_core_root_path)
            self.ipvbs_socket_path = constants.IPVBSS_PATH_SCGBE.format(rdma_core_root_path)
            self.ipvbs_local_path = constants.IPVBS_LOCAL_PATH_SCGBE.format(rdma_core_root_path)
        else:
            self.ipvbs_path = constants.IPVBS_PATH_OPEN.format(rdma_core_root_path)
            self.ipvbs_socket_path = constants.IPVBSS_PATH_OPEN.format(rdma_core_root_path)
            self.ipvbs_local_path = constants.IPVBS_LOCAL_PATH_OPEN.format(rdma_core_root_path)

        exec_command = f'cp -rf {self.ori_ipvbs_path} {self.ipvbs_path}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.exec_addr)
        exec_command = f'cp -rf {self.ori_ipvbs_socket_path} {self.ipvbs_socket_path}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.exec_addr)
        exec_command = f'cp -rf {self.ori_ipvbs_local_path} {self.ipvbs_local_path}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.exec_addr)

        exec_command = "screen -list"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.exec_addr)
        log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        re_ipvbs_screen = re.findall(rf'({pre_screen}_\d+)', rtn_outputs)
        # 创建文件夹，在内部进行编译
        vm, rpc_port = CommonOperation.get_node_info_from_path()
        log.info("vm:{},rpc_port:{}".format(vm, rpc_port))
        self.screen_name = format(vm) + '_'

        if re_ipvbs_screen:
            max_screen_name = max(re_ipvbs_screen, key=lambda x: int(x.split('_')[-1]))
            if self.screen_mark:
                self.screen_name += max_screen_name.split('_')[0] + '_' + self.screen_mark + '_' + str(
                    int(max_screen_name.split('_')[-1]) + 1)
            else:
                self.screen_name += max_screen_name.split('_')[0] + '_' + str(
                    int(max_screen_name.split('_')[-1]) + 1)
        else:
            self.screen_name += f'{pre_screen}_0'

        screen_log_path = "{}{}/{}".format(constants.LINUX_FILE_PATH_ROOT, vm, self.screen_name)

        # 创建screen会话
        exec_command = "mkdir -p {}; cd {};screen -dmS {}".format(screen_log_path, screen_log_path, self.screen_name)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.exec_addr
        )
        log.info(f'command:{exec_command}, rtn_code：{rtn_code}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')

        # screen内执行source /etc/profile，刷新环境变量
        exec_command = "screen -x -S {} -p 0 -X stuff '{}^M'".format(
            self.screen_name, f"source /etc/profile")
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.exec_addr)
        log.info(f'command:{exec_command}, rtn_code：{rtn_code}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        # screen内执行python3 ipvbs.py
        exec_command = "screen -x -S {} -p 0 -X stuff '{}^M'".format(
            self.screen_name, f"python3 {self.ori_ipvbs_path}")
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.exec_addr)
        time.sleep(0.3)
        log.info(f'command:{exec_command}, rtn_code：{rtn_code}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
        # exec_command = f"find {self.log_folder} -type f -name " +
        # "\"pyverbs_log*\" -printf '%T@ %p\n' | sort -nr | cut -d' ' -f2- | head-n 1"
        exec_command = f'ls {RESULT_LOG_FOLDER}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.exec_addr
        )
        if rtn_code:
            exec_command = f'mkdir -p {RESULT_LOG_FOLDER}'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                cmd=exec_command, cmd_execute_address=self.exec_addr)
            exec_command = f'ls {RESULT_LOG_FOLDER}'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                cmd=exec_command, cmd_execute_address=self.exec_addr)
        log_lst = re.findall(r'(pyverbs_log_\S+log)', rtn_outputs)
        if log_lst:
            self.log_path = RESULT_LOG_FOLDER + max(log_lst, key=lambda x: int(''.join(re.findall(r'(\d+)', x))))
        else:
            log.error('未产生日志')
        # TODO /home下面的加screen名

    def __init_socket__(self):
        drv_s, drv_c = CommonOperation.get_nic_driver_name()
        ip_s, ip_c = CommonOperation.get_nic_logical_ip()

        # 若对端是82599等，强制进行回环测试
        if drv_c in NOT_SUPPORT_ROCE_DRV:
            drv_c = drv_s
            ip_c = ip_s

        if self.exec_addr == CmdExecuteAdressEnum.SERVER.value:
            addr_flag = 's'
            drv = drv_s
            host = ip_s
        else:
            addr_flag = 'c'
            drv = drv_c
            host = ip_c

        # 从环境变量中获取rdma-core目录
        exec_command = f'echo \$PYTHONPATH'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.exec_addr)
        if '/' in rtn_outputs:
            rdma_core_root_path = re.findall(r'(/.*?/rdma-core-.*?)/', rtn_outputs)[0]
        else:
            log.warning(f'获取$PYTHONPATH环境变量值失败，使用默认rdma-core目录：{RDMA_CORE_PATH_DEF}')
            rdma_core_root_path = RDMA_CORE_PATH_DEF

        # if drv == constants.DRV_SCGBE_PF:
        #     ipvbs_path = constants.IPVBSS_PATH_SCGBE.format(rdma_core_root_path)
        # else:
        #     ipvbs_path = constants.IPVBSS_PATH_OPEN.format(rdma_core_root_path)

        # 根据节点名计算测试机server port
        vm, rpc_port = CommonOperation.get_node_info_from_path()
        # 原始脚本目录
        self.ori_ipvbs_path = "{}{}/{}".format(constants.LINUX_FILE_PATH_ROOT, vm, 'ipvbs.py')
        self.ori_ipvbs_socket_path = "{}{}/{}".format(constants.LINUX_FILE_PATH_ROOT, vm, 'ipvbs_s.py')
        self.ori_ipvbs_local_path = "{}{}/{}".format(constants.LINUX_FILE_PATH_ROOT, vm, 'ipvbs_execute_cmd_in_local.py')

        # 在/opt/tools/rdma-core-51.0/pyverbs/examples中保存一份
        if drv == constants.DRV_SCGBE_PF:
            self.ipvbs_path = constants.IPVBS_PATH_SCGBE.format(rdma_core_root_path)
            self.ipvbs_socket_path = constants.IPVBSS_PATH_SCGBE.format(rdma_core_root_path)
            self.ipvbs_local_path = constants.IPVBS_LOCAL_PATH_SCGBE.format(rdma_core_root_path)
        else:
            self.ipvbs_path = constants.IPVBS_PATH_OPEN.format(rdma_core_root_path)
            self.ipvbs_socket_path = constants.IPVBSS_PATH_OPEN.format(rdma_core_root_path)
            self.ipvbs_local_path = constants.IPVBS_LOCAL_PATH_OPEN.format(rdma_core_root_path)

        # 复制到/opt/tools/rdma-core-51.0/pyverbs/examples
        exec_command = f'cp -rf {self.ori_ipvbs_path} {self.ipvbs_path}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.exec_addr)
        exec_command = f'cp -rf {self.ori_ipvbs_socket_path} {self.ipvbs_socket_path}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.exec_addr)
        exec_command = f'cp -rf {self.ori_ipvbs_local_path} {self.ipvbs_local_path}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=self.exec_addr)

        ori_port_s = int(format(ord(vm[0]), 'd')[-1] + vm[-3:]) + random.randint(0, 100)
        port_s = 0
        for i in range(5):
            # ipvbs_s端口算法
            port_s = i * 10000 + ori_port_s
            _, output, _ = CommandOperation.execute_command_with_error(
                cmd=f'netstat -tuln | grep :{port_s}', cmd_execute_address=self.exec_addr
            )

            # 目标端口未被占用
            if format(port_s, 'd') not in output:
                target_port_availd = True
            # 目标端口被占用
            else:
                target_port_availd = False
            log.info(f'target_port_availd: {target_port_availd}')

            # ipvbs_s日志路径
            log_path = f'/home/pyverbs_log/{vm}_{host}_{port_s}_{addr_flag}'
            log.info(f'测试机节点：{vm}；ipvbs_s日志路径：{log_path}')
            # 目标ipvbs启动命令
            ipvbs_cmd = f'python3 {self.ori_ipvbs_socket_path} --ip {host} --port {port_s} --addr {addr_flag} --log_path={log_path}'

            # 目标端口被占用
            if not target_port_availd:
                _, output, _ = CommandOperation.execute_command_with_error(cmd=f'ps -ef | grep python3',
                                                                           cmd_execute_address=self.exec_addr)
                # 端口被ipvbs_s占用
                if ipvbs_cmd in output:
                    log.info(f'端口已被ipvbs_s占用, 不再重试端口: {ipvbs_cmd}')
                    break
                # 非ipvbs占用端口
                else:
                    log.info(f'非ipvbs占用端口, 更换端口重试')
            # 目标端口未被占用，启动ipvbs
            else:
                CommandOperation.execute_command_with_error(
                    cmd=f'nohup {ipvbs_cmd} > /home/test.log 2>&1 &', cmd_execute_address=self.exec_addr)
                break

        time.sleep(2)
        _, output, _ = CommandOperation.execute_command_with_error(cmd=f'ps -ef | grep python3|grep ipvbs',
                                                                   cmd_execute_address=self.exec_addr)
        if ipvbs_cmd in output:
            log.info(f'ipvbs_s启动成功')
        else:
            log.error(f'ipvbs_s启动失败')
            self.init_socket_success = False
            return

        # 查询所有连接到ipvbs_s上的client端口，创建新的client连接
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd=f'netstat -anp | grep ESTABLISHED | grep {port_s}', cmd_execute_address=self.exec_addr
        )
        re_port_c = re.findall(fr'{port_s}\s+\d+\.\d+\.\d+\.\d+:(\d+)\s+ESTABLISHED', output)
        if re_port_c:
            port_lst = [p[-3:] for p in re_port_c]
            ori_port_c = int(max(port_lst)) + 1
        else:
            ori_port_c = 1

        bind_ipvbs_s_socket = False
        for i in range(30000, 40000, 1000):
            try:
                port_c = i + ori_port_c
                # 判断端口有没有被占用
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    try:
                        s.bind(('0.0.0.0', port_c))
                        is_port_in_use = False  # 端口可用
                    except OSError:
                        is_port_in_use = True  # 端口被占用
                if is_port_in_use:
                    log.info(f'端口[{port_c}]被占用，更换新端口')
                    continue
                # 尝试绑定端口
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                log.info(f'localhost绑定本地端口：0.0.0.0 {port_c}')
                #self.client_socket.bind(('0.0.0.0', port_c))
                # self.client_socket.listen(5)
                log.info(f'localhost连接远端ipvbs_s端口: {host} {port_s}')
                self.client_socket.connect((host, port_s))
                # 绑定ipvbs_s端口成功
                bind_ipvbs_s_socket = True
                break
            except Exception as e:
                time.sleep(3)
                log.exception(e)
                log.info(f'localhost绑定本地端口[{port_c}]失败，更换新端口')
                self.client_socket.close()

        # 绑定ipvbs_s端口失败
        if not bind_ipvbs_s_socket:
            err_info = f'localhost连接{host} ipvbs_s.py port：{port_s} 失败'
            log.error(err_info)
            # raise SxeException(err_info)
            self.init_socket_success = False
        else:
            self.init_socket_success = True

    def shutdown_ipvbs_server(self):
        if self.commu == IpvbsCommuEnum.SOCKET.value:
            self.client_socket.sendall('shutdown'.encode('utf-8'))
        else:
            log.info('当前实例非socket启动，请尝试调用exit_all_ipvbs方法')

    @classmethod
    def exit_all_ipvbs(cls, exec_addr, commu=IpvbsCommuEnum.SCREEN.value, screen_mark: str = "", exit_ipvbs_s_force = False):
        """
        author:      wangwt
        date:        2024-09-03
        description: 退出并清除所有ipvbs的screen会话
        """
        vm, rpc_port = CommonOperation.get_node_info_from_path()
        exec_command = f"ps -ef|grep python3 |grep ipvbs_s.py |grep {vm}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=exec_addr)
        if rtn_outputs:
            init_socket_success = True
        else:
            init_socket_success = False

        if commu == IpvbsCommuEnum.SOCKET.value and init_socket_success:
            res = re.findall(
                r'(\w+)\s+(\d+)\s+(\d+)\s+\d+\s+[\d:]+\s+\S+\s+[\d:]+\s.*?--ip\s+([\d\.]+)\s+--port\s+(\d+)\s+--addr\s+(\w+)',
                rtn_outputs)
            socket_list = []
            if res:
                for pid_info in res:
                    socket_list.append([pid_info[3], int(pid_info[4])])
            pid_list = []
            if res:
                for pid_info in res:
                    pid_list.append(pid_info[1])
            # 强制退出远端的所有ipvbs_s
            if exit_ipvbs_s_force:
                for pid in pid_list:
                    exec_command = f"kill -9 {pid}"
                    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                        cmd=exec_command, cmd_execute_address=exec_addr)
            # 软退出远端的所有ipvbs_s
            else:
                for socket_port in socket_list:
                    ori_port_c = int(socket_port[1]) + 1
                    for i in range(1000, 65535, 5000):
                        try:
                            port_c = i + ori_port_c
                            # 判断端口有没有被占用
                            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                                try:
                                    s.bind(('0.0.0.0', port_c))
                                    is_port_in_use = False  # 端口可用
                                except OSError:
                                    is_port_in_use = True  # 端口被占用
                            if is_port_in_use:
                                log.info(f'端口[{port_c}]被占用，更换新端口')
                                continue

                            connect_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                            log.info(f'localhost bind socket: 0.0.0.0 {port_c}')
                            connect_socket.bind(('0.0.0.0', port_c))

                            log.info(f'localhost connect server: {socket_port[0]} {socket_port[1]}')
                            connect_socket.connect((socket_port[0], socket_port[1]))

                            log.info(f'localhost send shutdown to server: {socket_port[0]} {socket_port[1]}')
                            connect_socket.sendall('shutdown'.encode('utf-8'))

                            log.info(f'localhost close socket: 0.0.0.0 {port_c}')
                            connect_socket.close()

                            break
                        except Exception as e:
                            time.sleep(3)
                            log.info(e)
                            log.info(f'localhost绑定本地端口[{port_c}]失败，更换新端口')
                            connect_socket.close()
            # # 关闭本端socket
            # for socket_port in socket_list:
            #     exec_command = f"netstat -ano | grep {socket_port[0]} | grep {socket_port[1]}"
            #     rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            #         cmd=exec_command, cmd_execute_address=exec_addr)
        # 指定screen 或 socket初始化失败
        else:
            exec_command = "screen -list"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                cmd=exec_command, cmd_execute_address=exec_addr)
            # log.info(f'command:{exec_command}, \noutputs:{rtn_outputs}, \nerror:{rtn_err}')
            vm, rpc_port = CommonOperation.get_node_info_from_path()
            pre_screen = format(vm) + '_'
            pre_screen += IPVBS_SCREEN_NAME
            if exec_addr == CmdExecuteAdressEnum.SERVER.value:
                pre_screen += 'S'
            else:
                pre_screen += 'C'

            if screen_mark:
                pre_screen += f'_{screen_mark}'

            re_ipvbs_screen = re.findall(rf'(\d+\.{pre_screen}_\d+)', rtn_outputs)
            if re_ipvbs_screen:
                for ipvbs_screen in re_ipvbs_screen:
                    exec_command = "screen -x -S {} -p 0 -X stuff \\\"{}\\\"".format(ipvbs_screen, 'exit')
                    CommandOperation.execute_command_with_error(exec_command, cmd_execute_address=exec_addr)
                    exec_command = "screen -x -S {} -p 0 -X stuff '^M'".format(ipvbs_screen)
                    CommandOperation.execute_command_with_error(exec_command, cmd_execute_address=exec_addr)
                    exec_command = "screen -S {} -X quit".format(ipvbs_screen)
                    CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=exec_addr)
                    exec_command = "screen -wipe".format(ipvbs_screen)
                    CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=exec_addr)
            CommandOperation.execute_command_with_error(cmd=f'rm -rf {RESULT_LOG_FOLDER}*', cmd_execute_address=exec_addr)

    def exit_ipvbs_screen(self):
        """
        author:      wangwt
        date:        2024-09-03
        description: 退出并清除当前ipvbs所在screen会话
        """
        if self.commu == IpvbsCommuEnum.SOCKET.value and self.init_socket_success:
            self.client_socket.sendall('exit'.encode('utf-8'))
            self.client_socket.close()
        else:
            exec_command = "screen -x -S {} -p 0 -X stuff 'exit^M'".format(self.screen_name)
            CommandOperation.execute_command_with_error(exec_command, cmd_execute_address=self.exec_addr)
            exec_command = "screen -S {} -X quit".format(self.screen_name)
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=self.exec_addr)
            exec_command = "screen -wipe".format(self.screen_name)
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=self.exec_addr)
            CommandOperation.execute_command_with_error(
                cmd=f'rm -rf {self.log_path}', cmd_execute_address=self.exec_addr)

    def execute_ipvbs_cmd_in_screen(self, cmd: str, level=-1, timout=30, print_steps=True, print_outputs=True,
                                    use_sh=True, cmd_timeout: int = 0):
        """
        author:      wangwt
        date:        2024-09-05
        description: 获取所在screen会话界面增量日志，日志5s刷新一次，此方法最多等待10s
        :param use_sh True, 使用新的小脚本的方式执行ipvbs命令，相比旧方式，性能较好（可缩短50%执行时间），但兼容性可能不佳；
                            若出现不兼容cmd格式的情况，请使用旧方式执行cmd(use_sh=False)
                      False, 使用旧方式执行ipvbs命令，兼容性较好，但性能较低
        """
        server_logic_ip, client_logic_ip = CommonOperation.get_nic_logical_ip()
        if self.exec_addr == CmdExecuteAdressEnum.SERVER.value:
            logic_ip = server_logic_ip
        else:
            logic_ip = client_logic_ip

        if cmd_timeout:
            cmd = f'timeout{cmd_timeout}s {cmd}'

        if print_steps:
            CommonOperation.concat_test_steps(f'{self.exec_addr.title()}端[{logic_ip}]执行ipvbs -> [{cmd}]',
                                              level=level - 1)

        if not use_sh:
            exec_command = "screen -x -S {} -p 0 -X stuff \\\"{}\\\"".format(self.screen_name, cmd)
            CommandOperation.execute_command_with_error(exec_command, cmd_execute_address=self.exec_addr,
                                                        print_steps=False, print_outputs=False)
            exec_command = "screen -x -S {} -p 0 -X stuff '^M'".format(self.screen_name)
            CommandOperation.execute_command_with_error(exec_command, cmd_execute_address=self.exec_addr,
                                                        print_steps=False, print_outputs=False)
            rtn_outputs = ''
            ori_time = time.time()
            check_lst = cmd.split(';')
            check_wrd = check_lst[-1].strip()
            while time.time() - ori_time < timout:
                exec_command = f'cat {self.log_path}'
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                    exec_command, cmd_execute_address=self.exec_addr, print_steps=False, print_outputs=False)

                pattern = rf'execute:{check_wrd}.*status' \
                    .replace('(', '\(').replace(')', '\)') \
                    .replace('[', '\[').replace(']', '\]')
                check = re.findall(pattern, rtn_outputs, re.S)
                if check:
                    break
                elif cmd.strip() == 'exit':
                    break
            CommandOperation.execute_command_with_error(
                cmd=f"echo '' > {self.log_path}", cmd_execute_address=self.exec_addr, print_steps=False,
                print_outputs=False
            )
        else:
            cmd_temp = cmd.replace(" = ", '=')
            cmd_temp = cmd_temp.replace(" , ", ',')
            cmd_temp = cmd_temp.encode('utf-8')
            cmd_temp = ''.join([format(i, '02x') for i in cmd_temp])
            # cmd = cmd.replace("\'", '#').replace("\"", "##")
            exec_command = "python3 {} --screen=\'{}\' --cmd=\'{}\' --log_path={}" \
                .format(self.ipvbs_local_path, self.screen_name, cmd_temp, self.log_path)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=self.exec_addr, print_steps=False, print_outputs=False)
        if print_outputs:
            log.info(f"========ipvbs finish log [{self.screen_name}]:\n" + rtn_outputs)
        return rtn_outputs

    def execute_ipvbs_cmd_in_socket(self, cmd, timeout=300, cmd_timeout: int = 0, print_outputs=True):
        if cmd_timeout:
            cmd = f'timeout{cmd_timeout}s {cmd}'
        timeout &= 0xffff
        if cmd[-1] != ';':
            cmd += ';'

        def receive_all(sock, buffer_size=20480, timeout_s=5):
            start_time = time.time()
            # 使用字节串累积结果
            data_save = b""
            # 设置套接字超时，避免recv无限阻塞
            sock.settimeout(timeout_s)
            while True:
                # 总超时
                if time.time() > start_time + timeout_s:
                    log.warning(f'总超时 {timeout_s*2} 秒，停止接收')
                    break

                # 接收数据
                try:
                    part = sock.recv(buffer_size)
                # recv超时，继续循环检查总超时
                except socket.timeout:
                    continue
                # recv出错，停止接收
                except socket.error as e:
                    print(f"套接字错误: {e}")
                    break

                # print(f"接收到 {len(part)} 字节: {part}")  # 打印字节
                # print(f"十六进制: {part.hex()}")  # 以十六进制查看，方便定位 0xe4
                # 接收到空数据，表示连接关闭
                if not part:
                    print("连接已关闭")
                    break

                # 接收完成
                if b'#####RESULTEND######' in part:  # 接收到#####RESULTEND######字节串，表示一个完整的回复结束
                    break
                print(type(data_save))
                print(type(part))
                data_save += part
            return data_save

        self.client_socket.sendall(cmd.encode('utf-8'))
        ori_time = time.time()
        rtn_num = 0
        try:
            readable, writable, exceptional = select.select([self.client_socket], [], [], timeout)
            data = ''
            while True:
                if readable:
                    data += self.client_socket.recv(1048576*2).decode('utf-8')
                    # raw_data = receive_all(self.client_socket)
                    # data += raw_data.decode('utf-8')  # 在所有字节到齐后解码
                    get_cmd_data = ''
                    # print(f'>>>>>>>>>>>> data: {data} <<<<<<<<<<<<<<')
                    # data_split = data.split(';')
                    # print(f'>>>>>>>>>>>> data_split: {data_split} <<<<<<<<<<<<<<')
                    for info in data.split(';'):
                        # print(f'123456cmd: {cmd}')
                        # print(f'123456info: {info}')
                        if cmd.replace(';', '') in info:
                            get_cmd_data = info
                            # print(f'>>>>>>>>>>>> get_cmd_data: {get_cmd_data} <<<<<<<<<<<<<<')
                            break

                    if re.findall(fr'execute:.*RESULTEND', data, re.S) and get_cmd_data:
                        rtn_num += get_cmd_data.count("#####RESULTEND######")
                        # print(f'>>>>>>>>>>>> rtn_num: {rtn_num} <<<<<<<<<<<<<<')
                        break
                    else:
                        time.sleep(0.01)
                        readable, writable, exceptional = select.select(
                            [self.client_socket], [], [], timeout - (time.time() - ori_time))
                else:
                    get_cmd_data = 'status: error\nSocketTimeOut\n#####RESULTEND######'
                    break
        # except UnicodeDecodeError as e:
        #     # 使用 ‘replace’ 或 ‘ignore’ 查看大致内容
        #     decoded_data = raw_data.decode('utf-8', errors='replace')
        #     log.info(f"解码出错，替换后的内容： {decoded_data}")
        #     # 或者直接打印错误位置
        #     log.info(f"解码错误详情：{e}")
        #     get_cmd_data = f'{cmd}\n status: error\nUnicodeDecodeError\n#####RESULTEND######'
        except Exception as e:
            log.info('-------------Err Start---------------')
            log.info(e)
            log.info('-------------Err End---------------')
            get_cmd_data = f'{cmd}\n status: error\nSocketError\n#####RESULTEND######'

        if print_outputs:
            print(get_cmd_data)
        return get_cmd_data
        # while rtn_num < cmd_num:
        #     try:
        #         readable, writable, exceptional = select.select([self.client_socket], [], [], timeout)
        #         while True:
        #             if readable:
        #                 data = self.client_socket.recv(4096).decode('utf-8')
        #                 if re.findall(fr'execute:.*RESULTEND', data, re.S):
        #                     rtn_num += data.count("#####RESULTEND######")
        #                     break
        #                 else:
        #                     time.sleep(0.01)
        #                     readable, writable, exceptional = select.select(
        #                         [self.client_socket], [], [], timeout - (time.time() - ori_time))
        #             else:
        #                 data = 'status: error\nSocketTimeOut\n#####RESULTEND######'
        #                 err_flag = True
        #                 break
        #     except Exception:
        #         data = 'status: error\nSocketError\n#####RESULTEND######'
        #         err_flag = True
        #     print(data)
        #     result_lst.append(data)
        #     if err_flag:
        #         break
        # return '\n'.join(result_lst)

    def exec_and_get_ipvbs_result(self, cmd, level=-1, print_steps=True, print_outputs=True, use_sh=True,
                                  cmd_timeout: int = 0):
        """
        clear: ipvbs_s进程不退出，清理其他资源。exit: 推出ipvbs_s
        :param cmd:
        :param level:
        :param print_steps:
        :param print_outputs:
        :param use_sh:
        :param cmd_timeout:
        :return:
        """
        if self.commu == IpvbsCommuEnum.SOCKET.value and self.init_socket_success:
            rtn = self.execute_ipvbs_cmd_in_socket(cmd, cmd_timeout=cmd_timeout, print_outputs=print_outputs)
        else:
            rtn = self.execute_ipvbs_cmd_in_screen(
                cmd, level=level - 1, print_steps=print_steps, print_outputs=print_outputs, use_sh=use_sh,
                cmd_timeout=cmd_timeout)

        re_rtn = re.findall(r'status:\s+(\w+)\n(.*)\n#####RESULTEND######', rtn, re.S)
        if re_rtn:
            status = re_rtn[0][0]
            result = re_rtn[0][1].replace('#####RESULTEND######', '').strip()
        elif cmd.strip() == 'exit':
            status = IpvbsStatusEnum.SUCCESS.value
            result = None
        else:
            status = IpvbsStatusEnum.ERROR.value
            result = None
        return status, result

    def exec_multi_cmd(self, cmd_lst, bug_msk=None, sta_exp=None, print_steps=True, print_outputs=True,
                       use_sh=True, level=-1, cmd_timeout: int = 0):
        # TODO bugstop
        rtn_lst = []
        if not cmd_lst:
            return rtn_lst
        if self.commu == IpvbsCommuEnum.SOCKET.value and self.init_socket_success:
            for cmd in cmd_lst:
                status, result = self.exec_and_get_ipvbs_result(cmd=cmd, level=level-1, cmd_timeout=cmd_timeout)
                rtn_lst.append([status, result])
        else:
            compose_lst = []
            num_lst = []
            compose = ''
            num = 0
            for cmd in cmd_lst:
                if compose == '':
                    compose = cmd
                    num = 1
                    continue
                if len(compose) + len(cmd) < 700:
                    compose = constants.SEMICOLON.join([compose, cmd])
                    num += 1
                else:
                    compose_lst.append(compose)
                    num_lst.append(num)
                    compose = cmd
                    num = 1
            compose_lst.append(compose)
            num_lst.append(num)
            for compose, exp_num in zip(compose_lst, num_lst):
                rtn_output = self.execute_ipvbs_cmd_in_screen(cmd=compose,
                                                              print_steps=print_steps, print_outputs=print_outputs,
                                                              use_sh=use_sh, level=level-1, cmd_timeout=cmd_timeout)
                tmp_lst = re.findall(rf'status:\s+(\w+)\n(.*?)\n#####RESULTEND######', rtn_output, re.S)
                for status, result in tmp_lst:
                    rtn_lst.append([status, result.rstrip()])
        return rtn_lst

    def __del__(self):
        if self.commu == IpvbsCommuEnum.SOCKET.value:
            if self.client_socket:
                self.client_socket.close()

    @classmethod
    def force_exit_ipvbs_s(cls, exec_addr: str, level=-1, print_steps=True, print_outputs=True):
        """
        clear: ipvbs_s进程强制退出
        :param exec_addr:
        :param level:
        :param print_steps:
        :param print_outputs:
        :return:
        """
        vm, rpc_port = CommonOperation.get_node_info_from_path()
        pid_list = []
        cmd = f"ps -ef | grep python3 | grep ipvbs_s |grep {vm} | grep -v grep | tr -s ' ' | cut -d ' ' -f 2"
        status, result, _  = CommandOperation.execute_command_with_error(
            cmd, cmd_execute_address=exec_addr, print_steps=print_steps, print_outputs=print_outputs)
        if result:
            pid_list = result.split('\n')

        if pid_list:
            for pid in pid_list:
                if pid:
                    cmd = f"kill -9 {pid}"
                    status, result, _ = CommandOperation.execute_command_with_error(
                        cmd, cmd_execute_address=exec_addr, print_steps=print_steps, print_outputs=print_outputs)
                    # 强制退出失败
                    if status:
                        return RtnStatusEnum.FAIL.value
        return RtnStatusEnum.SUCCESS.value

    def get_all_obj(self, print_steps=True, print_outputs=True, use_sh=True, level=-1, cmd_timeout: int = 0):
        cmd = 'list(rdma_dict.keys())'
        status, result = self.exec_and_get_ipvbs_result(cmd=cmd,
                                                      print_steps=print_steps, print_outputs=print_outputs,
                                                      use_sh=use_sh, level=level - 1, cmd_timeout=cmd_timeout)
        return eval(result)


if __name__ == '__main__':
    f = None

    cmd_lst = [
        f"obj_ctx = device.Context(name='{constants.DRV_SCGBE_RDMA}0')",
        "obj_pd1 = pd.PD(creator=obj_ctx)",
        "obj_buf = mem_alloc.malloc(9000)",
        "obj_mr1 = mr.MR(creator=obj_pd1, length=9000, access=enums.ibv_access_flags.IBV_ACCESS_LOCAL_WRITE.value, "
        "address=obj_buf, implicit=False)",
        "obj_mr1.length",
        "obj_mr1.write(data='asdfghjkl'*1000, length=9000)",
        "obj_mr1.read(9000, 0).decode('utf-8')",
        # "obj_mr1.close()",
        "mem_alloc.free(obj_buf)",
    ]
    # IpvbsScreen.exit_all_ipvbs(CmdExecuteAdressEnum.SERVER.value)
    # IpvbsScreen.exit_all_ipvbs(CmdExecuteAdressEnum.CLIENT.value)

    ipvbs_s1 = IpvbsScreen(
        caller_class=f, exec_addr=CmdExecuteAdressEnum.SERVER.value, commu=IpvbsCommuEnum.SOCKET.value)
    # ipvbs_c = IpvbsScreen(caller_class=f, exec_addr=CmdExecuteAdressEnum.CLIENT.value)
    print('------------------->>>>>>>', ipvbs_s1.exec_multi_cmd(cmd_lst))
    # ipvbs_s.exit_ipvbs_screen()
    #
    # ipvbs_s.exit_ipvbs_screen()
    # ipvbs_c.exit_ipvbs_screen()

    ipvbs_s2 = IpvbsScreen(
        caller_class=f, exec_addr=CmdExecuteAdressEnum.SERVER.value, commu=IpvbsCommuEnum.SOCKET.value)
    # ipvbs_c = IpvbsScreen(caller_class=f, exec_addr=CmdExecuteAdressEnum.CLIENT.value)
    print('------------------->>>>>>>', ipvbs_s2.exec_multi_cmd(cmd_lst))
    # input()
