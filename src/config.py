import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///monitor.db")

# Login del dashboard (HTTP Basic). Sin DASHBOARD_PASSWORD, el sitio queda abierto -- así sigue
# funcionando como hasta ahora en desarrollo local. En la nube es OBLIGATORIO configurar ambas:
# sin login, cualquiera con la URL ve las menciones, el análisis de sentimiento y la estrategia.
DASHBOARD_USER = os.environ.get("DASHBOARD_USER")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD")

# Cloudflare Access (opcional, recomendado en producción): con ambas variables, el servidor valida
# el token firmado que Access agrega a cada petición. Así nadie entra llegando directo a la IP del
# VPS saltándose el login por correo. TEAM_DOMAIN = "<equipo>.cloudflareaccess.com"; AUD = el
# "Application Audience (AUD) Tag" de la aplicación en Zero Trust.
CF_ACCESS_TEAM_DOMAIN = os.environ.get("CF_ACCESS_TEAM_DOMAIN")
CF_ACCESS_AUD = os.environ.get("CF_ACCESS_AUD")

# URL pública del dashboard (sin / al final) -- para que las notificaciones (src/notify.py)
# puedan armar un link que abra el monitor directo en el candidato o la pestaña de la alerta.
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://monitordescucha.tech").rstrip("/")

# Notificaciones push por ntfy.sh (gratis, sin cuenta -- ver src/notify.py). NTFY_TOPIC_TEAM:
# alertas de campaña (mención negativa fuerte, actividad inusual en redes, resumen diario) para
# todo el equipo. NTFY_TOPIC_TECH: solo para Juan (túnel de Ollama caído, servidor). Los nombres
# de los topics deben ser largos y difíciles de adivinar -- ntfy.sh es público, cualquiera que
# sepa el nombre del topic puede suscribirse. Vacío = esa notificación no se envía.
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")
NTFY_TOPIC_TEAM = os.environ.get("NTFY_TOPIC_TEAM")
NTFY_TOPIC_TECH = os.environ.get("NTFY_TOPIC_TECH")

# /docs y /openapi.json describen toda la API; apagados salvo que se pidan explícitamente.
ENABLE_API_DOCS = os.environ.get("ENABLE_API_DOCS", "").lower() in ("1", "true", "yes")

# Un solo proceso debe correr el scheduler (captura + clasificación). 0 = solo web.
RUN_SCHEDULER = os.environ.get("RUN_SCHEDULER", "1").lower() not in ("0", "false", "no")

# Espera mínima entre acciones que gastan dinero (segundos).
REFRESH_MIN_INTERVAL = int(os.environ.get("REFRESH_MIN_INTERVAL", "120"))
INVESTIGATE_MIN_INTERVAL = int(os.environ.get("INVESTIGATE_MIN_INTERVAL", "30"))
REPORT_MIN_INTERVAL = int(os.environ.get("REPORT_MIN_INTERVAL", "60"))

# Sentimiento: "ollama" (local, gratis) o "claude" (requiere ANTHROPIC_API_KEY)
SENTIMENT_BACKEND = os.environ.get("SENTIMENT_BACKEND", "ollama")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:14b")
# Mitigación temporal (2026-09-26): el driver de NVIDIA (nvlddmkm.sys) está crasheando el equipo
# (BSOD 0x133 DPC_WATCHDOG_VIOLATION) bajo la carga sostenida de Ollama en GPU. OLLAMA_NUM_GPU=0
# fuerza CPU (más lento, pero no toca la GPU) mientras se actualiza el driver. None = decide Ollama.
OLLAMA_NUM_GPU = int(os.environ["OLLAMA_NUM_GPU"]) if os.environ.get("OLLAMA_NUM_GPU") is not None else None
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")  # solo el análisis narrativo del reporte (poco volumen, 1/día)
# Clasificación (label/tema/categoría/emoción por mención): esto es el volumen real -- cientos por
# día -- así que es lo que de verdad pesa en la factura. Haiku es lo que se cotizó y aprobó con el
# cliente (docs/cotizacion.md); Sonnet quedó puesto por error y costaba ~2× lo presupuestado
# (2026-09-30, cliente avisó que quedaban USD 5 de saldo -- viabilidad del proyecto en juego).
CLAUDE_CLASSIFY_MODEL = os.environ.get("CLAUDE_CLASSIFY_MODEL", "claude-haiku-4-5")

# Google Cloud (gratis): Custom Search JSON API + YouTube Data API v3
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID")
GOOGLE_CSE_DAILY_LIMIT = int(os.environ.get("GOOGLE_CSE_DAILY_LIMIT", "95"))
CSE_SITES = ["instagram.com", "facebook.com", "x.com"]

# Bright Data (de pago, opcional)
BRIGHTDATA_API_TOKEN = os.environ.get("BRIGHTDATA_API_TOKEN")

# Candidatos a monitorear — fuente: @noticalioficial (Instagram, 13 sep 2026),
# contrastado con prensa (El País, Caliescribe, Infobae, sep 2026).
# Los alias sin tilde importan: el matching es por substring y las tildes cuentan.
# Actualizar con la lista oficial de inscritos cuando la Registraduría la publique (2027).
CANDIDATES = [
    {
        "name": "Carlos Arias", "party": "Partido de la U",
        # La prensa lo nombra "Carlos Andrés Arias" en las notas del Concejo. Los homónimos
        # (p. ej. Carlos Andrés Arias Orjuela) los descarta el clasificador (topic "homónimo").
        "aliases": [
            "Carlos Andrés Arias Rueda", "Carlos Andrés Arias", "Carlos Andres Arias",
            "@soycarlosaarias", "Buenos Ciudadanos",
        ],
        # Homónimos conocidos: si aparecen en el titular o el cuerpo, la mención se descarta.
        "exclusions": [
            "Arias Orjuela", "Arias Orejuela", "Arias Navarro", "Jhon Arias", "Alfredo Arias",
            "Pastor Carlos Arias", "Carlos Miguel Arias", "Juan Carlos Arias", "Luis Carlos Arias",
        ],
        # "Carlos Arias" es un nombre común (auditoría 2026-09-29: prensa nacional sobre un
        # futbolista "Luis Carlos Arias" se colaba sin este filtro). Igual que Mondragón/Márquez/
        # Vélez, solo aplica a prensa (ver matching.has_required_context / enrich.py) -- no a
        # redes ni comentarios, donde la atribución viene de la cuenta, no del texto.
        "context_terms": ["Cali", "Alcaldía", "Alcaldia", "Concejo"],
    },
    {
        # Congresista del Pacto Histórico: sin exigir contexto local, la mayoría de prensa que
        # lo nombra es sobre su actividad legislativa nacional, no sobre Cali. Auditoría
        # 2026-09-26: 61% de sus menciones de prensa no mencionaban "Cali" ni "Alcaldía".
        "name": "Alfredo Mondragón", "party": "Pacto Histórico",
        "aliases": ["Alfredo Mondragon"],
        "context_terms": ["Cali", "Alcaldía", "Alcaldia"],
    },
    {
        "name": "Roberto Ortiz", "party": None,  # independiente; hoy concejal de Cali
        # "Chontico" a secas trae la Lotería Chontico; solo variantes con apellido.
        "aliases": ["Roberto Ortiz Urueña", "Roberto Ortiz Uruena", "Chontico Ortiz"],
    },
    {
        "name": "Mabel Lara", "party": "Nuevo Liberalismo",
        "aliases": [],
    },
    {
        "name": "Clara Luz Roldán", "party": "Partido de la U",  # única candidatura formalizada (sep 2026)
        "aliases": ["Clara Luz Roldan", "Clara Roldán", "Clara Roldan"],
    },
    {
        # Vicepresidenta de Colombia hasta ago-2026: sin exigir contexto local, la mayoría de
        # prensa que la nombra es sobre su gestión nacional, no sobre Cali. Auditoría 2026-09-26:
        # 31% de sus menciones de prensa no mencionaban "Cali" ni "Alcaldía" en absoluto.
        "name": "Francia Márquez", "party": "Pacto Histórico",
        "aliases": ["Francia Marquez", "Francia Elena Márquez"],
        "context_terms": ["Cali", "Alcaldía", "Alcaldia"],
    },
    {
        "name": "Carlos Paz", "party": None,  # afiliación no confirmada en prensa
        "aliases": [],
        # Homónimo geográfico: Villa Carlos Paz (Córdoba, Argentina) tiene medios locales que se
        # llaman igual ("Carlos Paz Vivo", "El Diario de Carlos Paz") y cuyo nombre de publicación
        # queda pegado al titular de Google News, coincidiendo con el nombre del candidato aunque
        # la nota no sea sobre él. Auditoría 2026-09-26: 3 de 5 menciones de prensa eran de esos
        # medios argentinos cubriendo un terremoto en Colombia, sin relación con el candidato.
        "exclusions": [
            "Carlos Paz Vivo", "eldiariodecarlospaz", "El Diario de Carlos Paz",
            "Villa Carlos Paz", "Carlos Paz, Argentina", "Carlos Paz (Argentina)",
            "Córdoba, Argentina", "Luis Carlos Paz",  # futbolista del América de Cali, años 60
            "La Clave, Carlos Paz y Salsa al Parque",  # DJ/presentador de salsa en vivo, confirmado por el cliente 2026-09-26
        ],
    },
    {
        "name": "Roger Mina", "party": None,  # gerente de Emcali; afiliación no confirmada
        "aliases": [],
    },
    {
        # Exministra de Minas y Energía: mismo problema que Francia Márquez, más marcado (43% de
        # sus menciones de prensa sin "Cali" ni "Alcaldía" en la auditoría 2026-09-26).
        "name": "Irene Vélez", "party": "Pacto Histórico",
        "aliases": ["Irene Velez", "Irene Vélez Torres"],
        "context_terms": ["Cali", "Alcaldía", "Alcaldia"],
    },
]

# Cuentas de Instagram/Facebook a monitorear vía Bright Data (posts + comentarios).
# "candidate": los posts/comentarios de esa cuenta se atribuyen al candidato; None = medio
# (solo cuenta lo que nombre a un candidato). Completar con los handles confirmados.
SOCIAL_ACCOUNTS = [
    {"platform": "instagram", "url": "https://www.instagram.com/soycarlosaarias/", "candidate": "Carlos Arias"},
    {"platform": "instagram", "url": "https://www.instagram.com/robertoortizcali/", "candidate": "Roberto Ortiz"},
    {"platform": "instagram", "url": "https://www.instagram.com/claraluzroldan/", "candidate": "Clara Luz Roldán"},
    {"platform": "facebook", "url": "https://www.facebook.com/ClaraLuzRoldanG/", "candidate": "Clara Luz Roldán"},
    {"platform": "instagram", "url": "https://www.instagram.com/noticalioficial/", "candidate": None},
    # X (Twitter): solo posts de la cuenta (Bright Data no trae las respuestas). Completar handles.
    {"platform": "x", "url": "https://x.com/claraluzroldan", "candidate": "Clara Luz Roldán"},
    # Concejales y candidatos restantes -- investigación 2026-09-28, cada cuenta confirmada
    # visitando el perfil real y contrastando la bio con el cargo/partido (nunca solo un handle
    # que suena parecido). Candidato "Carlos Paz" queda sin cuenta: no se pudo verificar ninguna
    # con confianza, y hay homónimos conocidos (DJ, ciudad argentina, futbolista) -- ver
    # config.py CANDIDATES para el detalle de esas exclusiones.
    {"platform": "instagram", "url": "https://www.instagram.com/audrytoro/", "candidate": "Audry María Toro Echavarría"},
    {"platform": "instagram", "url": "https://www.instagram.com/alfredolidersocial/", "candidate": "Alfredo Mondragón"},
    # OJO: bio no menciona Cali/Nuevo Liberalismo explícitamente; prensa reciente la muestra en el
    # gabinete de Éder (Secretaria de Desarrollo Económico), no en campaña activa -- confirmar con
    # el cliente si sigue vigente como candidata antes de darle peso en el análisis.
    {"platform": "instagram", "url": "https://www.instagram.com/mabellaranews/", "candidate": "Mabel Lara"},
    {"platform": "instagram", "url": "https://www.instagram.com/franciamarquezm/", "candidate": "Francia Márquez"},
    # Verificado de forma indirecta (perfil de X bloqueó la carga directa): bio coincidente vía
    # caché de buscador + la propia cuenta oficial de Emcali etiquetando este handle como suyo.
    {"platform": "x", "url": "https://x.com/RogerMinaC", "candidate": "Roger Mina"},
    {"platform": "instagram", "url": "https://www.instagram.com/ireneveleztorres/", "candidate": "Irene Vélez"},
    {"platform": "instagram", "url": "https://www.instagram.com/concejaltania/", "candidate": "Tania Fernández Sánchez"},
    {"platform": "instagram", "url": "https://www.instagram.com/hepelaez/", "candidate": "Henry Peláez Cifuentes"},
    {"platform": "instagram", "url": "https://www.instagram.com/soycarlospinilla/", "candidate": "Carlos Hernando Pinilla Malo"},
    {"platform": "instagram", "url": "https://www.instagram.com/fabioalonsoarroyave/", "candidate": "Fabio Alonso Arroyave Botero"},
    {"platform": "instagram", "url": "https://www.instagram.com/james10agudelo/", "candidate": "James Junior Agudelo Arevalo"},
    {"platform": "instagram", "url": "https://www.instagram.com/flowerojas/", "candidate": "Flower Enrique Rojas Torres"},
    {"platform": "instagram", "url": "https://www.instagram.com/rodrisalazarco/", "candidate": "Rodrigo Salazar Sarmiento"},
    {"platform": "instagram", "url": "https://www.instagram.com/carlospatinomoya/", "candidate": "Carlos Ariel Patiño"},
    # Prensa (nov-2025): renunció a la curul para asumir como representante a la Cámara -- puede
    # que ya no sea concejal activa. Confirmar si sigue vigente en el Concejo de Cali o si hay que
    # actualizar la lista COUNCILORS con su reemplazo.
    {"platform": "instagram", "url": "https://www.instagram.com/anaerazor/", "candidate": "Ana Leidy Erazo Ruiz"},
    # OJO: registros oficiales del Concejo lo nombran "Salazar Guapacha", no "Salazar Monsalve"
    # (mismo nombre/apellido, mismo perfil -- ingeniero, Pacto Histórico, curul desde nov-2024 por
    # fallo del Consejo de Estado). Confirmar el segundo apellido antes de confiar del todo.
    {"platform": "instagram", "url": "https://www.instagram.com/luisfernandosalazarg/", "candidate": "Luis Fernando Salazar"},
    {"platform": "x", "url": "https://x.com/MariaCconcejala", "candidate": "María del Carmen Londoño"},
    {"platform": "instagram", "url": "https://www.instagram.com/andresescobar2030/", "candidate": "Rafael Andrés Escobar González"},
    {"platform": "instagram", "url": "https://www.instagram.com/juanfmurgueitio/", "candidate": "Juan Felipe Murgueitio"},
    {"platform": "instagram", "url": "https://www.instagram.com/edisonlucumilucumi/", "candidate": "Edison Lucumi Lucumi"},
    {"platform": "instagram", "url": "https://www.instagram.com/alexahernandezcedeno/", "candidate": "Alexandra Hernández Cedeño"},
    {"platform": "instagram", "url": "https://www.instagram.com/marloncubillos_/", "candidate": "Marlon Andrés Cubillos Borrero"},
    {"platform": "instagram", "url": "https://www.instagram.com/ladaniplaza/", "candidate": "Daniela Plaza Saldarriaga"},
    {"platform": "instagram", "url": "https://www.instagram.com/edison_concejal/", "candidate": "Edison Alberto Giraldo Hoyos"},
]
# Presupuesto: plan gratuito de Bright Data (5.000 registros/mes). Consumo estimado con estos topes y
# 10 cuentas: ~1.200 registros/mes (solo posts nuevos + comentarios de los posts más comentados).
SOCIAL_WINDOW_DAYS = int(os.environ.get("SOCIAL_WINDOW_DAYS", "60"))     # se traen TODOS los posts de esta ventana
SOCIAL_MAX_POSTS = int(os.environ.get("SOCIAL_MAX_POSTS", "40"))          # tope por cuenta y corrida
SOCIAL_MAX_COMMENTS = int(os.environ.get("SOCIAL_MAX_COMMENTS", "30"))    # tope de comentarios por post
SOCIAL_COMMENT_POSTS = int(os.environ.get("SOCIAL_COMMENT_POSTS", "4"))   # posts por corrida a los que se piden comentarios
BRIGHTDATA_MONTHLY_CREDITS = int(os.environ.get("BRIGHTDATA_MONTHLY_CREDITS", "4000"))  # freno duro (plan: 5.000)

# Apify (X con respuestas): USD 5/mes gratis ≈ 12.000 tuits a USD 0,40/1.000.
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")
APIFY_MONTHLY_ITEMS = int(os.environ.get("APIFY_MONTHLY_ITEMS", "10000"))

# Concejo de Cali 2024-2027 (fuente: concejodecali.gov.co, publicación 60414).
# Carlos Arias y Roberto Ortiz también son concejales, pero van en CANDIDATES (son candidatos);
# el seed los marca con council=True. Alias: variantes sin tilde y forma corta con apellido.
COUNCILORS = [
    {"name": "Audry María Toro Echavarría", "party": "Partido de la U", "aliases": ["Audry Toro", "Audry Maria Toro"]},
    {"name": "Tania Fernández Sánchez", "party": "Partido de la U", "aliases": ["Tania Fernandez Sanchez", "Tania Fernández"]},
    {"name": "Henry Peláez Cifuentes", "party": "Partido de la U", "aliases": ["Henry Pelaez", "Henry Peláez"]},
    {"name": "Carlos Hernando Pinilla Malo", "party": "Partido Liberal", "aliases": ["Carlos Pinilla", "Carlos Hernando Pinilla"]},
    {"name": "Fabio Alonso Arroyave Botero", "party": "Partido Liberal", "aliases": ["Fabio Arroyave", "Fabio Alonso Arroyave"]},
    {"name": "James Junior Agudelo Arevalo", "party": "Partido Liberal", "aliases": ["James Agudelo", "Junior Agudelo"]},
    {"name": "Flower Enrique Rojas Torres", "party": "Alianza Verde", "aliases": ["Flower Rojas", "Flower Enrique Rojas"]},
    {"name": "Rodrigo Salazar Sarmiento", "party": "Alianza Verde", "aliases": ["Rodrigo Salazar"]},
    # Sin el alias corto "Carlos Patiño": así se llama una disidencia armada del Cauca y contamina todo.
    {"name": "Carlos Ariel Patiño", "party": "Alianza Verde", "aliases": ["Carlos Ariel Patino", "concejal Patiño"],
     "exclusions": ["Frente Carlos Patiño", "Frente Carlos Patino", "Columna Móvil Carlos Patiño",
                    "estructura Carlos Patiño", "Iván Mordisco", "disidencias de las Farc"]},
    {"name": "Ana Leidy Erazo Ruiz", "party": "Pacto Histórico", "aliases": ["Ana Erazo", "Ana Leidy Erazo"]},
    {"name": "Luis Fernando Salazar", "party": "Pacto Histórico", "aliases": ["Luis Fernando Salazar Monsalve"]},
    {"name": "María del Carmen Londoño", "party": "Pacto Histórico", "aliases": ["Maria del Carmen Londoño", "Carmen Londoño"]},
    {"name": "Rafael Andrés Escobar González", "party": "Centro Democrático", "aliases": ["Rafael Escobar", "Rafael Andrés Escobar"]},
    {"name": "Juan Felipe Murgueitio", "party": "Centro Democrático", "aliases": ["Felipe Murgueitio"]},
    {"name": "Edison Lucumi Lucumi", "party": "Cambio Radical", "aliases": ["Edison Lucumi"]},
    {"name": "Alexandra Hernández Cedeño", "party": "Cambio Radical", "aliases": ["Alexandra Hernandez Cedeño", "Alexandra Hernández"]},
    {"name": "Marlon Andrés Cubillos Borrero", "party": "Partido Conservador", "aliases": ["Marlon Cubillos", "Marlon Andrés Cubillos"]},
    {"name": "Daniela Plaza Saldarriaga", "party": "Colombia Renaciente", "aliases": ["Daniela Plaza"]},
    {"name": "Edison Alberto Giraldo Hoyos", "party": "Cali nos une", "aliases": ["Edison Giraldo", "Edison Alberto Giraldo"]},
]
# Concejales que además son candidatos (viven en CANDIDATES; aquí solo su partido en el Concejo).
COUNCIL_ALSO_CANDIDATES = {"Carlos Arias": "Partido de la U", "Roberto Ortiz": "Estatuto de Oposición"}
# Los concejales tienen nombres comunes: solo cuentan menciones con contexto local.
COUNCIL_CONTEXT = ["Cali", "Concejo"]

# Conversación de la ciudad (pestaña Ciudad): lo que no nombra a un candidato en estas fuentes
# se atribuye al candidato especial "Cali (ciudad)".
CITY_SOURCES = [
    {"type": "google_news", "name": "Google News Cali", "config": {"city": True, "terms": ["Cali"], "context": ""}},
    {"type": "youtube", "name": "YouTube Cali", "config": {"city": True, "terms": ["Cali noticias", "Cali hoy"], "context": ""}},
]

# Feeds RSS directos de medios — verificados el 2026-09-19 (todos responden 200 con entradas).
# "city": True → feed local: todo lo que no nombre a un candidato es conversación de Cali.
# Feeds nacionales (Caracol, Semana) solo aportan lo que nombre a un candidato.
RSS_SOURCES = [
    {"name": "El País Cali", "url": "https://www.elpais.com.co/arc/outboundfeeds/rss/category/cali/?outputType=xml", "city": True},
    {"name": "El Tiempo Cali", "url": "https://www.eltiempo.com/rss/colombia_cali.xml", "city": True},
    {"name": "Caracol Radio", "url": "https://caracol.com.co/arc/outboundfeeds/rss/?outputType=xml", "city": False},
    {"name": "Q'hubo Cali", "url": "https://www.qhubocali.com/feed/", "city": True},
    {"name": "Caliescribe", "url": "https://caliescribe.com/feed/", "city": True},
    {"name": "90 Minutos", "url": "https://90minutos.co/feed/", "city": True},
    {"name": "Semana", "url": "https://www.semana.com/arc/outboundfeeds/rss/?outputType=xml", "city": False},
    # Añadidas 2026-09-25 a pedido del cliente; feed verificado con curl (RSS 2.0 real, no una página de error).
    {"name": "Diario Occidente", "url": "https://occidente.co/feed/", "city": True},
    {"name": "Tu Barco", "url": "https://tubarco.news/feed/", "city": True},
    {"name": "Radio Reloj Cali", "url": "https://radiorelojcali.com/feed/", "city": True},
    {"name": "El Valluno Medios", "url": "https://elvalluno.com/feed/", "city": True},
    {"name": "La FM", "url": "https://www.lafm.com.co/rss/actualidad.xml", "city": False},  # nacional, no local de Cali
]
