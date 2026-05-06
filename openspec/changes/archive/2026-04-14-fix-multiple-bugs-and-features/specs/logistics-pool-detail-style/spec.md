## ADDED Requirements

### Requirement: 物流池详情弹窗使用全站主题变量
物流池详情 Dialog 组件 SHALL 使用 shadcn/ui CSS 变量（如 `hsl(var(--background))`、`hsl(var(--card))`、`hsl(var(--border))`）替代硬编码的 slate 颜色类，与全站 dark theme 保持一致。

#### Scenario: 弹窗背景色与全站一致
- **WHEN** 用户在公共物流池点击"查看"按钮打开物流详情
- **THEN** 弹窗的背景色、边框色、文字色均使用 CSS 变量，与网站整体 dark theme 风格一致

#### Scenario: 弹窗中各区块样式统一
- **WHEN** 弹窗内显示物流各属性分区（基本信息、费率、尺寸限制等）
- **THEN** 各分区使用 `card`/`muted` 等 shadcn/ui 语义色类，hover 效果使用 `accent` 色
