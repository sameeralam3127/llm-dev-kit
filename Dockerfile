FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=poll

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY app ./app

FROM base AS api
EXPOSE 8001
HEALTHCHECK --interval=20s --timeout=5s --retries=5 CMD curl -f http://localhost:8001/health || exit 1
CMD ["uvicorn", "app.api:api", "--host", "0.0.0.0", "--port", "8001"]

FROM base AS web
EXPOSE 8501
HEALTHCHECK --interval=20s --timeout=5s --retries=5 CMD curl -f http://localhost:8501/_stcore/health || exit 1
CMD ["streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true", "--browser.gatherUsageStats=false"]

FROM base AS mcp
CMD ["python", "-m", "app.mcp_server"]

FROM base AS worker
CMD ["python", "-m", "app.workers.embedding_worker"]
