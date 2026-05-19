## 1. 后端数据库层

- [x] 1.1 在 db/orders.py 新增 get_all_orders() 函数，联表 User 获取 username，支持 search/status/date_from/date_to 过滤和分页
- [x] 1.2 运行 python -m flake8 db/orders.py 通过

## 2. 后端 API 层

- [x] 2.1 在 pi/routes/statistics.py 新增 OrderItem 和 OrderPage Pydantic 模型
- [x] 2.2 新增 GET /api/statistics/orders 端点，admin 权限，支持 page/page_size/search/status/date_from/date_to 参数
- [x] 2.3 运行 python -m flake8 api/routes/statistics.py 通过

## 3. 后端测试

- [x] 3.1 在 ests/test_api_statistics.py 新增测试：admin 获取订单列表返回 200
- [x] 3.2 新增测试：非 admin 返回 403
- [x] 3.3 新增测试：搜索过滤（按用户名、按订单号）
- [x] 3.4 新增测试：状态过滤
- [x] 3.5 新增测试：日期范围过滤
- [x] 3.6 运行 python -m pytest tests/test_api_statistics.py --tb=short 全绿

## 4. 前端 API 层

- [x] 4.1 在 rontend/src/services/api.js 的 statisticsAPI 中新增 getOrders() 方法

## 5. 前端页面

- [x] 5.1 在 StatisticsPage.jsx 新增 state：ordersPage, orderPage, orderSearchInput, orderSearch, orderStatus, orderDateFrom, orderDateTo
- [x] 5.2 在 etchData 中并行调用 statisticsAPI.getOrders()
- [x] 5.3 新增"订单记录" TabsTrigger 和 TabsContent，包含搜索框、状态下拉、日期范围、表格、分页
- [x] 5.4 表格列：订单号 | 用户名 | 金额 | 套餐类型 | 状态 | 创建时间
- [x] 5.5 状态下拉选项：全部 / PENDING / SUCCESS / FAILED
- [x] 5.6 实现搜索防抖（300ms）和分页控件复用

## 6. 前端测试

- [x] 6.1 在 StatisticsPage.test.jsx 新增测试：订单 tab 渲染
- [x] 6.2 新增测试：搜索输入触发 API 调用
- [x] 6.3 新增测试：状态下拉筛选
- [x] 6.4 运行 cd frontend && npm run test 全绿

## 7. 验证

- [x] 7.1 运行 python -m flake8 整库通过
- [x] 7.2 运行 python -m pytest --tb=short 不引入新失败
- [x] 7.3 运行 cd frontend && npm run test 全绿
