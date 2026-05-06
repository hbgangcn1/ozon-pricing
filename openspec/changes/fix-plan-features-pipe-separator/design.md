## Context

订阅管理页面的方案卡片渲染功能描述时，每条功能应独立一行并带绿色对号图标。当前 DB 中 `plans.features` 字段以 `|` 分隔存储（如 `仅限快速模式|每日10次计算|1个物流模板|基础功能`），但 API 层 `_to_plan_response` 使用 `split(",")` 分割，导致整个字符串作为单条功能返回，前端只显示一个对号。

涉及文件：
- `api/routes/subscriptions.py` — `_to_plan_response`（第90-92行）、`create_plan_route`（第169行）、`update_plan_route`（第187-188行）
- `frontend/src/pages/PlanManagementPage.jsx` — `PlanEditForm.handleSubmit`（第160-162行）、textarea placeholder

## Goals / Non-Goals

**Goals:**
- API 层正确按 `|` 分割 features 字段，返回多元素数组
- API 层创建/更新方案时按 `|` 合并 features 数组写入 DB
- 方案管理编辑表单的 features 输入框按 `|` 分割/合并，placeholder 提示同步更新
- 无需修改 DB 数据（已经是 `|` 分隔）
- 无需修改前端 SubscriptionPage.jsx 渲染逻辑（已正确 `.map` + `CheckCircle`）

**Non-Goals:**
- 不做 DB 数据迁移
- 不改变 API 响应格式（仍然返回 `features: List[str]`）
- 不处理 `description` 字段（仅 features 有此问题）

## Decisions

### 决策 1：统一使用 `|` 作为唯一分隔符

**选择**: `features.split("|")` 替代 `features.split(",")`

**备选方案**: 用 `re.split(r'[,|]', features)` 同时支持逗号和竖线。

**理由**: 管理员确认统一使用 `|` 分隔，现有 DB 数据全部为 `|` 分隔，无需兼容逗号。单一分隔符更简洁，避免歧义。

### 决策 2：修改在 API 层而非前端

**选择**: 在后端 `_to_plan_response` 处理分割。

**备选方案**: 前端渲染时对每个 feature 字符串再按 `|` 拆分。

**理由**: API 负责数据转换是正确的职责边界。前端已经正确处理 `List[str]`，不需要知道 DB 存储格式。

## Risks / Trade-offs

- **[风险] 方案管理表单未同步修改** → 编辑后保存会用逗号合并写回 DB，下次读取又变成单条。**缓解**: 必须同步修改 PlanEditForm 的 split/join 逻辑。
- **[风险] features 文本本身包含 `|` 字符** → 会被错误分割。**缓解**: 当前数据无此情况，且管理员已知 `|` 是分隔符。风险极低。
