"""Esferas de relacionamiento, cercanía y NPS (pedido del cliente 2026-10-20).

  * Esfera por SECTOR: desde qué sector de la ciudad habla quien escribe (campo "esfera" del LLM, ver
    sentiment.ESFERAS).
  * Esfera por CERCANÍA: anillos alrededor del candidato según TODAS las opiniones de cada cuenta
    sobre él. Siempre en conteos agregados: nunca se lista ni se perfila a una persona.
  * NPS DIGITAL: lectura de lo que la gente escribe, no la pregunta de 0 a 10 de una encuesta; se rotula
    así en el tablero.
  * NPS de ENCUESTA: totales que carga la campaña (tabla survey_nps); solo agregados.
"""
from collections import Counter, defaultdict

from src import geo, stats
from src.models import Candidate, Mention, MentionPlace, SentimentLabel, SourceType, SurveyNPS
from src.queries import CARLOS, META_TOPICS, WHEN, _since, pct

NPS_MIN_N = 30  # con menos opiniones el NPS digital se muestra pero se marca como no concluyente
SURVEY_MIN_N = 100  # una encuesta con menos de 100 respuestas es muy ruidosa
RING_ORDER = ["simpatizantes", "cercanos", "indecisos", "críticos", "opositores"]
_PRESS = (SourceType.GOOGLE_NEWS, SourceType.RSS)


def is_own_post(m: Mention, candidate_name: str) -> bool:
    """Publicación de la cuenta propia del candidato. Los posts de cuentas monitoreadas guardan la cuenta
    de origen (`account`) pero no siempre `account_candidate` (en producción, ninguno de los 28 posts
    propios de Carlos lo tenía): la cuenta + el candidato de la mención bastan."""
    raw = m.raw or {}
    if raw.get("kind") != "post":
        return False
    return raw.get("account_candidate") == candidate_name or bool(raw.get("account") and m.candidate and m.candidate.name == candidate_name)


def opinion(m: Mention, candidate_name: str) -> str | None:
    """'promotor' | 'pasivo' | 'detractor' para el NPS digital, o None si la mención no expresa una
    opinión sobre el candidato. Promotor = apoyo fuerte (positivo con score >= 0,6); detractor =
    cualquier mención negativa; pasivo = apoyo tibio, o neutral pero con alguna emoción. Quedan fuera
    las publicaciones del propio candidato, las notas puramente informativas (neutral sin emoción) y
    lo tangencial u homónimo."""
    s = m.sentiment
    if not s or s.model == "regla" or (s.topic or "").lower() in META_TOPICS:
        return None
    if is_own_post(m, candidate_name):
        return None
    if s.label == SentimentLabel.NEUTRAL and (not s.emotion or s.emotion == "sin emoción marcada"):
        return None
    if s.label == SentimentLabel.NEGATIVE:
        return "detractor"
    if s.label == SentimentLabel.POSITIVE and s.score >= 0.6:
        return "promotor"
    return "pasivo"


def nps(counts: Counter, min_n: int = NPS_MIN_N) -> dict:
    """NPS = % promotores − % detractores, con un intervalo conservador (Wilson en cada parte)."""
    p, a, d = counts.get("promotor", 0), counts.get("pasivo", 0), counts.get("detractor", 0)
    n = p + a + d
    if not n:
        return {"n": 0, "promoters": 0, "passives": 0, "detractors": 0, "promoters_pct": 0, "passives_pct": 0,
                "detractors_pct": 0, "nps": None, "low": None, "high": None, "conclusive": False}
    pl, ph = stats.wilson(p, n)
    dl, dh = stats.wilson(d, n)
    return {"n": n, "promoters": p, "passives": a, "detractors": d,
            "promoters_pct": pct(p, n), "passives_pct": pct(a, n), "detractors_pct": pct(d, n),
            "nps": round((p - d) / n * 100), "low": round(pl - dh), "high": round(ph - dl), "conclusive": n >= min_n}


def _mentions(session, candidate_id: int, days: int) -> list[Mention]:
    return (session.query(Mention).filter(Mention.candidate_id == candidate_id, Mention.relevant.is_(True),
                                          WHEN >= _since(days)).all())


def _author_key(m: Mention) -> str | None:
    if not m.author:
        return None
    return f"{(m.raw or {}).get('platform') or m.source.type.value}:{m.author.strip().lower().lstrip('@')}"


def _ring(c: Counter) -> str:
    p, d = c["promotor"], c["detractor"]
    n = p + c["pasivo"] + d
    if n >= 2 and d / n >= 0.75:
        return "opositores"
    if d > p:
        return "críticos"
    if n >= 2 and p and not d:
        return "simpatizantes"
    if p > d:
        return "cercanos"
    return "indecisos"


def nps_digital(session, days: int = 30) -> dict:
    """NPS digital de cada candidato a la alcaldía."""
    rows = []
    for c in session.query(Candidate).filter_by(active=True, kind="candidate").all():
        cnt = Counter(o for m in _mentions(session, c.id, days) if (o := opinion(m, c.name)))
        rows.append({"candidate_id": c.id, "candidate": c.name, **nps(cnt)})
    rows.sort(key=lambda r: (r["candidate"] != CARLOS, -(r["nps"] if r["nps"] is not None else -999)))
    return {"days": days, "min_n": NPS_MIN_N, "rows": rows}


def relationship(session, candidate_id: int | None = None, days: int = 90) -> dict:
    cand = (session.get(Candidate, candidate_id) if candidate_id
            else session.query(Candidate).filter_by(name=CARLOS).first())
    if cand is None:
        return {"error": "candidato no encontrado"}
    scored = [m for m in _mentions(session, cand.id, days) if m.sentiment and m.sentiment.model != "regla"]
    ops = {m.id: opinion(m, cand.name) for m in scored}

    # --- por sector
    by_esfera: dict[str, list[Mention]] = defaultdict(list)
    for m in scored:
        if m.sentiment.esfera:
            by_esfera[m.sentiment.esfera].append(m)
    spheres = []
    for e, rows in by_esfera.items():
        labels = Counter(m.sentiment.label for m in rows)
        cats = Counter(m.sentiment.category for m in rows if m.sentiment.category and m.sentiment.category != "otro")
        spheres.append({"esfera": e, "mentions": len(rows),
                        "positive_pct": pct(labels.get(SentimentLabel.POSITIVE, 0), len(rows)),
                        "negative_pct": pct(labels.get(SentimentLabel.NEGATIVE, 0), len(rows)),
                        "categories": [{"category": c, "count": n} for c, n in cats.most_common(3)],
                        "nps": nps(Counter(ops[m.id] for m in rows if ops[m.id]))})
    spheres.sort(key=lambda r: -r["mentions"])

    # --- por cercanía (cuentas de personas; un medio no "se acerca" ni "se aleja")
    authors: dict[str, Counter] = defaultdict(Counter)
    author_esfera: dict[str, Counter] = defaultdict(Counter)
    own_accounts = set()
    for m in scored:
        raw = m.raw or {}
        if is_own_post(m, cand.name):
            own_accounts.add(raw.get("account") or _author_key(m))
            continue
        k, o = _author_key(m), ops[m.id]
        if not k or not o or m.source.type in _PRESS:
            continue
        authors[k][o] += 1
        author_esfera[k][m.sentiment.esfera or "sin clasificar"] += 1
    rings = {r: {"ring": r, "accounts": 0, "opinions": 0} for r in RING_ORDER}
    matrix: dict[str, Counter] = defaultdict(Counter)
    for k, c in authors.items():
        r = _ring(c)
        rings[r]["accounts"] += 1
        rings[r]["opinions"] += sum(c.values())
        matrix[author_esfera[k].most_common(1)[0][0]][r] += 1
    total_accounts = sum(r["accounts"] for r in rings.values())
    for r in rings.values():
        r["pct"] = pct(r["accounts"], total_accounts)

    # --- NPS por núcleo territorial y por tipo de fuente
    nucleos_of: dict[int, set] = defaultdict(set)
    ids = [m.id for m in scored if ops[m.id]]
    for k in range(0, len(ids), 900):
        for mid, pid in (session.query(MentionPlace.mention_id, MentionPlace.place_id)
                         .filter(MentionPlace.mention_id.in_(ids[k:k + 900])).all()):
            n = geo.nucleo_of(pid)
            if n:
                nucleos_of[mid].add(n)
    total, by_nucleo, by_source = Counter(), defaultdict(Counter), defaultdict(Counter)
    for m in scored:
        o = ops[m.id]
        if not o:
            continue
        total[o] += 1
        for n in nucleos_of.get(m.id, ()):
            by_nucleo[n][o] += 1
        by_source["prensa" if m.source.type in _PRESS else m.source.type.value][o] += 1

    return {
        "candidate": cand.name, "candidate_id": cand.id, "days": days, "min_n": NPS_MIN_N,
        "mentions": len(scored), "pending_esfera": sum(1 for m in scored if m.sentiment.esfera is None),
        "nps": nps(total), "spheres": spheres,
        "own_accounts": len(own_accounts), "accounts": total_accounts,
        "rings": [rings[r] for r in RING_ORDER],
        "matrix": [{"esfera": e, **{r: c.get(r, 0) for r in RING_ORDER}}
                   for e, c in sorted(matrix.items(), key=lambda kv: -sum(kv[1].values()))],
        "by_nucleo": [{"nucleo": n, "name": geo.NUCLEOS[n][0], **nps(c)}
                      for n, c in sorted(by_nucleo.items(), key=lambda kv: -sum(kv[1].values()))],
        "by_source": [{"source": s, **nps(c)} for s, c in sorted(by_source.items(), key=lambda kv: -sum(kv[1].values()))],
    }


# ---------- NPS de encuesta (lo carga la campaña) ----------

def _scope_ok(scope: str) -> bool:
    if scope == "cali":
        return True
    kind, _, val = scope.partition(":")
    if kind == "nucleo":
        return val in geo.NUCLEOS
    return kind == "comuna" and val.isdigit() and 1 <= int(val) <= 22


def survey_list(session) -> list[dict]:
    out = []
    for r in session.query(SurveyNPS).order_by(SurveyNPS.date.desc(), SurveyNPS.id.desc()).all():
        out.append({"id": r.id, "date": r.date, "scope": r.scope, "source": r.source, "notes": r.notes,
                    **nps(Counter({"promotor": r.promoters, "pasivo": r.passives, "detractor": r.detractors}),
                          min_n=SURVEY_MIN_N)})
    return out


def survey_add(session, data: dict) -> tuple[dict | None, str | None]:
    """Valida y guarda una medición. Devuelve (fila, None) o (None, motivo del rechazo)."""
    import re
    date = str(data.get("date") or "")
    scope = str(data.get("scope") or "cali").strip().lower()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return None, "fecha inválida (AAAA-MM-DD)"
    if not _scope_ok(scope):
        return None, "alcance inválido (cali, nucleo:<id> o comuna:<1-22>)"
    try:
        p, a, d = (int(data.get(k)) for k in ("promoters", "passives", "detractors"))
    except (TypeError, ValueError):
        return None, "promotores, pasivos y detractores deben ser números enteros"
    if min(p, a, d) < 0 or p + a + d == 0 or p + a + d > 1_000_000:
        return None, "los totales deben ser positivos y sumar al menos 1"
    if scope.startswith("comuna:"):
        scope = f"comuna:{int(scope.split(':')[1]):02d}"
    row = SurveyNPS(date=date, scope=scope, promoters=p, passives=a, detractors=d,
                    source=(str(data.get("source") or "").strip()[:120] or None),
                    notes=(str(data.get("notes") or "").strip()[:500] or None))
    session.add(row)
    session.commit()
    return next(r for r in survey_list(session) if r["id"] == row.id), None


def survey_delete(session, survey_id: int) -> bool:
    row = session.get(SurveyNPS, survey_id)
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True
