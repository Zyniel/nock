# syntax=docker/dockerfile:1
# The Nock server image: the built web client plus `python -m nock`.
# See docs/hosting.md (section 13) and docs/oracle-setup.md.

# Stage 1: build the web client into web/dist. The output is plain files, so it
# is built once on the build machine's own platform, even for an arm64 image.
FROM --platform=$BUILDPLATFORM node:24-slim AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: the Python environment and the app. The app finds web/dist, grids/
# and web/src/i18n/fr.json relative to its source folder, so the source tree is
# kept under /app and the project is installed in editable mode (uv's default).
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src/ src/
RUN uv sync --locked --no-dev
COPY web/src/i18n/ web/src/i18n/
COPY --from=web /app/web/dist/ web/dist/

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin nock \
    && mkdir /data \
    && chown nock /data
USER nock

# NOCK_HOST 0.0.0.0: inside a container the app must listen on every interface;
# the port is published nowhere in production, only Caddy reaches it.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    NOCK_HOST=0.0.0.0 \
    NOCK_PORT=8000 \
    NOCK_DATABASE=/data/nock.sqlite3
EXPOSE 8000
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=4)"]
CMD ["python", "-m", "nock"]
