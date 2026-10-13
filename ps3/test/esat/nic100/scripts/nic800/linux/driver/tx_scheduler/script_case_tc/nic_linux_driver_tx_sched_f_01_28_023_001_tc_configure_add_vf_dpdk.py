#!/usr/bin/env python3
# -*- encoding=utf8 -*-

"""
case author:   weiyuan1
script author: weiyuan1
date:          2026.09.07
description:

case number:   nic_linux_driver_tx_sched_f_01_28_023_001
case title:    TC层_基础功能_配置tc,添加VF，将VF加入dpdk内
check point:   配置tc,添加VF，将VF加入dpdk内
test condition:tc配置+VF加入DPDK
test platform: 测试PF/VF；DPDK(testpmd)环境

@steps:
1. 待补充：xmind 未展开该用例的具体测试步骤

@steps expect result:
1. 待补充：xmind 未展开该用例的预期结果

@changelog:

"""
import add_syspath

from scripts.script_libs import log
from scripts.nic800.linux.driver.tx_scheduler.script_base_tx_sched_cos_test import ScriptBaseTxSchedCosTest
from scripts.script_libs.common_operation import CommonOperation


class Script(ScriptBaseTxSchedCosTest):
    @classmethod
    def set_parameters(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 设置需要调用的变量
        :return: 无返回值
        """
        super().set_parameters()

    @classmethod
    def check_own_environment(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 检测当前脚本运行所需的局部环境是否具备，该方法只检测，不报bug,
                    函数内需要设定类变量local_enviroment_enabled的值，
                    局部环境检测正常，类变量local_enviroment_enabled设置为True
        :return: 无返回值
        """
        super().check_own_environment()
        log.info('脚本尚未实现，暂时跳过')
        cls.own_environment_enabled = False

    @classmethod
    def prepare(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 准备环境
        :return: 无返回值
        """
        super().prepare()

    @classmethod
    def do(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 执行测试环境
        :return: 无返回值
        """
        super().do()

        CommonOperation.concat_test_steps(

            '1. 待补充：xmind 未展开该用例的具体测试步骤; expect result: 1. 待补充：xmind 未展开该用例的预期结果')


    @classmethod
    def post(cls) -> None:
        """
        author: weiyuan1
        date: 2026.09.07
        descriptor: 整理环境及结果信息相关信息
        :return: 无返回值
        """
        super().post()


def main() -> None:
    Script.run()


if __name__ == "__main__":
    main()
