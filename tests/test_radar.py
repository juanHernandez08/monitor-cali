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


# ---------- retiros automáticos: la lista se actualiza sola ----------

def _withdraw_titles(name):
    return (f"{name} descarta aspirar a la Alcaldía de Cali - Diario Occidente",
            f"{name} no será candidato a la Alcaldía de Cali - El País")


def test_withdrawal_cues_are_recognized_and_ordinary_news_is_not():
    from src.radar import extract
    for t in ["Wilson Ruiz descarta aspirar a la Alcaldía de Cali", "Diana Rojas se retira de la contienda por la Alcaldía de Cali",
              "Gustavo Orozco renunció a su aspiración a la Alcaldía de Cali", "Andrés Lozano no será candidato a la Alcaldía de Cali",
              "Angélica Mayolo declina su candidatura a la Alcaldía de Cali", "Marino del Río no aspirará a la Alcaldía de Cali"]:
        assert extract(t)[0]["kind"] == "declino", t
    # «renunciará para ser candidato» y «renunciará a su cargo» son lo CONTRARIO de retirarse
    assert extract("Roger Mina renunciará para ser candidato a la Alcaldía de Cali")[0]["kind"] == "mueve"
    assert extract("Roger Mina renunciará a su gerencia para aspirar a la Alcaldía de Cali")[0]["kind"] == "mueve"


def test_a_watch_person_who_withdraws_leaves_the_lists_with_one_headline_and_can_be_restored(db_session):
    from src import radar, queries
    w = Candidate(name="Wilson Ruiz", aliases=[], kind="watch", status="suena")
    db_session.add(w)
    db_session.commit()
    _press(db_session, _withdraw_titles("Wilson Ruiz")[0], "w1")
    changes = radar.apply_changes(db_session)
    db_session.refresh(w)
    assert [c["change"] for c in changes] == ["retiro"]
    assert (w.kind, w.active, w.status, w.retired_from) == ("retired", False, "declino", "watch")
    o = radar.overview(db_session)
    assert "Wilson Ruiz" not in [p["name"] for p in o["people"]] and o["retired"][0]["name"] == "Wilson Ruiz"
    assert radar.apply_changes(db_session) == []  # no repite
    assert radar.restore(db_session, w.id).kind == "watch" and w.active


def test_a_main_candidate_needs_two_outlets_and_carlos_is_never_removed(db_session):
    from src import radar
    ortiz = Candidate(name="Roberto Ortiz", aliases=[], kind="candidate", status="suena")
    carlos = Candidate(name="Carlos Arias", aliases=[], kind="candidate", status="suena")
    db_session.add_all([ortiz, carlos])
    db_session.commit()
    _press(db_session, "Roberto Ortiz descarta aspirar a la Alcaldía de Cali - Diario Occidente", "o1")
    assert radar.apply_changes(db_session) == []  # un solo medio: se avisa, no se saca
    db_session.refresh(ortiz)
    assert ortiz.kind == "candidate"
    _press(db_session, "Roberto Ortiz no será candidato a la Alcaldía de Cali - El País", "o2", outlet="El País")
    assert [c["name"] for c in radar.apply_changes(db_session)] == ["Roberto Ortiz"]
    db_session.refresh(ortiz)
    assert ortiz.kind == "retired" and ortiz.retired_from == "candidate"
    # Carlos: aunque 2 medios lo digan, solo se avisa
    _press(db_session, "Carlos Arias descarta aspirar a la Alcaldía de Cali - Diario Occidente", "c1")
    _press(db_session, "Carlos Arias no será candidato a la Alcaldía de Cali - El País", "c2", outlet="El País")
    assert radar.apply_changes(db_session) == []
    db_session.refresh(carlos)
    assert carlos.kind == "candidate" and carlos.active


def test_retired_people_disappear_from_charts_and_come_back_when_two_outlets_say_they_are_in(db_session):
    from src import radar, queries
    c = Candidate(name="Mabel Lara", aliases=[], kind="candidate", status="suena")
    db_session.add(c)
    db_session.commit()
    assert "Mabel Lara" in [x["name"] for x in queries.social_candidates(db_session)]
    radar.retire(db_session, c, "prueba")
    assert "Mabel Lara" not in [x["name"] for x in queries.social_candidates(db_session)]
    assert db_session.query(Candidate).filter_by(kind="candidate").count() == 0  # fuera de todo lo que filtra por kind
    _press(db_session, "Mabel Lara confirma su candidatura a la Alcaldía de Cali - Diario Occidente", "m1")
    assert radar.apply_changes(db_session) == []  # un solo medio no la trae de vuelta
    _press(db_session, "Mabel Lara anuncia su candidatura a la Alcaldía de Cali - El País", "m2", outlet="El País")
    assert [x["change"] for x in radar.apply_changes(db_session)] == ["regreso"]
    db_session.refresh(c)
    assert c.kind == "candidate" and c.active and c.status == "oficial"
