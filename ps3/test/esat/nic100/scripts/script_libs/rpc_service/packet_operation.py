import string
import struct
import time
import socket
import random
import platform
import add_syspath
from scripts.script_libs.file_operation import FileOperation
from scripts.script_libs.enums import PacketType, TransportProtocal, ARPOpcode, \
    CmdExecuteAdressEnum, RtnStatusEnum, IPV6ExtensionHeaderEnum, FrameType
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse
from scapy.layers.l2 import Ether
from scripts.script_libs import constants, log
from scripts.script_libs.ifconfig import IfConfig
from scripts.script_libs.script_base import SxeThread
from scapy.layers import sctp, ipsec, l2, inet6, inet
from scapy.layers.l2 import SNAP, Dot3, Ether, Dot1Q, FCSField, ARP, LLC
from scapy.layers import dhcp
from scapy.all import *
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.command_operation import CommandOperation
from multiprocessing.connection import Client
from scripts.script_libs.rpc_service.rpc_client import RPCProxy
from scripts.script_libs.iperf_operation import IperfOperation
from scripts.script_libs.script_base import ScriptBase

# history
# 20230824 hejf merge liuxd code


class PacketOperation(object):

    @classmethod
    def structure_socket_packet(cls, length_of_string: int):
        """
        author: wei.yuan
        date:   2022-07-28
        description: 构造网络包报文
        """
        # random_string = "".join(random.choice(string.ascii_letters + string.digits
        #                                      ) for _ in range(length_of_string))
        random_string = ""
        string_list = ["s", "x", "e"]
        # sxe -> 737865
        for i in range(length_of_string):
            random_string += string_list[i % 3]
        return random_string

    @classmethod
    def structure_icmp_packet(cls, src: str, dst: str, ttl: int = 64, flags: int = 0, data=None):

        if data:
            pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / inet.IP(ihl=15, dst=dst, ttl=ttl,
                                                           flags=flags) / inet.ICMP() / f'{data}'
        else:
            pkt = inet.IP(ihl=15, dst=dst, ttl=ttl, flags=flags) / inet.ICMP()

        pkt.display()
        hexdump(pkt)
        c = send(pkt, return_packets=True)
        # c = sendp(pkt,)
        # c.show()

    @classmethod
    def structure_tcp_packet(cls, src: str, dst: str, ttl: int = 64, flags: int = 0, data=None):

        if data:
            pkt = inet.IP(ihl=15, dst=dst, ttl=ttl, flags=flags) / inet.TCP(dport=8080, sport=8800) / f'{data}'
        else:
            pkt = inet.IP(ihl=15, dst=dst, ttl=ttl, flags=flags) / inet.TCP(dport=27751, sport=30575)
        pkt.show()
        pkt.display()
        hexdump(pkt)
        # c = sendp(pkt, return_packets=True, iface="ens1f0")


def structure_ethernet_ii_packet(src: str, dst: str, ether_type: int = ETHER_TYPES.IPv4, data: str = ''):
    """
    author:      xianda.liu
    date:        2022-08-05
    description: 构造ethernet II帧
    :param src:  发端mac地址
    :param dst:  收端mac地址
    :param ether_type: ethertype, 默认取值0x0800(IPv4)
                 常用的ethertype: IPv6: 0x86DD  802.3: 0x0004
    :param data: 数据段
    :return:
    """
    pkt = Ether(src=src, dst=dst, type=ether_type) / data
    return pkt


class EtherFrame(object):
    """
    以太帧类型构造，构造帧类型为：以太帧，vlan帧
    """

    def __init__(self, ether_dict: dict, ):

        self.src_mac = ether_dict["src_mac"]
        self.dst_mac = ether_dict["dst_mac"]
        self.ether_type = ether_dict["ether_type"]
        self.prio = ether_dict["prio"]
        self.cfi_id = ether_dict["cfi_id"]
        self.vlan = ether_dict["vlan"]
        self.ether_pkt = None
        self.length = ether_dict["len_802_3"]
        self.ether_header_length = 0

    def struct_ether_packet(self):
        """
        author: wei.yuan1
        date:2022.09.06
        description:构造以太帧内容
        """
        self.ether_pkt = Ether(src=self.src_mac, dst=self.dst_mac, type=self.ether_type)
        self.ether_header_length = 18
        return self.ether_pkt, self.ether_header_length

    def struct_ethernet_vlan_packet(self):
        """
        author:                             xianda.liu
        date:                               2022-08-05
        description:                        构造802.1Q带有vlan tag的帧
        :return:
        """
        self.ether_pkt = Ether(
            src=self.src_mac,
            dst=self.dst_mac) / Dot1Q(
            prio=self.prio,
            id=self.cfi_id,
            vlan=self.vlan,
            type=self.ether_type
        )
        if self.ether_header_length is None:
            self.ether_header_length = 20
        else:
            self.ether_header_length = 22
        return self.ether_pkt, self.ether_header_length

    def struct_ethernet_llc_packet(self):
        """
        author: wei.yuan1
        date: 2022.09.13
        description: 构造LLC帧
        """

        # flag = [True if random.choice([True, False]) else False][0]
        # 第一种报文格式，有异常，暂时先使用第二种。第一种格式后续需要调试好。
        flag = False
        if flag:
            self.ether_pkt = Ether(src=self.src_mac, dst=self.dst_mac) / LLC(dsap=0x06, ssap=0x06, ctrl=3)
            self.ether_header_length = 21
        else:
            self.ether_pkt = Dot3(src=self.src_mac, dst=self.dst_mac, len=self.length) / LLC(
                dsap=0x00, ssap=0x00, ctrl=3)
            self.ether_header_length = 21
        return self.ether_pkt, self.ether_header_length

    def struct_ether_snap_packet(self):
        """
        author: wei.yuan1
        date: 2022.09.13
        description: 构造snap数据帧
        # TODO 存在疑问，SNAP字段中的OUI是否可以取值
        """
        oui_code = int("".join(self.src_mac.split(":")[:3]), 16)

        self.ether_pkt = Dot3(src=self.src_mac, dst=self.dst_mac, len=self.length) / LLC(
            dsap=0xaa, ssap=0xaa, ctrl=3) / SNAP(
            OUI=oui_code,
            # OUI="E4:B6:33",
            code=self.ether_type)
        self.ether_header_length = 26
        return self.ether_pkt, self.ether_header_length


class NetworkPacket:
    """
    网络层报文构造，构造报文类型为IP层的报文，包括ARP报文，IP报文，IPV6报文，icmp类型的报文
    """

    def __init__(self, ip_dict: dict):
        """
        """
        self.source_addr = ip_dict["source_addr"]
        self.dest_addr = ip_dict["dest_addr"]
        # 初始化ip协议为ipv4
        self.version = ip_dict["version"]
        self.ihl = ip_dict["ihl"]
        self.tos = ip_dict["tos"]
        self.len = ip_dict["ip_len"]
        # 默认不分片
        self.flags = ip_dict["ip_flags"]
        self.frag = ip_dict["frag"]
        # 默认最多可经过的路由数
        self.ttl = ip_dict["ttl"]
        self.proto = ip_dict["proto"]
        # 默认校验位
        self.checksum = ip_dict["checksum"]
        # self.options = ip_dict["ip_options"]
        """
        操作类型:
          1 ARP请求
          2 ARP应答
          3 RARP请求
          4 RARP应答
        """
        self.opcode = ip_dict["opcode"]
        # 表示发送方要映射的协议地址类型。对于IP地址，该值为0x0800。
        self.ptype = ip_dict["ptype"]
        # 表示硬件地址的类型。对于以太网，该类型的值为“1”。
        self.hwtype = ip_dict["hwtype"]
        self.hwlen = ip_dict["hwlen"]
        self.plen = ip_dict["plen"]
        self.protocol_len = ip_dict["protocol_len"]
        self.src_mac = ip_dict["src_mac"]
        self.dst_mac = ip_dict["dst_mac"]
        # 流量类别。该字段及其功能类似于IPv4的业务类型字段。
        # 该字段以区分业务编码点（DSCP）标记一个IPv6数据包，以此指明数据包应当如何处理。
        self.tc = ip_dict["tc"]
        # 流标签。该字段用来标记IP数据包的一个流，当前的标准中没有定义如何管理和处理流标签的细节。
        self.fl = ip_dict["fl"]
        # 下一报头，该字段指明了跟随在IPv6基本报头后的扩展报头的信息类型。
        self.nh = ip_dict["nh"]
        # 跳数限制，该字段定义了IPv6数据包所能经过的最大跳数，这个字段和IPv4中的TTL字段非常相似。
        self.hlim = ip_dict["hlim"]
        self.extension_header = ip_dict["extension_header"]
        self.network_header = None
        self.ipv6_extension_headers = None
        # IPV6扩展报头的协议类型
        self.extension_header_nh = self.nh
        self.network_header_length = 0

    def struct_arp_packet(self):
        """
        author: wei.yuan1
        date: 2022.09.02
        description: 构造ARP的L3层数据包
        :return 返回的报文长度，arp报文
        """
        # 根据操作类型决定ARP报文中hwdst字段的值
        hwdst_str = self.dst_mac
        if self.opcode == 1:
            hwdst_str = "00:00:00:00:00:00"
        self.network_header = ARP(hwsrc=self.src_mac, psrc=self.source_addr,
                                  hwdst=hwdst_str, pdst=self.dest_addr,
                                  hwlen=self.hwlen, op=self.opcode, plen=self.protocol_len)

        self.network_header_length = 28
        return self.network_header, self.network_header_length

    def struct_ip_packet(self):
        if self.proto:
            self.network_header = inet.IP(
                version=PacketType.PACKET_IPV4.value,
                ihl=self.ihl,
                tos=self.tos,
                len=self.len,
                flags=self.flags,
                frag=self.frag,
                ttl=self.ttl,
                chksum=self.checksum,
                src=self.source_addr,
                dst=self.dest_addr,
                proto=self.proto
                # options=self.options
            )
        else:
            self.network_header = inet.IP(
                version=PacketType.PACKET_IPV4.value,
                ihl=self.ihl,
                tos=self.tos,
                len=self.len,
                flags=self.flags,
                frag=self.frag,
                ttl=self.ttl,
                chksum=self.checksum,
                src=self.source_addr,
                dst=self.dest_addr,
                # options=self.options
            )
        self.network_header_length = 20
        return self.network_header, self.network_header_length

    def struct_icmp_packet(self):
        ip_pkt = self.struct_ip_packet()[0]
        self.network_header = ip_pkt / inet.ICMP()
        self.network_header_length = 28
        return self.network_header, self.network_header_length

    def struct_ipv6_extension_header(self):
        if self.extension_header == IPV6ExtensionHeaderEnum.Header_Hop_by_Hop.value:
            self.nh = 0
            self.ipv6_extension_headers = inet6.IPv6ExtHdrHopByHop()
        elif self.extension_header == IPV6ExtensionHeaderEnum.Header_Destination.value:
            self.nh = 60
            self.ipv6_extension_headers = inet6.IPv6ExtHdrDestOpt()
        elif self.extension_header == IPV6ExtensionHeaderEnum.Header_Routing.value:
            self.nh = 43
            self.ipv6_extension_headers = inet6.IPv6ExtHdrRouting()
        else:
            pass

    def struct_inet6_packet(self):
        self.network_header = inet6.IPv6(version=self.version, tc=self.tc,
                                         fl=self.fl, plen=self.plen, nh=self.nh,
                                         hlim=self.hlim, src=self.source_addr,
                                         dst=self.dest_addr
                                         )
        self.network_header_length = 40
        return self.network_header, self.network_header_length

    def struct_icmp_inet6_packet(self):
        ip_pkt = self.struct_inet6_packet()[0]
        self.network_header = ip_pkt / inet6.ICMPv6EchoRequest()
        self.network_header_length = 40 + 8
        return self.network_header, self.network_header_length
        # inet6.IPv6ExtHdrHopByHop


class TransportPacket:
    """
    传输层报文构造，构造报文类型为TCP类型报文，UDP类型报文，SCTP类型报文
    """

    def __init__(self, tranport_dict: dict = None):
        self.tcp_packet = None
        self.udp_packet = None
        self.sctp_packet = None
        # 源端口，标识由哪个应用程序发送
        self.sport = tranport_dict["sport"]
        # 目标端口，标识由哪个应用程序接收
        self.dport = tranport_dict["dport"]
        # UDP首部加上UDP数据的字节数，最小为8。
        self.len = tranport_dict["len"]
        # 如果是tcp报文，则校验位长度为16bit,如果为udp报文，则为2bit
        self.chksum = tranport_dict["chksum"]
        # 数据偏移，即首部长度，指出TCP报文段的数据起始处距离TCP报文段的起始处有多远，
        # 以32比特（4字节）为计算单位。最多有60字节的首部，若无选项字段，正常为20字节。
        self.dataofs = tranport_dict["dataofs"]
        # 窗口：TCP的流量控制，窗口起始于确认序号字段指明的值，
        # 这个值是接收端期望接收的字节数。窗口最大为65535字节
        self.windows = tranport_dict["windows"]
        # 紧急指针，只有当URG标志置1时紧急指针才有效。
        # TCP的紧急方式是发送端向另一端发送紧急数据的一种方式。
        # 紧急指针指出在本报文段中紧急数据共有多少个字节（紧急数据放在本报文段数据的最前面)。
        self.urgptr = tranport_dict["urgptr"]

        self.transport_header_length = 0
        self.flags = tranport_dict["flags"]

    def struct_transport_tcp_package(self):
        self.tcp_packet = inet.TCP(sport=self.sport, dport=self.dport, dataofs=self.dataofs,
                                   urgptr=self.urgptr, window=self.windows, flags=self.flags
                                   )
        self.transport_header_length = 19
        return self.tcp_packet, self.transport_header_length

    def struct_transport_udp_package(self):
        self.udp_packet = inet.UDP(sport=self.sport, dport=self.dport, len=self.len, chksum=self.chksum)
        self.transport_header_length = 8
        return self.udp_packet, self.transport_header_length

    def struct_tansport_sctp_packeage(self):
        # add by wangwt
        sctp_verification_tag = 0x12345678
        sctp_header = Raw(load=b"\x00\x00\x00\x00"  # 假设这是 SCTP 的一个简化版头部
                               + struct.pack("!I", sctp_verification_tag))  # 使用网络字节序打包验证标签
        sctp_udp_layer = inet.UDP(sport=self.sport, dport=self.dport)  # 使用 UDP 作为占位符（这不是正确的做法）
        self.sctp_packet = sctp_udp_layer / sctp_header
        return self.sctp_packet, self.transport_header_length


class StructNetworkDataPackage:

    def __init__(self, src_nic_name, dst_nic_name, network_packet_type: str = None, data_len: int = 55,
                 src_ip: str = None, dst_ip: str = None, src_mac: str = None, dst_mac: str = None, **kwargs):
        """
        author: wei.yuan1
        date: 2022.09.06
        description: 初始化方法
        :param data_len: 报文长度
        :param network_packet_type:要构造的网络包的类型,如果要构造以太帧的字节长度为12字节或者14字节，需要设置network_packet_type
        为None或者不传
        :param src_nic_name: 发端的网卡名称
        :param dst_nic_name: 收端的网卡名称
        change: 新增frame_type字段，内容为增加帧类型；如果帧为snap或者为llc类型，则会跳转到
        """
        self.data_len = data_len
        self.src_nic_name = src_nic_name
        self.dst_nic_name = dst_nic_name
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.src_mac = src_mac
        self.dst_mac = dst_mac
        self.ether_header_length = 0
        self.network_packet_type = network_packet_type
        self.network_packet_header_length = 0
        self.transport_packet_header_length = 0
        self.package_dict = {
            # ether层的帧头
            "src_mac": None, "dst_mac": None, "ether_type": 0,
            "prio": 0, "cfi_id": 0,
            "vlan": None, "frame_type": None,
            # 802.3长度字段
            "len_802_3": None,
            # ip层的报头字段
            "version": PacketType.PACKET_IPV4.value, "source_addr": None, "dest_addr": None,
            "ihl": 5, "ip_len": None, "tos": 0x0, "id": 1, "ip_flags": 2, "frag": 0, "ttl": 64,
            "checksum": None, "proto": None,
            # ipv6头字段
            "tc": 0, "fl": 0, "plen": 4, "nh": 58, "hlim": 64,
            "extension_header": IPV6ExtensionHeaderEnum.Header_Hop_by_Hop.value,
            # arp字段
            "opcode": ARPOpcode.ARP_QUEST.value,
            "ptype": "0x800", "hwtype": "1", "hwlen": 6, "protocol_len": 4,
            # 传输层的包头字段
            "sport": 8889, "dport": 8889, "len": None, "chksum": None, "seq": None, "windows": 8192,
            "dataofs": None, "urgptr": 0, "window": 8192, "flags": 0x2
        }
        for key in kwargs.keys():
            if key in self.package_dict.keys():
                self.package_dict[key] = kwargs.get(key)
            else:
                raise Exception("要修改的键值对不在此字典内,请确认修改")
        # 将以太帧的ether_type填充到字典中
        self.fix_dict_ether_type()
        # 将网卡的信息填充到字典中
        self.fix_dict_nic_information()
        # 修改网卡的vlan帧
        self.fix_dict_ether_vlan()
        if not self.package_dict["len_802_3"]:
            self.package_dict["len_802_3"] = self.data_len - 14 - 4
        for key in kwargs.keys():
            if key in self.package_dict.keys():
                self.package_dict[key] = kwargs.get(key)
            else:
                raise Exception("要修改的键值对不在此字典内,请确认修改")
        log.info("==>self.package_dict:\n{}".format(self.package_dict))

    def fix_dict_nic_information(self):
        """
        author: wei.yuan1
        date:2022.09.06
        description: 将网卡的mac地址，ip地址填充到字典中
        """
        # 将源mac地址，目标mac地址，源IP地址，目标IP地址填充到package_dict字典中
        # 不传入mac地址，默认选择待测设备的mac地址；否则，使用传入值
        if not self.src_mac:
            self.src_mac = IfConfig.get_device_mac_addr(self.src_nic_name,
                                                        cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
        if not self.dst_mac:
            self.dst_mac = IfConfig.get_device_mac_addr(self.dst_nic_name,
                                                        cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        # 判断IP的报文version是否为IPV4或者是IPV6,取发端的ip和收端的IP地址
        if self.package_dict["version"] == PacketType.PACKET_IPV6.value:
            if not self.dst_ip:
                self.dst_ip = IfConfig.get_device_ipv6_addr(self.dst_nic_name,
                                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            if not self.src_ip:
                self.src_ip = IfConfig.get_device_ipv6_addr(self.src_nic_name,
                                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
        else:
            if not self.dst_ip:
                self.dst_ip = IfConfig.get_device_ipv4_addr(self.dst_nic_name,
                                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
            if not self.src_ip:
                self.src_ip = IfConfig.get_device_ipv4_addr(self.src_nic_name,
                                                            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
        self.package_dict["src_mac"] = self.src_mac
        self.package_dict["dst_mac"] = self.dst_mac
        self.package_dict["source_addr"] = self.src_ip
        self.package_dict["dest_addr"] = self.dst_ip
        if (self.package_dict["version"] == TransportProtocal.TRANSPORT_ARP.value or
                self.network_packet_type == TransportProtocal.TRANSPORT_ARP.value):
            self.package_dict["dst_mac"] = "ff:ff:ff:ff:ff:ff"

    def fix_dict_ether_type(self):
        """
        author: wei.yuan1
        date: 2022.09.06
        description:修改网卡的ether_type
        """
        log.info("ETH_P_IP:{}".format(hex(ETH_P_IP)))
        if self.network_packet_type:
            if self.network_packet_type == TransportProtocal.TRANSPORT_ARP.value:
                self.package_dict["ether_type"] = ETH_P_ARP
            else:
                if self.package_dict["version"] == PacketType.PACKET_IPV4.value:
                    self.package_dict["ether_type"] = ETH_P_IP

                elif self.package_dict["version"] == PacketType.PACKET_IPV6.value:
                    self.package_dict["ether_type"] = ETH_P_IPV6
                else:
                    pass
        else:
            self.package_dict["ether_type"] = 0xFFFF

    def fix_dict_ether_vlan(self):
        """
        author: wei.yuan1
        date: 2022.09.06
        description: 以太帧的构造
        """
        src_nic_path = "/sys/devices/virtual/net/" + self.src_nic_name
        src_exist_flag = FileOperation.file_path_exists(path=src_nic_path, path_flag=True,
                                                        ip=CommandOperation.server_ip)
        dst_nic_path = "/sys/devices/virtual/net/" + self.dst_nic_name
        dst_exist_flag = FileOperation.file_path_exists(path=dst_nic_path, path_flag=True,
                                                        ip=CommandOperation.client_ip)

        if src_exist_flag == RtnStatusEnum.SUCCESS.value and dst_exist_flag == RtnStatusEnum.SUCCESS.value:
            self.package_dict["vlan"] = self.src_nic_name.split(".")[1]

    def struct_ether_frame(self):
        """
        author: wei.yuan1
        date: 2022.09.06
        description: 以太帧的构造
        :return ether_pkt: 以太帧的报头
        """
        ether_frame = EtherFrame(ether_dict=self.package_dict)

        if self.package_dict["vlan"] is not None:
            ether_pkt, self.ether_header_length = ether_frame.struct_ethernet_vlan_packet()
        else:
            if self.package_dict["frame_type"] == TransportProtocal.ETHER_SNAP.value:
                ether_pkt, self.ether_header_length = ether_frame.struct_ether_snap_packet()
            elif self.package_dict["frame_type"] == TransportProtocal.ETHER_LLC.value:
                ether_pkt, self.ether_header_length = ether_frame.struct_ethernet_llc_packet()
            else:
                ether_pkt, self.ether_header_length = ether_frame.struct_ether_packet()
        return ether_pkt

    def struct_network_packet(self):
        """
        author: wei.yuan1
        date: 2022.09.06
        description: 网络层数据包的构造
        """
        network_object = NetworkPacket(ip_dict=self.package_dict)
        print('self.network_packet_type: ', self.network_packet_type)
        if self.network_packet_type in [TransportProtocal.TRANSPORT_ICMP.value,
                                        TransportProtocal.TRANSPORT_ICMPV6.value]:
            self.package_dict["proto"] = 1
            if self.package_dict["version"] == PacketType.PACKET_IPV4.value:
                network_pkt, self.network_packet_header_length = network_object.struct_icmp_packet()
            else:
                network_pkt, self.network_packet_header_length = network_object.struct_icmp_inet6_packet()

        elif self.network_packet_type == TransportProtocal.TRANSPORT_ARP.value:
            network_pkt, self.network_packet_header_length = network_object.struct_arp_packet()
        else:
            if self.package_dict["version"] == PacketType.PACKET_IPV4.value:
                network_pkt, self.network_packet_header_length = network_object.struct_ip_packet()
            else:
                network_pkt, self.network_packet_header_length = network_object.struct_inet6_packet()
        return network_pkt

    def struct_transport_packet(self):
        """
        author: we.yuan1
        date: 2022.09.06
        description: 传输层数据包的构造
        """
        transport_pkt = None
        transport_object = TransportPacket(tranport_dict=self.package_dict)
        if self.network_packet_type == TransportProtocal.TRANSPORT_TCP.value:
            transport_pkt, self.transport_packet_header_length = transport_object.struct_transport_tcp_package()
        elif self.network_packet_type == TransportProtocal.TRANSPORT_SCTP.value:
            transport_pkt, self.transport_packet_header_length = transport_object.struct_tansport_sctp_packeage()
        elif self.network_packet_type == TransportProtocal.TRANSPORT_UDP.value:
            self.package_dict["len"] = self.data_len - self.network_packet_header_length
            transport_pkt, self.transport_packet_header_length = transport_object.struct_transport_udp_package()
        # add by wangwt 2024/02/29 [start]
        elif self.network_packet_type == TransportProtocal.TRANSPORT_TCP6.value:
            transport_pkt, self.transport_packet_header_length = transport_object.struct_transport_tcp_package()
        # add by wangwt 2024/02/29 [end]
        else:
            pass
        return transport_pkt

    def struct_package_header(self):
        packages_header = None
        if self.data_len < 12:
            raise ValueError("报文过短，请重新输入")
        if self.network_packet_type is None and 12 <= self.data_len <= 14:
            # 此分支用于构造14字节报文
            packages_header = self.struct_ether_frame()
        elif self.network_packet_type is None and self.data_len > 14:
            # 此分支用于构造llc和snap报文，后面直接跟数据
            packages_header = self.struct_ether_frame()
        # add by wangwt 2024/02/27 [start]
        elif self.network_packet_type is TransportProtocal.ETHER_II.value and self.package_dict['version'] is None:
            # 构造EtherII的包
            packages_header = self.struct_ether_frame()
        # add by wangwt [end]
        else:
            ether_frame_header = self.struct_ether_frame()
            # ipv4头中Total Length字段值(ip_len)包括ipv4头的长度，ipv6头中Payload length字段值(plen)不包括ipv6头本身
            # 14表示L2头长度
            # 40表示ipv6头长度
            self.package_dict["ip_len"] = self.data_len - self.ether_header_length
            self.package_dict["plen"] = self.data_len - self.ether_header_length - 40

            network_pkt_header = self.struct_network_packet()
            network_header = ether_frame_header / network_pkt_header
            packages_header = network_header

            if self.network_packet_type in [TransportProtocal.TRANSPORT_TCP.value,
                                            TransportProtocal.TRANSPORT_UDP.value,
                                            TransportProtocal.TRANSPORT_SCTP.value,
                                            TransportProtocal.TRANSPORT_TCP6.value,
                                            TransportProtocal.TRANSPORT_UDP6.value  # add by wangwt
                                            ]:
                packages_header = network_header / self.struct_transport_packet()

        temp = (self.ether_header_length + self.network_packet_header_length +
                self.transport_packet_header_length)
        network_packet_data_length = self.data_len - temp
        # 这里无需判断，数据段为负值时不会拼接
        # if network_packet_data_length < 0:
        #     raise Exception(ValueError)
        return packages_header, network_packet_data_length


def parse_data_packet(parse_message_file: str, packet_type: str):
    """
    author: wei,yuan1
    date: 2022.09.09
    description:报文解析
    :return 返回报文解析的字典,和报文中的报文的个数
    """
    packet_num = 0
    total_packet_dict = {}
    exist_flag = RtnStatusEnum.FAIL.value
    message_number = 0
    total_packet_dict = {}
    try:
        filter_data_packet = rdpcap(filename=parse_message_file)
        # 获取在报文文件中的报文的个数
        message_number = len(filter_data_packet)
        # 如果抓取到的报文的内容为空，则返回失败，报bug
        log.info("报文文件{}中的报文的个数:{}".format(parse_message_file, message_number))
        try:
            if message_number != 0:
                exist_flag = RtnStatusEnum.SUCCESS.value
        except Exception as e:
            return exist_flag
        for filter_data in filter_data_packet:
            message_data_dict = {
                "Ether_dst": filter_data.sprintf("%Ether.dst%"),
                "Ether_src": filter_data.sprintf("%Ether.src%"),
                "Ether_type": filter_data.sprintf("%Ether.type%"),
                "RAW": filter_data.sprintf("%Raw.load%")
            }
            # message_data_dict["RAW"] = struct.unpack("hhl", message_data_dict["RAW"])
            if packet_type != TransportProtocal.TRANSPORT_ARP.value:
                if message_data_dict["Ether_type"] != "ARP":
                    packet_num += 1
                    total_packet_dict[f"packet{str(packet_num)}"] = message_data_dict
            else:
                if message_data_dict["Ether_type"] == "ARP":
                    packet_num += 1
                    total_packet_dict[f"packet{str(packet_num)}"] = message_data_dict
        return exist_flag, message_number, total_packet_dict
    except FileNotFoundError:
        return exist_flag, message_number, total_packet_dict


def compare_message_information(tx_message: dict, rx_message: dict) -> tuple:
    """
    author: wei.yuan1
    date: 2022.09.09
    description: 对比报文的字典信息，返回值
    :param tx_message: 发送端的报文字典
    :param rx_message: 接收端的报文字典
    """
    return_value_list = []
    for tx_message_dict, rx_message_dict in zip(tx_message, rx_message):
        for tx_keys, rx_keys in zip(tx_message[tx_message_dict], rx_message[rx_message_dict]):
            if tx_message[tx_message_dict][tx_keys] == rx_message[rx_message_dict][rx_keys]:
                return_value_list.append(RtnStatusEnum.SUCCESS.value)
                log.info(f"Tx {tx_keys}:{tx_message[tx_message_dict][tx_keys]} =="
                         f" Rx {rx_keys}:{rx_message[rx_message_dict][rx_keys]}")
            # 测不足64字节时，网卡会自动数据段补0，如果tx为??， rx为'\x00\x00..'，认为相同
            elif (tx_keys == 'RAW' and
                  rx_message[rx_message_dict][rx_keys].replace(b'\\x00'.decode(), '').replace('\'', '').replace('b', '') ==
                  tx_message[tx_message_dict][tx_keys].replace(b'??'.decode(), '').replace('b', '')):
                return_value_list.append(RtnStatusEnum.SUCCESS.value)
                log.info("Rx RAW == Tx RAW")
            else:
                log.error("Tx[{},{}]:{}".format(tx_message_dict, tx_keys, tx_message[tx_message_dict][tx_keys]))
                log.error("Rx[{},{}]:{}".format(rx_message_dict, rx_keys, rx_message[rx_message_dict][rx_keys]))
                return_value_list.append(RtnStatusEnum.FAIL.value)
    if len(set(return_value_list)) != 1:
        return RtnStatusEnum.FAIL.value, rx_message
    else:
        return RtnStatusEnum.SUCCESS.value, rx_message


class PacketOperationWithCheck(object):

    def __init__(self, time_out, listen_proto_type, packet_header, data_len, transport_layer, tcpdump_enable=True,
                 ether_src_mac: str = None, ether_dst_mac: str = None, caller_class=ScriptBase,
                 checksum_flag: bool = True, count: int = 1, target_port: int = 0,
                 rpc_server_ip: str = '', rpc_client_ip: str = '', **kwargs):
        """
        入参
        :param time_out: 抓包超时时间
        :param listen_proto_type:  抓包/发包的类型
        :param packet_header: 包头
        :param data_len: 数据段长度
        :param transport_layer: 发包所在层数， 取值2或3
        :param tcpdump_enable: 是否启用tcpdump进行抓包，据说启动tcpdump会自动开启网卡混杂模式。默认True,此开关只影响收端
        :param ether_dst_mac: 收包侧的mac地址
        :param ether_src_mac: 发包侧的mac地址
        :param caller_class: 调用基类
        :param checksum_flag: 默认true，是否使用正确checksum
        """
        self.count = count
        self.ether_src_mac = ether_src_mac
        self.ether_dst_mac = ether_dst_mac
        self.time_out = time_out
        self.listen_proto_type = listen_proto_type
        self.packet_header = packet_header
        self.data_len = data_len
        self.transport_layer = transport_layer
        self.server_ip = rpc_server_ip if rpc_server_ip else CommandOperation.server_ip
        self.client_ip = rpc_client_ip if rpc_client_ip else CommandOperation.client_ip
        self.device_dict = {}
        if caller_class.test_port:
            self.test_port = caller_class.test_port
        else:
            self.test_port = 22

        self.device_dict["client_device_ip"] = caller_class.test_device_info_list[target_port]["client_device_ip"]
        self.device_dict["server_device_ip"] = caller_class.test_device_info_list[target_port]["server_device_ip"]
        self.device_dict["client_device_mac"] = caller_class.test_device_info_list[target_port]["client_device_mac"]
        self.device_dict["server_device_mac"] = caller_class.test_device_info_list[target_port]["server_device_mac"]
        self.device_dict["client_device_name"] = caller_class.test_device_info_list[target_port]["client_device_name"]
        self.device_dict["server_device_name"] = caller_class.test_device_info_list[target_port]["server_device_name"]
        self.device_dict["client_device_ipv6"] = caller_class.test_device_info_list[target_port]["client_device_ipv6"]
        self.device_dict["server_device_ipv6"] = caller_class.test_device_info_list[target_port]["server_device_ipv6"]

        self.tcpdump_enable = tcpdump_enable
        self.checksum_flag = checksum_flag
        if self.ether_dst_mac is None and self.ether_src_mac is None:
            self.tcpdump_filter_dict = {}
        elif self.ether_dst_mac is not None and self.ether_src_mac is None:
            self.tcpdump_filter_dict = {"ether src host": self.ether_src_mac}
        elif self.ether_dst_mac is None and self.ether_src_mac is not None:
            self.tcpdump_filter_dict = {"ether dst host": self.ether_dst_mac}
        else:
            self.tcpdump_filter_dict = {"ether src host": self.ether_src_mac, "ether dst host": self.ether_dst_mac}

        if kwargs is not None:
            self.tcpdump_filter_dict.update(kwargs)
        else:
            self.tcpdump_filter_dict = {}

    def packet_test_with_check(self, start_mode: str = ""):
        """
        带收发校验的数据报测试
        start_mode: 指定启动模式，client为只启动client端，server为只启动server端，其他为都启动
        :return:
        """
        server_os, client_os = CommonOperation.get_nic_os()
        vm, rpc_port = CommonOperation.get_node_info_from_path()
        CommonOperation.set_rpc_port(int(rpc_port))
        server_vm_path = "{}{}".format(CommonOperation.get_root_path(server_os), vm)
        client_vm_path = "{}{}".format(CommonOperation.get_root_path(client_os), vm)
        log.info("start_mode:{}".format(start_mode))
        if start_mode == 'server':
            # 创建远程拉起server端的线程
            server_service = SxeThread(self.server_run_service)
            server_service.start()
            time.sleep(3)
            # 创建向client端和server端进行业务程序的线程
            server_listener = Client((self.server_ip, constants.RPC_PORT))
            server_proxy = RPCProxy(server_listener).get_proxy()
            scapy_service = SxeThread(self.scapy_transport_packet, server_proxy=server_proxy,
                                      client_proxy=None)
            scapy_service.setDaemon(True)
            scapy_service.start()
            # 监测server端和client端的scpay_service服务是否还在运行中，如果不在运行中，
            # 则清理掉server_service进程和client_service进程
            while True:
                if not scapy_service.is_alive():
                    if server_os != 'windows':
                        server_command_kill = "ps -ef | grep 'python3 {}/rpc_server.py' ".format(server_vm_path) + \
                                              "| grep -v grep | awk '{print$2}' | xargs kill -9"
                        server_ssh_username = 'root'
                        win_vm_ip = ''
                        host_os_server = 'linux'
                    else:
                        server_command_get_pid = ""
                        server_command_kill = "taskkill -f -t -im python3.exe"
                        server_ssh_username = 'Administrator'
                        if self.server_ip == self.device_dict.get('server_win_vm_ip', 'na'):
                            win_vm_ip = self.server_ip
                            host_os_server = 'windows'
                        else:
                            win_vm_ip = ''
                            host_os_server = 'linux'
                        if server_command_get_pid:
                            _, pid, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                server_command_get_pid, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                ssh_ip=self.server_ip, ssh_port=str(self.test_port), ssh_username=server_ssh_username)
                            server_command_kill = server_command_kill.format(pid)
                    server_proxy.end_socket()
                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                        server_command_kill, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                        ssh_ip=self.server_ip, ssh_port=str(self.test_port), ssh_username=server_ssh_username,
                        host_os_server=host_os_server, win_vm_ip=win_vm_ip)
                    break
                else:
                    time.sleep(1)
                    continue
        elif start_mode == 'client':
            # 创建远程拉起client端的线程
            client_service = SxeThread(self.client_run_service)
            client_service.start()
            time.sleep(6)
            # 创建向client端和server端进行业务程序的线程
            print("self.client_ip:{}, constants.RPC_PORT:{}".format(self.client_ip, constants.RPC_PORT))
            status, res, err = CommandOperation.execute_command_with_error(
                f"netstat -ano|findstr {constants.RPC_PORT}",
                win_vm_ip=self.client_ip, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
            status, res, err = CommandOperation.execute_command_with_error(
                f"netstat -ano|findstr python",
                win_vm_ip=self.client_ip, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
            client_listener = Client((self.client_ip, constants.RPC_PORT))
            client_proxy = RPCProxy(client_listener).get_proxy()
            scapy_service = SxeThread(self.scapy_transport_packet, server_proxy=None,
                                      client_proxy=client_proxy)
            scapy_service.setDaemon(True)
            scapy_service.start()
            # 监测server端和client端的scpay_service服务是否还在运行中，如果不在运行中，
            # 则清理掉server_service进程和client_service进程
            while True:
                if not scapy_service.is_alive():
                    if client_os != 'windows':
                        client_command_kill = "ps -ef | grep 'python3 {}/rpc_server.py'".format(client_vm_path) + \
                                              " | grep -v grep | awk '{print$2}' | xargs kill -9"
                        client_ssh_username = 'root'
                        win_vm_ip = ''
                        host_os_client = 'linux'
                    else:
                        client_command_get_pid = ""
                        client_command_kill = "taskkill -f -t -im python3.exe"
                        client_ssh_username = 'Administrator'
                        if self.client_ip == self.device_dict.get('client_win_vm_ip', 'na'):
                            win_vm_ip = self.client_ip
                            host_os_client = 'windows'
                        else:
                            win_vm_ip = ''
                            host_os_client = 'linux'

                        if client_command_get_pid:
                            _, pid2, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                client_command_get_pid, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                ssh_ip=self.client_ip, ssh_port=str(self.test_port), ssh_username=client_ssh_username)
                            client_command_kill = client_command_kill.format(pid2)
                    client_proxy.end_socket()
                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                        client_command_kill, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                        ssh_ip=self.client_ip, ssh_port=str(self.test_port), ssh_username=client_ssh_username,
                        host_os_client=host_os_client, win_vm_ip=win_vm_ip)
                    break
                else:
                    time.sleep(1)
                    continue
        else:
            # 创建远程拉起client端的线程
            log.info("创建远程拉起client端和server端的rpc_server线程")
            client_service = SxeThread(self.client_run_service)
            # 创建远程拉起server端的线程
            server_service = SxeThread(self.server_run_service)
            server_service.start()
            client_service.start()
            # 低于2s时，listen可能会执行失败
            time.sleep(3)
            # 创建向client端和server端进行业务程序的线程
            log.info("创建向client端和server端进行业务程序的线程")
            rpc_port = CommonOperation.get_rpc_port()
            log.info("listen -> server_ip:{}, port:{}".format(self.server_ip, rpc_port))
            server_listener = Client((self.server_ip, rpc_port))
            server_proxy = RPCProxy(server_listener).get_proxy()

            log.info("listen -> client_ip:{}, port:{}".format(self.client_ip, rpc_port))
            client_listener = Client((self.client_ip, rpc_port))
            client_proxy = RPCProxy(client_listener).get_proxy()

            # 对server端和client端进行异步发包操作
            log.info("对server端和client端进行异步发包操作")
            scapy_service = SxeThread(self.scapy_transport_packet,
                                      server_proxy=server_proxy, client_proxy=client_proxy)
            scapy_service.setDaemon(True)
            scapy_service.start()
            # 监测server端和client端的scpay_service服务是否还在运行中，如果不在运行中，
            # 则清理掉server_service进程和client_service进程
            while True:
                if not scapy_service.is_alive():
                    if server_os != 'windows':
                        server_command_kill = "ps -ef | grep 'python3 {}/rpc_server.py'".format(server_vm_path) + \
                                              " | grep -v grep | awk '{print$2}' | xargs kill -9"
                        server_ssh_username = 'root'
                        host_os_server = 'linux'
                    else:
                        server_command_get_pid = ""
                        server_command_kill = "taskkill -f -t -im python3.exe"
                        server_ssh_username = 'Administrator'

                        if self.server_ip == self.device_dict.get('server_win_vm_ip', 'na'):
                            host_os_server = 'windows'
                        else:
                            host_os_server = 'linux'

                        if server_command_get_pid:
                            if self.server_ip != CommandOperation.server_ip:
                                win_vm_ip = self.server_ip
                            else:
                                win_vm_ip = None
                            _, pid, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                server_command_get_pid, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                win_vm_ip=win_vm_ip,
                                ssh_ip=self.server_ip, ssh_port=str(self.test_port), ssh_username=server_ssh_username)
                            server_command_kill = server_command_kill.format(pid)

                    if client_os != 'windows':
                        client_command_kill = "ps -ef | grep 'python3 {}/rpc_server.py'".format(client_vm_path) + \
                                              " | grep -v grep | awk '{print$2}' | xargs kill -9"
                        client_ssh_username = 'root'
                        host_os_client = 'linux'
                    else:
                        client_command_get_pid = ""
                        client_command_kill = "taskkill -f -t -im python3.exe"
                        client_ssh_username = 'Administrator'

                        if self.client_ip == self.device_dict.get('client_win_vm_ip', 'na'):

                            host_os_client = 'windows'
                        else:
                            host_os_client = 'linux'

                        if client_command_get_pid:
                            if self.client_ip != CommandOperation.client_ip:
                                win_vm_ip = self.client_ip
                            else:
                                win_vm_ip = None
                            _, pid2, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                                client_command_get_pid, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                                ssh_ip=self.client_ip, ssh_port=str(self.test_port), ssh_username=client_ssh_username,
                                win_vm_ip=win_vm_ip)
                            client_command_kill = client_command_kill.format(pid2)
                    server_proxy.end_socket()
                    client_proxy.end_socket()
                    if self.server_ip != CommandOperation.server_ip:
                        win_vm_ip = self.server_ip
                    else:
                        win_vm_ip = None
                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                        server_command_kill, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                        win_vm_ip=win_vm_ip,
                        ssh_ip=self.server_ip, ssh_port=str(self.test_port), ssh_username=server_ssh_username,
                        host_os_server=host_os_server)
                    if self.client_ip != CommandOperation.client_ip:
                        win_vm_ip = self.client_ip
                    else:
                        win_vm_ip = None
                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                        client_command_kill, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                        win_vm_ip=win_vm_ip,
                        ssh_ip=self.client_ip, ssh_port=str(self.test_port), ssh_username=client_ssh_username,
                        host_os_client=host_os_client)
                    break
                else:
                    time.sleep(1)
                    continue

    def client_run_service(self):
        """
        author: wei.yuan1
        date: 2022.09.01
        description: 在client端拉起rpc_server服务，用于发包和监测抓包
        """
        _, client_os = CommonOperation.get_nic_os()
        if client_os == 'windows':
            ssh_username = "Administrator"
        else:
            ssh_username = 'root'

        # # 检查rpc_port是否被占用，若被占用，+1并检查，直到找到未占用port，作为rpc_port
        vm, _ = CommonOperation.get_node_info_from_path()
        # CommonOperation.set_rpc_port(int(rpc_port))
        # para_port = int(rpc_port)
        # while para_port < int(rpc_port) + 100:
        #     if client_os == 'windows':
        #         cmd = "netstat -ano|findstr '{}'".format(para_port)
        #     else:
        #         cmd = "netstat -tulnp|grep '{}'".format(para_port)
        #     rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
        #         cmd, win_vm_ip=CommonOperation.get_vm_ip(execute_address=CmdExecuteAdressEnum.CLIENT.value),
        #         cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
        #         ssh_ip=CommandOperation.client_ip,
        #         ssh_port=str(CommandLineArgsParse.get_client_port()), ssh_username=ssh_username)
        #     if rtn_outputs:
        #         para_port += 1
        #     else:
        #         log.info("client find available port {}".format(para_port))
        #         CommonOperation.set_rpc_port(para_port)
        #         break

        vm_path = "{}{}".format(CommonOperation.get_root_path(client_os), vm)
        if client_os == 'windows':
            server_command = "python3 {}/rpc_server.py".format(vm_path)
            ssh_username = "Administrator"
        else:
            server_command = "python3 {}/rpc_server.py 2>&1".format(vm_path)
            ssh_username = 'root'

        if self.client_ip != CommandOperation.client_ip:
            win_vm_ip = self.client_ip
        else:
            win_vm_ip = None
        client_rtn_code, client_rtn_outputs, client_rtn_err = CommandOperation.execute_command_with_error(
            server_command, win_vm_ip=win_vm_ip,
            cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
            ssh_ip=self.client_ip,
            ssh_port=str(self.test_port), ssh_username=ssh_username)
        log.info("===>client_run_service, rtn_code:\n{},\nrtn_outputs:\n{},\n".
                 format(client_rtn_code, client_rtn_outputs.replace("..", "")))

    def server_run_service(self):
        """
        author: wei,yuan1
        date: 2022.09.01
        description: 在server端拉起rpc_server服务
        """
        server_os, _ = CommonOperation.get_nic_os()
        if server_os == 'windows':
            ssh_username = "Administrator"
        else:
            ssh_username = 'root'

        # 检查rpc_port是否被占用，若被占用，+1并检查，直到找到未占用port，作为rpc_port
        vm, _ = CommonOperation.get_node_info_from_path()
        # CommonOperation.set_rpc_port(int(rpc_port))
        # para_port = int(rpc_port)
        # while para_port < int(rpc_port) + 100:
        #     if server_os == 'windows':
        #         cmd = "netstat -ano|findstr '{}'".format(para_port)
        #     else:
        #         cmd = "netstat -tulnp|grep '{}'".format(para_port)
        #     vm_name = CommonOperation.get_vm_name(execute_address=CmdExecuteAdressEnum.SERVER.value)
        #     vm_ip = CommonOperation.get_vm_ip(vm_name, execute_address=CmdExecuteAdressEnum.SERVER.value)
        #     rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
        #         cmd, win_vm_ip=vm_ip,
        #         cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
        #         ssh_ip=CommandOperation.server_ip,
        #         ssh_port=str(CommandLineArgsParse.get_server_port()), ssh_username=ssh_username)
        #     if rtn_outputs:
        #         para_port += 1
        #     else:
        #         log.info("server find available port {}".format(para_port))
        #         CommonOperation.set_rpc_port(para_port)
        #         break

        vm_path = "{}{}".format(CommonOperation.get_root_path(server_os), vm)
        if server_os == 'windows':
            server_command = "python3 {}/rpc_server.py".format(vm_path)
        else:
            server_command = "python3 {}/rpc_server.py 2>&1".format(vm_path)

        if self.server_ip != CommandOperation.server_ip:
            win_vm_ip = self.server_ip
        else:
            win_vm_ip = None
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            server_command, win_vm_ip=win_vm_ip,
            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
            ssh_ip=self.server_ip,
            ssh_port=str(CommandLineArgsParse.get_server_port()), ssh_username=ssh_username)
        log.info("===>server_run_service, rtn_code:\n{},\nrtn_outputs:\n{},\n".
                 format(rtn_code, rtn_outputs.replace("..", "")))

    def scapy_transport_packet(self, server_proxy, client_proxy):
        """
        author: wei.yuan
        date: 2022.09.01
        description: 对server端和client端进行异步发包操作
        """
        # global manager
        if client_proxy and not server_proxy:
            client = SxeThread(self.client_send_packet, proxy=client_proxy)
            client.start()
            client.join()
        elif server_proxy and not client_proxy:
            manager = SxeThread(self.server_sniff_packet, proxy=server_proxy)
            manager.start()
            time.sleep(1)
            manager.join()
        else:
            client = SxeThread(self.client_send_packet, proxy=client_proxy)
            manager = SxeThread(self.server_sniff_packet, proxy=server_proxy)
            manager.start()
            time.sleep(1)
            client.start()
            client.join()
            manager.join()

        # if self.tcpdump_enable:
        #     manager = SxeThread(self.server_sniff_packet)
        #     manager.start()
        #     time.sleep(3)
        # client.start()
        # if self.tcpdump_enable:
        #     client.join()
        #     manager.join()

    def server_sniff_packet(self, proxy):
        """
        author: wei.yuan1
        date: 2022.09.01
        description: 在主机侧进行监听，抓包
        """
        # server_listener = Client((self.server_ip, constants.RPC_PORT))
        # proxy = RPCProxy(server_listener).get_proxy()
        if not self.device_dict.get('server_device_name'):
            log.warning(f'注意: 本次Server端抓包未指定网卡子端口')
        server_device_name = self.device_dict.get('server_device_name')
        # TODO 这里缺少对监听的协议类型的枚举值判断？枚举值会影响IP地址的选择
        if type(self.listen_proto_type) == str and 'v6' in self.listen_proto_type.lower():
            if not self.device_dict.get('client_device_ipv6'):
                log.warning(f'注意: 本次抓包基于IPv6地址, 但client端IPv6地址为空')
            server_test_drives_inet = self.device_dict.get('server_device_ipv6')
        elif type(self.listen_proto_type) == str and 'v6' not in self.listen_proto_type.lower():
            if not self.device_dict.get('client_device_ip'):
                log.warning(f'注意: 本次抓包基于IPv4地址, 但client端IPv4地址为空')
            server_test_drives_inet = self.device_dict.get('server_device_ip')
        else:
            log.warning(f"注意：本次抓包未指定监听协议类型, IP地址默认IPv4")
            if not self.device_dict.get('client_device_ip'):
                log.warning(f'注意: 本次抓包默认基于IPv4地址, 但client端IPv4地址为空')
            server_test_drives_inet = self.device_dict.get('server_device_ip')
        if self.tcpdump_enable:
            if self.listen_proto_type is None:
                server_test_drives_inet = None
                filter_packet_num, total_packet = proxy.sniff_packet(
                    iface=server_device_name,
                    dst_ip=server_test_drives_inet,
                    timeout=self.time_out,
                    filter_data_dict=self.tcpdump_filter_dict
                )
            else:
                filter_packet_num, total_packet = proxy.sniff_packet(
                    iface=server_device_name,
                    proto=self.listen_proto_type,
                    dst_ip=server_test_drives_inet,
                    timeout=self.time_out,
                    filter_data_dict=self.tcpdump_filter_dict
                )

    def client_send_packet(self, proxy):
        """
        author: wei.yuan1
        date：2022.09.01
        description:
        """
        # client_sender = Client((self.client_ip, constants.RPC_PORT))
        # proxy = RPCProxy(client_sender).get_proxy()
        if not self.device_dict.get('client_device_name'):
            log.warning(f'注意: 本次client端发包未指定网卡子端口')
        client_device_name = self.device_dict.get('client_device_name')

        if type(self.listen_proto_type) == str and 'v6' in self.listen_proto_type.lower():
            if not self.device_dict.get('client_device_ipv6'):
                log.warning(f'注意: 本次发包基于IPv6地址, 但client端IPv6地址为空')
            if not self.device_dict.get('server_device_ipv6'):
                log.warning(f'注意: 本次发包基于IPv6地址, 但server端IPv6地址为空')
            client_test_drives_inet = self.device_dict.get('client_device_ipv6')
            server_test_drives_inet = self.device_dict.get('server_device_ipv6')
        elif type(self.listen_proto_type) == str and 'v6' not in self.listen_proto_type.lower():
            if not self.device_dict.get('client_device_ip'):
                log.warning(f'注意: 本次抓包基于IPv4地址, 但client端IPv4地址为空')
            if not self.device_dict.get('server_device_ip'):
                log.warning(f'注意: 本次发包基于IPv4地址, 但server端IPv4地址为空')
            client_test_drives_inet = self.device_dict.get('client_device_ip')
            server_test_drives_inet = self.device_dict.get('server_device_ip')
        else:
            log.warning(f"注意：本次抓包未指定监听协议类型, IP地址默认IPv4")
            if not self.device_dict.get('client_device_ip'):
                log.warning(f'注意: 本次抓包默认基于IPv4地址, 但client端IP地址为空')
            if not self.device_dict.get('server_device_ip'):
                log.warning(f'注意: 本次发包基于IPv4地址, 但server端IPv4地址为空')
            client_test_drives_inet = self.device_dict.get('client_device_ip')
            server_test_drives_inet = self.device_dict.get('server_device_ip')
        if self.listen_proto_type is None:
            server_test_drives_inet = None
            client_test_drives_inet = None
        self.packet_header.show()
        log.info(
            "data_len: " + str(self.data_len) + "\n"
            "iface: " + str(client_device_name) + "\n"
            "count: " + str(self.count) + "\n"
            "sniff_dst_ip: " + str(server_test_drives_inet) + "\n"
            "sniff_src_ip: " + str(client_test_drives_inet) + "\n"
            "tcpdump_enable: " + str(self.tcpdump_enable) + "\n"
            "filter_data_dict: " + str(self.tcpdump_filter_dict))
        proxy.multiprocess_trigger(iface=client_device_name,
                                   proto=self.listen_proto_type,
                                   sniff_dst_ip=server_test_drives_inet,
                                   sniff_src_ip=client_test_drives_inet,
                                   packet_header=self.packet_header,
                                   data_len=self.data_len,
                                   timeout=self.time_out,
                                   transport_layer=self.transport_layer,
                                   filter_data_dict=self.tcpdump_filter_dict,
                                   tcpdump_enable=self.tcpdump_enable,
                                   count=self.count,
                                   checksum_flag=self.checksum_flag)

    @staticmethod
    def __download_network_packet_compare(remote_file_path: str, remote_ssh_ip: str, username: str = 'root'):
        """
        author: wei,yuan1
        date: 2022.09.06
        description: 从远端将文件下载到本地
        :param remote_file_path: 远程文件
        :param remote_ssh_ip: 远程的IP地址
        """
        # current_file_path = os.path.abspath(os.path.dirname(__file__))
        # # current_os_name = constants.HOST_OS
        # root_file_path = os.path.dirname(current_file_path)
        # while True:
        #     if "test" == os.path.basename(root_file_path):
        #         sys.path.append(root_file_path)
        #         break
        #     elif root_file_path == "/":
        #         raise ValueError
        #     else:
        #         root_file_path = os.path.dirname(root_file_path)
        #         sys.path.append(root_path)
        # script_path = os.path.join(root_path, "scripts/temp_files")
        # local_file_path = os.path.join(script_path, local_file_path)
        # local_file_path = FileOperation.get_specify_file_location(specify_file=local_file_path)
        # FileOperation.path_exists_for_windows(path=local_file_path, localpath_flag=True)
        # 检测文件在本地是否存在
        # if "windows" in current_os_name:
        #     FileOperation.path_exists_for_windows(path=local_file_path, localpath_flag=True)
        # else:
        #     FileOperation.file_path_exists(path=local_file_path, path_flag=True)

        download_rtn_code = FileOperation.file_path_exists(path=remote_file_path, path_flag=False, ip=remote_ssh_ip,
                                                           username=username)
        download_rtn_code = RtnStatusEnum.SUCCESS.value
        if download_rtn_code != RtnStatusEnum.SUCCESS.value:
            return download_rtn_code, None
        else:
            # 将文件下载到本地
            rtn_file_download_flag = FileOperation.sftp_download_file(
                localfile_path=None,
                remotefile_path=remote_file_path,
                ip=remote_ssh_ip,
                with_error=True,
                username=username
            )
            download_rtn_code = rtn_file_download_flag
            return download_rtn_code

    def network_packet_compare(self, client_network_packet_pcap: str = None, server_network_packet_pcap: str = None):

        """
        author: wei.yuan1
        date: 2022.09.12
        description: 报文比较并返回结果
        :param client_network_packet_pcap: 发端接收到的报文内容
        :param server_network_packet_pcap: 收端接收到的报文内容
        :return 报文比较的返回值，收发端的报文内容
        """
        pcap_file_path_server, pcap_file_path_client = CommonOperation.pcap_file_path()
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        if 'windows' not in host_os_client:
            username_client = 'root'
        else:
            username_client = 'Administrator'

        if 'windows' not in host_os_server:
            username_server = 'root'
        else:
            username_server = 'Administrator'
        rx_message_dict = {}
        tx_message_dict = {}
        rtn_code = RtnStatusEnum.SUCCESS.value
        if client_network_packet_pcap is None:
            client_network_packet_pcap = pcap_file_path_client
            # if 'windows' not in pcap_file_path_client:
            #     client_network_packet_pcap = "/root/client_packet.pcap"
            # else:
            #     client_network_packet_pcap = 'C:\\Users\\Administrator\\client_packet.pcap'
        if server_network_packet_pcap is None:
            server_network_packet_pcap = pcap_file_path_server
            # if 'windows' not in pcap_file_path_server:
            #     server_network_packet_pcap = "/root/server_packet.pcap"
            # else:
            #     server_network_packet_pcap = 'C:\\Users\\Administrator\\server_packet.pcap'
        current_path = os.path.abspath(os.path.dirname(__file__))
        # current_os_name = constants.HOST_OS
        root_path = os.path.dirname(current_path)
        while True:
            if "scripts" == os.path.basename(root_path):
                sys.path.append(root_path)
                break
            elif root_path == "/":
                raise ValueError
            else:
                root_path = os.path.dirname(root_path)
                sys.path.append(root_path)
        local_file_save_path = os.path.join(root_path, constants.FILE_TEMP_PATH_NAME)
        # local_file_save_path = constants.PCAP_PATH
        # if 'linux' in sys.platform:
        # client_localfile_path = os.path.join(local_file_save_path, os.path.basename(client_network_packet_pcap))
        # server_localfile_path = os.path.join(local_file_save_path, os.path.basename(server_network_packet_pcap))
        client_basename = None
        server_basename = None
        if '/' in client_network_packet_pcap:
            client_basename = client_network_packet_pcap.split('/')[-1]
        elif '\\' in client_network_packet_pcap:
            client_basename = client_network_packet_pcap.split('\\')[-1]
        if '/' in server_network_packet_pcap:
            server_basename = server_network_packet_pcap.split('/')[-1]
        elif '\\' in server_network_packet_pcap:
            server_basename = server_network_packet_pcap.split('\\')[-1]

        client_localfile_path = os.path.join(local_file_save_path, client_basename)
        server_localfile_path = os.path.join(local_file_save_path, server_basename)
        rtn_code = RtnStatusEnum.FAIL.value

        # 将文件下载到指定的路径下
        if 'windows' not in host_os_client:
            client_packet_rtn = self.__download_network_packet_compare(
                remote_file_path=client_network_packet_pcap,
                remote_ssh_ip=self.client_ip,
                username=username_client
            )
        else:
            scp_file_cmd = f"scp -P {self.test_port} {username_client}@{self.client_ip}:" \
                           f"'{client_network_packet_pcap}' {local_file_save_path}"
            client_packet_rtn, _, _ = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=scp_file_cmd,
                local_execute_flag=True
            )
        if 'windows' not in host_os_server:
            server_packet_rtn = self.__download_network_packet_compare(
                remote_file_path=server_network_packet_pcap,
                remote_ssh_ip=self.server_ip,
                username=username_server
            )
        else:
            scp_file_cmd =\
                f'scp -P {self.test_port} {username_server}@{self.server_ip}:' +\
                f'"{server_network_packet_pcap}" {local_file_save_path}'
            server_packet_rtn, out_put, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=scp_file_cmd,
                local_execute_flag=True
            )
            log.info('--out_put--:{}'.format(out_put))
            log.info('--err--:{}'.format(err))
        log.info('scp_packet result => client_rtn_code:{}, server_rtn_code:{}'
                 .format(client_packet_rtn, server_packet_rtn))
        if client_packet_rtn == RtnStatusEnum.SUCCESS.value and server_packet_rtn == RtnStatusEnum.SUCCESS.value:
            client_rtn_code, client_packet_num, client_packet_dict = parse_data_packet(client_localfile_path,
                                                                                       self.listen_proto_type)
            server_rtn_code, server_packet_num, server_packet_dict = parse_data_packet(server_localfile_path,
                                                                                       self.listen_proto_type)
            log.info('parse_data_packet result => client_rtn_code:{},server_rtn_code:{}'.
                     format(client_rtn_code, server_rtn_code))
            if client_rtn_code != RtnStatusEnum.SUCCESS.value or server_rtn_code != RtnStatusEnum.SUCCESS.value:
                rtn_code = RtnStatusEnum.FAIL.value
            else:
                rtn_packet_code, rx_packet_message_dict = compare_message_information(
                    tx_message=client_packet_dict,
                    rx_message=server_packet_dict)
                rtn_code = rtn_packet_code
                rx_message_dict = rx_packet_message_dict
                # if client_packet_num != server_packet_num:
                #     rtn_code = RtnStatusEnum.FAIL.value
                #     rx_message_dict = server_packet_dict
                # else:
                #     rtn_packet_code, rx_packet_message_dict = compare_message_information(
                #         tx_message=client_packet_dict,
                #         rx_message=server_packet_dict)
                #     rtn_code = rtn_packet_code
                #     rx_message_dict = rx_packet_message_dict
        else:
            rtn_code = RtnStatusEnum.FAIL.value
        command = 'mv {} {}' if 'win' not in sys.platform else 'ren {} {}'
        time_stamp = datetime.now().strftime('%Y%m%d%H%M%S')
        client_packet_path_new_linux = os.path.join(constants.PCAP_PATH, 'client' + time_stamp + '.pcap')
        # client_packet_path_new_linux = \
        #     client_localfile_path.replace('.pcap', time_stamp + '.pcap')
        # server_packet_path_new_linux = server_localfile_path.replace('.pcap', time_stamp + '.pcap')
        server_packet_path_new_linux = os.path.join(constants.PCAP_PATH, 'server' + time_stamp + '.pcap')
        client_packet_path_new_win = 'client_packet' + time_stamp + '.pcap'
        server_packet_path_new_win = 'server_packet' + time_stamp + '.pcap'

        if 'windows' not in sys.platform:
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command.format(client_localfile_path, client_packet_path_new_linux),
                local_execute_flag=True)
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command.format(server_localfile_path, server_packet_path_new_linux),
                local_execute_flag=True)
            # 修改外网代码机临时文件夹所属组
            cmd = f"chown -R tester:tester {local_file_save_path}"
            CommandOperation.execute_command_based_paramiko_with_rtncode(cmd=cmd, local_execute_flag=True,
                                                                         print_enable=True)
        else:
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command.format(client_localfile_path, client_packet_path_new_win),
                local_execute_flag=True)
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=command.format(server_localfile_path, server_packet_path_new_win),
                local_execute_flag=True)
        return rtn_code, rx_message_dict


class PacketOperationWithoutCheck(object):

    def __init__(self, caller_class=ScriptBase, test_time: int = 10, udp_flag: bool = False,
                 packet_length: int = 64, bandwidth: str = '10M', parallel_num: int = 8, rpc_server_ip: str = '',
                 rpc_client_ip: str = ''):
        self.test_time = test_time
        if caller_class.test_port:
            self.test_port = caller_class.test_port
        else:
            self.test_port = 22
        self.server_ip = rpc_server_ip if rpc_server_ip else CommandOperation.server_ip
        self.client_ip = rpc_client_ip if rpc_client_ip else CommandOperation.client_ip
        self.caller_class = caller_class
        self.udp_flag = udp_flag
        self.packet_length = packet_length
        self.bandwidth = bandwidth
        self.parallel_num = parallel_num

    def packet_test_without_check(self):
        """
        不带收发校验的数据报测试，使用iperf工具打流，用于与数据通路交互但不关心数据通路的测试，如驱动加卸载等
        :return:
        """
        # 创建client发包进程
        if self.server_ip != CommandOperation.server_ip:
            server_ip = self.server_ip
        else:
            server_ip = ''

        if self.client_ip != CommandOperation.client_ip:
            client_ip = self.client_ip
        else:
            client_ip = ''
        client_service = SxeThread(IperfOperation(caller_class=self.caller_class,
                                                  run_time=self.test_time,
                                                  packet_length=self.packet_length,
                                                  bandwidth=self.bandwidth,
                                                  udp_flag=self.udp_flag,
                                                  parallel_num=self.parallel_num,
                                                  rpc_client_ip=client_ip).client_iperf)
        # 创建server监听进程
        server_service = SxeThread(IperfOperation(caller_class=self.caller_class,
                                                  rpc_server_ip=server_ip).server_iperf)
        client_service.setDaemon(True)
        server_service.start()
        time.sleep(3)
        client_service.start()
        time.sleep(3)
        # 检查client端iperf是否还在运行中，如果不在运行中，则清理掉server端iperf进程
        host_os_server, _ = CommonOperation.get_nic_os()
        while True:
            if not client_service.is_alive():
                time.sleep(5)
                if 'windows' not in host_os_server:
                    server_command = "pkill -ef iperf3"
                else:
                    server_command = "taskkill /im iperf3.exe /f"
                CommandOperation.execute_command_with_error(server_command,
                                                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                                                            host_os_server=host_os_server)
                break
            else:
                time.sleep(10)


# # 重接二层帧封装方法，并支持
# class Ether(Ether):
#     def __init__(self, err_packet_flag: bool = False):
#         super().__init__()
#         self.err_packet_flag = err_packet_flag
#         from scapy.layers.l2 import DestMACField, SourceMACField, XShortEnumField
#         if self.err_packet_flag:
#             super().fields_desc = [DestMACField("dst"),
#                                    SourceMACField("src")]
#         else:
#             super().fields_desc = [DestMACField("dst"),
#                                    SourceMACField("src"),
#                                    XShortEnumField("type", 0x9000, ETHER_TYPES)]

class PacketOperationBySocketWithCheck(object):

    def __init__(self, caller_class, count: int, message: str = None,
                 socket_port: int = constants.SOCKET_PORT,
                 socket_protocal: str = TransportProtocal.TRANSPORT_TCP.value,
                 socket_ipv: str = PacketType.PACKET_IPV4.value,
                 data_len: int = 0,
                 virtual_flag: bool = False,
                 target_port: int = 0,
                 check_packet: bool = True,
                 rpc_server_ip: str = '',
                 rpc_client_ip: str = '',
                 timeout: int = 60
                 ):
        self.caller_class = caller_class
        self.device_dict = {}
        if caller_class.test_port:
            self.test_port = caller_class.test_port
        else:
            self.test_port = 22

        self.device_dict["client_device_ip"] = caller_class.test_device_info_list[target_port]["client_device_ip"]
        self.device_dict["server_device_ip"] = caller_class.test_device_info_list[target_port]["server_device_ip"]
        self.device_dict["client_device_mac"] = caller_class.test_device_info_list[target_port]["client_device_mac"]
        self.device_dict["server_device_mac"] = caller_class.test_device_info_list[target_port]["server_device_mac"]
        self.device_dict["client_device_name"] = caller_class.test_device_info_list[target_port]["client_device_name"]
        self.device_dict["server_device_name"] = caller_class.test_device_info_list[target_port]["server_device_name"]
        self.device_dict["client_device_ipv6"] = caller_class.test_device_info_list[target_port]["client_device_ipv6"]
        self.device_dict["server_device_ipv6"] = caller_class.test_device_info_list[target_port]["server_device_ipv6"]

        self.message = message
        self.server_rtn_code, self.client_rtn_code = None, None
        self.server_rtn_outputs, self.client_rtn_outputs = None, None
        self.count = count
        self.data_len = data_len
        self.socket_port = socket_port
        self.socket_ipv = socket_ipv
        self.socket_protocal = socket_protocal
        self.virtual_flag = virtual_flag
        self.check_packet = check_packet
        self.rpc_server_ip = rpc_server_ip
        self.rpc_client_ip = rpc_client_ip
        self.server_ip = rpc_server_ip if rpc_server_ip else CommandOperation.server_ip
        self.client_ip = rpc_client_ip if rpc_client_ip else CommandOperation.client_ip
        self.timeout = timeout

    def server_revice_packet(self):
        """
        author: weiyuan
        date:   2022-07-28
        description: 收包
        """
        server_kwargs = None
        server_os, _ = CommonOperation.get_nic_os()
        if server_os == 'windows':
            ssh_username = "Administrator"
            vm, rpc_port = CommonOperation.get_node_info_from_path()
            server_vm_path = "{}{}".format(CommonOperation.get_root_path(server_os), vm)
            server_args = ([], constants.PYTHON, "{}/receive_packet.py".
                           format(server_vm_path))
        else:
            ssh_username = 'root'
            server_args = ([], constants.PYTHON, constants.SOCKET_SERVER_PATH)

        if not self.virtual_flag:
            if self.socket_ipv == PacketType.PACKET_IPV4.value:
                server_kwargs = {"--proto": self.socket_protocal,
                                 "--ipv": self.socket_ipv,
                                 "--snip": self.device_dict['server_device_ip'],
                                 "--sp": self.socket_port,
                                 }
            elif self.socket_ipv == PacketType.PACKET_IPV6.value:
                server_kwargs = {"--proto": self.socket_protocal,
                                 "--ipv": self.socket_ipv,
                                 "--snip": self.device_dict['server_device_ipv6'],
                                 "--sp": self.socket_port,
                                 }
            else:
                pass
        else:
            if self.socket_ipv == PacketType.PACKET_IPV4.value:
                server_kwargs = {"--proto": self.socket_protocal,
                                 "--ipv": self.socket_ipv,
                                 "--snip": self.device_dict['server_vlan_ip'],
                                 "--sp": self.socket_port,
                                 }
            elif self.socket_ipv == PacketType.PACKET_IPV6.value:
                server_kwargs = {"--proto": self.socket_protocal,
                                 "--ipv": self.socket_ipv,
                                 "--snip": self.device_dict['server_vlan_ip'],
                                 "--sp": self.socket_port
                                 }
            else:
                pass
        server_command = CommandOperation.concat_parameters(*server_args, **server_kwargs)

        if self.rpc_server_ip:
            self.server_rtn_code, self.server_rtn_outputs, rtn_err = \
                CommandOperation.execute_command_with_error(
                # CommandOperation.execute_command_based_paramiko_with_rtncode(
                    server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                    ssh_ip=self.server_ip, timeout=self.timeout,
                    ssh_username=ssh_username, win_vm_ip=self.rpc_server_ip, host_os_server='windows')
        else:
            self.server_rtn_code, self.server_rtn_outputs, rtn_err = \
                CommandOperation.execute_command_with_error(
                # CommandOperation.execute_command_based_paramiko_with_rtncode(
                    server_command, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
                    ssh_username=ssh_username, ssh_ip=self.server_ip, timeout=self.timeout)

    def client_send_message(self):
        """
        author: weiyuan
        date:   2022-07-28
        description: 发送文件
        """
        client_kwargs = None
        _, client_os = CommonOperation.get_nic_os()
        if client_os == 'windows':
            ssh_username = "Administrator"
            vm, rpc_port = CommonOperation.get_node_info_from_path()
            client_vm_path = "{}{}".format(CommonOperation.get_root_path(client_os), vm)
            client_args = ([], constants.PYTHON, "{}/send_packet.py".
                           format(client_vm_path))
        else:
            ssh_username = 'root'
            client_args = ([], constants.PYTHON, constants.SOCKET_CLIENT_PATH)
        if not self.virtual_flag:
            if self.socket_ipv == PacketType.PACKET_IPV4.value:
                client_kwargs = {"--proto": self.socket_protocal,
                                 "--ipv": self.socket_ipv,
                                 "--snip": self.device_dict['server_device_ip'],
                                 "--sp": self.socket_port,
                                 "--data": self.message,
                                 "--data_len": self.data_len,
                                 "--count": self.count,
                                 }

            elif self.socket_ipv == PacketType.PACKET_IPV6.value:
                client_kwargs = {"--proto": self.socket_protocal,
                                 "--ipv": self.socket_ipv,
                                 "--snip": self.device_dict['server_device_ipv6'],
                                 "--sp": self.socket_port,
                                 "--data": self.message,
                                 "--data_len": self.data_len,
                                 "--count": self.count,
                                 }
            else:
                pass
        else:
            if self.socket_ipv == PacketType.PACKET_IPV4.value:
                client_kwargs = {"--proto": self.socket_protocal,
                                 "--ipv": self.socket_ipv,
                                 "--snip": self.device_dict['server_vlan_ip'],
                                 "--sp": self.socket_port,
                                 "--data": self.message,
                                 "--data_len": self.data_len,
                                 "--count": self.count,
                                 }
            elif self.socket_ipv == PacketType.PACKET_IPV6.value:
                client_kwargs = {"--proto": self.socket_protocal,
                                 "--ipv": self.socket_ipv,
                                 "--snip": self.device_dict['server_vlan_ip'],
                                 "--sp": self.socket_port,
                                 "--data": self.message,
                                 "--data_len": self.data_len,
                                 "--count": self.count,
                                 }
            else:
                pass
        client_command = CommandOperation.concat_parameters(*client_args, **client_kwargs)
        if self.rpc_client_ip:
            self.client_rtn_code, self.client_rtn_outputs, client_rtn_err = \
                CommandOperation.execute_command_with_error(
                # CommandOperation.execute_command_based_paramiko_with_rtncode(
                    client_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                    ssh_ip=self.client_ip,
                    ssh_username=ssh_username, win_vm_ip=self.rpc_client_ip, host_os_client='windows')
        else:
            self.client_rtn_code, self.client_rtn_outputs, client_rtn_err = \
                CommandOperation.execute_command_with_error(
                # CommandOperation.execute_command_based_paramiko_with_rtncode(
                    client_command, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                    ssh_username=ssh_username, ssh_ip=self.client_ip,)

    def packet_operation_by_socket(self):
        reci_p = SxeThread(self.server_revice_packet)
        send_p = SxeThread(self.client_send_message)
        # 创建远程拉起server端的线程
        time.sleep(1)
        send_p.setDaemon(True)
        reci_p.setDaemon(True)
        reci_p.start()
        time.sleep(20)
        send_p.start()
        send_p.join()
        reci_p.join()
        time.sleep(2)
        if not self.server_rtn_code and not self.client_rtn_code:
            result = ''
            server_os, client_os = CommonOperation.get_nic_os()
            if 'windows' not in client_os:
                for i in range(self.count):
                    result += self.message + str(i)
            else:
                result += self.message + '1' * self.data_len
            if self.server_rtn_outputs.strip() == result:
                log.info_caller('校验成功')
                return True
            elif self.check_packet:
                CommonOperation.create_bug_problem(case_cls=self.caller_class, key_word='socket收发功能',
                                                   description_word="报文校验失败")
            else:
                log.info(self.server_rtn_code)
                log.info('收发包不一致，但未报bug，请关注后续流程')
                return False
        else:
            return False

    def large_packet_operation_by_socket(self):
        reci_p = SxeThread(self.server_revice_packet)
        send_p = SxeThread(self.client_send_message)
        send_p.setDaemon(True)
        reci_p.setDaemon(True)
        reci_p.start()
        time.sleep(1)
        send_p.start()
        send_p.join()
        reci_p.join()
        if not self.server_rtn_code and not self.client_rtn_code:
            # result = ''
            # # for i in range(self.count):
            # #     result += self.message + str(i)
            # if self.server_rtn_outputs.strip()[:-1] == self.client_rtn_outputs.strip():
            #     log.info_caller('校验成功')
            return True
            # else:
            #     CommonOperation.create_bug_problem(case_cls=self.caller_class, key_word='socket收发功能',
            #                                        description_word="报文校验失败")
        else:
            return False


class SendpL4Packet(object):
    def __init__(self, caller_class, proto_type: (str or list),
                 ether_src_mac: str = None, ether_dst_mac: str = None, sport: int = None, dport: int = None,
                 payload: int = 0, checksum_flag: bool = True, ether_src_ip: str = None, ether_dst_ip: str = None,
                 target_port: int = 0, count: int = 1, rpc_server_ip: str = '',
                 rpc_client_ip: str = ''):
        """
        入参
        :param caller_class: 调用基类
        :param ether_dst_mac: 收包侧的mac地址
        :param ether_src_mac: 发包侧的mac地址
        :param sport: 4层发包侧端口号
        :param dport: 4层收包侧端口号
        :param payload: 载荷长度
        :param checksum_flag: checksum值是否正确，默认true
        :param ether_src_ip: 发端ip，如果传入以传入为准，否则使用test_device_info_dict中的ip
        :param ether_dst_ip: 收端ip，如果传入以传入为准，否则使用test_device_info_dict中的ip
        """
        self.ether_src_mac = ether_src_mac
        self.ether_dst_mac = ether_dst_mac
        # 只是管理IP
        self.server_ip = rpc_server_ip if rpc_server_ip else CommandOperation.server_ip
        self.client_ip = rpc_client_ip if rpc_client_ip else CommandOperation.client_ip
        self.packet_type = proto_type
        self.device_dict = {}
        if caller_class.test_port:
            self.test_port = caller_class.test_port
        else:
            self.test_port = 22

        self.device_dict["client_device_ip"] = caller_class.test_device_info_list[target_port]["client_device_ip"]
        self.device_dict["server_device_ip"] = caller_class.test_device_info_list[target_port]["server_device_ip"]
        self.device_dict["client_device_mac"] = caller_class.test_device_info_list[target_port]["client_device_mac"]
        self.device_dict["server_device_mac"] = caller_class.test_device_info_list[target_port]["server_device_mac"]
        self.device_dict["client_device_name"] = caller_class.test_device_info_list[target_port]["client_device_name"]
        self.device_dict["server_device_name"] = caller_class.test_device_info_list[target_port]["server_device_name"]
        self.device_dict["client_device_ipv6"] = caller_class.test_device_info_list[target_port]["client_device_ipv6"]
        self.device_dict["server_device_ipv6"] = caller_class.test_device_info_list[target_port]["server_device_ipv6"]

        self.sport = sport
        self.dport = dport
        self.payload = payload
        self.checksum_flag = checksum_flag
        self.ether_src_ip = ether_src_ip
        self.ether_dst_ip = ether_dst_ip
        self.count = count

    def sendp_packet(self, start_mode: str = ""):
        """
        带收发校验的数据报测试
        start_mode: 指定启动模式，client为只启动client端，server为只启动server端，其他为都启动
        :return:
        """
        log.info("start_mode:{}".format(start_mode))
        log.info("self.client_ip:{}, constants.RPC_PORT:{}".format(self.client_ip, str(constants.RPC_PORT)))
        if start_mode == 'client':
            # 创建远程拉起client端的线程
            client_service = SxeThread(self.client_run_service)
            client_service.start()
            time.sleep(6)
            # 创建向client端和server端进行业务程序的线程
            client_listener = Client((self.client_ip, constants.RPC_PORT))
            client_proxy = RPCProxy(client_listener).get_proxy()
            scapy_service = SxeThread(self.scapy_transport_packet, server_proxy=None,
                                      client_proxy=client_proxy)
            scapy_service.setDaemon(True)
            scapy_service.start()
            # 监测server端和client端的scpay_service服务是否还在运行中，如果不在运行中，
            # 则清理掉server_service进程和client_service进程
            server_os, client_os = CommonOperation.get_nic_os()
            vm, rpc_port = CommonOperation.get_node_info_from_path()
            vm_path = "{}{}".format(CommonOperation.get_root_path(client_os), vm)
            while True:
                if not scapy_service.is_alive():
                    time.sleep(5)
                    if client_os != 'windows':
                        client_command_kill = "ps -ef | grep 'python3 {}/rpc_server.py'".format(vm_path) + \
                                                 "| grep -v grep | awk '{print$2}' | xargs kill -9"
                        client_ssh_username = 'root'
                        win_vm_ip = ''
                        host_os_client = 'linux'
                    else:
                        client_command_get_pid = ""
                        client_command_kill = "taskkill -f -t -im python3.exe"
                        client_ssh_username = 'Administrator'

                        if self.client_ip == self.device_dict.get('client_win_vm_ip', 'na'):

                            win_vm_ip = self.client_ip
                            host_os_client = 'windows'
                        else:
                            win_vm_ip = ''
                            host_os_client = 'linux'
                    client_proxy.end_socket()
                    CommandOperation.execute_command_based_paramiko_with_rtncode(
                         client_command_kill, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                         ssh_ip=self.client_ip, ssh_port=str(self.test_port), ssh_username=client_ssh_username,
                         host_os_client=host_os_client, win_vm_ip=win_vm_ip)
                    break
                else:
                    continue

    def client_run_service(self):
        """
        author: wei.yuan1
        date: 2022.09.01
        description: 在client端拉起rpc_server服务，用于发包和监测抓包
        """
        server_os, client_os = CommonOperation.get_nic_os()
        vm, rpc_port = CommonOperation.get_node_info_from_path()
        vm_path = "{}{}".format(CommonOperation.get_root_path(client_os), vm)
        if client_os == 'windows':
            server_command = "python3 {}/rpc_server.py".format(vm_path)
            ssh_username = "Administrator"
            print('self.client_ip', self.client_ip, self.device_dict)
            if self.client_ip == self.device_dict.get('client_win_vm_ip', 'na'):
                win_vm_ip = self.client_ip
            else:
                win_vm_ip = ''
        else:
            server_command = "python3 {}/rpc_server.py 2>&1".format(vm_path)
            ssh_username = 'root'
            win_vm_ip = ''

        client_rtn_code, client_rtn_outputs, client_rtn_err = CommandOperation.execute_command_with_error(
            server_command, ssh_ip=self.client_ip,
            ssh_port=str(self.test_port), ssh_username=ssh_username,
            win_vm_ip=win_vm_ip, host_os_client=client_os, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
        log.info("===>client_run_service, rtn_code:\n{},rtn_outputs:\n{}".
                 format(client_rtn_code, client_rtn_outputs.replace("..", "")))

    def server_run_service(self):
        """
        author: wei,yuan1
        date: 2022.09.01
        description: 在server端拉起rpc_server服务
        """
        server_os, client_os = CommonOperation.get_nic_os()
        vm, rpc_port = CommonOperation.get_node_info_from_path()
        vm_path = "{}{}".format(CommonOperation.get_root_path(server_os), vm)
        if server_os == 'windows':
            server_command = "python3 {}/rpc_server.py".format(vm_path)
            ssh_username = "Administrator"
            if self.server_ip == self.device_dict.get('server_win_vm_ip', 'na'):
                win_vm_ip = self.server_ip
            else:
                win_vm_ip = ''
        else:
            server_command = "python3 {}/rpc_server.py 2>&1".format(vm_path)
            ssh_username = 'root'
            win_vm_ip = ''

        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            server_command, ssh_ip=self.server_ip,
            ssh_port=str(CommandLineArgsParse.get_server_port()), ssh_username=ssh_username,
            host_os_server=server_os, win_vm_ip=win_vm_ip, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
        log.info("===>server_run_service, rtn_code:\n{},rtn_outputs:\n{}".
                 format(rtn_code, rtn_outputs.replace("..", "")))

    def scapy_transport_packet(self, server_proxy, client_proxy):
        """
        author: wei.yuan
        date: 2022.09.01
        description: 对server端和client端进行异步发包操作
        """
        # global manager
        if client_proxy and not server_proxy:
            client = SxeThread(self.client_send_packet, proxy=client_proxy)
            client.start()
            client.join()

    def client_send_packet(self, proxy):
        """
        author: wei.yuan1
        date：2022.09.01
        description:
        """
        dst_ip = self.ether_dst_ip if self.ether_dst_ip else self.device_dict['server_device_ip']
        src_ip = self.ether_src_ip if self.ether_src_ip else self.device_dict['client_device_ip']
        if isinstance(self.packet_type, str):
            if self.packet_type == TransportProtocal.TRANSPORT_TCP.value:
                proxy.sendp_tcp_packet(dst_mac=self.ether_dst_mac, src_mac=self.ether_src_mac,
                                       dst_ip=dst_ip,
                                       src_ip=src_ip, dport=self.dport,
                                       sport=self.sport,
                                       iface=self.device_dict['client_device_name'],
                                       checksum_flag=self.checksum_flag,
                                       payload=self.payload,
                                       count=self.count)
            elif self.packet_type == TransportProtocal.TRANSPORT_UDP.value:
                proxy.sendp_udp_packet(dst_mac=self.ether_dst_mac, src_mac=self.ether_src_mac,
                                       dst_ip=dst_ip,
                                       src_ip=src_ip, dport=self.dport,
                                       sport=self.sport,
                                       iface=self.device_dict['client_device_name'],
                                       checksum_flag=self.checksum_flag,
                                       payload=self.payload,
                                       count=self.count
                                       )

            elif self.packet_type == TransportProtocal.TRANSPORT_SCTP.value:
                proxy.sendp_sctp_packet(dst_mac=self.ether_dst_mac, src_mac=self.ether_src_mac,
                                        dst_ip=dst_ip,
                                        src_ip=src_ip,
                                        iface=self.device_dict['client_device_name'],
                                        checksum_flag=self.checksum_flag,
                                        payload=self.payload,
                                        count=self.count
                                        )
            elif self.packet_type == TransportProtocal.TRANSPORT_TCP6.value:
                proxy.sendp_tcp6_packet(dst_mac=self.ether_dst_mac, src_mac=self.ether_src_mac,
                                        dst_ip=dst_ip,
                                        src_ip=src_ip, dport=self.dport,
                                        sport=self.sport,
                                        iface=self.device_dict['client_device_name'],
                                        checksum_flag=self.checksum_flag,
                                        payload=self.payload,
                                        count=self.count)

        elif isinstance(self.packet_type, list):
            for packet_type in self.packet_type:
                if packet_type == TransportProtocal.TRANSPORT_TCP.value:
                    proxy.sendp_tcp_packet(dst_mac=self.ether_dst_mac, src_mac=self.ether_src_mac,
                                           dst_ip=dst_ip,
                                           src_ip=src_ip, dport=self.dport,
                                           sport=self.sport,
                                           iface=self.device_dict['client_device_name'],
                                           checksum_flag=self.checksum_flag,
                                           payload=self.payload,
                                           count=self.count
                                           )
                elif packet_type == TransportProtocal.TRANSPORT_UDP.value:
                    proxy.sendp_udp_packet(dst_mac=self.ether_dst_mac, src_mac=self.ether_src_mac,
                                           dst_ip=dst_ip,
                                           src_ip=src_ip, dport=self.dport,
                                           sport=self.sport,
                                           iface=self.device_dict['client_device_name'],
                                           checksum_flag=self.checksum_flag,
                                           payload=self.payload,
                                           count=self.count
                                           )

                elif packet_type == TransportProtocal.TRANSPORT_SCTP.value:
                    proxy.sendp_sctp_packet(dst_mac=self.ether_dst_mac, src_mac=self.ether_src_mac,
                                            dst_ip=dst_ip,
                                            src_ip=src_ip,
                                            iface=self.device_dict['client_device_name'],
                                            checksum_flag=self.checksum_flag,
                                            payload=self.payload,
                                            count=self.count
                                            )
                elif packet_type == TransportProtocal.TRANSPORT_TCP6.value:
                    proxy.sendp_tcp6_packet(dst_mac=self.ether_dst_mac, src_mac=self.ether_src_mac,
                                            dst_ip=dst_ip,
                                            src_ip=src_ip, dport=self.dport,
                                            sport=self.sport,
                                            iface=self.device_dict['client_device_name'],
                                            checksum_flag=self.checksum_flag,
                                            payload=self.payload,
                                            count=self.count)


if __name__ == '__main__':
    # 调用方法举例:
    # PacketOperation.structure_icmp_packet(src='127.0.0.1', dst='10.17.91.253')
    # data = PacketOperation.structure_socket_packet(312)

    # package_object = StructNetworkDataPackage(src_nic_name="ens1f0", dst_nic_name="ens1f0",
    #                                           network_packet_type=TransportProtocal.TRANSPORT_ARP.value)
    # package_header = package_object.struct_package_header()
    # package_header.show()
    # data_dict = {"frame_type": TransportProtocal.ETHER_SNAP.value}
    # data_dict = {}
    data_dict = {

        "version": PacketType.PACKET_IPV6.value

    }
    package_object = StructNetworkDataPackage(src_nic_name="ens1f0", dst_nic_name="ens1f0", data_len=128,
                                              network_packet_type=TransportProtocal.TRANSPORT_IP.value, **data_dict)
    log.info("package_dict:{}".format(package_object.package_dict))

    package_header, package_header_length = package_object.struct_package_header()
    package_header.show()
    # print(package_header_length)
    # message_parse_data_packet(parse_message_file="D:/Desktop/packet.pcap")

    # packet_operation = PacketOperationWithCheck(time_out=60,
    #                                             listen_proto_type=TransportProtocal.TRANSPORT_ICMP.value,
    #                                             packet_header=package_header, data_len=package_header_length,
    #                                             transport_layer=2)
    #
    # # packet_operation.packet_test_with_check()
    # CommonOperation.concat_test_steps(f"3.查看抓取的报文，是否收到相应数据包")
    # # TODO 等待公共方法完善
    # rtn, rx_dict, tx_dict = packet_operation.network_packet_compare()
    # print(rtn)
    # print(tx_dict)
    # print(tx_dict)
