import datetime as dt

from src.models import Candidate, Source, SourceType, Mention, SentimentScore, SentimentLabel


class FakeEngine:
    def __init__(self, emotion="miedo"):
        self.emotion = emotion
        self.calls = []

    def score(self, text, candidate=None, city=False):
        from src.sentiment import SentimentResult
        self.calls.append(text)
        return SentimentResult(label=SentimentLabel.POSITIVE, score=0.5, topic="t", model="fake",
                               category="otro", summary="s", emotion=self.emotion)


def _mention(db_session, cand, src, ext, text, emotion):
    now = dt.datetime.utcnow()
    m = Mention(candidate_id=cand.id, source_id=src.id, external_id=ext, text=text, url=f"https://x/{ext}",
                raw={}, published_at=now, fetched_at=now, relevant=True)
    db_session.add(m)
    db_session.flush()
    db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.POSITIVE, score=0.5, topic="t",
                                  model="fake", category="otro", emotion=emotion))
    db_session.commit()
    return m


def test_reclassifies_only_mentions_with_a_retired_emotion(db_session):
    from scripts.reclassify_retired_emotions import run
    carlos = Candidate(name="Carlos Arias", aliases=[])
    src = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
    db_session.add_all([carlos, src])
    db_session.commit()
    alegria = _mention(db_session, carlos, src, "m1", "que buena noticia", emotion="alegría")
    anticipacion = _mention(db_session, carlos, src, "m2", "ya viene el anuncio", emotion="anticipación")
    fine = _mention(db_session, carlos, src, "m3", "texto normal", emotion="sorpresa")

    engine = FakeEngine(emotion="miedo")
    n = run(db_session, engine=engine)

    assert n == 2
    assert alegria.sentiment.emotion == "miedo"
    assert anticipacion.sentiment.emotion == "miedo"
    assert fine.sentiment.emotion == "sorpresa"  # no se toca lo que ya está bien


def test_reclassify_does_not_change_other_fields(db_session):
    from scripts.reclassify_retired_emotions import run
    carlos = Candidate(name="Carlos Arias", aliases=[])
    src = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
    db_session.add_all([carlos, src])
    db_session.commit()
    m = _mention(db_session, carlos, src, "m1", "texto", emotion="alegría")
    run(db_session, engine=FakeEngine(emotion="ira"))
    assert m.sentiment.label == SentimentLabel.POSITIVE
    assert m.sentiment.score == 0.5
    assert m.sentiment.topic == "t"
