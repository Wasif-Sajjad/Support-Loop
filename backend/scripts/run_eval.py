"""Epic H2 — runs the pipeline against docs/eval_set.csv and scores it.
Run: python scripts/run_eval.py
This is what Epic H3's GitHub Actions gate calls.
"""
import asyncio
import csv
import subprocess
import sys

from app.db import AsyncSessionLocal
from app.llm.base import get_provider
from app.config import settings
from app.agents.graph import build_graph
from app.models import EvalRun


async def main():
    llm = get_provider(settings.llm_provider)

    rows = []
    with open("docs/eval_set.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("docs/eval_set.csv is empty — add at least 50 hand-labeled rows (see docs/prd.md FR9).")
        sys.exit(1)

    correct_decisions = 0
    wrongly_auto_resolved = 0

    async with AsyncSessionLocal() as db:
        graph = build_graph(db, llm)
        for row in rows:
            result = await graph.ainvoke({"ticket_text": row["ticket_text"]})
            decision = result.get("decision")
            correct_decision = row["correct_decision"]

            if decision == correct_decision:
                correct_decisions += 1
            if decision == "auto_resolve" and correct_decision == "escalate":
                wrongly_auto_resolved += 1

        accuracy = correct_decisions / len(rows)
        wrongly_rate = wrongly_auto_resolved / len(rows)

        try:
            git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
        except Exception:
            git_sha = "unknown"

        passed = accuracy >= 0.75 and wrongly_rate <= 0.05  # tune against docs/brief.md targets

        db.add(EvalRun(git_sha=git_sha, accuracy=accuracy, wrongly_auto_resolved_rate=wrongly_rate,
                        passed=passed))
        await db.commit()

    print(f"Accuracy: {accuracy:.2%} | Wrongly auto-resolved: {wrongly_rate:.2%} | Passed: {passed}")
    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
