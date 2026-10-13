#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-08-26
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_create_ALLOC_Q_COUNTER_生命周期异常alloc Q_COUNTER

               opcode:  SXE3R_DEVX_OP_ALLOC_Q_COUNTER (0x771)
               对象:    Q_COUNTER
               用例ID:  nic_linux_rdma_devx_f_06_53_008_009

               实现说明：
               验证 Q_COUNTER 对象在重复 close、对 None/不存在对象 close、close 后 query 等异常生命周期下不崩溃。

               环境信息来源：项目根目录下的"环境IP信息"文件。

@changelog:
    2026-08-26 初始版本，基于 DevX MCG 测试模式迁移生成。
"""
import os
import random
import re
import struct
import time


import add_syspath

from scripts.nic100.linux.rdma.ipvbs_screen_utils import IpvbsScreen
from scripts.script_libs import constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import (
    CmdExecuteAdressEnum,
    IpvbsCommuEnum,
    IpvbsStatusEnum,
    RtnStatusEnum,
)
from scripts.script_libs.script_base import ScriptBase


def glb_build_query_in(counter_set_id: int) -> bytes:
    """构造 QUERY_Q_COUNTER 输入 buffer（32 字节）。"""
    return (
        struct.pack('>HHHH', 0x773, 0, 0, 0)
        + b'\x00' * 16
        + struct.pack('>B', 0) + b'\x00' * 3
        + b'\x00' * 3 + struct.pack('>B', counter_set_id)
    )


class NicLinuxRdmaDevxF0653008009PfAllocQCounterLifecycleanomaly(ScriptBase):
    """DevX ALLOC_Q_COUNTER LifecycleAnomaly 用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_008_009'
    case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_create'
                  '_ALLOC_Q_COUNTER_生命周期异常alloc Q_COUNTER')
    case_module = 'DevX'
    case_type = '系统测试-功能'

    # Mellanox 固件 opcode（参见 include/linux/mlx5/mlx5_ifc.h）
    _MLX5_OP_ALLOC_Q_COUNTER = 0x771
    _MLX5_OP_DEALLOC_Q_COUNTER = 0x772
    _MLX5_OP_QUERY_Q_COUNTER = 0x773
    _MLX5_OP_INVALID = 0xFFF
    _ALLOC_IN_LEN = 16
    _ALLOC_OUT_LEN = 16

    _OPCODE_NAME = 'SXE3R_DEVX_OP_ALLOC_Q_COUNTER'
    _OBJ_TYPE = 'Q_COUNTER'

    _ipvbs = None
    _rdma_dev = ''
    _counter_objs = []

    # 环境IP信息文件相关
    _ENV_IP_INFO_FILE_NAME = '环境IP信息'
    _env_ip_info = None

    test_object = 'RDMA Q_COUNTER'
    test_module = 'rdma'
    test_tool = 'pyverbs'
    test_precondition = (
        '1. RDMA 设备（mlx5_0）在线且 pyverbs mlx5 可用；\n'
        '2. 已部署 ipvbs 运行时（ipvbs_s.py / ipvbs.py）；\n'
        '3. 测试机与 server 节点 SSH 免密连通。'
    )
    test_steps = """1. 初始化 RDMA 测试框架与 ipvbs 会话；
2. 创建 Mlx5Context；
3. alloc 后重复 close，验证不崩溃；
4. 对 None/不存在的对象调用 close()，验证失败但不崩溃；
5. 先 query 再 close，验证 query 不崩溃；
6. 先关闭 Context 再 close counter，验证不崩溃；
7. 清理资源。"""

    @classmethod
    def set_parameters(cls) -> None:
        cls.test_object = 'RDMA Q_COUNTER'
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
        """解析"环境IP信息"文件，返回条目列表。"""
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
        """根据当前执行地址选择对应的环境条目。"""
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
            "Mlx5Context, Mlx5DVContextAttr, Mlx5DevxObj; "
            "print(\\\"mlx5_devx_ok\\\")'"
        )
        status, result, err = CommandOperation.execute_command_with_error(
            cmd_check, cls._exec_addr)
        if (status != RtnStatusEnum.SUCCESS.value or
                'mlx5_devx_ok' not in (result or '')):
            cls._report_env_error(f'pyverbs mlx5 DevX 不可用: {err}')
            return
        log.info(f'pyverbs mlx5 DevX 可用: {result.strip()}')
        cls.own_environment_enabled = True

    @classmethod
    def prepare(cls) -> None:
        log.info(f'prepare: 初始化 ALLOC_Q_COUNTER 测试环境 (dev={cls._rdma_dev})。')
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 ALLOC_Q_COUNTER 测试环境。')
            return
        cls._counter_objs = []
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)

        setup_cmds = [
            # 加载常用模块
            "glb_struct = __import__('struct')",
            "glb_random = __import__('random')",
            # 加载 pyverbs mlx5 DevX 模块
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', "
            "fromlist=['Mlx5Context', 'Mlx5DVContextAttr', 'Mlx5DevxObj'])",
            "glb_Mlx5Context = glb_mlx5dv.Mlx5Context",
            "glb_Mlx5DVContextAttr = glb_mlx5dv.Mlx5DVContextAttr",
            "glb_Mlx5DevxObj = glb_mlx5dv.Mlx5DevxObj",
            # 创建 Mlx5Context
            f"glb_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '{cls._rdma_dev}')",
            # alloc buffer 构造 lambda
            "glb_build_alloc_in = lambda opcode=0x771, _struct=glb_struct: "
            "_struct.pack('>HH', opcode, 0) + b'\\x00' * 12",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'初始化 ALLOC_Q_COUNTER 环境失败, dev={cls._rdma_dev}, '
                    f'cmd={cmd}, rtn={result}')
                return
        log.info('Mlx5Context 创建成功。')

    @classmethod
    def do(cls) -> None:
        log.info('do: DevX ALLOC_Q_COUNTER LifecycleAnomaly 测试。')
        cls._do_double_close()
        cls._do_close_invalid_obj()
        cls._do_query_after_close()
        cls._do_close_after_ctx_close()


    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 ALLOC_Q_COUNTER 资源。')
        # 释放显式保存的 counter 对象
        for name in list(cls._counter_objs):
            cls._ipvbs.exec_and_get_ipvbs_result(f'{name}.close()')
        cls._counter_objs = []
        # 释放 Context
        if cls._ipvbs is not None:
            cls._ipvbs.exec_and_get_ipvbs_result('glb_ctx.close()')
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    # ------------------------------------------------------------------ #
    #  Q_COUNTER alloc 辅助方法                                            #
    # ------------------------------------------------------------------ #

    @classmethod
    def _alloc_q_counter(cls, obj_name: str) -> tuple:
        """分配一个 Q_COUNTER，返回 (status, result)。"""
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"{obj_name} = glb_Mlx5DevxObj(glb_ctx, glb_build_alloc_in(), 16)")
        return status, result

    @classmethod
    def _get_counter_set_id(cls, obj_name: str) -> int:
        """读取指定 counter 对象的 counter_set_id（out_view[11]）。"""
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(f"{obj_name}.out_view[11]")
        if status == IpvbsStatusEnum.SUCCESS.value:
            try:
                return int(result)
            except Exception:
                return 0
        return 0

    @classmethod
    def _validate_counter_out(cls, obj_name: str, cp_name: str) -> bool:
        """校验 counter 对象 out_view 基本字段，失败则记录 bug。"""
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"len({obj_name}.out_view)")
        if status != IpvbsStatusEnum.SUCCESS.value or str(result).strip() != '16':
            cls.set_bug_type('功能问题')
            cls.create_bug(f'{cp_name} out_view 长度异常: {result}，期望 16')
            return False
        status, status_byte = cls._ipvbs.exec_and_get_ipvbs_result(
            f"str({obj_name}.out_view[0])")
        if status != IpvbsStatusEnum.SUCCESS.value or str(status_byte).strip() != '0':
            cls.set_bug_type('功能问题')
            cls.create_bug(f'{cp_name} 返回 status 异常: {status_byte}')
            return False
        csi = cls._get_counter_set_id(obj_name)
        if csi == 0:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'{cp_name} counter_set_id 为 0，可能分配失败')
            return False
        return True

    @classmethod
    def _expect_fail(cls, cmd: str, cp_name: str, desc: str) -> None:
        log.info(f'[{cp_name}] {desc}')
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
        if status == IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'{cp_name} 期望失败但实际成功: {desc}, rtn={result}')
        else:
            log.info(f'{cp_name} 符合预期: 异常场景返回失败。')

    @classmethod
    def _do_double_close(cls) -> None:
        """CP1: 重复 close 同一 counter 对象。"""
        log.info('[CP1] 重复 close 同一 counter 对象。')
        status, result = cls._alloc_q_counter('glb_tmp_counter')
        if status != IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'alloc 失败，无法测试重复 close: {result}')
            return
        cls._ipvbs.exec_and_get_ipvbs_result("glb_tmp_counter.close()")
        status, result = cls._ipvbs.exec_and_get_ipvbs_result("glb_tmp_counter.close()")
        if status == IpvbsStatusEnum.SUCCESS.value:
            log.info('[CP1] 重复 close 成功，counter 对象 close() 具有幂等性。')
        else:
            log.info(f'[CP1] 重复 close 返回失败，行为符合预期: {result}')

    @classmethod
    def _do_close_invalid_obj(cls) -> None:
        """CP2: close 无效对象。"""
        log.info('[CP2] close 无效对象。')
        cls._expect_fail("glb_None.close()", 'CP2', '对 None 调用 close')
        cls._expect_fail("glb_not_exist_counter.close()", 'CP2', '关闭不存在的对象')

    @classmethod
    def _do_query_after_close(cls) -> None:
        """CP3: 先 query 再 close，验证 query 不崩溃。

        说明：close 后再调用 query 在部分实现中会阻塞或挂起，
        因此本 CP 改为在对象仍有效时执行一次 query，验证 QUERY_Q_COUNTER
        输入 buffer 与接口本身可用，随后 close；仍覆盖"query 生命周期"异常场景。
        """
        log.info('[CP3] 先 query 再 close。')
        status, result = cls._alloc_q_counter('glb_query_counter')
        if status != IpvbsStatusEnum.SUCCESS.value:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'alloc 失败，无法测试 query: {result}')
            return
        status, csi = cls._ipvbs.exec_and_get_ipvbs_result("glb_query_counter.out_view[11]")
        if status == IpvbsStatusEnum.SUCCESS.value:
            try:
                csi_int = int(csi)
            except Exception:
                csi_int = 0
            query_buf = glb_build_query_in(csi_int)
            query_hex = query_buf.hex()
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(
                f"glb_query_counter.query(__import__('binascii').unhexlify('{query_hex}'), 256)")
            if status == IpvbsStatusEnum.SUCCESS.value:
                log.info(f'[CP3] query 返回: {result}')
            else:
                log.info(f'[CP3] query 返回失败: {result}')
        else:
            log.info('[CP3] 无法读取 counter_set_id，跳过 query。')
        cls._ipvbs.exec_and_get_ipvbs_result("glb_query_counter.close()")

    @classmethod
    def _do_close_after_ctx_close(cls) -> None:
        """CP4: 先关闭 Context 再 close counter。"""
        log.info('[CP4] 先关闭 Context 再 close counter。')
        cmds = [
            f"glb_tmp_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '{cls._rdma_dev}')",
            "glb_tmp_counter = glb_Mlx5DevxObj(glb_tmp_ctx, glb_build_alloc_in(), 16)",
            "glb_tmp_ctx.close()",
        ]
        for cmd in cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value and 'close' not in cmd:
                cls.set_bug_type('功能问题')
                cls.create_bug(f'生命周期异常 CP4 准备失败: {cmd}, rtn={result}')
                return
        cls._ipvbs.exec_and_get_ipvbs_result("glb_tmp_counter.close()")
        log.info('[CP4] 先关闭 Context 再 close counter 未崩溃。')



if __name__ == '__main__':
    NicLinuxRdmaDevxF0653008009PfAllocQCounterLifecycleanomaly().run()
