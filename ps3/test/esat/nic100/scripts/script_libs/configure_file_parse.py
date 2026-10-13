#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      haibin.xu
date:        2020.10.14 16:14
@summary:    各种配置文件的解析

@steps:

@changelog:

"""
import os
import re
import copy
from xml.etree import ElementTree

from scripts.script_libs import log
from scripts.script_libs.enums import RtnStatusEnum


class ConfigureFileParse(object):
    def __init__(self, configure_file_path: str):
        # 模拟平台配置文件路径
        self.configure_file_path = configure_file_path
        self.tree_obj = self.__parse_xml()

    def __configure_file_exists(self) -> bool:
        """
        author:      haibin.xu
        date:        2020-10-26 16:20:33
        description: 检查配置文件是否存在，不存在的话，报错，抛出异常

        :return:     存在返回True，不存在抛异常退出
        """
        rtn_exist = False

        if os.path.exists(self.configure_file_path):
            rtn_exist = True
        else:
            log.error('Not found configure file: {}'.format(self.configure_file_path))

        return rtn_exist

    def __parse_xml(self) -> ElementTree:
        """
        author:      haibin.xu
        date:        2020-10-26 16:13:12
        description: 检查 xml 文件格式的正确性, 并解析xml文件

        :return:     xml 文件格式正确，返回xml解析对象，不正确，报错抛出异常
        """
        tree_obj = None

        try:
            if self.__configure_file_exists():
                tree_obj = ElementTree.parse(self.configure_file_path)
        except Exception:
            log.error('Found format error in xml file: {}'.format(self.configure_file_path))

        return tree_obj

    def get_root_node(self) -> ElementTree.Element:
        """
        author:      haibin.xu
        date:        2020-10-26 16:32:31
        description: 获取xml文件的根节点对象

        :return:    返回xml文件的根节点对象
        """
        return self.tree_obj.getroot() if self.tree_obj is not None else None

    def get_node_of_given_node_name(self, node_name: str) -> list:
        """
        author:      haibin.xu
        date:        2020-10-26 16:45:48
        description: 根据node_name查找xml 文件下所有对应的节点对象,根据其格式的不同可以获取对应层级的节点对象。

        :param node_name: 指定节点名，当node_name为"base_node/child_node/***"的格式时，表示获取根节点下的
                          base_node节点中的child_node节点中的***节点对象，即表示其层级关系。
        :return:     返回指定节点名的所有节点对象
        """
        node_list = []

        if not node_name:
            log.error('Invalid node_name: {}'.format(node_name))
        elif self.tree_obj is None:
            log.error('Invalid tree object.')
        else:
            for elem in self.tree_obj.iterfind(node_name):
                node_list.append(elem)

        return node_list

    @staticmethod
    def get_node_value(node_obj: ElementTree.Element, node_name: str) -> str:
        """
        author:      haibin.xu
        date:        2020-10-26 20:10:55
        description: 获取节点对象指定子节点的值

        :param node_obj: 节点对象
        :param node_name: 子节点名
        :return:    返回节点内指定子节点的值
        """
        node_text = ''

        sub_node_obj = node_obj.find(node_name)
        if sub_node_obj is not None:
            node_text = sub_node_obj.text

        return node_text

    def __parse_node(self, parent_node: ElementTree.Element) -> dict:
        """
        author:      haibin.xu
        date:        2021-03-06 13:43:12
        description: 将xml节点数据解析到dict中

        :param parent_node: 待解析的节点
        :return:     返回节点数据解析的dict类型
        """
        def get_keys_in_dictlist(node_list: list) -> list:
            """
            author:      haibin.xu
            date:        2021-03-06 14:27:36
            description: 获取字典组成的列表中所有字典的键

            :param node_list: 字典组成的列表
            :return:     返回所有字典的键组成的列表类型
            """
            keys_list = []
            for n_dict in node_list:
                keys_list.extend(n_dict.keys())

            return keys_list

        def add_new_node_value(node_list: list, new_node: dict) -> list:
            """
            author:      haibin.xu
            date:        2021-03-06 14:51:41
            description: 将节点值加入节点列表中相同节点标签对应的列表中

            :param node_list: 节点列表
            :param new_node:  节点字典类型
            :return:          返回插入新节点值的节点列表
            """
            if 1 != len(new_node):
                log.error('node must be only one element.')
            else:
                new_node_key = None
                new_node_value = None
                for key, value in new_node.items():
                    new_node_key = key
                    new_node_value = value

                temp_list = copy.deepcopy(node_list)
                for i in range(len(node_list)):
                    if (new_node_key is not None) and (new_node_value is not None) and \
                            (new_node_key == list(node_list[i].keys())[0]):
                        temp_list[i][new_node_key].extend(new_node_value)
                        break

                node_list = temp_list

            return node_list

        if 0 == len(list(parent_node)):
            node_data_dict = {parent_node.tag: [parent_node.text]}
        else:
            parent_node_value_list = []
            for sub_node in list(parent_node):
                sub_node_dict = self.__parse_node(parent_node=sub_node)
                key_list = get_keys_in_dictlist(node_list=parent_node_value_list)
                if sub_node.tag not in key_list:
                    parent_node_value_list.append(sub_node_dict)
                else:
                    parent_node_value_list = add_new_node_value(parent_node_value_list, sub_node_dict)

            node_data_dict = {parent_node.tag: parent_node_value_list}

        return node_data_dict

    def convert_xml_to_dict(self) -> dict:
        """
        author:      haibin.xu
        date:        2021-03-06 11:17:45
        description: 将xml文件内的节点信息转换成字典类型

        :return:     返回转换成功的字典数据
        """
        root_node = self.get_root_node()
        xml_dict = {root_node.tag: []}
        if 0 == len(list(root_node)):
            log.warning('Not found sub node in root node.')
        else:
            root_node_value_list = []
            for sub_node in list(root_node):
                root_node_value_list.append(self.__parse_node(sub_node))
            xml_dict = {root_node.tag: root_node_value_list}

        return xml_dict

    @staticmethod
    def write_xml(tree_obj: ElementTree.ElementTree = None, file_path: str = None) -> int:
        """
        author:      haibin.xu
        date:        2021-03-11 14:13:04
        description: Write element tree to a file as XML

        :param tree_obj: 待要写入文件的ElementTree对象
        :param file_path: 保存文件名，后缀必须为xml
        :return:     写文件成功返回0， 失败返回-1
        """
        rtn_write_file = RtnStatusEnum.SUCCESS.value

        if os.path.exists(os.path.dirname(file_path)) and re.match(r'.*\.xml', file_path):
            if isinstance(tree_obj, ElementTree.ElementTree):
                try:
                    tree_obj.write(file_path, encoding='utf-8', xml_declaration=True)
                except Exception as e:
                    log.error('Fail to write xml file: {}. Reason: {}.'.format(file_path, e))
                    rtn_write_file = RtnStatusEnum.FAIL.value
            else:
                log.error('element tree: {}, type: {}. is not Elementree type.'.format(tree_obj, type(tree_obj)))
                rtn_write_file = RtnStatusEnum.FAIL.value
        else:
            log.error('File directory: {}, is not exists. Or file: {} is not xml file.'.format(
                os.path.dirname(file_path), file_path))
            rtn_write_file = RtnStatusEnum.FAIL.value

        return rtn_write_file
