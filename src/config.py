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
        "aliases": [
            "Carlos Andrés Arias Rueda", "Carlos Andres Arias", "Carlos Andrés Arias",
            "@soycarlosaarias", "Buenos Ciudadanos",
        ],
    },
    {
        "name": "Alfredo Mondragón", "party": "Pacto Histórico",
        "aliases": ["Alfredo Mondragon"],
    },
    {
        "name": "Roberto Ortiz", "party": None,  # independiente; hoy concejal de Cali
        "aliases": ["Roberto Ortiz Urueña", "Roberto Ortiz Uruena", "Chontico"],
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

# Feeds RSS directos de medios locales — se verifican en Task 12; los que no respondan se quitan.
RSS_SOURCES = [
    {"name": "El País Cali", "url": "https://www.elpais.com.co/rss/cali.xml"},
    {"name": "El Tiempo Cali", "url": "https://www.eltiempo.com/rss/colombia_cali.xml"},
    {"name": "Caracol Radio Cali", "url": "https://caracol.com.co/emisora/cali/rss/"},
    {"name": "Blu Radio Cali", "url": "https://www.bluradio.com/rss/cali"},
    {"name": "Q'hubo Cali", "url": "https://www.qhubocali.com/feed/"},
    {"name": "Caliescribe", "url": "https://caliescribe.com/feed/"},
]
