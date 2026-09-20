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

# Modelo de sentimiento (cámbialo en .env con OLLAMA_MODEL; llama3.1:8b si el Mac tiene <=16 GB de RAM)
MODEL="$(grep -E '^OLLAMA_MODEL=' .env | cut -d= -f2)"; MODEL="${MODEL:-qwen2.5:14b}"
pgrep -x ollama >/dev/null || (ollama serve >/dev/null 2>&1 &) ; sleep 3
ollama list | grep -q "^${MODEL}" || ollama pull "$MODEL"

.venv/bin/python -m pytest -q
echo
echo "Listo. Para la demo: bash scripts/demo.sh"
