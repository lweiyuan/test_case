#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-08-13
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_create_CQ创建_边界创建CQ

               opcode:  SXE3R_DEVX_OP_CREATE_CQ
               对象:    CQ（完成队列）
               用例ID:  nic_linux_rdma_devx_f_06_53_003_004

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


class NicLinuxRdmaDevxF0653003004PfCreateCqBoundary(ScriptBase):
    """DevX CQ 创建用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_003_004'
    case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_create'
                  '_CQ创建_边界创建CQ')
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
    _MAX_ATTEMPT = 2000
    _RELEASE_FOR_RECOVERY = 5
    _ipvbs = None
    _rdma_dev = ''
    _pd_objs = []
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
        "3. 持续循环创建 CQ（每次构造 CQ UMEM/DBR UMEM 并调用 create_devx_cq），记录成功创建数量，直至失败或达到安全上限 2000；\n"
        "4. 若触发资源耗尽，再次创建 CQ，观察失败表现；\n"
        "5. 释放部分 CQ（默认 5 个）后再次创建 CQ；\n"
        "6. 清理全部 CQ 资源。"
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
            log.info('do: DevX CQ 边界创建测试。')
            max_count, hit_exhausted = cls._do_until_exhausted()
            if hit_exhausted:
                cls._do_confirm_exhausted()
            cls._do_partial_release_recovery()

    @classmethod
    def post(cls) -> None:
            log.info(f'post: 清理 PD 资源 (共 {len(cls._cq_objs)} 个)。')
            for cq_name in list(cls._cq_objs):
                cls._close_cq(cq_name)
            cls._cq_objs = []
            if cls._ipvbs is not None:
                IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                           commu=IpvbsCommuEnum.SOCKET.value)

    @classmethod
    def _do_until_exhausted(cls) -> tuple:
            """CP1: 持续创建 PD 直到失败，返回 (成功数量, 是否真正触发耗尽)。"""
            log.info(f'[CP1] 持续创建 PD 直到资源耗尽（上限 {cls._MAX_ATTEMPT}）。')
            count = 0
            for i in range(cls._MAX_ATTEMPT):
                cq_name = f'obj_cq_cp1_{i}'
                status, cqn = cls._create_cq(cq_name)
                if status != IpvbsStatusEnum.SUCCESS.value or not cqn:
                    log.info(f'[CP1] 资源耗尽: 第 {i + 1} 次创建失败，'
                             f'此前成功创建 {count} 个 PD。')
                    return count, True
                count += 1
                if (count % 500) == 0:
                    log.info(f'[CP1] 已创建 {count} 个 PD，继续探测上限...')

            log.info(f'[CP1] 达到安全上限 {cls._MAX_ATTEMPT}，'
                     f'已成功创建 {count} 个 PD，当前环境未触发资源耗尽。')
            return count, False

    @classmethod
    def _do_confirm_exhausted(cls) -> None:
            """CP2: 确认资源耗尽后再次创建仍失败。"""
            log.info('[CP2] 确认资源耗尽后再次创建失败。')
            status, cqn = cls._create_cq('obj_cq_cp2_confirm')
            if status == IpvbsStatusEnum.SUCCESS.value and cqn:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    '资源 supposedly 耗尽后仍能成功创建 PD，'
                    '期望持续返回失败。')
                cls._close_cq('obj_cq_cp2_confirm')
            else:
                log.info('[CP2] 符合预期: 资源耗尽后再次创建失败。')

    @classmethod
    def _do_partial_release_recovery(cls) -> None:
            """CP3: 释放部分 PD 后验证资源可恢复。"""
            release_n = min(cls._RELEASE_FOR_RECOVERY, len(cls._cq_objs))
            log.info(f'[CP3] 释放 {release_n} 个 PD 后验证资源可恢复。')
            released = []
            for _ in range(release_n):
                if not cls._cq_objs:
                    break
                cq_name = cls._cq_objs[0]
                if cls._close_cq(cq_name):
                    released.append(cq_name)

            if len(released) != release_n:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'计划释放 {release_n} 个 PD，实际释放 {len(released)} 个。')
                return

            recover_count = len(released)
            recovered = []
            for i in range(recover_count):
                cq_name = f'obj_cq_cp3_recovered_{i}'
                status, cqn = cls._create_cq(cq_name)
                if status != IpvbsStatusEnum.SUCCESS.value or not cqn:
                    cls.set_bug_type('功能问题')
                    cls.create_bug(
                        f'释放 {release_n} 个 PD 后，第 {i + 1} 次恢复创建失败。')
                    return
                recovered.append(cqn)

            log.info(f'[CP3] 资源恢复验证成功: 释放 {release_n} 个后，'
                     f'成功创建 {len(recovered)} 个 PD，cqn={recovered}')


if __name__ == '__main__':
    NicLinuxRdmaDevxF0653003004PfCreateCqBoundary().run()
