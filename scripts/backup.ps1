<#
    Бэкап базы Stepik Control Panel.

    Дамп снимается внутри контейнера и копируется в папку backups.
    Хранятся последние 10 дампов. Папка backups не попадает в Git.
#>
[CmdletBinding()]
param(
    [string]$Reason = 'manual'
)

$ErrorActionPreference = 'Stop'

$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

$BackupDir = Join-Path $ProjectDir 'backups'
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$PgContainer = 'stepik-postgres'

function Fail([string]$Message) {
    Write-Host "ОШИБКА: $Message" -ForegroundColor Red
    exit 1
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
if (-not $Podman) { Fail "Podman не установлен" }

# Ошибки Podman в stderr не должны валить весь скрипт: решение принимается по коду возврата.
function Invoke-Podman {
    $ErrorActionPreference = 'Continue'
    & $Podman @args
    $global:LASTEXITCODE = $LASTEXITCODE
}

Invoke-Podman container exists $PgContainer *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Контейнер базы не создан — бэкап не нужен." -ForegroundColor Yellow
    exit 0
}

$running = (Invoke-Podman inspect -f '{{.State.Running}}' $PgContainer 2>$null) -eq 'true'
if (-not $running) {
    Write-Host "  База остановлена — бэкап пропущен." -ForegroundColor Yellow
    exit 0
}

$cfg = @{}
foreach ($raw in Get-Content (Join-Path $ProjectDir '.env')) {
    $line = $raw.Trim()
    if (-not $line -or $line.StartsWith('#')) { continue }
    $index = $line.IndexOf('=')
    if ($index -lt 1) { continue }
    $value = $line.Substring($index + 1).Trim()
    if ($value.StartsWith('"') -and $value.EndsWith('"')) { $value = $value.Trim('"') }
    $cfg[$line.Substring(0, $index).Trim()] = $value
}
$PgUser = if ($cfg['POSTGRES_USER']) { $cfg['POSTGRES_USER'] } else { 'stepik_panel' }
$PgDb = if ($cfg['POSTGRES_DB']) { $cfg['POSTGRES_DB'] } else { 'stepik_panel' }

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$name = "stepik_${stamp}_${Reason}.dump"
$destination = Join-Path $BackupDir $name

Invoke-Podman exec $PgContainer pg_dump -U $PgUser -d $PgDb -Fc -f /tmp/stepik_backup.dump
if ($LASTEXITCODE -ne 0) { Fail "pg_dump завершился ошибкой" }

Invoke-Podman exec $PgContainer pg_restore -l /tmp/stepik_backup.dump *> $null
if ($LASTEXITCODE -ne 0) {
    Invoke-Podman exec $PgContainer rm -f /tmp/stepik_backup.dump | Out-Null
    Fail "Дамп повреждён, бэкап не сохранён"
}

Invoke-Podman cp "${PgContainer}:/tmp/stepik_backup.dump" $destination
if ($LASTEXITCODE -ne 0) { Fail "Не удалось скопировать дамп на диск" }
Invoke-Podman exec $PgContainer rm -f /tmp/stepik_backup.dump | Out-Null

$file = Get-Item $destination
if ($file.Length -lt 1024) {
    Remove-Item $destination -Force
    Fail "Дамп получился пустым, бэкап не сохранён"
}

# Храним последние 10 дампов.
Get-ChildItem $BackupDir -Filter 'stepik_*.dump' |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 10 |
    Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host ("  Бэкап сохранён: {0} ({1:N1} МБ)" -f $name, ($file.Length / 1MB)) -ForegroundColor Green
