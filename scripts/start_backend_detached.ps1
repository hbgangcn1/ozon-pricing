param(
    [Parameter(Mandatory=$false)][string]$LogFile = "backend.log"
)
# 启动后端 — agent-friendly detach：
# 1. Start-Process 启动独立 PowerShell 子进程，bash 工具立即返回（不持有任何句柄）
# 2. 子 PowerShell 自己负责重定向到 LogFile
# 3. -WindowStyle Hidden 隐藏窗口（与 -RedirectStandardOutput 不同：本方案不让父进程持有 redirected 句柄）
# 4. 返回子进程 PID 供 agent 跟踪
Set-Location -LiteralPath "C:\Users\hbgan\OneDrive\Robert\learn\logistics"
if (Test-Path -LiteralPath $LogFile) { Remove-Item -LiteralPath $LogFile -Force }
$proc = Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ".\scripts\_run_backend_inner.ps1", "-LogFile", $LogFile `
    -WindowStyle Hidden `
    -PassThru
"backend_launcher_pid=$($proc.Id)"
"started_at=$(Get-Date -Format HH:mm:ss)"
