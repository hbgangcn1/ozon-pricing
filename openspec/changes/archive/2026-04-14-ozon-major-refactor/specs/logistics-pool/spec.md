## ADDED Requirements

### Requirement: 全局物流池存储
系统 SHALL 维护一个全局 logistics_pool 表，包含与 logistics 表相同的费率/尺寸/重量字段，额外含 source_file（来源文件名）、imported_at（导入时间戳）、is_active（0/1）。物流池条目无 user_id，对所有用户共享。

#### Scenario: 查看物流池列表
- **WHEN** 已认证用户请求 GET /api/logistics-pool
- **THEN** 系统返回所有 is_active=1 的物流池条目列表，含所有字段

#### Scenario: Admin 激活/停用物流池条目
- **WHEN** Admin 提交 PATCH /api/logistics-pool/{id}，设置 is_active=0
- **THEN** 该条目从用户可见列表中隐藏，但不物理删除

### Requirement: Admin 批量导入4种xlsx格式到物流池
系统 SHALL 支持 Admin 上传4种固定格式的 xlsx 文件，自动识别格式类型并解析所有字段，包括时效、尺寸限制、重量限制、费率、称重方式、体积重量系数等。

#### Scenario: 自动识别文件格式
- **WHEN** Admin 上传一个 xlsx 文件
- **THEN** 系统检查 Sheet 名称：含 `Russia-China CP` → 中国邮政rFBS；含 `CHINA rFBS` → 评分rFBS；含 `KZ & BY` 或 `Other CIS` → CIS rFBS；含 `CHINA FBP` → FBP；无法识别则返回 400 错误说明原因

#### Scenario: 解析中国邮政 rFBS
- **WHEN** Admin 上传中国邮政格式文件
- **THEN** 系统从 `Russia-China CP` Sheet 行4起解析：服务名、时效（min_days/max_days）、重量范围、计费规则（base_fee + continue_fee/continue_unit）、allow_battery、allow_liquid 等字段，fulfillment_type='rfbs'，destination='RU'

#### Scenario: 解析评分 rFBS（多公司）
- **WHEN** Admin 上传评分 rFBS 文件
- **THEN** 系统从 `CHINA rFBS` Sheet 解析：Scoring Group、Service Level、3PL、Delivery Method、时效、费率格式（`¥X.X + ¥Y.YYY/1 g`）、Battery/Liquid/Tarification/VolumeWeight 等，fulfillment_type='rfbs'，destination='RU'

#### Scenario: 解析 CIS rFBS
- **WHEN** Admin 上传 CIS rFBS 文件
- **THEN** 系统解析 `KZ & BY (ENG)` Sheet（destination='KZ' 或 'BY'）和 `Other CIS` Sheet（destination='KGZ'/'UZ'/'GE'/'AZ'），fulfillment_type='rfbs'

#### Scenario: 解析 FBP
- **WHEN** Admin 上传 FBP 文件
- **THEN** 系统从 `CHINA FBP` Sheet 解析：3PL（向上填充）、Delivery Service（向上填充）、Service Level（向上填充）、Destination Country（E列 → destination: Russia→'RU', Kazakhstan→'KZ', Belarus→'BY'）、Delivery Method（G列）、时效、费率、Tarification、VolumeWeight 等；Delivery Service 含 "Smart" → is_smart=1；fbp_service_level 从 Delivery Service 名称中提取（economy/standard/express/super_express）

#### Scenario: 解析费率格式
- **WHEN** 系统遇到 `¥X + ¥Y/1 g` 或 `¥X.X + ¥Y.YYY/1 g` 格式的运费
- **THEN** 解析为 base_fee=X（人民币），continue_fee=Y，continue_unit='1g'，fee_mode='base_plus_continue'

#### Scenario: 解析时效格式
- **WHEN** 系统遇到 `"11-15"` 或 `"11–15"` 格式的时效
- **THEN** 解析为 min_days=11，max_days=15

#### Scenario: 导入结果报告
- **WHEN** Admin 上传文件成功解析
- **THEN** 系统返回导入报告：成功条数、跳过条数（无法解析的行）、错误详情列表

#### Scenario: 重复导入处理
- **WHEN** Admin 再次上传同一文件（同 source_file + delivery_method + destination）
- **THEN** 系统更新现有记录（upsert），不创建重复条目

### Requirement: 用户从物流池选择并加入个人规则
用户 SHALL 能够浏览物流池，选择条目加入自己的物流规则列表，并可在个人列表中修改所有参数。

#### Scenario: 从物流池添加到个人列表
- **WHEN** 用户选择一条物流池条目，点击"添加到我的物流"
- **THEN** 系统将该条目复制到 logistics 表，user_id=当前用户，保留所有原始参数

#### Scenario: 修改个人物流规则
- **WHEN** 用户对自己 logistics 表中的条目进行编辑（修改费率、尺寸限制等任意字段）
- **THEN** 系统保存修改，不影响物流池原始记录

#### Scenario: 物流池条目更新后个人规则不受影响
- **WHEN** Admin 更新物流池中某条目的费率
- **THEN** 已复制到用户 logistics 表的记录不自动更新（快照语义）
