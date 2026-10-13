#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-08-11
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_create_PD创建_跨设备创建PD

               opcode:  SXE3R_DEVX_OP_CREATE_PD
               对象:    PD（保护域）
               用例ID:  nic_linux_rdma_devx_f_06_53_001_005

               实现说明：
               在 CX8 / mlx5 设备的多个 RDMA 设备（如 mlx5_0、mlx5_1）上
               分别通过 pyverbs 的 Mlx5DevxObj 下发固件 ALLOC_PD 命令创建 PD，
               验证各设备独立分配 PD、pd_num 不冲突且可分别释放。

               环境信息来源：项目根目录下的"环境IP信息"文件。

@changelog:
    2026-08-11 初始版本，覆盖多 RDMA 设备上独立创建/释放 PD 的跨设备场景。
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


class NicLinuxRdmaDevxF0653001005PfCreatePdCrossDevice(ScriptBase):
    """DevX PD 跨设备创建用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_001_005'
    case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_create'
                  '_PD创建_跨设备创建PD')
    case_module = 'DevX'
    case_type = '系统测试-功能'

    # Mellanox 固件 opcode
    _MLX5_OP_ALLOC_PD = 0x800

    _OPCODE_NAME = 'SXE3R_DEVX_OP_CREATE_PD'
    _OBJ_TYPE = 'PD'

    # 每个设备上创建的 PD 数量
    _PD_PER_DEVICE = 5

    _ipvbs = None
    _rdma_devs = []

    # 环境IP信息文件相关
    _ENV_IP_INFO_FILE_NAME = '环境IP信息'
    _env_ip_info = None

    test_object = 'RDMA PD（保护域）'
    test_module = 'rdma'
    test_tool = 'pyverbs'
    test_precondition = (
        '1. 至少一个 RDMA 设备（mlx5_0）在线且 pyverbs mlx5 可用；\n'
        '2. 若要进行真正的跨设备验证，需存在两个及以上 RDMA 设备（如 mlx5_0、mlx5_1）；\n'
        '3. 已部署 ipvbs 运行时（ipvbs_s.py / ipvbs.py）；\n'
        '4. 测试机与 server 节点 SSH 免密连通。'
    )
    test_steps = (
        '1. 初始化 ipvbs 会话；\n'
        '2. 自动探测所有可用 RDMA 设备，为每个设备创建 Mlx5Context；\n'
        '3. 在每个设备上通过 DevX ALLOC_PD 创建多个 PD；\n'
        '4. 校验每个设备内部 pd_num 唯一，设备间 PD 上下文独立；\n'
        '5. 依次释放各设备上的 PD，验证释放独立生效；\n'
        '6. 清理全部资源。'
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
        primary_dev = ''
        if env_entry:
            primary_dev = env_entry['device']
            log.info(
                f'从"环境IP信息"读取到执行端[{cls._exec_addr}]信息: '
                f"ip={env_entry['ip']}, port={env_entry['port']}, "
                f"username={env_entry['username']}, device={primary_dev}"
            )
        else:
            log.warning('未从"环境IP信息"获取到设备信息，将自动探测。')

        # 探测所有可用 RDMA 设备
        status, result, err = CommandOperation.execute_command_with_error(
            'ls /sys/class/infiniband/ 2>/dev/null', cls._exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or not result.strip():
            cls._report_env_error(f'未检测到 RDMA 设备, err={err}')
            return
        dev_list = sorted(result.split())
        log.info(f'检测到 RDMA 设备列表: {dev_list}')

        if primary_dev and primary_dev in dev_list:
            # 优先保证环境文件中指定的设备在首位
            dev_list.remove(primary_dev)
            dev_list.insert(0, primary_dev)
        elif primary_dev:
            cls._report_env_error(
                f'指定的 RDMA 设备 {primary_dev} 不存在，'
                f'当前设备列表: {dev_list}')
            return

        if not dev_list:
            cls._report_env_error('未检测到可用的 RDMA 设备。')
            return

        cls._rdma_devs = dev_list
        log.info(f'本用例将在以下设备上测试: {cls._rdma_devs}')

        if len(cls._rdma_devs) < 2:
            log.warning(
                '当前仅检测到一个 RDMA 设备，跨设备验证将退化为单设备验证；'
                '建议环境具备 mlx5_0 + mlx5_1 以覆盖完整场景。')

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
        log.info(f'prepare: 初始化跨设备 PD 测试环境 (opcode={cls._OPCODE_NAME}, '
                 f'devs={cls._rdma_devs})。')
        if not cls._rdma_devs:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化跨设备 PD 测试环境。')
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)
        # 确保远程节点存在 devx_qp_helper.py
        cls._deploy_helper_if_needed()

        # 公共模块与工具
        setup_common = [
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
        ]
        for cmd in setup_common:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'加载 pyverbs mlx5 DevX 模块失败, cmd={cmd}, rtn={result}')

        # 为每个目标设备创建独立的 Mlx5Context
        for dev in cls._rdma_devs:
            ctx_var = cls._ctx_var(dev)
            cmd = f"{ctx_var} = glb_Mlx5Context(glb_devx_attr, '{dev}')"
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'为设备 {dev} 创建 Mlx5Context 失败, cmd={cmd}, rtn={result}')
            log.info(f'设备 {dev} 的 Mlx5Context 创建成功。')

    @classmethod
    def do(cls) -> None:
        log.info('do: DevX PD 跨设备创建测试。')
        all_device_pd_nums = {}

        for dev in cls._rdma_devs:
            pd_nums = cls._do_create_on_device(dev)
            all_device_pd_nums[dev] = pd_nums

        cls._do_check_cross_device_independence(all_device_pd_nums)
        cls._do_release_per_device()

    @classmethod
    def post(cls) -> None:
        log.info('post: 清理跨设备 PD 资源。')
        cls._do_release_per_device()

        # 关闭每个设备的 Mlx5Context
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

    # ------------------------------------------------------------------ #
    #  变量命名辅助                                                        #
    # ------------------------------------------------------------------ #

    @classmethod
    def _ctx_var(cls, dev: str) -> str:
        """返回某设备 Mlx5Context 在 ipvbs 中的变量名。"""
        return f"glb_mlx5_ctx_{dev.replace('-', '_')}"

    @classmethod
    def _pd_var(cls, dev: str, pd_name: str) -> str:
        """返回某设备上某 PD 对象在 ipvbs 中的变量名。"""
        return f"glb_pd_{dev.replace('-', '_')}_{pd_name}"

    # ------------------------------------------------------------------ #
    #  PD 操作辅助方法                                                     #
    # ------------------------------------------------------------------ #

    @classmethod
    def _alloc_pd(cls, dev: str, pd_name: str) -> tuple:
        """在指定设备上通过 DevX ALLOC_PD 分配一个 PD，返回 (status, pd_num)。"""
        ctx_var = cls._ctx_var(dev)
        pd_var = cls._pd_var(dev, pd_name)
        alloc_cmds = [
            f"{pd_var}_in = glb_struct.pack('>HHHHQ', "
            f"{cls._MLX5_OP_ALLOC_PD}, 0, 0, 0, 0)",
            f"{pd_var} = glb_Mlx5DevxObj({ctx_var}, {pd_var}_in, 16)",
            f"{pd_var}_num = glb_struct.unpack('>I', "
            f"{pd_var}.out_view[8:12])[0] & 0xFFFFFF",
        ]
        for cmd in alloc_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                log.error(f'设备 {dev} DevX ALLOC_PD 命令失败: {cmd}, rtn={result}')
                return status, None

        status, pd_num = cls._ipvbs.exec_and_get_ipvbs_result(
            f"str({pd_var}_num)")
        if status != IpvbsStatusEnum.SUCCESS.value:
            return status, None

        pd_num = (pd_num or '').strip()
        log.info(f'设备 {dev} DevX PD 分配成功: {pd_name}, pd_num={pd_num}')
        return IpvbsStatusEnum.SUCCESS.value, pd_num

    @classmethod
    def _close_pd(cls, dev: str, pd_name: str) -> bool:
        """释放指定设备上的指定 PD。"""
        pd_var = cls._pd_var(dev, pd_name)
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f'{pd_var}.close()')
        if status == IpvbsStatusEnum.SUCCESS.value:
            log.info(f'设备 {dev} PD 释放成功: {pd_name}')
            return True
        log.warning(f'设备 {dev} PD 释放异常: {pd_name}, rtn={result}')
        return False

    # ------------------------------------------------------------------ #
    #  检查点                                                             #
    # ------------------------------------------------------------------ #

    @classmethod
    def _do_create_on_device(cls, dev: str) -> list:
        """CP1: 在单个设备上创建多个 PD，校验设备内 pd_num 唯一。"""
        n = cls._PD_PER_DEVICE
        log.info(f'[CP1][{dev}] 在设备 {dev} 上创建 {n} 个 PD。')
        pd_nums = []
        for i in range(n):
            pd_name = f'cp1_{i}'
            status, pd_num = cls._alloc_pd(dev, pd_name)
            if status != IpvbsStatusEnum.SUCCESS.value or not pd_num:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'设备 {dev} 第 {i + 1}/{n} 个 PD 创建失败，'
                    f'期望 {n} 次 PD 分配均成功。')
                return pd_nums
            pd_nums.append(pd_num)

        if len(set(pd_nums)) != n:
            cls.set_bug_type('功能问题')
            cls.create_bug(
                f'设备 {dev} 上 {n} 个 PD 的 pd_num 不唯一: {pd_nums}，'
                f'期望同一设备内每个 PD 返回互不相同的 pd_num。')
        else:
            log.info(f'[CP1][{dev}] {n} 个 PD pd_num 唯一: {pd_nums}')
        return pd_nums

    @classmethod
    def _do_check_cross_device_independence(cls, all_device_pd_nums: dict) -> None:
        """CP2: 校验各设备 PD 号集合独立，不存在跨设备上下文串扰。"""
        devs = list(all_device_pd_nums.keys())
        if len(devs) < 2:
            log.warning(
                '[CP2] 仅有一个设备可用，跳过跨设备独立性断言。')
            return

        log.info('[CP2] 校验跨设备 PD 分配独立性。')

        # 注意：不同设备的 pd_num 允许相同（PD 号是 per-context 的），
        # 因此不将 pd_num 交集作为失败或告警条件，仅作信息记录。
        for i in range(len(devs)):
            for j in range(i + 1, len(devs)):
                dev_a, dev_b = devs[i], devs[j]
                set_a = set(all_device_pd_nums.get(dev_a, []))
                set_b = set(all_device_pd_nums.get(dev_b, []))
                overlap = set_a & set_b
                log.info(
                    f'[CP2] 设备 {dev_a} 与 {dev_b} 的 pd_num 交集: '
                    f'{overlap if overlap else "无"}。'
                    f'PD 号跨设备独立，重叠属于正常现象。')

        # 进一步验证：在每个设备上再创建 1 个 PD，确认仍然成功，
        # 说明设备 A 的 PD 创建不影响设备 B 的可用资源。
        for dev in devs:
            extra_name = 'cp2_extra'
            status, pd_num = cls._alloc_pd(dev, extra_name)
            if status != IpvbsStatusEnum.SUCCESS.value or not pd_num:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'设备 {dev} 在他设备已创建 PD 后再次创建失败，'
                    f'期望各设备资源池相互独立。')
                return
            log.info(f'[CP2][{dev}] 他设备创建 PD 后本设备仍可创建，'
                     f'pd_num={pd_num}')

    @classmethod
    def _do_release_per_device(cls) -> None:
        """CP3: 依次释放每个设备上的所有 PD，验证释放独立生效。"""
        log.info('[CP3] 逐个设备释放全部 PD。')
        for dev in cls._rdma_devs:
            for i in range(cls._PD_PER_DEVICE):
                pd_name = f'cp1_{i}'
                cls._close_pd(dev, pd_name)
            # 也释放 CP2 的额外 PD
            cls._close_pd(dev, 'cp2_extra')
        log.info('[CP3] 跨设备 PD 释放完成。')


if __name__ == '__main__':
    NicLinuxRdmaDevxF0653001005PfCreatePdCrossDevice().run()
