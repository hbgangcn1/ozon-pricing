## Why

China Post 新版 xlsx (`xlsx/China_post_HELP_ePacket_AM_AZ_UZ_1776238342.xlsx`) 已经把亚美尼亚 (AM) 加进 CIS 工作表。**前置背景(关键)**:已归档的 change `2026-04-24-adapt-china-post-new-xlsx` 在文档上声称已完成新 xlsx 解析适配,**但实际代码未落地** — `xlsx_import/detector.py` 仍按旧 sheet 名(`Russia-China CP`)单 sheet 检测,`xlsx_import/parsers/china_post.py` 仍用旧列号布局,导致用户实测"导入成功但物流池为空"。本 change 同时承担两件事:

1. **Wave C(补落地虚假归档)**: 真正实施 detector + china_post 多 sheet 解析 + per-row 目的国 + 新列号布局,并把旧 `Russia-China CP` 单 sheet 格式标记为 **BREAKING fail-loud 拒绝**(避免静默 silent fail)。同步迁移 `tests/test_xlsx_import.py` 56 用例与新 fixture 对齐。
2. **AM 全链路打通**: detector + china_post 已能从新 xlsx 抽出 `destination='AM'` 行入库 `LogisticsPool` 后,下游链路仍缺 AM — 后端定价分组的 CIS 集合 (`_CIS_DESTS` / `_CIS_CODES`) 不含 AM,前端物流编辑页的目的国下拉、筛选下拉、定价结果的 rFBS-独联体子标签页也都没有 AM。结果是 AM 规则虽能入库公共池,却在 UI/分组中"隐身",用户既看不到也无法编辑/筛选/查看其定价结果。本 change 把 AM 加入所有相关常量/UI 组件。

合并到一个 change 的理由:Wave C 与 AM 链路在因果上同源(都是 China Post 新 xlsx 的产物),Wave C 不落地则 AM 永远入不了库,AM 链路不通则 Wave C 入库的 AM 行用户看不见。两者一并归档保持原子性。

## What Changes

**Wave C — xlsx_import 真正落地(补虚假归档)**:

- `xlsx_import/detector.py` **完整重写**: 改用 KEYWORDS-first 锚点检测(China Post / ePacket / etc),去除对单一 sheet 名 `Russia-China CP` 的硬绑定,新增 DEPRECATED sheet 识别(旧 `Russia-China CP` 工作表存在时抛 ValueError 中止导入)。
- `xlsx_import/parsers/china_post.py` **完整重写**: 1) 顶部声明列号常量(`COL_METHOD=2, COL_PRICE=3, COL_TIME=4, ..., COL_VOLUME=19`)替换魔术数字;2) 多 sheet 遍历(NEW xlsx 含多个 CIS sheet);3) per-row 目的国解析(从方法名/sheet 名识别 RU/KZ/BY/KGZ/UZ/GE/AZ/AM);4) 单位换算修正(eParcel 重量单位);5) 0 sheet/0 row 抛 ValueError(fail loud,不静默返回空)。
- `tests/test_xlsx_import.py` **56 用例完整迁移**: 切换到新 fixture (`China_post_HELP_ePacket_AM_AZ_UZ_1776238342.xlsx`)、rename 列号引用、更新 air/ground 锚点、新增旧 sheet reject 回归 + dual-sheet 解析回归、更新目的国分布断言。
- **BREAKING**: 旧 `Russia-China CP` 单 sheet 格式不再支持,导入时抛 `ValueError("检测到旧版 China Post (Russia-China CP) 工作表,已不再支持")`。理由:旧/新 sheet 解析逻辑差异过大不可共存,且新 xlsx 已是供应商正式版本,旧文件应淘汰。

**AM 全链路常量/UI 增补**:

- 后端 `_CIS_DESTS` 集合新增 `"AM"`,使 grouped_pricing 把 AM 行归入 CIS 分组。
- 后端 `_CIS_CODES` 列表新增 `"AM"`,使定价 API 返回的 grouped 结果包含 `rfbs_AM` 键。
- 前端 `CIS_COUNTRIES` 数组在末尾追加 `{ key: 'rfbs_AM', label: '亚美尼亚' }`,使定价结果页 rFBS-独联体子标签页出现"亚美尼亚" tab。
- 前端物流编辑页 `LogisticsBasicSection.jsx` 在 rFBS 分支新增 `<SelectItem value="AM">亚美尼亚(AM)</SelectItem>`(仅 rFBS 可选,与 KGZ/UZ/GE/AZ 一致;FBP economy/standard 不可选)。
- 前端筛选 `FILTER_DESTINATION_OPTIONS` 新增 `{ value: 'AM', label: '亚美尼亚(AM)' }`,使物流列表筛选下拉支持按 AM 过滤。
- 前端定价结果页 `PricingResult.jsx` 与 `PricingResultPanel.jsx` 的 CIS tab 网格类从 `grid-cols-6` 改为 `grid-cols-7`,容纳第 7 个国家 tab。
- 前端公共物流池页 `LogisticsPoolPage.jsx` 引入 `DESTINATION_LABEL_MAP`,在表格目的地列、详情弹窗副标题与字段值 3 处把 7 国代码统一渲染为"中文(代码)"格式。
- 周边一致性:`xlsx_import/parsers/cis_rfbs.py` 的 `DEST_MAP` 同步加入 AM 映射,避免未来其他 CIS rFBS 表导入时再次踩坑(本次不影响 China Post 链路,但保持 CIS parser 国家集合一致)。

**BREAKING**:旧 `Russia-China CP` 单 sheet xlsx 不再支持(详见 Wave C)。AM 常量/UI 增补本身无 BREAKING,所有改动均为加项,不影响现有 RU/KZ/BY/KGZ/UZ/GE/AZ 的行为。

## Capabilities

### New Capabilities
- `cis-destination-armenia`: 定义亚美尼亚 (AM) 作为 CIS 目的国在系统端到端的可见性合约 — 后端 CIS 分组、定价 API grouped 键、前端物流编辑/筛选下拉、定价结果 rFBS 子标签页、CIS rFBS parser 国家映射、China Post NEW xlsx 多 sheet 解析与 per-row 目的国识别、旧 sheet BREAKING 拒绝。

### Modified Capabilities
(无 — `xlsx-import` spec 已在 "Destination country SHALL be resolved per row" requirement 中支持 AM,本次将 China Post 多 sheet 行为以新 capability 集中描述,旧 spec 无需改动。)

## Impact

**后端代码** (5 文件):
- `xlsx_import/detector.py` — **完整重写**: KEYWORDS-first 检测 + DEPRECATED sheet 拒绝
- `xlsx_import/parsers/china_post.py` — **完整重写**: 列号常量 + 多 sheet + per-row destination + fail loud
- `pricing/grouped_pricing.py:388` — `_CIS_DESTS` 集合追加 AM
- `api/routes/pricing.py:96` — `_CIS_CODES` 列表追加 AM
- `xlsx_import/parsers/cis_rfbs.py:22-29` — `DEST_MAP` 加入 AM

**前端代码** (5 文件):
- `frontend/src/pages/pricing/pricingConstants.js:67-74` — `CIS_COUNTRIES`
- `frontend/src/pages/logistics/LogisticsBasicSection.jsx:48-55` — rFBS 分支 destination select
- `frontend/src/pages/logistics/logisticsConstants.js:50-58` — `FILTER_DESTINATION_OPTIONS` + 新增 `DESTINATION_LABEL_MAP`
- `frontend/src/pages/pricing/PricingResult.jsx:93` 与 `PricingResultPanel.jsx:152` — `grid-cols-6` → `grid-cols-7`
- `frontend/src/pages/LogisticsPoolPage.jsx` (3 处:表格列、弹窗副标题、字段 value) — 引入 `DESTINATION_LABEL_MAP`

**测试代码**:
- `tests/test_xlsx_import.py` — **56 用例完整迁移**(切 fixture + rename 列号 + air/ground 锚点更新 + 加 reject/dual-sheet 回归 + eParcel 单位修正)
- 新增 grouped_pricing AM 测试、定价 API rfbs_AM 键测试、cis_rfbs DEST_MAP AM 测试、PricingResult AM tab 渲染测试、LogisticsBasicSection method-type 切换测试

**数据库**: 无 schema 变更(`Logistics.destination` 与 `LogisticsPool.destination` 均为开放 String 列,默认 `'RU'`,无 enum/CHECK 约束)。

**API 契约**:
- `GET /api/pricing/calculate` 返回的 `grouped` 对象将多出 `rfbs_AM` 键(可能为空数组)。前端已用 `CIS_COUNTRIES.map()` 动态渲染,无需额外兼容代码。
- `POST /api/logistics-pool/import` 当上传旧 `Russia-China CP` 单 sheet xlsx 时将返回 ValueError(BREAKING)。

**测试影响**: 现有 grouped_pricing 测试若硬编码了 CIS 国家清单需要更新;前端定价结果快照测试若快照含 `grid-cols-6` 需更新;`tests/test_xlsx_import.py` 完整迁移到新 fixture。
