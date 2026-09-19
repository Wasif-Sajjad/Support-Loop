# Epic F — Orchestration
- F1: LangGraph state machine wiring classifier -> retriever -> drafter -> critic.
- F2: Semantic cache check/write around the retriever+drafter steps (Redis, embedding-similarity match).
- F3: Persist every step to gent_traces.