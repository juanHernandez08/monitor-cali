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


def test_councilors_require_local_context_and_exclude_armed_group(db_session, monkeypatch):
    """Los nombres de concejales son comunes: exigen contexto local y descartan homónimos conocidos."""
    from src.enrich import enrich_pending
    from src.matching import has_required_context
    seed(db_session)
    patino = db_session.query(Candidate).filter_by(name="Carlos Ariel Patiño").one()
    assert patino.context_terms == ["Cali", "Concejo"]
    assert has_required_context("El concejal habló en el Concejo de Cali", patino)
    assert not has_required_context("Combates en El Tambo, Cauca", patino)

    src = db_session.query(Source).filter_by(name="Google News").one()
    ingest(db_session, src, ListConnector([
        RawItem(external_id="g1", text="Condenan a integrante del Frente Carlos Patiño por atentado", url="https://news.google.com/rss/articles/A"),
        RawItem(external_id="g2", text="Carlos Ariel Patiño pidió un debate", url="https://news.google.com/rss/articles/B"),
        RawItem(external_id="g3", text="Carlos Ariel Patiño en evento", url="https://news.google.com/rss/articles/C"),
    ]))
    assert db_session.query(Mention).filter_by(external_id="g1").first() is None  # exclusión: grupo armado

    import src.enrich as m
    monkeypatch.setattr(m, "resolve_url", lambda url: url.replace("news.google.com/rss/articles/", "medio.co/"))
    monkeypatch.setattr(m, "fetch_article", lambda url: (("Carlos Ariel Patiño intervino en el Concejo de Cali.", None)
                                                         if url.endswith("/B") else ("Carlos Ariel Patiño en un acto en Popayán, Cauca.", None)))
    enrich_pending(db_session, limit=10)
    assert db_session.query(Mention).filter_by(external_id="g2").one().relevant is True
    assert db_session.query(Mention).filter_by(external_id="g3").one().relevant is False  # sin contexto local


def test_recompute_relevance_does_not_apply_press_rules_to_social(db_session):
    """Un comentario "👏" en el post del propio candidato no nombra a nadie, pero es relevante."""
    from scripts.recompute_relevance import recompute
    seed(db_session)
    carlos = db_session.query(Candidate).filter_by(name="Carlos Arias").one()
    ig = Source(type=SourceType.SOCIAL, name="IG")
    db_session.add(ig)
    db_session.commit()
    now = dt.datetime.utcnow()
    m = Mention(candidate_id=carlos.id, source_id=ig.id, external_id="ig:comment:1", text="👏👏",
                raw={"kind": "comment", "account_candidate": "Carlos Arias", "post_title": "x"},
                published_at=now, fetched_at=now, relevant=False)
    db_session.add(m)
    db_session.flush()
    db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.POSITIVE, score=0.5, topic="apoyo", model="f", category="otro"))
    db_session.commit()
    restored, dropped = recompute(db_session, only_council=True)
    assert restored == 1 and dropped == 0
    assert db_session.query(Mention).filter_by(external_id="ig:comment:1").one().relevant is True


def _yt_comment(db_session, candidate, source, ext, text, video_title, topic, label="negative",
                video_about_candidate=None, relevant=True):
    now = dt.datetime.utcnow()
    raw = {"kind": "comment", "video_id": "v1", "video_title": video_title}
    if video_about_candidate is not None:
        raw["video_about_candidate"] = video_about_candidate
    m = Mention(candidate_id=candidate.id, source_id=source.id, external_id=ext, text=text,
                raw=raw, published_at=now, fetched_at=now, relevant=relevant)
    db_session.add(m)
    db_session.flush()
    db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel(label), score=-0.5, topic=topic,
                                  model="f", category="otro"))
    db_session.commit()
    return m


def test_recompute_drops_youtube_comment_on_unrelated_video_regardless_of_llm_topic(db_session):
    """Caso real 2026-09-25: video de un temblor que no nombra a Carlos; el comentario tampoco lo
    nombra, pero el LLM lo etiquetó "rechazo e insultos" (no "tangencial"), así que el filtro por
    tema no lo agarraba. La regla nueva no depende de cómo lo haya clasificado el modelo."""
    from scripts.recompute_relevance import recompute
    seed(db_session)
    carlos = db_session.query(Candidate).filter_by(name="Carlos Arias").one()
    yt = Source(type=SourceType.YOUTUBE, name="YT")
    db_session.add(yt)
    db_session.commit()
    m = _yt_comment(db_session, carlos, yt, "yt:comment:1",
                    "Yo soy de Colombia sé cada uno de los temblores y la magnitud fue de 7.4, mentirosa",
                    "Temblor de 4.4 sacude a Cali: evacúan edificios del centro", topic="rechazo e insultos")
    restored, dropped = recompute(db_session, only_council=True)
    assert dropped == 1 and restored == 0
    assert m.relevant is False


def test_recompute_keeps_youtube_comment_when_video_names_the_candidate(db_session):
    from scripts.recompute_relevance import recompute
    seed(db_session)
    carlos = db_session.query(Candidate).filter_by(name="Carlos Arias").one()
    yt = Source(type=SourceType.YOUTUBE, name="YT")
    db_session.add(yt)
    db_session.commit()
    m = _yt_comment(db_session, carlos, yt, "yt:comment:2", "Ese señor no ha hecho nada",
                    "Carlos Arias, concejal de Cali, habla de la reconstrucción", topic="rechazo e insultos")
    restored, dropped = recompute(db_session, only_council=True)
    assert dropped == 0
    assert m.relevant is True


def test_recompute_keeps_youtube_comment_that_names_the_candidate_even_if_video_does_not(db_session):
    from scripts.recompute_relevance import recompute
    seed(db_session)
    carlos = db_session.query(Candidate).filter_by(name="Carlos Arias").one()
    yt = Source(type=SourceType.YOUTUBE, name="YT")
    db_session.add(yt)
    db_session.commit()
    m = _yt_comment(db_session, carlos, yt, "yt:comment:3", "Carlos Arias debería resolver esto ya",
                    "Temblor de 4.4 sacude a Cali", topic="reconstrucción")
    restored, dropped = recompute(db_session, only_council=True)
    assert dropped == 0
    assert m.relevant is True


def test_recompute_trusts_the_stored_video_about_candidate_flag_over_recomputing_it(db_session):
    """Si el conector ya guardó la marca (dato reciente), se usa esa en vez de re-evaluar el
    título contra los alias — evita falsos positivos si el título cambió de forma en el tiempo."""
    from scripts.recompute_relevance import recompute
    seed(db_session)
    carlos = db_session.query(Candidate).filter_by(name="Carlos Arias").one()
    yt = Source(type=SourceType.YOUTUBE, name="YT")
    db_session.add(yt)
    db_session.commit()
    m = _yt_comment(db_session, carlos, yt, "yt:comment:4", "que bueno", "Temblor en Cali",
                    topic="apoyo", label="positive", video_about_candidate=True)
    restored, dropped = recompute(db_session, only_council=True)
    assert dropped == 0
    assert m.relevant is True


def test_recompute_drops_press_note_the_llm_tagged_as_homonimo(db_session):
    """Caso real 2026-09-25: una nota sobre 'Francisco Piedrahita Plata' quedó con topic
    'homónimo' (el LLM la reconoció como de otra persona) pero recompute la dejaba relevant=True
    porque la rama de prensa solo miraba exclusions/contexto, nunca el topic. pipeline.py sí lo
    aplica al puntuar en vivo; recompute debe honrar la misma señal, no solo redes/YouTube."""
    from scripts.recompute_relevance import recompute
    seed(db_session)
    carlos = db_session.query(Candidate).filter_by(name="Carlos Arias").one()
    press = db_session.query(Source).filter_by(type=SourceType.GOOGLE_NEWS).first()
    now = dt.datetime.utcnow()
    m = Mention(candidate_id=carlos.id, source_id=press.id, external_id="g-homonimo",
                text="Francisco Piedrahita Plata: el caleño universal", body=None,
                url="https://x/1", published_at=now, fetched_at=now, relevant=True)
    db_session.add(m)
    db_session.flush()
    db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.NEUTRAL, score=0.0,
                                  topic="homónimo", model="f", category="otro"))
    db_session.commit()
    restored, dropped = recompute(db_session, only_council=True)
    assert dropped == 1
    assert m.relevant is False


def test_recompute_drops_press_note_whose_title_never_names_candidate_even_with_empty_body(db_session):
    """Mismo bug encontrado y corregido en enrich.py (auditoría 2026-09-26): body="" (intentado
    sin éxito) es distinto de body=None (pendiente), pero `is_relevant` los trataba igual y nunca
    exigía el nombre/contexto cuando el cuerpo no se pudo descargar. Con body=None sí debe seguir
    dando el beneficio de la duda (aún no se intentó enriquecer)."""
    from scripts.recompute_relevance import recompute
    seed(db_session)
    carlos = db_session.query(Candidate).filter_by(name="Carlos Arias").one()
    press = db_session.query(Source).filter_by(type=SourceType.GOOGLE_NEWS).first()
    now = dt.datetime.utcnow()
    failed = Mention(candidate_id=carlos.id, source_id=press.id, external_id="g-failed",
                     text="Terremoto sacude Colombia: reportan daños", body="",
                     url="https://x/1", published_at=now, fetched_at=now, relevant=True)
    pending = Mention(candidate_id=carlos.id, source_id=press.id, external_id="g-pending",
                      text="Otra nota sin nombrarlo", body=None,
                      url="https://x/2", published_at=now, fetched_at=now, relevant=True)
    db_session.add_all([failed, pending])
    db_session.commit()
    restored, dropped = recompute(db_session, only_council=True)
    assert dropped == 1
    assert failed.relevant is False  # body="" ya se intentó y el titular tampoco lo nombra
    assert pending.relevant is True  # body=None: aún no se sabe, se enriquecerá luego
