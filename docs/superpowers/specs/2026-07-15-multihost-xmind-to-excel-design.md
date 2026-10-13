# multi host.xmind 生成测试用例 Excel 设计文档

## 目标

依据 `xmind文件夹/multi host.xmind` 生成一份符合项目规范的 `MultiHost_RDMA_测试用例.xlsx`，并删除旧脚本 `ps3/test/esat/nic100/framework/biz/excel/generate_multihost_cases_from_xmind.py`。

## 方案

采用 **一次性生成（不保留脚本）** 方案：

1. 删除旧生成脚本。
2. 使用一次性 Python 代码解析 XMind（zip + JSON）。
3. 按项目 **测试用例生成** skill 的规范展开 `[FTx]` / `[TCx]` 节点与变化因子。
4. 输出 Excel 到 `excel测试用例文件夹/YYYY-MM-DD_HH-MM-SS/MultiHost_RDMA_测试用例.xlsx`。
5. 不保留新的生成脚本到仓库。

## 输出格式

Excel 列头：

- 所属产品 / 所属模块 / 优先级 / 用例类型 / 脚本名称 / 测试编号 / 用例标题
- 前提条件 / 测试步骤 / 预期结果 / 检查项/测试点 / 测试场景
- 用例测试分类 / 负责人 / 作者 / 测试平台实现自动化 / 需求点/测试对象 / 物理环境

## 变化因子处理

- 解析 `变化因子` 节点，识别 `[TE1]` / `[TE2]` / `[TE3]` 等维度。
- 对 `A/B/C 任选一个` 类文本，解析候选列表并为每个用例选取具体值。
- 业务类型映射到对应 perftest 命令（如 rdma read → ib_read_bw）。

## 验收标准

- 旧脚本已删除。
- 新生成的 Excel 文件位于 `excel测试用例文件夹/` 下按时间命名的子目录中。
- Excel 中至少包含 XMind 中 `[FT]` 与 `[TC]` 节点对应的所有用例。
- 不新增任何生成脚本到仓库。
