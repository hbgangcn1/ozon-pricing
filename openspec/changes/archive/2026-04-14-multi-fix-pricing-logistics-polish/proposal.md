## Why

系统在定价计算、物流管理、UI体验等方面存在多项功能缺陷和体验问题，影响日常运营效率。具体包括：缺少盈亏平衡分析能力、精准模式页面设计粗糙、空数据误报错误、物流编辑表单冗余字段、筛选器失效、测试数据残留、精准模式计算404错误、以及物流限价币种不统一等问题。这些问题需要集中修复以提升系统可用性和计算准确性。

## What Changes

- **盈亏平衡线计算**：每次定价计算时额外执行一次运营利润率=0的计算，前端增加"盈亏平衡线"toggle切换展示两套结果，无需重新调用API
- **精准模式页面UI优化**：对精准模式(PricingPage.jsx)页面进行视觉打磨，重点改善佣金类目"管理"按钮的尺寸、显眼度和美观度
- **空数据错误提示修复**：公共物流池页面(LogisticsPoolPage.jsx)和佣金类目页面(CommissionCategoriesPage.jsx)在数据库无数据时不再弹出"获取失败"的错误信息
- **物流编辑表单简化**：移除物流规则编辑页面中的"送货方式"字段（送货上门、自提、未知），移除"FBP服务等级"下拉菜单（经确认不参与定价计算）
- **物流管理页面增强**：陆运/空运标签页显示对应规则数量；修复发货类型和目的国筛选器无效的问题
- **测试用户清理改进**：增强测试套件的用户清理机制，确保测试结束后不残留测试用户
- **精准模式404修复**：修复精准模式执行计算时返回"Not Found"的bug
- **物流限价币种统一** **BREAKING**：所有物流限价从卢布/美元改为人民币(CNY)，移除货币单位下拉菜单，标签改为"价格上限（元）"/"价格下限（元）"，更新定价计算逻辑确保币种正确，修改Excel导入机制只导入人民币限价列

## Capabilities

### New Capabilities
- `breakeven-pricing`: 盈亏平衡线定价计算 — 每次定价时额外计算运营利润率为0的结果，前端toggle切换展示
- `precise-mode-polish`: 精准模式页面UI打磨 — 视觉优化、佣金类目管理按钮改善
- `empty-state-handling`: 空数据状态处理 — 物流池和佣金类目页空数据时静默处理而非报错
- `logistics-form-cleanup`: 物流编辑表单简化 — 移除送货方式和FBP服务等级字段
- `logistics-page-enhancements`: 物流管理页面增强 — 标签页计数和筛选器修复
- `test-user-cleanup`: 测试用户清理机制改进 — 确保测试后无残留用户
- `precise-mode-404-fix`: 精准模式404错误修复 — 定位并修复计算时的Not Found错误
- `price-limit-cny-unification`: 物流限价人民币统一 — 数据库、前端、计算逻辑、Excel导入全面改为CNY

### Modified Capabilities

## Impact

- **前端**：PricingPage.jsx（盈亏平衡toggle + UI打磨）、LogisticsPage.jsx（标签计数 + 筛选器修复 + 编辑表单简化 + 限价币种）、LogisticsPoolPage.jsx（空数据处理 + 限价导入）、CommissionCategoriesPage.jsx（空数据处理）
- **后端API**：api/routes/pricing.py（盈亏平衡计算）、api/routes/logistics.py（移除送货方式/FBP服务等级字段、限价字段变更）
- **定价引擎**：pricing/calculate_pricing.py + pricing/filter.py + pricing/cost_filter.py（盈亏平衡计算、限价币种逻辑）
- **数据库**：logistics/logistics_pool表的限价字段变更（移除RUB/USD列，统一CNY）
- **Excel导入**：xlsx_import/parsers/（修改所有解析器只导入CNY限价列）
- **测试**：tests/conftest.py + conftest.py（增强用户清理）、相关测试文件
- **汇率服务**：enhanced_exchange_service.py（限价检查不再需要实时汇率转换）
