param(
    [Parameter(Mandatory=$false)][string]$LogFile = "backend.log"
)
# 独立 PowerShell 子进程入口，由 scripts/start_backend_detached.ps1 调起
# 父 bash 工具不持有任何子进程句柄
Set-Location -LiteralPath "C:\Users\hbgan\OneDrive\Robert\learn\logistics"
$env:ALLOWED_ORIGINS = 'http://localhost:3001'
$env:E2E_TEST = '1'
$env:E2E_DISABLE_NEW_LOGIN_SESSION_KICK = '1'
# *>&1 合并 stdout+stderr，Out-File 实时刷盘
& .\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8003 *>&1 |
    Out-File -FilePath $LogFile -Encoding utf8 -Append
