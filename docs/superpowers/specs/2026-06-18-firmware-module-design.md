# NIC100 固件测试模块 Skill — 设计规格

## 1. 背景与目标

### 1.1 背景

NIC100 自动化测试框架当前已具备以太网、RoCE、IB、DPDK 四大业务模块的测试 skill，但缺少针对**固件升级、回滚、版本校验、异常恢复**的专项指导。项目代码中已存在大量固件相关实践：

- 主机侧：`sxe2cli upgrade`、`ethtool -f`、主备分区切换、`mlxconfig` 等。
- BMC/PLDM 侧：`PldmTool.firmware_upgrade`、BMC EID/UUID 匹配、PLDM 状态机轮询等。

这些知识分散在 `scripts/script_libs/ethtool_operation.py`、`common_operation.py`、`scripts/nic100/linux/fw/bmc/common_bmc.py` 等文件中，未能以 skill 形式沉淀，导致：

1. 新成员编写固件测试脚本时难以快速定位规范。
2. Agent 生成固件相关脚本时缺乏统一参考，容易遗漏升级前后校验、环境恢复等关键环节。

### 1.2 目标

在 `.kimi-code/skills/nic100/` 下新增**固件测试模块** skill，覆盖主机侧 NIC 固件与 BMC/PLDM 固件的升级、回滚、校验、恢复等核心测试场景，使其：

- 对人类测试工程师：提供清晰的命令参考、检查项、失败处理原则。
- 对 AI 代码生成：提供可复用的脚本结构、边界条件、Bug 记录模式。
- 与现有 skill（网卡测试框架、IB、以太网、缺陷自动记录）保持边界清晰、互相引用。

## 2. 需求澄清

通过与需求方确认，明确以下要点：

| 维度 | 结论 |
|------|------|
| 覆盖范围 | 主机侧 NIC 固件 + BMC/PLDM 固件两者都覆盖 |
| 目标读者 | 人类测试工程师 + AI 代码生成两者兼顾 |
| 核心章节 | 版本查询与校验、升级流程、回滚与分区切换、异常恢复与日志判断 |
| 组织形式 | 1 个总览 skill + 4 个子 skill（按动作+通道二维拆分） |

## 3. 设计决策

### 3.1 架构：1 个总览 skill + 4 个子 skill

选择该方案的原因：

- 既满足用户"按动作+通道二维拆分"的偏好，又通过总览 skill 沉淀通用规范，避免子 skill 之间大量重复。
- 总览 skill 作为入口，子 skill 作为特化参考，调用方可以按需加载。

目录结构：

```text
.kimi-code/skills/nic100/固件测试/
├── SKILL.md                      # 总览 skill
├── 主机侧固件升级/SKILL.md        # 主机侧 NIC 固件升级
├── 主机侧固件回滚/SKILL.md        # 主机侧 NIC 固件回滚
├── BMC_PLDM固件升级/SKILL.md      # BMC/PLDM 固件升级
└── BMC_PLDM固件回滚/SKILL.md      # BMC/PLDM 固件回滚
```

### 3.2 总览 skill 职责边界

总览 skill 只放**一次定义、全局通用**的内容：

1. 测试范围与关键概念（主分区/备分区、ping-pong 升级、EID/UUID、FW State）。
2. 核心命令速查表（sxe2cli / ethtool / ibstat / mlxconfig / BMC 工具）。
3. 通用检查项（升级前、升级中、升级后必做检查）。
4. 环境恢复与清理原则（post 阶段必须恢复版本/分区/链路）。
5. 失败处理与 Bug 记录规范（何时提 Bug、bug_type、result/expect）。
6. 子 skill 导航表。
7. 与现有 skill 关系说明。

### 3.3 子 skill 职责边界

每个子 skill 只写**本通道+本动作特化**的步骤和示例：

| 子 skill | 核心内容 |
|----------|----------|
| 主机侧固件升级 | `sxe2cli upgrade`、`ethtool -f`、镜像校验、状态轮询、升级后版本校验 |
| 主机侧固件回滚 | 主备分区查询与切换、版本回退、`uptime`/`reset reason` 校验、双分区覆盖等待 |
| BMC/PLDM 固件升级 | BMC IP/EID/UUID 准备、镜像传输、PLDM upgrade 命令、`0x31` 升级状态轮询 |
| BMC/PLDM 固件回滚 | BMC 侧回滚触发条件、回滚命令、BMC 重连、EID 重新获取、日志判断 |

### 3.4 与现有代码和 skill 的关系

| 关联方 | 关系说明 |
|--------|----------|
| 网卡测试框架 skill | 固件测试 skill 继承其目录约定、基类使用、环境配置原则。 |
| 缺陷自动记录 skill | 固件失败时的 Bug 记录引用该 skill，不重复定义字段。 |
| IB/以太网模块测试 skill | 固件升级后如需验证业务，引用这些 skill 的流量/链路检查方法。 |
| `scripts/nic100/linux/fw/bmc/` | BMC/PLDM 子 skill 以这些代码为实践基础，抽取通用模式而非照搬实现。 |
| `scripts/script_libs/ethtool_operation.py` | 主机侧升级命令参考该文件实现。 |
| `scripts/script_libs/common_operation.py` | 版本查询、镜像路径获取、环境恢复等逻辑参考该文件。 |

### 3.5 脚本位置建议

- 主机侧固件测试脚本建议放到：`ps3/test/esat/nic100/scripts/nic100/linux/fw/host/`
- BMC 侧固件测试脚本继续复用或扩展：`ps3/test/esat/nic100/scripts/nic100/linux/fw/bmc/`

本次 skill 创建不强制新建脚本目录，仅在总览 skill 中给出建议位置。

## 4. 内容来源

- 总览 skill：基于现有技能风格（如 IB 模块测试、以太网模块测试）重新组织。
- 子 skill：基于以下代码中的实际命令和模式抽象：
  - `ps3/test/esat/nic100/scripts/script_libs/ethtool_operation.py`
  - `ps3/test/esat/nic100/scripts/script_libs/common_operation.py`
  - `ps3/test/esat/nic100/scripts/nic100/linux/fw/bmc/common_bmc.py`
  - `ps3/test/esat/nic100/scripts/nic100/linux/fw/bmc/script_base_bmc.py`

## 5. 验证策略

1. **语法检查**：skill 中示例代码需通过 `python -m py_compile`。
2. **元数据检查**：skill 文件顶部 frontmatter（name/description）需符合现有 skill 格式。
3. **一致性走读**：确保命令、路径、关键字与项目代码一致。
4. **加载验证**：通过 kimi 平台 skill 加载机制验证新 skill 可被识别。

## 6. 文件清单

| 文件 | 说明 |
|------|------|
| `docs/superpowers/specs/2026-06-18-firmware-module-design.md` | 本设计规格 |
| `docs/superpowers/plans/2026-06-18-firmware-module-plan.md` | 实施计划（由 writing-plans 生成） |
| `.kimi-code/skills/nic100/固件测试/SKILL.md` | 总览 skill |
| `.kimi-code/skills/nic100/固件测试/主机侧固件升级/SKILL.md` | 主机侧固件升级子 skill |
| `.kimi-code/skills/nic100/固件测试/主机侧固件回滚/SKILL.md` | 主机侧固件回滚子 skill |
| `.kimi-code/skills/nic100/固件测试/BMC_PLDM固件升级/SKILL.md` | BMC/PLDM 固件升级子 skill |
| `.kimi-code/skills/nic100/固件测试/BMC_PLDM固件回滚/SKILL.md` | BMC/PLDM 固件回滚子 skill |

## 7. 风险与假设

- **硬件依赖**：固件升级/回滚涉及真实硬件和真实镜像路径，单元测试无法覆盖，需依赖人工 checklist。
- **权限依赖**：`ethtool -f`、PCIe 操作、BMC 命令通常需要 root 权限。
- **镜像路径依赖**：主机侧升级镜像路径依赖 `constants.py` 中的发布目录，skill 中只给出占位符或配置方式。
- **BMC 环境差异**：不同平台（G40/G50、Intel/Teston）BMC 工具和登录方式不同，子 skill 需说明平台适配要点。
