#!/usr/bin/env python3
# -*- encoding=utf8 -*-
import time
import os
from scripts.script_libs import log
from framework.libs import constants
from scripts.script_libs.file_operation import FileOperation
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import TestObjectEnum, TestObjectStrEnum, TestEntryStrEnum, RtnStatusEnum, \
    CompileObjectStrEnum


class LogCollect(object):

    def __init__(self, framework_run_dict: dict):
        # 框架运行时产生的参数
        self.framework_run_dict = framework_run_dict
        # 日志服务器ip
        self.log_server_ip = self.framework_run_dict['ip_dict'].get(constants.ENV_LOG_SERVER_IP)
        # 日志服务器 用户
        self.log_server_account = self.framework_run_dict['ip_dict'].get(constants.ENV_LOG_SERVER_ACCOUNT,
                                                                         constants.ENV_LOG_SERVER_ACCOUNT_FRAMEWORK)
        # ps server ip
        self.ps3_server_ip = self.framework_run_dict['ip_dict'].get(constants.ENV_PS3_SERVER_IP)
        # 日志收集 初始路径
        self.log_root_dir_path = ''
        # 日志服务器存放日志文件脚本级别路径
        self.log_script_dir_path = ''
        # 需要收集的测试框架及脚本日志
        self.framework_log_dict = {}
        # ps3 server收集文件后的文件夹名和打包压缩后的文件名
        self.ps3_server_collect_path = 'test_server_log'
        self.ps3_server_collect_tar = 'test_server_log.tar.gz'

    def get_ip_port(self):
        return self.framework_run_dict['ip_dict']['server_ip'],\
               self.framework_run_dict['ip_dict'].get(constants.ENV_TEST_PORT)

    @staticmethod
    def __get_date_time(start_timestamp: float = None) -> tuple:
        """
        author:      haibin.xu
        date:        2021-03-29 09:20:10
        description: 获取当前日期、时间，用于ps3server中log目录名的生成
        :param start_timestamp: 给定的时间戳

        :return:     返回当前日期、时间
        """

        local_time = time.localtime(start_timestamp) if start_timestamp else time.localtime()
        log_dir_date = time.strftime('%Y_%m_%d', local_time)
        log_dir_time = time.strftime('%H_%M_%S', local_time)

        return log_dir_date, log_dir_time

    def make_log_root_directory_in_log_server(self):
        """
        author:DuPanPan
        date:2020-04-26
        description:在日志服务器上创建日志基本路径
        :return return self.log_root_dir_path:日志基本路径

        @changelog      2021-03-29 09:31:18  haibin.xu
                        1. 优化函数实现, 函数名修正：log_root_dir_init -> make_log_root_directory_in_log_server
        """
        ip, port = self.get_ip_port()
        log_dir_date, log_dir_time = self.__get_date_time(self.framework_run_dict['test_start_timestamp'])

        log_directory_name = '_'.join([
            str(self.framework_run_dict['config_dict']['test_entry']),
            str(self.framework_run_dict['config_dict']['host_label']),
            str(ip),
            str(port)
        ])
        print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
        log.info(f"LOG_ROOT_PATH is :{constants.LOG_ROOT_PATH}")
        log.info(f"log_directory_name is :{log_directory_name}")
        log.info(f"log_dir_date is :{log_dir_date}")
        log.info(f"log_dir_time is :{log_dir_time}")
        self.log_root_dir_path = CommandOperation.format_linux_path_sep(os.path.join(
            constants.LOG_ROOT_PATH, log_directory_name, log_dir_date, log_dir_time))
        log.info(f"log_root_dir_path is :{self.log_root_dir_path}")
        print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
        try:
            mkdir_result = FileOperation.make_directory(dir_name=self.log_root_dir_path, ip=self.log_server_ip,
                                                        username=self.log_server_account, match_flag=False, port=port)
        except Exception as e:
            log.error('Found exception during make directory: {}, exception: {}'.format(self.log_root_dir_path, e))
            mkdir_result = RtnStatusEnum.FAIL.value

        if RtnStatusEnum.SUCCESS.value != mkdir_result:
            # add by hejf 20231213
            log.warning("=====================>日志账户framework下创建日志存储路径失败！！ sxe跑测，先忽略日志采集")
            mkdir_result = RtnStatusEnum.SUCCESS.value

        if RtnStatusEnum.SUCCESS.value == mkdir_result:
            log.info('Finish to make directory in log server[{}@{}:{}]: {}.'.format(
                self.log_server_account, self.log_server_ip, str(port), self.log_root_dir_path))
        else:
            log.error('Fail to make directory in log server[{}@{}:{}]: {}.'.format(
                self.log_server_account, self.log_server_ip, str(port), self.log_root_dir_path))
            self.log_root_dir_path = ''

        return self.log_root_dir_path

    def modify_log_permission(self, job_log_path):
        """
        author:      haibin.xu
        date:        2021-04-01 09:55:07
        description: 变更日志服务器中相关日志目录访问者权限

        :param job_log_path: 日志路径
        :return:     访问权限修改成功，返回0， 失败返回-1
        """
        rtn_modify = RtnStatusEnum.SUCCESS.value
        ip, port = self.get_ip_port()
        log.info('Start to change file mode ...')
        if constants.ENV_LOG_SERVER_ACCOUNT_FRAMEWORK == self.log_server_account:
            change_mode_cmd = 'sudo {} {}'.format(constants.CHANGE_MODE_FILE_PATH, job_log_path)
            try:
                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                    cmd=change_mode_cmd, ssh_ip=self.log_server_ip, ssh_port=str(port),
                    ssh_username=self.log_server_account, timeout=60)
                rtn_code = CommandOperation.check_cli_output(change_mode_cmd, cmd_code, cmd_stdout, cmd_stderr)
            except Exception as e:
                log.error('Found exception when modify permission, exception: {}'.format(e))
                rtn_code = RtnStatusEnum.FAIL.value

            if RtnStatusEnum.SUCCESS.value == rtn_code:
                log.info('Finish to change file mode: {}.'.format(job_log_path))
            else:
                rtn_modify = RtnStatusEnum.FAIL.value
                log.error('Fail to change file mode: {}.'.format(job_log_path))
        else:
            log.error('Invalid log server account: {}'.format(self.log_server_account))
            rtn_modify = RtnStatusEnum.FAIL.value

        return rtn_modify

    @staticmethod
    def get_filename_from_path(file_path: str = None) -> tuple:
        """
        author:      haibin.xu
        date:        2021-03-29 09:56:06
        description: 从文件的绝对路径中获取文件名

        :param file_path: 文件路径
        :return:     返回文件名
        """
        if file_path is not None:
            file_name_with_extension = os.path.basename(file_path)
            filename, extension = os.path.splitext(file_name_with_extension)
        else:
            filename = None
            extension = None

        return filename, extension

    def make_script_directory_in_log_server(self, script_name):
        """
        author:DuPanPan
        date:2020-09-27
        description:在日志服务器上创建脚本级日志基本路径
        :return :日志文件基本路径

        @changelog      2021-03-29 10:06:47  haibin.xu
                        1. 优化函数实现, log_script_dir_init -> make_script_directory_in_log_server
        """
        # 获取脚本名称
        if script_name is None:
            script_name = 'manual_collect_log'
        else:
            script_name, _ = self.get_filename_from_path(script_name)
            log_dir_date, log_dir_time = self.__get_date_time()
            script_name = script_name + "_" + log_dir_date + "_" + log_dir_time
        self.log_script_dir_path = CommandOperation.format_linux_path_sep(os.path.join(self.log_root_dir_path,
                                                                                       script_name))

        try:
            mkdir_result = FileOperation.make_directory(dir_name=self.log_script_dir_path, ip=self.log_server_ip,
                                                        username=self.log_server_account, match_flag=False)
        except Exception as e:
            log.error('Found exception during make directory: {}, exception: {}'.format(self.log_script_dir_path, e))
            mkdir_result = RtnStatusEnum.FAIL.value

        ip, port = self.get_ip_port()
        if RtnStatusEnum.SUCCESS.value == mkdir_result:
            log.info('Finish to make script directory in log server[{}@{}:{}]: {}.'.format(
                self.log_server_account, self.log_server_ip, str(port), self.log_script_dir_path))
        else:
            log.error('Fail to make script directory in log server[{}@{}:{}]: {}.'.format(
                self.log_server_account, self.log_server_ip, str(port), self.log_script_dir_path))

        return self.log_script_dir_path

    def set_framework_log_parameters(self):

        source_script_log_path = self.framework_run_dict['test_script_log_directory']
        source_framework_log_path = self.framework_run_dict['run_all_test_log_file']
        source_script_operation_log_path = constants.ESAT_PATH_OUT_PUTS_SCRIPTS_PATH
        script_name, _ = self.get_filename_from_path(file_path=self.framework_run_dict['script_name'])
        # 收集此次脚本日志 /script_dir/script_name*
        log.info('source_framework_log_path: {} '.format(source_framework_log_path))
        log.info('source_script_log_path: {}'.format(source_script_log_path))
        log.info('source_script_operation_log_path: {}'.format(source_script_operation_log_path))
        log.info('script_name: {}'.format(script_name))

        self.framework_log_dict = {
            source_framework_log_path: constants.LOG_DIR_NAME_TEST_SERVER,
            source_script_log_path: constants.LOG_DIR_NAME_TEST_SERVER,
            source_script_operation_log_path: constants.LOG_DIR_NAME_TEST_SERVER,
        }

    def collect_log_in_current_directory(self, log_dict: dict = None, collect_to_path: str = None,
                                         server_msg: str = None, username: str = 'root', ip: str = None,
                                         port: str = '22', localpath_flag: bool = False) -> bool:
        """
        author:      haibin.xu
        date:        2021-04-09 14:27:48
        description: 当前log路径下，归纳日志

        :param log_dict: log信息
        :param collect_to_path: log要拷贝的路径
        :param server_msg: server 信息
        :param username: log所在server 的用户名
        :param ip:   log所在server ip
        :param port: log所在server port
        :param localpath_flag: 是否本地路径
        :return:     返回是否成功收集到日志

        @changelog      2021-05-26 11:21:19  haibin.xu
                        1. 优化函数实现, 更新文件查找方法
        """
        # 如果 字典为空，则不需要收集
        if not log_dict:
            return True

        if CommandOperation.check_windows_cmd(ssh_ip=ip, local_execute_flag=localpath_flag):
            return self.collect_log_in_current_directory_for_windows(
                log_dict=log_dict, collect_to_path=collect_to_path, server_msg=server_msg, username=username,
                ip=ip, port=port, localpath_flag=localpath_flag)

        collect_log_flag = False
        target_path = None
        temp_log_dict = {}

        # 将拷贝目标目录相同的文件归类，以便后续统一拷贝
        for source_file, target_directory in log_dict.items():
            if target_directory not in temp_log_dict.keys():
                temp_log_dict.update({target_directory: [source_file]})
            else:
                temp_log_dict[target_directory].append(source_file)

        for target_directory, source_file in temp_log_dict.items():
            mkdir_flag = False
            source_file = ' '.join(source_file)
            # 判断文件是否存在
            try:
                _, found_file = FileOperation.find_files(path=source_file, ip=ip, port=port,
                                                         path_flag=localpath_flag)
            except Exception as e:
                log.error('Found exception during check file: {}, exception: {}'.format(source_file, e))
                found_file = ''

            if found_file:
                file_exist_flag = True
                log.debug('Found file: {}, in {} server: {}@{}:{}'.format(source_file, server_msg, username, ip,
                                                                          port))
            else:
                file_exist_flag = False
                log.warning('Not found file: {}, in {} server: {}@{}:{}'.format(source_file, server_msg, username,
                                                                                ip, port))

            if file_exist_flag:
                # 文件存在，创建目标文件夹
                target_path = CommandOperation.format_linux_path_sep(os.path.join(collect_to_path, target_directory))
                # 创建收集文件的目标文件夹
                try:
                    rtn_mkdir_flag = FileOperation.make_directory(dir_name=target_path, local_execute=localpath_flag,
                                                                  ip=ip, port=port, username=username,
                                                                  match_flag=False)
                except Exception as e:
                    log.error('Found exception during make directory: {}, exception: {}'.format(target_path, e))
                    rtn_mkdir_flag = RtnStatusEnum.FAIL.value

                if RtnStatusEnum.SUCCESS.value == rtn_mkdir_flag:
                    mkdir_flag = True
                    log.debug('Success to make directory: {}, in {} server: {}@{}:{}'.format(target_path, server_msg,
                                                                                             username, ip, port))
                else:
                    mkdir_flag = False
                    log.error('Fail to make directory: {}, in {} server: {}@{}:{}'.format(target_path, server_msg,
                                                                                          username, ip, port))

            if mkdir_flag:
                # 目标文件夹创建成功，拷贝文件
                try:
                    rtn_mkln_flag = FileOperation.create_symbolic_link(source_path=found_file,
                                                                       link_directory_path=target_path,
                                                                       local_execute_flag=localpath_flag,
                                                                       ssh_ip=ip, ssh_port=port,
                                                                       path_check_flag=False)
                except Exception as e:
                    log.error('Found exception during create link file save in path: {}, link to source path: {}, '
                              'exception: {}'.format(target_path, found_file, e))
                    rtn_mkln_flag = RtnStatusEnum.FAIL.value

                if RtnStatusEnum.SUCCESS.value == rtn_mkln_flag:
                    collect_log_flag = True
                    log.debug('Success to create link file save in path: {}, link to source path: {}, in {} server: '
                              '{}@{}:{}'.format(target_path, found_file, server_msg, username, ip, port))
                else:
                    log.error('Fail to create link file save in path: {}, link to source path: {}, in {} server: '
                              '{}@{}:{}'.format(target_path, found_file, server_msg, username, ip, port))

        return collect_log_flag

    def collect_log_in_current_directory_for_windows(self, log_dict: dict = None, collect_to_path: str = None,
                                                     server_msg: str = None, username: str = 'root', ip: str = None,
                                                     port: str = '22', localpath_flag: bool = False) -> bool:
        """
        author:      zhilong.zhang
        date:        2021-04-09 14:27:48
        description: 当前log路径下，归纳日志(仅适用于windows host qemu)

        :param log_dict: log信息
        :param collect_to_path: log要拷贝的路径
        :param server_msg: server 信息
        :param username: log所在server 的用户名
        :param ip:   log所在server ip
        :param port: log所在server port
        :param localpath_flag: 是否本地路径
        :return:     返回是否成功收集到日志
        """
        collect_log_flag = False
        target_path = None
        temp_log_dict = {}

        # 将拷贝目标目录相同的文件归类，以便后续统一拷贝
        for source_file, target_directory in log_dict.items():
            if target_directory not in temp_log_dict.keys():
                temp_log_dict.update({target_directory: [source_file]})
            else:
                temp_log_dict[target_directory].append(source_file)

        for target_directory, source_file in temp_log_dict.items():
            source_file = ','.join(source_file)

            # 创建收集文件的目标文件夹
            target_path = CommandOperation.format_linux_path_sep(os.path.join(collect_to_path, target_directory))
            try:
                rtn_mkdir_flag = FileOperation.make_directory(dir_name=target_path, local_execute=localpath_flag,
                                                              ip=ip, port=port, username=username,
                                                              match_flag=False)
            except Exception as e:
                log.error('Found exception during make directory: {}, exception: {}'.format(target_path, e))
                rtn_mkdir_flag = RtnStatusEnum.FAIL.value

            if RtnStatusEnum.SUCCESS.value == rtn_mkdir_flag:
                log.debug('Success to make directory: {}, in {} server: {}@{}:{}'.format(target_path, server_msg,
                                                                                         username, ip, port))
            else:
                log.error('Fail to make directory: {}, in {} server: {}@{}:{}'.format(target_path, server_msg,
                                                                                      username, ip, port))
            # 拷贝文件
            try:
                copy_file_cmd = 'cp -r {} {}'.format(source_file, target_path)
                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                    cmd=copy_file_cmd, local_execute_flag=localpath_flag, ssh_ip=ip, ssh_port=port,
                    ssh_username=username)
                if RtnStatusEnum.SUCCESS.value == cmd_code:
                    collect_log_flag = True
            except Exception as e:
                log.error('Found exception during copy file source path: {}, to target path: {}, '
                          'exception: {}'.format(source_file, target_path, e))

            if collect_log_flag:
                log.debug('Success to copy file source path: {}, to target path: {}, in {} server: '
                          '{}@{}:{}'.format(source_file, target_path, server_msg, username, ip, port))
            else:
                log.error('Faild to copy file source path: {}, to target path: {}, in {} server: '
                          '{}@{}:{}'.format(source_file, target_path, server_msg, username, ip, port))

        return collect_log_flag

    @staticmethod
    def pack_collect_log(file_path: str = None, tar_file_path: str = None, server_msg: str = None,
                         username: str = 'root', ip: str = None, port: str = '22',
                         localpath_flag: bool = False, is_pigz: bool = True,
                         tar_params: str = '-Phcf') -> bool:
        """
        author:      haibin.xu
        date:        2021-04-09 15:05:48
        description: 打包收集的日志

        :param file_path: 日志路径
        :param tar_file_path: 打包名
        :param server_msg: server 信息
        :param username: log所在server 的用户名
        :param ip:   log所在server ip
        :param port: log所在server port
        :param localpath_flag: 是否为本地路径
        :param is_pigz: pigz标志位
        :param tar_params: tar 参数
        :return:     返回是否成功打包日志文件
        """
        try:
            rtn_tar_flag = FileOperation.compress_files(file_path=file_path, tar_file_path=tar_file_path,
                                                        localpath_flag=localpath_flag, ip=ip, port=port,
                                                        username=username, is_pigz=is_pigz,
                                                        tar_params=tar_params)
        except Exception as e:
            log.error('Found exception during tar file: {}, exception: {}'.format(file_path, e))
            rtn_tar_flag = RtnStatusEnum.FAIL.value

        if RtnStatusEnum.SUCCESS.value == rtn_tar_flag:
            compress_file_flag = True
            log.debug('Success to compress file: {}, to tar file: {}. in {} server: {}@{}:{}'.format(
                file_path, tar_file_path, server_msg, username, ip, port))
        else:
            compress_file_flag = False
            log.error('Fail to compress file: {}, to tar file: {}. in {} server: {}@{}:{}'.format(
                file_path, tar_file_path, server_msg, username, ip, port))

        return compress_file_flag

    def scp_collect_log_to_log_server(self, source_file: str = None, server_msg: str = None, source_ip: str = None,
                                      source_port: str = '22', source_username: str = 'root',
                                      localpath_flag: bool = False) -> bool:
        """
        author:      haibin.xu
        date:        2021-04-09 15:17:17
        description: 将收集的日志文件拷贝到远程日志服务器

        :param source_file: 收集的日志路径
        :param server_msg: server 信息
        :param source_ip:   收集的日志所在的server ip
        :param source_port: 收集的日志所在的server port
        :param source_username: 收集的日志所在的server username
        :param localpath_flag: 是否为本地路径
        :return:     返回是否拷贝成功
        """
        # add by hejf 20231213
        if not FileOperation.path_exists(self.log_root_dir_path, localpath_flag=True, print_enable = False):
            log.warning("==========> 由于日志服务器存储路径{}不存在，日志仅存在本地，未采集到日志服务器！！！".
                        format(self.log_root_dir_path))
            return False
        ip, port = self.get_ip_port()
        try:
            if source_username == 'Administrator':
                rtn_scp_flag = FileOperation.windows_scp_file(source_file_path=source_file,
                                                              target_file_path=self.log_script_dir_path,
                                                              source_username=source_username,
                                                              windows_ip=source_ip,
                                                              source_port=source_port,
                                                              target_ip=self.log_server_ip,
                                                              target_port=port,
                                                              target_username=self.log_server_account)
            else:
                rtn_scp_flag = FileOperation.scp_file(source_file_path=source_file, source_username=source_username,
                                                      target_file_path=self.log_script_dir_path, source_ip=source_ip,
                                                      source_port=source_port, target_ip=self.log_server_ip,
                                                      target_port=port,
                                                      target_username=self.log_server_account,
                                                      local_execute=localpath_flag)
                if rtn_scp_flag == RtnStatusEnum.FAIL.value:
                    log.warning("双向免密采集失败，尝试单向免密采集")
                    rtn_scp_flag = FileOperation.target_scp_file(source_file_path=source_file,
                                                                 target_file_path=self.log_script_dir_path, source_ip=source_ip,
                                                                 source_port=source_port, target_ip=self.log_server_ip,
                                                                 target_port=port,
                                                                 target_username=self.log_server_account,
                                                                 local_execute=localpath_flag)
        except Exception as e:
            log.error('Found exception during scp files, exception: {}'.format(e))
            rtn_scp_flag = RtnStatusEnum.FAIL.value

        if RtnStatusEnum.SUCCESS.value == rtn_scp_flag:
            scp_file_flag = True
            log.debug('Success to copy {} log file: {}@{}:{}:{}, to log server target file path: {}@{}:{}:{}'.format(
                server_msg, source_username, source_ip, source_port, source_file, self.log_server_account,
                self.log_server_ip, str(port), self.log_script_dir_path))
        else:
            scp_file_flag = False
            log.error('Fail to copy {} log file: {}@{}:{}:{}, to log server target file path: {}@{}:{}:{}'.format(
                server_msg, source_username, source_ip, source_port, source_file, self.log_server_account,
                self.log_server_ip, str(port), self.log_script_dir_path))

        return scp_file_flag

    def delete_collect_log(self, pack_flag: bool = True, scp_flag: bool = True, collect_path: str = None,
                           colletc_tar_path: str = None, ip: str = None, port: str = '22', server_msg: str = None,
                           localpath_flag: bool = False, username: str = 'root') -> None:
        """
        author:      haibin.xu
        date:        2021-04-09 16:22:17
        description: 删除收集的log目录，压缩完成的log文件，以及远程拷贝到日志服务器上的log压缩包

        :param pack_flag: 日志打包标志位
        :param scp_flag:  日志传输标志位
        :param collect_path: log所在server下收集的log目录
        :param colletc_tar_path: 在log所在server下log压缩包
        :param ip:        log所在server的ip
        :param port:      log所在server的port
        :param server_msg: log所在server 信息
        :param localpath_flag: 是否本地路径
        :param username: 收集log所在的server 用户名
        :return:        None

        @changelog      2021-10-15 09:31:04  haibin.xu
                        1. 优化函数实现, 不再删除日志服务器上的压缩文件
        """
        files = ' '.join([collect_path, colletc_tar_path])
        if pack_flag and (RtnStatusEnum.SUCCESS.value == self.delete_files(delete_file=files, test_ip=ip,
                                                                           test_port=port,
                                                                           local_execute=localpath_flag)):
            log.debug('Success to delete log file: {}, in {} server: {}@{}:{}'.format(files, server_msg, username,
                                                                                      ip, port))
        else:
            log.warning('Fail or Not need to delete file: {}, in {} server: {}@{}:{}'.format(files, server_msg,
                                                                                             username, ip, port))
        # if scp_flag:
        #     # 日志传输成功，则删除拷贝到日志服务器上的log压缩包
        #     tar_file_path = CommandOperation.format_linux_path_sep(os.path.join(self.log_script_dir_path,
        #                                                                         os.path.basename(colletc_tar_path)))
        #     if (RtnStatusEnum.SUCCESS.value == self.delete_files(
        #             delete_file=tar_file_path, test_ip=self.log_server_ip, username=self.log_server_account)):
        #         log.debug('Success to delete file: {}, in log server: {}@{}:22'.format(
        #             tar_file_path, self.log_server_account, self.log_server_ip))
        #     else:
        #         log.warning('Fail to delete file: {}, in log server: {}@{}:22'.format(
        #             tar_file_path, self.log_server_account, self.log_server_ip))

    @staticmethod
    def delete_files(delete_file: (list, str), test_ip: str, test_port: str = '22', username: str = 'root',
                     match_flag: bool = False, local_execute: bool = False) -> int:
        """
        author: luyafei
        date: 2020.12.29
        description: 删除文件
        :param test_ip: 要删除文件所在机器的ip
        :param test_port: 要删除文件所在机器的port
        :param delete_file: 要删除的文件列表或文件
        :param username:    远程登录用户名
        :param match_flag: 是否对文件进行/root/ps3sim/.*模式匹配，
                           如果进行模式匹配，则只有匹配该模式才对文件进行操作
        :param local_execute: 本地执行标志位
        :return: 返回文件是否成功删除

        @changelog      2021-03-26 17:13:22  haibin.xu
                        1. 优化函数实现, 函数名修正：files_delete -> delete_files
        """
        rtn_delete = RtnStatusEnum.SUCCESS.value

        if (not local_execute) and (RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(
                ip=test_ip, port=test_port, ssh_username=username, connect_times=5)):
            log.error('Not to delete files: {}, reason: failed to connect server: {}@{}:{}'.format(
                delete_file, username, test_ip, test_port))
            return RtnStatusEnum.FAIL.value

        if delete_file:
            if isinstance(delete_file, list):
                delete_file = ' '.join(delete_file)
            try:
                delete_rtn, _ = FileOperation.delete_file(path=delete_file, ip=test_ip, port=test_port,
                                                          username=username, match_flag=match_flag,
                                                          localpath_flag=local_execute, file_check_flag=False)
            except Exception as e:
                log.error('Found exception during delete file: {}, exception: {}'.format(delete_file, e))
                delete_rtn = RtnStatusEnum.FAIL.value

            if RtnStatusEnum.SUCCESS.value == delete_rtn:
                log.debug('Success to delete file: {}.'.format(delete_file))
            else:
                log.warning('Fail to delete file: {}.'.format(delete_file))
                rtn_delete = RtnStatusEnum.FAIL.value
        else:
            log.debug('Not need to delete file, file list is null.')

        return rtn_delete

    def collect_framework_log(self):
        log.info('Start to collect framework log file to log server...')

        username = 'root'
        # username = 'testYF/[your-name]'

        # 收集框架和脚本日志
        self.set_framework_log_parameters()

        collect_flag = self.collect_log_in_current_directory(log_dict=self.framework_log_dict,
                                                             collect_to_path='', server_msg='test',
                                                             ip=self.ps3_server_ip, username=username,
                                                             localpath_flag=True)

        # 打包
        compress_file_flag = self.pack_collect_log(file_path=self.ps3_server_collect_path,
                                                   tar_file_path=self.ps3_server_collect_tar, server_msg='test',
                                                   ip=self.ps3_server_ip, localpath_flag=True,
                                                   username=username, is_pigz=False) if collect_flag else False

        # 传输
        scp_file_flag = self.scp_collect_log_to_log_server(source_file=self.ps3_server_collect_tar,
                                                           localpath_flag=True, server_msg='test',
                                                           source_ip=self.ps3_server_ip,
                                                           source_username=username) if \
            compress_file_flag else False

        if scp_file_flag:
            # 删除打包文件
            self.delete_collect_log(pack_flag=compress_file_flag, scp_flag=scp_file_flag,
                                    collect_path=self.ps3_server_collect_path,
                                    colletc_tar_path=self.ps3_server_collect_tar, ip=self.ps3_server_ip,
                                    server_msg='test', localpath_flag=True, username=username)
            log.info('Finish to collect framework log file to log server.\n')
        else:
            log.error('Fail to collect framework log file to log server.\n')

    def collect_log(self):
        return True
