---
name: 主机侧固件升级
description: 指导NIC100框架下通过scgbecli或ethtool对主机侧NIC固件进行升级，包括升级前校验、状态轮询和升级后验证。
---

# 主机侧固件升级

## 测试范围

- 通过 `scgbecli` 对 SXE2/SCGBE 网卡进行主机侧固件升级
- 通过 `ethtool -f` 对通用以太网接口进行固件刷写
- 升级前版本确认、镜像路径获取与存在性校验
- 升级过程中分区同步状态轮询
- 升级后驱动恢复、版本校验与基本业务冒烟

## 适用命令

### scgbecli 升级

> 实际二进制名称可能因网卡代际而异，例如 `scgbecli`、`sxe2cli` 等。项目框架中通过 `constants.SCGBECLI64` 构造命令，当前解析为 `scgbecli`（或 `{nicg}cli`）。

```bash
# 标准升级（带版本校验）
scgbecli -d <bdf> upgrade file=<image_path>

# 跳过版本校验
scgbecli -d <bdf> upgrade file=<image_path> noverchk

# 查询分区同步状态（versionlineswitch=0 不切换分区）
scgbecli -d <bdf> custom sxe2 upgrdsyncstate versionlineswitch=0
```

### ethtool 刷写

```python
from scripts.script_libs.ethtool_operation import EthtoolOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import CmdExecuteAdressEnum

# 默认通过框架 helper 获取当前 BDF 对应的升级镜像；用例指定自定义路径时可覆盖
image_path = CommonOperation.get_image_upgrade_file_for_bdf(
    bdf_info=bdf,
    exec_addr=exec_addr,
    caller_class=cls,
)

rtn_code, output, err = EthtoolOperation.ethtool_flash(
    device_name="ens1f0",
    file=image_path,
    region="0",  # 可选，留空则不带 region 参数
    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
)
```

## 升级前

1. **查询当前版本**
   - `ethtool -i <iface>` 查看 `firmware-version` 与 `driver` 信息。
   - `scgbecli -d <bdf> show fw` 查看 `FW Version`、`Product Version` 等字段。
2. **确认镜像存在**
   使用 `FileOperation.file_path_exists(path)` 校验本地或远端镜像是否可访问。
3. **获取默认镜像路径**
   参考 `CommonOperation.get_image_upgrade_file_for_bdf(bdf, exec_addr, caller_class)`，根据 BDF 对应的 sub-device-id 自动匹配 `OCP_X2_25G_IMAGE_PACKAGE_PATH` / `PCIE_X2_25G_IMAGE_PACKAGE_PATH` 等路径。
4. **记录原始版本与分区**
   在 `prepare()` 阶段备份当前版本号、启动分区与 BDF，便于 `post()` 阶段回滚。

## 升级中

1. **等待分区空闲**
   执行：
   ```bash
   scgbecli -d <bdf> custom sxe2 upgrdsyncstate versionlineswitch=0
   ```
   轮询输出中的 `run state: 0`，确认当前分区固件已覆盖完成，避免正在分区覆盖时执行升级。
2. **执行升级命令**
   - `scgbecli -d <bdf> upgrade file=<image_path>`
   - 如需跳过版本校验，追加 `noverchk`。
3. **再次轮询分区状态**
   升级命令返回后，继续轮询 `run state`，直到 `run state: 0` 或达到默认 300s 超时。

## 升级后

1. **驱动恢复**
   - 若用例要求重新加载驱动，调用 `CommonOperation.modprobe_driver(driver_name, exec_addr)`。
   - 若用例要求重启服务器，按「网卡测试框架」或「IB模块测试」skill 中的 reboot 检测流程等待上线。
2. **版本校验**
   通过 `scgbecli -d <bdf> show fw` 或 `ethtool -i <iface>` 获取当前版本，与目标版本比对。
3. **设备可见性校验**
   - 以太场景：`ip link show <iface>` 确认接口重新出现。
   - IB/RDMA 场景：`ibstat` / `ibstatus` 确认设备重新出现且状态为 `Active`。
4. **基本业务冒烟**
   - 以太：执行 `ping` 或 `iperf3` 连通性/流量测试。
   - IB/RDMA：执行 `ib_send_bw` 等 perftest 工具验证业务恢复。

## 失败处理

以下情况需按「缺陷自动记录」skill 调用 `create_bug` 或 `CommonOperation.create_bug_problem`：

- **升级命令返回非零**
  - scgbecli：`scgbecli -d <bdf> upgrade ...` 返回 `Status = Failure` 或非零退出码。
  - ethtool：`ethtool_flash` 返回非零。
- **分区同步超时**
  300s 内 `run state` 仍不为 0，报分区覆盖超时 Bug。
- **升级后版本不匹配**
  实际版本与目标版本不一致，报版本校验失败 Bug。
- **设备不可见或链路未恢复**
  升级后接口/device 未重新出现，或业务冒烟失败。

统一使用 `BugTypeEnum.FUNCTION.value`（即 `"功能问题"`）。

## 示例模式

下面给出基于 `cli_operation.py` 与 `common_operation.py` 的完整主机侧升级流程示例，可直接嵌入用例 `do()` 阶段：

```python
import time
from scripts.script_libs.cli_operation import CliOperation, AnalyzeCli
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.file_operation import FileOperation
from scripts.script_libs.enums import BugTypeEnum, CmdExecuteAdressEnum, RtnStatusEnum
from scripts.script_libs import constants, log

# 1. 获取默认升级镜像（根据 BDF 自动匹配设备类型）
bdf = "0000:03:00.0"
exec_addr = CmdExecuteAdressEnum.SERVER.value
image_path = CommonOperation.get_image_upgrade_file_for_bdf(
    bdf_info=bdf,
    exec_addr=exec_addr,
    caller_class=cls,
)
if not image_path:
    cls.bug_result = "未找到与 BDF 对应的升级镜像"
    cls.bug_expect = "应能根据 BDF 自动匹配到 Image 包"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("主机侧固件升级镜像获取失败")

# 2. 确认镜像存在
if RtnStatusEnum.SUCCESS.value != FileOperation.file_path_exists(image_path):
    cls.bug_result = f"升级镜像不存在: {image_path}"
    cls.bug_expect = "升级镜像应存在于指定路径"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("主机侧固件升级镜像不存在")

# 3. 等待分区空闲（避免正在分区覆盖时执行升级）
CliOperation.wait_upgrdsyncstate(
    caller_class=cls,
    device=bdf,
    exec_addr=exec_addr,
)

# 4. 执行 scgbecli 升级
CliOperation.cli_upgrade_fw(
    caller_class=cls,
    device=bdf,
    upgrade_file_path=image_path,
    exec_addr=exec_addr,
)

# 5. 升级命令返回后继续轮询分区同步状态，直到 run state 为 0 或超时
CliOperation.wait_upgrdsyncstate(
    caller_class=cls,
    device=bdf,
    exec_addr=exec_addr,
)

# 6. 重新加载 PF 驱动
CommonOperation.modprobe_driver(
    constants.DRV_SCGBE_PF,
    cmd_execute_address=exec_addr,
)

# 7. 校验版本号是否为目标版本
target_version = "0.6.0.5"
status, fw_info, raw = AnalyzeCli.analyze_dev_show_fw(
    dev_para=bdf,
    exec_addr=exec_addr,
)
current_version = fw_info.get("FW Version", "")
if current_version != target_version:
    cls.bug_result = f"升级后 FW 版本为 {current_version}，不是目标版本 {target_version}"
    cls.bug_expect = f"升级后 FW 版本应为 {target_version}"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("主机侧固件升级后版本校验失败")

# 8. 校验设备是否重新出现
status, dev_info, raw = AnalyzeCli.analyze_dev_show(
    dev_para=bdf,
    exec_addr=exec_addr,
)
link_status = dev_info.get("Link Status", "")
if "up" not in link_status.lower():
    cls.bug_result = f"升级后链路状态为 {link_status}"
    cls.bug_expect = "升级后链路应恢复为 up"
    cls.set_bug_type(BugTypeEnum.FUNCTION.value)
    cls.create_bug("主机侧固件升级后链路未恢复")
```

## 脚本位置建议

- 主机侧固件测试脚本建议放到：`ps3/test/esat/nic100/scripts/nic100/linux/fw/host/`
- 公共库：
  - `ps3/test/esat/nic100/scripts/script_libs/cli_operation.py`
  - `ps3/test/esat/nic100/scripts/script_libs/ethtool_operation.py`
  - `ps3/test/esat/nic100/scripts/script_libs/common_operation.py`

## 注意事项

1. `scgbecli upgrade` 与 `ethtool -f` 通常需要 root 权限。
2. 升级前务必确认镜像与设备型号、sub-device-id 匹配，避免刷写错误镜像。
3. 分区同步状态轮询默认按 5s 间隔、最多 60 次（约 300s）处理；若项目超时策略不同，可按需调整。
4. 升级过程中请勿断电或重启，避免设备变砖。
5. 并发执行多个固件升级用例时，确保目标 BDF/接口互不冲突。
6. `post()` 阶段必须恢复原始版本或分区，除非用例明确允许保留新版本。
