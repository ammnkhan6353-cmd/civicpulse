# Deliberate merge conflict — `backend/app/config.py`

**Branches:** `feat/rate-limit-default` (Partner A) and `feat/rate-limit-burst` (Partner B), both cut from `dev` at the same commit, both editing the `rate\_limit\_per\_minute` default on the same line.

* A: `Field(default=10, ge=1)  # Groq free tier: \~30 RPM org-wide`
* B: `Field(default=20, ge=1)  # shared CGNAT IPs need burst room`

A's PR merged first; B's `git merge origin/dev` produced the conflict (screenshots: `merge-conflict-markers.png`, `merge-conflict-resolution.png`, `merge-conflict-merged-pr.png`).

**Why A's version won:** \[We kept 10/min because Groq's free tier limits requests per minute for the whole organisation, not per user. 20/min per IP would let a few users use up the quota and push every complaint onto rules:fallback. The shared-IP problem is real, but the right fix is per-user limits, not a looser global one.]

