# Auditoría integral del monitor (2026-09-29)

| Documento | Contenido |
|---|---|
| [01-seguridad.md](01-seguridad.md) | 14 hallazgos (1 crítico, el puerto expuesto en el VPS, ya corregido en producción), cambios aplicados y acciones pendientes en el servidor |
| [02-frontend.md](02-frontend.md) | Carga por pestaña, errores, accesibilidad, móvil, nuevas vistas |
| [03-arquitectura.md](03-arquitectura.md) | N+1 (de 1.254 a 52 consultas), índices, scheduler, hoja de ruta |
| [04-estadistica-y-estrategia-redes.md](04-estadistica-y-estrategia-redes.md) | 8 errores en las cifras de redes, nuevas gráficas con intervalos de confianza y estrategia de redes para Carlos |
| [05-historico-2008-2026.md](05-historico-2008-2026.md) | Metodología y fuentes de la nueva pestaña Histórico |

## Acciones que requieren a alguien en el servidor
1. Desplegar con `scripts/deploy.sh` (ahora también ajusta el dueño de la carpeta de datos, porque la imagen ya no corre como root).
2. Revisar `DATABASE_URL` en el `.env` de producción y mover la base al volumen si hace falta (ver `01`, S7).
3. Configurar `CF_ACCESS_TEAM_DOMAIN` y `CF_ACCESS_AUD` (ver `01`, S2).
4. `pip install -r requirements.txt` (nueva dependencia: `pyjwt[crypto]`).
5. Regenerar el reporte del día: los guardados antes de hoy usan las cifras de redes con los errores E1 a E4.
