# Error analysis and eval design

Method: the original evals skills from github.com/ai-evals-course/evals-skills (evals-start routing, then error-discovery, generate-synthetic-data, write-code-eval). No real traces existed, so evals-start routes to generate-synthetic-data first, then error-discovery on the traces it produced.

## 1. Synthetic data (generate-synthetic-data)
Dimensions picked where failure was expected:
- Input form: NACHA addenda record (type 99 return, type 98 NOC) or free-text bank notice
- Code: R01 R02 R03 R04 R05 R07 R08 R09 R10 R11 R16 R20 R29, C01 C02 C03 C05 C06 C07, plus codes outside the runbook
- Ledger state: clean match, trace typo, already processed, already retried, amount differs, NOC data bad or already on file

Tuples are in `scripts/gen_data.py`. Labels come from scenario intent in that file, not from the agent. Free-text notices use a separate second step (`scripts/gen_notices.py`): an LLM writes each notice from its tuple, a filter rejects any notice that names the code, quotes the official title, or drops the trace.

## 2. First traces and failure modes (error-discovery)
v0 (`scripts/v0_naive.py`) mapped code to action with no ledger. Reviewing its 56 dev traces gave these failure modes, each now a category and a check:

| Failure mode seen in v0 | Category | Check |
|---|---|---|
| R10 retried like R01 | unauthorized_never_retry | never_retry_unauthorized |
| R01 retried forever | retry_limit | action_correct |
| Same return handled twice | duplicate | action_correct |
| Typo trace still acted on | unmatched_trace | action_correct |
| Partial return amount ignored | amount_mismatch | action_correct |
| Unknown C13 treated as an update | unknown_code | action_correct |
| NOC routing with bad checksum applied | malformed_noc | action_correct |
| NOC equal to file still applied | noc_noop | action_correct |
| Free-text notice not read at all | messy_notice, messy_hard | action_correct, noc_fields |
| Action with no written reason | all | reason_present |
| Full account number in a draft | all | pii_masked |
| Change made with no approval | all | approval_gate |

The review was done by me, not by an outside human annotator. That is the weakest step here.

## 3. Splits
- dev (56): used to build and tune rules, keywords and the LLM prompt.
- held-out (56): same tuple design, different seed and different notice styles. Hash frozen in `evals/HELDOUT.sha256` before tuning; the eval refuses to run if it changes. Caveat: I saw the held-out notice text once while checking generation quality, before tuning.
- stress (16): added after tuning, never used to tune. Notices carry a misleading, ruled-out reason ("not a closed account", "first thought it was fraud").

## 4. Checks (write-code-eval)
All checks are code, in `evals/checks.py`. No LLM judge is used, so write-judge-prompt and validate-evaluator were not needed. A case passes only if every check passes. Safety failures (a retry on an unauthorized code, or a change without approval) fail CI at any count.
