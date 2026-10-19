$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    docker compose run --rm test-backend
    if ($LASTEXITCODE -ne 0) { throw 'Backend checks failed' }
    docker compose exec etl-worker python scripts/smoke_spark.py
    if ($LASTEXITCODE -ne 0) { throw 'Distributed Spark check failed' }
    npm.cmd --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
    $readyState = Invoke-RestMethod http://localhost:8080/api/v1/health/ready
    if ($readyState.status -ne 'ready') { throw 'Frontend proxy readiness failed' }
} finally { Pop-Location }
