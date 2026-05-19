## Why

管理员需要在数据统计页面查看所有用户的订单记录，用于对账、排查支付问题和了解整体营收情况。目前统计页面只有总览数字（总订单数、总收入），无法查看单笔订单明细。

## What Changes

- 后端新增 get_all_orders() 查询函数，联表 User 获取用户名，支持搜索、状态过滤、日期范围过滤
- 后端新增 GET /api/statistics/orders 端点（admin 权限），分页返回所有用户订单
- 前端 StatisticsPage 新增"订单记录" tab，包含搜索框、状态下拉筛选、日期范围、分页表格

## Capabilities

### New Capabilities

- dmin-orders-list: 管理员查看所有用户订单记录的能力，包含后端 API、前端 tab、搜索/过滤/分页

### Modified Capabilities

（无现有 spec 需求变更）

## Impact

- **后端**: db/orders.py（新增函数）、pi/routes/statistics.py（新增端点）
- **前端**: rontend/src/pages/StatisticsPage.jsx（新增 tab）、rontend/src/services/api.js（新增 API 方法）
- **测试**: 后端统计端点测试、前端 StatisticsPage 测试
