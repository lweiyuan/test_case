#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-08-27
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_destroy_MKEY销毁_上下文重建销毁MKEY

               opcode:  MLX5_CMD_OP_CREATE_GENERAL_OBJECT (0xa00) +
                        MLX5_OBJ_TYPE_MKEY (0xff01)
               对象:    MKEY（内存键 / MR）
               用例ID:  nic_linux_rdma_devx_f_06_53_009_001

               实现说明：
               在 mlx5 设备上通过 pyverbs 的 Mlx5DevxObj 下发固件
               CREATE_GENERAL_OBJECT + MLX5_OBJ_TYPE_MKEY 命令创建内存键，
               验证 mkey 有效、唯一且可正常释放。
               注意：部分平台固件不支持通过 GENERAL_OBJECT + 0xff01 销毁 MKEY，
               helper 会按项目统一策略在 prepare() 中探测支持情况；不支持时
               将用例标记为 SKIP 而不是 FAIL。

               环境信息来源：项目根目录下的"环境IP信息"文件，
               按 server/client 顺序解析 IP、端口、用户名、密码及 RDMA 设备名。

@changelog:
    2026-08-27 初始版本，基于 DevX CREATE_GENERAL_OBJECT + MLX5_OBJ_TYPE_MKEY 生成。
"""
import os
import re


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


class NicLinuxRdmaDevxF0653009020PfDestroyMkeyGeneralObjectContextRebuildDestroyMkey(ScriptBase):
    """DevX GENERAL_OBJECT MKEY 正常创建用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_009_020'
    case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_destroy'
                  '_MKEY销毁_上下文重建销毁MKEY')
    case_module = 'DevX'
    case_type = '系统测试-功能'

    # Mellanox 固件 opcode / obj_type（参见 include/linux/mlx5/mlx5_ifc.h）
    _MLX5_OP_CREATE_GENERAL_OBJECT = 0xa00
    _MLX5_OBJ_TYPE_MKEY = 0xff01

    _OPCODE_NAME = 'MLX5_CMD_OP_CREATE_GENERAL_OBJECT + MLX5_OBJ_TYPE_MKEY'
    _OBJ_TYPE = 'MKEY'
    _MKEY_COUNT = 5
    _MKEY_LENGTH = 4096

    _mkey_supported = False

    _ipvbs = None
    _rdma_dev = ''
    _mkey_objs = []

    # 环境IP信息文件相关
    _ENV_IP_INFO_FILE_NAME = '环境IP信息'
    _env_ip_info = None

    test_object = 'RDMA MKEY（内存键）'
    test_module = 'rdma'
    test_tool = 'pyverbs'
    test_precondition = (
        '1. RDMA 设备（mlx5_0）在线且 pyverbs mlx5 可用；\n'
        '2. 已部署 ipvbs 运行时（ipvbs_s.py / ipvbs.py）与 devx_qp_helper.py；\n'
        '3. 测试机与 server 节点 SSH 免密连通。'
    )
    test_steps = (
        "1. 初始化 RDMA 测试框架与 ipvbs 会话；\n2. 创建 Mlx5Context 与 PD，探测 GENERAL_OBJECT MKEY 支持；\n3. 创建 MKEY 并记录；\n4. 重建 Mlx5Context 与 PD；\n5. 尝试使用旧对象调用 destroy_mkey_via_general_object，验证失败或异常被捕获；\n6. 在新上下文中创建并销毁新 MKEY，验证正常；\n7. 清理资源。"
    )

    @classmethod
    def set_parameters(cls) -> None:
        cls.test_object = 'RDMA MKEY（内存键）'
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
        """自动部署 devx_qp_helper.py 到远端。"""
        remote_dir = '/root/sxetest'
        local_dir = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

        env_entry = cls._get_env_entry_for_exec_addr()
        ip = env_entry.get('ip') if env_entry else None
        port = str(env_entry.get('port')) if env_entry else '22'
        if not ip:
            log.warning('无法获取执行端 IP，跳过 helper 自动部署。')
            return

        CommandOperation.execute_command_with_error(
            f'mkdir -p {remote_dir}', cls._exec_addr)

        files_to_deploy = [
            ('devx_qp_helper.py', 'devx_qp_helper.py'),
        ]
        for local_name, remote_name in files_to_deploy:
            local_path = os.path.join(local_dir, local_name)
            remote_path = os.path.join(remote_dir, remote_name)
            if not os.path.isfile(local_path):
                log.warning(f'本地文件不存在: {local_path}，跳过。')
                continue
            log.info(f'正在同步 {local_name} 到远程: '
                     f'{ip}:{remote_path}')
            rtn, _, _ = FileOperation.scp_file_to_remote(
                localfile_path=local_path,
                remotefile_path=remote_path,
                ip=ip,
                port=port,
                cmd_execute_address=cls._exec_addr
            )
            if rtn != RtnStatusEnum.SUCCESS.value:
                log.warning(f'{local_name} 自动部署可能失败，rtn={rtn}')
            else:
                log.info(f'{local_name} 自动部署完成。')

    @classmethod
    def prepare(cls) -> None:
        log.info(f'prepare: 初始化 GENERAL_OBJECT MKEY 上下文重建销毁MKEY测试环境 '
                 f'(opcode={cls._OPCODE_NAME}, dev={cls._rdma_dev})。')
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 MKEY 测试环境。')
            return
        cls._mkey_objs = []
        # 采用 SOCKET 通信模式（设备端未安装 screen）
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)
        cls._deploy_helper_if_needed()

        # 加载 helper、创建 Mlx5Context、创建 PD
        setup_cmds = [
            # 加载 DevX helper（需提前置于 /root/sxetest/）
            "glb_helper = __import__('devx_qp_helper')",
            # 加载 pyverbs mlx5 DevX 模块
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', "
            "fromlist=['Mlx5Context', 'Mlx5DVContextAttr', 'Mlx5DevxObj'])",
            "glb_Mlx5Context = glb_mlx5dv.Mlx5Context",
            "glb_Mlx5DVContextAttr = glb_mlx5dv.Mlx5DVContextAttr",
            "glb_Mlx5DevxObj = glb_mlx5dv.Mlx5DevxObj",
            # 创建 Mlx5Context
            f"glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '{cls._rdma_dev}')",
            # 创建 PD（MKEY 必须绑定 PD）
            "glb_pd_ret = glb_helper.create_devx_pd(glb_mlx5_ctx)",
            "glb_pd_obj = glb_pd_ret[0]",
            "glb_pd_num = glb_pd_ret[1]",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'创建 Mlx5Context/PD 失败, dev={cls._rdma_dev}, '
                    f'cmd={cmd}, rtn={result}')
                return
        # 读取 PD 号用于日志
        status, pd_num = cls._ipvbs.exec_and_get_ipvbs_result(
            'str(glb_pd_num)')
        if status == IpvbsStatusEnum.SUCCESS.value:
            log.info(f'Mlx5Context 与 PD 创建成功 (pd={pd_num}).')
        else:
            log.info('Mlx5Context 与 PD 创建成功。')

        # 探测当前环境是否支持 CREATE_GENERAL_OBJECT + MLX5_OBJ_TYPE_MKEY 创建 MKEY
        cls._probe_mkey_general_object_support()
        if not cls._mkey_supported:
            return

    @classmethod
    def _probe_mkey_general_object_support(cls) -> None:
        """在设备端实测 CREATE_GENERAL_OBJECT + MLX5_OBJ_TYPE_MKEY 是否受支持。"""
        probe_cmds = [
            "glb_mkey_support_ret = glb_helper.query_mkey_general_object_support(glb_mlx5_ctx)",
            "glb_mkey_supported = glb_mkey_support_ret[0]",
        ]
        for cmd in probe_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                log.warning(f'探测 GENERAL_OBJECT MKEY 支持失败: {cmd}, rtn={result}')
                cls._mkey_supported = False
                cls.own_environment_enabled = False
                return
        status, supported = cls._ipvbs.exec_and_get_ipvbs_result(
            'str(glb_mkey_supported)')
        cls._mkey_supported = (supported or '').strip().lower() == 'true'
        if not cls._mkey_supported:
            log.warning(
                '当前环境固件不支持通过 CREATE_GENERAL_OBJECT + '
                'MLX5_OBJ_TYPE_MKEY 创建 MKEY，'
                '该用例被标记为跳过（SKIP）。')
            cls.own_environment_enabled = False
            return
        log.info(
            '当前环境支持通过 CREATE_GENERAL_OBJECT + '
            'MLX5_OBJ_TYPE_MKEY 创建 MKEY。')

    @classmethod
    def do(cls) -> None:
        if not cls._mkey_supported:
            log.warning(
                '当前环境不支持 CREATE_GENERAL_OBJECT + MLX5_OBJ_TYPE_MKEY '
                '销毁 MKEY，跳过 do()。')
            return
        log.info('do: DevX GENERAL_OBJECT MKEY 上下文重建销毁测试。')
        cls._do_create_old_mkey()
        cls._do_rebuild_context()
        cls._do_destroy_old_after_rebuild()
        cls._do_create_destroy_new()
    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 MKEY 资源 (共 {len(cls._mkey_objs)} 个)。')
        for mkey_name in list(cls._mkey_objs):
            cls._close_mkey(mkey_name)
        cls._mkey_objs = []
        # 释放 PD 与上下文
        if cls._ipvbs is not None:
            cls._ipvbs.exec_and_get_ipvbs_result('glb_pd_obj.close()')
            cls._ipvbs.exec_and_get_ipvbs_result('glb_mlx5_ctx.close()')
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    # ------------------------------------------------------------------ #
    #  MKEY 操作辅助方法                                                   #
    # ------------------------------------------------------------------ #

    @classmethod
    def _create_mkey(cls, mkey_name: str) -> tuple:
        """通过 helper 分配一个 MKEY，返回 (status, mkey)。"""
        glb_mkey_name = f'glb_{mkey_name}'
        create_cmds = [
            # 通过 CREATE_GENERAL_OBJECT + MLX5_OBJ_TYPE_MKEY 创建 MKEY
            f"{glb_mkey_name}_ret = glb_helper.create_mkey_via_general_object(glb_mlx5_ctx, glb_pd_num, length={cls._MKEY_LENGTH})",
            f"{glb_mkey_name} = {glb_mkey_name}_ret[0]",
            f"{glb_mkey_name}_num = {glb_mkey_name}_ret[1]",
        ]
        for cmd in create_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                log.error(f'创建 MKEY 命令失败: {cmd}, rtn={result}')
                return status, None

        status, mkey = cls._ipvbs.exec_and_get_ipvbs_result(
            f"str({glb_mkey_name}_num)")
        if status != IpvbsStatusEnum.SUCCESS.value:
            return status, None

        cls._mkey_objs.append(mkey_name)
        mkey = (mkey or '').strip()
        log.info(f'MKEY 创建成功: {mkey_name}, mkey={mkey}')
        return IpvbsStatusEnum.SUCCESS.value, mkey

    @classmethod
    def _close_mkey(cls, mkey_name: str) -> bool:
        """释放指定 MKEY 资源。"""
        glb_mkey_name = f'glb_{mkey_name}'
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"glb_helper.destroy_mkey_via_general_object({glb_mkey_name})")
        if status == IpvbsStatusEnum.SUCCESS.value:
            log.info(f'MKEY 释放成功: {mkey_name}')
            if mkey_name in cls._mkey_objs:
                cls._mkey_objs.remove(mkey_name)
            return True
        log.warning(f'MKEY 释放异常: {mkey_name}, rtn={result}')
        return False

    # ------------------------------------------------------------------ #
    #  检查点                                                             #
    # ------------------------------------------------------------------ #


    @classmethod
    def _expect_fail(cls, cmd: str, cp_name: str, desc: str) -> None:
        """执行一条预期失败的命令，若成功则记录 bug。"""
        log.info(f'[{cp_name}] {desc}')
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
        if status == IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'{cp_name} 期望失败但实际成功: {desc}, cmd={cmd}, rtn={result}')
        else:
            log.info(f'{cp_name} 符合预期: 异常场景返回失败。')

    @classmethod
    def _do_create_old_mkey(cls) -> None:
        """CP1: 在原始上下文中创建 MKEY。"""
        log.info('[CP1] 原始上下文创建 MKEY。')
        status, mkey = cls._create_mkey('obj_mkey_old')
        if status != IpvbsStatusEnum.SUCCESS.value or not mkey:
            cls.set_bug_type('功能问题')
            cls.create_bug('原始上下文创建 MKEY 失败。')
            return
        log.info(f'[CP1] 旧 MKEY: {mkey}')

    @classmethod
    def _do_rebuild_context(cls) -> None:
        """CP2: 重建 Mlx5Context 与 PD。"""
        log.info('[CP2] 重建 Mlx5Context。')
        cls._ipvbs.exec_and_get_ipvbs_result('glb_pd_obj.close()')
        cls._ipvbs.exec_and_get_ipvbs_result('glb_mlx5_ctx.close()')
        rebuild_cmds = [
            f"glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '{cls._rdma_dev}')",
            "glb_pd_ret = glb_helper.create_devx_pd(glb_mlx5_ctx)",
            "glb_pd_obj = glb_pd_ret[0]",
            "glb_pd_num = glb_pd_ret[1]",
        ]
        for cmd in rebuild_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'重建 Mlx5Context/PD 失败, cmd={cmd}, rtn={result}')
                return
        log.info('[CP2] Mlx5Context 重建成功。')

    @classmethod
    def _do_destroy_old_after_rebuild(cls) -> None:
        """CP3: 重建后尝试销毁旧 MKEY，期望失败。"""
        log.info('[CP3] 重建后尝试销毁旧 MKEY。')
        cls._expect_fail(
            "glb_helper.destroy_mkey_via_general_object(glb_obj_mkey_old)",
            'CP3', '重建上下文后销毁旧 MKEY')

    @classmethod
    def _do_create_destroy_new(cls) -> None:
        """CP4: 在新上下文中创建并销毁新 MKEY。"""
        log.info('[CP4] 新上下文创建并销毁 MKEY。')
        status, mkey = cls._create_mkey('obj_mkey_new')
        if status != IpvbsStatusEnum.SUCCESS.value or not mkey:
            cls.set_bug_type('功能问题')
            cls.create_bug('新上下文创建 MKEY 失败。')
            return
        if not cls._close_mkey('obj_mkey_new'):
            cls.set_bug_type('功能问题')
            cls.create_bug('新上下文销毁 MKEY 失败。')
            return
        log.info(f'[CP4] 新 MKEY 创建并销毁成功: mkey={mkey}')

if __name__ == '__main__':
    NicLinuxRdmaDevxF0653009020PfDestroyMkeyGeneralObjectContextRebuildDestroyMkey().run()
