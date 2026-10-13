---
name: 测试脚本编写
description: Use when writing NIC100 Python test scripts in the framework, and needing to align with script naming, code style, structure, logging, cleanup, and bug-recording conventions.
---

# NIC100 测试脚本编写规范

## Overview

本 skill 指导如何在 NIC100 框架中编写符合规范的 Python 测试脚本，包括脚本位置、命名、结构、继承、代码风格、注释、清理阶段、日志输出和关键行为要求。

## When to Use

- 在 NIC100 框架中新增或修改 Python 测试脚本时
- 需要确认脚本命名、类名、变量名是否符合项目规范时
- 需要检查脚本是否完整包含 prepare / do / post 三阶段时
- 评审脚本代码风格、注释、日志、异常处理是否合规时
- 不确定公共库用法或清理阶段应如何恢复环境时

## 1. 脚本位置

- 通用脚本：`ps3/test/esat/nic100/scripts/`
- 模块脚本：`ps3/test/esat/nic100/scripts/nic100/linux/<模块>/`
- 公共库：`ps3/test/esat/nic100/scripts/script_libs/`

完整目录示例：

```
测试脚本文件夹/YYYY-MM-DD_HH-MM-SS/
```

| 英文模块代码 | 中文目录名 | 说明 |
|-------------|-----------|------|
| `driver` | `以太` | 主机以太网驱动相关功能 |
| `dpdk` | `dpdk` | DPDK 用户态驱动 |
| `rdma` | `rdma` | RDMA 功能 |
| `ib` | `ib` | InfiniBand 功能 |
| `fw` | `fw` | 固件相关 |

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

## 3. 脚本结构

每个测试脚本通常包含：

1. **文件头**：模块、用例编号、作者、日期、修改记录
2. **导入区**：脚本基类、公共库、模块专用库
3. **测试类**：继承自 `ScriptBase` 基类
4. **核心方法**：
   - `prepare()`：前置准备
   - `do()`：执行测试步骤
   - `post()`：清理与恢复
5. **入口**：`if __name__ == "__main__":`

## 4. 继承与重写

- 测试脚本必须继承 `scripts/script_libs/script_base.py` 中的 `ScriptBase` 基类。
- `framework/libs/classes/test_case.py` 中的 `TestCase` 是**用例元数据类**（case_id、case_title 等），不是脚本执行基类，不要直接继承。
- 重写 `prepare`、`do`、`post` 时，建议保留 `super()` 调用。
- 脚本内部通过框架提供的结果机制记录测试结果。

## 5. Python 代码风格速查

| 项目 | 规范 | 示例 |
|------|------|------|
| 类名 | PascalCase | `class TianyingVlanE2EPingKernel(ScriptBase)` |
| 函数/方法 | 小写+下划线 | `def check_own_environment(cls)` |
| 变量 | 小写+下划线 | `server_if = server_ifs[0]` |
| 常量 | 全大写+下划线 | `VLAN_ID = 100` |
| 文件名 | 小写+下划线 | `tianying_vlan_e2e_ping_kernel.py` |
| 缩进 | 4 个空格，禁止 TAB | - |
| 行宽 | 代码 ≤79 字符；注释/docstring ≤72 字符 | - |
| 空行 | 类/函数间 2 行；方法间 1 行 | - |
| 导入顺序 | 标准库 → 第三方 → 本地；分组空行 | `import os` → `import add_syspath` → `from scripts.script_libs import log` |

## 6. 脚本头与注释

脚本头应包含：

```python
"""
case number: nic_linux_driver_vlan_filter_f_01_24_001_001
case title: 双机 VLAN 子接口端到端 ping 通（内核驱动）
test category: 天鹰 VLAN 测试
check point: TP-02; TP-04; TP-06; TP-07; TP-08
author: xxx
date: 2026.07.20

@steps:
    1. client VLAN 子接口 ping server VLAN IP
    2. server 物理口抓包验证 VLAN tag

@expected:
    1. ping 0% loss，双向互通
    2. 物理口报文带 VLAN 100 tag

@changelog:
    2026.07.20 - 初始版本
"""
```

方法注释（推荐）：

```python
def command_exec(cmd: str, node_ip: str, timeout: int = None) -> tuple:
    """
    执行 shell 命令。

    :param cmd: 命令字符串
    :param node_ip: 执行节点 IP
    :param timeout: 超时时间（秒）
    :return: (rc, stdout, stderr)
    """
```

## 7. 常用公共库

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

## 8. 清理阶段（post）

- **必须执行**：即使 `do` 阶段失败，`post` 也应尽量完成环境恢复。
- 恢复网络配置、还原驱动参数、删除临时文件。
- 避免影响后续用例执行。

## 9. 日志与结果

- 使用框架提供的 `log` 工具，保持统一格式
- 关键步骤打印 INFO 级别日志
- 失败时打印 ERROR 级别日志，并说明失败原因
- 最终结果通过框架结果类上报

## 10. 关键行为要求

- **继承 `ScriptBase`**，重写 `prepare()` / `do()` / `post()`
- **使用 `log` 打印日志**，禁止直接用 `print`
- **使用 `CommandOperation` 等公共库**执行命令，不要直接 `os.system`
- **失败时调用 `create_bug`** 记录缺陷，清晰说明检查点、预期值、实际值
- **跨方法使用的类变量应在类中先声明**，避免在 `prepare` 中赋值后在 `post` 中引用时未定义
- **不要直接拷贝公共库文件**到自己的目录；公共方法抽到 `script_libs`
- **消除 PyCharm 所有警告**后再提交

## 11. 常见错误

| 错误 | 正确做法 |
|------|---------|
| 用例编号写成 `port-vlan-func-001` | 使用 `nic_linux_driver_vlan_filter_f_01_24_001_001` |
| 脚本名含编号描述如 `func_001` | 描述用英文单词，如 `basic_port_vlan_config_kernel` |
| 用例类型写成中文 | 使用 `f/p/str/sta/c/r` |
| 脚本放在 `.../linux/vlan/` 根目录 | 放到 `测试脚本文件夹/YYYY-MM-DD_HH-MM-SS/` |
| 直接 `print` 输出 | 使用 `log.info` / `log.error` |
| 类变量在 `prepare` 中首次赋值 | 在类体中先声明类变量 |

## 12. 注意事项

1. 不要在脚本里硬编码密码、IP、用户名等敏感信息，使用环境配置
2. 避免在脚本中直接调用 `os.system`，优先使用 `command_operation`
3. 远程命令需考虑超时和重试
4. 多 PF 用例注意区分 pport 和 vport
5. 新增脚本后，在本地先跑通再提交
6. **注意框架对 `iperf`/`iperf3` 命令的特殊处理**  
   `CommandOperation` 会自动在命令中替换 `iperf` 为 `iperf -p <port>`。因此：
   - 检测 iperf 是否存在时，使用 `which iperf` 而不是 `iperf -v`（后者把版本输出到 stderr）
   - 不要让日志文件名包含 `iperf` 子串，否则文件名会被框架改写
7. **多 IB 设备环境注意指定目标设备**  
   执行 `perfquery`、`saquery` 等端口级命令时，若节点存在多个 IB 设备，应使用 `-C <ca> -P <port>` 指定目标设备
8. **启动 opensm 需指定目标设备 GUID，并检查进程存活**  
   多设备环境下启动 opensm 时，使用 `-g <node_guid>` 指定 GUID，避免绑定到错误端口。Node GUID 通过 `ibstat <device> | grep "Node GUID"` 获取。启动后应通过 `pgrep -x opensm` 检查进程是否持续运行，未检测到则记录失败
9. **opensm 修改 SL2VL 后需用 `smpquery` 验证配置生效**  
   仅检查 opensm 进程存活不够，应通过 `smpquery sl2vl -C <ca> <base_lid> 1` 查询 SL2VL 表，确认 SL 到 VL 的映射与预期一致
10. **修改 opensm 配置需先生成默认配置**  
    使用 `opensm -c <path>` 生成默认配置文件，再基于默认配置修改或追加 QoS 参数，避免手写缺省参数导致遗漏。配置 `qos_sl2vl` 时，`max_op_vls` 和 `qos_max_vls` 需同时设置，否则 SL2VL 表可能不会按预期生效
11. **解析 `smpquery sl2vl` 输出时只取 `ports:` 行后面的值**  
    回显中第一行是 SL 索引（0~15），不是 VL 值。真正的 VL 映射在 `ports: in 0, out 0:` 行后面，解析时应跳过前两个端口编号，取后面 16 个数字。例如：

    ```python
    for line in output.splitlines():
        if "ports:" in line and "out 0:" in line:
            numbers = [int(x) for x in re.findall(r"\b(\d+)\b", line)]
            # 跳过 in/out 端口编号 0, 0
            vl_table = numbers[2:18]
    ```
12. **`ib_send_bw` 多播禁止使用 `-x` 参数**  
    多播由 `-M` 指定 MGID，使用 `-x` 指定 GID 索引会导致参数冲突/失败
13. **`ib_send_bw` 用户态多播后不要求检测多播组数量新增/消失**  
    重点验证业务带宽、多播 LID/QPN、opensm.log trap 66/67 等；saquery 多播组查询仅在需要独立验证子网状态时使用
14. **perftest 性能测试建议显式指定 `-D 60`**  
    不指定 `-D` 时会走默认迭代次数（如 `ib_send_bw`/`ib_send_lat` 默认 `-n 1000`），测试时间过短会导致带宽/延时结果波动大。推荐命令中统一加 `-D 60 -F`，并把等待时间设为 65 秒左右（留启动/收尾余量）
15. **解析 `ib_send_lat` 输出要兼容 `-D` 模式的 4 列格式**  
    默认 `-n` 模式输出 5 列（`t_min t_max t_typical`），`-D` 模式输出 4 列（`t_avg tps`）。提取延时的正则不能写死 5 列，否则在 `-D` 模式下会误判为"无有效延时"。推荐正则：
    ```python
    r'^\s*(\d+)\s+(\d+)\s+(\d+\.\d+|\d+)\s+(\d+\.\d+|\d+)(?:\s+(\d+\.\d+|\d+))?'
    ```
    5 列时取最后一列 `t_typical`，4 列时取第 3 列 `t_avg`。
