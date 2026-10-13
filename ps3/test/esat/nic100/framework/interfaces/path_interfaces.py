# -*- encoding=utf8 -*-
import os
import sys

FRAMEWORK_DIR = "framework"
# 将framework信息添加到系统环境变量中
cur_path = os.path.abspath(os.path.dirname(__file__))
root_path = os.path.split(cur_path)[0]
sys.path.append(root_path)
framework_path = os.path.join(root_path, FRAMEWORK_DIR)
sys.path.append(framework_path)
