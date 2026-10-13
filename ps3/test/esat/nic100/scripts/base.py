scripts_generate = '''#!/usr/bin/python3
# -*- coding:utf-8 -*-

"""
case number: %s
case title: %s
test category: %s
check point: %s
test platform: 物理平台&虚拟平台

author: lihr
date: 2026.05.09
@steps:
%s

@changelog:
"""
import add_syspath
from scripts.nic800.linux.rdma.kernel.dif.script_base_kernel_rdma_dif_reliability_test import ScriptBaseRdmaDif


class ScriptBaseRdma(ScriptBaseRdmaDif):

    @classmethod
    def set_parameters(cls) -> None:
        super().set_parameters()
        
        cls.case_title = "%s"
        
def main() -> None:
    ScriptBaseRdma.run()


if __name__ == '__main__':
    main()
'''
