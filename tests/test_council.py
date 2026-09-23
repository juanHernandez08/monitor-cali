import datetime as dt

from src.config import COUNCILORS
from src.models import Candidate, Source, SourceType, Mention, SentimentScore, SentimentLabel
from src.pipeline import ingest, CITY_NAME
from src.connectors.base import RawItem
from scripts.seed_sources import seed


class ListConnector:
    def __init__(self, items): self.items = items
    def fetch(self, terms): self.terms = terms; return self.items


def test_seed_creates_21_council_members_with_party(db_session):
    seed(db_session)
    council = db_session.query(Candidate).filter_by(council=True).all()
    assert len(council) == 21  # 19 concejales + Carlos Arias y Roberto Ortiz (también candidatos)
    assert len(COUNCILORS) == 19
    erazo = db_session.query(Candidate).filter_by(name="Ana Leidy Erazo Ruiz").one()
    assert erazo.kind == "councilor" and erazo.party == "Pacto Histórico"
    carlos = db_session.query(Candidate).filter_by(name="Carlos Arias").one()
    assert carlos.council is True and carlos.kind == "candidate"  # sigue siendo candidato en las vistas
    ortiz = db_session.query(Candidate).filter_by(name="Roberto Ortiz").one()
    assert ortiz.council is True and ortiz.kind == "candidate"


def test_councilors_are_matched_but_excluded_from_candidate_views(db_session):
    from src.queries import summary
    seed(db_session)
    src = db_session.query(Source).filter_by(name="Google News").one()
    ingest(db_session, src, ListConnector([
        RawItem(external_id="a", text="Ana Leidy Erazo Ruiz pidió un debate de control", url="https://x/a"),
    ]))
    m = db_session.query(Mention).filter_by(external_id="a").one()
    assert m.candidate.name == "Ana Leidy Erazo Ruiz"
    assert all(r["name"] != "Ana Leidy Erazo Ruiz" for r in summary(db_session, days=7))  # vista de candidatos intacta


def test_source_can_scope_terms_to_candidates_only(db_session):
    seed(db_session)
    yt = Source(type=SourceType.YOUTUBE, name="YT solo candidatos", config={"terms_for": "candidates"})
    db_session.add(yt)
    db_session.commit()
    conn = ListConnector([])
    ingest(db_session, yt, conn)
    assert "Carlos Arias" in conn.terms and "Ana Leidy Erazo Ruiz" not in conn.terms
    gn = db_session.query(Source).filter_by(name="Google News").one()
    conn2 = ListConnector([])
    ingest(db_session, gn, conn2)
    assert "Ana Leidy Erazo Ruiz" in conn2.terms  # prensa (gratis) sí cubre a los concejales


def test_council_overview_groups_by_party(db_session):
    from src.queries import council_overview
    seed(db_session)
    src = db_session.query(Source).filter_by(name="Google News").one()
    now = dt.datetime.utcnow()
    people = [("Ana Leidy Erazo Ruiz", "negative", -0.7), ("María del Carmen Londoño", "positive", 0.5),
              ("Audry María Toro Echavarría", "positive", 0.4)]
    for i, (name, label, score) in enumerate(people):
        c = db_session.query(Candidate).filter_by(name=name).one()
        m = Mention(candidate_id=c.id, source_id=src.id, external_id=f"m{i}", text=name, url=f"https://x/{i}",
                    published_at=now, fetched_at=now, raw={})
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel(label), score=score, topic="t", model="f", category="seguridad"))
    db_session.commit()
    o = council_overview(db_session, days=7)
    members = {r["name"]: r for r in o["members"]}
    assert members["Ana Leidy Erazo Ruiz"]["mentions"] == 1 and members["Ana Leidy Erazo Ruiz"]["negative"] == 1
    assert members["Ana Leidy Erazo Ruiz"]["party"] == "Pacto Histórico"
    parties = {r["party"]: r for r in o["parties"]}
    assert parties["Pacto Histórico"]["mentions"] == 2 and parties["Pacto Histórico"]["members"] == 3
    assert parties["Partido de la U"]["members"] == 4  # Audry, Tania, Henry + Carlos Arias
