# -*- encoding=utf8 -*-
from libs import constants
from scripts.script_libs import log


class TestEnvironment(object):
    """
    author: luyafei
    date  : 2020.04.22
    description: 描述测试环境字段信息
    """

    def __init__(self):
        # 项目名称
        self.project_id = ""
        # 代码分支
        self.git_branch = ""
        # 代码分支版本（commit id）
        self.git_branch_version = ""
        # 测试任务ID
        self.task_id = constants.DEFAULT_ENV_TASK_ID
        # 测试任务名称
        self.task_name = ""
        # 影响版本
        self.opened_build = constants.DEFAULT_ENV_OPENED_BUILD
        # 创建者
        self.opened_by = constants.DEFAULT_ENV_OPENED_BY
        # 测试阶段
        self.test_phase = ""
        # 产品id
        self.product_id = constants.DEFAULT_ENV_PRODUCT_ID
        # host 宿主机ip
        self.host_ip = ""
        # 操作系统
        self.host_os = ""
        # 芯片类型
        self.host_cpu = ""
        # 背板
        self.backplane = ""
        # 测试平台
        self.test_platform = ""

    """
    TestEnvironment类中各字段信息的set方法
    """
    def set_project_id(self, project_id: str) -> None:
        self.project_id = project_id

    def set_git_branch(self, git_branch: str) -> None:
        self.git_branch = git_branch

    def set_git_branch_version(self, git_branch_version: str) -> None:
        self.git_branch_version = git_branch_version

    def set_task_id(self, task_id: int) -> None:
        if task_id == "":
            task_id = constants.DEFAULT_ENV_TASK_ID
        self.task_id = task_id

    def set_task_name(self, task_name: str) -> None:
        self.task_name = task_name

    def set_opened_build(self, opened_build: str) -> None:
        if opened_build == "":
            opened_build = constants.DEFAULT_ENV_OPENED_BUILD
        self.opened_build = opened_build

    def set_opened_by(self, opened_by: str) -> None:
        if opened_by == "":
            opened_by = constants.DEFAULT_ENV_OPENED_BY
        self.opened_by = opened_by

    def set_test_phase(self, test_phase: str) -> None:
        self.test_phase = test_phase

    def set_product_id(self, product_id: str) -> None:
        if product_id == "":
            product_id = constants.DEFAULT_ENV_PRODUCT_ID
        self.product_id = product_id

    def set_host_ip(self, host_ip: str) -> None:
        self.host_ip = host_ip

    def set_host_qemu_ip(self, host_qemu_ip: str) -> None:
        """
        author:      haibin.xu
        date:        2021-05-14 10:04:54
        description: 设置host 节点 ip

        :param host_qemu_ip: 待要设置的host 节点ip
        :return:     None
        """
        self.host_qemu_ip = host_qemu_ip

    def set_soc_ip(self, soc_ip: str) -> None:
        self.soc_ip = soc_ip

    def set_soc_qemu_ip(self, soc_qemu_ip: str) -> None:
        """
        author:      haibin.xu
        date:        2021-05-14 10:03:01
        description: 设置soc 节点 ip

        :param soc_qemu_ip: 待要设置的soc 节点ip
        :return:     None
        """
        self.soc_qemu_ip = soc_qemu_ip

    def set_host_os(self, host_os: str) -> None:
        if host_os == "":
            host_os = constants.DEFAULT_ENV_HOST_OS
        self.host_os = host_os

    def set_host_cpu(self, host_cpu: str) -> None:
        self.host_cpu = host_cpu

    def set_backplane(self, back_plane: str) -> None:
        self.backplane = back_plane

    def set_test_platform(self, test_platform: str) -> None:
        self.test_platform = test_platform

    def keys(self) -> tuple:
        """
        author: luyafei
        date  : 2020.04.22
        description: 当对实例化对象使用dict(obj)的时候, 会调用这个方法,这里定义了字典
                     的键,其对应的值将以obj['name']的形式取, 但是对象是不可以以这种
                     方式取值的, 为了支持这种取值, 可以为类增加一个方法
        :return: 该环境字段信息类的类变量
        """
        return constants.ENV_PROJECT_NAME, constants.ENV_GIT_BRANCH, constants.ENV_GIT_BRANCH_VERSION, \
            constants.ENV_TASK_ID, constants.ENV_TASK_NAME, constants.ENV_OPENED_BUILD, constants.ENV_OPENED_BY, \
            constants.ENV_TEST_PHASE, constants.ENV_PRODUCT_ID, constants.ENV_HOST_IP, \
            constants.ENV_HOST_OS, constants.ENV_HOST_CPU, constants.ENV_BACKPLANE, \
            constants.ENV_TEST_PLATFORM

    def __getitem__(self, item: str) -> object:
        """
        author: luyafei
        date  : 2020.04.22
        description: 内置方法, 当使用obj['name']的形式的时候, 将调用这个方法,
                     这里返回的结果就是属性对应的值
        :param item: 属性名称
        :return: 属性对应的值
        """
        return getattr(self, item)

    def set_env_value(self, config_dict: dict, host_server_ip_dict: dict) -> None:
        """
        author: luyafei
        date  : 2020.04.22
        description: 解析config_dict中测试环境相关参数信息并赋值给当前对象
        :param host_server_ip_dict: 测试主机、ps3服务器、日志服务器ip字典信息
        :param config_dict: 解析测试配置文件得到的字典信息
        """
        if config_dict is None:
            log.error("config dict is None")
            return
        self.set_project_id(config_dict.get(constants.ENV_PROJECT_ID))
        self.set_git_branch(config_dict.get(constants.ENV_GIT_BRANCH))
        self.set_git_branch_version(config_dict.get(constants.ENV_GIT_BRANCH_VERSION))
        self.set_task_id(config_dict.get(constants.ENV_TASK_ID))
        self.set_task_name(config_dict.get(constants.ENV_TASK_NAME))
        self.set_opened_build(config_dict.get(constants.ENV_OPENED_BUILD))
        self.set_opened_by(config_dict.get(constants.ENV_OPENED_BY))
        self.set_test_phase(config_dict.get(constants.ENV_TEST_PHASE))
        self.set_product_id(config_dict.get(constants.ENV_PRODUCT_ID))
        self.set_host_os(config_dict.get(constants.ENV_HOST_OS))
        self.set_host_cpu(config_dict.get(constants.ENV_HOST_CPU))
        self.set_backplane(config_dict.get(constants.ENV_BACKPLANE))
        self.set_test_platform(config_dict.get(constants.ENV_TEST_PLATFORM))
        if host_server_ip_dict is None:
            log.error("host server ip dict is None")
            return
        server_ip_key_list = host_server_ip_dict.keys()
        if constants.ENV_HOST_IP in server_ip_key_list:
            self.set_host_ip(host_server_ip_dict.get(constants.ENV_HOST_IP))
