from fastapi import FastAPI

from app.api.knowledge import router as knowledge_router
from app.api.runs import router as runs_router
from app.config import LOG_LEVEL
from app.observability import configure_logging

configure_logging(LOG_LEVEL)
app = FastAPI(title="Expert Engine", version="0.1.0")
app.include_router(runs_router)
app.include_router(knowledge_router)


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    """Return a minimal liveness response for deployment probes."""
    return {"status": "ok"}
