---
name: 测试用例生成
description: 指导如何根据Excel测试用例、XMind测试点、需求文档或现有代码模式，在NIC100框架中生成规范的Python测试脚本。
---

# NIC100 测试用例生成指南

## 输入来源

- Excel 测试用例文件（如项目根目录的 `多PF测试-测试用例.xlsx`）
- XMind 测试点
- 需求文档或手工测试步骤
- 现有代码模式与模块依赖关系

## 输出位置

- 通用用例：`ps3/test/esat/nic100/scripts/`
- 模块用例：`ps3/test/esat/nic100/scripts/nic100/linux/<模块>/`
- 生成配置：`ps3/test/esat/nic100/scripts/generate_scripts.xlsx`

## 生成原则

1. **一个用例一个 .py 文件**
2. **不复写已有基类**，只继承使用
3. **脚本名与用例编号对应**，如 `multi_pf_test_tc002.py`
4. **遵循项目既有代码风格**
5. **包含 prepare / do / post 三阶段**

## 转换步骤

### 从 Excel 转换

1. 读取 Excel 中的“测试步骤”、“预期结果”、“前置条件”
2. 将步骤映射为 `do()` 中的函数调用
3. 将预期结果映射为断言或结果检查
4. 将前置条件映射为 `prepare()`
5. 将环境恢复映射为 `post()`

### 从 XMind 转换

1. 将根节点作为模块/特性
2. 子节点作为测试点
3. 叶子节点作为具体用例
4. 优先生成命令级步骤明确的用例

### 从现有代码模式生成

适用于没有现成 Excel/XMind，需要根据相似模块或历史脚本生成新脚本的场景。

1. **扫描项目结构**
   - 使用 `framework/biz/case_script_file_create.py` 或 `scripts/analyze_dependencies.py`
   - 识别目标模块目录下的现有脚本
   - 梳理模块间 import 依赖关系（参考「网卡测试框架」skill 的依赖分析部分）

2. **分析参考脚本**
   - 提取类结构、继承关系、方法划分
   - 梳理 import 依赖
   - 总结该模块常用的命令封装和断言模式

3. **确定新脚本边界**
   - 明确用例编号、模块归属、前置条件、测试步骤、预期结果
   - 对照相似脚本，避免遗漏 `post` 清理

4. **生成并裁剪**
   - 基于参考脚本生成模板，可使用模板生成器：
     ```bash
     python scripts/generate_script_template.py \
       --module-name "new_feature" \
       --output-dir "./new_scripts" \
       --based-on "existing_similar_module"
     ```
   - 生成器会分析参考模块的结构和样式，自动处理导入语句
   - 删除与本次用例无关的逻辑
   - 替换用例编号、设备名、IP、LID 等变量
   - 按「缺陷自动记录」skill 的要求补充 Bug 记录代码

5. **验证依赖**
   - 检查 import 语句是否有效
   - 确认无循环依赖
   - 必要时运行语法检查：`python -m py_compile <script>.py`

## 脚本模板要素

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用例编号：xxx
模块：IB/RoCE/以太/DPDK
作者：xxx
日期：xxx
描述：xxx
"""

from script_libs.script_base import ScriptBase

class XxxTest(ScriptBase):
    @classmethod
    def prepare(cls):
        super().prepare()
        # 前置准备

    @classmethod
    def do(cls):
        # 测试步骤
        pass

    @classmethod
    def post(cls):
        # 环境清理
        super().post()

if __name__ == "__main__":
    XxxTest().run()
```

## 质量检查

生成后确认：

- [ ] 导入语句正确且无循环依赖
- [ ] 命令参数符合当前环境
- [ ] 包含超时和异常处理
- [ ] `post` 阶段能恢复环境
- [ ] 失败时按规范记录 Bug
- [ ] 变量 `$lid` 等已替换为实际获取逻辑

## 常用工具

- `framework/biz/case_script_file_create.py`：用例脚本生成
- `framework/biz/excel/bug_result_excel_handle.py`：Bug 结果 Excel 处理
- `framework/biz/excel/report_excel_create.py`：报告 Excel 生成
- 自定义代码扫描脚本：用于分析项目结构、模块依赖和参考脚本模式
