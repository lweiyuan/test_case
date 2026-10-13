---
name: 以太网模块测试
description: 指导NIC100框架下以太网模块的测试要点，包括网口配置、流量测试、VLAN/Bridge、ethtool和链路状态检查。
---

# NIC100 以太网模块测试指南

## 测试范围

- 网口识别与链路状态检查
- IP/VLAN/Bridge 配置
- 基础连通性测试（ping）
- 流量测试（iperf、发包/收包工具）
- ethtool 参数检查与设置
- 驱动加载/卸载与参数验证

## 核心命令与库

| 命令/库 | 用途 |
|---------|------|
| `ip` / `ifconfig` | 网口/IP/VLAN 配置 |
| `ethtool` | 查询/设置网卡参数、环缓冲区、FEC 等 |
| `ping` | 连通性测试 |
| `iperf3` / `iperf` | TCP/UDP 流量性能测试 |
| `bridge_operation.py` | bridge 操作封装 |
| `packet_operation.py` | 自定义报文发送 |
| `ping_operation.py` | ping 操作封装 |
| `socket_operation.py` | socket 相关操作 |

## 常用检查项

1. **链路状态**：`ethtool <iface>` 查看 Link detected
2. **速率协商**：`ethtool <iface> | grep Speed`
3. **FEC 模式**：`ethtool --show-fec <iface>`
4. **Ring buffer**：`ethtool -g <iface>`
5. **驱动信息**：`ethtool -i <iface>`

## VLAN 与 Bridge

- VLAN 配置使用 `ip link add link <iface> name <vlan_iface> type vlan id <vid>`
- Bridge 操作优先使用 `bridge_operation.py` 封装
- 测试结束后在 `post` 阶段删除创建的 VLAN/Bridge

## 流量测试

- iperf 测试需指定 server/client
- 注意端口占用，可使用非默认端口
- 自定义报文测试使用 `packet_operation.py` / `send_packet.py` / `receive_packet.py`

## 脚本位置

- 公共库：`ps3/test/esat/nic100/scripts/script_libs/`
- 模块脚本：`ps3/test/esat/nic100/scripts/nic100/linux/driver/`

## 注意事项

1. 修改网口 IP 后，确认路由和 ARP 表正确
2. 测试前关闭防火墙或放行对应端口
3. 链路状态异常时，优先排查物理连接、对端配置、FEC 协商
4. 多队列网卡注意中断亲和性对性能的影响
