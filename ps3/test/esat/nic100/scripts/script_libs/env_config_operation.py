#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:     sunql
date:       2020-08-21
@summary:   解析框架env_config
"""

import os

from scripts.script_libs.configure_file_parse import ConfigureFileParse


class EnvConfigOperation(object):
    env_config_file_path = None
    env_config = []

    def __init__(self):
        self.env_config_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                                 'framework', 'env_conf', 'env_config.xml')
        if os.path.exists(self.env_config_file_path):
            self.env_config = ConfigureFileParse(self.env_config_file_path).\
                convert_xml_to_dict().get('env_config', [])

    def get_config_item(self, item: str) -> str or None:
        """
        根据节点key获取env conf 对应 value
        :param item: str
        :return: str
        """
        if len(self.env_config) > 0:
            for i in self.env_config:
                for k in i:
                    if k == item:
                        return (i[k])[0]
        return None

    def get_env_long_stab_test(self) -> bool:
        """
        获取 env config 长稳开关
        :return:bool
        """
        long_stab_test = str(self.get_config_item('long_stab_test') or '').strip()
        if long_stab_test == 'yes':
            return True
        return False
