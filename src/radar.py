"""Radar de precandidatos: estar siempre al tanto de quién suena para la Alcaldía de Cali.

Pedido del cliente 2026-10-21. Hace tres cosas, todas sobre titulares de prensa que el monitor YA captura
(Google News y medios locales): sin costo, sin YouTube y sin créditos de Apify.

  1. DETECTA nombres nuevos: un titular como «X entra en el sonajero por la Alcaldía de Cali» o «X va por
     firmas» propone a X; queda en una lista «por revisar» y una persona decide seguirlo o descartarlo.
     Nunca agrega a nadie solo.
  2. AVISA de novedades de los ya conocidos: oficializó, declinó, renuncia para aspirar, «suena».
  3. MUESTRA el panorama: estado de cada precandidato, nota que lo respalda y el calendario electoral.

Todo se lee de los titulares: un titular puede equivocarse, por eso los estados los confirma una persona
(botón en el tablero) y el radar solo los propone.
"""
import datetime as dt
import re
import unicodedata

from src import config
from src.models import Candidate, Mention, NotifyState, RadarSuggestion, Source, SourceType

PRESS = (SourceType.GOOGLE_NEWS, SourceType.RSS)
ELECTION = dt.date(2027, 10, 31)
CALENDAR = [
    {"date": "2026-10-31", "label": "Empieza el registro de comités independientes (recolección de firmas)", "approx": True},
    {"date": "2027-07-31", "label": "Fin del plazo de inscripción de candidaturas", "approx": True},
    {"date": "2027-10-31", "label": "Elecciones territoriales", "approx": False},
]
STATUSES = ("oficial", "suena", "declino", "revisar")

_TOKEN = r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:-[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?"
_NAME = rf"{_TOKEN}(?:\s+(?:(?:de|del|la|las|los|van|von)\s+)?{_TOKEN}){{1,3}}"
# cue -> (tipo de novedad, fuerza). Fuerte = por sí sola justifica proponer el nombre.
_CUES = [
    (r"entra(?:n)? en (?:el sonajero|la carrera)", "suena", True),
    (r"suena(?:n)?(?: -y fuerte-)?(?: como| para| por| en| cada)", "suena", True),
    (r"podr[ií]a ser (?:aspirante|candidat[oa])", "suena", False),
    (r"va por firmas", "oficial", True),
    (r"(?:confirma|confirmó|ratifica|ratificó|anuncia|anunció|oficializa|oficializó|formaliza|formalizó) (?:su )?(?:candidatura|aspiraci[oó]n)", "oficial", True),
    (r"ser[aá] (?:el )?candidat[oa]", "oficial", True),
    (r"se lanza(?: a la alcald[ií]a)?", "oficial", True),
    (r"(?:aspira|buscará|busca) (?:a )?(?:ser )?(?:la )?alcald[ií]a", "suena", False),
    (r"renunciar[aá] (?:para|a su)", "mueve", True),
    (r"(?:declina|desiste|se baja|renuncia a su (?:candidatura|aspiraci[oó]n)|no ser[aá] candidat[oa])", "declino", True),
]
_CUE_RE = [(re.compile(rf"(?P<name>{_NAME})\s+(?P<cue>{c})"), kind, strong) for c, kind, strong in _CUES]
_ROLES = {
    "exvicepresidenta", "exvicepresidente", "vicepresidenta", "vicepresidente", "senador", "senadora", "concejal",
    "concejala", "exministro", "exministra", "ministro", "ministra", "exalcalde", "exalcaldesa", "alcalde",
    "alcaldesa", "exgobernador", "exgobernadora", "gobernador", "gobernadora", "representante", "congresista",
    "exconcejal", "exconcejala", "exsenador", "exsenadora", "doctor", "doctora", "empresario", "empresaria",
    "exsecretario", "exsecretaria", "gerente", "pastor", "padre", "presidente", "presidenta", "candidato",
    "candidata", "aspirante", "exrepresentante", "periodista", "exdirector", "exdirectora", "director", "directora",
    "dirigente", "líder", "lider", "abogado", "abogada", "médico", "medica", "rector", "rectora", "profesor", "profesora",
}
_STOP = {
    "cali", "alcaldía", "alcaldia", "gobernación", "gobernacion", "valle", "partido", "pacto", "histórico", "historico",
    "concejo", "colombia", "democrático", "democratico", "liberal", "conservador", "conservadora", "verde", "radical",
    "cambio", "centro", "unión", "union", "nuevo", "liberalismo", "estatuto", "oposición", "oposicion", "gobierno",
    "senado", "cámara", "camara", "registraduría", "registraduria", "elecciones", "diario", "occidente", "país", "pais",
    "tiempo", "semana", "caracol", "radio", "infobae", "noticias", "graffiti", "colombiano", "colombiana", "nacional",
    "social", "político", "politico", "política", "politica", "comité", "comite", "movimiento", "firmas", "consulta",
    "bogotá", "bogota", "antioquia", "medellín", "medellin", "barranquilla", "cundinamarca",
}


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    return re.sub(r"\s+", " ", "".join(c for c in t if not unicodedata.combining(c)).lower()).strip()


_STOPN = {norm(w) for w in _STOP}


def clean_title(title: str) -> tuple[str, str | None]:
    """(titular sin el medio pegado al final, medio). Google News termina en « - El País»."""
    t = (title or "").replace("\n", " ").strip().lstrip("|¿ ").strip()
    outlet = None
    m = re.search(r"\s[-–]\s([^-–]{2,40})$", t)
    if m:
        outlet, t = m.group(1).strip(), t[:m.start()].strip()
    return t, outlet


def _tidy_name(raw: str) -> str | None:
    toks = raw.split()
    while toks and norm(toks[0]) in _ROLES:
        toks.pop(0)
    if len(toks) < 2 or any(norm(t) in _STOPN for t in toks):
        return None
    if toks[0][:1].islower():
        return None
    return " ".join(toks)


def extract(title: str) -> list[dict]:
    """Nombres propuestos por un titular, con el tipo de novedad: [{name, kind, strong, cue}]."""
    t, _ = clean_title(title)
    if "alcald" not in norm(t):  # solo la Alcaldía: «sonajero de la Gobernación» no cuenta
        return []
    out, seen = [], set()
    for rx, kind, strong in _CUE_RE:
        for m in rx.finditer(t):
            name = _tidy_name(m.group("name"))
            if name and name not in seen:
                seen.add(name)
                out.append({"name": name, "kind": kind, "strong": strong, "cue": m.group("cue").lower()})
    return out


def _known(session) -> tuple[set[str], list[Candidate]]:
    cands = session.query(Candidate).filter(Candidate.kind != "city").all()
    keys = set()
    for c in cands:
        for n in [c.name, *(c.aliases or [])]:
            keys.add(norm(n))
    return keys, cands


def _is_known(name: str, keys: set[str]) -> bool:
    n = norm(name)
    if n in keys:
        return True
    toks = set(n.split())
    # «Carlos Andrés Arias» vs «Carlos Arias»: todos los nombres de uno están en el otro
    return any(len(k.split()) >= 2 and (set(k.split()) <= toks or toks <= set(k.split())) for k in keys)


def _press_titles(session, days: int):
    since = dt.datetime.utcnow() - dt.timedelta(days=days)
    when = Mention.published_at
    q = (session.query(Mention.text, Mention.url, when, Source.name).join(Source, Mention.source_id == Source.id)
         .filter(Source.type.in_(PRESS), when >= since).order_by(when.desc()))
    seen = set()
    for text, url, published, source in q:
        title, outlet = clean_title(text)
        key = norm(title)[:90]
        if len(key) < 12 or key in seen:
            continue
        seen.add(key)
        yield title, (outlet or source), url, published


def scan(session, days: int = 45) -> list[RadarSuggestion]:
    """Busca nombres nuevos en los titulares y los guarda en la lista «por revisar». Devuelve los creados."""
    keys, _ = _known(session)
    agg: dict[str, dict] = {}
    for title, outlet, url, published in _press_titles(session, days):
        for hit in extract(title):
            if _is_known(hit["name"], keys):
                continue
            a = agg.setdefault(hit["name"], {"titles": set(), "outlets": set(), "strong": False, "cue": hit["cue"],
                                             "title": title, "url": url, "first": published, "last": published})
            a["titles"].add(norm(title)[:90])
            a["outlets"].add(outlet)
            a["strong"] = a["strong"] or hit["strong"]
            if published and published > a["last"]:
                a["last"], a["title"], a["url"], a["cue"] = published, title, url, hit["cue"]
            if published and published < a["first"]:
                a["first"] = published
    created = []
    for name, a in agg.items():
        if not (a["strong"] or len(a["titles"]) >= 2):
            continue
        day = lambda d: (d or dt.datetime.utcnow()).strftime("%Y-%m-%d")  # noqa: E731
        row = session.query(RadarSuggestion).filter_by(name=name).first()
        if row is None:
            row = RadarSuggestion(name=name, first_seen=day(a["first"]), last_seen=day(a["last"]), headlines=len(a["titles"]),
                                  outlets=sorted(a["outlets"]), cue=a["cue"], sample_title=a["title"][:200], sample_url=a["url"])
            session.add(row)
            created.append(row)
        else:
            row.headlines, row.outlets, row.last_seen = len(a["titles"]), sorted(a["outlets"]), day(a["last"])
            row.sample_title, row.sample_url, row.cue = a["title"][:200], a["url"], a["cue"]
    session.commit()
    return created


def news(session, days: int = 14, limit: int = 25) -> list[dict]:
    """Novedades de los YA conocidos (candidatos y en observación): oficializó, declinó, suena, renuncia."""
    keys, cands = _known(session)
    named = {}
    for c in cands:
        if c.kind in ("candidate", "watch"):
            for n in [c.name, *(c.aliases or [])]:
                named[norm(n)] = c
    out = []
    for title, outlet, url, published in _press_titles(session, days):
        for hit in extract(title):
            c = named.get(norm(hit["name"])) or next((cc for k, cc in named.items()
                                                      if len(k.split()) >= 2 and set(k.split()) <= set(norm(hit["name"]).split())), None)
            if c is None:
                continue
            out.append({"name": c.name, "candidate_id": c.id, "kind": hit["kind"], "title": title, "outlet": outlet,
                        "url": url, "date": published.strftime("%Y-%m-%d") if published else None,
                        "state": c.status})
            break
    return out[:limit]


def _count_mentions(session, c: Candidate, days: int) -> dict:
    """Titulares de prensa que nombran a la persona (por texto, no por atribución: una nota con dos nombres
    se atribuye a uno solo)."""
    names = [norm(n) for n in [c.name, *(c.aliases or [])]]
    heads, outlets, last = set(), set(), None
    for title, outlet, url, published in _press_titles(session, days):
        t = norm(title)
        if any(n in t for n in names):
            heads.add(t[:90])
            outlets.add(outlet)
            if last is None:
                last = {"title": title, "url": url, "outlet": outlet, "date": published.strftime("%Y-%m-%d") if published else None}
    return {"headlines": len(heads), "outlets": len(outlets), "last": last}


def overview(session, days: int = 30) -> dict:
    today = dt.date.today()
    people = []
    for c in (session.query(Candidate).filter(Candidate.active.is_(True), Candidate.kind.in_(("candidate", "watch")))
              .order_by(Candidate.kind, Candidate.name).all()):
        people.append({"candidate_id": c.id, "name": c.name, "party": c.party, "kind": c.kind, "status": c.status or "revisar",
                       "note": c.status_note, "url": c.status_url, "date": c.status_date, **_count_mentions(session, c, days)})
    people.sort(key=lambda p: ({"oficial": 0, "suena": 1, "revisar": 2, "declino": 3}.get(p["status"], 2), -p["headlines"]))
    sugg = (session.query(RadarSuggestion).filter(RadarSuggestion.state == "nuevo")
            .order_by(RadarSuggestion.last_seen.desc(), RadarSuggestion.headlines.desc()).all())
    return {
        "days": days, "today": today.isoformat(), "days_to_election": (ELECTION - today).days,
        "calendar": CALENDAR, "people": people, "news": news(session),
        "suggestions": [{"id": r.id, "name": r.name, "first_seen": r.first_seen, "last_seen": r.last_seen, "headlines": r.headlines,
                         "outlets": r.outlets or [], "cue": r.cue, "title": r.sample_title, "url": r.sample_url} for r in sugg],
        "max_candidates": 9, "candidates_now": sum(1 for p in people if p["kind"] == "candidate"),
    }


# ---------- acciones de una persona ----------

def follow(session, suggestion_id: int) -> Candidate | None:
    r = session.get(RadarSuggestion, suggestion_id)
    if r is None:
        return None
    c = session.query(Candidate).filter_by(name=r.name).first()
    if c is None:
        c = Candidate(name=r.name, kind="watch", aliases=[], context_terms=["Cali", "Alcaldía", "Alcaldia"],
                      status="suena", status_note=f"Detectado en prensa: «{(r.sample_title or '')[:140]}»",
                      status_url=r.sample_url, status_date=r.last_seen)
        session.add(c)
    r.state = "siguiendo"
    session.commit()
    return c


def dismiss(session, suggestion_id: int) -> bool:
    r = session.get(RadarSuggestion, suggestion_id)
    if r is None:
        return False
    r.state = "descartado"
    session.commit()
    return True


def set_status(session, candidate_id: int, status: str, note: str | None = None, url: str | None = None) -> Candidate | None:
    c = session.get(Candidate, candidate_id)
    if c is None or status not in STATUSES or c.kind not in ("candidate", "watch"):
        return None
    c.status = status
    if note is not None:
        c.status_note = note.strip()[:300] or None
    if url is not None:
        c.status_url = url.strip()[:500] or None
    c.status_date = dt.date.today().isoformat()
    session.commit()
    return c


def promote(session, candidate_id: int) -> tuple[Candidate | None, str | None]:
    """Pasa un precandidato en observación a candidato completo. Los gráficos tienen colores para 9."""
    c = session.get(Candidate, candidate_id)
    if c is None or c.kind != "watch":
        return None, "solo se puede pasar a candidato a alguien que está en observación"
    n = session.query(Candidate).filter_by(active=True, kind="candidate").count()
    if n >= 9:
        return None, ("ya hay 9 candidatos (los gráficos tienen colores para 9): archiva a uno antes "
                      "o déjalo en observación")
    c.kind = "candidate"
    c.status = "oficial" if c.status != "oficial" else c.status
    session.commit()
    return c, None


def archive(session, candidate_id: int) -> bool:
    c = session.get(Candidate, candidate_id)
    if c is None or c.kind != "watch":
        return False
    c.active = False
    session.commit()
    return True


# ---------- avisos ----------

def _notified(session, key: str) -> bool:
    return session.get(NotifyState, key) is not None


def _mark(session, key: str) -> None:
    session.add(NotifyState(key=key, value="1"))
    session.commit()


def notify_new(session) -> int:
    """Avisa (una sola vez) de nombres nuevos por revisar y de novedades de los conocidos."""
    from src import notify
    sent = 0
    for r in session.query(RadarSuggestion).filter_by(state="nuevo", notified=False).all():
        ok = notify.send(config.NTFY_TOPIC_TEAM, f"🛰️ Suena un nombre nuevo para la Alcaldía: {r.name}",
                         f"{r.sample_title}\n\nPor revisar en el Radar de precandidatos.", priority=3, tags=["satellite"],
                         click=f"{config.DASHBOARD_URL}/#radar", view_label="Ver nota", view_url=r.sample_url)
        r.notified = True
        sent += bool(ok)
    session.commit()
    labels = {"oficial": "Oficializa", "declino": "Declina", "mueve": "Se mueve", "suena": "Suena"}
    for n in news(session, days=3):
        if n["kind"] == "suena":
            continue  # «suena» es ruido diario; se avisa lo que cambia el panorama
        key = "radar_news:" + norm(n["title"])[:80]
        if _notified(session, key):
            continue
        notify.send(config.NTFY_TOPIC_TEAM, f"🛰️ {labels.get(n['kind'], 'Novedad')}: {n['name']}", f"{n['title']}\n({n['outlet']})",
                    priority=4 if n["kind"] in ("oficial", "declino") else 3, tags=["satellite"],
                    click=f"{config.DASHBOARD_URL}/#radar", view_label="Ver nota", view_url=n["url"])
        _mark(session, key)
        sent += 1
    return sent
