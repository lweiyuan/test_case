#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
远程串口操作类
author:      sunql
date:        2022.1.10
示例：
--------------------hba---------------------------

out = SocketOption.exec_socket_cmd('cli /c0 show', '10.22.112.40', 6500)
print(out)

--------------------raid--------------------------

out = SocketOption.exec_socket_cmd('ps -ef', '10.22.106.182', 6200, eof_key="]#")
print(out)

"""
import add_syspath
import re
import socket
import time
from threading import Thread
from scripts.script_libs import log
from scripts.script_libs import constants
from scripts.script_libs.enums import CmdExecuteAdressEnum


class MyThread(Thread):
    def __init__(self, target, args=()):
        """
            因为threading类没有返回值,因此在此处重新定义MyThread类,使线程拥有返回值
        """
        super(MyThread, self).__init__()
        self.func = target
        self.args = args

    def run(self):
        # 接受返回值
        self.result = self.func(*self.args)

    def get_result(self):
        # 线程不结束,返回值为None
        try:
            return self.result
        except Exception:
            return None


def limit_decor(timeout, granularity):
    """
        timeout 最大允许执行时长, 单位:秒
        granularity 轮询间隔，间隔越短结果越精确同时cpu负载越高
        return 未超时返回被装饰函数返回值,超时则返回 -1
    """

    def functions(func):
        def run(*args):
            thre_func = MyThread(target=func, args=args)
            thre_func.setDaemon(True)
            thre_func.start()
            sleep_num = int(timeout // granularity)
            for i in range(0, sleep_num):
                infor = thre_func.get_result()
                if infor:
                    return infor
                else:
                    time.sleep(granularity)
            return '-1'

        return run

    return functions


class SocketInteraction:

    def __init__(self, host, port, pwd_key, password, eof_key):
        """

        :param host:
        :param port:
        :param pwd_key: 输入密码标记
        :param password: 串口密码
        :param eof_key: 命令执行结束标记
        """
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.connect((host, port))
        self.pwd_key = pwd_key
        self.password = password
        self.eof_key = eof_key

    def __del__(self):
        self.tcp_socket.close()

    def close(self):
        self.tcp_socket.close()

    def recvline(self):
        return self.recvuntil('\n')

    def recv_n(self, n):
        # print(self.tcp_socket.recv(n))
        s = self.tcp_socket.recv(n)
        try:
            return s.decode('utf8')
        except Exception as e:
            return s.decode('utf16')

    def recvuntil(self, want_end_str):
        current_str = ''
        while True:
            current_str += self.recv_n(1)
            if current_str.endswith(want_end_str):
                return current_str

    def recvuntil_re(self, want_re_str):
        current_str = ''
        while True:
            current_str += self.recv_n(1)
            s = re.search(want_re_str, current_str)
            if s:
                return [current_str, s]

    def send(self, send_str):
        final_bytes = send_str.encode('utf8')
        self.tcp_socket.send(final_bytes)

    def sendline(self, send_str):
        self.send(send_str + '\n')

    def interact(self, cmd, timeout=10):
        @limit_decor(timeout, 1)
        def recv_loop(cmd):
            flag = True
            info = ''
            while True:
                c = self.recv_n(2)
                info += c
                if self.pwd_key and self.pwd_key in info:
                    self.sendline(self.password)
                    info = ''
                if self.eof_key in info and flag:
                    self.sendline(cmd)
                    flag = False
                    info = ''
                if self.eof_key in info:
                    return info.strip()

        self.sendline('')
        return recv_loop(cmd)


class SocketOption(object):

    @classmethod
    def exec_socket_cmd(cls, cmd, socket_ip=None, socket_port=None, timout: int = 30, retry_max: int = 2,
                        pwd_key: str = 'password:', password: str = 'q1w2e#', eof_key: str = 'PS3>',
                        excute_address: str = CmdExecuteAdressEnum.SERVER.value, filter: bool = True) -> str:
        """
        通过串口执行命令，返回 -1 为执行失败
        :param cmd:  需要执行的命令
        :param socket_ip:  串口 ip
        :param socket_port: 串口 port
        :param timout: 命令超时时间
        :param retry_max: 最大重试次数
        :param pwd_key: 串口连接成功后 输入 password 标记
        :param password: 串口密码
        :param eof_key: 命令执行结束标记,raid 卡请使用 ]#
        :return:
        """
        # '10.22.112.40', 6500
        if not socket_ip or not socket_port:
            if excute_address == CmdExecuteAdressEnum.SERVER.value:
                socket_ip = str(constants.SERVER_COM_IP)
                socket_port = constants.SERVER_COM_PORT
            else:
                socket_ip = str(constants.CLIENT_COM_IP)
                socket_port = constants.CLIENT_COM_PORT

        for i in range(retry_max+1):
            log.info(f"socket {socket_ip}:{socket_port}, connect num {i} exec cmd: {cmd}")
            try:
                si = SocketInteraction(socket_ip, int(socket_port), pwd_key, password, eof_key)
                output = si.interact(cmd, int(timout))
                si.close()
                if output == '-1':
                    continue
                break
            except Exception as e:
                output = '-1'
                log.info(e)

        if output != '-1':
            # 过滤掉串口中输出的日志
            if filter:
                # 2025/07/12.00:16:19.722629
                pattern = "\d+/\d+/\d+.\d+:\d+:\d+.\d+"
                output = re.sub(rf"^.*{pattern}.*\n?", "", output, flags=re.MULTILINE)
                pattern = "logPersistNorflashCheckSpace"
                output = re.sub(rf"^.*{pattern}.*\n?", "", output, flags=re.MULTILINE)

            output = output.splitlines()
            output[0] = ''
            if len(output) and eof_key in output[-1]:
                output[-1] = ''
            output = '\n'.join(output).strip('\n')

        log.info(f"==>serial cmd output: \n{output}")

        return output

    @classmethod
    def exec_socket_cmd_once(cls, cmd, socket_ip=None, socket_port=None, timout: int = 30, pwd_key: str = 'password:',
                             password: str = 'q1w2e#', eof_key: str = 'PS3>',
                             excute_address: str = CmdExecuteAdressEnum.SERVER.value, filter: bool = True) -> str:
        """
        通过串口执行命令，返回 -1 为执行失败
        :param cmd:  需要执行的命令
        :param socket_ip:  串口 ip
        :param socket_port: 串口 port
        :param timout: 命令超时时间
        :param pwd_key: 串口连接成功后 输入 password 标记
        :param password: 串口密码
        :param eof_key: 命令执行结束标记,raid 卡请使用 ]#
        :return:
        """
        # '10.22.112.40', 6500
        if not socket_ip or not socket_port:
            if excute_address == CmdExecuteAdressEnum.SERVER.value:
                socket_ip = str(constants.SERVER_COM_IP)
                socket_port = constants.SERVER_COM_PORT
            else:
                socket_ip = str(constants.CLIENT_COM_IP)
                socket_port = constants.CLIENT_COM_PORT
        log.info(f'测试机串口配置socket_ip {socket_ip}, socket_port {socket_port}, 执行的命令是{cmd}')
        try:
            si = SocketInteraction(socket_ip, int(socket_port), pwd_key, password, eof_key)
            output = si.interact(cmd, int(timout))
            si.close()

        except Exception as e:
            output = '-1'
            log.info(e)

        if output != '-1':
            # 过滤掉串口中输出的日志
            if filter:
                # 2025/07/12.00:16:19.722629
                pattern = "\d+/\d+/\d+.\d+:\d+:\d+.\d+"
                output = re.sub(rf"^.*{pattern}.*\n?", "", output, flags=re.MULTILINE)
                pattern = "logPersistNorflashCheckSpace"
                output = re.sub(rf"^.*{pattern}.*\n?", "", output, flags=re.MULTILINE)

            output = output.splitlines()
            output[0] = ''
            if len(output) and eof_key in output[-1]:
                output[-1] = ''
            output = '\n'.join(output).strip('\n')

        log.info(f"==>serial cmd output: \n{output}")
        return output


# com serial cmd test
# out = SocketOption.exec_socket_cmd('/comm show version all', '10.22.117.153', 6400)
