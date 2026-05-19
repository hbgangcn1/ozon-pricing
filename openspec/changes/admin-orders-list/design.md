## Context

现有统计页面（StatisticsPage）有 6 个 tab：总览、留存分析、用户活跃、充值与收入、操作日志、登录记录。后端 db/orders.py 只有 get_user_orders() 查询单个用户订单。管理员无法在统计页面查看所有用户的订单明细。

PaymentOrder 模型字段：id, order_id, user_id, amount, description, status, created_at, order_type, is_upgrade, upgrade_from_plan, upgrade_to_plan。

## Goals / Non-Goals

**Goals:**
- 管理员可在统计页面查看所有用户的订单记录
- 支持按用户名/订单号模糊搜索
- 支持按状态（PENDING/SUCCESS/FAILED）下拉筛选
- 支持日期范围过滤
- 支持分页浏览

**Non-Goals:**
- 不支持 CSV 导出
- 不支持订单详情弹窗
- 不修改现有订单 API（/api/orders）

## Decisions

**Decision 1: API 路径放在 /api/statistics/orders 而非 /api/orders**
- Rationale: 订单端点 /api/orders 是普通用户查自己订单的接口，admin 全量查询属于统计范畴，放在 /api/statistics/ 下语义更清晰，且自动继承 admin 权限守卫。

**Decision 2: 联表 User 获取 username，不冗余存储**
- Rationale: PaymentOrder.user_id 已有索引，联表查询性能足够。避免数据冗余。

**Decision 3: 搜索同时匹配 username 和 order_id**
- Rationale: 用户可能记不住完整订单号，也可能记不住完整用户名，模糊匹配两个字段覆盖更多场景。

**Decision 4: 状态筛选用下拉而非文本输入**
- Rationale: 状态值是固定的枚举（PENDING/SUCCESS/FAILED），下拉比文本输入更不容易出错。

## Risks / Trade-offs

- **[Risk]** 订单量大时联表查询可能较慢 → **Mitigation**: 分页 + 索引（user_id, created_at），实际场景单页 20 条影响可忽略
- **[Risk]** 搜索无索引可能慢 → **Mitigation**: 订单量级在万级以下，ILIKE 全表扫描可接受；未来可加 GIN 索引
