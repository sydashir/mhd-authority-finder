# MHD Authority Finder — scheduler image (ADR-012).
# Python 3.12 + uv + headless Chromium. Single stage on purpose: Playwright's browser
# lives at PLAYWRIGHT_BROWSERS_PATH and copying it across build stages is more fragile
# than the size win is worth. Secrets are NEVER baked in — they are mounted at runtime
# (see docker-compose.yml); state/cache persist via a mounted volume.
FROM python:3.12-slim-bookworm

# uv: copy the static binary from the official image, pinned (not :latest) to match uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /uvx /usr/local/bin/

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PLAYWRIGHT_NO_SANDBOX=1

# Chromium's system deps on Debian bookworm (explicit list — avoids the `--with-deps`
# distro-detection caveat). NB: bookworm uses libasound2, not the t64 rename.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libnss3 libnspr4 \
      libatk1.0-0 libatk-bridge2.0-0 libatspi2.0-0 \
      libcups2 libdbus-1-3 libdrm2 libgbm1 \
      libxcb1 libxkbcommon0 libx11-6 libxcomposite1 libxdamage1 \
      libxext6 libxfixes3 libxrandr2 \
      libpango-1.0-0 libcairo2 libasound2 \
      fonts-liberation fonts-unifont ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependency layer first (cached unless pyproject.toml / uv.lock change).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Install ONLY chromium, with the exact playwright the dep-sync put in the venv. Call the
# venv binary directly — `uv run` would try to build the not-yet-copied project and fail.
RUN /app/.venv/bin/playwright install chromium

# Project source, then install the project itself into the same venv.
COPY . .
RUN uv sync --frozen --no-dev

# Non-root runtime user that owns the app + the browser cache.
RUN groupadd --system app && useradd --system --gid app --create-home app \
    && chown -R app:app /ms-playwright /app
USER app

# Entrypoint = the scheduler. Interval + safety caps come from the mounted .env.
CMD ["uv", "run", "python", "-m", "authority_finder.cli", "schedule"]
