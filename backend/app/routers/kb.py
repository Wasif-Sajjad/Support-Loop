from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db import get_db
from app.models import KBChunk

router = APIRouter(prefix="/kb", tags=["kb"])


@router.get("/documents")
async def list_kb_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(KBChunk.source, func.count(KBChunk.id)).group_by(KBChunk.source))
    return [{"source": source, "chunk_count": count} for source, count in result.all()]


@router.post("/ingest")
async def trigger_ingest():
    """Stub — real ingestion logic lives in scripts/seed_kb.py (Epic B1/B2)."""
    return {"message": "Run `python scripts/seed_kb.py` to (re)ingest the knowledge base."}
