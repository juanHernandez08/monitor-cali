import datetime as dt

from src.models import Candidate, Source, SourceType, Mention, SentimentScore, SentimentLabel


def _seed(db_session):
    carlos = Candidate(name="Carlos Arias", party="U", aliases=[])
    clara = Candidate(name="Clara Luz Roldán", party="U", aliases=[])
    ig = Source(type=SourceType.SOCIAL, name="Instagram / Facebook (cuentas)")
    db_session.add_all([carlos, clara, ig])
    db_session.commit()
    now = dt.datetime.utcnow()

    def _post(cand, ext, text, platform, likes, comments, views, when_ago, label="positive", score=0.5):
        record = {"likesCount": likes, "videoPlayCount": views} if platform == "instagram" \
            else {"likes": likes, "viewsCount": views}
        m = Mention(candidate_id=cand.id, source_id=ig.id, external_id=ext, text=text,
                    url=f"https://x/{ext}", raw={"kind": "post", "platform": platform, "num_comments": comments, "record": record},
                    published_at=now - dt.timedelta(days=when_ago), fetched_at=now)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel(label), score=score, topic="t", model="f"))

    def _comment(cand, ext, text, when_ago):
        m = Mention(candidate_id=cand.id, source_id=ig.id, external_id=ext, text=text,
                    url="https://x/post1", raw={"kind": "comment", "platform": "instagram"},
                    published_at=now - dt.timedelta(days=when_ago), fetched_at=now)
        db_session.add(m)

    _post(carlos, "ig:post:1", "Trincheras en Cali", "instagram", likes=500, comments=40, views=73900, when_ago=20)
    _post(carlos, "ig:post:2", "Reactivación comercial", "instagram", likes=168, comments=22, views=10500, when_ago=5)
    _post(clara, "fb:post:1", "Gracias Cali", "facebook", likes=90, comments=10, views=2000, when_ago=3)
    _comment(carlos, "ig:comment:1", "que bien", when_ago=5)
    db_session.commit()
    return carlos, clara


def test_social_posts_only_returns_posts_not_comments_with_engagement_metrics(db_session):
    from src.queries import social_posts
    _seed(db_session)
    rows = social_posts(db_session, days=30)
    assert len(rows) == 3  # 2 de Carlos + 1 de Clara, el comentario no cuenta
    trincheras = next(r for r in rows if "Trincheras" in r["text"])
    assert trincheras["likes"] == 500 and trincheras["comments"] == 40 and trincheras["views"] == 73900
    assert trincheras["engagement"] == 540
    assert trincheras["platform"] == "instagram" and trincheras["candidate"] == "Carlos Arias"


def test_social_posts_sorted_by_engagement_by_default(db_session):
    from src.queries import social_posts
    _seed(db_session)
    rows = social_posts(db_session, days=30)
    assert [r["text"] for r in rows] == ["Trincheras en Cali", "Reactivación comercial", "Gracias Cali"]


def test_social_posts_filters_by_candidate_and_platform(db_session):
    from src.queries import social_posts
    carlos, clara = _seed(db_session)
    rows = social_posts(db_session, days=30, candidate_id=carlos.id)
    assert len(rows) == 2 and all(r["candidate"] == "Carlos Arias" for r in rows)
    rows = social_posts(db_session, days=30, platform="facebook")
    assert len(rows) == 1 and rows[0]["candidate"] == "Clara Luz Roldán"


def test_social_kpis_aggregate_totals_and_top_post(db_session):
    from src.queries import social_kpis
    _seed(db_session)
    k = social_kpis(db_session, days=30)
    assert k["total_posts"] == 3
    assert k["total_likes"] == 500 + 168 + 90
    assert k["total_comments"] == 40 + 22 + 10
    assert k["total_views"] == 73900 + 10500 + 2000
    assert k["top_post"]["text"] == "Trincheras en Cali"
    by_cand = {r["candidate"]: r["count"] for r in k["by_candidate"]}
    assert by_cand == {"Carlos Arias": 2, "Clara Luz Roldán": 1}


def test_social_posts_includes_councilors_not_only_race_candidates(db_session):
    # Bug real (2026-09-28): un reel de la concejal Audry Toro no aparecía en "Meta y redes"
    # porque social_posts() solo miraba Candidate.kind == "candidate", nunca "councilor".
    from src.queries import social_posts
    audry = Candidate(name="Audry María Toro Echavarría", party="U", aliases=[], kind="councilor", council=True)
    ig = Source(type=SourceType.SOCIAL, name="Instagram / Facebook (cuentas)")
    db_session.add_all([audry, ig])
    db_session.commit()
    now = dt.datetime.utcnow()
    m = Mention(candidate_id=audry.id, source_id=ig.id, external_id="ig:post:audry", text="Reel con fuerza",
                url="https://x/audry", raw={"kind": "post", "platform": "instagram", "num_comments": 300,
                                             "record": {"likesCount": 4000, "videoPlayCount": 90000}},
                published_at=now - dt.timedelta(days=1), fetched_at=now)
    db_session.add(m)
    db_session.flush()
    db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.POSITIVE, score=0.6, topic="t", model="f"))
    db_session.commit()

    rows = social_posts(db_session, days=30)
    assert any(r["candidate"] == "Audry María Toro Echavarría" and r["engagement"] == 4300 for r in rows)


def test_social_strong_posts_flags_engagement_well_above_the_accounts_own_average(db_session):
    from src.queries import social_strong_posts
    carlos = Candidate(name="Carlos Arias", party="U", aliases=[])
    ig = Source(type=SourceType.SOCIAL, name="Instagram / Facebook (cuentas)")
    db_session.add_all([carlos, ig])
    db_session.commit()
    now = dt.datetime.utcnow()

    def _post(ext, likes, comments, when_ago):
        m = Mention(candidate_id=carlos.id, source_id=ig.id, external_id=ext, text=ext,
                    url=f"https://x/{ext}", raw={"kind": "post", "platform": "instagram",
                                                 "num_comments": comments, "record": {"likesCount": likes}},
                    published_at=now - dt.timedelta(days=when_ago), fetched_at=now)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.POSITIVE, score=0.5, topic="t", model="f"))

    # Historial normal: ~50 de alcance por post.
    _post("p1", likes=40, comments=10, when_ago=60)
    _post("p2", likes=45, comments=8, when_ago=45)
    _post("p3", likes=50, comments=5, when_ago=30)
    # Este sí se dispara muy por encima de su propio promedio reciente.
    _post("p4", likes=2000, comments=300, when_ago=2)
    db_session.commit()

    strong = social_strong_posts(db_session, days=7, multiplier=3.0)
    assert len(strong) == 1
    assert strong[0]["text"] == "p4"
    assert strong[0]["engagement"] == 2300
    assert strong[0]["baseline"] > 0
    assert strong[0]["multiplier"] >= 3.0


def test_social_strong_posts_needs_enough_history_to_judge(db_session):
    # Sin historial previo no hay "propio promedio" contra qué comparar -- no se alerta
    # a ciegas la primera publicación de una cuenta recién agregada.
    from src.queries import social_strong_posts
    carlos = Candidate(name="Carlos Arias", party="U", aliases=[])
    ig = Source(type=SourceType.SOCIAL, name="Instagram / Facebook (cuentas)")
    db_session.add_all([carlos, ig])
    db_session.commit()
    now = dt.datetime.utcnow()
    m = Mention(candidate_id=carlos.id, source_id=ig.id, external_id="only", text="unica",
                url="https://x/only", raw={"kind": "post", "platform": "instagram",
                                           "num_comments": 500, "record": {"likesCount": 3000}},
                published_at=now - dt.timedelta(days=1), fetched_at=now)
    db_session.add(m)
    db_session.flush()
    db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.POSITIVE, score=0.5, topic="t", model="f"))
    db_session.commit()

    assert social_strong_posts(db_session, days=7) == []


def test_social_candidates_lists_race_candidates_and_councilors_not_city(db_session):
    from src.queries import social_candidates
    carlos, clara = _seed(db_session)
    audry = Candidate(name="Audry María Toro Echavarría", party="U", aliases=[], kind="councilor", council=True)
    cali = Candidate(name="Cali (ciudad)", aliases=[], kind="city")
    db_session.add_all([audry, cali])
    db_session.commit()

    names = {r["name"] for r in social_candidates(db_session)}
    assert names == {"Carlos Arias", "Clara Luz Roldán", "Audry María Toro Echavarría"}


def test_candidate_reach_comparison_ranks_by_average_engagement_and_shows_trend(db_session):
    from src.queries import candidate_reach_comparison
    carlos = Candidate(name="Carlos Arias", party="U", aliases=[])
    clara = Candidate(name="Clara Luz Roldán", party="U", aliases=[])
    ig = Source(type=SourceType.SOCIAL, name="Instagram / Facebook (cuentas)")
    db_session.add_all([carlos, clara, ig])
    db_session.commit()
    now = dt.datetime.utcnow()

    def _post(cand, ext, likes, comments, when_ago):
        m = Mention(candidate_id=cand.id, source_id=ig.id, external_id=ext, text=ext,
                    url=f"https://x/{ext}", raw={"kind": "post", "platform": "instagram",
                                                 "num_comments": comments, "record": {"likesCount": likes}},
                    published_at=now - dt.timedelta(days=when_ago), fetched_at=now)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.POSITIVE, score=0.5, topic="t", model="f"))

    # Carlos: alcance bajo y estable (empeorando levemente en la mitad reciente del período).
    _post(carlos, "c1", likes=45, comments=5, when_ago=25)
    _post(carlos, "c2", likes=55, comments=5, when_ago=20)
    _post(carlos, "c3", likes=30, comments=5, when_ago=5)
    _post(carlos, "c4", likes=20, comments=5, when_ago=2)
    # Clara: alcance mucho más alto y creciendo.
    _post(clara, "d1", likes=200, comments=20, when_ago=25)
    _post(clara, "d2", likes=250, comments=20, when_ago=20)
    _post(clara, "d3", likes=600, comments=50, when_ago=5)
    _post(clara, "d4", likes=700, comments=50, when_ago=2)
    db_session.commit()

    rows = {r["candidate"]: r for r in candidate_reach_comparison(db_session, days=30)}
    assert rows["Clara Luz Roldán"]["avg_engagement"] > rows["Carlos Arias"]["avg_engagement"]
    assert rows["Clara Luz Roldán"]["trend_pct"] > 0  # va en alza
    assert rows["Carlos Arias"]["trend_pct"] < 0  # va en baja
    ranked = candidate_reach_comparison(db_session, days=30)
    assert ranked[0]["candidate"] == "Clara Luz Roldán"  # ordenado por alcance promedio, de mayor a menor


def test_candidate_comment_reaction_only_counts_comments_on_the_candidates_own_post(db_session):
    from src.queries import candidate_comment_reaction
    carlos = Candidate(name="Carlos Arias", party="U", aliases=[])
    mondragon = Candidate(name="Alfredo Mondragón", party="Pacto Histórico", aliases=[])
    ig = Source(type=SourceType.SOCIAL, name="Instagram / Facebook (cuentas)")
    db_session.add_all([carlos, mondragon, ig])
    db_session.commit()
    now = dt.datetime.utcnow()

    def _comment(ext, text, label, owner, target_candidate):
        m = Mention(candidate_id=target_candidate.id, source_id=ig.id, external_id=ext, text=text,
                    url="https://x/post", raw={"kind": "comment", "platform": "instagram", "account_candidate": owner},
                    published_at=now - dt.timedelta(days=1), fetched_at=now)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel(label), score=0.0, topic="t", model="f"))

    # 3 comentarios en la publicación PROPIA de Carlos: 2 positivos, 1 negativo.
    _comment("m1", "bien", "positive", "Carlos Arias", carlos)
    _comment("m2", "bien2", "positive", "Carlos Arias", carlos)
    _comment("m3", "mal", "negative", "Carlos Arias", carlos)
    # Un insulto a Mondragón EN esa misma publicación de Carlos: no debe contar para Carlos.
    _comment("m4", "Mondragón es un ladrón", "negative", "Carlos Arias", mondragon)
    db_session.commit()

    rows = {r["candidate"]: r for r in candidate_comment_reaction(db_session, days=30, min_comments=1)}
    assert rows["Carlos Arias"]["comments"] == 3
    assert rows["Carlos Arias"]["positive_pct"] == 67
    assert "Alfredo Mondragón" not in rows  # el insulto fue en el post de Carlos, no en uno propio de Mondragón


def test_candidate_topic_gaps_lists_categories_the_candidate_never_touched(db_session):
    from src.queries import candidate_topic_gaps
    city = Candidate(name="Cali (ciudad)", kind="city", aliases=[])
    carlos = Candidate(name="Carlos Arias", aliases=[])
    feed = Source(type=SourceType.RSS, name="Q'hubo", config={"feed_url": "x", "city": True})
    db_session.add_all([city, carlos, feed])
    db_session.commit()
    now = dt.datetime.utcnow()

    def _m(cand, ext, text, cat, label="neutral", score=0.0):
        m = Mention(candidate_id=cand.id, source_id=feed.id, external_id=ext, text=text, url=f"https://x/{ext}",
                    raw={}, published_at=now - dt.timedelta(days=1), fetched_at=now)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel(label), score=score, topic="t", model="f", category=cat))

    _m(city, "a", "hueco en la via", "movilidad y transporte")
    _m(city, "b", "otro hueco", "movilidad y transporte")
    _m(city, "c", "fuga de agua", "servicios públicos")
    _m(carlos, "d", "Carlos habla de seguridad", "seguridad")  # Carlos sí tocó seguridad
    db_session.commit()

    gaps = {g["category"] for g in candidate_topic_gaps(db_session, "Carlos Arias", days=7)}
    assert "movilidad y transporte" in gaps
    assert "servicios públicos" in gaps
    assert "seguridad" not in gaps  # ya lo tocó
