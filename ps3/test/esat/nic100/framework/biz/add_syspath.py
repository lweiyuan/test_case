# -*- encoding=utf8 -*-
import os
import sys

FRAMEWORK_DIR = 'framework'
SCRIPTS_DIR = 'scripts'

# 获取当前文件所在目录
cur_path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
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
