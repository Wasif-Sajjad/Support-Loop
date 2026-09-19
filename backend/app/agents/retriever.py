"""Epic B — retrieves top-k relevant KB chunks for a ticket via pgvector similarity search.
"""
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sentence_transformers import SentenceTransformer

from app.models import KBChunk
from app.schemas import RetrievedChunk
from app.config import settings

_embedder: SentenceTransformer | None = None


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(settings.embedding_model_name)
    return _embedder


async def retrieve_kb(db: AsyncSession, query_text: str, category_hint: str | None = None, top_k: int = 5) -> list[RetrievedChunk]:
    embedder = get_embedder()
    query_embedding = embedder.encode(query_text).tolist()

    stmt = (
        select(KBChunk, KBChunk.embedding.cosine_distance(query_embedding).label("distance"))
        .order_by(text("distance"))
        .limit(top_k)
    )
    if category_hint:
        stmt = stmt.filter(KBChunk.category_hint == category_hint)

    result = await db.execute(stmt)
    rows = result.all()
    return [
        RetrievedChunk(chunk_id=chunk.id, content=chunk.content, similarity=1 - distance)
        for chunk, distance in rows
    ]
