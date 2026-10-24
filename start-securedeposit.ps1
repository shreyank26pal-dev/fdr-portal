# SecureDeposit — AICTE Security Deposit & FDR Lifecycle Portal (SIH26265)
# One-Click Local Launcher for Windows PowerShell

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " SecureDeposit | AICTE Security Deposit & FDR Portal (SIH26265)  " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Ensure database is seeded if empty
Write-Host "[1/3] Checking & seeding local SQLite database if empty..." -ForegroundColor Yellow
Push-Location "$Root\backend"
& ".\.venv\Scripts\python.exe" -m scripts.seed --if-empty
Pop-Location

# 2. Launch FastAPI Backend on http://127.0.0.1:8000
Write-Host "[2/3] Starting FastAPI Backend on http://127.0.0.1:8000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\backend'; .\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000"

# 3. Launch Vite React Frontend on http://localhost:5173
Write-Host "[3/3] Starting Vite Frontend on http://localhost:5173 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\frontend'; npm run dev"

Write-Host ""
Write-Host "Portal Live URLs:" -ForegroundColor Cyan
Write-Host "  -> Frontend Portal : http://localhost:5173" -ForegroundColor White
Write-Host "  -> Backend Swagger : http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "  -> Health Endpoint : http://127.0.0.1:8000/health" -ForegroundColor White
