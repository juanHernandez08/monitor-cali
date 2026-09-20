# Levanta Ollama, el servidor y un tunnel público. Uso: .\scripts\demo.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Get-Process ollama -ErrorAction SilentlyContinue)) {
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep 3
}
Write-Host "Precalentando el modelo de sentimiento..."
& ollama run qwen2.5:14b "hola" | Out-Null

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    winget install --id Cloudflare.cloudflared -e --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}

Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn src.api:app --host 0.0.0.0 --port 8000" -WindowStyle Minimized
Start-Sleep 4
Write-Host ""
Write-Host "Servidor local: http://localhost:8000"
Write-Host "Abriendo tunnel publico... copia la URL https://*.trycloudflare.com que aparece abajo:"
Write-Host ""
cloudflared tunnel --url http://localhost:8000
