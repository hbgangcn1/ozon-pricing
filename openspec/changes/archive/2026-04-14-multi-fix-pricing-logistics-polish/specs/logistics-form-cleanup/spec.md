## ADDED Requirements

### Requirement: 移除送货方式字段
物流规则编辑页面 SHALL 完全移除"送货方式"字段及其所有选项（送货上门、自提、未知）。

#### Scenario: 编辑表单无送货方式
- **WHEN** 用户点击物流规则的"编辑"按钮打开编辑页面
- **THEN** 编辑表单中不包含"送货方式"下拉菜单或任何相关选项

#### Scenario: 新建物流规则无送货方式
- **WHEN** 用户创建新的物流规则
- **THEN** 创建表单中不包含"送货方式"字段

### Requirement: 移除FBP服务等级字段
物流规则编辑页面 SHALL 移除"FBP服务等级"下拉菜单。该字段经确认不参与定价计算。

#### Scenario: 编辑表单无FBP服务等级
- **WHEN** 用户编辑物流规则
- **THEN** 编辑表单中不包含"FBP服务等级"下拉菜单

#### Scenario: 数据库字段保留
- **WHEN** FBP服务等级字段从UI移除后
- **THEN** 数据库中的fbp_service_level列 SHALL 保留不删除（降低风险），但不再通过UI设置新值
