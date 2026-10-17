# One-click local start for Lineage (Windows PowerShell). Run from the repo root:  .\start.ps1
# Seeds the demo pool if it is empty, then serves API + built frontend on http://localhost:8010
$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Host "No .venv found. See README 'Run it'."; exit 1 }
if (-not (Test-Path ".\frontend\dist\index.html")) {
  Write-Host "Building frontend..."; npm --prefix .\frontend run build | Out-Null
}
if (-not (Test-Path ".\data\seeds")) { & $py backend\scripts\fetch_seeds.py }
if (-not (Test-Path ".\data\lineage.sqlite")) { & $py backend\scripts\seed_pool.py --families 3 --chains 2 }
Write-Host "Lineage: http://localhost:8010  (tablet /edit, big screen /tree, audit /audit)"
& $py -m uvicorn app:app --app-dir backend --host 0.0.0.0 --port 8010
