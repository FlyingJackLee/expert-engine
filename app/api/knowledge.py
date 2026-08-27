from fastapi import APIRouter

from app.knowledge.postgres import PostgresKnowledgeRepository
from app.schemas.domain import KnowledgeDocumentInput

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


@router.post("/documents", status_code=201)
def ingest_document(document: KnowledgeDocumentInput) -> dict[str, str]:
    """Validate and persist one source document with its evidence chunks."""
    PostgresKnowledgeRepository().ingest(document.model_dump())
    return {"document_id": document.document_id, "status": "ingested"}
