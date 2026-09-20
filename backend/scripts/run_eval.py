"""Epic H2 — runs the pipeline against docs/eval_set.csv and scores it.
Run: python scripts/run_eval.py
This is what Epic H3's GitHub Actions gate calls.
"""
import asyncio
import csv
import subprocess
import sys
import time

from sqlalchemy import select, func
from app.db import AsyncSessionLocal
from app.config import settings
from app.models import Ticket, AgentTrace, EvalRun
from app.worker import get_arq_pool


async def main():
    rows = []
    with open("docs/eval_set.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("docs/eval_set.csv is empty — add at least 50 hand-labeled rows (see docs/prd.md FR9).")
        sys.exit(1)

    print(f"Loaded {len(rows)} eval cases. Enqueuing concurrently to ARQ worker...")
    t0 = time.monotonic()

    async with AsyncSessionLocal() as db:
        # 1. Create all tickets in DB
        tickets = []
        for row in rows:
            t = Ticket(raw_text=row["ticket_text"], channel="eval", status="received")
            db.add(t)
            tickets.append(t)
        await db.commit()
        for t in tickets:
            await db.refresh(t)

        ticket_ids = [t.id for t in tickets]
        id_to_row = {str(t.id): r for t, r in zip(tickets, rows)}

        # 2. Enqueue all jobs concurrently into ARQ
        pool = await get_arq_pool()
        await asyncio.gather(*[
            pool.enqueue_job("process_ticket_job", str(tid)) for tid in ticket_ids
        ])
        print(f"All {len(ticket_ids)} tickets enqueued. Awaiting concurrent execution...")

        # 3. Poll for completion
        completed_tickets = {}
        max_wait_seconds = 180
        poll_start = time.monotonic()

        while len(completed_tickets) < len(ticket_ids):
            if time.monotonic() - poll_start > max_wait_seconds:
                print(f"Timeout waiting for eval tickets ({len(completed_tickets)}/{len(ticket_ids)} completed).")
                break

            db.expire_all()
            stmt = select(Ticket).where(Ticket.id.in_(ticket_ids))
            res = await db.execute(stmt)
            current_tickets = res.scalars().all()

            for ct in current_tickets:
                if ct.status in ("resolved", "escalated", "failed"):
                    completed_tickets[str(ct.id)] = ct

            if len(completed_tickets) < len(ticket_ids):
                await asyncio.sleep(1.0)

        await pool.aclose()
        total_elapsed = time.monotonic() - t0
        print(f"Completed {len(completed_tickets)}/{len(ticket_ids)} tickets in {total_elapsed:.2f}s.")

        # 4. Score results
        correct_decisions = 0
        wrongly_auto_resolved = 0

        for tid_str, ct in completed_tickets.items():
            expected = id_to_row[tid_str]["correct_decision"]
            if ct.decision == expected:
                correct_decisions += 1
            if ct.decision == "auto_resolve" and expected == "escalate":
                wrongly_auto_resolved += 1

        accuracy = correct_decisions / len(rows) if rows else 0.0
        wrongly_rate = wrongly_auto_resolved / len(rows) if rows else 0.0

        # Calculate average cost and latency for this eval run
        trace_stmt = select(
            func.sum(AgentTrace.cost_usd),
            func.sum(AgentTrace.latency_ms)
        ).where(AgentTrace.ticket_id.in_(ticket_ids)).group_by(AgentTrace.ticket_id)
        trace_res = await db.execute(trace_stmt)
        ticket_traces = trace_res.all()

        avg_cost = sum(r[0] or 0.0 for r in ticket_traces) / len(ticket_traces) if ticket_traces else 0.0
        avg_latency = int(sum(r[1] or 0 for r in ticket_traces) / len(ticket_traces)) if ticket_traces else 0

        try:
            git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
        except Exception:
            git_sha = "unknown"

        passed = accuracy >= 0.75 and wrongly_rate <= 0.05

        eval_run = EvalRun(
            git_sha=git_sha,
            accuracy=accuracy,
            wrongly_auto_resolved_rate=wrongly_rate,
            avg_cost_usd=round(avg_cost, 6),
            avg_latency_ms=avg_latency,
            passed=passed,
        )
        db.add(eval_run)
        await db.commit()

    print(f"Accuracy: {accuracy:.2%} | Wrongly auto-resolved: {wrongly_rate:.2%} | Avg Cost: ${avg_cost:.6f} | Passed: {passed}")
    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
