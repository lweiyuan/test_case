# -*- encoding=utf8 -*-
import subprocess

from libs import utils_new as utils
from libs import constants
from scripts.script_libs import log

"""
author: luyafei
date  : 2020.04.22
description: 集合了脚本执行过程中需要的命令
"""


def get_run_script_cmd(script_path: str, script_log_output_dir: str,
                       expander_generation: str = None) -> str:
    """
    author: luyafei、panpan.du
    date  : 2020.04.22
    description: 生成执行脚本的命令
    :param script_path: 脚本名称
    :param script_log_output_dir: 测试脚本日志存放文件夹路径
    :param expander_generation: 脚本名称
    :return: 执行脚本的命令

    @changelog      2022-08-09 15:13:48  haibin.xu
                    1. 优化函数实现, 添加参数expander_generation，该参数只在expander测试时添加
    """
    cmd = "python3 %s" % script_path
    env_config, ip_config = utils.get_conf()

    # 超时时间限制
    script_timeout = env_config.get(constants.ENV_SCRIPT_TIMEOUT)
    if script_timeout is not None and script_timeout != "":
        timeout = str(script_timeout) + constants.SCRIPT_TIMEOUT_UNIT
        cmd = "timeout %s " % timeout + cmd

    # log_server_ip
    log_server_ip = ip_config.get(constants.ENV_LOG_SERVER_IP)
    if log_server_ip is not None and log_server_ip != "":
        cmd = cmd + (" --lsip %s" % log_server_ip)

    # log_server_user
    log_server_user = ip_config.get(constants.ENV_LOG_SERVER_ACCOUNT)
    if log_server_user is not None and log_server_user != "":
        cmd = cmd + (" --lsac %s" % log_server_user)

    # server ip
    host_ip = ip_config.get(constants.ENV_HOST_IP)
    if host_ip is not None and host_ip != "":
        cmd = cmd + (" --sip %s " % host_ip)
    else:
        log.warning("server ip is not configured")

    # server port
    host_port = ip_config.get(constants.ENV_HOST_PORT)
    if host_port is not None and host_port != "":
        cmd = cmd + (" --sp %s" % host_port)

    # server nic ip
    server_nic_ip = ip_config.get(constants.ENV_SERVER_NIC_IP)
    if server_nic_ip is not None and server_nic_ip != "":
        cmd = cmd + (" --snicip %s " % server_nic_ip)
    else:
        log.warning("server nic ip is not configured")

    # client ip
    client_ip = ip_config.get(constants.ENV_CLIENT_IP)
    if client_ip is not None and client_ip != "":
        cmd = cmd + (" --cip %s " % client_ip)
    else:
        log.warning("client ip is not configured")

    # server port
    client_port = ip_config.get(constants.ENV_CLIENT_PORT)
    if client_port is not None and client_port != "":
        cmd = cmd + (" --cp %s" % client_port)

    # client nic ip
    client_nic_ip = ip_config.get(constants.ENV_CLIENT_NIC_IP)
    if client_nic_ip is not None and client_nic_ip != "":
        cmd = cmd + (" --cnicip %s " % client_nic_ip)
    else:
        log.warning("client nic ip is not configured")

    # simulator
    test_host_type = env_config.get(constants.ENV_TEST_PLATFORM)
    if test_host_type == constants.ENV_PLATFORM_SIMU:
        cmd = cmd + " -s"

    # bug_stop
    if env_config.get(constants.ENV_BUG_STOP) is True:
        cmd = cmd + " --bs"
    # host_cpu 其中0表示x86, 1表示arm, 2表示mips
    host_cpu_lower = (env_config.get(constants.ENV_HOST_CPU)).lower()
    if host_cpu_lower == constants.HOST_CPU_X86:
        cmd = cmd + " --hc 0"
    elif host_cpu_lower == constants.HOST_CPU_ARM:
        cmd = cmd + " --hc 1"
    else:
        cmd = cmd + " --hc 2"
    # test_entry
    # direct
    # switch
    # single_mode
    # dpdk_mode
    # uefi_mode
    test_entry_lower = (env_config.get(constants.ENV_TEST_ENTRY)).lower()
    if test_entry_lower == 'direct':
        cmd = cmd + ' --te 0'
    elif test_entry_lower == 'switch':
        cmd = cmd + ' --te 1'
    elif test_entry_lower == 'single_mode':
        cmd = cmd + ' --te 2'
    elif test_entry_lower == 'dpdk_mode':
        cmd = cmd + ' --te 3'
    elif test_entry_lower == 'dpdk_auto_mode':
        cmd = cmd + ' --te 4'
    elif test_entry_lower == 'uefi_mode':
        cmd = cmd + ' --te 5'
    elif test_entry_lower == 'vf_keep_mode':
        cmd = cmd + ' --te 6'
    else:
        cmd = cmd + ' --te 7'

    test_object = '10'
    if env_config.get(constants.ENV_TEST_OBJECT) == constants.ENV_RUN_MODE_WITH_SRC:
        test_object = '11'
    elif env_config.get(constants.ENV_TEST_OBJECT) == constants.ENV_RUN_MODE_WITH_RPM:
        test_object = '12'
    elif env_config.get(constants.ENV_TEST_OBJECT) == constants.ENV_RUN_MODE_WITH_BG_TRAFFIC:
        test_object = '13'
    elif env_config.get(constants.ENV_TEST_OBJECT) == constants.ENV_RUN_MODE_WITH_SRC_KO:
        test_object = '14'
    elif env_config.get(constants.ENV_TEST_OBJECT) == constants.ENV_RUN_MODE_WITH_SRPM:
        test_object = '15'
    elif env_config.get(constants.ENV_TEST_OBJECT) == constants.ENV_RUN_MODE_WITH_KMOD_SRPM:
        test_object = '16'

    cmd = cmd + " --to " + test_object

    test_port = ip_config.get(constants.ENV_TEST_PORT)
    if test_port:
        cmd = cmd + " --tp " + str(test_port)

    if script_timeout is not None:
        cmd = cmd + ' --timeout {}'.format(str(script_timeout))

        # 长稳测试
    cmd = cmd + ' --lst %s' % str(env_config.get(constants.ENV_LONG_STAB_TEST) or 'False')

    if str(env_config.get(constants.EVN_SERVER_NIC_MODEL) or '') != "":
        cmd = cmd + ' --snicm %s' % str(env_config.get(constants.EVN_SERVER_NIC_MODEL) or '')

    if str(env_config.get(constants.EVN_CLIENT_NIC_MODEL) or '') != "":
        cmd = cmd + ' --cnicm %s' % str(env_config.get(constants.EVN_CLIENT_NIC_MODEL) or '')

    # server bmc ip
    server_bmc_ip = ip_config.get(constants.TEST_CONFIG_SERVER_BMC_IP)
    if server_bmc_ip is not None and server_bmc_ip != "":
        cmd = cmd + (" --sbmcip %s " % server_bmc_ip)
    else:
        log.warning("server bmc ip is not configured")

    suname = ip_config.get(constants.TEST_CONFIG_SUNAME)
    if suname is not None and suname != "":
        cmd = cmd + (" --suname %s " % suname)
    else:
        log.warning("suname is not configured")

    supasswd = ip_config.get(constants.TEST_CONFIG_SUPASSWD)
    if supasswd is not None and supasswd != "":
        cmd = cmd + (" --supasswd '%s' " % supasswd)
    else:
        log.warning("supasswd is not configured")

    # client bmc ip
    client_bmc_ip = ip_config.get(constants.TEST_CONFIG_CLIENT_BMC_IP)
    if client_bmc_ip is not None and client_bmc_ip != "":
        cmd = cmd + (" --cbmcip %s " % client_bmc_ip)
    else:
        log.warning("client bmc ip is not configured")

    cuname = ip_config.get(constants.TEST_CONFIG_CUNAME)
    if cuname is not None and cuname != "":
        cmd = cmd + (" --cuname %s " % cuname)
    else:
        log.warning("cuname is not configured")

    cupasswd = ip_config.get(constants.TEST_CONFIG_CUPASSWD)
    if cupasswd is not None and cupasswd != "":
        cmd = cmd + (" --cupasswd '%s' " % cupasswd)
    else:
        log.warning("cupasswd is not configured")

    # server com host
    com_host = ip_config.get(constants.TEST_CONFIG_SERVER_COM_IP)
    if com_host is not None and com_host != "":
        cmd = cmd + (" --scomip %s" % com_host)

    # server com port
    com_port = ip_config.get(constants.TEST_CONFIG_SERVER_COM_PORT)
    if com_port is not None and com_port != "":
        cmd = cmd + (" --scomport %s" % com_port)

    # client com host
    com_host = ip_config.get(constants.TEST_CONFIG_CLIENT_COM_IP)
    if com_host is not None and com_host != "":
        cmd = cmd + (" --ccomip %s" % com_host)

    # client com port
    com_port = ip_config.get(constants.TEST_CONFIG_CLIENT_COM_PORT)
    if com_port is not None and com_port != "":
        cmd = cmd + (" --ccomport %s" % com_port)

    cmd = cmd + ' -o %s' % script_log_output_dir
    log.info('Get execute script command: {}'.format(cmd))
    return cmd


def exec_run_script_cmd(script_cmd: str, print_flag: bool):
    """
    author: panpan.du
    date  : 2020.10.16
    description: 生成执行脚本的命令
    :param script_cmd: 脚本执行命令
    :param print_flag: 是否实时打印脚本输出信息
    :return: 执行脚本的命令
    """
    process = subprocess.Popen(script_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               encoding='utf-8')
    while True:
        # TODO 实时日志输出方式调整
        line = process.stdout.read()
        if line == '' or constants.OUTPUT_SPLIT_KEY in line:
            stdout = line
            log.info("%s " % stdout)
            break
        else:
            if print_flag:
                log.info("%s " % line.rstrip("\n\r"))
    process.wait()
    return process.returncode, stdout
