#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DevX QP/CQ/PD 创建辅助模块（基于 MLX5 PRM，依赖 scapy）。

该文件会被上传到远端测试节点（/root/sxetest/devx_qp_helper.py），
供 ipvbs 运行时通过 __import__ 加载，用于构造正确的 DevX CREATE_QP buffer。
"""
import resource
import struct
import math
import random

import logging
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
from scapy.packet import Packet
from scapy.fields import BitField, ByteField, IntField, ShortField, LongField, \
    StrFixedLenField, PacketField, PacketListField, PadField, FieldListField


class DevxOps:
    MLX5_CMD_OP_NOP = 0x80d
    MLX5_CMD_OP_QUERY_HCA_CAP = 0x100
    MLX5_CMD_OP_QUERY_HCA_VPORT_CONTEXT = 0x762
    MLX5_CMD_OP_QUERY_CONG_STATUS = 0x822
    MLX5_CMD_OP_QUERY_CONG_PARAMS = 0x824
    MLX5_CMD_OP_QUERY_CONG_STATISTICS = 0x826
    MLX5_CMD_OP_ALLOC_PD = 0x800
    MLX5_CMD_OP_CREATE_CQ = 0x400
    MLX5_CMD_OP_QUERY_CQ = 0x402
    MLX5_CMD_OP_MODIFY_CQ = 0x403
    MLX5_CMD_OP_CREATE_QP = 0x500
    MLX5_CMD_OP_DESTROY_QP = 0x501
    MLX5_CMD_OP_QUERY_QP = 0x50b
    MLX5_CMD_OP_CREATE_SRQ = 0x700
    MLX5_CMD_OP_DESTROY_SRQ = 0x701
    MLX5_CMD_OP_QUERY_SRQ = 0x702
    MLX5_CMD_OP_CREATE_MKEY = 0x200
    MLX5_CMD_OP_QUERY_MKEY = 0x201
    MLX5_CMD_OP_ALLOC_Q_COUNTER = 0x771
    MLX5_CMD_OP_DEALLOC_Q_COUNTER = 0x772
    MLX5_CMD_OP_QUERY_Q_COUNTER = 0x773
    MLX5_CMD_OP_CREATE_GENERAL_OBJECT = 0xa00
    MLX5_OBJ_TYPE_RESERVED_QPN = 0x002C
    MLX5_OBJ_TYPE_MKEY = 0xff01
    MLX5_QPC_ST_RC = 0x0
    MLX5_QPC_PM_STATE_MIGRATED = 0x3


class PRMPacket(Packet):
    def extract_padding(self, p):
        return "", p


class SwPas(PRMPacket):
    fields_desc = [
        IntField('pa_h', 0),
        BitField('pa_l', 0, 20),
        BitField('reserved1', 0, 12),
    ]


class AllocPdIn(PRMPacket):
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_ALLOC_PD),
        ShortField('uid', 0),
        ShortField('reserved1', 0),
        ShortField('op_mod', 0),
        StrFixedLenField('reserved2', None, length=8),
    ]


class GeneralObjInCmdHdr(PRMPacket):
    fields_desc = [
        ShortField('opcode', 0),
        ShortField('uid', 0),
        ShortField('reserved1', 0),
        ShortField('obj_type', 0),
        IntField('obj_id', 0),
        BitField('reserved2', 0, 3),
        BitField('log_obj_range', 0, 5),
        StrFixedLenField('reserved3', None, length=3),
    ]


class ReservedQpnBits(PRMPacket):
    fields_desc = [
        StrFixedLenField('reserved', None, length=16),
    ]


class CreateReservedQpnIn(PRMPacket):
    fields_desc = [
        PacketField('hdr', GeneralObjInCmdHdr(), GeneralObjInCmdHdr),
        PacketField('rqpns', ReservedQpnBits(), ReservedQpnBits),
    ]


class GeneralObjOutCmdHdr(PRMPacket):
    fields_desc = [
        ByteField('status', 0),
        BitField('reserved1', 0, 24),
        IntField('syndrome', 0),
        IntField('obj_id', 0),
        StrFixedLenField('reserved2', None, length=4),
    ]


class AllocPdOut(PRMPacket):
    fields_desc = [
        ByteField('status', 0),
        BitField('reserved1', 0, 24),
        IntField('syndrome', 0),
        ByteField('reserved2', 0),
        BitField('pd', 0, 24),
        StrFixedLenField('reserved3', None, length=4),
    ]


class SwCqc(PRMPacket):
    fields_desc = [
        BitField('status', 0, 4),
        BitField('as_notify', 0, 1),
        BitField('initiator_src_dct', 0, 1),
        BitField('dbr_umem_valid', 0, 1),
        BitField('reserved1', 0, 1),
        BitField('cqe_sz', 0, 3),
        BitField('cc', 0, 1),
        BitField('reserved2', 0, 1),
        BitField('scqe_break_moderation_en', 0, 1),
        BitField('oi', 0, 1),
        BitField('cq_period_mode', 0, 2),
        BitField('cqe_compression_en', 0, 1),
        BitField('mini_cqe_res_format', 0, 2),
        BitField('st', 0, 4),
        ByteField('reserved3', 0),
        IntField('dbr_umem_id', 0),
        BitField('reserved4', 0, 20),
        BitField('page_offset', 0, 6),
        BitField('reserved5', 0, 6),
        BitField('reserved6', 0, 3),
        BitField('log_cq_size', 0, 5),
        BitField('uar_page', 0, 24),
        BitField('reserved7', 0, 4),
        BitField('cq_period', 0, 12),
        ShortField('cq_max_count', 0),
        BitField('reserved8', 0, 24),
        ByteField('c_eqn', 0),
        BitField('reserved9', 0, 3),
        BitField('log_page_size', 0, 5),
        BitField('reserved10', 0, 24),
        StrFixedLenField('reserved11', None, length=4),
        ByteField('reserved12', 0),
        BitField('last_notified_index', 0, 24),
        ByteField('reserved13', 0),
        BitField('last_solicit_index', 0, 24),
        ByteField('reserved14', 0),
        BitField('consumer_counter', 0, 24),
        ByteField('reserved15', 0),
        BitField('producer_counter', 0, 24),
        BitField('local_partition_id', 0, 12),
        BitField('process_id', 0, 20),
        ShortField('reserved16', 0),
        ShortField('thread_id', 0),
        IntField('db_record_addr_63_32', 0),
        BitField('db_record_addr_31_3', 0, 29),
        BitField('reserved17', 0, 3),
    ]


class CreateCqIn(PRMPacket):
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_CREATE_CQ),
        ShortField('uid', 0),
        ShortField('reserved1', 0),
        ShortField('op_mod', 0),
        ByteField('reserved2', 0),
        BitField('cqn', 0, 24),
        StrFixedLenField('reserved3', None, length=4),
        PacketField('sw_cqc', SwCqc(), SwCqc),
        LongField('e_mtt_pointer_or_cq_umem_offset', 0),
        IntField('cq_umem_id', 0),
        BitField('cq_umem_valid', 0, 1),
        BitField('reserved4', 0, 31),
        StrFixedLenField('reserved5', None, length=176),
        PacketListField('pas', [], SwPas, count_from=lambda pkt: 0),
    ]


class CreateCqOut(PRMPacket):
    fields_desc = [
        ByteField('status', 0),
        BitField('reserved1', 0, 24),
        IntField('syndrome', 0),
        ByteField('reserved2', 0),
        BitField('cqn', 0, 24),
        StrFixedLenField('reserved3', None, length=4),
    ]


class ModifyCqIn(PRMPacket):
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_MODIFY_CQ),
        ShortField('uid', 0),
        ShortField('reserved1', 0),
        ShortField('op_mod', 0),
        ByteField('reserved2', 0),
        BitField('cqn', 0, 24),
        IntField('field_select', 0),
        PacketField('sw_cqc', SwCqc(), SwCqc),
        LongField('e_mtt_pointer_or_cq_umem_offset', 0),
        IntField('cq_umem_id', 0),
        BitField('cq_umem_valid', 0, 1),
        BitField('reserved4', 0, 31),
        StrFixedLenField('reserved5', None, length=176),
        PacketListField('pas', [], SwPas, count_from=lambda pkt: 0),
    ]


class ModifyCqOut(PRMPacket):
    fields_desc = [
        ByteField('status', 0),
        BitField('reserved1', 0, 24),
        IntField('syndrome', 0),
        ByteField('reserved2', 0),
        BitField('cqn', 0, 24),
        StrFixedLenField('reserved3', None, length=4),
    ]


class SwAds(PRMPacket):
    fields_desc = [
        BitField('fl', 0, 1),
        BitField('free_ar', 0, 1),
        BitField('reserved1', 0, 14),
        ShortField('pkey_index', 0),
        ByteField('reserved2', 0),
        BitField('grh', 0, 1),
        BitField('mlid', 0, 7),
        ShortField('rlid', 0),
        BitField('ack_timeout', 0, 5),
        BitField('reserved3', 0, 3),
        ByteField('src_addr_index', 0),
        BitField('log_rtm', 0, 4),
        BitField('stat_rate', 0, 4),
        ByteField('hop_limit', 0),
        BitField('reserved4', 0, 4),
        BitField('tclass', 0, 8),
        BitField('flow_label', 0, 20),
        StrFixedLenField('rgid_rip', b'\x00' * 16, length=16),
        BitField('reserved5', 0, 4),
        BitField('f_dscp', 0, 1),
        BitField('f_ecn', 0, 1),
        BitField('reserved6', 0, 1),
        BitField('f_eth_prio', 0, 1),
        BitField('ecn', 0, 2),
        BitField('dscp', 0, 6),
        ShortField('udp_sport', 0),
        BitField('dei_cfi_reserved_from_prm_041', 0, 1),
        BitField('eth_prio', 0, 3),
        BitField('sl', 0, 4),
        ByteField('vhca_port_num', 0),
        StrFixedLenField('rmac', b'\x00' * 6, length=6),
    ]


class SwQpc(PRMPacket):
    fields_desc = [
        BitField('state', 0, 4),
        BitField('lag_tx_port_affinity', 0, 4),
        ByteField('st', 0),
        BitField('reserved1', 0, 3),
        BitField('pm_state', 0, 2),
        BitField('reserved2', 0, 1),
        BitField('req_e2e_credit_mode', 0, 2),
        BitField('offload_type', 0, 4),
        BitField('end_padding_mode', 0, 2),
        BitField('reserved3', 0, 2),
        BitField('wq_signature', 0, 1),
        BitField('block_lb_mc', 0, 1),
        BitField('atomic_like_write_en', 0, 1),
        BitField('latency_sensitive', 0, 1),
        BitField('dual_write', 0, 1),
        BitField('drain_sigerr', 0, 1),
        BitField('multi_path', 0, 1),
        BitField('reserved4', 0, 1),
        BitField('pd', 0, 24),
        BitField('mtu', 0, 3),
        BitField('log_msg_max', 0, 5),
        BitField('reserved5', 0, 1),
        BitField('log_rq_size', 0, 4),
        BitField('log_rq_stride', 0, 3),
        BitField('no_sq', 0, 1),
        BitField('log_sq_size', 0, 4),
        BitField('reserved6', 0, 1),
        BitField('retry_mode', 0, 2),
        BitField('ts_format', 0, 2),
        BitField('data_in_order', 0, 1),
        BitField('rlkey', 0, 1),
        BitField('ulp_stateless_offload_mode', 0, 4),
        ByteField('counter_set_id', 0),
        BitField('uar_page', 0, 24),
        BitField('send_dbr_mode', 0, 2),
        BitField('reserved7', 0, 1),
        BitField('full_handshake', 0, 1),
        BitField('cnak_reverse_sl', 0, 4),
        BitField('user_index', 0, 24),
        BitField('reserved8', 0, 3),
        BitField('log_page_size', 0, 5),
        BitField('remote_qpn', 0, 24),
        PacketField('primary_address_path', SwAds(), SwAds),
        PacketField('secondary_address_path', SwAds(), SwAds),
        BitField('log_ack_req_freq', 0, 4),
        BitField('reserved9', 0, 4),
        BitField('log_sra_max', 0, 3),
        BitField('extended_rnr_retry_valid', 0, 1),
        BitField('reserved10', 0, 1),
        BitField('retry_count', 0, 3),
        BitField('rnr_retry', 0, 3),
        BitField('extended_retry_count_valid', 0, 1),
        BitField('fre', 0, 1),
        BitField('cur_rnr_retry', 0, 3),
        BitField('cur_retry_count', 0, 3),
        BitField('extended_log_rnr_retry', 0, 5),
        ShortField('extended_cur_rnr_retry', 0),
        ShortField('packet_pacing_rate_limit_index', 0),
        ByteField('reserved11', 0),
        BitField('next_send_psn', 0, 24),
        ByteField('reserved12', 0),
        BitField('cqn_snd', 0, 24),
        ByteField('reserved13', 0),
        BitField('deth_sqpn', 0, 24),
        ByteField('reserved14', 0),
        ByteField('extended_retry_count', 0),
        ByteField('reserved15', 0),
        ByteField('extended_cur_retry_count', 0),
        ByteField('reserved16', 0),
        BitField('last_acked_psn', 0, 24),
        ByteField('reserved17', 0),
        BitField('ssn', 0, 24),
        ByteField('reserved18', 0),
        BitField('log_rra_max', 0, 3),
        BitField('reserved19', 0, 1),
        BitField('atomic_mode', 0, 4),
        BitField('rre', 0, 1),
        BitField('rwe', 0, 1),
        BitField('rae', 0, 1),
        BitField('reserved20', 0, 1),
        BitField('page_offset', 0, 6),
        BitField('reserved21', 0, 3),
        BitField('cd_slave_receive', 0, 1),
        BitField('cd_slave_send', 0, 1),
        BitField('cd_master', 0, 1),
        BitField('reserved22', 0, 3),
        BitField('min_rnr_nak', 0, 5),
        BitField('next_rcv_psn', 0, 24),
        ByteField('reserved23', 0),
        BitField('xrcd', 0, 24),
        ByteField('reserved24', 0),
        BitField('cqn_rcv', 0, 24),
        LongField('dbr_addr', 0),
        IntField('q_key', 0),
        BitField('reserved25', 0, 5),
        BitField('rq_type', 0, 3),
        BitField('srqn_rmpn_xrqn', 0, 24),
        ByteField('reserved26', 0),
        BitField('rmsn', 0, 24),
        ShortField('hw_sq_wqebb_counter', 0),
        ShortField('sw_sq_wqebb_counter', 0),
        IntField('hw_rq_counter', 0),
        IntField('sw_rq_counter', 0),
        ByteField('reserved27', 0),
        BitField('roce_adp_retrans_rtt', 0, 24),
        BitField('reserved28', 0, 15),
        BitField('cgs', 0, 1),
        ByteField('cs_req', 0),
        ByteField('cs_res', 0),
        LongField('dc_access_key', 0),
        BitField('rdma_active', 0, 1),
        BitField('comm_est', 0, 1),
        BitField('suspended', 0, 1),
        BitField('dbr_umem_valid', 0, 1),
        BitField('reserved29', 0, 4),
        BitField('send_msg_psn', 0, 24),
        ByteField('reserved30', 0),
        BitField('rcv_msg_psn', 0, 24),
        LongField('rdma_va', 0),
        IntField('rdma_key', 0),
        IntField('dbr_umem_id', 0),
    ]


class CreateQpIn(PRMPacket):
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_CREATE_QP),
        ShortField('uid', 0),
        ShortField('reserved1', 0),
        ShortField('op_mod', 0),
        ByteField('reserved2', 0),
        BitField('input_qpn', 0, 24),
        BitField('reserved3', 0, 1),
        BitField('cmd_on_behalf', 0, 1),
        BitField('reserved4', 0, 14),
        ShortField('vhca_id', 0),
        IntField('opt_param_mask', 0),
        StrFixedLenField('reserved5', None, length=4),
        PacketField('sw_qpc', SwQpc(), SwQpc),
        LongField('e_mtt_pointer_or_wq_umem_offset', 0),
        IntField('wq_umem_id', 0),
        BitField('wq_umem_valid', 0, 1),
        BitField('reserved6', 0, 31),
        PacketListField('pas', [], SwPas, count_from=lambda pkt: 0),
    ]


class SwSrqc(PRMPacket):
    """mlx5_ifc_srqc_bits — SRQ context (512 bits = 64 bytes).

    Layout per PRM mlx5_ifc_srqc_bits:
        word 0 (byte  0): state(4) | log_srq_size(4) | reserved(24)
        word 1 (byte  4): wq_signature(1) | cont_srq(1) | rsv(1) | rlky(1) |
                          rsv(1) | log_rq_stride(3) | xrcd(24)
        word 2 (byte  8): page_offset(6) | reserved(2) | cqn(24)
        word 3 (byte 12): reserved(32)
        word 4 (byte 16): reserved(2) | log_page_size(6) | reserved(24)
        word 5 (byte 20): reserved(32)
        word 6 (byte 24): reserved(8) | pd(24)
        word 7 (byte 28): lwm(16) | wqe_cnt(16)
        word 8-9 (byte 32): reserved_at_100[0x40] (64 bits)
        word 10-11 (byte 40): dbr_addr[0x40] (64 bits)
        word 12-15 (byte 48): reserved_at_180[0x80] (128 bits)
        Total: 64 bytes
    """
    fields_desc = [
        # word 0 (4 bytes): state + log_srq_size + reserved
        BitField('state', 0, 4),
        BitField('log_srq_size', 0, 4),
        BitField('_rsv_w0', 0, 24),
        # word 1 (4 bytes): wq_signature | cont_srq | ... | log_rq_stride | xrcd
        BitField('wq_signature', 0, 1),
        BitField('cont_srq', 0, 1),
        BitField('_rsv1', 0, 1),
        BitField('rlky', 0, 1),
        BitField('_rsv2', 0, 1),
        BitField('log_rq_stride', 0, 3),
        BitField('xrcd', 0, 24),
        # word 2 (4 bytes): page_offset | reserved | cqn
        BitField('page_offset', 0, 6),
        BitField('_rsv3', 0, 2),
        BitField('cqn', 0, 24),
        # word 3 (4 bytes): reserved
        IntField('_rsv_w3', 0),
        # word 4 (4 bytes): reserved(2) | log_page_size(6) | reserved(24)
        BitField('_rsv4', 0, 2),
        BitField('log_page_size', 0, 6),
        BitField('_rsv5', 0, 24),
        # word 5 (4 bytes): reserved
        IntField('_rsv_w5', 0),
        # word 6 (4 bytes): reserved(8) | pd(24)
        BitField('_rsv6', 0, 8),
        BitField('pd', 0, 24),
        # word 7 (4 bytes): lwm(16) | wqe_cnt(16)
        ShortField('lwm', 0),
        ShortField('wqe_cnt', 0),
        # word 8-9 (8 bytes): reserved_at_100
        StrFixedLenField('_rsv_w8_9', None, length=8),
        # word 10-11 (8 bytes): dbr_addr
        LongField('dbr_addr', 0),
        # word 12-15 (16 bytes): reserved_at_180
        StrFixedLenField('_rsv_w12_15', None, length=16),
    ]


class CreateSrqIn(PRMPacket):
    """mlx5_ifc_create_srq_in_bits — PAS 模式（无 umem 字段）.

    CREATE_SRQ 与 CREATE_QP/CREATE_CQ 不同，不支持 umem_id 方式，
    只支持 PAS（Physical Address Segments）直接提供物理地址。

    Layout per PRM mlx5_ifc_create_srq_in_bits:
        header (16 bytes): opcode | uid | reserved | op_mod | reserved
        srq_context (64 bytes): mlx5_ifc_srqc_bits at byte offset 16
        reserved (192 bytes): byte offset 80-271
        pas[]: each entry 8 bytes, at byte offset 272
    Total without PAS: 272 bytes = MLX5_ST_SZ_BYTES(create_srq_in)
    """
    fields_desc = [
        # --- command header (16 bytes) ---
        ShortField('opcode', DevxOps.MLX5_CMD_OP_CREATE_SRQ),
        ShortField('uid', 0),
        ShortField('reserved1', 0),
        ShortField('op_mod', 0),
        StrFixedLenField('reserved2', None, length=8),
        # --- SRQ context at byte offset 16 (64 bytes) ---
        PacketField('sw_srqc', SwSrqc(), SwSrqc),
        # --- reserved (192 bytes) at byte offset 80 ---
        StrFixedLenField('reserved3', None, length=192),
        # --- PAS entries (each 8 bytes) at byte offset 272 ---
        PacketListField('pas', [], SwPas, count_from=lambda pkt: 0),
    ]


class CreateSrqOut(PRMPacket):
    """mlx5_ifc_create_srq_out_bits — 16 bytes.

    Layout per PRM (kernel create_srq_out_bits):
        byte  0: status(8) | reserved(24)
        byte  4: syndrome(32)
        byte  8: reserved(8) | srqn(24)
        byte 12: reserved(32)
        Total: 16 bytes

    Note: SRQN is obtained from DevX obj.obj_id, not parsed from output.
    """
    fields_desc = [
        ByteField('status', 0),
        BitField('reserved1', 0, 24),
        IntField('syndrome', 0),
        ByteField('reserved2', 0),
        BitField('srqn', 0, 24),
        StrFixedLenField('reserved3', None, length=4),
    ]


class SwMkc(PRMPacket):
    """mlx5_ifc_mkc_bits — MKEY context (512 bits = 64 bytes).

    Layout per Linux kernel mlx5_ifc.h mlx5_ifc_mkc_bits:
        word 0 (byte  0): free(1) | access_mode_4_2(3) |
                          relaxed_ordering_write(1) |
                          small_fence_on_rdma_read_response(1) | umr_en(1) |
                          a(1) | rw(1) | rr(1) | lw(1) | lr(1) |
                          access_mode_1_0(2) | ma_translation_mode(2)
        word 1 (byte  4): qpn(24) | mkey_7_0(8)
        word 2 (byte  8): reserved(32)
        word 3 (byte 12): length64(1) | bsf_en(1) | sync_umr(1) |
                          reserved(2) | expected_sigerr_count(1) |
                          reserved(1) | en_rinval(1) | pd(24)
        word 4-5 (byte 16): start_addr(64)
        word 6-7 (byte 24): len(64)
        word 8 (byte 32): bsf_octword_size(32)
        word 9-11 (byte 36): reserved(96)
        word 12 (byte 48): crossing_target_vhca_id(16) | reserved(16)
        word 13 (byte 52): translations_octword_size(32)
        word 14 (byte 56): relaxed_ordering_read(1) | reserved(1) |
                           log_page_size(6) | reserved(24)
        word 15 (byte 60): reserved(32)
        Total: 64 bytes
    """
    # MLX5_MKC_ACCESS_MODE_PA = 0x0, MTT = 0x1, KLMS = 0x2, KSM = 0x3
    fields_desc = [
        # word 0 (byte 0)
        BitField('free', 0, 1),
        BitField('access_mode_4_2', 0, 3),
        BitField('relaxed_ordering_write', 0, 1),
        BitField('small_fence_on_rdma_read_response', 0, 1),
        BitField('umr_en', 0, 1),
        BitField('a', 0, 1),
        BitField('rw', 0, 1),
        BitField('rr', 0, 1),
        BitField('lw', 0, 1),
        BitField('lr', 0, 1),
        BitField('access_mode_1_0', 0, 2),
        BitField('ma_translation_mode', 0, 2),
        # word 1 (byte 4): qpn(24) | mkey_7_0(8)
        BitField('qpn', 0, 24),
        BitField('mkey_7_0', 0, 8),
        # word 2 (byte 8): reserved
        IntField('_rsv_w2', 0),
        # word 3 (byte 12): length64 | bsf_en | sync_umr | ... | pd
        BitField('length64', 0, 1),
        BitField('bsf_en', 0, 1),
        BitField('sync_umr', 0, 1),
        BitField('_rsv3', 0, 2),
        BitField('expected_sigerr_count', 0, 1),
        BitField('_rsv4', 0, 1),
        BitField('en_rinval', 0, 1),
        BitField('pd', 0, 24),
        # word 4-5 (byte 16): start_addr
        LongField('start_addr', 0),
        # word 6-7 (byte 24): len
        LongField('len', 0),
        # word 8 (byte 32): bsf_octword_size
        IntField('bsf_octword_size', 0),
        # word 9-11 (byte 36): reserved
        StrFixedLenField('_rsv_w9_11', None, length=12),
        # word 12 (byte 48): crossing_target_vhca_id | reserved
        ShortField('crossing_target_vhca_id', 0),
        ShortField('_rsv_w12', 0),
        # word 13 (byte 52): translations_octword_size
        IntField('translations_octword_size', 0),
        # word 14 (byte 56): relaxed_ordering_read | log_page_size
        BitField('relaxed_ordering_read', 0, 1),
        BitField('_rsv_w14', 0, 1),
        BitField('log_page_size', 0, 6),
        BitField('_rsv_w14b', 0, 24),
        # word 15 (byte 60): reserved
        IntField('_rsv_w15', 0),
    ]


class CreateMkeyIn(PRMPacket):
    """mlx5_ifc_create_mkey_in_bits — 16 bytes header + 64 bytes MKC + reserved.

    Layout per PRM:
        byte  0: opcode(16) | uid(16)
        byte  4: reserved(16) | op_mod(16)
        byte  8: reserved(32)
        byte 12: pg_access(1) | mkey_umem_valid(1) | data_direct(1) |
                 reserved(29)
        byte 16: memory_key_mkey_entry = mlx5_ifc_mkc_bits (64 bytes)
        byte 80: reserved(128)
        byte 96: translations_octword_actual_size(32)
        byte 100: reserved(4)
        byte 104: pas[] (each 8 bytes)
    """
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_CREATE_MKEY),
        ShortField('uid', 0),
        ShortField('reserved1', 0),
        ShortField('op_mod', 0),
        StrFixedLenField('reserved2', None, length=8),
        BitField('pg_access', 0, 1),
        BitField('mkey_umem_valid', 0, 1),
        BitField('data_direct', 0, 1),
        BitField('reserved3', 0, 29),
        PacketField('mkc', SwMkc(), SwMkc),
        StrFixedLenField('reserved4', None, length=128),
        IntField('translations_octword_actual_size', 0),
        StrFixedLenField('reserved5', None, length=4),
        PacketListField('pas', [], SwPas, count_from=lambda pkt: 0),
    ]


class CreateMkeyOut(PRMPacket):
    """mlx5_ifc_create_mkey_out_bits — 16 bytes.

    Layout per PRM:
        byte  0: status(8) | reserved(24)
        byte  4: syndrome(32)
        byte  8: reserved(8) | mkey_index(24)
        byte 12: reserved(32)
        Total: 16 bytes
    """
    fields_desc = [
        ByteField('status', 0),
        BitField('reserved1', 0, 24),
        IntField('syndrome', 0),
        ByteField('reserved2', 0),
        BitField('mkey_index', 0, 24),
        StrFixedLenField('reserved3', None, length=4),
    ]


class CreateQpOut(PRMPacket):
    fields_desc = [
        ByteField('status', 0),
        BitField('reserved1', 0, 24),
        IntField('syndrome', 0),
        ByteField('reserved2', 0),
        BitField('qpn', 0, 24),
        StrFixedLenField('reserved3', None, length=4),
    ]


# --------------------------------------------------------------------------- #
# 辅助函数
# --------------------------------------------------------------------------- #

def roundup_pow_of_two(val):
    if val <= 1:
        return 1
    return 1 << (val - 1).bit_length()


def get_physical_addresses(buf_addr, size, page_size=4096):
    """读取 /proc/self/pagemap 获取虚拟地址对应的物理地址列表。

    需要 root 权限运行。返回每页的物理地址列表。
    """
    num_pages = (size + page_size - 1) // page_size
    addrs = []
    with open('/proc/self/pagemap', 'rb') as f:
        for i in range(num_pages):
            vaddr = buf_addr + i * page_size
            offset = (vaddr // page_size) * 8
            f.seek(offset)
            entry = struct.unpack('Q', f.read(8))[0]
            # bit 63: page present
            if not (entry & (1 << 63)):
                raise RuntimeError(
                    f'Page at vaddr {vaddr:#x} not present in pagemap')
            pfn = entry & ((1 << 55) - 1)
            if pfn == 0:
                raise RuntimeError(
                    f'Page at vaddr {vaddr:#x} has PFN=0 (no permission?)')
            phys_addr = pfn * page_size
            addrs.append(phys_addr)
    return addrs


def alloc_srq_buffer(size):
    """分配页对齐内存，锁定并获取物理地址。

    返回 (buf_addr, alloc_size, phys_addrs)：
        buf_addr: mmap 返回的虚拟地址（int）
        alloc_size: 实际分配大小（页对齐后）
        phys_addrs: 每页物理地址列表
    """
    import ctypes
    import ctypes.util
    import os

    page_size = os.sysconf('SC_PAGE_SIZE')  # 通常 4096
    alloc_size = ((size + page_size - 1) // page_size) * page_size

    libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
    libc.mmap.restype = ctypes.c_void_p
    libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int,
                          ctypes.c_int, ctypes.c_int, ctypes.c_long]
    libc.mlock.restype = ctypes.c_int
    libc.mlock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]

    MAP_PRIVATE = 0x02
    MAP_ANONYMOUS = 0x20
    PROT_READ = 0x1
    PROT_WRITE = 0x2

    addr = libc.mmap(None, alloc_size, PROT_READ | PROT_WRITE,
                     MAP_PRIVATE | MAP_ANONYMOUS, -1, 0)
    if addr is None or addr == ctypes.c_void_p(-1).value:
        raise RuntimeError(f'mmap failed: errno={ctypes.get_errno()}')

    # Touch all pages to ensure physical allocation
    ctypes.memset(addr, 0, alloc_size)

    # Pin memory pages
    ret = libc.mlock(ctypes.c_void_p(addr), alloc_size)
    if ret != 0:
        raise RuntimeError(f'mlock failed: errno={ctypes.get_errno()}')

    # Get physical addresses from pagemap
    phys_addrs = get_physical_addresses(addr, alloc_size, page_size)
    return addr, alloc_size, phys_addrs


def create_devx_pd(ctx):
    """通过 DevX ALLOC_PD 创建一个 PD，返回 [pd_obj, pd_num]。"""
    import pyverbs.providers.mlx5.mlx5dv as m
    cmd_in = bytes(AllocPdIn())
    pd_obj = m.Mlx5DevxObj(ctx, cmd_in, len(AllocPdOut()))
    pd_out = AllocPdOut(pd_obj.out_view)
    return [pd_obj, pd_out.pd]


def create_devx_cq(ctx, eqn, uar, cq_umem, cq_dbr_umem, ncqes=256):
    """通过 DevX CREATE_CQ 创建一个 CQ，返回 (cq_obj, cqn)。"""
    import pyverbs.providers.mlx5.mlx5dv as m
    log_cq_size = math.ceil(math.log2(ncqes))
    sw_cqc = SwCqc(
        st=0,  # ICCQ
        c_eqn=eqn,
        uar_page=uar.page_id,
        log_cq_size=log_cq_size,
        dbr_umem_valid=1,
        dbr_umem_id=cq_dbr_umem.umem_id,
    )
    cmd_in = bytes(CreateCqIn(
        sw_cqc=sw_cqc,
        cq_umem_id=cq_umem.umem_id,
        cq_umem_valid=1,
    ))
    cq_obj = m.Mlx5DevxObj(ctx, cmd_in, len(CreateCqOut()))
    cq_out = CreateCqOut(cq_obj.out_view)
    return [cq_obj, cq_out.cqn]


def modify_devx_cq(cq_obj, field_select, cq_period=None, cq_max_count=None,
                   op_mod=0, cq_umem=None, log_cq_size=None, cqn=None):
    """通过 DevX MODIFY_CQ 修改已创建 CQ 的属性。

    参数：
        cq_obj: Mlx5DevxObj，CREATE_CQ 返回的对象。
        field_select: 32 位字段选择掩码。
        cq_period / cq_max_count: moderation 参数（op_mod=0 时有效）。
        op_mod: 0=modify，1=resize。
        cq_umem: resize 时如需指定新 UMEM 可传入。
        log_cq_size: resize 时的新 log2(size)。
        cqn: 默认从 cq_obj.out_view 解析；异常测试可传入错误值覆盖。

    返回：
        (status, syndrome_or_err)，status=0 表示成功，status=-1 表示 Python 层异常。
    """
    try:
        if cqn is None:
            cqn = CreateCqOut(cq_obj.out_view).cqn
        sw_cqc = SwCqc()
        if cq_period is not None:
            sw_cqc.cq_period = cq_period
        if cq_max_count is not None:
            sw_cqc.cq_max_count = cq_max_count
        if log_cq_size is not None:
            sw_cqc.log_cq_size = log_cq_size

        cmd_in = ModifyCqIn(
            cqn=cqn,
            op_mod=op_mod,
            field_select=field_select,
            sw_cqc=sw_cqc,
        )
        if cq_umem is not None:
            cmd_in.cq_umem_id = cq_umem.umem_id
            cmd_in.cq_umem_valid = 1

        out_bytes = cq_obj.modify(bytes(cmd_in), len(ModifyCqOut()))
        out = ModifyCqOut(out_bytes)
        return out.status, out.syndrome
    except Exception as exc:
        return -1, str(exc)


def resize_devx_cq(ctx, cq_obj, new_ncqes):
    """通过 DevX MODIFY_CQ (op_mod=1) 调整 CQ 大小。

    参数：
        ctx: Mlx5Context。
        cq_obj: CREATE_CQ 返回的 Mlx5DevxObj。
        new_ncqes: 新的 CQ entry 数量（会向上取整到 2 的幂）。

    返回：
        (status, syndrome_or_err, new_cq_umem)。
        status=0 表示成功；失败时 new_cq_umem 为 None。
    """
    import pyverbs.providers.mlx5.mlx5dv as m
    try:
        cqn = CreateCqOut(cq_obj.out_view).cqn
        new_log_cq_size = math.ceil(math.log2(new_ncqes))
        cq_umem_size = (1 << new_log_cq_size) * 64  # mlx5 CQE 64 bytes
        new_cq_umem = m.Mlx5UMEM(ctx, size=cq_umem_size)

        sw_cqc = SwCqc(log_cq_size=new_log_cq_size)
        cmd_in = ModifyCqIn(
            cqn=cqn,
            op_mod=1,
            field_select=0x4,  # log_cq_size
            sw_cqc=sw_cqc,
            cq_umem_id=new_cq_umem.umem_id,
            cq_umem_valid=1,
        )
        out_bytes = cq_obj.modify(bytes(cmd_in), len(ModifyCqOut()))
        out = ModifyCqOut(out_bytes)
        if out.status != 0:
            return out.status, out.syndrome, None
        return out.status, out.syndrome, new_cq_umem
    except Exception as exc:
        return -1, str(exc), None


def modify_cq_general(ctx, cqn, field_select, cq_period=None, cq_max_count=None,
                      op_mod=0):
    """在指定 context 上直接下发 MODIFY_CQ（不依赖已有 cq_obj），返回 (status, syndrome_or_err)。"""
    import pyverbs.providers.mlx5.mlx5dv as m
    try:
        sw_cqc = SwCqc()
        if cq_period is not None:
            sw_cqc.cq_period = cq_period
        if cq_max_count is not None:
            sw_cqc.cq_max_count = cq_max_count
        cmd_in = ModifyCqIn(
            cqn=cqn,
            op_mod=op_mod,
            field_select=field_select,
            sw_cqc=sw_cqc,
        )
        out_bytes = m.Mlx5DevxObj(ctx, bytes(cmd_in), len(ModifyCqOut()))
        out = ModifyCqOut(out_bytes)
        return out.status, out.syndrome
    except Exception as exc:
        return -1, str(exc)


def probe_modify_cq_resize_support(ctx, eqn, uar):
    """探测当前环境是否支持 DevX MODIFY_CQ resize（op_mod=1）。

    创建一个临时 CQ 并尝试 resize 到 512 entries，成功返回 True；
    任何异常或固件返回失败均返回 False。探测过程会自动清理资源。
    """
    import pyverbs.providers.mlx5.mlx5dv as m
    cq_obj = None
    cq_umem = None
    cq_dbr = None
    try:
        cq_umem = m.Mlx5UMEM(ctx, size=16384)
        cq_dbr = m.Mlx5UMEM(ctx, size=8, alignment=8)
        cq_obj, cqn = create_devx_cq(ctx, eqn, uar, cq_umem, cq_dbr, ncqes=256)
        status, syndrome, _ = resize_devx_cq(ctx, cq_obj, 512)
        return status == 0
    except Exception:
        return False
    finally:
        for obj in (cq_obj, cq_umem, cq_dbr):
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass


def create_devx_qp(ctx, pd_num, uar, cq_obj, wq_umem, dbr_umem,
                   num_msgs=16, max_recv_sge=1):
    """通过 DevX CREATE_QP 创建一个 RC QP，返回 (qp_obj, qpn)。"""
    import pyverbs.providers.mlx5.mlx5dv as m

    cqn = CreateCqOut(cq_obj.out_view).cqn

    # RQ/SQ size calculation (simplified from rdma-core tests)
    wqe_size = 16 * max_recv_sge
    rq_wqe_size = roundup_pow_of_two(wqe_size)
    rq_wq_size = roundup_pow_of_two(rq_wqe_size * num_msgs)
    if rq_wq_size < 64:
        rq_wq_size = 64
    rq_wqe_num = rq_wq_size // rq_wqe_size
    rq_wqe_shift = int(math.log2(rq_wqe_size - 1)) + 1
    log_rq_stride = rq_wqe_shift - 4

    sq_offset = rq_wq_size
    sq_wqe_size = 192 + 16  # rough max overhead + data seg
    sq_wqe_size = (sq_wqe_size + 63) & ~63  # align to 64
    sq_wq_size = roundup_pow_of_two(sq_wqe_size * num_msgs)
    sq_wqe_num = sq_wq_size // 64

    log_rq_size = int(math.log2(rq_wqe_num - 1)) + 1
    log_sq_size = int(math.log2(sq_wqe_num - 1)) + 1

    qpc = SwQpc(
        st=DevxOps.MLX5_QPC_ST_RC,
        pd=pd_num,
        pm_state=DevxOps.MLX5_QPC_PM_STATE_MIGRATED,
        log_rq_size=log_rq_size,
        log_sq_size=log_sq_size,
        ts_format=0x1,
        log_rq_stride=log_rq_stride,
        uar_page=uar.page_id,
        cqn_snd=cqn,
        cqn_rcv=cqn,
        dbr_umem_id=dbr_umem.umem_id,
        dbr_umem_valid=1,
    )
    cmd_in = bytes(CreateQpIn(sw_qpc=qpc, wq_umem_id=wq_umem.umem_id,
                              wq_umem_valid=1))
    qp_obj = m.Mlx5DevxObj(ctx, cmd_in, len(CreateQpOut()))
    qp_out = CreateQpOut(qp_obj.out_view)
    return [qp_obj, qp_out.qpn]


class QueryQpIn(PRMPacket):
    """mlx5_ifc_query_qp_in_bits — QUERY_QP 输入（16 字节，无 uid 字段）。

    Layout:
        opcode[0x10] | reserved[0x10] | reserved[0x10] | op_mod[0x10]
        qpc_ext[0x1] | reserved[0x7] | qpn[0x18] | reserved[0x20]
    """
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_QUERY_QP),
        ShortField('reserved1', 0),
        ShortField('reserved2', 0),
        ShortField('op_mod', 0),
        BitField('qpc_ext', 0, 1),
        BitField('reserved3', 0, 7),
        BitField('qpn', 0, 24),
        IntField('reserved4', 0),
    ]


class QueryQpOut(PRMPacket):
    """mlx5_ifc_query_qp_out_bits 头部（到 qpc 起点共 24 字节）。

    后续 qpc(232B)/reserved(16B)/pas 由 extract_padding 吸收，
    关键 qpc 字段通过 parse_query_qp_out(raw) 直接按字节偏移解析。
    """
    fields_desc = [
        ByteField('status', 0),
        BitField('reserved1', 0, 24),
        IntField('syndrome', 0),
        StrFixedLenField('reserved2', None, length=8),
        IntField('opt_param_mask', 0),
        IntField('ece', 0),
    ]


def parse_query_qp_out(raw):
    """从 QUERY_QP 输出中提取关键字段，返回 dict。

    输出布局（mlx5_ifc_query_qp_out_bits）：
        status[8b] | reserved[24b] | syndrome[32b] | reserved[64b]
        opt_param_mask[32b] | ece[32b] | qpc(mlx5_ifc_qpc_bits, 232B)
        | reserved[128b] | pas...
    qpc 内关键字段位偏移：state@bit0、st@bit8、pd@bit40、remote_qpn@bit168。
    """
    fields = {
        'status': raw[0],
        'syndrome': int.from_bytes(raw[4:8], 'big'),
        'opt_param_mask': int.from_bytes(raw[16:20], 'big'),
        'ece': int.from_bytes(raw[20:24], 'big'),
        'state': (raw[24] >> 4) & 0xF,
        'st': raw[25],
        'pd': int.from_bytes(raw[29:32], 'big') & 0xFFFFFF,
        'remote_qpn': int.from_bytes(raw[45:48], 'big') & 0xFFFFFF,
    }
    return fields


def query_devx_qp(qp_obj, qpn=None, op_mod=0, qpc_ext=0, out_len=4096):
    """通过 DevX OBJ_QUERY 通道（qp_obj.query()）查询 QP，返回 (status, syndrome, fields_dict)。

    说明：pyverbs 的 Mlx5DevxObj 构造（__init__）只走内核 CREATE 通道
    （MLX5_IB_METHOD_DEVX_OBJ_CREATE，devx_is_obj_create_cmd 白名单），
    QUERY_QP(0x50b) 必须用 qp_obj.query() 对应的 OBJ_QUERY 通道
    （MLX5_IB_METHOD_DEVX_OBJ_QUERY）。内核 devx_is_valid_obj_id 要求
    cmd_in.qpn 与创建对象 qpn 一致，qpn=0 或不匹配直接内核 EINVAL、
    到不了固件。qpn 缺省时从 qp_obj.out_view 用 CreateQpOut() 解析。
    对象已销毁（close 后 obj=NULL）时确定性返回失败，避免 pyverbs
    query() 对 NULL 解引用导致段错误崩溃。

    成功：status==0 且 fields_dict 含 qpc 关键字段；
    失败：status!=0 时 fields_dict 为 None；
    异常：返回 (-1, 异常描述, None)。
    """
    try:
        if qp_obj is None or not qp_obj.obj:
            return -1, 'DevX 对象已销毁（handle=NULL），无法执行 QUERY', None
        if qpn is None:
            qpn = CreateQpOut(qp_obj.out_view).qpn
        cmd_in = QueryQpIn(qpn=qpn, op_mod=op_mod, qpc_ext=qpc_ext)
        raw = qp_obj.query(bytes(cmd_in), out_len)
        out = QueryQpOut(raw)
        if out.status != 0:
            return out.status, out.syndrome, None
        return 0, 0, parse_query_qp_out(raw)
    except Exception as exc:
        return -1, str(exc), None


def stress_query_devx_qp(qp_obj, count, qpn=None, op_mod=0, qpc_ext=0):
    """连续 count 次查询同一 QP，返回 (status_list, fields_consistent)。

    循环放在 helper 函数内部（普通函数帧），避免通过 ipvbs 远程 eval
    字符串中的列表推导式出现 NameError: name 'self' is not defined
    （eval 的 <string> 作用域看不到 response() 方法的局部变量）。

    返回：
        status_list: [(q_status, q_syndrome), ...]，共 count 项
        fields_consistent: 全部成功且每次解析出的 qpc 字段完全一致为 True；
                          无成功样本时为 False
    """
    status_list, fields_list = [], []
    for _ in range(count):
        q_status, q_syndrome, q_fields = query_devx_qp(
            qp_obj, qpn=qpn, op_mod=op_mod, qpc_ext=qpc_ext)
        status_list.append((q_status, q_syndrome))
        fields_list.append(q_fields)
    consistent = len(fields_list) > 0 and all(
        f == fields_list[0] for f in fields_list)
    return status_list, consistent


class QueryCqIn(PRMPacket):
    """mlx5_ifc_query_cq_in_bits — QUERY_CQ 输入（16 字节，无 uid 字段）。

    Layout: opcode[0x10] | reserved[0x10] | reserved[0x10] | op_mod[0x10]
            reserved[0x8] | cqn[0x18] | reserved[0x20]
    """
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_QUERY_CQ),
        ShortField('reserved1', 0),
        ShortField('reserved2', 0),
        ShortField('op_mod', 0),
        BitField('reserved3', 0, 8),
        BitField('cqn', 0, 24),
        IntField('reserved4', 0),
    ]


class QueryCqOut(PRMPacket):
    """mlx5_ifc_query_cq_out_bits 头部（16 字节）。

    后续 cq_context(64B)/reserved(192B)/pas 由 extract_padding 吸收，
    关键字段通过 parse_query_cq_out(raw) 直接按字节偏移解析。
    """
    fields_desc = [
        ByteField('status', 0),
        BitField('reserved1', 0, 24),
        IntField('syndrome', 0),
        StrFixedLenField('reserved2', None, length=8),
    ]


def parse_query_cq_out(raw):
    """从 QUERY_CQ 输出中提取关键字段，返回 dict。

    输出布局：status[8b] | reserved[24b] | syndrome[32b] | reserved[64b]
              cq_context(mlx5_ifc_cqc_bits, 64B, 从偏移 0x10 起) | ...

    相对 raw 的绝对偏移（cq_context 起点 0x10=16）：
        cqe_sz     = (raw[0x11] >> 5) & 0x7
        st         = (raw[0x12] >> 4) & 0xF
        page_offset= (raw[0x18:0x1b] >> 6) & 0x3F
        log_cq_size= raw[0x1c] & 0x1F
        uar_page   = raw[0x1d:0x20] & 0xFFFFFF
        cq_period  = raw[0x20:0x22] & 0xFFF
        cq_max_count = raw[0x22:0x24]
        eqn        = raw[0x24:0x28]
        log_page_size = raw[0x28] & 0x1F
        consumer_counter = raw[0x39:0x3c] & 0xFFFFFF
        producer_counter = raw[0x3d:0x40] & 0xFFFFFF
    """
    fields = {
        'status': raw[0],
        'syndrome': int.from_bytes(raw[4:8], 'big'),
        'cqe_sz': (raw[0x11] >> 5) & 0x7,
        'st': (raw[0x12] >> 4) & 0xF,
        'page_offset': (int.from_bytes(raw[0x18:0x1b], 'big') >> 6) & 0x3F,
        'log_cq_size': raw[0x1c] & 0x1F,
        'uar_page': int.from_bytes(raw[0x1d:0x20], 'big') & 0xFFFFFF,
        'cq_period': int.from_bytes(raw[0x20:0x22], 'big') & 0xFFF,
        'cq_max_count': int.from_bytes(raw[0x22:0x24], 'big'),
        'eqn': int.from_bytes(raw[0x24:0x28], 'big'),
        'log_page_size': raw[0x28] & 0x1F,
        'consumer_counter': int.from_bytes(raw[0x39:0x3c], 'big') & 0xFFFFFF,
        'producer_counter': int.from_bytes(raw[0x3d:0x40], 'big') & 0xFFFFFF,
    }
    return fields


def query_devx_cq(cq_obj, cqn=None, op_mod=0, out_len=4096):
    """通过 DevX OBJ_QUERY 通道（cq_obj.query()）查询 CQ。

    返回 (cq_status, cq_syndrome, fields_dict)：
        cq_status == 0  成功，fields_dict 为解析出的 cqc 关键字段
        cq_status == -1 确定性失败（对象已销毁或远程异常），
                        cq_syndrome 为失败原因描述

    注意：
        1. QUERY_CQ(0x402) 必须走 cq_obj.query() 的 OBJ_QUERY 通道，
           内核 devx_is_valid_obj_id 要求 cmd_in.cqn 与创建对象 cqn
           一致，否则内核 EINVAL 到不了固件；
        2. 对象已销毁（close 后 obj=NULL）时确定性返回失败，
           避免 pyverbs query() 段错误。
    """
    try:
        if cq_obj is None or not cq_obj.obj:
            return -1, 'DevX 对象已销毁（handle=NULL），无法执行 QUERY', None
        if cqn is None:
            cqn = CreateCqOut(cq_obj.out_view).cqn
        cmd_in = QueryCqIn(cqn=cqn, op_mod=op_mod)
        raw = cq_obj.query(bytes(cmd_in), out_len)
        out = QueryCqOut(raw)
        if out.status != 0:
            return out.status, out.syndrome, None
        return 0, 0, parse_query_cq_out(raw)
    except Exception as exc:
        return -1, str(exc), None


def stress_query_devx_cq(cq_obj, count, cqn=None, op_mod=0):
    """连续 count 次查询同一 CQ，返回 (status_list, fields_consistent)。

    循环必须收进 helper（普通函数帧），避免 ipvbs 远程 eval 字符串
    中列表推导式出现 NameError: name 'self' is not defined。
    """
    status_list, fields_list = [], []
    for _ in range(count):
        cq_status, cq_syndrome, cq_fields = query_devx_cq(
            cq_obj, cqn=cqn, op_mod=op_mod)
        status_list.append((cq_status, cq_syndrome))
        fields_list.append(cq_fields)
    consistent = len(fields_list) > 0 and all(
        f == fields_list[0] for f in fields_list)
    return status_list, consistent


class QuerySrqIn(PRMPacket):
    """mlx5_ifc_query_srq_in_bits — QUERY_SRQ 输入（16 字节，无 uid 字段）。

    Layout: opcode[0x10] | reserved[0x10] | reserved[0x10] | op_mod[0x10]
            reserved[0x8] | srqn[0x18] | reserved[0x20]
    """
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_QUERY_SRQ),
        ShortField('reserved1', 0),
        ShortField('reserved2', 0),
        ShortField('op_mod', 0),
        BitField('reserved3', 0, 8),
        BitField('srqn', 0, 24),
        IntField('reserved4', 0),
    ]


class QuerySrqOut(PRMPacket):
    """mlx5_ifc_query_srq_out_bits 头部（16 字节）。

    后续 srq_context(64B)/reserved(192B)/pas 由 extract_padding 吸收，
    关键字段通过 parse_query_srq_out(raw) 直接按字节偏移解析。
    """
    fields_desc = [
        ByteField('status', 0),
        BitField('reserved1', 0, 24),
        IntField('syndrome', 0),
        StrFixedLenField('reserved2', None, length=8),
    ]


def parse_query_srq_out(raw):
    """从 QUERY_SRQ 输出中提取关键字段，返回 dict。

    输出布局：status[8b] | reserved[24b] | syndrome[32b] | reserved[64b]
              srq_context(mlx5_ifc_srqc_bits, 64B, 从偏移 0x10 起) | ...

    相对 raw 的绝对偏移（srq_context 起点 0x10=16，对应 SwSrqc 布局）：
        state        = word0 高 4bit，raw[0x10] >> 4
        log_srq_size = word0 低 4bit，raw[0x10] & 0xF
        log_rq_stride= word1 3bit，raw[0x14] & 0x7
        xrcd         = word1 低 24bit，raw[0x15:0x18]
        page_offset  = word2 高 6bit，(raw[0x18] >> 2) & 0x3F
        cqn          = word2 低 24bit，raw[0x19:0x1c]
        log_page_size= word4 6bit，raw[0x20] & 0x3F
        pd           = word6 低 24bit，raw[0x29:0x2c]
        lwm          = word7 高 16bit，raw[0x2c:0x2e]
        wqe_cnt      = word7 低 16bit，raw[0x2e:0x30]
        dbr_addr     = word10-11，raw[0x38:0x40]
    """
    fields = {
        'status': raw[0],
        'syndrome': int.from_bytes(raw[4:8], 'big'),
        'state': (raw[0x10] >> 4) & 0xF,
        'log_srq_size': raw[0x10] & 0xF,
        'log_rq_stride': raw[0x14] & 0x7,
        'xrcd': int.from_bytes(raw[0x15:0x18], 'big') & 0xFFFFFF,
        'page_offset': (int.from_bytes(raw[0x18:0x1b], 'big') >> 2) & 0x3F,
        'cqn': int.from_bytes(raw[0x19:0x1c], 'big') & 0xFFFFFF,
        'log_page_size': raw[0x20] & 0x3F,
        'pd': int.from_bytes(raw[0x29:0x2c], 'big') & 0xFFFFFF,
        'lwm': int.from_bytes(raw[0x2c:0x2e], 'big'),
        'wqe_cnt': int.from_bytes(raw[0x2e:0x30], 'big'),
        'dbr_addr': int.from_bytes(raw[0x38:0x40], 'big'),
    }
    return fields


def query_devx_srq(srq_obj, srqn=None, op_mod=0, out_len=4096):
    """通过 DevX OBJ_QUERY 通道（srq_obj.query()）查询 SRQ。

    返回 (srq_status, srq_syndrome, fields_dict)：
        srq_status == 0  成功，fields_dict 为解析出的 srqc 关键字段
        srq_status == -1 确定性失败（对象已销毁、非 DevX 对象或远程异常），
                         srq_syndrome 为失败原因描述

    注意：
        1. QUERY_SRQ(0x702) 必须走 srq_obj.query() 的 OBJ_QUERY 通道，
           内核 devx_is_valid_obj_id 要求 cmd_in.srqn 与创建对象 srqn
           一致，否则内核 EINVAL 到不了固件；
        2. create_devx_srq 在固件拒绝 DevX CREATE_SRQ 时会回退标准 verbs
           SRQ（无 .obj/.query 属性），此处确定性返回失败；
        3. 对象已销毁（close 后 obj=NULL）时确定性返回失败，
           避免 pyverbs query() 段错误。
    """
    try:
        if srq_obj is None or not hasattr(srq_obj, 'obj') or not srq_obj.obj:
            return -1, 'DevX 对象已销毁或非 DevX 对象（handle=NULL），无法执行 QUERY', None
        if not hasattr(srq_obj, 'query'):
            return -1, '对象不支持 query()（verbs SRQ 回退路径），无法执行 QUERY', None
        if srqn is None:
            srqn = CreateSrqOut(srq_obj.out_view).srqn
        cmd_in = QuerySrqIn(srqn=srqn, op_mod=op_mod)
        raw = srq_obj.query(bytes(cmd_in), out_len)
        out = QuerySrqOut(raw)
        if out.status != 0:
            return out.status, out.syndrome, None
        return 0, 0, parse_query_srq_out(raw)
    except Exception as exc:
        return -1, str(exc), None


def stress_query_devx_srq(srq_obj, count, srqn=None, op_mod=0):
    """连续 count 次查询同一 SRQ，返回 (status_list, fields_consistent)。

    循环必须收进 helper（普通函数帧），避免 ipvbs 远程 eval 字符串
    中列表推导式出现 NameError: name 'self' is not defined。
    """
    status_list, fields_list = [], []
    for _ in range(count):
        srq_status, srq_syndrome, srq_fields = query_devx_srq(
            srq_obj, srqn=srqn, op_mod=op_mod)
        status_list.append((srq_status, srq_syndrome))
        fields_list.append(srq_fields)
    consistent = len(fields_list) > 0 and all(
        f == fields_list[0] for f in fields_list)
    return status_list, consistent


def create_devx_srq(ctx, pd_num, phys_addrs, num_wqes=64, page_size=4096):
    """创建一个 SRQ，返回 [srq_obj, srqn]。

    优先尝试 DevX CREATE_SRQ（PAS 模式）；若固件拒绝（部分平台 issi
    使能后 DevX uid 下 CREATE_SRQ/CREATE_RMP 不可用，返回 errno 121），
    自动回退到标准 verbs SRQ 路径（pyverbs SRQ + get_srq_num）。
    两种路径返回的对象都支持 close()。

    DevX 路径说明：
    CREATE_SRQ 不支持 umem_id，必须通过 PAS 提供物理地址。
    phys_addrs: 物理地址列表（每个对应一个 page_size 大小的页）。
    """
    import pyverbs.providers.mlx5.mlx5dv as m
    log_srq_size = math.ceil(math.log2(max(num_wqes, 1)))
    # log_page_size = page_shift - MLX5_ADAPTER_PAGE_SHIFT(12)
    log_page_size = int(math.log2(page_size)) - 12
    log_rq_stride = 0  # 16-byte WQE stride (minimal SRQ, wqe_shift=4-4=0)
    page_offset = 0

    # Calculate required PAS count (same formula as kernel get_pas_size)
    # rq_sz = 1 << (log_srq_size + 4 + log_rq_stride)
    # num_pas = DIV_ROUND_UP(rq_sz + page_offset * quanta, page_size)
    rq_sz = 1 << (log_srq_size + 4 + log_rq_stride)
    po_quanta = 1 << (log_page_size + 12 - 6)
    rq_sz_po = rq_sz + page_offset * po_quanta
    num_pas = (rq_sz_po + page_size - 1) // page_size
    if num_pas < 1:
        num_pas = 1

    # Only use the required number of PAS entries
    use_phys_addrs = phys_addrs[:num_pas]

    # dbr_addr: doorbell record 物理地址
    # 内核总是设置此字段(srq->db.dma)，固件需要写入 SRQ 计数器
    # 使用 buffer 第一页中 WQE 区域之后的位置作为 doorbell
    dbr_addr = phys_addrs[0] + rq_sz  # WQE 区域之后

    srqc = SwSrqc(
        log_srq_size=log_srq_size,
        log_rq_stride=log_rq_stride,
        log_page_size=log_page_size,
        page_offset=page_offset,
        pd=pd_num,
        lwm=0,
        dbr_addr=dbr_addr,
    )

    # Build PAS entries from physical addresses
    # PAS is raw 64-bit physical address in big-endian (kernel: cpu_to_be64)
    # SwPas layout: pa_h(32) + pa_l(20) + reserved(12) = 64 bits
    pas_list = []
    for phys_addr in use_phys_addrs:
        pas_list.append(SwPas(
            pa_h=(phys_addr >> 32) & 0xFFFFFFFF,
            pa_l=(phys_addr >> 12) & 0xFFFFF,
            reserved1=phys_addr & 0xFFF,
        ))

    cmd_in_pkt = CreateSrqIn(
        sw_srqc=srqc,
        pas=pas_list,
    )
    cmd_in = bytes(cmd_in_pkt)
    out_len = len(CreateSrqOut())  # 16 bytes
    # DEBUG: store info for retrieval via ipvbs
    global _last_srq_debug
    _last_srq_debug = (f'pas_count={len(pas_list)},pd={pd_num},'
                       f'log_srq_size={log_srq_size},'
                       f'log_page_size={log_page_size},'
                       f'log_rq_stride={log_rq_stride},'
                       f'rq_sz={rq_sz},num_pas={num_pas},'
                       f'dbr_addr={hex(dbr_addr)},'
                       f'cmd_in_len={len(cmd_in)},out_len={out_len},'
                       f'phys_addrs={[hex(a) for a in use_phys_addrs]}')
    try:
        srq_obj = m.Mlx5DevxObj(ctx, cmd_in, out_len)
        # 从 obj_id 获取 SRQN（DevX 对象内部 ID = 固件分配的 SRQN）
        try:
            srqn = srq_obj.obj_id
        except AttributeError:
            # fallback: 从 output buffer byte 8-11 解析（srqn field）
            srqn = struct.unpack('>I', srq_obj.out_view[8:12])[0] & 0xFFFFFF
        return [srq_obj, srqn]
    except Exception as devx_err:
        # DevX CREATE_SRQ 被固件拒绝（如 issi 使能平台对 DevX uid 返回
        # BAD_OP_ERR/errno 121）。回退标准 verbs SRQ 路径。
        _last_srq_debug += f' | devx_fail={devx_err}, verbs_fallback'
        return _create_verbs_srq(ctx, num_wqes)


def create_verbs_srq_with_pd(ctx, num_wqes=64):
    """标准 verbs 路径创建 SRQ，返回 [srq_obj, srqn, verbs_pd]。"""
    from pyverbs.pd import PD
    from pyverbs.srq import SRQ, SrqInitAttr, SrqAttr
    global _verbs_srq_pd_refs
    try:
        _verbs_srq_pd_refs
    except NameError:
        _verbs_srq_pd_refs = []
    # verbs SRQ 需要 verbs PD（独立于 DevX PD）；
    # SRQ 内部会对 PD 增加引用，同时用模块级列表保持引用防止提前回收。
    verbs_pd = PD(ctx)
    init_attr = SrqInitAttr(SrqAttr(max_wr=max(num_wqes, 1), max_sge=1))
    srq_obj = SRQ(verbs_pd, init_attr)
    _verbs_srq_pd_refs.append(verbs_pd)
    srqn = srq_obj.get_srq_num()
    return [srq_obj, srqn, verbs_pd]


def _create_verbs_srq(ctx, num_wqes=64):
    """兼容封装：标准 verbs 路径创建 SRQ，返回 [srq_obj, srqn]。"""
    return create_verbs_srq_with_pd(ctx, num_wqes)[:2]


# ---------------------------------------------------------------------- #
#  mlx5dv_devx_srq_query（libmlx5 C DV 接口）相关封装
#
#  背景：内核 devx 通道（Mlx5DevxObj / srq_obj.query()）对 QUERY_SRQ
#  固定要求对象按 CREATE_SRQ 编码；RMP 平台下 verbs SRQ 底层按
#  CREATE_RMP(0x90c) 编码，obj_id 校验不匹配返回 EINVAL(22)，命令不到
#  固件。libmlx5 的 mlx5dv_devx_srq_query 走 devx_ucmd 用户命令通道，
#  通过 ctypes 直接调用该 C 符号以覆盖该场景。
# ---------------------------------------------------------------------- #

def _load_mlx5dv_srq_query_fn():
    """惰性加载 libmlx5 的 mlx5dv_devx_srq_query 符号。

    返回 (fn, None)；加载失败返回 (None, err_msg)。
    """
    import ctypes
    import ctypes.util
    global _srq_query_lib
    try:
        _srq_query_lib
    except NameError:
        _srq_query_lib = None
    if _srq_query_lib is not None:
        return _srq_query_lib, None
    candidates = []
    try:
        found = ctypes.util.find_library('mlx5')
        if found:
            candidates.append(found)
    except Exception:
        pass
    candidates += ['libmlx5.so.1', 'libmlx5.so']
    last_err = None
    for name in candidates:
        try:
            lib = ctypes.CDLL(name, mode=ctypes.RTLD_GLOBAL)
            fn = lib.mlx5dv_devx_srq_query
            fn.restype = ctypes.c_int
            fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                           ctypes.c_void_p, ctypes.c_size_t]
            _srq_query_lib = fn
            return _srq_query_lib, None
        except Exception as load_err:
            last_err = load_err
    return None, f'加载 mlx5dv_devx_srq_query 失败: {last_err}'


def query_srq_via_libmlx5(srq_obj, srqn=None, op_mod=0, in_len=16,
                          out_len=4096, raw_in=None):
    """通过 libmlx5 C 接口 mlx5dv_devx_srq_query 查询 verbs SRQ。

    返回 (call_ret, fw_status, syndrome, detail)：
      - call_ret == 0：下发成功，fw_status 为固件 status，
        detail 为解析后的字段 dict（实际 out 长度 >=0x40 时）；
      - call_ret != 0：C 层返回 errno，命令被拒/未达固件，detail 为 None；
      - call_ret is None：被守卫拦截或函数加载失败，detail 为原因字符串。

    安全说明：out_storage 底层固定分配 >=4096 字节（out_len 仅作为
    outlen 参数透传），即使 libmlx5 未按 outlen 截断写入也不会越界。
    """
    import ctypes
    fn, load_err = _load_mlx5dv_srq_query_fn()
    if fn is None:
        return None, None, None, f'加载失败: {load_err}'
    # ---- 守卫：避免空指针 / 已销毁对象下发，防止段错误 ----
    if srq_obj is None:
        return None, None, None, '守卫: srq_obj 为 None（NULL 指针不下发）'
    if not hasattr(srq_obj, 'srq'):
        return None, None, None, '守卫: 对象非 pyverbs verbs SRQ（无 .srq 属性）'
    srq_ptr = getattr(srq_obj, 'srq', None)
    if srq_ptr is None:
        return None, None, None, '守卫: 已销毁（底层指针为空）'
    try:
        srq_ptr_val = int(srq_ptr)
    except Exception:
        srq_ptr_val = 0
    if not srq_ptr_val:
        return None, None, None, '守卫: 已销毁（底层指针为 0）'
    global _closed_verbs_srq_ids
    try:
        _closed_verbs_srq_ids
    except NameError:
        _closed_verbs_srq_ids = set()
    if srq_ptr_val in _closed_verbs_srq_ids:
        return None, None, None, '守卫: 已销毁（close 后查询）'
    if srqn is None:
        try:
            srqn = srq_obj.get_srq_num()
        except Exception as num_err:
            return None, None, None, f'守卫: 获取 srqn 失败: {num_err}'
    # ---- 构造 QUERY_SRQ inbox（opcode=0x702, srqn@byte9-11）----
    if raw_in is not None:
        cmd_in = bytes(raw_in)
    else:
        cmd_in = (struct.pack('>HHHH', 0x702, 0, 0, int(op_mod) & 0xFFFF) +
                  struct.pack('>I', int(srqn) & 0xFFFFFF) + b'\x00' * 4)
    cmd_storage = ctypes.create_string_buffer(cmd_in, len(cmd_in))
    out_storage = ctypes.create_string_buffer(max(int(out_len), 4096))
    try:
        ret = fn(ctypes.c_void_p(srq_ptr_val),
                 ctypes.cast(cmd_storage, ctypes.c_void_p), int(in_len),
                 ctypes.cast(out_storage, ctypes.c_void_p), int(out_len))
    except Exception as call_err:
        return None, None, None, '异常: 调用 mlx5dv_devx_srq_query 失败: ' + \
                                 str(call_err)
    raw = out_storage.raw
    if ret == 0:
        fw_status = raw[0] if len(raw) >= 1 else None
        syndrome = int.from_bytes(raw[4:8], 'big') if len(raw) >= 8 else None
        if len(raw) >= 0x40:
            try:
                detail = parse_query_srq_out(raw)
            except Exception as parse_err:
                detail = {'parse_error': str(parse_err)}
        else:
            detail = {'out_too_small': True, 'out_len': len(raw)}
        return 0, fw_status, syndrome, detail
    return int(ret), None, None, None


def probe_srq_query_libmlx5(dev='mlx5_0', num_wqes=8):
    """探测 mlx5dv_devx_srq_query 在当前环境是否可用。

    探测流程：verbs 创建 SRQ -> 经 libmlx5 C 接口下发 QUERY_SRQ -> 销毁。
    返回 (supported, evidence)。
    """
    from pyverbs.providers.mlx5.mlx5dv import Mlx5Context, Mlx5DVContextAttr
    ctx = None
    srq_obj = None
    try:
        ctx = Mlx5Context(Mlx5DVContextAttr(), dev)
        srq_obj, srqn, _ = create_verbs_srq_with_pd(ctx, num_wqes)
        ret, fw_status, syndrome, detail = query_srq_via_libmlx5(
            srq_obj, srqn=srqn)
        if ret == 0:
            return True, (f'mlx5dv_devx_srq_query 返回 0，fw_status='
                          f'{fw_status}，syndrome={syndrome}，'
                          f'fields={detail}')
        if ret is None:
            return False, str(detail)
        abs_ret = abs(int(ret))
        if abs_ret == 22:
            return False, ('内核 devx 通道 obj_id 编码不匹配: verbs SRQ'
                           '(底层 RMP 0x90c) vs QUERY_SRQ 要求(0x700)，'
                           '返回 EINVAL(22)，命令未达固件')
        if abs_ret == 121:
            return False, (f'EREMOTEIO: ret={ret}, fw_status={fw_status}, '
                           f'syndrome={syndrome}（命令达固件但被拒）')
        return False, f'ret={ret}, fw_status={fw_status}, syndrome={syndrome}'
    except Exception as exc:
        return False, f'探测异常: {exc}'
    finally:
        if srq_obj is not None:
            try:
                close_verbs_srq_guarded(srq_obj)
            except Exception:
                pass
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass


def stress_query_srq_libmlx5(srq_obj, count=100, srqn=None):
    """连续 count 次经 libmlx5 查询同一 verbs SRQ。

    返回 (status_list, consistent)：
        status_list: [(call_ret, fw_status, syndrome, detail), ...]
        consistent: 所有成功查询的字段 dict 是否一致
    """
    if srqn is None:
        try:
            srqn = srq_obj.get_srq_num()
        except Exception:
            srqn = None
    status_list, fields_list = [], []
    for _ in range(count):
        ret, fw_status, syndrome, detail = query_srq_via_libmlx5(
            srq_obj, srqn=srqn)
        status_list.append((ret, fw_status, syndrome, detail))
        if ret == 0 and isinstance(detail, dict) and \
                'parse_error' not in detail and 'out_too_small' not in detail:
            fields_list.append(detail)
    consistent = len(fields_list) > 0 and all(
        f == fields_list[0] for f in fields_list)
    return status_list, consistent


def create_query_destroy_stress_libmlx5(ctx, rounds=50, num_wqes=8):
    """循环 rounds 轮：创建 verbs SRQ -> libmlx5 查询 -> 销毁。

    返回 (ok_count, fail_list)；fail_list 元素 (round, phase, detail)。
    """
    ok_count, fail_list = 0, []
    for rnd in range(rounds):
        srq_obj = None
        try:
            srq_obj, srqn, _ = create_verbs_srq_with_pd(ctx, num_wqes)
            ret, fw_status, syndrome, detail = query_srq_via_libmlx5(
                srq_obj, srqn=srqn)
            if ret != 0:
                fail_list.append((rnd, 'query',
                                  f'ret={ret}, fw={fw_status}, '
                                  f'synd={syndrome}, detail={detail}'))
                continue
            ok_count += 1
        except Exception as exc:
            fail_list.append((rnd, 'create', str(exc)))
        finally:
            if srq_obj is not None:
                try:
                    close_verbs_srq_guarded(srq_obj)
                except Exception:
                    pass
    return ok_count, fail_list


def close_verbs_srq_guarded(srq_obj):
    """关闭 verbs SRQ 并登记其底层指针，防止 close 后误查询造成 UAF。

    注：登记集合按指针值匹配；指针复用场景下可能保守误判，可接受。
    """
    if srq_obj is None:
        return
    global _closed_verbs_srq_ids
    try:
        _closed_verbs_srq_ids
    except NameError:
        _closed_verbs_srq_ids = set()
    srq_ptr = getattr(srq_obj, 'srq', None)
    if srq_ptr is not None:
        try:
            _closed_verbs_srq_ids.add(int(srq_ptr))
        except Exception:
            pass
    try:
        srq_obj.close()
    except Exception:
        pass


def modify_verbs_srq_limit(srq_obj, srq_limit=4):
    """经 pyverbs verbs 接口修改 SRQ 的 srq_limit（lwm 阈值）。

    返回 (0, None) 或 (-1, err_msg)。
    """
    try:
        srq_obj.modify(srq_limit=srq_limit)
        return 0, None
    except TypeError:
        pass  # 签名兼容尝试：位置参数形式
    except Exception as exc:
        return -1, f'SRQ.modify 失败: {exc}'
    try:
        srq_obj.modify(srq_limit)
        return 0, None
    except Exception as exc:
        return -1, f'SRQ.modify 失败: {exc}'


# ---------------------------------------------------------------------- #
#  mlx5dv_devx_srq_modify（libmlx5 C DV 透传 ARM_RQ）相关封装
#
#  mlx5 固件命令族没有 MODIFY_SRQ 命令：SRQ 的 lwm(水位)修改由
#  ARM_RQ(0x703, op_mod=1) 实现。libmlx5 的 mlx5dv_devx_srq_modify 为
#  纯透传 C 符号，cmd_in 写入的 opcode 即为下发命令；本组封装构造
#  ARM_RQ inbox（16B: opcode=0x703/srqn/lwm）后经 ctypes 调用该符号
#  下发 devx_ucmd 用户命令通道，覆盖"SRQ modify"场景。
#
#  背景：内核 devx 通道对 ARM_RQ 的 obj_id 校验按 RQ 系（CREATE_RQ）
#  编码；RMP 平台下 verbs SRQ 底层按 CREATE_RMP(0x90c) 编码，obj_id
#  校验不匹配返回 EINVAL(22)，命令不到固件。
# ---------------------------------------------------------------------- #

def _load_mlx5dv_srq_modify_fn():
    """惰性加载 libmlx5 的 mlx5dv_devx_srq_modify 符号。

    返回 (fn, None)；加载失败返回 (None, err_msg)。
    """
    import ctypes
    import ctypes.util
    global _srq_modify_lib
    try:
        _srq_modify_lib
    except NameError:
        _srq_modify_lib = None
    if _srq_modify_lib is not None:
        return _srq_modify_lib, None
    candidates = []
    try:
        found = ctypes.util.find_library('mlx5')
        if found:
            candidates.append(found)
    except Exception:
        pass
    candidates += ['libmlx5.so.1', 'libmlx5.so']
    last_err = None
    for name in candidates:
        try:
            lib = ctypes.CDLL(name, mode=ctypes.RTLD_GLOBAL)
            fn = lib.mlx5dv_devx_srq_modify
            fn.restype = ctypes.c_int
            fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                           ctypes.c_void_p, ctypes.c_size_t]
            _srq_modify_lib = fn
            return _srq_modify_lib, None
        except Exception as load_err:
            last_err = load_err
    return None, f'加载 mlx5dv_devx_srq_modify 失败: {last_err}'


def modify_srq_via_libmlx5(srq_obj, srqn=None, op_mod=1, lwm=1, in_len=16,
                           out_len=4096, raw_in=None):
    """通过 libmlx5 C 接口 mlx5dv_devx_srq_modify 下发 ARM_RQ 修改 verbs SRQ。

    mlx5 固件命令族没有 MODIFY_SRQ 命令：SRQ 的 lwm(水位)修改由
    ARM_RQ(0x703, op_mod=1) 实现。libmlx5 的 mlx5dv_devx_srq_modify 为
    纯透传 C 符号，cmd_in 写入的 opcode(0x703) 即为下发命令。

    inbox 布局（16B）：
      byte0-1   opcode = 0x703
      byte2-3   uid = 0
      byte4-5   rsv = 0
      byte6-7   op_mod（SRQ 固定 1）
      byte8-11  srqn（低 24bit 有效）
      byte12-13 rsv = 0
      byte14-15 lwm（新水位阈值）

    返回 (call_ret, fw_status, syndrome, detail)：
      - call_ret == 0：下发成功，fw_status 为固件 status，detail 为回显
        （opcode/op_mod/srqn/lwm_set）dict；
      - call_ret != 0：C 层返回 errno，命令被拒/未达固件，detail 为 None；
      - call_ret is None：被守卫拦截或函数加载失败，detail 为原因字符串。

    安全说明：out_storage 底层固定分配 >=4096 字节（out_len 仅作为
    outlen 参数透传），即使 libmlx5 未按 outlen 截断写入也不会越界。
    """
    import ctypes
    fn, load_err = _load_mlx5dv_srq_modify_fn()
    if fn is None:
        return None, None, None, f'加载失败: {load_err}'
    # ---- 守卫：避免空指针 / 已销毁对象下发，防止段错误 ----
    if srq_obj is None:
        return None, None, None, '守卫: srq_obj 为 None（NULL 指针不下发）'
    if not hasattr(srq_obj, 'srq'):
        return None, None, None, '守卫: 对象非 pyverbs verbs SRQ（无 .srq 属性）'
    srq_ptr = getattr(srq_obj, 'srq', None)
    if srq_ptr is None:
        return None, None, None, '守卫: 已销毁（底层指针为空）'
    try:
        srq_ptr_val = int(srq_ptr)
    except Exception:
        srq_ptr_val = 0
    if not srq_ptr_val:
        return None, None, None, '守卫: 已销毁（底层指针为 0）'
    global _closed_verbs_srq_ids
    try:
        _closed_verbs_srq_ids
    except NameError:
        _closed_verbs_srq_ids = set()
    if srq_ptr_val in _closed_verbs_srq_ids:
        return None, None, None, '守卫: 已销毁（close 后修改）'
    if srqn is None:
        try:
            srqn = srq_obj.get_srq_num()
        except Exception as num_err:
            return None, None, None, f'守卫: 获取 srqn 失败: {num_err}'
    # ---- 构造 ARM_RQ inbox（opcode=0x703, op_mod=1, srqn@byte9-11,
    #      lwm@byte14-15）----
    if raw_in is not None:
        cmd_in = bytes(raw_in)
    else:
        cmd_in = (struct.pack('>HHHH', 0x703, 0, 0, int(op_mod) & 0xFFFF) +
                  struct.pack('>I', int(srqn) & 0xFFFFFF) +
                  struct.pack('>HH', 0, int(lwm) & 0xFFFF))
    cmd_storage = ctypes.create_string_buffer(cmd_in, len(cmd_in))
    out_storage = ctypes.create_string_buffer(max(int(out_len), 4096))
    try:
        ret = fn(ctypes.c_void_p(srq_ptr_val),
                 ctypes.cast(cmd_storage, ctypes.c_void_p), int(in_len),
                 ctypes.cast(out_storage, ctypes.c_void_p), int(out_len))
    except Exception as call_err:
        return None, None, None, '异常: 调用 mlx5dv_devx_srq_modify 失败: ' + \
                                 str(call_err)
    if ret == 0:
        raw = out_storage.raw
        fw_status = raw[0] if len(raw) >= 1 else None
        syndrome = int.from_bytes(raw[4:8], 'big') if len(raw) >= 8 else None
        detail = {'opcode': 'ARM_RQ(0x703)', 'op_mod': int(op_mod),
                  'srqn': int(srqn), 'lwm_set': int(lwm)}
        return 0, fw_status, syndrome, detail
    return int(ret), None, None, None


def probe_modify_srq_libmlx5(dev='mlx5_0', num_wqes=8):
    """探测 mlx5dv_devx_srq_modify(ARM_RQ) 在当前环境是否可用。

    探测流程：verbs 创建 SRQ -> 经 libmlx5 C 接口下发 ARM_RQ -> 销毁。
    返回 (supported, evidence)。
    """
    from pyverbs.providers.mlx5.mlx5dv import Mlx5Context, Mlx5DVContextAttr
    ctx = None
    srq_obj = None
    try:
        ctx = Mlx5Context(Mlx5DVContextAttr(), dev)
        srq_obj, srqn, _ = create_verbs_srq_with_pd(ctx, num_wqes)
        ret, fw_status, syndrome, detail = modify_srq_via_libmlx5(
            srq_obj, srqn=srqn, op_mod=1, lwm=1)
        if ret == 0:
            return True, (f'mlx5dv_devx_srq_modify(ARM_RQ) 返回 0，'
                          f'fw_status={fw_status}，syndrome={syndrome}，'
                          f'detail={detail}')
        if ret is None:
            return False, str(detail)
        abs_ret = abs(int(ret))
        if abs_ret == 22:
            return False, ('内核 devx 通道 obj_id 编码不匹配: verbs SRQ'
                           '(底层 RMP 0x90c) vs ARM_RQ 要求(RQ 系编码)，'
                           '返回 EINVAL(22)，命令未达固件')
        if abs_ret == 121:
            return False, (f'EREMOTEIO: ret={ret}, fw_status={fw_status}, '
                           f'syndrome={syndrome}（命令达固件但被拒）')
        return False, f'ret={ret}, fw_status={fw_status}, syndrome={syndrome}'
    except Exception as exc:
        return False, f'探测异常: {exc}'
    finally:
        if srq_obj is not None:
            try:
                close_verbs_srq_guarded(srq_obj)
            except Exception:
                pass
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass


def stress_modify_srq_libmlx5(srq_obj, count=100, srqn=None):
    """连续 count 次经 libmlx5 下发 ARM_RQ 修改同一 verbs SRQ。

    返回 (status_list, all_ok)：
        status_list: [(call_ret, fw_status, syndrome, detail), ...]
        all_ok: 非空且全部 call_ret == 0
    """
    if srqn is None:
        try:
            srqn = srq_obj.get_srq_num()
        except Exception:
            srqn = None
    status_list = []
    for _ in range(count):
        ret, fw_status, syndrome, detail = modify_srq_via_libmlx5(
            srq_obj, srqn=srqn, op_mod=1, lwm=1)
        status_list.append((ret, fw_status, syndrome, detail))
    all_ok = len(status_list) > 0 and all(
        s[0] == 0 for s in status_list)
    return status_list, all_ok


def create_modify_destroy_stress_libmlx5(ctx, rounds=50, num_wqes=8):
    """循环 rounds 轮：创建 verbs SRQ -> libmlx5 下发 ARM_RQ -> 销毁。

    返回 (ok_count, fail_list)；fail_list 元素 (round, phase, detail)。
    """
    ok_count, fail_list = 0, []
    for rnd in range(rounds):
        srq_obj = None
        try:
            srq_obj, srqn, _ = create_verbs_srq_with_pd(ctx, num_wqes)
            ret, fw_status, syndrome, detail = modify_srq_via_libmlx5(
                srq_obj, srqn=srqn, op_mod=1, lwm=1)
            if ret != 0:
                fail_list.append((rnd, 'modify',
                                  f'ret={ret}, fw={fw_status}, '
                                  f'synd={syndrome}, detail={detail}'))
                continue
            ok_count += 1
        except Exception as exc:
            fail_list.append((rnd, 'create', str(exc)))
        finally:
            if srq_obj is not None:
                try:
                    close_verbs_srq_guarded(srq_obj)
                except Exception:
                    pass
    return ok_count, fail_list


def post_recv_to_verbs_srq(srq_obj, count, wqe_size=1024, pd_obj=None):
    """向 verbs SRQ 投递 count 个接收 WR，使 wqe_cnt 增加。

    返回 (0, count) 或 (-1, err_msg)。
    """
    from pyverbs.wr import SGE, RecvWR
    from pyverbs.mr import MR
    try:
        pd = pd_obj or getattr(srq_obj, 'pd', None)
        if pd is None:
            return -1, '无法获取 SRQ 关联的 PD'
        # IBV_ACCESS_LOCAL_WRITE = 1
        mr = MR(pd, length=max(int(wqe_size) * int(count), 4096), access=1)
        wrs = []
        for i in range(int(count)):
            sge = SGE(mr.buf, int(wqe_size), mr.lkey)
            try:
                wrs.append(RecvWR(wr_id=i, num_sge=1, sg=[sge]))
            except TypeError:
                wrs.append(RecvWR(num_sge=1, sg=[sge], wr_id=i))
        srq_obj.post_recv(wrs)
        global _post_recv_mr_refs
        try:
            _post_recv_mr_refs
        except NameError:
            _post_recv_mr_refs = []
        _post_recv_mr_refs.append(mr)
        return 0, int(count)
    except Exception as exc:
        return -1, f'post_recv 失败: {exc}'


def query_reserved_qpn_caps(ctx):
    """探测当前设备是否支持 Reserved QPN，并返回最大 block 粒度。

    实现方式：先尝试创建 log_obj_range=0 的 block；若失败则认为不支持。
    若支持，则逐个尝试更大的 log_obj_range，返回最后一个成功的值。
    """
    import pyverbs.providers.mlx5.mlx5dv as m
    try:
        obj, _ = create_reserved_qpn(ctx, 0)
        destroy_reserved_qpn(obj)
    except Exception:
        return False, 0

    max_log = 0
    for log_range in range(1, 16):
        try:
            obj, _ = create_reserved_qpn(ctx, log_range)
            destroy_reserved_qpn(obj)
            max_log = log_range
        except Exception:
            break
    return True, max_log


def create_reserved_qpn(ctx, log_obj_range=0):
    """通过 DevX CREATE_GENERAL_OBJECT + MLX5_OBJ_TYPE_RESERVED_QPN 创建 block。

    返回 (obj, first_qpn)，其中 first_qpn 来自 general_obj_out_cmd_hdr 的 obj_id。
    """
    import pyverbs.providers.mlx5.mlx5dv as m
    hdr = GeneralObjInCmdHdr(
        opcode=DevxOps.MLX5_CMD_OP_CREATE_GENERAL_OBJECT,
        obj_type=DevxOps.MLX5_OBJ_TYPE_RESERVED_QPN,
        log_obj_range=log_obj_range,
    )
    rqpns = ReservedQpnBits()
    cmd_in = bytes(CreateReservedQpnIn(hdr=hdr, rqpns=rqpns))
    obj = m.Mlx5DevxObj(ctx, cmd_in, len(GeneralObjOutCmdHdr()))
    out = GeneralObjOutCmdHdr(obj.out_view)
    return obj, out.obj_id


def destroy_reserved_qpn(obj):
    """释放 Reserved QPN block（即销毁 General Object）。"""
    obj.close()


def try_create_reserved_qpn_raw(ctx, opcode, obj_type, log_obj_range):
    """用于异常测试：直接按指定参数尝试创建，返回 'OK' 或 'FAIL:<reason>'。"""
    import pyverbs.providers.mlx5.mlx5dv as m
    try:
        hdr = GeneralObjInCmdHdr(
            opcode=opcode,
            obj_type=obj_type,
            log_obj_range=log_obj_range,
        )
        rqpns = ReservedQpnBits()
        cmd_in = bytes(CreateReservedQpnIn(hdr=hdr, rqpns=rqpns))
        obj = m.Mlx5DevxObj(ctx, cmd_in, len(GeneralObjOutCmdHdr()))
        obj.close()
        return 'OK'
    except Exception as e:
        return f'FAIL:{e}'


class DevxMkeyNotSupportedError(RuntimeError):
    """固件不支持在 DevX uid 下创建 MKEY（errno 121 / Remote I/O error）。

    部分平台（如 issi 使能后）对 DevX uid 下 CREATE_MKEY 返回 errno 121，
    这是固件能力限制而非被测驱动/脚本缺陷。测试脚本捕获该异常后应将
    用例标记为 SKIP，而不是判失败。
    """


def create_devx_mkey(ctx, pd_num, length=4096, page_size=4096, access_mode=0):
    """通过 DevX 接口创建一个 MKEY，返回 [mkey_obj, mkey]。

    仅使用 DevX 原生接口：通过 Mlx5DevxObj 下发固件 CREATE_MKEY
    （MLX5_CMD_OP_CREATE_MKEY=0x200）命令，不经过 verbs。

    DevX 命令构造说明：
    默认使用 PA（Physical Address）访问模式 + free=1（空 MTT，不关联内存）创建
    一个仅绑定 PD 的"占位"MKEY，用于验证 DevX CREATE_MKEY 基本能力。
    可通过 access_mode 改为 KLMS（2）/MTT（1）等模式，供探测脚本交叉验证。
    qpn 必须设为 0xffffff（内核 set_mkc_access_pd_addr_fields 固定值）。

    若固件拒绝在 DevX uid 下创建 MKEY（errno 121），抛出
    DevxMkeyNotSupportedError，由测试脚本识别为环境限制并跳过用例。
    """
    import pyverbs.providers.mlx5.mlx5dv as m

    log_page_size = int(math.log2(page_size)) - 12
    if log_page_size < 0:
        log_page_size = 0

    mkc = SwMkc(
        free=1,                 # 无 PAS / 空 MTT
        access_mode_4_2=(access_mode >> 2) & 0x7,
        access_mode_1_0=access_mode & 0x3,
        umr_en=1,
        lw=1,
        lr=1,
        qpn=0xFFFFFF,           # 内核固定值
        length64=1,
        pd=pd_num & 0xFFFFFF,
        start_addr=0,
        len=length & 0xFFFFFFFFFFFFFFFF,
        translations_octword_size=0,
        log_page_size=log_page_size,
    )
    cmd_in_pkt = CreateMkeyIn(
        mkc=mkc,
        translations_octword_actual_size=0,
    )
    cmd_in = bytes(cmd_in_pkt)
    out_len = len(CreateMkeyOut())  # 16 bytes
    try:
        mkey_obj = m.Mlx5DevxObj(ctx, cmd_in, out_len)
        mkey_out = CreateMkeyOut(mkey_obj.out_view)
        # 完整 mkey = mkey_7_0(8) | mkey_index(24)
        mkey = (mkc.mkey_7_0 << 24) | (mkey_out.mkey_index & 0xFFFFFF)
        return [mkey_obj, mkey]
    except Exception as devx_err:
        # DevX CREATE_MKEY 被固件拒绝（issi 使能平台对 DevX uid 返回
        # errno 121 / Remote I/O error）。这是固件能力限制，非脚本/驱动缺陷。
        # 抛出专用异常，由测试脚本识别为环境限制并跳过用例。
        raise DevxMkeyNotSupportedError(
            f'固件拒绝在 DevX uid 下创建 MKEY: {devx_err!r}') from devx_err

class CreateMkeyGeneralObjectIn(PRMPacket):
    """通过 CREATE_GENERAL_OBJECT + MLX5_OBJ_TYPE_MKEY 创建 MKEY 的输入包。

    布局（基于 mlx5 PRM create_general_object_in 扩展）：
        byte  0-15: general_obj_in_cmd_hdr (opcode/uid/obj_type/obj_id/log_obj_range)
        byte 16-79: memory_key_context (mlx5_ifc_mkc_bits, 64 bytes)
        byte 80-..: 保留/对齐
    注意：部分平台对 obj_type 0xff01 的支持情况不同，实际布局可能需要根据
    目标固件调整。
    """
    fields_desc = [
        PacketField('hdr', GeneralObjInCmdHdr(), GeneralObjInCmdHdr),
        PacketField('mkc', SwMkc(), SwMkc),
        StrFixedLenField('reserved', None, length=16),
    ]


class DevxMkeyGeneralObjectNotSupportedError(RuntimeError):
    """固件不支持通过 CREATE_GENERAL_OBJECT + MLX5_OBJ_TYPE_MKEY 创建 MKEY。"""


def query_mkey_general_object_support(ctx):
    """探测当前环境是否支持通过 GENERAL_OBJECT + 0xff01 创建 MKEY。"""
    try:
        obj, mkey = create_mkey_via_general_object(ctx, pd_num=0)
        destroy_mkey_via_general_object(obj)
        return True, mkey
    except Exception:
        return False, 0


def create_mkey_via_general_object(ctx, pd_num, length=4096, page_size=4096,
                                   access_mode=0):
    """通过 DevX CREATE_GENERAL_OBJECT + MLX5_OBJ_TYPE_MKEY 创建 MKEY。

    返回 [mkey_obj, mkey]。
    """
    import pyverbs.providers.mlx5.mlx5dv as m

    log_page_size = int(math.log2(page_size)) - 12
    if log_page_size < 0:
        log_page_size = 0

    mkc = SwMkc(
        free=1,
        access_mode_4_2=(access_mode >> 2) & 0x7,
        access_mode_1_0=access_mode & 0x3,
        umr_en=1,
        lw=1,
        lr=1,
        qpn=0xFFFFFF,
        length64=1,
        pd=pd_num & 0xFFFFFF,
        start_addr=0,
        len=length & 0xFFFFFFFFFFFFFFFF,
        translations_octword_size=0,
        log_page_size=log_page_size,
    )
    hdr = GeneralObjInCmdHdr(
        opcode=DevxOps.MLX5_CMD_OP_CREATE_GENERAL_OBJECT,
        obj_type=DevxOps.MLX5_OBJ_TYPE_MKEY,
    )
    cmd_in = bytes(CreateMkeyGeneralObjectIn(hdr=hdr, mkc=mkc))
    out_len = len(GeneralObjOutCmdHdr())
    try:
        mkey_obj = m.Mlx5DevxObj(ctx, cmd_in, out_len)
        out = GeneralObjOutCmdHdr(mkey_obj.out_view)
        mkey = (mkc.mkey_7_0 << 24) | (out.obj_id & 0xFFFFFF)
        return [mkey_obj, mkey]
    except Exception as devx_err:
        raise DevxMkeyGeneralObjectNotSupportedError(
            f'固件拒绝通过 CREATE_GENERAL_OBJECT + MLX5_OBJ_TYPE_MKEY 创建 MKEY: '
            f'{devx_err!r}') from devx_err


def destroy_mkey_via_general_object(obj):
    """释放通过 CREATE_GENERAL_OBJECT + MLX5_OBJ_TYPE_MKEY 创建的 MKEY。"""
    obj.close()


def try_create_mkey_general_object_raw(ctx, opcode, obj_type, pd_num):
    """用于异常测试：直接按指定参数尝试创建 MKEY GENERAL_OBJECT。

    返回 'OK' 或 'FAIL:<reason>'。
    """
    import pyverbs.providers.mlx5.mlx5dv as m
    try:
        mkc = SwMkc(
            free=1,
            umr_en=1,
            lw=1,
            lr=1,
            qpn=0xFFFFFF,
            length64=1,
            pd=pd_num & 0xFFFFFF,
            start_addr=0,
            len=4096,
            translations_octword_size=0,
            log_page_size=0,
        )
        hdr = GeneralObjInCmdHdr(opcode=opcode, obj_type=obj_type)
        cmd_in = bytes(CreateMkeyGeneralObjectIn(hdr=hdr, mkc=mkc))
        obj = m.Mlx5DevxObj(ctx, cmd_in, len(GeneralObjOutCmdHdr()))
        obj.close()
        return 'OK'
    except Exception as e:
        return f'FAIL:{e}'


class QueryMkeyIn(PRMPacket):
    """mlx5_ifc_query_mkey_in_bits — QUERY_MKEY 输入（16 字节，无 uid 字段）。

    Layout: opcode[0x10] | reserved[0x10] | reserved[0x10] | op_mod[0x10]
            reserved[0x8] | mkey_index[0x18] | reserved[0x20]
    """
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_QUERY_MKEY),
        ShortField('reserved1', 0),
        ShortField('reserved2', 0),
        ShortField('op_mod', 0),
        BitField('reserved3', 0, 8),
        BitField('mkey_index', 0, 24),
        IntField('reserved4', 0),
    ]


class QueryMkeyOut(PRMPacket):
    """mlx5_ifc_query_mkey_out_bits 头部（16 字节）。

    后续 mkc(64B)/reserved/pas 由 extract_padding 吸收，
    关键字段通过 parse_query_mkey_out(raw) 直接按字节偏移解析。
    """
    fields_desc = [
        ByteField('status', 0),
        BitField('reserved1', 0, 24),
        IntField('syndrome', 0),
        StrFixedLenField('reserved2', None, length=8),
    ]


def parse_query_mkey_out(raw):
    """从 QUERY_MKEY 输出中提取 MKC 关键字段，返回 dict。

    输出布局：status[8b] | reserved[24b] | syndrome[32b] | reserved[64b]
              mkc(mlx5_ifc_mkc_bits, 64B, 从偏移 0x10 起) | reserved | pas

    相对 raw 的绝对偏移（mkc 起点 0x10=16，布局对应 SwMkc）：
        free   = word0 bit31，raw[0x10] >> 7
        access_mode_4_2 = raw[0x10] >> 4
        umr_en = word0 bit25，raw[0x10] >> 1
        a      = word0 bit24，raw[0x10] & 1
        rw/rr/lw/lr = word1 高 4bit，raw[0x11] 高 4 位各 1
        access_mode_1_0 = raw[0x11] >> 2
        ma_translation_mode = raw[0x11] & 3
        qpn    = word1 高 24bit，raw[0x14:0x17]
        mkey_7_0 = raw[0x17]
        length64 = word3 bit31，raw[0x1c] >> 7
        pd     = word3 低 24bit，raw[0x1d:0x20]
        start_addr = word4-5，raw[0x20:0x28]
        len    = word6-7，raw[0x28:0x30]
        translations_octword_size = word13，raw[0x44:0x48]
        log_page_size = word14 6bit，raw[0x48] & 0x3F
    """
    fields = {
        'status': raw[0],
        'syndrome': int.from_bytes(raw[4:8], 'big'),
        'free': (raw[0x10] >> 7) & 1,
        'access_mode_4_2': (raw[0x10] >> 4) & 0x7,
        'relaxed_ordering_write': (raw[0x10] >> 3) & 1,
        'small_fence_on_rdma_read_response': (raw[0x10] >> 2) & 1,
        'umr_en': (raw[0x10] >> 1) & 1,
        'a': raw[0x10] & 1,
        'rw': (raw[0x11] >> 7) & 1,
        'rr': (raw[0x11] >> 6) & 1,
        'lw': (raw[0x11] >> 5) & 1,
        'lr': (raw[0x11] >> 4) & 1,
        'access_mode_1_0': (raw[0x11] >> 2) & 0x3,
        'ma_translation_mode': raw[0x11] & 0x3,
        'qpn': int.from_bytes(raw[0x14:0x17], 'big') & 0xFFFFFF,
        'mkey_7_0': raw[0x17],
        'length64': (raw[0x1c] >> 7) & 1,
        'en_rinval': (raw[0x1c] >> 1) & 1,
        'pd': int.from_bytes(raw[0x1d:0x20], 'big') & 0xFFFFFF,
        'start_addr': int.from_bytes(raw[0x20:0x28], 'big'),
        'len': int.from_bytes(raw[0x28:0x30], 'big'),
        'translations_octword_size': int.from_bytes(raw[0x44:0x48], 'big'),
        'log_page_size': raw[0x48] & 0x3F,
    }
    return fields


def query_devx_mkey(mkey_obj, mkey_index=None, op_mod=0, out_len=4096):
    """通过 DevX OBJ_QUERY 通道（mkey_obj.query()）查询 MKEY。

    返回 (mkey_status, mkey_syndrome, fields_dict)：
        mkey_status == 0  成功，fields_dict 为解析出的 mkc 关键字段
        mkey_status == -1 确定性失败（对象已销毁、非 DevX 对象或远程异常），
                          mkey_syndrome 为失败原因描述

    注意：
        1. QUERY_MKEY(0x201) 必须走 mkey_obj.query() 的 OBJ_QUERY 通道，
           内核 devx_is_valid_obj_id 要求 cmd_in.mkey_index 与创建对象
           obj_id 一致，否则内核 EINVAL 到不了固件；
        2. create_devx_mkey 在固件拒绝 DevX CREATE_MKEY（errno 121）时
           抛 DevxMkeyNotSupportedError，探测阶段已识别为环境限制；
        3. 对象已销毁（close 后 obj=NULL）时确定性返回失败，
           避免 pyverbs query() 段错误。
    """
    try:
        if mkey_obj is None or not hasattr(mkey_obj, 'obj') or not mkey_obj.obj:
            return -1, 'DevX 对象已销毁或非 DevX 对象（handle=NULL），无法执行 QUERY', None
        if not hasattr(mkey_obj, 'query'):
            return -1, '对象不支持 query()（verbs MR 回退路径），无法执行 QUERY', None
        if mkey_index is None:
            mkey_index = CreateMkeyOut(mkey_obj.out_view).mkey_index
        cmd_in = QueryMkeyIn(mkey_index=mkey_index & 0xFFFFFF, op_mod=op_mod)
        raw = mkey_obj.query(bytes(cmd_in), out_len)
        out = QueryMkeyOut(raw)
        if out.status != 0:
            return out.status, out.syndrome, None
        return 0, 0, parse_query_mkey_out(raw)
    except Exception as exc:
        return -1, str(exc), None


def stress_query_devx_mkey(mkey_obj, count, mkey_index=None, op_mod=0):
    """连续 count 次查询同一 MKEY，返回 (status_list, fields_consistent)。

    循环必须收进 helper（普通函数帧），避免 ipvbs 远程 eval 字符串
    中列表推导式出现 NameError: name 'self' is not defined。
    """
    status_list, fields_list = [], []
    for _ in range(count):
        mkey_status, mkey_syndrome, mkey_fields = query_devx_mkey(
            mkey_obj, mkey_index=mkey_index, op_mod=op_mod)
        status_list.append((mkey_status, mkey_syndrome))
        fields_list.append(mkey_fields)
    consistent = len(fields_list) > 0 and all(
        f == fields_list[0] for f in fields_list)
    return status_list, consistent


# ====================================================================== #
#  Q_COUNTER（RDMA Q 计数器）—— DevX ALLOC/DEALLOC/QUERY                 #
#  依据 include/linux/mlx5/mlx5_ifc.h 中以下结构：                        #
#    mlx5_ifc_alloc_q_counter_in/out_bits   (16B in / 16B out)          #
#    mlx5_ifc_dealloc_q_counter_in_bits     (16B in)                    #
#    mlx5_ifc_query_q_counter_in/out_bits   (32B in / 256B out)         #
#  注意：ALLOC/DEALLOC 的 counter_set_id 为单字节位于 out/in 偏移 11；   #
#        QUERY 的 counter_set_id 为单字节位于 in 偏移 31（与 MKEY/SRQ    #
#        的 24bit id 布局不同），本段封装均已按 PRM 精确实现。            #
# ====================================================================== #


class AllocQCounterIn(PRMPacket):
    """mlx5_ifc_alloc_q_counter_in_bits — ALLOC_Q_COUNTER 输入（16 字节）。

    Layout: opcode[0x10] | uid[0x10] | reserved_at_20[0x10] | op_mod[0x10]
            reserved_at_40[0x40]
    """
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_ALLOC_Q_COUNTER),
        ShortField('uid', 0),
        ShortField('reserved1', 0),
        ShortField('op_mod', 0),
        StrFixedLenField('reserved2', None, length=8),
    ]


class AllocQCounterOut(PRMPacket):
    """mlx5_ifc_alloc_q_counter_out_bits — ALLOC_Q_COUNTER 输出（16 字节）。

    Layout: status[0x8] | reserved[0x18] | syndrome[0x20]
            reserved_at_40[0x18] | counter_set_id[0x8] | reserved_at_60[0x20]
    counter_set_id 为单字节，位于偏移 11（与 008_001 脚本 out_view[11] 一致）。
    """
    fields_desc = [
        ByteField('status', 0),
        BitField('reserved1', 0, 24),
        IntField('syndrome', 0),
        BitField('reserved2', 0, 24),
        ByteField('counter_set_id', 0),
        IntField('reserved3', 0),
    ]


class DeallocQCounterIn(PRMPacket):
    """mlx5_ifc_dealloc_q_counter_in_bits — DEALLOC_Q_COUNTER 输入（16 字节）。

    Layout: opcode[0x10] | reserved[0x10] | reserved[0x10] | op_mod[0x10]
            reserved_at_40[0x18] | counter_set_id[0x8] | reserved_at_60[0x20]
    counter_set_id 为单字节，位于偏移 11。
    """
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_DEALLOC_Q_COUNTER),
        ShortField('reserved1', 0),
        ShortField('reserved2', 0),
        ShortField('op_mod', 0),
        BitField('reserved3', 0, 24),
        ByteField('counter_set_id', 0),
        IntField('reserved4', 0),
    ]


def create_devx_q_counter(ctx):
    """通过 DevX ALLOC_Q_COUNTER 分配一个 Q_COUNTER，返回 [counter_obj, counter_set_id]。

    输入 16 字节（opcode=0x771 | uid=0 | op_mod=0），输出 16 字节，
    counter_set_id 为输出单字节（偏移 11）。对象 close() 即完成 DEALLOC_Q_COUNTER。

    注意：ALLOC_Q_COUNTER 不需要 PD，直接绑定 Context 下发；
    固件若拒绝（返回非 0 status）则关闭对象并抛出 RuntimeError，
    探测阶段据此识别环境限制。
    """
    import pyverbs.providers.mlx5.mlx5dv as m
    cmd_in = AllocQCounterIn()
    counter_obj = m.Mlx5DevxObj(ctx, bytes(cmd_in), 16)
    out = AllocQCounterOut(counter_obj.out_view)
    if out.status != 0:
        counter_obj.close()
        raise RuntimeError(
            f'ALLOC_Q_COUNTER 返回非 0 status={out.status}, syndrome={out.syndrome}')
    if out.counter_set_id == 0:
        counter_obj.close()
        raise RuntimeError('ALLOC_Q_COUNTER 返回 counter_set_id=0，分配疑似失败')
    return [counter_obj, out.counter_set_id]


class QueryQCounterIn(PRMPacket):
    """mlx5_ifc_query_q_counter_in_bits — QUERY_Q_COUNTER 输入（32 字节）。

    Layout: opcode[0x10] | reserved[0x10] | reserved[0x10] | op_mod[0x10]
            other_vport[0x1] | reserved_at_41[0xf] | vport_number[0x10]
            reserved_at_60[0x60] | clear[0x1] | aggregate[0x1] | reserved[0x1e]
            reserved_at_e0[0x18] | counter_set_id[0x8]
    counter_set_id 为单字节，位于偏移 31（与其他对象的 24bit id 不同）。
    """
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_QUERY_Q_COUNTER),
        ShortField('reserved1', 0),
        ShortField('reserved2', 0),
        ShortField('op_mod', 0),
        BitField('other_vport', 0, 1),
        BitField('reserved3', 0, 15),
        ShortField('vport_number', 0),
        StrFixedLenField('reserved4', None, length=12),
        BitField('clear', 0, 1),
        BitField('aggregate', 0, 1),
        BitField('reserved5', 0, 30),
        BitField('reserved6', 0, 24),
        ByteField('counter_set_id', 0),
    ]


class QueryQCounterOut(PRMPacket):
    """mlx5_ifc_query_q_counter_out_bits 头部（16 字节）。

    status[0x8] | reserved[0x18] | syndrome[0x20] | reserved_at_40[0x40]
    后续 256 字节输出（计数器区从偏移 0x10 起）由 extract_padding 吸收，
    关键计数字段通过 parse_query_q_counter_out(raw) 直接按字节偏移解析。
    """
    fields_desc = [
        ByteField('status', 0),
        BitField('reserved1', 0, 24),
        IntField('syndrome', 0),
        StrFixedLenField('reserved2', None, length=8),
    ]


def parse_query_q_counter_out(raw):
    """从 QUERY_Q_COUNTER 输出（256 字节）中提取关键字段，返回 dict。

    输出布局（mlx5_ifc_query_q_counter_out_bits，均为 32bit 计数器）：
        status @0 | reserved @1-3 | syndrome @4-7 | reserved @8-15
        rx_write_requests        @0x10   rx_read_requests           @0x18
        rx_atomic_requests       @0x20   rx_dct_connect             @0x28
        out_of_buffer            @0x30   out_of_sequence            @0x38
        duplicate_request        @0x40   rnr_nak_retry_err          @0x48
        packet_seq_err           @0x50   implied_nak_seq_err        @0x58
        local_ack_timeout_err    @0x60   req_rnr_retries_exceeded   @0x70
        resp_local_length_error  @0x78   req_local_length_error     @0x7c
        resp_local_qp_error      @0x80   local_operation_error      @0x84
        resp_local_protection    @0x88   req_local_protection       @0x8c
        resp_cqe_error           @0x90   req_cqe_error              @0x94
        req_mw_binding           @0x98   req_bad_response           @0x9c
        req_remote_invalid_request@0xa0  resp_remote_invalid_request@0xa4
        req_remote_access_errors @0xa8   resp_remote_access_errors  @0xac
        req_remote_operation_errors @0xb0 req_transport_retries_exceeded @0xb4
        cq_overflow              @0xb8   resp_cqe_flush_error       @0xbc
        req_cqe_flush_error      @0xc0   roce_adp_retrans           @0xc8
        roce_adp_retrans_to      @0xcc   roce_slow_restart          @0xd0
        roce_slow_restart_cnps   @0xd4   roce_slow_restart_trans    @0xd8
    """
    u32 = lambda off: int.from_bytes(raw[off:off + 4], 'big')
    fields = {
        'status': raw[0],
        'syndrome': int.from_bytes(raw[4:8], 'big'),
        'rx_write_requests': u32(0x10),
        'rx_read_requests': u32(0x18),
        'rx_atomic_requests': u32(0x20),
        'rx_dct_connect': u32(0x28),
        'out_of_buffer': u32(0x30),
        'out_of_sequence': u32(0x38),
        'duplicate_request': u32(0x40),
        'rnr_nak_retry_err': u32(0x48),
        'packet_seq_err': u32(0x50),
        'implied_nak_seq_err': u32(0x58),
        'local_ack_timeout_err': u32(0x60),
        'req_rnr_retries_exceeded': u32(0x70),
        'resp_local_length_error': u32(0x78),
        'req_local_length_error': u32(0x7c),
        'resp_local_qp_error': u32(0x80),
        'local_operation_error': u32(0x84),
        'resp_local_protection': u32(0x88),
        'req_local_protection': u32(0x8c),
        'resp_cqe_error': u32(0x90),
        'req_cqe_error': u32(0x94),
        'req_mw_binding': u32(0x98),
        'req_bad_response': u32(0x9c),
        'req_remote_invalid_request': u32(0xa0),
        'resp_remote_invalid_request': u32(0xa4),
        'req_remote_access_errors': u32(0xa8),
        'resp_remote_access_errors': u32(0xac),
        'req_remote_operation_errors': u32(0xb0),
        'req_transport_retries_exceeded': u32(0xb4),
        'cq_overflow': u32(0xb8),
        'resp_cqe_flush_error': u32(0xbc),
        'req_cqe_flush_error': u32(0xc0),
        'roce_adp_retrans': u32(0xc8),
        'roce_adp_retrans_to': u32(0xcc),
        'roce_slow_restart': u32(0xd0),
        'roce_slow_restart_cnps': u32(0xd4),
        'roce_slow_restart_trans': u32(0xd8),
    }
    return fields


def query_devx_q_counter(counter_obj, counter_set_id=None, op_mod=0, out_len=4096):
    """通过 DevX OBJ_QUERY 通道（counter_obj.query()）查询 Q_COUNTER。

    返回 (counter_status, counter_syndrome, fields_dict)：
        counter_status == 0  成功，fields_dict 为解析出的计数字段
        counter_status == -1 确定性失败（对象已销毁、非 DevX 对象或远程异常），
                             counter_syndrome 为失败原因描述

    注意：
        1. QUERY_Q_COUNTER(0x773) 必须走 counter_obj.query() 的 OBJ_QUERY
           通道，内核 devx_is_valid_obj_id 要求 cmd_in 中 obj_id 与创建
           对象一致，否则内核 EINVAL 到不了固件；
        2. QUERY_Q_COUNTER 的 counter_set_id 为单字节（in 偏移 31），
           由 AllocQCounterOut 解析得到（与 24bit id 的对象不同）；
        3. 对象已销毁（close 后 obj=NULL）时确定性返回失败，
           避免 pyverbs query() 段错误。
    """
    try:
        if counter_obj is None or not hasattr(counter_obj, 'obj') or not counter_obj.obj:
            return -1, 'DevX 对象已销毁或非 DevX 对象（handle=NULL），无法执行 QUERY', None
        if not hasattr(counter_obj, 'query'):
            return -1, '对象不支持 query()（非 DevX 对象），无法执行 QUERY', None
        if counter_set_id is None:
            counter_set_id = AllocQCounterOut(counter_obj.out_view).counter_set_id
        cmd_in = QueryQCounterIn(counter_set_id=counter_set_id & 0xFF, op_mod=op_mod)
        raw = counter_obj.query(bytes(cmd_in), out_len)
        out = QueryQCounterOut(raw)
        if out.status != 0:
            return out.status, out.syndrome, None
        return 0, 0, parse_query_q_counter_out(raw)
    except Exception as exc:
        return -1, str(exc), None


def stress_query_devx_q_counter(counter_obj, count, counter_set_id=None, op_mod=0):
    """连续 count 次查询同一 Q_COUNTER，返回 (status_list, fields_consistent)。

    循环必须收进 helper（普通函数帧），避免 ipvbs 远程 eval 字符串
    中列表推导式出现 NameError: name 'self' is not defined。
    """
    status_list, fields_list = [], []
    for _ in range(count):
        counter_status, counter_syndrome, counter_fields = query_devx_q_counter(
            counter_obj, counter_set_id=counter_set_id, op_mod=op_mod)
        status_list.append((counter_status, counter_syndrome))
        fields_list.append(counter_fields)
    consistent = len(fields_list) > 0 and all(
        f == fields_list[0] for f in fields_list)
    return status_list, consistent


class NopIn(PRMPacket):
    """MLX5_CMD_OP_NOP(0x80d) 输入：通用 16 字节命令头，无附加载荷。

    字段布局（实测为准，devx general command 通用头）：
        opcode[2] uid[2] op_mod[2] reserved1[2] reserved2[8]

    实测说明：字节4-5 为 devx general command 的 op_mod 字段，
    NOP 仅支持 op_mod=0，非 0 会被固件以 EREMOTEIO(121) 拒绝；
    字节6-7/字节8-15 为保留字段，非 0 被固件忽略（可填 0xFF）。
    """
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_NOP),
        ShortField('uid', 0),
        ShortField('op_mod', 0),
        ShortField('reserved1', 0),
        StrFixedLenField('reserved2', None, length=8),
    ]


def nop(ctx, op_mod=0, raw=None):
    """通过 DevX general command 通道下发一条 NOP(0x80d)，返回 (status, syndrome)。

    参数：
        ctx: Mlx5Context。
        op_mod: opcode_mod 字段（字节4-5），默认 0；注意 NOP 仅支持
            op_mod=0，非 0 会被固件以 EREMOTEIO(121) 拒绝。
        raw: 自定义 16 字节 inbox（用于保留字段全 1、非法 opcode 等
            边界/异常场景）。为 None 时按 NopIn 标准结构构造。

    返回：
        status == 0  固件命令成功；
        status > 0   固件返回错误（status 即固件错误码）；
        status == -1 Python 层异常，syndrome 为异常描述。

    说明：NOP 无对象 id、无输出载荷，使用 mlx5dv_devx_general_cmd
    通道发送（NOP 属于 general command 而非对象创建命令），outbox
    固定 16 字节，status 位于 byte 0、syndrome 位于 bytes 4~7。

    实测说明：NOP(0x80d) 在该环境（RHEL 9.1 / OFED 26.01）固件返回
    status=0，命令正常执行；此前误用 opcode=0x0（无效 opcode）才会被
    内核以 -EINVAL（errno 22）拒绝，命令到不了固件。
    """
    try:
        if raw is None:
            cmd_in = bytes(NopIn(op_mod=op_mod))
        else:
            cmd_in = raw
        out_raw = ctx.devx_general_cmd(cmd_in, 16)
        status = out_raw[0]
        syndrome = int.from_bytes(out_raw[4:8], 'big')
        return status, syndrome
    except Exception as exc:
        return -1, str(exc)


def stress_nop(ctx, count, op_mod=0):
    """连续 count 次下发 NOP，返回 (ok_count, fail_list)。

    ok_count 为 status==0 的次数；fail_list 为 [(status, syndrome), ...]。
    循环收进 helper，避免 ipvbs 远程 eval 字符串中的复杂表达式。
    """
    fail_list = []
    for _ in range(count):
        status, syndrome = nop(ctx, op_mod=op_mod)
        if status != 0:
            fail_list.append((status, syndrome))
    return count - len(fail_list), fail_list


def nop_cross_devices(dev_list):
    """对每个 RDMA 设备创建 Mlx5Context 并下发 NOP，返回结果列表。

    返回 [(dev, status, syndrome), ...]，按 dev_list 顺序排列；
    设备打开失败时 status=-1、syndrome 为异常描述。用于跨设备 NOP
    一致性测试（多 PF 场景）。
    """
    import pyverbs.providers.mlx5.mlx5dv as m
    results = []
    for dev in dev_list:
        try:
            ctx = m.Mlx5Context(m.Mlx5DVContextAttr(), dev)
            try:
                results.append((dev,) + nop(ctx))
            finally:
                ctx.close()
        except Exception as exc:
            results.append((dev, -1, str(exc)))
    return results


class QueryHcaCapIn(PRMPacket):
    """MLX5_CMD_OP_QUERY_HCA_CAP(0x100) 输入：通用 16 字节命令头。

    字段布局（mlx5_ifc_query_hca_cap_in_bits）：
        opcode[2] uid[2] reserved1[2] op_mod[2]
        reserved[4] capability_mask[4]
    """
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_QUERY_HCA_CAP),
        ShortField('uid', 0),
        ShortField('reserved1', 0),
        ShortField('op_mod', 0),
        StrFixedLenField('capability_mask', None, length=8),
    ]


def query_hca_cap(ctx, op_mod=0, out_len=1024, raw=None):
    """通过 DevX general command 通道下发 QUERY_HCA_CAP(0x100)，查询 HCA 能力。

    参数：
        ctx: Mlx5Context。
        op_mod: opcode_mod 字段。0=general 能力集；其余能力块（roce、
            atomic、odp 等）按固件支持情况返回。
        out_len: outbox 分配长度，默认 1024（实测该长度可成功返回能力数据）。
        raw: 自定义 16 字节 inbox（用于保留字段全 1、非法 opcode 等
            边界/异常场景）。为 None 时按 QueryHcaCapIn 标准结构构造。

    返回：
        (status, syndrome, out_raw)
        status == 0  固件命令成功，out_raw 为完整 outbox 字节；
        status > 0   固件返回错误，syndrome 即固件错误码，out_raw 为原始 outbox；
        status == -1 Python 层异常，syndrome 为异常描述、out_raw 为 None。

    说明：QUERY_HCA_CAP 位于内核 devx general_cmd 可下发列表内，内核会
    自动填充 uid，普通用户态上下文也可下发；实测固件 40.46.1006 返回
    status=0 正常成功（对照：NOP 等不在该列表的命令被内核以 -EINVAL
    拒绝，根本到不了固件）。status 位于 outbox byte 0，syndrome 位于
    bytes 4~8，HCA 能力数据从 byte 8 开始。
    """
    try:
        if raw is None:
            cmd_in = bytes(QueryHcaCapIn(op_mod=op_mod))
        else:
            cmd_in = raw
        out_raw = ctx.devx_general_cmd(cmd_in, out_len)
        status = out_raw[0]
        syndrome = int.from_bytes(out_raw[4:8], 'big')
        return status, syndrome, out_raw
    except Exception as exc:
        return -1, str(exc), None


def stress_query_hca_cap(ctx, count, op_mod=0, out_len=1024):
    """连续 count 次下发 QUERY_HCA_CAP，返回 (ok_count, fail_list)。

    ok_count 为 status==0 的次数；fail_list 为 [(status, syndrome), ...]。
    循环收进 helper，避免 ipvbs 远程 eval 字符串中的复杂表达式。
    """
    fail_list = []
    for _ in range(count):
        status, syndrome, _ = query_hca_cap(ctx, op_mod=op_mod, out_len=out_len)
        if status != 0:
            fail_list.append((status, syndrome))
    return count - len(fail_list), fail_list


def query_hca_cap_cross_devices(dev_list, op_mod=0, out_len=1024):
    """对每个 RDMA 设备创建 Mlx5Context 并下发 QUERY_HCA_CAP。

    返回 [(dev, status, syndrome), ...]，按 dev_list 顺序排列；
    设备打开失败时 status=-1、syndrome 为异常描述。用于跨设备
    QUERY_HCA_CAP 一致性测试（多 PF 场景）。
    """
    import pyverbs.providers.mlx5.mlx5dv as m
    results = []
    for dev in dev_list:
        try:
            ctx = m.Mlx5Context(m.Mlx5DVContextAttr(), dev)
            try:
                status, syndrome, _ = query_hca_cap(ctx, op_mod=op_mod,
                                                    out_len=out_len)
                results.append((dev, status, syndrome))
            finally:
                ctx.close()
        except Exception as exc:
            results.append((dev, -1, str(exc)))
    return results


class QueryHcaVportContextIn(PRMPacket):
    """MLX5_CMD_OP_QUERY_HCA_VPORT_CONTEXT(0x762) 输入：真实 16 字节布局。

    字段布局（mlx5_ifc_query_hca_vport_context_in_bits）：
        opcode[2] reserved[2] reserved[2] op_mod[2]
        other_vport(1bit)+reserved(11bit)+port_num(4bit)[2] vport_number[2]
        reserved[4]
    """
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_QUERY_HCA_VPORT_CONTEXT),
        ShortField('reserved1', 0),
        ShortField('reserved2', 0),
        ShortField('op_mod', 0),
        BitField('other_vport', 0, 1),
        BitField('reserved3', 0, 11),
        BitField('port_num', 1, 4),
        ShortField('vport_number', 0),
        StrFixedLenField('reserved4', None, length=4),
    ]


def query_hca_vport_context(ctx, op_mod=0, other_vport=0, port_num=1,
                            vport_number=0, out_len=1024, raw=None):
    """通过 DevX general command 通道下发 QUERY_HCA_VPORT_CONTEXT(0x762)。

    参数：
        ctx: Mlx5Context。
        op_mod: opcode_mod 字段。0=普通 vport 上下文；1=仅字段选择
            （field_select）查询等，按固件支持情况返回。
        other_vport: 1=查询指定 vport_number 的 vport（VF）；
            0=查询本机 vport（此时 vport_number 必须为 0）。
        port_num: 物理端口号（1 起）。双口设备用于区分端口。
        vport_number: vport 号（other_vport=1 时有效，0 为 PF）。
        out_len: outbox 分配长度，默认 1024。
        raw: 自定义 16 字节 inbox（用于保留字段全 1、非法 opcode、非法
            vport_number 等边界/异常场景）。为 None 时按
            QueryHcaVportContextIn 标准结构构造。

    返回：
        (status, syndrome, out_raw)
        status == 0  固件命令成功，out_raw 为完整 outbox 字节；
        status > 0   固件返回错误，syndrome 即固件错误码，out_raw 为原始 outbox；
        status == -1 Python 层异常，syndrome 为异常描述、out_raw 为 None。

    说明：QUERY_HCA_VPORT_CONTEXT 命令能穿过内核 devx general_cmd
    列表（内核会填充 uid），但实测固件 40.46.1006 返回 status=0x02
    （MLX5_CMD_STAT_BAD_OP_ERR，syndrome=0x00482341），即固件不识别该
    opcode——本环境不支持该命令，脚本探测到不支持会自动 skip。
    status 位于 outbox byte 0，syndrome 位于 bytes 4~8；hca_vport_context
    数据从 outbox byte 16 开始（field_select=bytes16-19，
    port_state/vport_state 在 byte 51 的高低 4bit，system_image_guid/
    port_guid/node_guid 分别在 bytes56-63/64-71/72-79）。
    """
    try:
        if raw is None:
            cmd_in = bytes(QueryHcaVportContextIn(
                op_mod=op_mod, other_vport=other_vport, port_num=port_num,
                vport_number=vport_number))
        else:
            cmd_in = raw
        out_raw = ctx.devx_general_cmd(cmd_in, out_len)
        status = out_raw[0]
        syndrome = int.from_bytes(out_raw[4:8], 'big')
        return status, syndrome, out_raw
    except Exception as exc:
        return -1, str(exc), None


def stress_query_hca_vport_context(ctx, count, op_mod=0, other_vport=0,
                                   port_num=1, vport_number=0, out_len=1024):
    """连续 count 次下发 QUERY_HCA_VPORT_CONTEXT，返回 (ok_count, fail_list)。

    ok_count 为 status==0 的次数；fail_list 为 [(status, syndrome), ...]。
    循环收进 helper，避免 ipvbs 远程 eval 字符串中的复杂表达式。
    """
    fail_list = []
    for _ in range(count):
        status, syndrome, _ = query_hca_vport_context(
            ctx, op_mod=op_mod, other_vport=other_vport, port_num=port_num,
            vport_number=vport_number, out_len=out_len)
        if status != 0:
            fail_list.append((status, syndrome))
    return count - len(fail_list), fail_list


def query_hca_vport_context_cross_devices(dev_list, op_mod=0, out_len=1024):
    """对每个 RDMA 设备创建 Mlx5Context 并下发 QUERY_HCA_VPORT_CONTEXT。

    返回 [(dev, status, syndrome), ...]，按 dev_list 顺序排列；
    设备打开失败时 status=-1、syndrome 为异常描述。用于跨设备
    QUERY_HCA_VPORT_CONTEXT 一致性测试（多 PF 场景）。
    """
    import pyverbs.providers.mlx5.mlx5dv as m
    results = []
    for dev in dev_list:
        try:
            ctx = m.Mlx5Context(m.Mlx5DVContextAttr(), dev)
            try:
                status, syndrome, _ = query_hca_vport_context(
                    ctx, op_mod=op_mod, out_len=out_len)
                results.append((dev, status, syndrome))
            finally:
                ctx.close()
        except Exception as exc:
            results.append((dev, -1, str(exc)))
    return results


class QueryCongStatusIn(PRMPacket):
    """MLX5_CMD_OP_QUERY_CONG_STATUS(0x822) 输入：真实 16 字节布局。

    字段布局（mlx5_ifc_query_cong_status_in_bits）：
        opcode[2] reserved[2] reserved[2] op_mod[2]
        reserved[3] priority(4bit)+cong_protocol(4bit)[1] reserved[4]
    """
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_QUERY_CONG_STATUS),
        ShortField('reserved1', 0),
        ShortField('reserved2', 0),
        ShortField('op_mod', 0),
        StrFixedLenField('reserved3', None, length=3),
        BitField('priority', 0, 4),
        BitField('cong_protocol', 0, 4),
        StrFixedLenField('reserved4', None, length=4),
    ]


def query_cong_status(ctx, op_mod=0, priority=0, cong_protocol=0,
                      out_len=64, raw=None):
    """通过 DevX general command 通道下发 QUERY_CONG_STATUS(0x822)。

    参数：
        ctx: Mlx5Context。
        op_mod: opcode_mod 字段，默认 0。
        priority: 优先级（4bit，0-7，用于查询对应优先级拥塞控制状态）。
        cong_protocol: 拥塞协议（4bit，0=DCQCN 等，按固件定义）。
        out_len: outbox 分配长度，默认 64（实际状态只有 16 字节）。
        raw: 自定义 16 字节 inbox（用于保留字段全 1、非法 opcode、
            非法 priority/cong_protocol 等边界/异常场景）。为 None 时按
            QueryCongStatusIn 标准结构构造。

    返回：
        (status, syndrome, out_raw)
        status == 0  固件命令成功，out_raw 为完整 outbox 字节；
        status > 0   固件返回错误，syndrome 即固件错误码，out_raw 为原始 outbox；
        status == -1 Python 层异常，syndrome 为异常描述、out_raw 为 None。

    说明：QUERY_CONG_STATUS 用于查询 RoCE 全局拥塞控制状态（enable /
    tag_enable），是 DevX 查询类命令。实测（开启 mlx5_core 动态调试抓
    outbox）该命令能穿过内核 devx general_cmd 列表（内核会填充 uid），
    但固件 40.46.1006 返回 status=0x02（MLX5_CMD_STAT_BAD_OP_ERR，
    syndrome=0x00d5d777），即固件不识别该 opcode——本环境不支持该命令，
    脚本探测到不支持会自动 skip。status 位于 outbox byte 0，syndrome
    位于 bytes 4~8；enable/tag_enable 位于 byte 12 的最高 2 bit
    （enable=0x80，tag_enable=0x40）。
    """
    try:
        if raw is None:
            cmd_in = bytes(QueryCongStatusIn(op_mod=op_mod, priority=priority,
                                             cong_protocol=cong_protocol))
        else:
            cmd_in = raw
        out_raw = ctx.devx_general_cmd(cmd_in, out_len)
        status = out_raw[0]
        syndrome = int.from_bytes(out_raw[4:8], 'big')
        return status, syndrome, out_raw
    except Exception as exc:
        return -1, str(exc), None


def stress_query_cong_status(ctx, count, op_mod=0, priority=0,
                             cong_protocol=0, out_len=64):
    """连续 count 次下发 QUERY_CONG_STATUS，返回 (ok_count, fail_list)。

    ok_count 为 status==0 的次数；fail_list 为 [(status, syndrome), ...]。
    循环收进 helper，避免 ipvbs 远程 eval 字符串中的复杂表达式。
    """
    fail_list = []
    for _ in range(count):
        status, syndrome, _ = query_cong_status(
            ctx, op_mod=op_mod, priority=priority,
            cong_protocol=cong_protocol, out_len=out_len)
        if status != 0:
            fail_list.append((status, syndrome))
    return count - len(fail_list), fail_list


class QueryCongParamsIn(PRMPacket):
    """MLX5_CMD_OP_QUERY_CONG_PARAMS(0x824) 输入：真实 16 字节布局。

    字段布局（mlx5_ifc_query_cong_params_in_bits）：
        opcode[2] reserved[2] reserved[2] op_mod[2]
        reserved[3] reserved(4bit)+cong_protocol(4bit)[1] reserved[4]
    """
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_QUERY_CONG_PARAMS),
        ShortField('reserved1', 0),
        ShortField('reserved2', 0),
        ShortField('op_mod', 0),
        StrFixedLenField('reserved3', None, length=3),
        BitField('reserved3b', 0, 4),
        BitField('cong_protocol', 0, 4),
        StrFixedLenField('reserved4', None, length=4),
    ]


def query_cong_params(ctx, op_mod=0, cong_protocol=0, out_len=272, raw=None):
    """通过 DevX general command 通道下发 QUERY_CONG_PARAMS(0x824)。

    参数：
        ctx: Mlx5Context。
        op_mod: opcode_mod 字段，默认 0。
        cong_protocol: 拥塞协议（4bit，0=802.1Qau，1=RoCE ECN，2=RoCEv2 CC）。
        out_len: outbox 分配长度，默认 272（status/syndrome 16 字节 +
            congestion_parameters 参数块 256 字节）。
        raw: 自定义 16 字节 inbox（用于保留字段全 1、非法 opcode、
            非法 cong_protocol 等边界/异常场景）。为 None 时按
            QueryCongParamsIn 标准结构构造。

    返回：
        (status, syndrome, out_raw)
        status == 0  固件命令成功，out_raw 为完整 outbox 字节；
        status > 0   固件返回错误，syndrome 即固件错误码，out_raw 为原始 outbox；
        status == -1 Python 层异常，syndrome 为异常描述、out_raw 为 None。

    说明：QUERY_CONG_PARAMS 用于查询拥塞控制协议配置参数（如 RoCE ECN
    的 alpha/beta 等），是 DevX 查询类命令。与 QUERY_CONG_STATUS(0x822)
    同族：STATUS 查当前拥塞状态，PARAMS 查协议参数。实测该命令能穿过
    内核 devx general_cmd 列表，但固件 40.46.1006 对同族 QUERY_CONG_STATUS
    返回 status=0x02（BAD_OP_ERR），QUERY_CONG_PARAMS 大概率同样不被
    支持，脚本探测到不支持会自动 skip。status 位于 outbox byte 0，
    syndrome 位于 bytes 4~8。
    """
    try:
        if raw is None:
            cmd_in = bytes(QueryCongParamsIn(op_mod=op_mod,
                                             cong_protocol=cong_protocol))
        else:
            cmd_in = raw
        out_raw = ctx.devx_general_cmd(cmd_in, out_len)
        status = out_raw[0]
        syndrome = int.from_bytes(out_raw[4:8], 'big')
        return status, syndrome, out_raw
    except Exception as exc:
        return -1, str(exc), None


def stress_query_cong_params(ctx, count, op_mod=0, cong_protocol=0,
                             out_len=272):
    """连续 count 次下发 QUERY_CONG_PARAMS，返回 (ok_count, fail_list)。

    ok_count 为 status==0 的次数；fail_list 为 [(status, syndrome), ...]。
    循环收进 helper，避免 ipvbs 远程 eval 字符串中的复杂表达式。
    """
    fail_list = []
    for _ in range(count):
        status, syndrome, _ = query_cong_params(
            ctx, op_mod=op_mod, cong_protocol=cong_protocol,
            out_len=out_len)
        if status != 0:
            fail_list.append((status, syndrome))
    return count - len(fail_list), fail_list


class QueryCongStatisticsIn(PRMPacket):
    """MLX5_CMD_OP_QUERY_CONG_STATISTICS(0x826) 输入：真实 16 字节布局。

    字段布局（mlx5_ifc_query_cong_statistics_in_bits）：
        opcode[2] reserved[2] reserved[2] op_mod[2]
        clear(1bit)+reserved(7bit)[1] reserved[3] reserved[4]
    """
    fields_desc = [
        ShortField('opcode', DevxOps.MLX5_CMD_OP_QUERY_CONG_STATISTICS),
        ShortField('reserved1', 0),
        ShortField('reserved2', 0),
        ShortField('op_mod', 0),
        BitField('clear', 0, 1),
        BitField('reserved3', 0, 7),
        StrFixedLenField('reserved4', None, length=11),
    ]


def query_cong_statistics(ctx, op_mod=0, clear=0, out_len=2176, raw=None):
    """通过 DevX general command 通道下发 QUERY_CONG_STATISTICS(0x826)。

    参数：
        ctx: Mlx5Context。
        op_mod: opcode_mod 字段，默认 0。
        clear: 查询后清零统计计数器（1bit），置 1 表示清零。
        out_len: outbox 分配长度，默认 2176（0x880，含 status/syndrome
            及各统计字段 rp_cur_flows/sum_flows/rp_cnp_*_high|low/
            time_stamp/accumulators_period/np_ecn_marked_roce_packets/
            np_cnp_sent 等）。
        raw: 自定义 16 字节 inbox（用于保留字段全 1、非法 opcode、
            clear 置 1 等边界/异常场景）。为 None 时按
            QueryCongStatisticsIn 标准结构构造。

    返回：
        (status, syndrome, out_raw)
        status == 0  固件命令成功，out_raw 为完整 outbox 字节；
        status > 0   固件返回错误，syndrome 即固件错误码，out_raw 为原始 outbox；
        status == -1 Python 层异常，syndrome 为异常描述、out_raw 为 None。

    说明：QUERY_CONG_STATISTICS 用于查询 RoCE 拥塞控制累计统计计数
    （RP/NP 各级计数器），与 QUERY_CONG_STATUS(0x822)、
    QUERY_CONG_PARAMS(0x824) 同族。实测该命令能穿过内核 devx
    general_cmd 列表，但固件 40.46.1006 对同族 QUERY_CONG_STATUS
    返回 status=0x02（BAD_OP_ERR），QUERY_CONG_STATISTICS 大概率同样
    不被支持，脚本探测到不支持会自动 skip。status 位于 outbox byte 0，
    syndrome 位于 bytes 4~8。
    """
    try:
        if raw is None:
            cmd_in = bytes(QueryCongStatisticsIn(op_mod=op_mod,
                                                 clear=clear))
        else:
            cmd_in = raw
        out_raw = ctx.devx_general_cmd(cmd_in, out_len)
        status = out_raw[0]
        syndrome = int.from_bytes(out_raw[4:8], 'big')
        return status, syndrome, out_raw
    except Exception as exc:
        return -1, str(exc), None


def stress_query_cong_statistics(ctx, count, op_mod=0, clear=0,
                                 out_len=2176):
    """连续 count 次下发 QUERY_CONG_STATISTICS，返回 (ok_count, fail_list)。

    ok_count 为 status==0 的次数；fail_list 为 [(status, syndrome), ...]。
    循环收进 helper，避免 ipvbs 远程 eval 字符串中的复杂表达式。
    """
    fail_list = []
    for _ in range(count):
        status, syndrome, _ = query_cong_statistics(
            ctx, op_mod=op_mod, clear=clear, out_len=out_len)
        if status != 0:
            fail_list.append((status, syndrome))
    return count - len(fail_list), fail_list


# ===================================================================== #
#  018 模块：mlx5dv_devx_umem_reg / reg_ex / dereg（libmlx5 ctypes 直调） #
# ===================================================================== #
# 已 dereg 的 umem 指针集合（防重复 dereg 造成 UAF）
_UMEM_DEREGISTERED_PTRS = set()
# helper 自动分配的 mmap 缓冲登记表：umem_ptr(int) -> (addr, alloc_size)
# dereg 成功后自动 munmap，防止泄漏
_UMEM_LIVE = {}


def _load_mlx5dv_umem_fns():
    """惰性加载 libmlx5 的 mlx5dv_devx_umem_reg/reg_ex/dereg 三个符号。

    返回 (fns, None)；加载失败返回 (None, err_msg)。
    fns = (fn_reg, fn_reg_ex, fn_dereg)。
    """
    import ctypes
    import ctypes.util
    global _umem_lib
    try:
        _umem_lib
    except NameError:
        _umem_lib = None
    if _umem_lib is not None:
        return _umem_lib, None
    candidates = []
    try:
        found = ctypes.util.find_library('mlx5')
        if found:
            candidates.append(found)
    except Exception:
        pass
    candidates += ['libmlx5.so.1', 'libmlx5.so']
    last_err = None
    for name in candidates:
        try:
            lib = ctypes.CDLL(name, mode=ctypes.RTLD_GLOBAL, use_errno=True)
            fn_reg = lib.mlx5dv_devx_umem_reg
            fn_reg.restype = ctypes.c_void_p
            fn_reg.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                               ctypes.c_size_t, ctypes.c_uint32]
            fn_reg_ex = lib.mlx5dv_devx_umem_reg_ex
            fn_reg_ex.restype = ctypes.c_void_p
            fn_reg_ex.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            fn_dereg = lib.mlx5dv_devx_umem_dereg
            fn_dereg.restype = ctypes.c_int
            fn_dereg.argtypes = [ctypes.c_void_p]
            _umem_lib = (fn_reg, fn_reg_ex, fn_dereg)
            return _umem_lib, None
        except Exception as load_err:
            last_err = load_err
    return None, f'加载 mlx5dv_devx_umem_reg/reg_ex/dereg 失败: {last_err}'


def _ctx_ptr(ctx):
    """提取 pyverbs Mlx5Context 的 ibv_context* 裸指针地址（int）。

    返回 (ptr, None)；失败返回 (None, 原因串)。
    pyverbs Context 的 .context 属性返回 <uintptr_t>self.context，
    Mlx5Context 继承自 Context 且未覆写，故可直接 int() 转换。
    """
    if ctx is None:
        return None, '守卫: ctx 为 None（NULL 指针不下发）'
    try:
        raw = getattr(ctx, 'context', None)
    except Exception as exc:
        return None, f'守卫: 读取 ctx.context 失败: {exc}'
    if raw is None:
        return None, '守卫: ctx 对象无 .context 属性（非 pyverbs mlx5 context）'
    try:
        ptr = int(raw)
    except Exception:
        ptr = 0
    if not ptr:
        return None, '守卫: ctx.context 地址为 0（context 已关闭?）'
    return ptr, None


def _alloc_locked_buffer(size):
    """mmap 页对齐匿名内存并触页锁定（best-effort mlock）。

    返回 (buf_addr_int, alloc_size)。失败抛 RuntimeError。
    devx umem_reg 由内核 ib_umem_get 自行 pin 页，用户态 mlock 非必需，
    mlock 失败（如 rlimit 限制）仅静默忽略，避免造成假失败。
    """
    import ctypes
    import ctypes.util
    import os
    page_size = os.sysconf('SC_PAGE_SIZE')
    need = max(int(size), 1)
    alloc_size = ((need + page_size - 1) // page_size) * page_size
    libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
    libc.mmap.restype = ctypes.c_void_p
    libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int,
                          ctypes.c_int, ctypes.c_int, ctypes.c_long]
    MAP_PRIVATE = 0x02
    MAP_ANONYMOUS = 0x20
    PROT_READ = 0x1
    PROT_WRITE = 0x2
    addr = libc.mmap(None, alloc_size, PROT_READ | PROT_WRITE,
                     MAP_PRIVATE | MAP_ANONYMOUS, -1, 0)
    if addr is None or addr == ctypes.c_void_p(-1).value:
        raise RuntimeError(f'mmap 失败: errno={ctypes.get_errno()}')
    # 触页保证物理分配
    ctypes.memset(addr, 0, alloc_size)
    try:
        libc.mlock.restype = ctypes.c_int
        libc.mlock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        libc.mlock(ctypes.c_void_p(addr), alloc_size)
    except Exception:
        pass
    return int(addr), alloc_size


def _free_locked_buffer(addr, size):
    """munmap 释放 _alloc_locked_buffer 分配的缓冲；静默容错。"""
    import ctypes
    import ctypes.util
    if not addr:
        return
    try:
        libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
        libc.munmap.restype = ctypes.c_int
        libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        libc.munmap(ctypes.c_void_p(int(addr)), int(size))
    except Exception:
        pass


def _read_umem_id(ptr_val):
    """从 mlx5dv_devx_umem 结构体读 umem_id（offset 0，u32）。"""
    import ctypes
    return int(ctypes.c_uint32.from_address(int(ptr_val)).value)


def umem_reg_via_libmlx5(ctx, size=4096, access=0, addr=None):
    """经 libmlx5 C 接口 mlx5dv_devx_umem_reg 注册 devx UMEM。

    返回 (call_ret, fw_status, syndrome, detail)：
      - call_ret == 0：成功，fw_status/syndrome 为 None，
        detail 为 dict，含 method/ptr/umem_id/addr/size/access；
      - call_ret 非 0：C 层 errno（reg 返回 NULL），detail 为原因串；
      - call_ret is None：守卫/加载失败，detail 为原因串。

    size<=0 时仍分配一个页缓冲并透传 size=0 下发（边界负向场景）。
    addr 未传时自动 mmap 锁定缓冲，dereg 成功后自动 munmap。
    """
    import ctypes
    fns, load_err = _load_mlx5dv_umem_fns()
    if fns is None:
        return None, None, None, f'加载失败: {load_err}'
    fn_reg = fns[0]
    ctx_ptr, err = _ctx_ptr(ctx)
    if ctx_ptr is None:
        return None, None, None, err
    buf = None
    try:
        if addr is None:
            buf_addr, alloc_size = _alloc_locked_buffer(int(size))
            addr = buf_addr
            buf = (buf_addr, alloc_size)
        else:
            addr = int(addr)
    except Exception as exc:
        return None, None, None, f'分配 umem 缓冲失败: {exc}'
    try:
        ctypes.set_errno(0)
        umem_ptr = fn_reg(ctypes.c_void_p(ctx_ptr), ctypes.c_void_p(addr),
                          ctypes.c_size_t(int(size)),
                          ctypes.c_uint32(int(access) & 0xFFFFFFFF))
    except Exception as call_err:
        if buf is not None:
            _free_locked_buffer(buf[0], buf[1])
        return None, None, None, '异常: 调用 mlx5dv_devx_umem_reg 失败: ' + \
                                 str(call_err)
    if not umem_ptr:
        errno = ctypes.get_errno() or -1
        if buf is not None:
            _free_locked_buffer(buf[0], buf[1])
        return int(errno), None, None, f'umem_reg 返回 NULL: errno={errno}'
    try:
        umem_id = _read_umem_id(int(umem_ptr))
    except Exception as exc:
        if buf is not None:
            _free_locked_buffer(buf[0], buf[1])
        return None, None, None, f'读取 umem_id 失败: {exc}'
    global _UMEM_LIVE
    _UMEM_LIVE[int(umem_ptr)] = buf
    # 该指针可能曾在 dereg 守卫集合中登记（libmlx5 malloc 复用地址），
    # 重新 reg 成功后清除登记，避免后续 dereg 被误判为重复 dereg
    _UMEM_DEREGISTERED_PTRS.discard(int(umem_ptr))
    detail = {'method': 'reg', 'ptr': int(umem_ptr), 'umem_id': int(umem_id),
              'addr': int(addr), 'size': int(size), 'access': int(access)}
    return 0, None, None, detail


def umem_reg_ex_via_libmlx5(ctx, size=4096, access=0, pgsz_bitmap=0x1000,
                            comp_mask=0, dmabuf_fd=-1, addr=None):
    """经 libmlx5 C 接口 mlx5dv_devx_umem_reg_ex 注册 UMEM（扩展入参）。

    mlx5dv_devx_umem_in 字段顺序（ctypes.Structure，勿手拼防错位）：
        addr u64 | size u64 | access u32 | pgsz_bitmap u32 |
        comp_mask u64 | dmabuf_fd i32 | reserved u32
    返回约定同 umem_reg_via_libmlx5；成功 detail 额外含 pgsz_bitmap/comp_mask。
    """
    import ctypes
    fns, load_err = _load_mlx5dv_umem_fns()
    if fns is None:
        return None, None, None, f'加载失败: {load_err}'
    fn_reg_ex = fns[1]
    ctx_ptr, err = _ctx_ptr(ctx)
    if ctx_ptr is None:
        return None, None, None, err
    buf = None
    try:
        if addr is None:
            buf_addr, alloc_size = _alloc_locked_buffer(int(size))
            addr = buf_addr
            buf = (buf_addr, alloc_size)
        else:
            addr = int(addr)
    except Exception as exc:
        return None, None, None, f'分配 umem 缓冲失败: {exc}'

    class _Mlx5dvDevxUmemIn(ctypes.Structure):
        _fields_ = [
            ('addr', ctypes.c_uint64),
            ('size', ctypes.c_uint64),
            ('access', ctypes.c_uint32),
            ('pgsz_bitmap', ctypes.c_uint32),
            ('comp_mask', ctypes.c_uint64),
            ('dmabuf_fd', ctypes.c_int32),
            ('reserved', ctypes.c_uint32),
        ]

    cmd_in = _Mlx5dvDevxUmemIn(
        addr=int(addr), size=int(size),
        access=int(access) & 0xFFFFFFFF,
        pgsz_bitmap=int(pgsz_bitmap) & 0xFFFFFFFF,
        comp_mask=int(comp_mask),
        dmabuf_fd=int(dmabuf_fd),
        reserved=0)
    try:
        ctypes.set_errno(0)
        umem_ptr = fn_reg_ex(ctypes.c_void_p(ctx_ptr),
                             ctypes.byref(cmd_in))
    except Exception as call_err:
        if buf is not None:
            _free_locked_buffer(buf[0], buf[1])
        return None, None, None, '异常: 调用 mlx5dv_devx_umem_reg_ex 失败: ' + \
                                 str(call_err)
    if not umem_ptr:
        errno = ctypes.get_errno() or -1
        if buf is not None:
            _free_locked_buffer(buf[0], buf[1])
        return int(errno), None, None, f'umem_reg_ex 返回 NULL: errno={errno}'
    try:
        umem_id = _read_umem_id(int(umem_ptr))
    except Exception as exc:
        if buf is not None:
            _free_locked_buffer(buf[0], buf[1])
        return None, None, None, f'读取 umem_id 失败: {exc}'
    global _UMEM_LIVE
    _UMEM_LIVE[int(umem_ptr)] = buf
    # 该指针可能曾在 dereg 守卫集合中登记（libmlx5 malloc 复用地址），
    # 重新 reg 成功后清除登记，避免后续 dereg 被误判为重复 dereg
    _UMEM_DEREGISTERED_PTRS.discard(int(umem_ptr))
    detail = {'method': 'reg_ex', 'ptr': int(umem_ptr),
              'umem_id': int(umem_id), 'addr': int(addr), 'size': int(size),
              'access': int(access), 'pgsz_bitmap': int(pgsz_bitmap),
              'comp_mask': int(comp_mask)}
    return 0, None, None, detail


def umem_dereg_via_libmlx5(ptr):
    """经 libmlx5 C 接口 mlx5dv_devx_umem_dereg 释放 UMEM。

    返回 (call_ret, fw_status, syndrome, detail)：
      - call_ret == 0：成功，detail 为 dict（含 dereg 前读取的 umem_id）；
      - call_ret 非 0：C 层返回错误，detail 为原因串；
      - call_ret is None：守卫拦截（NULL/已 dereg/加载失败），detail 为原因串。

    安全说明：libmlx5 dereg 内部会 free 结构体，本函数先读 umem_id 再下发；
    已 dereg 指针登记后二次调用直接守卫拦截，避免 UAF 段错误。
    """
    import ctypes
    fns, load_err = _load_mlx5dv_umem_fns()
    if fns is None:
        return None, None, None, f'加载失败: {load_err}'
    fn_dereg = fns[2]
    if ptr is None:
        return None, None, None, '守卫: umem 指针为 None（NULL 不下发）'
    try:
        ptr_val = int(ptr)
    except Exception:
        ptr_val = 0
    if not ptr_val:
        return None, None, None, '守卫: umem 指针为 0（NULL 不下发）'
    if ptr_val in _UMEM_DEREGISTERED_PTRS:
        return None, None, None, '守卫: 重复 dereg（该 umem 已 dereg 过）'
    try:
        umem_id = _read_umem_id(ptr_val)
    except Exception as exc:
        return None, None, None, f'守卫: 读取 umem_id 失败（内存已释放?）: {exc}'
    try:
        ctypes.set_errno(0)
        ret = fn_dereg(ctypes.c_void_p(ptr_val))
    except Exception as call_err:
        return None, None, None, '异常: 调用 mlx5dv_devx_umem_dereg 失败: ' + \
                                 str(call_err)
    if ret != 0:
        errno = ctypes.get_errno() or int(ret)
        return int(errno), None, None, f'dereg 返回 {ret}, errno={errno}'
    _UMEM_DEREGISTERED_PTRS.add(ptr_val)
    buf = _UMEM_LIVE.pop(ptr_val, None)
    if buf is not None:
        _free_locked_buffer(buf[0], buf[1])
    detail = {'method': 'dereg', 'umem_id': int(umem_id), 'ptr': int(ptr_val)}
    return 0, None, None, detail


def create_devx_cq_from_umem_ids(ctx, eqn, uar, cq_umem_id, dbr_umem_id,
                                 ncqes=256):
    """同 create_devx_cq，但 cq/dbr umem 由 libmlx5 devx umem_reg 提供。

    cq_umem_id/dbr_umem_id 为 int（umem_reg 返回 detail['umem_id']）。
    创建失败时 pyverbs 抛异常；成功返回 [cq_obj, cqn]。
    """
    import pyverbs.providers.mlx5.mlx5dv as m
    log_cq_size = math.ceil(math.log2(ncqes))
    sw_cqc = SwCqc(
        st=0,  # ICCQ
        c_eqn=eqn,
        uar_page=uar.page_id,
        log_cq_size=log_cq_size,
        dbr_umem_valid=1,
        dbr_umem_id=int(dbr_umem_id),
    )
    cmd_in = bytes(CreateCqIn(
        sw_cqc=sw_cqc,
        cq_umem_id=int(cq_umem_id),
        cq_umem_valid=1,
    ))
    cq_obj = m.Mlx5DevxObj(ctx, cmd_in, len(CreateCqOut()))
    cq_out = CreateCqOut(cq_obj.out_view)
    return [cq_obj, cq_out.cqn]


def create_devx_qp_from_umem_ids(ctx, pd_num, uar, cqn, wq_umem_id,
                                 dbr_umem_id, num_msgs=16, max_recv_sge=1):
    """同 create_devx_qp，但 CQ 编号与 wq/dbr umem 由外部 int 提供。

    cqn: 已创建 CQ 的编号；wq_umem_id/dbr_umem_id: umem_reg 返回的 id。
    创建失败时 pyverbs 抛异常；成功返回 [qp_obj, qpn]。
    """
    import pyverbs.providers.mlx5.mlx5dv as m
    cqn = int(cqn)

    # RQ/SQ size calculation（与 create_devx_qp 一致，从 rdma-core tests 简化）
    wqe_size = 16 * max_recv_sge
    rq_wqe_size = roundup_pow_of_two(wqe_size)
    rq_wq_size = roundup_pow_of_two(rq_wqe_size * num_msgs)
    if rq_wq_size < 64:
        rq_wq_size = 64
    rq_wqe_num = rq_wq_size // rq_wqe_size
    rq_wqe_shift = int(math.log2(rq_wqe_size - 1)) + 1
    log_rq_stride = rq_wqe_shift - 4

    sq_offset = rq_wq_size
    sq_wqe_size = 192 + 16  # rough max overhead + data seg
    sq_wqe_size = (sq_wqe_size + 63) & ~63  # align to 64
    sq_wq_size = roundup_pow_of_two(sq_wqe_size * num_msgs)
    sq_wqe_num = sq_wq_size // 64

    log_rq_size = int(math.log2(rq_wqe_num - 1)) + 1
    log_sq_size = int(math.log2(sq_wqe_num - 1)) + 1

    qpc = SwQpc(
        st=DevxOps.MLX5_QPC_ST_RC,
        pd=pd_num,
        pm_state=DevxOps.MLX5_QPC_PM_STATE_MIGRATED,
        log_rq_size=log_rq_size,
        log_sq_size=log_sq_size,
        ts_format=0x1,
        log_rq_stride=log_rq_stride,
        uar_page=uar.page_id,
        cqn_snd=cqn,
        cqn_rcv=cqn,
        dbr_umem_id=int(dbr_umem_id),
        dbr_umem_valid=1,
    )
    cmd_in = bytes(CreateQpIn(sw_qpc=qpc, wq_umem_id=int(wq_umem_id),
                              wq_umem_valid=1))
    qp_obj = m.Mlx5DevxObj(ctx, cmd_in, len(CreateQpOut()))
    qp_out = CreateQpOut(qp_obj.out_view)
    return [qp_obj, qp_out.qpn]


def probe_umem_reg_libmlx5(dev='mlx5_0'):
    """探测 mlx5dv_devx_umem_reg/dereg 在当前环境是否可用。

    探测流程：建 Mlx5Context -> umem_reg(4096) -> 读 umem_id -> dereg。
    返回 (supported, evidence)。
    """
    from pyverbs.providers.mlx5.mlx5dv import Mlx5Context, Mlx5DVContextAttr
    ctx = None
    try:
        ctx = Mlx5Context(Mlx5DVContextAttr(), dev)
        ret, _, _, detail = umem_reg_via_libmlx5(ctx, size=4096, access=0)
        if ret is None:
            return False, str(detail)
        if ret != 0:
            return False, f'umem_reg 返回 errno={ret}: {detail}'
        ptr = int(detail['ptr'])
        umem_id = int(detail['umem_id'])
        dret, _, _, ddetail = umem_dereg_via_libmlx5(ptr)
        if dret == 0:
            return True, (f'mlx5dv_devx_umem_reg/dereg 返回 0，'
                          f'umem_id={umem_id}')
        if dret is None:
            return False, str(ddetail)
        return False, f'dereg 失败: errno={dret}, {ddetail}'
    except Exception as exc:
        return False, f'探测异常: {exc}'
    finally:
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass


def probe_umem_reg_ex_libmlx5(dev='mlx5_0'):
    """探测 mlx5dv_devx_umem_reg_ex 在当前环境是否可用。

    探测流程：建 Mlx5Context -> umem_reg_ex(4096, pgsz_bitmap=0x1000)
    -> 读 umem_id -> dereg。
    返回 (supported, evidence)；reg_ex 返回 EOPNOTSUPP(95) 视为不支持。
    """
    from pyverbs.providers.mlx5.mlx5dv import Mlx5Context, Mlx5DVContextAttr
    ctx = None
    try:
        ctx = Mlx5Context(Mlx5DVContextAttr(), dev)
        ret, _, _, detail = umem_reg_ex_via_libmlx5(
            ctx, size=4096, pgsz_bitmap=0x1000, comp_mask=0)
        if ret is None:
            return False, str(detail)
        if ret != 0:
            return False, f'umem_reg_ex 返回 errno={ret}: {detail}'
        ptr = int(detail['ptr'])
        umem_id = int(detail['umem_id'])
        dret, _, _, ddetail = umem_dereg_via_libmlx5(ptr)
        if dret == 0:
            return True, (f'mlx5dv_devx_umem_reg_ex/dereg 返回 0，'
                          f'umem_id={umem_id}')
        if dret is None:
            return False, str(ddetail)
        return False, f'dereg 失败: errno={dret}, {ddetail}'
    except Exception as exc:
        return False, f'探测异常: {exc}'
    finally:
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass


def probe_umem_access_libmlx5(dev='mlx5_0', access=0xF):
    """探测 mlx5dv_devx_umem_reg 指定 access 标志组合是否可用。

    探测流程：建 Mlx5Context -> umem_reg(4096, access) -> dereg。
    返回 (supported, evidence)；内核/驱动拒绝的组合返回 errno 视为不支持。
    """
    from pyverbs.providers.mlx5.mlx5dv import Mlx5Context, Mlx5DVContextAttr
    ctx = None
    try:
        ctx = Mlx5Context(Mlx5DVContextAttr(), dev)
        ret, _, _, detail = umem_reg_via_libmlx5(
            ctx, size=4096, access=access)
        if ret is None:
            return False, str(detail)
        if ret != 0:
            return False, (f'umem_reg(access={access}) '
                           f'返回 errno={ret}: {detail}')
        ptr = int(detail['ptr'])
        umem_id = int(detail['umem_id'])
        dret, _, _, ddetail = umem_dereg_via_libmlx5(ptr)
        if dret == 0:
            return True, (f'mlx5dv_devx_umem_reg(access={access})/dereg '
                          f'返回 0，umem_id={umem_id}')
        if dret is None:
            return False, str(ddetail)
        return False, f'dereg 失败: errno={dret}, {ddetail}'
    except Exception as exc:
        return False, f'探测异常: {exc}'
    finally:
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass


def stress_umem_reg_dereg_libmlx5(ctx, count=1000, size=4096, access=0):
    """连续 count 次 umem_reg -> umem_dereg 循环。

    返回 (ok_count, fail_list)；ok_count==count 即全部成功。
    fail_list 元素为 (索引, ret, 原因串)。
    """
    ok_count = 0
    fail_list = []
    for i in range(int(count)):
        ret, _, _, detail = umem_reg_via_libmlx5(
            ctx, size=size, access=access)
        if ret != 0 or not isinstance(detail, dict):
            fail_list.append((i, ret, str(detail)))
            continue
        ptr = int(detail['ptr'])
        dret, _, _, ddetail = umem_dereg_via_libmlx5(ptr)
        if dret != 0:
            fail_list.append((i, dret, str(ddetail)))
            continue
        ok_count += 1
    return ok_count, fail_list


def try_create_devx_cq_from_umem_ids(ctx, eqn, uar, cq_umem_id, dbr_umem_id,
                                     ncqes=256):
    """尝试用外部 umem_id 创建 CQ（异常测试用）。

    成功返回 (True, [cq_obj, cqn])；pyverbs/固件拒绝返回 (False, repr(exc))。
    """
    try:
        return True, create_devx_cq_from_umem_ids(
            ctx, eqn, uar, cq_umem_id, dbr_umem_id, ncqes=ncqes)
    except Exception as exc:
        return False, repr(exc)


def try_create_devx_qp_from_umem_ids(ctx, pd_num, uar, cqn, wq_umem_id,
                                     dbr_umem_id, num_msgs=16, max_recv_sge=1):
    """尝试用外部 umem_id/CQ 创建 QP（异常测试用）。

    成功返回 (True, [qp_obj, qpn])；pyverbs/固件拒绝返回 (False, repr(exc))。
    """
    try:
        return True, create_devx_qp_from_umem_ids(
            ctx, pd_num, uar, cqn, wq_umem_id, dbr_umem_id,
            num_msgs=num_msgs, max_recv_sge=max_recv_sge)
    except Exception as exc:
        return False, repr(exc)


# ---------------------------------------------------------------------- #
#  mlx5dv_devx_qp_query（libmlx5 C DV 接口）相关封装
#
#  背景：内核 devx OBJ_QUERY 通道（qp_obj.query()）要求 cmd_in.qpn 与创建
#  对象一致，verbs QP（底层按 CREATE_QPN 编码创建）无法走该通道
#  （qpn 不匹配返回 EINVAL，命令到不了固件）。libmlx5 的
#  mlx5dv_devx_qp_query 走 devx_ucmd 用户命令通道，对任意 verbs QP 的
#  qpn 均可下发 QUERY_QP(0x50b)。此处经 ctypes 直接调用该 C 符号。
# ---------------------------------------------------------------------- #

def create_verbs_qp_with_pd(ctx, qp_type=2, max_send_wr=16, max_recv_wr=16,
                            cq_size=64):
    """标准 verbs 路径创建 QP，返回 [qp_obj, qpn, verbs_pd, verbs_cq]。

    qp_type 为 ibv 传输类型：2=RC、3=UC、4=UD。verbs QP 需要 verbs PD/CQ
    （独立于 DevX 对象）；用模块级列表保持 PD/CQ 引用防止提前回收。
    """
    from pyverbs.pd import PD
    from pyverbs.cq import CQ
    from pyverbs.qp import QP, QPInitAttr, QPCap
    global _verbs_qp_pd_refs, _verbs_qp_cq_refs
    try:
        _verbs_qp_pd_refs
    except NameError:
        _verbs_qp_pd_refs = []
    try:
        _verbs_qp_cq_refs
    except NameError:
        _verbs_qp_cq_refs = []
    verbs_pd = PD(ctx)
    verbs_cq = CQ(ctx, int(cq_size))
    cap = QPCap(max_recv_wr=max(int(max_recv_wr), 1),
                max_send_wr=max(int(max_send_wr), 1),
                max_recv_sge=1, max_send_sge=1)
    init_attr = QPInitAttr(qp_type=int(qp_type), scq=verbs_cq, rcq=verbs_cq,
                           cap=cap, sq_sig_all=1)
    qp_obj = QP(verbs_pd, init_attr=init_attr)
    _verbs_qp_pd_refs.append(verbs_pd)
    _verbs_qp_cq_refs.append(verbs_cq)
    qpn = int(qp_obj.qp_num)
    return [qp_obj, qpn, verbs_pd, verbs_cq]


def close_verbs_qp_guarded(qp_obj):
    """关闭 verbs QP 并登记其底层指针，防止 close 后误查询造成 UAF。

    注：登记集合按指针值匹配；指针复用场景下可能保守误判，可接受。
    """
    if qp_obj is None:
        return
    global _closed_verbs_qp_ids
    try:
        _closed_verbs_qp_ids
    except NameError:
        _closed_verbs_qp_ids = set()
    qp_ptr = getattr(qp_obj, 'qp', None)
    if qp_ptr is not None:
        try:
            _closed_verbs_qp_ids.add(int(qp_ptr))
        except Exception:
            pass
    try:
        qp_obj.close()
    except Exception:
        pass


def close_verbs_qp_resources(qp_obj, verbs_cq=None, verbs_pd=None, ctx=None):
    """按 QP -> CQ -> PD -> CTX 顺序释放 verbs QP 及其附属资源。

    verbs QP 必须先关闭才能关闭其发送/接收 CQ，否则 CQ.close 会失败；
    PD/CTX 依赖关系依次类推。
    """
    if qp_obj is not None:
        try:
            close_verbs_qp_guarded(qp_obj)
        except Exception:
            pass
    if verbs_cq is not None:
        try:
            verbs_cq.close()
        except Exception:
            pass
    if verbs_pd is not None:
        try:
            verbs_pd.close()
        except Exception:
            pass
    if ctx is not None:
        try:
            ctx.close()
        except Exception:
            pass


def _verbs_qp_fill_attr(attr, pairs):
    """对 QPAttr 无参实例按字段名赋值，返回 attr。

    无参构造的 QPAttr 默认值字段名与 pyverbs 关键字构造签名并不总一致，
    统一按 hasattr + setattr 填充（忽略缺失字段），吞掉单字段赋值异常。
    """
    for key, value in pairs:
        if value is None:
            continue
        if hasattr(attr, key):
            try:
                setattr(attr, key, value)
            except Exception:
                pass
    return attr


def verbs_qp_to_init(qp_obj, pkey_index=0, port_num=1, qp_access_flags=3):
    """将 verbs QP 迁移到 INIT(1) 态，返回 (0, None) 或 (-1, err_msg)。"""
    from pyverbs.qp import QPAttr
    if qp_obj is None:
        return -1, 'QP 对象为 None'
    try:
        attr = _verbs_qp_fill_attr(QPAttr(), [
            ('qp_state', 1),
            ('pkey_index', int(pkey_index)),
            ('port_num', int(port_num)),
            ('qp_access_flags', int(qp_access_flags)),
        ])
        qp_obj.to_init(attr)
        return 0, None
    except Exception as exc:
        return -1, f'QP.to_init 失败: {exc}'


def verbs_qp_to_rtr(qp_obj, qpn, qkey=0x1111, path_mtu=2, rq_psn=0,
                    max_dest_rd_atomic=1, min_rnr_timer=1):
    """将 INIT 态 verbs QP 迁移到 RTR(2) 态，返回 (0, None) 或 (-1, err)。

    qpn 为对端 QP 号（自连场景传自身 qpn）。UD 传输仅需 qkey/dest_qp_num
    等即可完成 RTR。
    """
    from pyverbs.qp import QPAttr
    if qp_obj is None:
        return -1, 'QP 对象为 None'
    try:
        attr = _verbs_qp_fill_attr(QPAttr(), [
            ('qp_state', 2),
            ('qkey', int(qkey)),
            ('path_mtu', int(path_mtu)),
            ('dest_qp_num', int(qpn)),
            ('rq_psn', int(rq_psn)),
            ('max_dest_rd_atomic', int(max_dest_rd_atomic)),
            ('min_rnr_timer', int(min_rnr_timer)),
        ])
        qp_obj.to_rtr(attr)
        return 0, None
    except Exception as exc:
        return -1, f'QP.to_rtr 失败: {exc}'


def verbs_qp_to_rts(qp_obj, qkey=0x1111, sq_psn=0, timeout=6, retry_cnt=5,
                    rnr_retry=5, max_rd_atomic=1):
    """将 RTR 态 verbs QP 迁移到 RTS(3) 态，返回 (0, None) 或 (-1, err)。"""
    from pyverbs.qp import QPAttr
    if qp_obj is None:
        return -1, 'QP 对象为 None'
    try:
        attr = _verbs_qp_fill_attr(QPAttr(), [
            ('qp_state', 3),
            ('qkey', int(qkey)),
            ('sq_psn', int(sq_psn)),
            ('timeout', int(timeout)),
            ('retry_cnt', int(retry_cnt)),
            ('rnr_retry', int(rnr_retry)),
            ('max_rd_atomic', int(max_rd_atomic)),
        ])
        qp_obj.to_rts(attr)
        return 0, None
    except Exception as exc:
        return -1, f'QP.to_rts 失败: {exc}'


def _load_mlx5dv_qp_query_fn():
    """惰性加载 libmlx5 的 mlx5dv_devx_qp_query 符号。

    返回 (fn, None)；加载失败返回 (None, err_msg)。
    """
    import ctypes
    import ctypes.util
    global _qp_query_lib
    try:
        _qp_query_lib
    except NameError:
        _qp_query_lib = None
    if _qp_query_lib is not None:
        return _qp_query_lib, None
    candidates = []
    try:
        found = ctypes.util.find_library('mlx5')
        if found:
            candidates.append(found)
    except Exception:
        pass
    candidates += ['libmlx5.so.1', 'libmlx5.so']
    last_err = None
    for name in candidates:
        try:
            lib = ctypes.CDLL(name, mode=ctypes.RTLD_GLOBAL)
            fn = lib.mlx5dv_devx_qp_query
            fn.restype = ctypes.c_int
            fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                           ctypes.c_void_p, ctypes.c_size_t]
            _qp_query_lib = fn
            return _qp_query_lib, None
        except Exception as load_err:
            last_err = load_err
    return None, f'加载 mlx5dv_devx_qp_query 失败: {last_err}'


def query_qp_via_libmlx5(qp_obj, qpn=None, op_mod=0, in_len=16, out_len=4096,
                         raw_in=None):
    """通过 libmlx5 C 接口 mlx5dv_devx_qp_query 查询 verbs QP。

    返回 (call_ret, fw_status, syndrome, detail)：
      - call_ret == 0：下发成功，fw_status 为固件 status，
        detail 为解析后的字段 dict（实际 out 长度 >=0x40 时）；
      - call_ret != 0：C 层返回 errno，命令被拒/未达固件，detail 为 None；
      - call_ret is None：被守卫拦截或函数加载失败，detail 为原因字符串。

    detail 字段来自 parse_query_qp_out，另含 sq_psn（qpc sq_psn@字节
    145-147，24 位大端；实测可由写入值精确回读）。qkey/rq_psn/path_mtu
    等在硬件 QPC 中无明文，未列入 detail。

    安全说明：out_storage 底层固定分配 >=4096 字节（out_len 仅作为
    outlen 参数透传），即使 libmlx5 未按 outlen 截断写入也不会越界。
    """
    import ctypes
    fn, load_err = _load_mlx5dv_qp_query_fn()
    if fn is None:
        return None, None, None, f'加载失败: {load_err}'
    # ---- 守卫：避免空指针 / 已销毁对象下发，防止段错误 ----
    if qp_obj is None:
        return None, None, None, '守卫: qp_obj 为 None（NULL 指针不下发）'
    if not hasattr(qp_obj, 'qp'):
        return None, None, None, '守卫: 对象非 pyverbs verbs QP（无 .qp 属性）'
    qp_ptr = getattr(qp_obj, 'qp', None)
    if qp_ptr is None:
        return None, None, None, '守卫: 已销毁（底层指针为空）'
    try:
        qp_ptr_val = int(qp_ptr)
    except Exception:
        qp_ptr_val = 0
    if not qp_ptr_val:
        return None, None, None, '守卫: 已销毁（底层指针为 0）'
    global _closed_verbs_qp_ids
    try:
        _closed_verbs_qp_ids
    except NameError:
        _closed_verbs_qp_ids = set()
    if qp_ptr_val in _closed_verbs_qp_ids:
        return None, None, None, '守卫: 已销毁（close 后查询）'
    if qpn is None:
        try:
            qpn = int(qp_obj.qp_num)
        except Exception as num_err:
            return None, None, None, f'守卫: 获取 qpn 失败: {num_err}'
    # ---- 构造 QUERY_QP inbox（opcode=0x50b, qpn@byte8-11）----
    if raw_in is not None:
        cmd_in = bytes(raw_in)
    else:
        cmd_in = (struct.pack('>HHHH', 0x50b, 0, 0, int(op_mod) & 0xFFFF) +
                  struct.pack('>I', int(qpn) & 0xFFFFFF) + b'\x00' * 4)
    cmd_storage = ctypes.create_string_buffer(cmd_in, len(cmd_in))
    out_storage = ctypes.create_string_buffer(max(int(out_len), 4096))
    try:
        ret = fn(ctypes.c_void_p(qp_ptr_val),
                 ctypes.cast(cmd_storage, ctypes.c_void_p), int(in_len),
                 ctypes.cast(out_storage, ctypes.c_void_p), int(out_len))
    except Exception as call_err:
        return None, None, None, '异常: 调用 mlx5dv_devx_qp_query 失败: ' + \
                                 str(call_err)
    raw = out_storage.raw
    if ret == 0:
        fw_status = raw[0] if len(raw) >= 1 else None
        syndrome = int.from_bytes(raw[4:8], 'big') if len(raw) >= 8 else None
        if len(raw) >= 0x40:
            try:
                detail = parse_query_qp_out(raw)
                if len(raw) >= 148:
                    detail['sq_psn'] = int.from_bytes(raw[145:148], 'big')
                else:
                    detail['sq_psn'] = None
            except Exception as parse_err:
                detail = {'parse_error': str(parse_err)}
        else:
            detail = {'out_too_small': True, 'out_len': len(raw)}
        return 0, fw_status, syndrome, detail
    return int(ret), None, None, None


def ibv_qp_to_state(qp_obj, state=5):
    """经 libibverbs ibv_modify_qp 将 QP 直接迁移到指定状态。

    state 取值：5=IBV_QPS_SQERR、6=IBV_QPS_ERR。用于构造 pyverbs 高层
    接口不易触发的状态（SQERR 通常需错误事件才能迁移，直接下发会被内核
    以 EINVAL(22) 拒绝——该拒绝本身即作为探测证据）。
    返回 (0, None) 成功；(-1, err_msg) 加载/调用异常；
    (errno, None) 内核拒绝（errno 为返回的 errno 绝对值）。
    """
    import ctypes
    import ctypes.util

    class _IbvQpAttrHead(ctypes.Structure):
        _fields_ = [('qp_state', ctypes.c_int),
                    ('en_sqd_async_notify', ctypes.c_int)]

    if qp_obj is None or not hasattr(qp_obj, 'qp'):
        return -1, 'QP 对象无效（无 .qp 属性）'
    candidates = []
    try:
        found = ctypes.util.find_library('ibverbs')
        if found:
            candidates.append(found)
    except Exception:
        pass
    candidates += ['libibverbs.so.1', 'libibverbs.so']
    fn = None
    for name in candidates:
        try:
            lib = ctypes.CDLL(name, mode=ctypes.RTLD_GLOBAL)
            fn = lib.ibv_modify_qp
            fn.restype = ctypes.c_int
            fn.argtypes = [ctypes.c_void_p, ctypes.POINTER(_IbvQpAttrHead),
                           ctypes.c_int]
            break
        except Exception:
            continue
    if fn is None:
        return -1, '加载 libibverbs 的 ibv_modify_qp 失败'
    try:
        head = _IbvQpAttrHead(qp_state=int(state), en_sqd_async_notify=0)
        ret = fn(ctypes.c_void_p(int(qp_obj.qp)), ctypes.byref(head), 1)
        # attr_mask 固定 IBV_QP_STATE=1
        if ret == 0:
            return 0, None
        return abs(int(ret)), None
    except Exception as exc:
        return -1, f'ibv_modify_qp 调用异常: {exc}'


def probe_qp_query_libmlx5(dev='mlx5_0', qp_type=2):
    """探测 mlx5dv_devx_qp_query 在当前环境是否可用。

    探测流程：verbs 创建 QP -> 经 libmlx5 C 接口下发 QUERY_QP -> 销毁。
    返回 (supported, evidence)。
    """
    from pyverbs.providers.mlx5.mlx5dv import Mlx5Context, Mlx5DVContextAttr
    ctx = None
    qp_obj = None
    try:
        ctx = Mlx5Context(Mlx5DVContextAttr(), dev)
        qp_obj, qpn, _, _ = create_verbs_qp_with_pd(ctx, qp_type=qp_type)
        ret, fw_status, syndrome, detail = query_qp_via_libmlx5(
            qp_obj, qpn=qpn)
        if ret == 0:
            return True, (f'mlx5dv_devx_qp_query 返回 0，fw_status='
                          f'{fw_status}，syndrome={syndrome}，'
                          f'fields={detail}')
        if ret is None:
            return False, str(detail)
        abs_ret = abs(int(ret))
        if abs_ret == 22:
            return False, ('EINVAL: ret=22, 命令被拒未达固件（devx_ucmd '
                           '通道不可用或入参非法）')
        if abs_ret == 121:
            return False, (f'EREMOTEIO: ret={ret}, fw_status={fw_status}, '
                           f'syndrome={syndrome}（命令达固件但被拒）')
        return False, f'ret={ret}, fw_status={fw_status}, syndrome={syndrome}'
    except Exception as exc:
        return False, f'探测异常: {exc}'
    finally:
        if qp_obj is not None:
            try:
                close_verbs_qp_guarded(qp_obj)
            except Exception:
                pass
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass


def probe_qp_query_states_libmlx5(dev='mlx5_0', qp_type=4, target='rts',
                                  qkey=0x1111, path_mtu=2, sq_psn=0x102030):
    """探测 verbs QP 状态推进各阶段（RESET/INIT/RTR/RTS）的 QUERY_QP 回读。

    target 取值: init/rtr/rts/sqer。qp_type 默认 4(UD)：UD 传输无连接，仅
    靠 qkey/dest_qp_num 等即可推进到 RTS，探测最稳。探测中任意一步查询
    失败即返回 (False, 原因)；sqer 目标在 RTS 后尝试 ibv_modify_qp 直转
    SQERR(5)，若驱动拒绝（SQERR 只能由错误事件触发，直转返回 EINVAL）
    即返回 (False, 原因)，对应用例探测即跳过。
    返回 (supported, evidence)。
    """
    from pyverbs.providers.mlx5.mlx5dv import Mlx5Context, Mlx5DVContextAttr
    ctx = None
    qp_obj = None
    try:
        ctx = Mlx5Context(Mlx5DVContextAttr(), dev)
        qp_obj, qpn, _, _ = create_verbs_qp_with_pd(ctx, qp_type=qp_type)
        target = str(target).lower()
        evidence = []

        def _state_query(tag):
            ret, fw, synd, detail = query_qp_via_libmlx5(qp_obj, qpn=qpn)
            state = detail.get('state') if isinstance(detail, dict) else None
            evidence.append(f'{tag} 态: ret={ret}, state={state}')
            return ret, state

        # RESET(0)：创建即查
        ret0, st0 = _state_query('RESET')
        if ret0 != 0:
            return False, evidence[-1] + '（创建后首查失败）'
        if target == 'reset':
            return st0 == 0, '; '.join(evidence)
        # INIT(1)
        r1, e1 = verbs_qp_to_init(qp_obj)
        if r1 != 0:
            return False, f'INIT 迁移失败: {e1}'
        ret1, st1 = _state_query('INIT')
        if ret1 != 0:
            return False, evidence[-1] + '（INIT 态查询失败）'
        if target == 'init':
            return st1 == 1, '; '.join(evidence)
        # RTR(2)
        r2, e2 = verbs_qp_to_rtr(qp_obj, qpn=qpn, qkey=int(qkey),
                                 path_mtu=int(path_mtu))
        if r2 != 0:
            return False, f'RTR 迁移失败: {e2}'
        ret2, st2 = _state_query('RTR')
        if ret2 != 0:
            return False, evidence[-1] + '（RTR 态查询失败）'
        if target == 'rtr':
            return st2 == 2, '; '.join(evidence)
        # RTS(3)
        r3, e3 = verbs_qp_to_rts(qp_obj, qkey=int(qkey), sq_psn=int(sq_psn))
        if r3 != 0:
            return False, f'RTS 迁移失败: {e3}'
        ret3, st3 = _state_query('RTS')
        if ret3 != 0:
            return False, evidence[-1] + '（RTS 态查询失败）'
        if target == 'rts':
            return st3 == 3, '; '.join(evidence)
        # SQERR(5)：RTS 后经 ibv_modify_qp 直转
        if target == 'sqer':
            ret_sq, err_sq = ibv_qp_to_state(qp_obj, state=5)
            if ret_sq != 0:
                return False, (f'SQERR 不可直接构造: ibv_modify_qp 返回 '
                               f'errno={ret_sq}（SQERR 只能由错误事件触发，'
                               f'本驱动拒绝主动迁移）{err_sq or ""}')
            ret4, st4 = _state_query('SQERR')
            if ret4 != 0:
                return False, evidence[-1] + '（SQERR 态查询失败）'
            return st4 == 5, '; '.join(evidence)
        return False, f'未知 target: {target}'
    except Exception as exc:
        return False, f'探测异常: {exc}'
    finally:
        if qp_obj is not None:
            try:
                close_verbs_qp_guarded(qp_obj)
            except Exception:
                pass
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass


def stress_query_qp_libmlx5(qp_obj, count=100, qpn=None):
    """连续 count 次经 libmlx5 查询同一 verbs QP。

    返回 (status_list, consistent)：
        status_list: [(call_ret, fw_status, syndrome, detail), ...]
        consistent: 所有成功查询的字段 dict 是否一致
    """
    if qpn is None:
        try:
            qpn = int(qp_obj.qp_num)
        except Exception:
            qpn = None
    status_list, fields_list = [], []
    for _ in range(int(count)):
        ret, fw_status, syndrome, detail = query_qp_via_libmlx5(
            qp_obj, qpn=qpn)
        status_list.append((ret, fw_status, syndrome, detail))
        if ret == 0 and isinstance(detail, dict) and \
                'parse_error' not in detail and 'out_too_small' not in detail:
            fields_list.append(detail)
    consistent = len(fields_list) > 0 and all(
        f == fields_list[0] for f in fields_list)
    return status_list, consistent


def create_query_destroy_stress_libmlx5(ctx, rounds=50, qp_type=2):
    """循环 rounds 轮：创建 verbs QP -> libmlx5 查询 -> 销毁。

    返回 (ok_count, fail_list)；fail_list 元素 (round, phase, detail)。
    """
    ok_count, fail_list = 0, []
    for rnd in range(int(rounds)):
        qp_obj = None
        try:
            qp_obj, qpn, _, _ = create_verbs_qp_with_pd(ctx, qp_type=qp_type)
            ret, fw_status, syndrome, detail = query_qp_via_libmlx5(
                qp_obj, qpn=qpn)
            if ret != 0:
                fail_list.append((rnd, 'query',
                                  f'ret={ret}, fw={fw_status}, '
                                  f'synd={syndrome}, detail={detail}'))
                continue
            ok_count += 1
        except Exception as exc:
            fail_list.append((rnd, 'create', str(exc)))
        finally:
            if qp_obj is not None:
                try:
                    close_verbs_qp_guarded(qp_obj)
                except Exception:
                    pass
    return ok_count, fail_list
