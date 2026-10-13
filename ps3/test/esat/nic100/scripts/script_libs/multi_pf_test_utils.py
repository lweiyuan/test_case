#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""Pure helper functions for multi-PF test scripts."""

import re
from typing import List


def parse_bandwidth_from_output(output: str, sample_lines: int = 5) -> float:
    """从 perftest 输出中解析最近 N 行 BW average[MB/sec] 的平均值。

    为排除停止动作导致的数据失真，默认排除最后一行，再向前取 sample_lines 行。
    """
    if not output:
        return 0.0

    pattern = re.compile(
        r"^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)",
        re.MULTILINE,
    )
    matches = pattern.findall(output)
    if not matches:
        return 0.0

    count = max(1, sample_lines)
    # 去掉最后一行，再向前取 count 行；数据不足时保留所有可用行
    recent = matches[-(count + 1) : -1] if len(matches) > count else matches[:-1]
    if not recent:
        recent = matches[-1:]

    bandwidths = []
    for match in recent:
        try:
            bandwidths.append(float(match[3]))
        except (ValueError, IndexError):
            continue

    return sum(bandwidths) / len(bandwidths) if bandwidths else 0.0


def is_pport(device: str) -> bool:
    """判断设备是否为 pport（物理端口）。双端口网卡的前两个 PF 为 pport。"""
    return device in ("mlx5_0", "mlx5_1")


def build_ib_read_bw_server_cmd(device: str, port: int, log_file: str) -> str:
    """构造 ib_read_bw server 端命令。"""
    return (
        f"nohup ib_read_bw -d {device} -p {port} -b --run_infinitely -D 1 -F "
        f"> {log_file} 2>&1 &"
    )


def build_ib_read_bw_client_cmd(device: str, port: int, server_ip: str, log_file: str) -> str:
    """构造 ib_read_bw client 端命令。"""
    return (
        f"nohup ib_read_bw -d {device} -p {port} -b --run_infinitely -D 1 -F {server_ip} "
        f"> {log_file} 2>&1 &"
    )


def build_query_commands(device: str, base_lid: str) -> List[str]:
    """构造针对指定 pport 的查询类命令列表。"""
    return [
        f"mlxconfig -d {device} q",
        f"smpquery -C {device} pi {base_lid} 1",
        f"perfquery -C {device} {base_lid} 1",
        f"ibportstate -C {device} {base_lid} 1",
    ]
