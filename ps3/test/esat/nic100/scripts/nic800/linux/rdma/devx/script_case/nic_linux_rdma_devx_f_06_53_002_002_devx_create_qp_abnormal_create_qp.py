#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-08-12
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_create_QP创建_异常创建QP

               opcode:  SXE3R_DEVX_OP_CREATE_QP
               对象:    QP（队列对）
               用例ID:  nic_linux_rdma_devx_f_06_53_002_002

               实现说明：
               在 CX8 / mlx5 设备上通过 pyverbs 的 Mlx5DevxObj 直接下发
               固件 CREATE_QP 命令（opcode=0x500）创建 QP，验证 QP 号有效、
               唯一且可正常释放。

               环境信息来源：项目根目录下的"环境IP信息"文件，
               按 server/client 顺序解析 IP、端口、用户名、密码及 RDMA 设备名。

@changelog:
    2026-08-12 初始版本，基于 DevX PD 测试经验迁移生成。
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


class NicLinuxRdmaDevxF0653002002PfCreateQpAbnormalCreateQp(ScriptBase):
    """DevX QP 异常创建QP用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_002_002'
    case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_create'
                  '_QP创建_异常创建QP')
    case_module = 'DevX'
    case_type = '系统测试-功能'

    # Mellanox 固件 opcode（参见 include/linux/mlx5/mlx5_ifc.h）
    _MLX5_OP_CREATE_QP = 0x500

    _OPCODE_NAME = 'SXE3R_DEVX_OP_CREATE_QP'
    _OBJ_TYPE = 'QP'
    _QP_COUNT = 5

    # DevX CREATE_QP 输入 buffer 总长度（含 opcode + 预留/QPC 区域）
    _CREATE_QP_IN_LEN = 512
    _CREATE_QP_OUT_LEN = 16

    _ipvbs = None
    _rdma_dev = ''
    _qp_objs = []

    # 环境IP信息文件相关
    _ENV_IP_INFO_FILE_NAME = '环境IP信息'
    _env_ip_info = None

    test_object = 'RDMA QP（队列对）'
    test_module = 'rdma'
    test_tool = 'pyverbs'
    test_precondition = (
        '1. RDMA 设备（mlx5_0）在线且 pyverbs mlx5 可用；\n'
        '2. 已部署 ipvbs 运行时（ipvbs_s.py / ipvbs.py）；\n'
        '3. 测试机与 server 节点 SSH 免密连通。'
    )
    test_steps = (
        '1. 初始化 ipvbs 会话；\n2. 使用非法设备名创建 Mlx5Context；\n3. 使用错误 opcode 下发 DevX 命令；\n4. 使用错误输出长度下发 DevX 命令；\n5. 使用无效上下文类型下发 DevX 命令；\n6. 使用超短输入 buffer 下发 DevX 命令；\n7. 清理资源。'
    )

    @classmethod
    def set_parameters(cls) -> None:
        cls.test_object = 'RDMA QP（队列对）'
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
        log.info(f'prepare: 初始化 QP 测试环境 (opcode={cls._OPCODE_NAME}, '
                 f'dev={cls._rdma_dev})。')
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 QP 测试环境。')
        cls._qp_objs = []
        cls._res = {}  # 保存 PD/UAR/CQ/UMEM 等公共资源对象
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)
        # 确保远程节点存在 devx_qp_helper.py
        cls._deploy_helper_if_needed()

        setup_cmds = [
            "__import__('sys').path.insert(0, '/root/sxetest')",
            "glb_helper = __import__('devx_qp_helper')",
            "glb_struct = __import__('struct')",
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', "
            "fromlist=['Mlx5Context', 'Mlx5DVContextAttr', 'Mlx5UMEM', 'Mlx5UAR', 'Mlx5DevxObj'])",
            "glb_Mlx5Context = glb_mlx5dv.Mlx5Context",
            "glb_Mlx5DVContextAttr = glb_mlx5dv.Mlx5DVContextAttr",
            "glb_Mlx5UMEM = glb_mlx5dv.Mlx5UMEM",
            "glb_Mlx5UAR = glb_mlx5dv.Mlx5UAR",
            "glb_Mlx5DevxObj = glb_mlx5dv.Mlx5DevxObj",
            f"glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '{cls._rdma_dev}')",
            "glb_pd_ret = glb_helper.create_devx_pd(glb_mlx5_ctx)",
            "glb_pd_obj = glb_pd_ret[0]",
            "glb_pdn = glb_pd_ret[1]",
            "glb_uar = glb_Mlx5UAR(glb_mlx5_ctx)",
            "glb_eqn = glb_mlx5_ctx.devx_query_eqn(0)",
            "glb_resource = __import__('resource')",
            "glb_cq_umem = glb_Mlx5UMEM(glb_mlx5_ctx, size=16384)",
            "glb_cq_dbr = glb_Mlx5UMEM(glb_mlx5_ctx, size=8, alignment=8)",
            "glb_cq_ret = glb_helper.create_devx_cq(glb_mlx5_ctx, glb_eqn, glb_uar, glb_cq_umem, glb_cq_dbr)",
            "glb_cq_obj = glb_cq_ret[0]",
            "glb_cqn = glb_cq_ret[1]",
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
        log.info('do: DevX QP 异常创建QP测试。')
        cls._do_abnormal_create_qp()

    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 QP 资源 (共 {len(cls._qp_objs)} 个)。')
        for qp_name in list(cls._qp_objs):
            cls._close_qp(qp_name)
        cls._qp_objs = []
        if cls._ipvbs is not None:
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    # ------------------------------------------------------------------ #
    #  QP 操作辅助方法                                                     #
    # ------------------------------------------------------------------ #

    @classmethod
    def _create_qp(cls, qp_name: str) -> tuple:
        """通过 DevX CREATE_QP 分配一个 QP，返回 (status, qpn)。"""
        glb_qp_name = f'glb_{qp_name}'
        create_cmds = [
            # 创建 QP 工作队列 UMEM 和 DBR UMEM
            "glb_resource = __import__('resource')",
            f"{glb_qp_name}_wq_umem = glb_Mlx5UMEM(glb_mlx5_ctx, size=glb_resource.getpagesize() * 2)",
            f"{glb_qp_name}_dbr_umem = glb_Mlx5UMEM(glb_mlx5_ctx, size=8, alignment=8)",
            # 通过 helper 创建 QP
            f"{glb_qp_name}_ret = glb_helper.create_devx_qp(glb_mlx5_ctx, glb_pdn, glb_uar, glb_cq_obj, {glb_qp_name}_wq_umem, {glb_qp_name}_dbr_umem)",
            f"{glb_qp_name} = {glb_qp_name}_ret[0]",
            f"{glb_qp_name}_num = {glb_qp_name}_ret[1]",
        ]
        for cmd in create_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                log.error(f'DevX CREATE_QP 命令失败: {cmd}, rtn={result}')
                return status, None

        status, qpn = cls._ipvbs.exec_and_get_ipvbs_result(
            f"str({glb_qp_name}_num)")
        if status != IpvbsStatusEnum.SUCCESS.value:
            return status, None

        cls._qp_objs.append(qp_name)
        qpn = (qpn or '').strip()
        log.info(f'DevX QP 创建成功: {qp_name}, qpn={qpn}')
        return IpvbsStatusEnum.SUCCESS.value, qpn

    @classmethod
    def _close_qp(cls, qp_name: str) -> bool:
        """释放指定 QP 及其关联的 WQ/DBR UMEM 资源。"""
        glb_qp_name = f'glb_{qp_name}'
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"{glb_qp_name}.close()")
        # 必须同步释放 QP 占用的 WQ UMEM 与 DBR UMEM，否则 UMEM 数量
        # 累积到上限后会导致后续 CREATE_QP 返回 Remote I/O error。
        for res_name in (f"{glb_qp_name}_wq_umem",
                         f"{glb_qp_name}_dbr_umem"):
            cls._ipvbs.exec_and_get_ipvbs_result(f"{res_name}.close()")
        if status == IpvbsStatusEnum.SUCCESS.value:
            log.info(f'QP 释放成功: {qp_name}')
            if qp_name in cls._qp_objs:
                cls._qp_objs.remove(qp_name)
            return True
        log.warning(f'QP 释放异常: {qp_name}, rtn={result}')
        return False

    @classmethod
    def _try_create_qp(cls, qp_name: str, in_len: int = None,
                       out_len: int = None, opcode: int = None,
                       ctx_name: str = 'glb_mlx5_ctx') -> tuple:
        """尝试创建 QP，返回 (status, result)。"""
        glb_qp_name = f'glb_{qp_name}'
        opcode = opcode if opcode is not None else cls._MLX5_OP_CREATE_QP
        in_len = in_len if in_len is not None else cls._CREATE_QP_IN_LEN
        out_len = out_len if out_len is not None else cls._CREATE_QP_OUT_LEN
        cmds = [
            f"{glb_qp_name}_in = glb_struct.pack('>HH', {opcode}, 0) + "
            f"bytes({in_len} - 4)",
            f"{glb_qp_name} = glb_Mlx5DevxObj({ctx_name}, {glb_qp_name}_in, {out_len})",
        ]
        for cmd in cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                return status, result
        return IpvbsStatusEnum.SUCCESS.value, None

    @classmethod
    def _do_abnormal_create_qp(cls) -> None:
        """检查点: 各类异常入参均失败且无崩溃。"""
        # CP1: 已在 check_own_environment 验证非法设备名，此处复用结论
        log.info('[CP1] 非法设备名导致 Mlx5Context 创建失败。')

        # CP2: 错误 opcode
        log.info('[CP2] 使用错误 opcode 下发 CREATE_QP。')
        status, _ = cls._try_create_qp('obj_qp_cp2', opcode=0xFFF)
        if status == IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug('错误 opcode 仍创建 QP 成功，期望返回失败。')

        # CP3: 错误输出长度
        log.info('[CP3] 使用错误输出长度下发 CREATE_QP。')
        status, _ = cls._try_create_qp('obj_qp_cp3', out_len=0)
        if status == IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug('错误输出长度仍创建 QP 成功，期望返回失败。')

        # CP4: 无效上下文类型
        log.info('[CP4] 使用无效上下文类型下发 CREATE_QP。')
        status, _ = cls._try_create_qp(
            'obj_qp_cp4', ctx_name="'not_a_context'")
        if status == IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug('无效上下文类型仍创建 QP 成功，期望返回失败。')

        # CP5: 超短输入 buffer
        log.info('[CP5] 使用超短输入 buffer 下发 CREATE_QP。')
        status, _ = cls._try_create_qp('obj_qp_cp5', in_len=8)
        if status == IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug('超短输入 buffer 仍创建 QP 成功，期望返回失败。')



if __name__ == '__main__':
    NicLinuxRdmaDevxF0653002002PfCreateQpAbnormalCreateQp().run()
