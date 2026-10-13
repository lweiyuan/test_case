#!/usr/bin/python3
# -*- encoding=utf8 -*-
"""
author: xiangyu.liu
date: 2022.02.15
description: 收集串口/messages/寄存器 日志
"""
import ctypes
from datetime import datetime
import datetime as datetime_i
import inspect
import os
import shutil
import threading
import time
import subprocess
import argparse
import struct
import re
# import paramiko


# 测试轮数
TEST_ROUND = 2500000
# 日志中允许出现的start/exit最大次数（一次是一对start/exit）
MAX_S_E_C = 10
# start/exit之前允许的最大时间间隔（ms）
TIME_BETWEEN_S_E_MS = 600
# 在日志中，从pxe start开始，n行之内(不含n)查找pxe exit
FIND_PXE_EXIT_RANGE = 5
# 用例运行前，导出一次日志
EXPORT_LOG_BEFORE_CASE_START = False
# 加载驱动后等待建链的时间
TIME_WAIT_LINK_UP = 5

# 主线程控制子线程退出
global_exit = False
# 子线程退出状态
sub_thread_exit = False

SUCCESS = 0
FAIL = 1

SXE2CLI64 = 'sxecli'
EID = 'b'
TOOL_DIR = "/root/sxetest/publish_version/debuginfo/sxebmctest/sxebmccli_*"
PKG_MAIN_DIR = "/root/sxetest/publish_version/debuginfo/sxe_fw_asic/debug/sxe_fw_pldm_asic_image_package.bin"
PKG_BAK_DIR = "/root/sxetest/publish_version/debuginfo/sxe_fw_asic/debug/sxe_fw_pldm_asic_image_package_bak.bin"
UPGRADE_IMAGE_PACKAGE_PATH = ('/root/sxetest/publish_version/products/Firmware/Standard-Products/1160-2X'
                              '/Image_*.*.*.*_NIC-1160-2X.bin')
SXE_PLDM_PACKAGE_PY = '/root/sxetest/publish_version/technical_support/Firmware/Tools/pkgTools/sxe_pldm_package.py'
VENDOR_ID = '1ff2'
DEVICE_ID1 = '10a1'

SERVER_HOST_IP = "10.22.114.228"
SERVER_HOST_PORT = "22"
SERVER_HOST_USER = "root"
SERVER_HOST_PWD = "Tianjian;123"
SERVER_BMC_IP = "10.22.115.228"
SERVER_BMC_PORT = "22"
SERVER_BMC_USER = "sysadmin"
SERVER_BMC_PWD = "superuser"
SERVER_BMC_USER_NET = 'Admin'  # 网页登录密码，升级pldm时使用
SERVER_BMC_PWD_NET = 'Admin@8000'

CLIENT_HOST_IP = "10.22.114.229"
CLIENT_HOST_PORT = "22"
CLIENT_HOST_USER = "root"
CLIENT_HOST_PWD = "Tianjian;123"
CLIENT_BMC_IP = "10.22.115.229"
CLIENT_BMC_PORT = "22"
CLIENT_BMC_USER = "sysadmin"
CLIENT_BMC_PWD = "superuser"
CLIENT_BMC_NAME_NET = 'Admin'  # 网页登录密码，升级pldm时使用
CLIENT_BMC_PWD_NET = 'Admin@8000'


# time_now() = datetime.datetime.now()
# TIME = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))


def time_now():
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))


def print_log(log, level="INFO"):
    print(f'[{time_now()}] {level} {log}')


def ssh_cmd(cmd, ip, port):
    cmd = f"ssh -p {port} root@{ip} '{cmd}'"
    # ssh = paramiko.SSHClient()
    # ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # ssh.connect(ip, int(port), SERVER_HOST_USER, SERVER_HOST_PWD)
    print_log("ssh exec cmd: {}".format(cmd))
    # stdin, stdout, stderr = ssh.exec_command(cmd)
    status, result = subprocess.getstatusoutput(cmd)
    print_log("result:\n{}\n".format(result))
    # result = stdout.read().decode()
    # ssh.close()
    return result


def local_cmd(cmd, print_success: bool = False, print_fail: bool = True):
    print_log("local exec cmd: {}".format(cmd))
    status, result = subprocess.getstatusoutput(cmd)
    if status == SUCCESS:
        print('success')
        if print_success:
            print_log("status: {}, result:\n{}\n".format(status, result))
    else:
        if print_fail:
            print_log("status: {}, result:\n{}\n".format(status, result))
    return status, result


def cli_pkg_to_pldm_pkg(cli_pkg_path, no_ver_chk):
    print_log('使用cli升级包生成pldm升级包')
    ssh_cmd('rm -rf /root/sxe_pldm_image.bin')
    out_put = ssh_cmd(f'find {UPGRADE_IMAGE_PACKAGE_PATH}')
    if out_put:
        image_path = out_put
    else:
        print_log('获取文件路径失败', "ERROR")
        exit(FAIL)
    version = re.findall(r'Image_(.*)_NIC-1160-2X', image_path)[0]
    cmd_pldm_pkg = (
        f'cd; python3 {SXE_PLDM_PACKAGE_PY} {cli_pkg_path} sxe_pldm_image.bin '
        f'{no_ver_chk} {version} {VENDOR_ID} {DEVICE_ID1}')
    pldm_pkg_output = ssh_cmd(cmd_pldm_pkg)
    print_log(f'指令执行结果：\n{pldm_pkg_output}')
    find_pkg = ssh_cmd('find /root/sxe_pldm_image.bin')
    if 'sxe_pldm_image.bin' in find_pkg:
        print_log('生成pldm升级包成功')
        return '/root/sxe_pldm_image.bin'
    else:
        print_log('生成pldm升级包失败', "ERROR")
        exit(FAIL)


def handle_log_file(host, port, username, log_file_path, target_dir='opt_termlog'):
    # 下载日志文件
    local_current_path = os.path.dirname(os.path.abspath(__file__))
    local_log_file_path = os.path.join(local_current_path, "temp_file")
    local_cmd(f"scp -P {port} {username}@{host}:{log_file_path} {local_current_path}", print_success=True)

    # 读取并处理日志文件
    with open(local_log_file_path, 'r') as file:
        expect_start_exit_count = MAX_S_E_C
        lines = file.readlines()
        pxe_start_pattern = r'(\d+/\d+/\d+\.\d+:\d+:\d+\.\d+).*(pxe start)'
        pxe_exit_pattern = r'(\d+/\d+/\d+\.\d+:\d+:\d+\.\d+).*(Pxe Exit)'
        check_log = True
        start_exit_count = 0
        total_num = len(lines)
        num = 0
        while num < total_num:
            # 匹配pxe start行号、时间
            match_pxe_start = re.findall(pxe_start_pattern, lines[num])
            if match_pxe_start:
                pxe_start_num = num
                print_log(f"find pxe start line{pxe_start_num}: {match_pxe_start}")
                pxe_start_timestr, pxe_start_event = match_pxe_start[0][0], match_pxe_start[0][1]
                pxe_start_time = datetime.strptime(pxe_start_timestr, '%Y/%m/%d.%H:%M:%S.%f')

                # 在找到pxe_start的后面几行之内匹配pxe exit行号、时间，但是不能匹配到第二个pxe_start
                find_pxe_exit_range = FIND_PXE_EXIT_RANGE
                find_pxe_exit_flag = False
                for i in range(pxe_start_num + 1, pxe_start_num + find_pxe_exit_range):
                    pxe_exit_num = i
                    match_pxe_exit = re.findall(pxe_exit_pattern, lines[pxe_exit_num])
                    # 找到pxe exit后break
                    if match_pxe_exit:
                        find_pxe_exit_flag = True
                        print_log(f"find pxe exit in line{pxe_exit_num}: {match_pxe_exit}")
                        pxe_exit_timestr, pxe_exit_event = match_pxe_exit[0][0], match_pxe_exit[0][1]
                        pxe_exit_time = datetime.strptime(pxe_exit_timestr, '%Y/%m/%d.%H:%M:%S.%f')
                        if pxe_exit_time - pxe_start_time > datetime_i.timedelta(milliseconds=TIME_BETWEEN_S_E_MS):
                            print_log(f"check_log failed: pxe_exit_time - pxe_start_time = {pxe_exit_time - pxe_start_time} > {TIME_BETWEEN_S_E_MS}", "ERROR")
                            check_log = False
                        else:
                            print_log(f"check_log pass: pxe_exit_time - pxe_start_time = {pxe_exit_time - pxe_start_time} <= {TIME_BETWEEN_S_E_MS}")
                            start_exit_count += 1
                        break
                    # 未找到pxe exit时，检查是否没有出现第二个pxe start
                    else:
                        match_pxe_start_2 = re.findall(pxe_start_pattern, lines[pxe_exit_num])
                        if match_pxe_start_2:
                            print_log(f"check_log failed: find second pxe start before find pxe exit", "ERROR")
                            check_log = False
                            break

                if not find_pxe_exit_flag:
                    print_log(f"check_log failed: not match pxe Exit in line[{pxe_start_num}, {pxe_start_num + find_pxe_exit_range})", "ERROR")
                    check_log = False
                    break

                if not check_log:
                    break
            num += 1

    # 总的start和exit次数应为2
    if start_exit_count > expect_start_exit_count:
        print_log(f"pxe start and exit count: {start_exit_count} expcet<= {expect_start_exit_count}", "ERROR")
        return False

    if check_log:  # 日志检查通过
        print_log("check_log success")
        os.remove(local_log_file_path)
        return True
    else:
        print_log("check_log failed !", "ERROR")
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        new_filename = f"{target_dir}/temp_log_file_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        shutil.move(local_log_file_path, new_filename)
        print_log(f"Log file moved to {new_filename}")
        return False


class SxeException(Exception):
    """用于create_bug方法中中抛该异常，Run方法中捕获"""
    pass


class FuncThread(threading.Thread):
    """
    author:      xianda.liu
    date:        2022-07-22
    description: 用于创建多线程使用，重写了threading.Thread的run、join方法，在子线程报异常时，
                 主线程可以捕获到，具体看参考scripts.test_example.test.py中的使用
    """

    def __init__(self, func_name, *args, **kwargs):
        threading.Thread.__init__(self)
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
        except (SxeException, Exception) as e:
            self.exception = e
            self.exit_code = 1
            print('run exception', e)
            # self.exc_traceback = traceback.format_exc()
        finally:
            del self.func_name, self.args, self.kwargs

    def join(self, timeout=None) -> tuple:
        """
        author:      haibin.xu
        date:        2020-10-01 16:45:26
        description: 重写父类中的 join 方法，增加抛 SxeException 异常功能
        :param timeout: 超时等待时间，该参数未使用，因为父类中含有该参数，所以重写时，必须要加上
        """
        super(FuncThread, self).join()
        if self.exception:
            raise self.exception
        return self.ret

    def result(self) -> tuple:
        """
        author:      xiangyu.liu
        date:        2020-10-01 16:45:26
        description: 获取函数执行结果
        """
        return self.ret

    def async_raise(self, tid, exctype):
        """raises the exception, performs cleanup if needed"""
        tid = ctypes.c_long(tid)
        if not inspect.isclass(exctype):
            exctype = type(exctype)
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
        if res == 0:
            raise ValueError("invalid thread id")
        elif res != 1:
            # """if it returns a number greater than one, you're in trouble,
            # and you should call it again with exc=NULL to revert the effect"""
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
            raise SystemError("PyThreadState_SetAsyncExc failed")


class CmdThread(threading.Thread):
    """线程封装类"""
    def __init__(self, name, delay, cmd, ip, port):
        threading.Thread.__init__(self)
        self.delay = delay
        self.name = name
        self.cmd = cmd
        self.ip = ip
        self.port = port

    def run(self):
        time.sleep(self.delay)
        print_log(f"thread {self.name} ===> {self.cmd}")
        result = ssh_cmd(self.cmd, self.ip, self.port)


class Bmc(object):
    def __init__(self, bmc_ip, bmc_port, user_name, password):
        self.bmc_ip = bmc_ip
        self.bmc_port = bmc_port
        self.user_name = user_name
        self.password = password

    def execute_cmd_with_tool(self, cmd, upgrade=False):
        tool_dir = TOOL_DIR
        if not upgrade:
            bmc_ip = f"--addr={SERVER_BMC_IP} --name={SERVER_BMC_USER} --passwd={SERVER_BMC_PWD}"
        else:
            bmc_ip = f"--addr={SERVER_BMC_IP} --name={SERVER_BMC_USER_NET} --passwd={SERVER_BMC_PWD_NET}"
        new_cmd = tool_dir + f" {cmd} " + bmc_ip
        status, res = local_cmd(new_cmd)
        return status, res

    def set_temp_threshold(self, fatal_h, fatal_l=None, warn_h=None, warn_l=None,):
        print_log("PLDM SetSensorThresHolds:")
        para_fatal_h = f' --upper_fatal={fatal_h}'
        para_fatal_l = f' --lower_fatal={fatal_l}' if fatal_l else ''
        para_warn_h = f' --upper_warn={warn_h}' if warn_h else ''
        para_warn_l = f' --lower_warn={warn_l}' if warn_l else ''
        cmd = f'-e {EID} -m 1 -t 2 -c 13 --sensor=0{para_fatal_h}{para_fatal_l}{para_warn_h}{para_warn_l}'
        status, result = self.execute_cmd_with_tool(cmd)
        if status == FAIL:
            return FAIL
        else:
            return SUCCESS

    def set_evt_receiver(self, evt_enable, addr_info, transport):
        print_log("PLDM SetEventReceiver:")
        cmd = f"-e {EID} -m 1 -t 2 -c 4 --evt_msg_global_enable={evt_enable} --transport={transport} --addr_info={addr_info}"
        status, result = self.execute_cmd_with_tool(cmd)
        if status == FAIL:
            return FAIL
        else:
            return SUCCESS

    def update_fw_ver(self, pkg_path, skip_ip=''):
        print_log("update_fw: {}".format(pkg_path))
        pkg_name = pkg_path.split('/')[-1]
        cmd_copy = f'sshpass -p {SERVER_BMC_PWD} scp {pkg_path} {SERVER_BMC_USER}@{SERVER_BMC_IP}:/var/'
        cmd_mv = f"sshpass -p {SERVER_BMC_PWD} ssh {SERVER_BMC_USER}@{SERVER_BMC_IP} 'cd /var/; mv {pkg_name} image.pldm'"
        _, _ = local_cmd(cmd_copy, print_success=True)
        status, result = local_cmd(cmd_mv, print_success=True)
        if status == FAIL:
            print_log("prepare image.pldm fail")
            return FAIL
        if skip_ip:
            cmd_upgrade = f'-e {EID} -m 1 -t 5 -c 0 -d {skip_ip}'
        else:
            cmd_upgrade = f'-e {EID} -m 1 -t 5 -c 0'
        status, result = self.execute_cmd_with_tool(cmd_upgrade, upgrade=True)
        if 'wait update' in result:
            status = SUCCESS
            print_log("send upgrade cmd to bmc success")
        elif '' in result:
            status = FAIL
        else:
            print_log("send upgrade cmd to bmc fail")
            return FAIL

        cmd_upgrade_state = f'{SXE2CLI64} /p0 custom sxe pldmupdatestate'
        while True:
            _, output_upgrade_state = ssh_cmd(cmd_upgrade_state, SERVER_HOST_IP, SERVER_HOST_PORT)
            time.sleep(5)
            re_upgrade_state = re.findall(r'pldm_update_state\s*:\s*(\d+)', output_upgrade_state)
            if re_upgrade_state:
                if re_upgrade_state[0] == '1':
                    print_log('不在升级状态')
                    break
                else:
                    print_log(f'升级中, status: {re_upgrade_state[0]}')
                    # time.sleep(10)
            else:
                print_log('custom命令获取升级状态失败，固件重启')
                break
        # self.close_monitor()

    def get_temp_threshold(self):
        print_log("PLDM GetStateSensorReading:")
        rtn_dict = {}
        cmd = f"-e {EID} -m 1 -t 2 -c 12 --sensor=0"
        status, result = self.execute_cmd_with_tool(cmd)
        if status == FAIL:
            return rtn_dict
        else:
            res = re.findall(r"upper_thold_warning:(-*\d+)", result)
            if res:
                rtn_dict["upper_thold_warning"] = res[0]
            else:
                rtn_dict["upper_thold_warning"] = None
            res = re.findall(r"upper_thold_crit:(-*\d+)", result)
            if res:
                rtn_dict["upper_thold_crit"] = res[0]
            else:
                rtn_dict["upper_thold_crit"] = None
            res = re.findall(r"upper_thold_fatal:(-*\d+)", result)
            if res:
                rtn_dict["upper_thold_fatal"] = res[0]
            else:
                rtn_dict["upper_thold_fatal"] = None
            res = re.findall(r"lower_thold_warning:(-*\d+)", result)
            if res:
                rtn_dict["lower_thold_warning"] = res[0]
            else:
                rtn_dict["lower_thold_warning"] = None
            res = re.findall(r"lower_thold_crit:(-*\d+)", result)
            if res:
                rtn_dict["lower_thold_crit"] = res[0]
            else:
                rtn_dict["lower_thold_crit"] = None
            res = re.findall(r"lower_thold_fatal:(-*\d+)", result)
            if res:
                rtn_dict["lower_thold_fatal"] = res[0]
            else:
                rtn_dict["lower_thold_fatal"] = None
            return rtn_dict

    def get_evt_receiver(self):
        print_log("PLDM GetEventReceiver:")
        rtn_dict = {}
        cmd = f"-e {EID} -m 1  -t 2 -c 5"
        status, result = self.execute_cmd_with_tool(cmd)
        if status == FAIL:
            return rtn_dict
        else:
            res = re.findall(r"transport_protocol_type:(\d+)", result)
            if res:
                rtn_dict["transport_protocol_type"] = res[0]
            else:
                rtn_dict["transport_protocol_type"] = None
            res = re.findall(r"evt_receiver_addr:(\d+)", result)
            if res:
                rtn_dict["evt_receiver_addr"] = res[0]
            else:
                rtn_dict["evt_receiver_addr"] = None
            return rtn_dict

    def get_fw_ver(self, frusize, transferflag):
        print_log("PLDM GetFruRecordTable:")
        rtn_dict = {}
        cmd = f"-e {EID} -m 1 -t 4 -c 2 --frusize={frusize} --transferflag={transferflag}"
        status, result = self.execute_cmd_with_tool(cmd)
        if status == FAIL:
            return rtn_dict
        else:
            if "field:1.3.1.1" not in result:
                return rtn_dict
            else:
                rtn_dict["fw_version"] = "1.3.1.1"
                return rtn_dict

    def close_monitor(self):
        _, output_dmi = ssh_cmd("dmidecode | grep 'Product Name'", SERVER_HOST_IP, SERVER_HOST_PORT)
        _, output_cpu = ssh_cmd("lscpu | grep 'Model name'", SERVER_HOST_IP, SERVER_HOST_PORT)
        ctr_file = ''
        if 'MDA' in output_cpu and '50' in output_dmi:
            ctr_file = '/var/FWmode'
        elif 'Intel' in output_cpu and '50' in output_dmi:
            ctr_file = '/var/MCTPFWUpdateFlag'

        _, ls_output = local_cmd(cmd=f'sshpass -p {SERVER_BMC_PWD} ssh {SERVER_BMC_USER}@{SERVER_BMC_IP} ls {ctr_file}',
                                 print_success=True)
        if ctr_file in ls_output:
            print_log('monitor 已关闭')
        else:
            cmd_stop_monitor = f'sshpass -p {SERVER_BMC_PWD} ssh {SERVER_BMC_USER}@{SERVER_BMC_IP} touch {ctr_file}'
            local_cmd(cmd=cmd_stop_monitor, print_success=True)
            time.sleep(25)


if __name__ == '__main__':

    def exec_func_loop(func, f_name="", repetitions=5, **kwargs):
        global global_exit
        global sub_thread_exit
        results = []
        loop_break = False
        for i in range(repetitions):
            result = func(**kwargs)
            results.append([f_name, str(i), result])
            if global_exit:
                print_log(f"global_exit, stop {f_name}")
                loop_break = True
                break
        if not loop_break:
            print_log(f"loop_end, stop {f_name}")
        sub_thread_exit = True
        return results

    def check_reboot():
        global global_exit
        global sub_thread_exit
        # 检查reboot是否成功
        check_powerup_max = 60
        check_powerup_count = 0
        check_powerup_delay = 5
        is_powerup = False
        while check_powerup_count < check_powerup_max:
            status, result = local_cmd(f"ping {SERVER_HOST_IP} -c 1", print_success=True)
            if ", 0% packet loss" in result:
                is_powerup = True
                break
            time.sleep(check_powerup_delay)
        if is_powerup:
            print_log(f"{SERVER_HOST_IP} power up success")
            global_exit = True
            return SUCCESS
        else:
            print_log(f"{SERVER_HOST_IP} power up fail", "ERROR")
            global_exit = True
            return FAIL

    def check_sub_thread():
        global global_exit
        global sub_thread_exit
        check_subthread_exit_max = 60
        check_subthread_exit_count = 0
        check_subthread_exit_delay = 1
        is_subthread_exit = False
        while check_subthread_exit_count < check_subthread_exit_max:
            if sub_thread_exit:
                is_subthread_exit = True
                break
            time.sleep(check_subthread_exit_delay)
        if is_subthread_exit:
            print_log(f"subthread_exit success")
            return SUCCESS
        else:
            print_log(f"subthread_exit fail", "ERROR")
            return FAIL

    def check_expects():
        # 1. 加载驱动
        ssh_cmd('sudo insmod sxe.ko', SERVER_HOST_IP, SERVER_HOST_PORT)
        time.sleep(TIME_WAIT_LINK_UP)
        # 2. 建联状态
        result = ssh_cmd('lspci | grep Linkdata', SERVER_HOST_IP, SERVER_HOST_PORT)
        if 'Linkdata' not in result:
            print_log('reboot后建链失败, 退出测试。', "ERROR")
            return FAIL
        result = ssh_cmd(f'{SXE2CLI64} show', SERVER_HOST_IP, SERVER_HOST_PORT)
        for dev_info in dev_info_lst:
            if dev_info not in result:
                print_log('reboot后建链失败, 退出测试。', "ERROR")
                return FAIL
        # 3. 端口状态
        for up_dev in up_dev_lst:
            if up_dev not in result:
                result = ssh_cmd(f'ifconfig {up_dev}', SERVER_HOST_IP, SERVER_HOST_PORT)
                if 'RUNNING' not in result:
                    print_log('reboot后加载驱动, 端口状态为down, 退出测试。', "ERROR")
                    return FAIL
        # # 4. 日志检查
        # ssh_cmd('cli /p0 show termlog all file=/root/temp_file', SERVER_HOST_IP, SERVER_HOST_PORT)
        # check_log = handle_log_file(SERVER_HOST_IP, SERVER_HOST_PORT, SERVER_HOST_USER, '/root/temp_file')
        # ssh_cmd('rm -rf /root/temp_file', SERVER_HOST_IP, SERVER_HOST_PORT)
        # if check_log is False:
        #     print_log('日志检查失败, 退出测试。', "ERROR")
        #     return FAIL

    def write_case_result(round, case_name, case_result):
        local_current_path = os.path.dirname(os.path.abspath(__file__))
        result_csv = os.path.join(local_current_path, "optionrom_bmc_case_result.csv")
        with open(result_csv, "a", encoding="utf-8") as file:
            result_str = f"\nround_{round},{case_name},{case_result}"
            file.write(result_str)

    def clear_case_result():
        local_current_path = os.path.dirname(os.path.abspath(__file__))
        result_csv = os.path.join(local_current_path, "optionrom_bmc_case_result.csv")
        time_stamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
        result_csv_new = os.path.join(local_current_path, f"optionrom_bmc_case_result_{time_stamp}.csv")
        local_cmd(f"cp {result_csv} {result_csv_new}", print_success=True)
        with open(result_csv, "w", encoding="utf-8") as file:
            result_str = f""
            file.write(result_str)

    """
    get_temp_threshold
    """
    def test_case_1():
        # 导出日志。排除干扰
        if EXPORT_LOG_BEFORE_CASE_START:
            ssh_cmd(f'{SXE2CLI64} /p0 show termlog all file=/root/temp_file', SERVER_HOST_IP, SERVER_HOST_PORT)

        # 子线程循环发送bmc命令
        kwargs = {}
        bmc_thread = FuncThread(exec_func_loop, func=bmc_obj.get_temp_threshold, f_name="get_temp_threshold", repetitions=1000, **kwargs)
        bmc_thread.start()
        time.sleep(5)
        # 主线程reboot主机，reboot成功后，停止子线程
        ssh_cmd("reboot", SERVER_HOST_IP, SERVER_HOST_PORT)

        # 检查reboot是否成功
        time.sleep(10)
        status = check_reboot()
        if status == FAIL:
            return FAIL

        # 检查子线程是否结束成功
        time.sleep(5)
        status = check_sub_thread()
        if status == FAIL:
            return FAIL

        # 检查预期结果（建联、端口、日志）
        status = check_expects()
        if status == FAIL:
            return FAIL

        # 检查预期结果（通过bmc读取网卡信息）
        rtn_dict = bmc_obj.get_temp_threshold()
        if not rtn_dict:
            print_log('功能恢复检查失败, 退出测试。', "ERROR")
            return FAIL

        global global_exit
        global_exit = False
        return SUCCESS

    """
    get_fw_ver
    """
    def test_case_2():
        # 导出日志。排除干扰
        if EXPORT_LOG_BEFORE_CASE_START:
            ssh_cmd(f'{SXE2CLI64} /p0 show termlog all file=/root/temp_file', SERVER_HOST_IP, SERVER_HOST_PORT)

        # 子线程循环发送bmc命令
        kwargs = {"frusize": '0x19c',
                  "transferflag": "1"}
        bmc_thread = FuncThread(exec_func_loop, func=bmc_obj.get_fw_ver, f_name="get_fw_ver", repetitions=1000, **kwargs)
        bmc_thread.start()
        time.sleep(5)
        # 主线程reboot主机，reboot成功后，停止子线程
        ssh_cmd("reboot", SERVER_HOST_IP, SERVER_HOST_PORT)

        # 检查reboot是否成功

        time.sleep(10)
        status = check_reboot()
        if status == FAIL:
            return FAIL

        # 检查子线程是否结束成功
        time.sleep(5)
        status = check_sub_thread()
        if status == FAIL:
            return FAIL

        # 检查预期结果（建联、端口、日志）
        status = check_expects()
        if status == FAIL:
            return FAIL

        # 检查预期结果（通过bmc读取网卡信息）
        rtn_dict = bmc_obj.get_fw_ver(frusize='0x19c', transferflag='1')
        if not rtn_dict:
            print_log('功能恢复检查失败, 退出测试。', "ERROR")
            return FAIL

        global global_exit
        global_exit = False
        return SUCCESS

    """
    set_temp_threshold
    """
    def test_case_3():
        # 导出日志。排除干扰
        if EXPORT_LOG_BEFORE_CASE_START:
            ssh_cmd(f'{SXE2CLI64} /p0 show termlog all file=/root/temp_file', SERVER_HOST_IP, SERVER_HOST_PORT)

        # 子线程循环发送bmc命令
        kwargs = {"fatal_h": "65"}
        bmc_thread_1 = FuncThread(exec_func_loop, func=bmc_obj.set_temp_threshold, f_name="set_temp_threshold", repetitions=1000, **kwargs)
        kwargs = {"fatal_h": "66"}
        bmc_thread_2 = FuncThread(exec_func_loop, func=bmc_obj.set_temp_threshold, f_name="set_temp_threshold", repetitions=1000, **kwargs)
        bmc_thread_1.start()
        bmc_thread_2.start()
        time.sleep(15)
        # 主线程reboot主机，reboot成功后，停止子线程
        ssh_cmd("reboot", SERVER_HOST_IP, SERVER_HOST_PORT)

        # 检查reboot是否成功
        time.sleep(30)
        status = check_reboot()
        if status == FAIL:
            return FAIL

        # 检查子线程是否结束成功
        time.sleep(5)
        status = check_sub_thread()
        if status == FAIL:
            return FAIL

        # 检查预期结果（建联、端口、日志）
        status = check_expects()
        if status == FAIL:
            return FAIL

        # 检查预期结果（通过bmc读取网卡信息）
        status = bmc_obj.set_temp_threshold(fatal_h='67')
        if status == FAIL:
            print_log('功能恢复检查失败, 退出测试。', "ERROR")
            return FAIL
        rtn_dict = bmc_obj.get_temp_threshold()
        if not rtn_dict:
            print_log('功能恢复检查失败, 退出测试。', "ERROR")
            return FAIL

        global global_exit
        global_exit = False
        return SUCCESS

    """
    set_evt_receiver
    """
    def test_case_4():
        # 导出日志。排除干扰
        if EXPORT_LOG_BEFORE_CASE_START:
            ssh_cmd(f'{SXE2CLI64} /p0 show termlog all file=/root/temp_file', SERVER_HOST_IP, SERVER_HOST_PORT)

        # 子线程循环发送bmc命令
        kwargs = {"evt_enable": "1", "addr_info": "16", "transport": "0"}
        bmc_thread_1 = FuncThread(exec_func_loop, func=bmc_obj.set_evt_receiver, f_name="set_evt_receiver", repetitions=1000, **kwargs)
        kwargs = {"evt_enable": "1", "addr_info": "1", "transport": "0"}
        bmc_thread_2 = FuncThread(exec_func_loop, func=bmc_obj.set_evt_receiver, f_name="set_evt_receiver", repetitions=1000, **kwargs)
        bmc_thread_1.start()
        bmc_thread_2.start()
        time.sleep(5)
        # 主线程reboot主机，reboot成功后，停止子线程
        ssh_cmd("reboot", SERVER_HOST_IP, SERVER_HOST_PORT)

        # 检查reboot是否成功
        time.sleep(10)
        status = check_reboot()
        if status == FAIL:
            return FAIL

        # 检查子线程是否结束成功
        time.sleep(5)
        status = check_sub_thread()
        if status == FAIL:
            return FAIL

        # 检查预期结果（建联、端口、日志）
        status = check_expects()
        if status == FAIL:
            return FAIL

        # 检查预期结果（通过bmc读取网卡信息）
        status = bmc_obj.set_evt_receiver(evt_enable='1', addr_info='16', transport="0")
        if status == FAIL:
            print_log('功能恢复检查失败, 退出测试。', "ERROR")
            return FAIL
        rtn_dict = bmc_obj.get_evt_receiver()
        if not rtn_dict:
            print_log('功能恢复检查失败, 退出测试。', "ERROR")
            return FAIL

        global global_exit
        global_exit = False
        return SUCCESS

    """
    get_evt_receiver
    """
    def test_case_5():
        # 导出日志。排除干扰
        if EXPORT_LOG_BEFORE_CASE_START:
            ssh_cmd(f'{SXE2CLI64} /p0 show termlog all file=/root/temp_file', SERVER_HOST_IP, SERVER_HOST_PORT)

        # 子线程循环发送bmc命令
        bmc_thread_1 = FuncThread(exec_func_loop, func=bmc_obj.get_evt_receiver, f_name="get_evt_receiver", repetitions=1000)
        bmc_thread_1.start()
        time.sleep(5)
        # 主线程reboot主机，reboot成功后，停止子线程
        ssh_cmd("reboot", SERVER_HOST_IP, SERVER_HOST_PORT)

        # 检查reboot是否成功
        time.sleep(10)
        status = check_reboot()
        if status == FAIL:
            return FAIL

        # 检查子线程是否结束成功
        time.sleep(5)
        status = check_sub_thread()
        if status == FAIL:
            return FAIL

        # 检查预期结果（建联、端口、日志）
        status = check_expects()
        if status == FAIL:
            return FAIL

        # 检查预期结果（通过bmc读取网卡信息）
        rtn_dict = bmc_obj.get_evt_receiver()
        if not rtn_dict:
            print_log('功能恢复检查失败, 退出测试。', "ERROR")
            return FAIL

        global global_exit
        global_exit = False
        return SUCCESS

    """
    update_fw_ver
    """
    def test_case_6():
        # 导出日志。排除干扰
        if EXPORT_LOG_BEFORE_CASE_START:
            ssh_cmd(f'{SXE2CLI64} /p0 show termlog all file=/root/temp_file', SERVER_HOST_IP, SERVER_HOST_PORT)

        # 子线程循环发送bmc命令
        kwargs = {"pkg_path": PKG_BAK_DIR}
        bmc_thread_1 = FuncThread(exec_func_loop, func=bmc_obj.update_fw_ver, f_name="update_fw_ver", repetitions=1, **kwargs)
        bmc_thread_1.start()
        time.sleep(15)
        # 主线程reboot主机，reboot成功后，停止子线程
        ssh_cmd("reboot", SERVER_HOST_IP, SERVER_HOST_PORT)

        # 检查reboot是否成功
        time.sleep(10)
        status = check_reboot()
        if status == FAIL:
            return FAIL

        # 检查子线程是否结束成功
        time.sleep(5)
        status = check_sub_thread()
        if status == FAIL:
            return FAIL

        # 检查预期结果（建联、端口、日志）
        status = check_expects()
        if status == FAIL:
            return FAIL

        # 检查预期结果（通过bmc读取网卡信息）
        rtn_dict = bmc_obj.get_fw_ver(frusize='0x19c', transferflag='1')
        if not rtn_dict:
            print_log('功能恢复检查失败, 退出测试。', "ERROR")
            return FAIL

        global global_exit
        global_exit = False
        return SUCCESS


    """main process"""
    # 测试开始前记录设备信息
    result = ssh_cmd(f'{SXE2CLI64} show', SERVER_HOST_IP, SERVER_HOST_PORT)
    up_dev_lst = re.findall(r'(\w+)\s+\|\d+\s+\|\S+\s+\|10Gb/s', result)
    dev_info_lst = re.findall(r'\|\d+\s+\|\w+:\w+:\w+:\w+:\w+:\w+\s+\|\w+\s+\|.*\|.*\|.*\|.*\|.*\|', result)

    # 备份并清理上次用例结果
    clear_case_result()

    bmc_obj = Bmc(SERVER_BMC_IP, SERVER_BMC_PORT, SERVER_BMC_USER, SERVER_BMC_PWD)

    # 循环执行全部测试用例
    for round in range(TEST_ROUND):
        print_log(f"============================ round {round} start ============================")

        # """case_1"""
        # print_log(f"********** round {round} test_case_1 start running**********")
        # status = test_case_1()
        # if status == FAIL:
        #     write_case_result(round, "test_case_1", "FAIL")
        #     print_log(f"********** round {round} test_case_1 run fail ! **********", "ERROR")
        #     exit(FAIL)
        # else:
        #     print_log(f"********** round {round} test_case_1 run success ! **********\n")
        # write_case_result(round, "test_case_1", "PASS")
        #
        # """case_2"""
        # print_log(f"********** round {round} test_case_2 start running**********")
        # status = test_case_2()
        # if status == FAIL:
        #     write_case_result(round, "test_case_2", "FAIL")
        #     print_log(f"********** round {round} test_case_2 run fail ! **********", "ERROR")
        #     exit(FAIL)
        # else:
        #     print_log(f"********** round {round} test_case_2 run success ! **********\n")
        # write_case_result(round, "test_case_2", "PASS")

        """case_3"""
        print_log(f"********** round {round} test_case_3 start running**********")
        status = test_case_3()
        if status == FAIL:
            write_case_result(round, "test_case_3", "FAIL")
            print_log(f"********** round {round} test_case_3 run fail ! **********", "ERROR")
            exit(FAIL)
        else:
            print_log(f"********** round {round} test_case_3 run success ! **********\n")
        write_case_result(round, "test_case_3", "PASS")

        # """case_4"""
        # print_log(f"********** round {round} test_case_4 start running**********")
        # status = test_case_4()
        # if status == FAIL:
        #     write_case_result(round, "test_case_4", "FAIL")
        #     print_log(f"********** round {round} test_case_4 run fail ! **********", "ERROR")
        #     exit(FAIL)
        # else:
        #     print_log(f"********** round {round} test_case_4 run success ! **********\n")
        # write_case_result(round, "test_case_4", "PASS")
        #
        # """case_5"""
        # print_log(f"********** round {round} test_case_5 start running**********")
        # status = test_case_5()
        # if status == FAIL:
        #     write_case_result(round, "test_case_5", "FAIL")
        #     print_log(f"********** round {round} test_case_5 run fail ! **********", "ERROR")
        #     exit(FAIL)
        # else:
        #     print_log(f"********** round {round} test_case_5 run success ! **********\n")
        # write_case_result(round, "test_case_5", "PASS")

        print_log(f"============================ round {round} end ============================\n\n")

    # status = bmc_obj.set_temp_threshold(fatal_h="65")
    # rtn_dict = bmc_obj.get_temp_threshold()
    # status = bmc_obj.set_temp_threshold(fatal_h="66")
    # rtn_dict = bmc_obj.get_temp_threshold()

    # status = bmc_obj.set_evt_receiver(evt_enable="1", addr_info="16", transport="0")
    # rtn_dict = bmc_obj.get_evt_receiver()
    # status = bmc_obj.set_evt_receiver(evt_enable="1", addr_info="1", transport="0")
    # rtn_dict = bmc_obj.get_evt_receiver()

    # status = bmc_obj.update_fw_ver(pkg_path=PKG_BAK_DIR)
    # rtn_dict = bmc_obj.get_fw_ver(frusize='0x19c', transferflag='1')


