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
