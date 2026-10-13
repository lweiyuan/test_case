# PHB XMind 转 Excel 测试用例实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 根据 `狮子项目/PHB-v1.0.xmind` 生成符合 `狮子项目/Qos_DiffServ_PHB_testcases.xlsx` 风格的 Excel 测试用例文件 `狮子项目/PHB_testcases_from_xmind.xlsx`。

**Architecture:** 使用 Python 脚本读取 XMind 的 `content.json`，递归提取叶子测试点；基于模板列结构填充用例字段，对无法推断字段标注「待补充」并设置黄色背景；最后通过 `openpyxl` 写入新 Excel 文件。

**Tech Stack:** Python 3.13（项目虚拟环境 `.venv`）、`openpyxl`、标准库 `json`/`zipfile`。

## Global Constraints

- 输出文件路径：`狮子项目/PHB_testcases_from_xmind.xlsx`。
- 用例编号前缀沿用模板风格：`sz-phb-eth-f-xxx`、`sz-phb-sue-f-xxx`、`sz-phb-hsloe-f-xxx`、`sz-phb-auto-xxx`。
- 无法推断的字段统一填写「待补充」，并设置黄色背景（`FFFF00`）。
- 标题行与模板一致，共 18 列。
- 所有文件操作均在当前工作目录 `C:/work/excel_to_scripts_project/ps3code` 内进行。

---

### Task 1: 创建 XMind 解析模块

**Files:**
- Create: `generate_phb_xmind_to_excel.py`
- Test: 内联 `if __name__ == "__main__"` 中调用并打印统计

**Interfaces:**
- Produces: `parse_xmind(xmind_path: str) -> list[dict]`，返回叶子节点列表，每个元素包含 `title` 和 `path`（从根到叶子的标题列表）。

- [ ] **Step 1: 编写解析函数骨架并运行失败测试**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate PHB test cases Excel from XMind."""

import json
import zipfile


def parse_xmind(xmind_path: str) -> list[dict]:
    """Parse XMind content.json and return leaf topics with full path."""
    raise NotImplementedError("parse_xmind not implemented")


if __name__ == "__main__":
    leaves = parse_xmind("狮子项目/PHB-v1.0.xmind")
    print(f"leaf count: {len(leaves)}")
```

Run: `.venv/Scripts/python.exe generate_phb_xmind_to_excel.py`
Expected: FAIL with `NotImplementedError`

- [ ] **Step 2: 实现递归解析并过滤空节点**

```python
def parse_xmind(xmind_path: str) -> list[dict]:
    with zipfile.ZipFile(xmind_path, "r") as zf:
        data = json.loads(zf.read("content.json").decode("utf-8"))

    results = []

    def _walk(node, path):
        title = (node.get("title") or "").strip()
        current = path + [title]
        children = node.get("children", {}).get("attached", [])
        if not children:
            if title:
                results.append({"title": title, "path": current})
            return
        for child in children:
            _walk(child, current)

    for sheet in data:
        root = sheet.get("rootTopic")
        if root:
            _walk(root, [])
    return results
```

- [ ] **Step 3: 运行并验证叶子数量**

Run: `.venv/Scripts/python.exe generate_phb_xmind_to_excel.py`
Expected: 输出 `leaf count: 323`

- [ ] **Step 4: Commit**

```bash
git add generate_phb_xmind_to_excel.py
git commit -m "feat: add XMind parser for PHB test cases"
```

---

### Task 2: 实现 Excel 生成逻辑

**Files:**
- Modify: `generate_phb_xmind_to_excel.py`

**Interfaces:**
- Consumes: `parse_xmind` 返回的叶子节点列表。
- Produces: `generate_excel(leaves: list[dict], template_path: str, output_path: str) -> None`，生成目标 Excel 文件。

- [ ] **Step 1: 定义表头和常量**

```python
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

HEADERS = [
    "测试产品", "测试模块", "优先级", "测试类型", "脚本名称", "用例编号",
    "用例标题", "前置条件", "测试步骤", "预期结果", "测试点/测试点",
    "测试场景", "所属测试方案", "作者", "状态", "适用平台实现自动化",
    "测试人/测试日期", "测试备注",
]

YELLOW_FILL = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
THIN_BORDER = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin"),
)
```

- [ ] **Step 2: 实现用例编号生成函数**

```python
def decide_prefix(title: str) -> str:
    lower = title.lower()
    if "sue" in lower:
        return "sz-phb-sue-f-"
    if "hsloe" in lower or "holse" in lower:
        return "sz-phb-hsloe-f-"
    if any(k in lower for k in ("eth", "ipv4", "ipv6", "802.1p", "dscp", "cos")):
        return "sz-phb-eth-f-"
    return "sz-phb-auto-"
```

- [ ] **Step 3: 实现 `generate_excel` 主函数**

```python
def generate_excel(leaves, template_path, output_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "测试用例"

    # 标题行
    for col_idx, header in enumerate(HEADERS, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER

    counters = {}
    for leaf in leaves:
        title = leaf["title"]
        path = leaf["path"]
        prefix = decide_prefix(title)
        counters[prefix] = counters.get(prefix, 0) + 1
        case_id = f"{prefix}{counters[prefix]:03d}"

        test_point = ">".join(path[1:]) if len(path) > 1 else title
        scenario = f"基于XMind节点：{title}"

        # 推断前置条件/步骤/预期结果
        precondition = "1. 测试环境准备就绪，设备上电并确认设备状态正常\n2. 待补充"
        steps = "1. 待补充"
        expected = "1. 待补充"
        remark = ""

        row_values = [
            "57.6T SU Switch(#58)",      # 测试产品
            "/Qos/DiffServ/PHB",           # 测试模块
            "1",                            # 优先级
            "系统测试-功能",                # 测试类型
            "",                             # 脚本名称
            case_id,                        # 用例编号
            title,                          # 用例标题
            precondition,                   # 前置条件
            steps,                          # 测试步骤
            expected,                       # 预期结果
            test_point,                     # 测试点/测试点
            scenario,                       # 测试场景
            "/业务测试/系统测试(#15900)",    # 所属测试方案
            "欢迎页",                       # 作者
            "欢迎页",                       # 状态
            "芯片名称、拥塞管理等(#13073)",  # 适用平台实现自动化
            "",                             # 测试人/测试日期
            remark,                         # 测试备注
        ]

        row_idx = ws.max_row + 1
        for col_idx, value in enumerate(row_values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border = THIN_BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if value == "待补充":
                cell.fill = YELLOW_FILL

    # 列宽
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 20
    ws.column_dimensions["C"].width = 8
    ws.column_dimensions["D"].width = 14
    ws.column_dimensions["E"].width = 14
    ws.column_dimensions["F"].width = 22
    ws.column_dimensions["G"].width = 55
    ws.column_dimensions["H"].width = 35
    ws.column_dimensions["I"].width = 45
    ws.column_dimensions["J"].width = 35
    ws.column_dimensions["K"].width = 70
    ws.column_dimensions["L"].width = 35
    ws.column_dimensions["M"].width = 28
    ws.column_dimensions["N"].width = 10
    ws.column_dimensions["O"].width = 10
    ws.column_dimensions["P"].width = 28
    ws.column_dimensions["Q"].width = 16
    ws.column_dimensions["R"].width = 35

    ws.freeze_panes = "A2"
    wb.save(output_path)
    print(f"Generated {len(leaves)} cases to {output_path}")
```

- [ ] **Step 4: 更新 `__main__` 调用**

```python
if __name__ == "__main__":
    leaves = parse_xmind("狮子项目/PHB-v1.0.xmind")
    generate_excel(
        leaves,
        "狮子项目/Qos_DiffServ_PHB_testcases.xlsx",
        "狮子项目/PHB_testcases_from_xmind.xlsx",
    )
```

- [ ] **Step 5: 运行生成脚本**

Run: `.venv/Scripts/python.exe generate_phb_xmind_to_excel.py`
Expected: 输出 `Generated 323 cases to 狮子项目/PHB_testcases_from_xmind.xlsx`

- [ ] **Step 6: Commit**

```bash
git add generate_phb_xmind_to_excel.py
git commit -m "feat: generate PHB test cases Excel from XMind"
```

---

### Task 3: 验证生成结果

**Files:**
- Read: `狮子项目/PHB_testcases_from_xmind.xlsx`

- [ ] **Step 1: 验证文件存在与基本信息**

Run:
```bash
.venv/Scripts/python.exe - <<'PY'
import openpyxl
wb = openpyxl.load_workbook("狮子项目/PHB_testcases_from_xmind.xlsx")
ws = wb.active
print(f"sheet name: {ws.title}")
print(f"max row: {ws.max_row}")
print(f"max col: {ws.max_column}")
print(f"header: {[ws.cell(1, c).value for c in range(1, ws.max_column + 1)]}")
PY
```

Expected:
```
sheet name: 测试用例
max row: 324
max col: 18
header: ['测试产品', '测试模块', '优先级', ...]
```

- [ ] **Step 2: 抽样检查黄色背景单元格**

Run:
```bash
.venv/Scripts/python.exe - <<'PY'
import openpyxl
wb = openpyxl.load_workbook("狮子项目/PHB_testcases_from_xmind.xlsx")
ws = wb.active
yellow_count = 0
for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
    for cell in row:
        if cell.value == "待补充" and cell.fill.start_color.rgb == "FFFFFF00":
            yellow_count += 1
print(f"待补充单元格数: {yellow_count}")
print(f"用例编号示例: {ws.cell(2, 6).value}, 标题: {ws.cell(2, 7).value}")
PY
```

Expected: 输出黄色「待补充」单元格数量大于 0，且用例编号前缀符合模板风格。

- [ ] **Step 3: Commit 验证结果摘要**

```bash
git add docs/superpowers/plans/2026-07-06-phb-xmind-to-excel.md
git commit -m "docs: add PHB XMind to Excel implementation plan"
```

---

## Self-Review

1. **Spec coverage**: 规格中的字段映射、编号前缀、待补充背景色、输出路径均已映射到 Task 2；验证标准映射到 Task 3。
2. **Placeholder scan**: 计划中没有 TBD/TODO，每个步骤都有具体代码和命令。
3. **Type consistency**: `parse_xmind` 返回 `list[dict]`，`generate_excel` 消费该类型并写入文件，接口一致。
