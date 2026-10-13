---
name: IB模块测试
description: NIC100框架下InfiniBand（IB）模块测试的总览skill，提供核心术语、测试范围、子skill导航和与现有skill的关系说明。
---

# NIC100 IB（InfiniBand）模块测试指南

## 测试范围

NIC100 IB 模块测试覆盖以下场景：

- IB 设备识别与状态检查
- IB 端口配置与状态切换
- OpenSM 子网管理器组网与 QoS 配置
- IB 性能测试（perftest 工具）
- PF/VF 配置、修改与验证
- GUID、LID 获取与使用
- 命令回显解析与错误判断
- 测试结果报告与自动化 Bug 记录

## 核心术语速查

| 术语 | 说明 |
|------|------|
| **pport（物理端口）** | 双端口网卡的前两个 PF 同时是 pport 和 vport；单端口网卡只有第一个 PF 是 pport |
| **vport（虚拟端口）** | 新增的 PF 为 vport |
| **线网** | 通过网线/光纤进行数据包转发，至少需要两个网卡分别作为服务端和客户端 |
| **自发自收** | 自己发给自己，一个网卡同时作为服务端和客户端 |
| **GUID** | 设备全局唯一标识，通过 `ibstat` 获取 |
| **LID** | 子网内局部标识，通过 `ibstat` 查看 `Base lid` |
| **OpenSM** | IB 子网管理器，负责 fabric 发现、路由、QoS |
| **perftest** | IB/RDMA 性能测试工具集 |

## 核心命令速查

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

## 子 skill 导航

| 测试场景 | 调用的子 skill |
|----------|----------------|
| 设备识别、端口概念、GUID/LID、状态检查 | `IB基础概念与设备检查` |
| OpenSM 安装、启动、配置、QoS、组网 | `OpenSM组网与QoS` |
| perftest 执行、并发、内存估算、结果解析 | `perftest工具使用` |
| perfquery 计数器查询、清零、错误/拥塞分析 | `perfquery计数器查询` |
| saquery 子网管理记录、多播组/成员查询 | `saquery子网管理查询` |
| smpquery 子网管理属性、拓扑与配置查询 | `smpquery子网管理查询` |
| rdma 设备/链路/资源/统计/命名空间管理 | `rdma工具使用` |
| mlxconfig、PF 修改、重启、复位、驱动恢复 | `IB网卡配置与恢复` |
| 命令回显判断、交互命令、错误修正 | `IB命令处理与回显解析` |
| 多播功能、iperf2 多播命令与场景构造 | `IB多播与iperf测试` |
| 脚本结构、命名、生成规范、Bug 记录 | `缺陷自动记录`（框架与通用能力） |

## 与现有 skill 的关系

- 继承「网卡测试框架」的目录约定、基类使用、环境配置原则。
- 执行 perftest 等命令时使用「网卡测试框架」中的 `CommandOperation` 等公共库。
- 失败时的 Bug 记录引用「缺陷自动记录」skill，不重复定义字段。
- 「IB命令处理与回显解析」中的命令判断原则可跨模块复用（如以太网、RoCE 模块测试）。

## 注意事项

1. `mlxconfig` 正常回显中可能包含 "error"，不代表失败；`-E-` 前缀才是明确错误。
2. 修改 PF 数量后必须重启服务器才能生效。
3. reboot 后需等待约 30 秒再检测服务器是否上线。
4. perftest 命令必须 server/client 成对使用。
5. 指定 SL 时 server 端和 client 端都必须加 `-S`，且值一致。
6. OpenSM 双端口组网时，需为每个 pport 分别指定 GUID。
