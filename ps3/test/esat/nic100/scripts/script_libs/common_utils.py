#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import add_syspath
import os
import re
import sys
import time
import json
import random
import threading
import itertools
from typing import Union
from datetime import datetime


class CommonUtils:
    case_cls = None
    cmd_collection = None
    cmd_collection_patched = False
    # 匹配文本中是否有指定序号
    serial_detect_pattern = r'^\d+\.(\d+\.)? '
    # 截取文本中的指定序号
    serial_match_pattern = r'^(\d+)\.((\d+)\.)? '

    @classmethod
    def set_case_cls(cls, case_cls):
        """
        author:      cheng.peng
        date:        2021-06-28
        description: 绑定工具类的当前script_base
        """
        cls.case_cls = case_cls

    @staticmethod
    def patch_log_format(log):
        """
        author: cheng.peng
        date: 2021.04.22
        description: 适用于小屏幕的log formatter, 更加可读
                     仅应该用在 Windows 调试中
                     在正式的 Linux 执行环境里, 应该按照原先规范生成log
                     将做这几个事:
                        将 [INFO] [ERROR] 染色
                        代码 pyfile.py:linenum 行数染色
                        cli命令, 但凡解析出来就染色
                        删除没什么信息量的文本片段
        """

        # def __get_format_msg(msg: str, module_name: str, line_num: int, func_name: str, level_name: str) -> str:
        #     asctime = datetime.datetime.now().strftime('%y-%m-%d %H:%M:%S')
        #     formatter_msg = '[{}] {:25s} {:20s} {:4s} {:8s}: {}'.format(
        #                      asctime, module_name, func_name, str(line_num), level_name, msg)
        #     return formatter_msg

        def shell_color(text, color='cyan'):
            color_dict = {
                'black': '0;30', 'darkgray': '1;30', 'red': '0;31', 'lightred': '1;31',
                'green': '0;32', 'lightgreen': '1;32', 'orange': '0;33', 'yellow': '1;33',
                'blue': '0;34', 'lightblue': '1;34', 'purple': '0;35', 'lightpurple': '1;35',
                'cyan': '0;36', 'lightcyan': '1;36', 'lightgray': '0;37', 'white': '1;37',
            }
            return "\033[{}m{}\033[0m".format(color_dict.get(color, '0'), text)

        def __new_get_format_msg(msg: str, module_name: str, line_num: int, func_name: str,
                                 level_name: str, format_flag: bool = True) -> str:
            asctime = shell_color(
                datetime.now().strftime('%H%M%S'),
                'orange')  # 临时使用, 不需要年月日
            script_position = shell_color(
                f'{module_name}:{line_num}', 'lightcyan')
            level_name = {
                'INFO': shell_color(level_name, 'orange'),
                'WARN': shell_color(level_name, 'yellow'),
                'ERROR': shell_color(level_name, 'red'),
            }.get(level_name, shell_color(level_name, 'blue'))

            eliminated = '-o StrictHostKeyChecking=no -o TcpKeepAlive=yes -o ServerAliveInterval=30 '
            eliminated += '-o ServerAliveCountMax=5 -l root'
            msg = str(msg).replace(eliminated, '...')
            eliminated = ' [\\s*Status\\s*=\\s*Success, or, \\s*"Status":\\s*"Success"].'
            msg = msg.replace(eliminated, '...Status=Success...')
            msg = msg.replace('ssh host: root@', '@')
            # eliminated = 'Connected (version 2.0, client OpenSSH_7.4)'
            # msg = msg.replace(eliminated, '...')
            # eliminated = 'Authentication (publickey) successful!'
            # msg = msg.replace(eliminated, '...')
            if 'All satisfy ' in msg or 'After sort policy:' in msg:
                msg = msg[:50] + ' ...'  # 去掉 PD json output

            msg = re.sub(
                r'("(?:time )?cli .+?")',
                r' \033[0;35m\1\033[0m',
                msg)
            msg = re.sub(
                r'Command: ((?:time )?cli .+?), execute',
                r' \033[0;35m"\1"\033[0m',
                msg)
            msg = re.sub(r', cmd: ((?:time )?cli .+?)$',
                         r' \033[0;35m"\1"\033[0m', msg)
            msg = re.sub(r', cmd: ((?:time )?cli .+?)$',
                         r' \033[0;35m"\1"\033[0m', msg)
            msg = re.sub(
                r'sending cmd `(cli .+?)`',
                r' \033[0;35m"\1"\033[0m',
                msg)

            msg = '\n'.join('  ' + line for line in msg.strip().splitlines())
            func_name = func_name + '()' if len(func_name) <= 20 else func_name[:17] + '...()'
            func_name = shell_color(func_name, 'lightcyan')
            if f'"{constants.SCGBECLI64} /c0 show j trace"' in msg:
                # 略过这种日志, 太多没用
                formatter_msg = f'[{asctime}][{level_name}] "{constants.SCGBECLI64} /c0 show j trace" ... '
            else:
                formatter_msg = f'[{asctime}][{level_name}] {script_position} in {func_name}: \n{msg}'
            return formatter_msg

        setattr(log, '__get_format_msg', __new_get_format_msg)

    @staticmethod
    def patch_collect_commands():
        """
        author: cheng.peng
        date: 2021.04.22
        description: 收集本地发送过的所有cli命令
        """
        if CommonUtils.cmd_collection_patched:
            return  # 有可能已经调用过了, 这时重复包装会导致在 CommonUtils.cmd_collection 里记录两次 cmds
        CommonUtils.cmd_collection = []

        old_executor1 = getattr(CommandOperation,
                                'execute_command_based_paramiko_with_rtncode')

        def new_executor1(*args, **kwargs):
            cmd = kwargs.get('cmd') or args[0]
            CommonUtils.cmd_collection.append(cmd)
            return old_executor1(*args, **kwargs)

        old_executor2 = getattr(CommandOperation, 'execute_command_with_error')

        def new_executor2(*args, **kwargs):
            cmd = kwargs.get('cmd') or args[0]
            CommonUtils.cmd_collection.append(cmd)
            return old_executor2(*args, **kwargs)

        setattr(
            CommandOperation,
            'execute_command_based_paramiko_with_rtncode',
            new_executor1)
        setattr(CommandOperation, 'execute_command_with_error', new_executor2)
        CommonUtils.cmd_collection_patched = True
