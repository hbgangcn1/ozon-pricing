## 1. UI 组件实现

- [x] 1.1 在 `frontend/src/pages/PlanManagementPage.jsx` 的 `PlanEditForm` 组件中，为"计算次数"字段添加 Switch 开关，checked 状态绑定 `formData.calcLimit === -1`
- [x] 1.2 为"物流模板"字段添加同样的 Switch 开关，checked 状态绑定 `formData.logisticsTemplate === -1`
- [x] 1.3 Switch 开启时隐藏对应的数值 Input 输入框，关闭时显示

## 2. 状态管理逻辑

- [x] 2.1 在 `handleNumberChange` 函数中处理 Switch 切换逻辑：开启时保存当前值到 `_prev*` 字段并设为 `-1`，关闭时从 `_prev*` 恢复（兜底默认值 calcLimit: 10, logisticsTemplate: 3）
- [x] 2.2 表单初始化时，若 `calcLimit === -1` 则 `_prevCalcLimit` 设为默认值 `10`；`logisticsTemplate` 同理设为 `3`

## 3. 提交清理

- [x] 3.1 在 `handleSubmit` 中通过 `localPlanToApi` 映射时过滤 `_prev*` 前缀字段，确保不发送给后端
