# CivicPulse Runbook

Commands are shown for bash; the PowerShell equivalent is given where it differs.
Namespace for everything on Kubernetes: `civicpulse`.

## 1. Deploy

### Local (Docker Compose)
```bash
cp .env.example .env          # PowerShell: Copy-Item .env.example .env
docker compose up -d --build
docker compose ps             # every service "healthy"; migrate "exited (0)"
curl http://localhost:8000/ready
```

### Local Kubernetes (k3d)
```bash
k3d cluster create civicpulse --agents 2 -p "8081:80@loadbalancer"
docker build -t civicpulse-backend:dev backend
docker build -t civicpulse-frontend:dev frontend
k3d image import civicpulse-backend:dev civicpulse-frontend:dev -c civicpulse
kubectl apply -f https://raw.githubusercontent.com/kubernetes/autoscaler/vertical-pod-autoscaler-1.2.1/vertical-pod-autoscaler/deploy/vpa-v1-crd-gen.yaml
kubectl apply -k k8s/overlays/dev
kubectl -n civicpulse rollout status deploy/backend
kubectl -n civicpulse get pods,svc,ingress,hpa
```
Open http://localhost:8081. To use your Groq key locally:
```bash
kubectl -n civicpulse create secret generic civicpulse-secrets \
  --from-literal=POSTGRES_PASSWORD=CHANGE_ME --from-literal=GROQ_API_KEY=<your key> \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n civicpulse rollout restart deploy/backend
```
(Keep `POSTGRES_PASSWORD` equal to the value Postgres was initialised with.)

### Production path (CI)
Merge a PR into `main`. `cd.yml` runs the full test suite, builds and pushes `ghcr.io/<owner>/civicpulse-*:<commit-sha>`, spins up an ephemeral k3d cluster, pins the prod overlay to that SHA, applies it, waits for `rollout status`, and smoke-tests the Ingress.

**What is running?**
```bash
kubectl -n civicpulse get deploy backend -o jsonpath='{.spec.template.spec.containers[0].image}'
```
The tag is a commit SHA → `git show <sha>`.

## 2. Roll back

**Fast / imperative (the 3 a.m. answer)** — returns to the previous ReplicaSet in seconds:
```bash
kubectl -n civicpulse rollout history deployment/backend
kubectl -n civicpulse rollout undo deployment/backend
kubectl -n civicpulse rollout status deployment/backend
```
Use it when users are hurting *now*. Downside: the cluster no longer matches Git — the next `apply` would re-deploy the bad version.

**Declarative / auditable (once the fire is out)** — re-apply the overlay pinned to the last good SHA:
```bash
cd k8s/overlays/prod
kustomize edit set image civicpulse-backend=ghcr.io/<owner>/civicpulse-backend:<previous-sha>
kustomize edit set image civicpulse-frontend=ghcr.io/<owner>/civicpulse-frontend:<previous-sha>
kubectl -n civicpulse delete job seed --ignore-not-found   # Job templates are immutable
kubectl apply -k .
```
In the team workflow this is a PR that reverts the bad commit, so Git, the registry and the cluster agree and the change is reviewed.

Locally with the dev overlay, tag images `:v1` / `:v2`, `k3d image import` both, and switch with `kubectl -n civicpulse set image deployment/backend backend=civicpulse-backend:v2`.

## 3. Read logs

Logs are JSON on stdout, one object per line, each with a `request_id`.
```bash
docker compose logs -f backend                                   # Compose
kubectl -n civicpulse logs -l app=backend -f --max-log-requests 10
kubectl -n civicpulse logs -l app=backend --tail=200 | jq 'select(.level=="WARNING")'
kubectl -n civicpulse logs -l app=backend --tail=500 | jq 'select(.request_id=="<id>")'
```
Every response carries `X-Request-ID`; grep for it to follow one request end to end. PowerShell has no `jq` by default: use `| Select-String WARNING`.

## 4. Triage starts failing

**Symptoms:** new complaints show `triaged_by = rules:fallback`; the Stats page shows fallbacks in the recent outcomes table; `civicpulse_triage_fallback_total` rises. Citizens still get 201 — that is the design — so this is found through observability, not user reports.

1. **Confirm and classify:**
   ```bash
   curl -s localhost:8000/api/meta/providers | jq '.active_provider, .recent[:5]'
   kubectl -n civicpulse logs -l app=backend --tail=500 | jq -c 'select(.message=="triage fallback") | {complaint_id, provider, error_class}'
   ```
2. **Act on `error_class`:**
   | error_class | Meaning | Action |
   |---|---|---|
   | `AuthenticationError` | key missing / revoked | Check the Secret / `.env`; create a new key at console.groq.com; update the GitHub Secret `GROQ_API_KEY` |
   | `RateLimitError` | free-tier quota exhausted | Check the Groq limits page; lower `RATE_LIMIT_PER_MINUTE`; the content-hash cache absorbs duplicates |
   | `APITimeoutError` / `APIConnectionError` | provider slow/down or no egress | `curl https://api.groq.com` from a backend pod; check the edge network (Compose) / cluster egress |
   | `NotFoundError` / `BadRequestError` | model name retired | Update `GROQ_MODEL` in the ConfigMap / `.env` to a current model |
   | `MalformedTriageOutput` | model returned invalid JSON / off-enum values | Usually transient; if persistent, the model changed — pin another model |
3. **Mitigate:** switch provider without a code change — set `TRIAGE_PROVIDER=rules` (or `ollama`) in the ConfigMap / `.env` and `kubectl -n civicpulse rollout restart deploy/backend` (`docker compose up -d backend`).
4. **Recover:** once `/api/meta/providers` shows fresh `llm:groq` outcomes, switch back.

## 5. HPA load test (evidence capture)

Requirements: k3d cluster from §1 (metrics-server is built into k3s), `k6`.

Terminal 1 — watch the HPA and save it:
```bash
kubectl -n civicpulse get hpa backend -w | tee docs/evidence/hpa-watch.txt
```
Terminal 2 — record replicas every 5 s:
```bash
while true; do echo "$(date +%s),$(kubectl -n civicpulse get deploy backend -o jsonpath='{.status.replicas}')"; sleep 5; done > load/replicas.csv
```
PowerShell:
```powershell
while ($true) { "$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()),$(kubectl -n civicpulse get deploy backend -o jsonpath='{.status.replicas}')" | Add-Content load/replicas.csv; Start-Sleep 5 }
```
Terminal 3 — offered load:
```bash
k6 run load/k6-script.js --out csv=load/k6-results.csv
```
Afterwards: stop terminals 1–2 with Ctrl+C, then `pip install matplotlib && python load/plot_scaling.py` → `docs/evidence/scaling-chart.png`.

## 6. Zero-downtime rolling update (bonus)

While k6 runs (§5, terminal 3), in another terminal:
```bash
kubectl -n civicpulse set image deployment/backend backend=civicpulse-backend:v2
kubectl -n civicpulse rollout status deployment/backend
```
k6's summary must show `http_req_failed: 0.00%`. This works because of `maxUnavailable: 0`, the readiness probe, the 8 s `preStop` sleep, and uvicorn's graceful drain on SIGTERM.

## 7. Persistence checks

```bash
docker compose down && docker compose up -d        # rows survive (named volume pgdata)
curl -s localhost:8000/api/stats | jq .total

kubectl -n civicpulse delete pod postgres-0         # StatefulSet recreates it on the same PVC
kubectl -n civicpulse wait --for=condition=ready pod/postgres-0 --timeout=120s
curl -s localhost:8081/api/stats | jq .total        # same number as before
```
