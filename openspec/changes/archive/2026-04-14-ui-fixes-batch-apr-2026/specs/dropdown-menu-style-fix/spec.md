## ADDED Requirements

### Requirement: 下拉菜单具有不透明背景
`DropdownMenuContent` 组件 SHALL 使用项目已定义的 Tailwind 颜色变量渲染不透明背景，不得使用未在 `tailwind.config.js` 中定义的颜色类。

#### Scenario: 物流管理页面打开更多操作菜单
- **WHEN** 用户在物流管理页面点击 "..." 按钮
- **THEN** 弹出的下拉菜单 MUST 具有 `bg-surface-container` 不透明背景色，文字清晰可读

#### Scenario: 下拉菜单项获得焦点
- **WHEN** 用户将鼠标悬停在菜单项上或使用键盘导航
- **THEN** 菜单项 MUST 显示 `bg-surface-high` 高亮背景，文字颜色为 `text-text-primary`

### Requirement: 下拉菜单分隔线可见
`DropdownMenuSeparator` SHALL 使用项目已定义的颜色变量渲染分隔线。

#### Scenario: 菜单含分隔线
- **WHEN** 下拉菜单中包含分隔线元素
- **THEN** 分隔线 MUST 使用 `bg-border` 或 `bg-surface-high` 颜色可见渲染
