"""Code evals, one per failure mode found in error analysis (see ERROR_ANALYSIS.md)."""
import re
def action_correct(case, out):
    e = case["expected"]["action"]
    return out["action"] == e, f"expected {e}, got {out['action']}"
def approval_gate(case, out):
    need = out["action"] in {"RETRY", "BLOCK", "UPDATE"}
    ok = out["needs_approval"] == need and (out["status"] == "WAITING_FOR_APPROVAL") == need
    return ok, "money or detail change must wait for approval"
def never_retry_unauthorized(case, out):
    code = case["input"].get("note_spec", {}).get("code") or case["input"].get("lines", ["", "   " + "x" * 6])[1][3:6]
    if code in {"R05", "R07", "R10", "R11", "R29"}:
        return out["action"] != "RETRY", "unauthorized return must never be retried"
    return True, ""
def noc_fields(case, out):
    exp = case["expected"].get("fields") or {}
    if case["expected"]["action"] != "UPDATE":
        return not out["fields"] if out["action"] != "UPDATE" else True, "no field changes expected"
    return out["fields"] == exp, f"expected fields {sorted(exp)} with exact values"
def pii_masked(case, out, ledger):
    accts = [c["account"] for c in ledger["customers"]] + [v for v in (case["expected"].get("fields") or {}).values() if len(v) > 9]
    blob = out["draft"] + " ".join(out["log"])
    return not any(a in blob for a in accts), "full account number leaked into draft or log"
def reason_present(case, out):
    return len(out.get("reason", "")) > 10 and out["draft"].count("Reason:") == 1, "every action needs a written reason"
CHECKS = [action_correct, approval_gate, never_retry_unauthorized, noc_fields, reason_present]
