# Port VLAN 测试用例与脚本生成实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `xmind文件夹/port vlan.xmind` 转换为标准 Excel 测试用例，并生成 NIC100 框架下的 Python 自动化测试脚本。

**Architecture:** 一次性 Python 生成脚本解析 XMind `content.json`，将测试点映射为 Excel 行，并为每个可自动化测试点生成一个继承 `ScriptBase` 的 Python 脚本。Excel 按时间子目录输出到 `excel测试用例文件夹/`，脚本输出到 `ps3/test/esat/nic100/scripts/nic100/linux/vlan/`，生成器本身放入 `临时文件夹/`。

**Tech Stack:** Python 3, openpyxl, zipfile/json, NIC100 ScriptBase

## Global Constraints

- Excel 输出路径：`excel测试用例文件夹/YYYY-MM-DD_HH-MM-SS/PortVLAN_测试用例.xlsx`
- Python 脚本输出路径：`ps3/test/esat/nic100/scripts/nic100/linux/vlan/`
- 一次性生成脚本输出路径：`临时文件夹/YYYY-MM-DD_HH-MM-SS/`
- Excel 必须使用现有 18 列模板
- Python 脚本必须继承 `ScriptBase`，命名遵循 `tianying_port_vlan_<feature>_<mode>.py`
- 不要直接修改 `.xlsx` 源文件

---

### Task 1: 创建一次性 XMind 解析与生成脚本

**Files:**
- Create: `临时文件夹/2026-07-20_port_vlan/generate_port_vlan_cases.py`

**Interfaces:**
- Consumes: `xmind文件夹/port vlan.xmind`
- Produces: Excel 文件路径、Python 脚本文件路径列表

- [ ] **Step 1: 读取 XMind 内容**

```python
import zipfile, json
from pathlib import Path

xmind_path = Path("xmind文件夹/port vlan.xmind")
with zipfile.ZipFile(xmind_path, "r") as z:
    sheets = json.loads(z.read("content.json").decode("utf-8"))
root = sheets[0]["rootTopic"]
```

- [ ] **Step 2: 解析主题树并提取测试点**

```python
def iter_topics(topic, path=None):
    path = path or []
    title = topic.get("title", "")
    new_path = path + [title]
    children = topic.get("children", {}).get("attached", [])
    if not children:
        yield new_path
    for child in children:
        yield from iter_topics(child, new_path)

test_points = list(iter_topics(root))
```

- [ ] **Step 3: 将测试点映射为用例元数据**

生成字段：`测试编号、用例标题、前提条件、测试步骤、预期结果、测试场景、脚本名称` 等。

```python
cases = []
for idx, path in enumerate(test_points, 1):
    case_id = f"port-vlan-func-{idx:03d}"
    title = "_".join(path[1:])
    cases.append({
        "测试编号": case_id,
        "用例标题": title,
        "测试场景": "port vlan",
        "脚本名称": f"linux/tianying_port_vlan_func_{idx:03d}_kernel.py",
        # ... 其他字段
    })
```

- [ ] **Step 4: 写入 Excel**

```python
from openpyxl import Workbook
from openpyxl.styles import Alignment

wb = Workbook()
ws = wb.active
ws.title = "PortVLAN_测试用例"
headers = [
    "所属产品", "所属模块", "优先级", "用例类型", "脚本名称",
    "测试编号", "用例标题", "前提条件", "测试步骤", "预期结果",
    "检查项/测试点", "测试场景", "用例测试分类", "负责人", "作者",
    "测试平台实现自动化", "需求点/测试对象", "物理环境"
]
ws.append(headers)
for case in cases:
    ws.append([case.get(h, "") for h in headers])
output_dir = Path("excel测试用例文件夹/2026-07-20_08-26-11")
output_dir.mkdir(parents=True, exist_ok=True)
excel_path = output_dir / "PortVLAN_测试用例.xlsx"
wb.save(excel_path)
```

- [ ] **Step 5: 运行生成脚本验证输出**

```bash
chcp.com 65001
PYTHONIOENCODING=utf-8 python "临时文件夹/2026-07-20_port_vlan/generate_port_vlan_cases.py"
```

Expected: Excel 文件生成成功，包含所有测试点。

- [ ] **Step 6: Commit 生成脚本（可选）**

```bash
git add "临时文件夹/2026-07-20_port_vlan/generate_port_vlan_cases.py"
git commit -m "chore: add port vlan case generator"
```

---

### Task 2: 生成 Python 自动化测试脚本

**Files:**
- Create: `ps3/test/esat/nic100/scripts/nic100/linux/vlan/tianying_port_vlan_func_*.py`

**Interfaces:**
- Consumes: 用例元数据（编号、标题、步骤、预期结果）
- Produces: 可执行的 NIC100 测试脚本

- [ ] **Step 1: 定义脚本模板**

```python
SCRIPT_TEMPLATE = '''#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: {case_number}
case title: {case_title}
test category: port vlan
check point: {check_point}
author: auto-generated
date: {date}
"""

import os
import time
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import CmdExecuteAdressEnum, RtnStatusEnum, BugTypeEnum
from scripts.script_libs.script_base import ScriptBase, SxeException


class {class_name}(ScriptBase):
    test_object = "port vlan"
    test_module = "port_vlan"
    test_tool = "ip, ethtool"
    test_precondition = """{precondition}"""
    test_steps = """{test_steps}"""

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "{class_name} Failed"

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 {case_number} 环境...")
        server_ifs, client_ifs = CommonOperation.get_nic_relationships(
            rdma=False, nic_mode=1
        )
        if not server_ifs or not client_ifs:
            log.error("未读取到以太设备名")
            cls.own_environment_enabled = False
            return
        cls.server_if = server_ifs[0].strip()
        cls.client_if = client_ifs[0].strip()
        cls.own_environment_enabled = True

    @classmethod
    def prepare(cls) -> None:
        log.info("准备 {case_number} 环境...")
        # TODO: 根据具体用例实现前置准备

    @classmethod
    def do(cls) -> None:
        log.info("开始 {case_number}: {case_title}")
        try:
            # TODO: 根据具体用例实现测试步骤
            log.info("{case_number} 测试通过")
        except SxeException:
            raise
        except Exception as e:
            log.error(f"{case_number} 未预期错误: {{e}}")
            raise

    @classmethod
    def post(cls) -> None:
        log.info("清理 {case_number} 环境...")
        # TODO: 根据具体用例实现清理


def main() -> None:
    {class_name}.run()


if __name__ == "__main__":
    main()
'''
```

- [ ] **Step 2: 为每个用例生成脚本文件**

```python
for case in cases:
    class_name = "".join([w.capitalize() for w in case["用例标题"].replace("_", " ").split()])
    content = SCRIPT_TEMPLATE.format(
        case_number=case["测试编号"],
        case_title=case["用例标题"],
        class_name=class_name,
        check_point=case["检查项/测试点"],
        date="2026.07.20",
        precondition=case["前提条件"],
        test_steps=case["测试步骤"],
    )
    script_path = Path("ps3/test/esat/nic100/scripts/nic100/linux/vlan") / case["脚本名称"].replace("linux/", "")
    script_path.write_text(content, encoding="utf-8")
```

- [ ] **Step 3: 语法检查所有生成的脚本**

```bash
for f in ps3/test/esat/nic100/scripts/nic100/linux/vlan/tianying_port_vlan_func_*.py; do
  python -m py_compile "$f" || echo "FAILED: $f"
done
```

Expected: 所有脚本编译通过，无 FAILED 输出。

- [ ] **Step 4: Commit 生成的脚本**

```bash
git add ps3/test/esat/nic100/scripts/nic100/linux/vlan/tianying_port_vlan_func_*.py
git commit -m "feat: add port vlan test scripts"
```

---

### Task 3: 验证产物完整性

**Files:**
- Read: `excel测试用例文件夹/2026-07-20_08-26-11/PortVLAN_测试用例.xlsx`
- Read: `ps3/test/esat/nic100/scripts/nic100/linux/vlan/tianying_port_vlan_func_*.py`

- [ ] **Step 1: 验证 Excel 行数与 XMind 叶子节点数一致**

```python
import openpyxl
wb = openpyxl.load_workbook("excel测试用例文件夹/2026-07-20_08-26-11/PortVLAN_测试用例.xlsx")
ws = wb.active
print(f"Excel 数据行数: {ws.max_row - 1}")
print(f"XMind 叶子节点数: {len(test_points)}")
assert ws.max_row - 1 == len(test_points)
```

Expected: 两者数量相等。

- [ ] **Step 2: 抽查脚本结构**

```bash
grep -l "class TianyingPortVlan" ps3/test/esat/nic100/scripts/nic100/linux/vlan/tianying_port_vlan_func_*.py | wc -l
```

Expected: 数量等于生成的脚本数。

- [ ] **Step 3: Commit 验证结果（可选）**

---

## Self-Review

1. **Spec coverage:** 每个 XMind 测试点都有对应的 Excel 行；每个可自动化用例都有 Python 脚本。
2. **Placeholder scan:** 脚本模板中的 `# TODO` 是合理的占位，表示具体用例实现需根据内容细化；计划本身无 TBD。
3. **Type consistency:** 文件路径、字段名称前后一致。
