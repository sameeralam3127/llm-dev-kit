# syntax=docker/dockerfile:1
# One slim base, one stage per microservice. Each stage installs only its own
# requirements, so images stay small and rebuilds only touch the changed service.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Pull in Debian security patches published after the base image was cut.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home appuser
WORKDIR /app


FROM base AS llm-service
COPY services/llm_service/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
COPY services/devkit_common ./devkit_common
COPY services/llm_service ./llm_service
USER appuser
EXPOSE 8010
CMD ["uvicorn", "llm_service.main:app", "--host", "0.0.0.0", "--port", "8010"]


FROM base AS rag-service
COPY services/rag_service/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
COPY services/devkit_common ./devkit_common
COPY services/rag_service ./rag_service
USER appuser
EXPOSE 8020
CMD ["uvicorn", "rag_service.main:app", "--host", "0.0.0.0", "--port", "8020"]


FROM base AS webhook-service
COPY services/webhook_service/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
COPY services/devkit_common ./devkit_common
COPY services/webhook_service ./webhook_service
USER appuser
EXPOSE 8030
CMD ["uvicorn", "webhook_service.main:app", "--host", "0.0.0.0", "--port", "8030"]


FROM base AS embedding-worker
COPY services/embedding_worker/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
COPY services/devkit_common ./devkit_common
COPY services/embedding_worker ./embedding_worker
USER appuser
CMD ["python", "-m", "embedding_worker.main"]


FROM base AS mcp-service
COPY services/mcp_service/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
COPY services/devkit_common ./devkit_common
COPY services/mcp_service ./mcp_service
USER appuser
CMD ["python", "-m", "mcp_service.main"]
