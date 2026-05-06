## Context

系统已有完整的微信支付 V3 后端实现（`wechat_pay_v3_api.py` 567 行，含 Native/JSAPI 下单、签名、解密），支付处理器（`payment_handler.py`），增强回调（`payment_callback_enhanced.py`，含 Queue + 重试 + 监控），以及订单模型（`models/order.py` PaymentOrder）。

这些模块从未接入 FastAPI 路由层。前端 `PaymentPage.jsx` 使用 mock 数据，`SubscriptionPage.jsx` 升级按钮仅弹出"功能开发中"提示。

**现有后端模块调用关系：**
```
wechat_pay_config.py → WeChatPayV3API (wechat_pay_v3_api.py)
                         ├── create_native_order(out_trade_no, description, total, ...)
                         ├── query_order(out_trade_no)
                         └── process_notify(headers, body)
                                └── decrypt_callback → PaymentCallbackEnhanced
                                                        └── PaymentHandler.handle_payment_success()
                                                              └── 更新 user.subscription_type/expires
```

**订阅系统数据流：**
- Plan 表：plan_code(free/efficiency/professional/enterprise)、display_price_month/year、actual_price_month/year、calc_limit、logistics_limit
- User 表：user_type、subscription_type、subscription_expires、remaining_calculations、billing_cycle
- 支付成功后：`handle_payment_success()` 从 description 提取 plan_code → 更新 user 字段

**前端技术栈：** React 18 + Vite + shadcn/ui (Radix UI) + Tailwind CSS + Zustand + sonner

**设计系统：** 深色主题（`#0d1117` 背景），主色 Indigo `#3e65ff`，Manrope 标题 + Inter 正文，shadcn/ui 组件

## Goals / Non-Goals

**Goals:**
- 打通 FastAPI 路由层，包装现有支付模块为 REST API
- 实现完整的前端支付流程：选择套餐 → 弹出二维码 → 扫码支付 → 实时轮询 → 展示结果
- `PaymentPage.jsx` 对接真实订单 API，替换 mock 数据
- `SubscriptionPage.jsx` 升级按钮触发真实支付
- 支付弹窗 UI 与现有深色主题设计系统完全一致

**Non-Goals:**
- 不修改核心支付模块（`wechat_pay_v3_api.py`、`payment_handler.py`、`payment_callback_enhanced.py`）
- 不实现 JSAPI 支付（仅 Native 扫码）
- 不实现套餐降级退款逻辑
- 不实现支付对账系统
- 不增加 Redis 依赖（使用数据库级幂等检查）

## Decisions

### D1: 使用 Native Pay（扫码支付）而非 JSAPI

**选择：** Native Pay（微信 V3 `create_native_order`）

**理由：** 系统是桌面端 B 端工具，用户通过电脑浏览器操作。Native Pay 返回 `code_url`（`weixin://` 协议），前端生成 QR 码，用户用微信扫码支付。JSAPI 需要微信内打开或获取 openid，不适合桌面场景。

**替代方案：** JSAPI（需微信内置浏览器）、H5支付（需额外申请权限）— 均不适合当前场景。

### D2: QR 码库选用 `qrcode.react`

**选择：** `qrcode.react`（npm 周下载量 ~2M，活跃维护）

**理由：** 提供 `QRCodeCanvas` 和 `QRCodeSVG` 两种渲染模式，支持 `imageSettings`（中间 logo），包体积小（~15KB），在深色主题下可通过 `bgColor`/`fgColor` 自定义颜色。

**替代方案：** `react-qr-code`（维护较少）、自研 Canvas 渲染（无必要）。

### D3: 支付状态使用前端轮询而非 WebSocket/SSE

**选择：** 前端定时轮询 `GET /api/payments/{order_id}/status`

**理由：**
1. 微信回调已有异步处理+重试机制（`payment_callback_enhanced.py`），前端轮询是双重保障
2. 项目无现有 WebSocket 基础设施，SSE 虽用于定价计算（`pricing.py`），但支付状态查询频率低（3-30s 间隔），HTTP 轮询更简单可靠
3. `code_url` 有效期 2 小时，轮询使用指数退避：3s → 6s → 12s → 24s → 30s（上限），对服务器压力极小

**替代方案：** WebSocket（需新增基础设施）、SSE（过重，支付场景不需要流式推送）。

### D4: API 路由直接调用现有模块，不引入新抽象

**选择：** `api/routes/payment.py` 直接导入 `wechat_pay_v3`（全局实例）和 `PaymentHandler`

**理由：** 核心模块已完整实现且经过 50+ commit 迭代。路由层仅做"接线"：参数校验 → 调用现有方法 → 返回结果。增加抽象层无益，徒增代码量。

**连接方式：**
```
POST /api/payments/create
  → 创建 PaymentOrder(status=PENDING) 写入 DB
  → wechat_pay_v3.create_native_order(out_trade_no, ...)
  → 返回 { code_url, order_id }

POST /api/payments/notify  (无认证)
  → wechat_pay_v3.process_notify(headers, body)
  → PaymentCallbackEnhanced.process_callback(...)
  → PaymentHandler.handle_payment_success(...)
  → 返回 200

GET /api/payments/{order_id}/status
  → DB 查 PaymentOrder.status
  → 若 status 仍为 PENDING，调用 wechat_pay_v3.query_order(out_trade_no) 同步最新状态
  → 返回 { status, trade_state }
```

### D5: 幂等性使用数据库级检查而非 Redis

**选择：** 在 `handle_payment_success` 入口检查 `PaymentOrder.status != PENDING` 则跳过

**理由：** 项目未在支付流程中使用 Redis（`redis_cache.py` 仅用于汇率缓存）。PaymentOrder 的 status 字段天然可作为幂等标记：首次处理时 PENDING → SUCCESS 原子更新，后续回调检查 status 已是 SUCCESS 则直接返回。已有的 `payment_callback_enhanced.py` 重试机制也通过内部状态跟踪避免重复处理。

**替代方案：** Redis SET NX 分布式锁（需引入新依赖，当前场景不需要）。

### D6: 支付弹窗使用 shadcn/ui Dialog 组件

**选择：** 基于 `Dialog`（Radix UI）实现支付二维码弹窗

**理由：** 项目已在 `LogisticsPage.jsx`、`PlanManagementPage.jsx` 等多处使用 `Dialog`/`DialogContent`/`DialogHeader` 组件。支付弹窗内容按状态切换：
1. **待扫码态**：QR 码 + 金额 + 订单号 + 倒计时 + "请使用微信扫码支付"提示
2. **支付成功态**：成功图标 + 套餐信息 + "查看订单"按钮
3. **支付失败/超时态**：错误提示 + "重新发起"按钮

**视觉规范：**
- 弹窗宽度：`max-w-md`（与简单操作弹窗一致）
- 背景：`bg-surface-container` + `border-surface-high`
- QR 码尺寸：240×240px，白色底色（`bgColor="#ffffff"`），黑色前景
- QR 码容器：圆角 `rounded-lg`，白色 padding 区域（因为是深色主题，QR 码需要白色背景才能扫描）
- 金额显示：`text-2xl font-bold text-primary`
- 状态图标：lucide-react `CheckCircle2`（成功，`text-status-success`）、`XCircle`（失败，`text-status-error`）
- 文字：Inter 字体，`text-sm text-text-secondary`

## Risks / Trade-offs

### R1: 微信商户证书可能已过期
**风险：** `cert/` 目录下的商户私钥和平台证书可能已过期，导致签名验证失败。
**缓解：** 实现前先检查证书有效期。API 路由增加 try/catch，返回明确的证书错误信息而非 500。

### R2: 回调 URL 需要公网可达
**风险：** `wechat_pay_config.py` 中回调地址是 `https://www.cbprice.cn/wechat/notify`，开发环境无法接收微信回调。
**缓解：** 开发阶段使用轮询查询作为主要状态更新方式。回调作为生产环境的实时补充。可通过 `LOCAL_TEST_MODE` 环境变量跳过回调处理。

### R3: 轮询在高并发下可能产生压力
**风险：** 多用户同时支付时，轮询请求叠加。
**缓解：** 指数退避策略（3s → 30s 上限）+ 最大轮询时长 2 小时。单个用户轮询请求极少。已有 `api/main.py` 限流中间件。

### R4: code_url 2 小时有效期
**风险：** 用户打开二维码后长时间未扫码，过期后扫码无效。
**缓解：** 前端显示倒计时，过期后自动关闭弹窗并提示"二维码已过期，请重新发起支付"。
