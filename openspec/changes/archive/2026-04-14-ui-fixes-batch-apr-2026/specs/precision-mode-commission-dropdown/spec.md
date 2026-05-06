## ADDED Requirements

### Requirement: 精准模式产品编辑使用佣金类目下拉菜单
精准模式中产品编辑对话框的佣金部分 SHALL 使用佣金类目下拉菜单（Select）替代手动输入框（RateInput），用户通过选择类目来决定产品佣金。

#### Scenario: 打开精准模式产品编辑对话框
- **WHEN** 用户在精准模式中点击产品列表中某产品的编辑按钮
- **THEN** 产品编辑对话框的佣金区域 MUST 显示为佣金类目下拉菜单（Select 组件）
- **AND** 下拉菜单 MUST 列出所有可用的佣金类目（从佣金类目列表接口获取）

#### Scenario: 选择佣金类目
- **WHEN** 用户从下拉菜单中选择一个佣金类目
- **THEN** 产品的 `commission_category_id` MUST 更新为所选类目的ID
- **AND** 保存产品时 MUST 将 `commission_category_id` 提交到后端

#### Scenario: 产品已有佣金类目
- **WHEN** 打开已设置 `commission_category_id` 的产品编辑对话框
- **THEN** 下拉菜单 MUST 默认选中该产品对应的佣金类目

#### Scenario: 产品无佣金类目
- **WHEN** 打开未设置 `commission_category_id` 的产品编辑对话框
- **THEN** 下拉菜单 MUST 显示为未选中状态（placeholder 提示"选择佣金类目"）
