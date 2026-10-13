#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-08-13
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_create_CQ创建_跨设备交替压力创建释放CQ

               opcode:  SXE3R_DEVX_OP_CREATE_CQ
               对象:    CQ（完成队列）
               用例ID:  nic_linux_rdma_devx_f_06_53_003_013

               实现说明：
               在 CX8 / mlx5 设备上通过 pyverbs 的 Mlx5DevxObj 直接下发
               固件 CREATE_CQ 命令（opcode=0x400）创建 CQ，验证 CQ 号有效、
               唯一且可正常释放。

               环境信息来源：项目根目录下的"环境IP信息"文件，
               按 server/client 顺序解析 IP、端口、用户名、密码及 RDMA 设备名。

@changelog:
    2026-08-13 初始版本，基于 DevX PD 测试模式迁移生成。
"""
import os
import random
import re
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


class NicLinuxRdmaDevxF0653003013PfCreateCqCrossDeviceAlternatingStress(ScriptBase):
    """DevX CQ 创建用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_003_013'
    case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_create'
                  '_CQ创建_跨设备交替压力创建释放CQ')
    case_module = 'DevX'
    case_type = '系统测试-功能'

    # Mellanox 固件 opcode（参见 include/linux/mlx5/mlx5_ifc.h）
    _MLX5_OP_CREATE_CQ = 0x400
    _MLX5_OP_DESTROY_CQ = 0x401
    _MLX5_OP_INVALID = 0xFFF
    _CREATE_CQ_IN_LEN = 512
    _CREATE_CQ_OUT_LEN = 16

    _MLX5_OP_ALLOC_PD = 0x800
    _OPCODE_NAME = 'SXE3R_DEVX_OP_CREATE_PD'
    _OPERATION_COUNT = 200
    _MAX_CONCURRENT_PD_PER_DEVICE = 20
    _RANDOM_SEED = 20260813
    _ipvbs = None
    _rdma_devs = []
    _env_ip_info = None

    _OPCODE_NAME = 'SXE3R_DEVX_OP_CREATE_CQ'
    _OBJ_TYPE = 'CQ'
    _CQ_COUNT = 5

    _ipvbs = None
    _rdma_dev = ''
    _cq_objs = []

    # 环境IP信息文件相关
    _ENV_IP_INFO_FILE_NAME = '环境IP信息'
    _env_ip_info = None

    test_object = 'RDMA CQ（完成队列）'
    test_module = 'rdma'
    test_tool = 'pyverbs'
    test_precondition = (
        '1. RDMA 设备（mlx5_0）在线且 pyverbs mlx5 可用；\n'
        '2. 已部署 ipvbs 运行时（ipvbs_s.py / ipvbs.py）；\n'
        '3. 测试机与 server 节点 SSH 免密连通。'
    )
    test_steps = (
        "1. 初始化 RDMA 测试框架与 ipvbs 会话；\n"
        "2. 自动探测所有可用 RDMA 设备；\n"
        "3. 为每个设备创建独立 Mlx5Context、UAR，查询 EQN；\n"
        "4. 在固定随机种子（20260813）下跨设备交替执行 200 次创建/释放操作；创建时调用 create_devx_cq，释放时调用 cq_obj.close()；\n"
        "5. 每轮操作后校验每个设备内部 cqn 唯一；\n"
        "6. 最终释放全部 CQ。"
    )

    @classmethod
    def set_parameters(cls) -> None:
        cls.test_object = 'RDMA CQ（完成队列）'
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
        # 跨设备用例：记录全部可用设备，作为多设备上下文创建的设备列表
        cls._rdma_devs = list(dev_list)
        log.info(f'检测到 RDMA 设备: {dev_list}, 本用例使用: {cls._rdma_dev}, '
                 f'跨设备列表: {cls._rdma_devs}')

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
    def prepare(cls) -> None:
        log.info(f'prepare: 初始化 CQ 测试环境 (opcode={cls._OPCODE_NAME}, '
                 f'devs={cls._rdma_devs})。')
        if not cls._rdma_devs:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 CQ 测试环境。')
            return
        cls._cq_objs = []
        # 采用 SOCKET 通信模式（设备端未安装 screen）
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)

        # 公共模块加载（仅一次）
        setup_cmds = [
            # 加载 DevX CQ helper（需提前置于 /root/sxetest/vm999/）
            "glb_helper = __import__('devx_qp_helper')",
            # 加载 struct 模块，用于异常/边界场景打包固件命令 buffer
            "glb_struct = __import__('struct')",
            # 加载 pyverbs mlx5 DevX 模块
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', "
            "fromlist=['Mlx5Context', 'Mlx5DVContextAttr', 'Mlx5UMEM', 'Mlx5UAR', 'Mlx5DevxObj'])",
            "glb_Mlx5Context = glb_mlx5dv.Mlx5Context",
            "glb_Mlx5DVContextAttr = glb_mlx5dv.Mlx5DVContextAttr",
            "glb_Mlx5UMEM = glb_mlx5dv.Mlx5UMEM",
            "glb_Mlx5UAR = glb_mlx5dv.Mlx5UAR",
            "glb_Mlx5DevxObj = glb_mlx5dv.Mlx5DevxObj",
            # 加载 resource 模块，用于获取页大小
            "glb_resource = __import__('resource')",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'加载 DevX 模块失败, cmd={cmd}, rtn={result}')

        # 为每个设备建立独立 Mlx5Context / UAR / EQN
        for dev in cls._rdma_devs:
            dev_suffix = dev.replace('-', '_')
            dev_cmds = [
                f"glb_mlx5_ctx_{dev_suffix} = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '{dev}')",
                f"glb_uar_{dev_suffix} = glb_Mlx5UAR(glb_mlx5_ctx_{dev_suffix})",
                f"glb_eqn_{dev_suffix} = glb_mlx5_ctx_{dev_suffix}.devx_query_eqn(0)",
            ]
            for cmd in dev_cmds:
                status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
                if status != IpvbsStatusEnum.SUCCESS.value:
                    cls.set_bug_type('功能问题')
                    cls.create_bug(
                        f'创建设备 {dev} 的 Mlx5Context 失败, cmd={cmd}, '
                        f'rtn={result}')
                    return
            log.info(f'设备 {dev} 的 Mlx5Context/UAR/EQN 创建成功。')

    # ------------------------------------------------------------------ #
    #  检查点                                                             #
    # ------------------------------------------------------------------ #
    @classmethod
    def _create_cq(cls, dev: str, cq_name: str) -> tuple:
            """在指定设备上通过 DevX CREATE_CQ 分配一个 CQ，返回 (status, cqn)。"""
            dev_suffix = dev.replace('-', '_')
            glb_cq_name = f'glb_cq_{dev_suffix}_{cq_name}'
            create_cmds = [
                # 每个 CQ 需要独立的 CQ UMEM 和 DBR UMEM（绑定对应设备的上下文）
                f"{glb_cq_name}_cq_umem = glb_Mlx5UMEM(glb_mlx5_ctx_{dev_suffix}, size=16384)",
                f"{glb_cq_name}_cq_dbr = glb_Mlx5UMEM(glb_mlx5_ctx_{dev_suffix}, size=8, alignment=8)",
                # 通过 helper 创建 CQ
                f"{glb_cq_name}_ret = glb_helper.create_devx_cq(glb_mlx5_ctx_{dev_suffix}, glb_eqn_{dev_suffix}, glb_uar_{dev_suffix}, {glb_cq_name}_cq_umem, {glb_cq_name}_cq_dbr)",
                f"{glb_cq_name} = {glb_cq_name}_ret[0]",
                f"{glb_cq_name}_num = {glb_cq_name}_ret[1]",
            ]
            for cmd in create_cmds:
                status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
                if status != IpvbsStatusEnum.SUCCESS.value:
                    log.error(f'DevX CREATE_CQ 命令失败: {cmd}, rtn={result}')
                    return status, None

            status, cqn = cls._ipvbs.exec_and_get_ipvbs_result(
                f"str({glb_cq_name}_num)")
            if status != IpvbsStatusEnum.SUCCESS.value:
                return status, None

            cls._cq_objs.append((dev, cq_name))
            cqn = (cqn or '').strip()
            log.info(f'DevX CQ 创建成功: dev={dev}, cq={cq_name}, cqn={cqn}')
            return IpvbsStatusEnum.SUCCESS.value, cqn

    @classmethod
    def _close_cq(cls, dev: str, cq_name: str) -> bool:
            """释放指定设备上指定 CQ 及其关联的 CQ UMEM / DBR UMEM 资源。"""
            dev_suffix = dev.replace('-', '_')
            glb_cq_name = f'glb_cq_{dev_suffix}_{cq_name}'
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(
                f"{glb_cq_name}.close()")
            # 必须同步释放 CQ 占用的 UMEM 与 DBR UMEM，否则 UMEM 数量
            # 累积到上限后会导致后续 CREATE_CQ 返回 Remote I/O error。
            for res_name in (f"{glb_cq_name}_cq_umem",
                             f"{glb_cq_name}_cq_dbr"):
                cls._ipvbs.exec_and_get_ipvbs_result(f"{res_name}.close()")
            if status == IpvbsStatusEnum.SUCCESS.value:
                log.info(f'CQ 释放成功: dev={dev}, cq={cq_name}')
                if (dev, cq_name) in cls._cq_objs:
                    cls._cq_objs.remove((dev, cq_name))
                return True
            log.warning(f'CQ 释放异常: dev={dev}, cq={cq_name}, rtn={result}')
            return False

    @classmethod
    def do(cls) -> None:
            log.info('do: DevX CQ 跨设备交替压力创建释放测试。')
            cls._do_alternating_stress()

    @classmethod
    def post(cls) -> None:
            log.info('post: 清理跨设备交替压力 PD 资源。')
            cls._release_all_pd()

            for dev in cls._rdma_devs:
                ctx_var = cls._ctx_var(dev)
                status, result = cls._ipvbs.exec_and_get_ipvbs_result(
                    f'{ctx_var}.close()')
                if status != IpvbsStatusEnum.SUCCESS.value:
                    log.warning(f'设备 {dev} 的 Mlx5Context 关闭异常: {result}')
                else:
                    log.info(f'设备 {dev} 的 Mlx5Context 已关闭。')

            if cls._ipvbs is not None:
                IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                           commu=IpvbsCommuEnum.SOCKET.value)

    @classmethod
    def _ctx_var(cls, dev: str) -> str:
            """返回某设备 Mlx5Context 在 ipvbs 中的变量名。"""
            return f"glb_mlx5_ctx_{dev.replace('-', '_')}"

    @classmethod
    def _pd_var(cls, dev: str, cq_name: str) -> str:
            """返回某设备上某 CQ 对象在 ipvbs 中的变量名。"""
            return f"glb_cq_{dev.replace('-', '_')}_{cq_name}"

    @classmethod
    def _get_cqn(cls, dev: str, cq_name: str) -> str or None:
            """获取指定设备上指定 PD 的 cqn。"""
            pd_var = cls._pd_var(dev, cq_name)
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(
                f'str({pd_var}_num)')
            if status == IpvbsStatusEnum.SUCCESS.value:
                return (result or '').strip()
            return None

    @classmethod
    def _do_alternating_stress(cls) -> None:
            """CP1: 跨设备交替随机创建/释放 PD，验证设备隔离与鲁棒性。"""
            op_count = cls._OPERATION_COUNT
            max_per_dev = cls._MAX_CONCURRENT_PD_PER_DEVICE
            random.seed(cls._RANDOM_SEED)

            log.info(f'[CP1] 开始跨设备交替压力测试 '
                     f'(seed={cls._RANDOM_SEED}, op_count={op_count}, '
                     f'max_per_device={max_per_dev})。')

            # 每个设备上存活的 PD: dev -> {cq_name: cqn}
            alive_per_dev = {dev: {} for dev in cls._rdma_devs}
            next_index = 0
            total_created = 0
            total_released = 0

            for step in range(op_count):
                # 选择动作：创建或释放
                can_create_devs = [
                    dev for dev in cls._rdma_devs
                    if len(alive_per_dev[dev]) < max_per_dev
                ]
                can_release_devs = [
                    dev for dev in cls._rdma_devs
                    if alive_per_dev[dev]
                ]

                if can_create_devs and can_release_devs:
                    do_create = random.choice([True, False])
                elif can_create_devs:
                    do_create = True
                elif can_release_devs:
                    do_create = False
                else:
                    break

                if do_create:
                    dev = random.choice(can_create_devs)
                    cq_name = f'cp1_{next_index}'
                    next_index += 1
                    status, cqn = cls._create_cq(dev, cq_name)
                    if status != IpvbsStatusEnum.SUCCESS.value or not cqn:
                        cls.set_bug_type('功能问题')
                        cls.create_bug(f'第 {step + 1} 步在设备 {dev} 创建 PD 失败。')
                        return
                    alive_per_dev[dev][cq_name] = cqn
                    total_created += 1
                else:
                    dev = random.choice(can_release_devs)
                    cq_name = random.choice(list(alive_per_dev[dev].keys()))
                    if cls._close_cq(dev, cq_name):
                        del alive_per_dev[dev][cq_name]
                        total_released += 1
                    else:
                        cls.set_bug_type('功能问题')
                        cls.create_bug(
                            f'第 {step + 1} 步在设备 {dev} 释放 PD {cq_name} 失败。')
                        return

                # 校验每个设备内部 cqn 唯一
                for dev, alive in alive_per_dev.items():
                    nums = list(alive.values())
                    if len(set(nums)) != len(nums):
                        cls.set_bug_type('功能问题')
                        cls.create_bug(
                            f'第 {step + 1} 步后设备 {dev} 出现重复 cqn: {nums}。')
                        return

            log.info(f'[CP1] 跨设备交替压力完成: 创建 {total_created} 次，'
                     f'释放 {total_released} 次。')
            for dev, alive in alive_per_dev.items():
                log.info(f'[CP1] 设备 {dev} 最终存活 PD 数: {len(alive)}')

            # 释放剩余全部 PD
            for dev in cls._rdma_devs:
                for cq_name in list(alive_per_dev[dev].keys()):
                    if cls._close_cq(dev, cq_name):
                        del alive_per_dev[dev][cq_name]
                    else:
                        cls.set_bug_type('功能问题')
                        cls.create_bug(f'最终清理设备 {dev} 的 PD {cq_name} 失败。')
                        return

            log.info('[CP1] 符合预期: 跨设备交替压力序列执行完毕，'
                     '无崩溃、无重复 cqn、全部 PD 已释放。')

    @classmethod
    def _release_all_pd(cls) -> None:
            """兜底释放所有设备上可能残留的 CQ 及其 UMEM/DBR UMEM。"""
            log.info('兜底清理所有设备上残留的 CQ 对象。')
            for dev, cq_name in list(cls._cq_objs):
                cls._close_cq(dev, cq_name)
            if not cls._cq_objs:
                log.info('无残留 CQ，跨设备交替压力资源已全部释放。')


if __name__ == '__main__':
    NicLinuxRdmaDevxF0653003013PfCreateCqCrossDeviceAlternatingStress().run()
