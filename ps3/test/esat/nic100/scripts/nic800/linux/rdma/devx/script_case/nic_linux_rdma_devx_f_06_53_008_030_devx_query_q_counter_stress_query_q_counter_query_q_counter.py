#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-09-01
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_query_Q_COUNTER查询_压力查询

               opcode:  SXE3R_DEVX_OP_QUERY_Q_COUNTER
               对象:    Q_COUNTER（RDMA Q 计数器）
               用例ID:  nic_linux_rdma_devx_f_06_53_008_030

               实现说明：
               通过 Mlx5DevxObj.query()（内核 OBJ_QUERY 通道，opcode=0x773）
               查询已分配的 Q_COUNTER，校验返回 status 与全部计数字段
               （rx_write_requests/rx_read_requests/out_of_buffer 等）。

               QUERY_Q_COUNTER 输入为 32 字节（counter_set_id 为单字节，
               位于输入偏移 31），对象 id 校验由内核 devx_is_valid_obj_id
               完成：cmd_in 中 counter_set_id 与对象 id 不一致时返回 EINVAL，
               到不了固件。

               环境信息来源：项目根目录下的"环境IP信息"文件，
               按 server/client 顺序解析 IP、端口、用户名、密码及 RDMA 设备名。

@changelog:
    2026-09-01 初始版本，基于 DevX QUERY_MKEY 模板生成。
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


class NicLinuxRdmaDevxF0653008008PfStressQueryQCounter(ScriptBase):
    """DevX Q_COUNTER 压力查询用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_008_030'
    case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_query'
                  '_Q_COUNTER查询_压力查询')
    case_module = 'DevX'
    case_type = '系统测试-功能'

    # Mellanox 固件 opcode（参见 include/linux/mlx5/mlx5_ifc.h）
    _MLX5_OP_QUERY_Q_COUNTER = 0x773

    _OPCODE_NAME = 'SXE3R_DEVX_OP_QUERY_Q_COUNTER'
    _OBJ_TYPE = 'Q_COUNTER'
    _QUERY_COUNT = 200

    _ipvbs = None
    _rdma_dev = ''
    _counter_objs = []

    # 远端 QUERY_Q_COUNTER 探测脚本（部署到 /root/sxetest/ 后执行）
    _PROBE_REMOTE_PATH = '/root/sxetest/probe_query_q_counter_file.py'
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
        "    counter_obj, csid = helper.create_devx_q_counter(ctx)\n"
        "except Exception as exc:\n"
        "    print('query_q_counter_create_fail=' + repr(exc))\n"
        "    ctx.close()\n"
        "    sys.exit(0)\n"
        "try:\n"
        "    ret = helper.query_devx_q_counter(counter_obj)\n"
        "    print('query_q_counter_ok' if ret[0] == 0 else "
        "'query_q_counter_fail=' + repr(ret))\n"
        "finally:\n"
        "    counter_obj.close()\n"
        "    ctx.close()\n"
    )

    # 环境IP信息文件相关
    _ENV_IP_INFO_FILE_NAME = '环境IP信息'
    _env_ip_info = None

    test_object = 'RDMA Q_COUNTER（Q 计数器）'
    test_module = 'rdma'
    test_tool = 'pyverbs'
    test_precondition = (
        '1. RDMA 设备（mlx5_0）在线且 pyverbs mlx5 可用；\n'
        '2. 已部署 ipvbs 运行时（ipvbs_s.py / ipvbs.py）；\n'
        '3. 测试机与 server 节点 SSH 免密连通。'
    )
    test_steps = (
        "1. 初始化 RDMA 测试框架与 ipvbs 会话；"
        "2. 创建 Mlx5Context，通过 DevX ALLOC_Q_COUNTER 创建 Q_COUNTER1（obj_counter_cp1）；"
        "3. 记录 Q_COUNTER1 的 counter_set_id（glb_obj_counter_cp1_num）；"
        "4. 连续 200 次查询 Q_COUNTER1，校验全部 status=0；"
        "5. 校验 200 次查询的计数字段完全一致；"
        "6. 清理 Q_COUNTER1 及相关资源，退出 ipvbs 会话。"
    )

    @classmethod
    def set_parameters(cls) -> None:
        cls.test_object = 'RDMA Q_COUNTER（Q 计数器）'
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
    def _probe_query_q_counter_support(cls) -> bool:
        """探测远端是否支持 DevX QUERY_Q_COUNTER（部署探测脚本到远端执行）。"""
        cls._deploy_helper_if_needed()  # 探测脚本依赖远端 helper
        local_probe = os.path.join(tempfile.gettempdir(),
                                   'probe_query_q_counter_file.py')
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
            log.warning('无法获取执行端 IP，跳过 QUERY_Q_COUNTER 探测。')
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
                'query_q_counter_create_fail' in (result or ''):
            log.warning('固件不支持 DevX uid 下 ALLOC_Q_COUNTER，'
                        '本用例 skip。')
            return False
        if status == RtnStatusEnum.SUCCESS.value and \
                'query_q_counter_ok' in (result or ''):
            log.info('探测到 DevX QUERY_Q_COUNTER 命令可用。')
            return True
        if status == RtnStatusEnum.SUCCESS.value and \
                'query_q_counter_fail' in (result or ''):
            log.warning(f'探测 QUERY_Q_COUNTER 查询失败: {result}，'
                        f'本用例 skip。')
            return False
        log.warning(f'探测 QUERY_Q_COUNTER 支持失败: err={err}, result={result}')
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

        # 4. 探测 QUERY_Q_COUNTER 命令支持情况
        if not cls._probe_query_q_counter_support():
            log.warning('当前环境不支持 DevX QUERY_Q_COUNTER，本用例 skip。')
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
        log.info(f'prepare: 初始化 Q_COUNTER 查询测试环境 (opcode={cls._OPCODE_NAME}, '
                 f'dev={cls._rdma_dev})。')
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 Q_COUNTER 查询测试环境。')
        cls._counter_objs = []
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)
        # 确保远程节点存在 devx_qp_helper.py
        cls._deploy_helper_if_needed()

        setup_cmds = [
            # 加载 DevX Q_COUNTER helper（自动部署到 /root/sxetest/）
            "__import__('sys').path.insert(0, '/root/sxetest')",
            "glb_helper = __import__('devx_qp_helper')",
            # 加载 pyverbs mlx5 DevX 模块
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', "
            "fromlist=['Mlx5Context', 'Mlx5DVContextAttr', 'Mlx5DevxObj', 'Mlx5UMEM'])",
            "glb_Mlx5Context = glb_mlx5dv.Mlx5Context",
            "glb_Mlx5DVContextAttr = glb_mlx5dv.Mlx5DVContextAttr",
            "glb_Mlx5DevxObj = glb_mlx5dv.Mlx5DevxObj",
            "glb_Mlx5UMEM = glb_mlx5dv.Mlx5UMEM",
            # 创建 Mlx5Context（Q_COUNTER 直接绑定 Context，无需 PD）
            f"glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), "
            f"'{cls._rdma_dev}')",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'初始化 DevX Q_COUNTER 查询环境失败, dev={cls._rdma_dev}, '
                    f'cmd={cmd}, rtn={result}')
                return

    @classmethod
    def do(cls) -> None:
        log.info('do: DevX QUERY_Q_COUNTER 测试。')
        cls._do_stress_query_q_counter()

    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 Q_COUNTER 资源 (共 {len(cls._counter_objs)} 个)。')
        for counter_name in list(cls._counter_objs):
            cls._close_q_counter(counter_name)
        cls._counter_objs = []
        if cls._ipvbs is not None:
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    #  Q_COUNTER 操作辅助方法                                               #
    # ------------------------------------------------------------------ #

    @classmethod
    def _alloc_q_counter(cls, counter_name: str) -> tuple:
        """通过 DevX ALLOC_Q_COUNTER 分配一个 Q_COUNTER，返回 (status, csid)。"""
        glb_counter_name = f'glb_{counter_name}'
        alloc_cmds = [
            # 通过 helper 创建 Q_COUNTER（无需 PD，直接绑定 Context）
            f"{glb_counter_name}_ret = glb_helper.create_devx_q_counter("
            f"glb_mlx5_ctx)",
            f"{glb_counter_name} = {glb_counter_name}_ret[0]",
            f"{glb_counter_name}_num = {glb_counter_name}_ret[1]",
        ]
        for cmd in alloc_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                log.error(f'DevX ALLOC_Q_COUNTER 命令失败: {cmd}, rtn={result}')
                return status, None

        status, csid = cls._ipvbs.exec_and_get_ipvbs_result(
            f"str({glb_counter_name}_num)")
        if status != IpvbsStatusEnum.SUCCESS.value:
            return status, None

        cls._counter_objs.append(counter_name)
        csid = (csid or '').strip()
        log.info(f'DevX Q_COUNTER 分配成功: {counter_name}, '
                 f'counter_set_id={csid}')
        return IpvbsStatusEnum.SUCCESS.value, csid

    @classmethod
    def _close_q_counter(cls, counter_name: str) -> bool:
        """释放指定 Q_COUNTER。"""
        glb_counter_name = f'glb_{counter_name}'
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"{glb_counter_name}.close()")
        if status == IpvbsStatusEnum.SUCCESS.value:
            log.info(f'Q_COUNTER 释放成功: {counter_name}')
            if counter_name in cls._counter_objs:
                cls._counter_objs.remove(counter_name)
            return True
        log.warning(f'Q_COUNTER 释放异常: {counter_name}, rtn={result}')
        return False

    @classmethod
    def _query_q_counter(cls, counter_name: str, csid=None, op_mod=0,
                         qf_suffix: str = '', obj_ref: str = None) -> tuple:
        """下发 DevX QUERY_Q_COUNTER，返回 (counter_status, counter_syndrome,
        counter_fields)。

        csid: 查询时使用的 counter_set_id。缺省时 helper 从对象 out_view
        解析；边界/销毁后查询可传入显式值（或远端变量名）。
        obj_ref: 远端对象引用名（如 'glb_counter_cp1_keep'）。销毁后查询时
        服务端已把含 'obj' 的引用从 rdma_dict 弹出，必须改用保存的引用。
        """
        glb_counter_name = f'glb_{counter_name}'
        ref_name = obj_ref or glb_counter_name
        if csid is None:
            cmd = (f"{glb_counter_name}_qf{qf_suffix} = "
                   f"glb_helper.query_devx_q_counter("
                   f"{ref_name}, op_mod={op_mod})")
        else:
            csid_ref = str(csid) if not isinstance(csid, str) else csid
            cmd = (f"{glb_counter_name}_qf{qf_suffix} = "
                   f"glb_helper.query_devx_q_counter("
                   f"{ref_name}, counter_set_id={csid_ref}, op_mod={op_mod})")
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
        if status != IpvbsStatusEnum.SUCCESS.value:
            return None, None, result
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"str({glb_counter_name}_qf{qf_suffix})")
        if status != IpvbsStatusEnum.SUCCESS.value:
            return None, None, result
        try:
            counter_status, counter_syndrome, counter_fields = ast.literal_eval(
                result.strip())
        except Exception:
            return None, None, result
        log.info(f'QUERY_Q_COUNTER 返回: status={counter_status}, '
                 f'syndrome={counter_syndrome}')
        return counter_status, counter_syndrome, counter_fields

    @classmethod
    def _check_query_fields(cls, counter_name: str, expr: str, desc: str,
                            qf_suffix: str = '') -> bool:
        """远端校验查询字段。expr 引用 glb_<counter_name>_qf<qf_suffix>。"""
        glb_counter_name = f'glb_{counter_name}'
        qf_var = f'{glb_counter_name}_qf{qf_suffix}'
        chk_var = f'glb_chk_{counter_name}{qf_suffix}'
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
    def _do_stress_query_q_counter(cls) -> None:
        """检查点1: 连续 200 次查询同一 Q_COUNTER，全部成功且字段一致。"""
        log.info(f'[CP1] 连续 {cls._QUERY_COUNT} 次查询 Q_COUNTER1。')
        status, csid = cls._alloc_q_counter('obj_counter_cp1')
        if status != IpvbsStatusEnum.SUCCESS.value or not csid:
            cls.set_bug_type('功能问题')
            cls.create_bug('创建 Q_COUNTER1 失败，无法执行压力查询。')
            return

        # 循环在 helper 函数内部执行：ipvbs 服务端用 eval 解析远程命令，
        # eval 字符串里的列表推导式/匿名函数是独立作用域，看不到
        # response() 的局部变量 self/rdma_dict，会抛
        # NameError: name 'self' is not defined。
        assign_cmd = (
            f"glb_stress_qf = glb_helper.stress_query_devx_q_counter("
            f"glb_obj_counter_cp1, {cls._QUERY_COUNT})"
        )
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(assign_cmd)
        if status != IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'连续 {cls._QUERY_COUNT} 次查询命令执行失败: '
                           f'{result}')
            return
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            'str(glb_stress_qf)')
        if status != IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'取回压力查询结果失败: {result}')
            return
        try:
            status_list, fields_consistent = ast.literal_eval(
                result.strip())
        except Exception as exc:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'解析压力查询结果失败: {exc}, raw={result}')
            return
        if not isinstance(status_list, list) or                 len(status_list) != cls._QUERY_COUNT:
            cls.set_bug_type('功能问题')
            cls.create_bug('压力查询返回条数异常，期望 '
                           f'{cls._QUERY_COUNT} 条。')
            return
        if not all(s == 0 for s, _ in status_list):
            fail_idx = next(i for i, (s, sy) in enumerate(status_list)
                            if s != 0)
            cls.set_bug_type('功能问题')
            cls.create_bug(f'压力查询第 {fail_idx} 次返回非 0 status: '
                           f'status_list[:5]={status_list[:5]}')
            return
        if not fields_consistent:
            cls.set_bug_type('功能问题')
            cls.create_bug('压力查询期间计数字段发生变化，字段不一致。')
            return
        log.info(f'连续 {cls._QUERY_COUNT} 次查询全部成功且字段一致。')
if __name__ == '__main__':
    NicLinuxRdmaDevxF0653008008PfStressQueryQCounter().run()
