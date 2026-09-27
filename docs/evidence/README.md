# Evidence

Put every screenshot and capture here, using these exact file names (scripts/check_submission.py looks for them).

| File | What it shows | How to get it |
|---|---|---|
| `branch-protection.png` | `main` rule: PR required, 1 approval, required status checks, no bypass | GitHub → Settings → Branches → edit rule → screenshot |
| `merge-conflict-markers.png` | `<<<<<<<` / `=======` / `>>>>>>>` in `backend/app/config.py` | VS Code after `git merge origin/dev` |
| `merge-conflict-resolution.png` | the resolved file / VS Code "Accept" choice | VS Code |
| `merge-conflict-merged-pr.png` | the merged PR page | GitHub |
| `merge-conflict.md` | 2–4 sentences on why that version won | write it |
| `red-check.png` | failing CI check + blocked merge button | the deliberately failing PR |
| `green-check.png` | the same PR after the fix, all green | same PR |
| `ping-fails.png` | `docker compose exec frontend ping -c1 postgres` failing | terminal |
| `persistence-compose.png` | row count before/after `docker compose down && up` | terminal |
| `persistence-k8s.png` | row count before/after `kubectl delete pod postgres-0` | terminal |
| `hpa-watch.txt` | `kubectl get hpa -w` output with replicas rising | RUNBOOK §5 |
| `scaling-chart.png` | replicas vs offered load | `python load/plot_scaling.py` |
| `vpa.md` | guessed requests, `kubectl describe vpa backend-vpa` output, new requests, HPA change | RUNBOOK §5 + VPA install |
| `image-sizes.md` | final image sizes + build-context sizes before/after `.dockerignore` | commands in the playbook |
| `screenshot-submit.png`, `screenshot-dashboard.png`, `screenshot-stats.png` | the three views (used by the README) | browser |
| `meta-providers.json` | `/api/meta/providers` output with the measured cache hit rate | `curl` |
| `groq-limits.png` | the Groq rate-limit page we cited | console.groq.com |
