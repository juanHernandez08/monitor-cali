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


def _seed_mention(db_session, candidate, score, ext_id="m1", topic="seguridad", account=None):
    src = db_session.query(Source).first()
    if src is None:
        src = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
        db_session.add(src)
        db_session.commit()
    m = Mention(candidate_id=candidate.id, source_id=src.id, external_id=ext_id, text="texto negativo",
                url=f"https://x/{ext_id}", fetched_at=dt.datetime.utcnow(),
                raw={"account": account} if account else {})
    db_session.add(m)
    db_session.flush()
    db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.NEGATIVE, score=score, topic=topic, model="fake"))
    db_session.commit()
    return m


def test_check_negative_mentions_first_run_does_not_sweep_existing_backlog(db_session, monkeypatch):
    """Bug real 2026-09-30: al activarse por primera vez, mandó de golpe 23 avisos de menciones
    negativas viejas (algunas de años atrás). La primera corrida solo debe fijar la marca de agua
    en lo que ya existe, sin notificar nada de eso."""
    carlos = Candidate(name="Carlos Arias", party="U", aliases=[])
    db_session.add(carlos)
    db_session.commit()
    _seed_mention(db_session, carlos, -0.9)  # ya existía ANTES de que el feature se activara

    sent = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: sent.append(a) or True)

    assert notify.check_negative_mentions(db_session) == 0
    assert sent == []
    assert notify._get_state(db_session, "last_negative_id") is not None


def test_check_negative_mentions_notifies_new_ones_then_dedupes(db_session, monkeypatch):
    carlos = Candidate(name="Carlos Arias", party="U", aliases=[])
    db_session.add(carlos)
    db_session.commit()
    _seed_mention(db_session, carlos, -0.9, ext_id="old")
    sent = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: sent.append(a) or True)
    notify.check_negative_mentions(db_session)  # primera corrida: solo fija la marca de agua
    assert sent == []

    _seed_mention(db_session, carlos, -0.9, ext_id="new")  # esta sí es posterior a la marca
    assert notify.check_negative_mentions(db_session) == 1
    assert len(sent) == 1
    # la misma mención no se vuelve a avisar en la siguiente corrida
    assert notify.check_negative_mentions(db_session) == 0
    assert len(sent) == 1


def test_check_negative_mentions_ignores_mild_negative(db_session, monkeypatch):
    carlos = Candidate(name="Carlos Arias", party="U", aliases=[])
    db_session.add(carlos)
    db_session.commit()
    notify.check_negative_mentions(db_session)  # fija la marca de agua en vacío
    _seed_mention(db_session, carlos, -0.2)  # por debajo del umbral -0.5

    sent = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: sent.append(a) or True)
    assert notify.check_negative_mentions(db_session) == 0
    assert sent == []


def test_check_negative_mentions_ignores_tangential_mentions(db_session, monkeypatch):
    """No basta con score <= -0.5: si el clasificador ya marcó el texto como 'mención
    tangencial' u 'homónimo', no es realmente sobre Carlos y no debe avisar (reporte
    2026-09-30: llegaron alertas de comentarios que no tenían nada que ver con él)."""
    carlos = Candidate(name="Carlos Arias", party="U", aliases=[])
    db_session.add(carlos)
    db_session.commit()
    notify.check_negative_mentions(db_session)  # fija la marca de agua en vacío
    _seed_mention(db_session, carlos, -0.9, topic="mención tangencial")

    sent = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: sent.append(a) or True)
    assert notify.check_negative_mentions(db_session) == 0
    assert sent == []


def test_check_negative_mentions_flags_comments_on_own_post(db_session, monkeypatch):
    carlos = Candidate(name="Carlos Arias", party="U", aliases=[])
    db_session.add(carlos)
    db_session.commit()
    notify.check_negative_mentions(db_session)  # fija la marca de agua en vacío
    own_url = "https://www.instagram.com/soycarlosaarias/"
    monkeypatch.setattr(notify.config, "SOCIAL_ACCOUNTS",
                         [{"platform": "instagram", "url": own_url, "candidate": "Carlos Arias"}])
    _seed_mention(db_session, carlos, -0.9, account=own_url)

    sent = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: sent.append(a[2]) or True)
    assert notify.check_negative_mentions(db_session) == 1
    assert "PROPIA" in sent[0]


def test_check_strong_posts_dedupes_across_runs(db_session, monkeypatch):
    posts = [{"id": 1, "candidate": "Carlos Arias", "candidate_id": 1, "multiplier": 4.2, "text": "un reel", "url": "https://x/1"}]
    import src.queries as q
    monkeypatch.setattr(q, "social_strong_posts", lambda *a, **k: posts)

    sent = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: sent.append(a) or True)

    assert notify.check_strong_posts(db_session) == 1
    assert len(sent) == 1
    assert notify.check_strong_posts(db_session) == 0  # mismo post, ya avisado
    assert len(sent) == 1


def test_check_city_trends_notifies_new_topic_then_dedupes(db_session, monkeypatch):
    novedades = [{"topic": "terremoto", "category": "reconstrucción", "count": 12, "is_new": True,
                  "trend_pct": None, "samples": [{"text": "algo pasó", "url": "https://x/1"}]}]
    import src.queries as q
    monkeypatch.setattr(q, "city_opportunities", lambda *a, **k: {"novedades": novedades, "carlos_strong": []})

    sent = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: sent.append(a) or True)

    assert notify.check_city_trends(db_session) == 1
    assert len(sent) == 1
    assert notify.check_city_trends(db_session) == 0  # mismo tema, ya avisado
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
