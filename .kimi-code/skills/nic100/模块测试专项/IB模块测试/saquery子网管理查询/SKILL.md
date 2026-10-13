---
name: saquery子网管理查询
description: 指导在NIC100框架下使用saquery查询IB子网管理信息，包括节点记录、多播组、多播成员、路径记录、SL2VL表等常见查询。
---

# saquery 子网管理查询

## 适用场景

- 查询 IB 子网中的节点、端口、链路、路径等 SA 记录
- 查看当前多播组（MCGroup）及其成员（MCMember）
- 验证 OpenSM 是否正确创建/删除多播组
- 配合 ib_send_bw / ib_send_lat 多播测试进行多播组状态校验

## 前置条件

- `opensm` 必须已启动并能管理本地 IB 端口
- 网卡需工作在 **IB 模式**（Link layer: InfiniBand）；Ethernet 模式下 opensm 会报 `No local ports detected`，saquery 无法绑定 SA
- 多设备环境下需指定目标 CA 与端口

## 命令基础

```bash
saquery [options] [query-name] [<name> | <lid> | <guid>]
```

默认查询 `NodeRecord`。

## 常用选项

| 选项 | 说明 |
|------|------|
| `-D, --list` | 列出本地 CA 的节点描述 |
| `-N` | 查询 NodeRecord |
| `-g` | 查询多播组信息（MCMemberRecord / MCGroup） |
| `-m <mlid>` | 查询指定多播组的成员 GID，例如 `saquery -m 0xC000` |
| `-p` | 查询 PathRecord |
| `-s` | 查询具有 isSM/isSMdisabled 能力的 PortInfoRecord |
| `-x` | 查询 LinkRecord |
| `-c` | 查询 SA 的 ClassPortInfo |
| `-S` | 查询 ServiceRecord |
| `-l <name>` | 返回指定名称的唯一 LID |
| `-L <name>` | 返回指定名称的所有 LID |
| `-G <name>` | 返回指定名称的 GUID |
| `-O <lid>` | 返回指定 LID 的节点名称 |
| `-U <guid>` | 返回指定 GUID 的节点名称 |

## 子网管理记录查询

支持直接指定查询名称（可缩写）：

| 查询名 | 别名 | 示例 |
|--------|------|------|
| NodeRecord | NR | `saquery NR 1` |
| PortInfoRecord | PIR | `saquery PIR 1/1` |
| SL2VLTableRecord | SL2VL | `saquery SL2VL 1/1/1` |
| PKeyTableRecord | PKTR | `saquery PKTR 1/1/0` |
| VLArbitrationTableRecord | VLAR | `saquery VLAR 1/1/0` |
| LinkRecord | LR | `saquery LR 1/1 2/1` |
| PathRecord | PR | `saquery PR` |
| MCMemberRecord | MCMR | `saquery MCMR` |
| MFTRecord | MFTR | `saquery MFTR 0xC000/0/0` |
| LFTRecord | LFTR | `saquery LFTR 1/0` |
| SMInfoRecord | SMIR | `saquery SMIR` |
| SwitchInfoRecord | SWIR | `saquery SWIR 1` |

## 多设备环境指定 CA/端口

当节点存在多个 IB 设备时，必须指定 `-C <ca>` 和 `-P <port>`，否则 saquery 可能无法绑定 SA 或绑定到错误设备：

```bash
saquery -C mlx5_0 -P 1 -g
saquery -C mlx5_0 -P 1 -m 0xC000
saquery -C mlx5_0 -P 1 -D
```

> 注意：`-C` 后接 CA 名（如 `mlx5_0`），`-P` 后接端口号（如 `1`）。

## 多播测试常用示例

```bash
# 列出当前所有多播组
saquery -C mlx5_0 -P 1 -g

# 查询指定多播组 0xC000 的成员 GID
saquery -C mlx5_0 -P 1 -m 0xC000

# 查询多播组成员记录
saquery -C mlx5_0 -P 1 MCMemberRecord

# ib_send_bw 多播业务启动前后对比多播组数量
saquery -C mlx5_0 -P 1 -g | wc -l
```

## 典型输出解读

### 多播组输出示例

```text
MGID:0xff12401fffff0000:00000000ffff0000  MLID:0xc000  PortGID:0xfe80000000000000:8c913a03004d2a54
```

- `MGID`：多播组 GID
- `MLID`：多播 LID（如 `0xc000`）
- `PortGID`：加入该多播组的端口 GID

### 多播成员输出示例

```text
saquery -m 0xC000
# 输出加入该多播组的成员 GID 列表
```

## 常见问题

### 1. `Failed to bind to the SA: No such file or directory`

**原因**：opensm 未启动。

**解决**：

```bash
opensm -B
```

### 2. `No SM/SA found on port (null):0`

**原因**：未指定 CA/端口，或指定设备未处于 IB 模式。

**解决**：

```bash
# 指定 CA/端口
saquery -C mlx5_0 -P 1 -g

# 确认 Link layer 为 InfiniBand
ibstat mlx5_0 | grep "Link layer"
```

### 3. `No local ports detected!`（opensm 日志）

**原因**：网卡当前为 Ethernet 模式，opensm 无法管理。

**解决**：需要将网卡切换到 IB 模式（加载 ipoib、配置固件等）。

## 自动化脚本建议

- 使用 `CommandOperation.execute_command_with_error` 执行 saquery。
- 多设备环境务必指定 `-C <ca> -P <port>`。
- 多播业务前后对比 `saquery -g` 输出，判断多播组是否正确创建/删除。
- 解析输出时优先正则匹配 `MGID:`、`MLID:`、`PortGID:` 等关键字。
- 失败时检查 opensm 状态和 `ibstat` 的 Link layer。

## 关联用例

- MC-9/MC-10：OpenSM 修改 SL2VL 后使用 `smpquery sl2vl -C mlx5_0 <base_lid> 1` 验证 SL2VL 表
- 任何需要独立验证子网多播组状态的场景（注意：`ib_send_bw` 用户态多播业务后不要求检测多播组数量新增/消失）

> 注：`sl2vl` 查询属于 `smpquery`，不属于 `saquery`。

## 参考

- 远程环境：`10.17.44.73`（`fpga44-73`，RHEL 9.1）
- 当前环境为 Ethernet 模式，saquery 需在 IB 模式下配合 opensm 使用
