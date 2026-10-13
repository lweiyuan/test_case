# -*- coding: utf-8 -*-
"""模拟框架 paramiko 池路径（无显式密码，验证密钥认证）"""
import paramiko
for ip in ("10.17.44.100", "10.17.44.102"):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        c.connect(hostname=ip, port=728, username="root", timeout=10, banner_timeout=15,
                  look_for_keys=True, allow_agent=True)
        _, out, _ = c.exec_command("echo PARAMIKO_KEY_OK", timeout=10)
        print(ip, "->", out.read().decode().strip())
    except Exception as e:
        print(ip, "FAIL:", repr(e))
    finally:
        c.close()
