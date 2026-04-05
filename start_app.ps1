# Streamlit 应用启动脚本
# 添加 PostgreSQL bin 到 PATH
$env:PATH += ";C:\Program Files\PostgreSQL\18\bin"

Write-Host "✅ 已添加 PostgreSQL 到 PATH"
Write-Host "正在启动 Streamlit..."

# 激活虚拟环境并启动应用
.\.venv\Scripts\Activate.ps1
streamlit run app.py
