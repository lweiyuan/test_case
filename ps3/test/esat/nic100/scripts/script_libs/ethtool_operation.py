import json
import pdb
import random
import re
import time


import add_syspath
from scripts.script_libs import constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum, RxfhIndirEnum, SpeedEnum, NicNameEnum, \
    EthtoolParamShortenEnum


class EthtoolOperation(object):

    @classmethod
    def check_ethtool_version(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-16
        description:        ethtool版本校验
                            回显格式:
                            ethtool version 5.0
        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.VERSION])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            if rtn_outputs.split('ethtool version ')[1] >= constants.ETHTOOL_VERSION:
                rtn_status = True
            else:
                log.info(f'ethtool版本不符合,当前版本{rtn_outputs},测试需要版本{constants.ETHTOOL_VERSION}')
        else:
            log.info(f'获取ethtool版本失败,错误信息:{rtn_err}')

        return rtn_status

    @classmethod
    def show_pause_options(cls, device_name: str,
                           cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> dict or None:
        """
        author:             xianda.liu
        date:               2022-07-16
        description:        ethtool --show-pause命令及结果解析
                            回显格式:
                            Pause parameters for ens1f0:
                            Autonegotiate:  off
                            RX:             on
                            TX:             on
        :param device_name:   网卡设备名称,如ens1f0
        return: {
                    Autonegotiate:off,
                    RX:on,
                    TX:on
                }
        """
        result_dict = dict()

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.SHOW_PAUSE, device_name])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # 将显示中的第一行截掉，防止误匹配
            split_result = rtn_outputs.split(device_name + constants.STR_COLON)[1]
            result_re = re.findall(pattern=constants.SHOW_PAUSE_PATTERN, string=split_result)

            for item in result_re:
                result_dict[item[0]] = item[1]

        return result_dict

    @classmethod
    def change_generic_options(cls, device_name: str, para_key: str, para_value: str,
                               cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-18
        description:        ethtool --change命令
        :param device_name:   网卡设备名称,如ens1f0
        :param para_key:      修改的参数名
        :param para_value:    修改的参数值
        :param cmd_execute_address:
        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.CHANGE, device_name,
                                                 para_key, para_value])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def change_msglvl_options(cls, device_name: str, para_key: str, para_value: str,
                              cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shaohui.wang
        date:               2022-09-28
        description:        ethtool --change命令
        :param device_name:   网卡设备名称,如ens1f0
        :param para_key:      消息类型名称
        :param para_value:    取值为on或off
        :param cmd_execute_address:
        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.CHANGE, device_name, constants.MSGLVL,
                                                 para_key, para_value])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def set_pause_options(cls, device_name: str, para_key: str, para_value: str,
                          cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-18
        description:        ethtool --pause命令
        :param device_name:   网卡设备名称,如ens1f0
        :param para_key:      修改的参数名
        :param para_value:    修改的参数值
        :param cmd_execute_address:
        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.PAUSE, device_name,
                                                 para_key, para_value])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def show_coalesce_options(cls, device_name: str,
                              cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> dict:
        """
        author:             xianda.liu
        date:               2022-07-16
        description:        ethtool --show-coalesce命令及结果解析
                            回显格式:
                            Coalesce parameters for ens1f0:
                            Adaptive RX: off  TX: off
                            stats-block-usecs: 0
                            sample-interval: 0
                            pkt-rate-low: 0
                            pkt-rate-high: 0

                            rx-usecs: 1
                            rx-frames: 0
                            rx-usecs-irq: 0
                            rx-frames-irq: 0

                            tx-usecs: 0
                            tx-frames: 0
                            tx-usecs-irq: 0
                            tx-frames-irq: 0

                            rx-usecs-low: 0
                            rx-frame-low: 0
                            tx-usecs-low: 0
                            tx-frame-low: 0

                            rx-usecs-high: 0
                            rx-frame-high: 0
                            tx-usecs-high: 0
                            tx-frame-high: 0
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        return: {
                    RX:off,
                    TX:off,
                    ...
                }
        """
        result_dict = dict()

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.SHOW_COALESCE, device_name])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # os_compatibility: 适配rocky
            rtn_outputs = rtn_outputs.replace("n/a", '0')
            # 将显示中的第一行截掉，防止误匹配
            split_result = rtn_outputs.split(device_name + constants.STR_COLON)[1]
            # ethtool -c中有两对TX RX，这段代码返回的字典中只有一对，第二对的值会覆盖第一对
            # result_re = re.findall(pattern=constants.SHOW_PAUSE_PATTERN, string=split_result)
            #
            # for item in result_re:
            #     # os_compatibility: 适配rocky
            #     if item[0] in ["RX", "TX"] and item[1] == '0':
            #         result_dict[item[0]] = 'off'
            #     else:
            #         result_dict[item[0]] = item[1]
            # 更换成以下方法，解决上述问题
            result_re = [tmp.replace('\t', '').strip() for tmp in split_result.split('\n') if tmp]
            for item in result_re:
                if 'Adaptive' in item:
                    # 兼容以前调用该接口的脚本，key 保持为 TX，RX
                    pairs = item.split()
                    result_dict['RX'] = pairs[2]
                    result_dict['TX'] = pairs[4]
                elif 'CQE mode' in item:
                    pairs = item.split()
                    result_dict['CQE_Rx'] = pairs[3]
                    result_dict['CQE_Tx'] = pairs[5]
                else:
                    key, value = item.split(":")
                    result_dict.update({key.strip(): value.strip()})

        return result_dict

    @classmethod
    def set_coalesce_options(cls, device_name: str, para_key: str, para_value: str,
                             cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-18
        description:        ethtool --coalesce命令
        :param device_name:   网卡设备名称,如ens1f0
        :param para_key:      修改的参数名
        :param para_value:    修改的参数值
        :param cmd_execute_address:
        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.COALESCE, device_name,
                                                 para_key, para_value])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def show_coalesce_options_by_queue(cls, device_name: str, queue_id: int = 0,
                                       cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> dict:
        """
        author:             shanshan.du
        date:               2024-11-28
        description:        ethtool --per-queue device_name queue_mask queue_id  --show-coalesce命令及结果解析
                            回显格式:
                            Coalesce parameters for ens1f0:
                            Queue: 0
                            Adaptive RX: off  TX: off
                            stats-block-usecs: 0
                            sample-interval: 0
                            pkt-rate-low: 0
                            pkt-rate-high: 0

                            rx-usecs: 1
                            rx-frames: 0
                            rx-usecs-irq: 0
                            rx-frames-irq: 0

                            tx-usecs: 0
                            tx-frames: 0
                            tx-usecs-irq: 0
                            tx-frames-irq: 0

                            rx-usecs-low: 0
                            rx-frame-low: 0
                            tx-usecs-low: 0
                            tx-frame-low: 0

                            rx-usecs-high: 0
                            rx-frame-high: 0
                            tx-usecs-high: 0
                            tx-frame-high: 0
        :param device_name:   网卡设备名称,如ens1f0
        :param queue_id: 队列编号, 如1, 2
        :param cmd_execute_address:
        return: {
                    RX:off,
                    TX:off,
                    ...
                }
        """
        result_dict = dict()

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.PER_QUEUE,
                                                 device_name, constants.QUEUE_MASK, str(queue_id),
                                                 constants.SHOW_COALESCE, device_name])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # os_compatibility: 适配rocky
            rtn_outputs = rtn_outputs.replace("n/a", '0')
            # 将显示中的第一行截掉，防止误匹配
            # split_result = rtn_outputs.split(device_name + constants.STR_COLON)[1]
            result_re = re.findall(pattern=constants.SHOW_PAUSE_PATTERN, string=rtn_outputs)

            for item in result_re:
                # os_compatibility: 适配rocky
                if item[0] in ["RX", "TX"] and item[1] == '0':
                    result_dict[item[0]] = 'off'
                else:
                    result_dict[item[0]] = item[1]

        return result_dict

    @classmethod
    def set_coalesce_options_by_queue(cls, device_name: str, para_key: str, para_value: str, queue_id: int = 0,
                                      cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             shanshan.du
        date:               2024-11-28
        description:        ethtool --per-queue device_name queue_mask 2 --coalesce命令
        :param device_name:   网卡设备名称,如ens1f0
        :param para_key:      修改的参数名
        :param para_value:    修改的参数值
        :param queue_id:      队列编号, 如 1, 2
        :param cmd_execute_address:
        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.PER_QUEUE, device_name,
                                                 constants.QUEUE_MASK, str(queue_id), constants.COALESCE,
                                                 para_key, para_value])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        log.info(f'command:{exec_command}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def query_ring_parameters(cls, device_name: str,
                              cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, netns_name: str = None) -> dict:
        """
        author:             xianda.liu
        date:               2022-07-16
        description:        ethtool --show-ring命令及结果解析
                            回显格式:
                            Ring parameters for ens1f0:
                            Pre-set maximums:
                            RX:             4096
                            RX Mini:        0
                            RX Jumbo:       0
                            TX:             4096
                            Current hardware settings:
                            RX:             512
                            RX Mini:        0
                            RX Jumbo:       0
                            TX:             512

                        rocky:
                            Ring parameters for ens6f1:
                            Pre-set maximums:
                            RX:             4096
                            RX Mini:        n/a
                            RX Jumbo:       n/a
                            TX:             4096
                            Current hardware settings:
                            RX:             512
                            RX Mini:        n/a
                            RX Jumbo:       n/a
                            TX:             512
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        return: {
                    'Pre-set maximums': {
                        'RX': '4096',
                        'RX Mini': '0',
                        'RX Jumbo': '0',
                        'TX': '4096'
                        },
                    'Current hardware settings': {
                        'RX': '512',
                        'RX Mini': '0',
                        'RX Jumbo': '0',
                        'TX': '512'
                        }
                }
        """
        result_dict = dict()

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.SHOW_RING, device_name])
        if netns_name:
            exec_command = f"ip netns exec {netns_name} {exec_command}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # os_compatibility: 适配rocky
            rtn_outputs = rtn_outputs.replace("n/a", '0')
            # 将显示中的第一行截掉，防止误匹配
            split_result = rtn_outputs.split(device_name + constants.STR_COLON)[1]
            result = [i.strip() for i in split_result.split('\n')]

            for item in result:
                result_re = re.match(pattern=constants.SHOW_RING_PATTERN, string=item)

                # 如果没有匹配，可能有两种情况，一种是内容为空，这种丢弃；一种是有key值没有value值，这种作为第一级字典的key值
                if not result_re:
                    if item.split(':')[0] != '':
                        result_dict[item.split(':')[0]] = {}
                    else:
                        pass

                else:
                    # 遍历所有字典，确认要添加的key值是否已存在于结果中，如果存在跳出本轮循环
                    for key, value in result_dict.items():
                        if result_re.groups()[0] not in value.keys():
                            result_dict[key][result_re.groups()[0]] = result_re.groups()[1]
                        else:
                            continue
        log.info("result_dict:{}".format(result_dict))
        return result_dict

    @classmethod
    def set_ring_parameters(cls, device_name: str, para_key: str, para_value: str,
                            cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-18
        description:        ethtool --set-ring命令
        :param device_name:   网卡设备名称,如ens1f0
        :param para_key:      修改的参数名
        :param para_value:    修改的参数值
        :param cmd_execute_address:
        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.SET_RING, device_name,
                                                 para_key, para_value])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def get_offload_and_features(cls, device_name: str,
                                 cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                                 win_vm_ip: str = None, ns_name: str = None, extra_para: str = None
                                 ) -> dict:
        """
        author:             xianda.liu
        date:               2022-07-16
        description:        ethtool --show-features命令及结果解析
                            回显格式:
                            Features for ens1f0:
                            rx-checksumming: on
                            tx-checksumming: on
                                    tx-checksum-ipv4: off [fixed]
                                    tx-checksum-ip-generic: on
                                    tx-checksum-ipv6: off [fixed]
                                    tx-checksum-fcoe-crc: off [fixed]
                                    tx-checksum-sctp: on
                            scatter-gather: on
                                    tx-scatter-gather: on
                                    tx-scatter-gather-fraglist: off [fixed]
                            tcp-segmentation-offload: on
                                    tx-tcp-segmentation: on
                                    tx-tcp-ecn-segmentation: off [fixed]
                                    tx-tcp-mangleid-segmentation: off
                                    tx-tcp6-segmentation: on
                            generic-segmentation-offload: on
                            generic-receive-offload: on
                            large-receive-offload: off [fixed]
                            rx-vlan-offload: on
                            tx-vlan-offload: on
                            ntuple-filters: off
                            receive-hashing: on
                            highdma: on [fixed]
                            rx-vlan-filter: on
                            vlan-challenged: off [fixed]
                            tx-lockless: off [fixed]
                            netns-local: off [fixed]
                            tx-gso-robust: off [fixed]
                            tx-fcoe-segmentation: off [fixed]
                            tx-gre-segmentation: on
                            tx-gre-csum-segmentation: on
                            tx-ipxip4-segmentation: on
                            tx-ipxip6-segmentation: on
                            tx-udp_tnl-segmentation: on
                            tx-udp_tnl-csum-segmentation: on
                            tx-gso-partial: on
                            tx-sctp-segmentation: off [fixed]
                            tx-esp-segmentation: on
                            tx-udp-segmentation: off [fixed]
                            tls-hw-rx-offload: off [fixed]
                            fcoe-mtu: off [fixed]
                            tx-nocache-copy: off
                            loopback: off [fixed]
                            rx-fcs: off [fixed]
                            rx-all: off
                            tx-vlan-stag-hw-insert: off [fixed]
                            rx-vlan-stag-hw-parse: off [fixed]
                            rx-vlan-stag-filter: off [fixed]
                            l2-fwd-offload: off
                            hw-tc-offload: off
                            esp-hw-offload: on
                            esp-tx-csum-hw-offload: on
                            rx-udp_tunnel-port-offload: on
                            tls-hw-tx-offload: off [fixed]
                            rx-gro-hw: off [fixed]
                            tls-hw-record: off [fixed]
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        :param win_vm_ip:
        return: {
                    RX:off,
                    TX:off,
                    ...
                }
        """
        result_dict = dict()

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.SHOW_FEATURES, device_name])
        if ns_name:
            exec_command = f"ip netns exec {ns_name} {exec_command}"
        if extra_para:
            exec_command = exec_command + f" {extra_para}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip)
        # log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # os_compatibility: 适配rocky
            rtn_outputs = rtn_outputs.replace("n/a", '0')
            # 将显示中的第一行截掉，防止误匹配
            split_result = rtn_outputs.split(device_name + constants.STR_COLON)[1]
            result_re = re.findall(pattern=constants.SHOW_FEATURES_PATTERN, string=split_result)
            for item in result_re:
                result_dict[item[0]] = item[1]
        return result_dict

    @classmethod
    def set_offload_and_features(cls, device_name: str, para_key: str, para_value: str,
                                 cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                                 win_vm_ip: str = None, fpga_flag: bool = False, netns_name: str = None,
                                 ssh_ip: str = None) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-18
        description:        ethtool --features命令
        :param device_name:   网卡设备名称,如ens1f0
        :param para_key:      修改的参数名
        :param para_value:    修改的参数值
        :param cmd_execute_address:
        :param win_vm_ip
        :param fpga_flag:是否为fpga厕所
        """
        if fpga_flag:
            return True
        else:
            rtn_status = False
            exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.FEATURES, device_name,
                                                     para_key, para_value])
            if netns_name:
                exec_command = f"ip netns exec {netns_name} {exec_command}"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address, win_vm_ip=win_vm_ip, ssh_ip=ssh_ip)
            # log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                rtn_status = True
            else:
                log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

            return rtn_status

    @classmethod
    def show_driver_infomation(cls, device_name: str,
                               cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                               ssh_ip: str = None,
                               test_port: int = None,
                               nets_name: str = '',
                               shorten: bool = False) -> dict:
        """
        author:             xianda.liu
        date:               2022-07-16
        description:        ethtool --driver命令
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:执行命令环境
        :param test_port: ssh 连接端口
        :param shorten: 是否通过参数简写方式执行命令
        :param nets_name: namespace
        @changelog      2024-07-24 15:52:31  shanshan.du
                        1. 增加参数shorten,支持通过参数简写方式执行命令
                        2025-10-31 10:36:10  shanshan.du
                        1. 适配OVS
        """
        result_dict = dict()

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.DRIVER, device_name])
        if shorten:
            key_name = EthtoolParamShortenEnum.DRIVER.value
            exec_command = constants.STR_SPACE.join([constants.ETHTOOL, key_name, device_name])
        if nets_name:
            exec_command = f'ip netns exec {nets_name} {exec_command}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip,
            ssh_port=str(test_port) if test_port is not None else None, print_outputs=False)
        if "No such device" in rtn_outputs + rtn_err:
            log.info("当前设备不存在，等待3s再执行一次")
            time.sleep(3)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip,
                ssh_port=str(test_port) if test_port is not None else None, print_outputs=False)
        # log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            split_result = rtn_outputs.split('\n')

            for i in split_result:
                result_re = re.findall(pattern=constants.SHOW_DRIVER_PATTERN, string=i)
                for item in result_re:
                    result_dict[item[0]] = item[1]
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        log.info_caller(str(result_dict))
        return result_dict

    @classmethod
    def do_register_dump(cls, device_name: str,
                         cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> dict:
        """
        author:             xianda.liu
        date:               2022-07-16
        description:        ethtool --register-dump命令及部分结果解析
                            回显格式:
                            0x042A4: LINKS (Link Status register)                 0x79081193
                                   Link Status:                                   up
                                   Link Speed:                                    10G
                            0x05080: FCTRL (Filter Control register)              0x00000400
                                   Broadcast Accept:                              enabled
                                   Unicast Promiscuous:                           disabled
                                   Multicast Promiscuous:                         disabled
                                   Store Bad Packets:                             disabled
                            0x04294: MFLCN (TabMAC Flow Control register)         0x0000000A
                                   Receive Flow Control Packets:                  enabled
                                   Discard Pause Frames:                          enabled
                                   Pass MAC Control Frames:                       disabled
                                   Receive Priority Flow Control Packets:         disabled
                            0x05088: VLNCTRL (VLAN Control register)              0x40008100
                                   VLAN Mode:                                     disabled
                                   VLAN Filter:                                   enabled
                            0x02100: SRRCTL0 (Split and Replic Rx Control 0)      0x00000402
                                   Receive Buffer Size:                           2KB
                            0x03D00: FCCFG (Flow Control Configuration)           0x00000008
                                   Transmit Flow Control:                         enabled
                                   Priority Flow Control:                         disabled
                            0x04240: HLREG0 (Highlander Control 0 register)       0x08002FFF
                                   Transmit CRC:                                  enabled
                                   Receive CRC Strip:                             enabled
                                   Jumbo Frames:                                  enabled
                                   Pad Short Frames:                              enabled
                                   Loopback:                                      disabled

        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        return: {
                    'Link Status:': 'up',
                    'Link Speed:': '10G',
                    'Broadcast Accept:': 'enabled',
                    'Unicast Promiscuous:': 'disabled',
                    'Multicast Promiscuous:': 'disabled',
                    'Store Bad Packets:': 'disabled',
                    'Receive Flow Control Packets:': 'enabled',
                    'Discard Pause Frames:': 'enabled',
                    'Pass MAC Control Frames:': 'disabled',
                    'Receive Priority Flow Control Packets:': 'disabled',
                    'VLAN Mode:': 'disabled',
                    'VLAN Filter:': 'enabled',
                    'Receive Buffer Size:': '2KB',
                    'Transmit Flow Control:': 'enabled',
                    'Priority Flow Control:': 'disabled',
                    'Transmit CRC:': 'enabled',
                    'Receive CRC Strip:': 'enabled',
                    'Jumbo Frames:': 'enabled',
                    'Pad Short Frames:': 'enabled',
                    'Loopback:': 'disabled'
                    }

        """
        result_dict = dict()
        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.REGISTER_DUMP, device_name])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # os_compatibility: 适配rocky
            rtn_outputs = rtn_outputs.replace("n/a", '0')
            rtn_list = rtn_outputs.split('\n')
            for i in rtn_list:
                result_re = re.findall(pattern=constants.SHOW_REGISTER_DUMP_PATTERN, string=i)
                for item in result_re:
                    if item[0] != '' and not item[0].startswith('('):
                        result_dict[item[0].strip()] = item[1].strip()

        return result_dict

    @classmethod
    def count_registers_from_dump_info(
            cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> int or None:
        """
        author:             xianda.liu
        date:               2022-07-16
        description:        根据ethtool --register-dump结果统计寄存器个数
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        """
        register_num = None

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.REGISTER_DUMP, device_name])
        exec_command += ' |wc -l'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            register_num = int(rtn_outputs.split('\n')[0])

        return register_num

    @classmethod
    def restart_negotiation(cls, device_name: str,
                            cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-16
        description:        ethtool --negotiate命令
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.NEGOTIATE, device_name])

        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def show_visible_port_identification(cls, device_name: str, blinking_time: str = '10',
                                         cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-16
        description:        ethtool --identify命令
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.IDENTIFY,
                                                 device_name, blinking_time])

        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def execute_adapter_self_test(cls, device_name: str, para_status: str = None,
                                  cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-16
        description:        ethtool --test命令
        :param device_name:   网卡设备名称,如ens1f0
        :param para_status: offline
        :param cmd_execute_address:
        """
        rtn_status = False

        if para_status:
            exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.TEST,
                                                     device_name, para_status])
        else:
            exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.TEST, device_name])

        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        # log.info(f'command:{exec_command}, rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            if 'PASS' in rtn_outputs:
                rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def show_adapter_statistics(cls, device_name: str,
                                cmd_execute_address = CmdExecuteAdressEnum.CLIENT.value,
                                ssh_ip: str = None,
                                shorten: bool = False,
                                print_outputs: bool = True,
                                netns_name: str = None,
                                grep_str: str = None
                                ) -> dict:
        """
        author:             xianda.liu
        date:               2022-07-16
        description:        ethtool --statistics命令及结果解析
                            回显格式:
                            NIC statistics:
                             rx_packets: 2815
                             tx_packets: 2807
                             rx_bytes: 170326
                             tx_bytes: 169440
                             ...
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        :param ssh_ip:
        :param shorten: 是否通过参数简写方式执行命令
        :param netns_name: 网络命名空间
        return: {
                    RX:off,
                    TX:off,
                    ...
                }
        @changelog      2024-07-25 10:07:21  shanshan.du
                        1. 增加参数shorten,支持通过参数简写方式执行命令
        """
        result_dict = dict()

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.STATISTICS, device_name])
        if shorten:
            exec_command = constants.STR_SPACE.join([constants.ETHTOOL,
                                                     EthtoolParamShortenEnum.STATISTICS.value,
                                                     device_name])
        if netns_name:
            exec_command = f"ip netns exec {netns_name} {exec_command}"
        if grep_str:
            exec_command += f" |{grep_str}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip, print_outputs=print_outputs)
        # log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            if grep_str:
                split_result = rtn_outputs.split('statistics' + constants.STR_COLON)[0]
            # 将显示中的第一行截掉，防止误匹配
            else:
                split_result = rtn_outputs.split('statistics' + constants.STR_COLON)[1]
            result_re = re.findall(pattern=constants.SHOW_STATISTICS_PATTERN, string=split_result)
            for item in result_re:
                result_dict[item[0]] = item[1]

        return result_dict

    @classmethod
    def show_phy_statistics(cls, device_name: str,
                            cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> dict:
        pass

    @classmethod
    def show_rx_nfc_options(cls, device_name: str,
                            cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> dict:
        pass

    @classmethod
    def set_rx_nfc_options(cls, device_name: str, para_list: list,
                           cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        pass

    @classmethod
    def show_time_stamping_capability(cls, device_name: str,
                                      cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> dict:
        """
        author:             shaohui.wang
        date:               2022-10-10
        description:        ethtool -T|--show-time-stamping devname命令
                            [root@test254 ~]# ethtool -T ens1f1
                            Time stamping parameters for ens1f1:
                            Capabilities:
                                    hardware-transmit     (SOF_TIMESTAMPING_TX_HARDWARE)
                                    software-transmit     (SOF_TIMESTAMPING_TX_SOFTWARE)
                                    hardware-receive      (SOF_TIMESTAMPING_RX_HARDWARE)
                                    software-receive      (SOF_TIMESTAMPING_RX_SOFTWARE)
                                    software-system-clock (SOF_TIMESTAMPING_SOFTWARE)
                                    hardware-raw-clock    (SOF_TIMESTAMPING_RAW_HARDWARE)
                            PTP Hardware Clock: 3
                            Hardware Transmit Timestamp Modes:
                                    off                   (HWTSTAMP_TX_OFF)
                                    on                    (HWTSTAMP_TX_ON)
                            Hardware Receive Filter Modes:
                                    none                  (HWTSTAMP_FILTER_NONE)
                                    ptpv1-l4-sync         (HWTSTAMP_FILTER_PTP_V1_L4_SYNC)
                                    ptpv1-l4-delay-req    (HWTSTAMP_FILTER_PTP_V1_L4_DELAY_REQ)
                                    ptpv2-event           (HWTSTAMP_FILTER_PTP_V2_EVENT)
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        return:
                {'capabilities':
                                ['hardware-transmit', 'software-transmit', 'hardware-receive',
                                'software-receive', 'software-system-clock', 'hardware-raw-clock'],
                'Hardware Transmit Timestamp Modes'  :['off', 'on'],
                'Hardware Receive Filter Modes'      :['none', 'ptpv1-l4-sync', 'ptpv1-l4-delay-req', 'ptpv2-event'],
                'PTP Hardware Clock'                 :'2'
                }

        """
        result_dict = {}

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.SHOW_TIME_STAMPING, device_name])

        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # 获取capabilities等键值对
            reg = r'Capabilities:([\s\S]*)PTP[\s\S]*Timestamp Modes:([\s\S]*)Hardware Receive Filter Modes:([\s\S]*)'
            obj = re.search(reg, rtn_outputs)
            for i in range(1, 4):
                ls_temp = []
                ls = obj.group(i).strip().split('\n')
                for item in ls:
                    ls_temp.append(item.split()[0])
                # 第一处匹配
                if i == 1:
                    result_dict['capabilities'] = ls_temp
                # 第二处匹配
                elif i == 2:
                    result_dict['Hardware Transmit Timestamp Modes'] = ls_temp
                # 第三处匹配
                else:
                    result_dict['Hardware Receive Filter Modes'] = ls_temp

            # 获取PTP Hardware Clock键值对
            ls_re = re.findall(r'PTP Hardware Clock:\s*(\d)', rtn_outputs)
            if ls_re:
                result_dict['PTP Hardware Clock'] = ls_re[0]
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return result_dict

    @classmethod
    def flash_firmware_image(cls, device_name, filename: str, region_number: str,
                             cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        pass

    @classmethod
    def show_permanent_hardware_address(cls, device_name,
                                        cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> str:
        """
        author:             xianda.liu
        date:               2022-07-16
        description:        ethtool --show-permaddr命令
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        return: xx:xx:xx:xx:xx:xx
        """
        address = None

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.SHOW_PERMADDR, device_name])

        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            address = rtn_outputs.strip().split(':')[1]
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return address

    @classmethod
    def query_channels(cls, device_name: str,
                       cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, ssh_ip: str = None,
                       netns_name: str = None) -> dict:
        """
                author:             xianda.liu
                date:               2022-07-16
                description:        ethtool --show-channel命令及结果解析
                                    回显格式:
                                    Channel parameters for ens1f0:
                                    Pre-set maximums:
                                    RX:             0
                                    TX:             0
                                    Other:          1
                                    Combined:       4
                                    Current hardware settings:
                                    RX:             0
                                    TX:             0
                                    Other:          1
                                    Combined:       4
                :param device_name:   网卡设备名称,如ens1f0
                :param cmd_execute_address:
                return: {
                            'Pre-set maximums': {

                                },
                            'Current hardware settings': {

                                }
                        }
                """
        result_dict = dict()

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.SHOW_CHANNELS, device_name])
        if netns_name:
            exec_command = f"ip netns exec {netns_name} {exec_command}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # os_compatibility: 适配rocky
            rtn_outputs = rtn_outputs.replace("n/a", '0')
            # 将显示中的第一行截掉，防止误匹配
            split_result = rtn_outputs.split(device_name + constants.STR_COLON)[1]
            result = [i.strip() for i in split_result.split('\n')]

            for item in result:
                result_re = re.match(pattern=constants.SHOW_CHANNELS_PATTERN, string=item)

                # 如果没有匹配，可能有两种情况，一种是内容为空，这种丢弃；一种是有key值没有value值，这种作为第一级字典的key值
                if not result_re:
                    if item.split(':')[0] != '':
                        result_dict[item.split(':')[0]] = {}
                    else:
                        pass

                else:
                    # 遍历所有字典，确认要添加的key值是否已存在于结果中，如果存在跳出本轮循环
                    for key, value in result_dict.items():
                        if result_re.groups()[0] not in value.keys():
                            result_dict[key][result_re.groups()[0]] = result_re.groups()[1]
                        else:
                            continue

        return result_dict

    @classmethod
    def set_channels(cls, device_name: str, para_key: str, para_value: str,
                     cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, ssh_ip: str = None, netns_name: str = None) -> tuple:
        """
        author:             xianda.liu
        date:               2022-07-18
        description:        ethtool --set-channels命令
        :param device_name:   网卡设备名称,如ens1f0
        :param para_key:      修改的参数名
        :param para_value:    修改的参数值
        :param cmd_execute_address:
        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.SET_CHANNELS, device_name,
                                                 para_key, para_value])
        if netns_name:
            exec_command = f"ip netns exec {netns_name} {exec_command}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
        log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        outputs = rtn_outputs + ";" + rtn_err
        return rtn_status, outputs

    @classmethod
    def query_private_flags(cls, device_name: str,
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value) -> dict:
        """
        author:             xianda.liu
        date:               2022-07-16
        description:        ethtool --show-priv-flags命令及结果解析
                            回显格式:
                            Private flags for ens1f0:
                                legacy-rx: off
                                vf-ipsec : off

        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        return: {
                    legacy-rx: off,
                    vf-ipsec : off
                }
        """
        result_dict = dict()

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.SHOW_PRIV_FLAGS, device_name])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # 将显示中的第一行截掉，防止误匹配
            split_result = rtn_outputs.split(device_name + constants.STR_COLON)[1]
            result_re = re.findall(pattern=constants.SHOW_PRIV_FLAGS_PATTERN, string=split_result)
            for item in result_re:
                result_dict[item[0]] = item[1]

        return result_dict

    @classmethod
    def set_private_flags(cls, device_name: str, para_key: str, para_value: str,
                          cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-18
        description:        ethtool --set-priv-flags命令
        :param device_name:   网卡设备名称,如ens1f0
        :param para_key:      修改的参数名
        :param para_value:    修改的参数值
        :param cmd_execute_address:
        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.SET_PRIV_FLAGS, device_name,
                                                 para_key, para_value])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def get_standard_info(cls, device_name: str,
                          cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, netns_name: str = None) -> dict:
        """
        author:             xianda.liu
        date:               2022-08-31
        description:        ethtool device命令
        :param device_name:   网卡设备名称,如ens1f0
        :param cmd_execute_address:
        return: {
                    'Supported ports': '[ FIBRE ]',
                    'Supported link modes': '10000baseT/Full',
                    'Supported pause frame use': 'Symmetric',
                    'Supports auto-negotiation': 'No',
                    'Supported FEC modes': 'Not reported',
                    'Advertised link modes': '10000baseT/Full',
                    'Advertised pause frame use': 'Symmetric',
                    'Advertised auto-negotiation': 'No',
                    'Advertised FEC modes': 'Not reported',
                    'Speed': '10000Mb/s',
                    'Duplex': 'Full',
                    'Port': 'FIBRE',
                    'PHYAD': '0',
                    'Transceiver': 'internal',
                    'Auto-negotiation': 'off',
                    'Supports Wake-on': 'd',
                    'Wake-on': 'd',
                    'Current message level': '0x00000007 (7)',
                    'Link detected': 'yes'
                }

        """
        try:
            result_dict = dict()
            exec_command = constants.STR_SPACE.join([constants.ETHTOOL, device_name])
            if netns_name:
                exec_command = f"ip netns exec {netns_name} {exec_command}"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                # 将显示中的第一行截掉，防止误匹配
                split_result = rtn_outputs.split(device_name + constants.STR_COLON)[1]
                item_list = split_result.split('\n')
                for item in item_list:
                    if constants.STR_COLON in item:
                        result_dict[item.split(constants.STR_COLON)[0].strip()] = item.split(
                            constants.STR_COLON)[1].strip()
                # Supported link modes回显有多行，需特殊处理
                re_result = re.search(r'Supported link modes:([\s\S]+)Supported pause frame use', rtn_outputs)
                if re_result:
                    result_dict['Supported link modes'] = re_result.group(1).split()
                re_result = re.search(r'Advertised link modes:([\s\S]+)Advertised pause frame use', rtn_outputs)
                if re_result:
                    result_dict['Advertised link modes'] = re_result.group(1).split()
        except Exception as e:
            result_dict = {
                'Supported ports': '[ FIBRE ]',
                'Supported link modes': None,
                'Supported pause frame use': 'Symmetric',
                'Supports auto-negotiation': 'No',
                'Supported FEC modes': 'Not reported',
                'Advertised link modes': None,
                'Advertised pause frame use': 'Symmetric',
                'Advertised auto-negotiation': None,
                'Advertised FEC modes': 'Not reported',
                'Speed': None,
                'Duplex': None,
                'Port': None,
                'PHYAD': '0',
                'Transceiver': 'internal',
                'Auto-negotiation': None,
                'Supports Wake-on': 'd',
                'Wake-on': 'd',
                'Current message level': '0x00000007 (7)',
                'Link detected': None
            }
            pattern_dict = {
                "capacity": r"capacity:\s*([^\n]+)",
                "autonegotiation": r"autonegotiation=([^\s]+)",
                "duplex": r"duplex=([^\s]+)",
                "link": r"link=([^\s]+)",
                "port": r"port=([^\s]+)",
            }
            exec_command = f'lshw -class network|grep -A 12 \\"logical name: {device_name}\\"'
            rtn_code, rtn_stdout, rtn_err = CommandOperation.execute_command_with_error(
                cmd=exec_command, cmd_execute_address=cmd_execute_address)
            result = {}
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                for key, pattern in pattern_dict.items():
                    match = re.search(pattern, rtn_stdout)
                    if match:
                        result[key] = match.group(1)
                result_dict["Advertised auto-negotiation"] = result["autonegotiation"]
                result_dict["Auto-negotiation"] = result["autonegotiation"]
                result_dict["Duplex"] = result["duplex"]
                result_dict["Link detected"] = result["link"]

                try:
                    result_dict["Supported ports"] = f"[ {result['port'].upper()} ]"
                    result_dict['Port'] = result["port"].upper()
                except Exception as e:
                    result_dict['Port'] = "FIBRE"
                    result_dict["Supported ports"] = "[ FIBRE ]"
                result_dict["Speed"] = str(int(re.search(r"\d+", result["size"]).group()) * 1000) + "Mb/s"
                result_dict["Advertised link modes"] = str(
                    int(re.search(r"\d+", result["size"]).group()) * 1000) + "T/Full"
                result_dict["Supported link modes"] = str(
                    int(re.search(r"\d+", result["size"]).group()) * 1000) + "T/Full"
        return result_dict

    @classmethod
    def set_fdir_info(cls, device_name, flow_type: str, action: str = '', queue: str = '',
                      loc: str = '', vf: str = '',
                      cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value, netns_name: str = None,
                      **kwargs):
        """
        author:             shaohui.wang
        date:               2022-10-10
        description:        ethtool -N|-U|--config-nfc|--config-ntuple devname
              flow-type ether|ip4|tcp4|udp4|sctp4|ah4|esp4|ip6|tcp6|udp6|ah6|esp6|sctp6
                        [ src %x:%x:%x:%x:%x:%x [m %x:%x:%x:%x:%x:%x] ]
                        [ dst %x:%x:%x:%x:%x:%x [m %x:%x:%x:%x:%x:%x] ]
                        [ proto %d [m %x] ]
                        [ src-ip IP-ADDRESS [m IP-ADDRESS] ]
                        [ dst-ip IP-ADDRESS [m IP-ADDRESS] ]
                        [ tos %d [m %x] ]
                        [ tclass %d [m %x] ]
                        [ l4proto %d [m %x] ]
                        [ src-port %d [m %x] ]
                        [ dst-port %d [m %x] ]
                        [ spi %d [m %x] ]
                        [ vlan-etype %x [m %x] ]
                        [ vlan %x [m %x] ]
                        [ user-def %x [m %x] ]
                        [ dst-mac %x:%x:%x:%x:%x:%x [m %x:%x:%x:%x:%x:%x] ]
        :param device_name:   网卡设备名称,如ens1f0
        :param flow_type:     取值为ether|ip4|tcp4|udp4|sctp4|ah4|esp4|ip6|tcp6|udp6|ah6|esp6|sctp6
        :param action:        Specifies the Rx queue to send packets to, or some other action.
                              -1            Drop the matched flow
                              0 or higher   Rx queue to route the flow
        :param loc:
        :param vf:
        :param cmd_execute_address:
        """
        rtn_status = False

        # 此处的掩码为反掩码 如 要匹配192.168.100.1/24网段，掩码应设为0.0.0.255
        param_dict = {
            # 二层头字段
            'src': None, 'src-mask': None, 'dst': None, 'dst-mask': None, 'proto': None, 'proto-mask': None,
            'src-ip': None, 'src-ip-mask': None, 'dst-ip': None, 'dst-ip-mask': None,
            # ipv4头字段
            'tos': None, 'tos-mask': None,
            # ipv6头字段
            'tclass': None, 'tclass-mask': None,
            'l4proto': None, 'l4proto-mask': None,
            'src-port': None, 'src-port-mask': None, 'dst-port': None, 'dst-port-mask': None,
            'spi': None, 'spi-mask': None, 'l4data': None, 'l4data-mask': None,
            'vlan-etype': None, 'vlan-etype-mask': None, 'vlan': None, 'vlan-mask': None,
            'user-def': None, 'user-def-mask': None,
            'dst-mac': None, 'dst-mac-mask': None
        }

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.CONFIG_NTUPLE, device_name, 'flow-type',
                                                 flow_type])
        for key_value in kwargs.keys():
            if key_value in param_dict.keys():
                exec_command = constants.STR_SPACE.join([exec_command, key_value, kwargs[key_value]])
            else:
                raise Exception("要修改的键值对不在此字典内,请确认修改")

        if vf:
            exec_command += ' vf ' + str(vf)
        if action:
            exec_command += ' action ' + str(action)
        elif queue:
            exec_command += ' queue ' + str(queue)

        if loc:
            exec_command += ' loc ' + str(loc)
        if netns_name:
            exec_command = f' ip netns exec {netns_name} {exec_command}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info(f'command:{exec_command},rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value and \
                r'rmgr: Cannot insert RX class rule: Operation not supported' not in rtn_err + rtn_outputs:
            rtn_status = True
        elif rtn_code == RtnStatusEnum.SUCCESS.value and \
                r'rmgr: Cannot insert RX class rule: Operation not supported' in rtn_err:
            rtn_status = False
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        return rtn_status

    @classmethod
    def del_fdir_rule(cls, device_name, rule_id: str, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value):
        """
        author:             shaohui.wang
        date:               2022-10-10
        description:        ethtool -N|-U|--config-nfc|--config-ntuple devname delete N
        :param device_name: 网卡设备名称,如ens1f0
        :param rule_id:     要删除的规则的ID
        :param cmd_execute_address:
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.CONFIG_NTUPLE, device_name, 'delete',
                                                 str(rule_id)])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def get_fdir_info(cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                      netns_name: str = None) -> tuple:
        """
        author:             shaohui.wang
        date:               2022-10.10
        description:        ethtool -n|-u|--show-nfc|--show-ntuple devname
                            4 RX rings available
                            Total 2 rules

                            Filter: 2044
                                    Rule Type: TCP over IPv4
                                    Src IP addr: 192.168.1.1 mask: 0.0.0.255
                                    Dest IP addr: 192.168.2.1 mask: 0.0.0.255
                                    TOS: 0x0 mask: 0xff
                                    Src port: 0 mask: 0xffff
                                    Dest port: 0 mask: 0xffff
                                    VLAN EtherType: 0x0 mask: 0xffff
                                    VLAN: 0x0 mask: 0xffff
                                    User-defined: 0x0 mask: 0xffffffffffffffff
                                    Action: Direct to queue 1

        :param device_name: 网卡设备名称,如ens1f0
        :param cmd_execute_address:
        return:
                            ring_num, rule_num, result_dict
                            result_dict格式如下：
                            {'2044': {
                                     'Rule Type': 'TCP over IPv4',
                                     'Src IP addr': ['192.168.1.0', '0.0.0.255'],
                                     'Dest IP addr': ['192.168.2.0', '0.0.0.255'],
                                     'TOS': ['0x0', '0xff'],
                                     'Src port': ['0', '0xffff'],
                                     'Dest port': ['0', '0xffff'],
                                     'VLAN EtherType': ['0x0', '0xffff'],
                                     'VLAN': ['0x0', '0xffff'],
                                     'User-defined': ['0x0', '0xffffffffffffffff'],
                                     'Action': 'Direct to queue 0'}
                            }
        """
        ring_num = 0
        rule_num = 0
        result_dict = dict()
        second_dict = dict()
        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.SHOW_NTUPLE, device_name])
        if netns_name:
            exec_command = f"ip netns exec {netns_name} {exec_command}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))

        result_re = re.search(r'(\d+) RX rings available', rtn_outputs)
        if result_re:
            ring_num = int(result_re.group(1))
        else:
            ring_num = 0

        result_re = re.search(r'Total (\d+) rules', rtn_outputs)
        if result_re:
            rule_num = int(result_re.group(1))
        else:
            rule_num = 0
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            result_re = re.search(r'(\d+) RX rings available', rtn_outputs)
            if result_re:
                ring_num = result_re.group(1)

            result_re = re.search(r'Total (\d+) rules', rtn_outputs)
            rule_num = result_re.group(1)

            if 'Filter' in rtn_outputs:
                filter_list = rtn_outputs.split('Filter:')
                # 去掉前三行
                del filter_list[0]
                for item in filter_list:
                    # item中第一个数字作为一级字典的key
                    item_list = item.split('\n')
                    key = item_list[0].strip()
                    for line in item_list:
                        if 'mask' not in line:
                            # 形似Rule Type: TCP over IPv4的行
                            if ':' in line:
                                second_dict[line.split(':')[0].strip()] = line.split(':')[1].strip()
                            else:
                                pass
                        else:
                            # 形似Src IP addr: 1.0.0.1 mask: 0.0.0.0的行
                            temp_str = line.replace('mask', '')
                            second_dict[temp_str.split(': ')[0].strip()] = [temp_str.split(':')[1].strip(),
                                                                           temp_str.split(':')[2].strip()]

                    result_dict[key] = second_dict.copy()
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        log.info("获取到ring_num：{}，rule_num：{}，result_dict：{}".format(ring_num, rule_num, result_dict))
        return int(ring_num), int(rule_num), result_dict

    @classmethod
    def get_rx_flow_hash(cls, device_name: str, flow_type: str,
                         cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, netns_name: str = None) -> str:
        """
        author:             shaohui.wang
        date:               2022-09-03
        description:        命令：ethtool -n|-u|--show-nfc|--show-ntuple devname
                            rx-flow-hash tcp4|udp4|ah4|esp4|sctp4|tcp6|udp6|ah6|esp6|sctp6

                            [root@test254 ~]# ethtool -n ens1f1 rx-flow-hash tcp4
                            TCP over IPV4 flows use these fields for computing Hash flow key:
                            IP SA
                            IP DA
                            L4 bytes 0 & 1 [TCP/UDP src port]
                            L4 bytes 2 & 3 [TCP/UDP dst port]

        :param device_name: 网卡设备名称,如ens1f0
        :param flow_type:   取值为tcp4|udp4|ah4|esp4|sctp4|tcp6|udp6|ah6|esp6|sctp6
        :param cmd_execute_address:
        return:
        UDP over IPV4 flows use these fields for computing Hash flow key:
        IP SA
        IP DA
        """
        result_str = ''
        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.SHOW_NTUPLE, device_name,
                                                 'rx-flow-hash', flow_type])
        if netns_name:
            exec_command = f"ip netns exec {netns_name} {exec_command}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            result_str = rtn_outputs
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return result_str

    @classmethod
    def set_rx_flow_hash(cls, device_name: str, para_key: str, para_value: str,
                         cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, netns_name: str = None) -> bool:
        """
                author:             shaohui.wang
                date:               2022-09-03
                description:        ethtool -N|-U|--config-nfc|--config-ntuple devname rx-flow-hash 命令
                :param device_name:   网卡设备名称,如ens1f0
                :param para_key:      修改的参数名, tcp4|udp4|ah4|esp4|sctp4|tcp6|udp6|ah6|esp6|sctp6
                :param para_value:    修改的参数值，m|v|t|s|d|f|n|r
                :param cmd_execute_address:
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.CONFIG_NTUPLE, device_name,
                                                 'rx-flow-hash', para_key, para_value])
        if netns_name:
            exec_command = f"ip netns exec {netns_name} {exec_command}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def show_rxfh_indir(cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, ssh_ip:str = None) -> dict:
        """
                author:             shaohui.wang
                date:               2022-10-07
                description:        ethtool -x|--show-rxfh-indir|--show-rxfh devname 命令
                                    [root@test254 ~]# ethtool -x ens1f0
                                    RX flow hash indirection table for ens1f0 with 16 RX ring(s):
                                        0:      0     1     2     3     4     5     6     7
                                        8:      8     9    10    11    12    13    14    15
                                       16:      0     1     2     3     4     5     6     7
                                       24:      8     9    10    11    12    13    14    15
                                       32:      0     1     2     3     4     5     6     7
                                       40:      8     9    10    11    12    13    14    15
                                       48:      0     1     2     3     4     5     6     7
                                       56:      8     9    10    11    12    13    14    15
                                       64:      0     1     2     3     4     5     6     7
                                       72:      8     9    10    11    12    13    14    15
                                       80:      0     1     2     3     4     5     6     7
                                       88:      8     9    10    11    12    13    14    15
                                       96:      0     1     2     3     4     5     6     7
                                      104:      8     9    10    11    12    13    14    15
                                      112:      0     1     2     3     4     5     6     7
                                      120:      8     9    10    11    12    13    14    15
                                    RSS hash key:
                                    01:3d:09:8a:96:cb:ea:ac:5e:6d:0a:9c:15:df:e4:ce:1f:02:48:23:7a:c9:00:75:c8
                                    :58:3d:74:cd:ec:89:1a:cc:b4:ad:73:7b:d4:ab:58
                                    RSS hash function:
                                        toeplitz: on
                                        xor: off
                                        crc32: off
                :param device_name: 网卡设备名称,如ens1f0
                :param cmd_execute_address:
                return:
                {
                     'rx_rings': 16   int 类型
                     'indir_table': ['0', '1', '2', ...........]
                     'indir_size': 16
                     'hash_key': '57:46:53:a3:d9:cb:ba:20:c1:1f:bb:4c:71:63:75:53:c2:b1:9c:b8:cd:a1:
                                  16:17:d4:ad:59:61:2f:25:36:5b:64:f2:1e:9f:a5:48:25:2c'
                      'hash_key_size':40
                      'hash_function': {
                        toeplitz: on
                        xor: off
                        crc32: off
                        }
                }
                """
        hash_func_dict = {}
        result_dict = {}

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.SHOW_RXFH, device_name])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
        # log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # 获取队列总个数
            first_line = rtn_outputs.split('\n')[0]
            # 适配6.6内核，第一行是空行
            if "with" not in first_line:
                first_line = rtn_outputs.split('\n')[1]
            ring_n_str = re.findall(r'\b\d{1,3}\b', first_line)[0]
            result_dict['rx_rings'] = int(ring_n_str)

            # 获取equal N 命令设置的值
            temp_str = rtn_outputs.split('ring(s):')[1]
            part1_str = temp_str.split('RSS')[0].strip()
            part1_str = re.sub(r'\d{1,4}:', '', part1_str)
            result_dict['indir_table'] = part1_str.split()
            result_dict['indir_size'] = len(set(result_dict['indir_table']))
            # log.info(result_dict['indir_table'])

            # 获取哈希key
            result_re = re.search(r'(\w\w:){2,}\w\w', rtn_outputs)
            hash_key = result_re.group()
            hash_key_size = (len(hash_key) + 1) // 3
            result_dict['hash_key'] = hash_key
            result_dict['hash_key_size'] = hash_key_size

            # 获取哈希函数字典
            part3_str = rtn_outputs.split('function:')[1].strip()
            item_list = part3_str.split('\n')
            for item in item_list:
                if constants.STR_COLON in item:
                    hash_func_dict[item.split(constants.STR_COLON)[0].strip()] = \
                        item.split(constants.STR_COLON)[1].strip()
            result_dict['hash_function'] = hash_func_dict

        return result_dict

    @classmethod
    def set_rxfh_indir(cls, device_name: str, hkey: str = '', equal: str = '', start: str = '',
                       weight: list = [], default: bool = False,
                       hfunc: str = '', context: str = '', new: bool = False, delete: str = False,
                       cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, ssh_ip: str = None,
                       netns_name: str = None) -> bool:
        """
                author:             shaohui.wang
                date:               2022-10-08
                description:        ethtool -X|--set-rxfh-indir|--rxfh devname [hkey xx:yy:zz:aa:bb:cc:...]
                                    [ equal N | weight W0 W1 ... | default ] [hfunc FUNC] [context CTX | new] [delete]
                                    命令
                :param device_name:   网卡设备名称,如ens1f0
                :param hkey:
                :param equal:        数字或字符串
                :param weight:
                :param default:
                :param hfunc:
                :param context:
                :param new:
                :param delete:
                :param cmd_execute_address:
        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.RXFH, device_name])
        if hkey:
            exec_command += ' hkey ' + hkey
        if equal:
            exec_command += ' equal ' + str(equal)
        if start:
            exec_command += ' start ' + str(start)
        if weight:
            exec_command += ' weight ' + constants.STR_SPACE.join([str(i) for i in weight])
        if default:
            exec_command += ' default'
        if hfunc:
            exec_command += ' hfunc ' + hfunc
        if context:
            exec_command += ' context ' + context
        if new:
            exec_command += ' new'
        if delete:
            exec_command += ' delete'
        if netns_name:
            exec_command = f"ip netns exec {netns_name} {exec_command}"
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
        log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')

        return rtn_status

    @classmethod
    def ethtool_get_module_info(cls, device_name: str,
                                cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> dict:
        """
        author:             yibo.gao
        date:               2025.11.01
        description:        获取光模块信息
                            [root@test254 ~]# ethtool -m ens1f1
                            Identifier                                : 0x03 (SFP)
                            Extended identifier                       : 0x04 (GBIC/SFP defined by 2-wire interface ID)
                            Connector                                 : 0x07 (LC)
                            Transceiver codes                         : 0x10 0x00 0x00 0x01 0x00 0x00 0x00 0x00 0x00
                            Transceiver type                          : 10G Ethernet: 10G Base-SR
                            Transceiver type                          : Ethernet: 1000BASE-SX
                            Encoding                                  : 0x06 (64B/66B)
                            BR, Nominal                               : 10300MBd
                            Rate identifier                           : 0x00 (unspecified)
                            Length (SMF,km)                           : 0km

        :param device_name: 网卡设备名称,如ens1f0
        :param cmd_execute_address: 命令执行位置
        return: 获取到的信息字典
        """
        result_dict = {}
        # ethtool -m ens1f1
        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, "-m", device_name])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            temp_list = rtn_outputs.split('\n')
            for line in temp_list:
                # Transceiver type : 10G Ethernet: 10G Base-SR特殊处理
                if line.count(':') >= 1:
                    ls = line.split(":", 1)
                    key_str = ls[0].strip()
                    value_str = ls[-1].strip()
                    # log.info("key_str:{}, {}".format(key_str, value_str.strip()))
                    if key_str not in result_dict:
                        result_dict[key_str] = value_str.strip()
                    else:
                        if isinstance(result_dict[key_str], list):
                            result_dict[key_str] = result_dict[key_str].append(value_str)
                        else:
                            result_dict[key_str] = [result_dict[key_str], value_str]
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        return result_dict


    @classmethod
    def get_module_info(cls, device_name: str,
                        cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, new_ethtool=False) -> dict:
        """
        author:             shaohui.wang
        date:               2022-10-10
        description:        获取光模块信息
                            [root@test254 ~]# ethtool -m ens1f1
                            Identifier                                : 0x03 (SFP)
                            Extended identifier                       : 0x04 (GBIC/SFP defined by 2-wire interface ID)
                            Connector                                 : 0x07 (LC)
                            Transceiver codes                         : 0x10 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00
                            Transceiver type                          : 10G Ethernet: 10G Base-SR
                            Encoding                                  : 0x06 (64B/66B)

        :param:
        return:
        """
        result_dict = {}
        if new_ethtool:
            exec_command = constants.STR_SPACE.join(['/usr/local/sbin/ethtool',
                                                     constants.DUMP_MODULE_EEPROM,
                                                     device_name])
        else:
            exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.DUMP_MODULE_EEPROM, device_name])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            temp_list = rtn_outputs.split('\n')
            for line in temp_list:
                # Transceiver type : 10G Ethernet: 10G Base-SR特殊处理
                if line.count(':') >= 1:
                    ls = line.split(':', 1)
                    key_str = ls[0].strip()
                    value_str = ls[-1].strip()
                    # log.info("key_str:{}, {}".format(key_str, value_str.strip()))
                    if key_str not in result_dict.keys():
                        result_dict[key_str] = value_str.strip()
                    else:
                        if isinstance(result_dict[key_str], list):
                            result_dict[key_str].append(value_str)
                        else:
                            result_dict[key_str] = [result_dict[key_str], value_str]
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        return result_dict

    @classmethod
    def do_eeprom_dump(cls, device_name: str, offset: str = '', length: str = '',
                       cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> tuple:
        """
        author:
        date:               2022-07-16
        description:        ethtool --eeprom-dump命令
                            [root@test253 ~]# ethtool -e ens1f1
                            Offset          Values
                            ------          ------
                            0x0000:         60 07 02 00 00 00 40 00 6d 00 fd 00 8d 01 a3 01
                            0x0010:         a9 01 af 01 b7 01 bf 01 c7 01 cf 01 09 02 b8 05
                            0x0020:         00 04 ff ff ff ff ff ff ff ff ff ff ff ff c8 02
                            0x0030:         ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff
                            0x0040:         ff ff ff ff ff ff ff ff ff ff ff ff ff ff fd 1e
                            0x0050:         f7 1e 22 40 22 40 a9 1d fd ff df 03 00 80 48 02
        :param device_name:   网卡设备名称,如ens1f0
        :param offset:        偏移
        :param length:        长度
        :param cmd_execute_address:
        return:
        result_offset  类型：str，从回显信息中获取的偏移
        result_length  类型：int，回显信息中数据的总个数
        """

        result_offset = 0
        result_length = 0

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.EEPROM_DUMP, device_name])
        if offset:
            exec_command += ' offset ' + str(offset)
        if length:
            exec_command += ' length ' + str(length)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            ls = rtn_outputs.split('\n')
            result_offset = ls[2].split(':')[0].strip()
            result_length = (len(ls) - 3) * 16 + len(ls[-1].split()) - 1

        return result_offset, result_length

    @classmethod
    def show_interface_desc(cls, driver_id: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei.yuan1
        description: 查看网卡的信息值
        :param cmd_execute_address:
        :param driver_id:
        :return:
        """
        exec_command = f"{constants.SXE2CLI64} /p{driver_id} show j"
        rtn_code, rtn_output, rtn_err = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            return rtn_code
        rtn_output = rtn_output.replace("\r", "")
        rtn_dict = json.loads(rtn_output)
        interface_dict = rtn_dict["System"][f"Port {driver_id}"]["Response Data"]["Basics"]
        return interface_dict

    @classmethod
    def show_driver_setting(cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                            ssh_ip: str = None, netns: str =None):
        """
        author: wei.yuan
        date：2022.10.20
        description: 显示网卡的配置信息
        Settings for ens1f0:
        Supported ports: [ FIBRE ]
        Supported link modes:   10000baseT/Full
        Supported pause frame use: Symmetric
        Supports auto-negotiation: No
        Supported FEC modes: Not reported
        Advertised link modes:  10000baseT/Full
        Advertised pause frame use: Symmetric
        Advertised auto-negotiation: No
        Advertised FEC modes: Not reported
        Speed: 10000Mb/s
        Duplex: Full
        Port: FIBRE
        PHYAD: 0
        Transceiver: internal
        Auto-negotiation: off
        Supports Wake-on: d
        Wake-on: d
        Current message level: 0x00000007 (7)
                               drv probe link
        Link detected: yes
        """
        result_dict = {}
        interface_info_dict = {}

        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, device_name])
        if netns:
            exec_command = "ip netns exec {} {}".format(netns, exec_command)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
        # log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            # 将显示中的第一行截掉，防止误匹配
            split_result = rtn_outputs.split(device_name + constants.STR_COLON)[1]
            temp_list = split_result.strip("\t").split('\n')
            temp_list = [i.strip("\t") for i in temp_list if i != "" and ":" in i]
            for index, item in enumerate(temp_list):
                # Transceiver type : 10G Ethernet: 10G Base-SR特殊处理
                if constants.STR_COLON in item:
                    result_dict[item.split(constants.STR_COLON)[0].strip()] = item.split(
                        constants.STR_COLON)[1].strip()
                    # Supported link modes回显有多行，需特殊处理
                re_result = re.search(r'Supported link modes:([\s\S]+)Supported pause frame use', rtn_outputs)
                advertise_result = re.search(r'Advertised link modes:([\s\S]+)Advertised pause frame use', rtn_outputs)

                if re_result:
                    result_dict['Supported link modes'] = re_result.group(1).split()
                    #log.info("Supported link modes:{}".format(result_dict['Supported link modes']))
                if advertise_result:
                    result_dict['Advertised link modes'] = advertise_result.group(1).split()
        for key, value in result_dict.items():
            if key == "Current message level":
                interface_info_dict[key] = value.split(" ")[0]
            else:
                interface_info_dict[key] = value

        return interface_info_dict

    @classmethod
    def is_support_switch_speed_device(cls, device_name: str, os_type: str = 'linux',
                                       cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                                       driver_id: str = '0') -> bool:
        """
        author:             junfeng.he
        date:               2023-11-02
        description:        查询网口是否支持切速
        :param device_name:   网卡设备名称,如ens1f0
        :param os_type:
        :param cmd_execute_address: 执行方向
        :param driver_id: 驱动适配器的ID
        return Bool
        """
        if os_type == 'windows':
            transceiver_type = []
            exec_command = f"{constants.SXE2CLI64} driver {driver_id} module_eeprom"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                item_list = rtn_outputs.split("\r\n")
                item_list = [index for index in item_list if index != ""]
                item_list = [index for index in item_list if ":" in index]
                for index in item_list:
                    if "Transceiver type" in index:
                        transceiver_type.append(index)
                if len(transceiver_type) >= 2:
                    return True
        else:
            device_info = cls.show_driver_setting(device_name=device_name, cmd_execute_address=cmd_execute_address)
            module_info = cls.get_module_info(device_name=device_name, cmd_execute_address=cmd_execute_address)
            transceiver_type = module_info.get("Transceiver type")
            log.info_caller(f"device info: {json.dumps(device_info)}")
            support_link_mode = device_info.get("Supported link modes")
            auto_negotiation = device_info.get("Auto-negotiation")
            advertised_auto_negotiation = device_info.get("Advertised auto-negotiation")
            advertised_link_mode = device_info.get("Advertised link modes")
            module_support_speed = cls.get_module_support_speed(
                device_name=device_name, os_type=os_type, cmd_execute_address=cmd_execute_address)
            # log.info("support_link_mode:{}".format(support_link_mode))
            # log.info("auto_negotiation:{}".format(auto_negotiation))
            # log.info("module_support_speed:{}".format(module_support_speed))
            if support_link_mode:
                if len(support_link_mode) >= 2 and len(module_support_speed) >= 2:
                    return True
        return False

    @classmethod
    def get_optical_module(cls, device_name: str, os_type, cmd_execute_address) -> bool:
        """
        author:             wei.yuan1
        date:               2024-15-20
        description:        获取网口模块信息
        :param device_name:   网卡设备名称,如ens1f0
        :param os_type:
        """
        rtn_code = False
        if os_type == 'windows':
            exec_command = f"{constants.SXE2CLI64} driver {device_name} module_eeprom"
        else:
            module_info = cls.get_module_info(device_name=device_name, cmd_execute_address=cmd_execute_address)
            if "Transceiver type" in module_info.keys():
                transceiver_type = module_info.get("Transceiver type")
                log.info_caller(f"device  module info: {json.dumps(module_info)}")
                pattern = r"\b\d+G\b"
                match = re.findall(pattern, transceiver_type)
                rtn_code = True if len(set(match)) > 1 else False
            else:
                log.warning("未获取到Transceiver type的解析信息！！尝试获取编码信息")
                speed_list = []
                if "0x0000" in module_info.keys():
                    source_code = module_info.get("0x0000")
                    # 03 04 07 10 00 00 01 00 00 00 00 06 67 00 00 00
                    source_code_list = source_code.split(" ")
                    if source_code_list[0] == "03":
                        if source_code_list[3] in ["10", "20"]:
                            speed_list.append(10000)
                        if source_code_list[6] in ["01", "02", "08"]:
                            speed_list.append(1000)
                rtn_code = True if len(speed_list) > 1 else False
        return rtn_code

    @classmethod
    def get_module_support_speed(cls, device_name: str, os_type, cmd_execute_address) -> list:
        """
        author:             wei.yuan1
        date:               2024-15-20
        description:        获取网口光模块信息
        :param device_name:   网卡设备名称,如ens1f0
        :param os_type:
        """
        speed_list = []
        if os_type == 'windows':
            exec_command = f"{constants.SXE2CLI64} driver {device_name} module_eeprom"
        else:
            module_info = cls.get_module_info(device_name=device_name, cmd_execute_address=cmd_execute_address)
            if "Transceiver type" in module_info.keys():
                transceiver_type = module_info.get("Transceiver type")
                log.info_caller(f"device module info: {json.dumps(module_info)}")
                if isinstance(transceiver_type, list):
                    info_list = transceiver_type
                else:
                    info_list = [transceiver_type]
                for info in info_list:
                    if '25G' in info:
                        speed_list.append(SpeedEnum.SPEED_25G.value)
                    # if '50G' in info:
                    #     speed_list.append(SpeedEnum.SPEED_50G.value)
                    # if '100G' in info:
                    #     speed_list.append(SpeedEnum.SPEED_100G.value)
                    if '10G' in info:
                        speed_list.append(SpeedEnum.SPEED_10G.value)
                # for info in info_list:
                #     match = re.findall(r"(\d+)BASE", info)
                #     if match:
                #         speed_list.append(int(match[0]))
                #     match = re.findall(r"(\d+)G", info)
                #     if match:
                #         speed_list.append(int(match[0]) * 1000)
            else:
                log.warning("未获取到Transceiver type的解析信息！！尝试获取编码信息:\n{}".format(module_info))
                if "0x0000" in module_info.keys():
                    source_code = module_info.get("0x0000")
                    # 03 04 07 10 00 00 01 00 00 00 00 06 67 00 00 00
                    log.info("source_code:{}".format(source_code))
                    source_code_list = source_code.split(" ")
                    log.info("source_code_list:{}".format(source_code_list))
                    if source_code_list[0] == "03":
                        if source_code_list[3] in ["10", "20"]:
                            speed_list.append(10000)
                        if source_code_list[6] in ["01", "02", "08"]:
                            speed_list.append(1000)
                    log.info("speed_list:{}".format(speed_list))
        return speed_list

    @classmethod
    def get_module_trans_type(cls, device_name: str, os_type='',
                              cmd_execute_address=CmdExecuteAdressEnum.SERVER.value) -> dict:
        """
        author:             shanshan.du
        date:               2025-11-27
        description:        获取网口光模块信息支持的速率和介质类型
        :param device_name:   网卡设备名称,如ens1f0
        :param os_type:
        """
        speed_type_dict = {}
        if os_type == 'windows':
            exec_command = f"{constants.SXE2CLI64} driver {device_name} module_eeprom"
        else:
            exec_command = constants.STR_SPACE.join([constants.ETHTOOL, constants.DUMP_MODULE_EEPROM, device_name])
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                module_info = rtn_outputs
                t_pattern = r'Transceiver type\s+:\s+(.*)\n'
                trans_info_list = re.findall(t_pattern, module_info)
                log.warning(f'trans_info_list = {trans_info_list}')
                for trans_info in trans_info_list:
                    if 'Ethernet:' in trans_info:
                        trans_info = trans_info.split('Ethernet:')[-1]

                    tran_type_pattern = r'(\d+)G.*?(Base-[A-Z0-9]{2,})'
                    tran_type_list = re.findall(tran_type_pattern, trans_info)
                    for speed_v, type_v in tran_type_list:
                        speed_type_dict[int(f'{speed_v}000')] = type_v
        log.warning(f'speed_type_dict = {speed_type_dict}')
        return speed_type_dict

    @classmethod
    def split_speed(cls, speed_value):  # -> tuple[int, Any] | None:
        """_summary_

        Args:
            speed_value (_type_): 将字符与数据进行拆分

        Returns:
            _type_: 数据和单位
        """

        pattern = r"^(\d+)(.*)"
        match = re.match(pattern, speed_value)
        if match:
            return int(match.group(1)), match.group(2)
        else:
            return None, None

    @classmethod
    def get_interface_support_speed(cls, device_name: str, os_type: str = "linux",
                                    cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author:             wei.yuan1
        date:               2024-15-20
        description:        获取网口最大速率
        :param device_name:   网卡设备名称,如ens1f0
        :param os_type:
        Returns:
            网口最大速率模式与网口最小速率模式
        
        """
        device_info = cls.show_driver_setting(device_name=device_name, cmd_execute_address=cmd_execute_address)
        log.info_caller(f"device info: {json.dumps(device_info)}")
        supported_link_modes = device_info.get("Supported link modes")
        speed_list = []
        media_type_list = []
        max_support_link_mode = []
        min_support_link_mode = []

        for speed in supported_link_modes:
            speed_num, media_type = cls.split_speed(speed)
            speed_list.append(speed_num)
            media_type_list.append(media_type)
        max_support_speed = str(max(speed_list))
        min_support_speed = str(min(speed_list))
        for speed in supported_link_modes:
            if max_support_speed in speed:
                max_support_link_mode.append(speed)
            elif min_support_speed in speed:
                min_support_link_mode.append(speed)
        return max_support_link_mode, min_support_link_mode

    @classmethod
    def speed_convert_to_register_value(cls, driver_type, speed: int, medium_type: str = "") -> str:
        """
        author:             junfeng.he
        date:               2024-09-10
        description:        网口速率转换成ethtool配置寄存器值
        """
        reg = ""
        if driver_type == NicNameEnum.SXE.value:
            if speed == SpeedEnum.SPEED_1G.value:
                reg = "0x22440"
            else:
                reg = "0x82440"
        elif driver_type == NicNameEnum.SXE2.value:
            if speed == SpeedEnum.SPEED_1G.value:
                log.error(f'不支持速率1G')
                reg = ""  # 测试不支持1G
            elif speed == SpeedEnum.SPEED_10G.value:
                reg = "0x80400"
            elif speed == SpeedEnum.SPEED_25G.value:
                reg = "0x100000400"
            elif speed == SpeedEnum.SPEED_50G.value:
                reg = "0x800000400"
            elif speed == SpeedEnum.SPEED_100G.value:
                reg = "0x40004080000000"  # 需要找开发提供
            else:
                reg = ""
                log.error(f'不支持的速率')
        else:
            if speed == SpeedEnum.SPEED_100M.value:
                reg = "0x004"
            if speed == SpeedEnum.SPEED_1G.value:
                reg = "0x0020"
            elif speed == SpeedEnum.SPEED_10G.value:
                reg = "0x1000"
            elif speed == SpeedEnum.SPEED_25G.value:
                if "CR" in medium_type.upper():
                    reg = "0x80000000"
                elif "SR" in medium_type.upper():
                    reg = "0x200000000"
                # elif "KR" in medium_type.upper():
                #     reg = "0x100000000"
                else:
                    reg = random.choice(["0x80000000", "0x200000000"])
                    reg = random.choice(["0x80000000", "0x200000000", "0x100000000"])
            elif speed == SpeedEnum.SPEED_50G.value:
                if "CR2" in medium_type.upper():
                    reg = "0x400000000"
                elif "SR2" in medium_type.upper():
                    reg = "0x10000000000"
                else:
                    reg = random.choice(["0x400000000", "0x10000000000"])
            elif speed == SpeedEnum.SPEED_100G.value:
                if "KR4" in medium_type.upper():
                    reg = str(hex(1 << 36))
                elif "SR4" in medium_type.upper():
                    reg = str(hex(1 << 37))
                elif "CR4" in medium_type.upper():
                    reg = str(hex(1 << 38))
                elif "LR4" in medium_type.upper():
                    reg = str(hex(1 << 39))
                else:
                    reg = random.choice([str(hex(1 << 36)), str(hex(1 << 37)), str(hex(1 << 38)), str(hex(1 << 39))])
        return reg

    @classmethod
    def ethtool_s_dev_speed(cls, device_name: str, speed=SpeedEnum.SPEED_10G.value, os_type='linux',
                            cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, an=None):
        """
        author:             jianghe
        date:               2026-01-20
        description:        设置网口速率
        """
        if os_type == 'windows':
            if speed == SpeedEnum.SPEED_1G.value:
                speed_rate = "1.0 Gbps Full Duplex"
            elif speed == SpeedEnum.SPEED_10G.value:
                speed_rate = "10 Gbps Full Duplex"
            else:
                speed_rate = "Auto Negotiation"
            exec_command = f"{constants.SET_NET_ADAPTER_ADVANCED_PROPERTY} -name {device_name} " \
                           f"-DisplayName 'Speed & Duplex' -DisplayValue '{speed_rate}' -confirm:$false"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        else:
            exec_command = "ethtool -s {} speed {}".format(device_name, speed)
            if an:
                exec_command = exec_command + f' autoneg {an}'
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        return rtn_code

    @classmethod
    def ethtool_s_dev_advertise(cls, device_name, advertise, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value):
        """
        author:             jianghe
        date:               2026-01-20
        description:        设置网口宣称速率
        """
        exec_command = "ethtool -s {} advertise {}".format(device_name, advertise)
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        return rtn_code

    @classmethod
    def set_speed(cls, device_name: str, os_type, driver_type, cmd_execute_address,
                  speed: int = SpeedEnum.SPEED_10G.value, medium_type: str = None, register_value: str = None):
        """
        author:             junfeng.he
        date:               2023-11-02
        description:        设置网口速率
        :param device_name:   网卡设备名称,如ens1f0
        :param os_type:
        :param driver_type:
        :param cmd_execute_address:
        :param speed:    SpeedEnum.SPEED_1G.value, SpeedEnum.SPEED_10G.value
        :param medium_type: 介质类型
        """
        rtn_code = False
        if os_type == 'windows':
            if speed == SpeedEnum.SPEED_1G.value:
                speed_rate = "1.0 Gbps Full Duplex"
            elif speed == SpeedEnum.SPEED_10G.value:
                speed_rate = "10 Gbps Full Duplex"
            else:
                speed_rate = "Auto Negotiation"
            exec_command = f"{constants.SET_NET_ADAPTER_ADVANCED_PROPERTY} -name {device_name} " \
                           f"-DisplayName 'Speed & Duplex' -DisplayValue '{speed_rate}' -confirm:$false"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        else:
            reg = ""
            if not register_value:
                # register_value = cls.speed_convert_to_register_value(driver_type, speed, medium_type)
                # exec_command = "ethtool -s {} advertise {}".format(device_name, register_value)
                reg = cls.speed_convert_to_register_value(driver_type, speed, medium_type)
            else:
                if driver_type == NicNameEnum.SXE.value:
                    if speed == SpeedEnum.SPEED_1G.value:
                        reg = "0x22440"
                    else:
                        reg = "0x82440"
                elif driver_type == NicNameEnum.SXE2.value:
                    if speed == SpeedEnum.SPEED_1G.value:
                        log.error(f'不支持速率1G')
                        reg = ""  # 测试不支持1G
                    elif speed == SpeedEnum.SPEED_10G.value:
                        reg = "0x80400"
                    elif speed == SpeedEnum.SPEED_25G.value:
                        reg = "0x100000400"
                    elif speed == SpeedEnum.SPEED_50G.value:
                        reg = "0x800000400"
                    elif speed == SpeedEnum.SPEED_100G.value:
                        reg = "0x40004080000000"  # 需要找开发提供
                    else:
                        reg = ""
                        log.error(f'不支持的速率')
                else:
                    if speed == SpeedEnum.SPEED_100M.value:
                        reg = "0x004"
                    elif speed == SpeedEnum.SPEED_1G.value:
                        reg = "0x0020"
                    elif speed == SpeedEnum.SPEED_10G.value:
                        # reg = "0x20000000000"
                        # reg = "0x40000000000"
                        reg = "0x80000000000"
                    elif speed == SpeedEnum.SPEED_25G.value:
                        if "CR" in medium_type.upper():
                            reg = "0x80000000"
                        elif "SR" in medium_type.upper():
                            reg = "0x200000000"
                        # elif "KR" in medium_type.upper():
                        #     reg = "0x100000000"
                        else:
                            reg = random.choice(["0x80000000", "0x200000000"])
                            reg = random.choice(["0x80000000", "0x200000000", "0x100000000"])
                    elif speed == SpeedEnum.SPEED_50G.value:
                        if "CR2" in medium_type.upper():
                            reg = "0x400000000"
                        elif "SR2" in medium_type.upper():
                            reg = "0x10000000000"
                        else:
                            reg = random.choice(["0x400000000", "0x10000000000"])
                    elif speed == SpeedEnum.SPEED_100G.value:
                        if "KR4" in medium_type.upper():
                            reg = str(hex(1 << 36))
                        elif "SR4" in medium_type.upper():
                            reg = str(hex(1 << 37))
                        elif "CR4" in medium_type.upper():
                            reg = str(hex(1 << 38))
                        elif "LR4" in medium_type.upper():
                            reg = str(hex(1 << 39))
                        else:
                            reg = random.choice(
                                [str(hex(1 << 36)), str(hex(1 << 37)), str(hex(1 << 38)), str(hex(1 << 39))])
            exec_command = "ethtool -s {} advertise {}".format(device_name, reg)
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        return rtn_code

    @classmethod
    def get_speed(cls, device_name: str, os_type, cmd_execute_address, driver_id: str = "0",
                  ssh_ip: str = None) -> int:
        """
        author:             junfeng.he
        date:               2023-11-02
        description:        得到网口速率
        :param device_name:   网卡设备名称,如ens1f0
        :param os_type:
        :param cmd_execute_address:
        return 1000,10000
        """

        def analyse_properties(outputs: str) -> dict:
            """
            description: 对网卡的参数进行解释
            :param outputs:
            :return:

            """
            # 创建新的字典
            dictionary = {}
            # 移除字符串中的换行符和空白字符
            rtn_output = outputs.replace('\r', '')
            cleaned_string = rtn_output.strip()
            # 分割字符串为行
            lines = cleaned_string.split('\n')
            # 遍历每一行的数据
            new_lines_str = ""
            for i, line in enumerate(lines):
                if ":" in line:
                    if i > 0:
                        new_lines_str += ("\n" + line)
                    else:
                        new_lines_str += line
                else:
                    if i > 0 and line:
                        new_lines_str += line.strip()
            new_lines = new_lines_str.split("\n")
            # 遍历每一行的数据
            for line in new_lines:
                # 分割行为键值对
                key, value = line.split(':', 1)
                # 清除键和值两侧的空白字符
                key = key.strip()
                value = value.strip()
                # 将键值对添加到字典中
                dictionary[key] = value
            return dictionary

        def get_nic_speed(nic_name):
            cmd_command = \
                f"{constants.GET_NET_ADAPTER} -name {nic_name} |FL"
            code, code_outputs, code_err = CommandOperation.execute_command_with_error(
                cmd_command, cmd_execute_address=cmd_execute_address)
            log.info(code_outputs)
            if "LinkSpeed(Gbps)" in analyse_properties(code_outputs):
                link_speed = analyse_properties(code_outputs)["LinkSpeed(Gbps)"]
                speed_unit = "Gbps"
            elif "LinkSpeed(Mbps)" in analyse_properties(code_outputs):
                link_speed = analyse_properties(code_outputs)["LinkSpeed(Mbps)"]
                speed_unit = "Mbps"
            else:
                link_speed = "0"
                speed_unit = ""
            return int(re.sub("\r+", "", link_speed)), speed_unit

        if os_type == 'windows':
            speed, unit = get_nic_speed(nic_name=device_name)
            if unit == "Gbps":
                speed = speed * 1000
            elif unit == "Mbps":
                speed = speed
            else:
                speed = 0
        else:
            try:
                exec_command = "ethtool {}".format(device_name)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                    exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
                log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
                speeds = re.findall(r"Speed: (\d+)Mb/s", rtn_outputs)
                if len(speeds) > 0:
                    speed = int(speeds[0])
                else:
                    values = re.findall(r"Speed: (\w+)", rtn_outputs)[0]
                    speed = 0
                    log.error(f"speed is Wrong, value is {values}")
            except Exception as e:
                exec_command = f"cat /sys/class/net/{device_name}/speed"
                rtn_code, rtn_outputs, _ = CommandOperation.execute_command_with_error(
                    exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
                if rtn_outputs.isdigit():
                    speed = int(rtn_outputs)
                else:
                    speed = 0
                    log.error(f"speed is Wrong, value is 0")
        return speed

    @classmethod
    def change_interrupted_speed(cls, device_name: str, speed: str, cmd_execute_address) -> tuple:
        """
        author:             shanshan.du
        date:               2024-09-02
        description:        得到网口速率
        :param device_name:   网卡设备名称,如ens1f0
        :param speed: 网卡设备中断速率
        :param cmd_execute_address: 执行命令方向
        return 1000,10000
        """
        exec_command = constants.STR_SPACE.join([constants.ETHTOOL, '-s', device_name,
                                                 'advertise', speed])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        # log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        return rtn_code, rtn_outputs, rtn_err

    @classmethod
    def ethtool_flash(cls, device_name: str, file: str, region: str = None,
                      cmd_execute_address = CmdExecuteAdressEnum.SERVER.value) -> tuple:
        """
        author:             jianghe
        date:               2025.06.10
        description:        ethtool -f升级固件
        """
        exec_command = f'{constants.ETHTOOL} -f {device_name} {file}'
        if region:
            exec_command += f' {region}'
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address=cmd_execute_address)
        # log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        return rtn_code, rtn_outputs, rtn_err

    @classmethod
    def ethtool_set_fec(cls, device_name, mode, cmd_execute_address, os_type=''):
        """
        author:             jianghe
        date:               2025.07.22
        description:        设置网口fec
        """
        if os_type == 'windows':
            # todo
            pass
        else:
            exec_command = f"ethtool --set-fec {device_name} encoding {mode}"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        return rtn_code

    @classmethod
    def ethtool_show_fec(cls, device_name, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, os_type=''):
        """
        author:             jianghe
        date:               2025.07.22
        description:        查询网口fec
        """
        rtn_code = False
        if os_type == 'windows':
            # todo
            pass
        else:
            exec_command = f"ethtool --show-fec {device_name}"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
            fec_parameters = {}
            fec_parameters.update(
                {'Configured FEC encodings': re.findall('Configured FEC encodings:\s*(.*)\n', rtn_outputs)[0]})
            fec_parameters.update(
                {'Active FEC encoding': re.findall('Active FEC encoding:\s*(.*)', rtn_outputs)[0]})
            return fec_parameters

    @classmethod
    def ethtool_set_autoneg(cls, device_name, switch, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value, os_type=''):
        """
        author:             jianghe
        date:               2025.07.22
        description:        设置自协商开关
        """
        if os_type == 'windows':
            # todo
            pass
        else:
            exec_command = f"ethtool -s {device_name} autoneg {switch}"
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                exec_command, cmd_execute_address=cmd_execute_address)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
            return rtn_code


if __name__ == '__main__':
    a = EthtoolOperation.get_speed('sxe-5', os_type="windows", cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    flow_configure = {'flow_type': 'tcp4','src-ip': '192.135.23.1',
                      'dst-ip': '5.5.23.2',
                      'dst-port': '5600',
                      'src-port': '78560',
                      'action': 1}

    # b = EthtoolOperation.query_channels("ens1f0")
    #
    # for key, value in b.items():
    #     print(key, ":", value)
    # c = EthtoolOperation.query_channels("ens1f0")
    # d = EthtoolOperation.show_time_stamping_capability("ens1f0")
    # print(d)
    # print(c["Current hardware settings"])
    # print("!!!!!!!!!!")
    # # print(a)
    # rx_queue = {}
    # for key, value in b.items():
    #     if "rx_queue" in key and "packets" in key:
    #         rx_queue[key] = value
    #     else:
    #         pass
    # for key, value in rx_queue.items():
    #     print(key,":",value)
