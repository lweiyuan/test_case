#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 VF 测试设计 .xmind（XMind 10 原生 content.json 格式）。
以原始可正常打开的文件为模板，保留 theme/metadata/manifest/resources/缩略图，
仅替换 rootTopic 主题树；rootTopic.extensions 必须为「数组」（否则 XMind 报
"t.extensions.some is not a function"）。
"""
import json, os, uuid, zipfile, shutil

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_XMIND = os.path.join(BASE, "VF测试设计.xmind")
TEMPLATE_XMIND = os.path.join(BASE, "以太Linux驱动_txsched_补全版.xmind")


def T(title, children=None):
    return {"title": title, "children": children or []}


def steps(seq):
    return [f"{i+1}. {s}" for i, s in enumerate(seq)]


# ---------------------------------------------------------------------------
# 主题树数据
# ---------------------------------------------------------------------------
tree = T("VF 限速测试设计", [
    T("VF 学习", [
        T("VF 是什么", [
            "VF（Virtual Function，虚拟功能）是 SR-IOV（Single Root I/O Virtualization，单根 I/O 虚拟化）技术中的虚拟 PCIe 设备",
            "SR-IOV 是 PCI Express 规范的扩展，它使一个物理 PCIe 设备（PF）看起来像多个虚拟设备（VF），从而在虚拟化环境中实现近原生的网络性能",
            "物理功能 PF（Physical Function）：设备的主要特性，宣传设备的 SR-IOV 能力，负责管理 VF 的创建与配置",
            "虚拟功能 VF：由 PF 通过 SR-IOV 能力寄存器动态控制分配，每个 VF 拥有独立的 PCI 配置空间、总线/设备/功能编号（路由 ID RID）和 PCI 内存空间",
            "VF 在内核中被视为热插拔的 PCI 设备，拥有自己的设备驱动程序，可正常工作并显示为真实的 PCI 设备",
            "每个 PF 和 VF 都有唯一的 PCIe 请求者 ID（RID），IOMMU 据此区分不同流量流并在 PF/VF 间应用内存与中断转换",
        ]),
        T("VF 的作用", [
            "性能提升：VF 可直通（passthrough）到虚拟机/容器，流量绕过软件交换机层，接近裸机性能",
            "资源隔离：VF 与 PF 及其他 VF 共享物理资源（内存、网络端口），但通过 RID/IOMMU 隔离，互不影响",
            "虚拟化支持：一个物理网卡可虚拟出多个 VF，分配给不同 VM/容器/命名空间使用（DPDK、kvm、vdpa、k8s 等）",
            "独立配置：每个 VF 可独立配置 MAC、VLAN、限速、trust、spoofchk、state 等属性，互不干扰",
            "网络资源最大化：一个 PF 下可创建多个 VF（上限可达 1008 个），充分复用物理端口带宽",
            "调度树子节点：在网卡 tx_sched 调度树中，VF 作为独立子树节点挂载，支持独立限速（PIR/CIR）与 QoS",
        ]),
        T("相关指令及解释", [
            T("创建 / 删除 VF（sysfs）", [
                "启用 SR-IOV（创建 VF）：echo <数量> > /sys/bus/pci/devices/<BDF>/sriov_numvfs（如 echo 4 > .../sriov_numvfs）",
                "禁用 SR-IOV（删除 VF）：echo 0 > /sys/bus/pci/devices/<BDF>/sriov_numvfs",
                "查看最大支持的 VF 数：cat /sys/bus/pci/devices/<BDF>/sriov_totalvfs",
                "查看当前已创建的 VF 数：cat /sys/bus/pci/devices/<BDF>/sriov_numvfs",
                "自动探测开关：echo 1|0 > /sys/bus/pci/devices/<BDF>/sriov_drivers_autoprobe",
                "BDF（Bus/Device/Function）为 PCI 地址，如 0000:01:00.0",
            ]),
            T("切换 eswitch 模式", [
                "切换为 switchdev：devlink dev eswitch set pci/0000:01:00.0 mode switchdev",
                "切换为 legacy：devlink dev eswitch set pci/0000:01:00.0 mode legacy",
                "查看当前模式：devlink dev eswitch show pci/0000:01:00.0",
                "switchdev 模式下会为每个 VF 创建 representor（代表端口）设备，可加入网桥",
            ]),
            T("ip link set vf 配置命令", [
                "通用格式：ip link set dev <pf> vf <NUM> <选项>（pf 为物理网卡名，NUM 为 VF 序号 0 起）",
                "设置 VF 的 MAC 地址：ip link set dev <pf> vf <N> mac <LLADDR>",
                "设置 VF 的 VLAN（发加 tag、收过滤并剥 tag）：ip link set dev <pf> vf <N> vlan <VID> [qos <0-7>] [proto <802.1Q|802.1ad>]",
                "设置 VF 最大发送带宽 PIR：ip link set dev <pf> vf <N> max_tx_rate <Mbps>（0 关闭限速）",
                "设置 VF 最小保证带宽 CIR：ip link set dev <pf> vf <N> min_tx_rate <Mbps>（须 ≤ max_tx_rate）",
                "（旧版）设置 VF 发送带宽：ip link set dev <pf> vf <N> rate <Mbps>（推荐改用 max_tx_rate）",
                "开启/关闭防欺骗检查：ip link set dev <pf> vf <N> spoofchk on|off",
                "设置 VF 链路状态：ip link set dev <pf> vf <N> state auto|enable|disable",
                "设置 VF trust（允许设置敏感/安全相关特性）：ip link set dev <pf> vf <N> trust on|off",
                "IB VF 的 Node GUID：ip link set dev <pf> vf <N> node_guid <eui64>",
                "IB VF 的 Port GUID：ip link set dev <pf> vf <N> port_guid <eui64>",
                "查看 VF 配置回显：ip link show <pf>",
            ]),
            T("队列配置命令", [
                "修改 VF 收发队列数：ethtool -L <vf设备名> tx <n> rx <n>",
                "查看 VF 队列能力：ethtool -l <vf设备名>",
                "PF 创建多个 VF：echo <数量> > /sys/class/net/<pf>/device/sriov_numvfs",
            ]),
            T("VF 划组限速命令（devlink rate）", [
                "查看所有 rate 对象：devlink port function rate show",
                "创建 VF 分组节点：devlink port function rate add pci/0000:03:00.0/<组名>",
                "设置 VF 分组共享带宽 SRL（tx_share=最小共享，tx_max=最大）：devlink port function rate add pci/0000:03:00.0/<组名> tx_share 1Gbit tx_max 10Gbit",
                "设置单个 VF 限速：devlink port function rate set pci/0000:03:00.0/<vf序号> tx_share 2Mbit tx_max 10Mbit",
                "将 VF 加入分组：devlink port function rate set pci/0000:03:00.0/<vf序号> parent <组名>",
                "解除 VF 分组：devlink port function rate set pci/0000:03:00.0/<vf序号> noparent",
                "设置严格优先级仲裁：devlink port function rate set ... tx_priority <N>",
                "设置加权公平仲裁：devlink port function rate set ... tx_weight <N>",
                "删除 VF 分组（需先解除所有子成员）：devlink port function rate del pci/0000:03:00.0/<组名>",
                "rate 对象类型：leaf（对应单个 VF/端口，由驱动创建）；node（用户创建的分组，可含多个 leaf）",
                "单位：bit/kbit/mbit/gbit、bps/kbps/mbps/gbps；0 表示不限速",
            ]),
            T("检查命令", [
                "查看 VF 设备列表：ip link show | grep -E 'eth|ens'（VF 设备通常带 v 后缀）",
                "查看 PF 下所有 VF 配置：ip link show <pf>",
                "查看 PCI 设备：lspci | grep -i ethernet / lspci | grep -i virtual",
                "查看 RDMA 设备与 netdev 映射：ibdev2netdev / rdma link -jp",
                "查看 IB/RDMA 设备状态：ibstat / ibstatus",
            ]),
        ]),
        T("完整测试流程", [
            T("1. 环境准备", [
                "systemctl stop lldpad（停止链路层发现协议服务）",
                "设置 l2-fwd-offload 为 off（关闭二层转发卸载）",
                "确认所有 port 已物理互通",
                "在 env_config.ini 或配置脚本中正确配置 RDMA 设备关系",
                "加载 PF core 驱动与以太驱动（如 insmod sxe3.ko / sxe3e.ko）",
            ]),
            T("2. 创建 VF", [
                "切换 eswitch mode 为 legacy 或 switchdev",
                "echo <数量> > sriov_numvfs 创建多个 VF",
                "检查是否生成对应的 VF 设备",
                "检查调度树中是否存在 VF 子树（debugfs）",
            ]),
            T("3. 配置 VF", [
                "ethtool -L 修改 VF 的队列数",
                "检查 VF 子树下的 q 和 qg 节点是否随之变化",
                "ip link set dev <pf> vf <N> max_tx_rate / min_tx_rate 设置 PIR/CIR",
                "（可选）ip link set vf 设置 MAC、VLAN、spoofchk、trust、state 等",
                "（可选）devlink port function rate 设置 VF 划组限速 SRL",
            ]),
            T("4. 检查调度树与配置生效", [
                "debugfs 获取 VF 调度子树信息，核对 pir 和 cir 值与设置一致",
                "ip link show 回显确认限速配置",
                "修改 PIR/CIR 后确认调度子树值同步变更",
            ]),
            T("5. 打流验证", [
                "iperf 进行 TCP 打流，验证带宽是否满足 max_tx_rate/min_tx_rate",
                "perftest（ib_read_bw / ib_write_bw / ib_send_bw）进行 RDMA 打流",
                "验证限速：实际带宽 ≤ max_tx_rate，且不低于 min_tx_rate（带宽充足时）",
            ]),
            T("6. 清理与恢复", [
                "删除 VF：echo 0 > sriov_numvfs",
                "检查调度树中 VF 子树是否被清空（无 VF teid 节点）",
                "恢复 eswitch mode、驱动、网络配置",
            ]),
        ]),
    ]),
    T("测试分析", [
        T("变化因子", [
            T("eswitch mode", ["legacy", "switchdev"]),
            T("VF 数量", ["1", "2", "64", "1008"]),
            T("限速配置", ["max_tx_rate（PIR）", "min_tx_rate（CIR）"]),
            T("队列配置", ["ethtool -L 修改 VF 队列数"]),
            T("发包方式", ["iperf TCP 打流", "perftest RDMA 打流"]),
            T("虚拟化形态", ["透传内核", "dpdk", "vdpa", "kvm", "k8s"]),
        ]),
        T("检查手段", [
            "debugfs 获取 VF 调度子树信息，查询 VF 的 pir 和 cir 值",
            "ip link 回显确认限速配置",
            "对 VF 打流验证实际带宽",
        ]),
        T("规格约束", [
            "单一 VF 限速不能大于父节点的限速",
            "max_tx_rate ≥ min_tx_rate",
            "限速取值范围：1 ~ 速率大小/1000",
            "VF 数量上限 1008 个",
        ]),
    ]),
    T("基础功能", [
        T("进内核 PF 配置 VF 限速", [
            T("前提条件", [
                "systemctl stop lldpad",
                "设置 l2-fwd-offload 为 off",
                "所有的 port 都已物理互通",
                "用户已在 env_config.ini 或配置脚本中正确配置 RDMA 设备关系",
            ]),
            T("legacy 模式 - 内核 TCP 打流", [
                T("测试步骤", steps([
                    "修改网卡的 switch mode 为 legacy",
                    "创建多个 VF 设备",
                    "检查是否存在对应的 VF 设备",
                    "检查调度树中是否存在 VF 子树信息",
                    "ethtool -L 修改 VF 的队列数",
                    "检查 VF 子树下的 q 和 qg 节点信息是否变化",
                    "设置 VF 的 PIR 与 CIR：ip link set dev <pf> vf 0 max_tx_rate 1000 min_tx_rate 100",
                    "检查 VF 调度子树中的 pir 和 cir 值是否与设置一致",
                    "修改设备的 PIR 与 CIR",
                    "检查调度子树中的值是否会同步修改",
                    "对 VF 进行 tcp 打流，检查流量是否满足限速",
                    "删除 VF 的设备",
                    "检查调度树中是否存在 VF 子树信息",
                ])),
                T("测试预期", [
                    "1. 修改 eswitch mode 成功",
                    "2. 创建 VF 成功",
                    "3. 添加 VF 设备成功",
                    "4. 在调度树对应的层级中存在添加 VF 的 teid 节点信息",
                    "5. 修改 VF 的队列信息成功",
                    "6. VF 子树的 q 和 qg 节点信息比之前有变化",
                    "7. 设置限速成功",
                    "8. 设置一致",
                    "9. 修改限速成功",
                    "10. 调度子树中的值会同步变更",
                    "11. 打流满足限速",
                    "12. 删除 VF 设备成功",
                    "13. 调度树对应的层级信息中没有 VF teid 信息",
                ]),
                T("组合因素", [
                    T("eswitch mode", ["legacy"]),
                    T("VF 数量", ["1", "2", "64", "1008"]),
                    T("限速组合", ["仅 max_tx_rate", "max_tx_rate+min_tx_rate"]),
                    T("发包方式", ["iperf TCP"]),
                ]),
            ]),
            T("switchdev 模式 - 内核 TCP 打流", [
                T("测试步骤", steps([
                    "修改网卡的 switch mode 为 switchdev，并创建 bridge",
                    "创建多个 VF 设备，将 repr 设备添加到网桥内",
                    "检查是否存在对应的 VF 设备",
                    "检查调度树中是否存在 VF 子树信息",
                    "ethtool -L 修改 VF 的队列数",
                    "检查 VF 子树下的 q 和 qg 节点信息是否变化",
                    "设置 VF 的 PIR 与 CIR：ip link set dev <pf> vf 0 max_tx_rate 1000 min_tx_rate 100",
                    "检查 VF 调度子树中的 pir 和 cir 值是否与设置一致",
                    "修改设备的 PIR 与 CIR",
                    "检查调度子树中的值是否会同步修改",
                    "对 VF 进行 tcp 打流，检查流量是否满足限速",
                    "删除 VF 的设备",
                    "检查调度树中是否存在 VF 子树信息",
                ])),
                T("测试预期", [
                    "1. 修改 eswitch mode 成功",
                    "2. 创建 VF 成功、repr 设备成功添加到网桥",
                    "3. 添加 VF 设备成功",
                    "4. 在调度树对应的层级中存在添加 VF 的 teid 节点信息",
                    "5. 修改 VF 的队列信息成功",
                    "6. VF 子树的 q 和 qg 节点信息比之前有变化",
                    "7. 设置限速成功",
                    "8. 设置一致",
                    "9. 修改限速成功",
                    "10. 调度子树中的值会同步变更",
                    "11. 打流满足限速",
                    "12. 删除 VF 设备成功",
                    "13. 调度树对应的层级信息中没有 VF teid 信息",
                ]),
                T("组合因素", [
                    T("eswitch mode", ["switchdev"]),
                    T("VF 数量", ["1", "2", "64", "1008"]),
                    T("限速组合", ["仅 max_tx_rate", "max_tx_rate+min_tx_rate"]),
                    T("发包方式", ["iperf TCP"]),
                ]),
            ]),
            T("legacy 模式 - RDMA 打流", [
                T("测试步骤", steps([
                    "修改网卡的 switch mode 为 legacy",
                    "创建多个 VF 设备",
                    "检查是否存在对应的 VF 设备",
                    "检查调度树中是否存在 VF 子树信息",
                    "ethtool -L 修改 VF 的队列数",
                    "检查 VF 子树下的 q 和 qg 节点信息是否变化",
                    "设置 VF 的 PIR 与 CIR：ip link set dev <pf> vf 0 max_tx_rate 1000 min_tx_rate 100",
                    "检查 VF 调度子树中的 pir 和 cir 值是否与设置一致",
                    "修改设备的 PIR 与 CIR",
                    "检查调度子树中的值是否会同步修改",
                    "对 VF 进行 perftest 打流，检查流量是否满足限速",
                    "删除 VF 的设备",
                    "检查调度树中是否存在 VF 子树信息",
                ])),
                T("测试预期", [
                    "1. 修改 eswitch mode 成功",
                    "2. 创建 VF 成功",
                    "3. 添加 VF 设备成功",
                    "4. 在调度树对应的层级中存在添加 VF 的 teid 节点信息",
                    "5. 修改 VF 的队列信息成功",
                    "6. VF 子树的 q 和 qg 节点信息比之前有变化",
                    "7. 设置限速成功",
                    "8. 设置一致",
                    "9. 修改限速成功",
                    "10. 调度子树中的值会同步变更",
                    "11. 打流满足限速",
                    "12. 删除 VF 设备成功",
                    "13. 调度树对应的层级信息中没有 VF teid 信息",
                ]),
                T("组合因素", [
                    T("eswitch mode", ["legacy"]),
                    T("VF 数量", ["1", "2", "64"]),
                    T("限速组合", ["仅 max_tx_rate", "max_tx_rate+min_tx_rate"]),
                    T("发包方式", ["perftest RDMA"]),
                ]),
            ]),
        ]),
    ]),
    T("可靠性", [
        T("反向测试", [
            T("单一 VF 限速大于父节点的限速", [
                T("测试步骤", steps([
                    "设置父节点限速为某速率值",
                    "设置单一 VF 的限速大于父节点的限速",
                    "清理环境",
                ])),
                T("测试预期", ["1. 设置父节点限速成功", "2. 命令执行失败", "3. 清理环境成功"]),
            ]),
            T("设置 max_tx_rate < min_tx_rate", [
                T("测试步骤", steps([
                    "对 VF 设置 max_tx_rate",
                    "设置 min_tx_rate 大于 max_tx_rate",
                    "清理环境",
                ])),
                T("测试预期", ["1. 设置 max_tx_rate 成功", "2. 命令执行失败", "3. 清理环境成功"]),
            ]),
            T("设置限速取值范围 < 1", [
                T("测试步骤", steps(["对 VF 设置限速值为小于 1 的取值", "清理环境"])),
                T("测试预期", ["1. 命令执行失败", "2. 清理环境成功"]),
            ]),
            T("设置限速取值范围 > 速率大小/1000", [
                T("测试步骤", steps([
                    "对 VF 设置限速值为大于速率大小/1000 的取值（如速率大小为 100000，设置 100000）",
                    "清理环境",
                ])),
                T("测试预期", ["1. 命令执行失败", "2. 清理环境成功"]),
            ]),
        ]),
        T("复位操作", [
            T("VF 配置限速后进行复位", [
                T("前提条件", [
                    "systemctl stop lldpad",
                    "设置 l2-fwd-offload 为 off",
                    "所有的 port 都已物理互通",
                    "用户已在 env_config.ini 或配置脚本中正确配置 RDMA 设备关系",
                ]),
                T("测试步骤", steps([
                    "创建 VF 并配置 max_tx_rate/min_tx_rate",
                    "检查 VF 调度子树的 pir 和 cir 值",
                    "对 VF 触发复位操作",
                    "复位后再次检查调度树 VF 子树的 pir 和 cir 值",
                    "对 VF 打流，验证限速是否保持",
                ])),
                T("测试预期", [
                    "1. 创建 VF、配置限速成功",
                    "2. 调度子树中的值与设置一致",
                    "3. 复位成功",
                    "4. 配置信息未改，pir/cir 值保持一致",
                    "5. 打流满足限速，限速配置保持",
                ]),
                T("组合因素", [
                    T("复位类型", [
                        "FLR", "VFLR", "PFLR", "GLR", "VFR", "固件复位", "core reset",
                        "PFLR 执行：echo 1 > /sys/class/net/ethx/device/reset",
                    ]),
                ]),
            ]),
        ]),
        T("与链路交互", [
            T("修改链路状态后检查队列限速是否修改", [
                T("测试步骤", steps([
                    "对 VF 配置 max_tx_rate/min_tx_rate",
                    "修改 VF 的链路状态为 down",
                    "检查调度树 VF 子树的 pir 和 cir 值",
                    "修改链路状态为 up",
                    "再次检查调度树 VF 子树的 pir 和 cir 值，并对 VF 打流",
                ])),
                T("测试预期", [
                    "1. 配置限速成功", "2. 命令执行成功", "3. 配置信息未改",
                    "4. 命令执行成功", "5. 配置信息未改，打流满足限速",
                ]),
            ]),
        ]),
        T("变更 VF 驱动后配置保持不变", [
            T("内核驱动变更为 dpdk", [
                T("测试步骤", steps([
                    "内核驱动下对 VF 配置 max_tx_rate/min_tx_rate",
                    "将 VF 驱动变更为 dpdk",
                    "检查 VF 的限速配置是否保持",
                ])),
                T("测试预期", ["1. 配置限速成功", "2. 驱动变更成功", "3. VF 的配置不变"]),
            ]),
            T("内核驱动变更为 vdpa 驱动", [
                T("测试步骤", steps([
                    "内核驱动下对 VF 配置 max_tx_rate/min_tx_rate",
                    "将 VF 驱动变更为 vdpa 驱动，注册 vdpa 设备",
                    "检查 VF 的限速配置是否保持",
                ])),
                T("测试预期", ["1. 配置限速成功", "2. 驱动变更、注册 vdpa 设备成功", "3. VF 的配置不变"]),
            ]),
        ]),
    ]),
    T("稳定性", [
        T("VF 打流中不断修改 VF 速率", [
            T("测试步骤", steps([
                "对 VF 配置限速，启动打流",
                "打流过程中不断修改 VF 的 max_tx_rate/min_tx_rate",
                "检查打流带宽是否随限速配置同步变化",
            ])),
            T("测试预期", [
                "1. 配置限速、打流成功",
                "2. 修改限速命令执行成功",
                "3. 设置限速后，VF 的带宽会同步修改，且不超过新设置的限速",
            ]),
        ]),
        T("VF 转为 vdpa 字符设备映射到容器/命名空间后，打流中修改限速", [
            T("测试步骤", steps([
                "将 VF 转为 vdpa 字符设备",
                "将 vdpa 设备映射到容器或其他命名空间",
                "打流过程中修改限速",
            ])),
            T("测试预期", [
                "1. 转换、映射成功",
                "2. 映射成功",
                "3. 设置限速后，时间内的最大带宽不大于 VF 的限速带宽",
            ]),
            T("组合因素", [T("映射场景", ["添加到 dpdk", "映射到 k8s", "映射到 kvm"])]),
        ]),
        T("VF RDMA 设备打流中修改 VF 限速", [
            T("测试步骤", steps([
                "添加 rdma 驱动，使能 VF RDMA 设备",
                "对 VF 配置限速",
                "对 VF RDMA 设备打流，打流过程中修改 VF 的限速带宽",
            ])),
            T("测试预期", [
                "1. 加载 rdma 驱动、使能 VF 成功",
                "2. 配置限速成功",
                "3. 添加 rdma 驱动后，VF 限速也同步限制 rdma 带宽",
            ]),
        ]),
    ]),
    T("压力测试", [
        T("legacy 模式 - 多组 VF 混合驱动并发限速", [
            T("前提条件", [
                "systemctl stop lldpad",
                "设置 l2-fwd-offload 为 off",
                "所有的 port 都已物理互通",
                "用户已在 env_config.ini 或配置脚本中正确配置 RDMA 设备关系",
            ]),
            T("测试步骤", steps([
                "修改 eswitch mode 为 legacy 模式",
                "创建多个 VF，将 VF 分为多组：一组使用 virtio 驱动透传到 kvm，一组使用 vdpa 驱动（用 vdpa 指令创建 vdpa 设备）透传到 kvm 内",
                "对 VF 设置限速：不同 VF 的限速均小于父节点的限速，但所有 VF 的限速之和大于父节点的限速",
                "对 VF 进行打流，检查不同 VF 的限速是否满足",
            ])),
            T("测试预期", [
                "1. 修改 legacy 模式成功",
                "2. 创建 VF 成功，并将 VF 放入到不同的容器中成功",
                "3. 限速命令设置成功",
                "4. VF 限速满足",
            ]),
        ]),
        T("switchdev 模式 - 多组 VF 混合驱动并发限速", [
            T("前提条件", [
                "systemctl stop lldpad",
                "设置 l2-fwd-offload 为 off",
                "所有的 port 都已物理互通",
                "用户已在 env_config.ini 或配置脚本中正确配置 RDMA 设备关系",
            ]),
            T("测试步骤", steps([
                "修改 eswitch mode 为 switchdev 模式",
                "创建多个 VF，将 VF 分为多组：一组使用 virtio 驱动透传到 kvm，一组使用 vdpa 驱动（用 vdpa 指令创建 vdpa 设备）透传到 kvm 内",
                "对 VF 设置限速：不同 VF 的限速均小于父节点的限速，但所有 VF 的限速之和大于父节点的限速",
                "对 VF 进行打流，检查不同 VF 的限速是否满足",
            ])),
            T("测试预期", [
                "1. 修改 switchdev 模式成功",
                "2. 创建 VF 成功，并将 VF 放入到不同的容器中成功",
                "3. 限速命令设置成功",
                "4. VF 限速满足",
            ]),
        ]),
    ]),
])


def build(node):
    """将 T()/字符串递归转换为 topic dict；字符串为叶子。"""
    if isinstance(node, str):
        return {"id": uuid.uuid4().hex, "title": node}
    t = {"id": uuid.uuid4().hex, "title": node["title"]}
    kids = node.get("children") or []
    if kids:
        t["children"] = {"attached": [build(k) for k in kids]}
    return t


# ---------------------------------------------------------------------------
# 以原始文件为模板，仅替换 rootTopic，extensions 必须为数组
# ---------------------------------------------------------------------------
tmpdir = os.path.join(BASE, ".vf_tmp")
os.makedirs(tmpdir, exist_ok=True)

# 1) 解压模板
with zipfile.ZipFile(TEMPLATE_XMIND) as zf:
    for info in zf.infolist():
        target = os.path.join(tmpdir, info.filename)
        if info.is_dir():
            os.makedirs(target, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with zf.open(info) as src, open(target, "wb") as dst:
            dst.write(src.read())

# 2) 替换 content.json 的 rootTopic
content_path = os.path.join(tmpdir, "content.json")
with open(content_path, "r", encoding="utf-8") as f:
    content = json.load(f)
sheet = content[0]
sheet_id = sheet["id"]
sheet["title"] = "VF 限速测试设计"
sheet["rootTopic"] = {
    "id": "vf_test_design_root_" + uuid.uuid4().hex[:8],
    "class": "topic",
    "title": "VF 限速测试设计",
    "structureClass": "org.xmind.ui.map.unbalanced",
    "children": build(tree)["children"],
    # 关键：extensions 必须是数组（元素为 {provider, content}）
    "extensions": [
        {
            "provider": "org.xmind.ui.map.unbalanced",
            "content": [{"name": "right-number", "content": "1"}],
        }
    ],
}
with open(content_path, "w", encoding="utf-8") as f:
    json.dump(content, f, ensure_ascii=False)

# 3) 更新 metadata activeSheetId
meta_path = os.path.join(tmpdir, "metadata.json")
with open(meta_path, "r", encoding="utf-8") as f:
    metadata = json.load(f)
metadata["activeSheetId"] = sheet_id
with open(meta_path, "w", encoding="utf-8") as f:
    json.dump(metadata, f, ensure_ascii=False)

# 4) 打包
if os.path.exists(OUT_XMIND):
    os.remove(OUT_XMIND)
with zipfile.ZipFile(OUT_XMIND, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, _, files in os.walk(tmpdir):
        for fn in files:
            full = os.path.join(root, fn)
            zf.write(full, os.path.relpath(full, tmpdir))

shutil.rmtree(tmpdir, ignore_errors=True)
print("生成完成：", OUT_XMIND)
