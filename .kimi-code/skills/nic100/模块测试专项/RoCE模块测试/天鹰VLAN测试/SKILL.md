---
name: 天鹰VLAN测试
description: 指导如何从 vlan.docx 等需求文档中提取天鹰 VLAN 测试点、生成 Excel 测试用例与测试点映射、按内核驱动/DPDK 场景拆分用例，并批量生成 NIC100 框架下的 Python 测试脚本。
---

# 天鹰 VLAN 测试技能

## 使用场景

- 需要分析 VLAN 相关需求文档（如 `vlan.docx`）并整理测试点
- 需要将 VLAN 测试点转换为结构化 Excel 测试用例
- 需要按执行场景（内核驱动 / DPDK）拆分用例
- 需要批量生成 NIC100 框架下可执行的 VLAN 测试脚本
- 需要理解天鹰与 CX7 在 VLAN offload 上的差异

## 前置依赖

- `网卡测试框架`：理解 ScriptBase、env_config、命令封装
- `测试脚本编写`：掌握 prepare/do/post、缺陷自动记录
- `测试用例生成`：掌握 Excel/需求转脚本流程
- `以太网模块测试`：VLAN/Bridge/ethtool 基础

## 天鹰 VLAN 核心测试点

| 编号 | 测试点 | 天鹰支持 | CX7 支持 | 说明 |
|------|--------|----------|----------|------|
| TP-01 | 报文识别 | ✅ | ✅ | VLAN/QinQ 报文识别，提取 VLAN ID/priority |
| TP-02 | 描述符单层 VLAN 插入 | ✅ | ✅ | CTag/STag 单层插入 |
| TP-03 | 描述符 QinQ VLAN 插入 | ✅ | ❌ | 外层 STAG + 内层 CTAG |
| TP-04 | 描述符单层 VLAN 剥离 | ✅ | ✅ | CTag/STag，回写描述符 |
| TP-05 | 描述符 QinQ VLAN 剥离 | ✅ | ❌ | 双层剥离，内外层回写 |
| TP-06 | VSI VLAN 插入 | ✅ | ❌ | 基于 VSI 在最外层插入 |
| TP-07 | VSI VLAN 剥离 | ✅ | ❌ | 剥离最外层，不回写 |
| TP-08 | VLAN 过滤 | ✅ | ✅ | 按 VLAN ID / 类型过滤 |
| TP-09 | VLAN 批量查询 | ✅ | ✅ | 查询 VLAN 配置 |
| TP-10 | 流表 VLAN 配置 | ✅ | ✅ | tc flower / DPDK rte_flow |
| TP-11 | 软硬件差异 | - | - | 天鹰支持 STag/Outer VLAN/多层 VLAN |
| TP-12 | 互斥与异常 | - | - | 流式/队列/VSI 互斥、FDB 切换限制 |

## 从需求文档提取测试点

### 处理图文混排文档

`vlan.docx` 的内容以图片形式存在时，无法直接用 `python-docx` 读取段落。使用以下流程：

```bash
# 1. 解压 docx 提取图片
rm -rf /tmp/vlan_docx_media && mkdir -p /tmp/vlan_docx_media
python - <<'PY'
import zipfile, os
with zipfile.ZipFile('vlan.docx', 'r') as z:
    for name in z.namelist():
        if name.startswith('word/media/'):
            z.extract(name, '/tmp/vlan_docx_media/')
PY

# 2. 查看图片内容（表格形式的测试点通常在其中）
ls /tmp/vlan_docx_media/word/media/
```

### 提取关键信息

从图片中重点关注：
- 功能特性表（如 2-2 VLAN 功能特性）
- 竞品差异对比表（如 3.4 天鹰与 CX7 实现 VLAN 卸载差异对比）
- 软硬件技术需求表（如 4.1 / 4.2）
- 物理环境调研结论中的约束（如 3.5）

## Excel 测试用例设计

### 推荐字段

| 字段 | 说明 |
|------|------|
| 用例编号 | TC-VLAN-001 起 |
| 用例标题 | 功能 + 场景 |
| 所属模块 | tianying_vlan |
| 优先级 | P0/P1/P2 |
| 用例类型 | 功能测试-正向/反向、集成测试 |
| 脚本名称 | 与用例编号对应的 Python 文件名 |
| 前置条件 | 环境准备 |
| 测试步骤 | 详细操作 |
| 预期结果 | 判定标准 |
| 测试点 | 覆盖的 TP-XX 列表 |
| 测试场景 | 内核驱动 / DPDK / DPDK-flow |
| 测试级别 | L1 / L2 |
| 测试平台或工具 | 所需环境与命令 |
| 备注说明 | 对应文档章节 |

### 场景拆分原则

当 `测试场景` 字段包含多个场景（如 `内核驱动; DPDK`）时，应拆分为独立用例：

| 原场景 | 拆分后编号后缀 | 脚本名后缀 | 标题后缀 |
|--------|---------------|-----------|---------|
| 内核驱动 | `-K` | `_kernel` | `（内核驱动）` |
| 内核驱动(SwitchDev) | `-K` | `_kernel` | `（内核驱动-SwitchDev）` |
| DPDK | `-D` | `_dpdk` | `（DPDK）` |
| DPDK flow | `-DF` | `_dpdk_flow` | `（DPDK flow）` |

拆分后每条用例只对应一个执行场景，便于脚本开发和统计覆盖率。

### 用例-测试点关系

建议在 Excel 中增加 `用例-测试点关系` sheet：
- 上半部分：每个测试点覆盖的用例编号及数量
- 下半部分：用例 × 测试点覆盖矩阵，用 `X` 标记

## 脚本生成流程

### 输出位置

```bash
测试脚本文件夹/YYYY-MM-DD_HH-MM-SS/
```

### 必须包含的文件

- `add_syspath.py`：子目录脚本执行时用于设置 sys.path，可从 `ps3/test/esat/nic100/scripts/nic100/linux/rdma/add_syspath.py` 复制
- 各用例 `.py` 脚本：继承 `ScriptBase`，包含 `prepare/do/post`

### 脚本结构要点

```python
class TianyingVlanTxInsertCtagKernel(ScriptBase):
    test_object = "天鹰 VLAN 测试"
    test_module = "tianying_vlan"
    test_tool = "ip, ethtool, ping, tcpdump"
    test_precondition = "..."
    test_steps = "..."

    VLAN_ID = 100
    SERVER_VLAN_IP = "192.168.100.1"
    CLIENT_VLAN_IP = "192.168.100.2"

    @classmethod
    def check_own_environment(cls):
        # 从 env_config 读取 server/client 以太网口
        server_ifs, client_ifs = CommonOperation.get_nic_relationships(
            rdma=False, nic_mode=RdmaMode.RoCE.value
        )
        # ...

    @classmethod
    def prepare(cls):
        # 保存 offload 状态、清理残留、创建 VLAN 子接口
        pass

    @classmethod
    def do(cls):
        # 抓包、ping、验证 VLAN tag
        pass

    @classmethod
    def post(cls):
        # 停止 tcpdump、删除子接口、恢复 offload、删除临时文件
        pass
```

### 缩进处理技巧

生成脚本时，多行代码块用 `textwrap.dedent` + `textwrap.indent` 处理，避免 f-string 多行插入导致缩进错误：

```python
import textwrap

def block(text: str, indent: int) -> str:
    # 只去掉首尾换行，保留缩进以便 dedent 正确计算
    return textwrap.indent(textwrap.dedent(text.strip("\n")), " " * indent)

# 使用示例
custom_methods = block('''
@classmethod
def _ensure_vlan_offloads(cls) -> None:
    ...
''', 4)
```

**注意**：不要在传入 `block()` 前对字符串调用 `.strip()`，因为 `.strip()` 会移除缩进空格，导致 `dedent` 失效。

## 常用验证命令

### VLAN 子接口

```bash
# 创建
ip link add link ens9f0np0 name ens9f0np0.100 type vlan id 100
ip addr add 192.168.100.1/24 dev ens9f0np0.100
ip link set ens9f0np0.100 up

# 删除
ip link del ens9f0np0.100

# STag 子接口
ip link add link ens9f0np0 name ens9f0np0.10 type vlan id 10 proto 802.1ad
```

### ethtool offload

```bash
# 查询
ethtool --features ens9f0np0 | grep vlan

# 设置
ethtool --features ens9f0np0 rx-vlan-offload on
ethtool --features ens9f0np0 tx-vlan-offload on
```

### 抓包验证

```bash
# server 物理口抓指定 VLAN
nohup tcpdump -i ens9f0np0 -nn -e -s 0 -w /tmp/capture.pcap vlan 100 &

# 解析
tcpdump -nn -e -r /tmp/capture.pcap
```

### 连通性

```bash
# client 从 VLAN 子接口 ping server
ping -c 5 -I ens9f0np0.100 192.168.100.1
```

## 天鹰 vs CX7 差异验证重点

1. **扩展 VLAN 类型**：天鹰支持 CTag、Outer VLAN1、Outer VLAN2、STag；CX7 主要支持 CTag
2. **多层 VLAN**：天鹰支持基于描述符的双层插入/剥离；CX7 不支持
3. **VSI VLAN**：天鹰支持基于 VSI 的插入/剥离；CX7 不支持
4. **队列 VLAN 剥离**：CX7 支持基于队列的 VLAN 剥离；天鹰不支持

## 复杂场景 TODO 标注

对于 DPDK、VSI、流表、互斥等复杂场景，生成脚本时应在关键位置标注 TODO：

- DPDK：PCI 地址、hugepage、testpmd 启动参数
- VSI：VF 创建、VSI VLAN 配置命令
- 流表：tc flower / DPDK rte_flow 具体规则
- 互斥：实际错误码、状态查询命令

## 常见陷阱

1. **子目录脚本找不到 `add_syspath`**：每个脚本目录需有自己的 `add_syspath.py`
2. **VLAN 子接口命名异常**：`ip_operation.py` 的 `add_vlan` 可能生成非预期接口名，建议直接用 `ip link add link ... name <if>.<vid> type vlan id <vid>`
3. **switchdev 模式无法设置 rx-vlan-offload**：需先切到 `legacy` 模式
4. **ping 不通**：检查 iptables / nftables / SELinux
5. **多行 f-string 缩进错误**：使用 `textwrap.dedent + indent`，避免 `.strip()`

## 参考文件

| 文件 | 说明 |
|------|------|
| `vlan.docx` | 天鹰 VLAN 需求文档（图片为主） |
| `天鹰VLAN测试用例.xlsx` | 拆分后的测试用例与测试点映射 |
| `gen_tianying_vlan_scripts_v2.py` | 脚本生成器 |
| `测试脚本文件夹/YYYY-MM-DD_HH-MM-SS/` | 生成的 52 个测试脚本 |
| `ps3/test/esat/nic100/scripts/multihost_vlan_offload_tc001.py` | 可参考的基础 VLAN 脚本 |

## 质量检查清单

生成脚本后确认：

- [ ] 全部脚本通过 `python -m py_compile`
- [ ] 样本脚本可通过 `--help` 正确加载框架
- [ ] 基础内核 VLAN 脚本可在双机环境跑通
- [ ] 复杂场景脚本中的 TODO 已明确标注
- [ ] 每个脚本的 `post()` 阶段能恢复环境
- [ ] 失败时按规范调用 `set_bug_type` + `create_bug`
