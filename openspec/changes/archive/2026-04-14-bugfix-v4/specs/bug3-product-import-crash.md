# Spec: 产品导入页面崩溃修复

## 目标
修复上传含大量列（144列）且有空列名的 xlsx 文件时，产品导入页面在 Step 2 崩溃的问题。

## 根因
1. 后端 `columns` 列表包含空字符串（来自 xlsx 中 None 列名）
2. 前端将空字符串传给 Radix UI `<SelectItem value="">` 导致组件内部错误
3. 144 列全部渲染在 Select 下拉中，体验极差

## 修改文件

### `api/routes/products.py`
1. 过滤 `headers` 中的空字符串：只返回非空列名
2. `_safe_value` 增强：
   - `float('nan')` / `float('inf')` → `None`
   - `datetime` 对象 → ISO 格式字符串
   - 其他非基础类型 → `str(v)`

### `frontend/src/pages/ProductImportPage.jsx`
1. 防御性过滤：接收 `columns` 后过滤空值 `columns.filter(c => c && c.trim())`
2. 预览表限制显示前 20 列，剩余列显示提示 "...还有 N 列未显示"
3. `JSON.stringify(row)` 作为 key 改为用行索引 `index`（避免大对象 stringify 性能问题）

## 验证
- 上传"定价与物流表不计抛.xlsx"不再崩溃
- Step 2 正确显示字段映射和预览
- flake8 clean
- vitest 通过
