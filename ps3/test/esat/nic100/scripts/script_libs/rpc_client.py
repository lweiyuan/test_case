
import pickle
import socket
import os
import re
import argparse
from scapy.all import *
from multiprocessing.connection import Client, Listener
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse
from scripts.script_libs.command_operation import CommandOperation


# TODO 本方法存在缺陷，multiprocessing模块对于win32支持有差异，使用当前代码会报错digest sent was rejected
# TODO 目前未找到可行的解决方案，怀疑是multiprocessing.Manager存在问题，但一般代码机均为Linux,基本不会暴露问题


class RPCProxy:
    def __init__(self, connection):
        self._connection = connection

    def get_proxy(self):
        proxy = RPCProxy(self._connection)
        return proxy

    def __getattr__(self, name):
        def do_rpc(*args, **kwargs):
            self._connection.send(pickle.dumps((name, args, kwargs)))
            result = pickle.loads(self._connection.recv())
            if isinstance(result, Exception):
                raise result
            return result

        return do_rpc


def manger_d():
    print("~~~~~~~~~~~manager")
    d = Client(('10.17.91.254', 8888))
    proxy = RPCProxy(d).get_proxy()
    filter_data_packet_num, total_packet = proxy.sniff_packet(iface="ens1f0", proto="icmp", dst_ip="192.168.100.254",
                                                              timeout=60)
    print(filter_data_packet_num)
    print(total_packet)
    # pkts = proxy.structure_sniff(packet_filter="host 10.17.91.253 and icmp and not broadcast", iface="eno1")
    # pkts.show()
    # pkts.nsummary(lambda r: r.sprintf("version:%IP.version%\n{IP:%IP.src% -> %IP.dst%}\n{Raw:%Raw.load%\n}"))


# 调用方法举例，参数仅需要指定client的ip以及具体调用方法内的参数，如src dst
def client_c():
    print("~~~~~~~~~~~client")
    c = Client(('10.17.91.253', 8888))
    proxy = RPCProxy(c).get_proxy()
    # proxy.structure_icmp_ping(ip="192.168.100.254")
    # proxy.structure_ip_ping(src_ip="10.17.91.253", dst_ip="10.17.91.254")

    # proxy.structure_icmp_scan(iprange="10.17.91.*")
    # proxy.structure_icmp_packet(src='192.168.100.253', dst='192.168.100.254')
    filter_data_packet_num, total_packet = proxy.multiprocess_trigger(iface="ens1f0", proto="tcp",
                                                                      dst_ip="192.168.100.254",
                                                                      src_ip="192.168.100.253")
    print("filter_data_packet_num, total_packet:", filter_data_packet_num, total_packet)
    print("~~~~~~~~~~~client")


def scapy_transport_packet():
    manager = SxeThread(manger_d)
    client = SxeThread(client_c)
    # print("~~~~~~~~~~~")
    manager.start()
    time.sleep(3)
    client.start()
    client.join()
    manager.join()


server_port = 8888
#  获取本地服务器的计算机名称
hostname = socket.gethostname()
# 获取本机的ip地址
current_ipv4 = socket.gethostbyname(hostname)


def server_receive_informatin():
    """
    author: wei.yuan
    date: 2022.08.05
    description: 在本地拉起一个socket服务器，仅用来接收数据
    """
    import socket
    import time

    tcp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
    buffer_size = 4096 * 10
    tcp_socket.bind((current_ipv4, server_port))
    receive_data = ""
    begin_time = time.time()
    client_socket, clientAddr = tcp_socket.accept()
    while True:
        content, addr = client_socket.recvfrom(buffer_size)
        now_time = time.time()

        # 如果没有看到结束标记
        # ，继续循环获取
        if 'SXETESTEND' not in content.decode():
            continue

        # 如果收到结束标记，中断循环
        elif 'SXETESTEND' in content.decode():
            receive_data = content.decode().replace('SXETESTEND', '')
            break

        # 如果循环超过60s，中断循环，防止网卡问题导致死循环
        elif now_time - begin_time > 60:
            break

        # 其他情形
        else:
            continue
    client_socket.close()
    tcp_socket.close()


def multiprocess_deal_task():
    """
    author: wei.yuan
    date: 2022.08.05
    description: 调用多进程来处理，进程一 拉起socket服务机制，进程二 进行负责抓包
    """
    import multiprocessing
    task1 = multiprocessing.Process(target=server_receive_informatin)
    task2 = multiprocessing.Process(target=scapy_transport_packet)
    task1.start()
    task2.start()
    task2.join(timeout=30)
    task1.join()
    task1.kill()


def client_send_informatin(server_tuple: (current_ipv4, server_port)):
    """
    author: wei.yuan
    date: 2022.08.05
    description: 从client端发送
    :param server_tuple: (server_addr, port)
    """
    import os
    import time
    import platform
    import socket
    tcp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
    os_name = platform.platform().lower()
    tcp_socket.connect(server_tuple)
    python_cmd = "python3 /root/sniff_test.py"
    msg = os.system(python_cmd)
    if 'windows' in os_name:
        tcp_socket.send(msg.encode('gbk'))
        tcp_socket.send('SXETESTEND'.encode('gbk'))
        recv_data = tcp_socket.recv(102400)
    else:
        tcp_socket.send(msg.encode('utf-8'))
        tcp_socket.send('SXETESTEND'.encode('utf-8'))
        recv_data = tcp_socket.recv(102400)
    tcp_socket.close()


def manager_task():
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
    vm_path = "/root/sxetest/{}".format(vm)
    server_command = "python3 {}/rpc_server.py".format(vm_path)
    rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
        server_command, ssh_ip=CommandLineArgsParse.get_server_node_ip(),
        ssh_port=str(CommandLineArgsParse.get_server_port()), ssh_username="root")


def client_task():
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
    vm_path = "/root/sxetest/{}".format(vm)
    server_command = "unbuffer nohup python3 {}/rpc_server.py".format(vm_path) + ">test.txt 2>&1 &"
    client_rtn_code, client_rtn_outputs, client_rtn_err = CommandOperation.execute_command_with_error(
        server_command, ssh_ip=CommandLineArgsParse.get_client_node_ip(),
        ssh_port=str(CommandLineArgsParse.get_client_port()), ssh_username="root")


if __name__ == '__main__':
    from scripts.script_libs.script_base import SxeThread
    from pykeyboard import PyKeyboard
    import time

    k = PyKeyboard()

    k.press_key(k.enter_key)
    manager = SxeThread(manager_task)

    client = SxeThread(client_task)
    scapy_packet = SxeThread(scapy_transport_packet)
    scapy_transport_packet()
    # scapy_packet.setDaemon(True)
    # manager.start()
    # time.sleep(4)
    #
    # client.start()
    # time.sleep(4)
    # scapy_packet.start()
    # while True:
    #     if not scapy_packet.is_alive():
    #         time.sleep(5)
    #         server_command = "pkill -ef python3"
    #         CommandOperation.execute_command_with_error(
    #             server_command, ssh_ip=CommandLineArgsParse.get_server_node_ip(),
    #             ssh_port=str(CommandLineArgsParse.get_server_port()), ssh_username="root")
    #         CommandOperation.execute_command_with_error(
    #             server_command, ssh_ip=CommandLineArgsParse.get_client_node_ip(),
    #             ssh_port=str(CommandLineArgsParse.get_client_port()), ssh_username="root")
    #         break
    #
    #     else:
    #         continue
