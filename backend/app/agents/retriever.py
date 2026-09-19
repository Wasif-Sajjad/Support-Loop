"""Epic B — retrieves top-k relevant KB chunks for a ticket via pgvector similarity search.

Retrieval strategy:
  1. If category_hint is provided, try a filtered cosine search first (faster, more precise).
  2. If the filtered search returns no results (e.g. category_hint doesn't match any chunk's
     category_hint column), fall back to an unfiltered full-KB search.
     This handles the case where seed_kb.py didn't set category_hint on seeded chunks
     (all current chunks have category_hint=NULL — see Epic B backlog for tagging story).
"""
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sentence_transformers import SentenceTransformer

from app.models import KBChunk
from app.schemas import RetrievedChunk
from app.config import settings

_embedder: SentenceTransformer | None = None


def get_embedder() -> SentenceTransformer:
    """Return the singleton SentenceTransformer embedder (lazy-loaded)."""
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(settings.embedding_model_name)
    return _embedder


async def retrieve_kb(
    db: AsyncSession,
    query_text: str,
    category_hint: str | None = None,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Retrieve the top-k most relevant KB chunks for a query via cosine similarity.

    Args:
        db: Async SQLAlchemy session.
        query_text: The raw ticket text used as the embedding query.
        category_hint: Optional category label to narrow the search. If provided,
            a filtered search runs first. If it returns no results, an unfiltered
            search is run as a fallback (so category_hint is best-effort, not strict).
        top_k: Number of chunks to return.

    Returns:
        A list of RetrievedChunk ordered by similarity descending (most similar first).
        May be empty if the KB has no indexed content.
    """
    embedder = get_embedder()
    query_embedding = embedder.encode(query_text).tolist()

    base_stmt = (
        select(KBChunk, KBChunk.embedding.cosine_distance(query_embedding).label("distance"))
        .order_by(text("distance"))
        .limit(top_k)
    )

    # Attempt 1: filtered by category_hint (best-effort).
    if category_hint:
        filtered_stmt = base_stmt.filter(KBChunk.category_hint == category_hint)
        result = await db.execute(filtered_stmt)
        rows = result.all()
        if rows:
            return [
                RetrievedChunk(chunk_id=chunk.id, content=chunk.content, similarity=1 - distance)
                for chunk, distance in rows
            ]
        # Fall through to unfiltered search if category hint matched nothing.

    # Attempt 2: unfiltered full-KB search.
    result = await db.execute(base_stmt)
    rows = result.all()
    return [
        RetrievedChunk(chunk_id=chunk.id, content=chunk.content, similarity=1 - distance)
        for chunk, distance in rows
    ]
