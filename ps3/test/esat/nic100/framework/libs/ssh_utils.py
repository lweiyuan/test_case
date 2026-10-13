# -*- encoding=utf8 -*-

import subprocess
import re
import socket
import os
import time

from libs import constants
from scripts.script_libs import log


def check_ip(ip_address: str) -> bool:
    """
    author:DuPanPan
    date:2020.07.21
    description:检查ip地址的正确性
    :param ip_address: ip地址
    :return flag:ip地址格式是否正确，正确返回True，不正确返回False
    """
    # 去掉端口号
    if ip_address is None or ip_address == "":
        flag = False
    else:
        ip_address = ip_address.split("-p")[0].strip()
        flag = bool(re.match(constants.IP_PATTERN, ip_address))
    if flag is False:
        log.error("IP ERROR: %s" % ip_address)
    return flag


def check_ping(ip_list: list) -> None:
    """
    author:panpan.du
    date:2020.10.14
    description:检查机器的连通性
    :param ip_list:检查连通性的ip列表
    """
    flag = True
    for ip in ip_list:
        if check_ip(ip):
            cmd = "ping %s -c 5 " % ip
            rc, output = subprocess.getstatusoutput(cmd)
            if rc != 0:
                flag = False
                log.error("Execute command %s error: %s" % (cmd, output))
                break
        else:
            break
    if flag is True:
        log.info("Ping ips is success:{}".format(ip_list))


def check_connect(ip: str) -> bool:
    """
    author: DuPanPan
    date  : 2020.08.26
    description:机器同步代码
    :return: True（可以ping通）或False（ping不通）
    """
    flag = True
    # 检查ip代码格式
    if not check_ip(ip):
        log.error("ip address format is incorrect: %s " % ip)
        flag = False
    else:
        # 检查是否能够ssh
        ssh_cmd = "timeout 15 ssh root@%s 'pwd'" % ip
        res, output = subprocess.getstatusoutput(ssh_cmd)
        if res != 0:
            # 检查是否能够ping通
            ping_cmd = "ping %s -c 3 " % ip
            rc, output = subprocess.getstatusoutput(ping_cmd)
            if rc != 0:
                flag = False
                log.error("ping %s is failed" % ip)
            else:
                log.info("ping %s is success" % ip)
                res, output = subprocess.getstatusoutput(ssh_cmd)
                if res == 0:
                    flag = True
                else:
                    flag = False
                    log.error("test ip %s ssh failed. output: %s" % (ip, output))
    if flag:
        log.info("%s connection success" % ip)
    return flag


def remote_ssh(source_ip: str, target_ip: str, source_account="root", target_account="root") -> bool:
    """
    author:panpan.du
    date:2020.10.14
    description:检查机器的ssh
    :param source_ip: 源ip
    :param target_ip: 目标ip
    :param source_account:源ip账户
    :param target_account:目标ip账号
    :return flag:能否ssh成功
    """
    flag = True
    local_ip = socket.gethostbyname(socket.gethostname())
    cmd_list_local = ["timeout 15 ssh %s@%s 'pwd'" % (target_account, target_ip)]  # 检查本机是否可以ssh目标ip地址命令
    cmd_list_remote = [
        # 检查本机ssh源ip地址命令
        "timeout 15 ssh %s@%s 'pwd'" % (source_account, source_ip),
        # 检查源ip地址ssh目标ip地址命令
        "timeout 15 ssh %s@%s 'ssh %s@%s pwd'" % (source_account, source_ip, target_account, target_ip)]
    if source_ip == local_ip:
        cmd_list = cmd_list_local
    else:
        cmd_list = cmd_list_remote
    for cmd in cmd_list:
        rc, output = subprocess.getstatusoutput(cmd)
        if rc != 0:
            flag = False
    return flag


def remote_files_record(remote_ip: str, path: str) -> list:
    """
    :author:panpan.du
    :date:2020.10.07
    :description: 记录文件夹中的所有文件信息
    :param remote_ip: 目标ip地址
    :param path:目录路径
    :return: 文件列表
    """
    file_list = list()
    if remote_file_path_check(remote_ip, path):
        cmd = "timeout 15 ssh root@% s 'ls %s'" % (remote_ip, path)
        rc, output = subprocess.getstatusoutput(cmd)
        if rc == 0:
            file_list = output.split()
    return file_list


def remote_file_path_check(remote_ip: str, path: str, remote_account: str = constants.ENV_DEFAULT_ACCOUNT,
                           local_ip=None) -> bool:
    """
    author:DuPanPan
    date:2020.04.26
    description:检查路径是否存在
    :param remote_ip: 连接的ip地址
    :param path: 文件或者文件夹路径
    :param remote_account: 账号
    :param local_ip 本地IP
    :return flag:文件是否存在，存在返回True，不存在返回False
    """
    local_ip_addr = local_ip if local_ip else socket.gethostbyname(socket.gethostname())
    if remote_ip == local_ip_addr:
        exist_cmd = "stat %s" % path
    else:
        # 超过10s没有返回结果则结束
        exist_cmd = "timeout 20 ssh %s@%s 'stat %s'" % (remote_account, remote_ip, path)
    rc, output = subprocess.getstatusoutput(exist_cmd)
    if rc != 0:
        flag = False
    else:
        flag = True
    return flag


def remote_directory_create(remote_ip: str, directory: str, remote_account: str = "root") -> bool:
    """
    author:panpan.du
    date:2020.10.14
    description:创建文件夹
    :param remote_ip: 连接的ip地址
    :param directory: 要创建的文件夹路径
    :param remote_account: 账户
    :return flag:文件夹是否创建成功，成功返回True，不成功返回False
    """
    local_ip = socket.gethostbyname(socket.gethostname())
    if remote_ip == local_ip:
        exist_cmd = "mkdir -p %s" % directory
    else:
        # 超过10s没有返回结果则结束
        exist_cmd = "timeout 20 ssh %s@%s 'mkdir -p %s'" % (remote_account, remote_ip, directory)
    log.info("mkdir cmd: %s" % exist_cmd)
    rc, output = subprocess.getstatusoutput(exist_cmd)
    if rc != 0:
        flag = False
        log.error("Execute command %s fail. error:\n%s" % (exist_cmd, output))
    else:
        flag = True
    return flag


def remote_file_clear(remote_ip: str, file: str, remote_account: str = "root", local_ip=None) -> None:
    """
    author:panpan.du
    date:2020.10.14
    description:清空文件
    :param remote_ip: 连接的ip地址
    :param file: 要清空的文件路径
    :param remote_account: 账户
    :param local_ip: 本地IP
    """
    # local_ip = socket.gethostbyname(socket.gethostname())
    if remote_file_path_check(remote_ip, file, constants.ENV_DEFAULT_ACCOUNT, local_ip):
        if remote_ip == local_ip:
            clear_cmd = "echo ''>%s" % file
        else:
            # 超过10s没有返回结果则结束
            clear_cmd = """timeout 20 ssh %s@%s "echo ''>%s" """ % (remote_account, remote_ip, file)
        rc, output = subprocess.getstatusoutput(clear_cmd)
        log.info("remote file clear command: %s. return code: %d. output: %s" % (clear_cmd, rc, output))
        if rc != 0:
            raise Exception("Execute command %s error:\n%s" % (clear_cmd, output))
    else:
        log.warning("File %s is not exist" % file)


def remote_file_delete(remote_ip: str, path: str, remote_account: str = constants.ENV_DEFAULT_ACCOUNT) -> None:
    """
    author:DuPanPan
    date:2020.10.15
    description:检查路径是否存在
    :param remote_ip: 连接的ip地址
    :param path: 文件或者文件夹路径
    :param remote_account: 账号
    """
    local_ip = socket.gethostbyname(socket.gethostname())
    if remote_ip == local_ip:
        delete_cmd = "rm -rf %s" % path
    else:
        # 超过10s没有返回结果则结束
        delete_cmd = "timeout 20 ssh %s@%s 'rm -rf %s'" % (remote_account, remote_ip, path)
    rc, output = subprocess.getstatusoutput(delete_cmd)
    log.info("remote file delete command: %s" % delete_cmd)
    if rc != 0:
        raise Exception("Execute command %s error:\n%s" % (delete_cmd, output))


def remote_cp(remote_ip: str, source_path: str, target_path: str, remote_account: str = "root") -> None:
    """
    :author:panpan.du
    :date:2020.10.14
    :description: 远程操作机器拷贝文件
    :param remote_ip:远程ip地址
    :param source_path: 原地址
    :param target_path: 目标地址
    :param remote_account: 账户
    """
    local_ip = socket.gethostbyname(socket.gethostname())
    if remote_ip == local_ip:
        cp_cmd = "cp -r %s %s" % (source_path, target_path)
    else:
        # 暂时不做时间限制
        cp_cmd = "timeout 1h ssh %s@%s 'cp -r %s %s'" % (remote_account, remote_ip, source_path, target_path)
    rc, output = subprocess.getstatusoutput(cp_cmd)
    if rc != 0:
        raise Exception("Execute command %s error:\n%s" % (cp_cmd, output))


def remote_tar_czf(remote_ip: str, directory_tar: str, directory: str, remote_account: str = "root") -> None:
    """
    :author:panpan.du
‘
    """
    local_ip = socket.gethostbyname(socket.gethostname())
    if remote_ip == local_ip:
        tar_cmd = "tar -czf %s %s" % (directory_tar, directory)
    else:
        # 超过5min没有返回结果则结束
        tar_cmd = "timeout 20m ssh %s@%s 'tar -czf %s %s'" % (remote_account, remote_ip, directory_tar, directory)
    rc, output = subprocess.getstatusoutput(tar_cmd)
    log.info("remote tar czf command: %s" % tar_cmd)
    if rc != 0:
        raise Exception("Execute command %s error:\n%s" % (tar_cmd, output))


def remote_tar_xzf(remote_ip: str, directory_tar: str, directory: str, remote_account: str = "root") -> None:
    """
    :author:panpan.du
    :date:2020.10.14
    :description:远程操作打包文件夹
    :param remote_ip:远程ip地址
    :param directory_tar: 打包后的文件名
    :param directory: 解包后所放路径
    :param remote_account: 账户
    """
    local_ip = socket.gethostbyname(socket.gethostname())
    if remote_ip == local_ip:
        tar_cmd = "tar -xzf %s -C %s" % (directory_tar, directory)
    else:
        # 超过5min没有返回结果则结束
        tar_cmd = "timeout 20m ssh %s@%s 'tar -xzf %s -C %s'" % (remote_account, remote_ip, directory_tar, directory)
    rc, output = subprocess.getstatusoutput(tar_cmd)
    log.info("remote tar xzf command: %s" % tar_cmd)
    if rc != 0:
        raise Exception("Execute command %s error:\n%s" % (tar_cmd, output))


def remote_scp(source_ip: str, source_path: str, target_ip: str,
               target_path: str, source_account: str = "root", target_account: str = "root") -> None:
    """
    :author:panpan.du
    :date:2020.10.14
    :description: 远程拷贝日志文件到日志服务器
    :param source_ip: 日志所在ip
    :param source_path: 日志所在路径
    :param target_ip: 日志服务器ip
    :param target_path: 日志服务器存放相应日志的路径
    :param source_account: 源ip账户
    :param target_account: 目标ip账号
    """
    local_ip = socket.gethostbyname(socket.gethostname())
    if source_ip == local_ip:
        scp_cmd = "scp -o StrictHostKeyChecking=no -r %s %s@%s:%s " % (source_path, target_account,
                                                                       target_ip, target_path)
    else:
        # 暂时不做时间限制
        scp_cmd = "ssh -o StrictHostKeyChecking=no %s@%s 'scp -o StrictHostKeyChecking=no -r %s %s@%s:%s '" % \
                  (source_account, source_ip, source_path, target_account, target_ip, target_path)
    rc, output = subprocess.getstatusoutput(scp_cmd)
    log.info("remote scp command: %s" % scp_cmd)
    if rc != 0:
        raise Exception("Execute command error:%s\n%s" % (scp_cmd, output))


def file_dir_check(file: str) -> bool:
    """
    author: luyafei
    date: 2020.11.08
    description: 检测目标文件是不是目录  规则：路径的最后一个字符是"/"表示目录，否则表示文件
    :param file:  要检测的文件
    :return:  True or False
    """
    last_str = file[-1]
    if last_str == "/":
        return False
    return True


def files_find(remote_ip: str, file_list: list, remote_account: str = "root") -> list:
    """
    author: luyafei
    date: 2020.11.08
    description: 查找目标文件列表
    :param remote_ip: 连接的远端ip地址
    :param file_list: 要查找的文件列表
    :param remote_account: 账户
    :return: 查找出的目标文件列表
    """
    find_file_list = []
    local_ip = socket.gethostbyname(socket.gethostname())
    for file in file_list:
        log.info("File path is: %s" % file)
        if file.find("find") != -1:
            find_cmd = file
        elif file.find("*") != -1:
            find_cmd = "ls %s" % file
        else:
            is_file = file_dir_check(file)
            if is_file:
                find_file_list.append(file)
                continue
            else:
                find_cmd = "find %s -type f" % file

        if remote_ip != local_ip:
            find_cmd = "timeout 20 ssh %s@%s %s" % (remote_account, remote_ip, find_cmd)
        log.info("Find file command is: %s" % find_cmd)
        rc, output = subprocess.getstatusoutput(find_cmd)
        if rc != 0:
            raise Exception("Execute command %s error:\n%s" % (find_cmd, output))
        else:
            log.info("Find files result is: %s" % str(output))
            find_file_list.extend(output.splitlines())

    return find_file_list


def get_ioc_process(ioc_port: str, ioc_ip: str) -> str:
    """
        author: zanzan.feng
        date: 2020.11.11
        description: 获取ioc进程id
        :param ioc_port: ioc进程所在机器端口地址
        :param ioc_ip: ioc进程所在机器ip地址
        :return: ioc进程id
    """
    log.info("ioc ip is %s, ioc port is %s" % (ioc_ip, ioc_port))
    cmd_info = "timeout 30s ssh -p %s root@%s 'ps -ef |grep ioc'" % (ioc_port, ioc_ip)
    ioc_process_id = ""
    try:
        cmd_code, cmd_output = subprocess.getstatusoutput(cmd_info)
        if cmd_code == 0:
            log.info("run %s success, output %s" % (cmd_info, cmd_output))
            if "./ioc" in cmd_output or "/opt/ps3/ioc" in cmd_output:
                # 暂时不考虑多个ioc进程的情况
                ioc_process_id = cmd_output.split()[1]
                log.info("%s run success process id %s" % (cmd_info, ioc_process_id))
        else:
            log.error("%s run failed ouput %s" % (cmd_info, cmd_output))
    except Exception as e:
        log.error("%s run exception %s" % (cmd_info, e))
    return ioc_process_id


def generate_pstack_info(ioc_port: str, ioc_ip: str, ioc_process_id: str, times=3, pprint=False) -> None:
    """
        author: zanzan.feng
        date: 2020.11.11
        description: 生成pstack文件信息在ioc机器中
        :param ioc_port: ioc进程所在机器端口地址
        :param ioc_ip: ioc进程所在机器ip地址
        :param ioc_process_id: ioc进程id
        :param times 需要获取pstack的次数
        :param pprint 是否输出到控制台打印，信息太多默认保存在文件中，不打印输出
        :return: None
    """
    log.info("ioc ip is %s, ioc port is %s, ioc process id is %s" % (ioc_ip, ioc_port, ioc_process_id))
    str_time = time.strftime("%Y%m%d%H%M%S", time.localtime())
    pstack_file = "/var/log/pstack_%s.log" % str_time
    cmd_info = "timeout 30s ssh -p %s root@%s  'pstack %s >> %s'" % (ioc_port, ioc_ip, ioc_process_id, pstack_file)
    cmd_read_info = "timeout 30s ssh -p %s root@%s 'cat %s'" % (ioc_port, ioc_ip, pstack_file)
    try:
        for i in range(times):
            cmd_code, cmd_output = subprocess.getstatusoutput(cmd_info)
            if cmd_code != 0:
                log.error("%s run failed output %s" % (cmd_info, cmd_output))
            if pprint:
                cmd_code, cmd_output = subprocess.getstatusoutput(cmd_read_info)
                log.info("cmd output %s " % cmd_output)
            log.info("times %s localtime %s" % (i, time.strftime("%Y-%m-%d %H-%M-%S", time.localtime())))
    except Exception as e:
        log.error("%s run exception %s" % (cmd_info, e))


def create_pstack(ioc_port: str, ioc_ip: str, times=3, pprint=False) -> None:
    """
        author: zanzan.feng
        date: 2020.11.11
        description: 创建pstack文件信息在ioc机器中的接口函数
        :param ioc_port: ioc进程所在机器端口地址
        :param ioc_ip: ioc进程所在机器ip地址
        :param times 需要获取pstack的次数
        :param pprint 是否输出到控制台打印，信息太多默认保存在文件中，不打印输出
        :return: None
    """
    log.info("ioc ip %s, ioc port %s, times %s, pprint %s" % (ioc_ip, ioc_port, times, pprint))
    ioc_process_id = get_ioc_process(ioc_port, ioc_ip)
    if ioc_process_id == "":
        log.error("get ioc process is failed! check cmd ps -ef |grep ioc")
    else:
        generate_pstack_info(ioc_port, ioc_ip, ioc_process_id, times=times, pprint=pprint)


def remote_cmd_execute(remote_ip: str, cmd: str) -> tuple:
    """
    author:
    date:2021.03.20
    description:远程执行命令
    :param remote_ip: 连接的ip地址
    :param cmd: 需执行的shell 命令
    """
    local_ip = socket.gethostbyname(socket.gethostname())
    if remote_ip == local_ip:
        cmd = "timeout 20 %s" % cmd
    else:
        # 超过20s没有返回结果则结束
        cmd = "timeout 20 ssh root@%s '%s'" % (remote_ip, cmd)
    rc, output = subprocess.getstatusoutput(cmd)
    log.info("remote_cmd_execute: %s" % cmd)
    return rc, output
