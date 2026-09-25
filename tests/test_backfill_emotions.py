import datetime as dt

from src.models import Candidate, Source, SourceType, Mention, SentimentScore, SentimentLabel


class FakeEngine:
    """Devuelve una emoción fija sin llamar a ningún modelo real."""
    def __init__(self, emotion="alegría"):
        self.emotion = emotion
        self.calls = []

    def score(self, text, candidate=None, city=False):
        from src.sentiment import SentimentResult
        self.calls.append(text)
        return SentimentResult(label=SentimentLabel.POSITIVE, score=0.5, topic="t", model="fake",
                               category="otro", summary="s", emotion=self.emotion)


def _mention(db_session, cand, src, ext, text, emotion=None, relevant=True, raw=None):
    now = dt.datetime.utcnow()
    m = Mention(candidate_id=cand.id, source_id=src.id, external_id=ext, text=text, url=f"https://x/{ext}",
                raw=raw or {}, published_at=now, fetched_at=now, relevant=relevant)
    db_session.add(m)
    db_session.flush()
    db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.POSITIVE, score=0.5, topic="t",
                                  model="fake", category="otro", emotion=emotion))
    db_session.commit()
    return m


def test_backfill_fills_only_mentions_missing_emotion(db_session):
    from scripts.backfill_emotions import run
    carlos = Candidate(name="Carlos Arias", aliases=[])
    src = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
    db_session.add_all([carlos, src])
    db_session.commit()
    without = _mention(db_session, carlos, src, "m1", "texto sin emoción")
    already = _mention(db_session, carlos, src, "m2", "texto ya con emoción", emotion="orgullo")

    engine = FakeEngine(emotion="alegría")
    n = run(db_session, engine=engine)

    assert n == 1
    assert without.sentiment.emotion == "alegría"
    assert already.sentiment.emotion == "orgullo"  # no se toca lo que ya tiene
    assert engine.calls == ["texto sin emoción"]


def test_backfill_does_not_change_other_fields(db_session):
    from scripts.backfill_emotions import run
    carlos = Candidate(name="Carlos Arias", aliases=[])
    src = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
    db_session.add_all([carlos, src])
    db_session.commit()
    m = _mention(db_session, carlos, src, "m1", "texto")
    engine = FakeEngine(emotion="miedo")
    run(db_session, engine=engine)
    assert m.sentiment.label == SentimentLabel.POSITIVE  # el original, no lo que devuelve el FakeEngine
    assert m.sentiment.score == 0.5
    assert m.sentiment.topic == "t"


def test_backfill_respects_limit(db_session):
    from scripts.backfill_emotions import run
    carlos = Candidate(name="Carlos Arias", aliases=[])
    src = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
    db_session.add_all([carlos, src])
    db_session.commit()
    _mention(db_session, carlos, src, "m1", "uno")
    _mention(db_session, carlos, src, "m2", "dos")
    engine = FakeEngine()
    n = run(db_session, engine=engine, limit=1)
    assert n == 1


def test_backfill_builds_context_like_pipeline_for_youtube_comments(db_session):
    from scripts.backfill_emotions import run
    carlos = Candidate(name="Carlos Arias", aliases=[])
    yt = Source(type=SourceType.YOUTUBE, name="YT")
    db_session.add_all([carlos, yt])
    db_session.commit()
    _mention(db_session, carlos, yt, "yt1", "buen video", raw={"kind": "comment", "video_title": "Entrevista a Carlos"})
    engine = FakeEngine()
    run(db_session, engine=engine)
    assert "Entrevista a Carlos" in engine.calls[0]


def test_backfill_skips_a_mention_when_scoring_fails(db_session):
    from scripts.backfill_emotions import run
    carlos = Candidate(name="Carlos Arias", aliases=[])
    src = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
    db_session.add_all([carlos, src])
    db_session.commit()
    m = _mention(db_session, carlos, src, "m1", "texto")

    class Boom:
        def score(self, *a, **k): raise RuntimeError("Ollama caído")
    n = run(db_session, engine=Boom())
    assert n == 0
    assert m.sentiment.emotion is None
