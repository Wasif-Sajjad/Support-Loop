from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import engine, Base
from app.routers import tickets, eval as eval_router, kb, metrics


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        from sqlalchemy import text
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Ticket Triage & Resolution Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tickets.router)
app.include_router(eval_router.router)
app.include_router(kb.router)
app.include_router(metrics.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
