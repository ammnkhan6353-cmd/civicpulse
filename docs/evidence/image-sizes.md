# Image and build-context sizes

| Image | Final size | Build stage (not shipped) |
|---|---|---|
| civicpulse-backend | [FILL IN] MB | builder (python:3.12-slim + wheels): [FILL IN] MB |
| civicpulse-frontend | [FILL IN] MB (target < 60 MB) | build (node:22-alpine + node_modules): [FILL IN] MB |

| Build context | Without `.dockerignore` | With `.dockerignore` |
|---|---|---|
| backend/ | [FILL IN] | [FILL IN] |
| frontend/ | [FILL IN] (node_modules!) | [FILL IN] |

Commands used are in the team playbook, "Evidence: image sizes".
