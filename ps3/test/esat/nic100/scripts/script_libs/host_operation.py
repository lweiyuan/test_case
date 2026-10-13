#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      haibin.xu
date:        2020.10.24 17:25
@summary:    host宿主机操作类及其方法定义

@steps:

@changelog:

"""
import time
import subprocess
import re
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum
from scripts.script_libs import log


class HostOperation(object):
    """
    @changelog      2021-05-17 17:32:54  haibin.xu
                    1. 优化函数实现, 增加类变量__host_node_name，__ioc_node_name，__host_node_id，__ioc_node_id
    """
    cmd_host_product = None

    host_node_ip = None
    test_object = None
    enclosure_slot_id_pattern = r'^\s*\d+:\d+(,\d+)*\s*$'
    showdisk_data_pattern = r'(\d+)\s*\d+\s*.*[0-9a-z]{7}\s*\n'

    __host_node_name = None
    __ioc_node_name = None
    __host_node_id = None
    __ioc_node_id = None
    __add_disk_times = None
    __disk_version_check_pattern = r'\n\s*versionCheck:\s*(true|false)\s*\n'
    # 通过rpm方式安装的驱动关键字
    rpm_driver_kw = 'Stars'

    # nvme插拔盘的标志位
    __is_nvme_pd_bool = False

    @classmethod
    def host_reboot(cls, ssh_ip: str, ssh_port: str = '22', timeout: int = 900) -> int:
        """
        物理机reboot
        author:      sunql
        time:        2022-04-26
        :param ssh_ip: ssh_ip
        :param ssh_port: ssh_port
        :param timeout: reboot超时时间（单位秒），默认1500秒
        :return: int
        @changelog 2022-12-07 14:11:00 zhilong.zhang
            1. 需求来源：宋渔洋、王琦、常金升
            2. 目的：硬复位失败后重启主机时间可能比较久，导致调用该方法最终返回失败，期望增加超时时间或提供超时时间参数
        """

        rtn_code = RtnStatusEnum.FAIL.value
        cmd = r"reboot"
        CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, timeout=60)

        start_ts = int(time.time())
        current_ts = start_ts
        flag = False
        while current_ts - start_ts <= timeout:
            time.sleep(5)
            # 不能ping通，表示关机成功
            if RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(
                    ip=ssh_ip, ssh_port=ssh_port, is_ping=True):
                flag = True
                log.info("不能ping通，表示关机成功")
                break
            # 更新当前时间
            current_ts = int(time.time())
        # 更新当前时间
        current_ts = int(time.time())
        # if flag:
        iretry = 0
        while current_ts - start_ts <= timeout:
            time.sleep(30)
            if iretry % 2:
                ssh_port = "22"
            else:
                ssh_port = "3322"
            iretry += 1
            # 能ping通，表示开机成功
            # if RtnStatusEnum.SUCCESS.value == CommandOperation.check_ip_connect(
            #         ip=ssh_ip, ssh_port=ssh_port, is_ping=True):
            #     rtn_code = RtnStatusEnum.SUCCESS.value
            #     break
            # 通过port判断是否开启
            cmd = "nc -zv {} {}".format(ssh_ip, ssh_port)
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation. \
                execute_command_based_paramiko_with_rtncode(cmd=cmd, local_execute_flag=True)
            log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
            if "Connected" in cmd_output + cmd_stderr:
               rtn_code = RtnStatusEnum.SUCCESS.value
               break
            # 更新当前时间
            current_ts = int(time.time())
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # 环境重启后，mm需重新编译才能生效
            log.info("环境reboot重启后，mm需重新编译才能生效")
            time.sleep(5)
            iretry = 5
            while iretry:
                result = cls.__check_md_command_available(ssh_ip=ssh_ip, ssh_port=ssh_port)
                log.info("mm重新编译配置结果：{}".format(result))
                if result:
                    cmd = "ulimit -c unlimited"
                    CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, timeout=60)
                    cmd = "echo '/home/nic_core/core-%e-%p-%t' > /proc/sys/kernel/core_pattern"
                    CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, timeout=60)
                    break
                else:
                    log.info("能ping通后md工具编译失败，重试")
                    time.sleep(60)
                iretry -= 1
            # ko对dca有依赖, 每次重启后执行一次，防止后续insmod ko报
            # insmod: ERROR: could not insert module sxe.ko: Unknown symbol in module，可dmesg看报错信息
            cmd = "modprobe dca"
            CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, timeout=60)

            # ubuntu默认不会up
            cmd = "cat /etc/os-release"
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip,
                                                                                          ssh_port=ssh_port, timeout=60)
            if "ubuntu" in cmd_output.lower():
                server_relation_list, client_relation_list = CommonOperation.get_nic_relationships()
                for index, device_name in enumerate(server_relation_list):
                    cmd = "ifconfig {} up".format(device_name)
                    cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_with_error(cmd=cmd,
                                                                                                  ssh_ip=ssh_ip,
                                                                                                  ssh_port=ssh_port,
                                                                                                  timeout=60)
        cmd = r"echo 120 > /proc/sys/kernel/hung_task_timeout_secs"
        CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip, ssh_port=ssh_port)
        return rtn_code

    @classmethod
    def host_nic_reboot(cls, ssh_ip: str, ssh_port: str = '22', timeout: int = 900,
                        cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> int:
        """
        物理机reboot
        author:      sunql
        time:        2022-04-26
        :param ssh_ip: ssh_ip
        :param ssh_port: ssh_port
        :param timeout: reboot超时时间（单位秒），默认1500秒
        :param cmd_execute_address:执行端
        :return: int
        @changelog 2022-12-07 14:11:00 zhilong.zhang
            1. 需求来源：宋渔洋、王琦、常金升
            2. 目的：硬复位失败后重启主机时间可能比较久，导致调用该方法最终返回失败，期望增加超时时间或提供超时时间参数
        """

        rtn_code = RtnStatusEnum.FAIL.value

        cmd_list = ["shutdown -r -t 2", "Restart-Computer"]
        for cmd in cmd_list:
            CommandOperation.execute_command_with_error(cmd=cmd, timeout=60, ssh_port=ssh_port,
                                                        cmd_execute_address=cmd_execute_address)

        start_ts = int(time.time())
        current_ts = start_ts
        flag = False
        while current_ts - start_ts <= timeout:
            time.sleep(5)
            # 不能ping通，表示关机成功
            if RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(
                    ip=ssh_ip, ssh_port=ssh_port, is_ping=True):
                flag = True
                log.info("不能ping通，表示关机成功")
                break
            # 更新当前时间
            current_ts = int(time.time())
        # 更新当前时间
        current_ts = int(time.time())
        # if flag:
        iretry = 0
        while current_ts - start_ts <= timeout:
            time.sleep(30)
            if iretry % 2:
                ssh_port = "22"
            else:
                ssh_port = "3322"
            iretry += 1
            # 能ping通，表示开机成功
            # if RtnStatusEnum.SUCCESS.value == CommandOperation.check_ip_connect(
            #         ip=ssh_ip, ssh_port=ssh_port, is_ping=True):
            #     rtn_code = RtnStatusEnum.SUCCESS.value
            #     break
            # 通过port判断是否开启
            cmd = "nc -zv {} {}".format(ssh_ip, ssh_port)
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation. \
                execute_command_based_paramiko_with_rtncode(cmd=cmd, local_execute_flag=True)
            log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
            if "Connected" in cmd_output + cmd_stderr:
                rtn_code = RtnStatusEnum.SUCCESS.value
                break
            # 更新当前时间
            current_ts = int(time.time())
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # 环境重启后，mm需重新编译才能生效
            log.info("环境reboot重启后，mm需重新编译才能生效")
            time.sleep(5)
            iretry = 5
            while iretry:
                result = cls.__check_md_command_available(ssh_ip=ssh_ip, ssh_port=ssh_port)
                log.info("mm重新编译配置结果：{}".format(result))
                if result:
                    cmd = "ulimit -c unlimited"
                    CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, timeout=60)
                    cmd = "echo '/home/nic_core/core-%e-%p-%t' > /proc/sys/kernel/core_pattern"
                    CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, timeout=60)
                    break
                else:
                    log.info("能ping通后md工具编译失败，重试")
                    time.sleep(30)
                iretry -= 1
            # ko对dca有依赖, 每次重启后执行一次，防止后续insmod ko报
            # insmod: ERROR: could not insert module sxe.ko: Unknown symbol in module，可dmesg看报错信息
            cmd = "modprobe dca"
            CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, timeout=60)

            # ubuntu默认不会up
            cmd = "cat /etc/os-release"
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip,
                                                                                          ssh_port=ssh_port, timeout=60)
            if "ubuntu" in cmd_output.lower():
                server_relation_list, client_relation_list = CommonOperation.get_nic_relationships()
                for index, device_name in enumerate(server_relation_list):
                    cmd = "ifconfig {} up".format(device_name)
                    cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_with_error(cmd=cmd,
                                                                                                  ssh_ip=ssh_ip,
                                                                                                  ssh_port=ssh_port,
                                                                                                  timeout=60)
        return rtn_code

    @classmethod
    def host_bmc_reboot(cls, ssh_ip: str, ssh_port: str = '22',
                        bmc_ip: str = '', uname: str = 'Admin', passwd: str = 'Admin@5000',
                        force_check: bool = True, timeout: int = 900) -> int:
        """
        物理机bmc reboot
        author:      junfeng.he
        time:        2023-11-09
        :param ssh_ip: ssh_ip
        :param ssh_port: ssh_port
        :param force_check: 是否强制检查主机ip是框架配置bmc ip才操作
        :param bmc_ip:
        :param uname:
        :param passwd:
        :param timeout: reboot超时时间（单位秒），默认1500秒
        :return: int
        @changelog
        """
        rtn_code = RtnStatusEnum.FAIL.value
        if force_check:
            cmd = f"ipmitool lan print 1 | grep 'IP Address'"
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, timeout=60)
            get_bmc_ips = re.findall(r': (\d+\.\d+\.\d+\.\d+)', rtn_outputs)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                if get_bmc_ips and bmc_ip == get_bmc_ips[0]:
                    pass
                else:
                    log.error(f"配置文件bmc ip：{bmc_ip}，与环境获取bmc ip：{get_bmc_ips}不一致，请检查配置！！！")
                    # return RtnStatusEnum.FAIL.value
        exec_command = f"ipmitool -U {uname} -I lan -H {bmc_ip} -P '{passwd}' power off"
        status, result = subprocess.getstatusoutput(exec_command)
        log.info("exec_command:{}, status:{}, result:{}".format(exec_command, status, result))
        if 'Authentication type NONE not supported' in result:
            exec_command = f"ipmitool -U {uname} -I lanplus -H {bmc_ip} -P '{passwd}' power off"
            status, result = subprocess.getstatusoutput(exec_command)
            log.info("exec_command:{}, status:{}, result:{}".format(exec_command, status, result))
        time.sleep(10)
        exec_command = f"ipmitool -U {uname} -I lan -H {bmc_ip} -P '{passwd}' power on"
        status, result = subprocess.getstatusoutput(exec_command)
        log.info("exec_command:{}, status:{}, result:{}".format(exec_command, status, result))
        if 'Authentication type NONE not supported' in result:
            exec_command = f"ipmitool -U {uname} -I lanplus -H {bmc_ip} -P '{passwd}' power on"
            status, result = subprocess.getstatusoutput(exec_command)
            log.info("exec_command:{}, status:{}, result:{}".format(exec_command, status, result))

        start_ts = int(time.time())
        current_ts = start_ts
        flag = False
        while current_ts - start_ts <= timeout:
            time.sleep(5)
            # 不能ping通，表示关机成功
            if RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(
                    ip=ssh_ip, ssh_port=ssh_port, is_ping=True):
                flag = True
                log.info("不能ping通，表示关机成功")
                break
            # 更新当前时间
            current_ts = int(time.time())
        # 更新当前时间
        current_ts = int(time.time())
        # if flag:
        iretry = 0
        while current_ts - start_ts <= timeout:
            time.sleep(30)
            if iretry % 2:
                ssh_port = "22"
            else:
                ssh_port = "3322"
            iretry += 1
            # # 能ping通，表示开机成功
            # if RtnStatusEnum.SUCCESS.value == CommandOperation.check_ip_connect(
            #         ip=ssh_ip, ssh_port=ssh_port, is_ping=True):
            #     rtn_code = RtnStatusEnum.SUCCESS.value
            #     break
            # 通过port判断是否开启
            cmd = "nc -zv {} {}".format(ssh_ip, ssh_port)
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation. \
                execute_command_based_paramiko_with_rtncode(cmd=cmd, local_execute_flag=True)
            log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
            if "Connected" in cmd_output + cmd_stderr:
                rtn_code = RtnStatusEnum.SUCCESS.value
                break
            # 更新当前时间
            current_ts = int(time.time())
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # 环境重启后，mm需重新编译才能生效
            log.info("环境bmc重启后，mm需重新编译才能生效")
            time.sleep(5)
            iretry = 5
            while iretry:
                result = cls.__check_md_command_available(ssh_ip=ssh_ip, ssh_port=ssh_port)
                log.info("mm重新编译配置结果：{}".format(result))
                if result:
                    cmd = "ulimit -c unlimited"
                    CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, timeout=60)
                    cmd = "echo '/home/nic_core/core-%e-%p-%t' > /proc/sys/kernel/core_pattern"
                    CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, timeout=60)
                    break
                else:
                    log.info("能ping通后md工具编译失败，重试")
                    time.sleep(60)
                iretry -= 1
            # ko对dca有依赖, 每次重启后执行一次，防止后续insmod ko报
            # insmod: ERROR: could not insert module sxe.ko: Unknown symbol in module，可dmesg看报错信息
            cmd = "modprobe dca"
            CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, timeout=60)

            # ubuntu默认不会up
            cmd = "cat /etc/os-release"
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip,
                                                                                          ssh_port=ssh_port, timeout=60)
            if "ubuntu" in cmd_output.lower():
                server_relation_list, client_relation_list = CommonOperation.get_nic_relationships()
                for index, device_name in enumerate(server_relation_list):
                    cmd = "ifconfig {} up".format(device_name)
                    cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_with_error(cmd=cmd,
                                                                                                  ssh_ip=ssh_ip,
                                                                                                  ssh_port=ssh_port,
                                                                                                  timeout=60)
        cmd = r"echo 120 > /proc/sys/kernel/hung_task_timeout_secs"
        CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip, ssh_port=ssh_port)
        return rtn_code

    @classmethod
    def host_shutdown(cls, ssh_ip: str, bmc_ip: str = '', uname: str = 'Admin', passwd: str = 'Admin@5000',
                        timeout: int = 900) -> int:
        """
        物理机shutdown -h now
        author:      junfeng.he
        time:        20250718
        :param ssh_ip: ssh_ip
        :param ssh_port: ssh_port
        :param force_check: 是否强制检查主机ip是框架配置bmc ip才操作
        :param bmc_ip:
        :param uname:
        :param passwd:
        :param timeout: reboot超时时间（单位秒），默认1500秒
        :return: int
        @changelog
        """
        rtn_code = RtnStatusEnum.FAIL.value
        cmd = f"shutdown -h now"
        CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip, timeout=60)

        start_ts = int(time.time())
        current_ts = start_ts
        flag = False
        while current_ts - start_ts <= timeout:
            time.sleep(5)
            # 不能ping通，表示关机成功
            if RtnStatusEnum.SUCCESS.value != CommandOperation.check_ip_connect(
                    ip=ssh_ip, is_ping=True):
                flag = True
                log.info("不能ping通，表示关机成功")
                break
            # 更新当前时间
            current_ts = int(time.time())
        exec_command = f"ipmitool -U {uname} -I lan -H {bmc_ip} -P '{passwd}' power on"
        status, result = subprocess.getstatusoutput(exec_command)
        log.info("exec_command:{}, status:{}, result:{}".format(exec_command, status, result))
        if 'Authentication type NONE not supported' in result:
            exec_command = f"ipmitool -U {uname} -I lanplus -H {bmc_ip} -P '{passwd}' power on"
            status, result = subprocess.getstatusoutput(exec_command)
            log.info("exec_command:{}, status:{}, result:{}".format(exec_command, status, result))

        iretry = 0
        while current_ts - start_ts <= timeout:
            time.sleep(30)
            if iretry % 2:
                ssh_port = "22"
            else:
                ssh_port = "3322"
            iretry += 1
            # # 能ping通，表示开机成功
            # if RtnStatusEnum.SUCCESS.value == CommandOperation.check_ip_connect(
            #         ip=ssh_ip, ssh_port=ssh_port, is_ping=True):
            #     rtn_code = RtnStatusEnum.SUCCESS.value
            #     break
            # 通过port判断是否开启
            cmd = "nc -zv {} {}".format(ssh_ip, ssh_port)
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation. \
                execute_command_based_paramiko_with_rtncode(cmd=cmd, local_execute_flag=True)
            log.info("cmd_rtn:{}, cmd_output:{}, cmd_stderr:{}".format(cmd_rtn, cmd_output, cmd_stderr))
            if "Connected" in cmd_output + cmd_stderr:
                rtn_code = RtnStatusEnum.SUCCESS.value
                break
            # 更新当前时间
            current_ts = int(time.time())
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # 环境重启后，mm需重新编译才能生效
            log.info("环境bmc重启后，mm需重新编译才能生效")
            time.sleep(5)
            iretry = 5
            while iretry:
                result = cls.__check_md_command_available(ssh_ip=ssh_ip, ssh_port=ssh_port)
                log.info("mm重新编译配置结果：{}".format(result))
                if result:
                    cmd = "ulimit -c unlimited"
                    CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, timeout=60)
                    cmd = "echo '/home/nic_core/core-%e-%p-%t' > /proc/sys/kernel/core_pattern"
                    CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, timeout=60)
                    break
                else:
                    log.info("能ping通后md工具编译失败，重试")
                    time.sleep(60)
                iretry -= 1
            # ko对dca有依赖, 每次重启后执行一次，防止后续insmod ko报
            # insmod: ERROR: could not insert module sxe.ko: Unknown symbol in module，可dmesg看报错信息
            cmd = "modprobe dca"
            CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip, ssh_port=ssh_port, timeout=60)

            # ubuntu默认不会up
            cmd = "cat /etc/os-release"
            cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_with_error(cmd=cmd, ssh_ip=ssh_ip,
                                                                                          ssh_port=ssh_port, timeout=60)
            if "ubuntu" in cmd_output.lower():
                server_relation_list, client_relation_list = CommonOperation.get_nic_relationships()
                for index, device_name in enumerate(server_relation_list):
                    cmd = "ifconfig {} up".format(device_name)
                    cmd_rtn, cmd_output, cmd_stderr = CommandOperation.execute_command_with_error(cmd=cmd,
                                                                                                  ssh_ip=ssh_ip,
                                                                                                  ssh_port=ssh_port,
                                                                                                  timeout=60)
        return rtn_code

    @classmethod
    def __check_md_command_available(cls, ssh_ip: str = None, ssh_port: str = None, ssh_username: str = None) -> bool:
        check_result = False
        exec_command = f'lsmod | grep mem_map'
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
        if rtn_code == RtnStatusEnum.SUCCESS.value and 'mem_map' in rtn_outputs:
            log.info(f'command:{exec_command}, outputs:{rtn_outputs}')
            check_result = True
        else:
            exec_command = 'cd /root/memmap/init_os;chmod +x init_os_env.sh;./init_os_env.sh'
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
            log.info(f'command:{exec_command}, rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
            exec_command = f'lsmod | grep mem_map'
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
            if rtn_code == RtnStatusEnum.SUCCESS.value and 'mem_map' in rtn_outputs:
                check_result = True
            else:
                log.error(f'mem_map不存在，编译失败')
        exec_command = 'md 0x000000'
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
        if "0x" not in rtn_outputs:
            exec_command = "ln -s /root/memmap/starsbox/starsbox /usr/bin/md"
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
            exec_command = "ln -s /root/memmap/starsbox/starsbox /usr/bin/mm"
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
            exec_command = 'md 0x000000'
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd=exec_command, ssh_ip=ssh_ip, ssh_port=ssh_port, ssh_username=ssh_username)
            if "0x" not in rtn_outputs:
                check_result = False
                log.error(f'md不存在，安装失败')
            else:
                check_result = True
                log.info(f'md安装成功')
        else:
            check_result = True
            log.info(f'md安装成功')
        return check_result
