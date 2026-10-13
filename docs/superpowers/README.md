# Superpowers 工作流 — 项目使用说明

本项目已集成 [Superpowers](https://github.com/obra/superpowers) Agentic Skills Framework，用于规范 AI 辅助软件开发流程。

## 安装位置

Skill 按类型分组存放：

| 平台 | NIC100 项目 Skill | Superpowers 通用 Skill |
|------|-------------------|------------------------|
| Kimi Code CLI | `.kimi-code/skills/nic100/` + `.kimi-code/plugins/nic100-testing/` | `.kimi-code/skills/superpowers/` + `.kimi-code/plugins/superpowers/` |
| Claude Code | `.claude/skills/nic100/` | `.claude/skills/superpowers/` |

### NIC100 项目 Skill（8 个）

- `网卡测试框架` — NIC100 框架整体结构与规范
- `以太网模块测试` — 以太网相关测试要点
- `RoCE模块测试` — RoCE 模块测试要点
- `IB模块测试` — InfiniBand 模块测试要点
- `DPDK模块测试` — DPDK 模块测试要点
- `测试用例生成` — 根据 Excel/XMind/需求生成测试脚本
- `测试脚本编写` — 编写符合规范的 NIC100 测试脚本
- `缺陷自动记录` — 自动化 Bug 记录规范

### Superpowers 通用 Skill（14 个）

- `brainstorming` — 需求澄清与设计细化
- `writing-plans` — 生成可执行实施计划
- `subagent-driven-development` — 子代理驱动开发
- `executing-plans` — 计划执行（无 subagent 平台备用）
- `dispatching-parallel-agents` — 并行代理分发
- `test-driven-development` — 测试驱动开发
- `systematic-debugging` — 系统化调试
- `requesting-code-review` / `receiving-code-review` — 代码审查
- `using-git-worktrees` — Git worktree 隔离
- `finishing-a-development-branch` — 分支收尾
- `verification-before-completion` — 完成前验证
- `writing-skills` — 自定义 skill 开发
- `using-superpowers` — 框架总览

## 目录结构

```
docs/superpowers/
├── README.md          # 本文件
├── specs/             # 设计规格文档
├── plans/             # 实施计划文档
└── decisions/         # 技术决策记录（ADR）
```

## 使用流程

开发新功能或重构时，按以下流程进行：

1. **Brainstorming（头脑风暴）**
   - Agent 会先提问澄清需求
   - 提供 2-3 种方案及取舍
   - 分段展示设计，逐段获得确认
   - 输出：`docs/superpowers/specs/YYYY-MM-DD-<feature>-design.md`

2. **Writing Plans（编写计划）**
   - 基于已批准的设计，生成实施计划
   - 每个任务 2-5 分钟工作量
   - 包含精确文件路径、测试步骤、预期输出
   - 输出：`docs/superpowers/plans/YYYY-MM-DD-<feature>.md`

3. **Subagent-Driven Development（子代理驱动开发）**
   - 每个任务派一个独立 subagent
   - Subagent 遵循 TDD：先写失败测试 → 实现 → 重构
   - 每个任务后进行两阶段审查：
     - 规格合规审查（Spec Compliance Review）
     - 代码质量审查（Code Quality Review）

4. **Finishing Branch（收尾）**
   - 最终审查
   - 提交 PR 或合并

## 项目特定约定

- 测试脚本位于 `ps3/test/esat/nic100/scripts/`
- 框架代码位于 `ps3/test/esat/nic100/framework/`
- 新增测试脚本应遵循项目现有 `NIC100` 框架规范
- 修改 Excel 处理逻辑时，优先在 `framework/biz/excel/` 中补充单元测试

## 快速开始

对 Agent 说：

> "我想用 Superpowers 流程实现 [功能描述]，先进行 brainstorming。"

Agent 会自动触发 `brainstorming` skill。
