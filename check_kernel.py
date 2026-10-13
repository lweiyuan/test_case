#!/usr/bin/env python3
"""SSH 获取 Linux 内核版本，版本大于 6.6 输出 1，否则输出 0。

用法示例:
    python check_kernel.py 192.168.1.100 -u root -p password
    python check_kernel.py 192.168.1.100 -u root -k ~/.ssh/id_rsa
    python check_kernel.py 192.168.1.100 -u root --ge   # 大于等于 6.6 也算 1
"""

import argparse
import re
import sys

import paramiko


def get_kernel_release(host, port, username, password=None, key_filename=None):
    """通过 SSH 执行 uname -r，返回内核版本字符串。"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            host,
            port=port,
            username=username,
            password=password,
            key_filename=key_filename,
            timeout=10,
        )
        _stdin, stdout, stderr = client.exec_command("uname -r", timeout=10)
        release = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if not release:
            raise RuntimeError(f"uname -r 无输出: {err}")
        return release
    finally:
        client.close()


def compare_kernel(release, target=(6, 6), inclusive=False):
    """内核版本与 target 比较，大于返回 1，否则 0。

    inclusive=True 时，等于 target（含 6.6.x）也返回 1。
    """
    m = re.match(r"(\d+)\.(\d+)", release)
    if not m:
        raise ValueError(f"无法解析内核版本: {release!r}")
    version = (int(m.group(1)), int(m.group(2)))

    if inclusive:
        return 1 if version >= target else 0
    return 1 if version > target else 0


def main():
    parser = argparse.ArgumentParser(description="SSH 检查 Linux 内核版本是否大于 6.6")
    parser.add_argument("host", help="目标主机 IP/域名")
    parser.add_argument("-P", "--port", type=int, default=22, help="SSH 端口，默认 22")
    parser.add_argument("-u", "--username", required=True, help="SSH 用户名")
    parser.add_argument("-p", "--password", help="SSH 密码（建议改用密钥 -k）")
    parser.add_argument("-k", "--key-file", help="SSH 私钥文件路径")
    parser.add_argument("--ge", action="store_true", help="大于等于 6.6 也算 1（默认严格大于）")
    args = parser.parse_args()

    try:
        release = get_kernel_release(
            args.host,
            port=args.port,
            username=args.username,
            password=args.password,
            key_filename=args.key_file,
        )
    except Exception as exc:
        print(f"SSH 获取内核版本失败: {exc}", file=sys.stderr)
        sys.exit(2)

    print(f"内核版本: {release}", file=sys.stderr)
    result = compare_kernel(release, target=(6, 6), inclusive=args.ge)
    print(result)  # 标准输出只有 1 或 0


if __name__ == "__main__":
    main()
