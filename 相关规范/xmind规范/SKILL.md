# NIC100 测试设计 .xmind 生成规范

> 本规范整理自 `tc层测试设计.xmind`、`以太Linux驱动_txsched_补全版.xmind`、`VF测试设计.xmind` 的生成实践，用于指导按测试规范/需求生成 **XMind 测试设计导图（.xmind）**。
> 放置位置：`相关规范/xmind规范/SKILL.md`，不进入 `.kimi-code/skills/` 自动加载目录。

## 1. 适用范围

- 把测试规范、需求文档、XMind 测试点整理成结构化 `.xmind` 测试设计导图
- 为已有测试设计（如 tc 层、VF、tx_sched）补充背景学习分支、测试分析、测试用例分层
- 需要交付「可被 XMind 正常打开」的思维导图时

## 2. 核心原则（必须遵守）

### 2.1 以模板方式生成，禁止手工构造 content.json

XMind 10 对文件结构校验严格，**手工从零拼装 `content.json` 会导致文件无法打开**。唯一可靠做法：

1. 取一个**当前能正常打开**的 `.xmind` 作为模板
2. 解压模板（保留 `theme`、`manifest.json`、`resources/`、`Thumbnails/`）
3. **仅替换 `rootTopic` 主题树**
4. 重新打包为 `.xmind`

### 2.2 `extensions` 必须是数组（最易踩的坑）

`rootTopic.extensions` 必须是**数组**，否则 XMind 打开时报：

```
TypeError: t.extensions.some is not a function
```

正确写法：

```json
"extensions": [
  {
    "provider": "org.xmind.ui.map.unbalanced",
    "content": [{ "name": "right-number", "content": "1" }]
  }
]
```

错误写法（对象，会报错）：

```json
"extensions": {
  "provider": "org.xmind.ui.map.unbalanced",
  "content": [{ "name": "right-number", "content": "1" }]
}
```

### 2.3 必需字段（缺一不可）

| 层级 | 字段 | 要求 |
|---|---|---|
| sheet | `id` / `class`("sheet") / `title` / `rootTopic` / `theme` / `topicPositioning`("fixed") / `relationships`(数组) | 缺 `theme` 会导致打不开 |
| rootTopic | `id` / `class`("topic") / `title` / `structureClass` / `children` / `extensions`(数组) | |
| topic 节点 | `id` / `title` / `children`(有子节点时) | 叶子节点只有 `id` + `title` |
| metadata.json | `activeSheetId` | 必须与 sheet.id 一致 |

其他要求：
- 每个 topic 的 `id` 必须**全局唯一**（用 `uuid.uuid4().hex`）
- `content.json` 用 **UTF-8 无 BOM** 写入
- `manifest.json` 的 `file-entries` 需与实际打包条目一致
- `structureClass` 用 `org.xmind.ui.map.unbalanced`

## 3. 主题树内容结构约定

参照 `tc层测试设计.xmind` 与 `VF测试设计.xmind` 的成熟结构：

```
<模块> 测试设计                     ← 根主题
├── <模块> 学习                     ← 背景知识（对齐 tc 层的「tc 学习」分支）
│   ├── <模块> 是什么               概念、定义、原理
│   ├── <模块> 的作用               为什么需要、解决什么问题
│   ├── 相关指令及解释               每条命令 + 中文解释（按功能分组）
│   └── 完整测试流程                 环境准备 → 配置 → 检查 → 打流 → 清理
├── 测试分析
│   ├── 变化因子                    组合因素的取值范围
│   ├── 检查手段                    debugfs / ethtool / 回显 / 打流
│   └── 规格约束                    上限、依赖关系、取值范围
├── 基础功能                        （正向用例）
├── 可靠性                          （反向 / 复位 / 链路 / 驱动变更）
├── 稳定性                          （打流中反复修改配置）
└── 压力测试                        （多组并发）
```

### 3.1 单个用例的四要素模板

每个用例节点下固定四段（与 tc 层模板一致）：

| 子节点 | 内容 |
|---|---|
| 前提条件（可选） | 环境依赖，逐条一行 |
| 测试步骤 | `1. ` `2. ` `3. ` 顺序编号 |
| 测试预期 | 与步骤**同编号、一一对应** |
| 组合因素 | 维度 → 取值列表（用于正交展开） |

### 3.2 命名约定

- 用例标题：`<算法/模式>-<场景条件>`，如 `ets算法限速tc和未配置限速的tc的带宽为满流量`
- 命令类叶子节点：`<中文说明>：<命令>`，如 `设置 VF 最大发送带宽 PIR：ip link set dev <pf> vf <N> max_tx_rate <Mbps>`

## 4. 生成工具（推荐直接调用）

`scripts/gen_xmind.py`：经实测验证的通用生成器。

```bash
# 1) 准备主题树 JSON（children 可嵌套，字符串即叶子）
#    见 scripts/example_tree.json

# 2) 生成并自检
python scripts/gen_xmind.py \
  --template <一个能正常打开的.xmind> \
  --out <输出.xmind> \
  --title "<模块> 测试设计" \
  --tree <tree.json> \
  --validate
```

Python 内嵌调用：

```python
from gen_xmind import generate, validate, T, steps

tree = T("VF 限速测试设计", [
    T("VF 学习", [
        T("VF 是什么", ["VF 是 SR-IOV 技术中的虚拟 PCIe 设备", "..."]),
        T("相关指令及解释", [
            T("ip link set vf", ["设置 PIR：ip link set dev <pf> vf <N> max_tx_rate <Mbps>"]),
        ]),
    ]),
    T("基础功能", [
        T("legacy 模式 - TCP 打流", [
            T("测试步骤", steps(["修改 eswitch mode 为 legacy", "创建 VF", "打流验证"])),
            T("测试预期", ["1. 设置成功", "2. 创建成功", "3. 带宽符合预期"]),
            T("组合因素", [T("VF 数量", ["1", "2", "64"])]),
        ]),
    ]),
])

out = generate("VF测试设计.xmind", "VF 限速测试设计", tree, template="<模板.xmind>")
print(validate(out))   # [] 表示通过
```

要点：
- `steps([...])` 自动加 `1. ` `2. ` 编号；预期若已带编号则直接写列表
- 字符串叶子节点自动生成唯一 id
- 生成器已处理 extensions 数组、theme 保留、activeSheetId 同步、manifest 一致性

## 5. 校验清单

生成后必须确认（`validate()` 覆盖前 5 项）：

- [ ] `rootTopic.extensions` 是**数组**
- [ ] sheet 含 `theme`、`relationships` 为数组
- [ ] `metadata.activeSheetId` == `sheet.id`
- [ ] 所有 topic `id` 唯一、无重复
- [ ] `manifest.json` 条目与实际打包内容一致
- [ ] 文件能实际用 XMind 打开（**最终以真实打开为准**）
- [ ] 测试步骤与测试预期编号一一对应、无跳跃错位
- [ ] 学习分支包含：是什么 / 作用 / 相关指令及解释 / 完整测试流程
- [ ] 用例分层完整：基础功能 / 可靠性 / 稳定性（+ 压力测试）

## 6. 常见问题排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `TypeError: t.extensions.some is not a function` | `extensions` 是对象而非数组 | 改为 `[{provider, content}]` |
| 提示「文件可能已损坏」 | 手工构造 content.json，缺 `theme` 或结构不完整 | 改用模板方式生成 |
| XMind 能打开但无内容 | `rootTopic.children` 结构错误 | 应为 `{"attached": [topic, ...]}` |
| 中文乱码 | 写入编码错误 | 用 UTF-8 无 BOM；读入 JSON 用 `utf-8-sig` 兼容 BOM |
| 生成的 JSON 读取报 BOM 错 | PowerShell 写文件带 BOM | 读取时用 `encoding="utf-8-sig"` |
| 用 xmind 库（content.xml 格式）生成后 XMind 10 报错 | 库产出 XMind 8 格式，与 XMind 10 不兼容 | 走 content.json（XMind 10 原生）模板方式 |

## 7. 参考文件

- 学习样例：`xmind文件夹/tc层测试设计.xmind`（含「tc 学习」分支 + 三层用例）
- 综合样例：`以太Linux驱动_txsched_补全版.xmind`（调度树全特性）
- 生成脚本：`相关规范/xmind规范/scripts/gen_xmind.py`
- 主题树示例：`相关规范/xmind规范/scripts/example_tree.json`
- 用例规范：`相关规范/用例规范.xlsx`
- 相关模块规范：`相关规范/以太规范/SKILL.md`、`相关规范/DPDK规范/SKILL.md`、`相关规范/RDMA规范/`
