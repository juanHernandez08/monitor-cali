"""Prueba de calidad: IA local (Ollama, lo ya guardado) vs. Claude Haiku 5.5 vs. Claude Sonnet 5.5
(referencia) sobre una muestra estratificada de menciones reales. SOLO LECTURA: no escribe en la base.

    python scripts/eval_models.py --n 100 --out /tmp/eval.json --max-usd 0.9

Muestra: 25 de prensa, 25 de redes (posts y comentarios), 25 comentarios de YouTube y 25 sobre Carlos
Arias, de los últimos 30 días, ya clasificadas por la IA local. Se detiene sola si el costo estimado
supera --max-usd. Precios (USD por millón de tokens): Haiku 5.5 0,10 / 0,50; Sonnet 5.5 2 / 10;
lectura de caché ~0,1x de la entrada."""
import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.db import SessionLocal  # noqa: E402
from src.models import Mention, SentimentScore, Source, SourceType  # noqa: E402
from src.pipeline import context_text  # noqa: E402
from src.queries import CARLOS, WHEN, _since  # noqa: E402
from src.sentiment import _parse_payload, _prompt_parts  # noqa: E402

PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.0, 10.0)}
MODEL_KW = {
    # clasificación de una etiqueta JSON: sin razonamiento facturado
    "claude-haiku-5-5": {"output_config": {"effort": "low"}, "thinking": {"type": "disabled"}},
    "claude-sonnet-5-5": {"output_config": {"effort": "low"}},
}


def cost(model: str, u) -> float:
    pin, pout = PRICES[model]
    cached = getattr(u, "cache_read_input_tokens", 0) or 0
    written = getattr(u, "cache_creation_input_tokens", 0) or 0
    return ((u.input_tokens + written * 1.25 + cached * 0.1) * pin + u.output_tokens * pout) / 1e6


def sample(s, n: int, seed: int = 20261020) -> list[Mention]:
    base = (s.query(Mention).join(SentimentScore).join(Source)
            .filter(Mention.relevant.is_(True), WHEN >= _since(30), SentimentScore.model.like("ollama/%")))
    rng = random.Random(seed)
    k = n // 4
    buckets = {
        "prensa": base.filter(Source.type.in_([SourceType.GOOGLE_NEWS, SourceType.RSS])).all(),
        "redes": base.filter(Source.type == SourceType.SOCIAL).all(),
        "youtube": base.filter(Source.type == SourceType.YOUTUBE).all(),
        "carlos": [m for m in base.all() if m.candidate.name == CARLOS],
    }
    picked, seen = [], set()
    for name, rows in buckets.items():
        rows = [m for m in rows if m.id not in seen]
        for m in rng.sample(rows, min(k, len(rows))):
            seen.add(m.id)
            picked.append((name, m))
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--out", default="eval.json")
    ap.add_argument("--max-usd", type=float, default=0.9)
    args = ap.parse_args()
    from anthropic import Anthropic
    client = Anthropic()
    s = SessionLocal()
    spent, rows = 0.0, []
    for bucket, m in sample(s, args.n):
        st = m.sentiment
        text = context_text(m)
        static, dynamic = _prompt_parts(text, m.candidate.name, m.candidate.kind == "city")
        row = {"id": m.id, "bucket": bucket, "candidate": m.candidate.name, "source": m.source.type.value,
               "kind": (m.raw or {}).get("kind"), "text": m.text[:400],
               "ollama": {"label": st.label.value, "score": st.score, "category": st.category, "emotion": st.emotion,
                          "topic": st.topic, "esfera": st.esfera, "lugar": st.place_hint}}
        for model, kw in MODEL_KW.items():
            if spent >= args.max_usd:
                print(f"TOPE: {spent:.3f} USD, se detiene")
                break
            t0 = time.time()
            try:
                r = client.messages.create(model=model, max_tokens=400, **kw, messages=[{"role": "user", "content": [
                    {"type": "text", "text": static, "cache_control": {"type": "ephemeral"}},
                    {"type": "text", "text": dynamic}]}])
                txt = next(b.text for b in r.content if getattr(b, "type", "") == "text")
                p = _parse_payload(txt, model)
                c = cost(model, r.usage)
                spent += c
                row[model] = {"label": p.label.value, "score": p.score, "category": p.category, "emotion": p.emotion,
                              "topic": p.topic, "esfera": p.esfera, "lugar": p.place_hint, "usd": round(c, 6),
                              "in": r.usage.input_tokens, "cache_read": getattr(r.usage, "cache_read_input_tokens", 0),
                              "out": r.usage.output_tokens, "secs": round(time.time() - t0, 2)}
            except Exception as e:  # una falla no tumba la prueba: queda anotada
                row[model] = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
        rows.append(row)
        if spent >= args.max_usd:
            break
    Path(args.out).write_text(json.dumps({"spent_usd": round(spent, 4), "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(rows)} menciones, gasto {spent:.4f} USD -> {args.out}")


if __name__ == "__main__":
    main()
