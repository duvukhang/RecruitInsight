param([Parameter(Mandatory=$true)][string]$Manifest,[string]$Database='recruitment_verify_restore')
$ErrorActionPreference = 'Stop'
$manifestAbsolute = (Resolve-Path -LiteralPath $Manifest).Path
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    $backupManifest = Get-Content -LiteralPath $manifestAbsolute -Raw | ConvertFrom-Json
    $backupIdentifier = $backupManifest.backup_id
    if ($backupIdentifier -notmatch '^[a-f0-9-]{36}$') { throw 'Invalid backup id' }
    $present = docker compose exec -T backend python -c "from pathlib import Path; print(Path('/data/backups/$backupIdentifier/manifest.json').is_file())"
    if ($present -ne 'True') {
        $backupDirectory = Split-Path -Parent $manifestAbsolute
        docker compose cp $backupDirectory "backend:/data/backups/$backupIdentifier"
        if ($LASTEXITCODE -ne 0) { throw 'Cannot copy backup into the backup volume' }
    }
    docker compose run --rm --user 0:0 --entrypoint python mongo-init scripts/restore.py --manifest "/data/backups/$backupIdentifier/manifest.json" --database $Database
    if ($LASTEXITCODE -ne 0) { throw 'Restore verification failed' }
} finally { Pop-Location }
