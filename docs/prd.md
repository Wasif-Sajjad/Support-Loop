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
- **NFR6 — Portability**: LLM provider must be swappable via config (env var + adapter pattern), since free-tier providers rate-limit or change catalogs without notice (this happened repeatedly through 2026).
- **NFR7 — Security**: No secrets in code; structured-output validation rejects anything that doesn't match the Pydantic schema, closing the door on prompt-injected free-text escaping into a customer-facing answer.

### 2.4 Epics
1. **Epic A — Infra Skeleton**: Docker Compose, Postgres, Redis, FastAPI shell, Next.js shell, CI pipeline skeleton.
2. **Epic B — Knowledge Base & Retrieval**: Scrape/compile docs, chunk, embed, load into vector store, build retriever agent.
3. **Epic C — Classifier Agent**: Bitext-grounded few-shot intent classifier with confidence.
4. **Epic D — Drafting Agent & Structured Output**: Pydantic-schema-enforced answer drafting with citations.
5. **Epic E — Escalation Critic & Guardrails**: Entailment check, confidence threshold, policy denylist.
6. **Epic F — Orchestration (LangGraph)**: Wire agents into a stateful graph with the semantic cache short-circuit.
7. **Epic G — Observability**: Tracing (Langfuse self-host or free tier), structured logs, cost/latency capture.
8. **Epic H — Golden Eval Set & CI Gate**: Hand-labeled 50-ticket set, eval runner, GitHub Actions gate.
9. **Epic I — Frontend**: Next.js ticket submitter, trace viewer, escalation queue, metrics dashboard.
10. **Epic J — Deployment**: Free-tier deployment (Render/self-host), documented runbook, README/postmortem writeup.
