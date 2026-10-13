---
name: IB命令处理与回显解析
description: 指导NIC100框架下IB相关命令的执行、回显解析、交互式命令处理、错误修正与文件重定向检查。
---

# IB 命令处理与回显解析

## 命令回显解析

### mlxconfig 错误判断

- 正常回显中可能包含 "error" 字样，**不代表失败**。
- `-E-` 是 mlxconfig 明确的错误前缀，可作为判断失败的可靠依据。
- 如果命令重定向到文件，需用 `cat` 查看文件内容并检查是否符合预期。

```python
# 示例：检查 mlxconfig 输出中的 -E- 前缀
def is_mlxconfig_failed(output):
    return "-E-" in output
```

### 其他命令

- 仔细阅读正常回显示例，避免将正常输出中的 "error" 误判为失败。
- 对于关键命令，建议同时检查返回码和输出内容。

## 交互式命令处理

如果测试用例包含需要交互的命令（如需要输入 y/n），需改为非交互式：

- 使用 `-y`、`--yes`、`-f`、`--force` 等选项。
- 通过管道传递输入：`echo "y" | command`
- 使用 here document：`command << EOF\ny\nEOF`
- 在自动化脚本中使用 expect 模块或 `subprocess.Popen` 的 `stdin` 处理交互。

## 命令错误修正

发现用例中命令有误时，按以下顺序检查：

1. 命令语法是否正确。
2. 参数格式是否符合要求。
3. 设备名称是否正确（`mlx5_0`、`mlx5_1` 等）。
4. 命令选项是否适用（例如 `-C` vs `-d`）。
5. 执行环境是否正确（server vs client）。

## 文件重定向检查

某些命令输出重定向到文件后，需使用 `cat` 查看文件内容并判断是否符合预期，不能仅依赖命令返回码。

```bash
mlxconfig -d <bdf> q > /tmp/mlxconfig.log 2>&1
cat /tmp/mlxconfig.log
```

## 通用判断原则

| 场景 | 建议做法 |
|------|----------|
| 命令返回非零 | 通常判定失败，但需结合输出判断 |
| 输出含 "error" 但无 `-E-` | 不要直接判定失败，需结合上下文 |
| 输出含 `-E-` | 判定失败 |
| 重定向到文件 | 必须 `cat` 查看内容再判断 |
| 交互式命令 | 改为非交互式执行 |

## perftest 输出解析原则

`ib_send_bw` / `ib_send_lat` 等 perftest 工具的输出中，数据行后可能直接追加 teardown 阶段的异常信息，**中间没有换行或空格**：

```text
 #bytes     #iterations    BW peak[MiB/sec]    BW average[MiB/sec]   MsgRate[Mpps]
 2048       1000             0.00               5360.89		     2.744775received UMAD with an error: 0x200
failed to get mlid from MAD
Couldn't Unregister the Mcast group on the SM
Couldn't destroy all SEND resources
```

解析时应注意：

1. **正则不要严格要求行尾空白**（即不要用 `\s*$`），否则匹配不到数据行。
2. **应遍历所有匹配到的数据行**，而不是只取最后一行，避免某一行的 `BW average` 为 0 导致误判。
3. 多播场景下，只要存在任意一行 `BW average > 0`，以下异常可忽略：
   - `failed to get mlid from MAD`
   - `Couldn't Unregister the Mcast group on the SM`
   - `Couldn't destroy all SEND resources`
   - `received UMAD with an error`
4. 建议 server/client 日志**分别解析**，只要有一端存在有效带宽，就不应直接判失败。

## SL2VL 回显解析原则

`smpquery sl2vl` 输出包含标题行和数据行，解析时应注意：

1. **标题行只是索引**：`SL: | 0| 1| ...|15|` 表示 SL0~SL15 的列索引，不是 VL 值。
2. **数据行可能有额外空格**：例如 `ports: in  0, out  0:`，匹配时不应严格要求 `"out 0:"`。
3. **数据行前面有端口编号**：整行数字序列形如 `[0, 0, 0, 1, 2, 3, ...]`，前两个 `0` 分别是 `in` 和 `out` 端口编号，应跳过。
4. **解析失败要打印原始输出**：便于定位是格式差异还是命令本身失败。
5. **结合 OperVLs 判断期望**：`smpquery portinfo` 中的 `OperVLs` 决定实际可用 VL 数量，验证 SL2VL 期望时应据此动态计算，而不是硬编码 16 个 VL。

## 与其他模块的关系

本 skill 中的命令判断原则具有通用性，可被「以太网模块测试」、「RoCE模块测试」等模块引用或复用。
