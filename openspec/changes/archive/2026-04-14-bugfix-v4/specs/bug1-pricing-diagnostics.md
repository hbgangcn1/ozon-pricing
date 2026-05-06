# Spec: 精准模式诊断日志

## 目标
为定价精准模式添加诊断日志，帮助排查"无可用方案"和未知物流来源问题。

## 修改文件

### `api/routes/pricing.py`
- 在 `/calculate-grouped` 端点中，加载用户物流后添加 logger.info 记录物流数量和名称列表
- 在 `/calculate` 端点中同样添加

### `pricing/calculate_pricing.py`
- 在 `_run_filters` 完成后，如果结果为空（所有物流被过滤），记录 WARNING 级别日志
- 日志内容包含：总物流数、被过滤数、过滤原因分布

## 验证
- 代码通过 flake8
- 不影响现有测试
- 日志在正常请求中不会过度输出（只在异常情况输出 WARNING）
