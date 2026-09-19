## Part 1 — Project Brief (Analyst phase)

### Problem statement
First-line IT/customer support triage is repetitive but risky to automate naively: an LLM that confidently answers a question it doesn't actually know the answer to is worse than no automation, because it erodes trust and can cause real damage (e.g., wrong instructions on account deletion or billing). The problem isn't "can an LLM answer support questions" — it's **can a system reliably tell the difference between a question it can safely answer and one it should hand to a human**, and prove that judgment with evidence.

### Target outcome
A deployed, monitored service that:
1. Classifies an incoming ticket's intent (27 categories, Bitext taxonomy).
2. Retrieves grounding evidence from a real technical knowledge base (Ubuntu/AWS/Kubernetes docs).
3. Drafts a structured, cited answer.
4. Critiques its own answer and decides **auto-resolve vs. escalate**, using both a confidence signal and hard policy rules (e.g., never auto-resolve anything touching PII, payment, or account deletion).
5. Is measurable: resolution rate, escalation rate, wrongly-auto-resolved rate, cost/ticket, latency — tracked on a dashboard, tested by a CI regression suite.

### Why it matters (portfolio framing)
This demonstrates the actual differentiator between a toy LLM demo and production agent engineering: grounding, structured output, self-critique/guardrails, observability, and a regression suite that catches silent quality regressions — the same shape of problem as Intercom Fin, Zendesk AI, or an internal support copilot.

### Constraints for this build
- **Budget: $0.** Every paid AWS/Azure service named in the original spec must have a free-tier or self-hosted substitute.
- **Solo developer**, portfolio timeline (target: 4–6 weeks part-time).
- Must produce a **quotable metric** at the end (e.g., "78% correct auto-resolve/escalate decisions on a 50-ticket held-out set, $0.0009/ticket, p50 latency 2.1s").
- This project is Project 1 of a 3-project chain — Project 2 replaces the zero-shot classifier with a fine-tuned model trained partly on this project's outputs; Project 3 reuses this project's router/cache/tracing patterns. Keep interfaces (especially the classifier's input/output contract and the eval set format) stable so Projects 2–3 can plug in without rework.

### Out of scope (v1)
- Multi-turn conversational support (v1 is single-ticket-in, single-answer-out).
- Multi-tenant auth/billing.
- Non-English tickets.
- Voice/phone channel.

### Success metrics
| Metric | Target |
|---|---|
| Correct auto-resolve/escalate decision (vs. hand-labeled eval set) | ≥ 75% |
| Wrongly auto-resolved rate (auto-resolved but should've escalated) | ≤ 5% — this is the number that matters most |
| Cost per ticket | < $0.002 using free-tier LLMs, effectively $0 |
| p50 end-to-end latency | < 5s |
| CI eval suite | Runs on every push, blocks merge on regression |
