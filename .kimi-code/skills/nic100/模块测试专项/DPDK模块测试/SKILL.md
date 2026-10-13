---
name: DPDK模块测试
description: 指导NIC100框架下DPDK模块的测试要点，包括DPDK环境配置、驱动绑定、 hugepage、testpmd和性能测试。
---

# NIC100 DPDK 模块测试指南

## 测试范围

- DPDK 环境准备（hugepage、驱动绑定）
- DPDK 应用编译与运行
- testpmd 基础转发与性能测试
- DPDK 与内核驱动切换
- PMD 相关参数验证

## 核心命令与工具

| 命令/工具 | 用途 |
|-----------|------|
| `dpdk-devbind.py` | 网卡与 DPDK 驱动绑定/解绑 |
| `testpmd` | DPDK 基础转发与性能测试 |
| `dpdk-hugepages.py` | hugepage 配置 |
| `lspci` / `pcie_operation.py` | 查看 PCIe 设备 |
| `ethtool` | 查看网卡基础信息 |

## 环境准备

1. **加载 VFIO/IGB_UIO 驱动**
   ```bash
   modprobe vfio-pci
   # 或
   modprobe uio
   insmod igb_uio.ko
   ```

2. **配置 hugepage**
   ```bash
   echo 1024 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages
   ```

3. **绑定网卡到 DPDK 驱动**
   ```bash
   dpdk-devbind.py --bind=vfio-pci <pci_addr>
   ```

## testpmd 常用命令

```bash
# 启动双端口转发
testpmd -l 0-3 -n 4 -- -i --portmask=0x3 --nb-cores=2

# 常用交互命令
start tx_first    # 开始转发
stop              # 停止
show port stats all
set fwd mac       # 设置二层转发模式
```

## 脚本层注意

- 使用 `pcie_operation.py` / `pcie_info.py` 获取 PCI 地址
- 绑定/解绑操作前后记录网卡状态，便于恢复
- DPDK 测试前后务必恢复内核驱动，避免影响后续用例

## 脚本位置

- 公共库：`ps3/test/esat/nic100/scripts/script_libs/pcie_operation.py`
- 辅助库：`ps3/test/esat/nic100/scripts/script_libs/pcie_info.py`

## 注意事项

1. DPDK 占用 CPU 核心，注意核心隔离和 NUMA 对齐
2. hugepage 配置需考虑内存大小和测试需求
3. 绑定 DPDK 驱动后，内核协议栈不再管理该网口
4. 测试结束后在 `post` 阶段解绑并恢复内核驱动
5. DPDK 版本与网卡驱动版本需匹配

---

## OVS flex_pattern 测试用例与脚本生成规范

> 本章节整理自 2026-07-29 针对 `xmind文件夹/OVS.xmind` 中 `flex_pattern` 异常测试点的用例/脚本生成实践，用于指导同类型 DPDK OVS 测试用例的生成。

### 用例编号规则

沿用项目编号体系：

```
nic_linux_dpdk_ovs_f_<平台编号>_<子模块编号>_<功能项>_<检查点>
```

- 产品名：`nic`
- 测试平台：`linux`
- 模块名：`dpdk`
- 子模块名：`ovs`
- 用例类型：`f`（功能）
- 平台编号：`02`（igb_uio DPDK）
- 子模块编号：`74`（OVS flex_pattern）
- 功能项：`001`
- 检查点：按顺序递增，如 `019`、`020` ...

模式区分：

| 模式 | 编号前缀示例 | 说明 |
|---|---|---|
| Legacy / PF / 非流隔离 | `nic_linux_dpdk_ovs_f_02_74_001_0xx` | 基础异常场景 |
| switchdev / VF / 流隔离 | `nic_linux_dpdk_ovs_f_02_74_101_0xx` | 与 Legacy 同场景的平台变体 |

后续新增异常点时，按现有最大检查点顺序补全即可。

### Excel 用例规范

**输出位置**：

```
excel测试用例文件夹/YYYY-MM-DD_HH-MM-SS/OVS_flex_pattern_异常测试.xlsx
```

**18 列标准**：

```
所属产品、所属模块、优先级、用例类型、脚本名称、测试编号、用例标题、
前提条件、测试步骤、预期结果、检查项/测试点、测试场景、用例测试分类、
负责人、作者、测试平台实现自动化、需求点/测试对象、物理环境
```

**公共字段**：

| 字段 | 值 |
|---|---|
| 所属产品 | NIC100 |
| 所属模块 | DPDK-OVS |
| 优先级 | A1 |
| 用例类型 | f |
| 用例测试分类 | 系统测试-功能 |
| 测试平台实现自动化 | Linux |
| 需求点/测试对象 | OVS flex_pattern 异常处理 |
| 物理环境 | 双机 / 单 NIC100 网卡 |
| 负责人 | liuchang6 |
| 作者 | liuchang6 |

**脚本名称列**：

```
ps3/test/esat/nic100/scripts/nic100/linux/dpdk/ovs/case_ovs/<用例编号>_<英文描述>.py
```

示例：

```
ps3/test/esat/nic100/scripts/nic100/linux/dpdk/ovs/case_ovs/nic_linux_dpdk_ovs_f_02_74_001_019_field_base_over_mtu.py
```

### 已确认的 flex_pattern 异常测试点

#### 已分配编号（12 条）

| 序号 | 测试编号 | 用例标题 |
|---|---|---|
| 1 | `nic_linux_dpdk_ovs_f_02_74_001_019` | field_base 超过 MTU |
| 2 | `nic_linux_dpdk_ovs_f_02_74_001_020` | field_size 超过 MTU |
| 3 | `nic_linux_dpdk_ovs_f_02_74_001_021` | spec 长度超过最长匹配位置（Legacy） |
| 4 | `nic_linux_dpdk_ovs_f_02_74_001_022` | spec 长度超过最长匹配位置（switchdev） |
| 5 | `nic_linux_dpdk_ovs_f_02_74_001_023` | 采样字段超过 16 word |
| 6 | `nic_linux_dpdk_ovs_f_02_74_001_024` | 字段长度与位置非 16 倍数 |
| 7 | `nic_linux_dpdk_ovs_f_02_74_001_025` | 非 e-switch 层下发规则失败 Legacy group2 |
| 8 | `nic_linux_dpdk_ovs_f_02_74_101_025` | 非 e-switch 层下发规则失败 switchdev group3 |
| 9 | `nic_linux_dpdk_ovs_f_02_74_001_026` | input_link 指定超过 1 个（Legacy） |
| 10 | `nic_linux_dpdk_ovs_f_02_74_101_026` | input_link 指定超过 1 个（switchdev） |
| 11 | `nic_linux_dpdk_ovs_f_02_74_001_027` | output_link 不允许添加（Legacy） |
| 12 | `nic_linux_dpdk_ovs_f_02_74_101_027` | output_link 不允许添加（switchdev） |

#### XMind 中标注“不再测试”的点

以下节点不生成用例：

- field_base 超过 flex 协议头长度
- field_size 超过 flex 协议头长度
- 协议头长度超过 MTU

### Python 测试脚本规范

#### 目录与命名

- 目录：`ps3/test/esat/nic100/scripts/nic100/linux/dpdk/ovs/case_ovs/`
- 命名：`<用例编号>_<英文描述>.py`，全小写，下划线分隔
- 同级目录需放置 `add_syspath.py`

#### 类与结构

- 继承 `scripts.script_libs.script_base.ScriptBase`
- 重写 `set_parameters`、`check_own_environment`、`prepare`、`do`、`post`
- 类名使用 PascalCase
- 文件头包含 case number、case title、author（liuchang6）、steps、expected

#### testpmd 交互方式

**必须使用 `screen` 托管 testpmd，并通过 `screen -X hardcopy` 抓取当前屏幕回显做校验。**

启动：

```python
cmd = (
    f"screen -dmS {cls.SCREEN_NAME} bash -c "
    f"'{cls.DPDK_TESTPMD} -l 0-3 -n 4 -a {cls.pf_bdf} "
    f"--file-prefix={cls.FILE_PREFIX} --iova-mode=pa "
    f"-- --forward-mode=io -i --rxq=4 --txq=4 "
    f"> {cls.TESTPMD_LOG} 2>&1'"
)
CommandOperation.execute_command_with_error(cmd, CmdExecuteAdressEnum.SERVER.value)
```

发送命令：

```python
safe_cmd = cmd.replace("'", "'\\''")
screen_cmd = f"screen -S {cls.SCREEN_NAME} -X stuff '{safe_cmd}\r'"
CommandOperation.execute_command_with_error(screen_cmd, CmdExecuteAdressEnum.SERVER.value)
```

读取回显：

```python
hardcopy_cmd = f"screen -S {cls.SCREEN_NAME} -X hardcopy {cls.HARDCOPY_FILE}"
CommandOperation.execute_command_with_error(hardcopy_cmd, CmdExecuteAdressEnum.SERVER.value)
# 读取 HARDCOPY_FILE 内容并校验
```

停止：

```python
CommandOperation.execute_command_with_error(
    f"screen -S {cls.SCREEN_NAME} -X stuff 'quit\r'",
    CmdExecuteAdressEnum.SERVER.value,
)
time.sleep(2)
CommandOperation.execute_command_with_error(
    f"screen -S {cls.SCREEN_NAME} -X quit 2>/dev/null || true",
    CmdExecuteAdressEnum.SERVER.value,
)
```

#### 校验逻辑

- 错误模式：`port_flow_complain`、`Failed`、`failed`、`not supported`、`not valid`、`Invalid argument`、`error`
- 成功标记：根据命令传入，如 `created`、`Flow rule #0 created`
- `show port stats 0` 输出从 hardcopy 中解析 `RX-packets:`

#### 环境准备与清理

**prepare 阶段**：

1. 获取 PF 设备名和 BDF
2. 记录原驱动和 MAC 地址
3. 绑定 PF 到 `vfio-pci`
4. 创建 flex profile JSON
5. 清理日志/hardcopy 临时文件

**post 阶段**：

1. 恢复 PF 原驱动绑定
2. 删除临时 JSON、日志、hardcopy 文件
3. 确保 screen 会话已结束

##### OVS / switchdev 场景下的 VF 处理

在 OVS flex_pattern 等 switchdev 测试场景中，VF 保持内核驱动即可，**不需要**通过 `dpdk-devbind.py` 绑定到 `vfio-pci`。创建 VF 后只需记录其 BDF，testpmd 直接使用 `-a $VF_BDF` 启动。

对应的环境流程：

- **prepare**：创建 VF → 获取 VF BDF → 切换 switchdev 模式 → 创建 flex JSON → 启动 testpmd（VF）
- **testpmd 启动后**：先执行 `flow isolate 0 on` 开启流隔离
- **post**：停止 testpmd → 移除 VF（`echo 0 > /sys/class/net/$PF/device/sriov_numvfs`）→ 恢复 e-switch 为 legacy → 删除临时文件

> 注意：PF 在此过程中始终保持内核驱动，不需要记录/恢复 PF 原驱动。

#### 发包方式

- 从 client 端（对端机器）使用 scapy 发送匹配报文
- 目的 MAC 使用 server PF 的 MAC
- 若环境为单机，需改用 loopback 或第二端口方案

### 命令准确性要求

生成脚本时，testpmd 命令必须与实际 DPDK 版本一致。若 XMind 中命令存在拼写错误、参数缺失或与官方帮助文档冲突，应：

1. 优先核对项目内现有 skill/脚本
2. 上机执行 `--help` / `man` / 试运行确认
3. 保留原意，最小改动纠正
4. 在脚本注释中注明修正原因

### 质量检查清单

生成后用例/脚本需确认：

- [ ] 18 列 Excel 无空值
- [ ] 用例编号连续、模式变体编号规范
- [ ] 脚本名与 Excel 脚本名称列一致
- [ ] 脚本继承 `ScriptBase`，含 prepare/do/post
- [ ] testpmd 使用 screen + hardcopy 校验
- [ ] 错误时调用 `create_bug` 记录缺陷
- [ ] 临时文件在 post 阶段清理
- [ ] 不修改 `.xlsx` 源文件，通过代码生成

### 参考文件

- XMind 源文件：`xmind文件夹/OVS.xmind`
- Excel 输出：`excel测试用例文件夹/2026-07-29_09-51-16/OVS_flex_pattern_异常测试.xlsx`
- 脚本示例：`ps3/test/esat/nic100/scripts/nic100/linux/dpdk/ovs/case_ovs/nic_linux_dpdk_ovs_f_02_74_001_019_field_base_over_mtu.py`
