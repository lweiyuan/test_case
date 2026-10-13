#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基于 005_001 模板生成 002-014 Reserved QPN 场景脚本。"""
import re
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
TEMPLATE = SRC_DIR / (
    'nic_linux_rdma_devx_f_06_53_005_001_devx_create_qpn_normal_create_qpn.py'
)
if not TEMPLATE.exists():
    raise FileNotFoundError(f'模板文件不存在: {TEMPLATE}')

SCENARIOS = [
    {
        'suffix': '002',
        'scene': 'abnormal',
        'scene_cn': '异常创建',
        'description': '验证错误 obj_type、超范围 log_obj_range 等异常参数会被固件拒绝。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 创建 Mlx5Context；\\n'"
            "        '3. 查询并确认设备支持 Reserved QPN；\\n'"
            "        '4. 使用错误 obj_type 尝试创建 block，期望失败；\\n'"
            "        '5. 使用超范围 log_obj_range 尝试创建 block，期望失败；\\n'"
            "        '6. 使用非 CREATE_GENERAL_OBJECT opcode 尝试创建，期望失败；\\n'"
            "        '7. 释放资源并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 异常参数测试。')\\n"
            "        bad_cases = [\\n"
            "            (0xa00, 0xff01, 0, '错误 obj_type'),\\n"
            "            (0xa00, 0x002c, 31, '超范围 log_obj_range'),\\n"
            "            (0x500, 0x002c, 0, '错误 opcode'),\\n"
            "        ]\\n"
            "        for opcode, obj_type, log_range, reason in bad_cases:\\n"
            "            status, result = cls._ipvbs.exec_and_get_ipvbs_result(\\n"
            "                f\"glb_helper.try_create_reserved_qpn_raw(\"\\n"
            "                f\"glb_mlx5_ctx, {opcode}, {obj_type}, {log_range})\")\\n"
            "            result = (result or '').strip()\\n"
            "            if status == IpvbsStatusEnum.SUCCESS.value and result == 'OK':\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'{reason} 未返回失败: {result}')\\n"
            "                return\\n"
            "            log.info(f'{reason} 正确返回失败: {result}')"
        ),
    },
    {
        'suffix': '003',
        'scene': 'stress',
        'scene_cn': '压力创建',
        'description': '连续创建/销毁大量 Reserved QPN block，验证 first_qpn 不重复且无资源泄漏。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 创建 Mlx5Context；\\n'"
            "        '3. 循环创建 100 个 log_obj_range=0 的 block 并立即释放；\\n'"
            "        '4. 检查所有 first_qpn 唯一；\\n'"
            "        '5. 再次批量创建 20 个 block，确认仍可成功；\\n'"
            "        '6. 释放全部 block 并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 压力测试。')\\n"
            "        total = 100\\n"
            "        first_qpns = []\\n"
            "        for i in range(total):\\n"
            "            name = f'obj_qpn_stress_{i}'\\n"
            "            status, first_qpn = cls._create_qpn_block(name, 0)\\n"
            "            if status != IpvbsStatusEnum.SUCCESS.value or not first_qpn:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'压力测试第 {i + 1}/{total} 次创建失败')\\n"
            "                return\\n"
            "            first_qpns.append(first_qpn)\\n"
            "            cls._close_qpn_block(name)\\n"
            "        if len(set(first_qpns)) != total:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'{total} 次创建的 first_qpn 出现重复')\\n"
            "            return\\n"
            "        log.info(f'压力测试完成，{total} 个 block first_qpn 唯一')\\n"
            "        batch2 = 20\\n"
            "        batch2_names = []\\n"
            "        for i in range(batch2):\\n"
            "            name = f'obj_qpn_stress2_{i}'\\n"
            "            status, first_qpn = cls._create_qpn_block(name, 0)\\n"
            "            if status != IpvbsStatusEnum.SUCCESS.value or not first_qpn:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'资源可用性批量创建第 {i + 1}/{batch2} 个失败')\\n"
            "                return\\n"
            "            batch2_names.append(name)\\n"
            "        log.info(f'资源可用性验证通过，{batch2} 个 block 创建成功')\\n"
            "        for name in batch2_names:\\n"
            "            cls._close_qpn_block(name)"
        ),
    },
    {
        'suffix': '004',
        'scene': 'boundary',
        'scene_cn': '边界创建',
        'description': '验证 log_obj_range=0（1 个 QPN）和最大支持粒度均能成功。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 创建 Mlx5Context；\\n'"
            "        '3. 查询设备支持的最大 log_obj_range；\\n'"
            "        '4. 使用 log_obj_range=0 创建 block，验证成功；\\n'"
            "        '5. 使用最大 log_obj_range 创建 block，验证成功；\\n'"
            "        '6. 释放 block 并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 边界测试。')\\n"
            "        status, first_qpn = cls._create_qpn_block('obj_qpn_min', 0)\\n"
            "        if status != IpvbsStatusEnum.SUCCESS.value or not first_qpn:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('log_obj_range=0 创建失败')\\n"
            "            return\\n"
            "        if cls._max_log_range <= 0:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('未能探测到有效的最大 log_obj_range')\\n"
            "            return\\n"
            "        status, first_qpn = cls._create_qpn_block(\\n"
            "            'obj_qpn_max', cls._max_log_range)\\n"
            "        if status != IpvbsStatusEnum.SUCCESS.value or not first_qpn:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'max_log_range={cls._max_log_range} 创建失败')\\n"
            "            return\\n"
            "        log.info(f'边界测试通过: max_log_range={cls._max_log_range}')"
        ),
    },
    {
        'suffix': '005',
        'scene': 'cross_device',
        'scene_cn': '跨设备创建',
        'description': '在 mlx5_0 和 mlx5_1 上分别创建 block，验证 QPN 范围独立。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 在 mlx5_0 上创建 Mlx5Context 并分配 block；\\n'"
            "        '3. 在 mlx5_1 上创建 Mlx5Context 并分配 block；\\n'"
            "        '4. 验证两个设备返回的 first_qpn 均有效且不相同；\\n'"
            "        '5. 释放 block 并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 跨设备测试。')\\n"
            "        other_dev = 'mlx5_1' if cls._rdma_dev == 'mlx5_0' else 'mlx5_0'\\n"
            "        if not cls._do_create_on_device(\\n"
            "                cls._rdma_dev, 'obj_qpn_dev0', 'obj_qpn_dev0_first', 'ctx_qpn_dev0'):\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'在 {cls._rdma_dev} 上创建 block 失败')\\n"
            "            return\\n"
            "        if not cls._do_create_on_device(\\n"
            "                other_dev, 'obj_qpn_dev1', 'obj_qpn_dev1_first', 'ctx_qpn_dev1'):\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'在 {other_dev} 上创建 block 失败')\\n"
            "            return\\n"
            "        status0, first0 = cls._ipvbs.exec_and_get_ipvbs_result(\\n"
            "            'str(obj_qpn_dev0_first)')\\n"
            "        status1, first1 = cls._ipvbs.exec_and_get_ipvbs_result(\\n"
            "            'str(obj_qpn_dev1_first)')\\n"
            "        if status0 != IpvbsStatusEnum.SUCCESS.value or status1 != IpvbsStatusEnum.SUCCESS.value:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('跨设备创建 Reserved QPN 失败')\\n"
            "            return\\n"
            "        if first0.strip() == first1.strip():\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'跨设备 first_qpn 相同: {first0}')\\n"
            "            return\\n"
            "        log.info(f'跨设备测试通过: {cls._rdma_dev}={first0}, {other_dev}={first1}')\\n"
            "        for _cleanup_cmd in [\\n"
            "            'glb_helper.destroy_reserved_qpn(obj_qpn_dev0)',\\n"
            "            'glb_helper.destroy_reserved_qpn(obj_qpn_dev1)',\\n"
            "            'ctx_qpn_dev0.close()',\\n"
            "            'ctx_qpn_dev1.close()',\\n"
            "        ]:\\n"
            "            _s, _r = cls._ipvbs.exec_and_get_ipvbs_result(_cleanup_cmd)\\n"
            "            if _s != IpvbsStatusEnum.SUCCESS.value:\\n"
            "                log.warning(f'跨设备清理失败: {_cleanup_cmd}, rtn={_r}')"
        ),
    },
    {
        'suffix': '006',
        'scene': 'context_rebuild',
        'scene_cn': '上下文重建',
        'description': '销毁并重建 Mlx5Context 后，Reserved QPN 仍可正常分配。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 创建 Mlx5Context 并分配 block，记录 first_qpn；\\n'"
            "        '3. 关闭当前 Mlx5Context；\\n'"
            "        '4. 重新创建 Mlx5Context；\\n'"
            "        '5. 再次分配 block，验证成功；\\n'"
            "        '6. 释放 block 并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 上下文重建测试。')\\n"
            "        status, first_qpn0 = cls._create_qpn_block('obj_qpn_before', 0)\\n"
            "        if status != IpvbsStatusEnum.SUCCESS.value:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('重建前创建 block 失败')\\n"
            "            return\\n"
            "        cmds = [\\n"
            "            'glb_mlx5_ctx.close()',\\n"
            "            f\"glb_mlx5_ctx = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '{cls._rdma_dev}')\",\\n"
            "        ]\\n"
            "        for cmd in cmds:\\n"
            "            s, r = cls._ipvbs.exec_and_get_ipvbs_result(cmd)\\n"
            "            if s != IpvbsStatusEnum.SUCCESS.value:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'上下文重建失败: {cmd}, {r}')\\n"
            "                return\\n"
            "        status, first_qpn1 = cls._create_qpn_block('obj_qpn_after', 0)\\n"
            "        if status != IpvbsStatusEnum.SUCCESS.value:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('重建后创建 block 失败')\\n"
            "            return\\n"
            "        log.info(f'上下文重建测试通过: before={first_qpn0}, after={first_qpn1}')"
        ),
    },
    {
        'suffix': '007',
        'scene': 'long_term_stability',
        'scene_cn': '长期稳定性',
        'description': '长时间循环申请/释放 Reserved QPN，验证无泄漏和重复。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 持续运行 300 轮：创建 5 个 block 后全部释放；\\n'"
            "        '3. 每轮检查 first_qpn 集合无交集；\\n'"
            "        '4. 释放资源并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 长期稳定性测试。')\\n"
            "        rounds = 300\\n"
            "        all_qpns = set()\\n"
            "        for r in range(rounds):\\n"
            "            round_qpns = []\\n"
            "            for i in range(5):\\n"
            "                name = f'obj_qpn_lt_{r}_{i}'\\n"
            "                status, first_qpn = cls._create_qpn_block(name, 0)\\n"
            "                if status != IpvbsStatusEnum.SUCCESS.value:\\n"
            "                    cls.set_bug_type('功能问题')\\n"
            "                    cls.create_bug(f'第 {r} 轮第 {i} 个 block 创建失败')\\n"
            "                    return\\n"
            "                round_qpns.append(first_qpn)\\n"
            "            overlap = all_qpns.intersection(set(round_qpns))\\n"
            "            if overlap:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'发现重复 first_qpn: {overlap}')\\n"
            "                return\\n"
            "            all_qpns.update(round_qpns)\\n"
            "            for i in range(5):\\n"
            "                cls._close_qpn_block(f'obj_qpn_lt_{r}_{i}')\\n"
            "        log.info(f'长期稳定性测试通过，共 {rounds} 轮')"
        ),
    },
    {
        'suffix': '008',
        'scene': 'multi_context',
        'scene_cn': '多上下文',
        'description': '同一设备上多个 Mlx5Context 分别申请 Reserved QPN，互不冲突。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 创建 3 个独立的 Mlx5Context；\\n'"
            "        '3. 每个 context 分配 block；\\n'"
            "        '4. 验证所有 first_qpn 唯一；\\n'"
            "        '5. 释放 block 并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 多上下文测试。')\\n"
            "        contexts = 3\\n"
            "        first_qpns = []\\n"
            "        for i in range(contexts):\\n"
            "            cmds = [\\n"
            "                f\"glb_ctx_{i} = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '{cls._rdma_dev}')\",\\n"
            "                f\"glb_ret_{i} = glb_helper.create_reserved_qpn(glb_ctx_{i}, 0)\",\\n"
            "                f\"glb_obj_{i} = glb_ret_{i}[0]\",\\n"
            "                f\"glb_first_{i} = glb_ret_{i}[1]\",\\n"
            "            ]\\n"
            "            for cmd in cmds:\\n"
            "                s, r = cls._ipvbs.exec_and_get_ipvbs_result(cmd)\\n"
            "                if s != IpvbsStatusEnum.SUCCESS.value:\\n"
            "                    cls.set_bug_type('功能问题')\\n"
            "                    cls.create_bug(f'上下文 {i} 创建 block 失败: {r}')\\n"
            "                    return\\n"
            "            status, first_qpn = cls._ipvbs.exec_and_get_ipvbs_result(\\n"
            "                f'str(glb_first_{i})')\\n"
            "            first_qpns.append(first_qpn.strip())\\n"
            "        if len(set(first_qpns)) != contexts:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'多上下文 first_qpn 不唯一: {first_qpns}')\\n"
            "            return\\n"
            "        for i in range(contexts):\\n"
            "            cls._ipvbs.exec_and_get_ipvbs_result(f'glb_obj_{i}.close()')\\n"
            "            cls._ipvbs.exec_and_get_ipvbs_result(f'glb_ctx_{i}.close()')\\n"
            "        log.info(f'多上下文测试通过: {first_qpns}')"
        ),
    },
    {
        'suffix': '009',
        'scene': 'lifecycle_anomaly',
        'scene_cn': '生命周期异常',
        'description': '验证 block 被销毁后，其 QPN 不可再次使用/关联。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 创建 block 并记录 first_qpn；\\n'"
            "        '3. 销毁该 block；\\n'"
            "        '4. 再次创建新 block，验证新 first_qpn 与旧值不同；\\n'"
            "        '5. 释放资源并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 生命周期异常测试。')\\n"
            "        status, first_qpn0 = cls._create_qpn_block('obj_qpn_life', 0)\\n"
            "        if status != IpvbsStatusEnum.SUCCESS.value:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('生命周期测试初始创建失败')\\n"
            "            return\\n"
            "        cls._close_qpn_block('obj_qpn_life')\\n"
            "        status, first_qpn1 = cls._create_qpn_block('obj_qpn_life2', 0)\\n"
            "        if status != IpvbsStatusEnum.SUCCESS.value:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('销毁后重新创建 block 失败')\\n"
            "            return\\n"
            "        if first_qpn0 == first_qpn1:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'销毁后分配了相同 first_qpn: {first_qpn1}')\\n"
            "            return\\n"
            "        log.info(f'生命周期异常测试通过: {first_qpn0} -> {first_qpn1}')"
        ),
    },
    {
        'suffix': '010',
        'scene': 'alloc_pattern',
        'scene_cn': '分配模式',
        'description': '按 1/2/4/8 等典型 block 大小创建，验证均成功。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 依次使用 log_obj_range=0,1,2,3 创建 block；\\n'"
            "        '3. 验证每个 block 的 first_qpn 有效且互不相同；\\n'"
            "        '4. 释放 block 并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 分配模式测试。')\\n"
            "        ranges = [0, 1, 2, 3]\\n"
            "        first_qpns = []\\n"
            "        for log_range in ranges:\\n"
            "            name = f'obj_qpn_pattern_{log_range}'\\n"
            "            status, first_qpn = cls._create_qpn_block(name, log_range)\\n"
            "            if status != IpvbsStatusEnum.SUCCESS.value or not first_qpn:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'log_obj_range={log_range} 创建失败')\\n"
            "                return\\n"
            "            first_qpns.append(first_qpn)\\n"
            "        if len(set(first_qpns)) != len(ranges):\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'不同 log_range 的 first_qpn 重复: {first_qpns}')\\n"
            "            return\\n"
            "        log.info(f'分配模式测试通过: {first_qpns}')"
        ),
    },
    {
        'suffix': '011',
        'scene': 'random_order',
        'scene_cn': '随机顺序',
        'description': '随机创建/销毁不同大小 block，验证无冲突。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 随机生成 20 个 log_obj_range（0~3）；\\n'"
            "        '3. 随机顺序创建/销毁 block；\\n'"
            "        '4. 验证所有 first_qpn 唯一；\\n'"
            "        '5. 释放资源并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 随机顺序测试。')\\n"
            "        random.seed(42)\\n"
            "        first_qpns = []\\n"
            "        ops = []\\n"
            "        for i in range(20):\\n"
            "            log_range = random.randint(0, min(3, cls._max_log_range))\\n"
            "            ops.append((i, log_range))\\n"
            "        for i, log_range in ops:\\n"
            "            name = f'obj_qpn_rand_{i}'\\n"
            "            status, first_qpn = cls._create_qpn_block(name, log_range)\\n"
            "            if status != IpvbsStatusEnum.SUCCESS.value:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'随机创建 {name} 失败')\\n"
            "                return\\n"
            "            first_qpns.append(first_qpn)\\n"
            "        random.shuffle(ops)\\n"
            "        for i, _ in ops:\\n"
            "            cls._close_qpn_block(f'obj_qpn_rand_{i}')\\n"
            "        if len(set(first_qpns)) != len(first_qpns):\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'随机顺序测试 first_qpn 重复: {first_qpns}')\\n"
            "            return\\n"
            "        log.info('随机顺序测试通过')"
        ),
    },
    {
        'suffix': '012',
        'scene': 'out_view_check',
        'scene_cn': '返回缓冲区校验',
        'description': '校验 CREATE_GENERAL_OBJECT 输出 buffer 的 status/syndrome/obj_id 格式。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 创建 block；\\n'"
            "        '3. 读取 out_view 的字节 0（status）、4-7（syndrome）、8-11（obj_id）；\\n'"
            "        '4. 验证 status=0、syndrome=0、obj_id 非 0；\\n'"
            "        '5. 释放 block 并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 返回缓冲区校验。')\\n"
            "        status, first_qpn = cls._create_qpn_block('obj_qpn_out', 0)\\n"
            "        if status != IpvbsStatusEnum.SUCCESS.value:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('out_view 校验时创建 block 失败')\\n"
            "            return\\n"
            "        check_cmds = [\\n"
            "            \"list(glb_obj_qpn_out.out_view[:16])\",\\n"
            "            \"glb_obj_qpn_out.out_view[0]\",\\n"
            "            \"glb_struct.unpack('>I', glb_obj_qpn_out.out_view[4:8])[0]\",\\n"
            "            \"glb_struct.unpack('>I', glb_obj_qpn_out.out_view[8:12])[0]\",\\n"
            "        ]\\n"
            "        results = []\\n"
            "        for cmd in check_cmds:\\n"
            "            s, r = cls._ipvbs.exec_and_get_ipvbs_result(cmd)\\n"
            "            if s != IpvbsStatusEnum.SUCCESS.value:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'读取 out_view 失败: {cmd}')\\n"
            "                return\\n"
            "            results.append(r.strip())\\n"
            "        out_status = int(results[1])\\n"
            "        out_syndrome = int(results[2])\\n"
            "        out_obj_id = int(results[3])\\n"
            "        if out_status != 0 or out_syndrome != 0 or out_obj_id == 0:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'out_view 字段异常: status={out_status}, '\\n"
            "                           f'syndrome={out_syndrome}, obj_id={out_obj_id}')\\n"
            "            return\\n"
            "        log.info(f'out_view 校验通过: obj_id={out_obj_id}')"
        ),
    },
    {
        'suffix': '013',
        'scene': 'cross_device_alternating_stress',
        'scene_cn': '跨设备交替压力',
        'description': '在 mlx5_0 与 mlx5_1 之间交替创建/释放 block。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 交替在两个 device 上创建 block；\\n'"
            "        '3. 验证所有 first_qpn 唯一；\\n'"
            "        '4. 交替释放 block；\\n'"
            "        '5. 清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 跨设备交替压力测试。')\\n"
            "        devs = [cls._rdma_dev, 'mlx5_1' if cls._rdma_dev == 'mlx5_0' else 'mlx5_0']\\n"
            "        first_qpns = []\\n"
            "        ctx_names = []\\n"
            "        for i in range(20):\\n"
            "            dev = devs[i % 2]\\n"
            "            name = f'obj_qpn_alt_{i}'\\n"
            "            ctx_name = f'ctx_qpn_alt_{i}'\\n"
            "            if not cls._do_create_on_device(dev, name, f'{name}_first', ctx_name):\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'交替创建 {name} 失败')\\n"
            "                return\\n"
            "            ctx_names.append(ctx_name)\\n"
            "            status, first_qpn = cls._ipvbs.exec_and_get_ipvbs_result(\\n"
            "                f'str({name}_first)')\\n"
            "            if status != IpvbsStatusEnum.SUCCESS.value:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'读取 {name} first_qpn 失败')\\n"
            "                return\\n"
            "            first_qpns.append(first_qpn.strip())\\n"
            "        if len(set(first_qpns)) != len(first_qpns):\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug(f'交替压力 first_qpn 重复: {first_qpns}')\\n"
            "            return\\n"
            "        log.info('跨设备交替压力测试通过')\\n"
            "        for i in range(20):\\n"
            "            name = f'obj_qpn_alt_{i}'\\n"
            "            ctx_name = ctx_names[i]\\n"
            "            for _cleanup_cmd in [\\n"
            "                f'glb_helper.destroy_reserved_qpn({name})',\\n"
            "                f'{ctx_name}.close()',\\n"
            "            ]:\\n"
            "                _s, _r = cls._ipvbs.exec_and_get_ipvbs_result(_cleanup_cmd)\\n"
            "                if _s != IpvbsStatusEnum.SUCCESS.value:\\n"
            "                    log.warning(f'交替压力清理失败: {_cleanup_cmd}, rtn={_r}')"
        ),
    },
    {
        'suffix': '014',
        'scene': 'property_access_stability',
        'scene_cn': '属性访问稳定性',
        'description': '反复读取 block 的 first_qpn，验证值稳定。',
        'test_steps': (
            "        '1. 初始化 RDMA 环境并建立 ipvbs 会话；\\n'"
            "        '2. 创建 block；\\n'"
            "        '3. 连续 100 次读取 first_qpn；\\n'"
            "        '4. 验证每次读取结果一致；\\n'"
            "        '5. 释放 block 并清理环境。'"
        ),
        'do_body': (
            "        log.info('do: DevX Reserved QPN 属性访问稳定性测试。')\\n"
            "        status, first_qpn = cls._create_qpn_block('obj_qpn_prop', 0)\\n"
            "        if status != IpvbsStatusEnum.SUCCESS.value or not first_qpn:\\n"
            "            cls.set_bug_type('功能问题')\\n"
            "            cls.create_bug('属性稳定性测试创建 block 失败')\\n"
            "            return\\n"
            "        read_count = 100\\n"
            "        for i in range(read_count):\\n"
            "            s, r = cls._ipvbs.exec_and_get_ipvbs_result(\\n"
            "                'str(glb_obj_qpn_prop_first)')\\n"
            "            if s != IpvbsStatusEnum.SUCCESS.value:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'第 {i} 次读取 first_qpn 失败')\\n"
            "                return\\n"
            "            if r.strip() != first_qpn:\\n"
            "                cls.set_bug_type('功能问题')\\n"
            "                cls.create_bug(f'第 {i} 次读取 first_qpn 不一致: '\\n"
            "                               f'期望 {first_qpn}, 实际 {r.strip()}')\\n"
            "                return\\n"
            "        log.info(f'属性访问稳定性测试通过，{read_count} 次读取一致')\\n"
            "        cls._close_qpn_block('obj_qpn_prop')"
        ),
    },
]


def generate():
    template_text = TEMPLATE.read_text(encoding='utf-8')
    for scenario in SCENARIOS:
        suffix = scenario['suffix']
        scene = scenario['scene']
        scene_cn = scenario['scene_cn']
        src_case_id = '005_001'
        dst_case_id = f'005_{suffix}'
        class_name_old = 'NicLinuxRdmaDevxF0653005001PfCreateQpnNormalCreateQpn'
        class_name_new = (
            f'NicLinuxRdmaDevxF0653005{suffix}PfCreateQpn{scene.title()}CreateQpn'
        )

        text = template_text
        text = text.replace(src_case_id, dst_case_id)
        text = text.replace(class_name_old, class_name_new)
        # 仅替换模板中保留的 _do_normal_create_qpn 辅助方法名，
        # 避免对任意 _normal_ 文本做全局替换。
        text = text.replace(
            '_do_normal_create_qpn', f'_do_{scene}_create_qpn')
        text = re.sub(
            r"case_title = \('.*?'\n\s*'.*?'\n\s*\)",
            f"case_title = ('RDMA DevX 接口测试_用户态_PF_devx_obj_create_"
            f"ReservedQPN创建_{scene_cn}ReservedQPN')",
            text,
            flags=re.DOTALL,
        )
        text = re.sub(
            r"description:\s+RDMA DevX 接口测试_用户态_PF_devx_obj_create_"
            r"ReservedQPN创建_正常创建ReservedQPN.*\n\n",
            f"description:   RDMA DevX 接口测试_用户态_PF_devx_obj_create_"
            f"ReservedQPN创建_{scene_cn}ReservedQPN\n\n"
            f"               {scenario['description']}\n\n",
            text,
        )
        text = re.sub(
            r"    test_steps = \(\n.*?    \)",
            lambda m: f"    test_steps = (\n{scenario['test_steps']}\n    )",
            text,
            flags=re.DOTALL,
        )
        # 替换 do() 方法体。假设 do() 与 post() 之间由 @classmethod 分隔，
        # 且 do() 定义在类缩进层级（4 个空格）。允许二者之间有可变空行。
        text = re.sub(
            r"    @classmethod\s*\n\s*def do\(cls\)\s*->\s*None:\s*\n.*?\n\s*@classmethod\s*\n\s*def post",
            f"    @classmethod\n    def do(cls) -> None:\n{scenario['do_body']}\n\n    @classmethod\n    def post",
            text,
            flags=re.DOTALL,
        )

        # 跨设备相关脚本需要 _do_create_on_device 辅助方法；若模板没有则追加
        if scene in ('cross_device', 'cross_device_alternating_stress'):
            helper_method = '''
    @classmethod
    def _do_create_on_device(cls, dev: str, obj_name: str,
                             first_name: str, ctx_name: str) -> bool:
        cmds = [
            f"{ctx_name} = glb_Mlx5Context(glb_Mlx5DVContextAttr(), '{dev}')",
            f"glb_ret_tmp = glb_helper.create_reserved_qpn({ctx_name}, 0)",
            f"{obj_name} = glb_ret_tmp[0]",
            f"{first_name} = glb_ret_tmp[1]",
        ]
        for cmd in cmds:
            s, r = cls._ipvbs.exec_and_get_ipvbs_result(cmd)
            if s != IpvbsStatusEnum.SUCCESS.value:
                log.error(f'在 {dev} 上创建 block 失败: {cmd}, {r}')
                return False
        return True
'''
            if 'def _do_create_on_device' not in text:
                text = text.replace(
                    'if __name__ == \'__main__\':',
                    helper_method + '\n\nif __name__ == \'__main__\':' 
                )

        if scene == 'random_order':
            text = text.replace(
                'import add_syspath\n\n',
                'import add_syspath\nimport random\n\n')

        out_name = (
            f'nic_linux_rdma_devx_f_06_53_{dst_case_id}_devx_create_qpn_'
            f'{scene}_create_qpn.py'
        )
        out_path = SRC_DIR / out_name
        if out_path.exists():
            print(f'Warning: overwriting existing generated script: {out_path}')
        out_path.write_text(text, encoding='utf-8')
        print(f'Generated {out_path}')


if __name__ == '__main__':
    generate()
