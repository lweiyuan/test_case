import pdb
import re
import time
import json
from typing import Union

# from numpy.distutils.exec_command import exec_command

import add_syspath
from typing import Union

from scripts.script_libs.script_base import ScriptBase
from scripts.script_libs import constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum, BondModeEnum, MacVlanModeEnum, OpcodeEnum, \
    ChipIdentification, FpgaBitfileClass
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.ifconfig import IfConfig


class IpOperation(object):

    @classmethod
    def set_devices_mtu(cls, drives_name: str, drives_mtu: str, win_vm_ip: str = None,
                        cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, test_reverse: bool = False):
        """
        author: weiyuan
        date:   2022.07.27
        description: 修改网卡的mtu值
        :param drives_name: 网卡名称
        :param drives_mtu: mtu值修改
        :param cmd_execute_address:
        :return 返回值，返回错误信息
        """
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        guest_os_server, guest_os_client = CommonOperation.get_guest_os(test_reverse)
        # windows系统命令行处理
        if (cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and 'windows' in host_os_client) or \
                (cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and 'windows' in host_os_server) or \
                (
                        cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and 'windows' in guest_os_client and win_vm_ip) or \
                (
                        cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and 'windows' in guest_os_server and win_vm_ip):
            # Get-NetAdapterAdvancedProperty -Name sxe-3 -DisplayName 'Jumbo Packet' | FL -Property *
            # Set-NetAdapterAdvancedProperty -Name sxe-3 -DisplayName 'Jumbo Packet' -DisplayValue '9014 Bytes'
            if drives_mtu not in ['4074', '9000']:
                taget_mtu = "Disabled"
            else:
                taget_mtu = "{} Bytes".format(int(drives_mtu) + 14)
            exec_command = "Set-NetAdapterAdvancedProperty -Name '{}' -DisplayName 'Jumbo Packet' " \
                           "-DisplayValue '{}'".format(drives_name, taget_mtu)
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_with_error(
                    cmd=exec_command, win_vm_ip=win_vm_ip, cmd_execute_address=cmd_execute_address)
            exec_command = "Get-NetAdapterAdvancedProperty -Name '{}' -DisplayName 'Jumbo Packet' | FL -Property *". \
                format(drives_name)
            rtn_code1, rtn_outputs1, rtn_err1 = \
                CommandOperation.execute_command_with_error(
                    cmd=exec_command, win_vm_ip=win_vm_ip, cmd_execute_address=cmd_execute_address)
            log.info("rtn_code1:{}, rtn_outputs1:{}, rtn_err1:{}".format(rtn_code1, rtn_outputs1, rtn_err1))
        else:
            exec_command = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.SET,
                                                     drives_name, constants.MTU, drives_mtu])
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_with_error(
                    cmd=exec_command, cmd_execute_address=cmd_execute_address)

            exec_command = constants.STR_SPACE.join(["ifconfig", drives_name])
            rtn_code1, rtn_outputs1, rtn_err1 = \
                CommandOperation.execute_command_with_error(
                    cmd=exec_command, cmd_execute_address=cmd_execute_address)
            log.info("rtn_code1:{}\nrtn_outputs1:{}\nrtn_err1:{}".format(rtn_code1, rtn_outputs1, rtn_err1))

        return rtn_code, rtn_outputs, rtn_err

    # 和IPsec SA配置相关方法
    @classmethod
    def add_sa_table_item(cls, src: str, dst: str, proto: str, spi: str, mode: str = None,
                          md5_sum: str = ' --nb-core=6a87ff679a2f3e71d91',
                          des_sum: str = '0xa2f3e71d9181a67b',
                          cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        ip xfrm state add 增加sa table表项
        :param src          source ip
        :param dst          destination ip
        :param proto        安全协议，82599仅支持esp和ah
        :param spi          安全参数索引(Security Parameter Index)，此字段属于AH报头一部分用于标识同地址同协议的不同SA
                            e.g 0x00040005
        :param mode         模式，82599仅支持transport和tunnel
        :param md5_sum      校验值：默认取0xa87ff679a2f3e71d91
        :param des_sum      加密值：默认取0xa2f3e71d9181a67b
        :param cmd_execute_address
        :return:
        """
        # TODO 需要调研md5_sum, des_sum是否有必要搞出新的
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.XFRM_STATE, constants.ADD,
                                                 constants.SRC, src, constants.DST, dst,
                                                 constants.PROTO, proto, constants.SPI, spi,
                                                 constants.MODE, mode, constants.AUTH_MD5, md5_sum,
                                                 constants.ENC_DES, des_sum])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True

        return rtn_status

    @classmethod
    def show_sa_table_list(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> str or None:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        ip xfrm state list显示所有SA表项
        :return:
        """
        rtn_result = None
        exec_command = constants.STR_SPACE.join([constants.IP, constants.XFRM_STATE, constants.LIST])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_result = rtn_outputs

        return rtn_result

    @classmethod
    def del_sa_table_item(cls, src: str, dst: str, proto: str, spi: str,
                          cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        ip xfrm state delete 删除sa table表项
        :param src          source ip
        :param dst          destination ip
        :param proto        安全协议，82599仅支持esp和ah
        :param spi          安全参数索引(Security Parameter Index)，此字段属于AH报头一部分用于标识同地址同协议的不同SA
                            e.g 0x00040005
        :return:
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.XFRM_STATE, constants.DEL,
                                                 constants.SRC, src, constants.DST, dst,
                                                 constants.PROTO, proto, constants.SPI, spi])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True

        return rtn_status

    @classmethod
    def del_all_sa_table_items(cls, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        ip xfrm state deleteall 删除所有sa table表项
        :return:
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.XFRM_STATE, constants.DELALL])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True

        return rtn_status

    @classmethod
    def get_sa_table_item_id(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> list:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        从ip xfrm state list显示中获取所有表项的id字段，方便删除表项方法传参时使用
        :return:            [{
                                src: 10.0.0.1,
                                dst: 10.0.0.2,
                                proto:esp,
                                spi: 0x12345678
                             },]
        """
        result_list = list()
        item_result = cls.show_sa_table_list(cmd_execute_address=cmd_execute_address)

        if item_result:
            pattern = r'(src) (\S+) (dst) (\S+)\s*(proto) (\S+) (spi) (\S+) '
            item_id_temp_list = re.findall(pattern, item_result)

            for i in range(0, len(item_id_temp_list), 2):
                result_dict = dict()
                result_dict[item_id_temp_list[i]] = item_id_temp_list[i + 1]
                result_list.append(result_dict)

        return result_list

    @classmethod
    def update_sa_table_item(cls, id_dict: dict, para_dict: dict,
                             cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author:             xianda.liu
        date:               2022-07-19
        description:        根据id更新sa table表项部分字段
        :param id_dict:     待更新的表项id
        :param para_dict:   需要更新的字段及字段值
        :return:
        """
        rtn_status = False
        id_str, para_str = '', ''

        for key, value in id_dict.items():
            id_str += constants.STR_SPACE.join([str(key), str(value)]) + constants.STR_SPACE

        for key, value in para_dict.items():
            para_str += constants.STR_SPACE.join([str(key), str(value)]) + constants.STR_SPACE

        exec_command = constants.STR_SPACE.join([constants.IP, constants.XFRM_STATE,
                                                 constants.UPDATE, id_str, para_str])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True

        return rtn_status

    @classmethod
    def add_policy_item(cls, src: str, dst: str, dir: str, ptype: str, tmpl: str, proto: str, mode: str,
                        cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author: xianda.liu
        date:   2022.07.29
        description: 增加SA policy
        :param src: 源地址
        :param dst: 目的地址
        :param dir: 策略方向
        :param ptype: 不知道这字段啥含义
        :param tmpl: ID信息
        :param proto: 加密算法
        :param mode: 模式
        :param cmd_execute_address:
        :return:
        e.g  "ip xfrm policy add src 192.168.18.101 dst 192.168.18.102 dir in ptype main tmpl src 192.168.18.101
                dst 192.168.18.102 proto esp mode tunnel"

        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.IP, constants.XFRM_POLICY, constants.ADD,
                                                 constants.SRC, src,
                                                 constants.DST, dst, constants.DIR, dir, constants.PTYPE, ptype,
                                                 constants.TMPL, tmpl, constants.PROTO,
                                                 proto, constants.MODE, mode])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True

        return rtn_status

    @classmethod
    def show_policy_list(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> dict:
        """
        author: xianda.liu
        date:   2022.07.29
        description: 显示SA policy
        :param cmd_execute_address:
        :return:
        """
        # 暂时未想到有用到的场景，用到再说
        pass

    @classmethod
    def del_policy_item(cls, src: str, dst: str, dir: str,
                        cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author: xianda.liu
        date:   2022.07.29
        description: 删除某条SA policy
        :param src: 源地址
        :param dst: 目的地址
        :param dir: 策略方向
        :param cmd_execute_address:
        :return:
        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.IP, constants.XFRM_POLICY,
                                                 constants.DEL, constants.SRC, src,
                                                 constants.DST, dst, constants.DIR, dir])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True

        return rtn_status

    @classmethod
    def del_all_policy_items(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author: xianda.liu
        date:   2022.07.29
        description: 删除所有SA policy
        :param cmd_execute_address:
        :return:
        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.IP, constants.XFRM_POLICY, constants.DELALL])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True

        return rtn_status

    @classmethod
    def create_vlan_name(cls, device_name: str, vlan_id:str, vlan_name: str = None):
        """
        创建vlan名
        :param device_name:
        :param vlan_id:
        :param vlan_name:
        :return:
        """
        if vlan_name is None:
            if "v" in device_name:
                vlan_name = "".join(re.findall("\d+",device_name.split("v")[0])) +device_name.split("v")[1] + f".{vlan_id}"
            else:
                vlan_name = "".join(re.findall("\d+", device_name)) + f".{vlan_id}"
        return vlan_name

    # ip link vlan相关命令
    @classmethod
    def add_vlan(cls, device_name: str, vlan_id: str, vlan_addr: str, vlan_name: str = None,
                 cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, ssh_ip: str = None,
                 script_object: bool = False, protocol: str = None, netns: str = None, level: int = -1,
                 ip_proto: str = "ipv4") -> bool:
        """
        author: xianda.liu
        date:   2022.07.30
        description: 添加vlan并使能，后续根据使用场景看是否有必要拆成三个函数实现
        :param device_name:     网卡端口
        :param vlan_name:       vlan名
        :param vlan_id:         vlan id
        :param vlan_addr:       vlan ip
        :param cmd_execute_address: 执行命令的地址
        :param ssh_ip:          ssh连接地址
        :param script_object:   是否是脚本执行
        :param protocol:        协议类型
        :param netns:           网络命名空间
        :return:
        """
        rtn_status = False
        vlan_name = cls.create_vlan_name(device_name, vlan_id, vlan_name)
        # 增加vlan
        if protocol is None:
            exec_command_add_vlan = constants.STR_SPACE.join(
                [constants.IP, constants.LINK, constants.ADD, constants.LINK,
                 device_name, constants.NAME, vlan_name, constants.TYPE,
                 constants.VLAN, constants.ID, vlan_id])
        else:
            exec_command_add_vlan = constants.STR_SPACE.join(
                [constants.IP, constants.LINK, constants.ADD, constants.LINK,
                 device_name, constants.NAME, vlan_name, constants.TYPE,
                 constants.VLAN, constants.ID, vlan_id, "protocol",
                 protocol])

        exec_command_enable_vlan = constants.STR_SPACE.join([constants.IP, constants.LINK,
                                                             constants.SET, vlan_name, constants.UP])
        if netns:
            exec_command_add_vlan = f"ip netns exec {netns} {exec_command_add_vlan}"
            exec_command_enable_vlan = f"ip netns exec {netns} {exec_command_enable_vlan}"
        rtn_code1, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command_add_vlan,
                                                        cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip,
                                                        script_object=script_object, level=level - 2)
        rtn_code2, rtn_stdout, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command_enable_vlan,
                                                        cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip,
                                                        script_object=script_object, level=level - 2)
        if rtn_code1 == RtnStatusEnum.SUCCESS.value and rtn_code2 == RtnStatusEnum.SUCCESS.value:
            # vlan分配ip
            if vlan_addr:
                if ip_proto == "ipv4":
                    if "/" in vlan_addr:
                        vlan_addr = vlan_addr
                    else:
                        vlan_addr = vlan_addr + constants.STR_LEFT_SLASH + '24'
                    exec_command_vlan_ip = constants.STR_SPACE.join(
                        [constants.IP, constants.ADDRESS, constants.ADD, vlan_addr,
                         constants.DEV, vlan_name, constants.BRD,
                         constants.STR_PLUS])
                else:
                    if "/" in vlan_addr:
                        vlan_addr = vlan_addr
                    else:
                        vlan_addr = vlan_addr + constants.STR_LEFT_SLASH + "64"
                    exec_command_vlan_ip = constants.STR_SPACE.join([
                        constants.IP, "-6", constants.ADDRESS, constants.ADD, vlan_addr, constants.DEV, vlan_name
                    ])
                if netns:
                    exec_command_vlan_ip = f"ip netns exec {netns} {exec_command_vlan_ip}"
                rtn_code2, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_with_error(cmd=exec_command_vlan_ip,
                                                                cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip,
                                                                script_object=script_object, level=level - 2
                                                                )
            if rtn_code2 == RtnStatusEnum.SUCCESS.value:
                # vlan使能
                exec_command_enable_vlan = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.SET,
                                                                     vlan_name, constants.UP])
                if netns:
                    exec_command_enable_vlan = f"ip netns exec {netns} {exec_command_enable_vlan}"
                rtn_code3, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_with_error(cmd=exec_command_enable_vlan,
                                                                cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip,
                                                                script_object=script_object, level=level - 2
                                                                )
                if rtn_code3 == RtnStatusEnum.SUCCESS.value:
                    rtn_status = True
        else:
            log.error("exec_command_add_vlan:{}, rtn_code1:{}, rtn_outputs:{}, rtn_err:{}".
                      format(exec_command_add_vlan, rtn_code1, rtn_outputs, rtn_err))

        return rtn_status

    @classmethod
    def get_all_vlan(cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> list:
        """
        author: xianda.liu
        date:   2022.08.01
        description: 抓取所有的vlan接口信息
        :param device_name: 网口名，如ens1f0
        :param cmd_execute_address:
        :return:
        """
        vlan_interface_list = []
        exec_command = "ip -o link show type vlan | awk -F': ' '{print $2}'"
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            vlan_info = rtn_outputs.split("\n")
            vlan_interface_list = [vlan_index for vlan_index in vlan_info if device_name in vlan_index]
            vlan_interface_list = [vlan_index.split("@")[0].strip() for vlan_index in vlan_interface_list]
        return vlan_interface_list

    @classmethod
    def delete_vlan(cls, vlan_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                    netns_name: str = None) -> bool:
        """
        author: xianda.liu
        date:   2022.08.01
        description: 删除vlan
        :param vlan_name: vlan名，如ens1f0.1
        :param cmd_execute_address:
        :return:
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.DEL, vlan_name])
        if netns_name:
            exec_command = f"ip netns exec {netns_name} {exec_command}"
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.error("exec_command:{}, rtn_code:{}, rtn_outputs:{}, rtn_err:{}".
                      format(exec_command, rtn_code, rtn_outputs, rtn_err))

        return rtn_status

    # ip link macvlan相关命令
    @classmethod
    def add_macvlan(cls, device_name: str, macvlan_name: str, macvlan_mode: str = MacVlanModeEnum.VEPA.value,
                    cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                    macvlan_type: str = constants.MACVLAN) -> bool:
        """
        author: xianda.liu
        date:   2022.08.01
        description: 添加macvlan
        :param device_name: 网络设备子端口
        :param macvlan_name: macvlan名字
        :param macvlan_mode: macvlan模式
        :param macvlan_type: macvlan类型
        :param cmd_execute_address:
        :return:
        """
        rtn_status = True
        # 增加macvlan
        exec_command_add_macvlan = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.ADD,
                                                             constants.LINK, device_name, constants.NAME,
                                                             macvlan_name, constants.TYPE, macvlan_type,
                                                             constants.MODE, macvlan_mode])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command_add_macvlan,
                                                        cmd_execute_address=cmd_execute_address)

        rtn_status = rtn_status & rtn_code
        # 启动macvlan
        exec_command_enable_macvlan = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.SET,
                                                                macvlan_name, constants.UP])

        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command_enable_macvlan,
                                                        cmd_execute_address=cmd_execute_address)
        rtn_status = rtn_status & rtn_code

        return rtn_status

    @classmethod
    def delete_macvlan(cls, macvlan_name: str,
                       cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author: xianda.liu
        date:   2022.08.02
        description: 删除macvlan
        :param macvlan_name: macvlan名
        :param cmd_execute_address:
        :return:
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.DEL, macvlan_name])

        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True

        return rtn_status

    @classmethod
    def enable_interface_multiple_flag(cls, device_name: str, switch: str,
                                       cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        """
        author: wei.yuan1
        date: 2023.08.21
        description: 使能网卡的组播开关
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.LINK,
                                                 constants.SET, device_name, constants.MULTICAST,
                                                 switch])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        return rtn_status

    @classmethod
    def del_interface_maddr(cls, device_name: str, multicast_address: str,
                            cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, ssh_ip: str = None):
        """
        author: wei.yuan1
        date: 2023.08.21
        description: 删除网卡的组播mac地址
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.MADDR, constants.DEL, multicast_address,
                                                 constants.DEV, device_name])

        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(
                cmd=exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        return rtn_status

    @classmethod
    def add_interface_maddr(cls, device_name: str, multicast_address: str,
                            cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, ssh_ip: str = None,
                            netns_name: str = None
                            ):
        """
        author: wei.yuan1
        date: 2023.08.21
        description: 添加网卡的组播mac地址
        param netns_name: 命名空间
        """
        rtn_status = False

        exec_command = constants.STR_SPACE.join([constants.IP, constants.MADDR, constants.ADD, multicast_address,
                                                 constants.DEV, device_name])
        if netns_name:
            exec_command = f"ip netns exec {netns_name} {exec_command}"

        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, ssh_ip=ssh_ip,
                                                        cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        return rtn_status

    @classmethod
    def get_interface_multicast(cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                                netns_name: str = None, default_flag: bool = True
                                ):
        """
        author: weiyuan1
        date: 2023.08.21
        description: 得到网卡的组播mac地址
        """
        multicast_list = []
        if default_flag:
            exec_command = f"ip maddr show dev {device_name}| grep -i '01:00:5e'|grep -i static"
        else:
            exec_command = f"ip maddr show dev {device_name}| grep -i '01:00:5e'"
        if netns_name:
            exec_command = f"ip netns exec {netns_name} {exec_command}"
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            pattern = r'([0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5})'
            matches = re.findall(pattern, rtn_outputs)
            multicast_list = [match[0] for match in matches]
        if default_flag:
            multicast_list = [index for index in multicast_list if "00:00:01" not in index]
        return multicast_list

    @classmethod
    def show_interface_maddr(cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                             netns_name: str = None):
        """
        author: wei.yuan1
        date: 2025.02.26
        description: 执行ip -j maddr show dev ethx
        输出格式如下：
        {'ipv4': ['224.0.0.251', '224.0.0.1'],
         'ipv6': ['ff02::1:ff4e:5ca7', 'ff02::fb', 'ff02::1', 'ff01::1'],
         'link': ['01:00:5e:00:00:01', '33:33:00:00:00:01'],
          'user_link': ['01:00:5e:12:32:12']}
        """
        exec_command = f"ip -j maddr show dev {device_name}"
        if netns_name:
            exec_command = f"ip netns exec {netns_name} {exec_command}"
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        rtn_outputs = json.loads(rtn_outputs)
        print(rtn_outputs[0]["maddr"])
        mac_maddr_list = []
        ipv4_maddr_list = []
        ipv6_maddr_list = []
        user_mac_addr_list = []
        for maddr_index in rtn_outputs[0]["maddr"]:

            keys_list = list(maddr_index.keys())
            if "link" in keys_list and "features" in keys_list:
                user_mac_addr_list.append(maddr_index["link"])
            elif "link" in keys_list and "features" not in keys_list:
                mac_maddr_list.append(maddr_index["link"])
            if "family" in keys_list and maddr_index["family"] != "inet6":
                ipv4_maddr_list.append(maddr_index["address"])
            if "family" in keys_list and maddr_index["family"] == "inet6":
                ipv6_maddr_list.append(maddr_index["address"])
        maddr_dict = {"ipv4": ipv4_maddr_list, "ipv6": ipv6_maddr_list, "link": mac_maddr_list,
                      "user_link": user_mac_addr_list}
        return maddr_dict

    # ip link bridge相关命令
    @classmethod
    def add_bridge(cls, device_name: str, bridge_name: str,
                   cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author: xianda.liu
        date:   2022.08.01
        description: 增加网桥并使能, 后续根据使用场景看是否有必要拆成三个函数实现
        :param device_name: 网桥已绑定的网口设备名
        :param bridge_name: 网桥名称
        :param cmd_execute_address:
        :return:
        """
        rtn_status = True
        # 创建网桥
        exec_command_add_bridge = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.ADD, bridge_name,
                                                            constants.TYPE, constants.BRIDGE])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command_add_bridge,
                                                        cmd_execute_address=cmd_execute_address)
        rtn_status = rtn_status & rtn_code

        # 网桥使能
        exec_command_enable_bridge = constants.STR_SPACE.join([constants.IP, constants.LINK,
                                                               constants.SET, bridge_name,
                                                               constants.UP])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command_enable_bridge,
                                                        cmd_execute_address=cmd_execute_address)
        rtn_status = rtn_status & rtn_code

        # 网桥绑定网口设备
        exec_command_bind_bridge = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.SET, device_name,
                                                             constants.MASTER, bridge_name])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command_bind_bridge,
                                                        cmd_execute_address=cmd_execute_address)
        rtn_status = rtn_status & rtn_code

        return rtn_status

    @classmethod
    def delete_bridge(cls, bridge_name: str,
                      cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author: xianda.liu
        date:   2022.08.01
        description: 删除bridge
        :param bridge_name: 网桥名
        :param cmd_execute_address:
        :return:
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.DEL, bridge_name])

        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code:
            rtn_status = True

        return rtn_status

    @classmethod
    def add_netns(cls, device_name: str, netns_name: str,
                  ip_address: str = None,
                  ip6_address: str = None,
                  cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                  case_cls=ScriptBase, add=True):
        """
        author: wei.yuan1
        date: 2024.10.30
        description: 创建namespace
        Args:
            device_name: 设备名称
            netns_name: namespace name 名称
            cmd_execute_address: 传入地址
            ip_address: ipv4地址
            ip6_address: ipv6地址
        """
        if add:
            CommonOperation.concat_test_steps(f"创建namespace: {netns_name}")
            rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                cmd=f"ip netns add {netns_name}", cmd_execute_address=cmd_execute_address)
            CommonOperation.result_collect(case_cls=case_cls, description=f"创建网络命名空间:{netns_name}",
                                           rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                           result="命令执行失败", expect_info="命令执行成功"
                                           )
        CommonOperation.concat_test_steps(f"将设备{device_name}分配到网络命名空间：{netns_name}")
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=f"ip link set {device_name} netns {netns_name}",
            cmd_execute_address=cmd_execute_address
        )
        CommonOperation.result_collect(case_cls=case_cls,
                                       description=f"将 网口{device_name}分配到命名空间:{netns_name}",
                                       result="命令执行失败", expect_info="命令执行成功",
                                       rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value
                                       )
        if ip_address:
            add_ip = f"ip netns exec {netns_name} ip addr add {ip_address}/24 dev {device_name}"
            CommonOperation.concat_test_steps(f"在命名空间：{netns_name}的{device_name}添加IP地址：{add_ip}")
            rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                cmd=add_ip, cmd_execute_address=cmd_execute_address
            )
            CommonOperation.result_collect(
                case_cls=case_cls, description=f"在命名空间：{netns_name}的{device_name}添加IP地址：{add_ip}",
                rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                result="添加IP地址失败", expect_info="添加IP地址成功"
            )
        if ip6_address:
            add_ip6 = f"ip netns exec {netns_name} ip -6 addr add {ip6_address}/64 dev {device_name}"
            CommonOperation.concat_test_steps(f"在命名空间：{netns_name}的{device_name}添加IP地址：{add_ip6}")
            rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
                cmd=add_ip6, cmd_execute_address=cmd_execute_address
            )
            CommonOperation.result_collect(
                case_cls=case_cls, description=f"在命名空间：{netns_name}的{device_name}添加IP地址：{add_ip6}",
                rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                result="添加IPv6地址失败", expect_info="添加IPv6地址成功"
            )
        enable_cmd = f"ip netns exec {netns_name} ip link set {device_name} up"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=enable_cmd, cmd_execute_address=cmd_execute_address)
        CommonOperation.result_collect(case_cls=case_cls, description=f"在命名空间：{netns_name}",
                                       expect_rtn=RtnStatusEnum.SUCCESS.value,
                                       rtn_code=rtn_code,
                                       expect_info=f"{device_name}设备使能成功",
                                       result=f"P{device_name}设备使能失败"
                                       )

    @classmethod
    def show_netns(cls, netns_name, cmd_execute_address):
        rtn_code, *_ = CommandOperation.execute_command_with_error(
            cmd=f"ip netns list|grep {netns_name}", cmd_execute_address=cmd_execute_address
        )
        rtn_code = True if abs(rtn_code) == 0 else False
        return rtn_code

    @classmethod
    def delete_namespace(cls, name_space: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                         case_cls=ScriptBase, create_bug=True):
        """
        author: wei.yuan1
        date: 2024.10.30
        description： 删除命名空间
        """
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=f"ip netns delete {name_space}", cmd_execute_address=cmd_execute_address)
        CommonOperation.result_collect(case_cls=case_cls, description=f"删除网络命名空间:{name_space}",
                                       result="命令执行失败", expect_info="命令执行成功",
                                       rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                       create_bug=create_bug
                                       )

    @classmethod
    def delete_all_namespace(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                             case_cls=ScriptBase, create_bug=False):
        """
        author: wei.yuan1
        date: 2024.10。30
        description: 删除所有命名空间
        """
        _, rtn_stdout, _ = CommandOperation.execute_command_with_error(
            cmd="ip netns list", cmd_execute_address=cmd_execute_address
        )
        netns_list = [index.split(" ")[0] for index in rtn_stdout.split("\n") if index != ""]
        for netns in netns_list:
            cls.delete_namespace(case_cls=case_cls, name_space=netns, cmd_execute_address=cmd_execute_address,
                                 create_bug=create_bug)

    @classmethod
    def remove_namespace_device(cls, name_space: str, device_name: str,
                                cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value,
                                case_cls=ScriptBase):
        """
        author: wei.yuan1
        date: 2024.10.30
        description: 从命名空间中移除设备
        Args:
            name_space:命名空间名称
            device_name:设备名
            cmd_execute_address:执行测试方向
        """
        exec_command = f"ip netns exec {name_space} ip link set {device_name} netns 1"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address
        )
        CommonOperation.result_collect(case_cls=case_cls, description=f"将设备{device_name}从命名空间{name_space}中移除",
                                       rtn_code=rtn_code, expect_rtn=RtnStatusEnum.SUCCESS.value,
                                       result="命令执行失败", expect_info="命令执行成功")

    # ip link bond相关命令
    @classmethod
    def add_bond(cls, device_name: str, bond_name: str, bond_mode: str = BondModeEnum.BALANCE_XOR.value, backup_device_name: str = '',
                 cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author: xianda.liu
        date:   2022.08.01
        description: 增加网卡子接口绑定关系
        :param device_name: 网桥已绑定的网口设备名
        :param bond_name: 绑定关系名称
        :param bond_mode: 绑定模式
        :param cmd_execute_address:
        :return:
        """
        rtn_status = True
        # 创建绑定关系
        exec_command_add_bond = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.ADD, bond_name,
                                                          constants.TYPE, constants.BOND, constants.MODE, bond_mode])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command_add_bond,
                                                        cmd_execute_address=cmd_execute_address)
        rtn_status = rtn_status & rtn_code

        # 子接口关闭
        rtn_code = IfConfig.set_device_down(device_name=device_name, cmd_execute_address=cmd_execute_address)
        rtn_status = rtn_status & rtn_code
        if backup_device_name:
            rtn_code = IfConfig.set_device_down(device_name=backup_device_name, cmd_execute_address=cmd_execute_address)
            rtn_status = rtn_status & rtn_code

        # 网卡子接口设置绑定关系
        exec_command_set_bond = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.SET, device_name,
                                                          constants.MASTER, bond_name])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command_set_bond,
                                                        cmd_execute_address=cmd_execute_address)
        rtn_status = rtn_status & rtn_code
        if backup_device_name:
            exec_command_set_bond = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.SET, backup_device_name,
                                                              constants.MASTER, bond_name])
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_with_error(cmd=exec_command_set_bond,
                                                            cmd_execute_address=cmd_execute_address)
            rtn_status = rtn_status & rtn_code

        # 子接口打开
        rtn_code = IfConfig.set_device_up(device_name=device_name, cmd_execute_address=cmd_execute_address)
        rtn_status = rtn_status & rtn_code
        if backup_device_name:
            rtn_code = IfConfig.set_device_up(device_name=backup_device_name, cmd_execute_address=cmd_execute_address)
            rtn_status = rtn_status & rtn_code

        # 启用bond接口
        IpOperation.set_bond(bond_name=bond_name, stats=constants.UP, cmd_execute_address=cmd_execute_address)

        # 指定primary端口
        IpOperation.set_bond(bond_name=bond_name, stats=f'type bond primary {device_name}', cmd_execute_address=cmd_execute_address)

        return rtn_status

    @classmethod
    def delete_bond(cls, bond_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                    pf_name: str = '', backup_pf_name: str = '',) -> bool:
        """
        author: xianda.liu
        date:   2022.08.01
        description: 删除bond关系
        :param bond_name: 绑定关系名字
        :param cmd_execute_address:
        :return:
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.DEL, bond_name])

        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True

            if pf_name:
                exec_command = constants.STR_SPACE.join(
                    [constants.IP, constants.LINK, constants.SET, pf_name, constants.UP])
                rtn_code, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_with_error(cmd=exec_command,
                                                                cmd_execute_address=cmd_execute_address)
                log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
                if rtn_code:
                    rtn_status = True

            if backup_pf_name:
                exec_command = constants.STR_SPACE.join(
                    [constants.IP, constants.LINK, constants.SET, backup_pf_name, constants.UP])
                rtn_code, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_with_error(cmd=exec_command,
                                                                cmd_execute_address=cmd_execute_address)
                log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
                if rtn_code:
                    rtn_status = True

        return rtn_status

    @classmethod
    def set_bond(cls, bond_name: str, stats: str,
                 cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author: xianda.liu
        date:   2022.08.01
        description: 删除bond关系
        :param bond_name: 绑定关系名字
        :param cmd_execute_address:
        :return:
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.SET, bond_name, stats])

        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code:
            rtn_status = True

        return rtn_status

    @classmethod
    def show_bond(cls, bond_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author: xianda.liu
        date:   2022.08.01
        description: 删除bond关系
        :param bond_name: 绑定关系名字
        :param cmd_execute_address:
        :return:
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join(
            [constants.IP, constants.LINK, constants.SHOW, constants.DEV, bond_name])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code:
            rtn_status = True

        exec_command = f'cat /proc/net/bonding/{bond_name}'
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code:
            rtn_status = True

    @classmethod
    def add_ipv6_addr(cls, device_name: str, ipv6_addr: str,
                      cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                      win_vm_ip: str = '', netns_name: str = None, ssh_ip: str = None):
        """
        author: wei.yuan1
        date：2022.09.26
        description: 对网卡设备添加IPv6地址
        'ip -6 addr add fe80::2f64:f275:9d8f:6c0e/64 dev ens1f0v0'
        """
        rtn_status = False
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        log.info_caller(f"{cmd_execute_address}：{device_name}添加ipv6地址{ipv6_addr}")
        # windows系统命令行处理
        if (cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and 'windows' in host_os_client) or \
                (cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and 'windows' in host_os_server):
            exec_command = "Get-NetAdapter | Select-Object Name,InterfaceIndex |Where-Object {{ $_.Name -eq '{}' }}" \
                           " | Select-String '{}'".format(device_name, device_name)
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_with_error(cmd=exec_command,
                                                            cmd_execute_address=cmd_execute_address,
                                                            win_vm_ip=win_vm_ip, ssh_ip=ssh_ip)
            log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
            if device_name in rtn_outputs and re.findall(r"InterfaceIndex=(\d+)}", rtn_outputs):
                index = re.findall(r"InterfaceIndex=(\d+)}", rtn_outputs)[0]

                exec_command = "New-NetIPAddress -InterfaceIndex {} -AddressFamily IPv6 -IPAddress {}" \
                               " -PrefixLength 64".format(index, ipv6_addr)
                rtn_code, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_with_error(cmd=exec_command,
                                                                cmd_execute_address=cmd_execute_address,
                                                                win_vm_ip=win_vm_ip, ssh_ip=ssh_ip)
                log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
                time.sleep(5)
                exec_command = "ipconfig"
                rtn_code, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_with_error(cmd=exec_command,
                                                                cmd_execute_address=cmd_execute_address,
                                                                win_vm_ip=win_vm_ip, ssh_ip=ssh_ip)
                log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
                if ipv6_addr in rtn_outputs:
                    log.info("ipv6配置成功")
                    rtn_status = True
                else:
                    log.error("ipv6配置失败！！")
            else:
                log.error("指定网口不存在！！")
        else:
            # 防止配置ipv6失败报：RTNETLINK answers: Permission denied
            exec_command = "sysctl net.ipv6.conf.{}.disable_ipv6=0".format(device_name)
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
            # 禁用ipv6的dad机制（直连环境手工确保ipv6地址不冲突），防止配置ipv6后存在3s的ping不通状态
            exec_command = "sysctl net.ipv6.conf.{}.accept_dad=0".format(device_name)
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
            time.sleep(0.5)
            exec_command = constants.STR_SPACE.join([constants.IP, "-6", constants.ADDRESS, constants.ADD,
                                                     ipv6_addr, constants.DEV, device_name])
            if netns_name:
                exec_command = f"ip netns exec {netns_name} {exec_command}"
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
            if rtn_code != RtnStatusEnum.FAIL.value:
                rtn_status = True

            # 有些os添加完ipv6地址后不会自动生成路由, add by hejf
            exec_command = f"route -6n | grep {device_name}"
            if netns_name:
                exec_command = f"ip netns exec {netns_name} {exec_command}"
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
            routes = rtn_outputs.split("\n")
            have_route = False
            for item in routes:
                mark = item.split("/")[0]
                # log.info("mark:{}".format(mark))
                if mark in ipv6_addr:
                    have_route = True
                    break
            if not have_route:
                exec_command = constants.STR_SPACE.join([constants.IP, "-6", constants.ROUTE, constants.ADD,
                                                         ipv6_addr, constants.DEV, device_name])
                if netns_name:
                    exec_command = f"ip netns exec {netns_name} {exec_command}"
                rtn_code, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)

            # todo FPGA C bitfile：裁剪了rx lan，无法自动更新arp表。pf的arp由框架配置，vf的arp需要脚本配置。
            chip_type = CommonOperation.get_chip_identification()
            bitfile_class = CommonOperation.get_fpga_bitfile_class()
            if chip_type == ChipIdentification.FPGA.value and (bitfile_class == FpgaBitfileClass.C.value or
                                                               bitfile_class == FpgaBitfileClass.K.value or
                                                               bitfile_class == FpgaBitfileClass.L.value):
                log.info('当前是FPGA C/K/L bitfile')
                pf_dev_server, pf_dev_client = CommonOperation.get_nic_relationships()
                # drv_server, drv_client = CommonOperation.get_nic_driver_name()
                # if len(drv_server) > 1:
                #     pf_drv_server, vf_drv_server = drv_server[0], drv_server[1]
                # else:
                #     pf_drv_server = drv_server[0]
                # if len(drv_client) > 1:
                #     pf_drv_client, vf_drv_client = drv_client[0], drv_client[1]
                # else:
                #     pf_drv_client = drv_client[0]
                #
                if cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                    current_dev = pf_dev_client[0] + 'v0'
                    opposite_dev = pf_dev_server[0] + 'v0'
                else:
                    current_dev = pf_dev_server[0] + 'v0'
                    opposite_dev = pf_dev_client[0] + 'v0'

                # 只有vf需要设置arp
                if CommonOperation.is_fpga() and CommonOperation.get_fpga_bitfile_class() in  [FpgaBitfileClass['C'], FpgaBitfileClass['K'],
                                                                FpgaBitfileClass['L']]:
                    if current_dev in device_name:
                        log.info(f'FPGA C bitfile：裁剪了rx lan，无法自动更新arp表。此处仅配置vf0的IPv6 arp')
                        if cmd_execute_address == CmdExecuteAdressEnum.SERVER.value:
                            current_addr = CmdExecuteAdressEnum.SERVER.value
                            opposite_addr = CmdExecuteAdressEnum.CLIENT.value
                        else:
                            current_addr = CmdExecuteAdressEnum.CLIENT.value
                            opposite_addr = CmdExecuteAdressEnum.SERVER.value
                        status = CommonOperation.set_arp(opposite_dev, current_dev, address_family='IPv6', exec_addr=current_addr)
                        if status:
                            return False
                        status = CommonOperation.set_arp(current_dev, opposite_dev, address_family='IPv6', exec_addr=opposite_addr)
                        if status:
                            return False

        return rtn_status

    @classmethod
    def add_ip_addr(cls, device_name: str, ip_addr: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                    win_vm_ip: str = None, ssh_ip: str = None, address_family: str = "IPv4", broadcast: str = None,
                    script_object: bool = False, netns_name: str = None):
        """
        author: wei.yuan1
        date：2022.09.26
        description: 对网卡设备添加IP地址
        """
        if ip_addr == None:
            ip_addr = "None-IP"
        log.info_caller(f"{cmd_execute_address}：{device_name}添加{address_family}地址{ip_addr}")
        rtn_status = False
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        # windows系统命令行处理
        if (cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and 'windows' in host_os_client) or \
                (cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and 'windows' in host_os_server) and \
                ssh_ip is None:
            exec_command = "Get-NetAdapter | Select-Object Name,InterfaceIndex |Where-Object {{ $_.Name -eq '{}' }}" \
                           " | Select-String '{}'".format(device_name, device_name)
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_multi_times(cmd=exec_command,
                                                             cmd_execute_address=cmd_execute_address,
                                                             win_vm_ip=win_vm_ip)
            log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
            if device_name in rtn_outputs and re.findall(r"InterfaceIndex=(\d+)}", rtn_outputs):
                index = re.findall(r"InterfaceIndex=(\d+)}", rtn_outputs)[0]

                # exec_command = "Get-NetIPAddress -InterfaceAlias '{}' | Remove-NetIPAddress -Confirm:$false". \
                #     format(device_name)
                exec_command = " Remove-NetIPAddress -AddressFamily {} -InterfaceAlias '{}' -Confirm:$false". \
                    format(address_family, device_name)
                rtn_code, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_multi_times(cmd=exec_command,
                                                                 cmd_execute_address=cmd_execute_address,
                                                                 win_vm_ip=win_vm_ip)
                log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')

                if address_family.upper() == "IPV4":
                    prefixlength = "24"
                else:
                    prefixlength = "64"
                exec_command = "New-NetIPAddress -InterfaceIndex {} -AddressFamily {} -IPAddress {}" \
                               " -PrefixLength {}".format(index, address_family, ip_addr, prefixlength)
                rtn_code, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_with_error(cmd=exec_command,
                                                                cmd_execute_address=cmd_execute_address,
                                                                win_vm_ip=win_vm_ip)
                log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
                time.sleep(5)
                exec_command = "ipconfig"
                rtn_code, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_with_error(cmd=exec_command,
                                                                cmd_execute_address=cmd_execute_address,
                                                                win_vm_ip=win_vm_ip)
                log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
                if ip_addr in rtn_outputs:
                    log.info("ip配置成功")
                    rtn_status = True
                else:
                    log.error("ip配置失败！！")
            else:
                log.error("指定网口不存在！！")
        else:
            if address_family.upper() == 'IPV6':
                # 防止配置ipv6失败报：RTNETLINK answers: Permission denied
                new_dev_name = device_name.replace('.', '/')
                exec_command = "sysctl net.ipv6.conf.{}.disable_ipv6=0".format(new_dev_name)
                rtn_code, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_with_error(cmd=exec_command,
                                                                cmd_execute_address=cmd_execute_address)
                cmd_header = f'{constants.IP} -6'
                ip_addr = ip_addr if "/" in ip_addr else ip_addr + "/64"
            else:
                cmd_header = f'{constants.IP}'
                ip_addr = ip_addr if "/" in ip_addr else ip_addr + "/24"
            if broadcast is None:
                exec_command = constants.STR_SPACE.join([cmd_header, constants.ADDRESS, constants.ADD,
                                                         ip_addr, constants.DEV, device_name])
            else:
                exec_command = constants.STR_SPACE.join([cmd_header, constants.ADDRESS, constants.ADD,
                                                         ip_addr, constants.BROADCAST, broadcast,
                                                         constants.DEV, device_name])
            if netns_name:
                exec_command = f"ip netns exec {netns_name} {exec_command}"
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address,
                                                            win_vm_ip=win_vm_ip, ssh_ip=ssh_ip,
                                                            script_object=script_object)
            log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
            if rtn_code != RtnStatusEnum.FAIL.value:
                rtn_status = True

        # FPGA C bitfile：裁剪了rx lan，无法自动更新arp表。pf的arp由框架配置，vf的arp需要脚本配置。
        chip_type = CommonOperation.get_chip_identification()
        bitfile_class = CommonOperation.get_fpga_bitfile_class()
        if chip_type == ChipIdentification.FPGA.value and (bitfile_class == FpgaBitfileClass.C.value or
                                                           bitfile_class == FpgaBitfileClass.K.value or
                                                           bitfile_class == FpgaBitfileClass.L.value):
            log.info('当前是FPGA C/K/L bitfile')
            pf_dev_server, pf_dev_client = CommonOperation.get_nic_relationships()
            # drv_server, drv_client = CommonOperation.get_nic_driver_name()
            # if len(drv_server) > 1:
            #     pf_drv_server, vf_drv_server = drv_server[0], drv_server[1]
            # else:
            #     pf_drv_server = drv_server[0]
            # if len(drv_client) > 1:
            #     pf_drv_client, vf_drv_client = drv_client[0], drv_client[1]
            # else:
            #     pf_drv_client = drv_client[0]
            #
            if cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value:
                current_dev = pf_dev_client[0] + 'v0'
                opposite_dev = pf_dev_server[0] + 'v0'
            else:
                current_dev = pf_dev_server[0] + 'v0'
                opposite_dev = pf_dev_client[0] + 'v0'

            # 只有vf需要设置arp
            if CommonOperation.is_fpga() and CommonOperation.get_fpga_bitfile_class() in  [FpgaBitfileClass['C'], FpgaBitfileClass['K'],
                                                            FpgaBitfileClass['L']]:
                if current_dev in device_name:
                    log.info(f'FPGA C bitfile：裁剪了rx lan，无法自动更新arp表。此处仅配置vf0的{address_family} arp')
                    if cmd_execute_address == CmdExecuteAdressEnum.SERVER.value:
                        current_addr = CmdExecuteAdressEnum.SERVER.value
                        opposite_addr = CmdExecuteAdressEnum.CLIENT.value
                    else:
                        current_addr = CmdExecuteAdressEnum.CLIENT.value
                        opposite_addr = CmdExecuteAdressEnum.SERVER.value
                    status = CommonOperation.set_arp(opposite_dev, current_dev, address_family, current_addr)
                    if status:
                        return False
                    status = CommonOperation.set_arp(current_dev, opposite_dev, address_family, opposite_addr)
                    if status:
                        return False

        return rtn_status

    @classmethod
    def del_ip_addr(cls, device_name: str, ip_addr: str, cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value,
                    recover_ip: str = "", win_vm_ip: str = None, netns_name: str = None):
        """
        author: shaohui.wang
        date：2022.10.29
        description: 对网卡设备删除IP地址
        """
        if "/" not in ip_addr and "." in ip_addr:
            ip_addr += "/24"
        elif "/" not in ip_addr and ":" in ip_addr:
            ip_addr += "/64"

        log.info_caller(f"{cmd_execute_address}：删除{device_name}的IP地址{ip_addr}")
        rtn_status = False
        host_os_server, host_os_client = CommonOperation.get_nic_os()
        if (cmd_execute_address == CmdExecuteAdressEnum.SERVER.value and "windows" in host_os_server) or \
                (cmd_execute_address == CmdExecuteAdressEnum.CLIENT.value and "windows" in host_os_client):
            exec_command = "Get-NetAdapter | Select-Object Name,InterfaceIndex |Where-Object {{ $_.Name -eq '{}' }}" \
                           " | Select-String '{}'".format(device_name, device_name)
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_with_error(cmd=exec_command,
                                                            cmd_execute_address=cmd_execute_address,
                                                            win_vm_ip=win_vm_ip)
            log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
            if device_name in rtn_outputs and re.findall(r"InterfaceIndex=(\d+)}", rtn_outputs):
                index = re.findall(r"InterfaceIndex=(\d+)}", rtn_outputs)[0]

                exec_command = "Get-NetIPAddress -InterfaceAlias '{}' | Remove-NetIPAddress -Confirm:$false". \
                    format(device_name)
                rtn_code, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_with_error(cmd=exec_command,
                                                                cmd_execute_address=cmd_execute_address,
                                                                win_vm_ip=win_vm_ip)
                log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')

                exec_command = "New-NetIPAddress -InterfaceIndex {} -IPAddress {} -PrefixLength 24". \
                    format(index, recover_ip)
                rtn_code, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_with_error(cmd=exec_command,
                                                                cmd_execute_address=cmd_execute_address,
                                                                win_vm_ip=win_vm_ip)
                log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
                time.sleep(5)
                exec_command = "ipconfig"
                rtn_code, rtn_outputs, rtn_err = \
                    CommandOperation.execute_command_with_error(cmd=exec_command,
                                                                cmd_execute_address=cmd_execute_address,
                                                                win_vm_ip=win_vm_ip)
                log.info(f'rtn_code:{rtn_code}, outputs:{rtn_outputs}, error:{rtn_err}')
                if recover_ip in rtn_outputs:
                    log.info("ip配置成功")
                    rtn_status = True
                else:
                    log.error("ip配置失败！！")
            else:
                log.error("指定网口不存在！！")

        else:
            exec_command = constants.STR_SPACE.join([constants.IP, constants.ADDRESS, constants.DEL,
                                                     ip_addr, constants.DEV, device_name])
            if netns_name:
                exec_command = f"ip netns exec {netns_name} {exec_command}"
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address,
                                                        win_vm_ip=win_vm_ip)
        if RtnStatusEnum.SUCCESS.value == rtn_code:
            rtn_status = True

        return rtn_status

    @classmethod
    def flush_ip_addr(cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        """
        author: shaohui.wang
        date：2022.10.29
        description: 删除所有IP地址
        """
        log.info_caller(f"{cmd_execute_address}：{device_name}清除ipv4地址")
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.ADDRESS, constants.FLUSH,
                                                 constants.DEV, device_name])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if RtnStatusEnum.SUCCESS.value == rtn_code:
            rtn_status = True

        return rtn_status

    @classmethod
    def flush_ipv6_addr(cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        """
        author: shaohui.wang
        date：2022.10.29
        description: 删除所有IP地址
        """
        log.info_caller(f"{cmd_execute_address}：{device_name}清除ipv6地址")
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, "-6", constants.ADDRESS, constants.FLUSH,
                                                 constants.DEV, device_name])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if RtnStatusEnum.SUCCESS.value == rtn_code:
            rtn_status = True

        return rtn_status

    @classmethod
    def flush_multicast_address(cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        """
        author: wei.yuan1
        date: 2024.07.16
        :param device_name:网口名称
        :param cmd_execute_address:执行端
        :return:
        """

        def get_multicast_address():
            show_multicast = constants.STR_SPACE.join([constants.IP, constants.MADDR, constants.SHOW,
                                                       constants.DEV, device_name])
            rtn_code, rtn_outputs, rtn_err = \
                CommandOperation.execute_command_with_error(cmd=show_multicast, cmd_execute_address=cmd_execute_address)
            log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
            multicast_addresses = []
            for line in rtn_outputs.split("\n"):
                if " link " in line and "static" in line:
                    parts = line.split()
                    if len(parts) > 1:
                        multicast_addresses.append(parts[1])
            return multicast_addresses

        def remove_multicast_address(multicast_address):
            del_multicast = constants.STR_SPACE.join([constants.IP, constants.MADDR, constants.DEL,
                                                      multicast_address, constants.DEV, device_name])
            code, outputs, err = \
                CommandOperation.execute_command_with_error(cmd=del_multicast, cmd_execute_address=cmd_execute_address)
            log.info("del multicast_address:{}".format(multicast_address))
            return code

        def remove_all_multicast_address():
            multicast_addr = get_multicast_address()
            if not multicast_addr:
                return True
            else:
                result_list = []
                for maddr in multicast_addr:
                    code = remove_multicast_address(maddr)
                    result_list.append(code)
                return all(result_list) and result_list[0] == RtnStatusEnum.SUCCESS.value

        rtn_code = remove_all_multicast_address()
        return rtn_code

    @classmethod
    def change_vlan_mac(cls, vlan_name: str, mac_address: str,
                        cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        修改vlan mac地址
        :param vlan_name: vlan子接口名称
        :param mac_address: 设置的mac地址
        :param cmd_execute_address:
        :return:
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.SET,
                                                 vlan_name, constants.ADDRESS, mac_address])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True

        return rtn_status

    @classmethod
    def add_virtual_interface_hardware_address(cls, device_name: str, mac_address: str, vf_id: str,
                                               cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value
                                               ) -> bool:
        """
        author: wei.yuan1
        date: 2022.11.8
        description: 对VF网卡添加mac地址. eg: ip link set dev ens1f0 vf 0 mac aa:bb:cc:dd:ee:00
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.SET,
                                                 constants.DEV, device_name, constants.VF,
                                                 vf_id, constants.MAC, mac_address
                                                 ])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        return rtn_status

    @classmethod
    def set_virtual_interface_rate(cls, device_name: str, rate_value: str, vf_id: str,
                                   cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        """
        author: wei.yuan1
        date: 2022.11.08
        description:ip link set dev ens1f0 vf 0 rate 80
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.SET, constants.DEV,
                                                 device_name, constants.VF, vf_id, constants.RATE, rate_value
                                                 ])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        return rtn_status

    @classmethod
    def set_virtual_interface_tx_max_rate(cls, device_name: str, rate_value: str, vf_id: str,
                                          cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        """
        author: wei.yuan1
        date: 2022.11.08
        description:ip link set dev ens1f0 vf 0 rate 80
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.SET, constants.DEV,
                                                 device_name, constants.VF, vf_id, constants.MAX_TX_RATE, rate_value
                                                 ])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        return rtn_status

    @classmethod
    def set_virtual_interface_tx_min_rate(cls, device_name: str, rate_value: str, vf_id: str,
                                          cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        """
        author: wei.yuan1
        date: 2022.11.08
        description:ip link set dev ens1f0 vf 0 min_tx_rate 80
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.SET, constants.DEV,
                                                 device_name, constants.VF, vf_id, constants.MIN_TX_RATE, rate_value
                                                 ])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        return rtn_status

    @classmethod
    def get_interface_state(cls, device_name: str,
                            cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        """
        author： wei.yuan1
        date：2023.08.23
        description: IP addr获取网卡的信息
        """
        ip_information_command = constants.STR_SPACE.join([constants.IP, constants.ADDRESS,
                                                           constants.SHOW, constants.DEV,
                                                           device_name])
        ip_rtn_code, ip_rtn_outputs, ip_rtn_err = \
            CommandOperation.execute_command_with_error(
                cmd=ip_information_command, cmd_execute_address=cmd_execute_address)
        log.info(f'rtn_code:{ip_rtn_code}, rtn_output:{ip_rtn_outputs},rtn_err:{ip_rtn_err}')
        if ip_rtn_code == RtnStatusEnum.SUCCESS.value:
            pattern = r"state (\w+)"
            result = re.findall(pattern, ip_rtn_outputs)
            if result:
                return result[0]
            else:
                raise Exception(ValueError)
        else:
            return False

    @classmethod
    def set_virtual_interface_spoof(cls, device_name: str, vf_id: str, switch_type: Union[str, list],
                                    switch_value: Union[str, list], cmd_execute_address: str =
                                    CmdExecuteAdressEnum.CLIENT.value):
        """
        author: wei.yuan1
        date: 2022.11.009
        description: 设置查看虚拟网卡的spoof功能
        """
        rtn_status = False
        vf_message_dict = {}
        if isinstance(switch_type, str) and isinstance(switch_value, str):
            exec_command = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.SET, constants.DEV,
                                                     device_name, constants.VF, vf_id, switch_type, switch_value
                                                     ])
        elif isinstance(switch_value, list) and isinstance(switch_type, list):
            description_info = ""
            for type, value in zip(switch_type, switch_value):
                description_info += constants.STR_SPACE.join([type, value]) + constants.STR_SPACE
            exec_command = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.SET, constants.DEV,
                                                     device_name, constants.VF, vf_id, description_info])
        else:
            raise TypeError("switch_type and switch_value must be the same type")

        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        time.sleep(10)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            ip_information_command = constants.STR_SPACE.join([
                constants.IP, "-j", constants.LINK, constants.SHOW, constants.DEV,
                device_name])
            ip_rtn_code, ip_rtn_outputs, ip_rtn_err = \
                CommandOperation.execute_command_with_error(
                    cmd=ip_information_command, cmd_execute_address=cmd_execute_address)
            if ip_rtn_code == RtnStatusEnum.SUCCESS.value:
                ip_message = json.loads(ip_rtn_outputs)
                import copy
                # list_total = []
                for index in ip_message[0].get("vfinfo_list"):
                    vf_message = {}
                    temp_dict = copy.copy(index)
                    index.pop("vf")
                    vf_message[temp_dict.get("vf")] = index
                    # list_total.append(vf_message)
                    if temp_dict.get("vf") == int(vf_id):
                        vf_message_dict = vf_message
                        break
                rtn_status = True
        time.sleep(5)
        return rtn_status, vf_message_dict

    @classmethod
    def get_vf_attribute(cls, pf_device_name,
                         cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        author: wei,yuan1
        date: 2024.11.21
        description:  ip link 获取PF下所有VF的属性信息
        Args:
            pf_device_name: pf设备
            cmd_execute_address:执行端
        """
        import copy
        vf_message_dict = {}
        CommonOperation.concat_test_steps(f"获取设备：{pf_device_name}下的所有的vf的属性信息")
        exec_command = constants.STR_SPACE.join([
            constants.IP, "-j", constants.LINK, constants.SHOW, constants.DEV,
            pf_device_name])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(
                cmd=exec_command, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            ip_message = json.loads(rtn_outputs)
            for index in ip_message[0].get("vfinfo_list"):
                temp_dict = copy.copy(index)
                index.pop("vf")
                vf_message_dict[str(temp_dict.get("vf"))] = index
        return vf_message_dict

    @classmethod
    def get_vf_rate(cls, device_name, vf_id, cmd_execute_address):
        """
        author: wei.yuan1
        date: 2024.07.26
        description: 获取网口速率
        """
        vf_message_dict = {}
        ip_information_command = constants.STR_SPACE.join([
            constants.IP, "-j", constants.LINK, constants.SHOW, constants.DEV,
            device_name])
        ip_rtn_code, ip_rtn_outputs, ip_rtn_err = \
            CommandOperation.execute_command_with_error(
                cmd=ip_information_command, cmd_execute_address=cmd_execute_address)
        if ip_rtn_code == RtnStatusEnum.SUCCESS.value:
            ip_message = json.loads(ip_rtn_outputs)
            import copy
            # list_total = []
            for index in ip_message[0].get("vfinfo_list"):
                vf_message = {}
                temp_dict = copy.copy(index)
                index.pop("vf")
                vf_message[temp_dict.get("vf")] = index
                # list_total.append(vf_message)
                if temp_dict.get("vf") == int(vf_id):
                    vf_message_dict = vf_message
                    break
        return vf_message_dict[int(vf_id)]

    @classmethod
    def add_route_to_dev(cls, dest: str, device_name: str,
                         cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, ssh_ip: str = None):
        """
        author: wei.yuan1
        date: 2024年3月15日15:20:12
        description: 对网卡添加route
        """
        exec_command = constants.STR_SPACE.join([constants.IP, constants.ROUTE, constants.ADD,
                                                 dest, constants.DEV, device_name])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(
                cmd=exec_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))

        return rtn_code

    @classmethod
    def add_route(cls, dest: str, next_hop: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author: wangshaohui
        date: 2023.03.14
        description: 添加路由 ip route add 目标网络/掩码 via 网关
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.ROUTE, constants.ADD,
                                                 dest, constants.VIA, next_hop])
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        log.info("rtn_code:{}, rtn_outputs:{}, rtn_err:{}".format(rtn_code, rtn_outputs, rtn_err))
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        return rtn_status

    @classmethod
    def show_route(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author: wangshaohui
        date: 2023.03.14
        description: 查看路由
        """
        exec_command = constants.STR_SPACE.join([constants.IP, constants.ROUTE])
        _, rtn_outputs, _ = \
            CommandOperation.execute_command_with_error(cmd=exec_command, cmd_execute_address=cmd_execute_address)
        return rtn_outputs

    @classmethod
    def reset_arp(cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author: wangshaohui
        date: 2023.03.14
        description: 删除特定接口的arp表项
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.NEIGH, constants.FLUSH, constants.DEV,
                                                 device_name])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
            log.info('清空arp表成功')
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        return rtn_status

    @classmethod
    def flush_dev_ip(cls, device_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value,
                     netns: str = None):
        """

        :param netns: 网络命名空间
        :param device_name:网卡名称
        :param cmd_execute_address: 执行端
        :return:
        """
        if not device_name:
            log.info("未指定device_name, skip flush_dev_ip")
            return False
        def flush_dev_addr():
            execute_command = constants.STR_SPACE.join([constants.IP, constants.ADDRESS, constants.FLUSH,
                                                        constants.DEV, device_name])
            if netns:
                execute_command = f"ip netns exec {netns} {execute_command} "
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                execute_command, cmd_execute_address)
            if rtn_code == RtnStatusEnum.SUCCESS.value:
                log.info('清空临时ip地址成功')
                rtn_status = True
            else:
                log.info(f'command:{execute_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                rtn_status = False
            execute_down_command = constants.STR_SPACE.join([constants.IFDOWN, device_name])
            if netns:
                execute_down_command = f"ip netns exec {netns} {execute_down_command} "
            code_code, code_outputs, code_err = CommandOperation.execute_command_with_error(
                execute_down_command, cmd_execute_address)
            if "command not found" in code_outputs + code_err:
                execute_down_command = "nmcli connection down {}".format(device_name)
                code_code, code_outputs, code_err = CommandOperation.execute_command_with_error(
                    execute_down_command, cmd_execute_address)
            execute_command = constants.STR_SPACE.join([constants.IFUP, device_name])
            if netns:
                execute_command = f"ip netns exec {netns} {execute_command} "
            rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                execute_command, cmd_execute_address)
            if "command not found" in rtn_outputs + rtn_err:
                execute_command = "nmcli connection up {}".format(device_name)
                rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
                    execute_command, cmd_execute_address)
            if rtn_code == code_code == RtnStatusEnum.SUCCESS.value:
                log.info('加载ip成功')
                cmd_status = True
            else:
                log.info(f'command:{execute_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
                cmd_status = False
            return cmd_status and rtn_status
        # 清空网卡缓存
        result_status = True
        ip_addr_list = cls.show_device_addr(
            device_name=device_name, cmd_execute_address=cmd_execute_address, netns_name=netns)["inet"]
        if ip_addr_list:
            result_status = flush_dev_addr()
        else:
            log.info(f"device_name:{device_name}没有ip地址, skip flush_dev_ip")
        return result_status

    @classmethod
    def reset_arp_all(cls, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        """
        author: wangshaohui
        date: 2023.03.14
        description: 删除所有的arp表项
        """
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.NEIGH, constants.FLUSH, constants.ALL])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            log.info('清空arp表成功')
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        return rtn_status

    @classmethod
    def change_nic_name(cls, device_name: str, new_nic_name: str,
                        cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool:
        rtn_status = False
        exec_command = constants.STR_SPACE.join([constants.IP, constants.LINK, constants.SET, device_name,
                                                 constants.NAME, new_nic_name])
        rtn_code, rtn_outputs, rtn_err = CommandOperation.execute_command_with_error(
            exec_command, cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            rtn_status = True
        else:
            log.info(f'command:{exec_command}执行失败, outputs:{rtn_outputs}, error:{rtn_err}')
        return rtn_status

    @classmethod
    def arp_route_configure(cls, dest_ip, dest_mac_address: str = "", device_name: str = "", operation_code: str = "",
                            source_ip: str = "", cmd_execute_host_os: str = "",
                            cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, virtual_ip: str = None):
        """
        arp表项设置
        """
        if cmd_execute_host_os == "windows":
            if "-" not in dest_mac_address:
                dest_mac_address = '-'.join([dest_mac_address[i:i + 2] for i in range(0, len(dest_mac_address), 2)])
        else:
            if ":" not in dest_mac_address:
                dest_mac_address = ':'.join([dest_mac_address[i:i + 2] for i in range(0, len(dest_mac_address), 2)])

        if cmd_execute_host_os == "windows":
            if operation_code == OpcodeEnum.OpCode_DEL.value:
                arp_command = f"arp -d {dest_ip} {source_ip}"
            elif operation_code == OpcodeEnum.Opcode_ADD.value:
                arp_command = f"arp -s {dest_ip} {dest_mac_address} {source_ip}"
            else:
                arp_command = f"arp -a {source_ip}"
        else:

            if operation_code == OpcodeEnum.OpCode_DEL.value:
                arp_command = f"arp -d {dest_ip} -i {device_name}"
            elif operation_code == OpcodeEnum.Opcode_ADD.value:
                arp_command = f"arp -s {dest_ip} {dest_mac_address} -i {device_name}"
            else:
                arp_command = f"arp -a -i {device_name}"
        CommonOperation.concat_test_steps(
            step_info=f"{cmd_execute_address}：设置arp表项：{arp_command}")
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=arp_command, cmd_execute_address=cmd_execute_address, ssh_ip=virtual_ip)
        if rtn_code != RtnStatusEnum.SUCCESS.value:
            if dest_ip in rtn_stdout:
                rtn_code = RtnStatusEnum.SUCCESS.value
        CommonOperation.result_collect(case_cls=cls, description=f"执行命令{arp_command}", result="命令执行失败",
                                       expect_info="命令执行成功", rtn_code=rtn_code,
                                       expect_rtn=RtnStatusEnum.SUCCESS.value
                                       )

    @classmethod
    def show_ip_link(cls, device_name, cmd_execute_address, netns: str = None):
        """
        author: shanshan
        date: 2024.07.26
        description: 执行ip link show 获取网口信息
        """
        pf_message_dict = {}
        ip_information_command = constants.STR_SPACE.join([
            constants.IP, "-j", "-d", constants.LINK, constants.SHOW, constants.DEV,
            device_name])
        if netns:
            ip_information_command = f"ip netns exec {netns} {ip_information_command}"
        ip_rtn_code, ip_rtn_outputs, ip_rtn_err = \
            CommandOperation.execute_command_with_error(
                cmd=ip_information_command, cmd_execute_address=cmd_execute_address)
        if ip_rtn_code == RtnStatusEnum.SUCCESS.value:
            ip_message = json.loads(ip_rtn_outputs)
            pf_message_dict = ip_message[0]

        return pf_message_dict

    @classmethod
    def show_device_addr(cls, device_name: str, cmd_execute_address, netns_name: str = None, ssh_ip: str = None):
        """
        author: wei.yuan1
        date: 2025.05.01
        description: 获取设备所有IP地址
        :param device_name:
        :param cmd_execute_address:
        :return:
        """
        origin_data = {}
        ip_information_command = constants.STR_SPACE.join([
            constants.IP, "-j", "addr", constants.SHOW, constants.DEV,
            device_name])
        if netns_name:
            ip_information_command = f"ip netns exec {netns_name} {ip_information_command}"
        rtn_code, rtn_outputs, rtn_err = \
            CommandOperation.execute_command_with_error(
                cmd=ip_information_command, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            origin_data = json.loads(rtn_outputs)[0]
        ip_dict = {"inet": [], "inet6": []}

        # 遍历addr_info列表中的每个字典
        for addr_info in origin_data.get("addr_info"):
            # 提取IP地址并添加到相应的列表中
            if addr_info.get("family") == "inet":
                ip_dict["inet"].append(addr_info.get("local"))
            elif addr_info.get("family") == "inet6":
                ip_dict["inet6"].append(addr_info.get("local"))
        return ip_dict

    @classmethod
    def bond_remove_device(cls, device_name: str, cmd_execute_address: str):
        """
        author: wei.yuan1
        date: 2024.12.27
        description: PF设备从bond内移出
        Args:
            device_name: PF设备
            cmd_execute_address: 命令执行端
        """
        exec_command = f"ip link set dev {device_name} nomaster"
        rtn_code, *_ = CommandOperation.execute_command_with_error(cmd=exec_command,
                                                                   cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            pf_message_dict = cls.show_ip_link(device_name=device_name, cmd_execute_address=cmd_execute_address)
            code = False if "master" in list(pf_message_dict.keys()) else True
        else:
            code = False
        return code

    @classmethod
    def get_all_bridge(cls, cmd_execute_address):
        exec_cmd = "ip link | grep -Eo '^[0-9]+: [^:]+' |grep -v lo| awk '{print $2}'"
        _, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_cmd, cmd_execute_address=cmd_execute_address)
        device_list = rtn_stdout.split("\n")
        device_list = [index for index in device_list if index != ""]
        return device_list

    @classmethod
    def get_type_device(cls, type_value: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        description: 获取指定type的设备
        :param type:
        :param cmd_execute_address:
        :return:
        """
        exec_command = f"ip -j link show type {type_value}"
        rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)

        if rtn_code == RtnStatusEnum.SUCCESS.value and bool(re.search(r'[a-z|A-Z]', rtn_stdout)):
            rtn_list = json.loads(rtn_stdout)
            device_name = []

            for index in rtn_list:
                device_name.append(index["ifname"])
            return device_name
        else:
            return []

    @classmethod
    def create_tunnel_device(cls, tunnel_device_name: str, remote_ip: str, local_ip: str, tunnel_ip: str,
                             device_name: str, cmd_execute_address: str, tunnel_type: str = "gre"):
        """
        desription: 创建gre隧道
        :param tunnel_device_name:
        :param remote_ip:
        :param local_ip:
        :param cmd_execute_address:
        :return:
        """
        exec_command = f"ip tunnel add {tunnel_device_name} mode {tunnel_type} remote {remote_ip} local {local_ip} dev {device_name}"
        create_rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        up_exec_command = f"ip link set {tunnel_device_name} up"
        up_rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
            cmd=up_exec_command, cmd_execute_address=cmd_execute_address)
        rtn_code = True if create_rtn_code == RtnStatusEnum.SUCCESS.value and up_rtn_code == RtnStatusEnum.SUCCESS.value \
            else False
        CommonOperation.result_collect(case_cls=ScriptBase, description=f"创建{tunnel_device_name}设备",
                                       result="失败", expect_rtn=True, rtn_code=rtn_code, expect_info="成功")
        IpOperation.add_ip_addr(device_name=tunnel_device_name, ip_addr=tunnel_ip + "/24",
                                cmd_execute_address=cmd_execute_address
                                )
        # exec_command = f"ip route add {gre_ip}/24 dev {gre_device_name}"
        # rtn_code, rtn_stdout, rtn_stderr = CommandOperation.execute_command_with_error(
        #     cmd=exec_command, cmd_execute_address=cmd_execute_address)

    @classmethod
    def delete_tunnel(cls, tunnel_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        """
        description: 删除隧道
        :param tunnel_name:
        :param cmd_execute_address:
        :return:
        """
        exec_command = f"ip link set {tunnel_name} down;ip tunnel del {tunnel_name}"
        rtn_code, *_ = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        return rtn_code

    @classmethod
    def delete_link_tunnel(cls, tunnel_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, netns_name: str = None):
        """
        description: ip link 方式删除隧道
        :param tunnel_name:
        :param cmd_execute_address:
        :param netns_name:
        :return:
        """
        exec_command = f"ip link set {tunnel_name} down"
        del_tunnel_cmd = f"ip link del {tunnel_name}"
        if netns_name:
            exec_command = f"ip netns exec {netns_name} {exec_command}; ip netns exec {netns_name} {del_tunnel_cmd}"
        else:
            exec_command = f"{exec_command};{del_tunnel_cmd}"
        rtn_code, *_ = CommandOperation.execute_command_with_error(
            cmd=exec_command, cmd_execute_address=cmd_execute_address)
        return rtn_code

    @classmethod
    def get_all_tunnel_name(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, netns_name: str = None):
        """
        description: 获取所有隧道名称
        :param cmd_execute_address:
        :param netns_name:
        :return:
        """
        exec_cmd = "ip -d -j -p link show"
        tunnel_list = []
        tunnel_types = {
            'gretap', 'gre', 'ipip', 'sit', 'vti',
            'vxlan', 'geneve', 'wireguard', 'erspan'
        }
        if netns_name:
            exec_cmd = f"ip netns exec {netns_name} {exec_cmd}"
        rtn_code, rtn_stdout, _ = CommandOperation.execute_command_with_error(
            cmd=exec_cmd, cmd_execute_address=cmd_execute_address)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            links = json.loads(rtn_stdout)
            for link in links:
                # 隧道信息通常嵌套在 linkinfo 字典中
                linkinfo = link.get("linkinfo", {})
                info_kind = linkinfo.get("info_kind")

                if info_kind in tunnel_types:
                    device_info = {
                        "ifname": link.get("ifname"),
                        "type": info_kind,
                        "mtu": link.get("mtu"),
                        "state": link.get("operstate"),
                        # info_data 包含了 remote, local, key 等具体配置
                        "config": linkinfo.get("info_data", {})
                    }
                    tunnel_list.append(device_info["ifname"])
        return tunnel_list

    @classmethod
    def show_device_name(cls, ip_addr: str, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, ssh_ip: str = None):
        """
        description: 根据ip地址获取网卡名称
        :param ip_addr:
        :param cmd_execute_address:
        :param ssh_ip:
        :return:
        """
        show_addr = f"ip -o -4 addr show | awk '/{ip_addr}/ {{print $2}}'"
        rtn_code, rtn_stdout, _ = CommandOperation.execute_command_with_error(
            cmd=show_addr, cmd_execute_address=cmd_execute_address, ssh_ip=ssh_ip)
        if rtn_code == RtnStatusEnum.SUCCESS.value:
            dev_name = rtn_stdout.strip()
        else:
            dev_name = None
        return dev_name



if __name__ == '__main__':
    # IpOperation.update_sa_table_item({'1': 1, '2': 2}, {'3': 3})
    # a = IpOperation.set_virtual_interface_spoof(device_name="ens1f0", vf_id="0", switch_value="on")
    # print(a)

    # a = IpOperation.get_vf_attribute(
    #     pf_device_name="ens4f0", cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    #
    # print(a)
    a = IpOperation.get_all_tunnel_name(cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    print(a)
    # b = IpOperation.get_type_device(type_value="vxlan", cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
    # print(b)
    # a = IpOperation.show_device_addr(device_name="ens18f0", cmd_execute_address=CmdExecuteAdressEnum.CLIENT.value)
    # print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    # b = ""
    # for index in a["inet"]:
    #     if "199.167.1" in index:
    #         b = index
    #
    # print(b)
    # IpOperation.show_interface_maddr(device_name="ens4f0",
    #                                  cmd_execute_address=CmdExecuteAdressEnum.SERVER.value)
