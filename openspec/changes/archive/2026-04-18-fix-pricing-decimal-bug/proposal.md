## Why

定价计算在处理 FBP 物流时崩溃，因为 `logistic_cost.py` 返回 `float` 类型的费用，而 `grouped_pricing.py` 使用 `Decimal` 类型，导致 `Decimal + float` 混合运算错误。同时，产品批量导入只支持 `.xlsx` 文件，不支持老旧的 `.xls` 格式。

## What Changes

1. **修复定价计算 Decimal 类型错误**
   - 修改 `logistic_cost.py` 中 `_calc_fee` 函数，确保 `base_fee`、`continue_fee`、`first_fee` 等字段正确转换为 `Decimal` 类型
   - 确保 `calculate_logistic_cost` 函数返回值始终是 `Decimal` 类型

2. **增加 xls 文件格式支持**
   - 在 `products.py` 的产品批量导入 API 中增加 `.xls` 文件支持
   - 安装 `xlrd` 依赖库用于读取 xls 格式
   - 根据文件后缀选择使用 `openpyxl`（xlsx）或 `xlrd`（xls）读取文件

## Capabilities

### New Capabilities
- `pricing-decimal-fix`: 修复定价计算中的 Decimal/float 类型混合问题

### Modified Capabilities
- `product-import`: 增加 xls 文件格式支持（扩展现有能力，非破坏性变更）

## Impact

### 定价计算
- 文件：`pricing/logistic_cost.py`（`_calc_fee` 函数）
- 文件：`pricing/cost_filter.py`（第 87 行）
- 影响：FBP 物流（fbp_ru、fbp_cis）分组计算，之前返回空结果

### 产品导入
- 文件：`api/routes/products.py`
- 依赖：需要安装 `xlrd>=2.0.0,<3.0.0`
- 影响：用户可使用老版本 Excel 文件（.xls 格式）导入产品数据
