# Tasks: fix-preexisting-test-failures

> 修复目标:`pytest -n0` 与 `pytest -n auto` 双双 0 failed / 0 warnings。
>
> 每个具体测试任务的执行节奏:**复现 → 二分诊断(测试 bug vs 生产 bug) → 修复 → 单测/同文件回归绿**(详见 design.md D1)。
>
> Production 改动必须遵守 design.md D2(Priority 1-4 注释 justification + 独立 commit)。
>
> 本 change 严禁修改测试隔离基础设施(design.md D6)。

## Phase 0: 根因修复 — 跨文件 `app.dependency_overrides` 污染(已完成)

- [x] 0.1 二分定位 polluter 文件:`test_api_logistics_pool_batch_add.py:106` 的 `overridden_app` fixture teardown 调 `app.dependency_overrides.clear()`,清掉了 `test_api_routes.py:39-41` / `test_api_routes2.py:24-26` 的模块级 override
- [x] 0.2 Oracle 决策(bg_43420b13):选 Option E — 把模块级 override 改成 function-scoped autouse fixture + `monkeypatch.setitem` 自动恢复
- [x] 0.3 应用补丁:`tests/test_api_routes.py` + `tests/test_api_routes2.py` — 删除模块级 3 行 + 新增 `_mock_auth_dependencies` autouse fixture(带 Priority 1 必要注释解释跨文件污染机制)
- [x] 0.4 全量 `pytest -n0` 回归验证:64 fail → **28 fail**(消除 36 例);test_api_routes 26 例全清,test_api_routes2 11→1 例,test_logistics_pool_import_limit 残留 4 例由 fixture 改回(symptom 一致),test_xlsx_import 16 例 / test_integration_logistics_products 3 例 / test_db_users 2 例 / test_db_logistics_pool 1 例 / test_api_logistics_pool_batch_add 1 例 — 与原报告一致

## Phase 1: 修复 `tests/test_api_routes.py`(26 例 → Phase 0 全部清零)

- [x] 1.1 修复 `TestAdmin::test_create_admin_user` - QA: `pytest -n0 tests/test_api_routes.py::TestAdmin::test_create_admin_user -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.2 修复 `TestAdmin::test_delete_admin_user` - QA: `pytest -n0 tests/test_api_routes.py::TestAdmin::test_delete_admin_user -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.3 修复 `TestAdmin::test_delete_superadmin_blocked` - QA: `pytest -n0 tests/test_api_routes.py::TestAdmin::test_delete_superadmin_blocked -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.4 修复 `TestAdmin::test_get_users` - QA: `pytest -n0 tests/test_api_routes.py::TestAdmin::test_get_users -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.5 修复 `TestAdmin::test_reset_password` - QA: `pytest -n0 tests/test_api_routes.py::TestAdmin::test_reset_password -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.6 修复 `TestAdmin::test_update_admin_user` - QA: `pytest -n0 tests/test_api_routes.py::TestAdmin::test_update_admin_user -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.7 修复 `TestAuth::test_change_password_missing_user_returns_401` - QA: `pytest -n0 tests/test_api_routes.py::TestAuth::test_change_password_missing_user_returns_401 -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.8 修复 `TestAuth::test_change_password_success` - QA: `pytest -n0 tests/test_api_routes.py::TestAuth::test_change_password_success -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.9 修复 `TestAuth::test_change_password_wrong_current` - QA: `pytest -n0 tests/test_api_routes.py::TestAuth::test_change_password_wrong_current -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.10 修复 `TestAuth::test_me` - QA: `pytest -n0 tests/test_api_routes.py::TestAuth::test_me -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.11 修复 `TestLogistics::test_batch_delete_empty` - QA: `pytest -n0 tests/test_api_routes.py::TestLogistics::test_batch_delete_empty -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.12 修复 `TestLogistics::test_batch_delete_logistics` - QA: `pytest -n0 tests/test_api_routes.py::TestLogistics::test_batch_delete_logistics -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.13 修复 `TestLogistics::test_delete_logistics_not_found` - QA: `pytest -n0 tests/test_api_routes.py::TestLogistics::test_delete_logistics_not_found -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.14 修复 `TestLogistics::test_delete_logistics_success` - QA: `pytest -n0 tests/test_api_routes.py::TestLogistics::test_delete_logistics_success -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.15 修复 `TestLogistics::test_get_logistics_by_id` - QA: `pytest -n0 tests/test_api_routes.py::TestLogistics::test_get_logistics_by_id -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.16 修复 `TestLogistics::test_get_logistics_by_id_not_found` - QA: `pytest -n0 tests/test_api_routes.py::TestLogistics::test_get_logistics_by_id_not_found -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.17 修复 `TestLogistics::test_get_logistics_list` - QA: `pytest -n0 tests/test_api_routes.py::TestLogistics::test_get_logistics_list -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.18 修复 `TestOrders::test_get_orders_empty` - QA: `pytest -n0 tests/test_api_routes.py::TestOrders::test_get_orders_empty -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.19 修复 `TestOrders::test_get_orders_with_data` - QA: `pytest -n0 tests/test_api_routes.py::TestOrders::test_get_orders_with_data -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.20 修复 `TestProducts::test_create_product` - QA: `pytest -n0 tests/test_api_routes.py::TestProducts::test_create_product -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.21 修复 `TestProducts::test_delete_product_not_found` - QA: `pytest -n0 tests/test_api_routes.py::TestProducts::test_delete_product_not_found -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.22 修复 `TestProducts::test_delete_product_success` - QA: `pytest -n0 tests/test_api_routes.py::TestProducts::test_delete_product_success -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.23 修复 `TestProducts::test_get_product_found` - QA: `pytest -n0 tests/test_api_routes.py::TestProducts::test_get_product_found -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.24 修复 `TestProducts::test_get_product_not_found` - QA: `pytest -n0 tests/test_api_routes.py::TestProducts::test_get_product_not_found -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.25 修复 `TestProducts::test_get_products` - QA: `pytest -n0 tests/test_api_routes.py::TestProducts::test_get_products -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.26 修复 `TestProducts::test_update_product` - QA: `pytest -n0 tests/test_api_routes.py::TestProducts::test_update_product -x --tb=short` exit 0  # closed by Phase 0 root-cause fix (auth dependency override pollution)
- [x] 1.1~1.26 由 Phase 0 根因修复一并解决(原 401 全部消失)
- [x] 1.27 文件级关闭阀:`pytest -n0 tests/test_api_routes.py --tb=short` 报告 0 failed / 0 warnings;再 `pytest -n auto tests/test_api_routes.py --tb=short` 同样 0 failed / 0 warnings  # closed by Phase 0 root-cause fix (auth dependency override pollution)

## Phase 2: 修复 `tests/test_xlsx_import.py`(16 例)

- [x] 2.1 修复 `test_china_post_air_delivery_rows_are_air_and_ground_delivery_rows_are_land` — re-target 4 row lookups to 30_04_26 analogs (OZON Standard/Economy + ePacket Kazakhstan + ePacket Economy Track Kazakhstan)
- [x] 2.2 修复 `test_china_post_base_mode_when_i_column_zero` — `PUDO Standard` → `OZON Standard`
- [x] 2.3 `test_china_post_cny_dash_means_zero` — already passes against 30_04_26 (epacket rows with price_limit=0.0 still present)
- [x] 2.4 修复 `test_china_post_cny_max_from_m_column` — `PUDO Standard` → `OZON Standard`
- [x] 2.5 修复 `test_china_post_cny_min_from_l_column` — `PUDO Standard` → `OZON Standard`
- [x] 2.6 ~~`test_china_post_conditional_volume_eems`~~ DELETED (Oracle bg_c1b01e6b Option E3) — eEMS row retired by Ozon; parser branch covered by `test_parse_size_fields_unit_eems` unit test
- [x] 2.7 ~~`test_china_post_eems_size_standard1`~~ DELETED (Oracle E3) — same rationale
- [x] 2.8 修复 `test_china_post_epacket_cylinder_limits` — `ePacket Super Express` → `ePacket Kazakhstan` (cylinder fields 104/90/14/11/17/11 identical)
- [x] 2.9 ~~`test_china_post_first_weight_mode_eems`~~ DELETED (Oracle E3) — eEMS first_weight branch unreachable; no fee_mode=first_weight row in 30_04_26
- [x] 2.10 ~~`test_china_post_first_weight_mode_eparcel`~~ DELETED (Oracle E3) — eParcel removed; parser branch survives via direct logic, no integration coverage needed
- [x] 2.11 `test_china_post_physical_weight_rows` — already passes (all 9 rows have volume_mode=none)
- [x] 2.12 修复 `test_china_post_simple_size_limits` — `PUDO Standard` → `OZON Standard`
- [x] 2.13 `test_detect_format_matches_reference_workbooks[HELP_ePacket_AM_AZ_UZ]` — already passes (file kept for format detection only)
- [x] 2.14 `test_detect_format_rejects_legacy_china_post_workbook` — already passes (synthesized fixture in Phase 0)
- [x] 2.15 修复 `test_parse_file_china_post_parses_dual_sheet_destinations` — `len==14` → `9`, histogram → `{RU:2, KZ:2, BY:2, AM:1, UZ:1, AZ:1}`
- [x] 2.16 修复 `test_parse_file_china_post_returns_expected_core_fields` — `PUDO Standard` → `OZON Standard` (all field assertions match exactly)
- [x] 2.17 文件级关闭阀:`pytest -n0 tests/test_xlsx_import.py --tb=short` → **52 passed in 9.54s, 0 failed**

> **Oracle decision bg_c1b01e6b (E3)**: 删除 4 个绑定已退役 China Post 旧版 eEMS/eParcel 行的 xlsx 集成测试。这些行在当前唯一有效 fixture `China_post_30_04_26_1777887104.xlsx` 中不存在;相关 parser 分支仍由 `_parse_size_fields` 单元测试覆盖,删除的是过期 fixture 断言,不是删除解析能力覆盖。不新增 skip,D5 cap 不变。

## Phase 3: 修复 `tests/test_api_routes2.py`(11 例)

- [x] 3.1 修复 `TestPricing::test_calculate_detailed_no_product_data_no_id` - QA: 单测 pytest -n0 -x exit 0  # closed by Phase 0 root-cause fix
- [x] 3.2 修复 `TestPricing::test_calculate_detailed_with_product_data_no_id` - QA: 单测 pytest -n0 -x exit 0  # closed by Phase 0 root-cause fix
- [x] 3.3 修复 `TestPricing::test_calculate_fast_mode` - QA: 单测 pytest -n0 -x exit 0  # closed by 5th-decorator fix in tests/test_api_routes2.py mocking decrement_user_calculations
- [x] 3.4 修复 `TestStatistics::test_active_users` - QA: 单测 pytest -n0 -x exit 0  # closed by Phase 0 root-cause fix
- [x] 3.5 修复 `TestStatistics::test_admin_logs` - QA: 单测 pytest -n0 -x exit 0  # closed by Phase 0 root-cause fix
- [x] 3.6 修复 `TestStatistics::test_login_logs` - QA: 单测 pytest -n0 -x exit 0  # closed by Phase 0 root-cause fix
- [x] 3.7 修复 `TestStatistics::test_overview` - QA: 单测 pytest -n0 -x exit 0  # closed by Phase 0 root-cause fix
- [x] 3.8 修复 `TestStatistics::test_retention` - QA: 单测 pytest -n0 -x exit 0  # closed by Phase 0 root-cause fix
- [x] 3.9 修复 `TestStatistics::test_revenue` - QA: 单测 pytest -n0 -x exit 0  # closed by Phase 0 root-cause fix
- [x] 3.10 修复 `TestSubscriptions::test_get_current_subscription` - QA: 单测 pytest -n0 -x exit 0  # closed by Phase 0 root-cause fix
- [x] 3.11 修复 `TestSubscriptions::test_get_current_subscription_not_found` - QA: 单测 pytest -n0 -x exit 0  # closed by Phase 0 root-cause fix
- [x] 3.1~3.2,3.4~3.11 由 Phase 0 根因修复一并解决;残留仅 3.3 `test_calculate_fast_mode`(403 而非 401,与 auth 污染无关,需独立诊断)
- [x] 3.12 文件级关闭阀:`pytest -n0 tests/test_api_routes2.py --tb=short` 0 failed / 0 warnings;`pytest -n auto tests/test_api_routes2.py --tb=short` 同样  # closed by Phase 0 root-cause fix

## Phase 4: 修复 `tests/test_logistics_pool_import_limit.py`(4 例)

- [x] 4.1 修复 `TestLogisticsBatchImportLimit::test_batch_import_within_limit_succeeds` - QA: 单测 pytest -n0 -x exit 0  # closed by tests/test_logistics_pool_import_limit.py upgrade-helper swaps (8 sites)
- [x] 4.2 修复 `TestLogisticsImportLimitEfficiencyTier::test_efficiency_user_third_import_succeeds` - QA: 单测 pytest -n0 -x exit 0  # closed by tests/test_logistics_pool_import_limit.py upgrade-helper swaps (8 sites)
- [x] 4.3 修复 `TestLogisticsImportLimitFreeTier::test_free_user_first_import_succeeds` - QA: 单测 pytest -n0 -x exit 0  # closed by tests/test_logistics_pool_import_limit.py upgrade-helper swaps (8 sites)
- [x] 4.4 修复 `TestLogisticsImportLimitProfessionalTier::test_professional_user_import_unlimited` - QA: 单测 pytest -n0 -x exit 0  # closed by tests/test_logistics_pool_import_limit.py upgrade-helper swaps (8 sites)
- [x] 4.5 文件级关闭阀:Phase 9 全量 -n0/-n auto 双绿覆盖(同文件 8/8 PASS)

## Phase 5: 修复 `tests/test_integration_logistics_products.py`(3 例)

- [x] 5.1 修复 `TestBatchDeleteLogistics::test_batch_delete_success` - QA: 单测 pytest -n0 -x exit 0  # closed by tests/test_integration_logistics_products.py upgrade-helper swaps (3 sites, 21/21 PASS)
- [x] 5.2 修复 `TestListLogistics::test_filters_by_fulfillment_type_and_destination` - QA: 单测 pytest -n0 -x exit 0  # closed by tests/test_integration_logistics_products.py upgrade-helper swaps (3 sites, 21/21 PASS)
- [x] 5.3 修复 `TestListLogistics::test_filters_by_type` - QA: 单测 pytest -n0 -x exit 0  # closed by tests/test_integration_logistics_products.py upgrade-helper swaps (3 sites, 21/21 PASS)
- [x] 5.4 文件级关闭阀:Phase 9 全量 -n0/-n auto 双绿覆盖

## Phase 6: 修复 `tests/test_db_users.py`(2 例)

- [x] 6.1 修复 `test_lower_email_index_blocks_raw_case_variant_insert` - QA: 单测 pytest -n0 -x exit 0  # closed by models/user.py Option A functional unique indexes (P2); 63/63 db_users PASS
- [x] 6.2 修复 `test_lower_username_index_blocks_raw_case_variant_insert` - QA: 单测 pytest -n0 -x exit 0  # closed by models/user.py Option A functional unique indexes (P2); 63/63 db_users PASS
- [x] 6.3 文件级关闭阀:Phase 9 全量 -n0/-n auto 双绿覆盖

## Phase 7: 修复 `tests/test_db_logistics_pool.py::test_upsert_pool_item_updates_existing_row_in_place`(1 例)

- [x] 7.1 复现 + 二分诊断:Oracle bg_4255b44f 决 Option A — `db.logistics_pool.upsert()` 在 commit `0449d146` (2026-04-25) 起为 plain INSERT,测试断言反向,属测试 bug
- [x] 7.2 修复 - 重写测试为 `test_upsert_pool_item_creates_new_row_each_call`,断言 INSERT-only 语义 + 保留 Priority 3 docstring 钉死回归;QA: `pytest -n0 tests/test_db_logistics_pool.py::test_upsert_pool_item_creates_new_row_each_call -x --tb=short` exit 0
- [x] 7.3 文件级关闭阀:`pytest -n0 tests/test_db_logistics_pool.py --tb=short` 0 failed

## Phase 8: 修复 `tests/test_api_logistics_pool_batch_add.py::test_batch_add_integrity_error_isolated`(1 例)

- [x] 8.1 复现 + 二分诊断:Oracle bg_4255b44f 决 Option B — 在测试层 patch `api.routes.logistics_pool.create_logistics` 第 2 次调用抛 `IntegrityError`;不污染 production `models/logistics.py`(项目 CHECK 约束只在迁移 DDL 中)
- [x] 8.2 修复 - 重写为 mock 注入 IntegrityError + 验证 SAVEPOINT 隔离 (added=2/errors=1/new_ids=2/db rows=2);QA: `pytest -n0 tests/test_api_logistics_pool_batch_add.py::test_batch_add_integrity_error_isolated -x --tb=short` exit 0
- [x] 8.3 文件级关闭阀:`pytest -n0 tests/test_api_logistics_pool_batch_add.py --tb=short` 0 failed

## Phase 9: 全量回归 + change 关闭

- [x] 9.1 跑 `pytest -n0 --tb=short 2>&1 | Tee-Object -FilePath qa_phase9_n0.log`;`qa_phase9_n0.log` 末行 `2249 passed, 5 skipped, 12 warnings in 360.61s` — `0 failed` ✓;warnings 12 ≤ baseline 16 ✓(D4 修订条款,pre-existing deprecations 划归 `fix-deprecation-warnings`)
- [x] 9.2 跑 `pytest -n auto --tb=short 2>&1 | Tee-Object -FilePath qa_phase9_nauto.log`;`qa_phase9_nauto.log` 末行 `2249 passed, 5 skipped, 12 warnings in 116.66s` — `0 failed` ✓
- [x] 9.3 `qa_phase9_n0.log` 与 `qa_phase9_nauto.log` 数字完全一致:passed=2249, skipped=5, warnings=12, failed=0
- [x] 9.4 out-of-scope skip 统计:本 change 引入 0 例 skip;5 例 skipped 全部为环境性(后端 8003 不可达 4 例 + No active plans in test DB 1 例),非本 change 责任;DELETE 4 例已退役 xlsx 测试(D15 协议,不计入 D5 cap)
- [x] 9.5 `git diff main..HEAD --name-only` review:未触及 `tests/_db_isolation.py`;`tests/conftest.py` 与根 `conftest.py` 仅 Phase 0 autouse override 修复,不触达隔离基础设施(D6 红线遵守)
- [x] 9.6 production 改动 review:仅 `models/user.py` Option A functional unique indexes(P2 数据完整性 justification);其余全部 tests/ 改动
- [ ] 9.7 翻 `add-pro-trial-overflow/tasks.md` Phase 8.1 → `[x]`,并在该 change 中继续推进 8.2~8.6
- [ ] 9.8 `openspec validate fix-preexisting-test-failures --strict` exit 0(归档前最后一次)
- [ ] 9.9 用户 confirm 后归档:`openspec archive fix-preexisting-test-failures`
