---
name: 缺陷自动记录
description: 指导NIC100框架中如何规范地自动记录Bug，包括触发条件、Bug类型、字段设置、线程安全处理，以及IB/RDMA测试脚本的生成规范与Bug记录集成。
---

# NIC100 自动化 Bug 记录规范

## 触发条件

以下非脚本自身问题导致的失败，必须自动提交 Bug：

- 设备命令执行失败（如 `mlxconfig`、`ibstat` 返回非零）
- 网络配置不符合预期（PF 数量不对、设备状态非 Active）
- 性能测试不达标
- 组网失败（opensm 无法启动、设备无法进入 Active）
- 硬件相关问题（设备不可见、GUID 获取失败）

**不应提 Bug 的情况**：脚本自身语法错误、逻辑错误等代码问题，应直接修复脚本。

## 三步流程

```python
# 步骤1: 设置 bug 类型
cls.set_bug_type("Function")  # 必须是 BugTypeEnum 中定义的类型

# 步骤2: 设置 bug 字段
cls.bug_result = "实际观察到的结果"
cls.bug_expect = "期望的结果"

# 步骤3: 调用 create_bug 抛出异常
cls.create_bug("详细的问题描述")
```

## Bug 类型枚举

| 类型 | 说明 |
|------|------|
| `IO_ERROR` | IO 错误 |
| `CC_ERROR` | 一致性错误（触发后跳过 post 清理阶段） |
| `PERFORMANCE` | 性能问题 |
| `CORE` | Core dump |
| `CRASH` | 程序崩溃 |
| `FUNCTION` | 功能问题（最常用） |
| `STABILITY` | 稳定性问题 |
| `RELIABILITY` | 可靠性问题 |
| `MEMORY_LEAK` | 内存泄漏 |

## 关键规则

1. **必须先设置 bug 类型**：调用 `create_bug` 前必须先调用 `set_bug_type`
2. **使用正确的异常类型**：`create_bug` 会抛出 `SxeException`
3. **线程安全**：多线程场景使用 `get_bug_data_with_create_bug`
4. **标题截取**：`bug_title` 会自动截取 `abnormal_msg` 前 200 个字符
5. **信息完整**：确保包含 `bug_title`、`bug_result`、`bug_expect`、`bug_type`

## 示例

```python
from script_libs.exceptions import SxeException

# 检查命令结果
if cmd_result.exit_code != 0:
    cls.set_bug_type("FUNCTION")
    cls.bug_result = f"命令执行失败：{cmd_result.stderr}"
    cls.bug_expect = "命令应成功执行并返回 0"
    cls.create_bug(f"{cmd} 执行失败，影响 {cls.__name__}")
```

## 在 IB/RDMA 测试脚本中的应用

### 测试脚本生成规范

- 每个用例应是一个独立的 `.py` 文件。
- 不要重复生成基类，只继承使用项目现有 NIC100 测试基类。
- 脚本名与用例编号对应，如 `multi_pf_test_tc002.py`。
- 遵循项目既有代码风格，包含 `prepare` / `do` / `post` 三阶段。
- 按本节要求补充 Bug 记录代码。

### 脚本结构示例

```python
class TestCase_IB_001(ScriptBase):
    @classmethod
    def prepare(cls):
        # 环境准备：检查设备、启动 OpenSM、配置 PF 等
        super().prepare()

    @classmethod
    def do(cls):
        # 执行测试：打流、状态检查、配置变更等
        pass

    @classmethod
    def post(cls):
        # 环境恢复：停止 OpenSM、恢复 PF、重启等
        super().post()
```

### 脚本位置

- IB/RDMA 相关脚本：`ps3/test/esat/nic100/scripts/nic100/linux/rdma/`
- 公共库：`ps3/test/esat/nic100/scripts/script_libs/rdma_core_tool.py`

### 测试结果报告要求

所有用例执行结束必须明确提示结果：

- 成功：输出 "测试执行成功" 或类似明确的成功状态信息。
- 失败：输出 "测试执行失败" 并附带简要描述失败原因。
- 提供完整的测试执行结果摘要，包括通过的步骤和失败的步骤。
- 面向测试人员的打印信息应尽量使用中文，避免中英文混用。

### IB/RDMA 场景下必须提 Bug 的情况

- 设备命令执行失败（如 `mlxconfig`、`ibstat` 返回非零）。
- 网络配置不符合预期（PF 数量不对、设备状态非 Active）。
- 性能测试不达标（带宽/延迟未达预期）。
- 组网失败（opensm 无法启动、设备无法进入 Active）。
- 硬件相关问题（设备不可见、GUID 获取失败）。

### IB/RDMA 场景下不应提 Bug 的情况

脚本自身语法错误、逻辑错误、导入错误、配置错误等代码问题，应直接修复脚本。

## 使用场景

- 在测试脚本中集成自动化 Bug 提交
- 统一团队 Bug 记录风格
- 避免漏提或误提 Bug
- 生成 IB/RDMA 测试脚本并补充 Bug 记录逻辑
- 判断测试失败是否应自动记录 Bug
