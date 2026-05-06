## ADDED Requirements

### Requirement: 物流列表操作按钮整洁布局
物流管理页面每条物流规则的操作区域 SHALL 使用下拉菜单（DropdownMenu）整合编辑、删除、转换运输方式操作，替代多按钮水平排列。

#### Scenario: 操作按钮使用下拉菜单
- **WHEN** 用户查看物流列表中的任一规则
- **THEN** 操作列 SHALL 显示一个"更多操作"按钮（MoreHorizontal 图标），点击后展开菜单包含：编辑、删除、转为空运/转为陆运

#### Scenario: 启用/禁用开关保留在行内
- **WHEN** 用户查看物流列表
- **THEN** 启用/禁用 Switch 组件 SHALL 保留在行内，不放入下拉菜单

### Requirement: 公共物流池删除全部功能正常工作
公共物流池的"删除全部"按钮 SHALL 成功删除所有记录，不显示错误。

#### Scenario: 成功删除所有物流池记录
- **WHEN** 管理员点击"删除全部"按钮并确认
- **THEN** 系统 SHALL 删除所有物流池记录并显示成功提示

#### Scenario: 删除后页面刷新
- **WHEN** 删除全部操作成功完成
- **THEN** 物流池列表 SHALL 刷新为空，总数显示为 0

### Requirement: 公共物流池查看详情 Dialog 布局清晰
查看详情 Dialog SHALL 以清晰、有组织的方式展示物流规则的所有字段。

#### Scenario: 详情 Dialog 字段分组展示
- **WHEN** 用户点击某条物流规则的"查看"按钮
- **THEN** Dialog SHALL 按逻辑分组展示字段（基本信息、价格限制、重量与尺寸、费用配置、特殊属性），每组有清晰的标题分隔

### Requirement: 公共物流池显示物流方式总数
公共物流池页面标题旁 SHALL 显示当前物流方式的总数。

#### Scenario: 标题旁显示总数
- **WHEN** 用户打开公共物流池页面
- **THEN** 页面标题旁 SHALL 显示物流方式总数（如"公共物流池 (128)"）

#### Scenario: 删除后总数更新
- **WHEN** 物流池中的记录被删除
- **THEN** 总数 SHALL 实时更新
