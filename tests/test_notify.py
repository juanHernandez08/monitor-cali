import datetime as dt

from src import notify
from src.models import Candidate, Source, SourceType, Mention, SentimentScore, SentimentLabel


def test_send_without_topic_makes_no_network_call(monkeypatch):
    calls = []
    monkeypatch.setattr(notify.requests, "post", lambda *a, **k: calls.append((a, k)))
    assert notify.send(None, "t", "m") is False
    assert calls == []


def test_send_posts_json_payload(monkeypatch):
    seen = {}

    class R:
        def raise_for_status(self): pass
    def fake_post(url, json, timeout):
        seen["url"], seen["json"] = url, json
        return R()
    monkeypatch.setattr(notify.requests, "post", fake_post)

    ok = notify.send("mi-topic", "Título", "cuerpo", priority=4, tags=["warning"])
    assert ok is True
    assert seen["json"]["topic"] == "mi-topic"
    assert seen["json"]["title"] == "Título"
    assert seen["json"]["priority"] == 4
    assert seen["json"]["tags"] == ["warning"]


def test_send_swallows_network_errors(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("no network")
    monkeypatch.setattr(notify.requests, "post", boom)
    assert notify.send("t", "title", "msg") is False


def _seed_mention(db_session, candidate, score, ext_id="m1"):
    src = db_session.query(Source).first()
    if src is None:
        src = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
        db_session.add(src)
        db_session.commit()
    m = Mention(candidate_id=candidate.id, source_id=src.id, external_id=ext_id, text="texto negativo",
                url=f"https://x/{ext_id}", fetched_at=dt.datetime.utcnow())
    db_session.add(m)
    db_session.flush()
    db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.NEGATIVE, score=score, model="fake"))
    db_session.commit()
    return m


def test_check_negative_mentions_notifies_once_then_dedupes(db_session, monkeypatch):
    carlos = Candidate(name="Carlos Arias", party="U", aliases=[])
    db_session.add(carlos)
    db_session.commit()
    _seed_mention(db_session, carlos, -0.9)

    sent = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: sent.append(a) or True)

    assert notify.check_negative_mentions(db_session) == 1
    assert len(sent) == 1
    # la misma mención no se vuelve a avisar en la siguiente corrida
    assert notify.check_negative_mentions(db_session) == 0
    assert len(sent) == 1


def test_check_negative_mentions_ignores_mild_negative(db_session, monkeypatch):
    carlos = Candidate(name="Carlos Arias", party="U", aliases=[])
    db_session.add(carlos)
    db_session.commit()
    _seed_mention(db_session, carlos, -0.2)  # por debajo del umbral -0.5

    sent = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: sent.append(a) or True)
    assert notify.check_negative_mentions(db_session) == 0
    assert sent == []


def test_check_strong_posts_dedupes_across_runs(db_session, monkeypatch):
    posts = [{"id": 1, "candidate": "Carlos Arias", "multiplier": 4.2, "text": "un reel"}]
    import src.queries as q
    monkeypatch.setattr(q, "social_strong_posts", lambda *a, **k: posts)

    sent = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: sent.append(a) or True)

    assert notify.check_strong_posts(db_session) == 1
    assert len(sent) == 1
    assert notify.check_strong_posts(db_session) == 0  # mismo post, ya avisado
    assert len(sent) == 1


def test_check_ollama_tunnel_alerts_after_second_failed_check(db_session, monkeypatch):
    monkeypatch.setattr(notify.config, "SENTIMENT_BACKEND", "ollama")
    monkeypatch.setattr(notify.time, "sleep", lambda s: None)

    class Down:
        ok = False
    monkeypatch.setattr(notify.requests, "get", lambda *a, **k: Down())

    sent = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: sent.append(a[1]) or True)

    notify.check_ollama_tunnel(db_session)
    assert len(sent) == 1
    assert "caído" in sent[0]
    # ya está marcado como caído: no reenvía el mismo aviso en la siguiente corrida
    notify.check_ollama_tunnel(db_session)
    assert len(sent) == 1


def test_check_ollama_tunnel_recovers(db_session, monkeypatch):
    monkeypatch.setattr(notify.config, "SENTIMENT_BACKEND", "ollama")
    notify._set_state(db_session, "ollama_down", "1")

    class Up:
        ok = True
    monkeypatch.setattr(notify.requests, "get", lambda *a, **k: Up())

    sent = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: sent.append(a[1]) or True)
    notify.check_ollama_tunnel(db_session)
    assert len(sent) == 1
    assert "recuperado" in sent[0]


def test_check_ollama_tunnel_skips_when_backend_is_not_ollama(db_session, monkeypatch):
    monkeypatch.setattr(notify.config, "SENTIMENT_BACKEND", "claude")
    calls = []
    monkeypatch.setattr(notify.requests, "get", lambda *a, **k: calls.append(1))
    notify.check_ollama_tunnel(db_session)
    assert calls == []
