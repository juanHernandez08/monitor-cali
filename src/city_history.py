"""Cali 2008 a 2026: indicadores económicos, sociales, de seguridad, salud y transporte por alcaldía.

Pedido del cliente (2026-09-29): la pestaña Histórico debe ir desde 2008 hasta el año en curso,
muy detallada, con fuentes confiables, en cinco frentes (económico, social, seguridad, salud y
transporte), con un análisis por período comparado hasta el presente y una conclusión con
estrategias viables para Carlos Arias.

Reglas de este módulo (las exige tests/test_city_history.py):
  * "Nada simulado": cada valor de cada serie apunta a una fuente con URL específica (no la
    página de inicio de un medio). Si un año no se pudo verificar, NO se interpola ni se estima:
    queda ausente y la gráfica muestra el hueco.
  * Cuando dos ediciones de una misma fuente no coinciden (revisiones de DANE, cambios de
    proyección de población), se usa la edición MÁS RECIENTE y se deja la nota.
  * Los cambios metodológicos se marcan en `notes` (p. ej. pobreza monetaria antes y después de
    la actualización DANE de 2020; GEIH con marco muestral 2018 desde 2021).

Fuente principal: informes de Calidad de Vida de Cali Cómo Vamos (CCV), que consolidan cifras
oficiales (DANE, Observatorio de Seguridad / CIMCE, Secretarías de Salud y Movilidad, Metrocali,
Medicina Legal). Complementos: boletines DANE (ICER, pobreza monetaria, ETUP) y prensa que cita
DANE para el dato más reciente.

    python -m pytest tests/test_city_history.py
"""
from __future__ import annotations

CURRENT_YEAR = 2026  # la alcaldía 2024-2027 sigue en curso; su último dato anual cerrado es 2025
# 2007 solo se usa como punto de partida: es la ciudad que recibió la primera alcaldía analizada.
BASELINE_YEAR = 2007

PERIODS = [
    {"id": "ospina-1", "mayor": "Jorge Iván Ospina", "start": 2008, "end": 2011,
     "label": "Ospina I (2008-2011)", "status": "completado"},
    {"id": "guerrero", "mayor": "Rodrigo Guerrero", "start": 2012, "end": 2015,
     "label": "Guerrero (2012-2015)", "status": "completado"},
    {"id": "armitage", "mayor": "Maurice Armitage", "start": 2016, "end": 2019,
     "label": "Armitage (2016-2019)", "status": "completado"},
    {"id": "ospina-2", "mayor": "Jorge Iván Ospina", "start": 2020, "end": 2023,
     "label": "Ospina II (2020-2023)", "status": "completado"},
    {"id": "eder", "mayor": "Alejandro Eder", "start": 2024, "end": 2027,
     "label": "Eder (2024-2027, en curso)", "status": "en curso"},
]

_CCV = "https://www.calicomovamos.org.co/_files/ugd/ba6905_"
SOURCES = {
    "ccv26_seg": {"name": "Cali Cómo Vamos, Informe de Calidad de Vida 2026 (datos 2025), Seguridad",
                  "url": _CCV + "f8ec7350bcda4f9a87b2e4e070cc61bb.pdf"},
    "ccv26_lab": {"name": "Cali Cómo Vamos, ICV 2026 (datos 2025), Mercado laboral (DANE GEIH)",
                  "url": _CCV + "2f556ddf87f34505a32fb6c6325f0095.pdf"},
    "ccv26_mov": {"name": "Cali Cómo Vamos, ICV 2026 (datos 2025), Movilidad (DANE ETUP, Secretaría de Movilidad)",
                  "url": _CCV + "af8fa50190cf4b8881a7626bda69fe54.pdf"},
    "ccv26_conv": {"name": "Cali Cómo Vamos, ICV 2026 (datos 2025), Convivencia (Medicina Legal)",
                   "url": _CCV + "1cb34a1f1b9d46ce89e998c1acf775bc.pdf"},
    "ccv25_seg": {"name": "Cali Cómo Vamos, ICV 2025 (datos 2024), Seguridad (CIMCE, Policía Nacional)",
                  "url": _CCV + "58e6f0efd57f429fafa22eaf837e7b3c.pdf"},
    "ccv25_sal": {"name": "Cali Cómo Vamos, ICV 2025 (datos 2024), Salud (DANE Estadísticas Vitales, MinSalud)",
                  "url": _CCV + "b0557549e8364f138335e0ce7d48b902.pdf"},
    "ccv24_eco": {"name": "Cali Cómo Vamos, ICV 2024 (datos 2023), Entorno económico (DANE, PUJ, Banco de la República, CCC)",
                  "url": _CCV + "822d633bb1fe4621a8d5e0b84a115cd4.pdf"},
    "ccv21_sal": {"name": "Cali Cómo Vamos, ICV 2021 (datos 2020), Salud (Secretaría de Salud Pública, INS)",
                  "url": _CCV + "5f4b7bb1625e4af5a199848b8e41afce.pdf"},
    "ccv21_mov": {"name": "Cali Cómo Vamos, ICV 2021 (datos 2020), Movilidad (Secretaría de Movilidad, Metrocali)",
                  "url": _CCV + "43efc6c89b09409da31e8bf2180d737c.pdf"},
    "ccv20_sal": {"name": "Cali Cómo Vamos, ICV 2020 (datos 2019), Salud (Secretaría de Salud Pública)",
                  "url": _CCV + "b5a727165d684c97a5e6080484acaf15.pdf"},
    "ccv20_eco": {"name": "Cali Cómo Vamos, ICV 2020 (datos 2019), Actividad económica (DANE GEIH)",
                  "url": _CCV + "b90f01194dc94933ab3534228ec50215.pdf"},
    "ccv19_eco": {"name": "Cali Cómo Vamos, ICV 2019 (datos 2018), Actividad económica (DANE GEIH)",
                  "url": _CCV + "fb622799bc424e439566eddaa0511a66.pdf"},
    "ccv19_mov": {"name": "Cali Cómo Vamos, ICV 2019 (datos 2018), Movilidad (Secretaría de Movilidad)",
                  "url": _CCV + "fa1e53c8ec0746b2a855a142dbf4d43a.pdf"},
    "ccv19_pob": {"name": "Cali Cómo Vamos, ICV 2019 (datos 2018), Pobreza y equidad (DANE, metodología MESEP)",
                  "url": _CCV + "be89b96ed8ae49ac96ba8ab68d33c3d2.pdf"},
    "ccv17_eco": {"name": "Cali Cómo Vamos, ICV 2017 (datos 2016), Actividad económica (DANE GEIH)",
                  "url": _CCV + "59a083086ab84488bbfbe5c2098411c2.pdf"},
    "ccv16_mov": {"name": "Cali Cómo Vamos, ICV 2016 (datos 2015), Movilidad (Secretaría de Movilidad)",
                  "url": _CCV + "e533c44e14fa4be09c82461908419abf.pdf"},
    "ccv13_sal": {"name": "Cali Cómo Vamos, ICV 2013 (datos 2012), Salud (Secretaría de Salud Pública, cifras preliminares)",
                  "url": _CCV + "b97ba64cbf5740f493d82460a2e0cac4.pdf"},
    "ccv13_mov": {"name": "Cali Cómo Vamos, ICV 2013 (datos 2012), Movilidad (Metro Cali, Secretaría de Tránsito)",
                  "url": _CCV + "6e6346bb542e4a8293756ac1f1088724.pdf"},
    "ccv11_mov": {"name": "Cali Cómo Vamos, ICV 2011 (datos 2010), Movilidad (Secretaría de Tránsito, Metro Cali)",
                  "url": _CCV + "90dbdd446d1344f387fc3486fd4424e3.pdf"},
    "dane_icer09": {"name": "DANE, Informe de Coyuntura Económica Regional Valle del Cauca 2009",
                    "url": "https://www.dane.gov.co/files/icer/2009/valle_icer_II_sem_09.pdf"},
    "dane_icer11": {"name": "DANE, Informe de Coyuntura Económica Regional Valle del Cauca 2011",
                    "url": "https://www.dane.gov.co/files/icer/2011/valledelcauca_icer__11.pdf"},
    "dane_pm20_cali": {"name": "DANE, Pobreza monetaria 2020, resultados Cali (serie empalmada 2012-2020)",
                       "url": "https://www.dane.gov.co/files/investigaciones/planes-departamentos-ciudades/210504-Pobreza-monetaria-2020-Cali.pdf"},
    "dane_pm24": {"name": "DANE, Pobreza monetaria 2024, presentación de resultados (23 ciudades)",
                  "url": "https://www.dane.gov.co/files/operaciones/PM/pres-PM-2024.pdf"},
    "elpais_pm25": {"name": "El País Cali, \"Más de 80.000 personas dejaron de vivir en la pobreza monetaria durante 2025 en Cali\" (cifras DANE)",
                    "url": "https://www.elpais.com.co/economia/mas-de-80000-personas-dejaron-de-vivir-en-la-pobreza-monetaria-durante-2025-en-cali-1203.html"},
    "elpais_des20": {"name": "El País Cali, \"Así estuvo el desempleo en Cali durante el 2020\" (cifras DANE)",
                     "url": "https://www.elpais.com.co/economia/asi-estuvo-el-desempleo-en-cali-durante-el-2020.html"},
    "dane_etup17": {"name": "DANE, Encuesta de Transporte Urbano de Pasajeros, boletín IV trimestre 2017",
                    "url": "https://www.dane.gov.co/files/investigaciones/boletines/transporte/bol_transp_IVtrim17.pdf"},
    "dane_etup19": {"name": "DANE, Encuesta de Transporte Urbano de Pasajeros, boletín IV trimestre 2019",
                    "url": "https://www.dane.gov.co/files/investigaciones/boletines/transporte/bol_transp_IVtrim19.pdf"},
    "elpais_paro21": {"name": "El País Cali, \"Cali ha perdido $2,5 billones por paro y bloqueos\" (Cámara de Comercio de Cali)",
                      "url": "https://www.elpais.com.co/economia/cali-ha-perdido-2-5-billones-por-paro-y-bloqueos-lea-el-balance-de-la-camara-de-comercio.html"},
    "alcaldia_cop16": {"name": "Alcaldía de Cali, \"Un total de 66 millones de dólares inyectó a la economía de Cali la COP16\"",
                       "url": "https://www.cali.gov.co/desarrolloeconomico/publicaciones/183606/un-total-de-66-millones-de-dolares-inyecto-a-la-economia-de-cali-la-cop16/"},
    "bid_desepaz": {"name": "BID, \"Programa Desarrollo, Seguridad y Paz, DESEPAZ de la ciudad de Cali\"",
                    "url": "https://publications.iadb.org/publications/spanish/document/Programa_Desarrollo_seguridad_y_paz_DESEPAZ_de_la_ciudad_de_Cali.pdf"},
    "pmc_homicidios": {"name": "Homicide Epidemic in Cali, Colombia: A Surveillance System Data Analysis, 1993-2018 (PMC)",
                       "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC8493160/"},
    "eltiempo_motos": {"name": "El Tiempo, \"Tres de cada cinco muertos en accidentes viales son motociclistas y dos de cada cinco, peatones en Cali\"",
                       "url": "https://www.eltiempo.com/amp/colombia/cali/tres-de-cada-cinco-muertos-en-accidentes-viales-son-motociclistas-y-dos-de-cada-cinco-peatones-en-cali-en-un-ano-mas-de-un-millon-de-comparendos-3524475"},
    "caliescribe_megaobras": {"name": "Caliescribe (editorial de opinión), \"21 Megaobras, valorización Cali, todo un fraude\"",
                              "url": "https://historico.caliescribe.com/21-megaobras-valorizacion-cali-todo-un-fraude"},
}

DOMAINS = [
    {"id": "economico", "label": "Económico"},
    {"id": "social", "label": "Social"},
    {"id": "seguridad", "label": "Seguridad"},
    {"id": "salud", "label": "Salud"},
    {"id": "transporte", "label": "Transporte"},
]


def _s(src: str, **values: float) -> list[dict]:
    """Tramo de serie de una misma fuente: _s("ccv25_seg", y2007=70.5, y2008=67.7, y2009=82.8)."""
    return [{"year": int(k[1:]), "value": v, "source": src} for k, v in values.items()]


# better: "lower" (menos es mejor), "higher" (más es mejor) o None (contexto, sin juicio).
INDICATORS = [
    # ------------------------------------------------------------------ económico
    {
        "id": "desempleo", "domain": "economico", "label": "Tasa de desempleo", "unit": "%",
        "better": "lower", "decimals": 1, "headline": True,
        "points": (_s("dane_icer09", y2008=12.0, y2009=13.6)
                   + _s("dane_icer11", y2010=13.7)
                   + _s("ccv17_eco", y2011=15.2, y2012=14.4)
                   + _s("ccv20_eco", y2013=14.4, y2014=13.1, y2015=11.7, y2016=10.8, y2017=11.8, y2018=11.5, y2019=12.5)
                   + _s("elpais_des20", y2020=20.4)
                   + _s("ccv26_lab", y2021=14.6, y2022=11.5, y2023=11.0, y2024=11.0, y2025=8.8)),
        "notes": "Cali AM (Cali-Yumbo), promedio anual DANE GEIH. Desde 2021 la GEIH usa el marco "
                 "muestral del censo 2018: la comparación con años anteriores es orientativa.",
    },
    {
        "id": "informalidad", "domain": "economico", "label": "Informalidad laboral", "unit": "%",
        "better": "lower", "decimals": 1,
        "points": (_s("ccv19_eco", y2012=51.4)
                   + _s("ccv20_eco", y2013=49.9, y2014=47.9, y2015=47.4, y2016=48.7, y2017=47.4, y2018=46.2, y2019=45.7)
                   + _s("ccv26_lab", y2021=48.9, y2022=47.2, y2023=47.6, y2024=47.7, y2025=46.5)),
        "notes": "Proporción de ocupados informales, Cali AM (DANE GEIH). 2020 no publicado en las fuentes consultadas.",
    },
    {
        "id": "crecimiento", "domain": "economico", "label": "Crecimiento económico (IMAE)", "unit": "%",
        "better": "higher", "decimals": 1,
        "points": _s("ccv24_eco", y2019=3.1, y2020=-2.6, y2021=5.1, y2022=7.5, y2023=1.6),
        "notes": "Indicador Mensual de Actividad Económica de Cali (Universidad Javeriana y Banco de la "
                 "República), variación anual. No hay PIB municipal oficial anual comparable antes de 2019.",
    },
    {
        "id": "empresas", "domain": "economico", "label": "Empresas registradas", "unit": "empresas",
        "better": "higher", "decimals": 0,
        "points": _s("ccv24_eco", y2020=88335, y2021=94588, y2022=100573, y2023=103488),
        "notes": "Registro mercantil de la Cámara de Comercio de Cali (total de empresas).",
    },
    # ------------------------------------------------------------------ social
    {
        "id": "pobreza", "domain": "social", "label": "Pobreza monetaria", "unit": "%",
        "better": "lower", "decimals": 1, "headline": True,
        "points": (_s("dane_pm20_cali", y2012=30.5, y2013=28.7, y2014=26.1, y2015=23.6, y2016=22.3,
                      y2017=22.2, y2018=21.6, y2019=21.9, y2020=36.3)
                   + _s("ccv24_eco", y2021=32.5)
                   + _s("dane_pm24", y2022=23.7, y2023=24.3, y2024=23.6)
                   + _s("elpais_pm25", y2025=19.7)),
        "notes": "Cali AM, metodología DANE actualizada en 2020 (serie empalmada desde 2012). Para 2008-2011 "
                 "solo existe la serie anterior (MESEP), no comparable: 25,1% en 2011 (Cali Cómo Vamos, ICV "
                 "2019). 2021 es la cifra revisada que publica Cali Cómo Vamos; la publicación original de "
                 "DANE para ese año fue 29,3%.",
    },
    {
        "id": "pobreza_extrema", "domain": "social", "label": "Pobreza monetaria extrema", "unit": "%",
        "better": "lower", "decimals": 1,
        "points": (_s("dane_pm20_cali", y2019=4.7, y2020=13.3)
                   + _s("ccv24_eco", y2021=10.6)
                   + _s("dane_pm24", y2022=6.6, y2023=7.2, y2024=7.8)
                   + _s("elpais_pm25", y2025=6.0)),
        "notes": "Cali AM, metodología DANE 2020. Antes de 2019 las cifras publicadas usan la metodología "
                 "anterior y no se incluyen para no mezclar series.",
    },
    {
        "id": "vif", "domain": "social", "label": "Violencia intrafamiliar (casos)", "unit": "casos",
        "better": "lower", "decimals": 0,
        "points": _s("ccv26_conv", y2018=3135, y2019=3250, y2020=1633, y2021=1803, y2022=2346, y2023=3349,
                     y2024=2683, y2025=2451),
        "notes": "Casos valorados por Medicina Legal. La caída de 2020 coincide con el confinamiento: "
                 "refleja menos denuncias, no necesariamente menos violencia.",
    },
    {
        "id": "embarazo_adolescente", "domain": "social", "label": "Fecundidad adolescente (15 a 19 años)",
        "unit": "por mil", "better": "lower", "decimals": 1,
        "points": _s("ccv25_sal", y2020=32.0, y2021=28.2, y2022=24.1, y2023=20.9, y2024=18.4),
        "notes": "Nacimientos por cada 1.000 mujeres de 15 a 19 años (DANE Estadísticas Vitales).",
    },
    # ------------------------------------------------------------------ seguridad
    {
        "id": "homicidios_tasa", "domain": "seguridad", "label": "Tasa de homicidios", "unit": "por 100 mil hab.",
        "better": "lower", "decimals": 1, "headline": True,
        "points": (_s("ccv25_seg", y2007=70.5, y2008=67.7, y2009=82.8, y2010=84.7, y2011=84.4, y2012=84.5, y2013=89.4,
                      y2014=70.9, y2015=61.9, y2016=58.3, y2017=56.2, y2018=51.8, y2019=49.7, y2020=47.2,
                      y2021=53.7, y2022=43.3, y2023=44.4, y2024=41.1)
                   + _s("ccv26_seg", y2025=46.5)),
        "notes": "Comité Interinstitucional de Muertes por Causa Externa (CIMCE), Observatorio de Seguridad "
                 "de Cali. Las tasas dependen de la proyección de población vigente en cada edición.",
    },
    {
        "id": "homicidios", "domain": "seguridad", "label": "Homicidios (número)", "unit": "casos",
        "better": "lower", "decimals": 0,
        "points": (_s("ccv25_seg", y2007=1490, y2008=1440, y2009=1768, y2010=1818, y2011=1820, y2012=1830, y2013=1942,
                      y2014=1545, y2015=1353, y2016=1280, y2017=1239, y2018=1154, y2019=1114, y2020=1069,
                      y2021=1220, y2022=986, y2023=1013, y2024=938)
                   + _s("ccv26_seg", y2025=1060)),
        "notes": "En 2025, 471 de los 1.060 homicidios (44,4%) fueron de jóvenes de 14 a 28 años (CCV 2026).",
    },
    {
        "id": "hurto_personas", "domain": "seguridad", "label": "Hurto a personas (denuncias)", "unit": "denuncias",
        "better": "lower", "decimals": 0,
        "points": _s("ccv25_seg", y2007=6061, y2008=6813, y2009=6579, y2010=7437, y2011=7501, y2012=9294, y2013=9104,
                     y2014=8614, y2015=10280, y2016=13715, y2017=15752, y2018=19986, y2019=12961,
                     y2020=18163, y2021=23329, y2022=24426, y2023=23271, y2024=21992),
        "notes": "Denuncias ante la Policía Nacional. Parte del aumento desde 2017 obedece a la denuncia "
                 "virtual (más facilidad para denunciar), no solo a más delitos.",
    },
    {
        "id": "extorsion", "domain": "seguridad", "label": "Extorsión (denuncias)", "unit": "denuncias",
        "better": "lower", "decimals": 0,
        "points": _s("ccv25_seg", y2007=51, y2008=84, y2009=54, y2010=85, y2012=86, y2013=185, y2014=225, y2015=281,
                     y2016=155, y2017=299, y2018=304, y2019=508, y2020=595, y2021=567, y2022=351,
                     y2023=468, y2024=473),
        "notes": "Denuncias ante la Policía Nacional. El dato de 2011 publicado es atípico frente a los años "
                 "vecinos y se omite hasta confirmarlo con la fuente primaria.",
    },
    {
        "id": "feminicidios", "domain": "seguridad", "label": "Feminicidios", "unit": "casos",
        "better": "lower", "decimals": 0,
        "points": (_s("ccv25_seg", y2015=17, y2016=16, y2017=16, y2018=23, y2019=12, y2020=19, y2021=10,
                      y2022=7, y2023=10, y2024=11)
                   + _s("ccv26_seg", y2025=5)),
        "notes": "CIMCE, Observatorio de Seguridad de Cali. 2025 es el menor número en once años.",
    },
    # ------------------------------------------------------------------ salud
    {
        "id": "mortalidad_infantil", "domain": "salud", "label": "Mortalidad infantil", "unit": "por mil nacidos vivos",
        "better": "lower", "decimals": 1, "headline": True,
        "points": (_s("ccv13_sal", y2008=10.3, y2011=9.3)
                   + _s("ccv20_sal", y2012=10.1, y2013=8.9, y2014=8.1, y2015=8.1, y2016=8.6, y2017=9.3,
                        y2018=8.6, y2019=8.1)
                   + _s("ccv25_sal", y2020=7.9, y2021=9.1, y2022=9.8, y2023=9.2, y2024=9.6)),
        "notes": "Menores de 1 año. 2008 y 2011 son cifras preliminares de la Secretaría de Salud; desde 2020, "
                 "DANE Estadísticas Vitales (definitivas).",
    },
    {
        "id": "mortalidad_menores5", "domain": "salud", "label": "Mortalidad en menores de 5 años",
        "unit": "por mil nacidos vivos", "better": "lower", "decimals": 1,
        "points": (_s("ccv13_sal", y2008=14.9, y2009=12.4, y2010=12.9, y2011=11.6)
                   + _s("ccv20_sal", y2012=12.2, y2013=10.5, y2014=9.6, y2015=10.3, y2016=9.5, y2017=10.2,
                        y2018=10.0, y2019=9.9)
                   + _s("ccv25_sal", y2020=9.7, y2021=10.9, y2022=10.9, y2023=10.6, y2024=10.9)),
        "notes": "2008-2011: Secretaría de Salud (preliminar). 2012-2019: Secretaría de Salud. Desde 2020: DANE.",
    },
    {
        "id": "mortalidad_materna", "domain": "salud", "label": "Mortalidad materna", "unit": "por 100 mil nacidos vivos",
        "better": "lower", "decimals": 1,
        "points": (_s("ccv20_sal", y2012=51.5, y2013=14.5, y2014=29.0, y2015=32.7, y2016=32.9, y2017=26.5,
                      y2018=12.0, y2019=21.0)
                   + _s("ccv21_sal", y2020=46.0)),
        "notes": "Con 25.000 a 30.000 nacimientos al año, cada muerte materna mueve la razón unos 3 a 4 "
                 "puntos: la serie es volátil y se lee en tendencia, no año a año. No se encontró cifra "
                 "oficial consolidada 2021-2025 en las fuentes consultadas.",
    },
    {
        "id": "desnutricion", "domain": "salud", "label": "Desnutrición aguda en menores de 5 años", "unit": "%",
        "better": "lower", "decimals": 2,
        "points": _s("ccv25_sal", y2020=0.21, y2021=0.26, y2022=0.32, y2023=0.35, y2024=0.41),
        "notes": "Prevalencia notificada (Secretaría de Salud Pública). Se duplicó entre 2020 y 2024.",
    },
    {
        "id": "contributivo", "domain": "salud", "label": "Afiliación al régimen contributivo", "unit": "% de afiliados",
        "better": "higher", "decimals": 1,
        "points": (_s("ccv20_sal", y2017=68.8, y2018=68.9, y2019=68.7)
                   + _s("ccv25_sal", y2020=67.0, y2021=67.2, y2022=63.6, y2023=62.4, y2024=60.8)),
        "notes": "Proporción de afiliados en régimen contributivo (MinSalud). Su caída refleja menos empleo "
                 "formal cotizante y el traslado al subsidiado (37,7% en 2024).",
    },
    # ------------------------------------------------------------------ transporte
    {
        "id": "pasajeros_mio", "domain": "transporte", "label": "Pasajeros del MIO", "unit": "millones al año",
        "better": "higher", "decimals": 1, "headline": True,
        "points": (_s("ccv11_mov", y2010=68.1)
                   + _s("ccv13_mov", y2011=97.3, y2012=130.6)
                   + _s("dane_etup17", y2016=143.4, y2017=144.6)
                   + _s("dane_etup19", y2018=141.2, y2019=135.1)
                   + _s("ccv26_mov", y2020=66.7, y2021=49.0, y2022=78.1, y2023=79.1, y2024=87.8, y2025=89.3)),
        "notes": "El MIO empezó a operar en marzo de 2009 (25,3 millones de pasajeros ese año incompleto). "
                 "2013-2015 no tienen total anual publicado en las fuentes consultadas (el promedio por día "
                 "hábil fue 471.361 en 2014 y 482.344 en 2015).",
    },
    {
        "id": "muertes_viales", "domain": "transporte", "label": "Muertes en siniestros viales", "unit": "personas",
        "better": "lower", "decimals": 0, "headline": True,
        "points": (_s("ccv11_mov", y2007=357, y2008=328, y2009=345, y2010=305)
                   + _s("ccv13_mov", y2011=250, y2012=272)
                   + _s("ccv16_mov", y2014=267, y2015=316)
                   + _s("ccv19_mov", y2017=322, y2018=334)
                   + _s("ccv21_mov", y2019=309, y2020=300)
                   + _s("ccv26_mov", y2021=294, y2022=327, y2023=307, y2024=320, y2025=326)),
        "notes": "Secretaría de Movilidad. 2013 y 2016 sin dato en las fuentes consultadas. En 2025 la tasa fue "
                 "14,3 por cada 100 mil habitantes; tres de cada cinco víctimas son motociclistas.",
    },
]

EVENTS = [
    {"year": 2009, "domain": "transporte", "title": "Arranca el MIO",
     "detail": "El sistema de transporte masivo inicia operación en marzo; 25,3 millones de pasajeros ese año.",
     "source": "ccv11_mov"},
    {"year": 2009, "domain": "economico", "title": "Plan de 21 Megaobras por valorización",
     "detail": "Acuerdo 241 de 2008; varias obras quedaron sin terminar años después. La fuente es un "
               "editorial de opinión, no un hallazgo verificado de forma independiente.",
     "source": "caliescribe_megaobras"},
    {"year": 2013, "domain": "seguridad", "title": "Pico de homicidios: 1.942 casos",
     "detail": "Tasa de 89,4 por 100 mil, la más alta del período analizado.", "source": "ccv25_seg"},
    {"year": 2014, "domain": "seguridad", "title": "DESEPAZ y enfoque epidemiológico",
     "detail": "Vigilancia de muertes violentas, restricciones focalizadas y prevención social: los "
               "homicidios bajan 30% entre 2013 y 2015.", "source": "bid_desepaz"},
    {"year": 2020, "domain": "salud", "title": "Pandemia de covid-19",
     "detail": "2.614 muertes por covid-19 en Cali en 2020; el desempleo sube a 20,4%.", "source": "ccv21_sal"},
    {"year": 2021, "domain": "social", "title": "Paro nacional, epicentro en Cali",
     "detail": "La Cámara de Comercio estimó pérdidas por $2,5 billones; los homicidios suben a 1.220.",
     "source": "elpais_paro21"},
    {"year": 2024, "domain": "economico", "title": "COP16 en Cali",
     "detail": "La Alcaldía reporta US$66 millones inyectados a la economía local.", "source": "alcaldia_cop16"},
    {"year": 2025, "domain": "economico", "title": "Desempleo de un dígito por primera vez",
     "detail": "8,8% anual en Cali-Yumbo, 2,2 puntos menos que en 2024.", "source": "ccv26_lab"},
    {"year": 2025, "domain": "seguridad", "title": "Repunte de homicidios (+13%)",
     "detail": "1.060 homicidios; 44% de las víctimas tenían entre 14 y 28 años. Entre el 1 y el 24 de enero "
               "de 2026 se registraron 93.", "source": "ccv26_seg"},
]

# ---------------------------------------------------------------------------------------------
# Conclusiones y estrategias. Redactadas a partir de las cifras de arriba (cada una cita los
# indicadores que la sustentan en `evidence`); el test valida que esos ids existan.

CONCLUSIONS = [
    {"domain": "seguridad", "evidence": ["homicidios_tasa", "homicidios", "hurto_personas"],
     "text": "El mayor logro estructural de la ciudad en 17 años: la tasa de homicidios cayó de 89,4 (2013) "
             "a 41,1 (2024), la más baja del período. Pero el avance no es irreversible: 2021 (paro) y 2025 "
             "(+13%) muestran repuntes, y casi la mitad de las víctimas son jóvenes de 14 a 28 años. El hurto "
             "a personas se triplicó en denuncias desde 2008."},
    {"domain": "economico", "evidence": ["desempleo", "informalidad"],
     "text": "El desempleo pasó de su pico de 20,4% (2020) a 8,8% en 2025, el nivel más bajo de la serie. "
             "La informalidad, en cambio, lleva una década estancada entre 46% y 49%: se crea empleo, pero no "
             "empleo formal."},
    {"domain": "social", "evidence": ["pobreza", "pobreza_extrema"],
     "text": "La pobreza monetaria bajó de 30,5% (2012) a 21,6% (2018), saltó a 36,3% con la pandemia y en "
             "2025 llegó a 19,7%, su mínimo. La pobreza extrema tardó más en recuperarse: en 2024 (7,8%) "
             "seguía por encima de 2019 (4,7%)."},
    {"domain": "salud", "evidence": ["mortalidad_infantil", "desnutricion", "contributivo"],
     "text": "La salud es el frente con menos progreso: la mortalidad infantil lleva 17 años entre 8 y 10 por "
             "mil y en 2022-2024 estuvo peor que en 2019-2020; la desnutrición aguda infantil se duplicó "
             "entre 2020 y 2024, y el régimen contributivo perdió 8 puntos desde 2018."},
    {"domain": "transporte", "evidence": ["pasajeros_mio", "muertes_viales"],
     "text": "El MIO nunca se recuperó: de 144,6 millones de pasajeros (2017) a 89,3 millones (2025), un 38% "
             "menos. Las muertes viales siguen entre 300 y 330 por año, igual que en 2008: 17 años sin "
             "mejora sostenida."},
]

STRATEGIES = [
    {"title": "Juventud segura: prevenir el homicidio donde se concentra",
     "evidence": ["homicidios", "homicidios_tasa", "desempleo"],
     "why": "44% de los homicidios de 2025 fueron de jóvenes de 14 a 28 años, y el enfoque epidemiológico "
            "(DESEPAZ) ya demostró en Cali que la violencia se puede bajar con datos y focalización.",
     "actions": [
         "Debate de control político en el Concejo con los datos del Observatorio de Seguridad por comuna y edad.",
         "Proyecto de acuerdo para un tablero público mensual de homicidios y hurtos por comuna (datos abiertos).",
         "Propuesta de programa: primer empleo y formación para jóvenes en las 5 comunas con más homicidios juveniles.",
     ],
     "viability": "Alta: el control político y los proyectos de acuerdo están dentro de las facultades de un "
                  "concejal; el tablero reutiliza datos que la Alcaldía ya produce.",
     "measure": "Homicidios de jóvenes 14 a 28 (base 2025: 471)."},
    {"title": "Rescate del MIO con metas públicas",
     "evidence": ["pasajeros_mio"],
     "why": "El sistema perdió 38% de sus pasajeros frente a 2017; es el principal problema de movilidad "
            "heredado por cuatro administraciones.",
     "actions": [
         "Seguimiento trimestral a Metrocali en el Concejo: pasajeros, flota en circulación y finanzas.",
         "Propuesta con meta verificable: volver a 110 millones de pasajeros anuales en 2029.",
         "Encuesta propia de usuarios en redes de Carlos para recoger quejas por ruta (insumo, no sustituto de datos oficiales).",
     ],
     "viability": "Media: la operación depende de la Alcaldía y Metrocali; el aporte del concejal es vigilancia, "
                  "propuesta y presión pública con cifras.",
     "measure": "Pasajeros anuales del MIO (base 2025: 89,3 millones)."},
    {"title": "Visión Cero: bajar las muertes viales",
     "evidence": ["muertes_viales"],
     "why": "326 muertes en 2025, el mismo nivel que en 2008; tres de cada cinco son motociclistas y dos de "
            "cada cinco, peatones.",
     "actions": [
         "Proyecto de acuerdo de política Visión Cero con meta de reducción de 30% en cuatro años.",
         "Priorizar los 20 puntos con más muertes (datos de la Secretaría de Movilidad) para intervenciones de bajo costo: cruces seguros, reductores, gestión de velocidad.",
         "Campaña de seguridad para motociclistas con gremios y plataformas de domicilios.",
     ],
     "viability": "Alta: es política pública de bajo costo, con evidencia internacional y datos locales disponibles.",
     "measure": "Muertes en siniestros viales (base 2025: 326)."},
    {"title": "Primera infancia: cero muertes evitables por desnutrición",
     "evidence": ["mortalidad_infantil", "desnutricion", "mortalidad_menores5"],
     "why": "La mortalidad infantil no mejora desde 2008 y la desnutrición aguda se duplicó en cuatro años: "
            "es un tema de personas, coherente con el enfoque de Carlos.",
     "actions": [
         "Debate de control político a la Secretaría de Salud sobre desnutrición y mortalidad infantil por comuna.",
         "Propuesta de ruta de atención integral en las comunas con más casos, con seguimiento público semestral.",
     ],
     "viability": "Alta en control político; media en ejecución (depende del presupuesto de salud del Distrito).",
     "measure": "Mortalidad infantil (base 2024: 9,6 por mil) y desnutrición aguda (base 2024: 0,41%)."},
    {"title": "Empleo formal, no solo empleo",
     "evidence": ["informalidad", "desempleo", "contributivo"],
     "why": "El desempleo está en mínimos, pero casi la mitad de los ocupados es informal y el régimen "
            "contributivo de salud se reduce: el siguiente reto es la calidad del empleo.",
     "actions": [
         "Propuesta de incentivos distritales (tarifas diferenciales, trámites simplificados) para formalizar microempresas.",
         "Alianzas con la Cámara de Comercio para capitalizar la economía de eventos (COP16) en empleo formal.",
     ],
     "viability": "Media: requiere articulación con la Alcaldía y el sector privado.",
     "measure": "Informalidad (base 2025: 46,5%)."},
    {"title": "\"Cali en cifras\": rendición de cuentas con datos",
     "evidence": ["homicidios_tasa", "pobreza", "desempleo", "pasajeros_mio", "muertes_viales"],
     "why": "Carlos es académico y no se pronuncia sin datos: publicar cada trimestre un tablero sencillo "
            "de estos indicadores lo diferencia de sus rivales y convierte su estilo en propuesta.",
     "actions": [
         "Pieza trimestral en redes: un indicador, una gráfica, una propuesta (usar las gráficas de esta pestaña).",
         "Serie de videos cortos \"lo que dicen los datos\" por frente (seguridad, salud, MIO, empleo).",
     ],
     "viability": "Muy alta: costo casi nulo; los datos ya están consolidados en este monitor.",
     "measure": "Alcance típico (mediana) por publicación de Carlos en la pestaña Meta y redes."},
]

METHODOLOGY = [
    "Cada alcaldía se evalúa desde el último dato del año anterior a su posesión (la situación que recibió) "
    "hasta el último dato disponible de su período (la que entregó). Si falta alguno de los dos, se usa el "
    "dato más cercano dentro del período y se indica.",
    "Los años sin dato verificable se dejan vacíos: no se interpola ni se estima.",
    "Varios indicadores cambiaron de metodología (pobreza en 2020, GEIH en 2021, proyecciones de población "
    "del censo 2018): las notas de cada indicador lo señalan.",
    "Los cambios reflejan el contexto de toda la ciudad (economía nacional, pandemia, paro), no solo la gestión "
    "del alcalde de turno.",
]


# ---------------------------------------------------------------------------------------------

def period_of(year: int) -> dict | None:
    return next((p for p in PERIODS if p["start"] <= year <= p["end"]), None)


def series(indicator: dict) -> dict[int, float]:
    return {p["year"]: p["value"] for p in indicator["points"]}


STABLE_PCT = 2.0  # cambios menores a ±2% se leen como "estable": no son una señal real


def _verdict(indicator: dict, delta: float | None, pct: float | None = None) -> str | None:
    if delta is None or indicator.get("better") is None:
        return None
    if abs(delta) < 1e-9 or (pct is not None and abs(pct) < STABLE_PCT):
        return "estable"
    improved = delta < 0 if indicator["better"] == "lower" else delta > 0
    return "mejoró" if improved else "empeoró"


def period_stats(indicator: dict) -> list[dict]:
    """Por alcaldía: valor recibido (año anterior a la posesión), valor entregado (último año del
    período con dato), cambio absoluto y relativo, promedio del período y veredicto."""
    data = series(indicator)
    out = []
    for p in PERIODS:
        years_in = sorted(y for y in data if p["start"] <= y <= min(p["end"], CURRENT_YEAR))
        start_year = p["start"] - 1 if (p["start"] - 1) in data else (years_in[0] if years_in else None)
        end_year = years_in[-1] if years_in else None
        start = data.get(start_year) if start_year is not None else None
        end = data.get(end_year) if end_year is not None else None
        delta = (end - start) if (start is not None and end is not None and end_year != start_year) else None
        pct = round(delta / start * 100, 1) if (delta is not None and start) else None
        avg = round(sum(data[y] for y in years_in) / len(years_in), indicator["decimals"] + 1) if years_in else None
        last_expected = min(p["end"], max(data)) if data else p["end"]
        # "parcial": no se mide todo el período (falta el dato heredado o el de cierre); el
        # veredicto sigue siendo real pero sobre una ventana más corta que la alcaldía.
        partial = not (start_year == p["start"] - 1 and end_year == last_expected)
        out.append({
            "period": p["id"], "label": p["label"], "start_year": start_year, "start": start,
            "end_year": end_year, "end": end, "delta": round(delta, 2) if delta is not None else None,
            "pct": pct, "avg": avg, "years_with_data": len(years_in),
            "start_is_inherited": start_year == p["start"] - 1, "partial": partial,
            "verdict": _verdict(indicator, delta, pct),
        })
    return out


def overall_change(indicator: dict) -> dict:
    """Primer dato disponible contra el último: la foto completa de 2008 (o el primer año con dato) al presente."""
    data = series(indicator)
    first, last = min(data), max(data)
    delta = data[last] - data[first]
    return {"first_year": first, "first": data[first], "last_year": last, "last": data[last],
            "delta": round(delta, 2), "pct": round(delta / data[first] * 100, 1) if data[first] else None,
            "verdict": _verdict(indicator, delta, round(delta / data[first] * 100, 1) if data[first] else None),
            "best_year": (min if indicator.get("better") == "lower" else max)(data, key=data.get)
            if indicator.get("better") else None}


def scorecard() -> list[dict]:
    """Matriz indicador x alcaldía con el veredicto (mejoró/empeoró) para la vista comparativa."""
    rows = []
    for ind in INDICATORS:
        if ind.get("better") is None:
            continue
        rows.append({"id": ind["id"], "label": ind["label"], "domain": ind["domain"],
                     "cells": [{"period": s["period"], "verdict": s["verdict"], "pct": s["pct"], "partial": s["partial"]}
                               for s in period_stats(ind)]})
    return rows


def period_balance() -> list[dict]:
    """Cuántos indicadores mejoraron, empeoraron o quedaron estables en cada alcaldía. Solo cuenta
    los que se pueden medir en el período completo (dato heredado y dato de cierre): una ventana
    parcial no es comparable entre alcaldías."""
    out = []
    for p in PERIODS:
        counts = {"mejoró": 0, "empeoró": 0, "estable": 0}
        for ind in INDICATORS:
            s = next(x for x in period_stats(ind) if x["period"] == p["id"])
            if s["verdict"] in counts and not s["partial"]:
                counts[s["verdict"]] += 1
        out.append({"period": p["id"], "label": p["label"], "improved": counts["mejoró"],
                    "worsened": counts["empeoró"], "stable": counts["estable"]})
    return out


def payload() -> dict:
    """Todo lo que necesita la pestaña Histórico, listo para JSON."""
    indicators = []
    for ind in INDICATORS:
        indicators.append({
            **{k: v for k, v in ind.items() if k != "points"},
            "points": sorted(ind["points"], key=lambda x: x["year"]),
            "sources": [{"key": k, **SOURCES[k]} for k in dict.fromkeys(pt["source"] for pt in ind["points"])],
            "periods": period_stats(ind),
            "overall": overall_change(ind),
        })
    return {
        "years": [2008, CURRENT_YEAR], "domains": DOMAINS, "periods": PERIODS,
        "indicators": indicators, "scorecard": scorecard(), "balance": period_balance(),
        "events": [{**e, "source": {"key": e["source"], **SOURCES[e["source"]]}} for e in EVENTS],
        "conclusions": CONCLUSIONS, "strategies": STRATEGIES, "methodology": METHODOLOGY,
    }
