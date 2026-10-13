#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测当前设备固件是否支持 DevX uid 下创建 MKEY。

输出约定（供测试脚本 _probe_devx_mkey_supported 解析）：
    DEVX_MKEY_SUPPORTED      固件支持，可通过 DevX 创建 MKEY
    DEVX_MKEY_NOT_SUPPORTED  固件限制，DevX 创建 MKEY 返回 errno 121
    其他                      探测过程异常

用法：python3 probe_mkey_support.py [device]
device 缺省时自动取 /sys/class/infiniband/ 下的第一个设备。
"""
import os
import sys

# 允许从脚本同目录导入 devx_qp_helper
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def _pick_device():
    if len(sys.argv) > 1:
        return sys.argv[1]
    dev_dir = '/sys/class/infiniband'
    if not os.path.isdir(dev_dir):
        return None
    names = sorted(os.listdir(dev_dir))
    return names[0] if names else None


def main():
    dev = _pick_device()
    if not dev:
        print('DEVX_MKEY_PROBE_ERR no_rdma_device')
        return 1
    import devx_qp_helper as h
    import pyverbs.providers.mlx5.mlx5dv as m

    ctx = m.Mlx5Context(m.Mlx5DVContextAttr(), dev)
    try:
        _, pd_num = h.create_devx_pd(ctx)
        # 交叉验证：依次尝试 PA(0)、KLMS(2) 访问模式。
        # 部分固件仅支持其中一种模式，避免 PA 失败就误判为不支持。
        for mode, name in [(0, 'PA'), (2, 'KLMS')]:
            try:
                h.create_devx_mkey(ctx, pd_num, access_mode=mode)
                print('DEVX_MKEY_SUPPORTED mode=%s' % name)
                return 0
            except h.DevxMkeyNotSupportedError:
                continue
        print('DEVX_MKEY_NOT_SUPPORTED')
    except Exception as e:  # noqa: BLE001
        print('DEVX_MKEY_PROBE_ERR %s %r' % (type(e).__name__, e))
    finally:
        try:
            ctx.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
