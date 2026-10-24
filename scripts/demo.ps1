# Sobe a demonstração pronta para apresentar: API (com worker) + app, já com dados de exemplo, e abre o navegador.
#   .\scripts\demo.ps1            sobe e popula (se estiver vazio)
#   .\scripts\demo.ps1 -Reset     apaga o progresso e popula de novo (estado conhecido)
param([switch]$Reset)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

# encerra instâncias anteriores desta demo (ignora o servidor de E2E, porta 8100)
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -match 'uvicorn|vite' -and $_.Name -match 'python|node' -and $_.CommandLine -notmatch '8100|5174'
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep 1
if ($Reset) { Remove-Item -Recurse -Force "$root\backend\var" -ErrorAction SilentlyContinue }

Start-Process -WindowStyle Hidden -WorkingDirectory "$root\backend" -FilePath uv `
  -ArgumentList 'run', 'uvicorn', 'app.api.main:get_app', '--factory', '--host', '127.0.0.1', '--port', '8000'
Start-Process -WindowStyle Hidden -WorkingDirectory "$root\frontend" -FilePath npm.cmd -ArgumentList 'run', 'dev'

for ($i = 0; $i -lt 40; $i++) {
  try { if ((Invoke-WebRequest http://127.0.0.1:8000/api/health -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200) { break } } catch { Start-Sleep 1 }
}
$s = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/demo/session -ContentType 'application/json' -Body '{"actor_id":"act_rui"}'
$r = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/demo/populate -Headers @{ 'X-Demo-Token' = $s.token }
if ($r.skipped) { Write-Host 'Dados de exemplo já presentes.' } else { Write-Host 'Dados de exemplo criados.' }
Start-Sleep 2
Start-Process 'http://127.0.0.1:5173/'
Write-Host 'Demo no ar: http://127.0.0.1:5173  (API :8000). Entre como "Rui Prado (implantador)".'
