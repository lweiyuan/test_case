---
name: 测试脚本编写
description: 指导如何在NIC100框架中编写符合规范的测试脚本，包括脚本结构、继承关系、常用库使用、清理阶段和日志输出规范。
---

# NIC100 测试脚本编写规范

## 脚本位置

- 通用脚本：`ps3/test/esat/nic100/scripts/`
- 模块脚本：`ps3/test/esat/nic100/scripts/nic100/linux/<模块>/`
- 公共库：`ps3/test/esat/nic100/scripts/script_libs/`

## 脚本结构

每个测试脚本通常包含：

1. **文件头**：模块、用例编号、作者、日期、修改记录
2. **导入区**：脚本基类、公共库、模块专用库
3. **测试类**：继承自 `ScriptBase` 基类
4. **核心方法**：
   - `prepare()`：前置准备
   - `do()`：执行测试步骤
   - `post()`：清理与恢复
5. **入口**：`if __name__ == "__main__":`

## 继承与重写

- 测试脚本必须继承 `scripts/script_libs/script_base.py` 中的 `ScriptBase` 基类。
- `framework/libs/classes/test_case.py` 中的 `TestCase` 是**用例元数据类**（case_id、case_title 等），不是脚本执行基类，不要直接继承。
- 重写 `prepare`、`do`、`post` 时，建议保留 `super()` 调用。
- 脚本内部通过框架提供的结果机制记录测试结果。

## 常用公共库

| 库文件 | 用途 |
|--------|------|
| `command_operation.py` | 命令执行与结果解析 |
| `host_operation.py` | 主机操作 |
| `ssh_operation.py` | SSH 远程执行 |
| `ip_operation.py` | IP 配置 |
| `ethtool_operation.py` | ethtool 操作 |
| `fio_operation.py` | FIO 性能测试 |
| `iperf_operation.py` | iperf 性能测试 |
| `log.py` | 日志打印 |
| `script_base.py` | 脚本基类/公共方法 |

## 命名规范

- 测试脚本：`multi_pf_test_tc002.py`、`nic_linux_rdma_xxx.py`
- 类名：大驼峰，如 `MultiPfTestTc002`
- 方法名：小写下划线，如 `check_pf_status`
- 常量：全大写，如 `DEFAULT_TIMEOUT = 300`

## 清理阶段（post）

- **必须执行**：即使 `do` 阶段失败，`post` 也应尽量完成环境恢复。
- 恢复网络配置、还原驱动参数、删除临时文件。
- 避免影响后续用例执行。

## 日志与结果

- 使用框架提供的 `log` 工具，保持统一格式
- 关键步骤打印 INFO 级别日志
- 失败时打印 ERROR 级别日志，并说明失败原因
- 最终结果通过框架结果类上报

## 注意事项

1. 不要在脚本里硬编码密码、IP、用户名等敏感信息，使用环境配置
2. 避免在脚本中直接调用 `os.system`，优先使用 `command_operation`
3. 远程命令需考虑超时和重试
4. 多 PF 用例注意区分 pport 和 vport
5. 新增脚本后，在本地先跑通再提交
