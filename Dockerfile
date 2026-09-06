# syntax=docker/dockerfile:1
# Hive Research — local-first (Ollama/LM Studio/Nvidia) + TSX web dashboard
# Multi-stage: 1) build web TSX, 2) python runtime

FROM node:20-slim AS webbuild
WORKDIR /app/web
COPY web/package.json web/package-lock.json* ./
RUN npm ci --silent || npm install --silent
COPY web/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# system deps for httpx/bs4 and health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# python deps
COPY pyproject.toml README.md ./
COPY hive ./hive
COPY openwebui ./openwebui
COPY tests ./tests
RUN pip install --upgrade pip && pip install -e . --no-cache-dir

# copy built web dashboard (from webbuild stage)
COPY --from=webbuild /app/web/dist ./web/dist
COPY web/package.json ./web/package.json
COPY scripts ./scripts
RUN chmod +x /app/scripts/*.sh

# create hive dirs (persist via volumes — rebuild-safe: volumes survive build/up, only down -v deletes)
RUN mkdir -p /root/.hive/machine/workspace /root/.hive/machine/workflows /root/.hive/exports && \
    mkdir -p /app/web

EXPOSE 8000 8001 11434

HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD curl -fs http://localhost:8000/api/health || exit 1

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["hive", "web", "--host", "0.0.0.0", "--port", "8000"]
