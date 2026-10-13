# -*- encoding=utf8 -*-
"""
author: DuPanPan
date: 2020-04-29
description: 提供与jenkins交互的接口
             1、创建用例脚本关系集
             2、创建env_config.xml文件的方法
"""
from biz.classes.case_script_map import CaseScriptMap
from biz.classes.config_file_manager import ConfigManager


def case_script_list_create(script_case_list: list) -> str:
    """
    author: DuPanPan
    date: 2020-04-29
    description: 调用创建用例脚本关系集的方法
    :param: script_case_rel_list：用例脚本关系集字典列表
    :return: 脚本用例关系列表文件路径
    """
    case_script_map = CaseScriptMap()
    case_script_rel_list_file_path = case_script_map.case_script_file_create(script_case_list)
    return case_script_rel_list_file_path


def env_config_file_create(env_config_dict: dict) -> None:
    """
    author: DuPanPan
    date: 2020-04-27
    description: 调用创建env_config.xml文件的方法
    :param: env_config_dict: 配置参数字典
    :return:无返回值
    """
    config_manager = ConfigManager.get_config_manager_object()
    config_manager.env_file_create(env_config_dict)


def ip_config_dict_get(host_location_str, jenkins_server_ip_str) -> dict:
    """
    author: DuPanPan
    date: 2020.10.29
    description:获取ip字典
    :return:返回ip字典
    """
    config_manager = ConfigManager.get_config_manager_object()
    ip_dict = config_manager.server_ips_dict_get(host_location_str, jenkins_server_ip_str)
    return ip_dict
