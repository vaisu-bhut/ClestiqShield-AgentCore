# PowerShell script to run tests in Docker container

Write-Host "Building test environment..." -ForegroundColor Cyan
docker-compose -f docker-compose.test.yml build

Write-Host "`nRunning all tests..." -ForegroundColor Cyan
docker-compose -f docker-compose.test.yml run --rm test

Write-Host "`nTest execution complete!" -ForegroundColor Green
Write-Host "Coverage report available at: htmlcov/index.html" -ForegroundColor Yellow

# Cleanup
Write-Host "`nCleaning up test containers..." -ForegroundColor Cyan
docker-compose -f docker-compose.test.yml down -v
