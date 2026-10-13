# coding=utf-8
"""
version: 1.0.0
date: 2024.08.28

使用说明：
1. 使用socket通讯，每个client连接时创建一个文件
1. 所有创建的对象需要以obj_开头
2. 调用接口方式与pyverbs相同，工具不记录对象由哪个设备创建，需要脚本自行维护
3. 通过mem_alloc.malloc申请的内存对象需要以obj_buf开头
4. exit退出交互式工具，并释放所有资源

脚本中的server:
    脚本自己，即测试机中的ipvbs_s.py进程，作为socket server
脚本中的client:
    ps3server中实例化出来的对象，作为socket client
rdma_dict与glb_dict：
    1. 变量不重叠
    2. rdma_dict: 变量以obj_开头。不同的socket client之间dict不同
    3. glb_dict: 变量以glb_开头。整个class共享
多线程：
    self.active_clients:
        保存当前ipvbs连接的ps3server的所有socket client
特殊命令：
    clear_obj:
        清除rdma_dict中资源（清除当前socket连接的obj_资源，不同socket之间的obj_资源相互独立）
    close_socket:
        关闭与socket client的连接
    exit:
        清除rdma_dict中资源（清除当前socket连接的obj_资源，不同socket之间的obj_资源相互独立）
        关闭与socket client的连接
    shutdown:
        关闭与所有socket client的连接
        关闭socket server
        清除所有rdma_dict中资源（不同socket之间的obj_资源相互独立）
        清除glb_dict中资源
        退出python进程
debug:
    1. 在10.22.66.227执行ps -ef获取socket server的端口号8999：python3 ipvbs_s.py ... --port 8999
    2. 在10.22.67.4执行telnet 10.22.66.227 8999
    3. 在telnet交互式窗口中执行self.rdma_dicts.keys(), 获取socket client端口号2001
    4. 在telnet交互式窗口中执行self.rdma_dicts[2001]['obj_qp1_server'].query(0)[0]

eg.
obj_ctx = device.Context(name='mlx5_0')
obj_pd1 = pd.PD(creator=obj_ctx)
obj_buf = mem_alloc.malloc(100)
obj_mr1 =  mr.MR(creator=obj_pd1, length=100, access=enums.ibv_access_flags.IBV_ACCESS_LOCAL_WRITE.value, address=obj_buf, implicit=False)
obj_mr1.length
obj_mr1.write(data='asdfghjkl', length=10)
obj_mr1.read(10, 0).decode()
obj_mr1.close()
mem_alloc.free(obj_buf)
"""

import copy
import re
import datetime
import os
import socket
import subprocess
import threading
from re import findall
from traceback import format_exc
from pyverbs import device, pyverbs_error, pd, mem_alloc, addr, mr, cq, wr, qp, srq
from pyverbs import pyverbs_error
from collections import defaultdict
import signal
import time
from string import *
from random import *
import atexit
import argparse
import concurrent.futures

rc_59 = False
rc_51 = False
status, result = subprocess.getstatusoutput('echo $PYTHONPATH')
if 'rdma-core-59.0' in result:
    rc_59 = True
elif 'rdma-core-51.0' in result:
    rc_51 = True
else:
    pass
if rc_59:
    from pyverbs import libibverbs_enums
    from pyverbs.libibverbs_enums import *
elif rc_51:
    from pyverbs import enums
    from pyverbs.enums import *
else:
    from pyverbs import enums
    from pyverbs.enums import *

VERSION = '2025.0908.1'
CLOSE_LST = [
    "<class 'pyverbs.mr.MR'>",
    "<class 'pyverbs.mr.MW'>",
    "<class 'pyverbs.pd.PD'>",
    "<class 'pyverbs.qp.QP'>",
    "<class 'pyverbs.device.Context'>"
]


# def eval_with_timeout(expression, timeout=5):
#     def timeout_handler(signum, frame):
#         raise TimeoutError(f"代码执行超时({timeout})")
#
#     signal.signal(signal.SIGALRM, timeout_handler)
#     signal.alarm(timeout)  # 设置超时时间
#
#     try:
#         result = eval(expression)  # 执行eval
#         signal.alarm(0)  # 取消超时
#         return result
#     except TimeoutError:
#         # print(f"超时({timeout})!")
#         return 'timeout'
#
# def exec_with_timeout(expression, timeout=5):
#     def timeout_handler(signum, frame):
#         raise TimeoutError(f"代码执行超时({timeout})")
#
#     signal.signal(signal.SIGALRM, timeout_handler)
#     signal.alarm(timeout)  # 设置超时时间
#
#     try:
#         result = exec(expression)  # 执行exec
#         signal.alarm(0)  # 取消超时
#         return result
#     except TimeoutError:
#         # print(f"超时({timeout})!")
#         return 'timeout'

# def eval_cmd(expression):
#     result = eval(expression)  # 执行eval
#     return result
#
# def exec_cmd(expression):
#     result = exec(expression)  # 执行exec
#     return result


class Ipvbs:
    def __init__(self, server_addr, port: int, exec_addr: str, log_path: str, debug_flag=0) -> None:
        """

        """
        # port_str = format(port, '05d')
        # if port_str[1] == '2':
        #     machine = "pm" + port_str[2:] + '_' + exec_addr
        # else:
        #     machine = 'vmx' + port_str[2:] + '_' + exec_addr
        #
        now = datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
        # log_folder = '/home/pyverbs_log/' + machine + '/' + now + '/'
        log_folder = os.path.join(log_path, now)
        os.makedirs(log_folder, exist_ok=True)
        self.log_folder = log_folder
        self.glb_log = os.path.join(self.log_folder, self.log_folder.split('/')[-1] + '_glb_log')
        self.dmesg_log = os.path.join(self.log_folder, self.log_folder.split('/')[-1] + '_dmesg_log')
        self.port = port
        self.glb_dict = dict()
        self.server_addr = server_addr
        self.active_clients = set()
        self.server_socket = None
        self.rdma_dicts = defaultdict(dict)
        self.debug_flag = debug_flag
        self.cmd_timeout = 3
        signal.signal(signal.SIGTERM, self.__exit__)

    def print_log(self, log_path, cmd, status, *args):
        """
        自定义print函数，将消息打印到控制台和文件。
        如果文件大小超过max_file_size，则创建新文件。
        """
        # 获取当前时间
        # max_file_size = 200 * 1024 * 1024
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 构造带时间戳的消息
        timed_message = f'[{now}] execute: {cmd}\n'
        timed_message += f'[{now}] status: {status}\n'
        for arg in args:
            timed_message += f'{arg}\n'
        timed_message += '#####RESULTEND######\n'

        with open(log_path, 'a') as file:
            file.write(timed_message + '\n')
        # if len(timed_message) > 2048:
        #     timed_message = f'[{now}] execute: {cmd}\n'
        #     timed_message += f'[{now}] status: {status}\n'
        #     timed_message += f'status length longer than 2048, check log please, path: {log_path}\n'
        #     timed_message += '#####RESULTEND######\n'
        #     timed_message += '\n'
        timed_message += log_path + '\n'
        # timed_message += (log_path + ';' + '\n')
        return timed_message

    def split_string(self, input_cmd):
        cmd_lst = []
        d_quot = False
        s_quot = False
        start = 0
        input_cmd = input_cmd.strip()
        length = len(input_cmd)
        index = 0
        while index < length:
            s = input_cmd[index]
            # for index, s in enumerate(input_cmd):
            if s == '"' and not d_quot:
                d_quot = True
            elif s == '"' and d_quot:
                d_quot = False
            if s == "'" and not s_quot:
                s_quot = True
            elif s == "'" and s_quot:
                s_quot = False
            if s == ';' and d_quot is False and s_quot is False:
                cmd_lst.append(input_cmd[start:index].strip())
                start = index + 1
                index += 1
            elif index == len(input_cmd) - 1:
                cmd_lst.append(input_cmd[start:index + 1].strip())
            index += 1

        return cmd_lst

    def clear_resources(self, exc_dict):
        obj_cmd = 'None'
        rtn_lst = []
        for obj_name, test_obj in exc_dict.items():
            try:
                obj_type = str(type(test_obj))
                if obj_type == "<class 'int'>" and 'buf' in obj_name:
                    obj_cmd = f"mem_alloc.free(exc_dict['{obj_name}'])"
                    result = eval(obj_cmd)
                    print(obj_cmd)
                    rtn_lst.append(self.print_log(self.glb_log, f'mem_alloc.free({obj_name})', 'success', result))
                else:
                    obj_cmd = f"exc_dict['{obj_name}'].close()"
                    print(obj_cmd)
                    result = eval(obj_cmd)
                    rtn_lst.append(self.print_log(self.glb_log, f'{obj_name}.close()', 'success', result))
            except pyverbs_error.PyverbsUserError:
                rtn_lst.append(self.print_log(self.glb_log, obj_cmd, 'failure', 'PyverbsUserError:', format_exc()))
            except pyverbs_error.PyverbsRDMAError:
                rtn_lst.append(self.print_log(self.glb_log, obj_cmd, 'failure', 'PyverbsError', format_exc()))
            except AttributeError:
                rtn_lst.append(self.print_log(self.glb_log, obj_cmd, 'failure', 'AttributeError:', format_exc()))
            except Exception:
                rtn_lst.append(self.print_log(self.glb_log, obj_cmd, 'failure', 'Exception:', format_exc()))
        rtn_str = ''
        for rtn in rtn_lst:
            rtn_str = '\n'.join(rtn)
        return rtn_str

    def response(self, cmd_lst, log_path, client_socket, rdma_dict):
        resp_lst = []
        for cmd in cmd_lst:
            try:
                if 'timeout' in cmd and '.timeout' not in cmd and 'timeout=' not in cmd:
                    res = re.findall(r'timeout(\d+)s', cmd)
                    if res:
                        self.cmd_timeout = int(res[0])
                        cmd = cmd.replace(f'timeout{self.cmd_timeout}s ', '')
                    else:
                        resp_lst.append(self.print_log(log_path, cmd, 'failure', 'timeout format error', format_exc()))
                        continue

                # 内核态命令处理
                if 'scgbe_utest' in cmd or 'sxe2_utest' in cmd or 'sxe3_utest' in cmd:
                    # resp_lst.append(self.print_log(log_path, cmd, 'success', f"============{cmd}"))
                    cmd_list = ['dmesg -C', cmd, 'dmesg -T|grep -v "speed is unknown"']
                    # cmd_2 = cmd
                    # cmd_3 = 'dmesg -T|grep -v "speed is unknown"'
                    cmd_new = ';'.join(cmd_list)
                    status, result = subprocess.getstatusoutput(cmd_new)
                    self.print_log(self.dmesg_log, cmd_new, 'success', result)

                    # status, result = subprocess.getstatusoutput('dmesg -C')
                    # status_1, result_1 = subprocess.getstatusoutput(cmd)
                    # status_2, result_2 = subprocess.getstatusoutput('dmesg|grep -v "speed is unknown"')
                    cmd_index = int(cmd.split(' ')[-1])
                    cmd_str = " ".join(cmd.split(' ')[1:-1]).replace('"', '').replace("'", "")
                    if cmd_index in [1,
                                     7,
                                     9, 10, 11, 12, 13, 14, 15,
                                     18,
                                     20, 21,
                                     23, 24,
                                     27, 28, 29,
                                     33, 34, 35,
                                     37,
                                     40, 41,
                                     43, 44,
                                     56, 57]:
                        obj_name = cmd_str.split(" ")[-1]
                        if 'obj' in obj_name:
                            rdma_dict[obj_name] = result
                        else:
                            self.glb_dict[obj_name] = result
                    if 'Response from kernel: Fail' in result:
                        resp_lst.append(self.print_log(log_path, cmd, 'failure', result))
                    else:
                        resp_lst.append(self.print_log(log_path, cmd, 'success', result))
                    continue

                # 用于debug
                if "self.rdma_dicts" in cmd:
                    result = eval(cmd)
                    resp=self.print_log(log_path, cmd, 'success', result)
                    client_socket.sendall(resp.encode('utf-8'))
                    return

                if cmd == 'clear_obj':
                    self.clear_resources(rdma_dict)
                    self.print_log(log_path, cmd, 'success', f"[{client_socket}] clear all obj.")
                elif cmd == 'close_socket':
                    client_socket.close()
                    self.print_log(log_path, cmd, 'success', f"[{client_socket}] close socket.")
                elif cmd == 'exit':
                    self.clear_resources(rdma_dict)
                    client_socket.close()
                    self.print_log(log_path, cmd, 'success', f"[{client_socket}] clear all obj and close socket.")
                elif cmd == 'shutdown':
                    self.global_shutdown(log_path)
                # 如果输入的指令是：对象名=类名.方法名(para1=**, para2=**), 则执行方法并将新创建的对象存到字典rdma_dict中, 输出返回结果
                elif findall(r'^[a-zA-Z0-9_.]+\s*=.*\)$', cmd) or findall(r'^\w+\s*=.*', cmd):
                    new_obj_name = cmd.split('=')[0].strip()
                    func_str = cmd[cmd.find('=') + 1:].strip()
                    replace_names = findall(rf'((?:obj|glb)_\w+)', func_str)
                    if replace_names:
                        exec_cmd = func_str
                        replace_set = set(replace_names)
                        for replace_name in replace_set:
                            if 'obj' in replace_name:
                                exec_cmd = exec_cmd.replace(replace_name, f"rdma_dict['{replace_name}']")
                            else:
                                exec_cmd = exec_cmd.replace(replace_name, f"self.glb_dict['{replace_name}']")
                    else:
                        exec_cmd = func_str
                    result = eval(exec_cmd)
                    if 'obj' in new_obj_name:
                        rdma_dict[new_obj_name] = result
                    else:
                        self.glb_dict[new_obj_name] = result
                    resp_lst.append(self.print_log(log_path, cmd, 'success', result))
                # 如果输入的指令是：类名.方法名(para1=**, para2=**), 则执行方法并输出返回结果
                elif findall(r'\(.*\)', cmd):
                    replace_names = findall(rf'((?:obj|glb)_\w+)', cmd)
                    if replace_names:
                        exec_cmd = cmd
                        replace_set = set(replace_names)
                        for replace_name in replace_set:
                            if 'obj' in replace_name:
                                exec_cmd = exec_cmd.replace(replace_name, f"rdma_dict['{replace_name}']")
                            else:
                                exec_cmd = exec_cmd.replace(replace_name, f"self.glb_dict['{replace_name}']")
                    else:
                        exec_cmd = cmd
                    result = eval(exec_cmd)
                    del_lst = ['free', 'close']
                    if any(word in exec_cmd for word in del_lst):
                        # rdma_dict[replace_names[0]] = None
                        rdma_dict.pop(replace_names[0], '')
                    resp_lst.append(self.print_log(log_path, cmd, 'success', result))
                # 如果输入的指令是类名.对象名，打印这个对象信息
                else:
                    replace_names = findall(rf'((?:obj|glb)_\w+)', cmd)
                    exec_cmd = cmd
                    if replace_names:
                        replace_set = set(replace_names)
                        for replace_name in replace_set:
                            if 'obj' in replace_name:
                                exec_cmd = exec_cmd.replace(replace_name, f"rdma_dict['{replace_name}']")
                            else:
                                exec_cmd = exec_cmd.replace(replace_name, f"self.glb_dict['{replace_name}']")
                    if '=' in exec_cmd:
                        result = exec(exec_cmd)
                    else:
                        result = eval(exec_cmd)
                    resp_lst.append(self.print_log(log_path, cmd, 'success', result))
            except pyverbs_error.PyverbsUserError:
                resp_lst.append(self.print_log(log_path, cmd, 'failure', 'PyverbsUserError:', format_exc()))
            except pyverbs_error.PyverbsRDMAError:
                resp_lst.append(self.print_log(log_path, cmd, 'failure', 'PyverbsError:', format_exc()))
            except AttributeError:
                resp_lst.append(self.print_log(log_path, cmd, 'failure', 'AttributeError:', format_exc()))
            except Exception:
                resp_lst.append(self.print_log(log_path, cmd, 'failure', 'Exception:', format_exc()))

        # from queue import Queue
        # import threading
        #
        # # 消息队列
        # send_queue = Queue()
        # stop_event = threading.Event()
        #
        # def sender_thread(sock):
        #     while not stop_event.is_set():
        #         data = send_queue.get()  # 阻塞获取数据
        #         sock.sendall(data)
        #
        # # 其他线程通过队列提交数据
        # def worker_thread(data):
        #     send_queue.put(data)

        # 发送响应
        for resp in resp_lst:
            print(f"send resp：{resp}")
            client_socket.sendall(resp.encode('utf-8'))
            # for i in range(0, len(resp), 2000):
            #     client_socket.sendall(resp[i * 2000: (i + 1) * 2000].encode('utf-8'))
            # # 启动独立发送线程
            # # sock = socket.socket()
            # worker_thread(f'{resp};'.encode('utf-8'))
            # sender = threading.Thread(target=sender_thread, args=(client_socket,))
            # sender.start()


    def handle_client(self, client_socket, client_address):
        print(f"Accepted connection from {client_address}")
        cli_port = client_address[1]
        rdma_dict = {}
        self.rdma_dicts[cli_port] = rdma_dict
        log_path = os.path.join(self.log_folder, self.log_folder.split('/')[-1] + '_obj_log_client_' + format(cli_port, '05d'))
        try:
            while True:
                # 阻塞等待接收数据
                data = client_socket.recv(2048).decode('utf-8')
                if not data:
                    break
                else:
                    print(f"Accepted data：{data}")
                cmd_lst = self.split_string(data)
                self.response(cmd_lst, log_path, client_socket, rdma_dict)

        except ConnectionResetError:
            print(f"Connection closed by {client_address}")
        except Exception as e:
            print(f"Error handling client {client_address}: {e}")
        finally:
            print('----------------------fin clear---------------------------')
            self.active_clients.discard(client_socket)
            client_socket.close()
            if self.debug_flag == 0:
                self.clear_resources(rdma_dict)
                del self.rdma_dicts[cli_port]
                self.print_log(log_path, 'exit', 'success', f"Connection from {client_address} has been closed")

    def start_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((self.server_addr, self.port))
            self.server_socket.listen(2048)
            print(f"Server listening on {self.server_addr}:{self.port}")
            print(type(self.server_socket))
            while True:
                # 若创建server socket失败，break
                if type(self.server_socket) != socket.socket:
                    print(f'Server create socket {self.server_addr}:{self.port} failed!')
                    break
                # 阻塞等待socket client连接
                client_socket, client_address = self.server_socket.accept()
                # 有socket client连接时，在线程中处理
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket, client_address))
                self.active_clients.add(client_socket)
                client_thread.isDaemon()
                client_thread.start()
        except OSError:
            print(f'Server bind {self.server_addr}:{self.port} failed!')  # 套接字可能已经关闭或不存在

    def global_shutdown(self, log_path):
        # 关闭与所有socket client的连接
        for client_socket in list(self.active_clients):
            try:
                client_socket.shutdown(socket.SHUT_RDWR)  # 关闭套接字
            except OSError:
                pass  # 套接字可能已经关闭或不存在
            client_socket.close()  # 确保关闭套接字
        self.active_clients.clear()  # 清空活动集合
        # 关闭socket server
        self.server_socket.shutdown(socket.SHUT_RDWR)
        # 清空所有obj资源
        for cli_port, rdma_dict in self.rdma_dicts.items():
            self.clear_resources(rdma_dict)
            if self.rdma_dicts.get(cli_port):
                self.rdma_dicts[cli_port].clear()
        # 清空glb资源
        self.clear_resources(self.glb_dict)
        self.glb_dict.clear()

        self.print_log(log_path, 'shutdown', "success", "All client connections close, All resource clear, exiting server.")
        # 退出python进程
        sys.exit(0)

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        print('----------------------exit clear---------------------------')
        for key, rdma_dict in self.rdma_dicts.items():
            self.clear_resources(rdma_dict)
        self.clear_resources(self.glb_dict)


if __name__ == '__main__':
    import sys

    arg_parser = argparse.ArgumentParser(description="A socket server for pyverbs.")
    arg_parser.add_argument('-i', '--ip', required=True, help='ipvbs server IP')
    arg_parser.add_argument('-p', '--port', required=True, type=int, help='ipvbs server port')
    arg_parser.add_argument('-a', '--addr', required=True, help='ipvbs server execute addr [s/c]')
    arg_parser.add_argument('-d', '--debug',type=int, default=0, help='1-debug模式； 0-正常模式')
    arg_parser.add_argument('-lp', '--log_path',type=str, default='', help='指定日志路径')

    args = vars(arg_parser.parse_args())
    ipvbs = Ipvbs(args['ip'], args['port'], exec_addr=args['addr'], log_path=args['log_path'], debug_flag=args['debug'])
    with ipvbs:
        ipvbs.start_server()
