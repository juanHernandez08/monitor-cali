FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# En la nube no hay Ollama: el sentimiento debe ir por Claude (ANTHROPIC_API_KEY).
ENV SENTIMENT_BACKEND=claude
EXPOSE 8000
CMD ["sh", "-c", "python -m scripts.seed_sources && uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
