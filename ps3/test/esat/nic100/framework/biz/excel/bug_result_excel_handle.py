# -*- encoding=utf8 -*-
import os
import openpyxl

from libs import constants
from libs import utils_excel
from libs.classes.bug import Bug
from libs.classes.result import Result
from scripts.script_libs import log

"""
author: luyafei
date  : 2020.04.26
description: 生成问题和结果excel文件，并写入相关信息
"""


def bug_list_columns() -> list:
    """
    author: luyafei、panpan.du
    date  : 2020.04.26
    description: 生成问题列表文件的列信息
    :return: 问题列表文件的列信息表
    """
    bug_column_list = [constants.BUG_COL_CASE_ID, constants.BUG_COL_BUG_TITLE, constants.BUG_COL_BUG_TYPE,
                       constants.BUG_COL_TEST_TYPE, constants.BUG_COL_TEST_TOOL, constants.BUG_COL_PRECONDITION,
                       constants.BUG_COL_STEPS, constants.BUG_COL_FREQUENCY, constants.BUG_COL_STATUS,
                       constants.BUG_COL_ASSIGNED_TO, constants.BUG_COL_DEADLINE, constants.BUG_COL_SEVERITY,
                       constants.BUG_COL_PRIORITY, constants.BUG_COL_LOG_PATH, constants.BUG_COL_CASE_VERSION,
                       constants.BUG_COL_TEST_SCRIPT, constants.BUG_COL_BRANCH_ID, constants.BUG_COL_MODULE_ID,
                       constants.BUG_COL_MODULE_NAME, constants.BUG_COL_PROJECT_ID, constants.BUG_COL_GIT_BRANCH_ID,
                       constants.BUG_COL_GIT_BRANCH_VERSION, constants.BUG_COL_TASK_ID, constants.BUG_COL_TASK_NAME,
                       constants.BUG_COL_OPENED_BUILD, constants.BUG_COL_OPENED_BY, constants.BUG_COL_TEST_PHASE,
                       constants.BUG_COL_PRODUCT_ID, constants.BUG_COL_HOST_IP, constants.BUG_COL_HOST_OS,
                       constants.BUG_COL_CPU_ARCHITECTURE, constants.BUG_COL_BACKPLANE, constants.BUG_COL_PLATFORM,
                       constants.BUG_COL_PLATFORM_INFO]

    return bug_column_list


def __result_list_columns() -> list:
    """
    author: luyafei、panpan.du
    date  : 2020.04.26
    description: 生成结果列表文件的列信息
    :return: 结果列表文件的列信息表
    """
    result_column_list = [constants.RESULT_COL_CASE_ID, constants.RESULT_COL_CASE_VERSION,
                          constants.RESULT_COL_CASE_TITLE, constants.RESULT_COL_SCRIPT,
                          constants.RESULT_COL_SCRIPT_RESULT, constants.RESULT_COL_SCRIPT_START_TIME,
                          constants.RESULT_COL_SCRIPT_DURATION, constants.RESULT_COL_PRE_DURATION,
                          constants.RESULT_COL_DO_DURATION, constants.RESULT_COL_POST_DURATION,
                          constants.RESULT_COL_OPENED_BY, constants.RESULT_COL_MEMORY_DELTA,
                          constants.RESULT_COL_IOPS, constants.RESULT_COL_BW, constants.RESULT_COL_RESP_TIME,
                          constants.RESULT_COL_RAW_PERF_DATA, constants.RESULT_COL_CLI_RESULT_MAX_TIME,
                          constants.RESULT_TEST_PLATFORM, constants.RESULT_TEST_PLATFORM_INFO]

    return result_column_list


def __create_excel(job_output_dir: str, excel_type: str, job_info_str: str) -> object:
    """
    author: luyafei
    date  : 2020.04.28
    description: 生成excel type对应的excel文件
    :param job_output_dir: excel文件所在的路径目录
    :param excel_type: excel文件类型（bugs excel or results excel）
    :param job_info_str: 测试job信息，包括id,name,开始时间
    :return: 生成的excel文件，带路径
    """
    # TODO 如果测试脚本很多的话（比如上千条）结果列表中是否需要按模块分sheet页？
    #     如果分sheet页的话测试报告如何显示？
    excel_file_name = ""
    sheet_column_list = []
    sheet_name = ""
    if excel_type == constants.BUG_EXCEL_KEY:
        # sheet页名称
        sheet_name = constants.BUG_SHEET
        # 问题列表文件中的列标题
        sheet_column_list = bug_list_columns()
        excel_file_name = job_info_str + constants.BUG_EXCEL_SUFFIX
    elif excel_type == constants.RESULT_EXCEL_KEY:
        # sheet页名称
        sheet_name = constants.RESULT_SHEET
        # 结果列表文件中的列标题
        sheet_column_list = __result_list_columns()
        excel_file_name = job_info_str + constants.RESULT_EXCEL_SUFFIX
    excel_file_path = os.path.join(job_output_dir, excel_type)

    if not os.path.exists(excel_file_path):
        try:
            os.makedirs(excel_file_path)
        except Exception as e:
            log.error("make excel file dir error. %s" % e)
            return None
    excel_file_name = os.path.join(excel_file_path, excel_file_name)
    # 创建excel文件
    utils_excel.create_excel_file(sheet_column_list, excel_file_name,
                                  sheet_name)
    return excel_file_name


def create_files(job_output_dir: str, job_info_str: str) -> tuple:
    """
    author: luyafei
    date  : 2020.04.28
    description: 创建问题列表文件和结果列表文件
    :param job_output_dir: job测试输出信息存放路径（results,bugs,reports,logs）
    :param job_info_str: 测试job信息
    :return: 问题列表excel文件及路径 结果列表excel文件及路径
    """
    # 生成问题列表、结果列表excel文件
    if job_info_str == "" or job_info_str is None:
        log.error("job info str is %s" % job_info_str)
        exit(1)
    bug_excel_file = __create_excel(job_output_dir,
                                    constants.BUG_EXCEL_KEY,
                                    job_info_str)
    result_excel_file = __create_excel(job_output_dir,
                                       constants.RESULT_EXCEL_KEY,
                                       job_info_str)
    if (bug_excel_file is None) or (result_excel_file is None):
        log.error("bug excel or result excel create failed")
        exit(1)
    return bug_excel_file, result_excel_file


def append_bug_to_excel(bug_object: Bug, case_dict_list: list, bug_excel_file: str) -> dict:
    """
    author: luyafei、panpan.du
    date  : 2020.04.26
    description: 将问题信息追加到问题列表的excel文件中，顺序与excel的title顺序保持一致
    :param bug_object: 问题字段对象
    :param case_dict_list: 脚本对应的用例信息字典列表
    :param bug_excel_file: 问题列表文件路径及名称
    :return: 执行正常返回dict
    """
    bug_dict = {}
    log.info("bug excel file: %s" % bug_excel_file)
    try:
        workbook = openpyxl.load_workbook(bug_excel_file)
        sheet = workbook.get_sheet_by_name(constants.BUG_SHEET)
    except Exception as e:
        log.error("get bug excel sheet failed. Error is %s" % e)
        return bug_dict
    # 问题的类型信息长度不能超过30，超过的话截取前30个字符
    if len(bug_object.type_name) >= constants.BUG_TYPE_MAX_LEN:
        bug_type_name = bug_object.type_name[0:constants.BUG_TYPE_MAX_LEN]
        bug_object.set_type_name(bug_type_name)
    # 生成和excel文件列信息对应的问题信息
    bug_object.set_case_values(case_dict_list[0])
    bug_info_list = [bug_object.test_case_object.case_id, bug_object.title, bug_object.type_name,
                     bug_object.test_case_object.case_type, bug_object.test_tool, bug_object.precondition,
                     bug_object.steps, bug_object.frequency, bug_object.status, bug_object.assigned_to,
                     bug_object.deadline, bug_object.severity, bug_object.priority, bug_object.log_path,
                     bug_object.test_case_object.case_version, bug_object.test_case_object.script_path,
                     bug_object.test_case_object.branch_id, bug_object.test_case_object.module_id,
                     bug_object.test_case_object.module_name, bug_object.test_env_object.project_id,
                     bug_object.test_env_object.git_branch, bug_object.test_env_object.git_branch_version,
                     bug_object.test_env_object.task_id, bug_object.test_env_object.task_name,
                     bug_object.test_env_object.opened_build, bug_object.test_env_object.opened_by,
                     bug_object.test_env_object.test_phase, bug_object.test_env_object.product_id,
                     bug_object.test_env_object.host_ip,
                     bug_object.test_env_object.host_os, bug_object.test_env_object.host_cpu,
                     bug_object.test_env_object.backplane, bug_object.test_env_object.test_platform,
                     bug_object.test_platform_info]

    # 获取用例名称列在bug_list中的位置索引
    for case_dict in case_dict_list:
        # 更新bug_info中的用例名称并将其追加到excel文件中
        bug_object.set_case_values(case_dict)
        utils_excel.append_info_to_excel(workbook, sheet, bug_info_list,
                                         bug_excel_file)

    bug_dict = dict(zip(bug_list_columns(), bug_info_list))
    return bug_dict


def append_result_to_excel(result_object: Result, case_dict_list: list,
                           result_excel_file: str) -> dict:
    """
    author: luyafei、panpan.du
    date  : 2020.04.26
    description: 将结果信息追加到结果列表文件中
    :param result_object: 结果字段信息
    :param case_dict_list: 本次执行脚本所对应的用例字典信息列表
    :param result_excel_file: 结果列表文件
    :return: 执行正常返回dict
    excel文件列信息为:
    ["caseId", "caseVersion", "caseName", "result", "script", "startTime",
    "duration", "preDuration", "doDuration", "postDuration"]
    @changelog  sunql
                1、增加 result_object.cli_result_max_time
    """
    # 打开问题excel文件，获取sheet
    try:
        workbook = openpyxl.load_workbook(result_excel_file)
        sheet = workbook.get_sheet_by_name(constants.RESULT_SHEET)
    except Exception as result:
        log.error("get result excel sheet failed. Error is %s" % result)
        return {}
    # 生成和excel文件列信息对应的list
    result_object.set_case_values(case_dict_list[0])
    result_list = [result_object.test_case_object.case_id, result_object.test_case_object.case_version,
                   result_object.test_case_object.case_title, result_object.test_case_object.script_path,
                   result_object.script_result, result_object.start_time, result_object.script_duration,
                   result_object.methods_time.pre_duration, result_object.methods_time.do_duration,
                   result_object.methods_time.post_duration, result_object.test_env_object.opened_by,
                   result_object.memtory_delta, result_object.iops, result_object.bw, result_object.resp_time,
                   result_object.raw_perf_data, result_object.cli_result_max_time, result_object.test_platform,
                   result_object.test_platform_info
                   ]

    for case_dict in case_dict_list:
        # TODO 等case_id的信息确定后，需要将该值修改为获取到的case id
        result_object.set_case_values(case_dict)
        utils_excel.append_info_to_excel(workbook, sheet, result_list, result_excel_file)
    return dict(zip(__result_list_columns(), result_list))
