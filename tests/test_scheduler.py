from src.models import Source, SourceType
from src.scheduler import build_connector, run_group, run_everything
from src.connectors.google_news import GoogleNewsConnector
from src.connectors.reddit_rss import RedditRSSConnector
from src.connectors.news_rss import RSSConnector


def test_build_connector_by_type(db_session, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_ID", raising=False)
    assert isinstance(build_connector(Source(type=SourceType.GOOGLE_NEWS, name="g"), db_session), GoogleNewsConnector)
    assert isinstance(build_connector(Source(type=SourceType.RSS, name="r", config={"feed_url": "x"}), db_session), RSSConnector)
    assert isinstance(build_connector(Source(type=SourceType.REDDIT, name="rd", config={"via": "rss"}), db_session), RedditRSSConnector)
    assert build_connector(Source(type=SourceType.GOOGLE_CSE, name="c", config={}), db_session) is None  # sin key


def test_run_group_skips_sources_without_connector(db_session, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_ID", raising=False)
    db_session.add(Source(type=SourceType.GOOGLE_CSE, name="c", config={}))
    db_session.commit()
    import src.scheduler as m
    monkeypatch.setattr(m, "ingest", lambda s, src, conn: 99)
    assert run_group(db_session, [SourceType.GOOGLE_CSE]) == {}


def test_run_group_runs_sources_concurrently_not_one_at_a_time(db_session, monkeypatch):
    """Pedido del cliente 2026-09-26: "Actualizar ahora" se demoraba mucho -- cada fuente (más de
    una decena de feeds de RSS/Google News) esperaba su propia respuesta de red una por una. Aquí
    no importa el conector real: basta con que 3 fuentes "lentas" (cada una tarda 0.3s) terminen
    en bloque en mucho menos que la suma secuencial (0.9s)."""
    import time
    for i in range(3):
        db_session.add(Source(type=SourceType.RSS, name=f"feed{i}", config={"feed_url": f"https://x/{i}"}))
    db_session.commit()
    import src.scheduler as m

    def slow_ingest(s, src, conn):
        time.sleep(0.3)
        return 1

    monkeypatch.setattr(m, "ingest", slow_ingest)
    t0 = time.time()
    results = run_group(db_session, [SourceType.RSS])
    elapsed = time.time() - t0
    assert results == {"feed0": 1, "feed1": 1, "feed2": 1}
    assert elapsed < 0.7  # en paralelo; en serie tomaría >= 0.9s


def test_run_everything_runs_the_four_groups_concurrently(monkeypatch):
    """Mismo pedido: run_everything() encadenaba job_fast, job_cse, job_youtube y job_social uno
    tras otro -- son independientes (cada uno abre su propia sesión), así que también deben
    correr en paralelo."""
    import time
    import src.scheduler as m

    def slow_job():
        time.sleep(0.2)

    for name in ("job_fast", "job_cse", "job_youtube", "job_social"):
        monkeypatch.setattr(m, name, slow_job)
    t0 = time.time()
    run_everything()
    elapsed = time.time() - t0
    assert elapsed < 0.5  # en paralelo; en serie tomaría >= 0.8s


def test_social_connector_gets_known_posts_pending_comments_and_marks_attempted(db_session, monkeypatch):
    import datetime as dt
    from src.models import Candidate, Mention
    import src.scheduler as m
    monkeypatch.setenv("BRIGHTDATA_API_TOKEN", "t")
    monkeypatch.setattr(m.config, "SOCIAL_ACCOUNTS", [{"platform": "instagram", "url": "https://www.instagram.com/x/", "candidate": "Carlos Arias"}])
    c = Candidate(name="Carlos Arias", aliases=[])
    src = Source(type=SourceType.SOCIAL, name="IG")
    db_session.add_all([c, src])
    db_session.commit()
    now = dt.datetime.utcnow()
    db_session.add(Mention(candidate_id=c.id, source_id=src.id, external_id="ig:post:p1", text="Trincheras en Cali", url="https://www.instagram.com/p/T/",
                           raw={"kind": "post", "account": "https://www.instagram.com/x/", "num_comments": "300", "record": {"post_id": "p1"}}, published_at=now, fetched_at=now))
    db_session.add(Mention(candidate_id=c.id, source_id=src.id, external_id="ig:post:p2", text="ya con comentarios", url="https://www.instagram.com/p/D/",
                           raw={"kind": "post", "account": "https://www.instagram.com/x/", "num_comments": "5", "comments_fetched": True, "record": {"post_id": "p2"}}, published_at=now, fetched_at=now))
    db_session.commit()

    conn = build_connector(src, db_session).connectors[0]  # Combined → Bright Data
    assert conn.known_post_ids == {"https://www.instagram.com/x/": ["p1", "p2"]}
    assert [p["url"] for p in conn.pending_comment_posts] == ["https://www.instagram.com/p/T/"]
    assert conn.pending_comment_posts[0]["title"] == "Trincheras en Cali" and conn.pending_comment_posts[0]["candidate"] == "Carlos Arias"
    assert conn.credits.remaining() > 0

    conn.comments_attempted = {"https://www.instagram.com/p/T/"}
    m.mark_comments_fetched(db_session, conn)
    assert db_session.query(Mention).filter_by(external_id="ig:post:p1").one().raw["comments_fetched"] is True


def test_city_sources_use_their_own_terms(db_session, monkeypatch):
    from src.scheduler import build_connector
    gn = Source(type=SourceType.GOOGLE_NEWS, name="Google News Cali", config={"city": True, "terms": ["Cali"], "context": ""})
    conn = build_connector(gn, db_session)
    captured = {}

    class Inner:
        def fetch(self, terms): captured["terms"] = terms; return []
    conn.inner = Inner()
    conn.fetch(["Carlos Arias", "Roberto Ortiz"])
    assert captured["terms"] == ["Cali"]


def _fake_apify_balance(monkeypatch, used=5.0, cap=19.0, end="2026-10-28"):
    """Los tests no deben llamar a Apify de verdad: el presupuesto lee el saldo de su API."""
    import datetime as dt
    from src import apify_budget
    monkeypatch.setattr(apify_budget, "fetch_status", lambda token, timeout=20: apify_budget.Status(
        used=used, cap=cap, cycle_start=dt.date(2026, 9, 29), cycle_end=dt.date.fromisoformat(end)))


def test_social_connector_routes_everything_to_apify_when_token_present(db_session, monkeypatch):
    """Con token de Apify, IG/FB/X van todos por Apify y Bright Data no se usa (créditos agotados
    el 2026-09-25): un solo proveedor, más simple y sin gastar lo que ya no existe."""
    import src.scheduler as m
    from src.connectors.x_apify import XApifyConnector
    from src.connectors.social_apify import SocialApifyConnector
    monkeypatch.setenv("BRIGHTDATA_API_TOKEN", "t")
    monkeypatch.setenv("APIFY_TOKEN", "a")
    monkeypatch.setattr(m.config, "SOCIAL_ACCOUNTS", [
        {"platform": "instagram", "url": "https://www.instagram.com/x/", "candidate": "Carlos Arias"},
        {"platform": "x", "url": "https://x.com/x", "candidate": "Carlos Arias"}])
    _fake_apify_balance(monkeypatch)
    src = Source(type=SourceType.SOCIAL, name="IG")
    db_session.add(src)
    db_session.commit()
    conn = build_connector(src, db_session)
    kinds = {type(c).__name__ for c in conn.connectors}
    assert kinds == {"SocialApifyConnector", "XApifyConnector"}
    ig = next(c for c in conn.connectors if isinstance(c, SocialApifyConnector))
    assert all(a["platform"] != "x" for a in ig.accounts)
    assert next(c for c in conn.connectors if isinstance(c, XApifyConnector)).accounts[0]["url"] == "https://x.com/x"


def test_social_connector_falls_back_to_brightdata_without_apify_token(db_session, monkeypatch):
    import src.scheduler as m
    from src.connectors.social_accounts import SocialAccountConnector
    monkeypatch.setenv("BRIGHTDATA_API_TOKEN", "t")
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    monkeypatch.setattr(m.config, "SOCIAL_ACCOUNTS", [
        {"platform": "instagram", "url": "https://www.instagram.com/x/", "candidate": "Carlos Arias"}])
    src = Source(type=SourceType.SOCIAL, name="IG")
    db_session.add(src)
    db_session.commit()
    conn = build_connector(src, db_session)
    kinds = {type(c).__name__ for c in conn.connectors}
    assert kinds == {"SocialAccountConnector"}


def test_next_run_fires_soon_when_a_restart_would_otherwise_postpone_it(db_session):
    """Un reinicio del servidor no debe posponer un job de intervalo largo (Bright Data, YouTube)
    otras 12h completas si ya estaba vencido: debe salir a correr pronto (~ahora), no reiniciar
    la cuenta regresiva desde cero."""
    import datetime as dt
    from src.scheduler import _next_run, SOCIAL_GROUP
    from src.models import Run

    src = Source(type=SourceType.SOCIAL, name="IG")
    db_session.add(src)
    db_session.commit()
    overdue = dt.datetime.utcnow() - dt.timedelta(hours=20)  # última corrida hace 20h, intervalo es 12h
    db_session.add(Run(source_id=src.id, started_at=overdue, finished_at=overdue))
    db_session.commit()

    due = _next_run(db_session, SOCIAL_GROUP, dt.timedelta(hours=12))
    now = dt.datetime.now(dt.timezone.utc)
    assert due <= now + dt.timedelta(seconds=5)  # vencido: debe salir ya, no esperar otras 12h


def test_next_run_respects_a_recent_run(db_session):
    import datetime as dt
    from src.scheduler import _next_run, YT_GROUP
    from src.models import Run

    src = Source(type=SourceType.YOUTUBE, name="YT")
    db_session.add(src)
    db_session.commit()
    recent = dt.datetime.utcnow() - dt.timedelta(hours=1)  # corrió hace 1h, intervalo 12h
    db_session.add(Run(source_id=src.id, started_at=recent, finished_at=recent))
    db_session.commit()

    due = _next_run(db_session, YT_GROUP, dt.timedelta(hours=12))
    now = dt.datetime.now(dt.timezone.utc)
    # debe faltar todavía cerca de 11h, no "ya" ni las 12h completas desde ahora
    assert dt.timedelta(hours=10) < (due - now) < dt.timedelta(hours=12)


def test_next_run_with_no_history_runs_now(db_session):
    import datetime as dt
    from src.scheduler import _next_run, CSE_GROUP

    due = _next_run(db_session, CSE_GROUP, dt.timedelta(hours=8))
    now = dt.datetime.now(dt.timezone.utc)
    assert due <= now + dt.timedelta(seconds=5)
