import random
import time
from math import *
from pathlib import Path
from holowan.v2.engine import Engine # 导⼊引擎模块
from holowan.v2.engine.path import DelayGamma # 导⼊损伤模块
from holowan.v2.engine.path import *
from holowan.v2.engine.classifier import IPv4Rule # 导⼊报⽂过滤器模块
from holowan.v2.engine.classifier import IPv6Rule # 导⼊报⽂过滤器模块
from holowan.v2.pixel import Pixel, FilterSettings
from holowan.v2.engine.stats import Statistics
from holowan.v2.pixel import FilterSettings, Pixel, MACFilter, Damage


from scripts.script_libs import log


class HolowanApi:
    def __init__(self, holowan_ip="172.17.30.88", holowan_port = "8080", engine_id:int = 1):
        # 初始化参数
        self.holowan_ip = holowan_ip  # HoloWAN 管理端⼝ IP地址
        self.holowan_port = holowan_port  # HoloWAN 端⼝号，默认为 8080
        self.engine_id = engine_id  # 下发损伤配置的引擎ID，engine1 ID为1，engine2 ID为2，以此类推
        self.holowan_conn_param = [holowan_ip, holowan_port, engine_id]
        self.engine = Engine(holowan_ip, holowan_port, engine_id) # 创建Engine对象
        # log.info(f'[Holwan] {result}.')

    def virtual_path_reset(self, path_id=1):
        """重置虚拟链路"""
        # 应⽤设置
        result = self.engine.reset_path(path_id)
        # 打印 result 判断是否应⽤成功
        print(result)

    def virtual_path_add(self):
        """添加虚拟链路"""
        # 应⽤设置
        result = self.engine.add_path()
        # 打印 result 判断是否应⽤成功
        print(result)

    def virtual_path_del(self, path_id=1, path_name="PATH 1"):
        """删除虚拟链路"""
        """
            path_id: int, 待禁⽤的 path 的 id
            path_name: str, 待禁⽤的 path 的名称
        """
        # 应⽤设置
        result = self.engine.remove_path(path_id, path_name)
        # 打印 result 判断是否应⽤成功
        print(result)

    def virtual_path_disable(self, path_id=1, path_name="PATH 1"):
        """禁用虚拟链路"""
        """
            path_id: int, 待禁⽤的 path 的 id
            path_name: str, 待禁⽤的 path 的名称
        """
        # 应⽤设置
        result = self.engine.disable_path(path_id,path_name)
        # 打印 result 判断是否应⽤成功
        print(result)

    def virtual_path_enable(self, path_id=1, path_name="PATH 1"):
        """启用虚拟链路"""
        """
            path_id: int, 待启⽤的 path 的 id
            path_name: str, 待启⽤的 path 的名称
        """
        # 应⽤设置
        result = self.engine.enable_path(path_id,path_name)
        # 打印 result 判断是否应⽤成功
        print(result)

    def virtual_path_apply_cfg(self, path_id=1):
        """将指定 Path 的配置应⽤到 HoloWAN"""
        """
            path_id: int, 待启⽤的 path 的 id
            path_name: str, 待启⽤的 path 的名称
        """
        path1 = self.engine.get_path_by_id(path_id)
        # 应⽤设置
        result = self.engine.apply_path_configuration(path1)
        # 打印 result 判断是否应⽤成功
        print(result)

    def packet_modify_disable(self, path_id=1, direction=0,):
        """禁用报文修改"""
        # 获取 path1
        path1 = self.engine.get_path_by_id(path_id)
        # 设置 path1 上 port1 to port2 ⽅向禁⽤报⽂修改
        if direction == 0: direction = "l2r"
        elif direction == 1: direction = "r2l"
        else: direction = "bi"
        # 形式2
        if direction == "l2r":
            # 设置 path1 上 port1 到 port2 ⽅向上的报⽂修改
            path1.l2r.modify = ModifyDisable()
        elif direction == "r2l":
            # 设置 path1 上 port2 到 port1 ⽅向上的报⽂修改
            path1.r2l.modify = ModifyDisable()
        else:
            # 设置 path1 上 port2 到 port1 以及Port2到Port1⽅向上的报⽂修改
            path1.l2r.modify = ModifyDisable()
            path1.r2l.modify = ModifyDisable()
        # 应⽤设置
        result = self.engine.apply_path_configuration(path1)
        # 打印 result 判断是否应⽤成功
        log.info(f"[HoloWan][packet_modify_disable]: disable the path(id:{path_id}) "
                 f"direction:({direction}) packet modify function, result:{result.data}")

    def packet_modify_mormal(self, path_id=1, direction=0, match_params=None, modify_params=None, crc=1, checksum=1):
        """报文损伤"""
        if modify_params is None:
            modify_params = {}
        if match_params is None:
            match_params = {}
        """usage: 
                    holowan_conn_param[] = ["172.17.30.88", "8080", 1]
                    direction: 0:Port1->port2; 1: Port2->port1; 2: 双向
                    match_params = {"match_header": 17, "match_offset": 2, "match_size": 2, "match_value": "0x12b7"}
        	        modify_params = {"modify_header": 8, "modify_offset": 1, "modify_size": 1, "modify_value": "0x03"}
                    """
        path1 = self.engine.get_path_by_id(path_id)
        #通过参数字典形式传参
        """ matchType参数取值列举             modifyType参数取值列举
            1:Ether                         1:Packet
            4:Vlan                          1:Ether Head
            5:Vlan Stack                    4:Vlan Head
            6:Mpls                          5:Vlan Stack Head
            7:PPPoE                         6:Mpls Head
            8:IPv4                          7:PPPoE Head
            12:IPv6                         8:IPv4 Head
            15:TCP                          12:IPv6 Head
            17:UDP                          15:TCP Head
                                            17:UDP Head
                                            46:Ether Payload
                                            49:Vlan Payload
                                            50:Vlan Stack Payload
            """
        if direction == 0:
            direction = "l2r"
        elif direction == 1:
            direction = "r2l"
        else:
            direction = "bi"
        # 形式2
        if direction == "l2r":
            # 设置 path1 上 port1 到 port2 ⽅向上的报⽂修改
            path1.l2r.modify = ModifyNormal(match_params=match_params, crc=crc, modify_params=modify_params, checksum=checksum)
        elif direction == "r2l":
            # 设置 path1 上 port2 到 port1 ⽅向上的报⽂修改
            path1.r2l.modify = ModifyNormal(match_params=match_params, crc=crc, modify_params=modify_params, checksum=checksum)
        else:
            # 设置 path1 上 port2 到 port1 以及Port2到Port1⽅向上的报⽂修改
            path1.l2r.modify = ModifyNormal(match_params=match_params, crc=crc, modify_params=modify_params,
                                            checksum=checksum)
            path1.r2l.modify = ModifyNormal(match_params=match_params, crc=crc, modify_params=modify_params,
                                            checksum=checksum)
        # 应⽤设置
        result = self.engine.apply_path_configuration(path1)
        # 打印 result 判断是否应⽤成功
        if int(result.res_dict['errCode'])==0:
            log.info(f"[HoloWan][packet_modify_mormal]: configure the path(id:{path_id}) "
                     f"direction:({direction}) packet modify function, result:{result.data}")
        else:log.info(f"[HoloWan][packet_modify_mormal]: configure the path(id:{path_id}) "
                 f"direction:({direction}) packet modify function, result:{result.data}")

    def packet_modify_cycle(self, path_id=1, direction=0, match_params=None, modify_params=None, crc=1, checksum=1):
        """报文损伤"""
        if modify_params is None:
            modify_params = {}
        if match_params is None:
            match_params = {}
        """usage: 
            holowan_conn_param[] = ["172.17.30.88", "8080", 1]
            direction: 0:Port1->port2; 1: Port2->port1; 2: 双向
            match_params = {"match_header": 17, "match_offset": 2, "match_size": 2, "match_value": "0x12b7"}
	        modify_params = {"modify_header": 8, "modify_offset": 1, "modify_size": 1, "modify_value": "0x3", "cycle_period": 100, "cycle_burst": 10}
	        """
        #通过参数字典形式传参
        """ matchType参数取值列举             modifyType参数取值列举
            1:Ether                         1:Packet
            4:Vlan                          1:Ether Head
            5:Vlan Stack                    4:Vlan Head
            6:Mpls                          5:Vlan Stack Head
            7:PPPoE                         6:Mpls Head
            8:IPv4                          7:PPPoE Head
            12:IPv6                         8:IPv4 Head
            15:TCP                          12:IPv6 Head
            17:UDP                          15:TCP Head
                                            17:UDP Head
                                            46:Ether Payload
                                            49:Vlan Payload
                                            50:Vlan Stack Payload
            """
        if direction == 0:
            direction = "l2r"
        elif direction == 1:
            direction = "r2l"
        else:
            direction = "bi"
        path1 = self.engine.get_path_by_id(path_id)
        # 形式2
        if direction == "l2r":
            # 设置 path1 上 port1 到 port2 ⽅向上的报⽂修改
            path1.l2r.modify = ModifyCycle(match_params=match_params, crc=crc, modify_params=modify_params,
                                           checksum=checksum)
        elif direction == "r2l":
            # 设置 path1 上 port2 到 port1 ⽅向上的报⽂修改
            path1.r2l.modify = ModifyCycle(match_params=match_params, crc=crc, modify_params=modify_params,
                                           checksum=checksum)
        else:
            # 设置 path1 上 port2 到 port1 以及Port2到Port1⽅向上的报⽂修改
            path1.l2r.modify = ModifyCycle(match_params=match_params, crc=crc, modify_params=modify_params,
                                           checksum=checksum)
            path1.r2l.modify = ModifyCycle(match_params=match_params, crc=crc, modify_params=modify_params,
                                           checksum=checksum)
        # 应⽤设置
        result = self.engine.apply_path_configuration(path1)
        # 打印 result 判断是否应⽤成功
        if int(result.res_dict['errCode'])==0:
            log.info(f"[Holowan]:{result.data}")
        else:
            log.error(f"[Holowan]:packet_modify_cycle调用失败，请检查环境!(result:{result.data})")

    def packet_modify_random(self, path_id=1, direction=0, match_params=None, modify_params=None, crc=1, checksum=1):
        """报文损伤"""
        if modify_params is None:
            modify_params = {}
        if match_params is None:
            match_params = {}
        """usage: 
            holowan_conn_param[] = ["172.17.30.88", "8080", 1]
            direction: 0:Port1->port2; 1: Port2->port1; 2: 双向
            match_params = {"match_header": 17, "match_offset": 2, "match_size": 2, "match_value": "0x12b7"}
            modify_params = {"modify_header": 8, "modify_offset": 1, "modify_size": 1, "modify_value": "0x3", "random_rate":0.1}
            """
        # 通过参数字典形式传参
        """ matchType参数取值列举             modifyType参数取值列举
            1:Ether                         1:Packet
            4:Vlan                          1:Ether Head
            5:Vlan Stack                    4:Vlan Head
            6:Mpls                          5:Vlan Stack Head
            7:PPPoE                         6:Mpls Head
            8:IPv4                          7:PPPoE Head
            12:IPv6                         8:IPv4 Head
            15:TCP                          12:IPv6 Head
            17:UDP                          15:TCP Head
                                            17:UDP Head
                                            46:Ether Payload
                                            49:Vlan Payload
                                            50:Vlan Stack Payload
            """
        if direction == 0:
            direction = "l2r"
        elif direction == 1:
            direction = "r2l"
        else:
            direction = "bi"
        path1 = self.engine.get_path_by_id(path_id)
        # 形式2
        if direction == "l2r":
            # 设置 path1 上 port1 到 port2 ⽅向上的报⽂修改
            path1.l2r.modify = ModifyRandom(match_params=match_params, modify_params=modify_params,
                                           crc=crc, checksum=checksum)
        elif direction == "r2l":
            # 设置 path1 上 port2 到 port1 ⽅向上的报⽂修改
            path1.r2l.modify = ModifyRandom(match_params=match_params, modify_params=modify_params,
                                           crc=crc, checksum=checksum)
        else:
            # 设置 path1 上 port2 到 port1 以及Port2到Port1⽅向上的报⽂修改
            path1.l2r.modify = ModifyRandom(match_params=match_params, modify_params=modify_params,
                                           crc=crc, checksum=checksum)
            path1.r2l.modify = ModifyRandom(match_params=match_params, modify_params=modify_params,
                                           crc=crc, checksum=checksum)
        # 应⽤设置
        result = self.engine.apply_path_configuration(path1)
        # 打印 result 判断是否应⽤成功
        if int(result.res_dict['errCode'])==0:
            log.info(f"[Holowan]:{result.data}")
        else:
            log.error(f"[Holowan]:packet_modify_random调用失败，请检查环境!(result:{result.data})")
        return int(result.res_dict['errCode'])

    def packet_modify_count(self, path_id=1, direction=0, match_params=None, count_params=None, crc=1, checksum=1):
        """报文损伤"""
        if match_params is None:
            match_params = {}
        if count_params is None:
            count_params = {}
        """usage: 
            holowan_conn_param[] = ["172.17.30.88", "8080", 1]
            direction: 0:Port1->port2; 1: Port2->port1; 2: 双向
            match_params = {"match_header": 17, "match_offset": 2, "match_size": 2, "match_value": "0x12b7"}
            count_params = {"offset": 22, "value": "ee", "modify_offset": 44, "modify_count": 1}
            """
        # 通过参数字典形式传参
        """ matchType参数取值列举
            1:Ether
            4:Vlan
            5:Vlan Stack
            6:Mpls
            7:PPPoE
            8:IPv4
            12:IPv6
            15:TCP
            17:UDP
            """
        if direction == 0:
            direction = "l2r"
        elif direction == 1:
            direction = "r2l"
        else:
            direction = "bi"
        path1 = self.engine.get_path_by_id(path_id)
        # 形式2
        if direction == "l2r":
            # 设置 path1 上 port1 到 port2 ⽅向上的报⽂修改
            path1.l2r.modify = ModifyCount(match_params=match_params, count_params=count_params,
                                           crc=crc, checksum=checksum)
        elif direction == "r2l":
            # 设置 path1 上 port2 到 port1 ⽅向上的报⽂修改
            path1.r2l.modify = ModifyCount(match_params=match_params, count_params=count_params,
                                           crc=crc, checksum=checksum)
        else:
            # 设置 path1 上 port2 到 port1 以及Port2到Port1⽅向上的报⽂修改
            path1.l2r.modify = ModifyCount(match_params=match_params, count_params=count_params,
                                           crc=crc, checksum=checksum)
            path1.r2l.modify = ModifyCount(match_params=match_params, count_params=count_params,
                                           crc=crc, checksum=checksum)
        # 应⽤设置
        result = self.engine.apply_path_configuration(path1)
        # 打印 result 判断是否应⽤成功
        if int(result.res_dict['errCode'])==0:
            log.info(f"[Holowan]:{result.data}")
        else:
            log.error(f"[Holowan]:packet_modify_random调用失败，请检查环境!(result:{result.data})")
        return int(result.res_dict['errCode'])

    def background_stream_disable(self, path_id=1, direction=0):
        """背景流"""
        """usage: 
            path_id: 对应UI上path id
            direction: 0:Port1->port2; 1: Port2->port1; 2: 双向
            """
        if direction == 0:
            direction = "l2r"
        elif direction == 1:
            direction = "r2l"
        else:
            direction = "bi"
        path1 = self.engine.get_path_by_id(path_id)
        # 形式2
        if direction == "l2r":
            # 设置 path1 上 port1 到 port2 ⽅向上的报⽂修改
            path1.l2r.background_utilization = BackgroundUtilizationDisable()
        elif direction == "r2l":
            # 设置 path1 上 port2 到 port1 ⽅向上的报⽂修改
            path1.r2l.background_utilization = BackgroundUtilizationDisable()
        else:
            # 设置 path1 上 port2 到 port1 以及Port2到Port1⽅向上的报⽂修改
            path1.l2r.background_utilization = BackgroundUtilizationDisable()
            path1.r2l.background_utilization = BackgroundUtilizationDisable()
        # 应⽤设置
        result = self.engine.apply_path_configuration(path1)
        # 打印 result 判断是否应⽤成功
        if int(result.res_dict['errCode'])==0:
            log.info(f"[Holowan]:{result.data}")
        else:
            log.error(f"[Holowan]:background_stream_disable调用失败，请检查环境!{result.data}")

    def background_stream_random(self, path_id=1, direction=0, background_params=None):
        """背景流"""
        if background_params is None:
            background_params = [10, 60]
        """usage: 
            direction: 0:Port1->port2; 1: Port2->port1; 2: 双向
            background_params = [rate:float, burst:int], rate:填写范围 0-100，允许填写⾄⼩数点后⼀位; 
                                burst:背景流量的帧⼤⼩。填写范围 64 - 10000。
            """
        if direction == 0:
            direction = "l2r"
        elif direction == 1:
            direction = "r2l"
        else:
            direction = "bi"
        path1 = self.engine.get_path_by_id(path_id)
        # 形式2
        if direction == "l2r":
            # 设置 path1 上 port1 到 port2 ⽅向上的报⽂修改
            path1.l2r.background_utilization = BackgroundUtilizationRandom(background_params[0], background_params[1])
        elif direction == "r2l":
            # 设置 path1 上 port2 到 port1 ⽅向上的报⽂修改
            path1.r2l.background_utilization = BackgroundUtilizationRandom(background_params[0], background_params[1])
        else:
            # 设置 path1 上 port2 到 port1 以及Port2到Port1⽅向上的报⽂修改
            path1.l2r.background_utilization = BackgroundUtilizationRandom(background_params[0], background_params[1])
            path1.r2l.background_utilization = BackgroundUtilizationRandom(background_params[0], background_params[1])
        # 应⽤设置
        result = self.engine.apply_path_configuration(path1)
        # 打印 result 判断是否应⽤成功
        if int(result.res_dict['errCode'])==0:
            log.info(f"[Holowan]:{result.data}")
        else:
            log.error(f"[Holowan]:background_stream_random调用失败，请检查环境!{result.data}")

    def packet_loss_random(self, path_id=1, direction=0, loss_rate=0.01):
        """报文丢弃"""
        """usage: 
            loss_rate:float, 每个报⽂丢弃的概率，填写范围 0-100，允许填写⾄⼩数点后 4 位。
            """
        if direction == 0:
            direction = "l2r"
        elif direction == 1:
            direction = "r2l"
        else:
            direction = "bi"
        path1 = self.engine.get_path_by_id(path_id)
        # 形式2
        if direction == "l2r":
            # 设置 path1 上 port1 到 port2 ⽅向上的报⽂修改
            path1.l2r.loss = LossRandom(loss_rate=loss_rate)
        elif direction == "r2l":
            # 设置 path1 上 port2 到 port1 ⽅向上的报⽂修改
            path1.r2l.loss = LossRandom(loss_rate=loss_rate)
        else:
            # 设置 path1 上 port2 到 port1 以及Port2到Port1⽅向上的报⽂修改
            path1.l2r.loss = LossRandom(loss_rate=loss_rate)
            path1.r2l.loss = LossRandom(loss_rate=loss_rate)
        # 应⽤设置
        result = self.engine.apply_path_configuration(path1)
        # 打印 result 判断是否应⽤成功
        if int(result.res_dict['errCode'])==0:
            log.info(f"[Holowan]:{result.data}")
        else:
            log.error(f"[Holowan]:packet_loss_random调用失败，请检查环境!{result.data}")

    def packet_loss_cycle(self, path_id=1, direction=0, period=1000, burst=10):
        """周期丢包，每个周期的最后若⼲个报⽂将被丢弃"""
        """usage: 
            period: int, 丢包的周期，填写范围 1-9999999;
            burst: int, 丢包的个数，填写范围 0-9999998
            """
        if direction == 0:
            direction = "l2r"
        elif direction == 1:
            direction = "r2l"
        else:
            direction = "bi"
        path1 = self.engine.get_path_by_id(path_id)
        # 形式2
        if direction == "l2r":
            # 设置 path1 上 port1 到 port2 ⽅向上的报⽂修改
            path1.l2r.loss = LossCycle(period=period, burst=burst)
        elif direction == "r2l":
            # 设置 path1 上 port2 到 port1 ⽅向上的报⽂修改
            path1.r2l.loss = LossCycle(period=period, burst=burst)
        else:
            # 设置 path1 上 port2 到 port1 以及Port2到Port1⽅向上的报⽂修改
            path1.l2r.loss = LossCycle(period=period, burst=burst)
            path1.r2l.loss = LossCycle(period=period, burst=burst)
        # 应⽤设置
        result = self.engine.apply_path_configuration(path1)
        # 打印 result 判断是否应⽤成功
        if int(result.res_dict['errCode'])==0:
            log.info(f"[Holowan]:{result.data}")
        else:
            log.error(f"[Holowan]:packet_loss_cycle调用失败，请检查环境!{result.data}")

    def packet_loss_burst(self, path_id=1, direction=0, probability=0.01, los_min=10, los_max=100):
        """突发丢包模式，设定每个报⽂被丢弃的概率，⼀旦丢包发⽣，则⼀次性丢弃若⼲的报⽂。"""
        """usage: 
            probability:int, 每个报⽂被丢弃的概率，填写范围 0-100，允许填写⾄⼩数点后 4 位;
            min: 最⼩连续丢包数量，填写范围 0-9999999;
            max: 最⼤连续丢包数量，填写范围 0-9999999。
            """
        if direction == 0:
            direction = "l2r"
        elif direction == 1:
            direction = "r2l"
        else:
            direction = "bi"
        path1 = self.engine.get_path_by_id(path_id)
        # 形式2
        if direction == "l2r":
            # 设置 path1 上 port1 到 port2 ⽅向上的报⽂修改
            path1.l2r.loss = LossBurst(probability=probability, min=los_min, max=los_max)
        elif direction == "r2l":
            # 设置 path1 上 port2 到 port1 ⽅向上的报⽂修改
            path1.r2l.loss = LossBurst(probability=probability, min=los_min, max=los_max)
        else:
            # 设置 path1 上 port2 到 port1 以及Port2到Port1⽅向上的报⽂修改
            path1.l2r.loss = LossBurst(probability=probability, min=los_min, max=los_max)
            path1.r2l.loss = LossBurst(probability=probability, min=los_min, max=los_max)
        # 应⽤设置
        result = self.engine.apply_path_configuration(path1)
        # 打印 result 判断是否应⽤成功
        if int(result.res_dict['errCode'])==0:
            log.info(f"[Holowan]:{result.data}")
        else:
            log.error(f"[Holowan]:packet_loss_burst调用失败，请检查环境!{result.data}")

    def packet_loss_gilbert_elliott(self, path_id=1, direction=0, good_state_loss=0.1, good_state_change=0.2,
                                   bad_state_loss=0.3, bad_state_change=0.4):
        """突发丢包模式，设定每个报⽂被丢弃的概率，⼀旦丢包发⽣，则⼀次性丢弃若⼲的报⽂。"""
        """usage: 
            good_state_loss: float, 良好通道丢包概率，填写范围 0-100，允许填写⾄⼩数点后 4 位。
            good_state_change: float, 良好通道转换到较差通道的概率，填写范围 0-100，允许填写⾄⼩数点后 4 位。
            bad_state_loss: float, 较差通道丢包概率，填写范围 0-100，允许填写⾄⼩数点后 4 位。
            bad_state_change: float, 较差通道转换到良好通道的概率，填写范围 0-100，允许填写⾄⼩数点后 4 位。
            """
        if direction == 0:
            direction = "l2r"
        elif direction == 1:
            direction = "r2l"
        else:
            direction = "bi"
        path1 = self.engine.get_path_by_id(path_id)
        # 形式2
        if direction == "l2r":
            # 设置 path1 上 port1 到 port2 ⽅向上的报⽂修改
            path1.l2r.loss = LossGilbertElliott(good_state_loss=good_state_loss, good_state_change=good_state_change,
                                                bad_state_loss=bad_state_loss, bad_state_change=bad_state_change)
        elif direction == "r2l":
            # 设置 path1 上 port2 到 port1 ⽅向上的报⽂修改
            path1.r2l.loss = LossGilbertElliott(good_state_loss=good_state_loss, good_state_change=good_state_change,
                                                bad_state_loss=bad_state_loss, bad_state_change=bad_state_change)
        else:
            # 设置 path1 上 port2 到 port1 以及Port2到Port1⽅向上的报⽂修改
            path1.l2r.loss = LossGilbertElliott(good_state_loss=good_state_loss, good_state_change=good_state_change,
                                                bad_state_loss=bad_state_loss, bad_state_change=bad_state_change)
            path1.r2l.loss = LossGilbertElliott(good_state_loss=good_state_loss, good_state_change=good_state_change,
                                                bad_state_loss=bad_state_loss, bad_state_change=bad_state_change)
        # 应⽤设置
        result = self.engine.apply_path_configuration(path1)
        # 打印 result 判断是否应⽤成功
        if int(result.res_dict['errCode'])==0:
            log.info(f"[Holowan]:{result.data}")
        else:
            log.error(f"[Holowan]:packet_loss_GilbertElliott调用失败，请检查环境!{result.data}")

    def packet_loss_count(self, path_id=1, direction=0, start_offset=1, loss_count=10):
        """突发丢包模式，设定每个报⽂被丢弃的概率，⼀旦丢包发⽣，则⼀次性丢弃若⼲的报⽂。"""
        """usage: 
            start_offset: 丢包其实位置;
            loss_count: 丢包数。
            """
        if direction == 0:
            direction = "l2r"
        elif direction == 1:
            direction = "r2l"
        else:
            direction = "bi"
        path1 = self.engine.get_path_by_id(path_id)
        # 形式2
        if direction == "l2r":
            # 设置 path1 上 port1 到 port2 ⽅向上的报⽂修改
            path1.l2r.loss = LossCount(start_offset=start_offset, loss_count=loss_count)
        elif direction == "r2l":
            # 设置 path1 上 port2 到 port1 ⽅向上的报⽂修改
            path1.r2l.loss = LossCount(start_offset=start_offset, loss_count=loss_count)
        else:
            # 设置 path1 上 port2 到 port1 以及Port2到Port1⽅向上的报⽂修改
            path1.l2r.loss = LossCount(start_offset=start_offset, loss_count=loss_count)
            path1.r2l.loss = LossCount(start_offset=start_offset, loss_count=loss_count)
        # 应⽤设置
        result = self.engine.apply_path_configuration(path1)
        # 打印 result 判断是否应⽤成功
        if int(result.res_dict['errCode'])==0:
            log.info(f"[packet_loss_count]:{result.data}")
        else:
            log.error(f"[packet_loss_count]:packet_loss_burst调用失败，请检查环境!{result.data}")

    def packet_capture_filter(self, path_id=1, direction=0):
        """
        src_mac, dst_mac
        Ether_type: any/ipv4/ipv6/arp/vlan/roce
        """
        # 创建 Pixel
        pixel = Pixel(self.holowan_ip, self.holowan_port, self.engine_id)
        # 设置 Pixel 过滤规则
        fs = FilterSettings(path=path_id, direction=direction)
        fs.mac = MACFilter(src="39-A9-FA-D7-F5-E8", dst="any", type="any")
        # fs.packet_length
        # 应⽤过滤规则
        result = pixel.set_filter_settings(fs)
        if int(result.res_dict['errCode']) == 0:
            log.info(f"[packet_capture_filter]:{result.data}")
        else:
            log.error(f"[packet_capture_filter]:调用失败，请检查环境!{result.data}")

    def packet_capture(self, duration=5, file_path=None):
        """损伤仪抓包"""
        """
            duration: 抓包持续时间，单位s(秒)
            file_path：存储路径，默认为None，存储在当前
            """
        # 创建 Pixel
        pixel = Pixel(self.holowan_ip, self.holowan_port, self.engine_id)
        pixel.stop_capture()
        time.sleep(2)
        # 清空抓包器
        result = pixel.clean_capture()
        print(result)
        # 开始抓包
        result = pixel.start_capture()
        print(result)
        time.sleep(int(duration))
        result = pixel.stop_capture()
        print(result)
        if file_path is None:
            file_path = f"D:\engine{self.engine_id}_test.pcap"
        # 导出 pcap⽂件
        result = pixel.export_pcap(file_path=file_path)
        if int(result.res_dict['errCode']) == 0:
            log.info(f"[packet_capture]:{result.data}")
        else:
            log.error(f"[packet_capture]:调用失败，请检查环境!{result.data}")

    def packet_capture_start(self):
        """损伤仪抓包"""
        """
            duration: 抓包持续时间，单位s(秒)
            file_path：存储路径，默认为None，存储在当前
            """
        # 创建 Pixel
        pixel = Pixel(self.holowan_ip, self.holowan_port, self.engine_id)
        pixel.stop_capture()
        time.sleep(2)
        # 清空抓包器
        result = pixel.clean_capture()
        print(f"result1:{result}")
        # 开始抓包
        result = pixel.start_capture()
        print(f"result2:{result}")
        if int(result.res_dict['errCode'])==0:
            log.info(f"[HoloWan][packet_capture_start]: Start to capture packet with engin(id:{self.engine_id}).({result.data})")
        else:log.error(f"[HoloWan][packet_capture_start]: Fail to start capture packet for engin(id:{self.engine_id}).({result.data})")

    def packet_capture_stop(self):
        # 创建 Pixel
        pixel = Pixel(self.holowan_ip, self.holowan_port, self.engine_id)
        # 停⽌抓包
        result = pixel.stop_capture()
        if int(result.res_dict['errCode'])==0 or int(result.res_dict['errCode'])==-4:
            log.info(f"[HoloWan][packet_capture_stop]: The capture with engin(id:{self.engine_id}) stopped.({result.data})")
        else:
            log.error(f"[HoloWan][packet_capture_stop]: Failed to stop capture with engin(id:{self.engine_id}).({result.data})")

    def packet_capture_export_pacp(self, file_path=""):
        """损伤仪抓包"""
        # 创建 Pixel
        pixel = Pixel(self.holowan_ip, self.holowan_port, self.engine_id)
        # 设置 pcap ⽂件的名称以及导出路径
        if len(file_path) < 1:
            file_path = f"engine{self.engine_id}_test.pcap"
        # 导出 pcap⽂件
        result = pixel.export_pcap(file_path=file_path)
        if not result:
            log.info(f"[HoloWan][packet_capture_export_pacp]: The capture file(.pcap) has been saved.({file_path}).({result})")
        else:
            log.error(f"[HoloWan][packet_capture_export_pacp]: Failed to save capture file(.pcap).({file_path}).({result})")

    def holowan_stats_clear(self, path_id=1):
        """损伤仪抓包"""
        stats = Statistics(holowan_ip=self.holowan_ip, holowan_port=self.holowan_port, engine_id=self.engine_id)
        path_stats = stats.all_paths_statistics_data
        print(path_stats[path_id].l2r_data)
        result = stats.clear_data()
        if not result:
            log.info(f"[HoloWan][holowan_stats_clear]: Clear engin({self.engine_id}).path({path_id}) statistics.({result.data})")
        else:
            log.error(f"[HoloWan][holowan_stats_clear]: Fail to clear engin({self.engine_id}).path({path_id}) statistics.({result.data})")

    def fixed_bandwidth_modify(self, path_id=1, rate=10000, unit=3, direction=0):
        """带宽修改"""
        """
        rate: float，带宽限制的数值，允许填写⼩数点后 1 位，单位为bps时不允许填写⼩数.
        unit: int, 带宽限制的单位，1：bps，2：Kbps，3：Mbps(默认)。
        默认:10000Mbps
        """
        # from holowan.v2.engine.path import BandwidthFixed
        # from holowan.v2.engine import Engine
        if unit == 1:
            unit_value = "bps"
        elif unit == 1:
            unit_value = "Kbps"
        else:
            unit_value = "Mbps"
        if direction == 0:
            direction = "l2r"
        elif direction == 1:
            direction = "r2l"
        else:
            direction = "bi"
        # 获取 path
        path = self.engine.get_path_by_id(path_id)
        if direction == "l2r":
            # 设置 path1 上 port1 to port2⽅向的带宽限制
            path.l2r.bandwidth = BandwidthFixed(rate=rate, unit=unit)
        elif direction == "r2l":
            # 设置 path1 上 port2 to port1⽅向的带宽限制
            path.r2l.bandwidth = BandwidthFixed(rate=rate, unit=unit)
        else:
            # 设置 path1 上 port1 to port2和 port2 to port1双⽅向的带宽限制
            path.l2r.bandwidth = BandwidthFixed(rate=rate, unit=unit)
            path.r2l.bandwidth = BandwidthFixed(rate=rate, unit=unit)
        # 应⽤损伤参数
        result = self.engine.apply_path_configuration(path)
        if int(result.res_dict['errCode'])==0:
            log.info(f"[HoloWan][fixed_bandwidth_modify]: Confiured engin({self.engine_id}).path({path_id}) "
                     f"fixed_rate={rate}{unit_value}.")
        else:
            log.info(f"[HoloWan][fixed_bandwidth_modify]: Fail to confiure engin({self.engine_id}).path({path_id}) "
                     f"fixed_rate={rate}{unit_value}.({result.data})")
        return result
            