# Ticket Triage & Resolution Agent

An AI agent that classifies incoming support tickets, retrieves grounded answers from a
knowledge base, drafts a structured resolution, and decides whether to auto-resolve or
escalate to a human — with full tracing and a golden-set evaluation suite.

Full design docs: `docs/brief.md`, `docs/prd.md`, `docs/architecture.md`.

## Stack
- Backend: FastAPI (Python 3.11), LangGraph, SQLAlchemy, Pydantic v2
- Frontend: Next.js 14 (App Router), TypeScript, Tailwind
- Database: PostgreSQL 16 + pgvector
- Cache: Redis 7
- LLM: Groq (primary, free) / Gemini (fallback, free) / Ollama (local, free)
- Tracing: Langfuse (self-hosted, optional — see docker-compose.yml)

## Quick start

```bash
cp .env.example .env
# fill in GROQ_API_KEY (free at console.groq.com) and/or GEMINI_API_KEY (free at aistudio.google.com)

docker compose up --build
```

- Backend: http://localhost:8000 (docs at /docs)
- Frontend: http://localhost:3000

Then seed the knowledge base and run the eval suite:

```bash
docker compose exec backend python scripts/seed_kb.py
docker compose exec backend python scripts/run_eval.py
```

## Project structure

```
backend/         FastAPI app, agents, LLM adapters, scripts, tests
frontend/        Next.js app (submit ticket, escalation queue, dashboard)
data/kb/         Raw knowledge-base source documents
docs/            Brief, PRD, architecture, golden eval set
.github/         CI: eval-gate workflow
```

## Status
Starter skeleton — see AGENTS.md and docs/prd.md Epics A–J for the build order.
