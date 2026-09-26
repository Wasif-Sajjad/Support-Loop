"""Epic H2 — runs the pipeline against docs/eval_set.csv and scores it.

Run:  python scripts/run_eval.py
This is what Epic H3's GitHub Actions gate calls.

Recalculated Pacing & Batched Execution (2026-09-22):
  - Real observed average: ~3,402 tokens/ticket (retrieved KB chunks + audit prompt).
  - Binding constraint: TPM = 8,000 on Groq free tier.
  - Safe throughput at 80% ceiling: ~1.9 tickets/minute (~30s-32s floor per ticket).
  - Executed in two batches of 27 tickets each (54 rows total).
  - Per-batch timeout: 16 minutes (comfortably above ~13.5 min expected per batch).
  - Pause between batches to allow sliding rate windows to reset.
  - Combined scoring and resolution-rate breakdown (safe escalations vs wrongly auto-resolved).
"""
import asyncio
import csv
import os
import subprocess
import sys
import time

# Ensure backend root is on sys.path when run inside the container
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from sqlalchemy import select, func
from app.db import AsyncSessionLocal
from app.models import Ticket, AgentTrace, EvalRun
from app.worker import process_ticket_job

# Pacing parameters based on observed 3,402 tokens/ticket and 8,000 TPM limit
INTERVAL_FLOOR_S = 32.0       # ~1.9 tickets/min at 80% ceiling (enforces TPM safety under 8,000)
BATCH_SIZE = 27               # 54 total rows divided into 2 batches of 27
INTER_BATCH_PAUSE_S = 20.0    # 20s cooldown between batches
BATCH_TIMEOUT_S = 16 * 60     # 16 minutes safety timeout per batch
PER_TICKET_TIMEOUT_S = 60     # 60s max execution per ticket
HIGH_TOKEN_THRESHOLD = 4500   # warn if a single ticket exceeds 4.5k tokens


async def _process_one(tid: str, index: int, total: int) -> str | None:
    """Process a single ticket with a per-ticket timeout."""
    try:
        await asyncio.wait_for(
            process_ticket_job({}, tid),
            timeout=PER_TICKET_TIMEOUT_S,
        )
        return tid
    except asyncio.TimeoutError:
        print(
            f"  [{index}/{total}] TIMEOUT after {PER_TICKET_TIMEOUT_S}s — ticket {tid} skipped.",
            flush=True,
        )
        return None
    except Exception as e:
        print(
            f"  [{index}/{total}] ERROR — ticket {tid}: {type(e).__name__}: {e}",
            flush=True,
        )
        return None


async def _score_and_persist(
    db,
    ticket_ids: list,
    id_to_row: dict,
    completed_ids: set,
    rows: list,
    total_elapsed: float,
    timed_out: bool,
) -> None:
    """Fetch results, score across all 54 rows, persist EvalRun, and print detailed breakdown."""
    db.expire_all()
    stmt = select(Ticket).where(Ticket.id.in_(ticket_ids))
    res = await db.execute(stmt)
    current_tickets = {str(ct.id): ct for ct in res.scalars().all()}

    total_rows = len(rows)
    correct_decisions = 0
    correct_auto_resolve = 0
    correct_escalate = 0
    safe_escalate = 0            # expected auto_resolve -> got escalate (conservative)
    wrongly_auto_resolved = 0    # expected escalate     -> got auto_resolve (safety miss)
    unscored = 0

    for tid_str in [str(t) for t in ticket_ids]:
        expected = id_to_row[tid_str]["correct_decision"]
        ct = current_tickets.get(tid_str)
        if ct is None or ct.decision is None or tid_str not in completed_ids:
            unscored += 1
            continue

        got = ct.decision
        if got == expected:
            correct_decisions += 1
            if got == "auto_resolve":
                correct_auto_resolve += 1
            else:
                correct_escalate += 1
        elif got == "escalate" and expected == "auto_resolve":
            safe_escalate += 1
        elif got == "auto_resolve" and expected == "escalate":
            wrongly_auto_resolved += 1

    accuracy = correct_decisions / total_rows
    wrongly_rate = wrongly_auto_resolved / total_rows

    # Calculate token & cost stats from AgentTrace
    trace_stmt = select(
        func.sum(AgentTrace.cost_usd),
        func.sum(AgentTrace.latency_ms),
    ).where(AgentTrace.ticket_id.in_(ticket_ids)).group_by(AgentTrace.ticket_id)
    trace_res = await db.execute(trace_stmt)
    ticket_traces = trace_res.all()

    avg_cost = (
        sum(r[0] or 0.0 for r in ticket_traces) / len(ticket_traces)
        if ticket_traces
        else 0.0
    )
    avg_latency = (
        int(sum(r[1] or 0 for r in ticket_traces) / len(ticket_traces))
        if ticket_traces
        else 0
    )

    try:
        git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    except Exception:
        git_sha = "unknown"

    prd_passed = accuracy >= 0.75 and wrongly_rate <= 0.05

    eval_run = EvalRun(
        git_sha=git_sha,
        accuracy=accuracy,
        wrongly_auto_resolved_rate=wrongly_rate,
        avg_cost_usd=round(avg_cost, 6),
        avg_latency_ms=avg_latency,
        passed=prd_passed,
    )
    db.add(eval_run)
    await db.commit()

    # --- Print Structured Evaluation Report ---
    sep = "=" * 62
    print(f"\n{sep}", flush=True)
    print("FINAL EVALUATION REPORT — 54 ROWS (2 BATCHES)", flush=True)
    print(sep, flush=True)
    if timed_out:
        print("⚠  EVAL ABORTED — one or more batches reached the safety timeout.", flush=True)
    print(f"Total Elapsed Time    : {total_elapsed:.1f}s ({total_elapsed / 60:.1f} min)", flush=True)
    print(f"Tickets Scored        : {total_rows - unscored}/{total_rows} ({unscored} unscored)", flush=True)
    print(f"Combined Accuracy     : {accuracy:.2%}  (PRD target ≥ 75.0%)", flush=True)
    print(f"Wrongly Auto-Resolved : {wrongly_rate:.2%}  (PRD target ≤ 5.0%)", flush=True)
    print(f"Avg Cost per Ticket   : ${avg_cost:.6f} (estimated standard pricing)", flush=True)
    print(f"Avg Latency per Ticket: {avg_latency}ms", flush=True)
    print(f"PRD Gate Passed       : {'PASSED ✓' if prd_passed else 'FAILED ✗'}", flush=True)

    print(f"\n--- Resolution Breakdown ---", flush=True)
    print(f"  • Correct Auto-Resolutions : {correct_auto_resolve:2d} (expected auto_resolve -> got auto_resolve)", flush=True)
    print(f"  • Correct Escalations      : {correct_escalate:2d} (expected escalate     -> got escalate)", flush=True)
    print(f"  • Safe Escalations (Costly): {safe_escalate:2d} (expected auto_resolve -> got escalate [safe/conservative])", flush=True)
    print(f"  • Wrongly Auto-Resolved    : {wrongly_auto_resolved:2d} (expected escalate     -> got auto_resolve [SAFETY MISS])", flush=True)
    if unscored:
        print(f"  • Unscored / Timed Out     : {unscored:2d}", flush=True)
    print(sep, flush=True)

    if not prd_passed:
        print(
            "\n✗ One or more PRD targets MISSED — stopping before any doc updates.",
            flush=True,
        )
        sys.exit(1)


async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Run eval pipeline on docs/eval_set.csv")
    parser.add_argument("--batch", type=int, default=0, help="Run specific batch (e.g. 1 or 2). Default 0 runs all batches.")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help=f"Tickets per batch (default: {BATCH_SIZE})")
    args = parser.parse_args()

    rows: list[dict] = []
    with open("docs/eval_set.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("docs/eval_set.csv is empty — please provide eval rows.")
        sys.exit(1)

    total_tickets = len(rows)
    cur_batch_size = args.batch_size
    batch_count = (total_tickets + cur_batch_size - 1) // cur_batch_size
    batches_to_run = [args.batch - 1] if args.batch > 0 else list(range(batch_count))

    expected_batch_minutes = (cur_batch_size * INTERVAL_FLOOR_S) / 60.0
    total_expected_minutes = (len(batches_to_run) * cur_batch_size * INTERVAL_FLOOR_S + max(0, len(batches_to_run) - 1) * INTER_BATCH_PAUSE_S) / 60.0

    print(f"\n{'='*62}", flush=True)
    if args.batch > 0:
        print(f"EVALUATION RUN — Batch {args.batch}/{batch_count} ({cur_batch_size} rows)", flush=True)
    else:
        print(f"FULL EVALUATION RUN — {total_tickets} rows in {batch_count} Batches", flush=True)
    print(f"{'='*62}", flush=True)
    print(f"Binding constraint   : TPM = 8,000 (observed ~3,402 tokens/ticket)", flush=True)
    print(f"Recalculated Pacing  : ~{60.0 / INTERVAL_FLOOR_S:.1f} tickets/min ({INTERVAL_FLOOR_S:.0f}s floor between starts)", flush=True)
    print(f"Per-batch size       : {cur_batch_size} tickets (Batch timeout: {BATCH_TIMEOUT_S // 60} min)", flush=True)
    print(f"Expected per-batch   : {expected_batch_minutes:.1f} minutes (~{cur_batch_size * INTERVAL_FLOOR_S:.0f}s)", flush=True)
    print(f"Total expected run   : {total_expected_minutes:.1f} minutes (~{total_expected_minutes * 60:.0f}s)\n", flush=True)

    t_global_start = time.monotonic()
    timed_out = False
    cumulative_tokens = 0

    async with AsyncSessionLocal() as db:
        # 1. Create all tickets upfront in DB
        tickets: list[Ticket] = []
        for row in rows:
            t = Ticket(raw_text=row["ticket_text"], channel="eval", status="received")
            db.add(t)
            tickets.append(t)
        await db.commit()
        for t in tickets:
            await db.refresh(t)

        ticket_ids = [t.id for t in tickets]
        id_to_row = {str(t.id): r for t, r in zip(tickets, rows)}
        completed_ids: set[str] = set()

        # 2. Process selected batches
        for b_run_idx, b_idx in enumerate(batches_to_run):
            start_idx = b_idx * cur_batch_size
            end_idx = min(start_idx + cur_batch_size, total_tickets)
            batch_slice = ticket_ids[start_idx:end_idx]

            print(f"\n--- Starting Batch {b_idx + 1}/{batch_count} (Tickets {start_idx + 1} to {end_idx}) ---", flush=True)
            t_batch_start = time.monotonic()

            for offset, tid in enumerate(batch_slice):
                global_num = start_idx + offset + 1
                elapsed_batch = time.monotonic() - t_batch_start
                if elapsed_batch >= BATCH_TIMEOUT_S:
                    print(
                        f"\n⚠ Hard timeout reached for Batch {b_idx + 1} after {elapsed_batch:.0f}s at ticket {global_num}.",
                        flush=True,
                    )
                    timed_out = True
                    break

                ticket_start = time.monotonic()
                row = id_to_row[str(tid)]
                result = await _process_one(str(tid), global_num, total_tickets)
                if result is not None:
                    completed_ids.add(result)

                # Query token usage for this ticket from agent_traces
                token_stmt = select(
                    func.sum(func.coalesce(AgentTrace.tokens_in, 0) + func.coalesce(AgentTrace.tokens_out, 0))
                ).where(AgentTrace.ticket_id == tid)
                ticket_tokens = (await db.execute(token_stmt)).scalar() or 0
                cumulative_tokens += ticket_tokens

                if ticket_tokens > HIGH_TOKEN_THRESHOLD:
                    print(
                        f"  ⚠ WARNING: Ticket {global_num} ({row['correct_intent']}) used {ticket_tokens} tokens "
                        f"(exceeds {HIGH_TOKEN_THRESHOLD} threshold; ~3,400 avg expected)",
                        flush=True,
                    )

                await db.refresh(tickets[global_num - 1])
                got_decision = tickets[global_num - 1].decision or "NONE"
                match_mark = "✓" if got_decision == row["correct_decision"] else "✗"

                print(
                    f"  [{global_num:2d}/{total_tickets}] {row['correct_intent']:24s} | "
                    f"expected={row['correct_decision']:12s} got={got_decision:12s} {match_mark} | "
                    f"tokens={ticket_tokens:4d} | elapsed={time.monotonic() - t_global_start:.0f}s",
                    flush=True,
                )

                if global_num % 5 == 0 or global_num == end_idx:
                    avg_per_ticket = cumulative_tokens / global_num
                    print(
                        f"  ── Progress [{global_num:2d}/{total_tickets}]: cumulative_tokens={cumulative_tokens:,} "
                        f"(avg {avg_per_ticket:.0f}/ticket) | total_elapsed={time.monotonic() - t_global_start:.1f}s",
                        flush=True,
                    )

                # Enforce pacing floor between ticket starts
                elapsed_this_ticket = time.monotonic() - ticket_start
                sleep_needed = max(0.0, INTERVAL_FLOOR_S - elapsed_this_ticket)
                if sleep_needed > 0 and global_num < total_tickets:
                    await asyncio.sleep(sleep_needed)

            if timed_out:
                break

            # Pause between batches if more batches remain
            if b_idx < batch_count - 1:
                print(f"\nPausing {INTER_BATCH_PAUSE_S:.0f}s between batches for rate-limit cooldown...", flush=True)
                await asyncio.sleep(INTER_BATCH_PAUSE_S)

        # 3. Clean up redis pool
        try:
            from app.cache import get_redis
            r = get_redis()
            await r.aclose()
        except Exception:
            pass

        # 4. Score and persist final results
        total_elapsed = time.monotonic() - t_global_start
        if args.batch > 0:
            target_indices = [i for b in batches_to_run for i in range(b * cur_batch_size, min((b + 1) * cur_batch_size, total_tickets))]
            eval_ticket_ids = [ticket_ids[i] for i in target_indices]
            eval_rows = [rows[i] for i in target_indices]
        else:
            eval_ticket_ids = ticket_ids
            eval_rows = rows

        await _score_and_persist(
            db, eval_ticket_ids, id_to_row, completed_ids, eval_rows, total_elapsed, timed_out
        )


if __name__ == "__main__":
    asyncio.run(main())
