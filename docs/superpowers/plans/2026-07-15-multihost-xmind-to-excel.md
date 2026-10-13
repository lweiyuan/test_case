> **I'm using the writing-plans skill to create the implementation plan.**

# multi host.xmind 生成测试用例 Excel 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除旧脚本后，依据 `multi host.xmind` 生成一份 `MultiHost_RDMA_测试用例.xlsx`。

**Architecture:** 使用一次性 Python 脚本解析 XMind（zip + JSON），提取 `[FTx]` / `[TCx]` 节点、前置条件、测试步骤、预期结果和变化因子，写入符合项目规范的 Excel。脚本运行后即删除，仅保留最终 Excel。

**Tech Stack:** Python 3, openpyxl, zipfile, json, re

## Global Constraints

- 不保留新的生成脚本到仓库。
- Excel 输出路径：`excel测试用例文件夹/YYYY-MM-DD_HH-MM-SS/MultiHost_RDMA_测试用例.xlsx`。
- 列头与项目现有测试用例 Excel 保持一致。
- 变化因子中的“任选一个”需解析为具体值，不原样写入。

---

### Task 1: 删除旧生成脚本

**Files:**
- Delete: `ps3/test/esat/nic100/framework/biz/excel/generate_multihost_cases_from_xmind.py`

**Interfaces:**
- 无输入输出，仅清理旧产物。

- [ ] **Step 1: 删除旧脚本**

```bash
rm "ps3/test/esat/nic100/framework/biz/excel/generate_multihost_cases_from_xmind.py"
```

- [ ] **Step 2: 确认删除**

```bash
ls "ps3/test/esat/nic100/framework/biz/excel/generate_multihost_cases_from_xmind.py"
```

Expected: `No such file or directory`

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove obsolete multihost xmind-to-excel generator"
```

---

### Task 2: 编写一次性 XMind 解析与 Excel 生成脚本

**Files:**
- Create: `/tmp/multihost_excel_gen.py`（临时文件，运行后删除）

**Interfaces:**
- Consumes: `xmind文件夹/multi host.xmind`
- Produces: `excel测试用例文件夹/YYYY-MM-DD_HH-MM-SS/MultiHost_RDMA_测试用例.xlsx`

- [ ] **Step 1: 创建临时脚本**

将以下完整脚本写入 `/tmp/multihost_excel_gen.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性脚本：根据 multi host.xmind 生成测试用例 Excel。"""
import os
import re
import zipfile
import json
from datetime import datetime
from itertools import product
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
SOURCE_FILE = os.path.join(PROJECT_ROOT, "xmind文件夹", "multi host.xmind")
OUTPUT_BASE_DIR = os.path.join(PROJECT_ROOT, "excel测试用例文件夹")

TARGET_COLUMNS = [
    "所属产品", "所属模块", "优先级", "用例类型", "脚本名称", "测试编号",
    "用例标题", "前提条件", "测试步骤", "预期结果", "检查项/测试点",
    "测试场景", "用例测试分类", "负责人", "作者", "测试平台实现自动化",
    "需求点/测试对象", "物理环境",
]

BUSINESS_TO_CMD = {
    "rdma read": "ib_read_bw",
    "rdma write": "ib_write_bw",
    "rdma rc send": "ib_send_bw",
    "rdma ud send": "ib_send_bw --ud",
    "rdma atomic": "ib_atomic_bw",
}

BUSINESS_TO_SUFFIX = {
    "rdma read": "bw-read", "rdma write": "bw-write",
    "rdma rc send": "bw-rc-send", "rdma ud send": "bw-ud-send",
    "rdma atomic": "bw-atomic",
}

def clean_value(value):
    if value is None:
        return ""
    return ILLEGAL_CHARACTERS_RE.sub(r"", str(value))

def load_xmind_topics(xmind_path):
    with zipfile.ZipFile(xmind_path, "r") as z:
        content = json.loads(z.read("content.json").decode("utf-8"))
    root = content[0]["rootTopic"]
    def _collect(topic):
        yield topic
        for child in topic.get("children", {}).get("attached", []):
            yield from _collect(child)
    return root, list(_collect(root))

def find_child(topic, substr):
    for child in topic.get("children", {}).get("attached", []):
        if substr in child.get("title", ""):
            return child
    return None

def collect_text_leaves(topic):
    texts = []
    children = topic.get("children", {}).get("attached", []) if topic else []
    if not children:
        t = topic.get("title", "").strip() if topic else ""
        if t:
            texts.append(t)
        return texts
    for child in children:
        texts.extend(collect_text_leaves(child))
    return texts

def get_factor_values(tc_node):
    factors = {}
    factors_node = find_child(tc_node, "变化因子")
    if not factors_node:
        return factors
    for factor in factors_node.get("children", {}).get("attached", []):
        title = factor.get("title", "")
        m = re.search(r"(\[TE\d+\])", title)
        if not m:
            continue
        values = collect_text_leaves(factor)
        factors[m.group(1)] = values
    return factors

def collect_te_strategies(node, result, current_strategy=None):
    title = node.get("title", "")
    new_strategy = current_strategy
    if "随机值" in title:
        new_strategy = "random"
    elif "遍历" in title or "正交" in title or "笛卡尔" in title:
        new_strategy = "cartesian"
    m = re.search(r"(\[TE\d+\])", title)
    if m and current_strategy:
        result[m.group(1)] = current_strategy
    for child in node.get("children", {}).get("attached", []):
        collect_te_strategies(child, result, new_strategy)

def get_factor_strategies(tc_node):
    strategies = {}
    strategy_node = find_child(tc_node, "测试策略")
    if strategy_node:
        collect_te_strategies(strategy_node, strategies)
    for te in get_factor_values(tc_node):
        if te not in strategies:
            strategies[te] = "cartesian"
    return strategies

def simplify_pkt_len(value_text):
    if not value_text:
        return value_text
    return re.split(r"[（(]", value_text)[0].strip()

def format_te3_short(value_text):
    m = re.findall(r"(\d+)", value_text)
    if len(m) >= 3:
        return f"port{m[0]}host{m[1]}pf{m[2]}"
    return value_text

def replace_command_for_business(steps_text, business_type):
    cmd = BUSINESS_TO_CMD.get(business_type, "ib_read_bw")
    text = re.sub(r"\bib_read_bw\b", cmd.split()[0], steps_text)
    if business_type == "rdma ud send":
        text = re.sub(r"(ib_send_bw\s+.*?)(\n|$)", r"\1 --ud\2", text)
    return text

def collect_numbered_leaves(topic):
    result = {}
    if topic is None:
        return result
    def _walk(node):
        children = node.get("children", {}).get("attached", [])
        if not children:
            text = node.get("title", "").strip()
            if text:
                m = re.match(r"^(\d+)[\.、]\s*(.*)", text)
                if m:
                    result[int(m.group(1))] = m.group(2).strip()
            return
        for child in children:
            _walk(child)
    _walk(topic)
    return result

def build_tc_info(tc_node):
    title = tc_node.get("title", "")
    case_type_tag = ""
    if "正向用例" in title:
        case_type_tag = "正向用例"
    elif "性能用例" in title:
        case_type_tag = "性能用例"
    elif "可靠性用例" in title:
        case_type_tag = "可靠性用例"
    elif "压力用例" in title:
        case_type_tag = "压力用例"
    return {
        "title": title,
        "case_type_tag": case_type_tag,
        "precondition": "\n".join(collect_text_leaves(find_child(tc_node, "前置条件"))),
        "steps": "\n".join(collect_text_leaves(find_child(tc_node, "测试步骤"))),
        "expectation": "\n".join(collect_text_leaves(find_child(tc_node, "测试预期"))),
        "numbered_expectations": collect_numbered_leaves(find_child(tc_node, "测试预期")),
        "topology": "\n".join(collect_text_leaves(find_child(tc_node, "测试拓扑"))),
        "factors": get_factor_values(tc_node),
        "strategies": get_factor_strategies(tc_node),
    }

def generate_expectation_for_step(step_text, overall_expectation, case_tag):
    step = step_text.strip()
    if not step:
        return ""
    expectations = []
    if re.search(r"两两组合|并发执行|所有.*设备", step):
        expectations.append("所有 RDMA 设备两两组合完成，业务并发执行，无冲突、无异常")
    if re.search(r"读取.*设备名|ibstat|识别设备", step):
        expectations.append("成功读取到两端有效的 RDMA 设备名")
    if re.search(r"检查.*状态|Active/LinkUp|LinkUp", step):
        expectations.append("两端 RDMA 设备状态均为 Active/LinkUp")
    if re.search(r"server.*启动.*ib_(read|write|send|atomic)_bw", step, re.IGNORECASE):
        expectations.append("server 端 RDMA perftest 进程正常启动，监听端口无报错")
    if re.search(r"client.*启动.*ib_(read|write|send|atomic)_bw", step, re.IGNORECASE):
        expectations.append("client 端与 server 端成功建立 RDMA 连接，开始打流")
    if re.search(r"iperf3\s+-s", step):
        expectations.append("iperf3 server 正常启动并监听端口")
    if re.search(r"iperf3\s+-c", step):
        expectations.append("iperf3 client 与 server 成功连接并开始以太流量测试")
    if re.search(r"解析.*日志|确认.*带宽|确认.*错误|带宽.*错误", step):
        base = "两端日志无错误，带宽/时延等指标符合预期"
        if case_tag == "性能用例" and "理论带宽" in overall_expectation:
            base += "，所有业务带宽总和接近网卡理论带宽"
        expectations.append(base)
    if re.search(r"停止.*perftest|停止.*进程", step):
        expectations.append("perftest / iperf3 进程正常退出，无残留、无 coredump")
    if not expectations:
        return overall_expectation.split("\n")[0] if overall_expectation else "执行成功，结果符合预期"
    return "；".join(expectations)

def generate_step_expectations(steps_text, overall_expectation, numbered_expectations=None, case_tag=""):
    numbered_expectations = numbered_expectations or {}
    raw_lines = [line.rstrip() for line in steps_text.splitlines()]
    steps, current = [], []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\d+[\.、]\s*", stripped):
            if current:
                steps.append("\n".join(current))
            current = [stripped]
        else:
            if current:
                current.append(stripped)
            else:
                current = [stripped]
    if current:
        steps.append("\n".join(current))

    result_lines = []
    for step in steps:
        stripped = step.strip()
        if stripped.startswith("#"):
            result_lines.append(step)
            summary = overall_expectation.split("\n")[0] if overall_expectation else ""
            summary = re.sub(r"^\d+[\.、]\s*", "", summary).strip()
            if summary:
                result_lines.append(f"  -> {summary}")
            continue
        step_content = re.sub(r"^\d+[\.、]\s*", "", stripped).strip()
        m = re.match(r"^(\d+)[\.、]", stripped)
        step_num = int(m.group(1)) if m else None
        if step_num is not None and step_num in numbered_expectations:
            exp = numbered_expectations[step_num]
            additional = []
            if re.search(r"iperf3\s+-s", step_content) and "iperf3 server" not in exp:
                additional.append("iperf3 server 正常启动并监听端口")
            if re.search(r"iperf3\s+-c", step_content) and "iperf3 client" not in exp:
                additional.append("iperf3 client 与 server 成功连接并开始以太流量测试")
            if additional:
                exp = f"{exp}；" + "；".join(additional)
        else:
            exp = generate_expectation_for_step(step_content, overall_expectation, case_tag)
        result_lines.append(step)
        result_lines.append(f"  -> {exp}")
    return "\n".join(result_lines)

def expand_tc_cases(tc_info, global_counter):
    factors = tc_info["factors"]
    strategies = tc_info["strategies"]
    tes = sorted(factors.keys())
    fixed_factors = [te for te in tes if strategies.get(te, "cartesian") != "random"]
    random_factors = [te for te in tes if strategies.get(te, "cartesian") == "random"]
    fixed_combinations = list(product(*[factors[te] for te in fixed_factors])) if fixed_factors else [()]
    cases = []
    for combo in fixed_combinations:
        case_values = dict(zip(fixed_factors, combo))
        for te in random_factors:
            values = factors[te]
            case_values[te] = values[global_counter[te] % len(values)]
            global_counter[te] += 1
        cases.append(case_values)
    return cases

def get_scenario_and_classification(ft_title, tc_case_tag):
    if "multi host的rdma通讯" in ft_title:
        scenario = "multi-host RDMA 通讯"
    elif "multi host的rdma和以太的混合通讯" in ft_title:
        scenario = "multi-host RDMA+以太混合通讯"
    elif "socket direct的rdma通讯" in ft_title:
        scenario = "socket direct RDMA 通讯"
    elif "socket direct的rdma和以太的混合通讯" in ft_title:
        scenario = "socket direct RDMA+以太混合通讯"
    else:
        scenario = ft_title
    classification = "系统测试-性能" if tc_case_tag == "性能用例" else "系统测试-功能"
    return scenario, classification

def get_priority(case_tag):
    return {"性能用例": "4", "可靠性用例": "2", "压力用例": "3"}.get(case_tag, "1")

def get_case_type_text(case_tag):
    return {
        "性能用例": "系统测试-性能[性能用例]",
        "可靠性用例": "系统测试-可靠性[可靠性用例]",
        "压力用例": "系统测试-压力[压力用例]",
    }.get(case_tag, "系统测试-功能[正向用例]")

def generate_excel():
    if not os.path.exists(SOURCE_FILE):
        raise FileNotFoundError(f"Source xmind not found: {SOURCE_FILE}")
    root, all_topics = load_xmind_topics(SOURCE_FILE)
    ft_nodes = [t for t in all_topics if re.search(r"\[FT\d+\]", t.get("title", ""))]
    global_counter = {}
    for ft in ft_nodes:
        for tc in ft.get("children", {}).get("attached", []):
            if re.search(r"\[TC\d+\]", tc.get("title", "")):
                tc_info = build_tc_info(tc)
                for te, strategy in tc_info["strategies"].items():
                    if strategy == "random" and te not in global_counter:
                        global_counter[te] = 0
    all_cases, case_seq = [], 1
    for ft in ft_nodes:
        ft_title = ft.get("title", "")
        tc_nodes = [c for c in ft.get("children", {}).get("attached", []) if re.search(r"\[TC\d+\]", c.get("title", ""))]
        for tc in tc_nodes:
            tc_info = build_tc_info(tc)
            scenario, classification = get_scenario_and_classification(ft_title, tc_info["case_type_tag"])
            expanded = expand_tc_cases(tc_info, global_counter)
            for ev in expanded:
                business = ev.get("[TE1]", "rdma read")
                pkt_len = ev.get("[TE2]", "64B")
                pkt_len_short = simplify_pkt_len(pkt_len)
                te3_text = ev.get("[TE3]", "port数量为1，host的数量为2，每个host的pf数量为1")
                tc_short_title = re.sub(r"^\[[^\]]+\]", "", tc_info["title"]).strip()
                tc_short_title = re.sub(r"\[[^\]]+\]", "", tc_short_title).strip()
                case_title = f"{tc_short_title}_业务:{business}_包长:{pkt_len_short}_{format_te3_short(te3_text)}"
                case_tag = tc_info["case_type_tag"]
                type_code = {"性能用例": "perf", "可靠性用例": "rel", "压力用例": "stress"}.get(case_tag, "func")
                case_id = f"multihost-rdma-{type_code}-{case_seq:03d}"
                script_suffix = BUSINESS_TO_SUFFIX.get(business, "bw-read")
                script_name = f"linux/multi-host-rdma-{type_code}-{case_seq:03d}-{script_suffix}.py"
                steps = replace_command_for_business(tc_info["steps"], business)
                steps = f"# 当前配置：业务类型={business}，包长={pkt_len}，拓扑={te3_text}\n" + steps
                step_expectations = generate_step_expectations(
                    steps, tc_info["expectation"], tc_info["numbered_expectations"], case_tag
                )
                row = [
                    "800G NIC", "multihost", get_priority(case_tag), get_case_type_text(case_tag),
                    script_name, case_id, case_title, tc_info["precondition"], steps,
                    step_expectations, case_title, scenario, classification,
                    "朱博", "朱博", "是", "multihost", tc_info["topology"],
                ]
                all_cases.append([clean_value(v) for v in row])
                case_seq += 1

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = os.path.join(OUTPUT_BASE_DIR, timestamp)
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "MultiHost_RDMA_测试用例.xlsx")
    wb = Workbook()
    if "Sheet" in wb.sheetnames:
        wb.remove(wb["Sheet"])
    ws = wb.create_sheet(title="MultiHost_RDMA_测试用例", index=0)
    ws.append(TARGET_COLUMNS)
    for case in all_cases:
        ws.append(case)
    ws.sheet_format.defaultColWidth = 20
    wb.save(output_file)
    print(f"Generated {output_file} with {len(all_cases)} test cases.")
    return output_file, len(all_cases)

if __name__ == "__main__":
    generate_excel()
```

- [ ] **Step 2: 运行脚本生成 Excel**

```bash
cd "C:/work/excel_to_scripts_project/ps3code"
python /tmp/multihost_excel_gen.py
```

Expected: 输出 `Generated excel测试用例文件夹/<timestamp>/MultiHost_RDMA_测试用例.xlsx with N test cases.`

---

### Task 3: 验证生成的 Excel

**Files:**
- Read: `excel测试用例文件夹/<timestamp>/MultiHost_RDMA_测试用例.xlsx`

**Interfaces:**
- 无输入输出，仅做人工/命令行检查。

- [ ] **Step 1: 检查文件存在且包含用例**

```bash
ls -lh excel测试用例文件夹/*/
```

Expected: 看到刚生成的 `.xlsx` 文件，大小 > 0。

- [ ] **Step 2: 用 openpyxl 读取并打印行数**

```python
from openpyxl import load_workbook
import glob
files = glob.glob("excel测试用例文件夹/*/MultiHost_RDMA_测试用例.xlsx")
wb = load_workbook(files[-1])
ws = wb.active
print("Rows:", ws.max_row, "Cols:", ws.max_column)
print("Headers:", [ws.cell(1, c).value for c in range(1, ws.max_column+1)])
```

Expected: `Rows: N+1`（含表头），表头与 TARGET_COLUMNS 一致。

---

### Task 4: 删除临时脚本并收尾

**Files:**
- Delete: `/tmp/multihost_excel_gen.py`

- [ ] **Step 1: 删除临时脚本**

```bash
rm /tmp/multihost_excel_gen.py
```

- [ ] **Step 2: 确认仓库状态**

```bash
git status
```

Expected: 仅有 `docs/superpowers/specs/...` 和 `docs/superpowers/plans/...` 的变更（如果有提交），以及新增的 Excel 文件（未被 git 跟踪）。

- [ ] **Step 3: Commit 文档变更**

```bash
git add docs/superpowers/
git commit -m "docs: add multihost xmind-to-excel design and plan"
```

---

## Self-Review

- **Spec coverage:** 删除旧脚本、一次性解析 XMind、生成 Excel、不保留新脚本均已覆盖。
- **Placeholder scan:** 无 TBD/TODO，所有代码和命令完整。
- **Type consistency:** 函数签名和返回值在临时脚本内部一致。
