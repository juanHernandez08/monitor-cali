# Mantiene abierto un túnel SSH inverso hacia el VPS (deploy@177.7.60.181) para que el servidor
# en la nube pueda pedirle clasificación de sentimiento a Ollama en ESTA máquina (gratis, sin
# tarjeta) -- decisión del 2026-09-30 mientras se recupera el saldo de la API de Claude.
#
# -R 127.0.0.1:11500:127.0.0.1:11434 : en el VPS, el puerto 11500 (solo loopback, nunca público)
#   reenvía hacia el Ollama de esta PC (127.0.0.1:11434). El .env de producción apunta a
#   OLLAMA_URL=http://127.0.0.1:11500.
#
# Si la conexión se corta (la PC se suspende, se pierde el wifi), este script reintenta solo cada
# 10 segundos -- sin quedar pegado, sin intervención manual.
#
# Instalado como Tarea Programada ("MonitorCaliOllamaTunnel") que arranca sola al iniciar sesión.
# Para verla/quitarla: Get-ScheduledTask MonitorCaliOllamaTunnel / Unregister-ScheduledTask.
# Para ver si está conectado ahora: Get-Process ssh -ErrorAction SilentlyContinue

$key = "$env:USERPROFILE\.ssh\monitor_cali_hostinger"

while ($true) {
    & ssh -N `
        -o ServerAliveInterval=30 `
        -o ServerAliveCountMax=3 `
        -o ExitOnForwardFailure=yes `
        -o StrictHostKeyChecking=accept-new `
        -R 127.0.0.1:11500:127.0.0.1:11434 `
        -i $key `
        deploy@177.7.60.181
    Start-Sleep -Seconds 10
}
