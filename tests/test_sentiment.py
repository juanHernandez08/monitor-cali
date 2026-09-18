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
