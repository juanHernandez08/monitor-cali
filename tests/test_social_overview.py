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
    assert "Cali (ciudad)" not in names
