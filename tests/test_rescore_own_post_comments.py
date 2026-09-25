import datetime as dt

from src.models import Candidate, Source, SourceType, Mention, SentimentScore, SentimentLabel
from src.sentiment import SentimentResult


class FakeEngine:
    def __init__(self, result): self.result = result; self.calls = []
    def score(self, text, candidate=None, city=False):
        self.calls.append(text)
        return self.result


def test_rescores_only_comments_on_the_candidates_own_post(db_session):
    from scripts.rescore_own_post_comments import run
    carlos = Candidate(name="Carlos Arias", aliases=[])
    ana = Candidate(name="Ana Pérez", aliases=[])
    ig = Source(type=SourceType.SOCIAL, name="IG")
    db_session.add_all([carlos, ana, ig])
    db_session.commit()
    now = dt.datetime.utcnow()
    own = Mention(candidate_id=carlos.id, source_id=ig.id, external_id="ig:comment:1", text="MONDRAGON TRAPO SUCIO",
                 raw={"kind": "comment", "post_title": "No Alfredo Mondragón...", "account_candidate": "Carlos Arias"},
                 published_at=now, fetched_at=now)
    other = Mention(candidate_id=ana.id, source_id=ig.id, external_id="ig:comment:2", text="me encanta",
                    raw={"kind": "comment", "post_title": "x", "account_candidate": None},
                    published_at=now, fetched_at=now)
    db_session.add_all([own, other])
    db_session.flush()
    db_session.add_all([
        SentimentScore(mention_id=own.id, label=SentimentLabel.NEGATIVE, score=-0.6, topic="rechazo e insultos", model="old"),
        SentimentScore(mention_id=other.id, label=SentimentLabel.POSITIVE, score=0.5, topic="apoyo", model="old"),
    ])
    db_session.commit()

    engine = FakeEngine(SentimentResult(SentimentLabel.POSITIVE, 0.4, "apoyo a Carlos", "fake"))
    assert run(db_session, engine) == 1
    assert "tercero" in engine.calls[0].lower()
    assert own.sentiment.label == SentimentLabel.POSITIVE and own.sentiment.score == 0.4
    assert other.sentiment.label == SentimentLabel.POSITIVE and other.sentiment.score == 0.5  # sin tocar
