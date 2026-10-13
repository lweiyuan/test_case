#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      jing.li
date:        2020.07.09 12:06
description: 文件类
"""
import os
import re
import copy
import sys
import time
import hashlib
import platform
import csv
from datetime import datetime

from scripts.script_libs import log
from scripts.script_libs import constants
from scripts.script_libs.common_operation import CommandOperation, CommonOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum, HostOsEnum
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse

# 查找挂在目录时，定义'lsblk | grep -A 1 sda'中的1，显示所有匹配行后的一行
MOUNT_LOCATION = 1
# 查找挂在目录时，mountpoint项所在列的位置
MOUNT_LUN_LOCATION = 7
# 执行mountpoint中用到了lun_list索引值为2的元素（即字串‘sda’在lun_list中的索引位置）
LUN_LOCATION = 2
# test/esat/scripts 目录绝对路径
SCRIPTS_DIRECTORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FileOperation(object):
    # Linux 使用 ls -ld 判断文件标志位
    __LINUX_FILE_FLAG = '-'
    # Linux 使用 ls -ld 判断文件夹标志位
    __LINUX_DIRECTORY_FLAG = 'd'
    # 定义删除或创建的白名单匹配字串，即使用者只能在/root/ps3test/.*/下进行文件或文件夹的删除和创建操作
    __PATH_PATTERN = constants.FILE_PATH_ROOT + '.*'
    # 本地文件临时保存路径
    __local_file_save_path = os.path.join(SCRIPTS_DIRECTORY, constants.FILE_TEMP_PATH_NAME)

    @staticmethod
    def __isvalid(param=None) -> bool:
        """
        author:      haibin.xu
        date:        2021-07-02 14:48:36
        description: 检查参数的有效性

        :param param: 待定检查的参数
        :return:     参数有效返回True，否则返回False
        """
        if param is None:
            rtn_check_result = False
        elif isinstance(param, str) and ('' == param):
            rtn_check_result = False
        elif isinstance(param, list) and ([] == param):
            rtn_check_result = False
        elif isinstance(param, dict) and ({} == param):
            rtn_check_result = False
        elif isinstance(param, tuple) and (() == param):
            rtn_check_result = False
        elif isinstance(param, bool):
            rtn_check_result = param
        else:
            rtn_check_result = True

        return rtn_check_result

    @classmethod
    def __match_path_pattern(cls, path, match_pattern: str = "") -> int:
        """
        author:      haibin.xu
        date:        2020-08-31 17:11:34
        description: 判断给定的路径是否符合规定的操作路径
        :param path: 给定的文件或目录路径
        :return:     给定的路径符合规定的操作路径，返回0， 否则返回-1
        """
        rtn_path_pattern = RtnStatusEnum.FAIL.value
        if not match_pattern:
            match_pattern = cls.__PATH_PATTERN

        if not re.match(match_pattern, path):
            log.error('Your path: {}, is not match to path pattern: {}.'.format(path, match_pattern))
        else:
            rtn_path_pattern = RtnStatusEnum.SUCCESS.value

        return rtn_path_pattern

    @staticmethod
    def path_exists_for_windows(path: str, ip: str = None, port: str = '22', localpath_flag: bool = False,
                                username: str = None, print_enable=True):
        """
        author:      sunql
        date:        2021-12-08 18:54:05
        description: 判定给定的路径是否存在
        :param path: 给定的路径
        :param ip:   指定执行命令的ip
        :param port: 指定执行命令的port
        :param localpath_flag: 本地路径标志位
        :param username: ssh登录用户名
        :param print_enable: 是否打印执行命令
        :return:     路径有效返回0，以及当前 ls -l的返回值，命令无效返回-1, 以及’‘
        """
        rtn_path_exists = RtnStatusEnum.FAIL.value
        check_path_cmd = 'test-path {}'.format(path)
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation. \
            execute_command_based_paramiko_with_rtncode(cmd=check_path_cmd, local_execute_flag=localpath_flag,
                                                        ssh_ip=ip, ssh_port=port, ssh_username=username)
        if 'True' in cmd_stdout:
            rtn_path_exists = RtnStatusEnum.SUCCESS.value
        return rtn_path_exists, path

    @staticmethod
    def path_exists(path: str, ip: str = None, port: str = '22', localpath_flag: bool = False,
                    username: str = "root", print_enable=True, level: int = -1) -> tuple:
        """
        author:      haibin.xu
        date:        2020-08-27 18:54:05
        description: 判定给定的路径是否存在
        :param path: 给定的路径
        :param ip:   指定执行命令的ip
        :param port: 指定执行命令的port
        :param localpath_flag: 本地路径标志位
        :param username: ssh登录用户名
        :param print_enable: 是否打印执行命令
        :return:     路径有效返回0，以及当前 ls -l的返回值，命令无效返回-1, 以及’‘

        @changelog      2021-03-15 17:12:58  haibin.xu
                        1. 优化函数实现, 添加参数localpath_flag
                        2021-03-16 11:12:10  haibin.xu
                        1. 优化函数实现, 添加参数username
                        2021-08-11 11:12:10  sunql
                        1. 修改命令执行方法为 execute_command_based_paramiko_with_rtncode，解决多线程调用卡死问题
        """
        # 设置路径存在标志位的初始值
        rtn_path_exists = RtnStatusEnum.FAIL.value
        cmd_stdout = ''

        if path:
            if CommandOperation.check_windows_cmd(ssh_ip=ip):
                rtn_path_exists, path = FileOperation.path_exists_for_windows(
                    path=path, username=username, ip=ip, port=port)
                return rtn_path_exists, '-' + path

            # 使用’ls -ld path‘判断路径有效性，命令有效会返回当前命令
            check_path_cmd = 'ls -ld {}'.format(path)
            # cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
            #     cmd=check_path_cmd, local_execute_flag=localpath_flag, ssh_ip=ip, ssh_port=port,
            #     ssh_username=username, print_enable=print_enable)
            # overwrite 修改命令执行方法为 execute_command_based_paramiko_with_rtncode
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation. \
                execute_command_based_paramiko_with_rtncode(cmd=check_path_cmd, local_execute_flag=localpath_flag,
                                                            ssh_ip=ip, ssh_port=port, ssh_username=username,
                                                            print_enable=print_enable, level=level-1)
            _ = CommandOperation.check_cli_output(check_path_cmd, cmd_code, cmd_stdout, cmd_stderr)
            # 支持*.pcap 格式删除
            if (RtnStatusEnum.SUCCESS.value == cmd_code) and \
                    (path in cmd_stdout or
                     ("*" in path and path.split("*")[-1] and path.split("*")[-1] in cmd_stdout)):
                rtn_path_exists = RtnStatusEnum.SUCCESS.value
        else:
            log.error('invalid path: {}.'.format(path))

        return rtn_path_exists, cmd_stdout

    @classmethod
    def dir_path_exists(cls, path: str, path_flag: bool = False, ip: str = None, port: str = '22',
                        username: str = None) -> int:
        """
        author:      haibin.xu
        date:        2020-08-27 19:37:11
        description: 判断目录是否存在
        :param path: 给定路径
        :param path_flag: 是否在本地查找路径，True表示在本地查找，False表示在远程server查找
        :param ip:   指定远程执行命令的ip
        :param port: 指定远程执行命令的port
        :param username: ssh登录用户名
        :return:     目录存在返回RtnStatusEnum.SUCCESS.value， 不存在返回RtnStatusEnum.FAIL.value

        @changelog      2021-03-16 10:53:54  haibin.xu
                        1. 优化函数实现, 添加远程执行的ip,port参数
                        2021-03-16 11:11:28  haibin.xu
                        1. 优化函数实现, 添加远程执行的username参数
        """
        # 初始化目录路径标志位
        rtn_dirpath_exits = RtnStatusEnum.FAIL.value

        if path_flag and ('*' not in path):
            rtn_dirpath_exits = RtnStatusEnum.SUCCESS.value if os.path.isdir(path) else RtnStatusEnum.FAIL.value
        else:
            check_path_exits, check_path_output = cls.path_exists(path, ip=ip, port=port, username=username,
                                                                  localpath_flag=path_flag)
            if (RtnStatusEnum.SUCCESS.value == check_path_exits) and \
                    (cls.__LINUX_DIRECTORY_FLAG == check_path_output[0]):
                rtn_dirpath_exits = RtnStatusEnum.SUCCESS.value

        return rtn_dirpath_exits

    @classmethod
    def file_path_exists(cls, path: str, path_flag: bool = False, ip: str = None, port: str = '22',
                         username: str = 'root') -> int:
        """
        author:      haibin.xu
        date:        2020-08-27 19:53:01
        description: 判断文件是否存在
        :param path: 给定路径
        :param path_flag: 是否在本地查找路径，True表示在本地查找，False表示在远程server查找
        :param ip:   指定远程执行命令的ip
        :param port: 指定远程执行命令的port
        :param username: 指定远程执行命令的登录用户名
        :return:     文件存在返回RtnStatusEnum.SUCCESS.value， 不存在返回RtnStatusEnum.FAIL.value
        """
        # 初始化目录路径标志位
        rtn_filepath_exits = RtnStatusEnum.FAIL.value

        if path_flag and ('*' not in path):
            rtn_filepath_exits = RtnStatusEnum.SUCCESS.value if os.path.isfile(path) else RtnStatusEnum.FAIL.value
        else:
            check_path_exits, check_path_output = cls.path_exists(path, ip=ip, port=port, localpath_flag=path_flag,
                                                                  username=username, print_enable=False)
            if (RtnStatusEnum.SUCCESS.value == check_path_exits) and (cls.__LINUX_FILE_FLAG == check_path_output[0]):
                rtn_filepath_exits = RtnStatusEnum.SUCCESS.value

        return rtn_filepath_exits

    @classmethod
    def make_directory(cls, dir_name: str, local_execute: bool = False, ip: str = None, port: str = '22',
                       username: str = None, match_flag: bool = True, delete_flag: bool = True) -> int:
        """
        author:      haibin.xu
        date:        2020-08-29 16:34:31
        description: 创建目录
        :param dir_name: 目录名
        :param local_execute: 本地执行标志位
        :param ip:   指定远程执行命令的ip
        :param port: 指定远程执行命令的port
        :param username: ssh登录用户名
        :param match_flag: 是否对文件进行/root/ps3sim/.*模式匹配，
                           如果进行模式匹配，则只有匹配该模式才对文件进行操作
        :param delete_flag: 是否先进行删除操作
        :return:     目录创建成功或目录已经存在返回 RtnStatusEnum.SUCCESS.value，失败，返回RtnStatusEnum.FAIL.value

        @changelog      2021-03-13 10:53:54  haibin.xu
                        1. 优化函数实现, 添加本地执行参数
                        2021-03-16 10:52:56  haibin.xu
                        1. 优化函数实现, 添加远程执行的ip, port
                        2021-03-16 11:13:49  haibin.xu
                        1. 优化函数实现, 添加远程执行的username参数
                        2021-06-03 10:51:53  haibin.xu
                        1. 优化函数实现, 添加删除操作参数delete_flag
        """
        rtn_mkdir = RtnStatusEnum.FAIL.value

        if dir_name and (
                (match_flag and (
                        RtnStatusEnum.SUCCESS.value == cls.__match_path_pattern(dir_name))) or not match_flag):
            if CommandOperation.check_windows_cmd(ssh_ip=ip, local_execute_flag=local_execute):
                dir_name = dir_name.replace(' ', ',')
                mkdir_cmd = 'rm -r -fo {}; mkdir -p {}'.format(dir_name, dir_name) if delete_flag else \
                    'mkdir -p {}'.format(dir_name)
            else:
                mkdir_cmd = 'rm -rf {}; mkdir -p {}'.format(dir_name, dir_name) if delete_flag else \
                    'mkdir -p {}'.format(dir_name)
            mkdir_code, mkdir_output, mkdir_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                mkdir_cmd, local_execute_flag=local_execute, ssh_ip=ip, ssh_port=port, ssh_username=username)
            if (RtnStatusEnum.SUCCESS.value == mkdir_code) or ('File exists' in mkdir_output) or \
                    ('File exists' in mkdir_stderr):
                rtn_mkdir = RtnStatusEnum.SUCCESS.value

        return rtn_mkdir

    @classmethod
    def sftp_upload_file(cls, localfile_path: str, remotefile_path: str, ip: str = None,
                         port: str = '22', cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> tuple:
        """
        author:      haibin.xu
        date:        2020-09-18 12:14:19
        description: 本地文件传输到远程服务器上
        :param localfile_path: 本地文件路径
        :param remotefile_path: 远程文件路径
        :param ip:   指定远程执行命令的ip
        :param port: 指定远程执行命令的port
        :return:     文件传输成功返回0， 失败返回-1

        @changelog      2021-03-08 11:55:18  haibin.xu
                        1. 优化函数实现，添加远程目录的ip, port
        """
        remotefile_md5 = constants.STR_EMPTY
        rtn_file_upload_flag = RtnStatusEnum.FAIL.value

        localfile_md5 = cls.get_md5(localfile_path, True)
        trans_file_flag = CommandOperation.transport_file_with_paramiko(
            local_path=localfile_path, remote_path=remotefile_path, transport_type='upload', ssh_ip=ip,
            ssh_port=port, cmd_execute_address=cmd_execute_address)
        if RtnStatusEnum.SUCCESS.value == trans_file_flag:
            remotefile_md5 = cls.get_md5(path=remotefile_path, ip=ip, port=port)

        log.info('after sftp_upload_file localfile_md5: {}, remotefile_md5: {}'.format(
            localfile_md5, remotefile_md5))
        if (remotefile_md5 != constants.STR_EMPTY) and (localfile_md5 == remotefile_md5):
            rtn_file_upload_flag = RtnStatusEnum.SUCCESS.value

        return rtn_file_upload_flag, localfile_md5, remotefile_md5

    @classmethod
    def scp_file_to_remote(cls, localfile_path: str, remotefile_path: str, ip: str = None, port: str = '22',
                           cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> tuple:
        """
        author:      xiangyu.liu
        date:        2020-09-18 12:14:19
        description: 本地文件传输到远程服务器上
        :param localfile_path: 本地文件路径
        :param remotefile_path: 远程文件路径
        :param ip:   指定远程执行命令的ip
        :param port: 指定远程执行命令的port
        :return:     文件传输成功返回0， 失败返回-1

        @changelog      2021-03-08 11:55:18  haibin.xu
                        1. 优化函数实现，添加远程目录的ip, port
        """
        remotefile_md5 = constants.STR_EMPTY
        rtn_file_upload_flag = RtnStatusEnum.FAIL.value

        localfile_md5 = cls.get_md5(localfile_path, True)
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        if (HostOsEnum.WINDOWS.value in host_os_client and
            cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value) or (
                HostOsEnum.WINDOWS.value in host_os_server and
                cmd_execute_address == CmdExecuteAdressEnum.SERVER.value):
            ssh_username = 'Administrator'
        else:
            ssh_username = "root"

        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            port = str(test_port)

        scp_file_cmd = f"scp -r -P {port} {localfile_path} {ssh_username}@{ip}:{remotefile_path} "
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            scp_file_cmd, local_execute_flag=True)
        # if RtnStatusEnum.SUCCESS.value == cmd_code:
        #     remotefile_md5 = cls.get_md5(path=remotefile_path, ip=ip, port=port)

        log.info('after scp_file localfile_md5: {}, remotefile_md5: {}'.format(
            localfile_md5, remotefile_md5))
        if (remotefile_md5 != constants.STR_EMPTY) and (localfile_md5 == remotefile_md5):
            rtn_file_upload_flag = RtnStatusEnum.SUCCESS.value

        return rtn_file_upload_flag, localfile_md5, remotefile_md5

    @classmethod
    def sftp_download_file(cls, localfile_path: str = None, remotefile_path: str = None, ip: str = None,
                           port: str = '22', with_error: bool = False, username: str = 'root') -> tuple:
        """
        author:      haibin.xu
        date:        2020-09-18 12:14:19
        description: 从远程服务器下载文件到本地
        :param localfile_path: 本地文件路径
        :param remotefile_path: 远程文件路径
        :param ip:   指定远程执行命令的ip
        :param port: 指定远程执行命令的port
        :param with_error: 是否返回错误信息
        :return:     文件传输成功返回0， 失败返回-1

        @changelog:
        """
        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            port = str(test_port)

        localfile_md5 = constants.STR_EMPTY
        rtn_file_download_flag = RtnStatusEnum.FAIL.value

        if localfile_path is None:
            localfile_path = os.path.join(cls.__local_file_save_path, os.path.basename(remotefile_path))
        remotefile_md5, err_msg = cls.get_md5(path=remotefile_path, ip=ip, port=port, with_error=True,
                                              username=username)
        log.info('Remote file: {}:{}:{}, its md5: {}'.format(ip, port, remotefile_path, remotefile_md5))
        if '' != remotefile_md5:
            trans_file_flag = CommandOperation.transport_file_with_paramiko(
                local_path=localfile_path, remote_path=remotefile_path, transport_type='download', ssh_ip=ip,
                ssh_port=port, ssh_username=username)
            if RtnStatusEnum.SUCCESS.value == trans_file_flag:
                rtn_file_download_flag = trans_file_flag
        if with_error:
            return rtn_file_download_flag
        return rtn_file_download_flag

    @classmethod
    def read_file(cls, path: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value,
                  print_enable: bool = True) -> str:
        """
        author: jing.li
        date: 2020.07.9
        description: 读取文件, 适用于小文件读取
        :param path:文件路径
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: 返回读取文件内容，文件不存在或读取有误时，返回‘’
        :notation: 建议方案，使用paramiko提供的sftp方法，将文件拷贝到本地，使用python标准读文件操作来读
        """
        file_content = constants.STR_EMPTY
        if cmd_execute_address == CmdExecuteAdressEnum.CLI_DEFAULT.value and \
                RtnStatusEnum.FAIL.value == cls.file_path_exists(path):
            log.error('Invalid filepath: {}'.format(path))
        else:
            read_file_cmd = 'cat {}'.format(path)
            readfile_cmd_code, file_content, readfile_cmd_stderr = CommandOperation.execute_command_with_error(
                read_file_cmd, cmd_execute_address=cmd_execute_address, print_enable=print_enable)
            if readfile_cmd_code:
                log.error('Error read the file: {}, Reason: {}'.format(path, readfile_cmd_stderr))
            elif not file_content and print_enable:
                log.warning('The content of file: {}  is Null.'.format(path))

        return file_content

    @classmethod
    def read_file_base_sftp(cls, localfile_path: str = None, remotefile_path: str = None) -> str:
        """
        author:      haibin.xu
        date:        2020-09-18 13:51:02
        description: 先将远程文件路径下载到本地，再进行读取
        :param localfile_path: 本地文件路径
        :param remotefile_path: 远程文件路径
        :return:     返回文件内容

        @changelog:
        """
        file_content = constants.STR_EMPTY
        trans_file_flag = RtnStatusEnum.FAIL.value

        if RtnStatusEnum.FAIL.value == cls.file_path_exists(remotefile_path):
            log.error('Invalid filepath: {}'.format(remotefile_path))
        else:
            trans_file_flag, _, _ = cls.sftp_download_file(localfile_path, remotefile_path)

        if RtnStatusEnum.SUCCESS.value == trans_file_flag:
            localfile_path = os.path.join(cls.__local_file_save_path, os.path.basename(remotefile_path))
            with open(localfile_path, 'r') as fp:
                file_content = fp.read()

        return file_content

    @classmethod
    def read_local_file(cls, localfile_path: str) -> str:
        """
        author:      haibin.xu
        date:        2020-10-14 15:24:08
        description: 读取本地文件

        :param localfile_path: 本地文件路径
        :return:     返回文件内容
        """
        file_content = constants.STR_EMPTY

        if os.path.isfile(localfile_path):
            with open(localfile_path, 'r') as fp:
                file_content = fp.read()

        return file_content

    @classmethod
    def write_local_file(cls, file_path: str, contents: str, write_mode: str = 'w') -> int:
        """
        author:      haibin.xu
        date:        2020-10-24 16:43:00
        description: 在本地写文件

        :param file_path: 本地文件路径
        :param contents: 要写的内容
        :param write_mode: 写模式
        :return:     文件写成功返回0，否则返回非0
        """
        rtn_write_file = RtnStatusEnum.FAIL.value

        if file_path:
            with open(file_path, write_mode) as fp:
                fp.write(contents)
            rtn_write_file = RtnStatusEnum.SUCCESS.value

        return rtn_write_file

    @classmethod
    def write_file_base_sftp(cls, file_path: str, contents: str, write_mode: str = 'w',
                             match_flag: bool = True,
                             cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> int:
        """
        author:      haibin.xu
        date:        2020-09-19 10:19:04
        description: 先将文件写在本地，再上传到远程服务器
        :param file_path: 文件名称
        :param contents: 写入的内容
        :param write_mode: 写模式
        :param match_flag: 是否需要添加匹配路径检查
        :return:     本地新写的文件成功传到远程服务器，返回0，否则，返回-1

        @changelog      2022-06-14 10:39:20  haibin.xu
                        1. 优化函数实现, 添加参数match_flag
                        2022-06-14 14:09:42  haibin.xu
                        1. 优化函数实现, 如果temp_files不存在，则创建
        """
        write_file_flag = False
        trans_file_flag = RtnStatusEnum.FAIL.value

        if match_flag:
            file_path_match = RtnStatusEnum.SUCCESS.value if RtnStatusEnum.SUCCESS.value == cls.__match_path_pattern(
                file_path) else RtnStatusEnum.FAIL.value
        else:
            file_path_match = RtnStatusEnum.SUCCESS.value
        localfile_path = os.path.join(cls.__local_file_save_path, os.path.basename(
            file_path)) if RtnStatusEnum.SUCCESS.value == file_path_match else constants.STR_EMPTY
        if not os.path.exists(cls.__local_file_save_path):
            cls.make_directory(dir_name=cls.__local_file_save_path, local_execute=True, match_flag=False)
        if RtnStatusEnum.SUCCESS.value == cls.write_local_file(file_path=localfile_path, contents=contents,
                                                               write_mode=write_mode):
            write_file_flag = True
        if write_file_flag:
            trans_file_flag, _, _ = cls.sftp_upload_file(localfile_path=localfile_path, remotefile_path=file_path,
                                                         cmd_execute_address=cmd_execute_address)

        return trans_file_flag

    @classmethod
    def write_file_base_scp(cls, remote_ip: str, file_path: str, contents: str, write_mode: str = 'w',
                            match_flag: bool = True,
                            cmd_execute_address: str = CmdExecuteAdressEnum.CLI_DEFAULT.value) -> int:
        """
        author:      xiangyu.liu
        date:        2020-09-19 10:19:04
        description: 先将文件写在本地，再上传到远程服务器
        :param file_path: 文件名称
        :param contents: 写入的内容
        :param write_mode: 写模式
        :param match_flag: 是否需要添加匹配路径检查
        :return:     本地新写的文件成功传到远程服务器，返回0，否则，返回-1
        """
        write_file_flag = False
        trans_file_flag = RtnStatusEnum.FAIL.value

        if match_flag:
            file_path_match = RtnStatusEnum.SUCCESS.value if RtnStatusEnum.SUCCESS.value == cls.__match_path_pattern(
                file_path) else RtnStatusEnum.FAIL.value
        else:
            file_path_match = RtnStatusEnum.SUCCESS.value
        localfile_path = os.path.join(cls.__local_file_save_path, os.path.basename(
            file_path)) if RtnStatusEnum.SUCCESS.value == file_path_match else constants.STR_EMPTY
        if not os.path.exists(cls.__local_file_save_path):
            cls.make_directory(dir_name=cls.__local_file_save_path, local_execute=True, match_flag=False)

        if RtnStatusEnum.SUCCESS.value == cls.write_local_file(file_path=localfile_path, contents=contents,
                                                               write_mode=write_mode):
            write_file_flag = True
        if write_file_flag:
            log.info("{} write to {} {}".format(contents, cmd_execute_address, file_path))
            trans_file_flag, _, _ = cls.scp_file_to_remote(ip=remote_ip, localfile_path=localfile_path,
                                                           remotefile_path=file_path,
                                                           cmd_execute_address=cmd_execute_address)

        return trans_file_flag

    @classmethod
    def mount_directory(cls, lun: str, dir_mount: str, file_system: str = 'ext4') -> int:
        """
        author: jing.li
        date: 2020.07.9
        description: 挂载目录
        :param dir_mount:挂载的目录路径
        :param lun: 创建的虚拟盘名称
        :param file_system: 文件系统类型
        :return: 是否挂载成功
        """
        rtn_ismount = RtnStatusEnum.FAIL.value
        match_dir_code = -1
        delete_file_code = -1
        mount_code = -1
        format_code = -1
        mk_dir_code = -1

        if RtnStatusEnum.SUCCESS.value == cls.__match_path_pattern(dir_mount):
            match_dir_code = 0

        dir_exists_flag = cls.dir_path_exists(dir_mount)

        if (RtnStatusEnum.SUCCESS.value == dir_exists_flag) and (0 == match_dir_code):
            # 如果目录存在，umount一下该目录
            umount_code = cls.umount_directory(dir_mount)
            # 如果umount成功，进一步删除该目录下所有文件
            if RtnStatusEnum.SUCCESS.value == umount_code:
                delete_file_code, _ = cls.delete_file(dir_mount + '/*')
                if RtnStatusEnum.SUCCESS.value != delete_file_code:
                    log.error('Success umount directory: {}, but fail to delete files in it.'.format(dir_mount))
            else:
                log.error('Fail to umount directory: {}'.format(dir_mount))
        elif (RtnStatusEnum.FAIL.value == dir_exists_flag) and (0 == match_dir_code):
            # 如果目录不存在但是目录符合白名单规定的路径格式，则创建该目录
            mk_dir_code = cls.make_directory(dir_mount)
            if RtnStatusEnum.FAIL.value == mk_dir_code:
                log.error('Fail to make directory: {}'.format(dir_mount))

        # 如果目录操作命令执行成功
        if (RtnStatusEnum.SUCCESS.value == delete_file_code) or (RtnStatusEnum.SUCCESS.value == mk_dir_code):
            # 格式化磁盘分区
            format_cmd = 'mkfs.{} -F {}'.format(file_system, lun)
            format_code, format_out, _ = CommandOperation.execute_command_with_error(format_cmd)
            if ': done' in format_out:
                format_code = RtnStatusEnum.SUCCESS.value

        if RtnStatusEnum.SUCCESS.value == format_code:
            # mount命令
            dir_mount_cmd = 'mount -w {} {}'.format(lun, dir_mount)
            # 执行mount命令
            mount_code, _, _ = CommandOperation.execute_command_with_error(dir_mount_cmd)

        # 如果mount命令执行成功，进一步检查mount目录是否真实存在
        if RtnStatusEnum.SUCCESS.value == mount_code:
            # 以’/‘分割虚拟盘字符串，lun 一般为 ’/dev/sda‘, lun_list = ['', 'dev', 'sda']
            lun_list = lun.strip().split('/')
            # 执行mountpoint中用到了lun_list索引值为2的元素（即获取字串‘sda’）,所以此处检查lun_list的大小是否 >= 3
            if 3 <= len(lun_list):
                # 检查mountpoint命令，以sda为例，该命令格式：lsblk | grep -A 1 sda | awk '{{print $7 }}'
                mount_check_cmd = "lsblk | grep -A {} {} | awk '{{print ${} }}'".format(
                    MOUNT_LOCATION, lun_list[LUN_LOCATION], MOUNT_LUN_LOCATION)
                lun_code, lun_output, _ = CommandOperation.execute_command_with_error(mount_check_cmd)
                if dir_mount in lun_output:
                    rtn_ismount = RtnStatusEnum.SUCCESS.value
            # 如果lun_list元素个数小于3，判定传入的lun字串无效，报错
            else:
                log.error('Invalid input lun: {}'.format(lun))

        return rtn_ismount

    @classmethod
    def umount_directory(cls, dir_umount: str) -> int:
        """
        author: jing.li
        date: 2020.07.9
        description: 卸载目录
        :param dir_umount:想要卸载的目录
        :return:卸载成功与该目录本来就没有mount两种情况下都返回0， 其他情况返回-1
        """
        # 初始化卸载目录的返回结果
        rtn_isumount = RtnStatusEnum.FAIL.value
        match_dir_code = -1

        # 判断卸载目录是否符合路径格式
        if RtnStatusEnum.SUCCESS.value == cls.__match_path_pattern(dir_umount):
            match_dir_code = 0

        if 0 == match_dir_code:
            # 卸载目录并将目录内文件置位空的命令
            dir_umount_cmd = 'umount -v {}'.format(dir_umount)

            dir_umount_code, _, dir_umount_stderr = CommandOperation.execute_command_with_error(dir_umount_cmd)
            # umount命令执行成功，或者该目录本就没有mount，都返回成功
            if (0 == dir_umount_code) or ('not mounted' in dir_umount_stderr):
                rtn_isumount = RtnStatusEnum.SUCCESS.value
            else:
                log.error('umount error: {}.'.format(dir_umount_stderr))

        return rtn_isumount

    @classmethod
    def copy_file(cls, path: str, copy_path: str, local_execute: bool = False, ip: str = None,
                  port: str = '22', match_flag: bool = True, file_check_flag: bool = True) -> int:
        """
        author: jing.li
        date: 2020.07.9
        description: 直接将一些目录下的所有文件复制到某个目录中
        :param path: 想要复制的文件
        :param copy_path:复制过去的目录
        :param localfile_path: 本地文件路径
        :param ip:   指定远程执行命令的ip
        :param port: 指定远程执行命令的port
        :param match_flag: 是否对文件进行/root/ps3sim/.*模式匹配，
                           如果进行模式匹配，则只有匹配该模式才对文件进行操作
        :param file_check_flag: 是否检查文件路径有效性
        :return:复制是否成功

        @changelog      2021-03-16 14:01:36  haibin.xu
                        1. 优化函数实现, 添加local_execute, ip, port参数
        """
        rtn_copy_file = RtnStatusEnum.FAIL.value
        file_pattern_flag = True
        file_path_flag = True

        # 根据match_flag参数判断是否进行文件路径模式匹配
        if not match_flag:
            log.debug('Not need to match file path pattern: {}.'.format(cls.__PATH_PATTERN))
        elif match_flag and (RtnStatusEnum.SUCCESS.value == cls.__match_path_pattern(path)) and \
                (RtnStatusEnum.SUCCESS.value == cls.__match_path_pattern(copy_path)):
            log.debug('Match the file path pattern: {}.'.format(cls.__PATH_PATTERN))
        else:
            file_pattern_flag = False

        # 首先判断路径是否存在
        if file_check_flag:
            if (RtnStatusEnum.SUCCESS.value != cls.file_path_exists(path, path_flag=local_execute, ip=ip)) or (
                    RtnStatusEnum.SUCCESS.value != cls.dir_path_exists(copy_path, path_flag=local_execute, ip=ip)):
                log.error('Invalid file path, Please check source file: {}, and destination file: {}'.format(
                    path, copy_path))
                file_path_flag = False
        # 其次判断路径是否符合规定的路径格式，都符合的话，开始拷贝操作
        if file_pattern_flag and file_path_flag:
            # 拷贝指令
            copy_cmd = 'cp -r {} {}'.format(path, copy_path)
            # 执行拷贝操作
            file_copy_code, _, file_copy_stderr = CommandOperation.execute_command_with_error(
                copy_cmd, local_execute_flag=local_execute, ssh_ip=ip, ssh_port=port)
            # 拷贝操作成功，返回0
            if (RtnStatusEnum.SUCCESS.value == file_copy_code) or ('are the same file' in file_copy_stderr):
                rtn_copy_file = RtnStatusEnum.SUCCESS.value
            else:
                log.error('Error copy the source file: {} to destination file: {}, Reason: {}'.format(
                    path, copy_path, file_copy_stderr))
        return rtn_copy_file

    @classmethod
    def copy_path_file(cls, path: str, copy_path: str, local_execute: bool = False, ip: str = None,
                       port: str = '22', match_flag: bool = True, file_check_flag: bool = True) -> int:
        """
        author: rui.song
        date: 2022.07.18
        description: 直接将一些目录下的所有文件复制到某个目录中
        :param path: 想要复制的文件
        :param copy_path:复制过去的目录
        :param local_execute: 本地文件路径
        :param ip:   指定远程执行命令的ip
        :param port: 指定远程执行命令的port
        :param match_flag: 是否对文件进行/root/ps3sim/.*模式匹配，
                           如果进行模式匹配，则只有匹配该模式才对文件进行操作
        :param file_check_flag: 是否检查文件路径有效性
        :return:复制是否成功
        """
        rtn_copy_file = RtnStatusEnum.FAIL.value
        file_pattern_flag = True
        file_path_flag = True

        # 根据match_flag参数判断是否进行文件路径模式匹配
        if not match_flag:
            log.debug('Not need to match file path pattern: {}.'.format(cls.__PATH_PATTERN))
        elif match_flag and (RtnStatusEnum.SUCCESS.value == cls.__match_path_pattern(path)) and \
                (RtnStatusEnum.SUCCESS.value == cls.__match_path_pattern(copy_path)):
            log.debug('Match the file path pattern: {}.'.format(cls.__PATH_PATTERN))
        else:
            file_pattern_flag = False

        # 首先判断路径是否存在
        if file_check_flag:
            if (RtnStatusEnum.SUCCESS.value != cls.file_path_exists(path, path_flag=local_execute, ip=ip)) and (
                    RtnStatusEnum.SUCCESS.value != cls.dir_path_exists(copy_path, path_flag=local_execute, ip=ip)):
                log.error('Invalid file path, Please check source file: {}, and destination file: {}'.format(
                    path, copy_path))
                file_path_flag = False
        # 其次判断路径是否符合规定的路径格式，都符合的话，开始拷贝操作
        if file_pattern_flag and file_path_flag:
            # 拷贝指令
            copy_cmd = '/usr/bin/cp -rpf {} {}'.format(path, copy_path)
            # 执行拷贝操作
            file_copy_code, _, file_copy_stderr = CommandOperation.execute_command_with_error(
                copy_cmd, local_execute_flag=local_execute, ssh_ip=ip, ssh_port=port)
            # 拷贝操作成功，返回0
            if (RtnStatusEnum.SUCCESS.value == file_copy_code) or ('are the same file' in file_copy_stderr):
                rtn_copy_file = RtnStatusEnum.SUCCESS.value
            else:
                log.error('Error copy the source file: {} to destination file: {}, Reason: {}'.format(
                    path, copy_path, file_copy_stderr))
        return rtn_copy_file

    @classmethod
    def scp_file_to_window(cls, source_file_path: str, target_file_path: str, source_ip: str = None,
                           source_port: str = '22', source_username: str = 'root', windows_ip: str = None,
                           target_port: str = '22', target_username: str = 'root', clear_target_file: bool = False):
        """
        author:      sunql
        date:        2021-12-17 17:03:55
        description: 从远程拷贝文件 , windows 需 在windows本地执行scp，从源服务器拉到本地
        :param source_file_path: 源文件路径
        :param target_file_path: 目标文件路径
        :param source_ip: 源文件所在server ip
        :param source_port: 源文件所在server port
        :param source_username: 源文件所在server 登录用户名
        :param windows_ip: 目标文件所在server ip
        :param target_port: 目标文件所在server port
        :param target_username: 目标文件所在server 登录用户名
        :param clear_target_file:是否清理目标地址文件
        :return:     命令执行成功，返回0，否则返回-1
        """
        rtn_scp_file = RtnStatusEnum.SUCCESS.value
        source_ip_valid_flag = True
        target_ip_valid_flag = True

        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            source_port = str(test_port)
            target_port = str(test_port)

        if source_ip is None:
            log.error('Not given valid source ip: {}'.format(source_ip))
            rtn_scp_file = RtnStatusEnum.FAIL.value
            source_ip_valid_flag = False

        if source_ip_valid_flag:
            if windows_ip is None:
                log.error('Not given valid target ip: {}.'.format(windows_ip))
                rtn_scp_file = RtnStatusEnum.FAIL.value
                target_ip_valid_flag = False

        if source_ip_valid_flag and target_ip_valid_flag:
            # 清理windows环境文件
            if clear_target_file:
                log.info('delete target file: {}'.format(target_file_path))
                cls.delete_file(path=target_file_path, ip=windows_ip, port=target_port, match_flag=False)
            # 拼接拷贝命令
            scp_file_cmd = f"scp -P {source_port} {source_username}@{source_ip}:{source_file_path} {target_file_path}"
            # 从远程拷贝到windows
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_for_windows(
                scp_file_cmd, ssh_ip=windows_ip, ssh_port=str(target_port))
            # 处理远程拷贝结果
            rtn_code = CommandOperation.check_cli_output(scp_file_cmd, cmd_code, cmd_stdout, cmd_stderr)

            if RtnStatusEnum.SUCCESS.value == rtn_code:
                log.debug('Success to scp source file path: {}@{}[{}]:{} to target file path: {}@{}[{}]:{}.'.format(
                    source_username, source_ip, source_port, source_file_path, target_username, windows_ip,
                    target_port, target_file_path))
            else:
                rtn_scp_file = RtnStatusEnum.FAIL.value

        return rtn_scp_file

    @classmethod
    def windows_scp_file(cls, source_file_path: str, target_file_path: str, target_ip: str = None,
                         source_port: str = '22', source_username: str = 'root', windows_ip: str = None,
                         target_port: str = '22', target_username: str = 'root'):
        """
        author:      sunql
        date:        2021-12-17 17:03:55
        description: 从远程拷贝文件 , windows 需 在windows本地执行scp，从源服务器拉到本地
        :param source_file_path: 源文件路径
        :param target_file_path: 目标文件路径
        :param source_ip: 源文件所在server ip
        :param source_port: 源文件所在server port
        :param source_username: 源文件所在server 登录用户名
        :param windows_ip: 目标文件所在server ip
        :param target_port: 目标文件所在server port
        :param target_username: 目标文件所在server 登录用户名
        :param clear_target_file:是否清理目标地址文件
        :return:     命令执行成功，返回0，否则返回-1
        """
        from scripts.script_libs.windows_command_operation import WindowsCommandOperation

        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            source_port = str(test_port)
            target_port = str(test_port)

        rtn_scp_file = RtnStatusEnum.SUCCESS.value
        source_ip_valid_flag = True
        target_ip_valid_flag = True

        if target_ip is None:
            log.error('Not given valid target ip: {}'.format(target_ip))
            rtn_scp_file = RtnStatusEnum.FAIL.value
            source_ip_valid_flag = False

        if source_ip_valid_flag:
            if windows_ip is None:
                log.error('Not given valid target ip: {}.'.format(windows_ip))
                rtn_scp_file = RtnStatusEnum.FAIL.value
                target_ip_valid_flag = False

        if source_ip_valid_flag and target_ip_valid_flag:
            # 拼接拷贝命令
            scp_file_cmd = f"{constants.SCP} -P {source_port} {source_file_path} " \
                           f"{target_username}@{target_ip}:{target_file_path}"
            # 从远程拷贝到windows
            cmd_code, cmd_stdout, cmd_stderr = WindowsCommandOperation.exec_win_cmd(
                scp_file_cmd, ssh_ip=windows_ip, ssh_port=source_port, pwd='Perseus;1234')
            # 处理远程拷贝结果
            rtn_code = CommandOperation.check_cli_output(scp_file_cmd, cmd_code, cmd_stdout, cmd_stderr)

            if RtnStatusEnum.SUCCESS.value == rtn_code:
                log.info('Success to scp windows file path: {}@{}[{}]:{} to target file path: {}@{}[{}]:{}.'.format(
                    source_username, windows_ip, source_port, source_file_path, target_username, target_ip,
                    target_port, target_file_path))
            else:
                rtn_scp_file = RtnStatusEnum.FAIL.value

        return rtn_scp_file

    @classmethod
    def scp_file(cls, source_file_path: str, target_file_path: str, source_ip: str = None, source_port: str = '22',
                 source_username: str = 'root', target_ip: str = None, target_port: str = '22',
                 target_username: str = 'root', cmd_execute_address: str = None, local_execute: bool = False,
                 clear_target_file: bool = False, print_enable: bool = True):
        """
        author:      haibin.xu
        date:        2021-03-16 17:03:55
        description: 远程拷贝文件

        :param source_file_path: 源文件路径
        :param target_file_path: 目标文件路径
        :param source_ip: 源文件所在server ip
        :param source_port: 源文件所在server port
        :param source_username: 源文件所在server 登录用户名
        :param target_ip: 目标文件所在server ip
        :param target_port: 目标文件所在server port
        :param target_username: 目标文件所在server 登录用户名
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选
        :param local_execute: 是否本地执行，即拷贝本地文件到远程目标地址
        :param clear_target_file:是否清理目标地址文件
        :param print_enable:
        :return:     命令执行成功，返回0，否则返回-1

        @changelog  2021.8.3    sunql
                    1、增加 clear_target_file 开关
                    2、增加 清理目标环境文件逻辑
        """
        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            source_port = str(test_port)
            target_port = str(test_port)

        if CommandOperation.check_windows_cmd(ssh_ip=target_ip):
            if source_ip is None:
                source_ip = constants.HOST_NODE_IP
            return cls.scp_file_to_window(source_file_path=source_file_path, target_file_path=target_file_path,
                                          source_ip=source_ip, source_port=source_port,
                                          source_username=source_username, windows_ip=target_ip,
                                          clear_target_file=clear_target_file)

        rtn_scp_file = RtnStatusEnum.FAIL.value
        source_ip_valid_flag = True
        target_ip_valid_flag = True

        if (source_ip is None) and (cmd_execute_address is None) and (not local_execute):
            log.error('Not given valid source ip: {}, or cmd_execute_address value: {}.'.format(
                source_ip, cmd_execute_address))
            rtn_scp_file = RtnStatusEnum.FAIL.value
            source_ip_valid_flag = False

        if source_ip_valid_flag:
            if target_ip is None:
                log.error('Not given valid target ip: {}.'.format(target_ip))
                rtn_scp_file = RtnStatusEnum.FAIL.value
                target_ip_valid_flag = False

        if source_ip_valid_flag and target_ip_valid_flag:
            # 清理远程环境文件
            if clear_target_file:
                log.info('delete target file: {}'.format(target_file_path))
                cls.delete_file(path=target_file_path, ip=target_ip, port=target_port, match_flag=False)
            # 拼接拷贝命令
            scp_file_cmd = 'scp -o StrictHostKeyChecking=no -P {} {} {}@{}:{}'.format(
                target_port, source_file_path, target_username, target_ip, target_file_path)
            # 执行远程拷贝
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                scp_file_cmd, cmd_execute_address=cmd_execute_address, ssh_ip=source_ip, ssh_port=source_port,
                ssh_username=source_username, local_execute_flag=local_execute, print_enable=print_enable)
            # 处理远程拷贝结果
            rtn_code = CommandOperation.check_cli_output(scp_file_cmd, cmd_code, cmd_stdout, cmd_stderr)

            if RtnStatusEnum.SUCCESS.value == rtn_code:
                rtn_scp_file = RtnStatusEnum.SUCCESS.value
                log.debug('Success to scp source file path: {}@{}[{}]:{} to target file path: {}@{}[{}]:{}.'.format(
                    source_username, source_ip, source_port, source_file_path, target_username, target_ip,
                    target_port, target_file_path))
            else:
                # hejf add 2024.10.10
                log.warning("使用scp命令拷贝失败，尝试使用scp -O")
                # 拼接拷贝命令
                scp_file_cmd = 'scp -O -o StrictHostKeyChecking=no -P {} {} {}@{}:{}'.format(
                    target_port, source_file_path, target_username, target_ip, target_file_path)
                # 执行远程拷贝
                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    scp_file_cmd, cmd_execute_address=cmd_execute_address, ssh_ip=source_ip, ssh_port=source_port,
                    ssh_username=source_username, local_execute_flag=local_execute, print_enable=print_enable)
                # 处理远程拷贝结果
                rtn_code = CommandOperation.check_cli_output(scp_file_cmd, cmd_code, cmd_stdout, cmd_stderr)

                if RtnStatusEnum.SUCCESS.value == rtn_code:
                    rtn_scp_file = RtnStatusEnum.SUCCESS.value
                    log.debug('Success to scp source file path: {}@{}[{}]:{} to target file path: {}@{}[{}]:{}.'.format(
                        source_username, source_ip, source_port, source_file_path, target_username, target_ip,
                        target_port, target_file_path))
                else:
                    rtn_scp_file = RtnStatusEnum.FAIL.value

        return rtn_scp_file

    @classmethod
    def target_scp_file(cls, source_file_path: str, target_file_path: str, source_ip: str = None,
                        source_port: str = '22',
                        source_username: str = 'root', target_ip: str = None, target_port: str = '22',
                        target_username: str = 'root', cmd_execute_address: str = None, local_execute: bool = False,
                        clear_target_file: bool = False, print_enable: bool = True):
        """
        author:      sunql
        date:        2021-03-16 17:03:55
        description: 从目标服务器发起scp命令拷贝文件到目标服务器本地

        :param source_file_path: 源文件路径
        :param target_file_path: 目标文件路径
        :param source_ip: 源文件所在server ip
        :param source_port: 源文件所在server port
        :param source_username: 源文件所在server 登录用户名
        :param target_ip: 目标文件所在server ip
        :param target_port: 目标文件所在server port
        :param target_username: 目标文件所在server 登录用户名
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选
        :param local_execute: 是否本地执行，即拷贝本地文件到远程目标地址
        :param clear_target_file:是否清理目标地址文件
        :param print_enable:
        :return:     命令执行成功，返回0，否则返回-1

        @changelog  2021.8.3    sunql
                    1、增加 clear_target_file 开关
                    2、增加 清理目标环境文件逻辑
        """

        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            source_port = str(test_port)
            target_port = str(test_port)

        if CommandOperation.check_windows_cmd(ssh_ip=target_ip):
            if source_ip is None:
                source_ip = constants.HOST_NODE_IP
            return cls.scp_file_to_window(source_file_path=source_file_path, target_file_path=target_file_path,
                                          source_ip=source_ip, source_port=source_port,
                                          source_username=source_username, windows_ip=target_ip,
                                          clear_target_file=clear_target_file)

        rtn_scp_file = RtnStatusEnum.FAIL.value
        source_ip_valid_flag = True
        target_ip_valid_flag = True

        if (source_ip is None) and (not local_execute):
            log.error('Not given valid source ip: {}, or cmd_execute_address value: {}.'.format(
                source_ip, cmd_execute_address))
            rtn_scp_file = RtnStatusEnum.FAIL.value
            source_ip_valid_flag = False

        if source_ip_valid_flag:
            if target_ip is None:
                log.error('Not given valid target ip: {}.'.format(target_ip))
                rtn_scp_file = RtnStatusEnum.FAIL.value
                target_ip_valid_flag = False

        if source_ip_valid_flag and target_ip_valid_flag:
            # 清理目标服务器环境文件
            if clear_target_file:
                log.info('delete target file: {}'.format(target_file_path))
                cls.delete_file(path=target_file_path, ip=target_ip, port=target_port, match_flag=False)
            # 拼接拷贝命令 scp
            scp_file_cmd = 'scp -o StrictHostKeyChecking=no -P {} {}@{}:{} {}'.format(
                target_port, source_username, source_ip, source_file_path, target_file_path)
            # 执行远程拷贝
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                scp_file_cmd, ssh_ip=target_ip, ssh_port=target_port,
                ssh_username=target_username, local_execute_flag=local_execute, print_enable=print_enable)
            # 处理远程拷贝结果
            rtn_code = CommandOperation.check_cli_output(scp_file_cmd, cmd_code, cmd_stdout, cmd_stderr)

            if RtnStatusEnum.SUCCESS.value == rtn_code:
                rtn_scp_file = RtnStatusEnum.SUCCESS.value
                log.debug('Success to scp source file path: {}@{}[{}]:{} to target file path: {}@{}[{}]:{}.'.format(
                    source_username, source_ip, source_port, source_file_path, target_username, target_ip,
                    target_port, target_file_path))
            else:
                # hejf add 2024.10.10
                log.warning("使用scp命令拷贝失败，尝试使用scp -O")
                # 拼接拷贝命令 scp
                scp_file_cmd = 'scp -O -o StrictHostKeyChecking=no -P {} {}@{}:{} {}'.format(
                    target_port, source_username, source_ip, source_file_path, target_file_path)
                # 执行远程拷贝
                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    scp_file_cmd, ssh_ip=target_ip, ssh_port=target_port,
                    ssh_username=target_username, local_execute_flag=local_execute, print_enable=print_enable)
                # 处理远程拷贝结果
                rtn_code = CommandOperation.check_cli_output(scp_file_cmd, cmd_code, cmd_stdout, cmd_stderr)
                if RtnStatusEnum.SUCCESS.value == rtn_code:
                    rtn_scp_file = RtnStatusEnum.SUCCESS.value
                    log.debug('Success to scp source file path: {}@{}[{}]:{} to target file path: {}@{}[{}]:{}.'.format(
                        source_username, source_ip, source_port, source_file_path, target_username, target_ip,
                        target_port, target_file_path))
                else:
                    rtn_scp_file = RtnStatusEnum.FAIL.value

        return rtn_scp_file

    @classmethod
    def get_file_size(cls, file_path: str, local_execute: bool = False, ip: str = None, port: str = '22',
                      username: str = None, file_check_flag: bool = True) -> int:
        """
        author:      haibin.xu
        date:        2021-04-08 14:43:05
        description: 获取文件大小
        :param file_path: 给定的文件路径
        :param local_execute: 本地执行标志位
        :param ip:   指定远程执行命令的ip
        :param port: 指定远程执行命令的port
        :param username: ssh连接登录用户
        :param file_check_flag: 是否检查文件路径有效性
        :return:     返回文件大小
        """
        file_size = None
        file_exist = True

        if file_check_flag and (RtnStatusEnum.FAIL.value == cls.file_path_exists(file_path, local_execute, ip,
                                                                                 port)):
            file_exist = False

        if file_exist:
            if local_execute:
                file_size = os.path.getsize(file_path)
            else:
                get_size_cmd = 'du -b {} | cut -f 1'.format(file_path)
                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    get_size_cmd, ssh_ip=ip, ssh_port=port, ssh_username=username)
                rtn_code = CommandOperation.check_cli_output(get_size_cmd, cmd_code, cmd_stdout, cmd_stderr)
                if (RtnStatusEnum.SUCCESS.value == rtn_code) and cmd_stdout.strip().isdigit():
                    file_size = int(cmd_stdout.strip())

        return file_size

    @classmethod
    def empty_file(cls, file_path: str, local_execute: bool = False, ip: str = None, port: str = '22',
                   username: str = None, match_flag: bool = True) -> int:
        """
        author:      haibin.xu
        date:        2020-08-31 16:12:51
        description: 清空文件内容
        :param file_path: 给定的文件路径
        :param local_execute: 本地执行标志位
        :param ip:   指定远程执行命令的ip
        :param port: 指定远程执行命令的port
        :param username: ssh连接登录用户
        :param match_flag: 是否对文件进行/root/ps3sim/.*模式匹配，
                           如果进行模式匹配，则只有匹配该模式才对文件进行操作
        :return:     文件清空操作成功，返回0， 失败返回-1

        @changelog      2021-03-13 10:59:50  haibin.xu
                        1. 优化函数实现，添加本地执行参数
                        2021-03-26 17:33:49  haibin.xu
                        1. 优化函数实现, 添加ip, port, username参数
        """
        rtn_empty_file = RtnStatusEnum.FAIL.value
        file_pattern_flag = True

        # 文件路径有效，且文件路径符合规定的路径白名单格式，则执行清空文件操作
        if not match_flag:
            log.info('Not need to match file path pattern: {}.'.format(cls.__PATH_PATTERN))
        elif match_flag and (RtnStatusEnum.SUCCESS.value == cls.__match_path_pattern(file_path)):
            log.info('Match the file path pattern: {}.'.format(cls.__PATH_PATTERN))
        else:
            file_pattern_flag = False

        if file_pattern_flag:
            if RtnStatusEnum.SUCCESS.value == cls.file_path_exists(file_path, local_execute, ip, port):
                file_size = cls.get_file_size(file_path, local_execute, ip, port, username, False)
                if 0 == file_size:
                    # 文件大小为0， 无需再进行清空操作
                    log.info('Not need to empty file: {}, in server: {}:{}, file size is 0.'.format(file_path, ip,
                                                                                                    port))
                    rtn_empty_file = RtnStatusEnum.SUCCESS.value
                elif file_size:
                    # file_size不为0时，进行清空操作
                    # 清空文件命令
                    empty_file_cmd = 'cat /dev/null > {}'.format(file_path)
                    # 命令执行
                    cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                        empty_file_cmd, local_execute_flag=local_execute, ssh_ip=ip, ssh_port=port,
                        ssh_username=username)
                    rtn_empty_file = CommandOperation.check_cli_output(empty_file_cmd, cmd_code, cmd_stdout,
                                                                       cmd_stderr)
                else:
                    # file_size为None时，不再进行清空操作
                    log.error('Can not get file size, not to next empty file.')
            else:
                # 文件不存在时，无需进行清空操作
                log.warning('Not found file: {}, in server: {}:{}'.format(file_path, ip, port))
                rtn_empty_file = RtnStatusEnum.SUCCESS.value

        return rtn_empty_file

    @classmethod
    def __get_md5(cls, file_path: str) -> str:
        """
        author:      haibin.xu
        date:        2020-11-03 08:49:18
        description: Windows系统下计算文件的md5值

        :param file_path: 文件路径
        :return:     返回文件的md5值
        """
        hash_obj = hashlib.md5()
        fp = open(file_path, 'rb')

        while True:
            bts = fp.read(8096)
            if not bts:
                break
            hash_obj.update(bts)

        fp.close()
        return hash_obj.hexdigest()

    @classmethod
    def get_md5(cls, path: str, path_flag: bool = False, ip: str = None, port: str = '22', username: str = 'root',
                with_error: bool = False):
        """
        author: jing.li
        date: 2020.07.9
        description: MD5校验函数
        :param path:文件路径
        :param path_flag: 是否在本地查找路径，True表示在本地查找，False表示在远程server查找
        :param ip:   指定远程执行命令的ip
        :param port: 指定远程执行命令的port
        :param username: 指定远程执行命令的登录用户名
        :param with_error: 是否返回错误信息
        :return: 文件md5值获取成功，返回md5值，失败返回空, with_error为True时返回tuple(md5, error_msg)
        """
        rtn_md5 = constants.STR_EMPTY
        err_msg = constants.STR_EMPTY
        if RtnStatusEnum.SUCCESS.value == cls.file_path_exists(path, path_flag, ip, port, username):
            if (platform.system() == 'Windows') and path_flag:
                rtn_md5 = cls.__get_md5(path)
            else:
                check_path_cmd = 'md5sum {}'.format(path)
                if CommandOperation.check_windows_cmd(ssh_ip=ip) and not path_flag:
                    check_path_cmd = f"Get-FileHash {path} -Algorithm md5 |  Format-Wide Hash"
                log.info(check_path_cmd)
                cmd_code, cmd_stdout, _ = CommandOperation.execute_command_with_error(
                    check_path_cmd, local_execute_flag=path_flag, ssh_ip=ip, ssh_port=port, ssh_username=username,
                    print_enable=False)
                if RtnStatusEnum.SUCCESS.value == cmd_code:
                    md5_obj = re.compile(constants.PATTERN_MD5).match(cmd_stdout)
                    rtn_md5 = md5_obj.group() if md5_obj else constants.STR_EMPTY
        else:
            log.error('Invalid file path: {}'.format(path))
            err_msg = 'cannot access {}: No such file or directory.'.format(path)
        if with_error:
            return rtn_md5, err_msg
        return rtn_md5

    @classmethod
    def check_md5(cls, path_pre: str, path_next: str) -> bool:
        """
        author: jing.li
        date: 2020.07.9
        description: 校验MD5
        :param path_pre: 一个文件路径
        :param path_next: 另一个文件路径
        :return:两个文件的MD5是否一致
        """
        return cls.get_md5(path_pre) == cls.get_md5(path_next)

    @staticmethod
    def normalize_path(path: str) -> str:
        """
        author: haibin.xu
        date: 2020.07.20
        description: 路径分隔符一致化，使路径中的分隔符统一为 os.sep
        :param path: 需要一致化操作的路径
        :return: 返回一致化处理后的路径
        """
        return path.replace('/', os.sep)

    @classmethod
    def delete_file(cls, path: str, localpath_flag: bool = False, ip: str = None, port: str = None,
                    username: str = None, match_flag: bool = True,
                    file_check_flag: bool = True, print_enable: bool = True, match_pattern: str = "",
                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value
                    ) -> tuple:
        """
        author: jing.li
        date: 2020.07.24
        description: 删除指定文件或目录下的所有文件
        :param path: 文件的路径
        :param localpath_flag: 是否在本地查找路径，True表示在本地查找，False表示在远程server查找
        :param ip:   指定远程执行命令的ip
        :param port: 指定远程执行命令的port
        :param username: ssh连接登录用户
        :param match_flag: 是否对文件进行/root/ps3sim/.*模式匹配，
                           如果进行模式匹配，则只有匹配该模式才进行删除操作
        :param file_check_flag: 是否检查文件路径有效性
        :param print_enable: 是否print
        :param cmd_execute_address:执行端方向
        :param match_pattern: 文件路径校验pattern
        :return: 返回(0 删除成功; -1 删除成功);状态信息

        @changelog      2021-03-15 17:10:08  haibin.xu
                        1. 优化函数实现, 添加localpath_flag, ip, port参数
        """
        rtn_code = RtnStatusEnum.SUCCESS.value
        file_exists_flag = RtnStatusEnum.SUCCESS.value
        cmd_stdout = constants.STR_EMPTY
        file_pattern_flag = True

        test_port = CommandLineArgsParse.get_test_port()
        if test_port:
            port = str(test_port)

        # 文件路径有效，且文件路径符合规定的路径白名单格式，则执行清空文件操作
        if not match_pattern:
            match_pattern = cls.__PATH_PATTERN
        if not match_flag:
            log.debug('Not need to match file path pattern: {}.'.format(match_pattern))
        elif match_flag and (RtnStatusEnum.FAIL.value == cls.__match_path_pattern(path, match_pattern)):
            rtn_code = RtnStatusEnum.FAIL.value
            file_pattern_flag = False

        if file_pattern_flag:
            if file_check_flag:
                file_exists_flag, _ = cls.path_exists(path, ip=ip, port=port, localpath_flag=localpath_flag,
                                                      username=username)
            # 如果文件路径有效，且文件路径符合规定的路径白名单格式，则执行删除文件操作
            if RtnStatusEnum.SUCCESS.value == file_exists_flag:
                delete_cmd = 'rm -rf {}'.format(path)

                if CommandOperation.check_windows_cmd(ssh_ip=ip, local_execute_flag=localpath_flag):
                    path = path.replace(' ', ',')
                    delete_cmd = 'rm -r -fo {}'.format(path)

                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                    delete_cmd, local_execute_flag=localpath_flag, cmd_execute_address=cmd_execute_address,
                    ssh_ip=ip, ssh_port=port, ssh_username=username, print_enable=print_enable)
                rtn_code = CommandOperation.check_cli_output(delete_cmd, cmd_code, cmd_stdout, cmd_stderr)
            else:
                log.warning('Not found file: {}, not need to delete.'.format(path))

        return rtn_code, cmd_stdout

    @classmethod
    def get_files(cls, file_path: str, path_flag: bool = False, ip: str = None, port: str = '22',
                  detect_file_size_flag: bool = False) -> tuple:
        """
        author:      haibin.xu
        date:        2021-03-15 11:50:19
        description: 获取指定路径下的文件
        :param file_path:文件路径
        :param path_flag: 是否在本地查找路径，True表示在本地查找，False表示在远程server查找
        :param ip:   指定远程执行命令的ip
        :param port: 指定远程执行命令的port
        :param detect_file_size_flag: 查询正在生成的文件标志位，对于一些正在生成的文件，其大小是一直在变动的，
                    需要循环查询该文件，直到其大小固定不变为止
        :return:    返回命令执行结果，文件列表

        @changelog      2021-10-12 11:00:46  haibin.xu
                        1. 优化函数实现, 增加参数detect_file_size_flag
        """
        rtn_files_list = []
        cmd_code = RtnStatusEnum.SUCCESS.value
        files_list = [fl.strip() for fl in file_path.split(' ') if fl.strip()]
        for file in files_list:
            if detect_file_size_flag:
                # $5, $NF分别为文件size,文件名
                get_files_cmd = 'ls -l {} | awk \'{{print $5,$NF}}\''.format(file)
                cmdout = ''
                start_time = datetime.now()
                end_time = start_time
                # 检查文件次数
                check_times = 5
                # 循环查询该文件（文件size一直增加），超过5分钟，强制停止
                while (end_time - start_time).seconds <= 300:
                    cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        get_files_cmd, local_execute_flag=path_flag, ssh_ip=ip, ssh_port=port, print_enable=False)
                    if RtnStatusEnum.SUCCESS.value == cmd_code:
                        if cmdout != cmd_stdout:
                            cmdout = cmd_stdout
                            # 等待两秒
                            time.sleep(2)
                            # 记录当前时间
                            end_time = datetime.now()
                        else:
                            if '' != cmdout:
                                # 文件大小不再变动时，停止查询
                                break
                            else:
                                # 输出返回为空，检查次数 -1, 检查次数为0时，直接退出循环
                                if 0 != check_times:
                                    check_times -= 1
                                    time.sleep(2)
                                else:
                                    break
                    else:
                        log.warning('Not found file: {}, stderr: {}'.format(file, cmd_stderr))
                        break
                if cmdout:
                    cmdout_lines = [cl.strip() for cl in cmdout.strip().splitlines() if cl.strip()]
                    for cl in cmdout_lines:
                        # 每一行包含文件大小和文件名两个元素
                        cl_list = cl.split()
                        if 2 == len(cl_list):
                            rtn_files_list.append(cl_list[1].strip())
            else:
                get_files_cmd = 'ls {}'.format(file)
                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    get_files_cmd, local_execute_flag=path_flag, ssh_ip=ip, ssh_port=port)
                if RtnStatusEnum.SUCCESS.value == cmd_code:
                    rtn_files_list.extend([fl.strip() for fl in cmd_stdout.strip().split() if fl.strip()])
                else:
                    log.warning('Not found file: {}, stderr: {}'.format(file, cmd_stderr))

        return cmd_code, rtn_files_list

    @classmethod
    def get_files_with_cmd(cls, find_files_cmd: str, path_flag: bool = False, ip: str = None, port: str = '22',
                           print_enable: bool = True) -> tuple:
        """
        author:      haibin.xu
        date:        2021-03-24 14:40:37
        description: 通过给定的命令获取文件

        :param find_files_cmd: 搜索文件的命令
        :param path_flag: 是否在本地查找路径，True表示在本地查找，False表示在远程server查找
        :param ip:   指定远程执行命令的ip
        :param port: 指定远程执行命令的port
        :param print_enable:
        :return:     返回执行命令结果和文件列表
        """
        rtn_files_list = []
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            find_files_cmd, local_execute_flag=path_flag, ssh_ip=ip, ssh_port=port, print_enable=print_enable)
        rtn_code = CommandOperation.check_cli_output(find_files_cmd, cmd_code, cmd_stdout, cmd_stderr)
        if RtnStatusEnum.SUCCESS.value == rtn_code:
            rtn_files_list = cmd_stdout.strip().split()

        return rtn_code, rtn_files_list

    @classmethod
    def compress_files(cls, file_path: str, tar_file_path: str, localpath_flag: bool = False, ip: str = None,
                       port: str = '22', username: str = 'root',
                       is_pigz: bool = True, tar_params: str = '-Phcf') -> int:
        """
        author:      haibin.xu
        date:        2021-03-16 15:20:58
        description: 文件压缩

        :param file_path: 待压缩的文件路径
        :param tar_file_path: 压缩后的文件路径
        :param localpath_flag: 本地执行标志位
        :param ip:   ssh 连接ip
        :param port: ssh 连接port
        :param username: ssh连接登录用户
        :param is_pigz: pigz标志位
        :param tar_params: tar 参数
        :return:     文件成功压缩，返回0， 否则返回-1

        @changelog      2022-03-07 11:29:14  haibin.xu
                        1. 优化函数实现, 不使用pigz时， -Phcf -> -Phzcf
        """
        rtn_compress = RtnStatusEnum.SUCCESS.value

        # 打包命令 -h 可以将软连接中的链接文件打包，-P 允许使用绝对路径进行压缩打包
        if username == 'Administrator':
            compress_file_cmd = "tar {} {} {}".format(tar_params, tar_file_path, file_path)
        else:
            compress_file_cmd = 'tar --warning=no-file-changed {} - {} | pigz -p 4 > {}'.format(tar_params,
                                                                                                file_path,
                                                                                                tar_file_path)
            if not is_pigz:
                # haibin.xu 2022-03-07 11:29:14 modify: -Phcf -> -Phzcf，不使用pigz进行压缩时，直接使用tar -Phzcf命令，
                # 这样生成的*.tar.gz压缩包才是真正的gz格式
                tar_params = str(tar_params).replace('hcf', 'hzcf')
                if not localpath_flag:
                    file_path = str(file_path).rstrip('/').split('/')
                    new_path = '/'.join(file_path[:-1]) + f' {file_path[-1]}'
                    compress_file_cmd = 'tar --warning=no-file-changed {} {} -C {}'.format(tar_params,
                                                                                           tar_file_path, new_path)
                else:
                    compress_file_cmd = 'tar --warning=no-file-changed {} {} {}'.format(tar_params,
                                                                                        tar_file_path, file_path)

        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
            compress_file_cmd, local_execute_flag=localpath_flag, ssh_ip=ip,
            ssh_port=port, ssh_username=username, timeout=3600)
        rtn_code = CommandOperation.check_cli_output(compress_file_cmd, cmd_code, cmd_stdout, cmd_stderr)
        if RtnStatusEnum.FAIL.value == rtn_code:
            if '' != cmd_stderr:
                log.error('Fail to compress file: {} to {} in server: root@{}. Reason: {}'.format(
                    file_path, tar_file_path, ip, cmd_stderr))
                rtn_compress = RtnStatusEnum.FAIL.value
            else:
                log.warning('Not found error message. affirm compress success.')

        return rtn_compress

    @classmethod
    def uncompress_file(cls, tar_file_path: str, untar_file_path: str = None, localpath_flag: bool = False,
                        ip: str = None, port: str = '22', username: str = 'root', match_flag: bool = True,
                        make_untardir_flag: bool = True) -> int:
        """
        author:      haibin.xu
        date:        2021-03-16 19:24:57
        description: 解压缩文件

        :param file_path: 待解压的文件路径
        :param tar_file_path: 解压后的文件路径
        :param localpath_flag: 本地执行标志位
        :param ip:   ssh 连接ip
        :param port: ssh 连接port
        :param username: ssh连接登录用户
        :param match_flag: 是否对文件进行/root/ps3sim/.*模式匹配，
                           如果进行模式匹配，则只有匹配该模式才对文件进行操作
        :param make_untardir_flag: untar_file_path路径有效时，是否重新创建该目录标志位
        :return:     文件成功解压，返回0， 否则返回-1
        """
        rtn_uncompress = RtnStatusEnum.SUCCESS.value

        if untar_file_path is not None:
            if make_untardir_flag:
                mkdir_flag = cls.make_directory(dir_name=untar_file_path, ip=ip, port=port, username=username,
                                                match_flag=match_flag)
            else:
                mkdir_flag = RtnStatusEnum.SUCCESS.value
        else:
            mkdir_flag = RtnStatusEnum.SUCCESS.value
            untar_file_path = './'

        if RtnStatusEnum.SUCCESS.value == mkdir_flag:
            uncompress_file_cmd = 'tar -xf {} -C {}'.format(tar_file_path, untar_file_path)
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                uncompress_file_cmd, local_execute_flag=localpath_flag, ssh_ip=ip, ssh_port=port,
                ssh_username=username)
            rtn_code = CommandOperation.check_cli_output(uncompress_file_cmd, cmd_code, cmd_stdout, cmd_stderr)
            if RtnStatusEnum.FAIL.value == rtn_code:
                log.error('Fail to uncompress file: {} to {} in server: root@{}. Reason: {}'.format(
                    tar_file_path, untar_file_path, ip, cmd_stderr))
                rtn_uncompress = RtnStatusEnum.FAIL.value
        else:
            log.error('Fail to make directory: {}'.format(untar_file_path))
            rtn_uncompress = RtnStatusEnum.FAIL.value

        return rtn_uncompress

    @classmethod
    def find_files(cls, path: str = None, path_flag: bool = False, ip: str = None, port: str = '22',
                   username: str = 'root') -> tuple:
        """
        author:      haibin.xu
        date:        2021-05-15 16:46:27
        description: 查找文件是否存在, 并返回已存在的文件

        :param path:待检查的文件名
        :param path_flag: 是否为本地路径
        :param ip:   文件所在服务器ip
        :param port: 文件所在服务器port
        :param username: 文件所在服务器登录用户名
        :return:     并以列表形式返回已存在的文件
        """
        rtn_code = RtnStatusEnum.SUCCESS.value
        rtn_files = ''
        files_list = []

        # 检查path
        if path is not None:
            files_list = [fl.strip() for fl in path.split(' ') if fl.strip()]
        else:
            log.error('Not found valid path: {}.'.format(path))

        if files_list:
            check_path_cmd = 'ls -ld {} | awk \'{{print $NF}}\''.format(path)
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=check_path_cmd, local_execute_flag=path_flag, ssh_ip=ip, ssh_port=port,
                ssh_username=username)
            if RtnStatusEnum.SUCCESS.value == cmd_code:
                rtn_code = RtnStatusEnum.SUCCESS.value
                if cmd_stdout:
                    stdout_list = [out.strip() for out in cmd_stdout.splitlines() if out.strip()]
                    rtn_files = ' '.join(stdout_list)
            else:
                all_out_list = []
                not_exist_files_list = []
                exist_files_list = copy.deepcopy(files_list)
                if cmd_stdout:
                    all_out_list.extend([le.strip() for le in cmd_stdout.splitlines() if le.strip()])
                if cmd_stderr:
                    all_out_list.extend([le.strip() for le in cmd_stderr.splitlines() if le.strip()])

                for out_file in all_out_list:
                    if 'ls:' not in out_file:
                        continue

                    for fl in files_list:
                        if fl in out_file:
                            not_exist_files_list.append(fl)
                            exist_files_list.remove(fl)

                if not_exist_files_list and exist_files_list:
                    log.warning('Not found some files in files list: {}, only return found files.'.format(
                        not_exist_files_list))

                rtn_code = RtnStatusEnum.FAIL.value
                rtn_files = ' '.join(exist_files_list)

        return rtn_code, rtn_files

    @classmethod
    def delete_fake_block_file(cls, target_path: str = '/dev/sd*', ssh_ip: str = None, ssh_port: str = None,
                               ssh_username: str = 'root') -> None:
        """
        author:      haibin.xu
        date:        2021-06-16 17:20:05
        description: 删除指定server指定目录下假的块文件设备，即文件名与块设备文件名类似，但不是块设备

        :param target_path: 目标路径
        :param ssh_ip: 指定server的ip
        :param ssh_port: 指定server的port
        :param ssh_username: 指定server登录用户名
        :return:    None
        """
        # 查找目标文件，并打印第一列和最后一列，如：-rw-r--r-- /dev/sdh
        get_target_file_cmd = 'ls -l {} | awk \'{{print $1, $NF}}\''.format(target_path)

        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
            cmd=get_target_file_cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
        rtn_code = CommandOperation.check_cli_output(get_target_file_cmd, cmd_code, cmd_stdout, cmd_stderr)

        fake_block_file_list = []
        # 命令执行成功，并且有输出
        if (RtnStatusEnum.SUCCESS.value == rtn_code) and cmd_stdout:
            # 按行分隔为target_file_list列表
            target_file_list = [out.strip() for out in cmd_stdout.splitlines() if out.strip()]
            for fl in target_file_list:
                # 如果每一行中匹配到target_path，且该行第一个字符为'-'时，以空格分隔改行，获取有效分隔元素
                fl_list = [fl_s.strip() for fl_s in fl.split(constants.STR_SPACE) if fl_s.strip()] if \
                    re.search(target_path, fl) and (cls.__LINUX_FILE_FLAG == fl[0]) else []
                # 匹配获取成功后，fl_list应该只有两个元素，即-rw-r--r--和/dev/sdh
                if (2 == len(fl_list)):
                    fake_block_file_list.append(fl_list[1])

        server_ip = ssh_ip if ssh_ip else 'cli deploy ip'

        if fake_block_file_list:
            log.info('Found fake block files: {}, in server: {}'.format(fake_block_file_list, server_ip))
        else:
            log.info('Not found any fake block file in server: {}'.format(server_ip))

        for fake_file in fake_block_file_list:
            delete_code, _ = cls.delete_file(path=fake_file, ip=ssh_ip, port=ssh_port, username=ssh_username,
                                             match_flag=False, file_check_flag=False)
            if RtnStatusEnum.SUCCESS.value == delete_code:
                log.info('Success to delete fake block file: {}, in server: {}'.format(fake_file, server_ip))
            else:
                log.info('Fail to delete fake block file: {}, in server: {}'.format(fake_file, server_ip))

    @classmethod
    def modify_file_permission(cls, file_path: str = None, mode: str = '+x', ssh_ip: str = None,
                               ssh_port: str = None, ssh_username: str = 'root') -> int:
        """
        author:      haibin.xu
        date:        2021-06-21 11:34:34
        description: 修改文件权限

        :param file_path: 待修改文件权限的路径
        :param mode: 设置的权限
        :param ssh_ip: 文件所在的server ip
        :param ssh_port: 文件所在的server port
        :param ssh_username: 文件所在的server 登录用户名
        :return: 文件修改成功，返回0， 否则返回-1
        """
        rtn_code = RtnStatusEnum.FAIL.value
        if file_path is None:
            log.error('Invalid file path: {}'.format(file_path))
        else:
            modify_file_permission_cmd = 'chmod {} {}'.format(mode, file_path)
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                cmd=modify_file_permission_cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
            rtn_code = CommandOperation.check_cli_output(modify_file_permission_cmd, cmd_code, cmd_stdout,
                                                         cmd_stderr)

        return rtn_code

    @staticmethod
    def check_module_exists(module: str = None, ssh_ip: str = None, ssh_port: str = None,
                            ssh_username: str = 'root') -> int:
        """
        author:      haibin.xu
        date:        2021-06-24 20:31:13
        description: 查看指定模块是否存在

        :param module: 指定模块名
        :param ssh_ip: 查看指定模块操作的server ip
        :param ssh_port: 查看指定模块操作的server port
        :param ssh_username: 查看指定模块操作的server 登录用户名
        :return: 模块存在返回0， 不存在返回-1
        """
        if module is None:
            log.error('Invalid module: {}'.format(module))
            rtn_code = RtnStatusEnum.FAIL.value
        else:
            check_mod_cmd = 'lsmod | awk \'{{print $1}}\' | grep \'^{}$\''.format(module)
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                cmd=check_mod_cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
            rtn_code = CommandOperation.check_cli_output(check_mod_cmd, cmd_code, cmd_stdout, cmd_stderr)

        return rtn_code

    @staticmethod
    def remove_module(module: str = None, ssh_ip: str = None, ssh_port: str = None,
                      ssh_username: str = 'root') -> int:
        """
        author:      haibin.xu
        date:        2021-06-24 20:52:08
        description: 卸载指定模块

        :param module: 指定模块名
        :param ssh_ip: 查看指定模块操作的server ip
        :param ssh_port: 查看指定模块操作的server port
        :param ssh_username: 查看指定模块操作的server 登录用户名
        :return: 卸载成功返回0， 卸载失败返回-1
        """
        if module is None:
            log.error('Invalid module: {}'.format(module))
            rtn_code = RtnStatusEnum.FAIL.value
        else:
            remove_mod_cmd = 'rmmod {}'.format(module)
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                cmd=remove_mod_cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
            rtn_code = CommandOperation.check_cli_output(remove_mod_cmd, cmd_code, cmd_stdout, cmd_stderr)

        return rtn_code

    @staticmethod
    def install_module(module_file_path: str = None, ssh_ip: str = None, ssh_port: str = None,
                       ssh_username: str = 'root') -> int:
        """
        author:      haibin.xu
        date:        2021-06-25 11:15:02
        description: 加载指定模块

        :param module_file_path: 指定模块文件路径
        :param ssh_ip: 查看指定模块操作的server ip
        :param ssh_port: 查看指定模块操作的server port
        :param ssh_username: 查看指定模块操作的server 登录用户名
        :return: 加载成功返回0， 加载失败返回-1
        """
        if module_file_path is None:
            log.error('Invalid module: {}'.format(module_file_path))
            rtn_code = RtnStatusEnum.FAIL.value
        else:
            install_mod_cmd = 'insmod {}'.format(module_file_path)
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                cmd=install_mod_cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
            rtn_code = CommandOperation.check_cli_output(install_mod_cmd, cmd_code, cmd_stdout, cmd_stderr)

        return rtn_code

    @classmethod
    def create_symbolic_link(cls, source_path: str = None, link_directory_path: str = None,
                             local_execute_flag: bool = False, ssh_ip: str = None, ssh_port: str = None,
                             ssh_username: str = 'root', path_check_flag: bool = True) -> int:
        """
        author:      haibin.xu
        date:        2021-07-02 14:38:45
        description: 创建文件或目录软连接

        :param source_file_path: 源文件或目录路径
        :param link_directory_path: 链接目录路径
        :param local_execute_flag: 是否在本地执行
        :param ssh_ip: 源文件或目录所在server ip
        :param ssh_port: 源文件或目录所在server port
        :param ssh_username: 源文件或目录所在server 登录用户名
        :param path_check_flag: 检查路径是否存在标志位
        :return: 软连接创建成功返回0，失败返回-1
        changelog:  sunql    调整ln -s 生成逻辑，拆分为多次生成，避免 ln -s 参数过长导致的linux cmd error
        """
        valid_spath_list = []
        rtn_create_link = RtnStatusEnum.FAIL.value

        # 判断source_path, link_file_path路径是否有效，无效的话，报错退出
        if (not cls.__isvalid(source_path)) or (not cls.__isvalid(link_directory_path)):
            log.error('Invalid source path or link file path: {}, {}'.format(source_path, link_directory_path))
            return rtn_create_link

        if path_check_flag:
            # 检查source_path中的路径是否存在，不存在的话，报错退出，source_path可能包含多个文件或目录的路径，所以需要切片处理
            source_path_list = source_path.split()
            for spath in source_path_list:
                spath_exist_flag, _ = cls.path_exists(path=spath, ip=ssh_ip, port=ssh_port, print_enable=False,
                                                      localpath_flag=local_execute_flag, username=ssh_username)
                if RtnStatusEnum.SUCCESS.value == spath_exist_flag:
                    valid_spath_list.append(spath)

            if not cls.__isvalid(valid_spath_list):
                log.error('Not found file or directory: {}'.format(source_path))
                return rtn_create_link

            # 检查link_directory_path目录是否存在，不存在的话，报错退出
            link_file_path_exist_flag, _ = cls.path_exists(path=link_directory_path, ip=ssh_ip, print_enable=True,
                                                           port=ssh_port, localpath_flag=local_execute_flag,
                                                           username=ssh_username)
            if RtnStatusEnum.SUCCESS.value != link_file_path_exist_flag:
                log.error('Not found file or directory: {}'.format(link_directory_path))
                return rtn_create_link

            valid_spath = ' '.join(valid_spath_list)
        else:
            valid_spath = source_path

        def split_lst(lst):
            """
            author:sunql
            把大列表拆分为50一个的小列表
            :param lst:
            :return:
            """
            step = 50 if len(lst) > 50 else len(lst)
            rs = [lst[i:i + step] for i in range(0, len(lst), step)]
            return rs

        valid_spath_list = valid_spath.split()
        valid_spath_list = split_lst(valid_spath_list)

        for i in range(len(valid_spath_list)):
            valid_spath = ' '.join(valid_spath_list[i])
            # 创建软连接
            create_link_cmd = 'ln -s {} {}'.format(valid_spath, link_directory_path)
            cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                cmd=create_link_cmd, local_execute_flag=local_execute_flag, ssh_ip=ssh_ip, ssh_port=ssh_port,
                ssh_username=ssh_username, print_enable=True)
            rtn_create_link = CommandOperation.check_cli_output(create_link_cmd, cmd_code, cmd_stdout, cmd_stderr)

        return rtn_create_link

    @classmethod
    def find_keywords_with_file(cls, path: str, keywords: list, path_flag: bool = False, ip: str = None,
                                port: str = '22', username: str = 'root') -> bool:
        """
        author:      sunql
        date:        2021-09-30 19:53:01
        description: 判断文件中是否存在指定关键字
        :param keywords: 关键字list
        :param path: 给定路径
        :param path_flag: 是否在本地查找路径，True表示在本地查找，False表示在远程server查找
        :param ip:   指定远程执行命令的ip
        :param port: 指定远程执行命令的port
        :param username: 指定远程执行命令的登录用户名
        :return:     关键字存在返回true
        """

        if RtnStatusEnum.SUCCESS.value != FileOperation.file_path_exists(path=path, path_flag=path_flag,
                                                                         ip=ip, port=port, username=username):
            return False
        keywords = '|'.join(keywords)
        cmd = f'egrep "{keywords}" {path}'
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
            cmd=cmd, local_execute_flag=path_flag, ssh_ip=ip, ssh_port=port,
            ssh_username=username)
        if int(cmd_code) == 0 and cmd_stdout != '':
            return True
        return False

    @classmethod
    def file_transmission(cls, file_name: str, remote_file: str, ssh_ip: str, ssh_port: str) -> int:
        """
        author: WeiYuan
        date:   2020/08/29 10:20
        description: 進行文件传输，并对其进行压缩和解压缩
        :param file_name: 要进行传输的文件名
        :param remote_file: 远程文件
        :param ssh_port: 需要远程传输的端口
        :param ssh_ip: 需要远程传输的ip
        :return : True/False
        """
        # 将路径和文件分离
        transport_flag = RtnStatusEnum.FAIL.value
        remote_path, remote_files = os.path.split(remote_file)
        exist_return, exist_out = cls.path_exists(remote_path)
        if "windows" not in platform.platform().lower():
            file_name = file_name.replace('\\', '/')
        if exist_return == 0:
            transport_flag = CommandOperation.transport_file_with_paramiko(local_path=file_name,
                                                                           remote_path=remote_file,
                                                                           transport_type='upload',
                                                                           ssh_ip=ssh_ip,
                                                                           ssh_port=ssh_port
                                                                           )
        else:
            rtn_mkdir = cls.make_directory(remote_path)
            if rtn_mkdir == RtnStatusEnum.SUCCESS.value:
                log.info("make directory:{} Success".format(remote_path))
                transport_flag = CommandOperation.transport_file_with_paramiko(local_path=file_name,
                                                                               remote_path=remote_file,
                                                                               transport_type='upload',
                                                                               ssh_ip=ssh_ip,
                                                                               ssh_port=ssh_port
                                                                               )
            else:
                log.error('Error make directory: {} '.format(remote_path))
        return transport_flag

    @classmethod
    def get_specify_file_location(cls, specify_file: str):
        """
        author: wei.yuan
        date: 2022.09.01
        description:获取指定文件的路径
        """
        import sys
        cur_path = os.path.abspath(os.path.dirname(__file__))
        # 获取根目录，即ps3/test/esat
        root_path = os.path.dirname(cur_path)
        while True:
            if 'scripts' == os.path.basename(root_path):
                # 假设第一次遇到的 'test' 目录是所需要的 root_path
                sys.path.append(root_path)
                break
            elif root_path == '/':
                # 找到根目录, 还没遇到 'scripts' 报错退出
                raise ValueError
            else:
                # 继续向上找一级
                root_path = os.path.dirname(root_path)
                # 将根目录添加到环境变量
                sys.path.append(root_path)
        scripts_path = os.path.join(root_path, "script_libs\\rpc_service", specify_file)
        return scripts_path

    @classmethod
    def download_network_packet(cls, remote_file_path: str, remote_ssh_ip: str):
        """
        author: wei,yuan1
        date: 2022.09.06
        description: 从远端将文件下载到本地
        :param remote_file_path: 远程文件
        :param remote_ssh_ip: 远程的IP地址
        """
        download_rtn_code = cls.file_path_exists(path=remote_file_path, path_flag=False, ip=remote_ssh_ip)
        if download_rtn_code != RtnStatusEnum.SUCCESS.value:
            return download_rtn_code, None
        else:
            # 将文件下载到本地
            rtn_file_download_flag = cls.sftp_download_file(
                localfile_path=None,
                remotefile_path=remote_file_path,
                ip=remote_ssh_ip,
                with_error=True
            )
            download_rtn_code = rtn_file_download_flag
            return download_rtn_code

    @classmethod
    def findstr_keyword(cls, key_word: str, host_os: str,
                        cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        date: 2023.12.26
        description: 在windows中查找關鍵字
        :param key_word: 關鍵字
        :param host_os: 执行端os
        :param cmd_execute_address: 执行端方向
        :return:
        """
        """
        Get-ChildItem -Path $search_dir -Filter $file_pattern -Recurse | ForEach-Object {
        # 使用 Select-String 命令查找包含指定关键字的内容
        $content = Get-Content $_.FullName | Select-String -Pattern $keywords -AllMatches
        # 根据条件筛选文件
        if ($content.Matches.Count -ge $keywords.Count -and $_.Length -ge $min_size) {
            Write-Output $_.FullName
            }
        }   
        """
        result_code = RtnStatusEnum.FAIL.value
        if host_os == "windows":
            exec_command = f'Get-Content "C:\\sxe_log\\*.log" | Select-String -Pattern "{key_word}"'
        else:
            exec_command = "grep -i 'Tx hang' /var/log/sxe.*"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value and rtn_stdout != "":
            result_code = RtnStatusEnum.SUCCESS.value
        else:
            result_code = RtnStatusEnum.FAIL.value
        return result_code

    @classmethod
    def read_csv_file(cls, file_path: str) -> list:
        """
        author: junfeng.he
        date  : 2024.6.12
        description: 该函数用于读取csv配置文件
        :param file_path: 文件名路徑
        :return: list，表格的每一行是list的每个元素，每个元素又是一个字符类型的list,[['a','b',],]
        """
        result = []
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                result.append(row)
        # log.info('读csv文件完成: \n{}'.format(result))
        return result

    @classmethod
    def write_csv_file(cls, file_path: str, titles: list, items: list) -> None:
        """
        author: junfeng.he
        date  : 2024.6.12
        description: 该函数用于写csv文件
        :param file_path: 文件名路徑
        :param titles: []
        :param items: [[],]
        """
        # 写csv文件
        with open(file_path, 'w', encoding='utf-8', newline='') as write_file:
            csv_writer = csv.writer(write_file)
            csv_writer.writerow(titles)
            csv_writer.writerows(items)
        log.info('写csv文件完成: {}'.format(file_path))


if __name__ == '__main__':
    # file_name = "D:\\sxe_project\\saitta_test\\nic_test\sagitta_code
    # \\test\\esat\\scripts\\script_libs\\rpc_service" \
    #             "\\rpc_server.py"
    # print("!!!!!!!!!!!!!!!!!")
    # print(file_name)
    # f = open(file_name, "r", encoding="utf-8")
    # print(f)
    # try:
    #     f.read()
    # except Exception as e:
    #     print("111111")

    # FileOperation.uncompress_file(tar_file_path='/root/sxetest/current_tar/
    # feature_sagitta-1.0.0_f71f75e_20230313_212859.tar.gz',
    #                               untar_file_path='/root/sxetest/current_version', ip='10.17.21.128')
    a = FileOperation.get_files(file_path='/root/sxetest/current_tar', ip='10.17.21.128')
    print(a)
    # print(FileOperation.get_files(file_path='/root/sxetest/current_tar/'))
