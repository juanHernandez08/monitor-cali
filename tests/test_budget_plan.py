import pytest

from src import budget_plan, config


@pytest.fixture(autouse=True)
def base(monkeypatch):
    monkeypatch.setattr(config, "MONTHLY_BUDGET_COP", 300_000)
    monkeypatch.setattr(config, "FIXED_MONTHLY_COP", 67_800)
    monkeypatch.setattr(config, "BUDGET_FX_COP_PER_USD", 3_700)
    monkeypatch.setattr(config, "APIFY_CYCLE_BUDGET_USD", 27)
    monkeypatch.setattr(config, "CLAUDE_MONTHLY_BUDGET_USD", 26)


def test_default_caps_fit_the_300k_budget_with_margin_at_a_conservative_dollar():
    p = budget_plan.worst_case()
    assert p.claude_usd == 26
    assert p.worst_case_cop == round(67_800 + (27 + 26) * 3_700)  # 263.900
    assert p.ok and p.margin_cop > 30_000  # >10 % de colchón por el dólar
    assert p.worst_case_cop < 300_000


def test_claude_is_trimmed_when_apify_plus_claude_would_not_fit(monkeypatch):
    monkeypatch.setattr(config, "APIFY_CYCLE_BUDGET_USD", 50)
    p = budget_plan.worst_case()
    assert p.claude_usd == pytest.approx((300_000 - 67_800) / 3_700 - 50, abs=0.01)  # ~12,76
    assert p.ok and p.worst_case_cop <= 300_000


def test_claude_goes_to_zero_if_apify_alone_exceeds_the_budget(monkeypatch):
    monkeypatch.setattr(config, "APIFY_CYCLE_BUDGET_USD", 80)
    assert budget_plan.claude_limit_usd() == 0.0
    assert budget_plan.worst_case().ok is False


def test_claude_budget_uses_the_trimmed_limit(monkeypatch):
    from src.claude_budget import ClaudeBudget
    monkeypatch.setattr(config, "APIFY_CYCLE_BUDGET_USD", 50)
    assert ClaudeBudget().monthly_usd == pytest.approx(12.76, abs=0.01)


def test_apify_ceiling_end_auto_applies_to_every_cycle():
    import datetime as dt
    from src import apify_budget as ab
    st = ab.Status(used=1.0, cap=30.0, cycle_start=dt.date(2026, 11, 29), cycle_end=dt.date(2026, 12, 28))
    plan = ab.compute_plan(st, dt.date(2026, 11, 30), ceiling=27, ceiling_end="auto", reserve=0.75, interval_hours=24)
    assert plan.ok and plan.ceiling == 27
    old = ab.compute_plan(st, dt.date(2026, 11, 30), ceiling=27, ceiling_end="2026-10-28", reserve=0.75, interval_hours=24)
    assert not old.ok and "ciclo nuevo" in old.reason  # con fecha, sigue fallando cerrado
