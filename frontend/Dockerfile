# syntax=docker/dockerfile:1
#
# Two stages. The first compiles the SPA; the second is a throwaway container
# whose only job is to copy the built assets into the shared `webroot` volume
# that the `proxy` (Caddy) service serves read-only. We do NOT run a web server
# here — Caddy already does SPA routing and API reverse-proxying in one place
# (see docker/Caddyfile).

# --- build stage ----------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app

# VITE_API_BASE is relative: Caddy proxies the API on the same origin, so the
# browser just calls /api/v1/* . No build arg needed for the composed stack.
ENV VITE_API_BASE=/api/v1

COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build          # -> /app/dist

# --- publish stage ------------------------------------------------------------
# Reuses the node:22-alpine layer already pulled for the build stage (no extra
# image). The container copies /app/dist into the mounted volume and exits;
# compose gates `proxy` on this completing successfully. `ENTRYPOINT []` clears
# any inherited entrypoint so the CMD runs as a plain shell invocation.
FROM node:22-alpine AS publish
COPY --from=build /app/dist /opt/site
ENTRYPOINT []
CMD ["sh", "-c", "rm -rf /srv/* && cp -a /opt/site/. /srv/ && echo 'frontend: published SPA bundle to /srv'"]
