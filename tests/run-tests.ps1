# PowerShell script to run tests in Docker container
$ScriptDir = Split-Path $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $ScriptDir "docker-compose.yml"

Write-Host "Building test environment..." -ForegroundColor Cyan
docker compose -f $ComposeFile build

Write-Host "`nRunning all tests..." -ForegroundColor Cyan
docker compose -f $ComposeFile run --rm test

Write-Host "`nTest execution complete!" -ForegroundColor Green
Write-Host "Coverage report available at: htmlcov/index.html" -ForegroundColor Yellow

# Cleanup
Write-Host "`nCleaning up test containers..." -ForegroundColor Cyan
docker compose -f $ComposeFile down -v
