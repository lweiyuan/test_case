#!/usr/bin/python3
# -*- encoding=utf8 -*-

import sys

import add_syspath
from framework.biz.classes.config_file_manager import ConfigManager
from scripts.script_libs import log

"""
author: DuPanPan
date: 2020.04.27
description: 提供对外进行创建配置文件env_config.xml
"""
if __name__ == '__main__':
    # 获取第二个参数，第一个参数是脚本名称
    if len(sys.argv) < 2:
        log.error("Parameter is error!")
        exit(1)
    env_config_info = sys.argv[1]
    config_xml_manager = ConfigManager.get_config_manager_object()
    config_xml_manager.env_file_create(env_config_info)
