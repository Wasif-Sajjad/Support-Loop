"""Epic B1/B2 — ingest KB documents from data/kb/, chunk, embed, load into pgvector.

Run inside Docker:  docker compose exec backend python scripts/seed_kb.py
Run locally:        python scripts/seed_kb.py  (from backend/ dir, with .env loaded)

Intent coverage for ingestion (10 intents):
  ACCOUNT / CONTACT / FEEDBACK intents (9 Bitext intents):
    recover_password, create_account, delete_account, edit_account, switch_account,
    registration_problems, contact_human_agent, contact_customer_service, complaint
    ⚠ SOURCE GAP: No widely available open-source dataset covers plain help-center
    prose for these account/contact intents. Until real docs are sourced or authored,
    place hand-written KB articles as .md files under data/kb/account/ and
    data/kb/contact/ and data/kb/feedback/. Follow the style in the existing
    infrastructure articles as a template.

  INFRA intent (1 author-curated intent):
    infrastructure_issue
    ✅ Sources: Kubernetes docs (kubernetes.io/docs), Docker troubleshooting docs,
    AWS troubleshooting guides. Clone/scrape and place under data/kb/infrastructure/.

Expected directory layout under data/kb/:
  data/kb/account/          → help-center-style articles for account intents
  data/kb/contact/          → FAQ pages: hours, channels, escalation policy
  data/kb/feedback/         → complaint handling policy (used to explain escalation)
  data/kb/infrastructure/   → K8s, Docker, AWS troubleshooting guides

Files outside these directories will still be ingested but are not part of the
intentional scope — remove them or add a new intent before seeding.
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

# KB subdirectories that correspond to our 10 supported intents.
# Ingestion is scoped to these directories to prevent irrelevant content
# from polluting the retriever's search space.
SCOPED_KB_DIRS = [
    "data/kb/account",
    "data/kb/contact",
    "data/kb/feedback",
    "data/kb/infrastructure",
]


def chunk_text(content: str) -> list[str]:
    """Split a document into overlapping fixed-size chunks.

    Args:
        content: The full document text to chunk.

    Returns:
        A list of non-empty text chunks of up to CHUNK_SIZE characters,
        overlapping by CHUNK_OVERLAP characters.
    """
    chunks: list[str] = []
    start = 0
    while start < len(content):
        end = start + CHUNK_SIZE
        chunks.append(content[start:end])
        start = end - CHUNK_OVERLAP
    return [c for c in chunks if c.strip()]


async def main() -> None:
    """Create DB tables, embed KB chunks, and upsert them into pgvector."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    embedder = SentenceTransformer(settings.embedding_model_name)

    # Collect only files under the scoped KB directories.
    all_files: list[str] = []
    for kb_dir in SCOPED_KB_DIRS:
        all_files.extend(glob.glob(f"{kb_dir}/**/*.md", recursive=True))
        all_files.extend(glob.glob(f"{kb_dir}/**/*.txt", recursive=True))

    if not all_files:
        print(
            "⚠ No files found in scoped KB directories. Nothing was seeded.\n"
            "Add .md or .txt documents to:\n"
            + "\n".join(f"  {d}/" for d in SCOPED_KB_DIRS)
            + "\nSee scripts/seed_kb.py module docstring for sourcing guidance."
        )
        return

    print(f"Found {len(all_files)} file(s) to ingest.")

    async with AsyncSessionLocal() as db:
        for filepath in all_files:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            # Derive source tag from the scoped subdirectory name (e.g. "infrastructure").
            parts = filepath.replace("\\", "/").split("/")
            source = parts[2] if len(parts) > 2 else "unknown"
            for chunk in chunk_text(content):
                embedding = embedder.encode(chunk).tolist()
                db.add(
                    KBChunk(
                        id=uuid.uuid4(),
                        source=source,
                        source_url=filepath,
                        content=chunk,
                        embedding=embedding,
                    )
                )
            print(f"  ✓ Ingested {filepath}")
        await db.commit()

    print("Done — KB seeding complete.")


if __name__ == "__main__":
    asyncio.run(main())

