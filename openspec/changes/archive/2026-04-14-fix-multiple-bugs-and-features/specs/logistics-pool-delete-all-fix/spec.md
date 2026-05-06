## ADDED Requirements

### Requirement: 删除全部物流池数据接口正常工作
系统 SHALL 确保 `DELETE /api/logistics-pool/all` 路由正确响应，返回删除条数。路由定义 MUST 位于 `/{pool_id}` 参数化路由之前，防止路径匹配冲突。

#### Scenario: 管理员删除全部物流池数据
- **WHEN** 管理员用户发送 `DELETE /api/logistics-pool/all` 请求
- **THEN** 系统删除所有物流池数据并返回 `{"deleted": N}`（N为删除条数），HTTP状态码200

#### Scenario: 非管理员尝试删除
- **WHEN** 普通用户发送 `DELETE /api/logistics-pool/all` 请求
- **THEN** 系统返回 HTTP 403 Forbidden

#### Scenario: 前端删除全部按钮触发正确请求
- **WHEN** 用户在公共物流池页面点击"删除全部"并确认
- **THEN** 前端发送 `DELETE /api/logistics-pool/all` 请求，成功后刷新列表
