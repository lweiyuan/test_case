import os
import random
import uuid
import add_syspath
import re

from scripts.script_libs.command_line_args_parse import CommandLineArgsParse
import configparser


ESAT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ESAT_PATH_OUT_PUTS_SCRIPTS_PATH = os.path.join(ESAT_PATH, 'outputs', 'scripts')

NIC_SCRIPT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NIC_CONFIG_PATH = os.path.join(NIC_SCRIPT_PATH, 'nic_driver_config.ini')
NIC_CONFIG_BK_PATH = os.path.join(NIC_SCRIPT_PATH, 'env_config.ini')

config = configparser.ConfigParser()
# modify code 2025-12-18 09:56:39 haibin.xu add: 配置文件不存在时，捕获异常，并将对应变量赋值为默认值
try:
    config.read(NIC_CONFIG_BK_PATH)
    # 验证字典是否已将正确读取配置文件，如果没有读取到，会报异常
    _ = config['nic_driver']
except Exception as e:
    print('读取 env_config.ini文件 异常，切换为默认值')
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

nicg = config['nic_driver']['server'].split(",")[0]
if 'nic_driver_rdma' in config:
    nicrg = config['nic_driver_rdma']['server'].split(",")[0]
else:
    nicrg = f'{nicg}rdma' if nicg != 'scgbe' else f'{nicg}_rdma'

platform_server = config['platform']['server']

if 'ocpx2' in platform_server.lower():
    subsystem = "1ff2:0c22"
elif 'ocpx4' in platform_server.lower():
    subsystem = "1ff2:0c23"
elif 'pcie10' in platform_server.lower():
    subsystem = "1ff2:0c24"
else:
    subsystem = "1ff2:0c21"
if 'ocpx2' in platform_server.lower():
    pci_speed = "16GT/s"
elif 'ocpx4' in platform_server.lower():
    pci_speed = "32GT/s"
else:
    pci_speed = "16GT/s"
pci_width = "x8"
if 'ASIC' in platform_server:
    is_fpga = False
else:
    is_fpga = True
if 'ASIC-NCD-HFx1' in platform_server:
    is_hf = True
else:
    is_hf = False

cur_path = os.path.abspath(os.path.dirname(__file__))
num_list = re.findall(r'([vp]m\d+)', cur_path)
if num_list and ('vm' in num_list[0] or 'pm' in num_list[0]):
    vm = num_list[0]
    if len(vm) < 2 + 4:
        rpc_port_value = "8" + vm.replace("vm", "").replace("pm", "")
    else:
        rpc_port_value = vm.replace("vm", "").replace("pm", "")
else:
    vm = "vm999"
    rpc_port_value = "8888"
vm_path = "/root/sxetest/{}".format(vm)
windows_iso_file = "C:/Users/Administrator/Downloads/zh-cn_windows_server_2022_updated_oct_2022_x64_dvd_884ce1ea.iso"

# debug版本vf创建过多回导致问题，顾做一个最大限制
DEBUG_VF_NUM = 4

"""
命令行参数常量
"""
# 规定server_ip为发包侧，client_ip为收包侧
# SERVER_IP = CommandLineArgsParse.get_server_ip()
SERVER_NODE_IP = CommandLineArgsParse.get_server_nic_ip()
SERVER_PORT = CommandLineArgsParse.get_server_port()
# CLIENT_IP = CommandLineArgsParse.get_client_ip()
CLIENT_NODE_IP = CommandLineArgsParse.get_client_nic_ip()
CLIENT_PORT = CommandLineArgsParse.get_client_port()
NO_TRACE_FLAG = CommandLineArgsParse.get_no_trace_flag()
PCAP_PATH = CommandLineArgsParse.get_log_output_path()
HOST_OS = CommandLineArgsParse.get_host_os()
IS_SIMU = CommandLineArgsParse.get_simu()

SERVER_COM_IP = CommandLineArgsParse.get_server_com_ip()
SERVER_COM_PORT = CommandLineArgsParse.get_server_com_port()
CLIENT_COM_IP = CommandLineArgsParse.get_client_com_ip()
CLIENT_COM_PORT = CommandLineArgsParse.get_client_com_port()

if 'windows' in HOST_OS:
    FILE_PATH_ROOT = 'C:/Users/Administrator/sxetest/'
else:
    # 用于在测试机上存储测试生成文件的linux根路径，文件操作只对该目录及其子目录下的文件有效，
    # 脚本基类会检测该目录是否存在，不存在情况下，自动创建
    FILE_PATH_ROOT = '/root/sxetest/'

WINDOWS_FILE_PATH_ROOT = 'C:/Users/Administrator/sxetest/'
LINUX_FILE_PATH_ROOT = '/root/sxetest/'
WINDOWS_TSHARK_PATH = 'C:/Program Files/Wireshark/tshark.exe'

# windows收发包小脚本的日志目录
LOG_FILE_DIR = 'win_package_process_log/'
LOG_FILE_PATTERN = r'win_package_process_output_(\d+)_(\d+)_(\d+)_(\d+)_(\d+)_(\d+)_test.log'
LOG_PATH_WIN = WINDOWS_FILE_PATH_ROOT + vm + "/" + LOG_FILE_DIR
LOG_PATH_LINUX = LINUX_FILE_PATH_ROOT + vm + "/" + LOG_FILE_DIR

# IP地址的正则表达式
PATTERN_IP = r'(25[0-5]|2[0-4]\d|[0-1]\d{2}|[1-9]?\d)\.(25[0-5]|2[0-4]\d|[0-1]\d{2}|[1-9]?\d)\.' \
             r'(25[0-5]|2[0-4]\d|[0-1]\d{2}|[1-9]?\d)\.(25[0-5]|2[0-4]\d|[0-1]\d{2}|[1-9]?\d)'

# 测试环境预留端口号, 8880-8889 -> 8000-9999,适配多dut对一test端场景
RESERVED_PORT = list(range(8000, 9999))
# RPC使用端口号默认8888
RPC_PORT = int(rpc_port_value)
# iperf使用默认端口号8889 -> 9889
IPERF_PORT = 9889
IPERF2_PORT = 9888
# socket使用默认端口号8887 -> 9887
SOCKET_PORT = 9887
SOCKET_PORT_LIST = list(range(32768, 60999))
# VLAN默认IP地址段，client、server 192.168.200.*
RESERVED_VLAN_IP_HEADER = '192.168.200.'
# MACVLAN默认IP地址段，client、server 192.168.150.*
RESERVED_MACVLAN_IP_HEADER = '192.168.150.'
# VF默认IP地址段，client、server 192.168.180.*
RESERVED_VF_IP_HEADER = '192.168.180.'
# VF默认IPv6地址段，client、server 2000::
RESERVED_VF_IPV6_HEADER = '2000::'
# 修改vlan mac地址时预留, client、server共用
RESERVED_VLAN_MAC_HEADER = '11:22:'
RESERVED_VLAN_MAC_HEADER_OTHER = '01:22:'
MAC_HEADER_SXE = 'e4:b6:33:'
MAC_HEADER_IXGBE = 'e8:61:1f:'
MULTICAST_HEADER = "01:00:5E:"
MAC_BROADCAST = "ff:ff:ff"

UNLINK_REBOOT_FLAG = False

COM_LOG_DIR = '/home/framework/other'

DPDK_SCREEN_NAME = "dpdktest"
SCREEN_LOG_PATH = "/home/dpdkscreenlog"
SCREEN_LOG_COLLECT_PATH = "/root/sxetest/"
SCREEN_LOG_NAME = "screenlog.0"
PKTGEN_AVAILABLE_CORE_INFO = "/root/sxetest/pktgen/available_core_info.txt"

# socket使用脚本路径
SOCKET_CLIENT_PATH = '{}/send_packet.py'.format(vm_path)
SOCKET_SERVER_PATH = '{}/receive_packet.py'.format(vm_path)

# rpc框架使用脚本路径
RPC_PATH = '{}/rpc_server.py'.format(vm_path)

# 片外cli升级包路径
UPGRADE_TAR_PATH = '/root/sxetest/upgrade_test_tar'
SAME_VERSION_TAR_PATH = '/root/sxetest/same_version_test_tar'
# 解压后升级包路径
RELEASE_VERSION = '/root/sxetest/publish_version/release_version.txt'
PACKAGE_PATH = '/root/sxetest/publish_version/'
PACKAGE_LAST_PATH = '/root/sxetest/publish_version_last/'
if is_fpga:
    NOR_FLASH_PKG_PATH = '/root/sxetest/publish_version/factory/Firmware/1260-X/norflashRegion*Fpga_*.*.*.*.bin'
else:
    NOR_FLASH_PKG_PATH = '/root/sxetest/publish_version/factory/Firmware/1260-X/norflashRegion*asic_*.*.*.*.bin'
UPGRADE_IMAGE_PACKAGE_PATH = ('/root/sxetest/publish_version/products/Firmware/Standard-Products/1260-X'
                              '/Image_*.*.*.*_NIC-1260-X.bin')
UPGRADE_IMAGE_PACKAGE_BAK_PATH = ('/root/sxetest/publish_version/technical_support/Firmware/Standard-Products_bak/'
                                  'Image_*.*.*.*_BAK_NIC-1260-X.bin')
UPGRADE_IMAGE_PACKAGE_WIN_PATH = \
    'C:\\Users\\Administrator\\sxetest\\publish_version\\sxe_fw_asic\\debug\\sxe_fw_asic_image_package.bin'
CFGTOOLS_PATH = '/root/sxetest/publish_version/technical_support/Firmware/Tools/cfgTools'
PS3_MAKE_PACKAGE = '/root/sxetest/publish_version/technical_support/Firmware/Tools/pkgTools/ps3_make_package.py'
# HEADER_BIN_OUTPUT = '/root/sxetest/publish_version/debuginfo/sxe_fw_asic/pkgTools/tools/package/sm23Sign/output/'
if is_fpga:
    HEADER_BIN_OUTPUT = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_fpga/pkgTools/output/'
else:
    HEADER_BIN_OUTPUT = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/pkgTools/output/'
HEADER_UBOOT_OUTPUT = ('/root/sxetest/publish_version/debuginfo/sxe_fw_asic/pkgTools/tools/package/sm23Sign/output/'
                       'header_config_sxe_fw_bootloader_bootloader_sxe_fw_asic.bin')
# SM23SIGN_DIR = '/root/sxetest/publish_version/debuginfo/sxe_fw_asic/pkgTools/tools/package/sm23Sign/'
# code review 2025/8/12 jhe: 修改路径
if is_fpga:
    SM23SIGN_DIR = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_fpga/pkgTools/'
else:
    SM23SIGN_DIR = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/pkgTools/'
ADD_HEADER_DIR = SM23SIGN_DIR
# USER_ADD_HEADER = \
#     '/root/sxetest/publish_version/debuginfo/sxe_fw_asic/pkgTools/tools/package/sm23Sign/user_add_header.sh'
if is_fpga:
    USER_ADD_HEADER = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_fpga/pkgTools/user_add_header.sh'
else:
    USER_ADD_HEADER = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/pkgTools/user_add_header.sh'
if is_fpga:
    USER_ADD_HEADER = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_fpga/pkgTools/user_add_header.sh'
else:
    USER_ADD_HEADER = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/pkgTools/user_add_header.sh'
CSV2BIN_PY = '/root/sxetest/publish_version/debuginfo/sxe_fw_asic/cfgTools/csv2bin.py'
SXE_CSV = '/root/sxetest/publish_version/debuginfo/sxe_fw_asic/cfgTools/csv/asic/sxe.csv'
SXE_USER_CSV = '/root/sxetest/publish_version/debuginfo/sxe_fw_asic/cfgTools/csv/sxeUser.csv'
PS3_CFG_SXESBR = '/root/sxetest/publish_version/debuginfo/sxe_fw_asic/cfgTools/ps3_cfg_sxesbr.h'
SXE_SBR_CSV = '/root/sxetest/publish_version/debuginfo/sxe_fw_asic/cfgTools/csv/asic/sxeSbr.csv'
SXE_OPROM_ROM = '/root/sxetest/publish_version/debuginfo/uefi/debug/x64/sxe_oprom.rom'

# HEADER_BOOTLOADER_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/' \
#                         'header_bootloader.bin'
HEADER_BOOTLOADER_BIN_OLD = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/' \
                            'header_bootloader.bin'
HEADER_FW_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/header_sxe_fw.bin'

BOOTLOADER_BIN = '/root/sxetest/publish_version/debuginfo/sxe_fw_asic/debug/bootloader_sxe_fw_asic.bin'

if 'ocpx2' in platform_server.lower():
    HEADER_FW_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-2A/header_{nicg}_fw.bin'
    HEADER_FW0_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-2A/header_{nicg}_fw_asic_0.bin'
    HEADER_FW1_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-2A/header_{nicg}_fw_asic_1.bin'
    HEADER_FW2_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-2A/header_{nicg}_fw_asic_2.bin'
    HEADER_FW3_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-2A/header_{nicg}_fw_asic_3.bin'
    HEADER_FW4_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-2A/header_{nicg}_fw_asic_4.bin'
    HEADER_FW5_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-2A/header_{nicg}_fw_asic_5.bin'

    HEADER_NVDATA_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-2A/' \
                        'header_config_nvdata.bin'
    HEADER_NVDATA_BIN_SCGBE =  '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-2A/' \
                        'header_config_nvdata.bin'
    HEADER_USERDEFAULT_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-2A/' \
                             'header_config_userDefault.bin'
    HEADER_USERDEFAULT_BIN_SCGBE = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-2A/' \
                                   'header_config_userDefault.bin'
    HEADER_OPROM_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-2A/' \
                       'header_sxe_oprom.bin'
    HEADER_OPROM_BIN_SCGBE = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-2A/' \
                             f'header_{nicg}_oprom.bin'
    HEADER_OPROM_BIN_SCGBE_OLD = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-2A/' \
                                 f'header_{nicg}_oprom.bin'

    BOOTLOADER_BIN = '/root/sxetest/publish_version/debuginfo/sxe_fw_asic/debug/bootloader_sxe_fw_asic.bin'
    HEADER_BOOTLOADER_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-2A/' \
                             'header_bootloader.bin'


elif 'ocpx4' in platform_server.lower():
    HEADER_FW_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-4A/header_{nicg}_fw.bin'
    HEADER_FW0_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-4A/header_{nicg}_fw_asic_0.bin'
    HEADER_FW1_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-4A/header_{nicg}_fw_asic_1.bin'
    HEADER_FW2_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-4A/header_{nicg}_fw_asic_2.bin'
    HEADER_FW3_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-4A/header_{nicg}_fw_asic_3.bin'
    HEADER_FW4_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-4A/header_{nicg}_fw_asic_4.bin'
    HEADER_FW5_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-4A/header_{nicg}_fw_asic_5.bin'

    HEADER_NVDATA_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-4A/' \
                        'header_config_nvdata.bin'
    HEADER_NVDATA_BIN_SCGBE = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-4A/' \
                              'header_config_nvdata.bin'
    HEADER_USERDEFAULT_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-4A/' \
                             'header_config_userDefault.bin'
    HEADER_USERDEFAULT_BIN_SCGBE = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-4A/' \
                                   'header_config_userDefault.bin'
    HEADER_OPROM_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-4A/' \
                       'header_sxe_oprom.bin'
    HEADER_OPROM_BIN_SCGBE = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-4A/' \
                             f'header_{nicg}_oprom.bin'
    HEADER_OPROM_BIN_SCGBE_OLD = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-4A/' \
                                 f'header_{nicg}_oprom.bin'
    HEADER_BOOTLOADER_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1263-4A/' \
                     'header_bootloader.bin'
elif 'pcie10' in platform_server.lower():
    HEADER_FW_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260C-2X/header_{nicg}_fw.bin'
    HEADER_FW0_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260C-2X/header_{nicg}_fw_asic_0.bin'
    HEADER_FW1_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260C-2X/header_{nicg}_fw_asic_1.bin'
    HEADER_FW2_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260C-2X/header_{nicg}_fw_asic_2.bin'
    HEADER_FW3_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260C-2X/header_{nicg}_fw_asic_3.bin'
    HEADER_FW4_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260C-2X/header_{nicg}_fw_asic_4.bin'
    HEADER_FW5_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260C-2X/header_{nicg}_fw_asic_5.bin'

    HEADER_NVDATA_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260C-2X/' \
                        'header_config_nvdata.bin'
    HEADER_NVDATA_BIN_SCGBE = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260C-2X/' \
                              'header_config_nvdata.bin'
    HEADER_USERDEFAULT_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260C-2X/' \
                             'header_config_userDefault.bin'
    HEADER_USERDEFAULT_BIN_SCGBE = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260C-2X/' \
                                   'header_config_userDefault.bin'
    HEADER_OPROM_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260C-2X/' \
                       'header_sxe_oprom.bin'
    HEADER_OPROM_BIN_SCGBE = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260C-2X/' \
                             f'header_{nicg}_oprom.bin'
    HEADER_OPROM_BIN_SCGBE_OLD = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260C-2X/' \
                                 f'header_{nicg}_oprom.bin'
    HEADER_BOOTLOADER_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260C-2X/' \
                     'header_bootloader.bin'
else:
    HEADER_FW_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260-2A/header_{nicg}_fw.bin'
    HEADER_FW0_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260-2A/header_{nicg}_fw_asic_0.bin'
    HEADER_FW1_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260-2A/header_{nicg}_fw_asic_1.bin'
    HEADER_FW2_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260-2A/header_{nicg}_fw_asic_2.bin'
    HEADER_FW3_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260-2A/header_{nicg}_fw_asic_3.bin'
    HEADER_FW4_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260-2A/header_{nicg}_fw_asic_4.bin'
    HEADER_FW5_BIN_SCGBE = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260-2A/header_{nicg}_fw_asic_5.bin'
    HEADER_NVDATA_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260-2A/' \
                        'header_config_nvdata.bin'
    HEADER_NVDATA_BIN_SCGBE = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260-2A/' \
                              'header_config_nvdata.bin'
    HEADER_USERDEFAULT_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260-2A/' \
                             'header_config_userDefault.bin'
    HEADER_USERDEFAULT_BIN_SCGBE = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260-2A/' \
                                   'header_config_userDefault.bin'
    HEADER_OPROM_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260-2A/' \
                       'header_sxe_oprom.bin'
    HEADER_OPROM_BIN_SCGBE = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260-2A/' \
                             f'header_{nicg}_oprom.bin'
    HEADER_OPROM_BIN_SCGBE_OLD = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260-2A/' \
                                 f'header_{nicg}_oprom.bin'

    HEADER_BOOTLOADER_BIN = '/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/1260-2A/' \
                     'header_bootloader.bin'



HEADER_FW_BIN_SCGBE_OLD = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/header_{nicg}_fw.bin'

HEADER_FW0_BIN_SCGBE_OLD = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/header_{nicg}_fw_asic_0.bin'
HEADER_FW1_BIN_SCGBE_OLD = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/header_{nicg}_fw_asic_1.bin'
HEADER_FW2_BIN_SCGBE_OLD = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/header_{nicg}_fw_asic_2.bin'
HEADER_FW3_BIN_SCGBE_OLD = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/header_{nicg}_fw_asic_3.bin'
HEADER_FW4_BIN_SCGBE_OLD = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/header_{nicg}_fw_asic_4.bin'
HEADER_FW5_BIN_SCGBE_OLD = f'/root/sxetest/publish_version/technical_support/Firmware/1260-X/Image_NIC-1260-X/header_{nicg}_fw_asic_5.bin'




if is_fpga:
    BOOTLOADER_BIN_SCGBE = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_fpga/debug/bootloader_{nicg}_fpga.bin'
else:
    BOOTLOADER_BIN_SCGBE = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/debug/bootloader_{nicg}_asic.bin'
# FW_BIN = '/root/sxetest/publish_version/deRbuginfo/sxe_fw_asic/debug/firmware/sxe_fw_asic.bin'
if is_fpga:
    FW_BIN = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_fpga/debug/firmware/{nicg}_fw_' + 'fpga{}.bin'
else:
    FW_BIN = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/debug/firmware/{nicg}_fw_' + 'asic_0.bin'
    FW_BIN1 = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/debug/firmware/{nicg}_fw_' + 'asic_1.bin'
    FW_BIN2 = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/debug/firmware/{nicg}_fw_' + 'asic_2.bin'
    FW_BIN3 = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/debug/firmware/{nicg}_fw_' + 'asic_3.bin'
    FW_BIN4 = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/debug/firmware/{nicg}_fw_' + 'asic_4.bin'
    FW_BIN5 = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/debug/firmware/{nicg}_fw_' + 'asic_5.bin'
NVDATA_BIN = '/root/sxetest/publish_version/debuginfo/sxe_fw_asic/debug/nvdata.bin'
USERDEFAULT_BIN = '/root/sxetest/publish_version/debuginfo/sxe_fw_asic/debug/userDefault.bin'
if is_fpga:
    RECOVERY_BIN = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_fpga/debug/header_recovery_{nicg}_fw.bin'
    # BOOTLOADER_TXT = '/root/sxetest/publish_version/debuginfo/sxe_fw_asic/pkgTools/header_config_sxe_fw_bootloader.txt'
    BOOTLOADER_TXT = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_fpga/pkgTools/comm_tool/header_config_bootloader_3m.txt'
    OPTIONROM_TXT = f'/root/sxetest/publish_version/debuginfo/{nicg}fw_fpga/pkgTools/comm_tool/header_config_{nicg}_optionrom_3m.txt'
    NVDATA_TXT = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_fpga/pkgTools/comm_tool/header_config_{nicg}_nvdata.txt'
    USERDEFAULT_TXT = f'/root/sxetest/publish_version/debuginfo/{nicg}fw_fpga/pkgTools/comm_tool/header_config_{nicg}_oem.txt'
    # FW_TXT = '/root/sxetest/publish_version/debuginfo/sxe_fw_asic/pkgTools/header_config_sxe_fw.txt'
    FW_TXT = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_fpga/pkgTools/comm_tool/header_config_{nicg}_fw.txt'

    # SIGNPACK_PY = '/root/sxetest//publish_version/debuginfo/sxe_fw_asic/pkgTools/tools/package/sm23Sign/signPack.py'
    SIGNPACK_PY = f'sxetest/publish_version/debuginfo/{nicg}_fw_fpga/pkgTools/signPack.py'
else:
    RECOVERY_BIN = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/debug/header_recovery_{nicg}_fw.bin'
    # BOOTLOADER_TXT = '/root/sxetest/publish_version/debuginfo/sxe_fw_asic/pkgTools/header_config_sxe_fw_bootloader.txt'
    BOOTLOADER_TXT = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/pkgTools/comm_tool/header_config_bootloader_6m.txt'
    OPTIONROM_TXT = f'/root/sxetest/publish_version/debuginfo/{nicg}fw_asic/pkgTools/comm_tool/header_config_{nicg}_optionrom_6m.txt'
    NVDATA_TXT = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/pkgTools/comm_tool/header_config_{nicg}_nvdata.txt'
    USERDEFAULT_TXT = f'/root/sxetest/publish_version/debuginfo/{nicg}fw_asic/pkgTools/comm_tool/header_config_{nicg}_oem.txt'
    # FW_TXT = '/root/sxetest/publish_version/debuginfo/sxe_fw_asic/pkgTools/header_config_sxe_fw.txt'
    FW_TXT = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/pkgTools/comm_tool/header_config_{nicg}_fw.txt'
    FW_TXT0 = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/pkgTools/comm_tool/header_config_{nicg}_fw.txt'
    FW_TXT1 = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/pkgTools/comm_tool/header_config_{nicg}_fw2.txt'
    FW_TXT2 = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/pkgTools/comm_tool/header_config_{nicg}_fw3.txt'
    FW_TXT3 = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/pkgTools/comm_tool/header_config_{nicg}_fw4.txt'
    FW_TXT4 = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/pkgTools/comm_tool/header_config_{nicg}_fw5.txt'
    FW_TXT5 = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/pkgTools/comm_tool/header_config_{nicg}_fw6.txt'

    # SIGNPACK_PY = '/root/sxetest//publish_version/debuginfo/sxe_fw_asic/pkgTools/tools/package/sm23Sign/signPack.py'
    SIGNPACK_PY = f'sxetest/publish_version/debuginfo/{nicg}_fw_asic/pkgTools/signPack.py'
# 片内cli工具路径
SERIAL_CLI_PY = '/root/sagitta_serial_cli.py'
SXECLI_DEBUG_PATH = '/root/sxetest/publish_version/sxe_cli/debug/x86_64/sxeclid_0.3.3.1_x86_64'

PS3_IMAGE_PACKAGE = 'ps3_image_package.bin'
# 待测版本(即发布版本)升级包路径
PUBLISH_TAR_PATH = '/root/sxetest/publish_tar'
# 当前tar包路径
CURRENT_TAR_PATH = '/root/sxetest/current_tar'
# dpdk使用的app路径
# DPDK_APP_PATH = '/dpdktest/dpdk-stable-20.11.5/build/app'
# DPDK_APP_PATH = '/root/sxetest/publish_version/dpdk/dpdk_debug'
DPDK_APP_PATH = '/root/sxetest/dpdk'
DPDK_PKTGEN_PATH = '/root/sxetest/pktgen'
PKTGEN_LOG = "/root/sxetest/pktgen/pktgen.log"
PKTGEN_LATEST_LOG = "/root/sxetest/pktgen/pktgen_latest.log"
DPDK_PERFORMANCE_LOG = '/root/sxetest/dpdk/performance.log'
# dpdk使用的usertools路径
# DPDK_USERTOOLS_PATH = '/dpdktest/dpdk-stable-20.11.5/usertools'
DPDK_USERTOOLS_PATH = '/root/sxetest/'
# dpdk驱动路径
# DPDK_IGB_UIO_PATH = '/root/dpdktest/dpdk-kmods/linux/igb_uio'
DPDK_IGB_UIO_PATH = '/root/sxetest/dpdk-kmods/dpdk-kmods/linux/igb_uio'
LOCAL_GRUB_PATH = '/root/grub'
REMOTE_GRUB_PATH = '/etc/sysconfig/grub'
# xdp程序路径
XDP_PATH = '/root/sxetest/xdp_test/AF_XDP-example'

base_address = 0xea180000
# 测试对象
test_obj = CommandLineArgsParse.get_test_object()
# 测试入口
TEST_ENTRY = CommandLineArgsParse.get_test_entry()
# ssh 命令拼接前缀
SSH_PREFIX = 'ssh -o StrictHostKeyChecking=no -o TcpKeepAlive=yes -o ServerAliveInterval=30 ' \
             '-o ServerAliveCountMax=5 -l {} -p {} {} "{}"'
# scp命令前缀
SCP = "scp -o StrictHostKeyChecking=no -o TcpKeepAlive=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=5"
# 记录脚本 cli 命令执行时间log
SCRIPT_CMD_TIME_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(os.path.dirname(__file__)))),
                                       'outputs', 'time')
SCRIPT_CMD_SCRIPTS_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(os.path.dirname(__file__)))),
                                       'outputs', 'scripts')
# 时间戳格式
TIME_FORMAT = '%Y%m%d%H%M%S'

NIC_STATUS_SUCCESS = r'\s*Status\s*=\s*Success'
NIC_STATUS_FAILED = r'\s*Status\s*=\s*Failure'

# if 'windows' in HOST_OS:
#     FILE_PATH_ROOT = 'C:/Users/Administrator/sxetest/'
# else:
#     # 用于在测试机上存储测试生成文件的linux根路径，文件操作只对该目录及其子目录下的文件有效，
#     脚本基类会检测该目录是否存在，不存在情况下，自动创建
#     FILE_PATH_ROOT = '/root/sxetest/'

# 网卡信息配置文件路径
IPTABLES_CONFIG_PATH = os.path.join(NIC_SCRIPT_PATH, "iptable_set.json")
SINGLE_TEST_MODE_PATH = os.path.join(NIC_SCRIPT_PATH, 'single_test_mode.txt')
FPGA_BIT_VERSION_PATH = os.path.join(NIC_SCRIPT_PATH, 'fpga_bit_version.txt')
WINRM_CONFIG_PATH = os.path.join(NIC_SCRIPT_PATH, "firewall_setting.ps1")
NIC_WIN_VM_CONFIG_PATH = os.path.join(NIC_SCRIPT_PATH, 'env_config_vm.ini')
NIC_ESXE_PATH = os.path.join(NIC_SCRIPT_PATH, 'nic100/utils/esxe.py')
NIC_DPDK_BUILD_PATH = os.path.join(NIC_SCRIPT_PATH, f'nic100/utils/scgbe_dpdk_build.sh')
NIC_IPERF_BT_PATH = os.path.join(NIC_SCRIPT_PATH, 'nic100/utils/iperf_bt_daemon.py')
NIC_SERIAL_DAEMON_PATH = os.path.join(NIC_SCRIPT_PATH, 'nic100/utils/ps3_serial_daemon.py')
NIC_SCLI_PATH = os.path.join(NIC_SCRIPT_PATH, 'nic100/utils/sagitta_serial_cli.py')
NIC_MODIFY_XML_PATH = os.path.join(NIC_SCRIPT_PATH, "nic100/utils/modify_xml.py")
NIC_PACKAGE_PROCESS_PATH = os.path.join(NIC_SCRIPT_PATH, 'nic100/utils/win_package_process.py')
NIC_RPC_SERVER_PATH = os.path.join(NIC_SCRIPT_PATH, 'script_libs/rpc_service/rpc_server.py')
NIC_RPC_CLIENT_PATH = os.path.join(NIC_SCRIPT_PATH, 'script_libs/rpc_service/rpc_client.py')
NIC_SEND_PACKET_PATH = os.path.join(NIC_SCRIPT_PATH, 'script_libs/socket_service/send_packet.py')
NIC_SEND_UDP_PACKET_PATH = os.path.join(NIC_SCRIPT_PATH, 'script_libs/socket_service/send_udp_packet.py')
NIC_RECEIVE_PACKET_PATH = os.path.join(NIC_SCRIPT_PATH, 'script_libs/socket_service/receive_packet.py')
NIC_IPVBS_PATH = os.path.join(NIC_SCRIPT_PATH, 'nic100/linux/rdma/ipvbs.py')
NIC_IPVBS_S_PATH = os.path.join(NIC_SCRIPT_PATH, 'nic100/linux/rdma/ipvbs_s.py')
NIC_IPVBS_LOCAL_PATH = os.path.join(NIC_SCRIPT_PATH, 'nic100/linux/rdma/ipvbs_execute_cmd_in_local.py')
NIC_INSTALL_SCRIPT_PATH = os.path.join(NIC_SCRIPT_PATH, "nic100/utils/install_all_version.py")
NIC_SET_IRQ_AFFINITY_PATH = os.path.join(NIC_SCRIPT_PATH, "nic100/utils/set_irq_affinity")
NIC_CHECK_AND_FREE_DISK = os.path.join(NIC_SCRIPT_PATH, "nic100/utils/check_and_free_disk.py")
NIC_SUB_SCRIPTS_MANEGER_PATH = os.path.join(NIC_SCRIPT_PATH, 'nic100/utils/subscript_manager.py')
NIC_PERSISTENCE_CONFIG_PATH = "/etc/sysconfig/network-scripts/"
# windows环境下用于物理机与虚拟机免密通信的凭证文件
NIC_WIN_CREDENTIAL_PATH = 'C:\\Users\\Administrator\\sxetest\\credential.xm'
# log日志默认目录名
LOG_DEFAULT_PATH_NAME = os.path.join('outputs', 'scripts')
# 临时文件保存目录名
FILE_TEMP_PATH_NAME = 'temp_files'
# VF驱动名称
VF_DRIVER = 'ixgbevf'
# PF驱动名称
PF_DRIVER = 'ixgbe'
VF_DRIVER_SXE = 'sxevf'
PF_DRIVER_SXE = 'sxe'
VF_DRIVER_SXE2 = 'sxe2vf'
PF_DRIVER_SXE2 = 'sxe2'
PF_DRIVER_SCGBE = f'{nicg}'
VF_DRIVER_SCGBE = f'{nicg}vf'
PF_DRIVER_ERROR = '???'
# DPDK驱动名称
DPDK_MOD = 'uio'
DPDK_DRIVER = 'igb_uio'
VFIO_PCI_DRIVER = 'vfio-pci'
VFIO_DRIVER = 'vfio'

"""
DPDK应用
"""
DPDK_TESTPMD = "dpdk-testpmd"
DPDK_PDUMP = "dpdk-pdump"
DPDK_PROC_INFO = "dpdk-proc-info"
DPDK_PTPCLIENT = "dpdk-ptpclient"
DPDK_ETHTOOL = "dpdk-ethtool"
DPDK_L3FWD = "dpdk-l3fwd"
DPDK_PKTGEN = "pktgen"

"""
字符串常量
"""
STR_EMPTY = ''
STR_SPACE = ' '
STR_EQUAL = '='
STR_COLON = ':'
STR_COMMA = ','
# linux系统换行符
STR_ENTER = '\n'
STR_UNDERLINE = '_'
STR_MINUS = '-'
STR_PATH_ALL = '/*'
STR_PERCENT = '%'
STR_LEFT_SLASH = '/'
STR_PLUS = '+'
STR_QUOTE = '"'
PIPE = '|'
SEMICOLON = ';'

"""
环境配置字段名
"""
ENV_TEST_OBJECT = 'test_object'
# md5值正则匹配模式
PATTERN_MD5 = r'([a-f\d]{32})|([A-F\d]{32})'
"""
命令or工具常量
"""

# cli命名未确认,暂时使用SXE2CLI64
SXECLI64 = 'sxecli'
SXE2CLI64 = 'sxe2cli'
SCGBECLI64 = f'{nicg}cli'
# 驱动命名未确认,暂时使用sxe.ko
DRIVER_FILE_NAME = 'sxe.ko'
DCBTOOL = 'dcbtool'
LLDPTOOL = 'lldptool'
ETHTOOL = 'ethtool'
IPERF = 'iperf3'
IPERF_WIN = 'C:/Users/Administrator/tools/iperf-3.1.3-win64/iperf-3.1.3-win64/iperf3.exe'
IP = 'ip'
IFCONFIG = 'ifconfig'
IPCONFIG = 'ipconfig /all'
NETSTAT = 'netstat'
IFSTAT = 'ifstat'
IFDOWN = 'ifdown'
IFUP = 'ifup'
NMCLI = "nmcli"
TCPDUMP = 'tcpdump'
PYTHON = 'python3'
SYSTEM = "systemctl"
STATUS = "status"
START = "start"
RESTART = 'restart'
EFIBOOTMGR = 'efibootmgr'
PING = "ping"
PSPING = "psping"
NETSH = "netsh"
INTERFACE = "interface"
FORWARD = "forwarding"
STATE = "state"
SXE2CLI64_WIN = 'sxecli'
DEVCON = "devcon"
# powershell命令
# 启用网卡
ENABLE_NET_ADAPTER = 'Enable-NetAdapter'
# 禁用网卡
DISABLE_NET_ADAPTER = 'Disable-NetAdapter'
# 禁用网卡绑定
DISABLE_NET_ADAPTER_BINDING = "Disable-NetAdapterBinding"
# 启用网卡绑定
ENABLE_NET_ADAPTER_BINDING = "enable-NetAdapterBinding"
# 在网络适配器上禁用选定的校验和卸载.
DISABLE_NET_ADAPTER_CHECKSUM_OFFLOAD = "Disable-NetAdapterChecksumOffload"
# 禁用网卡上的QoS.
DISABLE_NET_ADAPTER_QOS = "Disable-NetAdapterQos"
# 在网络适配器上禁用RSC
DISABLE_NET_ADAPTER_RSC = "Disable-NetAdapterRsc"
# 在网络适配器上禁用RSS
DISABLE_NET_ADAPTER_RSS = "Disable-NetAdapterRss"
# 禁用网卡上的SR-IOV功能
DISABLE_NET_ADAPTER_SR_IOV = "Disable-NetAdapterSriov"
# 禁用网卡上的VMQ特性.
DISABLE_NET_ADAPTER_VMQ = "Disable-NetAdapterVmq"
# 在网络适配器上启用选定的校验和卸载.
ENABLE_NET_ADAPTER_CHECKSUM_OFFLOAD = "Enable-NetAdapterChecksumOffload"
# 启用网卡上的QoS.
ENABLE_NET_ADAPTER_QOS = "Enable-NetAdapterQos"
# 在网络适配器上启用RSC
EnABLE_NET_ADAPTER_RSC = "Enable-NetAdapterRsc"
# 在网络适配器上启用RSS
EnABLE_NET_ADAPTER_RSS = "Enable-NetAdapterRss"
# 启用网卡上的SR-IOV功能
EnABLE_NET_ADAPTER_SR_IOV = "Enable-NetAdapterSriov"
# 启用网卡上的VMQ特性.
ENABLE_NET_ADAPTER_VMQ = "Enable-NetAdapterVmq"
# 查询网卡的高级特性
GET_NET_ADAPTER_ADVANCED_PROPERTY = 'Get-NetAdapterAdvancedProperty'
# 查询网卡的基本特性
GET_NET_ADAPTER = "Get-NetAdapter"
# 查询网卡的绑定设备的列表
GET_NET_ADAPTER_BINDING = "Get-NetAdapterBinding"
# 查询网卡的checksum offload
GET_CHECKSUMOFFLOAD = "Get-NetAdapterChecksumOffload"
# 查询网卡的LSO配置信息
Get_NetAdapterLso = "Get-NetAdapterLso"
GET_NET_ADAPTER_HARDWARE_INFO = "Get-NetAdapterHardwareInfo"
# 查询网卡的电源管理
Get_NetAdapterPowerManagement = "Get-NetAdapterPowerManagement"
# 查询网卡的QOS信息和DCB信息
Get_NetAdapterQos = "Get-NetAdapterQos"
# 查询网卡的RSC特性
Get_NetAdapterRsc = "Get-NetAdapterRsc"
# 查询网卡的RSS特性
Get_NetAdapterRss = "Get-NetAdapterRss"
# 查询网卡的虚拟化信息
GET_NET_ADAPTER_SRIOV = "Get-NetAdapterSriov"
# 查询网卡的统计信息
GET_NET_ADAPTER_STATISTICS = "Get-NetAdapterStatistics"
# 查询网卡的macvlan特性
GET_NET_ADAPTER_VMQ = "Get-NetAdapterVmq"
# 重启网卡
RESTART_NET_ADAPTER = "Restart-NetAdapter"
# 设置网卡的基本特性
SET_NET_ADAPTER = "Set-NetAdapter"
# 设置网卡的高级特性
SET_NET_ADAPTER_ADVANCED_PROPERTY = "Set-NetAdapterAdvancedProperty"
# 设置网络适配器上传输或筛选器的绑定状态
SET_NET_ADAPTER_BINDING = "Set-NetAdapterBinding"
# 设置网卡的checksum offload
SET_NETADAPTERCHECKSUMOffLOAD = "Set-NetAdapterChecksumOffload"
# 设置网卡的LSO属性
SET_NET_ADAPTER_LSO = "Set-NetAdapterLso"
# 设置网卡的Qos属性
SET_NET_ADAPTER_QOS = "Set-NetAdapterQos"
# 设置网卡的RSC
SET_NET_ADAPTER_RSC = "Set-NetAdapterRsc"
# 设置网卡的RSS
SET_NET_ADAPTER_RSS = "Set-NetAdapterRss"
# 设置网卡的虚拟化特性
SET_NET_ADAPTER_SRIOV = "Set-NetAdapterSriov"
# 设置网卡的macvlan 特性
SET_NET_ADAPTER_VMQ = "Set-NetAdapterVmq"
# 对网卡添加IP地址
NEW_NET_ADDRESS = "new-NetIpAddress"
FORMAT_TABLE = 'Format-Table'
FORMAT_LIST = 'Format-List'
SELECT_OBJECT = 'Select-Object'
# 创建team
NEW_NETLBFOTEAM = "New-NetLbfoTeam"
# 向指定网卡组添加新成员(网络适配器)
ADD_NETLBFOTEAMMEMBER = "Add-NetLbfoTeamMember"
# 为网卡组添加一个新接口。
ADD_NETLBFOTEAMNIC = "Add-NetLbfoTeamNic"
# 获取系统中NIC team的列表。
GET_NETLBFOTEAM = "Get-NetLbfoTeam"
# 获取属于NIC组成员的网络适配器。
GET_NETLBFOTEAMMEMBER = "Get-NetLbfoTeamMember"
# 获取vlan的信息
GET_NETLBFOTEAMNIC = "Get-NetLbfoTeamNic"
# 从主机移除指定的网卡组。
REMOVE_NETLBFOTEAM = "Remove-NetLbfoTeam"
# 从NIC组中删除一个或多个网络适配器。
REMOVE_NETLBFOTEAMMEMBER = "Remove-NetLbfoTeamMember"
# 从teaming中删除vlan 网卡
REMOVE_NETLBFOTEAMNIC = "Remove-NetLbfoTeamNIC"
# 对teaming网络组进行设置
SET_NETLBFOTEAM = "Set-NetLbfoTeam"
# 允许teaming中加入NIC
SET_NETLBFOTEAMMEMBER = "Set-NetLbfoTeamMember"
# 修改vlan的配置信息
SET_NETLBFOTEAMNIC = "Set-NetLbfoTeamNIC"
# 获取虚拟机网卡属性信息
GET_VMNETWORKADAPTER = 'Get-VMNetworkAdapter'
# 获取IP地址信息
GET_NETIPADDRESS = 'Get-NetIPAddress'
"""
DCB相关的命令信息
"""
# FlowControl相关的命令
DISABLE_FC = "Disable-NetQosFlowControl"
ENABLE_FC = "Enable-NetQosFlowControl"
SET_FC = "Set-NetQosFlowControl"
GET_FC = "Get-NetQosFlowControl"
SWITCH_FC = "Switch-NetQosFlowControl"
# dcbx相关的命令
GET_DCBX_SETTING = "Get-NetQosDcbxSetting"
SET_DCBX_SETTING = "Set-NetQosDcbxSetting"
SWITCH_DCBX = "Switch-NetQosDcbxSetting"
# TC相关的命令设置
GET_TC = "Get-NetQosTrafficClass"
NEW_TC = "New-NetQosTrafficClass"
SET_TC = "Set-NetQosTrafficClass"
REMOVE_TC = "Remove-NetQosTrafficClass"
SWITCH_TC = "Switch-NetQosTrafficClass"

"""
ptp测试
"""
PTP4L = "ptp4l"

"""
工具所需的最低版本
"""
ETHTOOL_VERSION = '5.0'
DCBTOOL_VERSION = '1.0.1'
IPERF_VERSION = '3.0'

"""
网卡寄存器基地址
"""
# 82599的PF0/PF1 基地址
intel_base_address_PF_0 = 0xea180000
intel_base_address_PF_1 = 0xea100000
# fpga PF0/PF1 基地址
fpga_base_address_PF_0 = 0x202fff900000
fpga_base_address_PF_1 = 0x202fff800000
"""
命令or工具参数
"""
# ethtool命令相关参数
CHANGE = '--change'
SHOW_PAUSE = '--show-pause'
PAUSE = '--pause'
SHOW_COALESCE = '--show-coalesce'
COALESCE = '--coalesce'
SHOW_RING = '--show-ring'
SET_RING = '--set-ring'
SHOW_FEATURES = '--show-features'
FEATURES = '--features'
DRIVER = '--driver'
REGISTER_DUMP = '--register-dump'
EEPROM_DUMP = '--eeprom-dump'
CHANGE_EEPROM = '--change-eeprom'
NEGOTIATE = '--negotiate'
IDENTIFY = '--identify'
TEST = '--test'
STATISTICS = '--statistics'
PHY_STATISTICS = '--phy-statistics'
SHOW_NTUPLE = '--show-ntuple'
CONFIG_NTUPLE = '--config-ntuple'
SHOW_TIME_STAMPING = '--show-time-stamping'
SHOW_RXFH = '--show-rxfh'
RXFH = '--rxfh'
FLASH = '--flash'
SHOW_PERMADDR = '--show-permaddr'
GET_DUMP = '--get-dump'
SET_DUMP = '--set-dump'
SHOW_CHANNELS = '--show-channels'
SET_CHANNELS = '--set-channels'
SHOW_PRIV_FLAGS = '--show-priv-flags'
SET_PRIV_FLAGS = '--set-priv-flags'
DUMP_MODULE_EEPROM = '--dump-module-eeprom'
SHOW_EEE = '--show-eee'
SET_EEE = '--set-eee'
SET_PHY_TUNABLE = '--set-phy-tunable'
GET_PHY_TUNABLE = '--get-phy-tunable'
RESET = '--reset'
SHOW_FEC = '--show-fec'
SET_FEC = '--set-fec'
VERSION = '--version'
MSGLVL = 'msglvl'
PER_QUEUE = '--per-queue'
QUEUE_MASK = 'queue_mask'

# ifconfig相关参数
UP = 'up'
DOWN = 'down'
MULTICAST = 'multicast'
MADDR = "maddr"
ALLMULTI = 'allmulti'
PROMISC = 'promisc'
HW_ETHER = "hw ether"

# dcbtool相关参数
GET_CONFIG = 'gc'
SET_CONFIG = 'sc'
GET_PEER_CONFIG = 'gp'
GET_OPERATIONAL_STATUS = 'go'
ON = 'on'
OFF = 'off'
DCB = 'dcb'
DCBX = 'dcbx'
PG = 'pg'
PFC = 'pfc'
APP = 'app'
FCOE = 'fcoe'
ISCSI = 'iscsi'
FIP = 'fip'
PGID = 'pgid'
PGPCT = 'pgpct'
UPPCT = 'uppct'
PFCUP = 'pfcup'
ENABLE = 'e'
ADVERTISE = 'a'
WILLING = 'w'
APPCFG = 'appcfg'

# lldptool相关参数
ETS_CFG = 'ETS-CFG'
GET_TLV = '-t'

# ip命令参数
XFRM_POLICY = 'xfrm policy'
XFRM_STATE = 'xfrm state'
ADD = 'add'
DEL = 'delete'
FLUSH = 'flush'
DELALL = 'deleteall'
UPDATE = 'update'
LIST = 'list'
SRC = 'src'
DST = 'dst'
DIR = 'dir'
PTYPE = 'ptype'
PROTO = 'proto'
TMPL = 'tmpl'
SPI = 'spi'
MODE = 'mode'
AUTH_MD5 = 'auth md5'
ENC_DES = 'enc des'
LINK = "link"
SHOW = "show"
SET = "set"
NAME = 'name'
TYPE = 'type'
ID = 'id'
ADDRESS = 'address'
DEV = 'dev'
VF = 'vf'
MAC = 'mac'
BRD = 'brd'
VLAN = 'vlan'
BRIDGE = 'bridge'
MASTER = 'master'
SLAVE = 'slave'
BOND = 'bond'
MACVLAN = 'macvlan'
RATE = 'rate'
MAX_TX_RATE = "max_tx_rate"
MIN_TX_RATE = "min_tx_rate"
SPOOF_CHK = "spoofchk"
QUERY_RSS = "query_rss"
TRUST = "trust"
XDP = "xdp"
OBJ = "obj"
ROUTE = 'route'
VIA = 'via'
NEIGH = 'neigh'
ALL = 'all'
"""
sendip 命令参数
"""
MODULE = "-p"  # -p指令
SRC_IP = "-is"
DST_IP = "-id"
SRC_PORT = "-ts"
DST_PORT = "-td"
SENDIP = "sendip"
FILE_PATCH = "-f"
DATA = "-d"
"""
netstat 命令参数
"""
ETHER_STATISTICS = '-e'

"""
Enable-NetAdapter 命令参数
"""
NAME1 = '-Name'
DISPLAY_NAME = '-DisplayName'
DISPLAY_VALUE = '-DisplayValue'
REGISTRY_KEYWORD = '-RegistryKeyword'
REGISTRY_VALUE = '-RegistryValue'
PROPERTY = '-Property'

"""
windows网卡属性
"""
RECEIVE_SIDE_SCALING = 'Receive Side Scaling'

"""
windows网卡硬件名称特征
"""
SXE_DEV_MARK_1 = '*1ff2*'
SXE_DEV_MARK_2 = '*NIC1160*'

"""
windows虚拟机参数
"""
# 定义各种名称的前缀
V_SWITCH_PREFIX_DEF = "sxeVmSwitch-"  # 虚拟交换机通用前缀
V_SWITCH_SRIOV_PREFIX_DEF = V_SWITCH_PREFIX_DEF + "sriov"  # SRIOV交换机前缀
V_SWITCH_VMQ_PREFIX_DEF = V_SWITCH_PREFIX_DEF + "vmq"  # VMQ交换机前缀
V_SWITCH_DEGVMQ_PREFIX_DEF = V_SWITCH_PREFIX_DEF + "degvmq"  # DEGVMQ交换机前缀
V_SWITCH_MANAGER_PREFIX_DEF = V_SWITCH_PREFIX_DEF + "manager"  # 管理交换机前缀
VM_NAME_PREFIX_DEF = "sxevm"  # 虚拟机名称前缀
VM_ADAPTER_MANAGER_PREFIX_DEF = "hyper-v-"  # 虚拟机管理适配器(内)前缀
VM_ADAPTER_TEST_PREFIX_DEF = "hyper-v-"  # 虚拟机被测适配器(内)前缀
VM_ADAPTER_VF_PREFIX_DEF = "sxe-vf-"  # 虚拟机VF适配器(内)前缀
VM_ADAPTER_VMQ_PREFIX_DEF = "sxe-vmq-"  # 虚拟机VMQ适配器(内)前缀
VM_ADAPTER_MACVLAN_PREFIX_DEF = "sxe-macvlan-"  # 虚拟机MACVLAN适配器(内)前缀
V_ADAPTER_MANAGER_PREFIX_DEF = VM_ADAPTER_MANAGER_PREFIX_DEF  # 虚拟机管理适配器(外)前缀
V_ADAPTER_TEST_PREFIX_DEF = VM_ADAPTER_TEST_PREFIX_DEF  # 虚拟机hyperv适配器(外)前缀
V_ADAPTER_VF_PREFIX_DEF = VM_ADAPTER_VF_PREFIX_DEF  # 虚拟机VF适配器(外)前缀
V_ADAPTER_VMQ_PREFIX_DEF = VM_ADAPTER_VMQ_PREFIX_DEF  # 虚拟机VMQ适配器(外)前缀
V_ADAPTER_MACVLAN_PREFIX_DEF = VM_ADAPTER_MACVLAN_PREFIX_DEF  # 虚拟机MACVLAN适配器(外)前缀
# 定义各种名称的默认值
VM_NAME_DEF = VM_NAME_PREFIX_DEF + "001"  # 虚拟机
V_SWITCH_SRIOV_NAME_DEF = V_SWITCH_SRIOV_PREFIX_DEF + '1'  # SRIOV交换机
V_SWITCH_VMQ_NAME_DEF = V_SWITCH_VMQ_PREFIX_DEF + '1'  # VMQ交换机
V_SWITCH_DEGVMQ_NAME_DEF = V_SWITCH_DEGVMQ_PREFIX_DEF + '1'  # DEGVMQ交换机
V_SWITCH_MANAGER_NAME_DEF = V_SWITCH_MANAGER_PREFIX_DEF + '1'  # 管理交换机
VM_ADAPTER_MANAGER_NAME_DEF = VM_ADAPTER_MANAGER_PREFIX_DEF + "manager"  # 虚拟机管理适配器(内)
VM_ADAPTER_TEST_NAME_DEF = VM_ADAPTER_TEST_PREFIX_DEF + "1"  # 虚拟机hyperv适配器(内)
VM_ADAPTER_VF_NAME_DEF = VM_ADAPTER_VF_PREFIX_DEF + "1"  # 虚拟机VF适配器(内)
VM_ADAPTER_VMQ_NAME_DEF = VM_ADAPTER_VMQ_PREFIX_DEF + "1"  # 虚拟机VMQ适配器(内)
VM_ADAPTER_MACVLAN_NAME_DEF = VM_ADAPTER_MACVLAN_PREFIX_DEF + "1"  # 虚拟机MACVLAN适配器(内)
V_ADAPTER_MANAGER_NAME_DEF = V_ADAPTER_MANAGER_PREFIX_DEF + "manager"  # 虚拟机管理适配器(外)
V_ADAPTER_TEST_NAME_DEF = V_ADAPTER_TEST_PREFIX_DEF + "1"  # 虚拟机hyperv适配器(外)
V_ADAPTER_VF_NAME_DEF = V_ADAPTER_VF_PREFIX_DEF + "1"  # 虚拟机VF适配器(外)
V_ADAPTER_VMQ_NAME_DEF = V_ADAPTER_VMQ_PREFIX_DEF + "1"  # 虚拟机VMQ适配器(外)
V_ADAPTER_MACVLAN_NAME_DEF = V_ADAPTER_MACVLAN_PREFIX_DEF + "1"  # 虚拟机MACVLAN适配器(外)
V_MANAGER_NAME = "SxeVm-manager"

"""
windows虚拟机配置文件目录
"""
# VM_CONF_PATH = "C:\Users\Administrator\sxetest"

"""
Linux KVM windows虚拟机配置参数
"""
KVM_TEST_VF_ID = "1"
KVM_TEST_VF_NUM = "10"
KVM_MAX_VF_NUM = 31
KVM_MAX_MANAGE_VF_NUM = 1
KVM_VM_NAME = "sxevm001-windows"
KVM_VF_ADAPTER_NAME = VM_ADAPTER_VF_NAME_DEF
KVM_MANAGE_ADAPTER_NAME = VM_ADAPTER_MANAGER_NAME_DEF
KVM_VMQ_ADAPTER_NAME = VM_ADAPTER_VMQ_NAME_DEF
KVM_MACVLAN_ADAPTER_NAME = VM_ADAPTER_MACVLAN_NAME_DEF

"""
命令回显正则匹配
"""
SHOW_PAUSE_PATTERN = r'(\S*):\s+(\S+)\s*'
SHOW_COALESCE_PATTERN = r'(\S*):\s+(\S+)\s+'
SHOW_RING_PATTERN = r'([\s\S]*):\s*(\d+)\s*'
SHOW_FEATURES_PATTERN = r'(\S*):\s+(\S+)\s+'
SHOW_DRIVER_PATTERN = r'(\S+):\s+(\S+)'
SHOW_REGISTER_DUMP_PATTERN = r'\s*([\s\S]*):\s{1,}(\S+)'
SHOW_STATISTICS_PATTERN = r'(\S+):\s(\S+)'
SHOW_CHANNELS_PATTERN = r'([\s\S]*):\s*(\d+)\s*'
SHOW_PRIV_FLAGS_PATTERN = r'(\S*)\s*:\s+(\S+)\s*'
SHOW_STANDARD_INFO_PATTERN = r'(\S*):\s+(\S+)\s+'

"""
片外cli命令显示--cli /px show
"""
PORT_LINK = 'Port Link'
LINK_STATUS = 'Link Status'
LINK_SPEED = 'Link Speed'
NO_LINK = 'No Link'

"""
固件
"""
GET_MFG_INFO = '/p{} show mfginfo'
SET_MFG_INFO = '/p{} set mfginfo{}'
MAX_VF_NUM = 256
REGION_MASTER = 'MASTER'
REGION_SLAVE = 'SLAVE'
MAX_WHITE_LIST_COUNT = 254
MAX_QUICK_LIST_COUNT = 40
FPGA_TEST = True  # FPGA阶段，asic卡测试时需要设置False
"""
ip地址的匹配模式
"""
PATTERN_IP = r'(25[0-5]|2[0-4]\d|[0-1]\d{2}|[1-9]?\d)\.(25[0-5]|2[0-4]\d|[0-1]\d{2}|[1-9]?\d)\.' \
             r'(25[0-5]|2[0-4]\d|[0-1]\d{2}|[1-9]?\d)\.(25[0-5]|2[0-4]\d|[0-1]\d{2}|[1-9]?\d)'

"""
命令回显正则匹配---片外cli
"""
# 公共部分
PATTERN_HEADER_CLI_VERSION = r'CLI Version\s*=\s*\w*\d+\.\d+\.\d+\.\d+'
PATTERN_HEADER_OPERATING_SYSTEM = r'Operating System\s*= Linux .+'
PATTERN_HEADER_SYSTEM_TIME = r'System Time\s*= \d{4}-[01]\d-[0-3]\d [0-2]\d:[0-5]\d:[0-5]\d\s*'
PATTERN_HEADER_PORT = r'Port (\d):\s*'
PATTERN_HEADER_LINE = r'-+\s*'
PATTERN_HEADER_STATUS_SUCCESS = r'\s{4}Status\s*= Success\s*'
PATTERN_HEADER_STATUS_FAILURE = r'\s{4}Status\s*= Failure\s*'
PATTERN_HEADER_DES_SUCCESS = r'\s{4}Description\s*= None\s*'
PATTERN_HEADER_DES_FAILURE = r'\s{4}Description\s*= (.+)\s*\(\s*(\w+)\s*0x.+\)\s*'
PATTERN_CTRL_SET_STATUS = r'\s{4}Ctrl Set Status:\s*'
PATTERN_SPLIT_LINE = r'\s{4}-+\s*'
PATTERN_TABLE_OUTER_LINE = r'\s{8}\+-+\+\s*'
PATTERN_TABLE_INNER_LINE_5_COLUMNS = r'\s{8}\+(-+\+){5}\s*'

# cli show命令
PATTERN_HEADER_SYSTEM_OVERVIEW = r'System Overview:\s*'
PATTERN_HEADER_CONTROLLER = r'\s{4}Controller 0:\s*'
PATTERN_TABLE_INNER_LINE_7_COLUMNS = r'\s{8}\+(-+\+){7}\s*'
PATTERN_TABLE_TITLE_CLI_SHOW = r'\s{8}\|Port\s*\|Mac Address\s*\|Network Name\s*\|' \
                               r'BDF\s*\(bus/dev/func\)\s*\|Link Speed' \
                               r'\s*\|Firmware Version\s*\|OptionRom Version\s*\|\s*'
PATTERN_TABLE_CONTENT_CLI_SHOW = r'\s+\|(\d+)\s*\|(\S+)\s*\|(\w+)\s+|(\S+)\s*\|(\S+)\s*\|(\d+ [GM]b/s|No Link)\s*\|' \
                                 r'(\S+)\s*\|(\S+)\s*\|\s*'
# cli px show命令
PATTERN_HEADER_BASICS = r'\s{4}Basics:'
PATTERN_SOC_STATUS = r'\s{8}SOC Status\s*= (\S+)\s*'
PATTERN_SOC_TEMPERATURE = r'\s{8}SOC Temperature \(Degree Celsius\)\s*= (\d+)\s*'
PATTERN_FIRMWARE_VERSION = r'\s{8}Firmware Version\s*= (\S+)\s*'
PATTERN_OPTIONROM_VERSION = r'\s{8}OptionRom Version\s*= (\S+)\s*'
PATTERN_MAC_ADDR = r'\s{8}Mac Address\s*= (\S+)\s*'
PATTERN_PORT_LINK = r'\s{8}Port Link\s*= ([01])\s*'
PATTERN_LINK_STATUS = r'\s{8}Link Status\s*= ([01])\s*'
PATTERN_LINK_SPEED = r'\s{8}Link Speed\s*= (.+)\s*'
PATTERN_SFP_INFO_GET_STATUS = r'\s{8}SFP Information Acquisition Status\s*= (\w+)\s*'
PATTERN_MOD_TEMPERATURE = r'\s{8}Optical Mod Temperature \(Degree Celsius\)\s*= (\d+)\s*'
PATTERN_MOD_TYPE = r'\s{8}Transceiver Type\s*= (.+)\s*'
PATTERN_VENDOR_NAME = r'\s{8}Vendor Name\s*= (.+)\s*'
PATTERN_VENDOR_PN = r'\s{8}Vendor PN\s*= (.+)\s*'
# 写寄存器命令
PATTERN_TABLE_TITLE_SET_REG = r'\s{8}\|Reg Type\s*\|Addr\s*\|Value\s*\|ErrCd\s*\|Message\s*\|\s*'
PATTERN_TABLE_CONTENT_SET_REG = r'\s{8}\|(\w)\s*\|(0x\w+)\s*\|(0x\w+)\s*\|(\d+)\s*\|(.+)\s*\|\s*'
PATTERN_SET_REG_PROMPT = r'\s*sxecli /px set reg type=<A\|B\|C\|D> \[width=<8\|16\|32\|64>\] ' \
                         r'addr=<value value1 \[value2 ...\]>\s*'
# cli -vv命令
PATTERN_VERSION = r'Version\s*:\s*\w*(\d+\.){3}\d+\s*'
PATTERN_BUILD_TIME = r'Build Time\s*: [A-Za-z]+ [0-3]\d \d{4} [0-2]\d:[0-5]\d:[0-5]\d\s*'
PATTERN_COMMIT_ID = r'Commit Id\s*: [0-9a-z]+\s*'
PATTERN_BRANCH = r'Branch\s*: \S+\s*'
PATTERN_ARCH = r'Arch\s*: x86_64\s*'
PATTERN_PRODUCT_SUPPORT = r'Product Support\s*: SXE'
PATTERN_BUILD_MODE = r'Build Mode\s*: debug\s*'

"""
命令回显正则匹配---片内cli
"""
PATTERN_UART_VERSION = r'Version\s*= [A-Z][a-z]{2,3} \d{1,2} 20\d{2} \d{2}:\d{2}:\d{2}\s*'
PATTERN_UART_SYSTEM_TIME = r'System Time\s*= \d{4}-[01]\d-[0-3]\d [0-2]\d:[0-5]\d:[0-5]\d\s*'
PATTERN_UART_STATUS_SUCCESS = r'Status\s*= Success\s*'
PATTERN_UART_STATUS_FAILURE = r'Status\s*= Failure\s*'
PATTERN_UART_DES_SUCCESS = r'Description\s*= None\s*'
PATTERN_UART_DES_FAILURE = r'Description\s*= (.+)\s*\(\s*(\w+)\s*0x[0-9a-fA-F]+\s*\[\s*-(\d+)\s*\]\s*\)\s*'
PATTERN_UART_SPLIT_LINE = r'-+\s*'
PATTERN_UART_TABLE_OUTER_LINE = r'\s{4}\+-+\+\s*'
PATTERN_UART_TABLE_INNER_LINE_3_COLUMNS = r'\s{4}\+(-+\+){3}\s*'
PATTERN_UART_TIME_SHOW = r'(\w+) show:\s*'
PATTERN_UART_TABLE_TITLE_SHOW_TIME = r'\s{4}\|Time\s*\|ErrCd\s*\|ErrMsg\s*\|\s*'
PATTERN_UART_TABLE_CONTENT_SHOW_TIME = r'\s{4}\|(.+)\|\s*(\d+)\s*\|\s*To Be Done\s*\|\s*'
PATTERN_UART_TABLE_CONTENT_SHOW_REG = r'\|(\w+)\s*\|(\w+)\s*\|(\w+)\s*\|(\w+)\s*\|(\w+)\s*\|(.+)\|'
PATTERN_UART_UP_TIME = r'(\d+) days,(\d+) hours,(\d+) minutes,(\d+) seconds'

"""
模式&协议
"""
IPV4 = 'ipv4'
IPV6 = 'ipv6'
TCP = 'tcp'
UDP = 'udp'

"""
ifconfig回显字段
"""
FLAGS = 'flags'
MTU = 'mtu'
INET = 'inet'
NETMASK = 'netmask'
BROADCAST = 'broadcast'
INET6 = 'inet6'
PREFIXLEN = 'prefixlen'
SCOPID = 'scopeid'
ETHER = 'ether'
INFINIBAND = 'infiniband'
TXQUEUELEN = 'txqueuelen'
RX_PACKETS = 'rx_packets'
TX_PACKETS = 'tx_packets'
RX_BYTES = 'rx_bytes'
TX_BYTES = 'tx_bytes'
RX_ERRORS = 'rx_errors'
TX_ERRORS = 'tx_errors'
FRAME = 'frame'

"""
ipconfig /all回显字段
"""
DESCRIPTION = 'Description'
MEDIA_STATE = 'media_state'

# 生产信息
VENDOR_NAME = 'LinkData'
PRODUCT_NAME = '1260-X'
VENDOR_ID = '1ff2'
VENDOR_ID_NAME = 'NIC1160'
DEVICE_ID1 = '10a1'
DEVICE_ID2 = '10a2'

# BMC 公共参数
BMC_NAME = 'superuser'
BMC_PWD = 'bmcAdmin80#$'
BMC_NAME_INTEL = 'sysadmin'
BMC_PWD_INTEL = 'superuser'
BMC_NAME_NET = 'Admin'  # 网页登录密码，升级pldm时使用
BMC_PWD_NET = 'Admin@8000'
if is_fpga:
    BMC_TOOL_PATH = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_fpga/pkgTools/bmctest/bmccli_debug'
    BMC_TOOL_PATH_BUSCTL = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_fpga/pkgTools/bmctest/bmccli_busctl'
    BMC_TOOL_PATH_MCTPAPP = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_fpga/pkgTools/bmctest/bmccli_mctpapp'
else:
    BMC_TOOL_PATH = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/pkgTools/bmctest/bmccli_debug'
    BMC_TOOL_PATH_BUSCTL = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/pkgTools/bmctest/bmccli_busctl'
    BMC_TOOL_PATH_MCTPAPP = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_asic/pkgTools/bmctest/bmccli_mctpapp'
BMC_LOG_PATH = '/var/sxelog/sxe_11.log'
BMC_EVT_FILE = '/var/sxeEvt_show.txt'

BMC_TEMP_SOC = 0
BMC_TEMP_P0 = 1
BMC_TEMP_P1 = 2
BMC_SPEED_P0 = 3
BMC_SPEED_P1 = 4
BMC_SPEC_SPEED_P0 = 5
BMC_SPEC_SPEED_P1 = 6
BMC_MTU_P0 = 7
BMC_MTU_P1 = 8

# port和pf的实际对应关系是否反转
BMC_PORT_PF_REVERSE = False
# 光模块规格速率
BMC_SPEC_SPEED_LIST = [5, 6, 13, 14]
# 端口当前速率
BMC_SEEP_LIST = [3, 4, 11, 12]
# 端口MTU
BMC_MTU_LIST = [7, 8, 15, 16]
# 光模块当前温度
BMC_TEMP_LIST = [1, 2, 9, 10]
ETHTOOL_BMC_SPEED_MAP = {
            'Unknown': 0,
            '100Mb/s': 1,
            '1000Mb/s': 2,
            '10000Mb/s': 3,
            "25000Mb/s": 4,
            "50000Mb/s": 5,
            "100000Mb/s": 6,
        }
OPTICAL_INFO_DICT = {
    "S2185-BD1C": {"spec_speed": 25,},
    "XP-8G10-01": {"spec_speed": 10, },
    "LA0SF068-SD-R": {"spec_speed": 25,}  # 铜缆
}

# PORT link状态
BMC_STATE_SENSOR_ID_LIST = [1, 2, 5, 6]
# PORT 在位情况
BMC_STATE_ABS_LIST = [3, 4, 7, 8]

BMC_THRES_SOC = 0
BMC_THRES_P0 = 1
BMC_THRES_P1 = 2

BMC_STATE_SOC = 0
BMC_STATE_P0 = 1
BMC_STATE_P1 = 2
BMC_STATE_ABS_P0 = 3
BMC_STATE_ABS_P1 = 4

# 注：0x8100是VLAN的TPID（识别码）后面还会有L2的EtherType，不能作为二层最终的EtherType
ETH_TYPE_LST = ['0x0805', '0x0806', '0x0808', '0x22f3', '0x22f4', '0x6558', '0x6559', '0x8035',
                '0x809b', '0x8137', '0x8138', '0x814c', '0x876b', '0x876c', '0x893b', '0x8946',
                '0x876d', '0x8808', '0x880b', '0x880c', '0x8847', '0x8848', '0x8863', '0x8864',
                '0x888e', '0x88a8', '0x88b7', '0x88c7', '0x88cc', '0x88e5', '0x88f5', '0x88f6',
                ]

"""
驱动管理-默认驱动文件目录
"""
PUBLISH_VERSION_PATH = WINDOWS_FILE_PATH_ROOT + "publish_version{0}/"
VERSION_WIN_DRV_ROOT_PATH = PUBLISH_VERSION_PATH + "products/Drivers/Windows/"
VERSION_WIN_DRV_FILE_PATH_FORMAT = VERSION_WIN_DRV_ROOT_PATH + "sxe{1}/sxe{1}/sxe{1}.inf"
WIN_PF_DRV_FILE_PATH = VERSION_WIN_DRV_FILE_PATH_FORMAT.format("", "pf")
WIN_VF_DRV_FILE_PATH = VERSION_WIN_DRV_FILE_PATH_FORMAT.format("", "vf")
WIN_PF_DRV_FILE_LAST_PATH = VERSION_WIN_DRV_FILE_PATH_FORMAT.format("_last", "pf")
WIN_VF_DRV_FILE_LAST_PATH = VERSION_WIN_DRV_FILE_PATH_FORMAT.format("_last", "vf")
VERSION_WIN_CAT_FILE_PATH_FORMAT = VERSION_WIN_DRV_ROOT_PATH + "sxe{1}/sxe{1}/sxe{1}.cat"
WIN_PF_CAT_FILE_PATH = VERSION_WIN_CAT_FILE_PATH_FORMAT.format("", "pf")
WIN_VF_CAT_FILE_PATH = VERSION_WIN_CAT_FILE_PATH_FORMAT.format("", "vf")
VERSION_WIN_SYS_FILE_PATH_FORMAT = VERSION_WIN_DRV_ROOT_PATH + "sxe{1}/sxe{1}/sxe{1}.sys"
WIN_PF_SYS_FILE_PATH = VERSION_WIN_SYS_FILE_PATH_FORMAT.format("", "pf")
WIN_VF_SYS_FILE_PATH = VERSION_WIN_SYS_FILE_PATH_FORMAT.format("", "vf")

# PLDM_IMAGE_NOVERCHK = ('/root/sxetest/publish_version/products/Firmware/BMC-Products/1260-X/Image_*.*.*.*_runmod6_NIC_PLDM-1260-X.bin')
# PLDM_IMAGE_VERCHK = ('/root/sxetest/publish_version/products/Firmware/BMC-Products/1260-X/Image_*.*.*.*_runmod6_NIC_PLDM-1260-X.bin')
PLDM_IMAGE_NOVERCHK = ('/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/sxe2_fw_pldm_asic_image_package_runmod6_noverchk.bin')
# PLDM_IMAGE_VERCHK = ('/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/sxe2_fw_pldm_asic_image_package_runmod6.bin')
PLDM_IMAGE_VERCHK = ('/root/sxetest/publish_version/products/Firmware/BMC-Products/1260-X/Image_*.*.*.*_runmod6_NIC_PLDM-1260-X.bin')

# PLDM_IMAGE_BAK_NOVERCHK = PLDM_IMAGE_NOVERCHK
# PLDM_IMAGE_BAK_VERCHK = PLDM_IMAGE_VERCHK

# PLDM_IMAGE_OLD_NOVERCHK = ('/root/sxetest/publish_version/products/Firmware/BMC-Products/1260-X/Image_*.*.*.*_runmod6_NIC_PLDM-1260-X.bin')
# PLDM_IMAGE_OLD_VERCHK = ('/root/sxetest/publish_version/products/Firmware/BMC-Products/1260-X/Image_*.*.*.*_runmod6_NIC_PLDM-1260-X.bin')
# PLDM_IMAGE_OLD_NOVERCHK = ('/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/sxe2_fw_pldm_asic_image_package_runmod6_noverchk.bin')
# PLDM_IMAGE_OLD_VERCHK = ('/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/sxe2_fw_pldm_asic_image_package_runmod6.bin')

# PLDM_IMAGE_NOVERCHK_D = (f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_fpga/debug/{nicg}_fw_pldm_fpga_image_package_runmod1A_noverchk.bin')
# PLDM_IMAGE_VERCHK_D = (f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_fpga/debug/{nicg}_fw_pldm_fpga_image_package_runmod1A.bin')

PLDM_IMAGE_HEADER_ERR = '/root/sxetest/fw0_pldm_wrong_header_checksum.bin'
PLDM_IMAGE_CONTENT_ERR = '/root/sxetest/test_package/sxe_fw_pldm_asic_image_package_content_err.bin'

MODIFY_XML = '/root/sxetest/modify_xml.py'
SXE_XML = '/root/sxetest/publish_version/technical_support/Firmware/Tools/cfgTools/sxe.xml'
SXEOEM_XML = '/root/sxetest/publish_version/technical_support/Firmware/Tools/cfgTools/sxeOem.xml'
XML2BIN = '/root/sxetest/publish_version/technical_support/Firmware/Tools/cfgTools/xml2bin'
XML_FOLDER = '/root/sxetest/publish_version/technical_support/Firmware/Tools/cfgTools/'
SXE_PLDM_PACKAGE_PY = '/root/sxetest/publish_version/technical_support/Firmware/Tools/pkgTools/sxe_pldm_package.py'
XML_PARA_LOGPERSISTON = 'sxeUser_mgrModule_loginfo_logPersistOn'
XML_PARA_PLDMRST = 'sxeUser_oobParam_pldmparam_isActiveRst'

SCGBENVDATA_XML = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_fpga/cfgTools/{nicg}Nvdata.xml'
SCGBENVDATA_XML = f'/root/sxetest/publish_version/technical_support/Firmware/Tools/cfgTools/{nicg}Nvdata.xml'
SCGBEOEM_XML = f'/root/sxetest/publish_version/technical_support/Firmware/Tools/cfgTools/{nicg}Oem.xml'
SKIP_IP = '10.17.21.17'
NIC_BMC_OPERATION_SH = f'/root/sxetest/publish_version/debuginfo/{nicg}_fw_fpga/pkgTools/bmctest/nic_bmc_operation.sh'
CHECK_ENCODE = '/root/check_encode.py'
"""
python运行的当前平台类型windows/linux
"""
PLAT_TYPE = "windows" if os.name == "nt" else "linux"

# rss,每个region有256个队列
E810_MAX_RING_NUM = 256
if IS_SIMU:
    # 模拟平台
    MAX_RING_NUM = 8
    MAX_VF_RING_NUM = 8
else:
    # todo hejf 2025.4.1 当前rss最大只支持2
    MAX_RING_NUM = 3
    MAX_VF_RING_NUM = 8

# dev_info
C_DEV_IP = 'client_device_ip'
S_DEV_IP = 'server_device_ip'
C_DEV_IPV6 = 'client_device_ipv6'
S_DEV_IPV6 = 'server_device_ipv6'
C_DEV_MAC = 'client_device_mac'
S_DEV_MAC = 'server_device_mac'
C_DEV_NAME = 'client_device_name'
S_DEV_NAME = 'server_device_name'
C_PF_DEV_NAME = 'client_pf_device_name'
S_PF_DEV_NAME = 'server_pf_device_name'
S_BUS_INFO = 'server_bus_info'
C_BUS_INFO = 'client_bus_info'

# 定义全局方法，用来设置TEST_ENTRY全局变量


def reset_test_entry(new_test_entry: str = None) -> None:
    """
    author:      haibin.xu
    date:        2021-05-07 14:46:40
    description: 提供重置 test entry的接口，供外部调用，如framework模块，此时脚本中还没有
                 命令行参数，test entry无法通过命令行参数解析进行赋值

    :param new_test_entry: 待要设置的 test_entry参数
    :return:     None
    """
    if new_test_entry not in ['host', 'soc']:
        print('Error: Invalid test entry which is seted: {}.'.format(new_test_entry))
    else:
        global TEST_ENTRY
        if 'host' == new_test_entry:
            TEST_ENTRY = 0
        else:
            TEST_ENTRY = 1


SCGBE_CLI = f'{nicg}cli'
DRV_SXE_PF = 'sxe'
# DRV_SCGBE_RDMA = f'{nicg}_rdma' if nicg!='scgbe' else f'{nicg}_rdma'
DRV_SCGBE_RDMA = f'{nicrg}'
DRV_SCGBE_PF = f'{nicg}'
DRV_SCGBE_VF = f'{nicg}vf'
ICE = "ice"
MLX5_CORE = 'mlx5_core'

MTU_MAX = 9702
MTU_DEFAULT = 1500

IOCTRL_FAILED = 'Ioctl failed'
CONTROLLER_NOT_FOUND = 'Controller not found'

COREDUMP_SIZE = 4608
if is_fpga:
    TERMLOG_ALL_SIZE = 2 * 1024
else:
    TERMLOG_ALL_SIZE = 8 * 1024
TERMLOG_SIZE = 4

TMP_PKG_PATH = '/root/tmp_pkg/'
IPVBS_PATH_OPEN = '{}/pyverbs/examples/ipvbs.py'
IPVBSS_PATH_OPEN = '{}/pyverbs/examples/ipvbs_s.py'
IPVBS_PATH_SCGBE = '{}/pyverbs/examples/ipvbs.py'
IPVBSS_PATH_SCGBE = '{}/pyverbs/examples/ipvbs_s.py'
IPVBS_LOCAL_PATH_OPEN = '{}/pyverbs/examples/ipvbs_execute_cmd_in_local.py'
IPVBS_LOCAL_PATH_SCGBE = '{}/pyverbs/examples/ipvbs_execute_cmd_in_local.py'
IPVBS_PATH_ORI = '/root/sxetest/{}'
IPVBS_DATA_FLAG = 'ipvbs_data_'
RDMA_FPGA_HOST_IP = ['10.22.66.227', "10.22.66.228", '10.17.137.240', '10.17.136.239']

DEBUGFS_PATH = f'/sys/kernel/debug/{nicg}rdma/'

IBV_ACCESS_LOCAL_WRITE = 1
IBV_ACCESS_REMOTE_WRITE = 2
IBV_ACCESS_REMOTE_READ = 4
IBV_ACCESS_REMOTE_ATOMIC = 8
IBV_ACCESS_MW_BIND = 16
IBV_ACCESS_ZERO_BASED = 32

IBV_REREG_MR_CHANGE_TRANSLATION = 1
IBV_REREG_MR_CHANGE_PD = 2
IBV_REREG_MR_CHANGE_ACCESS = 4

PRODUCT_FLAG = '1eb6'
SUB_VENDOR_ID_LINKDATA = "1FF2"
SUB_VENDOR_ID_TL = "206F"
SUB_DEVICE_ID_PCIE_X2 = "0C21"
SUB_DEVICE_ID_OCP_X2 = "0C22"
SUB_DEVICE_ID_OCP_X4 = "0C23"
SUB_DEVICE_ID_PCIE_X2_10G = "0C24"
PCIE_ID_DICT =  {
    SUB_DEVICE_ID_PCIE_X2: {
        # "vendor_id": "1FF2",
        "device_id": "10B1",
        # "sub_vendor_id": "1FF2",
        "sub_device_id": SUB_DEVICE_ID_PCIE_X2,
        "speed": 4,
        "width": 8,},
    SUB_DEVICE_ID_PCIE_X2_10G: {
        # "vendor_id": "1FF2",
        "device_id": "10B3",
        # "sub_vendor_id": "1FF2",
        "sub_device_id": SUB_DEVICE_ID_PCIE_X2_10G,
        "speed": 3,
        "width": 8, },
    SUB_DEVICE_ID_OCP_X2: {
        # "vendor_id": "1FF2",
        "device_id": "10B1",
        # "sub_vendor_id": "1FF2",
        "sub_device_id": SUB_DEVICE_ID_OCP_X2,
        "speed": 4,
        "width": 8, },
    SUB_DEVICE_ID_OCP_X4: {
        # "vendor_id": "1FF2",
        "device_id": "10B1",
        # "sub_vendor_id": "1FF2",
        "sub_device_id": SUB_DEVICE_ID_OCP_X4,
        "speed": 5,
        "width": 8, },
}

NEW_UPGRADE_IMAGE_PACKAGE_DIR = "/root/sxetest/publish_version/products/Firmware/Standard-Products/1260-X/"
PCIE_X2_25G_IMAGE_PACKAGE_PATH = NEW_UPGRADE_IMAGE_PACKAGE_DIR + "Image_*.*.*.*_runmod*_NIC_pcie-2-25-1260-X.bin"
PCIE_X2_10G_IMAGE_PACKAGE_PATH = NEW_UPGRADE_IMAGE_PACKAGE_DIR + "Image_*.*.*.*_runmod*_NIC_pcie-2-10-1260-X.bin"
OCP_X2_25G_IMAGE_PACKAGE_PATH = NEW_UPGRADE_IMAGE_PACKAGE_DIR + "Image_*.*.*.*_runmod*_NIC_ocp-2-25-1260-X.bin"
OCP_X4_25G_IMAGE_PACKAGE_PATH = NEW_UPGRADE_IMAGE_PACKAGE_DIR + "Image_*.*.*.*_runmod*_NIC_ocp-4-25-1260-X.bin"

# PCIE_X2_25G_PLDM_PACKAGE_PATH = "/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/pcie-2-25/sxe2_fw_pldm_asic_image_package_runmod*.bin"
# PCIE_X2_10G_PLDM_PACKAGE_PATH = "/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/pcie-2-10/sxe2_fw_pldm_asic_image_package_runmod*.bin"
# OCP_X2_25G_PLDM_PACKAGE_PATH = "/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/ocp-2-25/sxe2_fw_pldm_asic_image_package_runmod*.bin"
# OCP_X4_25G_PLDM_PACKAGE_PATH = "/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/ocp-4-25/sxe2_fw_pldm_asic_image_package_runmod*.bin"
NEW_UPGRADE_PLDM_PACKAGE_DIR = "/root/sxetest/publish_version/products/Firmware/BMC-Products/1260-X/"
PCIE_X2_25G_PLDM_PACKAGE_PATH = NEW_UPGRADE_PLDM_PACKAGE_DIR + "Image_*.*.*.*_runmod*_NIC_pcie-2-25-PLDM_1260-X.bin"
PCIE_X2_10G_PLDM_PACKAGE_PATH = NEW_UPGRADE_PLDM_PACKAGE_DIR + "Image_*.*.*.*_runmod*_NIC_pcie-2-10-PLDM_1260-X.bin"
OCP_X2_25G_PLDM_PACKAGE_PATH = NEW_UPGRADE_PLDM_PACKAGE_DIR + "Image_*.*.*.*_runmod*_NIC_ocp-2-25-PLDM_1260-X.bin"
OCP_X4_25G_PLDM_PACKAGE_PATH = NEW_UPGRADE_PLDM_PACKAGE_DIR + "Image_*.*.*.*_runmod*_NIC_ocp-4-25-PLDM_1260-X.bin"


# NEW_UPGRADE_PLDM_NOVERCHK_PACKAGE_DIR = "/root/sxetest/publish_version/products/Firmware/BMC-Products/1260-X/"
# PCIE_X2_25G_PLDM_NOVERCHK_PACKAGE_PATH = NEW_UPGRADE_PLDM_NOVERCHK_PACKAGE_DIR + "Image_*.*.*.*_runmod*_NIC_pcie-2-25-PLDM_NOVERCHK-1260-X.bin"
# PCIE_X2_10G_PLDM_NOVERCHK_PACKAGE_PATH = NEW_UPGRADE_PLDM_NOVERCHK_PACKAGE_DIR + "Image_*.*.*.*_runmod*_NIC_pcie-2-10-PLDM_NOVERCHK-1260-X.bin"
# OCP_X2_25G_PLDM_NOVERCHK_PACKAGE_PATH = NEW_UPGRADE_PLDM_NOVERCHK_PACKAGE_DIR + "Image_*.*.*.*_runmod*_NIC_ocp-2-25-PLDM_NOVERCHK-1260-X.bin"
# OCP_X4_25G_PLDM_NOVERCHK_PACKAGE_PATH = NEW_UPGRADE_PLDM_NOVERCHK_PACKAGE_DIR + "Image_*.*.*.*_runmod*_NIC_ocp-4-25-PLDM_NOVERCHK-1260-X.bin"
NEW_UPGRADE_PLDM_NOVERCHK_PACKAGE_DIR = "/root/sxetest/publish_version/debuginfo/sxe2_fw_asic/debug/"
PCIE_X2_25G_PLDM_NOVERCHK_PACKAGE_PATH = NEW_UPGRADE_PLDM_NOVERCHK_PACKAGE_DIR + "pcie-2-25/" + "sxe2_fw_pldm_asic_image_package_runmod*_noverchk.bin"
PCIE_X2_10G_PLDM_NOVERCHK_PACKAGE_PATH = NEW_UPGRADE_PLDM_NOVERCHK_PACKAGE_DIR + "pcie-2-10/" + "sxe2_fw_pldm_asic_image_package_runmod*_noverchk.bin"
OCP_X2_25G_PLDM_NOVERCHK_PACKAGE_PATH = NEW_UPGRADE_PLDM_NOVERCHK_PACKAGE_DIR + "ocp-2-25/" + "sxe2_fw_pldm_asic_image_package_runmod*_noverchk.bin"
OCP_X4_25G_PLDM_NOVERCHK_PACKAGE_PATH = NEW_UPGRADE_PLDM_NOVERCHK_PACKAGE_DIR + "ocp-4-25/" + "sxe2_fw_pldm_asic_image_package_runmod*_noverchk.bin"


"""
RDMA规格
"""
RDMA_MAX_VF_NUM = 32
RDMA_MAX_PF_NUM = 2
RDMA_MAX_PORT_NUM = 4
RDMA_MAX_TC_PER_PORT_NUM = 8
RDMA_MAX_CONC_QP_NUM = 4 * 1024
RDMA_MAX_QP_NUM = 256 * 1024
RDMA_MAX_CQ_NUM = 512 * 1024
RDMA_MAX_CEQ_NUM = 768 * 1024
RDMA_MAX_AEQ_NUM = 48 * 1024
RDMA_MAX_MR_NUM_PER_DEV = 4 * 1024
RDMA_MAX_MW_NUM_PER_DEV = 4 * 1024
RDMA_MAX_MR_LENGTH = 2 * 1024 * 1024 * 1024 * 1024  # 32 TB
RDMA_MAX_MW_LENGTH = 2 * 1024 * 1024 * 1024 * 1024  # 32 TB
RDMA_MAX_PD_NUM = 256 * 1024
RDMA_MAX_PBL_NUM = 256 * 1024 * 1024
RDMA_MAX_TRANS_DATA_LENGTH = 2 * 1024 * 1024 * 1024
RDMA_MAX_AH_NUM_PER_FUNC = 128 * 1024
RDMA_MAX_MR_PAGE = 1 * 1024 * 1024

RDMA_DRV_PARA_RESOURCE_PROFILE = 2
RDMA_DRV_PARA_MAX_RDMA_VFS = 32
RDMA_DRV_PARA_FRAGMENT_COUNT_LIMIT = 13


class EnvType:
    """
    环境类型
    """
    FPGA = "FPGA"
    HAPS = "HAPS"
    MLNX = "MLNX"


class Header:
    ETH = ['Ethernet.ethernetII']
    ETH_ARP = ['Ethernet.ethernetII', 'ARP.arp']
    ETH_VLAN_ARP = ['Ethernet.ethernetII', 'VLAN.vlan', 'ARP.arp']
    ETH_VLAN2_ARP = ['Ethernet.ethernetII', 'VLAN.vlan', 'VLAN.vlan', 'ARP.arp']
    ETH_VLAN_IP4 = ['Ethernet.ethernetII', 'VLAN.vlan', 'IPv4.ipv4']
    ETH_VLAN2_IP4 = ['Ethernet.ethernetII', 'VLAN.vlan', 'VLAN.vlan', 'IPv4.ipv4']
    ETH_CUSTOM = ['Ethernet.ethernetII', 'Custom.custom']
    ETH_VLAN_CUSTOM = ['Ethernet.ethernetII', 'VLAN.vlan', 'Custom.custom']
    ETH_VLAN_VLAN_CUSTOM = ['Ethernet.ethernetII', 'VLAN.vlan', 'VLAN.vlan', 'Custom.custom']
    ETH_8023_IP4 = ['Ethernet.8023', 'IPv4.ipv4']
    ETH_8023_IP6 = ['Ethernet.8023', 'IPv6.ipv6']
    ETH_8023_VLAN_IP4 = ['Ethernet.8023', 'VLAN.vlan', 'IPv4.ipv4']
    ETH_8023_VLAN_VLAN_IP4 = ['Ethernet.8023', 'VLAN.vlan', 'VLAN.vlan', 'IPv4.ipv4']
    ETH_IP4_CUSTOM = ['Ethernet.ethernetII', 'IPv4.ipv4', 'Custom.custom']
    ETH_IP6_CUSTOM = ['Ethernet.ethernetII', 'IPv6.ipv6', 'Custom.custom']
    PAUSE = ['Ethernet.ethernetII', 'Pause.pause']
    PFC = ['Ethernet.ethernetII', 'PFC.pfc']
    LACP = ['Ethernet.ethernetII', 'LACP.lacp']
    OSPF_HELLO = ['Ethernet.ethernetII', 'IPv4.ipv4', 'OSPFv2.ospfv2Hello']
    OSPF_UPDATE = ['Ethernet.ethernetII', 'IPv4.ipv4', 'OSPFv2.ospfv2LinkStateUpdate']
    IGMP_V2 = ['Ethernet.ethernetII', 'IPv4.ipv4', 'IGMP.igmpv2']
    IGMP_V3 = ['Ethernet.ethernetII', 'IPv4.ipv4', 'IGMP.igmpv3Query']
    L2TPV3_CTRL = ['Ethernet.ethernetII', 'IPv4.ipv4', 'L2TPv3.l2tpv3ControlOverIp']
    MLDV1_QUERY = ['Ethernet.ethernetII', 'IPv6.ipv6', 'ICMPv6.mldv1Query']
    MLDV1_REPORT = ['Ethernet.ethernetII', 'IPv6.ipv6', 'ICMPv6.mldv1Report']
    MLDV1_DONE = ['Ethernet.ethernetII', 'IPv6.ipv6', 'ICMPv6.mldv1Done']
    MLDV2_QUERY = ['Ethernet.ethernetII', 'IPv6.ipv6', 'ICMPv6.mldv2Query']
    MLDV2_REPORT = ['Ethernet.ethernetII', 'IPv6.ipv6', 'ICMPv6.mldv2Report']
    MAC_IN_MAC = ['Ethernet.ethernetII', 'VLAN.vlan', 'iTag.itag', 'Custom.custom']
    L2TPV2_AVP = ['generalTLV', 'generalWildcardTLV', 'messageTypeAvpOption', 'resultCodeAvpOption', 'protocolVersionAvpOption', 'framingCapabilitiesAvpOption', 'bearerCapabilitiesAvpOption', 'tieBreakerAvpOption', 'firmwareRevisionAvpOption', 'assignedTunnelIdAvpOption', 'receiveWindowSizeAvpOption', 'assignedSessionIdAvpOption', 'responseAvpOption', 'callSerialNumberAvpOption', 'minimumBpsAvpOption', 'maximumBpsAvpOption', 'bearerTypeAvpOption', 'framingTypeAvpOption', 'txConnectSpeedAvpOption', 'rxConnectSpeedAvpOption', 'physicalChannelIdAvpOption', 'proxyAuthenTypeAvpOption', 'proxyAuthenIdAvpOption']
    L2TPV3_AVP = ['generalTLV', 'generalWildcardTLV', 'messageTypeAvpOption', 'resultCodeAvpOption', 'tieBreakerAvpOption', 'receiveWindowSizeAvpOption', 'callSerialNumberAvpOption', 'physicalChannelIdAvpOption', 'circuitErrorAvpOption', 'routeIdAvpOption', 'assignedConnectionAvpOption', 'localSessionIdAvpOption', 'remoteSessionIdAvpOption', 'assignedCookieAvpOption', 'pwTypeAvpOption', 'l2SpecificSubAvpOption', 'dataSequencingAvpOption', 'txConnectSpeedAvpOption', 'rxConnectSpeedAvpOption', 'circuitStatusAvpOption']
    BFD_LIST = ['BFD.BFD', 'BFD.BFDWithSimplePasswordAuth', 'BFD.BFDWithMD5Auth', 'BFD.BFDWithSHA1Auth']


class ProtoType:
    PROTO_LEN_1 = '002C'
    PROTO_LEN_2 = '05DC'
    PROTO_LEN_3 = '007C'
    PROTO_LEN_4 = '0066'
    PROTO_LEN_5 = '003F'
    PROTO_LEN_6 = '006A'
    PROTO_LEN_7 = '002E'
    PPPOE_DISCOVERY = '8863'
    PPPOE_SESSION = '8864'
    VLAN_STAG = '88A8'
    ATA = '88A2'
    ECP = '8940'
    EAP = '888E'
    ECPRI = 'AEFE'
    NSH = '894F'
    MPLS_1 = '8847'
    MPLS_2 = '8848'
    ETH = '6558'
    IPV4 = '0800'
    IPV6 = '86DD'
    VLAN = '8100'
    ITAG = '88E7'
    ROCEV1 = '8915'
    PTP = '88F7'
    LLDP = '88CC'
    LACP = '8809'
    PAYLOAD = '88B5'
    MOBILITY = 135
    VRRP = 112
    EIGRP = 88
    OSPF = 89
    PIM = 103
    ICMP = 1
    IGMP = 2
    ESP = 50
    AH = 51
    ICMPV6 = 58
    SCTP = 132
    UDP = 17
    TCP = 6

    SSH = 22
    TELNET = 23
    LDP = 646
    BFD_1 = 3784
    BFD_2 = 3785
    BFD_3 = 4784
    BFD_4 = 6784
    BFD_5 = 7784
    IKE = 500
    IPSEC_NAT = 4500
    NTP = 123
    BGP = 179
    PTP_PORT = 320
    GTP_C = 2123
    GTP_U = 2152
    GTP = 3386
    PFCP = 8805
    GRE = 4754
    VXLAN = 4789
    VXLAN_GPE = 4790
    GENEVE = 6081
    MPLS_IN_UDP = 6635
    MAGIC = [9, 148, 152]

    ICMPv6_LIST = ['ra', 'na', 'ns', 'redirect', 'mldv1_query', 'mldv1_report', 'mld_done', 'mldv2_query', 'mldv2_report']


class Addr:
    MCAST_0 = '01:80:C2:00:00:03'
    MCAST_1 = '01:80:C2:00:00:14'
    MCAST_2 = '01:80:C2:00:00:15'
    MCAST_3 = '09:00:2B:00:00:05'
    MCAST_4 = '01:00:5E:90:00:02'
    MCAST_5 = '01:00:5E:90:00:03'
    MCAST_6 = '01:00:5E:00:00:12'
    MCAST_7 = '01:00:5E:00:00:05'
    MCAST_8 = '01:00:5E:00:00:06'
    MCAST_9 = '01:00:5E:00:00:64'
    MCAST_10 = '01:00:5E:00:00:0A'
    MCAST_11 = '01:00:5E:00:00:0D'
    MCAST_12 = '01:00:5E:00:00:09'
    MCAST_13 = '01:80:C2:00:00:02'
    MCAST_14 = '01:80:C2:00:00:01'
    MCAST_15 = '01:1b:19:00:00:00'
    MCAST_16 = '01:80:C2:00:00:0E'
    MCAST_20 = '33:33:00:00:00:02'
    MCAST_21 = '33:33:00:00:0B:02'
    MCAST_22 = '33:33:00:00:0A:02'
    MCAST_23 = '33:33:00:00:00:12'
    MCAST_24 = '33:33:00:00:00:01'
    MCAST_25 = '33:33:FF:44:00:00'
    MCAST_26 = '33:33:00:00:00:09'
    UNICAST_1 = '00:00:00:12:30:10'
    UNICAST_2 = '00:00:00:12:40:10'
    BROADCAST = 'FF:FF:FF:FF:FF:FF'
    BROADCAST_IP = '255.255.255.255'
    MCAST_IP_1 = '224.0.0.18'
    MCAST_IP_2 = '224.0.0.5'
    MCAST_IP_3 = '224.0.0.6'
    MCAST_IP_4 = '224.0.0.100'
    MCAST_IP_5 = '224.0.0.10'
    MCAST_IP_6 = '224.0.0.13'
    MCAST_IP_7 = '224.0.0.9'
    MCAST_IP6_1 = 'FF02::12'
    MCAST_IP6_2 = 'FF02::0A'
    MCAST_IP6_3 = 'FF02::0D'
    MCAST_IP6_4 = 'FF02::02'
    MCAST_IP6_5 = 'FF02::0B:02'
    MCAST_IP6_6 = 'FF02::01'
    MCAST_IP6_7 = 'ff02::1:FF44:0'
    MCAST_IP6_8 = 'FF02::09'
    LOCAL_IP6_1 = 'fe80000000000000220bc7fffe9f7a3a'
    LOCAL_IP6_2 = 'fe800000000000000109010000000002'


class Payload:
    ROCE_V1 = 'f002ffff0048ffff6400ffff00000000000001e9000000000000000001810101000001020001509c000125c800200000000000000000000000000000ffffffff000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000020300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001065ef880037'
    ISIS_1 = 'fefe03831b010612010003002904ab00000241410200000000000103d801020c000a808080000000000001010000'
    ISIS_2 = 'fefe03831b01061001000303000000000001001e05d9400000000000010101020110840402414101e810fe8000000000000002e0fcfffe3c64268102cc8ed303000000e502000008ff00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000008ff00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000008ff00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000008ff00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000008ff000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000088e00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
    ISIS_3 = 'fefe0383140100110100000200109400000b001e05d9018101cc0104030000018404c0550a03f00f000000000d0010940000010000000c08ff00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000008ff00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000008ff00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000008ff00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000008ff000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000089e0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
    ISIS_4 = 'fefe03831b010612010003007904af00000000000100000000000d8be8038102cc8ee502000001020110020c000a80808000000000000101840402414101800c0a80808002410000ffff0000e8102001000000000221020002fffe020101ec1c0000000a004020010000000002210000000a00402001000000000251'
    ISIS_5 = 'fefe0383210106190100030063000000000001000000000000000000ffffffffffffffff094004740000000000010000000000137fee0474000000000001010000000001db9b000000000241410200000000000105d400000000024141020001000000016436'
    ISIS_6 = 'fefe03831b010612010003003804af000000000001010000000001db9b038102cc8e02170000808080000000000001000080808000000241410200'
    PADI = '11090000000401010000'
    PTP = '0002002c00000000000000000000000000000000008063ffff0009ba0002043d0000000045b111492e3242630000'
    LLDP = '0207040004961fa726040405312f33060200780602000106020002060200030000ffffffffffffffffffffffffffffffaabb'
    UDP_CORRECT = '040004000022D9A3000102030405060708090a0b0c0d0e0f10111213141516171819'
    UDP_ERROR = '0400040000221234000102030405060708090a0b0c0d0e0f10111213141516171819'
    TCP_CORRECT = '040004000000000000000000501010009DE100000001020304050607080910111213141516171819'
    TCP_ERROR = '04000400000000000000000050101000123400000001020304050607080910111213141516171819'
    SCTP_CORRECT = '0B590B5900000E50C4C60011040000180001001440E44B920A1C062C1B66AF7E00000000'
    SCTP_ERROR = '0B590B5900000E5052C3055F040000180001001440E44B920A1C062C1B66AF7E00000000'
    ICMP_CORRECT = '0000877D00000001020304050607080910111213141516171819'
    ICMP_ERROR = '0000123400000001020304050607080910111213141516171819'
    PADO = '1107000000220101000001020006526f7574657201040010dc86bea485d4d541b2d7a7e73c753e6e'
    PADR = '1119000000220101000001020006526f7574657201040010dc86bea485d4d541b2d7a7e73c753e6e'
    PADS = '1165000300220101000001020006526f7574657201040010dc86bea485d4d541b2d7a7e73c753e6e'
    LCP_REQUEST = '110000030010c0210101000e010405d4050667453bbf'
    CHAP = '11000003001bc223020100191033b31b5020ebca95c4173c66b29f990b6e727231'
    IPCP_REQUEST = '11000003000c80210103000a030600000000'
    IPCP_NAK = '11000003000c80210303000a03060c010164000000000000000000'
    PAP = '110018b2001ac0230101001809616c6963656164736c09616c6963656164736c'
    LCP_ECHO_REQUEST = '110018b2000ac0210901000857dde38a'
    SNAP_1 = '0008aaaa0300'
    SNAP_2 = 'AAAA0300000088A8'
    SNAP_3 = 'AAAA030000000800'
    SNAP_ERROR_1 = 'a9aa03000000'
    SNAP_ERROR_2 = 'aaaa03100000'
    SNAP_ERROR_3 = 'aaaa03000000002E'
    SNAP_ERROR_4 = 'aaaa0300000005DC'
    ATA = '18000000000000000000000000000000'
    ECP = '10010000'
    EAP_START = '01010000'
    EAP_REQUEST = '010000050100000501'
    EAP_CHAP_REQUEST = '01000016010100160410675c0f0d6c0e1ac5d7e81346f48a51a1'
    EAP_CHAP_RESPONSE = '01000016020100160410bba20a4f5c644aa36764919af2cf4e1a'
    EAP_SUCCESS = '010000040301000400002ffc000000000000000000002ffc000031'
    ECPRI_0 = '10000014123487650F0E0D0C0B0A0908070605040302010000000000000000000000000000000000000000000000'
    ECPRI_1 = '10010014123487650F0E0D0C0B0A0908070605040302010000000000000000000000000000000000000000000000'
    ECPRI_2 = '10020014123487650F0E0D0C0B0A09080706050403020100000000000000000000000000000000000000'
    ECPRI_3 = '1003001812345678876543210F0E0D0C0B0A090807060504030201000000000000000000000000000000'
    ECPRI_4 = '1004001C110022330504030201000010FFEEDDCCBBAA998877665544332211000000000000000000'
    ECPRI_5 = '1005002A1100000045B111491C4178F40000000000B78000DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD'
    ECPRI_6 = '1006000A112200060504030201000000000000000000000000000000000000000000000000000000000000000000'
    ECPRI_7 = '1007000C11003301FFFF0000AAAAAAAA000000000000000000000000000000000000000000000000000000000000'
    NSH_IPV4 = '0002000100000000'
    NSH_IPV6 = '0002000200000000'
    NSH_ETH = '0002000300000000'
    NSH_NSH = '00020004000000000002000300000000507c6f4885a600000012301088B5'
    NSH_MPLS = '0002000500000000'
    NSH_UNDEFINED = '0002000600000000'
    NSH_TLV = '100600030000000000000013402000000012301012340000'
    MPLS_1 = '00010140450000280005000080fdb877c0a80002c0a8000a3830a500fff600000004000000050000272c0068'
    MPLS_2 = '0001004000010140450000280005000080fdb877c0a80002c0a8000a3830a500fff600000004000000050000272c0068'
    MPLS_ERROR_1 = '0001014055000014007b000080fd0000c0a80002c0a8000a'
    MPLS_ERROR_2 = '000101403000000000003bff2001000000000000000000000000000220010000000000000000000100f10011'
    NSH_ERROR_1 = '0002000400000000'
    NSH_ERROR_2 = '0002000600000000'
    NSH_ERROR_3 = '000200FD00000000'
    NSH_ERROR_4 = '0000000100000000'
    NSH_ERROR_5 = '0001000500000000'
    MOBILITY_1 = '11010000000012340000000000000000'
    MOBILITY_2 = '060201000000123400000000000000000000000000000000'
    MOBILITY_3 = '2C010000000012340000000000000000'
    VRRP_1 = '311a78010001a4170a8107030000000000000000'
    VRRP_2 = '311a78ff0001bf670a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a81070300000000000000000a8107030000000000000000'
    VRRP_3 = '311a78010001efef0a81070300000000000000000a81070300000000000000000a81070300000000000000000a8107030000000000000123'
    VRRP_4 = '301a78010001a5170a8107030000000000000000'
    VRRP_5 = '321a78010001eeef0a81070300000000000000000a81070300000000000000000a81070300000000000000000a8107030000000000000123'
    OSPF_HELLO = '0201002c0101010100000001fa9c00000000000000000000ffffff00000a0200000000280000000000000000'
    OSPFV3_DBD_1 = '0302001c01010101000000005e5d00000000001305dc0007004733de'
    OSPFV3_DBD_2 = '030205800101010100000000ab9600000000001305dc0003004733e101672001000000240000002480000001d0f8002801672001000000250000002580000001c007002801622001000000260000002680000001b015002801672001000000270000002780000001a0230028016220010000002800000028800000019031002801622001000000290000002980000001803f0028016420010000002a0000002a80000001704d0028016420010000002b0000002b80000001605b0028016220010000002c0000002c8000000150690028016720010000002d0000002d8000000140770028016420010000002e0000002e8000000130850028016420010000002f0000002f80000001209300280163200100000030000000308000000110a1002801622001000000310000003180000001ffaf002801622001000000320000003280000001efbd002801672001000000330000003380000001dfcb002801672001000000340000003480000001cfd9002801682001000000350000003580000001bfe7002801672001000000360000003680000001aff50028016320010000003700000037800000019f040028016220010000003800000038800000018f120028016220010000003900000039800000017f200028016220010000003a0000003a800000016f2e0028016220010000003b0000003b800000015f3c0028016020010000003c0000003c800000014f4a0028016520010000003d0000003d800000013f580028015e20010000003e0000003e800000012f660028015e20010000003f0000003f800000011f740028016020010000004000000040800000010f82002801652001000000410000004180000001fe90002801622001000000420000004280000001ee9e002801652001000000430000004380000001deac002801652001000000440000004480000001ceba002801652001000000450000004580000001bec8002801652001000000460000004680000001aed60028016020010000004700000047800000019ee40028016020010000004800000048800000018ef20028016020010000004900000049800000017e010028016020010000004a0000004a800000016e0f0028015e20010000004b0000004b800000015e1d0028015e20010000004c0000004c800000014e2b0028015a20010000004d0000004d800000013e390028016520010000004e0000004e800000012e470028016520010000004f0000004f800000011e550028016520010000005000000050800000010e630028015e2001000000510000005180000001fd71002801ae2001000000520000005280000001ed7f002801652001000000530000005380000001dd8d0028015e2001000000540000005480000001cd9b002801602001000000550000005580000001bda9002801652001000000560000005680000001adb70028016520010000005700000057800000019dc50028016020010000005800000058800000018dd30028016020010000005900000059800000017de10028016220010000005a0000005a800000016def0028016020010000005b0000005b800000015dfd0028015e20010000005c0000005c800000014d0c0028015e20010000005d0000005d800000013d1a0028015e20010000005e0000005e800000012d280028015e20010000005f0000005f800000011d360028016020010000006000000060800000010d44002801652001000000610000006180000001fc520028015e2001000000620000006280000001ec60002801652001000000630000006380000001dc6e002801602001000000640000006480000001cc7c002801162001000000650000006580000001bc8a002801162001000000660000006680000001ac98002800472001000000000101010180000012ed2f0018016920090000000100000001800000032375002c'
    EIGRP_1 = '0205ee68000000000000000000000000000000640001000c010001000000000f000400080c040102'
    EIGRP_2 = '0201fd9800000001000000010000000000000064'
    EIGRP_3 = '0201d5f10000000000000019000000000000029a0402002e000000000000000000000000000000000001f400000001000005ea00ff01000040200100000001000100'
    PIM_1 = '2000df93000100020069'
    PIM_2 = '2100deff00000000600000000408113f3ffe050700000001026097fffe0769eaff050000000000000000000000009999df29270f04089bac666f7274756e653e207368312e69696a6c61622e6e657420617420576564204f63742031332031333a31393a3532204a535420313939393a0a666f7274756e653e2049662074686520636f6c6c656765732077657265206265747465722c2069662074686579207265616c6c79206861642069742c20796f7520776f756c64206e65656420746f0a666f7274756e653e206765742074686520706f6c6963652061742074686520676174657320746f206b656570206f7264657220696e2074686520696e72757368696e67206d756c7469747564652e0a666f7274756e653e2053656520696e20636f6c6c65676520686f772077652074687761727420746865206e61747572616c206c6f7665206f66206c6561726e696e67206279206c656176696e670a666f7274756e653e20746865206e61747572616c206d6574686f64206f66207465616368696e67207768617420656163682077697368657320746f206c6561726e2c20616e6420696e73697374696e670a666f7274756e653e207468617420796f75207368616c6c206c6561726e207768617420796f752068617665206e6f207461737465206f7220636170616369747920666f722e20205468650a666f7274756e653e20636f6c6c6567652c2077686963682073686f756c64206265206120706c616365206f662064656c6967687466756c206c61626f722c206973206d616465206f64696f75730a666f7274756e653e20616e6420756e6865616c7468792c20616e642074686520796f756e67206d656e206172652074656d7074656420746f20667269766f6c6f757320616d7573656d656e747320746f0a666f7274756e653e2072616c6c79207468656972206a6164656420737069726974732e20204920776f756c64206861766520746865207374756469657320656c6563746976652e0a666f7274756e653e205363686f6c61727368697020697320746f2062652063726561746564206e6f7420627920636f6d70756c73696f6e2c20627574206279206177616b656e696e67206120707572650a666f7274756e653e20696e74657265737420696e206b6e6f776c656467652e2020546865207769736520696e7374727563746f72206163636f6d706c697368657320746869732062790a666f7274756e653e206f70656e696e6720746f2068697320707570696c7320707265636973656c79207468652061747472616374696f6e73207468652073747564792068617320666f720a666f7274756e653e2068696d73656c662e2020546865206d61726b696e6720697320612073797374656d20666f72207363686f6f6c732c206e6f7420666f722074686520636f6c6c6567653b20666f720a666f7274756e653e20626f79732c206e6f7420666f72206d656e3b20616e642069'
    PIM_3 = '23004D4D0200fe8000000000000002e018fffe982725000100d202000080ff05000000000000000000000000999900010001020007803ffe050100001c010200f8fffe03d9c0020005803ffe050700000001020086fffe0580fa'
    ICMPV6_RS_1 = '850057a7000000000101000002010104'
    ICMPV6_RS_2 = '850157a700000F100101000F02010104'
    ICMPV6_RA_1 = '860056a7000000000101000002010104'
    ICMPV6_RA_2 = '86FF55a8000000000101000002010104'
    IGMP = '1600089be1000064'
    AH = '04040000289224ca000000015df92b67b267c25d93797332'
    ESP = '000000070000000e140101011401010208007a8b3ffd000736e5bb63000000008954030000000000101112131415161718191a1b1c1d1e1f202122232425262728292a2b2c2d2e2f30313233343536370102020103000000040000007002000000000000'
    ICMPV6_REDIRECT_1 = '890013810000000020010000000000000000000000000002200100000000000000000000000000020101000002010104'
    ICMPV6_REDIRECT_2 = '8900f36d000000002001000000000000000000000000000220010000000000000000000000000002200100000000000000000000000000020101000002010104'
    TCP_TS_NOP_NOP = '080A123456789ABCDEF00101'
    TCP_TS_NOP_EOL = '080A123456789ABCDEF0010000'
    TCP_NOP_NOP_TS = '0101080A123456789ABCDEF0000000'
    TCP_NOP_TS_NOP = '01080A123456789ABCDEF00100'
    TCP_NOP_TS_EOL = '01080A123456789ABCDEF000'
    TCP_TS_EOL = '080A123456789ABCDEF0000000'
    TCP_MSS = '020411220000'
    TCP_60_bytes = '02041122030308050104021103051411223344556677889900112233080A123456789ABCDEF00101'
    SSH_1 = '5353482d322e302d4f70656e5353485f382e370d0a'
    SSH_2 = '000004e40b147d900de6c89c70d5b4636a1cb8a4ecde0000013b6469666669652d68656c6c6d616e2d67726f75702d65786368616e67652d7368613235362c6469666669652d68656c6c6d616e2d67726f75702d65786368616e67652d736861312c6469666669652d68656c6c6d616e2d67726f757031342d7368613235362c6469666669652d68656c6c6d616e2d67726f757031342d736861312c6469666669652d68656c6c6d616e2d67726f7570312d736861312c727361323034382d7368613235362c727361313032342d736861312c63757276653434382d7368613531322c637572766532353531392d7368613235362c637572766532353531392d736861323536406c69627373682e6f72672c656364682d736861322d6e697374703235362c656364682d736861322d6e697374703338342c656364682d736861322d6e697374703532312c6578742d696e666f2d630000007b7373682d656432353531392c7373682d65643434382c65636473612d736861322d6e697374703235362c65636473612d736861322d6e697374703338342c65636473612d736861322d6e697374703532312c7273612d736861322d3531322c7273612d736861322d3235362c7373682d7273612c7373682d647373000000bd6165733235362d6374722c6165733235362d6362632c72696a6e6461656c2d636263406c797361746f722e6c69752e73652c6165733139322d6374722c6165733139322d6362632c6165733132382d6374722c6165733132382d6362632c63686163686132302d706f6c7931333035406f70656e7373682e636f6d2c336465732d6374722c336465732d6362632c626c6f77666973682d6374722c626c6f77666973682d6362632c617263666f75723235362c617263666f7572313238000000bd6165733235362d6374722c6165733235362d6362632c72696a6e6461656c2d636263406c797361746f722e6c69752e73652c6165733139322d6374722c6165733139322d6362632c6165733132382d6374722c6165733132382d6362632c63686163686132302d706f6c7931333035406f70656e7373682e636f6d2c336465732d6374722c336465732d6362632c626c6f77666973682d6374722c626c6f77666973682d6362632c617263666f75723235362c617263666f75723132380000009b686d61632d736861322d3235362c686d61632d736861312c686d61632d736861312d39362c686d61632d6d64352c686d61632d736861322d3235362d65746d406f70656e7373682e636f6d2c686d61632d736861312d65746d406f70656e7373682e636f6d2c686d61632d736861312d39362d65746d406f70656e7373682e636f6d2c686d61632d6d64352d65746d406f70656e7373682e636f6d0000009b686d61632d736861322d3235362c686d61632d736861312c686d61632d736861312d39362c686d61632d6d64352c686d61632d736861322d3235362d65746d406f70656e7373682e636f6d2c686d61632d736861312d65746d406f70656e7373682e636f6d2c686d61632d736861312d39362d65746d406f70656e7373682e636f6d2c686d61632d6d64352d65746d406f70656e7373682e636f6d0000001a7a6c69622c7a6c6962406f70656e7373682e636f6d2c6e6f6e650000001a7a6c69622c7a6c6962406f70656e7373682e636f6d2c6e6f6e65000000000000000000000000007316f1c9fb8f1f74dd4fa6'
    TELNET_1 = 'fffd03fffb18fffb1ffffb20fffb21fffb22fffb27fffd05fffb23'
    TELNET_2 = 'fffa2000393630302c39363030fff0fffa230062616d2e7a696e672e6f72673a302e30fff0fffa270000444953504c41590162616d2e7a696e672e6f72673a302e30fff0fffa1800787465726d2d636f6c6f72fff0'
    LDP_TCP_1 = '000100200a010102000002000016000000050500000e000100b400000000010101010000'
    LDP_TCP_2 = '000100700101010100000300001600001f2f0101000e00010a01010101010101c0a801010400001700001f30010000070200011801010102000004000000030400001600001f3101000006020001100a0102000004000000030400001700001f320100000702000118c0a8010200000400000003'
    LDP_UDP = '0001001e0a0101020000010000140000000104000004000f0000040100040a010102'
    IKE_1 = '63a79b5eae8561a400000000000000000110020000000000000000fc0d00003800000001000000010000002c01010001000000240101000080010005800200028004000280030001800b0001000c0004000070800d00001801528bbbc00696121849ab9a1c5b2a51000000010d0000181e2b516905991c7d7c96fcbfb587e461000000090d0000144a131c81070358455c5728f20e95452f0d00001490cb80913ebb696e086381b5ec427b1f0d0000144048b7d56ebce88525e7de7f00d6c2d30d000014fb1de3cdf341b7ea16b7e5be0855f1200d00001426244d38eddb61b3172a36e3d0cfb81900000014e3a5966a76379fe707228231e5ce8652'
    IKE_2 = '55e5feb51e38275139411f58b2a6e815081005014d2b3ba00000004ccd52be7664ac639dc1efc22407d9ac8e76bc666cd45f8b303921e4b4e1e6137be8ce5a05307e288b4025811f6b9d3887'
    IKE_3 = 'f34dd4642a28d80839411f58b2a6e81508102001d6ffdb8c000000ac8c4b8e6ccaa92f6636ded9e77adc36e61c6062b31091e78db6457caac83e771814f9bc2a8492d3fc07948e363ab09a48e3eed444cc321ce76194271dcb4ea929acf717723553ff368b93f56a543ed16d05bb29955c5ad078d150bacead58b10d0007870a8f101d168f9785d8bd55027031e6808375f236885605cc8287de0c6b2a6612afa9f421a4121abc4b1b1dfe3e'
    NTP = 'd9000afa000000000001029000000000000000000000000000000000000000000000000000000000c50204ecec42ee92'
    PTP_UDP = '1b0200400000000c000000000000000000000000008063ffff0009ba0001003a0501000045b1115a0a734660000000600000008063ffff0009baf82100008080'
    BGP_1 = 'ffffffffffffffffffffffffffffffff002501040064005afe010403080206010400010001'
    BGP_2 = 'ffffffffffffffffffffffffffffffff01c002000000194001010040020402010064400304020101024005040000000a18b4010118b4010218b4010318b4010418b4010518b4010618b4010718b4010818b4010918b4010a18b4010b18b4010c18b4010d18b4010e18b4010f18b4011018b4011118b4011218b4011318b4011418b4011518b4011618b4011718b4011818b4011918b4011a18b4011b18b4011c18b4011d18b4011e18b4011f18b4012018b4012118b4012218b4012318b4012418b4012518b4012618b4012718b4012818b4012918b4012a18b4012b18b4012c18b4012d18b4012e18b4012f18b4013018b4013118b4013218b4013318b4013418b4013518b4013618b4013718b4013818b4013918b4013a18b4013b18b4013c18b4013d18b4013e18b4013f18b4014018b4014118b4014218b4014318b4014418b4014518b4014618b4014718b4014818b4014918b4014a18b4014b18b4014c18b4014d18b4014e18b4014f18b4015018b4015118b4015218b4015318b4015418b4015518b4015618b4015718b4015818b4015918b4015a18b4015b18b4015c18b4015d18b4015e18b4015f18b4016018b4016118b4016218b4016318b40164'
    PFCP_N = '200600A9123487000F0E0D0C0B0A0908070605040302010000000000000000000000000000000000000000000000'
    PFCP_S = '21330014123487650F0E0D0C0B0A0908070605040302010000000000000000000000000000000000000000000000'
    SCAPY_1 = '080045000028000100004070D950C0010101E0000012'
    SCAPY_2 = '080045000040000100004059d95cc0010101e0000005'
    SCAPY_3 = '08004500001c000100004002d978c0010101e0000064'
    SCAPY_4 = '08004500003c000100004058d95cc0010101e000000a'
    SCAPY_5 = '08004500001e000100004067d968c0010101e000000d'
    GRE_ROUTE = '001122040000000000000000'

class FrameLen:
    LEN_1 = 64
    LEN_2 = 1518
    LEN_4 = 142
    LEN_5 = 120
    LEN_6 = 81


class EnvRunType:
    """
    调试环境类型:
    - 本地调试为DEBUG
    - jenkins默认执行Remote
    """
    REMOTE = "Remote"
    DOCKER = "Docker"
    DEBUG = "Debug"


class KvmImageTempalte:

    @classmethod
    def template(cls, type: str):
        name = cls.random_str()
        if type == "min":
            return {"name": f"ty_vm_{name}", "vcpus": 2, "memory": "2048",
                    "template": f"/home/ty/ty_vm_{name}.qcow2,size=20,format=qcow2"}
        elif type == "mid":
            return {"name": f"ty_vm_{name}", "vcpus": 4, "memory": "8192",
                    "template": f"/home/ty/ty_vm_{name}.qcow2,size=20,format=qcow2"}
        elif type == "max":
            name = cls.random_str()
            return {"name": f"ty_vm_{name}", "vcpus": 8, "memory": "16384",
                    "template": f"/home/ty/ty_vm_{name}.qcow2,size=20,format=qcow2"}
        # match type:
        #     case "min":
        #         return {"name": f"ty_vm_{name}", "vcpus": 2, "memory": "2048",
        #                 "template": f"/home/ty/ty_vm_{name}.qcow2,size=20,format=qcow2"}
        #     case "mid":
        #         return {"name": f"ty_vm_{name}", "vcpus": 4, "memory": "8192",
        #                 "template": f"/home/ty/ty_vm_{name}.qcow2,size=20,format=qcow2"}
        #     case "max":
        #         name = cls.random_str()
        #         return {"name": f"ty_vm_{name}", "vcpus": 8, "memory": "16384",
        #                 "template": f"/home/ty/ty_vm_{name}.qcow2,size=20,format=qcow2"}

    @classmethod
    def random_str(cls):
        tmp = ["a", "b", "c", "d", "e", "f", "g", "x", "y", "z", "_", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
        return "".join(random.choices(tmp, k=5))


class DataType:
    RC = "RC"
    UD = "UD"
    UC = "UC"
    DC = "DC"
    ALL = ["RC", "UD", "UC"]  # !!未加入DC

class MtuType:
    MTU_0 = "1500"
    MTU_1 = "256"
    MTU_2 = "512"
    MTU_3 = "1024"
    MTU_4 = "2048"
    MTU_5 = "4096"
    MTU_6 = "6000"
    MTU_7 = "9000"
    MTU_8 = "9600"

    @classmethod
    def get_mtu_type(cls, mtu: str):
        if mtu == "1":
            return cls.MTU_1
        elif mtu == "2":
            return cls.MTU_2
        elif mtu == "3":
            return cls.MTU_3
        elif mtu == "4":
            return cls.MTU_4
        elif mtu == "5":
            return cls.MTU_5
        # match mtu:
        #     case "1":
        #         return cls.MTU_1
        #     case "2":
        #         return cls.MTU_2
        #     case "3":
        #         return cls.MTU_3
        #     case "4":
        #         return cls.MTU_4
        #     case "5":
        #         return cls.MTU_5
class DataMulticastFilter:
    #通过所有
    type_all = "0xff"
    #仅通过Neighbor_AD
    type_NA = "0x01"
    #仅通过ipv6_router_AD
    type_RA = "0x02"
    #仅通过DHCPv6 relay and server multicast
    type_DHCP_relay = "0x04"
    #仅通过_DHCP_multi
    type_DHCP_multi = "0x08"
    #仅通过multicast_ipv6_MLD
    type_MLD = "0x10"
    #仅通过multicast_ipv6_neighbor_solicitation
    type_NS = "0x20"
    #全部不置位（排除全部）
    type_pass_none = "0x00"
    enable='0x01'
    disable='0x00'

class DataBroadcastFilter:
    # @changelog 2025.11.19 gaoyb: 协议只是用低四位bit,此处只设置低四位为1
    type_all =  "0x0f"  # "0xff"

    type_arp = "0x01"

    type_dhcp_client = "0x02"

    type_dhcp_server = "0x04"

    type_netbios = "0x08"

    type_pass_none = "0x00"


class CastType:
    #支持广播
    type_enable_broadcast = "0x10"
    #禁用广播
    type_disable_broadcast = "0x11"
    #支持组播
    type_enable_mul_cast = "0x12"
    #禁用组播
    type_disable_mul_cast = "0x13"
    #单播
    type_unicast = "0x0e"

class DataPktSize:
    SIZE_2 = '2'
    SIZE_4 = '4'
    SIZE_8 = '8'
    SIZE_16 = '16'
    SIZE_32 = '32'
    SIZE_64 = '64'
    SIZE_128 = '128'
    SIZE_256 = '256'
    SIZE_512 = '512'
    SIZE_1K = '1024'
    SIZE_2K = '2048'
    SIZE_4K = '4096'
    SIZE_8K = '8192'
    SIZE_16K = '16384'
    SIZE_32K = '32768'
    SIZE_64K = '65536'
    SIZE_128K = '131072'
    SIZE_256K = '262144'
    SIZE_512K = '524288'
    SIZE_1M = '1048576'
    SIZE_2M = '2097152'
    SIZE_4M = '4194304'
    SIZE_8M = '8388608'
    SIZE_16M = '16777216'
    SIZE_32M = '33554432'
    SIZE_64M = '67108864'
    SIZE_128M = '134217728'
    SIZE_256M = '268435456'
    SIZE_512M = '536870912'
    SIZE_1G = '1073741824'
    SIZE_2G_1 = '2147483647'

    @classmethod
    def size_test_big(cls):
        return [
            cls.SIZE_16K
        ]

    @classmethod
    def size_test2(cls):
        return [
            cls.SIZE_2,
            cls.SIZE_4
        ]

    @classmethod
    def size_test1(cls):
        return [
            cls.SIZE_256
        ]

    @classmethod
    def size_256(cls):
        return [
            cls.SIZE_256
        ]

    @classmethod
    def size_512(cls):
        return [
            cls.SIZE_512
        ]

    @classmethod
    def size_1024(cls):
        return [
            cls.SIZE_1K
        ]

    @classmethod
    def size_2048(cls):
        return [
            cls.SIZE_2K
        ]

    @classmethod
    def size_4096(cls):
        return [
            cls.SIZE_4K
        ]

    @classmethod
    def size_less_than_256(cls):
        return [
            cls.SIZE_2,
            cls.SIZE_4,
            cls.SIZE_8,
            cls.SIZE_16,
            cls.SIZE_32,
            cls.SIZE_64,
            cls.SIZE_128,
            cls.SIZE_256
        ]

    @classmethod
    def size_less_than_512(cls):
        return [
            cls.SIZE_2,
            cls.SIZE_4,
            cls.SIZE_8,
            cls.SIZE_16,
            cls.SIZE_32,
            cls.SIZE_64,
            cls.SIZE_128,
            cls.SIZE_256,
            cls.SIZE_512
        ]

    @classmethod
    def size_less_than_1k(cls):
        return [
            cls.SIZE_2,
            cls.SIZE_4,
            cls.SIZE_8,
            cls.SIZE_16,
            cls.SIZE_32,
            cls.SIZE_64,
            cls.SIZE_128,
            cls.SIZE_256,
            cls.SIZE_512,
            cls.SIZE_1K
        ]

    @classmethod
    def size_less_than_2k(cls):
        return [
            cls.SIZE_2,
            cls.SIZE_4,
            cls.SIZE_8,
            cls.SIZE_16,
            cls.SIZE_32,
            cls.SIZE_64,
            cls.SIZE_128,
            cls.SIZE_256,
            cls.SIZE_512,
            cls.SIZE_1K,
            cls.SIZE_2K
        ]

    @classmethod
    def size_less_than_4k(cls):
        return [
            cls.SIZE_2,
            cls.SIZE_4,
            cls.SIZE_8,
            cls.SIZE_16,
            cls.SIZE_32,
            cls.SIZE_64,
            cls.SIZE_128,
            cls.SIZE_256,
            cls.SIZE_512,
            cls.SIZE_1K,
            cls.SIZE_2K,
            cls.SIZE_4K
        ]

    @classmethod
    def all_size(cls):
        return [
            cls.SIZE_2,
            cls.SIZE_4,
            cls.SIZE_8,
            cls.SIZE_16,
            cls.SIZE_32,
            cls.SIZE_64,
            cls.SIZE_128,
            cls.SIZE_256,
            cls.SIZE_512,
            cls.SIZE_1K,
            cls.SIZE_2K,
            cls.SIZE_4K,
            cls.SIZE_8K,
            cls.SIZE_16K,
            cls.SIZE_32K,
            cls.SIZE_64K,
            cls.SIZE_128K,
            cls.SIZE_256K,
            cls.SIZE_512K,
            cls.SIZE_1M,
            cls.SIZE_2M,
            cls.SIZE_4M,
            cls.SIZE_8M,
            cls.SIZE_16M,
            cls.SIZE_32M,
            cls.SIZE_64M,
            cls.SIZE_128M,
            cls.SIZE_256M,
            cls.SIZE_512M,
            cls.SIZE_1G,
            cls.SIZE_2G_1
        ]

    @classmethod
    def size_atomic(cls):
        return [
            cls.SIZE_8
        ]

class DataTime:
    time1 = "2022-11-11 11:11:00"
    time2 = "2260-11-11 11:11:00"
    time3 = "1970-11-11 11:11:00"

IPProtocolType = {'0': 'IPv6 Hop-by-Hop', '1': 'ICMP', '2': 'IGMP', '3': 'GGP', '4':'ethernet II', '5': 'Stream','6': 'TCP', '7': 'CBT', '8': 'EGP', '9': 'IGP', '10': 'BBN RCC', '11': 'NVP', '12': 'PUP', '13': 'ARGUS', '14': 'EMCON', '15': 'XNET', '16': 'CHAOS', '17': 'UDP',
                  # Protocol: Encap Security Payload (50)
                '18': 'MUX', '19': 'DCN-MEAS', '21': 'PRM ', '22': 'XNS-IDP', '23': 'TRUNK-1', '24': 'TRUNK-2', '25': 'LEAF-1', '26': 'LEAF-2', '28': 'IRTP', '29': 'ISO-TP4', '30': 'NETBLT',
                '31': 'MFE-NSP', '32': 'MERIT-INP', '33': 'DCCP', '34': '3PC', '35': 'IDPR', '36': 'XTP', '37': 'DDP', '38': 'IDPR-CMTP', '39': 'TP++', '40': 'IL', '41': 'IPv6 encapsulation', '42': 'SDRP',
                '43': 'Routing Header', '44': 'Fragment Header', '45': 'IDRP', '48': 'DSR', '49': 'BNA', '52': 'I-NLSP',  '53': 'SWIPE', '55': 'Min-IPv4', '56': 'TLSP', '57': 'SKIP',
                '61': 'Destination Options for IPv6 any host internal protocol', '62': 'CFTP', '63': 'any local network', '64': 'SAT-EXPAK', '65': 'Kryptolan', '66': 'RVD', '67': 'IPPC',
                '68': 'any distributed file system', '69': 'SAT-MON', '70': 'VISA', '71': 'IPCV', '72': 'CPNX', '73': 'CPHB', '74': 'WSN', '75': 'PVP', '76': 'BR-SAT-MON', '77': 'SUN-ND',
                '78': 'WB-MON', '79': 'WB-EXPAK', '80': 'ISO-IP', '81': 'VMTP', '82': 'SECURE-VMTP', '83': 'VINES', '84': 'TTP', '85': 'NSFNET-IGP', '86': 'DGP', '87': 'TCF', '88': 'EIGRP',
                '20': 'HMP', '27': 'RDP', '46': 'RSVP', '47': 'GRE', '51': 'AH', '50': 'ESP', '54': 'NARP ', '59': 'IPv6-NoNxt','58': 'ICMPV6', '60': 'IPv6-Opts', '89': 'OSPF',
                '90': 'Sprite RPC Protocol', '91': 'LARP', '92': 'MTP', '93': 'AX.25 Frames', '94': 'IP-within-IP Encapsulation Protocol', '95': 'MICP', '96': 'SCC-SP', '97': 'ETHERIP',
                '98': 'ENCAP', '99': 'any private encryption scheme', '100': 'GMTP', '101': 'IFMP', '102': 'PNNI over IP', '103': 'PIM', '104': 'ARIS', '105': 'SCPS', '106': 'QNX',
                '107': 'Active Networks', '108': 'IPComp', '109': 'SNP', '110': 'CPP', '111': 'IPX in IP', '113': 'PGM', '114': 'any 0-hop protocol', '116': 'DDX', '117': 'IATP',
                '118': 'STP', '119': 'SRP', '120': 'UTI', '121': 'SMP', '122': 'SM', '123': 'PTP', '125': 'FIRE', '128': 'SSCOPMCE', '129': 'IPLT', '130': 'SPS', '131': 'PIPE',
                '133': 'FC', '134': 'RSVP-E2E-IGNORE', '135': 'Mobility Header', '138': 'MANET Protocols', '139': 'Host Identity Protocol', '140': 'Shim6 Protocol', '141': 'WESP',
                '142': 'ROHC', '143': 'Ethernet', '144': 'AGGFRAG encapsulation payload for ESP', '145': 'NSH', '146': 'Homa', '147': 'BIT-EMU', '148': 'Unassigned', '256': 'GENEVE',
                '112': 'VRRP', '115': 'L2TP', '124': 'ISIS', '126': 'CRTP', '127': 'CRUDP', '132': 'SCTP', '136': 'UDPLite', '137': 'MPLS-in-IP', '253': 'Use for experimentation and testing', '254': 'Use for experimentation and testing', '255': 'Reserved'}
