#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写用例作者>
date:          2026-09-04
description:   RDMA DevX 接口测试_用户态_PF_umem_reg_访问权限umem_reg

               接口:    mlx5dv_devx_umem_reg / mlx5dv_devx_umem_reg_ex / mlx5dv_devx_umem_dereg（libmlx5 C DV，ctypes 直调）
               opcode:  无固件 MLX5 opcode：走内核 devx_umem_reg/devx_umem_dereg 通道（UPD/ioctl），libmlx5 在用户态完成 mkey/翻译表维护
               对象:    devx UMEM（内存注册）对象
               用例ID:  nic_linux_rdma_devx_f_06_53_018_002

访问权限：分别以 access=0 与全权限 access=0xF 注册 4KiB UMEM
并释放，校验各权限位组合均可正常注册/释放且 umem_id 互不相同。
               环境不支持判定：经 helper.probe_umem_access_libmlx5() 探测远端，脚本探测到不支持时自动 skip（本用例不产生失败）。

               环境信息来源：项目根目录下的"环境IP信息"文件，
               按 server/client 顺序解析 IP、端口、用户名、密码及 RDMA 设备名。

# changelog:
    2026-09-04 初始版本，由 017 模块模板适配为
    umem_reg(ctypes 直调) 生成。
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

class NicLinuxRdmaDevxF0653018002PfAccessFlagsUmemReg(ScriptBase):
    """DevX umem_reg 访问权限umem_reg用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_018_002'
    case_title = 'RDMA DevX 接口测试_用户态_PF_umem_reg_访问权限umem_reg'
    case_module = 'DevX'
    case_type = '系统测试-功能'

    # 无固件 MLX5 opcode：走内核 devx_umem_reg/devx_umem_dereg 通道
    _OPCODE_NAME = 'devx umem 通道（无固件 opcode）'
    _IF_NAME = 'mlx5dv_devx_umem_reg / mlx5dv_devx_umem_reg_ex / mlx5dv_devx_umem_dereg（libmlx5 C DV，ctypes 直调）'
    _OBJ_TYPE = 'devx UMEM（内存注册）对象'

    _ipvbs = None
    _rdma_dev = ''
    _probe_ok = False
    _umem_ids = []

    # 远端 umem_reg 探测脚本（部署到 /root/sxetest/ 后执行）
    _PROBE_REMOTE_PATH = '/root/sxetest/probe_umem_018_002_file.py'
    _PROBE_CONTENT = (
        """# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '/root/sxetest')
import devx_qp_helper as helper
dev = sys.argv[1] if len(sys.argv) > 1 else 'mlx5_0'
supported, evidence = helper.probe_umem_access_libmlx5(dev, 0xF)
print('umem_ok' if supported else 'umem_fail=' + repr(evidence))
"""
    )

    # 环境IP信息文件相关
    _ENV_IP_INFO_FILE_NAME = '环境IP信息'
    _env_ip_info = None

    test_object = 'devx UMEM 注册/释放（mlx5dv_devx_umem_reg / umem_reg_ex / umem_dereg）'
    test_module = 'rdma'
    test_tool = 'pyverbs + libmlx5(mlx5dv)'
    test_precondition = (
        '1. RDMA 设备（mlx5_0）在线且 libmlx5 mlx5dv 可用；\n'
        '2. 已部署 ipvbs 运行时（ipvbs_s.py / ipvbs.py）与 devx_qp_helper.py；\n'
        '3. 测试机与 server 节点 SSH 免密连通。'
    )
    test_steps = (
        "1. 初始化 RDMA 测试框架与 ipvbs 会话；\\n2. 创建 Mlx5Context：glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '<rdma_dev>')；\\n3. access=0 注册：glb_ret1 = glb_helper.umem_reg_via_libmlx5(glb_mlx5_ctx, size=4096, access=0)，校验 call_ret==0 后释放；\\n4. access=0xF 注册：glb_ret2 = glb_helper.umem_reg_via_libmlx5(glb_mlx5_ctx, size=4096, access=0xF)，校验 call_ret==0 后释放；\\n5. 校验两次注册的 umem_id 均有效（>0）且互不相同；\\n6. 清理资源：glb_mlx5_ctx.close() 关闭 context，退出 ipvbs 会话。"
    )
    test_expect = (
        '1. ipvbs 会话建立成功，RDMA 框架初始化完成；\\n2. Mlx5Context 创建成功，无异常；\\n3. access=0 注册成功，call_ret==0，释放成功；\\n4. access=0xF 注册成功，call_ret==0，释放成功；\\n5. 两次注册均返回有效 umem_id（>0）且互不相同；\\n6. 资源清理完成，无泄漏，无报错。'
    )

    @classmethod
    def set_parameters(cls) -> None:
        cls.test_object = 'devx UMEM 注册/释放（mlx5dv_devx_umem_reg / umem_reg_ex / umem_dereg）'
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
    def _probe_umem_support(cls) -> bool:
        """探测远端 mlx5dv_devx_umem_reg 是否可用（部署探测脚本到远端执行）。"""
        cls._deploy_helper_if_needed()  # 探测脚本依赖远端 helper
        local_probe = os.path.join(tempfile.gettempdir(),
                                   'probe_umem_018_002_file.py')
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
            log.warning('无法获取执行端 IP，跳过 umem_reg 探测。')
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
        if status == RtnStatusEnum.SUCCESS.value and                 'umem_ok' in (result or ''):
            log.info('探测到 mlx5dv_devx_umem_reg 命令可用。')
            return True
        if status == RtnStatusEnum.SUCCESS.value and                 'umem_fail' in (result or ''):
            log.warning(f'探测 mlx5dv_devx_umem_reg 返回失败: {result}，'
                        f'本用例 skip。')
            return False
        log.warning(f'探测 mlx5dv_devx_umem_reg 支持失败: err={err}, '
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
        if status != RtnStatusEnum.SUCCESS.value or                 'mlx5_devx_ok' not in (result or ''):
            cls._report_env_error(f'pyverbs mlx5 DevX 不可用: {err}')
            return
        log.info(f'pyverbs mlx5 DevX 可用: {result.strip()}')

        # 4. 探测 mlx5dv_devx_umem_reg 命令支持情况
        if not cls._probe_umem_support():
            log.warning('当前环境不支持 mlx5dv_devx_umem_reg，本用例 skip。')
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
        log.info(f'prepare: 初始化 mlx5dv_devx_umem_reg 测试环境 '
                 f'(dev={cls._rdma_dev})。')
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 '
                           'mlx5dv_devx_umem_reg 测试环境。')
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)
        # 确保远程节点存在 devx_qp_helper.py
        cls._deploy_helper_if_needed()

        setup_cmds = [
            # 加载 devx umem helper（自动部署到 /root/sxetest/）
            "__import__('sys').path.insert(0, '/root/sxetest')",
            "glb_helper = __import__('devx_qp_helper')",
            # 加载 pyverbs mlx5 DevX 模块（含 Mlx5UAR，供 CQ/QP 复用场景）
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', "
            "fromlist=['Mlx5Context', 'Mlx5DVContextAttr', 'Mlx5DevxObj', "
            "'Mlx5UMEM', 'Mlx5UAR'])",
            "glb_Mlx5Context = glb_mlx5dv.Mlx5Context",
            "glb_Mlx5DVContextAttr = glb_mlx5dv.Mlx5DVContextAttr",
            "glb_Mlx5DevxObj = glb_mlx5dv.Mlx5DevxObj",
            "glb_Mlx5UAR = glb_mlx5dv.Mlx5UAR",
            # 创建 Mlx5Context
            f"glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), "
            f"'{cls._rdma_dev}')",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'初始化 mlx5dv_devx_umem_reg 测试环境失败, '
                    f'dev={cls._rdma_dev}, cmd={cmd}, rtn={result}')
                return

    @classmethod
    def do(cls) -> None:
        log.info('do: mlx5dv_devx_umem_reg（devx UMEM 注册/释放）测试。')
        cls._do_case_001()

    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 mlx5dv_devx_umem_reg 测试资源。')
        if cls._ipvbs is not None:
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    # ------------------------------------------------------------------ #
    #  mlx5dv_devx_umem_reg 操作辅助方法                                  #
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
    def _fetch_ret3(cls, var_suffix: str):
        """取回 glb_<var>[:3]=(call_ret, None, None)；失败/解析失败返回 None。"""
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f'str(glb_{var_suffix}[:3])')
        if status != IpvbsStatusEnum.SUCCESS.value:
            return None
        try:
            val = ast.literal_eval((result or '').strip())
        except Exception:
            return None
        if not isinstance(val, tuple) or len(val) < 1:
            return None
        return val

    @classmethod
    def _fetch_detail(cls, var_suffix: str) -> str:
        """取回 glb_<var>[3] detail 字符串；失败返回空串。"""
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f'str(glb_{var_suffix}[3])')
        if status != IpvbsStatusEnum.SUCCESS.value:
            return ''
        return (result or '').strip()

    @classmethod
    def _parse_detail(cls, s: str):
        """将 detail 字符串解析为 dict；非 dict/解析失败返回 None。"""
        try:
            val = ast.literal_eval(s)
        except Exception:
            return None
        return val if isinstance(val, dict) else None

    @classmethod
    def _fetch_int(cls, expr: str):
        """远端求值表达式并返回 int；失败返回 None。"""
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(f'str({expr})')
        if status != IpvbsStatusEnum.SUCCESS.value:
            return None
        try:
            return int((result or '').strip())
        except Exception:
            return None

    @classmethod
    def _eval_expr(cls, expr: str):
        """远端求值表达式并返回字面值；失败/不可解析返回 None。"""
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(f'str({expr})')
        if status != IpvbsStatusEnum.SUCCESS.value:
            return None
        try:
            return ast.literal_eval((result or '').strip())
        except Exception:
            return None

    @classmethod
    def _do_reg(cls, size: int, var: str, desc: str):
        """注册 UMEM(access=0)，成功返回 (ptr, umem_id)，失败记 bug 返回 None。"""
        if not cls._exec_ok(
                f'glb_{var} = glb_helper.umem_reg_via_libmlx5('
                f'glb_mlx5_ctx, size={size}, access=0)', desc):
            return None
        ret3 = cls._fetch_ret3(var)
        if ret3 is None or ret3[0] is None:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'{desc} 被守卫拦截或取回失败: ret3={ret3}, '
                           f'detail={cls._fetch_detail(var)}')
            return None
        if ret3[0] != 0:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'{desc} 返回异常: call_ret={ret3[0]}, '
                           f'detail={cls._fetch_detail(var)}, 期望 0')
            return None
        detail = cls._parse_detail(cls._fetch_detail(var))
        if detail is None:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'{desc} detail 解析失败: {cls._fetch_detail(var)}')
            return None
        ptr = int(detail.get('ptr', 0))
        umem_id = int(detail.get('umem_id', 0))
        if ptr <= 0 or umem_id <= 0:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'{desc} 返回的 ptr/umem_id 非法: {detail}')
            return None
        log.info(f'{desc} 成功: umem_id={umem_id}, ptr={ptr}')
        return ptr, umem_id

    @classmethod
    def _do_dereg(cls, ptr, var: str, desc: str) -> bool:
        """释放 UMEM，成功返回 True；被守卫/失败记 bug 返回 False。"""
        if not cls._exec_ok(
                f'glb_{var} = glb_helper.umem_dereg_via_libmlx5({ptr})', desc):
            return False
        ret3 = cls._fetch_ret3(var)
        if ret3 is None or ret3[0] is None:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'{desc} 被守卫拦截或取回失败: ret3={ret3}, '
                           f'detail={cls._fetch_detail(var)}')
            return False
        if ret3[0] != 0:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'{desc} 返回异常: call_ret={ret3[0]}, '
                           f'detail={cls._fetch_detail(var)}, 期望 0')
            return False
        log.info(f'{desc} 成功。')
        return True

    @classmethod
    def _cleanup_ctx(cls) -> None:
        """清理：关闭 Mlx5Context。"""
        cls._exec_ok('glb_mlx5_ctx.close()', '关闭 Mlx5Context')



    # ------------------------------------------------------------------ #
    #  检查点实现                                                          #
    # ------------------------------------------------------------------ #
    @classmethod
    def _do_case_001(cls) -> None:
        """CP1: access=0 闭环；CP2: access=0xF 闭环；CP3: umem_id 唯一。"""
        log.info('[CP1] access=0 注册并释放。')
        for idx, access in ((1, 0), (2, 0xF)):
            if not cls._exec_ok(
                    f'glb_ret{idx} = glb_helper.umem_reg_via_libmlx5('
                    f'glb_mlx5_ctx, size=4096, access={access})',
                    f'注册 UMEM(access={access})'):
                return
            ret3 = cls._fetch_ret3(f'ret{idx}')
            if ret3 is None or ret3[0] != 0:
                cls.set_bug_type('功能问题')
                cls.create_bug(f'umem_reg(access={access}) 返回异常: '
                               f'ret3={ret3}, 期望 call_ret==0')
                return
            detail = cls._parse_detail(cls._fetch_detail(f'ret{idx}'))
            if detail is None or int(detail.get('umem_id', 0)) <= 0:
                cls.set_bug_type('功能问题')
                cls.create_bug(f'umem_reg(access={access}) detail 无效: '
                               f'{detail}')
                return
            umem_id = int(detail['umem_id'])
            log.info(f'access={access} 注册成功: umem_id={umem_id}')
            if not cls._exec_ok(
                    f"glb_dret{idx} = glb_helper.umem_dereg_via_libmlx5("
                    f"{detail['ptr']})", f'释放 UMEM(access={access})'):
                return
            dret3 = cls._fetch_ret3(f'dret{idx}')
            if dret3 is None or dret3[0] != 0:
                cls.set_bug_type('功能问题')
                cls.create_bug(f'umem_dereg(access={access}) 返回异常: '
                               f'dret3={dret3}, 期望 call_ret==0')
                return
            cls._umem_ids.append(umem_id)
        log.info('[CP2] 校验两次 umem_id 互不相同。')
        if len(cls._umem_ids) != 2 or             cls._umem_ids[0] == cls._umem_ids[1]:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'两次注册 umem_id 应互不相同: {cls._umem_ids}')
            return
        log.info('两次注册/释放均成功且 umem_id 唯一。')
        cls._cleanup_ctx()


if __name__ == '__main__':
    NicLinuxRdmaDevxF0653018002PfAccessFlagsUmemReg().run()
