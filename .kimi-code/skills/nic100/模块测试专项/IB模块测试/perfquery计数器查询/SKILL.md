---
name: perfquery计数器查询
description: 指导在NIC100框架下使用perfquery查询IB/RoCE端口性能计数器、错误计数器及扩展计数器，涵盖常见用法、清零技巧与输出解读。
---

# perfquery 计数器查询

## 适用场景

- 查询本地或远端 IB/RoCE 端口的性能/错误计数器
- 测试前后采集计数器基线，判断是否存在异常增长
- 定位丢包、错包、拥塞等 IB 网络问题
- 配合自动化脚本周期性采样并断言关键计数器

## 命令基础

```bash
perfquery [options] [<lid|guid> [[port(s)] [reset_mask]]]
```

| 位置参数 | 说明 |
|----------|------|
| `lid\|guid` | 目标节点地址；省略时读取本地端口 |
| `port(s)` | 端口号，支持 `1`、`1-10`、`1,4,8`、`255`（所有端口） |
| `reset_mask` | 仅配合 `-R` 使用，按位掩码选择清零对象 |

## 常用选项

### 计数器类型

| 选项 | 全称 | 含义 |
|------|------|------|
| `-x` | `--extended` | 扩展端口计数器 |
| `-X` | `--xmtsl` | 按 SL 发送数据计数器（QoS） |
| `-S` | `--rcvsl` | 按 SL 接收数据计数器（QoS） |
| `-D` | `--xmtdisc` | 发送丢弃详情 |
| `-E` | `--rcverr` | 接收错误详情 |
| `-T` | `--extended_speeds` | 扩展速率计数器 |
| | `--oprcvcounters` | 按操作码的接收计数器 |
| | `--flowctlcounters` | 流控计数器 |
| | `--vloppackets` / `--vlopdata` | 按 VL + 操作码的报文/数据计数器 |
| | `--vlxmitflowctlerrors` / `--vlxmitcounters` | VL 流控错误 / 等待发送 tick 计数器 |
| | `--swportvlcong` | 交换机端口 VL 拥塞 |
| | `--rcvcc` / `--xmitcc` | 接收/发送拥塞控制计数器 |
| | `--slrcvfecn` / `--slrcvbecn` | SL 接收 FECN / BECN 计数器 |
| | `--vlxmittimecc` | VL 发送时间拥塞控制计数器 |
| `-c` | `--smplctl` | 采样控制 |

### 聚合、遍历与清零

| 选项 | 说明 |
|------|------|
| `-a` / `--all_ports` | 聚合所有端口或指定多个端口的结果 |
| `-l` / `--loop_ports` | 逐个端口循环输出，不做聚合 |
| `-r` / `--reset_after_read` | 读取后清零计数器 |
| `-R` / `--Reset_only` | 仅清零，不读取 |

### 寻址与本地端口选择

| 选项 | 说明 |
|------|------|
| `-L` | 地址参数为 LID |
| `-G` | 地址参数为 GUID |
| `-C <ca>` | 指定本地 CA 名 |
| `-P <port>` | 指定本地 CA 端口号 |
| `-s <smlid>` | 指定 SM 端口 LID |
| `-y <key>` | 请求使用的 M_Key |
| `-t <ms>` | 超时时间 |

### 调试与配置

| 选项 | 说明 |
|------|------|
| `-v` / `-d` | 增加 verbose / debug 级别 |
| `-e` | 显示发送/接收错误 |
| `-z <file>` | 指定配置文件，默认 `/etc/infiniband-diags/ibdiag.conf` |
| `-V` / `-h` | 版本 / 帮助 |

## 重要注意事项

1. **数据单位是 octets / 4**  
   `PortXmitData`、`PortRcvData` 等字段表示的是 **字节数除以 4**，换算真实字节数时需要乘以 4。

2. **端口号 255 表示所有端口**

3. **reset_mask 精细清零**  
   - `0x0fff`：只清零错误相关计数器  
   - `0xf000`：只清零非错误相关计数器

4. **远端查询需要目标节点支持 PMA**  
   `perfquery` 通过 PerfMgt GMP 从目标端口的 PMA 获取计数器，若目标不支持会查询失败。

5. **多设备环境必须指定 CA 与端口**  
   当节点上存在多个 IB 设备（如 `mlx5_0` ~ `mlx5_7`）时，省略 `lid|guid` 直接执行 `perfquery` 可能失败：
   ```bash
   perfquery: iberror: failed: Failed to open '(null)' port '0'
   ```
   此时应使用 `-C <ca>` 和 `-P <port>` 指定本地目标设备：
   ```bash
   perfquery -C mlx5_0 -P 1
   perfquery -C mlx5_0 -P 1 -r
   perfquery -C mlx5_0 -P 1 -x
   ```

## 常用示例

```bash
# 读本地端口计数器
perfquery

# 读 lid 32 端口 1 的基本计数器
perfquery 32 1

# 读扩展计数器
perfquery -x 32 1

# 聚合 lid 32 所有端口
perfquery -a 32

# 逐个输出 lid 32 端口 1-10
perfquery -l 32 1-10

# 读取后清零
perfquery -r 32 1

# 仅清零端口 1
perfquery -R 32 1

# 只清零错误计数器
perfquery -R 32 2 0x0fff

# 只清零非错误计数器
perfquery -R 32 2 0xf000

# 按 GUID 查询扩展计数器
perfquery -G -x 0x0002c90300abcdef 1
```

## 典型测试用法

### 测试前后基线对比

```bash
# 测试前清零
perfquery -R 32 1

# 测试后读取并检查错误计数器是否增长
perfquery -E 32 1
perfquery -e 32 1
```

### 拥塞与 QoS 分析

```bash
# 查看 SL 级别收发数据
perfquery -X -S 32 1

# 查看 FECN/BECN 计数
perfquery --slrcvfecn --slrcvbecn 32 1

# 查看拥塞控制计数器
perfquery --rcvcc --xmitcc 32 1
```

## 自动化脚本建议

- 执行命令时使用框架的 `CommandOperation.execute_command_with_error` 或 `RdmaIO` 相关封装。
- 远端查询建议同时捕获 stdout 与 stderr，失败时检查 `timeout`、`PMA not supported` 等关键字。
- 解析输出时优先用正则匹配关键计数器名称和数值，避免依赖固定列宽。
- 清零操作前建议先读取一次确认命令通道正常，避免误清正在使用的端口计数器。
