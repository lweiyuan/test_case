#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      haibin.xu, junfeng.he
date:        2020.07.04 17:12
description: 定义枚举变量
change:      2020.08.28 junfeng.he调整枚举类结构，分离部分枚举变量为常量
"""
from enum import Enum, unique


@unique
class TestEntryEnum(Enum):
    """
    该枚举用于定义测试入口，同禅道选项中的test_entry, 用于测试用例脚本使用
    # direct
    # switch
    # single_mode
    # dpdk_mode
    """
    HOST = 0
    SOC = 1
    SINGLE_MODE = 2
    DPDK_MODE = 3
    DPDK_AUTO_MODE = 4
    UEFI_MODE = 5
    VF_KEEP_MODE = 6


@unique
class TestEntryStrEnum(Enum):
    """
    该枚举用于定义测试入口，同禅道选项中的test_entry
    """
    HOST = 'host'
    SOC = 'soc'
    UEFI = 'uefi'
    EXPANDER = 'expander'


@unique
class ByteEnum(Enum):
    """
    该枚举用于定义Byte（8bit）的位操作
    由于python 没有无符号类型，若直接取反会变成负数
    特定义FULL_BYTE用来取位反
    方法：ByteEnum.BITx.value^ByteEnum.FULL_BYTE.value —> ~ByteEnum.BITx.value
    example：0x01^0xFF = 0xFE
    """
    BIT0 = 0x01
    BIT1 = 0x02
    BIT2 = 0x04
    BIT3 = 0x08
    BIT4 = 0x10
    BIT5 = 0x20
    BIT6 = 0x40
    BIT7 = 0x80
    FULL_BYTE = 0xFF


@unique
class NumFormatEnum(Enum):
    """
    数值的不同进制位数
    """
    HEX = 16
    DEC = 10
    OCT = 8
    BIN = 2


@unique
class CmdStatusEnum(Enum):
    """
    cmd 执行成功返回值为0，执行失败为非0，可能是1，2，3 ...
    故判断指令执行成功与否，只能用SUCCESS来判断。
    """
    SUCCESS = 0


@unique
class CliStatusEnum(Enum):
    """
    cli 指令执行结果标识成功与否
    """
    SUCCESS = "Success"
    FAILURE = "Failure"
    ERROR = 'ERROR'


@unique
class RunRegion(Enum):
    """
    当前固件启动分区（本身pingpong升级互为主备，只是用作区分）
    """
    MASTER = "MASTER"
    SLAVE = "SLAVE"


@unique
class CaseOrderEnum(Enum):
    """
    测试顺序
    """
    DEFAULT_ORDER = 'default'
    DESC_ORDER = 'desc'
    RANDOM_ORDER = 'random'


@unique
class HostCpuEnum(Enum):
    """
    cpu 架构
    """
    CPU_X86 = 'x86'
    CPU_ARM = 'arm'
    CPU_MIPS = 'mips'


@unique
class HostLabelTypeEnum(Enum):
    """host label 类型"""
    VMS = 'vms'
    PMS = 'pms'


@unique
class CpuArchitecture(Enum):
    """
    cpu 架构
    """
    CPU_X86 = 0
    CPU_ARM = 1
    CPU_MIPS = 2


@unique
class BitStateEnum(Enum):
    """
    cmd获取标准输出的位操作结果为字符型0或1
    '0'代表 disable
    '1'代表 enable
    """
    DISABLE = '0'
    ENABLE = '1'


@unique
class RtnStatusEnum(Enum):
    """
    自定义函数指定返回状态，0为成功，-1为失败
    """
    SUCCESS = 0
    FAIL = -1
    FIO_VERIFY_ERR = 10000


@unique
class RxfhIndirEnum(Enum):
    """
    RX重定向表中的可修改参数
    """
    HKEY = 'hkey'
    HFUNC = 'hfunc'
    EQUAL = 'equal'
    WEIGHT = 'weight'
    DEFAULT = 'default'
    CONTEXT = 'context'
    DELETE = 'delete'


@unique
class SwitchEnum(Enum):
    """
    开关状态
    """
    SWITCH_ON = 'on'
    SWITCH_OFF = 'off'
    SWITCH_EMPTY = ''
    # 命令执行返回状态中的开关状态关键字
    SWITCH_SHOW_ON = 'On'
    SWITCH_SHOW_OFF = 'Off'


@unique
class ControllerStatusEnum(Enum):
    """
    控制卡状态
    """
    OPTIMAL = 'Optimal'
    NEEDS_ATTENTION = 'Needs Attention'
    FAILED = 'Failed'


@unique
class SpeedDuplexEnum(Enum):
    """
    网卡的速率带宽
    等号前面表示网卡支持的速率和双工模式
    等号后面表示寄存器写入寄存器中的值
    """

    TEN_GBPS_FULL_DUPLEX = "7"
    ONE_GBPS_FULL_DUPLEX = "6"


@unique
class BugTypeEnum(Enum):
    """
    定义bug类型，测试用例脚本中生成bug指定bug类型时，非此枚举变量中的类型，一律不予认可
    """
    IO_ERROR = 'IO错误'
    CC_ERROR = '一致性错误'
    PERFORMANCE = '性能问题'
    CORE = 'Core'
    CRASH = 'Crash'
    CORE_CRASH = 'CoreAndCrash'
    FUNCTION = '功能问题'
    DISPLAY = '显示问题'
    STABILITY = '稳定性问题'
    RELIABILITY = '可靠性问题'
    STRESS = '压力问题'
    MEMORY_LEAK = '内存泄漏问题'
    PROTOCOL = '协议问题'
    COMPATIBILITY = '兼容性问题'
    SECURITY = '安全性问题'
    DESIGN_DEFECT = '需求设计缺陷'
    STANDARD = '标准规范'
    INTERFACE = '界面问题'
    TIMEOUT = '超时问题'
    PARAMETERS = '参数配置问题'
    NETWORK = '网络问题'
    FILE_ERROR = '文件错误问题'


@unique
class MessageType(Enum):
    UNICAST = "unicast"
    MULCAST = "multi-cast"
    BROADCAST = "broadcast"


@unique
class TransportProtocal(Enum):
    """传输的协议类型"""
    TRANSPORT_ETH = "mac"
    TRANSPORT_TCP = "tcp"
    TRANSPORT_UDP = "udp"
    TRANSPORT_IP = "ip"
    TRANSPORT_SCTP = "sctp"
    TRANSPORT_ICMP = "icmp"
    TRANSPORT_ARP = "arp"
    ETHER_VLAN = "vlan"
    ETHER_SNAP = "snap"
    ETHER_LLC = "llc"
    TRANSPORT_ICMPV6 = 'icmpv6'
    ETHER_II = 'ethernet II'
    TRANSPORT_IPV6 = "ipv6"
    TRANSPORT_TCP4 = "tcp4"
    TRANSPORT_TCP6 = "tcp6"
    TRANSPORT_UDP4 = "udp4"
    TRANSPORT_UDP6 = "udp6"
    TRANSPORT_SCTP6 = "sctp6"
    TRANSPORT_ESP = "esp"
    TRANSPORT_PTP = 'ptp'
    TRANSPORT_IPv6Ext = 'IPv6 Hop-by-Hop'
    TRANSPORT_ICMPv6Echo = 'IPv6 encapsulation'
    TRANSPORT_IPv6ExtHdrRouting = 'Routing Header'
    TRANSPORT_IPv6ExtHdrFragment = 'Fragment Header'
    TRANSPORT_IPv6ExtHdrDestOpt = 'IPv6-Opts'
    TRANSPORT_IPv6Mobility = 'Mobility Header'
    TRANSPORT_GENEVE = 'GENEVE'
    TRANSPORT_GRE = 'GRE'
    TRANSPORT_MACVLAN = 'macvlan'
    TRANSPORT_MACVLAN_IPV4 = 'macvlan_ipv4'
    TRANSPORT_MACVLAN_IPV4_UDP = 'macvlan_ipv4_udp'
    TRANSPORT_MACVLAN_IPV4_TCP = 'macvlan_ipv4_tcp'
    TRANSPORT_IPSEC_IPV4_ESP = 'ipsec_ipv4_esp'
    TRANSPORT_IPSEC_IPV6_ESP = 'ipsec_ipv6_esp'
    TRANSPORT_IPSEC_IPV4_AH = 'ipsec_ipv4_ah'
    TRANSPORT_IPSEC_IPV6_AH = 'ipsec_ipv6_ah'
    TRANSPORT_IPSEC_ipv4_NATT_ESP = 'ipsec_ipv4_natt_esp'
    TRANSPORT_IPSEC_ipv6_NATT_ESP = 'ipsec_ipv6_natt_esp'
    TRANSPORT_GTPC_IPV4 = 'gtpc_ipv4'
    TRANSPORT_GTPC_IPV6 = 'gtpc_ipv6'
    TRANSPORT_GTPU_IPV4 = 'gtpu_ipv4'
    TRANSPORT_GTPU_IPV6 = 'gtpu_ipv6'
    TRANSPORT_GTPU_IPV4_FRAG_IPV4 = 'gtpu_ipv4_frag_ipv4'
    TRANSPORT_GTPU_IPV4_INNER_IPV4 = 'gtpu_ipv4_inner_ipv4'
    TRANSPORT_GTPU_IPV4_UDP_INNER_IPV4 = 'gtpu_ipv4_udp_inner_ipv4'
    TRANSPORT_GTPU_IPV4_TCP_INNER_IPV4 = 'gtpu_ipv4_tcp_inner_ipv4'
    TRANSPORT_GTPU_IPV4_ICMP_INNER_IPV4 = 'gtpu_ipv4_icmp_inner_ipv4'
    TRANSPORT_GTPU_IPV4_FRAG_INNER_IPV6 = 'gtpu_ipv4_frag_inner_ipv6'
    TRANSPORT_GTPU_IPV4_INNER_IPV6 = 'gtpu_ipv4_inner_ipv6'
    TRANSPORT_GTPU_IPV4_UDP_INNER_IPV6 = 'gtpu_ipv4_udp_inner_ipv6'
    TRANSPORT_GTPU_IPV4_TCP_INNER_IPV6 = 'gtpu_ipv4_tcp_inner_ipv6'
    TRANSPORT_GTPU_IPV4_ICMP_INNER_IPV6 = 'gtpu_ipv4_icmp_inner_ipv6'
    TRANSPORT_GTPU_IPV6_FRAG_INNER_IPV4 = 'gtpu_ipv6_frag_inner_ipv4'
    TRANSPORT_GTPU_IPV6_INNER_IPV4 = 'gtpu_ipv6_inner_ipv4'
    TRANSPORT_GTPU_IPV6_UDP_INNER_IPV4 = 'gtpu_ipv6_udp_inner_ipv4'
    TRANSPORT_GTPU_IPV6_TCP_INNER_IPV4 = 'gtpu_ipv6_tcp_inner_ipv4'
    TRANSPORT_GTPU_IPV6_ICMP_INNER_IPV4 = 'gtpu_ipv6_icmp_inner_ipv4'
    TRANSPORT_GTPU_IPV6_FRAG_INNER_IPV6 = 'gtpu_ipv6_frag_inner_ipv6'

@unique
class ARPOpcode(Enum):
    """ARP请求类型"""
    ARP_QUEST = 1
    ARP_ANSWER = 2
    RARP_QUEST = 3
    RARP_ANSWER = 4


@unique
class PacketType(Enum):
    """传输的报文类型"""
    PACKET_IPV4 = 4
    PACKET_IPV6 = 6


@unique
class TestPacketType(Enum):
    """测试包的类型"""
    VLAN = 'vlan'
    VLAN_WITH_TAG = 'vlan_with_tag'
    TCP = 'tcp'
    UDP = 'udp'
    IP = 'ip'
    ICMP = 'icmp'


@unique
class FilterTypeEnum(Enum):
    """过滤类型"""
    UNICAST = 'unicast'
    MULTICAST = 'multicast'
    BROADCAST = 'broadcast'
    PROMISC = 'promisc'
    VLAN = 'vlan'


@unique
class CmdExecuteAdressEnum(Enum):
    """执行命令的地址"""
    # 在server端执行命令, 即默认端口值 22
    SERVER = 'server'
    # 在Client端执行命令，即默认端口值 22
    CLIENT = 'client'
    # 根据test entry参数指定执行cli命令的地址
    CLI_DEFAULT = 'cli_default'
    # 双主机模式下的副主机
    SUB_HOST = 'sub_host'
    SERVER_NODE = 'server_node'
    CLIENT_NODE = 'client_node'


@unique
class IpvbsCommuEnum(Enum):
    """执行命令的地址"""
    # 在server端执行命令, 即默认端口值 22
    SCREEN = 'screen'
    SOCKET = 'socket'
    SCREEN_FORCE = 'screen_force'
    SOCKET_FORCE = 'socket_force'


@unique
class TestObjectEnum(Enum):
    """测试对象"""
    RAID = 0
    HBA = 1
    EXPANDER = 2
    PCIE_SWITCH = 3


@unique
class TestObjectStrEnum(Enum):
    """测试对象"""
    RAID = 'raid'
    HBA = 'hba'
    EXPANDER = 'expander'
    PCIE_SWITCH = 'pcie_switch'


@unique
class CompileObjectEnum(Enum):
    """编译对象"""
    PS3 = 0
    SIMULATOR = 1
    DRIVER = 2
    RAID = 3
    HBA = 4
    PCIE_SWITCH = 5
    EXPANDER = 6
    PS3CLI = 7
    FRONTEND = 8
    BACKEND = 9


@unique
class OpcodeEnum(Enum):
    """操作"""
    OpCode_DEL = "del"
    Opcode_ADD = "add"


@unique
class CompileObjectStrEnum(Enum):
    """编译对象"""
    PS3 = 'ps3'
    SIMULATOR = 'simulator'
    DRIVER = 'driver'
    RAID = 'raid'
    HBA = 'hba'
    PCIE_SWITCH = 'pcie_switch'
    EXPANDER = 'expander'
    PS3CLI = 'ps3cli'
    FRONTEND = 'frontend'
    BACKEND = 'backend'


@unique
class TestPlatformEnum(Enum):
    """测试平台"""
    SIMU_PLATFORM = 'simu_platform'
    REAL_PLATFORM = 'real_platform'


@unique
class HostOsEnum(Enum):
    """操作系统"""
    WINDOWS = 'windows'
    CENTOS = 'centos'
    UBUNTU = 'ubuntu'


@unique
class ExitCodeEnum(Enum):
    """脚本退出码"""
    EXIT_NORMAL = 0
    EXIT_FAIL = 1
    EXIT_SKIP = 2
    EXIT_EXCEPT = 6
    EXIT_TIMEOUT = 124


@unique
class CaseRunPhaseEnum(Enum):
    """ 脚本运行阶段 """
    PREPARE = 'prepare'
    DO = 'do'
    POST = 'post'


@unique
class BugOwner(Enum):
    BACKEND = 'Backend'
    FRONTEND = 'Frontend'
    HIL = 'HIL'
    MGR = 'Mgr'
    HOST = "Host Driver"


@unique
class BondModeEnum(Enum):
    BALANCE_RR = 'balance-rr'
    ACTIVE_BACKUP = 'active-backup'
    BALANCE_XOR = 'balance-xor'
    BROADCAST = 'broadcast'
    AD_8023 = '802.3ad'
    BALANCE_TLB = 'balance-tlb'
    BALANCE_ALB = 'balance-alb'


@unique
class FrameType(Enum):
    Frame_SNAP = "snap"
    Frame_LLC = "llc"


@unique
class MacVlanModeEnum(Enum):
    PRIVATE = 'private'
    VEPA = 'vepa'
    BRIDGE = 'bridge'
    PASSTHRU = 'passthru'
    MACTAP = 'mactap'


@unique
class IPV6ExtensionHeaderEnum(Enum):
    """IPV6的扩展报头"""
    Header_Hop_by_Hop = 0
    Header_Destination = "IPv6ExtHdrDestOpt"
    Header_Routing = "IPv6ExtHdrRouting"
    Header_Segment_Routing_TLV_Generic = "IPv6ExtHdrSegmentRoutingTLV"
    Header_Segment_Routing_TLV_Ingress_Node = "IPv6ExtHdrSegmentRoutingTLVIngressNode"
    Header_Segment_Routing_TLV_Egress_Node = "IPv6ExtHdrSegmentRoutingTLVEgressNode"
    Header_Segment_Routing_TLV_Pad1 = "IPv6ExtHdrSegmentRoutingTLVPad1"
    Header_Segment_Routing_TLV_PadN = "IPv6ExtHdrSegmentRoutingTLVPadN"
    Header_Segment_Routing_TLV_HMAC = "IPv6ExtHdrSegmentRoutingTLVHMAC"
    Header_Segment_Routing = "IPv6ExtHdrSegmentRouting"
    Header_Fragment = "IPv6ExtHdrFragment"


@unique
class TestObjectType(Enum):
    PF = 'pf'
    VF = 'vf'
    VLAN = 'pfvlan'
    DVLAN = 'pfdoublevlan'
    MACVLAN = 'pfmacvlan'
    TUNNEL = 'pftunnel'
    VFVLAN = 'vfvlan'
    VFDVLAN = 'vfdoublevlan'
    VFMACVLAN = 'vfmacvlan'
    VFTUNNEL = 'vftunnel'
    VFVMQ = 'vfvmq'
    VFVMQVLAN = 'vfvmqvlan'
    DEGVMQ = 'vfdegvmq'
    DUAL_VF = 'dual_vf'
    # 仅仅只有vf场景
    DVVF = 'dpdk_vfio_pci_vf'
    DIVF = 'dpdk_igb_uio_vf'
    BOND1 = 'bond1'
    BOND2 = 'bond2'
    BOND4 = 'bond4'


@unique
class NicNameEnum(Enum):
    INTEL_82599 = 'ixgbe'
    SXE = 'sxe'
    SXEVF = 'sxevf'
    E810 = 'ice'
    CX6 = 'mlx5_core'
    SCGBE = 'scgbe'
    SCGBEVF = 'scgbevf'
    SCGBE_RDMA = 'scgbe_rdma'
    SXE2 = 'sxe2'
    SXE2VF = 'sxe2vf'
    SXE2_RDMA = 'sxe2rdma'
    IRDMA = 'irdma'
    MLX5_IB = 'mlx5_ib'
    SCE = 'sce'
    SCEVF = 'savf'
    SCE_RDMA = 'srdma'
    Testca = 'Testca_ib'
    RENIX = 'renix'


@unique
class TestPmdForwadModeEnum(Enum):
    IO = 'io'
    RXONLY = 'rxonly'
    TXONLY = 'txonly'
    ICMPECHO = 'icmpecho'


@unique
class RegionEnum(Enum):
    UBOOT = 'uboot'
    FW = 'fw_master'
    NVDATA = 'nvdata'
    USER_DEFAULT = 'userdefault'
    OPTION_ROM = 'optionrom'
    FW_BAK = 'fw_slave'


@unique
class RegionNumEnum(Enum):
    UBOOT = 0
    UBOOT_BAK = 1
    OPTION_ROM = 2
    OPTION_ROM_BAK = 3
    FW = 10
    FW_BAK = 11
    NVDATA = 12
    NVDATA_BAK = 13
    USER_DEFAULT = 28
    USER_DEFAULT_BAK = 29
    SBR = 40
    SBR_BAK = 49


@unique
class UpgradeTypeEnum(Enum):
    UPGRADE = 'upgrade'
    DEGRADE = 'degrade'
    SAME_VERSION = 'same_version'


@unique
# checksumoffload的属性值
class ChecksumOffloadStatusEnum(Enum):
    # 去使能txrx
    DISABLE = "disable"
    # 只使能tx
    TXENABLE = "txenable"
    # 只使能rx
    RXENABLE = "rxenable"
    # txrx均使能
    TXRXENABLE = "txrxenable"


@unique
class FCRegisterEnum(Enum):
    DISABLE = "0"
    TX_ENABLE = "1"
    RX_ENABLE = "2"
    ALL_ENABLE = "3"


@unique
class BoolEnum(Enum):
    TRUE = "$True"
    FALSE = "$False"


@unique
class PolicyEnum(Enum):
    GLOBAL = "Global"
    Ada_Specific = "AdapterSpecific"


@unique
# profile选项配置
class RssProfileEnum(Enum):
    CLOSEST = "Closest"
    # 没有动态负载平衡
    CLOSESTSTATIC = "ClosestStatic"
    # 非均衡存储器访问
    NUMA = "NUMA"
    # 默认的行为。RSS处理器的选择与没有动态负载平衡的NUMA可伸缩性相同
    NUMASTATIC = "NUMAStatic"
    # RSS使用尽可能少的处理器来维持负载。这个选项有助于减少中断的数量
    CONSERVATIVE = "Conservative"


@unique
class RssLoadBalancingProfile(Enum):
    CLOSESTPROCESSOR = "ClosestProcessor"
    CLOSESTPROCESSORSTATIC = "ClosestProcessorStatic"
    NUMASCALING = "NUMAScaling"
    NUMASCALINGSTATIC = "NUMAScalingStatic"


@unique
# windows的mtu值设定，有效值为1514， 4088， 9014
class MTuSizeEnum(Enum):
    # 设置为disbled，mtu值为1514
    DISABLE = "Disabled"
    # 支持的最大mtu值为9014
    MAX_MTU = "9014 Bytes"
    # 通用设置为4088
    MIDDLE_MTU = "4088 Bytes"


@unique
class ShowMTUSizeEnum(Enum):
    DISABLE = "1500"
    MIDDLE_MTU = "4074"
    MAX_MTU = "9000"


@unique
# 指定设备间交换pdu (protocol data unit)或控制消息的频率。
class LacpTimerEnum(Enum):
    LACP_SLOW = "slow"
    LACP_FAST = "fast"


@unique
# 在对tc队列添加规则时，需填入的算法类型
class AlgorithmEnum(Enum):
    ETS = "ETS"
    STRICT = "Strict"


@unique
# 在接口之间分配网络流量的负载平衡算法
class BlanceAlgorithm(Enum):
    # 使用TCP源端口号、目的端口号和IP地址对出方向的流量进行hash处理。
    DYNAMIC = "Dynamic"
    # 使用源端和目的端的TCP端口和IP地址 创建哈希
    TRANSPORTPORTS = "TransportPorts"
    # 使用源和目的IP地址创建一个哈希
    IPADDRESSES = "IPAddresses"
    # 使用源和目的MAC地址创建哈希
    MACADDRESSES = "MacAddresses"
    # 根据源虚拟机hyper - v交换机端口标识分配网络流量
    HYPERVPORT = "HyperVPort"


@unique
# 指定网卡组的模式
class TeamingModeEnum(Enum):
    # 需要对交换机和主机都进行配置来识别其中的哪个链接形成团队。采用链路聚合控制协议(Lacp)识别主机和给定交换机之间连接的链路
    LACP = "LACP"
    # 需要在交换机和主机上进行配置
    STATIC = "Static"
    # 指定网卡组不需要配置网络交换机
    SWITCHINDEPEDENT = "SwitchIndependent"


@unique
class AdministrativeMode(Enum):
    # 允许团队成员加入NIC团队
    ACTIVE = "Active"
    STATNDBY = "Standby"


@unique
class SpeedEnum(Enum):
    SPEED_100M = 100
    SPEED_1G = 1000
    SPEED_10G = 10000
    SPEED_25G = 25000
    SPEED_40G = 40000
    SPEED_50G = 50000
    SPEED_100G = 100000
    SPEED_UNKNOW = 0


class FecEnum(Enum):
    AUTO = 'auto'
    OFF = 'off'
    RS528 = 'rs528'
    RS544 = 'rs544'
    BASER = 'baser'
    BASER_SHOW = 'BaseR'
    RS = 'rs'

class FlmFecEnum(Enum):
    # 无 FEC
    FLM_FEC_OFF = 0
    # BaseFEC
    FLM_FEC_BASER = 1
    # RS(528, 514)
    FLM_FEC_RS528 = 2
    # RS(544, 514)
    FLM_FEC_RS544 = 3
    # FEC 自动配置
    FLM_FEC_AUTO = 15

class FecEncodingEnum(Enum):
    AUTO = 'Auto'
    BASER= 'BaseR'
    OFF = 'Off'
    RS = 'RS'


@unique
class FcEnum(Enum):
    TX = 'tx'
    RX = 'rx'
    ON = 'on'
    OFF = 'off'
    ALL = 'all'


@unique
class QueueEnum(Enum):
    # 队列分配中测试对象是PF
    DISTRIBUTE_PF = "pf"
    # 队列分配中测试对象是VF
    DISTRIBUTE_VF = "VF"
    # 队列分配中测试对象是VMQ
    DISTRIBUTE_VMQ = "VMQ"


@unique
class VirtualModeEnum(Enum):
    # 虚机中的网络适配器为SR-IOV模式
    SR_IOV = "SR_IOV"
    # 虚机中的网络适配器为VMQ模式
    VMQ = "vmq"
    # 虚机中的网络适配器为DEGVMQ模式
    DEGVMQ = "degvmq"


@unique
class RunModeEnum(Enum):
    # "nic"
    RUN_MODE_WITH_KO = 10
    # "nic_with_src"
    RUN_MODE_WITH_SRC = 11
    # "nic_with_rpm"
    RUN_MODE_WITH_RPM = 12
    # "nic_with_background_traffic"
    RUN_MODE_WITH_BG_TRAFFIC = 13
    # "nic_with_src_ko"
    RUN_MODE_WITH_SRC_KO = 14
    # "nic_with_srpm"
    RUN_MODE_WITH_SRPM = 15
    # "nic_with_kmod_srpm"
    RUN_MODE_WITH_KMOD_SRPM = 16


class EthtoolParamShortenEnum(Enum):
    CHANGE = '-s'
    DRIVER = '-i'
    SHOW_PAUSE = 'a'
    STATISTICS = '-S'


class IpvbsStatusEnum(Enum):
    SUCCESS = 'success'
    FAILURE = 'failure'
    ERROR = 'error'


@unique
class PtpNetworkTransportEnum(Enum):
    ETHER = 2
    UDP_IPV4 = 4
    UDP_IPV6 = 6

@unique
class GptpNetworkTransportEnum(Enum):
    GPTP_FILE_ETHER = 'L2'
    GPTP_FILE_UDP_IPV4 = 'UDPv4'
    GPTP_FILE_UDP_IPV6 = 'UDPv6'

class PtpTimeStampModeEnum(Enum):
    HARDWARE = 'H'
    SOFTWARE = 'S'
    LEGACY_HW = 'L'


@unique
class FPGABitVer(Enum):
    VERSION_UNKNOW = 0
    # 单核minisoc+主业务测试版本
    VERSION_A = 10
    # 单核minisoc+单port PCS测试
    VERSION_B = 11
    # ROCE+多核minisoc
    VERSION_C = 12
    # 外设+多核minisoc
    VERSION_D = 13
    # 单核minisoc+ACL测试
    VERSION_E = 14
    # 单核minisoc+MAC SEC测试
    VERSION_F = 15
    # 单核minisoc+PCS环回测试
    VERSION_G = 16
    # 单核minisoc+IPSEC功能验证版本
    VERSION_H = 17
    # 备用
    VERSION_I = 18
    # 单核minisoc+7layer_tx_sched功能验证版本
    VERSION_J = 19


@unique
class FpgaBitfileClass(Enum):
    UNKNOW = '00'
    A = '0a'
    B = '0b'
    C = '0c'
    D = '0d'
    E = '0e'
    F = '0f'
    G = '10'
    H = '11'
    I = '12'
    J = '13'
    K = '14'
    L = '15'
    M = '16'
    N = '17'
    O = '18'
    Q = '20'


@unique
class ChipIdentification(Enum):
    ASIC = 'a'
    EMU = 'e'
    FPGA = 'f'
    NULL = '0'


@unique
class SRQCLASS(Enum):
    SRQ = 'srq'
    SRQEX = 'srq_ex'


@unique
class QPCLASS(Enum):
    QP = 'qp'
    QPEX = 'qp_ex'


@unique
class MemAllocClass(Enum):
    MR = 'mr'
    BUF = 'buf'


@unique
class QPTYPE(Enum):
    IBV_QPT_RC = 2
    IBV_QPT_UC = 3
    IBV_QPT_UD = 4
    IBV_QPT_RAW_PACKET = 8
    IBV_QPT_XRC_SEND = 9
    IBV_QPT_XRC_RECV = 10
    IBV_QPT_DRIVER = 0xff


@unique
class PDTYPE(Enum):
    # 标准PD
    PROTECT_DOMAIN = 0
    # thread domian
    THREAD_DOMAIN = 1
    # parent domain
    PARENT_DOMAIN = 2


@unique
class QPSTATE(Enum):
    IBV_QPS_RESET = 0
    IBV_QPS_INIT = 1
    IBV_QPS_RTR = 2
    IBV_QPS_RTS = 3
    IBV_QPS_SQD = 4
    IBV_QPS_SQE = 5
    IBV_QPS_ERR = 6
    IBV_QPS_UNKNOWN = 7


@unique
class Scgbe_Access(Enum):
    LOCAL_READ = 0x01
    LOCAL_WRITE = 0x02
    REMOTE_READ = 0x04
    REMOTE_WRITE = 0x08
    BIND_WINDOW = 0x10
    ZERO_BASED = 0x20


@unique
class MwType(Enum):
    IBV_MW_TYPE_1 = 1
    IBV_MW_TYPE_2 = 2


@unique
class ibv_mtu(Enum):
    IBV_MTU_256 = 1
    IBV_MTU_512 = 2
    IBV_MTU_1024 = 3
    IBV_MTU_2048 = 4
    IBV_MTU_4096 = 5


@unique
class ibv_send_flags(Enum):
    IBV_SEND_FENCE = 1 << 0  # 1
    IBV_SEND_SIGNALED = 1 << 1  # 2
    IBV_SEND_SOLICITED = 1 << 2  # 4
    IBV_SEND_INLINE = 1 << 3  # 8
    IBV_SEND_IP_CSUM = 1 << 4  # 16


@unique
class ibv_rereg_mr_flags(Enum):
    IBV_REREG_MR_CHANGE_TRANSLATION = 1
    IBV_REREG_MR_CHANGE_PD = 2
    IBV_REREG_MR_CHANGE_ACCESS = 4


@unique
class ibv_wr_opcode(Enum):
    IBV_WR_RDMA_WRITE = 0
    IBV_WR_RDMA_WRITE_WITH_IMM = 1
    IBV_WR_SEND = 2
    IBV_WR_SEND_WITH_IMM = 3
    IBV_WR_RDMA_READ = 4
    IBV_WR_ATOMIC_CMP_AND_SWP = 5
    IBV_WR_ATOMIC_FETCH_AND_ADD = 6
    IBV_WR_LOCAL_INV = 7
    IBV_WR_BIND_MW = 8
    IBV_WR_SEND_WITH_INV = 9
    IBV_WR_TSO = 10
    IBV_WR_DRIVER1 = 11
    IBV_WR_FLUSH = 14
    IBV_WR_ATOMIC_WRITE = 15


@unique
class ibv_access_flags(Enum):
    IBV_ACCESS_LOCAL_WRITE = 1
    IBV_ACCESS_REMOTE_WRITE = (1 << 1)
    IBV_ACCESS_REMOTE_READ = (1 << 2)
    IBV_ACCESS_REMOTE_ATOMIC = (1 << 3)
    IBV_ACCESS_MW_BIND = (1 << 4)
    IBV_ACCESS_ZERO_BASED = (1 << 5)
    IBV_ACCESS_ON_DEMAND = (1 << 6)
    IBV_ACCESS_HUGETLB = (1 << 7)
    IBV_ACCESS_RELAXED_ORDERING = (1 << 20)


@unique
class ibv_hardwire_access_flags(Enum):
    IBV_HARDWARE_ACCESS_LOCAL_READ = 1
    IBV_HARDWARE_ACCESS_LOCAL_WRITE = (1 << 1)
    IBV_HARDWARE_ACCESS_REMOTE_READ = (1 << 2)
    IBV_HARDWARE_ACCESS_REMOTE_WRITE = (1 << 3)
    IBV_HARDWARE_ACCESS_MW_BIND = (1 << 4)
    IBV_HARDWARE_ACCESS_ZERO_BASED = (1 << 5)



@unique
class ibv_mig_state(Enum):
    IBV_MIG_MIGRATED = 0
    IBV_MIG_REARM = 1
    IBV_MIG_ARMED = 2


@unique
class ibv_qp_create_send_ops_flags(Enum):
    IBV_QP_EX_WITH_RDMA_WRITE = 1 << 0
    IBV_QP_EX_WITH_RDMA_WRITE_WITH_IMM = 1 << 1
    IBV_QP_EX_WITH_SEND = 1 << 2
    IBV_QP_EX_WITH_SEND_WITH_IMM = 1 << 3
    IBV_QP_EX_WITH_RDMA_READ = 1 << 4
    IBV_QP_EX_WITH_ATOMIC_CMP_AND_SWP = 1 << 5  # 不支持ATOMIC
    IBV_QP_EX_WITH_ATOMIC_FETCH_AND_ADD = 1 << 6  # 不支持ATOMIC
    IBV_QP_EX_WITH_LOCAL_INV = 1 << 7
    IBV_QP_EX_WITH_BIND_MW = 1 << 8
    IBV_QP_EX_WITH_SEND_WITH_INV = 1 << 9
    IBV_QP_EX_WITH_TSO = 1 << 10
    IBV_QP_EX_WITH_ATOMIC_WRITE = 1 << 12  # 不支持ATOMIC


@unique
class ibv_qp_create_flags(Enum):
    # 组播时，防止收到自己给自己发送的数据
    IBV_QP_CREATE_BLOCK_SELF_MCAST_LB = 1
    # 一个分散帧校验序列的功能标志，主要用于RoCE（RDMA over Converged Ethernet）协议中，其作用是允许在接收数据时，将以太网帧的 FCS
    # （Frame Check Sequence）单独存放在分散的内存位置，而不是与数据主体连续存放。
    IBV_QP_CREATE_SCATTER_FCS = 2
    # 一个CVLAN 标签剥离功能标志，主要作用是在接收数据包时，硬件自动剥离 CVLAN（Customer VLAN）标签，只将有效载荷数据传递给应用程序，
    # 避免软件解析和剥离的开销，应用直接收到干净的以太网帧
    IBV_QP_CREATE_CVLAN_STRIPPING = 3
    # 一个指定源 QP 编号的功能标志，主要作用是允许应用程序在创建 QP 时显式指定 QP 编号（QPN），而不是由驱动程序自动分配
    IBV_QP_CREATE_SOURCE_QPN = 4
    # 一个PCI 写结束填充功能，其作用是在 PCIe 写操作末尾添加填充，确保 DMA 写入对齐到缓存行边界，从而提高 PCIe 总线的传输效率
    IBV_QP_CREATE_PCI_WRITE_END_PADDING = 5


@unique
class ibv_qp_init_attr_mask(Enum):
    IBV_QP_INIT_ATTR_PD = 1 << 0
    IBV_QP_INIT_ATTR_XRCD = 1 << 1
    IBV_QP_INIT_ATTR_CREATE_FLAGS = 1 << 2
    IBV_QP_INIT_ATTR_MAX_TSO_HEADER = 1 << 3
    IBV_QP_INIT_ATTR_IND_TABLE = 1 << 4
    IBV_QP_INIT_ATTR_RX_HASH = 1 << 5
    IBV_QP_INIT_ATTR_SEND_OPS_FLAGS = 1 << 6


@unique
class ibv_qp_attr_mask(Enum):
    IBV_QP_STATE = 1 << 0
    IBV_QP_CUR_STATE = 1 << 1
    IBV_QP_EN_SQD_ASYNC_NOTIFY = 1 << 2
    IBV_QP_ACCESS_FLAGS = 1 << 3
    IBV_QP_PKEY_INDEX = 1 << 4
    IBV_QP_PORT = 1 << 5
    IBV_QP_QKEY = 1 << 6
    IBV_QP_AV = 1 << 7
    IBV_QP_PATH_MTU = 1 << 8
    IBV_QP_TIMEOUT = 1 << 9
    IBV_QP_RETRY_CNT = 1 << 10
    IBV_QP_RNR_RETRY = 1 << 11
    IBV_QP_RQ_PSN = 1 << 12
    IBV_QP_MAX_QP_RD_ATOMIC = 1 << 13  # 不支持ATOMIC
    IBV_QP_ALT_PATH = 1 << 14
    IBV_QP_MIN_RNR_TIMER = 1 << 15
    IBV_QP_SQ_PSN = 1 << 16
    IBV_QP_MAX_DEST_RD_ATOMIC = 1 << 17  # 不支持ATOMIC
    IBV_QP_PATH_MIG_STATE = 1 << 18
    IBV_QP_CAP = 1 << 19
    IBV_QP_DEST_QPN = 1 << 20
    IBV_QP_RATE_LIMIT = 1 << 25


@unique
class ib_mr_type(Enum):
    IB_MR_TYPE_MEM_REG = 0
    IB_MR_TYPE_SG_GAPS = 1
    IB_MR_TYPE_DM = 2
    IB_MR_TYPE_USER = 3
    IB_MR_TYPE_DMA = 4
    IB_MR_TYPE_INTEGRITY = 5


@unique
class ib_sig_type(Enum):
    IB_SIGNAL_ALL_WR = 0
    IB_SIGNAL_REQ_WR = 1


@unique
class qp_attr_param(Enum):
    QP_STATE = 'qp_state'
    CUR_QP_STATE = 'cur_qp_state'
    PATH_MTU = 'path_mtu'
    PATH_MIG_STATE = 'path_mig_state'
    QKEY = 'qkey'
    RQ_PSN = 'rq_psn'
    SQ_PSN = 'sq_psn'
    DEST_QP_QPN = 'dest_qp_num'
    QP_ACCESS_FLAGS = 'qp_access_flags'
    CAP = 'cap'
    AH_ATTR = 'ah_attr'
    ALT_AH_ATTR = 'alt_ah_attr'
    PKEY_INDEX = 'pkey_index'
    ALT_PKEY_INDEX = 'alt_pkey_index'
    EN_SQD_ASYNC_NOTIFY = 'en_sqd_async_notify'
    SQ_DRAINING = 'sq_draining'
    MIN_RNR_TIMER = 'min_rnr_timer'
    PORT_NUM = 'port_num'
    TIMEOUT = 'timeout'
    RETRY_CNT = 'retry_cnt'
    RNR_RETRY = 'rnr_retry'
    ALT_PORT_NUM = 'alt_port_num'
    ALT_TIMEOUT = 'alt_timeout'
    RATE_LIMIT = 'rate_limit'
    MAX_RD_ATOMIC = 'max_rd_atomic'  # RC_to_rts: mlx5必选参数
    MAX_DEST_RD_ATOMIC = 'max_dest_rd_atomic'  # RC_to_rts: mlx5必选参数


@unique
class qp_attr_mask_to_qp_attr_param(Enum):
    IBV_QP_STATE = qp_attr_param.QP_STATE.value
    IBV_QP_CUR_STATE = qp_attr_param.CUR_QP_STATE.value
    IBV_QP_EN_SQD_ASYNC_NOTIFY = qp_attr_param.EN_SQD_ASYNC_NOTIFY.value
    IBV_QP_ACCESS_FLAGS = qp_attr_param.QP_ACCESS_FLAGS.value
    IBV_QP_PKEY_INDEX = qp_attr_param.PKEY_INDEX.value
    IBV_QP_PORT = qp_attr_param.PORT_NUM.value
    IBV_QP_QKEY = qp_attr_param.QKEY.value
    IBV_QP_AV = qp_attr_param.AH_ATTR.value
    IBV_QP_PATH_MTU = qp_attr_param.PATH_MTU.value
    IBV_QP_TIMEOUT = qp_attr_param.TIMEOUT.value
    IBV_QP_RETRY_CNT = qp_attr_param.RETRY_CNT.value
    IBV_QP_RNR_RETRY = qp_attr_param.RNR_RETRY.value
    IBV_QP_RQ_PSN = qp_attr_param.RQ_PSN.value
    IBV_QP_MAX_QP_RD_ATOMIC = qp_attr_param.MAX_RD_ATOMIC.value  # 不支持ATOMIC
    IBV_QP_ALT_PATH = ''
    IBV_QP_MIN_RNR_TIMER = qp_attr_param.MIN_RNR_TIMER.value
    IBV_QP_SQ_PSN = qp_attr_param.SQ_PSN.value
    IBV_QP_MAX_DEST_RD_ATOMIC = qp_attr_param.MAX_DEST_RD_ATOMIC.value  # 不支持ATOMIC
    IBV_QP_PATH_MIG_STATE = qp_attr_param.PATH_MIG_STATE.value
    IBV_QP_CAP = qp_attr_param.CAP.value
    IBV_QP_DEST_QPN = qp_attr_param.DEST_QP_QPN.value
    IBV_QP_RATE_LIMIT = qp_attr_param.RATE_LIMIT.value


@unique
class NodeType(Enum):
    LEAF_NODE = 'leaf'
    NONLEAF_NODE = 'nonleaf'


@unique
class ibv_wc_flags_ex(Enum):
    IBV_WC_EX_WITH_BYTE_LEN = 1 << 0
    IBV_WC_EX_WITH_IMM = 1 << 1
    IBV_WC_EX_WITH_QP_NUM = 1 << 2
    IBV_WC_EX_WITH_SRC_QP = 1 << 3
    IBV_WC_EX_WITH_SLID = 1 << 4
    IBV_WC_EX_WITH_SL = 1 << 5
    IBV_WC_EX_WITH_DLID_PATH_BITS = 1 << 6
    IBV_WC_EX_WITH_COMPLETION_TIMESTAMP = 1 << 7
    IBV_WC_EX_WITH_CVLAN = 1 << 8
    IBV_WC_EX_WITH_FLOW_TAG = 1 << 9
    IBV_WC_EX_WITH_COMPLETION_TIMESTAMP_WALLCLOCK = 1 << 11
    IBV_WC_EX_WITH_ALL = 2303


@unique
class return_wc_flags(Enum):
    GRH = 1
    WITH_IMMEDIATE = 2
    WITH_INVALIDATE = 8


@unique
class CqeOpcode(Enum):
    SEND = 0
    RDMA_WRITE = 1
    RDMA_READ = 2
    BIND_MW = 5
    LOCAL_INVALIDATE = 6
    RECEIVE = 128
    RECEIVE_RDMA_WITH_IMMEDIATE = 129


@unique
class CreateCqFunc(Enum):
    CQ = 0
    CQ_EX = 1
    MIX_CQ_CQEX = 2


@unique
class GidTestMode(Enum):
    IPV4 = 'ipv4'
    IPV6 = 'ipv6'
    IPV4_VLAN = 'ipv4_vlan'
    IPV6_VLAN = 'ipv6_vlan'
    IPV4_DVLAN = 'ipv4_dvlan'
    IPV6_DVLAN = 'ipv6_dvlan'
    VF_PORT_VLAN = 'vf_port_vlan'
    IPV4_MULTI = 'ipv4_multi'
    IPV6_MULTI = 'ipv6_multi'


@unique
class AECodeEvent(Enum):
    SCGBE_AE_AMP_UNALLOCATED_STAG = "SXE2_AE_AMP_UNALLOCATED_STAG"
    SCGBE_AE_AMP_INVALID_STAG = "SXE2_AE_AMP_INVALID_STAG"
    SCGBE_AE_AMP_BAD_QP = "SXE2_AE_AMP_BAD_QP"
    SCGBE_AE_AMP_BAD_PD = "SXE2_AE_AMP_BAD_PD"
    SCGBE_AE_AMP_BAD_STAG_KEY = "SXE2_AE_AMP_BAD_STAG_KEY"
    SCGBE_AE_AMP_BAD_STAG_INDEX = "SXE2_AE_AMP_BAD_STAG_INDEX"
    SCGBE_AE_AMP_BOUNDS_VIOLATION = "SXE2_AE_AMP_BOUNDS_VIOLATION"
    SCGBE_AE_AMP_RIGHTS_VIOLATION = "SXE2_AE_AMP_RIGHTS_VIOLATION"
    SCGBE_AE_AMP_FASTREG_VALID_STAG = "SXE2_AE_AMP_FASTREG_VALID_STAG"
    SCGBE_AE_AMP_FASTREG_MW_STAG = "SXE2_AE_AMP_FASTREG_MW_STAG"
    SCGBE_AE_AMP_FASTREG_INVALID_RIGHTS = "SXE2_AE_AMP_FASTREG_INVALID_RIGHTS"
    SCGBE_AE_AMP_FASTREG_INVALID_LENGTH = "SXE2_AE_AMP_FASTREG_INVALID_LENGTH"
    SCGBE_AE_AMP_INVALIDATE_NO_REMOTE_ACCESS_RIGHTS = "SXE2_AE_AMP_INVALIDATE_NO_REMOTE_ACCESS_RIGHTS"
    SCGBE_AE_AMP_INVALIDATE_MR_WITH_BOUND_WINDOWS = "SXE2_AE_AMP_INVALIDATE_MR_WITH_BOUND_WINDOWS"
    SCGBE_AE_AMP_MWBIND_VALID_STAG = "SXE2_AE_AMP_MWBIND_VALID_STAG"
    SCGBE_AE_AMP_MWBIND_OF_MR_STAG = "SXE2_AE_AMP_MWBIND_OF_MR_STAG"
    SCGBE_AE_AMP_MWBIND_TO_ZERO_BASED_STAG = "SXE2_AE_AMP_MWBIND_TO_ZERO_BASED_STAG"
    SCGBE_AE_AMP_MWBIND_TO_MW_STAG = "SXE2_AE_AMP_MWBIND_TO_MW_STAG"
    SCGBE_AE_AMP_MWBIND_INVALID_RIGHTS = "SXE2_AE_AMP_MWBIND_INVALID_RIGHTS"
    SCGBE_AE_AMP_MWBIND_INVALID_BOUNDS = "SXE2_AE_AMP_MWBIND_INVALID_BOUNDS"
    SCGBE_AE_AMP_MWBIND_TO_INVALID_PARENT = "SXE2_AE_AMP_MWBIND_TO_INVALID_PARENT"
    SCGBE_AE_AMP_MWBIND_BIND_DISABLED = "SXE2_AE_AMP_MWBIND_BIND_DISABLED"
    SCGBE_AE_AMP_INVALIDATE_TYPE1_MW = "SXE2_AE_AMP_INVALIDATE_TYPE1_MW"
    SCGBE_AE_AMP_MWBIND_ZERO_BASED_TYPE1_MW = "SXE2_AE_AMP_MWBIND_ZERO_BASED_TYPE1_MW"
    SCGBE_AE_AMP_MWBIND_WRONG_TYPE = "SXE2_AE_AMP_MWBIND_WRONG_TYPE"
    SCGBE_AE_AMP_FASTREG_PBLE_MISMATCH = "SXE2_AE_AMP_FASTREG_PBLE_MISMATCH"
    SCGBE_AE_CQ_OPERATION_ERROR = "SXE2_AE_CQ_OPERATION_ERROR"
    SCGBE_AE_IB_RREQ_AND_Q1_FULL = "SXE2_AE_IB_RREQ_AND_Q1_FULL"
    SCGBE_AE_IB_INVALID_REQUEST = "SXE2_AE_IB_INVALID_REQUEST"
    SCGBE_AE_WQE_UNEXPECTED_OPCODE = "SXE2_AE_WQE_UNEXPECTED_OPCODE"
    SCGBE_AE_IB_REMOTE_ACCESS_ERROR = "SXE2_AE_IB_REMOTE_ACCESS_ERROR"
    SCGBE_AE_IB_REMOTE_OP_ERROR = "SXE2_AE_IB_REMOTE_OP_ERROR"
    SCGBE_AE_ROCE_RSP_LENGTH_ERROR = "SXE2_AE_ROCE_RSP_LENGTH_ERROR"
    SCGBE_AE_LLP_TOO_MANY_RETRIES = "SXE2_AE_LLP_TOO_MANY_RETRIES"
    SCGBE_AE_QP_SUSPEND_COMPLETE = "SXE2_AE_QP_SUSPEND_COMPLETE"
    SCGBE_AE_LLWQE_ERR = "SXE2_AE_LLWQE_ERR"
    SCGBE_AE_DOORBELL_ERR = "SXE2_AE_DOORBELL_ERR"
    SCGBE_AE_LLWQE_8B_INVALID = "SXE2_AE_LLWQE_8B_INVALID"
    SCGBE_AE_DOORBELL_QSET_ERR = "SXE2_AE_DOORBELL_QSET_ERR"
    SCGBE_AE_DOORBELL_QPN_ERR = "SXE2_AE_DOORBELL_QPN_ERR"
    SCGBE_AE_DOORBELL_EQN_ERR = "SXE2_AE_DOORBELL_EQN_ERR"
    SCGBE_AE_DOORBELL_CQN_ERR = "SXE2_AE_DOORBELL_CQN_ERR"
    SCGBE_AE_DOORBELL_QPN_NUM_ERR = "SXE2_AE_DOORBELL_QPN_NUM_ERR"
    SCGBE_AE_WQE_LOAD_QPC_PBL_ERR = "SXE2_AE_WQE_LOAD_QPC_PBL_ERR"
    SCGBE_AE_WQE_LOAD_QPC_DMA_ERR = "SXE2_AE_WQE_LOAD_QPC_DMA_ERR"
    SCGBE_AE_WQE_LOAD_QPC_ECC_ERR = "SXE2_AE_WQE_LOAD_QPC_ECC_ERR"
    SCGBE_AE_WQE_QPC_CFG_ERR = "SXE2_AE_WQE_QPC_CFG_ERR"
    SCGBE_AE_WQE_RD_DMA_ERR = "SXE2_AE_WQE_RD_DMA_ERR"
    SCGBE_AE_WQE_CFG_ERR = "SXE2_AE_WQE_CFG_ERR"
    SCGBE_AE_WQE_OPCODE_ERR = "SXE2_AE_WQE_OPCODE_ERR"
    SCGBE_AE_WQE_LENGTH_ERR = "SXE2_AE_WQE_LENGTH_ERR"
    SCGBE_AE_WQE_LLWQE_ERR = "SXE2_AE_WQE_LLWQE_ERR"
    SCGBE_AE_WQE_RD_RESP_DMA_ERR = "SXE2_AE_WQE_RD_RESP_DMA_ERR"
    SCGBE_AE_WQE_RD_AH_ERR = "SXE2_AE_WQE_RD_AH_ERR"
    SCGBE_AE_WQE_AH_CFG_ERR = "SXE2_AE_WQE_AH_CFG_ERR"
    SCGBE_AE_WQE_SGE_ERR = "SXE2_AE_WQE_SGE_ERR"
    SCGBE_AE_RXT_OPCODE_ERR = "SXE2_AE_RXENG_RXT_OPCODE_ERR"
    SCGBE_AE_RXT_LENGTH_ERR = "SXE2_AE_RXENG_RXT_LENGTH_ERR"
    SCGBE_AE_RXT_RDMA_READ_OUTSTANDING_ERR = "SXE2_AE_RXT_RDMA_READ_OUTSTANDING_ERR"
    SCGBE_AE_RXI_BAD_RESPONSE = "SXE2_AE_RXI_BAD_RESPONSE"
    SCGBE_AE_RXI_LENGTH_ERR = "SXE2_AE_RXI_LENGTH_ERR"
    SCGBE_AE_RXI_IRRL_DMA_ERR = "SXE2_AE_RXI_IRRL_DMA_ERR"
    SCGBE_AE_RXT_RESP_WR_PADDR_ERR = "SXE2_AE_RXT_RESP_WR_PADDR_ERR"
    SCGBE_AE_RXT_RESP_RD_DMA_ERR = "SXE2_AE_RXT_RESP_RD_DMA_ERR"
    SCGBE_AE_RXI_SSNT_OVERSIZE_ERR = "SXE2_AE_RXI_SSNT_OVERSIZE_ERR"
    SCGBE_AE_RXI_SSNT_DMA_ERR = "SXE2_AE_RXI_SSNT_DMA_ERR"
    SCGBE_AE_RXT_RQE_LIMIT = "SXE2_AE_RXT_RQE_LIMIT"
    SCGBE_AE_RX_LOAD_QPC_DMA_ERR = "SXE2_AE_RX_LOAD_QPC_DMA_ERR"
    SCGBE_AE_RX_LOAD_QPC_PA_ERR = "SXE2_AE_RX_LOAD_QPC_PA_ERR"
    SCGBE_AE_RX_LOAD_SRQC_DMA_ERR = "SXE2_AE_RX_LOAD_SRQC_DMA_ERR"
    SCGBE_AE_RX_LOAD_SRQC_PA_ERR = "SXE2_AE_RX_LOAD_SRQC_PA_ERR"
    SCGBE_AE_RQ_PI_DMA_ERR = "SXE2_AE_RQ_PI_DMA_ERR"
    SCGBE_AE_RQ_ADDR_ERR = "SXE2_AE_RQ_ADDR_ERR"
    SCGBE_AE_RQ_DMA_ERR = "SXE2_AE_RQ_DMA_ERR"
    SCGBE_AE_RQ_WQE_VLD_ERR = "SXE2_AE_RQ_WQE_VLD_ERR"
    SCGBE_AE_SRQC_STS_ERR = "SXE2_AE_SRQC_STS_ERR"
    SCGBE_AE_SRQC_STS_RSV = "SXE2_AE_SRQC_STS_RSV"
    SCGBE_AE_TXENG_PAYLOAD_RD_DMA_ERR = "SXE2_AE_TXENG_PAYLOAD_RD_DMA_ERR"
    SCGBE_AE_TXENG_RD_PKEY_ERR = "SXE2_AE_TXENG_RD_PKEY_ERR"
    SCGBE_AE_TXENG_RD_SSNT_PBL_ERR = "SXE2_AE_TXENG_RD_SSNT_PBL_ERR"
    SCGBE_AE_TXENG_RD_IRRL_PBL_ERR = "SXE2_AE_TXENG_RD_IRRL_PBL_ERR"
    SCGBE_AE_TXENG_DIF_CHK_ERR = "SXE2_AE_TXENG_DIF_CHK_ERR"
    SCGBE_AE_TXENG_RESP_PAYLOAD_RD_DMA_ERR = "SXE2_AE_TXENG_RESP_PAYLOAD_RD_DMA_ERR"
    SCGBE_AE_TXENG_RESP_PAYLOAD_DIF_CHK_ERR = "SXE2_AE_TXENG_RESP_PAYLOAD_DIF_CHK_ERR"
    SCGBE_AE_TMO_WR_PA_ERR = "SXE2_AE_TMO_WR_PA_ERR"
    SCGBE_AE_TMO_RD_PA_ERR = "SXE2_AE_TMO_RD_PA_ERR"
    SCGBE_AE_TMO_RD_DMA_ERR = "SXE2_AE_TMO_RD_DMA_ERR"
    SCGBE_AE_TMO_RD_QPC_ERR = "SXE2_AE_TMO_RD_QPC_ERR"
    SCGBE_AE_CC_QP_RATE = "SXE2_AE_CC_QP_RATE"
    SCGBE_AE_CEQ_OVERFLOW = "SXE2_AE_CEQ_OVERFLOW"
    SCGBE_AE_EQ_STATUS_ERR = "SXE2_AE_EQ_STATUS_ERR"
    SCGBE_AE_CQ_STATUS_ERR = "SXE2_AE_CQ_STATUS_ERR"
    SCGBE_AE_QP_CQ_OVERFLOW = "SXE2_AE_QP_CQ_OVERFLOW"
    SCGBE_AE_RXENG_REMOTE_INVALID_ERROR = "SXE2_AE_RXENG_REMOTE_INVALID_ERROR"
    SCGBE_AE_RXENG_REMOTE_ACCESS_ERROR = "SXE2_AE_RXENG_REMOTE_ACCESS_ERROR"
    SCGBE_AE_RXENG_REMOTE_QP_ERROR = "SXE2_AE_RXENG_REMOTE_QP_ERROR"
    SCGBE_AE_RXENG_SRQ_LAST_WQE = "SXE2_AE_RXENG_SRQ_LAST_WQE"
    SCGBE_AE_RXENG_RXT_RQE_LIMIT = "SXE2_AE_RXENG_RXT_RQE_LIMIT"
    SCGBE_AE_RXENG_SRQC_STS_RSV = "SXE2_AE_RXENG_SRQC_STS_RSV"


@unique
class post_wr_status(Enum):
    SUCCESS = "None"
    FAIL_RECV_ERR_12_CANOT_ALLOC_MEM = 'Failed to post recv. Errno: 12, Cannot allocate memory'
    FAIL_SEND_ERR_12_CANOT_ALLOC_MEM = 'Failed to post send. Errno: 12, Cannot allocate memory'
    FAIL_SEND_ERR_22_INV_ARG = 'Failed to post send. Errno: 22, Invalid argument'
    FAIL_RECV_ERR_22_INV_ARG = 'Failed to post recv. Errno: 22, Invalid argument'
    FAIL_CREATE_QP_ERR_22_INV_ARG = 'Failed to create QP. Errno: 22, Invalid argument'
    FAIL_CREATE_AH_ERR_61_NO_DATA_AVA = 'Failed to create AH. Errno: 61, No data available'

@unique
class create_qp_status(Enum):
    SUCCESS = "None"
    FAIL_CREATE_QP_ERR_12_CANNOT_ALLOC_MEM = 'Failed to create QP. Errno: 12, Cannot allocate memory'
    FAIL_CREATE_QP_ERR_22_INV_ARG = 'Failed to create QP. Errno: 22, Invalid argument'


@unique
class create_cq_status(Enum):
    SUCCESS = "None"
    FAIL_CREATE_CQ_ERR_12_CANNOT_ALLOC_MEM = "Failed to create a CQ. Errno: 12, Cannot allocate memory"


@unique
class create_srq_status(Enum):
    SUCCESS = "None"
    FAIL_CREATE_SRQ_ERR_12_CANNOT_ALLOC_MEM = 'Failed to create SRQ. Errno: 12, Cannot allocate memory'


@unique
class PerftestCmd(Enum):
    SEND_BW = 'send_bw'
    SEND_LAT = 'send_lat'
    READ_BW = 'read_bw'
    READ_LAT = 'read_lat'
    WRITE_BW = 'write_bw'
    WRITE_LAT = 'write_lat'


@unique
class RateLimitType(Enum):
    HW = 'HW'
    SW = 'SW'
    PP = 'PP'

@unique
class RateLimit(Enum):
    Gbps_2p5 = '2.5'
    Gbps_5 = '5'
    Gbps_10 = '10'
    Gbps_14 = '14'
    Gbps_20 = '20'
    Gbps_25 = '25'
    Gbps_30 = '30'
    Gbps_40 = '40'
    Gbps_56 = '56'
    Gbps_60 = '60'
    Gbps_80 = '80'
    Gbps_100 = '100'
    Gbps_112 = '112'
    Gbps_120 = '120'
    Gbps_168 = '168'
    Gbps_200 = '200'
    Gbps_300 = '300'


@unique
class DpdkTxSizeEnum(Enum):
    TX_SIZE_64 = 'tx_64_bytes_phy'
    TX_SIZE_65_127 = 'tx_65_to_127_bytes_phy'
    TX_SIZE_128_255 = 'tx_128_to_255_bytes_phy'
    TX_SIZE_256_511 = 'tx_256_to_511_bytes_phy'
    TX_SIZE_512_1023 = 'tx_512_to_1023_bytes_phy'
    TX_SIZE_1024_1522 = 'tx_1024_to_1522_bytes_phy'


@unique
class DpdkNcdTxSizeEnum(Enum):
    TX_SIZE_64 = 'MAC{}_tx_64_bytes_phy'
    TX_SIZE_65_127 = 'MAC{}_tx_65_to_127_bytes_phy'
    TX_SIZE_128_255 = 'MAC{}_tx_128_to_255_bytes_phy'
    TX_SIZE_256_511 = 'MAC{}_tx_256_to_511_bytes_phy'
    TX_SIZE_512_1023 = 'MAC{}_tx_512_to_1023_bytes_phy'
    TX_SIZE_1024_1522 = 'MAC{}_tx_1024_to_1522_bytes_phy'
    TX_SIZE_1523_MAX = 'MAC{}_tx_1523_to_max_bytes_phy'


@unique
class DpdkRxSizeEnum(Enum):
    RX_SIZE_64 = 'rx_64_bytes_phy'
    RX_SIZE_65_127 = 'rx_65_to_127_bytes_phy'
    RX_SIZE_128_255 = 'rx_128_to_255_bytes_phy'
    RX_SIZE_256_511 = 'rx_256_to_511_bytes_phy'
    RX_SIZE_512_1023 = 'rx_512_to_1023_bytes_phy'
    RX_SIZE_1024_1522 = 'rx_1024_to_1522_bytes_phy'
    RX_SIZE_1523_MAX = 'rx_1523_to_max_bytes_phy'


@unique
class DpdkNcdRxSizeEnum(Enum):
    RX_SIZE_64 = 'MAC{}_rx_64_bytes_phy'
    RX_SIZE_65_127 = 'MAC{}_rx_65_to_127_bytes_phy'
    RX_SIZE_128_255 = 'MAC{}_rx_128_to_255_bytes_phy'
    RX_SIZE_256_511 = 'MAC{}_rx_256_to_511_bytes_phy'
    RX_SIZE_512_1023 = 'MAC{}_rx_512_to_1023_bytes_phy'
    RX_SIZE_1024_1522 = 'MAC{}_rx_1024_to_1522_bytes_phy'
    RX_SIZE_1523_MAX = 'MAC{}_rx_1523_to_max_bytes_phy'


class L2ProtoTypeEnum(Enum):
    IPV4 = '0x0800'
    ARP = '0x0806'


@unique
class WcStatus(Enum):
    WC_SUCCESS = "success"
    WC_LOC_LEN_ERR = "local length error"
    WC_LOC_QP_OP_ERR = "local QP op error"
    WC_LOC_PROT_ERR = "local protection error"
    WC_WR_FLUSH_ERR = "WR flush error"
    WC_MW_BIND_ERR = "memory window bind error"
    WC_BAD_RESP_ERR = "bad response error"
    LOC_ACCESS_ERR = "local access error"
    WC_REM_INV_REQ_ERR = "remote invalidate request error"
    WC_REM_ACCESS_ERR = "remote access error"
    WC_REM_OP_ERR = "remote op error"
    WC_RETRY_EXC_ERR = "retry exceeded error"
    WC_GENERAL_ERR = "general error"
    WC_RNR_RETRY_EXC_ERR = "RNR retry exceeded"


@unique
class ib_wc_status(Enum):
    IB_WC_SUCCESS = 0
    IB_WC_LOC_LEN_ERR = 1
    IB_WC_LOC_QP_OP_ERR = 2
    IB_WC_LOC_EEC_OP_ERR = 3
    IB_WC_LOC_PROT_ERR = 4
    IB_WC_WR_FLUSH_ERR = 5
    IB_WC_MW_BIND_ERR = 6
    IB_WC_BAD_RESP_ERR = 7
    IB_WC_LOC_ACCESS_ERR = 8
    IB_WC_REM_INV_REQ_ERR = 9
    IB_WC_REM_ACCESS_ERR = 10
    IB_WC_REM_OP_ERR = 11
    IB_WC_RETRY_EXC_ERR = 12
    IB_WC_RNR_RETRY_EXC_ERR = 13
    IB_WC_LOC_RDD_VIOL_ERR = 14
    IB_WC_REM_INV_RD_REQ_ERR = 15
    IB_WC_REM_ABORT_ERR = 16
    IB_WC_INV_EECN_ERR = 17
    IB_WC_INV_EEC_STATE_ERR = 18
    IB_WC_FATAL_ERR = 19
    IB_WC_RESP_TIMEOUT_ERR = 20
    IB_WC_GENERAL_ERR = 21

@unique
class ibv_srq_type(Enum):
    IBV_SRQT_BASIC = 0  # 常规SRQ，用于标准的数据接收队列
    IBV_SRQT_XRC = 1  # XRC（eXtended Reliable Connection）SRQ，支持跨多个QP（Queue Pair）共享接收队列，适用于大规模并行计算场景
    IBV_SRQT_TM = 2  # 标签匹配型 SRQ（Tag Matching Shared Receive Queue），专门用于支持基于标签的消息匹配机制


@unique
class ibv_srq_attr_mask(Enum):
    IBV_SRQ_MAX_WR = 1 << 0
    IBV_SRQ_LIMIT = 1 << 1


@unique
class ibv_srq_init_attr_mask(Enum):
    IBV_SRQ_INIT_ATTR_TYPE = 1 << 0
    IBV_SRQ_INIT_ATTR_PD = 1 << 1
    IBV_SRQ_INIT_ATTR_XRCD = 1 << 2
    IBV_SRQ_INIT_ATTR_CQ = 1 << 3
    IBV_SRQ_INIT_ATTR_TM = 1 << 4
    IBV_SRQ_INIT_ATTR_RESERVED = 1 << 5


@unique
class RdmaModul(Enum):
    MR = "mr"
    PD = "pd"
    QP = "qp"
    AH = "ah"
    CQ = "cq"


@unique
class CoreResetType(Enum):
    CLI = "cli"
    HOST_ACTIVE = "host_active"
    HOST_PASSIVE = "host_passive"
    HW_CORE = "hw_core"


@unique
class FwResetType(Enum):
    Core_Reset = "0"
    PCIe_Reset = "1"
    Sys_Reset = "2"


@unique
class ResetType(Enum):
    PFR = "PFR"
    PFLR = "PFLR"
    VFR = "VFR"
    VFLR = "VFLR"
    RDMA = 'RDMA'
    CORER = "CoreR"
    SYS = 'SYS'
    PCIE = 'PCIE'
    HOT = "HOT"


@unique
class SleepTime(Enum):
    FR = 20  # PFR PFLR VFR VFLR，复位等待时间
    CORER = 60  # core reset, sys reset, pcie reset，复位等待时间
    SYS = 30  # sys reset
    CHECK_FEATURE_AFTER_CORER = 25  # code review 2025/5/21 jianghe add: core reset后15s查特性还没恢复，等20s
    CHECK_FEATURE_AFTER_FR = 16  # PFR PFLR VFR VFLR后1s查特性还没恢复，等5s
    LINK_MNG = 15
    FUNCTION_REMOVE = 1
    TIME_31S = 91  # asic测试，90s才能ping通
    TIME_5S = 5  # vf从dpdk绑定到以太，需要等几秒配置IP才能配置上
    TIME_10S = 10  # 打流10s后注故障；注mdd故障10s后触发复位
    TIME_90S = 92
    TIME_60S = 61  # pf复位后等待60s创建vf


@unique
class FlowType(Enum):
    Flow_0 = 0  # 期望流量跌0
    Flow_1 = 1  # 期望流量不跌0
    Flow_1_0_1 = 2  # 期望流量先跌0，后恢复正常

@unique
class FlowDir(Enum):
    TX = 0
    RX = 1
    TXRX = 2


@unique
class LinkSpeedEthtool(Enum):  # ethtool dev查询的速率检查
    SPEED_1G = '1000Mb/s'
    SPEED_10G = '10000Mb/s'
    SPEED_25G = '25000Mb/s'
    SPEED_50G = '50000Mb/s'
    SPEED_100G = '100000Mb/s'


@unique
class LinkDetected(Enum):
    YES = 'yes'
    NO = 'no'


@unique
class CompareType(Enum):
    More = 0  # 期望流量跌0
    Less = 1  # 期望流量不跌0
    Equal = 2  # 期望流量先跌0，后恢复正常

@unique
class IB_QP_CREATE_FLAGS(Enum):
    IB_QP_CREATE_IPOIB_UD_LSO               = 1 << 0
    IB_QP_CREATE_BLOCK_MULTICAST_LOOPBACK   = 1 << 1
    IB_QP_CREATE_CROSS_CHANNEL              = 1 << 2
    IB_QP_CREATE_MANAGED_SEND               = 1 << 3
    IB_QP_CREATE_MANAGED_RECV               = 1 << 4
    IB_QP_CREATE_NETIF_QP                   = 1 << 5
    IB_QP_CREATE_INTEGRITY_EN               = 1 << 6
    IB_QP_CREATE_NETDEV_USE                 = 1 << 7
    IB_QP_CREATE_SCATTER_FCS                = 1 << 8
    IB_QP_CREATE_CVLAN_STRIPPING            = 1 << 9
    IB_QP_CREATE_SOURCE_QPN                 = 1 << 10
    IB_QP_CREATE_PCI_WRITE_END_PADDING      = 1 << 11
    IB_QP_CREATE_RESERVED_START             = 1 << 26
    IB_QP_CREATE_RESERVED_END               = 1 << 31


class UDPTunnelPacketEnum(Enum):
    VXLAN = 'vxlan'
    VXLAN_GPE = 'vxlan-gpe'
    GENEVE = 'geneve'
    ROCEV21 = 'rocev21'
    ROCEV22 = 'rocev22'
    GTPC = 'gtpc'
    GTPU = 'gtpu'
    PFCP = 'pfcp'
    ECPRI = 'ecpri'
    MPLS = 'mpls'
    NVGRE = 'nvgre'
    L2TP = 'l2tp'
    TEREDO = 'teredo'

class UDPTunnelPortEnum(Enum):
    VXLAN = 4789
    VXLAN_GPE = 4790
    GENEVE = 6081
    ROCEV21 = 4791
    ROCEV22 = 1021
    GTPC = 2123
    GTPU = 2152
    PFCP = 8805
    ECPRI = 0
    MPLS = 6635
    NVGRE = 4754
    L2TP = 1701
    TEREDO = 3544


@unique
class FdirFlowActionTypeEnum(Enum):
    # Fnav action types
    QUEUE = 0
    DROP = 1
    PASSTHRU = 2

    RSS = 3
    MARK = 4
    COUNT = 5
    SEND_TO_KERNEL = 6
    PORT_ID = 7


@unique
class FnavStatTypeEnum(Enum):
    # 流命中统计模式, 默认统计报文数
    DEFAULT = 0
    PACKETS_NUM = 1
    BYTES_NUM = 2
    PACKETS_BYTES_NUM = 3


@unique
class FnavProgModeEnum(Enum):
    # 操作表项的方式, 默认AdminQ 生成
    ADMINQ = 0
    # 硬件学习生成
    HARD_LEARN = 1


@unique
class MDDEventEnum(Enum):
    Event_1 = 1
    Event_2 = 2
    Event_3 = 3
    Event_4 = 4
    Event_5 = 5
    Event_6 = 6
    Event_7 = 7
    Event_8 = 8
    Event_9 = 9
    Event_10 = 10
    Event_11 = 11
    Event_12 = 12
    Event_13 = 13
    Event_14 = 14
    Event_15 = 15
    Event_16 = 16
    Event_17 = 17
    Event_18 = 18
    Event_19 = 19
    Event_20 = 20
    Event_21 = 21
    Event_22 = 22
    Event_23 = 23
    Event_24 = 24
    Event_25 = 25
    Event_26 = 26
    Event_27 = 27
    Event_28 = 28
    Event_29 = 29
    Event_30 = 30
    Event_31 = 31
    Event_32 = 32
    Event_33 = 33
    Event_34 = 34
    Event_35 = 35
    Event_36 = 36


@unique
class MDDRecoveryMethodEnum(Enum):
    PFR = 'PFR'
    PFLR = 'PFLR'
    VFR = 'VFR'
    VFLR = 'VFLR'
    DRIVER = 'DRIVER'


@unique
class RDMATypeEnum(Enum):
    RDMA_UD = "UD"
    RDMA_RC = "RC"

@unique
class HugeState(Enum):
    HUGE = "HUGE"
    CLOSE = "no"
    PREFER_HUGE = "PREFER_HUGE"

@unique
class DpdkDriverStatsModeEnum(Enum):
    # 硬件统计模式
    HW = 0
    # 软件统计模式
    SW= 1


@unique
class PtypeEnum(Enum):
    # Non-Tunneled IPv4
    MAC_IPV4_UDP_PAY = 24
    MAC_IPV4_TCP_PAY = 26
    MAC_IPV4_SCTP_PAY = 27
    MAC_IPV4_ICMP_PAY = 28
    # ipv4 --> GRE/GENEVE/VXLAN
    MAC_IPV4_GRENAT_PAY = 43
    MAC_IPV4_GRENAT_IPV4FRAG_PAY = 44
    MAC_IPV4_GRENAT_IPV4_PAY = 45
    MAC_IPV4_GRENAT_IPV4_UDP_PAY = 46
    MAC_IPV4_GRENAT_IPV4_TCP_PAY = 48
    MAC_IPV4_GRENAT_IPV4_SCTP_PAY = 49
    MAC_IPV4_GRENAT_IPV4_ICMP_PAY = 50

    MAC_IPV4_GRENAT_IPV6_IPV6FRAG_PAY = 51
    MAC_IPV4_GRENAT_IPV6_PAY = 52
    MAC_IPV4_GRENAT_IPV6_UDP_PAY = 53
    MAC_IPV4_GRENAT_IPV6_TCP_PAY = 55
    MAC_IPV4_GRENAT_IPV6_SCTP_PAY = 56
    MAC_IPV4_GRENAT_IPV6_ICMP_PAY = 57

    # IPv4 --> GRE/GENEVE/VXLAN --> MAC
    MAC_IPV4_GRENAT_MAC_PAY = 58

    # IPV4 --> GRE/GENEVE/VXLAN
    MAC_IPV4_GRENAT_MAC_IPV4FRAG_PAY = 59
    MAC_IPV4_GRENAT_MAC_IPV4_PAY = 60

    # IPV4 -->GRE/GENEVE/VXLAN --> MAC -->IPV4
    MAC_IPV4_GRENAT_MAC_IPV4_UDP_PAY = 61
    MAC_IPV4_GRENAT_MAC_IPV4_TCP_PAY = 63
    MAC_IPV4_GRENAT_MAC_IPV4_SCTP_PAY = 64
    MAC_IPV4_GRENAT_MAC_IPV4_ICMP_PAY = 65

    # IPV4 -->GRE/GENEVE/VXLAN --> MAC --> IPv6
    MAC_IPV4_GRENAT_MAC_IPV6_IPV6FRAG_PAY = 66
    MAC_IPV4_GRENAT_MAC_IPV6_PAY = 67
    MAC_IPV4_GRENAT_MAC_IPV6_UDP_PAY = 68
    MAC_IPV4_GRENAT_MAC_IPV6_TCP_PAY = 70
    MAC_IPV4_GRENAT_MAC_IPV6_SCTP_PAY = 71
    MAC_IPV4_GRENAT_MAC_IPV6_ICMP_PAY = 72

    # IPV4 -->GRE/GENEVE/VXLAN --> MAC
    MAC_IPV4_GRENAT_MACVLAN_PAY = 73

    # IPv4 --> GRE/GENEVE/VXLAN --> MAC/VLAN --> IPv4
    MAC_IPV4_GRENAT_MACVLAN_IPV4FRAG_PAY = 74
    MAC_IPV4_GRENAT_MACVLAN_IPV4_PAY = 75
    MAC_IPV4_GRENAT_MACVLAN_IPV4_UDP_PAY = 76
    MAC_IPV4_GRENAT_MACVLAN_IPV4_TCP_PAY = 78
    MAC_IPV4_GRENAT_MACVLAN_IPV4_SCTP_PAY = 79
    MAC_IPV4_GRENAT_MACVLAN_IPV4_ICMP_PAY = 80

    # IPv4 --> GRE/GENEVE/VXLAN --> MAC/VLAN --> IPv6
    MAC_IPV4_GRENAT_MACVLAN_IPV6_IPV6FRAG_PAY = 81
    MAC_IPV4_GRENAT_MACVLAN_IPV6_PAY = 82
    MAC_IPV4_GRENAT_MACVLAN_IPV6_UDP_PAY = 83
    MAC_IPV4_GRENAT_MACVLAN_IPV6_TCP_PAY = 85
    MAC_IPV4_GRENAT_MACVLAN_IPV6_SCTP_PAY = 86
    MAC_IPV4_GRENAT_MACVLAN_IPV6_ICMP_PAY = 87


    MAC_IPV6_GRENAT_PAY = 109
    MAC_IPV6_GRENAT_IPV4FRAG_PAY = 110
    MAC_IPV6_GRENAT_IPV4_PAY = 111
    MAC_IPV6_GRENAT_IPV4_UDP_PAY = 112
    MAC_IPV6_GRENAT_IPV4_TCP_PAY = 114
    MAC_IPV6_GRENAT_IPV4_SCTP_PAY = 115
    MAC_IPV6_GRENAT_IPV4_ICMP_PAY = 116

    # IPV6 --> GRE/GENEVE/VXLAN --> IPV6
    MAC_IPV6_GRENAT_IPV6_IPV6FRAG_PAY = 117
    MAC_IPV6_GRENAT_IPV6_PAY = 118
    MAC_IPV6_GRENAT_IPV6_UDP_PAY = 119
    MAC_IPV6_GRENAT_IPV6_TCP_PAY = 121
    MAC_IPV6_GRENAT_IPV6_SCTP_PAY = 122
    MAC_IPV6_GRENAT_IPV6_ICMP_PAY = 123

    # IPV6 --> GRE/GENEVE/VXLAN --> MAC
    MAC_IPV6_GRENAT_MAC_PAY = 124

    # IPV6 --> GRE/GENEVE/VXLAN --> MAC --> IPV4
    MAC_IPV6_GRENAT_MAC_IPV4FRAG_PAY = 125
    MAC_IPV6_GRENAT_MAC_IPV4_PAY = 126
    MAC_IPV6_GRENAT_MAC_IPV4_UDP_PAY = 127
    MAC_IPV6_GRENAT_MAC_IPV4_TCP_PAY = 129
    MAC_IPV6_GRENAT_MAC_IPV4_SCTP_PAY = 130
    MAC_IPV6_GRENAT_MAC_IPV4_ICMP_PAY = 131

    # IPV6 --> GRE/GENEVE/VXLAN --> MAC --> IPV6
    MAC_IPV6_GRENAT_MAC_IPV6_IPV6FRAG_PAY = 132
    MAC_IPV6_GRENAT_MAC_IPV6_PAY = 133
    MAC_IPV6_GRENAT_MAC_IPV6_UDP_PAY = 134
    MAC_IPV6_GRENAT_MAC_IPV6_TCP_PAY = 136
    MAC_IPV6_GRENAT_MAC_IPV6_SCTP_PAY = 137
    MAC_IPV6_GRENAT_MAC_IPV6_ICMP_PAY = 138

    # IPV6 --> GRE/GENEVE/VXLAN --> MAC --> VLAN
    MAC_IPV6_GRENAT_MACVLAN_PAY = 139

    # IPv6 --> GRE/GENEVE/VXLAN --> MAC/VLAN --> IP
    MAC_IPV6_GRENAT_MACVLAN_IPV4_IPV4FRAG_PAY = 140
    MAC_IPV6_GRENAT_MACVLAN_IPV4_PAY = 141
    MAC_IPV6_GRENAT_MACVLAN_IPV4_UDP_PAY = 142
    MAC_IPV6_GRENAT_MACVLAN_IPV4_TCP_PAY = 144
    MAC_IPV6_GRENAT_MACVLAN_IPV4_SCTP_PAY = 145
    MAC_IPV6_GRENAT_MACVLAN_IPV4_ICMP_PAY = 146

    # IPv6 --> GRE/GENEVE/VXLAN --> MAC/VLAN --> IPv6
    MAC_IPV6_GRENAT_MACVLAN_IPV6_IPV6FRAG_PAY = 147
    MAC_IPV6_GRENAT_MACVLAN_IPV6_PAY = 148
    MAC_IPV6_GRENAT_MACVLAN_IPV6_UDP_PAY = 149
    MAC_IPV6_GRENAT_MACVLAN_IPV6_TCP_PAY = 151
    MAC_IPV6_GRENAT_MACVLAN_IPV6_SCTP_PAY = 152
    MAC_IPV6_GRENAT_MACVLAN_IPV6_ICMP_PAY = 153

    MAC_IPV4_ESP = 160
    MAC_IPV6_ESP = 161

    MAC_IPV4_PFC = 278

    MAC_IPV4_GTPC = 327
    MAC_IPV6_GTPC = 328
    MAC_IPV4_GTPU = 329
    MAC_IPV6_GTPU = 330
    MAC_IPV4_GTPU_IPV4 = 332
    MAC_IPV4_GTPU_IPV4_UDP = 333
    MAC_IPV4_GTPU_IPV4_TCP = 334
    MAC_IPV4_GTPU_IPV4_ICMP = 335
    MAC_IPV6_GTPU_IPV4_PAY = 337
    MAC_IPV6_GTPU_IPV4_UDP = 338
    MAC_IPV6_GTPU_IPV4_TCP = 339
    MAC_IPV6_GTPU_IPV4_SCTP = 340

    MAC_IPV4_GTPU_IPV6_IPV6_FRAG = 341
    MAC_IPV6_GTPU_IPV6_PAY = 347
    MAC_IPV6_GTPU_IPV6_UDP = 348
    MAC_IPV6_GTPU_IPV6_TCP = 349
    MAC_IPV6_GTPU_IPV6_SCTP = 350

    MAC_IPV4_PFCP_NODE = 351
    MAC_IPV4_PFCP_SESSION = 352
    MAC_IPV6_PFCP_NODE = 353
    MAC_IPV6_PFCP_SESSION = 354


    MAC_IPV4_L2TPv3 = 360
    MAC_IPV6_L2TPv3 = 361

    # IPv4 L3 (NETWORK CPU)
    MAC_IPV4_L2TPv2_CTRL = 779
    MAC_IPV4_L2TPv2_DATA_WITHL = 780
    MAC_IPV4_L2TPv2_DATA_WITHOUTL = 781

    # IPv6 L3 (NETWORK CPU)
    MAC_IPV6_L2TPv2_CTRL = 787
    MAC_IPV6_L2TPv2_DATA_WITHL = 788
    MAC_IPV6_L2TPv2_DATA_WITHOUTL = 789

    # IPV6 --> GENEVE --> IPV4
    MAC_IPV6_VXLAN_IPV4FRAG_PAY = 877
    MAC_IPV6_VXLAN_IPV4_PAY = 876
    MAC_IPV6_VXLAN_IPV4_UDP_PAY = 879
    MAC_IPV6_VXLAN_IPV4_TCP_PAY = 880
    MAC_IPV6_VXLAN_IPV4_SCTP_PAY = 875
    MAC_IPV6_VXLAN_IPV4_ICMP_PAY = 874

    # IPV6 --> VXLAN --> IPV6
    MAC_IPV6_VXLAN_IPV6_IPV6FRAG_PAY = 871
    MAC_IPV6_VXLAN_IPV6_PAY = 870
    MAC_IPV6_VXLAN_IPV6_UDP_PAY = 872
    MAC_IPV6_VXLAN_IPV6_TCP_PAY = 873
    MAC_IPV6_VXLAN_IPV6_SCTP_PAY = 869
    MAC_IPV6_VXLAN_IPV6_ICMP_PAY = 868

    MAC_IPV6_UDP_VXLAN_PAY = 878


    # ipv4 --> VXLAN
    MAC_IPV4_VXLAN_PAY = 891
    MAC_IPV4_VXLAN_IPV4FRAG_PAY = 890
    MAC_IPV4_VXLAN_IPV4_PAY = 889
    MAC_IPV4_VXLAN_IPV4_UDP_PAY = 892
    MAC_IPV4_VXLAN_IPV4_TCP_PAY = 893
    MAC_IPV4_VXLAN_IPV4_SCTP_PAY = 888
    MAC_IPV4_VXLAN_IPV4_ICMP_PAY = 887

    MAC_IPV4_VXLAN_IPV6_IPV6FRAG_PAY = 884
    MAC_IPV4_VXLAN_IPV6_PAY = 883
    MAC_IPV4_VXLAN_IPV6_UDP_PAY = 885
    MAC_IPV4_VXLAN_IPV6_TCP_PAY = 886
    MAC_IPV4_VXLAN_IPV6_SCTP_PAY = 882
    MAC_IPV4_VXLAN_IPV6_ICMP_PAY = 881


    # IPV6 --> UDP --> GRE --> IPV6
    MAC_IPV6_UDP_GRE_IPV6_IPV6FRAG_PAY = 897
    MAC_IPV6_UDP_GRE_IPV6_PAY = 896
    MAC_IPV6_UDP_GRE_IPV6_UDP_PAY = 898
    MAC_IPV6_UDP_GRE_IPV6_TCP_PAY = 899
    MAC_IPV6_UDP_GRE_IPV6_SCTP_PAY = 895
    MAC_IPV6_UDP_GRE_IPV6_ICMP_PAY = 894

    # ipv6 -->UDP --> GRE --> IPV4
    MAC_IPV6_UDP_GRE_PAY = 904
    MAC_IPV6_UDP_GRE_IPV4FRAG_PAY = 903
    MAC_IPV6_UDP_GRE_IPV4_PAY = 902
    MAC_IPV6_UDP_GRE_IPV4_UDP_PAY = 905
    MAC_IPV6_UDP_GRE_IPV4_TCP_PAY = 906
    MAC_IPV6_UDP_GRE_IPV4_SCTP_PAY = 901
    MAC_IPV6_UDP_GRE_IPV4_ICMP_PAY = 900

    # IPV4 --> UDP --> GRE --> IPV6
    MAC_IPV4_UDP_GRE_IPV6_IPV6FRAG_PAY = 910
    MAC_IPV4_UDP_GRE_IPV6_PAY = 909
    MAC_IPV4_UDP_GRE_IPV6_UDP_PAY = 911
    MAC_IPV4_UDP_GRE_IPV6_TCP_PAY = 912
    MAC_IPV4_UDP_GRE_IPV6_SCTP_PAY = 908
    MAC_IPV4_UDP_GRE_IPV6_ICMP_PAY = 907

    # ipv4 -->UDP --> GRE
    MAC_IPV4_UDP_GRE_PAY = 917
    MAC_IPV4_UDP_GRE_IPV4FRAG_PAY = 916
    MAC_IPV4_UDP_GRE_IPV4_PAY = 915
    MAC_IPV4_UDP_GRE_IPV4_UDP_PAY = 918
    MAC_IPV4_UDP_GRE_IPV4_TCP_PAY = 919
    MAC_IPV4_UDP_GRE_IPV4_SCTP_PAY = 914
    MAC_IPV4_UDP_GRE_IPV4_ICMP_PAY = 913

    # IPV6 --> VXLAN --> MACVLAN --> IPV6
    MAC_IPV6_VXLAN_MACVLAN_IPV6_IPV6FRAG_PAY = 923
    MAC_IPV6_VXLAN_MACVLAN_IPV6_PAY = 922
    MAC_IPV6_VXLAN_MACVLAN_IPV6_UDP_PAY = 924
    MAC_IPV6_VXLAN_MACVLAN_IPV6_TCP_PAY = 925
    MAC_IPV6_VXLAN_MACVLAN_IPV6_SCTP_PAY = 921
    MAC_IPV6_VXLAN_MACVLAN_IPV6_ICMP_PAY = 920

    # IPv6 --> VXLAN --> MAC/VLAN
    MAC_IPV6_VXLAN_MACVLAN_PAY = 930

    # IPv6 --> VXLAN --> MAC/VLAN --> IPv6
    MAC_IPV6_VXLAN_MACVLAN_IPV4_IPV4FRAG_PAY = 929
    MAC_IPV6_VXLAN_MACVLAN_IPV4_PAY = 928
    MAC_IPV6_VXLAN_MACVLAN_IPV4_UDP_PAY = 931
    MAC_IPV6_VXLAN_MACVLAN_IPV4_TCP_PAY = 932
    MAC_IPV6_VXLAN_MACVLAN_IPV4_SCTP_PAY = 927
    MAC_IPV6_VXLAN_MACVLAN_IPV4_ICMP_PAY = 926


    # IPv4 --> VXLAN --> MAC/VLAN --> IPv6
    MAC_IPV4_VXLAN_MACVLAN_IPV6_IPV6FRAG_PAY = 936
    MAC_IPV4_VXLAN_MACVLAN_IPV6_PAY = 935
    MAC_IPV4_VXLAN_MACVLAN_IPV6_UDP_PAY = 937
    MAC_IPV4_VXLAN_MACVLAN_IPV6_TCP_PAY = 938
    MAC_IPV4_VXLAN_MACVLAN_IPV6_SCTP_PAY = 934
    MAC_IPV4_VXLAN_MACVLAN_IPV6_ICMP_PAY = 933

    # IPv4 --> VXLAN --> MAC/VLAN
    MAC_IPV4_VXLAN_MACVLAN_PAY = 943

    # IPv4 --> VXLAN --> MAC/VLAN --> IPv4
    MAC_IPV4_VXLAN_MACVLAN_IPV4_IPV4FRAG_PAY = 942
    MAC_IPV4_VXLAN_MACVLAN_IPV4_PAY = 941
    MAC_IPV4_VXLAN_MACVLAN_IPV4_UDP_PAY = 944
    MAC_IPV4_VXLAN_MACVLAN_IPV4_TCP_PAY = 945
    MAC_IPV4_VXLAN_MACVLAN_IPV4_SCTP_PAY = 940
    MAC_IPV4_VXLAN_MACVLAN_IPV4_ICMP_PAY = 939


    # IPV6 --> UDP --> GRE --> IPV6
    MAC_IPV6_UDP_GRE_MACVLAN_IPV6_IPV6FRAG_PAY = 949
    MAC_IPV6_UDP_GRE_MACVLAN_IPV6_PAY = 948
    MAC_IPV6_UDP_GRE_MACVLAN_IPV6_UDP_PAY = 950
    MAC_IPV6_UDP_GRE_MACVLAN_IPV6_TCP_PAY = 951
    MAC_IPV6_UDP_GRE_MACVLAN_IPV6_SCTP_PAY = 947
    MAC_IPV6_UDP_GRE_MACVLAN_IPV6_ICMP_PAY = 946

    # ipv6 -->UDP --> GRE --> IPV4
    MAC_IPV6_UDP_GRE_MACVLAN_PAY = 956
    MAC_IPV6_UDP_GRE_MACVLAN_IPV4FRAG_PAY = 955
    MAC_IPV6_UDP_GRE_MACVLAN_IPV4_PAY = 954
    MAC_IPV6_UDP_GRE_MACVLAN_IPV4_UDP_PAY = 957
    MAC_IPV6_UDP_GRE_MACVLAN_IPV4_TCP_PAY = 958
    MAC_IPV6_UDP_GRE_MACVLAN_IPV4_SCTP_PAY = 953
    MAC_IPV6_UDP_GRE_MACVLAN_IPV4_ICMP_PAY = 952

    # IPV4 --> UDP --> GRE --> IPV6
    MAC_IPV4_UDP_GRE_MACVLAN_IPV6_IPV6FRAG_PAY = 962
    MAC_IPV4_UDP_GRE_MACVLAN_IPV6_PAY = 961
    MAC_IPV4_UDP_GRE_MACVLAN_IPV6_UDP_PAY = 963
    MAC_IPV4_UDP_GRE_MACVLAN_IPV6_TCP_PAY = 964
    MAC_IPV4_UDP_GRE_MACVLAN_IPV6_SCTP_PAY = 960
    MAC_IPV4_UDP_GRE_MACVLAN_IPV6_ICMP_PAY = 959

    # ipv4 -->UDP --> GRE --> IPV4
    MAC_IPV4_UDP_GRE_MACVLAN_PAY = 969
    MAC_IPV4_UDP_GRE_MACVLAN_IPV4FRAG_PAY = 968
    MAC_IPV4_UDP_GRE_MACVLAN_IPV4_PAY = 967
    MAC_IPV4_UDP_GRE_MACVLAN_IPV4_UDP_PAY = 970
    MAC_IPV4_UDP_GRE_MACVLAN_IPV4_TCP_PAY = 971
    MAC_IPV4_UDP_GRE_MACVLAN_IPV4_SCTP_PAY = 966
    MAC_IPV4_UDP_GRE_MACVLAN_IPV4_ICMP_PAY = 965

    # IPV6 --> VXLAN --> MAC --> IPV6
    MAC_IPV6_VXLAN_MAC_IPV6_IPV6FRAG_PAY = 975
    MAC_IPV6_VXLAN_MAC_IPV6_PAY = 974
    MAC_IPV6_VXLAN_MAC_IPV6_UDP_PAY = 976
    MAC_IPV6_VXLAN_MAC_IPV6_TCP_PAY = 977
    MAC_IPV6_VXLAN_MAC_IPV6_SCTP_PAY = 973
    MAC_IPV6_VXLAN_MAC_IPV6_ICMP_PAY = 972



    # IPV6 --> VXLAN --> MAC
    MAC_IPV6_VXLAN_MAC_PAY = 982

    # IPV6 --> VXLAN --> MAC --> IPV4
    MAC_IPV6_VXLAN_MAC_IPV4FRAG_PAY = 981
    MAC_IPV6_VXLAN_MAC_IPV4_PAY = 980
    MAC_IPV6_VXLAN_MAC_IPV4_UDP_PAY = 983
    MAC_IPV6_VXLAN_MAC_IPV4_TCP_PAY = 984
    MAC_IPV6_VXLAN_MAC_IPV4_SCTP_PAY = 979
    MAC_IPV6_VXLAN_MAC_IPV4_ICMP_PAY = 978

    # ipv4 --> VXLAN --> MAC
    MAC_IPV4_VXLAN_MAC_PAY = 995
    MAC_IPV4_VXLAN_MAC_IPV4FRAG_PAY = 994
    MAC_IPV4_VXLAN_MAC_IPV4_PAY = 993
    MAC_IPV4_VXLAN_MAC_IPV4_UDP_PAY = 996
    MAC_IPV4_VXLAN_MAC_IPV4_TCP_PAY = 997
    MAC_IPV4_VXLAN_MAC_IPV4_SCTP_PAY = 992
    MAC_IPV4_VXLAN_MAC_IPV4_ICMP_PAY = 991

    MAC_IPV4_VXLAN_MAC_IPV6_IPV6FRAG_PAY = 988
    MAC_IPV4_VXLAN_MAC_IPV6_PAY = 987
    MAC_IPV4_VXLAN_MAC_IPV6_UDP_PAY = 989
    MAC_IPV4_VXLAN_MAC_IPV6_TCP_PAY = 990
    MAC_IPV4_VXLAN_MAC_IPV6_SCTP_PAY = 986
    MAC_IPV4_VXLAN_MAC_IPV6_ICMP_PAY = 985



@unique
class DpdkStartMode(Enum):
    AVX512 = '512'
    AVX256 = '256'
    SSE = '128'


@unique
class NcdTimestampRxMode(Enum):
    MODE_PTP_NS = 0
    MODE_1024_NS = 1
    MODE_2048_NS = 2
    MODE_4096_NS = 3
    MODE_8192_NS = 4
    MODE_16384_NS = 5

@unique
class MfgCheckType(Enum):
    MFG_DEF = 0
    MFG_DEF_OCP = 1
    MFG_TEST = 3
    MFG_TEST_OCP = 2
    MFG_MAX_OCP = 4
    MFG_MIDDLE_OCP = 5
    MFG_MIN_OCP = 6

@unique
class BmcSensorState(Enum):
    Unknown = 0
    Normal = 1
    Warning = 2
    Critical = 3
    Fatal = 4
    LowerWarning = 5
    LowerCritical = 6
    LowerFatal = 7
    UpperWarning = 8
    UpperCritical = 9
    UpperFatal = 10


@unique
class BmcEventState(Enum):
    Unknown = 0
    Normal = 1
    Warning = 2
    Critical = 3
    Fatal = 4
    LowerWarning = 5
    LowerCritical = 6
    LowerFatal = 7
    UpperWarning = 8
    UpperCritical = 9
    UpperFatal = 10


@unique
class BmcFwStateMain(Enum):
    UNDEFINED = 0x00  # 未初始化
    INIT = 0x10000  # 初始化
    RUN = 0x20000  # 正常运行
    ABNORMAL = 0x30000  # 异常

@unique
class BmcFwState(Enum):
    START_STATE_UNDEFINED = BmcFwStateMain.UNDEFINED.value  # 未初始化
    START_STATE_INIT_BASE = BmcFwStateMain.INIT.value + 0x1  # 先期初始化
    START_STATE_SCAN_DEVICE = BmcFwStateMain.INIT.value + 0x20  # 设备扫描
    START_STATE_FINISHED = BmcFwStateMain.RUN.value + 0x0  # 初始化完成
    START_STATE_UPGRADE = BmcFwStateMain.RUN.value + 0x1  # 升级中
    RUNNING_STATE_ABNORMAL = BmcFwStateMain.ABNORMAL.value + 0x1  # 运行异常, coredump0
    RUNNING_STATE_ABNORMAL_CORE1 = BmcFwStateMain.ABNORMAL.value + 0x2  # 运行异常, coredump1
    RUNNING_STATE_ABNORMAL_HEART = BmcFwStateMain.ABNORMAL.value + 0x3  # 运行异常, 从核心跳

@unique
class FwLogLevel(Enum):
    FATAL = 1
    ERROR = 2
    WARN = 3
    INFO = 4
    DBGFAULT = 5
    DEBU = 6

@unique
class RdmaMode(Enum):
    RoCE = 'RoCE'
    Infiniband = 'Infiniband'

# 发送模式
class TxBurstMode(Enum):
    SCALAR = 'Scalar'
    SCALAR_SIMPLE = 'Scalar Simple'

    # 512
    VECTOR_AVX512 = 'Vector AVX512'
    VECTOR_AVX512_SIMPLE = 'Vector AVX512 Simple'

    # 256
    VECTOR_AVX2 = 'Vector AVX2'
    VECTOR_AVX2_SIMPLE = 'Vector AVX2 Simple'

    # 128
    VECTOR_SSE = 'Vector SSE'
    VECTOR_SSE_SIMPLE = 'Vector SSE Simple'


# 接收模式
class RxBurstMode(Enum):
    SCALAR = 'Scalar'
    SCALAR_SCATTERED = 'Scalar Scattered'
    SCALAR_BULK_ALLOC = 'Scalar Bulk Alloc'

    # 512
    VECTOR_AVX512_SCATTERED = 'Vector AVX512 Scattered'
    VECTOR_AVX512_SCATTERED_OFFLOAD = 'Offload Vector AVX512 Scattered'
    VECTOR_AVX512 = 'Vector AVX512'
    VECTOR_AVX512_OFFLOAD = 'Offload Vector AVX512'

    # 256
    VECTOR_AVX2_SCATTERED = 'Vector AVX2 Scattered'
    VECTOR_AVX2_SCATTERED_OFFLOAD = 'Offload Vector AVX2 Scattered'
    VECTOR_AVX2 = 'Vector AVX2'
    VECTOR_AVX2_OFFLOAD = 'Offload Vector AVX2'

    # 128
    VECTOR_SSE_SCATTERED = 'Vector SSE Scattered'
    VECTOR_SSE_OFFLOAD = 'Vector SSE'


@unique
class StartMode(Enum):
    AVX512 = '512'
    AVX256 = '256'
    SSE = '128'
    SCALAR_SIMPLE = '64'


class PFSwitchMode(Enum):
    KERNEL = 0
    DPDK = 1
    COMMON = 2
    RDMA = 3
    MAX = 4

class VFSwitchMode(Enum):
    KERNEL = 0
    DPDK = 1
    COMMON = 2
    RDMA = 3
    MAX = 4

class ComModeStr(Enum):
    KERNEL = "kernel"
    DPDK = "dpdk"
    COMMON = "mixed"
    RDMA = "rdma"
