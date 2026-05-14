# 注意：默认用 Continue，避免单条 cmdlet 出错就让脚本闪退（双击运行时尤其致命）。
# 关键步骤需要"出错就停"的，自己用 try/catch 包。
$ErrorActionPreference = 'Continue'

# 双击 .ps1 闪退保护：任何未捕获异常都暂停窗口，让用户看到错误信息。
trap {
    Write-Host ''
    Write-Host '!!!! 脚本异常退出 !!!!' -ForegroundColor Red
    Write-Host $_ -ForegroundColor Red
    Write-Host $_.ScriptStackTrace -ForegroundColor DarkRed
    Write-Host ''
    Read-Host '按回车键关闭窗口'
    exit 1
}

$repoRoot = $PSScriptRoot
if (-not $repoRoot) { $repoRoot = Get-Location }

$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
$frontendDir = Join-Path $repoRoot 'frontend'
$frontendNodeModules = Join-Path $frontendDir 'node_modules'

# ── 前置检查 ──────────────────────────────────────────────
if (-not (Test-Path $venvPython)) {
    Write-Host "[ERROR] 找不到虚拟环境 Python：$venvPython" -ForegroundColor Red
    Write-Host '请先创建虚拟环境：python -m venv .venv ; .venv\Scripts\pip install -r requirements.txt' -ForegroundColor Yellow
    Read-Host '按回车键关闭窗口'
    exit 1
}

if (-not (Test-Path $frontendNodeModules)) {
    Write-Warning "未找到 frontend\node_modules，请先在 frontend 目录执行 npm install"
}

# ── 清理旧进程（按端口） ──────────────────────────────────────
function Stop-PortProcess {
    param([int]$Port)
    $maxAttempts = 3
    for ($attempt = 0; $attempt -lt $maxAttempts; $attempt++) {
        $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if (-not $connections) { return }

        # 检查是否有活跃进程持有该端口
        $procIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        $hasLiveProcess = $false
        $killTargets = @()
        foreach ($procId in $procIds) {
            $live = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if (-not $live) { continue }
            $hasLiveProcess = $true
            $killTargets += $procId
            # 向上追溯父进程（处理 uvicorn --reload 的父子结构）
            try {
                $cim = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction Stop
                if ($cim.ParentProcessId -and $cim.ParentProcessId -ne 0) {
                    $parent = Get-Process -Id $cim.ParentProcessId -ErrorAction SilentlyContinue
                    if ($parent -and $parent.ProcessName -in @('python', 'python3', 'node', 'cmd')) {
                        $killTargets += $cim.ParentProcessId
                    }
                }
            } catch {}
        }

        # 端口被已死进程的残留 socket 占用（Windows 内核延迟回收），不影响新服务绑定
        if (-not $hasLiveProcess) {
            Write-Host "[清理] 端口 $Port 有残留 socket（进程已退出），不影响启动。" -ForegroundColor DarkYellow
            return
        }

        # 去重后逐个杀
        $killTargets = $killTargets | Select-Object -Unique | Sort-Object
        foreach ($target in $killTargets) {
            try {
                $proc = Get-Process -Id $target -ErrorAction Stop
                Write-Host "[清理] 端口 $Port — 终止 $($proc.ProcessName) (PID: $target)..." -ForegroundColor Yellow
                taskkill /PID $target /T /F 2>$null | Out-Null
            } catch {}
        }
        # 等待端口释放
        for ($wait = 0; $wait -lt 8; $wait++) {
            Start-Sleep -Milliseconds 500
            $still = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
            if (-not $still) {
                Write-Host "[清理] 端口 $Port 已释放。" -ForegroundColor Green
                return
            }
        }
    }
    Write-Warning "端口 $Port 可能仍有残留连接，将尝试继续启动。"
}

Stop-PortProcess -Port 8003
Stop-PortProcess -Port 3001

# ── 设置后端环境变量（CORS / 开发模式）────────────────────────
# ALLOWED_ORIGINS 必须包含 vite 实际监听的端口；vite.config.js 锁定 3001（strictPort），
# 但保留 3002/5173 作为兜底防止本机其他实例占用导致漂移。
$env:ALLOWED_ORIGINS = 'http://localhost:3001,http://localhost:3002,http://localhost:5173'

# ── 启动后端（uvicorn）──────────────────────────────────────
Write-Host '[启动] FastAPI 后端...' -ForegroundColor Cyan
Write-Host "  ALLOWED_ORIGINS = $env:ALLOWED_ORIGINS" -ForegroundColor DarkGray
$backendProcess = Start-Process `
    -FilePath $venvPython `
    -ArgumentList '-m', 'uvicorn', 'api.main:app', '--reload', '--host', '0.0.0.0', '--port', '8003' `
    -WorkingDirectory $repoRoot `
    -PassThru `
    -WindowStyle Normal

# ── 启动前端（npm run dev）─────────────────────────────────
Write-Host '[启动] Vite 前端...' -ForegroundColor Cyan
$frontendProcess = Start-Process `
    -FilePath 'cmd.exe' `
    -ArgumentList '/c', 'npm', 'run', 'dev' `
    -WorkingDirectory $frontendDir `
    -PassThru `
    -WindowStyle Normal

# ── 状态输出 ─────────────────────────────────────────────
Write-Host ''
Write-Host '==========================================' -ForegroundColor Green
Write-Host '  开发环境已启动' -ForegroundColor Green
Write-Host '==========================================' -ForegroundColor Green
Write-Host "  Backend  : http://localhost:8003" -ForegroundColor Yellow
Write-Host "  Frontend : http://localhost:3001" -ForegroundColor Yellow
Write-Host '==========================================' -ForegroundColor Green
Write-Host ''
Write-Host '按 Ctrl+C 退出，脚本将自动关闭后端和前端进程。' -ForegroundColor Gray

# ── 等待 + 清理 ──────────────────────────────────────────
function Stop-ProcessTree {
    param([int]$ParentId)
    try {
        # 先停子进程
        Get-CimInstance Win32_Process |
            Where-Object { $_.ParentProcessId -eq $ParentId } |
            ForEach-Object { Stop-ProcessTree -ParentId $_.ProcessId }
        # 再停父进程
        Stop-Process -Id $ParentId -Force -ErrorAction SilentlyContinue
    }
    catch {
        # 进程可能已退出，忽略
    }
}

# ── 等待端口就绪 + 按端口监控存活 ──────────────────────────────
# 不能用 $backendProcess.HasExited / $frontendProcess.HasExited 判活：
#   - uvicorn --reload 在 Windows 上是 reloader 父进程 + worker 子进程结构，
#     Start-Process 拿到的是 reloader 句柄，它启动后会很快 detach/exit。
#   - cmd /c npm run dev 同理：cmd.exe 启动 npm 后立刻退出，留下孙子 node.exe。
# 正确做法：按端口 8003/3001 的 LISTENING 状态判定服务存活。
function Test-PortListening {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return [bool]$conn
}

function Get-PortOwnerPids {
    param([int]$Port)
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { return @() }
    return @($conns | Select-Object -ExpandProperty OwningProcess -Unique)
}

function Stop-PortTree {
    param([int]$Port)
    $ownerPids = Get-PortOwnerPids -Port $Port
    foreach ($ownerId in $ownerPids) {
        $live = Get-Process -Id $ownerId -ErrorAction SilentlyContinue
        if (-not $live) { continue }
        try {
            Write-Host "  关闭端口 $Port — $($live.ProcessName) (PID: $ownerId)" -ForegroundColor DarkYellow
            taskkill /PID $ownerId /T /F 2>$null | Out-Null
        } catch {}
    }
}

# 等待端口就绪（最多 30s）
Write-Host ''
Write-Host '等待服务就绪...' -ForegroundColor Gray
$backendUp = $false
$frontendUp = $false
for ($i = 0; $i -lt 60; $i++) {
    if (-not $backendUp -and (Test-PortListening -Port 8003)) {
        $backendUp = $true
        Write-Host '  [OK] 后端 8003 已监听' -ForegroundColor Green
    }
    if (-not $frontendUp -and (Test-PortListening -Port 3001)) {
        $frontendUp = $true
        Write-Host '  [OK] 前端 3001 已监听' -ForegroundColor Green
    }
    if ($backendUp -and $frontendUp) { break }
    Start-Sleep -Milliseconds 500
}
if (-not $backendUp)  { Write-Warning '后端 8003 在 30s 内未监听，请检查后端窗口是否报错。' }
if (-not $frontendUp) { Write-Warning '前端 3001 在 30s 内未监听，请检查前端窗口是否报错。' }

try {
    # 按端口轮询：只要其中一个端口不再监听即认为服务挂了
    while ($true) {
        $bAlive = Test-PortListening -Port 8003
        $fAlive = Test-PortListening -Port 3001
        if (-not $bAlive -and -not $fAlive) {
            Write-Host '后端和前端端口均已释放（服务退出）。' -ForegroundColor Yellow
            break
        }
        Start-Sleep -Seconds 2
    }
}
finally {
    Write-Host '正在关闭开发环境...' -ForegroundColor Yellow
    # 按端口关，覆盖所有 reloader/worker/cmd/node 子进程
    Stop-PortTree -Port 8003
    Stop-PortTree -Port 3001
    # 兜底：原始 launcher 句柄（如果还活着）
    foreach ($proc in @($backendProcess, $frontendProcess)) {
        if ($proc -and -not $proc.HasExited) {
            Stop-ProcessTree -ParentId $proc.Id
        }
    }
    Write-Host '开发环境已关闭。' -ForegroundColor Green
    Write-Host ''
    Read-Host '按回车键关闭窗口'
}
