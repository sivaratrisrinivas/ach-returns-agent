# ACH returns and NOC agent

A payment ops analyst opens the returns file every morning. Each R01, R10 or C02 means finding the original debit in the ledger, checking the runbook, then retrying, blocking or fixing the account. Most of that is lookup work. The risky part is the few cases that look routine but are not: an unauthorized R10 that must never be retried, a second return for the same debit, a trace number with one digit swapped.

This agent does the lookup and the runbook, drafts the action with a reason, and stops for a person before anything moves money or changes account details.

**Live demo:** https://sivaratrisrinivas.github.io/ach-returns-agent/ · **Video (83 s):** [demo.mp4](https://sivaratrisrinivas.github.io/ach-returns-agent/demo.mp4)

## How it works
1. Parse the NACHA return (addenda 99) or notice of change (addenda 98). Free-text bank notices go to an LLM reader.
2. Match the original trace to the ledger. No exact match: escalate. Never guess.
3. Apply [RUNBOOK.md](RUNBOOK.md): retry once, update account details, block, or escalate.
4. Retry, block and update wait for approval. Logs and drafts show only the last 4 digits.

Rules decide every action. The LLM (Groq, `openai/gpt-oss-120b`, free tier) only reads messy text into a code and a trace. Its output then goes through the same runbook, ledger match and checksum checks.

## Eval: 128 pass or fail cases
| | dev (56) | held-out (56) | stress (16) |
|---|---|---|---|
| Strict rules | 44 | 44 | 2 |
| Rules + keywords (tuned on dev) | 56 | 55 | 13 |
| Rules + LLM reader | 56 | 56 | 16 |

Structured cases (return codes, NOC codes, unauthorized never retry, retry limit, duplicates, unmatched trace, amount mismatch, unknown code, bad NOC data, NOC already on file): 41 of 41 in every mode on every split. Free-text notices are where the modes differ. Safety failures are zero everywhere, and every keyword miss was a safe escalation, not a wrong action. CI runs the full eval on each push (LLM answers replayed from a recorded cache). Per-category detail: `evals/last_run.txt`. Method: [ERROR_ANALYSIS.md](ERROR_ANALYSIS.md), following the ai-evals-course evals-skills steps evals-start, generate-synthetic-data, error-discovery and write-code-eval. No LLM judge, so write-judge-prompt and validate-evaluator were not needed.

## ROI
Monthly savings = returns per month x minutes saved per return x analyst cost per minute.
- Returns per month: 2,000 (assumption)
- Minutes saved per return: 7 (assumption, the input to confirm first)
- Loaded analyst cost: $60 per hour, $1 per minute (assumption)

2,000 x 7 x $1 = **$14,000 per month**, before counting avoided R10 retries.

## Run it
`python evals/run.py` (no install needed). Regenerate data: `python scripts/gen_data.py && python scripts/gen_notices.py`.

All data is synthetic. Code meanings are from public NACHA references (Nacha Return Reason Code Guide summaries, Modern Treasury, Huntington and U.S. Bank developer docs). Built by Srinivas as a work sample.
