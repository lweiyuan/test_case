#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-08-31
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_query_CQ查询_异常op_mod查询

               opcode:  SXE3R_DEVX_OP_QUERY_CQ
               对象:    CQ（完成队列）
               用例ID:  nic_linux_rdma_devx_f_06_53_003_041

               实现说明：
               通过 Mlx5DevxObj.query()（内核 OBJ_QUERY 通道，opcode=0x402）
               查询已创建的 CQ，校验返回 status 与 cqc 关键字段
               （log_cq_size/eqn/st/cqe_sz）。

               环境信息来源：项目根目录下的"环境IP信息"文件，
               按 server/client 顺序解析 IP、端口、用户名、密码及 RDMA 设备名。

@changelog:
    2026-08-31 初始版本，基于 DevX CQ 查询模板生成。
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


class NicLinuxRdmaDevxF0653010005PfAbnormalOpModQueryCq(ScriptBase):
    """DevX QP 正常查询QP用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_003_041'
    case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_query'
                  '_QP查询_正常查询QP')
    case_module = 'DevX'
    case_type = '系统测试-功能'

    # Mellanox 固件 opcode（参见 include/linux/mlx5/mlx5_ifc.h）
    _MLX5_OP_QUERY_CQ = 0x402

    _OPCODE_NAME = 'SXE3R_DEVX_OP_QUERY_CQ'
    _OBJ_TYPE = 'CQ'
    _QUERY_COUNT = 200

    _ipvbs = None
    _rdma_dev = ''
    _cq_objs = []

    # 远端 QUERY_CQ 探测脚本（部署到 /root/sxetest/ 后执行）
    _PROBE_REMOTE_PATH = '/root/sxetest/probe_query_cq_file.py'
    _PROBE_CONTENT = (
        "# -*- coding: utf-8 -*-\n"
        "import sys\n"
        "sys.path.insert(0, '/root/sxetest')\n"
        "import devx_qp_helper as helper\n"
        "from pyverbs.providers.mlx5.mlx5dv import (Mlx5Context, "
        "Mlx5DVContextAttr, Mlx5UMEM, Mlx5UAR)\n"
        "dev = sys.argv[1] if len(sys.argv) > 1 else 'mlx5_0'\n"
        "ctx = Mlx5Context(Mlx5DVContextAttr(), dev)\n"
        "try:\n"
        "    pd_obj, pdn = helper.create_devx_pd(ctx)\n"
        "    uar = Mlx5UAR(ctx)\n"
        "    eqn = ctx.devx_query_eqn(0)\n"
        "    cq_umem = Mlx5UMEM(ctx, size=16384)\n"
        "    cq_dbr = Mlx5UMEM(ctx, size=8, alignment=8)\n"
        "    cq_obj, cqn = helper.create_devx_cq(ctx, eqn, uar, "
        "cq_umem, cq_dbr)\n"
        "    ret = helper.query_devx_cq(cq_obj, cqn=cqn)\n"
        "    print('query_cq_ok' if ret[0] == 0 else "
        "'query_cq_fail=' + repr(ret))\n"
        "    cq_obj.close(); cq_umem.close(); cq_dbr.close()\n"
        "    uar.close(); pd_obj.close()\n"
        "finally:\n"
        "    ctx.close()\n"
    )

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
        "1. 初始化 RDMA 测试框架与 ipvbs 会话；"
        "2. 创建 Mlx5Context，查询 EQN，创建 PD、UAR、CQ 及 UMEM；"
        "3. 通过 DevX CREATE_CQ 创建 CQ1（obj_cq_cp1），记录返回的 cqn；"
        "4. 调用 helper query_devx_cq(glb_obj_cq_cp1, op_mod=0xffff) 下发异常 op_mod；"
        "5. 校验查询返回失败（status=-1），负向预期成立；"
        "6. 用 op_mod=0 重新查询 CQ1，校验 status=0 且 eqn==glb_eqn，CQ 未受影响；"
        "7. 清理 CQ1 及相关资源，退出 ipvbs 会话。"
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
    def _probe_query_cq_support(cls) -> bool:
        """探测远端是否支持 DevX QUERY_CQ 命令（部署探测脚本到远端执行）。"""
        cls._deploy_helper_if_needed()  # 探测脚本依赖远端 helper
        local_probe = os.path.join(tempfile.gettempdir(), 'probe_query_cq_file.py')
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
            log.warning('无法获取执行端 IP，跳过 QUERY_CQ 探测。')
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
                'query_cq_ok' in (result or ''):
            log.info('探测到 DevX QUERY_CQ 命令可用。')
            return True
        if err and 'Errno: 22' in err:
            log.info('探测到 QUERY_CQ 命令已处理（查询无效 CQN 返回 EINVAL）。')
            return True
        log.warning(f'探测 QUERY_CQ 支持失败: err={err}, result={result}')
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

        # 4. 探测 QUERY_CQ 命令支持情况
        if not cls._probe_query_cq_support():
            log.warning('当前环境不支持 DevX QUERY_CQ，本用例 skip。')
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
        log.info(f'prepare: 初始化 CQ 查询测试环境 (opcode={cls._OPCODE_NAME}, '
                 f'dev={cls._rdma_dev})。')
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 CQ 查询测试环境。')
        cls._cq_objs = []
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)
        # 确保远程节点存在 devx_qp_helper.py
        cls._deploy_helper_if_needed()

        setup_cmds = [
            # 加载 DevX QP helper（自动部署到 /root/sxetest/）
            "__import__('sys').path.insert(0, '/root/sxetest')",
            "glb_helper = __import__('devx_qp_helper')",
            # 加载 pyverbs mlx5 DevX 模块
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', "
            "fromlist=['Mlx5Context', 'Mlx5DVContextAttr', 'Mlx5UMEM', 'Mlx5UAR'])",
            "glb_Mlx5Context = glb_mlx5dv.Mlx5Context",
            "glb_Mlx5DVContextAttr = glb_mlx5dv.Mlx5DVContextAttr",
            "glb_Mlx5UMEM = glb_mlx5dv.Mlx5UMEM",
            "glb_Mlx5UAR = glb_mlx5dv.Mlx5UAR",
            # 创建 Mlx5Context
            f"glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '{cls._rdma_dev}')",
            # 创建 PD（DevX ALLOC_PD）
            "glb_pd_ret = glb_helper.create_devx_pd(glb_mlx5_ctx)",
            "glb_pd_obj = glb_pd_ret[0]",
            "glb_pdn = glb_pd_ret[1]",
            # 创建 UAR
            "glb_uar = glb_Mlx5UAR(glb_mlx5_ctx)",
            # 查询 EQN
            "glb_eqn = glb_mlx5_ctx.devx_query_eqn(0)",
            # 创建 CQ 所需 UMEM（16KiB 可放 256 个 64B CQE）
            "glb_resource = __import__('resource')",
            "glb_cq_umem = glb_Mlx5UMEM(glb_mlx5_ctx, size=16384)",
            "glb_cq_dbr = glb_Mlx5UMEM(glb_mlx5_ctx, size=8, alignment=8)",
            # 创建 CQ
            "glb_cq_ret = glb_helper.create_devx_cq(glb_mlx5_ctx, glb_eqn, glb_uar, glb_cq_umem, glb_cq_dbr)",
            "glb_cq_obj = glb_cq_ret[0]",
            "glb_cqn = glb_cq_ret[1]",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'初始化 DevX CQ 查询环境失败, dev={cls._rdma_dev}, '
                    f'cmd={cmd}, rtn={result}')
                return

    @classmethod
    def do(cls) -> None:
        log.info('do: DevX QUERY_CQ 测试。')
        cls._do_abnormal_op_mod_query_cq()

    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 CQ 资源 (共 {len(cls._cq_objs)} 个)。')
        for cq_name in list(cls._cq_objs):
            cls._close_cq(cq_name)
        cls._cq_objs = []
        if cls._ipvbs is not None:
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    #  CQ 操作辅助方法                                                     #
    # ------------------------------------------------------------------ #

    @classmethod
    def _create_cq(cls, cq_name: str) -> tuple:
        """通过 DevX CREATE_CQ 分配一个 CQ，返回 (status, cqn)。"""
        glb_cq_name = f'glb_{cq_name}'
        create_cmds = [
            # 创建 CQ UMEM（16KiB 可放 256 个 64B CQE）和 DBR UMEM
            f"{glb_cq_name}_umem = glb_Mlx5UMEM(glb_mlx5_ctx, size=16384)",
            f"{glb_cq_name}_dbr = glb_Mlx5UMEM(glb_mlx5_ctx, size=8, alignment=8)",
            # 通过 helper 创建 CQ
            f"{glb_cq_name}_ret = glb_helper.create_devx_cq(glb_mlx5_ctx, glb_eqn, glb_uar, {glb_cq_name}_umem, {glb_cq_name}_dbr)",
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

        cls._cq_objs.append(cq_name)
        cqn = (cqn or '').strip()
        log.info(f'DevX CQ 创建成功: {cq_name}, cqn={cqn}')
        return IpvbsStatusEnum.SUCCESS.value, cqn

    @classmethod
    def _close_cq(cls, cq_name: str) -> bool:
        """释放指定 CQ 及其关联的 UMEM/DBR 资源。"""
        glb_cq_name = f'glb_{cq_name}'
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"{glb_cq_name}.close()")
        # 必须同步释放 CQ 占用的 UMEM 与 DBR，否则 UMEM 数量
        # 累积到上限后会导致后续 CREATE_CQ 返回 Remote I/O error。
        for res_name in (f"{glb_cq_name}_umem",
                         f"{glb_cq_name}_dbr"):
            cls._ipvbs.exec_and_get_ipvbs_result(f"{res_name}.close()")
        if status == IpvbsStatusEnum.SUCCESS.value:
            log.info(f'CQ 释放成功: {cq_name}')
            if cq_name in cls._cq_objs:
                cls._cq_objs.remove(cq_name)
            return True
        log.warning(f'CQ 释放异常: {cq_name}, rtn={result}')
        return False

    @classmethod
    def _query_cq(cls, cq_name: str, cqn=None, op_mod=0,
                  qf_suffix: str = '', obj_ref: str = None) -> tuple:
        """下发 DevX QUERY_CQ，返回 (cq_status, cq_syndrome, cq_fields)。

        obj_ref: 远端对象引用名（如 'glb_cq_cp1_keep'）。销毁后查询时
        服务端已把含 'obj' 的引用从 rdma_dict 弹出，必须改用保存的引用。
        """
        glb_cq_name = f'glb_{cq_name}'
        ref_name = obj_ref or glb_cq_name
        if cqn is None:
            cmd = (f"{glb_cq_name}_qf{qf_suffix} = glb_helper.query_devx_cq("
                   f"{ref_name}, op_mod={op_mod})")
        else:
            cqn_ref = (str(int(cqn)) if isinstance(cqn, str) else str(cqn))
            cmd = (f"{glb_cq_name}_qf{qf_suffix} = glb_helper.query_devx_cq("
                   f"{ref_name}, cqn={cqn_ref}, op_mod={op_mod})")
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
        if status != IpvbsStatusEnum.SUCCESS.value:
            return None, None, result
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"str({glb_cq_name}_qf{qf_suffix})")
        if status != IpvbsStatusEnum.SUCCESS.value:
            return None, None, result
        try:
            cq_status, cq_syndrome, cq_fields = ast.literal_eval(
                result.strip())
        except Exception:
            return None, None, result
        log.info(f'QUERY_CQ 返回: status={cq_status}, syndrome={cq_syndrome}')
        return cq_status, cq_syndrome, cq_fields

    @classmethod
    def _check_query_fields(cls, cq_name: str, expr: str, desc: str,
                            qf_suffix: str = '') -> bool:
        """远端校验查询字段。expr 引用 glb_<cq_name>_qf<qf_suffix>。"""
        glb_cq_name = f'glb_{cq_name}'
        qf_var = f'{glb_cq_name}_qf{qf_suffix}'
        chk_var = f'glb_chk_{cq_name}{qf_suffix}'
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
    def _do_abnormal_op_mod_query_cq(cls) -> None:
        """检查点1: 非法 op_mod=0xffff 查询，期望失败后 CQ 不受影响。"""
        log.info('[CP1] 下发异常 op_mod=0xffff 查询。')
        status, cqn = cls._create_cq('obj_cq_cp1')
        if status != IpvbsStatusEnum.SUCCESS.value or not cqn:
            cls.set_bug_type('功能问题')
            cls.create_bug('创建 CQ1 失败，无法执行异常 op_mod 查询。')
            return

        cq_status, cq_syndrome, cq_fields = cls._query_cq(
            'obj_cq_cp1', op_mod=0xffff)
        if cq_status is None:
            cls.set_bug_type('功能问题')
            cls.create_bug('op_mod=0xffff 查询命令远程执行异常: '
                           f'{cq_syndrome}')
            return
        if cq_status == 0:
            cls.set_bug_type('功能问题')
            cls.create_bug('op_mod=0xffff 查询意外成功: status=0，'
                           '期望查询失败。')
            return
        log.info(f'op_mod=0xffff 按预期失败: status={cq_status}, '
                 f'syndrome={cq_syndrome}。')

        cq_status2, cq_syndrome2, cq_fields2 = cls._query_cq('obj_cq_cp1')
        if cq_status2 != 0:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'op_mod=0 复查 CQ1 返回非 0 status: '
                           f'{cq_status2}, syndrome={cq_syndrome2}，'
                           f'期望 status=0。')
            return
        cls._check_query_fields(
            'obj_cq_cp1',
            "glb_obj_cq_cp1_qf[2]['eqn'] == glb_eqn",
            'CQ1 op_mod 复查字段校验（eqn）')
if __name__ == '__main__':
    NicLinuxRdmaDevxF0653010005PfAbnormalOpModQueryCq().run()
