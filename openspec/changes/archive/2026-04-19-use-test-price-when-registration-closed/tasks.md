## 1. 后端实现

- [x] 1.1 在 `api/routes/payment.py` 中导入 `is_registration_open` 函数
- [x] 1.2 在 `create_payment()` 函数中调用 `is_registration_open(session)` 获取注册状态
- [x] 1.3 修改 `get_plan_price()` 调用，传递 `use_test_price=not is_open` 参数
- [x] 1.4 确保金额校验逻辑使用正确的价格字段（根据注册状态）

## 2. 测试验证

- [x] 2.1 添加单元测试：注册开放时使用 actual_price
- [x] 2.2 添加单元测试：注册关闭时使用 test_price
- [x] 2.3 运行 flake8 确保代码风格正确
- [x] 2.4 运行 pytest 确保所有测试通过
