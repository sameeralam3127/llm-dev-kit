# syntax=docker/dockerfile:1
# One slim base, one stage per microservice. Each stage installs only its own
# requirements, so images stay small and rebuilds only touch the changed service.

# The gateway image is now plain nginx: the frontend is the `web` service
# (Next.js), which nginx reverse-proxies rather than serving from disk.
# nginx.conf is bind-mounted by docker-compose so config changes need no rebuild.
# The "starting up" fallback page is baked in — it's static and never changes.
FROM nginx:1.27-alpine AS gateway
COPY nginx/starting.html /usr/share/nginx/html/_starting.html


FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Pull in Debian security patches published after the base image was cut.
# Cache mounts persist apt's index/archive across builds without baking them
# into the image (the mounts themselves never become layers), so there's
# nothing left to `rm -rf` afterwards.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update \
    && apt-get upgrade -y --no-install-recommends

RUN useradd --create-home appuser
WORKDIR /app


FROM base AS llm-service
COPY services/llm_service/requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /tmp/requirements.txt
COPY services/devkit_common/src/devkit_common ./devkit_common
COPY services/llm_service/src/llm_service ./llm_service
USER appuser
EXPOSE 8010
CMD ["uvicorn", "llm_service.main:app", "--host", "0.0.0.0", "--port", "8010"]


FROM base AS rag-service
COPY services/rag_service/requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /tmp/requirements.txt
COPY services/devkit_common/src/devkit_common ./devkit_common
COPY services/rag_service/src/rag_service ./rag_service
USER appuser
EXPOSE 8020
CMD ["uvicorn", "rag_service.main:app", "--host", "0.0.0.0", "--port", "8020"]


FROM base AS mcp-service
COPY services/mcp_service/requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /tmp/requirements.txt
COPY services/devkit_common/src/devkit_common ./devkit_common
COPY services/mcp_service/src/mcp_service ./mcp_service
USER appuser
CMD ["python", "-m", "mcp_service.main"]
