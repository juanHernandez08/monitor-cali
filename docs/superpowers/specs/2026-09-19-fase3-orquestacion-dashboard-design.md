# Fase 3 — Orquestación + Dashboard (sin keys de pago)

**Fecha:** 2026-09-19 · **Demo:** lunes 2026-09-21, 2:00 pm · **Estado:** aprobado

## Objetivo

Que el monitor capture menciones reales de los 9 candidatos a la Alcaldía de Cali 2027
(incluido Carlos Arias) desde prensa, Reddit, YouTube e Instagram/Facebook/X, las clasifique
por sentimiento, y las presente en un dashboard web con URL pública — todo funcionando el
lunes, **sin depender de Anthropic ni Bright Data**. Cuando lleguen esas keys se activan por
variable de entorno sin cambiar código.

## Fuentes (todas reales, sin costo)

| Fuente | Conector | Mecanismo | Credencial |
|---|---|---|---|
| Prensa | `GoogleNewsConnector` | RSS de Google News por término (`news.google.com/rss/search?q=…&gl=CO`) | ninguna |
| Prensa (feeds directos) | `RSSConnector` (existente) | Feeds de medios locales verificados | ninguna |
| Reddit | `RedditRSSConnector` | `reddit.com/search.rss?q=…&sort=new` | ninguna |
| Instagram / Facebook / X | `GoogleCSEConnector` | Custom Search JSON API con `site:instagram.com`, `site:facebook.com`, `site:x.com` | `GOOGLE_API_KEY` + `GOOGLE_CSE_ID` (gratis, 100 consultas/día) |
| YouTube | `YouTubeConnector` | YouTube Data API v3: `search.list` por término + `commentThreads.list` de los videos encontrados | `GOOGLE_API_KEY` (gratis, 10.000 unidades/día) |
| Reddit / SERP (Bright Data) | existentes | Se activan solo si `BRIGHTDATA_API_TOKEN` está definido | de pago (futuro) |

Cada conector implementa el `Connector` existente (`fetch(search_terms) -> list[RawItem]`).
`SourceType` gana `GOOGLE_NEWS`, `YOUTUBE`, `GOOGLE_CSE`.

**Presupuesto de consultas Google CSE:** 9 candidatos × 3 redes = 27 consultas por barrido.
El scheduler corre CSE máximo 3 veces al día (81/100). El conector lleva un contador diario
en tabla `api_usage` y se detiene al llegar a 95.

## Sentimiento

`SentimentEngine` gana un backend seleccionable por `SENTIMENT_BACKEND`:

- `ollama` (default): `POST http://localhost:11434/api/chat`, modelo `qwen2.5:14b`,
  `format: json`, `temperature: 0`. Mismo prompt que Claude. ~3 s por mención.
- `claude`: el existente, si `ANTHROPIC_API_KEY` está definido.

La columna `SentimentScore.model` registra qué modelo clasificó cada mención
(ej. `ollama/qwen2.5:14b`), visible en el dashboard.

El scoring se desacopla de la ingesta: la ingesta guarda menciones sin score; un job aparte
(`score_pending`) clasifica las pendientes en lotes. Así la ingesta no se bloquea por la
velocidad del modelo local y el dashboard muestra "pendiente de análisis" entretanto.

## Deduplicación entre fuentes

`Mention.url_normalized` (indexada): URL sin esquema, sin `www.`, sin parámetros `utm_*`/
`fbclid`/`igshid`, sin barra final, en minúsculas. Antes de insertar, si ya existe una
mención con la misma `url_normalized` (cualquier fuente), se omite. Menciones sin URL no
se deduplican por este criterio.

## Servicio único (`app/`)

Un proceso FastAPI:

- **Scheduler** (APScheduler, en el mismo proceso):
  - cada 15 min: Google News + RSS directos + Reddit RSS
  - cada 8 h: Google CSE (IG/FB/X)
  - cada 4 h: YouTube
  - cada 2 min: `score_pending` (lotes de 20)
- **Rutas**:
  - `GET /` → dashboard (Jinja2 + Chart.js por CDN, sin build step)
  - `GET /api/summary?days=7` → JSON: por candidato {menciones, pos, neg, neu, tendencia}
  - `GET /api/timeline?days=7` → JSON: menciones por día por candidato
  - `GET /api/mentions?candidate=&source=&label=&limit=` → JSON del feed
  - `GET /api/alerts` → menciones negativas (score ≤ −0.5) sobre Carlos, recientes primero
  - `POST /api/refresh` → dispara ingesta inmediata (en background) y devuelve 202
  - `GET /health` → estado del scheduler, última corrida por fuente, uso de cuota CSE
- **Logs**: tabla `runs` (source_id, started_at, finished_at, new_mentions, error) para
  mostrar "última actualización" y diagnosticar fallas sin abrir la consola.

## Dashboard (una página, español, responsive)

1. **Cabecera**: título, selector de rango (24 h / 7 d / 30 d), "Última actualización hace X min", botón **Actualizar ahora**.
2. **Tarjetas por candidato**: nombre, partido, # menciones, barra pos/neu/neg, variación vs período anterior. Carlos Arias primero y resaltado.
3. **Gráficos**: menciones por día por candidato (líneas); sentimiento por candidato (barras apiladas 100 %); top temas (barras horizontales, últimos 7 d).
4. **Alertas**: menciones negativas sobre Carlos, con texto, fuente, fecha y link.
5. **Feed**: tabla filtrable (candidato, fuente, sentimiento) con texto recortado, fuente con ícono, score, modelo, link "ver original". Paginación simple.

Sin login para la demo. Paleta neutra; badge por fuente (Prensa / Reddit / YouTube / IG / FB / X).

## URL pública

- **Lunes**: `cloudflared tunnel --url http://localhost:8000` desde la laptop → URL
  `https://<aleatorio>.trycloudflare.com`. Sin cuenta ni tarjeta. Script `scripts/demo.ps1`
  que levanta Ollama (si no está), el servidor y el tunnel, e imprime la URL.
- **Después**: `Dockerfile` + `docs/despliegue.md` (Railway/Render + Postgres). Ollama no
  corre en esos hosts baratos → en producción el backend de sentimiento debe ser Claude.
  Esto va explícito en el presupuesto.

## Presupuesto (`docs/presupuesto.md`)

Estimación mensual con supuestos de volumen (menciones/día) para: Anthropic (Sonnet 5),
Bright Data (SERP, Reddit, Instagram), Google CSE por encima del free tier, hosting
(Railway) y Postgres. Con la nota de qué se puede seguir haciendo gratis.

## Manejo de errores

- Cada conector se ejecuta aislado: si una fuente falla, se registra en `runs.error` y las
  demás continúan.
- Google CSE: si la cuota diaria se agota, el conector devuelve `[]` y registra el motivo.
- Ollama caído: `score_pending` registra el error y lo reintenta en el siguiente ciclo; las
  menciones quedan visibles como "pendiente".
- Feeds que no responden en 15 s se saltan.

## Pruebas

- Unitarias por conector con respuestas grabadas (fixtures JSON/XML), sin red.
- `normalize_url` con casos de `utm_*`, `www`, barra final, mayúsculas.
- Pipeline: dedup entre fuentes por URL; ingesta sin score + `score_pending` los completa.
- API: `TestClient` de FastAPI sobre SQLite en memoria con datos sembrados; cada ruta
  devuelve la forma esperada.
- Cuota CSE: al llegar al tope, `fetch` devuelve `[]` sin llamar a la API.

## Fuera de alcance

Radio/TV; alertas por correo/Telegram (es una sección del dashboard); login; Postgres en
producción (solo documentado); scraping directo de Instagram (Instaloader).
