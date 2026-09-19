# Epic D — Drafting Agent
- D1: Pydantic schema: {answer: str, cited_chunk_ids: list[UUID], confidence: float}.
- D2: Drafting prompt that forces citation of specific chunk IDs, forbids answering beyond retrieved content.
- D3: Handle the empty-retrieval case (force abstain).