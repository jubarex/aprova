# Verificação local: testes do backend + typecheck/build do frontend. Saída não zero em falha.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location "$root\backend"; try { uv run pytest -q; if ($LASTEXITCODE) { exit $LASTEXITCODE } } finally { Pop-Location }
Push-Location "$root\frontend"; try { npm run build; if ($LASTEXITCODE) { exit $LASTEXITCODE } } finally { Pop-Location }
Write-Host 'verify: OK'
