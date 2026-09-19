# Golden Eval Set

`eval_set.csv` currently has 4 placeholder rows so the pipeline/CI wiring can be
tested end-to-end. Per docs/prd.md FR9, you need 50+ hand-labeled rows before this
is a meaningful regression suite — sample from the Bitext dataset and add synthetic
technical tickets matched to your KB topics, including edge cases (near-duplicate
phrasing, policy-denylist intents, no-KB-coverage questions).
