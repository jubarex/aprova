# Sobe API (com worker embutido) e frontend. Ctrl+C encerra os dois.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$api = Start-Process -PassThru -NoNewWindow -WorkingDirectory "$root\backend" -FilePath uv `
  -ArgumentList 'run', 'uvicorn', 'app.api.main:get_app', '--factory', '--host', '127.0.0.1', '--port', '8000'
$web = Start-Process -PassThru -NoNewWindow -WorkingDirectory "$root\frontend" -FilePath npm.cmd -ArgumentList 'run', 'dev'
Write-Host 'API http://127.0.0.1:8000  |  App http://127.0.0.1:5173  (Ctrl+C para encerrar)'
try { Wait-Process -Id $api.Id, $web.Id -ErrorAction SilentlyContinue; while (-not $api.HasExited -and -not $web.HasExited) { Start-Sleep 1 } }
finally {
  foreach ($p in @($api, $web)) { if ($p -and -not $p.HasExited) { & taskkill /PID $p.Id /T /F | Out-Null } }
}
