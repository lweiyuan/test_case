# -*- coding: utf-8 -*-
"""复跑前核查：SSH 连通性 + 真机文件/环境状态"""
import paramiko, hashlib, sys

HOSTS = [("10.17.44.100", "server"), ("10.17.44.102", "client")]
PORT = 728
USER = "root"
PWD = "q4Jvi1z3DXVIh7uk"

def run(ip, cmd, timeout=20):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=ip, port=PORT, username=USER, password=PWD, timeout=10, banner_timeout=15)
    _, out, err = c.exec_command(cmd, timeout=timeout)
    rc = out.channel.recv_exit_status()
    o = out.read().decode(errors="ignore").strip()
    e = err.read().decode(errors="ignore").strip()
    c.close()
    return rc, o, e

for ip, role in HOSTS:
    print(f"===== {role} {ip} =====")
    rc, o, e = run(ip, "echo OK; hostname; python3 --version; which dcb iperf3; ip -br link | grep ens")
    print("rc=", rc)
    print(o)
    if e:
        print("stderr:", e)
    # 查找脚本文件并核对（若有）
    rc2, o2, e2 = run(ip, "find / -name '*021_030*' 2>/dev/null | head -5")
    print("--- find 021_030:", o2 or "(none)")
    if o2:
        for f in o2.splitlines():
            rc3, o3, _ = run(ip, f"wc -l {f} && md5sum {f}")
            print(f, "->", o3)
    # tx_sched debugfs 节点状态
    rc4, o4, _ = run(ip, "ls /sys/kernel/debug/mlx5_core/ 2>/dev/null; dcb ets show dev ens25f0np0 2>&1 | head -5")
    print("--- debugfs/dcb:", o4 or "(empty)")
    print()
