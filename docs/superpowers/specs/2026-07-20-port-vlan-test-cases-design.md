# Port VLAN 测试用例与脚本生成设计

## 目标
将 `xmind文件夹/port vlan.xmind` 转换为项目标准的 Excel 测试用例，并同步生成可在 NIC100 框架下执行的 Python 自动化测试脚本。

## 背景
`port vlan.xmind` 描述了 SR-IOV 场景下由 PF 为 VF 强制指定 VLAN ID 的功能，涵盖 VLAN 基础概念、VLAN 卸载流程、场景组合、改配/持久性、RDMA VLAN 及规格边界等测试点。

## 输入
- `xmind文件夹/port vlan.xmind`

## 输出

| 产物 | 目标路径 |
|------|---------|
| Excel 测试用例 | `excel测试用例文件夹/2026-07-20_HH-MM-SS/PortVLAN_测试用例.xlsx` |
| Python 自动化脚本 | `ps3/test/esat/nic100/scripts/nic100/linux/vlan/tianying_port_vlan_*.py` |
| 一次性生成脚本 | `临时文件夹/2026-07-20_HH-MM-SS/generate_port_vlan_cases.py` |

## 方案
采用**一次性生成**方式：
1. 用 Python 解析 XMind `content.json`，提取测试点树。
2. 将 XMind 节点映射为标准化测试用例字段。
3. 使用 `openpyxl` 写入 Excel，沿用现有 18 列模板。
4. 为每个可自动化的测试点生成一个 Python 脚本，继承 `ScriptBase`，遵循 `tianying_vlan_*_kernel.py` 风格。

## 用例覆盖

基于 XMind 内容，生成以下方向的用例：

1. **VLAN 基础配置**
   - 创建 VF
   - 配置/取消 port vlan
   - 配置 802.1p QoS
   - 配置 VLAN 协议（802.1Q / 802.1ad）
   - 固定 VF MAC / spoofchk / trust 等辅助配置

2. **VLAN 卸载流程**
   - 发端 VF 发出无 tag 帧
   - 发端硬件插入 VLAN
   - 收端硬件过滤 VLAN
   - 收端硬件剥离 VLAN
   - 收端 VF 收到无 tag 帧

3. **场景组合测试**
   - PF 配置 VLAN / 未配置 VLAN
   - 配置 port vlan / 未配置 port vlan
   - VF 配置 VLAN / 未配置 VLAN
   - 验证：相同 VLAN ID 可通信，不同 VLAN ID 隔离，相同层数可通信

4. **改配与持久性**
   - 改配 VF VLAN 后复位 VF 生效
   - 改配 VF VLAN 后复位 PF 生效
   - 重启主机或卸载 PF core 驱动后配置丢失

5. **RDMA VLAN**
   - 单层 VLAN 通信
   - 双层 VLAN 通信

6. **规格边界**
   - 最多 16 个 PF
   - 每个 PF 最多 63 个 VF

## Excel 字段

沿用现有 `MultiHost_RDMA_测试用例.xlsx` 的 18 列结构：

`所属产品、所属模块、优先级、用例类型、脚本名称、测试编号、用例标题、前提条件、测试步骤、预期结果、检查项/测试点、测试场景、用例测试分类、负责人、作者、测试平台实现自动化、需求点/测试对象、物理环境`

## Python 脚本规范

- 文件位置：`ps3/test/esat/nic100/scripts/nic100/linux/vlan/`
- 命名：`tianying_port_vlan_<feature>_<mode>.py`
- 类继承：`ScriptBase`
- 核心方法：`set_parameters`、`check_own_environment`、`prepare`、`do`、`post`
- 公共库：`CommandOperation`、`CommonOperation`、`EthtoolOperation`、`log` 等
- 结果上报：失败时调用 `create_bug` 记录缺陷

## 验收标准

- [ ] Excel 文件生成成功，格式与现有模板一致
- [ ] 用例覆盖 XMind 中所有可测试的叶子节点
- [ ] Python 脚本语法正确，可编译通过
- [ ] 脚本位置正确，命名规范
- [ ] 生成脚本本身放入 `临时文件夹/`，不污染产物目录
