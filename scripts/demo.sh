#!/usr/bin/env bash
# Demo en macOS: Ollama + servidor + tunnel público, y evita que el Mac se duerma.
# Uso: bash scripts/demo.sh   (Ctrl+C para terminar todo)
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL="$(grep -E '^OLLAMA_MODEL=' .env 2>/dev/null | cut -d= -f2)"; MODEL="${MODEL:-qwen2.5:14b}"

pgrep -x ollama >/dev/null || (ollama serve >/dev/null 2>&1 &) ; sleep 3
echo "Precalentando el modelo de sentimiento ($MODEL)..."
ollama run "$MODEL" "hola" >/dev/null

caffeinate -dims &            # el Mac no se duerme mientras corra la demo
CAFF=$!
.venv/bin/python -m uvicorn src.api:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
SERVER=$!
trap 'kill $SERVER $CAFF 2>/dev/null' EXIT
sleep 4

echo
echo "Servidor local: http://localhost:8000   (log: server.log)"
echo "Abriendo tunnel público... copia la URL https://*.trycloudflare.com que aparece abajo:"
echo
cloudflared tunnel --url http://localhost:8000
