from src.geo import ancestors, is_inside_cali, locate


def ids(text):
    return {p["id"] for p in locate(text)}


def test_unambiguous_barrios_corregimientos_and_comunas_are_found():
    assert "barrio:2003" in ids("Inundaciones en Siloé")
    assert ids("Huecos en la vía a Pance y en La Buitrera") >= {"corregimiento:53", "corregimiento:54"}
    assert ids("Las comunas 13, 14 y 15 sin agua") >= {"comuna:13", "comuna:14", "comuna:15"}
    assert "comuna:18" in ids("alternancia en la comuna dieciocho")


def test_ambiguous_names_need_a_barrio_trigger_and_to_be_about_cali():
    assert ids("Petro habló de la paz total") == set()
    assert ids("Simón Bolívar dijo") == set()
    assert "barrio:0802" in ids("Vecinos del barrio Simón Bolívar en Cali")
    assert ids("operación militar en la vereda La Esperanza") == set()  # puede ser de otro municipio


def test_trigger_word_picks_the_level_and_cities_win_over_homonym_barrios():
    assert "barrio:0214" in ids("Balacera en el barrio La Paz de Cali")
    assert "corregimiento:63" in ids("corregimiento La Paz, Cali")
    assert ids("El alcalde viajó a Barranquilla") == {"municipio:08001"}  # no el barrio Los Parques - Barranquilla
    assert "municipio:11001" in ids("En Bogotá")


def test_distrito_de_aguablanca_is_its_four_comunas():
    assert ids("Obras en el Distrito de Aguablanca") == {"comuna:13", "comuna:14", "comuna:15", "comuna:21"}


def test_hierarchy_rolls_barrios_up_to_comuna_and_city():
    assert ancestors("barrio:0216") == ["comuna:02", "municipio:76001", "departamento:76"]
    assert is_inside_cali("barrio:0216") and not is_inside_cali("municipio:76001")


def _mention(db_session, text, raw=None, hint=None, label="NEGATIVE", ext=None):
    import datetime as dt
    from src.models import Candidate, Mention, SentimentLabel, SentimentScore, Source, SourceType
    cand = db_session.query(Candidate).filter_by(name="Cali (ciudad)").first()
    if cand is None:
        cand = Candidate(name="Cali (ciudad)", aliases=[], kind="city")
        db_session.add_all([cand, Source(type=SourceType.RSS, name="Medio local")])
        db_session.commit()
    src = db_session.query(Source).first()
    now = dt.datetime.utcnow()
    m = Mention(candidate_id=cand.id, source_id=src.id, external_id=ext or text[:40], text=text, url="https://x/" + (ext or "a"),
                raw=raw or {}, published_at=now, fetched_at=now, relevant=True)
    db_session.add(m)
    db_session.flush()
    db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel[label], score=-0.5, topic="agua",
                                  category="servicios públicos", model="f", place_hint=hint))
    db_session.commit()
    return m


def test_assign_places_keeps_the_most_specific_zone_and_inherits_for_comments(db_session):
    from src.geo import assign_places
    from src.models import MentionPlace
    m = _mention(db_session, "Sin agua en el barrio Siloé, comuna 20 de Cali", ext="m1")
    assign_places(db_session, m)
    assert [p.place_id for p in db_session.query(MentionPlace).filter_by(mention_id=m.id)] == ["barrio:2003"]
    c = _mention(db_session, "qué vergüenza", raw={"kind": "comment", "post_title": "Inundación en Potrero Grande"}, ext="c1")
    assign_places(db_session, c)
    row = db_session.query(MentionPlace).filter_by(mention_id=c.id).one()
    assert (row.place_id, row.method) == ("comuna:21", "heredado")


def test_llm_place_hint_is_normalized_against_the_official_list(db_session):
    from src.geo import assign_places
    from src.models import MentionPlace
    m = _mention(db_session, "Balacera anoche, dos heridos", hint="La Paz", ext="h1")
    assign_places(db_session, m)
    row = db_session.query(MentionPlace).filter_by(mention_id=m.id).one()
    assert (row.place_id, row.method) == ("barrio:0214", "ia")
    n = _mention(db_session, "Huecos por todos lados", hint="calle 5 con 39", ext="h2")
    assert assign_places(db_session, n) == 0  # una dirección no está en el diccionario: no se inventa zona


def test_geo_zones_rolls_up_to_comuna_and_detail_merges_a_group(db_session):
    from src import queries
    from src.geo import assign_places
    for i, t in enumerate(["Sin agua en Siloé, Cali", "Balacera en Siloé, Cali", "Fiesta en Potrero Grande", "Inundación en Pance"]):
        assign_places(db_session, _mention(db_session, t, ext=f"z{i}"))
    db_session.commit()
    z = {r["id"]: r for r in queries.geo_zones(db_session, days=7, level="comuna", min_mentions=2)["zones"]}
    assert z["comuna:20"]["mentions"] == 2 and z["comuna:20"]["conclusive"] and z["comuna:20"]["negative_pct"] == 100
    assert z["comuna:21"]["mentions"] == 1 and not z["comuna:21"]["conclusive"]
    d = queries.geo_detail(db_session, ["comuna:20", "comuna:21"], days=7)
    assert d["mentions"] == 3 and d["facets"]["subzone"][0] == {"value": "barrio:2003", "name": "Siloé", "level": "barrio", "count": 2}
    c = queries.geo_zones(db_session, days=7, level="corregimiento")
    assert [r["id"] for r in c["zones"]] == ["corregimiento:53"]


def test_sentiment_parser_reads_the_place_hint():
    from src.sentiment import _parse_payload
    r = _parse_payload('{"label": "negative", "score": -0.4, "topic": "agua", "lugar": "barrio Siloé"}', "m")
    assert r.place_hint == "barrio Siloé"
    assert _parse_payload('{"label": "neutral", "score": 0}', "m").place_hint == ""


def test_football_teams_and_standings_are_not_places():
    assert ids("Deportes Tolima empató con el Junior de Barranquilla") == set()
    assert ids("Tabla de la liga BetPlay: 1. América 20 pts, 2. Tolima 16 pts, 3. Medellín 15 pts") == set()
    assert "barrio:2003" in ids("Los hinchas celebraron el gol en Siloé, Cali")
    assert "departamento:73" in ids("Lluvias fuertes en el Tolima y el Huila")


def test_social_comments_inherit_the_zone_of_the_full_parent_post(db_session):
    """Bug real 2026-10-20: 0 % de los comentarios de Instagram/Facebook tenían zona porque solo se miraba
    el `post_title` (los primeros ~90 caracteres); la publicación completa sí nombraba el barrio."""
    from src.geo import assign_places
    from src.models import MentionPlace
    post = _mention(db_session, "Recorrimos hoy la comunidad. " * 5 + "Estuvimos en el barrio Mojica escuchando a los vecinos",
                    raw={"kind": "post", "platform": "instagram"}, ext="post1")
    post.url = "https://www.instagram.com/p/abc/"
    com = _mention(db_session, "gracias por venir", ext="com1",
                   raw={"kind": "comment", "platform": "instagram", "post_title": "Recorrimos hoy la comunidad. Recorrimos hoy"})
    com.url = "https://www.instagram.com/p/abc/"
    db_session.commit()
    assign_places(db_session, com)
    row = db_session.query(MentionPlace).filter_by(mention_id=com.id).one()
    assert (row.place_id, row.method) == ("barrio:1506", "heredado")


def test_article_less_barrio_names_and_campaign_regions():
    # "Comuneros" son dos barrios oficiales (I y II) en comunas distintas: solo se puede afirmar Cali
    assert "barrio:" not in " ".join(ids("barrio Comuneros, Cali")) and "municipio:76001" in ids("barrio Comuneros, Cali")
    assert ids("Más policía en el oriente de Cali") == {"comuna:13", "comuna:14", "comuna:15", "comuna:16", "comuna:21"}
    assert ids("Comuneros firmes") == set()  # sin "barrio" delante no cuenta


def test_backfill_place_hints_only_sets_the_place_and_recomputes_the_zone(db_session):
    from src.models import MentionPlace
    from src.pipeline import backfill_place_hints
    from src.sentiment import SentimentResult
    from src.models import SentimentLabel

    class Fake:
        calls = 0
        def score(self, text, candidate=None, city=False):
            Fake.calls += 1
            return SentimentResult(label=SentimentLabel.POSITIVE, score=0.9, topic="otro tema", model="x", place_hint="La Paz")

    m = _mention(db_session, "Balacera anoche, dos heridos", ext="bf1")  # place_hint None: clasificada antes del campo
    assert backfill_place_hints(db_session, Fake(), limit=5) == 1
    db_session.refresh(m)
    assert m.sentiment.place_hint == "La Paz" and m.sentiment.label.name == "NEGATIVE" and m.sentiment.topic == "agua"
    assert db_session.query(MentionPlace).filter_by(mention_id=m.id).one().place_id == "barrio:0214"
    assert backfill_place_hints(db_session, Fake(), limit=5) == 0 and Fake.calls == 1  # ya no queda pendiente


def test_backfill_place_hints_stops_when_the_llm_is_down(db_session):
    from src.pipeline import backfill_place_hints

    class Down:
        def score(self, *a, **k):
            raise RuntimeError("PC apagado")

    m = _mention(db_session, "Huecos", ext="bf2")
    assert backfill_place_hints(db_session, Down(), limit=5) == 0
    db_session.refresh(m)
    assert m.sentiment.place_hint is None


def test_geo_detail_filters_facets_pagination_and_groups(db_session):
    from src import queries
    from src.geo import assign_places
    from src.models import Source, SourceType
    a = _mention(db_session, "Balacera en Siloé, Cali", ext="g1")                       # noticia (RSS), negativa
    social = Source(type=SourceType.SOCIAL, name="Instagram / Facebook (cuentas)")
    db_session.add(social)
    db_session.commit()
    b = _mention(db_session, "Sin agua en Siloé, Cali", ext="g2", label="POSITIVE")      # noticia, positiva
    c = _mention(db_session, "qué miedo vivir en Siloé, Cali", ext="g3",
                 raw={"kind": "comment", "platform": "instagram"})
    c.source_id = social.id
    b.sentiment.category = "seguridad y convivencia"
    b.sentiment.topic = "seguridad y convivencia"  # el LLM repitió la categoría como asunto: no debe salir como asunto
    db_session.commit()
    for m in (a, b, c):
        assign_places(db_session, m)
    db_session.commit()

    d = queries.geo_detail(db_session, ["comuna:20"], days=7)
    assert d["total"] == 3 and {f["value"]: f["count"] for f in d["facets"]["kind"]} == {"noticia": 2, "comentario": 1}
    assert {f["value"] for f in d["facets"]["channel"]} == {"prensa", "redes"}
    assert "seguridad y convivencia" not in {f["value"] for f in d["facets"]["topic"]}

    only = queries.geo_detail(db_session, ["comuna:20"], days=7, filters={"kind": "comentario"})
    assert only["mentions"] == 1 and only["total"] == 3 and only["items"][0]["text"].startswith("qué miedo")
    # la faceta del filtro activo sigue mostrando todas sus opciones (para poder cambiar de opción)
    assert {f["value"] for f in only["facets"]["kind"]} == {"noticia", "comentario"}

    cat = queries.geo_detail(db_session, ["comuna:20"], days=7, filters={"category": "seguridad y convivencia"})
    assert cat["mentions"] == 1
    page = queries.geo_detail(db_session, ["comuna:20"], days=7, limit=2, offset=2)
    assert len(page["items"]) == 1
    neg = queries.geo_detail(db_session, ["comuna:20"], days=7, sort="negative")
    assert neg["items"][0]["label"] == "negative"
    g = queries.geo_detail(db_session, ["comuna:20"], days=7, group="category")
    assert sum(x["mentions"] for x in g["groups"]) == 3 and all(len(x["items"]) <= 3 for x in g["groups"])
