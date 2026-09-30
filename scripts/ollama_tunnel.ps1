# Mantiene abierto un túnel SSH inverso hacia el VPS (deploy@177.7.60.181) para que el servidor
# en la nube pueda pedirle clasificación de sentimiento a Ollama en ESTA máquina (gratis, sin
# tarjeta) -- decisión del 2026-09-30 mientras se recupera el saldo de la API de Claude.
#
# -R 172.17.0.1:11500:127.0.0.1:11434 : el contenedor Docker del VPS NO alcanza 127.0.0.1 del
#   host (127.0.0.1 DENTRO del contenedor es su propio loopback) -- lo alcanza por la IP del
#   puente de Docker, 172.17.0.1 (host.docker.internal). Por eso el túnel escucha ahí, NO en
#   127.0.0.1 ni en 0.0.0.0: 172.17.0.1 solo es alcanzable desde el propio servidor y sus
#   contenedores, nunca desde internet (verificado). Requirió GatewayPorts clientspecified en
#   sshd_config del servidor (por defecto solo deja bindear a loopback). El .env de producción
#   apunta a OLLAMA_URL=http://host.docker.internal:11500.
#
# Si la conexión se corta (la PC se suspende, se pierde el wifi), este script reintenta solo cada
# 10 segundos -- sin quedar pegado, sin intervención manual.
#
# Instalado como Tarea Programada ("MonitorCaliOllamaTunnel") con DOS disparadores: al iniciar
# sesión, y un vigilante cada 5 minutos que la vuelve a lanzar si no está corriendo (un corte de
# luz real el 2026-09-30 mató el proceso y el disparador de "inicio de sesión" no se reactivó
# solo -- quedó 7 menciones sin clasificar hasta que alguien lo notó a mano; con el vigilante ya
# no hace falta notarlo).
# Para verla/quitarla: Get-ScheduledTask MonitorCaliOllamaTunnel / Unregister-ScheduledTask.
# Para ver si está conectado ahora: Get-Process ssh -ErrorAction SilentlyContinue

$key = "$env:USERPROFILE\.ssh\monitor_cali_hostinger"

while ($true) {
    & ssh -N `
        -o ServerAliveInterval=30 `
        -o ServerAliveCountMax=3 `
        -o ExitOnForwardFailure=yes `
        -o StrictHostKeyChecking=accept-new `
        -R 172.17.0.1:11500:127.0.0.1:11434 `
        -i $key `
        deploy@177.7.60.181
    Start-Sleep -Seconds 10
}
