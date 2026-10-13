---
name: 固件测试
description: 指导NIC100框架下固件测试的通用规范，覆盖主机侧NIC固件与BMC/PLDM固件的升级、回滚、版本校验、异常恢复和日志检查。
---

# NIC100 固件测试指南

## 测试范围

- 主机侧 NIC 固件升级与回滚（sxe2cli、ethtool）
- BMC/PLDM 固件升级与回滚（通过 BMC 通道）
- 固件版本查询与校验
- 升级失败后的环境恢复与日志检查

## 关键概念

### 主分区 / 备分区（ping-pong 升级）

NIC100 主机侧固件通常采用双分区 ping-pong 机制：当前运行所在分区为主分区，另一分区为备分区。升级时先将新固件写入备分区，完成校验后切换启动分区；回滚时则切回原分区。

### EID / UUID（BMC 侧设备识别）

- **EID**（Endpoint ID）：MCTP/PLDM 通信中用于标识 BMC 或网卡端点的短地址。
- **UUID**：BMC 或 PLDM 设备的唯一标识，升级前需确认镜像与目标设备的 UUID 匹配。

### FW State：`0x31` 表示升级中

BMC/PLDM 升级过程中，通过状态查询命令返回的 `FW State` 字段判断当前阶段：

- `0x31`：升级进行中
- `0x00` 或 `0x01`：升级完成/成功（具体以 BMC 工具返回说明为准）

### `run state: 0` 表示分区覆盖完成

主机侧 `sxe2cli custom sxe2 upgrdsyncstate` 返回的 `run state` 字段：

- `run state: 0`：当前分区固件已覆盖完成
- `run state: 1`：当前分区固件尚未覆盖完成，仍需等待

## 核心命令速查表

| 命令 | 用途 | 适用场景 |
|------|------|----------|
| `ethtool -f <iface> <img>` | 通过 ethtool 刷写固件 | 主机侧通用 |
| `sxe2cli -d <bdf> upgrade file=<path>` | 通过 cli 升级 Image | 主机侧 SXE2/SCGBE |
| `sxe2cli -d <bdf> custom sxe2 upgrdsyncstate versionlineswitch=0` | 查询分区同步状态 | 主机侧回滚 |
| `sxe2cli -d <bdf> custom sxe2 upgrdsyncstate versionlineswitch=1` | 切换启动分区 | 主机侧回滚 |
| `BMC_TOOL_PATH -e <eid> -m 1 -t 5 -c 0 --addr=<ip> --name=<user> --passwd=<pwd>` | PLDM 固件升级 | BMC/PLDM |
| `BMC_TOOL_PATH -m 0 -c 0xff --addr=<ip> --name=<user> --passwd=<pwd>` | 获取 BMC EID 列表 | BMC/PLDM |

## 通用检查项

### 升级前

1. 备份当前版本号与分区信息。
2. 确认升级镜像存在且路径正确。
3. 确认 BMC IP、EID、UUID 已获取（BMC/PLDM 场景）。
4. 确认服务器与 BMC 网络可达，升级工具路径有效。

### 升级中

1. 轮询升级状态，设置合理超时（如 300s）。
2. 关键命令失败后记录 result/expect 并触发 Bug。
3. 对 BMC/PLDM 场景，记录每次轮询的 `FW State` 与原始回显。

### 升级后

1. 校验版本号是否变为目标版本。
2. 校验链路/设备是否重新出现。
3. 校验基本业务（ping/ibstat/opensm）是否恢复。
4. 确认 `post()` 阶段可回滚到原始版本或分区。

## 环境恢复与清理原则

- `post()` 阶段必须恢复原始版本或分区，除非用例明确允许保留新版本。
- 主机侧升级后若需重启，必须等待服务器上线并重新加载驱动。
- BMC/PLDM 升级后必须重新获取 EID 并确认 MCTP 通信正常。
- 测试过程中生成的临时镜像文件或日志，应在 `post()` 阶段清理。

## 失败处理与 Bug 记录

以下情况均需自动提交 Bug：

- 升级命令返回非零
- 版本校验失败
- 设备不可见
- 链路未恢复
- 分区切换后启动分区不符合预期

使用 `BugTypeEnum.FUNCTION`，对应字符串为 `"功能问题"`。

### Bug 记录示例

```python
from scripts.script_libs.enums import BugTypeEnum

cls.bug_result = "实际结果"
cls.bug_expect = "期望结果"
cls.set_bug_type(BugTypeEnum.FUNCTION.value)
cls.create_bug("详细描述")
```

### 主机侧升级状态轮询示例

```python
import time

from scripts.script_libs.enums import BugTypeEnum, CmdExecuteAdressEnum

timeout = 300
start = time.time()
while time.time() - start < timeout:
    status, output, _ = CommandOperation.execute_command_with_error(
        f"sxe2cli -d {bdf} custom sxe2 upgrdsyncstate versionlineswitch=0",
        CmdExecuteAdressEnum.SERVER.value
    )
    if "run state: 0" in output:
        log.info("分区覆盖完成")
        break
    time.sleep(5)
else:
    cls.bug_result = f"升级状态在 {timeout}s 内未变为 run state: 0"
    cls.bug_expect = "固件升级完成后应显示 run state: 0"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("主机侧固件升级超时，分区覆盖未完成")
```

### BMC/PLDM 状态轮询示例

```python
import time

from scripts.script_libs.enums import BugTypeEnum, CmdExecuteAdressEnum

timeout = 300
start = time.time()
while time.time() - start < timeout:
    status, output, _ = CommandOperation.execute_command_with_error(
        f"{bmc_tool_path} -e {eid} -m 1 -t 5 -c 0 "
        f"--addr={bmc_ip} --name={bmc_user} --passwd={bmc_pwd}",
        CmdExecuteAdressEnum.SERVER.value
    )
    if "FW State: 0x31" in output:
        time.sleep(5)
        continue
    if "FW State: 0x00" in output or "FW State: 0x01" in output:
        log.info("BMC/PLDM 升级完成")
        break
    time.sleep(5)
else:
    cls.bug_result = f"BMC/PLDM 升级状态在 {timeout}s 内未变为成功状态"
    cls.bug_expect = "BMC/PLDM 升级完成后 FW State 应为 0x00 或 0x01"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 固件升级超时")
```

## 子 skill 导航

| 场景 | 调用子 skill |
|------|--------------|
| 主机侧 NIC 固件升级 | `主机侧固件升级` |
| 主机侧 NIC 固件回滚 | `主机侧固件回滚` |
| BMC/PLDM 固件升级 | `BMC_PLDM固件升级` |
| BMC/PLDM 固件回滚 | `BMC_PLDM固件回滚` |

## 与现有 skill 关系

- 继承「网卡测试框架」的目录与基类约定。
- Bug 记录引用「缺陷自动记录」。
- 升级后业务验证引用「以太网模块测试」或「IB模块测试」。

## 脚本位置建议

- 主机侧固件测试脚本建议放到：`ps3/test/esat/nic100/scripts/nic100/linux/fw/host/`
- BMC 侧固件测试脚本建议放到：`ps3/test/esat/nic100/scripts/nic100/linux/fw/bmc/`

## 注意事项

1. `ethtool -f` 和 `sxe2cli upgrade` 通常需要 root 权限。
2. 不同平台（G40/G50、Intel/Teston）的 BMC 工具和登录方式可能存在差异，子 skill 需按实际平台调整参数。
3. 固件升级/回滚依赖真实硬件和真实镜像路径，执行前务必确认镜像与设备型号匹配。
4. 升级过程中请勿中途断电或重启，避免设备变砖。
5. 并发执行多个固件升级用例时，需确保目标设备互不冲突。
