# Eval Set — Current Status

## Scope & Knowledge Base Grounding
Full 10/10 intent coverage with authoritative knowledge base documents authored and indexed in pgvector:
- 9 real Bitext intents (account/access/feedback/contact categories):
  - `recover_password` (`data/kb/account/recover_password.md`)
  - `create_account` (`data/kb/account/create_account.md`)
  - `delete_account` (`data/kb/account/delete_account.md` — policy denylist)
  - `edit_account` (`data/kb/account/edit_account.md`)
  - `switch_account` (`data/kb/account/switch_account.md`)
  - `registration_problems` (`data/kb/account/registration_problems.md`)
  - `contact_human_agent` (`data/kb/contact/contact_human_agent.md`)
  - `contact_customer_service` (`data/kb/contact/contact_customer_service.md`)
  - `complaint` (`data/kb/feedback/complaint.md` — policy denylist)
- 1 author-curated intent:
  - `infrastructure_issue` (`data/kb/infrastructure/troubleshooting.md` + Kubernetes/Docker/AWS docs)

## Three-way Split (Disjoint Sets)
1. `backend/app/agents/few_shot_examples.py` — 12 rows, used inside the classifier prompt.
2. `backend/tests/fixtures/classifier_holdout.csv` — 12 rows, used only by Story C3's unit test.
3. `docs/eval_set.csv` — 52 rows, golden eval set used by Epic H CI gate.

## Golden Eval Set Expansion (FR9)
- Expanded `docs/eval_set.csv` to 52 rows across all 10 intent classes.
- Verified against CI gate thresholds: accuracy ≥ 75%, wrongly auto-resolved ≤ 5%.
