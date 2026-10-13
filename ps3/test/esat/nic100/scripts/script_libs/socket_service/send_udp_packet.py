import os
import argparse
from itertools import groupby

"""
        : -t , --ipproto ip protocol ipv4 or ipv6
        : -i , --ipaddress remote ip_addr or ipv6_addr
        : -p , --port udp_port
        : -g , --gso_size gso size[less mtu]
        : -n , --packet_num send packet num
        : -s , --size single send packet【unit is 1k】
        : -l , --local_address if proto is ipv6 you can set source ip_addr
"""
parser = argparse.ArgumentParser(description="Test.")
# 添加命令行参数中的proto选项
parser.add_argument('--proto', type=str, help='指定TCP/UDP')
# 添加命令行参数中的ipv选项，默认为4
parser.add_argument('--ipv', default=4, type=int, help='指定ipv4/ipv6')
# 添加命令行参数中的snip选项
parser.add_argument('--snip', type=str, help='指定收包端测试网卡ip')
# 添加命令行参数中的cnip选项
parser.add_argument('--cnip', type=str, help='指定发包端测试网卡ip')
# 添加命令行参数中的cp选项
parser.add_argument('--sp', type=int, help='指定收包端口号')
# 添加命令行参数中的data 长度选项
parser.add_argument('--data_len', type=str, help='指定的数据长度,单位:KB', default="0")
# 添加命令行参数中的gso 长度选项
parser.add_argument('--gso_size', type=int, help='指定的gso 大小', default="0")
# 添加命令行参数中的count选项
parser.add_argument('--count', default=1, type=int, help='指定发送包的个数')
# 添加命令行参数中的file_dir选项
parser.add_argument('--file_path', default='', type=str, help='指定send_udp的路径')
args = parser.parse_args()

# -t
ipv = args.ipv
# -i remote ip
remote_ip = args.snip
# -l
local_ip = args.cnip
# -p
port = args.sp
# -g
gso_size = args.gso_size
# -n
packet_num = args.count
# -s
data_size = args.data_len
file_path = args.file_path
file_name = f"{file_path}/send_udp_packet"

if ipv == 4:
    ip_version_format = 'ipv4'
else:
    ip_version_format = 'ipv6'


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


def send_udp():
    cmd = f'send_udp_packet -t {ip_version_format} -i {remote_ip} -p {port} -g {gso_size} -n {packet_num}'
    cmd = f"{cmd} -s {data_size} -l {local_ip}"
    rtn_code = os.system(cmd)
    print(f'send cmd = {cmd} , rtn_code = {rtn_code}')
    if rtn_code == 0:
        print('send udp successfully')
    else:
        print('send udp failed')


if args.ipv == 4 and args.proto.lower() == 'udp':
    send_udp()
elif args.ipv == 6 and args.proto.lower() == 'udp':
    send_udp()

