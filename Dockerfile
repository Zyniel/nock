# syntax=docker/dockerfile:1
#
# The Nock image. The server finds web/dist, grids/ and web/src/i18n/fr.json
# from the place of its own modules (Path(__file__).resolve().parents[2]), so the
# final image keeps the repository layout under /app.

# --- Stage 1: build the web client (Node is not in the final image) -----------
FROM node:lts-slim AS web
WORKDIR /build
# The package files first: the install layer is reused while they do not change.
COPY web/package.json web/package-lock.json web/
RUN npm --prefix web ci
COPY web/ web/
RUN npm --prefix web run build

# --- Stage 2: install the Python project in a virtual environment -------------
FROM python:3.14-slim AS python
COPY --from=ghcr.io/astral-sh/uv:0.11.25 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PYTHON_PREFERENCE=only-system
WORKDIR /app
# The dependencies first (no dev group), then the project itself, editable as
# `uv sync` does: /app/.venv points to /app/src.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY README.md ./
COPY src/ src/
RUN uv sync --frozen --no-dev

# --- Stage 3: the runtime image ------------------------------------------------
FROM python:3.14-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NOCK_HOST=0.0.0.0 \
    NOCK_DATABASE=/data/nock.sqlite3
# A non-root user, and /data owned by it, so a fresh named volume is writable.
RUN useradd --system --create-home --uid 10001 nock \
    && mkdir /data \
    && chown nock:nock /data
WORKDIR /app
COPY --from=python /app/.venv /app/.venv
COPY --from=python /app/src /app/src
COPY --from=web /build/web/dist /app/web/dist
COPY web/src/i18n /app/web/src/i18n
COPY grids /app/grids
USER nock
VOLUME /data
EXPOSE 8000
# `/` answers 200 with a web build and 503 without. No curl in the image: the
# venv's Python asks (urlopen raises on a 503, which makes the check fail).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["/app/.venv/bin/python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('NOCK_PORT', '8000') + '/', timeout=3)"]
CMD ["/app/.venv/bin/python", "-m", "nock"]
