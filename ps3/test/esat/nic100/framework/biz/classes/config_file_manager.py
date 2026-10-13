# -*- encoding=utf8 -*-
import os
import ast
import xml.etree.ElementTree as ET
import re
from openpyxl import load_workbook
from itertools import islice
from scripts.script_libs import log
from framework.libs import constants
from framework.model.sagitta import constants as tj_constants


def format_value(value: str) -> object:
    """
    author:DuPanPan
    date:2020.04.28
    description: 标准化值
    :return value_format:标准化的值
    """
    value = str(value)
    if value == constants.NONE_STR or value == "":
        value_format = ""
    elif value in constants.TRUE_STR_LIST:
        value_format = True
    elif value in constants.FALSE_STR_LIST:
        value_format = False
    else:
        value = value.replace("\n", "")
        try:
            value_format = ast.literal_eval(value.strip())
        except BaseException:
            value_format = value.strip()

    return value_format


class ConfigManager(object):
    """
    author: DuPanPan
    date: 2020.04.23
    description: 管理配置XML文件（test_host_config.xml、server_common_config.xml、
                 env_config.xml）
    """

    config_manager_object = None

    def __init__(self):

        """文件路径"""
        self.test_host_file_path = ""
        self.env_file_path = ""
        self.server_common_path = ""

        """结果字典"""
        # test_host_config.xml文件解析的结果字典
        self.__test_host_dict = dict()
        # env_config.xml文件解析的结果字典
        self.__env_dict = dict()
        # 测试主机、ps3、log服务器的ip字典
        self.__ips_dict = dict()

        """解析env_config文件的标签名"""
        self.__env_fields_list = [constants.ENV_GIT_BRANCH, constants.ENV_GIT_BRANCH_VERSION,
                                  constants.ENV_PACKAGE_INSTALL, constants.ENV_PROJECT_NAME,
                                  constants.ENV_TEST_OBJECT, constants.ENV_TEST_PROJECT,
                                  constants.ENV_PACKAGE_PATH, constants.ENV_CASE_SCRIPT_LIST_PATH,
                                  constants.ENV_TASK_ID, constants.ENV_TASK_NAME, constants.ENV_JOB_ID,
                                  constants.ENV_JOB_NAME, constants.ENV_HOST_OS, constants.ENV_HOST_TYPE,
                                  constants.ENV_HOST_LABEL, constants.ENV_HOST_CPU, constants.ENV_CUSTOM_PARAMS,
                                  constants.ENV_DISK_INTERFACE, constants.ENV_DISK_MEDIUM, constants.ENV_BACKPLANE,
                                  constants.ENV_TEST_PLATFORM, constants.ENV_CASE_LEVEL, constants.ENV_TEST_ROUNDS,
                                  constants.ENV_CHIP_TYPE, constants.ENV_JENKINS_IP, constants.ENV_HOST_LOCATION,
                                  constants.ENV_TEST_SCRIPT_LIST, constants.ENV_TEST_CASE_LIST,
                                  constants.ENV_PRODUCT_ID, constants.ENV_PROJECT_ID, constants.ENV_OPENED_BUILD,
                                  constants.ENV_OPENED_BY, constants.ENV_TEST_PHASE, constants.ENV_SCRIPT_TIMEOUT,
                                  constants.ENV_TEST_ENTRY, constants.ENV_BUG_STOP,
                                  constants.ENV_PACKAGE_COMPILE, tj_constants.ENV_SWITCH_LABEL,
                                  tj_constants.EVN_SERVER_NIC_MODEL, tj_constants.EVN_CLIENT_NIC_MODEL,
                                  constants.ENV_COMPILE_OBJECT, constants.ENV_SHOW_CONSOLE_LOG,
                                  constants.ENV_GCOVER_VERSION, constants.ENV_FIREWALLD,
                                  constants.ENV_LONG_STAB_TEST, constants.ENV_CASE_LIST_ORDER,
                                  constants.ENV_RANDOM_EXEC,
                                  constants.ENV_RPM_INSTALL,
                                  constants.ENV_SKIP_QEMU_START,
                                  constants.ENV_PARAM_FROM_ZENTAO]
        self.__host_info = [constants.ENV_HOST_LABEL, constants.HOST_OWNER,
                            constants.TEST_CONFIG_SERVER_IP, constants.TEST_CONFIG_SERVER_NIC_IP,
                            constants.TEST_CONFIG_CLIENT_IP, constants.TEST_CONFIG_CLIENT_NIC_IP,
                            constants.TEST_CONFIG_SERVER_BMC_IP,
                            constants.TEST_CONFIG_SUNAME, constants.TEST_CONFIG_SUPASSWD,
                            constants.TEST_CONFIG_CLIENT_BMC_IP,
                            constants.TEST_CONFIG_CUNAME, constants.TEST_CONFIG_CUPASSWD,
                            constants.TEST_CONFIG_SERVER_COM_IP, constants.TEST_CONFIG_SERVER_COM_PORT,
                            constants.TEST_CONFIG_CLIENT_COM_IP, constants.TEST_CONFIG_CLIENT_COM_PORT]
        self.host_location_str = ""
        self.test_entry = ""
        self.test_object = ""
        self.host_label_str = ""
        self.host_type_str = ""
        self.host_cpu = ""
        self.jenkins_server_ip_str = ""
        self.parameters_from_zentao = ""

    @classmethod
    def get_config_manager_object(cls) -> config_manager_object:
        """
        author:DuPanPan
        date:2020.04.28
        description: 单例模式，返回一个对象
        :return: 返回一个配置文件管理对象
        """

        if cls.config_manager_object is None:
            cls.config_manager_object = ConfigManager()
        return cls.config_manager_object

    def __test_host_path_set(self) -> None:
        """
        author:DuPanPan
        date:2020.04.28
        description: :设置test_host_config.xml的路径
        :return: 无返回值
        """
        classes_path = os.path.dirname(os.path.abspath(__file__))
        # ..\PS3Test\framework\biz\classes
        biz_path = os.path.dirname(classes_path)
        # \PS3Test\framework\biz
        framework_path = os.path.dirname(biz_path)
        # \PS3Test\framework
        esat_path = os.path.dirname(framework_path)
        # \PS3Test

        if not self.__env_dict:
            self.__env_file_parse()

        self.test_host_file_path = os.path.join(esat_path, constants.PROJECT_DIR_CONF, self.host_location_str,
                                                self.host_type_str, self.host_label_str,
                                                constants.TEST_HOST_CONFIG_NAME)

    def __env_path_set(self) -> None:
        """
        author:DuPanPan
        date:2020.04.28
        description:设置env_config.xml的路径
        :return: 无返回值
        """
        classes_path = os.path.dirname(os.path.abspath(__file__))
        # ..\PS3Test\framework\biz\classes
        biz_path = os.path.dirname(classes_path)
        # \PS3Test\framework\biz
        framework_path = os.path.dirname(biz_path)
        # \PS3Test\framework\
        self.env_file_path = os.path.join(framework_path, constants.FRAMEWORK_DIR_ENV_CONF,
                                          constants.ENV_CONFIG_NAME)

    def __server_common_path_set(self) -> None:
        """
        author:DuPanPan
        date:2020.04.28
        description: 设置server_common_config.xml的路径
        :return: 无返回值
        """

        classes_path = os.path.dirname(os.path.abspath(__file__))
        # ..\PS3Test\framework\biz\classes
        biz_path = os.path.dirname(classes_path)
        # \PS3Test\framework\biz
        framework_path = os.path.dirname(biz_path)
        # \PS3Test\framework\
        esat_path = os.path.dirname(framework_path)
        # \PS3Test\

        # if not self.__env_dict:
        #     self.__env_file_parse()
        self.server_common_path = os.path.join(esat_path, constants.PROJECT_DIR_CONF,
                                               constants.SERVER_COMMON_CONFIG_NAME)

    def __create_test_host_file(self) -> None:
        host_config = self.get_host_config_info(self.host_label_str)
        log.info("host_config:{}".format(host_config))
        file_name = ConfigManager.get_test_host_config_filepath(self.host_label_str,
                                                                self.host_location_str, self.host_type_str)
        if not os.path.exists(os.path.dirname(file_name)):
            os.makedirs(os.path.dirname(file_name))
        if not os.path.exists(file_name):
            fd = open(file_name, mode="w", encoding="utf-8")
            fd.close()
        ConfigManager.save_test_host_config_xml(host_config, file_name, self.test_entry, self.test_object)

    def __test_host_file_parse(self) -> None:
        """
        author:DuPanPan
        date:2020.04.28
        description: 解析test_host_config.xml，更新字典和标签
        :return: 无返回值
        """
        root = None
        self.__test_host_path_set()
        try:
            root = ET.parse(self.test_host_file_path).getroot()
        except Exception as e:
            log.error("Not found %s" % self.test_host_file_path)
            log.error(str(e))
            exit(1)
        list_nodes = list(root)
        for node in list_nodes:
            key = node.tag
            value = node.text
            self.__test_host_dict[key] = format_value(value)
        log.info("Parse test host xml success")

    def __env_file_parse(self) -> None:
        """
        author:DuPanPan
        date:2020.04.28
        description: 解析env_config.xml
        :return: 无返回值
        """
        self.__env_path_set()
        root = None
        try:
            root = ET.parse(self.env_file_path).getroot()
        except Exception as e:
            log.error("Not found %s" % self.env_file_path)
            log.error(str(e))
            exit(1)

        list_nodes = list(root)
        for node in list_nodes:
            key = node.tag
            value = node.text
            self.__env_dict[key] = format_value(value)

        # 将case_level转化为list的形式
        case_level_list = []
        case_level_value = self.__env_dict.get(constants.ENV_CASE_LEVEL)
        if isinstance(case_level_value, int):
            case_level_list.append(str(case_level_value))
        elif isinstance(case_level_value, str):
            temp_list = case_level_value.split(constants.CASE_LEVEL_SPLIT_FLAG)
            for i in temp_list:
                case_level_list.append(str(i))
        elif isinstance(case_level_value, tuple) or isinstance(case_level_value, list) \
                or isinstance(case_level_value, set):
            for i in case_level_value:
                case_level_list.append(str(i))
        else:
            case_level_list = case_level_value
        self.__env_dict[constants.ENV_CASE_LEVEL] = case_level_list

        # 为解析其他两个文件赋值文件路径相关信息
        self.host_location_str = self.__env_dict.get(constants.ENV_HOST_LOCATION)
        self.host_label_str = self.__env_dict.get(constants.ENV_HOST_LABEL)
        self.test_entry = self.__env_dict.get(constants.ENV_TEST_ENTRY)
        self.test_object = self.__env_dict.get(constants.ENV_TEST_OBJECT)
        self.host_cpu = self.__env_dict.get(constants.ENV_HOST_CPU)
        self.jenkins_server_ip_str = self.__env_dict.get(constants.ENV_JENKINS_IP)
        host_type = self.__env_dict.get(constants.ENV_HOST_TYPE)
        if host_type == constants.ENV_VIRTUAL_MACHINE:
            self.host_type_str = constants.CONFIG_DIR_VIRTUAL
        elif host_type == constants.ENV_PHYSICAL_MACHINE:
            self.host_type_str = constants.CONFIG_DIR_PHYSICAL
        self.parameters_from_zentao = self.__env_dict.get(constants.ENV_PARAM_FROM_ZENTAO)
        log.info("Parse env_config.xml success")

    def __ips_parse(self, host_location_str: str, jenkins_server_ip_str: str) -> tuple:
        """
        author:DuPanPan
        date:2020.04.28
        description: 通过解析server_common_config.xml获取ps3_server_ip和log_server_ip
        :param host_location_str: jenkins服务器所在地址
        :param jenkins_server_ip_str: jenkins服务器ip地址
        :returns ps3_server_ip,log_server_ip: ps3测试框架服务器ip，日志服务器ip
        """
        ps3_ip = ""
        log_ip = ""
        root = None
        self.__server_common_path_set()
        try:
            root = ET.parse(self.server_common_path).getroot()
        except Exception as e:
            log.error("Not found %s" % self.server_common_path)
            log.error(str(e))
            exit(1)
        location_node = root.find(host_location_str)
        list_jenkins_nodes = location_node.findall(
            constants.SERVER_COMMON_JENKINS)
        for jenkins_node in list_jenkins_nodes:
            jenkins_ip = jenkins_node.find(
                constants.SERVER_COMMON_JENKINS_SERVER_IP)
            if jenkins_ip.text == jenkins_server_ip_str:
                try:
                    ps3_ip = jenkins_node.find(constants.ENV_PS3_SERVER_IP).text
                    log_ip = jenkins_node.find(constants.ENV_LOG_SERVER_IP).text
                    log_account = jenkins_node.find(constants.ENV_LOG_SERVER_ACCOUNT).text
                    break
                except Exception as e:
                    log.error("jenkins ip is not configured")
                    log.error(str(e))
                    exit(1)
        else:
            log.error("jenkins ip is not configured")
            exit(1)
        log.info("Parse server_common_config.xml success")
        return ps3_ip, log_ip, log_account

    def __env_fields_indent(self, element: ET, level=0) -> None:
        """
        author:DuPanPan
        date:2020.04.23
        description: 为xml文件增加缩进和换行
        :param element: XML文件中的元素
        :param level：element的级数
        :return: 无返回值
        """
        i = constants.INTENT_CHARACTER + level * constants.INTENT_SPLITTER
        if len(element):
            if not element.text or not element.text.strip():
                element.text = i + constants.INTENT_SPLITTER
            if not element.tail or not element.tail.strip():
                element.tail = i
            for elem in element:
                self.__env_fields_indent(elem, level + 1)
                if not elem.tail or not elem.tail.strip():
                    elem.tail = i
        else:
            if level and (not element.tail or not element.tail.strip()):
                element.tail = i

    def __env_file_create(self) -> None:
        """
        author:DuPanPan
        date:2020.04.23
        description:创建env_config.xml文件
        :return:无返回值
        """
        self.__env_path_set()
        if not os.path.exists(self.env_file_path):
            try:
                os.mknod(self.env_file_path)
            except Exception as e:
                log.error("Create %s failure" % self.env_file_path)
                log.error(str(e))
                exit(1)
        "添加根元素env_config"
        root = ET.Element(constants.ENV_ROOT_NODE_NAME)
        "根据传入的字典添加子元素"

        # 根据传入字典只记录固定的字段
        for tag in self.__env_fields_list:
            sub_elem = ET.SubElement(root, tag)
            sub_elem.text = str(self.__env_dict.get(tag))

        # 将传入的字典全部记录在配置文件中
        # for key, value in self.__env_dict.items():
        #     sub_elem = ET.SubElement(root, key)
        #     sub_elem.text = str(value)
        self.__env_fields_indent(root)

        et = ET.ElementTree(root)
        # 写入文件
        try:
            et.write(self.env_file_path,
                     encoding=constants.DEFAULT_ENCODING,
                     xml_declaration=True)
            log.info("Create %s success" % self.env_file_path)
        except Exception as e:
            log.error("Create %s failed" % self.env_file_path)
            log.error(str(e))
            exit(1)

    def env_file_create(self, env_config_dict: dict) -> bool:
        """
        author:DuPanPan
        date:2020.04.23
        description:创建env_config.py文件
        :param env_config_dict:数据来源，key为env_config文件的标签，value对应值
        :return return_code:是否创建成功，成功True，失败False
        """

        return_code = True
        if not bool(env_config_dict):
            log.info("The dictionary is empty and cannot create an xml file ")
            return_code = False
        if isinstance(env_config_dict, str):
            env_config_dict = ast.literal_eval(env_config_dict)
        else:
            env_config_dict = env_config_dict
        if not isinstance(env_config_dict, dict):
            log.error(
                "Wrong parameter type for creating file of env_config.xml: %s"
                % type(env_config_dict))
            exit(1)
        else:
            # 从禅道出发不必提供test_case_list和test_script_list,
            # 从框架触发时需要这两个字段，为保持配置文件字段名完整，此处加上这两个字段
            if constants.ENV_TEST_CASE_LIST not in env_config_dict.keys():
                env_config_dict[constants.ENV_TEST_CASE_LIST] = ""
            if constants.ENV_TEST_SCRIPT_LIST not in env_config_dict.keys():
                env_config_dict[constants.ENV_TEST_SCRIPT_LIST] = ""
            self.__env_dict = env_config_dict
            # self.__env_config_dict_keys_check()
            self.__env_file_create()

        return return_code

    def test_host_dict_get(self) -> dict:
        """
        author:DuPanPan
        date:2020.04.23
        description:获取test_host_config.xml文件解析的字典
        :return self.__dict_test_host_config:test_host_config.xml文件解析的结果字典
        """
        if self.__test_host_dict is None or len(self.__test_host_dict) == 0:
            self.__create_test_host_file()
            self.__test_host_file_parse()
        return self.__test_host_dict

    def env_dict_get(self) -> dict:
        """
        author:DuPanPan
        date:2020.04.28
        description:获取env_config.xml文件解析的字典
        :return self.__dict_env_config:env_config.xml文件解析的结果字典
        """
        if self.__env_dict is None or len(self.__env_dict) == 0:
            self.__env_file_parse()
        return self.__env_dict

    def ips_dict_get(self) -> dict:
        """
        author:DuPanPan
        date:2020.04.28
        description:获取测试所需的ip地址
        :return self.dict_host_ps3_log_ips:返回测试机、PS3测试框架服务器、
                                            日志服务器ip组成的字典
        """
        if self.__ips_dict is None or len(self.__test_host_dict) == 0:
            self.__ips_dict = self.test_host_dict_get()
            ips_tuple = self.__ips_parse(self.host_location_str, self.jenkins_server_ip_str)
            self.__ips_dict[constants.ENV_PS3_SERVER_IP] = ips_tuple[0]
            self.__ips_dict[constants.ENV_LOG_SERVER_IP] = ips_tuple[1]
            self.__ips_dict[constants.ENV_LOG_SERVER_ACCOUNT] = ips_tuple[2]

            host_config = self.get_host_config_info(self.host_label_str)
            self.__ips_dict[constants.TEST_CONFIG_SERVER_BMC_IP] = host_config[constants.TEST_CONFIG_SERVER_BMC_IP]
            self.__ips_dict[constants.TEST_CONFIG_SUNAME] = host_config[constants.TEST_CONFIG_SUNAME]
            self.__ips_dict[constants.TEST_CONFIG_SUPASSWD] = host_config[constants.TEST_CONFIG_SUPASSWD]
            self.__ips_dict[constants.TEST_CONFIG_CLIENT_BMC_IP] = host_config[constants.TEST_CONFIG_CLIENT_BMC_IP]
            self.__ips_dict[constants.TEST_CONFIG_CUNAME] = host_config[constants.TEST_CONFIG_CUNAME]
            self.__ips_dict[constants.TEST_CONFIG_CUPASSWD] = host_config[constants.TEST_CONFIG_CUPASSWD]
            if constants.TEST_CONFIG_SERVER_COM_IP in host_config.keys():
                self.__ips_dict[constants.TEST_CONFIG_SERVER_COM_IP] = host_config[constants.TEST_CONFIG_SERVER_COM_IP]
                self.__ips_dict[constants.TEST_CONFIG_SERVER_COM_PORT] = host_config[constants.TEST_CONFIG_SERVER_COM_PORT]
                self.__ips_dict[constants.TEST_CONFIG_CLIENT_COM_IP] = host_config[constants.TEST_CONFIG_CLIENT_COM_IP]
                self.__ips_dict[constants.TEST_CONFIG_CLIENT_COM_PORT] = host_config[constants.TEST_CONFIG_CLIENT_COM_PORT]

        return self.__ips_dict

    def server_ips_dict_get(self, host_location_str, jenkins_server_ip_str) -> dict:
        """
        author:DuPanPan
        date:2020.10.30
        description:获取测试所需的ip地址
        :param host_location_str: 主机所在地址
        :param jenkins_server_ip_str: jenkins服务器ip地址
        :return server_ips_dict: PS3测试框架服务器、日志服务器ip组成的字典
        """
        server_ips_dict = dict()
        ips_tuple = self.__ips_parse(host_location_str, jenkins_server_ip_str)
        server_ips_dict[constants.ENV_PS3_SERVER_IP] = ips_tuple[0]
        server_ips_dict[constants.ENV_LOG_SERVER_IP] = ips_tuple[1]
        server_ips_dict[constants.ENV_LOG_SERVER_ACCOUNT] = ips_tuple[2]
        server_ips_dict[constants.ENV_JENKINS_IP] = jenkins_server_ip_str
        return server_ips_dict

    def get_host_config_info(self, vm):
        wb = load_workbook(constants.HOST_CONFIG_FILE)
        ws = wb.active
        result = {}
        for line in islice(ws.rows, 1, None):
            row = {}
            for index, cell in enumerate(list(line)):
                if index < len(self.__host_info):
                    row[self.__host_info[index]] = str(cell.value)
                else:
                    break
            result[row.get(constants.ENV_HOST_LABEL)] = row
        return result.get(vm, {})

    @classmethod
    def sub_element(cls, root, tag, text):
        ele = ET.SubElement(root, tag)
        ele.text = text

    @classmethod
    def save_test_host_config_xml(cls, host_config, file_name, test_entry, test_object,
                                  indent="\t", new_line="\n", encoding="utf-8"):
        from xml.dom import minidom  # 避免循环引用
        pattern = re.compile(constants.IP_PATTERN)

        host_ip = host_config.get(constants.TEST_CONFIG_SERVER_IP, '-')

        root = ET.Element("test_host")
        cls.sub_element(root, constants.TEST_CONFIG_SERVER_IP, host_ip)
        cls.sub_element(root, constants.TEST_CONFIG_SERVER_NIC_IP,
                        str(host_config.get(constants.TEST_CONFIG_SERVER_NIC_IP) or '-'))
        cls.sub_element(root, constants.TEST_CONFIG_CLIENT_IP,
                        str(host_config.get(constants.TEST_CONFIG_CLIENT_IP) or '-'))
        cls.sub_element(root, constants.TEST_CONFIG_CLIENT_NIC_IP,
                        str(host_config.get(constants.TEST_CONFIG_CLIENT_NIC_IP) or '-'))

        raw_text = ET.tostring(root)
        dom = minidom.parseString(raw_text)
        with open(file_name, 'w') as f:
            dom.writexml(f, "", indent, new_line, encoding)

    @classmethod
    def get_test_host_config_filepath(cls, vm, location, host_type):
        classes_path = os.path.dirname(os.path.abspath(__file__))
        biz_path = os.path.dirname(classes_path)
        framework_path = os.path.dirname(biz_path)
        esat_path = os.path.dirname(framework_path)
        return os.path.join(esat_path, constants.PROJECT_DIR_CONF, location, host_type, vm,
                            constants.TEST_HOST_CONFIG_NAME)
