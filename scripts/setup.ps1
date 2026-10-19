$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.env')) {
        $configText = Get-Content -LiteralPath '.env.example' -Raw
        foreach ($secretName in @('MONGO_ROOT_PASSWORD','MONGO_APP_PASSWORD','JWT_SECRET','ADMIN_PASSWORD')) {
            $secretBytes = New-Object byte[] 32
            $randomGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
            $randomGenerator.GetBytes($secretBytes)
            $randomGenerator.Dispose()
            $secretValue = [Convert]::ToBase64String($secretBytes).Replace('+','-').Replace('/','_').TrimEnd('=')
            $configText = $configText -replace "(?m)^$secretName=\s*$", "$secretName=$secretValue"
        }
        [System.IO.File]::WriteAllText((Join-Path $projectRoot '.env'), $configText)
        Write-Host 'Created local .env with random secrets. Read ADMIN_PASSWORD locally to sign in.'
    }
    docker compose up -d --build --scale spark-worker=2
    if ($LASTEXITCODE -ne 0) { throw 'Docker startup failed' }
} finally { Pop-Location }
