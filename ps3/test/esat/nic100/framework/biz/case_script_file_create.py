#!/usr/bin/python3
# -*- encoding=utf8 -*-
import sys

import add_syspath
from framework.biz.classes.case_script_map import CaseScriptMap
from scripts.script_libs import log

"""
author: DuPanPan
date: 2020.04.29
description: 提供对外进行创建用例关系集文件的接口
"""

if __name__ == '__main__':
    # 获取执行脚本时传参的用例脚本关系列表，
    # python3 -u case_script_file.py case_script_list
    if len(sys.argv) < 2:
        log.error("Parameter is error!")
        exit(1)
    case_script_list = sys.argv[1]
    case_script_map = CaseScriptMap()
    case_script_file_path = case_script_map.case_script_file_create(case_script_list)
    print(case_script_file_path)
