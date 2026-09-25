from src.institutional_history import ADMINISTRATIONS, status_counts, debt_timeline


def test_four_administrations_in_chronological_order():
    periods = [a["period"] for a in ADMINISTRATIONS]
    assert periods == ["2012-2015", "2016-2019", "2020-2023", "2024-2027"]


def test_every_project_has_a_source_url_and_valid_status():
    valid_statuses = {"completado", "en curso", "incompleto"}
    for admin in ADMINISTRATIONS:
        for p in admin["projects"]:
            assert p["status"] in valid_statuses, f"{admin['mayor']}: estado inválido en {p['name']}"
            assert p["source"]["url"].startswith("http"), f"{admin['mayor']}: sin fuente en {p['name']}"
            assert p["source"]["name"], f"{admin['mayor']}: sin nombre de fuente en {p['name']}"


def test_every_metric_has_a_source():
    for admin in ADMINISTRATIONS:
        for m in admin["metrics"]:
            assert m["source"]["url"].startswith("http"), f"{admin['mayor']}: métrica sin fuente ({m['label']})"


def test_debt_entries_that_have_a_figure_also_have_a_source():
    for admin in ADMINISTRATIONS:
        debt = admin.get("debt")
        if debt and debt.get("value_billones_cop") is not None:
            assert debt["source"]["url"].startswith("http"), f"{admin['mayor']}: deuda sin fuente"


def test_only_the_current_administration_is_marked_en_curso():
    in_progress = [a["mayor"] for a in ADMINISTRATIONS if a["status"] == "en curso"]
    assert in_progress == ["Alejandro Eder Garcés"]


def test_status_counts_tallies_projects_by_status():
    ospina = next(a for a in ADMINISTRATIONS if "Ospina" in a["mayor"])
    counts = status_counts(ospina)
    assert counts["completado"] + counts["en curso"] + counts["incompleto"] == len(ospina["projects"])


def test_debt_timeline_only_includes_administrations_with_a_sourced_figure():
    timeline = debt_timeline()
    periods = [d["period"] for d in timeline]
    assert periods == ["2020-2023", "2024-2027"]  # Guerrero y Armitage no tienen cifra verificada
    assert timeline[0]["value_billones_cop"] == 3.2
    assert timeline[1]["value_billones_cop"] == 3.5
