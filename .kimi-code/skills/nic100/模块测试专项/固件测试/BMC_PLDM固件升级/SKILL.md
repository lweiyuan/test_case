---
name: BMC_PLDM固件升级
description: 指导NIC100框架下通过BMC通道和PLDM协议对网卡BMC侧固件进行升级，包括EID/UUID匹配、镜像传输、PLDM升级命令下发和0x31状态机轮询。
---

# BMC/PLDM 固件升级

## 测试范围

- 通过 BMC 通道和 PLDM 协议对 NIC100 BMC 侧固件进行升级。
- 升级前获取 BMC IP、EID 列表，并通过 UUID 将网卡 BDF 与 BMC EID 一一对应。
- 将升级镜像传输到 BMC `/var/` 目录并重命名为 `image.pldm`。
- 使用 `BMC_TOOL_PATH -e <eid> -m 1 -t 5 -c 0` 下发 PLDM 升级命令。
- 升级过程中轮询 `FW State`（`0x31` 表示升级中），直到状态解除或超时。
- 升级后重新获取 EID、校验版本、确认 MCTP 通信和业务恢复。
- 失败时按「缺陷自动记录」skill 自动提交 Bug。

## 核心概念

### EID（Endpoint ID）

MCTP/PLDM 通信中用于标识 BMC 或网卡端点的短地址。升级前必须通过 BMC 工具获取当前环境的 EID 列表，并确认目标网卡对应的 EID。

### UUID 匹配

BMC 或 PLDM 设备的唯一标识。升级前需通过 `PldmTool.get_uuid` 获取 BMC 侧 UUID，再与主机侧 `CliOperation.get_cli_show_fw_info` 返回的 `Base UUID` 进行匹配，从而将网卡 BDF 与 BMC EID 对应起来。

### FW State：`0x31`

BMC/PLDM 升级过程中，通过 `CommonTools.get_soc_fw_state(eid, execute_addr)` 查询固件状态：

- `0x31`：升级进行中（BUSY / UPDATE IN PROGRESS）。
- 其他值（如 `0x00`、`0x01` 等）：升级完成或退出升级状态（具体以 BMC 工具返回说明为准）。

## 适用命令

### 获取 BMC IP

```python
bmc_ip = CommonTools.get_bmc_ip(execute_addr=CmdExecuteAdressEnum.SERVER.value)
```

### 获取 BMC EID 列表

```python
eid_list = CommonTools.get_bmc_eid_list(
    ip=bmc_ip,
    execute_addr=CmdExecuteAdressEnum.SERVER.value,
    wait_max_count=5,
    interval=5,
)
```

### 通过 UUID 建立 BDF 与 EID 的对应关系

```python
info_dict = CommonTools.get_env_bmc_eid_info(
    test_device_info_list=cls.test_device_info_list,
    bmc_ip=bmc_ip,
    execute_addr=CmdExecuteAdressEnum.SERVER.value,
)
# info_dict[bdf]['eid'] 即为该 BDF 对应的 BMC EID
```

### 镜像传输

升级前需将本地镜像包拷贝到 BMC 的 `/var/` 目录，并重命名为 `image.pldm`：

```bash
# 拷贝镜像包到 BMC
sshpass -p <bmc_pwd> scp -P <bmc_ssh_port> <pkg_path> <bmc_user>@<bmc_ip>:/var/

# 在 BMC 上重命名为 image.pldm
sshpass -p <bmc_pwd> ssh -p <bmc_ssh_port> <bmc_user>@<bmc_ip> 'cd /var/; mv <pkg_name> image.pldm'

# 确认文件存在
sshpass -p <bmc_pwd> ssh -p <bmc_ssh_port> <bmc_user>@<bmc_ip> 'ls /var/ | grep image.pldm'
```

### PLDM 升级命令

非 Intel CPU 平台（Teston 等）通常使用完整镜像路径：

```bash
BMC_TOOL_PATH -e <eid> -m 1 -t 5 -c 0 -b /var/image.pldm -f <tid> --addr=<bmc_ip> --name=<bmc_user> --passwd='<bmc_pwd>'
```

其中 `<tid>` 通过 `PldmTool.get_tid_code_2(ip=<bmc_ip>, eid=<eid>, execute_addr=...)` 获取，返回 `(status, tid)`。

Intel CPU 平台当前通常简化为（以实际项目支持情况为准）：

```bash
BMC_TOOL_PATH -e <eid> -m 1 -t 5 -c 0 --addr=<bmc_ip> --name=<bmc_user> --passwd='<bmc_pwd>' -d <skip_ip>
```

参数说明：

| 参数 | 说明 |
|------|------|
| `-e <eid>` | 目标设备 EID |
| `-m 1` | MCTP 消息类型，固定为 1 |
| `-t 5` | PLDM 类型，固定为 5（FW Update） |
| `-c 0` | PLDM 命令码，固定为 0（Request Update） |
| `-b <path>` | BMC 侧镜像完整路径（非 Intel 平台） |
| `-f <tid>` | Terminus ID，通过 `PldmTool.get_tid_code_2` 获取 |
| `--addr=<bmc_ip>` | BMC IP 地址 |
| `--name=<bmc_user>` | BMC SSH 用户名 |
| `--passwd='<bmc_pwd>'` | BMC SSH 密码 |
| `-d <skip_ip>` | Intel 平台跳过参数（以实际环境为准） |

### 查询固件升级状态

```python
fw_state = CommonTools.get_soc_fw_state(
    eid=eid,
    execute_addr=CmdExecuteAdressEnum.SERVER.value,
)
```

返回值为整数形式的 `pres_state`，`0x31` 表示仍在升级中。

## 升级前

1. **获取 BMC IP**
   - 调用 `CommonTools.get_bmc_ip(execute_addr)` 从主机侧通过 `ipmitool lan print 1` 解析 BMC IP。
2. **获取 EID 列表**
   - 调用 `CommonTools.get_bmc_eid_list(ip, execute_addr)`。
   - 若列表为空，先尝试 `MctpTools.restart_mctp_service(bmc_ip)`，等待 90 秒后重新获取；仍失败则报 Bug。
3. **UUID 匹配**
   - 调用 `CommonTools.get_env_bmc_eid_info(test_device_info_list)`，将每个 BDF 的 `Base UUID` 与 BMC 侧 UUID 匹配，得到 `info_dict[bdf]['eid']`。
4. **记录原始版本**
   - 对每个目标 BDF，使用 `CliOperation.get_cli_show_fw_info(caller_class=cls, device=bdf)` 记录当前 `FW Version`、`Base UUID` 等。
5. **镜像准备**
   - 确认镜像包路径有效，按「镜像传输」步骤将镜像上传到 BMC 并命名为 `image.pldm`。

## 升级中

1. **关闭 BMC monitor**
   - 调用 `CommonTools.close_monitor(ip, execute_addr)`，避免 monitor 进程干扰升级。
2. **下发 PLDM 升级命令**
   - 根据 CPU 平台构造对应的 `BMC_TOOL_PATH` 命令。
   - 检查命令回显：出现 `wait update` 通常表示升级已触发；出现 `bad`/`fail` 或回显为空则报升级失败 Bug。
3. **轮询 `0x31` 状态**
   - 调用 `CommonTools.get_soc_fw_state(eid, execute_addr)` 轮询。
   - 状态为 `0x31` 时继续等待；状态变为非 `0x31` 时认为升级完成。
   - 设置合理超时，如 50 分钟（3000 秒），避免升级卡死。

## 升级后

1. **等待 BMC 重连**
   - 升级过程中 BMC 可能重启，需通过 `ping <bmc_ip>` 或执行简单 SSH 命令确认 BMC 已恢复。
2. **重新获取 EID**
   - BMC 重启后 EID 可能变化，需重新调用 `CommonTools.get_bmc_eid_list` 和 `CommonTools.get_env_bmc_eid_info` 建立新的 BDF-EID 映射。
3. **版本校验**
   - 通过 `CliOperation.get_cli_show_fw_info` 获取主机侧 `FW Version`，校验当前版本是否为目标版本。
   - `PldmTool.get_uuid(ip=bmc_ip, eid=eid, execute_addr=...)` 仅用于获取 BMC 侧 UUID，不能用于校验固件版本。
4. **MCTP 通信确认**
   - 对新的 EID 执行 `PldmTool.get_uuid`，确认 PLDM 通信正常；失败则先尝试 `MctpTools.restart_mctp_service`。
5. **业务恢复**
   - 若主机侧驱动或链路受影响，重新加载驱动并确认接口/设备可见。
   - 按业务类型执行基本冒烟（以太网 ping / IB perftest 等）。

## 失败处理

以下情况需按「缺陷自动记录」skill 调用 `create_bug` 或 `CommonOperation.create_bug_problem`，统一使用 `BugTypeEnum.FUNCTION.value`（即 `"功能问题"`）：

- **获取 EID 失败**
  - 先尝试 `MctpTools.restart_mctp_service(bmc_ip)`，等待 90 秒后重试；仍失败则报 Bug。
- **UUID 匹配失败**
  - 主机侧 `Base UUID` 与 BMC 侧 UUID 无法对应，报 Bug。
- **镜像传输失败**
  - 重试 5 次后仍无法在 BMC `/var/` 下找到 `image.pldm`，报 Bug。
- **PLDM 升级命令执行失败**
  - 回显包含 `bad`/`fail`、回显为空、或未出现 `wait update`，报 Bug。
- **状态持续为 `0x31` 超过超时时间**
  - 报升级失败 Bug。
- **BMC 升级后无法重连**
  - ping/SSH 恢复失败，报 BMC 恢复失败 Bug。
- **升级后版本校验失败**
  - 实际版本与目标版本不一致，报 Bug。

## 示例模式

下面给出基于 `common_bmc.py` 的完整 BMC/PLDM 升级流程示例，可直接嵌入用例 `do()` 阶段：

```python
import time

from scripts.nic100.linux.fw.bmc.common_bmc import CommonTools, PldmTool, MctpTools
from scripts.script_libs.cli_operation import CliOperation
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import BugTypeEnum, CmdExecuteAdressEnum
from scripts.script_libs import constants, log

# 1. 获取 BMC IP
exec_addr = CmdExecuteAdressEnum.SERVER.value
bmc_ip = CommonTools.get_bmc_ip(execute_addr=exec_addr)

# 2. 获取 EID 列表
eid_list = CommonTools.get_bmc_eid_list(ip=bmc_ip, execute_addr=exec_addr)
if not eid_list:
    log.warning("获取当前环境网卡的 BMC EID 失败，尝试重启 MCTP 服务")
    MctpTools.restart_mctp_service(bmc_ip=bmc_ip)
    time.sleep(90)
    eid_list = CommonTools.get_bmc_eid_list(
        ip=bmc_ip,
        execute_addr=exec_addr,
        wait_max_count=10,
    )
    if not eid_list:
        cls.bug_result = "重启 MCTP 服务后仍无法获取 BMC EID"
        cls.bug_expect = "应能正常获取 BMC EID 列表"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug("BMC/PLDM 升级前获取 EID 失败")

# 3. 通过 UUID 建立 BDF 与 EID 的对应关系
info_dict = CommonTools.get_env_bmc_eid_info(
    test_device_info_list=cls.test_device_info_list,
    bmc_ip=bmc_ip,
    execute_addr=exec_addr,
)

# 4. 记录原始版本并上传镜像
target_bdf = list(info_dict.keys())[0]
eid = info_dict[target_bdf]["eid"]

ori_fw_info = CliOperation.get_cli_show_fw_info(
    caller_class=cls,
    device=target_bdf,
)
ori_version = ori_fw_info.get("FW Version", "")

pkg_path = CommonOperation.get_bmc_pldm_upgrade_file_for_bdf(
    bdf_info=target_bdf,
    exec_addr=exec_addr,
    caller_class=cls,
)
if not pkg_path:
    cls.bug_result = "未找到与 BDF 对应的 BMC/PLDM 升级镜像"
    cls.bug_expect = "应能根据 BDF 自动匹配到 BMC/PLDM 镜像包"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 升级镜像获取失败")
pkg_name = pkg_path.split("/")[-1]
bmc_img_path = "/var"
bmc_img_name = "image.pldm"

# 4.1 关闭 monitor
CommonTools.close_monitor(ip=bmc_ip, execute_addr=exec_addr)

# 4.2 上传镜像
cmd_cp_pkg = (
    f"sshpass -p {constants.BMC_PWD} scp -P {CommandLineArgsParse.get_test_port()} "
    f"{pkg_path} {constants.BMC_NAME}@{bmc_ip}:{bmc_img_path}/"
)
CommandOperation.execute_command_with_error(cmd=cmd_cp_pkg, cmd_execute_address=exec_addr)

# 4.3 在 BMC 上重命名
cmd_mv = (
    f"sshpass -p {constants.BMC_PWD} ssh -p {CommandLineArgsParse.get_test_port()} "
    f"{constants.BMC_NAME}@{bmc_ip} 'cd {bmc_img_path}; mv {pkg_name} {bmc_img_name}'"
)
CommandOperation.execute_command_with_error(cmd=cmd_mv, cmd_execute_address=exec_addr)

# 4.4 确认文件存在
_, ls_output, _ = CommandOperation.execute_command_with_error(
    cmd=(
        f"sshpass -p {constants.BMC_PWD} ssh -p {CommandLineArgsParse.get_test_port()} "
        f"{constants.BMC_NAME}@{bmc_ip} 'ls {bmc_img_path}/ | grep {bmc_img_name}'"
    ),
    cmd_execute_address=exec_addr,
)
if bmc_img_name not in ls_output:
    cls.bug_result = f"BMC 侧未找到 {bmc_img_path}/{bmc_img_name}"
    cls.bug_expect = "镜像应成功上传到 BMC 并重命名为 image.pldm"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 升级镜像传输失败")

# 5. 下发 PLDM 升级命令（以非 Intel 平台为例）
status_tid, tid = PldmTool.get_tid_code_2(ip=bmc_ip, eid=eid, execute_addr=exec_addr)
cmd_upgrade = (
    f"{constants.BMC_TOOL_PATH} -e {eid} -m 1 -t 5 -c 0 "
    f"-b {bmc_img_path}/{bmc_img_name} -f {tid} "
    f"--addr={bmc_ip} --name={constants.BMC_NAME} --passwd='{constants.BMC_PWD}'"
)
log.info(f"PLDM 升级命令: {cmd_upgrade}")
status, output_upgrade, output_err = CommandOperation.execute_command_with_error(
    cmd=cmd_upgrade,
    cmd_execute_address=exec_addr,
)
output_upgrade += output_err
if "bad" in output_upgrade.lower() or "fail" in output_upgrade.lower():
    cls.bug_result = f"PLDM 升级命令返回错误: {output_upgrade}"
    cls.bug_expect = "升级命令应正常触发，回显包含 wait update 或类似成功提示"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 升级命令执行失败")
elif "wait update" not in output_upgrade:
    cls.bug_result = f"PLDM 升级命令回显异常: {output_upgrade}"
    cls.bug_expect = "升级命令应返回 wait update 提示"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 升级命令未触发升级")

# 6. 轮询 0x31 状态，直到状态解除或超时
timeout = 3000  # 50 分钟
start = time.time()
while time.time() - start < timeout:
    fw_state = CommonTools.get_soc_fw_state(eid=eid, execute_addr=exec_addr)
    log.info(f"当前 FW State: 0x{fw_state:02x}")
    if fw_state == 0x31:
        time.sleep(15)
        continue
    log.info("BMC/PLDM 升级状态已解除")
    break
else:
    cls.bug_result = f"FW State 在 {timeout}s 内持续为 0x31"
    cls.bug_expect = "升级完成后 FW State 应退出 0x31"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 固件升级超时")

# 7. 等待 BMC 重连
bmc_online = False
for _ in range(60):
    status, _, _ = CommandOperation.execute_command_with_error(
        cmd=f"ping -c 1 {bmc_ip}",
        cmd_execute_address=exec_addr,
    )
    if status == 0:
        bmc_online = True
        break
    time.sleep(5)
if not bmc_online:
    cls.bug_result = f"升级后 BMC {bmc_ip} 无法 ping 通"
    cls.bug_expect = "升级完成后 BMC 应恢复网络连接"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 升级后 BMC 恢复失败")

# 8. 重新获取 EID 并校验 UUID
info_dict = CommonTools.get_env_bmc_eid_info(
    test_device_info_list=cls.test_device_info_list,
    bmc_ip=bmc_ip,
    execute_addr=exec_addr,
)
new_eid = info_dict[target_bdf]["eid"]
_, uuid_bmc = PldmTool.get_uuid(
    ip=bmc_ip,
    eid=new_eid,
    execute_addr=exec_addr,
    create_bug=False,
)
if not uuid_bmc:
    cls.bug_result = f"升级后无法通过 EID {new_eid} 获取 BMC UUID"
    cls.bug_expect = "升级完成后 MCTP/PLDM 通信应恢复正常"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 升级后 MCTP 通信异常")

# 9. 版本校验
new_fw_info = CliOperation.get_cli_show_fw_info(
    caller_class=cls,
    device=target_bdf,
)
new_version = new_fw_info.get("FW Version", "")
target_version = "0.6.0.5"  # 按实际用例目标版本填写
if new_version != target_version:
    cls.bug_result = f"升级后 FW 版本为 {new_version}，不是目标版本 {target_version}"
    cls.bug_expect = f"升级后 FW 版本应为 {target_version}"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 升级后版本校验失败")
```

## 脚本位置建议

- BMC 侧固件测试脚本建议放到：`ps3/test/esat/nic100/scripts/nic100/linux/fw/bmc/`
- 公共库：`ps3/test/esat/nic100/scripts/nic100/linux/fw/bmc/common_bmc.py`

## 注意事项

1. BMC/PLDM 升级依赖真实 BMC 网络、SSH 账号和真实镜像路径，执行前务必确认镜像与设备型号、UUID 匹配。
2. 不同平台（G40/G50、Intel/Teston）的 BMC 工具路径和登录方式可能存在差异，需按实际环境调整 `BMC_TOOL_PATH`、`BMC_NAME`、`BMC_PWD`、SSH 端口（`CommandLineArgsParse.get_test_port()` 或 `cls.test_port`）等参数。
3. 升级过程中 BMC 和网卡固件可能重启，需预留足够的重连和轮询时间（建议 50 分钟以上）。
4. 升级过程中请勿中途断电或重启，避免设备变砖。
5. 并发执行多个 BMC/PLDM 升级用例时，需确保目标 EID/设备互不冲突。
6. `post()` 阶段必须恢复原始版本或分区，除非用例明确允许保留新版本。
