## Part 3 — Architecture (Architect phase)

### 3.1 High-level architecture

```
                        ┌─────────────────────────┐
                        │   Next.js Frontend       │
                        │  (submit ticket, trace    │
                        │   viewer, escalation      │
                        │   queue, metrics)         │
                        └────────────┬─────────────┘
                                     │ REST / JSON
                                     ▼
                        ┌─────────────────────────┐
                        │   FastAPI Backend         │
                        │  /tickets  /tickets/{id}  │
                        │  /eval     /metrics        │
                        └────────────┬─────────────┘
                                     │
                     ┌───────────────┼────────────────┐
                     ▼               ▼                ▼
             ┌───────────────┐ ┌───────────┐  ┌──────────────┐
             │ LangGraph      │ │ Postgres   │  │ Redis         │
             │ Agent Pipeline │ │ (ticket    │  │ (semantic     │
             │                │ │  state,    │  │  cache +      │
             │ classifier →   │ │  eval      │  │  rate-limit)  │
             │ retriever →    │ │  results)  │  │               │
             │ drafter →      │ └───────────┘  └──────────────┘
             │ critic         │
             └───────┬────────┘
                     │
        ┌────────────┼─────────────────┐
        ▼            ▼                 ▼
 ┌─────────────┐ ┌─────────────┐ ┌──────────────┐
 │ Vector Store │ │ LLM Provider │ │ Langfuse      │
 │ (pgvector /  │ │ (Groq /      │ │ (self-hosted  │
 │  Chroma)     │ │  Gemini /    │ │  or cloud     │
 │              │ │  Cerebras/   │ │  free tier)   │
 │              │ │  CF Workers) │ │               │
 └─────────────┘ └─────────────┘ └──────────────┘
```

### 3.2 Complete tech stack

| Layer | This build (free-tier / self-hosted) |
|---|---|
| Frontend | **Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui**, deployed free on Vercel or Netlify |
| Backend API | **FastAPI + Pydantic v2 + Uvicorn** |
| Agent orchestration | **LangGraph** (free/open-source) |
| Ticket state DB | **PostgreSQL 16** (Docker locally; free-tier Supabase or Neon in prod) |
| Vector store | **pgvector extension on the same Postgres** (avoids running a second DB) — or **Chroma** (embedded, file-based, zero infra) |
| Cache | **Redis** via Docker locally; free-tier **Upstash Redis** in prod (serverless, generous free quota) |
| KB document storage | **Local filesystem in repo `/data/kb/`** for dev; free-tier **Cloudflare R2** (10GB free, S3-compatible API) if you want cloud storage |
| Infra as code | **Docker Compose** for local/dev |
| Compute / deploy | **Render free web service** or a **free-tier Oracle Cloud / Google Cloud e2-micro VM** running Docker Compose |
| LLM (classifier, drafter, critic) | **Groq (Llama 3.3 70B / gpt-oss-120b, free, very fast)** as primary; **Google Gemini Flash (free tier, 1M context)**, **Cerebras**, and **Cloudflare Workers AI** as fallbacks/secondary; **Ollama running a local small model (Llama 3.2 3B / Qwen2.5 3B)** as a zero-network fallback for offline dev/testing |
| Embeddings | **`sentence-transformers/all-MiniLM-L6-v2`** (free, local, no API calls) via `sentence-transformers`, or **Gemini's free embedding endpoint** |
| Tracing / observability | **Langfuse** — self-host via their free Docker Compose image, or use their generous cloud free tier |
| CI/CD | **GitHub Actions** (free for public/private repos within limits) |
| Dashboard | **Grafana** (Docker, free) reading from Postgres, or a simple **Next.js metrics page** reading an API endpoint |
| Containerization | **Docker + Docker Compose** |

### 3.3 LLM provider adapter (why + how)

Free tiers rate-limit and change model catalogs without warning (documented repeatedly through 2026). Build one `LLMProvider` interface with `.complete(messages, response_schema=None)` and concrete adapters:

1. `GroqProvider` — default, fastest, generous free RPM on Llama/gpt-oss models.
2. `GeminiProvider` / `CerebrasProvider` / `CloudflareWorkersAIProvider` — fallbacks, huge context window (for Gemini), separate rate-limit pools.
3. `OllamaProvider` — local, zero network dependency, for offline development and for running the golden eval set without burning API quota.

Route via an env var (`LLM_PROVIDER=groq|gemini|cerebras|cloudflare|ollama`) and a simple retry-with-fallback wrapper.

### 3.4 Data model (PostgreSQL)

```sql
-- tickets: core ticket state (replaces DynamoDB table)
CREATE TABLE tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'received', -- received|classified|retrieved|drafted|resolved
    intent TEXT,
    category TEXT,
    classifier_confidence FLOAT,
    decision TEXT, -- auto_resolved | escalated | null
    final_answer TEXT,
    cited_chunk_ids UUID[],
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- kb_chunks: knowledge base chunks + embeddings (replaces separate vector DB)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE kb_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,        -- 'ubuntu-docs' | 'aws-docs' | 'k8s-docs'
    source_url TEXT,
    category_hint TEXT,          -- loosely maps to Bitext categories for retrieval boosting
    content TEXT NOT NULL,
    embedding VECTOR(384),       -- matches all-MiniLM-L6-v2 dimension
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON kb_chunks USING ivfflat (embedding vector_cosine_ops);

-- agent_traces: every agent step, for observability (mirrors what Langfuse also captures)
CREATE TABLE agent_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID REFERENCES tickets(id),
    agent_name TEXT NOT NULL,   -- classifier|retriever|drafter|critic
    input JSONB,
    output JSONB,
    tokens_in INT,
    tokens_out INT,
    cost_usd NUMERIC(10,6) DEFAULT 0,
    latency_ms INT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- eval_set: golden hand-labeled tickets
CREATE TABLE eval_set (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_text TEXT NOT NULL,
    correct_intent TEXT NOT NULL,
    correct_decision TEXT NOT NULL, -- auto_resolve | escalate
    notes TEXT
);

-- eval_runs: CI run history, for the "regression suite" story
CREATE TABLE eval_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    git_sha TEXT,
    accuracy FLOAT,
    wrongly_auto_resolved_rate FLOAT,
    avg_cost_usd NUMERIC(10,6),
    avg_latency_ms INT,
    passed BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### 3.5 API surface (FastAPI)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/tickets` | Submit a raw ticket; kicks off the pipeline |
| `GET` | `/tickets/{id}` | Full ticket record + status |
| `GET` | `/tickets/{id}/trace` | Full agent-by-agent reasoning trace |
| `GET` | `/tickets?decision=escalated` | Escalation queue for the frontend |
| `POST` | `/eval/run` | Trigger an eval run against `eval_set` (also called by CI) |
| `GET` | `/eval/runs` | History of eval runs, for the "did this regress" view |
| `GET` | `/metrics/summary` | Aggregate resolution rate, escalation rate, cost/ticket, latency |
| `POST` | `/kb/ingest` | Admin endpoint: re-chunk + re-embed a KB source |

### 3.6 Guardrails, concretely

- **Schema guardrail**: drafting agent's output is validated against a Pydantic model.
- **Entailment guardrail**: the critic re-reads each citation and asks "does this passage actually support this claim?"
- **Policy denylist guardrail**: regex/keyword + intent-based hard rule — categories like `cancel_order`+billing always escalated.
- **Confidence floor guardrail**: below a tunable threshold (start at 0.7), auto-escalate.
- **No-citation guardrail**: if retrieval returns nothing, the drafter abstains.
