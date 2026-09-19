"""Few-shot examples for the classifier prompt.

Sources:
- 9 intents (account/access, real Bitext data, entity placeholders resolved to
  concrete values): recover_password, create_account, delete_account, edit_account,
  switch_account, registration_problems, contact_human_agent, contact_customer_service,
  complaint.
- 1 intent (infrastructure_issue) is AUTHOR-CURATED, not from Bitext — Bitext has no
  infra/technical category. Written in a similar noisy, informal style to stay
  consistent with the rest of the prompt.

These rows are disjoint from backend/tests/fixtures/classifier_holdout.csv and from
docs/eval_set.csv — do not add a row here that also appears in either of those files.
"""

FEW_SHOT_EXAMPLES = [
    {"instruction": "want assistance to lodge a complaint against your business",
     "intent": "complaint", "category": "FEEDBACK", "confidence": 0.93},
    {"instruction": "can ya show me at what time customer assistance available is",
     "intent": "contact_customer_service", "category": "CONTACT", "confidence": 0.9},
    {"instruction": "helo to contact an assistant",
     "intent": "contact_human_agent", "category": "CONTACT", "confidence": 0.88},
    {"instruction": "new business acount",
     "intent": "create_account", "category": "ACCOUNT", "confidence": 0.85},
    {"instruction": "remove premium account",
     "intent": "delete_account", "category": "ACCOUNT", "confidence": 0.92},
    {"instruction": "update details on freemium account",
     "intent": "edit_account", "category": "ACCOUNT", "confidence": 0.87},
    {"instruction": "I need to reset my damn PIN code",
     "intent": "recover_password", "category": "ACCOUNT", "confidence": 0.9},
    {"instruction": "where can I report issues with sign-up?",
     "intent": "registration_problems", "category": "ACCOUNT", "confidence": 0.86},
    {"instruction": "I need assistance using the family profile",
     "intent": "switch_account", "category": "ACCOUNT", "confidence": 0.84},
    {"instruction": "my kubernetes pod keeps crashlooping after the last deploy",
     "intent": "infrastructure_issue", "category": "INFRA", "confidence": 0.91},
    {"instruction": "docker container wont start, getting exit code 1",
     "intent": "infrastructure_issue", "category": "INFRA", "confidence": 0.89},
    {"instruction": "ec2 instance is unreachable after a reboot",
     "intent": "infrastructure_issue", "category": "INFRA", "confidence": 0.88},
]
