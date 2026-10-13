#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
case number: IPERF-AGG-001
case title: 多进程 iperf3 多流并发打流并汇总总带宽
test category: 以太网性能测试
check point: 多路 iperf3 并发打流时各流带宽与总带宽统计正确
author: auto-generated
date: 2026.06.24
@steps:
    1. 按参数解析服务端/客户端角色 IP 列表。
    2. 每路流量启动一个子进程，内部通过 ssh 在服务端机拉起
       iperf3 -s，在客户端机拉起 iperf3 -c。
    3. 所有流同时放行并发打流。
    4. 汇总各路带宽，输出总带宽。

@expected:
    各流正常打流，脚本汇总输出总带宽值。

@changelog:
2026.06.24 - 首次创建
- 多进程并发：每路 iperf3 独立进程，通过 Event 同步同时开始
- 绕过 CommandOperation：其 iperf 端口改写逻辑会破坏多路一致性，
  iperf 相关命令一律通过 subprocess + ssh 直连执行
- ssh 端口通过框架参数 --sp/--cp 传入（环境 ssh 端口为 728）
- 每路 iperf 使用独立端口：起始 --iperf-port，逐路递增 1

用法示例：
    python nic_linux_driver_iperf_multi_flow_bandwidth_aggregate.py \
        --sip 10.17.44.100 --cip 10.17.44.102 \
        --sp 728 --cp 728 --te 2 \
        --server-ips 10.17.44.100,10.17.44.101 \
        --client-ips 10.17.44.102,10.17.44.103 \
        --duration 60 --iperf-port 5201 --parallel 1

说明：
- --sip/--cip 为两台测试机的 ssh 管理地址，--server-ips/--client-ips
  为 iperf 使用的业务 IP（位于各自测试机待测网口上，需已配置且互通）
- --iperf-port 为起始端口，第 N 路使用 iperf-port + N，各路端口不同
- 可选参数缺省值：--duration 60、--iperf-port 5201、--parallel 1、
  --ssh-user root；未传参时按默认值打流，仅 --server-ips/--client-ips
  必传（无默认业务 IP 可依）
- --te 2 表示 SINGLE_MODE，跳过框架的物理环境一致性检查
- 默认 ssh 用户 root，脚本按免密 ssh 设计，请确保代码机到两台
  测试机已配置免密登录
"""

import sys
import argparse

# 自定义参数必须在框架 import 之前从 sys.argv 中剥离，
# 否则框架 CommandLineArgsParse 在 import 时 parse_args 会因
# 未定义参数而 SystemExit
_CUSTOM_ARGS = None


def _pre_parse_custom_args() -> None:
    """剥离自定义参数，保留框架参数供后续框架解析"""
    global _CUSTOM_ARGS
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--server-ips', type=str, default='')
    parser.add_argument('--client-ips', type=str, default='')
    parser.add_argument('--duration', type=int, default=60)
    parser.add_argument('--iperf-port', type=int, default=5201)
    parser.add_argument('--parallel', type=int, default=1)
    parser.add_argument('--ssh-user', type=str, default='root')
    args, extras = parser.parse_known_args(sys.argv[1:])
    sys.argv = [sys.argv[0]] + extras
    _CUSTOM_ARGS = args


_pre_parse_custom_args()

import json
import time
import subprocess
import multiprocessing
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.enums import BugTypeEnum
from scripts.script_libs.script_base import ScriptBase
from scripts.script_libs.command_line_args_parse import (
    CommandLineArgsParse,
)

# 服务端就绪轮询次数与间隔（秒）
SERVER_READY_POLL = 20
SERVER_READY_INTERVAL = 1
# 等待所有流就绪的总超时（秒）
READY_TOTAL_TIMEOUT = 120
# ssh 连接超时（秒）
SSH_CONNECT_TIMEOUT = 10
# ssh 命令默认执行超时（秒）
SSH_CMD_TIMEOUT = 120


def _ssh_execute(host, port, user, remote_cmd, timeout=SSH_CMD_TIMEOUT):
    """通过 ssh 在远端主机执行命令，返回 (rc, stdout, stderr)"""
    cmd = [
        'ssh', '-p', str(port),
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'ConnectTimeout={}'.format(SSH_CONNECT_TIMEOUT),
        '-o', 'BatchMode=yes',
        '{}@{}'.format(user, host),
        remote_cmd,
    ]
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout,
        )
        out = proc.stdout.decode('utf-8', errors='replace')
        err = proc.stderr.decode('utf-8', errors='replace')
        return proc.returncode, out, err
    except subprocess.TimeoutExpired:
        return -1, '', 'ssh 执行超时: {}'.format(remote_cmd[:200])
    except OSError as exc:
        return -1, '', 'ssh 执行失败: {}'.format(exc)


def _parse_iperf_json(raw_stdout):
    """从 iperf3 -J 输出中提取 JSON，返回 (data, error_msg)"""
    text = raw_stdout.strip()
    start = text.find('{')
    if start < 0:
        return None, 'iperf3 输出中未找到 JSON 内容'
    try:
        return json.loads(text[start:]), None
    except ValueError as exc:
        return None, 'iperf3 JSON 解析失败: {}'.format(exc)


def _run_one_flow(idx, server_host, server_ssh_port, client_host,
                  client_ssh_port, ssh_user, server_ip, client_ip,
                  iperf_port, duration, parallel, start_event,
                  ready_queue, result_queue):
    """单个子进程：启动一路 iperf3 服务端并打一路客户端流量"""
    srv_pid_file = '/tmp/iperf3_srv_{}.pid'.format(idx)
    srv_log_file = '/tmp/iperf3_srv_{}.log'.format(idx)

    def _cleanup_server():
        clean_cmd = (
            'kill "$(cat {pid} 2>/dev/null)" 2>/dev/null; '
            'rm -f {pid} {log}; true'
        ).format(pid=srv_pid_file, log=srv_log_file)
        _ssh_execute(server_host, server_ssh_port, ssh_user, clean_cmd)

    try:
        # 1. 在服务端机启动 iperf3 服务端（后台运行，记录 pid）
        srv_cmd = (
            'nohup iperf3 -s -B {sip} -p {port} > {log} 2>&1 & '
            'echo $! > {pid}'
        ).format(sip=server_ip, port=iperf_port,
                 log=srv_log_file, pid=srv_pid_file)
        rc, out, err = _ssh_execute(server_host, server_ssh_port,
                                    ssh_user, srv_cmd)
        if rc != 0:
            ready_queue.put(('not_ready', idx))
            result_queue.put((
                'result', idx, False, 0,
                '服务端 iperf3 启动失败: {}'.format(err),
            ))
            return

        # 2. 轮询服务端监听端口是否就绪
        ready_cmd = 'ss -ltn | grep ":{port} "'.format(port=iperf_port)
        ready = False
        for _ in range(SERVER_READY_POLL):
            rc, out, err = _ssh_execute(server_host, server_ssh_port,
                                        ssh_user, ready_cmd)
            if rc == 0 and out.strip():
                ready = True
                break
            time.sleep(SERVER_READY_INTERVAL)
        ready_queue.put(('ready' if ready else 'not_ready', idx))
        if not ready:
            result_queue.put((
                'result', idx, False, 0,
                '服务端 iperf3 未在预期时间内监听端口 {}'.format(iperf_port),
            ))
            return

        # 3. 等待主进程统一放行，保证所有流同时开始
        start_event.wait()

        # 4. 在客户端机执行 iperf3 客户端打流
        cli_cmd = (
            'iperf3 -c {sip} -B {cip} -p {port} '
            '-t {dur} -P {par} -J'
        ).format(sip=server_ip, cip=client_ip, port=iperf_port,
                 dur=duration, par=parallel)
        cli_timeout = duration + 120
        rc, out, err = _ssh_execute(client_host, client_ssh_port,
                                    ssh_user, cli_cmd,
                                    timeout=cli_timeout)
        if rc != 0:
            result_queue.put((
                'result', idx, False, 0,
                'iperf3 客户端执行失败 rc={}: {}'.format(rc, err),
            ))
            return

        # 5. 解析 iperf3 结果
        data, parse_err = _parse_iperf_json(out)
        if parse_err is not None:
            result_queue.put(('result', idx, False, 0, parse_err))
            return
        if data.get('error'):
            result_queue.put((
                'result', idx, False, 0, 'iperf3 报错: {}'.format(
                    data['error']),
            ))
            return
        try:
            bps = data['end']['sum_sent']['bits_per_second']
        except (KeyError, TypeError):
            result_queue.put((
                'result', idx, False, 0,
                'iperf3 结果中缺少 sum_sent 带宽字段',
            ))
            return
        result_queue.put(('result', idx, True, bps, ''))
    finally:
        _cleanup_server()


class NicLinuxDriverIperfMultiFlowBandwidthAggregate(ScriptBase):
    test_object = "iperf3 Multi Flow Bandwidth Aggregate"
    test_module = "以太网模块测试"
    test_tool = "iperf3, ssh"
    test_precondition = """代码机与两台测试机之间已配置免密 ssh
两台测试机均已安装 iperf3
服务端/客户端业务 IP 已配置且互通"""
    test_steps = """
    1. 解析参数得到服务端角色 IP 列表与客户端角色 IP 列表。
    2. 每路流量启动一个子进程，子进程通过 ssh 在服务端机启动
       iperf3 -s，在客户端机启动 iperf3 -c 打流。
    3. 所有流就绪后同时放行，并发打流。
    4. 汇总各路带宽，输出总带宽值。
    """

    # 服务端/客户端测试机 ssh 管理地址与端口
    SERVER_HOST = None
    SERVER_SSH_PORT = None
    CLIENT_HOST = None
    CLIENT_SSH_PORT = None

    # 服务端角色监听 IP 列表 / 客户端角色源 IP 列表
    SERVER_IP_LIST = []
    CLIENT_IP_LIST = []
    FLOW_NUM = 0

    # 打流参数
    DURATION = 60
    IPERF_PORT = 5201
    PARALLEL = 1
    SSH_USER = 'root'

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "IperfMultiFlowBandwidthAggregate Failed"
        cls.bug_test_module = cls.test_module
        cls.bug_case = cls.__name__
        # 统一在此设置 bug 类型，确保 prepare/do 中 create_bug 能真正抛异常
        cls.set_bug_type(BugTypeEnum.PERFORMANCE.value)

        # 主机/端口解析放这里，保证 check_own_environment 阶段即可用
        cls.SERVER_HOST = CommandLineArgsParse.get_server_ip()
        cls.SERVER_SSH_PORT = CommandLineArgsParse.get_server_port()
        cls.CLIENT_HOST = CommandLineArgsParse.get_client_ip()
        cls.CLIENT_SSH_PORT = CommandLineArgsParse.get_client_port()

        cls.DURATION = _CUSTOM_ARGS.duration
        cls.IPERF_PORT = _CUSTOM_ARGS.iperf_port
        cls.PARALLEL = _CUSTOM_ARGS.parallel
        cls.SSH_USER = _CUSTOM_ARGS.ssh_user

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 iperf3 汇聚打流测试环境...")
        for host, port, name in [
            (cls.SERVER_HOST, cls.SERVER_SSH_PORT, "服务端机"),
            (cls.CLIENT_HOST, cls.CLIENT_SSH_PORT, "客户端机"),
        ]:
            rc, out, err = _ssh_execute(host, port, cls.SSH_USER,
                                        "which iperf3")
            if rc != 0 or not out.strip():
                log.error("{} 未找到 iperf3: {}".format(name, err))
                cls.own_environment_enabled = False
                return
        cls.own_environment_enabled = True
        log.info("环境检查通过：两台测试机均已安装 iperf3")

    @classmethod
    def prepare(cls) -> None:
        log.info("准备 iperf3 汇聚打流测试环境...")

        server_ips = [ip.strip() for ip in
                      _CUSTOM_ARGS.server_ips.split(',') if ip.strip()]
        client_ips = [ip.strip() for ip in
                      _CUSTOM_ARGS.client_ips.split(',') if ip.strip()]
        if not server_ips or not client_ips:
            cls.create_bug('服务端/客户端 IP 列表不能为空，请通过 '
                           '--server-ips/--client-ips 传入')
        if len(server_ips) != len(client_ips):
            cls.create_bug('服务端 IP 数量({})与客户端 IP 数量({})'
                           '不一致'.format(len(server_ips),
                                          len(client_ips)))
        cls.SERVER_IP_LIST = server_ips
        cls.CLIENT_IP_LIST = client_ips
        cls.FLOW_NUM = len(server_ips)
        log.info("共 {} 路 iperf3 流量".format(cls.FLOW_NUM))

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 iperf3 多流并发打流测试")
        log.info("=" * 60)

        if 'fork' in multiprocessing.get_all_start_methods():
            try:
                multiprocessing.set_start_method('fork')
            except RuntimeError:
                # 已设置过 start_method 时重复调用会抛异常，忽略即可
                pass

        start_event = multiprocessing.Event()
        ready_queue = multiprocessing.Queue()
        result_queue = multiprocessing.Queue()

        processes = []
        for idx in range(cls.FLOW_NUM):
            flow_port = cls.IPERF_PORT + idx
            proc = multiprocessing.Process(
                target=_run_one_flow,
                args=(idx, cls.SERVER_HOST, cls.SERVER_SSH_PORT,
                      cls.CLIENT_HOST, cls.CLIENT_SSH_PORT,
                      cls.SSH_USER, cls.SERVER_IP_LIST[idx],
                      cls.CLIENT_IP_LIST[idx], flow_port,
                      cls.DURATION, cls.PARALLEL, start_event,
                      ready_queue, result_queue),
            )
            processes.append(proc)
            proc.start()

        # 等待所有流就绪（或超时），再统一放行
        ready_flows = 0
        received = 0
        deadline = time.time() + READY_TOTAL_TIMEOUT
        while ready_flows < cls.FLOW_NUM and time.time() < deadline:
            try:
                msg = ready_queue.get(timeout=1)
            except Exception:
                continue
            if msg[0] == 'ready':
                ready_flows += 1
            # 每个子进程恰好 put 一条 ready/not_ready，收满即可结束等待
            received += 1
            if received >= cls.FLOW_NUM:
                break
        start_event.set()
        log.info("就绪流数 {}/{}，统一放行并发打流".format(
            ready_flows, cls.FLOW_NUM))

        for proc in processes:
            proc.join()

        # 汇总各流结果
        flow_results = {}
        while True:
            try:
                msg = result_queue.get(timeout=1)
            except Exception:
                break
            if msg[0] == 'result':
                flow_results[msg[1]] = msg

        total_bps = 0
        failed_flows = []
        for idx in range(cls.FLOW_NUM):
            if idx in flow_results:
                kind, i, ok, bps, err = flow_results[idx]
                if ok:
                    total_bps += bps
                    log.info(
                        "流{} 端口{} {sip}->{cip}: {bps:.2f} Mbps".format(
                            idx, cls.IPERF_PORT + idx,
                            sip=cls.SERVER_IP_LIST[idx],
                            cip=cls.CLIENT_IP_LIST[idx],
                            bps=bps / 1000 / 1000))
                else:
                    failed_flows.append(idx)
                    log.error("流{} 失败: {}".format(idx, err))
            else:
                failed_flows.append(idx)
                log.error("流{} 未返回结果".format(idx))

        log.info("=" * 60)
        log.info("总带宽: {:.2f} Mbps ({:.2f} Gbps)".format(
            total_bps / 1000 / 1000, total_bps / 1000 / 1000 / 1000))
        log.info("=" * 60)

        if failed_flows or total_bps <= 0:
            msg = 'iperf3 多流汇聚打流失败，失败流: {}，总带宽: ' \
                  '{:.2f} Mbps'.format(
                      failed_flows if failed_flows else '无(总带宽为0)',
                      total_bps / 1000 / 1000)
            cls.bug_result = msg
            cls.bug_expect = "所有流均打流成功，总带宽大于 0"
            cls.set_bug_type(BugTypeEnum.PERFORMANCE.value)
            cls.create_bug(msg)

    @classmethod
    def post(cls) -> None:
        log.info("清理测试环境...")
        for host, port, name in [
            (cls.SERVER_HOST, cls.SERVER_SSH_PORT, "服务端机"),
            (cls.CLIENT_HOST, cls.CLIENT_SSH_PORT, "客户端机"),
        ]:
            clean_cmd = (
                'for f in /tmp/iperf3_srv_*.pid; do '
                '[ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null; '
                'rm -f "$f"; done; '
                'rm -f /tmp/iperf3_srv_*.log; true'
            )
            _ssh_execute(host, port, cls.SSH_USER, clean_cmd)
        log.info("测试环境清理完成")


def main() -> None:
    NicLinuxDriverIperfMultiFlowBandwidthAggregate.run()


if __name__ == '__main__':
    main()
