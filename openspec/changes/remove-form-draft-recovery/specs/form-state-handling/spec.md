## ADDED Requirements

### Requirement: 前端不实现表单草稿自动持久化

系统 SHALL NOT 在前端任何位置自动将未提交的表单数据持久化到 `localStorage`、`sessionStorage`、`IndexedDB`、Cookie 或任何其他客户端存储介质。"自动"指无需用户主动点击"保存草稿"等显式动作即触发的写入行为。

本要求不限制：
- 认证态相关的存储（如 `authStore` 写入 `api_user` / `api_token`）
- 安全机制相关的存储（如 CSRF cookie）
- 用户主动触发的、与服务端协作的备份/恢复流程（如 SettingsPage 的数据库备份）

#### Scenario: 用户在表单中输入内容后未提交即关闭页面

- **WHEN** 用户在 RegisterPage / PricingPage / LogisticsPage 任一表单中输入内容
- **AND** 未点击提交即关闭标签页或导航至其他页面
- **THEN** 系统不在任何客户端存储介质中保留该表单的输入内容

#### Scenario: 用户输入触发 React 状态更新

- **WHEN** 用户在受本要求约束的页面中触发表单字段的 `onChange`
- **THEN** 系统不写入任何键名以 `draft:` 为前缀的 `sessionStorage` 或 `localStorage` 条目
- **AND** 系统不调用任何形式的"自动保存草稿"hook

### Requirement: 前端不实现表单草稿自动恢复弹窗

系统 SHALL NOT 在页面挂载时弹出任何询问"是否恢复上次未完成填写"的模态框、Toast、横幅或其他 UI 元素。

#### Scenario: 用户重新进入曾经填写过表单的页面

- **WHEN** 用户进入 RegisterPage / PricingPage / LogisticsPage 任一页面
- **AND** 浏览器存储中可能存在历史遗留的 `draft:*` 键
- **THEN** 系统不读取这些键
- **AND** 系统不渲染任何带"检测到未完成的填写"或类似含义的对话框
- **AND** 表单字段以默认值（空 / 静态默认值）显示

#### Scenario: 用户从过期会话状态返回登录页

- **WHEN** 用户因会话过期被重定向至 LoginPage
- **THEN** 登录页不承诺"登录后将恢复您的填写内容"
- **AND** 用户成功登录后系统不自动填充任何此前未提交的表单数据

### Requirement: 移除表单草稿机制相关代码资产

系统的前端代码库 SHALL NOT 包含以下文件：
- `frontend/src/hooks/useDraftPersist.js` 及其测试
- `frontend/src/components/DraftRestoreDialog.jsx` 及其测试

系统的前端代码库 SHALL NOT 在任何文件中：
- 引入（import）名为 `useDraftPersist` 的符号
- 引入（import）名为 `DraftRestoreDialog` 的符号
- 调用任何返回 `loadDraft` / `clearDraft` / `hasDraft` 接口三件套的 hook

#### Scenario: 代码库静态扫描

- **WHEN** 在 `frontend/src/` 下执行 `grep -r "useDraftPersist"` 或 `grep -r "DraftRestoreDialog"`
- **THEN** 不存在任何匹配
- **AND** 不存在任何引用 `draft:` 前缀 sessionStorage 键的代码

#### Scenario: 前端构建与测试

- **WHEN** 执行 `npm run build` 与 `npm run test`
- **THEN** 构建成功
- **AND** 全部测试通过（不应存在因移除 useDraftPersist 而残留的失败测试或反向断言）

### Requirement: 未来若需类似能力须经显式重新决策

如未来产品演进需要为任何表单场景提供"防数据丢失"能力，相关方案 MUST 通过新的 OpenSpec change 重新决策，并 SHOULD 优先考虑以下方向而非恢复旧的隐式自动持久化机制：
- 用户显式触发的"保存为草稿"按钮（与服务端 API 协作）
- 表单字段级的乐观提交（每改一个字段即落库）
- 离开页面前的浏览器原生 `beforeunload` 提示

本要求是产品/架构层面的约束声明，不对应运行时验证场景。

#### Scenario: 设计评审引用本要求

- **WHEN** 任何新 change 提出"为表单 X 添加自动保存草稿"
- **THEN** 评审者引用本 capability 作为前置背景，要求新方案明确说明与本 capability 的关系（修改 / 替换 / 例外）
