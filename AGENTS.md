# ps3code 项目 — Agent 工作指南

## 项目概述

本项目是 NIC100 网卡自动化测试框架，主要使用 Python 编写。

- 测试脚本：`ps3/test/esat/nic100/scripts/`
- 框架代码：`ps3/test/esat/nic100/framework/`
- 业务工具：`ps3/test/esat/nic100/framework/biz/`

## Superpowers 工作流

本项目已集成 [Superpowers](https://github.com/obra/superpowers) AI 开发工作流框架。Agent 在参与开发时应遵循以下原则：

## Skill 目录组织

项目 skill 已按类型分组，避免根目录混乱：

```
.kimi-code/skills/
├── nic100/          # NIC100 网卡测试项目 skill
│   ├── 框架与通用能力/    # 框架级与跨模块通用 skill
│   │   ├── 网卡测试框架
│   │   ├── 测试脚本编写
│   │   ├── 测试用例生成      # 已融合用例规范、脚本命名与 XMind 转 Excel 规则
│   │   └── 缺陷自动记录
│   └── 模块测试专项/      # 各业务模块测试 skill
│       ├── 以太网模块测试
│       ├── RoCE模块测试
│       ├── IB模块测试
│       ├── DPDK模块测试
│       └── 固件测试
└── superpowers/     # Superpowers 通用开发 workflow skill
    ├── brainstorming
    ├── writing-plans
    ├── subagent-driven-development
    ├── test-driven-development
    ├── systematic-debugging
    └── ...
```

对应的 Claude Code 路径为 `.claude/skills/nic100/` 和 `.claude/skills/superpowers/`。
调用 skill 时优先通过平台的 skill 加载机制，不要手动读取 SKILL.md。

1. **先设计，后编码**：使用 `brainstorming` skill 澄清需求并生成规格文档
2. **计划先行**：使用 `writing-plans` skill 生成详细实施计划
3. **TDD**：使用 `test-driven-development` skill，先写失败测试再实现
4. **Subagent 驱动**：复杂任务使用 `subagent-driven-development` skill，每个任务独立 subagent + 两阶段审查
5. **系统调试**：使用 `systematic-debugging` skill，先根因分析再修复
6. **验证闭环**：完成前使用 `verification-before-completion` skill 验证结果

## 项目特定规范

- 新增测试脚本应继承项目现有 NIC100 测试基类
- 公共工具函数应补充到 `framework/libs/` 并附带测试
- Excel/报告相关逻辑变更应同步更新 `framework/biz/excel/`
- 不要直接修改 `.xlsx` 源文件，应通过代码生成或处理

## 文档位置

- Superpowers 使用说明：`docs/superpowers/README.md`
- 设计规格：`docs/superpowers/specs/`
- 实施计划：`docs/superpowers/plans/`
- 技术决策：`docs/superpowers/decisions/`
