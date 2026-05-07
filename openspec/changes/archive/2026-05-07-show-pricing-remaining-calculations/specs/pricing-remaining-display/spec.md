# 物流定价页面剩余计算次数显示

## ADDED Requirements

### Requirement: 物流定价页面对 free/monthly 用户显示剩余计算次数

物流定价页面（`/pricing`）必须（MUST）在 Tab 切换组件上方，仅当 `user.user_type ∈ {free, monthly}` 时显示当前用户的剩余计算次数；其他套餐用户不得（MUST NOT）显示该提示。

显示格式固定为 `剩余 {n} 次计算`，其中 `{n} = user.remaining_calculations ?? 0`。样式：`text-xs text-muted-foreground text-center mb-2`。

实现位置：`frontend/src/pages/PricingPage.jsx:32-36`。

数据来源：`user.remaining_calculations` 由登录 API 返回，存储在 `authStore` 中。

#### Scenario: free 用户登录后查看 /pricing

- **GIVEN** 一个 `user_type=free` 的用户，且 `user.remaining_calculations=10`
- **WHEN** 该用户访问 `/pricing`
- **THEN** 页面在 Tab 切换组件上方显示 "剩余 10 次计算"

#### Scenario: monthly 用户登录后查看 /pricing

- **GIVEN** 一个 `user_type=monthly` 的用户，且 `user.remaining_calculations=5`
- **WHEN** 该用户访问 `/pricing`
- **THEN** 页面在 Tab 切换组件上方显示 "剩余 5 次计算"

#### Scenario: professional/enterprise/admin 用户访问 /pricing

- **GIVEN** 一个 `user_type ∉ {free, monthly}` 的用户
- **WHEN** 该用户访问 `/pricing`
- **THEN** 页面 **不** 显示 "剩余 X 次计算" 提示

#### Scenario: remaining_calculations 为 null

- **GIVEN** 一个 `user_type=free` 的用户，且 `user.remaining_calculations=null`
- **WHEN** 该用户访问 `/pricing`
- **THEN** 页面显示 "剩余 0 次计算"（`?? 0` 兜底）

## 约束

- 不修改任何 API 端点
- 不修改后端逻辑
- 不影响专业版/企业版用户体验
