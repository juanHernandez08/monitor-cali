# Cotización — Monitor de menciones, Alcaldía de Cali 2027

**Fecha:** 2026-09-23 · **TRM usada:** $3.208,66 COP por USD ([Banco de la República](https://www.banrep.gov.co/es/glosario/tasa-cambio-trm), 23-sep-2026).
Precios verificados en las páginas de cada proveedor en esa fecha. Cambian sin aviso: reconfirmar antes de contratar.

## 1. Qué hay que cambiar para no depender de un computador

Hoy el sistema corre en el PC de escritorio: si se apaga, se cierra la ventana o se reinicia,
deja de capturar y el enlace público muere. Dos piezas lo atan a esa máquina:

| Pieza | Hoy | En el servidor |
|---|---|---|
| Servidor web + capturador | ventana de PowerShell abierta | servicio `systemd` en un VPS, arranca solo tras un reinicio |
| Análisis de sentimiento | Ollama (`qwen2.5`) usando la tarjeta gráfica | **API de Claude (Haiku 4.5)** |
| Enlace público | tunnel de Cloudflare con URL aleatoria | dominio propio con HTTPS |
| Base de datos | `monitor.db` en el PC (8,7 MB hoy) | mismo archivo SQLite en el disco del VPS, con respaldo diario |

**El cambio de fondo es el sentimiento.** Alquilar una GPU en la nube cuesta entre USD 70 y 300
al mes; la API de Claude hace el mismo trabajo por **USD 3–6 al mes** con mejor calidad en
español. Medido sobre los datos reales del proyecto: 345 caracteres de mediana por mención,
~750 tokens de entrada y 50 de salida, unas 3.000 menciones al mes.

La base es SQLite y pesa 8,7 MB después de 2.526 menciones. **No hace falta Postgres**: en un año
rondaría los 150 MB. Menos piezas, menos costo, menos que se pueda romper.

## 2. Reemplazo de Bright Data

Bright Data quedó descartado como base: su plan gratuito (5.000 registros/mes) se agota y el
pago por uso no es predecible para una campaña con presupuesto cerrado.

| Necesidad | Reemplazo | Costo |
|---|---|---|
| Posts y **todos** los comentarios de las cuentas de **Carlos** (IG y FB) | **Meta Graph API** (oficial) | **Gratis, sin límite práctico.** Además entrega alcance, impresiones y guardados, que hoy no tenemos |
| Posts y likes de **rivales y concejales** | **Meta Business Discovery** (misma API) | Gratis. No entrega el texto de los comentarios |
| **Texto de los comentarios** de rivales y concejales | **Apify** (Instagram Scraper) | USD 2,30 por 1.000 registros |
| **X (Twitter)**: posts y **respuestas de la gente** | **Apify** (Tweet Scraper) | USD 0,40 por 1.000 tuits |
| Prensa, Reddit, YouTube | Google News, feeds locales, YouTube Data API | Gratis |

Bright Data queda como respaldo opcional, no como dependencia.

**Requisito para la parte gratuita de Meta:** el Instagram de Carlos debe ser cuenta *Business* o
*Creator* vinculada a una página de Facebook, y alguien con acceso debe crear una app gratuita en
Meta for Developers. Sin eso, sus comentarios también habría que pagarlos en Apify.

## 3. Consumo mensual estimado

Calculado sobre el volumen real del proyecto (30 candidatos, concejales y cuentas de medios):

| Concepto | Volumen/mes | Proveedor | USD/mes |
|---|---|---|---|
| Clasificación de sentimiento | ~3.000 menciones | Claude Haiku 4.5 (USD 1 / 5 por millón de tokens) | 3 |
| Posts y comentarios de IG/FB de rivales y concejales | ~4.000 registros | Apify | 9 |
| X: posts y respuestas | ~3.900 tuits | Apify | 2 |
| Servidor | — | VPS 2 vCPU / 4 GB | 6–12 |
| Dominio | — | `.co` o `.com` | 1 |
| Prensa, YouTube, Reddit, cuentas de Carlos | ilimitado | gratis | 0 |

## 4. Escenarios

### Escenario A — Mínimo viable (USD 10/mes ≈ **$32.000 COP/mes**)

| Ítem | USD/mes |
|---|---|
| VPS Hetzner CAX11 (2 vCPU ARM, 4 GB) | 4 |
| Claude Haiku 4.5 | 3 |
| Apify plan Free (USD 5 de crédito incluido) | 0 |
| Dominio (USD 12/año) | 1 |
| **Total** | **~8–10** |

Cubre: prensa, YouTube, Reddit, Ciudad, Agenda, Concejo, cuentas de Carlos vía Meta y **X completo**.
Limitación: los USD 5 de Apify no alcanzan para los comentarios de todos los rivales; habría que
priorizar 3 o 4 cuentas rivales al mes.

### Escenario B — Completo, recomendado (USD 35/mes ≈ **$112.000 COP/mes**)

| Ítem | USD/mes |
|---|---|
| VPS DigitalOcean 2 GB (o Hetzner CX23) | 12 |
| Claude Haiku 4.5 | 3 |
| Apify plan Starter (USD 19 de crédito incluido) | 19 |
| Dominio | 1 |
| **Total** | **~35** |

Cubre todo sin recortes: los 9 candidatos, los 21 concejales, cuentas de medios, X con respuestas
y comentarios de todos en Instagram y Facebook. Es el escenario que responde a los cuatro
objetivos completos.

### Escenario C — Campaña intensa (USD 60–70/mes ≈ **$200.000 COP/mes**)

Escenario B más volumen de Apify (plan Scale) para capturar más comentarios por publicación y
correr varias veces al día. Solo tiene sentido en los meses cercanos a la elección.

## 5. Costos únicos

| Ítem | USD | COP |
|---|---|---|
| Dominio primer año | 12 | 38.500 |
| Migración, configuración del servidor, HTTPS, respaldos y puesta en marcha | — | (trabajo de desarrollo) |
| **Total en dinero** | **12** | **38.500** |

No hay costos de licencias, instalación ni hardware: el proyecto es código propio.

## 6. Qué alcanza con $1.500.000 COP

| Escenario | Costo mensual | Meses cubiertos con 1,5 M |
|---|---|---|
| A — Mínimo | $32.000 | ~46 meses |
| **B — Completo (recomendado)** | **$112.000** | **~13 meses** |
| C — Campaña intensa | $200.000 | ~7 meses |

El Escenario B cubre **hasta octubre de 2027**, es decir todo el ciclo hasta las elecciones
territoriales, pagando por adelantado y sin volver a pedir presupuesto.

Nota: si el presupuesto de 1,5 M también debe cubrir el trabajo de desarrollo y migración, la
plata destinada a infraestructura se reduce en esa proporción. Con $400.000 COP asignados a
infraestructura, el Escenario B cubre ~3,5 meses y el A más de un año.

## 7. Riesgos y supuestos

- **Precios de terceros**: Claude, Apify, Hetzner y DigitalOcean pueden cambiar tarifas. Los
  montos de Claude y Apify son por consumo: si el volumen sube, suben; los topes que ya tiene el
  código (`BRIGHTDATA_MONTHLY_CREDITS`, `APIFY_MONTHLY_ITEMS`) evitan sobrecostos sorpresa.
- **Disponibilidad de Hetzner**: en septiembre de 2026 varios planes CX aparecían agotados.
  DigitalOcean es la alternativa segura, USD 6 más cara.
- **Meta Graph API**: depende de que Carlos tenga cuenta Business y de que su equipo autorice la
  app. Si no se consigue, sus comentarios pasan a Apify y el Escenario B sube unos USD 5.
- **Métodos de pago**: todos estos servicios cobran en dólares con tarjeta internacional.
- **Lo que no cubre esta cotización**: radio y televisión (requiere transcripción de audio, entre
  USD 50 y 260 al mes según el alcance), y la API oficial de X (USD 200/mes, innecesaria mientras
  Apify funcione).
