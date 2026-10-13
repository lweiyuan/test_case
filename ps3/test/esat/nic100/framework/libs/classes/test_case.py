# -*- encoding=utf8 -*-
from libs import constants


class TestCase(object):
    """
    author: luyafei
    date  : 2020.04.22
    description: 描述测试用例字段信息
    """

    def __init__(self):
        self.case_id = ""
        self.case_title = ""
        self.case_version = ""
        self.case_type = ""
        self.script_path = ""
        self.branch_id = constants.DEFAULT_ZEN_CASE_SCRIPT_BRANCH_ID
        self.module_id = constants.DEFAULT_ZEN_CASE_SCRIPT_MODULE_ID
        self.module_name = ""

    """
    TestCase类中各字段信息的set方法
    """
    def set_case_id(self, case_id: str) -> None:
        self.case_id = case_id

    def set_case_title(self, case_title: str) -> None:
        self.case_title = case_title

    def set_case_version(self, case_version: str) -> None:
        self.case_version = case_version

    def set_case_type(self, case_type: str) -> None:
        self.case_type = case_type

    def set_script_path(self, script_path: str) -> None:
        self.script_path = script_path

    def set_branch_id(self, branch_id: str) -> None:
        self.branch_id = branch_id

    def set_module_id(self, module_id: str) -> None:
        self.module_id = module_id

    def set_module_name(self, module_name: str) -> None:
        self.module_name = module_name

    def keys(self) -> tuple:
        """
        author: luyafei
        date  : 2020.04.22
        description: 当对实例化对象使用dict(obj)的时候, 会调用这个方法,这里定义了字典
                     的键, 其对应的值将以obj['name']的形式取,但是对象是不可以以这种
                     方式取值的, 为了支持这种取值, 可以为类增加一个方法
        :return: 该环境字段信息类的类变量
        """
        return constants.ZEN_CASE_SCRIPT_CASE_ID, constants.CASE_SCRIPT_CASE_VERSION, \
            constants.ZEN_CASE_SCRIPT_SCRIPT_LOCATION, constants.ZEN_CASE_SCRIPT_BRANCH_ID, \
            constants.ZEN_CASE_SCRIPT_MODULE_ID, constants.ZEN_CASE_SCRIPT_MODULE_NAME

    def __getitem__(self, item: str) -> object:
        """
        author: luyafei
        date  : 2020.04.22
        description: 内置方法, 当使用obj['name']的形式的时候, 将调用这个方法,
                     这里返回的结果就是变量对应的值
        :param item:
        """
        return getattr(self, item)

    def set_test_case_value(self, case_dict: dict) -> None:
        """
        author: luyafei
        date  : 2020.04.22
        description: 解析case_dict中测试用例相关参数信息并赋值给当前对象
        :param case_dict: 用例字典信息
        :return:
        """
        self.set_case_id(case_dict.get(constants.CASE_SCRIPT_CASE_ID))
        self.set_case_title(case_dict.get(constants.CASE_SCRIPT_CASE_TITLE))
        self.set_case_version(case_dict.get(constants.CASE_SCRIPT_CASE_VERSION))
        self.set_case_type(case_dict.get(constants.CASE_SCRIPT_CASE_TYPE))
        self.set_script_path(case_dict.get(constants.CASE_SCRIPT_SCRIPT_LOCATION))
        self.set_branch_id(case_dict.get(constants.CASE_SCRIPT_BRANCH_ID))
        self.set_module_id(case_dict.get(constants.CASE_SCRIPT_MODULE_ID))
        self.set_module_name(case_dict.get(constants.CASE_SCRIPT_MODULE_NAME))
