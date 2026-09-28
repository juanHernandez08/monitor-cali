import base64
import logging
import secrets
import threading
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src import config, queries
from src.connectors.social_apify import investigate_profile
from src.db import SessionLocal, init_db
from src.report import build_report, generate_and_store, report_to_pdf
from src.scheduler import run_everything, start_scheduler
from scripts.seed_sources import seed

INVESTIGATE_HOSTS = ("instagram.com", "facebook.com")

log = logging.getLogger(__name__)
BASE = Path(__file__).parent


def _asset_version() -> int:
    """Cambia cuando cambia algún archivo estático: evita que el navegador use JS/CSS viejo."""
    return int(max(f.stat().st_mtime for f in (BASE / "static").iterdir()))


def create_app(session_factory=None, start_jobs: bool = True) -> FastAPI:
    factory = session_factory or SessionLocal
    owns_session = session_factory is None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        sched = None
        if start_jobs:
            init_db()
            with SessionLocal() as s:
                seed(s)  # config.py es la fuente de verdad de candidatos y fuentes
            sched = start_scheduler()
        yield
        if sched:
            sched.shutdown(wait=False)

    app = FastAPI(title="Monitor Alcaldía de Cali 2027", lifespan=lifespan)

    @app.middleware("http")
    async def require_auth(request: Request, call_next):
        """Login HTTP Basic delante de TODO (API y estáticos incluidos) -- sin esto, cualquiera
        con la URL en la nube ve menciones, análisis de sentimiento y estrategia de campaña sin
        ninguna barrera. Sin DASHBOARD_PASSWORD configurada, no hace nada (desarrollo local)."""
        if not config.DASHBOARD_PASSWORD:
            return await call_next(request)
        header = request.headers.get("authorization", "")
        valid = False
        if header.startswith("Basic "):
            try:
                user, _, pwd = base64.b64decode(header[6:]).decode("utf-8").partition(":")
                valid = (secrets.compare_digest(user, config.DASHBOARD_USER or "")
                         and secrets.compare_digest(pwd, config.DASHBOARD_PASSWORD))
            except Exception:
                valid = False
        if not valid:
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Monitor Cali"'})
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
    templates = Jinja2Templates(directory=BASE / "templates")

    @contextmanager
    def session():
        s = factory()
        try:
            yield s
        finally:
            if owns_session:
                s.close()

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        return templates.TemplateResponse(request, "dashboard.html", {"v": _asset_version()})

    @app.get("/api/summary")
    def api_summary(days: int = Query(7, ge=1, le=365)):
        with session() as s:
            return queries.summary(s, days=days)

    @app.get("/api/timeline")
    def api_timeline(days: int = Query(7, ge=1, le=365)):
        with session() as s:
            return queries.timeline(s, days=days)

    @app.get("/api/mentions")
    def api_mentions(candidate_id: int | None = None, source_type: str | None = None,
                     label: str | None = None, days: int = Query(30, ge=1, le=365),
                     limit: int = Query(100, le=500), offset: int = 0):
        with session() as s:
            return queries.mentions(s, candidate_id=candidate_id, source_type=source_type,
                                    label=label, days=days, limit=limit, offset=offset)

    @app.get("/api/feed")
    def api_feed(candidate_id: int | None = None, source_type: str | None = None,
                 label: str | None = None, emotion: str | None = None, category: str | None = None,
                 city: bool = False, days: int = Query(30, ge=1, le=365), limit: int = Query(60, le=300),
                 offset: int = 0, day: str | None = None):
        with session() as s:
            return queries.feed(s, candidate_id=candidate_id, source_type=source_type, label=label,
                                emotion=emotion, category=category, city=city, days=days, limit=limit,
                                offset=offset, day=day)

    @app.get("/api/timeline/details")
    def api_timeline_details(days: int = Query(7, ge=1, le=365)):
        with session() as s:
            return queries.timeline_details(s, days=days)

    @app.get("/api/social/posts")
    def api_social_posts(candidate_id: int | None = None, platform: str | None = None, sort: str = "engagement",
                         days: int = Query(30, ge=1, le=365), limit: int = Query(200, le=500)):
        with session() as s:
            return queries.social_posts(s, days=days, candidate_id=candidate_id, platform=platform, sort=sort, limit=limit)

    @app.get("/api/social/kpis")
    def api_social_kpis(days: int = Query(30, ge=1, le=365)):
        with session() as s:
            return queries.social_kpis(s, days=days)

    @app.get("/api/social/candidates")
    def api_social_candidates():
        with session() as s:
            return queries.social_candidates(s)

    @app.get("/api/social/strong")
    def api_social_strong(days: int = Query(7, ge=1, le=90)):
        with session() as s:
            return queries.social_strong_posts(s, days=days)

    @app.get("/api/investigate")
    def api_investigate(url: str, platform: str = "instagram"):
        from urllib.parse import urlparse
        if platform not in ("instagram", "facebook"):
            return JSONResponse({"error": "plataforma no soportada"}, status_code=400)
        host = (urlparse(url).hostname or "").removeprefix("www.")
        if host not in INVESTIGATE_HOSTS:
            return JSONResponse({"error": "la URL debe ser de instagram.com o facebook.com"}, status_code=400)
        if not config.APIFY_TOKEN:
            return JSONResponse({"error": "falta APIFY_TOKEN en el servidor"}, status_code=400)
        posts = investigate_profile(config.APIFY_TOKEN, url, platform)
        total_likes = sum(p["likes"] for p in posts)
        total_comments = sum(p["comments"] for p in posts)
        total_views = sum(p["views"] for p in posts)
        return {
            "url": url, "platform": platform, "total_posts": len(posts),
            "total_likes": total_likes, "total_comments": total_comments, "total_views": total_views,
            "avg_engagement": round((total_likes + total_comments) / len(posts)) if posts else 0,
            "top_post": max(posts, key=lambda p: p["engagement"]) if posts else None,
            "posts": posts,
        }

    @app.get("/api/alerts")
    def api_alerts(days: int = Query(30, ge=1, le=365)):
        with session() as s:
            return queries.alerts(s, days=days)

    @app.get("/api/sources")
    def api_sources(days: int = Query(30, ge=1, le=365)):
        with session() as s:
            return queries.sources_by_candidate(s, days=days)

    @app.get("/api/topics")
    def api_topics(days: int = Query(7, ge=1, le=365), kind: str | None = None):
        with session() as s:
            return queries.topics(s, days=days, kind=kind)

    @app.get("/api/peak")
    def api_peak(candidate: str, day: str):
        with session() as s:
            return queries.peak_publication(s, candidate, day) or {}

    @app.get("/api/city/topics")
    def api_city_topics(days: int = Query(7, ge=1, le=365)):
        with session() as s:
            return queries.city_topics(s, days=days)

    @app.get("/api/city/emotions")
    def api_city_emotions(days: int = Query(7, ge=1, le=365)):
        with session() as s:
            return queries.city_emotions(s, days=days, samples_per=3)

    @app.get("/api/city/emotion-by-topic")
    def api_city_emotion_by_topic(days: int = Query(7, ge=1, le=365)):
        with session() as s:
            return queries.city_emotion_by_topic(s, days=days)

    @app.get("/api/city/opportunities")
    def api_city_opportunities(days: int = Query(7, ge=1, le=365)):
        with session() as s:
            return queries.city_opportunities(s, days=days)

    @app.get("/api/council")
    def api_council(days: int = Query(30, ge=1, le=365)):
        with session() as s:
            return queries.council_overview(s, days=days)

    @app.get("/api/agenda")
    def api_agenda(days: int = Query(30, ge=1, le=365)):
        with session() as s:
            return queries.agenda(s, days=days)

    @app.get("/api/perception")
    def api_perception(days: int = Query(30, ge=1, le=365)):
        with session() as s:
            return queries.citizen_perception(s, days=days)

    @app.get("/api/candidate/topics")
    def api_candidate_topics(name: str, days: int = Query(30, ge=1, le=365)):
        with session() as s:
            return queries.candidate_topic_map(s, name, days=days)

    @app.get("/api/city/kpis")
    def api_city_kpis(days: int = Query(7, ge=1, le=365)):
        with session() as s:
            return queries.city_kpis(s, days=days)

    @app.get("/api/institutional-history")
    def api_institutional_history():
        from src.institutional_history import ADMINISTRATIONS, debt_timeline, status_counts
        return {
            "administrations": [{**a, "status_counts": status_counts(a)} for a in ADMINISTRATIONS],
            "debt_timeline": debt_timeline(),
        }

    @app.get("/api/reports")
    def api_reports_list():
        from src.models import Report
        with session() as s:
            rows = s.query(Report).order_by(Report.date.desc()).limit(30).all()
            return [{"date": r.date, "generated_at": r.generated_at.isoformat()} for r in rows]

    @app.get("/api/reports/latest")
    def api_reports_latest():
        from src.models import Report
        with session() as s:
            r = s.query(Report).order_by(Report.date.desc()).first()
            return r.data if r else None

    @app.get("/api/reports/{date}")
    def api_reports_get(date: str):
        from src.models import Report
        with session() as s:
            r = s.query(Report).filter_by(date=date).first()
            if r is None:
                return JSONResponse({"error": "no hay reporte para esa fecha"}, status_code=404)
            return r.data

    @app.post("/api/reports/generate")
    def api_reports_generate():
        with session() as s:
            r = generate_and_store(s)
            return r.data

    @app.get("/api/reports/{date}/pdf")
    def api_reports_pdf(date: str):
        from src.models import Report
        with session() as s:
            r = s.query(Report).filter_by(date=date).first()
            data = r.data if r else build_report(s, date=date)
        pdf = report_to_pdf(data)
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="reporte-{date}.pdf"'})

    @app.get("/health")
    def health():
        with session() as s:
            return queries.status(s)

    @app.post("/api/refresh", status_code=202)
    def refresh():
        threading.Thread(target=run_everything, daemon=True).start()
        return JSONResponse({"status": "started"}, status_code=202)

    return app


app = create_app()
