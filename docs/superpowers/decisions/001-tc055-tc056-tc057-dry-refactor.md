# ADR-001: TC-055/TC-056/TC-057 代码重复（DRY）处理决定

## 状态

Accepted（已知技术债务，待后续专项重构）

## 背景

在生成 TC-057（PF0 AER 异常隔离）测试脚本时，代码审查发现该脚本与 TC-055（PF0 function 复位隔离）、TC-056（PF1-PF3 function 复位隔离）存在大量重复代码：

- PF 数量设置与服务器重启流程
- OpenSM 组网启动
- ib_read_bw 业务启动/停止/带宽检查
- PF 查询类命令（mlxconfig q / smpquery / perfquery / ibportstate）
- 驱动恢复与清理流程
- 通用工具方法（get_pf_count、get_device_bdf、get_base_lid 等）

## 决定

当前阶段不对 TC-055/TC-056 进行重构，原因如下：

1. **避免回归风险**：TC-055/TC-056 是已存在且经实际运行的脚本，直接修改可能引入不可预期的行为变更。
2. **保持本次改动范围可控**：本次任务目标是生成 TC-057 并走通 Superpowers 审查流程，不应扩大为跨文件重构。
3. **TC-057 已可独立运行**：通过继承 `ScriptBase` 并复用现有项目工具类，TC-057 已满足功能需求。

作为替代方案：

- 在 TC-057 文件顶部 `@changelog` 中明确标注该 TODO。
- 后续安排独立重构任务，创建 `MultiPfFaultIsolationBase` 公共基类或 `multi_pf_fault_isolation_mixin.py`Mixin，将公共方法抽取出来。
- 重构时同步更新 TC-055/TC-056/TC-057，并补充回归测试。

## 影响

- **短期**：三个脚本存在维护重复，后续修改公共逻辑时需要同时修改多处。
- **长期**：完成重构后，可降低维护成本，提高一致性。

## 相关文件

- `../../../ps3/test/esat/nic100/scripts/multi_pf/multi_pf_test_tc055.py`
- `../../../ps3/test/esat/nic100/scripts/multi_pf/multi_pf_test_tc056.py`
- `../../../ps3/test/esat/nic100/scripts/multi_pf/multi_pf_test_tc057.py`
