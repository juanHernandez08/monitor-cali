"""Presupuesto en dólares de Apify (src/apify_budget.py): cumplir el tope aprobado es requisito para
que el cliente renueve la aprobación del proyecto, así que todo falla CERRADO."""
import datetime as dt

from src import apify_budget as ab
from src.models import Run, Source, SourceType

TODAY = dt.date(2026, 10, 4)


def _status(used=13.85, cap=19.0, end=dt.date(2026, 10, 28)):
    return ab.Status(used=used, cap=cap, cycle_start=dt.date(2026, 9, 29), cycle_end=end)


def _plan(status, **kw):
    kw.setdefault("ceiling", 19.0)
    kw.setdefault("ceiling_end", "2026-10-28")
    kw.setdefault("reserve", 0.75)
    kw.setdefault("interval_hours", 24)
    return ab.compute_plan(status, TODAY, **kw)


def test_plan_spreads_what_is_left_over_the_remaining_days_after_the_reserve():
    p = _plan(_status())
    # 19 - 13,85 - 0,75 = 4,40 disponibles, 25 días contando hoy
    assert p.ok and p.days_left == 25 and p.available == 4.40
    assert abs(p.job_budget - 4.40 / 25) < 1e-3


def test_a_skipped_job_leaves_its_money_to_be_shared_by_the_remaining_ones_never_spent_at_once():
    today = _plan(_status(used=13.85))
    skipped_two_days = ab.compute_plan(_status(used=13.85), TODAY + dt.timedelta(days=2), ceiling=19.0, ceiling_end="2026-10-28",
                                       reserve=0.75, interval_hours=24)
    assert skipped_two_days.job_budget > today.job_budget          # el reparto sube un poco...
    assert skipped_two_days.job_budget < 2 * today.job_budget      # ...pero nunca se gasta de golpe lo acumulado


def test_ceiling_is_the_smaller_of_the_apify_cap_and_the_configured_budget():
    assert _plan(_status(cap=19.0), ceiling=27.0).ceiling == 19.0   # recarga sin subir el tope en Apify
    assert _plan(_status(cap=40.0), ceiling=27.0).ceiling == 27.0   # tope de Apify más alto que lo aprobado


def test_plan_fails_closed_when_balance_cannot_be_read():
    p = _plan(None)
    assert not p.ok and p.job_budget == 0


def test_plan_fails_closed_on_a_new_billing_cycle_until_a_new_budget_is_confirmed():
    p = _plan(_status(used=0.0, end=dt.date(2026, 11, 28)))
    assert not p.ok and "ciclo nuevo" in p.reason


def test_plan_fails_closed_when_only_the_reserve_is_left():
    assert not _plan(_status(used=18.5)).ok


def test_select_accounts_prioritizes_carlos_then_rivals_then_councilors_and_skips_media():
    accounts = [
        {"platform": "instagram", "url": "u/media", "candidate": None},
        {"platform": "instagram", "url": "u/conc", "candidate": "Concejal Uno"},
        {"platform": "instagram", "url": "u/rival", "candidate": "Rival Uno"},
        {"platform": "instagram", "url": "u/carlos", "candidate": "Carlos Arias"},
    ]
    kinds = {"Carlos Arias": "candidate", "Rival Uno": "candidate", "Concejal Uno": "councilor"}
    pending = [{"candidate": "Carlos Arias", "url": "p1"}]
    chosen, comment_posts, spent = ab.select_accounts(accounts, kinds, {}, 1.0, "Carlos Arias", pending, 30)
    assert [a["url"] for a in chosen] == ["u/carlos", "u/rival", "u/conc"]  # medios fuera por defecto
    assert comment_posts == 1 and spent > 0
    # con poco dinero: primero Carlos y sus comentarios; lo demás espera
    tight = ab.COST_IG_ACCOUNT + ab.comment_post_cost(30) + 0.001
    chosen, comment_posts, _ = ab.select_accounts(accounts, kinds, {}, tight, "Carlos Arias", pending, 30)
    assert [a["url"] for a in chosen] == ["u/carlos"] and comment_posts == 1


def test_select_accounts_rotates_oldest_first_and_never_exceeds_the_budget():
    accounts = [{"platform": "instagram", "url": f"u/{i}", "candidate": f"R{i}"} for i in range(5)]
    kinds = {f"R{i}": "candidate" for i in range(5)}
    last = {"u/0": "2026-10-04", "u/1": "2026-10-01", "u/2": "2026-10-03", "u/3": "2026-09-20", "u/4": "2026-10-02"}
    budget = 2.5 * ab.COST_IG_ACCOUNT
    chosen, _, spent = ab.select_accounts(accounts, kinds, last, budget, "Carlos Arias", [], 30)
    assert [a["url"] for a in chosen] == ["u/3", "u/1"] and spent <= budget


def test_job_spend_stops_when_real_spend_reaches_the_job_budget():
    seen = {"used": 10.0}
    spend = ab.JobSpend("t", budget=0.10, start_used=10.0, status_fn=lambda token: _status(used=seen["used"]))
    assert spend.remaining() > 0
    seen["used"] = 10.11  # Apify ya cobró más de lo presupuestado
    assert spend.remaining() == 0


def test_job_spend_uses_the_conservative_estimate_when_apify_cannot_be_queried():
    spend = ab.JobSpend("t", budget=0.05, start_used=10.0, status_fn=lambda token: None)
    spend.consume(30)  # 30 resultados: 0,002 + 30 * 0,003 = 0,092 > 0,05
    assert spend.remaining() == 0


def _social_source(db_session):
    src = Source(type=SourceType.SOCIAL, name="IG")
    db_session.add(src)
    db_session.commit()
    return src


def test_social_run_is_skipped_if_the_last_one_was_less_than_the_minimum_hours_ago(db_session, monkeypatch):
    """"Actualizar ahora" (o un reinicio) no puede disparar otra vuelta de pago el mismo día."""
    import src.scheduler as m
    monkeypatch.setattr(ab, "fetch_status", lambda token, timeout=20: _status())
    monkeypatch.setattr(m.config, "APIFY_CYCLE_BUDGET_END", "2026-10-28")
    src = _social_source(db_session)
    db_session.add(Run(source_id=src.id, started_at=dt.datetime.utcnow() - dt.timedelta(hours=3)))
    db_session.commit()
    assert m._apify_budget_run(db_session, src, "token", [], {}) is None


def test_social_run_goes_ahead_with_a_budget_when_enough_time_has_passed(db_session, monkeypatch):
    import src.scheduler as m
    monkeypatch.setattr(ab, "fetch_status", lambda token, timeout=20: _status())
    monkeypatch.setattr(m.config, "APIFY_CYCLE_BUDGET_END", "2026-10-28")
    monkeypatch.setattr(m.config, "SOCIAL_ACCOUNTS", [{"platform": "instagram", "url": "u/c", "candidate": "Carlos Arias"}])
    src = _social_source(db_session)
    db_session.add(Run(source_id=src.id, started_at=dt.datetime.utcnow() - dt.timedelta(hours=25)))
    db_session.commit()
    run = m._apify_budget_run(db_session, src, "token", [], {})
    assert run is not None and [a["url"] for a in run["accounts"]] == ["u/c"]
    assert run["plan"].job_budget > 0 and run["spend"].budget == run["plan"].job_budget


def test_social_run_is_blocked_and_nothing_is_spent_when_the_balance_cannot_be_checked(db_session, monkeypatch):
    import src.scheduler as m
    monkeypatch.setattr(ab, "fetch_status", lambda token, timeout=20: None)
    src = _social_source(db_session)
    assert m._apify_budget_run(db_session, src, "token", [], {}) is None
