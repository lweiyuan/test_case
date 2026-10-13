---
name: IB多播与iperf测试
description: NIC100框架下IB多播功能测试的专项skill，覆盖iperf2多播命令、IPv4/IPv6多播场景、与iperf3的差异及常见故障排查。
---

# NIC100 IB 多播与 iperf 测试指南

## 适用范围

- IB 多播功能验证（用户态 QP / 内核态 QP / ipoib）
- 使用 iperf 进行 IPv4/IPv6 多播数据包转发覆盖
- 多对多（1v2、2v2、2v1）多播场景构造
- iperf2 与 iperf3 在多播场景下的选型

## 环境要求

| 项目 | 要求 |
|------|------|
| 网卡驱动 | 天蝎网卡驱动已安装，IB 端口状态 Active |
| 工具 | `opensm`、`ib_send_bw`、`iperf`（2.x）、`iperf3` |
| 网络 | 测试节点之间 IB 网络互通 |
| 多播路由 | 节点需配置 `ip route add 224.0.0.2 dev ib0` |

## 核心原则

> **IB 多播测试必须使用 iperf 2.x，不能使用 iperf3。**
>
> iperf3 服务端无法绑定多播地址（`-B 224.0.0.2`），因此不能用于 `"iperf -s -u -B <multicast_addr>"` 这种多播服务端场景。
>
> **OpenSM 启动前状态检查需先复位网卡。**
>
> 为验证 opensm 启动能否将 ipoib 网口从 DOWN 激活为 UP，测试前应先停止 opensm，并通过重新加载 `mlx5_core` / `mlx5_ib` 驱动复位网卡，再加载 `ib_ipoib`，此时网口才处于真实的初始 DOWN 状态。

## 常用命令

### 服务端加入多播组

```bash
# IPv4 多播服务端
iperf -s -u -B 224.0.0.2 -i 1

# 参数说明
# -s  服务端模式
# -u  UDP 协议（多播基于 UDP）
# -B  绑定到多播地址，服务端通过该地址加入多播组
# -i  报告间隔（秒）
```

### 客户端向多播组发送

```bash
# IPv4 多播客户端
iperf -c 224.0.0.2 -u -l 128 -i 1 -t 1000 -B 192.168.1.111

# 参数说明
# -c  目标为多播地址
# -u  UDP 协议
# -l  数据包长度（字节）
# -i  报告间隔（秒）
# -t  测试时长（秒）
# -B  指定客户端源 IP
```

### IPv6 多播

```bash
# 配置 IPv6 地址（服务端/客户端应使用不同地址避免冲突）
ip -6 addr add 2001:db8::1/64 dev ib0

# 给所有节点发送多播
ping6 -I ib0 ff02::1

# 查看收发计数；多设备环境需指定 CA 与端口
perfquery -C mlx5_0 -P 1 -r
perfquery -C mlx5_0 -P 1
```

## 典型场景

### 场景1：1v1 多播

```bash
# 服务端
iperf -s -u -B 224.0.0.2 -i 1

# 客户端
iperf -c 224.0.0.2 -u -l 128 -i 1 -t 1000 -B 192.168.1.111
```

### 场景2：2v2 多对多多播（MC-16）

服务器 A：

```bash
ip route add 224.0.0.2 dev ib0
iperf -s -u -B 224.0.0.20 -i 1
```

服务器 B：

```bash
ip route add 224.0.0.2 dev ib0
iperf -s -u -B 224.0.0.20 -i 1
```

服务器 A 作为客户端：

```bash
iperf -c 224.0.0.20 -u -T 5 -l 128 -i 1 -t 1000 -B 192.168.100.1
```

服务器 B 作为客户端：

```bash
iperf -c 224.0.0.20 -u -T 5 -l 128 -i 1 -t 1000 -B 192.168.100.2
```

### 场景3：2v1 多对多多播（MC-18 / MC-19）

服务端：

```bash
ip route add 224.0.0.2 dev ib0
iperf -s -u -B 224.0.0.20 -i 1
```

客户端 A / B：

```bash
ip route add 224.0.0.2 dev ib0
iperf -c 224.0.0.20 -u -l 128 -i 1 -t 1000 -B <client_ip>
```

MC-19 需使用 ipoib connect 模式，包长设为 65520：

```bash
iperf -c 224.0.0.20 -u -l 65520 -i 1 -t 1000 -B <client_ip>
```

## iperf2 vs iperf3 对比

| 特性 | iperf 2.0.8 | iperf3 3.9 |
|------|-------------|------------|
| 多播服务端绑定 | **支持** `iperf -s -u -B <mcast>` | **不支持** |
| 默认端口 | 5001 | 5201 |
| UDP 默认包长 | 8 KB | dynamic / 1460 |
| 输出格式 | 文本 / CSV | 文本 / JSON |
| 双向测试 | `-d` / `-r` | `--bidir` / `-R` |

## 关键参数速查

| 参数 | 含义 | 多播场景说明 |
|------|------|--------------|
| `-s` | 服务端 | 必须 |
| `-c <addr>` | 客户端目标 | 写多播地址 |
| `-u` | UDP | 多播必须 |
| `-B <host>` | 绑定地址 | 服务端绑定多播地址；客户端绑定源 IP |
| `-T <ttl>` | TTL | 跨子网需增大，默认 1 |
| `-t <sec>` | 测试时长 | 长稳常用 1000 / 3600 / 7×24h |
| `-i <sec>` | 报告间隔 | 常用 1 |
| `-l <len>` | 包长 | 常用 128、1024、1460、65520 |
| `-P <n>` | 并行流 | 压力测试用 |

## 常见问题与排查

### 1. 服务端无法加入多播组

**现象**：客户端发送后服务端无输出。

**排查**：

```bash
# 确认使用的是 iperf 2.x
iperf -v

# 确认多播路由
ip route show | grep 224.0.0.2
```

### 2. 客户端报 "No route to host"

**排查**：

```bash
ip route add 224.0.0.2 dev ib0
```

### 3. 跨子网多播失败

**原因**：TTL 默认 1，无法跨子网。

**解决**：客户端加 `-T 5` 或更大值；同时需要支持多播的路由器。

### 4. 防火墙拦截

**排查**：

```bash
firewall-cmd --list-all
# 或临时关闭防火墙验证
systemctl stop firewalld
```

## 自动化脚本注意事项

1. **检测 iperf 时避免使用 `iperf -v`**
   - iperf 2.x 把版本信息输出到 **stderr**，stdout 为空。
   - 在 NIC100 框架 `CommandOperation.execute_command_with_error` 中应使用 `which iperf`，判断 stdout 是否非空。

2. **日志文件名不能包含 `iperf` 子串**
   - `CommandOperation` 对 `iperf`/`iperf3` 命令有特殊处理：会自动把命令中的 `iperf` 替换为 `iperf -p <port>`（避免多对一拓扑端口冲突）。
   - 如果日志文件名包含 `iperf`（如 `/tmp/iperf_mc3_client_ib0.log`），该子串也会被替换，导致文件名中出现空格，shell 解析异常。
   - **正确做法**：日志文件名避开 `iperf`，例如 `/tmp/mc3_client_ib0.log`。

3. 清理阶段需删除多播路由：`ip route del 224.0.0.2 dev ib0`。
4. 服务端和客户端启动顺序：先启动服务端，再启动客户端。
5. 多对多场景下，每个参与节点都需要配置多播路由。
6. 测试结束后确认所有 iperf 进程已退出，避免端口占用。
7. IPv4 多播测试时，服务端和客户端应配置不同 IP 地址，避免同一子网冲突。

### ib_send_bw 用户态多播结果判定

使用 `ib_send_bw -g -M <MGID>` 进行用户态多播测试时，判定业务成功的核心标准是：**日志中存在 BW average > 0 的数据行**。以下 teardown 阶段异常在多播场景下常见且可忽略：

- `failed to get mlid from MAD`
- `Couldn't Unregister the Mcast group on the SM`
- `Couldn't destroy all SEND resources`
- `received UMAD with an error`

解析日志时应注意：

1. 数据行后可能紧跟上述异常信息（无空白），正则不能限制 `\s*$`。
2. 建议分别解析 server/client 日志，只要有一端存在有效带宽就不判失败。
3. 可记录 `warning` 提示存在可忽略异常，但不要因此记录 Bug。

```python
import re

BENIGN_MCAST_ERRORS = [
    "failed to get mlid from MAD",
    "Couldn't Unregister the Mcast group on the SM",
    "Couldn't destroy all SEND resources",
]

def has_valid_bandwidth(output: str) -> bool:
    pattern = re.compile(
        r'^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)',
        re.MULTILINE,
    )
    return any(float(m[3]) > 0 for m in pattern.findall(output))
```

### ib_send_lat 多播延时结果判定

使用 `ib_send_lat -g -M <MGID>` 进行多播延时时，成功标志是日志中存在有效的 `t_avg[usec]` 或 `t_typical[usec]` 数据行。

`ib_send_lat` 输出格式因是否使用 `-D` 而不同：

- 默认 `-n` 模式（5 列）：`#bytes #iterations t_min t_max t_typical`
- `-D` 持续模式（4 列）：`#bytes #iterations t_avg tps`

兼容解析示例：

```python
import re

def parse_latency_from_output(output: str) -> float:
    pattern = re.compile(
        r'^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)(?:\s+(\d+\.\d+|\d+))?',
        re.MULTILINE,
    )
    matches = pattern.findall(output)
    if not matches:
        return 0.0
    last = matches[-1]
    # 5 列取 t_typical，4 列取 t_avg
    return float(last[4]) if last[4] else float(last[2])
```

以下 teardown 阶段异常在多播场景下常见且可忽略（不影响延时数据行判定）：

- `failed to get mlid from MAD`
- `Couldn't Unregister the Mcast group on the SM`
- `Couldn't destroy all SEND resources`
- `received UMAD with an error`
- `failed to open UMAD port 1`

> **环境前提**：多播延时测试要求网卡工作在 **InfiniBand 模式**。如果 `ibstat` 显示 `Link layer: Ethernet`，`ib_send_lat -g` 会初始化失败或无法产生有效延时数据。

## 关联用例

- MC-1 ~ MC-5：ipoib 驱动加载/卸载、OpenSM 启动前后状态
- MC-3 / MC-4：IPv4 / IPv6 多播基础验证
- MC-16 / MC-17 / MC-18 / MC-19：多对多多播场景
- MC-21 ~ MC-25：多播并发与混合业务

## 参考

- 远程环境实测：`10.17.44.73`（`fpga44-73`，RHEL 9.1）
- 项目文档：`docs/iperf_usage_tips.md`
