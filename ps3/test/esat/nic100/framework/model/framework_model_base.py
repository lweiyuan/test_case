#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      sunql
description: 测试项目框架基类
"""
from framework.libs import constants, utils_new as utils


class FrameworkModelBase(object):
    test_stop_code_list = [constants.RETURN_CODE_FAIL, constants.RETURN_CODE_TIMEOUT]
    frame_run_dict = None

    @classmethod
    def get_project_parameters(cls, frame_run_dict: dict) -> None:
        """
        获取测试项目参数
        :return:
        """
        cls.frame_run_dict = frame_run_dict
        raise Exception('please implements get_project_parameters()')

    @classmethod
    def brefore_test(cls) -> None:
        """
        测试前操作
        :return:
        """
        raise Exception('please implements brefore_test()')

    @classmethod
    def after_test(cls) -> None:
        """
        测试后操作
        :return:
        """
        raise Exception('please implements after_test()')

    @classmethod
    def after_test_round(cls) -> None:
        """
        每轮测试后操作
        :return:
        """
        raise Exception('please implements after_test_round()')

    @classmethod
    def before_exec_script(cls) -> None:
        """
        每个用例执行前操作
        :return:
        """
        raise Exception('please implements before_exec_script()')

    @classmethod
    def after_exec_script(cls) -> None:
        """
        每个用例执行后操作
        :return:
        """
        raise Exception('please implements before_exec_script()')

    @classmethod
    def check_bug_stop(cls, script_rtn_code):
        """
        每个用例执行后 判断是否停止测试
        :param script_rtn_code:
        :return:
        """
        return script_rtn_code in cls.test_stop_code_list

    @classmethod
    def after_check_bug(cls) -> None:
        """
        每个用例执行后 判断是否停止测试后 判断是否停止测试操作
        :return:
        """
        raise Exception('please implements after_check_bug()')

    @classmethod
    def create_result_object(cls, frame_run_dict: dict) -> object:
        """
        创建结果对象
        :param frame_run_dict
        :return:
        """
        return utils.make_result_object(frame_run_dict.get('start_time', ''),
                                        frame_run_dict.get('time_duration', ''),
                                        frame_run_dict.get('memory_delta', ''),
                                        frame_run_dict.get('test_platform', ''),
                                        frame_run_dict.get('test_platform_info', ''),
                                        )
