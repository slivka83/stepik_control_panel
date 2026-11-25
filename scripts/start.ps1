<#
    Запуск Stepik Control Panel на Windows через Podman.

    Правила, которые защищают данные:
      * база живёт в постоянном томе stepik_pgdata и никогда не пересоздаётся;
      * если том пропал, а бэкап есть — база восстанавливается из бэкапа;
      * если порт базы занят чужим процессом, запуск останавливается,
        чтобы панель не подключилась к другой (пустой) базе;
      * перед запуском делается бэкап, если последнему больше суток.

    Никакие команды удаления томов здесь не выполняются.
#>
[CmdletBinding()]
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

$LogDir = Join-Path $env:TEMP 'stepik-control-panel'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$BackupDir = Join-Path $ProjectDir 'backups'
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$PgContainer = 'stepik-postgres'
$RedisContainer = 'stepik-redis'
$PgVolume = 'stepik_pgdata'
$RedisVolume = 'stepik_redisdata'

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Fail([string]$Message) {
    Write-Host ""
    Write-Host "ОШИБКА: $Message" -ForegroundColor Red
    Write-Host ""
    exit 1
}

function Read-DotEnv([string]$Path) {
    $values = @{}
    if (-not (Test-Path $Path)) { return $values }
    foreach ($raw in Get-Content $Path) {
        $line = $raw.Trim()
        if (-not $line -or $line.StartsWith('#')) { continue }
        $index = $line.IndexOf('=')
        if ($index -lt 1) { continue }
        $key = $line.Substring(0, $index).Trim()
        $value = $line.Substring($index + 1).Trim()
        if ($value.StartsWith('"') -and $value.EndsWith('"')) { $value = $value.Trim('"') }
        $values[$key] = $value
    }
    return $values
}

$envFile = Join-Path $ProjectDir '.env'
if (-not (Test-Path $envFile)) {
    Fail "Не найден файл .env. Скопируйте .env.example в .env и заполните значения."
}
$cfg = Read-DotEnv $envFile

function Get-Config([string]$Key, [string]$Default) {
    if ($cfg.ContainsKey($Key) -and $cfg[$Key]) { return $cfg[$Key] }
    return $Default
}

$PgPort = [int](Get-Config 'POSTGRES_PORT' '5433')
$RedisPort = [int](Get-Config 'REDIS_PORT' '6380')
$BackendPort = [int](Get-Config 'BACKEND_PORT' '8000')
$FrontendPort = [int](Get-Config 'FRONTEND_PORT' '3000')
$PgUser = Get-Config 'POSTGRES_USER' 'stepik_panel'
$PgPassword = Get-Config 'POSTGRES_PASSWORD' 'stepik_panel'
$PgDb = Get-Config 'POSTGRES_DB' 'stepik_panel'
$RedisPassword = Get-Config 'REDIS_PASSWORD' 'stepik_redis'

# --- Podman ---------------------------------------------------------------

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
if (-not $Podman) {
    Fail "Podman не установлен. Установите его командой: winget install RedHat.Podman"
}

# Ошибки Podman в stderr не должны валить весь скрипт: решение принимается по коду возврата.
function Invoke-Podman {
    $ErrorActionPreference = 'Continue'
    & $Podman @args
    $global:LASTEXITCODE = $LASTEXITCODE
}

Write-Step "Проверка Podman"
Invoke-Podman info *> $null
if ($LASTEXITCODE -ne 0) {
    # Застрявший сокет от прошлого запуска мешает машине подняться.
    $staleSocket = Join-Path $env:TEMP 'podman\podman-machine-default-api.sock'
    if ((Test-Path $staleSocket) -and -not (Test-Path '\\.\pipe\podman-machine-default')) {
        Remove-Item $staleSocket -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  Запуск виртуальной машины Podman..."
    Invoke-Podman machine start | Out-Host
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 2
        Invoke-Podman info *> $null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    }
    if (-not $ready) {
        Fail "Виртуальная машина Podman не запустилась. Выполните: podman machine start"
    }
}
Write-Host "  Podman готов" -ForegroundColor Green

# --- Защита портов --------------------------------------------------------

function Get-ListenerProcess([int]$Port) {
    $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $connection) { return $null }
    return Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
}

function Assert-PortFreeOrOurs([int]$Port, [string]$ContainerName) {
    $process = Get-ListenerProcess $Port
    if (-not $process) { return }

    Invoke-Podman container exists $ContainerName *> $null
    $containerExists = ($LASTEXITCODE -eq 0)
    if ($containerExists) {
        $running = (Invoke-Podman inspect -f '{{.State.Running}}' $ContainerName 2>$null) -eq 'true'
        if ($running) { return }
    }

    Fail ("Порт $Port уже занят процессом '$($process.ProcessName)'. " +
          "Похоже, там работает другая база данных. Остановите её и запустите снова — " +
          "панель не должна подключаться к чужой или пустой базе.")
}

# --- Защита портов (до создания томов) ------------------------------------

Write-Step "PostgreSQL (порт $PgPort)"
Assert-PortFreeOrOurs $PgPort $PgContainer
Write-Step "Redis (порт $RedisPort)"
Assert-PortFreeOrOurs $RedisPort $RedisContainer

# --- Постоянные тома ------------------------------------------------------

Invoke-Podman volume inspect $PgVolume *> $null
if ($LASTEXITCODE -ne 0) {
    Invoke-Podman volume create $PgVolume | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "Не удалось создать том базы $PgVolume" }
}

Invoke-Podman volume inspect $RedisVolume *> $null
if ($LASTEXITCODE -ne 0) {
    Invoke-Podman volume create $RedisVolume | Out-Null
}

# --- Контейнеры -----------------------------------------------------------

function Start-OrCreateContainer([string]$Name, [string[]]$RunArgs) {
    Invoke-Podman container exists $Name *> $null
    if ($LASTEXITCODE -eq 0) {
        $running = (Invoke-Podman inspect -f '{{.State.Running}}' $Name 2>$null) -eq 'true'
        if (-not $running) {
            Invoke-Podman start $Name | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Fail "Не удалось запустить контейнер $Name. Посмотрите: podman logs $Name"
            }
        }
        return
    }

    Invoke-Podman run @RunArgs | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Fail "Не удалось создать контейнер $Name. Посмотрите: podman logs $Name"
    }
}

$pgArgs = @(
    '-d', '--name', $PgContainer, '--restart', 'unless-stopped',
    '-e', "POSTGRES_USER=$PgUser",
    '-e', "POSTGRES_PASSWORD=$PgPassword",
    '-e', "POSTGRES_DB=$PgDb",
    '-p', "${PgPort}:5432",
    '-v', "${PgVolume}:/var/lib/postgresql/data",
    'docker.io/library/postgres:16-alpine'
)
Start-OrCreateContainer $PgContainer $pgArgs

$redisArgs = @(
    '-d', '--name', $RedisContainer, '--restart', 'unless-stopped',
    '-p', "${RedisPort}:6379",
    '-v', "${RedisVolume}:/data",
    'docker.io/library/redis:7-alpine',
    'redis-server', '--requirepass', $RedisPassword
)
Start-OrCreateContainer $RedisContainer $redisArgs

$pgReady = $false
for ($i = 0; $i -lt 60; $i++) {
    Invoke-Podman exec $PgContainer pg_isready -U $PgUser -d $PgDb *> $null
    if ($LASTEXITCODE -eq 0) { $pgReady = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $pgReady) {
    Fail "PostgreSQL не отвечает. Посмотрите: podman logs $PgContainer"
}
Write-Host "  PostgreSQL готов" -ForegroundColor Green
Write-Host "  Redis готов" -ForegroundColor Green

# --- Восстановление из бэкапа (если база пустая, а бэкап есть) ------------

$latestBackup = Get-ChildItem $BackupDir -Filter 'stepik_*.dump' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1

$coursesRaw = Invoke-Podman exec $PgContainer psql -U $PgUser -d $PgDb -t -A `
    -c "SELECT CASE WHEN to_regclass('public.courses') IS NULL THEN 0 ELSE (SELECT count(*) FROM courses) END;" 2>$null
$dbEmpty = $true
if ($LASTEXITCODE -eq 0) {
    $dbEmpty = ([int](($coursesRaw | Out-String).Trim()) -eq 0)
}

if ($latestBackup -and $dbEmpty) {
    Write-Step "Восстановление базы из бэкапа: $($latestBackup.Name)"
    Invoke-Podman cp $latestBackup.FullName "${PgContainer}:/tmp/stepik_restore.dump"
    Invoke-Podman exec $PgContainer pg_restore -U $PgUser -d $PgDb `
        --no-owner --no-privileges --clean --if-exists --exit-on-error `
        /tmp/stepik_restore.dump | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Fail ("Не удалось восстановить базу из бэкапа $($latestBackup.FullName). " +
              "Файл сохранён, база не запущена, чтобы не показывать пустые данные.")
    }
    Invoke-Podman exec $PgContainer rm -f /tmp/stepik_restore.dump | Out-Null
    Write-Host "  База восстановлена из бэкапа" -ForegroundColor Green
}
elseif ($dbEmpty) {
    Write-Host ""
    Write-Host "  ВНИМАНИЕ: бэкапов нет, база создана пустой." -ForegroundColor Yellow
    Write-Host "  После входа в панель нажмите «Обновить», чтобы загрузить данные." -ForegroundColor Yellow
}

# --- Миграции -------------------------------------------------------------

Write-Step "Миграции базы"
$alembic = Join-Path $ProjectDir 'backend\.venv\Scripts\alembic.exe'
if (-not (Test-Path $alembic)) {
    Fail "Не найдено окружение backend. Установите зависимости: cd backend; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
}
Push-Location (Join-Path $ProjectDir 'backend')
try {
    & $alembic upgrade head | Out-Host
    if ($LASTEXITCODE -ne 0) { Fail "Миграции базы завершились ошибкой" }
}
finally {
    Pop-Location
}

# --- Бэкап ----------------------------------------------------------------

$latestBackup = Get-ChildItem $BackupDir -Filter 'stepik_*.dump' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
$needBackup = (-not $latestBackup) -or ($latestBackup.LastWriteTime -lt (Get-Date).AddHours(-24))
if ($needBackup) {
    Write-Step "Создание бэкапа базы"
    try {
        & (Join-Path $PSScriptRoot 'backup.ps1') -Reason 'auto' | Out-Host
    }
    catch {
        Write-Host "  Не удалось сделать бэкап: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# --- Backend и frontend ---------------------------------------------------

function Stop-OwnListener([int]$Port, [string[]]$AllowedNames) {
    $process = Get-ListenerProcess $Port
    if (-not $process) { return }
    if ($AllowedNames -notcontains $process.ProcessName) {
        Fail "Порт $Port занят процессом '$($process.ProcessName)'. Освободите его и запустите снова."
    }
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

Write-Step "Backend (порт $BackendPort)"
Stop-OwnListener $BackendPort @('uvicorn', 'python')
$backendDir = Join-Path $ProjectDir 'backend'
$uvicorn = Join-Path $backendDir '.venv\Scripts\uvicorn.exe'
$backendOut = Join-Path $LogDir 'backend.log'
$backendErr = Join-Path $LogDir 'backend.err.log'
$backendProcess = Start-Process -FilePath $uvicorn `
    -ArgumentList @('app.main:app', '--host', '0.0.0.0', '--port', "$BackendPort") `
    -WorkingDirectory $backendDir `
    -RedirectStandardOutput $backendOut `
    -RedirectStandardError $backendErr `
    -PassThru -WindowStyle Hidden
$backendProcess.Id | Set-Content (Join-Path $LogDir 'backend.pid')

$backendReady = $false
for ($i = 0; $i -lt 90; $i++) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$BackendPort/api/health" -TimeoutSec 2
        if ($response.StatusCode -eq 200) { $backendReady = $true; break }
    }
    catch { }
    Start-Sleep -Seconds 1
}
if (-not $backendReady) {
    Fail "Backend не ответил за 90 секунд. Лог: $backendErr"
}
Write-Host "  Backend готов" -ForegroundColor Green

Write-Step "Frontend (порт $FrontendPort)"
Stop-OwnListener $FrontendPort @('node', 'npm')
$frontendDir = Join-Path $ProjectDir 'frontend'
if (-not (Test-Path (Join-Path $frontendDir 'node_modules'))) {
    Write-Host "  Установка зависимостей frontend..."
    Push-Location $frontendDir
    try { & npm.cmd install | Out-Host } finally { Pop-Location }
}
$frontendOut = Join-Path $LogDir 'frontend.log'
$frontendErr = Join-Path $LogDir 'frontend.err.log'
$frontendProcess = Start-Process -FilePath 'npm.cmd' `
    -ArgumentList @('run', 'dev', '--', '--port', "$FrontendPort", '--host', '0.0.0.0') `
    -WorkingDirectory $frontendDir `
    -RedirectStandardOutput $frontendOut `
    -RedirectStandardError $frontendErr `
    -PassThru -WindowStyle Hidden
$frontendProcess.Id | Set-Content (Join-Path $LogDir 'frontend.pid')

$frontendReady = $false
for ($i = 0; $i -lt 90; $i++) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$FrontendPort/" -TimeoutSec 2
        if ($response.StatusCode -eq 200) { $frontendReady = $true; break }
    }
    catch { }
    Start-Sleep -Seconds 1
}
if (-not $frontendReady) {
    Fail "Frontend не ответил за 90 секунд. Лог: $frontendErr"
}
Write-Host "  Frontend готов" -ForegroundColor Green

# --- Итог ----------------------------------------------------------------

$courseCount = (Invoke-Podman exec $PgContainer psql -U $PgUser -d $PgDb -t -A -c 'select count(*) from courses;' 2>$null).Trim()

Write-Host ""
Write-Host "  Stepik Control Panel запущена" -ForegroundColor Green
Write-Host ""
Write-Host "  Панель:  http://localhost:$FrontendPort"
Write-Host "  API:     http://localhost:$BackendPort"
Write-Host "  Курсов в базе: $courseCount"
Write-Host ""
Write-Host "  Логи:    $LogDir"
Write-Host "  Бэкапы:  $BackupDir"
Write-Host "  Остановка: stop.bat"
Write-Host ""

if (-not $NoBrowser) {
    Start-Process "http://localhost:$FrontendPort" | Out-Null
}
