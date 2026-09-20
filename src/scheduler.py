import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from src import config
from src.connectors.google_cse import GoogleCSEConnector, QuotaTracker
from src.connectors.google_news import GoogleNewsConnector
from src.connectors.news_rss import RSSConnector
from src.connectors.reddit_rss import RedditRSSConnector
from src.connectors.social_accounts import SocialAccountConnector
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


def build_connector(source: Source, session):
    """Devuelve el conector para una fuente, o None si faltan credenciales."""
    google_key = os.environ.get("GOOGLE_API_KEY")
    cfg = source.config or {}
    if source.type == SourceType.GOOGLE_NEWS:
        return GoogleNewsConnector()
    if source.type == SourceType.RSS:
        return RSSConnector(feed_url=cfg["feed_url"])
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
        return YouTubeConnector(api_key=google_key) if google_key else None
    if source.type == SourceType.SOCIAL:
        token = os.environ.get("BRIGHTDATA_API_TOKEN")
        if not (token and config.SOCIAL_ACCOUNTS):
            return None
        return SocialAccountConnector(api_token=token, accounts=config.SOCIAL_ACCOUNTS,
                                      max_posts=config.SOCIAL_MAX_POSTS, max_comments=config.SOCIAL_MAX_COMMENTS,
                                      comment_posts=config.SOCIAL_COMMENT_POSTS)
    if source.type == SourceType.SERP and os.environ.get("BRIGHTDATA_API_TOKEN"):
        from src.connectors.serp import SerpConnector
        return SerpConnector(api_token=os.environ["BRIGHTDATA_API_TOKEN"], site=cfg.get("site"))
    return None


def run_group(session, types: list[SourceType]) -> dict[str, int]:
    results: dict[str, int] = {}
    for source in session.query(Source).filter(Source.type.in_(types)).all():
        connector = build_connector(source, session)
        if connector is None:
            log.info("fuente %s sin credenciales; se omite", source.name)
            continue
        results[source.name] = ingest(session, source, connector)
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
    # Bright Data: ~800 créditos por corrida, 5.000/mes gratis → cada 5 días
    sched.add_job(job_social, "interval", days=5, id="social", max_instances=1, coalesce=True)
    sched.add_job(job_score, "interval", minutes=2, id="score", max_instances=1, coalesce=True)
    sched.start()
    return sched
