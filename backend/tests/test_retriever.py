import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db import engine, Base, AsyncSessionLocal
from app.agents.retriever import retrieve_kb
from app.models import KBChunk


@pytest.fixture(scope="module", autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Optionally drop tables after test if desired, but for local dev testing we can leave it

@pytest.mark.asyncio
async def test_retriever():
    async with AsyncSessionLocal() as db:
        # Just verify the function runs without throwing errors and returns a list.
        # We are testing the SQL syntax and embedding integration here.
        query = "How do I fix a CrashLoopBackOff in Kubernetes?"
        results = await retrieve_kb(db, query_text=query, top_k=3)
        
        assert isinstance(results, list)
        # The list could be empty if seed_kb.py hasn't run, but the query itself shouldn't crash
        if len(results) > 0:
            assert hasattr(results[0], "content")
            assert hasattr(results[0], "similarity")
