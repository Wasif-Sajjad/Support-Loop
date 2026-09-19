# Epic D — Drafting Agent

## Status: ✅ Implementation Complete — Integration Tests Pending

### Stories
- [x] **D1**: Pydantic schema `{answer, cited_chunk_ids: list[UUID], confidence}` enforced via
  `DraftResolution` in `app/schemas.py`. All three fields are Pydantic-validated before the
  result is returned.
- [x] **D2**: System prompt in `drafter.py` explicitly forbids answering beyond retrieved content,
  requires citing bracketed chunk IDs, and instructs the LLM to return `confidence=0.0` and
  empty fields if the excerpts don't cover the question.
- [x] **D3**: Empty-retrieval fast-path returns `DraftResolution(answer="", cited_chunk_ids=[], confidence=0.0)`
  immediately, without making an LLM call. Also filters chunks below `MIN_SIMILARITY_THRESHOLD=0.30`.

### Tests (`backend/tests/test_drafter.py`)
- [x] `test_d3_abstain_on_empty_chunks` — pure unit test, no LLM
- [x] `test_d3_abstain_on_below_threshold_chunks` — pure unit test, no LLM
- [ ] `test_d2_grounded_answer_recover_password` — integration (run with `INTEGRATION=1`)
- [ ] `test_d2_grounded_answer_contact_customer_service` — integration (run with `INTEGRATION=1`)
- [ ] `test_d2_abstain_for_no_kb_content_intent` — integration (run with `INTEGRATION=1`)

### Open Backlog Items
- See Epic B for KB source gaps (6 remaining account intents need articles).
- Integration tests require `docker compose up` + `seed_kb.py` to have run first.