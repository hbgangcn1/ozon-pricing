## 1. 后端 API 路由层

- [x] 1.1 创建 `api/routes/payment.py` — 定义 FastAPI router (prefix="/api/payments", tags=["payment"])，包含 Pydantic 请求/响应模型（CreatePaymentRequest, PaymentStatusResponse, NotifyResponse）
- [x] 1.2 实现 `POST /api/payments/create` 端点 — 校验 amount 与 plans 表一致，创建 PaymentOrder(status=PENDING)，调用 `wechat_pay_v3.create_native_order()`，返回 `{ order_id, code_url }`。依赖 `get_current_user_id` 认证
- [x] 1.3 实现 `POST /api/payments/notify` 端点 — 无认证，调用 `wechat_pay_v3.process_notify(headers, body)` 处理微信回调。入口检查 PaymentOrder.status 实现幂等。异步执行业务逻辑确保 5 秒内返回 200
- [x] 1.4 实现 `GET /api/payments/{order_id}/status` 端点 — 认证用户查询自己的订单。PENDING 状态调用 `wechat_pay_v3.query_order()` 同步最新状态后返回；非 PENDING 直接返回 DB 状态。非本人订单返回 404
- [x] 1.5 在 `api/main.py` 中注册 payment router — `app.include_router(payment.router)`

## 2. 订单列表增强

- [x] 2.1 增强 `db/orders.py` — `get_user_orders()` 新增 status 筛选参数和 page/page_size 分页参数，返回 `{ orders, total }`
- [x] 2.2 增强 `api/routes/orders.py` — `GET /api/orders` 端点新增 query 参数 `status`(可选)、`page`(默认1)、`page_size`(默认10)，响应包含 `{ orders, total, page, page_size }`

## 3. 前端依赖安装

- [x] 3.1 安装 `qrcode.react` — 在 `frontend/` 目录执行 `npm install qrcode.react`

## 4. 前端 API 服务

- [x] 4.1 在 `frontend/src/services/api.js` 中新增 `paymentAPI` 模块 — 包含 `createOrder({ plan_code, billing_cycle, amount })` 方法（POST /api/payments/create）
- [x] 4.2 新增 `paymentAPI.getStatus(orderId)` 方法 — GET /api/payments/{orderId}/status
- [x] 4.3 增强 `ordersAPI.getAll()` 方法 — 支持 `{ status, page, page_size }` 查询参数

## 5. 支付二维码弹窗组件

- [x] 5.1 创建 `frontend/src/components/PaymentQRDialog.jsx` — 基于 shadcn/ui Dialog，接收 `open, onOpenChange, planCode, planName, billingCycle, amount, onSuccess` props
- [x] 5.2 实现弹窗"待扫码"状态 — 调用 `paymentAPI.createOrder()` 获取 code_url，使用 `QRCodeSVG` 渲染 240×240 二维码（白色背景容器 `rounded-xl bg-white p-4`），显示金额（`text-2xl font-bold text-primary`）、订单号、倒计时
- [x] 5.3 实现轮询 hook `usePaymentPolling` — 指数退避轮询（3s→6s→12s→24s→30s上限），调用 `paymentAPI.getStatus()`，最长 2 小时超时。返回 `{ status, countdown }`
- [x] 5.4 实现弹窗"支付成功"状态 — CheckCircle2 图标（`text-status-success`）、"支付成功"文字、套餐信息、"查看订单"按钮，3 秒后自动关闭
- [x] 5.5 实现弹窗"过期/失败"状态 — XCircle 图标（`text-status-error`）、"二维码已过期"文字、"重新发起支付"按钮（重新调用 createOrder）
- [x] 5.6 实现弹窗关闭确认 — 用户关闭弹窗时停止轮询，显示确认提示"关闭后可在订单页面查看支付状态"

## 6. 订阅页升级流程

- [x] 6.1 修改 `SubscriptionPage.jsx` 升级按钮 — 移除"功能开发中"toast，改为打开支付确认对话框
- [x] 6.2 实现支付确认对话框 — 使用 shadcn/ui Dialog，显示目标套餐名称、计费周期选择器（月/年 Switch/Tabs）、对应价格（从 plans 数据获取 actual_price），确认按钮触发 PaymentQRDialog
- [x] 6.3 集成 PaymentQRDialog — 确认后打开二维码弹窗，传入 planCode/planName/billingCycle/amount
- [x] 6.4 支付成功后刷新 — PaymentQRDialog onSuccess 回调中重新获取用户订阅信息（`subscriptionsAPI.getCurrent()`），更新页面显示

## 7. PaymentPage 真实数据对接

- [x] 7.1 移除 `PaymentPage.jsx` 中的 mockOrders 数据和相关代码
- [x] 7.2 添加 useEffect 加载真实订单 — 调用 `ordersAPI.getAll()` 获取订单列表，存入 state
- [x] 7.3 实现状态筛选 UI — 在搜索栏旁添加 Select 组件（全部/已支付/待支付/已关闭），筛选调用 API
- [x] 7.4 实现加载骨架屏 — 表格区域 loading 时显示 `bg-surface-high animate-pulse` 骨架
- [x] 7.5 实现空状态 — 无订单时显示空状态卡片："暂无订单记录，升级套餐后将在此显示订单信息"，带"前往订阅管理"按钮
- [x] 7.6 状态 Badge 多状态样式 — SUCCESS=`border-status-success/30 text-status-success`、PENDING=`border-status-warning/30 text-status-warning`、FAILED/CLOSED=`border-status-error/30 text-status-error`
- [x] 7.7 刷新按钮对接 — 点击刷新按钮重新调用 API，显示 sonner toast "刷新成功"
- [x] 7.8 分页对接 — 使用 API 返回的 total 计算总页数，翻页时调用 `ordersAPI.getAll({ page, page_size })`

## 8. 测试与验证

- [x] 8.1 后端 API 测试 — 为 `api/routes/payment.py` 编写 pytest 测试：创建订单（mock 微信API）、回调处理（mock 签名验证）、状态查询、金额校验、幂等性
- [x] 8.2 后端订单增强测试 — 为增强的 `GET /api/orders` 编写测试：状态筛选、分页、无参数默认行为
- [x] 8.3 前端组件测试 — 为 PaymentQRDialog 编写 Vitest 测试：渲染二维码、轮询状态切换、关闭确认
- [x] 8.4 前端页面测试 — 为修改后的 PaymentPage 和 SubscriptionPage 编写测试：API 数据加载、空状态、筛选
- [x] 8.5 运行全量后端测试 — `python -m pytest --tb=short` 确保无回归
- [x] 8.6 运行全量前端测试 — `cd frontend && npm run test` 确保无回归
- [x] 8.7 运行 flake8 检查 — `python -m flake8` 确保新代码符合规范
