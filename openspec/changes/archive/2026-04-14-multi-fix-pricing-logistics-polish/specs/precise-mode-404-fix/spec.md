## ADDED Requirements

### Requirement: 精准模式计算正常返回
精准模式执行定价计算时 SHALL 正确返回计算结果，不返回404 Not Found错误。

#### Scenario: 正常计算流程
- **WHEN** 用户在精准模式中选择产品并执行定价计算
- **THEN** 系统返回定价结果，不出现"Not Found"错误

#### Scenario: 端点路径正确
- **WHEN** 前端调用精准模式定价API
- **THEN** 请求URL与后端路由定义完全匹配，API正确注册

#### Scenario: 产品不存在时的友好错误
- **WHEN** 精准模式计算引用了不存在的产品ID
- **THEN** 系统返回明确的错误提示（如"产品不存在"），而非通用的"Not Found"
