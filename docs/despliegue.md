# Despliegue en la nube

Plan vigente desde 2026-09-28: **VPS propio (Hetzner) + SQLite + Docker**, Escenario B de
`docs/cotizacion.md` (~USD 41/mes ≈ $132.000 COP, dentro del presupuesto aprobado de 200.000
COP/mes). Reemplaza cualquier mención anterior a Railway/Postgres en este documento -- ese plan
quedó descartado: SQLite alcanza de sobra (10,9 MB con 2.770 menciones) y un VPS propio es más
barato que un PaaS con base de datos gestionada.

## 1. Qué necesita el cliente hacer (no lo puede hacer el asistente: requiere cuenta y pago)

1. **Crear cuenta en Hetzner Cloud** ([hetzner.com/cloud](https://www.hetzner.com/cloud)).
   Revisar disponibilidad antes de comprometerse -- en sept-2026 varios planes CX aparecían
   agotados en algunas regiones; si Hetzner no tiene cupo, DigitalOcean es el plan B (~USD 12/mes
   el droplet de 2 GB, siempre con stock).
2. **Crear un servidor**: imagen Ubuntu 24.04 LTS, plan con al menos 4 GB RAM (CX23 o equivalente,
   ~USD 6-12/mes), región cercana (Ashburn/US East es razonable para audiencia en Colombia).
3. **Agregar una llave SSH** al crear el servidor (recomendado) o anotar la contraseña root que
   Hetzner genera.
4. **Comprar un dominio** (~USD 12/año). Si el cliente ya tiene cuenta de Cloudflare (la usa para
   el túnel de desarrollo), comprarlo en Cloudflare Registrar es lo más simple: precio al costo y
   deja la puerta abierta a usar Cloudflare Access más adelante (login adicional sin tocar código,
   ver sección 4).
5. **Compartir con el asistente**: la IP del servidor + acceso SSH (llave privada o contraseña
   root), y el nombre del dominio comprado.

## 2. Qué hace el asistente una vez tiene acceso SSH

1. Instalar Docker en el servidor.
2. Clonar el repo (GitHub privado -- necesita que el repo exista ahí; hoy vive solo local).
3. Crear `.env` en el servidor con las variables de producción (ver plantilla abajo).
4. `docker build` + `docker run` (o `docker compose`), con reinicio automático
   (`--restart unless-stopped`) para que sobreviva a un reinicio del servidor.
5. Reverse proxy con Caddy (HTTPS automático vía Let's Encrypt, sin configuración manual de
   certificados) apuntando el dominio al contenedor.
6. Apuntar el dominio (registros DNS) al servidor.
7. Verificar `https://<dominio>/health` y que el login (HTTP Basic) pida credenciales.
8. Configurar el respaldo diario de `monitor.db` (cron simple: copiar el archivo a otro directorio
   o a almacenamiento externo).

## 3. Variables de entorno de producción

Plantilla en `.env.example`. En producción, además de lo que ya se usa en local:

```
SENTIMENT_BACKEND=claude          # en la nube no hay Ollama/GPU
ANTHROPIC_API_KEY=...             # reemplaza a Ollama para el análisis de sentimiento y el reporte
CLAUDE_MODEL=claude-sonnet-5
DASHBOARD_USER=...                # login obligatorio -- ver src/api.py, agregado 2026-09-28
DASHBOARD_PASSWORD=...            # usuario y contraseña compartida por todo el equipo (decisión del cliente)
GOOGLE_API_KEY=...
GOOGLE_CSE_ID=...
APIFY_TOKEN=...
```

`DATABASE_URL` se deja con el valor por defecto (SQLite) -- no hace falta Postgres.

## 4. Capa extra de acceso (opcional, recomendada): Cloudflare Access

Si el dominio pasa por Cloudflare (DNS proxied, "nube naranja"), se puede activar **Cloudflare
Zero Trust → Access** gratis para hasta 50 usuarios: pide un login por email (código de un solo
uso) ANTES de que la petición llegue al servidor -- una segunda barrera además del HTTP Basic de
la app, sin tocar código, y con registro de quién entró y cuándo. Se configura desde el panel de
Cloudflare, no requiere cambios en este repo.

## 5. Qué cambia respecto a correr en el PC local

| | PC local (hoy) | VPS en la nube |
|---|---|---|
| Sentimiento | Ollama (`qwen2.5:14b`, GPU) | Claude Haiku/Sonnet vía API |
| Base de datos | SQLite en el PC | SQLite en el disco del VPS, con respaldo diario |
| URL | túnel de Cloudflare, cambia al reiniciar | dominio propio, fija, con HTTPS |
| Disponibilidad | mientras el PC esté prendido y la ventana abierta | 24/7, sobrevive a reinicios |
| Acceso | quien tenga la URL del túnel (nadie lo pide) | login obligatorio (HTTP Basic + opcionalmente Cloudflare Access) |

El código de la aplicación no cambia: solo las variables de entorno y dónde corre.
