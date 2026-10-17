# Keeps a Cloudflare quick tunnel alive for the demo laptop and re-points the server's PUBLIC_URL
# when Cloudflare hands out a new address (quick tunnels get revoked after a while).
#   .\deploy\tunnel-watchdog.ps1            (run from the repo root; Ctrl+C to stop)
# Writes the current public URL to data\public_url.txt. The server is restarted in low-memory mode
# with PUBLIC_URL set, so the QR code on /tree always shows a working address.
param(
  [int]$CheckSeconds = 45,
  [int]$FailuresBeforeRestart = 2
)
$ErrorActionPreference = "Continue"
$cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cf) { $cf = "C:\Program Files (x86)\cloudflared\cloudflared.exe" }
$py = ".\.venv\Scripts\python.exe"
New-Item -ItemType Directory -Force .\data | Out-Null
$urlFile = ".\data\public_url.txt"

function Start-Tunnel {
  Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
  Start-Sleep -Seconds 2
  $log = Join-Path (Resolve-Path .\data) ("cloudflared-" + (Get-Date -Format "HHmmss") + ".log")
  Start-Process -FilePath $cf -ArgumentList "tunnel", "--url", "http://localhost:8010" -RedirectStandardError $log -WindowStyle Hidden
  for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $log) {
      $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1
      if ($m) { return $m.Matches.Value }
    }
  }
  return $null
}

function Start-Server([string]$publicUrl) {
  Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Seconds 2
  $env:USE_CLIP = "false"
  $env:PUBLIC_URL = $publicUrl
  Start-Process -FilePath $py -ArgumentList "-m", "uvicorn", "app:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8010", "--log-level", "warning" -WindowStyle Hidden
}

function Test-Url([string]$u) {
  try { $r = Invoke-WebRequest -UseBasicParsing -Uri "$u/api/health" -TimeoutSec 20; return $r.StatusCode -eq 200 } catch { return $false }
}

$url = Start-Tunnel
if (-not $url) { Write-Host "tunnel did not start"; exit 1 }
Set-Content $urlFile $url
Start-Server $url
Write-Host "$(Get-Date -Format HH:mm:ss) public URL: $url"
$fails = 0
while ($true) {
  Start-Sleep -Seconds $CheckSeconds
  if (Test-Url $url) { $fails = 0; continue }
  $fails++
  Write-Host "$(Get-Date -Format HH:mm:ss) tunnel check failed ($fails)"
  if ($fails -ge $FailuresBeforeRestart) {
    $new = Start-Tunnel
    if ($new) {
      $url = $new
      Set-Content $urlFile $url
      Start-Server $url
      Write-Host "$(Get-Date -Format HH:mm:ss) new public URL: $url"
    }
    $fails = 0
  }
}
