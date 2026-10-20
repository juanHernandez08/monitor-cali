"""Georreferenciación de menciones por el TEXTO: qué comuna, barrio, corregimiento o vereda de Cali
(o qué municipio/departamento de Colombia) nombra cada publicación, comentario o nota.

Las redes no entregan la ubicación de quien comenta (medido 2026-10-20 sobre 9.828 menciones: ningún
comentario la trae), así que el mapa mide DE QUÉ ZONA se habla, no desde dónde se habla. Es siempre
agregado por zona: nunca se ubica a una persona.

El diccionario (src/geo_data/gazetteer.json) sale de las capas oficiales -- ver scripts/build_geo.py.
Un nombre AMBIGUO ("La Paz", "Simón Bolívar", "20 de Julio") solo cuenta si el texto dice "barrio",
"sector", "vereda", etc. justo antes, y además habla de Cali."""
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

GAZETTEER = Path(__file__).resolve().parent / "geo_data" / "gazetteer.json"
CALI = "municipio:76001"

_NUM_WORDS = {"uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
              "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
              "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20,
              "veintiuno": 21, "veintidos": 22}
_NUM_ALT = "|".join(sorted(_NUM_WORDS, key=len, reverse=True))
_COMUNA = re.compile(r"\bcomunas?\s+((?:(?:n(?:o|ro|umero)?\.?\s*)?(?:\d{1,2}|" + _NUM_ALT +
                     r")\b(?:\s*(?:,|y|e|-)\s*)?)+)")
_COMUNA_NUM = re.compile(r"\d{1,2}|" + _NUM_ALT)
_TRIGGER_LOCAL = re.compile(r"(barrios?|sector(?:es)?|urbanizacion|vereda|veredas|corregimientos?|comuna \d{1,2}|b/|"
                            r"conjunto|unidad residencial|ciudadela)\s*(de |del |el |la |los |las )?$")
_TRIGGER_CITY = re.compile(r"(municipios?|departamentos?|ciudad|alcaldia)\s+(de |del )?(la |el )?$")
_ABOUT_CALI = re.compile(r"\bcali\b|\bcalen[oa]s?\b")
_LEVEL_OF_TRIGGER = (("barrio", "barrio"), ("b/", "barrio"), ("urbaniz", "barrio"), ("sector", "barrio"),
                     ("conjunto", "barrio"), ("unidad", "barrio"), ("ciudadela", "barrio"),
                     ("vereda", "vereda"), ("corregim", "corregimiento"))
# "Aguablanca" a secas casi siempre es el Distrito de Aguablanca (comunas 13, 14, 15 y 21), no el barrio
# de ese nombre en la comuna 8 -- el barrio solo cuenta si dice "barrio Aguablanca".
REGIONS = {"distrito de aguablanca": ["13", "14", "15", "21"], "aguablanca": ["13", "14", "15", "21"],
           # "oriente de Cali" y "la ladera" se leen con los núcleos territoriales de la campaña (Oriente, Ladera)
           "oriente de cali": ["13", "14", "15", "16", "21"], "zona de ladera": ["01", "18", "19", "20"],
           "laderas de cali": ["01", "18", "19", "20"], "ladera de cali": ["01", "18", "19", "20"]}


# Fútbol: "Deportes Tolima", "Junior de Barranquilla" o una tabla de posiciones ("2. tolima 16 pts")
# no hablan de esos lugares. Los nombres de equipo se borran antes de buscar, y en un texto claramente
# deportivo no se cuentan municipios ni departamentos (sí las zonas de Cali: "hinchas en Siloé").
_TEAMS = re.compile(r"\b(deportes tolima|deportivo pereira|atletico bucaramanga|independiente medellin|"
                    r"atletico nacional|junior de barranquilla|junior fc|boyaca chico|once caldas|deportivo pasto|"
                    r"deportes quindio|cucuta deportivo|alianza valledupar|alianza fc|aguilas doradas|"
                    r"union magdalena|jaguares de cordoba|real cartagena|patriotas boyaca|america de cali|"
                    r"deportivo cali|atletico huila|llaneros fc|fortaleza ceif|real santander|internacional de bogota|"
                    r"tigres fc|orsomarso|boca juniors de cali|atletico fc|bogota fc|leones fc|real cundinamarca)\b")
_SPORTS = re.compile(r"\b(liga betplay|betplay|futbol|partido|gol(es)?|hinchas?|entrenador|tecnico|delantero|"
                     r"arquero|fecha \d+|\d+ pts|clasico|estadio|torneo|campeonato|dimayor|convocatoria)\b")


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^\w\s/\-.,]", " ", t)  # quita signos que no separan palabras útiles
    return re.sub(r"\s+", " ", t).strip()


@lru_cache(maxsize=1)
def _index():
    data = json.loads(GAZETTEER.read_text(encoding="utf-8"))
    places = {p["id"]: p for p in data["places"]}
    by_variant: dict[str, list[tuple[str, bool]]] = {}
    for p in data["places"]:
        for v in p["variants"]:
            by_variant.setdefault(v["text"], []).append((p["id"], v["ambiguous"]))
    for r in REGIONS:
        by_variant.setdefault(r, [])  # para que la expresión la reconozca
    alts = sorted(by_variant, key=len, reverse=True)
    rx = re.compile(r"(?<![\w])(" + "|".join(re.escape(a) for a in alts) + r")(?![\w])")
    return places, by_variant, rx


def place(pid: str) -> dict | None:
    return _index()[0].get(pid)


def ancestors(pid: str) -> list[str]:
    """barrio:0216 -> [comuna:02, municipio:76001, departamento:76]."""
    places = _index()[0]
    out = []
    p = places.get(pid)
    while p:
        parent = p.get("parent")
        if not parent or parent == "co":
            break
        parent = CALI if parent == "76001" else parent
        out.append(parent)
        p = places.get(parent)
    return out


def _resolve(cands: list[str], trigger_word: str | None) -> str | None:
    """Un mismo nombre en varias zonas: la palabra de antes dice el nivel ("barrio La Paz" no es el
    corregimiento La Paz); si sigue habiendo varias, una que contiene a la otra gana la más específica
    ("Bogotá" municipio vs. departamento); si no, solo se afirma lo que tienen en común."""
    places = _index()[0]
    if len(cands) > 1 and trigger_word:
        level = next((lvl for prefix, lvl in _LEVEL_OF_TRIGGER if trigger_word.startswith(prefix)), None)
        cands = [c for c in cands if places[c]["level"] == level] or cands
    if len(cands) > 1:
        cands = [c for c in cands if not any(c in ancestors(o) for o in cands if o != c)]
    if len(cands) == 1:
        return cands[0]
    common = set(ancestors(cands[0]))
    for c in cands[1:]:
        common &= set(ancestors(c))
    return next((a for lvl in ("comuna", "corregimiento", "municipio") for a in common if a.startswith(lvl + ":")), None)


def locate(text: str) -> list[dict]:
    """Lugares nombrados en `text`. Cada uno: id, level, name y el fragmento que lo disparó (para poder
    auditar por qué se ubicó ahí)."""
    places, by_variant, rx = _index()
    t = norm(text)
    sports = len(set(m.group(0) for m in _SPORTS.finditer(t))) >= 2
    t = _TEAMS.sub(" ", t)
    found: dict[str, str] = {}
    # un nombre ambiguo con "barrio"/"vereda" delante puede ser de OTRO municipio ("vereda La Esperanza"
    # en una operación militar del Cauca): solo cuenta si el texto habla de Cali
    about_cali = bool(_ABOUT_CALI.search(t))

    for m in _COMUNA.finditer(t):
        for n in _COMUNA_NUM.findall(m.group(1)):
            num = _NUM_WORDS.get(n) or int(n)
            pid = f"comuna:{num:02d}"
            if pid in places:
                found.setdefault(pid, re.sub(r"[\s,ye-]+$", "", m.group(0)))

    for m in rx.finditer(t):
        v = m.group(1)
        before = t[max(0, m.start() - 32):m.start()]
        trig = _TRIGGER_LOCAL.search(before)
        if v in REGIONS and not trig:
            for c in REGIONS[v]:
                found.setdefault(f"comuna:{c}", v)
            continue
        city_trig = bool(_TRIGGER_CITY.search(before))
        cands = [pid for pid, amb in by_variant[v]
                 if not amb
                 or (trig and about_cali and places[pid]["level"] in ("barrio", "vereda", "corregimiento"))
                 or (city_trig and places[pid]["level"] in ("municipio", "departamento"))]
        if not cands:
            continue
        pid = _resolve(cands, trig.group(1) if trig else None)
        if pid and sports and places[pid]["level"] in ("municipio", "departamento"):
            continue
        if pid:
            found.setdefault(pid, v)

    return [{"id": pid, "level": places[pid]["level"], "name": places[pid]["name"], "matched": matched}
            for pid, matched in found.items()]


def is_inside_cali(pid: str) -> bool:
    return pid != CALI and CALI in ancestors(pid)


def _most_specific(found: list[dict]) -> list[dict]:
    """Si una mención nombra "barrio Siloé" y "comuna 20", basta Siloé (ya sube a la comuna 20)."""
    ids = {p["id"] for p in found}
    return [p for p in found if not any(p["id"] in ancestors(o) for o in ids if o != p["id"])]


def places_for_mention(mention, parent_text: str | None = None) -> list[dict]:
    """Zonas de una mención, con el método que las encontró: 'texto' (la mención misma, incluido el
    cuerpo de la nota), 'heredado' (un comentario sin lugar propio toma el del video/publicación que
    comenta) e 'ia' (el lugar que leyó el LLM, normalizado contra el diccionario oficial).
    `parent_text`: el texto COMPLETO de la publicación comentada, si se tiene (el `post_title` que
    guarda el comentario son solo los primeros ~90 caracteres y casi nunca trae el lugar)."""
    raw = mention.raw or {}
    own = locate(f"{mention.text}\n{(mention.body or '')[:3000]}")
    out = [{**p, "method": "texto"} for p in own]
    has_zone = any(is_inside_cali(p["id"]) for p in own)
    if not has_zone and raw.get("kind") == "comment":
        parent = parent_text or raw.get("video_title") or raw.get("video_context") or raw.get("post_title") or ""
        inherited = [p for p in locate(parent) if is_inside_cali(p["id"])]
        out += [{**p, "method": "heredado"} for p in inherited]
        has_zone = bool(inherited)
    hint = getattr(getattr(mention, "sentiment", None), "place_hint", None)
    if not has_zone and hint:
        # el LLM ya dijo que es un lugar de Cali: se lee como "barrio X de Cali" para que los nombres
        # ambiguos ("La Paz") cuenten, y se normaliza contra la lista oficial (lo que no esté, se descarta)
        guess = hint if re.search(r"\b(comuna|barrio|vereda|corregimiento|sector)\b", norm(hint)) else f"barrio {hint}"
        out += [{**p, "method": "ia"} for p in locate(f"{guess}, Cali") if is_inside_cali(p["id"])]
    seen, uniq = set(), []
    for p in _most_specific(out):
        if p["id"] not in seen:
            seen.add(p["id"])
            uniq.append(p)
    return uniq


def assign_places(session, mention) -> int:
    """Recalcula y guarda las zonas de `mention` (idempotente). No hace commit."""
    from src.models import Mention, MentionPlace
    session.query(MentionPlace).filter_by(mention_id=mention.id).delete()
    parent_text = None
    raw = mention.raw or {}
    if raw.get("kind") == "comment" and raw.get("platform") and mention.url:
        # el comentario guarda la URL de su publicación: es la misma URL de la mención de esa publicación
        for p in (session.query(Mention).filter(Mention.url == mention.url, Mention.id != mention.id)
                  .limit(20).all()):
            if (p.raw or {}).get("kind") == "post":
                parent_text = f"{p.text}\n{(p.body or '')[:3000]}"
                break
    found = places_for_mention(mention, parent_text)
    for p in found:
        session.add(MentionPlace(mention_id=mention.id, place_id=p["id"], level=p["level"],
                                 matched=(p.get("matched") or "")[:120], method=p["method"]))
    return len(found)
