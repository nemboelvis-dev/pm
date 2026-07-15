$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot ".env"

if (-not (Test-Path -LiteralPath $envPath)) {
    Write-Host "Missing .env. Copy .env.example to .env and set OPENROUTER_API_KEY." -ForegroundColor Red
    exit 1
}

docker compose --project-directory $projectRoot up --build --detach
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
