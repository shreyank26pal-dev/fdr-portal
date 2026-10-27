# SecureDeposit — AICTE Security Deposit & FDR Lifecycle Portal (SIH26265)
# One-Click Local Launcher for Windows PowerShell

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " SecureDeposit | AICTE Security Deposit & FDR Portal (SIH26265)  " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Determine Python executable (virtualenv or system python)
$PythonCmd = "python"
if (Test-Path "$Root\backend\.venv\Scripts\python.exe") {
    $PythonCmd = "$Root\backend\.venv\Scripts\python.exe"
}

# 2. Ensure backend .env exists with SQLite defaults
if (-not (Test-Path "$Root\backend\.env")) {
    Write-Host "[1/3] Initializing backend .env for local SQLite..." -ForegroundColor Yellow
    @"
DATABASE_URL=sqlite:///./fdr_portal.db
JWT_SECRET=dev-only-secret-change-me-0123456789abcdef
STORAGE_DIR=./storage
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173
FRONTEND_BASE_URL=http://localhost:5173
PUBLIC_BASE_URL=http://localhost:8000
SMTP_HOST=
MOCK_BANK_API_KEY=sandbox-bank-key
ENABLE_SCHEDULER=true
DEMO_MODE=true
"@ | Out-File -FilePath "$Root\backend\.env" -Encoding utf8
}

# 3. Seed database if empty
Write-Host "[2/3] Checking & seeding local SQLite database if empty..." -ForegroundColor Yellow
Push-Location "$Root\backend"
& $PythonCmd -m scripts.seed --if-empty
Pop-Location

# 4. Launch FastAPI Backend on http://127.0.0.1:8000
Write-Host "[3/3] Starting FastAPI Backend on http://127.0.0.1:8000 ..." -ForegroundColor Green
$BackendCmd = "cd '$Root\backend'; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
if (Test-Path "$Root\backend\.venv\Scripts\uvicorn.exe") {
    $BackendCmd = "cd '$Root\backend'; .\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload"
}
Start-Process powershell -ArgumentList "-NoExit", "-Command", $BackendCmd

# 5. Launch Vite React Frontend on http://localhost:5173 using npm.cmd to bypass script execution policies
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\frontend'; npm.cmd run dev"

Write-Host ""
Write-Host "Portal Live URLs:" -ForegroundColor Cyan
Write-Host "  -> Frontend Portal : http://localhost:5173" -ForegroundColor White
Write-Host "  -> Backend Swagger : http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "  -> Health Endpoint : http://127.0.0.1:8000/health" -ForegroundColor White
Write-Host ""
Write-Host "Demo Credentials for Testing:" -ForegroundColor Yellow
Write-Host "  -> Scrutiny Officer : officer@aicte-demo.in  / Password@123" -ForegroundColor Gray
Write-Host "  -> College 1        : college1@aicte-demo.in / Password@123" -ForegroundColor Gray
Write-Host "  -> Approver         : approver@aicte-demo.in / Password@123" -ForegroundColor Gray
Write-Host "=================================================================" -ForegroundColor Cyan
