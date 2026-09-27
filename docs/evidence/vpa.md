# VPA recommender loop (backend)

Cluster: k3d (1 server + 2 agents) on one laptop, 27 Sep 2026. VPA `updateMode: "Off"` - it only recommends.

1. **Requests we guessed** when writing `k8s/base/backend.yaml`: `cpu: 100m`, `memory: 128Mi`.
2. **Load test run:** `k6 run load/k6-script.js --out csv=load/k6-results.csv` at 20:05:03
   (0 -> 5 -> 40 -> 100 virtual users over 6m30s, GET-only). Evidence: `hpa-watch.txt`, `scaling-chart.png`.
3. **`kubectl -n civicpulse describe vpa backend-vpa`** after the run (condition `RecommendationProvided`):

        Recommendation:
          Container Recommendations:
            Container Name:  backend
            Lower Bound:
              Cpu:     25m
              Memory:  262144k
            Target:
              Cpu:     410m
              Memory:  262144k
            Uncapped Target:
              Cpu:     410m
              Memory:  262144k
            Upper Bound:
              Cpu:     22634m
              Memory:  6029819632


   Reading it: the Target is **4x our CPU guess and 2x our memory guess** (262144k = 256Mi).
   The Upper Bound is huge because the recommender had only ~30 minutes of history; its
   confidence interval narrows over days, so we act on the Target, not on the bounds.

4. **Requests updated to:** `cpu: 400m`, `memory: 256Mi` (Target 410m rounded down to a round
   number; memory equals the Target and stays under the 384Mi limit) - commit `7f42523`
   ("perf(k8s): set backend requests from VPA recommendation").

5. **Load test re-run - what changed about HPA behaviour** (same k6 script, started 20:32;
   evidence: `hpa-watch-after-vpa.txt`):

| | Before (100m / 128Mi) | After (400m / 256Mi) |
|---|---|---|
| CPU the HPA reported at peak | 174-434 % of request | 96-113 % of request |
| CPU once at max replicas | 200-400 % (never near target) | 52-90 % (hovering around the 60 % target) |
| First above target | +26 s | ~+60 s |
| First scale-out (2 -> 3) | +41 s | ~+75 s |
| Path to max | 2 -> 3 -> 6 -> 10 in 30 s | 2 -> 3 -> 4 -> 6 -> 9 -> 10 over ~2 min |
| Max replicas | 10 (= maxReplicas) | 10 (= maxReplicas) |
| Requests / failures | 71,700 / 1 (0.00 %) | 64,358 / 0 (0.00 %) |
| Latency p95 / max | 1.00 s / 11.25 s | 1.14 s / 15.36 s |

**What we learned.** With the guessed 100m request, utilisation (usage / request) was inflated
3-7x, so the HPA saw a crisis and jumped to `maxReplicas` in half a minute - the signal was
saturated and carried no information about *how much* capacity was needed. With the VPA-sized
request, utilisation is realistic: the HPA scaled in proportional steps (the HPA formula
`desired = ceil(current * utilisation / 60 %)` now produces +1 or +2 pods at a time), and at
10 replicas CPU sat around the target instead of 4x above it. The cost is a slower first
scale-out (~75 s vs ~41 s), because a pod now has to be genuinely busy before it reads 60 %.

It still reached 10 replicas, and throughput/latency barely changed. That is the honest limit
of this test: all 10 pods run on the same laptop's cores, so extra replicas cannot add real
CPU - on a real multi-node cluster they would. The right-sized request also matters to the
scheduler: 10 pods now *reserve* 4 CPUs, which is what they actually use, so the scheduler
will not over-pack a node the way 10 x 100m would have allowed.
