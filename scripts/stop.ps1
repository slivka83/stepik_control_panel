<#
    Остановка Stepik Control Panel.

    Перед остановкой делается бэкап базы. Контейнеры и тома не удаляются:
    при следующем запуске данные останутся на месте.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

$LogDir = Join-Path $env:TEMP 'stepik-control-panel'
$PgContainer = 'stepik-postgres'
$RedisContainer = 'stepik-redis'

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

$Podman = $null
$cmd = Get-Command 'podman.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($cmd) { $Podman = $cmd.Source }
if (-not $Podman) {
    foreach ($candidate in @(
        (Join-Path $env:ProgramFiles 'RedHat\Podman\podman.exe'),
        (Join-Path $env:ProgramFiles 'Podman\podman.exe')
    )) {
        if (Test-Path $candidate) { $Podman = $candidate; break }
    }
}

# Ошибки Podman в stderr не должны валить весь скрипт: решение принимается по коду возврата.
function Invoke-Podman {
    $ErrorActionPreference = 'Continue'
    & $Podman @args
    $global:LASTEXITCODE = $LASTEXITCODE
}

function Stop-PortListener([int]$Port, [string[]]$AllowedNames) {
    $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $connection) { return }
    $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
    if (-not $process) { return }
    if ($AllowedNames -notcontains $process.ProcessName) { return }
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
}

# --- Бэкап ----------------------------------------------------------------

if ($Podman) {
    Write-Step "Бэкап базы"
    try {
        & (Join-Path $PSScriptRoot 'backup.ps1') -Reason 'stop' | Out-Host
    }
    catch {
        Write-Host "  Бэкап не сделан: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# --- Backend и frontend ---------------------------------------------------

Write-Step "Остановка backend и frontend"
$allowedNames = @{
    backend = @('uvicorn', 'python')
    frontend = @('node', 'npm', 'cmd')
}
foreach ($name in @('backend', 'frontend')) {
    $pidFile = Join-Path $LogDir "$name.pid"
    if (Test-Path $pidFile) {
        $pidValue = (Get-Content $pidFile -Raw).Trim()
        if ($pidValue) {
            $process = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
            if ($process -and $allowedNames[$name] -contains $process.ProcessName) {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
}
Stop-PortListener 8000 @('uvicorn', 'python')
Stop-PortListener 3000 @('node', 'npm')

# --- Контейнеры -----------------------------------------------------------

if ($Podman) {
    Write-Step "Остановка контейнеров (данные сохраняются)"
    Invoke-Podman stop -t 15 $PgContainer $RedisContainer 2>$null | Out-Null
}

Write-Host ""
Write-Host "  Панель остановлена. База и бэкапы сохранены." -ForegroundColor Green
Write-Host ""
