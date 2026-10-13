---
name: multi-host-rdma
description: Use when testing NIC100 Multi-Host RDMA scenarios, including 2HOST/4HOST topologies, Host-to-Host RDMA traffic, mixed networking, PF/Host isolation, resource backpressure, and 24h stability.
---

# NIC100 Multi-Host RDMA 测试指南

## Overview

本 skill 聚焦 NIC100 网卡在 **Multi-Host（多 Host）场景下的 RDMA 测试**。核心目标是验证：多 Host 共享或独占物理 PORT 时，各 Host 上的 RDMA 业务互不干扰、性能均衡、异常隔离符合预期。

本 skill 是 `RoCE模块测试` 的子 skill。若任务涉及 RoCE 配置、PFC/ECN、单 Host RDMA 性能，先加载父 skill `RoCE模块测试`。

## When to Use

- 测试对象为 Multi-Host 形态（2HOST/4HOST、1PORT/2PORT/4PORT、Socket Direct）
- 需要验证 Host↔Host 的 RDMA 互通、带宽、时延
- 涉及 RDMA 与以太/VIRTIO/MNG-PCIE 的混合组网
- 需要验证 PFR/PFLR/Host 重启/Hot Reset/DPR/Global/Sys Reset 对 RDMA 的影响
- 需要验证共享资源/独占资源反压行为
- 需要执行 24h 长时间 RDMA 稳定性或性能均衡测试

## 必备前置技能

- **REQUIRED:** `RoCE模块测试` — RoCE 基础配置、perftest 使用、PFC/ECN
- **REQUIRED:** `网卡测试框架` — NIC100 框架目录、基类、环境配置
- **REQUIRED:** `测试脚本编写` — prepare/do/post 三阶段、命令封装规范
- **REQUIRED:** `测试用例生成` — Excel/XMind/需求转脚本
- **RECOMMENDED:** `IB模块测试` — IB/RDMA 命令（ibstat、opensm、smpquery、perfquery）

## Multi-Host 形态速查

| 形态 | Host 数 | Port 数 | PF 分配 | 典型平台 |
|------|---------|---------|---------|----------|
| 2HOST 1PORT | 2 | 1 | HOST0→PF0, HOST1→PF1，共用 PORT0 | FPGA |
| 2HOST 2PORT（独占） | 2 | 2 | HOST0→PF0/PORT0, HOST1→PF1/PORT1 | FPGA/EMU |
| 2HOST 2PORT（共用） | 2 | 2 | HOST0→PF0/PF1, HOST1→PF2/PF3；PF0/PF2→PORT0, PF1/PF3→PORT1 | FPGA/EMU |
| 4HOST 1PORT | 4 | 1 | HOSTi→PFi(i=0..3)，共用 PORT0 | EMU |
| 4HOST 4PORT（独占） | 4 | 4 | HOSTi→PFi→PORTi | EMU |
| 4HOST 4PORT（共用） | 4 | 4 | HOST0→PF0-PF3, HOST1→PF4-PF7, ... | EMU |
| 1HOST Socket Direct | 1 | 1 | 单 Host 双 NUMA：NUMA0→PF0, NUMA1→PF1，共用 PORT0 | FPGA/EMU |

## 核心原则

1. **禁止硬编码设备名**：所有 `mlx5_0`/`mlx5_1` 类常量必须通过 `env_config.ini` 动态读取。
2. **opensm 按 GUID 启动**：多设备/多 PORT 环境下，使用 `-g <node_guid>` 指定目标 pport。
3. **perftest 统一参数**：功能测试使用 `-D 60 -F`；24h 稳定性测试使用 `-D <run_seconds> -F`。
4. **命令级校验**：生成脚本时校验 ibstat/ib_read_bw/opensm 等命令的拼写与参数。
5. **post 阶段必须清理**：即使 `do()` 失败，也要停止 opensm/perftest、恢复 IP、删除临时文件。

## 动态读取 RDMA 设备名

```python
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import RdmaMode

server_devs, client_devs = CommonOperation.get_nic_relationships(
    rdma=True, nic_mode=RdmaMode.Infiniband.value
)
server_device = server_devs[0].strip() if server_devs else ""
client_device = client_devs[0].strip() if client_devs else ""

if not server_device or not client_device:
    cls.own_environment_enabled = False
    return
```

## 按 Node GUID 启动 opensm

```bash
# 获取 Node GUID
ibstat <device> | grep "Node GUID"

# 按 GUID 启动 opensm（多设备/多 PORT 环境必须）
nohup opensm -g <node_guid> -B -e -f /var/log/opensm.log > /dev/null 2>&1 &

# 启动后检查进程持续运行
pgrep -x opensm
```

## Host↔Host RDMA 带宽测试模板

```bash
# server
ib_read_bw -d <server_dev> -p 19000 -b -D 60 -F

# client
ib_read_bw -d <client_dev> -p 19000 -b -D 60 -F <server_ip>
```

可用的 perftest 工具：
- `ib_read_bw` / `ib_read_lat`：RDMA Read
- `ib_write_bw` / `ib_write_lat`：RDMA Write
- `ib_send_bw` / `ib_send_lat`：RDMA Send
- 双向并发：同时启动 read server + write client / read client + write server

## 混合组网场景

| 模式 | 说明 | 典型命令组合 |
|------|------|--------------|
| 共存 | 一个 PF 上同时跑以太+RDMA | `iperf3` + `ib_read_bw` 同一 PF |
| 半共存 | 同一 Host 多个 PF，分别跑不同流量 | PF0 以太 + PF1 RDMA |
| 不共存 | 不同 Host 分别跑不同流量 | HOST0 以太、HOST1 RDMA、HOST2 VIRTIO |
| 多 PF 共 PORT | 多个 PF 共用同一 PORT 跑 RDMA | 多对 ib_read_bw 并发 |

## 异常与隔离测试

| 操作 | 影响范围 | 验证重点 |
|------|----------|----------|
| PFR / PFLR | 仅当前 PF 所在 Host | 其他 Host RDMA 业务不中断、无丢包 |
| Host 重启 / Hot Reset | 仅当前 Host | 其他 Host 业务正常，复位 Host 恢复后业务恢复 |
| DPR Reset | 所有 Host 数据通路 | 所有 Host RDMA 中断，复位后恢复 |
| Global Reset / Sys Reset | 所有 Host | 所有 Host RDMA 中断，复位后恢复 |

**注意**：PFR/PFLR/Hot Reset/DPR/Global/Sys Reset 的具体触发命令依赖芯片/驱动实现，脚本中通常以 TODO 占位，执行前需由硬件/驱动团队确认并替换。

## 资源反压测试

| 类型 | 现象 | 验证方法 |
|------|------|----------|
| 共享资源反压 | 影响所有 Host 的 RDMA 带宽 | 占满共享缓存/HQM，观察所有 Host 带宽下降，释放后恢复 |
| 独占资源反压 | 仅影响单个 Host 的 RDMA 带宽 | 占满单个 Host 资源，观察仅该 Host 带宽下降 |

## 24h 稳定性与性能均衡

- 使用 `nohup` + 后台进程启动长时 perftest
- 每 10 分钟检查一次：进程存活、IB 设备状态、错包/丢包计数
- 默认运行 24h，可通过环境变量 `MULTIHOST_STABILITY_HOURS` 覆盖
- 性能均衡：多 Host 同时跑 ib_read_bw，比较各 Host 平均带宽，差异应 < 30%

## 常见错误与排查

| 现象 | 可能原因 | 排查 |
|------|----------|------|
| ib_read_bw 连接失败 | opensm 未启动或绑定到错误 PORT | 检查 `pgrep -x opensm` 与 `ibstat` 状态 |
| 带宽为 0 | 设备名错误、链路未 Up、CPU 绑定不当 | 检查设备名、ibstat、中断亲和性 |
| 多 Host 串流 | PPE TX/RX MAC 规则配置错误 | 确认 DMAC 到 PF/Host 的映射规则 |
| 复位后业务不恢复 | opensm 未重启或 GUID 错误 | 复位后重新按 GUID 启动 opensm |
| 某 Host 带宽明显低 | 独占资源被占满或 NUMA 亲和性不对 | 检查资源使用、CPU/内存 NUMA 绑定 |

## 参考文件

- 测试计划：`docs/superpowers/plans/2026-07-02-multihost-verification-test-plan.md`
- 测试点分析：`docs/multihost_verification_analysis.md`
- 用户场景用例 Excel：`MultiHost_RDMA_TestCases.xlsx`
- 框架脚本：`ps3/test/esat/nic100/scripts/multihost_test_tc001.py` ~ `tc006.py`
- 环境配置：`ps3/test/esat/nic100/scripts/env_config*.ini`

## 禁止事项

- ❌ 硬编码 `mlx5_0` / `mlx5_1` 等设备名
- ❌ server/client 使用同一设备名
- ❌ 命令中混用 `mlx5_0` 而不通过 env_config 读取
- ❌ 多播场景下 `ib_send_bw` 同时使用 `-x` 与 `-M`
- ❌ opensm 启动时不指定 GUID（多设备环境）
- ❌ 仅检查 opensm 进程存活，不通过 `ibstat`/`smpquery` 验证配置生效
