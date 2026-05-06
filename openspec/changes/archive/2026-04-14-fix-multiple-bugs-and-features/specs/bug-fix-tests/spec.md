## ADDED Requirements

### Requirement: 所有修复配套单元测试
每个 bug 修复 SHALL 配套至少一个单元测试，验证修复前行为（回归测试）和修复后行为。

#### Scenario: format_result 单元测试
- **WHEN** 运行 `pytest tests/` 中的 pricing 相关测试
- **THEN** 测试覆盖 `suggested_price=0`、`suggested_price=None`、`suggested_price>0` 三种情况

#### Scenario: 产品导入 preview 单元测试
- **WHEN** 运行 `pytest tests/` 中的 products import 测试
- **THEN** 测试验证 preview 端点返回全部行（非前10行）

#### Scenario: FBP Smart 检测单元测试
- **WHEN** 运行 `pytest tests/` 中的 xlsx_import 测试
- **THEN** 测试验证 service 列和 name 列中 Smart 关键词均被正确识别

### Requirement: 关键修复配套集成测试
涉及 API 端点修改的修复 SHALL 配套集成测试，通过 TestClient 模拟完整请求-响应流程。

#### Scenario: 删除全部物流池集成测试
- **WHEN** 运行集成测试
- **THEN** 测试通过 TestClient 发送 `DELETE /api/logistics-pool/all`，验证返回200和正确的删除数量

#### Scenario: 精准模式定价集成测试
- **WHEN** 运行集成测试
- **THEN** 测试通过 TestClient 发送精准模式定价请求，验证返回结果中 `is_available` 正确

### Requirement: UI 修复配套 E2E 测试
涉及前端交互的修复 SHALL 配套 Playwright E2E 测试，验证用户操作流程完整性。

#### Scenario: 物流池删除全部 E2E 测试
- **WHEN** 运行 Playwright E2E 测试
- **THEN** 测试模拟管理员用户登录 → 进入公共物流池 → 点击删除全部 → 验证列表清空

#### Scenario: 产品批量导入 E2E 测试
- **WHEN** 运行 Playwright E2E 测试
- **THEN** 测试模拟用户上传 Excel → 预览界面显示总数 → 确认导入 → 验证产品列表数量正确
