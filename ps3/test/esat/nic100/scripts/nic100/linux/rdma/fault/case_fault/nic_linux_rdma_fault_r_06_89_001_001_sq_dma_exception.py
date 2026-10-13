#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
case number: nic_linux_rdma_fault_r_06_89_001_001
case title: RDMA 错误处理-sq请求出现dma异常
test category: 可靠性(reliability)
check point:
    1. 构造TX_ENG模块SQ请求DMA异常场景。
    2. 校验CQE返回Local_Access_Error，syndrome=0x11，
       minor_syndrome=0x31。
    3. 校验无AEQ事件上报。
    4. 校验QP进入Error/Destroyed状态。
author: SNPY/lihr
date: 2026-08-03

@steps:
    1. 检查环境是否满足测试需求
       （pf/rdma驱动、rdma_core、pyverbs）。
    2. 创建QP/CQ/MR等组件，完成打流前准备
       （本端loopback RC QP）。
    3. 在TX_ENG模块构造"sq请求出现dma异常"场景
       （DMA错误）。
    4. 打流，触发注入错误（post send）。
    5. 检查CQE、AEQ及QP最终状态。
    6. 销毁测试资源。

@expected:
    1. 环境满足测试需求。
    2. 组件创建成功，完成打流准备工作。
    3. 故障注入成功。
    4. 打流触发注入的错误。
    5. 返回CQE：CQE名称为Local_Access_Error，syndrome为0x11，
       minor_syndrome为0x31；无AEQ事件上报；QP被销毁/进入Error。
    6. 测试资源销毁成功。

@changelog:
    2026-08-03 SNPY/lihr 缩短脚本名称，生成模板。
"""
import re
import time

import add_syspath

from scripts.nic100.linux.rdma.ipvbs_screen_utils import IpvbsScreen
from scripts.nic100.linux.rdma.rdma_cq_func import RdmaCQ
from scripts.nic100.linux.rdma.rdma_func import Rdma
from scripts.script_libs import constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import (
    CmdExecuteAdressEnum,
    IpvbsCommuEnum,
    IpvbsStatusEnum,
    RdmaMode,
    RtnStatusEnum,
)
from scripts.script_libs.script_base import ScriptBase


class NicLinuxRdmaFaultR0689001001SqDmaException(ScriptBase):
    """RDMA 错误处理：sq请求出现dma异常。"""

    test_object = '800G网卡'
    test_module = 'rdma'
    test_tool = constants.SXE2CLI64
    test_precondition = (
        '1. pf驱动、rdma驱动已加载；\n'
        '2. 已安装rdma_core；\n'
        '3. pyverbs安装完成且能正常使用。'
    )
    test_steps = (
        '1. 检查环境是否满足测试需求；\n'
        '2. 创建QP/CQ/MR等组件，完成打流前准备；\n'
        '3. 在TX_ENG模块构造"sq请求出现dma异常"场景；\n'
        '4. 打流，触发错误；\n'
        '5. 检查CQE、AEQ及QP最终状态；\n'
        '6. 销毁测试资源。'
    )

    # 测试对象侧，默认在server端执行loopback测试
    _exec_addr = CmdExecuteAdressEnum.SERVER.value
    _ipvbs = None
    _rdma_dev = ''
    _rdma_bus = ''
    _aeq_baseline = None

    # CQE预期值
    _EXP_CQE_STATUS = 'Local_Access_Error'
    _EXP_SYNDROME = 0x11
    _EXP_MINOR_SYNDROME = 0x31

    @classmethod
    def set_parameters(cls):
        """设置脚本运行参数。"""
        cls.test_object = '800G网卡'
        cls.test_module = 'rdma'
        cls.test_tool = constants.SXE2CLI64
        cls.own_environment_enabled = False

    @classmethod
    def check_own_environment(cls):
        """检查脚本运行所需的局部环境。"""
        log.info('开始检查局部环境。')
        enabled = True

        # 检查pf与rdma驱动是否已加载
        for drv in (constants.nicg, constants.DRV_SCGBE_RDMA):
            cmd = f'lsmod|grep -w {drv}'
            status, result, err = CommandOperation.execute_command_with_error(
                cmd, cls._exec_addr
            )
            if status != RtnStatusEnum.SUCCESS.value or not result:
                msg = f'{drv}驱动未加载或检查失败: {err}'
                log.error(msg)
                enabled = False

        # 动态获取RDMA设备名
        try:
            server_list, _ = CommonOperation.get_nic_relationships(
                rdma=True, nic_mode=RdmaMode.Infiniband.value
            )
            cls._rdma_dev = server_list[cls.target_port].strip()
        except Exception as e:
            log.error(f'获取RDMA设备关系失败: {e}')
            enabled = False

        if not cls._rdma_dev:
            log.error('未获取到有效的RDMA设备名。')
            enabled = False

        # 检查rdma_core/pyverbs基本可用性
        cmd = 'python3 -c "import pyverbs; print(pyverbs.__file__)"'
        status, result, err = CommandOperation.execute_command_with_error(
            cmd, cls._exec_addr
        )
        if status != RtnStatusEnum.SUCCESS.value or not result:
            log.error(f'pyverbs检查失败: {err}')
            enabled = False

        cls.own_environment_enabled = enabled
        log.info(f'局部环境检查结果: {enabled}')

    @classmethod
    def prepare(cls):
        """
        准备测试环境：加载驱动、配置ARP、
        启动pyverbs交互环境。
        """
        log.info('开始prepare阶段。')

        # 设置rdma环境
        status = Rdma.setup_rdma_env(
            test_direction_reverse=cls.test_direction_reverse
        )
        if status != RtnStatusEnum.SUCCESS.value:
            msg = 'RDMA环境初始化失败。'
            log.error(msg)
            cls._report_bug(msg, 'RDMA环境应初始化成功')

        # 获取BDF
        cls._rdma_bus = Rdma.get_bdf(cls._rdma_dev, cls._exec_addr)
        if not cls._rdma_bus:
            msg = f'获取RDMA设备{cls._rdma_dev}的BDF失败。'
            log.error(msg)
            cls._report_bug(msg, '应成功获取BDF')

        # 启动IpvbsScreen交互环境
        cls._ipvbs = IpvbsScreen(
            caller_class=cls,
            exec_addr=cls._exec_addr,
            commu=IpvbsCommuEnum.SCREEN.value,
            screen_mark='sq_dma_err',
        )
        log.info('IpvbsScreen启动完成。')

    @classmethod
    def do(cls):
        """
        执行测试：创建资源、注入故障、打流、校验结果。
        """
        log.info('开始do阶段。')

        # Step 1：环境检查已在check_own_environment完成
        log.info('Step1: 环境已满足测试需求。')

        # Step 2：创建QP/CQ/MR等组件
        log.info('Step2: 创建pyverbs测试资源。')
        cls._create_test_resources()

        # 记录AEQ基线
        cls._aeq_baseline = RdmaCQ.debugfs_ae_check(
            rdma_bus=cls._rdma_bus,
            cmd_execute_address=cls._exec_addr,
        )

        # Step 3：注入TX_ENG DMA错误
        log.info('Step3: 构造TX_ENG DMA异常场景。')
        cls.inject_tx_eng_dma_error(cls._rdma_bus, cls._exec_addr)

        # Step 4：打流触发错误
        log.info('Step4: 执行post send触发错误。')
        cls._post_send_and_poll()

        # Step 5：校验CQE、AEQ、QP状态
        log.info('Step5: 校验CQE、AEQ及QP最终状态。')
        cls._verify_cqe()
        cls._verify_aeq()
        cls._verify_qp_state()

        # Step 6：销毁资源在post阶段统一处理
        log.info('Step6: do阶段资源将在post阶段统一销毁。')

    @classmethod
    def post(cls):
        """清理测试资源，关闭IpvbsScreen，恢复环境。"""
        log.info('开始post阶段。')
        try:
            cls._destroy_test_resources()
        except Exception as e:
            log.warning(
                f'销毁资源异常（可能QP已被驱动销毁）: {e}'
            )
        finally:
            if cls._ipvbs is not None:
                try:
                    cls._ipvbs.exit_ipvbs_screen()
                except Exception as e:
                    log.warning(f'退出IpvbsScreen异常: {e}')
                cls._ipvbs = None
        log.info('post阶段完成。')


    @classmethod
    def inject_tx_eng_dma_error(cls, rdma_bus: str, exec_addr: str) -> int:
        """在TX_ENG模块构造SQ请求DMA异常场景。

        注意：当前驱动debugfs接口下TX_ENG DMA错误注入的
        具体文件和写入值需根据实际驱动实现确认/调整。
        以下命令为占位实现，遵循现有debugfs模式
        （参考RdmaCQ.create_ae_event）。

        :param rdma_bus: RDMA设备BDF。
        :param exec_addr: 命令执行端。
        :return: 命令执行状态。
        """
        inject_file = 'sq_dma_err_inject'
        inject_value = '1'
        cmd = (
            f'echo {inject_value} > '
            f'/sys/kernel/debug/{constants.DRV_SCGBE_RDMA}/'
            f'{rdma_bus}/TX_ENG/{inject_file}'
        )
        status, result, err = CommandOperation.execute_command_with_error(
            cmd, exec_addr
        )
        if status != RtnStatusEnum.SUCCESS.value:
            msg = (
                f'TX_ENG DMA错误注入失败: cmd={cmd}, '
                f'result={result}, err={err}'
            )
            log.error(msg)
            cls._report_bug(msg, 'TX_ENG DMA错误应注入成功')
        log.info('TX_ENG DMA错误注入完成。')
        return status

    @classmethod
    def _create_test_resources(cls):
        """通过IpvbsScreen创建pyverbs测试资源。"""
        rdma_dev = cls._rdma_dev
        cmd_list = [
            "import pyverbs",
            (
                "from pyverbs import device, pd, cq, qp, mr, wr, "
                "addr, mem_alloc, enums"
            ),
            f"obj_ctx = device.Context(name='{rdma_dev}')",
            "obj_pd = pd.PD(creator=obj_ctx)",
            # CQ容量需覆盖1000个signaled send对应的CQE
            "obj_cq = cq.CQ(ctx=obj_ctx, cqe=1024)",
            "obj_port_attr = obj_ctx.query_port(port_num=1)",
            "obj_lid = obj_port_attr.lid",
            "obj_buf = mem_alloc.malloc(4096)",
            (
                "obj_mr = mr.MR(creator=obj_pd, length=4096, "
                "access=enums.ibv_access_flags.IBV_ACCESS_LOCAL_WRITE.value, "
                "address=obj_buf, implicit=False)"
            ),
            "obj_mr.write(data='A'*64, length=64)",
            # send/recv队列深度需支持1000个WR
            (
                "obj_cap = qp.QPCap(max_send_wr=1024, max_recv_wr=1024, "
                "max_send_sge=1, max_recv_sge=1)"
            ),
            (
                "obj_init_attr = qp.QPInitAttr(qp_type=enums.IBV_QPT_RC, "
                "scq=obj_cq, rcq=obj_cq, cap=obj_cap, sq_sig_all=1)"
            ),
            "obj_qp1 = qp.QP(pd=obj_pd, init_attr=obj_init_attr)",
            "obj_qp2 = qp.QP(pd=obj_pd, init_attr=obj_init_attr)",
            "obj_qp1.to_init(qp.QPAttr(pkey_index=0, port_num=1))",
            "obj_qp2.to_init(qp.QPAttr(pkey_index=0, port_num=1))",
            (
                "obj_ah_attr = addr.AHAttr(dlid=obj_lid, port_num=1, "
                "is_global=0)"
            ),
            (
                "obj_qp1.to_rtr(qp.QPAttr(path_mtu=enums.ibv_mtu."
                "IBV_MTU_1024, rq_psn=0, max_dest_rd_atomic=1, "
                "min_rnr_timer=12, dest_qp_num=obj_qp2.qp_num, "
                "ah_attr=obj_ah_attr))"
            ),
            (
                "obj_qp2.to_rtr(qp.QPAttr(path_mtu=enums.ibv_mtu."
                "IBV_MTU_1024, rq_psn=0, max_dest_rd_atomic=1, "
                "min_rnr_timer=12, dest_qp_num=obj_qp1.qp_num, "
                "ah_attr=obj_ah_attr))"
            ),
            (
                "obj_qp1.to_rts(qp.QPAttr(timeout=6, retry_cnt=5, "
                "rnr_retry=5, sq_psn=0, max_rd_atomic=1))"
            ),
            (
                "obj_qp2.to_rts(qp.QPAttr(timeout=6, retry_cnt=5, "
                "rnr_retry=5, sq_psn=0, max_rd_atomic=1))"
            ),
            # QP2 预Posting 1000 个接收WR，匹配发送数量
            (
                "all([obj_qp2.post_recv(wr.RecvWR("
                "sge=[wr.SGE(addr=obj_mr.buf,length=64,lkey=obj_mr.lkey)],"
                "wr_id=0x1000+i)) is None for i in range(1000)])"
            ),
            "rdma_dict['ctx'] = obj_ctx",
            "rdma_dict['pd'] = obj_pd",
            "rdma_dict['cq'] = obj_cq",
            "rdma_dict['mr'] = obj_mr",
            "rdma_dict['buf'] = obj_buf",
            "rdma_dict['qp1'] = obj_qp1",
            "rdma_dict['qp2'] = obj_qp2",
        ]
        cls._exec_ipvbs_list(cmd_list, '创建pyverbs资源失败')
        log.info('pyverbs测试资源创建完成。')

    @classmethod
    def _destroy_test_resources(cls):
        """通过IpvbsScreen销毁pyverbs测试资源。

        使用ipvbs的exit命令统一释放rdma_dict中所有对象，避免
        QP已被驱动销毁后单独close触发异常。
        """
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            'exit', print_steps=False, print_outputs=False
        )
        if status != IpvbsStatusEnum.SUCCESS.value:
            log.warning(f'ipvbs exit返回非成功: {result}')
        log.info('pyverbs测试资源已销毁。')

    @classmethod
    def _post_send_and_poll(cls):
        """执行1000次post send并轮询所有CQE。"""
        cmd = (
            "all([obj_qp1.post_send(wr.SendWR(opcode=enums.IBV_WR_SEND,"
            "sge=[wr.SGE(addr=obj_mr.buf,length=64,lkey=obj_mr.lkey)],"
            "wr_id=i,send_flags=enums.IBV_SEND_SIGNALED.value)) is None "
            "for i in range(1000)]);"
            "time.sleep(1);"
            "obj_wc_list=[wc for _ in range(200) "
            "for wc in (obj_cq.poll(num_entries=1024) or [])];"
            "rdma_dict['wc']=obj_wc_list[-1] if obj_wc_list else None;"
            "rdma_dict['wc_count']=len(obj_wc_list)"
        )
        status, result = cls._ipvbs.exec_and_get_ipvbs_result(
            cmd, print_steps=False, print_outputs=False
        )
        if status != IpvbsStatusEnum.SUCCESS.value:
            detail = f'post send或poll cq失败: cmd={cmd}, result={result}'
            log.error(detail)
            cls._report_bug(detail, 'Ipvbs命令应执行成功')
        log.info('post send与poll cq执行完成，发送1000个WR。')

    @classmethod
    def _verify_cqe(cls):
        """校验CQE状态、syndrome及minor_syndrome。

        说明：标准 ibv_wc 结构没有 syndrome/minor_syndrome 字段，
        驱动通常通过自定义扩展或 vendor_err 暴露。本方法同时尝试
        从 WC 字符串表示中提取多个可能的字段名，并根据实际返回值
        校验。
        """
        status, wc_count_str = cls._ipvbs.exec_and_get_ipvbs_result(
            "str(rdma_dict.get('wc_count', 0))",
            print_steps=False,
            print_outputs=False,
        )
        try:
            wc_count = int(wc_count_str.strip()) if wc_count_str else 0
        except (ValueError, TypeError, AttributeError):
            wc_count = 0
        log.info(f'轮询到CQE数量: {wc_count}')
        if wc_count == 0:
            msg = '未轮询到任何CQE。'
            log.error(msg)
            cls._report_bug(msg, '应轮询到CQE')

        status, wc_str = cls._ipvbs.exec_and_get_ipvbs_result(
            "str(rdma_dict.get('wc'))",
            print_steps=False,
            print_outputs=False,
        )
        if status != IpvbsStatusEnum.SUCCESS.value or not wc_str:
            msg = '获取CQE信息失败。'
            log.error(msg)
            cls._report_bug(msg, '应成功获取CQE')
        log.info(f'最后一个CQE信息: {wc_str}')

        status_name = cls._extract_hex_or_word(wc_str, 'status')
        syndrome = cls._extract_hex_value(wc_str, 'syndrome')
        minor_syndrome = cls._extract_hex_value(
            wc_str, 'minor_syndrome'
        )
        vendor_err = cls._extract_hex_value(wc_str, 'vendor_err')

        # 若未直接提取到 syndrome/minor_syndrome，尝试从 vendor_err
        # 组合推断（低字节/高字节）。此处保留显式字段优先。
        if syndrome is None and vendor_err is not None:
            syndrome = (vendor_err >> 8) & 0xFF
        if minor_syndrome is None and vendor_err is not None:
            minor_syndrome = vendor_err & 0xFF

        check_pass = True
        if status_name != cls._EXP_CQE_STATUS:
            check_pass = False
            log.error(
                f'CQE状态不匹配: 实际={status_name}, '
                f'预期={cls._EXP_CQE_STATUS}'
            )
        if syndrome != cls._EXP_SYNDROME:
            check_pass = False
            log.error(
                f'CQE syndrome不匹配: 实际={syndrome}, '
                f'预期={cls._EXP_SYNDROME}'
            )
        if minor_syndrome != cls._EXP_MINOR_SYNDROME:
            check_pass = False
            log.error(
                f'CQE minor_syndrome不匹配: 实际={minor_syndrome}, '
                f'预期={cls._EXP_MINOR_SYNDROME}'
            )

        if not check_pass:
            msg = (
                f'CQE校验失败: status={status_name}, syndrome={syndrome}, '
                f'minor_syndrome={minor_syndrome}, vendor_err={vendor_err}'
            )
            cls._report_bug(
                msg,
                f'预期status={cls._EXP_CQE_STATUS}, '
                f'syndrome={hex(cls._EXP_SYNDROME)}, '
                f'minor_syndrome={hex(cls._EXP_MINOR_SYNDROME)}'
            )
        log.info('CQE校验通过。')

    @classmethod
    def _extract_hex_value(cls, text: str, field: str):
        """从文本中提取指定字段的十六进制值。"""
        match = re.search(
            rf"{field}\s*[=:]\s*(0x[0-9a-fA-F]+|\d+)", text
        )
        if match:
            value = match.group(1)
            return int(value, 16) if value.startswith('0x') else int(value)
        return None

    @classmethod
    def _extract_hex_or_word(cls, text: str, field: str) -> str:
        """从文本中提取指定字段的字符串或单词值。"""
        match = re.search(
            rf"{field}\s*[=:]\s*('[^']*'|\"[^\"]*\"|\w+)", text
        )
        if match:
            value = match.group(1)
            return value.strip("'\"")
        return ''

    @classmethod
    def _verify_aeq(cls):
        """校验无新增AEQ事件。"""
        diff_dict = RdmaCQ.debugfs_ae_check(
            scgbe_ae_dict_start=cls._aeq_baseline,
            rdma_bus=cls._rdma_bus,
            cmd_execute_address=cls._exec_addr,
        )
        if diff_dict:
            msg = f'检测到未预期的AEQ事件上报: {diff_dict}'
            log.error(msg)
            cls._report_bug(msg, '应无AEQ事件上报')
        log.info('AEQ校验通过，无新增事件。')

    @classmethod
    def _verify_qp_state(cls):
        """校验QP最终进入Error/Destroyed状态。"""
        status, qp_state = cls._ipvbs.exec_and_get_ipvbs_result(
            "rdma_dict['qp1'].state",
            print_steps=False,
            print_outputs=False,
        )
        if status != IpvbsStatusEnum.SUCCESS.value:
            # 获取状态失败通常意味着QP已被驱动销毁
            log.info(
                f'获取QP状态失败，认为QP已被销毁: {qp_state}'
            )
            return

        log.info(f'QP最终状态: {qp_state}')
        state_val = None
        try:
            state_val = int(qp_state.strip())
        except (ValueError, TypeError, AttributeError):
            pass

        # IBV_QPS_ERR = 6
        if state_val != 6:
            msg = (
                f'QP状态校验失败: 实际={qp_state}, '
                f'预期=ERR(6)/DESTROYED'
            )
            log.error(msg)
            cls._report_bug(msg, 'QP应进入Error状态或被销毁')
        log.info('QP状态校验通过。')

    @classmethod
    def _exec_ipvbs_list(cls, cmd_list, err_msg, raise_err=True):
        """批量执行Ipvbs命令并校验结果。"""
        for cmd in cmd_list:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(
                cmd, print_steps=False, print_outputs=False
            )
            if status != IpvbsStatusEnum.SUCCESS.value and raise_err:
                detail = f'{err_msg}: cmd={cmd}, result={result}'
                log.error(detail)
                cls._report_bug(detail, 'Ipvbs命令应执行成功')

    @classmethod
    def _report_bug(cls, result_info, expect_info):
        """调用公共接口记录缺陷并抛出异常。"""
        CommonOperation.create_bug_problem(
            case_cls=cls,
            key_word='RDMA SQ DMA异常错误处理',
            description_word=result_info,
            result_info=result_info,
            expect_info=expect_info,
            level=-1,
        )


if __name__ == '__main__':
    NicLinuxRdmaFaultR0689001001SqDmaException.run()
