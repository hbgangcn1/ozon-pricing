## ADDED Requirements

### Requirement: 限价字段统一为人民币
所有物流规则的价格限制字段 SHALL 统一使用人民币(CNY)计价。数据库中移除卢布(RUB)和美元(USD)相关的限价字段。

#### Scenario: 数据库字段变更
- **WHEN** 系统运行数据库迁移
- **THEN** logistics表和logistics_pool表的限价字段统一为price_limit_cny（上限）和price_min_cny（下限），移除price_limit_rub、price_limit_usd及price_limit_currency、price_min_currency字段

### Requirement: 移除货币单位下拉菜单
物流编辑页面 SHALL 移除货币单位选择下拉菜单（之前可选RUB/USD）。

#### Scenario: 编辑表单无货币选择
- **WHEN** 用户编辑物流规则的限价设置
- **THEN** 表单中不存在货币单位下拉菜单，所有限价默认为人民币

### Requirement: 限价标签改为人民币单位
价格限制字段的标签 SHALL 明确标注人民币单位。

#### Scenario: 标签显示
- **WHEN** 用户查看物流规则编辑表单的限价字段
- **THEN** 字段标签显示为"价格上限（元）"和"价格下限（元）"

### Requirement: 定价计算限价检查使用CNY
定价计算引擎在执行限价检查时 SHALL 直接使用CNY限价值比较，不再通过汇率转换。

#### Scenario: 限价检查无汇率转换
- **WHEN** 定价计算执行价格上下限检查
- **THEN** 直接将计算得出的CNY价格与物流规则的CNY限价进行比较，不调用汇率服务进行币种转换

#### Scenario: 限价检查正确性
- **WHEN** 某物流规则设置价格上限（元）为100，计算得出CNY价格为120
- **THEN** 该物流规则因价格超出上限而被过滤排除

### Requirement: Excel导入只导入CNY限价
Excel导入物流池时 SHALL 只读取人民币限价列，忽略卢布、美元、欧元限价列。

#### Scenario: China Post Excel导入
- **WHEN** 导入China Post rFBS的Excel文件
- **THEN** 系统读取"Shipment cost limit / min CNY"（列12）和"Shipment cost limit / max CNY"（列13）作为限价值，忽略RUB/USD/EUR列

#### Scenario: FBP Excel导入
- **WHEN** 导入FBP物流的Excel文件
- **THEN** 系统读取"Shipment cost limit / min-max CNY"（列15）解析为限价上下限，忽略RUB/USD/EUR列

#### Scenario: CIS Excel导入
- **WHEN** 导入CIS物流的Excel文件
- **THEN** 系统读取"Shipment cost limit / min-max CNY"列解析为限价上下限，忽略RUB/USD/EUR列

#### Scenario: Russia rFBS Excel导入
- **WHEN** 导入发往俄罗斯的rFBS Excel文件（China_scoring格式，"CHINA rFBS"sheet）
- **THEN** 系统读取"Shipment cost limit / min-max CNY"（列13，即N列）解析为限价上下限，忽略RUB/USD/EUR列（注：Ч1/Ч2 sheet为评分数据不含限价，限价在"CHINA rFBS" sheet中）

### Requirement: 已有数据迁移
系统 SHALL 提供数据迁移方案，将现有物流规则的RUB/USD限价按当前汇率转换为CNY限价。

#### Scenario: 迁移脚本执行
- **WHEN** 运行限价数据迁移脚本
- **THEN** 所有已有物流规则的RUB限价按当前卢布汇率转换为CNY值，USD限价按当前美元汇率转换为CNY值，结果存入CNY限价字段
