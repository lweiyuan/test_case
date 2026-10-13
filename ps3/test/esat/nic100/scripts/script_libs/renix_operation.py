import random
from math import *
from renix_py_api.renix import *
# from src.utils.exceptions import *
# from renix_py_api.benchmark_test.benchmark_test_api import *
# from renix_py_api.benchmark_test.smart_scripter_api import *
# from src.lib.log import log
# from src.const.const import RenixInfo

from scripts.script_libs import log
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.constants import ProtoType, Header, Addr, FrameLen, Payload
from scripts.script_libs.exceptions import *


class RenixApi:

    def __init__(self):
        # 初始化参数
        initialize(log_handle=log)
        log.info('[Renix] init finished')
        # config.ini文件中预定义的端口列表
        self.port_locations = RenixInfo.renix_port_locations
        # 获取系统入口
        self.sys_entry = get_sys_entry()
        # 预约端口字典；保存名称和对象的对应关系
        self.port_dict = {}
        # 接口字典；保存名称和对象的对应关系
        self.interface_dict = {}
        # 数据流字典；保存名称和对象的对应关系
        self.stream_dict = {}

    def connect_chassis(self):
        """
        连接chassis
        :return:
        """
        ConnectChassisCommand(HostnameList=RenixInfo.renix_server).execute()
        hw_manager = self.sys_entry.get_children('HardwareManager')[0]
        hw_chassis = hw_manager.get_children('HardwareChassis')[0]
        if hw_chassis.State.name != "CHASSIS_UP":
            log.error('[Renix] Failed to connect chassis.')
            raise Exception('[connect_to_chassis] chassis is not up')
        log.info('[Renix] Connect to chassis successfully.')

    def disconnect_chassis(self):
        """
        断开chassis
        :return:
        """
        DisconnectChassisCommand(HostnameList=RenixInfo.renix_server).execute()
        hw_manager = self.sys_entry.get_children('HardwareManager')[0]
        hw_chassis = hw_manager.get_children('HardwareChassis')[0]
        if hw_chassis.State.name != "CHASSIS_DOWN":
            raise Exception('[disconnect_chassis] chassis is not down')
        log.info('[Renix] Disconnect chassis successfully.')

    def reserve_ports(self, port_list: [] = None) -> list:
        """
        所有预置端口上线
        :return: 预约成功的端口的名称列表
        """
        port_names = []
        # 根据需要上线端口，默认全部
        if port_list:
            reserve_port_list = port_list
        else:
            reserve_port_list = self.port_locations
        # 强制释放所有端口，避免预约失败
        # ReleasePortCommand(LocationList=reserve_port_list, ForceRelease=True).execute()
        for port in reserve_port_list:
            # 创建端口，并命令
            port_i = Port(upper=self.sys_entry, Location=port)
            BringPortsOnlineCommand(PortList=[port_i.handle]).execute()
            if port_i.Online:
                self.port_dict.update({port_i.Name: port_i})
                port_names.append(port_i.Name)
                log.info(f'[Renix] [bring_port_online]端口:[{port_i.Name}#{port_i.Location}]上线成功')
                ether_type = str(port_i.get_relatives('SelectMedia', EnumRelationDirection.TARGET)[0])
                media = re.findall(r'Autogen.' + '(.*)' + ' object at', ether_type)[0]
                link_status = str(port_i.get_children(media)[0].LinkStatus)
                log.info(f'[Renix] 端口:[{port_i.Name}#{port_i.Location}] link 状态： {link_status}')
            else:
                log.error(f'[bring_port_online]端口:[{port_i.Name}#{port_i.Location}]上线失败')
                raise Exception(f'[bring_port_online]端口:[{port_i.Name}#{port_i.Location}]上线失败')
        return port_names

    def release_ports(self):
        """
        强制释放所有端口
        :return:
        """
        ReleasePortCommand(LocationList=self.port_locations, ForceRelease=True).execute()

    def build_interface(self, network_layer: str, top_layers: list, port_list: list = None) -> list:
        """
        创建接口
        :network_layer
        :top_layers: ['ipv4'];Valid inputs include eth, ipv4, ipv6, ppp, pppoe, vlan and vxlan
        :return: 创建的接口的名称列表
        """
        interface_names = []
        if not port_list:
            port_list = list(self.port_dict.keys())
        try:
            for port in port_list:
                interface = Interface(upper=self.port_dict[port])
                build_interface = BuildInterfaceCommand(InterfaceList=interface.Name, NetworkLayers=network_layer,
                                                        TopLayers=top_layers)
                build_interface.execute()
                self.interface_dict.update({interface.Name: interface})
                interface_names.append(interface.Name)
            log.info(f"[Renix] {port_list}添加接口成功")
            return interface_names
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 添加接口发生错误: {exception}")

    def update_interface(self, interface, layer, **kwargs) -> bool:
        """
        修改接口参数
        :param interface:
        :param layer:
        :param kwargs:
        :return:
        """
        if not interface or not kwargs:
            log.error('[Renix] 输入的interface或者参数有误！')
            return False
        try:
            interface_obj = self.interface_dict[interface]
            if layer == 'basic':
                interface_obj.edit(**kwargs)
            elif layer == 'eth':
                eth_layer = interface_obj.get_children('EthIILayer')[0]
                eth_layer.edit(**kwargs)
            elif layer == 'ipv4':
                ipv4_layer = interface_obj.get_children('Ipv4Layer')[0]
                ipv4_layer.edit(**kwargs)
            elif layer == 'ipv6':
                ipv6_layer = interface_obj.get_children('Ipv6Layer')[0]
                ipv6_layer.edit(**kwargs)
            elif layer == 'vlan':
                vlan_layer = interface_obj.get_children('VlanLayer')[0]
                vlan_layer.edit(**kwargs)
            elif layer == 'vlan_2':
                vlan_layer = interface_obj.get_children('VlanLayer')[1]
                vlan_layer.edit(**kwargs)
            else:
                return False
            # match layer:
            #     case 'basic':
            #         interface_obj.edit(**kwargs)
            #     case 'eth':
            #         eth_layer = interface_obj.get_children('EthIILayer')[0]
            #         eth_layer.edit(**kwargs)
            #     case 'ipv4':
            #         ipv4_layer = interface_obj.get_children('Ipv4Layer')[0]
            #         ipv4_layer.edit(**kwargs)
            #     case 'ipv6':
            #         ipv6_layer = interface_obj.get_children('Ipv6Layer')[0]
            #         ipv6_layer.edit(**kwargs)
            #     case 'vlan':
            #         vlan_layer = interface_obj.get_children('VlanLayer')[0]
            #         vlan_layer.edit(**kwargs)
            #     case 'vlan_2':
            #         vlan_layer = interface_obj.get_children('VlanLayer')[1]
            #         vlan_layer.edit(**kwargs)
            #     case _:
            #         return False
            return True
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 更新{interface}时发生错误: {exception}")

    def update_port_config(self, port, kwargs: dict) -> bool:
        """
        Object: 编辑端口配置，包括协商模式，速率，流控等
        :param port: 端口名称
        :param kwargs: 要修改的参数名称和值
                    Media: COPPER/FIBER
                    AutoNegotiation: True|False, default is True
                    LineSpeed: SPEED_10G, ......
                    Duplex: HALF/FULL
                    FlowControl: ENABLE/DISABLE/AUTO, default is DISABLE
        Return: None
        """
        try:
            port_object = self.port_dict[port]
            command = ConfigurePortsCommand(PortList=port_object.handle, **kwargs)
            command.execute()
            time.sleep(3)
            log.info(f"[Renix] 更新端口{port}完成")
            return True
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 更新{port}参数发生错误: {exception}")

    def update_port_schedule(self, port, **kwargs) -> bool:
        """
        Object: 修改端口级别关于流量的参数，包括发送模式，发送速率，造错等
        :param port: 端口名称
        :param kwargs:
                    TransmitMode: transmit mode, EnumTransmitMode.CONTINUOUS|BURST|TIME|STEP|ONSTREAM
                    GenerateError: generate error, EnumErrorGen.NO_ERROR|CRC
                    LoadProfileType: port base schedule or stream base schedule,
                                     EnumLoadProfileType.PORT_BASE|STREAM_BASE
                    IgnoreLinkState: ignore link state, EnumIgnoreLinkState.NO|YES
                    TimeStampPosTx: Timestamp Position Tx, EnumTimeStampPos.TIMESTAMP_HEAD|TIMESTAMP_TAIL
                    TimeStampPosRx: Timestamp Position Rx, EnumTimeStampPos.TIMESTAMP_HEAD|TIMESTAMP_TAIL
                    Rate: Inter Frame Gap (port base) rate
                    Unit: Inter Frame Gap (port base) unit, EnumFrameGapUnit.NS|PERCENT|FRAME_PER_SEC|BYTE_PER_SEC|
                          DATABIT_PER_SEC|LINEBIT_PER_SEC|INTER_FRAME_GAP_BYTE|KLINEBIT_PER_SEC|MLINEBIT_PER_SEC
                    Unit: stream base unit, EnumRateUnit.FRAME_PER_SEC|BYTE_PER_SEC
                    FramePerBurst: frames per burst
                    BurstCount: single burst or multiple bursts
                    BurstGap: gap between 2 bursts
                    BurstGapUnit: gap unit, EnumStreamBurstGapUnit.NS|US|MS|SEC
                    Seconds: Duration if Transmit Mode is Time
                    Frames: Frames if Transmit Mode is STEP
        return: None
        def update_port_schedule(self, port, kwargs: dict) 得到的kwargs是dict_items([('GenerateError', 'EnumErrorGen.CRC')])
        def update_port_schedule(self, port, **kwargs) 得到的kwargs是dict_items([('GenerateError', <EnumErrorGen.CRC: 1>)])
        """
        data_general = {}
        data_load_profile = {}
        data_transmit_mode = {}
        port_obj = self.port_dict[port]
        stream_port_cfg = port_obj.get_children(StreamPortConfig.cls_name())[0]
        # 端口的普通参数，造错，时延，端口带宽等
        list_rom_properties_cmd = ListROMPropertiesCommand(ROMName='StreamPortConfig', GetDetail=False)
        list_rom_properties_cmd.execute()
        params_general = list_rom_properties_cmd.Properties
        # 带宽单位和值
        list_rom_properties_cmd = ListROMPropertiesCommand(ROMName='InterFrameGapProfile', GetDetail=True)
        list_rom_properties_cmd.execute()
        params_load_profile = list_rom_properties_cmd.Properties
        # 突发配置时的参数
        list_rom_properties_cmd = ListROMPropertiesCommand(ROMName='BurstTransmitConfig', GetDetail=False)
        list_rom_properties_cmd.execute()
        params_trans_mode = list_rom_properties_cmd.Properties
        # 时间突发配置时的参数
        list_rom_properties_cmd = ListROMPropertiesCommand(ROMName='TimeTransmitConfig', GetDetail=False)
        list_rom_properties_cmd.execute()
        params_trans_2nd = list_rom_properties_cmd.Properties
        # step突发配置时的参数
        list_rom_properties_cmd = ListROMPropertiesCommand(ROMName='StepTransmitConfig', GetDetail=False)
        list_rom_properties_cmd.execute()
        params_trans_3nd = list_rom_properties_cmd.Properties
        params_trans_mode.extend(params_trans_2nd)
        params_trans_mode.extend(params_trans_3nd)
        params_trans_mode = list(set(params_trans_mode))

        try:
            for k, v in kwargs.items():
                if k in params_general:
                    data_general[k] = v
                elif k in params_load_profile:
                    data_load_profile[k] = v
                elif k in params_trans_mode:
                    data_transmit_mode[k] = v
                else:
                    raise InvalidInputParam(f'不支持设置{k}')
            if data_general:
                stream_port_cfg.edit(**data_general)

            if data_load_profile:
                if stream_port_cfg.LoadProfileType.name == 'PORT_BASE':
                    load_profile_cfg = stream_port_cfg.get_children(InterFrameGapProfile.cls_name())[0]
                else:
                    load_profile_cfg = stream_port_cfg.get_children(StreamLoadProfile.cls_name())[0]
                load_profile_cfg.edit(**data_load_profile)
            if data_transmit_mode:
                if stream_port_cfg.TransmitMode.name == 'BURST':
                    trans_mode_cfg = stream_port_cfg.get_children(BurstTransmitConfig.cls_name())[0]
                elif stream_port_cfg.TransmitMode.name == 'TIME':
                    trans_mode_cfg = stream_port_cfg.get_children(TimeTransmitConfig.cls_name())[0]
                elif stream_port_cfg.TransmitMode.name == 'STEP':
                    trans_mode_cfg = stream_port_cfg.get_children(StepTransmitConfig.cls_name())[0]
                else:
                    trans_mode_cfg = None
                    raise InvalidInputParam(f'不支持该流量类型')
                if trans_mode_cfg is not None:
                    trans_mode_cfg.edit(**data_transmit_mode)
            log.info(f"[Renix] 更新端口{port}完成")
            return True
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 修改流量profile发生错误: {exception}")

    def update_stream_load(self, stream, **kwargs) -> bool:
        """
        Object: 修改流的速率单位和值
        :param stream: 流名称
        :param kwargs:
            Rate: 速率
            Unit: 速率的单位, EnumFrameLoadUnit.FRAME_PER_SEC, EnumFrameLoadUnit.PERCENT ...
        Return: none
        Usage: edit_stream_load('Stream_1', Rate=20)
        """
        try:
            stream_obj = self.stream_dict[stream]
            load_obj = stream_obj.get_children('StreamTemplateLoadProfile')[0]
            load_obj.edit(**kwargs)
            log.info(f"[Renix] 更新流{stream}的速率完成")
            return True
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 修改流量带宽发生错误: {exception}")

    def update_stream_sche(self, stream, **kwargs) -> bool:
        """
        Object: 修改流的发送模式
        :param stream: 流名称
        :param kwargs:
        Return: none
        Usage: edit_stream_load('Stream_1', Rate=20)
        """
        try:
            stream_obj = self.stream_dict[stream]
            load_obj = stream_obj.get_children('StreamTransmitConfig')[0]
            load_obj.edit(**kwargs)
            log.info(f"[Renix] 更新流{stream}的发送模式完成")
            return True
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 修改流量发送模式发生错误: {exception}")

    def edit_stream(self, stream, **kwargs) -> bool:
        """
        Object: 修改流的参数，帧长等信息
        :param stream: 流名称
        :param kwargs:
            RepeatCount: 重复次数
            EnableSignature：使能signature域
            FrameLengthType：帧长类型
            FixedLength：帧长，固定帧长时使用
            MinLength：最小帧长，递增/递减/随机帧长使用
            MaxLength：最小帧长，递增/递减/随机帧长使用
            PayloadType:
            ......
        Return: none
        edit_stream(stream_1, FrameLengthType='RANDOM', MinLength=64, MaxLength=1518)
        """
        try:
            obj = self.stream_dict[stream]
            obj.edit(**kwargs)
            log.info(f"[Renix] 更新流{stream}的参数完成")
            return True
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 修改流量general参数发生错误: {exception}")

    def edit_stream_header(self, stream, idx, header_name, **kwargs) -> bool:
        """
        Object: 修改流的header参数，源/目的MAC等信息
        :param stream: 流名称
        :param idx: 流id
        :param header_name: 要修改的header名称
        :param kwargs:要修改的header中的字段名称和值
            ......
        Return: none
        Usage:  edit_stream_header('Stream_1', 0, 'ipv4_1', source='1.1.1.2', destination='33.33.3.3')
                edit_stream_header('Stream_1', 0, 'ethernetII_1', destMacAdd='00:00:00:13:40:ab')
                edit_stream_header('Stream_1', 0, 'custom_1', customOption_0='22335577')
                edit_stream_header('Stream_1', 0, 'udp_1', sourcePort=modifier)
        """
        try:
            stream_channel = self.stream_dict[stream].get_children('StreamChannel')[idx]
            template_string = stream_channel.TemplateString
            template_string = template_string.replace(r'\"', '"')
            paras = []
            if 'custom_' in header_name:
                for k, v in kwargs.items():
                    paras.append(f'{header_name}.patternByte.{k}.customPatternByteOption.patternByteOption={v}')
            else:
                header_types = re.findall(r'name=\"{}\" type=\"(\w*.\w*)\"'.format(header_name), template_string)
                header_type = header_types[0]
                list_header_pro_cmd = ListHeaderPropertiesCommand(header_type)
                list_header_pro_cmd.execute()
                header_properties = list_header_pro_cmd.Properties
                print(f"header_properties: {header_properties}")
                print(f"headers: {ListInstanceLeafCommand(Stream=self.stream_dict[stream].handle, Deep=True).execute()}")
                get_stream_protocol_values_cmd = GetStreamProtocolValuesCommand(Stream=self.stream_dict[stream].handle)
                get_stream_protocol_values_cmd.execute()
                print(get_stream_protocol_values_cmd.__dict__)
                for k, v in kwargs.items():
                    if 'XetModifier' in str(v):
                        for value in v:
                            paras.append(value.replace('XetModifier', f'{header_name}.{k}.XetModifier'))
                    else:
                        paras.append(f'{header_name}.{k}={v}')
            UpdateHeaderCommand(Stream=self.stream_dict[stream].handle, Parameter=paras).execute()
            log.info(f"[Renix] 更新流{stream}的header完成")
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] {stream} 修改报文头{header_name}发生错误: {exception}")

    def edit_stream_node(self, stream, idx, header_name, node, **kwargs):
        """
        Object: 修改流的header参数，源/目的MAC等信息
        :param node:
        :param stream: 流名称
        :param idx: 流id
        :param header_name: 要修改的header名称
        :param kwargs:要修改的header中的字段名称和值
            ......
        Return: none
        Usage:  edit_stream_header('Stream_1', 0, 'ipv4_1', source='1.1.1.2', destination='33.33.3.3')
                edit_stream_header('Stream_1', 0, 'ethernetII_1', destMacAdd='00:00:00:13:40:ab')
                edit_stream_header('Stream_1', 0, 'custom_1', customOption_0='22335577')
                edit_stream_header('Stream_1', 0, 'udp_1', sourcePort=modifier)
        """
        try:
            stream_channel = self.stream_dict[stream].get_children('StreamChannel')[idx]
            template_string = stream_channel.TemplateString
            template_string = template_string.replace(r'\"', '"')
            paras = []
            if 'custom_' in header_name:
                for k, v in kwargs.items():
                    paras.append(f'{header_name}.patternByte.{k}.customPatternByteOption.patternByteOption={v}')
            else:
                header_types = re.findall(r'name=\"{}\" type=\"(\w*.\w*)\"'.format(header_name), template_string)
                header_type = header_types[0]
                list_header_pro_cmd = ListHeaderPropertiesCommand(header_type)
                list_header_pro_cmd.execute()
                header_properties = list_header_pro_cmd.Properties
                print(f"header_properties: {header_properties}")
                get_stream_protocol_values_cmd = GetStreamProtocolValuesCommand(Stream=self.stream_dict[stream].handle)
                get_stream_protocol_values_cmd.execute()
                print(get_stream_protocol_values_cmd.__dict__)
                for k, v in kwargs.items():
                    if 'XetModifier' in str(v):
                        for value in v:
                            paras.append(value.replace('XetModifier', f'{header_name}.{node}.{k}.XetModifier'))
                    else:
                        paras.append(f'{header_name}.{node}.{k}={v}')
            UpdateHeaderCommand(Stream=self.stream_dict[stream].handle, Parameter=paras).execute()
            log.info(f"[Renix] 更新流{stream}的header完成")
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] {stream} 修改报文头{header_name}发生错误: {exception}")

    @staticmethod
    def create_modifier(modi_type, **kwargs) -> list:
        """
        Object: 设置一个跳变，供修改流参数使用
        :Params modi_type: 参数的跳变类型，Increment，Decrement, Random, List
        :Params kw: 跳变的参数
        Return：生成的跳变
        Usage： create_modifier('Increment', StreamType='IntraModifier', Start=1, Count=20, Step=1)
                create_modifier('Random', StreamType='InterModifier', Start=1, Count=20, Range=1000)
                create_modifier('List', StreamType='InterModifier', List=['1.1.1.2', '1.1.1.3'])
        """
        paras = []
        # params = ['Start', 'Count', 'Step', 'Range', 'List', 'StreamType', 'Offset', 'Mask', 'Seed']
        try:
            if modi_type == 'List':
                paras.append(f'XetModifier.{modi_type}=Clear')

            paras.append(f'XetModifier.Type={modi_type}')
            for k, v in kwargs.items():
                if k == 'List':
                    for var in v:
                        paras.append(f'XetModifier.{k}={var}')
                else:
                    paras.append(f'XetModifier.{k}={v}')
            return paras
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 创建modifier发生错误: {exception}")

    def insert_stream_header(self, stream, header):
        """
        Object: 在已存在的某条流中插入某个报文头
        :param stream: 流名称
        :param header: header 名称
        Return: none
        """
        try:
            insert_header_cmd = InsertHeaderCommand(Stream=self.stream_dict[stream].handle, HeaderType=header)
            result = insert_header_cmd.execute()
            # print(f'result: {result}')
            log.info(f"[Renix] 流{stream}添加{header}完成")
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 添加报文头{header}发生错误: {exception}")

    def insert_stream_node(self, stream, header, node_upper, node) -> bool:
        """
        插入节点
        :param stream:
        :param header:
        :param node_upper:
        :param node:
        :return:
        """
        try:
            handle = self.stream_dict[stream].handle
            list_leaf = ListInstanceLeafCommand(Stream=handle, Deep='True')
            list_leaf.execute()
            print(f'list_leaf.Leaves: {list_leaf.Leaves}')
            insert_node_upper = InsertNodeToASetCommand(Stream=handle, ParentName=header, NodeName=node_upper)
            insert_node_upper.execute()
            list_may_insert = ListSetMayInsertCommand(Stream=handle, ParentName=node_upper)
            list_may_insert.execute()
            print(f'list_may_insert._MayInsertNode: {list_may_insert._MayInsertNode}')
            insert_node = InsertNodeToASetCommand(Stream=handle, ParentName=node_upper, NodeName=node)
            insert_node.execute()
            return True
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 插入节点{node}发生错误: {exception}")

    def delete_stream_header(self, stream, header) -> bool:
        """
        Object: 在已存在的某条流中删除某个报文头
        :param stream: 流名称
        :param header: header 名称
        Return: none
        """
        try:
            delete_header_cmd = DeleteHeaderCommand(Stream=self.stream_dict[stream].handle, HeaderName=header)
            delete_header_cmd.execute()
            return True
        except Exception as exception:
            log.error(f"[Renix] 删除报文头发生错误: {exception}")
            return False

    def delete_stream(self, stream):
        try:
            self.stream_dict[stream].delete()
        except Exception as exception:
            log.error(f"[Renix] 删除流模板发生错误: {exception}")

    def delete_interface(self, interface):
        try:
            self.interface_dict[interface].delete()
        except Exception as exception:
            log.error(f"[Renix] 删除接口发生错误: {exception}")

    @staticmethod
    def save_xcfg(filename):
        """
        Object: save the config to a xcfg, only for test
        """
        save_case = SaveTestCaseCommand(TestCase=filename)
        save_case.execute()

    def create_binding_stream(self, src_layer, dst_layer, bidirection=True) -> list:
        """
        创建接口绑定流
        :param src_layer:
        :param dst_layer:
        :param bidirection:
        :return: 返回创建的流量的名称列表
        """
        try:
            # 执行创建绑定流的命令
            create_binding_stream_cmd = CreateBindingStreamCommand(SrcEndpointHandles=src_layer.Name,
                                                                   DstEndpointHandles=dst_layer.Name,
                                                                   Bidirection=bidirection,
                                                                   TopLayerType=1, TrafficMeshMode=0)
            create_binding_stream_cmd.execute()
            time.sleep(1)  # 等待绑定流创建完成
            streams_handle = create_binding_stream_cmd.BindingStreams

            # 查找绑定流的对象和名称
            stream_obj_list = []
            stream_new_list = []

            # 遍历所有端口，找出所有流
            for port in self.port_dict.values():
                stream_obj_list += port.get_children('StreamTemplate')

            # 从所有流中找出此次添加的流
            for stream in stream_obj_list:
                if stream.handle in streams_handle:
                    self.stream_dict[stream.Name] = stream
                    stream_new_list.append(stream.Name)
            log.info(f"[Renix] 创建绑定流完成")
            return stream_new_list
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 创建绑定流发送错误: {exception}")

    def create_stream(self, port, headers) -> str:
        """
        Object: add a raw stream
        :param port: 端口名称
        :param headers: 报文头列表
        Return: 返回创建的流的名称
        Usage:   headers = ['Ethernet.ethernetII', 'IPv4.ipv4', 'TCP.tcp']
                 stream = renix.create_stream('Port_1', headers)
        """
        # 辅助测试使用，查看支持的header 列表
        # list_header_type_cmd = ListHeaderTypesCommand()
        # list_header_type_cmd.execute()
        # print(list_header_type_cmd.__dict__)
        try:
            port_object = self.port_dict[port]
            stream = StreamTemplate(upper=port_object)
            create_header_cmd = CreateHeaderCommand(Stream=stream.handle, HeaderTypes=headers)
            create_header_cmd.execute()
            stream_name = stream.Name
            self.stream_dict[stream_name] = stream
            log.info(f"[Renix] 端口{port}创建raw流完成")
            return stream_name
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] {port}创建raw流发生错误: {exception}")

    def subscribe_result_view(self):
        """
        Object: 将配置文件订阅的统计视图重新订阅
        """
        result_view_handle = []
        try:
            result_view = self.sys_entry.get_children('PageResultView')
            for view in result_view:
                result_view_handle.append(view.handle)
            SubscribeResultCommand(ResultViewHandles=result_view_handle).execute()
        except Exception as exception:
            log.error(f"[Renix] 提交统计视图发生错误: {exception}")

    @staticmethod
    def create_all_result_view():
        try:
            result_view_create = CreateResultViewCommand(DataClassName=PortStats.cls_name(), ResultViewType=1)
            result_view_create.execute()
            result_view_create = CreateResultViewCommand(DataClassName=StreamBlockStats.cls_name(), ResultViewType=1)
            result_view_create.execute()
            result_view_create = CreateResultViewCommand(DataClassName=StreamStats.cls_name(), ResultViewType=1)
            result_view_create.execute()
        except Exception as exception:
            log.error(f"[Renix] 创建统计视图发生错误: {exception}")

    def get_port_stat(self, port, kwargs) -> dict:
        """
        Object: 获取指定端口的统计项的值
        param port: 端口名称
        param kwargs: 可变长度的统计项名称，可包括以下内容：
                    TxStreamFrames: sent total frames generated by fpga
                    RxSignatureStreamFrames: received signature frames
                    TxTotalFrames: sent packets count
                    RxTotalFrames: received packets count
                    TxFrameRate: sent packets rate
                    RxFrameRate: received packets rate
                    TxByteRate: sent byte rate
                    RxByteRate: received byte rate
                    RxIpv4ChecksumError: received IPv4 checksum error packets
                    RxUdpChecksumError: received UDP Checksum error packets
                    RxTcpChecksumError: received TCP Checksum error packets
                    RxFCSErr: received FCS error packets
                    RxUtil: received utilization
                    TxTotalBytes: sent total bytes
                    RxTotalBytes: received total bytes
                    RxPauseFrames: received Pause packets
                    RxUndersizeFrames: received short packets count
                    RxL1Rate: received L1 rate
                    TxL1Rate: sent L1 rate
                             ......
        return:   The statistic data of the retrieved items
        """
        try:
            stats = {}
            port_obj = self.port_dict[port]
            page_result = None
            page_list = self.sys_entry.get_children('PageResultView')
            for page in page_list:
                if page.DataClassName == 'PortStats':
                    page_result = page
            if not isinstance(page_result, PageResultView):
                raise Exception("找不到 Port 统计视图!")
            page_query = page_result.get_children()[0]
            port_stat_list = page_query.get_children()
            for port_stat in port_stat_list:
                if port_stat.PortHandle == port_obj.handle:
                    for item in kwargs:
                        key = f"_{item}"
                        if key in port_stat.__dict__.keys():
                            stats.update({item: port_stat.__dict__[key]})
                        else:
                            log.error(f"[Renix] 端口统计不包括{item}统计项")
            return stats
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 获取{port}统计发生错误: {exception}")

    def get_streamblock_stat(self, stream, kwargs) -> dict:
        """
        Object: 获取指定stream block的统计项的值
        param stream: stream block名称
        param kwargs: 可变长度的统计项名称，可包括以下内容：
                    TxStreamFrames: sent packets count
                    RxStreamFrames: received packets count
                    TxFrameRate: sent packets rate
                    RxFrameRate: received packets rate
                    TxByteRate: sent byte rate
                    RxByteRate: received byte rate
                    RxSeqErr: received sequence error packets
                    RxPayloadErr: received Payload error packets
                    MinLatency: minimum latency
                    AvaLatency: average latency
                    MaxLatency: maximum latency
                    TxBitRate: send bit rate
                    RxBitRate: received bit rate
                    RxUtil: received utilization
                    MinJitter: minimum jitter(10ns)
                    AvaJitter: average jitter(10ns)
                    MaxJitter: maximum jitter(10ns)
                    RxL1Rate: received L1 rate
                    TxL1Rate: sent L1 rate
                    ......
        return:   The statistic data of the retrieved items
        """
        try:
            page_result = None
            stream_found = 0
            stats = {}
            # 判断配置文件中是否有streamblock统计视图
            page_list = self.sys_entry.get_children('PageResultView')
            for page in page_list:
                if page.DataClassName == 'StreamBlockStats':
                    page_result = page
            if not isinstance(page_result, PageResultView):
                raise Exception("找不到 Stream Block 统计视图!")
            # 获取统计
            page_result_query = page_result.get_children()[0]
            record_count = page_result.RecordCount
            record_per_page = page_result.RecordPerPage
            pages = int(ceil(record_count * 1.0 / record_per_page))
            # 翻页查找指定流的统计
            for i in range(pages):
                GotoResultPageCommand(ResultViewHandle=page_result.handle, PageNumber=i + 1).execute()
                time.sleep(3)
                stat_data = page_result_query.get_children()
                for data in stat_data:
                    if data.StreamBlockID == stream:
                        stream_found = 1
                        for item in kwargs:
                            key = f"_{item}"
                            if key in data.__dict__.keys():
                                stats.update({item: data.__dict__[key]})
                            else:
                                raise InvalidInputParam(f"[Renix] stream block统计不包括{item}统计项")
            if stream_found != 1:
                raise InvalidInputParam(f"[Renix] 统计视图里找不到流：{stream}!")
            return stats
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 获取streamblock统计发生错误: {exception}")

    def get_streamblocks_stat(self, streams: list = None, kwargs: list = None) -> dict:
        """
        Object: 获取指定stream block的统计项的值
        param streams: stream block名称
        param kwargs: 可变长度的统计项名称，可包括以下内容：
                    TxStreamFrames: sent packets count
                    RxStreamFrames: received packets count
                    TxFrameRate: sent packets rate
                    RxFrameRate: received packets rate
                    TxByteRate: sent byte rate
                    RxByteRate: received byte rate
                    RxSeqErr: received sequence error packets
                    RxPayloadErr: received Payload error packets
                    MinLatency: minimum latency
                    AvaLatency: average latency
                    MaxLatency: maximum latency
                    TxBitRate: send bit rate
                    RxBitRate: received bit rate
                    RxUtil: received utilization
                    MinJitter: minimum jitter(10ns)
                    AvaJitter: average jitter(10ns)
                    MaxJitter: maximum jitter(10ns)
                    RxL1Rate: received L1 rate
                    TxL1Rate: sent L1 rate
                    ......
        return:   The statistic data of the retrieved items
        """
        try:
            if not streams:
                streams = list(self.stream_dict.keys())
            page_result = None
            stream_found = 0
            stats = {}
            # 判断配置文件中是否有streamblock统计视图
            page_list = self.sys_entry.get_children('PageResultView')
            for page in page_list:
                if page.DataClassName == 'StreamBlockStats':
                    page_result = page
            if not isinstance(page_result, PageResultView):
                raise Exception("找不到 Stream Block 统计视图!")
            # 获取统计
            page_result_query = page_result.get_children()[0]
            record_count = page_result.RecordCount
            record_per_page = page_result.RecordPerPage
            pages = int(ceil(record_count * 1.0 / record_per_page))
            # 翻页查找指定流的统计
            for i in range(pages):
                GotoResultPageCommand(ResultViewHandle=page_result.handle, PageNumber=i + 1).execute()
                time.sleep(3)
                stat_data = page_result_query.get_children()
                for data in stat_data:
                    if data.StreamBlockID in streams:
                        stream_found = 1
                        stream_data = {}
                        for item in kwargs:
                            key = f"_{item}"
                            if key in data.__dict__.keys():
                                stream_data.update({item: data.__dict__[key]})
                            else:
                                raise InvalidInputParam(f"[Renix] stream block统计不包括{item}统计项")
                        stats.update({data.StreamBlockID: stream_data})
                if stream_found != 1:
                    raise InvalidInputParam(f"[Renix] 统计视图里找不到流!")
            return stats
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 获取streamblock统计发生错误: {exception}")

    def get_stream_stat(self, stream, stream_id, kwargs) -> dict:
        """
        Object: 获取指定stream block的某个stream的统计项的值
        param stream: stream block名称
        param stream_id: stream block 预览中显示的stream ID
        param kwargs: 可变长度的统计项名称，可包括以下内容：
                    TxStreamFrames: sent packets count
                    RxStreamFrames: received packets count
                    TxFrameRate: sent packets rate
                    RxFrameRate: received packets rate
                    TxByteRate: sent byte rate
                    RxByteRate: received byte rate
                    RxSeqErr: received sequence error packets
                    RxPayloadErr: received Payload error packets
                    MinLatency: minimum latency
                    AvaLatency: average latency
                    MaxLatency: maximum latency
                    TxBitRate: send bit rate
                    RxBitRate: received bit rate
                    RxUtil: received utilization
                    MinJitter: minimum jitter(10ns)
                    AvaJitter: average jitter(10ns)
                    MaxJitter: maximum jitter(10ns)
                    RxL1Rate: received L1 rate
                    TxL1Rate: sent L1 rate
                    ......
        return:   The statistic data of the retrieved items
        """
        page_result = None
        stream_found = 0
        stats = {}
        try:
            # 判断配置文件中是否有stream统计视图
            page_list = self.sys_entry.get_children('PageResultView')
            for page in page_list:
                if page.DataClassName == 'StreamStats':
                    page_result = page
            if not isinstance(page_result, PageResultView):
                raise Exception("找不到 Stream 统计视图!")
            # 获取统计
            page_result_query = page_result.get_children()[0]
            record_count = page_result.RecordCount
            record_per_page = page_result.RecordPerPage
            pages = int(ceil(record_count * 1.0 / record_per_page))
            # 翻页查找指定流的统计
            for i in range(pages):
                GotoResultPageCommand(ResultViewHandle=page_result.handle, PageNumber=i + 1).execute()
                time.sleep(3)
                stat_data = page_result_query.get_children()
                for data in stat_data:
                    if data.StreamBlockID == stream and data.StreamID == stream_id:
                        stream_found = 1
                        for item in kwargs:
                            key = f"_{item}"
                            if key in data.__dict__.keys():
                                stats.update({item: data.__dict__[key]})
                            else:
                                raise InvalidInputParam(f"[Renix] stream 统计不包括{item}统计项")
            if stream_found != 1:
                raise InvalidInputParam(f"[Renix] 统计视图里找不到流：{stream}!")
            return stats
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 获取stream统计发生错误: {exception}")

    def check_arp(self, interface_list: [] = None):
        """
        Object: Send ARP of interface and check ARP status;
        :param interface_list: interface name;
        return: None
        """
        try:
            if interface_list:
                for intf in interface_list:
                    StartArpCommand(InterfaceConfigs=self.interface_dict[intf].handle, WaitLearningDone=True).execute()
            else:
                StartAllArpCommand(WaitLearningDone=True).execute()
            log.info(f"[Renix] 发送arp完成")
        except Exception as exception:
            log.error(f"[Renix] interface发送ARP发生错误: {exception}")

    def check_stream_arp(self, stream_list: [] = None):
        """
        Object: Send ARP of stream and check ARP status;
        :param stream_list: stream name;
        return: None
        """
        try:
            if stream_list:
                for stream in stream_list:
                    StartStreamArpCommand(StreamHandles=self.stream_dict[stream].handle).execute()
            else:
                StartAllStreamArpCommand().execute()
            log.info(f"[Renix] {stream_list}发送arp完成")
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 流发送ARP发生错误: {exception}")

    def get_ipv4_mac(self, interface) -> list:
        """
        获取interface的ipv4 resolved mac
        :param interface:
        :return:
        """
        try:
            interface_obj = self.interface_dict[interface]
            ipv4_layer = interface_obj.get_children('Ipv4Layer')[0]
            return ipv4_layer.ResolvedMacList
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 获取{interface}的resolved MAC发生错误: {exception}")

    def get_ipv6_mac(self, interface) -> list:
        """
        获取interface的ipv6 resolved mac
        :param interface:
        :return:
        """
        try:
            interface_obj = self.interface_dict[interface]
            ipv6_layer = interface_obj.get_children('Ipv6Layer')[0]
            return ipv6_layer.ResolvedMacList
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 获取{interface}的resolved MAC发生错误: {exception}")

    def get_ipv4_mac_state(self, interface) -> list:
        """
        获取interface的ipv4 resolved mac状态
        :param interface:
        :return:
        """
        try:
            interface_obj = self.interface_dict[interface]
            ipv4_layer = interface_obj.get_children('Ipv4Layer')[0]
            return ipv4_layer.GatewayMacResolveState
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 获取{interface}的resolved MAC发生错误: {exception}")

    def start_stream(self, stream_list: [] = None):
        """
        开始发送流量
        :param stream_list:
        :return:
        """
        stream_handle_list = []
        try:
            if stream_list:
                for stream in stream_list:
                    if stream not in self.stream_dict.keys():
                        raise InvalidInputParam(f"[Renix] 流{stream}不存在！")
                    stream_handle_list.append(self.stream_dict[stream].handle)
                if stream_handle_list:
                    StartStreamCommand(StreamList=stream_handle_list).execute()
                    log.info(f"[Renix] 流量{stream_list}开始发送...")
            else:
                StartAllStreamCommand().execute()
                log.info(f"[Renix] 所有流量开始发送...")
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 发送流发生错误: {exception}")

    def stop_stream(self, stream_list: [] = None):
        """
        停止发送流量
        :param stream_list:
        :return:
        """
        stream_handle_list = []
        try:
            if stream_list:
                for stream in stream_list:
                    if stream not in self.stream_dict.keys():
                        raise InvalidInputParam(f"[Renix] 流{stream}不存在！")
                    stream_handle_list.append(self.stream_dict[stream].handle)
                if stream_handle_list:
                    StopStreamCommand(StreamList=stream_handle_list).execute()
            else:
                StopAllStreamCommand().execute()
            log.info(f"[Renix] 流量停止发送...")
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 停止流发生错误: {exception}")

    def clear_all_results(self):
        """
        Object: 清空所有统计
        """
        result_view = self.sys_entry.get_children('PageResultView')
        result_view_handle = [x.handle for x in result_view]
        ClearResultCommand(ResultViewHandles=result_view_handle).execute()
        time.sleep(3)

    def ping_ipv4(self, interface, dst_ip, count) -> bool:
        """
        ping ipv4
        :param interface:
        :param dst_ip:
        :param count:
        :return:
        """
        interface_obj = self.interface_dict[interface]
        try:
            StartIpv4PingCommand(InterfaceHandle=interface_obj.handle, FrameCount=count, CustomIP=dst_ip).execute()
            time.sleep(count + 2)
            result = str(self.sys_entry.get_children('Ipv4PingConfig')[0].PingStatus)
            receive = int(re.findall(r'Received Packets: ' + '(.*)' + ' lost: 0', result)[0])
            return receive == count
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] ping发生错误: {exception}")

    def ping_ipv6(self, interface, dst_ip, count) -> bool:
        """
        ping ipv6
        :param interface:
        :param dst_ip:
        :param count:
        :return:
        """
        interface_obj = self.interface_dict[interface]
        try:
            StartIpv6PingCommand(InterfaceHandle=interface_obj.handle, FrameCount=count, CustomIP=dst_ip).execute()
            time.sleep(count + 2)
            result = str(self.sys_entry.get_children('Ipv6PingConfig')[0].PingStatus)
            receive = int(re.findall(r'Received Packets: ' + '(.*)' + ' lost: 0', result)[0])
            return receive == count
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] ping发生错误: {exception}")

    def start_capture(self, *ports):
        """
        开始捕获
        :param ports:
        :return:
        """
        if not ports:
            ports = list(self.port_dict.keys())
        try:
            for port in ports:
                port_obj = self.port_dict[port]
                capture = port_obj.get_children('CaptureConfig')[0]
                StartCaptureCommand(CaptureConfigs=capture.handle).execute()
            log.info(f"[Renix] {ports}开始抓包...")
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 开始捕获发生错误: {exception}")

    def stop_capture(self, *ports):
        """
        停止捕获
        :param ports:
        :return:
        """
        if not ports:
            ports = list(self.port_dict.keys())
        try:
            for port in ports:
                port_obj = self.port_dict[port]
                capture = port_obj.get_children('CaptureConfig')[0]
                StopCaptureCommand(CaptureConfigs=capture.handle).execute()
            time.sleep(3)
            log.info(f"[Renix] {ports}停止抓包...")
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] 开始捕获发生错误: {exception}")

    def download_pkt(self, port, file_dir, count=0):
        """
        下载报文
        :param port:
        :param file_dir:
        :param count:
        :return:
        """
        try:
            port_obj = self.port_dict[port]
            cap = port_obj.get_children('CaptureConfig')[0]
            download_cap_data_cmd = DownloadCaptureDataCommand(CaptureConfigs=cap.handle, FileDir=file_dir,
                                                               FileName=f'test{count}.pcap', MaxDownloadDataCount=count)
            download_cap_data_cmd.execute()
            # 确保足够的时间下载报文；count==0，说明所有报文全部下载
            download_time = 300 if count == 0 else (count / 10000 + 10)
            time.sleep(download_time)
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] {port}下载报文发生错误: {exception}")

    def get_pkt_data(self, port, idx) -> str:
        """
        获取某个报文的内容
        :param port:
        :param idx:
        :return:
        """
        try:
            port_obj = self.port_dict[port]
            cap = port_obj.get_children('CaptureConfig')[0]
            get_cap_data_by_index_cmd = GetCaptureDataByIndexCommand(CaptureConfig=cap.handle, Index=idx)
            get_cap_data_by_index_cmd.execute()
            data = get_cap_data_by_index_cmd.Data.replace(' ', '')
            return data
        except Exception as exception:
            raise InvalidInputParam(f"[Renix] {port}获取报文内容发生错误: {exception}")


class RenixTool:

    def __init__(self):
        self.renix_api = RenixApi()

    def add_chassis_connect(self):
        """
        连接机框
        :return:
        """
        self.renix_api.connect_chassis()

    def reserve_ports(self, port_list: [] = None) -> list:
        """
        预约端口
        :param port_list: //172.17.30.101/2/7格式的端口组成的列表，或者空列表
        :return:预约成功的端口的名称列表
        """
        return self.renix_api.reserve_ports(port_list)

    def add_interface(self, port: str = "", vlan: bool = False, ipv4: bool = False, ipv6: bool = False, count: int = 1) -> list:
        """
        添加接口
        :param count:
        :param port:
        :param vlan:
        :param ipv4:
        :param ipv6:
        :return:
        usage: add_interface(ipv4=True)
               add_interface(port_1, vlan=True, ipv6=True)
        Note: 假如有两个port，count设置为2，返回的interface列表里的顺序如下：
              port1 interface1, port2 interface1, port1 interface2, port2 interface2
        """
        # 将参数转换为 api 接口可识别的封装
        network_layer = 'eth'
        top_layers = []
        if vlan:
            network_layer = 'vlan'
        if ipv4:
            top_layers.append('ipv4')
        if ipv6:
            top_layers.append('ipv6')
        # 调用添加接口的api
        interface_list = []
        for i in range(count):
            if port:
                interface_list += self.renix_api.build_interface(network_layer, top_layers, [port])
            else:
                interface_list += self.renix_api.build_interface(network_layer, top_layers)
        return interface_list

    def add_2vlan_ipv4_interface(self, port: str = ''):
        if port:
            return self.renix_api.build_interface('vlan vlan', ['ipv4'], [port])
        else:
            return self.renix_api.build_interface('vlan vlan', ['ipv4'])

    def add_2vlan_ipv6_interface(self, port: str = ''):
        if port:
            return self.renix_api.build_interface('vlan vlan', ['ipv6'], [port])
        else:
            return self.renix_api.build_interface('vlan vlan', ['ipv6'])

    def add_ipv4_binding_stream(self, src, dst, bidirection=True) -> list:
        """
        添加ipv4绑定流，包括vlan+ipv4
        :param src:
        :param dst:
        :param bidirection:
        :return:
        usage: add_ipv4_binding_stream(interface_1, interface_2)
        """
        src_layer = self.renix_api.interface_dict[src].get_children('Ipv4Layer')[0]
        dst_layer = self.renix_api.interface_dict[dst].get_children('Ipv4Layer')[0]
        return self.renix_api.create_binding_stream(src_layer, dst_layer, bidirection)

    def add_ipv6_binding_stream(self, src, dst, bidirection=True) -> list:
        """
        添加ipv6绑定流，包括vlan+ipv6
        :param src:
        :param dst:
        :param bidirection:
        :return:
        """
        src_layer = self.renix_api.interface_dict[src].get_children('Ipv6Layer')[0]
        dst_layer = self.renix_api.interface_dict[dst].get_children('Ipv6Layer')[0]
        return self.renix_api.create_binding_stream(src_layer, dst_layer, bidirection)

    def add_raw_stream(self, port, stream_type) -> str:
        """
        添加raw流，需自己指定基础报文类型；如果在此基础上需要增加其他头部，使用 add_header
        :param port:
        :param stream_type:
        :return:
        usage: add_raw_stream(port_2, 'sctp4')
        """
        # 辅助测试使用，查看支持的header 列表
        # list_header_type_cmd = ListHeaderTypesCommand()
        # list_header_type_cmd.execute()
        # print(list_header_type_cmd.__dict__)
        headers = []
        if stream_type == '8023':
            headers = ['Ethernet.8023']
        elif stream_type == '8023_ipv4':
            headers = ['Ethernet.8023', 'IPv4.ipv4']
        elif stream_type == '8023_ipv6':
            headers = ['Ethernet.8023', 'IPv6.ipv6']
        elif stream_type == '8023_vlan_ipv4':
            headers = ['Ethernet.8023', 'VLAN.vlan', 'IPv4.ipv4']
        elif stream_type == '8023_dvlan_ipv4':
            headers = ['Ethernet.8023', 'VLAN.vlan', 'VLAN.vlan', 'IPv4.ipv4']
        elif stream_type == 'ether':
            headers = ['Ethernet.ethernetII']
        elif stream_type == 'arp':
            headers = ['Ethernet.ethernetII', 'ARP.arp']
        elif stream_type == 'ether_vlan':
            headers = ['Ethernet.ethernetII', 'VLAN.vlan']
        elif stream_type == 'pppoe':
            headers = ['Ethernet.ethernetII', 'PPPoE.pppoe', 'PPP.ppp']
        elif stream_type == 'vlan_pppoe':
            headers = ['Ethernet.ethernetII', 'VLAN.vlan', 'PPPoE.pppoe', 'PPP.ppp']
        elif stream_type == 'ipv4':
            headers = ['Ethernet.ethernetII', 'IPv4.ipv4']
        elif stream_type == 'ipv6':
            headers = ['Ethernet.ethernetII', 'IPv6.ipv6']
        elif stream_type == 'vlan+ipv4':
            headers = ['Ethernet.ethernetII', 'VLAN.vlan', 'IPv4.ipv4']
        elif stream_type == 'vlan+ipv6':
            headers = ['Ethernet.ethernetII', 'VLAN.vlan', 'IPv6.ipv6']
        elif stream_type == 'udp4':
            headers = ['Ethernet.ethernetII', 'IPv4.ipv4', 'UDP.udp']
        elif stream_type == 'udp6':
            headers = ['Ethernet.ethernetII', 'IPv6.ipv6', 'UDP.udp']
        elif stream_type == 'tcp4':
            headers = ['Ethernet.ethernetII', 'IPv4.ipv4', 'TCP.tcp']
        elif stream_type == 'tcp6':
            headers = ['Ethernet.ethernetII', 'IPv6.ipv6', 'TCP.tcp']
        elif stream_type == 'sctp4':
            headers = ['Ethernet.ethernetII', 'IPv4.ipv4', 'Sctp.sctp']
        elif stream_type == 'sctp6':
            headers = ['Ethernet.ethernetII', 'IPv6.ipv6', 'Sctp.sctp']
        elif stream_type == 'icmp4':
            headers = ['Ethernet.ethernetII', 'IPv4.ipv4', 'ICMPv4.icmpv4EchoRequest']
        elif stream_type == 'icmp6':
            headers = ['Ethernet.ethernetII', 'IPv6.ipv6', 'ICMPv6.icmpv6EchoRequest']
        elif stream_type == 'l2tp_ctl':
            headers = ['Ethernet.ethernetII', 'IPv4.ipv4', 'UDP.udp', 'L2TPv2.l2tpv2Control']
        elif stream_type == 'l2tp_data':
            headers = ['Ethernet.ethernetII', 'IPv4.ipv4', 'UDP.udp', 'L2TPv2.l2tpv2Data', 'PPP.ppp']
        elif stream_type == 'l2tpv3_ctl_over_udp':
            headers = ['Ethernet.ethernetII', 'IPv4.ipv4', 'UDP.udp', 'L2TPv3.l2tpv3ControlOverUdp']
        elif stream_type == 'l2tpv3_ctl_over_ip':
            headers = ['Ethernet.ethernetII', 'IPv4.ipv4', 'L2TPv3.l2tpv3ControlOverIp']
        elif stream_type == 'l2tpv3_data_over_udp':
            headers = ['Ethernet.ethernetII', 'IPv4.ipv4', 'UDP.udp', 'L2TPv3.l2tpv3DataOverUdp', 'PPP.ppp']
        elif stream_type == 'l2tpv3_data_over_ip':
            headers = ['Ethernet.ethernetII', 'IPv4.ipv4', 'L2TPv3.l2tpv3DataOverIp', 'PPP.ppp']
        else:
            raise InvalidInputParam(f"[Renix] 不支持输入的报文头{stream_type}")
        return self.renix_api.create_stream(port, headers)

    def add_header(self, stream, stream_header):
        """
        添加报文头
        :param stream:
        :param stream_header:
        :return:
        usage: add_header(stream_3, 'icmpv6')
        """
        headers = []
        if stream_header == 'eth':
            headers = ['Ethernet.ethernetII']
        elif stream_header == 'vlan':
            headers = ['VLAN.vlan']
        elif stream_header == 'mpls':
            headers = ['MPLS.mpls']
        elif stream_header == 'ipv4':
            headers = ['IPv4.ipv4']
        elif stream_header == 'ipv6':
            headers = ['IPv6.ipv6']
        elif stream_header == 'icmp':
            headers = ['ICMPv4.icmpv4EchoReply']
        elif stream_header == 'icmpv6':
            headers = ['ICMPv6.icmpv6EchoRequest']
        elif stream_header == 'redirect':
            headers = ['ICMPv6.icmpv6Redirect']
        elif stream_header == 'ra':
            headers = ['ICMPv6.routerAdvertise']
        elif stream_header == 'ns':
            headers = ['ICMPv6.neighborSolicit']
        elif stream_header == 'na':
            headers = ['ICMPv6.neighborAdvertise']
        elif stream_header == 'rs':
            headers = ['ICMPv6.routerSolicit']
        elif stream_header == 'mldv1_query':
            headers = ['ICMPv6.mldv1Query']
        elif stream_header == 'mldv1_report':
            headers = ['ICMPv6.mldv1Report']
        elif stream_header == 'mld_done':
            headers = ['ICMPv6.mldv1Done']
        elif stream_header == 'mldv2_query':
            headers = ['ICMPv6.mldv2Query']
        elif stream_header == 'mldv2_report':
            headers = ['ICMPv6.mldv2Report']
        elif stream_header == 'tcp':
            headers = ['TCP.tcp']
        elif stream_header == 'udp':
            headers = ['UDP.udp']
        elif stream_header == 'sctp':
            headers = ['Sctp.sctp']
        elif stream_header == 'gre':
            headers = ['GRE.gre']
        elif stream_header == 'custom':
            headers = ['Custom.custom']
        elif stream_header == 'vxlan':
            headers = ['UDP.udp', 'VXLAN.vxlan']
        elif stream_header == 'rocev2':
            headers = ['UDP.udp', 'Rocev2.rocev2']
        elif stream_header == 'fragment':
            headers = ['IPv6.ipv6FragmentHeader']
        elif stream_header == 'eth_ipv4':
            headers = ['Ethernet.ethernetII', 'IPv4.ipv4']
        elif stream_header == 'eth_vlan_ipv4':
            headers = ['Ethernet.ethernetII', 'VLAN.vlan', 'IPv4.ipv4']
        elif stream_header == 'eth_dvlan_ipv4':
            headers = ['Ethernet.ethernetII', 'VLAN.vlan', 'VLAN.vlan', 'IPv4.ipv4']
        elif stream_header == 'eth_ipv6':
            headers = ['Ethernet.ethernetII', 'IPv6.ipv6']
        elif stream_header == 'eth_vlan_ipv6':
            headers = ['Ethernet.ethernetII', 'VLAN.vlan', 'IPv6.ipv6']
        elif stream_header == 'eth_dvlan_ipv6':
            headers = ['Ethernet.ethernetII', 'VLAN.vlan', 'VLAN.vlan', 'IPv6.ipv6']
        elif stream_header == 'gtpv1':
            headers = ['UDP.udp', 'GTPv1.gtpv1']
        elif stream_header == 'l2tpv2_data':
            headers = ['UDP.udp', 'L2TPv2.l2tpv2Data', 'PPP.ppp']
        elif stream_header == 'l2tpv3_data':
            headers = ['L2TPv3.l2tpv3DataOverIp', 'PPP.ppp']
        elif stream_header == 'udp_l2tpv3_data':
            headers = ['UDP.udp', 'L2TPv3.l2tpv3DataOverUdp', 'PPP.ppp']
        elif stream_header == 'rip':
            headers = ['RIP.ripv2']
        elif stream_header == 'igmp':
            headers = ['IGMP.igmpv2']
        else:
            raise InvalidInputParam(f"[Renix] 不支持输入的报文头{stream_header}")

        for header in headers:
            self.renix_api.insert_stream_header(stream, header)

    def add_modifier(self, stream, header, field, modifier_type, **kwargs) -> bool:
        """
        创建一个modifier，并将该modifier添加到报文头的某个字段
        :param stream:
        :param header:
        :param field:
        :param modifier_type:
        :param kwargs:
        :return:
        usage: add_modifier(stream_3, 'ipv4_1', 'dst', 'Increment', Start='1.1.1.1', Count=20, Step=1)
               add_modifier(stream_3, 'ethernetII_1', 'source', 'Increment', Start='00:00:00:13:40:ab',
                            Count=20, Step=1, Offset=1)
        """
        modifier = self.renix_api.create_modifier(modifier_type, **kwargs)
        if 'udp' in header or 'tcp' in header:
            if field == 'src':
                return self.renix_api.edit_stream_header(stream, 0, header, sourcePort=modifier)
            elif field == 'dst':
                return self.renix_api.edit_stream_header(stream, 0, header, destPort=modifier)
            elif field == 'checksum':
                return self.renix_api.edit_stream_header(stream, 0, header, checksum=modifier)
        elif 'sctp' in header:
            if field == 'src':
                return self.renix_api.edit_stream_node(stream, 0, header, 'header', sourcePort=modifier)
            elif field == 'dst':
                return self.renix_api.edit_stream_node(stream, 0, header, 'header', destPort=modifier)
        elif 'ip' in header:
            if field == 'src':
                return self.renix_api.edit_stream_header(stream, 0, header, source=modifier)
            elif field == 'dst':
                return self.renix_api.edit_stream_header(stream, 0, header, destination=modifier)
        elif 'eth' in header:
            if field == 'src':
                return self.renix_api.edit_stream_header(stream, 0, header, sourceMacAdd=modifier)
            elif field == 'dst':
                return self.renix_api.edit_stream_header(stream, 0, header, destMacAdd=modifier)
        elif 'vlan' in header:
            if field == 'id':
                return self.renix_api.edit_stream_header(stream, 0, header, id=modifier)
            elif field == 'priority':
                return self.renix_api.edit_stream_header(stream, 0, header, priority=modifier)

    def check_env(self, stream_list: [] = None) -> bool:
        """
        测试之前检查环境是否妥当，且可以在开始正式测试之前先让OS学习路由表，防止正式测试丢包
        :param stream_list:
        :return:
        """
        self.renix_api.check_arp()
        self.start_stop_stream(stream_list, set_time=5)
        loss_pkt, loss_rate = self.get_loss(stream_list)
        if all(value < 10 for value in loss_rate.values()):
            flag = True
        else:
            flag = False
        self.clear_result()
        return flag

    # def create_modifier(self, modifier_type, **kwargs) -> list:
    #     """
    #     创建一个跳变
    #     :param modifier_type:
    #     :param kwargs:
    #     :return:
    #     Usage： create_modifier('Increment', StreamType='IntraModifier', Start=1, Count=20, Step=1)
    #             create_modifier('Random', StreamType='InterModifier', Start=1, Count=20, Range=1000)
    #             create_modifier('List', StreamType='InterModifier', List=['1.1.1.2', '1.1.1.3'])
    #     """
    #     return self.renix_api.create_modifier(modifier_type, **kwargs)

    def del_header(self, stream, header) -> bool:
        """
        删除报文头
        :param stream:
        :param header:
        :return:
        """
        return self.renix_api.delete_stream_header(stream, header)

    def edit_interface(self, interface, kwargs: dict) -> bool:
        """
        修改interface参数
        :param interface:
        :param kwargs:
        :return:
        usage: edit_interface(interface, {"count": 100, "ipv4_addr": "192.1.1.10"})
        """
        basic = {}
        eth = {}
        vlan = {}
        vlan_2 = {}
        ipv4 = {}
        ipv6 = {}
        result_list = []
        for item, value in kwargs.items():
            if item == 'count':
                basic['Count'] = value

            elif item == 'mac_addr':
                eth['Address'] = value
            elif item == 'mac_step':
                eth['Step'] = value

            elif item == 'vlan_id':
                vlan['VlanId'] = value
            elif item == 'vlan_pri':
                vlan['Priority'] = value
            elif item == 'vlan_step':
                vlan['Step'] = value

            elif item == 'vlan2_id':
                vlan_2['VlanId'] = value
            elif item == 'vlan2_pri':
                vlan_2['Priority'] = value
            elif item == 'vlan2_step':
                vlan_2['Step'] = value

            elif item == 'ipv4_addr':
                ipv4['Address'] = value
            elif item == 'ipv4_step':
                ipv4['Step'] = value
            elif item == 'ipv4_gateway':
                ipv4['Gateway'] = value
            elif item == 'ipv4_prefix':
                ipv4['PrefixLength'] = value
            elif item == 'ipv4_gateway_step':
                ipv4['GatewayStep'] = value

            elif item == 'ipv6_addr':
                ipv6['Address'] = value
            elif item == 'ipv6_step':
                ipv6['Step'] = value
            elif item == 'ipv6_gateway':
                ipv6['Gateway'] = value
            elif item == 'ipv6_prefix':
                ipv6['PrefixLength'] = value
            elif item == 'ipv6_gateway_step':
                ipv6['GatewayStep'] = value

            else:
                raise InvalidInputParam(f"[Renix] 编辑interface，未知的参数: {item}")
            # match item:
            #     case 'count':
            #         basic['Count'] = value
            # 
            #     case 'mac_addr':
            #         eth['Address'] = value
            #     case 'mac_step':
            #         eth['Step'] = value
            # 
            #     case 'vlan_id':
            #         vlan['VlanId'] = value
            #     case 'vlan_pri':
            #         vlan['Priority'] = value
            #     case 'vlan_step':
            #         vlan['Step'] = value
            # 
            #     case 'vlan2_id':
            #         vlan_2['VlanId'] = value
            #     case 'vlan2_pri':
            #         vlan_2['Priority'] = value
            #     case 'vlan2_step':
            #         vlan_2['Step'] = value
            # 
            #     case 'ipv4_addr':
            #         ipv4['Address'] = value
            #     case 'ipv4_step':
            #         ipv4['Step'] = value
            #     case 'ipv4_gateway':
            #         ipv4['Gateway'] = value
            #     case 'ipv4_prefix':
            #         ipv4['PrefixLength'] = value
            #     case 'ipv4_gateway_step':
            #         ipv4['GatewayStep'] = value
            # 
            #     case 'ipv6_addr':
            #         ipv6['Address'] = value
            #     case 'ipv6_step':
            #         ipv6['Step'] = value
            #     case 'ipv6_gateway':
            #         ipv6['Gateway'] = value
            #     case 'ipv6_prefix':
            #         ipv6['PrefixLength'] = value
            #     case 'ipv6_gateway_step':
            #         ipv6['GatewayStep'] = value
            # 
            #     case _:
            #         raise InvalidInputParam(f"[Renix] 编辑interface，未知的参数: {item}")
        result_list.append(self.renix_api.update_interface(interface, 'basic', **basic) if basic else True)
        result_list.append(self.renix_api.update_interface(interface, 'eth', **eth) if eth else True)
        result_list.append(self.renix_api.update_interface(interface, 'vlan', **vlan) if vlan else True)
        result_list.append(self.renix_api.update_interface(interface, 'vlan_2', **vlan_2) if vlan_2 else True)
        result_list.append(self.renix_api.update_interface(interface, 'ipv4', **ipv4) if ipv4 else True)
        result_list.append(self.renix_api.update_interface(interface, 'ipv6', **ipv6) if ipv6 else True)
        # 如果有修改参数失败的情况，返回False；否则返回True；测试用例开发者自行决定是否继续测试
        log.info(f"[Renix] 更新接口{interface}完成")
        return all(result_list)

    def edit_port_config(self, port, kwargs: dict) -> bool:
        """
        修改端口参数
        :param port:
        :param kwargs:
        :return:
        usage: edit_port_config(port_2, {"FlowControl": "ENABLE"})
        """
        return self.renix_api.update_port_config(port, kwargs)

    def edit_port_flow_control(self, port, state) -> bool:
        """
        设置端口的流控状态
        :param port:
        :param state:
        :return:
        usage: edit_port_flow_control(port_1, "ENABLE")
        """
        port_config = {'FlowControl': state}
        return self.renix_api.update_port_config(port, port_config)

    def edit_port_generate_error(self, port, err_type) -> bool:
        """
        设置端口的错误类型
        :param port:
        :param err_type:
        :return:
        usage: edit_port_generate_error(port_1, 'CRC')
               edit_port_generate_error(port_1, 'NO_ERROR')
        """
        if err_type == 'CRC':
            return self.renix_api.update_port_schedule(port, GenerateError=EnumErrorGen.CRC)
        else:
            return self.renix_api.update_port_schedule(port, GenerateError=EnumErrorGen.NO_ERROR)

    def edit_port_load(self, port, load_value, load_unit: str = '') -> bool:
        """
        设置端口的速率
        :param port:
        :param load_value:
        :param load_unit:
        :return:
        usage: edit_port_load(port_1, 1000, 'pps')
               edit_port_load(port_1, 100)
        """
        # 先设置单位
        if load_unit == 'percent':
            self.renix_api.update_port_schedule(port, Unit='PERCENT')
        elif load_unit == 'pps':
            self.renix_api.update_port_schedule(port, Unit='FRAME_PER_SEC')
        elif load_unit == 'mbps':
            self.renix_api.update_port_schedule(port, Unit='MLINEBIT_PER_SEC')
        elif load_unit == 'IFG':
            self.renix_api.update_port_schedule(port, Unit='INTER_FRAME_GAP_BYTE')
        elif load_unit == '':
            log.info(f"[Renix] {port}使用默认带宽单位")
        else:
            raise InvalidInputParam(f"[Renix] 暂不支持设置速率带宽为{load_unit}")
        # match load_unit:
        #     case 'percent':
        #         self.renix_api.update_port_schedule(port, Unit='PERCENT')
        #     case 'pps':
        #         self.renix_api.update_port_schedule(port, Unit='FRAME_PER_SEC')
        #     case 'mbps':
        #         self.renix_api.update_port_schedule(port, Unit='MLINEBIT_PER_SEC')
        #     case 'IFG':
        #         self.renix_api.update_port_schedule(port, Unit='INTER_FRAME_GAP_BYTE')
        #     case '':
        #         log.info(f"[Renix] {port}使用默认带宽单位")
        #     case _:
        #         raise InvalidInputParam(f"[Renix] 暂不支持设置速率带宽为{load_unit}")
        # 再设置速率
        return self.renix_api.update_port_schedule(port, Rate=load_value)

    def edit_port_load_type(self, port, load_type) -> bool:
        """
        设置端口调速的模式
        :param port:
        :param load_type:
        :return:
        usage: edit_port_load_type(port_2, 'stream')
        """
        if load_type == 'port':
            return self.renix_api.update_port_schedule(port, LoadProfileType=EnumLoadProfileType.PORT_BASE)
        elif load_type == 'stream':
            return self.renix_api.update_port_schedule(port, LoadProfileType=EnumLoadProfileType.STREAM_BASE)
        else:
            raise InvalidInputParam(f"[Renix] 不支持load type为{load_type}")

    def edit_port_continuous(self, port) -> bool:
        """
        设置端口为continuous发送模式
        :param port:
        :return:
        """
        return self.renix_api.update_port_schedule(port, TransmitMode=EnumTransmitMode.CONTINUOUS)

    def edit_port_burst(self, port, frames_per_burst, bursts=1, gap=12, gap_unit='bytes') -> bool:
        """
        设置端口为burst发送模式，同时设置burst的报文数等信息
        :param port:
        :param frames_per_burst:
        :param bursts:
        :param gap:
        :param gap_unit:
        :return:
        usage: edit_port_burst(port_1, 10000, 3)
               edit_port_burst(port_1, 10000)
        """
        return self.renix_api.update_port_schedule(port, TransmitMode=EnumTransmitMode.BURST, BurstCount=bursts,
                                                   FramePerBurst=frames_per_burst, BurstGapUnit=gap_unit, BurstGap=gap)

    def edit_port_time(self, port, burst_time) -> bool:
        """
        设置端口为时间突发模式，并设置发送时间
        :param port:
        :param burst_time:
        :return:
        """
        return self.renix_api.update_port_schedule(port, TransmitMode=EnumTransmitMode.TIME, Seconds=burst_time)

    def edit_port_on_stream(self, port) -> bool:
        """
        设置端口为基于流的突发模式
        :param port:
        :return:
        """
        return self.renix_api.update_port_schedule(port, TransmitMode=EnumTransmitMode.ONSTREAM)

    def edit_stream(self, stream, **kwargs) -> bool:
        """
        编辑流的通用参数
        :param stream:
        :param kwargs:
        :return:
        usage: edit_stream(stream_1, FrameLengthType='INCREMENT', MinLength=100, MaxLength=512)
        """
        return self.renix_api.edit_stream(stream, **kwargs)

    def edit_stream_header(self, stream, header, **kwargs) -> bool:
        """
        修改报文头
        :param stream:
        :param header:
        :param kwargs:
        :return:
        usage: edit_stream_header(stream_1, 'ipv4_1', destination='33.33.3.3')
               edit_stream_header(stream_3, 'ipv4_2', checksum='FFFF')  # checksum造错
               edit_stream_header(stream_1, 'ethernetII_1', destMacAdd=self.nic_p1_mac, protocolType='002E')
        """
        return self.renix_api.edit_stream_header(stream, 0, header, **kwargs)

    def edit_stream_load(self, stream, load_value, load_unit: str = '') -> bool:
        """
        设置某条流的带宽
        :param stream:
        :param load_value:
        :param load_unit:
        :return:
        usage: edit_stream_load(stream_2, 20)
        """
        # 先设置单位
        if load_unit == 'percent':
            self.renix_api.update_stream_load(stream, Unit='PERCENT')
        elif load_unit == 'pps':
            self.renix_api.update_stream_load(stream, Unit='FRAME_PER_SEC')
        elif load_unit == 'mbps':
            self.renix_api.update_stream_load(stream, Unit='MLINEBIT_PER_SEC')
        elif load_unit == 'IFG':
            self.renix_api.update_stream_load(stream, Unit='INTER_FRAME_GAP_BYTE')
        elif load_unit == '':
            log.info(f"[Renix] {stream}使用默认带宽单位")
        else:
            raise InvalidInputParam(f"[Renix] 暂不支持设置速率带宽为{load_unit}")
        # 再设置速率
        return self.renix_api.update_stream_load(stream, Rate=load_value)

    def edit_stream_burst(self, stream, frames_per_burst, bursts=1, gap=12, gap_unit='us'):
        """
        设置流为burst发送模式，且设置burst参数
        :param stream:
        :param frames_per_burst:
        :param bursts:
        :param gap:
        :param gap_unit: ns，us，ms，sec
        :return:
        usage: renix.edit_stream_burst(stream, 1000)
            需先设置端口的发送模式和调速模式为on stream：
            renix.edit_port_load_type(port_1, 'stream')
            renix.edit_port_on_stream(port_1)
        """
        return self.renix_api.update_stream_sche(stream, StreamTransmitMode=EnumTransmitMode.BURST, BurstCount=bursts,
                                                    FramePerBurst=frames_per_burst, BurstGapUnit=gap_unit, BurstGap=gap)

    def edit_stream_continuous(self, stream):
        """
        设置流为continuous发送模式
        :param stream:c
        :return:
        usage: renix.edit_stream_continuous(stream)
        """
        return self.renix_api.update_stream_sche(stream, StreamTransmitMode=EnumTransmitMode.CONTINUOUS)

    def edit_stream_ipv4_dscp(self, stream, header, value: int):
        """
        编辑ipv4 header 的dscp值
        :param stream:
        :param header:
        :param value: 十进制值
        :return:
        """
        binary_value = format(value, '06b')
        self.edit_stream_header(stream, header, **{'tos.diffServe.dscp.codePoint.precedence': binary_value})

    def edit_stream_ipv4_tos_byte(self, stream, header, value: int):
        """
        编辑ipv4 header 的tos值
        :param stream:
        :param header:
        :param value: 十进制值
        :return:
        未经调试
        """
        hex_value = format(value, 'x')
        self.edit_stream_header(stream, header, **{'tos.data': hex_value})

    def edit_stream_ipv4_dscp_modifier(self, stream, header, start: int, count: int, step: int = 1):
        """
        编辑ipv4 header 的dscp值，添加一个跳变
        :param stream:
        :param header:
        :param start: DSCP的十进制值，非整个traffic class
        :param count:
        :param step:
        :return:
        :usage: cls.renix.edit_stream_ipv4_dscp_modifier(stream, 'ipv4_1', 1, 7, 1)
        """
        binary_value = format(start, '06b')
        modifier = self.renix_api.create_modifier('Increment', Start=binary_value, Count=count, Step=step)
        self.edit_stream_header(stream, header, **{'tos.diffServe.dscp.codePoint.precedence': modifier})

    def edit_stream_ipv6_dscp(self, stream, header, value: int):
        """
        编辑ipv6 header 的dscp值
        :param stream:
        :param header:
        :param value: 十进制值
        :return:
        """
        self.edit_stream_header(stream, header, trafficClass=value * 4)

    def edit_stream_ipv6_tc(self, stream, header, value: int):
        """
        编辑ipv6 header 的traffic class值
        :param stream:
        :param header:
        :param value: 十进制值
        :return:
        """
        self.edit_stream_header(stream, header, trafficClass=value)

    def edit_stream_ipv6_dscp_modifier(self, stream, header, start: int, count: int, step: int = 1):
        """
        编辑ipv6 header 的dscp值，添加一个跳变
        :param stream:
        :param header:
        :param start: DSCP的十进制值，非整个traffic class
        :param count:
        :param step:
        :return:
        :usage: cls.renix.edit_stream_ipv6_dscp_modifier(stream, 'ipv6_1', 7, 8, 2)
        """
        modifier = self.renix_api.create_modifier('Increment', Start=start * 4, Count=count, Step=step)
        self.edit_stream_header(stream, header, trafficClass=modifier)

    def insert_ipv4_node(self, stream, header, node) -> bool:
        """
        插入ipv4 option
        :param stream:
        :param header:
        :param node: optionLooseSourceRoute, optionStrictSourceRoute, optionEndOfOptionList, optionNop, optionSecurity,
                     optionRouterAlert, optionRecordRoute, optionTimeStamp, optionStreamIdentifier, generalTLV
        :return:
        usage: insert_ipv4_node(stream_3, 'ipv4_1', 'optionLooseSourceRoute')
        """
        node_upper = f'{header}.ipv4HeaderOption'
        return self.renix_api.insert_stream_node(stream, header, node_upper, node)

    def insert_ipv4_random_node(self, stream, header):
        nodes = ['optionLooseSourceRoute', 'optionStrictSourceRoute', 'optionSecurity',
                 'optionNop', 'optionRouterAlert', 'optionRecordRoute', 'optionTimeStamp', 'optionStreamIdentifier']
        count = random.randint(1, 5)
        node = random.choice(nodes)
        self.insert_ipv4_node(stream, header, node)
        if node == 'optionLooseSourceRoute':
            self.insert_ipv4_route_list(stream, 'loose', count)
        elif node == 'optionStrictSourceRoute':
            self.insert_ipv4_route_list(stream, 'strict', count)

    def insert_ipv4_nodes_40_bytes(self, stream, header):
        nodes = ['optionLooseSourceRoute', 'optionStrictSourceRoute', 'optionSecurity', 'optionStreamIdentifier',
                 'optionNop', 'optionRouterAlert', 'optionRecordRoute', 'optionTimeStamp', 'optionEndOfOptionList']
        nodes = ['optionLooseSourceRoute', 'optionStrictSourceRoute', 'optionSecurity', 'optionStreamIdentifier',
                 'optionRouterAlert', 'optionTimeStamp']
        for node in nodes:
            # 插入失败，底层接口未返回false，取消判断
            self.insert_ipv4_node(stream, header, node)
            if node == 'optionLooseSourceRoute':
                self.insert_ipv4_route_list(stream, 'loose', 1)
            elif node == 'optionStrictSourceRoute':
                self.insert_ipv4_route_list(stream, 'strict', 1)

    def insert_ipv4_nodes_36_bytes(self, stream, header):
        nodes = ['optionRecordRoute', 'optionStrictSourceRoute', 'optionSecurity', 'optionStreamIdentifier',
                 'optionRouterAlert', 'optionTimeStamp']
        for node in nodes:
            # 插入失败，底层接口未返回false，取消判断
            self.insert_ipv4_node(stream, header, node)
            if node == 'optionLooseSourceRoute':
                self.insert_ipv4_route_list(stream, 'loose', 1)
            elif node == 'optionStrictSourceRoute':
                self.insert_ipv4_route_list(stream, 'strict', 1)

    def insert_ipv4_nodes_28_bytes(self, stream, header):
        nodes = ['optionRecordRoute', 'optionSecurity', 'optionRouterAlert', 'optionTimeStamp']
        for node in nodes:
            # 插入失败，底层接口未返回false，取消判断
            self.insert_ipv4_node(stream, header, node)
            if node == 'optionLooseSourceRoute':
                self.insert_ipv4_route_list(stream, 'loose', 1)
            elif node == 'optionStrictSourceRoute':
                self.insert_ipv4_route_list(stream, 'strict', 1)

    def insert_ipv4_route_list(self, stream, route_type, count) -> bool:
        """
        ipv4 的 松散路由或者严格路由选项增加route节点
        :param stream:
        :param route_type:
        :param count:
        :return:
        usage: insert_ipv4_route_list(stream_3, 'loose', 3)
        """
        node_upper = ''
        result_list = []
        if route_type == 'loose':
            node_upper = 'ipv4_1.ipv4HeaderOption.ipv4HeaderOptionList_0.optionLooseSourceRoute.addressList'
        if route_type == 'strict':
            node_upper = 'ipv4_1.ipv4HeaderOption.ipv4HeaderOptionList_0.optionStrictSourceRoute.addressList'
        node = 'ipv4AddrContainer'
        for i in range(count):
            result_list.append(self.renix_api.insert_stream_node(stream, 'ipv4', node_upper, node))
            # 修改option中的address
            # self.renix_api.edit_stream_header(stream, 0, 'ipv4_1', **{'ipv4_1.ipv4HeaderOption.ipv4HeaderOptionList_0.optionLooseSourceRoute.addressList.ipv4AddrContainer_0.ipv4Addr': '1.1.1.1'})
        return all(result_list)

    def get_port_stats(self, port, item_list: [] = None) -> dict:
        """
        获取端口的统计
        :param port:
        :param item_list:
        :return:
        usage: get_port_stats(port, ['TxTotalFrames', 'RxTotalFrames'])
               get_port_stats(port)
        """
        if not item_list:
            item_list = ['TxTotalFrames', 'RxTotalFrames', 'TxStreamFrames', 'RxSignatureStreamFrames',
                         'TxFrameRate', 'RxFrameRate', 'RxUtil', 'RxL1Rate', 'TxL1Rate',
                         'RxIpv4ChecksumError', 'RxUdpChecksumError', 'RxTcpChecksumError', 'RxFCSErr',
                         'TxTotalBytes', 'RxTotalBytes', 'RxPauseFrames', 'RxUndersizeFrames']
        stats = self.renix_api.get_port_stat(port, item_list)
        log.info(f"[Renix] 测试仪 {port} 统计：{stats}")
        return stats

    def get_streamblock_stats(self, stream, item_list: [] = None) -> dict:
        """
        获取 stream block 的统计
        :param stream:
        :param item_list:
        :return:
        usage: get_streamblock_stats(stream_1, 'TxStreamFrames', 'RxStreamFrames')
        """
        if not item_list:
            item_list = ['TxStreamFrames', 'RxStreamFrames', 'MinLatency', 'AvaLatency', 'MaxLatency',
                         'TxFrameRate', 'RxFrameRate', 'RxL1Rate', 'TxL1Rate', 'RxUtil',
                         'RxPayloadErr', 'MinJitter', 'AvaJitter', 'MaxJitter']
        stats = self.renix_api.get_streamblock_stat(stream, item_list)
        log.info(f"[Renix] 测试仪 {stream} 统计：{stats}")
        return stats

    def get_multi_stream_stats(self, stream_list: [] = None, item_list: [] = None) -> dict:
        """
        获取 多个stream block 的统计
        :param stream_list:
        :param item_list:
        :return: 一个包含字典的字典；内部的字典是每条流的统计项和统计数据；外部的字典是流名称和内部字典
        usage: get_multi_stream_stats(stream_list)
               get_multi_stream_stats()
        """
        if not item_list:
            item_list = ['TxStreamFrames', 'RxStreamFrames', 'MinLatency', 'AvaLatency', 'MaxLatency',
                         'TxFrameRate', 'RxFrameRate', 'RxL1Rate', 'TxL1Rate', 'RxUtil',
                         'RxPayloadErr', 'MinJitter', 'AvaJitter', 'MaxJitter']
        stats = self.renix_api.get_streamblocks_stat(stream_list, item_list)
        log.info(f"[Renix] 测试仪流量统计：{stats}")
        return stats

    def get_loss(self, stream_list: [] = None) -> tuple:
        """
        计算每条流的丢包数和丢包率
        :param stream_list:
        :return: 每条流的丢包数
        usage: get_loss([stream_1])
               get_loss()
        """
        loss_pkt_dict = {}
        loss_rate_dict = {}
        if not stream_list:
            stream_list = list(self.renix_api.stream_dict.keys())
        for stream in stream_list:
            stats = self.get_streamblock_stats(stream)
            if stats['TxStreamFrames'] == 0:
                raise InvalidInputParam(f"[Renix] 测试仪 {stream} 发送报文数为0，请检查测试环境")
            lost_packet = stats['TxStreamFrames'] - stats['RxStreamFrames']
            lost_rate = round(lost_packet / stats['TxStreamFrames'] * 100, 3)
            log.info(f"[Renix] {stream} lost packet is {lost_packet}; lost rate is: {lost_rate}%")
            loss_pkt_dict[stream] = lost_packet
            loss_rate_dict[stream] = lost_rate
        return loss_pkt_dict, loss_rate_dict

    def check_stream(self, stream_list: [] = None, threshold=0) -> bool:
        """
        检查是否每条流的丢包数符合要求
        :param stream_list:
        :param threshold:
        :return:
        """
        flag = True
        if not stream_list:
            stream_list = list(self.renix_api.stream_dict.keys())
        for stream in stream_list:
            stats = self.get_streamblock_stats(stream)
            lost_rate = (stats['TxStreamFrames'] - stats['RxStreamFrames'])/stats['TxStreamFrames']*100
            if lost_rate > threshold:
                flag = False
        return flag

    def check_stream_rate(self, stream_list: [] = None, threshold=1) -> bool:
        """
        检查是否每条流的丢包数符合要求
        :param stream_list:
        :param threshold:
        :return:
        """
        flag = True
        if not stream_list:
            stream_list = list(self.renix_api.stream_dict.keys())
        for stream in stream_list:
            stats = self.get_streamblock_stats(stream)
            lost_rate = (stats['TxFrameRate'] - stats['RxFrameRate'])/stats['TxFrameRate']*100
            if abs(lost_rate) > threshold:
                flag = False
        return flag

    def get_stream_stats(self, stream, stream_id, item_list: [] = None) -> dict:
        """
        获取 stream block 中某条流的统计
        :param stream:
        :param stream_id:
        :param item_list:
        :return:
        usage: get_stream_stats(stream_1, 1, 'TxStreamFrames', 'RxStreamFrames')
        """
        if not item_list:
            item_list = ['TxStreamFrames', 'RxStreamFrames', 'MinLatency', 'AvaLatency', 'MaxLatency'
                                                                                         'TxFrameRate', 'RxFrameRate',
                         'RxL1Rate', 'TxL1Rate', 'RxUtil',
                         'RxPayloadErr', 'MinJitter', 'AvaJitter', 'MaxJitter']
        stats = self.renix_api.get_stream_stat(stream, stream_id, item_list)
        log.info(f"[Renix] 测试仪 {stream} index{stream_id} 统计：{stats}")
        return stats

    def get_port_errors(self, *ports) -> int:
        """
        获取端口上的错误统计
        :param ports:
        :return:
        usage: get_port_errors()
        """
        error_count = 0
        if not ports:
            ports = self.renix_api.port_dict.keys()
        for port in ports:
            errors = self.renix_api.get_port_stat(port, ['RxFCSErr', 'RxIpv4ChecksumError', 'RxUdpChecksumError',
                                                         'RxTcpChecksumError'])
            log.info(f"[Renix] 测试仪 {port} errors统计: {errors}")
            for key, value in errors.items():
                error_count += value
        return error_count

    def get_stream_errors(self, *streams):
        """
        获取流上的错误统计
        :param streams:
        :return:
        usage: get_stream_errors()
        """
        error_count = 0
        if not streams:
            streams = self.renix_api.stream_dict.keys()
        for stream in streams:
            errors = self.renix_api.get_streamblock_stat(stream, ['RxPayloadErr'])
            log.info(f"[Renix] 测试仪 {stream} errors统计: {errors}")
            for key, value in errors.items():
                error_count += value
        return error_count

    def get_all_errors(self):
        """
        获取所有端口和所有流的错误统计
        :return:
        usage: get_all_errors()
        """
        port_errors = self.get_port_errors()
        stream_errors = self.get_stream_errors()
        return port_errors + stream_errors

    def get_ipv4_mac(self, interface) -> list:
        """
        获取interface的ipv4 resolved mac
        :param interface:
        :return:
        """
        return self.renix_api.get_ipv4_mac(interface)

    def get_ipv6_mac(self, interface) -> list:
        """
        获取interface的ipv6 resolved mac
        :param interface:
        :return:
        """
        return self.renix_api.get_ipv6_mac(interface)

    def start_arp(self, interface_list: [] = None):
        """
        接口发送arp
        :param interface_list:
        :return:
        usage: start_arp([interface_2])
               start_arp()
        """
        self.renix_api.check_arp(interface_list)

    def start_stream_arp(self, stream_list: [] = None):
        """
        接口发送arp
        :param stream_list:
        :return:
        usage: start_stream_arp([stream_1])
               start_stream_arp()
        """
        self.renix_api.check_stream_arp(stream_list)

    def start_stream(self, stream_list: [] = None):
        """
        开始发送流量
        :param stream_list:
        :return:
        usage: start_stream([stream_1])
               start_stream()
        """
        self.renix_api.create_all_result_view()
        self.renix_api.subscribe_result_view()
        # self.renix_api.check_arp()
        self.renix_api.start_stream(stream_list)
        time.sleep(5)

    def start_stop_stream(self, stream_list: [] = None, set_time=10):
        """
        开始发送流量，一段时间后，停止发送
        :param stream_list:
        :param set_time:
        :return:
        usage: start_stop_stream([stream_1], set_time=10)
               start_stop_stream()
        """
        self.renix_api.create_all_result_view()
        self.renix_api.subscribe_result_view()
        self.renix_api.check_arp()
        self.renix_api.start_stream(stream_list)
        time.sleep(set_time)
        self.renix_api.stop_stream(stream_list)
        time.sleep(5)

    def start_stop_stream_without_arp(self, stream_list: [] = None, set_time=10):
        """
        开始发送流量，一段时间后，停止发送；发流之前不发arp
        :param stream_list:
        :param set_time:
        :return:
        usage: start_stop_stream([stream_1], set_time=10)
               start_stop_stream()
        """
        self.renix_api.create_all_result_view()
        self.renix_api.subscribe_result_view()
        self.renix_api.start_stream(stream_list)
        time.sleep(set_time)
        self.renix_api.stop_stream(stream_list)
        time.sleep(5)

    def stop_stream(self, stream_list: [] = None):
        """
        停止发送流量
        :param stream_list:
        :return:
        """
        self.renix_api.stop_stream(stream_list)
        time.sleep(5)

    def get_ping_ipv4(self, interface, dst_ip, count=5) -> bool:
        """
        ping ipv4
        :param interface:
        :param dst_ip:
        :param count:
        :return: 无丢包返回True，有丢包返回False
        usage: get_ping_ipv4(interface_1, '192.1.1.1', 10)
        """
        return self.renix_api.ping_ipv4(interface, dst_ip, count)

    def get_ping_ipv6(self, interface, dst_ip, count=5) -> bool:
        """
        ping ipv6
        :param interface:
        :param dst_ip:
        :param count:
        :return: 无丢包返回True，有丢包返回False
        """
        return self.renix_api.ping_ipv6(interface, dst_ip, count)

    def start_capture(self, *ports):
        """
        开始捕获
        :param ports:
        :return:
        usage: start_capture()
        """
        self.renix_api.start_capture(*ports)
        time.sleep(5)

    def stop_capture(self, *ports):
        """
        停止捕获
        :param ports:
        :return:
        usage: stop_capture()
        """
        self.renix_api.stop_capture(*ports)

    def download_packets(self, port, count=0):
        """
        下载报文
        :param port:
        :param count: count=0时，下载全部报文；其他值时，下载对应数量的报文
        :return:
        usage: download_packets(port_1, 'D:/', 500)
        """
        current_directory = os.getcwd()
        file_dir = f"{current_directory}/{port}"
        self.renix_api.download_pkt(port, file_dir, count)

    def get_packet(self, port, idx) -> str:
        """
        获取指定报文的内容
        :param port:
        :param idx: 从1开始
        :return:
        usage: get_packet(port_1, 400)
        """
        return self.renix_api.get_pkt_data(port, idx)

    def get_pkts(self, port, count):
        """
        获取 count 个报文
        :param port:
        :param count:
        :return:
        """
        self.download_packets(port, count)
        pkts_list = [self.get_packet(port, i + 1) for i in range(count)]
        return pkts_list

    def subscribe_result(self):
        """
        订阅统计
        :return:
        """
        self.renix_api.create_all_result_view()
        self.renix_api.subscribe_result_view()
        time.sleep(1)

    def clear_result(self):
        """
        清空统计
        :return:
        """
        self.renix_api.clear_all_results()

    def disconn_chassis(self):
        """
        断开机框
        :return:
        """
        self.renix_api.disconnect_chassis()

    def release_port(self):
        """
        释放端口
        :return:
        """
        self.renix_api.release_ports()

    def save_xcfg(self, filename='D:/test.xcfg'):
        """
        保存配置到文件
        :return:
        """
        self.renix_api.save_xcfg(filename)

    def delete_streams(self, stream_list: [] = None):
        """
        删除指定流模板
        :param stream_list:
        :return:
        usage: delete_streams(stream_list)
        """
        if not stream_list:
            stream_list = self.renix_api.stream_dict.keys()
        for stream in stream_list:
            self.renix_api.delete_stream(stream)

    def delete_interfaces(self, interface_list: [] = None):
        """
        删除指定接口
        :param interface_list:
        :return:
        usage: delete_interfaces(interface_list)
        """
        if not interface_list:
            interface_list = self.renix_api.interface_dict.keys()
        for interface in interface_list:
            self.renix_api.delete_interface(interface)

    def insert_ipv6_hbh(self, stream, header):
        """
        增加hop by hop报文头，且插入option：['pad1', 'padN', 'routerAlert', 'jumbo', 'generalTLV', 'generalWildcardTLV']
        :param stream:
        :param header:
        :param node:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'IPv6.ipv6HopByHopHeader')
        for node in ['routerAlert', 'jumbo', 'padN']:
            self.renix_api.insert_stream_node(stream, header, 'ipv6HopByHopHeader_1.options', node)

    def insert_ipv6_rh(self, stream, header, count):
        """
        增加routing header报文头，且插入Ipv6Address
        :param count:
        :param stream:
        :param header:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'IPv6.ipv6RoutingHeader')
        for i in range(count):
            self.renix_api.insert_stream_node(stream, header, 'ipv6RoutingHeader_1.node', 'Ipv6Address')
        log.info(f'Routing header add {count} address')

    def insert_ipv6_dh(self, stream, header, count):
        """
        增加destination header报文头，且插入option：['pad1', 'padN', 'generalTLV', 'bierv6', 'generalWildcardTLV']
        :param count:
        :param stream:
        :param header:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'IPv6.ipv6DestinationHeader')
        self.renix_api.insert_stream_node(stream, header, 'ipv6DestinationHeader_1.options', 'bierv6')
        for i in range(count):
            self.renix_api.insert_stream_node(stream, header, 'ipv6DestinationHeader_1.options', 'generalTLV')
        log.info(f'Destination header add {count} tlv')

    def insert_ipv6_mh(self, stream, header, custom):
        """
        添加mobility header
        :param stream:
        :param header:
        :param custom:
        :return:
        """
        self.renix_api.edit_stream_header(stream, 0, header, nextHeader=ProtoType.MOBILITY)
        self.renix_api.insert_stream_header(stream, 'Custom.custom')
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)

    def insert_ipv6_nh_in_order(self, stream, header):
        """
        按照推荐顺序增加ipv6 next header
        :param stream:
        :param header:
        :return:
        """
        self.insert_ipv6_hbh(stream, header)
        self.insert_ipv6_dh(stream, header, 1)
        self.insert_ipv6_rh(stream, header, 1)
        self.add_header(stream, 'fragment')
        self.edit_stream(stream, FrameLengthType='AUTO')

    def insert_ipv6_nh_dup(self, stream, header):
        """
        destination header出现两次
        :param stream:
        :param header:
        :return:
        """
        self.insert_ipv6_hbh(stream, header)
        self.insert_ipv6_dh(stream, header, 1)
        self.insert_ipv6_rh(stream, header, 1)
        self.insert_ipv6_dh(stream, header, 1)
        self.edit_stream(stream, FrameLengthType='AUTO')

    def insert_ipv6_nh_disorder(self, stream, header):
        """
        不按照推荐顺序增加ipv6 next header
        :param stream:
        :param header:
        :return:
        """
        methods = [
            lambda: self.insert_ipv6_mh(stream, header, Payload.MOBILITY_1),
            lambda: self.insert_ipv6_rh(stream, header, 1),
            lambda: self.insert_ipv6_dh(stream, header, 1),
            lambda: self.insert_ipv6_hbh(stream, header),
            lambda: self.add_header(stream, 'fragment')]
        # random.shuffle(methods)
        for method in methods:
            method()
        self.edit_stream(stream, FrameLengthType='AUTO')

    def add_esp(self, stream, header):
        """
        添加ESP头
        :param stream:
        :param header:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'Custom.custom')
        if 'ipv4' in header:
            self.renix_api.edit_stream_header(stream, 0, header, protocol=ProtoType.ESP)
        if 'ipv6' in header:
            self.renix_api.edit_stream_header(stream, 0, header, nextHeader=ProtoType.ESP)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=Payload.ESP)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)

    def add_ah(self, stream, header):
        """
        添加AH头
        :param stream:
        :param header:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'Custom.custom')
        if 'ipv4' in header:
            self.renix_api.edit_stream_header(stream, 0, header, protocol=ProtoType.AH)
        if 'ipv6' in header:
            self.renix_api.edit_stream_header(stream, 0, header, nextHeader=ProtoType.AH)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=Payload.AH)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)

    def add_vrrp4(self, port, custom) -> str:
        """
        添加vrrp ipv4报文
        :param port:
        :param custom:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_IP4_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_6)
        self.renix_api.edit_stream_header(stream, 0, 'ipv4_1', protocol=ProtoType.VRRP, destination=Addr.MCAST_IP_1,
                                          ttl=255)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_vrrp6(self, port, custom) -> str:
        """
        添加vrrp ipv6报文
        :param port:
        :param custom:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_IP6_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_23)
        self.renix_api.edit_stream_header(stream, 0, 'ipv6_1', nextHeader=ProtoType.VRRP, destination=Addr.MCAST_IP6_1,
                                          hopLimit=255)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_ospf_hello(self, port) -> str:
        """
        添加ospf hello报文
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.OSPF_HELLO)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_7)
        self.renix_api.edit_stream_header(stream, 0, 'ipv4_1', destination=Addr.MCAST_IP_2, ttl=1)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_ospf_update(self, port) -> str:
        """
        添加ospf update报文
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.OSPF_UPDATE)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_8)
        self.renix_api.edit_stream_header(stream, 0, 'ipv4_1', destination=Addr.MCAST_IP_3, ttl=1)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_ospfv3_dbd(self, port, dst_mac, custom) -> str:
        """
        添加ospf dbd报文
        :param port:
        :param dst_mac:
        :param custom:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_IP6_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=dst_mac)
        self.renix_api.edit_stream_header(stream, 0, 'ipv6_1', source=Addr.LOCAL_IP6_1, destination=Addr.LOCAL_IP6_2,
                                          hopLimit=1, nextHeader=ProtoType.OSPF)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_igmp(self, port) -> str:
        """
        添加IGMPv2报文
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.IGMP_V2)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_9)
        self.renix_api.edit_stream_header(stream, 0, 'ipv4_1', destination=Addr.MCAST_IP_4, ttl=1)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_igmpv3(self, port) -> str:
        """
        添加IGMPv3报文
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.IGMP_V3)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_9)
        self.renix_api.edit_stream_header(stream, 0, 'ipv4_1', destination=Addr.MCAST_IP_4, ttl=1)
        addr_count = random.randint(1, 300)
        log.info(f'[Renix] 添加{addr_count}个地址测试')
        for i in range(addr_count):
            self.renix_api.insert_stream_node(stream, 'ipv4_1', 'igmpv3Query_1.sourceAddressList', 'ipv4AddrContainer')
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_eigrp4(self, port, custom) -> str:
        """
        添加EIGRP ipv4报文
        :param port:
        :param custom:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_IP4_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_10)
        self.renix_api.edit_stream_header(stream, 0, 'ipv4_1', protocol=ProtoType.EIGRP, destination=Addr.MCAST_IP_5,
                                          ttl=1)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_eigrp6(self, port, custom) -> str:
        """
        添加EIGRP ipv6报文
        :param port:
        :param custom:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_IP6_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_10)
        self.renix_api.edit_stream_header(stream, 0, 'ipv6_1', nextHeader=ProtoType.EIGRP, destination=Addr.MCAST_IP6_2,
                                          hopLimit=1)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_pim4(self, port, custom) -> str:
        """
        添加PIM ipv4报文
        :param port:
        :param custom:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_IP4_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_11)
        self.renix_api.edit_stream_header(stream, 0, 'ipv4_1', protocol=ProtoType.PIM, destination=Addr.MCAST_IP_6,
                                          ttl=1)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_pim6(self, port, custom) -> str:
        """
        添加PIM ipv6报文
        :param port:
        :param custom:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_IP6_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_11)
        self.renix_api.edit_stream_header(stream, 0, 'ipv6_1', nextHeader=ProtoType.PIM, destination=Addr.MCAST_IP6_3,
                                          hopLimit=1)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_l2tpv3_ctrl(self, stream):
        """
        增加L2TPv3 control 报文头
        :param stream:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'L2TPv3.l2tpv3ControlOverIp')
        count = random.randint(0, len(Header.L2TPV3_AVP))
        insert_tlv = random.sample(Header.L2TPV3_AVP, count)
        for tlv in insert_tlv:
            self.renix_api.insert_stream_node(stream, 'l2tpv3ControlOverIp_1', 'l2tpv3ControlOverIp_1.avpOptions', tlv)
        self.renix_api.insert_stream_node(stream, 'l2tpv3ControlOverIp_1', 'l2tpv3ControlOverIp_1.lengthOption',
                                          'excludeSessionLength')
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)

    def add_l2tpv2_length(self, stream):
        """
        增加L2TPv2 length 节点
        :param stream:
        :return:
        """
        self.renix_api.insert_stream_node(stream, 'l2tpv2Data_1', 'l2tpv2Data_1.lengthOption', 'length')

    def add_icmp6_rs(self, port) -> str:
        """
        添加ICMPv6 router solicitation报文
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, ['Ethernet.ethernetII', 'IPv6.ipv6', 'ICMPv6.routerSolicit'])
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_20)
        self.renix_api.edit_stream_header(stream, 0, 'ipv6_1', destination=Addr.MCAST_IP6_4)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_icmp6_ra(self, port) -> str:
        """
        添加ICMPv6 router advertisement报文
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, ['Ethernet.ethernetII', 'IPv6.ipv6', 'ICMPv6.routerAdvertise'])
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_24)
        self.renix_api.edit_stream_header(stream, 0, 'ipv6_1', destination=Addr.MCAST_IP6_6)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_icmp6_ns(self, port) -> str:
        """
        添加ICMPv6 neighbor solicitation报文
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, ['Ethernet.ethernetII', 'IPv6.ipv6', 'ICMPv6.neighborSolicit'])
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_25)
        self.renix_api.edit_stream_header(stream, 0, 'ipv6_1', destination=Addr.MCAST_IP6_7)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_icmp6_na(self, port) -> str:
        """
        添加ICMPv6 neighbor advertisement报文
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, ['Ethernet.ethernetII', 'IPv6.ipv6', 'ICMPv6.neighborAdvertise'])
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_24)
        self.renix_api.edit_stream_header(stream, 0, 'ipv6_1', destination=Addr.MCAST_IP6_6)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_mldv1_query(self, port) -> str:
        """
        添加MLDv1 query报文
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.MLDV1_QUERY)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_21)
        self.renix_api.edit_stream_header(stream, 0, 'ipv6_1', destination=Addr.MCAST_IP6_5)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_mldv1_report(self, port) -> str:
        """
        添加MLDv1 report报文
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.MLDV1_REPORT)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_21)
        self.renix_api.edit_stream_header(stream, 0, 'ipv6_1', destination=Addr.MCAST_IP6_5)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_mld_done(self, port) -> str:
        """
        添加MLDv1 done报文
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.MLDV1_DONE)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_21)
        self.renix_api.edit_stream_header(stream, 0, 'ipv6_1', destination=Addr.MCAST_IP6_5)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_mldv2_query(self, port) -> str:
        """
        添加MLDv2 query报文
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.MLDV2_QUERY)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_21)
        self.renix_api.edit_stream_header(stream, 0, 'ipv6_1', destination=Addr.MCAST_IP6_5)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_mldv2_report(self, port) -> str:
        """
        添加MLDv2 report报文
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.MLDV2_REPORT)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_21)
        self.renix_api.edit_stream_header(stream, 0, 'ipv6_1', destination=Addr.MCAST_IP6_5)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def insert_ip4_ver_err(self, stream, header):
        """
        插入一个错误的ipv4 version
        :param stream:
        :param header:
        :return:
        """
        err = random.choice([i for i in range(16) if i != 4])
        self.renix_api.edit_stream_header(stream, 0, header, version=err)

    def insert_ip4_ihl_err(self, stream, header):
        """
        插入一个错误的ipv4 header length
        :param stream:
        :param header:
        :return:
        """
        err = random.choice([i for i in range(4)])
        self.renix_api.edit_stream_header(stream, 0, header, headLen=err)

    def insert_ip4_frag(self, stream, header):
        """
        插入一个错误的ipv4 header length
        :param stream:
        :param header:
        :return:
        """
        self.edit_stream_header(stream, header, flags='001', offset=random.randint(1, 8191))

    def insert_ip6_ver_err(self, stream, header):
        """
        插入一个错误的ipv6 version
        :param stream:
        :param header:
        :return:
        """
        err = random.choice([i for i in range(16) if i != 6])
        self.renix_api.edit_stream_header(stream, 0, header, version=err)

    def add_tcp_option(self, stream, option):
        """
        添加一个TCP header并添加option
        :param stream:
        :param option:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'TCP.tcp')
        self.renix_api.edit_stream_header(stream, 0, 'tcp_1', option=option)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO')

    def add_telnet(self, stream, custom):
        """
        添加 TCP头，并添加telnet自定义头
        :param stream:
        :param custom:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'TCP.tcp')
        self.renix_api.insert_stream_header(stream, 'Custom.custom')
        # 随机选择修改源端口号还是目的端口号
        choice = random.randint(0, 1)
        if choice == 0:
            self.renix_api.edit_stream_header(stream, 0, 'tcp_1', sourcePort=ProtoType.TELNET)
        else:
            self.renix_api.edit_stream_header(stream, 0, 'tcp_1', destPort=ProtoType.TELNET)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO')

    def add_ssh(self, stream, custom):
        """
        添加 TCP头，并添加telnet自定义头
        :param stream:
        :param custom:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'TCP.tcp')
        self.renix_api.insert_stream_header(stream, 'Custom.custom')
        # 随机选择修改源端口号还是目的端口号
        choice = random.randint(0, 1)
        if choice == 0:
            self.renix_api.edit_stream_header(stream, 0, 'tcp_1', sourcePort=ProtoType.SSH)
        else:
            self.renix_api.edit_stream_header(stream, 0, 'tcp_1', destPort=ProtoType.SSH)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO')

    def add_bfd(self, stream, port_num):
        """
        添加 UDP头 和 BFD头
        :param stream:
        :param port_num:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        self.renix_api.insert_stream_header(stream, random.choice(Header.BFD_LIST))
        # # 随机选择修改源端口号还是目的端口号
        # choice = random.randint(0, 1)
        # if choice == 0:
        #     self.renix_api.edit_stream_header(stream, 0, 'udp_1', sourcePort=port_num)
        # else:
        self.renix_api.edit_stream_header(stream, 0, 'udp_1', destPort=port_num)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO')

    def add_ldp_tcp(self, stream, custom):
        """
        添加 tcp 头，并添加自定义ldp
        :param stream:
        :param custom:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'TCP.tcp')
        self.renix_api.insert_stream_header(stream, 'Custom.custom')
        # 随机选择修改源端口号还是目的端口号
        # choice = random.randint(0, 1)
        # if choice == 0:
        #     self.renix_api.edit_stream_header(stream, 0, 'tcp_1', sourcePort=ProtoType.LDP)
        # else:
        self.renix_api.edit_stream_header(stream, 0, 'tcp_1', destPort=ProtoType.LDP)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO')

    def add_ldp_udp(self, stream, custom):
        """
        添加 udp 头，并添加自定义ldp
        :param stream:
        :param custom:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        self.renix_api.insert_stream_header(stream, 'Custom.custom')
        self.renix_api.edit_stream_header(stream, 0, 'udp_1', sourcePort=ProtoType.LDP, destPort=ProtoType.LDP)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)

    def add_ripv1(self, port):
        """
        添加 udp+ripv1 头
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, ['Ethernet.ethernetII', 'IPv4.ipv4', 'UDP.udp', 'RIP.ripv1'])
        self.renix_api.insert_stream_node(stream, 'ripv1_1', 'ripv1_1.rip1Entries', 'rip1EntriesList')
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_12)
        self.renix_api.edit_stream_header(stream, 0, 'ipv4_1', destination=Addr.MCAST_IP_7)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_ripv2(self, port):
        """
        添加 udp+ripv2 头
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, ['Ethernet.ethernetII', 'IPv4.ipv4', 'UDP.udp', 'RIP.ripv2'])
        self.renix_api.insert_stream_node(stream, 'ripv2_1', 'ripv2_1.rip2Entries', 'rip2EntriesList')
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_12)
        self.renix_api.edit_stream_header(stream, 0, 'ipv4_1', destination=Addr.MCAST_IP_7)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_ripng(self, port):
        """
        添加 udp+ripng 头
        :param stream:
        :return:
        """
        stream = self.renix_api.create_stream(port, ['Ethernet.ethernetII', 'IPv6.ipv6', 'UDP.udp', 'RIP.ripng'])
        # self.renix_api.insert_stream_header(stream, 'UDP.udp')
        # self.renix_api.insert_stream_header(stream, 'RIP.ripng')
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_26)
        self.renix_api.edit_stream_header(stream, 0, 'ipv6_1', destination=Addr.MCAST_IP6_8)
        self.renix_api.insert_stream_node(stream, 'ripng_1', 'ripng_1.ripngEntries', 'ripngEntriesList')
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_dhcp4(self, stream):
        """
        添加 UDP+DHCPv4 头
        :param stream:
        :return:
        """
        header = random.choice(['DHCPv4.dhcpv4Client', 'DHCPv4.dhcpv4Server'])
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        self.renix_api.insert_stream_header(stream, header)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)

    def add_dhcp6(self, stream):
        """
        添加 UDP+DHCPv6 头
        :param stream:
        :return:
        """
        header = random.choice(['DHCPv6.dhcpv6Client', 'DHCPv6.dhcpv6Server', 'DHCPv6.Dhcpv6RelayForwardMessage'])
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        self.renix_api.insert_stream_header(stream, header)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)

    def add_ike(self, stream, custom):
        """
        添加 UDP头，并添加IKE自定义头
        :param stream:
        :param custom:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        self.renix_api.insert_stream_header(stream, 'Custom.custom')
        self.renix_api.edit_stream_header(stream, 0, 'udp_1', destPort=ProtoType.IKE)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO')

    def add_ipsec_nat(self, stream):
        """
        添加 UDP头，并添加IKE_Quick自定义头
        :param stream:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        # 随机选择修改源端口号还是目的端口号
        # choice = random.randint(0, 1)
        # if choice == 0:
        #     self.renix_api.edit_stream_header(stream, 0, 'udp_1', sourcePort=ProtoType.IPSEC_NAT)
        # else:
        #     self.renix_api.edit_stream_header(stream, 0, 'udp_1', destPort=ProtoType.IPSEC_NAT)
        self.renix_api.edit_stream_header(stream, 0, 'udp_1', destPort=ProtoType.IPSEC_NAT)
        self.renix_api.edit_stream(stream, PayloadType='RANDOM')

    def add_bgp(self, stream, custom):
        """
        添加 TCP头，并添加BGP自定义头
        :param stream:
        :param custom:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'TCP.tcp')
        self.renix_api.insert_stream_header(stream, 'Custom.custom')
        # # 随机选择修改源端口号还是目的端口号
        # choice = random.randint(0, 1)
        # if choice == 0:
        #     self.renix_api.edit_stream_header(stream, 0, 'tcp_1', sourcePort=ProtoType.BGP)
        # else:
        self.renix_api.edit_stream_header(stream, 0, 'tcp_1', destPort=ProtoType.BGP)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO')

    def add_ntp(self, stream, custom):
        """
        添加 UDP头，并添加NTP自定义头
        :param stream:
        :param custom:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        self.renix_api.insert_stream_header(stream, 'Custom.custom')
        self.renix_api.edit_stream_header(stream, 0, 'udp_1', sourcePort=ProtoType.NTP, destPort=ProtoType.NTP)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO')

    def add_ptp_header(self, stream, custom):
        """
        添加 UDP头，并添加PTP自定义头
        :param stream:
        :param custom:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        self.renix_api.insert_stream_header(stream, 'Custom.custom')
        self.renix_api.edit_stream_header(stream, 0, 'udp_1', sourcePort=ProtoType.PTP_PORT, destPort=ProtoType.PTP_PORT)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO')

    def add_gtp1_c(self, stream):
        """
        添加 UDP + GTPv1头
        :param stream:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        self.renix_api.insert_stream_header(stream, 'GTPv1.gtpv1')
        # # 随机选择修改源端口号还是目的端口号
        # choice = random.randint(0, 1)
        # if choice == 0:
        #     self.renix_api.edit_stream_header(stream, 0, 'udp_1', sourcePort=ProtoType.GTP_C)
        # else:
        self.renix_api.edit_stream_header(stream, 0, 'udp_1', destPort=ProtoType.GTP_C)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO')

    def add_gtp2_c(self, stream):
        """
        添加 UDP + GTPv2头
        :param stream:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        self.renix_api.insert_stream_header(stream, 'GTPv1.gtpv1')
        # # 随机选择修改源端口号还是目的端口号
        # choice = random.randint(0, 1)
        # if choice == 0:
        #     self.renix_api.edit_stream_header(stream, 0, 'udp_1', sourcePort=ProtoType.GTP_C)
        # else:
        self.renix_api.edit_stream_header(stream, 0, 'udp_1', destPort=ProtoType.GTP_C)
        self.renix_api.edit_stream_header(stream, 0, 'gtpv1_1', version=2)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO')

    def add_gtp2_c_tcp(self, stream):
        """
        添加 TCP + GTPv2头
        :param stream:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'TCP.tcp')
        self.renix_api.insert_stream_header(stream, 'GTPv1.gtpv1')
        # # 随机选择修改源端口号还是目的端口号
        # choice = random.randint(0, 1)
        # if choice == 0:
        #     self.renix_api.edit_stream_header(stream, 0, 'tcp_1', sourcePort=ProtoType.GTP_C)
        # else:
        self.renix_api.edit_stream_header(stream, 0, 'tcp_1', destPort=ProtoType.GTP_C)
        self.renix_api.edit_stream_header(stream, 0, 'gtpv1_1', version=2)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO')

    def add_gtp_u(self, stream):
        """
        添加 UDP + GTP-U头
        :param stream:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        self.renix_api.insert_stream_header(stream, 'GTPv1.gtpv1')
        self.renix_api.edit_stream_header(stream, 0, 'udp_1', destPort=ProtoType.GTP_U)
        self.renix_api.edit_stream(stream, EnableSignature=False)
        # self.renix_api.edit_stream_header(stream, 0, 'gtpv1_1', version=2)

    def add_gtp(self, stream):
        """
        添加 UDP + GTP’头
        :param stream:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        self.renix_api.insert_stream_header(stream, 'GTPv1.gtpv1')
        # 随机选择修改源端口号还是目的端口号
        choice = random.randint(0, 1)
        if choice == 0:
            self.renix_api.edit_stream_header(stream, 0, 'udp_1', sourcePort=ProtoType.GTP)
        else:
            self.renix_api.edit_stream_header(stream, 0, 'udp_1', destPort=ProtoType.GTP)
        self.renix_api.edit_stream_header(stream, 0, 'gtpv1_1', version=2)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO')

    def add_gtp_tcp(self, stream):
        """
        添加 TCP + GTP‘头
        :param stream:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'TCP.tcp')
        self.renix_api.insert_stream_header(stream, 'GTPv1.gtpv1')
        # 随机选择修改源端口号还是目的端口号
        choice = random.randint(0, 1)
        if choice == 0:
            self.renix_api.edit_stream_header(stream, 0, 'tcp_1', sourcePort=ProtoType.GTP)
        else:
            self.renix_api.edit_stream_header(stream, 0, 'tcp_1', destPort=ProtoType.GTP)
        self.renix_api.edit_stream_header(stream, 0, 'gtpv1_1', version=2)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO')

    def add_pfcp(self, stream, custom):
        """
        添加 UDP头，并添加PFCP自定义头
        :param stream:
        :param custom:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        self.renix_api.insert_stream_header(stream, 'Custom.custom')
        # # 随机选择修改源端口号还是目的端口号
        # choice = random.randint(0, 1)
        # if choice == 0:
        #     self.renix_api.edit_stream_header(stream, 0, 'udp_1', sourcePort=ProtoType.PFCP)
        # else:
        self.renix_api.edit_stream_header(stream, 0, 'udp_1', destPort=ProtoType.PFCP)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FixedLength=256, EnableSignature=False)

    def add_l2tpv3_ctrl_udp(self, stream):
        """
        增加UDP+L2TPv3 control 报文头
        :param stream:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        self.renix_api.insert_stream_header(stream, 'L2TPv3.l2tpv3ControlOverUdp')
        count = random.randint(0, len(Header.L2TPV3_AVP))
        insert_tlv = random.sample(Header.L2TPV3_AVP, count)
        for tlv in insert_tlv:
            self.renix_api.insert_stream_node(stream, 'l2tpv3ControlOverUdp_1', 'l2tpv3ControlOverUdp_1.avpOptions',
                                              tlv)
        self.renix_api.insert_stream_node(stream, 'l2tpv3ControlOverUdp_1', 'l2tpv3ControlOverUdp_1.lengthOption',
                                          'length')
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)

    def add_l2tpv2_ctrl(self, stream):
        """
        添加 UDP + L2TPv2 control头
        :param stream:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        self.renix_api.insert_stream_header(stream, 'L2TPv2.l2tpv2Control')
        count = random.randint(0, len(Header.L2TPV2_AVP))
        insert_tlv = random.sample(Header.L2TPV2_AVP, count)
        for tlv in insert_tlv:
            self.renix_api.insert_stream_node(stream, 'l2tpv2Control_1', 'l2tpv2Control_1.avpOptions', tlv)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO')

    def add_magic(self, stream, mac):
        """
        添加一个udp+magic报文头
        :param stream:
        :param mac:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        self.renix_api.insert_stream_header(stream, 'Custom.custom')
        src_port = random.randint(1024, 65534)
        payload = (Addr.BROADCAST + mac * 16).replace(':', '')
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        self.renix_api.edit_stream_header(stream, 0, 'udp_1', sourcePort=src_port,
                                          destPort=random.choice(ProtoType.MAGIC))
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=payload)

    def add_tcp_err(self, stream):
        """
        添加 TCP头，并设置data offset 小于5
        :param stream:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'TCP.tcp')
        err = random.randint(0, 4)
        self.renix_api.edit_stream_header(stream, 0, 'tcp_1', dataOffset=err)

    def add_tcp_checksum_err(self, stream):
        """
        添加 TCP头，并将checksum字段注错
        :param stream:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'TCP.tcp')
        self.renix_api.edit_stream_header(stream, 0, 'tcp_1', checksum="FFFF")

    def add_udp_err(self, stream):
        """
        添加 UDP头，并设置 length小于8
        :param stream:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        err = random.randint(0, 7)
        self.renix_api.edit_stream_header(stream, 0, 'udp_1', length=err)

    def add_udp_checksum_err(self, stream):
        """
        添加 UDP头，并将checksum字段注错
        :param stream:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        self.renix_api.edit_stream_header(stream, 0, 'udp_1', checksum="ffff")

    def add_udp_err_2(self, stream, err):
        """
        添加 UDP头，并设置 length不等于IP头部的值
        :param stream:
        :param err
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'UDP.udp')
        self.renix_api.edit_stream_header(stream, 0, 'udp_1', length=err)

    def add_sctp(self, stream, header_ip='auto', header_sctp='custom_1'):
        """
        添加一个sctp checksum正确的报文
        :param header_sctp:
        :param header_ip:
        :param stream:
        :return:
        """
        self.add_header(stream, 'sctp')
        self.renix_api.insert_stream_node(stream, 'sctp_1', 'sctp_1.chunks', 'sctpChunk')
        self.renix_api.insert_stream_node(stream, 'sctp_1', 'sctp_1.chunks.sctpChunk_0.chunkType', 'initChunk')
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)

    def add_sctp_error(self, stream, header_ip, header_sctp='custom_1'):
        """
        添加一个sctp checksum错误的报文
        :param header_sctp:
        :param stream:
        :return:
        """
        self.renix_api.insert_stream_header(stream, 'Custom.custom')
        if 'ipv4' in header_ip:
            self.renix_api.edit_stream_header(stream, 0, header_ip, protocol=ProtoType.SCTP)
        if 'ipv6' in header_ip:
            self.renix_api.edit_stream_header(stream, 0, header_ip, nextHeader=ProtoType.SCTP)
        self.renix_api.edit_stream_header(stream, 0, header_sctp, customOption_0=Payload.SCTP_ERROR)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)

    def add_stag_stream(self, port, vlan_id, intf_1_ip, intf_2_ip, dut_ip, dst_mac) -> str:
        """
        创建一个带stag的流
        :param port:
        :param vlan_id:
        :param intf_1_ip:
        :param intf_2_ip:
        :param dut_ip:
        :param dst_mac:
        :return:
        """
        # self.add_raw_stream()
        # 添加一条流，模拟interface 发arp（测试仪协议栈不支持发送88A8 tag）
        arp = self.renix_api.create_stream(port, Header.ETH_VLAN_ARP)
        self.renix_api.edit_stream_header(arp, 0, 'ethernetII_1', sourceMacAdd=Addr.UNICAST_1,
                                          destMacAdd=Addr.BROADCAST, protocolType=ProtoType.VLAN_STAG)
        self.renix_api.edit_stream_header(arp, 0, 'vlan_1', id=vlan_id)
        self.renix_api.edit_stream_header(arp, 0, 'arp_1', sendMac=Addr.UNICAST_1, sendIpv4=intf_1_ip,
                                          targetIpv4=dut_ip)
        self.renix_api.start_stream([arp])
        time.sleep(2)
        self.renix_api.stop_stream([arp])
        time.sleep(5)
        # 修改参数，模拟另外一个interface 发arp
        self.renix_api.edit_stream_header(arp, 0, 'ethernetII_1', sourceMacAdd=Addr.UNICAST_2)
        self.renix_api.edit_stream_header(arp, 0, 'arp_1', sendMac=Addr.UNICAST_2, sendIpv4=intf_2_ip,
                                          targetIpv4=dut_ip)
        self.renix_api.start_stream([arp])
        time.sleep(3)
        self.renix_api.stop_stream([arp])
        time.sleep(5)
        # 创建 stag流量， intf_1_ip --> intf_2_ip
        stream_stag = self.renix_api.create_stream(port, Header.ETH_VLAN_IP4)
        self.renix_api.edit_stream_header(stream_stag, 0, 'ethernetII_1', sourceMacAdd=Addr.UNICAST_1,
                                          destMacAdd=dst_mac, protocolType=ProtoType.VLAN_STAG)
        self.renix_api.edit_stream_header(stream_stag, 0, 'vlan_1', id=vlan_id)
        self.renix_api.edit_stream_header(stream_stag, 0, 'ipv4_1', source=intf_1_ip, destination=intf_2_ip)
        return stream_stag

    def add_qinq_stream(self, port, vlan_id, vlan_id2, src_ip, dst_ip, dut_ip, src_mac, dst_mac) -> str:
        """
        创建一个带stag的流
        :param port:
        :param vlan_id:
        :param src_ip:
        :param dst_ip:
        :param dut_ip:
        :param dst_mac:
        :return:
        """
        # 添加一条流，模拟interface 发arp（测试仪协议栈不支持发送88A8 tag）
        arp = self.renix_api.create_stream(port, Header.ETH_VLAN2_ARP)
        self.renix_api.edit_stream_header(arp, 0, 'ethernetII_1', sourceMacAdd=src_mac,
                                          destMacAdd=Addr.BROADCAST, protocolType=ProtoType.VLAN_STAG)
        self.renix_api.edit_stream_header(arp, 0, 'vlan_1', id=vlan_id)
        self.renix_api.edit_stream_header(arp, 0, 'vlan_2', id=vlan_id2)
        self.renix_api.edit_stream_header(arp, 0, 'arp_1', sendMac=src_mac, sendIpv4=src_ip,
                                          targetIpv4=dut_ip)
        self.renix_api.start_stream([arp])
        time.sleep(2)
        self.renix_api.stop_stream([arp])
        time.sleep(5)
        # 创建 stag流量
        stream_qinq = self.renix_api.create_stream(port, Header.ETH_VLAN2_IP4)
        self.renix_api.edit_stream_header(stream_qinq, 0, 'ethernetII_1', sourceMacAdd=src_mac,
                                          destMacAdd=dst_mac, protocolType=ProtoType.VLAN_STAG)
        self.renix_api.edit_stream_header(stream_qinq, 0, 'vlan_1', id=vlan_id)
        self.renix_api.edit_stream_header(stream_qinq, 0, 'vlan_2', id=vlan_id2)
        self.renix_api.edit_stream_header(stream_qinq, 0, 'ipv4_1', source=src_ip, destination=dst_ip)
        return stream_qinq

    def add_8023_stream(self, port, dst_mac) -> str:
        """
        创建802.3流量，不带IP头
        :param port:
        :param dst_mac:
        :param frame_len:
        :param ether_len:
        :return:
        """
        stream = self.add_raw_stream(port, '8023')
        self.renix_api.edit_stream_header(stream, 0, '8023_1', destMacAdd=dst_mac)
        return stream

    def add_8023_ip4(self, port, dst_mac, frame_len=0, ether_len=0) -> str:
        """
        创建802.3流量，可以自定义报文长度和ethernet length字段
        :param port:
        :param dst_mac:
        :param frame_len:
        :param ether_len:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_8023_IP4)
        # 如果 ether_len 没有传参，默认设置为正确的值
        if ether_len == 0:
            self.renix_api.edit_stream_header(stream, 0, '8023_1', destMacAdd=dst_mac)
        else:
            self.renix_api.edit_stream_header(stream, 0, '8023_1', destMacAdd=dst_mac, length=ether_len)
        # 如果 frame_len 没有传参，默认设置为随机帧长
        if frame_len == 0:
            self.renix_api.edit_stream(stream, FrameLengthType='RANDOM', MinLength=FrameLen.LEN_5,
                                       MaxLength=FrameLen.LEN_2, EnableSignature=False)
        else:
            self.renix_api.edit_stream(stream, FixedLength=frame_len, EnableSignature=False)
        return stream

    def add_8023_ip6(self, port, dst_mac) -> str:
        """
        创建802.3流量，可以自定义报文长度和ethernet length字段
        :param port:
        :param dst_mac:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_8023_IP6)
        self.renix_api.edit_stream_header(stream, 0, '8023_1', destMacAdd=dst_mac)
        self.renix_api.edit_stream(stream, FrameLengthType='RANDOM', MinLength=FrameLen.LEN_5, MaxLength=FrameLen.LEN_2,
                                   EnableSignature=False)
        return stream

    def add_8023_vlan(self, port, dst_mac, vlan_id) -> str:
        """
        创建 802.3+vlan 流量
        :param port:
        :param dst_mac:
        :param vlan_id:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_8023_VLAN_IP4)
        self.renix_api.edit_stream_header(stream, 0, '8023_1', destMacAdd=dst_mac)
        self.renix_api.edit_stream_header(stream, 0, 'vlan_1', id=vlan_id)
        self.renix_api.edit_stream(stream, FrameLengthType='RANDOM', MinLength=FrameLen.LEN_5, MaxLength=FrameLen.LEN_2)
        return stream

    def add_8023_dvlan(self, port, dst_mac, vlan_id, vlan_inner_id) -> str:
        """
        创建 802.3+双层vlan 流量
        :param port:
        :param dst_mac:
        :param vlan_id:
        :param vlan_inner_id:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_8023_VLAN_VLAN_IP4)
        self.renix_api.edit_stream_header(stream, 0, '8023_1', destMacAdd=dst_mac)
        self.renix_api.edit_stream_header(stream, 0, 'vlan_1', id=vlan_id)
        self.renix_api.edit_stream_header(stream, 0, 'vlan_2', id=vlan_inner_id)
        self.renix_api.edit_stream(stream, FrameLengthType='RANDOM', MinLength=FrameLen.LEN_5, MaxLength=FrameLen.LEN_2)
        return stream

    def add_8023_qinq(self, port, dst_mac, vlan_id, vlan_inner_id) -> str:
        """
        创建 802.3+qinq 流量
        :param port:
        :param dst_mac:
        :param vlan_id:
        :param vlan_inner_id:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_VLAN_VLAN_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=dst_mac,
                                          protocolType=ProtoType.PROTO_LEN_4)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=Payload.SNAP_2)
        self.renix_api.edit_stream_header(stream, 0, 'vlan_1', id=vlan_id)
        self.renix_api.edit_stream_header(stream, 0, 'vlan_2', id=vlan_inner_id)
        return stream

    def add_eth_custom(self, port, dst_mac, custom, protocol) -> str:
        """
        创建 eth+custom 流量，custom可以自定义为各种不同的报文类型
        :param port:
        :param dst_mac:
        :param custom:
        :param protocol:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=dst_mac, protocolType=protocol)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_eth_vlan_custom(self, port, dst_mac, vlan_id, custom, protocol) -> str:
        """
        创建 eth+vlan+custom 流量，custom可以自定义为各种不同的报文类型
        :param port:
        :param dst_mac:
        :param vlan_id:
        :param custom:
        :param protocol:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_VLAN_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=dst_mac)
        self.renix_api.edit_stream_header(stream, 0, 'vlan_1', id=vlan_id, protocol=protocol)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_eth_dvlan_custom(self, port, dst_mac, vlan_id, vlan_inner_id, custom, protocol) -> str:
        """
        创建 eth+vlan+vlan+custom 流量，custom可以自定义为各种不同的报文类型
        :param port:
        :param dst_mac:
        :param vlan_id:
        :param vlan_inner_id:
        :param custom:
        :param protocol:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_VLAN_VLAN_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=dst_mac)
        self.renix_api.edit_stream_header(stream, 0, 'vlan_1', id=vlan_id)
        self.renix_api.edit_stream_header(stream, 0, 'vlan_2', id=vlan_inner_id, protocol=protocol)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        return stream

    def add_eth_qinq_custom(self, port, dst_mac, vlan_id, vlan_inner_id, custom) -> str:
        """
        创建 eth+qinq+custom 流量，custom可以自定义为各种不同的报文类型
        :param port:
        :param dst_mac:
        :param vlan_id:
        :param vlan_inner_id:
        :param custom:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_VLAN_VLAN_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=dst_mac,
                                          protocolType=ProtoType.VLAN_STAG)
        self.renix_api.edit_stream_header(stream, 0, 'vlan_1', id=vlan_id)
        self.renix_api.edit_stream_header(stream, 0, 'vlan_2', id=vlan_inner_id, protocol=ProtoType.PROTO_LEN_1)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=custom)
        return stream

    def add_arp(self, port) -> str:
        """
        添加一个arp 流
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_ARP)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.BROADCAST)
        self.renix_api.edit_stream(stream, FixedLength=FrameLen.LEN_1, EnableSignature=False)
        return stream

    def add_arp_incorrect_ether_type(self, port) -> str:
        """
        添加一个arp 流
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_ARP)
        incorrect = format(random.randint(1536, 65535), '04X')
        incorrect = '0807' if incorrect == '0806' else incorrect
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.BROADCAST, protocolType=incorrect)
        self.renix_api.edit_stream(stream, FixedLength=FrameLen.LEN_1, EnableSignature=False)
        return stream

    def add_arp_incorrect_hw_type(self, port) -> str:
        """
        添加一个arp 流
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_ARP)
        incorrect = random.randint(0, 65535)
        incorrect = 0 if incorrect == 1 else incorrect
        self.renix_api.edit_stream(stream, FixedLength=FrameLen.LEN_1, EnableSignature=False)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.BROADCAST)
        self.renix_api.edit_stream_header(stream, 0, 'arp_1', hardwareType=incorrect)
        return stream

    def add_arp_incorrect_protocol_type(self, port) -> str:
        """
        添加一个arp 流
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_ARP)
        incorrect = format(random.randint(0, 65535), '04X')
        incorrect = '0801' if incorrect == '0800' else incorrect
        self.renix_api.edit_stream(stream, FixedLength=FrameLen.LEN_1, EnableSignature=False)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.BROADCAST)
        self.renix_api.edit_stream_header(stream, 0, 'arp_1', protocolType=incorrect)
        return stream

    def add_arp_incorrect_hw_size(self, port) -> str:
        """
        添加一个arp 流
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_ARP)
        incorrect = random.randint(0, 255)
        incorrect = 0 if incorrect == 6 else incorrect
        self.renix_api.edit_stream(stream, FixedLength=FrameLen.LEN_1, EnableSignature=False)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.BROADCAST)
        self.renix_api.edit_stream_header(stream, 0, 'arp_1', hardwareSize=incorrect)
        return stream

    def add_arp_incorrect_protocol_size(self, port) -> str:
        """
        添加一个arp 流
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_ARP)
        incorrect = random.randint(0, 255)
        incorrect = 0 if incorrect == 4 else incorrect
        self.renix_api.edit_stream(stream, FixedLength=FrameLen.LEN_1, EnableSignature=False)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.BROADCAST)
        self.renix_api.edit_stream_header(stream, 0, 'arp_1', protocolSize=incorrect)
        return stream

    def add_arp_incorrect_opcode(self, port) -> str:
        """
        添加一个arp 流
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_ARP)
        incorrect = random.randint(0, 65535)
        incorrect = 0 if incorrect == 1 else incorrect
        self.renix_api.edit_stream(stream, FixedLength=FrameLen.LEN_1, EnableSignature=False)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.BROADCAST)
        self.renix_api.edit_stream_header(stream, 0, 'arp_1', opcode=incorrect)
        return stream

    def add_arp_incorrect_target_ip(self, port) -> str:
        """
        添加一个arp 流
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_ARP)
        self.renix_api.edit_stream(stream, FixedLength=FrameLen.LEN_1, EnableSignature=False)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.BROADCAST)
        self.renix_api.edit_stream_header(stream, 0, 'arp_1', targetIpv4=Addr.BROADCAST_IP)
        return stream

    def add_rocev1(self, port, dst_mac) -> str:
        """
        添加一个arp 流
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_CUSTOM)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=dst_mac, protocolType=ProtoType.ROCEV1)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=Payload.ROCE_V1)
        return stream

    def add_lacp(self, port) -> str:
        """
        添加一个arp 流
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.LACP)
        self.renix_api.edit_stream(stream, FrameLengthType='AUTO', EnableSignature=False)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_13)
        return stream

    def add_isis_type1(self, port) -> str:
        """
        创建 isis 流量
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_1,
                                          protocolType=ProtoType.PROTO_LEN_1)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=Payload.ISIS_1)
        self.renix_api.edit_stream(stream, FixedLength=FrameLen.LEN_1, EnableSignature=False)
        return stream

    def add_isis_type2(self, port) -> str:
        """
        创建 isis 流量
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_2,
                                          protocolType=ProtoType.PROTO_LEN_2)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=Payload.ISIS_2)
        self.renix_api.edit_stream(stream, FixedLength=FrameLen.LEN_2, EnableSignature=False)
        return stream

    def add_isis_type3(self, port) -> str:
        """
        创建 isis 流量
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_3,
                                          protocolType=ProtoType.PROTO_LEN_2)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=Payload.ISIS_3)
        self.renix_api.edit_stream(stream, FixedLength=FrameLen.LEN_2, EnableSignature=False)
        return stream

    def add_isis_type4(self, port) -> str:
        """
        创建 isis 流量
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_4,
                                          protocolType=ProtoType.PROTO_LEN_3)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=Payload.ISIS_4)
        self.renix_api.edit_stream(stream, FixedLength=FrameLen.LEN_4, EnableSignature=False)
        return stream

    def add_isis_type5(self, port) -> str:
        """
        创建 isis 流量
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_5,
                                          protocolType=ProtoType.PROTO_LEN_4)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=Payload.ISIS_5)
        self.renix_api.edit_stream(stream, FixedLength=FrameLen.LEN_5, EnableSignature=False)
        return stream

    def add_isis_vlan(self, port, vlan_id) -> str:
        """
        创建 isis 流量
        :param port:
        :param vlan_id:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_VLAN_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_1)
        self.renix_api.edit_stream_header(stream, 0, 'vlan_1', id=vlan_id, protocol=ProtoType.PROTO_LEN_5)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=Payload.ISIS_6)
        self.renix_api.edit_stream(stream, FixedLength=FrameLen.LEN_6, EnableSignature=False)
        return stream

    def add_isis_dvlan(self, port, vlan_id, vlan_inner_id) -> str:
        """
        创建 isis 流量
        :param port:
        :param vlan_id:
        :param vlan_inner_id:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_VLAN_VLAN_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_3)
        self.renix_api.edit_stream_header(stream, 0, 'vlan_1', id=vlan_id)
        self.renix_api.edit_stream_header(stream, 0, 'vlan_2', id=vlan_inner_id, protocol=ProtoType.PROTO_LEN_5)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=Payload.ISIS_6)
        self.renix_api.edit_stream(stream, FixedLength=85, EnableSignature=False)
        return stream

    def add_ptp(self, port) -> str:
        """
        创建 ptp 流量
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_15,
                                          protocolType=ProtoType.PTP)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=Payload.PTP)
        self.renix_api.edit_stream(stream, FrameLengthType='Auto', EnableSignature=False)
        return stream

    def add_lldp(self, port) -> str:
        """
        创建 lldp 流量
        :param port:
        :return:
        """
        stream = self.renix_api.create_stream(port, Header.ETH_CUSTOM)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_16,
                                          protocolType=ProtoType.LLDP)
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=Payload.LLDP)
        self.renix_api.edit_stream(stream, FrameLengthType='Auto', EnableSignature=False)
        return stream

    def add_mpls_ipv4(self, port, dst_mac, count) -> str:
        """
        添加一个MPLS头个数可以自定义的流
        :param port:
        :param dst_mac:
        :param count:
        :return:
        """
        header_list = ['Ethernet.ethernetII']
        header_list.extend(['MPLS.mpls'] * count)
        header_list.append('IPv4.ipv4')
        stream = self.renix_api.create_stream(port, header_list)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=dst_mac)
        # 帧长 = 以太网头 + MPLS + IPv4头 + signature + FCS
        frame_len = 14 + 4 * count + 20 + 20 + 4
        self.renix_api.edit_stream(stream, FixedLength=frame_len, PayloadType='RANDOM')
        return stream

    def add_mpls_ipv6(self, port, dst_mac, count) -> str:
        """
        添加一个MPLS头个数可以自定义的流
        :param port:
        :param dst_mac:
        :param count:
        :return:
        """
        header_list = ['Ethernet.ethernetII']
        header_list.extend(['MPLS.mpls'] * count)
        header_list.append('IPv6.ipv6')
        stream = self.renix_api.create_stream(port, header_list)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=dst_mac)
        # 帧长 = 以太网头 + MPLS + IPv6头 + signature + FCS
        frame_len = 14 + 4 * count + 20 + 40 + 4
        self.renix_api.edit_stream(stream, FixedLength=frame_len, PayloadType='RANDOM')
        return stream

    def add_mpls_vlan(self, port, dst_mac, vlan_id, count) -> str:
        """
        添加一个VLAN+MPLS的流
        :param port:
        :param dst_mac:
        :param vlan_id:
        :param count:
        :return:
        """
        header_list = ['Ethernet.ethernetII', 'VLAN.vlan']
        header_list.extend(['MPLS.mpls'] * count)
        header_list.append('IPv4.ipv4')
        stream = self.renix_api.create_stream(port, header_list)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=dst_mac)
        self.renix_api.edit_stream_header(stream, 0, 'vlan_1', id=vlan_id)
        # 帧长 = 以太网头 + VLAN 头 + MPLS + IPv4头 + signature + FCS
        frame_len = 14 + 4 + 4 * count + 20 + 20 + 4
        self.renix_api.edit_stream(stream, FixedLength=frame_len, PayloadType='RANDOM')
        return stream

    def add_mpls_dvlan(self, port, dst_mac, vlan_id, vlan_inner_id, count, proto='802.1q') -> str:
        """
        添加一个双层VLAN+MPLS的流
        :param port:
        :param dst_mac:
        :param vlan_id:
        :param vlan_inner_id:
        :param count:
        :param proto:
        :return:
        """
        header_list = ['Ethernet.ethernetII', 'VLAN.vlan', 'VLAN.vlan']
        header_list.extend(['MPLS.mpls'] * count)
        header_list.append('IPv4.ipv4')
        stream = self.renix_api.create_stream(port, header_list)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=dst_mac)
        self.renix_api.edit_stream_header(stream, 0, 'vlan_1', id=vlan_id)
        self.renix_api.edit_stream_header(stream, 0, 'vlan_2', id=vlan_inner_id)
        # 帧长 = 以太网头 + 2*VLAN 头 + MPLS + IPv4头 + signature + FCS
        frame_len = 14 + 8 + 4 * count + 20 + 20 + 4
        self.renix_api.edit_stream(stream, FixedLength=frame_len, PayloadType='RANDOM')
        if proto == '802.1ad':
            self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', protocolType='88A8')
        return stream

    def add_pause(self, port) -> str:
        """
        添加一个pause帧
        :param port:
        :return:
        """
        header_list = Header.PAUSE
        stream = self.renix_api.create_stream(port, header_list)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_14)
        self.renix_api.edit_stream(stream, FixedLength=FrameLen.LEN_1, EnableSignature=False)
        return stream

    def add_pfc(self, port) -> str:
        """
        添加一个pfc流
        :param port:
        :return:
        """
        header_list = Header.PFC
        stream = self.renix_api.create_stream(port, header_list)
        self.renix_api.edit_stream_header(stream, 0, 'ethernetII_1', destMacAdd=Addr.MCAST_14)
        self.renix_api.edit_stream_header(stream, 0, 'pfc_1', **{'priorityEnableVector.p7': 1})
        self.renix_api.edit_stream_header(stream, 0, 'pfc_1', **{'priorityEnableVector.p6': 1})
        self.renix_api.edit_stream_header(stream, 0, 'pfc_1', **{'priorityEnableVector.p5': 1})
        self.renix_api.edit_stream_header(stream, 0, 'pfc_1', **{'priorityEnableVector.p4': 1})
        self.renix_api.edit_stream_header(stream, 0, 'pfc_1', **{'priorityEnableVector.p3': 1})
        self.renix_api.edit_stream_header(stream, 0, 'pfc_1', **{'priorityEnableVector.p2': 1})
        self.renix_api.edit_stream_header(stream, 0, 'pfc_1', **{'priorityEnableVector.p1': 1})
        self.renix_api.edit_stream_header(stream, 0, 'pfc_1', **{'priorityEnableVector.p0': 1})
        self.renix_api.edit_stream(stream, FixedLength=FrameLen.LEN_1, EnableSignature=False)
        # 配置timer
        self.renix_api.edit_stream_header(stream, 0, 'pfc_1', time0=65535)
        self.renix_api.edit_stream_header(stream, 0, 'pfc_1', time1=65535)
        self.renix_api.edit_stream_header(stream, 0, 'pfc_1', time2=65535)
        self.renix_api.edit_stream_header(stream, 0, 'pfc_1', time3=65535)
        self.renix_api.edit_stream_header(stream, 0, 'pfc_1', time4=65535)
        self.renix_api.edit_stream_header(stream, 0, 'pfc_1', time5=65535)
        self.renix_api.edit_stream_header(stream, 0, 'pfc_1', time6=65535)
        self.renix_api.edit_stream_header(stream, 0, 'pfc_1', time7=65535)
        return stream

    def add_mac_ipv4_in_mac(self, port, dst_mac) -> str:
        stream = self.renix_api.create_stream(port, Header.MAC_IN_MAC)
        self.edit_stream_header(stream, 'ethernetII_1', protocolType=ProtoType.VLAN_STAG, destMacAdd=dst_mac)
        self.edit_stream_header(stream, 'vlan_1', cfi=1, protocol=ProtoType.ITAG)
        self.edit_stream_header(stream, 'itag_1', encapCusDstAddr=dst_mac)
        self.edit_stream_header(stream, 'custom_1', customOption_0=ProtoType.IPV4)
        self.add_header(stream, 'ipv4')
        return stream

    def add_mac_ipv6_in_mac(self, port, dst_mac) -> str:
        stream = self.renix_api.create_stream(port, Header.MAC_IN_MAC)
        self.edit_stream_header(stream, 'ethernetII_1', protocolType=ProtoType.VLAN_STAG, destMacAdd=dst_mac)
        self.edit_stream_header(stream, 'vlan_1', cfi=1, protocol=ProtoType.ITAG)
        self.edit_stream_header(stream, 'itag_1', encapCusDstAddr=dst_mac)
        self.edit_stream_header(stream, 'custom_1', customOption_0=ProtoType.IPV6)
        self.add_header(stream, 'ipv6')
        return stream

    def add_mac_vlan_in_mac(self, port, dst_mac) -> str:
        stream = self.renix_api.create_stream(port, Header.MAC_IN_MAC)
        self.edit_stream_header(stream, 'ethernetII_1', protocolType=ProtoType.VLAN_STAG, destMacAdd=dst_mac)
        self.edit_stream_header(stream, 'vlan_1', cfi=1, protocol=ProtoType.ITAG)
        self.edit_stream_header(stream, 'itag_1', encapCusDstAddr=dst_mac)
        self.edit_stream_header(stream, 'custom_1', customOption_0=ProtoType.VLAN)
        self.add_header(stream, 'vlan')
        return stream

    def add_mac_mpls_in_mac(self, port, dst_mac) -> str:
        stream = self.renix_api.create_stream(port, Header.MAC_IN_MAC)
        self.edit_stream_header(stream, 'ethernetII_1', protocolType=ProtoType.VLAN_STAG, destMacAdd=dst_mac)
        self.edit_stream_header(stream, 'vlan_1', cfi=1, protocol=ProtoType.ITAG)
        self.edit_stream_header(stream, 'itag_1', encapCusDstAddr=dst_mac)
        self.edit_stream_header(stream, 'custom_1', customOption_0=ProtoType.MPLS_1)
        self.add_header(stream, 'mpls')
        return stream

    def add_mac_nsh_in_mac(self, port, dst_mac) -> str:
        stream = self.renix_api.create_stream(port, Header.MAC_IN_MAC)
        self.edit_stream_header(stream, 'ethernetII_1', protocolType=ProtoType.VLAN_STAG, destMacAdd=dst_mac)
        self.edit_stream_header(stream, 'vlan_1', cfi=1, protocol=ProtoType.ITAG)
        self.edit_stream_header(stream, 'itag_1', encapCusDstAddr=dst_mac)
        self.edit_stream_header(stream, 'custom_1', customOption_0=ProtoType.NSH)
        self.add_header(stream, 'custom')
        self.edit_stream_header(stream, 'custom_2', customOption_0=Payload.NSH_IPV4)
        self.add_header(stream, 'ipv4')
        return stream

    def add_gre(self, stream):
        """
        添加GRE头部，不添加checksum，key，sequence等字段
        :param stream:
        :return:
        """
        self.add_header(stream, 'gre')

    def add_udp_gre(self, stream):
        """
        添加UDP+GRE头部，不添加checksum，key，sequence等字段
        :param stream:
        :return:
        """
        self.add_header(stream, 'udp')
        self.edit_stream_header(stream, 'udp_1', destPort=ProtoType.GRE)
        self.add_header(stream, 'gre')

    def add_nvgre(self, stream):
        """
        添加GRE头部，将其自定义为NVGRE
        :param stream:
        :return:
        """
        self.add_header(stream, 'gre')
        self.insert_gre_key(stream)
        # self.edit_stream_header(stream, 'gre_1', )

    def insert_gre_csum(self, stream):
        checksum = random.randint(0, 65535)
        self.renix_api.edit_stream_header(stream, 0, 'gre_1', **{'checksum.GreChecksum.checksum': checksum})

    def insert_gre_key(self, stream):
        key = random.randint(0, 4294967295)
        # self.renix_api.insert_stream_node(stream, 'gre_1', 'gre_1.key', 'GreKey')
        self.renix_api.edit_stream_header(stream, 0, 'gre_1', **{'key.GreKey.key': key})

    def insert_gre_sequence(self, stream):
        sequence = random.randint(0, 4294967295)
        # self.renix_api.insert_stream_node(stream, 'gre_1', 'gre_1.sequenceNumber', 'GreSequenceNumber')
        self.renix_api.edit_stream_header(stream, 0, 'gre_1', **{'sequenceNumber.GreSequenceNumber.sequenceNumber': sequence})

    def insert_gre_route(self, stream):
        self.renix_api.edit_stream_header(stream, 0, 'gre_1', routing=1)
        self.add_header(stream, 'custom')
        self.renix_api.edit_stream_header(stream, 0, 'custom_1', customOption_0=Payload.GRE_ROUTE)

    def set_vxlan_to_vxlan_gpe(self, stream):
        self.edit_stream_header(stream, 'udp_1', destPort=ProtoType.VXLAN_GPE)
        self.edit_stream_header(stream, 'vxlan_1', flags='00001100', reserved1=3)

    def add_geneve(self, stream):
        # 添加4个custom字段，第一个填充version， length，flags；第二个填充protocol type；第三个填充VNI；第4个是padding
        self.add_header(stream, 'udp')
        self.add_header(stream, 'custom')
        self.add_header(stream, 'custom')
        self.add_header(stream, 'custom')
        self.add_header(stream, 'custom')
        self.edit_stream_header(stream, 'udp_1', destPort=ProtoType.GENEVE)
        self.edit_stream_header(stream, 'custom_1', customOption_0='0000')
        self.edit_stream_header(stream, 'custom_2', customOption_0=ProtoType.ETH)
        self.edit_stream_header(stream, 'custom_3', customOption_0='000001')
        # 补充1字节的padding使其length为4的整数倍
        self.edit_stream_header(stream, 'custom_4', customOption_0='00')

    def add_udp_mpls(self, stream):
        """
        添加UDP+GRE头部，不添加checksum，key，sequence等字段
        :param stream:
        :return:
        """
        self.add_header(stream, 'udp')
        self.edit_stream_header(stream, 'udp_1', destPort=ProtoType.MPLS_IN_UDP)
        self.add_header(stream, 'mpls')


# demo
# renix = RenixTool()
# port_1, port_2 = renix.reserve_ports()
# demo1
# interface_1, interface_2 = renix.add_interface(vlan=True, ipv6=True)
# renix.edit_interface(interface_1, {"count": 100, "vlan_pri": 2, "vlan_step": 10, "ipv6_addr": "1001::1001"})
# stream_1, stream_2 = renix.add_ipv6_binding_stream(interface_1, interface_2)
# renix.add_header(stream_1, 'icmpv6')
# demo2
# stream = renix.add_pause(port_1)
# renix.edit_port_load_type(port_1, 'stream')
# renix.edit_port_on_stream(port_1)
# renix.edit_stream_burst(stream, 1000)
# 其他
# start_capture()
# renix.start_stop_stream([stream_1])
# renix.get_port_stats(port_1, ['TxTotalFrames', 'RxTotalFrames'])
# renix.get_streamblock_stats(stream_1, ['TxStreamFrames', 'RxStreamFrames'])
# stop_capture()
# download_packets(port_1, 'D:/', 500)
# print(get_packet(port_1, 400))
# renix.save_xcfg()
# renix.disconn_chassis()

class RenixInfo:
    renix_server_list, renix_port_locations_list = CommonOperation.get_renix()
    if renix_server_list is not None:
        renix_server = renix_server_list[0]
    else:
        renix_server = None
    if renix_port_locations_list is not None:
        renix_port_locations = renix_port_locations_list.copy()
    else:
        renix_port_locations = None
