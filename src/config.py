import os

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///monitor.db")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
BRIGHTDATA_API_TOKEN = os.environ.get("BRIGHTDATA_API_TOKEN")

# Candidatos a monitorear — actualizar con la lista oficial de inscritos
CANDIDATES = [
    {
        "name": "Carlos Arias", "party": "Partido de la U",
        "aliases": ["Carlos Andrés Arias Rueda", "@soycarlosaarias", "Buenos Ciudadanos"],
    },
    {"name": "Ana Pérez", "party": "Partido X", "aliases": []},
    {"name": "Luis Gómez", "party": "Partido Y", "aliases": []},
]

# Fuentes RSS iniciales — verificar la URL real del feed de cada medio antes de correr
RSS_SOURCES = [
    {"name": "El País Cali", "url": "https://www.elpais.com.co/rss/cali.xml"},
    {"name": "El Tiempo Cali", "url": "https://www.eltiempo.com/rss/colombia_cali.xml"},
]
