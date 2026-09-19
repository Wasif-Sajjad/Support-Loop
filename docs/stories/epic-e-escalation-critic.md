# Epic E — Escalation Critic & Guardrails
- E1: Entailment check per citation (cheap LLM call or local NLI).
- E2: Policy denylist (regex/keyword + intent list) — hard override.
- E3: Confidence-threshold logic, tunable via config, tuned against the eval set.
- E4: Final decision + human-readable reasoning trace assembly.