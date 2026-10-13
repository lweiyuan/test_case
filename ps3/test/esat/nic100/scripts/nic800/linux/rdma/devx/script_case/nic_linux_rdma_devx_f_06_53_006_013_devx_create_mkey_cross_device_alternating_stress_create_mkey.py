#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-08-24
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_create_MKEY创建_跨设备交替压力

               opcode:  SXE3R_DEVX_OP_CREATE_MKEY (0x200)
               对象:    MKEY（内存键 / MR）
               用例ID:  nic_linux_rdma_devx_f_06_53_006_013

               实现说明：
               在多个 RDMA 设备上以随机顺序交替创建/释放 MKEY（固定种子），
               每步校验各设备内 mkey 唯一，验证跨设备资源隔离与压力鲁棒性。

               注意：部分平台 issi 使能后 DevX uid 下 CREATE_MKEY 被固件
               拒绝（errno 121），属环境能力限制。脚本在环境探测阶段识别
               该限制后将用例标记为跳过（SKIP），而非判失败。

               环境信息来源：项目根目录下的"环境IP信息"文件。

@changelog:
    2026-08-24 初始版本，基于 DevX 测试模式迁移生成。
"""
import os
import random
import re


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


class NicLinuxRdmaDevxF0653006013PfCreateMkeyCrossDeviceAlternatingStress(ScriptBase):
    """DevX MKEY 跨设备交替压力用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_006_013'
    case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_create'
                  '_MKEY创建_跨设备交替压力')
    case_module = 'DevX'
    case_type = '系统测试-功能'

    _MLX5_OP_CREATE_MKEY = 0x200
    _MLX5_OP_DESTROY_MKEY = 0x201

    _OPCODE_NAME = 'SXE3R_DEVX_OP_CREATE_MKEY'
    _OBJ_TYPE = 'MKEY'
    _MKEY_LENGTH = 4096
    _OPERATION_COUNT = 1000
    _MAX_CONCURRENT_PER_DEV = 20
    _RANDOM_SEED = 2024

    _ipvbs = None
    _rdma_dev = ''
    _rdma_devs = []
    _mkey_objs = []

    # 环境IP信息文件相关
    _ENV_IP_INFO_FILE_NAME = '环境IP信息'
    _env_ip_info = None

    test_object = 'RDMA MKEY（内存键）'
    test_module = 'rdma'
    test_tool = 'pyverbs'
    test_precondition = (
        '1. 存在多个 RDMA 设备（如 mlx5_0 / mlx5_1）且 pyverbs mlx5 可用；\n'
        '2. 已部署 ipvbs 运行时（ipvbs_s.py / ipvbs.py）与 devx_qp_helper.py；\n'
        '3. 测试机与 server 节点 SSH 免密连通。'
    )
    test_steps = (
        "1. 初始化 RDMA 测试框架与 ipvbs 会话；\n"
        "2. 探测所有可用 RDMA 设备并分别创建 Mlx5Context 与 PD；\n"
        "3. 以固定随机种子跨设备随机交替创建/释放 MKEY（默认 1000 次）；\n"
        "4. 每步校验各设备内存活 MKEY 编号唯一；\n"
        "5. 操作结束后释放全部存活 MKEY 并关闭各设备上下文。"
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
        """检查局部环境：存在多个 RDMA 设备且 pyverbs mlx5 DevX 可用。"""
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
        cls._rdma_devs = list(dev_list)
        if cls._rdma_dev and cls._rdma_dev not in dev_list:
            cls._report_env_error(
                f'指定的 RDMA 设备 {cls._rdma_dev} 不存在，'
                f'当前设备列表: {dev_list}')
            return
        if not cls._rdma_dev:
            cls._rdma_dev = dev_list[0]
        log.info(f'检测到 RDMA 设备: {dev_list}, 本用例使用: {cls._rdma_dev}, '
                 f'跨设备列表: {cls._rdma_devs}')

        # 至少需要 2 个设备才构成跨设备交替压力场景
        if len(cls._rdma_devs) < 2:
            log.warning('当前环境仅检测到 1 个 RDMA 设备，'
                        '跨设备交替压力场景不成立，用例被跳过（SKIP）。')
            cls.own_environment_enabled = False
            return

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

        # 4. 探测固件是否支持 DevX uid 下创建 MKEY
        if not cls._probe_devx_mkey_supported():
            log.warning('当前环境固件不支持 DevX uid 下创建 MKEY '
                        '(errno 121 / Remote I/O error)，'
                        '该用例被标记为跳过（SKIP）。')
            cls.own_environment_enabled = False
            return

        cls.own_environment_enabled = True

    @classmethod
    def _probe_devx_mkey_supported(cls) -> bool:
        """在设备端实测 DevX CREATE_MKEY 是否受固件支持。"""
        probe_cmd = (
            'python3 /root/sxetest/probe_mkey_support.py '
            + cls._rdma_dev
        )
        status, result, err = CommandOperation.execute_command_with_error(
            probe_cmd, cls._exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            log.error(f'DevX MKEY 能力探测执行失败: err={err}, result={result}')
            return False
        result = result or ''
        if 'DEVX_MKEY_SUPPORTED' in result:
            log.info('固件支持 DevX uid 下创建 MKEY。')
            return True
        if 'DEVX_MKEY_NOT_SUPPORTED' in result:
            log.warning('固件不支持 DevX uid 下创建 MKEY。')
            return False
        log.warning(f'DevX MKEY 能力探测结果未知: {result.strip()}')
        return False

    @classmethod
    def _deploy_helper_if_needed(cls) -> None:
        """自动部署 devx_qp_helper.py 与 probe_mkey_support.py 到远端。"""
        remote_dir = '/root/sxetest'
        local_dir = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

        env_entry = cls._get_env_entry_for_exec_addr()
        ip = env_entry.get('ip') if env_entry else None
        port = str(env_entry.get('port')) if env_entry else '22'
        if not ip:
            log.warning('无法获取执行端 IP，跳过 helper/probe 自动部署。')
            return

        CommandOperation.execute_command_with_error(
            f'mkdir -p {remote_dir}', cls._exec_addr)

        files_to_deploy = [
            ('devx_qp_helper.py', 'devx_qp_helper.py'),
            ('probe_mkey_support.py', 'probe_mkey_support.py'),
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
        log.info(f'prepare: 初始化 MKEY 跨设备交替压力环境 (devs={cls._rdma_devs})。')
        if not cls._rdma_devs:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 MKEY 测试环境。')
            return
        cls._mkey_objs = []
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)
        cls._deploy_helper_if_needed()

        setup_cmds = [
            "glb_helper = __import__('devx_qp_helper')",
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', "
            "fromlist=['Mlx5Context', 'Mlx5DVContextAttr', 'Mlx5DevxObj'])",
            "glb_Mlx5Context = glb_mlx5dv.Mlx5Context",
            "glb_Mlx5DVContextAttr = glb_mlx5dv.Mlx5DVContextAttr",
            "glb_Mlx5DevxObj = glb_mlx5dv.Mlx5DevxObj",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'加载 DevX 模块失败, cmd={cmd}, rtn={result}')
                return

        for dev in cls._rdma_devs:
            dev_suffix = dev.replace('-', '_')
            dev_cmds = [
                f"glb_ctx_{dev_suffix} = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '{dev}')",
                f"glb_pd_{dev_suffix}, glb_pdnum_{dev_suffix} = glb_helper.create_devx_pd(glb_ctx_{dev_suffix})",
            ]
            for cmd in dev_cmds:
                status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
                if status != IpvbsStatusEnum.SUCCESS.value:
                    cls.set_bug_type('功能问题')
                    cls.create_bug(
                        f'创建设备 {dev} 的 Mlx5Context/PD 失败, '
                        f'cmd={cmd}, rtn={result}')
                    return
            log.info(f'设备 {dev} 的 Mlx5Context/PD 创建成功。')

    @classmethod
    def do(cls) -> None:
        log.info('do: DevX MKEY 跨设备交替压力测试。')
        cls._do_alternating_stress()

    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理跨设备交替压力 MKEY 资源 (共 {len(cls._mkey_objs)} 个)。')
        cls._release_all_mkey()
        if cls._ipvbs is not None:
            for dev in cls._rdma_devs:
                dev_suffix = dev.replace('-', '_')
                cls._ipvbs.exec_and_get_ipvbs_result(
                    f'glb_pd_{dev_suffix}.close()')
                cls._ipvbs.exec_and_get_ipvbs_result(
                    f'glb_ctx_{dev_suffix}.close()')
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    # ------------------------------------------------------------------ #
    #  MKEY 操作辅助方法                                                   #
    # ------------------------------------------------------------------ #

    @classmethod
    def _create_mkey(cls, dev: str, mkey_name: str) -> tuple:
        """在指定设备上通过 DevX 分配一个 MKEY，返回 (status, mkey)。"""
        dev_suffix = dev.replace('-', '_')
        glb_mkey_name = f'glb_{mkey_name}'
        create_cmds = [
            f"{glb_mkey_name}_ret = glb_helper.create_devx_mkey(glb_ctx_{dev_suffix}, glb_pdnum_{dev_suffix}, length={cls._MKEY_LENGTH})",
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

        cls._mkey_objs.append((dev, mkey_name))
        mkey = (mkey or '').strip()
        return IpvbsStatusEnum.SUCCESS.value, mkey

    @classmethod
    def _close_mkey(cls, dev: str, mkey_name: str) -> bool:
        """释放指定设备上指定 MKEY 资源。"""
        glb_mkey_name = f'glb_{mkey_name}'
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"{glb_mkey_name}.close()")
        if status == IpvbsStatusEnum.SUCCESS.value:
            if (dev, mkey_name) in cls._mkey_objs:
                cls._mkey_objs.remove((dev, mkey_name))
            return True
        log.warning(f'MKEY 释放异常: dev={dev}, mkey={mkey_name}, rtn={result}')
        return False

    @classmethod
    def _release_all_mkey(cls) -> None:
        """兜底释放所有设备上残留的 MKEY。"""
        log.info('兜底清理所有设备上残留的 MKEY。')
        for dev, mkey_name in list(cls._mkey_objs):
            cls._close_mkey(dev, mkey_name)
        if not cls._mkey_objs:
            log.info('无残留 MKEY，跨设备交替压力资源已全部释放。')

    # ------------------------------------------------------------------ #
    #  检查点                                                             #
    # ------------------------------------------------------------------ #

    @classmethod
    def _do_alternating_stress(cls) -> None:
        """CP1: 跨设备随机交替创建/释放 MKEY，校验设备内 mkey 唯一。"""
        op_count = cls._OPERATION_COUNT
        max_concurrent = cls._MAX_CONCURRENT_PER_DEV
        random.seed(cls._RANDOM_SEED)

        # 每个设备的存活 MKEY: dev -> {mkey_name: mkey}
        alive_per_dev = {dev: {} for dev in cls._rdma_devs}
        next_index = {dev: 0 for dev in cls._rdma_devs}
        total_created = 0
        total_released = 0

        log.info(f'[CP1] 开始 {op_count} 次跨设备随机交替操作 '
                 f'(seed={cls._RANDOM_SEED}, '
                 f'max_concurrent/dev={max_concurrent})。')

        for step in range(op_count):
            # 选择一个设备（轮询+随机）
            dev = random.choice(cls._rdma_devs)
            alive = alive_per_dev[dev]
            can_create = len(alive) < max_concurrent
            can_release = bool(alive)

            if can_create and can_release:
                do_create = random.choice([True, False])
            elif can_create:
                do_create = True
            elif can_release:
                do_create = False
            else:
                continue

            if do_create:
                mkey_name = f'obj_mkey_dev{dev.replace("-", "_")}_{next_index[dev]}'
                next_index[dev] += 1
                status, mkey = cls._create_mkey(dev, mkey_name)
                if status != IpvbsStatusEnum.SUCCESS.value or not mkey:
                    cls.set_bug_type('功能问题')
                    cls.create_bug(
                        f'第 {step + 1} 步设备 {dev} 随机创建 MKEY 失败。')
                    return
                alive[mkey_name] = mkey
                total_created += 1
            else:
                mkey_name = random.choice(list(alive.keys()))
                if cls._close_mkey(dev, mkey_name):
                    del alive[mkey_name]
                    total_released += 1
                else:
                    cls.set_bug_type('功能问题')
                    cls.create_bug(
                        f'第 {step + 1} 步设备 {dev} 随机释放 '
                        f'MKEY {mkey_name} 失败。')
                    return

            # 校验该设备内 mkey 唯一
            nums = list(alive.values())
            if len(set(nums)) != len(nums):
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'第 {step + 1} 步设备 {dev} 出现重复 mkey: {nums}。')
                return

        log.info(f'[CP1] 跨设备交替压力完成: 创建 {total_created} 次，'
                 f'释放 {total_released} 次，'
                 f'最终存活 {sum(len(v) for v in alive_per_dev.values())} 个。')

        # 最后全部释放
        for dev in cls._rdma_devs:
            for mkey_name in list(alive_per_dev[dev].keys()):
                if not cls._close_mkey(dev, mkey_name):
                    cls.set_bug_type('功能问题')
                    cls.create_bug(
                        f'最终清理设备 {dev} 的 MKEY {mkey_name} 失败。')
                    return

        log.info('[CP1] 符合预期: 跨设备随机交替创建/释放无崩溃、'
                 '无重复 mkey、全部 MKEY 已释放。')


if __name__ == '__main__':
    NicLinuxRdmaDevxF0653006013PfCreateMkeyCrossDeviceAlternatingStress().run()
