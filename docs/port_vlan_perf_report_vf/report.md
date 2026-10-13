# Port VLAN（SR-IOV VF VLAN）对带宽性能影响测试报告

**用例编号**：TC-VLAN-PERF-001-VF  
**测试时间**：2026-07-22  
**测试脚本**：`ps3/test/esat/nic100/scripts/multihost_port_vlan_performance_tc001_vf.py`  
**报告路径**：`docs/port_vlan_perf_report_vf/report.md`

---

## 1. 测试目的

使用 SR-IOV VF Port VLAN 方式（`ip link set <pf> vf <vf_id> vlan <vlan_id>`）配置 VLAN 100，对比开启前后：

- `iperf3` TCP 带宽差异
- `dpdk-testpmd` PPS/BPS 差异

包长遍历 **64 / 128 / 256 / 512 / 1024** 字节，并验证 VLAN tag 真实出现在链路上。

---

## 2. 测试环境

| 角色 | IP:Port | 用户 | PF 网口 | VF 网口 | PF/VF PCI | 网卡 | 驱动 |
|------|---------|------|---------|---------|-----------|------|------|
| Server | 10.17.44.71:728 | root | ens9f0np0 | ens9f0v0 | 0000:38:00.0 / 0000:38:00.2 | ConnectX-8 | mlx5_core |
| Client | 10.17.44.73:3322 | root | ens9f0np0 | ens9f0v0 | 0000:38:00.0 / 0000:38:00.2 | ConnectX-8 | mlx5_core |

- 两端 PF 物理口直连。
- 每端创建 1 个 VF（PCI `0000:38:00.2`，接口 `ens9f0v0`）。
- DPDK 运行方式：**VF PCI + mlx5_core + verbs 模式**。
- 本环境未开启 IOMMU，testpmd 未使用 vfio-pci。

---

## 3. 测试方法

### 3.1 Port VLAN 配置方法

```bash
# 创建 VF
echo 1 > /sys/bus/pci/devices/0000:38:00.0/sriov_numvfs

# 无 VLAN 基准：VF 不绑定 VLAN（vlan 0）
ip link set ens9f0np0 vf 0 vlan 0

# Port VLAN 场景：VF 绑定 VLAN 100
ip link set ens9f0np0 vf 0 vlan 100
```

VF 绑定 VLAN 后，从 VF 发出的报文会自动打上 VLAN 100 tag，进入 VF 的报文会自动剥离 VLAN 100 tag。

### 3.2 iperf3 方法

1. 无 VLAN：两端 VF 设置 `vlan 0`，配置 `192.168.240.0/24`。
2. Port VLAN：两端 VF 设置 `vlan 100`，配置 `192.168.100.0/24`。
3. Server 在 VF 接口上启动 `iperf3 -s -p 5201`。
4. Client 在 VF 接口上执行：
   ```bash
   iperf3 -c <server_ip> -p 5201 -t 30 -B <client_ip> -l <pkt_len> -f m
   ```
5. 从 server 日志的 receiver 汇总行读取带宽（Mbps）。

### 3.3 DPDK testpmd 方法

1. 保持 VF 绑定 `mlx5_core`，加载 `mlx5_ib`。
2. 配置 1024 个 2M hugepage。
3. Server 在 VF PCI 上启动 rxonly 模式：
   ```bash
   dpdk-testpmd -l 0,1 -n 4 -a 0000:38:00.2 -- \
     --forward-mode=rxonly --portmask=0x1 --nb-cores=1 \
     --cmdline-file=/tmp/vf_tpmd_s_cmd.txt \
     --auto-start --stats-period=3
   ```
   其中命令文件内容为 `vlan set filter off 0`。
4. Client 在 VF PCI 上启动 txonly 模式：
   ```bash
   dpdk-testpmd -l 0,1 -n 4 -a 0000:38:00.2 -- \
     --forward-mode=txonly --portmask=0x1 --nb-cores=1 --txpkts=<pkt_len> \
     --eth-peer=0,ff:ff:ff:ff:ff:ff \
     --auto-start --stats-period=3
   ```
   说明：本环境 VF-to-VF 单播受硬件 FDB 限制无法到达对端 VF，因此使用广播目的 MAC 进行测试。VLAN 差异由 PF 硬件根据 VF VLAN 配置自动处理。
5. 从 `--stats-period=3` 打印的日志中提取最后的 `Rx-pps` / `Rx-bps`（server 侧）。

### 3.4 VLAN 生效验证

在 server PF 物理口 `ens9f0np0` 上抓包：

```bash
tcpdump -i ens9f0np0 -nn -e -s 0 -w /tmp/vf_verify.pcap
```

在 client VF 上运行 10s iperf3 VLAN 流量，最后读取 pcap 检查是否存在 `ethertype 802.1Q, vlan 100`。

---

## 4. 测试步骤与关键命令

### 4.1 环境准备（每端执行）

```bash
echo 1 > /sys/bus/pci/devices/0000:38:00.0/sriov_numvfs
modprobe mlx5_ib
echo 1024 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages
```

### 4.2 无 VLAN iperf3 基准

```bash
# server
ip link set ens9f0np0 vf 0 vlan 0
ip addr add 192.168.240.1/24 dev ens9f0v0
ip link set ens9f0v0 up
iperf3 -s -p 5201

# client
ip link set ens9f0np0 vf 0 vlan 0
ip addr add 192.168.240.2/24 dev ens9f0v0
ip link set ens9f0v0 up
iperf3 -c 192.168.240.1 -p 5201 -t 30 -B 192.168.240.2 -l <pkt_len> -f m
```

### 4.3 Port VLAN iperf3

```bash
# server
ip link set ens9f0np0 vf 0 vlan 100
ip addr add 192.168.100.1/24 dev ens9f0v0
ip link set ens9f0v0 up
iperf3 -s -p 5201

# client
ip link set ens9f0np0 vf 0 vlan 100
ip addr add 192.168.100.2/24 dev ens9f0v0
ip link set ens9f0v0 up
iperf3 -c 192.168.100.1 -p 5201 -t 30 -B 192.168.100.2 -l <pkt_len> -f m
```

### 4.4 无 VLAN testpmd

```bash
# 两端
ip link set ens9f0np0 vf 0 vlan 0

# server
printf 'vlan set filter off 0\n' > /tmp/vf_tpmd_s_cmd.txt
timeout 20 dpdk-testpmd -l 0,1 -n 4 -a 0000:38:00.2 -- \
  --forward-mode=rxonly --portmask=0x1 --nb-cores=1 \
  --cmdline-file=/tmp/vf_tpmd_s_cmd.txt --auto-start --stats-period=3

# client
timeout 15 dpdk-testpmd -l 0,1 -n 4 -a 0000:38:00.2 -- \
  --forward-mode=txonly --portmask=0x1 --nb-cores=1 --txpkts=<pkt_len> \
  --eth-peer=0,ff:ff:ff:ff:ff:ff --auto-start --stats-period=3
```

### 4.5 Port VLAN testpmd

```bash
# 两端
ip link set ens9f0np0 vf 0 vlan 100

# server / client 命令与 4.4 相同
```

### 4.6 VLAN 抓包验证

```bash
# server PF
nohup tcpdump -i ens9f0np0 -nn -e -s 0 -w /tmp/vf_verify.pcap >/tmp/tcpdump_vf_verify.log 2>&1 &
iperf3 -s -p 5201

# client VF
iperf3 -c 192.168.100.1 -p 5201 -t 10 -B 192.168.100.2 -l 256 -f m

# server PF
pkill -f 'tcpdump.*vf_verify.pcap'
tcpdump -nn -e -r /tmp/vf_verify.pcap | head -30
```

---

## 5. 测试结果

### 5.1 iperf3 带宽对比

| 包长 (B) | 无 VLAN (Mbps) | Port VLAN (Mbps) | 差异   |
|---------:|---------------:|-----------------:|-------:|
| 64       | 535            | 537              |   +0.37% |
| 128      | 1030           | 1040             |   +0.97% |
| 256      | 2000           | 2010             |   +0.50% |
| 512      | 3860           | 3780             |   -2.07% |
| 1024     | 7130           | 6990             |   -1.96% |

**结论**：开启 SR-IOV VF Port VLAN 后，iperf3 带宽波动在 ±2% 以内，可认为 VLAN tag 对 TCP 吞吐无显著影响。

### 5.2 DPDK testpmd 吞吐对比

server 侧 RX 统计（最后一条 `--stats-period=3` 输出）：

| 包长 (B) | 模式     | Rx-pps     | Rx-bps        | 估算 Mbps |
|---------:|----------|-----------:|--------------:|----------:|
| 64       | 无 VLAN   | 36,095,870 | 18,481,085,816 |    18,481 |
| 64       | Port VLAN | 39,324,793 | 20,134,294,488 |    20,134 |
| 128      | 无 VLAN   | 35,543,469 | 36,396,512,888 |    36,396 |
| 128      | Port VLAN | 38,663,311 | 39,591,231,032 |    39,591 |
| 256      | 无 VLAN   | 34,520,369 | 70,697,717,512 |    70,697 |
| 256      | Port VLAN | 37,371,757 | 76,537,360,368 |    76,537 |
| 512      | 无 VLAN   | 32,260,786 | 132,140,181,072 |   132,140 |
| 512      | Port VLAN | 34,809,144 | 142,578,255,232 |   142,578 |
| 1024     | 无 VLAN   | 30,189,528 | 247,312,620,464 |   247,312 |
| 1024     | Port VLAN | 30,864,956 | 252,845,720,784 |   252,845 |

**结论**：

- 64B/128B 小包受 CPU/单核转发限制，PPS 约 36~39 Mpps。
- 本次 VF testpmd 测试中，Port VLAN 场景的 PPS/BPS 略高于无 VLAN 场景（约 +7~10%）。分析可能原因：
  - 使用广播目的 MAC，无 VLAN 场景下的报文可能在硬件 e-switch 中走泛洪/特殊路径；
  - VLAN 100 场景下报文走硬件 VLAN 表项转发，路径更确定；
  - 测试波动也会导致 ±5% 以内差异。
- 综合来看，VF Port VLAN 未对 DPDK 小包转发性能产生负面影响；大包带宽随包长线性增长，VLAN 处理开销可忽略。

---

## 6. VLAN 生效验证

在 server PF `ens9f0np0` 上抓包，确认链路上存在 802.1Q VLAN 100 tag。捕获到的 ARP/mDNS 报文如下：

```text
02:01:16.803857 f2:a6:ff:47:5d:e2 > ff:ff:ff:ff:ff:ff, ethertype 802.1Q (0x8100), length 60: vlan 100, p 0, ethertype ARP (0x0806), Request who-has 192.168.100.1 tell 192.168.100.2, length 42
02:01:13.697805 b6:5c:03:91:df:9e > 01:00:5e:00:00:fb, ethertype 802.1Q (0x8100), length 127: vlan 100, p 0, ethertype IPv4 (0x0800), 192.168.100.1.5353 > 224.0.0.251.5353 ...
...
```

验证结果：**VLAN 100 tag 真实生效**，VF 发出的 iperf/ARP/mDNS 报文在 PF 链路上均携带 802.1Q VLAN 100。

完整抓包样本见：`docs/port_vlan_perf_report_vf/vlan_verify_tcpdump_sample.log`

---

## 7. 结论

1. **VLAN 生效性**：通过 `ip link set ens9f0np0 vf 0 vlan 100` 配置后，server PF 物理口 tcpdump 确认链路上存在 802.1Q VLAN 100 tag；iperf3 仅在两端 VF 均配置相同 VLAN 时才能通信。
2. **iperf3 性能影响**：开启 VF Port VLAN 后，64/128/256/512/1024 字节包长下带宽波动在 ±2% 以内，无显著性能下降。
3. **DPDK testpmd 性能影响**：VF Port VLAN 场景下各包长 PPS/BPS 与无 VLAN 场景基本持平甚至略高，VLAN 处理对硬件转发性能影响可忽略。
4. **总体结论**：在本测试环境（ConnectX-8、mlx5_core、VF、直连）下，使用 `ip link set <pf> vf 0 vlan 100` 方式的 Port VLAN 对 iperf3/testpmd 带宽性能影响极小。

---

## 8. 原始日志清单

所有原始日志已拉取到 `docs/port_vlan_perf_report_vf/`：

| 日志类型 | 文件命名 | 说明 |
|---------|---------|------|
| iperf server | `iperf_s_<mode>_<len>.log` | mode=`baseline`/`vlan`；len=64/128/256/512/1024 |
| iperf client | `iperf_c_<mode>_<len>.log` | 同上 |
| testpmd server | `testpmd_s_<len>_<mode>.log` | mode=`novlan`/`vlan100` |
| testpmd client | `testpmd_c_<len>_<mode>.log` | 同上 |
| VLAN 抓包样本 | `vlan_verify_tcpdump_sample.log` | tcpdump 读取 pcap 样本 |
| 汇总 | `summary.json` | iperf/testpmd 数值汇总 |

---

## 9. 环境恢复说明

测试完成后已执行：

- 停止所有 `iperf3`、`dpdk-testpmd`、tmux 会话。
- 将 VF VLAN 恢复为 0。
- 保留 VF 数量为 1（可根据需要 echo 0 彻底删除 VF）。
- 两端 PF 网口均保持 `mlx5_core` 驱动并 UP。

---

## 10. 注意事项与限制

1. **VF 单播限制**：本环境 VF-to-VF 单播报文因硬件 e-switch FDB 无法学习到对端 VF MAC，导致单播报文无法到达。因此 testpmd 使用广播目的 MAC `ff:ff:ff:ff:ff:ff` 进行测试，测试结果仍可有效对比 VLAN/no-VLAN 差异。
2. **VF MAC**：`ip link set <pf> vf <id> mac <mac>` 设置的是 VF 管理员 MAC，实际 `ens9f0v0` 接口可能显示不同 MAC，但不影响 VF 通信。
3. **DPDK verbs 模式**：本环境 `dpdk-testpmd` 使用 rdma-core/libmlx5 的 verbs 路径，必须保持 `mlx5_core` 绑定并加载 `mlx5_ib`。
4. **iperf3 小包**：`-l 64` 表示应用层 buffer 大小，实际 TCP MSS 仍由协议栈决定，64B 场景下实测吞吐约 535 Mbps。
