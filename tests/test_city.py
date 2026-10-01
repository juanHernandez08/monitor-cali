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
    assert "seguridad y convivencia" in CATEGORIES and "otro" in CATEGORIES


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


def test_city_source_discards_items_that_dont_name_the_city(db_session):
    """Un medio local/regional también publica notas de otros municipios o nacionales -- que la
    CUENTA sea de ciudad no basta, la nota misma debe nombrar a Cali (o "caleño/a") para contar
    como conversación de ciudad. Pedido del cliente 2026-10-01: "el filtro debe hacerlo en
    cualquier noticia que mencione a Cali" (antes entraba cualquier cosa sin candidato nombrado,
    incluida la cobertura de Buga, Tolima o noticias nacionales de medios con desk en Cali)."""
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    feed = Source(type=SourceType.RSS, name="90 Minutos", config={"feed_url": "x", "city": True})
    db_session.add_all([city, feed])
    db_session.commit()
    n = ingest(db_session, feed, ListConnector([
        RawItem(external_id="a", text="Feria de empleo en Buga: conoce cómo participar", url="https://x/a"),
        RawItem(external_id="b", text="Bruce Mac Master renuncia a la presidencia de la ANDI", url="https://x/b"),
        RawItem(external_id="c", text="Alcaldía de Cali abre convocatorias del Programa de Estímulos", url="https://x/c"),
        RawItem(external_id="d", text="Los caleños celebran el festival de música", url="https://x/d"),
    ]))
    assert n == 2
    kept = {m.external_id for m in db_session.query(Mention).all()}
    assert kept == {"c", "d"}


def test_city_source_comment_inherits_relevance_from_its_post_not_its_own_text(db_session):
    """Un comentario rara vez repite el nombre de la ciudad ("qué belleza", "bendiciones") aunque
    esté respondiendo a un post o video que sí es de Cali -- lo que decide es el post/video al que
    responde (raw.post_title / raw.video_title), no el texto suelto del comentario."""
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    social = Source(type=SourceType.SOCIAL, name="Instagram / Facebook (cuentas)", config={"city": True})
    db_session.add_all([city, social])
    db_session.commit()
    n = ingest(db_session, social, ListConnector([
        RawItem(external_id="a", text="qué belleza, bendiciones",
                raw={"kind": "comment", "post_title": "Alcaldía de Cali anuncia nueva obra"}, url="https://x/a"),
        RawItem(external_id="b", text="qué belleza, bendiciones",
                raw={"kind": "comment", "post_title": "Feria de empleo en Buga"}, url="https://x/b"),
    ]))
    assert n == 1
    assert db_session.query(Mention).one().external_id == "a"


def test_city_items_are_scored_with_city_prompt_and_store_category(db_session):
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    feed = Source(type=SourceType.RSS, name="Q'hubo", config={"feed_url": "x", "city": True})
    db_session.add_all([city, feed])
    db_session.commit()
    ingest(db_session, feed, ListConnector([RawItem(external_id="a", text="Vecinos de Cali protestan por falta de agua", url="https://x/a")]))

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


def test_city_topics_diversifies_samples_across_platforms(db_session):
    """Reporte del cliente 2026-10-01: "los comentarios que muestra, todos son de YouTube, lo que
    genera la duda si la lectura solo la hizo de YouTube" -- si YouTube tiene los comentarios con
    el puntaje mas intenso, las muestras ya no deben ser todas de esa misma plataforma cuando hay
    alternativas de otras redes para el mismo tema."""
    from src.queries import city_topics
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    yt = Source(type=SourceType.YOUTUBE, name="YouTube Cali", config={"city": True})
    ig = Source(type=SourceType.SOCIAL, name="Instagram (cuentas)")
    db_session.add_all([city, yt, ig])
    db_session.commit()
    now = dt.datetime.utcnow()
    # las 3 de YouTube tienen el score mas intenso -- sin diversificar, ganarian las 3 muestras
    rows = [
        (yt, "y1", -0.95, {"kind": "comment", "platform": "youtube"}),
        (yt, "y2", -0.90, {"kind": "comment", "platform": "youtube"}),
        (yt, "y3", -0.85, {"kind": "comment", "platform": "youtube"}),
        (ig, "i1", -0.40, {"kind": "comment", "platform": "instagram"}),
    ]
    for src, ext, score, raw in rows:
        m = Mention(candidate_id=city.id, source_id=src.id, external_id=ext, text=ext, url=f"https://x/{ext}",
                    raw=raw, author="u", published_at=now, fetched_at=now)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.NEGATIVE, score=score,
                                      topic="t", model="f", category="seguridad y convivencia"))
    db_session.commit()

    rows = city_topics(db_session, days=7, samples_per=2)
    sec = next(r for r in rows if r["category"] == "seguridad y convivencia")
    platforms = {s["platform"] for s in sec["samples"]}
    assert platforms == {"youtube", "instagram"}, f"se esperaba diversidad de plataformas, salió: {platforms}"


def test_city_topics_prefers_social_samples_over_press_even_with_lower_score(db_session):
    """Pedido del cliente 2026-09-30: si el mismo hecho tiene nota de prensa Y publicación en
    redes, prefiere la de redes como muestra -- ahí sí se puede evaluar la reacción de la gente en
    los comentarios, cosa que una nota de prensa no trae. La prensa se sigue capturando y contando
    igual, solo deja de ser la muestra elegida cuando hay una alternativa de redes."""
    from src.queries import city_topics
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    press = Source(type=SourceType.RSS, name="Q'hubo", config={"feed_url": "x", "city": True})
    social = Source(type=SourceType.SOCIAL, name="Instagram / Facebook (cuentas)")
    db_session.add_all([city, press, social])
    db_session.commit()
    now = dt.datetime.utcnow()
    rows = [
        # la nota de prensa tiene el score más intenso, pero debe quedar DESPUÉS de la de redes
        (city, "press1", "El País: terremoto golpea Cali", press, -0.95),
        (city, "soc1", "Instagram: así vivimos el terremoto", social, -0.4),
    ]
    for cand, ext, text, src, score in rows:
        m = Mention(candidate_id=cand.id, source_id=src.id, external_id=ext, text=text, url=f"https://x/{ext}",
                    raw={"kind": "post"}, author="u", published_at=now, fetched_at=now)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.NEGATIVE, score=score,
                                      topic="terremoto", model="f", category="terremoto y reconstrucción"))
    db_session.commit()

    rows_by_cat = {r["category"]: r for r in city_topics(db_session, days=7)}
    samples = rows_by_cat["terremoto y reconstrucción"]["samples"]
    assert samples[0]["text"] == "Instagram: así vivimos el terremoto"
    assert samples[1]["text"] == "El País: terremoto golpea Cali"


def test_city_topics_includes_dominant_emotion_visible_without_a_click(db_session):
    """Pedido del cliente 2026-10-01: la emoción debe verse directo en la tarjeta del tema, sin
    tener que abrir "ver comentarios de ejemplo". "Sin emoción marcada" no debe ganarle a una
    emoción real aunque sea más frecuente en términos absolutos -- no dice nada en un tema mixto."""
    from src.queries import city_topics
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    feed = Source(type=SourceType.RSS, name="Q'hubo", config={"feed_url": "x", "city": True})
    db_session.add_all([city, feed])
    db_session.commit()
    now = dt.datetime.utcnow()
    rows = [
        ("a", "felicidad"), ("b", "felicidad"), ("c", "ira"),
        ("d", None), ("e", None), ("f", None),  # "sin emoción marcada" es mayoría, pero no debe ganar
    ]
    for ext, emo in rows:
        m = Mention(candidate_id=city.id, source_id=feed.id, external_id=ext, text=ext, url=f"https://x/{ext}",
                    raw={}, author="u", published_at=now, fetched_at=now)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.NEUTRAL, score=0.0,
                                      topic="t", model="f", category="seguridad y convivencia", emotion=emo))
    db_session.commit()

    rows = city_topics(db_session, days=7)
    sec = next(r for r in rows if r["category"] == "seguridad y convivencia")
    assert sec["dominant_emotion"] == "felicidad"


def test_city_topic_emotion_samples_shows_the_apalancador(db_session):
    """Pedido del cliente 2026-10-01: si en el mapa de calor "deporte x felicidad" es lo más
    fuerte, debe poder verse qué es lo que está generando esa felicidad -- el apalancador es lo
    más valioso del reconocimiento de emociones, porque permite instrumentalizar la lectura."""
    from src.queries import city_topic_emotion_samples
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    feed = Source(type=SourceType.RSS, name="Q'hubo", config={"feed_url": "x", "city": True})
    db_session.add_all([city, feed])
    db_session.commit()
    now = dt.datetime.utcnow()
    rows = [
        ("a", "deporte", "felicidad", "triunfo del América de Cali"),
        ("b", "deporte", "felicidad", "ascenso del Cali a primera división"),
        ("c", "deporte", "ira", "pelea en las graderías"),
        ("d", "seguridad y convivencia", "felicidad", "no debe salir, es otro tema"),
    ]
    for ext, cat, emo, apalancador in rows:
        m = Mention(candidate_id=city.id, source_id=feed.id, external_id=ext, text=ext, url=f"https://x/{ext}",
                    raw={}, author="u", published_at=now, fetched_at=now)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.POSITIVE, score=0.5, topic="t",
                                      model="f", category=cat, emotion=emo, apalancador=apalancador))
    db_session.commit()

    samples = city_topic_emotion_samples(db_session, category="deporte", emotion="felicidad", days=7)
    assert {s["apalancador"] for s in samples} == {"triunfo del América de Cali", "ascenso del Cali a primera división"}


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


def test_city_opportunities_excludes_routine_pico_y_placa_reminders(db_session):
    """Pedido del cliente 2026-09-30: una nota de "pico y placa" que solo es el recordatorio
    diario de siempre no debe salir como novedad -- solo cuando hay una restricción real (pico y
    placa rotativo para pares/impares, día sin carro, etc.)."""
    from src.queries import city_opportunities
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    feed = Source(type=SourceType.RSS, name="Q'hubo", config={"feed_url": "x", "city": True})
    db_session.add_all([city, feed])
    db_session.commit()
    now = dt.datetime.utcnow()
    rows = [
        (city, "a", "Recuerda hoy el pico y placa en Cali", "movilidad y transporte", "pico y placa", "neutral", 0.0, 1),
        (city, "b", "Así va el pico y placa este lunes", "movilidad y transporte", "pico y placa", "neutral", 0.0, 1),
        (city, "c", "Pico y placa de hoy: consulta tu placa", "movilidad y transporte", "pico y placa", "neutral", 0.0, 1),
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
    assert "pico y placa" not in {x["topic"] for x in o["novedades"]}


def test_city_opportunities_includes_pico_y_placa_when_there_is_a_real_restriction(db_session):
    from src.queries import city_opportunities
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    feed = Source(type=SourceType.RSS, name="Q'hubo", config={"feed_url": "x", "city": True})
    db_session.add_all([city, feed])
    db_session.commit()
    now = dt.datetime.utcnow()
    rows = [
        (city, "a", "Anuncian pico y placa rotativo para números pares e impares", "movilidad y transporte", "pico y placa rotativo", "negative", -0.3, 1),
        (city, "b", "Pico y placa rotativo empieza a regir mañana", "movilidad y transporte", "pico y placa rotativo", "negative", -0.2, 1),
        (city, "c", "Dudas sobre el nuevo pico y placa rotativo", "movilidad y transporte", "pico y placa rotativo", "neutral", 0.0, 1),
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
    assert "pico y placa rotativo" in {x["topic"] for x in o["novedades"]}


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


def test_city_opportunities_excludes_topic_carlos_already_spoke_about_even_once(db_session):
    """Pedido del cliente 2026-09-30: si Carlos ya habló de un tema, así sea solo una vez,
    táchalo de "novedades donde Carlos podría hablar" -- el sentido de la lista es detectar
    huecos, no repetir lo que ya cubrió. Antes toleraba hasta 2 menciones suyas (carlos_max=2 por
    defecto); ahora con una sola mención ya no es un hueco."""
    from src.queries import city_opportunities
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    carlos = Candidate(name="Carlos Arias", aliases=[])
    feed = Source(type=SourceType.RSS, name="Q'hubo", config={"feed_url": "x", "city": True})
    db_session.add_all([city, carlos, feed])
    db_session.commit()
    now = dt.datetime.utcnow()
    rows = [
        (city, "a", "Operación Iron avanza en Cali", "seguridad y convivencia", "operación iron", "positive", 0.3, 1),
        (city, "b", "Operación Iron suma capturas", "seguridad y convivencia", "operación iron", "positive", 0.4, 1),
        (city, "c", "Balance de Operación Iron", "seguridad y convivencia", "operación iron", "neutral", 0.0, 1),
        (carlos, "d", "Carlos Arias celebra avances de la Operación Iron en Cali", "seguridad y convivencia",
         "seguridad y convivencia", "positive", 0.6, 1),
    ]
    for cand, ext, text, cat, topic, label, score, ago in rows:
        when = now - dt.timedelta(days=ago)
        m = Mention(candidate_id=cand.id, source_id=feed.id, external_id=ext, text=text, url=f"https://x/{ext}",
                    raw={}, author="u", published_at=when, fetched_at=when)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel(label), score=score, topic=topic, model="f", category=cat))
    db_session.commit()

    o = city_opportunities(db_session, days=7)  # carlos_max por defecto
    assert "operación iron" not in {x["topic"] for x in o["novedades"]}


def test_city_opportunities_merges_near_duplicate_topic_labels(db_session):
    """Bug real (2026-09-30): "operación iron", "operación iron en cali", "operación iron contra
    bandas" y "operación iron contra criminalidad" salían como 4 novedades separadas -- mismo
    hecho, etiquetado distinto por el LLM en cada nota. Ahora se juntan en una sola bajo la
    etiqueta más corta, con el conteo sumado."""
    from src.queries import city_opportunities
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    feed = Source(type=SourceType.RSS, name="Q'hubo", config={"feed_url": "x", "city": True})
    db_session.add_all([city, feed])
    db_session.commit()
    now = dt.datetime.utcnow()
    topics = ["operación iron", "operación iron en cali", "operación iron contra bandas",
              "operación iron contra criminalidad"]
    for i, topic in enumerate(topics):
        when = now - dt.timedelta(hours=i)
        m = Mention(candidate_id=city.id, source_id=feed.id, external_id=f"iron{i}",
                    text=f"Nota sobre {topic}", url=f"https://x/iron{i}", raw={}, author="u",
                    published_at=when, fetched_at=when)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.NEUTRAL, score=0.0,
                                      topic=topic, model="f", category="seguridad"))
    db_session.commit()

    o = city_opportunities(db_session, days=7, min_count=3)
    iron_novedades = [x for x in o["novedades"] if "iron" in x["topic"]]
    assert len(iron_novedades) == 1, f"se esperaba un solo tema fusionado, salieron: {iron_novedades}"
    assert iron_novedades[0]["topic"] == "operación iron"  # la etiqueta más corta del grupo
    assert iron_novedades[0]["count"] == 4  # las 4 notas quedan sumadas bajo el mismo tema


def test_city_opportunities_counts_carlos_presence_with_partial_topic_overlap(db_session):
    """Bug real (2026-09-30): "operación iron contra criminalidad" no calzaba con un post de
    Carlos que decía "La Operación IRON mejora la seguridad..." porque el post no repetía la
    palabra "criminalidad" -- el emparejamiento exigía TODAS las palabras del topic. Con al menos
    la mitad de solape alcanza."""
    from src.queries import mentions_covering_topic, mention_keywords
    carlos = Candidate(name="Carlos Arias", aliases=[])
    src = Source(type=SourceType.SOCIAL, name="Instagram / Facebook (cuentas)")
    m = Mention(candidate_id=1, source_id=1, external_id="d",
                text="La Operación IRON mejora la seguridad en Cali con coordinación entre instituciones.",
                url="https://x/d", raw={}, author="u",
                published_at=dt.datetime.utcnow(), fetched_at=dt.datetime.utcnow())
    m.sentiment = SentimentScore(label=SentimentLabel.POSITIVE, score=0.6, topic="seguridad", model="f", category="seguridad")
    keywords = mention_keywords([m])
    assert mentions_covering_topic("operación iron contra criminalidad", keywords) == 1


def test_city_kpis(db_session):
    from src.queries import city_kpis
    _seed_city(db_session)
    k = city_kpis(db_session, days=7)
    assert k["total"] == 5 and k["top_category"] == "servicios públicos"
    assert k["negative_pct"] == 60  # 3 de 5 negativas
