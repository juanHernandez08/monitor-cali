import json
import os
import re
import urllib.request
from dataclasses import dataclass

from src.models import SentimentLabel
from src import config

CATEGORIES = [
    "seguridad", "movilidad y transporte", "terremoto y reconstrucción", "servicios públicos", "salud",
    "educación", "empleo y economía", "vivienda", "medio ambiente y clima", "cultura y eventos", "deporte",
    "corrupción y gobierno", "política y elecciones", "orden público y protestas", "infraestructura y obras",
    "animales", "otro",
]
_CATEGORY_LINE = 'Además, asigna una "category" tomada EXACTAMENTE de esta lista: ' + ", ".join(CATEGORIES) + ".\n"

# Rueda de emociones de Plutchik + orgullo, frecuente en discurso político, + una salida neutra.
# "asco" cubre también "repulsión"; "alegría" cubre "felicidad"/"emoción" positiva. "sorpresa" y
# "anticipación" se retiraron (2026-09-28, pedido del cliente): casi nunca se usaban en la práctica
# y "anticipación" en particular no se lee como una emoción propiamente dicha en este contexto.
EMOTIONS = [
    "alegría", "confianza", "miedo", "tristeza", "asco", "ira", "orgullo",
    "sin emoción marcada",
]
_EMOTION_LINE = ('Además, asigna una "emotion" tomada EXACTAMENTE de esta lista, la que mejor describa lo que '
                 'siente quien escribió el texto (no el tema): ' + ", ".join(EMOTIONS) + '. "asco" incluye '
                 'repulsión/indignación visceral; "sin emoción marcada" es para texto puramente informativo.\n')

CITY_PROMPT = """Eres un analista de opinión pública de Cali, Colombia.
El siguiente texto (noticia, post o comentario) habla de la ciudad. Evalúa cómo lo percibe la ciudadanía:
- "negative": queja, molestia, miedo, preocupación, denuncia, indignación.
- "positive": orgullo, celebración, agradecimiento, buena noticia recibida con entusiasmo.
- "neutral": informativo, sin carga.
Sé decidido: si hay cualquier inclinación, aunque sea leve, no uses "neutral"; usa un score pequeño (±0.2 a ±0.4).
Lenguaje colombiano: "berraco/berraca", "bacano", "una chimba", "la rompió" son positivos; "qué pereza", "qué vaina", "ni mierda", "descarados" son negativos. Emojis: 👏🔥❤️💪 apoyo; 🤡💩🤮👎 rechazo; 😂🤣 burla si acompañan una crítica.

El "topic" es el ASUNTO concreto en 2-4 palabras (p. ej. "agua en Terrón Colorado", "huecos en la calle 5"). NUNCA uses el tono como topic. Si el texto no trata ningún asunto (solo saludos, emojis o insultos genéricos), usa topic "sin tema".
""" + _CATEGORY_LINE + _EMOTION_LINE + """
Además, escribe un "summary": un resumen de UNA sola frase (máx. 25 palabras) de QUÉ DICE el texto,
en español neutro, sin opinar. Para una noticia o post: de qué trata. Para un comentario: qué dice
la persona. Si el texto ya es muy corto (un par de palabras), repítelo tal cual como summary.

Texto: {text}

Responde SOLO con un JSON de la forma:
{{"label": "positive" | "negative" | "neutral", "score": <float entre -1.0 y 1.0>, "topic": "<asunto o 'sin tema'>", "category": "<una de la lista>", "summary": "<resumen de una frase>", "emotion": "<una de la lista>"}}
"""

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
NUNCA uses el tono como topic (no escribas "apoyo", "elogio", "crítica", "rechazo", "felicitación"). Si el texto es un insulto, burla, ataque personal o rechazo al candidato sin ningún asunto concreto, usa topic "rechazo e insultos". Si solo son aplausos, saludos o emojis de apoyo sin asunto, usa topic "sin tema".

Además, escribe un "summary": un resumen de UNA sola frase (máx. 25 palabras) de QUÉ DICE el texto
sobre {candidate}, en español neutro, sin opinar tú. Para una noticia o post: de qué trata en
relación a él. Para un comentario: qué dice la persona. Si el texto ya es muy corto, repítelo tal
cual como summary.
""" + _CATEGORY_LINE + _EMOTION_LINE + """
Responde SOLO con un JSON de la forma:
{{"label": "positive" | "negative" | "neutral", "score": <float entre -1.0 y 1.0>, "topic": "<asunto en 2-4 palabras, 'rechazo e insultos' o 'sin tema'>", "category": "<una de la lista>", "summary": "<resumen de una frase>", "emotion": "<una de la lista>"}}
"""
_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass
class SentimentResult:
    label: SentimentLabel
    score: float
    topic: str
    model: str
    category: str = "otro"
    summary: str = ""
    emotion: str = "sin emoción marcada"


def _parse_payload(text: str, model: str) -> SentimentResult:
    payload = json.loads(_JSON_FENCE.sub("", text).strip())
    label = str(payload.get("label", "neutral")).lower()
    if label not in {"positive", "negative", "neutral"}:
        label = "neutral"
    score = max(-1.0, min(1.0, float(payload.get("score", 0.0))))
    category = str(payload.get("category", "otro")).strip().lower()
    if category not in CATEGORIES:
        category = "otro"
    emotion = str(payload.get("emotion", "")).strip().lower()
    if emotion not in EMOTIONS:
        emotion = "sin emoción marcada"
    return SentimentResult(label=SentimentLabel(label), score=score,
                           topic=str(payload.get("topic", ""))[:80], model=model, category=category,
                           summary=str(payload.get("summary", "")).strip()[:220], emotion=emotion)


def _prompt(text: str, candidate: str | None, city: bool = False) -> str:
    if city:
        return CITY_PROMPT.format(text=text[:3000])
    return SENTIMENT_PROMPT.format(text=text[:3000], candidate=candidate or "mencionado")


class SentimentEngine:
    """Backend Claude (Anthropic API)."""

    def __init__(self, model: str | None = None, client=None):
        self.model = model or config.CLAUDE_MODEL
        if client is None:
            from anthropic import Anthropic
            client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.client = client

    def score(self, text: str, candidate: str | None = None, city: bool = False) -> SentimentResult:
        response = self.client.messages.create(
            model=self.model, max_tokens=256,
            messages=[{"role": "user", "content": _prompt(text, candidate, city)}],
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

    def score(self, text: str, candidate: str | None = None, city: bool = False) -> SentimentResult:
        options = {"temperature": 0}
        if config.OLLAMA_NUM_GPU is not None:
            options["num_gpu"] = config.OLLAMA_NUM_GPU
        data = _ollama_post(f"{self.base_url}/api/chat", {
            "model": self.model, "stream": False, "format": "json",
            "options": options,
            "messages": [{"role": "user", "content": _prompt(text, candidate, city)}],
        }, timeout=self.timeout)
        return _parse_payload(data["message"]["content"], f"ollama/{self.model}")


def build_sentiment_engine():
    backend = os.environ.get("SENTIMENT_BACKEND", "ollama").lower()
    if backend == "claude" and os.environ.get("ANTHROPIC_API_KEY"):
        return SentimentEngine()
    return OllamaSentimentEngine()
