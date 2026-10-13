---
name: 测试用例生成
description: Use when generating NIC100 test cases, Excel rows, or Python test scripts from Excel/XMind/requirements, and needing to align with project naming, directory, and code-style conventions.
---

# NIC100 测试用例生成指南

## Overview

本 skill 指导如何根据 Excel 测试用例、XMind 测试点、需求文档或现有代码模式，在 NIC100 框架中生成规范的测试用例与 Python 测试脚本。内容已融合项目《用例规范.xlsx》《针对测试脚本的代码规范.docx》以及 XMind 转 Excel 的实践规则。

## When to Use

- 从 XMind/Excel/需求文档生成新的测试用例或脚本时
- 为现有用例补全或修改脚本名称、编号、目录位置时
- 将 XMind 测试点展开为项目标准 18 列 Excel 测试用例时
- 评审生成的用例/脚本是否符合项目规范时
- 不确定某个模块的二级编号或脚本应放在哪个子目录时

## 输入来源

- Excel 测试用例文件（如项目根目录的 `多PF测试-测试用例.xlsx`）
- XMind 测试点（如 `xmind文件夹/multi host.xmind`）
- 需求文档或手工测试步骤
- 现有代码模式与模块依赖关系

## 输出位置

- 通用用例：`测试脚本文件夹/YYYY-MM-DD_HH-MM-SS/`
- 模块用例：`测试脚本文件夹/YYYY-MM-DD_HH-MM-SS/`
- 生成配置：`ps3/test/esat/nic100/scripts/generate_scripts.xlsx`
- Excel 测试用例：`excel测试用例文件夹/YYYY-MM-DD_HH-MM-SS/`
- 批量生成脚本：`测试脚本文件夹/YYYY-MM-DD_HH-MM-SS/`
- 临时生成脚本/中间文件：`临时文件夹/`

## 生成原则

1. **一个用例一个 .py 文件**
2. **不复写已有基类**，只继承使用
3. **脚本名与用例编号对应**，格式为 `<用例编号>_<脚本描述>.py`
4. **遵循项目既有代码风格**
5. **包含 prepare / do / post 三阶段**
6. **校验用例中命令的准确性**：测试用例中提到的命令可能存在拼写错误、选项误用或参数缺失，生成脚本时必须校验并纠正

## 1. 用例编号规范

格式：

```
产品名_测试平台_模块名称_用例类型_测试平台编号_子模块编号_功能检查项编号_测试检查点编号
```

示例：

```
nic_linux_fw_f_01_02_001_001
```

| 字段 | 说明 | 示例 |
|------|------|------|
| 产品名 | `nic` | nic |
| 测试平台 | `linux` / `windows` / `kvm_linux` / `hyperv_linux` 等 | linux |
| 模块名称 | 英文代码：`fw` / `driver` / `dpdk` / `rdma` / `ib` 等，**不是中文** | fw |
| 用例类型 | `f` 功能、`p` 性能、`str` 压力、`sta` 稳定、`c` 兼容、`r` 可靠 | f |
| 测试平台编号 | 2 位，linux 主机驱动/以太类为 `01`；igb_uio DPDK 为 `02`；vfio-pci DPDK 为 `03`；kvm_linux 为 `04` 等 | 01 |
| 子模块编号 | 2 位，由组长分配；无现成编号时标记为**待分配** | 02 |
| 功能检查项编号 | 3 位 | 001 |
| 测试检查点编号 | 3 位 | 001 |

## 2. 脚本命名规范

格式：

```
<用例编号>_<脚本描述>.py
```

要求：

- **全部小写**，单词间用下划线 `_` 分隔
- **脚本描述中禁止使用编号代替功能说明**
- 描述应体现检查项、测试场景、用例内容；如同时存在 kernel/dpdk 两种模式，可在描述末尾加 `_kernel` / `_dpdk`

示例：

```
nic_linux_fw_f_01_02_001_001_upgrade_check_the_effectiveness_of_single_package_upgrade.py
nic_linux_driver_vlan_filter_f_01_24_001_001_basic_port_vlan_config_kernel.py
```

## 3. 目录结构规范

```
测试脚本文件夹/YYYY-MM-DD_HH-MM-SS/
```

用例编号中的英文模块代码与目录中的中文模块名映射：

| 英文模块代码 | 中文目录名 | 说明 |
|-------------|-----------|------|
| `driver` | `以太` | 主机以太网驱动相关功能 |
| `dpdk` | `dpdk` | DPDK 用户态驱动 |
| `rdma` | `rdma` | RDMA 功能 |
| `ib` | `ib` | InfiniBand 功能 |
| `fw` | `fw` | 固件相关 |

常用模块编号参考：

| 模块 | 一级/二级编号 | 用例编号前缀示例 |
|------|--------------|------------------|
| 主机驱动 driver / 以太 | linux: 01；driver 子模块 11-50 | `nic_linux_driver_xxx_x_01_xx_xxx_xxx` |
| 以太网 VLAN filter | driver 子模块 24 | `nic_linux_driver_vlan_filter_x_01_24_xxx_xxx` |
| DPDK | linux igb_uio: 02；vfio-pci: 03；dpdk 子模块 41-59 | `nic_linux_dpdk_rss_x_02_41_xxx_xxx` |
| RDMA kernel | rdma: 06；kernel 子模块 01-50 | `nic_linux_rdma_kernel_device_x_06_10_xxx_xxx` |
| RDMA 用户态 | rdma: 06；用户态 51-99 | `nic_linux_rdma_device_x_06_61_xxx_xxx` |
| IB | ib: 07；子模块 01-99 | `nic_linux_ib_device_x_07_01_xxx_xxx` |
| FW CLI | fw: 01；cli 子模块 01 | `nic_linux_fw_cli_x_01_01_xxx_xxx` |
| FW Upgrade | fw: 01；upgrade 子模块 02 | `nic_linux_fw_upgrade_x_01_02_xxx_xxx` |

## 4. Excel 用例字段规范

沿用项目现有 18 列模板：

```
所属产品、所属模块、优先级、用例类型、脚本名称、测试编号、用例标题、
前提条件、测试步骤、预期结果、检查项/测试点、测试场景、用例测试分类、
负责人、作者、测试平台实现自动化、需求点/测试对象、物理环境
```

注意：

- `用例类型` 列应使用规范代码 `f/p/str/sta/c/r`，而非中文描述
- `优先级` 建议使用 A1/A2/B1/B2/C1/C2 等级体系；如用数字需与团队约定一致
- `脚本名称` 必须与生成脚本的文件名一致
- **硬性规定：测试步骤与预期结果必须一一对应**
  - `测试步骤` 列中的每个编号步骤，在 `预期结果` 列中必须有同编号条目与之对应
  - 禁止出现有步骤无预期、有预期无步骤、编号跳跃或错位的情况
  - 每个预期条目只写该步骤应达到的验证结果，不重复步骤原文
  - 环境清理类步骤（如关闭VM、还原环境）也必须有对应预期（如"环境恢复成功"）

## 5. 新特性归属与模糊场景处理

### 5.1 如何确定测试平台编号

| 场景 | 平台编号 | 说明 |
|------|---------|------|
| Linux 主机驱动/以太网功能 | `01` | 包括 VLAN、MAC filter、RSS、TSO 等 |
| Linux igb_uio DPDK | `02` | DPDK 绑定 igb_uio 驱动 |
| Linux vfio-pci DPDK | `03` | DPDK 绑定 vfio-pci 驱动 |
| KVM Linux 虚机 | `04` | 物理机 Linux + 虚机 Linux |
| Windows 主机驱动 | `10` | Windows 原生驱动 |
| 其他平台 | 参见《用例规范.xlsx》 | 按规范分配 |

### 5.2 如何确定子模块编号

1. **先查现有子模块**：在《用例规范.xlsx》中找到功能最接近的子模块，复用其编号
2. **无现成编号时**：在本 skill 的模块编号表中查找最接近的分类
3. **仍无法确定**：标记为 **待组长分配**，不要自行编造新编号

### 5.3 用例编号中是否允许复合模块名

**不允许**。`模块名称` 字段应使用单一英文代码（如 `driver`、`fw`、`rdma`）。功能细节应放到：

- 用例编号的后面字段：`..._功能检查项编号_测试检查点编号`
- 脚本描述部分：`<用例编号>_basic_port_vlan_config_kernel.py`

### 5.4 port vlan 归属示例

`port vlan` 属于 SR-IOV VF 的 VLAN 配置功能，与 VLAN filter 最接近，因此：

- **用例编号**：`nic_linux_driver_vlan_filter_f_01_24_xxx_xxx`
- **脚本名**：`nic_linux_driver_vlan_filter_f_01_24_001_001_basic_port_vlan_config_kernel.py`
- **目录**：`测试脚本文件夹/YYYY-MM-DD_HH-MM-SS/`

如果后续团队为 port vlan 单独分配了新子模块编号，再整体迁移。

## 6. 命令准确性校验

### 6.1 校验规则

生成脚本时，如果测试用例中包含具体命令（如 `perfquery`、`smpquery`、`rdma`、`ib_read_bw` 等），必须执行以下检查：

1. **识别可疑命令**
   - 命令拼写异常（如 `perfqury`、`smpqery`）
   - 选项或参数与官方帮助文档不符
   - 命令组合逻辑冲突（如聚合选项与单端口参数混用）
   - 用例描述与实际命令不匹配
   - 同一用例中命令风格前后不一致

2. **优先查询项目内相关 skill**
   - IB/RDMA 工具类命令：参考 `perfquery计数器查询`、`smpquery子网管理查询`、`rdma工具使用`
   - IB 模块测试流程：参考 `IB模块测试`、`IB基础概念与设备检查`
   - 其他模块命令：参考对应模块专项 skill
   - 命令回显与错误判断：参考 `IB命令处理与回显解析`

3. **上机或文档二次验证**
   - 如果 skill 未覆盖或版本行为不确定，登录目标环境执行 `--help` / `man` / 试运行确认
   - 搜索项目既有脚本 `ps3/test/esat/nic100/scripts/`，确认是否存在相同命令的用法

4. **纠正原则**
   - **保留原意**：只修正错误部分，不改变用例原本想测试的内容
   - **最小改动**：优先修正拼写、选项、参数顺序等表面错误
   - **等效替换**：原命令确实不存在时，用功能等价的标准命令替换
   - **不臆造**：不确定时不强行纠正，需在脚本注释中标注待确认

### 6.2 纠正示例

| 用例中的错误命令 | 问题 | 纠正后 |
|-----------------|------|--------|
| `perfquery -a 32 1` | `-a` 表示聚合所有端口，与单端口 `1` 语义冲突 | `perfquery 32 1` 或 `perfquery -a 32` |
| `smpquery portinfo 3` | 缺少端口号，默认查询端口 0 | `smpquery portinfo 3 1` |
| `rdma link show mlx5_0` | 缺少端口索引 | `rdma link show mlx5_0/1` |
| `perfquery -R 32 1`（原意读取并清零） | `-R` 表示仅清零 | `perfquery -r 32 1` |

### 6.3 记录方式

- 在生成的测试脚本注释中注明修正原因，例如：
  ```python
  # 原用例命令为 "perfquery -a 32 1"，-a 表示聚合所有端口，与单端口参数冲突
  # 已修正为 "perfquery 32 1"
  ```
- 如果改动较大或存在不确定性，单独整理差异说明供用户确认

## 7. 从 Excel 转换

1. 读取 Excel 中的“测试步骤”、“预期结果”、“前置条件”
2. 将步骤映射为 `do()` 中的函数调用
3. 将预期结果映射为断言或结果检查
4. 将前置条件映射为 `prepare()`
5. 将环境恢复映射为 `post()`

## 8. 从 XMind 转换

适用于将 XMind 测试点直接转换为项目标准的 Excel 测试用例，如 `multi host.xmind` → `MultiHost_RDMA_测试用例.xlsx`。

### 8.1 输入与节点约定

- XMind 文件（`.xmind`），解压后读取 `content.json`
- XMind 中需包含的规范节点：
  - `用例规范 → 固定点勿动`：所属产品、所属模块、用例类型、测试用例列表头
  - `用例规范 → 需修改点`：所属模块、需求点/测试对象、优先级策略、测试编号、脚本名称、负责人、作者
  - `测试点分解`：FT（Feature Topic）→ TC（Test Case）层级
  - 每个 TC 下包含：变化因子、测试策略、前置条件、测试步骤、测试预期、测试拓扑

### 8.2 解析 FT / TC

- FT 节点格式：`[FTn]<标题>-<估计用例数>`
- TC 节点格式：`[<用例类型标签>][TCn][可选demo]<标题>-<估计用例数>`

### 8.3 用例类型映射

按 XMind `用例规范 → 用例类型` 的中文分类输出：

| TC 标签 | Excel 用例类型 |
|---|---|
| 正向用例 | 系统测试-功能 |
| 性能用例 | 系统测试-性能 |
| 可靠性用例 | 系统测试-可靠性 |
| 稳定性用例 | 系统测试-稳定性 |
| 压力用例 | 系统测试-压力 |
| 兼容性用例 | 系统测试-兼容性 |
| 应用场景用例 | 系统测试-应用场景 |
| 协议用例 | 系统测试-协议 |

测试编号仍使用规范代码：`f / p / r / sta / str / c / scene / protocol`。

### 8.4 优先级策略映射

按 XMind `用例规范 → 需修改点 → 优先级策略`：

| 用例类型 | 优先级 |
|---|---|
| 系统测试-功能 | A1 |
| 系统测试-可靠性 | C1 |
| 系统测试-压力 / 性能 / 兼容性 / 稳定性 | C2 |

### 8.5 变化因子展开

读取 TC 下 `变化因子` 中的 `[TE1]业务类型`、`[TE2]业务包长`、`[TE3]port/host/pf` 等，并按 `测试策略` 展开：

- `[遍历]` / 直接列在 `[笛卡尔]` 下：取该因子的全部值
- `[随机值]`（条件：只采样1次，每次取1个值）：每个组合中循环取一个值
- `[边界值]`：取首、中、尾 3 个值
- `[正交]`：按遍历处理（或实现正交表）

组合数 = 所有“遍历/边界/正交”因子取值个数的笛卡尔积；采样因子按全局计数器循环。

### 8.6 选择型变化因子处理

识别“任选一个”写法：

```
业务类型
└── rdma read/rdma write/rdma rc send/rdma ud send/rdma atomic中任选一个
```

生成 Excel/脚本时，**不要**把“`XX/XX/XX 任选一个`”原话照搬进用例标题或场景。应解析候选列表，并**为每个生成的用例选取一个具体值**。

均匀分布规则：

1. **解析候选值**：按 `/`、`、`、`，` 等分隔符拆出候选列表
2. **不展开全排列**：不要把 5 个候选与正交维度做笛卡尔积变成 5× 用例
3. **全局均匀循环**：使用全局计数器为每个基础场景依次分配候选值，保证同一选择维度在所有用例之间均匀分布
   - 例：10 个可靠性用例 × 5 种业务类型 → 每种业务类型各 2 条
4. **场景和标题显示具体值**：生成的 `测试场景` 和 `用例标题` 中应显示 `业务类型: rdma write`，而不是 `rdma read/...中任选一个`

### 8.7 脚本名称与用例标题

脚本名称示例结构：

```
<XMind中的固定路径前缀>/<测试编号>_<业务类型>_<包长>_<端口配置>_<附加因子>.py
```

示例：

```
nic800/linux/rdma/multi_host/script_case/nic_linux_rdma_multi_host_f_06_100_001_001_rdma_read_64B_1port_2host_1pf.py
```

用例标题格式：

```
Multi_Host_<用例类型>_<TC标题（逗号替换为下划线）>_业务:<业务>_包长:<包长>_<端口配置>_<附加因子>
```

示例：

```
Multi_Host_系统测试-功能_单port_多host_共享port_pf两两打流_业务:rdma_read_包长:64B_1port2host1pf
```

### 8.8 业务类型到 perftest 命令

生成 Excel 时，如果 XMind 步骤中以 `ib_read_bw` 作为示例命令，需按实际选中的业务类型替换：

| 业务类型 | 带宽命令 | 延迟命令 |
|---------|---------|---------|
| rdma read | `ib_read_bw` | `ib_read_lat` |
| rdma write | `ib_write_bw` | `ib_write_lat` |
| rdma rc send | `ib_send_bw` | `ib_send_lat` |
| rdma ud send | `ib_send_bw --ud` | `ib_send_lat --ud` |
| rdma atomic | `ib_atomic_bw` | `ib_atomic_lat` |

若 TC 标题/场景包含“延迟/时延/latency”，或业务因子值指定 `*/lat`，则使用 `*_lat`。

### 8.9 Excel 格式要求

1. **测试步骤列**
   - 直接以 `1. XXX` 编号格式开始
   - **不要**在步骤前添加 `# 当前配置：业务类型=...，包长=...，拓扑=...` 等注释行
   - 配置信息应体现在 `用例标题` 中

2. **预期结果列**
   - **不要**重复步骤原文（如 `1. 将所有的rdma设备两两组合...`）
   - 应为与步骤对应的纯预期结果，并带相同编号：
     ```
     1. 所有 RDMA 设备两两组合完成，业务并发执行，无冲突、无异常
     2. 成功读取到两端有效的 RDMA 设备名
     3. 两端 RDMA 设备状态均为 Active/LinkUp
     ```
   - 若 XMind 中已提供编号预期，优先使用并统一编号格式

### 8.10 字段来源

| Excel 列 | 来源 |
|---|---|
| 所属产品 | XMind `用例规范 → 固定点勿动 → 所属产品` |
| 所属模块 | XMind `用例规范 → 固定点勿动 → 所属模块` |
| 优先级 | 按用例类型映射 |
| 用例类型 | XMind 用例类型中文分类 |
| 脚本名称 | 固定路径前缀 + 测试编号 + 描述 |
| 测试编号 | `nic_linux_<模块>_<类型代码>_06_100_<功能项>_<检查点>` |
| 用例标题 | `Multi_Host_<用例类型>_<TC标题>_<因子详情>` |
| 前提条件 | XMind TC `前置条件` |
| 测试步骤 | XMind TC `测试步骤`（已替换 perftest 命令） |
| 预期结果 | XMind TC `测试预期` |
| 检查项/测试点 | TC 标题 |
| 测试场景 | FT 标题 |
| 用例测试分类 | 用例类型中文（功能/性能/可靠性/稳定性/压力/兼容性） |
| 负责人/作者 | XMind `用例规范 → 需修改点` |
| 测试平台实现自动化 | `Linux`（或其他平台） |
| 需求点/测试对象 | XMind `用例规范 → 需修改点 → 需求点/测试对象` |
| 物理环境 | XMind TC `测试拓扑` |

### 8.11 调用方式

1. 将 XMind 文件放入 `xmind文件夹/`
2. 解压 XMind 到临时目录，读取 `content.json`
3. 运行生成脚本（参考 `临时文件夹/generate_multi_host_excel.py`）
4. 检查 `excel测试用例文件夹/<时间戳>/` 下的输出

## 9. 产物目录规则

项目内所有生成产物必须按类型归集到指定目录，避免散落在仓库根目录：

| 产物类型 | 目标目录 | 组织方式 |
|---------|---------|---------|
| Excel 测试用例 | `excel测试用例文件夹/` | 按生成时间建立子目录 `YYYY-MM-DD_HH-MM-SS/` |
| 测试脚本（批量生成或模板） | `测试脚本文件夹/` | 按生成时间建立子目录 `YYYY-MM-DD_HH-MM-SS/` |
| 临时脚本、中间文件、调试文件等 | `临时文件夹/` | 由作者自行决策是否删除，**不要自动删除** |

### 9.1 生成方式选择

| 方式 | 场景 | 产物 |
|------|------|------|
| 保留生成脚本 | 需要反复生成、长期维护 | `framework/biz/excel/xxx.py` 或 `framework/libs/` |
| 一次性生成 | 只需当前批次 Excel/脚本 | 生成脚本本身存放于 `临时文件夹/`，不自动删除，最终 Excel/脚本按产物目录规则输出 |

选择一次性生成时，不要把临时脚本直接放在项目根目录或产物目录中，应统一放入 `临时文件夹/`，由作者后续自行决定是否保留。

## 10. 从现有代码模式生成

适用于没有现成 Excel/XMind，需要根据相似模块或历史脚本生成新脚本的场景。

1. **扫描项目结构**
   - 使用 `framework/biz/case_script_file_create.py` 或 `scripts/analyze_dependencies.py`
   - 识别目标模块目录下的现有脚本
   - 梳理模块间 import 依赖关系（参考「网卡测试框架」skill 的依赖分析部分）

2. **分析参考脚本**
   - 提取类结构、继承关系、方法划分
   - 梳理 import 依赖
   - 总结该模块常用的命令封装和断言模式

3. **确定新脚本边界**
   - 明确用例编号、模块归属、前置条件、测试步骤、预期结果
   - 对照相似脚本，避免遗漏 `post` 清理

4. **生成并裁剪**
   - 基于参考脚本生成模板，可使用模板生成器：
     ```bash
     python scripts/generate_script_template.py \
       --module-name "new_feature" \
       --output-dir "./new_scripts" \
       --based-on "existing_similar_module"
     ```
   - 生成器会分析参考模块的结构和样式，自动处理导入语句
   - 删除与本次用例无关的逻辑
   - 替换用例编号、设备名、IP、LID 等变量
   - 按「缺陷自动记录」skill 的要求补充 Bug 记录代码

5. **验证依赖**
   - 检查 import 语句是否有效
   - 确认无循环依赖
   - 必要时运行语法检查：`python -m py_compile <script>.py`

## 11. 脚本模板要素

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用例编号：xxx
模块：IB/RoCE/以太/DPDK
作者：xxx
日期：xxx
描述：xxx
"""

from script_libs.script_base import ScriptBase

class XxxTest(ScriptBase):
    @classmethod
    def prepare(cls):
        super().prepare()
        # 前置准备

    @classmethod
    def do(cls):
        # 测试步骤
        pass

    @classmethod
    def post(cls):
        # 环境清理
        super().post()

if __name__ == "__main__":
    XxxTest().run()
```

## 12. 质量检查

生成后确认：

- [ ] 导入语句正确且无循环依赖
- [ ] 用例中命令已校验准确性，错误命令已纠正并注明原因
- [ ] XMind 中 `A/B/C 任选一个` 类文本已解析为具体值，未原样搬入场景/标题
- [ ] 选择型维度的取值在同类用例间均匀分布
- [ ] 测试步骤中的 perftest 命令与选中的业务类型一致
- [ ] 命令参数符合当前环境
- [ ] 包含超时和异常处理
- [ ] `post` 阶段能恢复环境
- [ ] 失败时按规范记录 Bug
- [ ] 变量 `$lid` 等已替换为实际获取逻辑
- [ ] XMind 转 Excel 时，`测试步骤` 列以 `1. XXX` 编号开始，无 `# 当前配置` 类注释
- [ ] `预期结果` 列只写预期内容，不重复步骤原文，且编号与步骤对应
- [ ] **测试步骤与预期结果一一对应**：步骤编号数量与预期编号数量完全一致，无缺失、无错位、无跳跃
- [ ] 18 列均已填充，无空值
- [ ] 用例类型为中文（系统测试-xxx），测试编号使用规范代码
- [ ] 脚本名称与用例编号、描述一致，全部小写
- [ ] 用例标题以 `Multi_Host_用例类型_` 开头，逗号已替换为下划线
- [ ] 变化因子展开数与 XMind 中 `-N` 估计值基本一致

## 13. 常用工具

- `framework/biz/case_script_file_create.py`：用例脚本生成
- `framework/biz/excel/bug_result_excel_handle.py`：Bug 结果 Excel 处理
- `framework/biz/excel/report_excel_create.py`：报告 Excel 生成
- 自定义代码扫描脚本：用于分析项目结构、模块依赖和参考脚本模式

## 参考文件

- `相关规范/用例规范.xlsx`
- `相关规范/针对测试脚本的代码规范.docx`
