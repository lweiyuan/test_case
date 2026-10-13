#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
author:      weifeng.meng
date:        2025/3/11
description:
"""

# pcie_utils
SETPCI_SPACE = ""
SETPCI = "/usr/local/bin/setpci"
#SETPCI = "/usr/sbin/setpci"
SETPCI_VERSION = "3.14.0"

LSPCI_SPACE = ""
LSPCI = "/usr/local/bin/lspci"
#LSPCI = "/usr/sbin/lspci"
LSPCI_VERSION = "3.14.0"

# pcie_info
TYVENDER_ID = "1ff2"
TYDEVICE_ID_PF = "10b1"
TYDEVICE_ID_VF = "10b2"


# pcicrawler
PCICRAWLER= "pcicrawler"
PF_ID = [(8178, 4273, 'endpoint')]
VF_ID = [(8178, 4274, 'endpoint')]

# sxeclid_1.6.0.4_x86_64 私有寄存器切lane
SXECLID = "sxe2cli"
REG_LANE = "0x950008c0"

#
IPERF_LOG_PATH="/home/iperf_log"

# vendor spec cap
#VENDOR_SPEC_CAP = "280"
VENDOR_SPEC_CAP = "25C"