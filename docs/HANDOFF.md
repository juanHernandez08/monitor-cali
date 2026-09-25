# HANDOFF — Monitor de menciones, Alcaldía de Cali 2027

Documento para retomar el proyecto en otra máquina o en otra sesión sin el historial de chat.
Léelo completo antes de tocar código. Estado al **2026-09-26** (auditoría nocturna).

## Qué es

Bot + dashboard que captura menciones de los **9 candidatos** a la Alcaldía de Cali 2027 (cliente:
campaña de **Carlos Arias**, concejal, Partido de la U) y de los **21 concejales de Cali**, las
clasifica por sentimiento, tema, categoría y **emoción** con un LLM, y las muestra en un tablero
web de 7 pestañas. Corre sin servicios de pago recurrentes salvo Apify (~USD 2-10/mes).

## Cómo se corre

- Windows: `.\scripts\demo.ps1` · macOS: `bash scripts/demo.sh` → Ollama + servidor en :8000 +
  túnel público de cloudflared (la URL cambia en cada arranque).
- Solo servidor: `python -m uvicorn src.api:app --host 0.0.0.0 --port 8000`.
- Tests: `python -m pytest -q` (129 al escribir esto). El proyecto se construye con TDD: test
  antes que el cambio de comportamiento.
- `.env` (no está en git) trae `GOOGLE_API_KEY`, `APIFY_TOKEN`, `OLLAMA_MODEL`. `BRIGHTDATA_API_TOKEN`
  ya no se usa (créditos agotados 2026-09-25) pero el conector queda de respaldo si se recupera.
- `monitor.db` (SQLite, modo **WAL** desde el 2026-09-26) — soporta el servidor y scripts de
  fondo escribiendo a la vez sin bloquearse. **Una sola máquina** debe tener el scheduler
  corriendo para no duplicar consumo de cuota de Apify/YouTube.

## Arquitectura del dashboard (reescrita 2026-09-25/26)

- **Navegación**: barra lateral fija (no pestañas horizontales), 7 secciones: Resumen,
  Candidatos, Publicaciones, Análisis en gráficas, Ciudad, Agenda, Concejo de Cali. Más una
  vista de **Perfil** (no está en la barra; se abre al tocar cualquier tarjeta de candidato y
  muestra todo lo recopilado de esa persona: gauge de positividad, temas, publicaciones).
- **Gráficas**: ApexCharts (no Chart.js). Helpers reutilizables en `dashboard.js`: `chart()`,
  `hbar()` (barra horizontal, admite `onClick` por barra), `hbar100()` (apilada al 100%, el
  color de cada serie se pasa explícito — nunca asumir orden positivo/neutral/negativo).
- **Paleta**: validada contra daltonismo con el skill de dataviz (`node scripts/validate_palette.js`
  si se agregan colores nuevos). Constantes en `dashboard.js`: `BLUE/ORANGE/AQUA/YELLOW/MAGENTA/
  GREEN/VIOLET/RED` (categórica) y `GOOD/CRITICAL/NEUTRAL_TONE` (estado).
- **Componente de temas** (`topicCard()`/`renderTopicCards()` en `dashboard.js`): tarjetas
  colapsadas con botón "ver comentarios de ejemplo", usado tanto en el Perfil de cualquier
  candidato como en "Detalle por tema" de Ciudad. Antes de escribir un componente nuevo similar,
  revisar si esto ya sirve.
- Los estáticos llevan `?v=<mtime>` para evitar caché; cambios en `.py` sí requieren reiniciar el
  servidor, cambios en `.html/.css/.js` no.

## Reglas que el cliente exigió (no relajar)

1. **Homónimos**: `exclusions` por candidato/concejal descarta la mención al ingresar, enriquecer
   y clasificar.
2. **Figuras nacionales**: candidatos con perfil político nacional (p. ej. Francia Márquez,
   Vicepresidenta hasta ago-2026; Irene Vélez, exministra; Alfredo Mondragón, congresista del
   Pacto Histórico) necesitan `context_terms` igual que los concejales, o la prensa nacional
   sobre su cargo se cuela como si fuera de la Alcaldía de Cali. Auditoría 2026-09-26: 31%, 43%
   y 61% de su prensa respectivamente no mencionaba "Cali" ni "Alcaldía" en absoluto. **Antes de
   agregar un candidato nuevo, evaluar si es figura pública nacional y ponerle `context_terms`.**
   También revisar homónimos geográficos/de terceros: Carlos Paz colisionaba con medios
   argentinos llamados igual que la ciudad turística Villa Carlos Paz ("Carlos Paz Vivo", "El
   Diario de Carlos Paz") y con un futbolista de los años 60 — resuelto con `exclusions`.
3. **Prensa**: debe nombrar al candidato en titular+cuerpo, o queda fuera. Esto se exige incluso
   cuando el cuerpo no se pudo descargar (`body == ""`): antes de 2026-09-26 ese caso se saltaba
   el chequeo por completo y la mención quedaba `relevant=True` para siempre con solo haber
   coincidido el término de búsqueda con Google News (que hace matching temático, no literal).
   Si el cuerpo sigue `None` (pendiente de enriquecer) sí se le da el beneficio de la duda.
4. **YouTube**: el video hereda al candidato solo si título/descripción lo nombran; si no, sus
   comentarios solo cuentan si ellos mismos lo nombran (independiente de cómo el LLM clasificó
   el tema — ver `scripts/recompute_relevance.py`).
5. **Temas**: nunca el tono. "rechazo e insultos" para ataques sin asunto; "sin tema" para
   aplausos/saludos.
6. **Emoción** (nuevo 2026-09-26): además de positivo/negativo/neutral, cada mención clasificada
   de ahora en adelante trae una emoción de la rueda de Plutchik + orgullo (`sentiment.EMOTIONS`).
   Es **forward-only** como el resumen de una frase — lo histórico se rellena con
   `scripts/backfill_emotions.py` (solo toca el campo `emotion`, no re-evalúa lo demás).
7. **Nada simulado**: si una fuente no tiene credencial, se omite.

## Fuentes y su estado (2026-09-26)

| Fuente | Conector | Estado |
|---|---|---|
| Google News, feeds RSS locales, Reddit | `google_news.py`, `news_rss.py`, `reddit_rss.py` | Gratis, activos; Google News resiliente a un término fallido igual que YouTube (fix 2026-09-26) |
| YouTube | `youtube.py` | `GOOGLE_API_KEY`; 77 términos (candidatos+concejales) puede chocar con la cuota diaria — un término fallido ya no tumba los demás (fix 2026-09-26) |
| Instagram / Facebook / X | `social_apify.py`, `x_apify.py` | **Apify** (`APIFY_TOKEN`), reemplazó a Bright Data (créditos agotados 2026-09-25). ~USD 0,40/corrida real medida |
| Bright Data | `social_accounts.py` | Respaldo inactivo; se usa solo si no hay `APIFY_TOKEN` |
| Google CSE | `google_cse.py` | Inactivo (API cerrada a clientes nuevos, 403) |

Faltan handles de redes de: Alfredo Mondragón, Mabel Lara, Carlos Paz, Roger Mina, y de la
mayoría de los 19 concejales (hoy solo cubiertos por prensa).

## Pendientes conocidos / próxima fase

- **Comparativas entre períodos**: se quitaron de Ciudad (flechas de tendencia, "tema que más
  crece") a pedido del cliente — la intención es una pestaña dedicada a esto. Los datos ya
  existen (`trend_pct` en `queries.city_topics`, `previous` en `queries.summary`); falta
  construir la vista.
- **Planes de gobierno, problemáticas por sector, iniciativas en marcha**: pedido pendiente de
  una fase anterior. Es investigación documental (fuentes primarias reales), no solo código —
  no se ha empezado.
- Backfill de emoción histórica: revisar si `scripts/backfill_emotions.py` ya terminó
  (`select count(*) from sentiment_scores where emotion is null`); si el proceso murió a medio
  camino, relanzarlo es seguro (solo toca filas con `emotion IS NULL`, no duplica trabajo).
- Sinónimos de temas ("terremoto"/"sismo") sin unificar.
- **Duda para Carlos Arias (no resuelta, necesita ojo local)**: 6 de las menciones de YouTube del
  candidato "Carlos Paz" vienen de videos de salsa en vivo ("La Clave, Carlos Paz y Salsa al
  Parque", canal ajeno a política) — podría ser un DJ/presentador de la escena de salsa de Cali
  homónimo, no el candidato. No se excluyó por no tener certeza; si Carlos confirma que no es él,
  agregar esa frase a `exclusions` de Carlos Paz en `config.py`.
- Alertas por correo/Telegram; radio/TV (fuera de alcance, ver `docs/cotizacion.md`).
- Despliegue en VPS (`docs/cotizacion.md`, `docs/despliegue.md`) — sigue corriendo en el PC local.

## Trabajar en dos máquinas

Repo en GitHub privado, `git pull`/`git push`. `monitor.db` y `.env` no se suben (ver
`.gitignore` — incluye también `monitor.db-journal/-wal/-shm`, archivos transitorios de SQLite en
modo WAL). Ver memoria del proyecto para el estado de Remote Control / control desde el Mac.
