---
name: RoCE模块测试
description: 指导NIC100框架下RoCE模块的测试要点，包括RoCEv1/RoCEv2配置、PFC/ECN、性能测试和常见问题排查。
---

# NIC100 RoCE 模块测试指南

## 测试范围

- RoCE 模式配置（RoCEv1 / RoCEv2）
- PFC（Priority Flow Control）配置
- ECN（Explicit Congestion Notification）配置
- RoCE 性能测试（perftest）
- CNP/拥塞控制相关测试
- DCB（Data Center Bridging）配置

## 核心命令

| 命令/工具 | 用途 |
|-----------|------|
| `mlxconfig` | 配置 RoCE 模式、PF/VF 数量 |
| `cma_roce_mode` / `roce_mode` | 查询/设置 RoCE 模式 |
| `dcbtool` | DCB 配置 |
| `ethtool` | 查看/设置 PFC、 ring buffer 等 |
| `ib_send_bw / ib_read_bw / ib_write_bw` | RoCE 性能测试 |
| `rdma_core_tool.py` | 脚本层 RDMA 工具封装 |

## RoCE 模式

- **RoCEv1**：基于以太网二层，使用 VLAN/PCP 优先级
- **RoCEv2**：基于 UDP/IP，可跨三层网络
- 根据用例要求选择对应模式，修改后可能需要重启驱动或服务器

## PFC 与 ECN

- PFC 优先级需与 RoCE 流量优先级一致
- ECN 配置通常涉及 `sysctl` 和 `tc` 命令
- 测试前确认交换机侧已开启对应功能

## 性能测试

- 与 IB 类似，perftest 命令需 server/client 成对启动
- 注意 RoCE 场景下使用正确的网卡设备和 IP 地址
- 示例：
  ```bash
  # server
  ib_send_bw -d mlx5_0 -R --report_gbits
  # client
  ib_send_bw -d mlx5_0 -R --report_gbits <server_ip>
  ```

## 脚本位置

- 公共库：`ps3/test/esat/nic100/scripts/script_libs/rdma_core_tool.py`
- 辅助库：`ps3/test/esat/nic100/scripts/script_libs/dcbtool_operation.py`
- 模块脚本：`ps3/test/esat/nic100/scripts/nic100/linux/rdma/`

## 常见问题

1. **RoCE 链路不通**：检查 IP、子网、VLAN、PFC 配置
2. **性能不达标**：检查 CPU 频率、ring buffer、中断亲和性、交换机配置
3. **CNP 异常**：确认 ECN 和 PFC 配置正确，交换机支持并开启
4. **模式切换失败**：确认 mlxconfig 设置后已重启或重新加载驱动
