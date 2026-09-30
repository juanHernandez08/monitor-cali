# Revisión de arquitectura (2026-09-29)

## Cómo está hoy

```
              ┌───────────────────────── un solo proceso (uvicorn) ─────────────────────────┐
 Conectores → │ APScheduler: ingesta (15 min / 8 h / 12 h) → enriquecimiento → LLM (2 min)   │
 (RSS, GN,    │ FastAPI: ~40 rutas JSON + HTML + estáticos                                   │
 YouTube,     │ queries.py (≈1.100 líneas) · report.py · sentiment.py                       │
 Apify)       └──────────────────────────────────┬──────────────────────────────────────────┘
                                                 │ SQLAlchemy
                                         SQLite (WAL) en volumen
```

Lo que está bien: separación clara conectores → pipeline → consultas → API; dependencias de pago opcionales (sin credencial, la fuente se omite); SQLite en WAL es suficiente para este volumen (≈5.000 menciones, crece unas 600 por día); 233 pruebas automáticas; decisiones documentadas en el HANDOFF.

## Hallazgos

| # | Hallazgo | Impacto | Estado |
|---|---|---|---|
| A1 | **Consultas N+1**: cada mención cargaba su sentimiento, candidato y fuente en consultas separadas. `/api/summary` a 90 días hacía 1.254 consultas SQL; `/api/agenda`, 3.129 | Lentitud creciente con los datos | Corregido: `lazy="selectin"` en `Mention`. Ahora 52 y 22 consultas; tiempos 2 a 5 veces menores |
| A2 | Sin índices en `mentions` para candidato, fecha y fuente | Consultas lineales | Corregido: índices idempotentes en `init_db()` |
| A3 | Scheduler dentro del proceso web: con `--workers 2` habría dos schedulers y doble gasto | Riesgo al escalar | Mitigado: `RUN_SCHEDULER=0` levanta solo la web |
| A4 | "Actualizar ahora" corría por fuera del scheduler, en paralelo con el mismo job | Doble gasto y carreras al guardar | Corregido: candado por grupo |
| A5 | Métricas de redes leídas con nombres de campo de un solo proveedor | Cifras erróneas (ver `04`) | Corregido |
| A6 | Migraciones manuales (`_add_missing_columns`): solo agrega columnas, no renombra ni cambia tipos | Deuda técnica | Recomendado: Alembic |
| A7 | `queries.py` mezcla 6 dominios (resumen, feed, redes, ciudad, agenda, concejo) | Mantenimiento | Recomendado: dividir en `queries/` por dominio |
| A8 | Carga de todo el período en Python para agregar (Counter sobre objetos ORM) | Escala hasta ~100 mil menciones; después, lento | Recomendado: agregaciones en SQL para resumen y timeline |
| A9 | Candidatos, cuentas y feeds viven en `config.py` y se "siembran" al arrancar | Cambiar un alias exige desplegar código | Aceptable hoy; a futuro, tabla editable |
| A10 | Sin respaldo automático ni monitoreo (solo logs) | Pérdida de datos / caídas silenciosas | Recomendado (ver abajo) |
| A11 | Frontend en un solo archivo JS global | Errores por orden de declaración | Mitigado; recomendado módulos ES (ver `02`) |
| A12 | Versión del prompt no se guarda con cada clasificación | No se puede saber con qué criterio se clasificó cada mención | Recomendado: `SentimentScore.model = "claude-sonnet-5@prompt-v7"` |

## Cambios aplicados
* `src/models.py`: carga `selectin` de `candidate`, `source` y `sentiment`.
* `src/db.py`: `_ensure_indexes()`.
* `src/config.py` y `src/api.py`: `RUN_SCHEDULER`, `CF_ACCESS_*`, intervalos mínimos, `ENABLE_API_DOCS`.
* `src/scheduler.py`: `@exclusive(nombre)` en todos los jobs.
* Módulos nuevos pequeños y con prueba propia: `security.py`, `netsafe.py`, `stats.py`, `city_history.py`.

## Hoja de ruta sugerida (en orden de valor/esfuerzo)
1. **Respaldo diario fuera del VPS** (30 min): cron con `sqlite3 .backup` y subida a un bucket o Drive.
2. **Monitoreo mínimo** (1 h): UptimeRobot o Healthchecks.io contra `/healthz`, y aviso si `runs.error` se repite.
3. **Fijar dependencias** con `pip-compile` (ver `01`).
4. **Alembic** para migraciones (medio día).
5. **Dividir `queries.py`** y mover agregaciones pesadas a SQL (1 día).
6. **Worker separado**: `RUN_SCHEDULER=0` en la web y un segundo contenedor con el scheduler, misma imagen (1 h, cuando haga falta más de un proceso web).
7. **Tabla de configuración** para candidatos y cuentas, editable desde el tablero (1 a 2 días).
