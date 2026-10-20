"""Arma el diccionario de lugares (src/geo_data/gazetteer.json) a partir de las capas oficiales
descargadas en data/geo_raw/ (no versionadas):

  * Cali -- servidor de mapas de Planeación (IDESC, ws-idesc.cali.gov.co), división político-
    administrativa del Acuerdo 0636 de 2026: 22 comunas, 342 barrios y sectores, 15 corregimientos,
    95 veredas.
  * Colombia -- servicio Divipola del DANE (Serv_DeptosMpiosANM_2018): 33 departamentos y 1.122
    municipios. El servicio MGN 2025 no entrega geometrías por consulta, por eso la versión 2018.

Cada lugar trae sus variantes de escritura y si es AMBIGUO: un nombre ambiguo ("La Paz",
"Santander", "Simón Bolívar", "20 de Julio") solo cuenta cuando el texto dice "barrio", "sector",
"vereda", etc. justo antes -- si no, una nota sobre Bolívar o sobre la paz terminaría en un barrio.

Uso: python scripts/build_geo.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.geo import norm  # noqa: E402

RAW = ROOT / "data" / "geo_raw"
OUT = ROOT / "src" / "geo_data" / "gazetteer.json"

# Una sola palabra casi siempre choca con otra cosa (un país, un apellido, un adjetivo). Estas no:
# son nombres propios de Cali que nadie usa para otra cosa.
SAFE_SINGLE = {
    "siloe", "menga", "mojica", "chipichape", "aguablanca", "aguacatal", "canaveralejo", "pasoancho",
    "salomia", "petecuy", "pizamos", "floralia", "desepaz", "calimio", "fepicol", "fonaviemcali",
    "vipasa", "villablanca", "juanambu", "cali", "pance", "felidia", "pichinde", "villacarmelo", "potrerogrande",
    "jamundi", "yumbo", "palmira", "buenaventura", "tulua", "cartago", "dagua", "bugalagrande",
    "caicedonia", "roldanillo", "zarzal", "vijes", "yotoco", "riofrio", "pradera", "guacari",
    "ansermanuevo", "medellin", "bogota", "barranquilla", "cartagena", "bucaramanga", "cucuta",
    "manizales", "popayan", "ibague", "neiva", "villavicencio", "valledupar", "sincelejo", "monteria",
    "riohacha", "quibdo", "tunja", "yopal", "mocoa", "leticia", "inirida", "mitu", "pereira",
    "antioquia", "cundinamarca", "boyaca", "risaralda", "quindio", "tolima", "huila", "caqueta",
    "putumayo", "choco", "casanare", "arauca", "vichada", "guaviare", "vaupes", "guainia",
}

# Nombres de varias palabras que también son otra cosa: fechas, personajes, frases comunes,
# lugares de otras ciudades.
AMBIGUOUS = {
    "la paz", "la libertad", "la esperanza", "la independencia", "la alianza", "la base", "la playa",
    "la isla", "la selva", "la merced", "la floresta", "la fortaleza", "la hacienda", "la cascada",
    "la campina", "la alborada", "la gran colombia", "las americas", "las acacias", "las delicias",
    "las granjas", "las ceibas", "los andes", "los pinos", "los robles", "los lagos", "los libertadores",
    "los conquistadores", "los comuneros", "los lideres", "los naranjos", "los guaduales",
    "los guayacanes", "los portales", "los parques", "el bosque", "el cedro", "el dorado", "el prado",
    "el recuerdo", "el refugio", "el remanso", "el retiro", "el rodeo", "el sena", "el troncal",
    "el trebol", "el vergel", "el jardin", "el jordan", "el ingenio", "el nacional", "el paraiso",
    "el piloto", "el diamante", "el manantial", "el cortijo", "el poblado", "el lido", "buenos aires",
    "bello horizonte", "vista hermosa", "santa fe", "santa rosa", "santa rita", "santa elena",
    "santa helena", "santa isabel", "santa barbara", "santa monica", "santa teresita", "santo domingo",
    "san antonio", "san benito", "san carlos", "san cayetano", "san cristobal", "san luis",
    "san marino", "san nicolas", "san pascual", "san pedro", "san vicente", "san francisco",
    "san miguel", "san pablo", "san juan bosco", "san pedro claver", "san judas tadeo", "patio bonito",
    "puerta del sol", "tierra blanca", "valle grande", "villa colombia", "villa del sol",
    "nuevo amanecer", "pueblo joven", "pueblo nuevo", "prados del norte", "prados del sur",
    "las orquideas", "la sultana", "el carmen", "la candelaria", "la fonda", "el futuro", "las brisas",
    "las palmas", "las nieves", "el faro", "el pinar", "el estero", "quebrada honda", "dos quebradas",
    "el otono", "el rosario", "el pato", "la sirena", "la luisa", "la maria", "la viga", "el porvenir",
    "la reforma", "la cajita", "la paila", "el banqueo", "el cerezo", "el palomar", "penas blancas",
    "las tres cruces", "el jardin", "el mango", "los laureles", "los arrayanes", "la riverita",
    "la castilla", "la elvira", "la leonera", "el hormiguero", "los cambulos", "el guabito",
    "villa del prado", "ciudad modelo", "las vegas", "nueva granada", "el coliseo", "seguros patria",
    "los samanes", "los fundadores", "las encinas", "las dalias", "las garzas", "villa luz", "berlin",
    "la chanca", "nuevo rey", "la riviera", "ciudad universitaria", "base aerea", "plaza de toros",
    "parque de la cana", "planta de tratamiento", "industria de licores", "club campestre",
    "ciudad campestre", "ciudad capri", "ciudad cordoba", "ciudad paraiso", "colinas del sur",
    "brisas de mayo", "primero de mayo", "doce de octubre", "siete de agosto", "20 de julio",
    "3 de julio", "alto jordan", "cuarteles de napoles", "alto napoles", "union de vivienda popular",
    "metropolitano del norte", "paso del comercio", "puente del comercio", "flora industrial",
    "promociones populares b", "republica de israel", "nueva tequendama", "tequendama", "los alamos",
    "brisas de los alamos", "ciudad los alamos", "ciudadela del rio", "rio cauca", "rio lili",
    "valle del lili", "parque la bandera", "pico de aguila", "pilas del cabuyal", "andes bajo",
    "la carolina", "cristo rey", "la hamaca", "alto de los mangos", "bella suiza", "kilometro 18",
    "valle del cauca", "la cumbre", "la union", "la victoria", "el cerrito", "el aguila", "el cairo",
    "el dovio", "santa marta", "san andres", "la guajira", "norte de santander", "san jose del guaviare",
    "el darien", "zoologico", "jardin botanico", "unidad deportiva", "alberto galindo",
    "jaime aparicio", "las quintas de don simon", "camino real", "bosques del limonar",
}
# "la union", "valle del cauca", etc. arriba quedan ambiguos a propósito solo cuando son variantes de barrio;
# como municipio/departamento se evalúan con MUNICIPAL_SAFE.
MUNICIPAL_SAFE = {"valle del cauca", "norte de santander", "la guajira", "san andres", "santa marta",
                  "san jose del guaviare", "el cerrito", "la cumbre", "el dovio", "el aguila"}

# Barrios con nombre de personaje: en una nota política se refieren a la persona, no al barrio.
PEOPLE = {
    "antonio narino", "simon bolivar", "jorge isaacs", "eduardo santos", "olaya herrera",
    "rafael uribe uribe", "laureano gomez", "lleras restrepo", "lleras camargo", "jorge eliecer gaitan",
    "marco fidel suarez", "benjamin herrera", "belisario caicedo", "evaristo garcia",
    "jose maria cordoba", "guillermo valencia", "omar torrijos", "rodrigo lara bonilla", "alfonso lopez",
    "alfonso lopez pumarejo", "alfonso bonilla aragon", "alfonso barberena", "alfonso barberena a.",
    "manuel maria buenaventura", "jose holguin garces", "jorge zawadsky", "jose manuel marroquin",
    "francisco eladio ramirez", "mario correa rengifo", "julio rincon", "ricardo balcazar",
    "ignacio rengifo", "ulpiano lloreda", "primitivo crespo", "saavedra galindo", "atanasio girardot",
    "cristobal colon", "leon xiii", "joaquin borrero sinisterra", "bueno madrid", "santiago de cali",
    "angel del hogar", "san joaquin", "lleras restrepo ii", "marroquin iii", "boyaca",
}

_PREFIX = re.compile(r"^(sector|urbanizacion|unidad residencial|ciudadela|barrio)\s+")
_STAGE = re.compile(r"\s+(primera|segunda|tercera|1a|2a|3a|i{1,3}|ii etapa)(\s+etapa)?$")
_CABECERA = re.compile(r"\s*\(cabecera\)\s*$")


def variants(name: str) -> list[str]:
    n = _CABECERA.sub("", norm(name))
    out = {n}
    for part in [p.strip() for p in n.split(" - ")] if " - " in n else [n]:
        out.add(part)
        base = _PREFIX.sub("", part)
        out.add(base)
        out.add(_STAGE.sub("", base))
    # "Ciudadela del Río" sin el prefijo queda "del rio": eso ya no es un nombre de lugar
    out = {v for v in out if len(v) >= 4 and not re.match(r"^(de|del)\s", v) or v in (n,)}
    return sorted(out, key=len, reverse=True)


def short_names(official: str) -> set[str]:
    """Nombre oficial del DANE -> como lo escribe la gente: "Distrito Especial, Industrial y Portuario de
    Barranquilla" -> "barranquilla"; "Bogotá, D.C." -> "bogota"; "Cartagena de Indias" -> "cartagena"."""
    n = norm(official)
    out = {n, re.sub(r",.*$", "", n)}
    if n.startswith("distrito") or n.startswith("archipielago"):
        out.add(re.sub(r",.*$", "", n.rsplit(" de ", 1)[1]) if " de " in n else n)
    if n == "cartagena de indias":
        out.add("cartagena")
    return {v for v in out if v}


def display(official: str) -> str:
    """"DISTRITO ESPECIAL, INDUSTRIAL Y PORTUARIO DE BARRANQUILLA" -> "Barranquilla"; "BOGOTÁ, D.C." -> "Bogotá"."""
    n = official.strip()
    if n.upper().startswith(("DISTRITO", "ARCHIPIÉLAGO", "ARCHIPIELAGO")) and " DE " in n.upper():
        n = n[n.upper().rindex(" DE ") + 4:]
    n = re.sub(r",.*$", "", n).title()
    return re.sub(r"\b(De|Del|La|Las|Los|Y)\b(?!$)", lambda m: m.group(1).lower(), n[:1]) + \
        re.sub(r"\b(De|Del|La|Las|Los|Y)\b", lambda m: m.group(1).lower(), n[1:])


def is_ambiguous(v: str, other_places: set[str]) -> bool:
    if v in other_places:  # un barrio que se llama como un municipio ("Barranquilla") es ambiguo siempre
        return True
    if v in PEOPLE or v in AMBIGUOUS or re.match(r"^\d+ de ", v):
        return True
    if " " not in v:
        return v not in SAFE_SINGLE
    return False


def load(name: str) -> list[dict]:
    return json.loads((RAW / name).read_text(encoding="utf-8"))["features"]


def main():
    comunas = load("cali_comunas.geojson")
    barrios = load("cali_barrios_sectores.geojson")
    correg = load("cali_corregimientos.geojson")
    veredas = load("cali_veredas.geojson")
    dptos = load("col_departamentos.geojson")
    mpios = load("col_municipios.geojson")

    # nombres de municipios/departamentos: un barrio que se llama igual que un municipio es ambiguo
    colombia_names = ({v for f in mpios for v in short_names(f["properties"]["MPIO_CNMBR"])}
                      | {v for f in dptos for v in short_names(f["properties"]["DPTO_CNMBR"])})

    places = []
    for f in comunas:
        p = f["properties"]
        places.append({"id": f"comuna:{p['comcodigo']}", "level": "comuna", "code": p["comcodigo"],
                       "name": f"Comuna {int(p['comcodigo'])}", "parent": "76001", "variants": []})
    for f in barrios:
        p = f["properties"]
        vs = variants(p["barnombre"])
        places.append({"id": f"barrio:{p['barcodigo']}", "level": "barrio", "code": p["barcodigo"],
                       "name": p["barnombre"], "category": p["barcategor"], "parent": f"comuna:{p['barcomuna']}",
                       "variants": [{"text": v, "ambiguous": is_ambiguous(v, colombia_names)} for v in vs]})
    for f in correg:
        p = f["properties"]
        vs = variants(p["corrnombre"])
        if norm(p["corrnombre"]) == "pichinde":
            vs.append("pichinde")
        places.append({"id": f"corregimiento:{p['corrcod']}", "level": "corregimiento", "code": p["corrcod"],
                       "name": p["corrnombre"], "parent": "76001",
                       "variants": [{"text": v, "ambiguous": is_ambiguous(v, colombia_names) or v == "navarro"} for v in vs]})
    for f in veredas:
        p = f["properties"]
        vs = variants(p["vernombre"])
        # una vereda que se llama igual que su corregimiento ("Pance (Cabecera)") ya la cubre el corregimiento
        vs = [v for v in vs if v != norm(p["vercorregi"])]
        places.append({"id": f"vereda:{p['vercodigo']}", "level": "vereda", "code": p["vercodigo"],
                       "name": p["vernombre"], "parent": f"corregimiento:{p['vercodcorr']}",
                       "variants": [{"text": v, "ambiguous": is_ambiguous(v, colombia_names)} for v in vs]})
    for f in dptos:
        p = f["properties"]
        vs = short_names(p["DPTO_CNMBR"])
        places.append({"id": f"departamento:{p['DPTO_CCDGO']}", "level": "departamento", "code": p["DPTO_CCDGO"],
                       "name": display(p["DPTO_CNMBR"]), "parent": "co",
                       "variants": [{"text": v, "ambiguous": not (v in SAFE_SINGLE or v in MUNICIPAL_SAFE)} for v in sorted(vs)]})
    for f in mpios:
        p = f["properties"]
        code = p["MPIO_CCDGO"]
        # Colombia a nivel municipio: el Valle completo y las capitales de departamento (código terminado en 001)
        if not (p["DPTO_CCDGO"] == "76" or code.endswith("001")):
            continue
        vs = short_names(p["MPIO_CNMBR"])
        if code == "76111":
            vs |= {"buga", "guadalajara de buga"}
        if code == "11001":
            vs |= {"bogota"}
        # "Barranquilla" a secas es la ciudad aunque exista el barrio "Los Parques - Barranquilla"
        amb = lambda v: not (v in SAFE_SINGLE or v in MUNICIPAL_SAFE)  # noqa: E731
        places.append({"id": f"municipio:{code}", "level": "municipio", "code": code,
                       "name": display(p["MPIO_CNMBR"]), "parent": f"departamento:{p['DPTO_CCDGO']}",
                       "variants": [{"text": v, "ambiguous": amb(v)} for v in sorted(vs)]})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": "IDESC Cali (Acuerdo 0636 de 2026) + DANE Divipola 2018",
                               "places": places}, ensure_ascii=False, indent=0), encoding="utf-8")
    amb = sum(1 for p in places for v in p["variants"] if v["ambiguous"])
    tot = sum(len(p["variants"]) for p in places)
    print(f"{len(places)} lugares, {tot} variantes ({amb} ambiguas) -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
