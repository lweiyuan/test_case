# -*- encoding=utf8 -*-
from libs import constants
from libs.classes.test_case import TestCase
from libs.classes.test_environment import TestEnvironment


class Result(object):
    """
    author: luyafei
    date  : 2020.04.24
    descriptor: 记录脚本执行的结果字段信息
    @changelog:     sunql
                1、增加cli_result_max_time属性及set方法
    """

    def __init__(self):
        # 测试用例信息
        self.test_case_object = None
        # 脚本测试结果
        self.script_result = ""
        # 脚本开始执行时间
        self.start_time = ""
        # 脚本执行时长
        self.script_duration = "0.0"
        # 脚本中主要方法执行时间信息
        self.methods_time = None
        # 测试环境信息
        self.test_env_object = None
        # 脚本测试前后内存差值
        self.memtory_delta = None
        # 脚本测试期间性能数据
        self.iops = '-'
        self.bw = '-'
        self.resp_time = '-'
        self.raw_perf_data = '-'
        # 脚本cli命令最大执行时间
        self.cli_result_max_time = '-'
        self.test_platform = '-'
        self.intf_med = '-'
        self.job_uuid = '-'
        self.test_platform_info = '-'

    """
    Result类中各字段信息的set方法
    """
    def set_test_case_object(self, test_case_object: object) -> None:
        self.test_case_object = test_case_object

    def set_script_result(self, script_result: str) -> None:
        self.script_result = script_result

    def set_start_time(self, start_time: str) -> None:
        self.start_time = start_time

    def set_script_duration(self, script_duration: str) -> None:
        self.script_duration = script_duration

    def set_methods_time(self, methods_time: object) -> None:
        self.methods_time = methods_time

    def set_test_env_object(self, test_env_object: object) -> None:
        self.test_env_object = test_env_object

    def set_memory_delta(self, mm_delta: int) -> None:
        self.memtory_delta = mm_delta

    def set_performance(self, iops: str = '-', bw: str = '-', resp_time: str = '-',
                        raw_perf_data: str = '-') -> None:
        self.iops = iops
        self.bw = bw
        self.resp_time = resp_time
        self.raw_perf_data = raw_perf_data

    def keys(self) -> tuple:
        """
        author: luyafei
        date  : 2020.04.24
        description: 当对实例化对象使用dict(obj)的时候, 会调用这个方法,这里定义了
                     字典的键, 其对应的值将以obj['name']的形式取,但是对象是不可以
                     以这种方式取值的, 为了支持这种取值, 可以为类增加一个方法
        :return: 该环境字段信息类的类变量
        """
        return constants.RESULT_ATTR_TEST_CASE_OBJECT, constants.RESULT_ATTR_SCRIPT_RESULT, \
            constants.RESULT_ATTR_START_TIME, constants.RESULT_ATTR_SCRIPT_DURATION, \
            constants.RESULT_ATTR_METHODS_TIME

    def __getitem__(self, item: str) -> object:
        """
        author: luyafei
        date  : 2020.04.24
        description: 内置方法, 当使用obj['name']的形式的时候, 将调用这个方法,
                     这里返回的结果就是属性对应的值
        :param item: 属性名称
        :return: 属性对应的值
        """
        return getattr(self, item)

    def set_case_values(self, case_dict: dict) -> None:
        """
        author: panpan.du
        date  : 2020.10.08
        description: 填写用例信息
        :param case_dict: 用例信息字典
        :return: 无返回值
        """
        test_case = TestCase()
        test_case.set_test_case_value(case_dict)
        self.set_test_case_object(test_case)

    def set_common_values(self, config_dict, server_ip_dict) -> None:
        """
        author: panpan.du
        date  : 2020.10.10
        description: 填写用例信息
        :param config_dict: 环境配置信息字典
        :param server_ip_dict: 服务器ip字典
        :return: 无返回值
        """
        test_env_object = TestEnvironment()
        test_env_object.set_env_value(config_dict, server_ip_dict)
        self.set_test_env_object(test_env_object)

    def set_cli_result_max_time(self, cli_res_max_time: str) -> None:
        """
        description:脚本cli命令最大执行时间
        author: sunql
        :param cli_res_max_time:
        :return:
        """
        self.cli_result_max_time = cli_res_max_time

    def set_test_platform(self, test_platform: str) -> None:
        """
        description:设置测试环境
        author: sunql
        :param test_platform:
        :return:
        """
        self.test_platform = test_platform

    def set_intf_med(self, intf_med: str) -> None:
        """
        description:设置测试用到的磁盘介质接口
        author: sunql
        :param intf_med:
        :return:
        """
        self.intf_med = intf_med

    def set_job_uuid(self, job_uuid: str) -> None:
        """
        description:设置本次测试唯一标识
        author: sunql
        :param job_uuid:
        :return:
        """
        self.job_uuid = job_uuid

    def set_test_platform_info(self, test_platform_info: str) -> None:
        """
        description:设置测试环境
        author: sunql
        :param test_platform:
        :return:
        """
        self.test_platform_info = test_platform_info
