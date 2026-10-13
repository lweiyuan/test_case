# -*- encoding=utf8 -*-
from libs import constants
from libs.classes.test_environment import TestEnvironment
from libs.classes.test_case import TestCase


class Bug(object):
    """
    author: luyafei
    date  : 2020.04.22
    description: 脚本测试结果字段信息
    """

    def __init__(self):
        # 问题名称
        self.title = ""
        # 问题类型, type在python中是方法名
        self.type_name = ""
        # 测试工具
        self.test_tool = ""
        # 测试条件
        self.precondition = ""
        # 复现步骤（问题描述）
        self.steps = ""
        # 日志存放路径
        self.log_path = ""

        # 发生频率
        self.frequency = constants.DEFAULT_FREQUENCY
        # 问题状态
        self.status = constants.DEFAULT_STATUS
        # 指派给
        self.assigned_to = constants.DEFAULT_ASSIGNED_TO
        # 截止日期
        self.deadline = ""
        # 禅道中问题的严重程度
        self.severity = constants.DEFAULT_SEVERITY
        # 优先级
        self.priority = constants.DEFAULT_PRIORITY

        # 配置环境类对象信息
        self.test_env_object = None
        # 测试用例类对象信息
        self.test_case_object = None
        # 测试环境信息
        self.test_platform_info = ''

    """
    Bug类中各字段信息的set方法
    """
    def set_title(self, title: str) -> None:
        self.title = title

    def set_type_name(self, type_name: str) -> None:
        self.type_name = type_name

    def set_test_tool(self, test_tool: str) -> None:
        self.test_tool = test_tool

    def set_precondition(self, precondition: str) -> None:
        self.precondition = precondition

    def set_steps(self, steps: str) -> None:
        self.steps = steps

    def set_log_path(self, log_path: str) -> None:
        self.log_path = log_path

    def set_frequency(self, frequency: str) -> None:
        self.frequency = frequency

    def set_status(self, status: str) -> None:
        self.status = status

    def set_assigned_to(self, assigned_to: str) -> None:
        self.assigned_to = assigned_to

    def set_deadline(self, deadline: str) -> None:
        self.deadline = deadline

    def set_severity(self, severity: int) -> None:
        self.severity = severity

    def set_pri(self, priority: int) -> None:
        self.priority = priority

    def set_test_env_object(self, test_env_object: object) -> None:
        self.test_env_object = test_env_object

    def set_test_case_object(self, test_case_object: object) -> None:
        self.test_case_object = test_case_object

    def keys(self) -> tuple:
        """
        author: luyafei
        date  : 2020.04.22
        description: 当对实例化对象使用dict(obj)的时候, 会调用这个方法,这里定义了字典
                     的键,其对应的值将以obj["name"]的形式取, 但是对象是不可以以这种
                     方式取值的, 为了支持这种取值, 可以为类增加一个方法
        :return: 该环境字段信息类的类变量
        """
        return constants.BUG_ATTR_BUG_TITLE, constants.BUG_ATTR_TYPE_NAME, constants.BUG_ATTR_TOOL, \
            constants.BUG_ATTR_PRECONDITION, constants.BUG_ATTR_STEPS,  constants.BUG_ATTR_LOG_PATH, \
            constants.BUG_ATTR_FREQUENCY,  constants.BUG_ATTR_STATUS, constants.BUG_ATTR_ASSIGNED_TO, \
            constants.BUG_ATTR_DEADLINE,  constants.BUG_ATTR_SEVERITY, constants.BUG_ATTR_PRIORITY, \
            constants.BUG_ATTR_LOG_PATH, constants.BUG_ATTR_ENV, constants.BUG_ATTR_CASE

    def __getitem__(self, item: str) -> object:
        """
        author: luyafei
        date  : 2020.04.22
        description: 内置方法, 当使用obj["name"]的形式的时候, 将调用这个方法,
                     这里返回的结果就是属性对应的值
        :param item: 属性名称
        :return: 属性对应的值
        """
        return getattr(self, item)

    def set_common_values(self, config_dict, server_ip_dict) -> None:
        """
        author: dupanpan
        date  : 2020.10.23
        description: 为BugFields对象的公共属性赋值（包括测试环境，测试目标，测试任务）
        :param config_dict: 环境配置参数字典
        :param server_ip_dict: 服务器ip字典
        return: 无返回
        """
        # 为测试环境字段对象赋值
        test_environment = TestEnvironment()
        test_environment.set_env_value(config_dict, server_ip_dict)
        self.set_test_env_object(test_environment)

    def set_case_values(self, case_dict: dict) -> None:
        """
        author: luyafei
        date  : 2020.04.22
        description: 填写用例信息
        :param case_dict: 用例信息字典
        :return: 无返回值
        """
        test_case = TestCase()
        test_case.set_test_case_value(case_dict)
        self.set_test_case_object(test_case)

    def set_platform_info(self, info: str) -> None:
        self.test_platform_info = info
