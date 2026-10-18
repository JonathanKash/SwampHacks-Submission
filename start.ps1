# One-click local start for Lineage (Windows PowerShell). Run from the repo root:
#   .\start.ps1                       serve API + built frontend on http://localhost:8010
#   .\start.ps1 -LowMemory            pHash-only candidates (no CLIP), for small laptops
#   .\start.ps1 -Tunnel               also open a Cloudflare quick tunnel and advertise its URL (QR code)
#   .\start.ps1 -PublicUrl https://lineage.example.com   advertise a fixed public URL (named tunnel / VM)
param(
  [switch]$LowMemory,
  [switch]$Tunnel,
  [string]$PublicUrl = ""
)
$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Host "No .venv found. See README 'Run it'."; exit 1 }
if (-not (Test-Path ".\frontend\dist\index.html")) {
  Write-Host "Building frontend..."; npm --prefix .\frontend run build | Out-Null
}
if (-not (Test-Path ".\data\seeds")) { & $py backend\scripts\fetch_seeds.py }
if (-not (Test-Path ".\data\lineage.sqlite")) { & $py backend\scripts\seed_pool.py --families 3 --chains 2 }
if ($LowMemory) { $env:USE_CLIP = "false" }

if ($Tunnel -and -not $PublicUrl) {
  # Quick tunnel: no account needed; the URL changes on every start, so we read it from the log.
  $cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
  if (-not $cf) { $cf = "C:\Program Files (x86)\cloudflared\cloudflared.exe" }
  if (-not (Test-Path $cf)) { Write-Host "cloudflared not found: winget install --id Cloudflare.cloudflared"; exit 1 }
  New-Item -ItemType Directory -Force .\data | Out-Null
  $log = Join-Path (Resolve-Path .\data) "cloudflared.log"
  if (Test-Path $log) { Remove-Item $log -Force }
  Start-Process -FilePath $cf -ArgumentList "tunnel", "--url", "http://localhost:8010" -RedirectStandardError $log -WindowStyle Hidden
  for ($i = 0; $i -lt 30 -and -not $PublicUrl; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $log) {
      $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1
      if ($m) { $PublicUrl = $m.Matches.Value }
    }
  }
  if (-not $PublicUrl) { Write-Host "Tunnel did not report a URL within 30 s; see $log" } else { Write-Host "Public URL: $PublicUrl" }
}
if ($PublicUrl) { $env:PUBLIC_URL = $PublicUrl }
# On a public link anyone can press "Remove" or delete an audit case unless ADMIN_TOKEN is set in .env
# (the UI asks for the token once on a 403). The Identify knowledge base is refused regardless.
$hasAdmin = $env:ADMIN_TOKEN -or ((Test-Path .env) -and (Select-String -Path .env -Pattern '^ADMIN_TOKEN=.+' -Quiet))
if ($PublicUrl -and -not $hasAdmin) { Write-Host "WARNING: ADMIN_TOKEN is not set; visitors on $PublicUrl can remove images and audit cases. Add ADMIN_TOKEN=<secret> to .env." }

Write-Host "Lineage: http://localhost:8010  (tablet /edit, big screen /tree, audit /audit, identify /identify)"
& $py -m uvicorn app:app --app-dir backend --host 0.0.0.0 --port 8010
