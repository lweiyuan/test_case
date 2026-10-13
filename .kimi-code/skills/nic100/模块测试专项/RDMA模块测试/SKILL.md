---
name: RDMA模块测试
description: 指导NIC100框架下RDMA模块的测试要点，包括RDMA EQ异常事件、MQ复位故障注入、pyverbs/ibv接口使用、设备映射、server端inline执行和常见API踩坑。
---

# NIC100 RDMA 模块测试指南

## 测试范围

- RDMA 设备识别与状态检查
- RDMA EQ（Event Queue）异常事件测试
- pyverbs / ibv 接口编程与调试
- netdev 与 rdma 设备名映射
- server 端 inline Python 执行技巧
- 异步事件检查与 dmesg 日志分析

## 核心术语

| 术语 | 说明 |
|------|------|
| **EQ** | Event Queue，事件队列，用于上报 RDMA 异步事件 |
| **AEQ** | Async Event Queue，异步事件队列 |
| **CEQ** | Completion Event Queue，完成事件队列 |
| **CQ** | Completion Queue，完成队列 |
| **QP** | Queue Pair，队列对 |
| **PD** | Protection Domain，保护域 |
| **MR** | Memory Region，内存区域 |
| **netdev** | 内核网络设备名，如 `ibs4f0` |
| **rdma dev** | RDMA 子系统设备名，如 `mlx5_0` |

## 脚本位置

- 模块脚本：`ps3/test/esat/nic100/scripts/nic100/linux/rdma/`
- EQ 事件用例：`ps3/test/esat/nic100/scripts/nic100/linux/rdma/eq/case_eq/`
- 公共库：`ps3/test/esat/nic100/scripts/script_libs/`

---

## EQ 异常事件测试

### 用例编号规则

沿用项目编号体系：

```
nic_linux_rdma_f_<平台编号>_<子模块编号>_<功能项>_<检查点>
```

示例：`06_70_005_013` 表示 RDMA EQ 异常事件测试中的 CEQ 错误场景。

### 脚本结构

- 继承 `scripts.script_libs.script_base.ScriptBase`
- 重写 `set_parameters`、`check_own_environment`、`prepare`、`do`、`post`
- 类名使用 PascalCase
- 文件头包含 case number、case title、author、steps、expected

### 触发 EQ 事件的典型思路

1. 创建 RDMA 资源（Context、PD、CQ、QP、MR）
2. 建立 QP 连接（INIT -> RTR -> RTS）
3. 打一笔流
4. 在不消费完成事件的情况下，主动销毁/修改某个资源，触发异常事件
5. 检查 dmesg / 驱动日志中是否上报预期 event_type / event_subtype

### 事件校验

通常从 dmesg 中抓取：

```python
status, output, _ = CommandOperation.execute_command_with_error(
    "dmesg | tail -n 200",
    CmdExecuteAdressEnum.SERVER.value,
)
# 正则匹配 event_type / event_subtype
```

---

## netdev 与 rdma 设备名映射

配置中读取到的通常是 netdev（如 `ibs4f0`），但 pyverbs/ibv 需要 rdma 设备名（如 `mlx5_0`）。

在 server 端执行：

```bash
rdma link -jp
```

返回 JSON 中每个 entry 形如：

```json
{"ifname": "mlx5_0/1", "netdev": "ibs4f0", ...}
```

匹配 `netdev == pf_if` 后，取 `ifname.split('/')[0]` 即为 rdma 设备名。

```python
import json
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.enums import CmdExecuteAdressEnum

def get_rdma_dev_name(netdev: str, default: str = "mlx5_0") -> str:
    status, output, err = CommandOperation.execute_command_with_error(
        "rdma link -jp",
        CmdExecuteAdressEnum.SERVER.value,
        timeout=30,
    )
    if status != 0 or not output.strip():
        return default
    try:
        links = json.loads(output)
        if not isinstance(links, list):
            links = [links]
        for link in links:
            if link.get("netdev") == netdev:
                ifname = link.get("ifname", "")
                rdma_dev = ifname.split("/")[0] if "/" in ifname else ifname
                if rdma_dev:
                    return rdma_dev
    except json.JSONDecodeError:
        pass
    return default
```

---

## server 端 inline 执行 Python

### 场景

需要在 server 端执行一段 Python（如调用 pyverbs），但不想生成 `/tmp/xxx.py` 临时文件。

### 避坑：SSH 外层双引号冲突

`CommandOperation.execute_command_with_error` 远程执行时会把命令用 `SSH_PREFIX` 包成：

```bash
ssh ... "python3 - <<'PY'
print("hello")
PY"
"
```

代码里的双引号会和 SSH 外层双引号冲突，导致命令被截断，出现 `invalid syntax` 等错误。

### 推荐方案：base64 编码后执行

```python
import base64

test_script = """..."""  # 要执行的 Python 代码字符串
encoded_script = base64.b64encode(test_script.encode("utf-8")).decode("utf-8")

CommandOperation.execute_command_with_error(
    f"printf '%s' '{encoded_script}' | base64 -d | python3 -",
    CmdExecuteAdressEnum.SERVER.value,
    timeout=120,
)
```

优点：
- 不生成临时文件
- base64 内容放在单引号内，不会和 SSH 外层双引号冲突
- inline 代码里可正常使用双引号、`%` 格式化等

---

## pyverbs 常见 API 误用

以下均来自 `临时文件夹/pyverbs/` 源码核对。

### 1. 设备发现

不要硬编码 `mlx5_0`，优先用 `rdma_get_devices()`：

```python
from pyverbs import device

dev_list = device.rdma_get_devices()
if not dev_list:
    raise RuntimeError("no rdma devices found")
dev = dev_list[0]
name = dev.name.decode("utf-8") if isinstance(dev.name, bytes) else dev.name
ctx = device.Context(name=name)
```

### 2. QPInitAttr 参数名

`QPInitAttr.__init__` 的参数是 `scq`/`rcq`，**不是** `send_cq`/`recv_cq`：

```python
from pyverbs import qp, enums

init_attr = qp.QPInitAttr(
    qp_type=enums.ibv_qp_type.IBV_QPT_RC.value,
    qp_context=ctx,
    scq=send_cq,      # 正确
    rcq=recv_cq,      # 正确
    cap=cap,
    sq_sig_all=0,
)
```

### 3. QPAttr 字段通过属性设置

`QPAttr.__init__` 只接受 `qp_state`、`cur_qp_state`、`port_num`、`path_mtu`。其它字段必须创建对象后再赋值：

```python
# INIT
init_attr_obj = qp.QPAttr(qp_state=enums.ibv_qp_state.IBV_QPS_INIT.value)
init_attr_obj.pkey_index = 0
init_attr_obj.port_num = PORT_NUM
init_attr_obj.qp_access_flags = access_flags
local_qp.to_init(init_attr_obj)

# RTR
rtr_attr = qp.QPAttr(
    qp_state=enums.ibv_qp_state.IBV_QPS_RTR.value,
    path_mtu=enums.ibv_mtu.IBV_MTU_1024.value,
)
rtr_attr.ah_attr = ah_attr
rtr_attr.dest_qp_num = remote_qp.qp_num
rtr_attr.rq_psn = 0
rtr_attr.max_dest_rd_atomic = 1
rtr_attr.min_rnr_timer = 12
local_qp.to_rtr(rtr_attr)

# RTS
rts_attr = qp.QPAttr(qp_state=enums.ibv_qp_state.IBV_QPS_RTS.value)
rts_attr.sq_psn = 0
rts_attr.timeout = 14
rts_attr.retry_cnt = 7
rts_attr.rnr_retry = 7
rts_attr.max_rd_atomic = 1
local_qp.to_rts(rts_attr)
```

### 4. WR 必须显式指定 num_sge

`RecvWR` 和 `SendWR` 都需要 `num_sge`：

```python
from pyverbs import wr

recv_wr = wr.RecvWR(wr_id=1, num_sge=1, sg=[recv_sge])
send_wr = wr.SendWR(
    opcode=enums.ibv_wr_opcode.IBV_WR_SEND.value,
    wr_id=2,
    num_sge=1,
    sg=[send_sge],
)
```

缺 `num_sge` 会报：`PyverbsUserError: A WR needs at least one SGE`。

### 5. CQ.poll() 参数

`CQ.poll(timeout=5)` 是错误的。`poll` 只接受 `num_entries`：

```python
import time

def poll_cq(cq_obj, max_retries=50, sleep_sec=0.1):
    for _ in range(max_retries):
        npolled, wcs = cq_obj.poll(num_entries=1)
        if npolled > 0:
            return npolled, wcs
        time.sleep(sleep_sec)
    return 0, []
```

### 6. 枚举常量使用 .value

pyverbs 示例中，枚举通常带 `.value`：

```python
enums.ibv_qp_type.IBV_QPT_RC.value
enums.ibv_qp_state.IBV_QPS_INIT.value
enums.ibv_mtu.IBV_MTU_1024.value
enums.ibv_wr_opcode.IBV_WR_SEND.value
enums.ibv_access_flags.IBV_ACCESS_LOCAL_WRITE.value
```

### 7. MR 内存写入

推荐用 `MR` 自动分配内存 + `write()`，避免手动 `mem_alloc`：

```python
from pyverbs import mr

send_mr = mr.MR(creator=pd_obj, length=buf_size, access=access_flags, address=None)
recv_mr = mr.MR(creator=pd_obj, length=buf_size, access=access_flags, address=None)
send_mr.write(data=b"A" * buf_size, length=buf_size, offset=0)
```

---

## 质量检查清单

生成/修改 RDMA/pyverbs 相关脚本后确认：

- [ ] 主脚本 `python -m py_compile` 通过
- [ ] 提取生成的 server 端 inline 脚本，再次 `python -m py_compile` 通过
- [ ] 若 inline 代码含双引号，必须使用 base64 或确保不会和 SSH 外层引号冲突
- [ ] pyverbs API 参数和源码示例一致（`scq`/`rcq`、`.value`、`num_sge`、属性 setter 等）
- [ ] 错误时调用 `create_bug` 记录缺陷
- [ ] 如需清理，确保 `post` 阶段删除 server 端临时文件

---

## 参考文件

- pyverbs 源码：`临时文件夹/pyverbs/`
- pyverbs 示例：`临时文件夹/pyverbs/examples/`
- EQ 脚本示例：`ps3/test/esat/nic100/scripts/nic100/linux/rdma/eq/case_eq/06_70_005_013_ceq_error.py`
- MQ 脚本目录：`nic800/linux/rdma/mq/script_case/`
- MQ 公共基类：`nic800/linux/rdma/mq/script_case/script_base_mq_ai.py`

---

# EQ 异常事件测试技巧

> 从 `nic100/linux/rdma/eq/` 与 `06_70_005_xxx` 系列用例中沉淀的实战技巧。

## 1. 事件触发三段式

EQ 异常事件一般按"建链 -> 打流 -> 破坏资源"触发：

```text
1. 创建 RDMA 资源（Context / PD / CQ / QP / MR）
2. 建立 QP 连接（INIT -> RTR -> RTS）
3. 打一笔流（让 CQ/QP 进入活跃态）
4. 在不消费完成事件的情况下，主动销毁/修改某个资源，触发异常事件
5. 从 dmesg / 驱动日志抓取预期 event_type / event_subtype
```

要点：
- **不消费 CQE** 是关键。多数 CEQ 错误靠"资源已销毁但 CQE 未回收"触发。
- 破坏动作要在 server 端 inline（见下文）或 `execute_command_with_error` 完成。

## 2. 日志抓取与事件前后对比

不要只 grep 关键字是否存在，要做**前后数量对比**，避免把历史日志误判为本次触发：

```python
def count_event(keyword: str) -> int:
    bash = (
        f"cnt=0; "
        f"cnt=$((cnt + $(dmesg 2>/dev/null | grep -icE '{keyword}' | head -1 || echo 0))); "
        f"cnt=$((cnt + $(cat /var/log/sxe3_drv_rdma.log* 2>/dev/null | grep -icE '{keyword}' | head -1 || echo 0))); "
        f"echo \"EVENT_CNT=$cnt\""
    )
    status, output, _ = CommandOperation.execute_command_with_error(bash, CmdExecuteAdressEnum.SERVER.value)
    for line in output.splitlines():
        if line.strip().startswith("EVENT_CNT="):
            return int(line.strip().split("=", 1)[1])
    return 0

before = count_event("CEQ Error")
# ... 触发动作 ...
after = count_event("CEQ Error")
assert after > before, "未检测到新的 CEQ Error 事件"
```

## 3. server 端 inline 执行的坑

EQ 场景常在 server 端跑一段 Python（pyverbs）。**不要**直接拼带双引号的 Python 字符串到 SSH 命令里，会和 SSH 外层双引号冲突。

推荐 base64 编码（详见上文"server 端 inline 执行 Python"）：

```python
import base64
encoded = base64.b64encode(py_code.encode("utf-8")).decode("utf-8")
CommandOperation.execute_command_with_error(
    f"printf '%s' '{encoded}' | base64 -d | python3 -",
    CmdExecuteAdressEnum.SERVER.value, timeout=120,
)
```

---

# MQ 复位故障注入测试技巧

> 从 `nic800/linux/rdma/mq/script_case/nic_linux_rdma_mq_r_06_72_008_001~019` 系列用例中沉淀的实战技巧。
> 核心目标：通过用户态工具 / 驱动加载参数注入 MQ 故障，断言驱动上报对应错误且**不触发 NIC 复位**。

## 1. 两种故障注入模式

| 模式 | 触发方式 | 适用用例 |
|------|----------|----------|
| `sbash` | 主机侧 sbash 壳中执行 `sxe3r_test_*` 用户态工具 | 004-013, 015-016, 018-019 |
| `insmod_ko` | 加载驱动时注入错误 ko 参数（`mq_test_insert_ko`），靠驱动日志断言 | 001-003, 014, 017 |

- `sbash` 模式需在注入前启动 sbash 测试壳（加载 `kdsh.ko` 并常驻 `./sbash`）。
- `insmod_ko` 模式先 `rmmod` 再 `insmod /root/sxe3_rdma.ko <错误参数>`，再读日志。
- `018` 为组合模式：先 `insmod` 错误参数，再在 sbash 中跑 `sxe3r_test_mw`。

## 2. 公共基类 `ScriptBaseMqAi`（重要）

为避免 19 个脚本重复，已提取公共基类 `script_base_mq_ai.py`。子类只需：

```python
import add_syspath
from script_base_mq_ai import ScriptBaseMqAi

class Nic0672008007MqCtxIdCheckFail(ScriptBaseMqAi):
    INJECT_MODE = "sbash"          # 或 "insmod_ko"
    PF_DEV = "sxe3_rdma0"
    EXPECT_RETVAL = "-5"           # insmod_ko 类可置空（不校验 retval）
    EXPECT_KEYWORDS = ["CTX ID Check Fail", "maj=0X19"]
    LOG_EVENT_KEYWORD = "CTX ID Check Fail"
    BUG_EXPECT_DESC = "访问未创建 QP 的 QPC 时，驱动应上报 CTX ID Check Fail，不触发复位"

    @classmethod
    def _inject_fault(cls) -> str:
        # 返回命令/日志输出字符串；基类 _check_result 据此做 retval/数量/复位判断
        return cls._run_in_sbash(f"sxe3r_test_qp_query_error {cls.PF_DEV} 10 0")
```

基类已固化：
- 生命周期 `set_parameters` / `check_own_environment` / `prepare` / `do`（`do` 在 `sbash` 模式自动 `_init_sbash()`）
- `_run_remote_bash` / `_init_sbash` / `_run_in_sbash` / `_reload_with_ko_param`
- `_get_event_count`（dmesg + `/var/log/sxe3_drv_rdma.log*` 前后对比）
- `_check_result`：retval 命中 **或** 关键字命中 **或** 事件数量增加，且**未触发复位**
- `_bug_and_raise`（用 `BUG_EXPECT_DESC` 填充 `bug_expect`）

子类可覆写 `post` 做驱动恢复（insmod_ko 类必须恢复为正常参数重新加载）。

## 3. sbash 启动标准写法

```python
init_bash = (
    f"chmod +x {SBASH_BIN}; "
    f"lsmod | grep -q kdsh || insmod {KDSH_KO}; "
    f"pgrep -f '{SBASH_BIN}' >/dev/null 2>&1 || "
    f"nohup {SBASH_BIN} >/dev/null 2>&1 & "
    f"sleep 2; echo INIT_DONE"
)
```

要点：
- `kdsh.ko` 只需加载一次（`lsmod | grep -q kdsh || insmod`）。
- `sbash` 是常驻壳，用 `nohup ... &` 后台运行，避免在远程 shell 阻塞。
- 用户态工具命令统一用 `CommandOperation.execute_command_based_paramiko_with_rtncode(cmd, SERVER, timeout=120)`，并在命令末尾拼接 `; echo "RETVAL=$?"` 以取返回值。

## 4. 结果校验四要素（必须全部满足）

```text
1. retval 命中 EXPECT_RETVAL（sbash 类）  或  日志关键字命中（insmod_ko 类）
2. dmesg / /var/log/sxe3_drv_rdma.log* 出现 EXPECT_KEYWORDS 之一
3. 事件数量：测试后 LOG_EVENT_KEYWORD 计数 > 测试前计数
4. 未触发 NIC 复位（日志不含 "trigger core reset" / "core reset" / "NIC reset"）
```

基类 `_check_result` 已把 1/3/4 自动化；insmod_ko 类靠 2/3 判定（retval 置空）。

## 5. sxe3r_test_* 工具 → maj 错误码映射表

| 故障点 | 用户态工具命令 | 期望 retval | maj |
|--------|----------------|-------------|-----|
| SQ Size Illegal (size=0) | `insmod` 错误参数 | - | 0X10 |
| SQ Size Illegal (>10) | `insmod` 错误参数 | - | 0X11 |
| MQC Not Created | `insmod` 错误参数 | - | 0X12 |
| Unsupported Opcode | `sxe3r_test_opcode <dev> 0xc` | -5 | 0X13/0X14 |
| Resize CQ Fail | `sxe3r_test_resize_cq_error <dev>` | -12 | 0X17 |
| UID Check Fail | `sxe3r_test_qp_query_error <dev> 1 255` | -5 | 0X18 |
| CTX ID Check Fail | `sxe3r_test_qp_query_error <dev> 10 0` | -5 | 0X19 |
| Invalid RoCE QPN | `sxe3r_test_qp_query_error <dev> 0 0` | -5 | 0X20 |
| Unsupported QP State Jump | `sxe3r_test_query_qp_rc_error <dev> 0` | -5 | 0X21 |
| Context Format Error | `sxe3r_test_set_qp_type <dev> 8` + `sxe3r_test_query_qp_rc <dev>` | -5 | 0X22 |
| QP Already Been Destroyed | `sxe3r_test_query_qp_rc <dev> 0`(取 qpn) + `sxe3r_test_qp_destroy2 <dev> <qpn>` | -5 | 0X24 |
| Invalid Qset ID | `sxe3r_test_qset_dereg <dev> {3,32,63}` | -5 | 0X30 |
| Invalid Qcounter index | `sxe3r_test_qcounter_dereg/_query <dev> {100,1000}` | -12 | 0X31 |
| Create MMQ Fail | `insmod` 错误参数 | - | 0X32 |
| Invalid Access Rights | `sxe3r_test_mr_set_mr_access_right <dev> 1` + `sxe3r_test_mr <dev>` | -5 | 0X40 |
| Invalid MRC_Type on Reg MR | `sxe3r_test_mr_set_mrc_type <dev> 1` + `sxe3r_test_mr <dev>` | -5 | 0X41 |
| Illegal MR Page Size | `insmod` 错误参数 | - | 0X42 |
| Invalid UMR_en on Allocate MR Key | `insmod` 错误参数 + `sxe3r_test_mw <dev>` | -5 | 0X43 |
| Deallocate a Valid MR | `sxe3r_test_mr_2 <dev>` | -5 | 0X44 |

> 注：`insmod` 错误参数对应原型 `mq_test_insert_ko=insert_ko_str_err_xx`，该字符串在仓库外不可见；
> 若编译宏已内置，子类把 `KO_ERR_PARAM` 置空即可按正常参数加载触发。

## 6. 用例编号与 Excel 约定

- 编号体系：`nic_linux_rdma_mq_r_06_72_008_0XX`
- 测试步骤与预期结果必须**一一对应**（每一步骤都有对应预期），Excel 校验脚本按行拆分后对比条目数。
- 公共基类路径需加入 `sys.path`（通过 `add_syspath` 模块），子类 `from script_base_mq_ai import ScriptBaseMqAi` 方可解析。

## 7. MQ 脚本质量检查清单

生成/修改 MQ 用例脚本后确认：

- [ ] `python -m py_compile` 通过
- [ ] 继承 `ScriptBaseMqAi`，仅实现 `_inject_fault()`，共性逻辑不重复写
- [ ] `INJECT_MODE` 与注入方式一致（sbash / insmod_ko）
- [ ] `LOG_EVENT_KEYWORD` / `EXPECT_KEYWORDS` / `BUG_EXPECT_DESC` 已按映射表填写
- [ ] insmod_ko 类必须覆写 `post` 恢复驱动为正常参数加载
- [ ] 测试步骤与预期结果数量一致（Excel 侧校验）
- [ ] 断言包含"未触发 NIC 复位"
