import socket
import platform
import argparse

parser = argparse.ArgumentParser(description="Test.")
# 添加命令行参数中的proto选项
parser.add_argument('--proto', type=str, help='指定TCP/UDP')
# 添加命令行参数中的ipv选项，默认为4
parser.add_argument('--ipv', default=4, type=int, help='指定ipv4/ipv6')
# 添加命令行参数中的cnip选项
parser.add_argument('--cnip', type=str, help='指定收包端测试网卡ip')
# 添加命令行参数中的cp选项
parser.add_argument('--cp', type=int, help='指定收包端口号')
# 添加命令行参数中的data选项
parser.add_argument('--data', type=str, help='指定数据,与file二选一', default='None')
# 添加命令行参数中的file选项
parser.add_argument('--file', type=str, help='指定文件路径,与data二选一', default='None')
args = parser.parse_args()

data = args.data
os_name = platform.platform().lower()


def send_udp(udp_socket):

    if 'windows' in os_name:
        udp_socket.sendto(data.encode('gbk'), (args.cnip, args.cp))
        udp_socket.sendto('SXETESTEND'.encode('gbk'), (args.cnip, args.cp))
    else:
        udp_socket.sendto(data.encode('utf-8'), (args.cnip, args.cp))
        udp_socket.sendto('SXETESTEND'.encode('utf-8'), (args.cnip, args.cp))

    udp_socket.close()


def send_tcp(tcp_socket):

    tcp_socket.connect((args.cnip, args.cp))

    if 'windows' in os_name:
        tcp_socket.send(data.encode('gbk'))
        tcp_socket.send('SXETESTEND'.encode('gbk'))
    else:
        tcp_socket.send(data.encode('utf-8'))
        tcp_socket.send('SXETESTEND'.encode('utf-8'))

    tcp_socket.close()


if args.ipv == 4 and args.proto.lower() == 'udp':
    udp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    send_udp(udp_socket)
elif args.ipv == 6 and args.proto.lower == 'udp':
    udp_socket = socket.socket(family=socket.AF_INET6, type=socket.SOCK_DGRAM)
    send_udp(udp_socket)
elif args.ipv == 4 and args.proto.lower() == 'tcp':
    tcp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
    send_tcp(tcp_socket)
else:
    tcp_socket = socket.socket(family=socket.AF_INET6, type=socket.SOCK_STREAM)
    send_tcp(tcp_socket)
