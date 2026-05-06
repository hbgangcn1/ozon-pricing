## 1. 数据库迁移

- [x] 1.1 在 models/logistics.py 和 models/logistics_pool.py 中添加 sum_of_sides_threshold 字段（Integer, server_default 0）
- [x] 1.2 在 api/models/schemas.py 中添加 sum_of_sides_threshold 字段
- [x] 1.3 创建 Alembic 迁移：新增 sum_of_sides_threshold 列 + 将 volume_mode='threshold' 更新为 'longest_side'
- [x] 1.4 执行 alembic upgrade head 确认迁移成功

## 2. 后端定价逻辑

- [x] 2.1 在 pricing/logistic_cost.py _calc_volume_weight 中新增 "sum_of_sides" 分支
- [x] 2.2 在 pricing/filter.py _filter_check_weight 中新增 "sum_of_sides" 分支
- [x] 2.3 在 db/logistics_crud.py 的 allowed fields 中添加 sum_of_sides_threshold
- [x] 2.4 运行 flake8 确认代码规范

## 3. FBP XLSX 导入解析

- [x] 3.1 在 xlsx_import/parsers/fbp.py 中添加 "Sum of sides" 模式识别逻辑：正则匹配 S 列提取阈值，设 volume_mode="sum_of_sides"
- [x] 3.2 添加 sum_of_sides_threshold 字段到解析结果 item dict
- [x] 3.3 在 db/logistics_pool.py 的 insert_row 中确保 sum_of_sides_threshold 字段被写入

## 4. 前端物流规则表单

- [x] 4.1 修复 LogisticsPage.jsx 中 volume_mode Select 值：threshold → longest_side
- [x] 4.2 新增 "三边和超过阈值时按体积重量计费"（value="sum_of_sides"）选项
- [x] 4.3 添加 volume_coefficient 和 sum_of_sides_threshold 到 DEFAULT_FORM
- [x] 4.4 handleEdit 中添加 volume_coefficient 和 sum_of_sides_threshold 字段加载
- [x] 4.5 实现条件字段渲染：longest_side 显示阈值+系数，sum_of_sides 显示阈值+系数，max_actual_vs_volume 显示系数
- [x] 4.6 在 LogisticsPoolPage.jsx 中显示 sum_of_sides_threshold 字段

## 5. 单元测试

- [x] 5.1 pytest: 测试 _calc_volume_weight "sum_of_sides" 模式（超过阈值/未超过）
- [x] 5.2 pytest: 测试 _filter_check_weight "sum_of_sides" 模式
- [x] 5.3 pytest: 测试 FBP 解析器正确解析 "Sum of sides ≤ 90 cm" 和 "Sum of sides ≤ 75 cm"
- [x] 5.4 运行完整 pytest 套件确认无回归

## 6. E2E 测试

- [x] 6.1 E2E: 导入 FBP XLSX → 验证所有 volume_mode/sum_of_sides_threshold/volume_coefficient 组合正确
- [x] 6.2 E2E: 从物流池添加"sum_of_sides"记录到用户规则 → 验证字段传递正确
- [x] 6.3 E2E: 定价计算验证——sum_of_sides 模式下三边和超过阈值时计费重量正确
- [x] 6.4 E2E: 定价计算验证——longest_side 模式下最长边超过阈值时计费重量正确
- [x] 6.5 清理临时测试脚本
