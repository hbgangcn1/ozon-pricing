## ADDED Requirements

### Requirement: 导入错误文字使用小号字体
批量导入产品成功后的结果面板中，错误信息文字 SHALL 使用小号字体（`text-sm`），不得使用大号字体突出显示。

#### Scenario: 导入完成后显示错误计数
- **WHEN** 用户完成批量导入产品操作且存在部分错误
- **THEN** 错误计数文字 MUST 使用 `text-sm` 字号显示，而非 `text-3xl`
- **AND** 错误文字颜色保持 `text-status-error` 红色不变

#### Scenario: 导入完成无错误
- **WHEN** 用户完成批量导入产品操作且无任何错误
- **THEN** 错误区域 MUST 显示 "0" 或不显示错误区块
