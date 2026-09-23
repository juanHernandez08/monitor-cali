import datetime as dt

from src.models import Candidate, Source, SourceType, Mention, SentimentScore, SentimentLabel
from src.pipeline import CITY_NAME
from src.queries import agenda, citizen_perception


def _add(db_session, cand, src, ext, text, cat, label, score, ago=1, kind=None, topic="t"):
    when = dt.datetime.utcnow() - dt.timedelta(days=ago)
    raw = {"kind": kind} if kind else {}
    m = Mention(candidate_id=cand.id, source_id=src.id, external_id=ext, text=text, url=f"https://x/{ext}",
                raw=raw, author="u", published_at=when, fetched_at=when)
    db_session.add(m)
    db_session.flush()
    db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel(label), score=score, topic=topic,
                                  model="f", category=cat))
    return m


def _seed(db_session):
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    carlos = Candidate(name="Carlos Arias", aliases=[])
    rival = Candidate(name="Rival X", aliases=[])
    feed = Source(type=SourceType.RSS, name="Q'hubo", config={"feed_url": "x", "city": True})
    ig = Source(type=SourceType.SOCIAL, name="IG")
    db_session.add_all([city, carlos, rival, feed, ig])
    db_session.commit()
    # Ciudad: seguridad muy caliente (8 menciones, 75% molestia), servicios públicos medio, deporte tranquilo
    for i in range(6):
        _add(db_session, city, feed, f"s{i}", f"atracos en el MIO {i}", "seguridad", "negative", -0.7, topic="atracos mio")
    for i in range(2):
        _add(db_session, city, feed, f"sn{i}", "operativo policial", "seguridad", "neutral", 0.0)
    for i in range(4):
        _add(db_session, city, feed, f"a{i}", "sin agua otra vez", "servicios públicos", "negative", -0.6, topic="agua")
    for i in range(6):
        _add(db_session, city, feed, f"d{i}", "gana el América", "deporte", "positive", 0.5)
    # Carlos ya habla de servicios públicos (2), nada de seguridad
    for i in range(2):
        _add(db_session, carlos, ig, f"cp{i}", "Carlos sobre el agua", "servicios públicos", "positive", 0.4, kind="post")
    # Comentarios ciudadanos: a Rival X le fue mal cuando habló de corrupción
    for i in range(5):
        _add(db_session, city, feed, f"c{i}", "escándalo en el concejo", "corrupción y gobierno", "negative", -0.8)
    for i in range(4):
        _add(db_session, rival, ig, f"rc{i}", "usted es igual de corrupto", "corrupción y gobierno", "negative", -0.8, kind="comment")
    _add(db_session, rival, ig, "rc9", "bien dicho", "corrupción y gobierno", "positive", 0.5, kind="comment")
    # Reacción a Carlos: mayormente positiva
    for i in range(3):
        _add(db_session, carlos, ig, f"cc{i}", "gracias concejal", "servicios públicos", "positive", 0.6, kind="comment")
    _add(db_session, carlos, ig, "cc9", "no ha hecho nada", "servicios públicos", "negative", -0.7, kind="comment")
    db_session.commit()
    return city, carlos, rival


def test_agenda_recommends_hot_problem_without_carlos_and_flags_risky_topic(db_session):
    _seed(db_session)
    a = agenda(db_session, days=7)
    speak = {t["category"]: t for t in a["speak"]}
    assert "seguridad" in speak  # mucha molestia y Carlos ausente
    top = a["speak"][0]
    assert top["category"] == "seguridad" and top["negative_pct"] == 75 and top["carlos_mentions"] == 0
    assert top["subtopics"][0]["topic"] == "atracos mio" and top["samples"]
    assert "deporte" not in speak  # sin molestia, no es un problema que resolver
    avoid = {t["category"]: t for t in a["avoid"]}
    assert "corrupción y gobierno" in avoid  # a quien habló le fue mal
    assert avoid["corrupción y gobierno"]["candidate_negative_pct"] == 80


def test_agenda_marks_topics_where_carlos_already_speaks(db_session):
    _seed(db_session)
    a = agenda(db_session, days=7)
    sp = {t["category"]: t for t in a["speak"]}
    if "servicios públicos" in sp:
        assert sp["servicios públicos"]["carlos_mentions"] == 5  # 2 posts + 3 comentarios


def test_citizen_perception_uses_only_comments(db_session):
    _seed(db_session)
    rows = {r["name"]: r for r in citizen_perception(db_session, days=7)}
    assert rows["Carlos Arias"]["comments"] == 4 and rows["Carlos Arias"]["positive"] == 3
    assert rows["Rival X"]["comments"] == 5 and rows["Rival X"]["negative"] == 4
    assert rows["Carlos Arias"]["positive_pct"] == 75 and rows["Rival X"]["negative_pct"] == 80
    assert CITY_NAME not in rows
    assert rows["Rival X"]["samples"][0]["text"] == "usted es igual de corrupto"
