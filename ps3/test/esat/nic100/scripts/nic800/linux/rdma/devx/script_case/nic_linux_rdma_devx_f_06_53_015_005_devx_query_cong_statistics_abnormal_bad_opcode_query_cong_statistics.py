#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-09-01
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_create_QUERY_CONG_STATISTICS_异常QUERY_CONG_STATISTICS_非法opcode

               opcode:  SXE3R_DEVX_OP_QUERY_CONG_STATISTICS(0x826)
               对象:    拥塞控制统计查询（无对象）
               用例ID:  nic_linux_rdma_devx_f_06_53_015_005

               实现说明：
               以未定义 opcode=0x1 构造 inbox 下发，预期固件拒绝（返回非 0 status 或 Python 层异常），随后标准 QUERY_CONG_STATISTICS 对照验证命令通道未受影响。

               环境信息来源：项目根目录下的"环境IP信息"文件，
               按 server/client 顺序解析 IP、端口、用户名、密码及 RDMA 设备名。

@changelog:
    2026-09-01 初始版本，基于 DevX QUERY_HCA_CAP 模板生成。
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


class NicLinuxRdmaDevxF0653015005PfAbnormalBadOpcodeQueryCongStatistics(ScriptBase):
    """DevX QUERY_CONG_STATISTICS 异常QUERY_CONG_STATISTICS_非法opcode用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_015_005'
    case_title = 'RDMA DevX 接口测试_用户态_PF_devx_obj_create_QUERY_CONG_STATISTICS_异常QUERY_CONG_STATISTICS_非法opcode'
    case_module = 'DevX'
    case_type = '系统测试-功能'

    # Mellanox 固件 opcode（参见 include/linux/mlx5/mlx5_ifc.h）
    _MLX5_OP_QUERY_CONG_STATISTICS = 0x826

    _OPCODE_NAME = 'SXE3R_DEVX_OP_QUERY_CONG_STATISTICS'
    _OBJ_TYPE = '拥塞控制统计查询（无对象）'
    _QCS_COUNT = 100

    _ipvbs = None
    _rdma_dev = ''
    _probe_ok = False

    # 远端 QUERY_CONG_STATISTICS 探测脚本（部署到 /root/sxetest/ 后执行）
    _PROBE_REMOTE_PATH = '/root/sxetest/probe_query_cong_statistics_file.py'
    _PROBE_CONTENT = (
        """# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '/root/sxetest')
import devx_qp_helper as helper
from pyverbs.providers.mlx5.mlx5dv import (Mlx5Context, Mlx5DVContextAttr)
dev = sys.argv[1] if len(sys.argv) > 1 else 'mlx5_0'
ctx = Mlx5Context(Mlx5DVContextAttr(), dev)
try:
    status, syndrome, _ = helper.query_cong_statistics(ctx)
    print('qcs_ok' if status == 0 else 'qcs_fail=' + repr((status, syndrome)))
finally:
    ctx.close()
"""
    )

    # 环境IP信息文件相关
    _ENV_IP_INFO_FILE_NAME = '环境IP信息'
    _env_ip_info = None

    test_object = 'RDMA 拥塞控制统计查询（QUERY_CONG_STATISTICS）'
    test_module = 'rdma'
    test_tool = 'pyverbs'
    test_precondition = (
        '1. RDMA 设备（mlx5_0）在线且 pyverbs mlx5 可用；\n'
        '2. 已部署 ipvbs 运行时（ipvbs_s.py / ipvbs.py）；\n'
        '3. 测试机与 server 节点 SSH 免密连通。'
    )
    test_steps = (
        "1. 初始化 RDMA 测试框架与 ipvbs 会话；\n"
        "2. 创建 Mlx5Context（glb_mlx5_ctx）；\n"
        "3. 构造非法 opcode=0x1 的 inbox：struct.pack('>HHHH', 0x1, 0, 0, 0) + b'\\x00'*8，调用 helper query_cong_statistics(raw=...) 下发；\n"
        "4. 校验命令被拒绝（status != 0，返回固件错误或异常描述）；\n"
        "5. 下发标准 QUERY_CONG_STATISTICS 对照，校验 status=0（命令通道未受影响）；\n"
        "6. 清理资源（关闭 context），退出 ipvbs 会话。"

    )
    test_expect = (
        "1. ipvbs 会话建立成功，RDMA 框架初始化完成；\n"
        "2. Mlx5Context 创建成功，无异常；\n"
        "3. 非法 opcode inbox 构造并下发成功；\n"
        "4. 命令被拒绝，返回非 0 status 或异常，未定义 opcode 不被执行；\n"
        "5. 标准 QUERY_CONG_STATISTICS 对照返回 status=0，命令通道未受影响；\n"
        "6. 资源清理完成，无泄漏，无报错。"

    )

    @classmethod
    def set_parameters(cls) -> None:
        cls.test_object = 'RDMA 拥塞控制统计查询（QUERY_CONG_STATISTICS）'
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
    def _probe_qcs_support(cls) -> bool:
        """探测远端 DevX QUERY_CONG_STATISTICS 是否可用（部署探测脚本到远端执行）。"""
        cls._deploy_helper_if_needed()  # 探测脚本依赖远端 helper
        local_probe = os.path.join(tempfile.gettempdir(),
                                   'probe_query_cong_statistics_file.py')
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
            log.warning('无法获取执行端 IP，跳过 QUERY_CONG_STATISTICS 探测。')
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
                'qcs_ok' in (result or ''):
            log.info('探测到 DevX QUERY_CONG_STATISTICS 命令可用。')
            return True
        if status == RtnStatusEnum.SUCCESS.value and \
                'qcs_fail' in (result or ''):
            log.warning(f'探测 QUERY_CONG_STATISTICS 返回失败: {result}，'
                        f'本用例 skip。')
            return False
        log.warning(f'探测 QUERY_CONG_STATISTICS 支持失败: err={err}, '
                    f'result={result}')
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
            log.warning(
                f'指定的 RDMA 设备 {cls._rdma_dev} 不存在，'
                f'当前设备列表: {dev_list}，自动回退到首个可用设备。')
            cls._rdma_dev = dev_list[0]
        if not cls._rdma_dev:
            cls._rdma_dev = dev_list[0]
        log.info(f'检测到 RDMA 设备: {dev_list}, 本用例使用: {cls._rdma_dev}')

        # 3. 检查 pyverbs mlx5 DevX 是否可用
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

        # 4. 探测 QUERY_CONG_STATISTICS 命令支持情况
        if not cls._probe_qcs_support():
            log.warning('当前环境不支持 DevX QUERY_CONG_STATISTICS，'
                        '本用例 skip。')
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
        log.info(f'prepare: 初始化 QUERY_CONG_STATISTICS 测试环境 '
                 f'(opcode={cls._OPCODE_NAME}, dev={cls._rdma_dev})。')
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 '
                           'QUERY_CONG_STATISTICS 测试环境。')
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)
        # 确保远程节点存在 devx_qp_helper.py
        cls._deploy_helper_if_needed()

        setup_cmds = [
            # 加载 DevX QUERY_CONG_STATISTICS helper（自动部署到 /root/sxetest/）
            "__import__('sys').path.insert(0, '/root/sxetest')",
            "glb_helper = __import__('devx_qp_helper')",
            # 加载 pyverbs mlx5 DevX 模块
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', "
            "fromlist=['Mlx5Context', 'Mlx5DVContextAttr', 'Mlx5DevxObj', 'Mlx5UMEM'])",
            "glb_Mlx5Context = glb_mlx5dv.Mlx5Context",
            "glb_Mlx5DVContextAttr = glb_mlx5dv.Mlx5DVContextAttr",
            "glb_Mlx5DevxObj = glb_mlx5dv.Mlx5DevxObj",
            "glb_Mlx5UMEM = glb_mlx5dv.Mlx5UMEM",
            # 创建 Mlx5Context（QUERY_CONG_STATISTICS 直接绑定 Context）
            f"glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), "
            f"'{cls._rdma_dev}')",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'初始化 DevX QUERY_CONG_STATISTICS 测试环境失败, '
                    f'dev={cls._rdma_dev}, cmd={cmd}, rtn={result}')
                return

    @classmethod
    def do(cls) -> None:
        log.info('do: DevX QUERY_CONG_STATISTICS 测试。')
        cls._do_abnormal_bad_opcode()

    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 QUERY_CONG_STATISTICS 测试资源。')
        if cls._ipvbs is not None:
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    # ------------------------------------------------------------------ #
    #  QUERY_CONG_STATISTICS 操作辅助方法                                                     #
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
    def _send_qcs(cls, raw_expr=None, op_mod=0,
                   clear=0, var_suffix='',
                   ctx_ref='glb_mlx5_ctx') -> tuple:
        """下发 DevX QUERY_CONG_STATISTICS，返回 (qcs_status, syndrome_or_err)。

        raw_expr: 自定义 inbox 表达式（远端求值）；None 时按参数标准构造。
        完整 outbox 保留在远端 glb_ret<var_suffix>[2]，
        可通过 _fetch_out_len 取回其长度（避免回传大字节串）。
        """
        if raw_expr is None:
            cmd = (f"glb_ret{var_suffix} = glb_helper.query_cong_statistics("
                   f"{ctx_ref}, op_mod={op_mod}, "
                   f"clear={clear})")
        else:
            cmd = (f"glb_ret{var_suffix} = glb_helper.query_cong_statistics("
                   f"{ctx_ref}, raw={raw_expr})")
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
        if status != IpvbsStatusEnum.SUCCESS.value:
            return None, result
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"str(glb_ret{var_suffix}[:2])")
        if status != IpvbsStatusEnum.SUCCESS.value:
            return None, result
        try:
            qcs_status, qcs_syndrome = ast.literal_eval(result.strip())
        except Exception:
            return None, result
        return qcs_status, qcs_syndrome

    @classmethod
    def _fetch_out_len(cls, var_suffix='') -> int:
        """取回远端 outbox 长度（len(glb_ret<var_suffix>[2])）。"""
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f'len(glb_ret{var_suffix}[2])')
        if status != IpvbsStatusEnum.SUCCESS.value:
            return -1
        try:
            return int((result or '').strip())
        except Exception:
            return -1

    @classmethod
    def _fetch_var_str(cls, var: str) -> str:
        """取回远端变量字符串值。"""
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(f'str({var})')
        if status != IpvbsStatusEnum.SUCCESS.value:
            return ''
        return (result or '').strip()

    # ------------------------------------------------------------------ #
    #  检查点实现                                                          #
    # ------------------------------------------------------------------ #

    @classmethod
    def _do_abnormal_bad_opcode(cls) -> None:
        """检查点1: 非法 opcode=0x1 应被拒绝；检查点2: 标准
        QUERY_CONG_STATISTICS 不受影响。"""
        log.info('[CP1] 下发非法 opcode=0x1 的命令。')
        raw_expr = ("__import__('struct').pack('>HHHH', 0x1, 0, 0, 0) "
                    "+ b'\\x00' * 8")
        status, syndrome = cls._send_qcs(raw_expr=raw_expr, var_suffix='bad')
        if status is None:
            # Python 层异常（如内核 EINVAL 拒绝）也视为命令被拒绝，符合预期
            log.info(f'非法 opcode 按预期被拒绝（Python 层）: {syndrome}')
        elif status != 0:
            log.info(f'非法 opcode 按预期被固件拒绝: status={status}, '
                     f'syndrome={syndrome}')
        else:
            cls.set_bug_type('功能问题')
            cls.create_bug('非法 opcode=0x1 意外成功: status=0，'
                           '期望固件拒绝未定义 opcode。')
            return

        log.info('[CP2] 下发标准 QUERY_CONG_STATISTICS 对照。')
        status2, syndrome2 = cls._send_qcs(var_suffix='ctrl')
        if status2 is None:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'标准 QUERY_CONG_STATISTICS 对照远程执行异常: '
                           f'{syndrome2}')
            return
        if status2 != 0:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'标准 QUERY_CONG_STATISTICS 对照返回非 0 '
                           f'status: {status2}, syndrome={syndrome2}，'
                           f'期望 status=0。')
            return
        log.info('非法 opcode 被拒绝后命令通道未受影响，标准 '
                 'QUERY_CONG_STATISTICS 仍 status=0，校验通过。')

if __name__ == '__main__':
    NicLinuxRdmaDevxF0653015005PfAbnormalBadOpcodeQueryCongStatistics().run()
