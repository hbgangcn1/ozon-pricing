## Context

当前 `POST /api/logistics-pool/{pool_id}/add-to-my-logistics` 和 `POST /api/logistics-pool/batch-add-to-my-logistics` 两个端点在添加物流时没有检查用户套餐的 `logistics_limit` 限制。

用户套餐的物流限制：
- 免费版 (free): `logistics_limit = 1`
- 效率版 (efficiency): `logistics_limit = 3`
- 专业版 (professional): `logistics_limit = -1` (无限制)
- 企业版 (enterprise): `logistics_limit = -1` (无限制)

## Goals / Non-Goals

**Goals:**
- 在导入前检查用户当前私有物流数量是否超过套餐限制
- 免费版用户只能拥有最多 1 条物流规则
- 效率版用户只能拥有最多 3 条物流规则
- 专业版及以上用户无限制

**Non-Goals:**
- 不修改物流删除逻辑（删除不受限制）
- 不修改单个物流创建逻辑（仅修改池导入）
- 不修改管理员导入公共池功能

## Decisions

### Decision 1: 在导入端点添加检查

**选择**：在 `add-to-my-logistics` 和 `batch-add-to-my-logistics` 端点添加物流限制检查

**理由**：
- 最小改动：只需修改这两个端点
- 逻辑清晰：导入时检查，与套餐限制关联

**实现方式**：
1. 获取用户订阅信息（通过 `get_user_with_subscription`）
2. 获取用户当前私有物流数量
3. 比较 `当前数量 + 导入数量` vs `logistics_limit`
4. 超出限制时返回错误

### Decision 2: 复用现有订阅获取函数

**选择**：使用 `get_user_with_subscription` 获取用户套餐信息

**理由**：
- 函数已存在且被其他端点使用
- 返回包含 `subscription_type` 和 `user_type`

### Decision 3: 获取用户物流数量

**选择**：通过 `get_logistics_by_filters` 获取用户物流总数

**理由**：
- 已有现成函数
- 返回包含 `total` 字段

## Risks / Trade-offs

[Risk] 并发导入可能导致超限 → **Mitigation**: 检查和插入不是原子操作，理论上存在竞态条件，但实际概率很低

[Risk] 批量导入时部分成功 → **Mitigation**: 批量导入中每条单独处理，一条失败不影响其他

## Open Questions

无
