## ADDED Requirements

### Requirement: 佣金类目列表管理
系统 SHALL 维护一个全局扁平的佣金类目列表，每个类目包含名称和3个价格层级（≤1500 RUB、1500-5000 RUB、>5000 RUB）对应的 FBP 佣金率（小数，如 0.08 代表 8%）。rFBS 佣金率 SHALL 等于对应 FBP 率 + 0.01，不单独存储。

#### Scenario: 创建新佣金类目
- **WHEN** Admin 提交包含名称、tier1_rate、tier2_rate、tier3_rate 的新类目请求
- **THEN** 系统创建类目记录，返回含 id 的类目对象，HTTP 201

#### Scenario: 查询类目列表
- **WHEN** 任意已认证用户请求 GET /api/commission-categories
- **THEN** 系统返回所有 is_active=1 的类目列表，含 id、name、fbp_tier1_rate、fbp_tier2_rate、fbp_tier3_rate

#### Scenario: 更新类目费率
- **WHEN** Admin 提交 PATCH /api/commission-categories/{id}，含新的费率值
- **THEN** 系统更新对应类目的费率字段，返回更新后的对象

#### Scenario: 删除（软删除）类目
- **WHEN** Admin 提交 DELETE /api/commission-categories/{id}
- **THEN** 系统将 is_active 设为 0（软删除），不物理删除，HTTP 200

#### Scenario: 类目名称唯一校验
- **WHEN** Admin 提交与已有类目名称重复的新建请求
- **THEN** 系统返回 400 错误，提示类目名称已存在

### Requirement: 按类目和售价计算佣金率
系统 SHALL 根据商品售价（RUB）和所选类目，自动选择对应层级的佣金率，rFBS 佣金率 = 选中层级的 FBP 率 + 0.01。

#### Scenario: 售价在 Tier 1（≤1500 RUB）
- **WHEN** 商品计算售价 ≤ 1500 RUB，且选定了某个佣金类目
- **THEN** 系统使用该类目的 fbp_tier1_rate；若为 rFBS 履约则使用 fbp_tier1_rate + 0.01

#### Scenario: 售价在 Tier 2（1500-5000 RUB）
- **WHEN** 商品计算售价 > 1500 且 ≤ 5000 RUB
- **THEN** 系统使用该类目的 fbp_tier2_rate（rFBS 则 +0.01）

#### Scenario: 售价在 Tier 3（>5000 RUB）
- **WHEN** 商品计算售价 > 5000 RUB
- **THEN** 系统使用该类目的 fbp_tier3_rate（rFBS 则 +0.01）

#### Scenario: 精准模式使用类目选择
- **WHEN** 用户在精准模式定价页面，使用下拉菜单选择佣金类目
- **THEN** 系统保存 commission_category_id 到产品记录，后续计算使用类目费率

#### Scenario: 快速模式保持手动输入
- **WHEN** 用户在快速模式输入佣金率数值
- **THEN** 系统使用手动输入的 commission_rate，不使用类目

### Requirement: 佣金类目管理页面
系统 SHALL 提供一个 Admin 专属的佣金类目管理页面，支持增删改查操作。

#### Scenario: Admin 访问佣金管理页面
- **WHEN** Admin 角色用户导航到佣金管理页面
- **THEN** 页面显示所有激活类目的列表，含名称和三层级费率

#### Scenario: 非 Admin 用户无法访问
- **WHEN** 非 Admin 用户尝试访问佣金管理页面或对应 API
- **THEN** 系统返回 403，页面显示无权限提示
