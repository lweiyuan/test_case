#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-08-11
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_create_PD创建_压力创建PD

               opcode:  SXE3R_DEVX_OP_CREATE_PD
               对象:    PD（保护域）
               用例ID:  nic_linux_rdma_devx_f_06_53_001_003

               实现说明：
               在 CX8 / mlx5 设备上通过 pyverbs 的 Mlx5DevxObj 反复下发
               固件 ALLOC_PD 命令，验证高频率创建/释放、大批量同时存在、
               以及重复创建后资源可正常回收。

               环境信息来源：项目根目录下的"环境IP信息"文件。

@changelog:
    2026-08-11 初始版本，覆盖高频循环、大批量同时存在及资源回收压力场景。
"""
import os
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


class NicLinuxRdmaDevxF0653001003PfCreatePdStress(ScriptBase):
    """DevX PD 压力创建用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_001_003'
    case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_create'
                  '_PD创建_压力创建PD')
    case_module = 'DevX'
    case_type = '系统测试-性能/压力'

    # Mellanox 固件 opcode
    _MLX5_OP_ALLOC_PD = 0x800

    _OPCODE_NAME = 'SXE3R_DEVX_OP_CREATE_PD'
    _OBJ_TYPE = 'PD'

    # 压力参数
    _LOOP_COUNT = 1000
    _BATCH_SIZE = 100

    _ipvbs = None
    _rdma_dev = ''
    _pd_objs = []

    # 环境IP信息文件相关
    _ENV_IP_INFO_FILE_NAME = '环境IP信息'
    _env_ip_info = None

    test_object = 'RDMA PD（保护域）'
    test_module = 'rdma'
    test_tool = 'pyverbs'
    test_precondition = (
        '1. RDMA 设备（mlx5_0）在线且 pyverbs mlx5 可用；\n'
        '2. 已部署 ipvbs 运行时（ipvbs_s.py / ipvbs.py）；\n'
        '3. 测试机与 server 节点 SSH 免密连通。'
    )
    test_steps = (
        '1. 初始化 ipvbs 会话并创建 Mlx5Context；\n'
        '2. 高频循环创建并立即释放 PD，统计成功率；\n'
        '3. 批量创建多个 PD 同时存在，校验 pd_num 唯一；\n'
        '4. 释放全部 PD 后再次创建，验证资源可恢复；\n'
        '5. 清理资源。'
    )

    @classmethod
    def set_parameters(cls) -> None:
        cls.test_object = 'RDMA PD（保护域）'
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
        返回按出现顺序排列的条目列表。
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
        log.info(f'prepare: 初始化 PD 压力测试环境 (opcode={cls._OPCODE_NAME}, '
                 f'dev={cls._rdma_dev})。')
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 PD 压力测试环境。')
        cls._pd_objs = []
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)
        # 确保远程节点存在 devx_qp_helper.py
        cls._deploy_helper_if_needed()

        setup_cmds = [
            # 加载 struct 模块，用于打包/解包固件命令 buffer
            "glb_struct = __import__('struct')",
            # 加载 pyverbs mlx5 DevX 模块，获取 Mlx5Context / Mlx5DVContextAttr / Mlx5DevxObj
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', "
            "fromlist=['Mlx5Context', 'Mlx5DVContextAttr', 'Mlx5DevxObj'])",
            # 绑定 Mlx5Context 类，用于创建 DevX 上下文
            "glb_Mlx5Context = glb_mlx5dv.Mlx5Context",
            # 绑定 Mlx5DVContextAttr 类，作为创建 Mlx5Context 的属性参数
            "glb_Mlx5DVContextAttr = glb_mlx5dv.Mlx5DVContextAttr",
            # 绑定 Mlx5DevxObj 类，用于下发 DevX 固件命令
            "glb_Mlx5DevxObj = glb_mlx5dv.Mlx5DevxObj",
            # 实例化默认的 DevX 上下文属性
            "glb_devx_attr = glb_Mlx5DVContextAttr()",
            # 创建 Mlx5Context，绑定到目标 RDMA 设备（变量带 glb_ 前缀才能跨 ipvbs 命令持久化）
            f"glb_mlx5_ctx = glb_Mlx5Context(glb_devx_attr, '{cls._rdma_dev}')",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'创建 Mlx5Context 失败, dev={cls._rdma_dev}, '
                    f'cmd={cmd}, rtn={result}')
        log.info('Mlx5Context 创建成功。')

    @classmethod
    def do(cls) -> None:
        log.info('do: DevX PD 压力创建测试。')
        cls._do_loop_create_release()
        cls._do_batch_exist()
        cls._do_recovery_after_release()

    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 PD 资源 (共 {len(cls._pd_objs)} 个)。')
        for pd_name in list(cls._pd_objs):
            cls._close_pd(pd_name)
        cls._pd_objs = []
        if cls._ipvbs is not None:
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    # ------------------------------------------------------------------ #
    #  PD 操作辅助方法                                                     #
    # ------------------------------------------------------------------ #

    @classmethod
    def _alloc_pd(cls, pd_name: str) -> tuple:
        """通过 DevX ALLOC_PD 分配一个 PD，返回 (status, pd_num)。"""
        glb_pd_name = f'glb_{pd_name}'
        alloc_cmds = [
            f"{glb_pd_name}_in = glb_struct.pack('>HHHHQ', "
            f"{cls._MLX5_OP_ALLOC_PD}, 0, 0, 0, 0)",
            f"{glb_pd_name} = glb_Mlx5DevxObj(glb_mlx5_ctx, "
            f"{glb_pd_name}_in, 16)",
            f"{glb_pd_name}_num = glb_struct.unpack('>I', "
            f"{glb_pd_name}.out_view[8:12])[0] & 0xFFFFFF",
        ]
        for cmd in alloc_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                log.error(f'DevX ALLOC_PD 命令失败: {cmd}, rtn={result}')
                return status, None

        status, pd_num = cls._ipvbs.exec_and_get_ipvbs_result(
            f"str({glb_pd_name}_num)")
        if status != IpvbsStatusEnum.SUCCESS.value:
            return status, None

        cls._pd_objs.append(pd_name)
        pd_num = (pd_num or '').strip()
        return IpvbsStatusEnum.SUCCESS.value, pd_num

    @classmethod
    def _close_pd(cls, pd_name: str) -> bool:
        """释放指定 PD。"""
        glb_pd_name = f'glb_{pd_name}'
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"{glb_pd_name}.close()")
        if status == IpvbsStatusEnum.SUCCESS.value:
            if pd_name in cls._pd_objs:
                cls._pd_objs.remove(pd_name)
            return True
        log.warning(f'PD 释放异常: {pd_name}, rtn={result}')
        return False

    # ------------------------------------------------------------------ #
    #  压力检查点                                                         #
    # ------------------------------------------------------------------ #

    @classmethod
    def _do_loop_create_release(cls) -> None:
        """CP1: 高频循环创建并立即释放 PD，统计成功率。"""
        n = cls._LOOP_COUNT
        log.info(f'[CP1] 高频循环创建/释放 PD {n} 次。')
        success = 0
        fail = 0
        start = time.time()
        for i in range(n):
            pd_name = f'obj_pd_cp1_{i}'
            status, pd_num = cls._alloc_pd(pd_name)
            if status != IpvbsStatusEnum.SUCCESS.value or not pd_num:
                fail += 1
                cls.set_bug_type('功能问题')
                cls.create_bug(f'循环创建 PD 第 {i + 1}/{n} 次失败。')
                continue
            success += 1
            if not cls._close_pd(pd_name):
                fail += 1
                cls.set_bug_type('功能问题')
                cls.create_bug(f'循环释放 PD 第 {i + 1}/{n} 次失败。')
        duration = time.time() - start
        log.info(
            f'[CP1] 循环压力完成: 总次数={n}, 成功={success}, 失败={fail}, '
            f'耗时={duration:.3f}s, 平均={duration / n * 1000:.3f}ms/次'
        )
        if fail > 0:
            cls.set_bug_type('功能问题')
            cls.create_bug(
                f'循环压力出现 {fail} 次失败，期望 {n} 次全部成功。')

    @classmethod
    def _do_batch_exist(cls) -> None:
        """CP2: 批量创建多个 PD 同时存在，校验 pd_num 唯一。"""
        n = cls._BATCH_SIZE
        log.info(f'[CP2] 批量创建 {n} 个 PD 同时存在。')
        pd_nums = []
        for i in range(n):
            pd_name = f'obj_pd_cp2_{i}'
            status, pd_num = cls._alloc_pd(pd_name)
            if status != IpvbsStatusEnum.SUCCESS.value or not pd_num:
                cls.set_bug_type('功能问题')
                cls.create_bug(f'批量创建第 {i + 1}/{n} 个 PD 失败。')
                return
            pd_nums.append(pd_num)

        unique = len(set(pd_nums))
        log.info(f'[CP2] 批量创建完成: 期望 {n} 个, 实际唯一 {unique} 个。')
        if unique != n:
            cls.set_bug_type('功能问题')
            cls.create_bug(
                f'批量创建 {n} 个 PD 存在重复 pd_num，唯一数={unique}。')

    @classmethod
    def _do_recovery_after_release(cls) -> None:
        """CP3: 释放全部 PD 后再次创建，验证资源可恢复。"""
        log.info('[CP3] 释放全部 PD 后验证资源可恢复。')
        for pd_name in list(cls._pd_objs):
            cls._close_pd(pd_name)
        cls._pd_objs = []

        status, pd_num = cls._alloc_pd('obj_pd_cp3')
        if status != IpvbsStatusEnum.SUCCESS.value or not pd_num:
            cls.set_bug_type('功能问题')
            cls.create_bug('资源回收后再次创建 PD 失败，期望可恢复。')
            return
        log.info(f'[CP3] 资源恢复验证成功: pd_num={pd_num}')
        cls._close_pd('obj_pd_cp3')


if __name__ == '__main__':
    NicLinuxRdmaDevxF0653001003PfCreatePdStress().run()
