# Ciudad — temas que se propagan en Cali y percepción ciudadana

**Fecha:** 2026-09-22 · **Estado:** aprobado por el cliente (chat 2026-09-22)

## Objetivo

Que la campaña sepa **de qué habla Cali** cada semana y **cómo lo siente la gente**, para decidir de
qué hablar y cómo. Hoy solo se guardan menciones que nombran a un candidato; esto captura la
conversación de la ciudad completa y la cruza con la presencia de Carlos Arias.

## Datos

Se crea un "candidato" especial **Cali (ciudad)** (`Candidate.kind = "city"`; los demás,
`"candidate"`). Todo lo que no nombre a un candidato pero venga de una fuente de ciudad se atribuye
a él. No aparece en las tarjetas ni gráficas de candidatos.

Fuentes de ciudad (mismos conectores, términos propios):
- Google News: consulta `Cali` (relevancia + when:7d) con contexto vacío → notas de Cali.
- Feeds RSS locales (El País Cali, Q'hubo, 90 Minutos, Caliescribe): **todo** el feed va a ciudad
  salvo lo que nombre a un candidato (que sigue yendo al candidato).
- YouTube: término `Cali noticias` (videos y comentarios).
- Instagram/Facebook: posts y comentarios de cuentas de medios (`candidate: None`) que no nombren
  a un candidato.
- Reddit: no (ruido).

## Clasificación

A **toda** mención (ciudad y candidatos) se le añade una **categoría fija** además del `topic` libre:

`seguridad` · `movilidad y transporte` · `terremoto y reconstrucción` · `servicios públicos` ·
`salud` · `educación` · `empleo y economía` · `vivienda` · `medio ambiente y clima` ·
`cultura y eventos` · `deporte` · `corrupción y gobierno` · `política y elecciones` ·
`orden público y protestas` · `infraestructura y obras` · `animales` · `otro`

`SentimentScore.category` (nueva columna). Para ciudad, el prompt cambia el marco: la etiqueta es
la **percepción ciudadana** del asunto — negativa = queja, molestia, miedo, preocupación;
positiva = orgullo, celebración, agradecimiento; neutral = informativo — y el `topic` es el
subtema concreto ("agua en Terrón Colorado"). Homónimos/exclusiones no aplican a ciudad; las
reglas de comentarios (tangencial, etiquetas sueltas) sí.

Reclasificar lo existente para poblar `category` (≈1.100 items, en segundo plano).

## Consultas (`src/queries.py`)

- `city_topics(days)` → por categoría: `count`, `previous` (período anterior), `trend_pct`,
  `positive/neutral/negative`, `subtopics` (top 5 `topic`), `samples` (3 comentarios con mayor
  |score|, con autor, fuente, url), `sources` (conteo por plataforma).
- `city_opportunities(days)` → categorías con volumen ≥ mediana y % negativo ≥ 40 % donde las
  menciones de Carlos con esa categoría son ≤ 2 → "temas calientes sin presencia"; y categorías
  donde Carlos tiene ≥ 3 menciones con ≥ 60 % positivas → "temas donde ya suma".
- `city_kpis(days)` → total de menciones de ciudad, categoría #1, categoría que más sube, % de
  percepción negativa global.

## Dashboard — pestaña **Ciudad**

1. KPIs: menciones de ciudad · tema #1 · tema que más sube · % de molestia ciudadana.
2. **¿De qué habla Cali esta semana?** — barras por categoría con ▲/▼ % vs período anterior.
   Lectura automática.
3. **¿Cómo lo siente la gente?** — barras 100 % (molesta / neutral / a favor) por categoría.
4. **Oportunidades para Carlos Arias** — dos listas con lectura: "la ciudad está molesta con X y
   Carlos no habla de ello" / "en Y Carlos ya tiene presencia positiva".
5. **Detalle por tema** — acordeón por categoría: subtemas y 3 comentarios representativos con
   link y sentimiento.

Textos en español llano, sin jerga; cada gráfica con qué se cuenta y cómo leerla.

## Scheduler

Ciudad entra en `job_fast` (Google News + RSS) y `job_youtube` con sus términos. Volumen esperado:
100–300 items/día → 1–2 h de clasificación diaria en segundo plano.

## Pruebas

Categoría en `_parse_payload`; atribución a ciudad en `ingest` (feed local sin candidato → ciudad;
con candidato → candidato); `city_topics` con tendencia y muestras; `city_opportunities` con los
dos casos; rutas API. Sin red.
