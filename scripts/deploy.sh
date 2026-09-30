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
docker run -d --name monitor-cali \
  --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  --env-file .env \
  -v /opt/monitor-cali/data:/app/data \
  monitor-cali:latest

echo "== listo, verificando /health =="
sleep 3
curl -sf http://localhost:8000/health && echo || echo "OJO: /health no respondió, revisar 'docker logs monitor-cali'"

# Verificación de seguridad: el puerto SOLO debe estar publicado en loopback (127.0.0.1), nunca
# en 0.0.0.0 -- si quedara abierto ahí, cualquiera en internet entra sin pasar por Cloudflare
# Access (pasó una vez, 2026-09-30: el mismo comando con la misma bandera -p 127.0.0.1:8000:8000
# publicó en 0.0.0.0 por una falla puntual de Docker; se corrigió recreando el contenedor, pero no
# hay que confiar en que no vuelva a pasar -- por eso esta verificación falla el despliegue en vez
# de quedar en silencio).
echo "== verificando que el puerto NO esté expuesto públicamente =="
BINDING=$(docker port monitor-cali 8000/tcp)
if [[ "$BINDING" != 127.0.0.1:* ]]; then
  echo "!!! CRÍTICO: el puerto 8000 quedó publicado en '$BINDING', NO en 127.0.0.1 -- esto salta"
  echo "!!! Cloudflare Access por completo. Corrigiendo ahora: recreando el contenedor."
  docker stop monitor-cali && docker rm monitor-cali
  docker run -d --name monitor-cali \
    --restart unless-stopped \
    -p 127.0.0.1:8000:8000 \
    --env-file .env \
    -v /opt/monitor-cali/data:/app/data \
    monitor-cali:latest
  sleep 3
  BINDING=$(docker port monitor-cali 8000/tcp)
  if [[ "$BINDING" != 127.0.0.1:* ]]; then
    echo "!!! SIGUE MAL después de reintentar: '$BINDING'. NO dejar así -- avisar antes de irse."
    exit 1
  fi
  echo "corregido: $BINDING"
else
  echo "OK: $BINDING (solo local, no accesible desde internet)"
fi
