#!/usr/bin/env bash
# Instalación en macOS. Uso: bash scripts/setup_mac.sh
# Requiere Homebrew (https://brew.sh). Instala Python 3.11, Ollama, cloudflared y las dependencias.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v brew >/dev/null; then
  echo "Falta Homebrew. Instálalo desde https://brew.sh y vuelve a correr este script."; exit 1
fi

command -v python3.11 >/dev/null || brew install python@3.11
command -v ollama >/dev/null || brew install ollama
command -v cloudflared >/dev/null || brew install cloudflared

[ -d .venv ] || python3.11 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

[ -f .env ] || cp .env.example .env

# Modelo de sentimiento según la RAM del Mac (se escribe en .env si no está definido):
#   <= 8 GB → qwen2.5:7b (4,7 GB) · <= 16 GB → llama3.1:8b · más → qwen2.5:14b
RAM_GB=$(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 ))
if [ "$RAM_GB" -le 8 ]; then DEFAULT_MODEL="qwen2.5:7b"
elif [ "$RAM_GB" -le 16 ]; then DEFAULT_MODEL="llama3.1:8b"
else DEFAULT_MODEL="qwen2.5:14b"; fi
MODEL="$(grep -E '^OLLAMA_MODEL=' .env | cut -d= -f2)"
# Si el .env viene de otro equipo con un modelo que no cabe en esta RAM, se reemplaza.
if [ -z "$MODEL" ] || { [ "$RAM_GB" -le 8 ] && echo "$MODEL" | grep -qE '14b|32b|70b'; } || { [ "$RAM_GB" -le 16 ] && echo "$MODEL" | grep -qE '32b|70b'; }; then
  MODEL="$DEFAULT_MODEL"
  if grep -q '^OLLAMA_MODEL=' .env; then sed -i '' "s|^OLLAMA_MODEL=.*|OLLAMA_MODEL=$MODEL|" .env; else echo "OLLAMA_MODEL=$MODEL" >> .env; fi
fi
echo "RAM: ${RAM_GB} GB → modelo de sentimiento: $MODEL"
pgrep -x ollama >/dev/null || (ollama serve >/dev/null 2>&1 &) ; sleep 3
ollama list | grep -q "^${MODEL}" || ollama pull "$MODEL"

.venv/bin/python -m pytest -q
echo
echo "Listo. Para la demo: bash scripts/demo.sh"
