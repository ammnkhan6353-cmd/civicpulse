# ADR 0002 — Frontend runtime configuration: proxy `/api`, never bake a URL

- **Status:** Accepted
- **Date:** 2026-09-26

## Context

Vite replaces `import.meta.env.*` at **build** time. If the backend URL were baked into the bundle, the frontend image would be environment-specific (one image for laptop, another for CI, another for the cluster), destroying build-once-deploy-many — the image we scanned and tested would not be the image we ship. Two standard fixes exist: (a) generate `/config.js` from environment variables when the container starts, or (b) never need an absolute backend URL at all.

## Decision

**Option (b): the browser only ever calls relative paths (`/api/...`).**

- In Compose, the frontend's nginx proxies `location /api/` to `http://backend:8000` (`frontend/nginx.conf`), forwarding `X-Forwarded-For` and `X-Request-ID`.
- In Kubernetes, the Ingress routes `/api` directly to the `backend` Service and `/` to the `frontend` Service on the same host (`k8s/base/ingress.yaml`).
- In development, the Vite dev server proxies `/api` to the local backend (`frontend/vite.config.ts`).

The API client (`frontend/src/api/client.ts`) contains no host, no port and no key.

## Consequences

- One frontend image runs unchanged in every environment; CD deploys the exact SHA-tagged image CI built and scanned.
- Same origin for page and API → **no CORS configuration is needed at all**, and no CORS mis-configuration is possible.
- No secret can leak through the bundle because the bundle holds no configuration; anything in a browser bundle is public regardless of minification.
- Trade-off: nginx's upstream name (`backend:8000`) is fixed by convention — every environment must provide a service called `backend`. If we ever need the SPA and API on different domains, we would switch to option (a) with a `/config.js` rendered at container start and add a CORS allow-list.
