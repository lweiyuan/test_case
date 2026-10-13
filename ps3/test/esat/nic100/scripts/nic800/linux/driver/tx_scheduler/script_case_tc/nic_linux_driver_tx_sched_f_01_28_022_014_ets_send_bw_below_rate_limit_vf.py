#!/usr/bin/env python3
# -*- encoding=utf8 -*-

"""
case author:   weiyuan1
script author: weiyuan1
date:          2026.09.07
description:

case number:   nic_linux_driver_tx_sched_f_01_28_022_014
case title:    TC层_基础功能_添加VF后配置tc_ets算法-添加VF后，限速tc的发送带宽小于限速带宽，未配置限速的tc的带宽为满流量-限速带宽值（VF个数=2；设置的tc数量包含=4）
check point:   ets算法-添加VF后，限速tc的发送带宽小于限速带宽，未配置限速的tc的带宽为满流量-限速带宽值（VF个数=2；设置的tc数量包含=4）
test condition:组合覆盖：VF个数∈{1,2,64}；设置的tc数量包含∈{2,4,8}
test platform: 测试PF/VF；双机iperf3打流

@steps:
1. 检查网卡支持的tc数量
2. 设置dcbx host ieee（指令：dcb dcbx set dev <intf_name> host ieee）
3. 获取tc节下VF eth子树及队列的信息
4. dcb ets 设置带宽比例（VF个数=2；设置的tc数量包含=4）（指令：dcb ets set dev <intf_name> tc-tsa all:ets tc-bw 0:25 1:25 2:25 3:25 4:0 5:0 6:0 7:0 prio-tc 0:0 1:1 2:2 3:3 4:0 5:1 6:2 7:3）
5. 查询dcb ets show dev <intf_name>（指令：dcb ets show dev <intf_name>）
6. 对VF添加IP地址，且vfip地址为不同网段的地址
7. 检索tx_sched调度树tc 节点是否增加
8. 对tc 设置限速（指令：dcb maxrate set dev <inf_name> tc-max 0:200 1:400 2:400 3:400 4:500 5:600 7:100）
9. tc app绑定优先级与tos（指令：dcb app add dev eth0 dscp <dscp>:<prio>）
10. 启动多个iperf3进程按照tos优先级同时进行对VF打流， 设置限速tc的iperf中的-b 为限速带宽，未配置限速tc的iperf的-b为满带宽-限速带宽值，并发进行打流（指令：iperf3 --tos <tos>）

@steps expect result:
1. 获取网卡支持的tc数量成功
2. 设置dcbx成功
3. 获取tc节下VF eth子树及队列的信息成功
4. dcb ets设置带宽比例成功
5. dcb ets 结果与设置的结果一致
6. 对VF添加IP地址成功
7. 每个tc节点下的vf子树及队列均为平均分配
8. 限速设置成功
9. 绑定优先级成功
10. VF打流成功，限速tc的VF的带宽值为限速带宽值之内，未限速的tc的带宽值未达标

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

            '1. 检查网卡支持的tc数量; expect result: 1. 获取网卡支持的tc数量成功')


        CommonOperation.concat_test_steps(

            '2. 设置dcbx host ieee（指令：dcb dcbx set dev <intf_name> host ieee）; expect result: 2. 设置dcbx成功')


        CommonOperation.concat_test_steps(

            '3. 获取tc节下VF eth子树及队列的信息; expect result: 3. 获取tc节下VF eth子树及队列的信息成功')


        CommonOperation.concat_test_steps(

            '4. dcb ets 设置带宽比例（VF个数=2；设置的tc数量包含=4）（指令：dcb ets set dev <intf_name> tc-tsa all:ets tc-bw 0:25 1:25 2:25 3:'

            '25 4:0 5:0 6:0 7:0 prio-tc 0:0 1:1 2:2 3:3 4:0 5:1 6:2 7:3）; expect result: 4. dcb ets设置带宽比例成功')


        CommonOperation.concat_test_steps(

            '5. 查询dcb ets show dev <intf_name>（指令：dcb ets show dev <intf_name>）; expect result: 5. dcb ets 结果与设置的结果一致')


        CommonOperation.concat_test_steps(

            '6. 对VF添加IP地址，且vfip地址为不同网段的地址; expect result: 6. 对VF添加IP地址成功')


        CommonOperation.concat_test_steps(

            '7. 检索tx_sched调度树tc 节点是否增加; expect result: 7. 每个tc节点下的vf子树及队列均为平均分配')


        CommonOperation.concat_test_steps(

            '8. 对tc 设置限速（指令：dcb maxrate set dev <inf_name> tc-max 0:200 1:400 2:400 3:400 4:500 5:600 7:100）; expect res'

            'ult: 8. 限速设置成功')


        CommonOperation.concat_test_steps(

            '9. tc app绑定优先级与tos（指令：dcb app add dev eth0 dscp <dscp>:<prio>）; expect result: 9. 绑定优先级成功')


        CommonOperation.concat_test_steps(

            '10. 启动多个iperf3进程按照tos优先级同时进行对VF打流， 设置限速tc的iperf中的-b 为限速带宽，未配置限速tc的iperf的-b为满带宽-限速带宽值，并发进行打流（指令：iperf3 --tos'

            ' <tos>）; expect result: 10. VF打流成功，限速tc的VF的带宽值为限速带宽值之内，未限速的tc的带宽值未达标')


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
