import json
from types import SimpleNamespace

from src.sentiment import SentimentEngine
from src.models import SentimentLabel


class FakeAnthropicClient:
    def __init__(self, reply):
        self._reply = reply
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        return SimpleNamespace(content=[SimpleNamespace(text=json.dumps(self._reply))])


def test_sentiment_engine_parses_claude_response():
    fake_client = FakeAnthropicClient({
        "label": "negative", "score": -0.6, "topic": "seguridad",
    })
    engine = SentimentEngine(client=fake_client)

    result = engine.score("El candidato prometió más seguridad pero no cumplió.")

    assert result.label == SentimentLabel.NEGATIVE
    assert result.score == -0.6
    assert result.topic == "seguridad"


def test_sentiment_engine_parses_summary_when_present():
    fake_client = FakeAnthropicClient({
        "label": "negative", "score": -0.6, "topic": "seguridad",
        "summary": "El candidato incumplió su promesa de más seguridad.",
    })
    engine = SentimentEngine(client=fake_client)
    result = engine.score("texto largo de una noticia...")
    assert result.summary == "El candidato incumplió su promesa de más seguridad."


def test_sentiment_engine_summary_defaults_to_empty_when_absent():
    fake_client = FakeAnthropicClient({"label": "neutral", "score": 0.0, "topic": "sin tema"})
    engine = SentimentEngine(client=fake_client)
    result = engine.score("hola")
    assert result.summary == ""


def test_sentiment_engine_truncates_long_summary():
    fake_client = FakeAnthropicClient({
        "label": "neutral", "score": 0.0, "topic": "x", "summary": "a" * 400,
    })
    engine = SentimentEngine(client=fake_client)
    result = engine.score("texto")
    assert len(result.summary) <= 220


def test_sentiment_engine_parses_emotion_from_the_fixed_list():
    fake_client = FakeAnthropicClient({
        "label": "negative", "score": -0.6, "topic": "seguridad", "emotion": "miedo",
    })
    engine = SentimentEngine(client=fake_client)
    result = engine.score("Que miedo, otra vez atracaron a alguien en el barrio.")
    assert result.emotion == "miedo"


def test_sentiment_engine_emotion_falls_back_when_not_in_the_list():
    fake_client = FakeAnthropicClient({"label": "neutral", "score": 0.0, "topic": "x", "emotion": "aburrimiento"})
    engine = SentimentEngine(client=fake_client)
    result = engine.score("texto")
    assert result.emotion == "sin emoción marcada"


def test_sentiment_engine_emotion_defaults_when_absent():
    fake_client = FakeAnthropicClient({"label": "neutral", "score": 0.0, "topic": "x"})
    engine = SentimentEngine(client=fake_client)
    result = engine.score("texto")
    assert result.emotion == "sin emoción marcada"
