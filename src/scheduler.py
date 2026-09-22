import datetime as dt
import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from src import config
from src.connectors.google_cse import GoogleCSEConnector, QuotaTracker
from src.models import Mention
from src.connectors.google_news import GoogleNewsConnector
from src.connectors.news_rss import RSSConnector
from src.connectors.reddit_rss import RedditRSSConnector
from src.connectors.social_accounts import SocialAccountConnector
from src.connectors.x_apify import XApifyConnector
from src.connectors.youtube import YouTubeConnector
from src.db import get_session
from src.enrich import enrich_pending
from src.models import Source, SourceType
from src.pipeline import ingest, score_pending
from src.sentiment import build_sentiment_engine

log = logging.getLogger(__name__)

FAST_GROUP = [SourceType.GOOGLE_NEWS, SourceType.RSS, SourceType.REDDIT]
CSE_GROUP = [SourceType.GOOGLE_CSE]
YT_GROUP = [SourceType.YOUTUBE]
SOCIAL_GROUP = [SourceType.SOCIAL]


class Combined:
    """Varios conectores para una misma fuente (p. ej. Bright Data para IG/FB + Apify para X)."""

    def __init__(self, connectors: list):
        self.connectors = [c for c in connectors if c is not None]
        self.source_name = "combined"

    def fetch(self, search_terms):
        items = []
        for c in self.connectors:
            try:
                items.extend(c.fetch(search_terms))
            except Exception:
                log.exception("conector %s falló", type(c).__name__)
        return items

    @property
    def comments_attempted(self) -> set:
        out: set = set()
        for c in self.connectors:
            out |= getattr(c, "comments_attempted", set())
        return out


class FixedTerms:
    """Envuelve un conector para que busque sus propios términos (fuentes de ciudad) y no los de los candidatos."""

    def __init__(self, inner, terms: list[str]):
        self.inner, self.terms = inner, terms
        self.source_name = getattr(inner, "source_name", "fixed")

    def fetch(self, search_terms):
        return self.inner.fetch(self.terms)


def build_connector(source: Source, session):
    """Devuelve el conector para una fuente, o None si faltan credenciales."""
    connector = _build(source, session)
    terms = (source.config or {}).get("terms")
    return FixedTerms(connector, terms) if (connector is not None and terms) else connector


def _build(source: Source, session):
    google_key = os.environ.get("GOOGLE_API_KEY")
    cfg = source.config or {}
    if source.type == SourceType.GOOGLE_NEWS:
        return GoogleNewsConnector(context=cfg["context"]) if "context" in cfg else GoogleNewsConnector()
    if source.type == SourceType.RSS:
        return RSSConnector(feed_url=cfg["feed_url"], filter_terms=not cfg.get("city"))
    if source.type == SourceType.REDDIT:
        if cfg.get("via") == "rss":
            return RedditRSSConnector()
        if os.environ.get("BRIGHTDATA_API_TOKEN"):
            from src.connectors.reddit import RedditConnector
            return RedditConnector(api_token=os.environ["BRIGHTDATA_API_TOKEN"])
        return None
    if source.type == SourceType.GOOGLE_CSE:
        cse_id = os.environ.get("GOOGLE_CSE_ID")
        if not (google_key and cse_id):
            return None
        quota = QuotaTracker(session, "google_cse", config.GOOGLE_CSE_DAILY_LIMIT)
        return GoogleCSEConnector(api_key=google_key, cse_id=cse_id, sites=config.CSE_SITES, quota=quota)
    if source.type == SourceType.YOUTUBE:
        if not google_key:
            return None
        return YouTubeConnector(api_key=google_key, context=cfg["context"]) if "context" in cfg else YouTubeConnector(api_key=google_key)
    if source.type == SourceType.SOCIAL:
        token = os.environ.get("BRIGHTDATA_API_TOKEN")
        apify = os.environ.get("APIFY_TOKEN")
        if not config.SOCIAL_ACCOUNTS or not (token or apify):
            return None
        known, pending, last_dates, post_texts = _social_state(session, source)
        month = dt.datetime.utcnow().strftime("%Y-%m")
        connectors = []
        x_accounts = [a for a in config.SOCIAL_ACCOUNTS if a["platform"] == "x"]
        if apify and x_accounts:  # X con respuestas de la gente; libera créditos de Bright Data
            connectors.append(XApifyConnector(token=apify, accounts=x_accounts, window_days=config.SOCIAL_WINDOW_DAYS,
                                              known_last_dates=last_dates, known_post_texts=post_texts,
                                              credits=QuotaTracker(session, "apify", config.APIFY_MONTHLY_ITEMS, today=month)))
        if token:
            accounts = [a for a in config.SOCIAL_ACCOUNTS if not (apify and a["platform"] == "x")]
            connectors.append(SocialAccountConnector(
                api_token=token, accounts=accounts, window_days=config.SOCIAL_WINDOW_DAYS, max_posts=config.SOCIAL_MAX_POSTS,
                max_comments=config.SOCIAL_MAX_COMMENTS, comment_posts=config.SOCIAL_COMMENT_POSTS,
                known_post_ids=known, pending_comment_posts=pending, known_last_dates=last_dates,
                credits=QuotaTracker(session, "brightdata", config.BRIGHTDATA_MONTHLY_CREDITS, today=month)))
        return Combined(connectors) if connectors else None
    if source.type == SourceType.SERP and os.environ.get("BRIGHTDATA_API_TOKEN"):
        from src.connectors.serp import SerpConnector
        return SerpConnector(api_token=os.environ["BRIGHTDATA_API_TOKEN"], site=cfg.get("site"))
    return None


def _social_state(session, source: Source) -> tuple[dict[str, list[str]], list[dict], dict[str, str], dict[str, str]]:
    """Posts ya guardados por cuenta (para no volver a pagarlos) y posts sin comentarios pedidos."""
    accounts = {a["url"]: a.get("candidate") for a in config.SOCIAL_ACCOUNTS}
    known: dict[str, list[str]] = {}
    last_dates: dict[str, str] = {}
    post_texts: dict[str, str] = {}
    pending: list[dict] = []
    for m in session.query(Mention).filter(Mention.source_id == source.id):
        raw = m.raw or {}
        if raw.get("kind") != "post":
            continue
        account = raw.get("account")
        post_id = (raw.get("record") or {}).get("post_id") or m.external_id.split(":")[-1]
        known.setdefault(account, []).append(post_id)
        if raw.get("platform") == "x":
            post_texts[post_id] = m.text
            if m.published_at:
                day = m.published_at.strftime("%Y-%m-%d")
                last_dates[account] = max(last_dates.get(account, ""), day)
        num = raw.get("num_comments")
        try:
            num = int(str(num).replace(",", "")) if num is not None else 0
        except ValueError:
            num = 0
        if m.url and num > 0 and not raw.get("comments_fetched") and raw.get("platform") != "x":  # X no tiene scraper de respuestas
            pending.append({"url": m.url, "platform": raw.get("platform"), "candidate": accounts.get(account),
                            "account": account, "title": m.text[:120], "num_comments": num})
    return known, pending, last_dates, post_texts


def mark_comments_fetched(session, connector) -> None:
    """Marca los posts cuyos comentarios ya se pidieron, para no volver a pagarlos."""
    attempted = getattr(connector, "comments_attempted", set())
    if not attempted:
        return
    for m in session.query(Mention).filter(Mention.url.in_(list(attempted))):
        raw = m.raw or {}
        if raw.get("kind") == "post":
            m.raw = {**raw, "comments_fetched": True}
    session.commit()


def run_group(session, types: list[SourceType]) -> dict[str, int]:
    results: dict[str, int] = {}
    for source in session.query(Source).filter(Source.type.in_(types)).all():
        connector = build_connector(source, session)
        if connector is None:
            log.info("fuente %s sin credenciales; se omite", source.name)
            continue
        results[source.name] = ingest(session, source, connector)
        mark_comments_fetched(session, connector)
    return results


def job_fast():
    with get_session() as s:
        log.info("fast: %s", run_group(s, FAST_GROUP))


def job_cse():
    with get_session() as s:
        log.info("cse: %s", run_group(s, CSE_GROUP))


def job_youtube():
    with get_session() as s:
        log.info("youtube: %s", run_group(s, YT_GROUP))


def job_social():
    with get_session() as s:
        log.info("social: %s", run_group(s, SOCIAL_GROUP))


def job_score():
    engine = build_sentiment_engine()
    with get_session() as s:
        e = enrich_pending(s, limit=20)
        if e:
            log.info("enrich: %d procesadas", e)
        n = score_pending(s, engine, limit=20)
        if n:
            log.info("score: %d clasificadas", n)


def run_everything():
    job_fast()
    job_cse()
    job_youtube()
    job_social()


def start_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="America/Bogota")
    sched.add_job(job_fast, "interval", minutes=15, id="fast", max_instances=1, coalesce=True)
    sched.add_job(job_cse, "interval", hours=8, id="cse", max_instances=1, coalesce=True)
    sched.add_job(job_youtube, "interval", hours=12, id="youtube", max_instances=1, coalesce=True)  # cuota: ~3.000 unidades/corrida
    # Bright Data: solo se pagan posts nuevos y comentarios pendientes; el contador mensual frena en el tope.
    sched.add_job(job_social, "interval", hours=12, id="social", max_instances=1, coalesce=True)
    sched.add_job(job_score, "interval", minutes=2, id="score", max_instances=1, coalesce=True)
    sched.start()
    return sched
