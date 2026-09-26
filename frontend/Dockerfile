# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# CivicPulse frontend - Node builds, nginx serves. The final image contains no
# Node, no node_modules and no source: only the static bundle and nginx.conf.
# ---------------------------------------------------------------------------

# ---- Stage 1: build --------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app
# Dependency manifests first: `npm ci` is cached until package*.json change.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
RUN npm run build

# ---- Stage 2: serve --------------------------------------------------------
FROM nginxinc/nginx-unprivileged:1.29-alpine AS runtime
# Apply Alpine security fixes released after the base tag was built, then drop root again.
USER root
RUN apk upgrade --no-cache
USER 101
COPY --chown=101:101 nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build --chown=101:101 /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]
CMD ["nginx", "-g", "daemon off;"]
