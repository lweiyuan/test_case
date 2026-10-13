---
name: DPDK模块测试
description: 指导NIC100框架下DPDK模块的测试要点，包括DPDK环境配置、驱动绑定、 hugepage、testpmd和性能测试。
---

# NIC100 DPDK 模块测试指南

## 测试范围

- DPDK 环境准备（hugepage、驱动绑定）
- DPDK 应用编译与运行
- testpmd 基础转发与性能测试
- DPDK 与内核驱动切换
- PMD 相关参数验证

## 核心命令与工具

| 命令/工具 | 用途 |
|-----------|------|
| `dpdk-devbind.py` | 网卡与 DPDK 驱动绑定/解绑 |
| `testpmd` | DPDK 基础转发与性能测试 |
| `dpdk-hugepages.py` | hugepage 配置 |
| `lspci` / `pcie_operation.py` | 查看 PCIe 设备 |
| `ethtool` | 查看网卡基础信息 |

## 环境准备

1. **加载 VFIO/IGB_UIO 驱动**
   ```bash
   modprobe vfio-pci
   # 或
   modprobe uio
   insmod igb_uio.ko
   ```

2. **配置 hugepage**
   ```bash
   echo 1024 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages
   ```

3. **绑定网卡到 DPDK 驱动**
   ```bash
   dpdk-devbind.py --bind=vfio-pci <pci_addr>
   ```

## testpmd 常用命令

```bash
# 启动双端口转发
testpmd -l 0-3 -n 4 -- -i --portmask=0x3 --nb-cores=2

# 常用交互命令
start tx_first    # 开始转发
stop              # 停止
show port stats all
set fwd mac       # 设置二层转发模式
```

## 脚本层注意

- 使用 `pcie_operation.py` / `pcie_info.py` 获取 PCI 地址
- 绑定/解绑操作前后记录网卡状态，便于恢复
- DPDK 测试前后务必恢复内核驱动，避免影响后续用例

## 脚本位置

- 公共库：`ps3/test/esat/nic100/scripts/script_libs/pcie_operation.py`
- 辅助库：`ps3/test/esat/nic100/scripts/script_libs/pcie_info.py`

## 注意事项

1. DPDK 占用 CPU 核心，注意核心隔离和 NUMA 对齐
2. hugepage 配置需考虑内存大小和测试需求
3. 绑定 DPDK 驱动后，内核协议栈不再管理该网口
4. 测试结束后在 `post` 阶段解绑并恢复内核驱动
5. DPDK 版本与网卡驱动版本需匹配
