import logging
import threading
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Literal

from fastapi import Body, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src import config, queries, security
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


SOURCE_TYPES = Literal["google_news", "rss", "reddit", "youtube", "social", "google_cse", "serp", "radio"]
FEED_SOURCE_TYPES = Literal["prensa", "google_news", "rss", "reddit", "youtube", "social", "google_cse", "serp", "radio"]
LABELS = Literal["positive", "negative", "neutral"]


def _bad_request(msg: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=status)


def create_app(session_factory=None, start_jobs: bool = True, cf_verifier=None) -> FastAPI:
    factory = session_factory or SessionLocal
    owns_session = session_factory is None
    if cf_verifier is None and config.CF_ACCESS_TEAM_DOMAIN and config.CF_ACCESS_AUD:
        cf_verifier = security.CloudflareAccessVerifier(config.CF_ACCESS_TEAM_DOMAIN, config.CF_ACCESS_AUD)
    mode = security.auth_mode(config.DASHBOARD_PASSWORD, cf_verifier)
    if mode == "abierto":
        log.warning("SIN AUTENTICACIÓN: el dashboard y las acciones que gastan dinero quedan abiertos a "
                    "quien llegue al puerto. Configurar DASHBOARD_PASSWORD o Cloudflare Access (ver "
                    "docs/auditoria/01-seguridad.md).")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        sched = None
        if start_jobs:
            init_db()
            with SessionLocal() as s:
                seed(s)  # config.py es la fuente de verdad de candidatos y fuentes
            # RUN_SCHEDULER=0 levanta solo la web: permite más de un proceso web (o un worker
            # aparte) sin duplicar la captura ni el gasto en Apify/YouTube.
            if config.RUN_SCHEDULER:
                sched = start_scheduler()
            else:
                log.info("RUN_SCHEDULER=0: este proceso solo sirve el dashboard")
        yield
        if sched:
            sched.shutdown(wait=False)

    docs = config.ENABLE_API_DOCS
    app = FastAPI(title="Monitor Alcaldía de Cali 2027", lifespan=lifespan,
                  docs_url="/docs" if docs else None, redoc_url=None, openapi_url="/openapi.json" if docs else None)

    @app.middleware("http")
    async def require_auth(request: Request, call_next):
        """Autenticación delante de TODO (API y estáticos). Con Cloudflare Access configurado se
        exige su token firmado; con DASHBOARD_PASSWORD, HTTP Basic. Si hay ambos, alcanza con
        cualquiera de los dos (el equipo entra por Access; un script o curl, con Basic). Sin
        ninguno queda abierto, como en desarrollo local, y se avisa en el log al arrancar."""
        # Se evalúa en cada petición (no solo al arrancar) para respetar cambios de configuración.
        current = security.auth_mode(config.DASHBOARD_PASSWORD, cf_verifier)
        if current == "abierto" or request.url.path in security.PUBLIC_PATHS:
            return await call_next(request)
        if cf_verifier and cf_verifier.verify(request.headers.get("cf-access-jwt-assertion")):
            return await call_next(request)
        if security.basic_auth_ok(request.headers.get("authorization", ""), config.DASHBOARD_USER,
                                  config.DASHBOARD_PASSWORD):
            return await call_next(request)
        headers = {"WWW-Authenticate": 'Basic realm="Monitor Cali"'} if config.DASHBOARD_PASSWORD else {}
        return Response(status_code=401, headers=headers)

    @app.middleware("http")
    async def csrf_guard(request: Request, call_next):
        """Un POST solo vale si lo manda el propio dashboard: sin esto, cualquier página que el
        usuario abra (con su sesión o su Basic auth guardados en el navegador) podría disparar
        "Actualizar ahora" o consultas pagas de Apify con un formulario oculto."""
        if not security.csrf_ok(request.method, request.headers, request.headers.get("host")):
            return JSONResponse({"error": "petición rechazada (CSRF)"}, status_code=403)
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = security.CSP
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if request.url.path.startswith("/api/") or request.url.path == "/health":
            response.headers["Cache-Control"] = "no-store"  # datos de campaña: nada en cachés intermedias
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
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
    def api_mentions(candidate_id: int | None = None, source_type: SOURCE_TYPES | None = None,
                     label: LABELS | None = None, days: int = Query(30, ge=1, le=365),
                     limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
        with session() as s:
            return queries.mentions(s, candidate_id=candidate_id, source_type=source_type,
                                    label=label, days=days, limit=limit, offset=offset)

    @app.get("/api/feed")
    def api_feed(candidate_id: int | None = None, source_type: FEED_SOURCE_TYPES | None = None,
                 label: LABELS | None = None, emotion: str | None = Query(None, max_length=40),
                 category: str | None = Query(None, max_length=60),
                 city: bool = False, days: int = Query(30, ge=1, le=365), limit: int = Query(60, ge=1, le=300),
                 offset: int = Query(0, ge=0), day: str | None = None, week: str | None = None):
        if day is not None and not security.valid_date(day):
            return _bad_request("day debe ser YYYY-MM-DD")
        if week is not None and not security.valid_week(week):
            return _bad_request("week debe ser YYYY-Sww")
        with session() as s:
            return queries.feed(s, candidate_id=candidate_id, source_type=source_type, label=label,
                                emotion=emotion, category=category, city=city, days=days, limit=limit,
                                offset=offset, day=day, week=week)

    @app.get("/api/timeline/details")
    def api_timeline_details(days: int = Query(7, ge=1, le=365)):
        with session() as s:
            return queries.timeline_details(s, days=days)

    @app.get("/api/social/posts")
    def api_social_posts(candidate_id: int | None = None, platform: Literal["instagram", "facebook", "x"] | None = None,
                         sort: Literal["engagement", "views", "recent"] = "engagement",
                         days: int = Query(30, ge=1, le=365), limit: int = Query(200, ge=1, le=500)):
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

    @app.get("/api/social/reach")
    def api_social_reach(days: int = Query(30, ge=1, le=365)):
        with session() as s:
            return queries.candidate_reach_comparison(s, days=days)

    @app.get("/api/social/insights")
    def api_social_insights(days: int = Query(90, ge=7, le=365), candidate: str = Query("Carlos Arias", max_length=120)):
        with session() as s:
            return queries.social_insights(s, days=days, candidate=candidate)

    @app.get("/api/conversation/weekly")
    def api_conversation_weekly(days: int = Query(90, ge=14, le=365), candidate: str = Query("Carlos Arias", max_length=120)):
        with session() as s:
            return queries.weekly_conversation(s, days=days, candidate=candidate)

    @app.get("/api/social/reaction")
    def api_social_reaction(days: int = Query(30, ge=1, le=365)):
        with session() as s:
            return queries.candidate_comment_reaction(s, days=days)

    @app.post("/api/investigate")
    def api_investigate(payload: dict = Body(...)):
        """POST (no GET): cada consulta gasta créditos de Apify, así que no debe poder dispararse
        con un simple enlace o una etiqueta <img>. Además corre de a una y con espera mínima."""
        from urllib.parse import urlparse
        url = str(payload.get("url") or "").strip()[:300]
        platform = payload.get("platform") or "instagram"
        if platform not in ("instagram", "facebook"):
            return _bad_request("plataforma no soportada")
        parsed = urlparse(url)
        host = (parsed.hostname or "").removeprefix("www.").removeprefix("m.")
        if parsed.scheme != "https" or host not in INVESTIGATE_HOSTS:
            return _bad_request("la URL debe ser https de instagram.com o facebook.com")
        if not config.APIFY_TOKEN:
            return _bad_request("falta APIFY_TOKEN en el servidor")
        ok, why = security.THROTTLE.try_start("investigate", config.INVESTIGATE_MIN_INTERVAL)
        if not ok:
            return _bad_request(f"consulta no iniciada: {why}", status=429)
        try:
            posts = investigate_profile(config.APIFY_TOKEN, url, platform)
        finally:
            security.THROTTLE.finish("investigate")
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
    def api_topics(days: int = Query(7, ge=1, le=365), kind: Literal["publications", "comments"] | None = None):
        with session() as s:
            return queries.topics(s, days=days, kind=kind)

    @app.get("/api/peak")
    def api_peak(candidate: str = Query(..., max_length=120), day: str = Query(...)):
        if not security.valid_date(day):
            return _bad_request("day debe ser YYYY-MM-DD")
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
    def api_candidate_topics(name: str = Query(..., max_length=120), days: int = Query(30, ge=1, le=365)):
        with session() as s:
            return queries.candidate_topic_map(s, name, days=days)

    @app.get("/api/candidate/emotions")
    def api_candidate_emotions(days: int = Query(30, ge=1, le=365)):
        with session() as s:
            return queries.candidate_emotions(s, days=days)

    @app.get("/api/city/kpis")
    def api_city_kpis(days: int = Query(7, ge=1, le=365)):
        with session() as s:
            return queries.city_kpis(s, days=days)

    @app.get("/api/institutional-history")
    def api_institutional_history():
        from src.institutional_history import ADMINISTRATIONS, debt_timeline, needs_verification, status_counts

        def flag(item):
            return {**item, "source": {**item["source"], "verify": needs_verification(item["source"])}} if item.get("source") else item

        return {
            "administrations": [{**a, "status_counts": status_counts(a),
                                 "metrics": [flag(m) for m in a.get("metrics", [])],
                                 "projects": [flag(p) for p in a.get("projects", [])],
                                 "debt": flag(a["debt"]) if a.get("debt") else None} for a in ADMINISTRATIONS],
            "debt_timeline": debt_timeline(),
        }

    @app.get("/api/city-history")
    def api_city_history():
        from src.city_history import payload
        return payload()

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
        if not security.valid_date(date):
            return _bad_request("fecha inválida (YYYY-MM-DD)")
        with session() as s:
            r = s.query(Report).filter_by(date=date).first()
            if r is None:
                return JSONResponse({"error": "no hay reporte para esa fecha"}, status_code=404)
            return r.data

    @app.post("/api/reports/generate")
    def api_reports_generate():
        ok, why = security.THROTTLE.try_start("report", config.REPORT_MIN_INTERVAL)
        if not ok:
            return _bad_request(f"reporte no generado: {why}", status=429)
        try:
            with session() as s:
                r = generate_and_store(s)
                return r.data
        finally:
            security.THROTTLE.finish("report")

    @app.get("/api/reports/{date}/pdf")
    def api_reports_pdf(date: str):
        from src.models import Report
        if not security.valid_date(date):
            return _bad_request("fecha inválida (YYYY-MM-DD)")
        with session() as s:
            r = s.query(Report).filter_by(date=date).first()
            data = r.data if r else build_report(s, date=date)
        pdf = report_to_pdf(data)
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="reporte-{date}.pdf"'})

    @app.get("/healthz")
    def healthz():
        """Público y mínimo: solo confirma que el proceso responde (Docker, deploy.sh)."""
        return {"ok": True}

    @app.get("/health")
    def health():
        with session() as s:
            return queries.status(s)

    @app.post("/api/refresh", status_code=202)
    def refresh():
        ok, why = security.THROTTLE.try_start("refresh", config.REFRESH_MIN_INTERVAL)
        if not ok:
            return JSONResponse({"status": "skipped", "reason": why}, status_code=429)

        def _run():
            try:
                run_everything()
            finally:
                security.THROTTLE.finish("refresh")

        threading.Thread(target=_run, daemon=True).start()
        return JSONResponse({"status": "started"}, status_code=202)

    return app


app = create_app()
