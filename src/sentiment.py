import json
import os
import re
import urllib.request
from dataclasses import dataclass

from src.models import SentimentLabel
from src import config

SENTIMENT_PROMPT = """Eres un analista de comunicación política de una campaña a la Alcaldía de Cali, Colombia.
Evalúa cómo deja parado al candidato {candidate} el siguiente texto (noticia, post o comentario).

Criterios:
- "positive": lo muestra con logros, apoyo, liderazgo, propuestas bien recibidas, o el autor lo elogia/apoya.
- "negative": lo asocia a críticas, escándalos, fracasos, rechazo, burla, o el autor lo ataca/desconfía.
- "neutral": SOLO si es una mención de agenda o trámite sin ninguna carga (p. ej. "asistirá al foro").
Sé decidido: si hay cualquier inclinación, aunque sea leve, no uses "neutral"; usa un score pequeño (±0.2 a ±0.4).
Lenguaje colombiano: "berraco/berraca", "teso/tesa", "bacano", "una chimba", "la rompió", "duro/dura", "con toda", "firme", "crack" son ELOGIOS. "lagarto", "mermelada", "vendido", "gavillero", "corrupto", "ladrón", "politiquero", "sinvergüenza", "paraco", "guerrillero" son ATAQUES. Emojis: 👏🔥❤️💪🙌👍 expresan apoyo; 🤡💩🤮👎 expresan rechazo; 😂🤣 suelen ser burla si acompañan una crítica.
Si el candidato aparece solo de paso en una noticia (una cita, una lista, un evento), clasifica igual el tono con que aparece y usa topic "mención tangencial".
Si el texto es un COMENTARIO que no se refiere al candidato ni a algo que él hizo o dijo (habla del tema del video/post, de otra persona o de otra cosa), responde neutral con score 0 y topic "mención tangencial".
SOLO si el texto claramente habla de OTRA persona con el mismo nombre (otra ciudad, otro cargo, otro país), responde neutral con score 0 y topic "homónimo".

Texto: {text}

El "topic" es el ASUNTO concreto del que trata el texto, en 2-4 palabras (p. ej. "seguridad", "agua en Terrón Colorado", "reconstrucción tras el terremoto", "empleo juvenil", "transporte público").
NUNCA uses el tono como topic (no escribas "apoyo", "elogio", "crítica", "rechazo", "felicitación"). Si el texto es un insulto, burla o ataque personal sin ningún asunto concreto, usa topic "insultos y ataques". Si solo son aplausos, saludos o emojis de apoyo sin asunto, usa topic "sin tema".

Responde SOLO con un JSON de la forma:
{{"label": "positive" | "negative" | "neutral", "score": <float entre -1.0 y 1.0>, "topic": "<asunto en 2-4 palabras, 'insultos y ataques' o 'sin tema'>"}}
"""
_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass
class SentimentResult:
    label: SentimentLabel
    score: float
    topic: str
    model: str


def _parse_payload(text: str, model: str) -> SentimentResult:
    payload = json.loads(_JSON_FENCE.sub("", text).strip())
    label = str(payload.get("label", "neutral")).lower()
    if label not in {"positive", "negative", "neutral"}:
        label = "neutral"
    score = max(-1.0, min(1.0, float(payload.get("score", 0.0))))
    return SentimentResult(label=SentimentLabel(label), score=score,
                           topic=str(payload.get("topic", ""))[:80], model=model)


def _prompt(text: str, candidate: str | None) -> str:
    return SENTIMENT_PROMPT.format(text=text[:3000], candidate=candidate or "mencionado")


class SentimentEngine:
    """Backend Claude (Anthropic API)."""

    def __init__(self, model: str | None = None, client=None):
        self.model = model or config.CLAUDE_MODEL
        if client is None:
            from anthropic import Anthropic
            client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.client = client

    def score(self, text: str, candidate: str | None = None) -> SentimentResult:
        response = self.client.messages.create(
            model=self.model, max_tokens=256,
            messages=[{"role": "user", "content": _prompt(text, candidate)}],
        )
        # Los modelos actuales pueden devolver bloques `thinking` antes del texto.
        for block in response.content:
            if getattr(block, "type", "text") == "text":
                return _parse_payload(block.text, self.model)
        raise ValueError("La respuesta de Claude no contiene un bloque de texto")


def _ollama_post(url: str, json_body: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(json_body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


class OllamaSentimentEngine:
    """Backend local (Ollama). Sin costo; ~3 s por mención con qwen2.5:14b."""

    def __init__(self, model: str | None = None, base_url: str | None = None, timeout: int = 180):
        self.model = model or config.OLLAMA_MODEL
        self.base_url = (base_url or config.OLLAMA_URL).rstrip("/")
        self.timeout = timeout

    def score(self, text: str, candidate: str | None = None) -> SentimentResult:
        data = _ollama_post(f"{self.base_url}/api/chat", {
            "model": self.model, "stream": False, "format": "json",
            "options": {"temperature": 0},
            "messages": [{"role": "user", "content": _prompt(text, candidate)}],
        }, timeout=self.timeout)
        return _parse_payload(data["message"]["content"], f"ollama/{self.model}")


def build_sentiment_engine():
    backend = os.environ.get("SENTIMENT_BACKEND", "ollama").lower()
    if backend == "claude" and os.environ.get("ANTHROPIC_API_KEY"):
        return SentimentEngine()
    return OllamaSentimentEngine()
