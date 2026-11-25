# CropDoc GB all-in-one image: API + built frontend + model (CPU only, no PyTorch).
# Build from the repository root:  docker compose up --build   →  http://localhost:8000
# Cloud hosts (Render, Hugging Face Spaces, Railway…) build this file directly; they give HTTPS, which the
# Live Scan camera needs on phones. The port comes from $PORT when the host sets it (default 8000).
FROM node:22-alpine AS web
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt
COPY backend/ backend/
COPY models/active/ models/active/
COPY results/ results/
COPY --from=web /src/frontend/dist frontend/dist
RUN useradd --create-home --uid 1000 cropdoc && mkdir -p /app/data && chown -R cropdoc /app/data
USER cropdoc
EXPOSE 8000
VOLUME ["/app/data"]
ENV PORT=8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health')" || exit 1
CMD ["sh", "-c", "exec python backend/run.py --host 0.0.0.0 --port \"$PORT\" --no-browser"]
