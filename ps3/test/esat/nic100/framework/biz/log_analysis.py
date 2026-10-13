#!/usr/bin/python3
# -*- encoding=utf8 -*-
"""
file name: 日志分析log_analysis
description: 日志分析
author: kaifeng.bi
date: 2021.11.15
"""
import os
import re
import sys
import time
import datetime

import add_syspath
from scripts.script_libs import log
from scripts.script_libs.script_base import ScriptBase
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum, BugOwner, FWLogKeywords
from scripts.script_libs import constants
from scripts.script_libs.controller_operation import ControllerOperation
from scripts.script_libs.host_operation import HostOperation
from framework.simulation.host_ioc_start import HostIocStart
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse
from scripts.script_libs.file_operation import FileOperation
from framework.biz.classes.config_file_manager import ConfigManager
from scripts.script_libs.custom_operation import CustomOperation
from scripts.script_libs.file_operation import FileOperation

# test/esat/scripts 目录绝对路径
SCRIPTS_DIRECTORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# test/esat 目录绝对路径
ESAT_DIRECTORY = os.path.dirname(SCRIPTS_DIRECTORY)
HOST_LOG_PATH = "/var/log/"  # 日志存放路径
PS3_LOG_PATH = "/var/log/ps3_log/"  # 日志存放路径
FWLOG_PATH = "/var/log/"  # 日志存放路径
NEW_FWLOG_PATH = "/root/var/log/"  # 日志存放路径
CLI_LOG_FILE = "~/ps3cli.log"  # 日志存放路径
HOST_EIO_WORD = "ps3_scsih_io_done.*reply_flags\[1\]"
HOST_RESET_WORD = "ps3_recovery_work"
HOST_TIMEOUT_WORD = "time out"
FWLOG_KEYWORDS = [keyword.value for keyword in FWLogKeywords]


class LogAnalysis(object):
    """
    author:         kaifeng.bi
    date:           2021.11.15
    description:    该类用来分析日志，采用模块化设计，在all_analysis_fun添加需要运行的功能
                    支持自动化和手动运行
    """

    log_type = 1  # 1:ps3_log 2:host_log 3:cli_log
    trace_list = []
    bug_owner = ''
    script_log_path = ''
    log_print2console = False
    IOSTAT_LOG_FILENAME = 'log.log'
    io_tmo = False

    def __init__(self, manual_flag: bool = False, host_ip: str = None, host_port: str = '22',
                 ioc_ip: str = None, ioc_port: str = '22',
                 hostnode_ip: str = None, iocnode_ip: str = None):
        """
        author:               kaifeng.bi
        date:                 2021.11.15
        description:          构造函数
        :param manual_flag:   手动还是自动，默认自动
        :param host_ip:       host ip
        :param host_port:     host port,默认22
        :param ioc_ip:        ioc ip
        :param ioc_port:      ioc port,默认22
        :param hostnode_ip:   host node ip
        :param iocnode_ip:    ioc node ip
        """
        # 配置文件字典
        self.__config_manager = None
        self.__ips_config_dict = None

        # 测试中所使用到的所有ip地址
        self.host_ip = None
        self.host_port = None
        self.ioc_ip = None
        self.ioc_port = None
        self.hostnode_ip = None
        self.iocnode_ip = None
        # 自动不打印分析流程到终端，手动打印
        self.log_print2console = manual_flag
        # 设置相关参数
        if manual_flag:
            self.__manual_set_parameters(host_ip, host_port, ioc_ip, ioc_port, hostnode_ip, iocnode_ip)
        else:
            self.__set_ip_parameters()

    def __manual_set_parameters(self, host_ip: str = None, host_port: str = '22',
                                ioc_ip: str = None, ioc_port: str = '22',
                                hostnode_ip: str = None, iocnode_ip: str = None) -> None:
        """
        author:               kaifeng.bi
        date:                 2021.11.15
        description:          手动设置参数
        :param host_ip:       host ip
        :param host_port:     host port,默认22
        :param ioc_ip:        ioc ip
        :param ioc_port:      ioc port,默认22
        :param hostnode_ip:   host node ip
        :param iocnode_ip:    ioc node ip
        """
        self.host_ip = host_ip
        self.host_port = host_port
        self.ioc_ip = ioc_ip
        self.ioc_port = ioc_port
        self.hostnode_ip = hostnode_ip
        self.iocnode_ip = iocnode_ip

    def __set_ip_parameters(self):
        """
        author:               kaifeng.bi
        date:                 2021.11.15
        description:          自动设置ip参数，从配置管理类获取
        """
        self.__config_manager = ConfigManager.get_config_manager_object()
        if self.__config_manager is None:
            log.error('Fail to get config manager object.')
            exit(1)

        self.__ips_config_dict = self.__config_manager.ips_dict_get()
        if self.__ips_config_dict is None:
            log.error('Fail to get config_manager_parameters: ips_dict_get.')
            exit(1)

        """测试中所使用到的所有ip地址"""
        self.host_ip = self.__ips_config_dict.get(constants.TEST_CONFIG_HOST_IP)
        self.host_port = self.__ips_config_dict.get(constants.TEST_CONFIG_HOST_PORT)
        self.ioc_ip = self.__ips_config_dict.get(constants.TEST_CONFIG_IOC_IP)
        self.ioc_port = self.__ips_config_dict.get(constants.TEST_CONFIG_IOC_PORT)
        self.hostnode_ip = self.__ips_config_dict.get(constants.TEST_CONFIG_HOST_QEMU_IP)
        self.iocnode_ip = self.__ips_config_dict.get(constants.TEST_CONFIG_IOC_QEMU_IP)

    def log_analysis(self, log_start_time: str=None, log_end_time: str=None) -> bool:
        """
        author:                 kaifeng.bi
        date:                   2021.11.15
        description:            日志分析函数
        :param log_start_time:  日志起始时间
        :param log_end_time:    日志结束时间
        """
        """执行分析函数"""
        '''***********************************   详细分析函数   ***********************************'''
        """日志分析
                " 0:check environment connection   self.check_environment_connection_and_reboot        "
                " 1:check cli status               self.check_cli_status                               "
                " 2:get eio info                   self.get_eio_info                                   "
                " 3:get host reset info            self.get_host_reset_info                            "

        """
        rtn = 0  # 0：无复位 #1：有复位无超时 #2：有复位有超时
        pre_log_file = log.get_log_file()
        self.init_script_log()
        self.script_log_info("------------------------START ANALYSIS--------------------------")

        i = 0
        all_analysis_fun = [self.get_host_reset_info, ]
        while i < len(all_analysis_fun):
            all_analysis_fun[i](log_start_time, log_end_time)
            i += 1

        self.script_log_info("------------------------END ANALYSIS--------------------------")
        if self.bug_owner:
            print('------------------------LOG ANALYSIS--------------------------')
            print('python3 log_analysis.py --hip={} --hnip={} --sip={} --snip={} --st={} --et={}'.
                  format(self.host_ip, self.hostnode_ip, self.iocnode_ip, self.iocnode_ip, log_start_time,
                         log_end_time))
            print('the bug owner is supposed to be {}, details refer to the file {}'.format(self.bug_owner,
                                                                                            self.script_log_path))
            print('------------------------LOG ANALYSIS--------------------------')
            self.bug_owner = ''
            if self.io_tmo:
                rtn = 2
            else:
                rtn = 1
        # 必须有设置为true的操作，不然其他的也不能打印到console
        env_conf_dict = ConfigManager.get_config_manager_object().env_dict_get()
        log.init(pre_log_file, env_conf_dict.get(constants.ENV_SHOW_CONSOLE_LOG, True))
        return rtn

    def get_host_reset_info(self, log_start_time: str=None, log_end_time: str=None):
        """
        author:                 kaifeng.bi
        date:                   2021.11.15
        description:            分析host reset情形
        :param log_start_time:  日志起始时间
        :param log_end_time:    日志结束时间
        """
        self.script_log_info("########GET HOST RESET INFO########")
        self.io_tmo = False
        start_time, file_start_time = self.change_time_format_to_host(log_start_time)
        end_time, file_end_time = self.change_time_format_to_host(log_end_time)
        found_file = self.get_host_log_files(file_start_time, file_end_time)
        rtn_info, rtn_code = self.\
            cat_log_by_time_with_keywords(found_file, start_time, end_time,
                                          keyword=HOST_RESET_WORD,
                                          cmd_execute_address=CmdExecuteAdressEnum.HOST_NODE.value,
                                          need_separator_flag=True, separator='[', time_begin_loc=2)

        if '' != rtn_info and '' == rtn_code:
            log.warning('host reset happened')
            self.bug_owner = BugOwner.HOST.value
            log.info(rtn_info)

            rtn_info, rtn_code = self.\
                cat_log_by_time_with_keywords(found_file, start_time, end_time,
                                              keyword=HOST_TIMEOUT_WORD,
                                              cmd_execute_address=CmdExecuteAdressEnum.HOST_NODE.value,
                                              need_separator_flag=True, separator='[', time_begin_loc=2)
            if '' != rtn_info and '' == rtn_code:
                log.info(rtn_info)
                self.io_tmo = True
            """
                self.trace_list = self.get_traceid(rtn_info, 2)
                info = self.get_all_info_with_traceid(log_start_time=log_start_time,
                                                      log_end_time=log_end_time, err='TIMEOUT')
                if 'mgr_abort' in info:
                    # thread_num = "\\" + info.split(']')[1] + '\]|grep aborted_trace_id'
                    # rtn_info, rtn_code = CommonFunc.\
                    #     cat_log_by_time_with_keywords_v2(found_file, start_time, end_time,
                    #                                      keyword=thread_num,
                    #                                      cmd_execute_address=CmdExecuteAddressEnum.HOST_NODE.value,
                    #                                      need_separator_flag=True, separator='[', time_begin_loc=2)
                    rtn_info = info.split('aborted')[1]
                    self.trace_list = self.get_traceid(rtn_info, 2)
                    info = self.get_all_info_with_traceid(log_start_time=log_start_time,
                                                          log_end_time=log_end_time, err='IO')
                    if 'SCMD_T_NORW' in info:
                        self.bug_owner = BugOwner.MGR.value
                    elif 'direct_f[1]' in info:
                        if 'DEV_T_VD' in info:
                            self.bug_owner = BugOwner.HIL.value
                        else:
                            self.bug_owner = BugOwner.BACKEND.value
                    else:
                        self.bug_owner = BugOwner.FRONTEND.value
                else:
                    self.bug_owner = BugOwner.MGR.value
            """
        elif '' == rtn_info and '' == rtn_code:
            log.info('did not find host reset')
        else:
            log.info('failed to get host reset info')

    def init_script_log(self) -> None:
        """
        author: kaifeng.bi
        date  : 2021.09.29
        descriptor: 生成脚本的日志文档
        :return: 无返回值
        """
        # 通过命令行参数获取log存放目录
        log_default_path = CommandLineArgsParse.get_log_output_path()

        # 如果命令行参数中没有配置log保存目录或log目录不存在时，使用默认路径
        if ('' == log_default_path) or (not os.path.exists(log_default_path)):
            # 此处不能使用log，因为此时log模块还未完成初始化，只有log模块初始化完成，才能使用log打印
            # print('Warning! Log file path not specified or invalid, Will use default script path. ')
            log_default_path = os.path.join(ESAT_DIRECTORY, constants.LOG_DEFAULT_PATH_NAME)
            # 如果不存在test/esat/outputs/scripts目录，则创建该目录
            if not os.path.exists(log_default_path):
                os.mkdir(log_default_path)

        # 从获取脚本路径获取脚本名称
        # script_name = os.path.basename(sys.argv[0]).replace('.py', '')

        # 构建脚本日志路径
        timestamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
        self.script_log_path = os.path.join(FileOperation.normalize_path(log_default_path),
                                            'log_analysis') + '_' + timestamp + '.log'
        # 初始化脚本日志
        log.init(self.script_log_path, print2console=self.log_print2console)

    def script_log_info(self, log_str: str=None) -> None:
        """
        author: kaifeng.bi
        date  : 2021.09.29
        descriptor: 不格式化显示脚本运行日志
        :return: 无返回值
        """
        log.info('\n' + log_str + '\n', format_flag=False)

    def get_all_info_with_traceid(self, log_start_time: str=None, log_end_time: str=None, err: str=None) -> str:
        """
        author:                 kaifeng.bi
        date:                   2021.11.15
        description:            通过traceid获取host，ioc，cli日志信息
        :param log_start_time:  日志起始时间
        :param log_end_time:    日志结束时间
        :param err:             显示要分析日志的类型
        """
        if not self.trace_list:
            return
        if err:
            self.script_log_info("@@@@@@@@@@@@HOST {} LOGS@@@@@@@@@@@@".format(err))
        self.script_log_info("********HOST LOGS********")
        start_time, file_start_time = self.change_time_format_to_host(log_start_time)
        end_time, file_end_time = self.change_time_format_to_host(log_end_time)
        found_file = self.get_host_log_files(file_start_time, file_end_time)
        host_info, rtn_code = self.\
            cat_log_by_time_with_keywords(found_file, start_time, end_time,
                                          keyword=self.trace_list[0],
                                          cmd_execute_address=CmdExecuteAdressEnum.HOST_NODE.value,
                                          need_separator_flag=True, separator='[', time_begin_loc=2)
        if '' != host_info and '' == rtn_code:
            self.script_log_info(host_info)

        # self.script_log_info("********PS3 LOGS********")
        # start_time, file_start_time = self.change_time_format_to_ps3(log_start_time)
        # end_time, file_end_time = self.change_time_format_to_ps3(log_end_time)
        # found_file = self.get_ioc_log_files(file_start_time, file_end_time)
        # rtn_info, rtn_code = self.\
        #     cat_log_by_time_with_keywords(found_file, start_time, end_time,
        #                                   keyword=self.trace_list[0],
        #                                   cmd_execute_address=CmdExecuteAdressEnum.SOC_NODE.value)
        # if '' != rtn_info and '' == rtn_code:
        #     self.script_log_info(rtn_info)
        #
        # self.script_log_info("********CLI LOGS********")
        # start_time = self.change_time_format_to_cli(log_start_time)
        # end_time = self.change_time_format_to_cli(log_end_time)
        # rtn_info, rtn_code = self.\
        #     cat_log_by_time_with_keywords(CLI_LOG_FILE, start_time, end_time,
        #                                   keyword=self.trace_list[0],
        #                                   cmd_execute_address=CmdExecuteAdressEnum.HOST_NODE.value)
        # if '' != rtn_info and '' == rtn_code:
        #     self.script_log_info(rtn_info)
        return host_info

    def get_traceid(self, info, log_type) -> list:
        """
        author:                 kaifeng.bi
        date:                   2021.11.15
        description:            获取traceid
        :param info:            从info获取traceid
        :param log_type:        日志类型
        """
        tracelist = []

        if log_type == 1:  # ps3 log
            trace = info.split('traceId=')
            trace = trace[1].split(',')
            tracelist.append(hex(trace[0])[2:])
        elif log_type == 2:  # host log
            info = info.split('\n')
            for i in info:
                trace = i.split('trace_id[')
                if len(trace) > 1:
                    trace = trace[1].split(']')
                    tracelist.append(trace[0][2:])
        elif log_type == 3:  # cli log
            trace = info.split('traceId = ')
            trace = trace[1].split(' ')
            tracelist.append(trace[0][2:])

        return tracelist

    def get_eio_info(self, log_start_time: str=None, log_end_time: str=None):
        """
        author:                 kaifeng.bi
        date:                   2021.11.15
        description:            获取eio信息
        :param log_start_time:  日志起始时间
        :param log_end_time:    日志结束时间
        """
        self.script_log_info("########GET EIO INFO########")
        start_time, file_start_time = self.change_time_format_to_host(log_start_time)
        end_time, file_end_time = self.change_time_format_to_host(log_end_time)
        found_file = self.get_host_log_files(file_start_time, file_end_time)
        rtn_info, rtn_code = self.\
            cat_log_by_time_with_keywords(found_file, start_time, end_time,
                                          keyword=HOST_EIO_WORD,
                                          cmd_execute_address=CmdExecuteAdressEnum.HOST_NODE.value,
                                          need_separator_flag=True, separator='[', time_begin_loc=2)

        if '' != rtn_info and '' == rtn_code:
            log.warning('eio happened')
            log.info(rtn_info)
        elif '' == rtn_info and '' == rtn_code:
            log.info('did not find eio')
        else:
            log.info('failed to get eio info')

        if rtn_info != '':
            self.trace_list = self.get_traceid(rtn_info, 2)
            log.info('trace id: {}'.format(self.trace_list))
        self.get_all_info_with_traceid(log_start_time=log_start_time, log_end_time=log_end_time)

    def change_time_format_to_ps3(self, time: str=None) -> tuple:
        """
        author:                 kaifeng.bi
        date:                   2021.11.15
        description:            把时间转化成ioc日志格式和文件名格式
        :param time:            时间
        """
        # log format 2021/09/28.11:18:04
        # filename format 2021.09.28.11.18.04
        if len(time) < 14:
            log.error("the time is wrong")
            return ''
        a = datetime.datetime.strptime(time, '%Y%m%d%H%M%S')
        return a.strftime('%Y/%m/%d.%H:%M:%S'), a.strftime('%Y.%m.%d.%H.%M.%S')

    def change_time_format_to_cli(self, time: str=None) -> str:
        """
        author:                 kaifeng.bi
        date:                   2021.11.15
        description:            把时间转化成cli日志格式
        :param time:            时间
        """
        # format 2021-09-17 17:53:10
        if len(time) < 14:
            log.error("the time is wrong")
            return ''
        a = datetime.datetime.strptime(time, '%Y%m%d%H%M%S')
        return a.strftime('%Y-%m-%d %H:%M:%S')

    def change_time_format_to_host(self, time: str = None) -> tuple:
        """
        author:                 kaifeng.bi
        date:                   2021.11.15
        description:            把时间转化成host日志格式和文件名格式
        :param time:            时间
        """
        # log format 2021-09-28;02:12:17
        # filename format 2021-09-28_02:12:17
        if len(time) < 14:
            log.error("the time is wrong")
            return ''
        a = datetime.datetime.strptime(time, '%Y%m%d%H%M%S') + datetime.timedelta(hours=-8)
        return a.strftime('%Y-%m-%d;%H:%M:%S'), a.strftime('%Y-%m-%d_%H:%M:%S')

    def change_time_format_to_fwlog(self, time: str = None) -> tuple:
        """
        author:                 kaifeng.bi
        date:                   2022.08.15
        description:            把时间转化成fwlog日志格式和文件名格式
        :param time:            时间
        """
        # log format 2022/08/15.12:24:03
        # filename format 20220815-123051
        if len(time) < 14:
            log.error("the time is wrong")
            return ''
        a = datetime.datetime.strptime(time, '%Y%m%d%H%M%S') + datetime.timedelta(hours=-8)
        return a.strftime('%Y/%m/%d.%H:%M:%S'), a.strftime('%Y%m%d-%H%M%S')

    def get_host_log_files(self, start_time: str = None, end_time: str = None) -> str:
        """
        author:                 kaifeng.bi
        date:                   2021.11.15
        description:            获取start和end时间段内的host日志文件
        :param start_time:      日志起始时间
        :param end_time:        日志结束时间
        """
        # filename format 2021-09-28_02:12:17
        find_files_cmd = 'ls -t {}ps3sas_drv.log*'.format(HOST_LOG_PATH)
        _, files = FileOperation.get_files_with_cmd(find_files_cmd=find_files_cmd, ip=self.hostnode_ip)
        find_files_cmd = 'ls -t {}ps3sas_drv.log*'.format(HOST_LOG_PATH + 'drvlog/')
        _, files_drvlog = FileOperation.get_files_with_cmd(find_files_cmd=find_files_cmd, ip=self.hostnode_ip)
        files += files_drvlog
        found_file = []
        # 日志文件以日志开始时间为文件名
        min = ''
        for file in files:
            if file[-19:] < start_time:
                if file[-19:] > min:
                    min = file[-19:]
        for file in files:
            if min <= file[-19:] < end_time:
                found_file.append(file)
        found_file = ' '.join(found_file) if files else ''
        return found_file if found_file else ''

    def get_ioc_log_files(self, start_time: str = None, end_time: str = None) -> str:
        """
        author:                 kaifeng.bi
        date:                   2021.11.15
        description:            获取start和end时间段内的ioc日志文件
        :param start_time:      日志起始时间
        :param end_time:        日志结束时间
        """
        # filename format 2021.09.28.11.18.04
        find_files_cmd = 'ls {}|grep ps3_log'.format(PS3_LOG_PATH)
        _, files = FileOperation.get_files_with_cmd(find_files_cmd=find_files_cmd, ip=self.iocnode_ip)
        found_file = []
        # 日志文件以日志结束时间为文件名
        max = '9999.99.99.99.99.99'
        for file in files:
            if file[-26:-7] > end_time:
                if file[-26:-7] < max:
                    max = file[-26:-7]
        for file in files:
            if start_time < file[-26:-7] <= max:
                found_file.append(PS3_LOG_PATH + file)
        found_file.append(PS3_LOG_PATH + 'ps3_log')
        found_file = ' '.join(found_file) if files else ''
        return found_file if found_file else ''

    def get_fwlog_files(self, start_time: str = None, end_time: str = None) -> str:
        """
        author:                 kaifeng.bi
        date:                   2022.08.15
        description:            获取start和end时间段内的fwlog日志文件
        :param start_time:      日志起始时间
        :param end_time:        日志结束时间
        """
        # filename format 20220815-121850
        find_files_cmd = 'ls {}|grep fwlog-host'.format(FWLOG_PATH)
        _, files = FileOperation.get_files_with_cmd(find_files_cmd=find_files_cmd, ip=self.hostnode_ip)
        found_file = []
        # 日志文件以日志结束时间为文件名
        max = '99999999-999999'
        for file in files:
            if constants.STR_MINUS.join([file.split('-')[2], file.split('-')[3]]) > end_time:
                if constants.STR_MINUS.join([file.split('-')[2], file.split('-')[3]]) < max:
                    max = constants.STR_MINUS.join([file.split('-')[2], file.split('-')[3]])
        for file in files:
            if start_time < constants.STR_MINUS.join([file.split('-')[2], file.split('-')[3]]) <= max:
                found_file.append(FWLOG_PATH + file)
        found_file = ' '.join(found_file) if files else ''
        return found_file if found_file else ''

    def check_environment_connection_and_reboot(self, log_start_time: str=None, log_end_time: str=None):
        """
        author:                 kaifeng.bi
        date:                   2021.11.15
        description:            检查环境是否可连接，如果不能连接则重启环境
        :param log_start_time:  日志起始时间
        :param log_end_time:    日志结束时间
        """
        self.script_log_info("########CHECK ENVIRONMENT CONNECTION AND REBOOT########")
        host_connection, ioc_connection, hostnode_pid, iocnode_pid = self.check_qemu_connection()
        if host_connection is False:
            CommandOperation.kill_process(process_id=hostnode_pid, ssh_ip=self.hostnode_ip)
            HostIocStart.add_host_node()
        if ioc_connection is False:
            CommandOperation.kill_process(process_id=iocnode_pid, ssh_ip=self.iocnode_ip)
            HostIocStart.add_ioc_node()

    def check_cli_status(self, log_start_time: str=None, log_end_time: str=None):
        """
        author:                 kaifeng.bi
        date:                   2021.11.15
        description:            获取cli状态
        :param log_start_time:  日志起始时间
        :param log_end_time:    日志结束时间
        """
        self.script_log_info("########CHECK CLI STATUS########")
        rtn_code, cli_info = ControllerOperation.check_cli_valid()
        if 'MGC:No such device' in cli_info:
            log.info('No Such Device')
        elif RtnStatusEnum.SUCCESS.value != rtn_code:
            log.info('cli execute failed, maybe timeout')
        else:
            log.info('cli execute successfully')

    def check_qemu_connection(self) -> tuple:
        """
        author:                 kaifeng.bi
        date:                   2021.11.15
        description:            检查qemu是否可以连接
        """
        def ping_node(ip):
            ping_flag = True
            cmd = "ping  -q -c 5  {}".format(ip)
            _, out, _ = CommandOperation.execute_command_with_error(cmd, ssh_ip=self.host_ip,
                                                                    ssh_port=self.host_port, timeout=300)
            if ', 0 received' in out:
                ping_flag = False
            log.info(f"ping node is {ping_flag} , {cmd} result: {out}")
            return ping_flag

        def get_node_process(ip, nodes, nodeName):
            pid = None
            node_id = None
            for node in nodes:
                if node['ip'] == ip:
                    node_id = node['id']
                    break
            if node_id:
                get_pid_cmd = 'ps -ef | grep {} | grep -v \'grep\' ' \
                              '| grep -v expander_Env | awk \'{{print $2}}\''.format(nodeName + node_id)
                cmd_code, pid, cmd_stderr = CommandOperation.execute_command_with_error(
                    cmd=get_pid_cmd, ssh_ip=self.host_ip, ssh_port=self.host_port, timeout=300)
                if not len(pid) > 0:
                    pid = None
                log.info(f"{get_pid_cmd} result: {pid}")
            return pid

        # 获取测试机所有qemu node
        nodes = HostOperation.get_node_info()
        # 测试hostqemu是否连通，ping 不通 且 进程存活
        log.info("check host node connection")
        host_connection = ping_node(self.hostnode_ip)
        host_node_pid = get_node_process(self.hostnode_ip, nodes, 'hostnode')
        log.info(f"host_node_pid is :{host_node_pid}")

        # 测试iocqemu是否连通，ping 不通 且 进程存活
        log.info("check ioc node connection")
        ioc_connection = ping_node(self.iocnode_ip)
        ioc_node_pid = get_node_process(self.iocnode_ip, nodes, 'iocnode')
        log.info(f"ioc_node_pid is :{ioc_node_pid}")

        return host_connection, ioc_connection, host_node_pid, ioc_node_pid

    def cat_log_by_time_with_keywords(self, log_path: str, start_time: str,
                                      end_time: str, keyword: str = "\'\'",
                                      cmd_execute_address: str = CmdExecuteAdressEnum.SOC_NODE.value,
                                      local_execute_flag: bool = False,
                                      need_separator_flag: bool = False,
                                      separator: str = '',
                                      time_begin_loc: int = 0) -> tuple:
        """
        author: xianda.liu
        date  : 2020.12.11
        description: 根据时间段（最小粒度为1秒钟）截取一段日志
        :param log_path: 日志路径（包含文件名，支持*的模糊匹配）
        :param start_time: 截取开始时间 格式：23/Nov/2020:19:00:00 (format:%d/%b/%Y:%H:%M:%S)
        :param end_time: 截取结束时间 格式：23/Nov/2020:19:00:00
        :param keyword: 可利用关键字进行log筛选，目前支持 单个关键字、多个关键字取或、并 这三种情况（"a","a|b","a|grep b"）
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选,默认为SOC_NODE
        :param local_execute_flag: 判定是否在本地主机执行命令，True表示在本地执行，False表示在远程执行,默认为False
        :param need_separator_flag: 是否需要分割符,用在awk -F后,默认False
        :param separator: 分隔符
        :param time_begin_loc: 时间字段在日志中起始位置 ps3_log默认为0 如果用分隔符，从1开始计算
        :return: 返回输出结果，错误信息, 为二元素元组 rtn_info, rtn_err
        """
        if log_path == '':
            return '', ''
        if "|grep" in keyword:
            items_list = keyword.split('|grep')
            keyword = "|grep ".join('' + i.strip() + '' for i in items_list)
        else:
            keyword = '-aE \"' + keyword + '\"'

        if not need_separator_flag:
            if PS3_LOG_PATH in log_path or NEW_FWLOG_PATH in log_path:
                command = """cat {} | awk '${} >="[{}" && ${} <="[{}"' | grep {}"""
            else:
                command = """cat {} | awk '${} >="{}" && ${} <="{}"' | grep {}"""
        else:
            command = """cat {} | awk -F""" + separator + """ '${} >="{}" && ${} <="{}"' | grep {}"""
        exec_command = command.format(log_path, str(time_begin_loc), start_time,
                                      str(time_begin_loc), end_time, keyword)
        rtn_info, rtn_err = CommandOperation.execute_command_based_paramiko(
            exec_command, cmd_execute_address,
            local_execute_flag)

        return rtn_info, rtn_err

    def get_keywords_from_fwlog(self, start_time: str,
                                end_time: str, keywords: list = FWLOG_KEYWORDS) -> list:
        """
        author: kaifeng.bi
        date  : 2022.08.19
        description: 从fwlog查找关键字
        :param start_time: 开始时间 格式：20220819000000 获取方法：_, start_tmie = CommandOperation.get_time()
        :param end_time: 结束时间 格式：20220819000000 获取方法：_, end_time = CommandOperation.get_time()
        :param keywords: 需要查找的关键字列表
        :return: 查找到的关键字列表
        """
        rtn_list = []
        # trigger日志
        CustomOperation.tigger_dump_log(ssh_ip=self.hostnode_ip)
        # 查找对应时间段的日志文件
        log_start_time, file_start_time = self.change_time_format_to_fwlog(start_time)
        log_end_time, file_end_time = self.change_time_format_to_fwlog(end_time)
        files = self.get_fwlog_files(file_start_time, file_end_time)
        # 创建新的文件夹
        FileOperation.make_directory(dir_name=NEW_FWLOG_PATH,
                                     ip=self.hostnode_ip, match_flag=False, delete_flag=True)
        # 复制文件
        FileOperation.copy_file(path=files, copy_path=NEW_FWLOG_PATH,
                                ip=self.hostnode_ip, match_flag=False,
                                file_check_flag=False)
        files = files.replace('/var/log/', NEW_FWLOG_PATH)
        files = files.split(' ')
        build_mode = CustomOperation.get_cli_build_mode_full(ssh_ip=self.hostnode_ip)
        new_files = ''

        for file in files:
            if file.find('tar.gz') > 0:
                FileOperation.uncompress_file(file, NEW_FWLOG_PATH, ip=self.hostnode_ip,
                                              match_flag=False, make_untardir_flag=False)
                file = file[:-7]

            new_file = file

            if build_mode != 'debug':
                new_file = file + '.log'
                translog_cmd = 'cd /root/tools;chmod +x transition.py;' + \
                               f'./transition.py transition.map* {file} > {new_file}'
                translog_code, _, translog_stderr = CommandOperation.execute_command_with_error(translog_cmd)
                # 日志转换操作成功，返回0
                if RtnStatusEnum.SUCCESS.value != translog_code:
                    log.error('translog file: {} to destination file: {}, Reason: {}'.format(
                        file, new_file, translog_stderr))

            new_files += (new_file + ' ')

        for keyword in keywords:
            log_rtn_info, log_rtn_err = self. \
                cat_log_by_time_with_keywords(new_files, log_start_time, log_end_time,
                                              keyword=keyword,
                                              cmd_execute_address=CmdExecuteAdressEnum.HOST_NODE.value)
            if log_rtn_info:
                rtn_list.append(keyword)
        log.error(rtn_list)
        return rtn_list

    def iostat_analysis(self) -> str:
        """
        author:                 xianda.liu
        date:                   2022.06.09
        description:            解析iostat log
        """
        iostat_log_full_path = os.path.join(constants.FILE_PATH_ROOT, self.IOSTAT_LOG_FILENAME)
        exec_command = 'cat ' + iostat_log_full_path
        rtn_code, rtn_outputs, _ = CommandOperation.execute_command_with_error(exec_command)
        err_msg = ''

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            import re
            pattern_timestamp = r'(\d*/\d*/\d* \d*:\d*:\d* \s*\S*)'
            # timestamp = '06/08/2022 08:21:19 PM'
            pattern_result = r'sd(\S*)\s+(\S*)\s+(\S*)\s+(\S*)\s+(\S*)\s+(\S*)\s*'
            # result = 'sdb               0.00         0.00         0.00          0          0'
            # 用\n\n分割
            content_list = rtn_outputs.split('\n\n')
            # 时间戳解析
            time_all_list, result_all_list = [], []
            for item in content_list:
                time_list = re.findall(pattern=pattern_timestamp, string=item)
                # iostat数据解析
                result_list = re.findall(pattern_result, item, re.S)
                if time_list:
                    time_all_list.append(time_list)
                if result_list:
                    result_all_list.append(result_list)

            for result_once in result_all_list:
                # 目前把盘符放在一起解析到item[0]
                for item in result_once:
                    if len(item) >= 1:
                        for i in range(1, len(item)):
                            # 目前发现0只有0和0.0两种形式
                            if eval(item[i]) != 0 and eval(item[i]) != 0.0:
                                break
                            else:
                                if i == len(item) - 1:
                                    err_msg += \
                                        '盘:sd{}在{}时出现跌0\n'.format(
                                            item[0], time_all_list[result_all_list.index(result_once)][0])
                                else:
                                    continue
        else:
            err_msg = '获取iostat日志时失败'
        return err_msg


def main() -> None:
    """
    author: kaifeng.bi
    descriptor: 执行日志分析
    date: 2021.09.27
    :return: 无返回值
    """
    log_analysis_obj = LogAnalysis(manual_flag=True,
                                   host_ip=CommandLineArgsParse.get_host_ip(),
                                   host_port=CommandLineArgsParse.get_host_port(),
                                   ioc_ip=CommandLineArgsParse.get_soc_ip(),
                                   ioc_port=CommandLineArgsParse.get_soc_port(),
                                   hostnode_ip=CommandLineArgsParse.get_host_node_ip(),
                                   iocnode_ip=CommandLineArgsParse.get_soc_node_ip()
                                   )
    log_analysis_obj.log_analysis(CommandLineArgsParse.get_log_start_time(),
                                  CommandLineArgsParse.get_log_end_time())
    log_analysis_obj.get_keywords_from_fwlog(CommandLineArgsParse.get_log_start_time(),
                                             CommandLineArgsParse.get_log_end_time())
    # log_analysis_obj.iostat_analysis()


if __name__ == '__main__':
    main()
