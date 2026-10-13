#!/usr/bin/python3
# -*- encoding=utf8 -*-
import optparse
import os
import openpyxl

import add_syspath
from scripts.script_libs import log
from framework.libs import utils_excel, constants, utils_new as utils
from framework.libs.classes.report_summary import ReportSummary
from framework.biz.excel import bug_result_excel_handle
from framework.biz.classes.config_file_manager import ConfigManager

"""
author: luyafei
date  : 2020.04.26
description: 生成测试报告excel文件，并写入相关信息
"""


def report_summary_columns() -> list:
    """
    author: luyafei
    date  : 2020.04.06
    description: 生成测试报告文件中概要信息列
    :return: 测试报告概要信息的列信息表
    """
    report_summary_column_list = [constants.REPORT_COL_TASK_NAME, constants.REPORT_COL_GIT_BRANCH_ID,
                                  constants.REPORT_COL_INSTALL_PACKAGE, constants.REPORT_COL_CASE_LIST_PATH,
                                  constants.REPORT_COL_TOTAL_DURATION, constants.REPORT_COL_SCRIPT_PASS,
                                  constants.REPORT_COL_SCRIPT_FAIL, constants.REPORT_COL_SCRIPT_SKIP,
                                  constants.REPORT_COL_SCRIPT_NOT_EXIST,
                                  constants.REPORT_COL_CASE_LEVEL, constants.REPORT_COL_HOST_IP,
                                  constants.REPORT_COL_IOC_IP,
                                  constants.REPORT_COL_HOST_OS, constants.REPORT_COL_TEST_PLATFORM]
    return report_summary_column_list


def report_bug_columns() -> list:
    """
    author: luyafei
    date  : 2020.04.06
    description: 生成测试报告文件中问题列信息
    :return: 测试报告中问题的列信息表
    """
    report_bug_column_list = [constants.BUG_COL_BUG_TITLE, constants.BUG_COL_BUG_TYPE, constants.BUG_COL_CASE_ID,
                              constants.BUG_COL_TEST_SCRIPT]
    return report_bug_column_list


def make_report_by_list(job_info_list: list) -> tuple:
    """
    author: luyafei
    date  : 2020.04.06
    description: 生成测试报告文件，并填入概要信息
    :param job_info_list 执行测试任务的job信息
    :return: 测试报告文件路径，测试报告文件
    """
    # 测试报告概要信息列标题
    report_summary_column_list = report_summary_columns()
    # sheet页名称
    sheet_name = constants.REPORT_SHEET
    # 由本次测试任务信息生成的文件夹名称
    folder_name = constants.FILE_NAME_CONNECTOR.join(job_info_list)
    # 结果列表文件的名称
    report_file_name = folder_name + constants.REPORT_EXCEL_SUFFIX
    # 获取当前路径及其父目录
    # ../test/esat/framework/biz/excel/report_excel_create.py
    current_path = os.path.dirname(os.path.abspath(__file__))
    # ../test/esat/framework/biz/excel
    current_path = os.path.dirname(current_path)
    # ../test/esat/framework/biz
    current_path = os.path.dirname(current_path)
    # ../test/esat/framework
    output_parent_path = os.path.dirname(current_path)
    # ../test/esat
    # 生成结果列表所在路径
    report_excel_file_path = os.path.join(output_parent_path,  constants.OUTPUTS, constants.OUTPUT_FRAMEWORK,
                                          folder_name, constants.REPORT_FOLDER_NAME)

    if not os.path.exists(report_excel_file_path):
        os.makedirs(report_excel_file_path)
    report_excel_file = os.path.join(report_excel_file_path, report_file_name)

    utils_excel.create_excel_file(report_summary_column_list, report_excel_file, sheet_name)
    return report_excel_file_path, report_excel_file


def __append_report_summary_to_excel(report_summary_object: ReportSummary,
                                     report_excel_file: str) -> None:
    """
    author: luyafei
    date  : 2020.04.06
    description: 将测试报告概要信息追加到excel文件中
    :param report_summary_object: 概要信息
    :param report_excel_file: 测试报告文件路径及名称
    """
    # 打开excel文件，获取sheet
    workbook = openpyxl.load_workbook(report_excel_file)
    sheet = workbook[constants.REPORT_SHEET]
    # 生成和excel文件列信息对应的list
    report_summary_list = [report_summary_object.task_name,
                           report_summary_object.git_branch,
                           report_summary_object.package_path,
                           report_summary_object.case_path,
                           report_summary_object.total_duration,
                           report_summary_object.pass_num,
                           report_summary_object.fail_num,
                           report_summary_object.skip_num,
                           report_summary_object.not_exist_num,
                           report_summary_object.case_level,
                           report_summary_object.host_ip,
                           report_summary_object.ioc_ip,
                           report_summary_object.host_os,
                           report_summary_object.test_platform]
    # 将report_summary_list写入excel
    utils_excel.append_info_to_excel(workbook, sheet, report_summary_list,
                                     report_excel_file)


def __append_report_bug_to_excel(report_bug_list: list, report_bug_excel: str) -> None:
    """
    author: luyafei
    date  : 2020.04.06
    description: 将测试报告中需要的问题信息追加到report bug excel文件中
    :param report_bug_list: 测试报告需要的问题信息列表
    :param report_bug_excel: 测试报告需要的问题excel文件
    """
    # 打开excel文件，获取sheet
    workbook = openpyxl.load_workbook(report_bug_excel)
    sheet = workbook.get_sheet_by_name(constants.REPORT_BUG_SHEET)
    # 生成和excel文件列信息对应的list
    for report_bug in report_bug_list:
        utils_excel.append_info_to_excel(workbook, sheet, report_bug,
                                         report_bug_excel)


def make_report(job_info_list: list, report_bug_list: list,
                report_summary_object: ReportSummary, result_excel_file: str) -> str:
    """
    author: luyafei
    date  : 2020.04.06
    description: 生成测试报告
    :param job_info_list: 执行测试任务的job信息
    :param report_bug_list: 测试报告中要包含的问题信息
    :param report_summary_object: 测试报告中的概要信息
    :param result_excel_file: 测试报告文件
    """
    report_excel_path, report_excel_file = make_report_by_list(job_info_list)
    log.info("report_excel_file: %s" % report_excel_file)
    __append_report_summary_to_excel(report_summary_object, report_excel_file)
    job_info = constants.FILE_NAME_CONNECTOR.join(job_info_list)
    report_bug_excel = os.path.join(report_excel_path, job_info + constants.REPORT_BUG_EXCEL_SUFFIX)

    report_bug_sheet_name = constants.REPORT_BUG_SHEET
    # TODO 文件创建不成功的异常处理 全部都要添加相关处理
    report_bug_column_list = report_bug_columns()
    utils_excel.create_excel_file(report_bug_column_list, report_bug_excel, report_bug_sheet_name)
    # 将report_bug_list中的信息追加到report bug excel文件中
    __append_report_bug_to_excel(report_bug_list, report_bug_excel)
    utils_excel.merge_excels(report_excel_file, [report_bug_excel, result_excel_file])
    return report_excel_file


def set_report_summary_info(config_dict: dict, host_server_ip_dict: dict,
                            arg_options: optparse.Values) -> ReportSummary:
    """
    author: luyafei
    date  : 2020.04.06
    description: 设置测试报告概要信息中的总时长、通过数量、失败数量、跳过数量
    :param config_dict: 环境配置文件中的信息字典
    :param host_server_ip_dict: 主机和服务器ip配置文件中的信息字典
    :param arg_options: 执行创建测试报告脚本时输入的参数信息
    :return: 填值后的测试报告概要信息对象
    """
    report_summary_object = ReportSummary()
    if config_dict is None:
        log.error("config dict is None")
        return report_summary_object
    report_summary_object.set_task_name(config_dict.get(constants.ENV_TASK_NAME))
    report_summary_object.set_git_branch(config_dict.get(constants.ENV_GIT_BRANCH))
    report_summary_object.set_package_path(config_dict.get(constants.ENV_PACKAGE_PATH))
    report_summary_object.set_case_level(str(config_dict.get(constants.ENV_CASE_LEVEL)))
    report_summary_object.set_case_path(config_dict[constants.ENV_CASE_SCRIPT_LIST_PATH])
    report_summary_object.set_host_os(config_dict.get(constants.ENV_HOST_OS))
    report_summary_object.set_test_platform(config_dict.get(constants.ENV_TEST_PLATFORM))
    report_summary_object.set_total_duration(arg_options.total_duration)
    report_summary_object.set_pass_num(arg_options.pass_num)
    report_summary_object.set_fail_num(arg_options.fail_num)
    report_summary_object.set_skip_num(arg_options.skip_num)
    report_summary_object.set_not_exist_num(arg_options.not_exist_num)
    if host_server_ip_dict is None:
        log.error("host server ip dict is None")
        return report_summary_object
    report_summary_object.set_x86_ip(host_server_ip_dict.get(constants.ENV_HOST_IP))
    report_summary_object.set_arm_ip(host_server_ip_dict.get(constants.ENV_IOC_IP))
    return report_summary_object


def arg_parse() -> optparse.Values:
    """
    author: luyafei
    date  : 2020.05.09
    description: 解析脚本参数
    :return: 参数选项的数据信息
    """
    # 以下是输入参数选项的信息
    parser = optparse.OptionParser()
    parser.add_option("--start", action="store", type="str",
                      dest="task_start_time",
                      help="task start time，eg: '20200423151820'")
    parser.add_option("-t", "--total", type="int", dest="total_duration",
                      default=0, help="total duration of test task ")
    parser.add_option("-p", "--pass", type="int", dest="pass_num", default=0,
                      help="pass num of test scripts ")
    parser.add_option("-f", "--fail", type="int", dest="fail_num", default=0,
                      help="fail num of test scripts")
    parser.add_option("-k", "--skip", type="int", dest="skip_num", default=0,
                      help="skip num of test scripts")
    parser.add_option("-n", "--not_exist", type="int", dest="not_exist_num", default=0,
                      help="not exist num of test scripts")
    parser.add_option("-b", "--bug", action="store", type="string",
                      dest="bug_excel",
                      help="bug excel file with path")
    parser.add_option("-r", "--result", action="store", type="string",
                      dest="result_excel",
                      help="result excel file with path")
    parser.add_option("-l", "--logfile", action="store", type="string",
                      default="",
                      dest="report_log_file")

    options, args = parser.parse_args()
    return options


def get_current_absolute_path() -> str:
    """
    author: luyafei
    date  : 20200512
    description: 获取当前脚本的绝对路径
    :return: 当前脚本的绝对路径
    """
    return os.path.abspath(__file__)


def create_report_excel(arg_options: optparse.Values) -> str:
    """
    author: luyafei
    date  : 20200511
    生成测试报告excel文件
    :param arg_options: 执行create_report_excel.py时输入的参数信息
    :return: 测试报告文件名称（含路径）
    """
    # 获取测试环境的配置信息以及所需服务器的ip信息
    env_configure = ConfigManager.get_config_manager_object()
    config_dict = env_configure.env_dict_get()
    ips_dict = env_configure.ips_dict_get()

    log.info("make report excel")
    # 生成一个测试报告概览字段对象
    report_summary_object = \
        set_report_summary_info(config_dict, ips_dict, arg_options)
    # 生成job信息列表，用于生成reports文件夹所在的文件夹名称
    job_info_list = utils.make_job_info_list(arg_options.task_start_time)
    # 生成测试报告中的bug列表
    report_bug_column_list = report_bug_columns()
    bug_column_list = bug_result_excel_handle.bug_list_columns()
    report_bug_list = \
        utils_excel.generate_report_bug_list(bug_column_list, report_bug_column_list, arg_options.bug_excel)
    report_excel_file = make_report(job_info_list, report_bug_list, report_summary_object, arg_options.result_excel)
    log.info("report excel file: %s" % report_excel_file)
    return report_excel_file


if __name__ == "__main__":
    # 解析输入的参数选项信息
    input_options = arg_parse()
    log.init(input_options.report_log_file)
    log.info("enter into create report excel")
    report_excel = create_report_excel(input_options)
    log.info("after make report excel: %s" % report_excel)
    print(report_excel)
