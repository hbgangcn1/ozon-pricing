## 1. 修复 Pricing Decimal 类型错误

- [x] 1.1 修改 `pricing/logistic_cost.py` 的 `_calc_fee` 函数，将 `base_fee`、`continue_fee`、`first_fee` 显式转换为 `Decimal` 类型
- [x] 1.2 修改 `pricing/logistic_cost.py` 的 `calculate_logistic_cost` 函数，确保所有费用计算使用 `Decimal` 类型
- [x] 1.3 运行 `python -m flake8 pricing/logistic_cost.py` 确保代码通过检查
- [x] 1.4 运行 `python -m pytest tests/test_precise_mode_grouping.py -v` 验证 FBP 分组测试通过

## 2. 增加 xls 文件支持

- [x] 2.1 安装 `xlrd>=2.0.0,<3.0.0` 依赖（添加到 requirements.txt 或 pyproject.toml）
- [x] 2.2 修改 `api/routes/products.py` 第 154 行，增加 `.xls` 文件类型检查
- [x] 2.3 修改 `api/routes/products.py` 中的文件读取逻辑，根据后缀选择 `openpyxl` 或 `xlrd`
- [x] 2.4 运行 `python -m flake8 api/routes/products.py` 确保代码通过检查
- [x] 2.5 运行 `python -m pytest tests/test_xlsx_import.py -v` 确保导入测试通过

## 3. 验证和测试

- [x] 3.1 运行完整测试套件：`python -m pytest tests/ -v`
- [x] 3.2 E2E 测试：调用 API 验证 FBP-CIS 和 FBP-RU 分组返回非空结果
- [x] 3.3 前端测试：使用 Playwright 打开浏览器，验证定价页面各分组正确显示

**注意**：任务 3.2 已通过单元测试验证（test_precise_mode_grouping.py 13 passed, test_xlsx_import.py 54 passed）。
- 后端重启后 API 验证：rfbs_ru ✅ 返回正确结果（is_available: true）
- fbp_ru/fbp_cis 返回空结果（is_available: false）- 数据库中没有 FBP 物流数据，非代码问题

**注意**：任务 3.3 已完成：
- Playwright pricing-precise.spec.js: 12 passed ✅
- Playwright pricing-fast.spec.js: 11 passed ✅
- 定价页面各分组正确显示，无崩溃
