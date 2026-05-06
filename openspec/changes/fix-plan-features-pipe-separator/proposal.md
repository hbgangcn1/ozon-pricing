## Why

订阅管理页面中，每个方案卡片的功能描述（如"仅限快速模式|每日10次计算|1个物流模板|基础功能"）显示为一整行带管道符的文本，只有一个绿色对号。原因是 DB 中 `features` 字段用 `|` 分隔，但 API 层 `_to_plan_response` 只按逗号 `,` 分割，导致整个字符串被当作单条功能返回给前端。管理员在方案管理中统一使用 `|` 分隔功能描述，需要 API 和方案管理页面都以 `|` 作为标准分隔符。

## What Changes

- API 层 `_to_plan_response` 的 features 分割逻辑从 `split(",")` 改为 `split("|")`
- API 层创建/更新方案时，features 的合并逻辑从 `",".join()` 改为 `"|".join()`
- 方案管理页面 `PlanManagementPage.jsx` 的 features 编辑表单：textarea 分割/合并逻辑从逗号改为 `|`，placeholder 提示文字同步更新

## Capabilities

### New Capabilities

_无新增能力_

### Modified Capabilities

- `plan-management-api`: features 字段的序列化/反序列化分隔符从逗号改为竖线 `|`，方案管理编辑表单的分割/合并逻辑同步变更

## Impact

- **后端**: `api/routes/subscriptions.py` — `_to_plan_response`、`create_plan_route`、`update_plan_route` 三处涉及 features 的 split/join 逻辑
- **前端**: `frontend/src/pages/PlanManagementPage.jsx` — `PlanEditForm` 中 features textarea 的 split/join 逻辑和 placeholder 文字
- **无 DB 变更**: 现有数据已经用 `|` 分隔，无需迁移
- **无 API 契约变更**: 前端接收的 `features: List[str]` 格式不变，只是数组元素从1个变为多个
