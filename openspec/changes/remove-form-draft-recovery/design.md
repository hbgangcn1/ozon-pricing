## Context

`useDraftPersist` hook 与 `DraftRestoreDialog` 组件构成的"表单草稿持久化与恢复"机制目前覆盖前端三个页面（Register / Pricing / Logistics），通过 `sessionStorage` 在 `draft:*` 键下保存表单数据，并在页面挂载时弹出阻塞模态框询问用户是否恢复。该机制存在多个固有缺陷（提交成功不清草稿、字段计数虚高、UI 状态被误算入"未填写"、弹窗不可逃逸），用户体验已与设计意图相反。设计层面的判断已经做出：**前端不再承担表单草稿持久化的职责**——这不是把弹窗换成横条、不是收紧触发条件、不是加阈值，而是彻底移除该能力。

当前架构中，三个页面对该机制的接入深度不同：
- **RegisterPage**：直接在页面层调用 `useDraftPersist`，状态全在页面内部
- **PricingPage**：通过 `usePricingCalculation` 这层 hook 间接持有 `fastDraft` / `preciseDraft` 两个 draft 实例
- **LogisticsPage**：通过 `useLogisticsPage` 这层 hook 间接持有 `logisticsDraft`，并配套 `restoreDraft` 函数与组合的 `draftState` 对象

LoginPage 含一句"您的会话已过期，登录后将恢复您的填写内容"提示，这句话承诺的是 useDraftPersist 的副作用——草稿移除后该承诺将变为虚假信息，必须同步修正。

## Goals / Non-Goals

**Goals:**
- 一次性、彻底移除前端的表单草稿持久化与恢复机制，不留任何"未来如果想再加回来"的钩子
- 移除后所有相关页面（Register / Pricing / Logistics）的页面行为符合"无任何自动表单恢复"的预期
- 修正 LoginPage 中因机制移除而失效的承诺性文案
- 全部相关单元测试同步移除（draft 测试用例不应再出现在测试套件中）
- 通过现有 lint（flake8 不适用前端，但前端有 ESLint）+ Vitest 全量测试 + 前端构建验证移除完整性

**Non-Goals:**
- 不替换为其他形式的草稿/恢复 UI（不是顶部横条、不是 toast、不是字段级灰显占位）
- 不实现任何"草稿迁移"或"一次性清理旧 sessionStorage 残留"的代码——`sessionStorage` 在标签页关闭时自然失效，不值得为它写一次性清理代码（用户已确认 1a 方案）
- 不动 `authStore` 的 localStorage 持久化（认证态恢复，无关）
- 不动 SettingsPage 的数据库备份/恢复功能（与表单状态无关）
- 不修改后端 API、数据库、迁移脚本（前端纯改动）
- 不引入或移除 npm 依赖（useDraftPersist 仅用 React 内置 + sessionStorage）

## Decisions

### D1：彻底删除文件 vs 保留空壳/no-op

**决策**：物理删除 `useDraftPersist.js`、`DraftRestoreDialog.jsx` 及其测试文件。

**理由**：
- 保留 no-op 空壳会让未来读代码的人困惑"这个 hook 是干嘛的，为什么所有调用都被删了"
- OpenSpec change 本身（archive 后保留在 `openspec/changes/archive/`）即是历史决策记录，无需在代码层留考古痕迹
- 物理删除让 import 残留立刻在 ESLint / Vitest 中暴露，是更好的"破坏即可见"信号

**替代方案**：
- 保留 hook 但导出 no-op 实现 → 否决，理由如上
- 软删除（标 deprecated 注释保留一个版本）→ 否决，没有外部消费者，无过渡期需求

### D2：sessionStorage 旧草稿处理策略

**决策**：不写主动清理代码，依赖 `sessionStorage` 在标签页关闭时自然失效（用户已选 1a）。

**理由**：
- `sessionStorage` 是标签页生命周期内的存储，关闭标签页即清空，残留窗口极短
- 写一次性清理代码意味着引入一个"启动时执行一次"的副作用——增加复杂度，收益微乎其微
- 用户已明确选择"零成本方案"

**替代方案**：
- 在 `App.jsx` 启动时遍历 `sessionStorage` 删除 `draft:*` 前缀键 → 否决（用户已拒绝）

### D3：LoginPage 过期提示文案的修改方式

**决策**：将"您的会话已过期，登录后将恢复您的填写内容"改为不含恢复承诺的版本，例如"您的会话已过期，请重新登录"。

**理由**：
- 草稿机制移除后，原文案承诺的"恢复填写内容"行为已不存在，保留即是误导
- 这是与 useDraftPersist 移除强耦合的文案修正，必须在同一个 change 中完成

**替代方案**：
- 完全删除该提示 → 否决。会话过期的提示本身有价值（解释为什么用户被踢回登录页），只是要去掉那段不再成立的承诺
- 保留原文案 + 增加注释 → 否决。代码层注释解决不了用户看到的产品文案问题

### D4：测试用例处理策略

**决策**：直接删除三个页面测试文件中所有 draft 相关用例（test cases / describe 块），不保留"应不出现 draft 弹窗"的反向断言。

**理由**：
- 反向断言（"页面挂载时 DraftRestoreDialog 不应渲染"）会因组件已不存在而退化为对未导入符号的引用，需要小心写法才不报错
- 该 change 本身在 OpenSpec 历史中即文档化了"此机制已移除"的事实
- 测试套件应反映**当前**行为，不应承载"曾经有什么但现在没了"的信息

**替代方案**：
- 保留少量反向断言确保未来不被无意重新引入 → 否决，OpenSpec change archive 已承担这个职责

### D5：useLogisticsPage 中 `draftState` 与 `restoreDraft` 的去留

**决策**：完全移除 `draftState` 组合对象、`logisticsDraft` 实例、`restoreDraft` 函数。`useLogisticsPage` 不再导出 `restoreDraft`。

**理由**：
- `restoreDraft` 唯一调用者是 LogisticsPage 中的草稿恢复回调，移除草稿后该函数失去任何调用入口
- `draftState` 把 `dialogOpen / editingItem / form / activeTab / filterFulfillment / filterDestination / currentPage / pageSize` 组装成一个对象，本就只为了喂给 useDraftPersist，移除草稿后该对象彻底失去用途

**替代方案**：
- 保留 `restoreDraft` 接口供未来其他场景使用 → 否决，无具体场景，YAGNI

### D6：usePricingCalculation 中两个 draft 实例与导出的去留

**决策**：完全移除 `fastDraft` / `preciseDraft` 实例化，并从 hook 返回值中移除这两项。

**理由**：同 D5。

### D7：本次新建的 capability spec 内容定位

**决策**：新建 capability `form-state-handling`，spec 内容为**反向决策记录**——明确写出"前端不实现表单草稿自动持久化与恢复"作为产品要求。

**理由**：
- 通常 spec 描述"系统应做什么"。本 change 的核心成果是"系统刻意不做什么"
- 如果未来有人提议"用户填到一半离开就丢了，咱给加个草稿保存吧"，他们应能在 specs 中找到"这是被刻意排除的能力"的依据
- 该 spec 同时承载未来若有相关变更（例如：决定为某个特定长表单单独引入服务端草稿）时的修改起点

**替代方案**：
- 不创建 capability spec，只在 change archive 中记录 → 否决。Archive 不是日常查阅入口；spec 才是"系统当前承诺/不承诺什么"的真实来源

## Risks / Trade-offs

- **风险**：用户在长表单（如 Logistics 39 字段）填到一半时遇到意外（浏览器崩溃、误关 tab、会话过期）会丢失填写内容
  - **缓解**：这是用户明确选择接受的代价（Q1 答复"不想留"）。该机制本身在解决该问题上的实际效果就极其差（弹窗体验糟糕到用户宁可丢失内容也不要它）。如未来有真实数据证明此问题严重，可重新评估并基于服务端的、用户主动触发的"保存为草稿"机制来解决——而不是回到隐式自动持久化的老路

- **风险**：移除过程中遗漏某处对 `useDraftPersist` 或 `DraftRestoreDialog` 的 import，导致构建失败
  - **缓解**：物理删除文件后任何残留 import 都会在 ESLint 与 Vitest 运行时立即报错；tasks.md 中安排了"构建 + 全量测试"的最终验证步骤

- **风险**：测试用例删除时误伤非 draft 相关的测试
  - **缓解**：tasks.md 要求按"先标记、后删除、再跑测试"三步执行，每个测试文件单独提交一次（commit per file），便于回退

- **风险**：LoginPage 文案改动可能与产品话术规范不符
  - **缓解**：决策中已给出默认文案"您的会话已过期，请重新登录"。如该文案需调整，可在 PR review 阶段直接修订，影响范围仅一行字符串

- **权衡**：选择"物理删除"而非"软删除"，意味着如果出现强烈用户回退诉求，恢复成本是从 git 历史 / OpenSpec archive 中重新引入文件——但这正是 OpenSpec 流程要支持的能力，不是负担

## Migration Plan

无运行时迁移（前端纯改动，无后端、无数据库、无 schema）。部署即生效：旧前端构建中已写入 `sessionStorage` 的 `draft:*` 键在用户关闭标签页后自然消失，新前端构建不再读取也不再写入这些键。

回滚策略：通过 git revert 撤销本 change 涉及的所有 commit 即可恢复原状——所有改动都在前端，无后端不可逆操作。

## Open Questions

- LoginPage 过期提示的最终文案需用户确认。决策中给出默认值"您的会话已过期，请重新登录"，如有更优文案以用户决定为准。
