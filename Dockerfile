FROM node:22-bookworm-slim AS frontend
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig*.json vite.config.ts ./
COPY src ./src
COPY public ./public
RUN npm run build:frontend

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    TINI_KILL_PROCESS_GROUP=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    ECO_NATIVE_HOST=0.0.0.0 ECO_NATIVE_PORT=18765 \
    ECO_NATIVE_DATA_DIR=/data ECO_NATIVE_ENV_PATH=/data/.env
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && python -m playwright install --with-deps chromium \
    && apt-get update && apt-get install -y --no-install-recommends xvfb xauth \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 app \
    && mkdir /data && chown app:app /data \
    && chmod -R a+rX /ms-playwright
COPY backend ./backend
COPY --from=frontend /app/dist/frontend ./dist/frontend
COPY docker/entrypoint.sh /usr/local/bin/eco-entrypoint
RUN chmod +x /usr/local/bin/eco-entrypoint
USER app
EXPOSE 18765
ENTRYPOINT ["eco-entrypoint"]
CMD ["python", "-m", "backend.web_server"]

# Optional target: build explicitly with a pinned Codex CLI version.
FROM runtime AS codex
USER root
COPY --from=frontend /usr/local/bin/node /usr/local/bin/node
COPY --from=frontend /usr/local/lib/node_modules/npm /opt/npm
ARG CODEX_VERSION
RUN test -n "$CODEX_VERSION" \
    && node /opt/npm/bin/npm-cli.js install --global --prefix /opt/codex "@openai/codex@$CODEX_VERSION" \
    && rm -rf /root/.npm /opt/npm \
    && mkdir -p /home/app/.codex && chown app:app /home/app/.codex
ENV PATH="/opt/codex/bin:${PATH}"
USER app

FROM runtime AS production
