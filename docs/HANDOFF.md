# HANDOFF — Monitor de menciones, Alcaldía de Cali 2027

Documento para retomar el proyecto en otra máquina o en otra sesión sin el historial de chat.
Léelo completo antes de tocar código. Estado al **2026-09-26** (auditoría nocturna).

## Qué es

Bot + dashboard que captura menciones de los **9 candidatos** a la Alcaldía de Cali 2027 (cliente:
campaña de **Carlos Arias**, concejal, Partido de la U) y de los **21 concejales de Cali**, las
clasifica por sentimiento, tema, categoría y **emoción** con un LLM, y las muestra en un tablero
web de 8 pestañas. Corre sin servicios de pago recurrentes salvo Apify (~USD 2-10/mes).

## Cómo se corre

- Windows: `.\scripts\demo.ps1` · macOS: `bash scripts/demo.sh` → Ollama + servidor en :8000 +
  túnel público de cloudflared (la URL cambia en cada arranque).
- Solo servidor: `python -m uvicorn src.api:app --host 0.0.0.0 --port 8000`.
- Tests: `python -m pytest -q` (144 al escribir esto). El proyecto se construye con TDD: test
  antes que el cambio de comportamiento.
- `.env` (no está en git) trae `GOOGLE_API_KEY`, `APIFY_TOKEN`, `OLLAMA_MODEL`. `BRIGHTDATA_API_TOKEN`
  ya no se usa (créditos agotados 2026-09-25) pero el conector queda de respaldo si se recupera.
- **`OLLAMA_NUM_GPU=0` en `.env` (mitigación temporal, 2026-09-26)**: el driver de NVIDIA
  (`nvlddmkm.sys`) está crasheando el equipo entero bajo la carga sostenida de Ollama en GPU —
  3 BSOD el mismo día, mismo código exacto `0x133 DPC_WATCHDOG_VIOLATION`, confirmado con
  `!analyze -v` sobre el volcado (`nvlddmkm+0x10bf33` en la pila, dentro de una ISR). Con esta
  variable, `src/sentiment.py` fuerza CPU en cada llamada a Ollama (más lento, pero no toca la
  GPU). **Quitar la línea del `.env` (o poner `OLLAMA_NUM_GPU=` vacío) en cuanto se actualice el
  driver de NVIDIA** — CPU-only no es el estado deseado a largo plazo, solo mientras tanto.
- `monitor.db` (SQLite, modo **WAL** desde el 2026-09-26) — soporta el servidor y scripts de
  fondo escribiendo a la vez sin bloquearse. **Una sola máquina** debe tener el scheduler
  corriendo para no duplicar consumo de cuota de Apify/YouTube.

## Arquitectura del dashboard (reescrita 2026-09-25/26)

- **Navegación**: barra lateral fija (no pestañas horizontales), 8 secciones: Resumen,
  Candidatos, Publicaciones, **Meta y redes**, Análisis en gráficas, Ciudad, **Histórico**, Agenda.
  **Concejo de Cali ya no es una pestaña propia**: vive dentro de Candidatos como una sub-pestaña
  ("Candidatos" / "Concejales", `.sub-nav`/`.subtab`/`.subtabpane` en `dashboard.css`/
  `dashboard.js`) — pedido del cliente 2026-09-26. Más una vista de **Perfil** (no está en la
  barra; se abre al tocar cualquier tarjeta de candidato y muestra todo lo recopilado de esa
  persona: gauge de positividad, temas, publicaciones). El botón "← Volver a…" de Perfil es
  dinámico (`lastTab` en `dashboard.js`): regresa a la pestaña desde la que se abrió (Resumen o
  Candidatos), no siempre a Resumen.
- **Meta y redes** (nuevo 2026-09-26): pestaña dedicada a publicaciones de Instagram/Facebook/X
  (`queries.social_posts()`/`social_kpis()`, `/api/social/posts`, `/api/social/kpis`), ordenadas
  por alcance real (likes + comentarios, y vistas cuando el video las trae) en vez de solo
  cronología. Los nombres de campo de likes/vistas cambian por plataforma y se normalizan en
  `queries._social_metrics()` (Instagram: `likesCount`/`videoPlayCount`; Facebook: `likes`/
  `viewsCount` dentro de `mention.raw["record"]`, el JSON crudo del scraper).
- **Histórico** (nuevo 2026-09-26): pestaña dedicada a comparar el período elegido contra el
  inmediatamente anterior de igual duración, por tema de ciudad. No necesitó backend nuevo — usa
  los campos `trend_pct`/`previous` que `queries.city_topics()` ya calculaba pero que la UI no
  mostraba en ningún lado desde que se quitaron las comparativas de Ciudad (pedido del cliente,
  ver commit `e8e987f` y ss.). Responde el pendiente "Comparativas entre períodos" de abajo.
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
- **Filtro de Publicaciones por tema**: `#f-category` en la pestaña Publicaciones filtra por la
  categoría fija (`sentiment.CATEGORIES`); igual que `label`/`emotion`, una publicación aparece
  si ella o alguno de sus comentarios pasa el filtro (`queries.feed(..., category=...)`).
- **Emociones de Ciudad con ejemplos**: la gráfica "¿Qué emoción transmite la ciudad?" tiene
  `onClick` por barra (igual que el histograma) que muestra citas de ejemplo debajo
  (`#city-emotion-detail`), en vez de ser solo un conteo sin forma de ver de qué se trata.
- **"Actualizar ahora" en paralelo (2026-09-26)**: `scheduler.run_group()` corría cada fuente
  (más de una decena de feeds de RSS/Google News) una por una, y `run_everything()` encadenaba
  sus 4 grupos (fast/cse/youtube/social) igual de secuencial — solo sumaba tiempos de espera de
  red sin motivo, ninguna fuente depende de otra. Ahora ambos usan `ThreadPoolExecutor`: cada
  hilo abre su propia sesión de SQLAlchemy (nunca compartir una entre hilos) contra el mismo
  engine, y el modo WAL ya soporta varios escritores a la vez. El botón del frontend también
  dejó de esperar 25s fijos — ahora consulta `/health` hasta ver una corrida terminada después
  del clic (salvavidas de 90s si algo se cuelga).
- **`pipeline.context_text(mention)`** (extraído 2026-09-26): construye el texto con contexto que
  se manda al LLM para un comentario suelto (video/post al que responde). Antes vivía duplicado
  dentro de `score_pending()` y de nuevo en `scripts/backfill_emotions.py` -- se corrigió el bug
  de abajo en un solo lugar la primera vez, pero casi se queda desactualizado el otro. Cualquier
  script nuevo que necesite ese contexto (comentarios, reclasificaciones) debe importar esta
  función, no copiarla.

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
7. **Comentarios en publicación propia**: el sentimiento se mide hacia el candidato dueño de la
   cuenta, no hacia cualquiera que el comentario mencione. Bug real 2026-09-26 (reportado por el
   cliente): un insulto a un tercero nombrado en la propia publicación del candidato (p. ej.
   "MONDRAGON TRAPO SUCIO" en un post de Carlos Arias titulado "No Alfredo Mondragón...") se
   contaba como mención NEGATIVA de Carlos y disparaba alertas falsas. `pipeline.context_text()`
   ahora le pide al LLM evaluar si el comentario apoya la publicación del candidato -normalmente
   sí, aunque el lenguaje contra ese tercero sea agresivo-, no el tono del insulto en sí.
8. **Nada simulado**: si una fuente no tiene credencial, se omite.

## Fuentes y su estado (2026-09-26)

| Fuente | Conector | Estado |
|---|---|---|
| Google News, feeds RSS locales, Reddit | `google_news.py`, `news_rss.py`, `reddit_rss.py` | Gratis, activos; Google News resiliente a un término fallido igual que YouTube (fix 2026-09-26) |
| YouTube | `youtube.py` | `GOOGLE_API_KEY`; 77 términos (candidatos+concejales) puede chocar con la cuota diaria — un término fallido ya no tumba los demás (fix 2026-09-26) |
| Instagram / Facebook / X | `social_apify.py`, `x_apify.py` | **Apify** (`APIFY_TOKEN`), reemplazó a Bright Data (créditos agotados 2026-09-25). ~USD 0,40/corrida real medida. Esquema real confirmado en producción 2026-09-26: Instagram trae `likesCount`/`videoPlayCount`/`videoViewCount`; Facebook trae `likes`/`viewsCount`/`videoPostViewCount` — sí hay vistas, no solo likes/comentarios |
| Bright Data | `social_accounts.py` | Respaldo inactivo; se usa solo si no hay `APIFY_TOKEN` |
| Google CSE | `google_cse.py` | Inactivo (API cerrada a clientes nuevos, 403) |

Faltan handles de redes de: Alfredo Mondragón, Mabel Lara, Carlos Paz, Roger Mina, y de la
mayoría de los 19 concejales (hoy solo cubiertos por prensa).

## Pendientes conocidos / próxima fase

- **Cobertura histórica de Instagram/Facebook — resuelto (2026-09-26)**: el conector solo mira
  hacia adelante desde la última publicación ya guardada por cuenta (`known_last_dates`, ver
  `scheduler._social_state`), así que una captura inicial incompleta nunca se corrige sola. Se
  corrió `scripts/backfill_social_history.py` una vez (autorizado por el cliente, gastó créditos
  de Apify reales) con ventana de 180 días para Carlos, Roberto Ortiz y Clara Luz Roldán: trajo 141
  publicaciones/comentarios nuevos. El reel más visto de Carlos Arias ("¿Trincheras en Cali?", cuyo
  titular real es "No Alfredo Mondragón, nuestro presidente...") sí se capturó, pero quedó **oculto
  por dos bugs separados**, ambos corregidos:
  1. El selector de período solo llegaba a 30 días (`#days` en `dashboard.html`) y las rutas de la
     API tenían `le=90`/`le=30` en `src/api.py` — el reel es de agosto, fuera de cualquier ventana
     disponible. Se agregaron opciones de 60/90/180 días y se subieron todos los topes de la API a
     `le=365` (el backend ya soportaba hasta 365 días; solo el frontend y algunas rutas lo
     restringían).
  2. **Bug real de atribución** en `pipeline.ingest()`: para una publicación propia (kind="post" en
     una fuente SOCIAL), si el texto nombraba a otro candidato completo (el titular de este reel
     empieza "No Alfredo Mondragón..."), `find_matching_candidate` la atrapaba antes de mirar el
     dueño real de la cuenta (`search_term`), así que el post entero -- y sus 1232 likes / 1232
     comentarios reales (solo 15 capturados por los topes de `SOCIAL_MAX_COMMENTS`) -- quedaba
     atribuido al candidato mencionado, no al dueño de la cuenta. Corregido: para publicaciones
     propias, el dueño de cuenta conocido por el conector ahora le gana a una mención textual de un
     tercero. `scripts/fix_own_post_attribution.py` reparó las 3 publicaciones ya afectadas
     (Carlos Arias, Roberto Ortiz x2) usando `config.SOCIAL_ACCOUNTS` como fuente de verdad; seguro
     de re-correr, no duplica ni toca lo ya correcto.
- **Planes de gobierno, problemáticas por sector, iniciativas en marcha**: pedido pendiente de
  una fase anterior. Es investigación documental (fuentes primarias reales), no solo código —
  no se ha empezado.
- Backfill de emoción histórica: **completado 2026-09-26** (2969 menciones). Si en el futuro
  quedan filas con `emotion IS NULL` (p. ej. tras ingestar mucho de golpe), relanzar
  `scripts/backfill_emotions.py` es seguro — solo toca esas filas, no duplica trabajo.
- Sinónimos de temas ("terremoto"/"sismo") sin unificar.
- **Oportunidades para Carlos Arias (Ciudad), rediseñado 2026-09-26**: ya no exige molestia/tono
  negativo — pedido explícito del cliente ("no es necesariamente que la gente debe estar
  molesta"). Ahora `queries.city_opportunities()` trabaja a nivel de `topic` (no de `category`) y
  marca "novedad" cuando un tema es **nuevo** (sin menciones en el período anterior) o está **en
  fuerte alza** (`trend_pct >= 80` por defecto), sin importar si el tono es positivo, negativo o
  informativo — así captura eventos como la llegada de una figura nacional a Cali, no solo quejas.
  El JSON cambió de `hot_without_carlos` a `novedades` (clave nueva, revisar si algo más la usa).
- Alertas por correo/Telegram; radio/TV (fuera de alcance, ver `docs/cotizacion.md`).
- Despliegue en VPS (`docs/cotizacion.md`, `docs/despliegue.md`) — sigue corriendo en el PC local.

## Trabajar en dos máquinas

Repo en GitHub privado, `git pull`/`git push`. `monitor.db` y `.env` no se suben (ver
`.gitignore` — incluye también `monitor.db-journal/-wal/-shm`, archivos transitorios de SQLite en
modo WAL). Ver memoria del proyecto para el estado de Remote Control / control desde el Mac.
