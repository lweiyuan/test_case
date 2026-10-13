#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author: xianda.liu
date: 2022-07-22
description: 用例脚本一级基类

@steps:
    1.初始化脚本日志文件
    2.检查通用物理环境
    3.准备测试环境
    4.执行测试
    5.清理测试环境
    6.根据脚本执行结果返回相应的exit code及output
"""
import ctypes
import inspect
import os
import re
import sys
import abc
import time
import shutil
import traceback
import threading
import configparser
import subprocess

from scripts.script_libs import log
from scripts.script_libs import constants
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse
from scripts.script_libs.file_operation import FileOperation
from scripts.script_libs.ethtool_operation import EthtoolOperation
from scripts.script_libs.dcbtool_operation import DcbtoolOperation
from scripts.script_libs.enums import BugTypeEnum, RtnStatusEnum, ExitCodeEnum, TestObjectType, TestEntryEnum
from scripts.script_libs.command_operation import CommandOperation

# test/esat/scripts 目录绝对路径
SCRIPTS_DIRECTORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# test/esat 目录绝对路径
ESAT_DIRECTORY = os.path.dirname(SCRIPTS_DIRECTORY)


class SxeException(Exception):
    """用于create_bug方法中中抛该异常，Run方法中捕获"""
    pass


class SxeThread(threading.Thread):
    """
    author:      xianda.liu
    date:        2022-07-22
    description: 用于创建多线程使用，重写了threading.Thread的run、join方法，在子线程报异常时，
                 主线程可以捕获到，具体看参考scripts.test_example.test.py中的使用
    """

    def __init__(self, func_name, *args, **kwargs):
        threading.Thread.__init__(self)
        self.args = args
        self.kwargs = kwargs
        self.func_name = func_name
        self.exception = None
        self.ret = None
        self.exit_code = 0
        # self.exc_traceback = ''

    def run(self) -> None:
        """
        author:      xianda.liu
        date:        2022-07-22
        description: 重写父类中的 run 方法，实现捕获子进程的 SxeException 异常
        """
        try:
            self.ret = self.func_name(*self.args, **self.kwargs)
        except (SxeException, Exception) as e:
            self.exception = e
            self.exit_code = 1
            print('run exception', e)
            # self.exc_traceback = traceback.format_exc()
        finally:
            del self.func_name, self.args, self.kwargs

    def join(self, timeout=None) -> tuple:
        """
        author:      haibin.xu
        date:        2020-10-01 16:45:26
        description: 重写父类中的 join 方法，增加抛 SxeException 异常功能
        :param timeout: 超时等待时间，该参数未使用，因为父类中含有该参数，所以重写时，必须要加上
        """
        super(SxeThread, self).join()
        if self.exception:
            raise self.exception
        return self.ret

    def result(self) -> tuple:
        """
        author:      xiangyu.liu
        date:        2020-10-01 16:45:26
        description: 获取函数执行结果
        """
        return self.ret

    def async_raise(tid, exctype):
        """raises the exception, performs cleanup if needed"""
        tid = ctypes.c_long(tid)
        if not inspect.isclass(exctype):
            exctype = type(exctype)
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
        if res == 0:
            raise ValueError("invalid thread id")
        elif res != 1:
            # """if it returns a number greater than one, you're in trouble,
            # and you should call it again with exc=NULL to revert the effect"""
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
            raise SystemError("PyThreadState_SetAsyncExc failed")


class ScriptBase(metaclass=abc.ABCMeta):
    """在每个用例脚本二级基类或者用例脚本里，必须给以下变量赋值"""
    test_object = ''
    test_module = ''
    test_tool = constants.SXE2CLI64  # 默认值constants.SXE2CLI64
    test_precondition = ''
    test_steps = ''

    """产生bug时必须给下面的变量赋值"""
    bug_title = ''
    bug_result = ''
    bug_expect = ''
    # 该参数需要调用set_bug_type来设定
    __bug_type = ''

    """设置测试各阶段的时间初始值"""  # -liuxd 保留
    # 通用物理环境的运行时间
    __chk_physical_env_duration = 0
    # 脚本自有环境的运行时间
    __chk_own_env_duration = 0
    # prepare阶段的运行时间
    __prepare_duration = 0
    # do阶段的运行时间
    __do_duration = 0
    # post阶段的运行时间
    __post_duration = 0

    # 所有脚本统一的物理环境开关
    __physical_environment_enabled = False
    # 特定case配置的物理环境开关
    own_environment_enabled = False
    # 特定case是否需要调整测试方向，默认ip1为server，ip2为client
    test_direction_reverse = False
    # 当有2个可测网口时，测试目标port顺序反向，默认测试第一口，当设为tree时，第二口将作为目标测试网口
    test_port_reverse = False
    # 测试目标port
    target_port = 0

    # 执行prepare操作结果标志位
    __prepare_flag = False
    # 执行do操作的结果标志位
    __do_flag = False
    # 执行post操作的结果标志位
    __post_flag = False
    # prepare、do阶段产生bug标志位
    __bug_in_prepare_do_flag = False
    # post阶段产生bug标志位
    __bug_in_post_flag = False
    # prepare/do/post阶段代码执行出现异常报错
    __exception_in_prepare_do_post_flag = False
    # 设置二次环境检查标志位
    __second_check_flag = False
    # 设置清理环境前的等待时间
    __wait_time_before_clear_env = 3

    # server_ip
    server_logical_ip = ''
    # soc_ip
    client_logical_ip = ''
    # server端串口连接位置
    server_serial_cli_exec_address = ''
    # client端串口连接位置
    client_serial_cli_exec_address = ''

    # 测试正常的result信息
    __normal_result = {}
    # prepare、do阶段的result信息保存在__test_result中
    __test_result = {}
    # post阶段的result信息保存在__post_result中
    __post_result = {}

    # 定义多线程锁
    __thread_lock = threading.Lock()

    # jekins配置环境
    __jenkins_physical_params_list = []
    # 日志文件路径
    __script_log_path = ''
    # iops 信息
    __iops = '-'
    # 带宽 信息
    __bw = '-'
    # 延时信息
    __resp_time = '-'
    # 性能统计信息
    __raw_perf_data = '-'
    # 临时文件保存目录
    __temp_directory_path = ''
    # 执行当期脚本结束后，停止测试，保留环境
    __stop_test = 'no'
    # 脚本进程id
    __script_pid = 0
    __script_cli_time = '-'
    # 脚本skip提示信息
    skip_message = {}

    # client测试对象
    client_test_object = TestObjectType.PF.value
    # server测试对象
    server_test_object = TestObjectType.PF.value
    # 所需数量,功能测试默认均为1, 为1时可以选择是否调用common_check_environment
    client_test_object_num = 1
    server_test_object_num = 1
    # 测试设备信息，server/client端各1个，用于收发测试、打流测试、压力测试，格式如下
    test_device_info_list = []
    test_device_info_dict = {}
    """
        {
            client_device_ip:
            server_device_ip:
            client_device_ipv6:
            server_device_ipv6:
            client_device_mac:
            server_device_mac:
            client_device_name:
            server_device_name:
            client_pf_device_name:
            server_pf_device_name:
            server_bus_info:
            client_bus_info: 
        }
        """
    iperf_result_list = []
    ping_result_list = []
    test_port = CommandLineArgsParse.get_test_port()
    non_blocking_bug_dict = {}

    @classmethod
    def __init_script_log(cls) -> None:
        """
        author: xianda.liu
        date  : 2022-07-22
        descriptor: 初始化脚本执行日志
        :return: 无返回值
        """
        # 通过命令行参数获取log存放目录
        log_default_path = CommandLineArgsParse.get_log_output_path()
        # 如果命令行参数中没有配置log保存目录或log目录不存在时，使用默认路径
        if ('' == log_default_path) or (not os.path.exists(log_default_path)):
            # 此处不能使用log，因为此时log模块还未完成初始化，只有log模块初始化完成，才能使用log打印
            print('Warning! Log file path not specified or invalid, Will use default script path. ')
            log_default_path = os.path.join(ESAT_DIRECTORY, constants.LOG_DEFAULT_PATH_NAME)
            # 如果不存在test/esat/outputs/scripts目录，则创建该目录
            if not os.path.exists(log_default_path):
                os.mkdir(log_default_path)

        # 从获取脚本路径获取脚本名称
        script_name = os.path.basename(sys.argv[0]).replace('.py', '')

        # 构建脚本日志路径
        timestamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
        cls.__script_log_path = os.path.join(FileOperation.normalize_path(log_default_path),
                                             script_name) + '_' + timestamp + '.log'
        # 初始化脚本日志
        log.init(cls.__script_log_path)
        # 脚本日志初始化完成，log模块打印第一条信息，输出log日志保存路径
        log.info('Log init success, save log file to: {}'.format(cls.__script_log_path))

    @classmethod
    def __init_temp_directory(cls) -> None:
        """
        author:      xianda.liu
        date:        2022-07-22
        description: 初始化临时中转目录，该目录不存在时，创建该目录，该目录存在时，直接删除再创建该目录，作为文件操作中从远程服务器
                     上拷贝文件到本地的临时存放路径
        :return:     无返回值

        @changelog:
        """
        # 通过 __file__ 参数获取 test/esat/scripts 目录
        cls.__temp_directory_path = os.path.join(SCRIPTS_DIRECTORY, constants.FILE_TEMP_PATH_NAME)

        if os.path.exists(cls.__temp_directory_path):
            if os.path.isdir(cls.__temp_directory_path):
                shutil.rmtree(cls.__temp_directory_path)
            else:
                os.remove(cls.__temp_directory_path)
        os.mkdir(cls.__temp_directory_path)

        log.info('Temp file save directory init success, path: {}'.format(cls.__temp_directory_path))

    @classmethod
    def get_temp_directory_path(cls) -> str:
        """
        author:      haibin.xu
        date:        2023-11-20 17:01:08
        description: 返回创建的临时目录路径

        :return:     返回创建的临时目录路径
        """
        return cls.__temp_directory_path

    @classmethod
    def __check_script_file(cls) -> bool:
        """
        author:      xianda.liu
        date:        2022-07-22
        description: 判断测试机目录/root/sxetest是否存在，不存在的情况下，创建该目录，创建失败，报异常
        :return:     None
        """
        rtn_path_flag = True
        # 对server/client两端测试机均检查/创建/root/sxetest目录（携带ssh ip/port，避免在本地误判）
        check_nodes = (
            (CommandLineArgsParse.get_server_ip(), str(CommandLineArgsParse.get_server_port())),
            (CommandLineArgsParse.get_client_ip(), str(CommandLineArgsParse.get_client_port())),
        )
        for node_ip, node_port in check_nodes:
            # 判断/root/sxetest是否存在
            path_exists_flag, _ = FileOperation.path_exists(
                constants.FILE_PATH_ROOT, ip=node_ip, port=node_port)
            # 不存在，创建该目录
            if RtnStatusEnum.SUCCESS.value != path_exists_flag:
                # 如果创建失败，报异常
                if RtnStatusEnum.FAIL.value == FileOperation.make_directory(
                        constants.FILE_PATH_ROOT, ip=node_ip, port=node_port):
                    rtn_path_flag = False
                    log.error('Error make directory: {}@{}.'.format(constants.FILE_PATH_ROOT, node_ip))
                else:
                    log.info('Success make directory: {}@{}, init file pass.'.format(
                        constants.FILE_PATH_ROOT, node_ip))
            else:
                log.info('Found directory: {}@{}, init file pass.'.format(
                    constants.FILE_PATH_ROOT, node_ip))
        return rtn_path_flag

    @classmethod
    def __check_ip(cls) -> bool:
        """
        author:      xianda.liu
        date:        2022-07-22
        description: 获取并检查logical_server_ip, logical_client_ip
        :return:     ip存在且格式正确返回True，否则返回False
        """
        log.info(" check ip start ")
        rtn_ip_flag = False
        # 从命令行中获取ip信息
        server_ip = CommandLineArgsParse.get_server_ip()
        client_ip = CommandLineArgsParse.get_client_ip()
        log.info(f"absolute server ip :{server_ip},absolute client ip:{client_ip}")
        # 正则匹配server ip和client ip格式是否准确, 同时符合才返回True
        if re.match(constants.PATTERN_IP, server_ip) and \
                re.match(constants.PATTERN_IP, client_ip):
            rtn_ip_flag = True
        else:
            log.error('Not found valid server ip and client ip.')

        return rtn_ip_flag

    @classmethod
    def __update_env_config(cls) -> None:
        """
        将配置文件nic_driver_config.ini中的server和client信息对调
        :return:
        """
        shutil.copy(constants.NIC_CONFIG_BK_PATH, constants.NIC_CONFIG_PATH)
        # FileOperation.copy_file(constants.NIC_CONFIG_BK_PATH, constants.NIC_CONFIG_PATH,
        #                         local_execute=True, match_flag=False, file_check_flag=False)

    @classmethod
    def __reverse_test_direction(cls) -> None:
        """
        将配置文件nic_driver_config.ini中的server和client信息对调
        :return:
        """
        config = configparser.ConfigParser()
        config.read(constants.NIC_CONFIG_PATH)

        log.warning("reverse_test_direction ==> before:".format())
        log.info("nic_driver==> server:{},client:{}".format(config['nic_driver']['server'],
                                                            config['nic_driver']['client']))
        log.info("nic_os==> server:{},client:{}".format(config['nic_os']['server'], config['nic_os']['client']))
        log.info("logical_ip==> server:{},client:{}".format(config['logical_ip']['server'],
                                                            config['logical_ip']['client']))
        log.info("platform==> server:{},client:{}".format(config['platform']['server'],
                                                          config['platform']['client']))
        log.info("serial_port_pos==> server:{},client:{}".format(config['serial_port_pos']['server'],
                                                                 config['serial_port_pos']['client']))
        log.info("relationships==> server:{},client:{}".format(config['relationships']['server'],
                                                               config['relationships']['client']))

        temp = config['nic_driver']['server']
        config['nic_driver']['server'] = config['nic_driver']['client']
        config['nic_driver']['client'] = temp

        temp = config['nic_os']['server']
        config['nic_os']['server'] = config['nic_os']['client']
        config['nic_os']['client'] = temp

        temp = config['logical_ip']['server']
        config['logical_ip']['server'] = config['logical_ip']['client']
        config['logical_ip']['client'] = temp

        temp = config['platform']['server']
        config['platform']['server'] = config['platform']['client']
        config['platform']['client'] = temp

        temp = config['serial_port_pos']['server']
        config['serial_port_pos']['server'] = config['serial_port_pos']['client']
        config['serial_port_pos']['client'] = temp

        temp = config['relationships']['server']
        config['relationships']['server'] = config['relationships']['client']
        config['relationships']['client'] = temp

        if 'nic_driver_rdma' in config:
            temp = config['nic_driver_rdma']['server']
            config['nic_driver_rdma']['server'] = config['nic_driver_rdma']['client']
            config['nic_driver_rdma']['client'] = temp

        if 'relationships_rdma' in config:
            temp = config['relationships_rdma']['server']
            config['relationships_rdma']['server'] = config['relationships_rdma']['client']
            config['relationships_rdma']['client'] = temp

        cls.server_logical_ip = config['logical_ip']['server']
        cls.client_logical_ip = config['logical_ip']['client']

        with open(constants.NIC_CONFIG_PATH, 'w+') as f:
            config.write(f)

        log.warning("reverse_test_direction ==> after:".format())
        log.info("nic_driver==> server:{},client:{}".format(config['nic_driver']['server'],
                                                            config['nic_driver']['client']))
        log.info("nic_os==> server:{},client:{}".format(config['nic_os']['server'], config['nic_os']['client']))
        log.info("logical_ip==> server:{},client:{}".format(config['logical_ip']['server'],
                                                            config['logical_ip']['client']))
        log.info("platform==> server:{},client:{}".format(config['platform']['server'],
                                                          config['platform']['client']))
        log.info("serial_port_pos==> server:{},client:{}".format(config['serial_port_pos']['server'],
                                                                 config['serial_port_pos']['client']))
        log.info("relationships==> server:{},client:{}".format(config['relationships']['server'],
                                                               config['relationships']['client']))
        if 'nic_driver_rdma' in config:
            log.info("nic_driver_rdma==> server:{},client:{}".format(config['nic_driver_rdma']['server'],
                                                                     config['nic_driver_rdma']['client']))
        if 'relationships_rdma' in config:
            log.info("relationships_rdma==> server:{},client:{}".format(config['relationships_rdma']['server'],
                                                                        config['relationships_rdma']['client']))

    @classmethod
    def __init(cls) -> None:
        """
        author:      xianda.liu
        date:        2022-07-22
        description: 初始化函数入口，其他初始化都可以放在该方法内
        :return:     None
        """
        # 初始化脚本log日志
        cls.__init_script_log()
        # 设置当前进程id
        cls.__script_pid = os.getpid()
        # 创建回传的pcap文件本地路径scripts/temp_files
        cls.__init_temp_directory()

    @classmethod
    def __check_physical_environment(cls) -> None:
        """
        author: xianda.liu
        date  : 2022-07-22
        descriptor: 准备脚本执行的物理环境
        :return: 无返回值
        """
        enable_flag = True
        check_start_time = time.time()

        # 更新配置文件
        cls.__update_env_config()
        if cls.test_direction_reverse:
            # junfeng.he 修改配置文件nic_driver_config.ini
            cls.__reverse_test_direction()

        # 检查文件根目录是否存在以及不存在时是否创建成功
        from scripts.script_libs.common_operation import CommonOperation
        nic_os_server, nic_os_client = CommonOperation.get_nic_os()
        renix_server_list, renix_locations_list = CommonOperation.get_renix()
        cls.server_serial_cli_exec_address, cls.client_serial_cli_exec_address = \
            CommonOperation.get_serial_port_pos()

        if CommandLineArgsParse.get_test_entry() in [TestEntryEnum.SINGLE_MODE.value, TestEntryEnum.UEFI_MODE.value]:
            log.warning("single_mode or uefi mode，不检查ps3server环境配置与测试机环境配置一致性")
        elif renix_server_list:
            log.warning("发包仪环境，不检查ps3server环境配置与测试机环境配置一致性")
        else:
            # 检查server ip和client ip
            if not cls.__check_ip():
                enable_flag = False

            if 'linux' == nic_os_client and 'linux' == nic_os_server:
                if not cls.__check_script_file():
                    log.info(f"检查{constants.FILE_PATH_ROOT}不存在，skip")
                    enable_flag = False
            # 检查配置文件ps3server ip与测试机ini文件中的是否一致
            server_ip = CommandLineArgsParse.get_server_ip()
            client_ip = CommandLineArgsParse.get_client_ip()
            cls.server_logical_ip, cls.client_logical_ip = CommonOperation.get_nic_logical_ip()
            if cls.test_direction_reverse:
                if cls.client_logical_ip != server_ip or cls.server_logical_ip != client_ip:
                    log.info('ps3server配置的主机ip[server:{},client:{}]与测试机配置的ip[server:{},client:{}]不一致'.
                             format(server_ip, client_ip, cls.client_logical_ip, cls.server_logical_ip))
                    enable_flag = False
            else:
                if cls.server_logical_ip != server_ip or cls.client_logical_ip != client_ip:
                    log.info('ps3server配置的主机ip[server:{},client:{}]与测试机配置的ip[server:{},client:{}]不一致'.
                             format(server_ip, client_ip, cls.server_logical_ip, cls.client_logical_ip))
                    enable_flag = False

        cls.__physical_environment_enabled = enable_flag
        if enable_flag:
            log.info('physical environment enabled')

        check_end_time = time.time()
        cls.__chk_physical_env_duration = check_end_time - check_start_time

    @classmethod
    def __set_result_info(cls, test_flag: bool = False, post_flag: bool = False) -> None:
        """
        author:      haibin.xu
        date:        2020-09-24 09:50:38
        description: 设置result信息
        :param test_flag: 配置prepare、do阶段报出的bug信息的标志位
        :param post_flag: 配置post阶段报出的bug信息的标志位
        :return      None
        """
        cls.__normal_result = {
            'object': cls.test_object,
            'module': cls.test_module,
            'tool': cls.test_tool,
            'precondition': cls.test_precondition,
            'steps': cls.test_steps,
        }
        # prepare、do阶段报出的bug信息，保存在__test_result中
        if test_flag and (not cls.__prepare_flag or not cls.__do_flag) and \
                (not cls.__exception_in_prepare_do_post_flag):
            cls.__test_result.update(cls.__normal_result)
            cls.__test_result.update({
                'title': cls.bug_title,
                'type': cls.__bug_type,
                'result': cls.bug_result,
                'expect': cls.bug_expect
            })
            # prepare、do阶段报出bug, __bug_in_prepare_do_flag置位True
            cls.__bug_in_prepare_do_flag = True
        # post阶段报出的bug信息，保存在__post_result中
        if post_flag and (not cls.__post_flag) and (not cls.__exception_in_prepare_do_post_flag):
            cls.__post_result.update(cls.__normal_result)
            cls.__post_result.update({
                'title': cls.bug_title,
                'type': cls.__bug_type,
                'result': cls.bug_result,
                'expect': cls.bug_expect
            })
            # post阶段报出bug, __bug_in_post_flag置位True
            cls.__bug_in_post_flag = True
        else:
            cls.__post_result = cls.__normal_result

    @classmethod
    def __output_console_info(cls) -> None:
        """
        author: zhilong.zhang
        date  : 2020.07.15
        descriptor: 打印控制台信息
        :return: 无返回值
        """

        """method_dict: 方法字典，包括的字段为准备环境时间，执行测试时间，清理环境时间"""
        method_dict = {
            # 准备时间包括三部分：prepare、自有环境检查时间、通用环境检查时间
            'pre_duration': cls.__prepare_duration + cls.__chk_own_env_duration + cls.__chk_physical_env_duration,
            'do_duration': cls.__do_duration,
            'post_duration': cls.__post_duration,
            'iops': cls.__iops,
            'bw': cls.__bw,
            'resp_time': cls.__resp_time,
            'raw_perf_data': cls.__raw_perf_data,
            'cli_result_max_time': cls.__script_cli_time
        }

        result_dict = {'test_result': cls.__test_result, 'post_result': cls.__post_result, 'methods': method_dict,
                       'stop_test': cls.__stop_test, 'skip_message': cls.skip_message}
        log.info('result_dict: {}'.format(result_dict))

    @classmethod
    def set_bug_type(cls, bug_type: str) -> None:
        """
        author:      haibin.xu,sunql
        date:        2020-08-19 09:51:55
        description: 设置bug type值，根据传入的bug_type参数，去判断该参数是否在BugTypeEnum枚举变量中，
                     在的话，返回该值，不在的话，取默认值 other
        :param bug_type: 传入的bug_type参数
        :return:     传入的bug_type在BugTypeEnum枚举变量中时，返回原值，不在的话，返回默认值 other
                @changelog      sunql
                1、增加判断是否出现了数据不一致bug，如果是有则停止后续测试
        """
        bug_type_list = [bt.value for bt in BugTypeEnum]
        if bug_type in bug_type_list:
            cls.__bug_type = bug_type
        else:
            log.error('Error set bug type, Please select its value from: {}'.format(bug_type_list))

    @classmethod
    def get_bug_data_with_create_bug(cls, abnormal_msg: str, bug_title: str, bug_result: str, bug_expect: str,
                                     bug_type: str) -> None:
        """
        author:      haibin.xu
        date:        2020-10-01 17:30:42
        description: 获取bug信息，并报bug异常，该函数内包含线程锁，主要为多线程使用，当然，单线程使用也没有问题

        :param bug_title: bug标题信息
        :param bug_result: bug结果信息
        :param bug_expect: 期望结果信息
        :param bug_type: bug类型
        :param abnormal_msg: 异常信息
        :return:
        """
        # 添加线程锁，这样在锁未释放的情况下，其他线程不会篡改bug信息
        cls.__thread_lock.acquire()
        cls.bug_title = bug_title
        cls.bug_result = bug_result
        cls.bug_expect = bug_expect
        cls.set_bug_type(bug_type)
        log.error_caller(abnormal_msg)
        cls.create_bug(abnormal_msg, log_print=False)
        cls.__thread_lock.release()

    @classmethod
    def create_bug(cls, abnormal_msg: str, log_print: bool = True) -> None:
        """
        author:     haibin.xu
        date:       2020.08.18
        descriptor: 打印异常log，抛出异常
        param abnormal_msg: 待要抛出的异常信息
        return:     无返回值
        """
        bug_type_list = [bt.value for bt in BugTypeEnum]
        if cls.__bug_type not in bug_type_list:
            log.error('Invalid bug_type value. Will not create bug. Please call function cls.set_bug_type() before '
                      'execute function create_bug')
        else:
            # 输出log
            if log_print:
                log.error_caller(abnormal_msg)
        bug_title = abnormal_msg[0:min(len(abnormal_msg), 200)]
        # 抛出异常
        raise SxeException(bug_title)

    @classmethod
    @abc.abstractmethod
    def set_parameters(cls) -> None:
        """
        author: panpan.du
        date  : 2020.06.28
        descriptor: 设置配置环境需要的参数
        """
        pass

    @classmethod
    @abc.abstractmethod
    def check_own_environment(cls) -> None:
        """
        author:      haibin.xu
        date:        2020-08-18 19:02:34
        description: 检测当前脚本运行所需要的局部环境是否具备，该方法只检测，不报bug，函数内需要设定类变量own_environment_enabled的值，
                     局部环境检测正常，类变量own_environment_enabled设置为True
        :return:     无返回值
        """
        pass

    @classmethod
    @abc.abstractmethod
    def prepare(cls) -> None:
        """
        author: panpan.du
        date  : 2020.06.28
        descriptor: 设置当前测试环境，准备Raid环境(设置控制器参数、组Raid等)
        """
        pass

    @classmethod
    @abc.abstractmethod
    def do(cls) -> None:
        """
        author: panpan.du
        date  : 2020.06.28
        descriptor: 执行测试
        :return: 无返回值
        """
        pass

    @classmethod
    def __non_blocking_bug_report(cls) -> None:
        """
        author: junfeng.he
        date  : 2024.05.15
        descriptor: 将记录的非阻塞式BUG抛出
        :return: 无返回值
        """
        desc = ""
        for k, v in cls.non_blocking_bug_dict.items():
            desc += "BUG-{}=>{};".format(k, v)
        if desc:
            cls.create_bug(desc)

    @classmethod
    @abc.abstractmethod
    def post(cls) -> None:
        """
        author: panpan.du
        date  : 2020.06.28
        descriptor: 整理环境
        :return: 无返回值
        """
        pass

    @classmethod
    def __run_check_own_environment(cls) -> None:
        """
        author:      haibin.xu
        date:        2020-08-18 19:19:08
        description: 封装类方法check_own_environment
        :return:     无返回值
        """
        try:
            check_start_time = time.time()
            cls.check_own_environment()
            check_end_time = time.time()
            cls.__chk_own_env_duration = check_end_time - check_start_time
        except Exception as e:
            # 打印调用栈信息
            log.exception(str(e))
            cls.__exception_in_prepare_do_post_flag = True

    @classmethod
    def __run_prepare(cls) -> None:
        """
        author:     haibin.xu
        date:       2020.07.21
        descriptor: 封装类方法prepare
        return:     无返回值
        """
        try:
            prepare_start_time = time.time()
            cls.prepare()
            prepare_end_time = time.time()
            cls.__prepare_duration = prepare_end_time - prepare_start_time
            cls.__prepare_flag = True
        except SxeException as e:
            log.error(str(e))
            # 将bug标志位置为True
            cls.__bug_in_prepare_do_flag = True

        except Exception as e:
            # 打印调用栈信息
            log.exception(str(e))
            cls.__exception_in_prepare_do_post_flag = True

    @classmethod
    def __run_do(cls) -> None:
        """
        author:     haibin.xu
        date:       2020.07.21
        descriptor: 封装类方法do
        return:     无返回值
        """
        try:
            do_start_time = time.time()

            cls.do()
            cls.__non_blocking_bug_report()
            do_end_time = time.time()
            cls.__do_duration = do_end_time - do_start_time
            cls.__do_flag = True
        except SxeException as e:
            log.error(str(e))
            # 将bug标志位置为True
            cls.__bug_in_prepare_do_flag = True
        except Exception as e:
            log.error(str(e))
            # 打印调用栈信息
            traceback.print_exc()
            cls.__exception_in_prepare_do_post_flag = True

    @classmethod
    def __run_post(cls) -> None:
        """
        author:     xianda.liu
        date:       2022-07-22
        descriptor: 封装类方法post
        return:     无返回值
        """
        try:
            post_start_time = time.time()
            if (not CommandLineArgsParse.get_bug_stop_flag()) or (not cls.__bug_in_prepare_do_flag):
                # 没有设置bug stop开关，或者prepare、do阶段没有报bug，都会执行post操作
                time.sleep(cls.__wait_time_before_clear_env)
                # 数据不一致bug不执行清理动作
                if cls.__bug_type != BugTypeEnum.CC_ERROR.value:
                    cls.post()
                else:
                    log.info(f"bug type is {BugTypeEnum.CC_ERROR.value}, do post skip")

            post_end_time = time.time()
            cls.__post_duration = post_end_time - post_start_time
            cls.__post_flag = True
        except SxeException as e:
            log.error(str(e))
        except Exception as e:
            log.error(str(e))
            # 打印调用栈信息
            traceback.print_exc()
            cls.__exception_in_prepare_do_post_flag = True
            # 通用的清理环境
            time.sleep(cls.__wait_time_before_clear_env)
            if not CommandLineArgsParse.get_is_long_stability():
                cls.__clean_up_environment()
        # 回收告警信息
        cls.skip_message = cls.__get_warn_message()

    @classmethod
    def __get_warn_message(cls) -> str:
        """
        author: junfeng.he
        date: 2026.02.12
        description: 获取要告警的信息
        """
        warn_message = {}
        log_default_path = os.path.join(ESAT_DIRECTORY, constants.LOG_DEFAULT_PATH_NAME)
        exec_command = f"cat {log_default_path}/warn_message"
        rtn_code, result = subprocess.getstatusoutput(exec_command)
        if rtn_code == RtnStatusEnum.SUCCESS.value and len(result):
            log.info(f'__get_warn_message:{result}')
            warn_message = result
            exec_command = f"echo '' > {log_default_path}/warn_message"
            rtn_code, result = subprocess.getstatusoutput(exec_command)
        return warn_message

    @classmethod
    def __clean_up_environment(cls) -> None:
        """
        author: zhilong.zhang
        date: 2020.11.24
        description: 当有遗留的vd未清理或jbod盘未切换为ready状态时，调用此方法环境清理
        :return: 无返回值
        - liuxd 暂时未想到需要清理那些配置，例如卸载网卡驱动，再加载？
        """
        log.info('Now clean up environment.')

        pass

        log.info('Finish clean up environment!')

    @classmethod
    def run(cls) -> None:
        """
        author: xianda.liu
        date  : 2022-07-22
        descriptor: 运行、组织脚本执行步骤，供子类在main方法中调用
        :return: 无返回值
        """
        # 初始化
        cls.__init()
        # 设置参数
        cls.set_parameters()
        # 检查物理环境
        cls.__check_physical_environment()
        if cls.__physical_environment_enabled:
            # 只在物理环境检查通过后，才进行局部环境检查
            cls.__run_check_own_environment()
        if cls.own_environment_enabled:
            # 局部环境检查通过的情况下，物理环境检查肯定也是通过的，所以此处只需判定局部环境检查即可
            # raid环境准备
            cls.__run_prepare()
            if cls.__prepare_flag:
                # 执行测试
                cls.__run_do()
            # 设置prepare、do阶段的 result 信息
            cls.__set_result_info(test_flag=True)
            # 整理环境，删除raid
            cls.__run_post()
            # 设置post阶段的 result 信息
            cls.__set_result_info(post_flag=True)
            # 获取脚本cli命令最大执行时间及level，- liuxd 暂时屏蔽
            # cls.__get_script_cli_time()
        # 恢复初始值
        # 物理环境与局部环境任意一个不具备时，程序跳出
        if not all([cls.__physical_environment_enabled, cls.own_environment_enabled]):
            cls.__output_console_info()
            log.warning("环境检查不通过，skip")
            exit(ExitCodeEnum.EXIT_SKIP.value)
        # prepare、do、post操作阶段有报bug时，打印bug信息并报错退出script_base_rdma_rcms_check
        if cls.__bug_in_prepare_do_flag or cls.__bug_in_post_flag:
            cls.__output_console_info()
            exit(ExitCodeEnum.EXIT_FAIL.value)
        # prepare、do、post操作阶段有代码执行异常报错时，打印信息并报错退出, 异常报错放在报bug之后判断，即如果有bug生成，则先报bug
        if cls.__exception_in_prepare_do_post_flag:
            cls.__output_console_info()
            exit(ExitCodeEnum.EXIT_EXCEPT.value)
        # 最后成功执行，打印正常log信息，并正常退出
        cls.__output_console_info()
        exit(ExitCodeEnum.EXIT_NORMAL.value)

    @classmethod
    def init(cls) -> None:
        """
        author:      chenmh1
        date:        2022.03.25
        description: init公共接口
        :return:     None
        """
        return cls.__init()

    @classmethod
    def run_check_own_environment(cls) -> None:
        """
        author:      chenmh1
        date:        2022.03.25
        description: run_check_own_environment公共接口
        :return:     None
        """
        return cls.__run_check_own_environment()

    @classmethod
    def run_prepare(cls) -> None:
        """
        author:      chenmh1
        date:        2022.03.25
        description: run_prepare公共接口
        :return:     None
        """
        return cls.__run_prepare()

    @classmethod
    def get_prepare_flag(cls) -> bool:
        """
        author:      chenmh1
        date:        2022.03.25
        description: prepare_flag公共接口
        :return:     None
        """
        return cls.__prepare_flag

    @classmethod
    def run_do(cls) -> None:
        """
        author:      chenmh1
        date:        2022.03.25
        description: run_do公共接口
        :return:     None
        """
        return cls.__run_do()

    @classmethod
    def set_result_info(cls, test_flag: bool = False, post_flag: bool = False) -> None:
        """
        author:      chenmh1
        date:        2022.03.25
        description: set_result_info公共接口
        :return:     None
        """
        return cls.__set_result_info(test_flag=test_flag, post_flag=post_flag)

    @classmethod
    def run_post(cls) -> None:
        """
        author:      chenmh1
        date:        2022.03.25
        description: run_post公共接口
        :return:     None
        """
        return cls.__run_post()

    @classmethod
    def get_physical_environment_enabled(cls) -> bool:
        """
        author:      chenmh1
        date:        2022.03.25
        description: physical_environment_enabled公共接口
        :return:     None
        """
        return cls.__physical_environment_enabled

    @classmethod
    def output_console_info(cls) -> None:
        """
        author:      chenmh1
        date:        2022.03.25
        description: output_console_info公共接口
        :return:     None
        """
        return cls.__output_console_info()

    @classmethod
    def get_bug_in_prepare_do_flag(cls) -> bool:
        """
        author:      chenmh1
        date:        2022.03.25
        description: bug_in_prepare_do_flag公共接口
        :return:     None
        """
        return cls.__bug_in_prepare_do_flag

    @classmethod
    def get_bug_in_post_flag(cls) -> bool:
        """
        author:      chenmh1
        date:        2022.03.25
        description: bug_in_post_flag公共接口
        :return:     None
        """
        return cls.__bug_in_post_flag

    @classmethod
    def get_exception_in_prepare_do_post_flag(cls) -> bool:
        """
        author:      chenmh1
        date:        2022.03.25
        description: exception_in_prepare_do_post_flag公共接口
        :return:     None
        """
        return cls.__exception_in_prepare_do_post_flag
