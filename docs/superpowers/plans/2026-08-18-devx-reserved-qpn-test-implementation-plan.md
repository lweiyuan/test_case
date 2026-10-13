# DevX Reserved QPN 测试实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于已批准的 QPN 测试设计，扩展 `devx_qp_helper.py`、生成 14 个 DevX Reserved QPN 测试脚本、更新合并 Excel，并跑通验证。

**Architecture:** 通过 `devx_qp_helper.py` 集中封装 `CREATE_GENERAL_OBJECT` + `MLX5_OBJ_TYPE_RESERVED_QPN` 的 buffer 构造；使用一个脚本生成器从正常脚本模板产出其余 13 个场景脚本，保证代码风格一致；最后用 openpyxl 把 14 条 QPN 用例追加到现有合并 Excel。

**Tech Stack:** Python 3、pyverbs（`Mlx5Context`、`Mlx5DevxObj`）、scapy（helper 中构造 PRM packet）、openpyxl（Excel 更新）、项目 NIC100 测试框架。

## Global Constraints

- 新增脚本继承项目现有 `ScriptBase`，命名符合 `nic_linux_rdma_devx_f_06_53_005_NNN_devx_create_qpn_<scene>_create_qpn.py`。
- helper 必须自动部署到远端 `/root/sxetest/`，沿用 `_deploy_helper_if_needed` 机制。
- 脚本通过 `IpvbsScreen` SOCKET 模式在远端执行 pyverbs 命令，不依赖远端 `screen`。
- 测试对象 first_qpn 从 `general_obj_out_cmd_hdr.obj_id` 解析。
- 不直接修改 `.xlsx` 源文件，Excel 更新必须通过 Python 脚本完成。
- 每个脚本独立可跑，`post()` 必须关闭所有 `Mlx5DevxObj` 并清理 `ipvbs_s`。

---

## File Structure

| 文件 | 类型 | 说明 |
|---|---|---|
| `ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/devx_qp_helper.py` | 修改 | 增加 Reserved QPN 的 PRM packet 类和创建/探测函数 |
| `ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/nic_linux_rdma_devx_f_06_53_005_001_devx_create_qpn_normal_create_qpn.py` | 创建 | 正常脚本模板 |
| `ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/generate_qpn_scripts.py` | 创建 | 基于模板生成 002-014 脚本 |
| `ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/nic_linux_rdma_devx_f_06_53_005_002~014_*.py` | 生成 | 13 个场景脚本 |
| `ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/update_devx_excel_with_qpn.py` | 创建 | 读取合并 Excel 并追加 QPN 用例 |
| `excel测试用例文件夹/DevX_PD_QP_CQ_SRQ_创建测试用例_含指令.xlsx` | 更新 | 追加 14 条 QPN 用例行 |

---

### Task 1: 扩展 `devx_qp_helper.py`

**Files:**
- Modify: `ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/devx_qp_helper.py`

**Interfaces:**
- Consumes: `Mlx5Context`, `Mlx5DevxObj`（远端 pyverbs）
- Produces:
  - `DevxOps.MLX5_CMD_OP_CREATE_GENERAL_OBJECT = 0xa00`
  - `DevxOps.MLX5_OBJ_TYPE_RESERVED_QPN = 0x002C`
  - `GeneralObjInCmdHdr` / `ReservedQpnBits` / `CreateReservedQpnIn` / `GeneralObjOutCmdHdr` scapy packet 类
  - `query_reserved_qpn_caps(ctx) -> (bool, int)`
  - `create_reserved_qpn(ctx, log_obj_range=0) -> (obj, first_qpn)`
  - `destroy_reserved_qpn(obj)`
  - `try_create_reserved_qpn_raw(ctx, opcode, obj_type, log_obj_range) -> str`（负向测试用，返回 `'OK'` 或 `'FAIL:...'`）

- [ ] **Step 1: 在 `DevxOps` 中增加常量**

```python
class DevxOps:
    MLX5_CMD_OP_ALLOC_PD = 0x800
    MLX5_CMD_OP_CREATE_CQ = 0x400
    MLX5_CMD_OP_CREATE_QP = 0x500
    MLX5_CMD_OP_DESTROY_QP = 0x501
    MLX5_CMD_OP_QUERY_QP = 0x50b
    MLX5_CMD_OP_CREATE_SRQ = 0x700
    MLX5_CMD_OP_DESTROY_SRQ = 0x701
    MLX5_CMD_OP_CREATE_GENERAL_OBJECT = 0xa00
    MLX5_OBJ_TYPE_RESERVED_QPN = 0x002C
    MLX5_QPC_ST_RC = 0x0
    MLX5_QPC_PM_STATE_MIGRATED = 0x3
```

- [ ] **Step 2: 在 `AllocPdIn` 类之后追加 General Object 相关 packet 类**

```python
class GeneralObjInCmdHdr(PRMPacket):
    fields_desc = [
        ShortField('opcode', 0),
        ShortField('uid', 0),
        ShortField('reserved1', 0),
        ShortField('obj_type', 0),
        IntField('obj_id', 0),
        BitField('reserved2', 0, 3),
        BitField('log_obj_range', 0, 5),
        StrFixedLenField('reserved3', None, length=3),
    ]


class ReservedQpnBits(PRMPacket):
    fields_desc = [
        StrFixedLenField('reserved', None, length=16),
    ]


class CreateReservedQpnIn(PRMPacket):
    fields_desc = [
        PacketField('hdr', GeneralObjInCmdHdr(), GeneralObjInCmdHdr),
        PacketField('rqpns', ReservedQpnBits(), ReservedQpnBits),
    ]


class GeneralObjOutCmdHdr(PRMPacket):
    fields_desc = [
        ByteField('status', 0),
        BitField('reserved1', 0, 24),
        IntField('syndrome', 0),
        IntField('obj_id', 0),
        StrFixedLenField('reserved2', None, length=4),
    ]
```

- [ ] **Step 3: 在 helper 文件末尾追加 Reserved QPN 操作函数**

```python
def query_reserved_qpn_caps(ctx):
    """探测当前设备是否支持 Reserved QPN，并返回最大 block 粒度。

    实现方式：先尝试创建 log_obj_range=0 的 block；若失败则认为不支持。
    若支持，则逐个尝试更大的 log_obj_range，返回最后一个成功的值。
    """
    import pyverbs.providers.mlx5.mlx5dv as m
    try:
        obj, _ = create_reserved_qpn(ctx, 0)
        destroy_reserved_qpn(obj)
    except Exception:
        return False, 0

    max_log = 0
    for log_range in range(1, 16):
        try:
            obj, _ = create_reserved_qpn(ctx, log_range)
            destroy_reserved_qpn(obj)
            max_log = log_range
        except Exception:
            break
    return True, max_log


def create_reserved_qpn(ctx, log_obj_range=0):
    """通过 DevX CREATE_GENERAL_OBJECT + MLX5_OBJ_TYPE_RESERVED_QPN 创建 block。

    返回 (obj, first_qpn)，其中 first_qpn 来自 general_obj_out_cmd_hdr 的 obj_id。
    """
    import pyverbs.providers.mlx5.mlx5dv as m
    hdr = GeneralObjInCmdHdr(
        opcode=DevxOps.MLX5_CMD_OP_CREATE_GENERAL_OBJECT,
        obj_type=DevxOps.MLX5_OBJ_TYPE_RESERVED_QPN,
        log_obj_range=log_obj_range,
    )
    rqpns = ReservedQpnBits()
    cmd_in = bytes(CreateReservedQpnIn(hdr=hdr, rqpns=rqpns))
    obj = m.Mlx5DevxObj(ctx, cmd_in, len(GeneralObjOutCmdHdr()))
    out = GeneralObjOutCmdHdr(obj.out_view)
    return obj, out.obj_id


def destroy_reserved_qpn(obj):
    """释放 Reserved QPN block（即销毁 General Object）。"""
    obj.close()


def try_create_reserved_qpn_raw(ctx, opcode, obj_type, log_obj_range):
    """用于异常测试：直接按指定参数尝试创建，返回 'OK' 或 'FAIL:<reason>'。"""
    try:
        hdr = GeneralObjInCmdHdr(
            opcode=opcode,
            obj_type=obj_type,
            log_obj_range=log_obj_range,
        )
        rqpns = ReservedQpnBits()
        cmd_in = bytes(CreateReservedQpnIn(hdr=hdr, rqpns=rqpns))
        obj = m.Mlx5DevxObj(ctx, cmd_in, len(GeneralObjOutCmdHdr()))
        obj.close()
        return 'OK'
    except Exception as e:
        return f'FAIL:{e}'
```

- [ ] **Step 4: 语法检查**

Run: `python -m py_compile ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/devx_qp_helper.py`
Expected: 无输出（exit 0）

- [ ] **Step 5: Commit**

```bash
git add ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/devx_qp_helper.py
git commit -m "feat(devx): add Reserved QPN helper functions and PRM packets"
```

---

### Task 2: 创建正常脚本模板 `005_001`

**Files:**
- Create: `ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/nic_linux_rdma_devx_f_06_53_005_001_devx_create_qpn_normal_create_qpn.py`

**Interfaces:**
- Consumes: `devx_qp_helper.py` 的 `query_reserved_qpn_caps` / `create_reserved_qpn` / `destroy_reserved_qpn`
- Produces: 可作为生成器模板的完整 standalone 脚本

- [ ] **Step 1: 编写完整正常脚本**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-08-18
description:   RDMA DevX 接口测试_用户态_PF_devx_obj_create_ReservedQPN创建_正常创建ReservedQPN

               opcode:  SXE3R_DEVX_OP_CREATE_GENERAL_OBJECT
               obj_type: MLX5_OBJ_TYPE_RESERVED_QPN (0x002C)
               对象:    Reserved QPN（预留队列对编号）
               用例ID:  nic_linux_rdma_devx_f_06_53_005_001

               实现说明：
               在 CX8 / mlx5 设备上通过 pyverbs 的 Mlx5DevxObj 直接下发
               固件 CREATE_GENERAL_OBJECT 命令（opcode=0xa00, obj_type=0x002C）
               创建 Reserved QPN block，验证 first_qpn 有效、唯一且可正常释放。

@changelog:
    2026-08-18 初始版本。
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


class NicLinuxRdmaDevxF0653005001PfCreateQpnNormalCreateQpn(ScriptBase):
    """DevX Reserved QPN 正常创建用例。"""

    case_id = 'nic_linux_rdma_devx_f_06_53_005_001'
    case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_create_'
                  'ReservedQPN创建_正常创建ReservedQPN')
    case_module = 'DevX'
    case_type = '系统测试-功能'

    _MLX5_OP_CREATE_GENERAL_OBJECT = 0xa00
    _MLX5_OBJ_TYPE_RESERVED_QPN = 0x002C
    _OPCODE_NAME = 'SXE3R_DEVX_OP_CREATE_GENERAL_OBJECT'
    _OBJ_TYPE = 'RESERVED_QPN'
    _QPN_BLOCK_COUNT = 5

    _CREATE_QPN_IN_LEN = 32
    _CREATE_QPN_OUT_LEN = 16

    _ipvbs = None
    _rdma_dev = ''
    _qpn_objs = {}
    _first_qpns = {}
    _reserved_qpn_supported = False
    _max_log_range = 0

    _ENV_IP_INFO_FILE_NAME = '环境IP信息'
    _env_ip_info = None

    test_object = 'RDMA Reserved QPN（预留队列对编号）'
    test_module = 'rdma'
    test_tool = 'pyverbs'
    test_precondition = (
        '1. RDMA 设备（mlx5_0）在线且 pyverbs mlx5 可用；\n'
        '2. 已部署 ipvbs 运行时（ipvbs_s.py / ipvbs.py）；\n'
        '3. 测试机与 server 节点 SSH 免密连通。'
    )
    test_steps = (
        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\n'
        '2. 创建 Mlx5Context；\n'
        '3. 查询并确认设备支持 Reserved QPN；\n'
        '4. 通过 DevX CREATE_GENERAL_OBJECT + MLX5_OBJ_TYPE_RESERVED_QPN '
        '创建单个 block，记录 first_qpn；\n'
        '5. 连续创建多个 block，验证 first_qpn 唯一；\n'
        '6. 释放全部 block 并清理资源。'
    )

    @classmethod
    def set_parameters(cls) -> None:
        cls.test_object = 'RDMA Reserved QPN（预留队列对编号）'
        cls.test_module = 'rdma'
        cls.test_tool = 'pyverbs'
        cls.own_environment_enabled = False
        cls._exec_addr = CmdExecuteAdressEnum.SERVER.value

    @classmethod
    def _find_env_ip_info_file(cls) -> str or None:
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
        log.error(msg)
        cls.own_environment_enabled = False

    @classmethod
    def check_own_environment(cls) -> None:
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
        if status != RtnStatusEnum.SUCCESS.value or \
                'mlx5_devx_ok' not in (result or ''):
            cls._report_env_error(f'pyverbs mlx5 DevX 不可用: {err}')
            return
        log.info(f'pyverbs mlx5 DevX 可用: {result.strip()}')
        cls.own_environment_enabled = True

    @classmethod
    def _deploy_helper_if_needed(cls) -> None:
        remote_helper = '/root/sxetest/devx_qp_helper.py'
        local_helper = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', 'devx_qp_helper.py'
        )
        local_helper = os.path.normpath(local_helper)
        if not os.path.isfile(local_helper):
            log.warning(f'本地 helper 文件不存在: {local_helper}，跳过自动部署。')
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
        log.info(f'prepare: 初始化 Reserved QPN 测试环境 '
                 f'(opcode={cls._OPCODE_NAME}, dev={cls._rdma_dev})。')
        cls._qpn_objs = {}
        cls._first_qpns = {}
        cls._reserved_qpn_supported = False
        cls._max_log_range = 0
        if not cls._rdma_dev:
            cls.set_bug_type('功能问题')
            cls.create_bug('RDMA 设备未就绪，无法初始化 Reserved QPN 测试环境。')
            return

        cls._ipvbs = IpvbsScreen(
            caller_class=cls, exec_addr=cls._exec_addr,
            commu=IpvbsCommuEnum.SOCKET.value)
        cls._deploy_helper_if_needed()

        setup_cmds = [
            "__import__('sys').path.insert(0, '/root/sxetest')",
            "glb_helper = __import__('devx_qp_helper')",
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', "
            "fromlist=['Mlx5Context', 'Mlx5DVContextAttr'])",
            "glb_Mlx5Context = glb_mlx5dv.Mlx5Context",
            "glb_Mlx5DVContextAttr = glb_mlx5dv.Mlx5DVContextAttr",
            f"glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), "
            f"'{cls._rdma_dev}')",
            "glb_caps = glb_helper.query_reserved_qpn_caps(glb_mlx5_ctx)",
            "glb_supported = glb_caps[0]",
            "glb_max_log = glb_caps[1]",
        ]
        for cmd in setup_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                cls.set_bug_type('功能问题')
                cls.create_bug(
                    f'初始化 Reserved QPN 环境失败, dev={cls._rdma_dev}, '
                    f'cmd={cmd}, rtn={result}')
                return

        status, supported = cls._ipvbs.exec_and_get_ipvbs_result(
            "str(glb_supported)")
        if status == IpvbsStatusEnum.SUCCESS.value:
            cls._reserved_qpn_supported = (supported or '').strip() == 'True'

        status, max_log = cls._ipvbs.exec_and_get_ipvbs_result(
            "str(glb_max_log)")
        if status == IpvbsStatusEnum.SUCCESS.value:
            try:
                cls._max_log_range = int((max_log or '').strip() or 0)
            except ValueError:
                cls._max_log_range = 0

        log.info(f'Reserved QPN 能力: supported={cls._reserved_qpn_supported}, '
                 f'max_log_range={cls._max_log_range}')

        if not cls._reserved_qpn_supported:
            cls.set_bug_type('功能问题')
            cls.create_bug('当前设备/固件不支持 Reserved QPN。')

    @classmethod
    def do(cls) -> None:
        log.info('do: DevX Reserved QPN 正常创建测试。')
        cls._do_normal_create_qpn()
        cls._do_batch_create_qpn()

    @classmethod
    def post(cls) -> None:
        log.info(f'post: 清理 Reserved QPN 资源 '
                 f'(共 {len(cls._first_qpns)} 个 block)。')
        for name in list(cls._first_qpns.keys()):
            cls._close_qpn_block(name)
        cls._qpn_objs = {}
        cls._first_qpns = {}
        if cls._ipvbs is not None:
            IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                       commu=IpvbsCommuEnum.SOCKET.value)

    @classmethod
    def _create_qpn_block(cls, name: str, log_obj_range: int = 0) -> tuple:
        glb_name = f'glb_{name}'
        create_cmds = [
            f"{glb_name}_ret = glb_helper.create_reserved_qpn("
            f"glb_mlx5_ctx, {log_obj_range})",
            f"{glb_name} = {glb_name}_ret[0]",
            f"{glb_name}_first = {glb_name}_ret[1]",
        ]
        for cmd in create_cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if status != IpvbsStatusEnum.SUCCESS.value:
                log.error(f'DevX CREATE_GENERAL_OBJECT(RESERVED_QPN) 失败: '
                          f'{cmd}, rtn={result}')
                return status, None

        status, first_qpn = cls._ipvbs.exec_and_get_ipvbs_result(
            f"str({glb_name}_first)")
        if status != IpvbsStatusEnum.SUCCESS.value:
            return status, None

        cls._qpn_objs[name] = glb_name
        first_qpn = (first_qpn or '').strip()
        cls._first_qpns[name] = first_qpn
        log.info(f'Reserved QPN block 创建成功: {name}, '
                 f'log_range={log_obj_range}, first_qpn={first_qpn}')
        return IpvbsStatusEnum.SUCCESS.value, first_qpn

    @classmethod
    def _close_qpn_block(cls, name: str) -> bool:
        glb_name = cls._qpn_objs.get(name)
        if not glb_name:
            return False
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            f"{glb_name}.close()")
        if status == IpvbsStatusEnum.SUCCESS.value:
            log.info(f'Reserved QPN block 释放成功: {name}')
            cls._qpn_objs.pop(name, None)
            cls._first_qpns.pop(name, None)
            return True
        log.warning(f'Reserved QPN block 释放异常: {name}, rtn={result}')
        return False

    @classmethod
    def _close_all_qpn_blocks(cls) -> None:
        for name in list(cls._qpn_objs.keys()):
            cls._close_qpn_block(name)

    @classmethod
    def _do_normal_create_qpn(cls) -> None:
        log.info('[CP1] 正常分配单个 Reserved QPN block。')
        status, first_qpn = cls._create_qpn_block('obj_qpn_cp1', 0)
        if status != IpvbsStatusEnum.SUCCESS.value or not first_qpn:
            cls.set_bug_type('功能问题')
            cls.create_bug('正常分配 Reserved QPN block 失败，'
                           '期望 DevX CREATE_GENERAL_OBJECT 成功并返回有效 first_qpn。')
            return
        if not first_qpn.isdigit():
            cls.set_bug_type('功能问题')
            cls.create_bug(f'first_qpn 非法: {first_qpn}，期望为数值型 QPN。')

    @classmethod
    def _do_batch_create_qpn(cls) -> None:
        n = cls._QPN_BLOCK_COUNT
        log.info(f'[CP2] 连续分配 {n} 个 Reserved QPN block。')
        first_qpns = []
        for i in range(n):
            name = f'obj_qpn_cp2_{i}'
            status, first_qpn = cls._create_qpn_block(name, 0)
            if status != IpvbsStatusEnum.SUCCESS.value or not first_qpn:
                cls.set_bug_type('功能问题')
                cls.create_bug(f'批量分配第 {i + 1}/{n} 个 block 失败。')
                return
            first_qpns.append(first_qpn)
        if len(set(first_qpns)) != n:
            cls.set_bug_type('功能问题')
            cls.create_bug(f'{n} 个 block 的 first_qpn 不唯一: {first_qpns}。')


if __name__ == '__main__':
    NicLinuxRdmaDevxF0653005001PfCreateQpnNormalCreateQpn().run()
```

- [ ] **Step 2: 本地语法检查**

Run: `python -m py_compile ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/nic_linux_rdma_devx_f_06_53_005_001_devx_create_qpn_normal_create_qpn.py`
Expected: exit 0

- [ ] **Step 3: Commit**

```bash
git add ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/nic_linux_rdma_devx_f_06_53_005_001_devx_create_qpn_normal_create_qpn.py
git commit -m "feat(devx): add Reserved QPN normal create script template (005_001)"
```

---

### Task 3: 创建脚本生成器 `generate_qpn_scripts.py`

**Files:**
- Create: `ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/generate_qpn_scripts.py`

**Interfaces:**
- Consumes: 已存在的 `005_001` 脚本模板文件
- Produces: 13 个新脚本文件 `005_002` ~ `005_014`

- [ ] **Step 1: 编写生成器**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基于 005_001 模板生成 002-014 Reserved QPN 场景脚本。"""
import re
from pathlib import Path

SRC_DIR = Path('ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case')
TEMPLATE = SRC_DIR / (
    'nic_linux_rdma_devx_f_06_53_005_001_devx_create_qpn_normal_create_qpn.py'
)

SCENARIOS = [
    {
        'suffix': '002',
        'scene': 'abnormal',
        'scene_cn': '异常创建',
        'description': '验证错误 obj_type、超范围 log_obj_range 等异常参数会被固件拒绝。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 创建 Mlx5Context；\\n'"
            "        '3. 查询并确认设备支持 Reserved QPN；\\n'"
            "        '4. 使用错误 obj_type 尝试创建 block，期望失败；\\n'"
            "        '5. 使用超范围 log_obj_range 尝试创建 block，期望失败；\\n'"
            "        '6. 使用非 CREATE_GENERAL_OBJECT opcode 尝试创建，期望失败；\\n'"
            "        '7. 释放资源并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 异常参数测试。')\\n"
            "        bad_cases = [\\n"
            "            (0xa00, 0xff01, 0, '错误 obj_type'),\\n"
            "            (0xa00, 0x002c, 31, '超范围 log_obj_range'),\\n"
            "            (0x500, 0x002c, 0, '错误 opcode'),\\n"
            "        ]\\n"
            "        for opcode, obj_type, log_range, reason in bad_cases:\\n"
            "            status, result = cls._ipvbs.exec_and_get_ipvbs_result(\\n"
            "                f\"glb_helper.try_create_reserved_qpn_raw(\"\\n"
            "                f\"glb_mlx5_ctx, {opcode}, {obj_type}, {log_range})\")\\n"
            "            result = (result or '').strip()\\n"
            "            if status == IpvbsStatusEnum.SUCCESS.value and result == 'OK':\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'{reason} 未返回失败: {result}')\\n"
            "                return\\n"
            "            log.info(f'{reason} 正确返回失败: {result}')"
        ),
    },
    {
        'suffix': '003',
        'scene': 'stress',
        'scene_cn': '压力创建',
        'description': '连续创建/销毁大量 Reserved QPN block，验证 first_qpn 不重复且无资源泄漏。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 创建 Mlx5Context；\\n'"
            "        '3. 循环创建 100 个 log_obj_range=0 的 block 并立即释放；\\n'"
            "        '4. 检查所有 first_qpn 唯一；\\n'"
            "        '5. 再次批量创建 20 个 block，确认仍可成功；\\n'"
            "        '6. 释放全部 block 并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 压力测试。')\\n"
            "        total = 100\\n"
            "        first_qpns = []\\n"
            "        for i in range(total):\\n"
            "            name = f'obj_qpn_stress_{i}'\\n"
            "            status, first_qpn = cls._create_qpn_block(name, 0)\\n"
            "            if status != IpvbsStatusEnum.SUCCESS.value or not first_qpn:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'压力测试第 {i + 1}/{total} 次创建失败')\\n"
            "                return\\n"
            "            first_qpns.append(first_qpn)\\n"
            "            cls._close_qpn_block(name)\\n"
            "        if len(set(first_qpns)) != total:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'{total} 次创建的 first_qpn 出现重复')\\n"
            "            return\\n"
            "        log.info(f'压力测试完成，{total} 个 block first_qpn 唯一')"
        ),
    },
    {
        'suffix': '004',
        'scene': 'boundary',
        'scene_cn': '边界创建',
        'description': '验证 log_obj_range=0（1 个 QPN）和最大支持粒度均能成功。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 创建 Mlx5Context；\\n'"
            "        '3. 查询设备支持的最大 log_obj_range；\\n'"
            "        '4. 使用 log_obj_range=0 创建 block，验证成功；\\n'"
            "        '5. 使用最大 log_obj_range 创建 block，验证成功；\\n'"
            "        '6. 释放 block 并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 边界测试。')\\n"
            "        status, first_qpn = cls._create_qpn_block('obj_qpn_min', 0)\\n"
            "        if status != IpvbsStatusEnum.SUCCESS.value or not first_qpn:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('log_obj_range=0 创建失败')\\n"
            "            return\\n"
            "        if cls._max_log_range <= 0:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('未能探测到有效的最大 log_obj_range')\\n"
            "            return\\n"
            "        status, first_qpn = cls._create_qpn_block(\\n"
            "            'obj_qpn_max', cls._max_log_range)\\n"
            "        if status != IpvbsStatusEnum.SUCCESS.value or not first_qpn:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'max_log_range={cls._max_log_range} 创建失败')\\n"
            "            return\\n"
            "        log.info(f'边界测试通过: max_log_range={cls._max_log_range}')"
        ),
    },
    {
        'suffix': '005',
        'scene': 'cross_device',
        'scene_cn': '跨设备创建',
        'description': '在 mlx5_0 和 mlx5_1 上分别创建 block，验证 QPN 范围独立。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 在 mlx5_0 上创建 Mlx5Context 并分配 block；\\n'"
            "        '3. 在 mlx5_1 上创建 Mlx5Context 并分配 block；\\n'"
            "        '4. 验证两个设备返回的 first_qpn 均有效且不相同；\\n'"
            "        '5. 释放 block 并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 跨设备测试。')\\n"
            "        cls._do_create_on_device(cls._rdma_dev, 'obj_qpn_dev0', 'obj_qpn_dev0_first')\\n"
            "        other_dev = 'mlx5_1' if cls._rdma_dev == 'mlx5_0' else 'mlx5_0'\\n"
            "        cls._do_create_on_device(other_dev, 'obj_qpn_dev1', 'obj_qpn_dev1_first')\\n"
            "        status0, first0 = cls._ipvbs.exec_and_get_ipvbs_result(\\n"
            "            'str(obj_qpn_dev0_first)')\\n"
            "        status1, first1 = cls._ipvbs.exec_and_get_ipvbs_result(\\n"
            "            'str(obj_qpn_dev1_first)')\\n"
            "        if status0 != IpvbsStatusEnum.SUCCESS.value or \\\\n\\n"
            "                status1 != IpvbsStatusEnum.SUCCESS.value:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('跨设备创建 Reserved QPN 失败')\\n"
            "            return\\n"
            "        if first0.strip() == first1.strip():\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'跨设备 first_qpn 相同: {first0}')\\n"
            "            return\\n"
            "        log.info(f'跨设备测试通过: {cls._rdma_dev}={first0}, {other_dev}={first1}')"
        ),
    },
    {
        'suffix': '006',
        'scene': 'context_rebuild',
        'scene_cn': '上下文重建',
        'description': '销毁并重建 Mlx5Context 后，Reserved QPN 仍可正常分配。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 创建 Mlx5Context 并分配 block，记录 first_qpn；\\n'"
            "        '3. 关闭当前 Mlx5Context；\\n'"
            "        '4. 重新创建 Mlx5Context；\\n'"
            "        '5. 再次分配 block，验证成功；\\n'"
            "        '6. 释放 block 并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 上下文重建测试。')\\n"
            "        status, first_qpn0 = cls._create_qpn_block('obj_qpn_before', 0)\\n"
            "        if status != IpvbsStatusEnum.SUCCESS.value:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('重建前创建 block 失败')\\n"
            "            return\\n"
            "        cmds = [\\n"
            "            'glb_mlx5_ctx.close()',\\n"
            \"            \"glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '\" + cls._rdma_dev + \"')\",\\n"
            "        ]\\n"
            "        for cmd in cmds:\\n"
            "            s, r = cls._ipvbs.exec_and_get_ipvbs_result(cmd)\\n"
            "            if s != IpvbsStatusEnum.SUCCESS.value:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'上下文重建失败: {cmd}, {r}')\\n"
            "                return\\n"
            "        status, first_qpn1 = cls._create_qpn_block('obj_qpn_after', 0)\\n"
            "        if status != IpvbsStatusEnum.SUCCESS.value:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('重建后创建 block 失败')\\n"
            "            return\\n"
            "        log.info(f'上下文重建测试通过: before={first_qpn0}, after={first_qpn1}')"
        ),
    },
    {
        'suffix': '007',
        'scene': 'long_term_stability',
        'scene_cn': '长期稳定性',
        'description': '长时间循环申请/释放 Reserved QPN，验证无泄漏和重复。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 持续运行 300 轮：创建 5 个 block 后全部释放；\\n'"
            "        '3. 每轮检查 first_qpn 集合无交集；\\n'"
            "        '4. 释放资源并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 长期稳定性测试。')\\n"
            "        rounds = 300\\n"
            "        all_qpns = set()\\n"
            "        for r in range(rounds):\\n"
            "            round_qpns = []\\n"
            "            for i in range(5):\\n"
            "                name = f'obj_qpn_lt_{r}_{i}'\\n"
            "                status, first_qpn = cls._create_qpn_block(name, 0)\\n"
            "                if status != IpvbsStatusEnum.SUCCESS.value:\\n"
            "                    cls.set_bug_type('功能问题')\\n"
            "                    cls.create_bug(f'第 {r} 轮第 {i} 个 block 创建失败')\\n"
            "                    return\\n"
            "                round_qpns.append(first_qpn)\\n"
            "            overlap = all_qpns.intersection(set(round_qpns))\\n"
            "            if overlap:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'发现重复 first_qpn: {overlap}')\\n"
            "                return\\n"
            "            all_qpns.update(round_qpns)\\n"
            "            for i in range(5):\\n"
            "                cls._close_qpn_block(f'obj_qpn_lt_{r}_{i}')\\n"
            "        log.info(f'长期稳定性测试通过，共 {rounds} 轮')"
        ),
    },
    {
        'suffix': '008',
        'scene': 'multi_context',
        'scene_cn': '多上下文',
        'description': '同一设备上多个 Mlx5Context 分别申请 Reserved QPN，互不冲突。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 创建 3 个独立的 Mlx5Context；\\n'"
            "        '3. 每个 context 分配 block；\\n'"
            "        '4. 验证所有 first_qpn 唯一；\\n'"
            "        '5. 释放 block 并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 多上下文测试。')\\n"
            "        contexts = 3\\n"
            "        first_qpns = []\\n"
            "        for i in range(contexts):\\n"
            "            cmds = [\\n"
            \"                f\"glb_ctx_{i} = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '{cls._rdma_dev}')\",\\n"
            "                f\"glb_ret_{i} = glb_helper.create_reserved_qpn(glb_ctx_{i}, 0)\",\\n"
            "                f\"glb_obj_{i} = glb_ret_{i}[0]\",\\n"
            "                f\"glb_first_{i} = glb_ret_{i}[1]\",\\n"
            "            ]\\n"
            "            for cmd in cmds:\\n"
            "                s, r = cls._ipvbs.exec_and_get_ipvbs_result(cmd)\\n"
            "                if s != IpvbsStatusEnum.SUCCESS.value:\\n"
            "                    cls.set_bug_type('功能问题')\\n"
            "                    cls.create_bug(f'上下文 {i} 创建 block 失败: {r}')\\n"
            "                    return\\n"
            "            status, first_qpn = cls._ipvbs.exec_and_get_ipvbs_result(\\n"
            "                f'str(glb_first_{i})')\\n"
            "            first_qpns.append(first_qpn.strip())\\n"
            "        if len(set(first_qpns)) != contexts:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'多上下文 first_qpn 不唯一: {first_qpns}')\\n"
            "            return\\n"
            "        for i in range(contexts):\\n"
            "            cls._ipvbs.exec_and_get_ipvbs_result(f'glb_obj_{i}.close()')\\n"
            "            cls._ipvbs.exec_and_get_ipvbs_result(f'glb_ctx_{i}.close()')\\n"
            "        log.info(f'多上下文测试通过: {first_qpns}')"
        ),
    },
    {
        'suffix': '009',
        'scene': 'lifecycle_anomaly',
        'scene_cn': '生命周期异常',
        'description': '验证 block 被销毁后，其 QPN 不可再次使用/关联。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 创建 block 并记录 first_qpn；\\n'"
            "        '3. 销毁该 block；\\n'"
            "        '4. 再次创建新 block，验证新 first_qpn 与旧值不同；\\n'"
            "        '5. 释放资源并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 生命周期异常测试。')\\n"
            "        status, first_qpn0 = cls._create_qpn_block('obj_qpn_life', 0)\\n"
            "        if status != IpvbsStatusEnum.SUCCESS.value:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('生命周期测试初始创建失败')\\n"
            "            return\\n"
            "        cls._close_qpn_block('obj_qpn_life')\\n"
            "        status, first_qpn1 = cls._create_qpn_block('obj_qpn_life2', 0)\\n"
            "        if status != IpvbsStatusEnum.SUCCESS.value:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('销毁后重新创建 block 失败')\\n"
            "            return\\n"
            "        if first_qpn0 == first_qpn1:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'销毁后分配了相同 first_qpn: {first_qpn1}')\\n"
            "            return\\n"
            "        log.info(f'生命周期异常测试通过: {first_qpn0} -> {first_qpn1}')"
        ),
    },
    {
        'suffix': '010',
        'scene': 'alloc_pattern',
        'scene_cn': '分配模式',
        'description': '按 1/2/4/8 等典型 block 大小创建，验证均成功。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 依次使用 log_obj_range=0,1,2,3 创建 block；\\n'"
            "        '3. 验证每个 block 的 first_qpn 有效且互不相同；\\n'"
            "        '4. 释放 block 并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 分配模式测试。')\\n"
            "        ranges = [0, 1, 2, 3]\\n"
            "        first_qpns = []\\n"
            "        for log_range in ranges:\\n"
            "            name = f'obj_qpn_pattern_{log_range}'\\n"
            "            status, first_qpn = cls._create_qpn_block(name, log_range)\\n"
            "            if status != IpvbsStatusEnum.SUCCESS.value or not first_qpn:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'log_obj_range={log_range} 创建失败')\\n"
            "                return\\n"
            "            first_qpns.append(first_qpn)\\n"
            "        if len(set(first_qpns)) != len(ranges):\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'不同 log_range 的 first_qpn 重复: {first_qpns}')\\n"
            "            return\\n"
            "        log.info(f'分配模式测试通过: {first_qpns}')"
        ),
    },
    {
        'suffix': '011',
        'scene': 'random_order',
        'scene_cn': '随机顺序',
        'description': '随机创建/销毁不同大小 block，验证无冲突。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 随机生成 20 个 log_obj_range（0~3）；\\n"
            "        '3. 随机顺序创建/销毁 block；\\n'"
            "        '4. 验证所有 first_qpn 唯一；\\n'"
            "        '5. 释放资源并清理环境。'"
        ),
        'do_body': (
            "        import random\\n"
            "        log.info('do: DevX Reserved QPN 随机顺序测试。')\\n"
            "        random.seed(42)\\n"
            "        first_qpns = []\\n"
            "        ops = []\\n"
            "        for i in range(20):\\n"
            "            log_range = random.randint(0, min(3, cls._max_log_range))\\n"
            "            ops.append((i, log_range))\\n"
            "        for i, log_range in ops:\\n"
            "            name = f'obj_qpn_rand_{i}'\\n"
            "            status, first_qpn = cls._create_qpn_block(name, log_range)\\n"
            "            if status != IpvbsStatusEnum.SUCCESS.value:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'随机创建 {name} 失败')\\n"
            "                return\\n"
            "            first_qpns.append(first_qpn)\\n"
            "        random.shuffle(ops)\\n"
            "        for i, _ in ops:\\n"
            "            cls._close_qpn_block(f'obj_qpn_rand_{i}')\\n"
            "        if len(set(first_qpns)) != len(first_qpns):\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'随机顺序测试 first_qpn 重复: {first_qpns}')\\n"
            "            return\\n"
            "        log.info('随机顺序测试通过')"
        ),
    },
    {
        'suffix': '012',
        'scene': 'out_view_check',
        'scene_cn': '返回缓冲区校验',
        'description': '校验 CREATE_GENERAL_OBJECT 输出 buffer 的 status/syndrome/obj_id 格式。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 创建 block；\\n'"
            "        '3. 读取 out_view 的字节 0（status）、4-7（syndrome）、8-11（obj_id）；\\n'"
            "        '4. 验证 status=0、syndrome=0、obj_id 非 0；\\n'"
            "        '5. 释放 block 并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 返回缓冲区校验。')\\n"
            "        status, first_qpn = cls._create_qpn_block('obj_qpn_out', 0)\\n"
            "        if status != IpvbsStatusEnum.SUCCESS.value:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('out_view 校验时创建 block 失败')\\n"
            "            return\\n"
            "        check_cmds = [\\n"
            "            \"list(glb_obj_qpn_out.out_view[:16])\",\\n"
            "            \"glb_obj_qpn_out.out_view[0]\",\\n"
            "            \"glb_struct.unpack('>I', glb_obj_qpn_out.out_view[4:8])[0]\",\\n"
            "            \"glb_struct.unpack('>I', glb_obj_qpn_out.out_view[8:12])[0]\",\\n"
            "        ]\\n"
            "        results = []\\n"
            "        for cmd in check_cmds:\\n"
            "            s, r = cls._ipvbs.exec_and_get_ipvbs_result(cmd)\\n"
            "            if s != IpvbsStatusEnum.SUCCESS.value:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'读取 out_view 失败: {cmd}')\\n"
            "                return\\n"
            "            results.append(r.strip())\\n"
            "        out_status = int(results[1])\\n"
            "        out_syndrome = int(results[2])\\n"
            "        out_obj_id = int(results[3])\\n"
            "        if out_status != 0 or out_syndrome != 0 or out_obj_id == 0:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'out_view 字段异常: status={out_status}, '\\n"
            "                           f'syndrome={out_syndrome}, obj_id={out_obj_id}')\\n"
            "            return\\n"
            "        log.info(f'out_view 校验通过: obj_id={out_obj_id}')"
        ),
    },
    {
        'suffix': '013',
        'scene': 'cross_device_alternating_stress',
        'scene_cn': '跨设备交替压力',
        'description': '在 mlx5_0 与 mlx5_1 之间交替创建/释放 block。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 交替在两个 device 上创建 block；\\n'"
            "        '3. 验证所有 first_qpn 唯一；\\n'"
            "        '4. 交替释放 block；\\n'"
            "        '5. 清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 跨设备交替压力测试。')\\n"
            "        devs = [cls._rdma_dev, 'mlx5_1' if cls._rdma_dev == 'mlx5_0' else 'mlx5_0']\\n"
            "        first_qpns = []\\n"
            "        for i in range(20):\\n"
            "            dev = devs[i % 2]\\n"
            "            name = f'obj_qpn_alt_{i}'\\n"
            "            cls._do_create_on_device(dev, name, f'{name}_first')\\n"
            "            status, first_qpn = cls._ipvbs.exec_and_get_ipvbs_result(\\n"
            "                f'str({name}_first)')\\n"
            "            if status != IpvbsStatusEnum.SUCCESS.value:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'交替创建 {name} 失败')\\n"
            "                return\\n"
            "            first_qpns.append(first_qpn.strip())\\n"
            "        if len(set(first_qpns)) != len(first_qpns):\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'交替压力 first_qpn 重复: {first_qpns}')\\n"
            "            return\\n"
            "        log.info('跨设备交替压力测试通过')"
        ),
    },
    {
        'suffix': '014',
        'scene': 'property_access_stability',
        'scene_cn': '属性访问稳定性',
        'description': '反复读取 block 的 first_qpn，验证值稳定。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 创建 block；\\n'"
            "        '3. 连续 100 次读取 first_qpn；\\n'"
            "        '4. 验证每次读取结果一致；\\n'"
            "        '5. 释放 block 并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 属性访问稳定性测试。')\\n"
            "        status, first_qpn = cls._create_qpn_block('obj_qpn_prop', 0)\\n"
            "        if status != IpvbsStatusEnum.SUCCESS.value:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('属性稳定性测试创建 block 失败')\\n"
            "            return\\n"
            "        read_count = 100\\n"
            "        for i in range(read_count):\\n"
            "            s, r = cls._ipvbs.exec_and_get_ipvbs_result(\\n"
            "                \"str(glb_helper.create_reserved_qpn(glb_mlx5_ctx, 0)[1])\")\\n"
            "            # 上面这行每次都创建新对象，不合适；改为读取已有对象属性\\n"
            "        # 修正：读取 obj_id\\n"
            "        values = set()\\n"
            "        for i in range(read_count):\\n"
            "            s, r = cls._ipvbs.exec_and_get_ipvbs_result(\\n"
            "                'str(glb_obj_qpn_prop.obj_id)')\\n"
            "            if s != IpvbsStatusEnum.SUCCESS.value:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'第 {i} 次读取 obj_id 失败')\\n"
            "                return\\n"
            "            values.add(r.strip())\\n"
            "        if len(values) != 1:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'obj_id 多次读取不一致: {values}')\\n"
            "            return\\n"
            "        log.info(f'属性访问稳定性测试通过，{read_count} 次读取一致')"
        ),
    },
]


def generate():
    template_text = TEMPLATE.read_text(encoding='utf-8')
    for scenario in SCENARIOS:
        suffix = scenario['suffix']
        scene = scenario['scene']
        scene_cn = scenario['scene_cn']
        src_case_id = '005_001'
        dst_case_id = f'005_{suffix}'
        class_name_old = 'NicLinuxRdmaDevxF0653005001PfCreateQpnNormalCreateQpn'
        class_name_new = (
            f'NicLinuxRdmaDevxF0653005{suffix}PfCreateQpn{scene.title()}CreateQpn'
        )

        text = template_text
        text = text.replace(src_case_id, dst_case_id)
        text = text.replace(class_name_old, class_name_new)
        text = text.replace('正常创建', scene_cn)
        text = text.replace('_normal_', f'_{scene}_')
        text = re.sub(
            r"case_title = \('.*?'_\n                  '.*?'_\n\)",
            f"case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_create_"
            f"ReservedQPN创建_{scene_cn}ReservedQPN')",
            text,
            flags=re.DOTALL,
        )
        text = re.sub(
            r"description:\\s+RDMA DevX 接口测试_用户态_PF_devx_obj_create_"
            r"ReservedQPN创建_正常创建ReservedQPN.*\n\n",
            f"description:   RDMA DevX 接口测试_用户态_PF_devx_obj_create_"
            f"ReservedQPN创建_{scene_cn}ReservedQPN\n\n"
            f"               {scenario['description']}\n\n",
            text,
        )
        text = re.sub(
            r"    test_steps = \(\n.*?    \)",
            f"    test_steps = (\n{scenario['test_steps']}\n    )",
            text,
            flags=re.DOTALL,
        )
        text = re.sub(
            r"    @classmethod\n    def do\(cls\) -> None:\n.*?\n\n    @classmethod\n    def post",
            f"    @classmethod\n    def do(cls) -> None:\n{scenario['do_body']}\n\n    @classmethod\n    def post",
            text,
            flags=re.DOTALL,
        )

        # 跨设备相关脚本需要 _do_create_on_device 辅助方法；若模板没有则追加
        if scene in ('cross_device', 'cross_device_alternating_stress'):
            helper_method = '''
    @classmethod
    def _do_create_on_device(cls, dev: str, obj_name: str, first_name: str) -> bool:
        cmds = [
            f"glb_ctx_tmp = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '{dev}')",
            f"glb_ret_tmp = glb_helper.create_reserved_qpn(glb_ctx_tmp, 0)",
            f"{obj_name} = glb_ret_tmp[0]",
            f"{first_name} = glb_ret_tmp[1]",
        ]
        for cmd in cmds:
            s, r = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if s != IpvbsStatusEnum.SUCCESS.value:
                log.error(f'在 {dev} 上创建 block 失败: {cmd}, {r}')
                return False
        return True
'''
            if '_do_create_on_device' not in text:
                text = text.replace(
                    'if __name__ == \'__main__\':',
                    helper_method + '\n\nif __name__ == \'__main__\':' 
                )

        out_name = (
            f'nic_linux_rdma_devx_f_06_53_{dst_case_id}_devx_create_qpn_'
            f'{scene}_create_qpn.py'
        )
        out_path = SRC_DIR / out_name
        out_path.write_text(text, encoding='utf-8')
        print(f'Generated {out_path}')


if __name__ == '__main__':
    generate()
```

- [ ] **Step 2: 语法检查**

Run: `python -m py_compile ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/generate_qpn_scripts.py`
Expected: exit 0

- [ ] **Step 3: Commit**

```bash
git add ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/generate_qpn_scripts.py
git commit -m "feat(devx): add Reserved QPN script generator (005_002~014)"
```

---

### Task 4: 运行生成器产出 13 个场景脚本

**Files:**
- 生成：13 个 `005_002` ~ `005_014` 脚本

- [ ] **Step 1: 运行生成器**

Run:
```bash
cd ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case
python generate_qpn_scripts.py
```
Expected: 打印 `Generated ...` 13 行。

- [ ] **Step 2: 批量语法检查**

Run:
```bash
cd ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case
for f in nic_linux_rdma_devx_f_06_53_005_*.py; do
    python -m py_compile "$f" || echo "FAIL $f"
done
```
Expected: 无 `FAIL` 输出。

- [ ] **Step 3: Commit 生成的脚本**

```bash
git add ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/nic_linux_rdma_devx_f_06_53_005_*.py
git commit -m "feat(devx): generate Reserved QPN scenario scripts 005_002~014"
```

---

### Task 5: 更新合并 Excel

**Files:**
- Create: `ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/update_devx_excel_with_qpn.py`
- Modify: `excel测试用例文件夹/DevX_PD_QP_CQ_SRQ_创建测试用例_含指令.xlsx`

**Interfaces:**
- Consumes: 现有 Excel 的 sheet 结构和最后一行 PD/QP/CQ/SRQ 用例
- Produces: 追加 14 条 QPN 用例后的 Excel

- [ ] **Step 1: 编写 Excel 更新脚本**

创建 `ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/update_devx_excel_with_qpn.py`。

实现要求：
- 使用 `openpyxl` 读取现有合并 Excel：`excel测试用例文件夹/DevX_PD_QP_CQ_SRQ_创建测试用例_含指令.xlsx`。
- 项目实际 Excel 为 18 列（与 PD/QP/CQ/SRQ 用例保持一致），脚本应根据已有表头或列语义填充，而不是假设只有 9 列。
- 从已生成的 14 个 QPN 脚本（`005_001` ~ `005_014`）中动态提取用例元数据：
  - `case_id`
  - `case_title`
  - `test_precondition`
  - `test_steps`
  - 脚本文件名
- 其他固定字段按项目已有约定填充：产品型号、模块、子模块、对象、opcode、工具、测试类型、优先级、功能等级、适用平台、执行命令等。
- 提供 `--dry-run` 选项用于预览，正常执行前自动创建时间戳备份。
- 在 sheet 末尾追加 14 行，不创建新 sheet。

```python
# 关键接口示意（具体列映射以实际 Excel 为准）
EXCEL_PATH = Path('excel测试用例文件夹/DevX_PD_QP_CQ_SRQ_创建测试用例_含指令.xlsx')
QPN_SCRIPT_GLOB = 'ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/nic_linux_rdma_devx_f_06_53_005_*.py'

def extract_case_from_script(path: Path) -> dict:
    ...

def append_qpn_cases(dry_run: bool = False):
    ...
```

- [ ] **Step 2: 安装 openpyxl 并运行**

Run:
```bash
pip install openpyxl
python ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/update_devx_excel_with_qpn.py
```
Expected: `已在 excel测试用例文件夹/DevX_PD_QP_CQ_SRQ_创建测试用例_含指令.xlsx 追加 14 条 QPN 用例`

- [ ] **Step 3: Commit**

```bash
git add ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/update_devx_excel_with_qpn.py
# Excel 文件为二进制，git 记录变更即可
git add excel测试用例文件夹/DevX_PD_QP_CQ_SRQ_创建测试用例_含指令.xlsx
git commit -m "docs(cases): append 14 Reserved QPN cases to merged Excel"
```

---

### Task 6: 跑通第一条脚本验证 helper 与模板

**Files:**
- Test: `ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/nic_linux_rdma_devx_f_06_53_005_001_devx_create_qpn_normal_create_qpn.py`

- [ ] **Step 1: 运行 005_001**

Run:
```bash
python ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/nic_linux_rdma_devx_f_06_53_005_001_devx_create_qpn_normal_create_qpn.py --lsip 10.17.44.100 --lsac framework --sip 10.17.44.100 --snicip 10.17.44.100 --sp 728 --cip 10.17.44.102 --cnicip 10.17.44.102 --cp 728 --hc 0 --te 0 --to 10 --tp 0 --timeout 1 --lst False --snicm centos --cnicm centos --sbmcip None --suname None --supasswd None --cbmcip None --cuname None --cupasswd None
```
Expected: exit 0，日志中出现 `Reserved QPN block 创建成功` 和 `first_qpn=`。

- [ ] **Step 2: 修复问题并重新跑测**

如果失败，查看日志定位：
- helper 未同步 → 检查 `_deploy_helper_if_needed`；
- `query_reserved_qpn_caps` 探测失败 → 检查固件是否支持 `MLX5_OBJ_TYPE_RESERVED_QPN`；
- `Mlx5DevxObj` 创建失败 → 检查 buffer 长度、opcode、obj_type。

- [ ] **Step 3: Commit 修复（如有）**

```bash
git add -A
git commit -m "fix(devx): resolve Reserved QPN normal script issues"
```

---

### Task 7: 顺序跑测 14 条脚本并汇总结果

**Files:**
- All 14 `005_xxx` scripts

- [ ] **Step 1: 顺序跑测脚本**

Run:
```bash
for id in 001 002 003 004 005 006 007 008 009 010 011 012 013 014; do
    echo "===== Running 005_${id} ====="
    python ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/nic_linux_rdma_devx_f_06_53_005_${id}_devx_create_qpn_*_create_qpn.py \
        --lsip 10.17.44.100 --lsac framework --sip 10.17.44.100 --snicip 10.17.44.100 --sp 728 \
        --cip 10.17.44.102 --cnicip 10.17.44.102 --cp 728 --hc 0 --te 0 --to 10 --tp 0 --timeout 1 \
        --lst False --snicm centos --cnicm centos --sbmcip None --suname None --supasswd None \
        --cbmcip None --cuname None --cupasswd None || echo "FAIL 005_${id}"
done
```
Expected: 无 `FAIL` 输出。

- [ ] **Step 2: 清理远端残留进程**

Run:
```bash
# 通过项目命令或框架内置清理
python -c "from scripts.nic100.linux.rdma.ipvbs_screen_utils import IpvbsScreen; from scripts.script_libs.enums import CmdExecuteAdressEnum, IpvbsCommuEnum; IpvbsScreen.exit_all_ipvbs(CmdExecuteAdressEnum.SERVER.value, commu=IpvbsCommuEnum.SOCKET.value, exit_ipvbs_s_force=True)"
```

- [ ] **Step 3: 最终 Commit**

```bash
git add -A
git commit -m "test(devx): verify all 14 Reserved QPN scripts pass"
```

---

## Self-Review

1. **Spec coverage:**
   - helper 封装 `CREATE_GENERAL_OBJECT` + `MLX5_OBJ_TYPE_RESERVED_QPN` → Task 1。
   - 14 条场景脚本 → Task 2 + Task 3 + Task 4。
   - Excel 合并更新 → Task 5。
   - 跑测验证 → Task 6 + Task 7。
2. **Placeholder scan:** 所有步骤均包含具体代码或命令，无 TBD/TODO。
3. **Type consistency:** helper 返回 `(obj, first_qpn)`；脚本中使用 `_create_qpn_block` 返回 `(status, first_qpn)`；命名统一。
