import datetime as dt

from src.connectors.base import RawItem
from src.models import Candidate, Source, SourceType, Mention, SentimentScore, SentimentLabel
from src.pipeline import ingest, score_pending, CITY_NAME
from src.sentiment import _parse_payload, CATEGORIES, SentimentResult


class ListConnector:
    def __init__(self, items): self.items = items
    def fetch(self, terms): return self.items


def test_parse_payload_reads_category_and_falls_back_to_otro():
    r = _parse_payload('{"label":"negative","score":-0.5,"topic":"agua en Terrón","category":"servicios públicos"}', "m")
    assert r.category == "servicios públicos"
    r2 = _parse_payload('{"label":"neutral","score":0,"topic":"x","category":"cosa rara"}', "m")
    assert r2.category == "otro"
    assert "seguridad" in CATEGORIES and "otro" in CATEGORIES


def test_city_source_items_without_candidate_go_to_city_and_with_candidate_to_candidate(db_session):
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    carlos = Candidate(name="Carlos Arias", aliases=[])
    feed = Source(type=SourceType.RSS, name="El País Cali", config={"feed_url": "x", "city": True})
    other = Source(type=SourceType.GOOGLE_NEWS, name="Google News", config={})
    db_session.add_all([city, carlos, feed, other])
    db_session.commit()
    n = ingest(db_session, feed, ListConnector([
        RawItem(external_id="a", text="Cortes de agua en Cali este lunes", url="https://x/a"),
        RawItem(external_id="b", text="Carlos Arias pide plan de choque", url="https://x/b"),
    ]))
    assert n == 2
    assert db_session.query(Mention).filter_by(external_id="a").one().candidate.name == CITY_NAME
    assert db_session.query(Mention).filter_by(external_id="b").one().candidate.name == "Carlos Arias"
    # una fuente que no es de ciudad sigue descartando lo que no nombra a nadie
    assert ingest(db_session, other, ListConnector([RawItem(external_id="c", text="Clima en Cali", url="https://x/c")])) == 0


def test_city_items_are_scored_with_city_prompt_and_store_category(db_session):
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    feed = Source(type=SourceType.RSS, name="Q'hubo", config={"feed_url": "x", "city": True})
    db_session.add_all([city, feed])
    db_session.commit()
    ingest(db_session, feed, ListConnector([RawItem(external_id="a", text="Vecinos protestan por falta de agua", url="https://x/a")]))

    class Engine:
        def __init__(self): self.calls = []
        def score(self, text, candidate=None, city=False):
            self.calls.append((candidate, city))
            return SentimentResult(SentimentLabel.NEGATIVE, -0.6, "agua", "f", category="servicios públicos")

    e = Engine()
    assert score_pending(db_session, e, limit=10) == 1
    assert e.calls == [(CITY_NAME, True)]
    sc = db_session.query(SentimentScore).one()
    assert sc.category == "servicios públicos" and sc.label == SentimentLabel.NEGATIVE


def _seed_city(db_session):
    from src.queries import summary
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    carlos = Candidate(name="Carlos Arias", aliases=[])
    feed = Source(type=SourceType.RSS, name="Q'hubo", config={"feed_url": "x", "city": True})
    yt = Source(type=SourceType.YOUTUBE, name="YouTube Cali", config={"city": True})
    db_session.add_all([city, carlos, feed, yt])
    db_session.commit()
    now = dt.datetime.utcnow()
    rows = [
        # (candidato, ext, texto, fuente, categoría, topic, label, score, hace_días, raw)
        (city, "a", "Sin agua en Terrón", feed, "servicios públicos", "agua en terrón colorado", "negative", -0.7, 1, {}),
        (city, "b", "Otra vez sin agua", yt, "servicios públicos", "agua en terrón colorado", "negative", -0.9, 2, {"kind": "comment", "video_title": "Cali sin agua"}),
        (city, "c", "Emcali responde", feed, "servicios públicos", "emcali", "neutral", 0.0, 3, {}),
        (city, "d", "Feria de Cali confirmada", feed, "cultura y eventos", "feria de cali", "positive", 0.6, 1, {}),
        (city, "e", "Atracos en el MIO", feed, "seguridad", "atracos mio", "negative", -0.6, 2, {}),
        (city, "f", "Semana pasada: robos", feed, "seguridad", "robos", "negative", -0.5, 10, {}),  # período anterior
        (city, "g", "Semana pasada: más robos", feed, "seguridad", "robos", "negative", -0.5, 11, {}),
        (carlos, "h", "Carlos Arias anuncia plan de cultura", feed, "cultura y eventos", "plan cultura", "positive", 0.5, 1, {}),
        (carlos, "i", "Carlos Arias apoya la Feria", feed, "cultura y eventos", "feria", "positive", 0.4, 2, {}),
        (carlos, "j", "Carlos Arias en evento cultural", feed, "cultura y eventos", "evento", "positive", 0.3, 2, {}),
    ]
    for cand, ext, text, src, cat, topic, label, score, ago, raw in rows:
        when = now - dt.timedelta(days=ago)
        m = Mention(candidate_id=cand.id, source_id=src.id, external_id=ext, text=text, url=f"https://x/{ext}",
                    raw=raw, author="u", published_at=when, fetched_at=when)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel(label), score=score, topic=topic, model="f", category=cat))
    db_session.commit()
    return city, carlos


def test_city_is_excluded_from_candidate_views(db_session):
    from src.queries import summary, timeline, sources_by_candidate, feed
    _seed_city(db_session)
    assert [r["name"] for r in summary(db_session, days=7)] == ["Carlos Arias"]
    assert [s["name"] for s in timeline(db_session, days=7)["series"]] == ["Carlos Arias"]
    assert sources_by_candidate(db_session, days=7)["candidates"] == ["Carlos Arias"]
    assert all(r["candidate"] == "Carlos Arias" for r in feed(db_session, days=7))


def test_city_topics_with_trend_perception_subtopics_and_samples(db_session):
    from src.queries import city_topics
    _seed_city(db_session)
    rows = {r["category"]: r for r in city_topics(db_session, days=7)}
    sp = rows["servicios públicos"]
    assert sp["count"] == 3 and sp["previous"] == 0 and sp["negative"] == 2 and sp["neutral"] == 1
    assert sp["subtopics"][0] == {"topic": "agua en terrón colorado", "count": 2}
    assert sp["samples"][0]["text"] == "Otra vez sin agua" and sp["samples"][0]["url"] == "https://x/b"
    sec = rows["seguridad"]
    assert sec["count"] == 1 and sec["previous"] == 2 and sec["trend_pct"] == -50
    assert "cultura y eventos" in rows and "Carlos Arias" not in str(rows)  # solo ciudad


def test_city_opportunities_carlos_strong_topics(db_session):
    from src.queries import city_opportunities
    _seed_city(db_session)
    o = city_opportunities(db_session, days=7)
    strong = [x["category"] for x in o["carlos_strong"]]
    assert strong == ["cultura y eventos"]  # 3 menciones positivas de Carlos


def test_city_opportunities_surfaces_new_or_rising_topics_regardless_of_tone(db_session):
    """Feedback del cliente 2026-09-26: antes "oportunidades" solo mostraba temas con molestia
    alta (>=40% negativo). Pidió que sea cualquier novedad donde Carlos pueda hablar -- sea o no
    negativa -- como un evento urgente/emergente (ej. la llegada de una figura nacional a Cali,
    que es informativa/positiva, no una queja)."""
    from src.queries import city_opportunities
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    carlos = Candidate(name="Carlos Arias", aliases=[])
    feed = Source(type=SourceType.RSS, name="Q'hubo", config={"feed_url": "x", "city": True})
    db_session.add_all([city, carlos, feed])
    db_session.commit()
    now = dt.datetime.utcnow()
    rows = [
        # tema totalmente nuevo (sin menciones en el período anterior), tono positivo/informativo
        (city, "a", "Llega figura nacional a Cali", "política y elecciones", "visita de figura nacional", "neutral", 0.0, 1),
        (city, "b", "Recibimiento multitudinario", "política y elecciones", "visita de figura nacional", "positive", 0.4, 1),
        (city, "c", "Agenda de la visita", "política y elecciones", "visita de figura nacional", "neutral", 0.1, 2),
        # tema con crecimiento fuerte (de 1 el período pasado a 3 ahora) -- también debe aparecer
        (city, "g", "Paro de transportadores anunciado", "movilidad y transporte", "paro transportadores", "negative", -0.4, 1),
        (city, "h", "Paro transportadores se extiende", "movilidad y transporte", "paro transportadores", "negative", -0.5, 2),
        (city, "i", "Paro transportadores tercer día", "movilidad y transporte", "paro transportadores", "negative", -0.6, 3),
        (city, "j", "Semana pasada: rumor de paro", "movilidad y transporte", "paro transportadores", "neutral", 0.0, 9),
        # tema viejo, sin crecimiento -- no debe aparecer
        (city, "d", "Bache en la 5ta", "infraestructura y obras", "baches", "negative", -0.3, 1),
        (city, "e", "Semana pasada: baches", "infraestructura y obras", "baches", "negative", -0.3, 8),
        (city, "f", "Semana pasada: más baches", "infraestructura y obras", "baches", "negative", -0.3, 9),
    ]
    for cand, ext, text, cat, topic, label, score, ago in rows:
        when = now - dt.timedelta(days=ago)
        m = Mention(candidate_id=cand.id, source_id=feed.id, external_id=ext, text=text, url=f"https://x/{ext}",
                    raw={}, author="u", published_at=when, fetched_at=when)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel(label), score=score, topic=topic, model="f", category=cat))
    db_session.commit()

    o = city_opportunities(db_session, days=7)
    novedades = {x["topic"]: x for x in o["novedades"]}
    assert "visita de figura nacional" in novedades  # nueva, aunque no sea negativa
    assert novedades["visita de figura nacional"]["is_new"] is True
    assert novedades["visita de figura nacional"]["carlos_mentions"] == 0
    assert "paro transportadores" in novedades  # en alza (de 1 a 3), aunque negativa
    assert novedades["paro transportadores"]["is_new"] is False
    assert novedades["paro transportadores"]["trend_pct"] == 200
    assert "baches" not in novedades  # sin crecimiento, no es novedad


def test_city_opportunities_excludes_sports_topics_from_novedades(db_session):
    """Feedback del cliente 2026-09-28: no sugerir que Carlos hable de partidos/equipos --
    fomenta rivalidad entre hinchas en vez de ayudarlo. "deporte" nunca debe salir en novedades,
    aunque sea un tema nuevo o en alza como cualquier otro."""
    from src.queries import city_opportunities
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    feed = Source(type=SourceType.RSS, name="Q'hubo", config={"feed_url": "x", "city": True})
    db_session.add_all([city, feed])
    db_session.commit()
    now = dt.datetime.utcnow()
    rows = [
        (city, "a", "Santa Fe vs Cali termina en polémica", "deporte", "santa fe vs cali", "negative", -0.3, 1),
        (city, "b", "Hinchas celebran el triunfo", "deporte", "santa fe vs cali", "positive", 0.5, 1),
        (city, "c", "Análisis del partido", "deporte", "santa fe vs cali", "neutral", 0.0, 1),
    ]
    for cand, ext, text, cat, topic, label, score, ago in rows:
        when = now - dt.timedelta(days=ago)
        m = Mention(candidate_id=cand.id, source_id=feed.id, external_id=ext, text=text, url=f"https://x/{ext}",
                    raw={}, author="u", published_at=when, fetched_at=when)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel(label), score=score, topic=topic, model="f", category=cat))
    db_session.commit()

    o = city_opportunities(db_session, days=7)
    assert "santa fe vs cali" not in {x["topic"] for x in o["novedades"]}


def test_city_opportunities_recognizes_carlos_presence_by_keywords_when_his_own_topic_label_differs(db_session):
    """Bug real (2026-09-28): un post de Carlos sobre la Operación Iron quedó clasificado con
    topic "seguridad" (demasiado genérico), no "Operación Iron" -- el emparejamiento por topic
    EXACTO nunca lo veía, así que la ciudad mostraba "Carlos: sin presencia" en un tema del que sí
    había hablado, con el texto completo nombrándolo. Ahora también se busca por palabras del
    tema dentro del texto/topic de sus menciones."""
    from src.queries import city_opportunities
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    carlos = Candidate(name="Carlos Arias", aliases=[])
    feed = Source(type=SourceType.RSS, name="Q'hubo", config={"feed_url": "x", "city": True})
    social = Source(type=SourceType.SOCIAL, name="Instagram / Facebook (cuentas)")
    db_session.add_all([city, carlos, feed, social])
    db_session.commit()
    now = dt.datetime.utcnow()
    rows = [
        (city, feed, "a", "Operación Iron captura a varios", "seguridad", "Operación Iron", "positive", 0.3, 1),
        (city, feed, "b", "Operación Iron se extiende", "seguridad", "Operación Iron", "positive", 0.4, 1),
        (city, feed, "c", "Balance de la Operación Iron", "seguridad", "Operación Iron", "neutral", 0.0, 1),
        (carlos, social, "d", "La seguridad se recupera con decisión. La Operación IRON marca un paso importante.",
         "seguridad", "seguridad", "positive", 0.6, 1),
    ]
    for cand, src, ext, text, cat, topic, label, score, ago in rows:
        when = now - dt.timedelta(days=ago)
        m = Mention(candidate_id=cand.id, source_id=src.id, external_id=ext, text=text, url=f"https://x/{ext}",
                    raw={}, author="u", published_at=when, fetched_at=when)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel(label), score=score, topic=topic, model="f", category=cat))
    db_session.commit()

    # Con el emparejamiento exacto anterior, carlos_mentions daba 0 aquí (el topic de Carlos era
    # "seguridad", no "Operación Iron") y el tema entraba a novedades como si él no hubiera
    # hablado. Con carlos_max=0 debe quedar afuera, porque su presencia real ahora sí se cuenta.
    o = city_opportunities(db_session, days=7, carlos_max=0)
    assert "operación iron" not in {x["topic"] for x in o["novedades"]}


def test_city_kpis(db_session):
    from src.queries import city_kpis
    _seed_city(db_session)
    k = city_kpis(db_session, days=7)
    assert k["total"] == 5 and k["top_category"] == "servicios públicos"
    assert k["negative_pct"] == 60  # 3 de 5 negativas
