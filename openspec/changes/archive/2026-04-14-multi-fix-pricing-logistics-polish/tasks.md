## 1. 精准模式404修复（优先 — 解除核心功能阻塞）

- [x] 1.1 检查前端精准模式计算的API调用路径，确认URL是否与后端路由匹配（api/routes/pricing.py的/calculate端点）
- [x] 1.2 检查后端pricing路由是否正确注册到FastAPI app（api/main.py中的router include）
- [x] 1.3 检查product_id参数传递是否正确（前端发送格式 vs 后端期望格式）
- [x] 1.4 修复导致404的根本原因
- [x] 1.5 手动验证精准模式计算正常返回结果

## 2. 空数据错误提示修复

- [x] 2.1 修改LogisticsPoolPage.jsx：当API返回空数组时不弹出"获取物流池内容失败"错误，显示空状态UI
- [x] 2.2 修改CommissionCategoriesPage.jsx：当API返回空数组时不弹出"获取佣金类目失败"错误，显示空状态UI
- [x] 2.3 确保真实API错误（4xx/5xx）仍正常弹出错误提示

## 3. 物流编辑表单简化

- [x] 3.1 从LogisticsPage.jsx的编辑表单中移除"送货方式"字段（送货上门、自提、未知选项）
- [x] 3.2 从LogisticsPage.jsx的编辑表单中移除"FBP服务等级"下拉菜单
- [x] 3.3 从新建物流规则表单中同步移除上述字段
- [x] 3.4 后端api/routes/logistics.py中保留数据库字段但不再在API校验中要求这些字段

## 4. 物流管理页面增强

- [x] 4.1 修改陆运/空运标签页显示规则数量：格式为"陆运（N个）"/"空运（M个）"
- [x] 4.2 诊断发货类型筛选器无效的原因（检查onChange事件、参数传递、后端查询逻辑）
- [x] 4.3 修复发货类型筛选器，确保选择后正确过滤列表
- [x] 4.4 诊断目的国筛选器无效的原因
- [x] 4.5 修复目的国筛选器，确保选择后正确过滤列表
- [x] 4.6 验证筛选器和标签计数功能正常工作

## 5. 物流限价人民币统一

- [x] 5.1 编写数据库迁移脚本：将现有RUB/USD限价按当前汇率转换为CNY值
- [x] 5.2 修改数据库模型（models/logistics.py, models/logistics_pool.py）：统一限价字段为CNY
- [x] 5.3 修改前端LogisticsPage.jsx编辑表单：移除货币单位下拉菜单，标签改为"价格上限（元）"/"价格下限（元）"
- [x] 5.4 修改定价计算引擎（pricing/filter.py, pricing/cost_filter.py）：限价检查直接使用CNY值，移除汇率转换逻辑
- [x] 5.5 修改Excel导入解析器（xlsx_import/parsers/中所有解析器）：只读取CNY限价列
- [x] 5.6 修改后端API（api/routes/logistics.py, db/logistics_crud.py）：更新允许字段列表
- [x] 5.7 运行数据库迁移并验证数据完整性
- [x] 5.8 端到端验证：导入Excel → 编辑限价 → 执行定价计算 → 验证限价检查使用CNY

## 6. 盈亏平衡线定价计算

- [x] 6.1 修改后端定价API（api/routes/pricing.py）：每次计算额外执行target_profit_margin=0的计算
- [x] 6.2 修改API响应结构，返回两套结果（normal_results + breakeven_results）
- [x] 6.3 在PricingPage.jsx精准模式结果区域添加"盈亏平衡线"Toggle开关
- [x] 6.4 前端状态管理：存储两套结果，Toggle切换时无API调用，直接切换展示
- [x] 6.5 无计算结果时Toggle禁用或隐藏
- [x] 6.6 验证Toggle切换正常，结果不丢失

## 7. 精准模式页面UI打磨

- [x] 7.1 对精准模式页面进行全面视觉优化（布局、间距、视觉层次）
- [x] 7.2 改善佣金类目"管理"按钮：增大尺寸、使用outline样式、添加Settings2图标、改善hover效果
- [x] 7.3 整体一致性检查和微调

## 8. 测试用户清理改进

- [x] 8.1 审查tests/conftest.py和根conftest.py中的测试用户创建和清理机制
- [x] 8.2 查找所有直接创建用户但未使用共享fixture的测试文件
- [x] 8.3 增强pytest_sessionfinish中的全局清理：确保批量删除所有is_test_user=1的用户
- [x] 8.4 为关键fixture添加robust teardown（即使测试异常也执行清理）
- [x] 8.5 运行完整测试套件并验证数据库中无残留测试用户

## 9. 最终验证

- [x] 9.1 运行后端flake8检查，确保无错误（项目代码通过，仅根目录临时脚本有lint）
- [x] 9.2 运行完整pytest测试套件：1328 passed, 12 failed（全部pre-existing）
- [x] 9.3 运行前端vitest测试套件：23 files, 190 tests passed
- [x] 9.4 前端build验证通过
