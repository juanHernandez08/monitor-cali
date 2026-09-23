import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///monitor.db")

# Sentimiento: "ollama" (local, gratis) o "claude" (requiere ANTHROPIC_API_KEY)
SENTIMENT_BACKEND = os.environ.get("SENTIMENT_BACKEND", "ollama")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:14b")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")

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
            "Pastor Carlos Arias", "Carlos Miguel Arias", "Juan Carlos Arias",
        ],
    },
    {
        "name": "Alfredo Mondragón", "party": "Pacto Histórico",
        "aliases": ["Alfredo Mondragon"],
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
        "name": "Francia Márquez", "party": "Pacto Histórico",
        "aliases": ["Francia Marquez", "Francia Elena Márquez"],
    },
    {
        "name": "Carlos Paz", "party": None,  # afiliación no confirmada en prensa
        "aliases": [],
    },
    {
        "name": "Roger Mina", "party": None,  # gerente de Emcali; afiliación no confirmada
        "aliases": [],
    },
    {
        "name": "Irene Vélez", "party": "Pacto Histórico",
        "aliases": ["Irene Velez", "Irene Vélez Torres"],
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
    {"name": "Carlos Ariel Patiño", "party": "Alianza Verde", "aliases": ["Carlos Patiño", "Carlos Patino"],
     # "Frente Carlos Patiño" es una disidencia armada del Cauca, no el concejal.
     "exclusions": ["Frente Carlos Patiño", "Columna Móvil Carlos Patiño", "Frente Carlos Patino"]},
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
]
