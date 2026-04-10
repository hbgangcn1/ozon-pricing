@echo off
setlocal

:: ── 前置检查 ──────────────────────────────────────────────
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [ERROR] 找不到虚拟环境：%~dp0.venv\Scripts\python.exe
    echo 请先创建虚拟环境：python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "%~dp0frontend\node_modules" (
    echo [WARN] 未找到 frontend\node_modules，请先在 frontend 目录执行 npm install
)

:: ── 清理旧进程（按端口） ─────────────────────────────────────
call :kill_port 8003
call :kill_port 3001

:: ── 启动后端（使用 venv 的 python） ─────────────────────────
echo [启动] FastAPI 后端...
start "logistics-backend" "%~dp0.venv\Scripts\python.exe" -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8003

:: ── 启动前端 ────────────────────────────────────────────────
echo [启动] Vite 前端...
start "logistics-frontend" cmd /c "cd /d "%~dp0frontend" && npm run dev"

:: ── 状态输出 ─────────────────────────────────────────────
echo.
echo ==========================================
echo   开发环境已启动
echo ==========================================
echo   Backend  : http://localhost:8003
echo   Frontend : http://localhost:3001
echo ==========================================
echo.
echo 关闭后端窗口（logistics-backend）和前端窗口（logistics-frontend）即可停止服务。

endlocal
exit /b 0

:kill_port
:: 用法: call :kill_port <端口号>
:: 查找监听指定端口的进程并终止（含子进程树）
setlocal
set "PORT=%~1"
for /f "tokens=5" %%a in ('netstat -aon -p TCP ^| findstr "LISTENING" ^| findstr ":%PORT% "') do (
    if not "%%a"=="0" (
        echo [清理] 端口 %PORT% 被 PID %%a 占用，正在终止...
        taskkill /PID %%a /T /F >nul 2>&1
    )
)
endlocal
exit /b 0
