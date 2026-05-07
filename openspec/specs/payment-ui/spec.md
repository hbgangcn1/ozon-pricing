## Purpose

payment-ui capability spec.

## Requirements


### Requirement: 支付二维码弹窗组件
系统 SHALL 提供支付二维码弹窗（基于 shadcn/ui Dialog），当用户触发支付时展示微信支付二维码，并实时显示支付状态。弹窗 SHALL 与现有深色主题设计系统完全一致。

#### Scenario: 弹窗展示二维码
- **WHEN** 用户点击套餐升级按钮并确认支付
- **THEN** 系统调用 `POST /api/payments/create` 获取 `code_url`，在弹窗中使用 `qrcode.react` 渲染 240×240 像素的微信支付二维码，二维码区域使用白色背景（确保深色主题下可扫描），同时显示金额（`text-2xl font-bold text-primary`）、订单号、倒计时和"请使用微信扫码支付"提示

#### Scenario: 实时轮询支付状态
- **WHEN** 二维码弹窗打开后
- **THEN** 前端每 3 秒轮询 `GET /api/payments/{order_id}/status`，使用指数退避策略（3s → 6s → 12s → 24s → 30s 上限），最长轮询 2 小时

#### Scenario: 支付成功状态
- **WHEN** 轮询接口返回 `trade_state: "SUCCESS"`
- **THEN** 弹窗切换为成功状态：显示 CheckCircle2 图标（`text-status-success`）、"支付成功"文字、套餐信息，提供"查看订单"按钮跳转 PaymentPage，3 秒后自动关闭弹窗并刷新用户订阅信息

#### Scenario: 二维码过期
- **WHEN** 倒计时结束（2 小时）或轮询返回 `trade_state: "CLOSED"`
- **THEN** 弹窗切换为过期状态：显示 XCircle 图标（`text-status-error`）、"二维码已过期"文字、"重新发起支付"按钮

#### Scenario: 用户关闭弹窗
- **WHEN** 用户在支付过程中关闭弹窗
- **THEN** 停止轮询，显示确认提示"关闭后可在订单页面查看支付状态"，订单保持 PENDING 状态

### Requirement: 支付弹窗视觉规范
支付弹窗 SHALL 遵循项目深色主题设计系统（surface `#0d1117`、primary `#3e65ff`、Manrope 标题 + Inter 正文），使用 shadcn/ui Dialog 组件，与 LogisticsPage、PlanManagementPage 中的弹窗风格完全一致。

#### Scenario: 弹窗样式一致性
- **WHEN** 支付弹窗渲染时
- **THEN** 弹窗使用 `DialogContent` 组件（`max-w-md`），背景 `bg-surface-container`，边框 `border-surface-high`，标题使用 `DialogTitle`（`font-headline`），内容文字使用 `text-text-secondary`，按钮使用项目标准 `Button` 组件变体

#### Scenario: 二维码容器样式
- **WHEN** 二维码渲染时
- **THEN** 二维码外层容器使用 `rounded-xl bg-white p-4`（白色背景确保深色主题下可扫描），周围留有 `mx-auto` 居中和适当间距

### Requirement: PaymentPage 对接真实 API
`PaymentPage.jsx` SHALL 移除所有 mock 数据，对接 `GET /api/orders` 真实端点，展示用户的实际订单历史。

#### Scenario: 加载真实订单数据
- **WHEN** 用户进入 PaymentPage
- **THEN** 页面调用 `GET /api/orders` 获取真实订单列表，显示订单号、套餐、金额、状态（使用 Badge 组件，SUCCESS=`text-status-success`、PENDING=`text-status-warning`、FAILED=`text-status-error`）、创建时间、支付时间

#### Scenario: 状态筛选
- **WHEN** 用户选择状态筛选器（全部/已支付/待支付/已关闭）
- **THEN** 页面调用 `GET /api/orders?status=xxx` 获取筛选结果

#### Scenario: 刷新按钮
- **WHEN** 用户点击刷新按钮
- **THEN** 页面重新调用 API 获取最新订单数据，显示 sonner toast "刷新成功"

#### Scenario: 空状态
- **WHEN** 用户没有任何订单
- **THEN** 页面显示空状态提示："暂无订单记录，升级套餐后将在此显示订单信息"，带有前往订阅页的按钮

#### Scenario: 加载状态
- **WHEN** API 请求进行中
- **THEN** 表格区域显示骨架屏加载动画（`bg-surface-high animate-pulse`）

### Requirement: 前端支付 API 服务
`frontend/src/services/api.js` SHALL 新增 paymentAPI 模块，包含支付流程所需的所有 API 调用方法。

#### Scenario: 创建支付订单方法
- **WHEN** 前端调用 `paymentAPI.createOrder({ plan_code, billing_cycle, amount })`
- **THEN** 发送 `POST /api/payments/create` 请求，携带 JWT token，返回 `{ order_id, code_url }`

#### Scenario: 查询支付状态方法
- **WHEN** 前端调用 `paymentAPI.getStatus(orderId)`
- **THEN** 发送 `GET /api/payments/{orderId}/status` 请求，返回 `{ status, trade_state }`

#### Scenario: 获取订单列表方法
- **WHEN** 前端调用 `paymentAPI.getOrders({ status, page, page_size })`
- **THEN** 发送 `GET /api/orders` 请求（带查询参数），返回 `{ orders, total, page, page_size }`

### Requirement: QR 码依赖安装
项目 SHALL 安装 `qrcode.react` 包用于生成微信支付二维码。

#### Scenario: 安装依赖
- **WHEN** 执行 `npm install qrcode.react`
- **THEN** `qrcode.react` 出现在 `package.json` 的 dependencies 中，可在组件中 `import { QRCodeSVG } from 'qrcode.react'`
