## Why

`fix-pytest-xdist-isolation` 解除了事件循环类隔离故障后,清晰的 `-n0` 全量基线暴露出 **64 例 pre-existing 业务测试失败**(集中在 8 个文件)。这些失败长期被早期的 event-loop 噪声掩盖,导致回归测试始终红/黄,无法作为质量阀门;`add-pro-trial-overflow` Phase 8.1(`零失败零警告`)也因此被卡住。本次 change 专门清零这 64 例失败,把测试套件恢复到"严格绿基线",同时解锁 add-pro-trial-overflow 归档。

## What Changes

- **修复 26 例** `tests/test_api_routes.py` 失败(Admin / Auth / Logistics / Orders / Products 五个 Test 类)
- **修复 16 例** `tests/test_xlsx_import.py` 失败(China Post xlsx 解析相关)
- **修复 11 例** `tests/test_api_routes2.py` 失败(Pricing / Statistics / Subscriptions 三个 Test 类)
- **修复 4 例** `tests/test_logistics_pool_import_limit.py` 失败(Free / Efficiency / Professional 三层导入额度)
- **修复 3 例** `tests/test_integration_logistics_products.py` 失败(批量删除/列表过滤)
- **修复 2 例** `tests/test_db_users.py` 失败(lower-case 唯一索引)
- **修复 1 例** `tests/test_db_logistics_pool.py::test_upsert_pool_item_updates_existing_row_in_place`(已知 `assert 2 == 1` 测试 bug)
- **修复 1 例** `tests/test_api_logistics_pool_batch_add.py::test_batch_add_integrity_error_isolated`
- **每例失败先诊断"测试 bug vs 生产 bug"**:测试 bug 仅改 `tests/`;若暴露真实生产 bug,在同 change 内修复 production 代码并附 Priority 1-4 注释 justification
- **最终阀门**:`pytest -n0` 与 `pytest -n auto` 双双 0 failed / 0 warnings(剩余必须文档化为 explicit out-of-scope flaky)
- **解锁** `add-pro-trial-overflow` Phase 8.1 翻 `- [x]`(本 change 归档后由该 change 自身处理)

## Capabilities

### New Capabilities

- **test-quality-baseline**:工程能力域,把"全量回归严格绿基线"作为可被 spec 化、可被机器验证的工程契约。补充内容包括:`pytest -n0` 与 `pytest -n auto` 双双 0 failed / 0 warnings 的并发等价性、每例失败的"测试 bug vs 生产 bug"分类协议、剩余 explicit out-of-scope flaky 的文档化要求

### Modified Capabilities

- 无业务 spec 级行为变更。若诊断中发现某例失败实为生产 bug,该 bug 修复需要单独评估是否触达业务 capability spec(本 change 默认范围内的失败均归类为测试侧问题或低风险生产实现细节,不触动现有业务 capability spec)

## Impact

- **代码**:主要触达 `tests/` 子集(8 个文件);极少数情况下可能触达 production 模块(`api/routes/admin.py`、`api/routes/logistics.py`、`api/routes/pricing.py`、`api/routes/subscriptions.py`、`api/routes/statistics.py`、`db/users.py`、`db/logistics_pool.py`、`services/xlsx_import.py` 等)——任何 production 改动必须经过"测试 bug vs 生产 bug"诊断 + Priority 1-4 注释 justification + 单独 commit
- **依赖**:不引入新依赖
- **数据库**:不新增迁移
- **生产部署**:不需要;纯本地质量回归
- **CI**:本 change 完成后,后续部署的 `deploy.sh` 会更早地从 pytest 红线发现新缺陷
- **解锁的下游**:`add-pro-trial-overflow` Phase 8.1 + 8.2 + 8.6;后续任何依赖"绿基线"的回归门禁
