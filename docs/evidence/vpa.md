# VPA recommender loop (backend)

1. **Requests we guessed** when writing `k8s/base/backend.yaml`: `cpu: 100m`, `memory: 128Mi`.
2. **Load test run:** `k6 run load/k6-script.js` on [FILL IN date/time].
3. **`kubectl describe vpa backend-vpa -n civicpulse`** after the run:

```
[FILL IN - paste the Recommendation section: Lower Bound / Target / Uncapped Target / Upper Bound]
```

4. **Requests updated to:** `cpu: [FILL IN]`, `memory: [FILL IN]` (commit [FILL IN sha]).
5. **Load test re-run — what changed about HPA behaviour:** [FILL IN — e.g. max replicas reached, time to first scale-out, CPU% the HPA reported].
