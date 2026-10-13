# -*- encoding=utf8 -*-
import os
import sys

FRAMEWORK_DIR = "framework"
BIZ_DIR = "biz"
LIBS_DIR = "libs"
SCRIPTS_DIR = 'scripts'

# 将framework信息添加到系统环境变量中
cur_path = os.path.abspath(os.path.dirname(__file__))
root_path = os.path.split(cur_path)[0]
sys.path.append(root_path)
framework_path = os.path.join(root_path, FRAMEWORK_DIR)
sys.path.append(framework_path)

# 将biz的路径信息添加到系统环境变量中
biz_path = os.path.join(framework_path, BIZ_DIR)
sys.path.append(biz_path)

# 将libs的路径信息添加到系统环境变量中
libs_path = os.path.join(framework_path, LIBS_DIR)
sys.path.append(libs_path)

# 将scripts目录添加到环境变量
scripts_path = os.path.join(root_path, SCRIPTS_DIR)
sys.path.append(scripts_path)
