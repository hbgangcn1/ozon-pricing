## ADDED Requirements

### Requirement: 产品批量导入支持全部行
系统 SHALL 在产品导入 preview 端点返回 Excel 文件中的全部数据行（不限于前10行）。confirm 端点 SHALL 处理全部提交的行数据。

#### Scenario: 预览包含全部行数据
- **WHEN** 用户上传包含 184 行产品数据的 Excel 文件到 `POST /api/products/import/preview`
- **THEN** 响应中 `preview_rows` 包含全部 184 条数据，`columns` 包含所有列名

#### Scenario: 确认导入处理全部行
- **WHEN** 前端将全部 184 条行数据发送到 `POST /api/products/import/confirm`
- **THEN** 系统处理全部 184 条数据，`imported` + `skipped` + `errors` 总数等于 184

#### Scenario: 前端预览界面显示摘要
- **WHEN** 用户上传 Excel 后进入预览界面
- **THEN** 前端显示前 N 行作为预览表格，并显示"共 M 条数据"的总数提示

### Requirement: 货币字段正确映射
产品导入中的"货币"列 SHALL 映射到产品的 `currency` 字段。该字段用于标识产品价格的货币单位（如 CNY、RUB），在定价计算中用于汇率换算。

#### Scenario: 货币字段成功映射
- **WHEN** Excel 中某行"货币"列值为 "CNY"
- **THEN** 导入后该产品的 `currency` 字段值为 "CNY"
