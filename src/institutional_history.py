"""Histórico institucional: qué se hizo (o no) en las últimas 4 alcaldías de Cali, y la deuda
pública asociada. Pedido explícito del cliente 2026-09-26: "reconocer e investigar a profundidad
qué proyectos se llevaron a cabo, cuáles se finalizaron, cuáles no y cuál es la deuda debido a
esto", con "investigación exhaustiva... aunque tome varias horas".

Esto es investigación documental real (prensa, fuentes oficiales, un paper académico), NO datos
derivados del scraping de menciones -- por la regla "nada simulado" del proyecto, cada afirmación
lleva su fuente. Donde la fuente es un editorial de opinión (Caliescribe) en vez de una nota
neutral, se marca explícitamente -- son señalamientos de esa publicación, no hechos verificados
de forma independiente por este proyecto.

Cobertura actual: hechos y cifras más documentados por administración, priorizando los que tienen
fuente verificable. No es exhaustivo proyecto por proyecto -- es una base real ampliable con más
horas de investigación si se necesita más profundidad.

    python -m pytest tests/test_institutional_history.py   # valida que cada entrada tenga fuente
"""

ADMINISTRATIONS = [
    {
        "mayor": "Jorge Iván Ospina Hernández",
        "period": "2008-2011",
        "party": "Movimiento independiente (con apoyo del Polo Democrático y otros sectores)",
        "status": "completado",
        "summary": (
            "Primera alcaldía de Ospina. Arranca el MIO (marzo de 2009) y se aprueba el plan de 21 "
            "Megaobras financiado por valorización. En seguridad, los homicidios subieron de 1.490 "
            "(2007) a 1.820 (2011), y la tasa pasó de 70,5 a 84,4 por 100 mil habitantes."
        ),
        "debt": None,  # no se encontró una cifra de deuda verificable para este período
        "metrics": [
            {
                "label": "Tasa de homicidios (por 100.000 hab.)",
                "start": 70.5, "start_year": 2007, "end": 84.4, "end_year": 2011, "change_pct": 20,
                "note": "De 1.490 homicidios en 2007 a 1.820 en 2011 (CIMCE, Observatorio de Seguridad de Cali).",
                "source": {"name": "Cali Cómo Vamos, ICV 2025, Seguridad (serie 2005-2024)",
                          "url": "https://www.calicomovamos.org.co/_files/ugd/ba6905_58e6f0efd57f429fafa22eaf837e7b3c.pdf"},
            },
        ],
        "projects": [
            {"name": "Inicio de operación del MIO", "category": "movilidad y transporte", "status": "completado",
             "description": "El sistema de transporte masivo empezó a operar en marzo de 2009 (25,3 millones de "
                            "pasajeros ese año; 97,3 millones en 2011). La cobertura prevista originalmente "
                            "nunca se completó en las administraciones siguientes.",
             "source": {"name": "Cali Cómo Vamos, ICV 2011, Movilidad (Metro Cali)",
                       "url": "https://www.calicomovamos.org.co/_files/ugd/ba6905_90dbdd446d1344f387fc3486fd4424e3.pdf"}},
            {"name": "Plan 21 Megaobras por valorización (Acuerdo 241 de 2008)", "category": "infraestructura y obras",
             "status": "incompleto",
             "description": "Plan de 21 obras viales financiado con cobro de valorización. Años después seguían "
                            "obras sin terminar; el editorial citado lo califica con dureza, lo que debe leerse "
                            "como postura de un medio de opinión.",
             "source": {"name": "Caliescribe (Editorial), \"21 Megaobras, valorización Cali, todo un fraude\"",
                       "url": "https://historico.caliescribe.com/21-megaobras-valorizacion-cali-todo-un-fraude"}},
        ],
    },
    {
        "mayor": "Rodrigo Guerrero Velasco",
        "period": "2012-2015",
        "party": "Partido Liberal (coalición)",
        "status": "completado",
        "summary": (
            "Alcaldía centrada en seguridad: aplicó el modelo DESEPAZ (enfoque epidemiológico/de "
            "salud pública contra la violencia) que ya había estrenado en su primer paso por la "
            "alcaldía (1992-1994). Cali pasó de la tasa de homicidios más alta del país a su nivel "
            "más bajo en 20 años durante su gestión."
        ),
        "debt": None,  # no se encontró una cifra específica y verificable de deuda para este período
        "metrics": [
            {
                "label": "Tasa de homicidios (por 100.000 hab.)",
                "start": 84.4, "start_year": 2011, "end": 61.9, "end_year": 2015,
                "change_pct": -27,
                "note": "De 1.820 homicidios en 2011 a 1.353 en 2015; el pico fue 2013 (1.942). Cifras CIMCE "
                        "(Observatorio de Seguridad de Cali), consolidadas por Cali Cómo Vamos.",
                "source": {"name": "Cali Cómo Vamos, ICV 2025, Seguridad (serie 2005-2024)",
                          "url": "https://www.calicomovamos.org.co/_files/ugd/ba6905_58e6f0efd57f429fafa22eaf837e7b3c.pdf"},
            },
        ],
        "projects": [
            {"name": "DESEPAZ (Desarrollo, Seguridad y Paz)", "category": "seguridad", "status": "completado",
             "description": "Programa de prevención de violencia con enfoque epidemiológico (vigilancia de "
                            "muertes violentas, restricción de horarios de venta de alcohol y porte de armas, "
                            "intervención social focalizada). Reconocido internacionalmente como caso de estudio.",
             "source": {"name": "BID, \"Programa Desarrollo, Seguridad y Paz, DESEPAZ de la ciudad de Cali\"",
                       "url": "https://publications.iadb.org/publications/spanish/document/Programa_Desarrollo_seguridad_y_paz_DESEPAZ_de_la_ciudad_de_Cali.pdf"}},
            {"name": "Recuperación de la malla vial", "category": "infraestructura y obras", "status": "en curso",
             "description": "La administración reportó avances en la recuperación de vías, sin cifra oficial "
                            "de cobertura final verificada por esta investigación.",
             "source": {"name": "Alcaldía de Santiago de Cali (portal histórico, página retirada del sitio)",
                       "url": "https://www.cali.gov.co"}},
        ],
    },
    {
        "mayor": "Maurice Armitage Cadavid",
        "period": "2016-2019",
        "party": "Movimiento ciudadano / independiente",
        "status": "completado",
        "summary": (
            "\"Balance agridulce\" según El Tiempo: saneó las finanzas del Distrito y mantuvo la "
            "reducción de homicidios, pero dejó promesas incumplidas -- el sistema de transporte "
            "MIO, su principal apuesta de movilidad, fue calificado por veedores ciudadanos como "
            "\"empresa fallida\"."
        ),
        "debt": {
            "note": "El Tiempo reporta \"saneamiento de las finanzas\" como su principal legado económico, "
                    "sin cifra de deuda específica en la fuente consultada.",
            "source": {"name": "El Tiempo, \"¿Cómo le fue a Maurice Armitage en la Alcaldía de Cali?\"",
                      "url": "https://www.eltiempo.com/colombia/cali/como-le-fue-a-maurice-armitage-en-la-alcaldia-de-cali-444216"},
        },
        "metrics": [
            {
                "label": "Reducción de homicidios (último año de gestión vs. anterior)",
                "start": None, "start_year": 2018, "end": None, "end_year": 2019, "change_pct": -19,
                "note": "Promedio de 3,01 muertes violentas diarias en 2019 vs. 3,20 en 2018.",
                "source": {"name": "El Tiempo, \"¿Cómo le fue a Maurice Armitage en la Alcaldía de Cali?\"",
                          "url": "https://www.eltiempo.com/colombia/cali/como-le-fue-a-maurice-armitage-en-la-alcaldia-de-cali-444216"},
            },
        ],
        "projects": [
            {"name": "Saneamiento fiscal y alianzas público-privadas", "category": "corrupción y gobierno", "status": "completado",
             "description": "Cali registró la mayor creación de empleo entre las 23 principales capitales "
                            "(ago-oct 2019) y descenso de la pobreza monetaria en el período, según la Cámara "
                            "de Comercio de Cali.",
             "source": {"name": "El Tiempo (declaraciones de Esteban Piedrahita, Cámara de Comercio de Cali)",
                       "url": "https://www.eltiempo.com/colombia/cali/como-le-fue-a-maurice-armitage-en-la-alcaldia-de-cali-444216"}},
            {"name": "Inversión en educación y cultura (60% del presupuesto)", "category": "educación", "status": "completado",
             "description": "60% del presupuesto de la administración se destinó a programas de educación y cultura.",
             "source": {"name": "El Tiempo, \"¿Cómo le fue a Maurice Armitage en la Alcaldía de Cali?\"",
                       "url": "https://www.eltiempo.com/colombia/cali/como-le-fue-a-maurice-armitage-en-la-alcaldia-de-cali-444216"}},
            {"name": "Cobertura de servicios públicos (agua, energía, alcantarillado)", "category": "servicios públicos", "status": "completado",
             "description": "Más del 95% de la población con cobertura, según el programa Cali Cómo Vamos.",
             "source": {"name": "El Tiempo (datos de Cali Cómo Vamos)",
                       "url": "https://www.eltiempo.com/colombia/cali/como-le-fue-a-maurice-armitage-en-la-alcaldia-de-cali-444216"}},
            {"name": "Sistema MIO (Masivo Integrado de Occidente)", "category": "movilidad y transporte", "status": "incompleto",
             "description": "Veedores ciudadanos (Luz Betty Jiménez, Pablo Borrero) lo calificaron como \"empresa "
                            "fallida\" al cierre de la administración; aumento de hurtos también señalado como "
                            "promesa incumplida en seguridad.",
             "source": {"name": "El Tiempo, \"¿Cómo le fue a Maurice Armitage en la Alcaldía de Cali?\"",
                       "url": "https://www.eltiempo.com/colombia/cali/como-le-fue-a-maurice-armitage-en-la-alcaldia-de-cali-444216"}},
        ],
    },
    {
        "mayor": "Jorge Iván Ospina Hernández",
        "period": "2020-2023",
        "party": "Alianza Verde (coalición \"Cali, Unida por la Vida\")",
        "status": "completado",
        "summary": (
            "Gestión marcada por la pandemia de covid-19, el paro nacional de 2021 (epicentro en "
            "Cali) y un fuerte crecimiento de la deuda pública. Avanzó proyectos de espacio público "
            "y cultura, pero un editorial de Caliescribe -- que debe leerse como señalamiento de "
            "opinión, no como hallazgo judicial confirmado -- le atribuye la responsabilidad "
            "principal del salto de la deuda distrital a $3,2 billones."
        ),
        "debt": {
            "value_billones_cop": 3.2,
            "note": ("Según el editorial de Caliescribe: deuda bancaria de $1,2 billones reconocida por el "
                    "alcalde electo Eder al recibir el Distrito, que sumando el reperfilamiento (mayores "
                    "plazos) y los intereses supera los $2,2 billones de capital + más de $1 billón en "
                    "intereses = ~$3,2 billones. El editorial atribuye la responsabilidad a la administración "
                    "Ospina y al Concejo 2020-2023 que aprobó los créditos. Esta es la postura de un medio de "
                    "opinión local, no una cifra oficial verificada de forma independiente por este proyecto."),
            "source": {"name": "Caliescribe (Editorial), \"La quiebra fiscal de Cali y los concejales\"",
                      "url": "https://caliescribe.com/2023/12/16/la-quiebra-fiscal-de-cali-y-los-concejales/"},
        },
        "metrics": [],
        "projects": [
            {"name": "Parque Científico y Tecnológico San Fernando", "category": "cultura y eventos", "status": "en curso",
             "description": "Se culminó e inauguró su primera fase (planetario digital y salas interactivas); "
                            "proyecto completo no finalizado en el período.",
             "source": {"name": "Alcaldía de Santiago de Cali (vía resumen de Google)", "url": "https://www.cali.gov.co"}},
            {"name": "Bulevar del Oriente", "category": "infraestructura y obras", "status": "completado",
             "description": "Espacio público de más de un kilómetro lineal entregado en el Distrito de Aguablanca.",
             "source": {"name": "Alcaldía de Santiago de Cali (vía resumen de Google)", "url": "https://www.cali.gov.co"}},
            {"name": "Parque Pacífico", "category": "cultura y eventos", "status": "en curso",
             "description": "Avance sustancial en infraestructura física para honrar la herencia cultural del "
                            "Pacífico; no se completó en el período.",
             "source": {"name": "Alcaldía de Santiago de Cali (vía resumen de Google)", "url": "https://www.cali.gov.co"}},
            {"name": "Corazón de Pance", "category": "medio ambiente y clima", "status": "en curso",
             "description": "Adquisición de más de 90 hectáreas de terreno ambientalmente protegido en el sur "
                            "de Cali para consolidar la reserva.",
             "source": {"name": "Alcaldía de Santiago de Cali (vía resumen de Google)", "url": "https://www.cali.gov.co"}},
            {"name": "Plan 21 Megaobras (herencia 2008/2010) -- 9 de 21 sin terminar", "category": "infraestructura y obras", "status": "incompleto",
             "description": "El plan de valorización de 2008 (Acuerdo 241) para 21 megaobras viales seguía con "
                            "9 obras faltantes al cierre de esta administración, según el editorial de "
                            "Caliescribe -- que también lo describe como parte del origen de la deuda distrital.",
             "source": {"name": "Caliescribe (Editorial), \"21 Megaobras, valorización Cali, todo un fraude\"",
                       "url": "https://historico.caliescribe.com/21-megaobras-valorizacion-cali-todo-un-fraude"}},
        ],
    },
    {
        "mayor": "Alejandro Eder Garcés",
        "period": "2024-2027",
        "party": "Independiente",
        "status": "en curso",
        "summary": (
            "Administración en curso (falta poco más de un año). Llegó con alto respaldo ciudadano "
            "prometiendo orden institucional y reactivar grandes proyectos. A la fecha: liderazgo "
            "en escenarios como la COP16 y anuncio de proyectos nuevos (Tren de Cercanías, "
            "renovación del Centro Histórico), pero también alta rotación de gabinete y una deuda "
            "que un editorial de Caliescribe reporta ya cercana a $3,5 billones -- más que la "
            "heredada de Ospina."
        ),
        "debt": {
            "value_billones_cop": 3.5,
            "note": ("Según el editorial de Caliescribe de julio 2026: \"endeudamiento cercano a $3,5 "
                    "billones\" a los 2,5 años de gobierno, sin solución estructural para el MIO, la "
                    "valorización ni las Megaobras heredadas. Es la postura de un medio de opinión local, "
                    "no una cifra oficial verificada de forma independiente por este proyecto."),
            "source": {"name": "Caliescribe (Editorial), \"Alejandro Eder: lo bueno, lo malo y lo feo, 2.5 años de gobierno\"",
                      "url": "https://caliescribe.com/2026/07/03/alejandro-eder-lo-bueno-lo-malo-y-lo-feo-2-5-anos-de-gobierno/"},
        },
        "metrics": [
            {
                "label": "Inversión extranjera directa recibida (bienio)",
                "start": None, "start_year": 2024, "end": 120, "end_year": 2026, "change_pct": None,
                "note": "US$120 millones en IED durante el bienio, según declaraciones del propio alcalde.",
                "source": {"name": "LaRepublica.co, entrevista a Alejandro Eder",
                          "url": "https://www.larepublica.co"},
            },
        ],
        "projects": [
            {"name": "Tren de Cercanías", "category": "movilidad y transporte", "status": "en curso",
             "description": "Anunciado como proyecto estratégico para 2026 en adelante; sin obra física "
                            "reportada al momento de esta investigación.",
             "source": {"name": "Alcaldía de Cali / YouTube, \"¿Qué se viene para Cali en 2026?\"",
                       "url": "https://www.youtube.com"}},
            {"name": "Renovación del Centro Histórico", "category": "infraestructura y obras", "status": "en curso",
             "description": "Uno de los frentes de obra activos anunciados para 2026 (la Alcaldía reportó más "
                            "de 130 frentes de obra activos en octubre de 2025).",
             "source": {"name": "Alcaldía de Cali / YouTube, \"¿Qué se viene para Cali en 2026?\"",
                       "url": "https://www.youtube.com"}},
            {"name": "Fortalecimiento de EMCALI", "category": "corrupción y gobierno", "status": "en curso",
             "description": "Reconocido como esfuerzo positivo por el editorial de Caliescribe, sin resultado "
                            "final aún al ser una administración en curso.",
             "source": {"name": "Caliescribe (Editorial), \"Alejandro Eder: lo bueno, lo malo y lo feo, 2.5 años de gobierno\"",
                       "url": "https://caliescribe.com/2026/07/03/alejandro-eder-lo-bueno-lo-malo-y-lo-feo-2-5-anos-de-gobierno/"}},
            {"name": "MIO, valorización y Megaobras heredadas", "category": "movilidad y transporte", "status": "incompleto",
             "description": "Sin solución estructural reportada a mitad de 2026, según el editorial de "
                            "Caliescribe -- los mismos problemas heredados de las tres administraciones "
                            "anteriores.",
             "source": {"name": "Caliescribe (Editorial), \"Alejandro Eder: lo bueno, lo malo y lo feo, 2.5 años de gobierno\"",
                       "url": "https://caliescribe.com/2026/07/03/alejandro-eder-lo-bueno-lo-malo-y-lo-feo-2-5-anos-de-gobierno/"}},
        ],
    },
]


def needs_verification(source: dict) -> bool:
    """Fuente que apunta a la portada de un sitio (p. ej. "https://www.cali.gov.co") o a un resumen
    de buscador: no permite comprobar el dato y debe reemplazarse por la nota específica."""
    url = (source or {}).get("url", "")
    path = url.split("://", 1)[-1].split("/", 1)[1] if "/" in url.split("://", 1)[-1] else ""
    return not path.strip("/") or "resumen de Google" in (source or {}).get("name", "")


def status_counts(admin: dict) -> dict:
    counts = {"completado": 0, "en curso": 0, "incompleto": 0}
    for p in admin["projects"]:
        counts[p["status"]] = counts.get(p["status"], 0) + 1
    return counts


def debt_timeline() -> list[dict]:
    """Serie de deuda pública distrital a través de las 4 administraciones, para graficar la
    tendencia -- solo incluye las que tienen cifra con fuente."""
    return [
        {"period": a["period"], "mayor": a["mayor"], "value_billones_cop": a["debt"]["value_billones_cop"]}
        for a in ADMINISTRATIONS if a.get("debt") and a["debt"].get("value_billones_cop") is not None
    ]
