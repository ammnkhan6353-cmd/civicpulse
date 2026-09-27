# ADR 0003 — Deploy by immutable commit SHA, never `:latest`

- **Status:** Accepted
- **Date:** 2026-09-26

## Context

"What is production running?" must have a one-word answer that can be pasted into `git show`. Mutable tags (`:latest`, `:main`) make that impossible: the same tag points at different images over time, rollbacks become guesses, and two nodes can pull different images for the "same" deployment.

## Decision

- `cd.yml` builds each image once and pushes it to GHCR as `ghcr.io/<owner>/civicpulse-<component>:<github.sha>` (and also `:latest` for humans browsing the registry — `:latest` is **pushed but never deployed**).
- The `deploy-k8s` job pins the prod overlay with `kustomize edit set image civicpulse-backend=ghcr.io/<owner>/civicpulse-backend:<sha>`; the committed overlay only contains the placeholder tag `set-by-cd`.
- Publishing and deploying jobs are gated with `needs:` — `build-push` needs `test`; `deploy-k8s` needs `build-push` — so nothing broken is ever published.
- Registry authentication uses the workflow's short-lived, repository-scoped `GITHUB_TOKEN` with `packages: write`, never a personal password.
- The image digest is captured as a job output and written to the run summary, for the digest-pinning bonus.

## Consequences

- `kubectl -n civicpulse get deploy backend -o jsonpath='{..image}'` prints the SHA; `git show <sha>` shows exactly what is running.
- **Rollback, two ways** (RUNBOOK): `kubectl rollout undo deployment/backend -n civicpulse` — fast, imperative, the 3 a.m. answer, but the cluster now disagrees with Git; then re-apply the overlay with the previous SHA — declarative and auditable, the correct state once the fire is out.
- Every commit to `main` creates two new image tags; old tags should be cleaned up by a GHCR retention policy.
- Next step (bonus): deploy by digest (`@sha256:…`) and sign with Cosign so the cluster can verify provenance, not just identity.
