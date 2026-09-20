import json

from src.sentiment import OllamaSentimentEngine, build_sentiment_engine, SentimentEngine
from src.models import SentimentLabel


def test_ollama_engine_parses_json(monkeypatch):
    captured = {}

    def fake_post(url, json_body, timeout):
        captured["body"] = json_body
        return {"message": {"content": json.dumps({"label": "negative", "score": -0.7, "topic": "seguridad"})}}

    import src.sentiment as m
    monkeypatch.setattr(m, "_ollama_post", fake_post)

    engine = OllamaSentimentEngine(model="qwen2.5:14b")
    r = engine.score("Ortiz no cumplió", candidate="Roberto Ortiz")

    assert r.label == SentimentLabel.NEGATIVE and r.score == -0.7
    assert r.model == "ollama/qwen2.5:14b"
    assert captured["body"]["format"] == "json"
    assert "Roberto Ortiz" in captured["body"]["messages"][0]["content"]


def test_build_engine_prefers_claude_when_key_present(monkeypatch):
    monkeypatch.setenv("SENTIMENT_BACKEND", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert isinstance(build_sentiment_engine(), SentimentEngine)


def test_build_engine_defaults_to_ollama(monkeypatch):
    monkeypatch.delenv("SENTIMENT_BACKEND", raising=False)
    assert isinstance(build_sentiment_engine(), OllamaSentimentEngine)
