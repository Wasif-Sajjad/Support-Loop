"""Epic B1/B2 starter — ingest KB documents from data/kb/, chunk, embed, load into pgvector.
Run: python scripts/seed_kb.py
Currently a stub that ingests any .md/.txt files already placed in data/kb/.
TODO: add the actual scraping/cloning step (e.g. clone kubernetes/website docs) per
docs/architecture.md Part 4.
"""
import asyncio
import glob
import uuid

from sentence_transformers import SentenceTransformer
from sqlalchemy import text

from app.db import AsyncSessionLocal, engine, Base
from app.models import KBChunk
from app.config import settings

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def chunk_text(content: str) -> list[str]:
    chunks = []
    start = 0
    while start < len(content):
        end = start + CHUNK_SIZE
        chunks.append(content[start:end])
        start = end - CHUNK_OVERLAP
    return [c for c in chunks if c.strip()]


async def main():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    embedder = SentenceTransformer(settings.embedding_model_name)
    all_files = glob.glob("data/kb/**/*.md", recursive=True) + glob.glob("data/kb/**/*.txt", recursive=True)
    files = all_files[:50]  # Limit to 50 files for initial testing to avoid multi-hour CPU embeddings

    if not files:
        print("No files found in data/kb/. Add some .md/.txt docs first (see README).")
        return

    async with AsyncSessionLocal() as db:
        for filepath in files:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            source = filepath.split("/")[2] if len(filepath.split("/")) > 2 else "unknown"
            for chunk in chunk_text(content):
                embedding = embedder.encode(chunk).tolist()
                db.add(KBChunk(id=uuid.uuid4(), source=source, source_url=filepath,
                                content=chunk, embedding=embedding))
            print(f"Ingested {filepath}")
        await db.commit()

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
