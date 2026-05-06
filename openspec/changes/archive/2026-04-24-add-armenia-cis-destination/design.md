## Context

China Post 供应商在新版 ePacket xlsx (`xlsx/China_post_HELP_ePacket_AM_AZ_UZ_1776238342.xlsx`) 的多个 CIS 工作表中加入了亚美尼亚行(以 `AM` 缩写出现在方法名中)。**关键背景**: 已归档的 change `2026-04-24-adapt-china-post-new-xlsx` 文档上声称已完成新 xlsx 解析适配,但**实际代码未落地** — `xlsx_import/detector.py` 仍按旧 sheet 名 `Russia-China CP` 检测,`xlsx_import/parsers/china_post.py` 仍用旧列号布局,导致用户实测"导入成功但物流池为空"。本 change 一并承担:

1. **Wave C(补虚假归档)**: 真正实施 detector + china_post 多 sheet 解析与 per-row 目的国识别,并把旧 sheet 标记为 BREAKING fail-loud 拒绝。
2. **AM 全链路**: 在所有下游常量/UI 中加入 AM,使 detector 抽出的 AM 行真正可见可操作。

数据库层无需改动:`Logistics.destination` 与 `LogisticsPool.destination` 都是开放 `String` 列(`models/logistics.py:141`),无 enum 或 CHECK 约束;`destination='AM'` 已能透明入库,公共池→私有池复制路径(`db/logistics_crud.py::create_logistics`)的 `_clean_fields` 不过滤 destination,直接透传。

## Goals / Non-Goals

**Goals:**
- Wave C: detector + china_post 真正支持 NEW xlsx 多 sheet + per-row 目的国;旧 sheet fail loud。
- AM 在系统所有 CIS 上下文(后端分组、定价 API、前端编辑/筛选/结果展示、公共池中文化)中可见且可操作。
- 改动最小化:常量层只在硬编码集合中追加,不引入新抽象;detector/china_post 重写采用列号常量替换魔术数字。
- 与现有 6 国 CIS (KZ/BY/KGZ/UZ/GE/AZ) 的代码模式完全一致,新增的 AM 视觉/行为与同类项对齐。

**Non-Goals:**
- 不重构 CIS 国家集合的存储方式(继续用硬编码常量;未来若再加国家可考虑抽离到统一配置文件)。
- 不修改 `xlsx-import` spec 中已有的 destination resolver requirement(它已经支持 AM)。
- 不修改 `LogisticsPool.destination` / `Logistics.destination` 列定义。
- 不扩展 FBP economy/standard 到 AM(用户决策:AM 仅 rFBS 可选)。
- 不为 CIS tab 网格引入响应式或滚动布局(用户决策:直接 `grid-cols-7`)。
- 不保留对旧 `Russia-China CP` 单 sheet xlsx 的兼容(BREAKING:fail loud 拒绝)。

## Decisions

### 决策 0:detector 用 KEYWORDS-first 检测,旧 sheet fail loud(Wave C 核心)

**选择**: `xlsx_import/detector.py` 重写为 KEYWORDS-first 锚点检测 — 通过"China Post"、"ePacket"等关键词在 sheet 名/header 中识别 China Post 格式,不再硬绑定单一 sheet 名 `Russia-China CP`。同时新增 DEPRECATED sheet 识别:存在 `Russia-China CP` 工作表时直接抛 `ValueError("检测到旧版 China Post (Russia-China CP) 工作表,已不再支持")`,而非静默降级或返回空。
**理由**:
- KEYWORDS-first 让 detector 与 sheet 命名解耦,未来供应商再改 sheet 名也不会破坏检测。
- Fail loud 解决虚假归档时期"导入成功但池为空"的 silent fail 用户体验问题(用户实测 3 次反馈)。
- 新旧 sheet 解析逻辑差异过大不可共存(列号/单位/destination 解析全不同),共存会让 parser 内部充斥分支,选择 BREAKING 拒绝。
**备选**:
- 保留旧 sheet 兼容并给出 deprecation warning — 被否,共存复杂度高且用户已迁移到新 xlsx。
- silent skip 旧 sheet — 被否,正是历史 silent fail 的根因。

### 决策 0.5:china_post.py 用列号常量替换魔术数字(Wave C 核心)

**选择**: `xlsx_import/parsers/china_post.py` 顶部声明列号常量集中:`COL_METHOD=2, COL_PRICE=3, COL_TIME=4, COL_BATT=5, COL_LIQ=6, COL_MEASUREMENTS=7, COL_WEIGHT_MIN=8, COL_WEIGHT_MAX=9, COL_CNY_MIN=12, COL_CNY_MAX=13, COL_TARIFICATION=18, COL_VOLUME=19`。所有 cell 访问通过常量引用。
**理由**: NEW xlsx 列号与 OLD 不同(部分列右移),且未来还可能再变。集中常量让下次列号变更只需修一处,不需要全文 grep 魔术数字;同时让 parser 自描述,提高可读性。
**备选**: 维持魔术数字 + inline comment — 被否,inline comment 不强制,后续容易漂移。

### 决策 0.6:china_post.py per-row 目的国 + dual/multi-sheet 遍历(Wave C 核心)

**选择**: 每行从方法名(如 `EMS-AM`、`ePacket-KZ`)和/或 sheet 名独立解析 destination,不假定 sheet 级默认值。所有匹配 sheets 遍历后合并到单一规则列表。
**理由**: NEW xlsx 的 CIS sheet 内一个 sheet 含多个目的国行(KZ/BY/AM/UZ/AZ 混合),sheet-level default 会让所有行被错分到同一国;per-row 解析才能正确分类。
**备选**: 按 sheet 拆分调用各国 parser — 被否,需要给每个 sheet 一个 parser 工厂,复杂度高且 sheet 与国一一对应假设不成立。

### 决策 0.7:0 sheet/0 row 抛 ValueError(Wave C 核心)

**选择**: parser 末尾守卫 — 0 个匹配 sheet 或 0 行有效数据均抛 `ValueError`,不返回空列表。
**理由**: 历史虚假归档的根因就是 parser 静默返回空 → import API 报告"成功" → 用户看到空池。Fail loud 让问题在 import 时立即暴露,不延迟到用户 UI。
**备选**: 返回空列表并由 import API 检测 — 被否,职责漂移;parser 自己最清楚是否解析成功。

### 决策 1:AM 在物流编辑页仅 rFBS 可选

**选择**: 在 `LogisticsBasicSection.jsx` 中只在 rFBS 分支的 destination select 中加入 AM,FBP economy/standard 分支不加。
**理由**: 与 KGZ/UZ/GE/AZ 的现有规则一致 — 这 4 国都只在 rFBS 下可选;只有 KZ/BY 因为业务量大才同时支持 FBP。AM 当前业务来源是 China Post CIS 表(rFBS 性质),没有 FBP 入库证据。
**备选**: 同时加到 FBP — 被否,因为没有 FBP-AM 的业务依据,加上去会让用户误以为 AM 有 FBP 选项。

### 决策 2:CIS tab 网格直接改为 grid-cols-7

**选择**: `PricingResult.jsx:93` 与 `PricingResultPanel.jsx:152` 的 `grid-cols-6` 改为 `grid-cols-7`。
**理由**: 当前是固定列数对齐,从 6 改 7 是最小改动,所有 tab 等宽,视觉一致性最好。
**备选**:
- `grid-cols-6` + AM 单独第二行 — 被否,视觉不平衡。
- 改成 flex 横向滚动 — 被否,过度设计;只有 7 个国家,不需要滚动。

### 决策 3:CIS_COUNTRIES 数组追加在末尾

**选择**: `pricingConstants.js` 的 `CIS_COUNTRIES` 数组保持现有顺序 `[KZ, BY, KGZ, UZ, GE, AZ]`,AM 追加到末尾。
**理由**: 保持现有 tab 顺序不变,降低用户习惯破坏;新增国家在末尾是最低视觉跳动的策略。
**备选**: 按字母序重排 — 被否,会改变所有现有用户的 tab 位置预期。

### 决策 4:周边 parser 一并补 AM

**选择**: `xlsx_import/parsers/cis_rfbs.py` 的 `DEST_MAP` 同步补齐 AM,即使本次不影响 China Post 链路(China Post 走 `china_post.py` 的 `CIS_COUNTRY_KEYWORDS`,不走 `cis_rfbs.py`)。
**理由**: 保持所有 CIS parser 的国家集合一致,避免下次另一个供应商表导入时再次踩同样的坑。代价极小(加 1-2 行),收益是消除一致性 bug 风险。
**备选**: 严格限定 scope 只改 China Post 链路相关 — 被否,会留下已知不一致项,为未来制造技术债。

### 决策 5:公共物流池列表页 7 国全部加中文标签

**选择**: 在 `LogisticsPoolPage.jsx` 的 3 处 destination 显示位置(表格列 line 238、详情弹窗副标题 line 409、详情字段 line 419)统一通过 `DESTINATION_LABEL_MAP` 把 7 个 CIS 国家代码渲染为 "中文(代码)" 格式(例:"亚美尼亚(AM)"、"哈萨克斯坦(KZ)")。
**理由**: 用户在被询问"公共池要不要顺便加中文"时选择"顺便修(7 国全部加中文)"。统一全部 7 国 UX,而非只给 AM 特殊处理,避免 UI 不一致(只 AM 显示中文、其他 6 国显示英文代码会更混乱)。
**实现**: 在 `frontend/src/pages/logistics/logisticsConstants.js` 新增 export `DESTINATION_LABEL_MAP`(从 `FILTER_DESTINATION_OPTIONS` 派生 `code -> label` 映射 + RU 兜底);`LogisticsPoolPage.jsx` 引入并在 3 处用 `DESTINATION_LABEL_MAP[item.destination] ?? item.destination` fallback。
**备选**:
- 不修公共池(只改私有池)— 被否,用户明确选择"顺便修"。
- 只给 AM 加中文 — 被否,UI 不一致。

### 决策 6:不创建新 capability,扩展现有 xlsx-import spec? 不,创建新 capability

**选择**: 创建新 capability `cis-destination-armenia`,描述 AM 端到端的可见性合约 + China Post NEW xlsx 多 sheet 解析合约 + BREAKING 旧 sheet 拒绝合约。
**理由**: 本次改动覆盖前端 UI + 后端分组 + 定价 API + xlsx 解析层重写,不属于 `xlsx-import` 的旧职责范畴(xlsx-import spec 已经有 AM 入库 requirement,不需要改)。新 capability 把端到端合约集中,未来加新国家或 China Post 再改格式可以参考此模式。
**备选**: 把 requirements 直接加进 `xlsx-import` spec — 被否,职责不匹配且会让 xlsx-import spec 膨胀含有前端 UI 合约。

### 决策 7:Wave C 与 AM 链路合并到单一 change

**选择**: 不复活虚假归档 change,也不新建 `adapt-china-post-new-xlsx-real`,把 Wave C 全部 scope 并入 `add-armenia-cis-destination`。
**理由**:
- 因果同源:Wave C 不落地则 AM 永远入不了库;AM 链路不通则 Wave C 入库的 AM 行用户看不见。两者一并归档保持原子性。
- OpenSpec 无官方 unarchive 流程,复活归档是反模式。
- 新建 `-real` 后缀 change 命名怪异且增加 archive 工作量。
- 用户已 explicit 选择方案 A(全部并入当前 change)。
**备选**:
- 复活归档 change 走平行 archive — 被否(见上)。
- 新建 `-real` change — 被否(见上)。
**Trade-off**: change 名字 `add-armenia-cis-destination` 与实际 scope 略不匹配(scope 比名字宽),但通过在 proposal Why 段明确说明"本 change 同时承担 Wave C 补落地"消解此问题。

## Risks / Trade-offs

- **[风险] BREAKING 旧 xlsx 拒绝可能影响仍持有旧文件的用户** → **缓解**: 错误消息明确说明"已不再支持",引导用户从供应商获取新版 xlsx;归档 change `2026-04-24-adapt-china-post-new-xlsx` 已先公告新格式适配,本 change 是补落地,用户应已知预期。
- **[风险] 后端 `_CIS_DESTS` 集合中 KGZ/GE 实际上不在 China Post 新文件的 CIS 工作表里(只有 KZ/BY/AM/UZ/AZ),可能是旧版兼容遗留** → **缓解**: 不在本次 scope,本次只确保加 AM 不破坏现有逻辑;KGZ/GE 是否清理留待未来另一个 change 评估。
- **[风险] 现有测试若硬编码了 CIS 国家清单(例如 grouped_pricing 测试断言 grouped 字典只有 6 个 rfbs_* 键),新增 AM 会导致测试失败** → **缓解**: tasks.md 中明确列出"运行完整 pytest 套件并修复任何因 AM 新增导致的失败";前端 vitest 快照同理。已实测 AM-related 129/129 全绿、xlsx_import 56/56 全绿。
- **[风险] 前端定价结果页若用户屏幕宽度较窄,7 列 tab 可能挤压标签文字** → **缓解**: "亚美尼亚" 三个字符与现有 "哈萨克斯坦" 五字符相比更短,实际不会更挤;若窄屏挤压问题暴露,后续以独立 change 优化(如响应式或缩写)。
- **[风险] FBP 分支不加 AM 后,如果用户从公共池导入了一条 destination='AM' 但 method_type='fbp_economy' 的规则到私有池,在编辑页会显示一个 select 中没有的值,Select 组件可能渲染为空** → **缓解**: 这种情况理论上不存在(China Post 解析器只把 AM 行写为 rFBS 性质),但 tasks.md 加一个验证步骤检查 `LogisticsPool` 中是否存在 `destination='AM' AND method_type IN ('fbp_economy', 'fbp_standard')` 的行;若存在,需要在编辑页 fallback 显示该值。
- **[风险] Wave C 与 AM scope 合并到一个 change 让 commit/PR 范围较大** → **缓解**: change 内通过 tasks.md 章节(0/1/2/3/4/5/6)明确分组;commit 时按 wave 拆分(C/A/B)或按章节拆,可读性可控。
