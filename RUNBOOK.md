# ACH returns and NOC runbook (written SOP the agent follows)

1. Match the entry's original trace number to the ledger. No exact match: escalate. Never guess.
2. Same return trace already processed: no action, log as duplicate.
3. Returned amount differs from the ledger: escalate.
4. R01, R09 (funds): retry once. If the entry was already retried, escalate (retry limit hit).
5. R02, R03, R04, R20 (bad or closed account): block the account for debits and ask the customer for new details.
6. R05, R07, R10, R11, R29 (unauthorized or revoked): block the account. Never retry. A new authorization is required.
7. R08 (stop payment), R16 (frozen or OFAC): escalate to a human. R16 goes to compliance.
8. Any code not in this runbook: escalate.
9. NOC C01, C02, C03, C05, C06, C07: update the named fields on file before the next entry.
   Corrected routing numbers must pass the ABA checksum. Bad data: escalate. Data equal to what is on file: no action.
10. Retry, block and update all wait for human approval. Escalate and no action do not.
11. Drafts and logs show only the last 4 digits of any account number.
