## 1. 数据库迁移基础

- [x] 1.1 更新 ORM 模型 `models/product.py`：所有价格/费用列从 `mapped_column(Float)` 改为 `mapped_column(Numeric(12, 4))`，包括 unit_price, labeling_fee, shipping_fee, promotion_cost_rate, target_profit_margin, commission_rate, withdrawal_fee_rate, payment_processing_fee, return_rate, vat_rate（cylinder_diameter, cylinder_length, battery_capacity_wh, battery_voltage 为物理量，保持 Float）
- [x] 1.2 更新 ORM 模型 `models/logistics.py`：price_limit, price_limit_rub, price_min, price_min_rub, price_limit_cny, price_min_cny, base_fee, first_fee, continue_fee 从 Float 改为 Numeric(12, 4)（volume_coefficient, battery_capacity_limit_wh, first_weight_g, continue_unit_g, min_weight, max_weight 为物理量，保持 Float）
- [x] 1.3 更新 ORM 模型 `models/logistics_pool.py`：与 logistics.py 对应的价格/费用列从 Float 改为 Numeric(12, 4)
- [x] 1.4 更新 ORM 模型 `models/commission_category.py`：fbp_tier1_rate, fbp_tier2_rate, fbp_tier3_rate, rfbs_tier1_rate, rfbs_tier2_rate, rfbs_tier3_rate 从 Float 改为 Numeric(12, 6)（费率需要更高精度）
- [x] 1.5 更新 ORM 模型 `models/config.py`：ExchangeRate.rate 从 Float 改为 Numeric(12, 6)
- [x] 1.6 创建 Alembic 迁移脚本：ALTER COLUMN ... TYPE NUMERIC(12,4/6) 覆盖上述所有表的列变更，包含 upgrade 和 downgrade

## 2. 数据库工具层迁移

- [x] 2.1 更新 `db/products.py`：`_FLOAT_DEFAULT_FIELDS` 的默认值从 `0.0` 改为 `Decimal('0')`, `_product_to_dict` 返回值中使用 Decimal，`batch_update_pricing_params` 接受 Decimal 参数
- [x] 2.2 更新 `db/logistics_crud.py`：create/update 函数中价格/费用字段处理改为 Decimal，`_logistics_to_dict` 返回 Decimal 值
- [x] 2.3 更新 `db/exchange.py`：`get_exchange_rate_fallback` 返回 `Optional[Decimal]`（移除 `float(value)` 转换），`update_exchange_rate_fallback` 参数类型从 `float` 改为 `Decimal`

## 3. 汇率服务迁移

- [x] 3.1 更新 `enhanced_exchange_service.py`：`get_fallback_exchange_rate()` 和 `get_fallback_usd_rate()` 返回 Decimal，内部兜底常量从 float 改为 Decimal（如 `Decimal('0.0904')`, `Decimal('7.2')`），`get_exchange_rate()` 和 `get_usd_rate()` 返回 Decimal，`update_fallback_rates` 接受 Decimal 参数，内部 `round()` 改为 `Decimal.quantize()`
- [x] 3.2 更新 `exchange_service.py`：确保导出的函数签名与返回类型与 enhanced_exchange_service 一致为 Decimal

## 4. Pricing 模块核心迁移（自底向上）

- [x] 4.1 迁移 `pricing/commission.py`：函数签名 float→Decimal，`float()` 转换改为 `Decimal(str())`，`round(x, 4)` 改为 `Decimal.quantize()`，阈值常量（1500, 5000）改为 Decimal，`fbp_rate + 0.01` 改为 Decimal 运算
- [x] 4.2 迁移 `pricing/logistic_cost.py`：所有 `float()` 转换改为 Decimal，`math.ceil(w / continue_unit)` 改为 Decimal 向上取整（`to_integral_value(ROUND_CEILING)`），返回类型 `Optional[float]` → `Optional[Decimal]`，数值字面量改为 Decimal
- [x] 4.3 迁移 `pricing/filter.py`：所有 `float()` 转换改为 Decimal，`math.ceil` 替换为 Decimal 向上取整，价格过滤计算使用 Decimal 算术
- [x] 4.4 迁移 `pricing/floating_price.py`：函数签名和返回类型 float→Decimal，迭代求解器中所有运算改为 Decimal，容差判断 `abs(...) < 0.001` 改为 `Decimal('0.001')` 比较，阈值常量（15, 10, 200, 0.02）改为 Decimal
- [x] 4.5 迁移 `pricing/final_price.py`：与 floating_price.py 同样处理，`round()` debug 调用改为 `Decimal.quantize()`，迭代收敛容差改为 Decimal
- [x] 4.6 迁移 `pricing/cost_filter.py`：`float()` 转换改为 Decimal，numerator/denominator 计算全部使用 Decimal 算术，函数签名 `cost_and_filter(unit_price: float, ...)` 改为 Decimal
- [x] 4.7 迁移 `pricing/profit.py`：函数签名 `calc_profit(price: float, cost: float, ...)` 全部改为 Decimal，利润率百分比计算使用 Decimal('100')，revenue_deductions 和 total_cost 计算使用 Decimal
- [x] 4.8 迁移 `pricing/select_best.py` 和 `pricing/fbp_stage3_select.py`：返回类型 `Optional[float]` → `Optional[Decimal]`，平均值计算使用 Decimal，成本格式化适配 Decimal
- [x] 4.9 迁移 `pricing/fbp_secondary_filter.py`：排序 key 中 `float()` 改为 Decimal
- [x] 4.10 迁移 `pricing/grouped_pricing.py`：所有 `float()` 转换改为 Decimal，margin 计算和 denom 计算使用 Decimal，字面量（0.2, 0.1, 0.3）改为 Decimal
- [x] 4.11 迁移 `pricing/calculate_pricing.py`：入口函数 `float()` 转换改为 Decimal，确保调用下游函数时传递 Decimal 值
- [x] 4.12 迁移 `pricing/_pricing_helpers.py`：兜底汇率常量改为 Decimal（`Decimal('0.0904')`, `Decimal('7.2')`），统计计算（avg_cost, cost_saving）使用 Decimal 算术
- [x] 4.13 迁移 `pricing/_result_helpers.py`：确认无需修改 — 仅传递值，不做 float() 转换，Decimal 值自然流过
- [x] 4.14 更新 `pricing/__init__.py` 和 `pricing/exchange_rate.py`：确认无需修改 — 仅 re-export，不涉及类型转换

## 5. API 层迁移

- [x] 5.1 更新 `api/models/schemas.py`：所有价格/费用/汇率相关字段从 `float` 改为 `Decimal`，添加 DecimalField 类型别名（PlainSerializer → float），确保 Pydantic v2 正确处理 Decimal 输入和输出
- [x] 5.2 移除 `api/routes/_pricing_helpers.py` 中的 `convert_decimals` 函数，更新 `format_result` 和 `build_breakdown` 中的 `round()` 为 Decimal.quantize()，添加 `_to_decimal()` 参数转换
- [x] 5.3 更新 `api/routes/pricing.py`：移除所有 `convert_decimals` 调用（6处），确保 pricing 模块返回的 Decimal 值直接传递给 Pydantic schema 序列化
- [x] 5.4 更新 `api/routes/statistics.py`：移除 `float()` 转换（如 `total_revenue = float(...)/100.0`），使用 Decimal 算术
- [x] 5.5 检查并更新 `api/routes/products.py` 和 `api/routes/logistics.py`：确认无需改动 — Decimal 值自然流过

## 6. 测试更新

- [x] 6.1 更新 pricing 核心测试：`tests/test_pricing_*.py`、`tests/test_commission*.py`、`tests/test_logistic_cost*.py`、`tests/test_floating_price*.py`、`tests/test_final_price*.py` — 所有 float 断言值改为 Decimal，mock 数据使用 Decimal
- [x] 6.2 更新 API 路由测试：`tests/test_api_routes*.py`、`tests/test_routes_pricing*.py`、`tests/test_pricing_format_result.py` — JSON 响应断言适配 Decimal 序列化后的数值
- [x] 6.3 更新 DB 层测试：`tests/test_db_*` 相关文件 — 产品/物流/汇率的 CRUD 测试使用 Decimal 输入和断言
- [x] 6.4 更新 conftest.py 中的测试夹具：产品/物流 fixture 数据中的 float 值改为 Decimal
- [x] 6.5 新增 Decimal 精度验证测试：验证迭代求解器（floating_price, final_price）在 Decimal 下的收敛行为，验证 Decimal.quantize 舍入正确性，验证 Decimal 序列化为 JSON number

## 7. 集成验证

- [x] 7.1 运行 flake8 确保零错误
- [x] 7.2 运行完整后端 pytest 套件（排除 test_e2e_volume_modes.py 和 test_xlsx_import.py），1592 测试全部通过
- [x] 7.3 运行前端 vitest 确保测试全部通过（234 passed）
- [x] 7.4 运行前端 eslint 确保零错误零警告
- [x] 7.5 运行 vite build 确保构建成功
- [x] 7.6 端到端验证：通过 API 调用定价接口，确认返回值为精确 Decimal 序列化的 JSON number（Products, Logistics, Statistics, CommissionCategories, Pricing 全部 JSON number ✅）
