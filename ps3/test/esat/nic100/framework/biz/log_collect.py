#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
author:      haibin.xu
date:        2021-04-02 09:36:32
@summary:    log日志搜集，该脚本主要提供以下两个功能：
             1. 向测试框架提供日志收集的相关接口；
             2. 脚本单独执行时，配置相关命令行参数后，可作为手动收集log使用，命令行参数配置提供两种方式：
                -1. 终端直接执行该脚本时，附带命令行参数，如下所示：
                    python log_collect.py --hip 10.22.81.1 --hp 22 --hnip 10.22.83.3 --sip 10.22.81.1 --sp 22
                                          --snip 10.22.83.4 --lsip 10.22.67.3 --lsac framework --hc 1 --to 0
                                          --te 0 --hl vm000
                -2. 在该脚本中直接定义main函数中的sys.argv列表，如下所示：
                    sys.argv = [
                        'collect_tool.py',
                        '--hip', '10.22.81.1',
                        '--hp', '22',
                        '--hnip', '10.22.83.3',
                        '--sip', '10.22.81.1',
                        '--sp', '22',
                        '--snip', '10.22.83.4',
                        '--lsip', '10.22.67.3',
                        '--lsac', 'framework',
                        '--hc', '1',
                        '--to', '0',
                        '--te', '0',
                        '--hl', 'vm000'
                   ]
                注意：相关命令行参数定义，请参考test/esat/scripts/scripts_libs/command_line_args_parse.py中的定义；
                     -1， -2两种方法不可同时使用，如果同时开启时，脚本命令行参数会以第二种方式为准，如使用第一种方式，务必注释掉main
                     函数中的 sys.argv列表；

@steps:

@changelog:

"""
import os
import re
import sys
import time
import importlib

import add_syspath
from framework.biz.classes.config_file_manager import ConfigManager
from framework.libs import constants
from scripts.script_libs import log
from scripts.script_libs import constants as libs_constants
from scripts.script_libs.host_operation import HostOperation
from scripts.script_libs.file_operation import FileOperation
from scripts.script_libs.controller_operation import ControllerOperation
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import TestObjectEnum, TestObjectStrEnum, TestEntryStrEnum, RtnStatusEnum, \
    CompileObjectStrEnum
from scripts.script_libs import command_line_args_parse as clap


class LogCollect(object):
    """
     author: DuPanPan
     date: 2020.04.26
     description: 收集日志至日志服务器
    """

    def __init__(self, manual_flag: bool = False, host_ip: str = None, host_port: str = '22',
                 host_qemu_ip: str = None, ioc_ip: str = None, ioc_port: int = '22', ioc_qemu_ip: str = None,
                 log_server_ip: str = None, log_server_account: str = None, host_cpu: str = None,
                 test_object: str = 'raid', test_entry: str = 'host', host_label: str = 'vm000',
                 test_platform: str = None, reg_file: str = None):
        # 配置文件字典
        self.__config_manager = None
        self.__env_config_dict = None
        self.__ips_config_dict = None

        # 测试中所使用到的所有ip地址
        self.log_server_ip = None
        self.log_server_account = None
        self.ps3_server_ip = None
        self.host_ip = None
        self.host_qemu_ip = None
        self.host_port = None
        self.ioc_ip = None
        self.ioc_qemu_ip = None
        self.ioc_port = None
        self.exp_port = None
        self.host_label = None
        self.host_os = None
        self.test_platform = None
        self.com_ip = None
        self.com_port = None

        # 当前测试环境中host端的cpu架构
        self.host_cpu = None
        # Jenkins配置的测试对象参数
        self.test_object = None
        # Jenkins配置的测试入口
        self.test_entry = None
        # Jenkins配置的测试平台参数
        self.test_platform = None
        # Jenkins配置的编译对象参数
        self.compile_object = None
        # 重置公共库测试对象参数
        self.libs_test_object = None
        # Jenkins配置的包是否安装参数
        self.package_install = None
        # Jenkins配置的安装包路径
        self.package_path = None
        # Jenkins配置的expander拓扑模板参数
        self.exp_topo_template = None
        # host 节点名称
        self.host_node_name = None
        # ioc 节点名称
        self.ioc_node_name = None
        # ioc节点id
        self.ioc_node_id = None
        # host节点id
        self.host_node_id = None

        # 日志服务器存放日志文件一个JOB级根路径
        self.log_root_dir_path = ''

        # 日志服务器存放日志文件脚本级别路径
        self.log_script_dir_path = ''

        # 记录当前host端Crash文件列表、ioc端core、crash列表
        self.qemu_crash_core_initial_data = {
            libs_constants.LOG_COLL_HOST_CRASH_DIR: [],
            libs_constants.LOG_COLL_IOC_CRASH_DIR: [],
            libs_constants.LOG_COLL_IOC_CORE_DIR: [],
            libs_constants.LOG_COLL_EXP_CORE_DIR: [],
            libs_constants.LOG_COLL_HOST_CORE_DIR: [],
        }

        # 记录ps3explog文件列表
        self.exp_log_initial_data = {
            libs_constants.LOG_COLL_PS3_EXP_LOG_DIR: []
        }
        # 记录ps3explog文件路径
        self.ps3_exp_log_files = None

        # 记录host 端需要删除的文件列表
        self.host_delete_files = None
        # 记录host 端需要清空的文件列表
        self.host_clean_files = None
        # 记录host qemu端需要删除的文件列表
        self.host_qemu_delete_files = None
        # 记录host qemu端需要清空的文件列表
        self.host_qemu_clean_files = None
        # 记录主机驱动需要删除的文件列表
        self.drv_delete_files = None
        # 记录主机驱动需要清空的文件列表
        self.drv_clean_files = None
        # 记录ioc 宿主机端需要删除的文件列表
        self.ioc_delete_files = None
        # 记录ioc 宿主机端需要清空的文件列表
        self.ioc_clean_files = None
        # 记录ioc qemu端需要删除的文件列表
        self.ioc_qemu_delete_files = None
        # 记录ioc qemu端需要清空的文件列表
        self.ioc_qemu_clean_files = None

        # 记录host qemu端core文件目录
        self.host_qemu_core_files = None
        # 记录host qemu端crash文件列表
        self.host_qemu_crash_files = None
        # 记录ioc qemu端core文件列表
        self.ioc_qemu_core_files = None
        # 记录ioc qemu端crash文件列表
        self.ioc_qemu_crash_files = None
        # 记录expander core文件列表
        self.expander_core_files = None
        # 当前脚本寄存器数据文件
        self.register_file = None

        # 测试工具输出文件列表
        self.test_tool_output_files = None

        # host宿主机收集文件和收集路径字典
        self.host_log_dict = {}
        self.host_log_dict_again = {}
        # host宿主机收集文件和收集路径字典
        self.host_expander_log_dict = {}
        # host qemu侧收集文件和收集路径字典
        self.host_qemu_log_dict = {}
        # ps3_server侧收集文件和收集路径字典
        self.ps3_server_framework_log_dict = {}
        # ioc宿主机收集文件和收集路径字典
        self.ioc_log_dict = {}
        # expander在ioc宿主机端需要收集的文件和收集路径字典
        self.ioc_expander_log_dict = {}
        # pcieswitch在ioc宿主机端需要收集的文件和收集路径字典
        self.ioc_pcieswitch_log_dict = {}
        # ioc qemu侧收集文件和收集路径字典
        self.ioc_qemu_log_dict = {}

        # ioc宿主机收集文件后的文件夹名和打包压缩后的文件名
        self.qemu_ioc_collect_path = constants.SIMULATOR_QEMU_IOC_EXP_LOG_COLLECT_DIR
        self.qemu_ioc_collect_tar = constants.SIMULATOR_QEMU_IOC_EXP_LOG_COLLECT_TAR
        self.pcie_ioc_collect_path = constants.SIMULATOR_QEMU_IOC_PCIESWITCH_LOG_COLLECT_DIR
        self.pcie_ioc_collect_tar = constants.SIMULATOR_QEMU_IOC_PCIESWITCH_LOG_COLLECT_TAR
        # ps3 server收集文件后的文件夹名和打包压缩后的文件名
        self.ps3_server_collect_path = constants.LOG_DIR_NAME_PS3_SERVER
        self.ps3_server_collect_tar = constants.LOG_DIR_NAME_PS3_SERVE_TAR
        # host宿主机收集文件后的文件夹名和打包压缩后的文件名
        self.host_qemu_collect_path = constants.SIMULATOR_QEMU_HOST_LOG_COLLECT_DIR
        self.host_qemu_collect_tar = constants.SIMULATOR_QEMU_HOST_LOG_COLLECT_TAR
        # host侧收集文件后的文件夹名和打包压缩后的文件名
        self.host_collect_path = constants.SIMULATOR_HOST_LOG_COLLECT_DIR
        self.host_collect_tar = constants.SIMULATOR_HOST_LOG_COLLECT_TAR
        # ioc 宿主机侧收集文件后的文件夹名和打包压缩后的文件名
        self.ioc_collect_path = constants.SIMULATOR_IOC_LOG_COLLECT_DIR
        self.ioc_collect_tar = constants.SIMULATOR_IOC_LOG_COLLECT_TAR
        # ioc qemu server侧收集文件后的文件夹名和打包压缩后的文件名
        self.ioc_qemu_collect_path = constants.SIMULATOR_IOC_QEMU_LOG_COLLECT_DIR
        self.ioc_qemu_collect_tar = constants.SIMULATOR_IOC_QEMU_LOG_COLLECT_TAR
        # 物理平台，expander串口日志
        self.host_expander_serial_log_path = constants.REAL_EXP_SERIAL_LOG_DIR
        # haibin.xu 2022-06-24 14:20:55 modify: 添加当前脚本测试起始时间
        self.current_script_test_start_time = None
        # haibin.xu 2022-06-24 14:22:15 modify: 添加当前脚本测试时间
        self.current_script_test_time = None
        # 设置相关参数
        if manual_flag:
            self.__manual_set_parameters(host_ip, host_port, host_qemu_ip, ioc_ip, ioc_port, ioc_qemu_ip,
                                         log_server_ip, log_server_account, host_cpu, test_object, test_entry,
                                         host_label, test_platform, reg_file)
        else:
            self.__set_obj_parameters()
            self.__set_ip_parameters()
            self.__set_other_parameters()
        self.__reset_constants_parameters()

    def __manual_set_parameters(self, host_ip: str = None, host_port: str = '22', host_qemu_ip: str = None,
                                ioc_ip: str = None, ioc_port: int = '22', ioc_qemu_ip: str = None,
                                log_server_ip: str = None, log_server_account: str = None, host_cpu: str = None,
                                test_object: str = None, test_entry: str = None, host_label: str = None,
                                test_platform: str = None, reg_file: str = None) -> None:
        """
        author:      haibin.xu
        date:        2021-03-31 17:57:42
        description: 手动设置参数，即不从配置文件中获取，直接使用创建log实例时传递的参数

        :return:
        """
        self.host_ip = host_ip
        self.host_port = host_port
        self.host_qemu_ip = host_qemu_ip
        self.ioc_ip = ioc_ip
        self.ioc_port = ioc_port
        self.ioc_qemu_ip = ioc_qemu_ip
        self.log_server_ip = log_server_ip
        self.log_server_account = log_server_account
        self.host_cpu = host_cpu
        self.test_object = test_object
        self.test_entry = test_entry
        self.host_label = host_label
        self.test_platform = test_platform
        self.register_file = reg_file

    def __set_obj_parameters(self) -> None:
        """
        author:      haibin.xu
        date:        2021-03-23 20:01:07
        description: 获取self.__config_manager，self.__env_config_dict，self.__ips_config_dict参数

        :return:     None
        """
        self.__config_manager = ConfigManager.get_config_manager_object()
        if self.__config_manager is None:
            log.error('Fail to get config manager object.')
            exit(1)

        self.__env_config_dict = self.__config_manager.env_dict_get()
        if self.__env_config_dict is None:
            log.error('Fail to get config_manager_parameters: env_dict_get.')
            exit(1)

        self.__ips_config_dict = self.__config_manager.ips_dict_get()
        if self.__ips_config_dict is None:
            log.error('Fail to get config_manager_parameters: ips_dict_get.')
            exit(1)

    def __set_ip_parameters(self):
        """
        :author:panpan.du
        :date:2020.10.19
        :description: 初始化ip地址
        : return: 无返回值

        @changelog      2021-03-23 19:59:14  haibin.xu
                        1. 优化函数实现, 方法名修正 __init_ip -> __set_ip_parameters
        """

        """测试中所使用到的所有ip地址"""
        self.log_server_ip = self.__ips_config_dict.get(constants.ENV_LOG_SERVER_IP)
        self.log_server_account = self.__ips_config_dict.get(constants.ENV_LOG_SERVER_ACCOUNT,
                                                             constants.ENV_DEFAULT_ACCOUNT)
        self.ps3_server_ip = self.__ips_config_dict.get(constants.ENV_PS3_SERVER_IP)
        self.host_ip = self.__ips_config_dict.get(constants.TEST_CONFIG_HOST_IP)
        self.host_qemu_ip = self.__ips_config_dict.get(constants.TEST_CONFIG_HOST_QEMU_IP)
        self.host_port = self.__ips_config_dict.get(constants.TEST_CONFIG_HOST_PORT)
        self.ioc_ip = self.__ips_config_dict.get(constants.TEST_CONFIG_IOC_IP)
        self.ioc_qemu_ip = self.__ips_config_dict.get(constants.TEST_CONFIG_IOC_QEMU_IP)
        self.ioc_port = self.__ips_config_dict.get(constants.TEST_CONFIG_IOC_PORT)
        self.exp_port = self.__ips_config_dict.get(constants.ENV_EXPANDER_PORT)
        self.com_ip = self.__ips_config_dict.get(constants.TEST_CONFIG_COMHOST)
        self.com_port = self.__ips_config_dict.get(constants.TEST_CONFIG_A72)
        if self.com_port:
            self.com_port = str(self.com_port)

    def __set_other_parameters(self) -> None:
        """
        author:      haibin.xu
        date:        2021-03-23 20:10:13
        description: 设置其余变量

        :return:     None
        """
        self.test_object = self.__env_config_dict.get(constants.ENV_TEST_OBJECT)
        if not self.test_object:
            log.error('Fail to get env parameter: test_object.')
            exit(1)

        # 获取test_entry参数
        self.test_entry = self.__env_config_dict.get(libs_constants.ENV_TEST_ENTRY)
        if self.test_entry is None:
            log.error('Fail to get test entry.')
            exit(1)

        # 获取host端的cpu架构
        self.host_cpu = self.__env_config_dict.get(libs_constants.ENV_HOST_CPU)
        if not self.host_cpu:
            log.error('Fail to get host cpu.')
            exit(1)

        # 获取host_lable
        self.host_label = self.__env_config_dict.get(constants.ENV_HOST_LABEL)
        self.host_os = self.__env_config_dict.get(constants.ENV_HOST_OS)

        self.package_install = self.__env_config_dict.get(constants.ENV_PACKAGE_INSTALL)
        self.package_path = self.__env_config_dict.get(constants.ENV_PACKAGE_PATH)

        self.compile_object = self.__env_config_dict.get(constants.ENV_COMPILE_OBJECT)
        self.exp_topo_template = self.__env_config_dict.get(constants.ENV_EXP_TOPO_TEMPLATE)

        # 获取测试平台
        self.test_platform = self.__env_config_dict.get(constants.ENV_TEST_PLATFORM)

    def __reset_constants_parameters(self) -> None:
        """
        author:      haibin.xu
        date:        2021-03-06 17:25:14
        description: 重置constans下的host ip, host node ip, ioc ip, ioc node ip, PS3CLI64, SIMADMIN

        :return:     None
        """
        libs_constants.reset_ip_parameters(new_host_ip=self.host_ip, new_host_node_ip=self.host_qemu_ip,
                                           new_ioc_ip=self.ioc_ip, new_ioc_node_ip=self.ioc_qemu_ip,
                                           new_host_port=self.host_port, new_ioc_port=self.ioc_port)
        log.info('Finish reset ip parameters in constants.py, host ip: {}, host node ip: {}, host port:{}, ioc ip: '
                 '{}, ioc node ip: {}, ioc port: {}.'.format(libs_constants.HOST_IP, libs_constants.HOST_NODE_IP,
                                                             libs_constants.HOST_PORT, libs_constants.SOC_IP,
                                                             libs_constants.SOC_NODE_IP, libs_constants.SOC_PORT))

        # 根据test_object值，设置libs_test_object
        if libs_constants.TEST_OBJECT_RAID == self.test_object:
            self.libs_test_object = TestObjectEnum.RAID.value
        elif libs_constants.TEST_OBJECT_HBA == self.test_object:
            self.libs_test_object = TestObjectEnum.HBA.value
        elif libs_constants.TEST_OBJECT_EXPANDER == self.test_object:
            self.libs_test_object = TestObjectEnum.EXPANDER.value
        elif libs_constants.TEST_OBJECT_PCIE_SWITCH == self.test_object:
            self.libs_test_object = TestObjectEnum.PCIE_SWITCH.value
        else:
            log.error('Invalid test object: {}.'.format(self.test_object))
            exit(1)

        libs_constants.reset_test_obj(new_test_obj=self.libs_test_object)
        log.info('Finish reset test object parameters in constants.py. test object: {}.'.format(
            libs_constants.test_obj))

        libs_constants.reset_cmd_product(new_host_cpu=self.host_cpu, test_object=self.libs_test_object)
        log.info('Finish reset command products parameters in constants.py. PS3CLI: {}, SIMADMIN: {}.'.format(
            libs_constants.PS3CLI64, libs_constants.SIMADMIN))

    def __get_node_info(self) -> None:
        """
        author:      haibin.xu
        date:        2021-04-30 16:59:45
        description: 获取节点信息

        :return:     None
        """
        if self.test_platform == constants.ENV_PLATFORM_REAL:
            return
        if (constants.ENV_TEST_ENTRY_IOC != self.test_entry) or (constants.ENV_TEST_OBJECT_EXPANDER !=
                                                                 self.test_object):
            # 获取host节点名称
            if (self.host_node_name is None) or (self.ioc_node_name is None) or (self.ioc_node_id is None):
                try:
                    self.host_node_name, self.host_node_id, self.ioc_node_name, self.ioc_node_id, _ = \
                        HostOperation.get_node_name_id()
                except Exception as e:
                    log.error('Found exception during get node data, exception: {}'.format(e))
                    self.host_node_name, self.ioc_node_name, self.ioc_node_id = None, None, None

    def __set_crash_core_files_parameters(self) -> None:
        """
        author:      haibin.xu
        date:        2021-04-09 11:05:57
        description: 设置host qemu, ioc qemu端的core, crash参数信息

        :return:     None
        """
        # 添加host qemu crash files
        self.host_qemu_crash_files = libs_constants.LOG_COLL_HOST_CRASH_FILE_PATH
        # 添加ioc qemu crash files
        self.ioc_qemu_crash_files = libs_constants.LOG_COLL_IOC_CRASH_FILE_PATH
        # 添加ioc qemu core files
        self.ioc_qemu_core_files = libs_constants.LOG_COLL_IOC_CORE_FILE_PATH
        # 添加expander core files
        if (TestEntryStrEnum.SOC.value == self.test_entry) and \
                ((TestObjectStrEnum.EXPANDER.value == self.test_object) or
                 (CompileObjectStrEnum.EXPANDER.value == self.compile_object)):
            self.expander_core_files = CommandOperation.format_linux_path_sep(os.path.join(
                constants.SIMULATOR_EXP_CLI_ROOT, self.exp_port, constants.CORE_FILES_NAME))

    def get_crash_core_files_before_test(self) -> None:
        """
        :author:panpan.du
        :date:2020.10.07
        :description: 记录crash、core文件夹中的所有文件信息
        :return: 无返回值

        @changelog      2021-03-24 10:20:55  haibin.xu
                        1. 优化函数实现, 函数名修正：files_record_original -> get_crash_core_files_before_test
        """

        if self.test_entry == TestEntryStrEnum.UEFI.value:
            return

        self.__set_crash_core_files_parameters()
        try:
            _, host_crash_files = FileOperation.get_files(file_path=self.host_qemu_crash_files,
                                                          ip=self.host_qemu_ip, port=self.host_port)
        except Exception as e:
            log.error('Found exception during get file: {}, exception: {}'.format(self.host_qemu_crash_files, e))
            host_crash_files = []

        if host_crash_files:
            self.qemu_crash_core_initial_data[libs_constants.LOG_COLL_HOST_CRASH_DIR] = host_crash_files
        else:
            log.warning('Fail to get host  crash files.')
        # 如果是物理平台，在host端查找core文件
        if self.test_platform == constants.ENV_PLATFORM_REAL:
            try:
                core_path_list = [
                    f"{libs_constants.LOG_COLL_HOST_CORE_FILE_PATH}*core*",
                ]

                _, host_core_files = FileOperation.get_files(file_path=' '.join(core_path_list),
                                                             ip=self.host_ip, port=self.host_port)
            except Exception as e:
                log.error('Found exception during get file: {}, exception: {}'.format(self.host_qemu_crash_files, e))
                host_crash_files = []

            if host_core_files:
                self.qemu_crash_core_initial_data[libs_constants.LOG_COLL_HOST_CORE_DIR] = host_core_files
            else:
                log.warning('Fail to get real host core files.')

        if constants.ENV_TEST_OBJECT_PCIE_SWITCH != self.test_object:
            try:
                _, ioc_crash_files = FileOperation.get_files(file_path=self.ioc_qemu_crash_files,
                                                             ip=self.ioc_qemu_ip, port=self.ioc_port)
            except Exception as e:
                log.error('Found exception during get file: {}, exception: {}'.format(self.ioc_qemu_crash_files, e))
                ioc_crash_files = []

            if ioc_crash_files:
                self.qemu_crash_core_initial_data[libs_constants.LOG_COLL_IOC_CRASH_DIR] = ioc_crash_files
            else:
                log.warning('Fail to get ioc qemu crash files.')

            try:
                _, ioc_core_files = FileOperation.get_files(file_path=self.ioc_qemu_core_files, ip=self.ioc_qemu_ip,
                                                            port=self.ioc_port)
            except Exception as e:
                log.error('Found exception during get file: {}, exception: {}'.format(self.ioc_qemu_core_files, e))
                ioc_core_files = []

            if ioc_core_files:
                self.qemu_crash_core_initial_data[libs_constants.LOG_COLL_IOC_CORE_DIR] = ioc_core_files
            else:
                log.warning('Fail to get ioc qemu core files.')
        else:
            log.info('Pcie switch test, not to collect ioc qemu crash and core files.')

        # 单独expander core文件
        if (TestEntryStrEnum.SOC.value == self.test_entry) and \
                ((TestObjectStrEnum.EXPANDER.value == self.test_object) or
                 (CompileObjectStrEnum.EXPANDER.value == self.compile_object)):
            try:
                _, exp_core_files = FileOperation.get_files(file_path=self.expander_core_files, ip=self.ioc_ip)
            except Exception as e:
                log.error('Found exception during get file: {}, exception: {}'.format(self.expander_core_files, e))
                exp_core_files = []

            if exp_core_files:
                self.qemu_crash_core_initial_data[libs_constants.LOG_COLL_EXP_CORE_DIR] = exp_core_files
            else:
                log.warning('Fail to get expander core files.')

        log.info('Get core/crash files of host and ioc qemu server before test: {}'.format(
            self.qemu_crash_core_initial_data))

    def __set_ps3_exp_log_parameters(self) -> None:
        """
        author:      haibin.xu
        date:        2022-06-03 10:05:13
        description: 设置ps3explog路径参数信息

        :return:     None
        """
        if self.ps3_exp_log_files is None:
            self.ps3_exp_log_files = CommandOperation.format_linux_path_sep(os.path.join(
                libs_constants.LOG_COLL_PS3_EXP_LOG_FILE_PATH))

    def update_ps3_exp_log_record_data(self) -> None:
        """
        author:      haibin.xu
        date:        2022-06-03 09:24:26
        description: 更新self.exp_log_initial_data[libs_constants.LOG_COLL_PS3_EXP_LOG_DIR]列表信息

        :return:     None
        """
        if (TestObjectStrEnum.EXPANDER.value == self.test_object) and \
                (constants.ENV_PLATFORM_REAL == self.test_platform):
            log.info('Start update ps3explog record data.')
            self.__set_ps3_exp_log_parameters()
            try:
                _, ps3explog_files = FileOperation.get_files(file_path=self.ps3_exp_log_files, ip=self.host_ip)
            except Exception as e:
                log.error('Found exception during get file: {}, exception: {}'.format(self.ps3_exp_log_files, e))
                ps3explog_files = []

            new_ps3exp_log = []
            for efile in ps3explog_files:
                if efile not in self.exp_log_initial_data[libs_constants.LOG_COLL_PS3_EXP_LOG_DIR]:
                    new_ps3exp_log.append(efile)

            log.debug('Get new ps3explog files: {}'.format(new_ps3exp_log))
            self.exp_log_initial_data[libs_constants.LOG_COLL_PS3_EXP_LOG_DIR].extend(new_ps3exp_log)

    def __get_new_ps3_expander_log(self) -> list:
        """
        author:      haibin.xu
        date:        2022-06-03 10:59:30
        description: 收集物理平台下新的ps3explog日志

        :return:     返回新的ps3explog日志列表

        @changelog
        """
        new_ps3explog_files = []

        if (TestObjectStrEnum.EXPANDER.value == self.test_object) and \
                (constants.ENV_PLATFORM_REAL == self.test_platform):
            log.info('Start to get new ps3 expander log...')

            log.info('export ps3explog')
            cmd_code, cmd_output, cmd_stderr = CommandOperation.execute_command_with_error(
                cmd='ps3explog --export', ssh_ip=self.host_ip, ssh_port='22', timeout=None)
            log.info('cmd: ps3explog --export\nstatus:{}\ncmd_output:\n{}\ncmd_stderr:\n{}'.format(
                cmd_code, cmd_output, cmd_stderr))

            self.__set_ps3_exp_log_parameters()
            ps3explog_dirname = os.path.dirname(self.ps3_exp_log_files)

            try:
                dir_exist = FileOperation.dir_path_exists(path=ps3explog_dirname, ip=self.host_ip)
            except Exception as e:
                log.error('Found exception during check directory path: {}, exception: {}.'.format(
                    ps3explog_dirname, e))
                dir_exist = RtnStatusEnum.FAIL.value

            if RtnStatusEnum.SUCCESS.value == dir_exist:
                log.info(f"ps3explog file path: {self.ps3_exp_log_files}")

                # 获取当前/home/ps3explog目录下文件列表
                try:
                    _, files = FileOperation.get_files(file_path=self.ps3_exp_log_files, ip=self.host_ip)
                except Exception as e:
                    log.error('Found exception during get files from directory: {}, exception: {}.'.format(
                        self.ps3_exp_log_files, e))
                    files = []

                if files:
                    log.debug('Found ps3explog in directory[{}]: {}'.format(ps3explog_dirname, files))
                    # 与旧文件列表对比找出新产生的ps3explog
                    for fle in files:
                        if fle not in self.exp_log_initial_data[libs_constants.LOG_COLL_PS3_EXP_LOG_DIR]:
                            new_ps3explog_files.append(fle)

        log.info('get new ps3 expander log: {}\n'.format(new_ps3explog_files))

        return new_ps3explog_files

    def __set_test_tool_output_parameters(self) -> None:
        """
        author:      haibin.xu
        date:        2021-04-09 11:29:22
        description: 设置测试工具输出文件参数

        :return:     None
        """
        if 'windows' not in libs_constants.HOST_OS:
            self.test_tool_output_files = [
                libs_constants.LOG_COLL_VDBENCH_OUTPUT_FILE_PATH,
                libs_constants.LOG_COLL_FIO_OUTPUT_FILE_PATH,
            ]
        else:
            self.test_tool_output_files = [
                libs_constants.WINDOWS_LOG_COLL_VDBENCH_OUTPUT_FILE_PATH,
                libs_constants.WINDOWS_LOG_COLL_FIO_OUTPUT_FILE_PATH,
            ]

    def delete_test_tool_files(self) -> None:
        """
        author:panpan.du
        date:2020.10.15
        description: 清空模拟平台上原有的日志文件
        :return: 无返回值

        @changelog      2021-03-24 10:39:01  haibin.xu
                        1. 优化函数实现, 函数名修正：delete_test_tool_files -> delete_test_tool_files
        """

        if self.test_entry == TestEntryStrEnum.UEFI.value:
            return

        # 删除测试工具vdbench和fio的输出文件
        self.__set_test_tool_output_parameters()
        log.info('Start to delete test tool files...'.format(
            self.test_entry, self.test_object))

        for file in self.test_tool_output_files:
            try:
                rtn_code, _ = FileOperation.delete_file(path=file, ip=self.host_qemu_ip, port=self.host_port,
                                                        file_check_flag=False)
            except Exception as e:
                log.error('Found exception during delete file: {}, exception: {}'.format(file, e))
                rtn_code = RtnStatusEnum.FAIL.value

            if RtnStatusEnum.SUCCESS.value == rtn_code:
                log.info('Finish to delete file: {}.'.format(file))
            else:
                log.warning('Fail to delete file: {}.'.format(file))

        log.info('Finish to delete test tool files.\n')

    @staticmethod
    def clean_files(file_list: list, test_ip: str, test_port: str = '22') -> None:
        """
        author: luyafei
        date: 2020.12.28
        description: 清理文件
        :param test_ip: 要清理文件所在机器的ip
        :param file_list: 要清理的文件列表
        :param test_port: 要清理文件所在机器的port
        :return: None

        @changelog      2021-03-26 17:38:37  haibin.xu
                        1. 优化函数实现, 函数名修正：files_clear -> clean_files
        """
        if RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(ip=test_ip, port=test_port,
                                                                            connect_times=5):
            log.error('Not to clean files: {}, reason: failed to connect server: root@{}:{}'.format(
                file_list, test_ip, test_port))
            return

        if file_list:
            files = ' '.join(file_list)
            batch_empty_files_cmd = 'for i in {}; do cat /dev/null > $i; done'.format(files)
            try:
                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    batch_empty_files_cmd, ssh_ip=test_ip, ssh_port=test_port)
                rtn_code = CommandOperation.check_cli_output(batch_empty_files_cmd, cmd_code, cmd_stdout, cmd_stderr)
            except Exception as e:
                log.error('Found exception during clean file, exception: {}'.format(e))
                rtn_code = RtnStatusEnum.FAIL.value

            if RtnStatusEnum.SUCCESS.value == rtn_code:
                log.debug('Success clean file: {}.'.format(files))
            else:
                log.warning('Fail to clean file: {}.'.format(files))
        else:
            log.debug('Not need to clean file, file list is null.')

    @staticmethod
    def delete_files(delete_file: (list, str), test_ip: str, test_port: str = '22', username: str = 'root',
                     match_flag: bool = False, local_execute: bool = False) -> int:
        """
        author: luyafei
        date: 2020.12.29
        description: 删除文件
        :param test_ip: 要删除文件所在机器的ip
        :param test_port: 要删除文件所在机器的port
        :param delete_file: 要删除的文件列表或文件
        :param username:    远程登录用户名
        :param match_flag: 是否对文件进行/root/ps3sim/.*模式匹配，
                           如果进行模式匹配，则只有匹配该模式才对文件进行操作
        :param local_execute: 本地执行标志位
        :return: 返回文件是否成功删除

        @changelog      2021-03-26 17:13:22  haibin.xu
                        1. 优化函数实现, 函数名修正：files_delete -> delete_files
        """
        rtn_delete = RtnStatusEnum.SUCCESS.value

        if (not local_execute) and (RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(
                ip=test_ip, port=test_port, ssh_username=username, connect_times=5)):
            log.error('Not to delete files: {}, reason: failed to connect server: {}@{}:{}'.format(
                delete_file, username, test_ip, test_port))
            return RtnStatusEnum.FAIL.value

        if delete_file:
            if isinstance(delete_file, list):
                delete_file = ' '.join(delete_file)
            try:
                delete_rtn, _ = FileOperation.delete_file(path=delete_file, ip=test_ip, port=test_port,
                                                          username=username, match_flag=match_flag,
                                                          localpath_flag=local_execute, file_check_flag=False)
            except Exception as e:
                log.error('Found exception during delete file: {}, exception: {}'.format(delete_file, e))
                delete_rtn = RtnStatusEnum.FAIL.value

            if RtnStatusEnum.SUCCESS.value == delete_rtn:
                log.debug('Success to delete file: {}.'.format(delete_file))
            else:
                log.warning('Fail to delete file: {}.'.format(delete_file))
                rtn_delete = RtnStatusEnum.FAIL.value
        else:
            log.debug('Not need to delete file, file list is null.')

        return rtn_delete

    def __set_host_delete_files_parameters(self) -> None:
        """
        author: luyafei
        date: 2021.01.02
        description: 获取host宿主机端要删除的日志
        :return: None

        @changelog      2021-03-24 14:11:42  haibin.xu
                        1. 优化函数实现
        """
        self.host_delete_files = []

        find_host_files_cmd = None

        self.__get_node_info()

        if (libs_constants.TEST_ENTRY_IOC == self.test_entry) and (libs_constants.TEST_OBJECT_EXPANDER ==
                                                                   self.test_object):
            self.host_delete_files.append(CommandOperation.format_linux_path_sep(os.path.join(
                constants.SIMULATOR_EXP_CLI_ROOT, str(self.exp_port), constants.SIMULATOR_EXP_EXP_EXPORT_LOG)))
            self.host_delete_files.append(CommandOperation.format_linux_path_sep(os.path.join(
                libs_constants.EXPANDER_CLI_ROOT, str(self.exp_port), libs_constants.EXPANDER_LOG)))
            self.host_delete_files.append(CommandOperation.format_linux_path_sep(os.path.join(
                libs_constants.EXPANDER_CLI_ROOT, str(self.exp_port), constants.CORE_FILES_NAME)))
        elif libs_constants.TEST_OBJECT_PCIE_SWITCH == self.test_object:
            find_host_files_cmd = 'find /opt/ps3swsim/log -name "ps3sas_{}.log_*" | grep ps3sas_{}.log_...' \
                .format(self.host_node_name, self.host_node_name) if self.host_node_name is not None else None
        elif libs_constants.HOST_CPU_X86 == self.host_cpu:
            find_host_files_cmd = 'find /opt/ps3sim/bin/log -name "ps3sas_{}.log_*" |grep ps3sas_{}.log_...' \
                .format(self.host_node_name, self.host_node_name) if self.host_node_name is not None else None
        elif self.host_cpu == libs_constants.HOST_CPU_ARM:
            find_host_files_cmd = 'find /opt/ps3sim/log -name "ps3sas_{}.log_*" | grep ps3sas_{}.log_...'.format(
                self.host_node_name, self.host_node_name) if self.host_node_name is not None else None
        else:
            log.error('Fail get find host files command. test object: {}, host cpu: {}.'.format(self.test_object,
                                                                                                self.host_cpu))
            exit(1)

        if find_host_files_cmd is not None:
            try:
                rtn_code, host_files = FileOperation.get_files_with_cmd(find_files_cmd=find_host_files_cmd,
                                                                        ip=self.host_ip)
            except Exception as e:
                log.error('Found exception during get files: {}, exception: {}'.format(find_host_files_cmd, e))
                rtn_code, host_files = RtnStatusEnum.FAIL.value, []

            if RtnStatusEnum.SUCCESS.value == rtn_code:
                self.host_delete_files.extend(host_files)
            else:
                log.warning('Fail to find host files to be deleted.')

        # 如果是物理平台清理
        if self.test_platform == constants.ENV_PLATFORM_REAL:
            self.host_delete_files.append('/var/log/fwlog*')
            self.host_delete_files.append('/var/log/drvlog/fwlog*')

        self.host_delete_files.append('/var/log/ps3agent_lib.log.hex.*')
        self.host_delete_files.append('/var/log/ps3agent_lib.log.*')
        self.host_delete_files.append('/var/log/ps3agent_server.log.*')
        self.host_delete_files.append('/usr/local/logs/sos/sos-*.log')
        self.host_delete_files.append('/usr/local/logs/wmgr/wmgr-*.log')

        log.info('Get host files to be deleted: {}.'.format(self.host_delete_files))

    def __set_host_clean_files_parameters(self) -> None:
        """
        author: luyafei
        date: 2021.01.02
        description: 获取host宿主机端要清理的日志
        :return: None

        @changelog      2021-03-24 15:16:33  haibin.xu
                        1. 优化函数实现, 函数名更正：host_server_clear_log_get -> __set_host_clean_files_parameters
        """
        self.host_clean_files = []
        find_host_files_cmd = None
        success_get_flag = True

        if libs_constants.TEST_OBJECT_PCIE_SWITCH == self.test_object:
            self.host_clean_files.append(libs_constants.HOST_PCIE_SWITCH_CLEAN_FILE_PATH)
        elif self.host_cpu == libs_constants.HOST_CPU_X86:
            find_host_files_cmd = 'find {}'.format(libs_constants.HOST_CLEAN_FILE_PATH)
        elif self.host_cpu == libs_constants.HOST_CPU_ARM:
            self.__get_node_info()
            find_host_files_cmd = 'find /opt/ps3sim/log -name "ps3sas_{0}.log_*" | grep ps3sas_{0}.log_.$'.format(
                self.host_node_name) if self.host_node_name is not None else None

        if find_host_files_cmd is not None:
            try:
                rtn_code, host_files = FileOperation.get_files_with_cmd(find_files_cmd=find_host_files_cmd,
                                                                        ip=self.host_ip)
            except Exception as e:
                log.error('Found exception during get files: {}, exception: {}'.format(find_host_files_cmd, e))
                rtn_code, host_files = RtnStatusEnum.FAIL.value, []

            if RtnStatusEnum.SUCCESS.value == rtn_code:
                self.host_clean_files.extend(host_files)
            else:
                success_get_flag = False
                log.warning('Fail to find host files to be clean.')

        if success_get_flag:
            log.info('Get host files to be clean: {}.'.format(self.host_clean_files))

    def __set_host_qemu_delete_files_parameters(self) -> None:
        """
        author:      haibin.xu
        date:        2021-03-27 14:18:38
        description: 设置host节点要删除的日志
        :return:     None
        @changelog  2021-11-26 yafei.lu
        1. 优化主机驱动删除的文件信息
        """
        # TODO luyafei modification
        if 'windows' not in libs_constants.HOST_OS:
            self.host_qemu_delete_files = [libs_constants.LOG_COLL_HOST_NODE_CRASH_FILE_PATH,
                                           constants.TEST_TOOL_HOST_CLI_ERROR_PATH]
            # 如果是模拟平台
            if self.test_platform == constants.ENV_PLATFORM_SIMU:
                self.host_qemu_delete_files.append(libs_constants.LOG_COLL_HOST_NODE_DRIVER_LOG_PATH)
        else:
            self.host_qemu_delete_files = [constants.WINDOWS_SIMULATOR_HOST_DRIVER_LOG_DELETE_PATH,
                                           constants.WINDOWS_TEST_TOOL_HOST_CLI_ERROR_PATH]
        self.host_qemu_delete_files.extend(self.drv_delete_files)
        log.info('Get host qemu files to be deleted: {}.'.format(self.host_qemu_delete_files))

    def __set_host_qemu_clean_files_parameters(self) -> None:
        """
        author:      haibin.xu
        date:        2021-03-27 14:19:38
        description: 设置host节点要清理的日志
        :return:     None
        @changelog  2021-11-26 yafei.lu
        1. 优化主机驱动清理的文件信息
        """
        # TODO luyafei modification
        self.host_qemu_clean_files = self.drv_clean_files
        log.info('Get host qemu files to be clean: {}.'.format(self.host_qemu_clean_files))

    def set_host_files(self) -> None:
        """
        author:      haibin.xu
        date:        2021-03-27 14:12:39
        description: 获取host宿主机端需要删除和清空的文件列表

        :return:     None
        """
        self.__set_host_delete_files_parameters()
        self.__set_host_clean_files_parameters()

    def set_host_qemu_files(self) -> None:
        """
        author:      haibin.xu
        date:        2021-03-27 14:17:03
        description: 设置host节点需要删除和清空的文件列表

        :return:     None
        """
        self.__get_drv_delete_clean_files()
        self.__set_host_qemu_delete_files_parameters()
        self.__set_host_qemu_clean_files_parameters()

    def __set_ioc_delete_files_parameters(self) -> None:
        """
        author:      haibin.xu
        date:        2021-03-27 15:53:57
        description: 设置ioc宿主机要删除的日志
        :return:     None
        """
        self.ioc_delete_files = []
        if self.exp_topo_template:
            self.__get_node_info()
            if self.ioc_node_id is not None:
                ioc_server_exp_log_files = '/opt/ps3sim/iocnode{}_expander/*.log'.format(self.ioc_node_id)
                self.ioc_delete_files.append(ioc_server_exp_log_files)
                ioc_server_exp_directorys = '/opt/ps3sim/iocnode{}_expander/simuExpander_*'.format(self.ioc_node_id)
                self.ioc_delete_files.append(ioc_server_exp_directorys)

                if (TestEntryStrEnum.HOST.value == self.test_entry) and \
                        (CompileObjectStrEnum.EXPANDER.value == self.compile_object) and \
                        (self.test_object in [TestObjectStrEnum.EXPANDER.value, TestObjectStrEnum.RAID.value,
                                              TestObjectStrEnum.HBA.value]):
                    ioc_server_exp_core_files = '/opt/ps3sim/iocnode{}_expander/{}'.format(
                        self.ioc_node_id, constants.CORE_FILES_NAME)
                    self.ioc_delete_files.append(ioc_server_exp_core_files)

        if self.test_object == libs_constants.TEST_OBJECT_PCIE_SWITCH:
            # PCIE SWITCH测试，删除ioc宿主机日志
            self.__get_node_info()
            self.ioc_delete_files.extend([
                constants.SIMULATOR_IOC_SERVER_PCIESWITCH_LOG_CLEAR_PATH.format(self.ioc_node_name,
                                                                                self.ioc_node_name),
                constants.SIMULATOR_IOC_SERVER_SIMUSWITCH_LOG_CLEAR_PATH.format(self.ioc_node_name,
                                                                                self.ioc_node_name)
            ] if self.ioc_node_name is not None else [])

        log.info('Get ioc files to be deleted: {}.'.format(self.ioc_delete_files))

    def __set_ioc_clean_files_parameters(self) -> None:
        """
        author:      haibin.xu
        date:        2021-03-27 15:54:11
        description: 设置ioc宿主机要清理的日志
        :return:     None
        """
        self.ioc_clean_files = []

        # if self.test_object == libs_constants.TEST_OBJECT_PCIE_SWITCH:
        #     # PCIE SWITCH测试，清理ioc宿主机日志
        #     self.__get_node_info()
        #     self.ioc_clean_files = [
        #         constants.SIMULATOR_IOC_SERVER_PCIESWITCH_LOG_CLEAR_PATH.format(self.ioc_node_name,
        #                                                                         self.ioc_node_name),
        #         constants.SIMULATOR_IOC_SERVER_SIMUSWITCH_LOG_CLEAR_PATH.format(self.ioc_node_name,
        #                                                                         self.ioc_node_name)
        #     ] if self.ioc_node_name is not None else []

        log.info('Get ioc files to be clean: {}.'.format(self.ioc_clean_files))

    def __set_ioc_qemu_delete_files_parameters(self) -> None:
        """
        author:      haibin.xu
        date:        2021-03-27 15:53:57
        description: 设置ioc节点要删除的日志
        :return:     None

        @change log:    constants.SIMULATOR_IOC_COLLECT_PATH 从日志清理中去除，
                        后面如需填写请与全部组长确认，并说明原因  2021-12- 15:53:57
        """
        self.ioc_qemu_delete_files = []

        if (libs_constants.TEST_OBJECT_PCIE_SWITCH != self.test_object) and \
                ((self.test_entry != constants.ENV_TEST_ENTRY_IOC) or
                 (self.test_object != constants.ENV_TEST_OBJECT_EXPANDER)):
            # 非pcie switch 和 expander测试时，需要删除ioc qemu端日志
            self.ioc_qemu_delete_files = [libs_constants.LOG_COLL_IOC_CORE_FILE_PATH,
                                          constants.SIMULATOR_IOC_CRASH_LOG_DELETE_PATH,
                                          constants.SIMULATOR_IOC_PSTACK_DELETE_PATH]
            """
            find_ioc_log_cmd = 'find /etc/ps3sim/log -name "iocNode.log_*" | grep iocNode.log_...$'
            try:
                _, files_list = FileOperation.get_files_with_cmd(find_files_cmd=find_ioc_log_cmd,
                                                                 ip=self.ioc_qemu_ip, port=self.ioc_port)
                self.ioc_qemu_delete_files.extend(files_list)
            except Exception as e:
                log.error('Found exception during get files: {}, exception: {}'.format(find_ioc_log_cmd, e))
            """
            if self.package_install and self.package_path:
                self.ioc_qemu_delete_files.append(constants.SIMULATOR_IOC_PS3_LOG_DELETE_PATH)

        self.ioc_qemu_delete_files.append('/var/log/ps3_log/asan_log*')

        log.debug('Get ioc qemu files to be deleted: {}.'.format(self.ioc_qemu_delete_files))

    def __set_ioc_qemu_clean_files_parameters(self) -> None:
        """
        author:      haibin.xu
        date:        2021-03-27 15:54:11
        description: 设置ioc节点要清理的日志
        :return:     None
        """
        self.ioc_qemu_clean_files = []
        return
        if (libs_constants.TEST_OBJECT_PCIE_SWITCH != self.test_object) and \
                ((self.test_entry != constants.ENV_TEST_ENTRY_IOC) or
                 (self.test_object != constants.ENV_TEST_OBJECT_EXPANDER)):
            # 非pcie switch 和 expander测试时，需要清理ioc qemu端日志
            find_files_cmd = 'find /etc/ps3sim/log -name "iocNode.log_*" | grep iocNode.log_.$'
            try:
                _, files_list = FileOperation.get_files_with_cmd(find_files_cmd=find_files_cmd, ip=self.ioc_qemu_ip,
                                                                 port=self.ioc_port)
                self.ioc_qemu_clean_files = files_list
            except Exception as e:
                log.error('Found exception during get files: {}, exception: {}'.format(find_files_cmd, e))

        log.info('Get ioc qemu files to be clean: {}.'.format(self.ioc_qemu_clean_files))

    def set_ioc_files(self) -> None:
        """
        author:      haibin.xu
        date:        2021-03-27 15:49:51
        description: 设置ioc宿主机端需要删除和清空的文件列表

        :return:     None
        """
        self.__set_ioc_delete_files_parameters()
        self.__set_ioc_clean_files_parameters()

    def set_ioc_qemu_files(self) -> None:
        """
        author:      haibin.xu
        date:        2021-03-27 15:52:07
        description: 设置ioc节点需要删除和清空的文件列表

        :return:     None
        """
        self.__set_ioc_qemu_delete_files_parameters()
        self.__set_ioc_qemu_clean_files_parameters()

    def init_log_files(self) -> None:
        """
        author:panpan.du
        date:2020.10.15
        description: 清空或删除host, ioc, host qemu, ioc qemu端的日志文件
        :return: 无返回值

        @changelog      2021-03-27 16:51:12  haibin.xu
                        1. 优化函数实现，函数名修正：files_log_clear -> init_log_files
        """
        # 获取host宿主机端文件列表，并删除或清空
        self.set_host_files()
        self.delete_files(self.host_delete_files, self.host_ip)
        self.clean_files(self.host_clean_files, self.host_ip)

        # 获取host qemu端文件列表，并删除或清空
        self.set_host_qemu_files()
        self.delete_files(self.host_qemu_delete_files, self.host_qemu_ip, self.host_port)
        self.clean_files(self.host_qemu_clean_files, self.host_qemu_ip, self.host_port)
        self.delete_files(self.drv_delete_files, self.host_qemu_ip, self.host_port)

        # 获取ioc宿主机端文件列表，并删除或清空
        self.set_ioc_files()
        self.delete_files(self.ioc_delete_files, self.ioc_ip)
        self.clean_files(self.ioc_clean_files, self.ioc_ip)

        # 获取ioc qemu端文件列表，并删除或清空
        if constants.ENV_TEST_OBJECT_PCIE_SWITCH != self.test_object:
            self.set_ioc_qemu_files()
            self.delete_files(self.ioc_qemu_delete_files, self.ioc_qemu_ip, self.ioc_port)
            self.clean_files(self.ioc_qemu_clean_files, self.ioc_qemu_ip, self.ioc_port)

    def __check_new_files(self, file_path: str, ip: str, port: str = '22', directory_name: str = None,
                          server_msg: str = None) -> bool:
        """
        author:      haibin.xu
        date:        2021-04-09 12:46:39
        description: 检查新文件操作

        :param file_path: 文件路径
        :param ip:   文件所在ip
        :param port: 端口
        :param directory_name: 目录名称
        :param server_msg: server 信息
        :return:     返回文件是否存在
        """
        new_files_flag = False

        try:
            _, files = FileOperation.get_files(file_path=file_path, ip=ip, port=port)
        except Exception as e:
            log.error('Found exception during get files: {}. exception: {}.'.format(file_path, e))
            files = []

        if files:
            log.info('Finish get {} files: {}'.format(server_msg, files))
            new_files = list(set(files).difference(
                set(self.qemu_crash_core_initial_data[directory_name])))
            if len(new_files) > 0:
                new_files_flag = True
                self.qemu_crash_core_initial_data[directory_name] = files
                log.info('Finish get new {} files: {}.'.format(server_msg, new_files))
            else:
                log.info('Not found new {} files.'.format(server_msg))
        else:
            log.warning('Fail to get {} files.'.format(server_msg))

        return new_files_flag

    def check_new_host_qemu_crash_files(self) -> bool:
        """
        :author:panpan.du
        :date:2020.10.11
        :description: 检查模拟平台host节点是否生成新的core、crash日志
        :return: 文件列表

        @changelog      2021-03-27 16:55:48  haibin.xu
                        1. 优化函数实现，函数名修正：check_simulator_host_crash_exist -> check_new_host_qemu_crash_files
        """
        if 'windows' in self.host_os:
            return False

        new_crash_files_flag = self.__check_new_files(file_path=libs_constants.LOG_COLL_HOST_CRASH_FILE_PATH,
                                                      ip=self.host_qemu_ip, port=self.host_port,
                                                      directory_name=libs_constants.LOG_COLL_HOST_CRASH_DIR,
                                                      server_msg='host qemu crash')

        return new_crash_files_flag

    def check_new_ioc_qemu_crash_files(self) -> bool:
        """
        :author:panpan.du
        :date:2020.10.11
        :description: 检查模拟平台ioc端是否生成新的crash日志
        :return: 文件列表

        @changelog      2021-03-27 18:01:24  haibin.xu
                        1. 优化函数实现, check_simulator_ioc_crash_exist -> check_new_ioc_qemu_crash_files
        """
        if constants.ENV_TEST_OBJECT_PCIE_SWITCH != self.test_object:
            new_ioc_crash_flag = self.__check_new_files(file_path=libs_constants.LOG_COLL_IOC_CRASH_FILE_PATH,
                                                        ip=self.ioc_qemu_ip, port=self.ioc_port,
                                                        directory_name=libs_constants.LOG_COLL_IOC_CRASH_DIR,
                                                        server_msg='ioc qemu crash')
        else:
            log.info('Pcie switch test, not to check ioc crash file.')
            new_ioc_crash_flag = False

        return new_ioc_crash_flag

    def check_new_ioc_qemu_core_files(self) -> bool:
        """
        :author:panpan.du
        :date:2020.10.11
        :description: 检查模拟平台ioc节点是否生成新的core日志
        :return: 文件列表

        @changelog      2021-03-27 17:11:13  haibin.xu
                        1. 优化函数实现，函数名修正：check_simulator_ioc_core_exis -> check_new_ioc_qemu_core_files
        """
        if constants.ENV_TEST_OBJECT_PCIE_SWITCH != self.test_object:
            core_path = CommandOperation.format_linux_path_sep(os.path.join(
                constants.SIMULATOR_IOC_CORE_LOG_ROOT_PATH, constants.CORE_FILES_NAME))
            new_core_files_flag = self.__check_new_files(
                file_path=core_path, ip=self.ioc_qemu_ip, port=self.ioc_port,
                directory_name=libs_constants.LOG_COLL_IOC_CORE_DIR, server_msg='ioc qemu core')
        else:
            log.info('Pcie switch test, not to check ioc core file.')
            new_core_files_flag = False

        return new_core_files_flag

    def check_new_rtems_ioc_core_files(self, target_ip: str) -> bool:
        """
        :author:
        :date:2021.3.30
        :description: 检查模拟平台rtems ioc节点是否生成新的core日志
        :return: 文件列表

        @changelog      2021-03-27 18:02:50  haibin.xu
                        1. 优化函数实现, check_simulator_rtems_soc_core_exist -> check_new_rtems_ioc_core_files
        """
        new_core_flag = False

        # 获取日志路径
        if libs_constants.TEST_OBJECT_PCIE_SWITCH == self.test_object:
            self.__get_node_info()
            log_path = '/opt/ps3swsim/{}'.format(self.ioc_node_name) if self.ioc_node_name is not None else ''

            # 检查soc端日志中是否生成core文件
            get_core_issue_cmd = 'timeout 180 cat -A {}/simu*.log |grep "*** FATAL ***" | wc -l'.format(log_path)
            try:
                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=get_core_issue_cmd, ssh_ip=target_ip, ssh_port='22')
                rtn_code = CommandOperation.check_cli_output(get_core_issue_cmd, cmd_code, cmd_stdout, cmd_stderr)
            except Exception as e:
                log.error('Found exception during check rtems ioc files, exception: {}'.format(e))
                rtn_code, cmd_stdout = RtnStatusEnum.FAIL.value, 0

            if (RtnStatusEnum.SUCCESS.value == rtn_code) and (0 < int(cmd_stdout)):
                log.info('Finish get rtems soc core issue: {}.'.format(cmd_stdout))
                get_core_info_cmd = 'timeout 180 cat -A {}/simu*.log |grep "*** FATAL ***" -A 20 -B 20'.\
                    format(log_path)
                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=get_core_info_cmd, ssh_ip=target_ip, ssh_port='22')
                rtn_code = CommandOperation.check_cli_output(get_core_info_cmd, cmd_code, cmd_stdout, cmd_stderr)
                if RtnStatusEnum.SUCCESS.value == rtn_code:
                    log.info('Finish get rtems ioc core info:\n{}'.format(cmd_stdout))
                    new_core_flag = True
                else:
                    log.warning('Fail to get rtems soc core info.')
            else:
                log.warning('Not found rtems ioc core info.')
        # expander 修改成linux版本后模拟平台不再从日志中找core，而是在maintest路径下找 core文件，物理环境从日志中找core
        elif libs_constants.TEST_OBJECT_EXPANDER == self.test_object:
            if self.test_platform == constants.ENV_PLATFORM_REAL:
                self.__get_node_info()
                # 获取当前日志文件
                get_log_file_cmd = "timeout 60 ps -ef | grep tty | grep minicom_log | grep -v grep " \
                                   "| awk '{print $NF}'"
                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=get_log_file_cmd, ssh_ip=target_ip, ssh_port='22')
                rtn_code = CommandOperation.check_cli_output(get_log_file_cmd, cmd_code, cmd_stdout, cmd_stderr)
                if RtnStatusEnum.SUCCESS.value == rtn_code:
                    log_file_list = cmd_stdout.split("\n")
                    core_mark = "Beginning of core dump"
                    log_mark = ""
                    for log_file in log_file_list:
                        if ".log" not in log_file:
                            continue
                        # 检查日志中是否生成core信息
                        get_core_issue_cmd = "timeout 180 cat -A {} |grep '{}' -B 20".format(log_file, core_mark)
                        try:
                            cmd_code, cmd_stdout, cmd_stderr = \
                                CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=get_core_issue_cmd, ssh_ip=target_ip, ssh_port='22')
                            rtn_code = CommandOperation.check_cli_output(
                                get_core_issue_cmd, cmd_code, cmd_stdout, cmd_stderr)
                            if RtnStatusEnum.SUCCESS.value == rtn_code:
                                log.info('Finish get expander core info:\n{}'.format(cmd_stdout))
                                if core_mark in cmd_stdout:
                                    log_mark += cmd_stdout
                        except Exception as e:
                            log.error('Found exception during check expander log files, exception: {}'.format(e))
                    if log_mark:
                        core_file_path = "/home/core"
                        get_mark_cmd = "mkdir -p {};cat {}/log_mark".format(core_file_path, core_file_path)
                        cmd_code, cmd_stdout, cmd_stderr = \
                            CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=get_mark_cmd, ssh_ip=target_ip, ssh_port='22')
                        rtn_code = CommandOperation.check_cli_output(
                            get_mark_cmd, cmd_code, cmd_stdout, cmd_stderr)
                        if not (RtnStatusEnum.SUCCESS.value == rtn_code and cmd_stdout == log_mark):
                            save_mark_cmd = "timeout 180 echo '{}' > {}/log_mark".format(
                                log_mark, core_file_path)
                            cmd_code, cmd_stdout, cmd_stderr = \
                                CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=save_mark_cmd, ssh_ip=target_ip, ssh_port='22')
                            rtn_code = CommandOperation.check_cli_output(
                                save_mark_cmd, cmd_code, cmd_stdout, cmd_stderr)
                            # down load core file from core dump area
                            retry = 5
                            while retry:
                                get_sg_cmd = "lsscsi -g | grep enclosu | awk '{print $NF}'"
                                cmd_code, cmd_stdout, cmd_stderr = \
                                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                                        cmd=get_sg_cmd, ssh_ip=target_ip, ssh_port='22')
                                rtn_code = CommandOperation.check_cli_output(
                                    save_mark_cmd, cmd_code, cmd_stdout, cmd_stderr)
                                if RtnStatusEnum.SUCCESS.value == rtn_code and "/dev/sg" in cmd_stdout:
                                    sg_list = cmd_stdout.split("\n")
                                    for sg in sg_list:
                                        if "/dev/sg" in sg:
                                            read_core_cmd = "sg_read_buffer {} -m 2 -i 0x8e -l 4m -r > " \
                                                            "{}/core_dump_{}.bin".format(sg,
                                                                                         core_file_path, time.time())
                                            cmd_code, cmd_stdout, cmd_stderr = \
                                                CommandOperation.execute_command_based_paramiko_with_rtncode(
                                                    cmd=read_core_cmd, ssh_ip=target_ip, ssh_port='22')
                                            rtn_code = CommandOperation.check_cli_output(
                                                save_mark_cmd, cmd_code, cmd_stdout, cmd_stderr)
                                    break
                                retry -= 1
                                time.sleep(30)
                            new_core_flag = self.__check_new_files(
                                file_path=core_file_path, ip=target_ip,
                                directory_name=libs_constants.LOG_COLL_EXP_CORE_DIR,
                                server_msg='exp core')
            else:
                # hba/raid + exp环境
                if libs_constants.TEST_ENTRY_HOST == self.test_entry:
                    self.__get_node_info()
                    exp_root_path = '/opt/ps3sim/iocnode{}_expander/'.format(self.ioc_node_id) \
                        if self.ioc_node_id is not None else ''
                    target_ip = self.ioc_ip
                # 单独exp环境
                else:
                    exp_root_path = CommandOperation.format_linux_path_sep(
                        os.path.join(constants.SIMULATOR_EXP_CLI_ROOT, self.exp_port))
                    target_ip = self.host_ip

                core_path = CommandOperation.format_linux_path_sep(os.path.join(exp_root_path,
                                                                                constants.CORE_FILES_NAME))
                new_core_flag = self.__check_new_files(file_path=core_path, ip=target_ip,
                                                       directory_name=libs_constants.LOG_COLL_EXP_CORE_DIR,
                                                       server_msg='exp core')
            log.info('get exp core：{}'.format(new_core_flag))

        return new_core_flag

    def __get_ip_port(self) -> tuple:
        """
        author:      haibin.xu
        date:        2021-03-29 09:15:01
        description: 获取ip, port，用于ps3server中log目录名的生成

        :return:     返回ip, port
        """
        if constants.ENV_TEST_ENTRY_HOST == self.test_entry:
            ip = self.host_ip
            port = self.host_port
        elif (constants.ENV_TEST_ENTRY_IOC == self.test_entry) and \
                (constants.ENV_TEST_OBJECT_EXPANDER != self.test_object):
            ip = self.ioc_ip
            port = self.ioc_port
        elif (constants.ENV_TEST_ENTRY_IOC == self.test_entry) and \
                (constants.ENV_TEST_OBJECT_EXPANDER == self.test_object):
            ip = self.host_ip
            port = self.exp_port
        else:
            log.warning('Invalid test_entry: {}'.format(self.test_entry))
            ip = 'ip'
            port = 'port'

        return ip, port

    @staticmethod
    def __get_date_time(start_timestamp: float = None) -> tuple:
        """
        author:      haibin.xu
        date:        2021-03-29 09:20:10
        description: 获取当前日期、时间，用于ps3server中log目录名的生成
        :param start_timestamp: 给定的时间戳

        :return:     返回当前日期、时间
        """

        local_time = time.localtime(start_timestamp) if start_timestamp else time.localtime()
        log_dir_date = time.strftime('%Y_%m_%d', local_time)
        log_dir_time = time.strftime('%H_%M_%S', local_time)

        return log_dir_date, log_dir_time

    def make_log_root_directory_in_log_server(self, start_timestamp: float = None) -> str:
        """
        author:DuPanPan
        date:2020-04-26
        description:在日志服务器上创建日志基本路径
        :return return self.log_root_dir_path:日志基本路径

        @changelog      2021-03-29 09:31:18  haibin.xu
                        1. 优化函数实现, 函数名修正：log_root_dir_init -> make_log_root_directory_in_log_server
        """
        ip, port = self.__get_ip_port()
        log_dir_date, log_dir_time = self.__get_date_time(start_timestamp)

        log_directory_name = '_'.join([str(self.test_entry), str(self.host_label), str(ip), str(port)])
        print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
        log.info(f"LOG_ROOT_PATH is :{constants.LOG_ROOT_PATH}")
        log.info(f"log_directory_name is :{log_directory_name}")
        log.info(f"log_dir_date is :{log_dir_date}")
        log.info(f"log_dir_time is :{log_dir_time}")
        self.log_root_dir_path = CommandOperation.format_linux_path_sep(os.path.join(
            constants.LOG_ROOT_PATH, log_directory_name, log_dir_date, log_dir_time))
        log.info(f"log_root_dir_path is :{self.log_root_dir_path}")
        print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
        try:
            mkdir_result = FileOperation.make_directory(dir_name=self.log_root_dir_path, ip=self.log_server_ip,
                                                        username=self.log_server_account, match_flag=False,
                                                        port=str(port))
        except Exception as e:
            log.error('Found exception during make directory: {}, exception: {}'.format(self.log_root_dir_path, e))
            mkdir_result = RtnStatusEnum.FAIL.value

        if RtnStatusEnum.SUCCESS.value == mkdir_result:
            log.info('Finish to make directory in log server[{}@{}:{}]: {}.'.format(
                self.log_server_account, self.log_server_ip, '22', self.log_root_dir_path))
        else:
            log.error('Fail to make directory in log server[{}@{}:{}]: {}.'.format(
                self.log_server_account, self.log_server_ip, '22', self.log_root_dir_path))
            self.log_root_dir_path = ''

        return self.log_root_dir_path

    @staticmethod
    def get_filename_from_path(file_path: str = None) -> tuple:
        """
        author:      haibin.xu
        date:        2021-03-29 09:56:06
        description: 从文件的绝对路径中获取文件名

        :param file_path: 文件路径
        :return:     返回文件名
        """
        if file_path is not None:
            file_name_with_extension = os.path.basename(file_path)
            filename, extension = os.path.splitext(file_name_with_extension)
        else:
            filename = None
            extension = None

        return filename, extension

    def make_script_directory_in_log_server(self, script_name: str = None) -> str:
        """
        author:DuPanPan
        date:2020-09-27
        description:在日志服务器上创建脚本级日志基本路径
        :return :日志文件基本路径

        @changelog      2021-03-29 10:06:47  haibin.xu
                        1. 优化函数实现, log_script_dir_init -> make_script_directory_in_log_server
        """
        # 获取脚本名称
        if script_name is None:
            script_name = 'manual_collect_log'
        else:
            script_name, _ = self.get_filename_from_path(script_name)
            log_dir_date, log_dir_time = self.__get_date_time()
            script_name = script_name + "_" + log_dir_date + "_" + log_dir_time
        self.log_script_dir_path = CommandOperation.format_linux_path_sep(os.path.join(self.log_root_dir_path,
                                                                                       script_name))

        try:
            mkdir_result = FileOperation.make_directory(dir_name=self.log_script_dir_path, ip=self.log_server_ip,
                                                        username=self.log_server_account, match_flag=False)
        except Exception as e:
            log.error('Found exception during make directory: {}, exception: {}'.format(self.log_script_dir_path, e))
            mkdir_result = RtnStatusEnum.FAIL.value

        if RtnStatusEnum.SUCCESS.value == mkdir_result:
            log.info('Finish to make script directory in log server[{}@{}:{}]: {}.'.format(
                self.log_server_account, self.log_server_ip, '22', self.log_script_dir_path))
            if self.__env_config_dict is not None:
                self.__env_config_dict[constants.ENV_LOG_SERVER_IP] = self.log_script_dir_path
        else:
            log.error('Fail to make script directory in log server[{}@{}:{}]: {}.'.format(
                self.log_server_account, self.log_server_ip, '22', self.log_script_dir_path))

        return self.log_script_dir_path

    def __collect_log_in_current_directory(self, log_dict: dict = None, collect_to_path: str = None,
                                           server_msg: str = None, username: str = 'root', ip: str = None,
                                           port: str = '22', localpath_flag: bool = False) -> bool:
        """
        author:      haibin.xu
        date:        2021-04-09 14:27:48
        description: 当前log路径下，归纳日志

        :param log_dict: log信息
        :param collect_to_path: log要拷贝的路径
        :param server_msg: server 信息
        :param username: log所在server 的用户名
        :param ip:   log所在server ip
        :param port: log所在server port
        :param localpath_flag: 是否本地路径
        :return:     返回是否成功收集到日志

        @changelog      2021-05-26 11:21:19  haibin.xu
                        1. 优化函数实现, 更新文件查找方法
        """
        # 如果 字典为空，则不需要收集
        if not log_dict:
            return True

        if CommandOperation.check_windows_cmd(ssh_ip=ip, local_execute_flag=localpath_flag):
            return self.__collect_log_in_current_directory_for_windows(
                log_dict=log_dict, collect_to_path=collect_to_path, server_msg=server_msg, username=username,
                ip=ip, port=port, localpath_flag=localpath_flag)

        collect_log_flag = False
        target_path = None
        temp_log_dict = {}

        # 将拷贝目标目录相同的文件归类，以便后续统一拷贝
        for source_file, target_directory in log_dict.items():
            if target_directory not in temp_log_dict.keys():
                temp_log_dict.update({target_directory: [source_file]})
            else:
                temp_log_dict[target_directory].append(source_file)

        for target_directory, source_file in temp_log_dict.items():
            mkdir_flag = False
            source_file = ' '.join(source_file)
            # 判断文件是否存在
            try:
                _, found_file = FileOperation.find_files(path=source_file, ip=ip, port=port,
                                                         path_flag=localpath_flag)
            except Exception as e:
                log.error('Found exception during check file: {}, exception: {}'.format(source_file, e))
                found_file = ''

            if found_file:
                file_exist_flag = True
                log.debug('Found file: {}, in {} server: {}@{}:{}'.format(source_file, server_msg, username, ip,
                                                                          port))
            else:
                file_exist_flag = False
                log.warning('Not found file: {}, in {} server: {}@{}:{}'.format(source_file, server_msg, username,
                                                                                ip, port))

            if file_exist_flag:
                # 文件存在，创建目标文件夹
                target_path = CommandOperation.format_linux_path_sep(os.path.join(collect_to_path, target_directory))
                # 创建收集文件的目标文件夹
                try:
                    rtn_mkdir_flag = FileOperation.make_directory(dir_name=target_path, local_execute=localpath_flag,
                                                                  ip=ip, port=port, username=username,
                                                                  match_flag=False)
                except Exception as e:
                    log.error('Found exception during make directory: {}, exception: {}'.format(target_path, e))
                    rtn_mkdir_flag = RtnStatusEnum.FAIL.value

                if RtnStatusEnum.SUCCESS.value == rtn_mkdir_flag:
                    mkdir_flag = True
                    log.debug('Success to make directory: {}, in {} server: {}@{}:{}'.format(target_path, server_msg,
                                                                                             username, ip, port))
                else:
                    mkdir_flag = False
                    log.error('Fail to make directory: {}, in {} server: {}@{}:{}'.format(target_path, server_msg,
                                                                                          username, ip, port))

            if mkdir_flag:
                # 目标文件夹创建成功，拷贝文件
                try:
                    rtn_mkln_flag = FileOperation.create_symbolic_link(source_path=found_file,
                                                                       link_directory_path=target_path,
                                                                       local_execute_flag=localpath_flag,
                                                                       ssh_ip=ip, ssh_port=port,
                                                                       path_check_flag=False)
                except Exception as e:
                    log.error('Found exception during create link file save in path: {}, link to source path: {}, '
                              'exception: {}'.format(target_path, found_file, e))
                    rtn_mkln_flag = RtnStatusEnum.FAIL.value

                if RtnStatusEnum.SUCCESS.value == rtn_mkln_flag:
                    collect_log_flag = True
                    log.debug('Success to create link file save in path: {}, link to source path: {}, in {} server: '
                              '{}@{}:{}'.format(target_path, found_file, server_msg, username, ip, port))
                else:
                    log.error('Fail to create link file save in path: {}, link to source path: {}, in {} server: '
                              '{}@{}:{}'.format(target_path, found_file, server_msg, username, ip, port))

        return collect_log_flag

    def __collect_log_in_current_directory_for_windows(self, log_dict: dict = None, collect_to_path: str = None,
                                                       server_msg: str = None, username: str = 'root', ip: str = None,
                                                       port: str = '22', localpath_flag: bool = False) -> bool:
        """
        author:      zhilong.zhang
        date:        2021-04-09 14:27:48
        description: 当前log路径下，归纳日志(仅适用于windows host qemu)

        :param log_dict: log信息
        :param collect_to_path: log要拷贝的路径
        :param server_msg: server 信息
        :param username: log所在server 的用户名
        :param ip:   log所在server ip
        :param port: log所在server port
        :param localpath_flag: 是否本地路径
        :return:     返回是否成功收集到日志
        """
        collect_log_flag = False
        target_path = None
        temp_log_dict = {}

        # 将拷贝目标目录相同的文件归类，以便后续统一拷贝
        for source_file, target_directory in log_dict.items():
            if target_directory not in temp_log_dict.keys():
                temp_log_dict.update({target_directory: [source_file]})
            else:
                temp_log_dict[target_directory].append(source_file)

        for target_directory, source_file in temp_log_dict.items():
            source_file = ','.join(source_file)

            # 创建收集文件的目标文件夹
            target_path = CommandOperation.format_linux_path_sep(os.path.join(collect_to_path, target_directory))
            try:
                rtn_mkdir_flag = FileOperation.make_directory(dir_name=target_path, local_execute=localpath_flag,
                                                              ip=ip, port=port, username=username,
                                                              match_flag=False)
            except Exception as e:
                log.error('Found exception during make directory: {}, exception: {}'.format(target_path, e))
                rtn_mkdir_flag = RtnStatusEnum.FAIL.value

            if RtnStatusEnum.SUCCESS.value == rtn_mkdir_flag:
                log.debug('Success to make directory: {}, in {} server: {}@{}:{}'.format(target_path, server_msg,
                                                                                         username, ip, port))
            else:
                log.error('Fail to make directory: {}, in {} server: {}@{}:{}'.format(target_path, server_msg,
                                                                                      username, ip, port))
            # 拷贝文件
            try:
                copy_file_cmd = 'cp -r {} {}'.format(source_file, target_path)
                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                    cmd=copy_file_cmd, local_execute_flag=localpath_flag, ssh_ip=ip, ssh_port=port,
                    ssh_username=username)
                if RtnStatusEnum.SUCCESS.value == cmd_code:
                    collect_log_flag = True
            except Exception as e:
                log.error('Found exception during copy file source path: {}, to target path: {}, '
                          'exception: {}'.format(source_file, target_path, e))

            if collect_log_flag:
                log.debug('Success to copy file source path: {}, to target path: {}, in {} server: '
                          '{}@{}:{}'.format(source_file, target_path, server_msg, username, ip, port))
            else:
                log.error('Faild to copy file source path: {}, to target path: {}, in {} server: '
                          '{}@{}:{}'.format(source_file, target_path, server_msg, username, ip, port))

        return collect_log_flag

    @staticmethod
    def __pack_collect_log(file_path: str = None, tar_file_path: str = None, server_msg: str = None,
                           username: str = 'root', ip: str = None, port: str = '22',
                           localpath_flag: bool = False, is_pigz: bool = True) -> bool:
        """
        author:      haibin.xu
        date:        2021-04-09 15:05:48
        description: 打包收集的日志

        :param file_path: 日志路径
        :param tar_file_path: 打包名
        :param server_msg: server 信息
        :param username: log所在server 的用户名
        :param ip:   log所在server ip
        :param port: log所在server port
        :param localpath_flag: 是否为本地路径
        :param is_pigz: pigz标志位
        :return:     返回是否成功打包日志文件
        """
        try:
            rtn_tar_flag = FileOperation.compress_files(file_path=file_path, tar_file_path=tar_file_path,
                                                        localpath_flag=localpath_flag, ip=ip, port=port,
                                                        username=username, is_pigz=is_pigz)
        except Exception as e:
            log.error('Found exception during tar file: {}, exception: {}'.format(file_path, e))
            rtn_tar_flag = RtnStatusEnum.FAIL.value

        if RtnStatusEnum.SUCCESS.value == rtn_tar_flag:
            compress_file_flag = True
            log.debug('Success to compress file: {}, to tar file: {}. in {} server: {}@{}:{}'.format(
                file_path, tar_file_path, server_msg, username, ip, port))
        else:
            compress_file_flag = False
            log.error('Fail to compress file: {}, to tar file: {}. in {} server: {}@{}:{}'.format(
                file_path, tar_file_path, server_msg, username, ip, port))

        return compress_file_flag

    def __unpack_collect_log_in_log_server(self, tar_file: str = None, untar_file: str = None,
                                           server_msg: str = None) -> bool:
        """
        author:      haibin.xu
        date:        2021-04-09 15:52:17
        description: 在日志服务器上解压日志文件

        :param tar_file: 待解压的日志压缩文件名
        :param untar_file: 解压后的日志文件名
        :param server_msg: 日志原有server信息
        :return:      返回是否解压成功

        @changelog      2021-10-15 09:40:01  haibin.xu
                        1. 优化函数实现，功能屏蔽，直接返回True，已屏蔽的代码不要删除，留待将来需要解压时可再使用
        """
        return True

        # untar_file_path = CommandOperation.format_linux_path_sep(os.path.join(self.log_script_dir_path,
        #                                                                       constants.LOG_DIR_SIMULATOR_NAME,
        #                                                                       untar_file))
        # tar_file_path = CommandOperation.format_linux_path_sep(os.path.join(self.log_script_dir_path, tar_file))
        #
        # try:
        #     rtn_untar_flag = FileOperation.uncompress_file(tar_file_path=tar_file_path,
        #                                                    untar_file_path=untar_file_path, ip=self.log_server_ip,
        #                                                    username=self.log_server_account, match_flag=False)
        # except Exception as e:
        #     log.error('Found exception during untar file: {}, exception: {}'.format(tar_file_path, e))
        #     rtn_untar_flag = RtnStatusEnum.FAIL.value
        #
        # if RtnStatusEnum.SUCCESS.value == rtn_untar_flag:
        #     log.debug('Success to uncompress {} log file: {}, to target file: {}, in log server: {}@{}:22'.format(
        #         server_msg, tar_file_path, untar_file_path, self.log_server_account, self.log_server_ip))
        #     untar_collect_log_flag = True
        # else:
        #     log.error('Fail to uncompress {} log file: {}, to target file: {}, in log server: {}@{}:22'.format(
        #         server_msg, tar_file_path, untar_file_path, self.log_server_account, self.log_server_ip))
        #     untar_collect_log_flag = False
        #
        # return untar_collect_log_flag

    def __scp_collect_log_to_log_server(self, source_file: str = None, server_msg: str = None, source_ip: str = None,
                                        source_port: str = '22', source_username: str = 'root',
                                        localpath_flag: bool = False) -> bool:
        """
        author:      haibin.xu
        date:        2021-04-09 15:17:17
        description: 将收集的日志文件拷贝到远程日志服务器

        :param source_file: 收集的日志路径
        :param server_msg: server 信息
        :param source_ip:   收集的日志所在的server ip
        :param source_port: 收集的日志所在的server port
        :param source_username: 收集的日志所在的server username
        :param localpath_flag: 是否为本地路径
        :return:     返回是否拷贝成功
        """
        try:
            rtn_scp_flag = FileOperation.scp_file(source_file_path=source_file,
                                                  target_file_path=self.log_script_dir_path, source_ip=source_ip,
                                                  source_port=source_port, target_ip=self.log_server_ip,
                                                  target_username=self.log_server_account,
                                                  local_execute=localpath_flag)
        except Exception as e:
            log.error('Found exception during scp files, exception: {}'.format(e))
            rtn_scp_flag = RtnStatusEnum.FAIL.value

        if RtnStatusEnum.SUCCESS.value == rtn_scp_flag:
            scp_file_flag = True
            log.debug('Success to copy {} log file: {}@{}:{}:{}, to log server target file path: {}@{}:22:{}'.format(
                server_msg, source_username, source_ip, source_port, source_file, self.log_server_account,
                self.log_server_ip, self.log_script_dir_path))
            log.info("log_server:{} ==> log_save_path:{}".format(self.log_server_ip, self.log_script_dir_path))
        else:
            scp_file_flag = False
            log.error('Fail to copy {} log file: {}@{}:{}:{}, to log server target file path: {}@{}:22:{}'.format(
                server_msg, source_username, source_ip, source_port, source_file, self.log_server_account,
                self.log_server_ip, self.log_script_dir_path))

        return scp_file_flag

    def __delete_collect_log(self, pack_flag: bool = True, scp_flag: bool = True, collect_path: str = None,
                             colletc_tar_path: str = None, ip: str = None, port: str = '22', server_msg: str = None,
                             localpath_flag: bool = False, username: str = 'root') -> None:
        """
        author:      haibin.xu
        date:        2021-04-09 16:22:17
        description: 删除收集的log目录，压缩完成的log文件，以及远程拷贝到日志服务器上的log压缩包

        :param pack_flag: 日志打包标志位
        :param scp_flag:  日志传输标志位
        :param collect_path: log所在server下收集的log目录
        :param colletc_tar_path: 在log所在server下log压缩包
        :param ip:        log所在server的ip
        :param port:      log所在server的port
        :param server_msg: log所在server 信息
        :param localpath_flag: 是否本地路径
        :param 收集log所在的server 用户名
        :return:        None

        @changelog      2021-10-15 09:31:04  haibin.xu
                        1. 优化函数实现, 不再删除日志服务器上的压缩文件
        """
        files = ' '.join([collect_path, colletc_tar_path])
        if pack_flag and (RtnStatusEnum.SUCCESS.value == self.delete_files(delete_file=files, test_ip=ip,
                                                                           test_port=port,
                                                                           local_execute=localpath_flag)):
            log.debug('Success to delete log file: {}, in {} server: {}@{}:{}'.format(files, server_msg, username,
                                                                                      ip, port))
        else:
            log.warning('Fail or Not need to delete file: {}, in {} server: {}@{}:{}'.format(files, server_msg,
                                                                                             username, ip, port))

        # scp_flag = False
        # if scp_flag:
        #     # 日志传输成功，则删除拷贝到日志服务器上的log压缩包
        #     tar_file_path = CommandOperation.format_linux_path_sep(os.path.join(self.log_script_dir_path,
        #                                                                         os.path.basename(colletc_tar_path)))
        #     if (RtnStatusEnum.SUCCESS.value == self.delete_files(
        #             delete_file=tar_file_path, test_ip=self.log_server_ip, username=self.log_server_account)):
        #         log.debug('Success to delete file: {}, in log server: {}@{}:22'.format(
        #             tar_file_path, self.log_server_account, self.log_server_ip))
        #     else:
        #         log.warning('Fail to delete file: {}, in log server: {}@{}:22'.format(
        #             tar_file_path, self.log_server_account, self.log_server_ip))

    def __check_log_time(self, log_files: list = None, log_type: str = 'fwlog') -> list:
        """
        author:      haibin.xu
        date:        2022-06-24 17:44:59
        description: 查看日志中的时间戳是否在测试脚本测试时间段内

        :param log_files: 待检查的日志文件列表
        :param log_type: 日志类型
        :return:     返回在测试脚本测试时间段内的所有日志
        """
        return log_files
        if self.current_script_test_start_time is None or self.current_script_test_time is None:
            log.info('Not specify script test start time and test time, Not to filter log with time stamp.')
            return log_files

        rtn_log_list = []
        time_pattern = None
        if ('fwlog' in log_type) and ('fwlog_tools' not in log_type):
            # 获取fwlog日志中的时间戳
            time_pattern = r'fwlog-.*?-(\d{8}\-\d{6})\-.*'
            log.info('Get {} log at test start time: {}, duration time: {}'.format(
                log_type, self.current_script_test_start_time, self.current_script_test_time))

        if time_pattern is not None:
            log.debug('All logs:\n{}'.format('\n'.join(log_files)))
            start_time_stamp = time.mktime(time.strptime(self.current_script_test_start_time, '%Y-%m-%d %H:%M:%S'))
            log.debug('start_time_stamp: {}'.format(start_time_stamp))
            before_start_time_file_list = []
            for i, logf in enumerate(log_files):
                match_list = re.findall(time_pattern, logf)
                if 1 == len(match_list):
                    fwlog_time_stamp = time.mktime(time.strptime(match_list[0], '%Y%m%d-%H%M%S'))
                    if fwlog_time_stamp >= start_time_stamp:
                        rtn_log_list.append(logf)
                    else:
                        before_start_time_file_list.append(logf)

            log.debug('All log after script start time:\n{}'.format('\n'.join(rtn_log_list)))
            log.debug('All log before start time:\n{}'.format('\n'.join(before_start_time_file_list)))

            max_time = None
            max_time_stamp = None
            for i, logf in enumerate(before_start_time_file_list):
                match_list = re.findall(time_pattern, logf)
                fwlog_time_stamp = time.mktime(time.strptime(match_list[0], '%Y%m%d-%H%M%S'))
                if (max_time is None) or (fwlog_time_stamp >= max_time):
                    max_time = fwlog_time_stamp
                    max_time_stamp = match_list[0]

            for logf in before_start_time_file_list:
                if max_time_stamp in logf:
                    rtn_log_list.append(logf)

            log.debug('All log add one before script start time:\n{}'.format('\n'.join(rtn_log_list)))
        else:
            rtn_log_list = log_files

        return rtn_log_list

    def __set_host_log_parameters(self) -> None:
        """
        author: luyafei
        date: 2021.01.02
        description: 更新host_log_dict变量
        :return: None

        @changelog      2021-03-29 11:32:48  haibin.xu
                        1. 优化函数实现, 函数名修正：host_server_log_dict_update -> __set_host_log_parameters
                        sunql
                        增加收集日志路径
        """
        self.__get_node_info()
        if self.test_platform != constants.ENV_PLATFORM_REAL:
            find_cmd_dict = {
                                'usr_local_logs_sos': f'find /usr/local/logs/sos/ -name "*.log"',
                                'usr_local_logs_wmgr': f'find /usr/local/logs/wmgr/ -name "*.log"',
                                'test_host_node_logs': f'find /opt/ps3sim/ -name '
                                                       f'"test_node{self.host_node_id}*" ',
                                'qemu_host_node_logs': f'find /opt/ps3sim/ -name '
                                                       f'"qemu_log_node{self.host_node_id}*" ',
                            }
            find_log_cmd = None
            collect_path = constants.LOG_DIR_NAME_QEMU_HOST

            if libs_constants.TEST_OBJECT_PCIE_SWITCH == self.test_object:
                find_log_cmd = 'find {}'.format(libs_constants.LOG_COLL_HOST_PCIE_SWITCH_FILE_PATH)
                collect_path = constants.SIMULATOR_HOST_PCIE_SWITCH_LOG_COLLECT_DIR
            elif self.host_cpu == constants.HOST_CPU_X86:
                find_log_cmd = 'find {} | sed \'1d\''.format(constants.SIMULATOR_HOST_SERVER_LOG_COLLECT_PATH)
            elif self.host_cpu == constants.HOST_CPU_ARM:
                find_log_cmd = 'find /opt/ps3sim/log -name "ps3sas_{}.log_*"'.format(self.host_node_name) if \
                    self.host_node_name is not None else None
            else:
                log.warning('Fail to set host log data, invalid host cpu: {} or test object: {}'.format(
                    self.host_cpu, self.test_object))

            if find_log_cmd is not None:
                find_cmd_dict[collect_path] = find_log_cmd

        # 物理平台需要收集的日志
        if self.test_platform == constants.ENV_PLATFORM_REAL:
            find_cmd_dict = {
                'ps3sas_drv_log': f'ls -t /var/log/ps3sas_drv.log*',
                'ps3sas_drv_bin': f'ls -t /var/log/ps3sas_drv.bin*',
                'ps3cli_log': f'ls -t /root/ps3cli.log*',
                'message_log': f'ls -t /var/log/message*',
                'mcelog': f'ls -t /var/log/mcelog*',
                'fwlog': f'ls -t /var/log/fwlog* ',
                'fwlog_tools': f'ls -t /root/tools/*transition.*',
                'root_ps3ko': f'ls -t /root/ps3.ko',
                'com_log': f'ls -t /home/comlog/*.log',
                'ps3_agent': f'ls -t /var/log/ps3agent_server.log* /var/log/ps3agent_lib.log*',
                'host_trace': f'ls -t /var/log/host_trace/*',
                'before_after_cli_log': f'ls -t /root/cli_exec_log/*.log',
                'fio_log': f'ls -t /root/ps3test/fio/*.log',
                'crash': f'ls -t /var/crash/vmcore*',
            }

        # 记录需要收集的日志文件
        for collect_path, cmd in find_cmd_dict.items():
            try:
                rtn_code, log_files = FileOperation.get_files_with_cmd(find_files_cmd=cmd, ip=self.host_ip)
            except Exception as e:
                log.error('Found exception during find files, exception: {}'.format(e))
                rtn_code, log_files = RtnStatusEnum.FAIL.value, []

            if RtnStatusEnum.SUCCESS.value == rtn_code:
                # haibin.xu 2022-06-24 14:49:18 modify: 取fwlog时，按照当前测试脚本测试起始时间来取fwlog
                log_files = self.__check_log_time(log_files=log_files, log_type=collect_path)
                for log_path in log_files:
                    self.host_log_dict.update({log_path: collect_path})

        log.info(self.host_log_dict)

        log.debug('host server log dict: {}.'.format(self.host_log_dict))

    def __set_host_log_parameters_again(self) -> None:
        """
        author: sunql
        date: 2021.01.02
        description: 更新host_log_dict变量
        :return: None

        @changelog      2021-03-29 11:32:48  haibin.xu
                        1. 优化函数实现, 函数名修正：host_server_log_dict_update -> __set_host_log_parameters
                        sunql
                        增加收集日志路径
        """
        self.__get_node_info()
        # 物理平台需要收集的日志
        if self.test_platform == constants.ENV_PLATFORM_REAL:
            find_cmd_dict = {
                'ps3sas_drv_log_again': f'ls -t /var/log/drvlog/ps3sas_drv.log*',
                'ps3sas_drv_bin_again': f'ls -t  /var/log/drvlog/ps3sas_drv.bin*',
                'fwlog_again': f'ls -t  /var/log/drvlog/fwlog* '
            }

            # 记录需要收集的日志文件
            for collect_path, cmd in find_cmd_dict.items():
                try:
                    rtn_code, log_files = FileOperation.get_files_with_cmd(find_files_cmd=cmd, ip=self.host_ip)
                except Exception as e:
                    log.error('Found exception during find files, exception: {}'.format(e))
                    rtn_code, log_files = RtnStatusEnum.FAIL.value, []

                if RtnStatusEnum.SUCCESS.value == rtn_code:
                    # haibin.xu 2022-06-25 15:51:36 modify: 取fwlog时，按照当前测试脚本测试起始时间来取fwlog
                    log_files = self.__check_log_time(log_files=log_files, log_type=collect_path)
                    for log_path in log_files:
                        self.host_log_dict_again.update({log_path: collect_path})

            log.info(self.host_log_dict_again)

            log.debug('host server log dict: {}.'.format(self.host_log_dict_again))

    def collect_real_platform_cash_log(self) -> bool:
        """
        :author:sunql
        :date:2022.03.1
        :description: 收集物理平台host侧crash日志
        :return collect_flag: 是否收集到了Crash文件
        """
        if CompileObjectStrEnum.FRONTEND.value == self.compile_object:
            log.info('Frontend test, not to collect real host  crash log.')
            return False

        collect_flag = self.__collect_crash_core_log(file_path=libs_constants.LOG_COLL_HOST_CRASH_FILE_PATH,
                                                     directory_name=libs_constants.LOG_COLL_HOST_CRASH_DIR,
                                                     collect_to_path=self.host_collect_path,
                                                     ip=self.host_ip, port=self.host_port,
                                                     server_msg='host', log_type='crash')

        return collect_flag

    def collect_real_platform_core_log(self) -> bool:
        """
        :author:sunql
        :date:2022.03.1
        :description: 收集物理平台host侧core日志
        :return collect_flag: 是否收集到了core文件
        """
        if CompileObjectStrEnum.FRONTEND.value == self.compile_object:
            log.info('Frontend test, not to collect real host core log.')
            return False

        collect_flag = self.__collect_crash_core_log(file_path=libs_constants.LOG_COLL_HOST_CORE_FILE_PATH,
                                                     directory_name=libs_constants.LOG_COLL_HOST_CORE_DIR,
                                                     collect_to_path=self.host_collect_path,
                                                     ip=self.host_ip, port=self.host_port,
                                                     server_msg='host', log_type='core')

        return collect_flag

    def collect_host_log(self) -> tuple:
        """
        :author:panpan.du
        :date:2020.10.19
        :description: 收集host宿主机的日文件并打包传输
        :return: tuple

        @changelog      2021-03-29 11:35:52  haibin.xu
                        1. 优化函数实现, 函数名修正：log_collect_host_server -> collect_host_log
        """
        log.info('test_entry: {}, test_object: {}, Start to collect host log ...'.format(
            self.test_entry, self.test_object))

        if CompileObjectStrEnum.FRONTEND.value == self.compile_object:
            log.info('Frontend test, not to collect host log.')
            return True, False, False

        if RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(ip=self.host_ip):
            log.error('Not to collect host log, reason: failed to connect to host server.')
            return False, False, False

        delete_old_dir, _ = FileOperation.delete_file(path=self.host_collect_path, ip=self.host_ip, match_flag=False,
                                                      file_check_flag=False)
        if RtnStatusEnum.SUCCESS.value != delete_old_dir:
            log.error('Can not delete old directory: {}, not to collect host server log.'.format(
                self.host_collect_path))
            return False, False, False

        # 更新self.host_log_dict
        self.__set_host_log_parameters()
        collect_flag = self.__collect_log_in_current_directory(log_dict=self.host_log_dict,
                                                               collect_to_path=self.host_collect_path,
                                                               server_msg='host', ip=self.host_ip)

        log.info(f"collect host log to {self.host_collect_path}  is {collect_flag}")
        # 再补收一次host log
        if collect_flag:
            self.__set_host_log_parameters_again()
            collect_flag = self.__collect_log_in_current_directory(log_dict=self.host_log_dict_again,
                                                                   collect_to_path=self.host_collect_path,
                                                                   server_msg='host', ip=self.host_ip)

            log.info(f"collect host log  again to {self.host_collect_path}  is {collect_flag}")

        # 物理平台收集Host端新产生的crash文件：
        if 'windows' not in libs_constants.HOST_OS and self.test_platform == constants.ENV_PLATFORM_REAL:
            crash_collect_flag = self.collect_real_platform_cash_log()
            core_collect_flag = self.collect_real_platform_core_log()
            # 收集 mini com 日志
            if self.com_port and 'dev' not in str(self.com_port) and str(self.com_port) != '':
                mini_log_path = f"/home/framework/other/{self.com_ip}/{self.com_port}/*.log"
                target_dir_name = f"{self.log_script_dir_path}/mini_com_log"
                cmd = f'mkdir -p {target_dir_name};ls -t {mini_log_path} | head -n 2 |xargs  cp -t {target_dir_name}'
                CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd,
                                                                             ssh_ip=self.log_server_ip,
                                                                             ssh_port=22,
                                                                             ssh_username=self.log_server_account)
        else:
            core_collect_flag = False
            crash_collect_flag = False

        # 打包
        compress_file_flag = self.__pack_collect_log(
            file_path=self.host_collect_path, tar_file_path=self.host_collect_tar, server_msg='host',
            ip=self.host_ip, is_pigz=False) if collect_flag else False

        # 传输
        scp_file_flag = self.__scp_collect_log_to_log_server(
            source_file=self.host_collect_tar, server_msg='host', source_ip=self.host_ip) if compress_file_flag \
            else False

        collect_log_flag = scp_file_flag

        if collect_log_flag:
            # 删除打包文件
            self.__delete_collect_log(pack_flag=compress_file_flag, scp_flag=scp_file_flag,
                                      collect_path=self.host_collect_path, colletc_tar_path=self.host_collect_tar,
                                      ip=self.host_ip, server_msg='host')

        if collect_log_flag:
            log.info('Finish to collect host log file to log server.\n')
        else:
            log.error('Fail to collect host log file to log server.\n')

        return collect_log_flag, crash_collect_flag, core_collect_flag

    def collect_host_log_after_rest(self) -> tuple:
        """
        :author:panpan.du
        :date:2020.10.19
        :description: 重启后再次收集host宿主机的日文件并打包传输
        :return: tuple

        @changelog      2021-03-29 11:35:52  haibin.xu
                        1. 优化函数实现, 函数名修正：log_collect_host_server -> collect_host_log
        """
        log.info('test_entry: {}, test_object: {}, Start to collect host log after reset ...'.format(
            self.test_entry, self.test_object))
        self.host_collect_tar = "host_log_after_reset.tar.gz"
        collect_log_flag, crash_collect_flag, core_collect_flag = self.collect_host_log()
        self.host_collect_tar = constants.SIMULATOR_HOST_LOG_COLLECT_TAR
        return collect_log_flag, crash_collect_flag, core_collect_flag

    def collect_host_log_after_framework_bug(self, script_name) -> tuple:
        """
        :author:sunql
        :date:2022.6.15
        :description: 硬复位后再次收集host宿主机的日文件并打包传输
        :return: tuple

        @changelog      2021-03-29 11:35:52  haibin.xu
                        1. 优化函数实现, 函数名修正：log_collect_host_server -> collect_host_log
        """
        log.info('test_entry: {}, test_object: {}, Start to collect host log after framework bug ...'.format(
            self.test_entry, self.test_object))
        self.make_script_directory_in_log_server(script_name)
        self.host_collect_tar = "host_log_after_framework_bug.tar.gz"
        collect_log_flag, crash_collect_flag, core_collect_flag = self.collect_host_log()
        self.host_collect_tar = constants.SIMULATOR_HOST_LOG_COLLECT_TAR
        return collect_log_flag, crash_collect_flag, core_collect_flag

    def __set_host_qemu_log_parameters(self) -> None:
        """
        author:      sunql
        date:        2021-04-09 16:41:07
        description: 设置self.host_qemu_log_dict参数

        :return:     None
        """
        if 'windows' not in libs_constants.HOST_OS:
            self.host_qemu_log_dict = {
                constants.SIMULATOR_HOST_DRIVER_LOG_COLLECT_PATH: constants.LOG_DIR_NAME_HOST_DRIVER,
                constants.SIMULATOR_HOST_DRIVER_BIN_COLLECT_PATH: constants.LOG_DIR_NAME_HOST_DRIVER,
                constants.SIMULATOR_HOST_MGT_LOG_COLLECT_CLEAR_PATH: constants.LOG_DIR_NAME_HOST_MGT,
                constants.SIMULATOR_HOST_FACTORY_LOG_COLLECT_CLEAR_PATH: constants.LOG_DIR_NAME_HOST_FACTORY,
                constants.SIMULATOR_HOST_MESSAGE_LOG_COLLECT_PATH: constants.LOG_DIR_NAME_HOST_MESSAGE,
                constants.TEST_TOOL_HOST_VDBENCH_CONFIGURE_COLLECT_PATH: constants.LOG_DIR_NAME_HOST_VDBENCH,
                constants.TEST_TOOL_HOST_VDBENCH_OUTPUT_COLLECT_PATH: constants.LOG_DIR_NAME_HOST_VDBENCH,
                constants.TEST_TOOL_HOST_VDBENCH_JRN_OUTPUT_COLLECT_PATH: constants.LOG_DIR_NAME_HOST_VDBENCH,
                constants.TEST_TOOL_HOST_VDBENCH_JN_OUTPUT_COLLECT_PATH: constants.LOG_DIR_NAME_HOST_VDBENCH,
                constants.TEST_TOOL_HOST_FIO_COLLECT_PATH: constants.LOG_DIR_NAME_HOST_FIO,
                constants.TEST_TOOL_HOST_CLI_ERROR_PATH: constants.LOG_DIR_NAME_HOST_CLI_ERROR,
                '/root/server.log*': 'root_server',
                '/root/ps3.ko': 'root_ps3ko',
                '/var/log/ps3agent_server.log*': 'ps3_agent',
                '/var/log/ps3agent_lib.log*': 'ps3_agent',
            }
            if RtnStatusEnum.SUCCESS.value == CommandOperation.get_dmesg_data(ssh_ip=self.host_qemu_ip,
                                                                              ssh_port=self.host_port):
                self.host_qemu_log_dict.update({
                    constants.SIMULATOR_HOST_DMESG_LOG_COLLECT_PATH: constants.LOG_DIR_NAME_HOST_DMESG})
        else:
            self.host_qemu_log_dict = {
                constants.WINDOWS_SIMULATOR_HOST_DRIVER_LOG_COLLECT_PATH: constants.LOG_DIR_NAME_HOST_DRIVER,
                constants.WINDOWS_SIMULATOR_HOST_DRIVER_BIN_COLLECT_PATH: constants.LOG_DIR_NAME_HOST_DRIVER,
                constants.WINDOWS_SIMULATOR_HOST_MGT_LOG_COLLECT_CLEAR_PATH: constants.LOG_DIR_NAME_HOST_MGT,
                constants.WINDOWS_SIMULATOR_HOST_FACTORY_LOG_COLLECT_CLEAR_PATH: constants.LOG_DIR_NAME_HOST_FACTORY,
                constants.WINDOWS_TEST_TOOL_HOST_CLI_ERROR_PATH: constants.LOG_DIR_NAME_HOST_CLI_ERROR,
                constants.WINDOWS_TEST_TOOL_HOST_VDBENCH_PATH: constants.LOG_DIR_NAME_HOST_VDBENCH,
                constants.WINDOWS_TEST_TOOL_HOST_FIO_PATH: constants.LOG_DIR_NAME_HOST_FIO,
            }

    def collect_host_qemu_log(self) -> bool:
        """
        :author:panpan.du
        :date:2020.10.19
        :description: 收集host qemu端的日文件并打包传输
        : return: 返回crash_collect_flag

        @changelog      2021-03-29 14:52:53  haibin.xu
                        1. 优化函数实现, 函数名修正：log_collect_simulator_host -> collect_host_qemu_log
        """
        log.info('test_entry: {}, test_object: {}, Start to collect host qemu log ...'.format(
            self.test_entry, self.test_object))

        if CompileObjectStrEnum.FRONTEND.value == self.compile_object:
            log.info('Frontend test, not to collect host qemu log.')
            return False

        if RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(ip=self.host_qemu_ip,
                                                                            port=self.host_port):
            log.error('Not to collect host qemu log, reason: failed to connect to host qemu server.')
            return False

        delete_old_dir, _ = FileOperation.delete_file(path=self.host_qemu_collect_path, ip=self.host_qemu_ip,
                                                      port=self.host_port, match_flag=False,
                                                      file_check_flag=False)
        if RtnStatusEnum.SUCCESS.value != delete_old_dir:
            log.error('Can not delete old directory: {}, not to collect host qemu server log.'.format(
                self.host_qemu_collect_path))
            return False

        # 将host qemu端文件收集到本地
        self.__set_host_qemu_log_parameters()
        collect_flag = self.__collect_log_in_current_directory(log_dict=self.host_qemu_log_dict,
                                                               collect_to_path=self.host_qemu_collect_path,
                                                               server_msg='host qemu', ip=self.host_qemu_ip,
                                                               port=self.host_port)

        # 收集Host端新产生的crash文件：
        if 'windows' not in libs_constants.HOST_OS:
            crash_collect_flag = self.collect_host_qemu_crash_log()
        else:
            crash_collect_flag = True

        # 打包
        compress_file_flag = self.__pack_collect_log(
            file_path=self.host_qemu_collect_path, tar_file_path=self.host_qemu_collect_tar, server_msg='host qemu',
            ip=self.host_qemu_ip, port=self.host_port) if (collect_flag or crash_collect_flag) else False

        # 传输
        scp_file_flag = self.__scp_collect_log_to_log_server(source_file=self.host_qemu_collect_tar,
                                                             server_msg='host qemu', source_ip=self.host_qemu_ip,
                                                             source_port=self.host_port) if compress_file_flag else \
            False

        # 解包
        success_collect_log_flag = self.__unpack_collect_log_in_log_server(tar_file=self.host_qemu_collect_tar,
                                                                           untar_file=self.host_qemu_collect_path,
                                                                           server_msg='host qemu') if scp_file_flag \
            else False

        if success_collect_log_flag:
            # 删除打包文件
            self.__delete_collect_log(pack_flag=compress_file_flag, scp_flag=scp_file_flag,
                                      collect_path=self.host_qemu_collect_path,
                                      colletc_tar_path=self.host_qemu_collect_tar,
                                      ip=self.host_qemu_ip, port=self.host_port, server_msg='host qemu')

        if success_collect_log_flag:
            log.info('Finish to collect host qemu log file to log server.\n')
        else:
            log.error('Fail to collect host qemu log file to log server.\n')

        return crash_collect_flag

    def __set_ioc_qemu_log_parameters(self) -> None:
        """
        author:      haibin.xu
        date:        2021-04-09 17:11:17
        description: 设置self.ioc_qemu_log_dict参数

        :return:     None
        """
        if constants.ENV_TEST_OBJECT_PCIE_SWITCH != self.test_object:
            self.ioc_qemu_log_dict = {
                constants.SIMULATOR_IOC_COLLECT_PATH: libs_constants.LOG_COLL_IOC_CORE_DIR,
                constants.SIMULATOR_IOC_LOG_COLLECT_PATH: constants.LOG_DIR_NAME_IOC_LOG,
                constants.SIMULATOR_IOC_PS3_LOG_COLLECT_PATH: constants.LOG_DIR_NAME_IOC_PS3,
                constants.SIMULATOR_IOC_CLI_LOG_COLLECT_PATH: constants.LOG_DIR_NAME_IOC_CLI,
                constants.SIMULATOR_IOC_MESSAGE_LOG_COLLECT_PATH: constants.LOG_DIR_NAME_IOC_MESSAGE,
                constants.SIMULATOR_IOC_PSTACK_LOG_COLLECT_PATH: constants.LOG_DIR_NAME_IOC_PSTACK,
                constants.SIMULATOR_IOC_PS3SIM_LOG_COLLECT_PATH: constants.LOG_DIR_NAME_IOC_PS3SIM_LOG,
                constants.SIMULATOR_IOC_TOP_LOG_COLLECT_PATH: constants.LOG_DIR_NAME_IOC_TOP
            }
            if RtnStatusEnum.SUCCESS.value == CommandOperation.get_dmesg_data(ssh_ip=self.ioc_qemu_ip,
                                                                              ssh_port=self.ioc_port):
                self.ioc_qemu_log_dict.update({
                    constants.SIMULATOR_IOC_DMESG_LOG_COLLECT_PATH: constants.LOG_DIR_NAME_IOC_DMESG})
        else:
            log.info('Pcie switch test, not set ioc_qemu_log_dict parameters.')

    def collect_ioc_qemu_log(self) -> tuple:
        """
        :author:panpan.du
        :date:2020.10.19
        :description: 收集host qemu端的日文件并打包传输
        :return: 返回crash，core文件搜集标志位

        @changelog      2021-03-29 17:11:45  haibin.xu
                        1. 优化函数实现, 函数名修正：log_collect_simulator_ioc -> collect_ioc_qemu_log
        """
        log.info('test_entry: {}, test_object: {}, Start to collect ioc qemu log ...'.format(
            self.test_entry, self.test_object))

        crash_collect_flag = False
        core_collect_flag = False
        success_collect_log_flag = True

        if constants.ENV_TEST_OBJECT_PCIE_SWITCH == self.test_object:
            log.info('Pcie Switch test, not to collect ioc qemu log.')
            return crash_collect_flag, core_collect_flag, success_collect_log_flag

        if RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(ip=self.ioc_qemu_ip, port=self.ioc_port):
            log.error('Not to collect ioc qemu log, reason: failed to connect to ioc qemu server.')
            return crash_collect_flag, core_collect_flag, success_collect_log_flag

        collect_to_path = CommandOperation.format_linux_path_sep(os.path.join(libs_constants.OPT_PS3_PATH,
                                                                              self.ioc_qemu_collect_path))
        delete_old_dir, _ = FileOperation.delete_file(path=collect_to_path, ip=self.ioc_qemu_ip, port=self.ioc_port,
                                                      match_flag=False, file_check_flag=False)
        if RtnStatusEnum.SUCCESS.value != delete_old_dir:
            log.error('Can not delete old directory: {}, not to collect ioc qemu server log.'.format(
                collect_to_path))
            return crash_collect_flag, core_collect_flag, success_collect_log_flag

        # 将文件收集到ioc本地
        self.__set_ioc_qemu_log_parameters()
        collect_flag = self.__collect_log_in_current_directory(log_dict=self.ioc_qemu_log_dict,
                                                               collect_to_path=collect_to_path,
                                                               server_msg='ioc qemu', ip=self.ioc_qemu_ip,
                                                               port=self.ioc_port)

        if constants.BACKEND == self.compile_object:
            self.collect_backend_tool_log()

        # 收集ioc端的Crash文件
        crash_collect_flag = self.collect_ioc_qemu_crash_log()
        # 收集ioc端的Core文件
        core_collect_flag = self.collect_ioc_qemu_core_log()

        # 有需要收集的文件
        # 打包
        ioc_qemu_tar_file_path = CommandOperation.format_linux_path_sep(os.path.join(
            libs_constants.OPT_PS3_PATH, self.ioc_qemu_collect_tar))
        compress_file_flag = self.__pack_collect_log(
            file_path=collect_to_path, tar_file_path=ioc_qemu_tar_file_path, server_msg='ioc qemu',
            ip=self.ioc_qemu_ip, port=self.ioc_port) if (collect_flag or crash_collect_flag or core_collect_flag) \
            else False

        # 传输
        scp_file_flag = self.__scp_collect_log_to_log_server(source_file=ioc_qemu_tar_file_path,
                                                             server_msg='ioc qemu', source_ip=self.ioc_qemu_ip,
                                                             source_port=self.ioc_port) if compress_file_flag else \
            False

        # 解包
        success_collect_log_flag = self.__unpack_collect_log_in_log_server(tar_file=self.ioc_qemu_collect_tar,
                                                                           untar_file=self.ioc_qemu_collect_path,
                                                                           server_msg='ioc qemu') if scp_file_flag \
            else False

        if success_collect_log_flag:
            # 删除打包文件
            self.__delete_collect_log(pack_flag=compress_file_flag, scp_flag=scp_file_flag,
                                      collect_path=collect_to_path, colletc_tar_path=ioc_qemu_tar_file_path,
                                      ip=self.ioc_qemu_ip, port=self.ioc_port, server_msg='ioc qemu')

        if success_collect_log_flag:
            log.info('Finish to collect ioc qemu log file to log server.\n')
        else:
            log.error('Fail to collect ioc qemu log file to log server.\n')

        return crash_collect_flag, core_collect_flag, success_collect_log_flag

    def __collect_crash_core_log(self, file_path: str = None, directory_name: str = None,
                                 collect_to_path: str = None, ip: str = None, port: str = '22',
                                 server_msg: str = None, log_type: str = None) -> bool:
        """
        author:      haibin.xu
        date:        2021-04-09 17:58:16
        description: 收集crash，core日志

        :param file_path: crash，core日志路径
        :param ip:    crash，core日志所在server ip
        :param port:  crash，core日志所在server port
        :param directory_name: 目录名称
        :param collect_to_path: 日志收集目标路径
        :param server_msg:  server 信息
        :param log_type: log类型， core or crash
        :return:

        @changelog      2021-10-12 16:20:19  haibin.xu
                        1. 优化函数实现，对ioc qemu core文件的收集优化，解决文件拷贝缺失的问题以及core文件单独打包
        """
        collect_flag = False
        # 是否检查文件大小标志位
        detect_file_size_flag = False

        try:
            dir_exist = FileOperation.dir_path_exists(path=file_path, ip=ip, port=port)

        except Exception as e:
            log.error('Found exception during check directory path: {}, exception: {}.'.format(file_path, e))
            dir_exist = RtnStatusEnum.FAIL.value

        if RtnStatusEnum.SUCCESS.value == dir_exist:
            if constants.SIMULATOR_IOC_CORE_LOG_ROOT_PATH == file_path:
                # 如果是获取core文件，则只获取/opt/ps3/*core*文件
                file_path = constants.SIMULATOR_IOC_CORE_LOG_PATH

            if libs_constants.LOG_COLL_HOST_CORE_FILE_PATH == file_path and log_type == 'core':
                file_path = f"{libs_constants.LOG_COLL_HOST_CORE_FILE_PATH}core_dump* "

            if 'exp process' == server_msg:
                # 如果是收集expander core文件，则只获取 file_path/expsimu.bin file_path/*core*文件
                file_path = constants.EXPANDER_CORE_LOG_PATH.format(file_path)
            if ('ioc qemu' == server_msg or 'host' == server_msg) and ('core' == log_type):
                # ioc core比较大，收集时，core文件可能还在创建中，此处设置该标志位为True,查找该文件时会将文件大小考虑进去
                detect_file_size_flag = True

            log.info(f"core file path: {file_path}")

            # 获取当前crash/core文件列表
            try:
                _, files = FileOperation.get_files(file_path=file_path, ip=ip, port=port,
                                                   detect_file_size_flag=detect_file_size_flag)
                log.info(f"find files:{files}")
            except Exception as e:
                log.error('Found exception during get files from directory: {}, exception: {}.'.format(file_path, e))
                files = []

            if files:
                if isinstance(files, list) and (1 == len(files)) and ((constants.FM_OPT_PS3_IOC == files[0]) or
                                                                      (constants.PS3_EXP_FW_FILE in files[0])):
                    log.info('Only find files: {}, not find really core files.'.format(files[0]))
                    files = []
                else:
                    log.debug('Found {} {} files in directory[{}]: {}'.format(server_msg, log_type, file_path,
                                                                              files))
            else:
                log.warning('Not found {} {} files in directory[{}]: {}'.format(server_msg, log_type, file_path,
                                                                                files))

            # 与旧文件列表对比找出新产生的crash/core
            new_files = list(set(files).difference(set(self.qemu_crash_core_initial_data[directory_name])))
            if len(new_files) == 1 and constants.FM_OPT_PS3_IOC == new_files[0]:
                new_files = []

            # 新产生的crash/core文件收集到目标文件夹中
            if len(new_files) > 0:
                log.info('Found new {} core/crash files: {}'.format(server_msg, new_files))
                # 如果是第二次收集core, /opt/ps3/ioc 或 /opt/ps3sim/iocnode*_expander/expsimu.bin文件可能会被滤除，所以此处
                # 需加回来
                for c_file in files:
                    if (constants.FM_OPT_PS3_IOC == c_file) and (c_file not in new_files):
                        new_files.append(constants.FM_OPT_PS3_IOC)
                        break
                    if (constants.PS3_EXP_FW_FILE in c_file) and (c_file not in new_files):
                        new_files.append(c_file)
                        break

                # 创建目标文件夹
                target_log_path = CommandOperation.format_linux_path_sep(os.path.join(collect_to_path,
                                                                                      directory_name))
                try:
                    mkdir_flag = FileOperation.make_directory(dir_name=target_log_path, ip=ip, port=port,
                                                              match_flag=False)
                except Exception as e:
                    log.error('Found exception during make directory: {}, exception: {}.'.format(target_log_path, e))
                    mkdir_flag = RtnStatusEnum.FAIL.value

                if RtnStatusEnum.SUCCESS.value == mkdir_flag:
                    log.debug('Finish to make directory: {}, in {} server.'.format(target_log_path, server_msg))
                    new_temp_files = [
                        CommandOperation.format_linux_path_sep(os.path.join(
                            file_path.replace('core_dump*', ''), file)) for file in new_files
                    ]

                    crash_files = ' '.join(new_temp_files)
                    try:
                        if ('ioc qemu' == server_msg) and ('core' == log_type):
                            # ioc core 单独做压缩操作，此处以core文件中字母/数字/.等字符命名压缩文件名
                            tar_file_name = 'ioc_qemu_core.tar.gz'
                            for fl in new_files:
                                if 'core' in fl:
                                    # 获取core文件中所有字母/数字/.等字符并重新组合
                                    tar_file_name = ''.join(re.findall(r'[a-zA-Z0-9.]', fl.replace('/opt/ps3/', ''))) \
                                                    + '.tar.gz'
                                    break
                            tar_file_path = CommandOperation.format_linux_path_sep(os.path.join(target_log_path,
                                                                                                tar_file_name))
                            handle_flag = FileOperation.compress_files(
                                file_path=crash_files, tar_file_path=tar_file_path, ip=ip, port=port)
                        else:
                            handle_flag = FileOperation.create_symbolic_link(
                                source_path=crash_files, link_directory_path=target_log_path, ssh_ip=ip,
                                ssh_port=port, path_check_flag=False)
                    except Exception as e:
                        log.error('Found exception during handle(compress or create link) file: {}, source path: {},'
                                  ' exception: {}'.format(target_log_path, crash_files, e))
                        handle_flag = RtnStatusEnum.FAIL.value

                    if RtnStatusEnum.SUCCESS.value == handle_flag:
                        log.debug('Success to handle(compress or create link) file save in path: {}, source path: {}'
                                  ', in {} server'.format(target_log_path, crash_files, server_msg))
                    else:
                        log.error('Fail to handle(compress or create link) file save in path: {}, source path: {}, '
                                  'in {} server'.format(target_log_path, crash_files, server_msg))
                    self.qemu_crash_core_initial_data[directory_name] = files

                    if constants.FM_OPT_PS3_IOC not in self.qemu_crash_core_initial_data[directory_name]:
                        self.qemu_crash_core_initial_data[directory_name].append(constants.FM_OPT_PS3_IOC)

                    collect_flag = True
                else:
                    log.error('Fail to make directory: {}, in {} server.'.format(target_log_path, server_msg))
            else:
                log.warning('Not found new {} {} files.'.format(server_msg, log_type))
        else:
            log.warning('Not found {} {} directory: {}'.format(server_msg, log_type, file_path))

        return collect_flag

    def collect_host_qemu_crash_log(self) -> bool:
        """
        :author:DuPanPan
        :date:2020.09.17
        :description: 收集模拟平台host侧crash日志
        :return collect_flag: 是否收集到了Crash文件

        @changelog      2021-03-29 15:09:02  haibin.xu
                        1. 优化函数实现, 函数名修正：log_collect_simulator_host_crash -> collect_host_qemu_crash_log
        """
        if CompileObjectStrEnum.FRONTEND.value == self.compile_object:
            log.info('Frontend test, not to collect host qemu crash log.')
            return False

        collect_flag = self.__collect_crash_core_log(file_path=libs_constants.LOG_COLL_HOST_CRASH_FILE_PATH,
                                                     directory_name=libs_constants.LOG_COLL_HOST_CRASH_DIR,
                                                     collect_to_path=self.host_qemu_collect_path,
                                                     ip=self.host_qemu_ip, port=self.host_port,
                                                     server_msg='host qemu', log_type='crash')

        return collect_flag

    def collect_backend_tool_log(self) -> None:
        """
        author: luyafei
        date: 2020.12.27
        description: 收集后端工具的日志
        :return: None

        @changelog      2021-03-29 19:47:01  haibin.xu
                        1. 优化函数实现，函数名修正：log_collect_backend_tool -> collect_backend_tool_log
        """
        log.info('compile object: {}, start to collect collect backend tool log in ioc qemu server ...'.format(
            self.compile_object))

        # 创建目标文件夹
        try:
            _, find_files = FileOperation.find_files(path=constants.BACKEND_TOOL_LOG_PATH, ip=self.ioc_qemu_ip,
                                                     port=self.ioc_port)
        except Exception as e:
            log.error('Found exception during check file path: {}, exception: {}.'.format(
                constants.BACKEND_TOOL_LOG_PATH, e))
            find_files = ''

        if find_files:
            log.debug('Success found backend tool log: {}, in ioc qemu server.'.format(find_files))
            backend_tool_log_path = CommandOperation.format_linux_path_sep(os.path.join(
                libs_constants.OPT_PS3_PATH, self.ioc_qemu_collect_path, constants.LOG_DIR_NAME_BACKEND_TOOL))
            try:
                mkdir_flag = FileOperation.make_directory(dir_name=backend_tool_log_path, ip=self.ioc_qemu_ip,
                                                          port=self.ioc_port, match_flag=False)
            except Exception as e:
                log.error('Found exception during make directory: {}, exception: {}.'.format(backend_tool_log_path,
                                                                                             e))
                mkdir_flag = RtnStatusEnum.FAIL.value

            if RtnStatusEnum.SUCCESS.value == mkdir_flag:
                try:
                    create_lnpath_flag = FileOperation.create_symbolic_link(
                        source_path=find_files, link_directory_path=backend_tool_log_path, ssh_ip=self.ioc_qemu_ip,
                        ssh_port=self.ioc_port, path_check_flag=False)
                except Exception as e:
                    log.error('Found exception during create link file save in path: {}, link to source path: '
                              '{}, exception: {}'.format(backend_tool_log_path, find_files, e))
                    create_lnpath_flag = RtnStatusEnum.FAIL.value

                if RtnStatusEnum.SUCCESS.value == create_lnpath_flag:
                    log.debug('Success to create link file save in path: {}, link to source path: {}, in ioc qemu '
                              'server.'.format(backend_tool_log_path, find_files))
                else:
                    log.error('Fail to create link file save in path: {}, link to source path: {}, in ioc qemu '
                              'server.'.format(backend_tool_log_path, find_files))

        log.info('Finish to collect backend tool log.\n')

    def collect_ioc_qemu_core_log(self) -> bool:
        """
        :author:DuPanPan
        :date:2020.09.27
        :description: 收集模拟平台ioc侧core日志
        :return collect_flag: 是否收集到了Core文件

        @changelog      2021-03-29 19:14:40  haibin.xu
                        1. 优化函数实现, 函数名修正：log_collect_simulator_ioc_core -> collect_ioc_qemu_core_log
        """
        log.info('Start to collect ioc qemu core log...')

        if constants.ENV_TEST_OBJECT_PCIE_SWITCH == self.test_object:
            log.info('Pcie Switch test, not to collect ioc qemu core log.')
            return False

        if RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(ip=self.ioc_qemu_ip, port=self.ioc_port):
            log.error('Not to collect ioc qemu log, reason: failed to connect to ioc qemu server.')
            return False

        collect_to_path = CommandOperation.format_linux_path_sep(os.path.join(libs_constants.OPT_PS3_PATH,
                                                                              self.ioc_qemu_collect_path))
        collect_flag = self.__collect_crash_core_log(file_path=constants.SIMULATOR_IOC_CORE_LOG_ROOT_PATH,
                                                     directory_name=libs_constants.LOG_COLL_IOC_CORE_DIR,
                                                     collect_to_path=collect_to_path, ip=self.ioc_qemu_ip,
                                                     port=self.ioc_port, server_msg='ioc qemu', log_type='core')
        log.info('Finish to collect ioc qemu core log.\n')

        return collect_flag

    def collect_ioc_qemu_crash_log(self) -> bool:
        """
        :author:DuPanPan
        :date:2020.09.17
        :description: 拷贝模拟平台ioc qemu侧ps3日志到日志服务器
        :return: collect_flag: 是否收集到了Crash文件

        @changelog      2021-03-29 17:34:59  haibin.xu
                        1. 优化函数实现, 函数名修正：log_collect_simulator_ioc_cras -> collect_ioc_qemu_crash_log
        """
        log.info('Start to collect ioc qemu crash log...')

        if constants.ENV_TEST_OBJECT_PCIE_SWITCH == self.test_object:
            log.info('Pcie Switch test, not to collect ioc qemu crash log.')
            return False

        if RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(ip=self.ioc_qemu_ip, port=self.ioc_port):
            log.error('Not to collect ioc qemu log, reason: failed to connect to ioc qemu server.')
            return False

        collect_to_path = CommandOperation.format_linux_path_sep(os.path.join(libs_constants.OPT_PS3_PATH,
                                                                              self.ioc_qemu_collect_path))

        collect_flag = self.__collect_crash_core_log(file_path=libs_constants.LOG_COLL_IOC_CRASH_FILE_PATH,
                                                     directory_name=libs_constants.LOG_COLL_IOC_CRASH_DIR,
                                                     collect_to_path=collect_to_path, ip=self.ioc_qemu_ip,
                                                     port=self.ioc_port, server_msg='ioc qemu', log_type='crash')

        log.info('Finish to collect ioc qemu crash log.\n')

        return collect_flag

    def init_expander_log(self, log_dict, ip: str = None, port: str = '22') -> None:
        """
        author: luyafei
        date: 2021.01.02
        description: 清理的expander日志
        :param log_dict: 要收集日志的源地址域目标地址字典
        :param ip: expander日志所在的server ip
        :param port: expander日志所在的server port
        :return: None

        @changelog      2021-03-29 20:36:12  haibin.xu
                        1. 优化函数实现, 函数名修正：exp_ioc_server_log_clear -> init_expander_log
        """
        clear_list = []

        log.info('Start to init expander log...')

        for log_item in log_dict.keys():
            log.debug('Get expander log: {}, to be cleaned.'.format(log_item))
            clear_list.append(log_item)

        self.clean_files(clear_list, ip, port)
        log.info('Finish to clean expander/pcie_switch log file: {} in server: {}:{}.\n'.format(
            clear_list, ip, port))

    def __get_newest_serial_log(self) -> list:
        """
        author:      haibin.xu
        date:        2022-02-22 11:08:01
        description: 获取最新的串口日志

        :return:     返回最新的串口日志名单列表
        """
        current_dir = None
        temp_log_files_list = []
        newest_serial_log_list = []
        find_files_cmd = f'ls {self.host_expander_serial_log_path}'
        rtn_code, serial_log_files = FileOperation.get_files_with_cmd(find_files_cmd=find_files_cmd, ip=self.host_ip)
        if RtnStatusEnum.SUCCESS.value == rtn_code:
            for i, se_log in enumerate(serial_log_files):
                # log列表中如果第一个元素没有包含minicom关键字段，说明只有一个串口
                if 'minicom' in se_log:
                    if temp_log_files_list:
                        newest_serial_log_list.append(CommandOperation.format_linux_path_sep(os.path.join(
                            current_dir, max(*temp_log_files_list) + '.log')))
                        temp_log_files_list.clear()
                    current_dir = se_log.replace(':', '')
                    continue
                else:
                    log_time_stamp = re.findall(r'(\d{14})\.log', se_log)
                    if 1 == len(log_time_stamp):
                        temp_log_files_list.append(log_time_stamp[0])

            if temp_log_files_list:
                if current_dir is None:
                    current_dir = self.host_expander_serial_log_path.replace('*', '')
                newest_serial_log_list.append(CommandOperation.format_linux_path_sep(os.path.join(
                    current_dir, max(*temp_log_files_list) + '.log')))
                temp_log_files_list.clear()

        return newest_serial_log_list

    def __set_host_expander_log_parameters(self) -> None:
        """
        author:      haibin.xu
        date:        2021-04-10 13:48:04
        description: 更新self.host_expander_log_dict参数

        :return:     None
        """
        if self.test_platform != constants.ENV_PLATFORM_REAL:
            ps3_expander_server_log = CommandOperation.format_linux_path_sep(os.path.join(
                constants.SIMULATOR_EXP_CLI_ROOT, str(self.exp_port), constants.SIMULATOR_EXP_EXPANDER_LOG))
            target_server_path = CommandOperation.format_linux_path_sep(os.path.join(
                constants.LOG_DIR_NAME_EXP_LOG, constants.LOG_DIR_NAME_EXP_SERVER_LOG))
            ps3_expander_export_log = CommandOperation.format_linux_path_sep(os.path.join(
                constants.SIMULATOR_EXP_CLI_ROOT, str(self.exp_port), constants.SIMULATOR_EXP_EXP_EXPORT_LOG))
            target_export_path = CommandOperation.format_linux_path_sep(os.path.join(
                constants.LOG_DIR_NAME_EXP_LOG, constants.LOG_DIR_NAME_EXP_EXPORT))
            self.host_expander_log_dict = {
                ps3_expander_server_log: target_server_path,
                ps3_expander_export_log: target_export_path,
            }
        else:
            # 物理环境，expander测试需要收集Message、minicom、寄存器日志
            ps3_expander_message_log = constants.SIMULATOR_HOST_MESSAGE_LOG_COLLECT_PATH
            target_message_path = CommandOperation.format_linux_path_sep(os.path.join(
                constants.LOG_DIR_NAME_EXP_LOG, constants.LOG_DIR_NAME_HOST_MESSAGE))
            self.host_expander_log_dict = {
                ps3_expander_message_log: target_message_path
            }
            ps3_cli_log = constants.SIMULATOR_IOC_CLI_LOG_COLLECT_PATH
            ps3_cli_collect_path = CommandOperation.format_linux_path_sep(os.path.join(
                constants.LOG_DIR_NAME_EXP_LOG, constants.LOG_DIR_NAME_HOST_MGT))
            self.host_expander_log_dict.update({ps3_cli_log: ps3_cli_collect_path})
            ps3_expander_serial_log = self.__get_newest_serial_log()
            target_serial_path = CommandOperation.format_linux_path_sep(os.path.join(
                constants.LOG_DIR_NAME_EXP_LOG, constants.LOG_DIR_NAME_HOST_SERIAL_LOG))
            for serial_log in ps3_expander_serial_log:
                match_list = re.findall(r'(minicom_log\d+).*', serial_log)
                if 1 == len(match_list):
                    tmp_dir = CommandOperation.format_linux_path_sep(os.path.join(target_serial_path, match_list[0]))
                else:
                    tmp_dir = target_serial_path
                self.host_expander_log_dict.update({serial_log: tmp_dir})
            if self.register_file:
                target_register_path = CommandOperation.format_linux_path_sep(os.path.join(
                    constants.LOG_DIR_NAME_EXP_LOG, constants.LOG_DIR_NAME_EXP_REGISTER_LOG))
                for reg_file in self.register_file:
                    self.host_expander_log_dict.update({reg_file: target_register_path})
            ps3_expander_log = self.__get_new_ps3_expander_log()
            target_ps3explog_path = CommandOperation.format_linux_path_sep(os.path.join(
                constants.LOG_DIR_NAME_EXP_LOG, libs_constants.LOG_COLL_PS3_EXP_LOG_DIR))
            for ps3explog in ps3_expander_log:
                self.host_expander_log_dict.update({ps3explog: target_ps3explog_path})

    def collect_expander_core_log(self) -> bool:
        """
        :author:
        :date:2021.05.15
        :description: 收集模拟平台expander侧core日志
        :return collect_flag: 是否收集到了Core文件

        @changelog
        """
        log.info('Start to collect expander core log...')
        # hba/raid + exp环境
        if libs_constants.TEST_ENTRY_HOST == self.test_entry:
            self.__get_node_info()
            exp_root_path = libs_constants.PS3SIM_EXP_ROOT.format(self.ioc_node_id) \
                if self.ioc_node_id is not None else ''
            target_ip = self.ioc_ip
            collect_path = self.ioc_collect_path
        # 单独exp环境
        else:
            exp_root_path = CommandOperation.format_linux_path_sep(os.path.join(
                constants.SIMULATOR_EXP_CLI_ROOT, self.exp_port + libs_constants.STR_LEFT_SLASH))
            target_ip = self.host_ip
            collect_path = self.host_collect_path

        collect_flag = self.__collect_crash_core_log(file_path=exp_root_path,
                                                     directory_name=libs_constants.LOG_COLL_EXP_CORE_DIR,
                                                     collect_to_path=collect_path,
                                                     ip=target_ip, server_msg='exp process', log_type='core')
        log.info('Finish to collect expander core log.\n')

        return collect_flag

    def collect_host_expander_log(self) -> bool:
        """
        :author:DuPanPan
        :date:2020.10.26
        :description: 拷贝Expander日志文件到日志服务器
        :return: 无返回值

        @changelog      2021-03-29 20:45:27  haibin.xu
                        1. 优化函数实现, 函数名修正：log_collect_simulator_expander -> collect_host_expander_log
                        2021-10-23 08:56:26  haibin.xu
                        1. 优化函数实现，注释掉清理expander日志部分，即init_expander_log行
        """
        log.info('test_entry: {}, test_object: {}, test_platform: {}, Start to collect host expander log ...'.format(
            self.test_entry, self.test_object, self.test_platform))

        if RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(ip=self.host_ip):
            log.error('Not to collect host expander log, reason: failed to connect to host server.')
            return

        delete_old_dir, _ = FileOperation.delete_file(path=self.host_collect_path, ip=self.host_ip, match_flag=False,
                                                      file_check_flag=False)
        if RtnStatusEnum.SUCCESS.value != delete_old_dir:
            log.error('Can not delete old directory: {}, not to collect host server expander log.'.format(
                self.host_collect_path))
            return

        # 收集/expAdmin.log 日志文件
        self.__set_host_expander_log_parameters()
        collect_flag = self.__collect_log_in_current_directory(log_dict=self.host_expander_log_dict,
                                                               collect_to_path=self.host_collect_path,
                                                               server_msg='host', ip=self.host_ip)

        if self.test_platform != constants.ENV_PLATFORM_REAL:
            # 收集expander core文件
            self.collect_expander_core_log()
        # 打包
        compress_file_flag = self.__pack_collect_log(
            file_path=self.host_collect_path, tar_file_path=self.host_collect_tar, server_msg='host',
            ip=self.host_ip) if collect_flag else False

        # 传输
        scp_file_flag = self.__scp_collect_log_to_log_server(
            source_file=self.host_collect_tar, server_msg='host', source_ip=self.host_ip) if compress_file_flag \
            else False

        # 解包
        success_collect_log_flag = self.__unpack_collect_log_in_log_server(
            tar_file=self.host_collect_tar, untar_file=self.host_collect_path, server_msg='host') if scp_file_flag \
            else False

        if success_collect_log_flag:
            # 删除打包文件
            self.__delete_collect_log(pack_flag=compress_file_flag, scp_flag=scp_file_flag,
                                      collect_path=self.host_collect_path, colletc_tar_path=self.host_collect_tar,
                                      ip=self.host_ip, server_msg='host')

        if success_collect_log_flag:
            # self.init_expander_log(self.host_expander_log_dict, self.host_ip)
            log.info('Finish to collect host expander log file to log server.\n')
        else:
            log.error('Fail to collect host expander log file to log server.\n')

        return success_collect_log_flag

    def __set_ps3_server_framework_log_parameters(self, source_framework_log_path: str = None,
                                                  source_script_log_path: str = None,
                                                  script_name: str = None) -> None:
        """
        author:      haibin.xu
        date:        2021-04-12 09:15:47
        description: 更新self.ps3_server_framework_log_dict参数
        :param source_framework_log_path: 框架日志文件所在路径
        :param source_script_log_path: 脚本日志文件夹所在路径
        :param script_name: 脚本名称

        :return:     None
        """
        # 收集此次脚本日志 /script_dir/script_name*
        log.info('source_framework_log_path: {}, source_script_log_path: {}, script_name: {}'.format(
            source_framework_log_path, source_script_log_path, script_name))
        script_name, _ = self.get_filename_from_path(file_path=script_name)
        log.info('script_name: {}'.format(script_name))

        self.ps3_server_framework_log_dict = {
            source_framework_log_path: constants.LOG_DIR_NAME_PS3_SERVER,
            source_script_log_path: constants.LOG_DIR_NAME_PS3_SERVER,
        }

        if script_name is not None:
            ioc_threads_log_path = CommandOperation.format_linux_path_sep(os.path.join(
                os.path.dirname(source_script_log_path), 'threads_data.log'))
            ioc_meminfo_log_path = CommandOperation.format_linux_path_sep(os.path.join(
                os.path.dirname(source_script_log_path), 'meminfo_data.log'))
            if self.ps3_server_framework_log_dict.get(source_script_log_path):
                del self.ps3_server_framework_log_dict[source_script_log_path]
            source_script_log_path = CommandOperation.format_linux_path_sep(
                os.path.join(source_script_log_path, script_name + '*'))
            log.info('source_script_log_path: {}'.format(source_script_log_path))
            self.ps3_server_framework_log_dict.update(
                {
                    ioc_threads_log_path: constants.LOG_DIR_NAME_PS3_SERVER,
                    ioc_meminfo_log_path: constants.LOG_DIR_NAME_PS3_SERVER,
                    source_script_log_path: constants.LOG_DIR_NAME_PS3_SERVER,
                }
            )

        log.info('Get ps3 server framework log: {}'.format(self.ps3_server_framework_log_dict))

    def collect_framework_log(self, source_framework_log_path: str = None, source_script_log_path: str = None,
                              script_name: str = None) -> None:
        """
        :author:DuPanPan
        :date:2020.04.26
        :description: 拷贝框架日志文件到日志服务器
        :param source_framework_log_path: 框架日志文件所在路径
        :param source_script_log_path: 脚本日志文件夹所在路径
        :param script_name: 脚本名称
        :return: 无返回值

        @changelog      2021-03-30 10:49:24  haibin.xu
                        1. 优化函数实现, 函数名修正：log_collect_ps3_server -> collect_framework_log
        """
        log.info('Start to collect framework log file to log server...')

        username = 'testYF/[your-name]'
        # 外网暂时写死root
        if self.test_platform == constants.ENV_PLATFORM_REAL:
            username = 'root'

        # 收集框架和脚本日志
        self.__set_ps3_server_framework_log_parameters(source_framework_log_path, source_script_log_path,
                                                       script_name)
        collect_flag = self.__collect_log_in_current_directory(log_dict=self.ps3_server_framework_log_dict,
                                                               collect_to_path='', server_msg='ps3',
                                                               ip=self.ps3_server_ip, username=username,
                                                               localpath_flag=True)

        # 打包
        compress_file_flag = self.__pack_collect_log(file_path=self.ps3_server_collect_path,
                                                     tar_file_path=self.ps3_server_collect_tar, server_msg='ps3',
                                                     ip=self.ps3_server_ip, localpath_flag=True,
                                                     username=username, is_pigz=False) if collect_flag else False

        # 传输
        scp_file_flag = self.__scp_collect_log_to_log_server(source_file=self.ps3_server_collect_tar,
                                                             localpath_flag=True, server_msg='ps3',
                                                             source_ip=self.ps3_server_ip,
                                                             source_username=username) if \
            compress_file_flag else False

        # 解包
        success_collect_log_flag = self.__unpack_collect_log_in_log_server(tar_file=self.ps3_server_collect_tar,
                                                                           untar_file=self.ps3_server_collect_path,
                                                                           server_msg='ps3') if scp_file_flag else \
            False
        if success_collect_log_flag:
            # 删除打包文件
            self.__delete_collect_log(pack_flag=compress_file_flag, scp_flag=scp_file_flag,
                                      collect_path=self.ps3_server_collect_path,
                                      colletc_tar_path=self.ps3_server_collect_tar, ip=self.ps3_server_ip,
                                      server_msg='ps3', localpath_flag=True, username=username)

        if success_collect_log_flag:
            log.info('Finish to collect framework log file to log server.\n')
        else:
            log.error('Fail to collect framework log file to log server.\n')

    def __set_ioc_pcie_switch_log_parameters(self) -> None:
        """
        author:      haibin.xu
        date:        2021-03-20 10:13:59
        description: 更新pcieSwitch在ioc宿主机端的日志收集路径字典

        :return:     None

        @changelog      2021-03-30 11:36:32  haibin.xu
                        1. 优化函数实现, 函数名修正：pcie_switch_ioc_server_log_dict_update ->
                        __set_ioc_pcie_switch_log_parameters
        """
        self.__get_node_info()
        self.ioc_pcieswitch_log_dict = {
            constants.SIMULATOR_IOC_SERVER_PCIESWITCH_LOG_CLEAR_PATH.format(self.ioc_node_name, self.ioc_node_name):
                constants.SIMULATOR_QEMU_IOC_PCIESWITCH_LOG_COLLECT_DIR,
            constants.SIMULATOR_IOC_SERVER_SIMUSWITCH_LOG_CLEAR_PATH.format(self.ioc_node_name, self.ioc_node_name):
                constants.SIMULATOR_QEMU_IOC_PCIESWITCH_LOG_COLLECT_DIR
        } if self.ioc_node_name is not None else {}

        log.info('pcie switch ioc log data: %s' % self.ioc_pcieswitch_log_dict)

    def __set_ioc_expander_log_parameters(self) -> None:
        """
        author: luyafei
        date: 2020.12.31
        description: 更新expander在ioc宿主机端的日志收集路径字典
        :return: True更新成功 False更新失败

        @changelog      2021-03-30 11:43:39  haibin.xu
                        1. 优化函数实现，函数名修正：exp_ioc_server_log_dict_update -> __set_ioc_expander_log_parameters
        """
        self.__get_node_info()
        ioc_server_exp_log_dir = '/opt/ps3sim/iocnode{}_expander/'.format(self.ioc_node_id) \
            if self.ioc_node_id is not None else None
        ps3_expander_log_path = CommandOperation.format_linux_path_sep(
            os.path.join(ioc_server_exp_log_dir, constants.SIMULATOR_EXP_EXPANDER_LOG)) \
            if ioc_server_exp_log_dir is not None else None
        simu_expander_log_path = CommandOperation.format_linux_path_sep(
            os.path.join(ioc_server_exp_log_dir, constants.SIMULATOR_EXP_EXP_EXPORT_LOG)) \
            if ioc_server_exp_log_dir is not None else None

        self.ioc_expander_log_dict = {
            ps3_expander_log_path: constants.SIMULATOR_QEMU_IOC_EXP_LOG_COLLECT_DIR,
            simu_expander_log_path: constants.SIMULATOR_QEMU_IOC_EXP_LOG_COLLECT_DIR
        } if ioc_server_exp_log_dir is not None else {}

        log.debug('expander ioc server log dict: {}'.format(self.ioc_expander_log_dict))

    def collect_ioc_expander_log(self) -> bool:
        """
        author:      haibin.xu
        date:        2021-03-30 13:44:52
        description: 收集ioc宿主机上Expander相关日志

        :return:     bool

        @changelog      2021-10-23 08:57:45  haibin.xu
                        1. 优化函数实现，注释掉清理expander日志部分，即init_expander_log行
        """
        log.info('Start to collect ioc expander log file to log server...')

        if RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(ip=self.ioc_ip):
            log.error('Not to collect ioc log, reason: failed to connect to ioc server.')
            return

        # 收集ioc宿主机上Expander相关日志到~/ioc_log目录
        self.__set_ioc_expander_log_parameters()
        collect_flag = self.__collect_log_in_current_directory(log_dict=self.ioc_expander_log_dict,
                                                               collect_to_path=self.ioc_collect_path,
                                                               server_msg='ioc', ip=self.ioc_ip)

        self.collect_expander_core_log()

        if collect_flag:
            # self.init_expander_log(self.ioc_expander_log_dict, self.ioc_ip)
            log.info('Finish to collect ioc expander log file to log server.\n')
        else:
            log.error('Fail to collect ioc expander log file to log server.\n')

        return collect_flag

    def collect_ioc_pcie_switch_log(self) -> bool:
        """
        author:      haibin.xu
        date:        2021-03-30 14:01:30
        description: 收集ioc宿主机pcie switch相关日志

        :return: bool
        """
        log.info('Start to collect ioc pcie switch log file to log server...')

        if RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(ip=self.ioc_ip):
            log.error('Not to collect ioc log, reason: failed to connect to ioc server.')
            return

        # 收集ioc宿主机pcie switch相关日志到~/ioc_log目录
        self.__set_ioc_pcie_switch_log_parameters()
        collect_flag = self.__collect_log_in_current_directory(log_dict=self.ioc_pcieswitch_log_dict,
                                                               collect_to_path=self.ioc_collect_path,
                                                               server_msg='ioc', ip=self.ioc_ip)
        if collect_flag:
            self.init_expander_log(self.ioc_pcieswitch_log_dict, self.ioc_ip)
            log.info('Finish to collect ioc pcie switch log file to log server.\n')
        else:
            log.error('Fail to collect ioc pcie switch log file to log server.\n')

        return collect_flag

    def __set_ioc_log_parameters(self) -> None:
        """
        author: sunql
        date:   2022.01.29
        description: 更新ioc_log_dict变量
        :return: None
        """
        self.__get_node_info()
        find_cmd_dict = {
            'test_ioc_node_logs': f'find /opt/ps3sim/ -name ' + f'"test_node{self.ioc_node_id}*" ',
            'qemu_ioc_node_logs': f'find /opt/ps3sim/ -name ' + f'"qemu_log_node{self.ioc_node_id}*" '
        }

        for collect_path, cmd in find_cmd_dict.items():
            try:
                rtn_code, log_files = FileOperation.get_files_with_cmd(find_files_cmd=cmd, ip=self.ioc_ip)
            except Exception as e:
                log.error('Found exception during find files, exception: {}'.format(e))
                rtn_code, log_files = RtnStatusEnum.FAIL.value, []

            if RtnStatusEnum.SUCCESS.value == rtn_code:
                for log_path in log_files:
                    self.ioc_log_dict.update({log_path: collect_path})

        log.debug('ioc log dict: {}.'.format(self.ioc_log_dict))

    def collect_ioc_other_log(self) -> bool:
        """
        author:      sunql
        date:        2022-01-30 14:01:30
        description: 收集ioc宿主机相关日志

        :return: bool
        """
        log.info('Start to collect ioc log file to log server...')

        if RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(ip=self.ioc_ip):
            log.error('Not to collect ioc log, reason: failed to connect to ioc server.')
            return

        # 收集ioc宿主机相关日志到~/ioc_log目录
        self.__set_ioc_log_parameters()
        collect_flag = self.__collect_log_in_current_directory(log_dict=self.ioc_log_dict,
                                                               collect_to_path=self.ioc_collect_path,
                                                               server_msg='ioc', ip=self.ioc_ip)
        if collect_flag:
            # self.init_expander_log(self.ioc_expander_log_dict, self.ioc_ip)
            log.info('Finish to collect ioc log file to log server.\n')
        else:
            log.error('Fail to collect ioc log file to log server.\n')

        return collect_flag

    def collect_ioc_log(self) -> bool:
        """
        author: luyafei
        date: 2020.12.29
        description: 收集ioc宿主机上Expander, pcieSwitch相关日志(当前需要在IOC宿主机上收集的日志)
        :return: bool

        @changelog      2021-03-30 11:52:50  haibin.xu
                        1. 优化函数实现, 函数名修正：log_collect_ioc_server -> collect_ioc_log
                        2022-06-07 17:30:01  haibin.xu
                        1. 优化函数实现, 收集ioc log后添加ioc_log目录判断，最后返回结果如果是日志为空未收集（未创建ioc_log）情况下，
                        也返回True
        """
        log.info('test_entry: {}, test_object: {}, Start to collect ioc log ...'.format(
            self.test_entry, self.test_object))

        if RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(ip=self.ioc_ip):
            log.error('Not to collect ioc log, reason: failed to connect to ioc server.')
            return

        delete_old_dir, _ = FileOperation.delete_file(path=self.ioc_collect_path, ip=self.ioc_ip, match_flag=False,
                                                      file_check_flag=False)
        if RtnStatusEnum.SUCCESS.value != delete_old_dir:
            log.error('Can not delete old directory: {}, not to collect ioc server log.'.format(
                self.ioc_collect_path))
            return

        collect_expander_flag = False
        collect_pcie_flag = False
        if (libs_constants.TEST_ENTRY_HOST == self.test_entry) and \
                (constants.ENV_TEST_OBJECT_PCIE_SWITCH != self.test_object):
            collect_expander_flag = self.collect_ioc_expander_log()
        if constants.ENV_TEST_OBJECT_PCIE_SWITCH == self.test_object:
            collect_pcie_flag = self.collect_ioc_pcie_switch_log()

        # 收集ioc端log
        collect_flag = self.collect_ioc_other_log() or collect_expander_flag or collect_pcie_flag
        # haibin.xu 2022-06-07 17:26:26 modify: 添加检查ioc_log目录是否存在
        if RtnStatusEnum.SUCCESS.value == FileOperation.dir_path_exists(path=self.ioc_collect_path, ip=self.ioc_ip):
            ioc_log_exist_flag = True
        else:
            ioc_log_exist_flag = False
        # haibin.xu 2022-06-07 17:26:50 modify: 只有ioc_log目录存在才打包
        compress_file_flag = self.__pack_collect_log(
            file_path=self.ioc_collect_path, tar_file_path=self.ioc_collect_tar,
            server_msg='ioc', ip=self.ioc_ip, is_pigz=False) \
            if ioc_log_exist_flag else False

        # 传输
        scp_file_flag = self.__scp_collect_log_to_log_server(
            source_file=self.ioc_collect_tar, server_msg='ioc', source_ip=self.ioc_ip) if compress_file_flag \
            else False

        # 解包
        success_collect_log_flag = self.__unpack_collect_log_in_log_server(
            tar_file=self.ioc_collect_tar, untar_file=self.ioc_collect_path, server_msg='ioc') if scp_file_flag \
            else False

        if success_collect_log_flag:
            # 删除打包文件
            self.__delete_collect_log(pack_flag=compress_file_flag, scp_flag=scp_file_flag,
                                      collect_path=self.ioc_collect_path, colletc_tar_path=self.ioc_collect_tar,
                                      ip=self.ioc_ip, server_msg='ioc')

        if success_collect_log_flag:
            log.info('Finish to collect ioc log file to log server.\n')
        # haibin.xu 2022-06-07 17:33:18 modify: 添加日志为空未收集（未创建ioc_log）情况下的日志打印
        elif collect_flag and (not ioc_log_exist_flag):
            log.info('Not found ioc log files, not need to collect ioc log to log server.\n')
        else:
            log.error('Fail to collect ioc log file to log server.\n')

        # haibin.xu 2022-06-07 17:25:03 modify: 成功收集日志或者是日志为空未收集（未创建ioc_log）情况下，都返回True
        if success_collect_log_flag or (collect_flag and (not ioc_log_exist_flag)):
            rtn_collect_flag = True
        else:
            rtn_collect_flag = False

        return rtn_collect_flag

    def collect_log(self) -> tuple:
        """
        :author:DuPanPan
        :date:2020.09.27
        :description: 拷贝虚拟平台上的日志
        :return: 返回ioc_crash_flag, ioc_core_flag, host_crash_flag

        @changelog      2021-03-30 14:27:03  haibin.xu
                        1. 优化函数实现, 函数名修正：log_collect_simulator -> collect_log
        """
        ioc_core_flag = False
        ioc_crash_flag = False
        host_crash_flag = False
        collect_log_flag = True

        log.info('Start to collect log...\n')

        simulator_path = CommandOperation.format_linux_path_sep(os.path.join(self.log_script_dir_path,
                                                                             constants.LOG_DIR_SIMULATOR_NAME))

        check_log_server = CommandOperation.check_ip_connect(ip=self.log_server_ip,
                                                             ssh_username=self.log_server_account)
        if RtnStatusEnum.SUCCESS.value != check_log_server:
            log.error('Failed to connect log server: {}@{}:22, not collect log.'.format(
                self.log_server_account, self.log_server_ip))
        elif RtnStatusEnum.SUCCESS.value == FileOperation.make_directory(
                dir_name=simulator_path, ip=self.log_server_ip, username=self.log_server_account, match_flag=False):
            log.info('Finish to make directory: {}, in log server.\n'.format(simulator_path))
            if ((constants.ENV_TEST_ENTRY_IOC == self.test_entry) and
                (constants.ENV_TEST_OBJECT_EXPANDER == self.test_object)) or (
                    (constants.ENV_TEST_ENTRY_HOST == self.test_entry) and
                    (constants.ENV_TEST_OBJECT_EXPANDER == self.test_object) and
                    (constants.ENV_PLATFORM_REAL == self.test_platform)):
                # 单独expander测试或物理环境expander测试
                collect_log_flag = self.collect_host_expander_log()
            else:
                # 如果是物理平台
                if self.test_platform == constants.ENV_PLATFORM_REAL:
                    print("------------real log coll---------")
                    collect_log_flag, host_crash_flag, ioc_core_flag = self.collect_host_log()
                else:
                    # 其他情况
                    ioc_crash_flag, ioc_core_flag, collect_qemu_log_flag = self.collect_ioc_qemu_log()
                    collect_ioc_log_flag = self.collect_ioc_log()
                    host_crash_flag = self.collect_host_qemu_log()
                    collect_host_log_flag, _, _ = self.collect_host_log()
                    collect_log_flag = collect_ioc_log_flag and collect_host_log_flag and collect_qemu_log_flag
        else:
            log.error('Fail to make directory: {}, in log server.\n'.format(simulator_path))

        log.info('collect all log to log server path: {}'.format(self.log_script_dir_path))
        log.info('Finish to collect log.\n')

        return ioc_crash_flag, ioc_core_flag, host_crash_flag, collect_log_flag

    def modify_log_permission(self, job_log_path: str) -> int:
        """
        author:      haibin.xu
        date:        2021-04-01 09:55:07
        description: 变更日志服务器中相关日志目录访问者权限

        :param job_log_path: 日志路径
        :return:     访问权限修改成功，返回0， 失败返回-1
        """
        rtn_modify = RtnStatusEnum.SUCCESS.value

        log.info('Start to change file mode ...')
        if constants.ENV_LOG_SERVER_ACCOUNT_FRAMEWORK == self.log_server_account:
            change_mode_cmd = 'sudo {} {}'.format(libs_constants.CHANGE_MODE_FILE_PATH, job_log_path)
            try:
                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                    cmd=change_mode_cmd, ssh_ip=self.log_server_ip, ssh_port='22',
                    ssh_username=self.log_server_account, timeout=60)
                rtn_code = CommandOperation.check_cli_output(change_mode_cmd, cmd_code, cmd_stdout, cmd_stderr)
            except Exception as e:
                log.error('Found exception when modify permission, exception: {}'.format(e))
                rtn_code = RtnStatusEnum.FAIL.value

            if RtnStatusEnum.SUCCESS.value == rtn_code:
                log.info('Finish to change file mode: {}.'.format(job_log_path))
            else:
                rtn_modify = RtnStatusEnum.FAIL.value
                log.error('Fail to change file mode: {}.'.format(job_log_path))
        else:
            log.error('Invalid log server account: {}'.format(self.log_server_account))
            rtn_modify = RtnStatusEnum.FAIL.value

        return rtn_modify

    def __check_disk_wanted_clear(self, check_path: str, ip: str, port: str) -> bool:
        """
        检查磁盘空间是否需要清理，如果使用率达到85%，返回true
        :author sunql
        :param check_path:
        :param ip:
        :param port:
        :return: bool
        """
        cmd = "df -h {} | grep {} | awk  '{}'".format(check_path, '/', '{print $5}')
        cmd_code, cmd_output, cmd_error = CommandOperation.execute_command_with_error(cmd, ssh_ip=ip, ssh_port=port,
                                                                                      timeout=20)
        if RtnStatusEnum.SUCCESS.value == cmd_code:
            disk_free_size = str(cmd_output).strip().strip('%')
            disk_free_size = int(disk_free_size) if len(disk_free_size) else 0
            log.info(f" qemu ip: {ip} , log disk used: {disk_free_size}%")
            if disk_free_size > 85:
                return True
        return False

    def clear_qemu_log_by_long_test(self):
        # 检查host qemu 磁盘空间
        if self.__check_disk_wanted_clear('/root', self.host_qemu_ip, self.host_port):
            # 获取host qemu端文件列表，并删除或清空
            self.set_host_qemu_files()
            self.delete_files(self.host_qemu_delete_files, self.host_qemu_ip, self.host_port)
            self.clean_files(self.host_qemu_clean_files, self.host_qemu_ip, self.host_port)

        if self.__check_disk_wanted_clear('/etc/ps3sim/log', self.ioc_qemu_ip,
                                          self.ioc_port) or self.__check_disk_wanted_clear('/var/log/ps3_log',
                                                                                           self.ioc_qemu_ip,
                                                                                           self.ioc_port):
            # 获取ioc qemu端文件列表，并删除或清空
            self.set_ioc_qemu_files()
            self.delete_files(self.ioc_qemu_delete_files, self.ioc_qemu_ip, self.ioc_port)
            self.clean_files(self.ioc_qemu_clean_files, self.ioc_qemu_ip, self.ioc_port)

    def __get_drv_path(self) -> str:
        drv_path = "/var/log/"
        if self.test_platform == constants.ENV_PLATFORM_REAL:
            drv_path = HostOperation.get_real_drv_path(ssh_ip=self.host_ip)
        return drv_path

    def __get_drv_delete_clean_files(self) -> None:
        self.drv_clean_files = []
        self.drv_delete_files = []

        # 命令的含义是：查找距系现在365*24H内修改或的文件（修改时间是升序）
        # find_drv_log_files_cmd = 'find /var/log/ps3sas_drv.log.* -mtime -365'
        # find_drv_bin_files_cmd = 'find /var/log/ps3sas_drv.bin.* -mtime -365'

        def get_drv_log(drv_path):
            find_drv_log_files_cmd = f"ls {drv_path}" + r" | grep 'ps3sas_drv.log.*' | sort -nr | sed -n '10,$p'"
            find_drv_bin_files_cmd = f"ls {drv_path}" + r" | grep 'ps3sas_drv.bin.*' | sort -nr | sed -n '10,$p'"
            drv_log_files = self.__get_drv_files(find_drv_log_files_cmd)
            drv_bin_files = self.__get_drv_files(find_drv_bin_files_cmd)

            if drv_log_files:
                # 补全路径
                for i in range(len(drv_log_files)):
                    drv_log_files[i] = f"{drv_path}{drv_log_files[i]}"

                # self.drv_clean_files.append(drv_log_files[0])
                # log.info('Driver clean files: {}'.format(self.drv_clean_files))
                # drv_log_files.pop(0)
                self.drv_delete_files.extend(drv_log_files)
                log.info('Driver delete files: {}'.format(self.drv_delete_files))

            if drv_bin_files:
                # 补全路径
                for i in range(len(drv_bin_files)):
                    drv_bin_files[i] = f"{drv_path}{drv_bin_files[i]}"
                # self.drv_clean_files.append(drv_bin_files[0])
                # log.info('Driver clean files: {}'.format(self.drv_clean_files))
                # drv_bin_files.pop(0)
                self.drv_delete_files.extend(drv_bin_files)
                log.info('Driver delete files: {}'.format(self.drv_delete_files))

        get_drv_log('/var/log/')
        get_drv_log('/var/log/drvlog/')

    def __get_drv_files(self, find_cmd: str) -> list:
        """
        author: luyafei
        date: 2021.11.26
        :param find_cmd: 获取驱动文件的命令
        :return: 驱动文件列表
        """
        try:
            rtn_code, drv_files = FileOperation.get_files_with_cmd(find_files_cmd=find_cmd, ip=self.host_qemu_ip)
        except Exception as e:
            log.error('Found exception during get driver files: {}, exception: {}'.format(find_cmd, e))
            rtn_code, drv_files = RtnStatusEnum.FAIL.value, []

        if RtnStatusEnum.SUCCESS.value == rtn_code and drv_files:
            # 将获取到的主机驱动文件按照修改时间排序，升序
            log.info('Get driver files: {}.'.format(drv_files))
            # drv_files = sorted(drv_files, key=lambda drv_file: os.path.getmtime(drv_file))
        else:
            log.warning('Fail to find driver files or driver files is {}.'.format(drv_files))

        return drv_files


def __get_command_line_parameters() -> dict:
    """
    author:      haibin.xu
    date:        2021-04-01 17:30:25
    description: 获取命令行参数

    :return:     返回命令行参数字典
    """
    para_dict = {}
    para_dict.update({'host_ip': clap.CommandLineArgsParse.get_host_ip()})
    para_dict.update({'host_port': clap.CommandLineArgsParse.get_host_port()})
    para_dict.update({'host_qemu_ip': clap.CommandLineArgsParse.get_host_node_ip()})
    para_dict.update({'ioc_ip': clap.CommandLineArgsParse.get_soc_ip()})
    para_dict.update({'ioc_port': clap.CommandLineArgsParse.get_soc_port()})
    para_dict.update({'ioc_qemu_ip': clap.CommandLineArgsParse.get_soc_node_ip()})
    para_dict.update({'log_server_ip': clap.CommandLineArgsParse.get_log_server_ip()})
    para_dict.update({'log_server_account': clap.CommandLineArgsParse.get_log_server_account()})
    host_cpu = clap.CommandLineArgsParse.get_host_cpu()
    if 0 == host_cpu:
        host_cpu = 'x86'
    elif 2 == host_cpu:
        host_cpu = 'mips'
    else:
        host_cpu = 'arm'
    para_dict.update({'host_cpu': host_cpu})
    para_dict.update({'host_label': clap.CommandLineArgsParse.get_host_label()})
    test_object = clap.CommandLineArgsParse.get_test_object()
    if 1 == test_object:
        test_object = 'hba'
    elif 2 == test_object:
        test_object = 'expander'
    elif 3 == test_object:
        test_object = 'pcie_switch'
    else:
        test_object = 'raid'
    para_dict.update({'test_object': test_object})

    test_entry = clap.CommandLineArgsParse.get_test_entry()
    if 1 == test_entry:
        test_entry = 'soc'
    else:
        test_entry = 'host'
    para_dict.update({'test_entry': test_entry})

    test_platform = constants.ENV_PLATFORM_SIMU if clap.CommandLineArgsParse.get_simu_platform() else \
        constants.ENV_PLATFORM_REAL
    para_dict.update({'test_platform': test_platform})
    # 此处指定寄存器数据文件
    para_dict.update({'register_file': None})

    return para_dict


def main():
    # 解析输入的参数选项信息，供测试使用，使用者可以直接修改sys.argv列表，也可以直接使用命令行，使用命令行收集log时，务必注释掉sys.argv
    # sys.argv = [
    #     'collect_tool.py',
    #     '--hip', '10.22.81.1',
    #     '--hp', '22',
    #     '--hnip', '10.22.83.3',
    #     '--sip', '10.22.81.1',
    #     '--sp', '22',
    #     '--snip', '10.22.83.4',
    #     '--lsip', '10.22.65.11',
    #     '--lsac', 'framework',
    #     '--hc', '1',
    #     '--to', '0',
    #     '--te', '0',
    #     '--hl', 'vm000'
    # ]

    importlib.reload(clap)
    input_options = __get_command_line_parameters()
    log.info('Finish to parse command parameters.')
    # 此处执行寄存器数据文件路径
    # input_options['register_file'] = '/opt/dump_log/dump_register_20220222113113.log'
    log_collect_obj = LogCollect(manual_flag=True,
                                 host_ip=input_options.get('host_ip'),
                                 host_port=input_options.get('host_port'),
                                 host_qemu_ip=input_options.get('host_qemu_ip'),
                                 ioc_ip=input_options.get('ioc_ip'),
                                 ioc_port=input_options.get('ioc_port'),
                                 ioc_qemu_ip=input_options.get('ioc_qemu_ip'),
                                 log_server_ip=input_options.get('log_server_ip'),
                                 host_cpu=input_options.get('host_cpu'),
                                 log_server_account=input_options.get('log_server_account'),
                                 test_object=input_options.get('test_object'),
                                 test_entry=input_options.get('test_entry'),
                                 host_label=input_options.get('host_label'),
                                 test_platform=input_options.get('test_platform'),
                                 reg_file=input_options.get('register_file'))
    log.info('Finish to create log collect object.')
    log_root_directory = log_collect_obj.make_log_root_directory_in_log_server()
    log.info('Finish to make log root directory: {}'.format(log_root_directory))

    log_script_dir_path = log_collect_obj.make_script_directory_in_log_server()
    log.info('Finish to make log script directory: {}\n'.format(log_script_dir_path))

    if ((constants.ENV_TEST_ENTRY_IOC == input_options.get('test_entry')) and
        (constants.ENV_TEST_OBJECT_EXPANDER == input_options.get('test_object'))) or (
            (constants.ENV_TEST_ENTRY_HOST == input_options.get('test_entry')) and
            (constants.ENV_TEST_OBJECT_EXPANDER == input_options.get('test_object')) and
            (constants.ENV_PLATFORM_REAL == input_options.get('test_platform'))):
        log_collect_obj.update_ps3_exp_log_record_data()
        # 单独expander测试或物理环境expander测试
        log_collect_obj.collect_host_expander_log()
    else:
        # 如果是物理平台
        if input_options.get('test_platform') == constants.ENV_PLATFORM_REAL:
            print("%%%%%%%%%%%%%%%%%% real plat form %%%%%%%%%%%%%%%%%%%%%%%%55")
            log_collect_obj.collect_host_log()
        else:
            # 其他情况
            log_collect_obj.collect_ioc_qemu_log()
            log_collect_obj.collect_ioc_log()
            log_collect_obj.collect_host_qemu_log()
            log_collect_obj.collect_host_log()

    if RtnStatusEnum.SUCCESS.value == log_collect_obj.modify_log_permission(log_root_directory):
        log.info('Finish to modify permission of log: {}\n\n'.format(log_root_directory))
    else:
        log.warning('Fail to modify permission of log: {}\n\n'.format(log_root_directory))

    log.info('Finish collect all log to file: {}@{}:{}'.format(log_collect_obj.log_server_account,
                                                               log_collect_obj.log_server_ip,
                                                               log_collect_obj.log_root_dir_path))


if __name__ == '__main__':
    main()
