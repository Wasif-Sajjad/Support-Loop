from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models import EvalCase, EvalRun

router = APIRouter(prefix="/eval", tags=["eval"])


@router.post("/run")
async def run_eval(db: AsyncSession = Depends(get_db)):
    """Triggers the golden-set eval. Starter stub — the real scoring loop lives in
    scripts/run_eval.py (Epic H2) so it can also be invoked from CI without an HTTP round trip.
    """
    result = await db.execute(select(EvalCase))
    cases = result.scalars().all()
    return {"message": "Use scripts/run_eval.py for the full scoring loop.", "eval_case_count": len(cases)}


@router.get("/runs")
async def list_eval_runs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EvalRun).order_by(EvalRun.created_at.desc()).limit(20))
    return result.scalars().all()
