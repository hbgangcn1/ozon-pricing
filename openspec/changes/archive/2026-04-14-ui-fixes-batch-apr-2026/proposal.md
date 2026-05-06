## Why

物流管理系统存在5个UI/UX缺陷影响用户体验和数据准确性：菜单透明、限价显示错误、错误文字过大、佣金输入无法清零、精准模式产品编辑缺少类目选择。这些问题分布在多个页面，需要统一修复以保证系统一致性和可用性。

## What Changes

- **物流管理页面下拉菜单透明修复**：`dropdown-menu.jsx` 使用了未定义的 shadcn/ui 颜色变量（`bg-card`等），导致下拉菜单背景透明。需替换为项目已定义的 Tailwind 颜色。
- **公共物流池限价显示修复**：`LogisticsPoolPage.jsx` 详情面板显示旧的 `price_limit` 字段而非统一后的 `price_limit_cny` 字段，导致限价数据不正确。需切换到 CNY 字段。
- **批量导入错误文字过大修复**：`ProductImportPage.jsx` 导入结果面板中错误计数使用 `text-3xl`，红色文字过于突兀。需减小字号。
- **佣金编辑输入框默认值0无法删除修复**：`CommissionCategoriesPage.jsx` 中佣金率输入框的 onChange 使用 `parseFloat(value) || 0`，导致无法清空输入框。需允许空值中间态。
- **精准模式产品编辑佣金改为类目下拉**：`PricingPage.jsx` 中精准模式的产品编辑对话框仍使用手动输入佣金率，需改为佣金类目下拉菜单选择。

## Capabilities

### New Capabilities
- `dropdown-menu-style-fix`: 修复下拉菜单组件颜色映射，消除透明背景问题
- `price-limit-cny-display`: 公共物流池详情面板切换到 CNY 限价字段显示
- `import-error-text-size`: 减小批量导入结果面板中错误文字的字号
- `commission-input-clearing`: 修复佣金编辑输入框无法清空默认值0的问题
- `precision-mode-commission-dropdown`: 精准模式产品编辑中佣金改为类目下拉菜单选择

### Modified Capabilities
<!-- 无需修改已有规格的需求 -->

## Impact

- **前端组件**：`dropdown-menu.jsx`、`LogisticsPoolPage.jsx`、`ProductImportPage.jsx`、`CommissionCategoriesPage.jsx`、`PricingPage.jsx`
- **无后端变更**：所有修复均为前端UI层面，不涉及API或数据库变更
- **无破坏性变更**：所有修复为行为修正和样式调整，不影响现有数据
