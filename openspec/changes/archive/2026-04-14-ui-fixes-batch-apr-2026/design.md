## Context

物流管理系统前端存在5个独立的UI/UX缺陷，均为前端层面问题，不涉及后端API或数据库变更。

当前状态：
1. `dropdown-menu.jsx` 使用 shadcn/ui 默认颜色变量（`bg-card`、`text-card-foreground`等），但项目 `tailwind.config.js` 未映射这些变量，导致背景透明
2. `LogisticsPoolPage.jsx` 详情面板显示旧的 `price_limit`/`price_min` 字段，而非迁移后的 `price_limit_cny`/`price_min_cny` 字段
3. `ProductImportPage.jsx` 导入结果面板的错误计数使用 `text-3xl`（~30px），红色大字过于刺眼
4. `CommissionCategoriesPage.jsx` 佣金率输入框 onChange 使用 `parseFloat(value) || 0`，空输入立刻被替换为0
5. `PricingPage.jsx` 精准模式产品编辑对话框中佣金仍为手动输入 RateInput，未改为类目下拉选择

## Goals / Non-Goals

**Goals:**
- 修复下拉菜单透明问题，使用项目已有的颜色变量
- 公共物流池详情面板正确显示人民币限价
- 导入结果面板错误文字缩小到合理尺寸
- 佣金输入框允许用户清空后重新输入数字
- 精准模式产品编辑中佣金改为从佣金类目下拉菜单选择

**Non-Goals:**
- 不重构 shadcn/ui 组件体系，仅做颜色映射替换
- 不修改后端 API 或数据库结构
- 不修改限价数据的导入/存储逻辑
- 不修改佣金类目本身的CRUD功能

## Decisions

### D1: 下拉菜单颜色替换策略
**选择**: 直接替换 `dropdown-menu.jsx` 中未定义的颜色类为项目已有颜色
- `bg-card` → `bg-surface-container`
- `text-card-foreground` → `text-text-primary`
- `focus:bg-accent` → `focus:bg-surface-high`
- `focus:text-accent-foreground` → `focus:text-text-primary`

**替代方案**: 在 tailwind.config.js 中添加 card/accent 变量映射。不采用，因为全局添加未使用的变量增加维护负担。

### D2: 限价字段切换
**选择**: 将 `detailItem?.price_limit` / `detailItem?.price_min` 直接替换为 `detailItem?.price_limit_cny` / `detailItem?.price_min_cny`，并添加 "¥" 前缀标识货币。
**理由**: 后端数据库已完成 CNY 统一迁移，API 已返回 `_cny` 字段，仅前端显示未更新。

### D3: 错误文字字号
**选择**: 将 `text-3xl` 改为 `text-sm`，使错误文字成为辅助信息而非视觉焦点。
**理由**: 错误信息是补充说明，不应比成功统计数字更突出。

### D4: 佣金输入框清空策略
**选择**: 修改 onChange 逻辑，允许空字符串作为中间态。输入为空时设置 state 为 `''`，提交时再转换为数字 `0`。
**替代方案**: 使用 Ant Design InputNumber 组件。不采用，因为当前项目使用自定义 Input 组件风格统一。

### D5: 精准模式产品编辑佣金下拉
**选择**: 复用精准模式计算表单中已有的佣金类目 Select 组件模式，将产品编辑对话框中的 commission_rate RateInput 替换为 commission_category_id Select 下拉菜单。
**理由**: 产品模型已支持 `commission_category_id` 字段，且精准模式计算表单已有类目下拉的实现可参考。

## Risks / Trade-offs

- **[R1] dropdown-menu.jsx 被其他页面共用** → 颜色替换影响所有使用该组件的地方。缓解：替换的目标颜色（surface-container、surface-high）是项目通用色，适用于所有场景。
- **[R2] 佣金输入允许空值中间态** → 用户可能意外提交空值。缓解：表单提交时强制将空值转为0。
- **[R3] 精准模式产品编辑改为下拉后，已有手动输入的佣金率数据** → 已存在的 commission_rate 值不会丢失，但编辑时将切换到类目选择模式。缓解：如果产品有 commission_category_id 则显示对应类目，否则默认不选中。
