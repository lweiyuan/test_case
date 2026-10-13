import socket
import os
import random
import time
import string
import platform
import argparse
from itertools import product
from typing import Union
from itertools import groupby

parser = argparse.ArgumentParser(description="Test.")
# 添加命令行参数中的proto选项
parser.add_argument('--proto', type=str, help='指定TCP/UDP')
# 添加命令行参数中的ipv选项，默认为4
parser.add_argument('--ipv', default=4, type=int, help='指定ipv4/ipv6')
# 添加命令行参数中的cnip选项
parser.add_argument('--snip', type=str, help='指定收包端测试网卡ip')
# 添加命令行参数中的cp选项
parser.add_argument('--sp', type=int, help='指定收包端口号')
# 添加命令行参数中的data选项
parser.add_argument('--data', type=str, help='指定数据,与file二选一', default='None')
# 添加命令行参数中的data 长度选项
parser.add_argument('--data_len', type=str, help='指定的文件数据长度', default="0")
# 添加命令行参数中的file选项
parser.add_argument('--file', type=str, help='指定文件路径,与data二选一', default='None')
# 添加命令行参数中的count选项
parser.add_argument('--count', default=1, type=int, help='指定发送包的个数')
args = parser.parse_args()

data = args.data
count = args.count
data_len = args.data_len
os_name = platform.platform().lower()
file_name = "/root/socket_file.txt"


def get_data_size_by_byte() -> int:
    """
    author:      shanshan.du
    date:        2024.07.26 17:25
    description:根据入参data_len(不同类型的输入:1k,1K, 1024) 确定字节数
    :return : 参数输入错误
    :return :返回字节大小
    """
    gen_data_size = 0
    size_data = args.data_len
    if isinstance(size_data, str):
        # 将用户的输入的数据进行抽取，提取出来要输入的内容
        file_str_size = [
            ''.join(list(g))
            for k, g in groupby(size_data, key=lambda x: x.isdigit())
        ]
        if len(file_str_size) == 1:
            if file_str_size[0].isdigit():
                gen_data_size = int(file_str_size[0])
            return gen_data_size
        else:
            # 对字符串的单位进行判断
            if not size_data[-1].isdigit():
                size_data = size_data.title()
                data_part = int(size_data[:-1])
                size_title = size_data[-1]
                # 单位为Kb
                if size_title == 'K':
                    gen_data_size = data_part * 1024
                # 单位为Mb
                elif size_title == 'M':
                    gen_data_size = data_part * 1024 * 1024
                # 单位为Gb
                elif size_title == 'G':
                    gen_data_size = data_part * 1024 * 1024 * 1024
                # 单位为Tb
                elif size_title == 'T':
                    gen_data_size = data_part * 1024 * 1024 * 1024 * 1024

    elif isinstance(size_data, int):
        gen_data_size = int(size_data)

    return gen_data_size


# 计算入参字节的大小
input_data_size = get_data_size_by_byte()


def create_origin_file(size: Union[int, str], file_path: str) -> tuple:
    """
    author:      WeiYuan
    date:        2020/08/29 19:25
    description:创建指定大小的文件,以K为单位
    场景模拟：
    test_name = "ssss"
    remote_path = constants.FILE_PATH_ROOT + 'read_file/' + test_name
    rtn = create_file(23, file_name=test_name, remote_file=remote_path)
    :param size: 创建文件的大小
    :param file_path: 创建文件所需要的名字
    :return :True 文件创建成功
    :return : 参数输入错误
    :return :传输文件错误
    """
    # 初始化话rtn
    rtn_file_exits = -1
    local_path, local_file = os.path.split(file_path)
    is_exists = os.path.exists(local_path)
    if not is_exists:
        print(f"{local_path}目录创建成功")
        os.mkdir(local_path)
    # 计算入参字节的大小
    file_size = get_data_size_by_byte()
    # 由于创建文件按照K为单位, 故做格式转换
    size_int, size_decimal = file_size // 1024, file_size % 1024
    # 文件填充内容
    ran_str = ''.join(
        random.sample(string.ascii_letters + string.digits,
                      16))

    # 显示字符串的序列如：[11,12]
    content_iter = list(product(ran_str, ran_str))
    # 将列表转化为字符串
    content_str = [''.join(pair) for pair in content_iter]
    # 打开文件，并向其中写入内容
    try:
        cut_section = "".join(content_str)
        start_word = "".join(content_str)
        with open(file_name, 'w') as input_file:
            # 整数部分
            if size_int > 0:
                # 文件内容大小为size
                for i in range(0, size_int):
                    # 每1k数据的开始数据
                    start_word = 'ps3-integration test index{i:08} 1kb'.format(i=i)
                    # 不足1k的数据进行填充的数据内容
                    cut_section = content_str[i % len(content_str)] * (
                            (1024 - len(start_word)) // 2 + 1)
                    # 所有的内容进行累加
                    word_line = start_word + cut_section
                    # 保证每次写入文件的字符为1024，
                    input_file.write(word_line[:1024])

            # 　小数部分
            if size_decimal > 0:
                # 不足1k的数据进行填充的数据内容
                cut_section = "".join(cut_section) * 4
                # 所有的内容进行累加
                word_line = start_word + cut_section
                # 保证每次写入文件的字符为1024，
                input_file.write(word_line[:size_decimal])

        # 创建完成文件后，进行文件的传输
    except IOError:
        return rtn_file_exits, "输入错误"


def create_file():
    create_origin_file(size=args.data_len, file_path=file_name)


def send_udp(udp_socket, count):
    if 'windows' in os_name:
        for i in range(count):
            if args.data_len > 5000:
                create_file()
                data_f = open(file_name, 'r')
                data_message = data_f.read()
                print(data_message)
                udp_socket.sendto(data_message.encode('gbk'), (args.snip, args.sp))
            else:
                if data:
                    udp_socket.sendto(data.encode('gbk'), (args.snip, args.sp))
                else:
                    udp_socket.sendto(('1' * args.data_len).encode('gbk'), (args.snip, args.sp))
        udp_socket.sendto('SXETESTEND'.encode('gbk'), (args.snip, args.sp))
    else:
        for i in range(count):
            if input_data_size > 5:
                create_file()
                data_f = open(file_name, 'r')
                data_message = data_f.read()
                print(data_message)
                udp_socket.sendto(data_message.encode('utf-8'), (args.snip, args.sp))
            else:
                if data:
                    udp_socket.sendto(data.encode('utf-8'), (args.snip, args.sp))
                else:
                    udp_socket.sendto(('1' * args.data_len).encode('utf-8'),
                                      (args.snip, args.sp))
        udp_socket.sendto('SXETESTEND'.encode('utf-8'), (args.snip, args.sp))

    udp_socket.close()


def send_tcp(tcp_socket, count):
    while True:
        try:
            if args.ipv == 4:
                tcp_socket.connect((args.snip, args.sp))
                # print(tcp_socket)
                break
            else:
                tcp_socket.connect(addrinfo[-1])
                # print(tcp_socket)
                break
        except socket.timeout as e1:
            print('Socket error1：', e1)
            time.sleep(5)
        except socket.error as e:
            print('Socket error:', e)
            time.sleep(5)

    if 'windows' in os_name:
        for i in range(count):
            if input_data_size > 5000:
                create_file()
                data_f = open(file_name, 'r')
                data_message = data_f.read()
                print(data_message)
                tcp_socket.send(data_message.encode('gbk'))
            else:
                if data:
                    tcp_socket.send(data.encode('gbk'))
                else:
                    tcp_socket.send(('1' * args.data_len).encode('gbk'))
        tcp_socket.send('SXETESTEND'.encode('gbk'))
    else:
        for i in range(count):
            if input_data_size > 5:
                create_file()
                data_f = open(file_name, 'r')
                data_message = data_f.read()
                print(data_message)
                tcp_socket.send(data_message.encode('utf-8'))
            else:
                if data:
                    tcp_socket.send(data.encode('utf-8'))
                else:
                    tcp_socket.send(('1' * args.data_len).encode('utf-8'))
        tcp_socket.send('SXETESTEND'.encode('utf-8'))

    tcp_socket.close()


if args.ipv == 4 and args.proto.lower() == 'udp':
    udp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    udp_socket.settimeout(5)
    send_udp(udp_socket, count)
elif args.ipv == 6 and args.proto.lower == 'udp':
    udp_socket = socket.socket(family=socket.AF_INET6, type=socket.SOCK_DGRAM)
    udp_socket.settimeout(5)
    send_udp(udp_socket, count)
elif args.ipv == 4 and args.proto.lower() == 'tcp':
    tcp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
    tcp_socket.settimeout(5)
    send_tcp(tcp_socket, count)
else:
    addrinfo = socket.getaddrinfo(args.snip, args.sp, 0, 0)[0]
    tcp_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    tcp_socket.settimeout(5)
    # tcp_socket.setblocking(True)
    send_tcp(tcp_socket, count)
