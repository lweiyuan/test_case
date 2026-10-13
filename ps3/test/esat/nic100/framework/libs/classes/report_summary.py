# -*- encoding=utf8 -*-
from libs import constants


class ReportSummary(object):
    """
    author: luyafei
    date  : 2020.04.24
    descriptor: 测试报告概要信息字段
    """
    pass_num = 0
    fail_num = 0
    skip_num = 0
    not_exist_num = 0

    def __init__(self):
        # 任务名称
        self.task_name = ""
        # 代码分支
        self.git_branch = ""
        # 测试安装包
        self.package_path = ""
        # 测试用例路径
        self.case_path = ""
        # 用例级别
        self.case_level = ""
        # 测试总时长
        self.total_duration = ""
        # 通过测试脚本数目
        self.pass_num = 0
        # 失败测试脚本数目
        self.fail_num = 0
        # 跳过测试脚本数目
        self.skip_num = 0
        # 不存在的测试脚本数目
        self.not_exist_num = 0
        # 测试服务器ip
        self.host_ip = ""
        self.ioc_ip = ""
        # 测试主机os
        self.host_os = ""
        # 测试平台
        self.test_platform = ""

    """
    ReportSummary类中各字段信息的set方法
    """

    def set_task_name(self, task_name: str) -> None:
        self.task_name = task_name

    def set_git_branch(self, git_branch: str) -> None:
        self.git_branch = git_branch

    def set_package_path(self, package_path: str) -> None:
        self.package_path = package_path

    def set_case_path(self, case_path: str) -> None:
        self.case_path = case_path

    def set_case_level(self, case_level: str) -> None:
        self.case_level = case_level

    def set_total_duration(self, total_duration: int) -> None:
        self.total_duration = total_duration

    def set_pass_num(self, pass_num: int) -> None:
        self.pass_num = pass_num

    def set_fail_num(self, fail_num: int) -> None:
        self.fail_num = fail_num

    def set_skip_num(self, skip_num: int) -> None:
        self.skip_num = skip_num

    def set_not_exist_num(self, not_exist_num: int) -> None:
        self.not_exist_num = not_exist_num

    def set_x86_ip(self, host_ip: str) -> None:
        self.host_ip = host_ip

    def set_arm_ip(self, ioc_ip: str) -> None:
        self.ioc_ip = ioc_ip

    def set_host_os(self, host_os: str) -> None:
        self.host_os = host_os

    def set_test_platform(self, test_platform: str) -> None:
        self.test_platform = test_platform

    def keys(self) -> tuple:
        """
        author: luyafei
        date  : 2020.04.24
        description: 当对实例化对象使用dict(obj)的时候, 会调用这个方法,这里定义了
                     字典的键, 其对应的值将以obj['name']的形式取, 但是对象是不可以
                     以这种方式取值的, 为了支持这种取值, 可以为类增加一个方法
        :return: 该环境字段信息类的类变量
        """
        return constants.REPORT_ATTR_TASK_NAME, constants.REPORT_ATTR_GIT_BRANCH, \
            constants.REPORT_ATTR_PACKAGE_PATH, constants.REPORT_ATTR_CASE_PATH, constants.REPORT_ATTR_CASE_LEVEL, \
            constants.REPORT_ATTR_TOTAL_DURATION, constants.REPORT_ATTR_PASS_NUM, constants.REPORT_ATTR_FAIL_NUM, \
            constants.REPORT_ATTR_SKIP_NUM, constants.REPORT_ATTR_NOT_EXIST_NUM, constants.REPORT_ATTR_HOST_IP, \
            constants.REPORT_ATTR_IOC_IP, constants.REPORT_ATTR_HOST_OS, constants.REPORT_ATTR_TEST_PLATFORM

    def __getitem__(self, item: str) -> object:
        """
        author: luyafei
        date  : 2020.04.24
        description: 内置方法, 当使用obj['name']的形式的时候, 将调用这个方法,
                     这里返回的结果就是变量对应的值
        :param item: 属性名称
        :return: 属性对应的值
        """
        return getattr(self, item)
