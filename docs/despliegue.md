# Despliegue en la nube (Escenario 2)

Requiere `ANTHROPIC_API_KEY` (en la nube no hay Ollama) y las keys de Google.

## Railway (recomendado)

1. Subir el repo a GitHub (privado).
2. En [railway.app](https://railway.app): **New Project → Deploy from GitHub repo**. Railway detecta el `Dockerfile`.
3. **Add Postgres** al proyecto. Railway inyecta `DATABASE_URL` con esquema `postgresql://`; cambiarla en las variables del servicio a `postgresql+psycopg://...` (mismo valor, distinto prefijo).
4. Añadir `psycopg[binary]>=3.1` a `requirements.txt` y volver a desplegar.
5. Variables de entorno del servicio (Settings → Variables), copiando de `.env.example`:
   - `SENTIMENT_BACKEND=claude`, `ANTHROPIC_API_KEY`, `CLAUDE_MODEL=claude-sonnet-5`
   - `GOOGLE_API_KEY`, `GOOGLE_CSE_ID`, `GOOGLE_CSE_DAILY_LIMIT=95`
6. **Settings → Networking → Generate Domain** → URL pública fija.
7. El contenedor corre el seed y arranca el servidor con el scheduler. Verificar en `https://<dominio>/health`.

Costo: plan Hobby USD 5/mes + uso (el servicio es liviano; Postgres pequeño).

## Plan B: Render + Neon

- [render.com](https://render.com): **Web Service** desde el repo con Docker. El free tier se duerme tras 15 min sin tráfico (primera carga ~50 s); el plan Starter (USD 7/mes) no.
- [neon.tech](https://neon.tech): Postgres gratis (0,5 GB). Copiar la connection string como `DATABASE_URL` con prefijo `postgresql+psycopg://`.

## Qué cambia respecto a la demo local

| | Demo local (lunes) | Nube |
|---|---|---|
| Sentimiento | Ollama en el PC | Claude Sonnet 5 |
| Base de datos | SQLite (`monitor.db`) | Postgres |
| URL | `*.trycloudflare.com`, cambia al reiniciar | Dominio fijo |
| Disponibilidad | Mientras el PC esté encendido | 24/7 |

El código es el mismo; solo cambian variables de entorno.
