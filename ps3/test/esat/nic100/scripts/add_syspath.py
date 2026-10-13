#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      XuHaibin
date:        2020.07.17 14:26
description:
"""
import os
import sys

# 获取当前文件所在目录
cur_path = os.path.abspath(os.path.dirname(__file__))
# 获取根目录，即ps3/test/esat
root_path = cur_path
while True:
    if root_path.endswith('test/esat') or root_path.endswith('test\\esat'):
        break
    root_path = os.path.dirname(root_path)

# 自动推导当前 NIC 目录名（如 nic、nic100 等）
# cur_path 形如 .../ps3/test/esat/nic100/scripts
NIC_DIR = os.path.basename(os.path.dirname(cur_path))
FRAMEWORK_DIR = os.path.join(NIC_DIR, 'framework')
SCRIPTS_DIR = os.path.join(NIC_DIR, 'scripts')

# 将根目录添加到环境变量
sys.path.insert(0, root_path)
# 将framework目录添加到环境变量
framework_path = os.path.join(root_path, FRAMEWORK_DIR)
sys.path.insert(0, framework_path)
# 将scripts目录添加到环境变量
scripts_path = os.path.join(root_path, SCRIPTS_DIR)
sys.path.insert(0, scripts_path)
# 将nic目录添加到环境变量
nic_path = os.path.join(root_path, NIC_DIR)
sys.path.insert(0, nic_path)
