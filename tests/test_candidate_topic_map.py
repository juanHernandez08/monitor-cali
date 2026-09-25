import datetime as dt

from src.models import Candidate, Source, SourceType, Mention, SentimentScore, SentimentLabel
from src.queries import candidate_topic_map


def _add(db_session, cand, src, ext, text, label, score, topic, ago=1, kind=None):
    when = dt.datetime.utcnow() - dt.timedelta(days=ago)
    raw = {"kind": kind} if kind else {}
    m = Mention(candidate_id=cand.id, source_id=src.id, external_id=ext, text=text, url=f"https://x/{ext}",
                raw=raw, author="u", published_at=when, fetched_at=when)
    db_session.add(m)
    db_session.flush()
    db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel(label), score=score, topic=topic,
                                  model="f", category="cat"))
    return m


def _seed(db_session):
    carlos = Candidate(name="Carlos Arias", aliases=[])
    rival = Candidate(name="Rival X", aliases=[])
    ig = Source(type=SourceType.SOCIAL, name="IG")
    yt = Source(type=SourceType.YOUTUBE, name="YT")
    db_session.add_all([carlos, rival, ig, yt])
    db_session.commit()

    # Carlos: 3 menciones sobre "malla vial" (2 positivas, 1 negativa), 2 sobre "seguridad" (negativas)
    _add(db_session, carlos, ig, "c1", "buena gestión con la malla vial", "positive", 0.6, "malla vial", kind="comment")
    _add(db_session, carlos, ig, "c2", "por fin arreglaron esa vía", "positive", 0.5, "malla vial", kind="comment")
    _add(db_session, carlos, yt, "c3", "la malla vial sigue mal en mi barrio", "negative", -0.4, "malla vial", kind="comment")
    _add(db_session, carlos, ig, "c4", "inseguridad total en el sector", "negative", -0.7, "seguridad", kind="comment")
    _add(db_session, carlos, ig, "c5", "nos roban todos los días", "negative", -0.8, "seguridad", kind="comment")
    # ruido a ignorar: sin tema, y de otro candidato
    _add(db_session, carlos, ig, "c6", "hola", "neutral", 0.0, "sin tema", kind="comment")
    _add(db_session, rival, ig, "r1", "otro tema de otro candidato", "negative", -0.5, "malla vial", kind="comment")


def test_candidate_topic_map_groups_by_topic_with_sentiment_and_samples(db_session):
    _seed(db_session)
    rows = candidate_topic_map(db_session, "Carlos Arias", days=7)
    by_topic = {r["topic"]: r for r in rows}

    assert "malla vial" in by_topic and "seguridad" in by_topic
    assert "sin tema" not in by_topic  # etiqueta de control, no es un tema real

    malla = by_topic["malla vial"]
    assert malla["count"] == 3 and malla["positive"] == 2 and malla["negative"] == 1
    assert malla["positive_pct"] == 67
    assert malla["samples"]

    seguridad = by_topic["seguridad"]
    assert seguridad["count"] == 2 and seguridad["negative"] == 2

    # ordenado por volumen, el tema con más menciones primero
    assert rows[0]["topic"] == "malla vial"

    # no debe traer menciones de otro candidato
    assert sum(r["count"] for r in rows) == 5


def test_candidate_topic_map_unknown_candidate_returns_empty(db_session):
    assert candidate_topic_map(db_session, "Nadie", days=7) == []
