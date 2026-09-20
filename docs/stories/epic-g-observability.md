# Epic G — Observability
- [x] G1: Langfuse tracing wired into every LLM call and agent step (session propagation, metadata, inputs/outputs).
- [x] G2: Real cost calculation per call based on published standard rates per 1K tokens for Groq (Llama 3.3 70B) and Gemini 1.5/3.6 Flash, labeled as "estimated at standard pricing". Aggregated in GET /metrics/summary and dashboard provider breakdown.
- [x] Async Worker: ARQ task queue worker offloading LangGraph pipeline from POST /tickets, with frontend polling and concurrent eval support.