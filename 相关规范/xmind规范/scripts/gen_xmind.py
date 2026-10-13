#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用 XMind 生成器（NIC100 测试设计导图）

以「现有可正常打开的 .xmind」为模板，仅替换 rootTopic 主题树，输出新的 .xmind。
这是唯一经过验证可靠的方式：直接手工构造 content.json 会导致 XMind 打不开
（典型报错 TypeError: t.extensions.some is not a function，原因是 extensions
不是数组）。

用法：
  python gen_xmind.py --template <模板.xmind> --out <输出.xmind> \
      --title "VF 限速测试设计" --tree <tree.json>

tree.json 结构（children 可嵌套，字符串即叶子节点）：
  {
    "title": "根标题",
    "children": [
      {"title": "分支A", "children": ["叶子1", "叶子2"]},
      "叶子字符串"
    ]
  }

也支持 Python 直接调用：
  from gen_xmind import generate, T, steps
  generate("out.xmind", "标题", T("根", [...]), template="模板.xmind")
"""
import argparse
import json
import os
import shutil
import sys
import uuid
import zipfile

# 默认模板：项目内任意一个「能正常打开」的 xmind
DEFAULT_TEMPLATE_CANDIDATES = [
    "以太Linux驱动_txsched_补全版.xmind",
    "tc层测试设计.xmind",
    "以太Linux驱动_txsched.xmind",
]


def T(title, children=None):
    """构造主题节点：T(标题, [子节点...])；子节点可为 T(...) 或字符串。"""
    return {"title": title, "children": children or []}


def steps(seq):
    """把不带编号的步骤列表转为带 '1. ' '2. ' 编号的列表。"""
    return [f"{i + 1}. {s}" for i, s in enumerate(seq)]


def _build(node):
    """把 T()/str 结构递归转换为 XMind topic dict。字符串为叶子（仅 id+title）。"""
    if isinstance(node, str):
        return {"id": uuid.uuid4().hex, "title": node}
    if not isinstance(node, dict) or "title" not in node:
        raise ValueError(f"非法主题节点（需为 str 或 {{'title':..,'children':[..]}}）：{node!r}")
    t = {"id": uuid.uuid4().hex, "title": node["title"]}
    kids = node.get("children") or []
    if kids:
        t["children"] = {"attached": [_build(k) for k in kids]}
    return t


def resolve_template(template=None, search_dirs=None):
    """确定模板 xmind 路径。"""
    if template:
        if not os.path.exists(template):
            raise FileNotFoundError(f"模板不存在：{template}")
        return template
    dirs = search_dirs or [os.getcwd(), os.path.dirname(os.path.abspath(__file__))]
    for d in dirs:
        for name in DEFAULT_TEMPLATE_CANDIDATES:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
    raise FileNotFoundError(
        "未找到可用模板 xmind。请用 --template 指定一个「能正常打开」的 .xmind 文件。"
    )


def _extract(zip_path, dest):
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            target = os.path.join(dest, info.filename)
            if info.is_dir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())


def generate(out_path, title, tree, template=None, sheet_title=None,
             structure_class="org.xmind.ui.map.unbalanced", keep_template_resources=True):
    """
    生成 .xmind。

    参数：
      out_path   输出路径（.xmind）
      title      根主题标题（同时作为 sheet 标题，除非指定 sheet_title）
      tree       主题树（T(...) 结构）
      template   模板 xmind 路径（强烈建议显式指定一个能正常打开的文件）
      sheet_title sheet 标题，默认同 title
    """
    template = resolve_template(template)
    out_path = os.path.abspath(out_path)
    tmpdir = os.path.join(os.path.dirname(out_path), "._xmind_tmp_" + uuid.uuid4().hex[:8])
    os.makedirs(tmpdir, exist_ok=True)

    try:
        # 1) 解压模板（保留 theme / manifest / resources / 缩略图）
        _extract(template, tmpdir)

        content_path = os.path.join(tmpdir, "content.json")
        if not os.path.exists(content_path):
            raise RuntimeError(
                "模板缺少 content.json（XMind 10 原生格式）。请换用 XMind 10 保存的 .xmind 作模板。"
            )
        with open(content_path, "r", encoding="utf-8") as f:
            content = json.load(f)

        sheet = content[0]
        sheet_id = sheet.get("id") or uuid.uuid4().hex
        sheet["id"] = sheet_id
        sheet["class"] = "sheet"
        sheet["title"] = sheet_title or title
        sheet["topicPositioning"] = sheet.get("topicPositioning", "fixed")
        sheet["relationships"] = sheet.get("relationships", [])

        # 2) 替换 rootTopic —— extensions 必须是「数组」，否则 XMind 报
        #    TypeError: t.extensions.some is not a function
        sheet["rootTopic"] = {
            "id": uuid.uuid4().hex,
            "class": "topic",
            "title": title,
            "structureClass": structure_class,
            "children": _build(tree).get("children", {"attached": []}),
            "extensions": [
                {
                    "provider": structure_class,
                    "content": [{"name": "right-number", "content": "1"}],
                }
            ],
        }

        with open(content_path, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False)

        # 3) metadata.activeSheetId 必须与 sheet.id 一致
        meta_path = os.path.join(tmpdir, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        else:
            metadata = {"creator": {"name": "Vana", "version": "10.1.3.202005082128"}}
        metadata["activeSheetId"] = sheet_id
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False)

        # 4) manifest.json 条目需与实际打包内容一致
        files = []
        for root, _, names in os.walk(tmpdir):
            for n in names:
                files.append(os.path.relpath(os.path.join(root, n), tmpdir).replace("\\", "/"))
        manifest_path = os.path.join(tmpdir, "manifest.json")
        manifest = {"file-entries": {f: {} for f in sorted(files)}}
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False)

        # 5) 打包为 .xmind（ZIP）
        if os.path.exists(out_path):
            os.remove(out_path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, names in os.walk(tmpdir):
                for n in names:
                    full = os.path.join(root, n)
                    zf.write(full, os.path.relpath(full, tmpdir).replace("\\", "/"))
        return out_path
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def validate(xmind_path):
    """自检：扩展为数组、id 唯一、theme 存在、activeSheetId 匹配。"""
    problems = []
    with zipfile.ZipFile(xmind_path) as z:
        names = z.namelist()
        if "content.json" not in names:
            return ["缺少 content.json"]
        content = json.loads(z.read("content.json").decode("utf-8"))
        metadata = json.loads(z.read("metadata.json").decode("utf-8")) if "metadata.json" in names else {}

    sheet = content[0]
    rt = sheet.get("rootTopic", {})
    if not isinstance(rt.get("extensions"), list):
        problems.append("rootTopic.extensions 不是数组（XMind 将报 t.extensions.some）")
    if "theme" not in sheet or not sheet["theme"]:
        problems.append("sheet 缺少 theme（XMind 可能无法打开）")
    if not isinstance(sheet.get("relationships"), list):
        problems.append("sheet.relationships 不是数组")
    if metadata.get("activeSheetId") != sheet.get("id"):
        problems.append("metadata.activeSheetId 与 sheet.id 不一致")

    ids = []
    def walk(n):
        ids.append(n.get("id"))
        for c in (n.get("children") or {}).get("attached", []) or []:
            walk(c)
    walk(rt)
    dup = {i for i in ids if i and ids.count(i) > 1}
    if dup:
        problems.append(f"存在重复 topic id：{list(dup)[:3]}")
    if len(ids) != len(set(ids)):
        problems.append("topic id 不唯一")
    return problems


def main():
    ap = argparse.ArgumentParser(description="以模板方式生成 XMind 测试设计导图")
    ap.add_argument("--template", help="模板 .xmind（能正常打开的）")
    ap.add_argument("--out", required=True, help="输出 .xmind 路径")
    ap.add_argument("--title", required=True, help="根主题标题")
    ap.add_argument("--tree", required=True, help="主题树 JSON 文件路径")
    ap.add_argument("--validate", action="store_true", help="生成后自检")
    args = ap.parse_args()

    # utf-8-sig：兼容 Windows 下带 BOM 的 JSON 文件
    with open(args.tree, "r", encoding="utf-8-sig") as f:
        tree = json.load(f)

    out = generate(args.out, args.title, tree, template=args.template)
    print("生成完成：", out)
    if args.validate:
        problems = validate(out)
        if problems:
            print("自检发现问题：")
            for p in problems:
                print("  -", p)
            sys.exit(1)
        print("自检通过")


if __name__ == "__main__":
    main()
