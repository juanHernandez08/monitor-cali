import logging
import threading
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src import queries
from src.db import SessionLocal, init_db
from src.scheduler import run_everything, start_scheduler
from scripts.seed_sources import seed

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
                 days: int = Query(30, ge=1, le=365), limit: int = Query(60, le=300), offset: int = 0,
                 day: str | None = None):
        with session() as s:
            return queries.feed(s, candidate_id=candidate_id, source_type=source_type, label=label,
                                emotion=emotion, category=category, days=days, limit=limit, offset=offset, day=day)

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
