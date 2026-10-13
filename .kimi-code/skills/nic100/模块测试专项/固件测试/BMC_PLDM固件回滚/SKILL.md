---
name: BMC_PLDM固件回滚
description: 指导NIC100框架下对BMC/PLDM固件进行回滚，包括回滚触发条件、命令执行、BMC重连、EID重新获取、回滚后校验与日志检查。
---

# BMC/PLDM 固件回滚

## 测试范围

- 在升级失败、版本校验失败或业务异常时，将 BMC/PLDM 固件恢复到升级前版本。
- 通过再次下发 PLDM upgrade 命令使用旧版本镜像实现回滚（部分平台支持 BMC 侧自带回滚指令时也可使用）。
- 回滚后等待 BMC 重启恢复、重新获取 EID、重建 BDF-EID 映射、校验 UUID/版本/关键 sensor。
- 检查 BMC 日志中是否存在异常关键字（`ERROR`、`FAIL` 等）。
- 失败时按「缺陷自动记录」skill 自动提交 Bug。

## 核心概念

### 回滚触发条件

以下场景需要执行 BMC/PLDM 固件回滚：

1. **升级后版本校验失败**：实际 FW 版本与目标版本不一致。
2. **升级后 BMC 无法正常通信**：EID 无法获取、UUID 读取失败、MCTP/PLDM 通信异常。
3. **用例明确要求验证回滚流程**：如升级后回滚到原版本并确认功能正常。
4. **升级过程中状态长时间卡住**：`FW State` 持续为 `0x31` 超过超时时间，且需恢复环境。

### 回滚命令形式

BMC/PLDM 回滚通常通过再次下发 PLDM upgrade 命令，使用旧版本镜像实现；部分平台支持 BMC 侧自带的回滚指令。命令形式与升级相同：

```bash
BMC_TOOL_PATH -e <eid> -m 1 -t 5 -c 0 --addr=<bmc_ip> --name=<bmc_user> --passwd=<bmc_pwd>
```

非 Intel CPU 平台（Teston 等）通常需要指定 BMC 侧镜像路径与 Terminus ID：

```bash
BMC_TOOL_PATH -e <eid> -m 1 -t 5 -c 0 -b /var/image_rollback.pldm -f <tid> --addr=<bmc_ip> --name=<bmc_user> --passwd='<bmc_pwd>'
```

其中 `<tid>` 通过 `PldmTool.get_tid_code_2(ip=<bmc_ip>, eid=<eid>, execute_addr=...)` 获取，返回 `(status, tid)`。

## 回滚前准备

1. **确认 BMC IP 可达**
   - 调用 `CommonTools.get_bmc_ip(execute_addr)` 获取 BMC IP。
2. **准备回滚镜像**
   - 默认通过 `CommonOperation.get_bmc_pldm_upgrade_file_for_bdf(bdf_info=bdf, exec_addr=exec_addr, caller_class=cls)` 获取框架配置的旧版本 BMC/PLDM 镜像路径；当用例指定自定义路径时，可显式覆盖该返回值。
   - 确认镜像路径有效后，按「镜像传输」步骤上传到 BMC，命名为 `image_rollback.pldm`。
3. **记录升级前关键信息**
   - 记录升级前的 `FW Version`、`Base UUID`、EID、关键 sensor 读数，用于回滚后对比。
4. **关闭 BMC monitor**
   - 调用 `CommonTools.close_monitor(ip, execute_addr)`，避免 monitor 进程干扰回滚。

## 回滚执行

1. **重新获取当前 EID**
   - 调用 `CommonTools.get_bmc_eid_list(ip, execute_addr)` 与 `CommonTools.get_env_bmc_eid_info(...)` 建立 BDF-EID 映射。
2. **获取 TID**
   - 调用 `PldmTool.get_tid_code_2(ip=bmc_ip, eid=eid, execute_addr=exec_addr)` 获取 Terminus ID。
3. **下发回滚命令**
   - 构造与升级命令相同形式的 PLDM upgrade 命令，使用旧版本镜像。
   - 检查回显：出现 `wait update` 通常表示回滚已触发；出现 `bad`/`fail` 或回显为空则报回滚失败 Bug。

## 回滚后等待

1. **等待 BMC 重启后 IP 可 ping 通**
   - 回滚过程中 BMC 可能重启，需通过 `ping <bmc_ip>` 或执行简单 SSH 命令确认 BMC 已恢复，通常从 15 秒开始轮询。
2. **重新获取 EID 列表**
   - BMC 重启后 EID 可能变化，需重新调用 `CommonTools.get_bmc_eid_list`。
3. **单 EID 无法通信时尝试重启 BMC**
   - 若某个 EID 无法通信，可调用 `CommonTools.reboot_bmc(ip, execute_addr)` 后重新获取。

## 回滚后校验

1. **UUID 校验**
   - 通过 `PldmTool.get_uuid(ip=bmc_ip, eid=eid, execute_addr=...)` 获取 BMC 侧 UUID，确认与升级前一致。
2. **关键 sensor 状态校验**
   - 通过 `PldmTool.get_state_sensor_reading(ip=bmc_ip, eid=eid, sensor=..., execute_addr=...)` 校验关键 sensor 状态正常。
3. **版本校验（双版本模型）**
   - 回滚前通过 `CliOperation.get_cli_show_fw_info(caller_class=cls, device=bdf)` 记录当前版本，作为 `pre_rollback_version`。
   - 回滚前或测试设计阶段明确目标旧版本 `target_rollback_version`（可由测试用例参数、回滚镜像元数据或升级前记录提供）。
   - 回滚后再次获取 FW 版本，确认其**等于 `target_rollback_version`**；若仍等于 `pre_rollback_version`，说明回滚未实际切换版本，也应报 Bug。
4. **BMC 日志检查**
   - 登录 BMC 检查日志文件中是否包含 `ERROR`、`FAIL` 等异常关键字。

## 失败处理

以下情况需按「缺陷自动记录」skill 调用 `create_bug`，统一使用 `BugTypeEnum.FUNCTION.value`（即 `"功能问题"`）：

- **回滚命令失败**
  - 回显包含 `bad`/`fail`、回显为空、或未出现 `wait update`，记录 result/expect 并调用 `create_bug`。
- **回滚后 BMC 无法重连**
  - ping/SSH 恢复失败，尝试 `CommonTools.reboot_bmc` 后仍失败则报 Bug。
- **回滚后版本仍不符合预期**
  - 实际版本与旧版本不一致，报版本校验失败 Bug。
- **回滚后 UUID/sensor 异常**
  - UUID 无法获取或与升级前不一致、关键 sensor 状态异常，报 Bug。
- **BMC 日志存在异常关键字**
  - 日志中出现 `ERROR`、`FAIL` 等关键字，按实际影响程度决定是否报 Bug。

## 示例模式

下面给出基于 `common_bmc.py` 的完整 BMC/PLDM 回滚流程示例，可直接嵌入用例 `do()` 或 `post()` 阶段。示例中回滚镜像路径默认由 `CommonOperation.get_bmc_pldm_upgrade_file_for_bdf` 根据 BDF 自动获取，用例指定自定义路径时可直接覆盖：

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

# 2. 重新获取 EID 列表
eid_list = CommonTools.get_bmc_eid_list(ip=bmc_ip, execute_addr=exec_addr)
if not eid_list:
    log.warning("回滚前获取当前环境网卡的 BMC EID 失败，尝试重启 MCTP 服务")
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
        cls.create_bug("BMC/PLDM 回滚前获取 EID 失败")

# 3. 通过 UUID 建立 BDF 与 EID 的对应关系
info_dict = CommonTools.get_env_bmc_eid_info(
    test_device_info_list=cls.test_device_info_list,
    bmc_ip=bmc_ip,
    execute_addr=exec_addr,
)

# 4. 记录回滚前版本并准备回滚镜像
target_bdf = list(info_dict.keys())[0]
eid = info_dict[target_bdf]["eid"]

ori_fw_info = CliOperation.get_cli_show_fw_info(
    caller_class=cls,
    device=target_bdf,
)
pre_rollback_version = ori_fw_info.get("FW Version", "")
expected_uuid = ori_fw_info.get("Base UUID", "").lower()

# 目标回滚版本由测试用例参数指定，例如：
# cls.target_rollback_version = "0.5.0.0"
# 也可从回滚镜像元数据或升级前记录中获取。
target_rollback_version = cls.target_rollback_version

# 默认通过框架 helper 获取设备对应的 BMC/PLDM 升级（回滚）镜像路径；
# 当用例指定自定义路径时，可显式覆盖。
rollback_pkg_path = CommonOperation.get_bmc_pldm_upgrade_file_for_bdf(
    bdf_info=target_bdf,
    exec_addr=exec_addr,
    caller_class=cls,
)
pkg_name = rollback_pkg_path.split("/")[-1]
bmc_img_path = "/var"
bmc_img_name = "image_rollback.pldm"

# 4.1 关闭 monitor
CommonTools.close_monitor(ip=bmc_ip, execute_addr=exec_addr)

# 4.2 上传回滚镜像
cmd_cp_pkg = (
    f"sshpass -p {constants.BMC_PWD} scp -P {CommandLineArgsParse.get_test_port()} "
    f"{rollback_pkg_path} {constants.BMC_NAME}@{bmc_ip}:{bmc_img_path}/"
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
    cls.bug_expect = "回滚镜像应成功上传到 BMC 并重命名为 image_rollback.pldm"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 回滚镜像传输失败")

# 5. 下发 PLDM 回滚命令（以非 Intel 平台为例）
status_tid, tid = PldmTool.get_tid_code_2(ip=bmc_ip, eid=eid, execute_addr=exec_addr)
cmd_rollback = (
    f"{constants.BMC_TOOL_PATH} -e {eid} -m 1 -t 5 -c 0 "
    f"-b {bmc_img_path}/{bmc_img_name} -f {tid} "
    f"--addr={bmc_ip} --name={constants.BMC_NAME} --passwd='{constants.BMC_PWD}'"
)
log.info(f"PLDM 回滚命令: {cmd_rollback}")
status, output_rollback, output_err = CommandOperation.execute_command_with_error(
    cmd=cmd_rollback,
    cmd_execute_address=exec_addr,
)
output_rollback += output_err
if "bad" in output_rollback.lower() or "fail" in output_rollback.lower():
    cls.bug_result = f"PLDM 回滚命令返回错误: {output_rollback}"
    cls.bug_expect = "回滚命令应正常触发，回显包含 wait update 或类似成功提示"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 回滚命令执行失败")
elif "wait update" not in output_rollback:
    cls.bug_result = f"PLDM 回滚命令回显异常: {output_rollback}"
    cls.bug_expect = "回滚命令应返回 wait update 提示"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 回滚命令未触发回滚")

# 6. 轮询 0x31 状态，直到状态解除或超时
timeout = 3000  # 50 分钟
start = time.time()
while time.time() - start < timeout:
    fw_state = CommonTools.get_soc_fw_state(eid=eid, execute_addr=exec_addr)
    log.info(f"当前 FW State: 0x{fw_state:02x}")
    if fw_state == 0x31:
        time.sleep(15)
        continue
    log.info("BMC/PLDM 回滚状态已解除")
    break
else:
    cls.bug_result = f"FW State 在 {timeout}s 内持续为 0x31"
    cls.bug_expect = "回滚完成后 FW State 应退出 0x31"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 固件回滚超时")

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
    cls.bug_result = f"回滚后 BMC {bmc_ip} 无法 ping 通"
    cls.bug_expect = "回滚完成后 BMC 应恢复网络连接"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 回滚后 BMC 恢复失败")

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
    cls.bug_result = f"回滚后无法通过 EID {new_eid} 获取 BMC UUID"
    cls.bug_expect = "回滚完成后 MCTP/PLDM 通信应恢复正常"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 回滚后 MCTP 通信异常")

if uuid_bmc.lower() != expected_uuid:
    cls.bug_result = f"回滚后 BMC UUID 为 {uuid_bmc}，与升级前 UUID {expected_uuid} 不一致"
    cls.bug_expect = "回滚后 BMC UUID 应与升级前保持一致"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 回滚后 UUID 校验失败")

# 9. 版本校验
# 双版本模型：
# - pre_rollback_version：回滚前记录到的版本（通常为升级后的新版本）。
# - target_rollback_version：期望回滚到的目标旧版本，由测试用例参数或镜像元数据指定。
# 回滚后应观察到 rollback_version == target_rollback_version，
# 且 rollback_version != pre_rollback_version（否则说明版本未切换）。
rollback_fw_info = CliOperation.get_cli_show_fw_info(
    caller_class=cls,
    device=target_bdf,
)
rollback_version = rollback_fw_info.get("FW Version", "")
if rollback_version != target_rollback_version:
    if rollback_version == pre_rollback_version:
        cls.bug_result = (
            f"回滚后 FW 版本仍为 {rollback_version}，与回滚前版本相同，"
            f"未切换到目标旧版本 {target_rollback_version}"
        )
        cls.bug_expect = (
            f"回滚后 FW 版本应为 {target_rollback_version}，"
            f"且应不同于回滚前版本 {pre_rollback_version}"
        )
    else:
        cls.bug_result = f"回滚后 FW 版本为 {rollback_version}，不是目标旧版本 {target_rollback_version}"
        cls.bug_expect = f"回滚后 FW 版本应为 {target_rollback_version}"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 回滚后版本校验失败")

# 10. 关键 sensor 状态校验（示例：SOC 状态 sensor）
status_sensor, state_dict = PldmTool.get_state_sensor_reading(
    ip=bmc_ip,
    eid=new_eid,
    sensor=constants.BMC_STATE_SOC,
    execute_addr=exec_addr,
)
if status_sensor != "0":
    cls.bug_result = f"回滚后获取 state sensor 失败，status: {status_sensor}"
    cls.bug_expect = "回滚后 state sensor 应能正常读取且 status 为 0"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("BMC/PLDM 回滚后 sensor 读取失败")

# 11. BMC 日志异常关键字检查
log_cmd = (
    f"sshpass -p {constants.BMC_PWD} ssh -p {CommandLineArgsParse.get_test_port()} "
    f"{constants.BMC_NAME}@{bmc_ip} 'grep -iE \"ERROR|FAIL\" {constants.BMC_LOG_PATH} || true'"
)
_, log_output, _ = CommandOperation.execute_command_with_error(
    cmd=log_cmd,
    cmd_execute_address=exec_addr,
)
if log_output.strip():
    log.warning(f"BMC 日志中发现异常关键字:\n{log_output}")
    # 根据实际影响决定是否提 Bug；如影响功能则取消下面注释
    # cls.bug_result = f"回滚后 BMC 日志存在异常关键字: {log_output.strip()}"
    # cls.bug_expect = "回滚后 BMC 日志不应存在 ERROR/FAIL 等异常关键字"
    # cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    # cls.create_bug("BMC/PLDM 回滚后 BMC 日志异常")
```

## 脚本位置建议

- BMC 侧固件测试脚本建议放到：`ps3/test/esat/nic100/scripts/nic100/linux/fw/bmc/`
- 公共库：`ps3/test/esat/nic100/scripts/nic100/linux/fw/bmc/common_bmc.py`

## 注意事项

1. BMC/PLDM 回滚依赖真实 BMC 网络、SSH 账号和真实旧版本镜像路径，执行前务必确认镜像与设备型号、UUID 匹配。
2. 不同平台（G40/G50、Intel/Teston）的 BMC 工具路径和登录方式可能存在差异，需按实际环境调整 `BMC_TOOL_PATH`、`BMC_NAME`、`BMC_PWD`、SSH 端口（`CommandLineArgsParse.get_test_port()` 或 `cls.test_port`）等参数。
3. 回滚过程中 BMC 和网卡固件可能重启，需预留足够的重连和轮询时间（建议 50 分钟以上）。
4. 回滚前必须备份升级前的版本号、UUID 和关键 sensor 读数，作为回滚后对比基线。
5. 若回滚后单 EID 无法通信，可先尝试 `MctpTools.restart_mctp_service(bmc_ip)`，仍失败则尝试 `CommonTools.reboot_bmc(ip, execute_addr)`。
6. 并发执行多个 BMC/PLDM 回滚用例时，需确保目标 EID/设备互不冲突。
7. `post()` 阶段必须恢复原始版本或分区，除非用例明确允许保留新版本。
