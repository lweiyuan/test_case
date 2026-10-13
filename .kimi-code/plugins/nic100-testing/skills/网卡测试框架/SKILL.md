---
name: 网卡测试框架
description: 指导NIC100自动化测试框架的整体结构、目录约定、执行入口、环境配置和通用规范。用于理解框架、定位文件、运行测试、排查框架级问题。
---

# NIC100 自动化测试框架指南

## 项目定位

- 项目根目录：`ps3/test/esat/nic100/`
- 测试对象：网卡（NIC），覆盖 IB、RoCE、以太网、DPDK 四大模块
- 协作规模：20+ 人通过 Git 协同开发

## 目录结构

```
ps3/test/esat/nic100/
├── framework/              # 框架核心
│   ├── biz/                # 业务层：用例脚本生成、Excel 报告、日志分析
│   ├── interfaces/         # 外部接口（Jenkins 调用等）
│   ├── libs/               # 框架公共库：用例基类、环境类、命令封装、工具函数
│   ├── model/              # 框架模型与适配层
│   └── env_conf/           # 环境配置文件
├── scripts/                # 测试脚本目录
│   ├── script_libs/        # 脚本公共库
│   ├── nic100/             # nic100 相关脚本（linux/driver/fw/rdma 等）
│   └── nic800/             # nic800 相关脚本
├── outputs/                # 测试输出与日志
└── run_test.sh             # 本地执行入口
```

## 核心入口

- **本地执行**：`ps3/test/esat/nic100/run_test.sh`
- **全量执行**：`ps3/test/esat/nic100/framework/run_all_test.py`
- **PS3 执行**：`ps3/test/esat/nic100/framework/run_all_test_ps3.py`
- **Jenkins 调用**：`ps3/test/esat/nic100/framework/interfaces/jenkins_call_framework.py`

## 关键基类与类

- 用例信息/元数据类：`framework/libs/classes/test_case.py`
- 脚本执行基类：`scripts/script_libs/script_base.py` 中的 `ScriptBase`
- 测试结果类：`framework/libs/classes/result.py`
- 测试环境类：`framework/libs/classes/test_environment.py`
- Bug 记录类：`framework/libs/classes/bug.py`
- 报告汇总类：`framework/libs/classes/report_summary.py`

## 环境配置

- 环境配置文件位于 `framework/env_conf/` 和 `scripts/env_config*.ini`
- 修改环境配置前，先备份原有配置
- 不同平台使用不同 env 文件，如 `env_config_cd.xml`、`env_platform_config_bak.json`

## 通用规范

1. **新增脚本**放到 `scripts/` 下对应模块目录，命名遵循团队约定
2. **公共函数**优先放到 `script_libs/`，避免各脚本重复实现
3. **修改框架基类**需谨慎，影响所有用例
4. **输出日志**统一放到 `outputs/scripts/`，按用例名+时间命名
5. **Python 版本**：项目同时存在 Python 3.8/3.12/3.13 的 pyc，编写脚本时注意兼容性

## 项目结构与依赖分析

在新增模块、重构框架或深入理解项目架构时，可借助依赖分析工具扫描代码：

1. 运行依赖分析脚本：
```bash
python scripts/analyze_dependencies.py /path/to/python/project
```

2. 脚本输出：
   - `dependencies.json`：模块间依赖关系图
   - `modules.txt`：模块列表
   - `structure_report.md`：代码结构报告

3. 分析要点：
   - 识别关键模块及相互引用关系
   - 定位循环依赖
   - 评估新功能对现有模块的影响范围
   - 为生成符合框架规范的新脚本提供参考

## 使用场景

- 理解 NIC100 框架目录与模块划分
- 定位框架级公共类和工具函数
- 排查测试执行入口、环境配置问题
- 新增模块或重构框架前查阅
- 分析项目依赖关系与代码结构
