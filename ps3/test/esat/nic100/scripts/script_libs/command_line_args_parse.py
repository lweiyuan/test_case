#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      xianda.liu
date:        2022-07-16
description: 定义命令行参数解析类
"""
import argparse
import os
import pdb

from scripts.script_libs.env_config_operation import EnvConfigOperation
import configparser


class CommandLineArgsParse(object):
    """命令行参数解析"""
    parser = argparse.ArgumentParser(description="Sagitta Test.")
    # 添加命令行参数中的server ip选项
    parser.add_argument('--sip', type=str, help='指定 server ip，即收包侧ip')
    # 添加命令行参数中的server port选项，为可选项，默认为728
    parser.add_argument('--sp', default=728, type=int, help='指定 server 端口号，默认为：728 。')
    # 添加命令行参数中的server node ip选项
    parser.add_argument('--snicip', type=str, help='指定 server nic ip')
    # 添加命令行参数中的server bmc ip选项
    parser.add_argument('--sbmcip', type=str, help='指定 server bmc ip')
    # 添加命令行参数中的client ip选项
    parser.add_argument('--cip', type=str, help='指定 client ip，即发包侧ip')
    # 添加命令行参数中的client port选项，为可选项，默认为728
    parser.add_argument('--cp', default=728, type=int, help='指定 client 端口号，默认为：728 。')
    # 添加命令行参数中的com host ip选项
    parser.add_argument('--scomip', type=str, help='指定 server com host ip，物理环境，需指定该参数。')
    # 添加命令行参数中的com host port选项
    parser.add_argument('--scomport', type=str, help='指定 server com host port，物理环境，需指定该参数。')
    # 添加命令行参数中的com host ip选项
    parser.add_argument('--ccomip', type=str, help='指定 client com host ip，物理环境，需指定该参数。')
    # 添加命令行参数中的com host port选项
    parser.add_argument('--ccomport', type=str, help='指定 client com host port，物理环境，需指定该参数。')
    # 添加命令行参数中的client node ip选项
    parser.add_argument('--cnicip', type=str, help='指定 client nic ip')
    # 添加命令行参数中的client node ip选项
    parser.add_argument('--cbmcip', type=str, help='指定 client bmc ip')
    # 添加命令行参数中的server_nic_model选项
    parser.add_argument('--snicm', type=str, help='指定 server nic model')
    # 添加命令行参数中的client_nic_model选项
    parser.add_argument('--cnicm', type=str, help='指定 client nic model')
    # 添加命令行参数中的server bmc user name选项
    parser.add_argument('--suname', type=str, help='指定 server bmc user name')
    # 添加命令行参数中的server bmc password选项
    parser.add_argument('--supasswd', type=str, help='指定 server bmc password')
    # 添加命令行参数中的client bmc user name选项
    parser.add_argument('--cuname', type=str, help='指定 client bmc user name')
    # 添加命令行参数中的client bmc password选项
    parser.add_argument('--cupasswd', type=str, help='指定 client bmc password')
    # 添加命令行参数中的 log_server_ip选项，为必选项，当没有给定ip时，argparse标准库会自动报错
    parser.add_argument('--lsip', type=str, default='10.22.65.11', help='日志服务器ip地址')
    # 添加命令行参数中的log_server_account选项，为可选项，默认为framework
    parser.add_argument('--lsac', default='framework', type=str, help='日志服务器账号,选填参数,默认为framework用户')
    # 添加test entry选项，为可选项，默认为0
    parser.add_argument('--te', default=0, type=int, help='指定 test entry, 0表示网卡直连, 1表示使用交换机， 默认为0')
    # 添加命令行参数中的log保存路径 output选项，为可选项
    parser.add_argument('-o', '--output', type=str, help='指定日志保存路径, 可选参数，不指定时'
                                                         '默认保存路径: test/esat/outputs')
    # 添加命令行参数中的host_lable选项
    parser.add_argument('--hl', default='vm000', type=str, help='host_lable参数，默认为vm000')
    # host cpu架构，其中0表示x86架构，1表示arm架构，2表示mips架构
    parser.add_argument('--hc', default=0, type=int, help='指定主机cpu架构，0表示x86架构，1表示arm架构，2表示mips架构')
    # 是否开启bug_stop开关，命令行中不添加此参数时，为False，添加为True
    parser.add_argument('--bs', action='store_true', help='指定是否开启bug stop开关，可选参数，命令行中带有此参数表示有bug'
                                                          '产生时，脚本不再清理环境')
    # cli命令中是否添加trace
    parser.add_argument('--nt', action='store_true', help='指定执行cli命令时是否添加trace参数，命令行中没有此参数表示添加，'
                                                          '有此参数时，不添加')
    # 添加test object选项，10表示nic,11表示nic_with_src,12表示nic_with_src,13表示nic_with_background_triffic 默认为10
    parser.add_argument('--to', default=10, type=int, help='10表示nic,11表示nic_with_src,12表示nic_with_src,'
                                                           '13表示nic_with_background_triffic 默认为10')
    # 添加test port,如果传参后才可使用
    parser.add_argument('--tp', default=0, type=int, help='默认为0')
    # 脚本超时时长
    parser.add_argument('--timeout', default=0.5, type=float, help='指定当前脚本执行超时时长，单位为h, 默认为0.5h')
    # 临时定义框架调用的命令行参数，临时规避框架调用脚本时的命令行参数问题
    parser.add_argument('--start', action='store', type=str, dest='task_start_time',
                        help="task start time，eg: '20200423151820'")
    parser.add_argument('-t', '--total', type=int, dest='total_duration', default=0,
                        help='total duration of test task ')
    parser.add_argument('-p', '--pass', type=int, dest='pass_num', default=0, help='pass num of test scripts ')
    parser.add_argument('-f', '--fail', type=int, dest='fail_num', default=0, help='fail num of test scripts')
    parser.add_argument('-k', '--skip', type=int, dest='skip_num', default=0, help='skip num of test scripts')
    parser.add_argument('-n', '--not_exist', type=int, dest='not_exist_num', default=0,
                        help='not exist num of test scripts')
    parser.add_argument('-b', '--bug', action='store', type=str, dest='bug_excel',
                        help='bug excel file with path')
    parser.add_argument('-r', '--result', action='store', type=str, dest='result_excel',
                        help='result excel file with path')
    parser.add_argument('-l', '--logfile', action='store', type=str, default='', dest='report_log_file')
    # 添加命令行参数中的long_stab_test选项
    parser.add_argument('--lst', type=str, default='None', help='指定 long_stab_test，'
                                                                '当需要进行长稳测试时指定该参数，需指定该参数。')
    # 添加命令行参数中的日志start time选项
    parser.add_argument('--st', type=str, help="log start time，eg: '20200423151820'")
    # 添加命令行参数中的日志end time选项
    parser.add_argument('--et', type=str, help="log end time，eg: '20200423151820'")

    # 添加命令行参数中的simu选项
    parser.add_argument('-s', "--simu", action='store_true', help='当前测试为模拟平台')

    args = parser.parse_args()

    lst = None
    ltr = None
    mlk = None
    os = None
    elst = None
    exam = None
    test_obj_str = None

    @classmethod
    def get_simu(cls) -> str:
        """
        author:      xianda.liu
        date:        2022-07-16
        description: 获取命令行参数中的 server ip
        :return:     返回命令行中的sip
        """
        simu = True if cls.args.simu else False
        return simu

    @classmethod
    def get_server_ip(cls) -> str:
        """
        author:      xianda.liu
        date:        2022-07-16
        description: 获取命令行参数中的 server ip
        :return:     返回命令行中的sip
        """
        rtn_ip = cls.args.sip if cls.args.sip else ''

        return rtn_ip

    @classmethod
    def get_test_port(cls) -> int:
        """
        author:      junfeng.he
        date:        2024-02-29
        description: 获取命令行参数中的使用的ssh端口
        :return:     返回命令行中的tp
        """
        rtn_port = cls.args.tp if cls.args.tp else 0
        return rtn_port

    @classmethod
    def get_server_port(cls) -> int:
        """
        author:      xianda.liu
        date:        2022-07-16
        description: 获取命令行参数中的 server port
        :return:     返回命令行中的sp
        """
        return cls.args.sp

    @classmethod
    def get_server_nic_ip(cls) -> str:
        """
        author:      xianda.liu
        date:        2022-07-16
        description: 获取命令行参数中的 server nic ip
        :return:     返回命令行中的snip
        """
        snicip = cls.args.snicip if cls.args.snicip else ''

        return snicip

    @classmethod
    def get_server_bmc_ip(cls) -> str:
        """
        author:      xianda.liu
        date:        2022-07-16
        description: 获取命令行参数中的 server nic ip
        :return:     返回命令行中的snip
        """
        sbmcip = cls.args.sbmcip if cls.args.sbmcip else ''

        return sbmcip

    @classmethod
    def get_server_bmc_uname(cls) -> str:
        """
        author:      junfeng.he
        date:        2023-11-09
        description: 获取命令行参数中的 server bmc user name
        :return:     bmc user name
        """
        suname = cls.args.suname if cls.args.suname else ''

        return suname

    @classmethod
    def get_server_bmc_passwd(cls) -> str:
        """
        author:      junfeng.he
        date:        2023-11-09
        description: 获取命令行参数中的 server bmc passwd
        :return:     bmc passwd
        """
        supasswd = cls.args.supasswd if cls.args.supasswd else ''

        return supasswd.replace("'", "")

    @classmethod
    def get_client_ip(cls) -> str:
        """
        author:      xianda.liu
        date:        2022-07-16
        description: 获取命令行参数中的 client ip
        :return:     返回命令行中的cip
        """
        rtn_ip = cls.args.cip if cls.args.cip else ''

        return rtn_ip

    @classmethod
    def get_client_port(cls) -> int:
        """
        author:      xianda.liu
        date:        2022-07-16
        description: 获取命令行参数中的 client port
        :return:     返回命令行中的cp
        """
        return cls.args.cp

    @classmethod
    def get_client_nic_ip(cls) -> str:
        """
        author:      xianda.liu
        date:        2022-07-16
        description: 获取命令行参数中的 client nic ip
        :return:     返回命令行中的cnip
        """
        cnicip = cls.args.cnicip if cls.args.cnicip else ''

        return cnicip

    @classmethod
    def get_client_bmc_ip(cls) -> str:
        """
        author:      xianda.liu
        date:        2022-07-16
        description: 获取命令行参数中的 client nic ip
        :return:     返回命令行中的cnip
        """
        cbmcip = cls.args.cbmcip if cls.args.cbmcip else ''

        return cbmcip

    @classmethod
    def get_client_bmc_uname(cls) -> str:
        """
        author:      junfeng.he
        date:        2023-11-09
        description: 获取命令行参数中的 client bmc user name
        :return:     bmc user name
        """
        cuname = cls.args.cuname if cls.args.cuname else ''

        return cuname

    @classmethod
    def get_client_bmc_passwd(cls) -> str:
        """
        author:      junfeng.he
        date:        2023-11-09
        description: 获取命令行参数中的 client bmc passwd
        :return:     bmc passwd
        """
        cupasswd = cls.args.cupasswd if cls.args.cupasswd else ''

        return cupasswd.replace("'", "")

    @classmethod
    def get_server_com_ip(cls) -> str:
        """
        author:      hejf
        date:        2025-07-12 14:11:59
        description: 获取命令行参数中的scomip的值，即 server com ip,串口主机IP
        :return:     返回命令行中的scomip的值, 未设置时，返回''
        """
        rtn_ip = cls.args.scomip if cls.args.scomip else ''

        return rtn_ip

    @classmethod
    def get_server_com_port(cls) -> str:
        """
        author:      hejf
        date:        2025-07-12 14:11:59
        description: 获取命令行参数中的scomport的值，即 server com port,串口port
        :return:     返回命令行中的scomport的值, 未设置时，返回''
        """
        rtn_port = cls.args.scomport if cls.args.scomport else ''

        return rtn_port

    @classmethod
    def get_client_com_ip(cls) -> str:
        """
        author:      hejf
        date:        2025-07-12 14:11:59
        description: 获取命令行参数中的scomip的值，即 server com ip,串口主机IP
        :return:     返回命令行中的scomip的值, 未设置时，返回''
        """
        rtn_ip = cls.args.ccomip if cls.args.ccomip else ''

        return rtn_ip

    @classmethod
    def get_client_com_port(cls) -> str:
        """
        author:      hejf
        date:        2025-07-12 14:11:59
        description: 获取命令行参数中的scomport的值，即 server com port,串口port
        :return:     返回命令行中的scomport的值, 未设置时，返回''
        """
        rtn_port = cls.args.ccomport if cls.args.ccomport else ''

        return rtn_port

    @classmethod
    def get_test_entry(cls) -> int:
        """
        author:      haibin.xu
        date:        2020-12-01 15:22:53
        description: 获取命令行参数中的 test entry
        :return:     返回命令行中的 test entry，未设置时，默认为0
        """
        return cls.args.te

    @classmethod
    def get_test_object(cls) -> int:
        """
        author:      haibin.xu
        date:        2021-01-12 14:20:04
        description: 获取命令行参数中的 test object 值
        :return:     返回命令行参数中的 test object，未设置时，默认为0
        """
        return cls.args.to

    @classmethod
    def get_log_output_path(cls) -> str:
        """
        author:      haibin.xu
        date:        2020-09-03 19:31:56
        description: 获取log保存路径
        :return:     指定路径时，返回log保存路径，未指定时，返回‘’
        """
        rtn_log_output_path = ''
        if cls.args.output:
            rtn_log_output_path = cls.args.output

        return rtn_log_output_path

    @classmethod
    def get_bug_stop_flag(cls) -> bool:
        """
        author:      haibin.xu
        date:        2020-11-05 11:36:10
        description: 获取bug stop参数，带有--bs，表示脚本测试报bug时，不再清理当前环境，不带--bs时，
                     表示脚本测试报bug时，继续清理当前环境

        :return:     带有--bs时返回True，否则返回False
        """
        return cls.args.bs

    @classmethod
    def get_no_trace_flag(cls) -> bool:
        """
        author:      haibin.xu
        date:        2020-11-12 15:52:19
        description: 获取no trace参数，带有--nt, 表示脚本中的cli命令不追加trace参数，没有--nt,表示追加trace参数

        :return:     带有--nt时返回True，否则返回False
        """
        # return cls.args.nt
        return False

    @classmethod
    def get_script_name(cls) -> str:
        """
        author:      haibin.xu
        date:        2020-09-08 14:52:25
        description: 获取脚本名称
        :return:     返回执行的脚本名
        """
        return cls.parser.prog

    @classmethod
    def get_host_cpu(cls) -> int:
        """
        author:      haibin.xu
        date:        2020-11-21 15:59:50
        description: 获取host cpu架构

        :return:     返回host cpu架构
        """
        return cls.args.hc

    @classmethod
    def get_log_server_ip(cls) -> str:
        """
        author:      haibin.xu
        date:        2021-04-01 17:56:53
        description: 获取日志服务器 ip

        :return:     返回日志服务器ip
        """
        return cls.args.lsip

    @classmethod
    def get_log_server_account(cls) -> str:
        """
        author:      haibin.xu
        date:        2021-04-01 17:58:17
        description: 获取日志服务器用户名

        :return:     返回日志服务器用户名
        """
        return cls.args.lsac

    @classmethod
    def get_script_timeout(cls) -> int:
        """
        author:      haibin.xu
        date:        2021-08-11 10:23:47
        description: 获取脚本执行超时时长 timeout参数

        :return:     返回转换为s的超时时长
        """
        try:
            return int(float(cls.args.timeout) * 3600)
        except Exception:
            return 1800

    @classmethod
    def get_is_log_trace(cls) -> bool:
        """
        author:      sunql
        date:        2021-08-18 10:23:47
        description: 获取是否开启日志trace

        :return:    bool
        """
        if cls.ltr is None:
            if cls.args.ltr == 'True':
                cls.ltr = True
            else:
                cls.ltr = False

        return cls.ltr

    @classmethod
    def get_log_start_time(cls) -> str:
        """
        author:      kaifeng.bi
        date:        2021-09-28 19:07:48
        description: 获取命令行参数中的 log start time
        :return:     返回命令行中的start time

        """
        st = cls.args.st if cls.args.st else ''

        return st

    @classmethod
    def get_log_end_time(cls) -> str:
        """
        author:      kaifeng.bi
        date:        2021-09-28 19:07:48
        description: 获取命令行参数中的 sanblaze ip
        :return:     返回命令行中的ip

        """
        et = cls.args.et if cls.args.et else ''

        return et

    @classmethod
    def get_is_long_stability(cls) -> bool:
        """
        author:      sunql
        date:        2021-08-18 10:23:47
        description: 获取是否长稳参数

        :return:     返回是否长稳
        """
        if cls.lst is None:
            if cls.args.lst == 'True':
                cls.lst = True
            else:
                cls.lst = False

        return cls.lst

    @classmethod
    def get_host_os(cls) -> bool:
        """
        author:      sunql
        date:        2021-11-8 10:23:47
        description: 获取host_os

        :return:     返回host_os
        """
        if cls.os is None:
            cls.os = str(EnvConfigOperation().get_config_item('host_os') or '').strip()
            if cls.os == "":
                cls.os = "centos8.2"
        return cls.os

    @classmethod
    def get_server_nic_model(cls) -> str:
        return cls.args.snicm

    @classmethod
    def get_client_nic_model(cls) -> str:
        return cls.args.cnicm

    @classmethod
    def get_nic_os_type(cls) -> tuple:
        """
        从配置文件获取测试方向是否反向，并且从参数中获取os type
        :return:
        """
        NIC_SCRIPT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        NIC_CONFIG_PATH = os.path.join(NIC_SCRIPT_PATH, 'nic_driver_config.ini')
        NIC_CONFIG_BK_PATH = os.path.join(NIC_SCRIPT_PATH, 'env_config.ini')

        config = configparser.ConfigParser()
        try:
            config.read(NIC_CONFIG_BK_PATH)
            # 验证字典是否已将正确读取配置文件，如果没有读取到，会报异常
            _ = config['nic_driver']
        except Exception as e:
            print('读取 {} 文件 异常，切换为默认值'.format(NIC_CONFIG_BK_PATH))
            config = {
                'nic_driver': {
                    'server': 'sxe2,sxe2vf',
                    'client': 'mlx5_core,mlx5_core'
                },
                'nic_os': {
                    'server': 'linux',
                    'client': 'linux'
                },
                'logical_ip': {
                    'server': '10.100.194.204',
                    'client': '10.100.194.209'
                },
                'platform': {
                    'server': 'ASIC-CRB-PCIEx2',
                    'client': 'none'
                },
                'serial_port_pos': {
                    'server': 'developer@10.22.67.5_10.100.194.221_5100',
                    'client': 'none'
                },
                'relationships': {
                    'server': 'ens4f0',
                    'client': 'enp35s0f0np0'
                },
                'nic_driver_rdma': {
                    'server': 'sxe2_rdma',
                    'client': 'mlx5_ib'
                },
                'relationships_rdma': {
                    'server': 'sxe2_rdma0',
                    'client': 'mlx5_0'
                }
            }
        server_logical_ip_org, client_logical_ip_org = config['logical_ip']['server'], config['logical_ip']['client']

        config = configparser.ConfigParser()
        try:
            config.read(NIC_CONFIG_PATH)
            # 验证字典是否已将正确读取配置文件，如果没有读取到，会报异常
            _ = config['nic_driver']
        except Exception as e:
            print('读取 {} 文件 异常，切换为默认值'.format(NIC_CONFIG_PATH))
            config = {
                'nic_driver': {
                    'server': 'sxe2,sxe2vf',
                    'client': 'mlx5_core,mlx5_core'
                },
                'nic_os': {
                    'server': 'linux',
                    'client': 'linux'
                },
                'logical_ip': {
                    'server': '10.100.194.204',
                    'client': '10.100.194.209'
                },
                'platform': {
                    'server': 'ASIC-CRB-PCIEx2',
                    'client': 'none'
                },
                'serial_port_pos': {
                    'server': 'developer@10.22.67.5_10.100.194.221_5100',
                    'client': 'none'
                },
                'relationships': {
                    'server': 'ens4f0',
                    'client': 'enp35s0f0np0'
                },
            }

        server_nic_logical_ip, client_nic_logical_ip = config['logical_ip']['server'], config['logical_ip']['client']

        if server_logical_ip_org == client_nic_logical_ip and client_logical_ip_org == server_nic_logical_ip:
            # 已反向
            server_os_type, client_os_type = \
                CommandLineArgsParse.get_client_nic_model(), CommandLineArgsParse.get_server_nic_model()
        else:
            server_os_type, client_os_type = \
                CommandLineArgsParse.get_server_nic_model(), CommandLineArgsParse.get_client_nic_model()
        return server_os_type, client_os_type
