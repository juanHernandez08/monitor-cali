from src import city_history as ch


def test_periods_cover_2008_to_current_administration_without_gaps():
    years = [y for p in ch.PERIODS for y in range(p["start"], p["end"] + 1)]
    assert years[0] == 2008
    assert years == list(range(2008, ch.PERIODS[-1]["end"] + 1))
    assert [p["status"] for p in ch.PERIODS].count("en curso") == 1


def test_every_point_has_a_specific_source():
    for ind in ch.INDICATORS:
        assert ind["domain"] in {d["id"] for d in ch.DOMAINS}
        for pt in ind["points"]:
            src = ch.SOURCES[pt["source"]]
            assert src["url"].startswith("https://"), ind["id"]
            # una URL de portada ("https://www.medio.com") no permite verificar el dato
            assert src["url"].count("/") > 3, f"{ind['id']}: fuente sin ruta específica"
            assert src["name"]


def test_no_duplicated_years_and_values_within_the_period_studied():
    for ind in ch.INDICATORS:
        years = [p["year"] for p in ind["points"]]
        assert len(years) == len(set(years)), ind["id"]
        assert all(ch.BASELINE_YEAR <= y <= ch.CURRENT_YEAR for y in years), ind["id"]


def test_the_five_requested_domains_have_headline_indicators():
    domains = {i["domain"] for i in ch.INDICATORS if i.get("headline")}
    assert domains == {"economico", "social", "seguridad", "salud", "transporte"}


def test_period_stats_uses_the_year_before_taking_office_as_baseline():
    tasa = next(i for i in ch.INDICATORS if i["id"] == "homicidios_tasa")
    guerrero = next(s for s in ch.period_stats(tasa) if s["period"] == "guerrero")
    assert (guerrero["start_year"], guerrero["start"]) == (2011, 84.4)
    assert (guerrero["end_year"], guerrero["end"]) == (2015, 61.9)
    assert guerrero["verdict"] == "mejoró"
    assert guerrero["start_is_inherited"] is True


def test_first_period_without_prior_data_starts_at_its_first_year():
    desempleo = next(i for i in ch.INDICATORS if i["id"] == "desempleo")  # sin dato 2007
    ospina = next(s for s in ch.period_stats(desempleo) if s["period"] == "ospina-1")
    assert ospina["start_year"] == 2008 and ospina["start_is_inherited"] is False
    assert ospina["partial"] is True and ospina["verdict"] == "empeoró"


def test_small_changes_read_as_stable():
    contributivo = next(i for i in ch.INDICATORS if i["id"] == "contributivo")
    armitage = next(s for s in ch.period_stats(contributivo) if s["period"] == "armitage")
    assert armitage["verdict"] == "estable"  # 68,8 a 68,7: -0,1%


def test_verdict_respects_direction_of_improvement():
    mio = next(i for i in ch.INDICATORS if i["id"] == "pasajeros_mio")  # más es mejor
    ospina2 = next(s for s in ch.period_stats(mio) if s["period"] == "ospina-2")
    assert ospina2["delta"] < 0 and ospina2["verdict"] == "empeoró"


def test_conclusions_and_strategies_cite_existing_indicators():
    ids = {i["id"] for i in ch.INDICATORS}
    for block in ch.CONCLUSIONS + ch.STRATEGIES:
        assert block["evidence"] and set(block["evidence"]) <= ids
    for s in ch.STRATEGIES:
        assert s["actions"] and s["viability"] and s["measure"]


def test_events_have_sources_and_fall_inside_a_period():
    for e in ch.EVENTS:
        assert e["source"] in ch.SOURCES
        assert ch.period_of(e["year"]) is not None


def test_payload_is_json_serializable():
    import json
    data = ch.payload()
    json.dumps(data)
    assert len(data["indicators"]) == len(ch.INDICATORS)
    assert {b["period"] for b in data["balance"]} == {p["id"] for p in ch.PERIODS}
