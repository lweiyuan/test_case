#!/usr/bin/python3
# -*- encoding=utf8 -*-
"""
author: luyafei
date  : 2020.04.21
description: PS3测试框架的入口脚本
    入口脚本的功能：
        1：准备测试环境
        2：组织脚本测试
        3：处理测试结果

@changelog      2021-02-03 14:49:50  haibin.xu
                1. framework交接给haibin.xu，并展开逐步优化
                2021-02-27 10:19:37  haibin.xu
                1. 定义RunAllTestPs3类，将原有函数全部封装为RunAllTestPs3类类方法，
                   将原有全局变量全部封装为RunAllTestPs3类类变量
                2021-8-19           sunql
                1、增加长稳测试类变量 long_stab_test 及长稳测试相关逻辑
                2022-06-06 15:16:45  haibin.xu
                1. 优化函数实现, 添加类变量current_test_rounds_index，即当前是第几轮测试
"""
import os
import re
import time
import json
import copy
import multiprocessing
import ctypes
import random
import add_syspath
from datetime import datetime, timedelta
from framework.biz.log_collect import LogCollect
from framework.biz.classes.case_script_map import CaseScriptMap
from framework.biz.excel import bug_result_excel_handle, report_excel_create
from framework.libs.classes.bug import Bug
from framework.libs import commands, constants, utils, ssh_utils, utils_excel
from framework.simulation.host_ioc_start import HostIocStart
from framework.simulation.exp_simu_open import ExpanderSimuStart
from framework.simulation.sw_simu_open import PcieSwitchSimuStart
from framework.simulation.real_host_start import RealHostStart
from framework.simulation.real_exp_start import RealExpanderStart
from scripts.script_libs.env_platform_operation import EnvPlatFormOperation
from scripts.script_libs import log
from scripts.script_libs import constants as libs_constants
from scripts.script_libs.host_operation import HostOperation
from scripts.script_libs.expander_operation import ExpanderOperation
from scripts.script_libs.custom_operation import CustomOperation
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.virtual_disk import VirtualDisk
from scripts.script_libs.controller_operation import ControllerOperation
from scripts.script_libs.enums import RtnStatusEnum, TestObjectEnum, HostCpuEnum, TestObjectStrEnum, \
    TestEntryStrEnum, CompileObjectStrEnum, TestPlatformEnum, CaseOrderEnum
from scripts.script_libs.file_operation import FileOperation
from scripts.script_libs.bmc_operation import BmcOperation
from scripts.script_libs.raid_scoket_operation import RaidSocketOption
from framework.biz.log_analysis import LogAnalysis
from scripts.script_libs.exam_2021.topo_manager import TopoManager
from scripts.script_libs import global_var


# 定义RunAllTestPs3类，封装相关方法
class RunAllTestPs3(object):
    # 定义日志收集对象
    collect_log = None
    # 定义用例关联对象
    case_script_dict = None
    # 定义配置信息变量
    config_dict = None
    # 定义日志服务器、测试主机、PS3测试服务器的ip
    ip_dict = None
    # 代码覆盖率标志位
    gcov_flag = None
    # 测试bug列表excel文件路径
    test_bug_excel_file_path = None
    # 测试result列表excel文件路径
    test_result_excel_file_path = None
    # 测试结果中report_log路径
    test_report_log_file_path = None
    # 测试报告excel文件名称及路径
    test_report_excel_file_path = None
    # run all test的日志文件名称及路径
    run_all_test_log_file = None
    # 测试脚本的日志文件目录
    test_script_log_directory = None
    # 记录是否存在bug
    g_bug_existed = False

    bug_existed_flag = False
    # 脚本测试通过数
    pass_num = 0
    # 脚本测试失败数
    fail_num = 0
    # 脚本测试跳过数
    skip_num = 0
    # 脚本不存在数
    not_exist_num = 0
    # 脚本发生异常数
    except_num = 0
    # 脚本超时数
    timeout_num = 0
    # jenkins ps3_**_prepare job id
    job_id = None
    # jenkins ps3_**_prepare job name
    job_name = None
    # outputs/framework下当前测试脚本结果保存的目录名，如：ps3_auto_test_prepare_14093_20210610175943
    job_directory_name = None
    # outputs/framework下当前测试脚本结果保存的目录绝对路径，如：/home/test/ps3test/vms/vm204/ps3/test/esat/outputs/
    # framework/ps3_auto_test_prepare_14093_20210610175943
    job_directory_path = None
    # ioc进程下所有线程数据文件路径
    thread_data_path = None
    # ioc qemu server下meminfo 文件路径
    ioc_qemu_meminfo_path = None
    ioc_vmstat_path = None
    ioc_iostat_path = None
    ioc_qemu_iostat_path = None
    # 保存解析测试单excel或csv文件的数据
    script_case_dict = None
    # 本次测试日志保存在日志服务器上的路径，如：/home/framework/log/host_vm670_10.22.81.1_22/2021_06_11/16_03_12
    log_server_path = None
    # 测试轮次
    test_rounds = None
    # bug_stop 开关
    bug_stop = None
    # host宿主机ip
    host_ip = None
    # host宿主机端口
    host_port = None
    # host节点ip
    host_qemu_ip = None
    # ioc宿主机ip
    ioc_ip = None
    # ioc端口
    ioc_port = None
    # ioc节点ip
    ioc_qemu_ip = None
    # ioc节点ioc进程pid
    ioc_pid = None
    # 测试入口
    test_entry = None
    test_function = None
    # 测试对象
    test_object = None
    package_install = None
    # 测试平台
    test_platform = None
    # 编译对象
    compile_object = None
    # script_libs 下测试对象
    libs_test_object = None
    # bug对象，用于bug信息收集
    bug_object = None
    # cpu 架构
    host_cpu = None
    # pcie_switch 测试标志位
    pcie_switch_flag = False
    # expander 测试标志位
    expander_flag = False
    # host_config.xlsx配置文件中exp_port
    expander_port = False
    # 版本部署ip, port
    cli_deploy_ip = None
    cli_deploy_port = 22
    # 自动加盘标志位
    auto_add_disk_flag = None
    # 监听进程
    monitor_process = None
    # 测试开始时间戳
    test_start_timestamp = None
    # 测试开始时间,格式为20200423151820
    test_start_time = None
    # 整个测试耗时时长，单位为妙
    test_total_seconds = None
    # test/esat/scripts目录
    scripts_directory = None
    # host, ioc节点名称, id
    host_node_name = None
    ioc_node_name = None
    ioc_node_id = None
    # 上次检查时间
    last_check_time = None
    # 相关进程列表
    process_list = ['logFlushThread', 'sched_', 'sched_wdog', 'MPC_ASYNC_THD', 'MPC_SYNC_SHORT', 'MPC_SYNC_LONG',
                    'MPC_MONITOR_THD', 'ps3Timer', 'diskFaultTimer', 'simImgCb', 'simPalReq', 'simDiskThd',
                    'replyCombThd', 'ioc', 'upLinkDmaWrThd', 'upLinkDmaRdThd', 'downLinkDmaWrThd',
                    'downLinkDmaRdThd', 'apuDmaWrThd', 'apuDmaRdThd', 'CRON_H', 'CRON_L', 'NS_TCPSONAR',
                    'NT_CHKCONN', 'NT_TCPEP', 'NP_TMRRECONN', 'NP_TMRNRQ', 'NP_MONITOR', 'NP_THDPOOL']

    # expander env id值
    expander_env_id = None
    # 是否长稳测试
    long_stab_test = False
    # 是否打开 log trace
    log_trace = False
    # 是否打开 host trace
    host_trace = False
    case_list_order = CaseOrderEnum.DEFAULT_ORDER.value
    # 是否打开fio延时日志监控
    fio_cmd_lat = False
    # 断流监控
    cut_off = 10
    # 软硬复位测试
    driver_reset = 'default'
    driver_reset_time = 300
    # 跳过 host ioc start
    skip_qemu_start = False
    # expander
    expander_devsn = None
    # 内存溢出监控
    memory_leak = False
    # 脚本结束后内存监控
    ioc_memory_leak = False
    # 忽略盘类型
    ignore_disk = False
    # sanBlaze ip
    san_blaze_ip = None
    # mpduip
    mpduip = None
    # 卡下系统盘vd id
    os_vd_id = 0
    # 卡下系统盘slot id
    os_slot_id = ''
    # 串口服务器ip
    comhost_ip = None
    # a72串口文件名
    a72_com = None
    # 重启标志位
    host_ioc_reset = False
    # host os
    host_os = None
    # cli 版本
    cli_mode = None
    cli_version = None
    cli_commit_id = None
    cli_branch = None

    # 定义日志分析对象
    log_analysis = None
    # vd 队列深度
    vd_queue_depth = None
    # 数据一致性错误时是否停止测试
    cc_error_stop = True
    # 2021年底考试
    exam_2021 = False
    # 2021年底考试长稳
    exam_long_stab_test_2021 = False
    # 当前测试轮数索引，即当前是第几轮测试
    current_test_rounds_index = 0
    log_server_account = None
    log_server_ip = None
    test_server_log_back_path = None
    # iostat进程
    iostat_proc = None
    # 移动日志进程
    mv_log_proc = None
    # 定时复位进程
    reset_proc = None
    # 断流检测输出
    iostat_analysis = multiprocessing.Manager().Value(ctypes.c_char_p, '')
    # 断流检测开始时间戳
    iostat_time = multiprocessing.Manager().Value(ctypes.c_char_p, '')
    # 断流检测日志路径
    iostat_log_full_path = multiprocessing.Manager().Value(ctypes.c_char_p, '')
    # 测试环境信息
    test_platform_info = ''
    # 测试环境(附加expander)信息
    test_platform_add_exp_info = {}
    # expander generation
    expander_generation = None
    # 断流检测方式 0：原方式 1：海康方式
    way_of_iostat = 1
    # 满盘检测文件行数
    slow_disk_conf_lines = 0
    # 海康os慢盘服务是否存在
    hikos_disk_service = False
    # 中层io监控进程
    middle_layer_proc = None
    # 兼容性测试
    compatibility_test = False
    # 清理测试环境日志
    clear_log = True
    # expander所在的控制器id
    exp_ctrl_id = 0
    # 框架暂存core 路径
    raid_core_list = []
    # ps3+expander测试标志位
    ps3_exp_test_flag = False
    # 本次job执行用于回传禅道的关键信息
    jenkins_job_info = {}

    is_perf = False

    @classmethod
    def __get_collect_log_obj(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-02-26 16:36:27
        description: 获取LogCollect类实例
        :return:     None
        """
        cls.collect_log = LogCollect()

    @classmethod
    def __get_case_script_map_obj(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-02-26 16:39:06
        description: 获取CaseScriptMap类实例

        :return:     None
        """
        cls.case_script_dict = CaseScriptMap()

    @classmethod
    def __get_env_configure_data(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-02-26 16:41:59
        description: 获取测试需要的环境配置信息及日志服务器、测试主机、PS3测试服务器的ip

        :return:     None
        """
        cls.config_dict, cls.ip_dict = utils.get_conf()

    @classmethod
    def __drop_caches(cls) -> None:
        """
        author:      sunql
        date:        2022-01-06 13:39:34
        description: 清理缓存操作,解决模拟平台宿主机缓存过大，刷写缓慢引起的io性能下降问题。 需求提出人：吴庆民

        :return:     None
        """
        if cls.test_platform == TestPlatformEnum.REAL_PLATFORM.value:
            return
        drop_caches_cmd = 'echo 3 > /proc/sys/vm/drop_caches'
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=drop_caches_cmd, ssh_ip=cls.ioc_ip, ssh_port='22', print_enable=True)
        rtn_code = CommandOperation.check_cli_output(drop_caches_cmd, cmd_code, cmd_stdout, cmd_stderr)
        if RtnStatusEnum.SUCCESS.value == rtn_code:
            log.info('Success to clean buf/cache.')

    @classmethod
    def __cat_vmstat(cls) -> str:
        """
        author:      sunql
        date:        2022-01-06 13:39:34
        description: 获取 ioc vmstat 需求提出人：吴庆民

        :return:     str
        """
        rtn_info = ''
        cmd = 'cat /proc/vmstat | egrep "dirty|writeback"'
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, ssh_ip=cls.ioc_ip, ssh_port='22', print_enable=False)
        rtn_code = CommandOperation.check_cli_output(cmd, cmd_code, cmd_stdout, cmd_stderr,
                                                     print_enable=False)
        if RtnStatusEnum.SUCCESS.value == rtn_code:
            rtn_info = cmd_stdout
        return rtn_info

    @classmethod
    def __ioc_iostat(cls) -> str:
        """
        author:      sunql
        date:        2022-02-06 13:39:34
        description: 获取 ioc iostat，需求提出人：吴庆民

        :return:     str
        """
        rtn_info = ''
        cmd = 'iostat -xhd'
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, ssh_ip=cls.ioc_ip, ssh_port='22', print_enable=False)
        rtn_code = CommandOperation.check_cli_output(cmd, cmd_code, cmd_stdout, cmd_stderr,
                                                     print_enable=False)
        if RtnStatusEnum.SUCCESS.value == rtn_code:
            rtn_info = cmd_stdout
        return rtn_info

    @classmethod
    def __ioc_qemu_iostat(cls) -> str:
        """
        author:      sunql
        date:        2022-02-06 13:39:34
        description: 获取 ioc qemu iostat，需求提出人：吴庆民

        :return:     str
        """
        rtn_info = ''
        cmd = 'iostat -xhd'
        cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, ssh_ip=cls.ioc_qemu_ip, ssh_port='22', print_enable=False)
        rtn_code = CommandOperation.check_cli_output(cmd, cmd_code, cmd_stdout, cmd_stderr,
                                                     print_enable=False)
        if RtnStatusEnum.SUCCESS.value == rtn_code:
            rtn_info = cmd_stdout
        return rtn_info

    @classmethod
    def fio_reset(cls):
        """
        有fio进程时定时软、硬重启
        :return:
        """
        while True:
            if cls.driver_reset == 'hard_reset':
                ControllerOperation.hard_reset(libs_constants.X16_CONTROLLER)
            if cls.driver_reset == 'soft_reset':
                ControllerOperation.soft_reset(libs_constants.X16_CONTROLLER)
            time.sleep(cls.driver_reset_time)

    @classmethod
    def __chmod_env_conf(cls):
        """
        修改envconf下所有文件权限 为 777，用于适配外网测试时权限问题
        :return:
        """
        cmd = f"chmod -R 777 {constants.ENV_CONF_DIRECTORY}"
        CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd, local_execute_flag=True,
                                                                     print_enable=True)

    @classmethod
    def __get_ioc_pid(cls, force: bool = False) -> None:
        """
        author:      haibin.xu
        date:        2021-06-15 15:22:03
        description: 获取ioc节点server下ioc进程pid

        :param force: 是否要重新获取ioc pid
        :return:     None
        """
        if cls.test_object == constants.ENV_TEST_OBJECT_EXPANDER or \
                cls.test_object == constants.ENV_TEST_OBJECT_PCIE_SWITCH:
            log.warning("==> test_object is expander or pcieswitc，can't get ioc PID.")
            return

        if (cls.ioc_pid is None) or force:
            # cls.ioc_pid为None时，或者force为True时，获取cls.ioc_pid
            cls.ioc_pid = CommandOperation.get_process_id(process_name=constants.IOC_PROCESS_NAME,
                                                          ssh_ip=cls.ioc_qemu_ip, ssh_port=cls.ioc_port)
            if cls.ioc_pid is None:
                log.error('Fail to get ioc PID.')

    @classmethod
    def __get_log_analysis_obj(cls) -> None:
        """
        author:      kaifeng.bi
        date:        2021-11-15 16:36:27
        description: 获取LogAnalysis类实例
        :return:     None
        """
        cls.log_analysis = LogAnalysis()
        if cls.way_of_iostat == 1:
            cmd = r"ps -ef | grep get_slow_disk | grep -v grep | awk '{print $2}' | head -n1"
            _, stdout, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, ssh_ip=cls.host_ip, ssh_port='22', print_enable=False)
            if len(stdout):
                cls.hikos_disk_service = True

    @classmethod
    def iostat_process(cls, iostat_analysis: str = None, iostat_log_full_path: str = None, iostat_time: str = None):
        """
        author:      kaifeng.bi
        date:        2022-06-09 11:42:27
        description: 有fio或vdbench进行iostat断流检测
        :return:     None
        """
        iostat_lun_name_tmp = ''
        global_var.iostat_lun_name = ""
        wait_stable_time = 0
        write_code = FileOperation.write_file(libs_constants.IOSTAT_LUN_NAME_FILE,
                                              global_var.iostat_lun_name)
        if RtnStatusEnum.SUCCESS.value != write_code:
            log.error('Failed to write iostat_lun_name: {}.'.format(global_var.iostat_lun_name))

        def iostat():
            nonlocal iostat_lun_name_tmp
            nonlocal wait_stable_time
            threshold = 20
            cmd = r"ps -ef | grep fio | grep -v grep | awk '{print $2}' | head -n1"
            _, fio_stdout, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, ssh_ip=cls.host_ip, ssh_port='22', print_enable=False)
            # log.info(fio_stdout)

            cmd = r"ps -ef | grep vdbench | grep -v grep | awk '{print $2}' | head -n1"
            _, vdbench_stdout, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, ssh_ip=cls.host_ip, ssh_port='22', print_enable=False)
            # log.info(vdbench_stdout)
            read_out = FileOperation.read_file(libs_constants.IOSTAT_LUN_NAME_FILE,
                                               print_enable=False)
            if global_var.iostat_lun_name != read_out:
                wait_stable_time = 0
                global_var.iostat_lun_name = read_out
            # print('iostat线程获取到的：%s' % global_var.iostat_lun_name)
            if not len(vdbench_stdout) and not len(fio_stdout):
                # log.info("not found fio/vdbench proc")
                cmd = r"ps -ef | grep iostat | grep -v grep | awk '{print $2}' | head -n1"
                _, iostat_stdout, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, ssh_ip=cls.host_ip, ssh_port='22', print_enable=False)
                # log.info(iostat_stdout)

                if iostat_stdout:
                    cmd = f"kill -9 {iostat_stdout}"
                    _, _, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=cmd, ssh_ip=cls.host_ip, ssh_port='22')
                    cmd = "sed -i '{},$d' {}".format((len(iostat_lun_name_tmp.strip().split(' ')) + 6) *
                                                     int(threshold / cls.cut_off) + 1,
                                                     iostat_log_full_path.value)
                    _, iostat_log_stdout, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=cmd, ssh_ip=cls.host_ip, ssh_port='22', print_enable=True)
                    # rtn_code = FileOperation.write_file(iostat_log_full_path.value,
                    #                                     iostat_log_stdout, print_enable=False)
                    # if RtnStatusEnum.SUCCESS.value != rtn_code:
                    #     log.error('Failed to write iostat_log_file: {}.'.format(iostat_log_stdout))
                    iostat_analysis.value = LogAnalysis().iostat_analysis()
                    if not iostat_analysis.value:
                        iostat_time.value = ''

                iostat_lun_name_tmp = ''
                # print('iostat线程清空盘符')
                if global_var.iostat_lun_name:
                    global_var.iostat_lun_name = ""
                    rtn_code = FileOperation.write_file(libs_constants.IOSTAT_LUN_NAME_FILE,
                                                        global_var.iostat_lun_name)
                    if RtnStatusEnum.SUCCESS.value != rtn_code:
                        log.error('Failed to write iostat_lun_name: {}.'.format(global_var.iostat_lun_name))
                return
            # print('iostat线程备份的：%s' % global_var.iostat_lun_name)
            if iostat_lun_name_tmp != global_var.iostat_lun_name:
                cmd = r"ps -ef | grep iostat | grep -v grep | awk '{print $2}' | head -n1"
                _, iostat_stdout, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=cmd, ssh_ip=cls.host_ip, ssh_port='22', print_enable=False)
                # log.info(iostat_stdout)

                if iostat_stdout:
                    cmd = f"kill -9 {iostat_stdout}"
                    _, _, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=cmd, ssh_ip=cls.host_ip, ssh_port='22', print_enable=False)
                    cmd = "sed -i '{},$d' {}".format((len(iostat_lun_name_tmp.strip().split(' ')) + 6) *
                                                     int(threshold / cls.cut_off) + 1,
                                                     iostat_log_full_path.value)
                    _, iostat_log_stdout, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd=cmd, ssh_ip=cls.host_ip, ssh_port='22', print_enable=True)
                    # rtn_code = FileOperation.write_file(iostat_log_full_path.value,
                    #                                     iostat_log_stdout, print_enable=False)
                    # if RtnStatusEnum.SUCCESS.value != rtn_code:
                    #     log.error('Failed to write iostat_log_file: {}.'.format(iostat_log_stdout))

                if global_var.iostat_lun_name:
                    if not iostat_time.value:
                        _, iostat_time.value = CommandOperation.get_time()
                    wait_stable_time += int(cls.cut_off)
                    if len(vdbench_stdout):
                        threshold = 60
                    if wait_stable_time >= threshold or len(global_var.iostat_lun_name) < len(iostat_lun_name_tmp):
                        LogAnalysis.IOSTAT_LOG_FILENAME = 'iostat_' + iostat_time.value + '.log'
                        iostat_log_full_path.value = os.path.join(libs_constants.FILE_PATH_ROOT,
                                                                  LogAnalysis.IOSTAT_LOG_FILENAME)
                        cmd = \
                            f"nohup iostat {global_var.iostat_lun_name} {cls.cut_off} -t >> " \
                            f"{iostat_log_full_path.value} 2>&1 &"
                        _, _, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                            cmd=cmd, ssh_ip=cls.host_ip, ssh_port='22')
                        iostat_lun_name_tmp = global_var.iostat_lun_name
                        wait_stable_time = 0
                else:
                    iostat_lun_name_tmp = global_var.iostat_lun_name

        while True:
            iostat()
            time.sleep(cls.cut_off)

    @classmethod
    def iostat_process_hikos(cls):
        """
        author:      kaifeng.bi
        date:        2022-11-02
        description: 通过海康方式进行满盘检测
        :return:     None
        """
        LogAnalysis().get_slow_disk()

    @classmethod
    def scsi_middle_layer_process(cls):
        """
        author:      kaifeng.bi
        date:        2022-11-09
        description: 监控中层io状态
        :return:     None
        """
        LogAnalysis().watch_scsi_middle_layer()

    @classmethod
    def mv_test_server_log(cls):
        """
        定时移动测试机中日志进程
        author: sunql
        :return:
        """

        if not cls.host_trace and not cls.exam_long_stab_test_2021 and \
                not HostOperation.check_hba_rpm_install(ssh_ip=cls.host_ip):
            return

        if cls.test_object in [constants.TEST_OBJECT_EXPANDER, constants.TEST_OBJECT_PCIE_SWITCH] or \
                cls.test_entry == TestEntryStrEnum.UEFI.value or constants.ENV_PLATFORM_SIMU == cls.test_platform:
            return

        now = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
        cls.test_server_log_back_path = f"/home/framework/run_log/{cls.host_ip}/{now}"

        rtn = FileOperation.make_directory(dir_name=cls.test_server_log_back_path, ip=cls.log_server_ip,
                                           username=constants.ENV_LOG_SERVER_ACCOUNT_FRAMEWORK,
                                           delete_flag=False, match_flag=False)
        if rtn != RtnStatusEnum.SUCCESS.value:
            exit(0)
            log.error("make test server log bak dir exec fail , test is stop ...")

        cls.mv_log_proc = multiprocessing.Process(target=cls.mv_log_process)
        cls.mv_log_proc.daemon = True
        cls.mv_log_proc.start()

    @classmethod
    def mv_log_process(cls):
        """
        定时移动测试机驱动日志
        :return:
        """

        def get_files(find_cmd, log_path):
            try:
                rtn_code, drv_files = FileOperation.get_files_with_cmd(find_files_cmd=find_cmd, ip=cls.host_ip,
                                                                       print_enable=False)
            except Exception as e:
                rtn_code, drv_files = RtnStatusEnum.FAIL.value, []

            for i in range(len(drv_files)):
                drv_files[i] = f"{log_path}/{drv_files[i]}"

            return drv_files

        def scp_and_del_file(source, target):

            rtn_code, _ = FileOperation.path_exists(path=source, ip=cls.host_ip,
                                                    username='root', print_enable=False)
            if rtn_code != RtnStatusEnum.SUCCESS.value:
                log.debug(f"{source} not found.")
                return rtn_code

            rtn_code = FileOperation.target_scp_file(source_file_path=source, source_ip=cls.host_ip, source_port=22,
                                                     target_file_path=target, target_ip=cls.log_server_ip,
                                                     target_port=22,
                                                     print_enable=False)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                rtn_code, _ = FileOperation.delete_file(path=source, ip=cls.host_ip,
                                                        username='root', match_flag=False, print_enable=False)

            return rtn_code

        def mv_log():
            log.debug(f'mv test server log start , log path: {cls.test_server_log_back_path}')

            log_path_list = ['/var/log', '/var/log/drvlog']

            # 如果对ps3 conf 做了配置，那么日志路径从ps conf 中获取
            ps3_conf_log_path = HostOperation.get_log_path(cls.host_ip, cls.host_port)
            if ps3_conf_log_path and '/var/log' in ps3_conf_log_path:
                log_path_list = [ps3_conf_log_path]

            log_file_list = [
                "ls -t {} | grep ps3sas_drv.log | sed -n '12,$p'",
                "ls -t {} | grep ps3sas_drv.bin | sed -n '12,$p'",
                "ls -t {} | grep fwlog | sed -n '200,$p'",
            ]
            # 获取所有需要移除的文件
            log_files_all = []
            for log_file_cmd in log_file_list:
                for log_path in log_path_list:
                    find_cmd = log_file_cmd.format(log_path)
                    log_files = get_files(find_cmd, log_path)
                    log_files_all.extend(log_files)

            for log_file in log_files_all:
                scp_and_del_file(log_file, cls.test_server_log_back_path)

        while True:
            mv_log()
            time.sleep(120)

    @classmethod
    def simulator_node_close(cls) -> None:
        """
        author: panapn.du
        date  : 2020.10.22
        description: 执行关闭节点
        :return: 无返回值

        @changelog      2021-02-27 09:53:42  haibin.xu
                        1. 作为类方法并入RunAllTestPs3类
        """
        if constants.ENV_PLATFORM_SIMU == cls.test_platform:
            script_path = constants.HOST_IOC_CLOSE_FILE_PATH
            if (constants.ENV_TEST_ENTRY_IOC == cls.test_entry) and (
                    cls.test_object == constants.ENV_TEST_OBJECT_EXPANDER):
                script_path = constants.EXPANDER_CLOSE_FILE_PATH
            log.info("Simulator is closing...")
            result = utils.simulator_operate(script_path, cls.host_qemu_ip, cls.host_port)
            if result:
                log.error("Simulator close fail")
                log.error(result)
                exit(0)
            else:
                log.info("Simulator close success")

    @classmethod
    def simulator_node_reset(cls):
        """
        author: panapn.du
        date  : 2020.10.22
        description: 执行重启节点
        :return: 无返回值

        @changelog      2021-02-27 09:53:23  haibin.xu
                        1. 作为类方法并入RunAllTestPs3类
        """
        if (constants.ENV_PLATFORM_SIMU == cls.test_platform) and not (
                (constants.ENV_TEST_ENTRY_IOC == cls.test_entry) and (
                constants.ENV_TEST_OBJECT_EXPANDER == cls.test_object)):
            script_path = constants.HOST_IOC_RESET_FILE_PATH
            log.info("Simulator is resetting...")
            result = utils.simulator_operate(script_path, cls.host_qemu_ip, cls.host_port)
            if result:
                log.error("Simulator reset fail")
                log.error(result)
                exit(0)
            else:
                log.info("Simulator reset success")
                time.sleep(30)

    @staticmethod
    def __isvalid(param=None) -> bool:
        """
        author:      haibin.xu
        date:        2021-06-08 15:34:55
        description: 检查参数的有效性

        :param param: 待定检查的参数
        :return:     参数有效返回True，否则返回False
        """
        if param is None:
            rtn_check_result = False
        elif isinstance(param, str) and ('' == param):
            rtn_check_result = False
        elif isinstance(param, list) and ([] == param):
            rtn_check_result = False
        elif isinstance(param, dict) and ({} == param):
            rtn_check_result = False
        elif isinstance(param, tuple) and (() == param):
            rtn_check_result = False
        elif isinstance(param, bool):
            rtn_check_result = param
        else:
            rtn_check_result = True

        return rtn_check_result

    @classmethod
    def __get_other_parameters(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-03-20 16:56:11
        description: 获取相关类变量

        :return:     None
        """
        cls.host_cpu = cls.config_dict.get(constants.ENV_HOST_CPU)
        if not cls.__isvalid(cls.host_cpu) or (cls.host_cpu not in [hc.value for hc in HostCpuEnum]):
            log.error('Fail to get env parameter: host_cpu.')
            exit(1)

        cls.host_os = cls.config_dict.get(constants.ENV_HOST_OS)
        if not cls.__isvalid(cls.host_os):
            log.error('Fail to get host_os: {}.'.format(cls.host_os))
            exit(1)

        cls.job_id = cls.config_dict.get(constants.ENV_JOB_ID)
        if not cls.__isvalid(cls.job_id):
            log.error('Fail to get job_id: {}.'.format(cls.job_id))
            exit(1)

        cls.job_name = cls.config_dict.get(constants.ENV_JOB_NAME)
        if not cls.__isvalid(cls.job_name):
            log.error('Fail to get job_name: {}.'.format(cls.job_name))
            exit(1)

        # 执行测试任务轮数
        cls.test_rounds = cls.config_dict.get(constants.ENV_TEST_ROUNDS)
        if not cls.__isvalid(cls.test_rounds) and (1 > cls.test_rounds):
            log.error('Invalid test rounds: {}.'.format(cls.test_rounds))
            exit(1)

        cls.host_ip = cls.ip_dict.get(constants.ENV_HOST_IP)
        if not cls.__isvalid(cls.host_ip):
            log.error('Fail to get host ip.')
            exit(1)

        cls.host_port = cls.ip_dict.get(constants.ENV_HOST_PORT)
        if not cls.__isvalid(cls.host_port):
            log.warning('Fail to get host port. set default value 22.')
            cls.host_port = 22

        cls.host_qemu_ip = cls.ip_dict.get(constants.ENV_HOST_QEMU_IP)
        if not cls.__isvalid(cls.host_qemu_ip):
            log.error('Fail to get host qemu ip.')
            exit(1)

        cls.ioc_ip = cls.ip_dict.get(constants.TEST_CONFIG_IOC_IP)
        if not cls.__isvalid(cls.ioc_ip):
            log.error('Fail to get ioc ip.')
            exit(1)

        cls.ioc_port = cls.ip_dict.get(constants.ENV_IOC_PORT)
        if not cls.__isvalid(cls.ioc_port):
            log.warning('Fail to get ioc port. set default value 22.')
            cls.ioc_port = 22

        cls.ioc_qemu_ip = cls.ip_dict.get(constants.TEST_CONFIG_IOC_QEMU_IP)
        if not cls.__isvalid(cls.ioc_qemu_ip):
            log.error('Fail to get ioc qemu ip.')
            exit(1)

        cls.test_platform = cls.config_dict.get(constants.ENV_TEST_PLATFORM)
        if not cls.__isvalid(cls.test_platform):
            log.error('Fail to get test platform.')
            exit(1)

        cls.auto_add_disk_flag = cls.config_dict.get(constants.ENV_CASE_AUTO_ADD_DISK)
        if not cls.__isvalid(cls.auto_add_disk_flag) or cls.test_platform == TestPlatformEnum.REAL_PLATFORM.value:
            log.error('Fail to get auto_add_disk_flag, set default value: False.')
            cls.auto_add_disk_flag = False
        log.info('Auto add disk flag: {}.'.format(cls.auto_add_disk_flag))

        cls.gcov_flag = cls.config_dict.get(constants.ENV_GCOVER_VERSION)
        if not cls.__isvalid(cls.gcov_flag):
            log.info('Current package is not gcover version.')
            cls.gcov_flag = False
        log.info('gcov flag: {}.'.format(cls.gcov_flag))

        cls.compile_object = cls.config_dict.get(constants.ENV_COMPILE_OBJECT)
        if not cls.__isvalid(cls.compile_object):
            log.warning('Fail to get compile_object. set default value: ps3')
            cls.compile_object = 'ps3'

        cls.test_entry = cls.config_dict.get(constants.ENV_TEST_ENTRY)
        if not cls.__isvalid(cls.test_entry):
            log.error('Fail to get test entry.')
            exit(1)

        cls.test_function = cls.config_dict.get(constants.ENV_TEST_FUNCTION)
        if not cls.__isvalid(cls.test_function):
            log.warning('Fail to get test_function, set it default value: one')
            cls.bug_stop = 'one'

        cls.test_object = cls.config_dict.get(constants.ENV_TEST_OBJECT)
        if not cls.__isvalid(cls.test_object):
            log.error('Fail to get test object.')
            exit(1)

        cls.package_install = cls.config_dict.get(constants.ENV_PACKAGE_INSTALL)
        log.info('package install: {}'.format(cls.package_install))

        cls.install_cmd = cls.config_dict.get(constants.ENV_INSTALL_CMD)
        log.info('install cmd: {}'.format(cls.install_cmd))

        if (TestEntryStrEnum.SOC.value == cls.test_entry) and (TestObjectStrEnum.EXPANDER.value == cls.test_object):
            # 只有在单独expander测试时，才获取expander_port
            cls.expander_port = cls.ip_dict.get(constants.ENV_EXPANDER_PORT)
            if not cls.__isvalid(cls.expander_port):
                log.warning('Fail to get expander port.')

        cls.bug_stop = cls.config_dict.get(constants.ENV_BUG_STOP)
        if not cls.__isvalid(cls.bug_stop):
            log.warning('Fail to get bug stop, set it default value: False')
            cls.bug_stop = False

        if TestObjectStrEnum.RAID.value == cls.test_object:
            cls.libs_test_object = TestObjectEnum.RAID.value
        elif TestObjectStrEnum.HBA.value == cls.test_object:
            cls.libs_test_object = TestObjectEnum.HBA.value
        elif TestObjectStrEnum.EXPANDER.value == cls.test_object:
            cls.libs_test_object = TestObjectEnum.EXPANDER.value
        elif TestObjectStrEnum.PCIE_SWITCH.value == cls.test_object:
            cls.libs_test_object = TestObjectEnum.PCIE_SWITCH.value
        else:
            log.error('Invalid test object: {}.'.format(cls.test_object))
            exit(1)

        cls.PS3CLI = libs_constants.PS3CLI64
        cls.PS3KO = libs_constants.DRIVER_FILE_NAME
        if HostCpuEnum.CPU_X86.value == cls.host_cpu:
            cls.host_work_path = libs_constants.HOST_WORK_PATH_X86
        elif HostCpuEnum.CPU_ARM.value == cls.host_cpu:
            cls.host_work_path = libs_constants.HOST_WORK_PATH
        else:
            log.error('Invalid host_cpu: {}.'.format(cls.host_cpu))
            exit(1)

        cls.long_stab_test = cls.config_dict.get(constants.ENV_LONG_STAB_TEST)
        if not cls.__isvalid(cls.long_stab_test):
            log.warning('Fail to get long stab test, set it default value: no')
            cls.long_stab_test = False

        cls.log_trace = cls.config_dict.get(constants.ENV_LOG_TRACE)
        if not cls.__isvalid(cls.log_trace):
            log.warning('Fail to get log trace, set it default value: no')
            cls.log_trace = False

        cls.host_trace = cls.config_dict.get(constants.ENV_HOST_TRACE)
        if not cls.__isvalid(cls.host_trace):
            log.warning('Fail to get host trace, set it default value: no')
            cls.host_trace = False

        cls.case_list_order = cls.config_dict.get(constants.ENV_CASE_LIST_ORDER)
        if not cls.__isvalid(cls.case_list_order):
            log.warning('Fail to get case list order, set it default value: default')
            cls.case_list_order = CaseOrderEnum.DEFAULT_ORDER.value

        cls.fio_cmd_lat = cls.config_dict.get(constants.ENV_FIO_CMD_LAT)
        if not cls.__isvalid(cls.fio_cmd_lat):
            log.warning('Fail to get fio cmd lat, set it default value: no')
            cls.fio_cmd_lat = False

        cls.cut_off = cls.config_dict.get(constants.ENV_CUT_OFF)
        if not cls.__isvalid(cls.cut_off):
            log.warning('Fail to get cut off, set it default value: 10')
            cls.cut_off = 10

        cls.driver_reset = cls.config_dict.get(constants.ENV_DRIVER_RESET)
        if not cls.__isvalid(cls.driver_reset):
            log.warning('Fail to get driver reset, set it default value: default')
            cls.driver_reset = 'default'

        cls.driver_reset_time = cls.config_dict.get(constants.ENV_DRIVER_RESET_TIME)
        if not cls.__isvalid(cls.driver_reset_time):
            log.warning('Fail to get driver reset time, set it default value: 300')
            cls.driver_reset_time = 300

        cls.skip_qemu_start = cls.config_dict.get(constants.ENV_SKIP_QEMU_START)
        if not cls.__isvalid(cls.skip_qemu_start):
            log.warning('Fail to get skip qemu start, set it default value: no')
            cls.skip_qemu_start = False

        cls.memory_leak = cls.config_dict.get(constants.ENV_MEMORY_LEAK)
        if not cls.__isvalid(cls.memory_leak):
            log.warning('Fail to get memory leak, set it default value: no')
            cls.memory_leak = False

        cls.ioc_memory_leak = cls.config_dict.get(constants.ENV_IOC_MEMORY_LEAK)
        if not cls.__isvalid(cls.ioc_memory_leak):
            log.warning('Fail to get ioc_memory_leak, set it default value: no')
            cls.ioc_memory_leak = False

        cls.ignore_disk = cls.config_dict.get(constants.ENV_IGNORE_DISK)
        if not cls.__isvalid(cls.ignore_disk):
            log.warning('Fail to get ignore disk, set it default value: no')
            cls.ignore_disk = False

        cls.cc_error_stop = cls.config_dict.get(constants.ENV_CC_ERROR_STOP)
        if not cls.__isvalid(cls.cc_error_stop):
            log.warning('Fail to get cc_error_stop, set it default value: no')
            cls.cc_error_stop = False

        cls.san_blaze_ip = cls.ip_dict.get(constants.TEST_CONFIG_SANBLAZE)
        if cls.san_blaze_ip is None:
            log.info('Fail to get SAN blaze ip.')

        cls.comhost_ip = cls.ip_dict.get(constants.TEST_CONFIG_COMHOST)
        if cls.comhost_ip is None:
            log.info('Fail to get comhost ip.')

        cls.a72_com = str(cls.ip_dict.get(constants.TEST_CONFIG_A72))
        if cls.a72_com is None:
            log.info('Fail to get a72 com.')

        cls.log_server_account = cls.ip_dict.get(constants.ENV_LOG_SERVER_ACCOUNT)
        if cls.log_server_account is None:
            log.info('Fail to get log_server_account.')

        cls.log_server_ip = cls.ip_dict.get(constants.ENV_LOG_SERVER_IP)
        if cls.log_server_ip is None:
            log.info('Fail to get log_server_ip.')

        cls.mpduip = cls.ip_dict.get(constants.TEST_CONFIG_MPDUIP)
        if cls.mpduip is None:
            log.info('Fail to get mpdu ip.')

        try:
            cls.vd_queue_depth = int(cls.ip_dict.get(constants.ENV_VD_QUEUE_DEPTH))
        except Exception as e:
            cls.vd_queue_depth = None

        if cls.vd_queue_depth is None or cls.vd_queue_depth <= 0:
            cls.vd_queue_depth = None
            log.info('Fail to get vd queue depth.')

        cls.exam_2021 = cls.config_dict.get(constants.ENV_EXAM_2021)
        if not cls.__isvalid(cls.exam_2021):
            log.warning('Fail to get exam 2021, set it default value: no')
            cls.exam_2021 = False

        cls.exam_long_stab_test_2021 = cls.config_dict.get(constants.ENV_EXAM_LONG_STAB_TEST_2021)
        if not cls.__isvalid(cls.exam_long_stab_test_2021):
            log.warning('Fail to get exam_long_stab_test_2021, set it default value: no')
            cls.exam_long_stab_test_2021 = False

        cls.compatibility_test = cls.config_dict.get(constants.ENV_COMPATIBILITY_TEST)
        if not cls.__isvalid(cls.compatibility_test):
            log.warning('Fail to get compatibility_test, set it default value: no')
            cls.compatibility_test = False

        cls.clear_log = cls.config_dict.get(constants.ENV_CLEAR_LOG)
        if not cls.__isvalid(cls.clear_log):
            log.warning('Fail to get clear log, set it default value: yes')
            cls.clear_log = True

        cls.is_perf = cls.config_dict.get(constants.ENV_IS_PREF)
        if not cls.__isvalid(cls.is_perf):
            log.warning('Fail to get is_perf, set it default value: no')
            cls.is_perf = False

    @classmethod
    def __reset_constants_parameters(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-03-22 10:12:46
        description: 重置constans下的host ip, host node ip, ioc ip, ioc node ip, PS3CLI64, SIMADMIN

        :return:     None
        """
        libs_constants.reset_ip_parameters(new_host_ip=cls.host_ip, new_host_node_ip=cls.host_qemu_ip,
                                           new_ioc_ip=cls.ioc_ip, new_ioc_node_ip=cls.ioc_qemu_ip,
                                           new_host_port=cls.host_port, new_ioc_port=cls.ioc_port)
        log.info('Success reset ip parameters in constants.py, host ip: {}, host node ip: {}, ioc ip: {}, '
                 'ioc node ip: {}, host port: {}, ioc port: {}.'.format(libs_constants.HOST_IP,
                                                                        libs_constants.HOST_NODE_IP,
                                                                        libs_constants.SOC_IP,
                                                                        libs_constants.SOC_NODE_IP,
                                                                        libs_constants.HOST_PORT,
                                                                        libs_constants.SOC_PORT))

        libs_constants.reset_cmd_product(new_host_cpu=cls.host_cpu, test_object=cls.libs_test_object)
        log.info('Success reset command products parameters in constants.py. PS3CLI: {}, SIMADMIN: {}'.format(
            libs_constants.PS3CLI64, libs_constants.SIMADMIN))

        libs_constants.reset_test_obj(new_test_obj=cls.libs_test_object)
        log.info('Success reset test object parameter in constants.py. test object: {}.'.format(
            libs_constants.test_obj))

        libs_constants.reset_test_entry(new_test_entry=cls.test_entry)
        log.info('Success reset test entry parameter in constants.py. test entry: {}.'.format(
            libs_constants.TEST_ENTRY))

    @classmethod
    def __get_cli_deploy_ip(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-03-17 16:28:54
        description: 获取cli 部署ip

        :return:     None

        @changelog      2021-04-20 16:15:23  haibin.xu
                        1. 函数名调整：__get_frontend_ip -> __get_cli_deploy_ip
        """
        if TestEntryStrEnum.HOST.value == cls.test_entry:
            cls.cli_deploy_ip = cls.host_qemu_ip
            cls.cli_deploy_port = cls.host_port
        elif TestEntryStrEnum.SOC.value == cls.test_entry:
            cls.cli_deploy_ip = cls.ioc_qemu_ip
            cls.cli_deploy_port = cls.ioc_port
        elif TestEntryStrEnum.UEFI.value == cls.test_entry:
            log.info("test entry is uefi , not need get cli deploy ip ")
        else:
            log.error('Fail to get cli deploy ip, reason: invalid test entry, not host or soc.')
            exit(1)

    @classmethod
    def __get_bug_obj(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 17:12:59
        description: 初始化bug对象, 用于后续的bug收集

        :return:     None
        """
        # 将测试环境、测试目标、测试任务信息设置到bug对象中
        cls.bug_object = Bug()
        cls.bug_object.set_common_values(cls.config_dict, cls.ip_dict)

    @classmethod
    def init_parameters(cls):
        """
        author:      haibin.xu
        date:        2021-02-26 16:46:24
        description: 初始化类变量
        :return:     None
        """
        log.info(constants.LOG_FUNCION_SCRIPTS.format('Start init run all test ps3 parameters ...'))

        cls.__get_case_script_map_obj()
        cls.__get_env_configure_data()
        cls.__get_other_parameters()
        cls.__reset_constants_parameters()
        cls.__get_bug_obj()
        cls.__get_collect_log_obj()
        cls.__get_cli_deploy_ip()
        cls.__get_log_analysis_obj()

        log.info(constants.LOG_FUNCION_SCRIPTS.format('Finish init run all test ps3 parameters.'))

    @classmethod
    def start_simulator_platform(cls) -> int:
        """
        author: panapn.du
        date  : 2020.10.22
        description: 启动模拟平台
        :return: 模拟平台脚本正常执行，返回0，执行失败，返回-1

        @changelog      2021-02-27 09:28:18  haibin.xu
                        1. 作为类方法并入RunAllTestPs3类
                        2021-03-04 18:06:43  haibin.xu
                        1. 优化函数实现，将该函数只作为启动模拟平台的功能
                        2. 函数名更改：simulator_node_start -> start_simulator_platform
                        3. 更改返回值类型 None -> int
        """
        log.info(constants.LOG_FUNCION_SCRIPTS.format('Start simulator test platform ...'))
        log.info('test_entry: {}, test_object: {}'.format(cls.test_entry, cls.test_object))

        if (constants.ENV_TEST_ENTRY_IOC == cls.test_entry) and (constants.ENV_TEST_OBJECT_EXPANDER ==
                                                                 cls.test_object):
            log.info('Call script exp_simu_open.py.')
            cls.expander_flag = True
            rtn_script, cls.expander_env_id = ExpanderSimuStart.do()
        elif constants.ENV_TEST_OBJECT_PCIE_SWITCH == cls.test_object:
            log.info('Call script sw_simu_open.py.')
            cls.pcie_switch_flag = True
            rtn_script = PcieSwitchSimuStart.do()
        else:
            log.info('Call host_ioc_start.py.')
            rtn_script, cls.expander_env_id = HostIocStart.do()

        log.info(constants.LOG_FUNCION_SCRIPTS.format('Success to finish simulator test platform.'))

        return rtn_script

    @classmethod
    def start_real_platform(cls) -> int:
        """
        author:      haibin.xu
        date:        2021-03-04 18:17:32
        description: 启动真实平台

        :return:     真实平台脚本正常执行，返回0，执行失败，返回-1
        """
        log.info(constants.LOG_FUNCION_SCRIPTS.format('Start real test platform ...'))

        if cls.test_object in [constants.TEST_OBJECT_EXPANDER, constants.TEST_OBJECT_PCIE_SWITCH]:
            if not cls.__isvalid(cls.package_install):
                log.info('package_install: {}, not need to update expander'.format(cls.package_install))
                return 0
            rtn_script = RealExpanderStart.do()
        else:
            log.info('Call host_ioc_start.py.')
            rtn_script = RealHostStart.do()

        log.info(constants.LOG_FUNCION_SCRIPTS.format('Success to finish real test platform.'))
        return rtn_script

    @classmethod
    def __enable_watchdog(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 14:12:13
        description: 检查并使能watchdog开关

        :return:     None
        """
        # 非模拟平台环境,物理环境开启后会卡住，暂时关闭
        if cls.test_platform != constants.ENV_PLATFORM_SIMU:
            return

        if (not cls.pcie_switch_flag) and (not cls.expander_flag):
            watchdog_switch, watchdog_bark_time = CustomOperation.check_watchdog_state()
            if '1' != watchdog_switch:
                # watchdog_switch不为1时，表示watchdog尚未打开，需要打开，dog_bark_time 根据研发（戚海平）建议设为80s
                if RtnStatusEnum.SUCCESS.value == CustomOperation.set_watchdog(dog_barken=1, dog_bark_time=80):
                    log.info('Success open watchdog, dogbarktime: 80s.')
                else:
                    log.warning('Fail to open watchdog.')
            else:
                log.info('Opened watchdog, not need to reopen watchdog.')

    @classmethod
    def __get_test_start_time_info(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 14:15:11
        description: 设置测试开始时间参数

        :return:     None
        """
        # 任务开始测试时间，格式为20200423151820(2020年4月23日)
        cls.test_start_timestamp, cls.test_start_time = CommandOperation.get_time()

    @classmethod
    def __init_run_all_test_log_file(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 14:58:07
        description: 初始化run_all_test_ps3_[timestamp].log文件，日志路径test/esat/outputs/framework/

        :return:     None
        """
        log.info("init run all test log file")
        # 获取当前测试文件名，即run_all_test_ps3
        script_file_name, _ = CommandOperation.get_file_info(os.path.abspath(__file__))
        log.info('script file name: {}'.format(script_file_name))
        # 初始化当前脚本的日志文件, 如test/esat/outputs/framework/run_all_test_ps3_20210611145106.log
        cls.run_all_test_log_file = utils.make_run_all_test_log(cls.test_start_time, script_file_name)

    @classmethod
    def __init_outputs_job_directory(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 15:25:15
        description: 初始化test/esat/outputs/framework/目录下的[job_name]_[job_id]_[测试开始时间戳]目录，全路径如：
                     test/esat/outputs/framework/ps3_auto_test_prepare_14093_20210610175943

        :return:     None
        """
        # 生成测试任务信息列表, 即[job_name, str(job_id), task_start_time]
        job_info_list = utils.make_job_info_list(cls.test_start_time)
        # 生成正在执行的测试job的输出信息目录, 即test/esat/outputs/framework/ps3_auto_test_prepare_14093_20210610175943
        cls.job_directory_path, cls.job_directory_name = utils.make_job_outputs_dir(job_info_list)
        log.info('outputs job directory path: {}; job directory name: {}'.format(cls.job_directory_path,
                                                                                 cls.job_directory_name))
        # 生成保存web截图的目录,即test/esat/outputs/framework/ps3_auto_test_14093_web_screenshot
        cls.web_directory_path = utils.make_web_outputs_dir(constants.WEB_SCREENSHOT_PATH)
        log.info('outputs web screenshot directory path: {}'.format(cls.web_directory_path))

    @classmethod
    def __get_script_case_info(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 16:25:20
        description: 解析测试用例case文件，获取需要测试的脚本信息，如禅道触发，文件路径一般为：test/esat/scripts/
                     case_script_lists/zentao_auto/case_script_20210506101716.xlsx, 如Jenkins触发，文件路径一般为：test/
                     esat/scripts/case_script_lists/common/mini_case_script_list.csv

        :return:     None
        """
        cls.script_case_dict = cls.case_script_dict.case_script_dict_get()

    @classmethod
    def __get_shuffle_script_case_info(cls) -> None:
        """
        author:      sunql
        date:        2021-08-19
        description: 返回打乱顺序后的cases字典
        :return: None
        """
        if cls.long_stab_test:
            dict_key_ls = list(cls.script_case_dict.keys())
            random.shuffle(dict_key_ls)
            # 多执行一次，确保乱序
            random.shuffle(dict_key_ls)
            new_dict = {}
            for key in dict_key_ls:
                new_dict[key] = cls.script_case_dict.get(key)
            cls.script_case_dict = new_dict
            log.info("test is long stab test,shuffle cases is ok")
        elif constants.TEST_OBJECT_EXPANDER == cls.test_object:
            if CaseOrderEnum.DEFAULT_ORDER.value == cls.case_list_order:
                new_dict = {}
                dict_key_ls = list(cls.script_case_dict.keys())

                if CaseOrderEnum.DESC_ORDER.value == cls.case_list_order:
                    dict_key_ls = dict_key_ls[::-1]
                elif CaseOrderEnum.RANDOM_ORDER.value == cls.case_list_order:
                    random.shuffle(dict_key_ls)

                for key in dict_key_ls:
                    new_dict[key] = cls.script_case_dict.get(key)
                cls.script_case_dict = new_dict

                log.info('expander test, Success to modify case_list_order: {}.'.format(cls.case_list_order))
        else:
            log.info('Not long stable test and expander test, not need to modify test order.')

    @classmethod
    def __save_shuffle_script_case_to_excel(cls) -> None:
        """
        author:      sunql
        date:        2021-08-19
        description: 保存打乱顺序后的cases至excel
        :return:
        """
        try:
            _ = (CaseScriptMap()).shuffle_case_script_file_create(cls.script_case_dict,
                                                                  cls.test_script_log_directory)
        except Exception as e:
            log.error("can not create shuffle script case excel:\n{}".format(e))

    @classmethod
    def __init_log_directory_in_log_server(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 16:33:51
        description: 在日志服务器上初始化本次测试的日志保存路径，如：/home/framework/log/host_vm670_10.22.81.1_22/
                     2021_06_11/16_03_12

        :return:     None
        """
        cls.log_server_path = cls.collect_log.make_log_root_directory_in_log_server(cls.test_start_timestamp)
        if cls.log_server_path == '':
            log.error('make log_directory_in_log_server is fail , test stop')
            exit(1)

    @classmethod
    def __init_test_bug_and_result_file(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 16:42:59
        description: 初始化本次测试的bug, result的Excel文件，如：test/esat/outputs/framework/
                     ps3_auto_test_prepare_5688_20210611160312/bugs/
                     ps3_auto_test_prepare_5688_20210611160312_bugs.xlsx, test/esat/outputs/framework/
                     ps3_auto_test_prepare_5688_20210611160312/results/
                     ps3_auto_test_prepare_5688_20210611160312_results.xlsx

        :return:     None
        """
        # 生成问题列表文件和结果列表文件
        cls.test_bug_excel_file_path, cls.test_result_excel_file_path = bug_result_excel_handle.create_files(
            cls.job_directory_path, cls.job_directory_name)

    @classmethod
    def __init_test_report_log_file(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 16:53:20
        description: 初始化测试报告日志文件，如：test/esat/outputs/framework/
                     ps3_auto_test_prepare_5688_20210611160312/report_log_20210611160312.log

        :return:     None
        """
        report_log_file_name = '{}_{}.log'.format(constants.REPORT_LOG_FILE_NAME, cls.test_start_time)
        cls.test_report_log_file_path = os.path.join(cls.job_directory_path, report_log_file_name)

    @classmethod
    def __init_test_scripts_directory(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-11 17:02:00
        description: 初始化测试脚本日志目录，即：test/esat/outputs/framework/ps3_auto_test_prepare_5688_20210611160312/
                     test_script_logs

        :return:     None
        """
        cls.test_script_log_directory = utils.make_scripts_log(cls.job_directory_path)

    @classmethod
    def __set_ioc_node_log_poll_write(cls):
        """
        当日志trace参数为True时，获取ioc log磁盘大小，并判断是否需要调整循环写
        :return:
        """
        # 当不打开log trace 或 不需要重新启动 host ioc 时
        if not cls.log_trace or cls.skip_qemu_start:
            log.info('log trace unwanted modify......')
            return
        log.info("log trace is True,reset log poll write begin")
        # 获取ioc log 磁盘size
        disk_size = HostOperation.get_ioc_node_log_disk_size(cls.ioc_qemu_ip)
        if disk_size <= 30:
            log.info(f"free disk size is {disk_size}G,unwanted reset log poll write")
            return
        # 重设 log 循环写文件数量及size
        file_num = int(disk_size * 0.8)
        rtn_code = CustomOperation.set_ioc_node_log_poll_write(ip=cls.host_qemu_ip, ioc_ip=cls.ioc_qemu_ip,
                                                               file_num=file_num)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            log.error("log trace is True,but reset log poll write exec fail")
            exit(1)
        log.info("log trace is True,reset log poll write is success")

    @classmethod
    def __clean_disk_part(cls):
        """
        author: sunql
        date  : 2022.02.18
        description: 清理卡下所有磁盘分区
        :return:
        """
        if constants.ENV_PLATFORM_REAL == cls.test_platform and \
                (cls.test_object == constants.TEST_OBJECT_EXPANDER or
                 cls.test_object == constants.TEST_OBJECT_PCIE_SWITCH) or \
                cls.test_entry == TestEntryStrEnum.UEFI.value:
            # do nothing, add by hejf,20220319
            return

        log.info("start clean disk part...")

        scid = CommandOperation.git_scsi_host_id()
        log.info(f"scsi host id: {scid}")

        if scid:
            # 获取job是否为on
            jbod_flag = ControllerOperation.check_jbod_on(controller_id=libs_constants.X16_CONTROLLER)
            rtn_code = RtnStatusEnum.SUCCESS.value
            # job off 时,打开
            if not jbod_flag:
                rtn_code, _ = ControllerOperation.set_jbod_switch(controller_id=libs_constants.X16_CONTROLLER,
                                                                  switch_type='on')
            # 删除卡下盘分区
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                CommandOperation.del_ps3_disk_part(scid)
            # 如果job，刚刚on过
            if not jbod_flag and rtn_code == RtnStatusEnum.SUCCESS.value:
                rtn_code, _ = ControllerOperation.set_jbod_switch(controller_id=libs_constants.X16_CONTROLLER,
                                                                  switch_type='off')

        log.info("end clean disk part...")

    @classmethod
    def check_tools(cls) -> None:
        """
        检查环境中工具是否符合要求
        author: sunql
        date  : 2022.04.12
        :return:
        """

        # 跳过Expander\windows\uefi环境对于FIO工具的检查
        if constants.ENV_TEST_OBJECT_EXPANDER == cls.test_object or \
                constants.ENV_TEST_OBJECT_PCIE_SWITCH == cls.test_object \
                or 'windows' in cls.host_os or cls.test_entry == TestEntryStrEnum.UEFI.value:
            return
        stop_flag = False
        # 检查 fio 版本
        cmd = "fio -v"
        _, cmd_out, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd,
                                                                                     ssh_ip=cls.host_qemu_ip)
        log.info(f"check fio version result is: {cmd_out}")
        if cmd_out != "fio-3.1":
            stop_flag = True
            log.error(f"check fio version is fail,version must fio-3.1")

        if stop_flag:
            log.error(f"check tools is fail，test finish ...")
            exit(1)

    @classmethod
    def __check_testserver_memmap(cls):
        """
        测试开始前检查是否保留了4G内存空间
        :return:
        """
        if constants.ENV_PLATFORM_REAL != cls.test_platform:
            return

        if cls.test_object != constants.TEST_OBJECT_RAID:
            return

        if cls.test_entry == TestEntryStrEnum.UEFI.value:
            return

        memmap = CommandOperation.get_testserver_memmap()
        if memmap < 4:
            log.error(f"check testserver memmap is fail, memory map must > 4G，test stop ...")
            exit(1)

    @classmethod
    def __check_mini_com(cls) -> None:
        """
        检查串口交换机是否存活
        author:sunql
        :return: None
        """

        def get_com_log_num(com_log_path):
            cmd = f'cat {com_log_path} | wc -l'
            _, output, _ = CommandOperation. \
                execute_command_based_paramiko_with_rtncode(cmd=cmd,
                                                            ssh_ip=cls.log_server_ip,
                                                            ssh_port='22',
                                                            ssh_username=cls.log_server_account)
            log.info(f"com log num is {output}")
            return int(output.strip())

        if constants.ENV_PLATFORM_REAL == cls.test_platform and \
                (cls.test_object == constants.TEST_OBJECT_EXPANDER or
                 cls.test_object == constants.TEST_OBJECT_PCIE_SWITCH) or \
                cls.test_entry == TestEntryStrEnum.UEFI.value:
            return

        if constants.ENV_PLATFORM_REAL != cls.test_platform:
            return

        if cls.test_object != constants.TEST_OBJECT_HBA:
            return

        # 判断是否需要检查串口交换机状态
        if not cls.a72_com or 'dev' in cls.a72_com or cls.a72_com == '' \
                or not cls.comhost_ip or cls.comhost_ip == '':
            log.info(f"com port is {cls.a72_com},com ip is {cls.comhost_ip},not need check")
            return

        ip = cls.comhost_ip
        port = cls.a72_com
        day = time.strftime("%Y-%m-%d", time.localtime())
        com_log_path = f"{libs_constants.COM_LOG_DIR}/{ip}/{port}/com_log_{ip}_{port}_{day}.log"

        for i in range(3):
            check_flag, output = FileOperation.path_exists(path=com_log_path, ip=cls.log_server_ip,
                                                           username=cls.log_server_account)
            if check_flag == RtnStatusEnum.SUCCESS.value:
                break
            else:
                # 如果时12：00有可能串口日志文件还没有生成，强制生成一下再重试
                CustomOperation.tigger_dump_log(controller_id='call')
                time.sleep(30)

        if check_flag != RtnStatusEnum.SUCCESS.value:
            log.error(f"com log not exists , test is stop , please check")
            exit(1)

        line_num = get_com_log_num(com_log_path)

        CustomOperation.tigger_dump_log(controller_id='call')

        for i in range(100):
            time.sleep(3)
            if get_com_log_num(com_log_path) != line_num:
                return

        log.error(f"com log not change after exec cli, test is stop , please check")
        exit(1)

    @classmethod
    def get_os_vd_info(cls) -> None:
        """
        获取卡下 os vd 信息 并保存
        :return: None
        """
        if constants.ENV_PLATFORM_REAL == cls.test_platform and \
                (cls.test_object == constants.TEST_OBJECT_EXPANDER or
                 cls.test_object == constants.TEST_OBJECT_PCIE_SWITCH) or \
                cls.test_entry in [TestEntryStrEnum.UEFI.value, TestEntryStrEnum.SOC.value]:
            return

        log.info("get os vd start ...")

        cls.os_vd_id = VirtualDisk.get_os_vd_id(controller_id=libs_constants.X16_CONTROLLER, without_config=True)
        # cls.os_vd_id = 1
        log.info(f"os vd id is {cls.os_vd_id}")

        if cls.os_vd_id > -1:
            cls.os_slot_id = VirtualDisk.get_vd_eid_sid(libs_constants.X16_CONTROLLER, cls.os_vd_id)
            log.info(f"os slot id is {cls.os_slot_id}")

            if not cls.os_slot_id:
                log.error("not found os slot id , test is stop ...")
                exit()
        # 保存信息到配置文件
        os_vd_info = {libs_constants.ENV_OS_VD_ID: cls.os_vd_id, libs_constants.ENV_OS_SLOT_ID: cls.os_slot_id}
        EnvPlatFormOperation.set_env_platform_info(os_vd_info)

        log.info("get os vd end ...")

    @classmethod
    def __get_platform_info(cls):

        if cls.test_entry in [TestEntryStrEnum.SOC.value, TestEntryStrEnum.UEFI.value]:
            log.info('test entry is soc or uefi, not need to collect platform info, return.')
            return

        platform_info = HostOperation.get_platform_info()
        tools_info = HostOperation.get_test_tools_info()
        driver_info = HostOperation.get_modinfo()
        ioc_info = CustomOperation.get_cli_sysinfo(controller_id=libs_constants.X16_CONTROLLER)
        _, cli_commit_id, cli_branch = ControllerOperation.get_cli_version(libs_constants.X16_CONTROLLER)
        cli_driver_dict = ControllerOperation.get_cli_fw_nv_bios_version(libs_constants.X16_CONTROLLER)
        driver_info['driver_build_branch'] = cli_driver_dict['driver_version']
        driver_info['ioc_version'] = cli_driver_dict['fw_version']
        driver_info['disk_num'] = cli_driver_dict['disk_num']
        driver_info['cli_version'] = cli_driver_dict['cli_version']
        driver_info['cpld_version'] = cli_driver_dict['cpld_version']
        cls.test_platform_info = {'mini_com_ip': cls.comhost_ip, 'mini_com_port': cls.a72_com}
        cls.test_platform_info.update(platform_info)
        cls.test_platform_info.update(ioc_info)
        cls.test_platform_info.update(driver_info)
        cls.test_platform_info.update({'cli_commit_id': cli_commit_id, 'cli_branch': cli_branch})
        cls.test_platform_info.update(tools_info)
        cls.test_platform_add_exp_info = copy.deepcopy(cls.test_platform_info)
        cls.test_platform_info = json.dumps(cls.test_platform_info)
        log.info(f"test platfrom info : {cls.test_platform_info}")
        cls.bug_object.set_platform_info(cls.test_platform_info)
        # 打印 soft cli info
        log.info("soft cli info is:{}".format(ControllerOperation.get_soft_cli_info()))

    @classmethod
    def check_cli_fw_bois_nv_version(cls):
        """
        检查 cli fw bois nvdata version是否一致，仅物理环境hba检查
        :return:
        """
        if cls.test_object != TestObjectStrEnum.HBA.value:
            return
        if cls.test_platform != TestPlatformEnum.REAL_PLATFORM.value:
            return
        if cls.test_entry == TestEntryStrEnum.UEFI.value:
            return
        # 如果是兼容性测试不验证
        if cls.compatibility_test:
            return

        log.info("compatibility test is no,check version start ...")

        version_dict = ControllerOperation.get_cli_fw_nv_bios_version(libs_constants.X16_CONTROLLER)
        log.info(version_dict)
        version_dict.pop('disk_num')
        version_dict.pop('cpld_version')
        value = None
        for key in version_dict.keys():
            if not value:
                value = version_dict.get(key)
                continue
            if value != version_dict.get(key):
                log.error(f"{version_dict}, please check test version")
                exit(1)

    @classmethod
    def prepare_before_test(cls) -> None:
        """
        author: luyafei
        date  : 2020.04.21
        description: 测试前准备
        :return:

        @changelog      2021-02-27 09:38:05  haibin.xu
                        1. 作为类方法并入RunAllTestPs3类
                        2021-06-04 10:10:00  haibin.xu
                        1. 优化函数实现， 函数名修正：prepare_env -> prepare_before_test
        """
        # 检查环境工具
        cls.check_tools()
        cls.__get_platform_info()
        # 检查串口交换机
        # cls.__check_mini_com()
        # 检查内存预留空间是否 >= 4G
        cls.__check_testserver_memmap()
        # 获取cli build mode
        cls.get_cli_mod()
        # 验证cli 版本
        cls.check_cli_fw_bois_nv_version()
        # 获取系统vd信息
        cls.get_os_vd_info()
        # 启动测试前切割串口服务器日志
        cls.split_real_com_log()
        # 清理卡下所有磁盘分区
        cls.__clean_disk_part()
        # 设置测试开始时间参数
        cls.__get_test_start_time_info()
        # 初始化test/esat/outputs/framework/目录下的run_all_test_ps3_[测试开始时间戳].log
        cls.__init_run_all_test_log_file()
        # 创建[job_name]_[job_id]_[测试开始时间戳]目录，如ps3_auto_test_prepare_14093_20210610175943，路径：
        # /home/test/ps3test/vms/vm204/ps3/test/esat/outputs/framework/
        cls.__init_outputs_job_directory()
        # 获取本次测试需要的测试脚本信息
        cls.__get_script_case_info()
        # @overwirte如果是长稳测试，则打乱csaelist顺序，并保存打乱结果
        cls.__get_shuffle_script_case_info()
        # @overwirte当日志trace参数为True时，获取ioc log磁盘大小，并重设日志循环写
        # cls.__set_ioc_node_log_poll_write()
        # 在日志服务器上初始化本次测试的日志保存路径，如：/home/framework/log/host_vm670_10.22.81.1_22/2021_06_11/16_03_12
        cls.__init_log_directory_in_log_server()
        # 初始化本次测试的bug, result的Excel文件
        cls.__init_test_bug_and_result_file()
        # 初始化测试报告日志文件，即：test/esat/outputs/framework/ps3_auto_test_prepare_5688_20210611160312/
        # report_log_20210611160312.log
        cls.__init_test_report_log_file()
        # 生成测试脚本日志文件夹, 即：test/esat/outputs/framework/ps3_auto_test_prepare_5688_20210611160312/
        # test_script_logs
        cls.__init_test_scripts_directory()
        # 创建/var/log/ioccore
        cls.__init_real_core_directory()

        cls.__init_cli_log_sh_directory()
        # @overwirte如果是长稳测试，则保存打乱csaelist顺序结果至excel
        cls.__save_shuffle_script_case_to_excel()
        # 使能watchdog开关
        cls.__enable_watchdog()
        # 创建一个监测子进程
        cls.__start_subprocess()

        if cls.test_entry in [TestEntryStrEnum.SOC.value, TestEntryStrEnum.UEFI.value] or \
                cls.test_object in [constants.TEST_OBJECT_EXPANDER, constants.TEST_OBJECT_PCIE_SWITCH] or \
                cls.test_platform == TestPlatformEnum.SIMU_PLATFORM.value:
            pass
        else:
            # 定期检测vdbench/fio进程，启动iostat监测断流
            if 0 != cls.cut_off and (cls.way_of_iostat == 0 or not cls.hikos_disk_service):
                if cls.way_of_iostat == 1:
                    cmd = f'wc -l /root/ps3test/slow_disk_log.conf'
                    _, cls.slow_disk_conf_lines, _ = \
                        CommandOperation.execute_command_with_error(cmd, print_enable=False)
                    log.info('slow disk lines is {}'.format(cls.slow_disk_conf_lines))
                    cls.iostat_proc = multiprocessing.Process(target=cls.iostat_process_hikos)
                else:
                    cls.iostat_proc = multiprocessing.Process(target=cls.iostat_process,
                                                              args=(cls.iostat_analysis,
                                                                    cls.iostat_log_full_path,
                                                                    cls.iostat_time))
                cls.iostat_proc.daemon = True
                cls.iostat_proc.start()
                cls.middle_layer_proc = multiprocessing.Process(target=cls.scsi_middle_layer_process)
                cls.middle_layer_proc.daemon = True
                cls.middle_layer_proc.start()
            # 定期硬复位
            if cls.driver_reset in ['soft_reset', 'hard_reset']:
                log.info(f"{cls.driver_reset} start ...")
                cls.reset_proc = multiprocessing.Process(target=cls.fio_reset)
                cls.reset_proc.daemon = True
                cls.reset_proc.start()

        cls.__chmod_env_conf()
        cls.__check_raid_core_before_test()

    @classmethod
    def __init_real_core_directory(cls):
        """
        物理环境创建core 文件夹并拷贝 readcore 工具
        author:      sunql
        date:        2022-04-09 10:15:30
        :return:
        """
        if constants.ENV_PLATFORM_REAL == cls.test_platform and \
                (cls.test_object == constants.TEST_OBJECT_EXPANDER or
                 cls.test_object == constants.TEST_OBJECT_PCIE_SWITCH) or \
                cls.test_entry == TestEntryStrEnum.UEFI.value:
            # do nothing, add by hejf,20220411
            return
        if cls.test_platform != constants.ENV_PLATFORM_REAL:
            return

        rtn_code = FileOperation.make_directory(dir_name=libs_constants.LOG_COLL_HOST_CORE_FILE_PATH,
                                                ip=cls.host_ip, match_flag=False, delete_flag=False)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            target_file_path = f"{libs_constants.LOG_COLL_HOST_CORE_FILE_PATH}"
            rtn_code = FileOperation.scp_file(source_file_path='/home/ps3Tools/read_vmcore /home/ps3Tools/devmset',
                                              target_file_path=target_file_path, local_execute=True,
                                              target_ip=cls.host_ip, clear_target_file=False)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f"init {libs_constants.LOG_COLL_HOST_CORE_FILE_PATH} success")
            # 调整read_vmcore 执行权限
            cmd = f"chmod +x {target_file_path}read_vmcore {target_file_path}devmset"
            CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd,
                                                                         ssh_ip=cls.host_ip,
                                                                         ssh_port=cls.host_port)
        else:
            log.error(f"init {libs_constants.LOG_COLL_HOST_CORE_FILE_PATH} fail")
            exit(1)

    @classmethod
    def __init_cli_log_sh_directory(cls):
        """
        生成 批量执行 cli 命令生产日志需要的文件夹及拷贝批量执行脚本
        author:      sunql
        date:        2022-04-09 10:15:30
        :return:
        """
        if constants.ENV_PLATFORM_REAL == cls.test_platform and \
                (cls.test_object == constants.TEST_OBJECT_EXPANDER or
                 cls.test_object == constants.TEST_OBJECT_PCIE_SWITCH) or \
                cls.test_entry == TestEntryStrEnum.UEFI.value:
            # do nothing, add by hejf,20220411
            return
        if cls.test_platform != constants.ENV_PLATFORM_REAL:
            return

        rtn_code = FileOperation.make_directory(dir_name=libs_constants.LOG_COLL_HOST_CLI_EXCE_PATH,
                                                ip=cls.host_ip, match_flag=False, delete_flag=True)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            target_file_path = f"{libs_constants.LOG_COLL_HOST_CLI_EXCE_PATH}"
            rtn_code = FileOperation.scp_file(source_file_path='/home/ps3Tools/exec_cli_to_log.sh',
                                              target_file_path=target_file_path, local_execute=True,
                                              target_ip=cls.host_ip, clear_target_file=False)
            rtn_code = FileOperation.scp_file(source_file_path='/home/ps3Tools/cs100_exec_cli_to_log.sh',
                                              target_file_path=target_file_path, local_execute=True,
                                              target_ip=cls.host_ip, clear_target_file=False)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info(f"init {libs_constants.LOG_COLL_HOST_CLI_EXCE_PATH} success")
            # 调整exec_cli_to_log.sh 执行权限
            cmd = f"chmod +x {libs_constants.LOG_COLL_HOST_CLI_EXCE_PATH}exec_cli_to_log.sh"
            CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd,
                                                                         ssh_ip=cls.host_ip,
                                                                         ssh_port=cls.host_port)
            cmd = f"chmod +x {libs_constants.LOG_COLL_HOST_CLI_EXCE_PATH}cs100_exec_cli_to_log.sh"
            CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd,
                                                                         ssh_ip=cls.host_ip,
                                                                         ssh_port=cls.host_port)
        else:
            log.error(f"init {libs_constants.LOG_COLL_HOST_CLI_EXCE_PATH} fail")
            exit(1)

    @classmethod
    def __exec_cli_to_log(cls) -> None:
        """
        执行 cli 批量执行脚本并生产日志
        :return:
        """

        if constants.ENV_PLATFORM_REAL == cls.test_platform and \
                (cls.test_object == constants.TEST_OBJECT_EXPANDER or
                 cls.test_object == constants.TEST_OBJECT_PCIE_SWITCH) or \
                cls.test_entry == TestEntryStrEnum.UEFI.value:
            # do nothing, add by hejf,20220411
            return

        if cls.test_platform != constants.ENV_PLATFORM_REAL:
            return

        version = ControllerOperation.get_product_version()
        log.info(f"product version is {version}")

        exec_file = "exec_cli_to_log.sh"
        if version != 'es100':
            exec_file = "cs100_exec_cli_to_log.sh"

        now = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
        log_file = f"{libs_constants.LOG_COLL_HOST_CLI_EXCE_PATH}exec_cli_{now}.log"
        sh_script = f"{libs_constants.LOG_COLL_HOST_CLI_EXCE_PATH}{exec_file}"
        cmd = f"{sh_script} >> {log_file}"
        rc, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd,
                                                                                    ssh_ip=cls.host_ip,
                                                                                    ssh_port=cls.host_port)
        if rc != RtnStatusEnum.SUCCESS.value:
            log.error(f"exec {sh_script} fail")
            # exit(1)

    @classmethod
    def __modify_log_directory_in_log_server(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 10:15:30
        description: 修改日志服务器上当前测试日志目录的访问权限

        :return:     None
        """
        # 修改日志服务器上收集到的日志的访问者权限
        log.info("Will modify log directory access authority in log server.")
        cls.collect_log.modify_log_permission(cls.log_server_path)

    @classmethod
    def __get_test_total_time(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 10:20:00
        description: 获取本次测试的总时长，单位为秒

        :return:     None
        """
        # 测试结束时间戳
        test_end_timestamp, _ = CommandOperation.get_time()
        cls.test_total_seconds = int((test_end_timestamp - cls.test_start_timestamp) / constants.TIME_RATIO)

    @classmethod
    def __make_test_report_file(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 10:41:11
        description: 生成test/esat/outputs/framework/ps3_auto_test_prepare_5688_20210611160312/reports/
                     ps3_auto_test_prepare_5688_20210611160312_report.xlsx

        :return:     None
        """
        # 获取create_report_excel.py的绝对路径
        log.info(constants.REPORT_CREATE_START)
        create_report_script_path = report_excel_create.get_current_absolute_path()
        if not cls.__isvalid(create_report_script_path):
            log.error(constants.REPORT_PATH_FAIL % create_report_script_path)
            exit(1)

        # 生成测试报告
        cls.test_report_excel_file_path = utils.make_test_report_file(
            create_report_script_path, cls.test_start_time, str(cls.test_total_seconds),
            cls.test_bug_excel_file_path, cls.test_result_excel_file_path, cls.test_report_log_file_path)
        if not cls.__isvalid(cls.test_report_excel_file_path):
            log.error(constants.REPORT_CREATE_FAIL)
            exit(1)
        log.info(constants.REPORT_CREATE_SUC)

    @classmethod
    def __close_subprocess(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 10:57:28
        description: 关闭测试前创建的子进程

        :return:     None
        """
        if (cls.monitor_process is not None) and cls.monitor_process.is_alive():
            cls.monitor_process.terminate()
            log.info('Success to close subprocess.')

    @classmethod
    def __close_mv_log_proc(cls):
        """
        关闭测试前创建的mv_log_proc进程
        author:sunql
        :return:
        """
        if cls.mv_log_proc is not None and cls.mv_log_proc.is_alive():
            cls.mv_log_proc.terminate()
            log.info('Success to close mv log process.')

    @classmethod
    def process_test_result(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 10:12:41
        description: 测试结果处理

        :return:     None
        """
        # 修改日志服务器上当前测试日志目录的访问权限
        cls.__modify_log_directory_in_log_server()
        # 获取本次测试任务的总时长，单位为秒
        cls.__get_test_total_time()
        # 创建本次测试报告Excel文件，即test/esat/outputs/framework/ps3_auto_test_prepare_5688_20210611160312/reports/
        #                          ps3_auto_test_prepare_5688_20210611160312_report.xlsx
        cls.__make_test_report_file()

        # 修改 result excel 文件名 增加版本信息
        old_test_result_excel_file_path = cls.test_result_excel_file_path
        cls.test_result_excel_file_path = cls.test_result_excel_file_path.split('.')
        cls.test_result_excel_file_path[0] += f"_{cls.cli_commit_id}_{cls.cli_branch}"
        cls.test_result_excel_file_path = '.'.join(cls.test_result_excel_file_path)
        os.rename(old_test_result_excel_file_path, cls.test_result_excel_file_path)
        log.info(f"test_result_excel_file_path:{cls.test_result_excel_file_path}")
        # 关闭测试前创建的子进程
        cls.__close_subprocess()
        # 关闭测试前创建的iostat进程
        if 0 != cls.cut_off and (cls.iostat_proc is not None) and cls.iostat_proc.is_alive():
            cls.iostat_proc.terminate()
            log.info('Success to close iostat process.')
        # 关闭测试前创建的中层监控进程
        if 0 != cls.cut_off and (cls.middle_layer_proc is not None) and cls.middle_layer_proc.is_alive():
            cls.middle_layer_proc.terminate()
            log.info('Success to close middle layer process.')
        # 关闭测试前创建的mv_log_proc进程
        cls.__close_mv_log_proc()
        # 关闭测试前创建的reset_proc进程
        if cls.reset_proc is not None and cls.reset_proc.is_alive():
            cls.reset_proc.terminate()
            log.info('Success to close reset process.')

    @classmethod
    def simulator_node_reset_with_result(cls, reset_type="default") -> bool:
        """
        author: panapn.du
        date  : 2020.10.22
        description: 执行重启节点
        :return: 重启节点,最多尝试2次,重启失败，结束测试

        @changelog      2021-02-27 09:46:21  haibin.xu
                        1. 作为类方法并入RunAllTestPs3类
        """
        result = False
        if constants.ENV_PLATFORM_SIMU == cls.test_platform:
            if (constants.ENV_TEST_ENTRY_IOC == cls.test_entry) and (
                    constants.ENV_TEST_OBJECT_EXPANDER == cls.test_object):
                log.info('Call script exp_simu_open.py to reset simulator...')
                result = ExpanderSimuStart.reset()
            elif constants.ENV_TEST_OBJECT_PCIE_SWITCH == cls.test_object:
                log.info('Call script sw_simu_open.py to reset simulator...')
                result = PcieSwitchSimuStart.reset()
            else:
                script_path = constants.HOST_IOC_RESET_FILE_PATH
                log.info("Simulator is resetting...")
                for i in range(2):
                    result = utils.simulator_restart(cls.test_bug_excel_file_path, cls.test_result_excel_file_path,
                                                     script_path, cls.host_ip, cls.host_port)
                    if result:
                        break
        else:
            script_path = "simulation/real_host_reset.py"

            if reset_type == 'hba_release_core':
                script_path = "simulation/real_hba_release_reset.py"

            log.info("real host is resetting...")
            result = utils.simulator_restart(cls.test_bug_excel_file_path, cls.test_result_excel_file_path,
                                             script_path, cls.host_ip, cls.host_port)
        return result

    @classmethod
    def __get_current_memory(cls) -> int:
        """
        author:      haibin.xu
        date:        2021-05-12 17:18:07
        description: 获取当前内存占用

        :return:     返回内存占用
        """
        if cls.test_object == TestObjectStrEnum.EXPANDER.value:
            # 非模拟平台环境
            if cls.test_platform != constants.ENV_PLATFORM_SIMU:
                return -1

        if cls.test_entry == TestEntryStrEnum.UEFI.value:
            return -1

        if (not cls.pcie_switch_flag) and (not cls.expander_flag):
            memory_before_test = CustomOperation.get_current_memory(controller_id=libs_constants.X16_CONTROLLER)
        else:
            # 单独expander 或 pcie switch测试时，不统计已分配内存
            memory_before_test = -1

        if 0 < memory_before_test:
            log.info('Get current allocated total memory : {} Bytes'.format(memory_before_test))
        else:
            log.warning('Failed to get current allocated total memory, Maybe not need to get or failed to get.')

        return memory_before_test

    @classmethod
    def __get_host_ioc_node(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-13 22:12:40
        description: 获取host,ioc节点信息

        :return:      None
        """
        if (cls.host_node_name is None) or (cls.ioc_node_name is None):
            cls.host_node_name, _, cls.ioc_node_name, cls.ioc_node_id, _ = HostOperation.get_node_name_id()

    @classmethod
    def __flush_log(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-05-12 17:27:47
        description: 刷新log

        :return:     None
        """

        if cls.test_entry == TestEntryStrEnum.UEFI.value:
            return

        # 非模拟平台环境
        if cls.test_platform != constants.ENV_PLATFORM_SIMU and \
                cls.test_object != TestObjectStrEnum.EXPANDER.value and \
                cls.test_object != TestObjectStrEnum.PCIE_SWITCH.value:
            CustomOperation.tigger_dump_log(controller_id=libs_constants.X16_CONTROLLER)
            if not ControllerOperation.check_trigger_dump_log(controller_id=libs_constants.X16_CONTROLLER):
                cls.bug_stop = True
                cls.bug_existed_flag = True
                log.error("trigger dump log fail, test stop ")
            return

        # 单独expander 或 pcie switch 或前端测试时，不刷新log
        if (not cls.pcie_switch_flag) and (not cls.expander_flag) and \
                (CompileObjectStrEnum.FRONTEND.value != cls.compile_object):
            cls.__get_host_ioc_node()
            flush_host, flush_ioc = HostOperation.flush_log(cls.host_node_name, cls.ioc_node_name)
            if RtnStatusEnum.SUCCESS.value == flush_host:
                log.info('Success to flush host qemu log.')
            else:
                log.error('Fail to flush host qemu log.')
            if RtnStatusEnum.SUCCESS.value == flush_ioc:
                log.info('Success to flush ioc qemu log.')
            else:
                log.error('Fail to flush ioc qemu log.')

    @classmethod
    def __get_scripts_directory(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 11:30:49
        description: 获取脚本所在的scripts目录，即/test/esat/scripts目录

        :return:     None
        """
        cls.scripts_directory = CommandOperation.format_linux_path_sep(constants.SCRIPTS_DIRECTORY)
        log.info('scripts common directory: {}'.format(cls.scripts_directory))

    @classmethod
    def __handle_script_test_result_info(cls, script_name: str = None, result_type: str = None,
                                         script_info_list: list = None, result_file: str = None,
                                         script_test_output: str = None) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 14:33:23
        description: 处理单个脚本测试结果信息，即将脚本的测试结果信息写到result excel文件中

        :param script_name: 脚本名
        :param result_type: 脚本状态类型
        :param script_info_list: 脚本信息
        :param result_file: result excel文件路径
        :param script_test_output: 脚本测试输出信息
        :return:    None
        """
        handle_result_flag = True
        if constants.SCRIPT_CASE_NON_EXIST == result_type:
            # 没有脚本测试信息
            log.error(constants.CASE_NOT_EXIST_INFO % script_name)
            cls.not_exist_num += 1
        elif constants.SCRIPT_NON_EXIST == result_type:
            # 有脚本测试信息，但是脚本不存在
            log.error(constants.SCRIPT_NOT_EXIST_INFO % script_name)
            cls.not_exist_num += 1
        elif constants.REPORT_COL_SCRIPT_SKIP == result_type:
            # cli 部署ip连接失败
            log.error(constants.PING_CMD_FAIL_INFO % script_name)
            cls.skip_num += 1
        elif 'framework' == result_type:
            # framework发现bug时使用
            pass
        else:
            handle_result_flag = False

        if handle_result_flag:
            # 将测试结果信息写到result excel文件中
            utils.handle_result_info(script_info_list, result_file, script_test_output, result_type)

    @classmethod
    def __check_deploy_ip(cls, check_fail_times: int = 0) -> int:
        """
        author:      haibin.xu
        date:        2021-06-12 15:19:34
        description: 检查部署cli服务器ip是否正常连接

        :param check_fail_times: 已检查失败的次数
        :return:     返回连接失败的次数
        """
        # 如果是uefi环境不检查
        if cls.test_entry == TestEntryStrEnum.UEFI.value:
            return 0

        is_ping = False
        if 'windows' in cls.host_os:
            is_ping = True

        if RtnStatusEnum.SUCCESS.value == CommandOperation.check_ip_connect(ip=cls.cli_deploy_ip, is_ping=is_ping):
            check_fail_times = 0
        else:
            check_fail_times += 1

        return check_fail_times

    @classmethod
    def __get_expander_devsn(cls) -> tuple:
        """
        author:      haibin.xu
        date:        2021-07-22 17:42:31
        description: 获取指定expander的devSn列表

        :return:     返回指定expander的devSn列表
        """
        exp_devsn = []
        expander_env_pattern = r'expander_Env{}_(.*)'.format(cls.expander_env_id)
        rtn_code, stdout = CommandOperation.get_process_data(process_kwname='Env{}'.format(cls.expander_env_id),
                                                             ssh_ip=cls.ioc_ip, column_list=['NF'])
        if RtnStatusEnum.SUCCESS.value == rtn_code:
            exp_devsn = re.findall(expander_env_pattern, stdout)

        if isinstance(exp_devsn, list) and (1 < len(exp_devsn)):
            rtn_code = RtnStatusEnum.SUCCESS.value
        else:
            rtn_code = RtnStatusEnum.FAIL.value
            exp_devsn = []

        return rtn_code, exp_devsn

    @classmethod
    def __expander_gcov(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-08-09 19:24:59
        description: expander 覆盖率版本测试时，需要执行expander 自己的gcov方法

        :return: None
        """
        if cls.gcov_flag and ((TestObjectStrEnum.EXPANDER.value == cls.test_object) or
                              (CompileObjectStrEnum.EXPANDER.value == cls.compile_object)):
            if not cls.__isvalid(cls.expander_devsn):
                _, cls.expander_devsn = cls.__get_expander_devsn()
            if TestEntryStrEnum.SOC.value == cls.test_entry:
                exp_simu_host_file_path = CommandOperation.format_linux_path_sep(os.path.join(
                    libs_constants.EXPANDER_CLI_ROOT, str(cls.expander_port)))
            else:
                cls.__get_host_ioc_node()
                exp_simu_host_file_path = CommandOperation.format_linux_path_sep(os.path.join(
                    libs_constants.IOC_WORK_PATH, libs_constants.IOC_EXPANDER_PATH.format(cls.ioc_node_id)))

            if RtnStatusEnum.SUCCESS.value == CustomOperation.expander_gcov(
                    execute_script_path=exp_simu_host_file_path, exp_devsn_list=cls.expander_devsn,
                    ssh_ip=cls.ioc_ip):
                log.info('Expander gcover version, success to execute gcov command')
            else:
                log.warning('Expander gcover version, fail to execute gcov command')

    @classmethod
    def __get_gcov(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 15:33:51
        description: 覆盖率版本测试时，需执行命令cli /c0 custom mgr gcov

        :return:     None
        """
        if cls.test_entry == TestEntryStrEnum.UEFI.value:
            return

        if cls.gcov_flag:
            if (TestObjectStrEnum.EXPANDER.value != cls.test_object) and \
                    (CompileObjectStrEnum.EXPANDER.value != cls.compile_object):
                if RtnStatusEnum.SUCCESS.value == CustomOperation.get_gcov_info():
                    log.info('Gcover version, success to execute command: *cli /c* custom mgr gcov')
                else:
                    log.warning('Gcover version, fail to execute command: *cli /c* custom mgr gcov')
            else:
                cls.__expander_gcov()

    @classmethod
    def __get_paramters_before_script_test(cls) -> tuple:
        """
        author:      haibin.xu
        date:        2021-06-12 15:53:22
        description: 获取脚本测试前的一些参数

        :return:     返回脚本开始时间戳，开始时间，测试前的内存占用等
        """
        # 脚本开始执行时间戳
        start_timestamp, start_time = CommandOperation.get_time(time_format='%Y-%m-%d %H:%M:%S')
        # 统计测试前已分配内存
        memory_before_test = cls.__get_current_memory()

        return start_timestamp, start_time, memory_before_test

    @classmethod
    def __get_paramters_after_script_test(cls, memory_before_test: float, start_timestamp: float) -> tuple:
        """
        author:      haibin.xu
        date:        2021-06-12 16:14:21
        description: 获取脚本测试后的一些参数

        :return:     返回脚本结束时内存占用差值，脚本测试前后时间
        """
        # 统计测试后已分配内存
        memory_after_test = cls.__get_current_memory()
        # 统计测试前后内存差值
        memory_delta = memory_after_test - memory_before_test
        # 测试脚本执行时长
        time_duration = round(float(time.time() - start_timestamp), constants.DURATION_ROUND_BIT)

        return memory_delta, time_duration

    @classmethod
    def __check_real_hba_debug_crash_core_files(cls, core_crash_code: int = None,
                                                test_break_flag: bool = False) -> tuple:
        """
        hba卡debug版本获取core
        author:      haibin.xu
        :param core_crash_code:
        :param test_break_flag:
        :return: core_crash_code，test_break_flag
        """
        log.info("check real hba debug core files start ...")
        cmd_code = FileOperation.make_directory(dir_name=libs_constants.LOG_COLL_HOST_CORE_FILE_PATH,
                                                ip=cls.host_ip, match_flag=False, delete_flag=False)
        if RtnStatusEnum.SUCCESS.value == cmd_code:
            # 生成core
            now = time.time()
            cmd = f"cd {libs_constants.LOG_COLL_HOST_CORE_FILE_PATH};./read_vmcore core_dump_{now}.log"
            cmd_code, cmd_output, cmd_stderr = \
                CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd, ssh_ip=cls.host_ip)
            log.info(f"hba debug core find output:{cmd_output}")
        # 如果命令执行成功
        if cmd_code in [255, 0]:
            # 没有core
            if len(cmd_output) and 'not found vmcore' in str(cmd_output).lower():
                CustomOperation.tigger_dump_log(ssh_ip=cls.host_ip, controller_id=libs_constants.X16_CONTROLLER)
                time.sleep(30)
            # 有core
            else:
                core_file_path = f"{libs_constants.LOG_COLL_HOST_CORE_FILE_PATH}core_dump_{now}.log"
                core_crash_code = constants.RETURN_CODE_FAIL
                core_get_flag = False
                # 循环获取core文件
                for i in range(10):
                    time.sleep(30)
                    if FileOperation.file_path_exists(core_file_path, ip=cls.host_ip) == RtnStatusEnum.SUCCESS.value:
                        core_get_flag = True
                        break
                # 有core但是没有拿到，停止测试
                if not core_get_flag:
                    test_break_flag = True
                    cls.bug_stop = True
                    cls.bug_existed_flag = True
                    log.error(f"core dump output is None,but not find file: {core_file_path} ..., test stop")
                else:
                    log.info(f"core file is find,path: {core_file_path} ...")
                    cmd = f"cd {libs_constants.LOG_COLL_HOST_CORE_FILE_PATH};./devmset 0x180000000 0 1 32"
                    CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd, ssh_ip=cls.host_ip)

        else:
            log.error(f"read_vmcore exec  error, test stop")
            # 保留环境
            test_break_flag = True
            cls.bug_stop = True
            cls.bug_existed_flag = True

        return test_break_flag, core_crash_code

    @classmethod
    def __check_real_hba_debug_crash_core_files_new(cls, core_crash_code: int = None,
                                                    test_break_flag: bool = False) -> tuple:
        """
        hba卡debug版本获取core,串口连接交换机时
        author:      haibin.xu
        :param core_crash_code:
        :param test_break_flag:
        :return: core_crash_code，test_break_flag
        """
        log.info("check real hba debug core files start ...")
        if CommandOperation.check_cli_core(cls.comhost_ip, cls.a72_com,
                                           cls.log_server_account, cls.log_server_ip):
            CommandOperation.clean_cli_core_file(cls.comhost_ip, cls.a72_com,
                                                 cls.log_server_account, cls.log_server_ip)
        else:
            return test_break_flag, core_crash_code

        cmd_code = FileOperation.make_directory(dir_name=libs_constants.LOG_COLL_HOST_CORE_FILE_PATH,
                                                ip=cls.host_ip, match_flag=False, delete_flag=False)
        if RtnStatusEnum.SUCCESS.value == cmd_code:
            # 生成core
            now = time.time()
            cmd = f"cd {libs_constants.LOG_COLL_HOST_CORE_FILE_PATH};./read_vmcore core_dump_{now}.log"
            cmd_code, cmd_output, cmd_stderr = \
                CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd, ssh_ip=cls.host_ip)
            log.info(f"hba debug core find output:{cmd_output}")
        # 如果命令执行成功
        if cmd_code in [255, 0]:
            # 没有core
            if len(cmd_output) and 'not found vmcore' in str(cmd_output).lower():
                CustomOperation.tigger_dump_log(ssh_ip=cls.host_ip, controller_id=libs_constants.X16_CONTROLLER)
                time.sleep(30)
            # 有core
            else:
                core_file_path = f"{libs_constants.LOG_COLL_HOST_CORE_FILE_PATH}core_dump_{now}.log"
                core_crash_code = constants.RETURN_CODE_FAIL
                core_get_flag = False
                # 循环获取core文件
                for i in range(10):
                    time.sleep(30)
                    if FileOperation.file_path_exists(core_file_path, ip=cls.host_ip) == RtnStatusEnum.SUCCESS.value:
                        core_get_flag = True
                        break
                # 有core但是没有拿到，停止测试
                if not core_get_flag:
                    test_break_flag = True
                    cls.bug_stop = True
                    cls.bug_existed_flag = True
                    log.error(f"core dump output is None,but not find file: {core_file_path} ..., test stop")
                else:
                    log.info(f"core file is find,path: {core_file_path} ...")
                    cmd = f"cd {libs_constants.LOG_COLL_HOST_CORE_FILE_PATH};./devmset 0x180000000 0 1 32"
                    CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd, ssh_ip=cls.host_ip)
        else:
            log.error(f"read_vmcore exec  error:{cmd_code} \n {cmd_output} \n {cmd_stderr}, test stop")
            # 保留环境
            test_break_flag = True
            cls.bug_stop = True
            cls.bug_existed_flag = True

        return test_break_flag, core_crash_code

    @classmethod
    def __check_real_hba_release_crash_core_files(cls, core_crash_code: int = None,
                                                  test_break_flag: bool = False) -> tuple:
        """
        hba卡release版本获取core
        author:      haibin.xu
        :param core_crash_code:
        :param test_break_flag:
        :return: core_crash_code，test_break_flag
        """
        log.info("check real hba release core files start ...")
        check_cli = cls.__check_cli_execute()
        stop_flag = False
        if check_cli:
            CustomOperation.tigger_dump_log(ssh_ip=cls.host_ip, controller_id=libs_constants.X16_CONTROLLER)
            time.sleep(30)
        else:
            core_crash_code = constants.RETURN_CODE_FAIL
            # 查找core
            _, log_path = HostOperation.get_real_host_com_screen(ssh_ip=cls.comhost_ip, com=cls.a72_com,
                                                                 com_keywords=constants.TEST_CONFIG_A72)
            core_keywords = ['Beginning of core dump', 'End or core dump']
            if FileOperation.find_keywords_with_file(path=log_path, ip=cls.comhost_ip, keywords=core_keywords):
                core_crash_code = constants.RETURN_CODE_FAIL
                # 重启节点
                reset_flag = cls.simulator_node_reset_with_result('hba_release_core')
                if not reset_flag:
                    # 重启失败,停止测试
                    stop_flag = True
                    log.info(constants.RESTART_SIMULATOR_FAILED)
                else:
                    # 重启后再次切割com口a72日志
                    cls.split_real_com_log()
        if stop_flag:
            # 保留环境
            test_break_flag = True
            cls.bug_stop = True
            cls.bug_existed_flag = True

        log.info("check real hba release core files end ...")

        return test_break_flag, core_crash_code

    @classmethod
    def __check_real_hba_release_crash_core_files_new(cls, core_crash_code: int = None,
                                                      test_break_flag: bool = False) -> tuple:
        """
        hba卡release版本获取core 串口连接交换机时
        author:      haibin.xu
        :param core_crash_code:
        :param test_break_flag:
        :return: core_crash_code，test_break_flag
        """
        log.info("check real hba release core files start ...")
        if CommandOperation.check_cli_core(cls.comhost_ip, cls.a72_com,
                                           cls.log_server_account, cls.log_server_ip):
            CommandOperation.clean_cli_core_file(cls.comhost_ip, cls.a72_com,
                                                 cls.log_server_account, cls.log_server_ip)
        else:
            return test_break_flag, core_crash_code

        core_crash_code = constants.RETURN_CODE_FAIL

        check_cli = cls.__check_cli_execute()
        stop_flag = False
        if check_cli:
            # 导出core
            if HostOperation.hba_release_core_dump_log(controller_id=libs_constants.X16_CONTROLLER,
                                                       ssh_ip=cls.host_ip) == RtnStatusEnum.SUCCESS.value:
                log.info("hba release core dump log success")
                if CustomOperation.tigger_dump_log(controller_id=libs_constants.X16_CONTROLLER,
                                                   ssh_ip=cls.host_ip) == RtnStatusEnum.SUCCESS.value:
                    time.sleep(30)
                else:
                    stop_flag = True
                    log.error('custom tigger dump log fail, test stop')
            else:
                stop_flag = True
                log.error('hba release core dump log fail, test stop')

        else:
            reset_flag = cls.simulator_node_reset_with_result('hba_release_core')
            if not reset_flag:
                # 重启失败,停止测试
                stop_flag = True
                log.info(constants.RESTART_SIMULATOR_FAILED)
        if stop_flag:
            # 保留环境
            test_break_flag = True
            cls.bug_stop = True
            cls.bug_existed_flag = True

        log.info("check real hba release core files end ...")

        return test_break_flag, core_crash_code

    @classmethod
    def check_core_dump_done(cls, file_path):
        """
        core 文件大小不再变化时，认为core dump 完成
        :param file_path:
        :return:
        """

        cmd = f"du -s {file_path}" + r" | awk '{print $1}'"
        size = 0
        for i in range(300):
            _, out, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, ssh_ip=cls.host_ip,
                                                                                     ssh_port=cls.host_port)
            if 'No such file or directory' not in out:
                out = int(out)
                if out == size and out > 10:
                    break
                size = out
            time.sleep(3)

        return size

    @classmethod
    def __check_raid_core_before_test(cls):
        """
        raid 环境开始测试前清理 ioc 内 core
        :return:
        """
        if cls.test_object != constants.TEST_OBJECT_RAID:
            return

        log.info(f"check raid core before test start ...")

        socket_core_list = RaidSocketOption.get_raid_core_path_list(cls.comhost_ip, cls.a72_com)
        log.info(f"connect socket , find old raid core file list: {socket_core_list}")
        for socket_core in socket_core_list:
            if socket_core not in cls.raid_core_list:
                cls.raid_core_list.append(socket_core)

    @classmethod
    def __get_raid_core(cls) -> tuple:
        """
        获取raid core
        :return: 是否继续测试，是否有core
        """
        if 'dev' in cls.a72_com or not len(cls.a72_com):
            log.error("mini com config error,test stop ...")
            return False, False

        socket_core_list = RaidSocketOption.get_raid_core_path_list(cls.comhost_ip, cls.a72_com)
        log.info(f"connect socket , find raid core file list: {socket_core_list}")

        log.info(f"core list before check:{cls.raid_core_list}")

        # 判断socket 获取的的core 是否为新文件
        new_core_flag = False
        for socket_core in socket_core_list:
            if socket_core not in cls.raid_core_list:
                new_core_flag = True
                cls.raid_core_list.append(socket_core)

        log.info(f"core list after check:{cls.raid_core_list}")
        # 串口内未找到 core
        if not len(socket_core_list) or not new_core_flag:
            log.info("connect socket, not find new raid core ...")
            return True, False

        core_dump_flag = False
        # 查看 coredump 是否完成
        for i in range(10):
            if not RaidSocketOption.check_coredump_proc(cls.comhost_ip, cls.a72_com):
                core_dump_flag = True
                break
            time.sleep(60)

        # ioc 生成core进程没有在10分中内结束
        if not core_dump_flag:
            log.error("core gz process more than 10 minutes, test stop ...")
            return False, True

        # cli 不可用则进入串口操作
        if not cls.__check_cli_execute():
            # 掉电重启
            reset_flag = cls.simulator_node_reset_with_result()
            if not reset_flag:
                # 重启失败,停止测试
                log.error(" reset platform error,test stop ...")
                return False, True

            if not cls.__check_cli_execute():
                log.error("cli exec fail,test stop ...")
                return False, True

        # 导出前先记录/var/log 下已存在的core文件
        get_core_file_cmd = "ls -d /var/log/core*"
        _, old_core_list = FileOperation.get_files_with_cmd(find_files_cmd=get_core_file_cmd, ip=cls.host_ip)

        for path in old_core_list:
            path = path.strip()
            if 'core' in path and path not in cls.raid_core_list:
                cls.raid_core_list.append(path)

        # 导出core到/var/log
        rtn = CustomOperation.tigger_dump_log(controller_id=libs_constants.X16_CONTROLLER,
                                              ssh_ip=cls.host_ip, type='1')
        if rtn != RtnStatusEnum.SUCCESS.value:
            log.error("cli trigger dump fail,test stop ...")
            return False, True
        # 等待180秒
        time.sleep(180)

        # 判断 var log 下是否有新文件产生
        new_core_file = None
        get_core_file_cmd = "ls -d /var/log/core*"
        _, new_core_list = FileOperation.get_files_with_cmd(find_files_cmd=get_core_file_cmd, ip=cls.host_ip)
        for path in new_core_list:
            path = path.strip()
            if 'core' in path and path not in cls.raid_core_list:
                new_core_file = path
                cls.raid_core_list.append(path)

        # 如果/var/log下没有新的core文件生成，则 trigger dump 失败，停测
        if not new_core_file:
            log.error("cli trigger dump fail,test stop ...")
            return False, True

        # 判断 core文件 trigger dump 完成
        if not cls.check_core_dump_done(new_core_file):
            log.error("cli trigger dump fail,test stop ...")
            return False, True

        log.info(f"trigger dump raid core file:{new_core_file}")

        # 解析core
        ControllerOperation.get_raid_ioc_core(controller_id=libs_constants.X16_CONTROLLER)
        time.sleep(180)

        # 找到解析后的core文件
        new_core_list = []
        get_core_file_cmd = "ls -d /var/log/ioccore/core*"
        _, find_core_list = FileOperation.get_files_with_cmd(find_files_cmd=get_core_file_cmd, ip=cls.host_ip)
        for path in find_core_list:
            path = path.strip()
            if 'core' in path and path not in cls.raid_core_list:
                size = cls.check_core_dump_done(path)
                new_core_list.append({'path': path, 'size': size})

        log.info(new_core_list)

        success_num = 0
        for socket_core in socket_core_list:
            socket_core_file = socket_core.replace('/app', '')
            for new_core in new_core_list:
                if socket_core_file in new_core['path']:
                    socket_core_size = RaidSocketOption.get_file_size(socket_core)
                    log.info(f"{socket_core} size:{socket_core_size}")
                    if socket_core_size == new_core['size']:
                        success_num += 1
        log.info(success_num)

        if len(socket_core_list) != success_num:
            log.error("cli trigger dump fail,test stop ...")
            return False, True

        # 导出ioc
        if not ControllerOperation.get_raid_ioc(controller_id=libs_constants.X16_CONTROLLER):
            log.error("raid ioc file not export to /var/log/ioccore/,test stop ...")
            return False, True

        return True, True

    @classmethod
    def __check_crash_core_files(cls, script_rtn_code: int = None, script_rtn_output: str = None,
                                 rtn_code_list: list = None, test_break_flag: bool = False) -> tuple:
        """
        author:      haibin.xu
        date:        2021-06-12 16:48:39
        description: 检查crash,core文件

        :param script_rtn_code: 脚本测试返回码
        :param script_rtn_output: 脚本测试结果
        :param rtn_code_list: 返回码列表
        :return:     返回脚本返回码，以及检查crash/core文件返回码
        """
        log.info("check crash core files ...")
        core_crash_code = constants.RETURN_CODE_SUCCESS

        if cls.test_entry == TestEntryStrEnum.UEFI.value:
            return script_rtn_code, core_crash_code, test_break_flag, script_rtn_output

        if script_rtn_code in rtn_code_list:
            # core、crash的判断，目前只在模拟平台，test_entry不为ioc, test_object不为expander时才去检查
            if constants.ENV_PLATFORM_SIMU == cls.test_platform:
                core_crash_code, script_rtn_output = utils.check_simulator_crash_core(cls.collect_log,
                                                                                      script_rtn_output)

            # 物理环境
            if constants.ENV_PLATFORM_REAL == cls.test_platform:
                if cls.test_object == constants.TEST_OBJECT_EXPANDER or \
                        cls.test_object == constants.TEST_OBJECT_PCIE_SWITCH:
                    # 检查是否有core产生, add by hejf,20220319
                    core_flag = cls.collect_log.check_new_rtems_ioc_core_files(cls.host_ip)
                    if core_flag:
                        core_crash_code = constants.RETURN_CODE_FAIL
                        # 出core后等待60s再重新测试
                        time.sleep(60)
                #  如果是hba卡
                elif cls.test_object == constants.TEST_OBJECT_HBA:
                    if cls.cli_mode == 'debug':
                        if 'dev' not in cls.a72_com:
                            test_break_flag, core_crash_code = \
                                cls.__check_real_hba_debug_crash_core_files_new(core_crash_code, test_break_flag)
                        else:
                            test_break_flag, core_crash_code = \
                                cls.__check_real_hba_debug_crash_core_files(core_crash_code, test_break_flag)
                    elif cls.cli_mode in ['release', 'ocm_release', 'ocm_debug']:

                        if 'dev' not in cls.a72_com:
                            test_break_flag, core_crash_code = \
                                cls.__check_real_hba_release_crash_core_files_new(core_crash_code, test_break_flag)
                        else:
                            test_break_flag, core_crash_code = \
                                cls.__check_real_hba_release_crash_core_files(core_crash_code, test_break_flag)
                    else:
                        log.error("can not get cli build mode,test stop...")
                        test_break_flag = True
                        cls.bug_stop = True
                        cls.bug_existed_flag = True
                else:
                    test_flag, has_core = cls.__get_raid_core()
                    if has_core:
                        core_crash_code = constants.RETURN_CODE_FAIL

                    if not test_flag:
                        test_break_flag = True
                        cls.bug_stop = True
                        cls.bug_existed_flag = True

                # 检查linux os crash
                crash_flag = cls.collect_log.check_new_ioc_qemu_crash_files()

                # 添加物理平台core bug信息
                if core_crash_code == constants.RETURN_CODE_FAIL or crash_flag:
                    out_dict = utils.format_script_output(script_rtn_output)
                    core_crash_bug_dict = out_dict.get(constants.POST_RESULT)
                    if core_crash_code == constants.RETURN_CODE_FAIL and not crash_flag:
                        core_crash_bug_dict[constants.BUG_TITLE] = str(core_crash_bug_dict.get(
                            constants.BUG_TITLE, "")) + "物理平台出现core"
                        core_crash_bug_dict[constants.BUG_TYPE] = constants.DEFAULT_CORE_CRASH_BUG_TYPE
                        core_crash_bug_dict[constants.BUG_RESULT] = constants.DEFAULT_CORE_BUG_RESULT
                        core_crash_bug_dict[constants.BUG_EXPECT] = constants.DEFAULT_CORE_BUG_EXPECT
                    # 添加crash bug信息
                    elif core_crash_code != constants.RETURN_CODE_FAIL and crash_flag:
                        core_crash_bug_dict[constants.BUG_TITLE] = str(core_crash_bug_dict.get(
                            constants.BUG_TITLE, "")) + "物理平台出现crash"
                        core_crash_bug_dict[constants.BUG_TYPE] = constants.DEFAULT_CORE_CRASH_BUG_TYPE
                        core_crash_bug_dict[constants.BUG_RESULT] = constants.DEFAULT_CRASH_BUG_RESULT
                        core_crash_bug_dict[constants.BUG_EXPECT] = constants.DEFAULT_CRASH_BUG_EXPECT
                        log.info("The crash appears")
                    # 添加core crash 同时出现的信息
                    elif core_crash_code != constants.RETURN_CODE_FAIL and crash_flag:
                        core_crash_bug_dict[constants.BUG_TITLE] = str(core_crash_bug_dict.get(
                            constants.BUG_TITLE, "")) + "物理平台出现crash、core"
                        core_crash_bug_dict[constants.BUG_TYPE] = constants.DEFAULT_CORE_CRASH_BUG_TYPE
                        core_crash_bug_dict[constants.BUG_RESULT] = constants.DEFAULT_CORE_CRASH_BUG_RESULT
                        core_crash_bug_dict[constants.BUG_EXPECT] = constants.DEFAULT_CORE_CRASH_BUG_EXPECT

                    out_dict[constants.CORE_CRASH_RESULT] = core_crash_bug_dict
                    script_rtn_output = str(out_dict)
                    core_crash_code = constants.RETURN_CODE_FAIL

        # 脚本执行失败或者出现Core、Crash都将return_code更改为失败
        if constants.RETURN_CODE_FAIL in [script_rtn_code, core_crash_code]:
            script_rtn_code = constants.RETURN_CODE_FAIL
            # 如果是物理环境脚本失败后再次刷出日志,raid 上面已经 执行 过了
            if constants.ENV_PLATFORM_REAL == cls.test_platform and cls.test_entry != TestEntryStrEnum.UEFI.value:
                if cls.test_object in [TestObjectStrEnum.HBA.value]:
                    CustomOperation.tigger_dump_log(controller_id=libs_constants.X16_CONTROLLER,
                                                    ssh_ip=cls.host_ip)
                    time.sleep(30)

        return script_rtn_code, core_crash_code, test_break_flag, script_rtn_output

    @classmethod
    def __handle_script_return_code(cls, script_rtn_code: int = None, script_rtn_output: str = None,
                                    script_failed_times: int = None, index: int = None, result_object: object = None,
                                    script_info_list: list = None, script_name: str = None,
                                    script_break_flag: bool = None) -> tuple:
        """
        author:      haibin.xu
        date:        2021-06-12 17:09:39
        description: 处理测试返回码

        :param script_rtn_code: 脚本测试返回码
        :param script_rtn_output: 脚本测试结果
        :param script_failed_times: 脚本失败次数
        :param index:   当前脚本循环到第几次的索引
        :param result_object: result 对象
        :param script_info_list: 测试脚本信息
        :param script_name: 测试脚本名称
        :param script_break_flag: 脚本终止标志位
        :return:  返回测试终止标志位，ioc core文件存在标志位，ioc crash文件存在标志位，host crash文件是否存在标志位
        """
        if constants.RETURN_CODE_FAIL == script_rtn_code:
            script_failed_times += 1
            script_break_flag = False
            if index == 0:
                cls.fail_num += 1
                cls.g_bug_existed = True
        elif constants.RETURN_CODE_SUCCESS == script_rtn_code:
            cls.pass_num += 1
        elif constants.RETURN_CODE_TIMEOUT == script_rtn_code:
            if constants.ENV_PLATFORM_REAL != cls.test_platform:
                ssh_utils.create_pstack(ioc_port=cls.ioc_port, ioc_ip=cls.ioc_qemu_ip)
            cls.timeout_num += 1
            # @overwirte 临时方案先将timeout脚本数量并入failed数量中，后期timeout单独统计
            if index == 0:
                cls.fail_num += 1
            # @overwrite end
            cls.g_bug_existed = True
        elif constants.RETURN_CODE_EXCEPTION == script_rtn_code:
            cls.except_num += 1
        else:
            cls.skip_num += 1

        ioc_core_flag, ioc_crash_flag, host_crash_flag, collect_log_flag = utils.handle_script_return_code(
            cls.bug_object, result_object, cls.collect_log, script_rtn_code, script_rtn_output, script_info_list,
            cls.run_all_test_log_file, cls.test_script_log_directory, cls.test_bug_excel_file_path,
            cls.test_result_excel_file_path, script_name, script_failed_times)

        # 如果日志收集失败,停止测试
        if not collect_log_flag and cls.test_entry != TestEntryStrEnum.UEFI.value:
            # add by hejf,exp和pcieswitch允许日志采集失败，环境中会保留，不进行强制停止测试
            if cls.test_object == constants.TEST_OBJECT_EXPANDER or \
                    cls.test_object == constants.TEST_OBJECT_PCIE_SWITCH:
                log.warning(r"log collect fail,please attention...")
            else:
                log.error(r"log collect fail,test stop...")
                # if cls.test_object == constants.TEST_OBJECT_PCIE_SWITCH and cls.gcov_flag:
                #     cls.bug_stop = False
                # else:
                cls.bug_stop = True
                cls.bug_existed_flag = True
                collect_bug_title = cls.collect_log.bug_info.get('title')
                collect_log_steps = cls.collect_log.bug_info.get('test_steps')
                cls.__create_framework_bug({'title': f'日志收集失败：{collect_bug_title}', "type_name": "日志收集失败",
                                            'test_tool': 'cli', 'log_path': cls.log_server_path,
                                            'test_steps': collect_log_steps})

        return script_break_flag, script_failed_times, ioc_core_flag, ioc_crash_flag, host_crash_flag

    @classmethod
    def __check_cli_execute(cls) -> bool:
        """
        author:      haibin.xu
        date:        2021-07-06 11:56:15
        description: 检查cli 执行是否有no souch derive

        :return:     cli正常执行返回True, 异常返回False
        """
        rtn_cli_execute = True
        # 如果是 uefi 不验证
        if cls.test_entry == TestEntryStrEnum.UEFI.value:
            return rtn_cli_execute

        rtn_code, cli_cmd_output = ControllerOperation.check_cli_valid(controller_id=libs_constants.X16_CONTROLLER)
        if RtnStatusEnum.SUCCESS.value != rtn_code:
            for exp_info in libs_constants.ENVIRONMENT_EXCEPTION_LIST:
                if exp_info in cli_cmd_output:
                    log.error('Failed to execute cli command, found exception: {}.'.format(exp_info))
                    rtn_cli_execute = False
                    break

        return rtn_cli_execute

    @classmethod
    def __check_cli_success(cls) -> bool:
        """
        author:      sunql
        date:        2022-03-06 11:56:15
        description: 检查cli 执行是否正常

        :return:     cli正常执行返回True, 异常返回False
        """
        rtn_cli_execute = True

        rtn_code, cli_cmd_output = ControllerOperation.check_cli_valid(controller_id=libs_constants.X16_CONTROLLER)
        if RtnStatusEnum.SUCCESS.value != rtn_code:
            rtn_cli_execute = False
            log.error('Failed to execute cli command : {}.'.format(cli_cmd_output))

        return rtn_cli_execute

    @classmethod
    def __check_bug_stop(cls, script_rtn_code: int = None, rtn_code_list: list = None, script_path: str = None,
                         script_break_flag: bool = None, test_break_flag: bool = None) -> tuple:
        """
        author:      haibin.xu
        date:        2021-06-12 17:44:59
        description: 检查bug_stop参数, 设置test_break_flag， script_break_flag标志位

        :param script_rtn_code: 脚本测试返回码
        :param rtn_code_list: 返回码列表
        :param script_path: 脚本路径
        :param script_break_flag: 脚本终止标志位
        :param test_break_flag: 测试终止标志位
        :return:     返回test_break_flag， script_break_flag
        """

        def private_check_cli_execute():
            if cls.test_object in [constants.TEST_OBJECT_EXPANDER, constants.TEST_OBJECT_PCIE_SWITCH] or \
                    cls.test_entry == TestEntryStrEnum.UEFI.value:
                return True
            return cls.__check_cli_execute()

        log.info(f"bug_stop is: {cls.bug_stop},script_rtn_code is:{script_rtn_code}")
        if cls.bug_stop and ((script_rtn_code in rtn_code_list) or (not private_check_cli_execute())):
            log.info(constants.SCRIPT_BUG_STOP_INFO % script_path)
            # 设置整个终端测试任务为True
            test_break_flag = True
            # 跳出脚本循环
            script_break_flag = True
            # 不再进行下一轮测试
            cls.bug_existed_flag = True
        log.info(f"bug_stop is: {cls.bug_stop},bug_existed_flag is:{cls.bug_existed_flag}")
        return test_break_flag, script_break_flag

    @classmethod
    def __after_resset_clear(cls) -> bool:
        """
        sunql
        重启后环境清理：清理故障，删除vd,set ready
        :return: 故障清理成功 返回 true
        """
        log.info("clear error start ...")
        # haibin.xu 2023-01-05 17:17:04 modify: soc expander测试，直接返回
        if cls.test_entry == TestEntryStrEnum.SOC.value and cls.test_object == TestObjectStrEnum.EXPANDER.value:
            log.info('Expander test on soc, not need to clear error.')
            return True

        cmd = f"{libs_constants.PS3CLI64} /c{libs_constants.X16_CONTROLLER} /vall abort init"
        CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd, ssh_ip=cls.host_qemu_ip)
        cmd = f"{libs_constants.PS3CLI64} /c{libs_constants.X16_CONTROLLER} /eall/sall abort init"
        CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd, ssh_ip=cls.host_qemu_ip)
        disk_ids = []
        if constants.ENV_PLATFORM_REAL == cls.test_platform:
            pd_list = ControllerOperation.get_pd_info(controller_id=libs_constants.X16_CONTROLLER)
            if len(pd_list):
                for pd in pd_list:
                    disk_ids.append(pd.get('DID'))
        else:
            disk_ids = HostOperation.get_all_disk_id(ioc_node=cls.ioc_node_name)
        # 清理故障
        clear_err_flag = True
        try:
            if len(disk_ids):
                for did in disk_ids:
                    if RtnStatusEnum.SUCCESS.value != HostOperation. \
                            clean_disk_error(disk_id=did, ioc_node=cls.ioc_node_name):
                        clear_err_flag = False
                        log.error(f"clear  disks error  failed , did:{did}")
            else:
                clear_err_flag = False
                log.error("get disks id  failed")
        except Exception as e:
            log.error(e)
            clear_err_flag = False

        # 物理环境直接删除vd
        delete_code = VirtualDisk.del_all_vd_without_os(controller_id=libs_constants.X16_CONTROLLER,
                                                        os_vid=cls.os_vd_id)
        if RtnStatusEnum.SUCCESS.value == delete_code:
            log.info('Success to finish delete all vd info.\n')
        else:
            log.warning('Failed to delete all vd info.\n')
        # 仅hba set ready ，raid 有jbod 盘不能执行此操作
        if cls.test_object == TestObjectStrEnum.HBA.value:
            cmd = f"{libs_constants.PS3CLI64} /c{libs_constants.X16_CONTROLLER} /eall/sall set ready"
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=cmd, ssh_ip=cls.host_qemu_ip)
        cmd = f"{libs_constants.PS3CLI64} /c{libs_constants.X16_CONTROLLER} /fall del"
        CommandOperation.execute_command_based_paramiko_with_rtncode(
            cmd=cmd, ssh_ip=cls.host_qemu_ip)

        log.info("clear error end ...")

        return clear_err_flag

    @classmethod
    def __check_reset_host_ioc(cls, crash_core_check_code: int = None, ioc_core_flag: bool = None,
                               ioc_crash_flag: bool = None, host_crash_flag: bool = None,
                               script_break_flag: bool = True, test_break_flag: bool = False,
                               script_rtn_code: int = 0) -> tuple:
        """
        author:      haibin.xu
        date:        2021-06-13 09:16:28
        description: 检查环节是否需要重启

        :param crash_core_check_code: core/crash信息检查返回码
        :param ioc_core_flag: ioc core文件是否存在标志位
        :param ioc_crash_flag: ioc crash文件是否存在标志位
        :param host_crash_flag: host crash文件是否存在标志位
        :param script_break_flag: 脚本终止标志位
        :param test_break_flag: 测试终止标志位
        :param script_rtn_code: 脚本执行结果code
        :return: 返回test_break_flag， script_break_flag
        """
        if constants.ENV_PLATFORM_REAL == cls.test_platform and \
                (cls.test_object == constants.TEST_OBJECT_EXPANDER or
                 cls.test_object == constants.TEST_OBJECT_PCIE_SWITCH) or \
                cls.test_entry == TestEntryStrEnum.UEFI.value:
            # do nothing, add by hejf,20220319
            return test_break_flag, script_break_flag

        # 如果是windows os 不重启
        if 'windows' in cls.host_os:
            return test_break_flag, script_break_flag
        log.info(f"^^^^^^^^^^^^^^^^^{cls.bug_stop}-{cls.bug_existed_flag}-{test_break_flag}-{script_break_flag}")
        need_reset_flag = False
        stop_test_flag = False
        # 当用户配置bug不停止时
        if (not cls.bug_stop) and (cls.compile_object != CompileObjectStrEnum.BACKEND.value):
            # 如果是模拟平台不需要判断cli是否可以执行
            if cls.test_platform == TestPlatformEnum.SIMU_PLATFORM.value:
                need_reset_flag = True
                if crash_core_check_code == constants.RETURN_CODE_FAIL:
                    log.info('Found crash or core files, need to reset host ioc node.')
                elif ioc_core_flag:
                    log.info('Found ioc core files, need to reset host ioc node.')
                elif ioc_crash_flag:
                    log.info('Found ioc crash files, need to reset host ioc node.')
                elif host_crash_flag:
                    log.info('Found host crash files, need to reset host ioc node.')
                elif script_rtn_code == constants.RETURN_CODE_TIMEOUT:
                    # 尝试不重启：脚本超时后，仅清除后台任务及磁盘故障，nvme盘不处理
                    if cls.__check_cli_success():
                        cmd = f"{libs_constants.PS3CLI64} /c0 /vall abort init"
                        CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd, ssh_ip=cls.host_qemu_ip)
                        cmd = f"{libs_constants.PS3CLI64} /c0 /eall/sall abort init"
                        CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd, ssh_ip=cls.host_qemu_ip)
                        disk_ids = HostOperation.get_all_disk_id(ioc_node=cls.ioc_node_name)
                        # 清理故障
                        clear_err_flag = True
                        for did in disk_ids:
                            if RtnStatusEnum.SUCCESS.value != HostOperation. \
                                    clean_disk_error(disk_id=did, ioc_node=cls.ioc_node_name):
                                clear_err_flag = False
                        # 如果清理故障成功
                        if clear_err_flag:
                            delete_code = VirtualDisk.del_all_vd_without_os(libs_constants.X16_CONTROLLER,
                                                                            cls.os_vd_id)
                            if RtnStatusEnum.SUCCESS.value == delete_code:
                                log.info('Success to finish delete all vd info.\n')
                            else:
                                log.warning('Failed to delete all vd info.\n')
                            # 仅hba set ready ，raid 有jbod 盘不能执行此操作
                            if cls.test_object == TestObjectStrEnum.HBA.value:
                                cmd = f"{libs_constants.PS3CLI64} /c0 /eall/sall set ready"
                                CommandOperation.execute_command_based_paramiko_with_rtncode(
                                    cmd=cmd, ssh_ip=cls.host_qemu_ip)

                            cmd = f"{libs_constants.PS3CLI64} /c0 /fall del"
                            CommandOperation.execute_command_based_paramiko_with_rtncode(
                                cmd=cmd, ssh_ip=cls.host_qemu_ip)

                        # 磁盘故障清理成功并能执行cli命令，尝试不重启成功
                        if clear_err_flag and cls.__check_cli_success():
                            need_reset_flag = False
                    # 尝试不重启：end
                    # 尝试不重启失败
                    if need_reset_flag:
                        log.info(f'test script return code is {constants.RETURN_CODE_TIMEOUT},'
                                 f'need to reset host ioc node.')

                elif utils.is_simulator_need_restart():
                    log.info('Found pcie switch or expander or cli execute issue, need to reset host ioc node.')
                else:
                    need_reset_flag = False
                # 前面条件都不满足
                if CommandOperation.check_ip_connect(ip=cls.host_qemu_ip) != RtnStatusEnum.SUCCESS.value:
                    need_reset_flag = True
            # 如果是物理平台，需要判断cli是否可以执行
            else:
                # 出现crash，物理平台停止测试
                if host_crash_flag:
                    log.info('Found real platform crash files, test stop.')
                    stop_test_flag = True
                # 如果cli执行失败
                rtn_code, _ = ControllerOperation.check_cli_valid(controller_id=libs_constants.X16_CONTROLLER)
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    # 如果有core且testobj==hba，重启环境
                    if ioc_core_flag and cls.test_object == TestObjectEnum.HBA.value:
                        log.info('Found real platform core files, and cli exec fail，reset host.')
                        need_reset_flag = True
                    # 如果cli执行后是no sourch dervice
                    elif not cls.__check_cli_execute():
                        need_reset_flag = True
                    # 停止测试
                    else:
                        log.info('Not Found real platform core files or test obj is raid, '
                                 'and cli exec fail，test stop.')
                        stop_test_flag = True

        if need_reset_flag and not cls.bug_stop and not stop_test_flag:
            # 重启节点并设置继续测试标志
            reset_flag = cls.simulator_node_reset_with_result()
            if not reset_flag:  # 重启失败
                stop_test_flag = True
                log.info(constants.RESTART_SIMULATOR_FAILED)
            else:
                # 重启成功，如果是覆盖率版本，重新执行命令cli /c0 custom mgr gcov
                cls.__get_gcov()
                cls.__get_ioc_pid(force=True)
                if cls.test_platform == TestPlatformEnum.REAL_PLATFORM.value:
                    # 重启后再次切割com口a72日志
                    cls.split_real_com_log()
                    # 如果是物理平台，需要再收集一次日志
                    collect_flag, crash_collect_flag, core_collect_flag = cls.collect_log.collect_host_log_after_rest()
                    # 如果日志收集失败，保留环境，停止测试
                    if not collect_flag:
                        stop_test_flag = True
                        log.info('collect host log after rest fail,test stop...')

        if stop_test_flag:
            cls.bug_stop = True
            test_break_flag = True
            script_break_flag = True
            cls.bug_existed_flag = True
        elif not cls.bug_stop and script_rtn_code in [constants.RETURN_CODE_TIMEOUT,
                                                      constants.RETURN_CODE_FAIL, constants.RETURN_CODE_EXCEPTION]:
            # 重启成功后清理一次环境
            cls.__after_resset_clear()

        log.info(f"^^^^^^^^^^^^^^^^^{cls.bug_stop}-{cls.bug_existed_flag}-{test_break_flag}-{script_break_flag}")
        return test_break_flag, script_break_flag

    @classmethod
    def __check_stop_test(cls, cmd_output: str, test_break_flag, script_break_flag) -> tuple:
        log.info(f"check bug stop by cmd_output:{cmd_output}")
        if utils.parse_stop_test(cmd_output):
            test_break_flag = True
            script_break_flag = True
            cls.bug_existed_flag = True
            cls.bug_stop = True
        log.info(f"bug_stop is: {cls.bug_stop},bug_existed_flag is:{cls.bug_existed_flag}")
        return test_break_flag, script_break_flag

    @classmethod
    def clean_host_trace(cls) -> None:
        """
        清理host_trace文件夹
        :return:
        """
        FileOperation.make_directory(dir_name=libs_constants.HOST_TRACE_PATH,
                                     ip=cls.host_ip, port=cls.host_port, match_flag=False)

    @classmethod
    def print_sas_io(cls) -> None:
        """
        获取 sas io
        :return:
        """
        if (cls.test_object == constants.TEST_OBJECT_EXPANDER or
            cls.test_object == constants.TEST_OBJECT_PCIE_SWITCH) or \
                cls.test_entry == TestEntryStrEnum.UEFI.value:
            return

        if cls.test_platform != TestPlatformEnum.REAL_PLATFORM.value:
            return

        version = ControllerOperation.get_product_version()
        log.info(f"product version is {version}")
        if version != 'es100':
            return

        _, out = CustomOperation.get_sas_io(controller_id=libs_constants.X16_CONTROLLER)

        log.info("print sas io: ".format(out))

    @classmethod
    def check_ioc_halt(cls, script_code: int) -> int:
        """
        判断ioc是否为halt状态
        :param script_code: 脚本执行结果返回码
        :return:
        """
        if (cls.test_object == constants.TEST_OBJECT_EXPANDER or
            cls.test_object == constants.TEST_OBJECT_PCIE_SWITCH) or \
                cls.test_entry == TestEntryStrEnum.UEFI.value:
            return script_code

        host_no = ControllerOperation.get_host_no(controller_id=libs_constants.X16_CONTROLLER)
        rtn_code = CustomOperation.get_halt_status(host_no, controller_id=libs_constants.X16_CONTROLLER)
        if rtn_code == RtnStatusEnum.FAIL.value:
            # 如果halt 需要重新打开通路，让cli可用
            CustomOperation.halt_support_cli(host_no)
            cls.bug_stop = True
            cls.bug_existed_flag = True
            script_code = constants.RETURN_CODE_FAIL
            log.error('ioc is halt,test stop ...')

            cls.__create_framework_bug({'title': '发现 ioc halt', "type_name": "发现 ioc halt",
                                        'test_tool': 'cli', 'log_path': cls.log_server_path})

        return script_code

    @classmethod
    def check_mm_block(cls, m_time: str = '30'):
        """
        打印内存占用
        :param time:
        :return:
        """
        if cls.test_object == constants.TEST_OBJECT_RAID:
            return

        out = ""
        # 每轮测试结束后打印内存占用
        for i in range(3):
            _, out = CustomOperation.mm_show_block(controller_id=libs_constants.X16_CONTROLLER, time=m_time)
            if 'MemoryType' in out:
                break
            time.sleep(2)

        log.info(f"print mm_block info:{out}")

        if cls.test_platform == TestPlatformEnum.REAL_PLATFORM.value and 'MemoryType' in out:
            out = str(out.strip()).splitlines()
            for i in range(len(out)):
                if 'MemoryType' in out[i]:
                    if i + 1 < len(out) and len(out[i + 1].strip()) > 1:
                        cls.__create_framework_bug({'title': '疑似发现内存泄露', "type_name": "疑似发现内存泄露",
                                                    'test_tool': 'cli', 'log_path': cls.log_server_path})
                        break

    @classmethod
    def __force_to_exit_test(cls):
        """
        根据测试框架下的文件检测是否要强制退出本轮测试
        :return: bool
        @changelog      2023-02-06 13:36:46  junfeng.he
        """
        exit_file = "{}/exit_test.txt".format(cls.scripts_directory)
        log.info("=========> you can execute [echo 'exit' > {}] force to exit test.<=========".format(exit_file))
        file_content = FileOperation.read_local_file(exit_file)
        log.info("=========> current value:{} ".format(file_content))
        if "exit" in file_content:
            log.info("=========> trigger force to exit test!!!! <=========".format())
            return True
        else:
            return False

    @classmethod
    def __clear_exit_test_file(cls):
        """
        根据测试框架下的文件检测是否要强制退出本轮测试
        :return: bool
        @changelog      2023-02-06 13:36:46  junfeng.he
        """
        exit_file = "{}/exit_test.txt".format(cls.scripts_directory)
        file_content = FileOperation.read_local_file(exit_file)
        log.info("=========> current value:{}".format(file_content))
        if "exit" in file_content:
            FileOperation.write_local_file(exit_file, "continue")
            file_content = FileOperation.read_local_file(exit_file)
            log.info("=========> return the file[{}] content to {}.".format(exit_file, file_content))

    @classmethod
    def __check_log_analysis(cls, script_start_timestamp, script_name, test_break_flag):
        """
        日志分析，监测断流、复位
        :param script_start_timestamp:
        :param script_name:
        :param test_break_flag:
        :return:

        @changelog      2022-10-25 13:36:46  haibin.xu
                        1. 优化函数实现, expander测试，直接返回
        """

        if cls.test_entry == TestEntryStrEnum.SOC.value or cls.test_object == TestObjectStrEnum.PCIE_SWITCH.value \
                or cls.test_object == TestObjectStrEnum.EXPANDER.value:
            return test_break_flag

        if cls.test_entry == TestEntryStrEnum.UEFI.value:
            return test_break_flag

        # 进行日志分析
        _, script_end_time = CommandOperation.get_time()

        log.info('start log analysis ...')
        rtn = cls.log_analysis.log_analysis(
            time.strftime('%Y%m%d%H%M%S', time.localtime(script_start_timestamp)), script_end_time)
        cmd = f'wc -l /root/ps3test/slow_disk_log.conf'
        _, latest_lines, _ = CommandOperation.execute_command_with_error(cmd, print_enable=False)
        log.info('slow disk latest lines is {}'.format(latest_lines))
        # 检测到硬复位报bug @毕凯锋
        if (rtn and cls.driver_reset == 'default') or \
                ((cls.driver_reset == 'soft_reset' or cls.driver_reset == 'hard_reset') and rtn == 2) or \
                (((cls.iostat_analysis.value and cls.way_of_iostat == 0) or
                  (cls.way_of_iostat == 1 and not cls.hikos_disk_service and
                   latest_lines != cls.slow_disk_conf_lines)) and
                 cls.test_platform == TestPlatformEnum.REAL_PLATFORM.value and cls.cut_off):
            if ((cls.iostat_analysis.value and cls.way_of_iostat == 0) or
                (cls.way_of_iostat == 1 and latest_lines != cls.slow_disk_conf_lines and
                 not cls.hikos_disk_service)) and \
                    cls.test_platform == TestPlatformEnum.REAL_PLATFORM.value and cls.cut_off:
                if cls.way_of_iostat == 0:
                    log.info('----------------------------------------------------------')
                    log.info(cls.iostat_analysis.value)
                    log.info('details refer to the file: %s' % cls.iostat_log_full_path.value)
                    log.info('----------------------------------------------------------')
                else:
                    log.info('发现IO断流或性能下降, 参考主机侧的/root/ps3test/slow_disk_log.conf')
                    cmd = 'iostat -V'
                    _, out, _ = CommandOperation.execute_command_with_error(cmd, print_enable=False)
                    version = out.split(' ')[2].split('.')[0]
                    if version <= '10':
                        log.info('判定标准：($6<50 && $7<50 && $14>=99.0) || '
                                 '($6==0 && $7==0 && $9>0 && $10==0 && $14>80) || '
                                 '($11>5000 && $14>99.0) || ($12>5000 && $14>99.0)')
                    else:
                        log.info('判定标准：($4<50 && $5<50 && $16>=99.0) || '
                                 '($4==0 && $5==0 && $12>0 && $10==0 && $11==0 && $16>80) || '
                                 '($10>5000 && $16>99.0) || ($11>5000 && $16>99.0)')
                    cls.slow_disk_conf_lines = latest_lines

                test_case = dict()
                if cls.way_of_iostat == 0:
                    test_case[constants.CASE_SCRIPT_SCRIPT_LOCATION] = 'framework_' + cls.iostat_time.value
                    cls.iostat_analysis.value = ''
                    cls.iostat_time.value = ''
                else:
                    test_case[constants.CASE_SCRIPT_SCRIPT_LOCATION] = 'framework_' + script_end_time
                test_case[constants.CASE_SCRIPT_CASE_TITLE] = '发现IO断流或性能下降'
                cls.__create_framework_bug({'title': '发现IO断流或性能下降', "type_name": "发现IO断流或性能下降",
                                            'test_tool': 'cli',
                                            'log_path': cls.collect_log.log_script_dir_path}, test_case)
            else:
                test_case = dict()
                test_case[constants.CASE_SCRIPT_SCRIPT_LOCATION] = 'framework_' + script_end_time
                test_case[constants.CASE_SCRIPT_CASE_TITLE] = '主机发起复位'
                cls.__create_framework_bug({'title': '主机发起复位', "type_name": "主机发起复位",
                                            'test_tool': 'cli',
                                            'log_path': cls.collect_log.log_script_dir_path}, test_case)
            # 如果出现硬复位,收集日志
            collect_flag, _, _ = cls.collect_log.collect_host_log_after_framework_bug(script_name)
            # 如果日志收集失败，保留环境，停止测试
            if not collect_flag:
                cls.bug_stop = True
                cls.bug_existed_flag = True
                test_break_flag = True
                log.info('collect host log after framework bug fail, test stop')

        return test_break_flag

    @classmethod
    def clear_cmd_stat(cls):
        """
        脚本执行前 ，清理统计
        author: sunql
        story: songjy

        @changelog      1.   job 开始  或者 重启 后 ，执行打开主机驱动性能统计开关, 其从host_no后面的xxx填写实际的host no
                            cli driver cmd_stat_switch_store host_no xxx value 0x3 mask 0xf
                        2.   脚本执行前 ，清理统计，连续敲几次下面的开关clear命令，防止待IO clear
                            cli driver cmd_stat_clear host_no xxx
                        3.  执行后查询统计，发起IO前查询都是0，如果不是0，可以再敲一下步骤2的清理
                            cli driver cmd_stat_dump host_no xxx

        :return: None
        """
        return
        if cls.is_perf:
            return
        for i in range(10):
            ControllerOperation.clear_soft_stat(controller_id=libs_constants.X16_CONTROLLER)
            if ControllerOperation.dump_soft_stat(controller_id=libs_constants.X16_CONTROLLER) == 0:
                break
            else:
                out = ControllerOperation.dump_soft_stat_all(controller_id=libs_constants.X16_CONTROLLER)
                log.error("clear soft stat fail，dump soft  stat is:\n".format(out))

        log.info("clear soft stat success")

    @classmethod
    def do_script_test(cls) -> None:
        """
        author: luyafei
        date  : 2020.04.21
        执行脚本测试
        :return: None

        @changelog      2021-02-27 09:41:11  haibin.xu
                        1. 作为类方法并入RunAllTestPs3类
                        2021-06-13 09:48:06  haibin.xu
                        1. 优化函数实现， 去掉所有参数，全部以类变量代替，封装代码块，函数返回值修改为None
                        2021-08-19          sunql
                        1、增加长稳测试 空转逻辑
                        2、增加长稳测试 检查qemu log磁盘空间并清理逻辑
                        2022-06-03 09:19:51  haibin.xu
                        1. 优化函数实现, expander物理环境下，每个case测试前更新ps3explog记录信息
        """
        cmd_code = RtnStatusEnum.FAIL.value
        # ping失败次数
        ping_fail_times = 0
        # 测试终端标志位
        test_break_flag = False
        script_start_timestamp = 0
        # return code列表，用于core/crash的判断
        return_code_list = [constants.RETURN_CODE_FAIL, constants.RETURN_CODE_SUCCESS, constants.RETURN_CODE_TIMEOUT,
                            constants.RETURN_CODE_SKIP]

        # 获取脚本所在的scripts目录，即/test/esat/scripts目录
        cls.__get_scripts_directory()
        # 获取初始crash/core文件信息，用于后续检查crash/core文件
        cls.collect_log.get_crash_core_files_before_test()

        # 测试前进行环境检查
        cls.environment_prepare_before_test()
        cls.last_check_time = datetime.now()

        # 清除强制退出内容
        cls.__clear_exit_test_file()

        # 记录运行脚本的数量
        script_run_num = 0
        # script_case_dict存放待测试的脚本信息
        for script_name in cls.script_case_dict.keys():
            # 当前测试脚本对应的测试用例info
            script_info_list = cls.script_case_dict.get(script_name)

            if not isinstance(script_info_list, list) or (isinstance(script_info_list, list) and
                                                          len(script_info_list) == 0):
                # 不是list类型，或者是list类型但是是空列表时，该脚本信息不存在，跳过
                script_info_list = [{constants.CASE_SCRIPT_CASE_TITLE: 'case is not existed'}]
                cls.__handle_script_test_result_info(script_name, constants.SCRIPT_CASE_NON_EXIST, script_info_list,
                                                     cls.test_result_excel_file_path, 'Script case not exists')
                continue

            # 测试脚本路径
            script_path = CommandOperation.format_linux_path_sep(os.path.join(cls.scripts_directory, script_name))

            # 脚本不存在
            if not os.path.exists(script_path):
                cls.__handle_script_test_result_info(script_path, constants.SCRIPT_NON_EXIST, script_info_list,
                                                     cls.test_result_excel_file_path, 'Script not exists')
                continue

            # ps3explog日志记录更新
            cls.collect_log.update_ps3_exp_log_record_data()

            # 测试前进行环境检查
            cls.environment_monitor_before_test()

            # 打印测试脚本路径信息
            log.info(constants.SCRIPT_START_INFO % script_path)

            # 检查测试机是否能够连通
            ping_fail_times = cls.__check_deploy_ip(ping_fail_times)

            # 测试机能够连通
            if 0 == ping_fail_times:
                # 是否需要再次执行脚本
                script_break_flag = True
                # 脚本失败次数
                script_failed_times = 0
                # 如果是覆盖率版本，需要执行cli /c0 custom mgr gcov
                cls.__get_gcov()
                # 获取执行脚本的命令
                script_execute_cmd = commands.get_run_script_cmd(script_path, cls.test_script_log_directory,
                                                                 [cls.expander_generation, cls.exp_ctrl_id])

                for i in range(constants.EXEC_SCRIPTS_MAX_TIMES):
                    # 打印fio vdbench 进程信息
                    cls.get_fio_vdbench_proc_info()
                    # 清理vdbench、fio相关文件
                    cls.collect_log.delete_test_tool_files()
                    # 清理ioc宿主机缓存
                    cls.__drop_caches()
                    # 获取测试前的时间戳，开始时间，内存占用
                    script_start_timestamp, script_start_time, memory_before_test = \
                        cls.__get_paramters_before_script_test()
                    # 清理host_trace
                    cls.clean_host_trace()
                    # 测试前获取 sas io
                    cls.print_sas_io()
                    # 测试前清理 cmd stat
                    cls.clear_cmd_stat()
                    # 脚本执行前批量获取环境、通道等信息
                    cls.__exec_cli_to_log()
                    # 测试前开启定时移动测试机drv日志
                    cls.__close_mv_log_proc()
                    cls.mv_test_server_log()
                    # 脚本开始执行
                    cmd_code, cmd_output = CommandOperation.execute_script_command(script_cmd=script_execute_cmd)
                    # 测试后关闭移动drv 日志进程
                    cls.__close_mv_log_proc()
                    # 测试后获取 sas io
                    cls.print_sas_io()
                    cls.__exec_cli_to_log()
                    # @overwrite 执行失败时检查测试机是否连通，进程是否存在，测试机超时并进程存在时，重置所有标志位，通知框架停止测试
                    test_break_flag, script_break_flag = cls.__check_qemu_connect_process(test_break_flag,
                                                                                          script_break_flag, cmd_code)
                    # log.info(f"5^^^{cls.bug_stop}-{cls.bug_existed_flag}-{test_break_flag}-{script_break_flag}")
                    # 获取测试后的内存差值，测试时长
                    memory_delta, time_duration = cls.__get_paramters_after_script_test(memory_before_test,
                                                                                        script_start_timestamp)
                    cls.collect_log.current_script_test_start_time = script_start_time
                    cls.collect_log.current_script_test_time = time_duration
                    # 打印脚本执行返回码
                    log.info('Script execute return code: {}'.format(cmd_code))

                    # expander 覆盖率版本测试，gcov命令需要在每次执行完脚本后再执行一遍
                    cls.__expander_gcov()

                    # 生成result对象，并将测试开始时间，测试时间，内存差值赋值
                    result_object = utils.make_result_object(script_start_time, str(time_duration),
                                                             memory_delta, cls.test_platform)

                    # 日志刷新，将缓存中的日志落盘
                    cls.__flush_log()

                    # 临时逻辑 检查卡的halt 状态，如果为halt ，框架报bug 并设置 bug stop 为 True
                    cmd_code = cls.check_ioc_halt(cmd_code)

                    # 每个脚本执行完成后打印内存占用并检查泄露
                    if cls.ioc_memory_leak:
                        log.info("ioc_memory_leak is yes , please wait 1 minute")
                        time.sleep(60)
                        cls.check_mm_block('1')

                    # 检查是否出现Core、Crash
                    cmd_code, core_crash_code, test_break_flag, cmd_output = \
                        cls.__check_crash_core_files(cmd_code, cmd_output, return_code_list, test_break_flag)

                    # 测试后进行环境检查
                    test_break_flag, cls.collect_log.register_file = cls.environment_monitor_after_test(
                        script_path, cmd_code, script_start_time)

                    # 处理结果返回码, 并收集日志，并再一次查询crash/core文件，以及返回相应标志位
                    script_break_flag, script_failed_times, ioc_core_flag, ioc_crash_flag, host_crash_flag = \
                        cls.__handle_script_return_code(cmd_code, cmd_output, script_failed_times, i, result_object,
                                                        script_info_list, script_name, script_break_flag)

                    # 当用户配置遇到bug停止测试的情况
                    test_break_flag, script_break_flag = cls.__check_bug_stop(
                        cmd_code, [constants.RETURN_CODE_FAIL, constants.RETURN_CODE_TIMEOUT], script_path,
                        script_break_flag, test_break_flag)

                    # 当用户配置bug不停止，但是scriptBase返回结果中需要停止后续测试
                    test_break_flag, script_break_flag = cls.__check_stop_test(cmd_output, test_break_flag,
                                                                               script_break_flag)

                    # 用户配置bug不停止时，检测环境是否需要重启
                    test_break_flag, script_break_flag = cls.__check_reset_host_ioc(
                        core_crash_code, ioc_core_flag, ioc_crash_flag, host_crash_flag, script_break_flag,
                        test_break_flag, cmd_code)

                    # 脚本fail 打印 mpc job info
                    cls.__print_mpc_jobInfo(cmd_code)

                    if script_break_flag:
                        break

            elif 0 < ping_fail_times <= constants.PING_FAILED_MAX_TIMES:
                cls.__handle_script_test_result_info(
                    script_path, constants.REPORT_COL_SCRIPT_SKIP, script_info_list, cls.test_result_excel_file_path,
                    'Fail to connect cli deploy server ip: {}'.format(cls.cli_deploy_ip))
            else:
                test_break_flag = True
                log.error('Fail connection times more than {}, exit the test task.'.format(
                    constants.PING_FAILED_MAX_TIMES))

            # 修改日志服务器上当前测试日志目录的访问权限
            cls.__modify_log_directory_in_log_server()

            # 进行日志分析
            # if cls.__check_log_analysis(script_start_timestamp, script_name, test_break_flag):
            #     test_break_flag = True

            # 检查是否强制测试单结束，提前回收测试结果，退出本轮
            if not test_break_flag:
                test_break_flag = cls.__force_to_exit_test()

            #  跳出循环，停止测试
            if test_break_flag:
                log.info('test stop , test_stop_flag is true')
                break
            # 长稳测试时
            script_run_num += 1
            if cls.long_stab_test:
                # 清理qemu log
                cls.collect_log.clear_qemu_log_by_long_test()
                # 当运行50脚本，sleep
                if script_run_num % 50 == 0:
                    log.info("sleeping,please wait...")
                    time.sleep(random.randint(60, 300))
        # haibin.xu 2023-01-06 09:21:00 modify: 添加pcieSwitch不做get_crc_info检查操作，expander测试情况下只在lsmod中有ps3
        # 时才执行
        # if cls.test_platform != constants.ENV_PLATFORM_SIMU and cls.test_entry != TestEntryStrEnum.UEFI.value:
        #     if cls.test_object == constants.ENV_TEST_OBJECT_PCIE_SWITCH:
        #         return
        #     elif cls.test_object == constants.ENV_TEST_OBJECT_EXPANDER and cls.ps3_exp_test_flag:
        #         LogAnalysis().get_crc_info(cls.config_dict.get(constants.ENV_HOST_LABEL), cls.job_id)

    @classmethod
    def __print_mpc_jobInfo(cls, script_code):
        """
        脚本错误时打印 mpc job info
        :param script_code:
        :return:
        """
        if cls.test_object == constants.ENV_TEST_OBJECT_EXPANDER:
            cmd_code, cmd_stdout, _ = CommandOperation.execute_command_with_error(
                "lsmod | grep ps3", ssh_ip=cls.host_ip, ssh_port=cls.host_port, timeout=5)
            if (RtnStatusEnum.SUCCESS.value != cmd_code) or ('ps3' not in cmd_stdout):
                log.info('test object is expander, no ps3 drive, not need to print mpc info.')
                return

        if script_code == constants.RETURN_CODE_FAIL:
            out = CustomOperation.get_mpc_jobInfo(controller_id=libs_constants.X16_CONTROLLER)
            log.info(f"print mpc job info {out}")

    @classmethod
    def __check_qemu_connect_process(cls, test_break_flag: bool, script_break_flag: bool,
                                     cmd_code: int = None) -> tuple:
        """
        执行失败时检查测试机是否连通，进程是否存在, 如存在执行gcore, 并跳出脚本执行
        author: sunql
        :param script_break_flag:
        :param cmd_code:
        :return tuple
        """
        cls.host_ioc_reset = False
        # 非模拟平台环境
        # haibin.xu 2023-01-07 11:25:50 modify: 添加soc侧expander测试
        if cls.test_platform != constants.ENV_PLATFORM_SIMU or 'windows' in cls.host_os or \
                (TestEntryStrEnum.SOC.value == cls.test_entry and
                 TestObjectStrEnum.EXPANDER.value == cls.test_object):
            return test_break_flag, script_break_flag
        # 模拟平台执行
        if cmd_code != constants.RETURN_CODE_SUCCESS:

            def ping_node(ip):
                ping_flag = True
                cmd = "ping  -q -c 5  {}".format(ip)
                _, out, _ = CommandOperation.execute_command_with_error(cmd, ssh_ip=cls.host_ip,
                                                                        ssh_port=cls.host_port, timeout=30)
                if ', 0 received' in out:
                    ping_flag = False
                log.info(f"ping node is {ping_flag} , {cmd} result: {out}")
                return ping_flag

            def get_node_process(ip, nodes, nodeName):
                pid = None
                node_id = None
                for node in nodes:
                    if node['ip'] == ip:
                        node_id = node['id']
                        break
                if node_id:
                    get_pid_cmd = 'ps -ef | grep {} | grep -v \'grep\' ' \
                                  '| grep -v expander_Env | awk \'{{print $2}}\''.format(nodeName + node_id)
                    cmd_code, pid, cmd_stderr = CommandOperation.execute_command_with_error(
                        cmd=get_pid_cmd, ssh_ip=cls.host_ip, ssh_port=cls.host_port, timeout=300)
                    if not len(pid) > 0:
                        pid = None
                    log.info(f"{get_pid_cmd} result: {pid}")
                return pid

            def gcore(pid):
                cmd = f"nohup gcore {pid} > /dev/null 2>&1 &"
                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                    cmd=cmd, ssh_ip=cls.host_ip, ssh_port=cls.host_port, timeout=300)
                rtn_code = CommandOperation.check_cli_output(cmd, cmd_code, cmd_stdout, cmd_stderr)
                if RtnStatusEnum.SUCCESS.value == rtn_code:
                    log.info(f"{cmd} is start in bg,file path:/root/core.{pid},please wait... ")
                else:
                    log.error(f"{cmd} exec fail,please execute cmd by hand,error:{cmd_stderr}")

            def stack(pid):
                cmd = f"cat /proc/{pid}/stack > /root/stack.{pid}"
                cmd_code, cmd_stdout, cmd_stderr = CommandOperation.execute_command_with_error(
                    cmd=cmd, ssh_ip=cls.host_ip, ssh_port=cls.host_port, timeout=300)
                rtn_code = CommandOperation.check_cli_output(cmd, cmd_code, cmd_stdout, cmd_stderr)
                if RtnStatusEnum.SUCCESS.value == rtn_code:
                    log.info(f"{cmd} is success ,file save path:/root/stack.{pid} ")
                else:
                    log.error(f"{cmd} exec fail,please execute cmd by hand,error:{cmd_stderr}")

            def killHostQemu(pid, nodes):
                falg = False
                for i in range(3):
                    kill_cmd = f"kill -9 {pid}"
                    _, _, _ = CommandOperation.execute_command_with_error(
                        cmd=kill_cmd, ssh_ip=cls.host_ip, ssh_port=cls.host_port, timeout=300)
                    host_qemu_pid = get_node_process(cls.host_qemu_ip, nodes, 'hostnode')
                    if not host_qemu_pid:
                        falg = True
                        log.info(f"kill host qemu success")
                        break
                return falg

            def add_host_node():
                rtn_add_host_node = HostOperation.add_host_node(cls.host_node_name)
                if RtnStatusEnum.SUCCESS.value == rtn_add_host_node:
                    log.info('Success to finish add hostnode: {}.'.format(cls.host_node_name))
                    return True
                else:
                    log.error('Fail to add hostnode: {}.'.format(cls.host_node_name))
                    return False

            # 获取测试机所有qemu node
            nodes = HostOperation.get_node_info()
            # 测试hostqemu是否连通，ping 不通 且 进程存活
            if not (ping_node(cls.host_qemu_ip)):
                host_qemu_pid = get_node_process(cls.host_qemu_ip, nodes, 'hostnode')
                log.info(f"host_qemu_pid is :{host_qemu_pid}")
                if host_qemu_pid:
                    script_break_flag = True
                    # kill host process
                    if not killHostQemu(host_qemu_pid, nodes) or not add_host_node():
                        test_break_flag = True
                        cls.bug_stop = True
                        cls.bug_existed_flag = True
                elif not add_host_node():
                    script_break_flag = True
                    test_break_flag = True
                    cls.bug_stop = True
                    cls.bug_existed_flag = True
                else:
                    cls.host_ioc_reset = True

            # 测试iocqemu是否连通，ping 不通 且 进程存活
            # log.info("check ioc qemu start")
            # if not (ping_node(cls.ioc_qemu_ip)):
            #     ioc_qemu_pid = get_node_process(cls.ioc_qemu_ip, nodes, 'iocnode')
            #     log.info(f"ioc_qemu_pid is :{ioc_qemu_pid}")
            #     if ioc_qemu_pid:
            #         test_break_flag = True
            #         script_break_flag = True
            #         cls.bug_stop = True
            #         cls.bug_existed_flag = True
            #         gcore(ioc_qemu_pid)
            #         stack(ioc_qemu_pid)

        return test_break_flag, script_break_flag

    @classmethod
    def collect_current_test_round_all_log(cls) -> None:
        """
        author:      haibin.xu
        date:        2022-06-25 16:27:48
        description: 收集当前轮测试的所有log

        :return:     None
        """
        log.info('Start to collect all log of test round: {}'.format(cls.current_test_rounds_index))
        cls.collect_log.current_script_test_start_time = None
        cls.collect_log.current_script_test_time = None
        if constants.TEST_OBJECT_EXPANDER == cls.test_object:
            if cls.current_test_rounds_index != (cls.test_rounds - 1):
                log.warning('Expander test, not last test round, not to collect all log.')
                return
            else:
                log.info('Expander test, and the last test round, collect all log.')
        else:
            current_fail_num = None
            if 0 == cls.current_test_rounds_index:
                # 上一轮失败脚本个数
                before_fail_num = cls.fail_num
                # 本轮失败脚本个数
                current_fail_num = cls.fail_num
            else:
                before_fail_num = current_fail_num
                current_fail_num = cls.fail_num

            if (0 == cls.fail_num) or ((0 < cls.current_test_rounds_index) and
                                       (current_fail_num == before_fail_num)):
                log.info('Not found new failed script at current round test, not need to collect log.')
                return

        log_directory_name = 'test_round_{}_all_log'.format(cls.current_test_rounds_index)
        cls.collect_log.make_script_directory_in_log_server(script_name=log_directory_name)
        _, _, _, collect_log_flag = cls.collect_log.collect_log()
        cls.collect_log.collect_framework_log(source_framework_log_path=cls.run_all_test_log_file,
                                              source_script_log_path=cls.job_directory_path)
        cls.__modify_log_directory_in_log_server()

        log.info('Finish to collect all log of test round: {}'.format(cls.current_test_rounds_index))
        # 如果日志收集失败,停止测试
        if not collect_log_flag and cls.test_entry != TestEntryStrEnum.UEFI.value:
            if cls.test_object == constants.TEST_OBJECT_EXPANDER or \
                    cls.test_object == constants.TEST_OBJECT_PCIE_SWITCH:
                log.warning(r"collect {} fail,please attention...".format(log_directory_name))
            else:
                log.error(r"collect {} fail,test stop...".format(log_directory_name))
                cls.bug_stop = True
                cls.bug_existed_flag = True
                cls.__create_framework_bug({'title': '收集当前job的所有日志失败', "type_name": "日志收集失败",
                                            'test_tool': 'cli', 'log_path': cls.log_server_path})

    @classmethod
    def get_fio_vdbench_proc_info(cls):
        """
        获取 fio vdbench 进程并打印
        :return:
        """
        if cls.test_entry == TestEntryStrEnum.UEFI.value:
            return

        def get_proc(keyword):
            cmd = f"ps -ef | grep {keyword} | grep -v grep"
            code, out, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd,
                                                                                        ssh_ip=cls.host_qemu_ip,
                                                                                        ssh_port='22')
            out = out.strip()
            if keyword in out:
                log.warning(f"{keyword} proc info: \n {out}")

        get_proc('fio')
        get_proc('vdbench')

    @classmethod
    def __create_framework_bug(cls, bug_info: dict, test_case=None):
        """
        创建 framework bug
        :param bug_info:
        :param test_case:
        :return:
        """
        if not test_case:
            test_case = dict()
            test_case[constants.CASE_SCRIPT_SCRIPT_LOCATION] = 'framework'
            test_case[constants.CASE_SCRIPT_CASE_TITLE] = ''
        case_dict_list = [test_case]
        cls.__handle_script_test_result_info('framework', 'framework', case_dict_list,
                                             cls.test_result_excel_file_path, 'framework create bug')

        bug_dict = {}
        # 生成Bug信息
        bug_object = Bug()
        bug_object.set_common_values(cls.config_dict, cls.ip_dict)
        bug_object.set_title(bug_info.get('title', ''))
        bug_object.set_type_name(bug_info.get('type_name', ''))
        bug_object.set_test_tool(bug_info.get('test_tool', ''))
        bug_object.set_precondition('')
        bug_object.set_steps(bug_info.get('test_steps', ''))
        bug_object.set_log_path(bug_info.get('log_path', ''))
        bug_object.set_platform_info(cls.test_platform_info)
        # 构造bug字典
        bug_dict = bug_result_excel_handle.append_bug_to_excel(bug_object, case_dict_list,
                                                               cls.test_bug_excel_file_path)
        # 提交bug信息到禅道
        utils.submit_to_zentao(result_data={}, bug_data=bug_dict)

    @classmethod
    def run_test(cls) -> None:
        """
        author: luyafei
        date  : 2020.04.21
        description: 组织测试执行
        :return: 无返回值

        @changelog      2021-02-27 09:33:14  haibin.xu
                        1. 作为类方法并入RunAllTestPs3类
                        2021-06-13 09:56:50  haibin.xu
                        1. 优化函数实现, 相关方法提取
        """
        # 执行脚本测试
        for i in range(cls.test_rounds):
            cls.current_test_rounds_index = i
            if not cls.exam_2021 and not cls.exam_long_stab_test_2021:
                log.info('exam is False')
                cls.bug_existed_flag = False
                cls.do_script_test()
                # 仅最后一轮打印,何俊峰
                # if cls.test_rounds == i+1:
                #     time.sleep(300)
                #     cls.check_mm_block('5')
                # haibin.xu 2022-06-27 19:12:19 modify: 收集当前轮所有日志
                # haibin.xu 2022-07-30 09:34:11 modify: ioc测试搂底收集日志被亮哥注释掉，但是expander需要，此处添加expander
                # 判断
                if constants.TEST_OBJECT_EXPANDER == cls.test_object:
                    cls.collect_current_test_round_all_log()
                # haibin.xu 2022-07-05 17:25:14 modify: expander测试，打印串口日志中包含的FATAL等级日志
                # haibin.xu 2022-07-30 09:41:38 modify: 将expander判断移到方法内部判断
                ExpanderOperation.check_fatal_level_info(cls.host_qemu_ip, cls.test_object)
                if (cls.bug_stop is True) and (cls.bug_existed_flag is True):
                    break
                # 检查是否强制测试单结束，提前回收测试结果，退出多伦
                if cls.__force_to_exit_test():
                    break
            else:
                log.info('exam is True')
                TopoManager.delete_fixed_dir()
                # 第一步：获取所有拓扑
                source_dir = libs_constants.EXAM_2021_TOPO_LIST_DIR
                w = os.walk(source_dir)
                topo_list = []
                for path, _, file_list in w:
                    for file_name in file_list:
                        if not file_name.endswith('.json'):
                            continue
                        script_path = os.path.join(path, file_name)
                        topo_list.append(script_path)
                log.info(f"topo_list is {topo_list}")
                # 第二步：遍历拓扑
                # 2021.12.28 这里获取 topo_list 后, 顺便给排序, 保证按照 "*.json 的全路径名的字母顺序"来执行多个 topo
                for topo_file in sorted(topo_list):
                    # 记录当前拓扑，给公共库用
                    if not TopoManager.write_current_topo_file(topo_file):
                        continue
                    cls.bug_existed_flag = False
                    cls.do_script_test()
                    time.sleep(300)
                    cls.check_mm_block('5')
                    if (cls.bug_stop is True) and (cls.bug_existed_flag is True):
                        break
                if (cls.bug_stop is True) and (cls.bug_existed_flag is True):
                    break

    @classmethod
    def get_bug_result_excel_data(cls) -> dict:
        """
        author: luyafei
        date  : 2020.05.23
        description: 获取bug、result表中的数据信息
        :return: bug、result表中所有行的数据信息

        @changelog      2021-02-27 09:50:42  haibin.xu
                        1. 作为类方法并入RunAllTestPs3类
        """
        bug_results_dict = {}
        bug_dict_list = utils_excel.get_excel_data_by_row(cls.test_bug_excel_file_path)
        result_dict_list = utils_excel.get_excel_data_by_row(cls.test_result_excel_file_path)
        bug_results_dict.setdefault(constants.BUG_EXCEL_KEY, bug_dict_list)
        bug_results_dict.setdefault(constants.RESULT_EXCEL_KEY, result_dict_list)
        bug_results_dict.setdefault(constants.RESULT_JOB_KEY, cls.jenkins_job_info)
        return bug_results_dict

    @classmethod
    def __add_summary_info(cls, test_info_dict: dict) -> dict:
        """
        author:      haibin.xu
        date:        2021-03-01 19:55:59
        description: 测试问题、结果信息字典
        :return:     返回更新后的统计信息数据
        """
        summary_info_dict = {}
        summary_info_dict.setdefault(constants.REPORT_COL_SCRIPT_PASS, cls.pass_num)
        summary_info_dict.setdefault(constants.REPORT_COL_SCRIPT_FAIL, cls.fail_num)
        summary_info_dict.setdefault(constants.REPORT_COL_SCRIPT_SKIP, cls.skip_num)
        summary_info_dict.setdefault(constants.REPORT_COL_SCRIPT_NOT_EXIST, cls.not_exist_num)
        summary_info_dict.setdefault(constants.REPORT_COL_SCRIPT_EXCEPTION, cls.except_num)
        summary_info_dict.setdefault(constants.REPORT_COL_SCRIPT_TIMEOUT, cls.timeout_num)
        test_info_dict.setdefault(constants.SCRIPT_SUMMARY_TAG, summary_info_dict)
        if (cls.test_entry == constants.ENV_TEST_ENTRY_IOC and
            cls.test_object == constants.ENV_TEST_OBJECT_EXPANDER) or (
                cls.test_object == constants.ENV_TEST_OBJECT_PCIE_SWITCH):
            test_info_dict.setdefault(constants.IOC_VERSION, 'PcieSwitch test or Expander test, no ioc version.')
        else:
            test_info_dict.setdefault(constants.IOC_VERSION, utils.get_ioc_version())

        return test_info_dict

    @classmethod
    def get_test_platform(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-03-04 17:57:02
        description: 获取测试入口

        :return:     None

        @changelog      2021-03-20 16:50:32  haibin.xu
                        1. 函数名修正：get_test_entry -> get_test_platform
        """
        log.info('Test platform: {}.'.format(cls.test_platform))

        if cls.test_platform != constants.ENV_PLATFORM_SIMU:
            CommandOperation.clean_cli_core_file(cls.comhost_ip, cls.a72_com,
                                                 cls.log_server_account, cls.log_server_ip)
        rtn_result = RtnStatusEnum.SUCCESS.value
        if constants.ENV_PLATFORM_SIMU == cls.test_platform:
            rtn_result = cls.start_simulator_platform()
        else:
            if cls.test_entry not in [TestEntryStrEnum.UEFI.value]:
                rtn_result = cls.start_real_platform()
            elif cls.test_entry == TestEntryStrEnum.UEFI.value:
                if not BmcOperation.power_status():
                    rtn_result = RtnStatusEnum.FAIL.value
                    log.error("fail to get bmc info ...")

        if RtnStatusEnum.SUCCESS.value == rtn_result:
            log.info(constants.LOG_FUNCION_SCRIPTS.format('Success to finish {}.'.format(cls.test_platform)))
            # time.sleep(30)
        else:
            log.error(constants.LOG_FUNCION_SCRIPTS.format('Fail to finish {}.'.format(cls.test_platform)))
            exit(0)

    @classmethod
    def statistic_ioc_threads(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-07 17:21:28
        description: 统计（ioc）线程数，线程异常时，答应线程调用栈信息

        :return:     None
        """
        log.info('Start to statistic ioc thread info ...')

        # 获取ioc进程id
        cls.__get_ioc_pid()

        while cls.ioc_pid:
            all_info = '\n'
            tar_thread_list = []
            # 如果ioc qemu 服务器异常掉电，则终止对ioc进程下所有线程的监测
            if RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(ip=cls.ioc_qemu_ip,
                                                                                port=cls.ioc_port):
                log.error('Can not connect soc qemu server: root@{}:{}, terminate statistic all threads of ioc '
                          'process.'.format(cls.ioc_qemu_ip, cls.ioc_port))
                break
            # 获取ioc进程下所有线程信息，以及线程pid,线程名关键信息
            raw_stdout, keycloumn_stdout = CommandOperation.get_all_threads_in_process(
                process_id=cls.ioc_pid, ssh_ip=cls.ioc_qemu_ip, ssh_port=cls.ioc_port)

            # 统计当前ioc进程下的所有线程包含target线程的数量
            for keyc in keycloumn_stdout:
                for tar_thread in cls.process_list:
                    if isinstance(keyc, tuple) and (2 == len(keyc)) and tar_thread in keyc[1]:
                        tar_thread_list.append(keyc)

            # 如果包含目标线程数大于0，记录相关线程id,线程名信息
            if 0 < len(tar_thread_list):
                statistic_info = 'thread_count: {}, thread_list: {}\n\n'.format(
                    len(tar_thread_list), tar_thread_list)
                # 统计到ioc线程时，把统计信息添加到待all_info
                all_info += statistic_info

            if constants.MAX_ALLOW_THREADS < len(tar_thread_list):
                # 线程数量异常时，获取各线程的调用栈信息
                thread_stack_info = ''
                for thread in tar_thread_list:
                    rtn_code, rtn_stdout = CommandOperation.get_process_thread_stack(
                        process_id=thread[0], ssh_ip=cls.ioc_qemu_ip, ssh_port=cls.ioc_port)
                    if (RtnStatusEnum.SUCCESS.value == rtn_code) and rtn_stdout:
                        thread_stack_info += 'thread_pid: {}, thread_name: {}, pstack:\n{}'.format(
                            thread[0], thread[1], rtn_stdout)

                if thread_stack_info:
                    # 线程数量异常时，将调用栈信息添加到all_info
                    all_info += thread_stack_info + '\n'
                    if raw_stdout:
                        # IOC所有线程信息，也添加到all_info
                        all_info += raw_stdout + '\n\n'

            if '\n' != all_info:
                # 将all_info写到threads_data.log日志中
                log.info2file(msg=all_info, file_path=cls.thread_data_path)

            ioc_node_meminfo = CommandOperation.get_meminfo(ssh_ip=cls.ioc_qemu_ip, ssh_port=cls.ioc_port)
            if cls.__isvalid(ioc_node_meminfo):
                ioc_node_meminfo += '\n\n'
                log.info2file(msg=ioc_node_meminfo, file_path=cls.ioc_qemu_meminfo_path)

            ioc_node_vmstat_info = cls.__cat_vmstat()
            if cls.__isvalid(ioc_node_vmstat_info):
                ioc_node_vmstat_info += '\n\n'
                log.info2file(msg=ioc_node_vmstat_info, file_path=cls.ioc_vmstat_path)

            ioc_node_iostat_info = cls.__ioc_iostat()
            if cls.__isvalid(ioc_node_iostat_info):
                ioc_node_iostat_info += '\n\n'
                log.info2file(msg=ioc_node_iostat_info, file_path=cls.ioc_iostat_path)

            ioc_qemu_iostat_info = cls.__ioc_qemu_iostat()
            if cls.__isvalid(ioc_qemu_iostat_info):
                ioc_qemu_iostat_info += '\n\n'
                log.info2file(msg=ioc_qemu_iostat_info, file_path=cls.ioc_qemu_iostat_path)

            time.sleep(5)

    @classmethod
    def __start_subprocess(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 11:13:26
        description: 创建并启动子进程，用于监测和统计ioc节点服务器线程信息

        :return:     None
        """
        # 如果是物理平台直接返回
        if cls.test_platform == TestPlatformEnum.REAL_PLATFORM.value:
            return

        cls.thread_data_path = CommandOperation.format_linux_path_sep(os.path.join(
            cls.job_directory_path, libs_constants.THREADS_DATA_FILE))

        cls.ioc_qemu_meminfo_path = CommandOperation.format_linux_path_sep(os.path.join(
            cls.job_directory_path, libs_constants.MEMINFO_DATA_FILE))

        cls.ioc_vmstat_path = CommandOperation.format_linux_path_sep(os.path.join(
            cls.job_directory_path, libs_constants.IOC_VMSTAT_DATA_FILE))
        log.info(f"ioc_vmstat_path:{cls.ioc_vmstat_path}")

        cls.ioc_iostat_path = CommandOperation.format_linux_path_sep(os.path.join(
            cls.job_directory_path, libs_constants.IOC_IOSTAT_DATA_FILE))
        log.info(f"ioc_iostat_path:{cls.ioc_iostat_path}")

        cls.ioc_qemu_iostat_path = CommandOperation.format_linux_path_sep(os.path.join(
            cls.job_directory_path, libs_constants.IOC_QEMU_IOSTAT_DATA_FILE))
        log.info(f"ioc_qemu_iostat_path:{cls.ioc_qemu_iostat_path}")

        if not cls.pcie_switch_flag:
            cls.monitor_process = multiprocessing.Process(target=cls.statistic_ioc_threads)
            cls.monitor_process.daemon = True
            cls.monitor_process.start()

    @classmethod
    def summary_test_info(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-06-12 11:14:27
        description: 汇总本次测试相关信息

        :return:     None
        """
        # 获取bug、result表中的数据信息, 并汇总其他统计信息
        bugs_results_info_dict = cls.get_bug_result_excel_data()
        print(bugs_results_info_dict)
        bugs_results_info_dict = cls.__add_summary_info(bugs_results_info_dict)
        # 将汇总数据进行json格式编码, 即将字典{constants.RESULT_RUN_ALL_TEST: bugs_results_info_dict}转化为字符串，供Jenkins
        # 通过json.loads()方法将json格式数据转换为字典。
        print_result = json.dumps({constants.RESULT_RUN_ALL_TEST: bugs_results_info_dict}, ensure_ascii=False)
        log.info(constants.TEST_FINISH_INFO)
        # 将test/esat/outputs/framework/run_all_test_ps3_20210610175943.log 转到ps3/test/esat/outputs/
        #     framework/ps3_auto_test_prepare_14093_20210610175943目录下
        time.sleep(120)
        utils.move_run_all_test_log(cls.run_all_test_log_file, cls.job_directory_path)
        # 此处使用不带时间戳打印，主要是为了jekins脚本auto_test.py中获取到run_all_test_ps3.py的输出
        log.info(print_result, format_flag=False)

    @classmethod
    def check_cli_memory_error(cls):
        """
        author:      sunql
        description: 检查内存泄露并报bug

        :return:     None
        :return:
        """
        if constants.ENV_PLATFORM_REAL == cls.test_platform and \
                (cls.test_object == constants.TEST_OBJECT_EXPANDER or
                 cls.test_object == constants.TEST_OBJECT_PCIE_SWITCH) or \
                cls.test_entry == TestEntryStrEnum.UEFI.value:
            # do nothing, add by hejf,20220319
            return

        # 如果是windows环境不检查
        if 'windows' in cls.host_os:
            return
        # 关闭内存监控，不管是否开启先关闭一次
        log.info("close memory monitor ......")
        CommandOperation.close_memory_leak()

        if not cls.memory_leak:
            return

        if FileOperation.find_keywords_with_file(path=constants.TEST_TOOL_HOST_CLI_ERROR_PATH,
                                                 keywords=['AddressSanitizer: stack-buffer-overflow',
                                                           'AddressSanitizer: SGEV'],
                                                 ip=cls.host_qemu_ip):
            log.error("cli memory leak......")

            cls.__create_framework_bug({'title': 'cli命令内存溢出', "type_name": "内存泄漏问题",
                                        'test_tool': 'cli', 'log_path': cls.log_server_path})

    @classmethod
    def environment_prepare_before_test(cls) -> None:
        """
        author:      junfeng.he
        description: 测试前进行环境准备工作
        :return:     None
        :return:
        """
        log.info("environment prepare before test ......")
        # 如果测试对象是expander
        if cls.test_object == TestObjectStrEnum.EXPANDER.value:
            # 非模拟平台环境
            if cls.test_platform != constants.ENV_PLATFORM_SIMU:
                # 只在第一轮测试时调用expander_topo_collect
                if 0 == cls.current_test_rounds_index:
                    cls.expander_generation = ExpanderOperation.expander_topo_collect(cls.host_qemu_ip)
            # 测试入口为Host，获取expander 所在控制器id
            if constants.ENV_TEST_ENTRY_HOST == cls.test_entry:
                target_ctrl_id = ExpanderOperation.get_ctrl_id_include_exp(cls.host_qemu_ip)
                if target_ctrl_id is not None:
                    log.info('Current expander belong to Controller id: {}'.format(target_ctrl_id))
                    cls.exp_ctrl_id = target_ctrl_id
            # 检查ioc侧是否为测试环境
            cmd_code, cmd_stdout, _ = CommandOperation.execute_command_with_error(
                "lsmod | grep ps3", ssh_ip=cls.host_ip, ssh_port=cls.host_port, timeout=5)
            if (RtnStatusEnum.SUCCESS.value == cmd_code) and ('ps3' not in cmd_stdout):
                cls.ps3_exp_test_flag = True
                cls.collect_log.ps3_exp_test_flag = cls.ps3_exp_test_flag
        # 其他测试对象，可以在此处添加
        else:
            pass

    @classmethod
    def environment_monitor_before_test(cls) -> None:
        """
        author:      junfeng.he
        description: 测试前进行环境检查、处理等
        :return:     None
        :return:
        """
        log.info("environment monitor before test ......")
        # 如果测试对象是expander
        if cls.test_object == TestObjectStrEnum.EXPANDER.value:
            # 非模拟平台环境
            if cls.test_platform != constants.ENV_PLATFORM_SIMU:
                exp_topo_info = ExpanderOperation.expander_topo_monitor(cls.host_qemu_ip, cls.log_trace)
                if isinstance(exp_topo_info, str) and exp_topo_info:
                    cls.test_platform_add_exp_info.update({'other': exp_topo_info})
                    platform_add_exp_info = json.dumps(cls.test_platform_add_exp_info)
                    cls.bug_object.set_platform_info(platform_add_exp_info)
        elif cls.test_object == TestObjectStrEnum.PCIE_SWITCH.value:
            # 非模拟平台环境
            if cls.test_platform != constants.ENV_PLATFORM_SIMU:
                ExpanderOperation.delete_pcie_log(cls.host_qemu_ip)
                # return ExpanderOperation.pcie_read_ups_info(cls.host_qemu_ip)
        # 其他测试对象，可以在此处添加
        else:
            if cls.test_platform != constants.ENV_PLATFORM_SIMU:
                CommandOperation.clean_cli_core_file(cls.comhost_ip, cls.a72_com,
                                                     cls.log_server_account, cls.log_server_ip)

    @classmethod
    def environment_monitor_after_test(cls, script_path: str, script_test_result: int,
                                       script_test_start_time: str = None) -> tuple:
        """
        author:      junfeng.he
        description: 测试后进行环境检查、处理等
        :param       script_path，脚本路径
        :param       script_test_result，脚本测试结果
        :param       script_test_start_time，脚本测试起始时间
        :return:     script_break_flag, register_dump_file

        @changelog      2022-02-22 16:07:21  haibin.xu
                        1. 修改返回类型：bool -> tuple, 增加返回dump 寄存器文件
                        2023-02-16 16:17:35  haibin.xu
                        1. 优化函数实现：添加脚本测试起始时间参数
        """
        log.info("environment monitor after test ......")
        force_excute = False
        if script_test_result == constants.RETURN_CODE_FAIL or \
                cls.last_check_time + timedelta(seconds=3600) < datetime.now():
            force_excute = True
            # 更新检查时间
            cls.last_check_time = datetime.now()

        # 如果测试对象是expander
        if cls.test_object == TestObjectStrEnum.EXPANDER.value:
            # 非模拟平台环境
            if cls.test_platform != constants.ENV_PLATFORM_SIMU:
                return ExpanderOperation.expander_status_monitor(
                    script_test_result, force_excute, cls.host_qemu_ip, script_path, cls.expander_generation,
                    script_test_start_time, cls.ps3_exp_test_flag)
        # 如果测试对象为pcie switch
        elif cls.test_object == TestObjectStrEnum.PCIE_SWITCH.value:
            # 非模拟平台环境
            if cls.test_platform != constants.ENV_PLATFORM_SIMU:
                if force_excute:
                    return ExpanderOperation.pcie_switch_status_monitor(cls.host_qemu_ip, script_path)
                else:
                    status = ExpanderOperation.check_exp_evtlog_num(sg=None, host_qemu_ip=cls.host_qemu_ip,
                                                                    test_object=constants.TEST_OBJECT_PCIE_SWITCH)
                    if not status:
                        return False, None
                    return ExpanderOperation.pci_read_ups_info_after_test(cls.host_qemu_ip)
        # 其他测试对象，可以在此处添加
        else:
            pass

        return False, None

    @classmethod
    def get_cli_mod(cls) -> None:
        """
        获取cli mode版本 debug或release
        :return:
        """
        if constants.ENV_PLATFORM_REAL == cls.test_platform and \
                (cls.test_object == constants.TEST_OBJECT_EXPANDER or
                 cls.test_object == constants.TEST_OBJECT_PCIE_SWITCH) or \
                cls.test_entry in [TestEntryStrEnum.UEFI.value, TestEntryStrEnum.SOC.value]:
            # do nothing, add by hejf,20220411
            return

        if cls.test_platform == constants.ENV_PLATFORM_REAL:
            cls.cli_mode = CustomOperation.get_cli_build_mode_full(controller_id=libs_constants.X16_CONTROLLER,
                                                                   ssh_ip=cls.host_ip)
            log.info(f"cli mode is {cls.cli_mode}")

        cls.cli_version, cls.cli_commit_id, cls.cli_branch = ControllerOperation.get_cli_version(
            controller_id=libs_constants.X16_CONTROLLER)
        log.info(f"cli version is {cls.cli_version}")
        log.info(f"cli commit id is {cls.cli_commit_id}")
        log.info(f"cli build branch is {cls.cli_branch}")

    @classmethod
    def split_real_com_log(cls) -> None:
        """
        切割com口a72日志
        :return: None
        """
        if constants.ENV_PLATFORM_REAL == cls.test_platform and \
                (cls.test_object == constants.TEST_OBJECT_EXPANDER or
                 cls.test_object == constants.TEST_OBJECT_PCIE_SWITCH) or \
                cls.test_entry == TestEntryStrEnum.UEFI.value:
            # do nothing, add by hejf,20220411
            return

        if 'dev' not in cls.a72_com:
            return

        if cls.test_platform == constants.ENV_PLATFORM_REAL:

            if not HostOperation.split_a72_com_log(ssh_ip=cls.comhost_ip, com=cls.a72_com):
                log.info(f"split_a72_com_log fail")

            log.info(f"split_a72_com_log success")

    @classmethod
    def pcie_gcno_end(cls) -> None:
        """
        pcie_switch 代码覆盖率所有命令脚本执行完成后，执行./pcieswitch_simu_host.elf -v命令，退出覆盖率检查
        """
        if cls.gcov_flag and cls.test_object == constants.ENV_TEST_OBJECT_PCIE_SWITCH:
            if cls.test_platform == constants.ENV_PLATFORM_SIMU:
                ExpanderOperation.pcie_switch_gcno_end(cls.host_qemu_ip)

    @classmethod
    def post_job_info_to_zentao(cls):
        """
        提交job信息到禅道 ，并生成json文件
        :return:
        """
        cls.jenkins_job_info = utils.test_run_submit(json.loads(cls.test_platform_info), cls.test_start_timestamp)
        if not cls.jenkins_job_info:
            test_platform_info = json.loads(cls.test_platform_info)
            cls.jenkins_job_info['job_uuid'] = cls.config_dict.get(constants.ENV_JOB_UUID)
            cls.jenkins_job_info['host_ip'] = cls.ip_dict.get(constants.ENV_HOST_IP)
            cls.jenkins_job_info['host_label'] = cls.config_dict.get(constants.ENV_HOST_LABEL)
            cls.jenkins_job_info['platform'] = cls.config_dict.get(constants.ENV_TEST_PLATFORM)
            cls.jenkins_job_info['test_obj'] = cls.config_dict.get(constants.ENV_TEST_OBJECT)
            cls.jenkins_job_info['start_time'] = int(cls.test_start_timestamp)
            cls.jenkins_job_info['end_time'] = int(time.time())
            cls.jenkins_job_info['os'] = cls.config_dict.get(constants.ENV_HOST_OS)
            # cls.jenkins_job_info['type'] =test_platform_info['type']
            cls.jenkins_job_info['kernel'] = test_platform_info['kernel']
            cls.jenkins_job_info['cpu'] = test_platform_info['cpu']
            cls.jenkins_job_info['memory'] = test_platform_info['memory']
            cls.jenkins_job_info['disk_num'] = test_platform_info['disk_num']
            cls.jenkins_job_info['ioc_version'] = test_platform_info['ioc_version']
            cls.jenkins_job_info['driver_version'] = test_platform_info['driver_build_branch']
            cls.jenkins_job_info['cli_version'] = test_platform_info['cli_version']
            cls.jenkins_job_info['cpld_version'] = test_platform_info['cpld_version']

    @classmethod
    def run(cls) -> None:
        """
        author:      haibin.xu
        date:        2021-02-27 09:12:46
        description: 脚本执行入口

        :return:     None
        """
        log.info(constants.LOG_SCRIPTS.format('Start run run_all_test_ps3 ...'))
        cls.init_parameters()
        # 启动测试节点
        cls.get_test_platform()
        log.info(constants.TEST_START_INFO)
        # 测试开始前的一些准备操作
        cls.prepare_before_test()
        cls.run_test()
        cls.post_job_info_to_zentao()
        cls.pcie_gcno_end()
        cls.check_cli_memory_error()
        cls.process_test_result()
        cls.summary_test_info()

        log.info(constants.LOG_SCRIPTS.format('Finish run run_all_test_ps3.'))


def main():
    RunAllTestPs3.run()


if __name__ == '__main__':
    main()
