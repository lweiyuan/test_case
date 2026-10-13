import re
import time, copy 
import add_syspath
import json, ipaddress, random
from scripts.script_libs import log
from scripts.script_libs.ifconfig import IfConfig
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.rdma_core_tool import RdmacoreTool
from scripts.script_libs.ip_operation import IpOperation
from scripts.script_libs.iperf_operation import IperfOperation, Iperf2Operation
from scripts.script_libs.pcie_pcituils import LspciOperation, SetpciOperation
from scripts.script_libs.pcie_operation import LinkChangeOpeation, LinkCheckOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.nvmecli import NvmeOperation
from scripts.script_libs.fio_operation import FioOperation
from scripts.script_libs.script_base import SxeThread
from scripts.script_libs.windows_hyperv_manage_vm import KvmOp
from scripts.script_libs.enums import CmdExecuteAdressEnum, TestPacketType, FilterTypeEnum, TransportProtocal, \
    RtnStatusEnum, TestPmdForwadModeEnum, TestObjectType, NicNameEnum
from enum import Enum, unique
from scripts.script_libs.enums import RtnStatusEnum, CmdExecuteAdressEnum, BondModeEnum, RdmaMode

@unique
class GidType(Enum):
    """
    自定义函数指定返回状态，0为成功，-1为失败
    """
    DEFAULT = 'default'
    IPV4 = 'ipv4'
    IPV6 = 'ipv6'


class rdma_link_info():
    
    def __init__(self):
        self.link = None
        self.state = None
        self.physical_state = None
        self.netdev = None

class ib_portinfo():
    
    def __init__(self):
        self.state = None
        self.max_mtu = None
        self.active_mtu = None
        self.sm_lid = None
        self.port_lid = None
        self.port_lmc = None
        self.link_layer = None
        self.max_msg_sz = None
        self.port_cap_flags = None
        self.port_cap_flags2 = None
        self.max_vl_num = None
        self.bad_pkey_cntr = None
        self.qkey_viol_cntr = None
        self.sm_sl = None
        self.pkey_tbl_len = None
        self.gid_tbl_len = None
        self.subnet_timeout = None
        self.init_type_reply = None
        self.active_width = None
        self.active_speed = None
        self.phys_state = None

class ib_devinfo():
    
    def __init__(self):
        self.hca_id = None
        self.transport = None
        self.fw_ver = None
        self.node_guid = None
        self.sys_image_guid = None
        self.vendor_id = None
        self.vendor_part_id = None
        self.hw_ver = None
        self.phys_port_cnt = None
        self.max_mr_size = None
        self.page_size_cap = None
        self.max_qp = None
        self.max_qp_wr = None
        self.device_cap_flags = None
        self.max_sge = None
        self.max_sge_rd = None
        self.max_cq = None
        self.max_cqe = None
        self.max_mr = None
        self.max_pd = None
        self.max_qp_rd_atom = None
        self.max_ee_rd_atom = None
        self.max_res_rd_atom = None
        self.max_qp_init_rd_atom = None
        self.max_ee_init_rd_atom = None
        self.atomic_cap = None
        self.max_ee = None
        self.max_rdd = None
        self.max_mw = None
        self.max_raw_ipv6_qp = None
        self.max_raw_ethy_qp = None
        self.max_mcast_grp = None
        self.max_mcast_qp_attach = None
        self.max_total_mcast_qp_attach = None
        self.max_ah = None
        self.max_fmr = None
        self.max_srq = None
        self.max_srq_wr = None
        self.max_srq_sge = None
        self.max_pkeys = None
        self.local_ca_ack_delay = None
        self.general_odp_caps = None
        self.rc_odp_caps = None
        self.uc_odp_caps = None
        self.ud_odp_caps = None
        self.xrc_odp_caps = None
        self.completion_timestamp_mask = None
        self.hca_core_clock = None
        self.device_cap_flags_ex = None
        self.tso_caps = None
        self.rss_caps = None
        self.max_wq_type_rq = None
        self.packet_pacing_caps = None
        self.cq_moderation_caps = None
        self.num_comp_vectors = None
        self.port_info: ib_portinfo= None #默认只有一个
    

class Env(CommandOperation, IpOperation, CommonOperation, NvmeOperation, FioOperation, IfConfig, RdmacoreTool,
          LspciOperation, SetpciOperation, LinkCheckOperation, LinkChangeOpeation, IperfOperation, Iperf2Operation,
          KvmOp):
    
    @classmethod
    def add_bond_interface(cls, bond_name, bond_mode, *netdev, **kwargs):
        ipaddress = kwargs.get("ipaddress", None)
        cmd_execute_address = kwargs.get("cmd_execute_address", CmdExecuteAdressEnum.SERVER.value)
        command = f"ip link add {bond_name} type bond mode {bond_mode} miimon 100"
        if  bond_mode == BondModeEnum.BALANCE_XOR.value:
            command += " xmit_hash_policy layer2"
        elif bond_mode == BondModeEnum.AD_8023.value:
            command += " lacp_rate slow"
        cmd_code, cmd_output, cmd_stderr = Env.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        if cmd_stderr:
            return cmd_code, cmd_output, cmd_stderr
        cmd_code, cmd_output, cmd_stderr = Env.execute_command_based_paramiko_with_rtncode(f"ip link set {bond_name} type bond mode {bond_mode}", 
                                                                                           cmd_execute_address)
        if cmd_stderr:
            return cmd_code, cmd_output, cmd_stderr
        
        for dev in netdev:
            cmd_list = [f"ip link set {dev} down",
                        f"ip link set {dev} master {bond_name}",
                        f"ip link set {dev} up",]
            for cmd in cmd_list:
                cmd_code, cmd_output, cmd_stderr = Env.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
                if cmd_stderr:
                    return cmd_code, cmd_output, cmd_stderr
        if ipaddress != None:
            command = f"ifconfig {bond_name} {ipaddress}"
            cmd_code, cmd_output, cmd_stderr = Env.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
            if cmd_stderr:
                return cmd_code, cmd_output, cmd_stderr
        Env.execute_command(f"ifconfig {bond_name} up", cmd_execute_address)
        return bond_name
    
    @classmethod
    def get_same_numa_cpu_string(cls, master_numa, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value) :
        numa_node_path = f"/sys/devices/system/node/node{master_numa}/cpulist"
        cmd_code, cmd_output, cmd_stderr = Env.execute_command_based_paramiko_with_rtncode(f"cat {numa_node_path}",
                                                                                           cmd_execute_address)
        if cmd_code == RtnStatusEnum.FAIL.value:
            return None
        return cmd_output

    @classmethod
    def get_cross_num_cpu_string(cls, master_numa, cmd_execute_address=CmdExecuteAdressEnum.SERVER.value) :
        numa_node_path = f"/sys/devices/system/node/"
        cmd_code, cmd_output, cmd_stderr = Env.execute_command_based_paramiko_with_rtncode(f"ls {numa_node_path}",
                                                                                           cmd_execute_address)
        if cmd_code == RtnStatusEnum.FAIL.value:
            return None
        node_list = re.findall(r"(node\d+)", cmd_output)
        node_list.remove(f"node{master_numa}")
        chosen_numa = random.choice(node_list)
        numa_node_path = f"/sys/devices/system/node/{chosen_numa}/cpulist"
        cmd_code, cmd_output, cmd_stderr = Env.execute_command_based_paramiko_with_rtncode(f"cat {numa_node_path}",
                                                                                           cmd_execute_address)
        if cmd_code == RtnStatusEnum.FAIL.value:
            return None
        return cmd_output

    @classmethod
    def random_available_ipv4_address(cls, prefix="", num: int = 2) -> list:
        """
        生成同一网段内的多个随机IPv4地址
        
        参数:
            prefix (str): IPv4网络前缀，默认为私有地址(192.168.0.0/24)
            num (int): 需要生成的地址数量，默认为2
            
        返回:
            list: 包含随机IPv4地址字符串的列表
        """
        # 设置默认前缀为私有地址(192.168.0.0/24)
        prefix = "192.168.0.0/24" if prefix == "" else prefix
        
        # 解析网络前缀
        network = ipaddress.IPv4Network(prefix, strict=False)
        network_addr = network.network_address
        prefix_len = network.prefixlen
        
        # 计算主机部分的位数
        host_bits = 32 - prefix_len
        
        # 生成num个随机地址
        addresses = set()
        while len(addresses) < num:
            # 生成随机的主机部分
            host_part = random.getrandbits(host_bits)
            # 组合成完整地址
            ip = network_addr + host_part
            # 确保不是网络地址或广播地址
            if ip != network.network_address and ip != network.broadcast_address:
                addresses.add(str(ip))
        
        return list(addresses)
    
    @classmethod
    def random_available_ipv6_address(cls, prefix="", num: int = 2) -> list:
        """
        生成同一网段内的多个随机IPv6地址，只在最后16位（最后一段）内变化
        
        参数:
            prefix (str): IPv6网络前缀，默认为ULA地址(fd00::/64)
            num (int): 需要生成的地址数量，默认为2
            
        返回:
            list: 包含随机IPv6地址字符串的列表
        """
        # 设置默认前缀为ULA地址(fd00::/64)
        prefix = "fd00::/64" if prefix == "" else prefix
        
        # 解析网络前缀
        network = ipaddress.IPv6Network(prefix, strict=False)
        network_addr = network.network_address
        prefix_len = network.prefixlen
        
        # 确保前缀长度至少是112位（这样最后16位是主机部分）
        if prefix_len > 112:
            raise ValueError("Prefix length must be 112 or less to allow variation in the last 16 bits")
        
        # 生成num个随机地址
        addresses = set()
        while len(addresses) < num:
            # 生成随机的最后16位（0-65535）
            last_part = random.randint(0, 65535)
            
            # 获取网络部分（前112位）
            network_part = int(network_addr) >> 16 << 16
            
            # 组合成完整地址（网络部分 + 随机最后16位）
            ip = network_part + last_part
            
            # 转换为IPv6Address对象
            ip_obj = ipaddress.IPv6Address(ip)
            
            # 确保不是网络地址或广播地址
            if ip_obj != network.network_address and ip_obj != network.broadcast_address:
                addresses.add(str(ip_obj))
        
        return list(addresses)


    # @classmethod
    # def assert_bug_problem(cls, key_word:str, description_word:str,
    #                        result_info: str = '', expect_info: str = '', *args, **kwargs):
    #     if result_info != expect_info:
    #         cls.create_bug_problem(cls, key_word, description_word, result_info, expect_info)

    @classmethod
    def assert_function_status(cls, func, expect:bool, *args, **kwargs):
        status, result = func(*args, **kwargs)
        if status != expect:
            Env.create_bug_problem(cls, func.__name__, result, status, expect)
        return status, result

    @classmethod
    def assert_function_result(cls, func, expect:bool, *args, **kwargs):
        status, result = func(*args, **kwargs)
        if result != expect:
            Env.create_bug_problem(cls, func.__name__, status, result, expect)
        return status, result

    @classmethod
    def assert_status(cls, func_result, expect:bool, *args, **kwargs):
        status, result = func_result
        description_word = kwargs.get('description_word', result)
        if status != expect:
            Env.create_bug_problem(cls, "", description_word, status, expect)
        return status, result

    @classmethod
    def assert_result(cls, func_result, expect:bool, *args, **kwargs):
        status, result = func_result
        if result != expect:
            Env.create_bug_problem(cls, "", status, result, expect)
        return status, result
    
    
    @classmethod
    def iperf3_interactive_commcheck(cls, server_ip, 
                              sever_cmd_address: str = CmdExecuteAdressEnum.SERVER.value,
                              client_cmd_address: str = CmdExecuteAdressEnum.CLIENT.value,
                              timeout=60,
                              *args, **kwargs) -> tuple:
        def server_iperf3(*args, **kwargs):
            command = f"timeout {timeout}s iperf3 -s -i 5 "
            for arg in args:
                command += f"--{arg} "
            for key, val in kwargs.items():
                command += f"--{key}={val} "            
            return cls.execute_command_based_paramiko_with_rtncode(command, sever_cmd_address)
                
        def client_iperf3(*args, **kwargs):
            command = f"iperf3 -c {server_ip} -i 5 "
            for arg in args:
                command += f"--{arg} "
            for key, val in kwargs.items():
                command += f"--{key}={val} "            
            return cls.execute_command_based_paramiko_with_rtncode(command, client_cmd_address)
                
        S = SxeThread(server_iperf3)
        C = SxeThread(client_iperf3)
        S.start() ; time.sleep(3) ; C.start()
        C.join() ; S.join()
        # cmd_code, cmd_output, cmd_stderr = C.join() ; cmd_code, cmd_output, cmd_stderr = S.join()
        return S.ret, C.ret
    
    
    @classmethod
    def clear_vf_device(cls, bdf:str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        command = f"echo 0 > /sys/bus/pci/devices/{bdf}/sriov_numvfs"
        return cls.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
    
    @classmethod
    def get_rdmadev_by_netport(cls, dev:str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        command = f"rdma link |grep {dev}"
        cmd_code, cmd_output, cmd_stderr = cls.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        Rdev_port = cmd_output.split()[1]
        Rdev, Rport = Rdev_port.split('/')[0], Rdev_port.split('/')[1]
        return Rdev, Rport

    @classmethod
    def get_rdmadev_by_ib_netport(cls, dev: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        command = f'ethtool -i {dev}'
        cmd_code, cmd_output, cmd_stderr = cls.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        res = re.findall(r'bus-info: (\w+:\w+:\w+\.\w+)', cmd_output)
        if res:
            bdf = res[0]
        else:
            return ""

        # 获取当前rdma mode
        rdma_mode = CommonOperation.get_rdma_mode(bdf, cmd_execute_address)

        if rdma_mode == RdmaMode.RoCE.value:
            cmd_command = f'rdma link'
            cmd_code, cmd_output, cmd_stderr = cls.execute_command_based_paramiko_with_rtncode(
                cmd_command, cmd_execute_address)
            if cmd_code != RtnStatusEnum.SUCCESS.value:
                log.error(f'command:{cmd_command}执行失败, outputs:{cmd_output}, error:{cmd_stderr}')
            rdma_device = re.findall(r'link\s*(\S+)/.*?{}\b'.format(dev), cmd_output)
            # rdma_device = cmd_output.split("/")[0].split()[1]
            rdma_device = rdma_device[0]
        else:
            cmd_command = f'ls /sys/bus/pci/devices/{bdf}/infiniband'
            cmd_code, cmd_output, cmd_stderr = cls.execute_command_based_paramiko_with_rtncode(
                cmd_command, cmd_execute_address)
            rdma_device = cmd_output
        # 获取port
        cmd_command = f'rdma link | grep {rdma_device}'
        cmd_code, cmd_output, cmd_stderr = cls.execute_command_based_paramiko_with_rtncode(
            cmd_command, cmd_execute_address)
        rdma_port = re.findall(r'/(\d+)', cmd_output)
        return rdma_device, rdma_port[0]

    @classmethod
    def get_rdmadev_by_mode_name(cls, dev: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        command = f'ethtool -i {dev}'
        cmd_code, cmd_output, cmd_stderr = cls.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        bdf = re.findall(r'bus-info: (\w+:\w+:\w+\.\w+)', cmd_output)
        # 获取当前rdma mode
        rdma_mode = CommonOperation.get_rdma_mode(bdf[0], cmd_execute_address)
        return rdma_mode
    
    
    @classmethod
    def get_upstream_bdf(cls, bdf:str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> str:
        command = f"find /sys/devices/pci* -name *{bdf}*"
        _, rtn_outputs, _ = cls.execute_command_with_error(command, cmd_execute_address)
        ret = re.split('/', rtn_outputs, 0, re.M)
        id = ret.index(f"{bdf}")
        log.info(ret[id - 1])
        return ret[id - 1]

    @classmethod
    def pci_path(cls, bdf: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> str:
        command = f"find /sys/devices/pci* -name *{bdf}*"
        _, rtn_outputs, _ = cls.execute_command_with_error(command, cmd_execute_address)
        return rtn_outputs
    
    @classmethod
    def add_dvlan(cls, device_name: str, vlan0_id: str, vlan1_id: str, vlan0_addr: str, vlan1_addr: str,
                    vlan0_name:str = None, vlan1_name:str = None, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value) -> bool :
        """
        author: lei.he
        date:   2025.04.09
        description: 为网络端口创建双层vlan
        :param device_name: 网口名，如ens1f0
        :param cmd_execute_address:
        :return:
        """
        if vlan0_name == None:
            vlan0_name = device_name + f"{vlan0_id}"
        rtn_code1 = cls.add_vlan(device_name, vlan0_id, vlan0_addr, vlan0_name,
                                                       cmd_execute_address)
        if vlan1_name == None:
            vlan1_name = vlan0_name + f"{vlan1_id}"
        rtn_code2 = cls.add_vlan(vlan0_name, vlan1_id, vlan1_addr, vlan1_name, protocol="802.1Q",
                                                       cmd_execute_address=cmd_execute_address)
        return True if rtn_code1 and rtn_code2 else False

    @classmethod
    def find_evidence_in_dmesg(cls, evidence_pattern:str, line_num: int = 10,
                               cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value, showinfo = True) -> tuple:
        """
        author: lei.he
        date:   2025.04.09
        description: 寻找dmesg内符合条件的信息
        :param evidence_pattern: 例如网口名，如ens1f0
        :param cmd_execute_address:
        :return: True, [...]/ false, None
        """
        cmd_code, cmd_output, cmd_stderr = cls.execute_command_with_error(f"dmesg | tail -n {line_num}", cmd_execute_address, print_enable=showinfo)
        if evidence_pattern != "all":
            res = re.findall(evidence_pattern, cmd_output)
            if res:
                log.info(f"dmesg: {res}")
                return True, res
            return False, None
        else:
            cmd_code, cmd_output, cmd_stderr = cls.execute_command_with_error(f"dmesg -c |tee -a /var/log/dmesg.old > /dev/null", cmd_execute_address, print_enable=showinfo)
            return True, cmd_output

    @classmethod
    def nmcli_add_ipv4(cls, dev:str, address:str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        command = f"nmcli connection add type ethernet con-name {dev} ifname {dev} ipv4.addresses {address}/24 ipv4.method manual"
        return cls.execute_command_based_paramiko_with_rtncode(
            command , cmd_execute_address)

    @classmethod
    def ib_status_down(cls, devace_name: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        command = f'ibportstate -D 0 1 -C {devace_name} disable'
        cls.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)

    @classmethod
    def ib_status_up(cls, devace_name: str, guid: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        command = f'ibportstate -D 0 1 -C {devace_name} enable -P 1'
        cls.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        # 开启opensm
        command = f'opensm -V -B -g {guid}'
        cls.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        # 开启opensm之后状态等一会才会变成Active
        time.sleep(2)

    @classmethod
    def kill_opensm(cls):
        command = "kill -9 `ps -ef | grep opensm | awk 'NR == 1{print $2}'`"
        cls.execute_command_based_paramiko_with_rtncode(command, CmdExecuteAdressEnum.CLIENT.value)
        cls.execute_command_based_paramiko_with_rtncode(command, CmdExecuteAdressEnum.SERVER.value)

    @classmethod
    def set_ib_mtu(cls, device_name: str, mtu: str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        command = f'ibportstate  -D 0 1 -C {device_name} mtu {mtu}'
        cls.execute_command_based_paramiko_with_rtncode(command, CmdExecuteAdressEnum.SERVER.value)

    @classmethod
    def ibv_devinfo_vvv(cls, dev:str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        command = f"ibv_devinfo -d {dev} -vvv"
        cmd_code, cmd_output, cmd_stderr = cls.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        data = cmd_output
        pattern = r"([a-zA-Z0-9_ ]+):\s*(.*)"
        matches = re.findall(pattern, data)
        ib_dev = ib_devinfo()
        for match in matches:
            field_name = match[0].strip().replace(" ", "_").lower()  # 将字段名转换为小写并用下划线替代空格
            if field_name not in ["rc_odp_caps", "uc_odp_caps", "ud_odp_caps", "xrc_odp_caps",
                                  "tso_caps", "rss_caps", "packet_pacing_caps", "cq_moderation_caps"]:
                field_value = match[1].strip()
                if hasattr(ib_dev, field_name):
                    setattr(ib_dev, field_name, field_value)
        port1 = ib_portinfo() #默认只有一个
        for port_info in re.split("port:", data)[1:]:
            matches = re.findall(pattern, data)
            for match in matches:
                field_name = match[0].strip().replace(" ", "_").lower()  # 将字段名转换为小写并用下划线替代空格
                field_value = match[1].strip()
                if hasattr(port1, field_name):
                    setattr(port1, field_name, field_value)
        ib_dev.port_info = port1
        # for key, value in vars(ib_dev).items():
        #     log.info(f"{key}: {value}")
        # for key, value in vars(port1).items():
        #     log.info(f"{key}: {value}")
        return ib_dev
    
    @classmethod
    def ethtool_i(cls, netdev:str, cmd_execute_address: str = CmdExecuteAdressEnum.CLIENT.value):
        command = f"ethtool -i {netdev}"
        cmd_code, cmd_output, cmd_stderr = cls.execute_command_based_paramiko_with_rtncode(command, cmd_execute_address)
        if cmd_code !=0:
            exit(-1)
        pattern = r"([a-zA-Z\-]+):\s*([^\n]+)"
        netdev_info = {}
        for lines in cmd_output.split('\n'):
            log.info(lines)
            matches = re.findall(pattern, lines)
            for match in matches:
                key, value = match
                netdev_info[key.strip()] = value.strip()
        log.info(netdev_info)
        return netdev_info

    def iperf_interactive_commcheck(cls, *args, **kwargs):
        command = ""

    @classmethod
    def get_cpu_model_name(cls, cmd_execute_address: CmdExecuteAdressEnum.SERVER.value):
        data = {}
        cmd_code, cmd_output, cmd_stderr = Env.execute_command_based_paramiko_with_rtncode("lscpu", cmd_execute_address)
        # if cmd_code == RtnStatusEnum.FAIL.value:
        #     return None
        data['Model name'] = re.search(r"Model name:\s+(.+)", cmd_output).group(1)
        data['Model name'] = data['Model name'].replace(" ", "_")
        data['Model name'] = data['Model name'].replace("(", "_")
        data['Model name'] = data['Model name'].replace(")", "_")
        log.info(data['Model name'])
        return data['Model name']

    @classmethod
    def get_nic_pf_name(cls, bdf, cmd_execute_address: CmdExecuteAdressEnum.SERVER.value):
        data = {}
        cmd_code, cmd_output, cmd_stderr = Env.execute_command_with_error(f"lspci -s {bdf} ",
                                                                                           cmd_execute_address)
        # if cmd_code == RtnStatusEnum.FAIL.value:
        #     return None
        data["Ethernet controller"] = re.search(r"Ethernet controller:\s+(.+)", cmd_output).group(1)
        data["Ethernet controller"] = data["Ethernet controller"].replace(" ", "_")
        data["Ethernet controller"] = data["Ethernet controller"].replace("(", "_")
        data["Ethernet controller"] = data["Ethernet controller"].replace(")", "_")
        log.info(data["Ethernet controller"])
        return data["Ethernet controller"]

    @classmethod
    def ib_interactive_commcheck(cls, server_ip, oper:str, device_server:str, device_client:str, timeout:int= 5,
                              sever_cmd_address: str = CmdExecuteAdressEnum.SERVER.value,
                              client_cmd_address: str = CmdExecuteAdressEnum.CLIENT.value,
                              *args, **kwargs) -> tuple:
        def server_oper():
            command = f"{oper} -d {device_server} "
            for arg in args:
                command += f"--{arg} "
            for key, val in kwargs.items():
                if val == None:
                    continue
                command += f"--{key}={val} "            
            return cls.execute_command_based_paramiko_with_rtncode(f"timeout {timeout}s {command}", sever_cmd_address)
                
        def client_oper():
            command = f"{oper} -d {device_client} {server_ip} "
            for arg in args:
                command += f"--{arg} "
            for key, val in kwargs.items():
                if val == None:
                    continue
                command += f"--{key}={val} "
            return cls.execute_command_based_paramiko_with_rtncode(command, client_cmd_address)
        cls.execute_command_based_paramiko_with_rtncode(f"killall {oper}", sever_cmd_address)
        cls.execute_command_based_paramiko_with_rtncode(f"killall {oper}", client_cmd_address)
        S = SxeThread(server_oper)
        C = SxeThread(client_oper)
        S.start() ; time.sleep(3) ; C.start()
        C.join() ; S.join()
        # cmd_code, cmd_output, cmd_stderr = C.join() ; cmd_code, cmd_output, cmd_stderr = S.join()
        return S.ret, C.ret

    ##################上面是perftest工具集，下面是rdma-core工具集##################
    
    @classmethod
    def rping_interactive_commcheck(cls, server_ip, 
                              sever_cmd_address: str = CmdExecuteAdressEnum.SERVER.value,
                              client_cmd_address: str = CmdExecuteAdressEnum.CLIENT.value,
                              *args, **kwargs) -> tuple:
        def server_rping(*args, **kwargs):
            command = f"rping -s -a {server_ip} -C 10 -v "
            for arg in args:
                command += f"--{arg} "
            for key, val in kwargs.items():
                command += f"--{key}={val} "            
            return cls.execute_command_based_paramiko_with_rtncode(command, sever_cmd_address)
                
        def client_rping(*args, **kwargs):
            command = f"rping -c -a {server_ip} -C 10 -v "
            for arg in args:
                command += f"--{arg} "
            for key, val in kwargs.items():
                command += f"--{key}={val} "            
            return cls.execute_command_based_paramiko_with_rtncode(command, client_cmd_address)
        cls.execute_command_based_paramiko_with_rtncode("killall rping", sever_cmd_address)
        cls.execute_command_based_paramiko_with_rtncode("killall rping", client_cmd_address)
        S = SxeThread(server_rping)
        C = SxeThread(client_rping)
        S.start() ; time.sleep(3) ; C.start()
        C.join() ; S.join()
        # cmd_code, cmd_output, cmd_stderr = C.join() ; cmd_code, cmd_output, cmd_stderr = S.join()
        return S.ret, C.ret

    @classmethod
    def rdma_link(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        command = "rdma link"
        _, cmd_output, _ = cls.execute_command_with_error(command, cmd_execute_address)
        all = []
        rdmas = cmd_output.split('\n')
        for rdma in rdmas:
            new = rdma_link_info() ; data = rdma.split()
            data[1] = new.link
            data[3] = new.state
            data[5] = new.physical_state
            data[7] = new.netdev
            all.append(new)
        return all

    def rdma_resource(cls, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value, *args, **kwargs):
        command = f"rdma resource -j"
        cmd_code, cmd_output, cmd_stderr = cls.execute_command_with_error(command, cmd_execute_address)
        if cmd_code != RtnStatusEnum.SUCCESS.value:
            return cmd_code, cmd_stderr
        return cmd_code, json.loads(cmd_output)

    @classmethod
    def get_gid_info_by_ip(cls, dev, ip_address, format_gid=True, cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        command = f"ibv_devinfo -v -d {dev} |grep {ip_address}"
        _, cmd_output, _ = cls.execute_command_with_error(command, cmd_execute_address)
        match = re.search(r'GID\[\s*(\d+)\s*]:\s*(::ffff:[\d\.]+),\s*(.*)', cmd_output)
        if match:
            gid_index = match.group(1)  # 获取GID部分
            gid = match.group(2)  # 获取完整的IP地址部分
            description_segment = match.group(3)  # 获取描述部分
            if format_gid:
                # ipv6转换
                if '.' not in gid:
                    parts = gid.split(':')
                    double_colon_index = None
                    for i, part in enumerate(parts):
                        if part == '':
                            double_colon_index = i
                            break
                    if double_colon_index is not None:
                        missing_parts = 8 - len(parts) + 1  # +1 for the empty part
                        parts = parts[:double_colon_index] + ['0000'] * missing_parts + parts[
                                                                                        double_colon_index + 1:]
                # ipv4转换
                else:
                    parts = gid.split(':')
                    ipv4_part = parts[-1]
                    temp_list = [format(int(x), '02x') for x in ipv4_part.split('.')]
                    new_list = []
                    for i in range(0, len(temp_list), 2):
                        new_list.append(temp_list[i] + temp_list[i + 1])
                    parts = parts[:-1] + new_list
                    double_colon_index = None
                    for i, part in enumerate(parts):
                        if part == '':
                            double_colon_index = i
                            break
                    if double_colon_index is not None:
                        missing_parts = 8 - len(parts) + 1  # +1 for the empty part
                        parts = parts[:double_colon_index] + ['0000'] * missing_parts + parts[
                                                                                        double_colon_index + 1:]
                formatted_parts = [part.zfill(4) for part in parts]
                gid = ':'.join(formatted_parts)
                
            return gid_index, gid, description_segment

    @classmethod
    def get_gid_info_by_ib_gid_info(cls, rdma_name, rdma_port, format_gid=True,
                                    cmd_execute_address: str = CmdExecuteAdressEnum.SERVER.value):
        cmd = f'ibv_devinfo -v -d {rdma_name} -i {rdma_port} |grep GID'
        cmd_code, cmd_output, cmd_stderr = cls.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address)
        if cmd_code != RtnStatusEnum.SUCCESS.value:
            log.error(f'cmd:{cmd}执行失败')
            return {}
        match = re.findall(r'GID\[\s*(\d+)]:\s*([\w:]+)', cmd_output)
        if match:
            gid_idx = match[0][0]
            gid_value = match[0][1]
            log.info("当前环境GID为{}".format(gid_value))
            return gid_idx, gid_value

    @classmethod
    def random_available_ip_address(cls, **kwargs) -> list:
        ipaddress_type = kwargs.get("ipaddress_type", "ipv4")
        prefix = kwargs.get("prefix", "")
        num = kwargs.get("num", 2)
        if ipaddress_type == "ipv4":
            return cls.random_available_ipv4_address(prefix, num)
        elif ipaddress_type == "ipv6":
            return cls.random_available_ipv6_address(prefix, num)
        else:
            log.warning("Not found vaild ipaddress_type")
            return None

    @classmethod
    def get_rdma_link(cls, rdma_dev_i: str = "", dev_port_i: str = "1", exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> dict:
        """
        author: xiangyu.liu
        date: 2024.10.21
        description: 获取rdma link信息
        :param rdma_dev_i: rdma设备名称，不指定时返回全部rdma link
        :param exec_addr: 执行环境
        :return: 返回 rdma_device
        """
        rtn_dict = {}
        if rdma_dev_i:
            cmd = f"rdma link -jp show {rdma_dev_i}/{dev_port_i}"
        else:
            cmd = f"rdma link -jp"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            log.error(f'cmd:{cmd}执行失败')
            return {}
        data = json.loads(result)
        for i in data:
            rdma_dev = i['ifname']
            if rdma_dev_i:
                if rdma_dev == rdma_dev_i:
                    rtn_dict[rdma_dev] = copy.deepcopy(i)
                    break
            else:
                rtn_dict[rdma_dev] = copy.deepcopy(i)
        return rtn_dict

    @classmethod
    def get_dev_by_net(cls, netdev_i: str, exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author: xiangyu.liu
        date: 2024.10.21
        description: 获取rdma的设备名
        :param netdev_i: lan设备名称
        :param exec_addr: 执行环境
        :return: 返回 rdma_device
        """
        rdma_link_dict = cls.get_rdma_link(exec_addr=exec_addr)
        for k, v in rdma_link_dict.items():
            if v["netdev"] == netdev_i:
                return k

    @classmethod
    def get_net_dev_by_rdma(cls, rdmadev_i: str, exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author: xiangyu.liu
        date: 2024.10.21
        description: 获取lan的设备名
        :param rdmadev_i: rdma设备名称
        :param exec_addr: 执行环境
        :return: 返回 lan_device
        """
        rdma_link_dict = cls.get_rdma_link(rdmadev_i, exec_addr=exec_addr)
        print(f'rdma_link_dict: {rdma_link_dict}')
        print(f'rdmadev_i: {rdmadev_i}')
        for k, v in rdma_link_dict.items():
            if k == rdmadev_i:
                return v['netdev']

    @classmethod
    def get_dev_port(cls, rdma_dev_i: str, exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> list:
        """
        author: xiangyu.liu
        date: 2024.10.21
        description: 获取rdma的设备名
        :param rdma_dev_i: rdma设备名称
        :param exec_addr: 执行环境
        :return: 返回 rdma_device
        """
        all_port = []
        rdma_link_dict = cls.get_rdma_link(rdma_dev_i, exec_addr=exec_addr)
        for k, v in rdma_link_dict.items():
            if k == rdma_dev_i:
                all_port.append(v['port'])
        return all_port

    @classmethod
    def get_dev_bdf(cls, rdma_dev_i: str, exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> str:
        """
        author: xiangyu.liu
        date: 2024.10.21
        description: 获取rdma的设备名
        :param rdma_dev_i: rdma设备名称
        :param exec_addr: 执行环境
        :return: 返回 rdma_device
        """
        eth_dev = cls.get_net_dev_by_rdma(rdma_dev_i, exec_addr)
        cmd = f'ethtool -i {eth_dev}'
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            log.error(f'cmd:{cmd}执行失败')
            return ''
        res = re.findall(r'bus-info: ([\d:\.]+)', result)
        if res:
            bdf = res[0]
        else:
            bdf = ''
        return bdf

    @classmethod
    def get_port_gid(cls, rdma_dev_i: str, dev_port: str, exec_addr: str = CmdExecuteAdressEnum.SERVER.value,
                     format_gid: bool = True) -> dict:
        """
        author: xiangyu.liu
        date: 2024.10.21
        description: 获取rdma的设备名
        :param rdma_dev_i: rdma设备名称
        :param exec_addr: 执行环境
        :return: 返回 rdma_device
        """
        rtn_dict = {}
        gid_type = ''
        lan_dev = cls.get_net_dev_by_rdma(rdma_dev_i, exec_addr)
        cmd = f'ifconfig {lan_dev}|grep ether'
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            log.error(f'cmd:{cmd}执行失败')
            return {}
        lan_mac = re.findall(r'([\w:]{17})', result)[0]
        cmd = f'ibv_devinfo -v -d {rdma_dev_i} -i {dev_port}|grep GID'
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            log.error(f'cmd:{cmd}执行失败')
            return {}
        res = re.findall(r'\s+GID\[\s+(\d+)\]:\s+([\w:.]+), RoCE v2', result)
        if res:
            for gid_index, gid in res:
                if lan_mac[-5:].replace(":", "") in "{:0>4}".format(gid.split(':')[-1]):
                    gid_type = GidType.DEFAULT.value
                elif "." in gid:
                    gid_type = GidType.IPV4.value
                else:
                    gid_type = GidType.IPV6.value

                if format_gid:
                    # ipv6转换
                    if '.' not in gid:
                        parts = gid.split(':')
                        double_colon_index = None
                        for i, part in enumerate(parts):
                            if part == '':
                                double_colon_index = i
                                break
                        if double_colon_index is not None:
                            missing_parts = 8 - len(parts) + 1  # +1 for the empty part
                            parts = parts[:double_colon_index] + ['0000'] * missing_parts + parts[
                                                                                            double_colon_index + 1:]
                    # ipv4转换
                    else:
                        parts = gid.split(':')
                        ipv4_part = parts[-1]
                        temp_list = [format(int(x), '02x') for x in ipv4_part.split('.')]
                        new_list = []
                        for i in range(0, len(temp_list), 2):
                            new_list.append(temp_list[i] + temp_list[i + 1])
                        parts = parts[:-1] + new_list
                        double_colon_index = None
                        for i, part in enumerate(parts):
                            if part == '':
                                double_colon_index = i
                                break
                        if double_colon_index is not None:
                            missing_parts = 8 - len(parts) + 1  # +1 for the empty part
                            parts = parts[:double_colon_index] + ['0000'] * missing_parts + parts[
                                                                                            double_colon_index + 1:]
                    formatted_parts = [part.zfill(4) for part in parts]
                    gid = ':'.join(formatted_parts)
                rtn_dict[gid_index] = [gid_type, gid]
            return rtn_dict
        else:
            return {}

    @classmethod
    def get_rdma_resource(cls, rdma_dev_i: str, dev_port_i: str = '1', element_name: str = '',
                          exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> dict:
        """
        author: xiangyu.liu
        date: 2024.10.21
        description: 获取rdma的资源数量
        :param lan_dev_i: lan网络接口名称，不指定时返回全部rdma link
        :param exec_addr: 执行环境
        :return: 返回 rdma_device
        """
        rtn_dict = {}

        if not element_name:
            cmd = f"rdma resource -jp show"
        else:
            cmd = f"rdma resource -jp show {element_name}"

        if rdma_dev_i:
            if element_name in ['']:
                cmd += f' {rdma_dev_i}'
            elif element_name in ['qp', 'cmd_id']:
                cmd += f' link {rdma_dev_i}/{dev_port_i}'
            elif element_name in ['cq', 'pd', 'mr', 'ctx', 'srq']:
                cmd += f' dev {rdma_dev_i}'

        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            log.error(f'cmd:{cmd}执行失败')
            return {}
        data = json.loads(result)

        # 遍历每个
        temp_list = []
        for i in data:
            rdma_dev = i['ifname']
            if rdma_dev == rdma_dev_i:
                temp_list.append(copy.deepcopy(i))
        rtn_dict[rdma_dev_i] = copy.deepcopy(temp_list)
        return rtn_dict

    @classmethod
    def get_rdma_statistic(cls, rdma_dev_i: str, dev_port_i: str = '1', exec_addr: str = CmdExecuteAdressEnum.SERVER.value) -> dict:
        """
        author: xiangyu.liu
        date: 2024.10.21
        description: 获取rdma的统计信息
        :param lan_dev_i: lan网络接口名称，不指定时返回全部rdma link
        :param exec_addr: 执行环境
        :return: 返回 rdma_device
        """
        rtn_dict = {}
        if rdma_dev_i:
            cmd = f"rdma statistic -jp show link {rdma_dev_i}/{dev_port_i}"
        else:
            cmd = f"rdma statistic -jp"
        status, result, err = CommandOperation.execute_command_with_error(cmd, exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            log.error(f'cmd:{cmd}执行失败')
            return {}
        data = json.loads(result)

        # 遍历每个
        for i in data:
            rdma_dev = i['ifname']
            rtn_dict[rdma_dev] = copy.deepcopy(i)
            if rdma_dev == rdma_dev_i:
                break
        return rtn_dict
