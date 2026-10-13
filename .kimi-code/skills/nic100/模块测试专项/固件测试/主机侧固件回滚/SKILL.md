---
name: 主机侧固件回滚
description: 指导NIC100框架下通过主备分区切换对主机侧NIC固件进行回滚，包括分区查询、切换、重启和回滚后校验。
---

# 主机侧固件回滚

## 测试范围

- 通过 `scgbecli` 对 SXE2/SCGBE 网卡进行主机侧固件回滚
- 查询当前主备分区状态并切换启动分区
- 切换后重启服务器，使固件从原分区（旧版本）启动
- 回滚后校验 uptime、reset reason、版本、设备可见性与链路状态
- 回滚失败时自动记录 Bug

## 关键概念

### 主分区 / 备分区（ping-pong 回滚）

NIC100 主机侧固件采用双分区 ping-pong 机制。升级时新固件写入备分区并切换启动分区；回滚时再次切回主分区，使设备从旧版本启动。

### `versionlineswitch=0` 与 `versionlineswitch=1`

- `versionlineswitch=0`：仅查询当前分区同步状态，不切换分区。
- `versionlineswitch=1`：执行切分区操作，使下次启动使用另一分区。

对应项目框架中的调用方式：

```python
# 查询分区状态
CliOperation.get_upgrade_syncstate_info(
    bus_info=bdf,
    caller_class=cls,
    switch_info="0",
    exec_addr=exec_addr,
)

# 切换启动分区
CliOperation.change_flash_flag(
    bus_info=bdf,
    caller_class=cls,
    exec_addr=exec_addr,
)
```

### `run state` 含义

执行 `custom sxe2 upgrdsyncstate` 后，输出中的 `run state` 字段：

- `run state: 0`：当前分区固件已覆盖完成，分区空闲
- `run state: 1`：当前分区固件正在覆盖中，需要循环等待

### `switch_state` 含义

切分区命令执行后，通过 `versionlineswitch=0` 再次查询，`switch_state` 应变为 `1`，表示下次启动将使用另一分区。

## 适用命令

> 实际二进制名称可能因网卡代际而异，例如 `scgbecli`、`sxe2cli` 等。项目框架中通过 `constants.SCGBECLI64` 构造命令，当前解析为 `scgbecli`。

### 查询分区同步状态

```bash
scgbecli -d <bdf> custom sxe2 upgrdsyncstate versionlineswitch=0
```

### 切换启动分区

```bash
scgbecli -d <bdf> custom sxe2 upgrdsyncstate versionlineswitch=1
```

### 查询回滚后固件信息

```bash
scgbecli -d <bdf> custom sxe2 fwinfo
```

典型输出包含：

```text
port 0000:03:00.0
version    = 0.6.0.5
...
uptime: 0 days,0 hours,2 minutes,10 seconds
sys run Region: MASTER
NIC RST CAUSE: PWR_RST
```

## 回滚前

1. **记录原始版本**
   在 `prepare()` 阶段通过 `scgbecli -d <bdf> show fw` 或 `ethtool -i <iface>` 记录当前 FW 版本、BDF 与启动分区，便于 `post()` 阶段再次回滚或环境恢复。
2. **确认目标回滚版本**
   确认另一分区中存放的版本为预期回退版本。必要时通过升级流程先将旧版本写入备分区，再执行回滚。
3. **确认分区空闲**
   查询 `run state` 为 `0`，避免在分区覆盖过程中执行切换。

## 回滚中

1. **查询当前分区状态**
   调用 `CliOperation.get_upgrade_syncstate_info(switch_info="0")` 获取 `run_state`、`switch_state`、`fw_flash_flag`、`boot_flash_flag`、`open_state`。
2. **等待分区空闲**
   若 `run_state` 为 `1`，循环查询直到 `run_state` 为 `0` 或 300s 超时。
3. **执行切分区**
   调用 `CliOperation.change_flash_flag(...)` 或执行 `versionlineswitch=1`。
4. **验证切换生效**
   再次查询 `switch_state` 是否为 `1`；若不为 `1`，报 Bug。
5. **等待分区覆盖完成**
   切分区后若 `run_state` 为 `1`，循环等待直到 `run_state` 为 `0` 或超时。
6. **重启服务器**
   `CommonTools.reboot_host` 需要传入真实的服务器 SSH IP。通过 `CommandLineArgsParse.get_server_ip()` 获取服务器 IP 后，调用 `CommonTools.reboot_host(ssh_ip=server_ip, timeout=900)`，或按项目 reboot 流程等待服务器上线并重新加载驱动。

## 回滚后校验

1. **uptime 校验**
   通过 `scgbecli -d <bdf> custom sxe2 fwinfo` 获取 `uptime`，验证重启后运行时间是否合理（通常应小于数分钟）。
2. **reset reason 校验**
   通过同一命令输出中的 `NIC RST CAUSE` 验证启动原因是否符合预期（如 `PWR_RST`）。
3. **版本回退校验**
   通过 `scgbecli -d <bdf> show fw` 或 `ethtool -i <iface>` 获取当前版本，与记录的原始版本比对，确认已回退到旧版本。
4. **设备与链路恢复校验**
   - 以太场景：`ip link show <iface>` 确认接口重新出现；`scgbecli -d <bdf> show` 确认 `Link Status` 为 `up`。
   - IB/RDMA 场景：`ibstat` / `ibstatus` 确认设备状态为 `Active`。

## 失败处理

以下情况需按「缺陷自动记录」skill 调用 `create_bug` 或 `CommonOperation.create_bug_problem`：

- **切分区命令执行失败**或 `switch_state` 未变为 `1`
- **分区覆盖超时**：切分区后 300s 内 `run_state` 仍不为 `0`
- **重启后 uptime 异常**：过大或过小，超出合理阈值
- **reset reason 不符合预期**：如预期 `PWR_RST` 但返回其他原因
- **版本未回退到预期**：实际版本与原始/目标版本不一致
- **设备不可见或链路未恢复**：回滚后接口/device 未重新出现，或业务冒烟失败

统一使用 `BugTypeEnum.FUNCTION.value`（即 `"功能问题"`）。

## 示例模式

下面给出基于 `cli_operation.py` 与 `command_operation.py` 的完整主机侧回滚流程示例，可直接嵌入用例 `do()` 阶段（示例假设运行在类方法中，`cls` 为当前用例类）：

```python
import re
import time

from scripts.script_libs.cli_operation import CliOperation, AnalyzeCli
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import BugTypeEnum, CmdExecuteAdressEnum, RtnStatusEnum
from scripts.script_libs import constants, log
from scripts.nic100.linux.fw.bmc.common_bmc import CommonTools


def do_host_firmware_rollback(cls, bdf, original_version, exec_addr=None):
    """主机侧固件回滚：切分区 -> 重启 -> 校验"""
    if exec_addr is None:
        exec_addr = CmdExecuteAdressEnum.SERVER.value

    timeout = 300
    interval = 5

    # 1. 记录回滚前分区状态
    state_before = CliOperation.get_upgrade_syncstate_info(
        bus_info=bdf,
        caller_class=cls,
        switch_info="0",
        exec_addr=exec_addr,
    )
    log.info(f"回滚前分区状态: {state_before}")

    # 2. 等待当前分区空闲
    start = time.time()
    while time.time() - start < timeout:
        state = CliOperation.get_upgrade_syncstate_info(
            bus_info=bdf,
            caller_class=cls,
            switch_info="0",
            exec_addr=exec_addr,
        )
        if state.get("run_state") == 0:
            log.info("当前分区空闲，可以执行切分区")
            break
        time.sleep(interval)
    else:
        cls.bug_result = f"分区在 {timeout}s 内未变为 run state: 0"
        cls.bug_expect = "切分区前应显示 run state: 0"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug("主机侧固件回滚前分区覆盖超时")
        return

    # 3. 执行切分区操作
    CliOperation.change_flash_flag(
        bus_info=bdf,
        caller_class=cls,
        exec_addr=exec_addr,
    )

    # 4. 验证 switch_state 已变为 1
    state_after = CliOperation.get_upgrade_syncstate_info(
        bus_info=bdf,
        caller_class=cls,
        switch_info="0",
        exec_addr=exec_addr,
    )
    if state_after.get("switch_state") != 1:
        cls.bug_result = f"切分区后 switch_state 为 {state_after.get('switch_state')}"
        cls.bug_expect = "切分区后 switch_state 应为 1"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug("主机侧固件回滚切分区失败")
        return

    # 5. 等待分区覆盖完成
    start = time.time()
    while time.time() - start < timeout:
        state = CliOperation.get_upgrade_syncstate_info(
            bus_info=bdf,
            caller_class=cls,
            switch_info="0",
            exec_addr=exec_addr,
        )
        if state.get("run_state") == 0:
            log.info("分区覆盖完成")
            break
        time.sleep(interval)
    else:
        cls.bug_result = f"切分区后 {timeout}s 内 run state 仍为 1"
        cls.bug_expect = "切分区后应显示 run state: 0"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug("主机侧固件回滚后分区覆盖未完成")
        return

    # 6. 重启服务器并重新加载驱动
    server_ip = CommandLineArgsParse.get_server_ip()
    CommonTools.reboot_host(ssh_ip=server_ip, timeout=900)

    # 7. 校验 uptime 与 reset reason
    cmd = f"{constants.SCGBECLI64} -d {bdf} custom sxe2 fwinfo"
    status, output, _ = CommandOperation.execute_command_with_error(
        cmd=cmd, cmd_execute_address=exec_addr
    )
    if status != RtnStatusEnum.SUCCESS.value:
        cls.bug_result = f"custom sxe2 fwinfo 执行失败: {output}"
        cls.bug_expect = "回滚后应能正常获取 fwinfo"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug("主机侧固件回滚后 fwinfo 获取失败")
        return

    uptime_match = re.search(
        r"uptime:\s*(\d+)\s*days?,?\s*(\d+)\s*hours?,?\s*(\d+)\s*minutes?,?\s*(\d+)\s*seconds?",
        output,
    )
    if not uptime_match:
        cls.bug_result = "fwinfo 输出中未解析到 uptime"
        cls.bug_expect = "回滚后应能解析到 uptime"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug("主机侧固件回滚后 uptime 解析失败")
        return
    days, hours, minutes, seconds = map(int, uptime_match.groups())
    total_seconds = days * 86400 + hours * 3600 + minutes * 60 + seconds
    uptime_threshold = 600  # 示例阈值，实际按场景调整
    if total_seconds > uptime_threshold:
        cls.bug_result = f"回滚后 uptime 为 {total_seconds}s，超过阈值 {uptime_threshold}s"
        cls.bug_expect = f"回滚后 uptime 应小于 {uptime_threshold}s"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug("主机侧固件回滚后 uptime 异常")
        return

    rst_match = re.search(r"NIC RST CAUSE:\s*(.+?)(?:\n|$)", output)
    if not rst_match:
        cls.bug_result = "fwinfo 输出中未解析到 NIC RST CAUSE"
        cls.bug_expect = "回滚后应能解析到 NIC RST CAUSE"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug("主机侧固件回滚后启动原因解析失败")
        return
    rst_cause = rst_match.group(1).strip()
    expected_reason = "PWR_RST"
    if expected_reason.lower() not in rst_cause.lower():
        cls.bug_result = f"回滚后启动原因为 {rst_cause}"
        cls.bug_expect = f"回滚后启动原因应包含 {expected_reason}"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug("主机侧固件回滚后启动原因不符合预期")
        return

    # 8. 校验版本回退到预期版本
    status, fw_info, raw = AnalyzeCli.analyze_dev_show_fw(
        dev_para=bdf,
        exec_addr=exec_addr,
    )
    current_version = fw_info.get("FW Version", "")
    if current_version != original_version:
        cls.bug_result = f"回滚后 FW 版本为 {current_version}，不是预期版本 {original_version}"
        cls.bug_expect = f"回滚后 FW 版本应为 {original_version}"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug("主机侧固件回滚后版本校验失败")
        return

    # 9. 校验设备与链路恢复
    status, dev_info, raw = AnalyzeCli.analyze_dev_show(
        dev_para=bdf,
        exec_addr=exec_addr,
    )
    link_status = dev_info.get("Link Status", "")
    if "up" not in link_status.lower():
        cls.bug_result = f"回滚后链路状态为 {link_status}"
        cls.bug_expect = "回滚后链路应恢复为 up"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug("主机侧固件回滚后链路未恢复")
        return

    log.info("主机侧固件回滚完成，所有校验通过")
```

> 项目 `common_bmc.py` 中的 `CommonTools.get_reset_reason_and_uptime_check` 也提供了封装好的 uptime 与 reset reason 校验方法，BMC/PLDM 相关用例可直接复用；主机侧用例如需统一阈值控制，可参考其实现。

## 脚本位置建议

- 主机侧固件测试脚本建议放到：`ps3/test/esat/nic100/scripts/nic100/linux/fw/host/`
- 公共库：
  - `ps3/test/esat/nic100/scripts/script_libs/cli_operation.py`
  - `ps3/test/esat/nic100/scripts/script_libs/command_operation.py`
  - `ps3/test/esat/nic100/scripts/script_libs/common_operation.py`
  - `ps3/test/esat/nic100/scripts/nic100/linux/fw/bmc/common_bmc.py`

## 注意事项

1. `scgbecli` 切分区与 `custom sxe2 fwinfo` 通常需要 root 权限。
2. 回滚前务必确认目标分区中的固件版本与设备型号匹配，避免误切到错误版本。
3. 分区同步状态轮询默认按 5s 间隔、最多 60 次（约 300s）处理；若项目超时策略不同，可按需调整。
4. 切分区后必须重启服务器才能生效，重启后需等待驱动重新加载、设备重新出现。
5. 回滚过程中请勿中途断电或强制重启，避免设备变砖。
6. 并发执行多个固件回滚用例时，确保目标 BDF/接口互不冲突。
7. `post()` 阶段必须恢复原始版本或分区，除非用例明确允许保留当前版本。
