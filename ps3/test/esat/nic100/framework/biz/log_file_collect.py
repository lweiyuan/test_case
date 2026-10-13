#!/usr/bin/python3
# -*- encoding=utf8 -*-
import argparse

import add_syspath
from biz.log_collect import LogCollect

"""
author: DuPanPan
date: 2020.09.30
description: 提供对外进行收集日志的命令
"""


def arg_parse():
    """
    author: panpan.du
    date  : 2020.09.30
    description: 解析脚本参数
    :return: 参数选项的数据信息
    """
    # 以下是输入参数选项的信息
    parser = argparse.ArgumentParser(description="test Test.")
    # 添加命令行参数中的 ip选项，为必选项，当没有给定ip时，argparse标准库会自动报错
    parser.add_argument('-ip', '--host_ip', required=True, type=str)
    # 添加命令行参数中的 logip选项，为必选项，当没有给定ip时，argparse标准库会自动报错
    parser.add_argument('-logip', '--log_server_ip', required=True, type=str)
    # 添加命令行参数中的 port选项，为可选项，默认为22
    parser.add_argument('-p', '--port', default=None, type=int)
    # 添加命令行参数中的ioc ip选项,为可选项，默认None
    parser.add_argument('-ioc', '--ioc_ip', default=None, type=str)
    # 添加命令行参数中的 ioc port选项，为可选项，默认为22
    parser.add_argument('-iocp', '--ioc_port', default=None, type=int)
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    # 获取第二个参数，第一个参数是脚本名称
    # 解析输入的参数选项信息
    input_options = arg_parse()
    log_collect_manager = LogCollect()
    log_collect_manager.collect_log_command(input_options.host_ip, input_options.port,  input_options.ioc_ip,
                                            input_options.ioc_port, input_options.log_server_ip)
