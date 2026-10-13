#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-08-13
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_create_CQ创建_长时间稳定性创建CQ

               opcode:  SXE3R_DEVX_OP_CREATE_CQ
               对象:    CQ（完成队列）
               用例ID:  nic_linux_rdma_devx_f_06_53_003_007

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


class NicLinuxRdmaDevxF0653003007PfCreateCqLongTermStability(ScriptBase):
    """DevX CQ 创建用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_003_007'
    case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_create'
                  '_CQ创建_长时间稳定性创建CQ')
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
    _RUN_DURATION_SECONDS = 600
    _MAX_ITERATIONS = 0
    _ipvbs = None
    _rdma_dev = ''
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
        "2. 创建 Mlx5Context、UAR，查询 EQN；\n"
        "3. 在 600 秒内循环：构造 CQ UMEM/DBR UMEM，调用 create_devx_cq 创建 CQ，解析 cqn，然后释放 CQ；\n"
        "4. 统计总迭代次数、成功次数、失败次数；\n"
        "5. 统计平均耗时与最大耗时；\n"
        "6. 确认无失败、无显著变慢后清理资源。"
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
    def prepare(cls) -> None:
        log.info(f'prepare: 初始化 CQ 测试环境 (opcode={cls._OPCODE_NAME}, '
                 f'dev={cls._rdma_dev})。')
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 CQ 测试环境。')
        cls._cq_objs = []
        # 采用 SOCKET 通信模式（设备端未安装 screen）
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)

        # 建立 Mlx5Context、UAR，查询 EQN
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
            # 创建 Mlx5Context
            f"glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '{cls._rdma_dev}')",
            # 创建 UAR（CQ 需要 uar_page）
            "glb_uar = glb_Mlx5UAR(glb_mlx5_ctx)",
            # 查询 EQN（CQ 需要 c_eqn）
            "glb_eqn = glb_mlx5_ctx.devx_query_eqn(0)",
            # 加载 resource 模块，用于获取页大小
            "glb_resource = __import__('resource')",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'创建 Mlx5Context 失败, dev={cls._rdma_dev}, '
                    f'cmd={cmd}, rtn={result}')
        log.info('Mlx5Context 创建成功。')

    # ------------------------------------------------------------------ #
    #  检查点                                                             #
    # ------------------------------------------------------------------ #
    @classmethod
    def _create_cq(cls, cq_name: str) -> tuple:
            """通过 DevX CREATE_CQ 分配一个 CQ，返回 (status, cqn)。"""
            glb_cq_name = f'glb_{cq_name}'
            create_cmds = [
                # 每个 CQ 需要独立的 CQ UMEM 和 DBR UMEM
                f"{glb_cq_name}_cq_umem = glb_Mlx5UMEM(glb_mlx5_ctx, size=16384)",
                f"{glb_cq_name}_cq_dbr = glb_Mlx5UMEM(glb_mlx5_ctx, size=8, alignment=8)",
                # 通过 helper 创建 CQ
                f"{glb_cq_name}_ret = glb_helper.create_devx_cq(glb_mlx5_ctx, glb_eqn, glb_uar, {glb_cq_name}_cq_umem, {glb_cq_name}_cq_dbr)",
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

            cls._cq_objs.append(cq_name)
            cqn = (cqn or '').strip()
            log.info(f'DevX CQ 创建成功: {cq_name}, cqn={cqn}')
            return IpvbsStatusEnum.SUCCESS.value, cqn

    @classmethod
    def _close_cq(cls, cq_name: str) -> bool:
            """释放指定 CQ 及其关联的 CQ UMEM / DBR UMEM 资源。"""
            glb_cq_name = f'glb_{cq_name}'
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(
                f"{glb_cq_name}.close()")
            # 必须同步释放 CQ 占用的 UMEM 与 DBR UMEM，否则 UMEM 数量
            # 累积到上限后会导致后续 CREATE_CQ 返回 Remote I/O error。
            for res_name in (f"{glb_cq_name}_cq_umem",
                             f"{glb_cq_name}_cq_dbr"):
                cls._ipvbs.exec_and_get_ipvbs_result(f"{res_name}.close()")
            if status == IpvbsStatusEnum.SUCCESS.value:
                log.info(f'CQ 释放成功: {cq_name}')
                if cq_name in cls._cq_objs:
                    cls._cq_objs.remove(cq_name)
                return True
            log.warning(f'CQ 释放异常: {cq_name}, rtn={result}')
            return False

    @classmethod
    def do(cls) -> None:
            log.info('do: DevX CQ 长时间稳定性测试。')
            cls._do_long_term_stability()

    @classmethod
    def post(cls) -> None:
            log.info('post: 清理长时间稳定性 PD 测试资源。')
            if cls._ipvbs is not None:
                IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                           commu=IpvbsCommuEnum.SOCKET.value)

    @classmethod
    def _do_long_term_stability(cls) -> None:
            """CP1: 长时间循环创建/释放 PD，统计成功率和耗时。"""
            duration = cls._RUN_DURATION_SECONDS
            max_iter = cls._MAX_ITERATIONS
            log.info(f'[CP1] 开始长时间稳定性测试，计划运行 {duration} 秒。')

            start_time = time.time()
            iteration = 0
            success_count = 0
            failure_count = 0
            latencies = []

            while True:
                elapsed = time.time() - start_time
                if elapsed >= duration:
                    break
                if max_iter > 0 and iteration >= max_iter:
                    log.info(f'达到最大迭代次数 {max_iter}，提前结束。')
                    break

                iteration += 1
                cq_name = f'pd_stability_{iteration}'
                iter_start = time.time()

                status, cqn = cls._create_cq(cq_name)
                if status != IpvbsStatusEnum.SUCCESS.value or not cqn:
                    failure_count += 1
                    cls.set_bug_type('功能问题')
                    cls.create_bug(
                        f'长时间稳定性测试第 {iteration} 次 PD 创建失败，'
                        f'运行时间 {elapsed:.1f}s。')
                    # 遇到失败也尝试继续，不立即退出
                    continue

                if not cqn.isdigit():
                    failure_count += 1
                    cls.set_bug_type('功能问题')
                    cls.create_bug(
                        f'长时间稳定性测试第 {iteration} 次返回非法 cqn: '
                        f'{cqn}。')
                    cls._close_cq(cq_name)
                    continue

                if not cls._close_cq(cq_name):
                    failure_count += 1
                    cls.set_bug_type('功能问题')
                    cls.create_bug(
                        f'长时间稳定性测试第 {iteration} 次 PD 释放失败。')
                    continue

                success_count += 1
                latency = time.time() - iter_start
                latencies.append(latency)

                # 每 30 秒输出一次中间统计
                if iteration % 30 == 0 or (iteration <= 10):
                    avg_latency = sum(latencies) / len(latencies) if latencies else 0
                    max_latency = max(latencies) if latencies else 0
                    log.info(
                        f'[CP1] 进度: 迭代 {iteration}, 成功 {success_count}, '
                        f'失败 {failure_count}, 已运行 {elapsed:.1f}s, '
                        f'平均耗时 {avg_latency*1000:.2f}ms, '
                        f'最大耗时 {max_latency*1000:.2f}ms')

            total_elapsed = time.time() - start_time
            total_iterations = success_count + failure_count

            if total_iterations == 0:
                cls.set_bug_type('功能问题')
                cls.create_bug('长时间稳定性测试未完成任何有效迭代。')
                return

            success_rate = success_count / total_iterations
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            max_latency = max(latencies) if latencies else 0

            log.info(
                f'[CP1] 长时间稳定性测试结束: 总迭代 {total_iterations}, '
                f'成功 {success_count}, 失败 {failure_count}, '
                f'成功率 {success_rate*100:.2f}%, 运行 {total_elapsed:.1f}s, '
                f'平均耗时 {avg_latency*1000:.2f}ms, 最大耗时 {max_latency*1000:.2f}ms'
            )

            if failure_count > 0:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'长时间稳定性测试出现 {failure_count} 次失败，'
                    f'成功率 {success_rate*100:.2f}%，期望 100%。')

            if success_rate < 1.0:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'长时间稳定性测试成功率不足 100%: {success_rate*100:.2f}%。')


if __name__ == '__main__':
    NicLinuxRdmaDevxF0653003007PfCreateCqLongTermStability().run()
