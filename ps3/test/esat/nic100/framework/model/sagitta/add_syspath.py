#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      haibin.xu
date:        2021.02.03 15:16
@summary:    添加环境变量

@changelog      2021-02-03 15:17:41  haibin.xu
                1. 调整脚本名称，保持与测试用例脚本一致，path_framwork.py -> add_syspath.py
                2. 添加相应注释信息
"""
import os
import sys


SCRIPTS_DIR = 'scripts'
FRAMEWORK_DIR = 'framework'

# 获取当前文件所在目录
cur_path = os.path.abspath(os.path.dirname(__file__))
# 获取根目录，即ps3/test/esat
root_path = os.path.dirname(cur_path)
# 将根目录添加到环境变量
sys.path.append(root_path)

# 将framework目录添加到环境变量
framework_path = os.path.join(root_path, FRAMEWORK_DIR)
sys.path.append(framework_path)

# 将scripts目录添加到环境变量
scripts_path = os.path.join(root_path, SCRIPTS_DIR)
sys.path.append(scripts_path)
