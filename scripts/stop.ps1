$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot

docker compose --project-directory $projectRoot down
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
