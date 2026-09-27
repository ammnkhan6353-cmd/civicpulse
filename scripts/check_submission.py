#!/usr/bin/env python3
"""Pre-submission lint:  python scripts/check_submission.py

Catches the mechanical failures behind most automatic deductions (assignment 5.3).
It is a lint, not a grader: a clean run does not guarantee a good mark.
Exit code 0 = clean, 1 = problems found.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
problems: list[str] = []
warnings: list[str] = []


def fail(msg: str) -> None:
    problems.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def read(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


# 1. Secrets in git ---------------------------------------------------------------
tracked = git("ls-files").splitlines()
for name in tracked:
    base = name.rsplit("/", 1)[-1]
    if base == ".env" or (base.startswith(".env.") and base != ".env.example"):
        fail(f"tracked env file: {name}")
    if base == "secrets.prod.env":
        fail(f"tracked secrets file: {name}")

history = git("log", "--all", "-p", "--no-color")
if re.search(r"gsk_[A-Za-z0-9]{20,}", history):
    fail("a Groq API key (gsk_...) appears in git history - rotate it and rewrite history")
if re.search(r"AIza[0-9A-Za-z_\-]{30,}", history):
    fail("a Google API key appears in git history")

# 2. Pinned images -----------------------------------------------------------------
image_re = re.compile(r"^\s*(?:FROM|image:)\s+([^\s#]+)", re.IGNORECASE | re.MULTILINE)
files_with_images = ["backend/Dockerfile", "frontend/Dockerfile", "compose.yaml", "compose.prod.yaml"]
files_with_images += [str(p.relative_to(ROOT)) for p in (ROOT / "k8s").rglob("*.yaml")]
for rel in files_with_images:
    for ref in image_re.findall(read(rel)):
        ref = ref.strip("\"'")
        if ref.startswith("civicpulse-") or "${" in ref:
            continue  # our own images: tag set by the overlay / IMAGE_TAG
        last = ref.split("/")[-1]
        if ":" not in last and "@sha256:" not in ref:
            fail(f"{rel}: unpinned image '{ref}'")
        elif last.endswith(":latest"):
            fail(f"{rel}: ':latest' image '{ref}'")

# 3. compose.prod.yaml: no build:, no published DB/cache ports, IMAGE_TAG used --------------
prod = read("compose.prod.yaml")
if re.search(r"^\s*build:", prod, re.MULTILINE):
    fail("compose.prod.yaml contains a build: key")
if "${IMAGE_TAG" not in prod:
    fail("compose.prod.yaml does not use ${IMAGE_TAG}")
for service in ("postgres", "redis"):
    block = re.search(rf"^  {service}:\n((?:    .*\n|\n)*)", prod, re.MULTILINE)
    if block and re.search(r"^    ports:", block.group(1), re.MULTILINE):
        fail(f"compose.prod.yaml publishes a port on {service}")

# 4. localhost between services ------------------------------------------------------
for rel in ["compose.yaml", "compose.prod.yaml", "frontend/nginx.conf", "backend/app/config.py"]:
    for line in read(rel).splitlines():
        if "localhost" in line and not line.strip().startswith("#"):
            fail(f"{rel}: 'localhost' used for service-to-service traffic: {line.strip()}")

# 5. Kubernetes ----------------------------------------------------------------------
k8s_text = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "k8s").rglob("*.yaml"))
if not re.search(r"kind:\s*StatefulSet[\s\S]*?name:\s*postgres", k8s_text):
    fail("postgres is not a StatefulSet")
if "volumeClaimTemplates" not in read("k8s/base/postgres.yaml"):
    fail("postgres StatefulSet has no volumeClaimTemplates")
if re.search(r"type:\s*(NodePort|LoadBalancer)", k8s_text):
    fail("a NodePort/LoadBalancer Service exists (database must be ClusterIP)")
if re.search(r"newTag:\s*latest", k8s_text):
    fail("an overlay deploys :latest")
for secret_file in (ROOT / "k8s").rglob("*.env*"):
    content = secret_file.read_text(encoding="utf-8")
    if secret_file.name != "secrets.prod.env" and re.search(r"gsk_|AIza", content):
        fail(f"{secret_file.relative_to(ROOT)} contains a real-looking API key")
if "resources:" not in read("k8s/base/backend.yaml") or "requests:" not in read(
    "k8s/base/backend.yaml"
):
    fail("backend has no resources.requests - the HPA cannot compute utilisation")

# 6. Workflows ------------------------------------------------------------------------
cd = read(".github/workflows/cd.yml")
for job in ("build-push", "deploy-k8s"):
    match = re.search(rf"^  {job}:\n((?:    .*\n|\n)*)", cd, re.MULTILINE)
    if not match or "needs:" not in match.group(1):
        fail(f"cd.yml job '{job}' is not gated by needs:")
for wf in (".github/workflows/ci.yml", ".github/workflows/cd.yml", ".github/workflows/release.yml"):
    text = read(wf)
    if not text:
        fail(f"missing {wf}")
    elif "permissions:" not in text:
        fail(f"{wf} has no permissions: block")
    for uses in re.findall(r"uses:\s*([^\s]+)", text):
        if not uses.startswith("./") and "@" not in uses:
            fail(f"{wf}: action not pinned: {uses}")

# 7. Schema DDL outside migrations -------------------------------------------------------
for path in (ROOT / "backend" / "app").rglob("*.py"):
    if "create_all(" in path.read_text(encoding="utf-8"):
        fail(f"{path.relative_to(ROOT)} calls create_all() - schema must come from Alembic")

# 8. Required documents -----------------------------------------------------------------
required = [
    "README.md", "LICENSE", ".env.example", "load/k6-script.js",
    "docs/ENGINEERING-NOTES.md", "docs/RUNBOOK.md", "docs/AI-USAGE.md", "docs/TRIAGE.md",
    "docs/adr/0001-provider-interface.md", "docs/adr/0002-frontend-runtime-config.md",
    "docs/adr/0003-deploy-by-sha.md", "docs/adr/0004-pii-and-data-governance.md",
]
for rel in required:
    if not (ROOT / rel).exists():
        fail(f"missing {rel}")

evidence = ROOT / "docs" / "evidence"
expected_evidence = [
    "branch-protection", "merge-conflict", "red-check", "green-check",
    "hpa-watch", "scaling-chart", "vpa", "ping-fails",
]
for stem in expected_evidence:
    if not any(p.name.startswith(stem) for p in evidence.glob("*")):
        warn(f"docs/evidence/ has no '{stem}*' file yet")

for doc in sorted((ROOT / "docs").rglob("*.md")):
    if "[FILL IN" in doc.read_text(encoding="utf-8"):
        warn(f"{doc.relative_to(ROOT)} still has [FILL IN] placeholders")

# 9. Collaboration -----------------------------------------------------------------------
shortlog = git("shortlog", "-sn", "--no-merges", "HEAD")
counts = [int(line.split()[0]) for line in shortlog.splitlines() if line.strip()]
if counts:
    total = sum(counts)
    if total < 35:
        warn(f"only {total} non-merge commits (need >= 35)")
    if len(counts) >= 2 and min(counts[:2]) / total < 0.35:
        warn(f"commit split below 35% for one partner: {shortlog.strip()}")

# --------------------------------------------------------------------------------------
for w in warnings:
    print(f"WARN  {w}")
for p in problems:
    print(f"FAIL  {p}")
if problems:
    print(f"\n{len(problems)} problem(s) found.")
    sys.exit(1)
print(f"\nClean: no automatic-deduction problems found ({len(warnings)} warning(s)).")
