# Multi Host 验证测试方案分析

> 来源：《multihost验证测试方案.pptx》
> 分析日期：2026-07-02

---

## 一、方案概述

本方案针对 NIC100 网卡在不同 Host 数量与 Port 数量组合下的 Multi-Host 场景，制定验证组网、验证平台与验证策略。核心目标是保证：

- 多 Host 在独立网络场景与混合组网场景下，报文收发正常、无错包、无丢包。
- 基于 PF 的隔离机制在 PFR/PFLR、Host 重启/Hot Reset 等异常场景下互不影响。
- 共享资源与独占资源的反压行为符合预期。
- 各 Host 在长时间（24h）打流下性能均衡，无卡死。

---

## 二、测试点（Test Points）

| 序号 | 测试点 | 说明 |
|------|--------|------|
| TP-01 | 多 Host 与 Port 的组合形态 | 验证 2HOST/4HOST 与 1PORT/2PORT/4PORT 的多种拓扑配置，以及 Socket Direct 模式。 |
| TP-02 | 以太独立网络 | Host↔发包仪、Host↔Host 的以太报文收发与环回。 |
| TP-03 | RDMA（RoCE）独立网络 | Host↔外部发包仪、Host↔Host 的 RDMA 数据收发。 |
| TP-04 | VIRTIO 独立网络 | Host↔发包仪、Host↔Host 的 VIRTIO/DPDK 数据收发。 |
| TP-05 | MNG 网络独立 | MNG 带外管理网络的独立性验证。 |
| TP-06 | 混合组网 | 以太/RDMA/VIRTIO/MNG-PCIE 在同一网卡上共存/半共存/不共存的流量模型。 |
| TP-07 | 异常与隔离 | PFR、PFLR、Host 重启、Hot Reset、DPR Reset、Global Reset、Sys Reset 对多 Host 的影响。 |
| TP-08 | 资源反压 | 共享资源反压影响所有 Host，独立资源反压只影响单个 Host。 |
| TP-09 | 性能均衡 | 24h 长时间打流，验证各 Host 性能均衡、无卡死/丢包/错包。 |

---

## 三、Host 与 Port 组合形态（测试项）

| 编号 | 形态 | Host 数量 | Port 数量 | PF 分配 | 适用平台 |
|------|------|-----------|-----------|---------|----------|
| HI-01 | 2HOST 1PORT | 2 | 1 | HOST0→PF0, HOST1→PF1；PF0/PF1 共用 PORT0 | FPGA |
| HI-02 | 2HOST 2PORT（独占） | 2 | 2 | HOST0→PF0(PORT0), HOST1→PF1(PORT1) | FPGA |
| HI-03 | 2HOST 2PORT（共用） | 2 | 2 | HOST0→PF0/PF1, HOST1→PF2/PF3；PF0/PF2→PORT0, PF1/PF3→PORT1 | FPGA/EMU |
| HI-04 | 4HOST 1PORT | 4 | 1 | HOST0→PF0, HOST1→PF1, HOST2→PF2, HOST3→PF3；共用 PORT0 | EMU |
| HI-05 | 4HOST 4PORT（独占） | 4 | 4 | HOSTi→PF(i)，PFi→PORTi | EMU |
| HI-06 | 4HOST 4PORT（共用） | 4 | 4 | HOST0→PF0-PF3, HOST1→PF4-PF7, HOST2→PF8-PF11, HOST3→PF12-PF15 | EMU |
| HI-07 | 1HOST Socket Direct | 1 | 1 | 单 Host 通过 2x8 PCIe 接入两个 NUMA Node；NUMA0→PF0, NUMA1→PF1，共用 PORT0 | FPGA/EMU |

---

## 四、网络类型验证策略（测试项）

### 4.1 以太独立网络

| 编号 | 测试项 | 流量方向 | 关键动作 |
|------|--------|----------|----------|
| ETH-01 | Host↔发包仪 | 外部→Host→外部 | 发包仪按 DMAC 发送；PPE 查 RX MAC 规则转发到不同 Host；Host 侧以太驱动/DPDK 环回，从 TX 送回发包仪。需关闭 PPE TX MAC 规则，避免片内再次环回。 |
| ETH-02 | Host↔Host | Host→Host | Host 用户态使用 ping/iperf/scapy 收发；PPE 查 TX MAC 规则在片内环回，经 HQM 送回目标 Host。 |

### 4.2 RDMA 独立网络

| 编号 | 测试项 | 流量方向 | 关键动作 |
|------|--------|----------|----------|
| RDMA-01 | Host↔外部发包仪 | 外部→Host | Host 用户态使用 RDMA 测试工具收发；MAC 配置 TX→RX 环回模拟发包仪；目的 MAC 设为本 PF MAC；关闭 PPE TX MAC 规则。 |
| RDMA-02 | Host↔Host | Host→Host | Host 用户态使用 RDMA 测试工具收发；TX 目的 MAC 指定对端 Host PF MAC；PPE 查 TX MAC 规则片内环回，经 HQM+RDMA-RX-ENGINE 到另一 Host。 |

### 4.3 VIRTIO 独立网络

| 编号 | 测试项 | 流量方向 | 关键动作 |
|------|--------|----------|----------|
| VIRTIO-01 | Host↔发包仪 | 外部→Host→外部 | 发包仪按 DMAC 发送；PPE 查 RX MAC 规则经 VIRTIO-RX-ENGINE 到不同 Host；Host 用户态 DPDK 工具环回后 TX 送回发包仪。 |
| VIRTIO-02 | Host↔Host | Host→Host | Host 用户态 DPDK 工具收发；TX 目的 MAC 指定对端 Host PF MAC；PPE 查 TX MAC 规则片内环回，经 HQM+VIRTIO-RX-ENGINE 到另一 Host。 |

### 4.4 混合组网

| 编号 | 模式 | 说明 |
|------|------|------|
| MIX-01 | 共存模式 | 每个 Host 一个 PF，PF 上同时跑以太 + RDMA 业务。 |
| MIX-02 | 半共存模式 | 每个 Host 上起多个 PF，每个 PF 跑不同流量（如 PF0 以太、PF1 RDMA）。 |
| MIX-03 | 不共存模式 | 每个 Host 一个 PF，不同 Host 分别跑以太/RDMA/VIRTIO。 |
| MIX-04 | 多 PF 共 PORT | 多个 PF 共用同一 PORT，验证不同 PF 上流量模型互不干扰。 |

---

## 五、异常与隔离验证项

| 编号 | 测试项 | 预期影响范围 |
|------|--------|--------------|
| EXC-01 | PF 隔离 PFR/PFLR | 仅影响当前 PF 所在 Host，其他 Host 无影响。 |
| EXC-02 | Host 重启 / Hot Reset | 仅影响当前 Host，其他 Host 无影响。 |
| EXC-03 | DPR Reset | 影响所有 Host 数据通路。 |
| EXC-04 | Global Reset / Sys Reset | 影响所有 Host。 |
| EXC-05 | 共享资源反压 | 影响所有 Host 收发。 |
| EXC-06 | 独立资源反压 | 只影响单个 Host。 |

---

## 六、性能与稳定性验证项

| 编号 | 测试项 | 验收标准 |
|------|--------|----------|
| PERF-01 | 24h 长时间打流 | 以太/RDMA/VIRTIO 独立网络及混合网络，持续 24h 无卡死、无丢包、无错包。 |
| PERF-02 | 各 Host 性能均衡 | 多 Host 同时打流时，各 Host 带宽/延时指标均衡，无明显倾斜。 |

---

## 七、验证平台

| 平台 | 连接方式 | 适用 Host 数 | 适用场景 |
|------|----------|--------------|----------|
| FPGA 平台 | 2x8 PCIe | 2 Host | 两 Host 用例验证 |
| EMU 平台 | 4x4 PCIe | 4 Host | 四 Host 用例验证及满规格验证 |

---

## 八、用例编号规划

建议采用统一编号：`multihost_test_tc<nnn>`。

| 用例编号 | 对应测试项 | 标题 |
|----------|------------|------|
| TC-001 | HI-01 + ETH-02 | 2HOST 1PORT 以太独立网络 Host↔Host 互通 |
| TC-002 | HI-02 + RDMA-02 | 2HOST 2PORT RDMA 独立网络 Host↔Host 互通 |
| TC-003 | HI-04 + MIX-04 | 4HOST 1PORT 混合组网共存模式流量验证 |
| TC-004 | EXC-01 | 基于 PF 隔离的 PFR/PFLR 不影响其他 Host |
| TC-005 | EXC-05 + PERF-02 | 共享资源反压下多 Host 性能均衡 |
| TC-006 | PERF-01 | 混合组网 24h 长时间稳定性打流 |

---

## 九、输出文件

- 本分析文档：`docs/multihost_verification_analysis.md`
- 测试用例脚本：`ps3/test/esat/nic100/scripts/multihost_test_tc*.py`
