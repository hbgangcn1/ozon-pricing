## Why

当前从公共物流池导入私有物流时，没有检查用户套餐的物流规则上限限制。免费版用户（logistics_limit=1）和效率版用户（logistics_limit=3）在导入过多物流时会超出其套餐限制。需要在校oser导入前检查并提示用户。

## What Changes

- **新增导入前检查逻辑**：在从公共物流池导入私有物流时，先统计用户当前私有物流数量，计算导入后总数，与套餐限制比较
- **免费版限制**：logistics_limit=1，超出时提示"免费版物流规则上限是1条，无法导入更多物流"
- **效率版限制**：logistics_limit=3，超出时提示"效率版物流规则上限是3条，无法导入更多物流"
- **专业版及以上**：无限制（logistics_limit=-1 或更高）

## Capabilities

### New Capabilities

- `logistics-import-limit`: 新增物流导入限制检查功能，在导入前验证用户是否有足够的套餐配额

### Modified Capabilities

- 无 - 现有功能不涉及此检查逻辑

## Impact

- **受影响代码**：物流导入相关 API 或服务（需要找到具体实现位置）
- **依赖**：套餐的 `logistics_limit` 字段，用户当前私有物流数量统计
- **前端影响**：导入失败时显示错误提示
