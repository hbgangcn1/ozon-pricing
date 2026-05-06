## Context

本系统是一个基于 FastAPI + React 的 Ozon 跨境电商定价工具，使用 SQLAlchemy 2.0 异步 ORM + PostgreSQL 数据库，Alembic 迁移，前端使用 shadcn/ui + Tailwind + Zustand。

当前状态：
- `models/logistics.py`：Logistics 表有完整的费率、尺寸、重量字段，但**没有** fulfillment_type / destination / FBP 相关字段
- `models/product.py`：Product 表有 `commission_rate: Float` 固定字段，无类目关联
- `pricing/calculate_pricing.py`：`calculate_pricing(product, land_logistics, air_logistics, mode, priority)` 返回单一结果字典，含 best_land / best_air
- `pricing/logistic_cost.py`：按重量/尺寸/电池/液体过滤，不感知 fulfillment_type 或目的地
- 用户表：`user_type`（用户类型）、`remaining_calculations`（当日剩余次数）、`subscription_expires`（到期时间戳）已存在
- Admin 端：`api/routes/admin.py` 提供用户 CRUD，但无订阅时长/次数调整端点

改造涉及：数据库结构、定价核心逻辑、批量导入脚本、前端多页面，属于大型跨切面变更。

## Goals / Non-Goals

**Goals:**
- 新增 `commission_categories` 表，支持按类目+价格层级计算 FBP/rFBS 佣金
- 扩展 `logistics` 表，支持 rFBS（7国）和 FBP（RU/KZ/BY）物流方式
- 新增 `logistics_pool` 全局物流池表，支持 Admin 批量导入4种 xlsx 格式
- 定价结果按 4 个 Tab（rFBS-RU、rFBS-CIS各国、FBP-RU、FBP-RU+CIS）分组返回
- 产品批量导入（xlsx列映射+数据清洗+重复处理）
- Admin 可调整用户订阅时长、当日次数、用户类型

**Non-Goals:**
- 不做多级类目树（一级扁平列表）
- 不做 rFBS 佣金独立存储（rFBS = FBP + 1%，前端/后端计算时推导）
- 不做 FBP Smart 物流公司管理器（is_smart 字段自动识别，按Delivery Service名含"Smart"判断）
- 不做支付/订阅购买流程改造（仅管理员手动调整）
- 不做 E2E 测试（本次改造不包含 Playwright 测试）

## Decisions

### D1：commission_categories 表结构 — 只存 FBP 三层级费率

**决策**：`commission_categories` 表存储3个 FBP 层级费率（tier1/tier2/tier3），rFBS = FBP + 0.01，不单独存储。

**原因**：用户确认"rFBS 比 FBP 每层级高 1%"，在计算时用代码推导，避免数据冗余和同步问题。

**价格层级定义**：
- Tier 1：商品售价 ≤ 1500 RUB
- Tier 2：1500 < 售价 ≤ 5000 RUB
- Tier 3：售价 > 5000 RUB

**一次迭代收敛**：不会出现"初始价格1500以下加佣金后跨到5000以上"的情况，无需多次迭代。

---

### D2：logistics 表扩展字段 — 5个新增字段

**决策**：Alembic 迁移新增5列，所有现有记录默认值为 `'rfbs'` / `'RU'` / NULL / NULL / 0。

```
fulfillment_type: str  默认 'rfbs'   # 'rfbs' 或 'fbp'
destination:      str  默认 'RU'     # rfbs: RU/KZ/BY/KGZ/UZ/GE/AZ; fbp: RU/KZ/BY
fbp_service_level:str  可空           # 'economy'/'standard'/'express'/'super_express'
fbp_company:      str  可空           # 3PL 公司名称
is_smart:         int  默认 0         # 0 或 1
```

**原因**：向后兼容，现有物流记录全部视为 rFBS + 目的地 Russia。

---

### D3：logistics_pool 表 — 复用 logistics 字段集

**决策**：`logistics_pool` 表与 `logistics` 共用相同字段集，额外增加 `source_file`、`imported_at`、`is_active` 字段，无 `user_id`（全局共享）。

**原因**：物流池是全局模板，用户从中选择后复制到自己的 logistics 表（user_id 赋值为当前用户）。

---

### D4：xlsx 批量导入 — 按文件类型自动路由，不手动选择

**决策**：根据 xlsx 文件名关键词和 Sheet 名称自动判断格式类型（4种），Admin 不需要手动指定格式。

| 文件类型 | 识别特征 |
|---------|---------|
| 中国邮政 rFBS | Sheet 含 `Russia-China CP` |
| 评分 rFBS（其他公司）| Sheet 含 `CHINA rFBS` |
| CIS rFBS | Sheet 含 `KZ & BY` 或 `Other CIS` |
| FBP | Sheet 含 `CHINA FBP` |

**FBP 解析要点**：
- `Delivery Service` 列含 `Smart` → `is_smart=1`
- G列物流名称末尾含 `KZ` → `destination='KZ'`，含 `BY` → `destination='BY'`，否则 `destination='RU'`
- 3PL/Delivery Service 列向上填充（合并单元格效果）
- 费率格式：`¥X + ¥Y/1 g` → `base_fee=X, continue_fee=Y, continue_unit='1g'`

---

### D5：定价结果分组 — 4 个 Tab，单次计算全部返回

**决策**：`calculate_pricing` 扩展为接收按分组分类的物流列表，一次计算返回4个分组结果，每组含 best_land / best_air。

**分组**：
1. `rfbs_ru`：rFBS + destination=RU
2. `rfbs_cis`：rFBS + destination IN (KZ/BY/KGZ/UZ/GE/AZ)，按国家进一步细分
3. `fbp_ru`：FBP + destination=RU
4. `fbp_cis`：FBP + destination IN (KZ/BY)

**Smart 标注**：在结果中，`is_smart=1` 的物流方式重点标注，不影响计算逻辑。

---

### D6：product.commission_rate → commission_category_id

**决策**：
- 精准模式：`commission_rate` 字段替换为 `commission_category_id`（外键，可空）
- 快速模式：保留 `commission_rate` 手动输入数值，不做类目选择
- 数据迁移：现有 `commission_rate` 值保留（快速模式用），新增 `commission_category_id` 列默认为 NULL

---

### D7：产品批量导入 — 前端列映射 + 后端清洗

**决策**：
1. 前端：上传 xlsx → 解析表头 → 用户拖拽/下拉映射列到产品字段
2. 后端：接收映射关系 + 数据行，执行清洗（字符串→数值）+ 重复检测
3. 重复检测：按产品名称匹配，返回冲突列表
4. 前端：展示冲突，用户逐条选择"覆盖"或"跳过"
5. 后端：提交最终确认后批量入库

---

### D8：Admin 订阅管理 — 新增3个专用端点

**决策**：在 `api/routes/admin.py` 中新增：
- `POST /api/admin/users/{user_id}/subscription/extend` — 调整到期时间（+/- 天数）
- `POST /api/admin/users/{user_id}/calculations/adjust` — 调整当日剩余次数（+/- 次数）
- `POST /api/admin/users/{user_id}/type` — 修改用户类型

**原因**：与现有 admin 路由风格一致；细粒度端点便于权限控制和日志记录。

## Risks / Trade-offs

- **[迁移风险] logistics 表现有36个用户数据**  
  → 迁移时新增列带默认值，不影响现有数据；Alembic 在本地验证后再推生产

- **[性能风险] 4分组计算量是原来4倍**  
  → 每组物流数量会相应减少（原来全量 → 分组后各为子集），总计算量相近

- **[前端复杂度] PricingPage.jsx 已是最大文件（56KB）**  
  → Tab 组件拆分，各 Tab 内容独立组件，避免单文件继续膨胀

- **[xlsx 解析脆弱性] 4种格式各有特殊结构**  
  → 严格按文件特征自动识别，解析失败返回详细错误信息给 Admin

- **[向后兼容] commission_rate 字段**  
  → 快速模式继续使用 commission_rate；精准模式新增 commission_category_id，两字段共存

## Migration Plan

1. Alembic 新增迁移：`commission_categories` 表、`logistics_pool` 表、`logistics` +5列、`products` +1列
2. 本地 `alembic upgrade head` 验证
3. 部署顺序：先后端（DB迁移 + API）→ 再前端（新页面上线）
4. 回滚：`alembic downgrade -1`；前端回滚 git revert

## Open Questions

（无，所有设计决策已通过用户确认）
