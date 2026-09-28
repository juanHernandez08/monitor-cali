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
  -p 8000:8000 \
  --env-file .env \
  -v /opt/monitor-cali/data:/app/data \
  monitor-cali:latest

echo "== listo, verificando /health =="
sleep 3
curl -sf http://localhost:8000/health && echo || echo "OJO: /health no respondió, revisar 'docker logs monitor-cali'"
