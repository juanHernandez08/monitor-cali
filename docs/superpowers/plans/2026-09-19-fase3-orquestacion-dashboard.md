# Fase 3 — Orquestación + Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capturar menciones reales de los 9 candidatos desde Google News, feeds RSS, Reddit RSS, Google CSE (IG/FB/X) y YouTube; clasificarlas con Ollama (o Claude si hay key); mostrarlas en un dashboard FastAPI con URL pública vía cloudflared — demo lunes 2026-09-21.

**Architecture:** Los conectores nuevos implementan el `Connector` existente y devuelven `RawItem` (ahora con `search_term` para atribuir comentarios de YouTube a un candidato). El pipeline se parte en `ingest` (guarda sin score, dedup por URL normalizada, registra `Run`) y `score_pending` (clasifica en lotes). Un proceso FastAPI corre APScheduler + rutas JSON + una página Jinja2/Chart.js. Spec: `docs/superpowers/specs/2026-09-19-fase3-orquestacion-dashboard-design.md`.

**Tech Stack:** Python 3.11, SQLAlchemy 2, feedparser, requests, FastAPI, uvicorn, Jinja2, APScheduler 3, python-dotenv, Chart.js (CDN), Ollama (qwen2.5:14b), cloudflared.

---

## Estructura de archivos

```
src/
├── models.py            MOD  SourceType +GOOGLE_NEWS/YOUTUBE/GOOGLE_CSE; Mention.url_normalized; Run; ApiUsage
├── urlnorm.py           NEW  normalize_url()
├── config.py            MOD  load_dotenv, GOOGLE_*, OLLAMA_*, SENTIMENT_BACKEND, CSE_SITES, RSS_SOURCES verificados
├── sentiment.py         MOD  OllamaSentimentEngine + build_sentiment_engine(); score(text, candidate=None)
├── pipeline.py          MOD  ingest() / score_pending() / run_pipeline() como wrapper
├── matching.py          MOD  find_candidate_by_term()
├── queries.py           NEW  summary / timeline / mentions / alerts / topics / status
├── scheduler.py         NEW  build_connector(source, session), run_group(), jobs, start_scheduler()
├── api.py               NEW  create_app(session_factory, start_jobs) + rutas
├── templates/dashboard.html   NEW
├── static/dashboard.js        NEW
├── static/dashboard.css       NEW
└── connectors/
    ├── base.py          MOD  RawItem.search_term
    ├── google_news.py   NEW  GoogleNewsConnector, build_query_url
    ├── reddit_rss.py    NEW  RedditRSSConnector, build_search_url, _download
    ├── google_cse.py    NEW  GoogleCSEConnector, QuotaTracker
    └── youtube.py       NEW  YouTubeConnector
scripts/
├── seed_sources.py      MOD  EXTRA_SOURCES (Google News, Reddit, CSE, YouTube)
├── run_once.py          NEW  ingesta + scoring manual
└── demo.ps1             NEW  levanta Ollama + uvicorn + cloudflared
docs/presupuesto.md, docs/despliegue.md, README.md, Dockerfile, .env.example
tests/ test_urlnorm.py test_google_news.py test_reddit_rss.py test_google_cse.py test_youtube.py
       test_sentiment_ollama.py test_pipeline_v2.py test_queries.py test_api.py test_scheduler.py
```

`requirements.txt` añade: `requests>=2.31`, `fastapi>=0.115`, `uvicorn[standard]>=0.30`, `jinja2>=3.1`, `apscheduler>=3.10,<4`, `httpx>=0.27`, `python-dotenv>=1.0`.

Cada task: escribir test → correr y ver FAIL → implementar → correr y ver PASS → commit.

---

### Task 1: Modelos + normalize_url
Files: `src/models.py`, `src/urlnorm.py`, `tests/test_urlnorm.py`, `tests/test_models.py`

- `normalize_url(url)`: sin esquema, sin `www.`, sin `utm_*`/`fbclid`/`igshid`/`gclid`/`ref`, sin barra final, host y path en minúsculas; `None`/`""` → `None`. Casos de prueba: `https://www.ElPais.com.co/cali/nota-1/?utm_source=x&fbclid=abc` → `elpais.com.co/cali/nota-1`; `https://youtube.com/watch?v=abc&igshid=1` → `youtube.com/watch?v=abc`.
- `SourceType` += `GOOGLE_NEWS`, `YOUTUBE`, `GOOGLE_CSE`. `Mention.url_normalized` (String, index). `Run(source_id, started_at, finished_at, new_mentions, error)`. `ApiUsage(service, day, count)` con unique `(service, day)`.
- Commit: `feat: url_normalized, Run, ApiUsage y nuevos SourceType`

### Task 2: RawItem.search_term + GoogleNewsConnector
Files: `src/connectors/base.py`, `src/connectors/google_news.py`, `tests/test_google_news.py`

- `RawItem.search_term: str | None = None`.
- `build_query_url(term)` → `https://news.google.com/rss/search?q="term"&hl=es-419&gl=CO&ceid=CO:es-419`.
- `GoogleNewsConnector(pause_seconds=1.0).fetch(terms)`: por término, `feedparser.parse(url)`; `external_id = entry.id or link`; texto = título + summary sin HTML (`html.unescape` + regex de tags); `author = entry.source.title`; dedup dentro del batch; `search_term=term`; `time.sleep(pause)` entre términos.
- Test con feed de muestra parcheando `feedparser.parse` (capturar `real = feedparser.parse` antes).
- Commit: `feat: conector Google News RSS`

### Task 3: RedditRSSConnector
Files: `src/connectors/reddit_rss.py`, `tests/test_reddit_rss.py`

- `build_search_url(term)` → `https://www.reddit.com/search.rss?q="term"&sort=new`.
- `_download(url) -> bytes` con `User-Agent` de navegador (Reddit devuelve 403 sin él), timeout 15.
- `RedditRSSConnector(pause_seconds=2.0).fetch(terms)`: `feedparser.parse(_download(url))`; Atom → `entry.id`, `entry.link`, `entry.author`, `entry.updated_parsed`, `entry.summary` (HTML → texto).
- Test parchea `_download` con un Atom de muestra.
- Commit: `feat: conector Reddit RSS`

### Task 4: GoogleCSEConnector + QuotaTracker
Files: `src/connectors/google_cse.py`, `tests/test_google_cse.py`

- `QuotaTracker(session, service, daily_limit, today=None)`: fila `ApiUsage` por día; `remaining()`, `consume(n)` (commit).
- `GoogleCSEConnector(api_key, cse_id, sites, quota, pause_seconds=1.0, num=10).fetch(terms)`: por término × sitio, si `quota.remaining() <= 0` retorna lo acumulado; `requests.get("https://www.googleapis.com/customsearch/v1", params={key, cx, q: f'"{term}" site:{site}', num, gl: "co", hl: "es"}, timeout=15)`; `quota.consume(1)`; items → `RawItem(external_id=link, text=title+snippet, url=link, raw={"site", "title"}, search_term=term)`.
- Test: `requests.get` parcheado, 2 términos × 2 sitios con cuota 3 → exactamente 3 llamadas; primera query `'"Mabel Lara" site:instagram.com'`.
- Commit: `feat: conector Google CSE (IG/FB/X) con cuota diaria`

### Task 5: YouTubeConnector
Files: `src/connectors/youtube.py`, `tests/test_youtube.py`

- `YouTubeConnector(api_key, max_videos=5, max_comments=50, pause_seconds=0.5, published_after_days=30)`.
- Por término: `GET /youtube/v3/search` (`part=snippet, q, type=video, regionCode=CO, relevanceLanguage=es, order=date, maxResults, publishedAfter`) → `RawItem(external_id=f"yt:video:{id}", text=title+description, url=watch?v=, author=channelTitle, raw={"kind":"video"})`; luego `GET /commentThreads` (`part=snippet, videoId, maxResults, order=relevance, textFormat=plainText`; `HTTPError` → sin comentarios) → `RawItem(external_id=f"yt:comment:{id}", text=textDisplay, url=watch?v=&lc=, author=authorDisplayName, raw={"kind":"comment","video_id","video_title"}, search_term=term)`.
- Test con `requests.get` parcheado según sufijo de URL.
- Commit: `feat: conector YouTube (videos + comentarios)`

### Task 6: Sentimiento Ollama + fábrica
Files: `src/sentiment.py`, `src/config.py`, `tests/test_sentiment_ollama.py`

- Config: `SENTIMENT_BACKEND` (default `ollama`), `OLLAMA_URL`, `OLLAMA_MODEL` (`qwen2.5:14b`), `CLAUDE_MODEL` (`claude-sonnet-5`).
- Prompt incluye el nombre del candidato ("sentimiento HACIA el candidato {candidate}; informativo sin juicio → neutral"). `_parse_payload` tolera fences, label inválido → neutral, score recortado a [-1, 1], topic ≤ 80 chars.
- `SentimentEngine` (Claude) importa `anthropic` perezosamente; `score(text, candidate=None)`.
- `_ollama_post(url, json_body, timeout)` con `urllib`; `OllamaSentimentEngine.score` → `POST /api/chat` con `format: json`, `temperature: 0`; `model = f"ollama/{name}"`.
- `build_sentiment_engine()`: `claude` si `SENTIMENT_BACKEND=claude` y hay `ANTHROPIC_API_KEY`; si no, Ollama.
- Commit: `feat: sentimiento con Ollama local + selección de backend por entorno`

### Task 7: Pipeline v2
Files: `src/pipeline.py`, `src/matching.py`, `tests/test_pipeline_v2.py`

- `find_candidate_by_term(term, candidates)`: igualdad exacta (case-insensitive) contra nombre o alias.
- `ingest(session, source, connector) -> int`: crea `Run`; `try:` fetch → por item: skip si existe `(source_id, external_id)`; `url_norm = normalize_url(url)`; skip si existe otra mención con ese `url_normalized`; candidato = `find_matching_candidate(text)` o `find_candidate_by_term(search_term)`; skip si `None`; inserta sin score. `except Exception` → rollback, `run.error`. Siempre cierra `run.finished_at`, `run.new_mentions`. Nunca lanza.
- `score_pending(session, engine, limit=20) -> int`: menciones sin `SentimentScore` (outerjoin), más recientes primero; `engine.score(text, candidate=mention.candidate.name)`; si falla, log + `break`.
- `run_pipeline(...)` = `ingest` + `score_pending` (compatibilidad con tests existentes).
- Tests: dedup entre fuentes por URL con `utm_`; comentario sin nombre atribuido por `search_term`; `Run` registrado; `score_pending` clasifica y luego devuelve 0; conector que lanza → `Run.error` contiene el mensaje.
- Commit: `feat: pipeline v2 — ingest/score_pending, dedup por URL, registro de Runs`

### Task 8: Config de fuentes + seed + scheduler + run_once
Files: `src/config.py`, `scripts/seed_sources.py`, `src/scheduler.py`, `scripts/run_once.py`, `tests/test_seed.py`, `tests/test_scheduler.py`

- Config: `load_dotenv()` al inicio; `GOOGLE_API_KEY`, `GOOGLE_CSE_ID`, `GOOGLE_CSE_DAILY_LIMIT=95`, `CSE_SITES=["instagram.com","facebook.com","x.com"]`; `RSS_SOURCES` con feeds **verificados** (probar cada URL con feedparser; quitar los que devuelvan 0 entradas).
- `seed_sources.EXTRA_SOURCES`: Google News (`GOOGLE_NEWS`), Reddit (`REDDIT`, config `{"via": "rss"}`), "Instagram / Facebook / X (Google)" (`GOOGLE_CSE`), YouTube (`YOUTUBE`). `seed()` los siembra idempotente.
- `scheduler.build_connector(source, session)`: por tipo; `None` si faltan credenciales (CSE necesita `GOOGLE_API_KEY`+`GOOGLE_CSE_ID`; YouTube `GOOGLE_API_KEY`; Reddit vía Bright Data y SERP solo con `BRIGHTDATA_API_TOKEN`).
- `run_group(session, types) -> dict[name, new]`; `job_fast` (GOOGLE_NEWS, RSS, REDDIT) cada 15 min; `job_cse` cada 8 h; `job_youtube` cada 4 h; `job_score` cada 2 min (lote 20); `run_everything()`; `start_scheduler()` → `BackgroundScheduler(timezone="America/Bogota")`, `max_instances=1, coalesce=True`.
- `scripts/run_once.py`: `init_db`, `seed`, `run_everything`, y scoring hasta vaciar pendientes salvo `--no-score`.
- Tests: `build_connector` devuelve el tipo correcto y `None` sin key; `run_group` omite fuentes sin conector.
- Commit: `feat: scheduler, fábrica de conectores, seed completo y run_once`

### Task 9: Consultas del dashboard
Files: `src/queries.py`, `tests/test_queries.py`

- `summary(session, days)` → lista por candidato `{candidate_id, name, party, mentions, previous, positive, negative, neutral, pending}` ordenada Carlos primero, luego por menciones desc.
- `timeline(session, days)` → `{labels: [YYYY-MM-DD en hora Bogotá], series: [{name, data}]}`; fecha = `published_at or fetched_at`.
- `mentions(session, candidate_id, source_type, label, days=30, limit, offset)` → dicts `{id, candidate, candidate_id, source, source_type, text, url, author, published_at, label, score, topic, model}`.
- `alerts(session, candidate_name="Carlos Arias", threshold=-0.5, days=30, limit=20)`.
- `topics(session, days, limit=10)` → `[{topic, count}]` agrupando `lower(topic)`.
- `status(session)` → `{total_mentions, scored, pending, last_run, cse_used_today, sources: [{name, type, last_run, last_new, error, total}]}`.
- Commit: `feat: consultas del dashboard`

### Task 10: API FastAPI + página
Files: `src/api.py`, `src/templates/dashboard.html`, `src/static/dashboard.css`, `src/static/dashboard.js`, `tests/test_api.py`

- `create_app(session_factory=None, start_jobs=True)`: monta `/static`; Jinja2 en `templates/`; startup → `init_db()` + `start_scheduler()` si `start_jobs`; rutas `GET /`, `/api/summary?days`, `/api/timeline?days`, `/api/mentions?candidate_id&source_type&label&days&limit&offset`, `/api/alerts?days`, `/api/topics?days`, `/health`, `POST /api/refresh` (hilo daemon con `run_everything`, 202). `app = create_app()` al final del módulo.
- Página en español: cabecera (título, selector 24h/7d/30d, "última actualización", botón Actualizar), tarjetas por candidato (Carlos resaltado, barra pos/neu/neg, variación), gráficos Chart.js (líneas por día, barras apiladas de sentimiento, temas), alertas, feed filtrable con link "ver". JS carga todo por `fetch`, refresca cada 2 min.
- Tests con `TestClient` y `create_app(session_factory=lambda: db_session, start_jobs=False)`: `/` contiene "Monitor"; cada ruta JSON devuelve la forma esperada; `/api/refresh` → 202 con `run_everything` parcheado.
- Commit: `feat: dashboard FastAPI + página con gráficos, alertas y feed`

### Task 11: Demo, Docker, docs
Files: `.env.example`, `scripts/demo.ps1`, `Dockerfile`, `docs/presupuesto.md`, `docs/despliegue.md`, `README.md`, `requirements.txt`

- `.env.example` con todas las variables (comentadas en español).
- `demo.ps1`: arranca `ollama serve` si no corre, precalienta `qwen2.5:14b`, instala `cloudflared` vía winget si falta, lanza uvicorn minimizado, corre `cloudflared tunnel --url http://localhost:8000` e imprime la URL.
- `Dockerfile` python:3.11-slim, `SENTIMENT_BACKEND=claude`, CMD seed + uvicorn en `$PORT`.
- `docs/presupuesto.md`: tres escenarios (Gratis / Básico ~USD 40/mes: Claude + Railway / Completo + Bright Data), tabla por servicio con supuesto de volumen, nota de que Ollama no corre en hosting barato.
- `docs/despliegue.md`: Railway + Postgres (`postgresql+psycopg://`, `psycopg[binary]`), variables, plan B Render + Neon.
- `README.md`: qué es, instalar, `.env`, `run_once`, `uvicorn`, `demo.ps1`, tests.
- Commit: `feat: demo script, Dockerfile, presupuesto, despliegue y README`

### Task 12: Verificación end-to-end
- Verificar feeds RSS reales y podar `RSS_SOURCES`.
- `python -m scripts.run_once` con `.env` real → menciones por fuente en consola; scoring con Ollama.
- `uvicorn src.api:app --port 8000` → revisar cada sección del dashboard y el botón Actualizar.
- `.\scripts\demo.ps1` → abrir la URL `trycloudflare.com` desde el celular.
- Commit final.
