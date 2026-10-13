# RDMA EQ 事件脚本注错方法来源说明

> 本文件说明 `ps3/test/esat/nic100/scripts/nic100/linux/rdma/eq/case_eq/` 下每个 EQ 事件测试脚本的触发方法及其参考来源。

## 事件类型来源

- `EQ事件.png`：定义了 `sxe3r_event_type` 枚举，给出每个事件的 `event_type`（如 `0x4`、`0x31` 等）。
- `天蝎 RDMA异常处理AEQE.xlsx`：给出了 AEQE 事件（`0x30`~`0x34`）的 subtype 含义与注错方法。
- `天蝎 RDMA异常处理MQ.xlsx`：给出了 MQ 命令执行过程中各类 syndrome 的注错方法（部分可作为 WQE/MQ 异常构造参考）。
- `原型验证-异常专项.xls`：给出了大量 TX/RX/RCMS/CQEQ 等模块的异常场景、注错命令和预期 AEQE 事件。
- `异常构造.docx`：给出了 CQ/CEQ/AEQ 异常构造的详细步骤与预期事件。

---

## 脚本与注错方法对照表

| 脚本 | 事件名 | event_type / subtype | 触发方法 | 参考来源 |
|---|---|---|---|---|
| `06_70_005_001_notify_any.py` | `NOTIFY_ANY` | `0x0` / N/A | 先订阅 `NOTIFY_ANY`，再触发一个已知事件（复用 CQ DBR DMA 错误场景：`mw 0x844a205c 0x9d` + 打流） | 触发方法来自 `异常构造.docx` 第 4 条；`NOTIFY_ANY` 机制来自 `EQ事件.png` |
| `06_70_005_002_comm_est.py` | `COMM_EST` | `0x2` / N/A | RC QP 建立连接后由硬件/固件自然上报 | 事件定义来自 `EQ事件.png`；触发逻辑基于 RC 连接建立流程 |
| `06_70_005_003_so_drained.py` | `SO_DRAINED` | `0x3` / N/A | SQ 中所有 WQE 完成后由硬件自然上报 | 事件定义来自 `EQ事件.png`；触发逻辑基于 SQ 排空语义 |
| `06_70_005_004_cq_dbr_dma_err.py` | `CQ_ERROR` | `0x4` / `0x3` | CQ polling + depth=8，注入 `mw 0x844a205c 0x9d`，QP 打流触发 CQ 溢出读 DBR | `异常构造.docx` 第 4 条："读取 CQ DBR 发生 DMA 错误" |
| `06_70_005_005_local_wqe_catastrophic_err.py` | `CATASTROPHIC_ERR` | `0x5` / `0x2` | 启动 rdma_test，注入 `mw 0x844d0024 0x3d`，发送 RDMA Read 请求 | `原型验证-异常专项.xls` 第 4 行："TX_ENG:非重传resp请求出现dma异常" |
| `06_70_005_006_invalid_request_local_wqe_err.py` | `INVALID_REQUEST_LOCAL_WQE_ERR` | `0x10` / N/A | 构造非法 WQE（reserved opcode 等）并下发 | **现有文档中无直接对应注错方法**，基于事件语义与 `MQ` 中 illegal opcode 思路推断，留 TODO |
| `06_70_005_007_local_access_violation_wq_err.py` | `LOCAL_ACCESS_VIOLATION_WQ_ERR` | `0x11` / `0x21` | Responder 侧注入 `mw 0x844a205c 0x85`，Initiator 发起 Read 请求 | `原型验证-异常专项.xls` 第 77 行："T端vapa返回错误" |
| `06_70_005_008_srq_catastrophic_err.py` | `SRQ_CATASTROPHIC_ERR` | `0x12` / N/A | 破坏 SRQ 上下文或异常销毁 SRQ 后收发 | **现有文档中无直接对应注错方法**，基于 SRQ 异常场景推断，留 TODO |
| `06_70_005_009_last_wqe_reached.py` | `LAST_WQE_REACHED` | `0x13` / N/A | SRQ 绑定 QP 上 WQE 处理完毕 / QP 进入 Error 状态 | **现有文档中无直接对应注错方法**，基于 IB/RDMA SRQ 事件语义推断，留 TODO |
| `06_70_005_010_srq_limit.py` | `SRQ_LIMIT` | `0x14` / N/A | 创建 SRQ 并设置 limit，消耗 WQE 至水位以下 | **现有文档中无直接对应注错方法**，基于 IB/RDMA SRQ limit 事件语义推断，留 TODO |
| `06_70_005_011_doorbell_congestion.py` | `DOORBELL_CONGESTION` | `0x1a` / N/A | `mw 0x844c0140 0x8` 后持续高频按 CQ 门铃 | `天蝎 RDMA异常处理AEQE.xlsx` 中 `function_resource_access_error` / `uar_back_pressure_timeout_error` 的按门铃拥塞相关注错方式 |
| `06_70_005_012_context_error.py` | `CONTEXT_ERROR` | `0x30` / `0x1` | `mw 0x8444e114 0xa` 使能 QPC cache 注错，再 `mw 0x844a205c 0xd`，QP 打流 | `原型验证-异常专项.xls` 第 196 行："TX_WQE load qpc 返回错误 DMA Read Error" |
| `06_70_005_013_ceq_error.py` | `CEQ_ERROR` | `0x31` / `0x2` | 创建 CEQ 并绑定 QP/CQ，带流情况下通过 `ibv_destroy_cq`（pyverbs 中 `cq.close()`）销毁 CEQ | `天蝎 RDMA异常处理AEQE.xlsx` 中 `ceq_error` 子类型 `0x2`："销毁 CEQ 前未将绑定的 QP/CQ 排空"；销毁动作使用 `ibv_destroy_cq` |
| `06_70_005_014_function_resource_access_error.py` | `FUNCTION_RESOURCE_ACCESS_ERROR` | `0x32` / `0x1` | `mw 0x844c0140 0x8` + `mw 0x844C4254 0x2`，持续按 CQ 门铃 | `天蝎 RDMA异常处理AEQE.xlsx` 中 `function_resource access_error` 子类型 `0x1` |
| `06_70_005_015_uar_back_pressure_timeout_error.py` | `UAR_BACK_PRESSURE_TIMEOUT_ERROR` | `0x33` / `0x2` | `mw 0x844c0140 0x8` 后持续高频按 CQ 门铃，使主机侧 CQ 门铃 FIFO 溢出 | `天蝎 RDMA异常处理AEQE.xlsx` 中 `uar_back_pressure_timeout_error` 子类型 `0x2` |
| `06_70_005_016_db_proc_error.py` | `DB_PROC_ERROR` | `0x34` / `0x2` | 下发 LL_WQE 长度为 0 并按门铃 | `天蝎 RDMA异常处理AEQE.xlsx` 中 `db_proc_error` 子类型 `0x2`："LLWQE 长度非法" |

---

## 说明

1. **有直接文档支撑**的脚本：`06_70_005_004`、`06_70_005_005`、`06_70_005_007`、`06_70_005_011`~`06_70_005_016`。
2. **基于事件语义/通用 RDMA 行为推断**的脚本：`06_70_005_001`（触发方法有文档，事件语义通用）、`06_70_005_002`、`06_70_005_003`、`06_70_005_006`、`06_70_005_008`~`06_70_005_010`，这些脚本中均留有 `TODO`，需要你根据实际工具（`rdma_test`、`ibv_*`）或硬件注错能力补全。
3. 所有 `event_type` / `event_subtype` 均来自 `EQ事件.png` 和相关 Excel 文档。
