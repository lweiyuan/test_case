# Multi-Host 验证测试计划

> **For agentic workers:** 本计划为测试执行计划，非代码开发计划。实施时按阶段执行测试任务，记录结果并回归问题。

**Goal:** 依据《multihost验证测试方案.pptx》，在 NIC100 网卡 Multi-Host 场景下完成 Host/Port 组合形态、独立网络、混合组网、异常隔离、资源反压及 24h 稳定性等系统性验证，确保各 Host 业务互不干扰、性能均衡。

**Architecture:** 以 FPGA（2HOST）和 EMU（4HOST）为硬件验证平台，利用 NIC100 自动化测试框架（`ps3/test/esat/nic100/`）执行脚本；测试脚本继承 `ScriptBase`，按 `prepare / do / post` 组织，命令通过 `CommandOperation` 分发到各 Host，结果通过框架 `create_bug` 机制记录。

**Tech Stack:** Python 3.8+/3.12/3.13、NIC100 测试框架、iperf3、perftest（`ib_read_bw` 等）、DPDK/testpmd、ethtool、ibstat/opensm/smpquery/perfquery、mlxconfig。

## Global Constraints

- 测试对象：NIC100 网卡 Multi-Host 功能
- 验证平台：FPGA（2x8 PCIe，2 Host）、EMU（4x4 PCIe，4 Host）
- 脚本位置：`ps3/test/esat/nic100/scripts/`
- 设备名禁止硬编码，必须通过 `env_config.ini` 动态读取
- RDMA/IB 命令优先使用动态设备名，opensm 按 Node GUID 启动
- perftest 统一使用 `-D 60 -F`（稳定性测试使用 `-D <run_seconds> -F`）
- 所有脚本必须包含 `post` 清理阶段，即使 `do` 失败也要尽量恢复环境
- Python 版本需兼容 3.8/3.12/3.13

---

## 1. 背景与范围

### 1.1 背景

NIC100 网卡支持多 Host 共享或独占物理 PORT 的多种组合形态。不同 Host 上的 PF 可能共用同一 PORT，也可能各独占一个 PORT。验证重点是：在独立网络（以太/RDMA/VIRTIO/MNG）和混合组网场景下，各 Host 业务正常、互不影响；在异常复位和资源共享场景下，隔离性与反压行为符合预期。

### 1.2 测试范围

**包含：**
- 2HOST/4HOST 与 1PORT/2PORT/4PORT 的组合形态验证
- 以太独立网络（Host↔发包仪、Host↔Host）
- RDMA（RoCE）独立网络（Host↔外部发包仪、Host↔Host）
- VIRTIO 独立网络（Host↔发包仪、Host↔Host）
- MNG 带外网络独立场景
- 以太/RDMA/VIRTIO/MNG-PCIE 混合组网
- 异常场景：PFR、PFLR、Host 重启、Hot Reset、DPR Reset、Global Reset、Sys Reset
- 共享资源反压与独占资源反压
- 24h 长时间稳定性与性能均衡

**不包含：**
- 非 Multi-Host 单 Host 功能验证（已有其他专项覆盖）
- 性能基准标定（本次仅验证性能均衡与无错包）
- 固件升级/回滚（由固件测试专项覆盖）

---

## 2. 测试目标

| 目标编号 | 目标描述 | 验收标准 |
|----------|----------|----------|
| OBJ-01 | 验证所有 Multi-Host 与 PORT 组合形态可正常配置并识别 PF | 各形态下 `lspci`/`ibstat` 识别的 PF 数量与分配与方案一致 |
| OBJ-02 | 验证独立网络场景下各 Host 报文收发正常 | ping/iperf3/perftest 无丢包、无错包、带宽 > 0 |
| OBJ-03 | 验证混合组网场景下不同流量互不干扰 | 共存/半共存/不共存模式同时运行，各 Host 无异常 |
| OBJ-04 | 验证 PF 级与 Host 级隔离 | PFR/PFLR/Host 重启仅影响当前 Host，其他 Host 业务不中断 |
| OBJ-05 | 验证共享/独占资源反压 | 共享资源反压影响所有 Host，独占资源反压仅影响单个 Host |
| OBJ-06 | 验证长时间稳定性 | 24h 混合流量无卡死、无丢包、无错包，各 Host 性能均衡 |

---

## 3. 测试环境与平台

### 3.1 硬件平台

| 平台 | 连接方式 | 支持 Host 数 | 适用形态 | 主要用途 |
|------|----------|--------------|----------|----------|
| FPGA | 2x8 PCIe | 2 Host | 2HOST 1PORT / 2HOST 2PORT / Socket Direct | 两 Host 功能验证、问题定位 |
| EMU  | 4x4 PCIe | 4 Host | 4HOST 1PORT / 4HOST 4PORT / 2HOST 2PORT | 四 Host 验证、满规格验证 |

### 3.2 软件环境

| 组件 | 要求 |
|------|------|
| OS | Linux（建议 RHEL/Rocky/Ubuntu LTS，内核版本与驱动匹配） |
| 驱动 | NIC100 对应内核驱动已加载，RDMA 驱动（mlx4/mlx5 或项目专用驱动）正常 |
| 工具 | iperf3、perftest、DPDK/testpmd、ethtool、iproute2、ibutils、opensm、mlxconfig |
| 框架 | `ps3/test/esat/nic100/` 自动化框架，环境配置 `env_config.ini` 已正确填写 |

### 3.3 网络拓扑示例

**FPGA 2HOST 1PORT**
```
[HOST0/PF0]───┐
              ├── PORT0 ── 外部网络/发包仪
[HOST1/PF1]───┘
```

**EMU 4HOST 1PORT**
```
[HOST0/PF0]───┐
[HOST1/PF1]───┼── PORT0
[HOST2/PF2]───┤
[HOST3/PF3]───┘
```

---

## 4. 测试策略

### 4.1 分阶段策略

| 阶段 | 名称 | 周期 | 内容 |
|------|------|------|------|
| P1 | 形态与基础连通 | 3 天 | 配置各 Host/Port 形态，验证 PF 识别、链路 Up、基础 ping 通 |
| P2 | 独立网络验证 | 5 天 | 以太/RDMA/VIRTIO/MNG 独立网络 Host↔Host 与 Host↔仪器的功能验证 |
| P3 | 混合组网验证 | 4 天 | 共存/半共存/不共存模式下的混合流量验证 |
| P4 | 异常与隔离 | 4 天 | PFR/PFLR/Host 重启/Hot Reset/DPR/Global/Sys Reset |
| P5 | 资源反压 | 3 天 | 共享资源与独占资源反压场景 |
| P6 | 稳定性与性能均衡 | 7 天 | 24h 长时间打流、性能均衡分析、问题回归 |

### 4.2 自动化策略

- 功能用例优先使用已生成的 Python 脚本在框架中执行
- 24h 稳定性测试通过 `nohup` + 后台进程 + 周期性检查实现
- 异常场景（如 PFR/PFLR）中部分触发命令依赖硬件/驱动接口，脚本中以 TODO 占位，执行前需人工确认并替换为实际命令
- 所有脚本执行结果由框架自动收集日志，失败时自动触发 Bug 记录

### 4.3 回归策略

- 每轮发现问题修复后，执行问题相关用例及相邻用例的冒烟测试
- 重大问题修复后，执行对应独立网络或混合组网模块的全量回归
- 发布前执行一轮完整的 P1-P6 全量验证

---

## 5. 测试用例清单

### 5.1 已生成脚本与对应关系

| 用例编号 | 脚本路径 | 对应测试项 | 形态/平台 | 预计时长 |
|----------|----------|------------|-----------|----------|
| TC-001 | `ps3/test/esat/nic100/scripts/multihost_test_tc001.py` | 以太独立网络 Host↔Host | 2HOST 1PORT / FPGA | ~3 min |
| TC-002 | `ps3/test/esat/nic100/scripts/multihost_test_tc002.py` | RDMA 独立网络 Host↔Host | 2HOST 2PORT / FPGA | ~3 min |
| TC-003 | `ps3/test/esat/nic100/scripts/multihost_test_tc003.py` | 混合组网共存模式 | 4HOST 1PORT / EMU | ~5 min |
| TC-004 | `ps3/test/esat/nic100/scripts/multihost_test_tc004.py` | PF 隔离 PFR/PFLR | 2HOST 1PORT / FPGA | ~5 min |
| TC-005 | `ps3/test/esat/nic100/scripts/multihost_test_tc005.py` | 共享资源反压 | 2HOST/4HOST / FPGA/EMU | ~5 min |
| TC-006 | `ps3/test/esat/nic100/scripts/multihost_test_tc006.py` | 24h 稳定性混合打流 | 2HOST/4HOST / FPGA/EMU | 24h（可配置） |

### 5.2 需补充的手动用例/探索性测试

| 编号 | 用例 | 说明 |
|------|------|------|
| TC-007 | 以太独立网络 Host↔发包仪 | 发包仪按 DMAC 发送，Host 侧 DPDK 环回；需关闭 PPE TX MAC 规则 |
| TC-008 | RDMA 独立网络 Host↔外部发包仪 | MAC 配置 TX→RX 环回模拟发包仪，验证 RDMA RX 通路 |
| TC-009 | VIRTIO 独立网络 Host↔发包仪 | 发包仪按 DMAC 发送，Host 侧 DPDK testpmd 环回 |
| TC-010 | VIRTIO 独立网络 Host↔Host | Host 间使用 DPDK 工具收发，PPE TX MAC 片内环回 |
| TC-011 | MNG 网络独立 | 验证各 Host MNG 带外管理网络独立互通 |
| TC-012 | 混合组网半共存/不共存 | 每个 Host 多个 PF 或不同 Host 跑不同流量 |
| TC-013 | Host 重启/Hot Reset 隔离 | 单 Host 重启后业务恢复，其他 Host 不受影响 |
| TC-014 | DPR Reset / Global Reset / Sys Reset | 验证影响范围符合预期（DPR 影响所有 Host 数据通路，Global/Sys 影响所有 Host） |
| TC-015 | 独占资源反压 | 单个 Host 资源占满只影响本 Host |
| TC-016 | 各 Host 性能均衡 | 多 Host 同时打流，对比带宽/延时方差 |

### 5.3 用例优先级

- **P0（阻塞）：** TC-001、TC-002、TC-007、TC-008、TC-013
- **P1（核心）：** TC-003、TC-004、TC-009、TC-010、TC-011、TC-014、TC-015
- **P2（完整）：** TC-005、TC-006、TC-012、TC-016

---

## 6. 测试执行计划

### 6.1 执行入口

```bash
# 单个用例执行
cd ps3/test/esat/nic100/scripts
python multihost_test_tc001.py

# 或框架批量执行（需参考 run_test.sh / run_all_test.py）
cd ps3/test/esat/nic100
bash run_test.sh --scripts scripts/multihost_test_tc001.py,scripts/multihost_test_tc002.py
```

### 6.2 环境配置检查清单

执行前确认：
- [ ] `env_config.ini` 中 `[relationships]`、`[relationships_rdma]` 已正确填写各 Host 设备名
- [ ] 各 Host 之间管理网络互通，SSH/框架执行地址可达
- [ ] FPGA/EMU 平台已上电，PCIe 链路正常
- [ ] 目标形态（2HOST/4HOST、1PORT/2PORT/4PORT）已在网卡配置中生效
- [ ] iperf3、perftest、DPDK、opensm、mlxconfig 等工具已安装
- [ ] 外部发包仪（如需要）已连接并配置好 DMAC 流

### 6.3 执行顺序建议

```
Day 1-3:  P1 形态与基础连通（TC-001/TC-002 冒烟 + TC-007/TC-008 手动）
Day 4-8:  P2 独立网络验证（TC-001~TC-002 全形态 + TC-007~TC-011）
Day 9-12: P3 混合组网验证（TC-003 + TC-012）
Day 13-16: P4 异常与隔离（TC-004 + TC-013 + TC-014）
Day 17-19: P5 资源反压（TC-005 + TC-015）
Day 20-26: P6 稳定性与性能均衡（TC-006 + TC-016 + 问题回归）
```

---

## 7. 入口与出口准则

### 7.1 测试入口准则

- 测试平台硬件安装完成，PCIe 链路识别正常
- 网卡固件/驱动版本满足 Multi-Host 功能基线
- `env_config.ini` 配置完成并通过框架环境自检
- 关键工具（iperf3、perftest、DPDK、opensm）可用
- 测试用例脚本已通过语法与加载检查

### 7.2 测试出口准则

- P0/P1 用例全部通过，P2 用例通过率达到 90% 以上
- 24h 稳定性测试无卡死、无丢包、无错包
- 所有阻塞性问题已关闭或已明确遗留并评估风险
- 测试报告、Bug 清单、问题分析文档已完成评审

---

## 8. 风险与应对

| 风险编号 | 风险描述 | 影响 | 应对措施 |
|----------|----------|------|----------|
| R-01 | PFR/PFLR 触发命令依赖具体芯片/驱动，脚本中为占位符 | 中 | 执行前由硬件/驱动同事提供确切命令并替换；先在非生产环境验证 |
| R-02 | 4HOST 环境需要 4 个独立执行地址，框架默认可能只配置 2 个 | 高 | 提前确认 `CmdExecuteAdressEnum` 中 `SUB_HOST`、`SERVER_NODE`、`CLIENT_NODE` 的配置与连通性 |
| R-03 | 共享资源反压的触发方式依赖芯片实现 | 中 | 与芯片/架构团队确认反压注入方法；先小流量验证再全量 |
| R-04 | 24h 稳定性测试耗时长，环境问题会导致全量重来 | 高 | 使用 `MULTIHOST_STABILITY_HOURS` 环境变量支持缩短时长做预跑；保留完整日志 |
| R-05 | 多 Host 共用 PORT 时发包仪/交换机配置错误导致结果不可信 | 中 | 测试前与硬件团队确认 DMAC/VLAN/端口映射；先用单 Host 流量验证物理通路 |
| R-06 | PPE TX/RX MAC 规则配置错误导致片内环回不符合预期 | 高 | 测试前确认 PPE 规则状态；独立网络 Host↔Host 与 Host↔仪器需采用不同规则 |

---

## 9. 交付物

| 交付物 | 路径 | 说明 |
|--------|------|------|
| 测试方案分析 | `docs/multihost_verification_analysis.md` | 测试点、测试项、Host/Port 形态、验证策略 |
| 测试计划 | 本文件 | 执行计划、用例清单、环境、风险 |
| 测试脚本 | `ps3/test/esat/nic100/scripts/multihost_test_tc001.py` ~ `tc006.py` | 自动化用例脚本 |
| 测试报告 | `outputs/` 或项目指定报告目录 | 执行后生成 |
| Bug 记录 | 由框架自动记录或禅道/Jira | 失败用例触发 |

---

## 10. 任务分解（执行用）

> 以下任务为测试执行与脚本完善任务，按依赖关系排序。

### Task 1: 环境准备与形态配置

**内容：**
- 在 FPGA/EMU 平台上配置目标 Multi-Host 形态
- 填写 `env_config.ini` 中各 Host 的以太/RDMA 设备关系
- 验证各 Host 管理面可达、业务面链路 Up

**验收：**
- `lspci | grep -i mellanox` 在所有 Host 上输出预期 PF 数量
- `ibstat -l` / `ip link` 能识别到目标设备
- 框架自检脚本可成功连通所有 Host

### Task 2: 独立网络功能验证

**内容：**
- 执行 TC-001（以太 Host↔Host）
- 执行 TC-002（RDMA Host↔Host）
- 手动补充 TC-007/TC-008/TC-009/TC-010/TC-011

**验收：**
- 所有 P0 独立网络用例通过，无丢包错包

### Task 3: 混合组网验证

**内容：**
- 执行 TC-003（4HOST 1PORT 共存模式）
- 手动补充 TC-012（半共存/不共存）

**验收：**
- 多流量并发时各 Host 业务均正常

### Task 4: 异常与隔离验证

**内容：**
- 替换 TC-004 中 PFR/PFLR 占位命令为实际命令
- 执行 TC-004、TC-013、TC-014

**验收：**
- PF/Host 级复位隔离符合预期；Global/Sys Reset 影响所有 Host

### Task 5: 资源反压验证

**内容：**
- 替换 TC-005 中共享资源占满占位命令
- 执行 TC-005、TC-015

**验收：**
- 共享资源反压影响所有 Host，独占资源反压只影响单个 Host

### Task 6: 稳定性与性能均衡

**内容：**
- 执行 TC-006（默认 24h，可按需缩短预跑）
- 执行 TC-016 性能均衡分析

**验收：**
- 24h 无卡死/丢包/错包；各 Host 带宽/延时方差在合理范围

### Task 7: 报告与回归

**内容：**
- 汇总测试结果，生成测试报告
- 对失败用例进行问题定位、修复、回归

**验收：**
- 测试报告通过评审；P0/P1 问题全部关闭

---

## 11. 附录

### 11.1 关键命令参考

```bash
# 查看 PF 数量
lspci | grep -i mellanox | wc -l

# 查看 IB/RDMA 设备
ibstat -l

# 启动 opensm（按 GUID）
nohup opensm -g <NODE_GUID> -B -e -f /var/log/opensm.log > /dev/null 2>&1 &

# RDMA 带宽测试
ib_read_bw -d <dev> -b -D 60 -F
ib_read_bw -d <dev> -b -D 60 -F <server_ip>

# 以太带宽测试
iperf3 -s -p 5201
iperf3 -c <server_ip> -p 5201 -t 60 -f m

# 错包计数
ethtool -S <if> | grep -E 'rx_errors|tx_errors'
```

### 11.2 相关文档

- `docs/multihost_verification_analysis.md`
- `ps3/test/esat/nic100/scripts/multihost_test_tc001.py` ~ `tc006.py`
- `AGENTS.md`（项目规范）
