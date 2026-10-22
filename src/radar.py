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

from sqlalchemy import func

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
    (r"renunciar[aá] (?:para|a su (?:curul|cargo|puesto|gerencia|direcci[oó]n))", "mueve", True),
    # RETIRO: solo frases inequívocas. Con ellas el radar saca a la persona de las listas (ver apply_changes).
    (r"(?:declina|declinó|desiste|desistió|se baja|se bajó|se retira|se retiró|retira|retiró|renuncia|renunció|renunciará) "
     r"(?:de |a |a la |a su |su |de su )?(?:la )?(?:candidatura|aspiraci[oó]n|carrera|contienda|alcald[ií]a|carrera por la alcald[ií]a)", "declino", True),
    (r"(?:no ser[aá]|no va a ser|ya no ser[aá]) (?:el |la )?candidat[oa]", "declino", True),
    (r"(?:descarta|descartó) (?:aspirar|ser candidat[oa]|su candidatura|su aspiraci[oó]n|lanzarse)", "declino", True),
    (r"no (?:aspirar[aá]|se lanzar[aá]|ir[aá] a la alcald[ií]a|buscar[aá] la alcald[ií]a)", "declino", True),
    (r"dice no a (?:la alcald[ií]a|su candidatura)", "declino", True),
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
    # NFC: algunos titulares de Google News llegan con la tilde "descompuesta" (a + acento suelto) y los patrones
    # de abajo no los reconocían (pasó con «¿Roger Mina renunciará para ser candidato...?», 2026-10-21).
    t = unicodedata.normalize("NFC", title or "").replace("\n", " ").strip().lstrip("|¿ ").strip()
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
    when = func.coalesce(Mention.published_at, Mention.fetched_at)
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
        if c.kind in ("candidate", "watch", "retired"):
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
    retired = []
    for c in (session.query(Candidate).filter(Candidate.kind.in_(("candidate", "watch", "retired")))
              .order_by(Candidate.kind, Candidate.name).all()):
        row = {"candidate_id": c.id, "name": c.name, "party": c.party, "kind": c.kind, "status": c.status or "revisar",
               "note": c.status_note, "url": c.status_url, "date": c.status_date}
        if c.kind == "retired":
            retired.append({**row, "was": c.retired_from})
        elif c.active:
            people.append({**row, **_count_mentions(session, c, days)})
    people.sort(key=lambda p: ({"oficial": 0, "suena": 1, "revisar": 2, "declino": 3}.get(p["status"], 2), -p["headlines"]))
    sugg = (session.query(RadarSuggestion).filter(RadarSuggestion.state == "nuevo")
            .order_by(RadarSuggestion.last_seen.desc(), RadarSuggestion.headlines.desc()).all())
    return {
        "days": days, "today": today.isoformat(), "days_to_election": (ELECTION - today).days,
        "calendar": CALENDAR, "people": people, "retired": sorted(retired, key=lambda r: r["date"] or "", reverse=True), "news": news(session),
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


PROTECTED = {"Carlos Arias"}  # el candidato del cliente: el radar avisa, pero nunca lo saca por un titular
MIN_OUTLETS_CANDIDATE = 2  # sacar a uno de los 9 candidatos exige que lo cuenten al menos 2 medios distintos


def _manual_key(candidate_id: int) -> str:
    return f"radar_manual_retire:{candidate_id}"


def retire(session, c: Candidate, note: str | None = None, url: str | None = None, manual: bool = False) -> None:
    """Saca a la persona de listas y gráficos (kind="retired", todas las consultas filtran por kind) y deja de
    buscarla (active=False). Las menciones ya guardadas se conservan: se puede reactivar sin perder historia.
    `manual`: lo decidió una persona del equipo; entonces la prensa no la reactiva sola (solo el botón «Reactivar»)."""
    if c.kind != "retired":
        c.retired_from = c.kind
    c.kind, c.active, c.status = "retired", False, "declino"
    c.status_note = (note or "Anunció que no será candidato.")[:300]
    c.status_url = url  # la nota del retiro; sin ella no se deja la vieja de «suena» como si respaldara el retiro
    c.status_date = dt.date.today().isoformat()
    if manual and not _notified(session, _manual_key(c.id)):
        session.add(NotifyState(key=_manual_key(c.id), value="1"))
    session.commit()


def restore(session, candidate_id: int, status: str = "suena") -> Candidate | None:
    c = session.get(Candidate, candidate_id)
    if c is None or c.kind != "retired":
        return None
    flag = session.get(NotifyState, _manual_key(c.id))
    if flag is not None:
        session.delete(flag)
    c.kind, c.active, c.status = c.retired_from or "watch", True, status
    c.retired_from = None
    c.status_note = (c.status_note or "") + " (reactivado)"
    c.status_date = dt.date.today().isoformat()
    session.commit()
    return c


def _reports(session, days: int) -> dict[int, dict[str, dict]]:
    """Por persona y tipo de novedad: titulares distintos y medios distintos que la cuentan."""
    keys, cands = _known(session)
    named = {}
    for c in cands:
        if c.kind in ("candidate", "watch", "retired"):
            for n in [c.name, *(c.aliases or [])]:
                named[norm(n)] = c
    out: dict[int, dict[str, dict]] = {}
    for title, outlet, url, published in _press_titles(session, days):
        for hit in extract(title):
            nm = norm(hit["name"])
            c = named.get(nm) or next((cc for k, cc in named.items() if len(k.split()) >= 2 and set(k.split()) <= set(nm.split())), None)
            if c is None:
                continue
            slot = out.setdefault(c.id, {}).setdefault(hit["kind"], {"titles": set(), "outlets": set(), "title": title, "url": url,
                                                                      "outlet": outlet, "date": published})
            slot["titles"].add(norm(title)[:90])
            slot["outlets"].add(outlet)
            break
    return out


def apply_changes(session, days: int = 7) -> list[dict]:
    """Mantiene la lista al día SIN que nadie la toque:
      * si la prensa informa que alguien se RETIRA («no será candidato», «renunció a su aspiración», «descarta aspirar»),
        sale de listas y gráficos y se avisa al equipo. Un precandidato en observación sale con un solo titular;
        uno de los 9 candidatos exige 2 medios distintos; Carlos Arias nunca se saca solo (solo se avisa).
      * si alguien retirado vuelve a OFICIALIZAR su candidatura (2 medios), se reactiva.
    Todo es reversible desde el tablero («Reactivar»). Devuelve lo que cambió."""
    from src import notify
    changes = []
    reps = _reports(session, days)
    for cid, kinds in reps.items():
        c = session.get(Candidate, cid)
        if c is None:
            continue
        d = kinds.get("declino")
        if d and c.kind != "retired":
            enough = len(d["outlets"]) >= (MIN_OUTLETS_CANDIDATE if c.kind == "candidate" else 1)
            key = f"radar_retire:{c.id}:{norm(d['title'])[:60]}"
            if _notified(session, key):
                continue
            if c.name in PROTECTED or not enough:
                notify.send(config.NTFY_TOPIC_TEAM, f"🛰️ Posible retiro de {c.name} (por confirmar)",
                            f"{d['title']}\n({d['outlet']}) — no se sacó del monitor: " +
                            ("es el candidato del cliente." if c.name in PROTECTED else "solo lo reporta un medio; esperando otro."),
                            priority=4, tags=["warning"], click=f"{config.DASHBOARD_URL}/#radar", view_label="Ver nota", view_url=d["url"])
                if c.name in PROTECTED:
                    _mark(session, key)  # una sola vez; si no se confirma con más medios, se reintenta en el próximo ciclo
                continue
            retire(session, c, f"Se retiró: «{d['title'][:200]}» ({d['outlet']})", d["url"])
            _mark(session, key)
            changes.append({"name": c.name, "change": "retiro", "title": d["title"], "url": d["url"]})
            notify.send(config.NTFY_TOPIC_TEAM, f"🛰️ Se retira: {c.name}",
                        f"{d['title']}\n({d['outlet']})\n\nSalió de las listas y de los gráficos. Si fue un error, se reactiva en el Radar.",
                        priority=4, tags=["door"], click=f"{config.DASHBOARD_URL}/#radar", view_label="Ver nota", view_url=d["url"])
        elif (c.kind == "retired" and kinds.get("oficial") and len(kinds["oficial"]["outlets"]) >= 2
              and not _notified(session, _manual_key(c.id))):  # un retiro manual solo lo revierte una persona
            o = kinds["oficial"]
            key = f"radar_return:{c.id}:{norm(o['title'])[:60]}"
            if _notified(session, key):
                continue
            restore(session, c.id, "oficial")
            _mark(session, key)
            changes.append({"name": c.name, "change": "regreso", "title": o["title"], "url": o["url"]})
            notify.send(config.NTFY_TOPIC_TEAM, f"🛰️ Vuelve: {c.name} oficializa su candidatura", f"{o['title']}\n({o['outlet']})",
                        priority=4, tags=["leftwards_arrow_with_hook"], click=f"{config.DASHBOARD_URL}/#radar", view_label="Ver nota", view_url=o["url"])
    return changes


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
        if n["kind"] in ("suena", "declino"):
            continue  # «suena» es ruido diario; los retiros los avisa apply_changes (con lo que se hizo)
        key = "radar_news:" + norm(n["title"])[:80]
        if _notified(session, key):
            continue
        notify.send(config.NTFY_TOPIC_TEAM, f"🛰️ {labels.get(n['kind'], 'Novedad')}: {n['name']}", f"{n['title']}\n({n['outlet']})",
                    priority=4 if n["kind"] in ("oficial", "declino") else 3, tags=["satellite"],
                    click=f"{config.DASHBOARD_URL}/#radar", view_label="Ver nota", view_url=n["url"])
        _mark(session, key)
        sent += 1
    return sent
