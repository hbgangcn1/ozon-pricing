## Why

用户在实际使用过程中发现了多项 UI 精度问题、功能缺失、数据导入 bug 以及计算结果显示逻辑不合理等问题。这些问题直接影响日常操作效率和定价准确性，需要批量修复和改进。涵盖 8 个改动领域：物流规则编辑精度、产品编辑字段精简、物流池查看与导入修复、产品批量导入 bug、佣金管理默认值调整、计算结果页面重构、CIS 国家细分筛选、物流陆运/空运切换。

## What Changes

### 1. 物流规则编辑 - 精度与电池字段
- 价格上限 (`price_limit_cny`) 和价格下限 (`price_min_cny`) 在编辑时保留的小数位过多，需限制为 **2 位小数**（显示和编辑均生效）
- 勾选"允许电池"后，移除"电池容量限制(Wh)"字段的显示（`battery_wh_limit` 字段不再需要在 UI 中展示）

### 2. 产品编辑 - 精简电池与 MSDS 字段
- 在精准模式的电池区域和产品编辑弹窗中：
  - 移除"电池容量填写方式"单选组（`battery_capacity_type` radio）
  - 移除"容量(Wh)"、"容量(mAh)"、"电压(V)"三个输入字段
  - 移除"有 MSDS 证书"复选框
- 仅保留"含电池"复选框作为布尔标记

### 3. 公共物流池 - 查看详情功能
- 每条物流记录增加"查看"按钮
- 点击后弹出 Dialog 展示物流规则的全部字段（只读，不可编辑）

### 4. 物流池导入 - Bug 修复与功能增强
- **导入有时失败**：`xlsx_import` 的 `detect_format` 可能因文件格式不匹配抛异常（"无法识别xlsx格式"），需改善错误处理，返回更具体的错误信息
- **导入覆盖问题**：当前 `upsert` 可能替换已有数据，需改为追加模式（`insert` 而非 `upsert`），保留历史数据累积
- **新增"删除全部"按钮**：管理员可一键清空公共物流池，需二次确认

### 5. 产品批量导入 - 崩溃修复
- 导入 `定价与物流表不计抛.xlsx` 时前端崩溃显示"页面发生了意外错误"
- 需排查后端 `productImportAPI.preview` 解析该文件时的异常，添加错误捕获和友好提示

### 6. 佣金管理 - 默认值与自动计算
- 当前佣金编辑默认填写 FBP 佣金，改为 **默认填写 rFBS 佣金**
- FBP 佣金 = rFBS 佣金 - 1%（自动计算，不可直接编辑）
- 编辑界面需明确说明"FBP 佣金根据 rFBS 佣金自动计算（rFBS - 1%）"

### 7. 计算结果页面重构
#### 7.1 合并结果展示
- 移除独立的"价格优先方案"和"速度优先方案"区域
- 将它们整合进"分组计算结果"中
- 每个分组 tab 内的标题改为：`物流名称` + Smart 标志（如有）+ 陆运/空运
- 不再区分"自提"和"送货上门"

#### 7.2 rFBS-独联体国家细分
- rFBS-独联体 tab 需细分为 6 个国家（KZ、BY、KGZ、UZ、GE、AZ）
- 可通过子 tab 或下拉筛选，选择后只展示该国家的计算结果

#### 7.3 FBP-俄+CIS 二次筛选逻辑
- 计算完结果后，按"同一公司 + 同一 Service Level"分组
- 每组取价格最高的方式作为候选
- 各组候选方式再进行低价优先/速度优先筛选

### 8. 物流陆运/空运切换按钮
- 物流管理页面的物流列表中：
  - 陆运规则增加"转为空运"按钮
  - 空运规则增加"转为陆运"按钮
- 点击后切换该规则的 `type` 字段（`land` ↔ `air`），自动移到对应 tab

## Capabilities

### New Capabilities
- `logistics-pool-detail-view`: 公共物流池查看详情弹窗功能
- `logistics-pool-delete-all`: 物流池管理员一键删除全部功能
- `logistics-transport-toggle`: 物流陆运/空运快速切换按钮
- `fbp-cis-secondary-filter`: FBP-俄+CIS 计算结果的二次分组筛选逻辑
- `rfbs-cis-country-breakdown`: rFBS-独联体计算结果的国家级细分筛选

### Modified Capabilities
- `logistics-rule-editor`: 价格字段精度改为2位小数，移除电池容量限制字段
- `product-editor`: 移除电池容量填写方式、Wh/mAh/V 字段和 MSDS 字段
- `logistics-pool-import`: 修复导入失败问题，改为追加模式而非覆盖
- `product-batch-import`: 修复特定 xlsx 文件导入崩溃问题
- `commission-management`: 默认填写 rFBS 佣金，FBP 佣金自动计算
- `pricing-results-display`: 合并价格/速度优先方案到分组结果中，重新组织标题

## Impact

### 前端影响
- `LogisticsPage.jsx`: 价格字段精度、电池字段、陆运/空运切换按钮
- `PricingPage.jsx`: 产品编辑弹窗字段精简、精准模式字段精简、计算结果渲染重构
- `LogisticsPoolPage.jsx`: 查看详情按钮、删除全部按钮、导入追加逻辑
- `CommissionCategoriesPage.jsx`: 默认 rFBS 佣金、FBP 自动计算说明
- `ProductImportPage.jsx`: 崩溃修复的错误处理改进
- `services/api.js`: 新增物流池删除全部、物流切换类型的 API 调用

### 后端影响
- `api/routes/logistics_pool.py`: 新增 DELETE 全部 endpoint、改 import 为追加模式
- `api/routes/logistics.py`: 新增 transport type toggle endpoint
- `api/routes/products.py`: 产品导入错误处理改进
- `xlsx_import/detector.py`: 改进格式检测错误信息
- `pricing/calculate_pricing.py`: FBP-CIS 二次筛选逻辑、rFBS-CIS 国家级分组
- `api/routes/commission_categories.py` + `db/commission_categories.py`: 佣金存储模型调整（rFBS 为主，FBP 自动算）
- `models/logistics.py` 或相关 ORM 模型：可能需要确认 commission 字段

### 数据库
- 佣金类目表可能需要调整字段名（从 fbp_tier*_rate 改为 rfbs_tier*_rate 或新增字段）
- 需要 Alembic 迁移
