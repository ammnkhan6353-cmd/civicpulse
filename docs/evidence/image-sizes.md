# Image and build-context sizes

Measured on Meerab's laptop, 27 Sep 2026, Docker Desktop with the containerd image store.

## Image sizes

| Image | Final (shipped) | Build stage (not shipped) |
|---|---|---|
| civicpulse-backend | **97.2 MB** | builder (python:3.12-slim + compiled wheels): 67.6 MB |
| civicpulse-frontend | **30.3 MB** (target < 60 MB - met) | build (node:22-alpine + node_modules + source): 104.6 MB |

**How measured:** `docker save <image> -o img.tar`, then the file size. With the containerd image
store, `docker images` reports compressed content *plus* the unpacked snapshot, so it roughly
doubles every number (it showed 404 MB / 112 MB for the two final images); the exported archive
is what is actually pushed to GHCR and pulled by the cluster.

**What the multi-stage builds buy us:**
- **Frontend:** the final image contains nginx, `nginx.conf` and the static `dist/` bundle only - no
  Node.js, no `node_modules`, no TypeScript source. 104.6 MB of build tooling is left behind, and the
  shipped image is about 3.5x smaller than the build stage.
- **Backend:** the runtime is larger than the builder, and that is expected: the builder holds only
  the compiled wheel files, while the runtime has them *installed* (unpacked into site-packages) plus
  the Debian security upgrades and our code. The gain here is not size but safety and cache speed:
  no pip cache, no wheel files (`rm -rf /wheels`), non-root user 10001, and the slow dependency layer
  is rebuilt only when `requirements.txt` changes.

## Build context (what `docker build` sends to the daemon)

| Build context | Without `.dockerignore` | With `.dockerignore` |
|---|---|---|
| backend/ | 318.5 kB | 126 kB (2.5x smaller) |
| frontend/ | **124.6 MB** (node_modules!) | **236 kB** (~500x smaller) |

**How measured:** `$env:DOCKER_BUILDKIT = "0"` then `docker build ...`, reading the line
"Sending build context to Docker daemon". The classic builder is used on purpose: BuildKit
transfers the context incrementally and only reports what changed since the previous build
(it showed 716 B / 112 kB), which hides the real size. `.dockerignore` was renamed away for the
"without" run and restored immediately (`git status` clean afterwards).

The backend difference is small on this laptop because its virtualenv lives elsewhere; on a
machine with `backend/.venv` present, the "without" number would include the whole venv.