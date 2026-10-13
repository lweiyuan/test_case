# NIC100 固件测试模块 Skill 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `.kimi-code/skills/nic100/` 下创建一套固件测试模块 skill（1 个总览 + 4 个子 skill），覆盖主机侧 NIC 固件与 BMC/PLDM 固件的升级、回滚、校验、恢复等核心测试场景。

**Architecture:** 总览 skill 沉淀通用概念、命令速查、检查清单、失败处理原则；4 个子 skill 分别聚焦主机升级、主机回滚、BMC/PLDM 升级、BMC/PLDM 回滚的动作细节与示例。所有 skill 均为 Markdown 文档，顶部 frontmatter 遵循项目既有 skill 格式。

**Tech Stack:** Markdown, YAML frontmatter; 内容来源于项目既有 Python 脚本（`ethtool_operation.py`, `cli_operation.py`, `common_operation.py`, `scripts/nic100/linux/fw/bmc/`）。

## Global Constraints

- 新增 skill 必须位于 `.kimi-code/skills/nic100/` 下，目录名使用中文，与现有 `以太网模块测试`、`IB模块测试` 等保持一致。
- 每个 `SKILL.md` 顶部必须包含 `name` 和 `description` frontmatter。
- 总览 skill 只放全局通用内容；子 skill 只写本通道+本动作特化内容，避免重复。
- 示例代码/命令必须能从项目代码中找到出处，不虚构命令或路径。
- 不直接修改 `.xlsx` 源文件或现有脚本代码；本次仅新增 skill 文档。
- 示例 Python 代码需通过 `python -m py_compile` 语法检查。
- 文档面向人类测试工程师和 AI 代码生成两者兼顾，关键判断逻辑用中文说明。

---

## File Structure

| File | Responsibility |
|------|----------------|
| `.kimi-code/skills/nic100/固件测试/SKILL.md` | 总览：范围、概念、命令速查、通用检查项、失败处理、子 skill 导航 |
| `.kimi-code/skills/nic100/固件测试/主机侧固件升级/SKILL.md` | 主机侧 NIC 固件升级：sxe2cli/ethtool 升级、镜像校验、状态轮询、升级后验证 |
| `.kimi-code/skills/nic100/固件测试/主机侧固件回滚/SKILL.md` | 主机侧 NIC 固件回滚：分区查询/切换、版本回退、uptime/reset reason 校验、双分区覆盖等待 |
| `.kimi-code/skills/nic100/固件测试/BMC_PLDM固件升级/SKILL.md` | BMC/PLDM 固件升级：BMC 准备、PLDM upgrade、状态机轮询、BMC 重连 |
| `.kimi-code/skills/nic100/固件测试/BMC_PLDM固件回滚/SKILL.md` | BMC/PLDM 固件回滚：回滚触发条件、回滚命令、BMC 重连与日志判断 |

---

### Task 1: Create parent directory and overview skill

**Files:**
- Create: `.kimi-code/skills/nic100/固件测试/SKILL.md`
- Create: `.kimi-code/skills/nic100/固件测试/.gitkeep` (optional, to ensure directory tracks)

**Interfaces:**
- Produces: overview skill with frontmatter `name: 固件测试` and `description: ...`
- Produces: sections covering scope, concepts, command cheat sheet, checklists, failure handling, navigation

- [ ] **Step 1: Create the skill directory**

```bash
mkdir -p .kimi-code/skills/nic100/固件测试
```

- [ ] **Step 2: Write the overview SKILL.md**

Create `.kimi-code/skills/nic100/固件测试/SKILL.md` with this structure:

```markdown
---
name: 固件测试
description: 指导NIC100框架下固件测试的通用规范，覆盖主机侧NIC固件与BMC/PLDM固件的升级、回滚、版本校验、异常恢复和日志检查。
---

# NIC100 固件测试指南

## 测试范围
- 主机侧 NIC 固件（sxe2cli/ethtool 升级、回滚）
- BMC/PLDM 固件（通过 BMC 通道升级、回滚）
- 版本查询与校验
- 升级失败后的环境恢复

## 关键概念
- 主分区 / 备分区（ping-pong 升级）
- EID / UUID（BMC 侧设备识别）
- FW State：`0x31` 表示升级中
- `run state: 0` 表示分区覆盖完成

## 核心命令速查表
| 命令 | 用途 | 适用场景 |
|------|------|----------|
| `ethtool -f <iface> <img>` | 通过 ethtool 刷写固件 | 主机侧通用 |
| `sxe2cli -d <bdf> upgrade file=<path>` | 通过 cli 升级 Image | 主机侧 SXE2/SCGBE |
| `sxe2cli -d <bdf> custom sxe2 upgrdsyncstate versionlineswitch=0` | 查询分区同步状态 | 主机侧回滚 |
| `sxe2cli -d <bdf> custom sxe2 upgrdsyncstate versionlineswitch=1` | 切换启动分区 | 主机侧回滚 |
| `BMC_TOOL_PATH -e <eid> -m 1 -t 5 -c 0 ...` | PLDM 固件升级 | BMC/PLDM |
| `bmc_tool -m 0 -c 0xff --addr=<ip> ...` | 获取 BMC EID 列表 | BMC/PLDM |

## 通用检查项
### 升级前
1. 备份当前版本号与分区信息。
2. 确认升级镜像存在且路径正确。
3. 确认 BMC IP、EID、UUID 已获取（BMC/PLDM 场景）。

### 升级中
1. 轮询升级状态，设置合理超时（如 300s）。
2. 关键命令失败后记录 result/expect 并触发 Bug。

### 升级后
1. 校验版本号是否变为目标版本。
2. 校验链路/设备是否重新出现。
3. 校验基本业务（ping/ibstat/opensm）是否恢复。

## 环境恢复与清理原则
- `post()` 阶段必须恢复原始版本或分区，除非用例明确允许保留新版本。
- 主机侧升级后若需重启，必须等待服务器上线并重新加载驱动。
- BMC/PLDM 升级后必须重新获取 EID 并确认 MCTP 通信正常。

## 失败处理与 Bug 记录
- 升级命令返回非零、版本校验失败、设备不可见、链路未恢复，均需自动提交 Bug。
- 使用 `BugTypeEnum.FUNCTION`。
- 示例模式：
  ```python
  cls.bug_result = "实际结果"
  cls.bug_expect = "期望结果"
  cls.set_bug_type("Function")
  cls.create_bug("详细描述")
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
```

- [ ] **Step 3: Verify frontmatter format**

Run a quick check that the frontmatter parses as YAML:

```bash
python -c "import yaml; print(yaml.safe_load(open('.kimi-code/skills/nic100/固件测试/SKILL.md'))['name'])"
```

Expected output: `固件测试`

- [ ] **Step 4: Commit**

```bash
git add .kimi-code/skills/nic100/固件测试/SKILL.md
git commit -m "docs(skill): add firmware testing overview skill"
```

---

### Task 2: Create host-side firmware upgrade sub-skill

**Files:**
- Create: `.kimi-code/skills/nic100/固件测试/主机侧固件升级/SKILL.md`

**Interfaces:**
- Consumes: overview skill concepts (partitions, version check, post recovery)
- Produces: host upgrade skill with command references from `ethtool_operation.py` and `cli_operation.py`

- [ ] **Step 1: Create the sub-skill directory**

```bash
mkdir -p .kimi-code/skills/nic100/固件测试/主机侧固件升级
```

- [ ] **Step 2: Write the SKILL.md**

Create `.kimi-code/skills/nic100/固件测试/主机侧固件升级/SKILL.md` covering:

```markdown
---
name: 主机侧固件升级
description: 指导NIC100框架下通过sxe2cli或ethtool对主机侧NIC固件进行升级，包括升级前校验、状态轮询和升级后验证。
---

# 主机侧固件升级

## 适用命令

### sxe2cli 升级
```bash
sxe2cli -d <bdf> upgrade file=<image_path>
# 跳过版本校验
sxe2cli -d <bdf> upgrade file=<image_path> noverchk
```

### ethtool 刷写
```python
rtn_code, output, err = EthtoolOperation.ethtool_flash(
    device_name="ens1f0",
    file="/path/to/image.bin",
    region="0",  # optional
    cmd_execute_address=CmdExecuteAdressEnum.SERVER.value,
)
```

## 升级前
1. 查询当前版本：`ethtool -i <iface>` 或 `sxe2cli -d <bdf> show`。
2. 确认镜像存在：使用 `FileOperation.file_path_exists(path)`。
3. 获取镜像路径：参考 `CommonOperation.get_image_upgrade_file_for_bdf(bdf, exec_addr, caller_class)`。

## 升级中
1. 先查询分区同步状态：
   ```bash
   sxe2cli -d <bdf> custom sxe2 upgrdsyncstate versionlineswitch=0
   ```
   等待 `run state: 0` 后再执行升级（避免正在分区覆盖）。
2. 执行升级命令。
3. 轮询 `run state`，直到 `run state: 0` 或超时（默认 300s）。

## 升级后
1. 重新加载驱动或重启服务器（视用例要求）。
2. 校验版本号是否为目标版本。
3. 校验设备是否重新出现在 `ibstat` / `ip link` 中。
4. 执行基本业务冒烟（ping 或 ib_send_bw）。

## 失败处理
- 升级命令返回非零 → 记录 bug_result/bug_expect，调用 `create_bug`。
- 300s 内 `run state` 不为 0 → 报分区覆盖超时 Bug。
- 升级后版本不匹配 → 报版本校验失败 Bug。

## 示例模式
```python
from scripts.script_libs.cli_operation import CliOperation

# 1. 等待分区空闲
CliOperation.wait_upgrdsyncstate(cls, device=bdf, exec_addr=exec_addr)

# 2. 执行升级
CliOperation.cli_upgrade_fw(
    caller_class=cls,
    device=bdf,
    upgrade_file_path=image_path,
    exec_addr=exec_addr,
)

# 3. 升级后恢复
CommonOperation.modprobe_driver(DRV_SCGBE_PF, exec_addr)
# 4. 版本校验 ...
```
```

- [ ] **Step 3: Validate any embedded Python snippets**

```bash
python -m py_compile <<'PY'
# extract only the fenced python block and test syntax
PY
```

For skill docs, manually verify that the Python snippets do not contain syntax errors by reading them.

- [ ] **Step 4: Commit**

```bash
git add .kimi-code/skills/nic100/固件测试/主机侧固件升级/SKILL.md
git commit -m "docs(skill): add host firmware upgrade sub-skill"
```

---

### Task 3: Create host-side firmware rollback sub-skill

**Files:**
- Create: `.kimi-code/skills/nic100/固件测试/主机侧固件回滚/SKILL.md`

**Interfaces:**
- Consumes: overview skill concepts, host upgrade commands
- Produces: host rollback skill with partition switching logic from `cli_operation.py`

- [ ] **Step 1: Create the sub-skill directory**

```bash
mkdir -p .kimi-code/skills/nic100/固件测试/主机侧固件回滚
```

- [ ] **Step 2: Write the SKILL.md**

Create `.kimi-code/skills/nic100/固件测试/主机侧固件回滚/SKILL.md` covering:

```markdown
---
name: 主机侧固件回滚
description: 指导NIC100框架下通过主备分区切换对主机侧NIC固件进行回滚，包括分区查询、切换、重启和回滚后校验。
---

# 主机侧固件回滚

## 关键概念
- 主分区 / 备分区：ping-pong 机制，当前运行分区与待切换分区互为备份。
- `versionlineswitch=0`：查询当前分区状态。
- `versionlineswitch=1`：执行切分区操作。
- `run state: 0`：分区空闲；`run state: 1`：分区覆盖中。

## 分区查询
```python
state = CliOperation.get_upgrade_syncstate_info(
    bus_info=bdf,
    caller_class=cls,
    switch_info="0",
    exec_addr=exec_addr,
)
# state 包含：run_state, switch_state, fw_flash_flag, boot_flash_flag, open_state
```

## 切换分区
```python
CliOperation.change_flash_flag(
    bus_info=bdf,
    caller_class=cls,
    exec_addr=exec_addr,
)
```

切换后需要重启服务器，使固件从另一分区启动。

## 回滚后校验
1. 通过 `custom sxe2 fwinfo` 获取 `uptime`，验证重启时间是否合理。
2. 通过 `NIC RST CAUSE` 验证启动原因是否符合预期。
3. 通过 `ethtool -i <iface>` 或 `sxe2cli -d <bdf> show` 校验版本是否回到旧版本。
4. 校验设备是否重新出现，链路是否恢复。

## 双分区覆盖等待
执行 `change_flash_flag` 后，如果 `custom sxe2 upgrdsyncstate` 显示 `run state: 1`，需要循环等待，直到 `run state: 0` 或超时。

## 失败处理
- 切分区命令执行失败，或 `switch_state` 未变为 1 → 报 Bug。
- 重启后 uptime 异常（过大或过小）→ 报 Bug。
- 版本未回退到预期 → 报 Bug。
```

- [ ] **Step 3: Commit**

```bash
git add .kimi-code/skills/nic100/固件测试/主机侧固件回滚/SKILL.md
git commit -m "docs(skill): add host firmware rollback sub-skill"
```

---

### Task 4: Create BMC/PLDM firmware upgrade sub-skill

**Files:**
- Create: `.kimi-code/skills/nic100/固件测试/BMC_PLDM固件升级/SKILL.md`

**Interfaces:**
- Consumes: overview skill concepts, BMC/PLDM tooling from `scripts/nic100/linux/fw/bmc/`
- Produces: BMC/PLDM upgrade skill with EID/UUID matching and state polling

- [ ] **Step 1: Create the sub-skill directory**

```bash
mkdir -p .kimi-code/skills/nic100/固件测试/BMC_PLDM固件升级
```

- [ ] **Step 2: Write the SKILL.md**

Create `.kimi-code/skills/nic100/固件测试/BMC_PLDM固件升级/SKILL.md` covering:

```markdown
---
name: BMC_PLDM固件升级
description: 指导NIC100框架下通过BMC通道和PLDM协议对网卡BMC侧固件进行升级，包括EID/UUID匹配、镜像传输和状态机轮询。
---

# BMC/PLDM 固件升级

## 环境准备
1. 获取 BMC IP：`CommonTools.get_bmc_ip(execute_addr)`。
2. 获取 BMC EID 列表：`CommonTools.get_bmc_eid_list(ip, execute_addr)`。
3. 通过 UUID 将网卡 BDF 与 BMC EID 对应：`CommonTools.get_env_bmc_eid_info(test_device_info_list)`。

## 镜像传输
升级前需将镜像文件拷贝到 BMC `/var/` 目录并重命名为 `image.pldm`：

```bash
sshpass -p <pwd> scp <pkg_path> <user>@<bmc_ip>:/var/
sshpass -p <pwd> ssh <user>@<bmc_ip> 'cd /var/; mv <pkg_name> image.pldm'
```

## PLDM 升级命令
```bash
BMC_TOOL_PATH -e <eid> -m 1 -t 5 -c 0 --addr=<bmc_ip> --name=<bmc_user> --passwd=<bmc_pwd> -d <skip_ip>
```

## 状态机轮询
升级过程中固件状态为 `0x31`（升级中）。通过 `CommonTools.get_soc_fw_state(eid, execute_addr)` 轮询，直到状态不再是 `0x31` 或超时（如 50 分钟）。

## 升级后
1. 等待 BMC 重连（ping BMC IP）。
2. 重新获取 EID。
3. 通过 `PldmTool.get_uuid` 或 `CliOperation.get_cli_show_fw_info` 校验版本。
4. 确认 MCTP 通信正常。

## 失败处理
- 获取 EID 失败 → 先尝试 `MctpTools.restart_mctp_service`，仍失败则报 Bug。
- 状态持续为 `0x31` 超过超时时间 → 报升级失败 Bug。
- BMC 升级后无法重连 → 报 BMC 恢复失败 Bug。
```

- [ ] **Step 3: Commit**

```bash
git add .kimi-code/skills/nic100/固件测试/BMC_PLDM固件升级/SKILL.md
git commit -m "docs(skill): add bmc-pldm firmware upgrade sub-skill"
```

---

### Task 5: Create BMC/PLDM firmware rollback sub-skill

**Files:**
- Create: `.kimi-code/skills/nic100/固件测试/BMC_PLDM固件回滚/SKILL.md`

**Interfaces:**
- Consumes: overview skill concepts, BMC/PLDM upgrade commands
- Produces: BMC/PLDM rollback skill with BMC reconnect and log checking

- [ ] **Step 1: Create the sub-skill directory**

```bash
mkdir -p .kimi-code/skills/nic100/固件测试/BMC_PLDM固件回滚
```

- [ ] **Step 2: Write the SKILL.md**

Create `.kimi-code/skills/nic100/固件测试/BMC_PLDM固件回滚/SKILL.md` covering:

```markdown
---
name: BMC_PLDM固件回滚
description: 指导NIC100框架下对BMC/PLDM固件进行回滚，包括回滚触发条件、命令执行、BMC重连和回滚后校验。
---

# BMC/PLDM 固件回滚

## 回滚触发条件
- 升级后版本校验失败。
- 升级后 BMC 无法正常通信。
- 用例明确要求验证回滚流程。

## 回滚命令
BMC/PLDM 回滚通常通过再次下发 PLDM upgrade 命令，使用旧版本镜像实现；部分平台支持 BMC 侧自带的回滚指令。命令形式与升级相同：

```bash
BMC_TOOL_PATH -e <eid> -m 1 -t 5 -c 0 --addr=<bmc_ip> --name=<bmc_user> --passwd=<bmc_pwd>
```

## 回滚后等待
1. 固件重启后等待 BMC IP 可 ping 通（通常 15s 起步）。
2. 重新获取 EID 列表。
3. 若单 EID 无法通信，尝试 `CommonTools.reboot_bmc(ip, execute_addr)` 后重新获取。

## 回滚后校验
1. 通过 `PldmTool.get_uuid` 校验 UUID 与之前一致。
2. 通过 `PldmTool.get_state_sensor_reading` 校验关键 sensor 状态。
3. 检查 BMC 日志中是否有异常错误关键字（如 `ERROR`、`FAIL`）。

## 失败处理
- 回滚命令失败 → 记录 result/expect 并调用 `create_bug`。
- 回滚后 BMC 无法重连 → 尝试 reboot BMC，仍失败则报 Bug。
- 回滚后版本仍不符合预期 → 报版本校验失败 Bug。
```

- [ ] **Step 3: Commit**

```bash
git add .kimi-code/skills/nic100/固件测试/BMC_PLDM固件回滚/SKILL.md
git commit -m "docs(skill): add bmc-pldm firmware rollback sub-skill"
```

---

### Task 6: Validate all skills

**Files:**
- Read: all 5 `SKILL.md` files created above

**Interfaces:**
- Consumes: all created skill files
- Produces: validation report (pass/fail)

- [ ] **Step 1: Check frontmatter on all skills**

```bash
for f in .kimi-code/skills/nic100/固件测试/SKILL.md \
         .kimi-code/skills/nic100/固件测试/主机侧固件升级/SKILL.md \
         .kimi-code/skills/nic100/固件测试/主机侧固件回滚/SKILL.md \
         .kimi-code/skills/nic100/固件测试/BMC_PLDM固件升级/SKILL.md \
         .kimi-code/skills/nic100/固件测试/BMC_PLDM固件回滚/SKILL.md; do
  echo "=== $f ==="
  python -c "import yaml,sys; d=yaml.safe_load(open('$f')); print(d['name'], '-', d['description'])"
done
```

Expected: each prints its name and description without error.

- [ ] **Step 2: Check for placeholder text**

```bash
grep -R "TBD\|TODO\|待补充\|implement later\|fill in details" .kimi-code/skills/nic100/固件测试/ || echo "No placeholders found"
```

Expected: `No placeholders found`

- [ ] **Step 3: Verify Python snippets compile**

Extract fenced Python blocks and run `py_compile`:

```bash
python <<'PY'
import re, py_compile, tempfile, os
files = [
    '.kimi-code/skills/nic100/固件测试/主机侧固件升级/SKILL.md',
    '.kimi-code/skills/nic100/固件测试/主机侧固件回滚/SKILL.md',
    '.kimi-code/skills/nic100/固件测试/BMC_PLDM固件升级/SKILL.md',
    '.kimi-code/skills/nic100/固件测试/BMC_PLDM固件回滚/SKILL.md',
]
for path in files:
    with open(path, encoding='utf-8') as f:
        text = f.read()
    blocks = re.findall(r'```python\n(.*?)\n```', text, re.S)
    for i, code in enumerate(blocks):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tmp:
            tmp.write(code)
            tmp_name = tmp.name
        try:
            py_compile.compile(tmp_name, doraise=True)
            print(f"OK: {path} block {i+1}")
        finally:
            os.unlink(tmp_name)
PY
```

Expected: all blocks print `OK`.

- [ ] **Step 4: Final commit**

```bash
git add docs/superpowers/plans/2026-06-18-firmware-module-plan.md
git commit -m "docs(plan): add firmware module skill implementation plan"
```

---

## Schedule & Dependencies

| Task | Dependencies | Estimated Effort |
|------|--------------|------------------|
| Task 1: Overview skill | none | 30 min |
| Task 2: Host upgrade skill | Task 1 | 30 min |
| Task 3: Host rollback skill | Task 1, Task 2 | 30 min |
| Task 4: BMC/PLDM upgrade skill | Task 1 | 30 min |
| Task 5: BMC/PLDM rollback skill | Task 1, Task 4 | 30 min |
| Task 6: Validation | Task 2-5 | 20 min |

**Total estimated effort:** ~2.5 hours

**Critical path:** Task 1 → Tasks 2-5 (parallelizable) → Task 6

---

## Execution Options

**Plan complete and saved to `docs/superpowers/plans/2026-06-18-firmware-module-plan.md`.**

Two execution options:

1. **Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach do you prefer?
