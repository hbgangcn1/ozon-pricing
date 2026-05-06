## ADDED Requirements

### Requirement: 产品导入 preview_rows 值类型安全
后端产品导入的 preview endpoint SHALL 确保 preview_rows 中所有值为 JSON 安全类型（str, int, float, bool, None），不包含 datetime、Decimal 或其他不可序列化类型。

#### Scenario: 包含日期列的 xlsx 文件正常解析
- **WHEN** 用户上传包含日期格式单元格的 xlsx 文件（如"定价与物流表不计抛.xlsx"）
- **THEN** preview endpoint SHALL 返回 200 OK，preview_rows 中的日期值被转为字符串

#### Scenario: 包含公式错误的 xlsx 文件正常解析
- **WHEN** 用户上传包含 #DIV/0! 等公式错误的 xlsx 文件
- **THEN** preview endpoint SHALL 返回 200 OK，错误值被转为空字符串或错误标记字符串

### Requirement: 前端产品导入列映射页面不崩溃
前端产品导入页面在进入列映射步骤（Step 2）时 SHALL 不因数据类型问题崩溃。

#### Scenario: 列映射页面正常渲染
- **WHEN** 后端返回 preview 数据后前端进入 Step 2
- **THEN** 列映射 UI SHALL 正常渲染，显示列名下拉选择器和预览表格

#### Scenario: 预览表格显示所有行
- **WHEN** 用户查看预览表格
- **THEN** 所有 preview_rows SHALL 正确显示，无空白行或错误
