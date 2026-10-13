---
name: OpenSM组网与QoS
description: 指导NIC100框架下OpenSM子网管理器的安装、启动、QoS配置、双端口组网与故障排查。
---

# OpenSM 组网与 QoS

## 安装

```bash
# Ubuntu/Debian
sudo apt-get install opensm rdma-core infiniband-diags

# CentOS/RHEL
sudo yum install opensm libibverbs-utils infiniband-diags
```

## 常用启动方式

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

## 关键命令行参数

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

## 配置文件

- 默认配置位置：
  - Ubuntu/Debian：`/etc/rdma/opensm.conf`
  - CentOS/RHEL：`/etc/opensm/opensm.conf`
- 生成默认配置：`opensm -c /tmp/opensm.conf`

### 修改配置文件的规范

1. **先生成默认配置，再做修改**：使用 `opensm -c <path>` 生成默认配置文件，避免手写缺省参数。
2. **普通参数建议查找替换**：如已存在同名参数，建议先 `grep` 定位再修改。
3. **QoS 参数推荐追加到文件尾部**：opensm 使用最后出现的值，追加 QoS 块可覆盖默认值而不破坏原文件结构。

示例：

```bash
# 1. 生成默认配置
opensm -c /tmp/opensm_base.conf

# 2. 追加 QoS 参数块（覆盖默认值）
cat >> /tmp/opensm_base.conf << 'EOF'
# QoS override
qos TRUE
max_op_vls 16
qos_max_vls 16
qos_sl2vl 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15
EOF

# 3. 使用修改后的配置启动 opensm
opensm -g 0x8c913a03004d2a55 -Q -F /tmp/opensm_base.conf -B
```

> 注意：`max_op_vls` 和 `qos_max_vls` 需同时设置，否则 `qos_sl2vl` 可能不会按预期生效。

## QoS 配置

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

### `qos_sl2vl` 实际生效规则

`qos_sl2vl` 配置的 VL 值最终是否生效，受端口实际支持的 `OperVLs` 数量限制。应通过 `smpquery portinfo` 查询 `OperVLs` 字段确认：

```bash
smpquery portinfo -C mlx5_0 0x1 1 | grep OperVLs
# 典型输出：OperVLs:.........................VL0-3
```

实际生效规则（已在本项目测试环境中验证）：

- **配置值 < 15**：按实际 `OperVLs` 数量取模。例如 `OperVLs=VL0-3`（4 个 VL）时，配置值 `14` 实际生效为 `14 % 4 = 2`。
- **配置值 = 15**：opensm 会保留 `15`，不会取模。此值通常用于构造无效 VL 场景（如 MC-9 验证 SL15->VL15 时业务按预期失败）。
- 未显式配置的 SL 使用默认映射：`SL % OperVLs`。

因此，自动化脚本验证 SL2VL 表时，**不能简单硬编码 16 个 VL 的期望**，应：

1. 查询 `OperVLs` 获取实际 VL 数量。
2. 根据配置的 `qos_sl2vl` 值和上述规则计算期望表。
3. 与 `smpquery sl2vl` 解析结果对比。

示例（MC-10 配置 `0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,14`，OperVLs=4）：

```text
期望 SL2VL 表 = [0,1,2,3,0,1,2,3,0,1,2,3,0,1,2,2]
```

## 双端口组网

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

## 多播测试前的 OpenSM 准备（多 pport）

多播测试（MC-11 / MC-14 ~ MC-41 等）应确保**每个 pport 都启动并持续运行一个 opensm 实例**。推荐在 `prepare()` 中执行一次，在每次多播业务前再做保守检查（必要时重启）。

### pport 识别

```python
def get_pport_list(pf_list, pport_count=2):
    """双端口网卡前两个 PF 为 pport；单端口仅第一个为 pport"""
    return pf_list[:min(pport_count, len(pf_list))]
```

### 为每个 pport 启动 OpenSM

```python
def start_opensm_for_pports(exec_addr, pport_list):
    for idx, pport in enumerate(pport_list):
        guid = ibstat(pport) | grep "Node GUID"
        cmd = (
            f"nohup opensm -g {guid} -B -e "
            f"-f /var/log/opensm_p{idx}.log > /dev/null 2>&1 &"
        )
        CommandOperation.execute_command_with_error(cmd, exec_addr)
        time.sleep(3)
    time.sleep(10)  # 等待子网扫描完成
```

### 验证 OpenSM 运行

```python
def verify_opensm_for_pports(exec_addr, pport_list):
    status, result, _ = CommandOperation.execute_command_with_error(
        "pgrep -x opensm", exec_addr
    )
    running_count = len([line.strip() for line in result.splitlines() if line.strip()])
    if running_count < len(pport_list):
        raise RuntimeError(
            f"opensm 进程数不足：实际 {running_count}，期望至少 {len(pport_list)}"
        )
```

### 保守检查（每次业务前）

```python
def ensure_opensm_for_pports(exec_addr, pport_list):
    if not is_opensm_running(exec_addr):
        restart_opensm(exec_addr, pport_list)
    else:
        status, result, _ = CommandOperation.execute_command_with_error(
            "pgrep -x opensm", exec_addr
        )
        running_count = len([line.strip() for line in result.splitlines() if line.strip()])
        if running_count < len(pport_list):
            restart_opensm(exec_addr, pport_list)
    verify_opensm_for_pports(exec_addr, pport_list)
```

## 状态验证与故障排查

- 验证子网启动：`grep "SUBNET UP" /var/log/opensm.log`
- 查看端口状态：`ibstat`，期望 `State: Active`、`Physical state: LinkUp`
- 查看 fabric 拓扑：`ibnetdiscover`
- 查看链路信息：`iblinkinfo`
- 验证 SL2VL 配置是否生效：

  ```bash
  base_lid=$(ibstat mlx5_0 | grep "Base lid" | awk '{print $NF}')
  smpquery sl2vl -C mlx5_0 ${base_lid} 1
  ```

  注意：`SL: | 0| 1| ...|15|` 只是 SL 索引，真正的 VL 值在 `ports: in 0, out 0:` 行后面。

常见排查思路：
- 设备无法进入 Active：检查 OpenSM 是否已启动、端口是否为 pport。
- 多 pport 组网失败：确认每个 pport 都被 OpenSM 扫描到。
- LID 获取失败：检查链路状态是否为 Active。
- 同一 fabric 上出现多个 active SM：确保每个子网只有一个主 SM，或正确配置优先级。
