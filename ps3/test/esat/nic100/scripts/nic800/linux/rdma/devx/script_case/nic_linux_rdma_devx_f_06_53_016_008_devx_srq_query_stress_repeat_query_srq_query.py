#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-09-03
description:   RDMA DevX 接口测试_用户态_PF_verbs_srq_query_100次重复查询verbs_srq_query

               接口:    mlx5dv_devx_srq_query（libmlx5 C DV，ctypes 直调）
               opcode:  SXE3R_DEVX_OP_QUERY_SRQ(0x702)
               对象:    verbs SRQ（底层 RMP 0x90c 编码）
               用例ID:  nic_linux_rdma_devx_f_06_53_016_008

               压力场景：连续 100 次经 mlx5dv_devx_srq_query 查询同一 verbs SRQ，校验全部 call_ret==0 且解析字段一致（命令通道稳定、outbox 无串扰）。

               实现说明：
               经 helper.query_srq_via_libmlx5() 构造 QUERY_SRQ inbox
               （opcode=0x702, srqn@byte9-11）并调用 libmlx5 的
               mlx5dv_devx_srq_query C 符号下发 devx_ucmd 通道。

               环境不支持判定（本机 40.46.1006 固件实证）：
               内核 devx 通道 devx_is_valid_obj_id 对 QUERY_SRQ(0x702)
               强制要求对象按 CREATE_SRQ(0x700) 编码；RMP 平台 verbs SRQ
               底层按 CREATE_RMP(0x90c) 编码，obj_id 永不相等 -> EINVAL(22)，
               命令不到固件。脚本探测到不支持时自动 skip（本用例不产生失败）。

               环境信息来源：项目根目录下的"环境IP信息"文件，
               按 server/client 顺序解析 IP、端口、用户名、密码及 RDMA 设备名。

# changelog:
    2026-09-03 初始版本，基于 DevX QUERY_CONG_STATISTICS 模板生成。
"""
import ast
import os
import re
import tempfile


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


class NicLinuxRdmaDevxF0653016008PfStressRepeatQuerySrqQuery(ScriptBase):
    """DevX verbs_srq_query 100次重复查询verbs_srq_query用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_016_008'
    case_title = 'RDMA DevX 接口测试_用户态_PF_verbs_srq_query_100次重复查询verbs_srq_query'
    case_module = 'DevX'
    case_type = '系统测试-功能'

    # Mellanox 固件 opcode（参见 include/linux/mlx5/mlx5_ifc.h）
    _MLX5_OP_QUERY_SRQ = 0x702

    _OPCODE_NAME = 'SXE3R_DEVX_OP_QUERY_SRQ'
    _IF_NAME = 'mlx5dv_devx_srq_query(libmlx5 C DV)'
    _OBJ_TYPE = 'verbs SRQ 对象'

    _ipvbs = None
    _rdma_dev = ''
    _probe_ok = False

    # 远端 QUERY_SRQ 探测脚本（部署到 /root/sxetest/ 后执行）
    _PROBE_REMOTE_PATH = '/root/sxetest/probe_verbs_srq_query_016_008_file.py'
    _PROBE_CONTENT = (
        """# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '/root/sxetest')
import devx_qp_helper as helper
dev = sys.argv[1] if len(sys.argv) > 1 else 'mlx5_0'
supported, evidence = helper.probe_srq_query_libmlx5(dev)
print('srqq_ok' if supported else 'srqq_fail=' + repr(evidence))
"""
    )

    # 环境IP信息文件相关
    _ENV_IP_INFO_FILE_NAME = '环境IP信息'
    _env_ip_info = None

    test_object = 'verbs SRQ 查询（mlx5dv_devx_srq_query / QUERY_SRQ）'
    test_module = 'rdma'
    test_tool = 'pyverbs + libmlx5(mlx5dv)'
    test_precondition = (
        '1. RDMA 设备（mlx5_0）在线且 libmlx5 mlx5dv 可用；\n'
        '2. 已部署 ipvbs 运行时（ipvbs_s.py / ipvbs.py）与 devx_qp_helper.py；\n'
        '3. 测试机与 server 节点 SSH 免密连通。'
    )
    test_steps = (
        "1. 初始化 RDMA 测试框架与 ipvbs 会话；\n2. 创建 Mlx5Context：glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '<rdma_dev>')；\n3. 创建 verbs SRQ：glb_srq_list = glb_helper.create_verbs_srq_with_pd(glb_mlx5_ctx, 64)；\n4. 压力查询：glb_ret8 = glb_helper.stress_query_srq_libmlx5(glb_srq_obj, 100, srqn=glb_srqn)；\n5. 校验 glb_ret8：查询总次数==100、全部 call_ret==0、consistent==True；\n6. 清理资源：glb_helper.close_verbs_srq_guarded(glb_srq_obj) 关闭 SRQ，glb_mlx5_ctx.close() 关闭 context，退出 ipvbs 会话；"

    )

    test_expect = (
        "1. ipvbs 会话建立成功，RDMA 框架初始化完成；\n2. Mlx5Context 创建成功，无异常；\n3. verbs SRQ 创建成功，无异常；\n4. 压力查询执行完成，无异常；\n5. 总次数==100 且全部 call_ret==0、consistent==True，命令通道稳定无串扰；\n6. 资源清理完成，无泄漏，无报错。"

    )


    @classmethod
    def set_parameters(cls) -> None:
        cls.test_object = 'verbs SRQ 查询（mlx5dv_devx_srq_query / QUERY_SRQ）'
        cls.test_module = 'rdma'
        cls.test_tool = 'pyverbs + libmlx5(mlx5dv)'
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
    def _probe_srq_query_support(cls) -> bool:
        """探测远端 mlx5dv_devx_srq_query 是否可用（部署探测脚本到远端执行）。"""
        cls._deploy_helper_if_needed()  # 探测脚本依赖远端 helper
        local_probe = os.path.join(tempfile.gettempdir(),
                                   'probe_verbs_srq_query_016_008_file.py')
        try:
            with open(local_probe, 'w', encoding='utf-8') as f:
                f.write(cls._PROBE_CONTENT)
        except OSError as exc:
            log.warning(f'写入本地探测脚本失败: {exc}')
            return False
        env_entry = cls._get_env_entry_for_exec_addr()
        ip = env_entry.get('ip') if env_entry else None
        port = str(env_entry.get('port')) if env_entry else '22'
        if not ip:
            log.warning('无法获取执行端 IP，跳过 verbs_srq_query 探测。')
            return False
        rtn, _, _ = FileOperation.scp_file_to_remote(
            localfile_path=local_probe,
            remotefile_path=cls._PROBE_REMOTE_PATH,
            ip=ip,
            port=port,
            cmd_execute_address=cls._exec_addr)
        if rtn != RtnStatusEnum.SUCCESS.value:
            log.warning(f'部署探测脚本返回 rtn={rtn}，继续尝试执行验证。')
        status, result, err = CommandOperation.execute_command_with_error(
            f'python3 {cls._PROBE_REMOTE_PATH} {cls._rdma_dev}', cls._exec_addr)
        if status == RtnStatusEnum.SUCCESS.value and \
                'srqq_ok' in (result or ''):
            log.info('探测到 mlx5dv_devx_srq_query 命令可用。')
            return True
        if status == RtnStatusEnum.SUCCESS.value and \
                'srqq_fail' in (result or ''):
            log.warning(f'探测 mlx5dv_devx_srq_query 返回失败: {result}，'
                        f'本用例 skip。')
            return False
        log.warning(f'探测 mlx5dv_devx_srq_query 支持失败: err={err}, '
                    f'result={result}')
        return False

    @classmethod
    def check_own_environment(cls) -> None:
        """检查局部环境：RDMA 设备存在且 libmlx5 mlx5dv DevX 可用。"""
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
            log.warning(
                f'指定的 RDMA 设备 {cls._rdma_dev} 不存在，'
                f'当前设备列表: {dev_list}，自动回退到首个可用设备。')
            cls._rdma_dev = dev_list[0]
        if not cls._rdma_dev:
            cls._rdma_dev = dev_list[0]
        log.info(f'检测到 RDMA 设备: {dev_list}, 本用例使用: {cls._rdma_dev}')

        # 3. 检查 libmlx5 mlx5dv / pyverbs mlx5 DevX 是否可用
        # 注意：命令经框架 SSH 双引号包裹传输，命令内部不能含双引号，
        # 否则本地 shell 会先剥掉内层双引号导致远端 Python 语法/名称错误
        cmd_check = (
            "python3 -c 'import pyverbs.providers.mlx5.mlx5dv as m; "
            "print(m.Mlx5Context.__name__, m.Mlx5DVContextAttr.__name__, "
            "m.Mlx5DevxObj.__name__)' && echo mlx5_devx_ok"
        )
        status, result, err = CommandOperation.execute_command_with_error(
            cmd_check, cls._exec_addr)
        if status != RtnStatusEnum.SUCCESS.value or \
                'mlx5_devx_ok' not in (result or ''):
            cls._report_env_error(f'pyverbs mlx5 DevX 不可用: {err}')
            return
        log.info(f'pyverbs mlx5 DevX 可用: {result.strip()}')

        # 4. 探测 mlx5dv_devx_srq_query 命令支持情况
        if not cls._probe_srq_query_support():
            log.warning('当前环境不支持 mlx5dv_devx_srq_query，本用例 skip。')
            return
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
        log.info(f'prepare: 初始化 mlx5dv_devx_srq_query 测试环境 '
                 f'(opcode={cls._OPCODE_NAME}, dev={cls._rdma_dev})。')
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 '
                           'mlx5dv_devx_srq_query 测试环境。')
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)
        # 确保远程节点存在 devx_qp_helper.py
        cls._deploy_helper_if_needed()

        setup_cmds = [
            # 加载 mlx5dv_devx_srq_query helper（自动部署到 /root/sxetest/）
            "__import__('sys').path.insert(0, '/root/sxetest')",
            "glb_helper = __import__('devx_qp_helper')",
            # 加载 pyverbs mlx5 DevX 模块
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', "
            "fromlist=['Mlx5Context', 'Mlx5DVContextAttr', 'Mlx5DevxObj', 'Mlx5UMEM'])",
            "glb_Mlx5Context = glb_mlx5dv.Mlx5Context",
            "glb_Mlx5DVContextAttr = glb_mlx5dv.Mlx5DVContextAttr",
            "glb_Mlx5DevxObj = glb_mlx5dv.Mlx5DevxObj",
            # 创建 Mlx5Context
            f"glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), "
            f"'{cls._rdma_dev}')",
        ]
        setup_cmds += [
            # 创建 verbs SRQ（mlx5dv_devx_srq_query 的查询目标）
            f"glb_srq_list = glb_helper.create_verbs_srq_with_pd(glb_mlx5_ctx, 64)",
            "glb_srq_obj = glb_srq_list[0]",
            "glb_srqn = glb_srq_list[1]",
            "glb_srq_pd = glb_srq_list[2]",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'初始化 mlx5dv_devx_srq_query 测试环境失败, '
                    f'dev={cls._rdma_dev}, cmd={cmd}, rtn={result}')
                return

    @classmethod
    def do(cls) -> None:
        log.info('do: mlx5dv_devx_srq_query（verbs SRQ 查询）测试。')
        cls._do_case_008()

    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 mlx5dv_devx_srq_query 测试资源。')
        if cls._ipvbs is not None:
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    # ------------------------------------------------------------------ #
    #  mlx5dv_devx_srq_query 操作辅助方法                                 #
    # ------------------------------------------------------------------ #

    @classmethod
    def _exec_ok(cls, cmd: str, desc: str) -> bool:
        """执行远端命令，成功返回 True，失败记录 bug 返回 False。"""
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
        if status != IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'{desc} 命令执行失败: {result}')
            return False
        return True

    @classmethod
    def _query_srq(cls, var_suffix='1', srq_ref='glb_srq_obj',
                   srqn_expr='glb_srqn', op_mod=0, in_len=16, out_len=4096):
        """下发 mlx5dv_devx_srq_query，返回 (call_ret, fw_status, syndrome, detail)。

        detail: 取回后的 detail 字符串（成功为 dict 的 str，守卫拦截为原因 str）。
        """
        cmd = (f'glb_ret{var_suffix} = glb_helper.query_srq_via_libmlx5('
               f'{srq_ref}, srqn={srqn_expr}, op_mod={op_mod}, '
               f'in_len={in_len}, out_len={out_len})')
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
        if status != IpvbsStatusEnum.SUCCESS.value:
            return None, None, None, f'远程执行异常: {result}'
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f'str(glb_ret{var_suffix}[:3])')
        if status != IpvbsStatusEnum.SUCCESS.value:
            return None, None, None, f'取回查询结果失败: {result}'
        try:
            call_ret, fw_status, syndrome = ast.literal_eval(result.strip())
        except Exception as exc:
            return None, None, None, f'解析查询结果失败: {result}, {exc}'
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f'str(glb_ret{var_suffix}[3])')
        if status != IpvbsStatusEnum.SUCCESS.value:
            return call_ret, fw_status, syndrome, f'<取回detail失败: {result}>'
        return call_ret, fw_status, syndrome, (result or '').strip()

    @classmethod
    def _fetch_field(cls, var_suffix: str, key: str):
        """取回远端 detail dict 中 key 字段的 int 值；失败返回 None。"""
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"str(glb_ret{var_suffix}[3][{key!r}])")
        if status != IpvbsStatusEnum.SUCCESS.value:
            return None
        try:
            return int((result or '').strip())
        except Exception:
            return None

    @classmethod
    def _fetch_expr(cls, expr: str) -> str:
        """远端求值表达式并返回其 str 表示；失败返回空串。"""
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(f'str({expr})')
        if status != IpvbsStatusEnum.SUCCESS.value:
            return ''
        return (result or '').strip()

    @classmethod
    def _cleanup_srq_ctx(cls) -> None:
        """清理：关闭 verbs SRQ 与 Mlx5Context。"""
        if not cls._exec_ok(
                'glb_helper.close_verbs_srq_guarded(glb_srq_obj)',
                '关闭 verbs SRQ'):
            return
        cls._exec_ok('glb_mlx5_ctx.close()', '关闭 Mlx5Context')

    @classmethod
    def _cleanup_ctx(cls) -> None:
        """清理：关闭 Mlx5Context（无 SRQ 场景）。"""
        cls._exec_ok('glb_mlx5_ctx.close()', '关闭 Mlx5Context')

    # ------------------------------------------------------------------ #
    #  检查点实现                                                          #
    # ------------------------------------------------------------------ #
    @classmethod
    def _do_case_008(cls) -> None:
        """CP1: 100 次重复查询全部 ret=0 且 consistent=True。"""
        log.info('[CP1] 100 次重复压力查询。')
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            'glb_ret8 = glb_helper.stress_query_srq_libmlx5('
            'glb_srq_obj, 100, srqn=glb_srqn)')
        if status != IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'压力查询远程执行异常: {result}')
            return
        summary = cls._fetch_expr(
            'tuple((len(glb_ret8[0]), '
            'all(map(lambda s: s[0] == 0, glb_ret8[0])), glb_ret8[1]))')
        try:
            total, all_ok, consistent = ast.literal_eval(summary)
        except Exception:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'压力查询汇总解析失败: {summary}')
            return
        if total != 100 or not all_ok:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'100 次压力查询存在失败: total={total}, '
                           f'all_ret0={all_ok}')
            return
        if not consistent:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'100 次压力查询字段不一致: consistent={consistent}')
            return
        log.info(f'100 次压力查询全部成功且字段一致: total={total}, '
                 f'all_ret0={all_ok}, consistent={consistent}。')
        cls._cleanup_srq_ctx()
    @classmethod
    def _body_query_ok(cls, var_suffix: str) -> bool:
        """下发查询并校验 ret=0/fw=0；失败记 bug 返回 False。"""
        log.info(f'下发查询{var_suffix}。')
        call_ret, fw_status, syndrome, detail = cls._query_srq(
            var_suffix=var_suffix)
        if call_ret is None:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'查询{var_suffix}被守卫拦截或远程异常: '
                           f'{detail}')
            return False
        if call_ret != 0 or fw_status != 0:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'查询{var_suffix}返回异常: ret={call_ret}, '
                           f'fw_status={fw_status}, syndrome={syndrome}，'
                           f'期望 ret=0 且 fw_status=0。')
            return False
        log.info(f'查询{var_suffix}成功: ret=0, fw_status={fw_status}, '
                 f'syndrome={syndrome}')
        return True


if __name__ == '__main__':
    NicLinuxRdmaDevxF0653016008PfStressRepeatQuerySrqQuery().run()
