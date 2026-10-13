#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键检测当前环境是否支持 DevX Reserved QPN。

用法：
    python3 /root/sxetest/check_reserved_qpn_support.py [device]

默认检测 mlx5_0，可传入 mlx5_1 等。
"""
import sys

sys.path.insert(0, '/root/sxetest')

import pyverbs.providers.mlx5.mlx5dv as m
from pyverbs.providers.mlx5.mlx5dv import Mlx5Context, Mlx5DVContextAttr

import devx_qp_helper as h


def _create_general_object(ctx, obj_type, log_obj_range):
    """尝试下发 CREATE_GENERAL_OBJECT，返回 (success, reason)。"""
    hdr = h.GeneralObjInCmdHdr(
        opcode=h.DevxOps.MLX5_CMD_OP_CREATE_GENERAL_OBJECT,
        obj_type=obj_type,
        log_obj_range=log_obj_range,
    )
    cmd_in = bytes(h.CreateReservedQpnIn(hdr=hdr, rqpns=h.ReservedQpnBits()))
    try:
        obj = m.Mlx5DevxObj(ctx, cmd_in, len(h.GeneralObjOutCmdHdr()))
        obj.close()
        return True, 'OK'
    except Exception as e:
        return False, f'{type(e).__name__}: {e}'


def check(dev_name='mlx5_0'):
    print(f'=== Reserved QPN 环境检测: {dev_name} ===')
    print()

    # 1. 设备与固件版本
    try:
        with open(f'/sys/class/infiniband/{dev_name}/fw_ver', 'r') as f:
            fw_ver = f.read().strip()
    except Exception:
        fw_ver = 'unknown'
    print(f'[1] 固件版本: {fw_ver}')
    print()

    # 2. pyverbs DevX 初始化
    try:
        ctx = Mlx5Context(Mlx5DVContextAttr(), dev_name)
        print('[2] pyverbs Mlx5Context: OK')
    except Exception as e:
        print(f'[2] pyverbs Mlx5Context: FAIL - {e}')
        return
    print()

    # 3. helper 探测函数
    supported, max_log = h.query_reserved_qpn_caps(ctx)
    print(f'[3] query_reserved_qpn_caps(): supported={supported}, max_log_range={max_log}')
    print()

    # 4. 直接创建 Reserved QPN
    ok, reason = _create_general_object(ctx, h.DevxOps.MLX5_OBJ_TYPE_RESERVED_QPN, 0)
    print(f'[4] CREATE_GENERAL_OBJECT(RESERVED_QPN, log=0): {"OK" if ok else "FAIL"} ({reason})')
    print()

    # 5. 换不同 obj_type 验证是否是 GENERAL_OBJECT 整体不支持
    print('[5] 测试 CREATE_GENERAL_OBJECT 在不同 obj_type 下的表现:')
    for obj_type in [0, 0x0001, 0x0002, 0x0100, 0x002C]:
        ok, reason = _create_general_object(ctx, obj_type, 0)
        print(f'    obj_type={obj_type:#06x}: {"OK" if ok else "FAIL"} ({reason})')
    print()

    # 6. 结论
    if supported:
        print('[结论] 当前环境支持 Reserved QPN。')
    else:
        print('[结论] 当前环境不支持 Reserved QPN。')
        print('       原因：CREATE_GENERAL_OBJECT 被固件拒绝（errno 121 或类似错误）。')
        print('       建议：确认固件版本是否支持 MLX5_OBJ_TYPE_RESERVED_QPN，或更换测试环境。')


if __name__ == '__main__':
    dev = sys.argv[1] if len(sys.argv) > 1 else 'mlx5_0'
    check(dev)
