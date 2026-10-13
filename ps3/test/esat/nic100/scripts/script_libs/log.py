#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      haibin.xu, junfeng.he
date:        2020.07.11 13:35
description: 定义日志类
"""
import os
import sys
import logging
import datetime
import traceback
import logging.handlers

g_logger = None
g_print2console = True
g_logfile = None
LOG_MAX_BYTES = 1024 * 1024 * 100
LOG_BACKUP_COUNT = 10
RETURN_SUCCESS = 0
RETURN_FAIL = -1
# 供一般log打印时函数调用栈使用
FUNCTION_CALLED_INDEX = -3
# 供二层基类log打印时函数调用栈使用
FUNCTION_DEEPER_CALLED_INDEX = -4


class LogRecorder(object):
    """
    author:         haibin.xu
    date:           2020.07.09
    description:    该类封装了python第三方库logging模块，按照指定格式打印
    """

    def __init__(self, logfile: str):
        """
        author:         haibin.xu
        date:           2020.07.09
        description:    构造函数，formatter定义log打印格式，logger定义创建的logging模块实例
        :param logfile: 输出日志文件路径
        """
        # 指定日志输出文件
        self.logfile = logfile
        # 指定日志最大字节数
        self.log_maxbytes = LOG_MAX_BYTES
        # 自定日志文件数量，如果创建的文件数量多于此值，就删除最老的
        self.log_backup_count = LOG_BACKUP_COUNT
        # 指定logger输出格式
        # self.formatter = logging.Formatter(SpecialEnum.LOG_FORMAT.value)
        # 获取logger实例，如果参数为空则返回root logger
        self.logger = logging.getLogger(self.logfile)

    def get_logger(self) -> logging.Logger:
        """
        author:         haibin.xu
        date:           2020.07.09
        description:    获取配置完全的logging实例，相关配置包含控制台信息，log默认等级信息等
        :return:        返回已配置好的logging实例
        """
        if self.logfile is not None:
            file_handler = logging.handlers.RotatingFileHandler(self.logfile, maxBytes=int(self.log_maxbytes),
                                                                backupCount=int(self.log_backup_count),
                                                                encoding='utf-8')
            # 指定写入文件的日志的最低输出级别
            file_handler.setLevel(logging.DEBUG)
            # 添加文件日志输出
            self.logger.addHandler(file_handler)
        if g_print2console:
            # 控制台日志
            console_handler = logging.StreamHandler(sys.stdout)
            # 指定控制台输出的日志的最低输出级别
            console_handler.setLevel(logging.INFO)
            # console_handler.formatter = self.formatter
            # 添加控制台配置
            self.logger.addHandler(console_handler)

        # 指定日志的最低输出级别
        self.logger.setLevel(logging.DEBUG)

        return self.logger


def init(log_file: str = None, print2console: bool = True) -> None:
    """
    author:                 haibin.xu
    date  :                 2020.07.11
    description:            初始化日志模块，创建logger实例，赋给全局变量g_logger
    :param log_file:        日志保存的文件名，如果为空，则不生成日志文件
    :param print2console:   控制台输出log开关
    :return:                无返回值
    """
    global g_logger
    global g_print2console
    global g_logfile
    g_print2console = print2console
    g_logfile = log_file
    if g_logger:
        # 去掉未初始化时创建的logger对象中的handler,否则会出现log的重复打印
        handlers_list = g_logger.handlers
        for handler in handlers_list[:]:
            g_logger.removeHandler(handler)
    g_logger = LogRecorder(log_file).get_logger()


def __check_logger() -> None:
    """
    author:                 haibin.xu
    date  :                 2020.07.21
    description:            检查全局变量g_logger是否已经赋值，没有的话，调用init，初始化，g_logger，此种情况下，log只输出到控制台
    :return:                无返回值
    """
    global g_logger
    if not g_logger:
        init()


def __find_caller_info() -> tuple:
    """
    author:                 haibin.xu
    date  :                 2020.07.21
    description:            通过函数调用栈信息，获取调用info、debug、warning、error、critical等方法的主调函数信息，包括主调函数所在
                            的模块，行号，函数名
    :return:                返回主调函数的模块，行号，函数名
    """
    stack = traceback.extract_stack()[FUNCTION_CALLED_INDEX]
    module_name = stack.filename.replace('/', os.sep).split(os.sep)[-1]
    return module_name, stack.lineno, stack.name


def __find_deeper_caller_info(level: int = -1) -> tuple:
    """
    author:                 junfeng.he
    date  :                 2020.08.17
    description:            通过函数调用栈信息，获取调用info、debug、warning、error、critical等方法的主调函数信息，包括主调函数所在
                            的模块，行号，函数名
    :return:                返回主调函数的模块，行号，函数名
    """
    if len(traceback.extract_stack()) >= abs(FUNCTION_CALLED_INDEX + level):
        stack = traceback.extract_stack()[FUNCTION_CALLED_INDEX + level]
    else:
        stack = traceback.extract_stack()[FUNCTION_DEEPER_CALLED_INDEX]
    module_name = stack.filename.replace('/', os.sep).split(os.sep)[-1]
    return module_name, stack.lineno, stack.name


def __get_format_msg(msg: str, module_name: str, line_num: int, func_name: str, level_name: str,
                     format_flag: bool = True, pre_add_line: bool = False) -> str:
    """
    author:                 haibin.xu
    date  :                 2020.07.21
    description:            格式化输出信息
    :param msg:             待打印的log信息
    :param module_name:     主调函数所在的模块名
    :param line_num:        主调函数调用打印log的行号
    :param func_name:       主调函数名
    :param level_name:      log输出等级
    :param format_flag:     是否对输出信息进行格式化
    :param pre_add_line:    是否需要在前面添加换行符
    :return:                返回格式化后的log信息
    """
    new_line = '\n' if pre_add_line else ''

    if format_flag:
        asctime = datetime.datetime.now().strftime('%y-%m-%d %H:%M:%S')
        formatter_msg = '{}[{}] {:25s} {:20s} {:4s} {:8s}: {}'.format(
            new_line, asctime, module_name, func_name, str(line_num), level_name, msg)
    else:
        formatter_msg = new_line + msg

    return formatter_msg


def debug(msg: str) -> None:
    """
    author:         haibin.xu
    date  :         2020.07.11
    description:    以debug等级输出日志信息
    :param msg:     要输出的日志信息
    """
    __check_logger()
    module_name, line_num, func_name = __find_caller_info()
    formatter_msg = __get_format_msg(msg, module_name, line_num, func_name, 'DEBUG')
    g_logger.debug(formatter_msg)


def debug_caller(msg: str, level: int=-1) -> None:
    """
    author:         junfeng.he
    date  :         2020.08.17
    description:    以debug等级输出日志信息
    :param msg:     要输出的日志信息
    """
    __check_logger()
    module_name, line_num, func_name = __find_deeper_caller_info(level)
    formatter_msg = __get_format_msg(msg, module_name, line_num, func_name, 'DEBUG')
    g_logger.debug(formatter_msg)


def info(msg: str, format_flag: bool = True, pre_add_line: bool = False) -> None:
    """
    author:         haibin.xu
    date  :         2020.07.11
    description:    以info等级输出日志信息，一般信息打印输出
    :param msg:     要输出的日志信息
    :param format_flag: 是否对输出信息进行格式化
    :param pre_add_line: 是否需要在前面添加换行符
    """
    __check_logger()
    module_name, line_num, func_name = __find_caller_info()
    formatter_msg = __get_format_msg(msg, module_name, line_num, func_name, 'INFO', format_flag, pre_add_line)
    g_logger.info(formatter_msg)


def skip(caller_class: object, msg) -> None:
    """
    author:         haibin.xu
    date  :         2020.07.11
    description:    以error等级输出日志信息，一般信息打印输出, 该方法用在用例脚本环境检查阶段使用，caller_class 一定是script_base或其子类
    :param msg:     要输出的日志信息
    :param format_flag: 是否对输出信息进行格式化
    :param func_called_idx: 指定函数调用栈索引
    """
    caller_class.skip_message = msg
    __check_logger()
    module_name, line_num, func_name = __find_caller_info()
    formatter_msg = __get_format_msg(msg, module_name, line_num, func_name, 'ERROR')
    g_logger.error(formatter_msg)

def info2file(msg: str, file_path: str) -> None:
    """
    author:      haibin.xu
    date:        2021-06-08 10:19:40
    description: 打印日志到指定文件

    :param msg:  待要保存的日志
    :param file_path: 保存日志的文件路径
    :return:     None
    """
    module_name, line_num, func_name = __find_caller_info()
    formatter_msg = __get_format_msg(msg, module_name, line_num, func_name, 'INFO')
    with open(file_path, 'a+') as fp:
        fp.write(formatter_msg)


def info_caller(msg: str, level: int = -1, pre_add_line: bool = False) -> None:
    """
    author:         junfeng.he
    date  :         2020.08.17
    description:    以info等级输出日志信息，一般信息打印输出
    :param msg:     要输出的日志信息
    :param pre_add_line: 是否需要在前面添加换行符
    """
    __check_logger()
    module_name, line_num, func_name = __find_deeper_caller_info(level)
    formatter_msg = __get_format_msg(msg, module_name, line_num, func_name, 'INFO', pre_add_line=pre_add_line)
    g_logger.info(formatter_msg)


def warning(msg: str) -> None:
    """
    author:         haibin.xu
    date  :         2020.07.11
    description:    以warning等级输出日志信息，警告信息输出，如没有配置文件输出路径，从而使用默认输出路径这种情况就可以使用警告等级
    :param msg:     要输出的日志信息
    """
    __check_logger()
    module_name, line_num, func_name = __find_caller_info()
    formatter_msg = __get_format_msg(msg, module_name, line_num, func_name, 'WARNING')
    g_logger.warning(formatter_msg)


def warning_caller(msg: str, level: int=-1) -> None:
    """
    author:         junfeng.he
    date  :         2020.08.17
    description:    以warning等级输出日志信息，警告信息输出，如没有配置文件输出路径，从而使用默认输出路径这种情况就可以使用警告等级
    :param msg:     要输出的日志信息
    """
    __check_logger()
    module_name, line_num, func_name = __find_deeper_caller_info(level)
    formatter_msg = __get_format_msg(msg, module_name, line_num, func_name, 'WARNING')
    g_logger.warning(formatter_msg)


def exception(msg: str) -> None:
    """
    author:      haibin.xu
    date:        2021-07-10 11:52:36
    description: 以error等级输出异常信息

    :param msg:  异常信息头
    :return:     None
    """
    __check_logger()
    module_name, line_num, func_name = __find_caller_info()
    formatter_msg = __get_format_msg(msg, module_name, line_num, func_name, 'ERROR')
    g_logger.exception(formatter_msg)


def error(msg: str) -> None:
    """
    author:         haibin.xu
    date  :         2020.07.11
    description:    以error等级输出日志信息，一般错误信息输出
    :param msg:     要输出的日志信息
    """
    __check_logger()
    module_name, line_num, func_name = __find_caller_info()
    formatter_msg = __get_format_msg(msg, module_name, line_num, func_name, 'ERROR')
    g_logger.error(formatter_msg)


def error_caller(msg: str, level: int=-1) -> None:
    """
    author:         junfeng.he
    date  :         2020.08.17
    description:    以error等级输出日志信息，一般错误信息输出
    :param msg:     要输出的日志信息
    """
    __check_logger()
    module_name, line_num, func_name = __find_deeper_caller_info(level)
    formatter_msg = __get_format_msg(msg, module_name, line_num, func_name, 'ERROR')
    g_logger.error(formatter_msg)


def critical(msg: str) -> None:
    """
    author:         haibin.xu
    date  :         2020.07.11
    description:    以critical等级输出日志信息， critical为严重错误输出
    :param msg:     要输出的日志信息
    """
    __check_logger()
    module_name, line_num, func_name = __find_caller_info()
    formatter_msg = __get_format_msg(msg, module_name, line_num, func_name, 'CRITICAL')
    g_logger.critical(formatter_msg)


def critical_caller(msg: str, level: int=-1) -> None:
    """
    author:         junfeng.he
    date  :         2020.08.17
    description:    以critical等级输出日志信息，critical为严重错误输出
    :param msg:     要输出的日志信息
    """
    __check_logger()
    module_name, line_num, func_name = __find_deeper_caller_info(level)
    formatter_msg = __get_format_msg(msg, module_name, line_num, func_name, 'CRITICAL')
    g_logger.critical(formatter_msg)


def attach_test_steps_info(caller_class: type, msg: str) -> None:
    """
    author:      haibin.xu
    date:        2020-12-29 16:35:43
    description: 打印并且添加测试步骤信息

    :param caller_class: 调用类
    :param msg:  待打印并且添加的信息
    :return:     无返回值
    """
    info_caller(msg)
    if 'test_steps' in dir(caller_class):
        caller_class.test_steps += msg
    else:
        error('Not find property "test_steps" in class: {}.'.format(caller_class))


def get_log_file() -> str or None:
    """
    author:                 kaifeng.bi
    date  :                 2021.11.20
    description:            获取日志文件
    :return:                str
    """
    global g_logfile
    return g_logfile
