---
name: IB模块测试
description: 指导NIC100框架下InfiniBand（IB）模块的测试要点、常用命令、端口概念、OpenSM组网、perftest性能测试、命令回显解析、PF配置与重启、自动化Bug记录等。
---

# NIC100 IB（InfiniBand）模块测试指南

## 测试范围

- IB 设备识别与状态检查
- IB 端口配置与状态切换
- OpenSM 子网管理器组网与 QoS 配置
- IB 性能测试（perftest 工具）
- PF/VF 配置、修改与验证
- GUID、LID 获取与使用
- 命令回显解析与错误判断
- 测试结果报告与自动化 Bug 记录

## 核心概念

### 端口概念（pport / vport）

- **pport（物理端口）**：双端口网卡的头两个 PF 同时是 pport 和 vport；单端口网卡只有第一个 PF 是 pport。
- **vport（虚拟端口）**：新增的 PF 为 vport。
- **非 pport 的 PF** 不需要执行 `smpquery`、`perfquery`、`ibportstate`、`mlxconfig` 等端口级命令。

### 线网与自发自收

- **线网**：通过网线/光纤进行数据包转发，至少需要两个网卡分别作为服务端和客户端。
- **自发自收**：自己发给自己，一个网卡同时作为服务端和客户端。

### GUID 与 LID

#### Node GUID 获取

- 使用 `ibstat` 命令获取，直接可用。
- 格式示例：`0x8c913a03004d2a55`。
- **不要**使用 `cat /sys/class/infiniband/{device}/node_guid`，可能格式不兼容。

#### LID 替换

- 用例中出现 `$lid` 的地方，需替换为真实测试环境中的 base LID。
- 通过 `ibstat` 查看对应端口的 `Base lid`。

### 设备数量统计

- `ibstat | grep CA` 获取的数量是实际数量的两倍。
- 正确做法：
  - `ibstat -l | wc -l`
  - 或 `ibstat | grep "CA '" | cut -d"'" -f2 | sort -u | wc -l`

## 核心命令

| 命令 | 用途 |
|------|------|
| `ibstat` | 查看 IB 设备状态、GUID、端口状态 |
| `ibstatus` | 查看端口链路状态 |
| `ibportstate` | 修改/查询端口状态 |
| `smpquery` | 子网管理查询 |
| `perfquery` | 性能计数器查询 |
| `opensm` | 启动子网管理器 |
| `ib_read_bw / ib_write_bw / ib_send_bw` | RDMA/IB 带宽测试 |
| `ib_read_lat / ib_write_lat / ib_send_lat` | RDMA/IB 延迟测试 |
| `mlxconfig` | 配置网卡 PF/VF 数量等 |

## OpenSM 子网管理器

### 安装

```bash
# Ubuntu/Debian
sudo apt-get install opensm rdma-core infiniband-diags

# CentOS/RHEL
sudo yum install opensm libibverbs-utils infiniband-diags
```

### 常用启动方式

```bash
# 前台启动
opensm

# 指定 GUID 启动（-g 后为 Node GUID）
opensm -g 0x8c913a03004d2a55

# 后台守护模式
opensm -B

# 指定配置文件、QoS、日志启动
opensm -g 0x8c913a03004d2a55 -B -e -Q -F /tmp/opensm.conf -f /var/log/opensm.log

# 通过 systemctl 启动
systemctl enable --now opensm
```

### 关键命令行参数

| 参数 | 说明 |
|------|------|
| `-g, --guid` | 绑定本地端口 GUID（可指定多个，最多 8 个） |
| `-c, --create-config` | 生成默认配置文件并退出 |
| `-F, --config` | 指定配置文件路径 |
| `-B, --daemon` | 后台守护模式 |
| `-Q, --qos` | 启用 QoS 配置 |
| `-Y, --qos_policy_file` | 指定 QoS 策略文件 |
| `-p, --priority` | 设置 SM 优先级（0-15，越高越优先） |
| `-l, --lmc` | 设置子网 LMC 值（0-7） |
| `-R, --routing_engine` | 选择路由引擎（updn、ftree、lash、dor 等） |
| `-o, --once` | 配置一次后退出 |
| `-s, --sweep` | 扫描间隔（秒，0 表示禁用） |
| `-f, --log_file` | 日志文件路径 |
| `-e, --erase_log_file` | 启动前删除已有日志 |
| `-D <flags>` | 日志详细级别（位标志） |

### 配置文件

- 默认配置位置：
  - Ubuntu/Debian：`/etc/rdma/opensm.conf`
  - CentOS/RHEL：`/etc/opensm/opensm.conf`
- 生成默认配置：`opensm -c /tmp/opensm.conf`

### QoS 配置

本产品要求 `max_op_vls` 必须设置为 **4**。推荐在配置文件末尾追加 QoS 参数块：

```text
# QoS default options
# max_op_vls is REQUIRED for this product - must be set to 4
max_op_vls 4
qos_max_vls 4
qos_high_limit 1
qos_vlarb_high 0:1,1:2,2:4,3:255
qos_vlarb_low 0:1,1:2,2:4,3:255
qos_sl2vl 0,1,2,3
```

修改普通参数时建议先查找再替换；QoS 参数推荐直接追加到文件尾部（opensm 使用最后出现的值）。

### 双端口组网

- 双端口网卡的前两个 PF（如 `mlx5_0`、`mlx5_1`）是 pport。
- 为每个 pport 分别指定 GUID 启动 OpenSM：

```bash
# 获取两个 pport 的 Node GUID
ibstat mlx5_0 | grep "Node GUID"
ibstat mlx5_1 | grep "Node GUID"

# 分别启动 OpenSM
nohup opensm -g 0x8c913a03004d2a55 -B -e -Q -F /tmp/opensm.conf -f /var/log/opensm_0.log &
nohup opensm -g 0x8c913a03004d2a56 -B -e -Q -F /tmp/opensm.conf -f /var/log/opensm_1.log &
```

### 状态验证与故障排查

- 验证子网启动：`grep "SUBNET UP" /var/log/opensm.log`
- 查看端口状态：`ibstat`，期望 `State: Active`、`Physical state: LinkUp`
- 查看 fabric 拓扑：`ibnetdiscover`
- 查看链路信息：`iblinkinfo`

常见排查思路：
- 设备无法进入 Active：检查 OpenSM 是否已启动、端口是否为 pport。
- 多 pport 组网失败：确认每个 pport 都被 OpenSM 扫描到。
- LID 获取失败：检查链路状态是否为 Active。
- 同一 fabric 上出现多个 active SM：确保每个子网只有一个主 SM，或正确配置优先级。

## perftest 性能测试

### 基本规则

- 所有 perftest 命令必须成对出现：先启动 server，再启动 client。
- 如果测试用例没有明确要求，默认执行 60 秒（使用 `-D 60`）。
- 建议增加 `-F` 参数，避免 CPU 频率相关提示干扰日志解析。

### 常用命令

| 命令 | 方向 | 测试指标 |
|------|------|----------|
| `ib_send_bw` | 发送带宽 | 带宽 |
| `ib_read_bw` | 读带宽 | 带宽 |
| `ib_write_bw` | 写带宽 | 带宽 |
| `ib_send_lat` | 发送延迟 | 延迟 |
| `ib_read_lat` | 读延迟 | 延迟 |
| `ib_write_lat` | 写延迟 | 延迟 |

### 常用参数

| 参数 | 说明 |
|------|------|
| `-d <dev>` | 指定设备，如 `mlx5_0` |
| `-i <port>` | 指定端口号 |
| `-p <port>` | 指定监听/连接端口 |
| `-s <size>` | 消息大小（字节） |
| `-q <num>` | QP 数量 |
| `-D <sec>` | 测试持续时间（秒） |
| `-n <iters>` | 迭代次数 |
| `-b` | 带宽测试模式 |
| `-F` | 禁用 CPU 频率提示 |
| `-S <sl>` | 服务级别（server/client 必须一致） |
| `--report_gbits` | 以 Gbps 为单位报告 |
| `--run_infinitely` | 持续运行，需外部停止 |

### 基础示例

```bash
# server
ib_read_bw -d mlx5_0 -b -F -p 18000

# client
ib_read_bw -d mlx5_0 -b -F -p 18000 <server_ip>
```

### 多线程并发执行

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

### 内存估算与参数调整

打流前需评估服务器空闲内存，再根据余量调整 `-q`（QP 数量）和 `-s`（包长）：

- **线网业务**：单条流内存 ≈ `2 * QP数量 * 包长`
- **自发自收业务**：单条流内存 ≈ `4 * QP数量 * 包长`
- 默认包长按 64KB（65536 字节）估算。

调整原则：
1. 预留至少 20%~30% 安全余量。
2. 优先降低 `-q`。
3. 次选降低 `-s`；注意包长会影响带宽结果。
4. 用例有明确要求时以用例为准。

### 结果重定向与成功判定

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

### 输出解析与带宽统计

perftest 三种常见运行方式：

1. **指定运行时间（`-D <seconds>`）**：输出只有一条最终统计行，直接取 `BW average[MB/sec]`。
2. **指定发包量（`-n <iters>`）**：输出只有一条最终统计行，取 `BW average[MB/sec]`。
3. **永久运行并被外部停止（`--run_infinitely`）**：会周期性输出多行统计，建议取**除最后一次之外的最近 10 次** `BW average[MB/sec]` 求平均，避免停止时末尾统计失真。

统一解析正则示例：

```python
import re

def parse_bandwidth_from_output(output):
    pattern = re.compile(
        r'^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)\s*$',
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

### Python 接口

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

## 网卡配置

### PF 数量修改

1. 使用 `mlxconfig` 修改 `NUM_OF_PF` 参数。
2. **必须重启服务器**才能生效；仅重新加载驱动或复位设备通常不足够。
3. 若当前 PF 数量与目标值相同，可跳过设置和重启（除非用例专门测试"设置为原值"场景）。

```python
current_pf = cls.get_pf_count(exec_addr)
if current_pf == target_pf_count:
    log.info(f"PF count is already {target_pf_count}, skipping configuration and reboot")
    continue
# 执行 mlxconfig 设置和重启
```

### 重启检测

执行 reboot 后不是立即重启，需注意检测时机：

1. 发送重启命令。
2. 等待约 30 秒让服务器开始重启流程。
3. 循环检测服务器是否上线（建议通过执行 `echo ping` 等命令并验证输出）。
4. 设置合理超时（如 300 秒）。

```python
reboot_cmd = "nohup sh -c 'sleep 2 && reboot' > /dev/null 2>&1 &"
CommandOperation.execute_command_with_error(reboot_cmd, exec_addr)
time.sleep(30)
if not cls.wait_for_server_availability(exec_addr, timeout=300):
    # 处理超时
```

### function 复位与恢复流程

对某个 function（PF/VF）进行复位及恢复时：

1. **复位命令**：
   ```bash
   echo 1 | sudo tee /sys/bus/pci/devices/$VF_BDF/reset
   ```
   - `$VF_BDF` 为待复位设备的 PCI BDF 地址，如 `0000:03:00.1`。

2. **等待设备从 `ibstat` 中消失**：
   ```bash
   while ibstat -l | grep -q "^${DEVICE_NAME}$"; do sleep 1; done
   ```

3. **停止所有 OpenSM 进程**：
   执行 `/etc/init.d/openibd force-restart` 前，必须先停止所有 OpenSM 进程，避免驱动重启过程中 OpenSM 与子网状态冲突：
   ```bash
   pkill -9 -f opensm
   ```

4. **恢复 IB 驱动**：
   ```bash
   /etc/init.d/openibd force-restart
   ```

5. **等待 10 秒**，让驱动和网络状态稳定后再继续操作。

## 命令处理

### 命令回显解析

#### mlxconfig 错误判断

- 正常回显中可能包含 "error" 字样，**不代表失败**。
- `-E-` 是 mlxconfig 明确的错误前缀，可作为判断失败的可靠依据。
- 如果命令重定向到文件，需用 `cat` 查看文件内容并检查是否符合预期。

#### 其他命令

- 仔细阅读正常回显示例，避免将正常输出中的 "error" 误判为失败。
- 对于关键命令，建议同时检查返回码和输出内容。

### 交互式命令处理

如果测试用例包含需要交互的命令（如需要输入 y/n），需改为非交互式：

- 使用 `-y`、`--yes`、`-f`、`--force` 等选项。
- 通过管道传递输入：`echo "y" | command`
- 使用 here document：`command << EOF\ny\nEOF`
- 在自动化脚本中使用 expect 模块或 `subprocess.Popen` 的 `stdin` 处理交互。

### 命令错误修正

发现用例中命令有误时，按以下顺序检查：

1. 命令语法是否正确。
2. 参数格式是否符合要求。
3. 设备名称是否正确（`mlx5_0`、`mlx5_1` 等）。
4. 命令选项是否适用（例如 `-C` vs `-d`）。
5. 执行环境是否正确（server vs client）。

### 文件重定向检查

某些命令输出重定向到文件后，需使用 `cat` 查看文件内容并判断是否符合预期，不能仅依赖命令返回码。

## 测试代码生成

- 每个用例应是一个独立的 `.py` 文件。
- 不要重复生成基类，只继承使用。
- 脚本名与用例编号对应，如 `multi_pf_test_tc002.py`。
- 遵循项目既有代码风格，包含 `prepare` / `do` / `post` 三阶段。
- 按「缺陷自动记录」skill 的要求补充 Bug 记录代码。

## 测试结果与 Bug 记录

### 结果报告要求

所有用例执行结束必须明确提示结果：

- 成功：输出 "测试执行成功" 或类似明确的成功状态信息。
- 失败：输出 "测试执行失败" 并附带简要描述失败原因。
- 提供完整的测试执行结果摘要，包括通过的步骤和失败的步骤。
- 面向测试人员的打印信息应尽量使用中文，避免中英文混用。

### 必须提 Bug 的情况

以下非脚本自身问题导致的失败，必须自动提交 Bug：

- 设备命令执行失败（如 `mlxconfig`、`ibstat` 返回非零）。
- 网络配置不符合预期（PF 数量不对、设备状态非 Active）。
- 性能测试不达标。
- 组网失败（opensm 无法启动、设备无法进入 Active）。
- 硬件相关问题（设备不可见、GUID 获取失败）。

### 不应提 Bug 的情况

脚本自身语法错误、逻辑错误、导入错误、配置错误等代码问题，应直接修复脚本。

### Bug 记录流程

```python
# 步骤1: 设置 bug 类型
cls.set_bug_type("Function")

# 步骤2: 设置 bug 字段
cls.bug_result = "实际观察到的结果"
cls.bug_expect = "期望的结果"

# 步骤3: 调用 create_bug 抛出异常
cls.create_bug("详细的问题描述")
```

详细规则参考「缺陷自动记录」skill。

## 脚本位置

- 相关脚本：`ps3/test/esat/nic100/scripts/nic100/linux/rdma/`
- 公共库：`ps3/test/esat/nic100/scripts/script_libs/rdma_core_tool.py`

## 使用场景

- 执行 InfiniBand 性能测试
- 配置和管理 mlx5 网卡
- 进行 RDMA 网络调试
- 分析命令回显结果
- 生成测试脚本
- 修正测试用例中的命令错误
- IB/RDMA 网络层问题定位

## 注意事项

1. mlxconfig 正常回显中可能包含 "error"，不代表失败；`-E-` 前缀才是明确错误。
2. 修改 PF 数量后必须重启服务器才能生效。
3. 执行 reboot 后需等待约 30 秒再检测服务器是否上线。
4. 检测上线时不仅看返回码，还要验证命令输出内容。
5. perftest 命令必须 server/client 成对使用。
6. 指定 SL 时 server 端和 client 端都必须加 `-S`，且值一致。
7. OpenSM 双端口组网时，需为每个 pport 分别指定 GUID。
