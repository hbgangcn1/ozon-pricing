## ADDED Requirements

### Requirement: 单个物流导入限制检查
从物流池导入单个物流到用户私有物流时，系统 SHALL 检查用户当前私有物流数量是否超过套餐限制。如果当前数量已达上限，返回 HTTP 403 错误。

#### Scenario: 免费版用户导入第 2 条物流被拒绝
- **WHEN** 免费版用户（logistics_limit=1）已有 1 条私有物流，通过 `POST /api/logistics-pool/{pool_id}/add-to-my-logistics` 尝试导入第 2 条物流
- **THEN** 系统返回 HTTP 403 `{"detail": "免费版物流规则上限是1条，无法导入更多物流"}`

#### Scenario: 效率版用户导入第 4 条物流被拒绝
- **WHEN** 效率版用户（logistics_limit=3）已有 3 条私有物流，通过 `POST /api/logistics-pool/{pool_id}/add-to-my-logistics` 尝试导入第 4 条物流
- **THEN** 系统返回 HTTP 403 `{"detail": "效率版物流规则上限是3条，无法导入更多物流"}`

#### Scenario: 专业版用户导入无限制
- **WHEN** 专业版用户（logistics_limit=-1）已有任意数量私有物流，通过 `POST /api/logistics-pool/{pool_id}/add-to-my-logistics` 尝试导入更多物流
- **THEN** 系统返回 HTTP 200 `{"id": <new_logistics_id>}`

#### Scenario: 免费版用户导入第 1 条物流成功
- **WHEN** 免费版用户（logistics_limit=1）有 0 条私有物流，通过 `POST /api/logistics-pool/{pool_id}/add-to-my-logistics` 导入物流
- **THEN** 系统返回 HTTP 201 `{"id": <new_logistics_id>}`

### Requirement: 批量物流导入限制检查
从物流池批量导入物流到用户私有物流时，系统 SHALL 在导入前检查用户当前私有物流数量 + 拟导入数量是否超过套餐限制。如果会超出限制，返回 HTTP 403 错误。

#### Scenario: 免费版用户批量导入超限被拒绝
- **WHEN** 免费版用户（logistics_limit=1）已有 0 条私有物流，通过 `POST /api/logistics-pool/batch-add-to-my-logistics` 尝试一次性导入 3 条物流（ids=[1,2,3]）
- **THEN** 系统返回 HTTP 403 `{"detail": "免费版物流规则上限是1条，本次导入3条会超出限制，请分批导入"}`

#### Scenario: 效率版用户批量导入部分成功
- **WHEN** 效率版用户（logistics_limit=3）已有 1 条私有物流，通过 `POST /api/logistics-pool/batch-add-to-my-logistics` 尝试导入 2 条物流（ids=[1,2]）
- **THEN** 系统返回 HTTP 200 `{"added": 2, "not_found": [], "new_ids": [...], "errors": []}`

#### Scenario: 批量导入后正好达到限制
- **WHEN** 效率版用户（logistics_limit=3）已有 2 条私有物流，通过 `POST /api/logistics-pool/batch-add-to-my-logistics` 尝试导入 1 条物流
- **THEN** 系统返回 HTTP 200 `{"added": 1, ...}`

### Requirement: 物流限制信息来自套餐配置
系统的物流规则限制 SHALL 从用户当前订阅的套餐（Plan）中读取 `logistics_limit` 字段。如果用户未订阅任何套餐，默认 `logistics_limit=1`。

#### Scenario: 未订阅用户默认限制为 1
- **WHEN** 用户无订阅信息（subscription_type 为空或 null）
- **THEN** 系统使用 `logistics_limit=1` 进行检查
