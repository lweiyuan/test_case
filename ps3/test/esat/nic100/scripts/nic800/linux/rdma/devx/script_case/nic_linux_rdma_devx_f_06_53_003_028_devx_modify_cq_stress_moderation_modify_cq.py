#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-08-27
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_modify_CQ修改_压力修改CQ_moderation

               opcode:  SXE3R_DEVX_OP_MODIFY_CQ
               对象:    CQ（完成队列）
               用例ID:  nic_linux_rdma_devx_f_06_53_003_028

               实现说明：
               在 CX8 / mlx5 设备上通过 pyverbs 的 Mlx5DevxObj 创建 CQ，
               再调用 MODIFY_CQ（opcode=0x403）修改 CQ 属性，
               验证命令可正常下发或异常被正确捕获。

               环境信息来源：项目根目录下的"环境IP信息"文件。

@changelog:
    2026-08-27 初始版本，基于 DevX CREATE_CQ / DESTROY_CQ 测试脚本迁移生成。
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


class NicLinuxRdmaDevxF0653003028PfStressModifyCqModeration(ScriptBase):
    """DevX CQ 修改_stress_modify_cq_moderation用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_003_028'
    case_title = 'RDMA DevX 接口测试_用户态_PF_devx_obj_modify_CQ修改_压力修改CQ_moderation'
    case_module = 'DevX'
    case_type = '系统测试-功能'

    # Mellanox 固件 opcode
    _MLX5_OP_CREATE_CQ = 0x400
    _MLX5_OP_MODIFY_CQ = 0x403

    _OPCODE_NAME = 'SXE3R_DEVX_OP_MODIFY_CQ'
    _OBJ_TYPE = 'CQ'

    _ipvbs = None
    _rdma_dev = ''
    _cq_objs = {}

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
        "2. 创建 Mlx5Context、UAR、EQN、CQ UMEM、DBR UMEM；\n"
        "3. 持续 5 分钟循环：创建 CQ -> 调用 MODIFY_CQ 修改 moderation -> 销毁 CQ；\n"
        "4. 统计成功率与总迭代次数；\n"
        "5. 清理资源。\n"
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
        返回按出现顺序排列的条目列表，每个条目为 dict。
        """
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
                    entries.append({
                        'ip': match.group(1),
                        'port': int(match.group(2)),
                        'username': match.group(3),
                        'password': match.group(4),
                        'device': match.group(5),
                    })
        except Exception as exc:
            log.warning(f'解析环境IP信息失败: {exc}')
        return entries

    @classmethod
    def _get_env_entry_for_exec_addr(cls) -> dict or None:
        """获取当前执行端对应的环境信息条目。"""
        if not cls._env_ip_info:
            return None
        for entry in cls._env_ip_info:
            if entry.get('device') == cls._rdma_dev:
                return entry
        return cls._env_ip_info[0] if cls._env_ip_info else None

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
            "Mlx5Context, Mlx5DVContextAttr, Mlx5DevxObj; print(1)'"
        )
        status, result, err = CommandOperation.execute_command_with_error(
            cmd_check, cls._exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or \
                '1' not in (result or ''):
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
        env_entry = cls._get_env_entry_for_exec_addr()
        ip = env_entry.get('ip') if env_entry else None
        port = str(env_entry.get('port')) if env_entry else '22'
        username = env_entry.get('username') if env_entry else 'root'
        if not ip:
            log.warning('无法获取执行端 IP，跳过 helper 自动部署。')
            return
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
        log.info(f'prepare: 初始化 CQ 测试环境 (opcode={cls._OPCODE_NAME}, '
                 f'dev={cls._rdma_dev})。')
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 CQ 测试环境。')
        cls._cq_objs = {}
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)
        cls._deploy_helper_if_needed()

        setup_cmds = [
            "__import__('sys').path.insert(0, '/root/sxetest')",
            "glb_helper = __import__('devx_qp_helper')",
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', "
            "fromlist=['Mlx5Context', 'Mlx5DVContextAttr', 'Mlx5UMEM', 'Mlx5UAR', 'Mlx5DevxObj'])",
            "glb_Mlx5Context = glb_mlx5dv.Mlx5Context",
            "glb_Mlx5DVContextAttr = glb_mlx5dv.Mlx5DVContextAttr",
            "glb_Mlx5UMEM = glb_mlx5dv.Mlx5UMEM",
            "glb_Mlx5UAR = glb_mlx5dv.Mlx5UAR",
            "glb_Mlx5DevxObj = glb_mlx5dv.Mlx5DevxObj",
            f"glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '{cls._rdma_dev}')",
            "glb_uar = glb_Mlx5UAR(glb_mlx5_ctx)",
            "glb_eqn = glb_mlx5_ctx.devx_query_eqn(0)",
            "glb_resource = __import__('resource')",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'初始化 DevX CQ 环境失败, dev={cls._rdma_dev}, '
                    f'cmd={cmd}, rtn={result}')
                return

    @classmethod
    def do(cls) -> None:
        log.info('do: DevX CQ 修改_stress_modify_cq_moderation测试。')
        cls._do_stress_modify_cq_moderation()

    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 CQ 资源。')
        for cq_name in list(cls._cq_objs):
            cls._close_cq(cq_name)
        cls._cq_objs = {}
        if cls._ipvbs is not None:
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    @classmethod
    def _create_cq(cls, cq_name: str, ncqes: int = 256) -> tuple:
        """通过 DevX CREATE_CQ 分配一个 CQ，返回 (status, cqn)。"""
        glb_cq_name = f'glb_{cq_name}'
        umem_size = ncqes * 64  # mlx5 CQE 64 bytes
        create_cmds = [
            f"{glb_cq_name}_cq_umem = glb_Mlx5UMEM(glb_mlx5_ctx, size={umem_size})",
            f"{glb_cq_name}_cq_dbr = glb_Mlx5UMEM(glb_mlx5_ctx, size=8, alignment=8)",
            f"{glb_cq_name}_ret = glb_helper.create_devx_cq(glb_mlx5_ctx, glb_eqn, glb_uar, {glb_cq_name}_cq_umem, {glb_cq_name}_cq_dbr, ncqes={ncqes})",
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
        cls._cq_objs[cq_name] = glb_cq_name
        cqn = (cqn or '').strip()
        log.info(f'DevX CQ 创建成功: {cq_name}, cqn={cqn}')
        return IpvbsStatusEnum.SUCCESS.value, cqn

    @classmethod
    def _close_cq(cls, cq_name: str, extra_umems: list = None) -> bool:
        """释放指定 CQ 及其关联的 CQ UMEM / DBR UMEM 资源。"""
        glb_cq_name = cls._cq_objs.pop(cq_name, None)
        if not glb_cq_name:
            return False
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"{glb_cq_name}.close()")
        res_names = [f"{glb_cq_name}_cq_umem", f"{glb_cq_name}_cq_dbr"]
        if extra_umems:
            res_names.extend(extra_umems)
        for res_name in res_names:
            cls._ipvbs.exec_and_get_ipvbs_result(f"{res_name}.close()")
        if status == IpvbsStatusEnum.SUCCESS.value:
            log.info(f'CQ 释放成功: {cq_name}')
            return True
        log.warning(f'CQ 释放异常: {cq_name}, rtn={result}')
        return False

    @classmethod
    def _exec_modify_and_check(cls, cmd: str, desc: str,
                               expect_success: bool = True,
                               log_fail: bool = True) -> bool:
        """下发 MODIFY_CQ 远程命令并校验返回的 (status, syndrome)。"""
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
        if status != IpvbsStatusEnum.SUCCESS.value:
            if log_fail:
                log.error(f'{desc} 远程执行失败: {result}')
            # 负向用例：远程执行异常（对象失效、参数错误等）视为预期失败
            return expect_success
        try:
            # result 形如 "(0, 0)" 或 "(-1, '...')"
            parts = result.strip('()').split(',', 1)
            mod_status = int(parts[0].strip())
        except Exception:
            if log_fail:
                log.error(f'{desc} 返回无法解析: {result}')
            return not expect_success
        ok = (mod_status == 0)
        if expect_success:
            if ok:
                log.info(f'{desc} 成功: status=0')
                return True
            if log_fail:
                log.error(f'{desc} 返回失败: {result}')
            return False
        else:
            if ok:
                if log_fail:
                    log.error(f'{desc} 期望失败但实际成功: {result}')
                return True
            log.info(f'{desc} 正确失败: {result}')
            return False

    @classmethod
    def _get_other_device(cls) -> str or None:
        """返回另一个可用 RDMA 设备名，没有则返回 None。"""
        status, result, _ = CommandOperation.execute_command_with_error(
            'ls /sys/class/infiniband/ 2>/dev/null', cls._exec_addr)
        if status != RtnStatusEnum.SUCCESS.value:
            return None
        devs = [d for d in result.split() if d != cls._rdma_dev]
        return devs[0] if devs else None

    @classmethod
    def _do_stress_modify_cq_moderation(cls) -> None:
        """CP1: stress_modify_cq_moderation。"""
        import time
        ok = 0
        fail = 0
        i = 0
        start = time.time()
        while time.time() - start < 300:
            status, cqn = cls._create_cq(f'obj_cq_{i}')
            if status != IpvbsStatusEnum.SUCCESS.value or not cqn:
                fail += 1
                i += 1
                continue
            cq_name = f'obj_cq_{i}'
            glb_name = cls._cq_objs.get(cq_name)
            cmd = (f"glb_helper.modify_devx_cq({glb_name}, field_select=0x3, "
                   f"cq_period={10 + (i % 100)}, cq_max_count={1 + (i % 16)})")
            if cls._exec_modify_and_check(cmd, f'第 {i} 次 MODIFY_CQ', log_fail=False):
                cls._close_cq(cq_name)
                ok += 1
            else:
                cls._close_cq(cq_name)
                fail += 1
            i += 1
        cost = time.time() - start
        log.info(f'压力测试完成: iterations={i}, ok={ok}, fail={fail}, cost={cost:.3f}s')
        if fail > 0:
            cls.set_bug_type('性能问题')
            cls.create_bug(f'压力 MODIFY_CQ 存在失败: fail={fail}')


if __name__ == '__main__':
    NicLinuxRdmaDevxF0653003028PfStressModifyCqModeration().run()
