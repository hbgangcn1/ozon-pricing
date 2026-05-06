## Context

### 当前状态

定价计算在处理 FBP 物流时返回空结果。通过 E2E 测试发现错误：

```
ERROR: pricing.calculate_pricing: 计算定价时发生错误: unsupported operand type(s) for +: 'decimal.Decimal' and 'float'
```

**根本原因**：
- `pricing/grouped_pricing.py` 的 `_stage1_filter` 函数使用 `Decimal("0")` 作为默认值调用 `cost_and_filter`
- `pricing/cost_filter.py` 第 87 行：`base_cost_calc = unit_price + labeling_fee + shipping_fee + cost`
- `pricing/logistic_cost.py` 的 `calculate_logistic_cost` 返回的 `cost` 是 `float` 类型（来自数据库的 `base_fee`、`continue_fee` 字段）
- `Decimal + float` 混合运算导致 `TypeError`

### 问题代码路径

```
calculate_pricing_grouped()
  → _run_group("fbp", dest_filter, ...)
    → _group_fbp_cis(subset, group_product, mode, _split_logistics)
      → _stage1_filter()  ← 使用 Decimal
        → cost_and_filter()  ← cost 返回 float
          → 第 87 行 TypeError
```

### 约束

- 数据库中的物流数据字段（`base_fee`、`continue_fee` 等）是 `float` 类型
- API 返回时保持与数据库一致的类型
- `logistic_cost.py` 必须能处理 `float` 输入并输出 `Decimal`

## Goals / Non-Goals

**Goals:**
- 修复 `logistic_cost.py` 中 `calculate_logistic_cost` 函数，确保返回 `Decimal` 类型
- 确保 `cost_filter.py` 中的 `base_cost_calc` 计算不出现类型错误
- 增加 `.xls` 文件支持用于产品导入

**Non-Goals:**
- 不修改数据库 schema（字段类型保持 float）
- 不修改 FBP 物流导入逻辑
- 不修改 rFBS 物流计算逻辑（rFBS 正常工作）

## Decisions

### Decision 1: 修复 `logistic_cost.py` 的类型处理

**选项 A**: 在 `_calc_fee` 中将所有费用字段转换为 Decimal（推荐）
- 修改 `_calc_fee` 函数，将 `base_fee`、`continue_fee`、`first_fee` 显式转换为 `Decimal`
- 优点：最小改动，集中在单一函数
- 缺点：需要在多个地方添加 Decimal 转换

**选项 B**: 在 `calculate_logistic_cost` 入口处统一转换
- 将所有来自物流数据的 numeric 字段在入口处转换为 Decimal
- 优点：统一处理，避免遗漏
- 缺点：改动范围更大

**选择**: 选项 A - 在 `_calc_fee` 中转换，因为这是费用的最终计算点

### Decision 2: xls 文件支持

**选项 A**: 统一使用 `pandas.read_excel` 自动检测格式
- `pandas` 依赖 `xlrd` 读取 xls，依赖 `openpyxl` 读取 xlsx
- 优点：代码简洁，自动处理格式
- 缺点：增加 pandas 依赖

**选项 B**: 根据文件后缀分支处理
- `suffix == ".xlsx"`: 使用 `openpyxl`
- `suffix == ".xls"`: 使用 `xlrd` 直接读取
- 优点：显式控制，不依赖 pandas
- 缺点：需要两套读取逻辑

**选择**: 选项 B - 保持现有代码风格，只在必要时增加分支

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| xls 文件内容格式与 xlsx 不一致 | 错误处理时返回明确的错误信息 |
| xlrd 库版本兼容性问题 | 使用 `xlrd>=2.0.0,<3.0.0` 约束版本 |
| Decimal 转换精度损失 | 使用 `Decimal(str(value))` 避免浮点精度问题 |

## Migration Plan

1. 安装 `xlrd>=2.0.0,<3.0.0` 依赖
2. 修改 `pricing/logistic_cost.py` 的 `_calc_fee` 函数
3. 修改 `api/routes/products.py` 增加 xls 支持
4. 运行测试验证：`python -m pytest tests/ -v`
5. E2E 验证定价计算 FBP 分组显示正确

## Open Questions

无
