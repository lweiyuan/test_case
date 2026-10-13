#!/usr/bin/python3
# -*- encoding=utf8 -*-
"""
file name = common_func
author: shanshan.du
date: 2024.07.16
"""
import re
import time
from enum import Enum, unique
import datetime

from scripts.script_libs import log, constants
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum, PacketType, PtpNetworkTransportEnum, \
    NicNameEnum, UDPTunnelPacketEnum, PtypeEnum
from scripts.script_libs.ifconfig import IfConfig
from scripts.script_libs.ip_operation import IpOperation


class IPv4Object(object):
    def __init__(self, src_ip: str = '', dst_ip: str = '', tos: str = '',
                 ttl: str = '', proto: str = '', pkid: str = '', chksum: str = '',
                 fragment: bool = False, frag_flags = 'MF', fragment_offset = '0'):
        # src ip
        self.src_ip = src_ip
        # dst_ip
        self.dst_ip = dst_ip
        # Type of Service 服务类型,只有在有QoS差分服务要求时这个字段才起作用。
        self.tos = tos
        # Total Length
        self.ttl = ttl
        # Identification
        self.proto = proto
        # 标识,主机每发一个报文,加1,分片重组时会用到该字段
        self.pkid = pkid
        # check_sum
        self.checksum = chksum

        # 是否分片
        self.fragment = fragment
        # 标志位
        self.frag_flags = frag_flags
        # 片偏移
        self.fragment_offset = fragment_offset


class IPv6Object(object):
    def __init__(self, src_ip: str = '', dst_ip: str = '', tc: str = '',
                 ttl: str = '', next_hdr: str = '', pkid: str = '', fragment: bool = False, frag_id = '1'):
        # src ip
        self.src_ip = src_ip
        # dst_ip
        self.dst_ip = dst_ip

        self.tc = tc
        # Total Length
        self.ttl = ttl

        # proto == nh == next header
        self.next_hdr = next_hdr
        # 标识,主机每发一个报文,加1,分片重组时会用到该字段
        self.pkid = pkid
        # 是否分片
        self.fragment = fragment
        self.frag_id = frag_id


class ESPObject(object):
    def __init__(self, spi: str = '', seq: str = '', data: str = ''):
        self.spi = spi
        self.seq = seq
        self.data = data

class VXLANObject(object):
    def __init__(self, vni: str = '42'):
        self.vni = vni

@unique
class DevTypeEnum(Enum):
    PF = 0
    VF = 1


class PacketHeaderLengthEnum(Enum):
    TCP = 66
    TCP_IPV6 = 86
    IPIP = 20
    TCP_IPV4_IPV4_ETH = 86
    TCP_IPV4_IPV6_ETH = 106
    TCP_IP6IP6 = 134
    TCP_IPV6_IPV4 = 114
    TCP_VXLAN = 86
    TCP_VXLAN_IPV6 = 156
    TCP_VXLAN_IPV6_IPV4 = 136
    TCP_IP6_GRE = 118
    TCP_IPV4_GRE_IPV4_ETH = 90
    TCP_IPV4_GRE_IPV6_ETH = 110
    # RFC 2784 -> 6 , RFC 1701 -> 24
    # GRE: 4, VXLAN: 8
    GRE = 24
    VXLAN = 50
    UDP = 42
    UDP_IPV6 = 62
    UDP_GRE = 66
    UDP_GRE_IPV6_IPV4 = 114
    UDP_IPIP = 62
    # IPv4-in-IPv6, 不包含FCS length
    UDP_IPV6_IPV4 = 82
    # IPv6-in-IPv4
    UDP_IPV4_IPV6 = 82
    UDP_VXLAN = 42
    UDP_GENEVE = 50
    # VXLAN
    TCP_IPV4_ETH_VXLAN_UDP_IPV4_ETH = 116
    TCP_IPV4_ETH_VXLAN_UDP_IPV6_ETH = 136
    TCP_IPV6_ETH_VXLAN_UDP_IPV4_ETH = 136
    TCP_IPV6_ETH_VXLAN_UDP_IPV6_ETH = 156
    # GENEVE
    TCP_IPV4_ETH_GENEVE_UDP_IPV4_ETH = 116
    TCP_IPV4_ETH_GENEVE_UDP_IPV6_ETH = 136
    TCP_IPV6_ETH_GENEVE_UDP_IPV4_ETH = 136
    TCP_IPV6_ETH_GENEVE_UDP_IPV6_ETH = 156
    # 不包含FCS length
    UDP_GENEVE_IPV4_IPV4 = 92
    UDP_GENEVE_IPV4_IPV6 = 112
    UDP_GENEVE_IPV6_IPV4 = 112
    UDP_GENEVE_IPV6_IPV6 = 132


class ExtendedDevTypeEnum(Enum):
    VXLAN = 'vxlan'
    VXLAN_GPE = 'vxlan-gpe'
    VLAN = 'vlan'
    UDP_GUE = 'gue'
    SIT = 'sit'
    ISATAP = 'isatap'
    GRE = 'gre'
    IPIP = 'ipip'
    IP6_IP6 = 'ip6ip6'
    # IPv6-in-IPv4
    IP_IP6 = 'ipip6'
    # IPv4-in-IPv6
    IP6_IP = 'sit'
    IP6_GRE = 'ip6gre'
    VTI6 = 'vti6'
    GEVENE = 'geneve'
    GTPU = 'gtp-u'
    GTPC = 'gtp-c'
    NVGRE = 'nvgre'


class EthtoolTsoTnlTypeEnum(Enum):
    IP4_IP4 = 'ipxip4'
    IP6_IP4 = 'ipxip4'
    IP4_IP6 = 'ipxip6'
    IP6_IP6 = 'ipxip6'
    GRE = 'gre'


# TSO 相关ethtool 影响的配置属性
class TsoObject(object):
    pro_dict = {"tx_udp_tnl_segmentation": "tx-udp_tnl-segmentation",
                "tx_udp_tnl_csum_segmentation": "tx-udp_tnl-csum-segmentation",
                "tx_ipxip4_segmentation": "tx-ipxip4-segmentation",
                "tx_ipxip6_segmentation": "tx-ipxip6-segmentation"}

    def __init__(self, tcp_segmentation_offload: str = 'on',
                 tx_gre_segmentation: str = '',
                 tx_ipxip4_segmentation: str = '',
                 tx_ipxip6_segmentation: str = '',
                 tx_udp_tnl_segmentation: str = ''):
        # 主元素
        self.tcp_segmentation_offload = tcp_segmentation_offload
        self.tx_udp_tnl_segmentation = tx_udp_tnl_segmentation
        # 联动属性
        bind_expected_value = tcp_segmentation_offload
        self.tx_tcp_segmentation = bind_expected_value
        self.tx_tcp_ecn_segmentation = bind_expected_value
        self.tx_tcp6_segmentation = bind_expected_value
        self.tx_tcp_mangleid_segmentation = bind_expected_value
        # 隧道配置
        # if tx_gre_segmentation:
        self.tx_gre_segmentation = tx_gre_segmentation
        self.tx_gre_csum_segmentation = tx_gre_segmentation
        # if tx_ipxip4_segmentation:
        self.tx_ipxip4_segmentation = tx_ipxip4_segmentation
        # elif tx_ipxip6_segmentation:
        self.tx_ipxip6_segmentation = tx_ipxip6_segmentation
        # elif tx_udp_tnl_segmentation:
        self.tx_udp_tnl_csum_segmentation = tx_udp_tnl_segmentation


# USO相关ethtool 影响的配置属性
class UsoObject(object):
    pro_dict = {"tx_udp_segmentation": "tx-udp-segmentation",
                "tx_udp_tnl_segmentation": "tx-udp_tnl-segmentation",
                "tx_udp_tnl_csum_segmentation": "tx-udp_tnl-csum-segmentation"}

    def __init__(self, tx_udp_segmentation: str = 'on',
                 tx_udp_tnl_segmentation: str = 'off',
                 tx_udp_tnl_csum_segmentation: str = 'off'):
        self.tx_udp_segmentation = tx_udp_segmentation
        self.tx_udp_tnl_segmentation = tx_udp_tnl_segmentation
        self.tx_udp_tnl_csum_segmentation = tx_udp_tnl_csum_segmentation


class CommonFunc(object):

    @classmethod
    def create_tunnel(cls, local_ip: str,
                      remote_ip: str,
                      mode: str = 'ipip',
                      name: str = 'tunnel',
                      cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: shanshan.du
        date  : 2024.07.17
        description: 创建指定类型的隧道
        :param local_ip: TX IP
        :param remote_ip: RX IP
        :param mode: 隧道类型, ipip or gre or ip6gre
        :param name: 隧道名称
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: 无返回值
        """
        """
        ip tunnel add tunnel0 mode ipip remote <远程IP地址> local <本地IP地址>
        """
        tunnel_cmd = f"ip tunnel add {name} mode {mode} remote {remote_ip} local {local_ip}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=tunnel_cmd, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        return rtn_code, rtn_outputs, rtn_err

    @classmethod
    def create_vxlan(cls, local_ip: str,
                     remote_ip: str,
                     vxlan_name: str = 'vxlan0',
                     vni_id: int = 42,
                     dev_name: str = '',
                     dst_port: int = 4789,
                     cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author: shanshan.du
        date  : 2024.07.17
        description: 创建 vxlan
        :param local_ip: TX IP
        :param remote_ip: RX IP
        :param vxlan_name: 隧道 vxlan 名称
        :param vni_id: 指定VNI值, 这个值可以在1~2*24之间
        :param dev_name: 网口接口
        :param dst_port: vtep 通信的端口
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: 无返回值
        """
        cmd_prefix = f'ip link add {vxlan_name} type vxlan id {vni_id}'
        vxlan_cmd = f'{cmd_prefix} dstport {dst_port} remote {remote_ip} local {local_ip}  dev {dev_name}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=vxlan_cmd, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        return rtn_code, rtn_outputs, rtn_err

    @classmethod
    def create_geneve(cls,
                      remote_ip: str,
                      geneve_name: str = 'geneve0',
                      vni_id: int = 50,
                      dst_port: int = 6081,
                      cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author: shanshan.du
        date  : 2024.07.17
        description: 创建 vxlan
        :param remote_ip: RX IP
        :param geneve_name: 隧道 vxlan 名称
        :param vni_id: 指定VNI值, 这个值可以在1~2*24之间
        :param dst_port: vtep 通信的端口
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: 无返回值
        """
        cmd_prefix = f'ip link add {geneve_name} type geneve vni {vni_id}'
        vxlan_cmd = f'{cmd_prefix} dstport {dst_port} remote {remote_ip}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=vxlan_cmd, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        return rtn_code, rtn_outputs, rtn_err

    @classmethod
    def create_vlan(cls,
                    device_name: str,
                    vlan_name: str = 'geneve0',
                    vlan_id: int = 50,
                    cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author: shanshan.du
        date  : 2025.01.04
        description: 创建 vxlan
        :param device_name: 网口名称
        :param vlan_name: 隧道 vxlan 名称
        :param vlan_id: 指定vlan_id
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: 无返回值
        """
        vlan_cmd = f"ip link add link {device_name} name {vlan_name} type vlan id {vlan_id}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=vlan_cmd, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        return rtn_code, rtn_outputs, rtn_err

    @classmethod
    def create_nvgre(cls,
                     remote_ip: str,
                     nvgre_name: str = 'nvgre0',
                     vni_id: int = 50,
                     local_ip: str = None,
                     is_layer2: bool = False,
                     cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author: xujw2
        date  : 2026.03.04
        创建 NVGRE 隧道（使用 GRE + key 模拟），自动适配外层 IPv4 或 IPv6
        :param remote_ip: 对端 IP 地址（IPv4 或 IPv6）
        :param nvgre_name: 隧道设备名称
        :param vni_id: 虚拟网络标识（VNI），映射为 GRE key
        :param local_ip: 本端 IP 地址（可选，建议指定）
        :param is_layer2: 是否为二层隧道（True 使用 gretap/ip6gretap，False 使用 gre/ip6gre）
        :param cmd_execute_address: 命令执行环境
        :return: (返回码，标准输出，错误输出)
        """
        import ipaddress

        # 判断 remote_ip 的地址族
        try:
            ip = ipaddress.ip_address(remote_ip)
            outer_family = 'ip6' if ip.version == 6 else 'ip4'
        except ValueError:
            log.warning(f"无法解析 remote_ip '{remote_ip}'，将按 IPv4 处理")
            outer_family = 'ip4'

        # 选择正确的隧道类型
        if outer_family == 'ip4':
            # base_type = 'gretap' if is_layer2 else 'gre'
            base_type = 'gretap'
        else:  # IPv6
            # base_type = 'ip6gretap' if is_layer2 else 'ip6gre'
            base_type = 'ip6gretap'

        # 构建命令
        cmd = f'ip link add {nvgre_name} type {base_type} remote {remote_ip} key {vni_id}'
        if local_ip:
            cmd += f' local {local_ip}'
        # 可选添加 ttl
        # cmd += ' ttl 64'

        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=cmd_execute_address
        )
        log.info(f'NVGRE 创建结果 - code: {rtn_code}, output: {rtn_outputs}, error: {rtn_err}')
        return rtn_code, rtn_outputs, rtn_err

    @classmethod
    def ip_link_set(cls, dev_name: str,
                    operate_type: str = 'up',
                    cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: shanshan.du
        date  : 2024.07.17
        description: 执行ip link set dev_name up|down
        :param dev_name: 网络接口名称
        :param operate_type: up or down
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: (rtn_code, rtn_err, rtn_msg)
        """
        cmd = f"ip link set {dev_name} {operate_type}"
        rtn_code, rtn_msg, rtn_err = CommandOperation. \
            execute_command_with_error(cmd, cmd_execute_address=cmd_execute_address)

        return rtn_code, rtn_msg, rtn_err

    @classmethod
    def ip_link_del(cls, dev_name: str,
                    cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: shanshan.du
        date  : 2024.07.17
        description: 执行ip link set dev_name up|down
        :param dev_name: 网络接口名称
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: (rtn_code, rtn_err, rtn_msg)
        """
        cmd = f"ip link del {dev_name}"
        rtn_code, rtn_msg, rtn_err = CommandOperation. \
            execute_command_with_error(cmd, cmd_execute_address=cmd_execute_address)

        return rtn_code, rtn_msg, rtn_err

    @classmethod
    def ipip_add_addr(cls, dev_name: str, local_ip: str, remote_ip: str,
                      cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: shanshan.du
        date  : 2024.07.17
        description: 执行ip addr add 命令配置 ip-in-ip隧道 ip
        :param dev_name: 网络接口名称
        :param local_ip: 本端隧道ip
        :param remote_ip: 对端隧道ip
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: (rtn_code, rtn_err, rtn_msg)
        """
        addr_cmd = f'ip addr add {local_ip} peer {remote_ip} dev {dev_name}'
        rtn_code, rtn_msg, rtn_err = CommandOperation. \
            execute_command_with_error(addr_cmd, cmd_execute_address=cmd_execute_address)

        return rtn_code, rtn_msg, rtn_err

    @staticmethod
    def ping_node(target_ip: str, device_name: str = '', payload_len=56, disc_opt='', count=10,
                  cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> bool:
        """
        author: shanshan.du
        date  : 2024.07.18
        description: 执行ip link set dev_name up|down
        :param disc_opt: 是否分片的选项
        :param payload_len: payload长度
        :param target_ip: 目标操作ip
        :param device_name: 指定网口执行命令
        :param count: 包数量
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: 返回ip 是否可以 ping 通
        """
        ping_flag = True
        cmd = 'ping -c {} {} -I {} -s {}'.format(count, target_ip, device_name, payload_len)
        if disc_opt:
            cmd += f' -M {disc_opt}'
        _, out, _ = CommandOperation.execute_command_with_error(cmd,
                                                                timeout=30,
                                                                cmd_execute_address=cmd_execute_address)
        if ', 0 received' in out or not len(out.strip()):
            ping_flag = False
        log.info(f"ping node is {ping_flag}, {cmd} result: {out}")
        return ping_flag

    @staticmethod
    def send_packet_by_socket(proto: str = 'TCP',
                              ip_version: int = 4,
                              target_ip: str = '',
                              port: str = '8090',
                              data_size: int = '',
                              file: str = None,
                              count: int = 1,
                              gso_size: int = 1,
                              local_ip: str = '',
                              cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                              netns_name: str = None) -> tuple:
        """
        author: shanshan.du
        date  : 2024.07.18
        description: 通过socket发送数据报文
        :param proto: 报文类型
        :param ip_version: ip协议类型
        :param target_ip: socket server
        :param port: 端口号
        :param data_size: 发送数据
        :param file: 指定文件路径
        :param count: 发送报文个数
        :param gso_size: gso 大小
        :param local_ip: 本端 ip
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :param netns_name: Network Namespace
        :return: 返回是否成功(True, '') or (False, err_msg)
        changelog:
            author: wei.yuan1
            date:2025.01.10
            description: 从namespace空间的网口发包
        """
        vm, rpc_port = CommonOperation.get_node_info_from_path()
        base_tool_dir = f'/root/sxetest/{vm}'
        file_path = f"{base_tool_dir}/send_packet.py"
        send_packet_cmd = f"python3 {file_path} --proto {proto} --ipv {ip_version} --snip {target_ip} "
        send_packet_cmd = f"{send_packet_cmd} --sp {port} --data_len {data_size} --file '{file}' --count {count}"
        if netns_name:
            send_packet_cmd = f"ip netns exec {netns_name} {send_packet_cmd}"
        if proto == 'UDP':
            file_path = f'{base_tool_dir}/send_udp_packet.py'
            send_packet_cmd = f"python3 {file_path} --proto {proto} --ipv {ip_version} --snip {target_ip} "
            send_packet_cmd = f"{send_packet_cmd} --sp {port} --data_len {data_size} --count {count} "
            send_packet_cmd = f"{send_packet_cmd} --gso_size {gso_size} --file_path {base_tool_dir} --cnip {local_ip}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=send_packet_cmd, cmd_execute_address=cmd_execute_address)
        log.info("send msg  rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            return False, rtn_err
        return True, ''

    @staticmethod
    def receive_packet_by_socket(proto: str = 'TCP',
                                 ip_version: int = 4,
                                 target_ip: str = '',
                                 port: str = '8090',
                                 data: str = '',
                                 file: str = None,
                                 cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                                 netns_name: str = None) -> tuple:
        """
        author: shanshan.du
        date  : 2024.07.18
        description: 通过socket接受数据报文
        :param proto: 报文类型
        :param ip_version: ip协议类型
        :param target_ip: socket server
        :param port: 端口号
        :param data: 发送数据
        :param file: 指定文件路径
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: 返回是否成功(True, '') or (False, err_msg)
        :changelog:
            author: wei.yuan1
            date: 2025.01.10
            description: 增加namespace中的测试
            :param netns_name: namespace
        """
        vm, rpc_port = CommonOperation.get_node_info_from_path()

        base_tool_dir = f'/root/sxetest/{vm}'
        file_path = f"{base_tool_dir}/receive_packet.py"
        receive_packet_cmd = f"python3 {file_path} --proto {proto} --ipv {ip_version} --snip {target_ip} "
        receive_packet_cmd = f"{receive_packet_cmd} --sp {port} --data '{data}' --file {file}"
        if netns_name:
            receive_packet_cmd = f"ip netns exec {netns_name} {receive_packet_cmd}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=receive_packet_cmd, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            return False, rtn_err
        return True, ''

    @classmethod
    def tcpdump(cls, iface = None,
                proto: str = None,
                src_ip: str = None,
                dst_ip: str = None,
                ether_src: str = None,
                ether_dst: str = None,
                packet_path: str = '',
                cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> None:
        """
        author: shanshan.du
        date: 2024.07.16
        description: 使用tcpdump抓包
        :param iface: 抓取的网卡子接口名称
        :param proto: 报文类型
        :param src_ip: 源ip
        :param dst_ip: 目的ip
        :param ether_src: mac src
        :param ether_dst: mac dst
        :param packet_path: 抓取的包路径
        :param cmd_execute_address: 命令执行位置
        """
        if proto and proto.lower() != 'ptp':
            tcpdump_cmd = f"tcpdump {proto.lower()} -p "
            if iface:
                if type(iface) is list:
                    dev_parameter = ""
                    for dev in iface:
                        dev_parameter += f" -i {dev}"
                    tcpdump_cmd = f"{tcpdump_cmd}{dev_parameter}"
                else:
                    tcpdump_cmd = f"{tcpdump_cmd} -i {iface}"
            if src_ip:
                tcpdump_cmd = f"{tcpdump_cmd} and src host {src_ip}"
                if dst_ip:
                    tcpdump_cmd = f"{tcpdump_cmd} and dst host {dst_ip}"
            elif dst_ip:
                tcpdump_cmd = f"{tcpdump_cmd} and dst host {dst_ip}"
            if ether_src:
                tcpdump_cmd = f"{tcpdump_cmd} and ether src {ether_src}"
                if ether_dst:
                    tcpdump_cmd = f"{tcpdump_cmd} and ether dst {ether_dst}"
            elif ether_dst:
                tcpdump_cmd = f"{tcpdump_cmd} and ether dst {ether_dst}"
        else:
            tcpdump_cmd = f"tcpdump  -p "
            if iface:
                tcpdump_cmd = f"{tcpdump_cmd} -i {iface} "
            if src_ip:
                tcpdump_cmd = f"{tcpdump_cmd} src host {src_ip}"
                if dst_ip:
                    tcpdump_cmd = f"{tcpdump_cmd} and dst host {dst_ip}"
            elif dst_ip:
                tcpdump_cmd = f"{tcpdump_cmd} dst host {dst_ip}"
            if ether_src:
                tcpdump_cmd = f"{tcpdump_cmd} ether src {ether_src}"
                if ether_dst:
                    tcpdump_cmd = f"{tcpdump_cmd} and ether dst {ether_dst}"
            elif ether_dst:
                tcpdump_cmd = f"{tcpdump_cmd} ether dst {ether_dst}"
        if proto and proto.lower() == 'ptp':
            tcpdump_cmd = f"{tcpdump_cmd} -T {proto.lower()}"
        tcpdump_cmd = f"{tcpdump_cmd} -w {packet_path}"

        CommandOperation.execute_command_with_error(tcpdump_cmd, cmd_execute_address=cmd_execute_address)

    @classmethod
    def read_pcap_with_condition(cls, packet_path: str,
                                 src_ip: str = None,
                                 dst_ip: str = None,
                                 ether_src: str = None,
                                 ether_dst: str = None,
                                 cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author: shanshan.du
        date: 2024.07.16
        description: 读取pcap文件
        :param packet_path: 抓取的包路径
        :param src_ip: 源ip
        :param dst_ip: 目的ip
        :param ether_src: mac src
        :param ether_dst: mac dst
        :param cmd_execute_address: 命令执行位置
        """
        read_pcap_cmd = f"tcpdump -e -r {packet_path} -nn"
        if src_ip:
            read_pcap_cmd = f"{read_pcap_cmd} src host {src_ip}"
            if dst_ip:
                read_pcap_cmd = f"{read_pcap_cmd} and dst host {dst_ip}"
        elif dst_ip:
            read_pcap_cmd = f"{read_pcap_cmd} dst host {dst_ip}"
        if ether_src:
            read_pcap_cmd = f"{read_pcap_cmd} ether src {ether_src}"
            if ether_dst:
                read_pcap_cmd = f"{read_pcap_cmd} and ether dst {ether_dst}"
        elif ether_dst:
            read_pcap_cmd = f"{read_pcap_cmd} ether dst {ether_dst}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            read_pcap_cmd, cmd_execute_address=cmd_execute_address, print_outputs=False)
        # log.info("rtn_code:{}, rtn_outputs:\n{}\n, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            return rtn_outputs
        else:
            if 'truncated dump file' in rtn_err:
                return rtn_outputs
            return ''

    @classmethod
    def get_valid_packet_info(cls, tcpdump_text: str) -> dict:
        """
        author: shanshan.du
        date: 2024.07.19
        description: 获取报文中的src mac 对应数据 length
        :param tcpdump_text:  tcpdump 抓取报文
        :return: 返回发送数据的所有报文 mac, length, flags
        """
        """
        15:18:28.176727 50:7c:6f:07:23:16 > b6:c9:25:33:e7:8b, ethertype IPv4 (0x0800), 
        length 66: 192.181.82.140.38434 > 192.181.82.150.8890: Flags [.], 
        ack 2, win 229, options [nop,nop,TS val 2538713841 ecr 3569487811], length 0

        """
        index = 0
        packet_info = dict()
        data_pattern = r'\S+\s*?(\S+)\s*?>\s*?(\S+),\s+?ethertype\s+(\S+)\s*?.*length\s+(\d+):'
        tcpdump_data_list = re.findall(data_pattern, tcpdump_text)
        for tcpdump_data in tcpdump_data_list:
            src_mac, dst_mac, ether_type, length = tcpdump_data
            if not packet_info.get(src_mac, ''):
                packet_info[src_mac] = []
            packet_info[src_mac].append({'dst_mac': dst_mac, 'length': int(length), 'ether_type': ether_type})
            index += 1

        log.info(f"抓取到所有的报文信息： {packet_info}")
        return packet_info

    @classmethod
    def server_pkill_tcpdump(cls, pcap_path: str, cmd_execute_address) -> tuple:
        """
        author: shanshan.du
        date: 2024.07.25
        description: 在指定端pkill拉起tcpdmup进程，必须用这个方法，才能保证抓包结果落盘
        :param pcap_path: pcap 路径
        :param cmd_execute_address: 执行命令环境
        :return: 返回执行结果
        """
        exec_command = f"ps -ef | grep tcpdump|grep '{pcap_path}'"
        exec_command = f"{exec_command}| grep -v grep | " + " awk '{print $2}' | xargs kill -s 2"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info("exec_command:{}, rtn_code:{}, rtn_outputs:{}, rtn_err:{}".
                 format(exec_command, rtn_code, rtn_outputs, rtn_err))
        return rtn_code, rtn_outputs, rtn_err

    @classmethod
    def server_pkill_socket(cls, server_name: str = 'send_packet.py',
                            cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author: shanshan.du
        date: 2025.01.08
        description: 在指定端pkill拉起socket进程
        :param server_name: receive_packet or send_packet
        :param cmd_execute_address: 执行命令环境
        :return: 返回实例本地属性列表
        """
        kill_cmd = f"ps -ef|grep {server_name}|grep -v grep |awk -F ' ' {{'print $2'}} |xargs kill -9 "
        CommandOperation.execute_command_with_error(kill_cmd, cmd_execute_address=cmd_execute_address)

    @classmethod
    def server_pkill_iperf3(cls, cmd_execute_address, iperf_port: int = constants.IPERF_PORT) -> tuple:
        """
        author: shanshan.du
        date: 2024.07.25
        description: 在指定端pkill拉起iperf3进程
        :param cmd_execute_address: 执行命令环境
        :param iperf_port: iperf3 占用端口
        :return: 返回执行结果
        """
        exec_command = f"ps -ef|grep 'iperf3 -p {iperf_port}' | grep -v grep | awk '{{print $2}}' | xargs kill -2]"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info("exec_command:{}, rtn_code:{}, rtn_outputs:{}, rtn_err:{}".
                 format(exec_command, rtn_code, rtn_outputs, rtn_err))
        return rtn_code, rtn_outputs, rtn_err

    @classmethod
    def server_pkill_phc2sys(cls, cmd_execute_address) -> tuple:
        """
        author: shanshan.du
        date: 2024.07.25
        description: 在指定端pkill拉起phc2sys进程
        :param cmd_execute_address: 执行命令环境
        :return: 返回执行结果
        """
        exec_command = "ps -ef|grep phc2sys|grep CLOCK_REALTIME|grep -v grep|awk '{print $2}'| xargs kill -9 "
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info("exec_command:{}, rtn_code:{}, rtn_outputs:{}, rtn_err:{}".
                 format(exec_command, rtn_code, rtn_outputs, rtn_err))
        return rtn_code, rtn_outputs, rtn_err

    @classmethod
    def server_pkill_ptp4l(cls, cmd_execute_address) -> tuple:
        """
        author: shanshan.du
        date: 2024.07.25
        description: 在指定端pkill拉起ptp4l进程
        :param cmd_execute_address: 执行命令环境
        :return: 返回执行结果
        """
        exec_command = "ps -ef|grep ptp4l | grep -v grep|awk '{print $2}'| xargs kill -9 "
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info("exec_command:{}, rtn_code:{}, rtn_outputs:{}, rtn_err:{}".
                 format(exec_command, rtn_code, rtn_outputs, rtn_err))
        return rtn_code, rtn_outputs, rtn_err

    @staticmethod
    def data_size_to_bytes(data_size: str) -> int:
        """
        author: shanshan.du
        date: 2024.07.16
        description: 转换数据大小为字节单位
        :param data_size: 数据大小
        :return: 返回转换后的数据大小
        """
        byte_size = 1
        if isinstance(data_size, str) and not data_size.title()[-1].isdigit():
            size = int(data_size.title()[:-1])
            s_title = data_size.title()[-1]
            if s_title == 'K':
                byte_size = size * 1024
                # 单位为Mb
            elif s_title == 'M':
                byte_size = size * 1024 * 1024
                # 单位为Gb
            elif s_title == 'G':
                byte_size = size * 1024 * 1024 * 1024
                # 单位为Tb
            elif s_title == 'T':
                byte_size = size * 1024 * 1024 * 1024
                # 如果没有输入单位
            elif s_title == 'B':
                byte_size = size
        else:
            byte_size = int(data_size)

        return byte_size

    @staticmethod
    def get_arp_table(cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> dict:
        """
        author: shanshan.du
        date  : 2024.07.18
        description: 执行arp -n命令
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: 返回是否成功(True, '') or (False, err_msg)
        """
        result_info = dict()
        get_arp_cmd = 'arp -n'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            get_arp_cmd, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:\n{}\n, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            pattern = r'(\S{8,15})\s*?(ether)\s+(.*)\s+(\S+)\s+(en\S*)'
            res_list = re.findall(pattern, rtn_outputs)
            for mac_info in res_list:
                address, hw_type, hw_address, flags_mask, iface = mac_info
                result_info[address] = {'address': address, 'hw_type': hw_type, 'hw_address': hw_address,
                                        'flags_mask': flags_mask, 'iface': iface}

        return result_info

    @staticmethod
    def add_arp_table_record(target_ip: str,
                             target_mac: str,
                             dev_name: str,
                             cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author: shanshan.du
        date  : 2024.07.18
        description: 执行arp -s 192.181.81.40 50:7c:6f:06:74:dc -i ens3f0命令
        :param target_ip: 操作 ip
        :param target_mac: 操作mac addr
        :param dev_name: NIC 网卡接口
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: 返回是否成功(True, '') or (False, err_msg)
        """
        check_flag = False
        err_msg = ''
        add_arp_cmd = f"apr -s {target_ip} {target_mac} -i {dev_name}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            add_arp_cmd, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:\n{}\n, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            check_flag = True
        else:
            err_msg = f"add arp recode failed , err_msg = {rtn_err}"
        return check_flag, err_msg

    @staticmethod
    def compare_dict_info(data_dict1: dict, data_dict2: dict) -> tuple:
        """
        author:             shanshan.du
        date:               2024-07-24
        description:        对比两组字典数据是否一致
        :param data_dict1: 字典形式的数据
        :param data_dict2: 字典形式的数据
        """
        check_flag = True
        err_msg = ''
        if isinstance(data_dict1, dict) and isinstance(data_dict2, dict):
            if len(data_dict1) != len(data_dict2):
                check_flag = False
                err_msg = f'数据长度不一致, expected = {len(data_dict1)}, actual = {len(data_dict2)}'
                return check_flag, err_msg
            for key, value1 in data_dict1.items():
                value2 = data_dict2.get(key, '')
                if not value2:
                    check_flag = False
                    err_msg = f'key={key}在{data_dict2}中不存在'
                    return check_flag, err_msg
                log.info(f'key = {key}, expected value = {value1}, actual = {value2}')
                if value1 != value2:
                    check_flag = False
                    err_msg = f'key={key}在{value1} !+ {value2}'
                    return check_flag, err_msg
        else:
            check_flag = False
            err_msg = '传入数据格式错误'

        return check_flag, err_msg

    @staticmethod
    def get_cli_show_info(cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> dict:
        """
        author: shanshan.du
        date: 2024.07.16
        description: 解析cli show j 命令返回结果
        :param cmd_execute_address:执行命令环境
        :return: 返回解析后的数据dict
        """
        result_dict = {}
        cmd_args = (f"{constants.SCGBECLI64}", constants.SHOW, 'j')
        exec_command = constants.STR_SPACE.join(cmd_args)

        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            result_dict = eval(rtn_outputs)['System']['System Overview']['Controller 0'][0]
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        return result_dict

    @classmethod
    def update_systime(cls, new_time: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> tuple:
        """
        author: shanshan.du
        date: 2024.09.05
        description: 修改当前系统的时间
        :param new_time: 系统时间
        :param cmd_execute_address:执行命令方向
        :return: 返回rtn_code, rtn_info, rtn_err
        """
        rtn_code, rtn_info, rtn_err = CommandOperation. \
            execute_command_with_error(f"date -s '{new_time}'", cmd_execute_address=cmd_execute_address)
        return rtn_code, rtn_info, rtn_err

    @classmethod
    def update_real_time_clock(cls, new_time: str,
                               cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> tuple:
        """
        author: shanshan.du
        date: 2024.09.05
        description: hwclock 命令修改硬件时钟
        :param new_time: 时间
        :param cmd_execute_address:执行命令方向
        :return: 返回rtn_code, rtn_info, rtn_err
        """
        rtn_code, rtn_info, rtn_err = CommandOperation. \
            execute_command_with_error(f"hwclock --set --date='{new_time}'", cmd_execute_address=cmd_execute_address)
        return rtn_code, rtn_info, rtn_err

    @classmethod
    def update_mtu_and_check(cls, caller_class,
                             dev_name: str,
                             mtu: int = 1500,
                             cmd_exec_address: str = CmdExecuteAdressEnum.SERVER.value) -> None:
        """
        author: shanshan.du
        date: 2024.07.16
        description: 修改mtu值后, 验证修改配置是否生效
        :param caller_class: 调用类
        :param dev_name: 设备名称
        :param mtu: 修改mtu的值
        :param cmd_exec_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: None
        """
        rtn_code = IfConfig.set_device_mtu(device_name=dev_name,
                                           mtu_value=mtu,
                                           cmd_exec_address=cmd_exec_address)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            CommonOperation.create_bug_problem(case_cls=caller_class,
                                               key_word="tso",
                                               description_word=f"修改{dev_name}的mtu为{mtu}",
                                               expect_info="命令下发成功",
                                               result_info="命令下发失败")
        nic_mtu_value = IfConfig.get_device_mtu(device_name=dev_name,
                                                cmd_execute_address=cmd_exec_address)
        log.info(f"{dev_name}期望的mtu为{mtu}, 实际为{nic_mtu_value}")
        if int(nic_mtu_value) != mtu:
            CommonOperation.create_bug_problem(case_cls=caller_class,
                                               key_word="mtu",
                                               description_word=f"修改{dev_name}的mtu为{mtu}",
                                               expect_info="修改mtu值实际生效符合预期",
                                               result_info="修改mtu值实际生效不符合预期")

    @classmethod
    def reset_nic(cls,
                  dev_name: str,
                  cmd_exec_address: str = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author: shanshan.du
        date: 2024.09.09
        description: 复位网卡
        :param dev_name: 设备名称
        :param cmd_exec_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: rtn_code, rtn_info, trn_err
        """
        reset_cmd = f'echo 1 > /sys/class/net/{dev_name}/device/reset'
        rtn_code, rtn_info, rtn_err = CommandOperation. \
            execute_command_with_error(reset_cmd,
                                       cmd_execute_address=cmd_exec_address)
        return rtn_code, rtn_info, rtn_err

    @classmethod
    def get_simu_mac(cls, index, pattern_low_bit, pattern_high_bit, other: str = "99:99:99") -> str:
        """
        author: junfeng.he
        date: 2023.08.18
        description: 生成mac地址：如f8:61:1f:35:aa:8f
        :return: 构造的mac addr
        """
        # log.info("{} ,{}".format(index, (0x1 << (1 + pattern_high_bit - pattern_low_bit))))
        if index > (0x1 << (1 + pattern_high_bit - pattern_low_bit)):
            log.error("传入index值范围超限！")
            simu_mac = "FF:FF:FF:FF:FF:FF"
        else:
            value = index << pattern_low_bit
            value = value & 0xffffffffffff
            # reg -> b4:07:00:ff:33:33
            # mac -> 33:33:ff:00:07:b4
            # 组播地址低位第8bit要为1 F9 -> 1111 1001
            simu_mac = "F9:{}:{:02x}:{:02x}".format(
                other,
                # (value % 256) ,
                # (value // 256 % 256),
                # (value // 256 // 256 % 256),
                # (value // 256 // 256 // 256 % 256),
                (value // 256 // 256 // 256 // 256 % 256),
                (value // 256 // 256 // 256 // 256 // 256 % 256)).upper()
            # log.info("simu_mac:{}".format(simu_mac))
        return simu_mac

    @classmethod
    def add_simu_mac(cls, mac_addr: str, dev_name: str,
                     cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                     netns_name: str = None) -> tuple:
        """
        author: junfeng.he
        date: 2023.08.18
        description: add 生成mac地址：如f8:61:1f:35:aa:8f
        :param mac_addr: mac 地址
        :param dev_name: 网络接口名称
        :param cmd_execute_address: 执行环境
        :param netns_name: 网络命名空间
        :return: 返回 rtn_code, rtn_outputs, rtn_err

        @changelog      2025-06-10 15:43:30  shanshan.du
                1. 增加参数netns_name, 支持在namespace中执行命令
        """
        exec_command = f'ip maddr add {mac_addr}  dev {dev_name}'
        if netns_name:
            exec_command = f"ip netns exec {netns_name} {exec_command}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            log.error(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        return rtn_code, rtn_outputs, rtn_err

    @classmethod
    def del_simu_mac(cls, mac_addr: str, dev_name: str,
                     cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> tuple:
        """
        author: junfeng.he
        date: 2023.08.18
        description: 删除生成mac地址：如f8:61:1f:35:aa:8f
        :param mac_addr: mac 地址
        :param dev_name: 网络接口名称
        :param cmd_execute_address: 执行环境
        :return: 返回执行命令结果
        """
        exec_command = f'ip maddr del {mac_addr}  dev {dev_name}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            log.error(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        return rtn_code, rtn_outputs, rtn_err

    @classmethod
    def get_char_device(cls,
                  dev_name: str, bdf: str = '',
                  cmd_exec_address: str = CmdExecuteAdressEnum.SERVER.value) -> list:
        """
        author: shanshan.du
        date: 2026.03.26
        description: 获取当前指定字符设备
        :param dev_name: 设备名称
        :param bdf: pf or vf bdf
        :param cmd_exec_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: rtn_code, rtn_info, trn_err
        """
        character_dpdk_list = []
        bdf = CommonOperation.get_bdf_of_nic(dev_name, cmd_execute_address=cmd_exec_address)
        get_cmd = f'll /dev/{constants.DRV_SCGBE_PF}dpdk-{bdf}'
        bdf_pattern = r'(sxe2-dpdk*)'
        cmd_code, cmd_output, cmd_stderr = CommandOperation.\
            execute_command_with_error(cmd=get_cmd, cmd_execute_address=cmd_exec_address)
        if cmd_code == RtnStatusEnum.SUCCESS.value:
            character_dpdk_list = re.findall(bdf_pattern, cmd_output)

        return character_dpdk_list

    @classmethod
    def check_char_device(cls, dev_name: str, cmd_exec_address: str = CmdExecuteAdressEnum.SERVER.value) -> bool:
        """
        author: shanshan.du
        date: 2026.03.26
        description: 检查当前指定字符设备是否存在
        :param dev_name: 设备名称
        :param bdf: pf or vf bdf
        :param cmd_exec_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: True: 字符设备存在, False: 字符设备不存在
        """
        check_flag = False
        bdf = CommonOperation.get_bdf_of_nic(dev_name, cmd_execute_address=cmd_exec_address)
        get_cmd = f'ls /dev/ | grep dpdk-{bdf}'
        bdf_info = f'dpdk-{bdf}'
        cmd_code, cmd_output, cmd_stderr = CommandOperation.\
            execute_command_with_error(cmd=get_cmd, cmd_execute_address=cmd_exec_address)
        if cmd_code == RtnStatusEnum.SUCCESS.value:
            if bdf_info in cmd_output:
                check_flag = True

        return check_flag


class TcpDumpConfig(object):
    def __init__(self,
                 iface: str = '',
                 proto: str = '',
                 src_ip: str = '',
                 dst_ip: str = '',
                 ether_src: str = '',
                 ether_dst: str = '',
                 pcap_path: str = " tso_test.pcap",
                 run_flag: bool = True):
        self.iface = iface
        self.proto = proto
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.ether_src = ether_src
        self.ether_dst = ether_dst
        self.pcap_path = pcap_path

        self.run_flag = run_flag

    def get_tcpdump_length(self, cmd_execute_address: str) -> int:
        """
        author: shanshan.du
        date: 2025.02.25
        description: 获取抓包的报文个数
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: 返回创建vf device name
        """
        pkt_num = 0
        get_cmd = f'cat {self.pcap_path} |wc -l'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            get_cmd, cmd_execute_address)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            log.error(f'command:{get_cmd}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        else:
            pkt_num = int(rtn_outputs)
        return pkt_num


class FuncRelationObject(object):
    def __init__(self,
                 server_device_ip: str = None,
                 server_device_ipv6: str = None,
                 server_device_name: str = None,
                 server_bus_info: str = None,
                 client_device_ip: str = None,
                 client_device_name: str = None,
                 server_device_mac: str = None,
                 client_device_mac: str = None):
        self.server_device_ip = server_device_ip
        self.server_device_ipv6 = server_device_ipv6
        self.server_device_name = server_device_name
        self.server_bus_info = server_bus_info
        self.client_device_ip = client_device_ip
        self.client_device_name = client_device_name
        self.server_device_mac = server_device_mac
        self.client_device_mac = client_device_mac


class TestDataConfig(object):
    # cfc 长度为 4 字节
    cfc_length = 4
    def __init__(self, mtu: int = 1500,
                 server_dev_type: DevTypeEnum = DevTypeEnum.PF,
                 client_dev_type: DevTypeEnum = DevTypeEnum.PF,
                 proto: str = 'TCP',
                 ip_version: PacketType = PacketType.PACKET_IPV4,
                 ip_version_inner=None,
                 extend_dev_type=None,
                 udp_tnl_type=None,
                 udp_tnl_port=0,
                 test_object=None,
                 device_info_dict=None,
                 data_size: str = "1",
                 gso_size: int = 0,
                 packet_num: int = 1,
                 dpdk_test: bool = False,
                 src_port: int = 8090,
                 dst_port: int = 8090,
                 vf_num: int = 1, create_vf_flag: bool = True, vf_index: int = 0,
                 client_vf_num: int = 1, client_create_vf_flag: bool = True, client_vf_index: int = 0,
                 single_vlan: bool = False, vlan_id: int = 1, double_vlan: bool = False, checksum: str = '0xaabb',
                 ipv4_fragment: bool = False, ipv6_fragment: bool = False,
                 ipv4_obj: IPv4Object = None, ipv6_obj: IPv6Object = None,
                 ipv4_inner_obj: IPv4Object = None, ipv6_inner_obj: IPv6Object = None,
                 esp_obj: ESPObject = None,
                 vxlan_obj: VXLANObject = None, ptype: PtypeEnum = None):
        self.mtu = mtu
        # 发送数据
        self.data_size = data_size
        # gso_size, 只有 UDP 报文才会使用该字段
        self.gso_size = gso_size
        # 发送报文的个数
        self.packet_num = packet_num
        # 本端dev类型
        self.server_dev_type = server_dev_type
        # 对端dev类型
        self.client_dev_type = client_dev_type
        # proto 类型, TCP or UDP
        self.proto = proto
        # 外层协议类型, ipv
        self.ip_version = ip_version
        # 隧道协议类型, ipv
        self.ip_version_inner = ip_version_inner
        # 隧道类型
        self.extend_dev_type = extend_dev_type
        # udp 隧道类型
        self.udp_tnl_type = udp_tnl_type
        # vf 数量
        self.vf_num = vf_num
        # tso or uso object
        self.test_object = test_object
        # outer relationship
        self.outer_func_relation = FuncRelationObject()
        # inner relationship
        self.inner_func_relation = FuncRelationObject()
        # 初始PF连接信息
        self.pf_info = device_info_dict
        # 是否为 dpdk 准备测试数据
        self.dpdk_test = dpdk_test
        # TCP/UDP 端口
        self.src_port = src_port
        self.dst_port = dst_port
        # server 创建vf
        self.create_vf_flag = create_vf_flag
        # server 存在多个 vf 时, vf index 指定选择哪个 vf
        self.vf_index = vf_index
        # client 创建 vf
        self.client_create_vf_flag = client_create_vf_flag
        # client 创建 vf 个数
        self.client_vf_num = client_vf_num
        # client 存在多个 vf 时, vf index 指定选择哪个 vf
        self.client_vf_index = client_vf_index
        # 单层 vlan
        self.single_vlan = single_vlan
        # vlan id
        self.vlan_id = vlan_id
        # 双层vlan
        self.double_vlan = double_vlan
        # check sum
        self.checksum = checksum
        # ipv4 fragment
        self.ipv4_fragment = ipv4_fragment
        # ipv6 fragment
        self.ipv6_fragment = ipv6_fragment
        # udp tnl port
        self.udp_tnl_port = udp_tnl_port
        # ipv4 obj
        self.ipv4_obj = ipv4_obj
        # ipv6 obj
        self.ipv6_obj = ipv6_obj
        # ipv4 inner obj
        self.ipv4_inner_obj = ipv4_inner_obj
        # ipv6 inner obj
        self.ipv6_inner_obj = ipv6_inner_obj
        # esp obj
        self.esp_obj = esp_obj
        # vxlan obj
        self.vxlan_obj = vxlan_obj
        # packet type
        self.ptype = ptype

    def __create_vf(self, pf_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> list:
        """
        author: shanshan.du
        date: 2024.07.17
        description: 创建 PF下的VF
        :param pf_name: PF设备名称
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: 返回创建vf device name
        """
        nicg = CommonOperation.get_nic_generation()
        # echo 1 > num_sri
        vf_name_list = []
        if self.vf_num:
            if (self.create_vf_flag and cmd_execute_address == CmdExecuteAdressEnum.SERVER.value) or \
                    (self.client_create_vf_flag and cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value):
                server_driver_name, client_driver_name = CommonOperation.get_nic_driver_name()
                CommonOperation.concat_test_steps('  创建{}的{}个vf'.format(pf_name, self.vf_num))
                # 默认取 server driver name
                driver_name = server_driver_name
                if cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                    driver_name = client_driver_name
                if driver_name != nicg:
                    CommonOperation.modprobe_driver(
                        CommonOperation.get_nic_vf_driver_name_by_pf(driver_name),
                        cmd_execute_address=cmd_execute_address)
                    log.info(f"清除 pf= {pf_name}的已有vf")
                    CommonOperation.generate_vf_device(
                        pf_device_name=pf_name,
                        vf_num=0,
                        cmd_execute_address=cmd_execute_address)
                log.info(f"创建 pf= {pf_name} {self.vf_num}个vf")
                if driver_name in [NicNameEnum.SXE2.value, NicNameEnum.SCGBE.value]:
                    CommonOperation.generate_vf_device(
                        pf_device_name=pf_name,
                        vf_num=self.vf_num,
                        cmd_execute_address=cmd_execute_address)
                    time.sleep(5)
                    # 加载vf驱动
                    CommonOperation.modprobe_driver(f"{server_driver_name}vf",
                                                    cmd_execute_address=cmd_execute_address)
                elif driver_name in (NicNameEnum.E810.value, NicNameEnum.INTEL_82599.value,
                                     NicNameEnum.SXE.value, NicNameEnum.CX6.value):
                    # 创建 vf 驱动,内核在驱动
                    CommonOperation.generate_vf_device(
                        pf_device_name=pf_name,
                        vf_num=self.vf_num,
                        cmd_execute_address=cmd_execute_address)
                if driver_name in (NicNameEnum.INTEL_82599.value, NicNameEnum.E810.value):
                    # 由于 82599 网卡需要ip link set vf up 才能上报
                    for v_id in range(self.vf_num):
                        vf_name = f'{pf_name}v{v_id}'
                        rtn_code, _, rtn_err = CommonFunc.ip_link_set(dev_name=vf_name,
                                                                      cmd_execute_address=cmd_execute_address)
                        if rtn_code != RtnStatusEnum.SUCCESS.value:
                            log.error(f"ip set {vf_name} up 失败 {rtn_err}")
                            return vf_name_list
            log.info(f" time sleep 10 s, 由于VF上报比较慢")
            time.sleep(10)
            vf_name_list = self.get_vf_list(pf_name=pf_name, cmd_execute_address=cmd_execute_address)
        return vf_name_list

    @staticmethod
    def get_vf_list(pf_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> list:
        """
        author: shanshan.du
        date: 2024.07.17
        description: 获取 PF下的VF
        :param pf_name: PF设备名称
        :param cmd_execute_address: 指定命令执行环境，该值从CmdExecuteAdressEnum中挑选。
        :return: 返回创建vf device name
        """
        # echo 1 > num_sri
        vf_name_list = []
        server_driver_name, client_driver_name = CommonOperation.get_nic_driver_name()
        get_vf_name_cmd = f"ifconfig|grep {pf_name}v |awk -F : '{{print $1}}'"
        if server_driver_name == NicNameEnum.CX6.value:
            pf_name = pf_name[:-3]
            get_vf_name_cmd = f"ifconfig|grep {pf_name}v |awk -F : '{{print $1}}'"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            cmd=get_vf_name_cmd, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            vf_name_list = re.findall(rf'({pf_name}v\S+)', rtn_outputs)
        return vf_name_list

    def get_target_relation(self):
        # 初始环境状态置位
        check_status = True
        log.info("本端拓扑信息生成中....")
        if self.udp_tnl_type:
            if self.udp_tnl_type not in (UDPTunnelPacketEnum.GTPC, UDPTunnelPacketEnum.GTPU,
                                         UDPTunnelPacketEnum.PFCP, UDPTunnelPacketEnum.TEREDO,
                                         UDPTunnelPacketEnum.ROCEV21):
                self.extend_dev_type = self.udp_tnl_type
        pf_name = self.pf_info["server_device_name"]
        pf_ip = self.pf_info['server_device_ip']
        client_pf_name = self.pf_info["client_device_name"]
        client_pf_ip = self.pf_info['client_device_ip']
        # ip 协议类型
        addr_family = 'IPv4'
        # 地址初始化
        # 获取本端PF 的dev name
        self.outer_func_relation.server_device_name = pf_name
        # 获取对端PF 的dev name
        self.outer_func_relation.client_device_name = client_pf_name
        # 获取本端PF的ip
        if self.ip_version == PacketType.PACKET_IPV4:
            self.outer_func_relation.server_device_ip = self.pf_info['server_device_ip']
            self.outer_func_relation.client_device_ip = self.pf_info['client_device_ip']
        else:
            self.outer_func_relation.server_device_ipv6 = self.pf_info['server_device_ipv6']
            self.outer_func_relation.client_device_ip = self.pf_info['client_device_ipv6']
        # 本端拓扑信息生成
        if self.server_dev_type == DevTypeEnum.PF:
            # 获取本端PF 的dev name
            self.outer_func_relation.server_device_name = pf_name
            # 获取对端PF 的dev name
            self.outer_func_relation.client_device_name = client_pf_name
            # 获取本端PF的ip
            if self.ip_version == PacketType.PACKET_IPV4:
                self.outer_func_relation.server_device_ip = self.pf_info['server_device_ip']
                self.outer_func_relation.client_device_ip = self.pf_info['client_device_ip']
            else:
                self.outer_func_relation.server_device_ipv6 = self.pf_info['server_device_ipv6']
                self.outer_func_relation.client_device_ip = self.pf_info['client_device_ipv6']
                addr_family = 'IPv6'
                pf_ip = self.pf_info['server_device_ipv6']
                client_pf_ip = self.pf_info['client_device_ipv6']
            self.outer_func_relation.server_device_mac = self.pf_info['server_device_mac']
            # RX 环境信息配置
            if self.client_dev_type == DevTypeEnum.PF:
                self.outer_func_relation.client_device_name = client_pf_name
                self.outer_func_relation.client_device_ip = client_pf_ip
                self.outer_func_relation.client_device_mac = self.pf_info['client_device_mac']
            elif self.client_dev_type == DevTypeEnum.VF:
                # 创建VF并配置addr
                vf_name_list = self.__create_vf(client_pf_name, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                if len(vf_name_list) < self.vf_num:
                    check_status = False
                    return check_status
                # 获取对端VF 的dev name
                vf_name = vf_name_list[self.client_vf_index] if isinstance(vf_name_list, list) else ''
                self.outer_func_relation.client_device_name = vf_name
                # 已有pf 和 pf 在同一网段, base pf ip 创建不同网段新 ip addr, 再次使得 tx pf 和 rx vf 在同一网段
                new_local_ip = ''
                new_local_ip_prefix = ''
                # 增加check, 确认当前环境中该ip 是否已经存在
                check_rtn_code = RtnStatusEnum.SUCCESS.value
                add_index = 1
                while check_rtn_code == RtnStatusEnum.SUCCESS.value:
                    if add_index > 1:
                        log.warning(f'ip = {new_local_ip} 已经存在, 需要重新生成, add_index = {add_index}')
                    new_local_ip = self.generate_ip(base_ip=pf_ip, common_network=False,
                                                    add_network_prefix=False, ip_version=self.ip_version,
                                                    add_index=add_index)
                    check_ip_exist_cmd = f'ip a|grep {new_local_ip}'
                    check_rtn_code, _, _ = CommandOperation. \
                        execute_command_with_error(cmd=check_ip_exist_cmd,
                                                   cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                    new_local_ip_prefix = self.generate_ip(base_ip=pf_ip,
                                                           common_network=False,
                                                           add_network_prefix=True, ip_version=self.ip_version,
                                                           add_index=add_index)
                    add_index += 1
                # add 本端PF的ip
                if self.ip_version == PacketType.PACKET_IPV4:
                    check_status = IpOperation.add_ip_addr(device_name=pf_name,
                                                           ip_addr=new_local_ip_prefix,
                                                           address_family=addr_family,
                                                           cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                else:
                    check_status = IpOperation.add_ipv6_addr(device_name=pf_name,
                                                             ipv6_addr=new_local_ip_prefix,
                                                             cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                if not check_status:
                    log.error(f"add dev_name = {pf_name} ip = {new_local_ip} 失败")
                    return check_status
                # 更新TX PF ip
                if self.ip_version == PacketType.PACKET_IPV4:
                    self.outer_func_relation.server_device_ip = new_local_ip
                else:
                    self.outer_func_relation.server_device_ipv6 = new_local_ip
                # 生成RX vf 的ip, 与 TX PF在同一网段
                remote_vf_ip = self.generate_ip(base_ip=new_local_ip, common_network=True,
                                                add_network_prefix=False, ip_version=self.ip_version)
                remote_vf_ip_prefix = self.generate_ip(base_ip=new_local_ip,
                                                       common_network=True,
                                                       add_network_prefix=True,
                                                       ip_version=self.ip_version)
                # 修改RX VF ip
                if self.ip_version == PacketType.PACKET_IPV4:
                    check_status = IpOperation.add_ip_addr(device_name=vf_name,
                                                           ip_addr=remote_vf_ip_prefix,
                                                           address_family=addr_family,
                                                           cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                else:
                    check_status = IpOperation.add_ipv6_addr(device_name=vf_name,
                                                             ipv6_addr=remote_vf_ip_prefix,
                                                             cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                if not check_status:
                    log.error(f"add dev_name = {pf_name} ip = {remote_vf_ip} 失败")
                    return check_status
                # 更新RX VF ip
                self.outer_func_relation.client_device_ip = remote_vf_ip
                vf_config = IfConfig.analysis_ifconfig_info(device_name=vf_name,
                                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                self.outer_func_relation.client_device_mac = vf_config['ether']
                time.sleep(5)
            else:
                # 待补充 vxlan, vlan
                pass

        elif self.server_dev_type == DevTypeEnum.VF:
            vf_name_list = self.__create_vf(pf_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            log.info(f'vf_list = {vf_name_list}')
            vf_name = vf_name_list[self.vf_index] if isinstance(vf_name_list, list) else ''
            # TX VF 的dev name
            self.outer_func_relation.server_device_name = vf_name
            # 获取本端 PF的IP
            if self.ip_version == PacketType.PACKET_IPV6:
                addr_family = 'IPv6'
                pf_ip = self.outer_func_relation.client_device_ip
            # 已有pf -> pf, 再增加一对地址 vf -> pf
            # 保持TX PF的ip, 使得TX PF的和RX PF在同一网段, 新增TX vf 与 TX pf 不在同一个网段, 而TX VF与RX PF在同一网段
            # 添加 TX vf ip
            new_local_ip = ''
            new_local_ip_prefix = ''
            # 增加check, 确认当前环境中该ip 是否已经存在
            check_rtn_code = RtnStatusEnum.SUCCESS.value
            add_index = 1
            while check_rtn_code == RtnStatusEnum.SUCCESS.value:
                if add_index > 1:
                    log.warning(f'ip = {new_local_ip} 已经存在, 需要重新生成, add_index = {add_index}')
                new_local_ip = self.generate_ip(base_ip=pf_ip, common_network=False,
                                                add_network_prefix=False, ip_version=self.ip_version,
                                                add_index=add_index)
                temp_remote_ip = self.generate_ip(base_ip=new_local_ip, common_network=True,
                                                  add_network_prefix=False, ip_version=self.ip_version,
                                                  add_index=add_index)
                # check 本端
                log.info(f'vf new_local_ip = {new_local_ip}')
                check_ip_exist_cmd = f'ip a|grep {new_local_ip[:-3]}'
                check_rtn_code, _, _ = CommandOperation. \
                    execute_command_with_error(cmd=check_ip_exist_cmd,
                                               cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                new_local_ip_prefix = self.generate_ip(base_ip=pf_ip, common_network=False,
                                                       add_network_prefix=True, ip_version=self.ip_version,
                                                       add_index=add_index)
                # check 对端
                check_ip_exist_cmd = f'ip a|grep {temp_remote_ip[:-3]}'
                check_rtn_remote_code, _, _ = CommandOperation. \
                    execute_command_with_error(cmd=check_ip_exist_cmd,
                                               cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                # remote ip duplicate
                if check_rtn_remote_code == RtnStatusEnum.SUCCESS.value:
                    check_rtn_code = RtnStatusEnum.SUCCESS.value

                add_index += 1
            # 之所以删除, 是因为vf 可能已经存在, 导致重复添加 ip 失败, 故添加前先删除ip
            IpOperation.flush_ip_addr(device_name=vf_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            IpOperation.flush_ipv6_addr(device_name=vf_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            if self.ip_version == PacketType.PACKET_IPV4:
                check_status = IpOperation.add_ip_addr(device_name=vf_name,
                                                       ip_addr=new_local_ip_prefix,
                                                       address_family=addr_family,
                                                       cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            else:
                check_status = IpOperation.add_ipv6_addr(device_name=vf_name,
                                                         ipv6_addr=new_local_ip_prefix,
                                                         cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            if not check_status:
                log.error(f"add vf dev_name = {pf_name} ip = {new_local_ip} 失败")
                return check_status

            # 添加 RX pf ip
            new_remote_ip = self.generate_ip(base_ip=new_local_ip, common_network=True,
                                             add_network_prefix=False, ip_version=self.ip_version)
            new_remote_ip_prefix = self.generate_ip(base_ip=new_local_ip, common_network=True,
                                                    add_network_prefix=True, ip_version=self.ip_version)
            # cmd_stop = f'systemctl stop NetworkManager'
            # log.warning('CLIENT暂不执行systemctl stop NetworkManager，观察影响')
            # CommandOperation.execute_command_with_error(cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
            #                                             cmd=cmd_stop)

            # 更新TX server端 ip
            if self.ip_version == PacketType.PACKET_IPV4:
                self.outer_func_relation.server_device_ip = new_local_ip
                self.outer_func_relation.client_device_ip = new_remote_ip
            elif self.ip_version == PacketType.PACKET_IPV6:
                self.outer_func_relation.server_device_ipv6 = new_local_ip
                self.outer_func_relation.client_device_ip = new_remote_ip
            log.info(f"初始依赖PF IP = {pf_name}, 生成vf = {vf_name} vf_ip = {new_local_ip}")
            # update tx vf mac
            vf_config = IfConfig.analysis_ifconfig_info(device_name=vf_name,
                                                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            self.outer_func_relation.server_device_mac = vf_config['ether']
            rx_pf_name = self.outer_func_relation.client_device_name
            if self.client_dev_type == DevTypeEnum.VF:
                vf_name_list = self.__create_vf(rx_pf_name, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                # 获取RX VF 的dev name
                remote_vf_name = vf_name_list[self.client_vf_index] if isinstance(vf_name_list, list) else ''
                self.outer_func_relation.client_device_name = remote_vf_name
                IpOperation.flush_ip_addr(device_name=remote_vf_name,
                                          cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                IpOperation.flush_ipv6_addr(device_name=remote_vf_name,
                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                time.sleep(5)
                if self.ip_version == PacketType.PACKET_IPV4:
                    check_status = IpOperation.add_ip_addr(device_name=remote_vf_name,
                                                           ip_addr=new_remote_ip_prefix,
                                                           address_family=addr_family,
                                                           cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                else:
                    check_status = IpOperation.add_ipv6_addr(device_name=remote_vf_name,
                                                             ipv6_addr=new_remote_ip_prefix,
                                                             cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)

                if not check_status:
                    log.error(f"add vf dev_name = {remote_vf_name} ip = {new_remote_ip} 失败")
                    return check_status
                # ip set up
                rtn_code, _, rtn_err = CommonFunc.ip_link_set(dev_name=remote_vf_name,
                                                              cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.error(f"ip link set {self.outer_func_relation.client_device_name} 失败 {rtn_err}")
                    return check_status
                # update RX ip
                self.outer_func_relation.client_device_ip = new_remote_ip
                # update mac
                vf_config = IfConfig.analysis_ifconfig_info(device_name=remote_vf_name,
                                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                self.outer_func_relation.client_device_mac = vf_config['ether']
            elif self.client_dev_type == DevTypeEnum.PF:
                self.outer_func_relation.client_device_name = client_pf_name
                self.outer_func_relation.client_device_ip = new_remote_ip
                self.outer_func_relation.client_device_mac = self.pf_info['client_device_mac']
                if self.ip_version == PacketType.PACKET_IPV4:
                    check_status = IpOperation.add_ip_addr(device_name=client_pf_name,
                                                           ip_addr=new_remote_ip_prefix,
                                                           address_family=addr_family,
                                                           cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                else:
                    check_status = IpOperation.add_ipv6_addr(device_name=client_pf_name,
                                                             ipv6_addr=new_remote_ip_prefix,
                                                             cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                if not check_status:
                    log.error(f"add remote pf dev_name = {pf_name} ip = {new_remote_ip} 失败")
                    return check_status

        tunnel_name = ''
        udp_tnl_check = False
        if self.udp_tnl_type not in (UDPTunnelPacketEnum.GTPC, UDPTunnelPacketEnum.GTPU,
                                     UDPTunnelPacketEnum.PFCP, UDPTunnelPacketEnum.TEREDO,
                                     UDPTunnelPacketEnum.ROCEV21):
            udp_tnl_check = True
        # create vxlan or gre or ip-in-ip or geneve
        if self.extend_dev_type or (self.udp_tnl_type and udp_tnl_check):
            tunnel_name = f'{self.extend_dev_type.value}_test'
            CommonOperation.concat_test_steps('为避免有隧道残留, 删除 TX 和 RX 已存在的隧道等接口')
            del_name = f'{tunnel_name}_s0_name'
            CommonFunc.ip_link_del(dev_name=del_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            del_name = f'{tunnel_name}_c0_name'
            CommonFunc.ip_link_del(dev_name=del_name, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
            CommonFunc.ip_link_del(dev_name=tunnel_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            CommonFunc.ip_link_del(dev_name=tunnel_name, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)

            # dpdk 场景只生成ip, 不生成隧道
            outter_tx_base_ip = ''
            outter_rx_base_ip = ''
            inner_tx_base_ip = ''
            inner_rx_base_ip = ''
            if self.ip_version == PacketType.PACKET_IPV4 and self.ip_version_inner in (None, PacketType.PACKET_IPV4):
                outter_tx_base_ip = self.outer_func_relation.server_device_ip
                outter_rx_base_ip = self.outer_func_relation.client_device_ip
                inner_tx_base_ip = self.outer_func_relation.server_device_ip
            elif self.ip_version == PacketType.PACKET_IPV6 and self.ip_version_inner in (None, PacketType.PACKET_IPV6):
                outter_tx_base_ip = self.outer_func_relation.server_device_ipv6
                outter_rx_base_ip = self.outer_func_relation.client_device_ip
                inner_tx_base_ip = self.outer_func_relation.server_device_ipv6
            elif self.ip_version == PacketType.PACKET_IPV4 and self.ip_version_inner == PacketType.PACKET_IPV6:
                outter_tx_base_ip = self.outer_func_relation.server_device_ip
                outter_rx_base_ip = self.outer_func_relation.client_device_ip
                # 因为需要给隧道内创建ipv6 地址
                inner_tx_base_ip = self.pf_info['server_device_ipv6']
            elif self.ip_version == PacketType.PACKET_IPV6 and self.ip_version_inner == PacketType.PACKET_IPV4:
                outter_tx_base_ip = self.outer_func_relation.server_device_ipv6
                outter_rx_base_ip = self.outer_func_relation.client_device_ip
                # 因为需要给隧道内创建ipv4 地址
                inner_tx_base_ip = self.pf_info['server_device_ip']

            inner_tx_ip = ''
            inner_tx_ip_prefix = ''
            # 增加check, 确认当前环境中该ip 是否已经存在
            check_rtn_code = RtnStatusEnum.SUCCESS.value
            add_index = 1
            while check_rtn_code == RtnStatusEnum.SUCCESS.value and inner_tx_base_ip:
                if add_index > 1:
                    log.warning(f'ip = {inner_tx_ip} 已经存在, 需要重新生成, add_index = {add_index},'
                                f' inner_tx_base_ip = {inner_tx_base_ip},new_tx_ip = {inner_tx_ip}')
                inner_tx_ip = self.generate_ip(base_ip=inner_tx_base_ip,
                                               common_network=False,
                                               add_network_prefix=False,
                                               ip_version=self.ip_version_inner, add_index=add_index)
                if not inner_tx_ip:
                    log.error(f'生成 新的 inner_tx_ip 为空')
                    break
                if inner_tx_ip:
                    check_ip_exist_cmd = f'ip a|grep {inner_tx_ip}'
                    check_rtn_code, _, _ = CommandOperation. \
                        execute_command_with_error(cmd=check_ip_exist_cmd,
                                                   cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                inner_tx_ip_prefix = self.generate_ip(base_ip=inner_tx_base_ip,
                                                      common_network=False,
                                                      add_network_prefix=True,
                                                      ip_version=self.ip_version_inner, add_index=add_index)

                add_index += 1

            inner_rx_ip = self.generate_ip(base_ip=inner_tx_ip,
                                           common_network=True,
                                           add_network_prefix=False,
                                           ip_version=self.ip_version_inner)
            inner_rx_ip_prefix = self.generate_ip(base_ip=inner_tx_ip,
                                                  common_network=True,
                                                  add_network_prefix=True,
                                                  ip_version=self.ip_version_inner)
            if self.ip_version_inner == PacketType.PACKET_IPV4:
                self.inner_func_relation.server_device_ip = inner_tx_ip
            else:
                self.inner_func_relation.server_device_ipv6 = inner_tx_ip
            self.inner_func_relation.client_device_ip = inner_rx_ip
            log.info(f"inner_tx_base_ip = {inner_tx_base_ip}, tunnel = {tunnel_name},\
             inner_tx_ip = {inner_tx_ip}, inner_rx_ip = {inner_rx_ip}")
            if self.dpdk_test:
                # dpdk 只添加地址, 不实际创建隧道
                check_status = True
                # 强制设置外层 mac 为内层 mac
                self.inner_func_relation.server_device_mac = self.outer_func_relation.server_device_mac
                self.inner_func_relation.client_device_mac = self.outer_func_relation.client_device_mac
                return check_status
            if not self.dpdk_test:
                # 在客户端入口
                if self.extend_dev_type == ExtendedDevTypeEnum.VXLAN:
                    rtn_code, _, rtn_err = CommonFunc. \
                        create_vxlan(local_ip=outter_tx_base_ip,
                                     remote_ip=outter_rx_base_ip,
                                     vxlan_name=tunnel_name,
                                     dev_name=self.outer_func_relation.server_device_name,
                                     cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                elif self.extend_dev_type == ExtendedDevTypeEnum.GEVENE:
                    rtn_code, _, rtn_err = CommonFunc. \
                        create_geneve(remote_ip=outter_rx_base_ip,
                                      geneve_name=tunnel_name,
                                      cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                elif self.extend_dev_type == ExtendedDevTypeEnum.VLAN:
                    rtn_code, _, rtn_err = CommonFunc. \
                        create_vlan(device_name=self.outer_func_relation.server_device_name,
                                    vlan_name=tunnel_name,
                                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                elif self.extend_dev_type == ExtendedDevTypeEnum.NVGRE:
                    rtn_code, _, rtn_err = CommonFunc. \
                        create_nvgre(remote_ip=outter_rx_base_ip,
                                      nvgre_name=tunnel_name,
                                      local_ip=outter_tx_base_ip,
                                      cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                else:
                    # 在客户端入口
                    # ip tunnel add tunl0 mode ipip remote <服务器IP地址> local <客户端IP地址>
                    rtn_code, _, rtn_err = CommonFunc. \
                        create_tunnel(local_ip=outter_tx_base_ip,
                                      remote_ip=outter_rx_base_ip,
                                      mode=self.extend_dev_type.value,
                                      name=tunnel_name,
                                      cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)

                self.inner_func_relation.server_device_name = tunnel_name
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.error(f"ip tunnel add {tunnel_name} 失败 {rtn_err}")
                    check_status = False
                    return check_status
                # tx tunnel set up
                rtn_code, _, rtn_err = CommonFunc. \
                    ip_link_set(dev_name=tunnel_name,
                                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.error(f"ip set {tunnel_name} up 失败 {rtn_err}")
                    check_status = False
                    return check_status

                #  ip addr add <客户端隧道地址>/24 dev tunl0
                log.info('客户端隧道地址')
                # add tx tunnel addr
                if self.ip_version_inner == PacketType.PACKET_IPV4:
                    addr_family = 'ipv4'
                    check_status = IpOperation.add_ip_addr(device_name=tunnel_name,
                                                           ip_addr=inner_tx_ip_prefix,
                                                           address_family=addr_family,
                                                           cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                else:
                    check_status = IpOperation.add_ipv6_addr(device_name=tunnel_name,
                                                             ipv6_addr=inner_tx_ip_prefix,
                                                             cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                if not check_status:
                    log.error(f"add inner tx ip ={inner_tx_ip} up 失败 {rtn_err}")
                    return check_status

                # 在服务器入口
                if self.extend_dev_type == ExtendedDevTypeEnum.VXLAN:
                    rtn_code, _, rtn_err = CommonFunc. \
                        create_vxlan(local_ip=outter_rx_base_ip,
                                     remote_ip=outter_tx_base_ip,
                                     vxlan_name=tunnel_name,
                                     dev_name=self.outer_func_relation.client_device_name,
                                     cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                elif self.extend_dev_type == ExtendedDevTypeEnum.GEVENE:
                    rtn_code, _, rtn_err = CommonFunc. \
                        create_geneve(remote_ip=outter_tx_base_ip,
                                      geneve_name=tunnel_name,
                                      cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                elif self.extend_dev_type == ExtendedDevTypeEnum.VLAN:
                    rtn_code, _, rtn_err = CommonFunc. \
                        create_vlan(device_name=self.outer_func_relation.client_device_name,
                                    vlan_name=tunnel_name,
                                    cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                elif self.extend_dev_type == ExtendedDevTypeEnum.NVGRE:
                    rtn_code, _, rtn_err = CommonFunc. \
                        create_nvgre(remote_ip=outter_tx_base_ip,
                                      nvgre_name=tunnel_name,
                                      local_ip=outter_rx_base_ip,
                                      cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                else:
                    # ip tunnel add tunl0 mode ipip remote <客户端IP地址> local <服务器IP地址>
                    rtn_code, _, rtn_err = CommonFunc. \
                        create_tunnel(local_ip=outter_rx_base_ip,
                                      remote_ip=outter_tx_base_ip,
                                      mode=self.extend_dev_type.value,
                                      name=tunnel_name,
                                      cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)

                if rtn_code != RtnStatusEnum.SUCCESS.value:
                    log.error(f"ip set {tunnel_name} up 失败 {rtn_err}")
                    check_status = False
                    return check_status
                check_status = CommonFunc.ip_link_set(dev_name=tunnel_name,
                                                      cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                if not check_status:
                    log.error(f"ip add {tunnel_name} 失败")
                    return check_status
            self.inner_func_relation.client_device_name = tunnel_name
            # ip addr add <服务器隧道地址>/24 dev tunl0
            log.info(f'设置服务器隧道地址: {inner_rx_ip_prefix}')
            # add rx tunnel addr
            if self.ip_version_inner == PacketType.PACKET_IPV4:
                addr_family = 'ipv4'
                log.info(f'当前是 inner = ipv4 addr_family = {addr_family}')
                check_status = IpOperation.add_ip_addr(device_name=tunnel_name,
                                                       ip_addr=inner_rx_ip_prefix,
                                                       address_family=addr_family,
                                                       cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
            else:
                check_status = IpOperation.add_ipv6_addr(device_name=tunnel_name,
                                                         ipv6_addr=inner_rx_ip_prefix,
                                                         cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)

            if not check_status:
                log.error(f"ip add {tunnel_name} 失败")
                return check_status

            cmd_stop = f'systemctl stop NetworkManager'
            log.warning('CLIENT暂不执行systemctl stop NetworkManager，观察影响')
            CommandOperation.execute_command_with_error(cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                                        cmd=cmd_stop)
            CommandOperation.execute_command_with_error(cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                        cmd=cmd_stop)

            if self.ip_version == PacketType.PACKET_IPV4:
                self.inner_func_relation.server_device_ip = inner_tx_ip
            else:
                self.inner_func_relation.server_device_ipv6 = inner_tx_ip
            self.inner_func_relation.client_device_ip = inner_rx_ip
            log.info(f"inner_tx_base_ip = {inner_tx_base_ip}, tunnel = {self.extend_dev_type.value},\
             inner_tx_ip = {inner_tx_ip}, inner_rx_ip = {inner_rx_ip}")
        time.sleep(8)

        # 只有非 dpdk 的场景才可以ping 通
        if not self.dpdk_test:
            if self.outer_func_relation.client_device_ip:
                log.info("time sleep 5 s ")
                time.sleep(5)
                # ping tx
                if self.ip_version == PacketType.PACKET_IPV4 and self.outer_func_relation.server_device_ip:
                    check_status = CommonFunc.ping_node(target_ip=self.outer_func_relation.server_device_ip,
                                                        device_name=self.outer_func_relation.client_device_name,
                                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                elif self.outer_func_relation.server_device_ipv6:
                    target_ip = self.outer_func_relation.server_device_ipv6
                    time.sleep(10)
                    check_status = CommonFunc.ping_node(target_ip=target_ip,
                                                        device_name=self.outer_func_relation.client_device_name,
                                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                if not check_status:
                    log.error(f"rx ping tx {self.outer_func_relation.server_device_ip}\
                     or {self.outer_func_relation.server_device_ipv6} 失败")
                    return check_status
                # ping rx
                target_ip = self.outer_func_relation.client_device_ip
                if self.ip_version == PacketType.PACKET_IPV6:
                    time.sleep(10)
                    target_ip = self.outer_func_relation.client_device_ip
                check_status = CommonFunc.ping_node(target_ip=target_ip,
                                                    device_name=self.outer_func_relation.server_device_name,
                                                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                if not check_status:
                    log.error(f"tx ping rx {self.outer_func_relation.client_device_ip} 失败")
                    return check_status
            if self.inner_func_relation.client_device_ip:
                # ping tx
                if self.ip_version == PacketType.PACKET_IPV4 and self.inner_func_relation.server_device_ip:
                    time.sleep(5)
                    check_status = CommonFunc.ping_node(target_ip=self.inner_func_relation.server_device_ip,
                                                        device_name=self.inner_func_relation.client_device_name,
                                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                elif self.inner_func_relation.server_device_ipv6:
                    target_ip = self.inner_func_relation.server_device_ipv6
                    time.sleep(10)
                    check_status = CommonFunc.ping_node(target_ip=target_ip,
                                                        device_name=self.inner_func_relation.client_device_name,
                                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                if not check_status:
                    log.error(f"rx ping inner tx {self.outer_func_relation.server_device_ip} 失败")
                    return check_status
                # ping rx
                target_ip = self.inner_func_relation.client_device_ip
                time.sleep(5)
                if self.ip_version_inner == PacketType.PACKET_IPV6:
                    target_ip = self.inner_func_relation.client_device_ip
                    time.sleep(10)
                check_status = CommonFunc.ping_node(target_ip=target_ip,
                                                    device_name=self.inner_func_relation.server_device_name,
                                                    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                if not check_status:
                    log.error(f"tx ping rx {self.inner_func_relation.client_device_ip} 失败")
        if self.extend_dev_type and self.extend_dev_type in (ExtendedDevTypeEnum.VXLAN,
                                                             ExtendedDevTypeEnum.GEVENE,
                                                             ExtendedDevTypeEnum.VLAN):
            if not self.dpdk_test:
                server_obj = IfConfig.analysis_ifconfig_info(device_name=tunnel_name,
                                                             cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
                client_obj = IfConfig.analysis_ifconfig_info(device_name=tunnel_name,
                                                             cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                self.inner_func_relation.server_device_mac = server_obj['ether']
                self.inner_func_relation.client_device_mac = client_obj['ether']
            else:
                client_obj = IfConfig.analysis_ifconfig_info(device_name=tunnel_name,
                                                             cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
                self.inner_func_relation.client_device_mac = client_obj['ether']

        return check_status

    @staticmethod
    def generate_ip(base_ip: str,
                    common_network: bool = False,
                    add_network_prefix: bool = True,
                    ip_version: Enum = PacketType.PACKET_IPV4,
                    add_index: int = 1) -> str:
        """
        author: shanshan.du
        date: 2024.07.17
        description: 在base ip 基础上生成新的 IP 地址
        :param base_ip: 参考 ip
        :param common_network: 默认生成IP与base ip 不在同一网段
        :param add_network_prefix: 生成ip addr 时是添加网络地址前缀： True, False: 反之
        :param ip_version: ip 协议类型
        :param add_index: ip 修改变量
        :return: 返回新 ip 地址
        """
        new_ip_format = ''
        if ip_version == PacketType.PACKET_IPV4:
            ip_pattern = r'(\d+).(\d+).(\d+).(\d+)'
            result_ip = re.findall(ip_pattern, base_ip)
            if not result_ip:
                log.error(f"base_ip = {base_ip},获取 ip 分段失败 ")
                return new_ip_format
            ip_p1, ip_p2, ip_p3, ip_p4 = result_ip[0]

            if common_network:
                if int(ip_p4) + 10 * add_index > 255:
                    ip_p4 = int(ip_p4) - 10 * add_index
                else:
                    ip_p4 = int(ip_p4) + 10 * add_index
                new_ip = ".".join([ip_p1, ip_p2, ip_p3, f"{ip_p4}"])
            else:
                if int(ip_p3) + 1 * add_index > 255:
                    ip_p3 = int(ip_p3) - 1 * add_index
                else:
                    ip_p3 = int(ip_p3) + 1 * add_index
                new_ip = ".".join([ip_p1, ip_p2, f"{ip_p3}", ip_p4])
            if add_network_prefix:
                new_ip_format = f"{new_ip}/24"
            else:
                new_ip_format = new_ip
        elif ip_version == PacketType.PACKET_IPV6:
            if common_network:
                ip_pattern = r'(\S+)(\d+)'
                ip_part_prefix, ip_part_end = re.findall(ip_pattern, base_ip)[0]
                new_ip_part = f"{int(ip_part_end, 16) + 10 * add_index:0x}"
                new_ip = f"{ip_part_prefix}{new_ip_part}"
            else:
                ip_pattern = r'(\S+::)([a-zA-Z0-9]+)(:[a-zA-Z0-9]+)'
                ip_part_prefix, ip_part_mid, ip_part_end = re.findall(ip_pattern, base_ip)[0]
                new_ip_part = f"{int(ip_part_mid, 16) + 10 * add_index:0x}"
                new_ip = f"{ip_part_prefix}{new_ip_part}{ip_part_end}"
            if add_network_prefix:
                new_ip_format = f"{new_ip}/112"
            else:
                new_ip_format = new_ip

        return new_ip_format


class DateUtils(object):
    @classmethod
    def get_now_datetime(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> datetime:
        """
        author: shanshan.du
        date: 2024.09.05
        description: 获取当前系统的时间
        :param cmd_execute_address:执行命令方向
        :return: 返回时间: 2024-09-05 09:49:01
        """
        cmd = 'timedatectl'
        rtn_code, rtn_info, rtn_err = CommandOperation. \
            execute_command_with_error(cmd=cmd, cmd_execute_address=cmd_execute_address)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            return None
        pattern = r'(Local time):[\s|\S]*?(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+'
        time_list = re.findall(pattern, rtn_info)
        if not time_list:
            return None
        time_dict = dict(time_list)
        now_time = time_dict['Local time']
        date_format = '%Y-%m-%d %H:%M:%S'
        new_datetime = datetime.datetime.strptime(now_time, date_format)

        return new_datetime

    @classmethod
    def get_rtc_time(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> datetime:
        """
        author: shanshan.du
        date: 2024.09.05
        description: 获取硬件时钟时间
        :param cmd_execute_address:执行命令方向
        :return: 返回时间: 2024-09-05 09:49:01
        """
        cmd = 'timedatectl'
        rtn_code, rtn_info, rtn_err = CommandOperation. \
            execute_command_with_error(cmd=cmd, cmd_execute_address=cmd_execute_address)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            return None
        pattern = r'(RTC time):[\s|\S]*?(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+'
        time_list = re.findall(pattern, rtn_info)
        if not time_list:
            return None
        time_dict = dict(time_list)
        now_time = time_dict['RTC time']
        date_format = '%Y-%m-%d %H:%M:%S'
        new_datetime = datetime.datetime.strptime(now_time, date_format)

        return new_datetime

    @classmethod
    def update_datetime(cls, base_datetime: datetime, days: int = 0, hours: int = 0,
                        minutes: int = 0, seconds: int = 0) -> datetime:
        """
        author: shanshan.du
        date: 2024.09.05
        description: 修改当前系统的时间
        :param base_datetime: 初始时间
        :param days: 修改天数增量
        :param hours: 修改小时增量
        :param minutes: 修改分钟增量
        :param seconds: 修改秒数增量
        :return: 返回时间: 2024-09-05 09:49:01
        """
        new_time = base_datetime + datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
        return new_time

    @classmethod
    def get_str_datetime(cls, new_datetime: datetime) -> str:
        """
        author: shanshan.du
        date: 2024.09.05
        description: datetime 类型转换为日期字符串
        :param new_datetime: 时间
        :return: 返回时间: 2024-09-05 09:49:01
        """
        date_format = '%Y-%m-%d %H:%M:%S'
        new_str_time = new_datetime.strftime(date_format)
        return new_str_time


class PtpUtils(object):
    @classmethod
    def exec_ptp(cls, dev_name: str,
                 network_transport: int = 4,
                 time_stamp: str = '',
                 exec_time: int = 40,
                 slave_only_mode: bool = True,
                 cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                 redirect: bool = False, file_name: str = '') -> tuple:
        """
        author: shanshan.du
        date: 2024.09.05 10:52:30
        description: 主从时钟同步系统时间一致
        :param dev_name: 网卡设备名称
        :param time_stamp: 目前支持 -H        HARDWARE (default)
                                   -S        SOFTWARE
                                   -L        LEGACY HW
        :param network_transport: 目前支持 -2        IEEE 802.3
                                          -4        UDP IPV4 (default)
                                          -6        UDP IPV6

        :param exec_time: 命令执行的时间
        :param slave_only_mode: slave only mode
        :param cmd_execute_address:执行命令方向
        :param redirect: 是否重定向到文件
        :param file_name: 重定向文件名称
        :return: 返回 rtn_code, rtn_info, rtn_err
        """
        ptp_cmd = f'timeout {exec_time} ptp4l -i {dev_name} -m -{network_transport}'
        if time_stamp:
            ptp_cmd = f'{ptp_cmd} -{time_stamp}'
        if slave_only_mode:
            ptp_cmd = f'{ptp_cmd} -s'
        if redirect:
            ptp_cmd = f'{ptp_cmd} > {file_name}'
        rtn_code, rtn_info, rtn_err = CommandOperation. \
            execute_command_with_error(cmd=ptp_cmd, cmd_execute_address=cmd_execute_address)
        return rtn_code, rtn_info, rtn_err

    @classmethod
    def check_tcpdump_text(cls, tcpdump_text: str, dst_mac: str,
                           network_transport: int = PtpNetworkTransportEnum.ETHER.value) -> tuple:
        """
        author: shanshan.du
        date: 2024.09.04
        descriptor: 解析tcpdump抓取报文的dst_ip 是否符合组播地址, 首地址在224~239
        :param tcpdump_text: tcpdump 抓取报文
        :param dst_mac: 目的 mac
        :param network_transport: 网络协议类型
        :return: (True, '') or (False, err_msg)
        """
        """
        协议MAC举例
        01-00-5E-00-00-B8 为 BFD MAC;

        09-00-2B-00-00-05 为 Cisco ISIS 协议MAC;

        01-1B-19-00-00-00 为 PTP 协议MAC;

        01-0F-E2-00-00-01 为 DLDP 协议MAC;

        01-00-0C-CC-CC-CC 为 ULDP(UniDirectional Link Detection Protocol) 协议MAC;

        01-00-0C-CC-CC-CD 为 PVST（Per VLAN Spanning Tree）协议MAC
        """
        """
        IP组播MAC格式
        IPv4组播mac：01-00-5E-XX-XX-XX
        IP后3字节

        IPv6组播mac：33-33-XX-XX-XX-XX
        IP后4字节
        """
        check_flag = False
        err_msg = ''
        data_pattern = r'length\s+\d+:\s+([a-zA-Z0-9.]{1,})\s+>\s+([a-zA-Z0-9.]{1,}):\s+PTPv2'
        if network_transport == PtpNetworkTransportEnum.ETHER.value:
            data_pattern = r'>\s+([a-zA-Z0-9:]{1,}),\s+ethertype\s+PTP[\s|\S]*?length\s+\d+:\s+'
        elif network_transport == PtpNetworkTransportEnum.UDP_IPV6.value:
            data_pattern = r'>\s+([a-zA-Z0-9:]{1,})[\s|\S]*?ethertype\s+IPv6[\s|\S]*?PTPv2'
        data_list = re.findall(data_pattern, tcpdump_text)
        # print(f'data_list = {data_list}')
        if not data_list:
            err_msg = '不存在PTPv2 报文, 不符合预期'
            return check_flag, err_msg
        log.info(f'存在PTPv2报文')
        # print(f'data_list = {data_list}')
        break_flag = False
        if network_transport == PtpNetworkTransportEnum.UDP_IPV4.value:
            for data_values in data_list:
                src_mac, dst_mac = data_values
                if data_values == dst_mac:
                    continue
                first_ip_part = int(dst_mac.split('.')[0])
                if 224 <= first_ip_part <= 239:
                    log.info(f'dst_mac ={dst_mac} 属于组播地址, 符合预期')
                else:
                    log.error(f'dst_mac ={dst_mac} 不属于组播地址, 不符合预期')
                    break_flag = True
                    break
        elif network_transport == PtpNetworkTransportEnum.UDP_IPV6.value:
            for data_values in data_list:
                if data_values == dst_mac:
                    continue
                if data_values.startswith('33:33:'):
                    log.info(f'dst_mac ={data_values} 属于组播地址, 符合预期')
                else:
                    log.info(f'dst_mac ={data_values} 不属于组播地址, 不符合预期')
                    break_flag = True
                    break
        elif network_transport == PtpNetworkTransportEnum.ETHER.value:
            for data_values in data_list:
                if data_values == dst_mac:
                    continue
                if '01:1b:19:00:00:00' == data_values:
                    log.debug(f'dst_ip ={data_values} 属于组播地址, 符合预期')
                else:
                    log.error(f'dst_ip ={data_values} 不属于组播地址, 符合预期')
                    break_flag = True
                    break
        if not break_flag:
            check_flag = True
        return check_flag, err_msg


class Phc2SysUtils(object):
    @classmethod
    def exec_phc2sys(cls, slave_clock: str = 'CLOCK_REALTIME',
                     exec_time: int = 60,
                     master_clock: str = 'CLOCK_REALTIME',
                     cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> tuple:
        """
        author: shanshan.du
        date: 2024.09.05 11:49:30
        description: 将PTP硬件时钟同步系统时间
        :param slave_clock: 从时钟
        :param exec_time: 命令执行的时间
        :param master_clock: 主时钟
        :param cmd_execute_address:执行命令方向
        :return: 返回 rtn_code, rtn_info, rtn_err
        """
        phc2sys_cmd = f'timeout {exec_time} phc2sys -s {slave_clock} -w -m -c {master_clock}'
        rtn_code, rtn_info, rtn_err = CommandOperation. \
            execute_command_with_error(cmd=phc2sys_cmd, cmd_execute_address=cmd_execute_address)
        return rtn_code, rtn_info, rtn_err
