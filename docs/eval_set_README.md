# Eval Set — Current Status

## Scope (Epic C decision)
10 intents, chosen so every intent has real KB coverage:
- 9 real Bitext intents (account/access category): recover_password, create_account,
  delete_account, edit_account, switch_account, registration_problems,
  contact_human_agent, contact_customer_service, complaint
- 1 author-curated intent: infrastructure_issue (Bitext has no infra/technical
  category — these examples are hand-written, not sourced from the dataset,
  and are clearly marked as such in few_shot_examples.py)

## Three-way split (do not let these overlap)
1. `backend/app/agents/few_shot_examples.py` — 12 rows, used inside the classifier prompt
2. `backend/tests/fixtures/classifier_holdout.csv` — 12 rows, used only by Story C3's unit test
3. `docs/eval_set.csv` — 13 rows, used by the Epic H CI gate

## KNOWN GAP — scale up before relying on the CI gate
13 rows in the golden eval set is enough to prove the pipeline and CI wiring work,
but far short of the 50+ row target in docs/prd.md FR9. This environment doesn't
have access to huggingface.co, so these rows were built from a small manually-provided
sample rather than the full dataset (Bitext has ~1,000 examples per intent available).

**To close this gap:** run `datasets.load_dataset("bitext/Bitext-customer-support-llm-chatbot-training-dataset")`
locally, filter to the 9 intents listed above, sample ~15-20 additional rows per intent
(non-overlapping with the rows already in all three files here), replace any
`{{Entity}}`-style placeholders with concrete values, and add `correct_decision`/`notes`
using the policy already established in `docs/eval_set.csv` as your template. Write
15-20 more `infrastructure_issue` examples yourself in the same style, since no dataset
covers that category.
