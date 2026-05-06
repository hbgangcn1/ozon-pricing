## 1. 下拉菜单透明修复

- [x] 1.1 修改 `frontend/src/components/ui/dropdown-menu.jsx` 中 `DropdownMenuContent` 的颜色类：`bg-card` → `bg-surface-container`，`text-card-foreground` → `text-text-primary`
- [x] 1.2 修改 `DropdownMenuItem` 和 `DropdownMenuCheckboxItem` 的焦点颜色类：`focus:bg-accent` → `focus:bg-surface-high`，`focus:text-accent-foreground` → `focus:text-text-primary`
- [x] 1.3 修改 `DropdownMenuSeparator` 的颜色类：`bg-muted` → `bg-surface-high`
- [ ] 1.4 使用 audit + polish 技能对物流管理页面下拉菜单进行视觉审查和打磨

## 2. 公共物流池限价显示修复

- [x] 2.1 修改 `frontend/src/pages/LogisticsPoolPage.jsx` 详情面板中价格上限字段：`detailItem?.price_limit` → `detailItem?.price_limit_cny`
- [x] 2.2 修改详情面板中价格下限字段：`detailItem?.price_min` → `detailItem?.price_min_cny`
- [x] 2.3 为限价显示添加 "¥" 人民币货币符号前缀

## 3. 批量导入错误文字大小修复

- [x] 3.1 修改 `frontend/src/pages/ProductImportPage.jsx` 导入结果面板中错误计数文字的字号类：`text-3xl` → `text-sm`

## 4. 佣金编辑输入框默认值修复

- [x] 4.1 修改 `frontend/src/pages/CommissionCategoriesPage.jsx` 佣金率输入框的 onChange 逻辑，允许空字符串作为中间态（`e.target.value === '' ? '' : parseFloat(e.target.value)`）
- [x] 4.2 修改表单提交逻辑，在提交时将空值转换为 0

## 5. 精准模式产品编辑佣金下拉菜单

- [x] 5.1 在 `frontend/src/pages/PricingPage.jsx` 产品编辑对话框中，将佣金 RateInput 替换为佣金类目 Select 下拉菜单
- [x] 5.2 添加 `commission_category_id` 到产品编辑表单的 state 中
- [x] 5.3 在打开编辑对话框时，从产品数据中读取 `commission_category_id` 并设为 Select 默认值
- [x] 5.4 修改保存产品逻辑，提交 `commission_category_id` 而非 `commission_rate`

## 6. 验证

- [x] 6.1 验证物流管理页面下拉菜单不再透明
- [x] 6.2 验证公共物流池详情面板显示正确的人民币限价
- [x] 6.3 验证批量导入结果面板错误文字为小号字体
- [x] 6.4 验证佣金编辑输入框可以清空后正常输入新数字
- [x] 6.5 验证精准模式产品编辑中佣金为下拉菜单选择
