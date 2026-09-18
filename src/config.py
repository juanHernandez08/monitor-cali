import os

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///monitor.db")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
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

# Fuentes RSS iniciales — verificar la URL real del feed de cada medio antes de correr
RSS_SOURCES = [
    {"name": "El País Cali", "url": "https://www.elpais.com.co/rss/cali.xml"},
    {"name": "El Tiempo Cali", "url": "https://www.eltiempo.com/rss/colombia_cali.xml"},
]
