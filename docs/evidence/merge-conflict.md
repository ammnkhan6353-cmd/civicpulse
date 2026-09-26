# Deliberate merge conflict — `backend/app/config.py`

**Branches:** `feat/rate-limit-default` (Partner A) and `feat/rate-limit-burst` (Partner B), both cut from `dev` at the same commit, both editing the `rate_limit_per_minute` default on the same line.

- A: `Field(default=10, ge=1)  # Groq free tier: ~30 RPM org-wide`
- B: `Field(default=20, ge=1)  # shared CGNAT IPs need burst room`

A's PR merged first; B's `git merge origin/dev` produced the conflict (screenshots: `merge-conflict-markers.png`, `merge-conflict-resolution.png`, `merge-conflict-merged-pr.png`).

**Why A's version won:** [FILL IN in your own words, 2–4 sentences — e.g. "Groq's free tier limits requests per minute for the whole organisation, not per user, so 20/min per IP would let two users exhaust the quota for everybody and push every citizen onto rules:fallback. B's concern — many citizens behind one mobile-carrier IP — is real, but the fix for it is a per-user key, not a looser global limit. We kept 10/min and noted the CGNAT issue as future work."]
