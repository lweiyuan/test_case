---
name: IB网卡配置与恢复
description: 指导NIC100框架下IB网卡的PF/VF数量修改、重启检测、function复位与IB驱动恢复流程。
---

# IB 网卡配置与恢复

## PF 数量修改

1. 使用 `mlxconfig` 修改 `NUM_OF_PF` 参数。
2. **必须重启服务器**才能生效；仅重新加载驱动或复位设备通常不足够。
3. 若当前 PF 数量与目标值相同，可跳过设置和重启（除非用例专门测试"设置为原值"场景）。

```python
def configure_pf_if_needed(cls, target_pf_count, exec_addr):
    current_pf = cls.get_pf_count(exec_addr)
    if current_pf == target_pf_count:
        log.info(f"PF count is already {target_pf_count}, skipping configuration and reboot")
        return
    # 执行 mlxconfig 设置和重启
    cls.set_pf_count(target_pf_count, exec_addr)
    cls.reboot_and_wait(exec_addr)
```

## 重启检测

执行 reboot 后不是立即重启，需注意检测时机：

1. 发送重启命令。
2. 等待约 30 秒让服务器开始重启流程。
3. 循环检测服务器是否上线（建议通过执行 `echo ping` 等命令并验证输出）。
4. 设置合理超时（如 300 秒）。

```python
def reboot_and_wait(cls, exec_addr, timeout=300):
    reboot_cmd = "nohup sh -c 'sleep 2 && reboot' > /dev/null 2>&1 &"
    CommandOperation.execute_command_with_error(reboot_cmd, exec_addr)
    time.sleep(30)
    if not cls.wait_for_server_availability(exec_addr, timeout=timeout):
        log.error("Server did not come back after reboot")
        cls.create_bug("服务器重启后未在超时时间内恢复")
```

## function 复位与恢复流程

对某个 function（PF/VF）进行复位及恢复时：

1. **复位命令**：
   ```bash
   echo 1 | sudo tee /sys/bus/pci/devices/$VF_BDF/reset
   ```
   - `$VF_BDF` 为待复位设备的 PCI BDF 地址，如 `0000:03:00.1`。

2. **等待设备从 `ibstat` 中消失**：
   ```bash
   while ibstat -l | grep -q "^${DEVICE_NAME}$"; do sleep 1; done
   ```

3. **停止所有 OpenSM 进程**：
   执行 `/etc/init.d/openibd force-restart` 前，必须先停止所有 OpenSM 进程，避免驱动重启过程中 OpenSM 与子网状态冲突：
   ```bash
   pkill -9 -f opensm
   ```

4. **恢复 IB 驱动**：
   ```bash
   /etc/init.d/openibd force-restart
   ```

5. **等待 10 秒**，让驱动和网络状态稳定后再继续操作。

## 配置变更后的检查项

- PF 数量是否与目标一致
- `ibstat -l` 是否能看到预期设备
- 端口状态是否为 Active / LinkUp
- OpenSM 是否需要重新启动
- GUID、LID 是否与预期一致

## ipoib 模式设置与恢复

某些多播用例（如 MC-19）要求 ipoib 接口工作在 `connected` 模式。测试脚本应在 `prepare` 阶段检查并设置，在 `post` 阶段恢复原始模式，避免影响后续用例。

### 检查当前模式

```bash
cat /sys/class/net/<iface>/mode
```

### 设置为 connected 模式

```bash
ip link set <iface> down
echo connected > /sys/class/net/<iface>/mode
ip link set <iface> up
```

### Python 自动化示例

```python
IPOIB_MODE_FILE = "/sys/class/net/{iface}/mode"

def ensure_ipoib_connected(exec_addr, iface):
    status, result, _ = CommandOperation.execute_command_with_error(
        f"cat {IPOIB_MODE_FILE.format(iface=iface)}", exec_addr
    )
    current_mode = result.strip().lower()
    if current_mode == "connected":
        return current_mode

    CommandOperation.execute_command_with_error(
        f"ip link set {iface} down && "
        f"echo connected > {IPOIB_MODE_FILE.format(iface=iface)} && "
        f"ip link set {iface} up",
        exec_addr,
    )
    return current_mode  # 返回原始模式，用于 post 阶段恢复

def restore_ipoib_mode(exec_addr, iface, orig_mode):
    if not orig_mode or orig_mode == "connected":
        return
    CommandOperation.execute_command_with_error(
        f"ip link set {iface} down && "
        f"echo {orig_mode} > {IPOIB_MODE_FILE.format(iface=iface)} && "
        f"ip link set {iface} up",
        exec_addr,
    )
```

### 注意事项

1. 修改模式前必须先 `ip link set down`，否则 `echo` 写入可能失败。
2. 设置完成后应验证 `/sys/class/net/<iface>/mode` 是否已变为目标值。
3. 原始模式应在类属性或全局变量中保存，确保 `post` 阶段能恢复。
4. 如果脚本在 `check_own_environment()` 中因模式非 `connected` 而直接跳过，应改为在 `prepare()` 中主动设置并在 `post()` 中恢复。

## 常见问题

- **mlxconfig 修改后未生效**：忘记重启服务器，或当前 PF 数量已等于目标值导致跳过。
- **复位后设备不恢复**：未先停止 OpenSM 就执行 `openibd force-restart`。
- **重启后检测超时**：等待时间不足 30 秒，或检测命令本身未正确执行。
