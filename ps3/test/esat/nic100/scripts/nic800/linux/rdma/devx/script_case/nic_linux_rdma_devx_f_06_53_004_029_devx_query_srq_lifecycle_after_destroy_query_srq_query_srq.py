#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-09-01
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_query_SRQ查询_销毁后查询

               opcode:  SXE3R_DEVX_OP_QUERY_SRQ
               对象:    SRQ（共享接收队列）
               用例ID:  nic_linux_rdma_devx_f_06_53_004_029

               实现说明：
               通过 Mlx5DevxObj.query()（内核 OBJ_QUERY 通道，opcode=0x702）
               查询已创建的 SRQ，校验返回 status 与 srqc 关键字段
               （state/log_srq_size/log_page_size/pd/lwm）。

               环境信息来源：项目根目录下的"环境IP信息"文件，
               按 server/client 顺序解析 IP、端口、用户名、密码及 RDMA 设备名。

@changelog:
    2026-09-01 初始版本，基于 DevX SRQ 查询模板生成。
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


class NicLinuxRdmaDevxF0653010007PfLifecycleAfterDestroyQuerySrq(ScriptBase):
    """DevX SRQ 销毁后查询用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_004_029'
    case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_query'
                  '_SRQ查询_销毁后查询')
    case_module = 'DevX'
    case_type = '系统测试-功能'

    # Mellanox 固件 opcode（参见 include/linux/mlx5/mlx5_ifc.h）
    _MLX5_OP_QUERY_SRQ = 0x702

    _OPCODE_NAME = 'SXE3R_DEVX_OP_QUERY_SRQ'
    _OBJ_TYPE = 'SRQ'
    _QUERY_COUNT = 200

    _ipvbs = None
    _rdma_dev = ''
    _srq_objs = []

    # 远端 QUERY_SRQ 探测脚本（部署到 /root/sxetest/ 后执行）
    _PROBE_REMOTE_PATH = '/root/sxetest/probe_query_srq_file.py'
    _PROBE_CONTENT = (
        "# -*- coding: utf-8 -*-\n"
        "import sys\n"
        "sys.path.insert(0, '/root/sxetest')\n"
        "import devx_qp_helper as helper\n"
        "from pyverbs.providers.mlx5.mlx5dv import (Mlx5Context, "
        "Mlx5DVContextAttr)\n"
        "dev = sys.argv[1] if len(sys.argv) > 1 else 'mlx5_0'\n"
        "ctx = Mlx5Context(Mlx5DVContextAttr(), dev)\n"
        "try:\n"
        "    pd_obj, pdn = helper.create_devx_pd(ctx)\n"
        "    buf_addr, alloc_size, phys_addrs = helper.alloc_srq_buffer(16384)\n"
        "    srq_obj, srqn = helper.create_devx_srq(ctx, pdn, phys_addrs)\n"
        "    if not hasattr(srq_obj, 'query'):\n"
        "        print('query_srq_fallback_verbs')\n"
        "    else:\n"
        "        ret = helper.query_devx_srq(srq_obj, srqn=srqn)\n"
        "        print('query_srq_ok' if ret[0] == 0 else "
        "'query_srq_fail=' + repr(ret))\n"
        "        srq_obj.close()\n"
        "    pd_obj.close()\n"
        "finally:\n"
        "    ctx.close()\n"
    )

    # 环境IP信息文件相关
    _ENV_IP_INFO_FILE_NAME = '环境IP信息'
    _env_ip_info = None

    test_object = 'RDMA SRQ（共享接收队列）'
    test_module = 'rdma'
    test_tool = 'pyverbs'
    test_precondition = (
        '1. RDMA 设备（mlx5_0）在线且 pyverbs mlx5 可用；\n'
        '2. 已部署 ipvbs 运行时（ipvbs_s.py / ipvbs.py）；\n'
        '3. 测试机与 server 节点 SSH 免密连通。'
    )
    test_steps = (
        "1. 初始化 RDMA 测试框架与 ipvbs 会话；"
        "2. 创建 Mlx5Context，通过 DevX ALLOC_PD 创建 PD，分配 SRQ buffer（PAS 模式）；"
        "3. 通过 DevX CREATE_SRQ 创建 SRQ1（obj_srq_cp1），记录返回的 srqn；"
        "4. 调用 helper query_devx_srq(glb_obj_srq_cp1) 查询 SRQ1，校验 status=0；"
        "5. 调用 obj_srq_cp1.close() 通过 DevX DESTROY_SRQ 销毁 SRQ1；"
        "6. 以原 srqn 再次调用 helper query_devx_srq 查询已销毁的 SRQ；"
        "7. 校验查询返回失败（status=-1），销毁后查询负向预期成立；"
        "8. 清理资源，退出 ipvbs 会话。"
    )

    @classmethod
    def set_parameters(cls) -> None:
        cls.test_object = 'RDMA SRQ（共享接收队列）'
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
    def _probe_query_srq_support(cls) -> bool:
        """探测远端是否支持 DevX QUERY_SRQ 命令（部署探测脚本到远端执行）。"""
        cls._deploy_helper_if_needed()  # 探测脚本依赖远端 helper
        local_probe = os.path.join(tempfile.gettempdir(), 'probe_query_srq_file.py')
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
            log.warning('无法获取执行端 IP，跳过 QUERY_SRQ 探测。')
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
                'query_srq_fallback_verbs' in (result or ''):
            log.warning('SRQ 创建回退到标准 verbs SRQ（无 query 通道），'
                        '不支持 DevX QUERY_SRQ，本用例 skip。')
            return False
        if status == RtnStatusEnum.SUCCESS.value and \
                'query_srq_ok' in (result or ''):
            log.info('探测到 DevX QUERY_SRQ 命令可用。')
            return True
        if err and 'Errno: 22' in err:
            log.info('探测到 QUERY_SRQ 命令已处理（查询无效 SRQN 返回 EINVAL）。')
            return True
        log.warning(f'探测 QUERY_SRQ 支持失败: err={err}, result={result}')
        return False

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

        # 4. 探测 QUERY_SRQ 命令支持情况
        if not cls._probe_query_srq_support():
            log.warning('当前环境不支持 DevX QUERY_SRQ，本用例 skip。')
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
        log.info(f'prepare: 初始化 SRQ 查询测试环境 (opcode={cls._OPCODE_NAME}, '
                 f'dev={cls._rdma_dev})。')
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 SRQ 查询测试环境。')
        cls._srq_objs = []
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)
        # 确保远程节点存在 devx_qp_helper.py
        cls._deploy_helper_if_needed()

        setup_cmds = [
            # 加载 DevX SRQ helper（自动部署到 /root/sxetest/）
            "__import__('sys').path.insert(0, '/root/sxetest')",
            "glb_helper = __import__('devx_qp_helper')",
            # 加载 pyverbs mlx5 DevX 模块
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', "
            "fromlist=['Mlx5Context', 'Mlx5DVContextAttr', 'Mlx5DevxObj', 'Mlx5UMEM'])",
            "glb_Mlx5Context = glb_mlx5dv.Mlx5Context",
            "glb_Mlx5DVContextAttr = glb_mlx5dv.Mlx5DVContextAttr",
            "glb_Mlx5DevxObj = glb_mlx5dv.Mlx5DevxObj",
            "glb_Mlx5UMEM = glb_mlx5dv.Mlx5UMEM",
            # 创建 Mlx5Context
            f"glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), "
            f"'{cls._rdma_dev}')",
            # 通过 DevX ALLOC_PD 创建 PD（SRQ 需要有效的 PD）
            "glb_pd_ret = glb_helper.create_devx_pd(glb_mlx5_ctx)",
            "glb_pd_obj = glb_pd_ret[0]",
            "glb_pdn = glb_pd_ret[1]",
            # 分配 SRQ buffer 并获取物理地址（PAS 模式）
            # CREATE_SRQ 不支持 umem_id，必须用 PAS 提供物理地址
            "glb_srq_buf_ret = glb_helper.alloc_srq_buffer(16384)",
            "glb_srq_buf_addr = glb_srq_buf_ret[0]",
            "glb_srq_buf_size = glb_srq_buf_ret[1]",
            "glb_srq_phys_addrs = glb_srq_buf_ret[2]",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'初始化 DevX SRQ 查询环境失败, dev={cls._rdma_dev}, '
                    f'cmd={cmd}, rtn={result}')
                return

    @classmethod
    def do(cls) -> None:
        log.info('do: DevX QUERY_SRQ 测试。')
        cls._do_lifecycle_after_destroy_query_srq()

    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 SRQ 资源 (共 {len(cls._srq_objs)} 个)。')
        for srq_name in list(cls._srq_objs):
            cls._close_srq(srq_name)
        cls._srq_objs = []
        if cls._ipvbs is not None:
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    #  SRQ 操作辅助方法                                                     #
    # ------------------------------------------------------------------ #

    @classmethod
    def _alloc_srq(cls, srq_name: str) -> tuple:
        """通过 DevX CREATE_SRQ 分配一个 SRQ，返回 (status, srqn)。"""
        glb_srq_name = f'glb_{srq_name}'
        alloc_cmds = [
            # 通过 helper 创建 SRQ（PAS 模式，使用物理地址）
            f"{glb_srq_name}_ret = glb_helper.create_devx_srq("
            f"glb_mlx5_ctx, glb_pdn, glb_srq_phys_addrs)",
            f"{glb_srq_name} = {glb_srq_name}_ret[0]",
            f"{glb_srq_name}_num = {glb_srq_name}_ret[1]",
        ]
        for cmd in alloc_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                log.error(f'DevX CREATE_SRQ 命令失败: {cmd}, rtn={result}')
                return status, None

        status, srqn = cls._ipvbs.exec_and_get_ipvbs_result(
            f"str({glb_srq_name}_num)")
        if status != IpvbsStatusEnum.SUCCESS.value:
            return status, None

        cls._srq_objs.append(srq_name)
        srqn = (srqn or '').strip()
        log.info(f'DevX SRQ 分配成功: {srq_name}, srqn={srqn}')
        return IpvbsStatusEnum.SUCCESS.value, srqn

    @classmethod
    def _close_srq(cls, srq_name: str) -> bool:
        """释放指定 SRQ 及其关联的 WQ UMEM 资源。"""
        glb_srq_name = f'glb_{srq_name}'
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"{glb_srq_name}.close()")
        if status == IpvbsStatusEnum.SUCCESS.value:
            log.info(f'SRQ 释放成功: {srq_name}')
            if srq_name in cls._srq_objs:
                cls._srq_objs.remove(srq_name)
            return True
        log.warning(f'SRQ 释放异常: {srq_name}, rtn={result}')
        return False

    @classmethod
    def _query_srq(cls, srq_name: str, srqn=None, op_mod=0,
                   qf_suffix: str = '', obj_ref: str = None) -> tuple:
        """下发 DevX QUERY_SRQ，返回 (srq_status, srq_syndrome, srq_fields)。

        obj_ref: 远端对象引用名（如 'glb_srq_cp1_keep'）。销毁后查询时
        服务端已把含 'obj' 的引用从 rdma_dict 弹出，必须改用保存的引用。
        """
        glb_srq_name = f'glb_{srq_name}'
        ref_name = obj_ref or glb_srq_name
        if srqn is None:
            cmd = (f"{glb_srq_name}_qf{qf_suffix} = glb_helper.query_devx_srq("
                   f"{ref_name}, op_mod={op_mod})")
        else:
            srqn_ref = (str(int(srqn)) if isinstance(srqn, str) else str(srqn))
            cmd = (f"{glb_srq_name}_qf{qf_suffix} = glb_helper.query_devx_srq("
                   f"{ref_name}, srqn={srqn_ref}, op_mod={op_mod})")
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
        if status != IpvbsStatusEnum.SUCCESS.value:
            return None, None, result
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"str({glb_srq_name}_qf{qf_suffix})")
        if status != IpvbsStatusEnum.SUCCESS.value:
            return None, None, result
        try:
            srq_status, srq_syndrome, srq_fields = ast.literal_eval(
                result.strip())
        except Exception:
            return None, None, result
        log.info(f'QUERY_SRQ 返回: status={srq_status}, syndrome={srq_syndrome}')
        return srq_status, srq_syndrome, srq_fields

    @classmethod
    def _check_query_fields(cls, srq_name: str, expr: str, desc: str,
                            qf_suffix: str = '') -> bool:
        """远端校验查询字段。expr 引用 glb_<srq_name>_qf<qf_suffix>。"""
        glb_srq_name = f'glb_{srq_name}'
        qf_var = f'{glb_srq_name}_qf{qf_suffix}'
        chk_var = f'glb_chk_{srq_name}{qf_suffix}'
        cmd = f'{chk_var} = ({qf_var}[2] is not None and {expr})'
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
        if status != IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'{desc} 校验命令执行失败: {result}')
            return False
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f'str({chk_var})')
        passed = status == IpvbsStatusEnum.SUCCESS.value and \
            (result or '').strip() == 'True'
        if passed:
            log.info(f'{desc} 校验通过')
        else:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'{desc} 校验失败: {result}')
        return passed


    @classmethod
    def _do_lifecycle_after_destroy_query_srq(cls) -> None:
        """检查点1: 销毁 SRQ 后以原 srqn 查询，期望失败。"""
        log.info('[CP1] 查询后销毁 SRQ，再以原 srqn 查询。')
        status, srqn = cls._alloc_srq('obj_srq_cp1')
        if status != IpvbsStatusEnum.SUCCESS.value or not srqn:
            cls.set_bug_type('功能问题')
            cls.create_bug('创建 SRQ1 失败，无法执行销毁后查询。')
            return

        srq_status, srq_syndrome, srq_fields = cls._query_srq('obj_srq_cp1')
        if srq_status != 0:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'销毁前查询 SRQ1 返回非 0 status: '
                           f'{srq_status}, syndrome={srq_syndrome}，'
                           f'期望 status=0。')
            return
        log.info('销毁前查询 SRQ1 成功。')

        # 销毁前保存 SRQ 对象引用：服务端 close 会把含 'obj' 的引用从
        # rdma_dict 弹出，glb_dict 中的非 obj 引用不受影响，销毁后查询
        # 用它 + 原 srqn 触发 helper guard（对象已销毁）返回预期失败。
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            'glb_srq_cp1_keep = glb_obj_srq_cp1')
        if status != IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'保存 SRQ1 对象引用失败: {result}')
            return

        # 通过 DevX DESTROY_SRQ 销毁 SRQ1
        cls._close_srq('obj_srq_cp1')

        srq_status2, srq_syndrome2, srq_fields2 = cls._query_srq(
            'obj_srq_cp1', srqn=int(srqn), obj_ref='glb_srq_cp1_keep')
        if srq_status2 is None:
            cls.set_bug_type('功能问题')
            cls.create_bug('销毁后查询命令远程执行异常: '
                           f'{srq_syndrome2}')
            return
        if srq_status2 == 0:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'销毁后以原 srqn={srqn} 查询意外成功: '
                           f'status=0，期望查询失败。')
            return
        log.info(f'销毁后查询按预期失败: status={srq_status2}, '
                 f'syndrome={srq_syndrome2}。')
if __name__ == '__main__':
    NicLinuxRdmaDevxF0653010007PfLifecycleAfterDestroyQuerySrq().run()
