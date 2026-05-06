## 1. 后端实现

- [ ] 1.1 在 `api/routes/logistics_pool.py` 中导入 `get_user_with_subscription` 函数
- [ ] 1.2 添加辅助函数 `_check_logistics_limit(session, user_id, import_count)` 检查导入限制
- [ ] 1.3 修改 `add-to-my-logistics` 端点，导入前检查限制（单个导入 import_count=1）
- [ ] 1.4 修改 `batch-add-to-my-logistics` 端点，导入前检查限制

## 2. 测试验证

- [ ] 2.1 添加单元测试：免费版用户导入第1条成功
- [ ] 2.2 添加单元测试：免费版用户导入第2条被拒绝
- [ ] 2.3 添加单元测试：效率版用户导入第3条成功
- [ ] 2.4 添加单元测试：效率版用户导入第4条被拒绝
- [ ] 2.5 添加单元测试：专业版用户导入无限制
- [ ] 2.6 添加单元测试：批量导入超限检查
- [ ] 2.7 运行 flake8 确保代码风格正确
- [ ] 2.8 运行 pytest 确保所有测试通过
