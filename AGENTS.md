# AGENTS.md — Standing instructions for AI coding agents on this project

## Project
AI-powered IT/customer support ticket triage & resolution agent.
See docs/brief.md, docs/prd.md, docs/architecture.md for full context before starting any story.

## Code style
- Python: PEP 8, type hints required on every function signature, docstrings (Google style) on public functions.
- TypeScript: strict mode on, no `any` unless justified with a comment.
- Every new backend function that isn't a trivial passthrough needs a pytest test.

## Architecture rules
- All LLM calls MUST go through the `LLMProvider` interface in `backend/app/llm/base.py` — never call a provider SDK directly from agent/route code.
- All LLM-facing structured output MUST be a Pydantic model — never accept raw free text as a final agent output.
- No agent step may write directly to the database without going through `app/db.py` session handling.
- Keep the eval set (`docs/eval_set.csv`) as ground truth — no agent may edit it to make a change "pass."

## Cost constraint
- This project targets $0/month. Do not introduce a dependency that requires a paid tier unless explicitly asked.

## Security
- Never commit secrets. All config comes from environment variables via `.env` (see `.env.example`).
- Validate all external input with Pydantic before it reaches an LLM prompt.

## Workflow
- One story at a time (see docs/prd.md Epics + the project's story backlog).
- Write/update tests alongside implementation, not after.
- Do not mark a story complete until `docker compose up` boots cleanly and relevant tests pass.
