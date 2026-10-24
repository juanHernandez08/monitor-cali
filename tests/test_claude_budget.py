import contextlib
import json
from types import SimpleNamespace

import pytest

from src import claude_budget as cb
from src.claude_budget import BudgetExceeded, ClaudeBudget, cost_usd
from src.models import Candidate, Mention, SentimentScore, Source, SourceType
from src.sentiment import ContentError, SentimentEngine


@pytest.fixture
def budget(db_session, monkeypatch):
    @contextlib.contextmanager
    def fake_session():
        yield db_session

    monkeypatch.setattr(cb, "get_session", fake_session)
    from src import notify
    sent = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: sent.append(a[1]) or True)
    b = ClaudeBudget(monthly_usd=1.0, fallback_model="claude-haiku-5-5")
    b.sent = sent
    return b


def usage(i=0, o=0, cw=0, cr=0):
    return SimpleNamespace(input_tokens=i, output_tokens=o, cache_creation_input_tokens=cw, cache_read_input_tokens=cr)


def test_cost_uses_model_prices_and_cache_discounts():
    # Sonnet 5.5: 2 USD/M entrada, 10 USD/M salida; lectura de caché 0,1x; escritura 1,25x
    assert cost_usd("claude-sonnet-5-5", usage(i=1_000_000)) == pytest.approx(2.0)
    assert cost_usd("claude-sonnet-5-5", usage(o=1_000_000)) == pytest.approx(10.0)
    assert cost_usd("claude-sonnet-5-5", usage(cr=1_000_000)) == pytest.approx(0.2)
    assert cost_usd("claude-sonnet-5-5", usage(cw=1_000_000)) == pytest.approx(2.5)
    # escritura de caché de 1 hora = 2x entrada (cuando la API desglosa por duración)
    u = usage(cw=1_000_000)
    u.cache_creation = SimpleNamespace(ephemeral_1h_input_tokens=1_000_000, ephemeral_5m_input_tokens=0)
    assert cost_usd("claude-sonnet-5-5", u) == pytest.approx(4.0)
    u.cache_creation = SimpleNamespace(ephemeral_1h_input_tokens=400_000, ephemeral_5m_input_tokens=600_000)
    assert cost_usd("claude-sonnet-5-5", u) == pytest.approx(2 * (0.8 + 0.75))
    assert cost_usd("claude-haiku-5-5", usage(i=1_000_000, o=1_000_000)) == pytest.approx(0.6)
    assert cost_usd("modelo-desconocido", usage(i=1_000_000)) == pytest.approx(3.0)  # se cuenta caro, nunca barato
    assert cost_usd("claude-sonnet-5-5", None) == 0.0
    assert cost_usd("claude-sonnet-5-5", SimpleNamespace()) == 0.0


def test_spend_accumulates_per_month_and_ignores_other_months(budget, db_session):
    from src.models import ApiUsage
    db_session.add(ApiUsage(service=cb.SERVICE, day="2020-01-05", count=9_000_000))  # otro mes: no cuenta
    db_session.commit()
    assert budget.spent() == 0.0
    budget.add("claude-sonnet-5-5", usage(i=100_000, o=10_000))  # 0,2 + 0,1
    budget.add("claude-sonnet-5-5", usage(i=100_000, o=10_000))
    assert budget.spent() == pytest.approx(0.6, abs=1e-4)


def test_model_degrades_to_the_cheap_one_at_the_cap_and_warns_once(budget):
    assert budget.model_for("claude-sonnet-5-5") == "claude-sonnet-5-5"
    budget.add("claude-sonnet-5-5", usage(o=85_000))  # 0,85 USD = 85 % del tope de 1 USD
    assert budget.model_for("claude-sonnet-5-5") == "claude-sonnet-5-5"
    assert budget.model_for("claude-sonnet-5-5") == "claude-sonnet-5-5"
    assert len([t for t in budget.sent if "80 %" in t]) == 1  # avisa una sola vez al mes
    budget.add("claude-sonnet-5-5", usage(o=20_000))  # 1,05 USD: pasó el tope
    assert budget.model_for("claude-sonnet-5-5") == "claude-haiku-5-5"
    assert budget.model_for("claude-sonnet-5-5") == "claude-haiku-5-5"
    assert len([t for t in budget.sent if "alcanzado" in t]) == 1
    assert budget.status()["degraded"] is True


def test_hard_stop_far_above_the_cap(budget):
    budget.add("claude-sonnet-5-5", usage(o=160_000))  # 1,6 USD >= 1,5 x tope
    with pytest.raises(BudgetExceeded):
        budget.model_for("claude-sonnet-5-5")


def test_api_errors_about_credit_or_key_alert_once_per_day(budget):
    credit = SimpleNamespace(status_code=400)
    credit.__str__ = None  # no se usa: el texto sale del mensaje
    class Err(Exception):
        status_code = 400
    budget.report_api_error(Err("Your credit balance is too low to access the Anthropic API"))
    budget.report_api_error(Err("Your credit balance is too low to access the Anthropic API"))
    assert len([t for t in budget.sent if "saldo" in t]) == 1
    class Auth(Exception):
        status_code = 401
    budget.report_api_error(Auth("invalid x-api-key"))
    assert any("clave" in t for t in budget.sent)
    class Other(Exception):
        status_code = 400
    n = len(budget.sent)
    budget.report_api_error(Other("max_tokens: 0 es inválido"))  # un 400 cualquiera no es de saldo
    assert len(budget.sent) == n


class FakeClient:
    def __init__(self, content, use=None):
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)
        self._content, self._use = content, use

    def _create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(content=self._content, usage=self._use, stop_reason="end_turn")


def _text(d):
    return [SimpleNamespace(type="text", text=json.dumps(d))]


def test_engine_charges_the_budget_and_uses_the_degraded_model(budget):
    client = FakeClient(_text({"label": "neutral", "score": 0.0, "topic": "x"}), usage(i=1000, o=100))
    engine = SentimentEngine(classify_model="claude-sonnet-5-5", client=client, budget=budget)
    r = engine.score("texto")
    assert r.model == "claude-sonnet-5-5" and client.calls[0]["output_config"] == {"effort": "low"}
    assert budget.spent() > 0
    budget.add("claude-sonnet-5-5", usage(o=105_000))  # pasa el tope (1 USD) sin llegar al tope duro (1,5 USD)
    r = engine.score("texto")
    assert r.model == "claude-haiku-5-5" and client.calls[-1]["model"] == "claude-haiku-5-5"
    assert client.calls[-1]["output_config"] == {"effort": "low"}  # Haiku 5.5 sí acepta effort (el 4.5 no)


def test_haiku_4_5_still_omits_effort(budget):
    client = FakeClient(_text({"label": "neutral", "score": 0.0, "topic": "x"}))
    SentimentEngine(classify_model="claude-haiku-4-5", client=client, budget=budget).score("texto")
    assert "output_config" not in client.calls[0]


def test_refusal_without_text_is_a_content_error_not_an_api_failure(budget):
    client = FakeClient([SimpleNamespace(type="thinking", thinking="")])
    with pytest.raises(ContentError):
        SentimentEngine(client=client, budget=budget).score("texto")


def test_a_content_error_does_not_block_the_queue_and_is_set_aside_after_three_tries(db_session):
    from src import pipeline
    pipeline._content_failures.clear()
    c = Candidate(name="Carlos Arias", aliases=[], kind="candidate")
    s = Source(type=SourceType.RSS, name="x", config={})
    db_session.add_all([c, s])
    db_session.flush()
    bad = Mention(candidate_id=c.id, source_id=s.id, external_id="1", text="texto que Claude rechaza", url="u1")
    good = Mention(candidate_id=c.id, source_id=s.id, external_id="2", text="otra mención", url="u2")
    db_session.add_all([bad, good])
    db_session.commit()

    class Engine:
        def score(self, text, candidate=None, city=False):
            if "rechaza" in text:
                raise ContentError("sin texto")
            from src.sentiment import SentimentResult
            from src.models import SentimentLabel
            return SentimentResult(label=SentimentLabel.NEUTRAL, score=0.0, topic="x", model="m")

    for _ in range(3):
        pipeline.score_pending(db_session, Engine())
    db_session.refresh(bad)
    db_session.refresh(good)
    assert good.sentiment is not None  # la de atrás se clasificó aunque la primera fallara
    assert bad.relevant is False and bad.sentiment.model == "error" and bad.sentiment.topic == "no clasificable"


def test_an_api_failure_still_stops_the_cycle_and_retries_next_time(db_session):
    from src import pipeline
    c = Candidate(name="Carlos Arias", aliases=[], kind="candidate")
    s = Source(type=SourceType.RSS, name="x", config={})
    db_session.add_all([c, s])
    db_session.flush()
    m = Mention(candidate_id=c.id, source_id=s.id, external_id="1", text="texto", url="u1")
    db_session.add(m)
    db_session.commit()

    class Down:
        def score(self, *a, **k):
            raise ConnectionError("sin red")

    assert pipeline.score_pending(db_session, Down()) == 0
    assert db_session.query(SentimentScore).count() == 0  # sigue pendiente


def test_score_backlog_alert_fires_once_and_clears(db_session, monkeypatch):
    from src import notify
    sent = []
    monkeypatch.setattr(notify, "send", lambda topic, title, *a, **k: sent.append(title) or True)
    notify.check_score_backlog(db_session, 10)
    assert sent == []
    notify.check_score_backlog(db_session, 100)
    notify.check_score_backlog(db_session, 120)  # dentro de las 6 horas: no repite
    assert sent == ["🟠 Menciones sin clasificar"]
    notify.check_score_backlog(db_session, 3)
    assert sent[-1] == "✅ Clasificación al día"
