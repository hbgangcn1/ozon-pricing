## Why

系统已有完整的微信支付 V3 后端模块（`wechat_pay_v3_api.py`、`payment_handler.py`、`payment_callback_enhanced.py`），但这些模块从未接入 FastAPI API 层，前端支付页面使用的是硬编码 mock 数据。用户无法通过系统完成套餐购买和升级，订阅管理页面的升级按钮仅弹出"功能开发中"提示。需要打通"后端支付模块 → API 路由 → 前端支付流程"的完整链路，使用户可以通过微信扫码支付完成订阅升级。

## What Changes

### 后端 API 层
- 新增 `api/routes/payment.py`：包含支付发起（创建 Native 订单返回二维码 URL）、微信回调通知接收、订单状态查询三个端点
- 修改 `api/main.py`：注册支付路由
- 修改 `api/routes/orders.py`：增强订单查询，支持状态筛选和分页参数

### 前端支付流程
- 新增支付二维码弹窗组件：用户点击升级 → 弹出微信支付二维码 → 实时轮询支付状态 → 展示支付结果
- 重构 `PaymentPage.jsx`：替换 mock 数据，对接真实订单 API，支持按状态筛选、实时刷新
- 修改 `SubscriptionPage.jsx`：升级按钮触发真实支付流程而非提示信息
- 新增 `frontend/src/services/api.js` 中的 paymentAPI 方法

### 依赖
- 前端新增 QR 码渲染库（`qrcode.react`）

## Capabilities

### New Capabilities
- `payment-api`: 微信支付 FastAPI 路由层 — 支付发起、微信回调通知、订单状态查询端点，连接现有 `payment_handler.py` 和 `wechat_pay_v3_api.py`
- `payment-ui`: 前端支付流程 — 二维码支付弹窗组件、支付状态轮询、订单历史真实数据展示、订阅页升级触发支付

### Modified Capabilities
- `subscription-feature-gating`: 订阅页升级按钮从"提示开发中"改为触发真实支付流程，需调整升级按钮的交互逻辑

## Impact

### 代码影响
- **新建**: `api/routes/payment.py`、前端支付弹窗组件
- **修改**: `api/main.py`、`PaymentPage.jsx`、`SubscriptionPage.jsx`、`frontend/src/services/api.js`
- **不修改**: `payment_handler.py`、`wechat_pay_v3_api.py`、`wechat_pay_config.py`、`payment_callback_enhanced.py`、`models/order.py`（核心逻辑已完整）

### API 影响
- 新增 3 个端点：`POST /api/payments/create`、`POST /api/payments/notify`、`GET /api/payments/{order_id}/status`
- 增强 1 个端点：`GET /api/orders`（增加筛选参数）

### 依赖影响
- 前端 `package.json` 新增 `qrcode.react`
- 后端无新增依赖（微信支付库已存在）

### 安全考量
- 微信回调端点需验签（已有 `verify_signature` 实现），无需认证中间件
- 支付发起端点需用户认证（`get_current_user_id`）
- 回调处理需幂等性保证（已有 `payment_callback_enhanced.py` 重试机制）
