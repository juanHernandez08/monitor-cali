import datetime as dt

from src.models import Candidate, Mention, RadarSuggestion, Source, SourceType


# Titulares reales de la prensa (oct-2026), tal como los guarda Google News.
HEADLINES = [
    ("Guillermo Ulloa entra en el sonajero por la Alcaldía de Cali La falta de un favorito para ganar...", {"Guillermo Ulloa"}),
    ("Maurice Armitage suena -y fuerte- para la Alcaldía de Cali A Maurice Armitage le vienen insistiendo", {"Maurice Armitage"}),
    ("Marino del Río entra en la carrera por la Alcaldía de Cali El sonajero de posibles candidatos", {"Marino del Río"}),
    ("Aspirantes a la Alcaldía de Cali: Juan Martín Bravo va por firmas - Diario Occidente", {"Juan Martín Bravo"}),
    ("Exvicepresidenta Francia Márquez podría ser aspirante a Alcaldía de Cali - El País", {"Francia Márquez"}),
    ("¿Roger Mina renunciará para ser candidato a la Alcaldía de Cali? Graffiti - Diario Occidente", {"Roger Mina"}),
    ("Clara Luz Roldán confirma candidatura a la Alcaldía de Cali por el Partido de La U - Infobae", {"Clara Luz Roldán"}),
    # lo que NO debe proponer
    ("Fabio Arroyave en el sonajero para la Gobernación del Valle - Diario Occidente", set()),  # Gobernación, no Alcaldía
    ("Pacto Histórico busca candidato a la Alcaldía de Cali - occidente.co", set()),
    ("El sonajero para la Alcaldía de Cali y la Gobernación del Valle sigue moviéndose: estos candidatos suenan de izquierda y derecha", set()),
    ("Partido Liberal anuncia candidatura a la Alcaldía de Cali", set()),  # un partido no es una persona
]


def test_extract_proposes_only_people_in_titles_about_the_mayoralty():
    from src.radar import extract
    for title, expected in HEADLINES:
        assert {h["name"] for h in extract(title)} == expected, title


def test_extract_classifies_the_news_type():
    from src.radar import extract
    kind = lambda t: extract(t)[0]["kind"]  # noqa: E731
    assert kind("Juan Martín Bravo va por firmas a la Alcaldía de Cali") == "oficial"
    assert kind("Guillermo Ulloa entra en el sonajero por la Alcaldía de Cali") == "suena"
    assert kind("Roger Mina renunciará para ser candidato a la Alcaldía de Cali") == "mueve"
    assert kind("Wilson Ruiz desiste de su aspiración a la Alcaldía de Cali") == "declino"


def test_extract_handles_decomposed_accents_like_the_ones_google_news_sends():
    import unicodedata
    from src.radar import extract
    t = unicodedata.normalize("NFD", "| ¿Roger Mina renunciará para ser candidato a la Alcaldía de Cali? Graffiti - Diario Occidente")
    assert [h["name"] for h in extract(t)] == ["Roger Mina"]
    t2 = unicodedata.normalize("NFD", "Aspirantes a la Alcaldía de Cali: Juan Martín Bravo va por firmas - Diario Occidente")
    assert [h["name"] for h in extract(t2)] == ["Juan Martín Bravo"]


def _press(db_session, title, ext, days_ago=1, outlet="Diario Occidente"):
    src = db_session.query(Source).filter_by(name=outlet).first()
    if src is None:
        src = Source(type=SourceType.RSS, name=outlet)
        db_session.add(src)
        db_session.commit()
    city = db_session.query(Candidate).filter_by(name="Cali (ciudad)").first()
    if city is None:
        city = Candidate(name="Cali (ciudad)", aliases=[], kind="city")
        db_session.add(city)
        db_session.commit()
    now = dt.datetime.utcnow()
    db_session.add(Mention(candidate_id=city.id, source_id=src.id, external_id=ext, text=title, url=f"https://x/{ext}", raw={},
                           published_at=now - dt.timedelta(days=days_ago), fetched_at=now))
    db_session.commit()


def test_scan_suggests_new_names_but_never_known_ones_and_is_idempotent(db_session):
    from src.radar import scan
    db_session.add_all([Candidate(name="Clara Luz Roldán", aliases=["Clara Roldán"]), Candidate(name="Roger Mina", aliases=[])])
    db_session.commit()
    _press(db_session, "Guillermo Ulloa entra en el sonajero por la Alcaldía de Cali - Diario Occidente", "a")
    _press(db_session, "Guillermo Ulloa entra en el sonajero por la Alcaldía de Cali - Diario Occidente", "a2")  # misma nota repetida
    _press(db_session, "Clara Luz Roldán anuncia su candidatura a la Alcaldía de Cali - calihoy.com", "b")  # ya conocida
    _press(db_session, "¿Roger Mina renunciará para ser candidato a la Alcaldía de Cali? - Diario Occidente", "c")  # ya conocido
    created = scan(db_session)
    assert [r.name for r in created] == ["Guillermo Ulloa"]
    assert db_session.query(RadarSuggestion).one().headlines == 1  # la nota repetida cuenta una vez
    assert scan(db_session) == []  # no duplica


def test_news_reports_changes_of_known_people_and_actions_follow_dismiss_promote(db_session):
    from src import radar
    c = Candidate(name="Roger Mina", aliases=[], kind="candidate", status="suena")
    db_session.add(c)
    db_session.commit()
    _press(db_session, "¿Roger Mina renunciará para ser candidato a la Alcaldía de Cali? - Diario Occidente", "n1")
    n = radar.news(db_session)
    assert n and n[0]["name"] == "Roger Mina" and n[0]["kind"] == "mueve"

    _press(db_session, "Juan Martín Bravo va por firmas a la Alcaldía de Cali - Diario Occidente", "n2")
    radar.scan(db_session)
    sug = db_session.query(RadarSuggestion).one()
    w = radar.follow(db_session, sug.id)
    assert w.kind == "watch" and w.status == "suena" and db_session.get(RadarSuggestion, sug.id).state == "siguiendo"
    assert radar.set_status(db_session, w.id, "oficial", "Confirmó que irá por firmas").status == "oficial"
    assert radar.set_status(db_session, w.id, "inventado") is None  # solo estados válidos

    # promover: los gráficos tienen colores para 9 candidatos (Roger ya es 1)
    for i in range(7):
        db_session.add(Candidate(name=f"Otro {i}", aliases=[], kind="candidate"))
    db_session.commit()
    assert radar.promote(db_session, w.id)[0].kind == "candidate"  # el noveno cabe
    w2 = Candidate(name="Diana Rojas", aliases=[], kind="watch")
    db_session.add(w2)
    db_session.commit()
    c2, err = radar.promote(db_session, w2.id)
    assert c2 is None and "9" in err  # el décimo no
    assert radar.archive(db_session, w2.id) and not db_session.get(Candidate, w2.id).active


def test_overview_counts_headlines_by_text_and_lists_the_calendar(db_session):
    from src import radar
    db_session.add(Candidate(name="Juan Martín Bravo", aliases=[], kind="watch", status="oficial", status_note="Va por firmas"))
    db_session.commit()
    _press(db_session, "Juan Martín Bravo va por firmas a la Alcaldía de Cali - Diario Occidente", "o1")
    _press(db_session, "Aspirantes a la Alcaldía: Juan Martín Bravo y Clara Luz Roldán - El País", "o2", outlet="El País")
    o = radar.overview(db_session)
    p = next(x for x in o["people"] if x["name"] == "Juan Martín Bravo")
    assert p["headlines"] == 2 and p["outlets"] == 2 and p["last"]["url"]
    assert o["days_to_election"] > 0 and len(o["calendar"]) == 3


def test_seed_creates_the_watchlist_without_touching_candidates(db_session):
    from scripts.seed_sources import seed
    seed(db_session)
    watch = {c.name for c in db_session.query(Candidate).filter_by(kind="watch")}
    assert {"Juan Martín Bravo", "Alejandro Ocampo", "Maurice Armitage"} <= watch
    clara = db_session.query(Candidate).filter_by(name="Clara Luz Roldán").one()
    assert clara.kind == "candidate" and clara.status == "oficial"
    seed(db_session)  # idempotente
    assert db_session.query(Candidate).filter_by(name="Alejandro Ocampo").count() == 1


def test_watch_people_are_searched_in_free_sources_but_not_in_youtube():
    """Cuota de YouTube: 100 unidades por nombre y corrida. El radar no debe gastarla."""
    import inspect
    from src import pipeline
    assert 'c.kind == "candidate"' in inspect.getsource(pipeline.ingest)  # terms_for=candidates solo busca candidatos
