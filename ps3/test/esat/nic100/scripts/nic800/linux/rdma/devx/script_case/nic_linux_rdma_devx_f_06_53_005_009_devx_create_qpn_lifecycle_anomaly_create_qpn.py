#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-08-18
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_create_ReservedQPN创建_生命周期异常ReservedQPN

               验证 block 被销毁后，其 QPN 不可再次使用/关联。

               opcode:  SXE3R_DEVX_OP_CREATE_GENERAL_OBJECT
               obj_type: MLX5_OBJ_TYPE_RESERVED_QPN (0x002C)
               对象:    Reserved QPN（预留队列对编号）
               用例ID:  nic_linux_rdma_devx_f_06_53_005_009

               实现说明：
               在 CX8 / mlx5 设备上通过 pyverbs 的 Mlx5DevxObj 直接下发
               固件 CREATE_GENERAL_OBJECT 命令（opcode=0xa00, obj_type=0x002C）
               创建 Reserved QPN block，验证 first_qpn 有效、唯一且可正常释放。

@changelog:
    2026-08-18 初始版本。
"""
import os
import re

import add_syspath

from scripts.nic100.linux.rdma.ipvbs_screen_utils import IpvbsScreen
from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.file_operation import FileOperation
from scripts.script_libs.enums import (
    CmdExecuteAdressEnum,
    IpvbsCommuEnum,
    IpvbsStatusEnum,
    RtnStatusEnum,
)
from scripts.script_libs.script_base import ScriptBase


class NicLinuxRdmaDevxF0653005009PfCreateQpnLifecycle_AnomalyCreateQpn(ScriptBase):
    """DevX Reserved QPN 正常创建用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_005_009'
    case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_create_ReservedQPN创建_生命周期异常ReservedQPN')
    test_steps = (
        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\n'        '2. 创建 block 并记录 first_qpn；\n'        '3. 销毁该 block；\n'        '4. 再次创建新 block，验证新 first_qpn 与旧值不同；\n'        '5. 释放资源并清理环境。'
    )

    @classmethod
    def set_parameters(cls) -> None:
        cls.test_object = 'RDMA Reserved QPN（预留队列对编号）'
        cls.test_module = 'rdma'
        cls.test_tool = 'pyverbs'
        cls.own_environment_enabled = False
        cls._exec_addr = CmdExecuteAdressEnum.SERVER.value

    @classmethod
    def _find_env_ip_info_file(cls) -> str or None:
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
        env_path = cls._find_env_ip_info_file()
        if not env_path:
            log.warning(f'未找到"{cls._ENV_IP_INFO_FILE_NAME}"文件，将使用自动探测。')
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
        log.error(msg)
        cls.own_environment_enabled = False

    @classmethod
    def check_own_environment(cls) -> None:
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
    def _deploy_helper_if_needed(cls) -> None:
        remote_helper = '/root/sxetest/devx_qp_helper.py'
        local_helper = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', 'devx_qp_helper.py'
        )
        local_helper = os.path.normpath(local_helper)
        if not os.path.isfile(local_helper):
            log.warning(f'本地 helper 文件不存在: {local_helper}，跳过自动部署。')
            return

        env_entry = cls._get_env_entry_for_exec_addr()
        ip = env_entry.get('ip') if env_entry else None
        port = str(env_entry.get('port')) if env_entry else '22'
        if not ip:
            log.warning('无法获取执行端 IP，跳过 helper 自动部署。')
            return

        remote_dir = os.path.dirname(remote_helper)
        CommandOperation.execute_command_with_error(
            f'mkdir -p {remote_dir}', cls._exec_addr)

        log.info(f'正在同步 helper 到远程: {local_helper} -> '
                 f'{ip}:{remote_helper}')
        rtn, _, _ = FileOperation.scp_file_to_remote(
            localfile_path=local_helper,
            remotefile_path=remote_helper,
            ip=ip,
            port=port,
            cmd_execute_address=cls._exec_addr
        )
        if rtn != RtnStatusEnum.SUCCESS.value:
            log.warning(f'helper 自动部署可能失败，rtn={rtn}')
        else:
            log.info('helper 自动部署完成。')

    @classmethod
    def prepare(cls) -> None:
        log.info(f'prepare: 初始化 Reserved QPN 测试环境 '
                 f'(opcode={cls._OPCODE_NAME}, dev={cls._rdma_dev})。')
        cls._qpn_objs = {}
        cls._first_qpns = {}
        cls._reserved_qpn_supported = False
        cls._max_log_range = 0
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 Reserved QPN 测试环境。')
            return

        cls._ipvbs = IpvbsScreen(
            caller_class=cls, exec_addr=cls._exec_addr,
            commu=IpvbsCommuEnum.SOCKET.value)
        cls._deploy_helper_if_needed()

        setup_cmds = [
            "__import__('sys').path.insert(0, '/root/sxetest')",
            "glb_helper = __import__('devx_qp_helper')",
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', "
            "fromlist=['Mlx5Context', 'Mlx5DVContextAttr'])",
            "glb_Mlx5Context = glb_mlx5dv.Mlx5Context",
            "glb_Mlx5DVContextAttr = glb_mlx5dv.Mlx5DVContextAttr",
            f"glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), "
            f"'{cls._rdma_dev}')",
            "glb_caps = glb_helper.query_reserved_qpn_caps(glb_mlx5_ctx)",
            "glb_supported = glb_caps[0]",
            "glb_max_log = glb_caps[1]",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'初始化 Reserved QPN 环境失败, dev={cls._rdma_dev}, '
                    f'cmd={cmd}, rtn={result}')
                return

        status, supported = cls._ipvbs.exec_and_get_ipvbs_result(
            "str(glb_supported)")
        if status == IpvbsStatusEnum.SUCCESS.value:
            cls._reserved_qpn_supported = (supported or '').strip() == 'True'

        status, max_log = cls._ipvbs.exec_and_get_ipvbs_result(
            "str(glb_max_log)")
        if status == IpvbsStatusEnum.SUCCESS.value:
            try:
                cls._max_log_range = int((max_log or '').strip() or 0)
            except ValueError:
                cls._max_log_range = 0

        log.info(f'Reserved QPN 能力: supported={cls._reserved_qpn_supported}, '
                 f'max_log_range={cls._max_log_range}')

        if not cls._reserved_qpn_supported:
            log.warning('当前设备/固件不支持 Reserved QPN，本用例跳过。')
            cls.own_environment_enabled = False
            return

    @classmethod
    def do(cls) -> None:
        if not cls._reserved_qpn_supported:
            log.warning('当前设备/固件不支持 Reserved QPN，跳过 do 阶段。')
            return
        log.info('do: DevX Reserved QPN 生命周期异常测试。')
        status, first_qpn0 = cls._create_qpn_block('obj_qpn_life', 0)
        if status != IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug('生命周期测试初始创建失败')
            return
        cls._close_qpn_block('obj_qpn_life')
        status, first_qpn1 = cls._create_qpn_block('obj_qpn_life2', 0)
        if status != IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug('销毁后重新创建 block 失败')
            return
        if first_qpn0 == first_qpn1:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'销毁后分配了相同 first_qpn: {first_qpn1}')
            return
        log.info(f'生命周期异常测试通过: {first_qpn0} -> {first_qpn1}')

    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 Reserved QPN 资源 '
                 f'(共 {len(cls._first_qpns)} 个 block)。')
        for name in list(cls._first_qpns.keys()):
            cls._close_qpn_block(name)
        cls._qpn_objs = {}
        cls._first_qpns = {}
        if cls._ipvbs is not None:
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    @classmethod
    def _create_qpn_block(cls, name: str, log_obj_range: int = 0) -> tuple:
        glb_name = f'glb_{name}'
        create_cmds = [
            f"{glb_name}_ret = glb_helper.create_reserved_qpn("
            f"glb_mlx5_ctx, {log_obj_range})",
            f"{glb_name} = {glb_name}_ret[0]",
            f"{glb_name}_first = {glb_name}_ret[1]",
        ]
        for cmd in create_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                log.error(f'DevX CREATE_GENERAL_OBJECT(RESERVED_QPN) 失败: '
                          f'{cmd}, rtn={result}')
                return status, None

        status, first_qpn = cls._ipvbs.exec_and_get_ipvbs_result(
            f"str({glb_name}_first)")
        if status != IpvbsStatusEnum.SUCCESS.value:
            return status, None

        cls._qpn_objs[name] = glb_name
        first_qpn = (first_qpn or '').strip()
        cls._first_qpns[name] = first_qpn
        log.info(f'Reserved QPN block 创建成功: {name}, '
                 f'log_range={log_obj_range}, first_qpn={first_qpn}')
        return IpvbsStatusEnum.SUCCESS.value, first_qpn

    @classmethod
    def _close_qpn_block(cls, name: str) -> bool:
        glb_name = cls._qpn_objs.get(name)
        if not glb_name:
            return False
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"glb_helper.destroy_reserved_qpn({glb_name})")
        if status == IpvbsStatusEnum.SUCCESS.value:
            log.info(f'Reserved QPN block 释放成功: {name}')
            cls._qpn_objs.pop(name, None)
            cls._first_qpns.pop(name, None)
            return True
        log.warning(f'Reserved QPN block 释放异常: {name}, rtn={result}')
        return False

    @classmethod
    def _do_lifecycle_anomaly_create_qpn(cls) -> None:
        log.info('[CP1] 正常分配单个 Reserved QPN block。')
        status, first_qpn = cls._create_qpn_block('obj_qpn_cp1', 0)
        if status != IpvbsStatusEnum.SUCCESS.value or not first_qpn:
            cls.set_bug_type('功能问题')
            cls.create_bug('正常分配 Reserved QPN block 失败，'
                           '期望 DevX CREATE_GENERAL_OBJECT 成功并返回有效 first_qpn。')
            return
        if not first_qpn.isdigit():
            cls.set_bug_type('功能问题')
            cls.create_bug(f'first_qpn 非法: {first_qpn}，期望为数值型 QPN。')

    @classmethod
    def _do_batch_create_qpn(cls) -> None:
        n = cls._QPN_BLOCK_COUNT
        log.info(f'[CP2] 连续分配 {n} 个 Reserved QPN block。')
        first_qpns = []
        for i in range(n):
            name = f'obj_qpn_cp2_{i}'
            status, first_qpn = cls._create_qpn_block(name, 0)
            if status != IpvbsStatusEnum.SUCCESS.value or not first_qpn:
                cls.set_bug_type('功能问题')
                cls.create_bug(f'批量分配第 {i + 1}/{n} 个 block 失败。')
                return
            first_qpns.append(first_qpn)
        if len(set(first_qpns)) != n:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'{n} 个 block 的 first_qpn 不唯一: {first_qpns}。')


if __name__ == '__main__':
    NicLinuxRdmaDevxF0653005009PfCreateQpnLifecycle_AnomalyCreateQpn().run()
