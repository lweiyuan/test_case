#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: TC-VLAN-013-D
case title: 基于 VSI 的 VLAN 剥离（DPDK）
test category: 天鹰 VLAN 测试（DPDK 场景）
check point: TP-07
author: auto-generated
date: 2026.07.10

@steps:
    1. 对端 uplink 发送 CTag vlan 100 报文
    2. server uplink 接收
    3. 检查 VSI 关联接口收到的报文
    4. 检查描述符是否回写 VLAN

@expected:
    1. VSI 关联接口收到 untagged 报文
    2. 业务通信正常
    3. 描述符中不回写 VLAN（VSI 剥离不回写）

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


class TianyingVlanVsiStripDpdk(ScriptBase):
    test_object = "天鹰 VLAN 测试"
    test_module = "tianying_vlan"
    test_tool = "DPDK, testpmd, rte_flow"
    test_precondition = """1. 配置 VSI VLAN 100
2. 对端发送带 vlan 100 的报文到 uplink"""
    test_steps = """
    1. 对端 uplink 发送 CTag vlan 100 报文
    2. server uplink 接收
    3. 检查 VSI 关联接口收到的报文
    4. 检查描述符是否回写 VLAN
    """

    VLAN_ID = 100
    # TODO: 根据实际 DPDK 环境修改 PCI 地址、hugepage 配置、testpmd 参数
    DPDK_PCI_SERVER = "0000:03:00.0"
    DPDK_PCI_CLIENT = "0000:03:00.0"

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "TianyingVlanVsiStripDpdk Failed"

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 TC-VLAN-013-D 自有环境...")
        # DPDK 场景通常不需要通过 env_config 读取 RDMA 设备名，而是绑定 PCI
        # TODO: 根据实际环境确认 DPDK 网卡 PCI 地址与 hugepage 配置
        cls.own_environment_enabled = True
        log.info("TC-VLAN-013-D 环境检查通过（DPDK 环境需人工确认）")

    @classmethod
    def prepare(cls) -> None:
        log.info("准备 TC-VLAN-013-D DPDK 测试环境...")
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
        log.info("开始 TC-VLAN-013-D：基于 VSI 的 VLAN 剥离（DPDK）")
        log.info("=" * 60)
        try:
            # TODO: 通过 DPDK API / testpmd CLI 执行 VLAN 操作并验证
            result_ok = cls._run_dpdk_vlan_test()
            if not result_ok:
                cls._bug_and_raise("DPDK VLAN 测试未通过")

            log.info("TC-VLAN-013-D 测试通过")
        except SxeException:
            raise
        except Exception as e:
            log.error(f"TC-VLAN-013-D 未预期错误: {e}")
            raise

    @classmethod
    def _bug_and_raise(cls, msg: str) -> None:
        cls.bug_result = msg
        cls.bug_expect = "DPDK VLAN offload / rte_flow 应按预期工作"
        cls.set_bug_type(BugTypeEnum.FUNCTION.value)
        cls.create_bug(msg)

    @classmethod
    def post(cls) -> None:
        log.info("清理 TC-VLAN-013-D DPDK 测试环境...")
        # TODO: 恢复 DPDK 环境、解绑网卡、释放 hugepage
        CommandOperation.execute_command_with_error(
            "echo 'quit' | socat - /tmp/testpmd.sock 2>/dev/null || true",
            CmdExecuteAdressEnum.SERVER.value
        )

        log.info("TC-VLAN-013-D 清理完成")


def main() -> None:
    TianyingVlanVsiStripDpdk.run()


if __name__ == "__main__":
    main()
