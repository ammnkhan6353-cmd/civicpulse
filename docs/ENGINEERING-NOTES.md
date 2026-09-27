# Engineering Notes — the eight questions

References are `file:line` in this repository. Lines marked **[FILL IN]** need numbers from our own runs; do not submit with them.

---

### 1. Three things that differ between a laptop and a CI runner, and the line that freezes each

1. **Python / Node runtime version.** A laptop has whatever Python the student installed (3.11, 3.13, the Windows Store alias); the runner has its own image default. Frozen by `backend/Dockerfile:9` and `:18` (`FROM python:3.12-slim-bookworm`) and `frontend/Dockerfile:8` (`FROM node:22-alpine`); the non-container CI jobs pin the same versions in `.github/workflows/ci.yml:32` and `:37` (`PYTHON_VERSION: "3.12"`, `NODE_VERSION: "22"`).
2. **Dependency versions.** `pip install fastapi` on Monday and on Friday can resolve differently; `node_modules` on a laptop is whatever was last installed. Frozen by `frontend/Dockerfile:11-12` (`COPY package.json package-lock.json` + `npm ci`, which installs exactly the lockfile and fails if it disagrees with package.json) and `backend/Dockerfile:14-15` (`COPY requirements.txt` + `pip wheel -r requirements.txt` in a builder stage; the tooling versions are pinned exactly in `backend/requirements-dev.txt:2,5,6`).
3. **Environment and configuration.** The laptop has a `.env` with a real Groq key and `TRIAGE_PROVIDER=llm`; the runner has no secrets and must be deterministic. Frozen by `.github/workflows/ci.yml:70` (`TRIAGE_PROVIDER: simulated` for the test job) and the integration job's `.env` rewrite (`ci.yml:164`), and in the cluster by `k8s/base/configmap.yaml` + a Secret, never a file on disk.

(A fourth we hit: line endings. Files committed from Windows get CRLF, which breaks shell scripts in Linux containers — frozen by `.gitattributes:2`, `* text=auto eol=lf`.)

### 2. Where our pipeline sits on the CI/CD maturity ladder

**Rung: Continuous Delivery with automated deployment to an ephemeral environment.** Every PR runs lint, type checks, unit and component tests, image builds, a vulnerability scan, manifest validation and a Compose integration test (`ci.yml`), and `main` is protected so nothing merges red. Every merge to `main` re-tests the merged result, publishes immutable SHA-tagged images and deploys them to a real Kubernetes cluster with a smoke test (`cd.yml:21-24`, `:81-83`). We are *not* at continuous deployment to a persistent production environment: the k3d cluster is thrown away after the run.

**Next rung: GitOps continuous deployment to a long-lived cluster** (Argo CD or Flux reconciling `k8s/overlays/prod` from Git). What it buys: the cluster's state is always what Git says (drift is detected and reverted), deploys and rollbacks become a reviewed commit, and nobody needs `kubectl` credentials in CI.

### 3. The exact line guaranteeing build-once-deploy-many

`.github/workflows/cd.yml:130` —
```
kustomize edit set image "civicpulse-backend=ghcr.io/$OWNER/civicpulse-backend:$SHA"
```
The image deployed is the one pushed in `build-push` under the tag `${{ github.sha }}` (`cd.yml:49`), which is the same Dockerfile CI built and scanned — nothing is rebuilt for deployment. For the frontend this only works because no environment-specific value is compiled into the bundle (ADR 0002: relative `/api` URLs, `frontend/src/api/client.ts`).

**What breaks without it:** deploying `:latest`, or rebuilding at deploy time, means the artifact in production is not the artifact that passed the tests. `:latest` also moves: two pods started ten minutes apart can run different code, and "what is production running?" has no answer you can `git show`, so rollback is guesswork.

### 4. With a live LLM the service is probabilistic. What does "correct" mean, and how is CI deterministic?

For the triage component, "correct" is a **contract**, not an exact output:
- every response is a valid `TriageResult` (enum category and priority, summary ≤ 140 chars, confidence 0–1) — enforced in `backend/app/providers/triage/base.py:14-22` and `llm.py:73`;
- the request always succeeds (201) within a bounded time — 10 s timeout (`llm.py:47`), one jittered retry (`retry.py:16-31`), otherwise fallback (`services/triage_service.py:73-84`);
- the result is honestly labelled (`triaged_by`) and measured (`triage_latency_ms`), so quality can be audited later;
- classification quality itself is a *statistical* property, judged on a labelled sample rather than per request.

CI is deterministic by design, not luck: the suite pins `TRIAGE_PROVIDER=simulated` (`ci.yml:70`), `SimulatedTriage` is a pure function of its input (`providers/triage/simulated.py`), the tests inject a provider that always raises and one that returns malformed JSON (`tests/conftest.py`, `tests/test_fallback.py`), the LLM client is replaced with a fake returning scripted replies and exceptions (`tests/test_providers.py`), the retry sleep and the rate-limiter clock are injected so no test calls `time.sleep()` or races the minute boundary, and Redis/Postgres are fakeredis and in-memory SQLite. The LLM runs with `temperature=0` in production (`llm.py:57`) to reduce — not eliminate — variance.

### 5. HPA lag: seconds between offered load rising and replicas rising

**[FILL IN from docs/evidence/hpa-watch.txt and scaling-chart.png]** — e.g. "k6 reached 40 VUs at t = 45 s; the HPA first reported > 60 % at t = 75 s; replicas went 2 → 4 at t = 90 s and the new pods passed readiness at t = 110 s: ~65 s from load to capacity."

Where the time goes (explain with our numbers):
1. **Metrics pipeline:** kubelet/cAdvisor samples CPU, metrics-server scrapes every ~15 s (k3s default), and reports a *windowed average*, so a spike is visible only after one or two scrapes.
2. **HPA sync period:** the controller evaluates every 15 s. Our `scaleUp.stabilizationWindowSeconds: 0` (`k8s/base/hpa.yaml:22`) removes any extra wait on the way up.
3. **Pod start:** scheduling, the `migrate` init container (`k8s/base/backend.yaml`, `initContainers`), Python start-up, then readiness (`/ready` every 5 s) before the Service sends traffic.

What would reduce it: a lower CPU target or higher `minReplicas` (spare headroom), a faster metrics resolution, removing the migration init container from every pod (run migrations once as a Job), a smaller image / faster start, or scaling on a leading signal (request rate, queue length) via custom metrics or KEDA instead of CPU, which only rises *after* users are already waiting. This lag is why autoscaling does not replace capacity planning.

### 6. Why VPA is in Off mode, and the failure mode of Auto alongside our HPA

`k8s/base/vpa.yaml:16` sets `updateMode: "Off"`: VPA only *recommends*. Our HPA scales on CPU **utilisation = usage ÷ request** (`hpa.yaml:17`). In Auto mode VPA also acts on CPU — by changing the *request*. Under load VPA raises the request → computed utilisation falls → the HPA scales *in* → each remaining pod gets more traffic → usage rises → VPA raises the request again (and evicts pods to apply it, which itself removes capacity mid-spike). The two controllers fight over one signal and the deployment oscillates. Recommender mode plus a human decision is standard practice: we read `kubectl describe vpa backend-vpa`, update `resources.requests` in `backend.yaml:91` in a reviewed commit, and re-run the load test.

Our loop (**[FILL IN]** in `docs/evidence/vpa.md`): guessed requests 100m CPU / 128Mi → VPA Target **[FILL IN]**, Lower **[FILL IN]**, Upper **[FILL IN]** → updated to **[FILL IN]** → HPA behaviour after: **[FILL IN — e.g. "scaled to fewer, busier pods; first scale-out 20 s later because the higher request made 60 % harder to reach"]**.

### 7. `internal: true` blocks outbound traffic. Where does that leave the service calling the LLM?

`compose.yaml:162-164` makes `internal` a network with no route to the outside world; Postgres, Redis and Ollama sit only on it (`compose.yaml:114,130,148`). A container that is *only* on `internal` cannot reach `api.groq.com`.

Our resolution: the **backend is the one service on both networks** (`compose.yaml:62`, `networks: [edge, internal]`). `edge` is a normal bridge network with outbound NAT, so the backend reaches Groq through `edge` and reaches the database through `internal`. The frontend is only on `edge` (`compose.yaml:20`) and so has no route to data: `docker compose exec frontend ping -c1 postgres` → `ping: bad address 'postgres'` (asserted in CI, `ci.yml` integration job).

Trade-off: the backend is now the single component with both internet egress and database access, so a compromised backend can exfiltrate. The stricter alternative is a dedicated egress proxy (or a small "triage gateway" service) on a third network that is the only thing allowed out, with an allow-list for `api.groq.com`; or the Ollama path, which needs no egress at all. We accepted the simpler design for a two-person project and documented it here.

### 8. The failure — something that cost us more than an hour

- **Symptom:** On our first CI run, the `integration` job failed at the POST step with
  `curl: (56) Connection reset by peer`, although `docker compose up` had succeeded.
- **What we wrongly believed first:** Me and Meerab believed that the backend was crashing on startup, so we
  looked at backend logs and the Groq key for a while - but CI uses `TRIAGE_PROVIDER=simulated`, so
  the key was irrelevant and the backend logs were clean.
- **The command or log line that told the truth:** `curl -fsS http://127.0.0.1:8000/ready`
  returned 200 while the request to nginx on :8080 was reset - the wait loop only waited
  for the backend, not for nginx.
- **Fix:** commit `6ce9cf5`, `.github/workflows/ci.yml:175-184` - the wait step now loops
  until both `/ready` (backend) and `/healthz` (nginx) answer.
- **What we'd do differently:** Next time around, we would wait on the health endpoint of every hop the test goes
  through, not just the one we wrote.