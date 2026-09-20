# Presupuesto — Monitor de menciones, Alcaldía de Cali 2027

**Fecha:** 2026-09-19 · Precios en USD, tomados de las páginas públicas de cada proveedor en esa fecha. Verificar antes de contratar.

## Supuestos de volumen

| Concepto | Valor |
|---|---|
| Candidatos monitoreados | 9 (incluido Carlos Arias), ~30 términos de búsqueda con alias |
| Menciones nuevas por día (prensa + Reddit + YouTube + redes) | 150–400 (hoy, sin campaña formal); 1.000+ en campaña |
| Tokens por clasificación de sentimiento | ~350 de entrada + ~40 de salida |
| Barridos de redes sociales (Google CSE) | 3 por día × 27 consultas = 81 consultas/día |

## Escenario 1 — Gratis (lo que corre el lunes)

| Servicio | Uso | Costo/mes |
|---|---|---|
| Google News RSS + feeds de medios | Prensa | 0 |
| Reddit RSS | Reddit | 0 |
| Google Custom Search JSON API | Instagram / Facebook / X (100 consultas/día gratis) | 0 |
| YouTube Data API v3 | Videos + comentarios (10.000 unidades/día gratis) | 0 |
| Ollama (qwen2.5:14b) en un PC propio | Sentimiento | 0 (el PC debe quedar encendido) |
| cloudflared tunnel | URL pública temporal | 0 |
| **Total** | | **USD 0** |

Limitaciones: la URL cambia cada vez que se reinicia el tunnel; el análisis depende de que el PC esté encendido; ~3–10 s por mención (suficiente para <2.000 menciones/día).

## Escenario 2 — Básico en la nube (recomendado para operar)

| Servicio | Uso | Costo/mes (estimado) |
|---|---|---|
| Anthropic API — Claude Sonnet 5 ($2 entrada / $10 salida por millón de tokens) | Sentimiento: 300 menciones/día ≈ 3,5 M tokens/mes | ~USD 12 |
| Railway (Hobby) | Servidor + scheduler + Postgres, URL fija | USD 5 + uso (~USD 10–15) |
| Google CSE por encima del free tier ($5 por 1.000 consultas) | Solo si se sube a 6+ barridos/día | USD 0–15 |
| **Total** | | **USD 30–45** |

En campaña (1.000 menciones/día) el costo de Claude sube a ~USD 40/mes; el resto no cambia.

## Escenario 3 — Completo (+ Bright Data)

Agrega búsqueda directa dentro de Reddit e Instagram/Facebook (no solo lo indexado por Google) y cobertura más profunda.

| Servicio | Uso | Costo/mes (estimado) |
|---|---|---|
| Escenario 2 | | USD 30–45 |
| Bright Data Web Scraper API — pay-as-you-go $1,50 por 1.000 registros (5.000 registros/mes gratis) | Reddit por keyword + posts de cuentas conocidas de IG/FB: ~30.000 registros/mes | ~USD 40 |
| Bright Data SERP API | Reemplazo/complemento de Google CSE si se agota la cuota | ~USD 10–20 |
| **Total** | | **USD 80–105** |

Nota: Bright Data ofrece 25 % de descuento por 3 meses en Scraper API (código promocional en su página al 2026-09-19).

## Fuera de presupuesto (decisión aparte)

- **Radio / TV**: captura de streams + transcripción. Construir internamente requiere un servidor con GPU (~USD 50–100/mes) o Whisper vía API (~USD 0,006/min de audio → 8 h/día de 3 emisoras ≈ USD 260/mes). Alternativa: proveedor de monitoreo de medios (Multiarchivo, Mass Medios, IPNoticias) con cotización formal.
- **X (Twitter) oficial**: la API Basic cuesta USD 200/mes y da 10.000 lecturas; no se recomienda por ahora.

## Recomendación

Arrancar en **Escenario 1** hoy, pasar a **Escenario 2** en cuanto se aprueben ~USD 45/mes (URL fija, no depende de un PC), y evaluar **Escenario 3** solo si la cobertura de Instagram/Facebook vía Google resulta insuficiente en las primeras semanas.
