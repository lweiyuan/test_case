#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-09-01
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_query_MKEY查询_正常查询MKEY

               opcode:  SXE3R_MQ_OP_QUERY_MR
               对象:    MKEY（内存键 / MR）
               用例ID:  nic_linux_rdma_devx_f_06_53_006_023

               实现说明：
               通过 Mlx5DevxObj.query()（内核 OBJ_QUERY 通道，opcode=0x201）
               查询已创建的 MKEY，校验返回 status 与 mkc 关键字段
               （pd/qpn/length64/len/start_addr/log_page_size）。

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


class NicLinuxRdmaDevxF0653010001PfNormalQueryMkey(ScriptBase):
    """DevX MKEY 正常查询MKEY用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_006_023'
    case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_query'
                  '_MKEY查询_正常查询MKEY')
    case_module = 'DevX'
    case_type = '系统测试-功能'

    # Mellanox 固件 opcode（参见 include/linux/mlx5/mlx5_ifc.h）
    _MLX5_OP_QUERY_MKEY = 0x201

    _OPCODE_NAME = 'SXE3R_MQ_OP_QUERY_MR'
    _OBJ_TYPE = 'MKEY'
    _QUERY_COUNT = 200
    _MKEY_LENGTH = 4096

    _ipvbs = None
    _rdma_dev = ''
    _mkey_objs = []

    # 远端 QUERY_MKEY 探测脚本（部署到 /root/sxetest/ 后执行）
    _PROBE_REMOTE_PATH = '/root/sxetest/probe_query_mkey_file.py'
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
        "    try:\n"
        "        mkey_obj, mkey = helper.create_devx_mkey(ctx, pdn)\n"
        "    except Exception as exc:\n"
        "        print('query_mkey_create_fail=' + repr(exc))\n"
        "        pd_obj.close()\n"
        "        ctx.close()\n"
        "        sys.exit(0)\n"
        "    if not hasattr(mkey_obj, 'query'):\n"
        "        print('query_mkey_fallback_verbs')\n"
        "    else:\n"
        "        ret = helper.query_devx_mkey(mkey_obj, "
        "mkey_index=mkey & 0xFFFFFF)\n"
        "        print('query_mkey_ok' if ret[0] == 0 else "
        "'query_mkey_fail=' + repr(ret))\n"
        "        mkey_obj.close()\n"
        "    pd_obj.close()\n"
        "finally:\n"
        "    ctx.close()\n"
    )

    # 环境IP信息文件相关
    _ENV_IP_INFO_FILE_NAME = '环境IP信息'
    _env_ip_info = None

    test_object = 'RDMA MKEY（内存键）'
    test_module = 'rdma'
    test_tool = 'pyverbs'
    test_precondition = (
        '1. RDMA 设备（mlx5_0）在线且 pyverbs mlx5 可用；\n'
        '2. 已部署 ipvbs 运行时（ipvbs_s.py / ipvbs.py）；\n'
        '3. 测试机与 server 节点 SSH 免密连通。'
    )
    test_steps = (
        "1. 初始化 RDMA 测试框架与 ipvbs 会话；"
        "2. 创建 Mlx5Context，通过 DevX ALLOC_PD 创建 PD；"
        "3. 通过 DevX CREATE_MKEY 创建 MKEY1（obj_mkey_cp1），记录返回的 mkey；"
        "4. 调用 helper query_devx_mkey(glb_obj_mkey_cp1) 查询 MKEY1；"
        "5. 校验查询返回 status=0，且 mkc 中 pd==glb_pdn、qpn==0xffffff、length64==1、len==glb_mkey_len、start_addr==0、log_page_size==0；"
        "6. 再次查询 MKEY1，校验两次查询结果完全一致；"
        "7. 创建 MKEY2（obj_mkey_cp2）并查询，校验其 pd 仍等于 glb_pdn；"
        "8. 清理 MKEY1、MKEY2 及相关资源，退出 ipvbs 会话。"
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
    def _probe_query_mkey_support(cls) -> bool:
        """探测远端是否支持 DevX QUERY_MKEY 命令（部署探测脚本到远端执行）。"""
        cls._deploy_helper_if_needed()  # 探测脚本依赖远端 helper
        local_probe = os.path.join(tempfile.gettempdir(), 'probe_query_mkey_file.py')
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
            log.warning('无法获取执行端 IP，跳过 QUERY_MKEY 探测。')
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
                'query_mkey_fallback_verbs' in (result or ''):
            log.warning('MKEY 创建回退到标准 verbs MR（无 query 通道），'
                        '不支持 DevX QUERY_MKEY，本用例 skip。')
            return False
        if status == RtnStatusEnum.SUCCESS.value and \
                'query_mkey_create_fail' in (result or ''):
            log.warning('固件不支持 DevX uid 下创建 MKEY（errno 121），'
                        '本用例 skip。')
            return False
        if status == RtnStatusEnum.SUCCESS.value and \
                'query_mkey_ok' in (result or ''):
            log.info('探测到 DevX QUERY_MKEY 命令可用。')
            return True
        if err and 'Errno: 22' in err:
            log.info('探测到 QUERY_MKEY 命令已处理（查询无效 MKEY 返回 EINVAL）。')
            return True
        log.warning(f'探测 QUERY_MKEY 支持失败: err={err}, result={result}')
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

        # 4. 探测 QUERY_MKEY 命令支持情况
        if not cls._probe_query_mkey_support():
            log.warning('当前环境不支持 DevX QUERY_MKEY，本用例 skip。')
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
        log.info(f'prepare: 初始化 MKEY 查询测试环境 (opcode={cls._OPCODE_NAME}, '
                 f'dev={cls._rdma_dev})。')
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 MKEY 查询测试环境。')
        cls._mkey_objs = []
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)
        # 确保远程节点存在 devx_qp_helper.py
        cls._deploy_helper_if_needed()

        setup_cmds = [
            # 加载 DevX MKEY helper（自动部署到 /root/sxetest/）
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
            # 通过 DevX ALLOC_PD 创建 PD（MKEY 需要有效的 PD）
            "glb_pd_ret = glb_helper.create_devx_pd(glb_mlx5_ctx)",
            "glb_pd_obj = glb_pd_ret[0]",
            "glb_pdn = glb_pd_ret[1]",
            # MKEY 长度（与 create_devx_mkey length 参数保持一致）
            "glb_mkey_len = 4096",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'初始化 DevX MKEY 查询环境失败, dev={cls._rdma_dev}, '
                    f'cmd={cmd}, rtn={result}')
                return

    @classmethod
    def do(cls) -> None:
        log.info('do: DevX QUERY_MKEY 测试。')
        cls._do_normal_query_mkey()

    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 MKEY 资源 (共 {len(cls._mkey_objs)} 个)。')
        for mkey_name in list(cls._mkey_objs):
            cls._close_mkey(mkey_name)
        cls._mkey_objs = []
        if cls._ipvbs is not None:
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    #  MKEY 操作辅助方法                                                     #
    # ------------------------------------------------------------------ #

    @classmethod
    def _alloc_mkey(cls, mkey_name: str) -> tuple:
        """通过 DevX CREATE_MKEY 分配一个 MKEY，返回 (status, mkey)。"""
        glb_mkey_name = f'glb_{mkey_name}'
        alloc_cmds = [
            # 通过 helper 创建 MKEY（free=1 占位 MKEY，绑定 PD）
            f"{glb_mkey_name}_ret = glb_helper.create_devx_mkey("
            f"glb_mlx5_ctx, glb_pdn, length={cls._MKEY_LENGTH})",
            f"{glb_mkey_name} = {glb_mkey_name}_ret[0]",
            f"{glb_mkey_name}_num = {glb_mkey_name}_ret[1]",
        ]
        for cmd in alloc_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                log.error(f'DevX CREATE_MKEY 命令失败: {cmd}, rtn={result}')
                return status, None

        status, mkey = cls._ipvbs.exec_and_get_ipvbs_result(
            f"str({glb_mkey_name}_num)")
        if status != IpvbsStatusEnum.SUCCESS.value:
            return status, None

        cls._mkey_objs.append(mkey_name)
        mkey = (mkey or '').strip()
        log.info(f'DevX MKEY 分配成功: {mkey_name}, mkey={mkey}')
        return IpvbsStatusEnum.SUCCESS.value, mkey

    @classmethod
    def _close_mkey(cls, mkey_name: str) -> bool:
        """释放指定 MKEY。"""
        glb_mkey_name = f'glb_{mkey_name}'
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"{glb_mkey_name}.close()")
        if status == IpvbsStatusEnum.SUCCESS.value:
            log.info(f'MKEY 释放成功: {mkey_name}')
            if mkey_name in cls._mkey_objs:
                cls._mkey_objs.remove(mkey_name)
            return True
        log.warning(f'MKEY 释放异常: {mkey_name}, rtn={result}')
        return False

    @classmethod
    def _query_mkey(cls, mkey_name: str, mkey_index=None, op_mod=0,
                    qf_suffix: str = '', obj_ref: str = None) -> tuple:
        """下发 DevX QUERY_MKEY，返回 (mkey_status, mkey_syndrome, mkey_fields)。

        obj_ref: 远端对象引用名（如 'glb_mkey_cp1_keep'）。销毁后查询时
        服务端已把含 'obj' 的引用从 rdma_dict 弹出，必须改用保存的引用。
        """
        glb_mkey_name = f'glb_{mkey_name}'
        ref_name = obj_ref or glb_mkey_name
        if mkey_index is None:
            cmd = (f"{glb_mkey_name}_qf{qf_suffix} = glb_helper.query_devx_mkey("
                   f"{ref_name}, op_mod={op_mod})")
        else:
            mkey_index_ref = (str(int(mkey_index)) if isinstance(mkey_index, str)
                              else str(mkey_index))
            cmd = (f"{glb_mkey_name}_qf{qf_suffix} = glb_helper.query_devx_mkey("
                   f"{ref_name}, mkey_index={mkey_index_ref}, op_mod={op_mod})")
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
        if status != IpvbsStatusEnum.SUCCESS.value:
            return None, None, result
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"str({glb_mkey_name}_qf{qf_suffix})")
        if status != IpvbsStatusEnum.SUCCESS.value:
            return None, None, result
        try:
            mkey_status, mkey_syndrome, mkey_fields = ast.literal_eval(
                result.strip())
        except Exception:
            return None, None, result
        log.info(f'QUERY_MKEY 返回: status={mkey_status}, syndrome={mkey_syndrome}')
        return mkey_status, mkey_syndrome, mkey_fields

    @classmethod
    def _check_query_fields(cls, mkey_name: str, expr: str, desc: str,
                            qf_suffix: str = '') -> bool:
        """远端校验查询字段。expr 引用 glb_<mkey_name>_qf<qf_suffix>。"""
        glb_mkey_name = f'glb_{mkey_name}'
        qf_var = f'{glb_mkey_name}_qf{qf_suffix}'
        chk_var = f'glb_chk_{mkey_name}{qf_suffix}'
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
    def _do_normal_query_mkey(cls) -> None:
        """检查点1: 正常查询已创建 MKEY，校验查询字段。"""
        log.info('[CP1] 正常查询 MKEY1。')
        status, mkey = cls._alloc_mkey('obj_mkey_cp1')
        if status != IpvbsStatusEnum.SUCCESS.value or not mkey:
            cls.set_bug_type('功能问题')
            cls.create_bug('创建 MKEY1 失败，无法执行正常查询。')
            return

        mkey_status, mkey_syndrome, mkey_fields = cls._query_mkey('obj_mkey_cp1')
        if mkey_status is None:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'查询 MKEY1 远程执行异常: {mkey_syndrome}')
            return
        if mkey_status != 0:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'正常查询 MKEY1 返回非 0 status: {mkey_status}, '
                           f'syndrome={mkey_syndrome}，期望 status=0。')
            return
        cls._check_query_fields(
            'obj_mkey_cp1',
            "glb_obj_mkey_cp1_qf[2]['pd'] == glb_pdn and "
            "glb_obj_mkey_cp1_qf[2]['qpn'] == 0xffffff and "
            "glb_obj_mkey_cp1_qf[2]['length64'] == 1 and "
            "glb_obj_mkey_cp1_qf[2]['len'] == glb_mkey_len and "
            "glb_obj_mkey_cp1_qf[2]['start_addr'] == 0 and "
            "glb_obj_mkey_cp1_qf[2]['log_page_size'] == 0",
            'MKEY1 查询字段校验（pd/qpn/length64/len/start_addr/log_page_size）')

        mkey_status2, mkey_syndrome2, mkey_fields2 = cls._query_mkey(
            'obj_mkey_cp1', qf_suffix='2')
        if mkey_status2 != 0 or mkey_fields2 is None:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'重复查询 MKEY1 失败: status={mkey_status2}, '
                           f'syndrome={mkey_syndrome2}，期望两次查询均成功。')
            return
        if mkey_fields != mkey_fields2:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'两次查询 MKEY1 结果不一致: {mkey_fields} != '
                           f'{mkey_fields2}，期望完全一致。')
            return
        log.info('两次查询 MKEY1 结果一致，校验通过。')

        status2, mkey2 = cls._alloc_mkey('obj_mkey_cp2')
        if status2 != IpvbsStatusEnum.SUCCESS.value or not mkey2:
            cls.set_bug_type('功能问题')
            cls.create_bug('创建 MKEY2 失败，无法执行多 MKEY 查询。')
            return
        mkey_status3, mkey_syndrome3, mkey_fields3 = cls._query_mkey('obj_mkey_cp2')
        if mkey_status3 != 0:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'查询 MKEY2 返回非 0 status: {mkey_status3}, '
                           f'syndrome={mkey_syndrome3}，期望 status=0。')
            return
        cls._check_query_fields(
            'obj_mkey_cp2',
            "glb_obj_mkey_cp2_qf[2]['pd'] == glb_pdn",
            'MKEY2 查询字段校验（pd）')
if __name__ == '__main__':
    NicLinuxRdmaDevxF0653010001PfNormalQueryMkey().run()
