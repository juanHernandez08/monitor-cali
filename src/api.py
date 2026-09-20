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

log = logging.getLogger(__name__)
BASE = Path(__file__).parent


def create_app(session_factory=None, start_jobs: bool = True) -> FastAPI:
    factory = session_factory or SessionLocal
    owns_session = session_factory is None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        sched = None
        if start_jobs:
            init_db()
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
        return templates.TemplateResponse(request, "dashboard.html", {})

    @app.get("/api/summary")
    def api_summary(days: int = Query(7, ge=1, le=90)):
        with session() as s:
            return queries.summary(s, days=days)

    @app.get("/api/timeline")
    def api_timeline(days: int = Query(7, ge=1, le=90)):
        with session() as s:
            return queries.timeline(s, days=days)

    @app.get("/api/mentions")
    def api_mentions(candidate_id: int | None = None, source_type: str | None = None,
                     label: str | None = None, days: int = Query(30, ge=1, le=365),
                     limit: int = Query(100, le=500), offset: int = 0):
        with session() as s:
            return queries.mentions(s, candidate_id=candidate_id, source_type=source_type,
                                    label=label, days=days, limit=limit, offset=offset)

    @app.get("/api/alerts")
    def api_alerts(days: int = Query(30, ge=1, le=365)):
        with session() as s:
            return queries.alerts(s, days=days)

    @app.get("/api/topics")
    def api_topics(days: int = Query(7, ge=1, le=90)):
        with session() as s:
            return queries.topics(s, days=days)

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
