## Why

物流规则的"体积重量计费方式"存在三个问题需要修复：
1. **前端 UI 缺失条件字段**：选择"最长边超过阈值时按体积重量计费"后，不会显示"最长边阈值(cm)"和"体积重量系数"输入框，用户无法配置阈值参数。同时前端表单值 `"threshold"` 与后端定价引擎期望的 `"longest_side"` 不一致，导致该模式在定价计算中从未生效。
2. **缺少"三边和超过阈值"模式**：需要新增"三边和超过阈值时按体积重量计费"模式——当产品长+宽+高超过指定阈值时，按体积重量计费。
3. **FBP XLSX 导入未解析"Sum of sides"模式**：导入 FBP 表格时，S 列出现 "Sum of sides ≤ 90 cm - physical weight, Sum of sides > 90 cm - volumetric weight" 格式的内容，当前解析器未识别这种模式，未正确设置 volume_mode、阈值和体积系数。添加到"我的物流规则"后也必须正确传递这些字段。

## What Changes

- **修复"最长边超过阈值"模式 UI**：当 volume_mode 选择 `"longest_side"` 时，条件渲染"最长边阈值(cm)"和"体积重量系数"输入框。修复前端表单值从 `"threshold"` 改为 `"longest_side"`，与后端定价引擎一致。
- **新增"三边和超过阈值"模式**：
  - 数据库：在 logistics 和 logistics_pool 表新增 `sum_of_sides_threshold` (int, default 0) 字段
  - 后端定价引擎：`_calc_volume_weight` 和 `_filter_check_weight` 新增 `"sum_of_sides"` 分支
  - 前端：新增下拉选项"三边和超过阈值时按体积重量计费"，条件渲染"三边和阈值(cm)"和"体积重量系数"
  - API schema：新增 `sum_of_sides_threshold` 字段
- **FBP 导入解析"Sum of sides"模式**：
  - 解析器识别 S 列 "Sum of sides ≤ X cm" 格式，提取阈值 X
  - 设置 volume_mode 为 `"sum_of_sides"`，sum_of_sides_threshold 为 X，volume_coefficient 从 T 列解析
  - "添加到我的物流规则"时正确传递所有字段

## Capabilities

### New Capabilities
- `sum-of-sides-volume-mode`: 三边和超过阈值时按体积重量计费模式，包含定价计算、过滤逻辑、UI 和 XLSX 导入解析

### Modified Capabilities
- `longest-side-volume-mode`: 修复前端值名称不一致（threshold → longest_side）及条件字段缺失

## Impact

- **数据库**: 需要 Alembic 迁移为两个表添加 `sum_of_sides_threshold` 列
- **后端**: `pricing/logistic_cost.py`, `pricing/filter.py` 增加新计算分支
- **前端**: `LogisticsPage.jsx` 修改 Select 值和增加条件渲染字段
- **XLSX 导入**: `xlsx_import/parsers/fbp.py` 增加 "Sum of sides" 模式解析
- **API**: `api/models/schemas.py` 增加新字段
- **测试**: 单元测试 + E2E 测试覆盖所有变更
