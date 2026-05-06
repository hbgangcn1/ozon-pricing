## ADDED Requirements

### Requirement: 空数据静默处理
当公共物流池页面(LogisticsPoolPage.jsx)和佣金类目页面(CommissionCategoriesPage.jsx)从数据库加载数据时，如果返回空数据（空数组），系统 SHALL NOT 弹出任何错误提示信息。

#### Scenario: 物流池空数据
- **WHEN** 公共物流池页面加载时数据库中无物流池数据（API返回空数组）
- **THEN** 页面显示空状态UI（如空表格或Empty组件），不弹出"获取物流池内容失败"的错误消息

#### Scenario: 佣金类目空数据
- **WHEN** 佣金类目页面加载时数据库中无佣金类目数据（API返回空数组）
- **THEN** 页面显示空状态UI，不弹出"获取佣金类目失败"的错误消息

#### Scenario: 真实API错误仍需提示
- **WHEN** API返回HTTP错误状态码（4xx或5xx）
- **THEN** 系统 SHALL 弹出相应的错误提示信息
