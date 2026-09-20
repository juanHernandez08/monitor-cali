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
]
SOCIAL_MAX_POSTS = int(os.environ.get("SOCIAL_MAX_POSTS", "5"))
SOCIAL_MAX_COMMENTS = int(os.environ.get("SOCIAL_MAX_COMMENTS", "25"))
SOCIAL_COMMENT_POSTS = int(os.environ.get("SOCIAL_COMMENT_POSTS", "3"))

# Feeds RSS directos de medios — verificados el 2026-09-19 (todos responden 200 con entradas).
RSS_SOURCES = [
    {"name": "El País Cali", "url": "https://www.elpais.com.co/arc/outboundfeeds/rss/category/cali/?outputType=xml"},
    {"name": "El Tiempo Cali", "url": "https://www.eltiempo.com/rss/colombia_cali.xml"},
    {"name": "Caracol Radio", "url": "https://caracol.com.co/arc/outboundfeeds/rss/?outputType=xml"},
    {"name": "Q'hubo Cali", "url": "https://www.qhubocali.com/feed/"},
    {"name": "Caliescribe", "url": "https://caliescribe.com/feed/"},
    {"name": "90 Minutos", "url": "https://90minutos.co/feed/"},
    {"name": "Semana", "url": "https://www.semana.com/arc/outboundfeeds/rss/?outputType=xml"},
]
