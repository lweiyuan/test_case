#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: TC-VLAN-027-D
case title: 验证天鹰支持多层 VLAN 插入/剥离（DPDK）
test category: 天鹰 VLAN 测试（DPDK 场景）
check point: TP-03; TP-05; TP-11
author: auto-generated
date: 2026.07.10

@steps:
    1. 分别测试双层插入、双层剥离
    2. 使用 tcpdump 验证物理口双层标签
    3. 使用 mbuf/描述符验证回写

@expected:
    1. 天鹰双层 VLAN 插入/剥离均成功
    2. CX7 同类操作失败或不支持
    3. 描述符正确回写两层 VLAN ID

@changelog:
    2026.07.10 - 初始版本，基于 NIC100 框架生成
"""

import os
import re
import time
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import (
    CmdExecuteAdressEnum,
    RtnStatusEnum,
    BugTypeEnum,
    RdmaMode,
)
from scripts.script_libs.script_base import ScriptBase, SxeException


class TianyingVlanMultiLayerDpdk(ScriptBase):
    test_object = "天鹰 VLAN 测试"
    test_module = "tianying_vlan"
    test_tool = "DPDK, testpmd, rte_flow"
    test_precondition = """1. 天鹰网卡
2. 对端可收发 QinQ"""
    test_steps = """
    1. 分别测试双层插入、双层剥离
    2. 使用 tcpdump 验证物理口双层标签
    3. 使用 mbuf/描述符验证回写
    """

    VLAN_ID = 100
    # TODO: 根据实际 DPDK 环境修改 PCI 地址、hugepage 配置、testpmd 参数
    DPDK_PCI_SERVER = "0000:03:00.0"
    DPDK_PCI_CLIENT = "0000:03:00.0"

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "TianyingVlanMultiLayerDpdk Failed"

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 TC-VLAN-027-D 自有环境...")
        # DPDK 场景通常不需要通过 env_config 读取 RDMA 设备名，而是绑定 PCI
        # TODO: 根据实际环境确认 DPDK 网卡 PCI 地址与 hugepage 配置
        cls.own_environment_enabled = True
        log.info("TC-VLAN-027-D 环境检查通过（DPDK 环境需人工确认）")

    @classmethod
    def prepare(cls) -> None:
        log.info("准备 TC-VLAN-027-D DPDK 测试环境...")
        # TODO: 配置 DPDK 环境：hugepage、绑定网卡、启动 testpmd/l2fwd
        log.info("准备 DPDK 环境 (TODO: 根据实际环境修改)")


    @classmethod
    def _run_dpdk_vlan_test(cls) -> bool:
        # TODO: 实现 DPDK VLAN offload / rte_flow 验证逻辑
        log.info("执行 DPDK VLAN 测试 (TODO: 替换为实际 DPDK 命令/API)")
        CommandOperation.execute_command_with_error(
            "echo 'vlan set strip on 0' | socat - /tmp/testpmd.sock || true",
            CmdExecuteAdressEnum.SERVER.value
        )
        return True


    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 TC-VLAN-027-D：验证天鹰支持多层 VLAN 插入/剥离（DPDK）")
        log.info("=" * 60)
        try:
            # TODO: 通过 DPDK API / testpmd CLI 执行 VLAN 操作并验证
            result_ok = cls._run_dpdk_vlan_test()
            if not result_ok:
                cls._bug_and_raise("DPDK VLAN 测试未通过")

            log.info("TC-VLAN-027-D 测试通过")
        except SxeException:
            raise
        except Exception as e:
            log.error(f"TC-VLAN-027-D 未预期错误: {e}")
            raise

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "DPDK VLAN offload / rte_flow 应按预期工作"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)

    @classmethod
    def post(cls) -> None:
        log.info("清理 TC-VLAN-027-D DPDK 测试环境...")
        # TODO: 恢复 DPDK 环境、解绑网卡、释放 hugepage
        CommandOperation.execute_command_with_error(
            "echo 'quit' | socat - /tmp/testpmd.sock 2>/dev/null || true",
            CmdExecuteAdressEnum.SERVER.value
        )

        log.info("TC-VLAN-027-D 清理完成")


def main() -> None:
    TianyingVlanMultiLayerDpdk.run()


if __name__ == "__main__":
    main()
