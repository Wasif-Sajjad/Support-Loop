# Project 1 — Ticket Triage & Resolution Agent
### Full BMAD-Method Project Package (Brief → PRD → Architecture → Epics/Stories)
### Zero-cost stack: Next.js + FastAPI + Postgres + Redis + free-tier LLMs

> This document follows the **BMAD Method** (Breakthrough Method for Agile AI-Driven Development) structure: **Analyst → PM → Architect → Scrum Master** artifacts, each a durable, versioned Markdown artifact you can commit to the repo (`docs/brief.md`, `docs/prd.md`, `docs/architecture.md`, `docs/epics/*`). Everything below is written so you can literally split it into those files.

---

## Part 0 — How to use this with BMAD

If you're running BMAD agents (in an IDE, Claude Code, or the BMAD web bundles), feed each part of this document to the matching agent as its seed input instead of starting from a blank page:

| BMAD Agent | Feed it | Produces |
|---|---|---|
| **Analyst** | Part 1 (Project Brief) | Refined `project-brief.md` |
| **PM** | Part 1 + Part 2 (PRD) | `prd.md` with FRs/NFRs, epics |
| **Architect** | Part 2 + Part 3 (Architecture) | `architecture.md`, component diagrams |
| **Product Owner** | `prd.md` + `architecture.md` | Sharded, aligned docs |
| **Scrum Master** | Sharded docs | Story files in `docs/stories/*.md` |
| **Dev** | One story at a time | Code |
| **QA** | Story + code | Gate pass/fail against the golden eval set |

Keep the **golden eval set** (Part 6) as the one artifact every agent must respect — it's your ground truth, not something any agent is allowed to "improve" quietly.

---

## Part 1 — Project Brief (Analyst phase)

### Problem statement
First-line IT/customer support triage is repetitive but risky to automate naively: an LLM that confidently answers a question it doesn't actually know the answer to is worse than no automation, because it erodes trust and can cause real damage (e.g., wrong instructions on account deletion or billing). The problem isn't "can an LLM answer support questions" — it's **can a system reliably tell the difference between a question it can safely answer and one it should hand to a human**, and prove that judgment with evidence.

### Target outcome
A deployed, monitored service that:
1. Classifies an incoming ticket's intent (27 categories, Bitext taxonomy).
2. Retrieves grounding evidence from a real technical knowledge base (Ubuntu/AWS/Kubernetes docs).
3. Drafts a structured, cited answer.
4. Critiques its own answer and decides **auto-resolve vs. escalate**, using both a confidence signal and hard policy rules (e.g., never auto-resolve anything touching PII, payment, or account deletion).
5. Is measurable: resolution rate, escalation rate, wrongly-auto-resolved rate, cost/ticket, latency — tracked on a dashboard, tested by a CI regression suite.

### Why it matters (portfolio framing)
This demonstrates the actual differentiator between a toy LLM demo and production agent engineering: grounding, structured output, self-critique/guardrails, observability, and a regression suite that catches silent quality regressions — the same shape of problem as Intercom Fin, Zendesk AI, or an internal support copilot.

### Constraints for this build
- **Budget: $0.** Every paid AWS/Azure service named in the original spec must have a free-tier or self-hosted substitute.
- **Solo developer**, portfolio timeline (target: 4–6 weeks part-time).
- Must produce a **quotable metric** at the end (e.g., "78% correct auto-resolve/escalate decisions on a 50-ticket held-out set, $0.0009/ticket, p50 latency 2.1s").
- This project is Project 1 of a 3-project chain — Project 2 replaces the zero-shot classifier with a fine-tuned model trained partly on this project's outputs; Project 3 reuses this project's router/cache/tracing patterns. Keep interfaces (especially the classifier's input/output contract and the eval set format) stable so Projects 2–3 can plug in without rework.

### Out of scope (v1)
- Multi-turn conversational support (v1 is single-ticket-in, single-answer-out).
- Multi-tenant auth/billing.
- Non-English tickets.
- Voice/phone channel.

### Success metrics
| Metric | Target |
|---|---|
| Correct auto-resolve/escalate decision (vs. hand-labeled eval set) | ≥ 75% |
| Wrongly auto-resolved rate (auto-resolved but should've escalated) | ≤ 5% — this is the number that matters most |
| Cost per ticket | < $0.002 using free-tier LLMs, effectively $0 |
| p50 end-to-end latency | < 5s |
| CI eval suite | Runs on every push, blocks merge on regression |

---

## Part 2 — Product Requirements Document (PM phase)

### 2.1 Users & context
Single persona: an internal support-ops user who receives either (a) an auto-resolved answer sent to the customer, or (b) an escalation packet handed to a human agent with the full reasoning trace attached so they don't start from zero.

### 2.2 Functional Requirements (FR)

- **FR1**: System accepts a raw ticket (free text) via API and assigns a UUID and `received` status, persisted durably.
- **FR2**: System classifies the ticket into one of the 27 Bitext intents + parent category, with a confidence score, using an LLM prompted few-shot from labeled examples (no fine-tuning in v1 — that's Project 2).
- **FR3**: System retrieves top-k relevant passages from a vector store built from the knowledge base (Ubuntu Server docs, AWS troubleshooting docs, Kubernetes docs), scoped/boosted by the classified intent/category.
- **FR4**: Before retrieval, system checks a semantic cache (embedding-similarity, not exact-string) for a near-identical previously-answered question; on hit, reuse the cached answer and skip LLM calls for that step.
- **FR5**: System drafts an answer strictly as structured output (Pydantic-validated JSON: `answer`, `cited_chunks[]`, `confidence`) — never accepts free-text as the final draft.
- **FR6**: System runs an escalation critic that checks: (a) do citations actually support the claims in the answer (semantic entailment check, not just cosine similarity), (b) is confidence above a tunable threshold, (c) does the ticket match a **hard policy denylist** (PII change, payment, account deletion, security/credentials) that forces escalation regardless of confidence.
- **FR7**: System outputs a final decision: `auto_resolved` (with answer) or `escalated` (with full reasoning trace: classification, retrieved chunks, draft, critic verdict).
- **FR8**: Every agent step (classifier, retriever, drafter, critic) is traced with input, output, token count, latency, and cost.
- **FR9**: A golden eval set of ≥50 hand-labeled tickets (correct intent + correct auto-resolve/escalate decision) is run automatically in CI on every push; CI fails the build if aggregate accuracy drops below a set floor vs. the last known-good baseline.
- **FR10**: A dashboard shows resolution rate, escalation rate, wrongly-auto-resolved rate, cost/ticket, and latency, filterable by time window.
- **FR11**: A minimal frontend lets a human (a) submit a test ticket and see the full pipeline trace, (b) browse a queue of escalated tickets and their reasoning trace, (c) view the metrics dashboard.

### 2.3 Non-Functional Requirements (NFR)

- **NFR1 — Cost**: Entire stack must run at $0 using free tiers / self-hosting on a single small VM or local Docker Compose.
- **NFR2 — Reproducibility**: Full stack must come up with `docker compose up` and a documented `.env`.
- **NFR3 — Observability**: No agent step is a black box; every LLM call must be traced (inputs, outputs, tokens, cost, latency).
- **NFR4 — Determinism of grounding**: The drafting agent must not answer without citations when the retriever found nothing relevant — it must explicitly abstain/escalate instead of hallucinating.
- **NFR5 — Latency**: p50 < 5s per ticket end-to-end (acceptable for async support workflows, not live chat).
- **NFR6 — Portability**: LLM provider must be swappable via config (env var + adapter pattern), since free-tier providers rate-limit or change catalogs without notice (this happened repeatedly through 2026 — see Part 5).
- **NFR7 — Security**: No secrets in code; structured-output validation rejects anything that doesn't match the Pydantic schema, closing the door on prompt-injected free-text escaping into a customer-facing answer.

### 2.4 Epics (high level — detailed stories in Part 7)

1. **Epic A — Infra Skeleton**: Docker Compose, Postgres, Redis, FastAPI shell, Next.js shell, CI pipeline skeleton.
2. **Epic B — Knowledge Base & Retrieval**: Scrape/compile docs, chunk, embed, load into vector store, build retriever agent.
3. **Epic C — Classifier Agent**: Bitext-grounded few-shot intent classifier with confidence.
4. **Epic D — Drafting Agent & Structured Output**: Pydantic-schema-enforced answer drafting with citations.
5. **Epic E — Escalation Critic & Guardrails**: Entailment check, confidence threshold, policy denylist.
6. **Epic F — Orchestration (LangGraph)**: Wire agents into a stateful graph with the semantic cache short-circuit.
7. **Epic G — Observability**: Tracing (Langfuse self-host or free tier), structured logs, cost/latency capture.
8. **Epic H — Golden Eval Set & CI Gate**: Hand-labeled 50-ticket set, eval runner, GitHub Actions gate.
9. **Epic I — Frontend**: Next.js ticket submitter, trace viewer, escalation queue, metrics dashboard.
10. **Epic J — Deployment**: Free-tier deployment (Fly.io/Render/Railway/self-host), documented runbook, README/postmortem writeup.

---

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
 │              │ │  OpenRouter) │ │  free tier)   │
 └─────────────┘ └─────────────┘ └──────────────┘
```

### 3.2 Complete tech stack

| Layer | Original (paid AWS) spec | This build (free-tier / self-hosted) |
|---|---|---|
| Frontend | — (not specified) | **Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui**, deployed free on Vercel or Netlify |
| Backend API | FastAPI | **FastAPI + Pydantic v2 + Uvicorn** |
| Agent orchestration | LangGraph | **LangGraph** (unchanged — it's free/open-source) |
| Ticket state DB | DynamoDB | **PostgreSQL 16** (Docker locally; free-tier Supabase or Neon in prod) |
| Vector store | (implied, unspecified) | **pgvector extension on the same Postgres** (avoids running a second DB) — or **Chroma** (embedded, file-based, zero infra) as a simpler alternative |
| Cache | ElastiCache (Redis) | **Redis** via Docker locally; free-tier **Upstash Redis** in prod (serverless, generous free quota) |
| KB document storage | S3 | **Local filesystem in repo `/data/kb/`** for dev; free-tier **Cloudflare R2** (10GB free, S3-compatible API) if you want cloud storage |
| Infra as code | Terraform (AWS) | **Docker Compose** for local/dev; optional minimal **Terraform for Fly.io/Render** if you want IaC on your resume — same *concept*, zero cost target |
| Compute / deploy | ECS Fargate | **Fly.io free allowance**, **Render free web service**, or a **free-tier Oracle Cloud / Google Cloud e2-micro VM** running Docker Compose |
| LLM (classifier, drafter, critic) | Not specified (implied paid) | **Groq (Llama 3.3 70B / gpt-oss-120b, free, very fast)** as primary; **Google Gemini Flash (free tier, 1M context)** as fallback/secondary; **Ollama running a local small model (Llama 3.2 3B / Qwen2.5 3B)** as a zero-network fallback for offline dev/testing |
| Embeddings | Not specified | **`sentence-transformers/all-MiniLM-L6-v2`** (free, local, no API calls) via `sentence-transformers`, or **Gemini's free embedding endpoint** if you want to stay API-based |
| Tracing / observability | Langfuse | **Langfuse** — self-host via their free Docker Compose image, or use their generous cloud free tier |
| CI/CD | GitHub Actions | **GitHub Actions** (unchanged — free for public/private repos within limits) |
| Dashboard | CloudWatch | **Grafana** (Docker, free) reading from Postgres, or a simple **Next.js metrics page** reading an API endpoint — simplest path, recommended for v1 |
| Containerization | Docker | **Docker + Docker Compose** (unchanged) |

**Design principle behind every substitution:** keep the *interface* the same as the "real" AWS-shaped version (a repository/adapter pattern for storage, an LLM-provider adapter, a vector-store adapter) so that swapping in AWS later (for a resume line like "designed to be cloud-portable") is a config change, not a rewrite. This is worth stating explicitly in your README — it shows you understand the abstraction, not just the free substitute.

### 3.3 LLM provider adapter (why + how)

Free tiers rate-limit and change model catalogs without warning (documented repeatedly through 2026). Build one `LLMProvider` interface with `.complete(messages, response_schema=None)` and three concrete adapters:

1. `GroqProvider` — default, fastest, generous free RPM on Llama/gpt-oss models.
2. `GeminiProvider` — fallback, huge context window, separate rate-limit pool so you get two independent free quotas.
3. `OllamaProvider` — local, zero network dependency, for offline development and for running the golden eval set without burning API quota.

Route via an env var (`LLM_PROVIDER=groq|gemini|ollama`) and a simple retry-with-fallback wrapper: if the primary 429s, fall back to the secondary automatically. This single design decision is also a strong interview talking point ("designed for multi-provider resilience because free tiers are unreliable by nature").

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
| `POST` | `/tickets` | Submit a raw ticket; kicks off the pipeline (sync for demo, or returns immediately + poll for real async) |
| `GET` | `/tickets/{id}` | Full ticket record + status |
| `GET` | `/tickets/{id}/trace` | Full agent-by-agent reasoning trace |
| `GET` | `/tickets?decision=escalated` | Escalation queue for the frontend |
| `POST` | `/eval/run` | Trigger an eval run against `eval_set` (also called by CI) |
| `GET` | `/eval/runs` | History of eval runs, for the "did this regress" view |
| `GET` | `/metrics/summary` | Aggregate resolution rate, escalation rate, cost/ticket, latency for the dashboard |
| `POST` | `/kb/ingest` | Admin endpoint: re-chunk + re-embed a KB source |

### 3.6 Frontend (Next.js) — do you actually need it?

Yes, but keep it small — three pages:
1. **`/submit`** — textarea to submit a test ticket, streams back the live pipeline trace (classification → retrieval → draft → critic verdict) so you can *show* the reasoning in a demo/interview, not just the final answer.
2. **`/queue`** — table of escalated tickets with their full trace, sortable/filterable — this is literally the "hand off to human" screen a real support-ops tool would have.
3. **`/dashboard`** — the four numbers (resolution rate, escalation rate, wrongly-auto-resolved rate, cost/ticket) as simple charts (Recharts), pulling from `/metrics/summary`.

Stack: Next.js App Router, TypeScript, Tailwind, shadcn/ui components, Recharts for charts, deployed free on Vercel (frontend) talking to your backend wherever it's hosted.

### 3.7 Guardrails, concretely

- **Schema guardrail**: drafting agent's output is validated against a Pydantic model; a validation failure is itself logged and treated as an automatic escalation, never retried into "just try to get valid JSON" loops that could degrade grounding.
- **Entailment guardrail**: the critic re-reads each citation and asks (via a small, cheap LLM call or a local NLI model) "does this passage actually support this claim?" — catches the common RAG failure of citing something merely *topically similar*.
- **Policy denylist guardrail**: regex/keyword + intent-based hard rule — categories like `cancel_order`+billing, anything mentioning SSN/password/payment card, are **always** escalated regardless of confidence. This is a rule, not a model decision — deterministic and auditable.
- **Confidence floor guardrail**: below a tunable threshold (start at 0.7, tune against the eval set), auto-escalate.
- **No-citation guardrail**: if retrieval returns nothing above a similarity floor, the drafter is instructed (and structurally forced via the schema — `cited_chunks` can be empty but then `decision` must be `escalate`) to abstain rather than answer from parametric memory.

---

## Part 4 — Dataset

### Primary dataset (classification)
**Bitext Customer Support LLM Chatbot Training Dataset** — ~27K utterance/intent pairs, 27 intents under broader categories (ORDER, REFUND, ACCOUNT, INVOICE, SHIPPING, SUBSCRIPTION, etc.), with a `flags` field for linguistic variation.
- Hugging Face: `bitext/Bitext-customer-support-llm-chatbot-training-dataset`
- Free, no auth needed, loadable via `datasets.load_dataset(...)`.
- Use for: few-shot examples in the classifier prompt, and as the source pool to hand-craft your 50-ticket golden eval set (sample + lightly rewrite into "incoming ticket" phrasing, then re-verify the label by hand).

### Knowledge base (retrieval/RAG) — all free, public, scrapeable
| Source | Why | Access |
|---|---|---|
| Ubuntu Server Documentation | Real troubleshooting guides for a technical audience | `https://ubuntu.com/server/docs` — static docs, scrape with `requests` + `BeautifulSoup`, respect robots.txt, or use their GitHub-hosted doc source if available |
| AWS Troubleshooting Guides | Common cloud-infra failure modes | AWS public docs (e.g., troubleshooting sections of EC2/S3/IAM docs) — public, no auth |
| Kubernetes Documentation | Crashlooping pods, resource limits, networking — the flagship example in the assignment | `https://kubernetes.io/docs/` — official docs are open-source (Apache 2.0 licensed content in the k8s/website GitHub repo), cleanly scrapeable and even directly cloneable from `github.com/kubernetes/website` |

Practical tip: clone `kubernetes/website`'s markdown source directly from GitHub instead of scraping rendered HTML — it's already clean Markdown, licensed for reuse, and trivially chunkable.

### Golden eval set (you build this by hand)
50+ tickets, each with:
- `ticket_text` (a realistic incoming ticket, some sampled/rewritten from Bitext, some synthetic technical ones you write to match the KB topics)
- `correct_intent`
- `correct_decision` (`auto_resolve` or `escalate`) — deliberately include edge cases: low-confidence-but-correct, high-confidence-but-should-escalate-on-policy, no-KB-coverage cases.

This set is the single most valuable artifact in the whole project — it's what turns "I built an agent" into "I built and *validated* an agent."

---

## Part 5 — Free LLM & infra options (deploy and test at $0)

### LLM inference (pick 2, for primary + fallback)
| Provider | Free tier (subject to change — verify at signup) | Best for |
|---|---|---|
| **Groq** | Fast inference on Llama 3.3 70B, gpt-oss-120b/20b, Qwen3-32B; no card required | Primary — speed matters for the p50<5s NFR |
| **Google AI Studio (Gemini)** | Gemini Flash models free, up to 1M token context, no card required | Fallback + long-context KB retrieval edge cases |
| **OpenRouter** | Multiple free model slots through one key | Quick provider variety without juggling multiple SDKs |
| **Ollama (local)** | 100% free, no network, run Llama 3.2 3B / Qwen2.5 3B on your own machine | Offline dev + running the CI eval suite without burning any API quota |

> Free tiers are rate-limited and their model catalogs change without notice — this is exactly why Part 3.3's provider-adapter pattern exists. Build it from day one, don't bolt it on later.

### Embeddings
- **`sentence-transformers/all-MiniLM-L6-v2`** run locally via the `sentence-transformers` Python package — free, fast, no API calls, 384-dim (matches the `pgvector` schema above).

### Vector store
- **pgvector** (extension on the Postgres you already run) — simplest, one less service to operate.
- Alternative: **Chroma** (embedded, file-based) if you want to decouple vector search from Postgres for the resume line "evaluated multiple vector store options."

### Cache
- **Redis** via Docker locally.
- **Upstash Redis** free tier for a deployed version (serverless, pay-per-request pricing with a real free allowance, works well with serverless/edge deploys).

### Object storage (KB docs)
- Local `/data/kb/` folder in the repo for dev.
- **Cloudflare R2** free tier (10GB, S3-compatible API — so your code literally uses `boto3`, meaning "I used S3" isn't even a stretch) if you want it cloud-hosted.

### Managed Postgres (free tier)
- **Supabase** or **Neon** — both have workable free Postgres tiers with `pgvector` support out of the box.

### Compute / hosting
- **Fly.io** free allowance, or **Render** free web service, for the FastAPI backend + Docker Compose services.
- **Vercel** (free) for the Next.js frontend.
- Fallback: a single **Oracle Cloud Always-Free** or **Google Cloud free-tier e2-micro** VM running the whole `docker compose` stack together — simplest mental model, one machine, everything on it.

### Tracing
- **Langfuse** — self-host their OSS Docker image (genuinely free, unlimited, since it's your own instance) rather than relying on their cloud free-tier quota.

### CI/CD
- **GitHub Actions** — free minutes are ample for a project this size.

---

## Part 6 — Guardrails, evaluation & the CI gate (detail)

### Eval runner logic (pseudocode)
```
for row in eval_set:
    result = run_pipeline(row.ticket_text)
    intent_correct = result.intent == row.correct_intent
    decision_correct = result.decision == row.correct_decision
    wrongly_auto_resolved = (result.decision == "auto_resolve"
                              and row.correct_decision == "escalate")
    record(result, intent_correct, decision_correct, wrongly_auto_resolved)

accuracy = mean(decision_correct)
wrongly_auto_resolved_rate = mean(wrongly_auto_resolved)
write_eval_run(git_sha, accuracy, wrongly_auto_resolved_rate, avg_cost, avg_latency)

# CI gate
if accuracy < baseline_accuracy - 0.05 or wrongly_auto_resolved_rate > 0.05:
    fail_build("Regression: quality dropped below floor")
```

### GitHub Actions sketch
```yaml
name: eval-gate
on: [push, pull_request]
jobs:
  eval:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: ankane/pgvector
        env: { POSTGRES_PASSWORD: postgres }
        ports: ["5432:5432"]
      redis:
        image: redis
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: python scripts/seed_kb.py
      - run: python scripts/run_eval.py --provider ollama   # zero-cost, deterministic-ish CI
      - run: python scripts/check_gate.py
```

Use the **Ollama** provider in CI specifically so your regression suite never depends on a rate-limited free API being available at the moment GitHub Actions happens to run.

---

## Part 7 — Epics → Stories (Scrum Master phase, ready to hand to Dev)

**Epic A — Infra Skeleton**
- A1: Docker Compose with Postgres+pgvector, Redis, FastAPI, Next.js services, all with health checks.
- A2: `.env.example` documenting every required var (LLM keys, DB URL, Redis URL).
- A3: GitHub Actions skeleton that at least lints + boots the compose stack.

**Epic B — Knowledge Base & Retrieval**
- B1: Script to clone/scrape Ubuntu/AWS/K8s docs into `/data/kb/` as clean Markdown/text.
- B2: Chunking script (semantic or fixed-size w/ overlap) + embedding via MiniLM, loaded into `kb_chunks`.
- B3: Retriever agent: given intent/category + ticket text, return top-k chunks with similarity scores.

**Epic C — Classifier Agent**
- C1: Few-shot prompt template built from sampled Bitext examples per intent.
- C2: Classifier agent returns `{intent, category, confidence}` as structured output.
- C3: Unit tests against a held-out slice of Bitext (separate from your 50-ticket eval set).

**Epic D — Drafting Agent**
- D1: Pydantic schema: `{answer: str, cited_chunk_ids: list[UUID], confidence: float}`.
- D2: Drafting prompt that forces citation of specific chunk IDs, forbids answering beyond retrieved content.
- D3: Handle the empty-retrieval case (force abstain).

**Epic E — Escalation Critic & Guardrails**
- E1: Entailment check per citation (cheap LLM call or local NLI).
- E2: Policy denylist (regex/keyword + intent list) — hard override.
- E3: Confidence-threshold logic, tunable via config, tuned against the eval set.
- E4: Final `decision` + human-readable reasoning trace assembly.

**Epic F — Orchestration**
- F1: LangGraph state machine wiring classifier → retriever → drafter → critic.
- F2: Semantic cache check/write around the retriever+drafter steps (Redis, embedding-similarity match).
- F3: Persist every step to `agent_traces`.

**Epic G — Observability**
- G1: Langfuse self-hosted via Docker Compose, wired into every LLM call.
- G2: Cost calculation per call (token counts × provider's published free/paid rate, so the "cost per ticket" number still means something even on free tiers).

**Epic H — Golden Eval Set & CI Gate**
- H1: Hand-label 50+ tickets (sampled from Bitext + synthetic technical ones matched to your KB).
- H2: Eval runner script + `/eval/run` endpoint.
- H3: GitHub Actions gate comparing against last known-good baseline.

**Epic I — Frontend**
- I1: `/submit` page with live trace view.
- I2: `/queue` escalation table.
- I3: `/dashboard` metrics charts.

**Epic J — Deployment & Writeup**
- J1: Deploy backend (Fly.io/Render) + frontend (Vercel) + managed Postgres (Supabase/Neon) + Upstash Redis.
- J2: README with architecture diagram, the quotable metric, and a "tradeoffs" section (e.g., resolution-rate vs. wrongly-auto-resolved-rate curve).
- J3: Postmortem-style writeup: what broke, what you'd change, how Project 2/3 build on this.

---

## Part 8 — Forward compatibility with Projects 2 & 3

- **Project 2** replaces Epic C's classifier with a fine-tuned model. Keep the classifier behind the same interface (`classify(ticket_text) -> {intent, category, confidence}`) so swapping in a LoRA-tuned DistilBERT/Llama endpoint is a one-file change, and reuse this project's 50-ticket eval set (plus your CI gate) unmodified to compare zero-shot vs. fine-tuned head-to-head — that comparison *is* Project 2's headline result.
- **Project 3** reuses this project's semantic-cache pattern and Langfuse tracing wholesale, and extends the LLM-provider adapter (Part 3.3) into a full complexity-based router. Keep the adapter interface stable now so it's a drop-in dependency later rather than a rewrite.

---

## Quick-start checklist

- [ ] `docker compose up` brings up Postgres(+pgvector), Redis, FastAPI, Next.js
- [ ] Groq + Gemini API keys in `.env` (both free, no card)
- [ ] KB ingested (`python scripts/seed_kb.py`)
- [ ] 50-ticket eval set hand-labeled and seeded into `eval_set`
- [ ] `python scripts/run_eval.py` produces an accuracy/cost/latency report
- [ ] GitHub Actions gate green
- [ ] Deployed: Vercel (frontend) + Fly.io/Render (backend) + Supabase/Neon (Postgres) + Upstash (Redis)
- [ ] README has the one quotable sentence: *"X% correct auto-resolve/escalate decisions, Y% wrongly auto-resolved, $Z/ticket, p50 latency Ns — all on free-tier infrastructure."*
