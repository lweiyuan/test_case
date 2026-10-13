from scapy.all import *
from scapy.layers.inet import IP

bpf = "host 192.168.100.253 and icmp and not broadcast"


def _on_success_cb(pkt: Packet) -> bool:
    if IP in pkt:
        print('收到一个来自 {} 目的 {} 的IP数据包'.format(pkt[IP].src, pkt[IP].dst))
        return True


def handle_prn_IP(packet):
    """
    author: wei.yuan
    date: 2022.08.05
    description: 对IP数据包的进行操作的函数
    """
    lambda packet: (packet.sprintf("{IP:%IP.src% -> %IP.dst%\n}{Raw:%Raw.load%\n}")).encode("utf-8")
    print(packet)


def handle_prn_TCP(packet):
    """
    author: wei.yuan
    date: 2022.08.05
    description: 对TCP数据包的进行操作的函数
    """
    lambda packet: packet.sprintf("%IP.src%:%TCP.sport% -> %IP.dst%:%TCP.dport%  %2s,TCP.flags% : %TCP.payload%")
    print(packet)
    packet[0].show()


def handle_prn_UDP(packet):
    """
    author: wei.yuan
    date: 2022.08.05
    description: 对UDP数据包的进行操作的函数
    """
    lambda packet: packet.sprintf("%IP.src%:%UDP.sport% -> %IP.dst%:%UDP.dport%  %2s,UDP.flags% : %UDP.payload%")
    print(packet)


def sniff_one(iface: str = None, timeout: float = 10, bpf: str = 'ip', on_success=_on_success_cb):
    """捕获网络数据包，收到一个预期的包则退出"""
    return sniff(
        iface=iface,  # 指定接口，不指定则嗅探所有的接口
        filter=bpf,  # 过滤规则，使用 Berkeley Packet Filter (BPF)语法
        timeout=timeout,  # 达到这个时长后退出嗅探，默认为None
        store=False,  # 是否保存结果，设置为False则返回None
        stop_filter=on_success,  # 这是一个函数，用于停止捕获
    )


def sniff_with_cb(iface: str = None, timeout: float = 10, bpf: str = 'ip', cb=lambda pkt: pkt.show()):
    """捕获数据包，带回调函数"""
    return sniff(
        prn=cb,  # callback（回调函数）
        iface=iface,  # 指定接口，不指定则嗅探所有的接口
        filter=bpf,  # 过滤规则，使用 Berkeley Packet Filter (BPF)语法
        timeout=timeout,  # 达到这个时长后退出嗅探，默认为None
        store=False,  # 是否保存结果，设置为False则返回None
    )


def sniff_with_timeout(iface: str = None, timeout: float = 10, bpf: str = 'ip') -> PacketList:
    """捕获数据包"""
    return sniff(
        iface=iface,  # 指定接口，不指定则嗅探所有的接口
        filter=bpf,  # 过滤规则，使用 Berkeley Packet Filter (BPF)语法
        timeout=timeout,  # 达到这个时长后退出嗅探，默认为None
        store=True,  # 是否保存结果，设置为False则返回None
    )


def sniff_to_file(iface: str = None, timeout: float = 10, bpf: str = 'ip', pcapfile: str = './myScapy.pcap'):
    """捕获网络数据包，并保存到文件"""
    pkts = sniff_with_timeout(iface, timeout, bpf)
    if list:
        wrpcap(pcapfile, pkts)
        # wireshark(pkts)  # 不保存文件，且使用 wireshark 打开
