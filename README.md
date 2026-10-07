# Monitor de menciones — Alcaldía de Cali 2027

Bot que captura menciones de los candidatos a la Alcaldía de Cali (incluido Carlos Arias) en prensa, Reddit, YouTube e Instagram/Facebook/X, las clasifica por sentimiento y las muestra en un dashboard web.

## Fuentes

| Fuente | Cómo | Credencial |
|---|---|---|
| Prensa | Google News RSS por candidato + feeds directos (El País, El Tiempo, Caracol, Q'hubo, Caliescribe, 90 Minutos, Semana) | ninguna |
| Reddit | Búsqueda pública vía RSS | ninguna |
| Instagram / Facebook (cuentas conocidas) | Bright Data Web Scraper API: posts recientes + comentarios de las cuentas en `SOCIAL_ACCOUNTS` | `BRIGHTDATA_API_TOKEN` (5.000 registros/mes gratis) |
| IG / FB / X (búsqueda) | Índice de Google con `site:` — **Custom Search JSON API cerrada a clientes nuevos**; el conector queda para Serper/SerpApi | pendiente |
| YouTube | YouTube Data API v3: videos + comentarios | `GOOGLE_API_KEY` (gratis) |
| Sentimiento | Ollama local (`qwen2.5:14b`) o Claude Sonnet 5 | Ollama: ninguna · Claude: `ANTHROPIC_API_KEY` |

Las fuentes sin credencial simplemente se omiten; al poner la key en `.env` se activan.

## Instalación

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env      # y completar las keys que tengas
```

Ollama: instalar desde ollama.com y `ollama pull qwen2.5:14b`.

## Instalación en macOS

```bash
bash scripts/setup_mac.sh     # Homebrew → Python 3.11, Ollama, cloudflared, venv, modelo, tests
bash scripts/demo.sh          # Ollama + servidor + tunnel público; Ctrl+C termina todo
```

Para llevar el proyecto de Windows a Mac: copiar la carpeta **sin** `.venv/` (se recrea) y **con** `monitor.db` (los datos ya capturados) y `.env`. En Macs con 16 GB o menos, poner `OLLAMA_MODEL=llama3.1:8b` en `.env` antes de correr el setup.

## Uso

```powershell
# Ingesta + clasificación una vez (útil para llenar la base la primera vez)
.\.venv\Scripts\python -m scripts.run_once

# Servidor con scheduler (ingesta cada 15 min, clasificación cada 2 min)
.\.venv\Scripts\python -m uvicorn src.api:app --port 8000
# → http://localhost:8000

# Demo con URL pública (levanta Ollama + servidor + tunnel)
.\scripts\demo.ps1
```

Rutas JSON: `/api/summary`, `/api/timeline`, `/api/mentions`, `/api/alerts`, `/api/topics`, `/health`, `POST /api/refresh`.

## Estructura

```
src/
  models.py        Candidate, Source, Mention, SentimentScore, Run, ApiUsage
  config.py        candidatos (con alias), feeds RSS, variables de entorno
  matching.py      atribución de una mención a un candidato (nombre/alias)
  connectors/      google_news, news_rss, reddit_rss, google_cse, youtube (+ reddit/serp vía Bright Data)
  pipeline.py      ingest() guarda sin score y deduplica por URL; score_pending() clasifica en lotes
  sentiment.py     OllamaSentimentEngine / SentimentEngine (Claude) / build_sentiment_engine()
  scheduler.py     APScheduler: qué fuente corre cuándo
  queries.py       consultas del dashboard
  api.py           FastAPI; sirve el tablero compilado (static/app) y, de respaldo, el anterior (templates/, /legacy)
frontend/          tablero React + Tailwind (Vite); `npm run build` lo compila a src/static/app
scripts/           seed_sources.py, run_once.py, demo.ps1
docs/              presupuesto.md, despliegue.md, specs y planes
```

## Tablero (frontend)

Está en `frontend/` (React 18 + Tailwind 4 + ApexCharts, con Vite). El Dockerfile lo compila solo
(etapa Node); para verlo en local:

```powershell
cd frontend; npm install; npm run build   # genera src/static/app (no se versiona)
.\.venv\Scripts\python -m uvicorn src.api:app --port 8000   # y abrir http://localhost:8000
```

Para desarrollar con recarga en caliente: `npm run dev` (puerto 5173; reenvía /api al 8000).
Si `src/static/app` no existe, `/` cae al tablero anterior; ese sigue disponible en `/legacy`.

## Tests

```powershell
.\.venv\Scripts\python -m pytest -q
```

## Limitaciones conocidas

- Instagram/Facebook: se leen solo las cuentas listadas en `SOCIAL_ACCOUNTS` (candidatos y medios); no hay búsqueda abierta por palabra clave. Cada registro consume 1 crédito de Bright Data (~800 por corrida); el scheduler corre cada 5 días.
- Nombres comunes ("Carlos Arias", "Carlos Paz") traen homónimos; el clasificador recibe el nombre del candidato y suele marcarlos como neutrales, pero cuentan como mención. Ajustar alias en `config.py`.
- Reddit limita la tasa (429); el conector se detiene y reintenta en el siguiente ciclo.
- Las notas de Google News se enriquecen con el cuerpo del artículo antes de clasificar (`src/enrich.py`); si el medio bloquea la descarga, se clasifica solo con el titular.
- Radio/TV no está cubierto (ver `docs/presupuesto.md`).
