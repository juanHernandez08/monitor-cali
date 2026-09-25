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
