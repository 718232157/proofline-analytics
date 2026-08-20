FROM node:24-alpine AS frontend-build

WORKDIR /build/frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
ENV VITE_API_BASE_URL=""
ENV VITE_WORKSPACE_SLUG="moneki"
RUN pnpm build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    DATABASE_URL=sqlite:////app/backend/var/proofline.db \
    STATIC_DIR=/app/frontend/dist

WORKDIR /app
COPY backend/ ./backend/
COPY data/ ./data/
COPY workspaces/ ./workspaces/
COPY --from=frontend-build /build/frontend/dist ./frontend/dist
RUN pip install --no-cache-dir -e ./backend

WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os, urllib.request; port=os.getenv('PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=3)"

CMD ["sh", "-c", "python -m app.cli ingest --workspace moneki && python -m app.cli process --workspace moneki && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
