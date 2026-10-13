#!/usr/bin/env python3
# -*- encoding=utf8 -*-
import time
import os

from framework.model.log_collect import LogCollect
# from scripts.nic100.utils.win_package_process import vm_path
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs import log
from scripts.script_libs.file_operation import FileOperation
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum
from framework.model.sagitta import constants as tj_constants
from framework.libs import constants


class LogCollect(LogCollect):

    def get_server_ip_port(self):
        return self.framework_run_dict['ip_dict']['server_ip'], self.framework_run_dict['ip_dict']['test_port']

    def get_client_ip_port(self):
        return self.framework_run_dict['ip_dict']['client_ip'], self.framework_run_dict['ip_dict']['test_port']

    def clear_log(self, ip, port, target_execute_address, os_type):
        if os_type == 'windows':
            file_list = [
                ['C:/sxe_log/', 'sxe_win_drv_str.*'],
                ['C:/sxe_log/', 'sxe_win_drv_bin.*'],
            ]
            for files in file_list:
                file_path = files[0]
                file_patttern = files[1]
                cmd = f"Get-ChildItem -Path '{file_path}' -Filter '{file_patttern}' " \
                    f"| Sort-Object LastWriteTime -Descending | Select-Object -Skip 2 | Remove-Item -Force"
                _, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd,
                    host_os_server=self.framework_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=self.framework_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                    cmd_execute_address=target_execute_address,
                    ssh_ip=ip,
                    ssh_port=port)
                log.info(out)

            file_list = [
                ['C:/Users/Administrator/nic_log/', "nic_log_*"]
            ]
            for files in file_list:
                file_path = files[0]
                file_patttern = files[1]
                cmd = f"Get-ChildItem -Path '{file_path}' -Filter '{file_patttern}' " \
                    f"| Sort-Object LastWriteTime -Descending | Select-Object -Skip 30 | Remove-Item -Force -Recurse"
                _, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd,
                    host_os_server=self.framework_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=self.framework_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                    cmd_execute_address=target_execute_address,
                    ssh_ip=ip,
                    ssh_port=port)
                log.info(out)

        else:
            vm, rpc_port = CommonOperation.get_node_info_from_path()
            file_list = [
                # '/var/log/scgbe.bin.*',
                # '/var/log/scgbe.log.*',
                # '/var/log/scgbevf.bin.*',
                # '/var/log/scgbevf.log.*',
                # '/var/log/scgbepmd.log.*',
                # '/var/log/scgbevfpmd.log.*',
                '/home/pyverbs_log/pyverbs_log_*',
                f'/home/dpdkscreenlog{vm}/screenlog_bk_*',
                '/var/log/sxe2.bin.*',
                '/var/log/sxe2.log.*',
                '/var/log/sxe2vf.bin.*',
                '/var/log/sxe2vf.log.*',
                '/var/log/sxe2pmd.log.*',
                '/var/log/sxe2vfpmd.log.*',
                '/var/log/sxe2_common_pmd.log.*',
                '/var/log/sxe2vf_common_pmd.log.*',
                '/var/log/sxe2-fw-*',
            ]
            for files in file_list:
                cmd = f"ls {files} | sort -nr |sed -n '6,$p' " + r"| xargs rm -fr {}"
                _, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd,
                    host_os_server=self.framework_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=self.framework_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                    cmd_execute_address=target_execute_address,
                    ssh_ip=ip,
                    ssh_port=port)
                log.info(out)

            # 删除未压缩的文件
            file_list = [
                '/home/nic_log/nic_log_*',
            ]
            for files in file_list:
                cmd = (f"ls {files} | grep -v 'tar.gz' | grep {files.replace('*', '')} " +
                       r"| awk -F':' '{print $1}' | sort -nr |sed -n '1,$p' " +
                       r"| xargs rm -fr {}")
                _, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd,
                    host_os_server=self.framework_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=self.framework_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                    cmd_execute_address=target_execute_address,
                    ssh_ip=ip,
                    ssh_port=port)
                log.info(out)

            file_list = [
                '/home/nic_log/nic_log_*',
                '/home/nic_core/core-*',
            ]
            for files in file_list:
                cmd = f"ls {files} | sort -nr |sed -n '15,$p' " + r"| xargs rm -fr {}"
                _, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                    cmd,
                    host_os_server=self.framework_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                    host_os_client=self.framework_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                    cmd_execute_address=target_execute_address,
                    ssh_ip=ip,
                    ssh_port=port)
                log.info(out)

    def collect_log(self):
        def collect_host_log(ip, port, target_execute_address,  os_type):
            collect_flag = False
            vm, rpc_port = CommonOperation.get_node_info_from_path()
            test_start_timestamp = int(self.framework_run_dict['last_log_collect_timestamp'])
            time_offset = int(time.time()) - test_start_timestamp
            # 多给5分钟余量，避免日志切割不及时导致第一份日志未采集到
            time_offset += 300
            if os_type == 'windows':
                cmd = f"python3 {tj_constants.WINDOWS_FILE_PATH_ROOT}esxe.py --cl --sst {time_offset} --vm {vm}"
            else:
                cmd = f"python3 /usr/bin/esxe.py --cl --sst {time_offset} --vm {vm}"

            _, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                cmd,
                host_os_server=self.framework_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                host_os_client=self.framework_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                cmd_execute_address=target_execute_address, timeout=2700,
                ssh_ip=ip, ssh_port=port, print_outputs=False)
            out_info = out + err
            # log.info(out_info)

            out = str(out_info).splitlines()
            path = None
            tree_flag = False
            print_tree_info = ""
            for line in out:
                if "拷贝日志信息如下" in line:
                    tree_flag = True
                elif tree_flag:
                    print_tree_info += line + "\r\n"

                if 'COLLECT_LOG_PATH' in line:
                    path = line.split('COLLECT_LOG_PATH:')[-1]
                    break
            log.info(print_tree_info)
            info = ""
            count = 0
            for line in out:
                info += line
                count += 1
                if count == 200:
                    info = info.replace("'", "").replace("\"", "")
                    cmd = f"echo '{info}' > /home/nic_log/esxe_excute.log"
                    _, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd,
                        host_os_server=self.framework_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=self.framework_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                        cmd_execute_address=target_execute_address,
                        ssh_ip=ip, ssh_port=port, print_steps=False, print_outputs=False)
                    info = ""
                elif count % 200 == 0 or count == len(out):
                    info = info.replace("'", "").replace("\"", "")                   
                    cmd = f"echo '{info}' >> /home/nic_log/esxe_excute.log"
                    _, out, err = CommandOperation.execute_command_based_paramiko_with_rtncode(
                        cmd,
                        host_os_server=self.framework_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL),
                        host_os_client=self.framework_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL),
                        cmd_execute_address=target_execute_address,
                        ssh_ip=ip, ssh_port=port, print_steps=False, print_outputs=False)
                    info = ""

            if os_type == 'windows':
                username = "Administrator"
                rtn = RtnStatusEnum.SUCCESS.value
                match_pattern = "C:/Users/Administrator/nic_log/"
            else:
                username = "root"
                rtn, _ = FileOperation.path_exists(path=path, ip=ip, port=port)
                match_pattern = "/home/nic_log"

            if path and rtn == RtnStatusEnum.SUCCESS.value:
                collect_flag = True

            # 打包
            collect_flag = self.pack_collect_log(file_path=path, tar_params='-hcf',
                                                 tar_file_path=f'{path}_{ip}.tar.gz', server_msg='test',
                                                 username=username,
                                                 ip=ip, port=port, is_pigz=False) if collect_flag else False

            # 传输
            collect_flag = self.scp_collect_log_to_log_server(source_file=f'{path}_{ip}.tar.gz',
                                                              server_msg='test',
                                                              source_username=username, source_ip=ip,
                                                              source_port=port) if collect_flag else False
            # 如果日志已传输成功，则删除本地原目录，压缩包暂时不删
            if collect_flag:
                FileOperation.delete_file(path=path, ip=ip, port=port, match_flag=True, username=username,
                                          file_check_flag=True, match_pattern=match_pattern)

            return collect_flag

        def collect_com_log(log_server_ip, log_server_username, com_ip, com_port, target_mark):
            # 串口交换机上的监控进程在log server上
            collect_com_log = True
            # 采集串口交换机日志
            if com_ip != "None" and com_port != "None":
                path = f'{constants.COM_LOG_DIR}com_log_{target_mark}_{com_ip}_{com_port}'
                FileOperation.make_directory(path, ip=log_server_ip, username=log_server_username, match_flag=False)
                for i in range(2):
                    day = time.strftime("%Y-%m-%d", time.localtime(time.time() - i*86400))
                    com_log_path = f"{constants.COM_LOG_DIR}/{com_ip}/{com_port}/com_log_{com_ip}_{com_port}_{day}.log"
                    FileOperation.copy_file(com_log_path, path, ip=log_server_ip, match_flag=False)

                # 打包
                collect_com_log = self.pack_collect_log(file_path=path, tar_params='-hcf',
                                                     tar_file_path=f'{path}.tar.gz', server_msg='test',
                                                     username=log_server_username,
                                                     ip=log_server_ip, is_pigz=False) if collect_com_log else False

                # 传输
                rtn_copy_file = FileOperation.copy_file(f'{path}.tar.gz', self.log_script_dir_path,
                                                        ip=log_server_ip, match_flag=False)
                if rtn_copy_file == RtnStatusEnum.SUCCESS.value:
                    collect_com_log = True  if collect_com_log else False
                else:
                    collect_com_log = False
                # collect_com_log = self.scp_collect_log_to_log_server(
                #     source_file=f'{path}.tar.gz', server_msg='test', source_username=log_server_username,
                #     source_ip=log_server_ip, localpath_flag=False) if collect_com_log else False

                # 如果日志已传输成功，则删除本地原目录
                if collect_com_log:
                    FileOperation.delete_file(path=path, ip=log_server_ip, username=log_server_username,
                                              file_check_flag=True, match_flag=False)
                    FileOperation.delete_file(path=f"{path}.tar.gz", ip=log_server_ip, username=log_server_username,
                                              file_check_flag=True, match_flag=False)
            return collect_com_log

        if self.framework_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) in \
                [tj_constants.UEFI_MODE]:
            log.info("uefi测试模式，无需进行os下的日志采集")
            return True

        # 如果未记录过last_log_collect_timestamp，则赋值成测试单开始跑测时间
        if 'last_log_collect_timestamp' not in self.framework_run_dict.keys():
            self.framework_run_dict['last_log_collect_timestamp'] = self.framework_run_dict['test_start_timestamp']
        server_ip, server_port = self.get_server_ip_port()
        client_ip, client_port = self.get_client_ip_port()
        server_os_type = self.framework_run_dict['config_dict'].get(tj_constants.EVN_SERVER_NIC_MODEL)
        client_os_type = self.framework_run_dict['config_dict'].get(tj_constants.EVN_CLIENT_NIC_MODEL)
        server_log_collect_result = collect_host_log(server_ip, server_port,
                                                     CmdExecuteAdressEnum.SERVER.value, server_os_type)

        # # 日志服务器ip
        # log_server_ip = self.framework_run_dict['ip_dict'].get(constants.ENV_LOG_SERVER_IP)
        # # 日志服务器 用户
        # log_server_account = self.framework_run_dict['ip_dict'].get(constants.ENV_LOG_SERVER_ACCOUNT,
        #                                                             constants.ENV_LOG_SERVER_ACCOUNT_FRAMEWORK)

        # server_com_ip = self.framework_run_dict['ip_dict'].get('server_com_ip', 'None')
        # server_com_port = self.framework_run_dict['ip_dict'].get('server_com_port', 'None')
        # server_collect_com_log = collect_com_log(log_server_ip, log_server_account, server_com_ip, server_com_port,
        #                                          target_mark="server_{}".format(server_ip))

        client_renix_only_flag = CommonOperation.is_renix_only()
        if ((self.framework_run_dict['config_dict'].get(tj_constants.ENV_TEST_ENTRY) not in [tj_constants.SINGLE_MODE]) and
                not client_renix_only_flag):
            client_log_collect_result = collect_host_log(client_ip, client_port,
                                                         CmdExecuteAdressEnum.CLIENT.value, client_os_type)

            # client_com_ip = self.framework_run_dict['ip_dict'].get('client_com_ip', 'None')
            # client_com_port = self.framework_run_dict['ip_dict'].get('client_com_port', 'None')
            # client_collect_com_log = collect_com_log(log_server_ip, log_server_account, client_com_ip, client_com_port,
            #                                          target_mark="client_{}".format(client_ip))
        else:
            client_log_collect_result = True
            # client_collect_com_log = True

        # log_collect_result = server_log_collect_result and client_log_collect_result and server_collect_com_log and client_collect_com_log
        # log.info("log_collect_result:{} = {} & {} & {} & {}".format(log_collect_result, server_log_collect_result,
        #                                                             client_log_collect_result, server_collect_com_log,
        #                                                             client_collect_com_log))
        log_collect_result = server_log_collect_result and client_log_collect_result
        log.info("log_collect_result:{} = server:{} & client:{}".format(log_collect_result, server_log_collect_result, client_log_collect_result))
        if log_collect_result:
            # 如果两端日志都采集成功，则更新最新的日志采集时间
            self.framework_run_dict['last_log_collect_timestamp'] = time.time()
        return log_collect_result
