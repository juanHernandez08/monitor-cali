# Empaqueta el proyecto para llevarlo a otro equipo (Mac): todo menos .venv y cachés,
# incluyendo monitor.db (datos capturados) y .env (claves). Uso: .\scripts\pack_for_mac.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$stage = Join-Path $env:TEMP "monitor-cali"
$zip = Join-Path ([Environment]::GetFolderPath("Desktop")) "monitor-cali.zip"
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
robocopy $root $stage /E /XD .venv .git __pycache__ .pytest_cache .claude /XF "*.pyc" | Out-Null
if (Test-Path $zip) { Remove-Item -Force $zip }
# tar (bsdtar, incluido en Windows 10+) escribe rutas con "/" — Compress-Archive usa "\" y macOS
# descomprime archivos con nombres como "scripts\demo.sh" en vez de carpetas.
tar -a -cf $zip -C $stage .
Remove-Item -Recurse -Force $stage
Write-Host "Listo: $zip"
Write-Host "Contiene monitor.db y .env (claves): compártelo solo por un canal privado (AirDrop, USB, Drive privado)."
