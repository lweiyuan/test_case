#!/usr/bin/python3
# -*- encoding=utf8 -*-
"""
author: sunql
description: PS3测试框架的入口脚本
    入口脚本的功能：
        1：准备测试环境
        2：组织脚本测试
        3：处理测试结果
"""
import os
import re
import time
import json
import copy
import multiprocessing
import ctypes
import random
import add_syspath
import subprocess
from framework.biz.classes.case_script_map import CaseScriptMap
from framework.biz.excel import bug_result_excel_handle, report_excel_create
from framework.libs.classes.bug import Bug
from framework.libs import commands, constants, utils_new as utils, utils_excel
from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.file_operation import FileOperation
from framework.model import config
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.iperf_operation import IperfOperation
from scripts.script_libs.dcbtool_operation import DcbtoolOperation
from scripts.script_libs.ethtool_operation import EthtoolOperation
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum, NicNameEnum, CaseOrderEnum
from scripts.script_libs import constants as script_constants


# 定义RunAllTest类，封装相关方法
class RunAllTest(object):
    # 定义用例关联对象
    case_script_dict = None
    # 定义配置信息变量
    config_dict = None
    # 定义日志服务器、测试主机、PS3测试服务器的ip
    ip_dict = None
    # 测试结果中report_log路径
    test_report_log_file_path = None
    # 测试报告excel文件名称及路径
    test_report_excel_file_path = None

    # 定义日志收集对象 collect_log = None
    # 测试bug列表excel文件路径 test_bug_excel_file_path
    # 测试result列表excel文件路径 test_result_excel_file_path
    # run all test的日志文件名称及路径 run_all_test_log_file = None
    # 测试脚本的日志文件目录 test_script_log_directory = None
    # bug对象，用于bug信息收集 bug_object = None
    # 代码覆盖率标志位  gcov_flag = None
    # bug_stop 开关
    # bug_stop = False
    case_list_order = CaseOrderEnum.DEFAULT_ORDER.value
    # 随机执行case
    random_exec = False
    # 是否长稳测试
    long_stab_test = False
    # 记录是否存在bug
    g_bug_existed = False
    # 脚本测试通过数
    pass_num = 0
    # 脚本测试失败数
    fail_num = 0
    # 脚本测试跳过数
    skip_num = 0
    # 脚本不存在数
    not_exist_num = 0
    # 脚本发生异常数
    except_num = 0
    # 脚本超时数
    timeout_num = 0
    # jenkins ps3_**_prepare job id
    job_id = None
    # jenkins ps3_**_prepare job name
    job_name = None
    # outputs/framework下当前测试脚本结果保存的目录名，如：ps3_auto_test_prepare_14093_20210610175943
    job_directory_name = None
    # outputs/framework下当前测试脚本结果保存的目录绝对路径，如：/home/test/ps3test/vms/vm204/ps3/test/esat/outputs/
    # framework/ps3_auto_test_prepare_14093_20210610175943
    job_directory_path = None
    # 保存解析测试单excel或csv文件的数据
    # script_case_dict = None
    # 本次测试日志保存在日志服务器上的路径，如：/home/framework/log/host_vm670_10.22.81.1_22/2021_06_11/16_03_12
    log_server_path = None
    # 测试轮次
    test_rounds = None

    # 测试开始时间戳
    test_start_timestamp = None
    # 测试开始时间,格式为20200423151820
    test_start_time = None
    # 整个测试耗时时长，单位为妙
    test_total_seconds = None
    # test/esat/scripts目录
    scripts_directory = None

    frame_model_config = {}
    frame_model = None

    # 测试项目
    test_project = None

    # 停止测试标志位  test_stop = False
    framework_run_dict = {'test_stop': False}
    # core和crash检查
    abnormal_dict = {"core": {"server": [], "client": []}, "crash": {"server": [], "client": []}}
    # 确认是否可以使用3322端口测试
    test_port = 22
    version_compatibility_test = False
    # 本次job执行用于回传禅道的关键信息
    jenkins_job_info = {}
    log_waring = []

    @classmethod
    def __get_collect_log_obj(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-02-26 16:36:27
        description: 获取LogCollect类实例
        :return:     None
        """
        log_obj_path = cls.frame_model_config.get('log_collect', None)
        if not log_obj_path:
            log.error('Invalid log_obj_path: {}.'.format(log_obj_path))
            exit(1)

        log_obj_model = __import__(log_obj_path, fromlist=['None'])
        cls.framework_run_dict['collect_log'] = log_obj_model.LogCollect(cls.framework_run_dict)

    @classmethod
    def __get_case_script_map_obj(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-02-26 16:39:06
        description: 获取CaseScriptMap类实例

        :return:     None
        """
        cls.case_script_dict = CaseScriptMap()

    @classmethod
    def __get_env_configure_data(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-02-26 16:41:59
        description: 获取测试需要的环境配置信息及日志服务器、测试主机、PS3测试服务器的ip

        :return:     None
        """
        cls.config_dict, cls.ip_dict = utils.get_conf()
        cls.framework_run_dict['config_dict'] = cls.config_dict
        cls.framework_run_dict['ip_dict'] = cls.ip_dict
        # add by hejf,根据测试机是否开放3322端口确定测试端口
        cls.__init_test_port(update=False)

    @classmethod
    def __chmod_env_conf(cls):
        """
        修改envconf下所有文件权限 为 777，用于适配外网测试时权限问题
        :return:
        """
        cmd = f"chmod -R 777 {constants.ENV_CONF_DIRECTORY}"
        CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd, local_execute_flag=True,
                                                                     print_enable=True)

    @staticmethod
    def __isvalid(param=None) -> bool:
        """
        author:      haibin.xu
        date:        2021-06-08 15:34:55
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
    def __get_framework_parameters(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-03-20 16:56:11
        description: 获取相关类变量

        :return:     None
        """
        # cls.test_project = 'sagitta'
        cls.test_project = cls.config_dict.get(constants.ENV_TEST_PROJECT)
        if not cls.__isvalid(cls.test_project):
            log.error('Fail to get test_project: {}.'.format(cls.test_project))
            exit(1)

        cls.job_id = cls.config_dict.get(constants.ENV_JOB_ID)
        if not cls.__isvalid(cls.job_id):
            log.error('Fail to get job_id: {}.'.format(cls.job_id))
            exit(1)

        cls.job_name = cls.config_dict.get(constants.ENV_JOB_NAME)
        if not cls.__isvalid(cls.job_name):
            log.error('Fail to get job_name: {}.'.format(cls.job_name))
            exit(1)

        # 执行测试任务轮数
        cls.test_rounds = cls.config_dict.get(constants.ENV_TEST_ROUNDS)
        if not cls.__isvalid(cls.test_rounds) and (1 > cls.test_rounds):
            log.error('Invalid test rounds: {}.'.format(cls.test_rounds))
            exit(1)

        cls.framework_run_dict['bug_stop'] = cls.config_dict.get(constants.ENV_BUG_STOP)
        if not cls.__isvalid(cls.framework_run_dict['bug_stop']):
            log.warning('Fail to get bug stop, set it default value: False')
            cls.framework_run_dict['bug_stop'] = False

        cls.long_stab_test = cls.config_dict.get(constants.ENV_LONG_STAB_TEST)
        if not cls.__isvalid(cls.long_stab_test):
            log.warning('Fail to get long stab test, set it default value: no')
            cls.long_stab_test = False

        cls.random_exec = cls.config_dict.get(constants.ENV_RANDOM_EXEC)
        if not cls.__isvalid(cls.random_exec):
            log.warning('Fail to get random_exec, set it default value: no')
            cls.random_exec = False
        else:
            log.info(f"random_exec value is : {cls.random_exec}")

    @classmethod
    def __get_project_frame_model(cls):
        frame_model_path = cls.frame_model_config.get('model_path', None)
        if not frame_model_path:
            log.error('Invalid model_path: {}.'.format(frame_model_path))
            exit(1)

        frame_model = __import__(frame_model_path, fromlist=['None'])
        cls.frame_model = frame_model.FrameworkModel

    @classmethod
    def __get_project_parameters(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-03-20 16:56:11
        description: 获取相关类变量

        :return:     None
        """
        log.info("framework_run_dict:{}".format(cls.framework_run_dict))
        cls.frame_model.get_project_parameters(cls.framework_run_dict)

    @classmethod
    def __init_test_port(cls, update: bool=True) -> None:
        """
        author:      haibin.xu
        date:        2021-03-20 16:56:11
        description: 获取相关类变量

        :return:     None
        """
        cls.test_port = 22
        server_ip = cls.framework_run_dict["ip_dict"]["server_nic_ip"]
        client_ip = cls.framework_run_dict["ip_dict"]["client_nic_ip"]

        server_support_3322 = False
        if cls.config_dict.get(constants.ENV_TEST_ENTRY) == constants.TEST_ENTRY_UEFI_MODE:
            log.info("uefi测试模式，无需进行os下的配置与检查")
            if cls.config_dict.get(constants.ENV_JENKINS_IP, 'unknow') in ["10.17.22.136", "172.17.30.145", "172.17.229.18"]:
                cls.test_port = 3322
            return
        else:
            cmd = "nc -zv {} 3322".format(server_ip)
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation. \
                execute_command_based_paramiko_with_rtncode(cmd=cmd, local_execute_flag=True)
            log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
            if "Connected" in cmd_output + cmd_stderr:
                server_support_3322 = True
            else:
                server_support_3322 = False

        # 是否发包仪环境
        client_is_renix = False
        cmd = 'cat /root/sxetest/env_config.ini|grep -A 3 relationships|grep client'
        if server_support_3322:
            ssh_server_port = '3322'
        else:
            ssh_server_port = '22'
        cmd_rtn, cmd_output, cmd_stderr = CommandOperation. \
            execute_command_based_paramiko_with_rtncode(cmd=cmd, ssh_ip=server_ip, ssh_port=ssh_server_port)
        log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
        if cmd_output.count('/') > 3:
            client_is_renix = True

        if cls.config_dict.get(constants.ENV_TEST_ENTRY) == constants.TEST_ENTRY_SINGLE_MODE or client_is_renix:
            client_support_3322 = server_support_3322
        else:
            cmd = "nc -zv {} 3322".format(client_ip)
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation. \
                execute_command_based_paramiko_with_rtncode(cmd=cmd, local_execute_flag=True)
            log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
            if "Connected" in cmd_output+cmd_stderr:
                client_support_3322 = True
            else:
                client_support_3322 = False
            if cls.config_dict.get(constants.ENV_TEST_ENTRY) == constants.TEST_ENTRY_UEFI_MODE:
                server_support_3322 = client_support_3322

        if server_support_3322 and client_support_3322:
            cls.test_port = 3322
        log.info("==> init_test_port:{}".format(cls.test_port))
        cls.framework_run_dict['ip_dict']['test_port'] = cls.test_port
        if update:
            cls.__get_project_parameters()

    @classmethod
    def __get_bug_obj(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 17:12:59
        description: 初始化bug对象, 用于后续的bug收集

        :return:     None
        """
        # 将测试环境、测试目标、测试任务信息设置到bug对象中
        cls.framework_run_dict['bug_object'] = Bug()
        cls.framework_run_dict['bug_object'].set_common_values(cls.config_dict, cls.ip_dict)

    @classmethod
    def __get_test_start_time_info(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 14:15:11
        description: 设置测试开始时间参数

        :return:     None
        """
        # 任务开始测试时间，格式为20200423151820(2020年4月23日)
        cls.framework_run_dict['test_start_timestamp'], cls.test_start_time = CommandOperation.get_time()

    @classmethod
    def __init_run_all_test_log_file(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 14:58:07
        description: 初始化run_all_test_ps3_[timestamp].log文件，日志路径test/esat/outputs/framework/

        :return:     None
        """
        log.info("init run all test log file")
        # 获取当前测试文件名，即run_all_test_ps3
        script_file_name, _ = CommandOperation.get_file_info(os.path.abspath(__file__))
        log.info('script file name: {}'.format(script_file_name))
        # 初始化当前脚本的日志文件, 如test/esat/outputs/framework/run_all_test_ps3_20210611145106.log
        cls.framework_run_dict[
            'run_all_test_log_file'] = utils.make_run_all_test_log(cls.test_start_time, script_file_name)

    @classmethod
    def __init_outputs_job_directory(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 15:25:15
        description: 初始化test/esat/outputs/framework/目录下的[job_name]_[job_id]_[测试开始时间戳]目录，全路径如：
                     test/esat/outputs/framework/ps3_auto_test_prepare_14093_20210610175943

        :return:     None
        """
        # 生成测试任务信息列表, 即[job_name, str(job_id), task_start_time]
        job_info_list = utils.make_job_info_list(cls.test_start_time)
        # 生成正在执行的测试job的输出信息目录, 即test/esat/outputs/framework/ps3_auto_test_prepare_14093_20210610175943
        cls.job_directory_path, cls.job_directory_name = utils.make_job_outputs_dir(job_info_list)
        cls.framework_run_dict['job_directory_path'] = cls.job_directory_path
        cls.framework_run_dict['job_directory_name'] = cls.job_directory_name
        log.info('outputs job directory path: {}; job directory name: {}'.format(cls.job_directory_path,
                                                                                 cls.job_directory_name))

    @classmethod
    def __get_script_case_info(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 16:25:20
        description: 解析测试用例case文件，获取需要测试的脚本信息，如禅道触发，文件路径一般为：test/esat/scripts/
                     case_script_lists/zentao_auto/case_script_20210506101716.xlsx, 如Jenkins触发，文件路径一般为：test/
                     esat/scripts/case_script_lists/common/mini_case_script_list.csv

        :return:     None
        """
        cls.framework_run_dict['script_case_dict'] = cls.case_script_dict.case_script_dict_get()

    @classmethod
    def __get_shuffle_script_case_info(cls) -> None:
        """
        author:      sunql
        date:        2021-08-19
        description: 返回打乱顺序后的cases字典
        :return: None
        """
        log.info("__get_shuffle_script_case_info ->:{}".format(cls.random_exec))
        if cls.long_stab_test or cls.random_exec:
            dict_key_ls = list(cls.framework_run_dict['script_case_dict'].keys())
            random.shuffle(dict_key_ls)
            # 多执行一次，确保乱序
            random.shuffle(dict_key_ls)
            new_dict = {}
            for key in dict_key_ls:
                new_dict[key] = cls.framework_run_dict['script_case_dict'].get(key)
            cls.framework_run_dict['script_case_dict'] = new_dict
            log.info("shuffle cases to random")

    @classmethod
    def __save_shuffle_script_case_to_excel(cls) -> None:
        """
        author:      sunql
        date:        2021-08-19
        description: 保存打乱顺序后的cases至excel
        :return:
        """
        try:
            _ = (CaseScriptMap()).shuffle_case_script_file_create(cls.framework_run_dict['script_case_dict'],
                                                                  cls.framework_run_dict['test_script_log_directory'])
        except Exception as e:
            log.error("can not create shuffle script case excel:\n{}".format(e))

    @classmethod
    def __init_log_directory_in_log_server(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 16:33:51
        description: 在日志服务器上初始化本次测试的日志保存路径，如：/home/framework/log/host_vm670_10.22.81.1_22/
                     2021_06_11/16_03_12

        :return:     None
        """
        cls.framework_run_dict['log_server_path'] = cls.framework_run_dict['collect_log']. \
            make_log_root_directory_in_log_server()
        if cls.framework_run_dict['log_server_path'] == '':
            log.error('make log_directory_in_log_server is fail , test stop')
            exit(1)

    @classmethod
    def __init_test_bug_and_result_file(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 16:42:59
        description: 初始化本次测试的bug, result的Excel文件，如：test/esat/outputs/framework/
                     ps3_auto_test_prepare_5688_20210611160312/bugs/
                     ps3_auto_test_prepare_5688_20210611160312_bugs.xlsx, test/esat/outputs/framework/
                     ps3_auto_test_prepare_5688_20210611160312/results/
                     ps3_auto_test_prepare_5688_20210611160312_results.xlsx

        :return:     None
        """
        # 生成问题列表文件和结果列表文件
        cls.framework_run_dict['test_bug_excel_file_path'], cls.framework_run_dict[
            'test_result_excel_file_path'] = bug_result_excel_handle.create_files(
            cls.job_directory_path, cls.job_directory_name)

    @classmethod
    def __init_test_report_log_file(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 16:53:20
        description: 初始化测试报告日志文件，如：test/esat/outputs/framework/
                     ps3_auto_test_prepare_5688_20210611160312/report_log_20210611160312.log

        :return:     None
        """
        report_log_file_name = '{}_{}.log'.format(constants.REPORT_LOG_FILE_NAME, cls.test_start_time)
        cls.test_report_log_file_path = os.path.join(cls.job_directory_path, report_log_file_name)

    @classmethod
    def __init_test_scripts_directory(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 17:02:00
        description: 初始化测试脚本日志目录，即：test/esat/outputs/framework/ps3_auto_test_prepare_5688_20210611160312/
                     test_script_logs

        :return:     None
        """
        cmd = f"mkdir -p {constants.ESAT_PATH_OUT_PUTS_SCRIPTS_PATH}"
        cmd_rtn, cmd_output, cmd_stderr = CommandOperation. \
            execute_command_based_paramiko_with_rtncode(cmd=cmd, local_execute_flag=True)
        log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))

        cls.framework_run_dict['test_script_log_directory'] = utils.make_scripts_log(cls.job_directory_path)

    @classmethod
    def __modify_log_directory_in_log_server(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 10:15:30
        description: 修改日志服务器上当前测试日志目录的访问权限

        :return:     None
        """
        # 修改日志服务器上收集到的日志的访问者权限
        log.info("Will modify log directory access authority in log server.")
        cls.framework_run_dict['collect_log'].modify_log_permission(
            cls.framework_run_dict.get('log_server_path', ''))

    @classmethod
    def __get_test_total_time(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 10:20:00
        description: 获取本次测试的总时长，单位为秒

        :return:     None
        """
        # 测试结束时间戳
        test_end_timestamp, _ = CommandOperation.get_time()
        cls.test_total_seconds = int((test_end_timestamp -
                                      cls.framework_run_dict['test_start_timestamp']) / constants.TIME_RATIO)

    @classmethod
    def __make_test_report_file(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 10:41:11
        description: 生成test/esat/outputs/framework/ps3_auto_test_prepare_5688_20210611160312/reports/
                     ps3_auto_test_prepare_5688_20210611160312_report.xlsx

        :return:     None
        """
        # 获取create_report_excel.py的绝对路径
        log.info(constants.REPORT_CREATE_START)
        create_report_script_path = report_excel_create.get_current_absolute_path()
        if not cls.__isvalid(create_report_script_path):
            log.error(constants.REPORT_PATH_FAIL % create_report_script_path)
            exit(1)

        # 生成测试报告
        cls.test_report_excel_file_path = utils.make_test_report_file(
            create_report_script_path, cls.test_start_time, str(cls.test_total_seconds),
            cls.framework_run_dict['test_bug_excel_file_path'], cls.framework_run_dict['test_result_excel_file_path'],
            cls.test_report_log_file_path)
        if not cls.__isvalid(cls.test_report_excel_file_path):
            log.error(constants.REPORT_CREATE_FAIL)
            exit(1)
        log.info(constants.REPORT_CREATE_SUC)

    @classmethod
    def __get_scripts_directory(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 11:30:49
        description: 获取脚本所在的scripts目录，即/test/esat/scripts目录

        :return:     None
        """
        cls.scripts_directory = CommandOperation.format_linux_path_sep(constants.SCRIPTS_DIRECTORY)
        log.info('scripts common directory: {}'.format(cls.scripts_directory))

    @classmethod
    def __handle_script_test_result_info(cls, script_name: str = None, result_type: str = None,
                                         script_info_list: list = None, result_file: str = None,
                                         script_test_output: str = None) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 14:33:23
        description: 处理单个脚本测试结果信息，即将脚本的测试结果信息写到result excel文件中

        :param script_name: 脚本名
        :param result_type: 脚本状态类型
        :param script_info_list: 脚本信息
        :param result_file: result excel文件路径
        :param script_test_output: 脚本测试输出信息
        :return:    None
        """
        handle_result_flag = True
        if constants.SCRIPT_CASE_NON_EXIST == result_type:
            # 没有脚本测试信息
            log.error(constants.CASE_NOT_EXIST_INFO % script_name)
            cls.not_exist_num += 1
        elif constants.SCRIPT_NON_EXIST == result_type:
            # 有脚本测试信息，但是脚本不存在
            log.error(constants.SCRIPT_NOT_EXIST_INFO % script_name)
            cls.not_exist_num += 1
        elif constants.REPORT_COL_SCRIPT_SKIP == result_type:
            # cli 部署ip连接失败
            log.error(constants.PING_CMD_FAIL_INFO % script_name)
            cls.skip_num += 1
        elif 'framework' == result_type:
            # framework发现bug时使用
            pass
        else:
            handle_result_flag = False

        if handle_result_flag:
            # 将测试结果信息写到result excel文件中
            utils.handle_result_info(script_info_list, result_file, script_test_output, result_type)

    @classmethod
    def __get_paramters_before_script_test(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 15:53:22
        description: 获取脚本测试前的一些参数
                     返回脚本开始时间戳，开始时间，测试前的内存占用等
        """
        # 脚本开始执行时间戳
        cls.framework_run_dict['start_timestamp'], cls.framework_run_dict[
            'start_time'] = CommandOperation.get_time(time_format='%Y-%m-%d %H:%M:%S')

    @classmethod
    def __get_paramters_after_script_test(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 16:14:21
        description: 获取脚本测试后的一些参数
                    返回脚本结束时内存占用差值，脚本测试前后时间
        """
        # 测试脚本执行时长
        cls.framework_run_dict['time_duration'] = round(
            float(time.time() - cls.framework_run_dict['start_timestamp']), constants.DURATION_ROUND_BIT)

    @classmethod
    def before_exec_script(cls):
        # 获取测试前的时间戳，开始时间，内存占用
        cls.__get_paramters_before_script_test()

        cls.frame_model.before_exec_script()

        # 脚本执行前，框架做环境检查，获取当前状态下的crash和core状态
        cls.abnormal_dict = cls.frame_model.env_abnormal_check()

    @classmethod
    def after_exec_script(cls):
        # 获取测试后测试时长
        cls.__get_paramters_after_script_test()

        # 脚本执行完成后，框架做环境检查
        bug_need_stop, desc = cls.frame_model.env_status_check(cls.abnormal_dict,
                                                               cls.framework_run_dict['script_rtn_code'])
        if desc:
            cls.framework_run_dict['script_rtn_code'] = constants.RETURN_CODE_FAIL

        # 生成result对象，并将测试开始时间，测试时间，内存差值赋值
        cls.framework_run_dict['result_object'] = cls.frame_model.create_result_object(cls.framework_run_dict)

        cls.frame_model.after_exec_script()

        cls.__handle_script_return_code()

        # 下面这步会进行日志采集
        utils.handle_script_return_code(cls.framework_run_dict)

        if desc:
            cls.__create_framework_bug(
                f"环境异常=>[{desc}] {cls.framework_run_dict['script_name']}", '')
            log.info("环境检查异常，将上次测试脚本结果由{}改成{}".
                     format(cls.framework_run_dict['script_rtn_code'], constants.RETURN_CODE_FAIL))

        cls.frame_model.env_check_and_recover()

        cls.__check_bug_stop()

        cls.frame_model.after_check_bug()

        # 修改日志服务器上当前测试日志目录的访问权限
        # cls.__modify_log_directory_in_log_server()

    @classmethod
    def before_framework_exit(cls):
        # 框架在最后结束前作一次检查
        desc = cls.frame_model.before_framework_exit()
        if desc:
            cls.__create_framework_bug(
                f"框架结尾检查异常=>[job id:{cls.job_id}] ->\n{desc} ", '')
            cls.framework_run_dict['script_rtn_code'] = constants.RETURN_CODE_FAIL

            # 生成result对象，并将测试开始时间，测试时间，内存差值赋值
            cls.framework_run_dict['result_object'] = cls.frame_model.create_result_object(cls.framework_run_dict)

            cls.__handle_script_return_code()
            # 下面这步会进行日志采集
            utils.handle_script_return_code(cls.framework_run_dict)

            # 修改日志服务器上当前测试日志目录的访问权限
            # cls.__modify_log_directory_in_log_server()

    @classmethod
    def __check_bug_stop(cls) -> None:
        """
        检查bug_stop参数, 设置test_stop标志
        script_rtn_code: 脚本测试返回码
        :return:
        """
        log.info(
            f"bug_stop is: {cls.framework_run_dict['bug_stop']},"
            f"script_rtn_code is:{cls.framework_run_dict['script_rtn_code']}")
        if cls.framework_run_dict['bug_stop'] and cls.frame_model.check_bug_stop(
                cls.framework_run_dict['script_rtn_code']):
            cls.framework_run_dict['test_stop'] = True

        if utils.parse_stop_test(cls.framework_run_dict['script_rtn_output']):
            cls.framework_run_dict['test_stop'] = True

        if constants.RETURN_CODE_SUCCESS != cls.framework_run_dict['script_rtn_code']:
            bug_need_stop, desc = cls.frame_model.env_status_check(cls.abnormal_dict,
                                                                   cls.framework_run_dict['script_rtn_code'])
            if bug_need_stop:
                cls.framework_run_dict['test_stop'] = True
                log.info(f"当前用例脚本测试未通过，再次检查环境，{desc}，设置bug stop，框架退出测试!!!!！")
                cls.__create_framework_bug(f"当前用例脚本测试未通过，再次检查环境，{desc},设置bug stop，框架退出测试!!!", 'ping')

        if not cls.framework_run_dict.get('collect_log_flag', True):
            # cls.framework_run_dict['test_stop'] = True
            log.error("日志收集失败，请确认测试主机与日志服务器之间是否是双向免密！！！")
            cls.__create_framework_bug(f"日志收集失败{cls.framework_run_dict['script_name']}", 'collect_log')

    @classmethod
    def __create_framework_bug(cls, title, tool):
        test_case = dict()
        test_case[constants.CASE_SCRIPT_SCRIPT_LOCATION] = 'framework'
        test_case[constants.CASE_SCRIPT_CASE_TITLE] = ''
        case_dict_list = [test_case]
        # 构造bug字典
        bug_dict = {}
        # 生成Bug信息
        bug_object = Bug()
        bug_object.set_common_values(cls.config_dict, cls.ip_dict)
        bug_object.set_title(title)
        bug_object.set_type_name('框架执行失败')
        bug_object.set_test_tool(tool)
        bug_object.set_precondition('')
        if cls.framework_run_dict.get('bug_object', ''):
            latest_scripts_steps = cls.framework_run_dict['bug_object'].steps
        else:
            latest_scripts_steps = ""
        bug_object.set_steps(f"{latest_scripts_steps}\n\n==>以上步骤执行完后，框架检查到BUG")
        bug_object.set_log_path(cls.framework_run_dict.get('log_path', 'NA'))
        bug_dict = bug_result_excel_handle.append_bug_to_excel(
            bug_object, case_dict_list, cls.framework_run_dict.get('test_bug_excel_file_path'))
        # 提交bug信息到禅道
        utils.submit_to_zentao(result_data={}, bug_data=bug_dict)

    @classmethod
    def __handle_script_return_code(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 17:09:39
        description: 处理测试返回码
        :return:  返回测试终止标志位，ioc core文件存在标志位，ioc crash文件存在标志位，host crash文件是否存在标志位
        """
        if constants.RETURN_CODE_FAIL == cls.framework_run_dict['script_rtn_code']:
            cls.fail_num += 1
            cls.g_bug_existed = True
        elif constants.RETURN_CODE_SUCCESS == cls.framework_run_dict['script_rtn_code']:
            cls.pass_num += 1
        elif constants.RETURN_CODE_TIMEOUT == cls.framework_run_dict['script_rtn_code']:
            cls.timeout_num += 1
            # @overwirte 临时方案先将timeout脚本数量并入failed数量中，后期timeout单独统计
            cls.fail_num += 1
            # @overwrite end
            cls.g_bug_existed = True
        elif constants.RETURN_CODE_EXCEPTION == cls.framework_run_dict['script_rtn_code']:
            cls.except_num += 1
        else:
            cls.skip_num += 1

    @classmethod
    def __force_to_exit_test(cls):
        """
        根据测试框架下的文件检测是否要强制退出本轮测试
        :return: bool
        @changelog      2023-02-06 13:36:46  junfeng.he
        """
        exit_file = "{}/exit_test.txt".format(cls.scripts_directory.replace("nic100/", "").replace("nic/", ""))
        log.info("=========> you can execute [echo 'exit' > {}] force to exit test.<=========".format(exit_file))
        file_content = FileOperation.read_local_file(exit_file)
        log.info("=========> current value:{} ".format(file_content))
        if "exit" in file_content:
            log.info("=========> trigger force to exit test!!!! <=========".format())
            return True
        else:
            return False

    @classmethod
    def __clear_exit_test_file(cls):
        """
        根据测试框架下的文件检测是否要强制退出本轮测试
        :return: bool
        @changelog      2023-02-06 13:36:46  junfeng.he
        """
        exit_file = "{}/exit_test.txt".format(cls.scripts_directory.replace("nic100/", "").replace("nic/", ""))
        file_content = FileOperation.read_local_file(exit_file)
        log.info("=========> current value:{}".format(file_content))
        if "exit" in file_content:
            FileOperation.write_local_file(exit_file, "continue")
            file_content = FileOperation.read_local_file(exit_file)
            log.info("=========> return the file[{}] content to {}.".format(exit_file, file_content))

    @classmethod
    def get_product_info(cls, server_os_type) -> tuple:
        log.info("=========> get_product_info:")
        if cls.config_dict.get(constants.ENV_TEST_ENTRY) == constants.TEST_ENTRY_UEFI_MODE:
            log.info("uefi测试模式，无需进行os下的配置与检查")
            cli_version = "unknow"
            fw_version = "unknow"
            product_name = "nic100"
            option_rom_version = "unknow"
            kernel = ""
            host_os = "unknow"
            driver_version = "unknow"
            return cli_version, fw_version, product_name, option_rom_version, host_os, kernel, driver_version

        fpga_bit_version = "none"
        server_ip = cls.framework_run_dict['ip_dict']['server_ip']
        nicg = CommonOperation.get_nic_generation()
        if server_os_type == "windows":
            host_os = "unknow"
            kernel = ""
            cmd = f"{nicg}cli show"
        else:
            cmd = "uname -a"
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            kernel = cmd_output
            cmd = "cat /etc/os-release"
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            prety_name = re.findall(r'PRETTY_NAME="(.*)"', cmd_output)
            if prety_name:
                host_os = prety_name[0]
            else:
                host_os = "unknow"
            cmd = f"{nicg}cli show"
        cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        cli_versions = re.findall(r'CLI Version\s+=\s+(\S+)', cmd_output)
        if cli_versions:
            cli_version = cli_versions[0]
        else:
            cli_version = "unknow"
        fw_versions = re.findall(r'\s+\|(\S+\.\S+\.\S+\.\S+)\s+', cmd_output)
        if fw_versions:
            fw_version = fw_versions[0]
            if len(fw_versions) >= 2:
                option_rom_version = fw_versions[1]
            else:
                option_rom_version = "unknow"
        else:
            fw_version = "unknow"
            option_rom_version = "unknow"
        bdfs = re.findall(r'(\d\d\d\d)\s+\|(\d+:\d+.\d+)\s+', cmd_output)
        devs = re.findall(r'\S{2}:\S{2}:\S{2}:\S{2}:\S{2}:\S{2}\s*\|(\S+)', cmd_output)
        driver_version = "unknow"
        if bdfs:
            bdf = bdfs[0][0] + ":" + bdfs[0][1]
            if server_os_type == "windows":
                product_name = "nic100"
            else:
                cmd = "ethtool -i {}".format(devs[0])
                server_ip = cls.framework_run_dict['ip_dict']['server_ip']
                cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                driver_versions = re.findall(r"version: (\S+)", cmd_output)
                if driver_versions:
                    driver_version = driver_versions[0]
                else:
                    driver_version = "unknow"
                cmd = "lspci -vvvs {} | grep 'Product'".format(bdf)
                server_ip = cls.framework_run_dict['ip_dict']['server_ip']
                cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                product_names = re.findall(r'Product Name:(.+)', cmd_output)
                if product_names:
                    product_name = product_names[0]
                else:
                    product_name = "nic100"

                cmd = f"{nicg}cli -d {bdf} get reg type=A width=32 addr=0xB800248C"
                cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                fpga_bit_versions = re.findall(r'0xb800248c \|(\S+)', cmd_output)
                if fpga_bit_versions:
                    fpga_bit_version = fpga_bit_versions[0]
                else:
                    fpga_bit_version = "unknow"
                CommonOperation.set_fpga_bit_version(value=fpga_bit_version)
        else:
            product_name = "nic100"

        pf_com_mode = CommonOperation.get_com_mode("pf")
        vf_com_mode = CommonOperation.get_com_mode("vf")
        com_mode = f"{pf_com_mode}-{vf_com_mode}"
        log.info("host_os:{}, kernel:{}, driver_version:{}, cli_version:{}, fw_version:{}, product_name:{}, fpga_bit_version:{}, com_mode:{}".format(
            host_os, kernel, driver_version, cli_version, fw_version, product_name, fpga_bit_version, com_mode))
        return cli_version, fw_version, product_name, option_rom_version, host_os, kernel, driver_version, com_mode

    @classmethod
    def do_script_test(cls, rounds: int) -> None:
        """
        author: luyafei
        date  : 2020.04.21
        执行脚本测试
        :return: None

        @changelog      2021-02-27 09:41:11  haibin.xu
                        1. 作为类方法并入RunAllTestPs3类
                        2021-06-13 09:48:06  haibin.xu
                        1. 优化函数实现， 去掉所有参数，全部以类变量代替，封装代码块，函数返回值修改为None
                        2021-08-19          sunql
                        1、增加长稳测试 空转逻辑
                        2、增加长稳测试 检查qemu log磁盘空间并清理逻辑
                        2022-06-03 09:19:51  haibin.xu
                        1. 优化函数实现, expander物理环境下，每个case测试前更新ps3explog记录信息
        """
        # 获取脚本所在的scripts目录，即/test/esat/scripts目录
        cls.__get_scripts_directory()
        # 清除强制退出内容
        cls.__clear_exit_test_file()

        # 根据拓扑获取发布优先级
        server_os, _ = CommonOperation.get_nic_os()
        renix_server_list, renix_locations_list = CommonOperation.get_renix()

        # 是否发包仪环境
        if renix_server_list:
            client_is_renix = True
        else:
            client_is_renix = False

        if (cls.config_dict.get(constants.ENV_TEST_ENTRY) == constants.TEST_ENTRY_SINGLE_MODE or
                client_is_renix or cls.config_dict.get(constants.ENV_TEST_ENTRY) == constants.TEST_ENTRY_UEFI_MODE):
            CommonOperation.set_single_test_mode(value="yes")
            log.info("当前设置为单机测试模式，不会检查两端是否能ping通")
        else:
            CommonOperation.set_single_test_mode(value="no")

        if server_os == "windows":
            publish_pri, publish_pri_ext = "1", "Windows"
        else:
            publish_pri, publish_pri_ext = "0", "Linux"
        platform_case_info = {'publish_pri': publish_pri, 'publish_pri_ext': publish_pri_ext}

        cls.framework_run_dict['publish_pri'] = publish_pri
        cls.framework_run_dict['publish_pri_ext'] = publish_pri_ext
        try:
            cli_version, fw_version, product_name, option_rom_version, host_os, kernel, driver_version, com_mode = cls.get_product_info(server_os)
            platform_case_info['ioc_version'] = fw_version
            platform_case_info['test_object'] = 'nic100'
            platform_case_info['host_os'] = host_os
            platform_case_info['product_name'] = product_name
            platform_case_info['cli_version'] = cli_version
            platform_case_info['option_rom_version'] = option_rom_version
            platform_case_info['jenkins_job_id'] = cls.job_id
            platform_case_info['jenkins_ip'] = cls.config_dict.get(constants.ENV_JENKINS_IP, '')
            platform_case_info['job_uuid_id'] = cls.config_dict.get(constants.ENV_JOB_UUID, '')
            platform_case_info['host_label'] = cls.config_dict.get(constants.ENV_HOST_LABEL, '')
            platform_case_info['kernel'] = kernel
            platform_case_info['driver_version'] = driver_version
            platform_case_info['com_mode'] = com_mode

        except Exception as e:
            log.error(e)

        cls.framework_run_dict['test_platform_info'] = json.dumps(platform_case_info)

        # 创建fail_rebuild.csv,可用于后续补测
        fail_rebuild_csv_path = os.path.join(cls.scripts_directory.split("ps3/test")[0], "fail_rebuild.csv")
        cls.__create_rebuild_csv(fail_rebuild_csv_path)
        if cls.random_exec:
            # 创建random_rebuild.csv,可用于后续按random后顺序重测
            random_rebuild_csv_path = os.path.join(cls.scripts_directory.split("ps3/test")[0], "random_rebuild.csv")
            cls.__create_rebuild_csv(random_rebuild_csv_path)

        # 清空测试fail用例记录
        cls.frame_model.clear_Testles_failed_test_case()
        # 备份自动生成的用例表格
        cls.frame_model.backup_Testles_zento_test_case()

        cls.framework_run_dict['script_run_num'] = 0

        stats_results = {"total": len(cls.framework_run_dict['script_case_dict'].keys()),
                         "pass": 0, "fail": 0, "skip": 0, "except": 0, "pass_rate": "0%"}
        # script_case_dict存放待测试的脚本信息
        print(cls.framework_run_dict)
        for script_name in cls.framework_run_dict['script_case_dict'].keys():
            # 当前测试脚本对应的测试用例info
            script_info_list = cls.framework_run_dict['script_case_dict'].get(script_name)

            if not isinstance(script_info_list, list) or (isinstance(script_info_list, list) and
                                                          len(script_info_list) == 0):
                # 不是list类型，或者是list类型但是是空列表时，该脚本信息不存在，跳过
                script_info_list = [{constants.CASE_SCRIPT_CASE_TITLE: 'case is not existed'}]
                cls.__handle_script_test_result_info(script_name, constants.SCRIPT_CASE_NON_EXIST, script_info_list,
                                                     cls.framework_run_dict['test_result_excel_file_path'],
                                                     'Script case not exists')
                continue

            # 测试脚本路径
            if "nic100" in cls.scripts_directory:
                if 'system_test_smoke' in script_name:
                    cur_scripts_directory = cls.scripts_directory
                elif "nic100" not in script_name and "nic800" not in script_name:
                    cur_scripts_directory = cls.scripts_directory.replace("nic100", "nic")
                else:
                    cur_scripts_directory = cls.scripts_directory
            else:
                if "nic100" in script_name:
                    cur_scripts_directory = cls.scripts_directory.replace("nic", "nic100")
                else:
                    cur_scripts_directory = cls.scripts_directory
            if "system_test_smoke" in script_name:
                # 测试脚本
                script_name_new = script_name.split('_Testles_')[0]
                if '.py' not in script_name_new:
                    script_path_real = f"{script_name.split('_Testles_')[0]}.py"
                else:
                    script_path_real = f"{script_name.split('_Testles_')[0]}"
                # case_title = f"Testles_{script_path.split('_Testles_')[1].replace('.py', '')}"
                script_path = CommandOperation.format_linux_path_sep(
                    os.path.join(os.path.abspath(os.path.dirname(cur_scripts_directory)), script_path_real))
            else:
                script_path = CommandOperation.format_linux_path_sep(os.path.join(cur_scripts_directory, script_name))

            # 脚本不存在
            if not os.path.exists(script_path):
                cls.__handle_script_test_result_info(script_path, constants.SCRIPT_NON_EXIST, script_info_list,
                                                     cls.framework_run_dict['test_result_excel_file_path'],
                                                     'Script not exists')
                continue

            # 打印测试脚本路径信息
            log.info(constants.SCRIPT_START_INFO % script_path)
            # 获取测试前的时间戳，开始时间
            script_start_timestamp, script_start_time = CommandOperation.get_time(time_format='%Y-%m-%d %H:%M:%S')

            cls.before_exec_script()
            #  跳出循环，停止测试
            if cls.framework_run_dict['test_stop']:
                flag_check = False
                for script_name_inner in cls.framework_run_dict['script_case_dict'].keys():
                    if script_name_inner == script_name:
                        flag_check = True
                    elif flag_check:
                        cls.__write_to_rebuild_csv(fail_rebuild_csv_path, script_name)
                break

            # 获取执行脚本的命令（若测试脚本路径存在关键字system_test_smoke, 则进入测试测试框架处理流程）
            if "system_test_smoke" in script_path:
                print(f"====={script_name}+++")
                script_path_real = f"{script_name.split('_Testles_')[0]}.py"
                case_title = f"{script_name.split('_Testles_')[1].replace('.py', '')}"
                # 执行测试框架的命令str
                nic100_root_path = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
                Testles_entry_script = os.path.join(nic100_root_path,
                                                     "Testles_autotest", "framework", "run_all_test_ib.py")
                script_execute_cmd = f"python3 {Testles_entry_script}"
                # 填充测试测试框架运行参数json文件
                cls.frame_model.fill_Testles_test_parameters(script_path_real)
                # 测试用例表格中，script对应的全部用例填充Y(为防止上一次运行的残留，首先全部改成N, 再填充需要的Y)
                cls.frame_model.fill_Testles_test_case(script_name, case_title, run_type="N")
                all_case_title, all_case_id = cls.frame_model.fill_Testles_test_case(script_name, case_title)
                if isinstance(all_case_title, str) and "case not exist" in all_case_title:
                    cls.__handle_script_test_result_info(script_path_real, constants.SCRIPT_CASE_NON_EXIST, script_info_list,
                                                         cls.framework_run_dict['test_result_excel_file_path'],
                                                         'Case not exists')
                    continue
                for i, executing_case_title in enumerate(all_case_title):
                    if isinstance(executing_case_title, str) and "case not exist" in executing_case_title:
                        cls.__handle_script_test_result_info(script_path_real, constants.SCRIPT_CASE_NON_EXIST,
                                                             script_info_list,
                                                             cls.framework_run_dict['test_result_excel_file_path'],
                                                             'Case not exists')
                        continue
                    print("\n")
                    log.info('Start to execute case: {}, scripts:{}'.format(executing_case_title, script_path_real))
                    # 仅当前运行的用例填充到运行文件中，用于控制测试脚本每次仅执行一个用例
                    cls.frame_model.fill_Testles_executing_case_config(executing_case_title)
                    # 脚本开始执行
                    cmd_code, cmd_output = CommandOperation.execute_script_command(script_cmd=script_execute_cmd)
                    # 打印脚本执行返回码
                    log.info('Script execute return code: {}'.format(cmd_code))

                    # 禅道触发用例时，不能修改caseid，否则会导致caseid与禅道不一致，无法回传结果到禅道
                    # cls.framework_run_dict['script_case_dict'][script_name][0]["caseId"] = all_case_id[i]
                    # cls.framework_run_dict['script_case_dict'][script_name][0]["caseTitle"] = executing_case_title
                    cls.framework_run_dict['script_rtn_code'] = cmd_code
                    cls.framework_run_dict['script_rtn_output'] = cmd_output
                    cls.framework_run_dict['script_name'] = script_name
                    cls.framework_run_dict['script_info_list'] = script_info_list

                    if cmd_code == constants.RETURN_CODE_SUCCESS:
                        stats_results["pass"] += 1
                    elif cmd_code == constants.RETURN_CODE_FAIL:
                        stats_results["fail"] += 1
                    elif cmd_code == constants.RETURN_CODE_SKIP:
                        stats_results["skip"] += 1
                    else:
                        stats_results["except"] += 1
                    stats_results["pass_rate"] = "{:.2f}%".format(stats_results["pass"] * 100 / stats_results["total"])
                    cls.version_compatibility_update_test_result(rounds, stats_results)

                    # 将测试不通过的脚本写入fail_rebuild.csv,可用于后续补测
                    if cls.framework_run_dict['script_rtn_code'] != constants.RETURN_CODE_SUCCESS:
                        cls.__write_to_rebuild_csv(fail_rebuild_csv_path, script_name)

                    if cls.random_exec:
                        # 写入random_rebuild.csv,可用于后续按random后顺序重测
                        cls.__write_to_rebuild_csv(random_rebuild_csv_path, script_name)

                    # 解析脚本输出
                    cls.__parse_cmd_output(script_name ,cmd_code, cmd_output)

                    cls.after_exec_script()

                    # 框架warning信息获取
                    message = cls.__get_warn_message()
                    if message:
                        msg = f"{script_name}:<WARN>" + message
                        cls.log_waring.append(msg)

                    if not cls.framework_run_dict['test_stop']:
                        cls.framework_run_dict['test_stop'] = cls.__force_to_exit_test()

                    #  跳出循环，停止测试
                    if cls.framework_run_dict['test_stop']:
                        break

                    cls.framework_run_dict['script_run_num'] += 1

                # 还原测试测试用例csv，script对应的全部用例填充N
                cls.frame_model.fill_Testles_test_case(script_name, case_title, run_type="N")

            else:
                script_execute_cmd = commands.get_run_script_cmd(
                    script_path,
                    cls.framework_run_dict['test_script_log_directory']
                )
                # 脚本开始执行
                cmd_code, cmd_output = CommandOperation.execute_script_command(script_cmd=script_execute_cmd)
                cls.framework_run_dict['script_rtn_code'] = cmd_code
                cls.framework_run_dict['script_rtn_output'] = cmd_output
                cls.framework_run_dict['script_name'] = script_name
                cls.framework_run_dict['script_info_list'] = script_info_list
                # 打印脚本执行返回码
                log.info('Script execute return code: {}'.format(cmd_code))

                if cmd_code == constants.RETURN_CODE_SUCCESS:
                    stats_results["pass"] += 1
                elif cmd_code == constants.RETURN_CODE_FAIL:
                    stats_results["fail"] += 1
                elif cmd_code == constants.RETURN_CODE_SKIP:
                    stats_results["skip"] += 1
                else:
                    stats_results["except"] += 1
                stats_results["pass_rate"] = "{:.2f}%".format(stats_results["pass"] * 100 / stats_results["total"])
                cls.version_compatibility_update_test_result(rounds, stats_results)

                # 将测试不通过的脚本写入fail_rebuild.csv,可用于后续补测
                if cls.framework_run_dict['script_rtn_code'] != constants.RETURN_CODE_SUCCESS:
                    cls.__write_to_rebuild_csv(fail_rebuild_csv_path, script_name)

                if cls.random_exec:
                    # 写入random_rebuild.csv,可用于后续按random后顺序重测
                    cls.__write_to_rebuild_csv(random_rebuild_csv_path, script_name)

                # 解析脚本输出，
                cls.__parse_cmd_output(script_name, cmd_code, cmd_output)

                cls.after_exec_script()

                # 框架warning信息获取
                message = cls.__get_warn_message()
                if message:
                    msg = f"{script_name}:<WARN>" + message
                    cls.log_waring.append(msg)

                if not cls.framework_run_dict['test_stop']:
                    cls.framework_run_dict['test_stop'] = cls.__force_to_exit_test()

                #  跳出循环，停止测试
                if cls.framework_run_dict['test_stop']:
                    flag_check = False
                    for script_name_inner in cls.framework_run_dict['script_case_dict'].keys():
                        if script_name_inner == script_name:
                            flag_check = True
                        elif flag_check:
                            cls.__write_to_rebuild_csv(fail_rebuild_csv_path, script_name_inner)
                    break

                cls.framework_run_dict['script_run_num'] += 1

        # 每轮测试后执行操作
        cls.frame_model.after_test_round()

    @classmethod
    def __create_rebuild_csv(cls, rebuild_csv_path):
        """
        author: junfeng.he
        date  : 2023.09.15
        description: 获取非pass脚本列表，用于补测
        :return: None
        """
        content = 'caseId,caseTitle,caseVersion,caseLevel,caseType,branchId,moduleId,moduleName,caseStep,' \
                  'scriptLocation,runId,needRun\n'
        num = 3
        for k in range(num):
            i = num - k - 1
            if i == 0:
                subfix = ""
                subfix_last = ".last1"
            else:
                subfix = ".last{}".format(i)
                subfix_last = ".last{}".format(i+1)
            cmd = "/bin/mv {} {}".format(rebuild_csv_path + "{}".format(subfix),
                                         rebuild_csv_path + "{}".format(subfix_last))
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, local_execute_flag=True)
            log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
        FileOperation.write_local_file(rebuild_csv_path, content, "w")

    @classmethod
    def __write_to_rebuild_csv(cls, rebuild_csv_path, script_path):
        """
        author: junfeng.he
        date  : 2023.09.15
        description: 获取非pass脚本列表，用于补测
        :return: None
        """
        content = "{},-,1,A1,system-test,0,0,-,-,{},,Y\n".format(int(time.time()), script_path)
        FileOperation.write_local_file(rebuild_csv_path, content, "a")

    @classmethod
    def get_bug_result_excel_data(cls) -> dict:
        """
        author: luyafei
        date  : 2020.05.23
        description: 获取bug、result表中的数据信息
        :return: bug、result表中所有行的数据信息

        @changelog      2021-02-27 09:50:42  haibin.xu
                        1. 作为类方法并入RunAllTestPs3类
        """
        bug_results_dict = {}
        bug_dict_list = utils_excel.get_excel_data_by_row(cls.framework_run_dict['test_bug_excel_file_path'])
        result_dict_list = utils_excel.get_excel_data_by_row(cls.framework_run_dict['test_result_excel_file_path'])
        bug_results_dict.setdefault(constants.BUG_EXCEL_KEY, bug_dict_list)
        bug_results_dict.setdefault(constants.RESULT_EXCEL_KEY, result_dict_list)
        bug_results_dict.setdefault(constants.RESULT_JOB_KEY, cls.jenkins_job_info)
        return bug_results_dict

    @classmethod
    def __add_summary_info(cls, test_info_dict: dict) -> dict:
        """
        author:      haibin.xu
        date:        2021-03-01 19:55:59
        description: 测试问题、结果信息字典
        :return:     返回更新后的统计信息数据
        """
        summary_info_dict = {}
        summary_info_dict.setdefault(constants.REPORT_COL_SCRIPT_PASS, cls.pass_num)
        summary_info_dict.setdefault(constants.REPORT_COL_SCRIPT_FAIL, cls.fail_num)
        summary_info_dict.setdefault(constants.REPORT_COL_SCRIPT_SKIP, cls.skip_num)
        summary_info_dict.setdefault(constants.REPORT_COL_SCRIPT_NOT_EXIST, cls.not_exist_num)
        summary_info_dict.setdefault(constants.REPORT_COL_SCRIPT_EXCEPTION, cls.except_num)
        summary_info_dict.setdefault(constants.REPORT_COL_SCRIPT_TIMEOUT, cls.timeout_num)
        test_info_dict.setdefault(constants.SCRIPT_SUMMARY_TAG, summary_info_dict)

        test_info_dict.setdefault(constants.IOC_VERSION, cls.framework_run_dict['test_platform_info'])
        test_info_dict.setdefault(constants.LOG_WARN, json.dumps(cls.log_waring))
        return test_info_dict

    @classmethod
    def init_parameters(cls):
        """
        author:      haibin.xu
        date:        2021-02-26 16:46:24
        description: 初始化类变量
        :return:     None
        """
        log.info(constants.LOG_FUNCION_SCRIPTS.format(f'Start init run all test {cls.test_project} parameters ...'))

        # 获取用例、脚本关联关系的对象
        cls.__get_case_script_map_obj()
        cls.__get_env_configure_data()
        cls.__get_bug_obj()
        cls.__get_framework_parameters()
        cls.frame_model_config = config.model_config[cls.test_project]
        cls.__get_collect_log_obj()
        cls.__get_project_frame_model()
        cls.__get_project_parameters()

        log.info(constants.LOG_FUNCION_SCRIPTS.format(f'Finish init run all test {cls.test_project} parameters.'))

    @classmethod
    def get_os_switch_test_list(cls) -> list:
        """
        author: junfeng.he
        date  : 2023.10.13
        description: 测试框架根据switch_lable，获取os测试编号列表
        :return: os_switch_test_list
        @changelog
        """
        if cls.framework_run_dict['config_dict']['switch_label']:
            os_switch_test_list = cls.framework_run_dict['config_dict']['switch_label'].split(',')
        else:
            os_switch_test_list = ['default']
        log.info("os_switch> os_switch_test_list: {}".format(os_switch_test_list))
        if len(os_switch_test_list) > 1:
            server_ip = cls.framework_run_dict['ip_dict']['server_ip']
            cmd = "efibootmgr"
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            # log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
            for os_version in os_switch_test_list:
                if os_version == 'default':
                    bios_infos = re.findall(r'BootOrder: (.*)', cmd_output)
                    if bios_infos:
                        os_version = bios_infos[0].split(',')[0]
                        if os_version not in os_switch_test_list:
                            bios_infos = re.findall(r'(Boot{}.*)'.format(os_version), cmd_output)
                            log.info("default -> {}".format(bios_infos))
                        else:
                            flag = False
                            for index, os_version_temp in enumerate(os_switch_test_list):
                                if os_version == os_version_temp and index < len(bios_infos[0].split(',')):
                                    os_version = bios_infos[0].split(',')[index]
                                    bios_infos = re.findall(r'(Boot{}.*)'.format(os_version), cmd_output)
                                    log.info("default -> {}".format(bios_infos))
                                    flag = True
                                    break
                            if not flag:
                                log.info("default -> unknow")
                else:
                    bios_infos = re.findall(r'(Boot{}.*)'.format(os_version), cmd_output)
                    log.info("{} -> {}".format(os_version, bios_infos))

        return os_switch_test_list

    @classmethod
    def os_switch(cls, os_version) -> int:
        """
        author: junfeng.he
        date  : 2023.10.13
        description: 测试框架根据switch_lable，通过efibootmgr工具切换系统启动项
        :return: 0：无需处理直接跑测；1：重启成功并恢复到可测试状态，-1：重启后系统未恢复到可测试初始状态
        @changelog
        """
        from scripts.script_libs.host_operation import HostOperation
        log.info("os_switch> os_version:{}".format(os_version))
        if os_version == 'default':
            log.info("os_switch> default,无需判断直接跑测")
            return 0
        nicg = CommonOperation.get_nic_generation()
        server_ip = cls.framework_run_dict['ip_dict'][constants.TEST_CONFIG_SERVER_IP]
        cmd = "efibootmgr"
        cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
        bios_infos = re.findall(r'BootOrder: (.*)', cmd_output)
        if bios_infos:
            bios_info_list = bios_infos[0].split(',')
            if os_version not in bios_info_list:
                log.error(f"os_switch> 设定的index:{os_version}不在列表内，不可配置！！")
                return -1
            if os_version == bios_info_list[0]:
                log.info("os_switch> 当前版本已是设定os版本index:{}".format(os_version))
                return 0
            new_bios_info_list = [os_version]
            for info in bios_info_list:
                if info != os_version:
                    new_bios_info_list.append(info)
            new_bios_info = ','.join(new_bios_info_list)
            log.info('os_switch> new_bios_info:{}'.format(new_bios_info))
            cmd = "efibootmgr -o {}".format(new_bios_info)
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
            if new_bios_info in cmd_output:
                time.sleep(3)
                reboot_result = HostOperation.host_reboot(ssh_ip=server_ip, ssh_port=str(cls.test_port))
                if reboot_result != RtnStatusEnum.SUCCESS.value:
                    log.info('os_switch> reboot重启主机失败,再尝试一次bmc重启')
                    server_nic_ip = cls.framework_run_dict['ip_dict'][constants.TEST_CONFIG_SERVER_BMC_IP]
                    server_bmc_name = cls.framework_run_dict['ip_dict'][constants.TEST_CONFIG_SUNAME]
                    server_bmc_password = cls.framework_run_dict['ip_dict'][constants.TEST_CONFIG_SUPASSWD]
                    reboot_result = HostOperation.host_bmc_reboot(
                        ssh_ip=server_ip, ssh_port=str(cls.test_port), bmc_ip=server_nic_ip, uname=server_bmc_name,
                        passwd=server_bmc_password, force_check=False)
                if reboot_result == RtnStatusEnum.SUCCESS.value:
                    log.info('os_switch> 重启主机成功,需要重新加载驱动')
                    log.info('os_switch> ps3server需删除/root/.ssh/known_hosts')
                    cmd = "ssh-keygen -R {}".format(server_ip)
                    cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=cmd, local_execute_flag=True)
                    log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
                    cmd = "ssh-keygen -R [{}]:3322".format(server_ip)
                    cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=cmd, local_execute_flag=True)
                    log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
                    log.info('os_switch> 使用subprocess执行到远端命令促使自动添加know hosts')
                    iretry = 40
                    while iretry:
                        if iretry % 2:
                            ssh_port = 22
                        else:
                            ssh_port = 3322
                        cmd = "ssh -p {} root@{} 'uname -a'".format(ssh_port, server_ip)
                        cmd_rtn, cmd_output, cmd_stderr = CommandOperation.\
                            execute_command_based_paramiko_with_rtncode(cmd=cmd, local_execute_flag=True)
                        log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
                        if cmd_rtn == 0:
                            break
                        time.sleep(5)
                        iretry -= 1
                    cls.__init_test_port()
                    log.info('os_switch> 重新加载驱动')
                    if cls.framework_run_dict['config_dict'][constants.ENV_TEST_OBJECT] in \
                            [constants.ENV_RUN_MODE_WITH_SRC, constants.ENV_RUN_MODE_WITH_RPM,
                             constants.ENV_RUN_MODE_WITH_SRPM, constants.ENV_RUN_MODE_WITH_KMOD_SRPM]:
                        cmd = f"modprobe {nicg}"
                    else:
                        cmd = f"insmod /root/{nicg}.ko"
                    cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
                    if cmd_rtn != 0:
                        log.warning("os_switch> 加载驱动Failed！！！")
                        log.warning("os_switch> 尝试卸载驱动后insmod重新加载")
                        cmd = f"rmmod {nicg}"
                        cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
                        cmd = f"insmod /root/{nicg}.ko"
                        cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=server_ip, ssh_port=str(cls.test_port),
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                        log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
                        if cmd_rtn != 0:
                            log.error(f"os_switch> insmod {nicg}.ko Failed！！！")
                            return -1
                    # 将环境重新配置刷新
                    cls.frame_model.brefore_test()
                    return 1
        log.info("os_switch> switch OS Failed！！！")
        return -1

    @classmethod
    def version_compatibility_env_prepare(cls, index) -> None:
        """
        author: junfeng.he
        date  : 2024.06.12
        description: 测试框架根据index读取版本兼容性测试组合准备环境
        index: 测试组合索引
        @changelog
        """
        if index == 0:
            # 首次环境准备已经在prepare_before_test中完成，此次无需执行
            return
        if not cls.version_compatibility_test:
            return
        log.info("vc_test> version_compatibility_env_prepare index:{}".format(index))
        # 根据index读取版本兼容性测试组合csv中的组合包路径
        pkg_info_list = FileOperation.read_csv_file(cls.job_directory_path + "/compatible_versions_test.csv")
        parameter = cls.framework_run_dict['config_dict'][constants.ENV_PACKAGE_PATH].split("*")
        parameter_str = ""
        for iindex, para in enumerate(parameter):
            if iindex > 0:
                parameter_str += "*" + para
        log.info(f"pkg_info_list:{pkg_info_list}")
        log.info(f"parameter_str:{parameter_str}")
        cls.framework_run_dict['config_dict'][constants.ENV_PACKAGE_PATH] = pkg_info_list[index+1][0] + parameter_str
        log.info("vc_test> package_path:{}".format(cls.framework_run_dict['config_dict'][constants.ENV_PACKAGE_PATH]))
        # 升级版本信息，准备测试环境
        cls.frame_model.brefore_test()

    @classmethod
    def version_compatibility_update_test_round(cls) -> None:
        """
        author: junfeng.he
        date  : 2024.06.12
        description: 测试框架根据读取版本兼容性测试组合更新测试轮数
        @changelog
        """
        if "csv" not in cls.framework_run_dict['config_dict'][constants.ENV_PACKAGE_PATH]:
            return
        cls.version_compatibility_test = True
        # 根据index读取版本兼容性测试组合csv中的组合包路径
        pkg_info_list = FileOperation.read_csv_file(cls.job_directory_path + "/compatible_versions_test.csv")
        # log.info("vc_test> pkg_info_list:{}".format(pkg_info_list))
        if len(pkg_info_list) > 1:
            log.warning("vc_test> version_compatibility_update_test_round> from {} to {}".format(
                cls.test_rounds, len(pkg_info_list) - 1))
            cls.test_rounds = len(pkg_info_list) - 1

    @classmethod
    def version_compatibility_update_test_result(cls, index, stats_dict) -> None:
        """
        author: junfeng.he
        date  : 2024.06.12
        description: 测试框架根据读取版本兼容性测试组合更新测试轮数
        @changelog
        """
        if not cls.version_compatibility_test:
            return
        # 根据index版本兼容性测试结果
        pkg_info_list = FileOperation.read_csv_file(cls.job_directory_path + "/compatible_versions_test.csv")
        log.info("vc_test> pkg_info_list:{}".format(pkg_info_list))
        table_header = []
        table_data = []
        for data in pkg_info_list:
            if "path" in data[0]:
                table_header = data
            elif "tar.gz" in data[0]:
                table_data.append(data)
        kmap = {}
        for i, key in enumerate(table_header):
            kmap[key] = i
        for k, v in stats_dict.items():
            if index < len(table_data) and "tar.gz" in table_data[index][0]:
                table_data[index][kmap[k]] = str(v)
        FileOperation.write_csv_file(cls.job_directory_path + "/compatible_versions_test.csv", table_header, table_data)
        log.info("vc_test> table_header:\n{}".format(table_header))
        log.info("vc_test> table_data:\n{}".format(table_data))

    @classmethod
    def prepare_before_test(cls) -> None:
        """
        author: luyafei
        date  : 2020.04.21
        description: 测试前准备
        :return:

        @changelog      2021-02-27 09:38:05  haibin.xu
                        1. 作为类方法并入RunAllTest类
        """
        # 设置测试开始时间参数
        cls.__get_test_start_time_info()
        # 初始化test/esat/outputs/framework/目录下的run_all_test_ps3_[测试开始时间戳].log
        cls.__init_run_all_test_log_file()
        # 创建[job_name]_[job_id]_[测试开始时间戳]目录，如ps3_auto_test_prepare_14093_20210610175943，路径：
        # /home/test/ps3test/vms/vm204/ps3/test/esat/outputs/framework/
        cls.__init_outputs_job_directory()
        # 获取本次测试需要的测试脚本信息
        cls.__get_script_case_info()
        # @overwirte如果是长稳测试，则打乱csaelist顺序，并保存打乱结果
        cls.__get_shuffle_script_case_info()
        # 在日志服务器上初始化本次测试的日志保存路径，如：/home/framework/log/host_vm670_10.22.81.1_22/2021_06_11/16_03_12
        cls.__init_log_directory_in_log_server()
        # 初始化本次测试的bug, result的Excel文件
        cls.__init_test_bug_and_result_file()
        # 初始化测试报告日志文件，即：test/esat/outputs/framework/ps3_auto_test_prepare_5688_20210611160312/
        # report_log_20210611160312.log
        cls.__init_test_report_log_file()
        # 生成测试脚本日志文件夹, 即：test/esat/outputs/framework/ps3_auto_test_prepare_5688_20210611160312/
        # test_script_logs
        cls.__init_test_scripts_directory()
        # @overwirte如果是长稳测试，则保存打乱csaelist顺序结果至excel
        cls.__save_shuffle_script_case_to_excel()
        cls.__chmod_env_conf()

        before = cls.framework_run_dict['test_start_timestamp']
        cls.frame_model.brefore_test()

        # 如果初始test_start_timestamp变更，说明存在上个测试单的残留环境需要采集日志，这里补充warning信息打印到summary
        if  before != cls.framework_run_dict['test_start_timestamp']:
            msg = f"上个测试单最后一次日志采集异常，此测试单补收:{cls.framework_run_dict['log_server_path']}/before_test_"
            cls.log_waring.append(msg)
        cls.version_compatibility_update_test_round()

    @classmethod
    def run_test(cls) -> None:
        """
        author: luyafei
        date  : 2020.04.21
        description: 组织测试执行
        :return: 无返回值

        @changelog      2021-02-27 09:33:14  haibin.xu
                        1. 作为类方法并入RunAllTestPs3类
                        2021-06-13 09:56:50  haibin.xu
                        1. 优化函数实现, 相关方法提取
        """
        # 执行脚本测试
        for i in range(cls.test_rounds):
            cls.version_compatibility_env_prepare(i)
            if cls.framework_run_dict['test_stop']:
                break
            cls.do_script_test(i)

            # 检查是否强制测试单结束，提前回收测试结果，退出本轮
            if cls.__force_to_exit_test():
                break

        cls.before_framework_exit()

    @classmethod
    def __parse_cmd_output(cls, script_name, cmd_code, re_stdout):
        if re_stdout is not None:
            re_stdout = re_stdout.split(constants.OUTPUT_SPLIT_KEY)[-1]
            re_stdout = re_stdout.split(constants.OUTPUT_END_SPLIT_KEY)[0]

        try:
            # log.info(re_stdout)
            out_dict = eval(re_stdout)
            if cmd_code == constants.RETURN_CODE_SKIP:
                msg = f"{script_name}:" + out_dict.get('skip_message')
                cls.log_waring.append(msg)
            elif out_dict.get('skip_message'):
                msg = f"{script_name}:<WARN>" + out_dict.get('skip_message')
                cls.log_waring.append(msg)
        except Exception as e:
            log.error(str(e))


    @classmethod
    def __get_warn_message(cls) -> str:
        """
        author: junfeng.he
        date: 2026.02.12
        description: 获取要告警的信息
        """
        warn_message = {}
        # 获取output的路径
        # ../test/esat/framework/run_all_test.py
        cur_path = os.path.dirname(os.path.abspath(__file__))
        # ../test/esat/
        output_parent_path = os.path.dirname(cur_path)
        log_default_path = os.path.join(output_parent_path, constants.OUTPUTS)
        exec_command = f"cat {log_default_path}/warn_message"
        rtn_code, result = subprocess.getstatusoutput(exec_command)
        if rtn_code == RtnStatusEnum.SUCCESS.value and len(result):
            log.info(f'__get_warn_message:{result}')
            warn_message = result
            exec_command = f"echo '' > {log_default_path}/warn_message"
            rtn_code, result = subprocess.getstatusoutput(exec_command)
        return warn_message


    @classmethod
    def process_test_result(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 10:12:41
        description: 测试结果处理

        :return:     None
        """

        # 获取本次测试任务的总时长，单位为秒
        cls.__get_test_total_time()
        # 创建本次测试报告Excel文件，即test/esat/outputs/framework/ps3_auto_test_prepare_5688_20210611160312/reports/
        #                          ps3_auto_test_prepare_5688_20210611160312_report.xlsx
        cls.__make_test_report_file()

    @classmethod
    def summary_test_info(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 11:14:27
        description: 汇总本次测试相关信息

        :return:     None
        """
        # 获取bug、result表中的数据信息, 并汇总其他统计信息
        bugs_results_info_dict = cls.get_bug_result_excel_data()

        bugs_results_info_dict = cls.__add_summary_info(bugs_results_info_dict)

        # 将汇总数据进行json格式编码, 即将字典{constants.RESULT_RUN_ALL_TEST: bugs_results_info_dict}转化为字符串，供Jenkins
        # 通过json.loads()方法将json格式数据转换为字典。
        print_result = json.dumps({constants.RESULT_RUN_ALL_TEST: bugs_results_info_dict}, ensure_ascii=False)

        log.info(constants.TEST_FINISH_INFO)

        cls.get_os_switch_test_list()

        # 将test/esat/outputs/framework/run_all_test_ps3_20210610175943.log 转到ps3/test/esat/outputs/
        #     framework/ps3_auto_test_prepare_14093_20210610175943目录下
        # utils.move_run_all_test_log(cls.framework_run_dict['run_all_test_log_file'], cls.job_directory_path)
        # 此处使用不带时间戳打印，主要是为了jekins脚本auto_test.py中获取到run_all_test_ps3.py的输出
        log.info(print_result, format_flag=False)


    @classmethod
    def change_outputs_owner(cls, owner: str = "tester:tester") -> None:
        """
        author:      junfeng.he
        date:        2025-06-17 11:14:27
        description: 修改outputs文件夹权限
        :return:     None
        """
        cmd = "chown -R {} {}".format(owner, constants.ESAT_PATH_OUT_PUTS_PATH)
        cmd_rtn, cmd_output, cmd_stderr = CommandOperation. \
            execute_command_based_paramiko_with_rtncode(cmd=cmd, local_execute_flag=True)
        log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))

    @classmethod
    def post_job_info_to_zentao(cls):
        """
        提交job信息到禅道 ，并生成json文件
        :return:
        """
        test_platform_info = {}
        try:
            test_platform_info = json.loads(cls.framework_run_dict['test_platform_info'])
        except Exception as e:
            test_platform_info = {}

        cls.jenkins_job_info = utils.test_run_submit(test_platform_info, cls.framework_run_dict['test_start_timestamp'])

        if not cls.jenkins_job_info:
            cls.jenkins_job_info['job_uuid'] = cls.config_dict.get(constants.ENV_JOB_UUID)
            cls.jenkins_job_info['host_ip'] = cls.ip_dict.get(constants.ENV_HOST_IP)
            cls.jenkins_job_info['host_label'] = cls.config_dict.get(constants.ENV_HOST_LABEL)
            cls.jenkins_job_info['platform'] = cls.config_dict.get(constants.ENV_TEST_PLATFORM)
            cls.jenkins_job_info['test_obj'] = "nic100" # cls.config_dict.get(constants.ENV_TEST_OBJECT)
            cls.jenkins_job_info['start_time'] = int(cls.framework_run_dict['test_start_timestamp'])
            cls.jenkins_job_info['end_time'] = int(time.time())
            cls.jenkins_job_info['os'] = cls.config_dict.get(constants.ENV_HOST_OS)
            cls.jenkins_job_info['type'] = cls.config_dict.get(constants.ENV_TEST_OBJECT)
            cls.jenkins_job_info['kernel'] = test_platform_info.get('kernel')
            cls.jenkins_job_info['cpu'] = test_platform_info.get('cpu')
            cls.jenkins_job_info['memory'] = test_platform_info.get('memory')
            cls.jenkins_job_info['disk_num'] = test_platform_info.get('disk_num')
            cls.jenkins_job_info['ioc_version'] = test_platform_info.get('ioc_version')
            cls.jenkins_job_info['driver_version'] = test_platform_info.get('driver_build_branch')
            cls.jenkins_job_info['cli_version'] = test_platform_info.get('cli_version')
            cls.jenkins_job_info['cpld_version'] = test_platform_info.get('cpld_version')
            cls.jenkins_job_info['com_mode'] = test_platform_info.get('com_mode')

    @classmethod
    def run(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-02-27 09:12:46
        description: 脚本执行入口

        :return:     None
        """
        log.info(constants.LOG_SCRIPTS.format('Start run run_all_test ...'))

        # 初始化参数
        cls.init_parameters()

        cls.prepare_before_test()

        os_switch_test_list = cls.get_os_switch_test_list()
        for os_version in os_switch_test_list:
            if cls.os_switch(os_version) < 0:
                continue
            if os_version != "default":
                cls.frame_model.brefore_test()
            cls.run_test()
            # 检查是否强制测试单结束，提前回收测试结果，退出本轮
            if cls.__force_to_exit_test():
                break

        cls.frame_model.after_test()

        cls.process_test_result()

        cls.post_job_info_to_zentao()

        cls.summary_test_info()

        cls.change_outputs_owner(owner="tester:tester")

        log.info(constants.LOG_SCRIPTS.format('Finish run run_all_test ...'))

    @classmethod
    # Linux防火墙开放预留端口, Windows未调研到有命令支持
    def __add_firewall_list(cls, reserved_port_list: list = script_constants.RESERVED_PORT) -> None:
        for port in reserved_port_list:
            command_add_tcp_port = 'firewall-cmd --permanent --add-port={}/tcp'.format(str(port))
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command_add_tcp_port, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command_add_tcp_port, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
            command_add_udp_port = 'firewall-cmd --permanent --add-port={}/udp'.format(str(port))
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command_add_udp_port, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command_add_udp_port, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)

        command_reload = 'firewall-cmd --reload'
        CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=command_reload, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=command_reload, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)

        return

    @classmethod
    # 检查预留端口是否可用
    def __check_port_available(cls, reserved_port_list: list = script_constants.RESERVED_PORT) -> None:
        for port in reserved_port_list:
            cls.__kill_processid_port(str(port), CmdExecuteAdressEnum.CLIENT.value)
            cls.__kill_processid_port(str(port), CmdExecuteAdressEnum.SERVER.value)
            command_check_tcp = 'firewall-cmd --query-port={}/tcp'.format(str(port))
            command_check_udp = 'firewall-cmd --query-port={}/udp'.format(str(port))
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command_check_tcp, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command_check_tcp, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command_check_udp, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command_check_udp, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)

    @classmethod
    # 如果有占用，调用杀死端口进程的方法
    def __kill_processid_port(cls, port: str, cmd_execute_address) -> None:
        """
        author: wei.yuan
        date:2022年8月3日14:17:35
        description: 使用命令将对应进程所使用的端口号杀死
        """
        if 'windows' not in script_constants.HOST_OS:
            port_to_processid_cmd = f"netstat -nlp|grep :{port}| " \
                                    f"awk '{{print $7}}'|awk -F '/' '{{print $1}}'"
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd_execute_address=cmd_execute_address, cmd=port_to_processid_cmd)
            clean_port_process_list = [result.strip() for result in cmd_output.split("\n") if
                                       result.strip() != '']
            if len(clean_port_process_list) != 0:
                for clean_port_process in clean_port_process_list:
                    clean_process_cmd = f" kill 9 {clean_port_process}"
                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd_execute_address=cmd_execute_address, cmd=clean_process_cmd)
            else:
                log.warning_caller(f"{port} 没有对应的进程")
        else:
            port_to_processid_cmd = f"taskkill /T /F /PID {port}"
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd_execute_address=cmd_execute_address, ssh_username="Administrator",
                cmd=port_to_processid_cmd)


def main():
    RunAllTest.run()


if __name__ == '__main__':
    main()
