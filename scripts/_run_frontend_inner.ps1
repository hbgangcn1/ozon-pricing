param(
    [Parameter(Mandatory=$false)][string]$LogFile = "frontend.log"
)
Set-Location -LiteralPath "C:\Users\hbgan\OneDrive\Robert\learn\logistics\frontend"
& npm.cmd run dev *>&1 |
    Out-File -FilePath ("..\" + $LogFile) -Encoding utf8 -Append
