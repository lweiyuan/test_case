# RDMA EQ 事件测试用例示例

基于 `xmind文件夹/EQ事件.png` 中的事件类型，选取 **`SXE3R_EVENT_TYPE_CQ_ERROR = 0x4`**，子类型 `0x3`（读取 CQ DBR 发生 DMA 错误）作为示例。

> 注错方法来源：`xmind文件夹/异常构造.docx` 第 4 条。

---

## 1. Excel 18 列用例示例

| 序号 | 字段 | 示例值 |
|---|---|---|
| 1 | 所属产品 | NIC100 |
| 2 | 所属模块 | RDMA-异常 |
| 3 | 优先级 | A1 |
| 4 | 用例类型 | f |
| 5 | 脚本名称 | `ps3/test/esat/nic100/scripts/nic100/linux/rdma/eq/case_eq/06_70_005_004_cq_dbr_dma_err.py` |
| 6 | 测试编号 | `06_70_005_004` |
| 7 | 用例标题 | RDMA_EQ事件_CQ DBR DMA错误 |
| 8 | 前提条件 | 1. NIC100 RDMA 驱动（sxe3_rdma 等）已加载<br>2. 存在可用于测试的 PF 端口<br>3. `/sys/kernel/debug/sxe3_rdma/$BDF/` 可写<br>4. `rdma_test` 工具可用 |
| 9 | 测试步骤 | 1. 配置 CQ 为 polling 模式，CQ 深度设置为 8<br>2. 注入 DMA 错误：`mw 0x844a205c 0x9d`<br>3. 使用 `rdma_test` 创建 QP 并持续打流，使 CQ 溢出并触发 DBR 读取<br>4. 查看驱动日志 / sysfs 异步事件 / dmesg |
| 10 | 预期结果 | 1. 收到一笔 CQ 错误异步事件，`event_type = 0x4`，`event_subtype = 0x3`<br>2. 驱动不 panic、不死机<br>3. 事件内容与注入场景一致 |
| 11 | 检查项/测试点 | CQ DBR DMA 错误事件正确上报 |
| 12 | 测试场景 | RDMA 异常事件处理 |
| 13 | 用例测试分类 | 系统测试-功能 |
| 14 | 负责人 | liuchang6 |
| 15 | 作者 | liuchang6 |
| 16 | 测试平台实现自动化 | Linux |
| 17 | 需求点/测试对象 | RDMA EQ 事件处理 |
| 18 | 物理环境 | 单机 / 双机 NIC100 网卡 |

---

## 2. 关键注错命令说明

```bash
# 1. 确认 CQ 为 polling 模式、深度为 8
#    通过 rdma_test 配置文件或驱动参数设置：
#    cq_num_poll = 1
#    cq_depth    = 8

# 2. 注入 DMA 错误（对 RDMA_DMA 寄存器 0x844a205c 写 0x9d）
mw 0x844a205c 0x9d

# 3. 创建 QP 并打流（示例）
rdma_test -c srq_cfg_b1_depth16_rqe32_qp4.txt
rdma_test -c srq_cfg_b1_depth16_rqe32_qp4.txt -s 127.0.0.1
```

---

## 3. 预期异步事件格式

```c
// 事件类型来自 sxe3r_event_type 枚举
SXE3R_EVENT_TYPE_CQ_ERROR = 0x4

// 子类型/细节（来自异常构造.docx）
// 0x3：读取 CQ DBR 发生 DMA 错误
```

---

## 4. Python 脚本示例（NIC100 框架风格）

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case number: 06_70_005_004
case title: RDMA_EQ事件_CQ DBR DMA错误
test category: RDMA 异常事件测试
check point: CQ DBR DMA 错误时正确上报 event_type=0x4/subtype=0x3
author: liuchang6
date: 2026.08.03
"""

import re
import time
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum, BugTypeEnum
from scripts.script_libs.script_base import ScriptBase, SxeException


class Nic06700005004CqDbrDmaErr(ScriptBase):
    test_object = "RDMA EQ 异常事件测试"
    test_module = "rdma_eq"
    test_tool = "rdma_test, mw, debugfs"
    test_precondition = """1. RDMA 驱动已加载
2. 存在可用 PF 端口
3. debugfs 可写"""

    EXPECT_EVENT_TYPE = "0x4"
    EXPECT_EVENT_SUBTYPE = "0x3"
    DMA_ERR_REG = "0x844a205c"
    DMA_ERR_VAL = "0x9d"

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "RDMA CQ DBR DMA error event test failed"

    @classmethod
    def check_own_environment(cls) -> None:
        # 获取测试网口、BDF 等
        cls.own_environment_enabled = True

    @classmethod
    def prepare(cls) -> None:
        # 配置 CQ polling、深度 8，清理日志
        log.info("配置 CQ polling 模式并设置 cq_depth=8...")

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 case 06_70_005_004：CQ DBR DMA 错误事件")
        log.info("=" * 60)
        try:
            # 1. 注入 DMA 错误
            cls._inject_dma_error()
            # 2. 启动 rdma_test 打流
            cls._start_traffic()
            # 3. 检查事件
            cls._check_async_event()
            log.info("case 06_70_005_004 测试通过")
        except SxeException:
            raise
        except Exception as e:
            log.error(f"case 06_70_005_004 未预期错误: {e}")
            raise

    @classmethod
    def _inject_dma_error(cls) -> None:
        cmd = f"mw {cls.DMA_ERR_REG} {cls.DMA_ERR_VAL}"
        log.info(f"注入 DMA 错误: {cmd}")
        status, _, err = CommandOperation.execute_command_with_error(
            cmd, CmdExecuteAdressEnum.SERVER.value
        )
        if status != RtnStatusEnum.SUCCESS.value:
            cls._bug_and_raise(f"注错命令执行失败: {err}")

    @classmethod
    def _start_traffic(cls) -> None:
        log.info("启动 rdma_test 打流...")
        # 实际调用 rdma_test 工具

    @classmethod
    def _check_async_event(cls) -> None:
        log.info("检查异步事件...")
        # 从 dmesg / 驱动日志 / debugfs 解析 event_type 与 event_subtype
        # if not matched: cls._bug_and_raise("未收到预期的 CQ DBR DMA 错误事件")

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = (
            f"应收到 event_type={cls.EXPECT_EVENT_TYPE}, "
            f"event_subtype={cls.EXPECT_EVENT_SUBTYPE} 的 CQ 错误异步事件"
        )
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)

    @classmethod
    def post(cls) -> None:
        log.info("清理测试环境...")
        # 停止 rdma_test、恢复 CQ 配置等


def main() -> None:
    Nic06700005004CqDbrDmaErr.run()


if __name__ == "__main__":
    main()
```

---

## 5. 参考

- `xmind文件夹/EQ事件.png`
- `xmind文件夹/异常构造.docx` 第 4、7 条
- `xmind文件夹/天蝎 RDMA异常处理AEQE.xlsx`
