"""Backfill único: trae publicaciones viejas de Instagram/Facebook que quedaron fuera de la
ventana normal de captura.

Por diseño, `SocialApifyConnector`/`scheduler._social_state` solo miran HACIA ADELANTE desde la
última publicación ya guardada por cuenta (`known_last_dates`), para no re-pagar en cada corrida
lo que ya se tiene. Eso significa que un hueco en la captura inicial (p. ej. el conector arrancó
tarde, o la primera corrida no alcanzó a traer todo) nunca se corrige solo -- hay que forzar una
ventana más ancha una vez. Caso real 2026-09-26: el reel con más vistas de Carlos Arias
("¿Trincheras en Cali?") nunca se capturó porque la primera corrida (2026-09-20, todavía con
Bright Data) no lo trajo, y desde que se migró a Apify (2026-09-25) el conector ya solo mira
publicaciones más nuevas que la última conocida.

Este script ignora `known_last_dates` (fuerza `window_days` completo desde hoy) pero SÍ respeta
`known_post_ids`, así que no duplica lo que ya está guardado -- solo trae lo que faltaba.
Consume créditos de Apify reales (autorizado por el cliente 2026-09-26); no correrlo por rutina.

    python -m scripts.backfill_social_history
"""
import logging

from src import config
from src.connectors.social_apify import SocialApifyConnector
from src.db import get_session, init_db
from src.models import Source, SourceType
from src.pipeline import ingest
from src.scheduler import _social_state
from src.connectors.google_cse import QuotaTracker

log = logging.getLogger(__name__)

BACKFILL_WINDOW_DAYS = 180
BACKFILL_MAX_POSTS = 60


def run(session, token: str) -> int:
    source = session.query(Source).filter_by(type=SourceType.SOCIAL).first()
    if source is None:
        print("No hay fuente SOCIAL configurada (corre scripts/seed_sources.py primero).")
        return 0
    known, pending, _last_dates, post_texts = _social_state(session, source)
    ig_fb_accounts = [a for a in config.SOCIAL_ACCOUNTS if a["platform"] != "x"]
    if not ig_fb_accounts:
        print("No hay cuentas de Instagram/Facebook configuradas.")
        return 0
    import datetime as dt
    month = dt.datetime.utcnow().strftime("%Y-%m")
    credits = QuotaTracker(session, "apify", config.APIFY_MONTHLY_ITEMS, today=month)
    connector = SocialApifyConnector(
        token=token, accounts=ig_fb_accounts, window_days=BACKFILL_WINDOW_DAYS, max_posts=BACKFILL_MAX_POSTS,
        max_comments=config.SOCIAL_MAX_COMMENTS, comment_posts=config.SOCIAL_COMMENT_POSTS,
        known_post_ids=known, pending_comment_posts=pending, known_last_dates={}, credits=credits,
    )
    n = ingest(session, source, connector)
    from src.scheduler import mark_comments_fetched
    mark_comments_fetched(session, connector)
    return n


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    import os
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        print("Falta APIFY_TOKEN en el entorno.")
    else:
        init_db()
        with get_session() as s:
            n = run(s, token)
        print(f"listo: {n} publicaciones/comentarios nuevos traídos")
