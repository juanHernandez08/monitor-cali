import datetime as dt
import functools
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import sessionmaker

from src import apify_budget, config
from src.connectors.google_cse import GoogleCSEConnector, QuotaTracker
from src.models import Mention
from src.connectors.google_news import GoogleNewsConnector
from src.connectors.news_rss import RSSConnector
from src.connectors.reddit_rss import RedditRSSConnector
from src.connectors.social_accounts import SocialAccountConnector
from src.connectors.social_apify import SocialApifyConnector
from src.connectors.x_apify import XApifyConnector
from src.connectors.youtube import YouTubeConnector
from src.db import get_session
from src.enrich import enrich_pending
from src.models import Run, Source, SourceType
from src.pipeline import ingest, score_pending
from src.sentiment import build_sentiment_engine
from sqlalchemy import func

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
        self.finish = None  # callback opcional (session) al terminar la vuelta: contabilidad del presupuesto

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
        ig_fb_accounts = [a for a in config.SOCIAL_ACCOUNTS if a["platform"] != "x"]
        budget_run = None
        if apify:
            # Presupuesto en dólares: manda sobre todo lo demás (ver src/apify_budget.py). Si no se puede
            # comprobar el saldo o no toca vuelta todavía, no se gasta nada.
            budget_run = _apify_budget_run(session, source, apify, pending, last_dates)
            if budget_run is None:
                return None
            x_accounts = [a for a in budget_run["accounts"] if a["platform"] == "x"]
            ig_fb_accounts = [a for a in budget_run["accounts"] if a["platform"] != "x"]
        # Bright Data agotó sus créditos gratis el 2026-09-25 ("Customer is not active" en su
        # Marketplace); con token de Apify, Instagram/Facebook/X van por ahí. Bright Data queda
        # como respaldo solo si no hay token de Apify.
        apify_credits = (budget_run["spend"] if budget_run else
                         (QuotaTracker(session, "apify", config.APIFY_MONTHLY_ITEMS, today=month) if apify else None))
        if apify and x_accounts:
            # Con presupuesto en dólares, una cuenta de X sin historial NO trae 60 días de golpe (un backfill
            # llegó a costar USD 0,12 en una sola corrida) ni 200 respuestas por cuenta.
            connectors.append(XApifyConnector(token=apify, accounts=x_accounts,
                                              window_days=14 if budget_run else config.SOCIAL_WINDOW_DAYS,
                                              max_posts=30 if budget_run else 100, max_replies=60 if budget_run else 200,
                                              known_last_dates=last_dates, known_post_texts=post_texts,
                                              credits=apify_credits))
        if apify and ig_fb_accounts:
            connectors.append(SocialApifyConnector(
                token=apify, accounts=ig_fb_accounts, window_days=config.SOCIAL_WINDOW_DAYS, max_posts=config.SOCIAL_MAX_POSTS,
                max_comments=config.SOCIAL_MAX_COMMENTS,
                comment_posts=budget_run["comment_posts"] if budget_run else config.SOCIAL_COMMENT_POSTS,
                known_post_ids=known, pending_comment_posts=pending, known_last_dates=last_dates, credits=apify_credits,
                comment_only_for=budget_run["carlos"] if budget_run else None))
        elif token and ig_fb_accounts:
            connectors.append(SocialAccountConnector(
                api_token=token, accounts=ig_fb_accounts, window_days=config.SOCIAL_WINDOW_DAYS, max_posts=config.SOCIAL_MAX_POSTS,
                max_comments=config.SOCIAL_MAX_COMMENTS, comment_posts=config.SOCIAL_COMMENT_POSTS,
                known_post_ids=known, pending_comment_posts=pending, known_last_dates=last_dates,
                credits=QuotaTracker(session, "brightdata", config.BRIGHTDATA_MONTHLY_CREDITS, today=month)))
        if not connectors:
            return None
        combined = Combined(connectors)
        if budget_run:
            combined.finish = lambda s, b=budget_run: _finish_apify_job(s, b)
        return combined
    if source.type == SourceType.SERP and os.environ.get("BRIGHTDATA_API_TOKEN"):
        from src.connectors.serp import SerpConnector
        return SerpConnector(api_token=os.environ["BRIGHTDATA_API_TOKEN"], site=cfg.get("site"))
    return None


def _apify_budget_run(session, source: Source, token: str, pending: list[dict], last_dates: dict[str, str]) -> dict | None:
    """Decide si hay vuelta de redes y cuánto puede gastar. None = no gastar nada (y avisar si corresponde)."""
    from src import notify
    from src.models import Candidate
    from src.queries import CARLOS

    last = session.query(func.max(Run.started_at)).filter(Run.source_id == source.id).scalar()
    now = dt.datetime.utcnow()
    if last is not None and now - last < dt.timedelta(hours=config.SOCIAL_MIN_HOURS):
        log.info("social: la última vuelta fue hace %.1f h (mínimo %s h); no se gasta Apify", (now - last).total_seconds() / 3600,
                 config.SOCIAL_MIN_HOURS)
        return None
    plan, status = apify_budget.current_plan(token)
    if not plan.ok:
        log.warning("social: sin presupuesto Apify: %s", plan.reason)
        notify.notify_apify_blocked(session, plan.reason)
        return None
    kinds = {c.name: c.kind for c in session.query(Candidate)}
    accounts, comment_posts, est = apify_budget.select_accounts(
        config.SOCIAL_ACCOUNTS, kinds, last_dates, plan.job_budget, CARLOS, pending, config.SOCIAL_MAX_COMMENTS,
        include_media=config.SOCIAL_INCLUDE_MEDIA)
    if not accounts:
        log.warning("social: el presupuesto de la vuelta ($%.3f) no alcanza ni para una cuenta", plan.job_budget)
        return None
    log.info("social: presupuesto de la vuelta $%.3f (disponible $%.2f, %d días); %d cuentas, comentarios de %d post(s), estimado $%.3f",
             plan.job_budget, plan.available, plan.days_left, len(accounts), comment_posts, est)
    return {"plan": plan, "status": status, "accounts": accounts, "comment_posts": comment_posts, "estimate": est,
            "carlos": CARLOS, "spend": apify_budget.JobSpend(token, plan.job_budget, status.used)}


def _finish_apify_job(session, run: dict) -> None:
    """Cierra la vuelta: gasto real contra lo planeado, y aviso al soporte técnico."""
    from src import notify
    after = apify_budget.fetch_status(config.APIFY_TOKEN)
    plan = run["plan"]
    spent = max(0.0, after.used - run["status"].used) if after else None
    notify.notify_apify_job(session, plan, spent, run["estimate"], len(run["accounts"]), run["comment_posts"],
                            after.used if after else None)


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
        if m.published_at:  # también sirve a IG/FB por Apify, que no tiene "posts_to_not_include"
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
    """Corre cada fuente del grupo en paralelo. Antes era secuencial: con una decena de feeds de
    RSS/Google News, "Actualizar ahora" esperaba cada respuesta de red una por una sin motivo --
    ninguna fuente depende de otra. Cada hilo abre su propia sesión (una sesión de SQLAlchemy no
    es segura para compartir entre hilos) contra el mismo engine que `session`; el modo WAL
    (src/db.py) ya soporta varios escritores a la vez sin bloquearse."""
    source_ids_names = [(s.id, s.name) for s in session.query(Source).filter(Source.type.in_(types)).all()]
    if not source_ids_names:
        return {}

    ThreadSession = sessionmaker(bind=session.get_bind(), future=True)

    @contextmanager
    def _thread_session():
        s = ThreadSession()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    def _run(source_id: int) -> tuple[str, int | None]:
        with _thread_session() as s:
            source = s.query(Source).filter_by(id=source_id).one()
            connector = build_connector(source, s)
            if connector is None:
                log.info("fuente %s sin credenciales; se omite", source.name)
                return source.name, None
            n = ingest(s, source, connector)
            mark_comments_fetched(s, connector)
            finish = getattr(connector, "finish", None)
            if finish:
                try:
                    finish(s)
                except Exception:
                    log.exception("no se pudo cerrar la contabilidad de la vuelta de %s", source.name)
            return source.name, n

    results: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(source_ids_names))) as pool:
        futures = {pool.submit(_run, sid): name for sid, name in source_ids_names}
        for future in as_completed(futures):
            name = futures[future]
            try:
                fetched_name, n = future.result()
            except Exception:
                log.exception("fuente %s falló en paralelo", name)
                continue
            if n is not None:
                results[fetched_name] = n
    return results


_JOB_LOCKS: dict[str, threading.Lock] = {}


def exclusive(name: str):
    """Un mismo grupo nunca corre dos veces a la vez en este proceso. APScheduler ya evita que un
    job se solape consigo mismo (max_instances=1), pero "Actualizar ahora" (run_everything) corre
    por fuera del scheduler: sin este candado, un clic justo cuando arranca job_social duplicaba la
    consulta a Apify (y su costo) y podía guardar el mismo post dos veces en paralelo."""
    lock = _JOB_LOCKS.setdefault(name, threading.Lock())

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not lock.acquire(blocking=False):
                log.info("job %s ya está corriendo; se omite esta ejecución", name)
                return None
            try:
                return fn(*args, **kwargs)
            finally:
                lock.release()
        return wrapper
    return deco


@exclusive("fast")
def job_fast():
    with get_session() as s:
        log.info("fast: %s", run_group(s, FAST_GROUP))


@exclusive("cse")
def job_cse():
    with get_session() as s:
        log.info("cse: %s", run_group(s, CSE_GROUP))


@exclusive("youtube")
def job_youtube():
    with get_session() as s:
        log.info("youtube: %s", run_group(s, YT_GROUP))


@exclusive("social")
def job_social():
    with get_session() as s:
        log.info("social: %s", run_group(s, SOCIAL_GROUP))


@exclusive("daily_report")
def job_daily_report():
    from src.report import generate_and_store
    from src import notify
    with get_session() as s:
        r = generate_and_store(s)
        log.info("reporte diario generado: %s", r.date)
        notify.notify_daily_summary(r.data)


def _analyst_available() -> bool:
    """¿Responde la IA que redacta el análisis? Con Ollama (el PC del cliente por túnel) se comprueba antes de
    pedirle algo, para no llenar el registro de errores cada 10 minutos mientras está apagada."""
    if config.SENTIMENT_BACKEND != "ollama":
        return True
    import requests
    try:
        return requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5).ok
    except Exception:
        return False


@exclusive("report_narrative")
def job_report_narrative():
    """Completa el análisis narrativo de un reporte reciente que salió sin él (PC del cliente apagado a las 7 a. m.)."""
    from src.report import fill_missing_narrative
    from src import notify
    with get_session() as s:
        from src.models import Report
        cutoff = (dt.datetime.utcnow() - dt.timedelta(days=1)).strftime("%Y-%m-%d")
        latest = s.query(Report).filter(Report.date >= cutoff).order_by(Report.date.desc()).first()
        if latest is None or (latest.data or {}).get("narrative") or not _analyst_available():
            return
        done = fill_missing_narrative(s)
        if done:
            log.info("análisis narrativo completado para el reporte %s", done.date)
            notify.notify_daily_summary(done.data)


@exclusive("score")
def job_score():
    from src import notify
    engine = build_sentiment_engine()
    with get_session() as s:
        e = enrich_pending(s, limit=20)
        if e:
            log.info("enrich: %d procesadas", e)
        n = score_pending(s, engine, limit=20)
        if n:
            log.info("score: %d clasificadas", n)
        alerted = notify.check_negative_mentions(s)
        if alerted:
            log.info("notify: %d menciones negativas avisadas", alerted)


@exclusive("notify_social")
def job_notify_social():
    from src import notify
    with get_session() as s:
        n = notify.check_strong_posts(s)
        if n:
            log.info("notify: %d publicaciones fuertes avisadas", n)


@exclusive("notify_city")
def job_notify_city():
    from src import notify
    with get_session() as s:
        n = notify.check_city_trends(s)
        if n:
            log.info("notify: %d temas de ciudad avisados", n)


@exclusive("ollama_health")
def job_ollama_health():
    from src import notify
    with get_session() as s:
        notify.check_ollama_tunnel(s)


def run_everything():
    """Los 4 grupos son independientes (cada uno abre su propia sesión) -- correrlos uno tras
    otro solo suma tiempos de espera de red sin necesidad."""
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(job) for job in (job_fast, job_cse, job_youtube, job_social)]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                log.exception("un grupo de run_everything falló")


def _next_run(session, source_types: list[SourceType], interval: dt.timedelta) -> dt.datetime:
    """Cuándo debe salir a correr un job de intervalo largo, mirando la última corrida REAL en la
    base de datos en vez de contar desde que arrancó este proceso.

    Sin esto, cada reinicio del servidor (se cae, se actualiza código, se apaga el PC) reinicia la
    cuenta regresiva de 8h/12h desde cero. Si los reinicios son más frecuentes que el intervalo —como
    pasó el 2026-09-24, varios reinicios en un día tumbaron la captura de Bright Data— el job nunca
    llega a dispararse. Si ya venció, sale ya; si no, respeta lo que falta.
    """
    last = (
        session.query(func.max(Run.started_at))
        .join(Source, Source.id == Run.source_id)
        .filter(Source.type.in_(source_types))
        .scalar()
    )
    now = dt.datetime.now(dt.timezone.utc)
    if last is None:
        return now
    if last.tzinfo is None:
        last = last.replace(tzinfo=dt.timezone.utc)
    due = last + interval
    return due if due > now else now


def start_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="America/Bogota")
    with get_session() as s:
        cse_next = _next_run(s, CSE_GROUP, dt.timedelta(hours=8))
        yt_next = _next_run(s, YT_GROUP, dt.timedelta(hours=12))
        social_next = _next_run(s, SOCIAL_GROUP, dt.timedelta(hours=config.SOCIAL_INTERVAL_HOURS))
    sched.add_job(job_fast, "interval", minutes=15, id="fast", max_instances=1, coalesce=True)
    sched.add_job(job_cse, "interval", hours=8, id="cse", max_instances=1, coalesce=True, next_run_time=cse_next)
    sched.add_job(job_youtube, "interval", hours=12, id="youtube", max_instances=1, coalesce=True,  # cuota: ~3.000 unidades/corrida
                  next_run_time=yt_next)
    # Bright Data: solo se pagan posts nuevos y comentarios pendientes; el contador mensual frena en el tope.
    sched.add_job(job_social, "interval", hours=config.SOCIAL_INTERVAL_HOURS, id="social", max_instances=1, coalesce=True, next_run_time=social_next)
    sched.add_job(job_score, "interval", minutes=2, id="score", max_instances=1, coalesce=True)
    # Reporte diario, lunes a viernes -- el cliente lo revisa al llegar en la mañana.
    sched.add_job(job_daily_report, "cron", day_of_week="mon-fri", hour=7, minute=0,
                  id="daily_report", max_instances=1, coalesce=True)
    # Notificaciones (src/notify.py): actividad fuerte en redes cada 15 min, salud del túnel de
    # Ollama cada 10 min -- las menciones negativas se avisan dentro de job_score, justo al
    # clasificarlas.
    # El análisis del reporte lo redacta la IA del PC del cliente: si estaba apagado a las 7 a. m., se completa solo después.
    sched.add_job(job_report_narrative, "interval", minutes=10, id="report_narrative", max_instances=1, coalesce=True)
    sched.add_job(job_notify_social, "interval", minutes=15, id="notify_social", max_instances=1, coalesce=True)
    sched.add_job(job_notify_city, "interval", hours=1, id="notify_city", max_instances=1, coalesce=True)
    sched.add_job(job_ollama_health, "interval", minutes=10, id="ollama_health", max_instances=1, coalesce=True)
    sched.start()
    return sched
