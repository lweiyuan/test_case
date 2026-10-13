#!/usr/bin/python3
# -*- encoding=utf8 -*-

"""
author:    zanzan.feng
date  :    2021/4/3
description:
"""
import os
import random
import time
import re
import xlrd

from base import scripts_generate


class GenerateScripts:

    @classmethod
    def __init__(cls, xlsx_filename, xlsx_sheet_name):
        cls.xlsx_filename = xlsx_filename
        cls.xlsx_sheet_name = xlsx_sheet_name

    @classmethod
    def create_file(cls, filename, contents):
        # 创建脚本文件
        print(filename)
        with open(filename, "w", encoding='utf-8', newline="\n") as f:
            f.write(contents)

    @classmethod
    def generate_scripts(cls):
        path = os.path.dirname(cls.xlsx_filename)
        if os.path.isfile(cls.xlsx_filename) and os.path.exists(cls.xlsx_filename):
            pass
        else:
            print("路径错误")

        workbook = xlrd.open_workbook(cls.xlsx_filename)
        sheet = workbook.sheet_by_name(cls.xlsx_sheet_name)
        # 过滤标题
        for i in range(1, sheet.nrows):
            data_line = sheet.row_values(i)
            params = data_line[1]
            print(params)

            scripts_name = path + os.sep + data_line[6].replace('/', '\\')
            # 创建目录
            os.makedirs(os.path.dirname(scripts_name), exist_ok=True)

            base_all = scripts_generate % (data_line[0],  # 测试编号
                                           data_line[1],  # 测试标题
                                           data_line[15], # 测试场景
                                           data_line[12], # 检查点
                                           data_line[10], # 测试步骤
                                           data_line[1],  # 用例标题
                                                )

            cls.create_file(scripts_name, base_all)


gs = GenerateScripts(r"D:\lihr\ps3code\ps3\test\esat\nic100\scripts\generate_scripts.xlsx", "Sheet1")

gs.generate_scripts()
