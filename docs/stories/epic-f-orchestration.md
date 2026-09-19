# Epic F — Orchestration

## Status: ✅ Complete

### Stories

- [x] **F1 — LangGraph state machine**
  Full async pipeline: `classify → cache_check → retrieve → draft → critic`.
  Every node captures latency. `PipelineState` is fully typed.
  Conditional edge after `cache_check` short-circuits to `END` on a cache hit.

- [x] **F2 — Semantic cache (Phase 1)**
  On cache **hit**: skips retriever + drafter + critic entirely, returns cached answer.
  On cache **miss**: runs full pipeline, then writes result to Redis on `auto_resolve`.
  Current implementation uses exact-hash (SHA-256 of lowercased ticket text).
  ⚠ **Backlog (F2 Phase 2)**: upgrade to embedding-cosine-similarity lookup so
  semantically identical but textually different tickets also hit the cache.
  Requires storing `(embedding_vector, payload)` pairs in Redis and a k-NN scan.

- [x] **F3 — Trace persistence**
  Four `AgentTrace` rows written per ticket (classifier, retriever, drafter, critic)
  in a single batch commit. All inputs/outputs/latencies stored as JSONB.
  `GET /tickets/{id}/trace` reconstructs and returns the full `TicketTrace`.

### New API endpoints
| Method | Path | Purpose |
|---|---|---|
| `POST` | `/tickets` | Submit ticket → run pipeline → persist result |
| `GET` | `/tickets/{id}/trace` | Full E4 reasoning trace for a ticket |
| `GET` | `/tickets/{id}` | Ticket record |
| `GET` | `/tickets?decision=escalated` | Escalation queue |

### Open Backlog Items

1. **F2 Phase 2** — True embedding-similarity cache (Redis + k-NN).
2. **Background task queue** — Currently the pipeline runs synchronously in the
   HTTP request. For production, move to a Celery/ARQ background task so the
   POST `/tickets` returns immediately with `status: received`.
3. **Retry + fallback** — If the primary LLM provider (Groq) returns a 429,
   automatically retry with the configured fallback (Gemini/Cerebras).
   Add a retry wrapper in `app/llm/base.py::get_provider`.
4. **Entailment trace storage** — `EntailmentStepTrace` items are assembled in
   memory but not persisted per-step to DB. Store them in a separate
   `entailment_traces` table or as a JSONB column on `agent_traces`.