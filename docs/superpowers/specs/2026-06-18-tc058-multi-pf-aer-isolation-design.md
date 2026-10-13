# TC-058 多 PF AER 故障隔离测试 — 设计规格

## 1. 背景与目标

根据《多PF测试-测试用例.xlsx》中的 **TC-058**：
> 4 个 PF 进行业务期间，对 PF1-PF3（mlx5_1/2/3）注入 AER 异常，验证其他 PF（尤其是 PF0）的业务不受影响。

本设计的目标是为 TC-058 生成一个可执行、可维护、可测试的 NIC100 测试脚本，并遵循项目已有的 `multi_pf_test_tc0xx.py` 代码风格。

## 2. 需求澄清

- **测试对象**：双端口天蝎网卡，PF0/PF1 为 pport，PF2/PF3 为 vport。
- **关键步骤**：
  1. 配置 PF 数量为 4 并重启生效。
  2. 启动 OpenSM 组网，所有 IB 设备 Active。
  3. 在 4 个 PF 上并发启动 `ib_read_bw` 业务。
  4. 业务期间对 PF1-PF3 注入 AER（Bad TLP）异常。
  5. 检查 PF0 的 `ib_read_bw` 日志，确认带宽持续有效。
  6. 对 PF0 使用真实 base LID 执行查询类命令（mlxconfig / smpquery / perfquery / ibportstate）。
  7. `post` 阶段停止业务、恢复 IB 驱动、清理 AER 状态并检查 PF1-PF3 恢复。
- **通过标准**：PF0 业务在 PF1-PF3 AER 异常期间不中断，查询命令无异常；post 阶段环境恢复成功。

## 3. 设计决策

### 3.1 架构：脚本 + 可测试小工具模块

为了保持与现有 `multi_pf_test_tc055~tc057.py` 一致，主测试脚本仍继承 `ScriptBase`，采用 `prepare / do / post` 三阶段。但为了避免脚本文件过大并满足 TDD 要求，将**纯函数型、可独立测试**的小工具抽取到独立模块 `multi_pf_test_utils.py`：

- `parse_bandwidth_from_output(output, sample_lines=5)`：从 perftest 日志解析最近 N 行带宽均值。
- `is_pport(device)`：判断设备是否为 pport。
- `build_ib_read_bw_server_cmd(device, port, log_file)` / `build_ib_read_bw_client_cmd(...)`：构造 ib_read_bw 命令字符串。
- `build_query_commands(device, base_lid)`：构造查询类命令列表。

主脚本通过 import 使用这些小工具，保持 `do()` 方法内主要表达“做什么”，而不是字符串拼接细节。

### 3.2 不复用/不修改现有脚本

TC-055 ~ TC-057 已经存在且风格一致。本次不对它们做重构，避免引入回归风险。新的工具模块对旧脚本不可见，后续如有需要可再逐步迁移。

### 3.3 错误处理

延续 `ScriptBase` 模式：
- 关键步骤失败时填充 `bug_result`、`bug_expect`，设置 `BugTypeEnum.FUNCTION`，调用 `create_bug()` 抛出 `SxeException`。
- `do()` 阶段即使失败也要调用 `stop_all_traffic()` 停止业务。
- `post()` 阶段使用 `try/finally` 调用 `super().post()`，确保清理尽量执行。

### 3.4 AER 注入与恢复

- 注入前：清理目标 PF 的 AER 状态，关闭 UE severity 与 UE mask（防止错误升级为致命错误）。
- 注入：优先使用 `IpErrorInject.ep_bad_tlp_injection(bdf, exec_addr)`，失败则回退到 `setpci` 手动置位。
- 注入后：检查 UE 错误计数是否增加。
- post 阶段：清理 AER 状态，恢复 UE severity/mask，执行 `openibd force-restart` 恢复驱动，检查 PF1-PF3 重新出现在 `ibstat` 中。

## 4. 数据流

```text
multi_pf_test_tc058.py
  ├─ set_parameters / check_own_environment / prepare
  ├─ do
  │   ├─ set_pf_and_reset(4)  → mlxconfig + reboot
  │   ├─ start_opensm_networking()  → ibstat GUID → opensm
  │   ├─ start_all_traffic()  → multi_pf_test_utils.build_*_cmd
  │   ├─ inject_aer_error_on_device(PF1~PF3)  → IpErrorInject / setpci
  │   ├─ check_traffic_continuity(PF0)  → multi_pf_test_utils.parse_bandwidth_from_output
  │   └─ run_query_commands(PF0)  → multi_pf_test_utils.build_query_commands
  └─ post
      ├─ stop_all_traffic
      ├─ recover_ib_driver_in_post
      ├─ clean_aer_status_for_device(PF1~PF3)
      ├─ restore_aer_severity_mask_for_device(PF1~PF3)
      └─ check_inject_devices_recovered
```

## 5. 测试策略

严格按 TDD 进行：
1. 先删除已生成的 `multi_pf_test_tc058.py` 草案（TDD 要求不能基于已有实现写测试）。
2. 为 `multi_pf_test_utils.py` 编写单元测试，覆盖正常/异常输入、边界条件。
3. 实现 `multi_pf_test_utils.py`，让测试通过。
4. 实现 `multi_pf_test_tc058.py`，调用工具函数。
5. 验证：
   - 单元测试全部通过。
   - 脚本 `python -m py_compile` 通过。
   - 关键路径 checklist 无遗漏。

## 6. 文件清单

| 文件 | 说明 |
|------|------|
| `../../../ps3/test/esat/nic100/scripts/multi_pf/multi_pf_test_tc058.py` | TC-058 主测试脚本 |
| `ps3/test/esat/nic100/scripts/script_libs/multi_pf_test_utils.py` | 可单元测试的纯函数工具 |
| `ps3/test/esat/nic100/scripts/test/test_multi_pf_test_utils.py` | 工具模块单元测试 |
| `docs/superpowers/specs/2026-06-18-tc058-multi-pf-aer-isolation-design.md` | 本设计规格 |
| `docs/superpowers/plans/2026-06-18-tc058-multi-pf-aer-isolation-plan.md` | 实施计划（由 writing-plans 生成） |

## 7. 风险与假设

- **硬件依赖**：AER 注入、`ib_read_bw`、OpenSM 等依赖真实 IB 环境，单元测试无法覆盖，需保留手动 checklist。
- **权限**：`setpci`、PCI reset、`mlxconfig` 等命令需要 root 权限。
- **双端口形态**：脚本假设 `mlx5_0/1` 为 pport，`mlx5_2/3` 为 vport，与 TC-057 一致。
