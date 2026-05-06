# Spec: 公共物流池修复

## 目标
修复公共物流池的三个问题：只显示100条、导入500错误、删除全部失败。

## 修改文件

### Bug 2.1: 显示限制
**`frontend/src/pages/LogisticsPoolPage.jsx`**
- `fetchLogistics()` 调用 `logisticsPoolAPI.getAll({ limit: 1000 })` 而不是无参数调用

### Bug 2.2: 导入错误处理
**`api/routes/logistics_pool.py`**
- import 端点的 `for index, row in enumerate(result.get("rows", []))` 循环外添加 try/catch
- 捕获 SQLAlchemy/DB 级异常，记录日志并返回已导入数量 + 错误信息
- 确保部分成功时不丢失已导入数据（在 per-row loop 中添加 `await session.commit()` 每 N 行提交一次）

### Bug 2.3: 删除错误信息
**`frontend/src/pages/LogisticsPoolPage.jsx`**
- `handleDeleteAll` catch 块改为 `toast.error(error?.response?.data?.detail || '删除失败')`

**`api/routes/logistics_pool.py`**
- delete 端点添加 try/except 包裹，返回 HTTPException(500, detail=str(exc))

## 验证
- 导入174条数据后，前端能显示全部174条
- 导入失败时前端显示具体错误信息而非 "Internal Server Error"
- 删除全部时显示具体错误原因
- flake8 clean
- 现有测试通过
