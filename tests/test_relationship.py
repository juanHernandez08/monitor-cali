import datetime as dt

from src.models import Candidate, Mention, SentimentLabel, SentimentScore, Source, SourceType


def _setup(db_session):
    carlos = Candidate(name="Carlos Arias", aliases=[], kind="candidate")
    rival = Candidate(name="Roberto Ortiz", aliases=[], kind="candidate")
    social = Source(type=SourceType.SOCIAL, name="Instagram / Facebook (cuentas)")
    news = Source(type=SourceType.RSS, name="Medio local")
    db_session.add_all([carlos, rival, social, news])
    db_session.commit()
    return carlos, rival, social, news


def _m(db_session, cand, src, ext, label, score, author=None, esfera="ciudadanía", kind="comment",
       emotion="felicidad", raw=None, topic="seguridad"):
    now = dt.datetime.utcnow()
    m = Mention(candidate_id=cand.id, source_id=src.id, external_id=ext, text=ext, url=f"https://x/{ext}",
                author=author, raw=raw or {"kind": kind, "platform": "instagram"}, published_at=now, fetched_at=now)
    db_session.add(m)
    db_session.flush()
    db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel[label], score=score, topic=topic,
                                  model="f", emotion=emotion, esfera=esfera))
    return m


def test_nps_digital_counts_promoters_passives_and_detractors_and_skips_non_opinions(db_session):
    from src.relationship import nps_digital
    carlos, rival, social, news = _setup(db_session)
    _m(db_session, carlos, social, "p1", "POSITIVE", 0.8, "ana")       # promotor
    _m(db_session, carlos, social, "p2", "POSITIVE", 0.9, "beto")      # promotor
    _m(db_session, carlos, social, "a1", "POSITIVE", 0.3, "caro")      # pasivo (apoyo tibio)
    _m(db_session, carlos, social, "d1", "NEGATIVE", -0.5, "dani")     # detractor
    _m(db_session, carlos, news, "info", "NEUTRAL", 0.0, emotion="sin emoción marcada", kind=None, raw={})  # informativa: fuera
    _m(db_session, carlos, social, "own", "POSITIVE", 0.9, raw={"kind": "post", "account_candidate": "Carlos Arias"})  # propio: fuera
    # en producción los posts propios solo traen la cuenta de origen, sin account_candidate
    _m(db_session, carlos, social, "own2", "POSITIVE", 0.9, raw={"kind": "post", "account": "https://www.instagram.com/soycarlosaarias/"})
    _m(db_session, carlos, social, "tg", "NEGATIVE", -0.4, "eva", topic="mención tangencial")  # tangencial: fuera
    db_session.commit()
    row = next(r for r in nps_digital(db_session, days=7)["rows"] if r["candidate"] == "Carlos Arias")
    assert (row["n"], row["promoters"], row["passives"], row["detractors"]) == (4, 2, 1, 1)
    assert row["nps"] == 25 and not row["conclusive"]
    assert row["low"] < row["nps"] < row["high"]


def test_relationship_rings_are_aggregated_counts_never_names(db_session):
    from src.relationship import relationship
    carlos, rival, social, news = _setup(db_session)
    for i in range(2):
        _m(db_session, carlos, social, f"fan{i}", "POSITIVE", 0.9, "fan", esfera="líderes comunitarios y JAC")
    _m(db_session, carlos, social, "once", "POSITIVE", 0.7, "una_vez")
    _m(db_session, carlos, social, "mix", "NEUTRAL", 0.0, "dudoso", emotion="sorpresa")
    _m(db_session, carlos, social, "crit", "NEGATIVE", -0.3, "critico")
    for i in range(3):
        _m(db_session, carlos, social, f"op{i}", "NEGATIVE", -0.8, "opositor", esfera="actores políticos")
    _m(db_session, carlos, news, "nota", "NEGATIVE", -0.5, "El País", kind=None, raw={})  # un medio no entra a los anillos
    _m(db_session, carlos, social, "propio", "POSITIVE", 0.9, raw={"kind": "post", "account": "https://www.instagram.com/soycarlosaarias/"})
    db_session.commit()
    r = relationship(db_session, days=7)
    rings = {x["ring"]: x["accounts"] for x in r["rings"]}
    assert rings == {"simpatizantes": 1, "cercanos": 1, "indecisos": 1, "críticos": 1, "opositores": 1}
    assert r["accounts"] == 5 and r["own_accounts"] == 1
    assert "fan" not in str(r) and "opositor" not in str(r).replace("opositores", "")  # sin nombres de cuentas
    matrix = {x["esfera"]: x for x in r["matrix"]}
    assert matrix["líderes comunitarios y JAC"]["simpatizantes"] == 1 and matrix["actores políticos"]["opositores"] == 1
    spheres = {s["esfera"]: s for s in r["spheres"]}
    assert spheres["actores políticos"]["negative_pct"] == 100
    assert {s["source"] for s in r["by_source"]} == {"social", "prensa"}


def test_survey_nps_validates_and_stores_only_totals(db_session):
    from src.relationship import survey_add, survey_delete, survey_list
    ok, err = survey_add(db_session, {"date": "2026-10-15", "scope": "nucleo:oriente", "promoters": 60,
                                      "passives": 25, "detractors": 35, "source": "puerta a puerta"})
    assert err is None and ok["nps"] == 21 and ok["n"] == 120 and ok["conclusive"]
    assert survey_add(db_session, {"date": "15/10/2026", "promoters": 1, "passives": 1, "detractors": 1})[1]
    assert survey_add(db_session, {"date": "2026-10-15", "scope": "nucleo:marte", "promoters": 1, "passives": 1, "detractors": 1})[1]
    assert survey_add(db_session, {"date": "2026-10-15", "scope": "comuna:7", "promoters": 0, "passives": 0, "detractors": 0})[1]
    assert survey_add(db_session, {"date": "2026-10-16", "scope": "comuna:7", "promoters": 3, "passives": 1, "detractors": 1})[0]["scope"] == "comuna:07"
    assert len(survey_list(db_session)) == 2
    assert survey_delete(db_session, ok["id"]) and len(survey_list(db_session)) == 1


def test_sentiment_parser_reads_the_esfera_and_defaults_to_ciudadania():
    from src.sentiment import _parse_payload
    assert _parse_payload('{"label": "positive", "score": 0.5, "esfera": "Gremios y comercio"}', "m").esfera == "gremios y comercio"
    assert _parse_payload('{"label": "positive", "score": 0.5, "esfera": "marcianos"}', "m").esfera == "ciudadanía"


def test_nucleo_of_maps_barrios_comunas_and_corregimientos():
    from src.geo import nucleo_of
    assert nucleo_of("barrio:2003") == "ladera"      # Siloé, comuna 20
    assert nucleo_of("comuna:21") == "oriente"
    assert nucleo_of("vereda:6207") == "rural" and nucleo_of("corregimiento:53") == "rural"
    assert nucleo_of("municipio:76001") is None
