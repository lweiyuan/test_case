#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      junfeng.he
date:        2024.06.22 14:26
description: ---
"""
import os
import sys

FRAMEWORK_DIR = 'framework'
SCRIPTS_DIR = 'scripts'

# 获取当前文件所在目录
cur_path = os.path.abspath(os.path.dirname(__file__))
# 获取根目录，即ps3/test/esat
root_path = os.path.dirname(cur_path)
while True:
    if 'test' == os.path.basename(root_path):
        # 假设第一次遇到的 'test' 目录是所需要的 root_path
        sys.path.append(root_path)
        break
    elif root_path == '/':
        # 找到根目录, 还没遇到 'scripts' 报错退出
        raise ValueError
    else:
        # 继续向上找一级
        root_path = os.path.dirname(root_path)
        # 将根目录添加到环境变量
        sys.path.append(root_path)
# 将framework目录添加到环境变量
framework_path = os.path.join(root_path, FRAMEWORK_DIR)
sys.path.append(framework_path)
# 将scripts目录添加到环境变量
scripts_path = os.path.join(root_path, SCRIPTS_DIR)
sys.path.append(scripts_path)
print(os.getcwd())
