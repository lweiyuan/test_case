#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
description: 将项目根目录/framework/scripts/nic 目录加入 sys.path。
             逻辑与 scripts/add_syspath.py 保持一致（自动推导 NIC 目录名）。
"""
import os
import sys

# 获取当前文件所在目录
cur_path = os.path.abspath(os.path.dirname(__file__))

# 向上查找 ps3/test/esat 根目录
root_path = cur_path
while True:
    if root_path.endswith('test/esat') or root_path.endswith('test\\esat'):
        break
    parent = os.path.dirname(root_path)
    if parent == root_path:
        raise ValueError('未找到 test/esat 根目录')
    root_path = parent

# 自动推导 NIC 目录名（如 nic100），即 root_path 下承载 scripts 的那一层
NIC_DIR = os.path.relpath(cur_path, root_path).split(os.sep)[0]
FRAMEWORK_DIR = os.path.join(NIC_DIR, 'framework')
SCRIPTS_DIR = os.path.join(NIC_DIR, 'scripts')

for _p in (
    root_path,
    os.path.join(root_path, FRAMEWORK_DIR),
    os.path.join(root_path, SCRIPTS_DIR),
    os.path.join(root_path, NIC_DIR),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)
