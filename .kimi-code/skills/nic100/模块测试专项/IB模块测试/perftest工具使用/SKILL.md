---
name: perftest工具使用
description: 指导NIC100框架下使用perftest工具执行IB/RDMA带宽、延迟、多播测试，包括并发执行、内存估算与结果解析。
---

# IB 性能测试

## 基本规则

- 所有 perftest 命令必须成对出现：先启动 server，再启动 client。
- 如果测试用例没有明确要求，默认执行 60 秒（使用 `-D 60`）。
- 建议增加 `-F` 参数，避免 CPU 频率相关提示干扰日志解析。

## 常用命令

| 命令 | 方向 | 测试指标 |
|------|------|----------|
| `ib_send_bw` | 发送带宽 | 带宽 |
| `ib_read_bw` | 读带宽 | 带宽 |
| `ib_write_bw` | 写带宽 | 带宽 |
| `ib_send_lat` | 发送延迟 | 延迟 |
| `ib_read_lat` | 读延迟 | 延迟 |
| `ib_write_lat` | 写延迟 | 延迟 |

## 常用参数

| 参数 | 说明 |
|------|------|
| `-d <dev>` | 指定设备，如 `mlx5_0` |
| `-i <port>` | 指定 IB 端口号 |
| `-p <port>` | 指定监听/连接端口（默认 18515） |
| `-s <size>` | 消息大小（字节），BW 默认 65536，Lat 默认 2 |
| `-l <list>` | post list 大小（**不是包长**，包长请用 `-s`） |
| `-q <num>` | QP 数量 |
| `-D <sec>` | 测试持续时间（秒） |
| `-n <iters>` | 迭代次数；write 默认 5000，send/read 默认 1000 |
| `-b` | 双向带宽测试（server/client 均需加） |
| `-F` | 禁用 CPU 频率提示 |
| `-S <sl>` | 服务级别（server/client 必须一致） |
| `-x <idx>` | GID index |
| `-c <type>` | 连接类型 RC/XRC/UC/UD/DC/SRD（默认 RC） |
| `--report_gbits` | 以 Gbps 为单位报告 |
| `--run_infinitely` | 持续运行，需外部停止 |
| `-g` | 发送到多播组 |
| `-M <mgid>` | 多播组 GID |
| `--use-srq` | 使用共享接收队列 |

## 基础示例

```bash
# server
ib_read_bw -d mlx5_0 -b -F -p 18000

# client
ib_read_bw -d mlx5_0 -b -F -p 18000 <server_ip>
```

## 多线程并发执行

并发执行多条 perftest 流时，建议使用 Python `_thread` 模块进行低层级线程管理：

```python
import _thread

client_results = []
completed = [0]
lock = _thread.allocate_lock()

for proc in processes:
    _thread.start_new_thread(
        cls._client_thread_entry,
        (proc, client_results, completed, lock)
    )

# 手动轮询等待所有线程完成
timeout = 240
start_time = time.time()
while completed[0] < len(processes):
    if time.time() - start_time > timeout:
        log.error(f"Timeout: {completed[0]}/{len(processes)} completed")
        break
    time.sleep(0.5)
```

线程入口函数规范：

```python
@staticmethod
def _client_thread_entry(proc, client_results, completed, lock):
    try:
        client_cmd = (
            f"nohup ib_read_bw -d {proc['device']} -q 1024 -s 65536 "
            f"-b --run_infinitely -D 1 -F -p {proc['port']} -S {proc['sl']} {proc['server_ip']} "
            f"> /tmp/ib_read_bw_client_{proc['port']}.log 2>&1 &"
        )
        status, result, err = CommandOperation.execute_command_with_error(
            client_cmd, CmdExecuteAdressEnum.CLIENT.value
        )
        res = {"device": proc['device'], "sl": proc['sl'], "port": proc['port'],
               "status": status, "result": result, "err": err}
    except Exception as e:
        res = {"device": proc['device'], "sl": proc['sl'], "port": proc['port'],
               "status": -1, "result": "", "err": str(e)}

    with lock:
        client_results.append(res)
        completed[0] += 1
```

关键注意事项：
- 必须加锁访问共享状态。
- 必须在线程内捕获异常，否则异常会静默丢失。
- `_thread` 没有 `join()`，需通过共享计数器 + 轮询等待完成。
- 避免在子线程中调用 `create_bug`，Bug 记录逻辑应在主线程中统一处理。
- 指定 SL 时 server 端也必须加 `-S`，且两端值一致。

## 内存估算与参数调整

打流前需评估服务器空闲内存，再根据余量调整 `-q`（QP 数量）和 `-s`（包长）：

- **线网业务**：单条流内存 ≈ `2 * QP数量 * 包长`
- **自发自收业务**：单条流内存 ≈ `4 * QP数量 * 包长`
- 默认包长按 64KB（65536 字节）估算。

调整原则：
1. 预留至少 20%~30% 安全余量。
2. 优先降低 `-q`。
3. 次选降低 `-s`；注意包长会影响带宽结果。
4. 用例有明确要求时以用例为准。

## 结果重定向与成功判定

并发执行时，必须将**收发两端**输出重定向到独立日志文件，并发结束后通过检查文件内容判断每条流是否成功。

```bash
# server
nohup ib_read_bw -d mlx5_0 -b -D 1 -F -p 18000 > /tmp/ib_read_bw_server_18000.log 2>&1 &

# client
nohup ib_read_bw -d mlx5_0 -b -D 1 -F -p 18000 <server_ip> > /tmp/ib_read_bw_client_18000.log 2>&1 &
```

- `--run_infinitely` 场景下，超时仅作为停止机制，不代表失败。
- 成功判定应检查日志中是否存在有效的 `BW average[MB/sec]` 且数值大于 0。
- 出现 `Couldn't connect`、`connection refused`、`failed to initialize` 等致命连接错误且无有效带宽时判定失败。

## 输出解析与带宽统计

perftest 三种常见运行方式：

1. **指定运行时间（`-D <seconds>`）**：输出只有一条最终统计行，直接取 `BW average[MB/sec]`。
2. **指定发包量（`-n <iters>`）**：输出只有一条最终统计行，取 `BW average[MB/sec]`。
3. **永久运行并被外部停止（`--run_infinitely`）**：会周期性输出多行统计，建议取**除最后一次之外的最近 10 次** `BW average[MB/sec]` 求平均，避免停止时末尾统计失真。

统一解析正则示例：

```python
import re

def parse_bandwidth_from_output(output):
    # 注意：不要要求行尾为空白，perftest 数据行后可能紧跟 teardown 异常信息
    pattern = re.compile(
        r'^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)',
        re.MULTILINE
    )
    matches = pattern.findall(output)
    if not matches:
        return 0.0
    if len(matches) == 1:
        return float(matches[0][3])
    recent_matches = matches[-11:-1]
    return sum(float(m[3]) for m in recent_matches) / len(recent_matches)
```

> **关键注意**：perftest 数据行（尤其是多播场景）末尾可能紧跟 `received UMAD with an error`、`failed to get mlid from MAD` 等异常信息，**中间没有空白**。正则若使用 `\s*$` 会匹配失败，导致误判为无带宽。

## ib_send_lat 延时输出解析

`ib_send_lat` 的输出列数随运行方式不同而变化，解析时需注意区分：

| 运行方式 | 输出列 | 延时字段 |
|----------|--------|----------|
| 默认 `-n <iters>` | `#bytes #iterations t_min[usec] t_max[usec] t_typical[usec]` | `t_typical`（第 5 列） |
| 持续 `-D <sec>` | `#bytes #iterations t_avg[usec] tps average` | `t_avg`（第 3 列） |

示例（`-D` 模式）：

```text
 #bytes        #iterations       t_avg[usec]    tps average
 512           1915478            0.78           638810.36
```

兼容两种格式的正则示例：

```python
import re

def parse_latency_from_output(output: str) -> float:
    # 5 列时取 t_typical；4 列（-D）时取 t_avg
    pattern = re.compile(
        r'^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)(?:\s+(\d+\.\d+|\d+))?',
        re.MULTILINE,
    )
    matches = pattern.findall(output)
    if not matches:
        return 0.0
    last = matches[-1]
    return float(last[4]) if last[4] else float(last[2])
```

> **注意**：与 `ib_send_bw` 一样，`-D` 模式只有一条最终统计行；`--run_infinitely` 会周期性输出多行，建议取除最后一次外的最近 10 次求平均。

## 环境实测信息

基于 `10.17.44.73`（`fpga44-73`，RHEL 9.1，Linux 5.14.0-162.6.1.el9_1.x86_64）：

| 项目 | 实测结果 |
|------|----------|
| perftest 包 | `perftest-4.5-0.20.gac7cca5.59056.x86_64` |
| 可用命令 | `ib_send_bw/lat`、`ib_read_bw/lat`、`ib_write_bw/lat`、`ib_atomic_bw/lat` |
| IB 设备 | `mlx5_0` ~ `mlx5_7` 共 8 个 |
| 端口状态 | ACTIVE，400 Gb/sec (4X NDR)，LinkUp |
| 默认监听端口 | 18515 |

## 常用参数速查（实测校准）

| 参数 | 含义 | 实测备注 |
|------|------|----------|
| `-d <dev>` | 指定设备，如 `mlx5_0` | 默认使用第一个可用设备 |
| `-i <port>` | 指定 IB 端口号 | 默认 1 |
| `-p <port>` | 指定监听/连接端口 | **默认 18515** |
| `-s <size>` | **消息大小（字节）** | BW 默认 65536；Lat 默认 2。**注意：不是 `-l`** |
| `-l <list>` | post list 大小 | 连续 post 的 WQE 数量，**不是包长** |
| `-q <num>` | QP 数量 | 默认 1 |
| `-D <sec>` | 测试持续时间 | 与 `-n` 二选一 |
| `-n <iters>` | 迭代次数 | 与 `-D` 二选一；send/read 默认 1000，write 默认 5000 |
| `-b` | 双向带宽测试 | server/client 均需加 |
| `-F` | 禁用 CPU 频率提示 | 建议常态化使用 |
| `-S <sl>` | 服务级别 | 两端必须一致 |
| `-x <idx>` | GID index | IB 默认无 gid，ETH 默认 0 |
| `-c <type>` | 连接类型 | RC/XRC/UC/UD/DC/SRD，**默认 RC** |
| `--report_gbits` | 以 Gbps 报告 | 便于与网卡速率对比 |
| `--run_infinitely` | 持续运行 | 需外部停止 |
| `-g` | 发送到多播组 | 配合 `-M` 指定 MGID |
| `-M <mgid>` | 多播组 GID | 示例：`255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:00` |
| `--use-srq` | 使用共享接收队列 | 多播/高并发场景可能用到 |

## 多播测试要点

IB 多播使用 `ib_send_bw` 的 `-g` 和 `-M` 参数：

```bash
# 服务端（加入多播组）
ib_send_bw -g -M 255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:00

# 客户端
ib_send_bw -g -M 255:01:00:00:00:02:201:133:00:00:00:00:00:00:00:00 <server_ip> \
  --pkey_index=<index> -S 1 -m 2048 -s 2048
```

注意事项：

1. **多播场景禁止使用 `-x` 参数**。`-x` 用于指定 GID 索引，但多播由 `-M` 指定 MGID，使用 `-x` 会导致参数冲突/失败。
2. 多播实际使用 **UD（Unreliable Datagram）** 传输服务，即使指定 `-c RC` 也会自动回落为 UD。
3. 多播本地 QPN 必须为 `0xFFFFFF`。
4. 多播数据包头部 SL 由子网管理器（SM）提供或派生，**禁止使用 VL15**。
5. 业务运行期间 `/var/log/opensm.log` 应出现 `trap_num 66/67`（多播组创建/删除）。
6. `ib_send_bw` 用户态多播业务完成后，**无需检测多播组数量新增/消失**；SA 查询仅在需要独立验证子网多播组状态时使用。

### 多播测试结果判定

使用 `ib_send_bw` 进行多播测试时，只要日志中存在**有效的 BW average（大于 0）**，以下异常内容应视为可忽略，**不判定为失败**：

- `failed to get mlid from MAD`
- `Couldn't Unregister the Mcast group on the SM`
- `Couldn't destroy all SEND resources`
- `received UMAD with an error`

Python 判定示例：

```python
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
    matches = pattern.findall(output)
    return any(float(m[3]) > 0 for m in matches)
```

## 各命令默认值差异

| 命令 | 默认 size | 默认 iters | 支持连接类型 |
|------|-----------|------------|--------------|
| `ib_send_bw` | 65536 | 1000 | RC/XRC/UC/UD/DC/SRD |
| `ib_send_lat` | 2 | 1000 | RC/XRC/UC/UD/DC/SRD |
| `ib_read_bw` | 65536 | 1000 | RC/XRC/DC |
| `ib_read_lat` | 2 | 1000 | RC/XRC/DC |
| `ib_write_bw` | 65536 | 5000 | RC/XRC/UC/DC |
| `ib_write_lat` | 2 | 1000 | RC/XRC/UC/DC |

> 写操作默认迭代次数为 5000，与 send/read 不同；解析结果时需注意。

## 常见错误与排查

### 1. `ib_send_bw -v` 卡住

**原因**：`-v` 在 perftest 中不是 version，执行后会启动服务端等待连接。

**解决**：查看版本用 `-V`：

```bash
ib_send_bw -V
```

### 2. 包长设置不生效

**原因**：误用 `-l` 作为包长。perftest 中 `-l` 是 post list，`-s` 才是消息大小。

**解决**：

```bash
# 正确：-s 2048 设置包长为 2048 字节
ib_send_bw -d mlx5_0 -s 2048

# 错误：-l 2048 会把 post list 设为 2048
```

### 3. 客户端连接失败

**排查步骤**：

1. 确认服务端已先启动并在监听端口（默认 18515）。
2. 确认两端使用相同端口：`-p <port>`。
3. 确认 IB 端口状态 ACTIVE：`ibstatus`。
4. 检查防火墙是否放行对应 TCP/UDP 端口。
5. 确认两端 `-S <sl>` 一致（如果使用了 SL）。

### 4. 带宽结果异常低

**可能原因**：

- CPU 频率未锁定：加 `-F`。
- 包长太小：尝试 `-s 65536` 或更大。
- QP 数量不足：尝试 `-q 4` 或更高。
- 使用了事件模式 `-e`：默认 poll 模式通常性能更好。

### 5. 多播测试收不到包

**排查**：

1. 确认 opensm 已启动并配置好多播组。
2. 确认使用 `ib_send_bw -g` 且 MGID 一致。
3. 检查是否指定了 VL15（应失败）。
4. 查看 `/var/log/opensm.log` 是否有 trap 66/67。

## Python 接口

```python
from scripts.nic100.linux.rdma.rdma_func import RdmaIO

# 基本用法
status, result = RdmaIO.perftest(dev='mlx5_0', opcode='send', perf_type='bw')

# 自定义参数
set_para = {
    'qp_type': 'RC',
    'qp_num': '2',
    'pkg_size': '65535',
    'pkg_num': '1000',
    'server_ip': '192.168.1.100',
}
status, result = RdmaIO.perftest(
    dev='mlx5_0', opcode='send', perf_type='bw', para_dict=set_para
)
```
