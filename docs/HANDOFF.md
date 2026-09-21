# HANDOFF — Monitor de menciones, Alcaldía de Cali 2027

Documento para retomar el proyecto en otra máquina o en otra sesión de Claude Code sin el
historial de chat. Léelo completo antes de tocar código. Estado al 2026-09-21 (día de la demo).

## Qué es

Bot + dashboard que captura menciones de 9 candidatos a la Alcaldía de Cali 2027 (el cliente es
la campaña de **Carlos Arias**, concejal, Partido de la U), las clasifica por sentimiento con un
LLM y las muestra en una página web. Todo corre **sin servicios de pago**: Google News RSS,
feeds de medios, Reddit RSS, YouTube Data API (key gratuita de Google), Bright Data plan gratuito
para Instagram/Facebook por cuenta, y **Ollama local** para el sentimiento.

Arquitectura, decisiones y presupuesto: `docs/superpowers/specs/`, `docs/superpowers/plans/`,
`docs/presupuesto.md`, `docs/despliegue.md`, `README.md`.

## Cómo se corre

- Windows: `.\scripts\demo.ps1` · macOS: `bash scripts/demo.sh` → Ollama + servidor en :8000 +
  tunnel público de cloudflared (la URL cambia en cada arranque; **una sola ventana a la vez**).
- Solo servidor: `python -m uvicorn src.api:app --host 0.0.0.0 --port 8000`.
- Tests: `python -m pytest -q` (69 al momento de escribir esto). Escribe un test antes de cambiar
  comportamiento; el proyecto se construyó con TDD.
- `.env` (no está en git) trae `GOOGLE_API_KEY`, `BRIGHTDATA_API_TOKEN`, `OLLAMA_MODEL`. En un Mac
  de 8 GB el modelo debe ser `qwen2.5:7b`; en el PC con RTX 3060 es `qwen2.5:14b`.
- `monitor.db` (SQLite) es la base; **una sola máquina debe tener el scheduler corriendo** para no
  duplicar consumo de créditos de Bright Data (5.000/mes gratis, ~800 por corrida, cada 5 días).

## Reglas que el cliente exigió (no relajar)

El usuario revisa el dashboard nota por nota; cada falso positivo le resta credibilidad al producto.
Ver `src/pipeline.py`, `src/enrich.py`, `src/connectors/youtube.py`, `src/config.py`.

1. **Homónimos**: `CANDIDATES[...]["exclusions"]` (p. ej. "Arias Orjuela", "Jhon Arias") descarta
   la mención al ingresar, al enriquecer y al clasificar. Regla dura, antes del modelo.
2. **Prensa**: se descarga el artículo completo (`src/enrich.py`, Google News → URL real vía
   `googlenewsdecoder`, texto vía `trafilatura`). Si titular + cuerpo no nombran al candidato o un
   alias → `relevant=False`. Google devuelve notas por enlaces/etiquetas del medio.
3. **YouTube**: el video hereda al candidato solo si título o descripción lo nombran; si no, sus
   comentarios solo cuentan si ellos mismos lo nombran.
4. **Comentarios**: "mención tangencial" → irrelevante, salvo en publicaciones de la cuenta propia
   del candidato (ahí un aplauso es apoyo). "@handle" suelto → neutral, irrelevante, sin modelo.
5. **Temas** (`topic`): es el asunto concreto, nunca el tono. "rechazo e insultos" para ataques
   sin asunto; "sin tema" para aplausos/saludos. El dashboard separa temas de publicaciones vs
   reclamos en comentarios.
6. **Nada simulado**: el cliente rechazó datos de demostración. Si una fuente no tiene credencial,
   se omite (no se inventa).
7. Sin DuckDuckGo (lo descartó por confiabilidad). La Custom Search JSON API de Google está cerrada
   a clientes nuevos (403 aunque esté habilitada); para búsqueda tipo Google usar Serper/SerpApi.

## Fuentes y su estado

| Fuente | Conector | Credencial | Notas |
|---|---|---|---|
| Google News | `google_news.py` | ninguna | 3 consultas por término (relevancia + when:60d + when:7d). `when:` rompe frases con comillas si va solo. |
| Feeds RSS de medios | `news_rss.py` | ninguna | URLs verificadas en `config.RSS_SOURCES`. |
| Reddit | `reddit_rss.py` | ninguna | Agrupa términos con OR; 429 frecuente → reintenta en el siguiente ciclo. |
| YouTube | `youtube.py` | `GOOGLE_API_KEY` | search.list = 100 unidades; corrida cada 12 h. |
| Instagram/Facebook por cuenta | `social_accounts.py` | `BRIGHTDATA_API_TOKEN` | Cuentas en `config.SOCIAL_ACCOUNTS`. SDK con `auto_create_zones=False`. IG posts = `client.search.instagram.posts(url, num_of_posts)`, comentarios = `client.scrape.instagram.comments(url)`. |
| IG/FB/X por búsqueda | `google_cse.py` | — | Inactivo (API de Google cerrada). Adaptar a Serper si se retoma. |
| Bright Data Reddit/SERP | `reddit.py`, `serp.py` | `BRIGHTDATA_API_TOKEN` | Del plan original; no se usan hoy. |

Faltan handles de Instagram/Facebook de: Alfredo Mondragón, Mabel Lara, Francia Márquez, Irene
Vélez, Roger Mina, Carlos Paz, y la página de Facebook de Carlos. Se agregan en `SOCIAL_ACCOUNTS`.

## Dashboard

`src/api.py` (FastAPI, scheduler APScheduler en el mismo proceso, seed al arrancar),
`src/queries.py` (consultas), `src/templates/dashboard.html`, `src/static/dashboard.{css,js}`.
Dos pestañas: **Resumen** (KPIs, panel de Carlos con foto de IG, rivales, alertas, reclamos, feed
agrupado por publicación con comentarios desplegables y miniaturas) y **Análisis en gráficas**
(5 gráficas grandes, cada una con explicación y una "lectura" automática en una frase).
Los estáticos llevan `?v=<mtime>` para evitar caché. Servidor nuevo = reiniciar para tomar código.

## Pendientes conocidos

- Sinónimos de temas ("terremoto", "sismo", "sismo cali") — unificar con lista de equivalencias.
- Búsqueda abierta en IG/FB/X (Serper o SerpApi cuando el usuario logre registrarse).
- Despliegue en nube (Railway + Postgres + Claude) cuando haya presupuesto — `docs/despliegue.md`.
- Alertas por correo/Telegram; radio/TV (fuera de alcance, ver presupuesto).
- Afiliación real de Carlos (la U ya tiene a Clara Luz Roldán), y partido de Carlos Paz / Roger Mina.

## Trabajar en dos máquinas

Subir el repo a un GitHub privado y hacer `git pull`/`git push` en cada equipo. `monitor.db` y
`.env` no se suben. Para llevar todo de una vez: `.\scripts\pack_for_mac.ps1` (usa `tar` para que
las rutas queden con `/`); si un zip viejo dejó archivos como `scripts\demo.sh`, reubicar con
`for f in *\\*; do mkdir -p "$(dirname "${f//\\//}")"; mv "$f" "${f//\\//}"; done` y quitar `\r`
con `sed -i '' 's/\r$//' scripts/*.sh .env`.
