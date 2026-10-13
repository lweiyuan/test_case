# excel测试用例文件夹

本目录用于统一存放自动生成的 Excel 测试用例。

## 组织规则

1. 所有生成的测试用例统一放在本目录下。
2. 以生成时间建立子目录，命名格式：`YYYY-MM-DD_HH-MM-SS`。
3. 同一批次生成的多个 Excel 文件放入同一个时间子目录。
4. 原始输入文件（如 .xmind、源 .xlsx）不要放入本目录。

## 示例

```
excel测试用例文件夹/
├── README.md
├── .gitkeep
├── 2026-07-15_09-57-00/
│   ├── 天鹰VLAN测试用例.xlsx
│   └── MultiHost_RoCE_TestCases.xlsx
└── 2026-07-14_15-35-00/
    └── 天鹰VLAN测试用例.xlsx
```
