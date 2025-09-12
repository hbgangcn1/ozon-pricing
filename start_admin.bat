@echo off
echo 启动管理员后台系统...
echo 访问地址: http://localhost:8517
echo 默认账号: admin / admin123
echo.
python -m streamlit run admin_backend.py --server.port 8517
pause

