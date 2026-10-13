#!/usr/bin/env python3
# -*- encoding=utf8 -*-

"""
author: luyafei
date  : 20200511
description: 一些通用信息的操作方法
             1:生成job信息列表
             2:获取执行python脚本命令结果中最后一行的信息
             3:执行python脚本命令
"""
import subprocess
import os
import time
import copy
import json
import requests

from libs import constants
from libs import commands
from biz.excel import bug_result_excel_handle
from libs.classes.method_time import MethodTime
from libs.classes.result import Result
from libs.classes.bug import Bug
from libs.classes.report_summary import ReportSummary
from biz.classes.config_file_manager import ConfigManager
from scripts.script_libs import log
from scripts.script_libs import constants as libs_constants


def get_conf() -> tuple:
    """
    author: luyafei、panpan.du
    date  : 2020.04.29
    description: 获取测试需要的环境配置信息及日志服务器、测试主机、PS3测试服务器的ip
    :return ip_dict:环境配置信息字典，日志服务器、测试主机、PS3测试服务器的ip字典信息
    """
    env_configure = ConfigManager.get_config_manager_object()
    config_dict = env_configure.env_dict_get()
    ip_dict = env_configure.ips_dict_get()
    return config_dict, ip_dict


def get_time(cur_time: tuple) -> str:
    """
    author: luyafei
    date  : 2020.04.21
    description: 将时间戳转换为指定格式的时间
    :param cur_time: 当前时间  localtime格式
    :return: 返回指定格式的时间
    """
    # 格式为20200423151820(2020年4月23日)
    return time.strftime("%Y%m%d%H%M%S", cur_time)


def get_time_dd_hh(cur_time: tuple) -> str:
    """
    author: luyafei
    date  : 2020.09.30
    description:将时间戳转换为指定格式
    :param cur_time: 要转换的时间  localtime格式
    :return: 返回指定格式的时间
    """
    # 时间格式为 2020-09-30 18:57:00
    return time.strftime("%Y-%m-%d %H:%M:%S", cur_time)


def make_job_info_list(task_start_time: str) -> list:
    """
    author: luyafei
    date  : 2020.04.21
    description: 生成测试任务信息列表（任务ID，任务名称和测试任务开始执行时间）
    :param task_start_time: 测试任务开始执行时间格式为20200423151820(2020年4月23日 15:18:20)
    :return: job_info_list
    """
    # 执行测试job信息
    config_dict, ip_dict = get_conf()
    job_id = config_dict[constants.ENV_JOB_ID]
    job_name = config_dict[constants.ENV_JOB_NAME]
    if job_id is None and job_name is None:
        log.error("job id is None, job name is None")
        exit(1)
    # 测试任务信息列表
    job_info_list = [job_name, str(job_id), str(task_start_time)]
    return job_info_list


def make_path_dir(path_str: str) -> None:
    """
    author: luyafei
    date  : 2020.12.18
    description: 如果路径目录不存在则生成相应路径
    :param path_str: 路径字符串
    :return: None
    """
    if not os.path.exists(path_str):
        try:
            os.makedirs(path_str)
        except Exception as result:
            log.error("make dir failed. path: %s. result: %s" % (path_str, result))


def handle_script_return_code(framework_run_dict: dict) -> None:
    """
    author: panpan.du
    date  : 2020.10.22
    description: bug字典转化为一个Bug对象
    :param post_bug_object: Bug对象
    :param result_object: Result对象
    :param collect_log:收集日志信息对象
    :param return_code:脚本返回码
    :param output:脚本输出结果
    :param case_dict_list:用例字典列表
    :param g_log_file:日志路径
    :param g_test_script_log_dir:脚本测试路径
    :param bug_excel_file:bug的表格路径
    :param result_excel_file:测试结果表格路径
    :param script_name:脚本名称
    :param failed_times:脚本失败次数
    :return:
    """
    ioc_core_flag = False
    ioc_crash_flag = False
    host_crash_flag = False
    collect_log_flag = True
    bug_dict_list = []
    log_path = ''

    return_code = framework_run_dict['script_rtn_code']
    output = framework_run_dict['script_rtn_output']
    post_bug_object = framework_run_dict['bug_object']
    collect_log = framework_run_dict['collect_log']
    result_object = framework_run_dict['result_object']
    script_name = framework_run_dict['script_name']
    case_dict_list = framework_run_dict['script_info_list']
    g_test_script_log_dir = framework_run_dict['test_script_log_directory']
    g_log_file = framework_run_dict['run_all_test_log_file']
    bug_excel_file = framework_run_dict['test_bug_excel_file_path']
    result_excel_file = framework_run_dict['test_result_excel_file_path']
    # 根据返回码提交测试结果
    if return_code == constants.RETURN_CODE_TIMEOUT:
        # 测试结果超时
        test_result_info = "Script test timeout. Result: failed."
        # 增加脚本运行超时bug
        post_bug_object.set_title(constants.DEFAULT_TIMEOUT_BUG_TITLE)
        post_bug_object.set_type_name(constants.DEFAULT_TIMEOUT_BUG_TYPE)
        post_bug_object.set_steps(constants.DEFAULT_TIMEOUT_BUG_STEPS)
        # 收集脚本日志
        log_path, ioc_core_flag, ioc_crash_flag, host_crash_flag, collect_log_flag = collect_logs(
            collect_log, g_log_file, g_test_script_log_dir, script_name)
        post_bug_object.set_log_path(log_path)
        bug_dict = bug_result_excel_handle.append_bug_to_excel(post_bug_object, case_dict_list, bug_excel_file)
        bug_dict_list.append(bug_dict)
        result_object.set_script_result(constants.REPORT_COL_SCRIPT_FAIL)

    elif return_code == constants.RETURN_CODE_SUCCESS:
        # 测试通过
        test_result_info = "Script: %s test finish. Result: pass." % script_name
        result_object.set_script_result(constants.REPORT_COL_SCRIPT_PASS)
    elif constants.RETURN_CODE_EXCEPTION == return_code:
        # 脚本发生异常
        test_result_info = "Script: %s test finish. Result: script exception." % script_name
        result_object.set_script_result(constants.REPORT_COL_SCRIPT_EXCEPTION)
    elif return_code == constants.RETURN_CODE_FAIL:
        # 测试结果失败
        test_result_info = "Script: %s test finish. Result: failed." % script_name
        # 解析测试结果值
        post_bug_object, test_bug_object, core_crash_bug_object = parse_bug_info(output, post_bug_object)
        if post_bug_object.set_title != "脚本执行错误":
            # 收集脚本日志
            log_path, ioc_core_flag, ioc_crash_flag, host_crash_flag, collect_log_flag = collect_logs(
                collect_log, g_log_file, g_test_script_log_dir, script_name)
        else:
            log_path = "NA"

        # 脚本整理环境bug
        if post_bug_object[constants.BUG_TITLE] != "":
            post_bug_object.set_log_path(log_path)
            # frequency = str(failed_times) + "/" + str(constants.EXEC_SCRIPTS_MAX_TIMES)
            frequency = "1"
            steps = post_bug_object.steps
            steps = "发生频率：%s\n" % frequency + steps
            post_bug_object.set_steps(steps)
            bug_dict = bug_result_excel_handle.append_bug_to_excel(post_bug_object, case_dict_list, bug_excel_file)
            bug_dict_list.append(bug_dict)

        # 脚本测试bug
        if test_bug_object is not None:
            test_bug_object.set_log_path(log_path)
            # frequency = str(failed_times) + "/" + str(constants.EXEC_SCRIPTS_MAX_TIMES)
            frequency = "1"
            steps = test_bug_object.steps
            steps = "发生频率：%s\n" % frequency + steps
            test_bug_object.set_steps(steps)
            bug_dict = bug_result_excel_handle.append_bug_to_excel(test_bug_object, case_dict_list, bug_excel_file)
            bug_dict_list.append(bug_dict)

        # 脚本运行出现core、crash的bug
        if core_crash_bug_object is not None:
            core_crash_bug_object.set_log_path(log_path)
            # frequency = str(failed_times) + "/" + str(constants.EXEC_SCRIPTS_MAX_TIMES)
            frequency = "1"
            steps = post_bug_object.steps
            steps = "发生频率：%s\n" % frequency + steps
            core_crash_bug_object.set_steps(steps)
            bug_dict = bug_result_excel_handle.append_bug_to_excel(core_crash_bug_object, case_dict_list,
                                                                   bug_excel_file)
            bug_dict_list.append(bug_dict)

        # 填写测试结果
        result_object.set_script_result(constants.REPORT_COL_SCRIPT_FAIL)

    # 测试物理环境不满足
    elif return_code == constants.RETURN_CODE_SKIP:
        test_result_info = "Script: %s test finish. Physical environment is disable. Result: skip." % script_name
        result_object.set_script_result(constants.REPORT_COL_SCRIPT_SKIP)

    # 脚本返回码不在预期结果中，暂时跳过
    else:
        test_result_info = "Script: %s test unknown error. Result: skip." % script_name
        result_object.set_script_result(constants.REPORT_COL_SCRIPT_SKIP)

    # 解析测试结果并将测试结果写入表格中
    result_object = parse_result_info(output, result_object)
    result_dict = bug_result_excel_handle.append_result_to_excel(result_object, case_dict_list, result_excel_file)
    # 提交res信息到禅道
    submit_to_zentao(result_dict, {})
    info_msg = "\n--------------------%s--------------------" % test_result_info
    log.info(info_msg)
    for item in bug_dict_list:
        submit_to_zentao({}, item)

    framework_run_dict['ioc_core_flag'] = ioc_core_flag
    framework_run_dict['ioc_crash_flag'] = ioc_crash_flag
    framework_run_dict['host_crash_flag'] = host_crash_flag
    framework_run_dict['collect_log_flag'] = collect_log_flag
    framework_run_dict['log_path'] = log_path


def get_parent_path() -> str:
    """
    author: luyafei
    date  : 2020.12.19
    description: 获取当前文件所在文件夹的父路径
    :return: 父路径的字符串
    """
    # 获取output的路径
    # ../test/esat/framework/libs/utils.py
    cur_path = os.path.dirname(os.path.abspath(__file__))
    # ../test/esat/framework/libs
    cur_path = os.path.dirname(cur_path)
    # ../test/esat/framework
    output_parent_path = os.path.dirname(cur_path)
    return output_parent_path


def make_job_outputs_dir(job_info_list: list) -> tuple:
    """
    author:luyafei
    date  : 2020.04.28
    description: 生成正在执行的测试job在PS3测试服务器上输出信息目录
    :param job_info_list:
    :return: 输出信息目录和执行测试job信息组成的字符串
    """
    job_info_str = constants.FILE_NAME_CONNECTOR.join(job_info_list)
    # 获取outputs的路径
    cur_parent_path = get_parent_path()
    job_output_dir = os.path.join(cur_parent_path, constants.OUTPUTS, constants.OUTPUT_FRAMEWORK, job_info_str)
    make_path_dir(job_output_dir)

    return job_output_dir, job_info_str


def make_web_outputs_dir(web_info_list: list) -> str:
    """
    author:yinfc
    date  : 2022.06.08
    description: 生成正在执行的测试job在PS3测试服务器上输出web截图目录
    :param web_info_list:
    :return: 输出web截图目录的字符串
    """

    config_dict, ip_dict = get_conf()
    job_id = config_dict[constants.ENV_JOB_ID]
    job_name = config_dict[constants.ENV_JOB_NAME]
    job_info_list = [job_name, str(job_id), constants.WEB_SCREENSHOT_PATH]

    web_info_str = constants.FILE_NAME_CONNECTOR.join(job_info_list)
    # 获取outputs的路径
    cur_parent_path = get_parent_path()
    web_output_dir = os.path.join(cur_parent_path, constants.OUTPUTS, constants.OUTPUT_FRAMEWORK, web_info_str)
    make_path_dir(web_output_dir)

    return web_output_dir


def make_result_object(start_time: str, time_duration: str, mm_delta: int = 0,
                       test_platform: str = '', test_platform_info: str = '') -> Result:
    """
    author: luyafei
    date  : 2020.05.06
    description: 生成测试结果对象
    :param start_time: 测试脚本开始执行的时间
    :param time_duration: 测试脚本执行时长
    :param mm_delta: 内存差值
    :param test_platform: 测试环境
    :return: 测试结果对象

    @changelog      2021-05-06 09:15:06  haibin.xu
                    1. 优化函数实现， 添加mm_delta参数
    """
    config_dict, ip_dict = get_conf()
    result_fields = Result()
    result_fields.set_common_values(config_dict, ip_dict)
    result_fields.set_start_time(start_time)
    result_fields.set_script_duration(time_duration)
    result_fields.set_memory_delta(mm_delta)
    result_fields.set_test_platform(test_platform)
    result_fields.set_test_platform_info(test_platform_info)
    return result_fields


def make_run_all_test_log(test_start_time: str, file_name: str) -> str:
    """
    author: luyafei
    date  : 2020.04.28
    description: 初始化run all test脚本的执行日志
    :param test_start_time: 脚本开始执行的时间
    :param file_name: 日志文件名称
    :return: 返回run all test的日志名称和路径
    """
    config_dict, _ = get_conf()
    show_console_log = config_dict.get(constants.ENV_SHOW_CONSOLE_LOG, True)
    # 获取output的路径
    output_parent_path = get_parent_path()
    # ../test/esat
    output_dir = os.path.join(output_parent_path, constants.OUTPUTS, constants.OUTPUT_FRAMEWORK)
    make_path_dir(output_dir)
    log.info('output dir: {}'.format(output_dir))
    log_file_path = os.path.join(output_dir, "%s_%s.log" % (file_name, test_start_time))
    try:
        log.info('log file path: {}, show_console_log: {}'.format(log_file_path, show_console_log))
        log.init(log_file_path, show_console_log)
        log.info("create framework log success")
    except Exception as result:
        log.error("create framework log error. %s" % result)

    return log_file_path


def move_run_all_test_log(log_file_path, output_dir: str) -> None:
    """
    author: panpan.du
    date  : 2020.10.30
    description: 初始化run all test脚本的执行日志
    :param log_file_path: 日志文件
    :param output_dir: 日志应该所在文件夹
    """
    # 获取output的路径
    # ../test/esat/framework/libs/utils.py
    mv_cmd = "mv %s %s" % (log_file_path, output_dir)
    # rc, output = commands.exec_run_script_cmd(mv_cmd, True)
    rc, output = subprocess.getstatusoutput(mv_cmd)
    if rc != 0:
        log.error("Move log file failed. output: %s" % output)


def make_test_report_file(
        create_report_script_path: str,
        test_start_time: str,
        task_total_duration: str,
        g_bug_excel: str,
        g_result_excel: str,
        report_log_path: str) -> object:
    """
    author: luyafei
    date  : 2020.05.12
    description: 执行生成python脚本命令
    :param create_report_script_path: python脚本命令
    :param test_start_time: python脚本命令
    :param task_total_duration: python脚本命令
    :param g_bug_excel: python脚本命令
    :param g_result_excel: python脚本命令
    :param report_log_path: python脚本命令
    :return: 返回测试报告的文件名（包含路径）
    """
    python_cmd_result = None
    python_cmd = "python3 -u %s --start %s -t %s -p %d -f %d -k %d -n %d -b %s -r %s -l %s" % \
                 (create_report_script_path, str(test_start_time), str(task_total_duration), ReportSummary.pass_num,
                  ReportSummary.fail_num, ReportSummary.skip_num, ReportSummary.not_exist_num, g_bug_excel,
                  g_result_excel, report_log_path)
    log.info("python command: \n%s" % python_cmd)
    rc, output = subprocess.getstatusoutput(python_cmd)
    if rc != 0:
        log.error("python command do fail, result code: %d. output: %s" % (rc, output))
    else:
        if output:
            line_list = output.splitlines()
            python_cmd_result = line_list[-1]
    return python_cmd_result


def make_scripts_log(job_output_dir: str) -> str:
    """
    author: DuPanPan
    date  : 2020.04.28
    description: 初始化测试脚本的执行日志
    :param job_output_dir: 脚本开始执行的时间
    :return: 返回测试脚本的日志文件夹
    @changelog      sunql
                1、增加创建记录脚本cli执行时间日志文件夹
    """
    script_log_dir = os.path.join(job_output_dir, constants.TEST_SCRIPT_LOG_DIR)
    make_path_dir(script_log_dir)
    # overwrite 创建记录脚本cli执行时间日志文件夹
    make_path_dir(libs_constants.SCRIPT_CMD_TIME_LOG_DIR)
    return script_log_dir


def parse_output_bug_dict(re_stdout: str) -> tuple:
    """
    author: panpan.du
    date  : 2020.09.11
    description: 将一个输出转化为Bug字典
    :param re_stdout: 字典名称
    :return: 对应的bug字典、result字典
    """
    if re_stdout is not None:
        re_stdout = str(re_stdout).split(constants.OUTPUT_SPLIT_KEY)[-1]
        re_stdout = re_stdout.split(constants.OUTPUT_END_SPLIT_KEY)[0]
    # 检查bug信息
    test_bug_dict = dict()
    test_result_dict = dict()
    test_method_info = dict()
    try:
        out_dict = eval(str(re_stdout))
        test_bug_info = out_dict.get(constants.TEST_RESULT)
        test_method_info = out_dict.get(constants.METHODS)
    except Exception as e:
        test_bug_info = None
        log.error(str(e))
        log.info("open script output: %s" % re_stdout)

    # 填写bug信息
    if test_bug_info is not None and len(test_bug_info) != 0:
        test_bug_dict[constants.BUG_COL_BUG_TITLE] = str(test_bug_info.get(constants.BUG_TITLE, ""))
        test_bug_dict[constants.BUG_COL_BUG_TYPE] = str(test_bug_info.get(constants.BUG_TYPE, ""))
        test_bug_dict[constants.BUG_COL_TEST_TOOL] = str(test_bug_info.get(constants.BUG_TOOL, ""))
        test_bug_dict[constants.BUG_COL_PRECONDITION] = str(test_bug_info.get(constants.BUG_PRECONDITION, ""))

        test_precondition = "前置步骤: \n" + str(test_bug_info.get(constants.BUG_PRECONDITION))
        test_steps = "步骤：\n" + str(test_bug_info.get(constants.BUG_STEPS, ""))
        test_result = "测试结果：\n" + str(test_bug_info.get(constants.BUG_RESULT, ""))
        test_expect = "预期结果：\n" + str(test_bug_info.get(constants.BUG_EXPECT, ""))
        test_steps = ";".join([test_precondition, test_steps, test_result, test_expect])
        test_steps = test_steps.replace(";;", ";")
        test_steps = test_steps.replace(";", ";\n")
        test_bug_dict[constants.BUG_COL_STEPS] = test_steps

        # 填写结果信息
        test_result_dict[constants.RESULT_COL_PRE_DURATION] = test_method_info.get(constants.PRE_DURATION)
        test_result_dict[constants.RESULT_COL_DO_DURATION] = test_method_info.get(constants.DO_DURATION)
        test_result_dict[constants.RESULT_COL_POST_DURATION] = test_method_info.get(constants.POST_DURATION)
    else:
        test_bug_dict[constants.BUG_COL_BUG_TITLE] = "脚本执行错误"
        test_bug_dict[constants.BUG_COL_BUG_TYPE] = ""
        test_bug_dict[constants.BUG_COL_TEST_TOOL] = ""
        test_bug_dict[constants.BUG_COL_PRECONDITION] = ""
        test_bug_dict[constants.BUG_COL_STEPS] = ""
        test_result_dict[constants.RESULT_COL_PRE_DURATION] = "0.0"
        test_result_dict[constants.RESULT_COL_DO_DURATION] = "0.0"
        test_result_dict[constants.RESULT_COL_POST_DURATION] = "0.0"

    # 写测试用例信息
    test_result_dict[constants.RESULT_COL_CASE_TITLE] = constants.DEFAULT_RESET_SIMULATOR_CASE_TITLE
    test_result_dict[constants.RESULT_COL_SCRIPT_RESULT] = constants.REPORT_COL_SCRIPT_FAIL
    # 填写配置文件
    config_dict, ip_dict = get_conf()
    test_bug_dict[constants.BUG_COL_PROJECT_ID] = config_dict.get(constants.ENV_PROJECT_ID)
    test_bug_dict[constants.BUG_COL_GIT_BRANCH_ID] = config_dict.get(constants.ENV_GIT_BRANCH)
    test_bug_dict[constants.BUG_COL_GIT_BRANCH_VERSION] = config_dict.get(constants.ENV_GIT_BRANCH_VERSION)
    test_bug_dict[constants.BUG_COL_TASK_ID] = config_dict.get(constants.ENV_TASK_NAME)
    test_bug_dict[constants.BUG_COL_OPENED_BUILD] = config_dict.get(constants.ENV_OPENED_BUILD)
    test_bug_dict[constants.BUG_COL_OPENED_BY] = config_dict.get(constants.ENV_OPENED_BY)
    test_bug_dict[constants.BUG_COL_TEST_PHASE] = config_dict.get(constants.ENV_TEST_PHASE)
    test_bug_dict[constants.BUG_COL_PRODUCT_ID] = config_dict.get(constants.ENV_PRODUCT_ID)
    test_bug_dict[constants.BUG_COL_HOST_IP] = ip_dict.get(constants.ENV_HOST_IP)
    test_bug_dict[constants.BUG_COL_IOC_IP] = ip_dict.get(constants.ENV_IOC_IP)
    test_bug_dict[constants.BUG_COL_HOST_OS] = config_dict.get(constants.ENV_HOST_OS)
    test_bug_dict[constants.BUG_COL_CPU_ARCHITECTURE] = config_dict.get(constants.ENV_HOST_CPU)
    test_bug_dict[constants.BUG_COL_BACKPLANE] = config_dict.get(constants.ENV_TEST_PLATFORM)
    return test_bug_dict, test_result_dict


def parse_bug_info(re_stdout: str, post_bug_object: Bug) -> tuple:
    """
    author: luyafei、panpan.du
    date  : 2020.04.21
    description: 解析测试结果，将结果存入问题对象中
    :param re_stdout: 脚本执行结果
    :param post_bug_object: 问题对象
    :return: 填入测试结果信息之后的问题对象
    """
    re_stdout = str(re_stdout)
    if re_stdout is not None:
        std_out = re_stdout.split(constants.OUTPUT_SPLIT_KEY)[-1]
        re_stdout = std_out.split(constants.OUTPUT_END_SPLIT_KEY)[0]
    # 检查post的信息
    try:
        out_dict = eval(re_stdout)
        post_bug_dict = out_dict.get(constants.POST_RESULT)
        test_bug_dict = out_dict.get(constants.TEST_RESULT)
        core_crash_bug_dict = out_dict.get(constants.CORE_CRASH_RESULT)
    except Exception:
        post_bug_dict = None
        test_bug_dict = None
        core_crash_bug_dict = None
        post_bug_object.set_title("脚本执行错误")
        post_bug_object.set_steps("")
        log.error("Script error info：%s, please check your script" % re_stdout)
    # 检查post信息
    if post_bug_dict is not None and len(post_bug_dict) != 0:
        post_bug_object = handle_bug_dict_to_object(post_bug_dict, post_bug_object)

    # 检查test信息
    if test_bug_dict is not None and len(test_bug_dict) != 0:
        test_bug_object = copy.copy(post_bug_object)
        test_bug_object = handle_bug_dict_to_object(test_bug_dict, test_bug_object)
    else:
        test_bug_object = None

    # 检查core、Crash信息
    if core_crash_bug_dict is not None and len(core_crash_bug_dict) != 0:
        core_crash_bug_object = copy.copy(post_bug_object)
        core_crash_bug_object = handle_bug_dict_to_object(core_crash_bug_dict, core_crash_bug_object)
    else:
        core_crash_bug_object = None
    log.info("core crash bug object: %s" % core_crash_bug_object)

    return post_bug_object, test_bug_object, core_crash_bug_object


def parse_result_info(re_stdout: str, result_object: Result) -> Result:
    """
    author: luyafei、panpan.du
    date  : 2020.04.21
    description: 解析测试结果，将脚本中主要方法的执行时长信息存入结果对象中
    :param re_stdout: 脚本执行结果
    :param result_object: 结果对象
    :return: 填入主要方法测试时长后的结果对象
    @changelog      sunql
                1、增加 cli_result_max_time 处理
    """
    pre_duration = 0.0
    do_duration = 0.0
    post_duration = 0.0
    iops = '-'
    bw = '-'
    resp_time = '-'
    raw_perf_data = '-'
    cli_result_max_time = '-'
    methods_time = MethodTime()

    if re_stdout is not None:
        re_stdout = re_stdout.split(constants.OUTPUT_SPLIT_KEY)[-1]
        re_stdout = re_stdout.split(constants.OUTPUT_END_SPLIT_KEY)[0]
    # log.warning(f"============> re_stdout:{re_stdout}")
    methods_duration = {}
    try:
        out_dict = eval(re_stdout)
        methods_duration = out_dict.get(constants.METHODS)
        pre_duration = methods_duration.get(constants.PRE_DURATION, "0.0")
        do_duration = methods_duration.get(constants.DO_DURATION, "0.0")
        post_duration = methods_duration.get(constants.POST_DURATION, "0.0")
        iops = methods_duration.get(constants.FM_IOPS, '-')
        bw = methods_duration.get(constants.FM_BW, '-')
        resp_time = methods_duration.get(constants.FM_RESP_TIME, '-')
        raw_perf_data = methods_duration.get(constants.FM_RAW_PERF_DATA, '-')
        cli_result_max_time = methods_duration.get(constants.CLI_RESULT_MAX_TIME, '-')
    except BaseException:
        log.warning(f"methods_duration:{methods_duration}，解析失败")
    try:
        pre_duration = round(float(pre_duration), constants.DURATION_ROUND_BIT)
        do_duration = round(float(do_duration), constants.DURATION_ROUND_BIT)
        post_duration = round(float(post_duration), constants.DURATION_ROUND_BIT)
    except Exception as e:
        log.error(str(e))

    methods_time.set_pre_duration(pre_duration)
    methods_time.set_do_duration(do_duration)
    methods_time.set_post_duration(post_duration)
    result_object.set_methods_time(methods_time)
    result_object.set_cli_result_max_time(cli_result_max_time)
    result_object.set_performance(iops, bw, resp_time, raw_perf_data)

    return result_object


def parse_stop_test(re_stdout: str) -> bool:
    """
    description: 解析测试结果，获取stop_test value
    author: luyafei
    date  : 2020.10.01
    :param re_stdout:
    :return:bool
    """
    stop_test = False

    if re_stdout is not None:
        re_stdout = re_stdout.split(constants.OUTPUT_SPLIT_KEY)[-1]
        re_stdout = re_stdout.split(constants.OUTPUT_END_SPLIT_KEY)[0]

    try:
        out_dict = eval(re_stdout)
        if out_dict.get('stop_test') == 'yes':
            log.info("test stop is yes")
            stop_test = True
    except Exception as e:
        log.error(str(e))

    return stop_test


def handle_result_info(case_dict_list: list, result_excel_file: str, output: str, script_result: str) -> None:
    """
    author: luyafei
    date  : 2020.10.01
    description: 处理脚本不存在或ping测试主机ip失败时的结果信息
    :param case_dict_list: 脚本对应的测试用例信息
    :param result_excel_file: 结果列表文件
    :param output: 输出信息
    :param script_result: 脚本执行的结果
    :return: 无返回
    """
    result_object = make_result_object(get_time_dd_hh(time.localtime(time.time())), time_duration="0.0")
    result_object = parse_result_info(output, result_object)
    result_object.set_script_result(script_result)
    result_dict = bug_result_excel_handle.append_result_to_excel(result_object, case_dict_list, result_excel_file)
    # 提交res信息到禅道
    submit_to_zentao(result_dict)


def handle_bug_dict_to_object(bug_dict: dict, bug_object: Bug) -> Bug:
    """
    author: panpan.du
    date  : 2020.10.22
    description: bug字典转化为一个Bug对象
    :param bug_dict: Bug字典
    :param bug_object: Bug对象
    :return: 填入测试结果信息之后的Bug对象
    """
    bug_object.set_title(str(bug_dict.get(constants.BUG_TITLE, "")))
    bug_object.set_type_name(str(bug_dict.get(constants.BUG_TYPE, "")))
    bug_object.set_test_tool(str(bug_dict.get(constants.BUG_TOOL, "")))
    bug_object.set_precondition(
        str(bug_dict.get(constants.BUG_COL_PRECONDITION, "")))

    post_precondition = "前置步骤:\n" + \
                        str(bug_dict.get(constants.BUG_COL_PRECONDITION))
    post_steps = "步骤：\n" + str(bug_dict.get(constants.BUG_COL_STEPS, ""))
    post_result = "测试结果：" + str(bug_dict.get(constants.BUG_RESULT, ""))
    post_expect = "预期结果：" + str(bug_dict.get(constants.BUG_EXPECT, ""))
    post_test_steps = ";".join(
        [post_precondition, post_steps, post_result, post_expect])
    post_test_steps = post_test_steps.replace("；", ";")
    post_test_steps = post_test_steps.replace(";;", ";")
    post_test_steps = post_test_steps.replace(";", ";\n")

    bug_object.set_steps(post_test_steps)

    return bug_object


def format_script_output(output: str) -> dict:
    """
    格式化脚本输出
    :param output:
    :return: dict
    """
    out_dict = {}
    if output:
        output = output.split(constants.OUTPUT_SPLIT_KEY)[-1]
        output = output.split(constants.OUTPUT_END_SPLIT_KEY)[0]
        try:
            out_dict = eval(output)
        except BaseException:
            out_dict = {}
            log.exception(output)

    if not out_dict:
        # 如果output为空，则补一个初始结果，当脚本执行超时时，output为空
        log.warning(">> the output is empty,set a init result dict to out_dict.")
        out_dict = {'test_result': {'object': '',
                                    'module': '',
                                    'tool': '',
                                    'precondition': '',
                                    'steps': '',
                                    'title': '',
                                    'type': '',
                                    'result': '',
                                    'expect': '',
                                    },
                    'post_result': {'object': '',
                                    'module': '',
                                    'tool': '',
                                    'precondition': '',
                                    'steps': '',
                                    },
                    'methods': {'pre_duration': '0',
                                'do_duration': '0',
                                'post_duration': '0'}
                    }
    return out_dict


def collect_logs(collect_log: object, log_file: str, test_script_log_dir: str, script_name: str) -> tuple:
    """
    author: DuPanPan
    date  : 2020.05.06
    :param collect_log：收集日志对象
    :param log_file: 框架日志路径
    :param test_script_log_dir: 测试脚本日志路径
    :param script_name: 脚本名称
    :return log_script_path: 日志文件的路径

    @changelog      2022-02-22 17:38:46  haibin.xu
                    1. expander 物理环境，test_entry为host情况下，打开日志收集
    """
    ioc_core_flag = False
    ioc_crash_flag = False
    host_crash_flag = False

    log_script_path = collect_log.make_script_directory_in_log_server(script_name)

    collect_log_flag = collect_log.collect_log()

    # 收集 ps3server日志
    collect_log.collect_framework_log()

    return log_script_path, ioc_core_flag, ioc_crash_flag, host_crash_flag, collect_log_flag


def _isvalid_param(param=None) -> bool:
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


def log_dir_change_mode(file_path: str) -> None:
    """
    author: DuPanPan
    date  : 2020.11.03
    :param file_path: 测试脚本日志路径
    :return:无返回值
    """
    change_file_mode_script = os.path.join(constants.CHANGE_MODE_FILE_PATH)

    config_dict, ip_dict = get_conf()
    log_server_ip = ip_dict.get(constants.ENV_LOG_SERVER_IP)
    cmd = " timeout 10s ssh %s@%s 'sudo %s %s'" % (constants.ENV_LOG_SERVER_ACCOUNT_FRAMEWORK, log_server_ip,
                                                   change_file_mode_script, file_path)
    log.info("Change file mode cmd: %s" % cmd)
    res, output = commands.exec_run_script_cmd(cmd, True)
    if res != 0:
        log.error("Change file mode execute failed, will retry. Return code: %d, output: %s" % (res, str(output)))
        res, output = commands.exec_run_script_cmd(cmd, True)
        if res == constants.RETURN_CODE_TIMEOUT:
            log.error("The script run timeout. Output: %s" % str(output))
        elif res != 0:
            log.error("Change file mode failed. Output: %s" % str(output))


def add_summary_info_to_dict(test_info_dict: dict) -> None:
    """
    author: luyafei
    date  : 2020.05.23
    :param test_info_dict: 测试问题、结果信息字典
    :return: 无返回值
    """
    summary_info_dict = {}
    summary_info_dict.setdefault(constants.REPORT_COL_SCRIPT_PASS, ReportSummary.pass_num)
    summary_info_dict.setdefault(constants.REPORT_COL_SCRIPT_FAIL, ReportSummary.fail_num)
    summary_info_dict.setdefault(constants.REPORT_COL_SCRIPT_SKIP, ReportSummary.skip_num)
    summary_info_dict.setdefault(constants.REPORT_COL_SCRIPT_NOT_EXIST, ReportSummary.not_exist_num)
    test_info_dict.setdefault(constants.SCRIPT_SUMMARY_TAG, summary_info_dict)
    test_info_dict.setdefault(constants.IOC_VERSION, get_ioc_version())


def get_case_scripts_dir_name(test_object=None) -> str:
    """
    author: sunming
    date: 2021.01.06
    :param test_object: 测试对象
    :return: 脚本路径
    """
    if test_object is None:
        config_dict, _ = get_conf()
        test_object = config_dict.get(constants.ENV_TEST_OBJECT, 'raid')
    if 'raid' == test_object or 'None' == test_object:
        return 'scripts'
    else:
        return 'scripts_hba'


def get_ioc_version() -> str:
    ips_dict = ConfigManager.get_config_manager_object().ips_dict_get()
    soc_ip = ips_dict[constants.TEST_CONFIG_IOC_QEMU_IP]
    soc_port = ips_dict[constants.TEST_CONFIG_IOC_PORT]
    host_ioc_ip = soc_ip + " -p " + str(soc_port)
    cmd = "ssh -q -o 'UserKnownHostsFile /dev/null' root@{} '/opt/ps3/ioc -v'".format(host_ioc_ip)
    _, output = subprocess.getstatusoutput(cmd)
    return output


def get_process_id(name):
    """
    author: sunming
    date: 2021.06.01
    :param name: 进程包含的字符串
    :return: 进程PID
    """
    child = subprocess.Popen(['pgrep', '-f', name], stdout=subprocess.PIPE, shell=False)
    response = child.communicate()[0]
    return response.decode().strip()


def submit_to_zentao(result_data: dict = {}, bug_data: dict = {}, zentao_plantform_branch: int = 0) -> None:
    env_config, _ = get_conf()
    parameter_dict = env_config.get(constants.ENV_PARAM_FROM_ZENTAO)

    log.info('-------------------parameter-dict----------------------')
    log.info(parameter_dict)
    log.info('---------------------------------------------------------')

    if parameter_dict == '' or parameter_dict is None or parameter_dict == 'None':
        log.info('Test not from zentao run success.')
        return

    parameter_dict['product_id'] = parameter_dict.get('product').get('product_id')
    parameter_dict['task_id'] = parameter_dict.get('task').get('task_id')
    parameter_dict['product_id'] = 0 if parameter_dict['product_id'] == '' else int(parameter_dict['product_id'])
    parameter_dict['task_id'] = 0 if parameter_dict['task_id'] == '' else int(parameter_dict['task_id'])
    parameter_dict['job_id'] = env_config.get(constants.ENV_JOB_ID)

    if bool(result_data):
        log.info('-----------------post-result-data----------------------')
        log.info(result_data)
        log.info('---------------------------------------------------------')
        results_submit(parameter_dict, result_data)
    if bool(bug_data):
        log.info('-----------------post-bug-data----------------------')
        log.info(bug_data)
        log.info('---------------------------------------------------------')
        bugs_submit(parameter_dict, bug_data, zentao_plantform_branch)


def bugs_submit(parameter_dict: dict, bug_data: dict, zentao_plantform_branch: int = 0) -> None:
    """
    author:                           sunql
    date:                             2021.09.20
    description:                      调用提交bug信息接口
    :param parameter_dict:            env参数字典
    :param bug_data:                  提交的bug信息
    :param zentao_plantform_branch:   zentao_plantform_branch
    """
    from jenkins.utils import common as jin_common, constants as jin_constants

    bugs_batch = {
        'autoCommit': True,
        'bugs': [bug_data]
    }

    timestamp_str, md5_token = jin_common.md5_token_get(parameter_dict['code'], parameter_dict['key'])
    bugs_url_submit = jin_constants.ZENTAO_BASE_URL_BUGS_SUBMIT + '{}&branch={}&code={}&time={}&token={}&t=json'. \
        format(parameter_dict['product_id'], zentao_plantform_branch, parameter_dict['code'], timestamp_str, md5_token)
    try:
        respone = requests.post(bugs_url_submit, json.dumps(bugs_batch))
        log.info(f"post bug to zentao is：{respone.status_code}")
    except Exception as e:
        log.error(f"post bug to zentao error: {e}")


def results_submit(parameter_dict: dict, result_data: dict) -> None:
    """
    author:                           sunql
    date:                             2021.09.20
    description:                      调用提交result信息接口
    :param parameter_dict:            env参数字典
    :param task_id:                   指定提交接口的taskID值
    :param result_data:               提交的result信息
    """
    from jenkins.utils import common as jin_common, constants as jin_constants
    timestamp_str, md5_token = jin_common.md5_token_get(parameter_dict['code'], parameter_dict['key'])

    test_type = "testtask"
    if parameter_dict['task_id'] == 0:
        test_type = "testcase"

    results_batch = {
        'autoCommit': True,
        'jenkinsJobId': parameter_dict['job_id'],
        'results': [result_data]
    }

    results_url_submit = \
        jin_constants.ZENTAO_BASE_URL_RESULTS_SUBMIT + '&from={}&task_id={}&code={}&time={}&token={}&t=json'.format(
            test_type, parameter_dict['task_id'], parameter_dict['code'], timestamp_str, md5_token)
    try:
        respone = requests.post(results_url_submit, json.dumps(results_batch))
        log.info(f"post results to zentao is：{respone.status_code}")
    except Exception as e:
        log.error(f"post results to zentao error: {e}")


def test_run_submit(res: dict, start_time: str) -> dict:
    """
    author:                           sunql
    date:                             2021.09.20
    description:                      调用禅道信息接口
    :param parameter_dict:            env参数字典
    :param task_id:                   指定提交接口的taskID值
    :param result_data:               提交的result信息
    """
    env_config, ip_dict = get_conf()
    parameter_dict = env_config.get(constants.ENV_PARAM_FROM_ZENTAO)
    debug_mode = env_config.get(constants.ENV_DEBUG_MODE)
    if debug_mode:
        return {}

    log.info('-------------------parameter-dict----------------------')
    log.info(parameter_dict)
    log.info('---------------------------------------------------------')

    if parameter_dict == '' or parameter_dict is None or parameter_dict == 'None':
        log.info('Test not from zentao run success.')
        return {}

    parameter_dict['product_id'] = parameter_dict.get('product').get('product_id')
    parameter_dict['task_id'] = parameter_dict.get('task').get('task_id')
    parameter_dict['product_id'] = 0 if parameter_dict['product_id'] == '' else int(parameter_dict['product_id'])
    parameter_dict['task_id'] = 0 if parameter_dict['task_id'] == '' else int(parameter_dict['task_id'])

    from jenkins.utils import common as jin_common, constants as jin_constants
    timestamp_str, md5_token = jin_common.md5_token_get(parameter_dict['code'], parameter_dict['key'])

    data = {}
    data['owner'] = parameter_dict['user_name']
    data['task_id'] = parameter_dict['task_id']
    data['product'] = parameter_dict['product_id']
    data['job_uuid'] = env_config.get(constants.ENV_JOB_UUID)
    data['host_ip'] = ip_dict.get(constants.ENV_HOST_IP)
    data['host_label'] = env_config.get(constants.ENV_HOST_LABEL)
    data['platform'] = env_config.get(constants.ENV_TEST_PLATFORM)
    # data['test_obj'] = env_config.get(constants.ENV_TEST_OBJECT)
    data['test_obj'] = res.get('test_object')
    data['start_time'] = int(start_time)
    data['end_time'] = int(time.time())
    data['type'] = env_config.get(constants.ENV_TEST_OBJECT)
    data['os'] = env_config.get(constants.ENV_HOST_OS)
    data['kernel'] = res.get('kernel')
    data['cpu'] = res.get('cpu')
    data['memory'] = res.get('memory')
    data['disk_num'] = res.get('disk_num')
    data['ioc_version'] = res.get('ioc_version')
    data['driver_version'] = res.get('driver_build_branch')
    data['cli_version'] = res.get('cli_version')
    data['cpld_version'] = res.get('cpld_version')
    log.info(json.dumps(data))

    results_url_submit = \
        jin_constants.ZENTAO_BASE_URL_TESTRUN_SUBMIT + '&code={}&time={}&token={}&t=json'.format(
            parameter_dict['code'], timestamp_str, md5_token)

    try:
        respone = requests.post(results_url_submit, json.dumps(data))
        log.info(f"post job info to zentao is：{respone.status_code}")
        # log.info(f"{respone.text}")
    except Exception as e:
        log.error(f"post job info to zentao error: {e}")

    return data
