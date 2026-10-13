# -*- encoding=utf8 -*-
"""
description: 用于测试项目中使用的常量信息
"""

ENV_SWITCH_LABEL = 'switch_label'
EVN_SERVER_NIC_MODEL = 'server_nic_model'
EVN_CLIENT_NIC_MODEL = 'client_nic_model'
ENV_FIREWALLD = "firewalld"
ENV_TEST_ENTRY = "test_entry"
DIRECT = 'direct'
SWITCH = 'switch'
SINGLE_MODE = 'single_mode'
UEFI_MODE = 'uefi_mode'
DPDK_MODE = 'dpdk_mode'
DPDK_AUTO_MODE = 'dpdk_auto_mode'
VF_KEEP_MODE = 'vf_keep_mode'


WINDOWS_FILE_PATH_ROOT = 'C:/Users/Administrator/sxetest/'
LINUX_FILE_PATH_ROOT = '/root/sxetest/'
FIREWALL_FILE = "firewall_setting.ps1"

WINDOWS_ABNORMAL_BK_PATH = 'C:/Users/Administrator/sxetest/nic_abnormal'
LINUX_ABNORMAL_BK_PATH = '/home/nic_abnormal'

Testles_CASE_FILE = "ib_auto_tc.csv"
Testles_FAILED_CASE_FILE = "ib_failed_tc.csv"
Testles_ZENTO_CASE_FILE = "sagitta_test_case_list.csv"

RDMA_BITFILES = ['0c', '14', '15']

SIMU_ROOT_PATH = "/var/nic_sim"
SIMU_CONFIG = "{}/sim_conf.xml".format(SIMU_ROOT_PATH)
SIMU_SCRIPT = "{}/deploy_sim.py".format(SIMU_ROOT_PATH)
