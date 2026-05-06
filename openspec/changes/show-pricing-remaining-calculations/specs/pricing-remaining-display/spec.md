# 物流定价页面剩余计算次数显示

## 概要

在物流定价计算页面为免费版/体验版用户显示每日剩余计算次数。

## 背景

免费版用户每日有 10 次物流定价计算限制。目前用户无法直观看到剩余次数，可能导致在不知情的情况下遇到"计算次数已用完"的情况。

## 需求

### FR-1: 剩余次数显示

在物流定价页面（`/pricing`）的 Tab 切换组件上方，显示当前用户的剩余计算次数。

### FR-1.1: 显示条件

- 仅当 `user.user_type` 为 `free` 或 `monthly` 时显示
- `user.user_type` 为其他值时不显示

### FR-1.2: 显示格式

```
剩余 {n} 次计算
```

其中 `{n}` 为 `user.remaining_calculations` 的值，如果为 `null` 则显示 `0`。

### FR-1.3: 样式

- 文字大小：12px (`text-xs`)
- 颜色：`text-muted-foreground`
- 对齐：居中 (`text-center`)
- 间距：下方留 8px 间隔 (`mb-2`)

## 界面示意

```
┌─────────────────────────────────────┐
│                                     │
│    剩余 7 次计算                    │  ← 仅 free/monthly 用户可见
│                                     │
├─────────────────────────────────────┤
│  [快速模式]    [精准模式]           │
├─────────────────────────────────────┤
│  物流定价（快速模式）               │
│  ...                                │
└─────────────────────────────────────┘
```

## 技术实现

### 修改文件

- `frontend/src/pages/PricingPage.jsx`

### 实现方式

在 `<Tabs>` 前添加条件渲染：

```jsx
{['free', 'monthly'].includes(user?.user_type) && (
  <div className="text-xs text-muted-foreground text-center mb-2">
    剩余 {user?.remaining_calculations ?? 0} 次计算
  </div>
)}
```

## 数据来源

`user.remaining_calculations` 在用户登录时从 API 获取，已存储在 `authStore` 中。

## 约束

- 不修改任何 API 端点
- 不修改后端逻辑
- 不影响专业版/企业版用户体验
