---
name: IB基础概念与设备检查
description: 指导NIC100框架下IB模块的端口概念、GUID/LID获取、设备状态检查与数量统计。
---

# IB 基础概念与设备检查

## 端口概念（pport / vport）

- **pport（物理端口）**：双端口网卡的头两个 PF 同时是 pport 和 vport；单端口网卡只有第一个 PF 是 pport。
- **vport（虚拟端口）**：新增的 PF 为 vport。
- **非 pport 的 PF** 不需要执行 `smpquery`、`perfquery`、`ibportstate`、`mlxconfig` 等端口级命令。

### pport 识别方法

```python
def get_pport_list(pf_list, pport_count=2):
    """从 PF 列表中识别所有 pport

    双端口网卡前两个 PF 为 pport；单端口网卡仅第一个 PF 为 pport。
    通过 pport_count 控制，默认取前 2 个（不足则取全部）。
    """
    return pf_list[:min(pport_count, len(pf_list))]
```

实际使用时应先获取全部 PF 列表：

```bash
ibstat -l
```

多播测试前需为每个 pport 启动并验证 opensm。

## 线网与自发自收

- **线网**：通过网线/光纤进行数据包转发，至少需要两个网卡分别作为服务端和客户端。
- **自发自收**：自己发给自己，一个网卡同时作为服务端和客户端。

## GUID 与 LID

### Node GUID 获取

- 使用 `ibstat` 命令获取，直接可用。
- 格式示例：`0x8c913a03004d2a55`。
- **不要**使用 `cat /sys/class/infiniband/{device}/node_guid`，可能格式不兼容。

```bash
ibstat mlx5_0 | grep "Node GUID"
```

### LID 替换

- 用例中出现 `$lid` 的地方，需替换为真实测试环境中的 base LID。
- 通过 `ibstat` 查看对应端口的 `Base lid`。

```bash
ibstat mlx5_0 | grep "Base lid"
```

## 设备数量统计

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
| `saquery` | SA（子网管理器）记录查询 |
| `opensm` | 启动 OpenSM 子网管理器 |

## opensm 启动规范

- 修改 opensm 配置时，**应先用 `opensm -c <path>` 生成默认配置文件，再基于默认配置修改或追加 QoS 参数**，避免手写缺省参数导致遗漏。
- 单设备环境可直接使用 `opensm -B`；**多设备环境必须指定目标设备 GUID**，避免 opensm 绑定到错误端口：

  ```bash
  opensm -g <node_guid> -B
  ```

- Node GUID 应通过 `ibstat <device> | grep "Node GUID"` 获取，格式示例：`0x8c913a03004d2a55`。
- 不推荐使用 `cat /sys/class/infiniband/{device}/node_guid` 获取 GUID，格式可能与 opensm 不兼容。
- 后台启动示例：

  ```bash
  nohup opensm -g 0x8c913a03004d2a55 -B > /var/log/opensm.log 2>&1 &
  ```

- 启动后应检查 opensm 进程是否持续运行：

  ```bash
  pgrep -x opensm >/dev/null 2>&1
  ```

  若未检测到进程，应记录失败。

- 若通过 opensm 修改了 SL2VL 等配置，启动后应使用 `smpquery` 验证配置是否真正生效，例如：

  ```bash
  # 获取 base lid
  base_lid=$(ibstat mlx5_0 | grep "Base lid" | awk '{print $NF}')

  # 查询 SL2VL 表
  smpquery sl2vl -C mlx5_0 ${base_lid} 1
  ```

  典型输出：

  ```text
  # SL2VL table: Lid 1
  #     SL: | 0| 1| 2| 3| 4| 5| 6| 7| 8| 9|10|11|12|13|14|15|
  # ports: in 0, out 0: | 0| 1| 0| 1| 0| 1| 0| 1| 0| 1| 0| 1| 0| 1| 0| 1|
  ```

  **注意**：
  - 第一行 `SL: | 0| 1| ...|15|` 只是 SL 索引，**不是 VL 值**
  - 真正的 VL 值在 `ports: in 0, out 0:` 这一行后面
  - 解析时应去掉前两个端口编号 `0, 0`，取后面 16 个数字作为 SL0~15 的 VL 映射

- 配置 `qos_sl2vl` 时，必须同时设置 `max_op_vls` 和 `qos_max_vls`，否则 SL2VL 表可能不会按预期生效。

## 多设备环境命令指定目标设备

当节点存在多个 IB 设备时，以下命令应使用 `-C <ca> -P <port>` 指定目标设备：

- `perfquery -C mlx5_0 -P 1 -r`
- `saquery -C mlx5_0 -P 1 -g`
- `smpquery pi -C mlx5_0 1 1`（LID 需替换为实际 base lid）

> 注意：`-C` 后接 CA 名（如 `mlx5_0`），`-P` 后接端口号（如 `1`）。

## 设备名读取（避免硬编码）

测试脚本**不应**直接硬编码 `mlx5_0` / `mlx5_1` 等设备名，而应通过 `env_config.ini` 中的 `[relationships_rdma]` 读取。NIC100 框架提供 `CommonOperation.get_nic_relationships()` 接口：

```python
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import RdmaMode

server_relations, client_relations = CommonOperation.get_nic_relationships(
    rdma=True, nic_mode=RdmaMode.Infiniband.value
)
server_device = server_relations[0].strip() if server_relations else ""
client_device = client_relations[0].strip() if client_relations else ""
```

### 注意事项

1. 必须在 `ScriptBase.__update_env_config()` 之后调用，通常放在 `check_own_environment()` 中读取。
2. 若读取不到设备名或设备不存在，应设置 `own_environment_enabled = False` 并返回。
3. `ib_send_bw -d <dev>`、`ibstat <dev>`、`smpquery -C <dev>` 等命令都应使用读取到的动态设备名。

## 设备状态检查 checklist

1. 设备是否可见：`ibstat -l`
2. 端口状态是否为 Active：`ibstat mlx5_0 | grep State`
3. Physical state 是否为 LinkUp：`ibstat mlx5_0 | grep "Physical state"`
4. Base lid 是否正常获取：`ibstat mlx5_0 | grep "Base lid"`
5. Node GUID 格式是否正确：`ibstat mlx5_0 | grep "Node GUID"`
6. IB 设备与 netdev 映射：`ibdev2netdev`

## IB 设备与 netdev 映射

使用 `ibdev2netdev` 查看 IB 设备对应的内核网络接口：

```bash
ibdev2netdev
```

典型输出：

```text
mlx5_0 port 1 ==> ib0 (Up)
mlx5_1 port 1 ==> ib1 (Up)
```

### 模式识别

- **IB 模式**：`ibdev2netdev` 输出 `ib*` 接口，例如 `mlx5_0 port 1 ==> ib0 (Up)`。
- **Ethernet 模式**：输出 `ens*` / `eth*` 等以太网接口，例如 `mlx5_0 port 1 ==> ens9f0np0 (Up)`。

如果期望进行 ipoib 多播测试但 `ibdev2netdev` 显示以太网接口，说明网卡未工作在 IB 模式，需检查驱动加载或固件配置。

## 常见问题

- **LID 获取失败**：检查链路状态是否为 Active。
- **设备数量翻倍**：使用 `ibstat -l | wc -l` 而不是 `ibstat | grep CA`。
- **命令报错找不到设备**：确认设备名称是 `mlx5_0`、`mlx5_1` 等，不是 vport 设备。
