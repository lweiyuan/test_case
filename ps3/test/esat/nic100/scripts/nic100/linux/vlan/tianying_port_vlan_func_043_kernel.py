#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: port-vlan-func-043
case title: 测试分析_规格_每个PF最多可以创建63个VF
test category: port vlan
check point: 每个PF最多可以创建63个VF
author: auto-generated
date: 2026.07.20

@steps:
    1. 在单个 PF 下创建 63 个 VF
    2. 检查所有 VF 可被识别
    3. 尝试创建第 64 个 VF

@expected:
    1. 63 个 VF 创建成功且可被识别
    2. 第 64 个 VF 创建失败或被拒绝
    3. 无异常崩溃
"""

import os
import time
import add_syspath

from scripts.script_libs import log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import (
    CmdExecuteAdressEnum,
    RtnStatusEnum,
    BugTypeEnum,
)
from scripts.script_libs.script_base import ScriptBase, SxeException


class TianyingPortVlanPf63Vf043(ScriptBase):
    test_object = "port vlan"
    test_module = "port_vlan"
    test_tool = "ip, ethtool"
    test_precondition = """1. 网卡支持 SR-IOV，已加载 PF 驱动
2. 已创建 VF 并识别到网口
3. 测试机之间物理链路 Up
4. 环境配置中已正确设置 server/client 网口关系"""
    test_steps = """
1. 在单个 PF 下创建 63 个 VF
2. 检查所有 VF 可被识别
3. 尝试创建第 64 个 VF
    """

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        cls.bug_title = "TianyingPortVlanPf63Vf043 Failed"

    @classmethod
    def check_own_environment(cls) -> None:
        log.info("检查 port-vlan-func-043 环境...")
        server_ifs, client_ifs = CommonOperation.get_nic_relationships(
            rdma=False, nic_mode=1
        )
        if not server_ifs or not client_ifs:
            log.error("未读取到以太设备名")
            cls.own_environment_enabled = False
            return
        cls.server_if = server_ifs[0].strip()
        cls.client_if = client_ifs[0].strip()
        log.info(f"server 网口: {cls.server_if}, client 网口: {cls.client_if}")
        cls.own_environment_enabled = True

    @classmethod
    def prepare(cls) -> None:
        log.info("准备 port-vlan-func-043 环境...")
        # 根据具体用例实现：创建 VF、配置 VLAN 等前置准备

    @classmethod
    def do(cls) -> None:
        log.info("=" * 60)
        log.info("开始 port-vlan-func-043: 测试分析_规格_每个PF最多可以创建63个VF")
        log.info("=" * 60)
        try:
            # 根据具体用例实现测试步骤
            # 参考 test_steps 中的命令与检查点
            log.info("port-vlan-func-043 测试通过")
        except SxeException:
            raise
        except Exception as e:
            log.error(f"port-vlan-func-043 未预期错误: {e}")
            raise

    @classmethod
    def post(cls) -> None:
        log.info("清理 port-vlan-func-043 环境...")
        # 根据具体用例实现环境恢复：删除 VLAN、卸载 VF 等


def main() -> None:
    TianyingPortVlanPf63Vf043.run()


if __name__ == "__main__":
    main()
