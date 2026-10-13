---
name: rdma工具使用
description: 指导在NIC100框架下使用rdma工具查看和管理RDMA设备、链路、资源、命名空间及统计计数器。
---

# rdma 工具使用

## 适用场景

- 查看本地 RDMA 设备、链路状态与固件信息
- 查看内核 RDMA 资源占用（QP、CQ、MR、PD 等）
- 查看驱动层 RDMA 统计计数器
- 管理 RDMA 设备的 network namespace 模式
- 自动化脚本中替代传统 `ibstat`/`ibstatus` 获取结构化输出

## 命令基础

```bash
rdma [ OPTIONS ] OBJECT { COMMAND | help }
rdma [ -force ] -batch filename
```

### 全局 OPTIONS

| 选项 | 说明 |
|------|------|
| `-V` / `-Version` | 显示版本并退出 |
| `-d` / `-details` | 输出详细信息，重复一次可包含驱动特定详情 |
| `-r` / `-raw` | 以原始格式输出驱动特定详情 |
| `-j` / `-json` | 输出 JSON 格式 |
| `-p` / `-pretty` | 与 `-j` 配合生成格式化 JSON |
| `-b` / `-batch <file>` | 从文件批量读取并执行命令 |
| `-force` | 批量模式下遇到错误不终止 |

### 顶层 OBJECT

| 对象 | 说明 |
|------|------|
| `dev` | RDMA 设备 |
| `link` | RDMA 端口/链路 |
| `resource` | RDMA 资源 |
| `system` | RDMA 子系统相关 |
| `statistic` | RDMA 统计计数器 |
| `help` | 帮助 |

> 对象名可缩写，例如 `stats`、`stat`、`s` 均可表示 `statistic`。

## 各 OBJECT 详解

### dev — 设备管理

```bash
rdma dev show [DEV]                          # 查看设备
rdma dev set [DEV] name DEVNAME              # 重命名设备
rdma dev set [DEV] netns NSNAME              # 将设备移入指定 network namespace
rdma dev set [DEV] adaptive-moderation [on|off]  # 开关自适应中断节制
```

**常见输出字段**：

| 字段 | 说明 |
|------|------|
| `node_type` | 节点类型，如 `ca`（Channel Adapter） |
| `fw` | 固件版本 |
| `node_guid` | 节点 GUID |
| `sys_image_guid` | 系统镜像 GUID |
| `adaptive-moderation` | 自适应中断节制状态 |
| `caps` | 设备能力标志（需 `-d`） |

### link — 链路/端口管理

```bash
rdma link show [DEV/PORT_INDEX]              # 查看链路状态
rdma link add NAME type TYPE netdev NETDEV   # 添加软 RDMA 链路（如 rxe）
rdma link delete NAME                        # 删除链路
```

**常见输出字段**：

| 字段 | 说明 |
|------|------|
| `state` | 逻辑状态：`ACTIVE` / `DOWN` |
| `physical_state` | 物理状态：`LINK_UP` / `DISABLED` / `POLLING` |
| `netdev` | 关联的网络接口名 |

### resource — 资源查看

```bash
rdma resource show [DEV]                     # 汇总所有资源
rdma resource show [qp|cm_id|pd|mr|cq|ctx|srq]  # 按类型查看
rdma resource show qp link [DEV/PORT] [FILTER-NAME FILTER-VALUE]
rdma resource show cq link [DEV/PORT] [FILTER-NAME FILTER-VALUE]
rdma resource show pd dev [DEV] [FILTER-NAME FILTER-VALUE]
rdma resource show mr dev [DEV] [FILTER-NAME FILTER-VALUE]
rdma resource show ctx dev [DEV] [FILTER-NAME FILTER-VALUE]
rdma resource show srq dev [DEV] [FILTER-NAME FILTER-VALUE]
```

**资源类型**：

| 类型 | 全称 |
|------|------|
| `qp` | Queue Pair |
| `cq` | Completion Queue |
| `mr` | Memory Region |
| `pd` | Protection Domain |
| `cm_id` | Connection Manager ID |
| `ctx` | Context |
| `srq` | Shared Receive Queue |

**过滤器**：`cntn`、 `lqpn`、 `pid`

### system — 子系统配置

```bash
rdma system show [ netns ]                   # 查看当前网络命名空间模式
rdma system set netns { shared | exclusive } # 设置命名空间模式
```

**模式说明**：

| 模式 | 说明 |
|------|------|
| `shared` | 多个 netns 可共享同一 RDMA 设备 |
| `exclusive` | RDMA 设备独占绑定到某个 netns |

### statistic — 统计计数器

```bash
rdma statistic show                          # 查看链路统计
rdma statistic show link [DEV/PORT_INDEX]    # 查看指定端口统计
rdma statistic mode [ supported ]            # 查看计数器模式
rdma statistic mode [ supported ] link [DEV/PORT]
rdma statistic set link [DEV/PORT] optional-counters [COUNTERS]
rdma statistic unset link [DEV/PORT] optional-counters
```

**QP 级别统计**（较高级用法）：

```bash
rdma statistic qp show
rdma statistic qp show link mlx5_2/1
rdma statistic qp mode
rdma statistic qp set link mlx5_2/1 auto type on
rdma statistic qp bind link mlx5_2/1 lqpn 178
rdma statistic qp unbind link mlx5_2/1 cntn 4
```

## 常用示例

```bash
# 查看所有 RDMA 设备
rdma dev show

# 查看设备详细信息（含能力标志）
rdma dev show -d

# 查看所有 RDMA 链路状态
rdma link show

# 查看指定端口链路
rdma link show mlx5_0/1

# 查看所有资源汇总
rdma resource show

# 查看指定设备的 QP
rdma resource show qp link mlx5_0/1

# 查看链路统计
rdma statistic show
rdma statistic show link mlx5_0/1

# 查看网络命名空间模式
rdma system show netns

# JSON 输出便于脚本解析
rdma -j -p dev show
rdma -j -p link show
rdma -j -p statistic show
```

## 典型测试用法

### 检查设备与链路健康

```bash
rdma dev show
rdma link show
```

### 检查资源是否泄漏

```bash
rdma resource show
rdma resource show qp link mlx5_0/1
```

### 检查端口统计与错误

```bash
rdma statistic show link mlx5_0/1
```

### 批量执行命令

```bash
cat > /tmp/rdma_cmds.txt <<EOF
dev show
link show
resource show
system show netns
EOF
rdma -batch /tmp/rdma_cmds.txt
```

## 与 perfquery / smpquery 的关系

| 工具 | 层级 | 查询内容 | 典型用途 |
|------|------|----------|----------|
| `rdma` | Linux 内核 / 驱动层 | 设备、链路、内核资源、驱动统计 | 本地设备管理、链路排查、资源监控 |
| `smpquery` | IB 子网管理协议（SMP） | 节点信息、端口信息、PKey、SL2VL、VLArb | IB fabric 拓扑与配置查询 |
| `perfquery` | IB 性能管理（PerfMgt GMP） | 端口性能/错误计数器 | 性能监控、错误统计、拥塞分析 |

## 自动化脚本建议

- 优先使用 `rdma -j -p` 获取 JSON 输出，便于 Python `json.loads()` 解析。
- 链路健康检查重点判断 `state == ACTIVE` 且 `physical_state == LINK_UP`。
- 资源泄漏排查可周期性采集 `rdma resource show` 并对比 QP/CQ/MR 数量变化。
- 驱动统计计数器重点关注 `rnr_nak_retry_err`、`packet_seq_err`、`local_ack_timeout_err`、`resp_cqe_error`、`req_remote_access_errors` 等错误字段。
- 批量模式下建议加 `-force`，避免单条命令失败导致整体中断。
