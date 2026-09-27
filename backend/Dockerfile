# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# CivicPulse backend - multi-stage, pinned, non-root.
# Pin by digest for the bonus:  FROM python:3.12-slim-bookworm@sha256:<digest>
# (get it with: docker buildx imagetools inspect python:3.12-slim-bookworm)
# ---------------------------------------------------------------------------

# ---- Stage 1: builder - compile wheels for every dependency --------------------
FROM python:3.12-slim-bookworm AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
# Copy ONLY the requirements first: this layer (the slow one) is reused from
# cache on every build where requirements.txt did not change.
COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt

# ---- Stage 2: runtime ---------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
# Pick up Debian security fixes published after the base tag was built.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home app
WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels /wheels/* && rm -rf /wheels

# Source last: editing code invalidates only this cheap layer.
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app app ./app

USER 10001
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

# Exec form: uvicorn is PID 1 and receives SIGTERM directly (a shell would swallow it).
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "20", "--no-access-log"]
