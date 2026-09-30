#!/usr/bin/env bash
# Despliega la última versión en el servidor: trae el código, reconstruye la imagen y reinicia
# el contenedor sin perder la base de datos ni el .env (viven fuera del repo, en /opt/monitor-cali).
# Uso: ./scripts/deploy.sh   (correrlo DENTRO del servidor, en /opt/monitor-cali)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== git pull =="
git pull --ff-only

echo "== docker build =="
docker build -t monitor-cali:latest .

echo "== reiniciar contenedor =="
docker stop monitor-cali 2>/dev/null || true
docker rm monitor-cali 2>/dev/null || true
# La imagen ya no corre como root (usuario 10001, ver Dockerfile): la carpeta de datos debe ser
# suya para que SQLite pueda escribir. Contenedor desechable para no depender de sudo.
docker run --rm -v /opt/monitor-cali/data:/data busybox chown -R 10001:10001 /data

# Función en vez de repetir el comando: hoy mismo pasó DOS veces que una bandera de "docker run"
# (primero -p 127.0.0.1, después --add-host) no se aplicaba a la primera corrida y sí al
# reintentar -- una falla puntual de este Docker/VPS, no del comando. Por eso cada propiedad se
# verifica DESPUÉS de levantar el contenedor y se recrea sola si hace falta, en vez de confiar en
# que "docker run" salió bien porque no tiró error.
start_container() {
  # --add-host: si SENTIMENT_BACKEND=ollama (2026-09-30, saldo de Claude casi agotado -- clasifica
  # la PC del cliente por un túnel SSH inverso, ver scripts/ollama_tunnel.ps1), OLLAMA_URL usa
  # host.docker.internal -- 127.0.0.1 DENTRO del contenedor es su propio loopback, no el del host.
  # El túnel escucha en 172.17.0.1 (el puente de Docker), NO en 127.0.0.1: el contenedor llega por
  # esa interfaz, no por loopback -- son direcciones distintas aunque estén en la misma máquina.
  # También hizo falta abrir el puerto 11500 en ufw SOLO para 172.17.0.0/16 (ver ollama_tunnel.ps1
  # y `sudo ufw status` -- por defecto ufw bloquea todo lo que no sea el 22, sin importar que el
  # tráfico venga de un contenedor propio).
  docker run -d --name monitor-cali \
    --restart unless-stopped \
    -p 127.0.0.1:8000:8000 \
    --add-host=host.docker.internal:host-gateway \
    --env-file .env \
    -v /opt/monitor-cali/data:/app/data \
    monitor-cali:latest
}

start_container
echo "== listo, verificando /healthz =="
sleep 3
curl -sf http://127.0.0.1:8000/healthz && echo || echo "OJO: /healthz no respondió, revisar 'docker logs monitor-cali'"

recreate_if_needed() {
  local check_desc="$1" check_cmd="$2"
  if eval "$check_cmd"; then
    return 0
  fi
  echo "!!! '$check_desc' falló -- recreando el contenedor (falla puntual conocida de este Docker)."
  docker stop monitor-cali && docker rm monitor-cali
  start_container
  sleep 3
  if ! eval "$check_cmd"; then
    echo "!!! SIGUE MAL después de reintentar ('$check_desc'). NO dejar así -- avisar antes de irse."
    exit 1
  fi
  echo "corregido: $check_desc"
}

# Seguridad: el puerto SOLO debe estar publicado en loopback (127.0.0.1), nunca en 0.0.0.0 -- si
# quedara abierto ahí, cualquiera en internet entra sin pasar por Cloudflare Access.
echo "== verificando que el puerto NO esté expuesto públicamente =="
recreate_if_needed "puerto 8000 en 127.0.0.1" \
  '[[ "$(docker port monitor-cali 8000/tcp)" == 127.0.0.1:* ]]'
echo "OK: $(docker port monitor-cali 8000/tcp) (solo local, no accesible desde internet)"

# Si el backend es Ollama (ver arriba), el contenedor debe poder resolver host.docker.internal --
# si no, la clasificación se cae en silencio con "Name or service not known".
if grep -q '^SENTIMENT_BACKEND=ollama' .env 2>/dev/null; then
  echo "== verificando que el contenedor alcance el Ollama de la PC (host.docker.internal) =="
  recreate_if_needed "resolución de host.docker.internal" \
    'docker exec monitor-cali getent hosts host.docker.internal >/dev/null 2>&1'
  echo "OK: host.docker.internal resuelve dentro del contenedor"
fi
