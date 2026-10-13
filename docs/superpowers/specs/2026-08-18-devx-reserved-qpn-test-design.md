# DevX Reserved QPN 测试设计

## 1. 目标与范围

为 mlx5 DevX 的 **Reserved QPN** 创建能力增加一套自动化测试脚本，覆盖正常、异常、边界、压力、跨 device、生命周期等场景，与现有 PD/QP/CQ/SRQ 脚本在风格、编号、用例模板上保持一致。

测试层：**DevX 命令层**，即直接通过 `CREATE_GENERAL_OBJECT`（`0xa00`）+ `MLX5_OBJ_TYPE_RESERVED_QPN`（`0x002C`）创建/销毁 Reserved QPN block。

## 2. 基本原理

Reserved QPN 不是独立 opcode 对象，而是通用对象的一种：

| 字段 | 值 | 说明 |
|---|---|---|
| opcode | `0xa00` | `MLX5_CMD_OP_CREATE_GENERAL_OBJECT` |
| obj_type | `0x002C` | `MLX5_OBJ_TYPE_RESERVED_QPN` |
| log_obj_range | N | 一次申请 `2^N` 个连续 QPN |
| object_id（返回值） | first_qpn | 返回的 object_id 就是该 block 的第一个 QPN |

输入 buffer 结构：`general_obj_in_cmd_hdr`（16 bytes）+ `reserved_qpn_bits`（16 bytes，全 0），共 **32 bytes**。  
输出 buffer：`general_obj_out_cmd_hdr`（16 bytes），其中 `obj_id` 字段为 first_qpn。

## 3. 前置条件

1. RDMA 设备为 mlx5，且 pyverbs mlx5 DevX 可用（同现有脚本）。
2. 设备支持 General Object 机制且支持 `MLX5_OBJ_TYPE_RESERVED_QPN`。
3. helper 在 prepare 阶段通过 `ctx.devx_general_cmd()` 查询 HCA cap，获取：
   - `general_obj_types` 中 bit `0x2C` 是否置位；
   - `log_reserved_qpn_granularity`（或 `log_reserved_qpns_per_obj`）以确定 block 大小上限。
4. 若不支持，脚本按项目约定记录 `skip` 或失败。

## 4. Helper 扩展（`devx_qp_helper.py`）

新增两个函数：

```python
def query_reserved_qpn_caps(ctx) -> (supported: bool, max_log_range: int):
    """通过 QUERY_HCA_CAP 查询 general_obj_types 和 cap_2 中的 reserved qpn 粒度。"""

def create_reserved_qpn(ctx, log_obj_range: int) -> (Mlx5DevxObj, first_qpn: int):
    """构造 32B create_reserved_qpn_in buffer：
    opcode=0xa00, obj_type=0x002C, log_obj_range=log_obj_range
    调用 Mlx5DevxObj(ctx, in_buf, 32)，从 out_view 解析 obj_id 作为 first_qpn。
    """
```

销毁直接复用 `obj.close()`，可再包一层 `destroy_reserved_qpn(obj)` 保持风格统一。

## 5. 脚本清单（14 条）

编号接 SRQ（004），QPN 用 **005**。

| 序号 | 脚本名 | 场景 | 核心验证点 |
|---|---|---|---|
| 001 | `nic_linux_rdma_devx_f_06_53_005_001_devx_create_qpn_normal_create_qpn.py` | 正常创建 | 能创建 block，first_qpn 非 0，block 内 QPN 连续 |
| 002 | `nic_linux_rdma_devx_f_06_53_005_002_devx_create_qpn_abnormal_create_qpn.py` | 异常参数 | 错误 obj_type、超范围 log_obj_range、零长度等返回失败 |
| 003 | `nic_linux_rdma_devx_f_06_53_005_003_devx_create_qpn_stress_create_qpn.py` | 压力 | 连续创建/销毁大量 block，first_qpn 不重复 |
| 004 | `nic_linux_rdma_devx_f_06_53_005_004_devx_create_qpn_boundary_create_qpn.py` | 边界 | log_obj_range=0（1 个 QPN）和 max 粒度 |
| 005 | `nic_linux_rdma_devx_f_06_53_005_005_devx_create_qpn_cross_device_create_qpn.py` | 跨 device | 在 mlx5_0 / mlx5_1 上分别创建，QPN 范围独立 |
| 006 | `nic_linux_rdma_devx_f_06_53_005_006_devx_create_qpn_context_rebuild_create_qpn.py` | 上下文重建 | 销毁 context 后重建，QPN block 仍能正常分配 |
| 007 | `nic_linux_rdma_devx_f_06_53_005_007_devx_create_qpn_long_term_stability_create_qpn.py` | 长期稳定性 | 循环申请-释放 N 次，无泄漏、无重复 |
| 008 | `nic_linux_rdma_devx_f_06_53_005_008_devx_create_qpn_multi_context_create_qpn.py` | 多 context | 同一设备上多个 Mlx5Context 分别申请 QPN，互不冲突 |
| 009 | `nic_linux_rdma_devx_f_06_53_005_009_devx_create_qpn_lifecycle_anomaly_create_qpn.py` | 生命周期异常 | block 内部分 QPN 未释放时直接销毁对象等异常路径 |
| 010 | `nic_linux_rdma_devx_f_06_53_005_010_devx_create_qpn_alloc_pattern_create_qpn.py` | 分配模式 | 按 1/2/4/8/... 等典型 block 大小创建 |
| 011 | `nic_linux_rdma_devx_f_06_53_005_011_devx_create_qpn_random_order_create_qpn.py` | 随机顺序 | 随机创建/销毁不同大小 block，验证无冲突 |
| 012 | `nic_linux_rdma_devx_f_06_53_005_012_devx_create_qpn_out_view_check_create_qpn.py` | 输出校验 | 校验 out_view 的 status/syndrome/obj_id 格式 |
| 013 | `nic_linux_rdma_devx_f_06_53_005_013_devx_create_qpn_cross_device_alternating_stress_create_qpn.py` | 交替跨 device 压力 | mlx5_0/mlx5_1 上交替创建释放 |
| 014 | `nic_linux_rdma_devx_f_06_53_005_014_devx_create_qpn_property_access_stability_create_qpn.py` | 属性访问稳定性 | 反复读取 first_qpn、block 大小等属性，值稳定 |

## 6. 目录与命名

- 脚本目录：`ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/`
- Helper：`ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/devx_qp_helper.py`
- 日志目录：沿用 `ps3/test/esat/nic100/scripts/nic800/linux/rdma/devx/script_case/qpn_run_logs/`（可选）

## 7. Excel / 用例更新

沿用“合并到同一个 Excel、同一个 sheet”的要求，新增 14 条 QPN 用例行，字段与 PD/QP/CQ/SRQ 对齐：

- 用例编号：`f_06_53_005_001` ~ `f_06_53_005_014`
- 对象：`RDMA Reserved QPN`
- opcode：`CREATE_GENERAL_OBJECT` + `MLX5_OBJ_TYPE_RESERVED_QPN`
- 测试步骤：第一步为前置检查（查询 cap），第二步开始创建/验证/释放。

## 8. 清理与异常处理

- 每个脚本 `post()` 阶段显式关闭所有 `Mlx5DevxObj`。
- 若能力不支持，记录 skip 并清理已创建资源。
- 跑测失败时通过 `exit_all_ipvbs` 清理远端 `ipvbs_s` 进程（复用现有机制）。

## 9. 依赖与风险

| 依赖 | 说明 |
|---|---|
| `ctx.devx_general_cmd()` | 需要确认当前 pyverbs 版本支持；若不支持，helper 里降级为“直接尝试创建”。 |
| `log_reserved_qpn_granularity` 字段名/偏移 | 不同 rdma-core/固件版本可能叫 `log_reserved_qpns_per_obj`，helper 里做兼容。 |
| 远端 `devx_qp_helper.py` 自动部署 | 沿用现有 `_deploy_helper_if_needed` 机制。 |
