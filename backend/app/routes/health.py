"""/health, /ready and /metrics.

/health = liveness. "Is the process alive?" It touches NOTHING external. If it
checked the database, a slow database would make Kubernetes restart every
backend pod at once - a restart loop across the whole deployment.

/ready = readiness. "Should this pod receive traffic?" 200 only if Postgres AND
Redis answer; otherwise 503 naming what failed, and Kubernetes removes the pod
from the Service endpoints (without restarting it) until it recovers.
"""

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.services.health_service import HealthService

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(request: Request) -> JSONResponse:
    service = HealthService(request.app.state.session_factory, request.app.state.cache)
    failed = service.failed_dependencies()
    if failed:
        return JSONResponse(status_code=503, content={"status": "not ready", "failed": failed})
    return JSONResponse(status_code=200, content={"status": "ready"})


@router.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
