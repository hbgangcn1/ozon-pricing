## 0. Wave C — xlsx_import 真正落地(补虚假归档 adapt-china-post-new-xlsx)

- [x] 0.1 完整重写 `xlsx_import/detector.py`:KEYWORDS-first 检测(China Post / ePacket 等关键词锚点),去除对单一 sheet 名 `Russia-China CP` 的硬绑定
- [x] 0.2 在 `detector.py` 加入 DEPRECATED sheet 识别:存在 `Russia-China CP` 工作表时抛 `ValueError("检测到旧版 China Post (Russia-China CP) 工作表,已不再支持")`,fail loud 不再静默降级
- [x] 0.3 完整重写 `xlsx_import/parsers/china_post.py`:顶部声明列号常量(`COL_METHOD=2, COL_PRICE=3, COL_TIME=4, COL_BATT=5, COL_LIQ=6, COL_MEASUREMENTS=7, COL_WEIGHT_MIN=8, COL_WEIGHT_MAX=9, COL_CNY_MIN=12, COL_CNY_MAX=13, COL_TARIFICATION=18, COL_VOLUME=19`)替换魔术数字
- [x] 0.4 在 `china_post.py` 实现多 sheet 遍历:NEW xlsx 含 RU/CIS/eParcel 等多个 sheet,每个 sheet 独立解析然后合并
- [x] 0.5 在 `china_post.py` 实现 per-row 目的国解析:从方法名(如 `EMS-AM`)/sheet 名识别 RU/KZ/BY/KGZ/UZ/GE/AZ/AM
- [x] 0.6 修正 eParcel 重量单位换算(g→kg)
- [x] 0.7 在 `china_post.py` 加 fail-loud 守卫:0 sheet 或 0 row 抛 ValueError(防止"导入成功但池为空"silent fail)
- [x] 0.8 `tests/test_xlsx_import.py` 完整迁移:切换到新 fixture `xlsx/China_post_HELP_ePacket_AM_AZ_UZ_1776238342.xlsx`、rename 列号引用、更新 air/ground 锚点、新增旧 sheet ValueError 回归、新增 dual-sheet 解析回归、修正 eParcel 单位断言、更新目的国分布断言为 `{RU:7, KZ:2, BY:2, AM:1, UZ:1, AZ:1}`
- [x] 0.9 烟雾测试:`POST /api/logistics-pool/import` 上传 NEW xlsx 返回 `{imported:14, skipped:0, errors:[]}`;上传 OLD xlsx 返回 ValueError
- [x] 0.10 `python -m flake8 xlsx_import/detector.py xlsx_import/parsers/china_post.py tests/test_xlsx_import.py` 零警告
- [x] 0.11 `python -m pytest tests/test_xlsx_import.py -q` 56/56 全绿

## 1. 后端常量更新

- [x] 1.1 在 `pricing/grouped_pricing.py:388` 的 `_CIS_DESTS` 集合追加 `"AM"`(保持现有 6 国不动,只在末尾加)
- [x] 1.2 在 `api/routes/pricing.py:96` 的 `_CIS_CODES` 列表追加 `"AM"`(保持现有顺序,末尾追加;若当前是字母序,可改为字母序插入,但需与 design 决策一致 — 末尾追加)
- [x] 1.3 在 `xlsx_import/parsers/cis_rfbs.py:22-29` 的 `DEST_MAP` 加入 AM 映射:`'armenia' -> 'AM'`(全名,小写)以及 `'am' -> 'AM'`(短码),保持与现有 entries 同样大小写规则
- [x] 1.4 运行 `python -m flake8 pricing/grouped_pricing.py api/routes/pricing.py xlsx_import/parsers/cis_rfbs.py`,确保零警告

## 2. 后端测试更新

- [x] 2.1 运行 `python -m pytest tests/ --tb=short -q`,记录所有失败用例
- [x] 2.2 修复任何因 `_CIS_DESTS` / `_CIS_CODES` 增加 AM 而硬编码失败的测试(常见:断言 grouped 字典 keys 数量、断言 _CIS_DESTS 长度、断言 grouped 缺 rfbs_AM 键)
- [x] 2.3 新增测试:在 `tests/test_grouped_pricing.py`(或对应文件)加一条测试 — 输入一条 `destination='AM', method_type='rfbs'` 的 logistics 行,断言它落在 `grouped['rfbs_AM']` 而非 `grouped['other']`
- [x] 2.4 新增测试:断言定价 API `/api/pricing/calculate` 的 grouped 响应包含 `rfbs_AM` 键(可为空数组)
- [x] 2.5 新增测试:为 `xlsx_import/parsers/cis_rfbs.py` 的 `DEST_MAP` 加测试 — 输入 `armenia` 与 `AM` 都应返回 `'AM'`
- [x] 2.6 重跑 `python -m pytest tests/ --tb=short -q`,确认全部通过

## 3. 前端常量更新

- [x] 3.1 在 `frontend/src/pages/pricing/pricingConstants.js` 的 `CIS_COUNTRIES` 数组末尾追加 `{ key: 'rfbs_AM', label: '亚美尼亚' }`(保持现有 6 项顺序不变)
- [x] 3.2 在 `frontend/src/pages/logistics/logisticsConstants.js` 的 `FILTER_DESTINATION_OPTIONS` 数组追加 `{ value: 'AM', label: '亚美尼亚(AM)' }`(位置:与现有 KGZ/UZ/GE/AZ 同组,按 design 决策末尾追加)
- [x] 3.3 在 `frontend/src/pages/logistics/LogisticsBasicSection.jsx` 的 rFBS 分支(行 48-55 附近)新增 `<SelectItem value="AM">亚美尼亚(AM)</SelectItem>`,位置紧跟 AZ 之后
- [x] 3.4 确认 LogisticsBasicSection.jsx 的 FBP economy/standard 分支**不要**添加 AM(对照 design 决策 1)
- [x] 3.5 修改 `frontend/src/pages/pricing/PricingResult.jsx:93` 与 `frontend/src/pages/pricing/PricingResultPanel.jsx:152` 的 CSS class — 把 `grid-cols-6` 改为 `grid-cols-7`
- [x] 3.6 在 `frontend/src/pages/logistics/logisticsConstants.js` 新增 export `DESTINATION_LABEL_MAP`(从 `FILTER_DESTINATION_OPTIONS` 派生 `{ code: label }` 字典,含 7 个 CIS 国家 + RU)
- [x] 3.7 在 `frontend/src/pages/LogisticsPoolPage.jsx` 引入 `DESTINATION_LABEL_MAP`,并修改 3 处 destination 显示:
  - line 238 表格 destination 列:`render: (item) => DESTINATION_LABEL_MAP[item.destination] ?? item.destination`
  - line 409 详情弹窗副标题:把 `{detailItem?.destination}` 包成 `{DESTINATION_LABEL_MAP[detailItem?.destination] ?? detailItem?.destination}`
  - line 419 详情字段 value:同上
- [x] 3.8 (可选验证)若 logistics 私有列表页 LogisticsPage.jsx 也直接渲染 raw destination,顺便用 `DESTINATION_LABEL_MAP` 包一下;否则跳过

## 4. 前端测试更新

- [x] 4.1 运行 `cd frontend && npm run test`,记录所有失败用例
- [x] 4.2 修复任何快照测试失败(常见:CIS_COUNTRIES 长度断言、grid-cols-6 字符串快照、destination 选项数量快照)
- [x] 4.3 新增 vitest 测试:在 `frontend/src/__tests__/` 下,为 PricingResult 组件加一条测试 — mock grouped 响应包含 `rfbs_AM`,断言 DOM 中渲染了 "亚美尼亚" tab
- [x] 4.4 新增 vitest 测试:为 LogisticsBasicSection 加一条测试 — 选择 method type rfbs 时 destination dropdown 包含 AM,选择 fbp_economy 时不包含
- [x] 4.5 重跑 `cd frontend && npm run test`,确认全部通过

## 5. 端到端验证

- [x] 5.1 启动后端(参考 AGENTS.md 后端启动模板)与前端(`cd frontend && npm run dev`,后台启动)
- [x] 5.2 用 API 直接验证:登录获取 token → 调 `/api/pricing/calculate` → 检查响应 `grouped` 对象含 `rfbs_AM` 键
- [x] 5.3 用 Playwright MCP 浏览器验证:
  - 登录
  - 进入定价结果页 → 切到 rFBS-独联体 tab → 截图确认 7 个国家 tab 平均分布且最后一个是 "亚美尼亚"
  - 进入物流编辑页 → 选 method_type=rfbs → 截图确认 destination 下拉含 "亚美尼亚(AM)"
  - 同一页切到 method_type=fbp_economy → 截图确认 destination 下拉**不**含 AM
  - 进入物流列表页 → 打开 destination 筛选 → 截图确认含 "亚美尼亚(AM)" 选项
  - 进入**公共物流池页**(LogisticsPoolPage)→ 截图确认表格"目的地"列 7 个 CIS 国家全部显示中文(如 "亚美尼亚(AM)"、"哈萨克斯坦(KZ)" 等),不再是裸代码
  - 在公共物流池页打开任意 CIS 规则的"查看"详情弹窗 → 截图确认副标题与"目的地"字段都显示中文格式
- [x] 5.4 用 API 验证 pool→private 复制:
  - 在 LogisticsPool 找一条 destination='AM' 的 rFBS 行(China Post 导入产物)
  - 调 batch-add API 把它复制到测试用户的私有池
  - 调 GET /api/logistics 查询私有池,确认该条 destination='AM' 不变
  - 在前端编辑这条规则,确认 destination select 显示 "亚美尼亚(AM)" 为已选值
- [x] 5.5 边缘情况:如果 5.4 中发现 LogisticsPool 中存在 destination='AM' 但 method_type ∈ {fbp_economy, fbp_standard} 的行(理论上不应该有),记录到一个 follow-up note,留待另一个 change 处理 fallback 显示

## 6. 文档与归档

- [x] 6.1 PLAN.md 更新当前任务状态(若 PLAN.md 跟踪了此 change)
- [x] 6.2 运行 `openspec validate add-armenia-cis-destination --strict`,确认 change valid
- [x] 6.3 完成所有上述任务后,可运行 `/opsx-archive add-armenia-cis-destination` 归档 change
