# Evidence

Every screenshot and capture referenced by the README, the Engineering Notes and the rubric. All were produced by us on 27 Sep 2026.

| File | What it shows | Rubric |
|---|---|---|
| `branch-protection.png` | `main` rule: PR required, 1 approval, 7 required status checks, no bypass | A |
| `merge-conflict-markers.png` | `<<<<<<<` / `=======` / `>>>>>>>` in `backend/app/config.py` (PR #35) | A |
| `merge-conflict-resolution.png` | the resolved line: Accept Incoming, 10/min kept | A |
| `merge-conflict-merged-pr.png` | PR #35 merged | A |
| `merge-conflict.md` | why the 10/min version won, in our words | A |
| `red-check.png` | release PR: `test-backend` failing and the merge button blocked | I |
| `green-check.png` | the same PR after the revert: all checks green, merge allowed | I |
| `screenshot-dashboard.png`, `screenshot-submit.png`, `screenshot-stats.png` | the three views (submit shows `llm:groq`, stats shows `X-Cache: HIT`) | B, J |
| `meta-providers.json` | `/api/meta/providers`: hits 3, misses 2, hit rate 60 % | F |
| `fallback-ui.png`, `fallback-log.png` | wrong Groq key: complaint still accepted as `rules:fallback`, one WARNING log line with `AuthenticationError` | F |
| `ping-fails.png` | `docker compose exec frontend ping -c1 postgres` fails: frontend has no route to the database | G |
| `persistence-compose.png` | row count unchanged across `docker compose down` / `up` | D |
| `image-sizes.md` | final and build-stage image sizes; build context before/after `.dockerignore` | G |
| `persistence-k8s.png` | row count unchanged after `kubectl delete pod postgres-0` | H |
| `hpa-watch.txt` | `kubectl get hpa -w` during the k6 load test: 2 -> 10 replicas, then back to 2 | H |
| `scaling-chart.png` | backend replicas vs offered load (k6 virtual users) | H |
| `vpa.md` | guessed requests, VPA recommendation, updated requests (commit 7f42523), before/after HPA behaviour | H |
| `hpa-watch-after-vpa.txt` | `kubectl get hpa -w` for the re-run with the VPA-sized requests | H |
| `rollback.png` | `kubectl rollout undo` back to the previous image, then declarative re-apply of the overlay | I |