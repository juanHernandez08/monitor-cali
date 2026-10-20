"""Mide cuántas menciones se pueden ubicar en una zona (solo lectura, no escribe en la base).

  * texto propio: el lugar lo nombra la mención misma;
  * heredado: un comentario sin lugar propio hereda el del video/publicación que comenta (si el
    video es sobre Siloé, los comentarios hablan de Siloé).

Uso: python scripts/geo_coverage.py [ruta_db]"""
import collections
import json
import random
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.geo import locate, is_inside_cali, norm, CALI  # noqa: E402

db = sys.argv[1] if len(sys.argv) > 1 else "monitor.db"
c = sqlite3.connect(db)
rows = c.execute("""select m.id, s.type, m.text, m.raw, m.url from mentions m join sources s on s.id = m.source_id
                    where m.relevant = 1""").fetchall()

# texto de cada publicación padre, para heredar (comentarios de redes guardan la URL de su publicación)
post_text = {}
for mid, typ, text, raw, url in rows:
    j = json.loads(raw) if raw else {}
    if j.get("kind") == "post" and url:
        post_text[url] = text or ""

stats = collections.defaultdict(collections.Counter)
levels = collections.Counter()
top = collections.Counter()
samples = []
for mid, typ, text, raw, url in rows:
    j = json.loads(raw) if raw else {}
    kind = j.get("kind") or ("comment" if typ == "YOUTUBE" and j.get("video_context") else "item")
    key = f"{typ}/{kind}"
    s = stats[key]
    s["total"] += 1
    own = locate(text or "")
    inside = [p for p in own if is_inside_cali(p["id"])]
    inherited = []
    if not inside and kind == "comment":
        if typ == "YOUTUBE":
            parent = j.get("video_context") or ""
        else:
            parent = j.get("post_title") or ""
        inherited = [p for p in locate(parent) if is_inside_cali(p["id"])]
    if inside:
        s["zona_texto_propio"] += 1
    elif inherited:
        s["zona_heredada"] += 1
    elif any(p["id"] == CALI for p in own):
        s["solo_cali_ciudad"] += 1
    elif own:
        s["otro_lugar_colombia"] += 1
    for p in inside or inherited:
        levels[p["level"]] += 1
        top[p["name"] + " (" + p["level"] + ")"] += 1
    if inside:
        p = inside[0]
        t = norm(text)
        i = t.find(p["matched"])
        samples.append((typ, p["name"], p["level"], t[max(0, i - 70):i + 70]))

print(f"menciones relevantes: {len(rows)}\n")
print(f"{'fuente/tipo':22} {'total':>6} {'zona propia':>12} {'heredada':>9} {'zona total':>11} {'solo Cali':>10} {'otro lugar':>10}")
tot = collections.Counter()
for key in sorted(stats, key=lambda k: -stats[k]["total"]):
    s = stats[key]
    tot.update(s)
    z = s["zona_texto_propio"] + s["zona_heredada"]
    print(f"{key:22} {s['total']:6} {s['zona_texto_propio']:6} ({s['zona_texto_propio']/s['total']*100:4.1f}%) {s['zona_heredada']:9} "
          f"{z:5} ({z/s['total']*100:4.1f}%) {s['solo_cali_ciudad']:10} {s['otro_lugar_colombia']:10}")
z = tot["zona_texto_propio"] + tot["zona_heredada"]
print(f"{'TOTAL':22} {tot['total']:6} {tot['zona_texto_propio']:6} ({tot['zona_texto_propio']/tot['total']*100:4.1f}%) "
      f"{tot['zona_heredada']:9} {z:5} ({z/tot['total']*100:4.1f}%) {tot['solo_cali_ciudad']:10} {tot['otro_lugar_colombia']:10}")
print("\npor nivel:", dict(levels))
print("\nlugares más nombrados:")
for name, n in top.most_common(30):
    print(f"  {n:5}  {name}")
addr = re.compile(r"\b(calle|carrera|cra\.?|cr\.?|cl\.?|avenida|av\.?|diagonal|transversal|autopista)\s*\d+[a-z]?\b")
n_addr = sum(1 for _, _, text, _, _ in rows if addr.search(norm(text or "")))
print(f"\nmenciones con una dirección o vía numerada (calle/carrera/avenida N): {n_addr}")
random.seed(7)
print("\nmuestra al azar para revisar a mano (¿está bien ubicada?):")
for typ, name, lvl, ctx in random.sample(samples, min(40, len(samples))):
    print(f"  [{typ}] {name} ({lvl}): ...{ctx}...")
