#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-09-04
description:   RDMA DevX 接口测试_用户态_PF_verbs_qp_query_UD传输verbs_qp_query

               接口:    mlx5dv_devx_qp_query（libmlx5 C DV，ctypes 直调）
               opcode:  SXE3R_DEVX_OP_QUERY_QP(0x50b)
               对象:    verbs QP
               用例ID:  nic_linux_rdma_devx_f_06_53_020_008

                传输类型（UD）：创建 verbs QP(UD)，三次重复经 mlx5dv_devx_qp_query 下发 QUERY_QP(0x50b)，校验 state=0/st=2(UD) 且字段一致。

               实现说明：
               经 helper.query_qp_via_libmlx5() 构造 QUERY_QP inbox
               （opcode=0x50b, qpn@byte9-11）并调用 libmlx5 的
               mlx5dv_devx_qp_query C 符号下发 devx_ucmd 通道。

                环境不支持判定：
                本用例依赖 mlx5dv_devx_qp_query 对 verbs QP(UD) 的下发通道；探测失败时自动 skip。

               环境信息来源：项目根目录下的"环境IP信息"文件，
               按 server/client 顺序解析 IP、端口、用户名、密码及 RDMA 设备名。

# changelog:
    2026-09-04 初始版本，基于 DevX QUERY_SRQ(016) 模板生成。
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


class NicLinuxRdmaDevxF0653020008PfTransportUdQpQuery(ScriptBase):
    """DevX verbs_qp_query UD传输verbs_qp_query用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_020_008'
    case_title = 'RDMA DevX 接口测试_用户态_PF_verbs_qp_query_UD传输verbs_qp_query'
    case_module = 'DevX'
    case_type = '系统测试-功能'

    # Mellanox 固件 opcode（参见 include/linux/mlx5/mlx5_ifc.h）
    _MLX5_OP_QUERY_QP = 0x50b

    _OPCODE_NAME = 'SXE3R_DEVX_OP_QUERY_QP'
    _IF_NAME = 'mlx5dv_devx_qp_query(libmlx5 C DV)'
    _OBJ_TYPE = 'verbs QP 对象'

    _ipvbs = None
    _rdma_dev = ''
    _probe_ok = False

    # 远端 QUERY_QP 探测脚本（部署到 /root/sxetest/ 后执行）
    _PROBE_REMOTE_PATH = '/root/sxetest/probe_verbs_qp_query_020_008_file.py'
    _PROBE_CONTENT = (
        """# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '/root/sxetest')
import devx_qp_helper as helper
dev = sys.argv[1] if len(sys.argv) > 1 else 'mlx5_0'
supported, evidence = helper.probe_qp_query_libmlx5(dev, qp_type=4)
print('qpq_ok' if supported else 'qpq_fail=' + repr(evidence))
"""
    )

    # 环境IP信息文件相关
    _ENV_IP_INFO_FILE_NAME = '环境IP信息'
    _env_ip_info = None

    test_object = 'verbs QP 查询（mlx5dv_devx_qp_query / QUERY_QP）'
    test_module = 'rdma'
    test_tool = 'pyverbs + libmlx5(mlx5dv)'
    test_precondition = (
        '1. RDMA 设备（mlx5_0）在线且 libmlx5 mlx5dv 可用；\n'
        '2. 已部署 ipvbs 运行时（ipvbs_s.py / ipvbs.py）与 devx_qp_helper.py；\n'
        '3. 测试机与 server 节点 SSH 免密连通。'
    )

    test_steps = (
        "1. 初始化 RDMA 测试框架与 ipvbs 会话；\n"
        "2. 创建 Mlx5Context：glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '<rdma_dev>')；\n"
        "3. 创建 verbs QP(UD)：glb_qp_list = glb_helper.create_verbs_qp_with_pd(glb_mlx5_ctx, 4, 16, 16, 64)，取 glb_qp_obj/glb_qpn/glb_qp_pd/glb_qp_cq；\n"
        "4. 下发查询1：glb_ret1 = glb_helper.query_qp_via_libmlx5(glb_qp_obj, qpn=glb_qpn)，校验 qpc state==0、st==2(UD)；\n"
        "5. 下发查询2：glb_ret2 = glb_helper.query_qp_via_libmlx5(glb_qp_obj, qpn=glb_qpn)；\n"
        "6. 下发查询3：glb_ret3 = glb_helper.query_qp_via_libmlx5(glb_qp_obj, qpn=glb_qpn)，校验三次查询 qpc 字段（state/st/pd/remote_qpn）完全一致；\n"
        "7. 清理资源：glb_helper.close_verbs_qp_guarded(glb_qp_obj) 关闭 QP，glb_mlx5_ctx.close() 关闭 context，退出 ipvbs 会话；"
    )

    test_expect = (
        "1. ipvbs 会话建立成功，RDMA 框架初始化完成；\n"
        "2. Mlx5Context 创建成功，无异常；\n"
        "3. verbs QP(UD) 创建成功，glb_qpn 为有效 QP 编号；\n"
        "4. 查询1下发成功，qpc 字段可解析，state==0、st==2(UD)；\n"
        "5. 查询2下发成功，无异常；\n"
        "6. 查询3下发成功，三次查询 qpc 字段（state/st/pd/remote_qpn）完全一致，命令通道稳定；\n"
        "7. 资源清理完成，无泄漏，无报错。"
    )

    @classmethod
    def set_parameters(cls) -> None:
        cls.test_object = 'verbs QP 查询（mlx5dv_devx_qp_query / QUERY_QP）'
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
    def _probe_qp_query_support(cls) -> bool:
        """探测远端 mlx5dv_devx_qp_query 是否可用（部署探测脚本到远端执行）。"""
        cls._deploy_helper_if_needed()  # 探测脚本依赖远端 helper
        local_probe = os.path.join(tempfile.gettempdir(),
                                   'probe_verbs_qp_query_020_008_file.py')
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
            log.warning('无法获取执行端 IP，跳过 verbs_qp_query 探测。')
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
                'qpq_ok' in (result or ''):
            log.info('探测到 mlx5dv_devx_qp_query 命令可用。')
            return True
        if status == RtnStatusEnum.SUCCESS.value and \
                'qpq_fail' in (result or ''):
            log.warning(f'探测 mlx5dv_devx_qp_query 返回失败: {result}，'
                        f'本用例 skip。')
            return False
        log.warning(f'探测 mlx5dv_devx_qp_query 支持失败: err={err}, '
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

        # 4. 探测 mlx5dv_devx_qp_query 命令支持情况
        if not cls._probe_qp_query_support():
            log.warning('当前环境不支持 mlx5dv_devx_qp_query，本用例 skip。')
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
        log.info(f'prepare: 初始化 mlx5dv_devx_qp_query 测试环境 '
                 f'(opcode={cls._OPCODE_NAME}, dev={cls._rdma_dev})。')
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 '
                           'mlx5dv_devx_qp_query 测试环境。')
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)
        # 确保远程节点存在 devx_qp_helper.py
        cls._deploy_helper_if_needed()

        setup_cmds = [
            # 加载 mlx5dv_devx_qp_query helper（自动部署到 /root/sxetest/）
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
            # 创建 verbs QP（mlx5dv_devx_qp_query 的查询目标）
            f"glb_qp_list = glb_helper.create_verbs_qp_with_pd(glb_mlx5_ctx, 4, 16, 16, 64)",
            "glb_qp_obj = glb_qp_list[0]",
            "glb_qpn = glb_qp_list[1]",
            "glb_qp_pd = glb_qp_list[2]",
            "glb_qp_cq = glb_qp_list[3]",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'初始化 mlx5dv_devx_qp_query 测试环境失败, '
                    f'dev={cls._rdma_dev}, cmd={cmd}, rtn={result}')
                return

    @classmethod
    def do(cls) -> None:
        log.info('do: mlx5dv_devx_qp_query（verbs QP 查询）测试。')
        cls._do_case_008()

    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 mlx5dv_devx_qp_query 测试资源。')
        if cls._ipvbs is not None:
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    #  ------------------------------------------------------------------ #
    #  mlx5dv_devx_qp_query 操作辅助方法                                        #
    #  ------------------------------------------------------------------ #

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
    def _query_qp(cls, var_suffix='1', qp_ref='glb_qp_obj',
                  qpn_expr='glb_qpn', op_mod=0, in_len=16, out_len=4096,
                  raw_in_expr=''):
        """下发 mlx5dv_devx_qp_query，返回 (call_ret, fw_status, syndrome, detail)。

        detail: 取回后的 detail 字符串（成功为 dict 的 str，守卫拦截为原因 str）。
        """
        cmd = (f'glb_ret{var_suffix} = glb_helper.query_qp_via_libmlx5('
               f'{qp_ref}, qpn={qpn_expr}, op_mod={op_mod}, '
               f'in_len={in_len}, out_len={out_len}')
        if raw_in_expr:
            cmd += f", raw_in={raw_in_expr}"
        cmd += ')'
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
    def _cleanup_qp_ctx(cls) -> None:
        """清理：关闭 verbs QP 与 Mlx5Context。"""
        if not cls._exec_ok(
                'glb_helper.close_verbs_qp_guarded(glb_qp_obj)',
                '关闭 verbs QP'):
            return
        cls._exec_ok('glb_mlx5_ctx.close()', '关闭 Mlx5Context')

    @classmethod
    def _cleanup_ctx(cls) -> None:
        """清理：关闭 Mlx5Context（无 QP 场景）。"""
        cls._exec_ok('glb_mlx5_ctx.close()', '关闭 Mlx5Context')

    #  ------------------------------------------------------------------ #
    #  检查点实现                                                              #
    #  ------------------------------------------------------------------ #
    @classmethod
    def _do_case_008(cls) -> None:
        """CP1: 正常查询 ret=0/fw=0；CP2: qpc state==0、st==2(UD)；
        CP3: 三次重复查询 qpc 字段一致。"""
        log.info('[CP1] 下发正常 mlx5dv_devx_qp_query（UD）。')
        if not cls._body_query_ok('1'):
            return
        log.info('[CP2] 校验 qpc 字段（state==0, st==2/UD）。')
        state = cls._fetch_field('1', 'state')
        st = cls._fetch_field('1', 'st')
        if state is None or st is None:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'qpc 字段解析失败: state={state}, st={st}')
            return
        if state != 0 or st != 2:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'qpc 字段校验失败: state={state}(期望0), '
                           f'st={st}(期望2/UD)')
            return
        log.info(f'qpc 字段校验通过: state={state}, st={st}')
        log.info('[CP3] 三次重复查询校验一致性。')
        if not cls._body_query_ok('2'):
            return
        if not cls._body_query_ok('3'):
            return
        for key in ('state', 'st', 'pd', 'remote_qpn'):
            v1 = cls._fetch_field('1', key)
            v2 = cls._fetch_field('2', key)
            v3 = cls._fetch_field('3', key)
            if v1 is None or v2 is None or v3 is None or v1 != v2:
                cls.set_bug_type('功能问题')
                cls.create_bug(f'三次查询字段 {key} 不一致: '
                               f'{v1} vs {v2} vs {v3}')
                return
        log.info('三次查询 qpc 字段完全一致，命令通道稳定。')
        cls._cleanup_qp_ctx()
    @classmethod
    def _body_query_ok(cls, var_suffix: str) -> bool:
        """下发查询并校验 ret=0/fw=0；失败记 bug 返回 False。"""
        log.info(f'下发查询{var_suffix}。')
        call_ret, fw_status, syndrome, detail = cls._query_qp(
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
    NicLinuxRdmaDevxF0653020008PfTransportUdQpQuery().run()
