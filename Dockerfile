FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# .dockerignore deja fuera .env, monitor.db, .git y respaldos: la imagen no lleva secretos ni datos.
COPY . .
# Usuario sin privilegios: si alguien lograra ejecutar código en el contenedor, no sería root.
# /app completo es del usuario: si un .env viejo aún dice DATABASE_URL=sqlite:///monitor.db, SQLite
# puede crear el archivo (aunque ahí NO sobrevive a un redespliegue: ver docs/auditoria/01-seguridad.md).
RUN useradd --create-home --uid 10001 app && mkdir -p /app/data && chown -R app:app /app
USER app
# En la nube no hay Ollama: el sentimiento debe ir por Claude (ANTHROPIC_API_KEY).
ENV SENTIMENT_BACKEND=claude
# La base vive en el volumen /app/data (deploy.sh monta /opt/monitor-cali/data ahí). Antes el valor
# por defecto era sqlite:///monitor.db DENTRO del contenedor: si el .env no lo cambiaba, cada
# despliegue (docker rm + run) borraba todos los datos. Un DATABASE_URL en .env sigue mandando.
ENV DATABASE_URL=sqlite:////app/data/monitor.db
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"
CMD ["sh", "-c", "python -m scripts.seed_sources && uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=127.0.0.1"]
