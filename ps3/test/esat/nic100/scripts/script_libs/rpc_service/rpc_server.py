# import queue
# import ipaddress
# import threading
import pickle
import signal
# import subprocess
# import os
# import re
# import copy
# from threading import Thread
# from typing import Union
# inet下不完全统计
from scapy.layers.inet import IP, TCP, UDP, ICMP
# inet6下有一堆ipv6 extension包格式
# from scapy.layers.inet6 import *
# 2层
# from scapy.layers.inet6 import IPv6
from scapy.layers.l2 import Ether
# IPsec
# from scapy.layers.ipsec import AH, ESP
# from scapy.layers import sctp, ipsec, l2, inet6, inet
from scapy.all import *
from sys import platform
from scapy.layers.sctp import SCTP
import sys
from multiprocessing.connection import Listener
thread_ret_values = []

# history
# 20230824 hejf merge liuxd code
# 20230825 liuxd modify checksum -> chksum
# 20230903 hejf modify port and save path
# 20231006 hejf modify for windows
# 20231206 hejf modify for ubuntu core,delete "socket.gethostname()"
# 20231220 hejf modify for ubuntu core,move "from multiprocessing.connection import Listener" position
# 20240111 liuxy delete no use import and function

WINDOWS_FILE_PATH_ROOT = 'C:/Users/Administrator/sxetest/'
LINUX_FILE_PATH_ROOT = '/root/sxetest/'


class RpcServiceException(Exception):
    """用于create_bug方法中中抛该异常，Run方法中捕获"""
    pass


class RpcServiceThread(threading.Thread):
    """
    author:      xianda.liu
    date:        2022-07-22
    description: 用于创建多线程使用，重写了threading.Thread的run、join方法，在子线程报异常时，
                 主线程可以捕获到，具体看参考scripts.test_example.test.py中的使用
    """

    def __init__(self, func_name, *args, **kwargs):
        threading.Thread.__init__(self, func_name, *args, **kwargs)
        self.args = args
        self.kwargs = kwargs
        self.func_name = func_name
        self.exception = None
        self.ret = None
        self.exit_code = 0
        # self.exc_traceback = ''

    def run(self) -> None:
        """
        author:      xianda.liu
        date:        2022-07-22
        description: 重写父类中的 run 方法，实现捕获子进程的 SxeException 异常
        """
        try:
            self.ret = self.func_name(*self.args, **self.kwargs)
        except (RpcServiceException, Exception) as e:
            self.exception = e
            self.exit_code = 1
            # self.exc_traceback = traceback.format_exc()
        finally:
            del self.func_name, self.args, self.kwargs

    def join(self, timeout=None) -> None:
        """
        author:      haibin.xu
        date:        2020-10-01 16:45:26
        description: 重写父类中的 join 方法，增加抛 SxeException 异常功能
        :param timeout: 超时等待时间，该参数未使用，因为父类中含有该参数，所以重写时，必须要加上
        """
        super(RpcServiceThread, self).join()
        if self.exception:
            raise self.exception
        return self.ret

    def get_result(self):
        return self.ret

    # def async_raise(tid, exctype):
    #     """raises the exception, performs cleanup if needed"""
    #     tid = ctypes.c_long(tid)
    #     if not inspect.isclass(exctype):
    #         exctype = type(exctype)
    #     res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    #     if res == 0:
    #         raise ValueError("invalid thread id")
    #     elif res != 1:
    #         # """if it returns a number greater than one, you're in trouble,
    #         # and you should call it again with exc=NULL to revert the effect"""
    #         ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
    #         raise SystemError("SxeThreadState_SetAsyncExc failed")


class RPCHandler:
    def __init__(self):
        self._functions = {}

    def register_function(self, func):
        self._functions[func.__name__] = func

    def handle_connection(self, connection, sock):
        try:
            while True:
                func_name, args, kwargs = pickle.loads(connection.recv())
                # print("func_name:", func_name, args, kwargs)
                try:
                    r = self._functions[func_name](*args, **kwargs)
                    connection.send(pickle.dumps(r))
                    if func_name == 'end_socket':
                        thread_ret_values.append(1)
                        break
                    else:
                        thread_ret_values.append(0)
                except Exception as e:
                    connection.send(pickle.dumps(e))
                    thread_ret_values.append(0)
        except EOFError:
            print("EOFError")
            pass
        finally:
            if 1 in thread_ret_values:
                sock.close()


def rpc_server(handler, address):
    sock = Listener(address)
    while True:
        client = sock.accept()
        t = Thread(target=handler.handle_connection, args=(client, sock))
        t.daemon = True
        t.start()


def end_socket():
    pass


# 所有构造包的方法写在这
def structure_ip_ping(src_ip: str, dst_ip: str, proto: str = 'TCP', dport: int = 80,
                      timeout: float = 2, retry: int = 2) -> bool:
    """使用 tcp 或 udp 探测主机是否活跃"""
    if proto.upper() == 'UDP':
        pkt = sr1(IP(dst=dst_ip, src=src_ip) / UDP(dport=dport), timeout=timeout, retry=retry)
        pkt.show()
        return pkt is not None

    elif proto.upper() == 'TCP':
        pkt = sr1(IP(dst=dst_ip, src=src_ip) / TCP(dport=dport, flags="S"), timeout=timeout, retry=retry)
        pkt.show()
        return pkt is not None

    else:
        return False


def structure_icmp_ping(src_ip: str, dst_ip: str, timeout: float = 2, retry: int = 2) -> bool:
    """使用icmp探测主机是否活跃"""
    pkt = sr1(IP(src=src_ip, dst=dst_ip) / ICMP(), timeout=timeout, retry=retry)
    pkt.show()
    return pkt is not None


# def ip_ping(ip: str, proto: str = 'TCP', dport: int = 80, timeout: float = 2, retry: int = 2) -> bool:
#     """使用 tcp 或 udp 探测主机是否活跃"""
#     if proto.upper() == 'UDP':
#         pkt = sr1(IP(dst=ip) / UDP(dport=dport), timeout=timeout, retry=retry)
#         return pkt is not None
# 
#     elif proto.upper() == 'TCP':
#         pkt = sr1(IP(dst=ip) / TCP(dport=dport, flags="S"), timeout=timeout, retry=retry)
#         return pkt is not None
# 
#     else:
#         return False


def send_packet(packet_header, data_len: int, transport_layer: int, iface, count: int = 1,
                checksum_flag: bool = True, proto: str = '') -> None:
    def structure_socket_packet(length_of_string: int):
        """
        author: wei.yuan
        date:   2022-07-28
        description: 构造网络包报文
        """
        import string
        random_string = ""
        # random_string = "".join(random.choice(string.ascii_letters + string.digits
        #                                      ) for _ in range(length_of_string))
        string_list = ["s", "x", "e"]
        # sxe -> 737865
        for i in range(length_of_string):
            random_string += string_list[i % 3]
        return random_string

    packet = packet_header / structure_socket_packet(data_len)
    if checksum_flag:
        pass
    else:
        if proto == 'ip':
            packet[IP].chksum = 0
    packet.show()
    if transport_layer == 2:
        res = sendp(packet, iface=iface, count=count)
    else:
        res = send(packet, iface=iface, count=count)


def get_match_parameter(param_pattern: str, params_list: list = None, params_dict: dict = None) -> str:
    """
    author:      haibin.xu
    date:        2020-09-09 15:26:18
    description: 从参数列表中获取指定匹配模式的参数
    :param param_pattern: 参数匹配模式
    :param params_list: 参数列表
    :param params_dict: 关键字参数
    :return:     返回匹配的参数，没有的话，返回''
    """
    rtn_param = ' '

    if params_list is not None:
        for param in params_list:
            if re.match(param_pattern, param):
                rtn_param = param
                break
    if (' ' == rtn_param) and (params_dict is not None):
        for key_pa in params_dict:
            if re.match(param_pattern, key_pa):
                rtn_param = key_pa
                break

    return rtn_param


def sort_parameters(priority_params_list: list, *args: tuple, **kwargs: dict) -> tuple:
    """
    author:      haibin.xu
    date:        2020-08-26 16:21:03
    description: 根据参数优先级列表（类变量cli_cmd_args_list中已定义）调整输入参数顺序
    :param priority_params_list: 优先级参数列表
    :param args:  独立参数信息，以元组形式给出
    :param kwargs: 参数信息，以字典形式给出
    :return:     返回优先级调整后的列表

    @changelog      2020-11-13 10:53:00  haibin.xu
                    1. 优化函数实现, 实现独立参数、关键字参数严格按照优先级列表排序的功能，如果同一个参数即出现在
                       独立参数列表中又出现在关键字参数字典中（一般不会有这种情况），则独立参数形式排在关键字参数
                       形式之前
    """
    rtn_param_list = []
    remain_args_list = [ar for ar in list(args) if ar != ' ']
    remain_kwargs_dict = copy.deepcopy(kwargs)
    for param in priority_params_list:
        param_in_args = get_match_parameter(param_pattern=param, params_list=remain_args_list)
        param_in_kwargs = get_match_parameter(param_pattern=param, params_dict=kwargs)
        if param_in_args:
            rtn_param_list.append(param_in_args)
            remain_args_list.remove(param_in_args)
        if param_in_kwargs:
            rtn_param_list.append(param_in_kwargs + '=' + str(kwargs[param_in_kwargs]))
            del remain_kwargs_dict[param_in_kwargs]

    return rtn_param_list, remain_args_list, remain_kwargs_dict


def concat_parameters(*args: tuple, **kwargs: dict) -> str:
    """
    author:         wei.yuan
    date:           2020.07.06
    description:    拼接可选参数与关键字参数
    :param args:    可选参数
    :param kwargs:  关键字参数
    :return:        返回拼接结果
    """
    concat_args_list, remain_args_list, remain_kwargs_dict = sort_parameters(*args, **kwargs)
    concat_args_list.extend(remain_args_list)
    count = 0
    temp_list = []
    if 'tshark' not in remain_args_list[0]:
        # linux系统
        for key in remain_kwargs_dict:
            print(key, ":", str(remain_kwargs_dict[key]))
            count += 1
            if count < len(remain_kwargs_dict):
                concat_args_list.append(key + ' ' + str(remain_kwargs_dict[key]) + ' and')
            else:
                concat_args_list.append(key + ' ' + str(remain_kwargs_dict[key]))
        concat_args_str = " ".join(concat_args_list)
    else:
        # windows系统
        for key in remain_kwargs_dict:
            print(key, ":", str(remain_kwargs_dict[key]))
            count += 1
            if count < len(remain_kwargs_dict):
                temp_list.append(key + ' ' + str(remain_kwargs_dict[key]) + ' and')
            else:
                temp_list.append(key + ' ' + str(remain_kwargs_dict[key]))
        temp_str = " ".join(temp_list)
        concat_args_str = " ".join(concat_args_list) + ' -f ' + '"' + temp_str + '"'

    return concat_args_str


# def handle_prn(word):
#     # word = bytes.decode(word)
#     import re
#     pat = r'\\x[0-9a-f]{2,3}'
#     data1 = re.sub(pat, '', word)
#     data_list = []
#     for line in data1.splitlines():
#         if re.match(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', line):
#             pass
#         else:
#             line = re.sub(r"\\[a-zA-Z]", "", line)
#             res = re.compile("[^\\u4e00-\\u9fa5^a-z^A-Z^0-9]")
#             data_list.append((re.sub(res, "", line)))
#     return data_list[-1]


# 解析包
def filters_data_packet(filter_file: str = "/root/packet.pcap"):
    """
    author: wei.yuan
    date: 2022年8月10日17:13:36
    description: 解析包
    :param filter_file: 包文件路径
    :return filter_data_packet_num,total_packet: 包个数，包的格式内容
    """
    cur_path = os.path.abspath(os.path.dirname(__file__))
    num_list = re.findall(r'([vp]m\d+)', cur_path)
    if num_list and ('vm' in num_list[0] or 'pm' in num_list[0]):
        vm = num_list[0]
        if len(vm) < 2 + 4:
            port = "8" + vm.replace("vm", "").replace("pm", "")
        else:
            port = vm.replace("vm", "").replace("pm", "")
    else:
        vm = "vm999"
        port = "8888"
    if os.name == 'nt':  # Windows
        vm_path = "{}{}".format(WINDOWS_FILE_PATH_ROOT, vm)
    else:
        vm_path = "{}{}".format(LINUX_FILE_PATH_ROOT, vm)
    if filter_file == "/root/packet.pcap":
        filter_file = "{}/packet.pcap".format(vm_path)

    total_packet = {}
    packet_num = 0
    import socket
    # 下面这行ubuntu环境会出core，注释掉
    # hostname = socket.gethostname()
    hostname = "127.0.0.1"
    ip = socket.gethostbyname(hostname)
    print('ip=============', ip)
    filter_data_packet = rdpcap(filter_file)
    filter_data_packet_num = len(filter_data_packet)
    for filter_data in filter_data_packet:
        packet_dict = {"Ether_dst": filter_data.sprintf("%Ether.dst%"),
                       "Ether_src": filter_data.sprintf("%Ether.src%"),
                       "IP_src": filter_data.sprintf("%IP.src%"), "IP_dst": filter_data.sprintf("%IP.dst%"),
                       "RAW": filter_data.sprintf("%Raw.load%")}
        packet_num += 1
        total_packet[f"packet{str(packet_num)}"] = packet_dict
    return filter_data_packet_num, total_packet


# 抓包
def sniff_packet(iface: str = None, proto: Union[str, int]=None, catch_num: str = None, src_ip: str = None,
                 timeout: int = 10, dst_ip: str = None, dst_port: str = None, src_port: str = None,
                 store_file: str = "/root/server_packet.pcap", filter_data_dict=None):
    """
    author: wei.yuan
    date: 2022年8月9日14:28:32
    description: 使用tcpdump 抓包
    :param iface: 指定的网卡
    :param proto: 协议内容或者协议代号
    :param catch_num: 抓包数量
    :param src_ip:源IP地址
    :param dst_ip: 目标IP地址
    :param dst_port: 目标端口号
    :param src_port: 源端口号
    :param timeout: 查看任务的退出时间，并在指定的时间进行退出
    :param store_file: 存储到指定的pcap文件中
    :param filter_data_dict: 需要额外补充的字典
    """
    print("sniff_packet")
    cur_path = os.path.abspath(os.path.dirname(__file__))
    num_list = re.findall(r'([vp]m\d+)', cur_path)
    if num_list and ('vm' in num_list[0] or 'pm' in num_list[0]):
        vm = num_list[0]
        if len(vm) < 2 + 4:
            port = "8" + vm.replace("vm", "").replace("pm", "")
        else:
            port = vm.replace("vm", "").replace("pm", "")
    else:
        vm = "vm999"
        port = "8888"
    if os.name == 'nt':  # Windows
        vm_path = "{}{}".format(WINDOWS_FILE_PATH_ROOT, vm)
    else:
        vm_path = "{}{}".format(LINUX_FILE_PATH_ROOT, vm)
    if store_file == "/root/server_packet.pcap":
        store_file = "{}/server_packet.pcap".format(vm_path)

    if filter_data_dict is None:
        filter_data_dict = {}
    import datetime
    print(datetime.datetime.now())
    global tcpdump_cmd
    # 对vlan网卡抓包时进行判断，如果为vlan网卡，不进行对ip地址，协议作为抓包条件
    if "." in iface:
        src_ip = None
        dst_ip = None
        proto = None
    print(platform)
    if 'win' not in platform:
        tcpdump_description = "tcpdump"
        tcpdump_args = ([], tcpdump_description, "-vv")
        tcpdump_list = list(tcpdump_args)
        kwargs = {}
        if catch_num:
            catch_num = f" -c {catch_num}"
            tcpdump_list.append(catch_num)
        if iface:
            iface_kwargs = f"-i {iface}"
            tcpdump_list.append(iface_kwargs)
        if src_ip:
            src_kwargs = {"src": src_ip}
            kwargs.update(src_kwargs)
        if dst_ip:
            dst_kwargs = {"dst": dst_ip}
            kwargs.update(dst_kwargs)
        if dst_port:
            dst_port_kwargs = {"dst port": dst_port}
            kwargs.update(dst_port_kwargs)
        if src_port:
            src_port_kwargs = {"src port": src_port}
            kwargs.update(src_port_kwargs)
        if len(filter_data_dict) != 0:
            kwargs.update(filter_data_dict)
        if proto and proto != "None" and proto != "null":
            if isinstance(proto, int):
                proto_info = {"proto": proto}
                kwargs.update(proto_info)
                tcpdump_cmd_args = tuple(tcpdump_list)
                tcpdump_cmd = concat_parameters(*tcpdump_cmd_args, **kwargs) + f" -w {store_file} -p"
                print(tcpdump_cmd)
            else:
                proto_info = 'ip6' if proto in ['icmpv6', 'ipv6'] else proto
                tcpdump_cmd_args = tuple(tcpdump_list)
                tcpdump_cmd = concat_parameters(*tcpdump_cmd_args, **kwargs) + f" -w {store_file} and {proto_info} -p"
        else:
            tcpdump_cmd_args = tuple(tcpdump_list)
            tcpdump_cmd = concat_parameters(*tcpdump_cmd_args, '-f', **kwargs) + f" -w {store_file} -p"
        if tcpdump_cmd.count("and") > 4:
            raise Exception(f"输入的参数超出上限，上限为4.引发异常。参数项个数为{len(kwargs)}")
        print("tcpdump_cmd:", tcpdump_cmd)
        obj = subprocess.Popen(tcpdump_cmd, shell=True, start_new_session=True,
                               close_fds=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(timeout)
        os.killpg(obj.pid, signal.SIGTERM)
    else:
        tcpdump_description = '"C:\\Program Files\\Wireshark\\tshark.exe"'
        tcpdump_args = ([], tcpdump_description)
        tcpdump_list = list(tcpdump_args)
        kwargs = {}
        # if proto:
        #     if isinstance(proto, int):
        #         proto_info = {"proto": proto}
        #         kwargs.update(proto_info)
        #         tcpdump_cmd_args = tuple(tcpdump_list)
        #         tcpdump_cmd = concat_parameters(*tcpdump_cmd_args, **kwargs) + f" -w {store_file}"
        #         print(tcpdump_cmd)
        #     else:
        #         proto_info = 'ip6' if proto in ['icmpv6', 'ipv6'] else proto
        #         tcpdump_cmd_args = tuple(tcpdump_list)
        #         tcpdump_cmd = concat_parameters(*tcpdump_cmd_args, **kwargs) + f" -w {store_file} and {proto_info}"
        # else:
        #     tcpdump_cmd_args = tuple(tcpdump_list)
        #     tcpdump_cmd = concat_parameters(*tcpdump_cmd_args, **kwargs) + f" -w {store_file}"
        # 下面为新增内容
        if catch_num:
            catch_num = f" -c {catch_num}"
            tcpdump_list.append(catch_num)
        if iface:
            iface_kwargs = f'-i "{iface}"'
            tcpdump_list.append(iface_kwargs)
        # src_kwargs = {"not": "arp"}
        # kwargs.update(src_kwargs)
        if src_ip:
            src_kwargs = {"src": src_ip}
            kwargs.update(src_kwargs)
        if dst_ip:
            dst_kwargs = {"dst": dst_ip}
            kwargs.update(dst_kwargs)
        if dst_port:
            dst_port_kwargs = {"dst port": dst_port}
            kwargs.update(dst_port_kwargs)
        if src_port:
            src_port_kwargs = {"src port": src_port}
            kwargs.update(src_port_kwargs)
        # if proto:
        #     if isinstance(proto, int):
        #         pass
        #     else:
        #         proto = 'ip6' if proto in ['icmpv6', 'ipv6'] else proto
        #     proto_kwargs = {"proto": proto}
        #     kwargs.update(proto_kwargs)
        if len(filter_data_dict) != 0:
            kwargs.update(filter_data_dict)
        tcpdump_cmd_args = tuple(tcpdump_list)
        tcpdump_cmd = concat_parameters(*tcpdump_cmd_args, **kwargs) + f" -w {store_file} -p"
        # tcpdump_cmd.replace('proto', '')

        print("tcpdump_cmd:", tcpdump_cmd)
        obj = subprocess.Popen(tcpdump_cmd, shell=True, start_new_session=True,
                               close_fds=False, stdout=None, stderr=None)
        time.sleep(timeout)
        taskkill_cmd = 'taskkill -f -t -im tshark.exe'
        subprocess.Popen(taskkill_cmd, shell=True, start_new_session=True,
                         close_fds=False)

    # 不指定proto时，会自动使用mac地址抓包， 此时删掉and会有tcpdump过滤器语法错误
    # if tcpdump_cmd.count("and") <= 1
    #     and (src_ip is None and src_port is None and dst_ip is None and dst_port is None):
    #     tcpdump_cmd = tcpdump_cmd.replace("and", "")
    # obj = subprocess.Popen(tcpdump_cmd, shell=True, start_new_session=True,
    #                        close_fds=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    cmd_output, cmd_stderr = obj.communicate(timeout=timeout)
    ret_code = obj.poll()
    try:
        if isinstance(cmd_output, bytes):
            cmd_output = cmd_output.decode('utf-8').rstrip()
    except UnicodeDecodeError:
        if isinstance(cmd_output, bytes):
            try:
                cmd_output = cmd_output.decode('gbk').rstrip()
            except UnicodeDecodeError:
                print("\033[44m Found UnicodeDecodeError!!!!!!!!!!!!!!!!!\033]0m")
                print('cmd_output: {}'.format(cmd_output))
                cmd_output = cmd_output.decode('utf-8', 'ignore').rstrip()
    try:
        if isinstance(cmd_stderr, bytes):
            cmd_stderr = cmd_stderr.decode('utf-8').rstrip()
    except UnicodeDecodeError:
        if isinstance(cmd_stderr, bytes):
            try:
                cmd_stderr = cmd_stderr.decode('gbk').rstrip()
            except UnicodeDecodeError:
                print("\033[44m Found UnicodeDecodeError!!!!!!!!!!!!!!!!!\033]0m")
                print('cmd_stderr: {}'.format(cmd_stderr))
                cmd_stderr = cmd_stderr.decode('utf-8', 'ignore').rstrip()
    filter_data_packet_num, total_packet = filters_data_packet(filter_file=store_file)
    return filter_data_packet_num, total_packet


def multiprocess_trigger(packet_header, data_len, iface: str, proto: Union[str, int]=None,
                         catch_num: str = None, sniff_src_ip: str = None,
                         timeout: int = 20, sniff_dst_ip: str = None, dst_port: str = None, src_port: str = None,
                         store_file: str = "/root/client_packet.pcap", transport_layer: int = 2, filter_data_dict=None,
                         tcpdump_enable: bool = True, count: int = 1, checksum_flag: bool = True):
    cur_path = os.path.abspath(os.path.dirname(__file__))
    num_list = re.findall(r'([vp]m\d+)', cur_path)
    if num_list and ('vm' in num_list[0] or 'pm' in num_list[0]):
        vm = num_list[0]
        if len(vm) < 2 + 4:
            port = "8" + vm.replace("vm", "").replace("pm", "")
        else:
            port = vm.replace("vm", "").replace("pm", "")
    else:
        vm = "vm999"
        port = "8888"
    if os.name == 'nt':  # Windows
        vm_path = "{}{}".format(WINDOWS_FILE_PATH_ROOT, vm)
    else:
        vm_path = "{}{}".format(LINUX_FILE_PATH_ROOT, vm)
    if store_file == "/root/client_packet.pcap":
        store_file = "{}/client_packet.pcap".format(vm_path)
    # 发包侧网卡监听
    if filter_data_dict is None:
        filter_data_dict = {}
    # 发包
    if packet_header is not None:
        send_thread = Thread(target=send_packet, args=(packet_header, data_len, transport_layer, iface, count,
                                                       checksum_flag, proto))
        # send_thread = Thread(target=structure_icmp_ping, args=(sniff_src_ip, sniff_dst_ip))
        if tcpdump_enable:
            listener_thread = Thread(target=sniff_packet,
                                     args=(iface, proto, catch_num,
                                           sniff_src_ip, timeout, sniff_dst_ip,
                                           dst_port, src_port, store_file, filter_data_dict))
            listener_thread.start()
            time.sleep(10)
        send_thread.start()
        if tcpdump_enable:
            listener_thread.join()
        send_thread.join()
    else:
        sniff_packet(iface, proto, catch_num, sniff_src_ip, timeout, sniff_dst_ip,
                     dst_port, src_port, store_file, filter_data_dict
                     )


def server_hike_ptp(device: str, time_out: int = 30, store_file: str = "/root/time_stamp_server.log"):
    """
    author: wei.yuan1
    date:2022.10.13
    description: 在server端拉起ptp监听程序
    :param device: 监听的网口名称
    :param time_out: 超时时间
    :param store_file: 存放日志的文件
    """
    exec_command = f"ptp4l -i {device} -m -H |tee {store_file}"
    print("server_hike_ptp -> exec_command:{},".format(exec_command))
    obj = subprocess.Popen(exec_command, shell=True, start_new_session=True,
                           close_fds=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(time_out)
    os.killpg(obj.pid, signal.SIGTERM)
    cmd_output, cmd_stderr = obj.communicate(timeout=time_out)
    try:
        if isinstance(cmd_output, bytes):
            cmd_output = cmd_output.decode('utf-8').rstrip()
    except UnicodeDecodeError:
        if isinstance(cmd_output, bytes):
            try:
                cmd_output = cmd_output.decode('gbk').rstrip()
            except UnicodeDecodeError:
                print("\033[44m Found UnicodeDecodeError!!!!!!!!!!!!!!!!!\033]0m")
                print('cmd_output: {}'.format(cmd_output))
                cmd_output = cmd_output.decode('utf-8', 'ignore').rstrip()
    try:
        if isinstance(cmd_stderr, bytes):
            cmd_stderr = cmd_stderr.decode('utf-8').rstrip()
    except UnicodeDecodeError:
        if isinstance(cmd_stderr, bytes):
            try:
                cmd_stderr = cmd_stderr.decode('gbk').rstrip()
            except UnicodeDecodeError:
                print("\033[44m Found UnicodeDecodeError!!!!!!!!!!!!!!!!!\033]0m")
                print('cmd_stderr: {}'.format(cmd_stderr))


def client_hike_ptp(device: str, time_out: int = 30, store_file: str = "/root/time_stamp_client.log"):
    """
    author: wei.yuan1
    date:2022.10.13
    description: 在client端拉起ptp监听程序
    :param device: 监听的网口
    :param time_out: 超时时间
    :param store_file: 存放日志的文件
    """
    exec_command = f"ptp4l -A -4 -H -i {device} -m -s | tee {store_file}"
    print("client_hike_ptp -> exec_command:{},".format(exec_command))
    obj = subprocess.Popen(exec_command, shell=True, start_new_session=True,
                           close_fds=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(time_out)
    os.killpg(obj.pid, signal.SIGTERM)
    cmd_output, cmd_stderr = obj.communicate(timeout=time_out)
    try:
        if isinstance(cmd_output, bytes):
            cmd_output = cmd_output.decode('utf-8').rstrip()
    except UnicodeDecodeError:
        if isinstance(cmd_output, bytes):
            try:
                cmd_output = cmd_output.decode('gbk').rstrip()
            except UnicodeDecodeError:
                print("\033[44m Found UnicodeDecodeError!!!!!!!!!!!!!!!!!\033]0m")
                print('cmd_output: {}'.format(cmd_output))
                cmd_output = cmd_output.decode('utf-8', 'ignore').rstrip()
    try:
        if isinstance(cmd_stderr, bytes):
            cmd_stderr = cmd_stderr.decode('utf-8').rstrip()
    except UnicodeDecodeError:
        if isinstance(cmd_stderr, bytes):
            try:
                cmd_stderr = cmd_stderr.decode('gbk').rstrip()
            except UnicodeDecodeError:
                print("\033[44m Found UnicodeDecodeError!!!!!!!!!!!!!!!!!\033]0m")
                print('cmd_stderr: {}'.format(cmd_stderr))


def sendp_tcp_packet(dst_mac, src_mac, dst_ip, src_ip, dport, sport, iface,
                     payload: int = 0, checksum_flag: bool = True, count: int = 1):
    if checksum_flag:
        if not payload:
            sendp([Ether(dst=dst_mac, src=src_mac) / IP(src=src_ip, dst=dst_ip) / TCP(
                sport=sport, dport=dport)], iface=iface, count=count)
        else:
            sendp([Ether(dst=dst_mac, src=src_mac) / IP(src=src_ip, dst=dst_ip) / TCP(
                sport=sport, dport=dport) / structure_socket_packet(payload)], iface=iface, count=count)
    else:
        pkt = Ether(dst=dst_mac, src=src_mac) / IP(src=src_ip, dst=dst_ip) / TCP(
                sport=sport, dport=dport) / structure_socket_packet(payload)
        pkt[TCP].chksum = 0
        sendp(pkt, iface=iface, count=count)


def sendp_udp_packet(dst_mac, src_mac, dst_ip, src_ip, dport, sport, iface,
                     payload: int = 0, checksum_flag: bool = True, count: int = 1):
    if checksum_flag:
        if not payload:
            sendp([Ether(dst=dst_mac, src=src_mac) / IP(src=src_ip, dst=dst_ip) / UDP(
                sport=sport, dport=dport)], iface=iface, count=count)
        else:
            sendp([Ether(dst=dst_mac, src=src_mac) / IP(src=src_ip, dst=dst_ip) / UDP(
                sport=sport, dport=dport) /structure_socket_packet(payload)], iface=iface, count=count)
    else:
        pkt = Ether(dst=dst_mac, src=src_mac) / IP(src=src_ip, dst=dst_ip) / UDP(
            sport=sport, dport=dport) / structure_socket_packet(payload)
        # todo UDP checksum如果为0，则表示不校验checksum，故此处不能设0
        pkt[UDP].chksum = 1
        sendp(pkt, iface=iface, count=count)


def sendp_sctp_packet(dst_mac, src_mac, dst_ip, src_ip, iface, payload: int = 0, checksum_flag: bool = True,
                      count: int = 1):

    if checksum_flag:
        if not payload:
            sendp([Ether(dst=dst_mac, src=src_mac) / IP(src=src_ip, dst=dst_ip) / SCTP()], iface=iface,
                  count=count)
        else:
            sendp([Ether(dst=dst_mac, src=src_mac) / IP(src=src_ip,
                                                        dst=dst_ip) / SCTP() / structure_socket_packet(payload)],
                  iface=iface, count=count)
    else:
        pkt = Ether(dst=dst_mac, src=src_mac) / IP(src=src_ip, dst=dst_ip) / SCTP() / structure_socket_packet(
            payload)
        pkt[SCTP].chksum = 0
        sendp(pkt, iface=iface, count=count)


# def sendp_tcp6_packet(dst_mac, src_mac, dst_ip, src_ip, iface, payload: int = 0, checksum_flag: bool = True,
#                       count: int = 1):
#     if checksum_flag:
#         if not payload:
#             sendp([Ether(dst=dst_mac, src=src_mac) / IPv6(src=src_ip, dst=dst_ip) / TCP()], iface=iface,
#                   count=count)
#         else:
#             sendp([Ether(dst=dst_mac, src=src_mac) / IPv6(src=src_ip,
#                   dst=dst_ip) / TCP() / structure_socket_packet(payload)],
#                   iface=iface, count=count)
#     else:
#         pkt = Ether(dst=dst_mac, src=src_mac) / IPv6(src=src_ip, dst=dst_ip) / TCP() / structure_socket_packet(
#             payload)
#         pkt[TCP].chksum = 0
#         sendp(pkt, iface=iface, count=count)


def structure_socket_packet(length_of_string: int):
    """
    author: wei.yuan
    date:   2022-07-28
    description: 构造网络包报文
    """
    import string
    random_string = ""
    # random_string = "".join(random.choice(string.ascii_letters + string.digits
    #                                      ) for _ in range(length_of_string))
    string_list = ["s", "x", "e"]
    # sxe -> 737865
    for i in range(length_of_string):
        random_string += string_list[i % 3]
    return random_string


handler = RPCHandler()
handler.register_function(structure_icmp_ping)
handler.register_function(send_packet)
handler.register_function(sniff_packet)
handler.register_function(structure_ip_ping)
handler.register_function(multiprocess_trigger)
handler.register_function(server_hike_ptp)
handler.register_function(client_hike_ptp)
handler.register_function(end_socket)
handler.register_function(sendp_tcp_packet)
handler.register_function(sendp_udp_packet)
handler.register_function(sendp_sctp_packet)
# handler.register_function(sendp_tcp6_packet)
# Run the server
# 下面这行ubuntu环境会出core，注释掉
# hostname = socket.gethostname()
hostname = "127.0.0.1"
ip = socket.gethostbyname(hostname)
rpc_port = 8888
if len(sys.argv) != 1:
    if len(sys.argv) != 3:
        print("Usage: python3 rpc_server.py <ip> <port>")
        exit(1)
    elif "." not in sys.argv[1]:
        print("Usage: python3 rpc_server.py <ip> <port>")
        exit(1)
    else:
        ip = sys.argv[1]
        rpc_port = int(sys.argv[2])

rpc_server(handler, (ip, rpc_port))
# filter_data = {"host": "11:22:33:44:55:66"}
# multiprocess_trigger(
#     iface="ens1f0",
#     packet_header="",
#     data_len=100,
#     timeout=50,
#     transport_layer=3,
#     filter_nic_data=filter_data
# )
# server_hike_ptp("ens1f0", 30)
