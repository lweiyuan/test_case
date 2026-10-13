#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      XuHaibin
date:        2020.07.17 14:26
description:
"""
import os
import sys

if 'nt' == os.name:
    FRAMEWORK_DIR = 'nic\\framework'
    SCRIPTS_DIR = 'nic\\scripts'
else:
    FRAMEWORK_DIR = 'nic/framework'
    SCRIPTS_DIR = 'nic/scripts'

# 获取当前文件所在目录
cur_path = os.path.abspath(os.path.dirname(__file__))
# 获取根目录，即ps3/test/esat
root_path = cur_path
while True:
    if root_path.endswith('test/esat') or root_path.endswith('test\\esat'):
        break
    root_path = os.path.dirname(root_path)
# 将根目录添加到环境变量
sys.path.append(root_path)
# 将framework目录添加到环境变量
framework_path = os.path.join(root_path, FRAMEWORK_DIR)
sys.path.append(framework_path)
# 将scripts目录添加到环境变量
scripts_path = os.path.join(root_path, SCRIPTS_DIR)
sys.path.append(scripts_path)
