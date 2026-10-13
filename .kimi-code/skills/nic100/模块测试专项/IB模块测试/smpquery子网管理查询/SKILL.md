---
name: smpquery子网管理查询
description: 指导在NIC100框架下使用smpquery查询IB子网管理属性，包括节点信息、端口信息、交换机信息、PKey/SL2VL/VL仲裁表等。
---

# smpquery 子网管理查询

## 适用场景

- 查询 IB 网络中节点、端口、交换机的子网管理属性
- 验证链路速率、宽度、状态等端口参数
- 检查 QoS 相关配置（SL2VL、VL Arbitration）
- 检查 PKey 分区表配置
- 配合自动化脚本进行拓扑发现与配置校验

## 命令基础

```bash
smpquery [options] <op> <dest dr_path|lid|guid> [op params]
```

| 位置参数 | 说明 |
|----------|------|
| `<op>` | 查询操作，大小写不敏感，支持别名 |
| `<dest>` | 目标地址：直接路由 `dr_path`、LID 或 GUID |
| `[op params]` | 操作额外参数，常见为 `<portnum>` |

## 支持的操作

| 操作 | 别名 | 参数 | 用途 |
|------|------|------|------|
| `NodeInfo` | `NI` | `<addr>` | 节点基本信息（设备 ID、GUID、端口数等） |
| `NodeDesc` | `ND` | `<addr>` | 节点描述字符串 |
| `PortInfo` | `PI` | `<addr> [<portnum>]` | 端口信息，默认端口 0 |
| `PortInfoExtended` | `PIE` | `<addr> [<portnum>]` | 扩展端口信息 |
| `SwitchInfo` | `SI` | `<addr>` | 交换机信息 |
| `PKeyTable` | `PKeys` | `<addr> [<portnum>]` | PKey 分区表 |
| `SL2VLTable` | `SL2VL` | `<addr> [<portnum>]` | SL 到 VL 映射表 |
| `VLArbitration` | `VLArb` | `<addr> [<portnum>]` | VL 仲裁表 |
| `GUIDInfo` | `GI` | `<addr>` | GUID 信息 |
| `MlnxExtPortInfo` | `MEPI` | `<addr> [<portnum>]` | Mellanox 扩展端口信息，默认端口 0 |

## 常用选项

### 寻址方式

| 选项 | 说明 |
|------|------|
| `-D` / `--Direct` | 直接路由寻址，如 `0` 或 `0,1,2,1,4` |
| `-L` / `--Lid` | 地址参数为 LID |
| `-G` / `--Guid` | 地址参数为 GUID |
| `-c` / `--combined` | 组合路由寻址，格式 `<lid> <DR_Path>` |
| `-s <smlid>` | 指定 SM 端口 LID |

### 本地端口选择

| 选项 | 说明 |
|------|------|
| `-C <ca>` | 指定本地 CA 名 |
| `-P <port>` | 指定本地 CA 端口号 |

### 查询控制

| 选项 | 说明 |
|------|------|
| `-x` / `--extended` | 设置 `SMSupportsExtendedSpeeds` bit 31，仅影响 `PortInfo` 查询 |
| `-K` / `--show_keys` | 在输出中显示安全密钥（mkey、smkey 等） |
| `-y <key>` | 请求使用的 M_Key |
| `--node-name-map <file>` | 指定 GUID 到友好名称的映射文件 |

### 调试与配置

| 选项 | 说明 |
|------|------|
| `-t <ms>` | 超时时间 |
| `-z <file>` | 指定配置文件，默认 `/etc/infiniband-diags/ibdiag.conf` |
| `-v` / `-d` | 增加 verbose / debug 级别 |
| `-e` | 显示发送/接收错误 |
| `-V` / `-h` | 版本 / 帮助 |

## 重要注意事项

1. **操作名大小写不敏感**，支持别名。例如 `smpquery nodeinfo 3` 与 `smpquery NI 3` 等价。

2. **默认端口为 0**  
   `PortInfo`、`PortInfoExtended`、`MlnxExtPortInfo` 等操作若省略 `<portnum>`，默认查询端口 0。

3. **直接路由路径的第二个数字必须匹配本地使用的端口**  
   例如 `-D "0,1,2,1,4"` 中的 `1` 需与 `-P` 指定端口或自动选择的端口一致。

4. **`-x` 仅影响 PortInfo 查询**  
   该选项设置 AttributeModifier 的 ExtendedSpeeds 支持位，用于获取扩展速率信息。

5. **节点名称映射文件**  
   通过 `--node-name-map` 可将 GUID 映射为可读名称，便于识别交换机/网卡。

## 常用示例

```bash
# 按 LID 查询端口 1 的 PortInfo
smpquery portinfo 3 1

# 按 GUID 查询交换机信息
smpquery -G switchinfo 0x2C9000100D051 1

# 按直接路由查询本节点信息
smpquery -D nodeinfo 0

# 按组合路由查询节点信息
smpquery -c nodeinfo 6 0,12

# 查询节点描述
smpquery nodedesc 3

# 查询 PKey 表
smpquery pkeytable 3 1

# 查询 SL2VL 映射表
smpquery sl2vltable 3 1

# 显示安全密钥
smpquery -K portinfo 3 1

# 查询扩展端口信息
smpquery portinfoextended -x 3 1
```

## 典型测试用法

### 拓扑与设备识别

```bash
# 获取目标节点基本信息
smpquery nodeinfo 3

# 获取目标节点描述
smpquery nodedesc 3
```

### 端口参数检查

```bash
# 查询端口信息
smpquery portinfo 3 1

# 查询扩展端口信息（带扩展速率支持）
smpquery -x portinfo 3 1
```

### QoS 配置验证

```bash
# 检查 SL 到 VL 映射
smpquery sl2vltable 3 1

# 检查 VL 仲裁策略
smpquery vlarbitration 3 1
```

### SL2VL 输出解析

`smpquery sl2vl` 典型输出如下：

```text
# SL2VL table: Lid 1
#                 SL: | 0| 1| 2| 3| 4| 5| 6| 7| 8| 9|10|11|12|13|14|15|
ports: in  0, out  0: | 0| 1| 2| 3| 0| 1| 2| 3| 0| 1| 2| 3| 0| 1| 2| 3|
```

解析要点：

- 第一行 `SL: | 0|...|15|` 是 SL 索引，**不是 VL 值**。
- 真正的 VL 值在 `ports: in 0, out 0:`（实际可能有额外空格，如 `in  0, out  0`）这一行后面。
- 数据行包含前两个端口编号（in/out），解析时应跳过，取后面的 16 个 VL 值。
- 若解析失败，应将原始输出打印到日志以便排查。

Python 解析示例：

```python
import re

def parse_sl2vl_table(output: str) -> list | None:
    for line in output.splitlines():
        if "ports:" in line and "out" in line:
            numbers = [int(x) for x in re.findall(r"\b(\d+)\b", line)]
            if len(numbers) >= 18:
                return numbers[2:18]   # 跳过 in/out 端口编号
            if len(numbers) >= 16:
                return numbers[-16:]
    return None
```

### 查询实际支持的 VL 数量

验证 SL2VL 配置时，应同时查询端口 `OperVLs` 以确认实际可用 VL 范围：

```bash
smpquery portinfo -C mlx5_0 0x1 1 | grep OperVLs
```

典型输出 `OperVLs: VL0-3` 表示该端口实际只支持 4 个 VL（0~3）。此时 `qos_sl2vl` 中除 `15` 以外的配置值会按 `OperVLs` 数量取模生效。

### 分区配置验证

```bash
# 检查端口 PKey 表
smpquery pkeytable 3 1
```

## 与 perfquery 的关系

| 维度 | smpquery | perfquery |
|------|----------|-----------|
| 查询对象 | 子网管理属性（节点、端口、交换、PKey、SL2VL 等） | 性能/错误计数器 |
| 协议 | SMP | PerfMgt GMP |
| 典型用途 | 拓扑发现、配置检查、链路参数确认 | 性能监控、错误统计、拥塞分析 |
| 输出特点 | 人类可读的结构化字段 | 计数器数值 |

## 自动化脚本建议

- 执行命令时使用框架的 `CommandOperation.execute_command_with_error` 或 `RdmaIO` 相关封装。
- 解析输出时优先匹配关键字段名，避免依赖固定列宽。
- 远端查询需确认目标节点可达且子网管理正常。
- 对需要多次查询同一节点的场景，建议先获取 LID/GUID，再用统一地址方式查询，减少解析复杂度。
