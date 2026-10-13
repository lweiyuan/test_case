#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-08-25
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_destroy_ATTACH_TO_MCG_上下文重建后detach MCG

               opcode:  SXE3R_DEVX_OP_DETACH_FROM_MCG (0x807)
               对象:    MCG（多播组）
               用例ID:  nic_linux_rdma_devx_f_06_53_007_020

               实现说明：
               创建 UD QP，使用 DevX ATTACH_TO_MCG 加入多播组后，
               调用 attach 对象的 close() 触发 DETACH_FROM_MCG，
               验证 detach 接口正确。

               环境信息来源：项目根目录下的"环境IP信息"文件。

@changelog:
    2026-08-25 初始版本，基于 DevX ATTACH_TO_MCG 测试脚本迁移生成。
"""
import os
import random
import re
import socket
import struct
import time


import add_syspath

from scripts.nic100.linux.rdma.ipvbs_screen_utils import IpvbsScreen
from scripts.script_libs import constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import (
    CmdExecuteAdressEnum,
    IpvbsCommuEnum,
    IpvbsStatusEnum,
    RtnStatusEnum,
)
from scripts.script_libs.script_base import ScriptBase


class NicLinuxRdmaDevxF0653007020PfDetachFromMcgContextrebuild(ScriptBase):
    """DevX DETACH_FROM_MCG 上下文重建后detach MCG用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_007_020'
    case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_destroy'
                  '_ATTACH_TO_MCG_上下文重建后detach MCG')
    case_module = 'DevX'
    case_type = '系统测试-功能'

    # Mellanox 固件 opcode（参见 include/linux/mlx5/mlx5_ifc.h）
    _MLX5_OP_ATTACH_TO_MCG = 0x806
    _MLX5_OP_DETACH_FROM_MCG = 0x807
    _MLX5_OP_INVALID = 0xFFF
    _ATTACH_IN_LEN = 32
    _ATTACH_OUT_LEN = 16

    _OPCODE_NAME = 'SXE3R_DEVX_OP_DETACH_FROM_MCG'
    _OBJ_TYPE = 'MCG'
    _MCG_GID = 'ff12::1'

    _ipvbs = None
    _rdma_dev = ''
    _attach_objs = []

    # 环境IP信息文件相关
    _ENV_IP_INFO_FILE_NAME = '环境IP信息'
    _env_ip_info = None

    test_object = 'RDMA MCG（多播组）'
    test_module = 'rdma'
    test_tool = 'pyverbs'
    test_precondition = (
        '1. RDMA 设备（mlx5_0）在线且 pyverbs mlx5 可用；\n'
        '2. 已部署 ipvbs 运行时（ipvbs_s.py / ipvbs.py）；\n'
        '3. 测试机与 server 节点 SSH 免密连通。'
    )
    test_steps = """1. 初始化 RDMA 测试框架与 ipvbs 会话；
2. 创建 Mlx5Context、verbs PD/CQ/UD QP；
3. attach QP 到 MCG；
4. 关闭当前 Mlx5Context；
5. 重新创建 Mlx5Context；
6. 尝试 close 旧 attach 对象，观察结果；
7. 清理资源。"""

    @classmethod
    def set_parameters(cls) -> None:
        cls.test_object = 'RDMA MCG（多播组）'
        cls.test_module = 'rdma'
        cls.test_tool = 'pyverbs'
        cls.own_environment_enabled = False
        cls._exec_addr = CmdExecuteAdressEnum.SERVER.value

    @classmethod
    def _find_env_ip_info_file(cls) -> str or None:
        """向上查找项目根目录下的"环境IP信息"文件。"""
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        while True:
            candidate = os.path.join(cur_dir, cls._ENV_IP_INFO_FILE_NAME)
            if os.path.isfile(candidate):
                return candidate
            parent = os.path.dirname(cur_dir)
            if parent == cur_dir:
                break
            cur_dir = parent
        return None

    @classmethod
    def _parse_env_ip_info(cls) -> list:
        """解析"环境IP信息"文件，返回条目列表。"""
        env_path = cls._find_env_ip_info_file()
        if not env_path:
            log.warning(f'未找到"{cls._ENV_IP_INFO_FILE_NAME}"文件，'
                        f'将使用自动探测。')
            return []

        entries = []
        pattern = re.compile(
            r'(\d+\.\d+\.\d+\.\d+)\s+'
            r'端口号\s*(\d+)\s+'
            r'用户名\s*(\S+)\s+'
            r'密码\s*(\S+)\s+'
            r'设备\s*(\S+)'
        )
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    match = pattern.match(line)
                    if not match:
                        log.warning(f'环境信息行格式不匹配，已跳过: {line}')
                        continue
                    ip, port, username, password, device = match.groups()
                    entries.append({
                        'ip': ip,
                        'port': int(port),
                        'username': username,
                        'password': password,
                        'device': device,
                    })
        except Exception as e:
            log.error(f'读取"{env_path}"失败: {e}')
            return []
        return entries

    @classmethod
    def _get_env_entry_for_exec_addr(cls) -> dict or None:
        """根据当前执行地址选择对应的环境条目。"""
        if not cls._env_ip_info:
            return None
        if cls._exec_addr == CmdExecuteAdressEnum.SERVER.value:
            index = 0
        elif cls._exec_addr == CmdExecuteAdressEnum.CLIENT.value:
            index = 1
        else:
            return None
        if index < len(cls._env_ip_info):
            return cls._env_ip_info[index]
        return None

    @classmethod
    def _report_env_error(cls, msg: str) -> None:
        """局部环境检查失败时记录日志并禁用本用例。"""
        log.error(msg)
        cls.own_environment_enabled = False

    @classmethod
    def check_own_environment(cls) -> None:
        """检查局部环境：RDMA 设备存在且 pyverbs mlx5 DevX 可用。"""
        log.info('开始检查局部环境。')
        cls.own_environment_enabled = False
        cls._env_ip_info = cls._parse_env_ip_info()

        env_entry = cls._get_env_entry_for_exec_addr()
        if env_entry:
            cls._rdma_dev = env_entry['device']
            log.info(
                f'从"环境IP信息"读取到执行端[{cls._exec_addr}]信息: '
                f"ip={env_entry['ip']}, port={env_entry['port']}, "
                f"username={env_entry['username']}, device={cls._rdma_dev}"
            )
        else:
            log.warning('未从"环境IP信息"获取到设备信息，将自动探测。')

        status, result, err = CommandOperation.execute_command_with_error(
            'ls /sys/class/infiniband/ 2>/dev/null', cls._exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or not result.strip():
            cls._report_env_error(f'未检测到 RDMA 设备, err={err}')
            return
        dev_list = result.split()
        if cls._rdma_dev and cls._rdma_dev not in dev_list:
            cls._report_env_error(
                f'指定的 RDMA 设备 {cls._rdma_dev} 不存在，'
                f'当前设备列表: {dev_list}')
            return
        if not cls._rdma_dev:
            cls._rdma_dev = dev_list[0]
        log.info(f'检测到 RDMA 设备: {dev_list}, 本用例使用: {cls._rdma_dev}')

        cmd_check = (
            "python3 -c 'from pyverbs.providers.mlx5.mlx5dv import "
            "Mlx5Context, Mlx5DVContextAttr, Mlx5DevxObj; "
            "print(\\\"mlx5_devx_ok\\\")'"
        )
        status, result, err = CommandOperation.execute_command_with_error(
            cmd_check, cls._exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or \
                'mlx5_devx_ok' not in (result or ''):
            cls._report_env_error(f'pyverbs mlx5 DevX 不可用: {err}')
            return
        log.info(f'pyverbs mlx5 DevX 可用: {result.strip()}')
        cls.own_environment_enabled = True

    @classmethod
    def prepare(cls) -> None:
        log.info(f'prepare: 初始化 DETACH_FROM_MCG 测试环境 (dev={cls._rdma_dev})。')
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 DETACH_FROM_MCG 测试环境。')
            return
        cls._attach_objs = []
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)

        setup_cmds = [
            # 加载常用模块
            "glb_struct = __import__('struct')",
            "glb_socket = __import__('socket')",
            "glb_pyverbs_pd = __import__('pyverbs.pd', fromlist=['PD'])",
            "glb_pyverbs_cq = __import__('pyverbs.cq', fromlist=['CQ'])",
            "glb_pyverbs_qp = __import__('pyverbs.qp', fromlist=['QP', 'QPCap', 'QPInitAttr'])",
            # 加载 pyverbs mlx5 DevX 模块
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', "
            "fromlist=['Mlx5Context', 'Mlx5DVContextAttr', 'Mlx5DevxObj'])",
            "glb_Mlx5Context = glb_mlx5dv.Mlx5Context",
            "glb_Mlx5DVContextAttr = glb_mlx5dv.Mlx5DVContextAttr",
            "glb_Mlx5DevxObj = glb_mlx5dv.Mlx5DevxObj",
            # 创建 Mlx5Context
            f"glb_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '{cls._rdma_dev}')",
            # 创建 verbs PD/CQ/UD QP
            "glb_pd = glb_pyverbs_pd.PD(glb_ctx)",
            "glb_cq = glb_pyverbs_cq.CQ(glb_ctx, 16)",
            "glb_cap = glb_pyverbs_qp.QPCap(max_recv_wr=1, max_send_wr=1, "
            "max_recv_sge=1, max_send_sge=1)",
            "glb_init = glb_pyverbs_qp.QPInitAttr(qp_type=4, scq=glb_cq, "
            "rcq=glb_cq, cap=glb_cap, sq_sig_all=1)",
            "glb_qp = glb_pyverbs_qp.QP(glb_pd, init_attr=glb_init)",
            "glb_qpn = glb_qp.qp_num",
            # 多播组 GID
            f"glb_gid = glb_socket.inet_pton(glb_socket.AF_INET6, '{cls._MCG_GID}')",
            # attach buffer 构造 lambda
            "glb_build_attach_in = lambda qpn, gid, opcode=0x806, _struct=glb_struct: "
            "_struct.pack('>HHHH', opcode, 0, 0, 0) + "
            "_struct.pack('>B', 0) + _struct.pack('>I', qpn)[1:] + "
            "_struct.pack('>I', 0) + gid",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'初始化 DETACH_FROM_MCG 环境失败, dev={cls._rdma_dev}, '
                    f'cmd={cmd}, rtn={result}')
                return
        log.info('Mlx5Context / PD / CQ / UD QP 创建成功。')

    @classmethod
    def do(cls) -> None:
        log.info('do: DevX DETACH_FROM_MCG 上下文重建后detach MCG测试。')
        cls._do_context_rebuild_detach()


    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 DETACH_FROM_MCG 资源。')
        # 释放显式保存的 attach 对象
        for name in list(cls._attach_objs):
            cls._ipvbs.exec_and_get_ipvbs_result(f'{name}.close()')
        cls._attach_objs = []
        # 释放 QP/CQ/PD/Context
        if cls._ipvbs is not None:
            cls._ipvbs.exec_and_get_ipvbs_result('glb_qp.close()')
            cls._ipvbs.exec_and_get_ipvbs_result('glb_cq.close()')
            cls._ipvbs.exec_and_get_ipvbs_result('glb_pd.close()')
            cls._ipvbs.exec_and_get_ipvbs_result('glb_ctx.close()')
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    # ------------------------------------------------------------------ #
    #  MCG attach/detach 辅助方法                                           #
    # ------------------------------------------------------------------ #

    @classmethod
    def _attach_qpn_to_mcg(cls, obj_name: str, qpn_var: str, gid_var: str) -> tuple:
        """将指定 qpn attach 到 MCG，返回 (status, result)。"""
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"{obj_name} = glb_Mlx5DevxObj(glb_ctx, glb_build_attach_in({qpn_var}, {gid_var}), 16)")
        if status == IpvbsStatusEnum.SUCCESS.value:
            cls._attach_objs.append(obj_name)
        return status, result

    @classmethod
    def _close_attach_obj(cls, obj_name: str) -> bool:
        """关闭 attach 对象以触发 detach，返回是否成功。"""
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(f"{obj_name}.close()")
        if status == IpvbsStatusEnum.SUCCESS.value:
            log.info(f'attach 对象关闭成功 (detach): {obj_name}')
            if obj_name in cls._attach_objs:
                cls._attach_objs.remove(obj_name)
            return True
        log.warning(f'attach 对象关闭异常: {obj_name}, rtn={result}')
        return False

    @classmethod
    def _do_context_rebuild_detach(cls) -> None:
        """CP1: context 重建后 close/detach 旧 MCG。"""
        log.info('[CP1] context 重建后 close/detach 旧 MCG。')
        status, result = cls._attach_qpn_to_mcg('glb_attach_cp1', 'glb_qpn', 'glb_gid')
        if status != IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'attach 失败: {result}')
            return
        cls._ipvbs.exec_and_get_ipvbs_result("glb_old_ctx = glb_ctx")
        cls._ipvbs.exec_and_get_ipvbs_result("glb_old_attach = glb_attach_cp1")
        status, _ = cls._ipvbs.exec_and_get_ipvbs_result(
            f"glb_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '{cls._rdma_dev}')")
        if status != IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug('重建 Mlx5Context 失败')
            return
        status, result = cls._ipvbs.exec_and_get_ipvbs_result("glb_old_attach.close()")
        if status == IpvbsStatusEnum.SUCCESS.value:
            log.warning('旧 context 的 attach 对象在 context 重建后仍可 close，可能存在风险')
        else:
            log.info('旧 context 的 attach 对象在 context 重建后 close 失败，符合隔离预期。')
        cls._ipvbs.exec_and_get_ipvbs_result("glb_old_ctx.close()")



if __name__ == '__main__':
    NicLinuxRdmaDevxF0653007020PfDetachFromMcgContextrebuild().run()
