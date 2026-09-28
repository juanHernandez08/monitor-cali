# HANDOFF — Monitor de menciones, Alcaldía de Cali 2027

Documento para retomar el proyecto en otra máquina o en otra sesión sin el historial de chat.
Léelo completo antes de tocar código. Estado al **2026-09-28**.

## Qué es

Bot + dashboard que captura menciones de los **9 candidatos** a la Alcaldía de Cali 2027 (cliente:
campaña de **Carlos Arias**, concejal, Partido de la U) y de los **21 concejales de Cali**, las
clasifica por sentimiento, tema, categoría y **emoción** con un LLM, y las muestra en un tablero
web de **9 pestañas** (se agregó Reporte, ver abajo). Corre sin servicios de pago recurrentes
salvo Apify (presupuesto aprobado: hasta 200.000 COP/mes, 2026-09-28).

## Cómo se corre

- Windows: `.\scripts\demo.ps1` · macOS: `bash scripts/demo.sh` → Ollama + servidor en :8000 +
  túnel público de cloudflared (la URL cambia en cada arranque).
- Solo servidor: `python -m uvicorn src.api:app --host 0.0.0.0 --port 8000`.
- Tests: `python -m pytest -q` (189 al escribir esto). El proyecto se construye con TDD: test
  antes que el cambio de comportamiento.
- **Login obligatorio en la nube (2026-09-28)**: `DASHBOARD_USER`/`DASHBOARD_PASSWORD` en `.env`
  activan HTTP Basic delante de TODO (API y estáticos) -- sin ellas el sitio queda abierto, como
  hasta ahora en local. Antes de desplegar en la nube, configurarlas SIEMPRE (ver sección
  "Despliegue en la nube" abajo).
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
- **Ciudad ya no es solo un resumen (2026-09-28)**: la pestaña estaba limitada a agregados
  (temas, KPIs, oportunidades) sin forma de ver el contenido de fondo. Se agregó: (1) panel
  "¿Qué emoción transmite cada tema?", un heatmap tema×emoción (`queries.city_emotion_by_topic()`,
  `/api/city/emotion-by-topic`) con las 12 categorías más mencionadas; (2) panel "Todo lo que pasa
  en Cali" al final de la pestaña -- feed completo (prensa, YouTube, Instagram/Facebook/X) de
  menciones con `Candidate.kind == "city"`, con sentimiento por publicación y por comentario,
  tema y emoción visibles, y los mismos filtros que Publicaciones (`queries.feed(..., city=True)`,
  ya soportado por `/api/feed?city=true`). Reutiliza `renderFeedList()` sin cambios. **Ojo**: al
  agregar cualquier ruta nueva en `api.py` hay que reiniciar uvicorn -- los cambios en `.py` no se
  recargan solos (a diferencia de `.js`/`.html`), y este mismo cambio quedó devolviendo 404 en el
  servidor corriendo hasta reiniciarlo.

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

**Cobertura de redes ampliada (2026-09-28)**: `config.SOCIAL_ACCOUNTS` pasó de 3 cuentas (Carlos
Arias, Roberto Ortiz, Clara Luz Roldán) a **24**, cubriendo casi todos los candidatos y concejales.
Causa raíz del bug reportado por el cliente ("un reel de la concejal Audry Toro no aparece"): el
conector nunca la scrapeaba porque su cuenta no estaba en esta lista -- no era un problema de
clasificación. Cada cuenta nueva se verificó visitando el perfil real (bio + cargo/partido
coincidente), nunca solo un handle que suena parecido. Detalle y caveats en el commit; los más
importantes:
- **Carlos Paz**: sin cuenta -- no se pudo verificar ninguna con confianza (homónimos: DJ,
  ciudad argentina, futbolista de los 60).
- **Mabel Lara** (`mabellaranews`): identidad confirmada (599K seguidores), pero su bio no
  menciona Cali/Nuevo Liberalismo y prensa reciente la muestra en el gabinete de Éder (Secretaria
  de Desarrollo Económico) -- confirmar con el cliente si sigue activa como candidata 2027.
- **Luis Fernando Salazar** (`luisfernandosalazarg`): registros oficiales del Concejo lo nombran
  "Salazar Guapacha", no "Salazar Monsalve" como está en `COUNCILORS` -- mismo perfil en todo lo
  demás (ingeniero, Pacto Histórico, curul desde nov-2024), pero revisar el segundo apellido.
- **Ana Leidy Erazo Ruiz** (`anaerazor`): prensa indica que renunció a la curul en nov-2025 para
  asumir como representante a la Cámara -- la cuenta es real y suya, pero `COUNCILORS` puede estar
  desactualizado (¿ya tiene reemplazo en el Concejo?).
- **Roger Mina** (`x.com/RogerMinaC`): verificado de forma indirecta (X bloqueó la carga directa
  del perfil), corroborado por caché de buscador + la cuenta oficial de Emcali etiquetándolo.

`social_posts()`/`social_kpis()` (pestaña Meta y redes) ahora incluyen concejales, no solo a los
9 candidatos a la alcaldía (antes filtraban `Candidate.kind == "candidate"` a secas). El filtro de
candidato de esa pestaña ahora sale de `/api/social/candidates`, no de la lista de 9 de Resumen.

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
- **Planes de gobierno, problemáticas por sector, iniciativas en marcha**: **primera versión
  hecha 2026-09-26** — ver `src/institutional_history.py` y la sección "Las últimas 4 alcaldías
  de Cali" al final de la pestaña Histórico. Es investigación documental real (prensa, fuentes
  oficiales, un estudio académico), cada afirmación con su fuente citada. Cobertura actual:
  hechos y cifras más documentados por administración (deuda pública, proyectos insignia,
  métricas con fuente) — **no es exhaustivo proyecto por proyecto todavía**; es una base sólida
  ampliable con más horas de investigación. Varias fuentes son editoriales de opinión de
  Caliescribe (marcadas explícitamente como tal en la UI y en los datos) — son señalamientos de
  ese medio, no hallazgos verificados de forma independiente; si se consigue una cifra oficial
  de Contraloría/Concejo, reemplazar esa fuente por la oficial. Antes de agregar más
  administraciones o proyectos, seguir el mismo patrón: cada entrada en `ADMINISTRATIONS`
  necesita `source: {name, url}` — `tests/test_institutional_history.py` lo exige.
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
- **Emociones "sorpresa" y "anticipación" retiradas (2026-09-28)**: pedido del cliente
  ("anticipación no es una emoción como tal") -- ambas casi nunca se usaban en la práctica.
  `sentiment.EMOTIONS` quedó en 7 + "sin emoción marcada". Las 12 menciones ya guardadas con esos
  valores se reclasificaron con `scripts/reclassify_retired_emotions.py` (seguro de re-correr si
  aparece algún caso suelto).
- **Alerta de actividad fuerte en redes (2026-09-28)**: `queries.social_strong_posts()` compara
  cada publicación contra el promedio de alcance de esa MISMA cuenta (no un umbral fijo igual para
  todos) -- necesita al menos 2 publicaciones previas de esa cuenta para tener con qué comparar.
  Panel nuevo en Resumen, al lado de Alertas. Esto es justo lo que le faltaba al monitor para
  cumplir su propósito: antes nada avisaba cuando algo se viraliza.
- **"Investigar un perfil" (2026-09-28)**: panel nuevo arriba de Meta y redes -- pegás CUALQUIER
  URL de Instagram/Facebook (rival, cuenta nueva) y `investigate_profile()`
  (`src/connectors/social_apify.py`) trae sus publicaciones recientes al momento vía Apify, sin
  pasar por `SOCIAL_ACCOUNTS` ni guardar nada en la base de datos. Gasta créditos de Apify en
  cada consulta -- pensado para uso puntual, no para monitoreo recurrente.
- **Reporte diario, lunes a viernes (2026-09-28)**: pestaña nueva "Reporte". Se genera solo a las
  7 a.m. hora Bogotá (`scheduler.job_daily_report`, cron `mon-fri`) y también a demanda con el
  botón "Generar el de hoy". Cubre: actividad en redes de candidatos y concejales (últimos 3 días,
  para que el reporte del lunes alcance a cubrir el fin de semana), publicaciones con fuerza fuera
  de lo habitual, temas de ciudad más mencionados y "novedades" (últimos 7 días, reusa
  `city_opportunities()`), y cuántas menciones siguen sin analizar (`SentimentScore` pendiente).
  Queda guardado en la tabla `reports` (un JSON por día, se sobreescribe si se regenera el mismo
  día) -- `src/report.py` tiene el cálculo y el armado del PDF (`reportlab`, nueva dependencia en
  `requirements.txt`). Botón "Descargar PDF" en la pestaña baja `/api/reports/{date}/pdf`. Tanto
  la pestaña como el PDF incluyen gráficas de barras (publicaciones por candidato/concejal, temas
  de ciudad) -- pedido explícito del cliente, no solo texto. **Bug real atrapado al probar con
  datos reales (no con listas vacías)**: `queries.city_topics()` devuelve la clave `"category"`,
  no `"topic"` -- el PDF tiraba `KeyError` en cuanto había datos de ciudad reales. Corregido en
  `report.py` y en `dashboard.js`; se agregó `tests/test_report.py::test_report_to_pdf_with_real_city_topics_and_social_data`
  para que no vuelva a pasar sin que un test lo note.
- **Reporte rehecho como análisis de datos, no solo cifras (2026-09-28, mismo día)**: el cliente
  mandó feedback duro con un documento de referencia ("muy mal hecho, muy pobre") pidiendo un
  analista de verdad: por qué el alcance de Carlos es el que es frente a sus rivales, y una
  estrategia basada en eso. Se agregó:
  - `queries.candidate_reach_comparison()`: alcance promedio por publicación, ritmo semanal y
    tendencia (primera vs. segunda mitad del período) por candidato/concejal.
  - `queries.candidate_comment_reaction()`: % positivo/neutral/negativo de los comentarios en la
    publicación PROPIA de cada quien (no cualquier comentario que lo nombre de pasada -- exige que
    `Mention.candidate` coincida con `raw.account_candidate`, si no un insulto a un tercero dejado
    en el post de X se contaba como reacción a X).
  - `queries.candidate_topic_gaps()`: categorías de ciudad con volumen real donde el candidato no
    tiene NINGUNA mención propia -- usa la `category` fija del LLM, exacta, no el `topic` libre.
  - `sentiment.py`: nuevo método `generate_text(prompt)` en ambos motores (Claude/Ollama) -- texto
    libre, no la clasificación JSON de `score()`. Se usa una sola vez por reporte para redactar
    "resumen ejecutivo", "por qué" y "estrategia" **a partir de las cifras ya calculadas arriba**
    (nunca le pasamos texto libre de menciones: el prompt (`report.ANALYST_PROMPT`) le prohíbe
    inventar hechos que no estén en los números dados, y si el LLM falla el reporte se genera
    igual, solo sin esa sección). Probado en producción real (2026-09-28): detectó que Carlos
    tiene 100% de comentarios positivos en sus propias publicaciones (67 de 67) -- señal real de
    audiencia autoseleccionada, exactamente el tipo de hallazgo que pedía el cliente.
  - Dos bugs reales de `city_opportunities()` corregidos con TDD en el mismo commit:
    1. **Nunca sugerir equipos deportivos**: `NOVEDADES_EXCLUDED_CATEGORIES = {"deporte"}` -- el
       cliente fue explícito: recomendar que Carlos hable de un partido/equipo fomenta rivalidad
       entre hinchas en vez de ayudarlo.
    2. **"Carlos: sin presencia" en temas de los que sí había hablado**: el emparejamiento era por
       `topic` EXACTO entre la mención de ciudad y la de Carlos, pero el LLM no siempre etiqueta
       igual el mismo asunto real (un post de Carlos sobre la Operación Iron quedó con topic
       "seguridad", no "Operación Iron"). Ahora `queries.mentions_covering_topic()` compara
       palabras distintivas del texto/topic, no el string exacto -- confirmado con datos reales:
       antes daba "Carlos: sin presencia" en Operación Iron, ahora "Carlos: 1 menciones".
  - Pestaña Reporte y PDF ampliados con las gráficas nuevas: alcance promedio por candidato,
    tendencia (verde/rojo), reacción ciudadana (barras 100% apiladas), y las listas "temas que
    Carlos no ha tocado" y "estrategia recomendada". Verificado en vivo contra datos reales del
    2026-09-28 (navegador + PDF descargado), no solo con los tests.

## Despliegue en la nube (prioridad del cliente desde 2026-09-28)

`docs/cotizacion.md` tiene el plan ya costeado y aprobado: **Escenario B** (VPS + SQLite + Claude
Haiku, ~USD 41/mes ≈ $132.000 COP, cabe cómodo en el presupuesto aprobado de 200.000 COP/mes).
`docs/despliegue.md` quedó desactualizado (recomienda Railway + Postgres, un plan anterior) --
seguir `cotizacion.md`, no `despliegue.md`, salvo que el cliente pida explícitamente Railway.

Ya listo en código para desplegar:
- `Dockerfile` (raíz del repo) -- usa `SENTIMENT_BACKEND=claude` automáticamente, corre el seed y
  levanta uvicorn. No necesita cambios para un VPS o un PaaS con soporte Docker.
- **Login obligatorio** (`DASHBOARD_USER`/`DASHBOARD_PASSWORD`, ver arriba) y encabezados de
  seguridad HTTP (`X-Frame-Options`, `X-Content-Type-Options`, HSTS cuando hay HTTPS) en
  `src/api.py`.

Falta (acciones que solo el cliente puede hacer -- crear cuentas, pagar):
1. Crear cuenta + servidor en el proveedor de VPS (DigitalOcean recomendado sobre Hetzner: en
   sept-2026 varios planes CX de Hetzner aparecían agotados, ver `cotizacion.md` §7).
2. Dominio propio si no tiene uno (~USD 12/año).
3. Acceso SSH al servidor (IP + credenciales) para desplegar.
4. Confirmar `ANTHROPIC_API_KEY` para producción (en la nube reemplaza a Ollama).
5. Elegir usuario/contraseña del login del dashboard.

## Trabajar en dos máquinas

Repo en GitHub privado, `git pull`/`git push`. `monitor.db` y `.env` no se suben (ver
`.gitignore` — incluye también `monitor.db-journal/-wal/-shm`, archivos transitorios de SQLite en
modo WAL). Ver memoria del proyecto para el estado de Remote Control / control desde el Mac.
