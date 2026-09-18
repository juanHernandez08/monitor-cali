import json
import re
from dataclasses import dataclass

from anthropic import Anthropic

from src.models import SentimentLabel
from src.config import ANTHROPIC_API_KEY

SENTIMENT_PROMPT = """Eres un analista de comunicación política en Cali, Colombia.
Clasifica el siguiente texto sobre un candidato a la alcaldía.

Texto: {text}

Responde SOLO con un JSON de la forma:
{{"label": "positive" | "negative" | "neutral", "score": <float entre -1.0 y 1.0>, "topic": "<tema en 2-3 palabras>"}}
"""

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass
class SentimentResult:
    label: SentimentLabel
    score: float
    topic: str
    model: str


class SentimentEngine:
    def __init__(self, model: str = "claude-sonnet-5", client=None):
        self.model = model
        self.client = client or Anthropic(api_key=ANTHROPIC_API_KEY)

    def score(self, text: str) -> SentimentResult:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=256,
            messages=[{"role": "user", "content": SENTIMENT_PROMPT.format(text=text)}],
        )
        payload = json.loads(_extract_text(response))
        return SentimentResult(
            label=SentimentLabel(payload["label"]),
            score=float(payload["score"]),
            topic=payload["topic"],
            model=self.model,
        )


def _extract_text(response) -> str:
    # Los modelos actuales pueden devolver bloques `thinking` antes del texto.
    for block in response.content:
        if getattr(block, "type", "text") == "text":
            return _JSON_FENCE.sub("", block.text).strip()
    raise ValueError("La respuesta de Claude no contiene un bloque de texto")
