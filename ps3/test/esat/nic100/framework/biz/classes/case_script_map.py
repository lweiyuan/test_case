# -*- encoding=utf8 -*-
"""
author: DuPanPan
date: 2020.04.29
description: 用例和脚本关系之间转换
"""
import ast
import os
import time
import pandas
import uuid

from libs import constants
from libs import utils_excel
from scripts.script_libs import log
from biz.classes.config_file_manager import ConfigManager


def format_value(value: str) -> str:
    """
    author:DuPanPan
    date:2020.05.27
    description: 字符串去掉换行和空格
    :return value_format:标准化后的字符串
    """
    value = str(value).replace("\n", "")
    value_format = value.strip()
    return value_format


def case_title_index_get(work_sheet: object) -> dict:
    """
    author:DuPanPan
    date:2020.10.09
    description: 获取表头和对应索引号
    :param work_sheet:sheet表格
    :return title_index:表格的属性和对应表格列值
    """
    row_index_column_name = 1
    row_info = work_sheet[row_index_column_name]
    title_index = {}
    index = 0
    for cell in row_info:
        title_index[cell.value] = index
        index += 1
    return title_index


def case_filter(row_info: list, title_index: dict, case_level_list: list) -> bool:
    """
    author:DuPanPan
    date:2020.10.09
    description: 根据条件筛选用例
    :param row_info:表格获取的一行信息
    :param title_index:表格的属性和对应表格列值
    :param case_level_list:用例等级列表
    :return agree_flag:用例是否符合条件,符合为True，不符合为False
    """
    agree_flag = True
    try:
        case_level = row_info[title_index[constants.CASE_SCRIPT_CASE_LEVEL]].value
        case_title = row_info[title_index[constants.CASE_SCRIPT_CASE_TITLE]].value
        script_location = row_info[title_index[constants.CASE_SCRIPT_SCRIPT_LOCATION]].value
        need_run = row_info[title_index[constants.CASE_SCRIPT_NEED_RUN]].value
    except Exception as e:
        log.error("The excel title is error, please check your excel")
        log.error(str(e))
        return False
    case_level = str(case_level)
    # 过滤case_level和空行
    if case_level not in case_level_list or case_title is None or script_location is None \
            or (need_run is not None and need_run != constants.CASE_SCRIPT_NEED_RUN_YES):
        agree_flag = False

    return agree_flag


def case_script_read_line(row_info: list, title_index: dict) -> dict:
    """
    author: DuPanPan
    date  : 2020.04.29
    description: 将表格的一行数据读取到一个字典
    :param row_info:表格的一行数据
    :param title_index: 表格的属性和对应表格列值
    :return row_info_dict:表格的一行信息构建的字典
    """
    row_info_dict = {}
    try:
        row_info_dict[constants.CASE_SCRIPT_CASE_ID] = \
            row_info[title_index[constants.CASE_SCRIPT_CASE_ID]].value

        row_info_dict[constants.CASE_SCRIPT_CASE_TITLE] = \
            row_info[title_index[constants.CASE_SCRIPT_CASE_TITLE]].value

        row_info_dict[constants.CASE_SCRIPT_CASE_VERSION] = \
            row_info[title_index[constants.CASE_SCRIPT_CASE_VERSION]].value

        # 暂时定为functional指定值
        row_info_dict[constants.CASE_SCRIPT_CASE_TYPE] = "functional"

        row_info_dict[constants.CASE_SCRIPT_CASE_LEVEL] = \
            str(row_info[title_index[constants.CASE_SCRIPT_CASE_LEVEL]].value)

        row_info_dict[constants.CASE_SCRIPT_SCRIPT_LOCATION] = \
            row_info[title_index[constants.CASE_SCRIPT_SCRIPT_LOCATION]].value

        row_info_dict[constants.CASE_SCRIPT_BRANCH_ID] = \
            row_info[title_index[constants.CASE_SCRIPT_BRANCH_ID]].value

        row_info_dict[constants.CASE_SCRIPT_MODULE_ID] = \
            row_info[title_index[constants.CASE_SCRIPT_MODULE_ID]].value

        row_info_dict[constants.CASE_SCRIPT_MODULE_NAME] = \
            row_info[title_index[constants.CASE_SCRIPT_MODULE_NAME]].value

        row_info_dict[constants.CASE_SCRIPT_CASE_STEP] = \
            row_info[title_index[constants.CASE_SCRIPT_CASE_STEP]].value

        row_info_dict[constants.CASE_SCRIPT_RUN_ID] = \
            row_info[title_index[constants.CASE_SCRIPT_RUN_ID]].value

        row_info_dict[constants.CASE_SCRIPT_NEED_RUN] = row_info[title_index[constants.CASE_SCRIPT_NEED_RUN]].value
    except Exception as e:
        log.error(str(e))
        log.error("The excel title is error, please check your excel")
        exit(1)

    return row_info_dict


class CaseScriptMap(object):
    """
    author: DuPanPan
    date  : 2020.04.23
    description: 用例和脚本关联
    """

    def __init__(self):

        """创建用例脚本时存放路径"""
        self.__case_script_list_path = ""

        """以script为key的字典"""
        self.__case_script_dict = {}

        """关系表字段名"""
        self.__case_script_list_columns = [constants.CASE_SCRIPT_CASE_ID, constants.CASE_SCRIPT_CASE_TITLE,
                                           constants.CASE_SCRIPT_CASE_VERSION, constants.CASE_SCRIPT_CASE_TYPE,
                                           constants.CASE_SCRIPT_CASE_LEVEL, constants.CASE_SCRIPT_SCRIPT_LOCATION,
                                           constants.CASE_SCRIPT_BRANCH_ID, constants.CASE_SCRIPT_MODULE_ID,
                                           constants.CASE_SCRIPT_MODULE_NAME, constants.CASE_SCRIPT_CASE_STEP,
                                           constants.CASE_SCRIPT_RUN_ID, constants.CASE_SCRIPT_NEED_RUN]

        """禅道传入字段名"""
        self.__case_script_list_zen_columns = [constants.ZEN_CASE_SCRIPT_CASE_ID,
                                               constants.ZEN_CASE_SCRIPT_CASE_TITLE,
                                               constants.ZEN_CASE_SCRIPT_CASE_VERSION,
                                               constants.ZEN_CASE_SCRIPT_CASE_TYPE,
                                               constants.ZEN_CASE_SCRIPT_CASE_LEVEL,
                                               constants.ZEN_CASE_SCRIPT_SCRIPT_LOCATION,
                                               constants.ZEN_CASE_SCRIPT_BRANCH_ID,
                                               constants.ZEN_CASE_SCRIPT_MODULE_ID,
                                               constants.ZEN_CASE_SCRIPT_MODULE_NAME,
                                               constants.ZEN_CASE_SCRIPT_CASE_STEP,
                                               constants.ZEN_CASE_SCRIPT_RUN_ID,
                                               constants.ZEN_CASE_SCRIPT_NEED_RUN]

    def __case_script_file_create(self) -> None:
        """
          author: DuPanPan
          date  : 2020.04.29
          description: 创建用例关系集文件
          :param: sheet_name: 创建的表名称
          :return: 无返回值
          """
        classes_path = os.path.dirname(os.path.abspath(__file__))
        # ..\PS3Test\framework\biz\classes
        biz_path = os.path.dirname(classes_path)
        # \PS3Test\framework\biz
        framework_path = os.path.dirname(biz_path)
        # \PS3Test\framework\
        esat_path = os.path.dirname(framework_path)
        # \PS3Test\
        time_stamp = time.strftime(constants.DEFAULT_TIME_FORMAT, time.localtime())
        uid = str(uuid.uuid4())
        file_name = constants.CASE_SCRIPT_FILE_NAME + uid + constants.EXCEL_SUFFIX_NAME
        case_script_list_dir = os.path.join(esat_path, constants.CASE_SCRIPT_PART_PATH_NAME)
        if not os.path.exists(case_script_list_dir):
            try:
                os.makedirs(case_script_list_dir)
            except:
                log.error("Create file %s failure" % case_script_list_dir)

        sheet_name = constants.CASE_SCRIPT_SHEET_NAME
        self.__case_script_list_path = os.path.join(esat_path, constants.CASE_SCRIPT_PART_PATH_NAME, file_name)
        utils_excel.create_excel_file(self.__case_script_list_columns, self.__case_script_list_path, sheet_name)

    def __case_script_list_format(self, case_script_rel_list: list) -> list:
        """
        author: DuPanPan
        date  : 2020.05.23
        description: 标准化数据，将禅道关键字更改为框架关系表的字段名
        :param: case_script_rel_list，用例脚本关系列表，字典组成的列表
        :return format_list_of_dicts：返回格式化后的列表
        """
        if isinstance(case_script_rel_list, str):
            list_of_dicts = ast.literal_eval(case_script_rel_list)
        else:
            list_of_dicts = case_script_rel_list
        if not isinstance(list_of_dicts, list):
            log.error("Wrong parameter for creating file of case script list external:%s" % type(list_of_dicts))
            exit(1)

        format_list_of_dicts = []
        for one_dict in list_of_dicts:
            if isinstance(one_dict, str):
                one_dict_data = ast.literal_eval(one_dict)
            else:
                one_dict_data = one_dict
            if not isinstance(one_dict_data, dict):
                log.error("Wrong parameter for creating file of case script list inner: %s" % type(one_dict_data))
                exit(1)
            format_dict = dict()
            # 根据传入字典的关键字找到表格中对应的字段名，形成以表格字段为关键字的一个字典
            for key in self.__case_script_list_columns:
                index = self.__case_script_list_columns.index(key)
                zen_key = self.__case_script_list_zen_columns[index]
                format_dict[key] = one_dict_data.get(zen_key)
            format_list_of_dicts.append(format_dict)
        return format_list_of_dicts

    def case_script_file_create(self, case_script_list: list) -> str:
        """
        author: DuPanPan
        date  : 2020.04.29
        description: 创建用例脚本关系集excel表格并填入数据
        :param: list_dict_case_script_rel，用例脚本关系列表
        :return self.__path_case_script_rel_list：返回文件路径
        """
        self.__case_script_file_create()
        case_script_list_format = self.__case_script_list_format(case_script_list)
        workbook = utils_excel.get_work_book(self.__case_script_list_path)
        sheet_name = constants.CASE_SCRIPT_SHEET_NAME
        worksheet = workbook[sheet_name]
        for item in case_script_list_format:
            script_locations = item.get(constants.CASE_SCRIPT_SCRIPT_LOCATION)
            script_locations_list = str(script_locations).split(constants.CASE_SCRIPT_LOCATIONS_SPLIT_FLAG)
            for script_location in script_locations_list:
                row_info = []
                item[constants.CASE_SCRIPT_SCRIPT_LOCATION] = script_location
                for key in self.__case_script_list_columns:
                    row_info.append(format_value(str(item.get(key))))
                worksheet.append(row_info)
        workbook.save(self.__case_script_list_path)
        log.info("write excel file %s success" % self.__case_script_list_path)
        return self.__case_script_list_path

    def case_add_dict(self, row_info: list, title_index: dict, test_script_list: list, test_case_list: list,
                      row_info_dict: dict) -> None:
        """
        author:DuPanPan
        date:2020.10.09
        description: 根据条件筛选用例
        :param row_info:表格的一行数据
        :param title_index: 表格的属性和对应表格列值
        :param test_script_list: 测试脚本集列表
        :param test_case_list: 测试用例集列表
        :param row_info_dict:表格的一行信息构建的字典
        :return 无返回值
        """
        case_title = row_info[title_index[constants.CASE_SCRIPT_CASE_TITLE]].value
        script_location = row_info[title_index[constants.CASE_SCRIPT_SCRIPT_LOCATION]].value
        # 根据给出的script_list的查询到的关系表
        if test_script_list != "" and test_script_list is not None:
            if script_location in test_script_list:
                if script_location not in self.__case_script_dict.keys():
                    self.__case_script_dict[script_location] = []
                self.__case_script_dict[script_location].append(row_info_dict)
        # 根据给出的case_list的关系表
        elif test_case_list != "" and test_case_list is not None:
            if case_title in test_case_list:
                if script_location not in self.__case_script_dict.keys():
                    self.__case_script_dict[script_location] = []
                self.__case_script_dict[script_location].append(row_info_dict)

        # 配置文件中没有指定测试用例列表，也没有指定测试脚本列表，
        # 则返回关系集中所有数据
        else:
            if script_location not in self.__case_script_dict.keys():
                self.__case_script_dict[script_location] = list()
            self.__case_script_dict[script_location].append(row_info_dict)

    def __case_script_file_read(self) -> None:
        """
        :author: DuPanPan
        :date  : 2020.04.23
        :description:读取用例脚本关系集
        :return: 无返回值
        """
        config_xml_manager = ConfigManager.get_config_manager_object()
        env_config_dict = config_xml_manager.env_dict_get()
        case_script_list_path = env_config_dict.get(constants.ENV_CASE_SCRIPT_LIST_PATH)
        test_case_list = env_config_dict.get(constants.ENV_TEST_CASE_LIST)
        test_script_list = env_config_dict.get(constants.ENV_TEST_SCRIPT_LIST)
        case_level_list = env_config_dict.get(constants.ENV_CASE_LEVEL)
        work_book = utils_excel.get_work_book(case_script_list_path)
        for sheet in work_book.sheetnames:
            # 获取表格名
            work_sheet = work_book[sheet]
            title_index = case_title_index_get(work_sheet)
            # 从第2行读取数据到一个以脚本为关键字的字典中
            for row_info in work_sheet.iter_rows(min_row=constants.CASE_SCRIPT_READ_MIN_ROW):
                # 过滤不符合条件的用例
                if case_filter(row_info, title_index, case_level_list) is False:
                    continue
                # 将表格的一行数据读取到一个字典
                row_info_dict = case_script_read_line(row_info, title_index)
                # 将用例信息字典加入到对应的脚本字典中去
                self.case_add_dict(row_info, title_index, test_script_list, test_case_list, row_info_dict)

    def __case_script_file_read_csv(self) -> None:
        """
        :author: zanzan.feng
        :date  : 2020.11.20
        :description:从csv表中读取用例脚本关系集
        :return: 无返回值
        """
        config_xml_manager = ConfigManager.get_config_manager_object()
        env_config_dict = config_xml_manager.env_dict_get()
        case_script_list_path = env_config_dict.get(constants.ENV_CASE_SCRIPT_LIST_PATH)
        log.info("csv file in %s " % case_script_list_path)
        start_row = int(constants.CASE_SCRIPT_READ_MIN_ROW) - 1
        # constants定义的表头信息
        contents = constants.ScriptsHeader.header
        try:
            df = pandas.read_csv(case_script_list_path, encoding="gb2312", header=None, keep_default_na=False)
        except UnicodeDecodeError:
            df = pandas.read_csv(case_script_list_path, encoding="utf-8", header=None, keep_default_na=False)
        except Exception as e:
            log.error("%s decode error reason %s" % (case_script_list_path, e))
        # 获取标题信息
        header = [i for i in df.iloc[0]]
        log.info("csv header is %s " % header)
        # 检查title是否满足
        rtn_flag = True
        try:
            # 根据配置文件匹配csv文件内容是否在配置信息中
            for name in header:
                if name not in constants.ScriptsHeader.header.values():
                    log.error("value is false, csv value:%s" % name)
                    rtn_flag = False
        except IndexError:
            log.error("header nums is false, csv num:%s, contants num:%s contents:%s" %
                      (len(header), len(contents), contents))
            rtn_flag = False
        except Exception as e:
            log.error("title is error reason %s " % e)
            rtn_flag = False
        if rtn_flag:
            # 检查scriptLocation 是否为空如果为空就过滤此行信息, 如果needRun 不为Y则过滤，如果case_level不在参数内则过滤
            scriptLocation_index = header.index("scriptLocation")
            needRun_index = header.index("needRun")
            case_level_index = header.index("caseLevel")
            case_level = env_config_dict.get(constants.REPORT_ATTR_CASE_LEVEL)
            log.info("case level params %s" % case_level)
            scripts_names = {}
            for i in range(start_row, df.shape[0]):
                list_data = list(df.iloc[i])
                dict_data = {}
                if list_data[scriptLocation_index] \
                        and list_data[needRun_index].upper() == "Y" and list_data[case_level_index] in case_level:
                    dict_data = dict(zip(header, list_data))
                if dict_data:
                    data = []
                    data.append(dict_data)
                    scripts_names.update({dict_data["scriptLocation"]: data})
            self.__case_script_dict = scripts_names

    def case_script_dict_get(self) -> dict:
        """
        :author: DuPanPan
        :date:2020.04.23
        :description:对外提供关联方法，返回字典
        :return self.__dict_case_scripts:符合条件的用例脚本结果字典
        changelog: 当路径为csv时调用csv方法解析 date 2020.11.13
        """
        self.__case_script_dict = {}
        config_xml_manager = ConfigManager.get_config_manager_object()
        env_config_dict = config_xml_manager.env_dict_get()
        case_script_list_path = env_config_dict.get(constants.ENV_CASE_SCRIPT_LIST_PATH)
        if ".csv" in case_script_list_path:
            self.__case_script_file_read_csv()
        else:
            self.__case_script_file_read()

        if not self.__case_script_dict:
            log.error("Test script list is empty")
            exit(1)
        return self.__case_script_dict

    def __shuffle_case_script_file_create(self, file_path: str) -> None:
        """
          author: sunql
          description: 创建用例关系集文件
          :return: 无返回值
          """

        time_stamp = time.strftime(constants.DEFAULT_TIME_FORMAT, time.localtime())
        file_name = 'shuffle_' + constants.CASE_SCRIPT_FILE_NAME + time_stamp + constants.EXCEL_SUFFIX_NAME
        case_script_list_dir = file_path
        if not os.path.exists(case_script_list_dir):
            try:
                os.makedirs(case_script_list_dir)
            except:
                log.error("Create file %s failure" % case_script_list_dir)

        sheet_name = constants.CASE_SCRIPT_SHEET_NAME
        self.__case_script_list_path = os.path.join(case_script_list_dir, file_name)
        utils_excel.create_excel_file(self.__case_script_list_columns, self.__case_script_list_path, sheet_name)

    def shuffle_case_script_file_create(self, case_script_dict: dict, file_pah: str) -> str:
        """
        author: sunql
        date  : 2020.08.19
        description: 创建用例脚本关系集excel表格并填入数据
        :param: list_dict_case_script_rel，用例脚本关系列表
        :return self.__path_case_script_rel_list：返回文件路径
        """
        self.__shuffle_case_script_file_create(file_pah)
        workbook = utils_excel.get_work_book(self.__case_script_list_path)
        sheet_name = constants.CASE_SCRIPT_SHEET_NAME
        worksheet = workbook[sheet_name]
        case_list = list(case_script_dict.values())
        for item in case_list:
            row_info = []
            item = item[0]
            for key in self.__case_script_list_columns:
                row_info.append(format_value(str(item.get(key))))
            worksheet.append(row_info)
        workbook.save(self.__case_script_list_path)
        log.info("write excel file %s success" % self.__case_script_list_path)
        return self.__case_script_list_path
