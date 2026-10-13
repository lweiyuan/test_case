# NIC100 以太(tc层/tx_scheduler) 测试用例生成规范

> 本规范整理自 2026-09-07 针对 `xmind文件夹/tc层测试设计.xmind` 中"测试用例"主题的用例生成实践，用于指导后续同类型以太网 tc 层（tx_scheduler 调度树）测试用例的生成。
> 放置位置：`相关规范/以太规范/SKILL.md`，不进入 `.kimi-code/skills/` 自动加载目录，避免影响其他使用者。

## 1. 适用范围

- 从 `xmind文件夹/tc层测试设计.xmind` 或同类 XMind 文件生成以太 tc 层（tx_scheduler）测试用例
- 生成项目标准 **29 列** Excel 测试用例（团队 tc 层模板，列顺序见 §3.2）
- 覆盖：dcb ets / strict / ets+strict 算法配置 tc、限速、VF、DPDK、RDMA sl、可靠性（反向/切速/链路/复位/加卸载驱动）、稳定性
- 组合因素采用**取值的全组合（笛卡尔积）**，每种组合生成一条用例

## 2. 用例编号规则

```
nic_linux_driver_tx_sched_<用例类型>_<平台编号>_<子模块编号>_<功能项>_<检查点>
```

- 产品名：`nic`
- 测试平台：`linux`
- 模块名：`driver`
- 子模块：`tx_scheduler`（子模块编号 `28`）
- 用例类型与编号映射：
  - 功能项 1~4（基础功能）→ `f`
  - 功能项 5~9（可靠性）→ `r`
  - 功能项 10~11（稳定性）→ `sta`
- 平台编号：`01`（linux 主机驱动/以太）
- 子模块编号：`28`（tx_scheduler）
- 功能项：3 位数字（`021`~`031`，见 §5）
- 检查点：3 位数字，按组内顺序递增（跨 TC 连续编号，组合拆分的每条用例也各占一个检查点）

示例：

```
nic_linux_driver_tx_sched_f_01_28_021_001
nic_linux_driver_tx_sched_f_01_28_021_003
nic_linux_driver_tx_sched_r_01_28_028_005
nic_linux_driver_tx_sched_sta_01_28_031_009
```

### 2.1 优先级与用例测试分类

| 用例类型 | 优先级 | 用例测试分类 |
|---|---|---|
| f（基础功能） | A1 | 系统测试-功能 |
| r（可靠性） | C1 | 系统测试-可靠性 |
| sta（稳定性） | C2 | 系统测试-稳定性 |

## 3. Excel 用例规范

### 3.1 输出位置

```
excel测试用例文件夹/YYYY-MM-DD_HH-MM-SS/tc层测试用例.xlsx
```

- 由生成脚本自动创建以当前时间命名的目录
- 工作表名：`TC层测试用例`；首行加粗表头，冻结首行（`freeze_panes='A2'`）
- 不直接修改 `.xlsx` 源文件，一律通过代码生成

### 3.2 29 列模板（列顺序必须严格一致）

```
测试编号、脚本名称、用例标题、所属产品、所属模块、需求点/测试对象、用例类型、
用例测试分类、分类、检查项/测试点、卡类别、物理环境、前提条件、测试场景、
测试步骤、预期结果、输入数据、优先级、冒烟测试、最小用例集、用例来源、
系统测试用例编号、测试平台实现自动化、时间(min)、作者、备注、已调试、
测试结果、实现阶段
```

### 3.3 公共字段取值

| 字段 | 值 |
|---|---|
| 所属产品 | 800G网卡 |
| 所属模块 | driver |
| 用例类型 | f / r / sta（见 §2.1） |
| 用例测试分类 | 系统测试-功能 / 系统测试-可靠性 / 系统测试-稳定性 |
| 分类 | 与"用例测试分类"取值相同 |
| 检查项/测试点 | TC 标题（组合拆分时含组合后缀，如 `...（VF个数=1；设置的tc数量包含=2）`） |
| 卡类别 | 空 |
| 前提条件 | 见 §4.5 |
| 输入数据 | 空 |
| 冒烟测试 | 否 |
| 最小用例集 | 空 |
| 用例来源 | XMind |
| 系统测试用例编号 | 空 |
| 测试平台实现自动化 | Linux |
| 时间(min) | 空 |
| 作者 | weiyuan1 |
| 备注 | 空 |
| 已调试 | 否 |
| 测试结果 | 空 |
| 实现阶段 | 空 |

> 注意：本规范实际生成的用例 `所属产品` 为 **800G网卡**（按实际产品填写，不沿用 DPDK 规范中的 NIC800 全局约定）。

### 3.4 脚本名称列

格式：

```
nic800/linux/driver/tx_scheduler/script_case_tc/<用例编号>_<英文描述>.py
```

- `<英文描述>` 全小写、下划线分隔，与 TC 标题对应（脚本描述见 §5 TC 清单）
- 前缀固定为 `nic800/linux/driver/tx_scheduler/script_case_tc/`（不加 `ps3/test/esat/nic100/scripts/`）

示例：

```
nic800/linux/driver/tx_scheduler/script_case_tc/nic_linux_driver_tx_sched_f_01_28_021_001_ets_rate_limit_unlimited_full_bandwidth_pf.py
```

### 3.5 用例标题

```
<标题前缀><TC标题><组合后缀>
```

- 标题前缀按分区+二级组确定：`TC层_基础功能_进内核PF配置tc_`、`TC层_可靠性_复位操作_` 等（见 §5）
- TC 标题取 XMind 中 TC 节点标题
- 组合拆分的用例追加后缀 `（因素1=值1；因素2=值2）`，例如：
  `TC层_基础功能_进内核PF配置tc_ets算法限速tc和未配置限速的tc的带宽为满流量（设置的tc数量包含=2）`

## 4. 组合因素与用例拆分规则

> **核心规则：组合因素的每个取值类型均为一条用例，采用所有因素取值的全组合（笛卡尔积），每种组合生成一条用例。**

### 4.1 组合因素解析（XMind 结构）

组合因素节点支持两种嵌套层级：

- **两层（绝大多数）**：`组合因素 → 步骤N遍历组合以下情况 → 因素名（如"设置的tc数量包含"/"VF个数"）→ [取值...]`
- **一层（仅复位操作）**：`组合因素 → 步骤N组合遍历以下几种情况 → [GLR/PFLR/PFR/...]`，此时因素名自动命名为 `复位类型`

> **`步骤N` 的含义**：组合遍历发生在 XMind 指定的具体步骤 N 中。生成用例时，组合取值（`<组合串>`）写入该步骤文本：`步骤N. <原文本>（<组合串>）`，不再在末尾追加额外遍历步骤，预期结果也不再追加额外行。

示例（一层，复位操作）：

```
组合因素
  └─ 步骤N组合遍历以下几种情况
       ├─ GLR
       ├─ PFLR/PFR
       └─ core reset
```

解析结果为：`复位类型 = {GLR, PFLR/PFR, core reset}`

### 4.2 全组合拆分

对解析出的每个因素（因素名→取值列表），取各因素取值的**笛卡尔积**，**每种组合生成一条用例**：

- 无组合因素的 TC：生成 1 条用例
- 1 个因素（PF 场景，如 `设置的tc数量包含` 取 3 个值）：3 条
- 2 个因素（VF 场景，如 `VF个数`×`设置的tc数量` = 3×3）：9 条

拆分后每条用例：

| 字段 | 内容 |
|---|---|
| 用例标题 | `<前缀><TC标题>（<组合串>）`，组合串形如 `VF个数=1；设置的tc数量包含=2` |
| 测试场景 | `组合覆盖：因素1∈{v1,v2}；因素2∈{v1,v2}`（完整取值范围） |
| 测试步骤 | XMind 指定"步骤N"处携带组合取值：`步骤N. <原文本>（<组合串>）`；未标注步骤时回退到含"设置带宽比例"的步骤；仍无可用步骤时末尾追加 `遍历组合以下情况：<组合覆盖>，本用例按组合执行（<组合串>）` |
| 预期结果 | 基础预期原样保留，与步骤一一对应（不再追加额外行） |

步骤/预期编号按 `1. 2. 3. ...` 顺序编号，与原始步骤一一对应。

### 4.3 已确认的组合因素取值（tc层测试设计.xmind）

| 场景 | 因素 | 取值 | 每条 TC 拆分条数 |
|---|---|---|---|
| PF 打流（基础功能/稳定性） | 设置的tc数量包含 | `2`、`2-4之间任意一个`、`支持的最大tc数` | 3 |
| VF 打流（基础功能/稳定性） | VF个数 × 设置的tc数量 | VF个数∈{`1`,`2`,`64`}；设置tc数量（前4个TC为{`2`,`4`,`8`}，其余为{`2`,`2-4之间任意一个`,`支持的最大tc数`}） | 9 |
| 复位-仅tc配置（可靠性） | 复位类型 | `GLR`、`PFLR/PFR`、`core reset` | 3 |
| 复位-创建VF后（可靠性） | 复位类型 | `GLR`、`PFLR/PFR`、`core reset`、`VFR`、`VFLR` | 5 |

> 实际取值以 XMind 中"组合因素"节点内容为准，生成脚本动态解析；上表为当前 xmind 已确认值。

### 4.4 无组合因素的 TC

- 生成 1 条用例，测试场景列取该组的场景说明（如 `ets/strict/ets+strict算法配置tc`）
- 测试步骤/预期结果原样保留（经 §6 的清理与补全处理）

### 4.5 前提条件

按二级组确定，逐条一行、以换行连接：

- **通用前提（GENERIC_PRE）**：
  1. `systemctl stop lldpad`
  2. `设置l2-fwd-offload为off`
  3. `所有的port都已物理互通`
  4. `用户已在 env_config.ini 或配置脚本中正确配置 RDMA 设备关系`
- **VF 组（添加VF后配置tc）**：通用前提 + `对PF创建VF设备`
- **切速组（切速和带宽分配交互）**：通用前提 + `支持多速率开关切换速率`
- 其余组（反向测试、与链路交互、复位操作、加卸载驱动）：仅通用前提

## 5. 已确认的 TC 清单（功能项编号）

### 5.1 基础功能（f，A1，功能项 021~024）

| 功能项 | 二级组 | TC 数 | 标题前缀 | 场景说明 | 需求点/测试对象 | 物理环境 |
|---|---|---|---|---|---|---|
| 021 | 进内核PF配置tc | 10 | `TC层_基础功能_进内核PF配置tc_` | ets/strict/ets+strict算法配置tc | tc层tx_sched调度树; dcb ets/strict/ets+strict配置与限速 | 测试PF/VF；双机iperf3打流 |
| 022 | 添加VF后配置tc | 11 | `TC层_基础功能_添加VF后配置tc_` | ets/strict/ets+strict算法配置tc(VF) | 同上 | 测试PF/VF；双机iperf3打流 |
| 023 | 配置tc,添加VF，将VF加入dpdk内 | 1（裸 TC） | `TC层_基础功能_` | tc配置+VF加入DPDK | tc层tx_sched调度树; VF加入DPDK | 测试PF/VF；DPDK(testpmd)环境 |
| 024 | 配置tc,添加VF,rdma中配置sl，进行打流 | 1（裸 TC） | `TC层_基础功能_` | tc配置+VF RDMA sl打流 | tc层tx_sched调度树; VF RDMA sl | 测试PF/VF；RDMA用户态环境 |

> 功能项 023/024 为**裸 TC**：XMind 中二级节点本身就是 TC（无子 TC 节点），各生成 1 条用例，无组合因素。

**功能项 021 的 10 条 TC（脚本描述）**：

```
ets_rate_limit_unlimited_full_bandwidth_pf       ets算法限速tc和未配置限速的tc的带宽为满流量
ets_send_bw_below_rate_limit_pf                  ets算法限速tc的发送带宽小于限速带宽，未配置限速的tc的带宽为满流量-限速带宽值
ets_no_rate_limit_full_bandwidth_pf              ets算法所有的tc均没有配置限速，且tc的带宽为满流量带宽
strict_rate_limit_unlimited_full_bandwidth_pf    strict算法限速tc和未配置限速的tc的带宽为满流量
strict_send_bw_below_rate_limit_pf               strict算法限速tc的发送带宽小于限速带宽，未配置限速的tc的带宽为满流量
strict_no_rate_limit_full_bandwidth_pf           strict算法所有的tc均没有配置限速，且tc的带宽为满流量带宽
strict_all_tc_share_port_bandwidth_pf            strict算法-所有tc均没有配置限速，且每个tc的发送带宽均不为0，且所有tc之和为端口的带宽值
ets_strict_strict_limit_ets_unlimit_pf           ets+strict-设置strict队列配置限速，配置ets的不配置限速，所有tc按照满带宽进行打流
ets_strict_ets_limit_strict_unlimit_pf           设置strict队列配置不配置限速，配置ets的配置限速，strict队列流量小于限速流量
ets_strict_no_rate_limit_full_bandwidth_pf       设置strict队列不配置限速，配置ets的不配置限速，所有tc的带宽为满流量
```

**功能项 022 的 11 条 TC（脚本描述）**：与 021 同构，后缀 `_pf` 改为 `_vf`（标题前缀 `添加VF后配置tc`），新增：

```
ets_strict_rate_limit_full_bandwidth_vf    ets+strict-添加VF后，设置strict 队列且配置限速，配置ets的配置限速，所有tc的带宽为满流量
```

### 5.2 可靠性（r，C1，功能项 025~029）

| 功能项 | 二级组 | TC 数 | 标题前缀 | 需求点/测试对象 |
|---|---|---|---|---|
| 025 | 反向测试 | 4 | `TC层_可靠性_反向测试_` | dcb配置反向/边界校验 |
| 026 | 切速和带宽分配交互 | 4 | `TC层_可靠性_切速和带宽分配交互_` | dcb maxrate与速率切换交互 |
| 027 | 与链路交互 | 1 | `TC层_可靠性_与链路交互_` | 链路down/up与tc配置交互 |
| 028 | 复位操作 | 2（组合拆分后 3+5=8 条） | `TC层_可靠性_复位操作_` | 复位后tc配置保持 |
| 029 | 加卸载驱动 | 1 | `TC层_可靠性_加卸载驱动_` | 驱动卸载/加载后tc配置保持 |

**反向测试（025）4 条 TC**：

```
reverse_tc_maxrate_gt_port_rate          对单一TC限速大于port限速
reverse_ets_bw_sum_not_equal_100         配置ets类型tc时，bw总和小于100或者大于100
reverse_strict_tc_bw_not_null            ets+strict类型tc时，设置strict的tc的 tc-bw不为空
reverse_queue_num_less_than_tc_num       队列数小于tc数
```

**切速和带宽分配交互（026）4 条 TC**：

```
rate_switch_up_pf_after_maxrate           先配置dcb maxrate后，然后向上切速，PF打流
rate_switch_down_pf_after_maxrate         配置完dcb maxrate后，port向下切速，PF打流
rate_switch_down_vf_after_maxrate         配置完dcb maxrate后，port向下切速，VF打流
rate_switch_up_vf_after_maxrate           先配置dcb maxrate后，然后向上切速，VF打流
```

**复位操作（028）2 条 TC（组合因素见 §4.3）**：

```
reset_after_tc_rate_limit       dcb ets算法配置tc与prio,tc与bw进行绑定后，设置限速后，进行复位
reset_after_vf_tc_rate_limit    dcb ets算法配置tc与prio,tc与bw进行绑定后，创建VF,设置限速后，进行复位
```

### 5.3 稳定性（sta，C2，功能项 030~031）

| 功能项 | 二级组 | TC 数 | 标题前缀 | 需求点/测试对象 |
|---|---|---|---|---|
| 030 | 进内核PF配置tc | 1（组合拆分后 3 条） | `TC层_稳定性_进内核PF配置tc_` | 打流中反复修改tc配置(网络不跌0) |
| 031 | 添加VF后配置tc | 1（组合拆分后 9 条） | `TC层_稳定性_添加VF后配置tc_` | 打流中反复修改tc配置(网络不跌0) |

TC 标题：`打流过程中，反复修改网卡tc配置信息.网络不存在长时间的跌0的情况`，脚本描述 `modify_tc_config_during_traffic_pf` / `modify_tc_config_during_traffic_vf`。

### 5.4 用例总数（当前 xmind 实测）

- 基础功能：PF 10×3=30（组合） + VF 11×9=99（组合） + dpdk 1 + rdma 1 = **131 条**
- 可靠性：反向 4 + 切速 4 + 链路 1 + 复位 3+5=8 + 加卸载 1 = **18 条**
- 稳定性：PF 3 + VF 9 = **12 条**
- 合计：**161 条**（其中含组合拆分 149 条）

## 6. 步骤/预期对齐与文本处理规则

### 6.1 步骤与预期对齐（pad_expected）

- 步骤与预期各自按出现顺序编号（`1. 2. 3. ...`），一一对应
- **预期少于步骤**：缺失预期按步骤语义自动补全：
  | 步骤关键词 | 补全预期 |
  |---|---|
  | 含"复位" | `复位成功` |
  | 含"卸载驱动" | `卸载驱动成功` |
  | 含"加载驱动" | `加载驱动成功` |
  | 含"切速" | `切速成功` |
  | 含"创建VF" | `创建VF成功` |
  | 含"检索/检查/获取/查询" | `调度树tc节点信息符合预期` |
  | 含"打流" | `打流成功，带宽符合预期` |
  | 含"链路" | `命令执行成功` |
  | 其他 | `命令执行成功` |
- **预期多于步骤**：尾部多余预期合并进最后一条预期（用 `；` 连接），保留全部源文本，不丢弃
- XMind 未展开步骤/预期的 TC：步骤填 `1. 待补充：xmind 未展开该用例的具体测试步骤`，预期填 `1. 待补充：xmind 未展开该用例的预期结果`

### 6.2 文本清理与错别字修正（clean_step / fix_typo）

- 去掉步骤/预期行首序号（`1.`、`1、`、`1)` 等），压缩连续空白
- 强制修正两类错别字（含步骤、预期、组合注入文本）：
  - `为限速的tc的带宽值未达标` → `未限速的tc的带宽值未达标`
  - `为配置限速tc` → `未配置限速tc`

### 6.3 实操指令注入（enhance_step_with_cmd）

来源：`tc层测试设计.xmind` → `tc学习` → `实操指令`（dump 52-72 行）。将 xmind 中的操作名匹配到测试步骤，在步骤文本末尾追加 `（指令：<cmd>）`。

- 匹配方式：正则取步骤行首编号 → 清理文本 → 剥离尾部 `（…）` 组合后缀 → **精确匹配**操作名（含 `iperf3` 的步骤用包含匹配）：
  | xmind 操作名 | 注入指令 |
  |---|---|
  | 设置dcbx host ieee | `dcb dcbx set dev <intf_name> host ieee` |
  | 查询dcb ets show dev <intf_name> | `dcb ets show dev <intf_name>` |
  | dcb ets 设置带宽比例（场景命令） | 按用例场景选：纯 ets → `dcb ets set dev <intf_name> tc-tsa all:ets tc-bw 0:25 1:25 2:25 3:25 4:0 5:0 6:0 7:0 prio-tc 0:0 1:1 2:2 3:3 4:0 5:1 6:2 7:3`；纯 strict → `... tc-tsa all:strict tc-bw 0:0 1:0 ...`；ets+strict 混合 → `... tc-tsa all:strict 0:ets 2:ets tc-bw 0:50 1:0 2:50 ...` |
  | 对tc 设置限速 | `dcb maxrate set dev <inf_name> tc-max 0:200 1:400 2:400 3:400 4:500 5:600 7:100` |
  | tc app绑定优先级与tos | `dcb app add dev eth0 dscp <dscp>:<prio>` |
  | 含 `iperf3` 的步骤 | `iperf3 --tos <tos>` |
- 场景命令选择（`ets_cmd_for`）：用例标题含 `ets_strict` → 混合命令；含 `strict` → 全 strict；否则全 ets
- **只注入测试步骤列，预期列不加指令**
- 反例（不注入）：步骤文本带组合后缀（如 `分配的bw总和小于100`、`设置的tc速率大于port的速率`、`复位类型=GLR`）不精确匹配操作名 → 不追加指令，避免在非法/反向配置步骤误加

## 7. 生成与校验脚本

- 生成脚本：`临时文件夹/generate_tc_excel.py`
  - 读取 `xmind文件夹/tc层测试设计.xmind`（zip 内 `content.json`），定位"测试用例"主题下的 基础功能/可靠性/稳定性 三个分区
  - 按 XMind 二级主题顺序遍历（`SUB_TOPIC_ORDER`），解析每个 TC 的 测试步骤/测试预期/组合因素/前提条件
  - 生成 29 列 Excel 并做自检
- 校验脚本：`临时文件夹/verify_tc_excel.py`
  - 按**列名**查找列（`h={name:i}`），不受列顺序影响
  - 校验字段取值、步骤/预期条数与编号、组合用例场景列等

### 7.1 生成脚本内置自检规则

- 步骤编号连续（`1~N`）、预期编号连续（`1~N`）
- 步骤与预期条数一致
- 无残留错别字（`为限速的tc的带宽值未达标` / `为配置限速tc`）
- 无残留"任选"
- XMind TC 数量与 `TC_LIST` 元数据不一致时输出警告

## 8. 质量检查清单

生成后用例需确认：

- [ ] 29 列顺序与 §3.2 完全一致
- [ ] 用例编号连续、功能项编号映射正确（f/r/sta）
- [ ] 脚本名称列前缀为 `nic800/linux/driver/tx_scheduler/script_case_tc/`，脚本描述全小写下划线
- [ ] 组合因素取全组合（笛卡尔积），每种组合一条，测试场景列含完整取值范围，组合取值写入 XMind 指定步骤（步骤N）
- [ ] 步骤/预期编号连续且一一对应，无残留错别字
- [ ] 公共字段取值符合 §3.3（所属产品=800G网卡、作者=weiyuan1、冒烟测试=否、已调试=否等）
- [ ] 生成脚本自检问题数为 0
- [ ] 不修改 `.xlsx` 源文件，通过代码生成

## 9. 参考文件

- XMind 源文件：`xmind文件夹/tc层测试设计.xmind`
- Excel 输出（最新）：`excel测试用例文件夹/2026-09-07_15-37-24/tc层测试用例.xlsx`
- 生成脚本：`临时文件夹/generate_tc_excel.py`
- 校验脚本：`临时文件夹/verify_tc_excel.py`
- 模板参考：`excel测试用例文件夹/DevX_PD_QP_CQ_SRQ_创建测试用例_含指令.xlsx`（示例 Excel，取列头顺序）
- 用例规范：`相关规范/用例规范.xlsx`
- 项目 skill 目录：`.kimi-code/skills/nic100/模块测试专项/以太网模块测试/SKILL.md`
