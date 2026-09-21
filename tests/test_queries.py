import datetime as dt

from src.models import Candidate, Source, SourceType, Mention, SentimentScore, SentimentLabel, Run
from src.queries import summary, timeline, mentions, alerts, topics, status


def _seed(db_session):
    carlos = Candidate(name="Carlos Arias", party="U", aliases=[])
    ana = Candidate(name="Ana Pérez", party="X", aliases=[])
    src = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
    db_session.add_all([carlos, ana, src])
    db_session.commit()
    now = dt.datetime.utcnow()
    rows = [
        (carlos, "m1", "malo", SentimentLabel.NEGATIVE, -0.9, "seguridad", now),
        (carlos, "m2", "bueno", SentimentLabel.POSITIVE, 0.8, "movilidad", now - dt.timedelta(days=1)),
        (ana, "m3", "neutro", SentimentLabel.NEUTRAL, 0.0, "Seguridad", now),
        (ana, "m5", "de paso", SentimentLabel.NEUTRAL, 0.0, "mención tangencial", now),
    ]
    for cand, ext, text, label, score, topic, when in rows:
        m = Mention(candidate_id=cand.id, source_id=src.id, external_id=ext, text=text,
                    url=f"https://x/{ext}", published_at=when, fetched_at=when)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=label, score=score, topic=topic, model="fake"))
    db_session.add(Mention(candidate_id=ana.id, source_id=src.id, external_id="m4", text="pendiente", fetched_at=now))
    db_session.add(Run(source_id=src.id, new_mentions=4, finished_at=now))
    db_session.commit()
    return carlos, ana


def test_summary_counts_by_candidate(db_session):
    carlos, _ = _seed(db_session)
    rows = summary(db_session, days=7)
    row = next(r for r in rows if r["candidate_id"] == carlos.id)
    assert row["mentions"] == 2 and row["negative"] == 1 and row["positive"] == 1
    assert rows[0]["name"] == "Carlos Arias"  # Carlos siempre primero


def test_timeline_groups_by_day(db_session):
    _seed(db_session)
    data = timeline(db_session, days=7)
    assert len(data["labels"]) == 7
    assert sum(sum(s["data"]) for s in data["series"]) == 5


def test_mentions_filters(db_session):
    carlos, _ = _seed(db_session)
    rows = mentions(db_session, candidate_id=carlos.id, label="negative", limit=10)
    assert [r["text"] for r in rows] == ["malo"]
    assert rows[0]["url"] == "https://x/m1" and rows[0]["source"] == "Google News"
    assert len(mentions(db_session, source_type="google_news")) == 5


def test_alerts_negative_about_carlos(db_session):
    _seed(db_session)
    rows = alerts(db_session, candidate_name="Carlos Arias", threshold=-0.5)
    assert [r["text"] for r in rows] == ["malo"]


def test_topics_and_status(db_session):
    _seed(db_session)
    t = topics(db_session, days=7)
    assert t[0] == {"topic": "seguridad", "count": 2}
    assert all(x["topic"] != "mención tangencial" for x in t)
    st = status(db_session)
    assert st["pending"] == 1 and st["total_mentions"] == 5
    assert st["sources"][0]["name"] == "Google News" and st["sources"][0]["last_new"] == 4


def test_feed_groups_comments_under_their_publication(db_session):
    from src.queries import feed
    carlos = Candidate(name="Carlos Arias", aliases=[])
    ig = Source(type=SourceType.SOCIAL, name="IG")
    yt = Source(type=SourceType.YOUTUBE, name="YouTube")
    gn = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
    db_session.add_all([carlos, ig, yt, gn])
    db_session.commit()
    now = dt.datetime.utcnow()

    def add(src, ext, text, raw, label, score, url=None, when=now):
        m = Mention(candidate_id=carlos.id, source_id=src.id, external_id=ext, text=text, url=url,
                    raw=raw, published_at=when, fetched_at=when, author="a")
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=label, score=score, topic="t", model="f"))
        return m

    add(ig, "ig:post:1", "Cali unida", {"kind": "post"}, SentimentLabel.POSITIVE, 0.3, url="https://instagram.com/p/1/")
    add(ig, "ig:comment:1", "👏", {"kind": "comment", "post_title": "Cali unida"}, SentimentLabel.POSITIVE, 0.5, url="https://instagram.com/p/1/", when=now - dt.timedelta(hours=1))
    add(ig, "ig:comment:2", "no", {"kind": "comment", "post_title": "Cali unida"}, SentimentLabel.NEGATIVE, -0.6, url="https://instagram.com/p/1/", when=now - dt.timedelta(hours=2))
    # comentario de YouTube cuyo video no está guardado → fila sintética con el título del video
    add(yt, "yt:comment:9", "qué bien", {"kind": "comment", "video_id": "v9", "video_title": "Entrevista"}, SentimentLabel.POSITIVE, 0.4,
        url="https://www.youtube.com/watch?v=v9&lc=9", when=now - dt.timedelta(days=1))
    add(gn, "g1", "Nota de prensa", {}, SentimentLabel.NEUTRAL, 0.0, url="https://elpais.com.co/n/1", when=now - dt.timedelta(days=2))
    db_session.commit()

    rows = feed(db_session, days=7, limit=10)

    assert [r["kind"] for r in rows] == ["post", "comments", "news"]
    post = rows[0]
    assert post["text"] == "Cali unida" and post["url"] == "https://instagram.com/p/1/" and post["label"] == "positive"
    assert post["comments_summary"] == {"total": 2, "positive": 1, "negative": 1, "neutral": 0}
    assert [c["text"] for c in post["comments"]] == ["👏", "no"]
    video = rows[1]
    assert video["text"] == "Entrevista" and video["url"] == "https://www.youtube.com/watch?v=v9"
    assert video["comments_summary"]["total"] == 1 and video["label"] is None
    assert rows[2]["comments_summary"]["total"] == 0 and rows[2]["comments"] == []


def test_feed_label_filter_keeps_publication_with_matching_comments(db_session):
    from src.queries import feed
    carlos = Candidate(name="Carlos Arias", aliases=[])
    ig = Source(type=SourceType.SOCIAL, name="IG")
    db_session.add_all([carlos, ig])
    db_session.commit()
    now = dt.datetime.utcnow()
    p = Mention(candidate_id=carlos.id, source_id=ig.id, external_id="ig:post:1", text="post", url="https://instagram.com/p/1/", raw={"kind": "post"}, published_at=now, fetched_at=now)
    c = Mention(candidate_id=carlos.id, source_id=ig.id, external_id="ig:comment:1", text="malo", url="https://instagram.com/p/1/", raw={"kind": "comment", "post_title": "post"}, published_at=now, fetched_at=now)
    db_session.add_all([p, c])
    db_session.flush()
    db_session.add_all([SentimentScore(mention_id=p.id, label=SentimentLabel.POSITIVE, score=0.3, topic="t", model="f"),
                        SentimentScore(mention_id=c.id, label=SentimentLabel.NEGATIVE, score=-0.6, topic="t", model="f")])
    db_session.commit()

    rows = feed(db_session, days=7, label="negative")
    assert len(rows) == 1 and rows[0]["text"] == "post"
    assert [x["text"] for x in rows[0]["comments"]] == ["malo"]


def test_summary_includes_avatar_from_instagram_posts(db_session, monkeypatch):
    from src import queries
    monkeypatch.setattr(queries.config, "SOCIAL_ACCOUNTS", [
        {"platform": "instagram", "url": "https://www.instagram.com/soycarlosaarias/", "candidate": "Carlos Arias"}])
    carlos = Candidate(name="Carlos Arias", aliases=[])
    ig = Source(type=SourceType.SOCIAL, name="IG")
    db_session.add_all([carlos, ig])
    db_session.commit()
    db_session.add(Mention(candidate_id=carlos.id, source_id=ig.id, external_id="ig:post:1", text="x",
                           raw={"kind": "post", "account": "https://www.instagram.com/soycarlosaarias/",
                                "record": {"profile_image_link": "https://cdn/pic.jpg", "thumbnail": "https://cdn/t.jpg"}}))
    db_session.commit()
    row = summary(db_session, days=7)[0]
    assert row["avatar"] == "https://cdn/pic.jpg"


def test_feed_rows_carry_thumbnails(db_session):
    from src.queries import feed
    carlos = Candidate(name="Carlos Arias", aliases=[])
    ig = Source(type=SourceType.SOCIAL, name="IG")
    yt = Source(type=SourceType.YOUTUBE, name="YouTube")
    db_session.add_all([carlos, ig, yt])
    db_session.commit()
    now = dt.datetime.utcnow()
    db_session.add(Mention(candidate_id=carlos.id, source_id=ig.id, external_id="ig:post:1", text="p", url="https://instagram.com/p/1/",
                           raw={"kind": "post", "record": {"thumbnail": "https://cdn/t.jpg"}}, published_at=now, fetched_at=now))
    db_session.add(Mention(candidate_id=carlos.id, source_id=yt.id, external_id="yt:video:v1", text="v", url="https://www.youtube.com/watch?v=v1",
                           raw={"kind": "video"}, published_at=now, fetched_at=now))
    db_session.add(Mention(candidate_id=carlos.id, source_id=yt.id, external_id="yt:comment:9", text="c", url="https://www.youtube.com/watch?v=v9&lc=9",
                           raw={"kind": "comment", "video_id": "v9", "video_title": "t"}, published_at=now, fetched_at=now))
    db_session.commit()
    rows = {r["external_id"] if r.get("external_id") else r["kind"]: r for r in feed(db_session, days=7)}
    thumbs = {r["text"]: r["thumbnail"] for r in feed(db_session, days=7)}
    assert thumbs["p"] == "https://cdn/t.jpg"
    assert thumbs["v"] == "https://i.ytimg.com/vi/v1/hqdefault.jpg"
    assert thumbs["t"] == "https://i.ytimg.com/vi/v9/hqdefault.jpg"


def test_sources_by_candidate_counts_relevant_mentions_per_source_type(db_session):
    from src.queries import sources_by_candidate
    carlos = Candidate(name="Carlos Arias", aliases=[])
    ana = Candidate(name="Ana Pérez", aliases=[])
    gn = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
    yt = Source(type=SourceType.YOUTUBE, name="YouTube")
    db_session.add_all([carlos, ana, gn, yt])
    db_session.commit()
    now = dt.datetime.utcnow()
    db_session.add_all([
        Mention(candidate_id=carlos.id, source_id=gn.id, external_id="1", text="a", fetched_at=now),
        Mention(candidate_id=carlos.id, source_id=yt.id, external_id="2", text="b", fetched_at=now),
        Mention(candidate_id=carlos.id, source_id=yt.id, external_id="3", text="c", fetched_at=now, relevant=False),
        Mention(candidate_id=ana.id, source_id=gn.id, external_id="4", text="d", fetched_at=now),
    ])
    db_session.commit()
    data = sources_by_candidate(db_session, days=7)
    assert data["candidates"][0] == "Carlos Arias"
    assert data["series"]["google_news"] == [1, 1]
    assert data["series"]["youtube"] == [1, 0]


def test_topics_can_split_publications_from_comments(db_session):
    carlos = Candidate(name="Carlos Arias", aliases=[])
    ig = Source(type=SourceType.SOCIAL, name="IG")
    db_session.add_all([carlos, ig])
    db_session.commit()
    now = dt.datetime.utcnow()
    rows = [("p1", {"kind": "post"}, "reconstrucción"), ("c1", {"kind": "comment"}, "agua en terrón colorado"),
            ("c2", {"kind": "comment"}, "sin tema"), ("n1", {}, "seguridad")]
    for ext, raw, topic in rows:
        m = Mention(candidate_id=carlos.id, source_id=ig.id, external_id=ext, text="x", raw=raw, published_at=now, fetched_at=now)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.NEUTRAL, score=0, topic=topic, model="f"))
    db_session.commit()
    assert {t["topic"] for t in topics(db_session, days=7, kind="publications")} == {"reconstrucción", "seguridad"}
    assert {t["topic"] for t in topics(db_session, days=7, kind="comments")} == {"agua en terrón colorado"}  # "sin tema" fuera
