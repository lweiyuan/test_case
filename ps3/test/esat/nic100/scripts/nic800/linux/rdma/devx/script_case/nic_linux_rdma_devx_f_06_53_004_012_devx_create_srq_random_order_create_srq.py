#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-08-14
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_create_SRQ创建_随机顺序创建释放SRQ

               opcode:  SXE3R_DEVX_OP_CREATE_SRQ
               对象:    SRQ（共享接收队列）
               用例ID:  nic_linux_rdma_devx_f_06_53_004_012

               实现说明：
               在 CX8 / mlx5 设备上通过 pyverbs 的 Mlx5DevxObj 直接下发
               固件 CREATE_SRQ 命令（opcode=0x700）创建 SRQ，验证 SRQ 号有效、
               唯一且可正常释放。

               环境信息来源：项目根目录下的"环境IP信息"文件，
               按 server/client 顺序解析 IP、端口、用户名、密码及 RDMA 设备名。

@changelog:
    2026-08-14 初始版本，基于 DevX QP 测试脚本模板迁移。
"""
import os
import random
import re
import time


import add_syspath

from scripts.nic100.linux.rdma.ipvbs_screen_utils import IpvbsScreen
from scripts.script_libs import constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.file_operation import FileOperation
from scripts.script_libs.enums import (
    CmdExecuteAdressEnum,
    IpvbsCommuEnum,
    IpvbsStatusEnum,
    RtnStatusEnum,
)
from scripts.script_libs.script_base import ScriptBase


class NicLinuxRdmaDevxF0653012PfCreateSrqRandomOrder(ScriptBase):
    """DevX SRQ 随机顺序创建释放SRQ用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_004_012'
    case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_create'
                  '_SRQ创建_随机顺序创建释放SRQ')
    case_module = 'DevX'
    case_type = '系统测试-功能'

    # Mellanox 固件 opcode（参见 include/linux/mlx5/mlx5_ifc.h）
    _MLX5_OP_CREATE_SRQ = 0x700
    _MLX5_OP_DESTROY_SRQ = 0x701

    _OPCODE_NAME = 'SXE3R_DEVX_OP_CREATE_SRQ'
    _OBJ_TYPE = 'SRQ'
    _SRQ_COUNT = 5
    _OPERATION_COUNT = 20
    _MAX_CONCURRENT_SRQ = 5
    _RANDOM_SEED = 42

    _ipvbs = None
    _rdma_dev = ''
    _srq_objs = []

    # 环境IP信息文件相关
    _ENV_IP_INFO_FILE_NAME = '环境IP信息'
    _env_ip_info = None

    test_object = 'RDMA SRQ（共享接收队列）'
    test_module = 'rdma'
    test_tool = 'pyverbs'
    test_precondition = (
        '1. RDMA 设备（mlx5_0）在线且 pyverbs mlx5 可用；\n'
        '2. 已部署 ipvbs 运行时（ipvbs_s.py / ipvbs.py）；\n'
        '3. 测试机与 server 节点 SSH 免密连通。'
    )
    test_steps = (
        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\n'
        '2. 创建 Mlx5Context，通过 DevX ALLOC_PD 创建 PD；\n'
        '3. 通过 DevX CREATE_SRQ 创建 SRQ 并校验 SRQ 号有效；\n'
        '4. 连续创建多个 SRQ，校验 SRQ 号唯一；\n'
        '5. 释放 SRQ 并清理资源。'
    )

    @classmethod
    def set_parameters(cls) -> None:
        cls.test_object = 'RDMA SRQ（共享接收队列）'
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
        """
        解析"环境IP信息"文件。

        每行格式：IP 端口号PORT 用户名USER 密码PWD 设备DEV
        返回按出现顺序排列的条目列表，每个条目为 dict：
            {
                'ip': str, 'port': int, 'username': str,
                'password': str, 'device': str
            }
        """
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
        """根据当前执行地址选择对应的环境条目（第1条=SERVER，第2条=CLIENT）。"""
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

        # 1. 从环境信息获取目标 RDMA 设备，失败则自动探测
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

        # 2. 检查 RDMA 设备是否存在
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

        # 3. 检查 pyverbs mlx5 DevX 是否可用
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
        """自动将本地 devx_qp_helper.py 同步到远程节点 /root/sxetest/。"""
        remote_helper = '/root/sxetest/devx_qp_helper.py'
        local_helper = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', 'devx_qp_helper.py'
        )
        local_helper = os.path.normpath(local_helper)
        if not os.path.isfile(local_helper):
            log.warning(f'本地 helper 文件不存在: {local_helper}，'
                        f'跳过自动部署。')
            return

        # 获取目标 IP 与端口
        env_entry = cls._get_env_entry_for_exec_addr()
        ip = env_entry.get('ip') if env_entry else None
        port = str(env_entry.get('port')) if env_entry else '22'
        username = env_entry.get('username') if env_entry else 'root'
        if not ip:
            log.warning('无法获取执行端 IP，跳过 helper 自动部署。')
            return

        # 确保目标目录存在
        remote_dir = os.path.dirname(remote_helper)
        CommandOperation.execute_command_with_error(
            f'mkdir -p {remote_dir}', cls._exec_addr)

        log.info(f'正在同步 helper 到远程: {local_helper} -> '
                 f'{username}@{ip}:{remote_helper}')
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
        log.info(f'prepare: 初始化 SRQ 测试环境 (opcode={cls._OPCODE_NAME}, '
                 f'dev={cls._rdma_dev})。')
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 SRQ 测试环境。')
        cls._srq_objs = []
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)
        # 确保远程节点存在 devx_qp_helper.py
        cls._deploy_helper_if_needed()

        setup_cmds = [
            # 加载 DevX SRQ helper（自动部署到 /root/sxetest/）
            "__import__('sys').path.insert(0, '/root/sxetest')",
            "glb_helper = __import__('devx_qp_helper')",
            # 加载 pyverbs mlx5 DevX 模块
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', "
            "fromlist=['Mlx5Context', 'Mlx5DVContextAttr', 'Mlx5DevxObj', 'Mlx5UMEM'])",
            "glb_Mlx5Context = glb_mlx5dv.Mlx5Context",
            "glb_Mlx5DVContextAttr = glb_mlx5dv.Mlx5DVContextAttr",
            "glb_Mlx5DevxObj = glb_mlx5dv.Mlx5DevxObj",
            "glb_Mlx5UMEM = glb_mlx5dv.Mlx5UMEM",
            # 创建 Mlx5Context
            f"glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), "
            f"'{cls._rdma_dev}')",
            # 通过 DevX ALLOC_PD 创建 PD（SRQ 需要有效的 PD）
            "glb_pd_ret = glb_helper.create_devx_pd(glb_mlx5_ctx)",
            "glb_pd_obj = glb_pd_ret[0]",
            "glb_pdn = glb_pd_ret[1]",
            # 分配 SRQ buffer 并获取物理地址（PAS 模式）
            # CREATE_SRQ 不支持 umem_id，必须用 PAS 提供物理地址
            "glb_srq_buf_ret = glb_helper.alloc_srq_buffer(16384)",
            "glb_srq_buf_addr = glb_srq_buf_ret[0]",
            "glb_srq_buf_size = glb_srq_buf_ret[1]",
            "glb_srq_phys_addrs = glb_srq_buf_ret[2]",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'初始化 DevX SRQ 环境失败, dev={cls._rdma_dev}, '
                    f'cmd={cmd}, rtn={result}')
                return
        log.info('Mlx5Context 和 PD 创建成功。')

    @classmethod
    def do(cls) -> None:
        log.info('do: DevX SRQ 正常创建测试。')
        cls._do_normal_create_srq()
        cls._do_batch_create_srq()

    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 SRQ 资源 (共 {len(cls._srq_objs)} 个)。')
        for srq_name in list(cls._srq_objs):
            cls._close_srq(srq_name)
        cls._srq_objs = []
        if cls._ipvbs is not None:
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    # ------------------------------------------------------------------ #
    #  SRQ 操作辅助方法                                                     #
    # ------------------------------------------------------------------ #

    @classmethod
    def _alloc_srq(cls, srq_name: str) -> tuple:
        """通过 DevX CREATE_SRQ 分配一个 SRQ，返回 (status, srqn)。"""
        glb_srq_name = f'glb_{srq_name}'
        alloc_cmds = [
            # 通过 helper 创建 SRQ（PAS 模式，使用物理地址）
            f"{glb_srq_name}_ret = glb_helper.create_devx_srq("
            f"glb_mlx5_ctx, glb_pdn, glb_srq_phys_addrs)",
            f"{glb_srq_name} = {glb_srq_name}_ret[0]",
            f"{glb_srq_name}_num = {glb_srq_name}_ret[1]",
        ]
        for cmd in alloc_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                log.error(f'DevX CREATE_SRQ 命令失败: {cmd}, rtn={result}')
                return status, None

        status, srqn = cls._ipvbs.exec_and_get_ipvbs_result(
            f"str({glb_srq_name}_num)")
        if status != IpvbsStatusEnum.SUCCESS.value:
            return status, None

        cls._srq_objs.append(srq_name)
        srqn = (srqn or '').strip()
        log.info(f'DevX SRQ 分配成功: {srq_name}, srqn={srqn}')
        return IpvbsStatusEnum.SUCCESS.value, srqn

    @classmethod
    def _close_srq(cls, srq_name: str) -> bool:
        """释放指定 SRQ 及其关联的 WQ UMEM 资源。"""
        glb_srq_name = f'glb_{srq_name}'
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"{glb_srq_name}.close()")
        if status == IpvbsStatusEnum.SUCCESS.value:
            log.info(f'SRQ 释放成功: {srq_name}')
            if srq_name in cls._srq_objs:
                cls._srq_objs.remove(srq_name)
            return True
        log.warning(f'SRQ 释放异常: {srq_name}, rtn={result}')
        return False

    # ------------------------------------------------------------------ #
    #  检查点                                                             #
    # ------------------------------------------------------------------ #

    @classmethod
    def do(cls) -> None:
        log.info('do: DevX SRQ 随机顺序创建释放测试。')
        cls._do_random_order_check()

    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 SRQ 随机顺序测试资源 '
                 f'(共 {len(cls._srq_objs)} 个)。')
        for srq_name in list(cls._srq_objs):
            cls._close_srq(srq_name)
        cls._srq_objs = []
        if cls._ipvbs is not None:
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    @classmethod
    def _do_random_order_check(cls) -> None:
        """CP1: 随机顺序创建/释放 SRQ，验证鲁棒性。"""
        op_count = cls._OPERATION_COUNT
        max_concurrent = cls._MAX_CONCURRENT_SRQ
        random.seed(cls._RANDOM_SEED)

        log.info(f'[CP1] 开始 {op_count} 次随机创建/释放操作 '
                 f'(seed={cls._RANDOM_SEED}, max_concurrent={max_concurrent})。')

        alive_srqns = {}  # srq_name -> srqn
        next_index = 0
        total_created = 0
        total_released = 0

        for step in range(op_count):
            can_create = len(alive_srqns) < max_concurrent
            can_release = bool(alive_srqns)

            if can_create and can_release:
                do_create = random.choice([True, False])
            elif can_create:
                do_create = True
            elif can_release:
                do_create = False
            else:
                break

            if do_create:
                srq_name = f'obj_srq_rand_{next_index}'
                next_index += 1
                status, srqn = cls._alloc_srq(srq_name)
                if status != IpvbsStatusEnum.SUCCESS.value or not srqn:
                    cls.set_bug_type('功能问题')
                    cls.create_bug(f'第 {step + 1} 步随机创建 SRQ 失败。')
                    return
                alive_srqns[srq_name] = srqn
                total_created += 1
            else:
                srq_name = random.choice(list(alive_srqns.keys()))
                if cls._close_srq(srq_name):
                    del alive_srqns[srq_name]
                    total_released += 1
                else:
                    cls.set_bug_type('功能问题')
                    cls.create_bug(f'第 {step + 1} 步随机释放 SRQ {srq_name} 失败。')
                    return

            # 校验当前存活 SRQ 编号唯一
            nums = list(alive_srqns.values())
            if len(set(nums)) != len(nums):
                cls.set_bug_type('功能问题')
                cls.create_bug(f'第 {step + 1} 步后出现重复 srqn: {nums}。')
                return

        log.info(f'[CP1] 随机操作完成: 创建 {total_created} 次，'
                 f'释放 {total_released} 次，'
                 f'最终存活 {len(alive_srqns)} 个 SRQ。')

        # 最后全部释放
        for srq_name in list(alive_srqns.keys()):
            if cls._close_srq(srq_name):
                del alive_srqns[srq_name]
            else:
                cls.set_bug_type('功能问题')
                cls.create_bug(f'最终清理 SRQ {srq_name} 失败。')
                return

        log.info('[CP1] 符合预期: 随机创建/释放序列执行完毕，'
                 '无崩溃、无重复 srqn、全部 SRQ 已释放。')


if __name__ == '__main__':
    NicLinuxRdmaDevxF0653012PfCreateSrqRandomOrder().run()
