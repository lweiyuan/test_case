#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时测试脚本：验证 DevX 资源创建能力。"""
import add_syspath

from scripts.nic100.linux.rdma.ipvbs_screen_utils import IpvbsScreen
from scripts.script_libs import log
from scripts.script_libs.enums import (
    CmdExecuteAdressEnum,
    IpvbsCommuEnum,
    IpvbsStatusEnum,
)
from scripts.script_libs.script_base import ScriptBase


class TestDevxResources(ScriptBase):
    case_id = 'test_devx_resources'
    case_title = 'Test DevX Resources'
    case_module = 'DevX'
    case_type = '临时测试'

    @classmethod
    def set_parameters(cls) -> None:
        cls.own_environment_enabled = False
        cls._exec_addr = CmdExecuteAdressEnum.SERVER.value

    @classmethod
    def check_own_environment(cls) -> None:
        cls.own_environment_enabled = True

    @classmethod
    def prepare(cls) -> None:
        cls._ipvbs = IpvbsScreen(caller_class=cls, exec_addr=cls._exec_addr,
                                 commu=IpvbsCommuEnum.SOCKET.value)

    @classmethod
    def do(cls) -> None:
        cmds = [
            "glb_helper = __import__('devx_qp_helper')",
            "glb_mlx5dv = __import__('pyverbs.providers.mlx5.mlx5dv', fromlist=['Mlx5Context', 'Mlx5DVContextAttr', 'Mlx5DevxObj', 'Mlx5UMEM', 'Mlx5UAR'])",
            "glb_ctx = glb_mlx5dv.Mlx5Context(glb_mlx5dv.Mlx5DVContextAttr(), 'mlx5_0')",
            "glb_pd_ret = glb_helper.create_devx_pd(glb_ctx)",
            "glb_pd_obj = glb_pd_ret[0]",
            "glb_pdn = glb_pd_ret[1]",
            "str(glb_pdn)",
            "glb_uar = glb_mlx5dv.Mlx5UAR(glb_ctx)",
            "str(glb_uar.page_id)",
            "glb_eqn = glb_ctx.devx_query_eqn(0)",
            "str(glb_eqn)",
            "glb_resource = __import__('resource')",
            "glb_cq_umem = glb_mlx5dv.Mlx5UMEM(glb_ctx, size=16384)",
            "glb_cq_dbr = glb_mlx5dv.Mlx5UMEM(glb_ctx, size=8, alignment=8)",
            "glb_cq_ret = glb_helper.create_devx_cq(glb_ctx, glb_eqn, glb_uar, glb_cq_umem, glb_cq_dbr)",
            "glb_cq_obj = glb_cq_ret[0]",
            "glb_cqn = glb_cq_ret[1]",
            "str(glb_cqn)",
            "glb_qp_umem = glb_mlx5dv.Mlx5UMEM(glb_ctx, size=glb_resource.getpagesize())",
            "glb_qp_dbr = glb_mlx5dv.Mlx5UMEM(glb_ctx, size=8, alignment=8)",
            "glb_qp_ret = glb_helper.create_devx_qp(glb_ctx, glb_pdn, glb_uar, glb_cq_obj, glb_qp_umem, glb_qp_dbr)",
            "glb_qp_obj = glb_qp_ret[0]",
            "glb_qpn = glb_qp_ret[1]",
            "str(glb_qpn)",
        ]
        for cmd in cmds:
            status, result = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            log.info(f'{cmd}: status={status}, result={result[:200] if result else None}')
            if status != IpvbsStatusEnum.SUCCESS.value:
                break

    @classmethod
    def post(cls) -> None:
        IpvbsScreen.exit_all_ipvbs(exec_addr=cls._exec_addr,
                                   commu=IpvbsCommuEnum.SOCKET.value)


if __name__ == '__main__':
    TestDevxResources().run()
