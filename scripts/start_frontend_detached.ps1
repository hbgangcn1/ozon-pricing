param(
    [Parameter(Mandatory=$false)][string]$LogFile = "frontend.log"
)
Set-Location -LiteralPath "C:\Users\hbgan\OneDrive\Robert\learn\logistics"
if (Test-Path -LiteralPath $LogFile) { Remove-Item -LiteralPath $LogFile -Force }
$proc = Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ".\scripts\_run_frontend_inner.ps1", "-LogFile", $LogFile `
    -WindowStyle Hidden `
    -PassThru
"frontend_launcher_pid=$($proc.Id)"
"started_at=$(Get-Date -Format HH:mm:ss)"
