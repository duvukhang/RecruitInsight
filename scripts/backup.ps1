$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
$streamingWasRunning = $false
try {
    $streamingServices = docker compose -f docker-compose.yml -f docker-compose.streaming.yml ps --status running --services
    $streamingWasRunning = $streamingServices -contains 'streaming-worker'
    if ($streamingWasRunning) { docker compose -f docker-compose.yml -f docker-compose.streaming.yml stop streaming-worker }
    docker compose stop etl-worker training-worker
    if ($LASTEXITCODE -ne 0) { throw 'Cannot stop compute workers' }
    $backupOutput = docker compose exec -T backend python scripts/backup.py
    if ($LASTEXITCODE -ne 0) { throw 'Backup failed' }
    $backupInfo = $backupOutput | ConvertFrom-Json
    $localBackup = Join-Path 'artifacts/backups' $backupInfo.backup_id
    New-Item -ItemType Directory -Force 'artifacts/backups' | Out-Null
    docker compose cp "backend:/data/backups/$($backupInfo.backup_id)" $localBackup
    if ($LASTEXITCODE -ne 0) { throw 'Could not copy backup to host' }
    Write-Host "Backup manifest: $localBackup/manifest.json"
} finally {
    docker compose start etl-worker training-worker
    if ($streamingWasRunning) { docker compose -f docker-compose.yml -f docker-compose.streaming.yml start streaming-worker }
    Pop-Location
}
