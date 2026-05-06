## ADDED Requirements

### Requirement: 物流记录包含履约方式和目的地字段
系统 SHALL 在 logistics 表中新增5个字段：fulfillment_type（rfbs/fbp）、destination（目的地国家代码）、fbp_service_level、fbp_company、is_smart。现有记录默认 fulfillment_type='rfbs'，destination='RU'。

#### Scenario: 新建 rFBS 物流记录
- **WHEN** 用户创建一条物流记录，选择 fulfillment_type='rfbs'，destination='KZ'
- **THEN** 系统保存含这5个新字段的物流记录，destination 接受 RU/KZ/BY/KGZ/UZ/GE/AZ

#### Scenario: 新建 FBP 物流记录
- **WHEN** 用户创建一条物流记录，选择 fulfillment_type='fbp'，destination='BY'
- **THEN** 系统保存记录，destination 仅接受 RU/KZ/BY；fbp_service_level 接受 economy/standard/express/super_express

#### Scenario: 旧有物流记录向后兼容
- **WHEN** 系统读取 Alembic 迁移前创建的物流记录
- **THEN** fulfillment_type 默认为 'rfbs'，destination 默认为 'RU'，is_smart 默认为 0

#### Scenario: FBP Smart 物流标注
- **WHEN** 一条 FBP 物流记录的 is_smart=1
- **THEN** 前端在物流列表和计算结果中以醒目方式标注该条目为 Smart，优先于显示具体物流名称

#### Scenario: 取消自提/送货上门区分
- **WHEN** 用户查看或创建物流规则
- **THEN** 界面中不再展示自提/送货上门选项；fee_mode 字段不再含有 pudo/courier 语义区分

### Requirement: 物流列表按履约方式和目的地筛选
系统 SHALL 支持按 fulfillment_type 和 destination 过滤用户物流列表。

#### Scenario: 按履约方式筛选
- **WHEN** 前端请求 GET /api/logistics?fulfillment_type=fbp
- **THEN** 系统返回当前用户所有 fulfillment_type='fbp' 的物流记录

#### Scenario: 按目的地筛选
- **WHEN** 前端请求 GET /api/logistics?destination=KZ
- **THEN** 系统返回当前用户所有 destination='KZ' 的物流记录

### Requirement: FBP destination 约束
FBP 物流的 destination SHALL 只允许 RU、KZ、BY。Express 和 Super Express 服务级别 SHALL 只允许 destination='RU'。

#### Scenario: FBP Economy/Standard 可发 CIS
- **WHEN** 用户创建 fbp_service_level='economy' 或 'standard'、destination='KZ' 的 FBP 物流记录
- **THEN** 系统接受并保存该记录

#### Scenario: FBP Express 不可发 CIS
- **WHEN** 用户尝试创建 fbp_service_level='express'、destination='KZ' 的 FBP 物流记录
- **THEN** 系统返回 400 错误，提示 Express/Super Express 只支持 Russia
