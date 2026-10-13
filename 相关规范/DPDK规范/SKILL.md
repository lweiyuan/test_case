# NIC100 DPDK OVS flex_pattern 测试用例生成规范

> 本规范整理自 2026-07-29 针对 `xmind文件夹/OVS.xmind` 中 `flex_pattern` 异常测试点的用例/脚本生成实践，以及 2026-08-10 `dpdk-vdpa` 用例（建立 VM 并登录/文件传输）的脚本生成实践，用于指导后续同类型 DPDK OVS / dpdk-vdpa 测试用例的生成。
> 放置位置：`相关规范/DPDK规范/SKILL.md`，不进入 `.kimi-code/skills/` 自动加载目录，避免影响其他使用者。

## 1. 适用范围

- 从 `xmind文件夹/OVS.xmind` 或同类 XMind 文件生成 DPDK OVS 相关测试用例
- 生成项目标准 18 列 Excel 测试用例
- 生成 NIC100 框架下的 Python 测试脚本
- 当前主要针对 `flex_pattern` 异常/边界测试场景
- 新增：`dpdk-vdpa` 建立 VM 类测试（vdpa 启动、qemu 启动、VM 登录/文件传输等），详见第 8 章

## 2. 用例编号规则

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

## 3. Excel 用例规范

### 3.1 输出位置

```
excel测试用例文件夹/YYYY-MM-DD_HH-MM-SS/OVS_flex_pattern_异常测试.xlsx
```

### 3.2 18 列标准

沿用项目既有 18 列模板：

```
所属产品、所属模块、优先级、用例类型、脚本名称、测试编号、用例标题、
前提条件、测试步骤、预期结果、检查项/测试点、测试场景、用例测试分类、
负责人、作者、测试平台实现自动化、需求点/测试对象、物理环境
```

### 3.3 公共字段

> **全局约定（适用于所有模块用例 Excel 生成）**：`所属产品` 固定填写 **NIC800**。不论 DPDK、RDMA 还是其他模块，生成的 18 列用例 Excel 中"所属产品"列一律为 `NIC800`，不要写成 NIC100 或其他值。

| 字段 | 值 |
|---|---|
| 所属产品 | NIC800 |
| 所属模块 | DPDK-OVS |
| 优先级 | A1 |
| 用例类型 | f |
| 用例测试分类 | 系统测试-功能 |
| 测试平台实现自动化 | Linux |
| 需求点/测试对象 | OVS flex_pattern 异常处理 |
| 物理环境 | 双机 / 单 NIC800 网卡 |
| 负责人 | liuchang6 |
| 作者 | liuchang6 |

### 3.4 脚本名称列

格式：

```
ps3/test/esat/nic100/scripts/nic100/linux/dpdk/ovs/case_ovs/<用例编号>_<英文描述>.py
```

示例：

```
ps3/test/esat/nic100/scripts/nic100/linux/dpdk/ovs/case_ovs/nic_linux_dpdk_ovs_f_02_74_001_019_field_base_over_mtu.py
```

## 4. 已确认的 flex_pattern 异常测试点

### 4.1 已分配编号（12 条）

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

### 4.2 XMind 中标注“不再测试”的点

以下节点在 XMind 中已明确标注“不再测试”，不生成用例：

- field_base 超过 flex 协议头长度
- field_size 超过 flex 协议头长度
- 协议头长度超过 MTU

## 5. Python 测试脚本规范

### 5.1 目录与命名

- 目录：`ps3/test/esat/nic100/scripts/nic100/linux/dpdk/ovs/case_ovs/`
- 命名：`<用例编号>_<英文描述>.py`，全小写，下划线分隔
- 同级目录需放置 `add_syspath.py`（复制其他模块版本即可）

### 5.2 类与结构

- 继承 `scripts.script_libs.script_base.ScriptBase`
- 重写 `set_parameters`、`check_own_environment`、`prepare`、`do`、`post`
- 类名使用 PascalCase
- 文件头包含 case number、case title、author（liuchang6）、steps、expected

### 5.3 testpmd 交互方式

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

### 5.4 校验逻辑

- 错误模式：`port_flow_complain`、`Failed`、`failed`、`not supported`、`not valid`、`Invalid argument`、`error`
- 成功标记：根据命令传入，如 `created`、`Flow rule #0 created`
- `show port stats 0` 输出从 hardcopy 中解析 `RX-packets:`

### 5.5 环境准备与清理

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

#### switchdev / VF 场景补充

在 switchdev 模式变体（编号 `101_0xx`）中，testpmd 基于 VF 运行，VF **保持内核驱动，不需要绑定到 `vfio-pci`**。创建 VF 后只需记录其 BDF，testpmd 直接使用 `-a $VF_BDF` 启动。

对应流程：

- **prepare**：创建 VF → 获取 VF BDF → 切换 PF e-switch 到 switchdev 模式 → 创建 flex JSON → 启动 testpmd（VF）
- **testpmd 启动后**：先执行 `flow isolate 0 on` 开启流隔离
- **post**：停止 testpmd → 移除 VF（`echo 0 > /sys/class/net/$PF/device/sriov_numvfs`）→ 恢复 e-switch 为 legacy → 删除临时文件

> PF 在此过程中始终保持内核驱动，不需要记录/恢复 PF 原驱动。

### 5.6 发包方式

- 从 client 端（对端机器）使用 scapy 发送匹配报文
- 目的 MAC 使用 server PF 的 MAC
- 若环境为单机，需改用 loopback 或第二端口方案

## 6. 命令准确性要求

生成脚本时，testpmd 命令必须与实际 DPDK 版本一致。若 XMind 中命令存在拼写错误、参数缺失或与官方帮助文档冲突，应：

1. 优先核对项目内现有 skill/脚本
2. 上机执行 `--help` / `man` / 试运行确认
3. 保留原意，最小改动纠正
4. 在脚本注释中注明修正原因

## 7. 质量检查清单

生成后用例/脚本需确认：

- [ ] 18 列 Excel 无空值
- [ ] 用例编号连续、模式变体编号规范
- [ ] 脚本名与 Excel 脚本名称列一致
- [ ] 脚本继承 `ScriptBase`，含 prepare/do/post
- [ ] testpmd 使用 screen + hardcopy 校验
- [ ] 错误时调用 `create_bug` 记录缺陷
- [ ] 临时文件在 post 阶段清理
- [ ] 不修改 `.xlsx` 源文件，通过代码生成

## 8. dpdk-vdpa 建立 VM 测试脚本范式

> 整理自 2026-08-10 `dpdk-vdpa-NIC功能测试用例.xlsx` 用例 001（vm 登录）/ 002（文件传输）的脚本实现。
> 典型用例：vdpa 启动 → 创建 socket → qemu 启动 VM → 防火墙 → VM 配 IP → 登录/传输 → 关闭 VM。

### 8.1 标准步骤与脚本步骤映射

| # | 用例步骤 | 脚本实现 | 预期校验 |
|---|---|---|---|
| 1 | 创建 2 个 VF | `echo 2 > /sys/bus/pci/devices/<pf_bdf>/sriov_numvfs` | 读回 `sriov_numvfs==2` |
| 2 | 启动 vdpa：`dpdk-vdpa -l 0-1 --socket-mem 1024 -a <bdf>,class=vdpa -- -i` | 命名管道作 stdin 后台常驻启动（交互 `-i` 需保持会话） | `pgrep dpdk-vdpa` 进程存在 |
| 3 | 创建 socket：`create /tmp/vdpa-socketvf0 <bdf>` | 向管道写 `create` 命令 | `ls /tmp/vdpa-socketvf0` 存在 |
| 4 | 启动 qemu 虚拟机 | `nohup qemu-system-x86_64 ... -chardev socket,path=<socket> ...`（hostfwd `22001→22`） | `pgrep qemu` 进程存在 |
| 5 | 关防火墙：`setenforce 0; systemctl stop firewalld; iptables -F` | 同命令 server 端执行 | 返回码 0 |
| 6 | 登录 VNC 配 DHCP | ssh 连 VM(22001) 执行 `dhclient; ip a`（自动化替代 VNC 手动操作） | 输出含 `inet` |
| 7 | ssh 登录 VM 执行命令 / scp 传输文件 | `execute_command_based_paramiko_with_rtncode(ssh_ip="127.0.0.1", ssh_port="22001", ssh_username="root", ...)` | 返回码 0 且命令结果符合预期 |
| 8 | 关闭 VM，还原环境 | `pkill qemu` | 进程退出 |

### 8.2 关键实现规则（务必遵守）

- **不要写死环境相关路径/地址**，全部动态获取：
  - `pf_bdf`：用 `EthtoolOperation.show_driver_infomation(pf_if, CmdExecuteAdressEnum.SERVER.value).get("bus-info")` 从配置首 pf 取（不要写死 `0000:a8:00.2`）。
  - `vdpa_bin`：用 `find / -name dpdk-vdpa -type f 2>/dev/null | head -1` 在 server 端查找（不要写死 `/home/zhubo/dpdk/...`）。
  - 取不到时 `cls.own_environment_enabled = False` 提前退出。
- **vdpa 交互模式**：`dpdk-vdpa -- -i` 是交互式，需用**命名管道**作 stdin 后台常驻（`mkfifo /tmp/vdpa_in; dpdk-vdpa ... -- -i < /tmp/vdpa_in &`），再 `echo 'create <socket> <bdf>' > /tmp/vdpa_in` 发送命令；否则进程会在 EOF 后退出。
- **qemu VM 登录**：qemu 用 `-netdev user,hostfwd=tcp::22001-:22` 把 VM 的 22 端口映射出来；VM 内命令一律通过 `execute_command_based_paramiko_with_rtncode(ssh_ip="127.0.0.1", ssh_port="22001", ssh_username="root")` 执行。
- **步骤 6 用 ssh 代替 VNC 登录配 IP** 是自动化常规做法；若必须严格走 VNC，需额外 VNC 客户端自动化。
- **每个步骤独立校验预期**，失败统一 `cls.create_bug(...)`；bug_title/bug_result/bug_expect 对应用例标题与期望。
- **post 阶段还原**：`pkill dpdk-vdpa; pkill qemu-system; rm -f <socket> <pipe>; echo 0 > sriov_numvfs`，并清理临时文件（如 scp 源文件）。

### 8.3 框架 API 正确签名（易错点）

- 命令执行：`CommandOperation.execute_command(cmd, CmdExecuteAdressEnum.SERVER)` 返回二元组 `(code, output)`；
  `CommandOperation.execute_command_with_error(cmd, cmd_execute_address=...)` 返回三元组 `(code, out, err)`，`code==RtnStatusEnum.SUCCESS.value(0)` 表示成功。
- VM 内执行：`CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, cmd_execute_address=SERVER, ssh_ip="127.0.0.1", ssh_port="22001", ssh_username="root", timeout=120)`。
- pf 接口名：`server_ifs, _ = CommonOperation.get_nic_relationships(rdma=False)` 返回**接口名字符串列表**（非连接对象）。

### 8.4 脚本示例

- VM 登录：`ps3/test/esat/nic100/scripts/nic100/linux/dpdk/vdpa/nic_linux_dpdk_vdpa_f_03_70_001_001_leagcy_split_ssh.py`
- 文件传输(scp)：`ps3/test/esat/nic100/scripts/nic100/linux/dpdk/vdpa/nic_linux_dpdk_vdpa_f_03_70_001_002_leagcy_split_scp.py`
- Excel 源：`excel测试用例文件夹/2026-08-07_16-52-29/dpdk-vdpa-NIC功能测试用例_规范.xlsx`（legacy 001/002）

## 9. 参考文件

- XMind 源文件：`xmind文件夹/OVS.xmind`
- Excel 输出：`excel测试用例文件夹/2026-07-29_09-51-16/OVS_flex_pattern_异常测试.xlsx`
- 脚本示例：`ps3/test/esat/nic100/scripts/nic100/linux/dpdk/ovs/case_ovs/nic_linux_dpdk_ovs_f_02_74_001_019_field_base_over_mtu.py`
- dpdk-vdpa 脚本示例（见 §8.4）
- 项目 skill 目录：`.kimi-code/skills/nic100/模块测试专项/DPDK模块测试/SKILL.md`
