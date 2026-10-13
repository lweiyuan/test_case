#!/usr/bin/env python3
"""根据 VF 网口名获取所属 PF 网口名（Linux SR-IOV）。

原理（基于 sysfs）：
1. 读取 /sys/class/net/<vf>/device 链接：
   - 若链接目标本身是 <PF设备>/virtfnN，直接得到 PF 设备目录；
   - 否则 VF 通常是独立 PCI 功能，反查所有网卡的 <PF设备>/virtfn* 链接，
     指向同一 VF 设备的就是它的 PF。
2. PF 设备目录下的 net/ 子目录里就是 PF 网口名。
3. 都失败时回退到常见命名规则（如 ens1f0v0 -> ens1f0）。

用法：
    python vf_to_pf.py ens1f0v0
"""

import argparse
import glob
import os
import re
import sys

SYS_CLASS_NET = "/sys/class/net"


def _netdev_of(pf_dev):
    """从 PF 设备目录读取其网口名，如 <pf_dev>/net/ens1f0。"""
    net_dir = os.path.join(pf_dev, "net")
    if os.path.isdir(net_dir):
        entries = sorted(os.listdir(net_dir))
        if entries:
            return entries[0]
    return None


def _pf_from_link(vf_link):
    """情况 1：VF device 链接直接指向 <PF设备>/virtfnN，从链接目标解析 PF。"""
    try:
        target = os.readlink(vf_link)
    except OSError:
        return None
    if not re.search(r"virtfn\d+$", os.path.basename(target)):
        return None
    base = target if os.path.isabs(target) else os.path.join(os.path.dirname(vf_link), target)
    # base 形如 .../<PF设备>/virtfnN，去掉末段即 PF 设备目录
    return os.path.realpath(os.path.dirname(base))


def _pf_from_reverse_scan(vf_dev, sys_class_net):
    """情况 2：遍历所有网卡的设备目录，找 virtfn* 指向该 VF 设备的 PF。"""
    try:
        nets = os.listdir(sys_class_net)
    except OSError:
        return None
    for net in nets:
        pf_link = os.path.join(sys_class_net, net, "device")
        if not os.path.isdir(pf_link):
            continue
        pf_dev = os.path.realpath(pf_link)
        for virtfn in glob.glob(os.path.join(pf_dev, "virtfn*")):
            if os.path.realpath(virtfn) == vf_dev:
                return pf_dev
    return None


def _pf_from_name(vf_name):
    """回退：按常见命名规则去掉尾部 vN，如 ens1f0v0 -> ens1f0。"""
    m = re.match(r"^(.*)v\d+$", vf_name)
    if m and m.group(1):
        return m.group(1)
    return None


def get_pf_name(vf_name, sys_class_net=SYS_CLASS_NET):
    """根据 VF 网口名返回 PF 网口名；找不到返回 None。"""
    if not vf_name:
        return None

    vf_link = os.path.join(sys_class_net, vf_name, "device")
    if not os.path.exists(vf_link):
        # sysfs 中不存在该网卡，只能按命名规则回退
        return _pf_from_name(vf_name)

    # 优先从 device 链接目标解析
    pf_dev = _pf_from_link(vf_link)
    if pf_dev is None:
        # 反查：PF 的 virtfn* 链接指向该 VF 设备
        vf_dev = os.path.realpath(vf_link)
        pf_dev = _pf_from_reverse_scan(vf_dev, sys_class_net)

    if pf_dev:
        name = _netdev_of(pf_dev)
        if name:
            return name

    # 最后按命名规则回退
    return _pf_from_name(vf_name)


def main():
    parser = argparse.ArgumentParser(description="根据 VF 网口名获取 PF 网口名")
    parser.add_argument("vf", help="VF 网口名，如 ens1f0v0")
    parser.add_argument("--sysfs", default=SYS_CLASS_NET, help="sysfs 网卡目录，默认 /sys/class/net")
    args = parser.parse_args()

    pf = get_pf_name(args.vf, sys_class_net=args.sysfs)
    if pf:
        print(pf)
        sys.exit(0)
    print(f"未找到 {args.vf} 对应的 PF", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
