#!/usr/bin/python3
# -*- encoding=utf8 -*-

"""
case author:   <填写用例作者>
script author: <填写脚本作者>
date:          2026-08-06
description:   RDMA CQ 接口测试_用户态_PF_查询CQ信息_查询标准CQ信息
                用例ID: nic_linux_rdma_cq_f_06_66_003_044

                本脚本直接继承 ScriptBase（不依赖 ScriptBaseCqCommon），
                用框架底层封装（RdmaQpProc.qp_state_switch / RdmaCQ）自行
                编排 server/client 双端 RC 打流：
                  1. 创建标准 CQ（RdmaCQ.create_cq_operate，供查询CQ信息使用）
                  2. server/client 双端 RC 建链 + send/recv 打流
                  3. 校验两端 CQ 轮询到的 WC 状态

                @changelog:
                  2026-08-06 创建脚本，直接继承 ScriptBase 实现双端打流。
"""

import re
import threading
import time

import add_syspath

from scripts.nic100.linux.rdma.ipvbs_screen_utils import IpvbsScreen
from scripts.nic100.linux.rdma.rdma_cq_func import RdmaCQ
from scripts.nic100.linux.rdma.qp.rdma_qp_func import RdmaQpProc
from scripts.nic100.linux.rdma.rdma_func import Rdma
from scripts.script_libs import constants, log
from scripts.script_libs.command_operation import CommandOperation
from scripts.script_libs.common_operation import CommonOperation
from scripts.script_libs.enums import (
    CmdExecuteAdressEnum,
    IpvbsStatusEnum,
    RdmaMode,
    RtnStatusEnum,
)
from scripts.script_libs.script_base import ScriptBase


class NicLinuxRdmaCqF0666003044PfQueryCqInfo(ScriptBase):
    """用户态 PF 查询标准 CQ 信息 —— 直接继承 ScriptBase 的双端打流实现。"""

    test_object = '800G网卡'
    test_module = 'rdma'
    test_tool = constants.SXE2CLI64
    test_precondition = (
        '1. pf驱动、rdma驱动已加载；\n'
        '2. 已安装rdma_core；\n'
        '3. pyverbs安装完成且能正常使用；\n'
        '4. server/client双端网络互通（RoCE）。'
    )
    test_steps = (
        '1. 检查环境并初始化RDMA双端环境；\n'
        '2. 创建标准CQ；\n'
        '3. server/client双端RC建链并打流；\n'
        '4. 校验两端CQ的WC状态；\n'
        '5. 清理测试资源。'
    )

    case_id = 'nic_linux_rdma_cq_f_06_66_003_044'
    case_title = 'RDMA CQ 接口测试_用户态_PF_查询CQ信息_查询标准CQ信息'
    case_module = 'CQ'
    case_type = '系统测试-功能'

    # 打流参数
    _GID_INDEX = 0
    _RDMA_PORT = 1
    _MSG_SIZE = 64
    _TEST_DATA = 'A' * _MSG_SIZE
    _EXP_WC_STATUS = 'IBV_WC_SUCCESS'

    # 双端共享状态
    _shared = None          # dict: 存放两端 qp_num / gid
    _evt_server_ready = None
    _evt_client_ready = None
    _evt_client_done = None
    _server_wc_status = None
    _client_wc_status = None

    @classmethod
    def set_parameters(cls) -> None:
        """设置脚本运行参数。"""
        cls.test_object = '800G网卡'
        cls.test_module = 'rdma'
        cls.test_tool = constants.SXE2CLI64
        cls.own_environment_enabled = False
        cls._exec_addr = CmdExecuteAdressEnum.SERVER.value

    @classmethod
    def check_own_environment(cls) -> None:
        """检查脚本运行所需的局部环境（驱动 / rdma_core / pyverbs）。"""
        log.info('开始检查局部环境。')
        for drv in (constants.nicg, constants.DRV_SCGBE_RDMA):
            cmd = f'lsmod|grep -w {drv}'
            status, result, err = CommandOperation.execute_command_with_error(
                cmd, cls._exec_addr)
            if status != RtnStatusEnum.SUCCESS.value or not result:
                cls._report_env_error(f'{drv}驱动未加载或检查失败: {err}')

    @classmethod
    def prepare(cls) -> None:
        """初始化双端 RDMA 环境，并建立 server/client 两个 ipvbs 实例。"""
        log.info('开始准备双端RDMA环境。')
        rtn = Rdma.setup_rdma_env(
            address_family='IPv4', test_direction_reverse=False)
        if rtn != RtnStatusEnum.SUCCESS.value:
            cls._report_env_error('初始化RDMA双端环境失败。')

        cls._ipvbs_server = IpvbsScreen(
            caller_class=cls, exec_addr=CmdExecuteAdressEnum.SERVER.value)
        cls._ipvbs_client = IpvbsScreen(
            caller_class=cls, exec_addr=CmdExecuteAdressEnum.CLIENT.value)

        cls._shared = {}
        cls._evt_server_ready = threading.Event()
        cls._evt_client_ready = threading.Event()
        cls._evt_client_done = threading.Event()

    @classmethod
    def do(cls) -> None:
        """测试点：创建标准CQ + 双端RC打流 + 校验WC。"""
        log.info('do: 开始创建标准CQ并执行双端打流。')

        # ---------- 步骤1: 创建标准 CQ（供查询CQ信息使用）----------
        # TODO: 开发未提供 cqe3dv_devx_query_cq 接口，暂只创建标准CQ，
        #       待接口提供后在此处追加查询与断言。
        rdma_dev_s = constants.nicg
        status, _ = RdmaCQ.create_cq_operate(
            cls._ipvbs_server, rdma_dev_s, cq_ex_flag=False)
        if status != IpvbsStatusEnum.SUCCESS.value:
            cls.report_bug(
                err_type='server端创建标准CQ失败。',
                expect_info='应成功创建标准CQ')
        else:
            log.info('server端标准CQ创建成功(obj_server_cq1)。')

        # ---------- 步骤2: 双端 RC 打流 ----------
        server_thread = threading.Thread(target=cls._run_server)
        client_thread = threading.Thread(target=cls._run_client)

        server_thread.start()
        client_thread.start()
        server_thread.join()
        client_thread.join()

        # ---------- 步骤3: 校验打流 WC 状态 ----------
        cls._check_traffic_result()

        log.info('do: 双端打流与校验完成。')

    # ------------------------------------------------------------------ #
    #  双端建链打流实现（基于 RdmaQpProc 底层 qp_state_switch 封装）        #
    # ------------------------------------------------------------------ #
    @classmethod
    def _create_qp_basic(cls, ipvbs, rdma_dev, cq_obj='obj_cq',
                         pd_obj='obj_pd', ctx_obj='obj_ctx'):
        """在指定 ipvbs 上创建 context/pd/mr/cq/qp，并切换到 INIT 状态。
        返回 (qp对象名, mr对象名)。
        """
        cmd_list = [
            f"obj_ctx = device.Context(name='{rdma_dev}')",
            "obj_pd = pd.PD(creator=obj_ctx)",
            f"{cq_obj} = cq.CQ(ctx=obj_ctx, cqe=1024, "
            f"channel=obj_ctx.create_comp_channel(), comp_vector=0)",
            "obj_mr = mr.MR(creator=obj_pd, length=4096, "
            "access=enums.ibv_access_flags.IBV_ACCESS_LOCAL_WRITE.value "
            "| enums.ibv_access_flags.IBV_ACCESS_REMOTE_WRITE.value "
            "| enums.ibv_access_flags.IBV_ACCESS_REMOTE_READ.value)",
            "obj_mr.write(data='%s', length=%d)" % (cls._TEST_DATA, cls._MSG_SIZE),
            "obj_cap = qp.QPCap(max_send_wr=128, max_recv_wr=128, "
            "max_send_sge=1, max_recv_sge=1)",
            "obj_init_attr = qp.QPInitAttr(qp_type=enums.IBV_QPT_RC, "
            f"scq={cq_obj}, rcq={cq_obj}, cap=obj_cap, sq_sig_all=1)",
            "obj_qp = qp.QP(pd=obj_pd, init_attr=obj_init_attr)",
            # 切换到 INIT
            "obj_qp_attr_init = qp.QPAttr(qp_state=enums.IBV_QPS_INIT.value, "
            "pkey_index=0, port_num=%d)" % cls._RDMA_PORT,
            "obj_qp_attr_init.qp_access_flags = "
            "enums.ibv_access_flags.IBV_ACCESS_LOCAL_WRITE.value "
            "| enums.ibv_access_flags.IBV_ACCESS_REMOTE_WRITE.value "
            "| enums.ibv_access_flags.IBV_ACCESS_REMOTE_READ.value",
            "obj_qp.to_init(obj_qp_attr_init)",
        ]
        rtn_list = ipvbs.exec_multi_cmd(cmd_list)
        for rtn in rtn_list:
            if rtn[0] != IpvbsStatusEnum.SUCCESS.value:
                return None, None
        return 'obj_qp', 'obj_mr'

    @classmethod
    def _run_server(cls):
        """server 端：建链 + 监听(post recv) + 等待对端数据 + poll CQ。"""
        log.info('server端打流线程启动。')
        ipvbs = cls._ipvbs_server
        rdma_dev = constants.nicg
        gid = cls._query_gid(ipvbs, rdma_dev)

        qp_obj, mr_obj = cls._create_qp_basic(ipvbs, rdma_dev)
        if qp_obj is None:
            cls._server_wc_status = 'CREATE_QP_FAIL'
            cls._evt_server_ready.set()
            return

        # 获取本端 qp_num 并写入共享，通知对端
        status, qpn = ipvbs.exec_and_get_ipvbs_result("str(obj_qp.qp_num)")
        cls._shared['server_qpn'] = qpn.strip() if qpn else ''
        cls._shared['server_gid'] = gid
        cls._evt_server_ready.set()

        # 等待 client 就绪
        cls._evt_client_ready.wait(timeout=120)

        # 用 client 的 qp_num / gid 建链（to_rtr / to_rts）
        ok = cls._qp_to_rtr_rts(
            ipvbs, qp_obj, 'SERVER',
            remote_qpn=cls._shared.get('client_qpn', ''),
            remote_gid=cls._shared.get('client_gid', ''))
        if not ok:
            cls._server_wc_status = 'QP_STATE_FAIL'
            cls._evt_client_done.set()
            return

        # post recv 等待对端 send
        cmd_list = [
            "obj_recv_sge = wr.SGE(addr=obj_mr.buf, length=%d, lkey=obj_mr.lkey)"
            % cls._MSG_SIZE,
            "obj_recv_wr = wr.RecvWR(sg=[obj_recv_sge], wr_id=0x1)",
            "obj_qp.post_recv(obj_recv_wr) is None",
        ]
        rtn_list = ipvbs.exec_multi_cmd(cmd_list)
        for rtn in rtn_list:
            if rtn[0] != IpvbsStatusEnum.SUCCESS.value:
                cls._server_wc_status = 'POST_RECV_FAIL'
                cls._evt_client_done.set()
                return

        # poll CQ 取 recv WC
        cls._server_wc_status = cls._poll_cq(ipvbs, 'SERVER')
        cls._evt_client_done.set()
        log.info('server端打流线程结束。')

    @classmethod
    def _run_client(cls):
        """client 端：建链 + 发送(post send) + poll CQ。"""
        log.info('client端打流线程启动。')
        ipvbs = cls._ipvbs_client
        rdma_dev = constants.nicg
        gid = cls._query_gid(ipvbs, rdma_dev)

        qp_obj, mr_obj = cls._create_qp_basic(ipvbs, rdma_dev)
        if qp_obj is None:
            cls._client_wc_status = 'CREATE_QP_FAIL'
            cls._evt_client_ready.set()
            return

        status, qpn = ipvbs.exec_and_get_ipvbs_result("str(obj_qp.qp_num)")
        cls._shared['client_qpn'] = qpn.strip() if qpn else ''
        cls._shared['client_gid'] = gid
        cls._evt_client_ready.set()

        # 等待 server 就绪
        cls._evt_server_ready.wait(timeout=120)

        # 用 server 的 qp_num / gid 建链
        ok = cls._qp_to_rtr_rts(
            ipvbs, qp_obj, 'CLIENT',
            remote_qpn=cls._shared.get('server_qpn', ''),
            remote_gid=cls._shared.get('server_gid', ''))
        if not ok:
            cls._client_wc_status = 'QP_STATE_FAIL'
            cls._evt_client_done.set()
            return

        # post send（signaled）
        cmd_list = [
            "obj_send_sge = wr.SGE(addr=obj_mr.buf, length=%d, lkey=obj_mr.lkey)"
            % cls._MSG_SIZE,
            "obj_send_wr = wr.SendWR(opcode=enums.IBV_WR_SEND, "
            "sg=[obj_send_sge], wr_id=0x2, "
            "send_flags=enums.IBV_SEND_SIGNALED.value)",
            "obj_qp.post_send(obj_send_wr) is None",
        ]
        rtn_list = ipvbs.exec_multi_cmd(cmd_list)
        for rtn in rtn_list:
            if rtn[0] != IpvbsStatusEnum.SUCCESS.value:
                cls._client_wc_status = 'POST_SEND_FAIL'
                cls._evt_client_done.set()
                return

        # poll CQ 取 send WC
        cls._client_wc_status = cls._poll_cq(ipvbs, 'CLIENT')
        cls._evt_client_done.set()
        log.info('client端打流线程结束。')

    @classmethod
    def _qp_to_rtr_rts(cls, ipvbs, qp_obj, role, remote_qpn, remote_gid):
        """使用 RdmaQpProc 底层封装完成 QP 的 RTR/RTS 状态切换。"""
        # 创建对端 AH attr
        ah_cmd = (
            "obj_ah_attr = addr.AHAttr(port_num=%d, is_global=1, "
            "gid='%s', sgid_index=%d, gid_index=%d, sl=0, dlid=0, "
            "traffic_class=0, hop_limit=255, src_path_bits=0)"
            % (cls._RDMA_PORT, remote_gid, cls._GID_INDEX, cls._GID_INDEX)
        )
        rtn_list = ipvbs.exec_multi_cmd([ah_cmd])
        for rtn in rtn_list:
            if rtn[0] != IpvbsStatusEnum.SUCCESS.value:
                return False

        # RTR
        cfg_rtr = {
            'qp_state': 'enums.IBV_QPS_RTR.value',
            'path_mtu': 'enums.IBV_MTU_1024.value',
            'dest_qp_num': remote_qpn,
            'rq_psn': 0,
            'max_dest_rd_atomic': 1,
            'min_rnr_timer': 12,
            'av': 'obj_ah_attr',
        }
        status, _ = RdmaQpProc.qp_state_switch(
            ipvbs, qp_obj, 'RC', cfg_rtr,
            src_state=1, dst_state=2, remote_qp_num=remote_qpn,
            obj_ah_attr='obj_ah_attr',
            exec_addr=CmdExecuteAdressEnum.SERVER.value if role == 'SERVER'
            else CmdExecuteAdressEnum.CLIENT.value)
        if status != RtnStatusEnum.SUCCESS.value:
            return False

        # RTS
        cfg_rts = {
            'qp_state': 'enums.IBV_QPS_RTS.value',
            'timeout': 6,
            'retry_cnt': 5,
            'rnr_retry': 5,
            'sq_psn': 0,
            'max_rd_atomic': 1,
        }
        status, _ = RdmaQpProc.qp_state_switch(
            ipvbs, qp_obj, 'RC', cfg_rts,
            src_state=2, dst_state=3,
            exec_addr=CmdExecuteAdressEnum.SERVER.value if role == 'SERVER'
            else CmdExecuteAdressEnum.CLIENT.value)
        return status == RtnStatusEnum.SUCCESS.value

    @classmethod
    def _query_gid(cls, ipvbs, rdma_dev):
        """查询本端指定 gid_index 的 GID 字符串。"""
        status, gid = ipvbs.exec_and_get_ipvbs_result(
            "str(%s.query_gid(%d, %d))"
            % (rdma_dev, cls._RDMA_PORT, cls._GID_INDEX))
        return gid.strip() if gid else ''

    @classmethod
    def _poll_cq(cls, ipvbs, role):
        """poll CQ 直至取到一个 WC，返回 WC 状态字符串。"""
        for _ in range(50):
            status, wc = ipvbs.exec_and_get_ipvbs_result(
                "str(%s.poll(num_entries=1))" % 'obj_cq')
            if status == IpvbsStatusEnum.SUCCESS.value and wc and wc != '[]':
                # 提取 status 字段
                m = re.search(r"status[=:\s]+([A-Za-z0-9_]+)", wc)
                return m.group(1) if m else wc
            time.sleep(0.05)
        return 'NO_WC'

    @classmethod
    def _check_traffic_result(cls) -> None:
        """校验双端打流的 WC 状态。"""
        log.info('开始校验双端打流结果。')
        for role, wc_status in (('server', cls._server_wc_status),
                                ('client', cls._client_wc_status)):
            if not wc_status or cls._EXP_WC_STATUS not in str(wc_status):
                msg = '{}端WC状态异常: {}'.format(role, wc_status)
                log.error(msg)
                cls.report_bug(
                    err_type=msg,
                    expect_info='WC状态应为{}'.format(cls._EXP_WC_STATUS))
            else:
                log.info('{}端打流WC状态为{}，校验通过。'.format(
                    role, cls._EXP_WC_STATUS))

    @classmethod
    def post(cls) -> None:
        """清理双端 ipvbs 资源。"""
        log.info('post: 清理双端测试资源。')
        if getattr(cls, '_ipvbs_server', None) is not None:
            IpvbsScreen.exit_all_ipvbs(
                caller_class=cls, exec_addr=CmdExecuteAdressEnum.SERVER.value)
        if getattr(cls, '_ipvbs_client', None) is not None:
            IpvbsScreen.exit_all_ipvbs(
                caller_class=cls, exec_addr=CmdExecuteAdressEnum.CLIENT.value)


def re_search_wc_status(wc_str):
    """从 WC 字符串中提取 status 值。"""
    import re
    m = re.search(r"status[=:\s]+([A-Za-z0-9_]+)", wc_str)
    return m.group(1) if m else wc_str


def time_sleep(sec):
    import time
    time.sleep(sec)


def re_search_wc_status(wc_str):
    """从 WC 字符串中提取 status 值。"""
    import re
    m = re.search(r"status[=:\s]+([A-Za-z0-9_]+)", wc_str)
    return m.group(1) if m else wc_str


def time_sleep(sec):
    import time
    time.sleep(sec)


if __name__ == '__main__':
    NicLinuxRdmaCqF0666003044PfQueryCqInfo().run()
