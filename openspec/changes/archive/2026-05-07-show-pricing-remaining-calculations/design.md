# design.md

## 变更概述

在物流定价计算页面为免费版/体验版用户显示剩余计算次数。

## 技术方案

### 修改文件

`frontend/src/pages/PricingPage.jsx`

### 实现位置

在 `<Tabs>` 组件上方添加一行提示文字：

```jsx
{/* 在 Tabs 上方显示，只对 free/monthly 用户可见 */}
{['free', 'monthly'].includes(user?.user_type) && (
  <div className="text-xs text-muted-foreground text-center mb-2">
    剩余 {user?.remaining_calculations ?? 0} 次计算
  </div>
)}

<Tabs value={activeTab} onValueChange={setActiveTab}>
  <TabsList className="mb-4 grid grid-cols-2 w-full">
    ...
  </TabsList>
  ...
</Tabs>
```

### 用户来源

`user` 对象来自 `useAuthStore()` hook，已经在组件中使用：

```jsx
const { user } = useAuthStore()
```

`user.remaining_calculations` 字段已经在用户登录时从 API 获取并存储在 localStorage 中。

### 显示条件

- `user.user_type` 为 `free` 或 `monthly` 时显示
- `user.user_type` 为 `professional`、`enterprise`、`gratitude`、`test` 或 `admin` 时不显示

### 样式设计

- 文字大小：`text-xs`（12px）
- 颜色：`text-muted-foreground`（灰色）
- 对齐：`text-center`
- 间距：`mb-2`（底部 margin 8px）

## 布局示意

```
┌─────────────────────────────────────┐
│                                     │
│    剩余 7 次计算                    │  ← 仅 free/monthly 用户可见
│                                     │
├─────────────────────────────────────┤
│  [快速模式]    [精准模式]           │  ← TabsList
├─────────────────────────────────────┤
│  物流定价（快速模式）               │  ← CardTitle
│  ...                                │
│                                     │
└─────────────────────────────────────┘
```

## 数据流

1. 用户登录时，`remaining_calculations` 从 API 响应获取
2. 存储到 localStorage（`authStore.setAuth`）
3. `PricingPage` 通过 `useAuthStore()` 获取 `user` 对象
4. 组件渲染时根据 `user.user_type` 条件显示剩余次数

## 兼容性

- 不修改任何 API
- 不修改后端逻辑
- 只影响前端展示
- 向后兼容
