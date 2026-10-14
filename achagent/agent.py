"""ACH returns + NOC agent. Rules first; LLM only to read free-text bank notices."""
import json, re
from .nacha import parse, aba_ok
from .codes import RETURNS, NOCS
from . import llm

MONEY_OR_DETAILS = {"RETRY", "BLOCK", "UPDATE"}
FUNDS = {"R01", "R09"}
BAD_ACCOUNT = {"R02", "R03", "R04", "R20"}
UNAUTHORIZED = {"R05", "R07", "R10", "R11", "R29"}
HUMAN = {"R08": "stop payment needs a human to confirm with the customer",
         "R16": "account frozen or OFAC, route to compliance"}
MAX_RETRIES = 1  # runbook: retry once (Nacha allows up to two reinitiations; this SOP is stricter)

def mask(s):
    return re.sub(r"\d{5,17}", lambda m: "****" + m.group(0)[-4:], s)

# ---------- reading free text ----------
KEYWORDS = [  # tuned on dev notices only
    ("R16", r"ofac|frozen|freeze"), ("R10", r"not authori[sz]ed|unauthori[sz]ed|didn.t (authori|approve)|originator (is )?unknown|(don|doesn).t recogni[sz]e|isn.t (theirs|mine)"),
    ("R07", r"revoked|pulled (back )?(their|the) (authori|permission)"), ("R08", r"stop(ped)? payment|got stopped"),
    ("R02", r"account (is |was |has been )?(now )?closed"), ("R03", r"can.t find|cannot locate|no such account|unable to locate"),
    ("R09", r"uncollected|not collected|funds (weren|were not|aren).t available"), ("R01", r"insufficient|not enough (money|funds)|nsf"),
    ("R04", r"invalid account|account number format"),
]
def trace_from_text(t):
    for m in re.finditer(r"\d[\d \-]{13,22}\d", t):
        d = re.sub(r"\D", "", m.group(0))
        if len(d) == 15: return d
    return None

def _text_fields(t):
    f = {}
    r = re.findall(r"routing\W{0,4}(?:number\W{0,3})?(?:to\W{0,2})?(\d{9})\b", t, re.I)
    a = re.findall(r"acc(?:oun)?t\W{0,4}(?:number\W{0,3})?(?:to\W{0,2})?(\d{6,17})\b", t, re.I)
    if r: f["routing"] = r[-1]
    if a: f["account"] = a[-1]
    return f

def keyword_read(t):
    tl = t.lower()
    f = _text_fields(t)
    if f:  # new numbers in the text means a notice of change
        return "C03" if len(f) == 2 else ("C02" if "routing" in f else "C01")
    for code, pat in KEYWORDS:
        if re.search(pat, tl):
            return code
    return None

LLM_SYS = ("You read ACH notices sent to a fintech payment ops team and map them to exactly one NACHA code. "
           "Return codes: " + "; ".join(f"{k} {v}" for k, v in RETURNS.items()) + ". "
           "Notification of change codes: " + "; ".join(f"{k} {v[0]}" for k, v in NOCS.items()) + ". "
           "If a message gives new routing and/or account numbers, it is a notification of change. "
           "If the code is unclear, use UNKNOWN. Reply only with JSON: "
           '{"code": "...", "trace": "15 digits or null", "routing": "or null", "account": "or null", "txn_code": "or null", "why": "short"}')

def llm_read(t):
    raw = llm.chat(LLM_SYS, mask_for_llm(t))
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}

def mask_for_llm(t):
    # names stay (needed), but nothing else sensitive is in notices; corrected numbers are needed to read the NOC
    return t

# ---------- core ----------
class Agent:
    def __init__(self, ledger, mode="hybrid"):
        self.mode = mode  # "rules", "rules_kw", "hybrid"
        self.cust = {c["id"]: c for c in ledger["customers"]}
        self.by_trace = {e["trace"]: e for e in ledger["ledger"]}

    def decide(self, case):
        log = []
        inp = case["input"]; processed = {tuple(x) for x in case["context"].get("processed_returns", [])}
        src = "rules"
        if inp["kind"] == "addenda":
            p = parse(inp["lines"]); code, trace = p["code"], p["orig_trace"]
            amount = p["amount_cents"]; corrected = p.get("corrected")
            log.append(f"parsed addenda type {p['addenda_type']} code {code} original trace {trace}")
            fields_in = None
        else:
            text = inp["text"]; trace = trace_from_text(text); amount = None; corrected = None; fields_in = {}
            code = None
            if self.mode == "rules_kw":
                code = keyword_read(text); src = "keywords"
            elif self.mode == "hybrid":
                j = llm_read(text); src = "llm"
                code = (j.get("code") or "").upper() or None
                if j.get("trace"):
                    lt = re.sub(r"\D", "", str(j["trace"]))
                    if trace and lt != trace:
                        return self._out("ESCALATE", None, code, "LLM trace disagrees with the trace found in the text", log, src)
                    trace = trace or lt
                fields_in = {k: re.sub(r"\D", "", str(j[k])) for k in ("routing", "account", "txn_code") if j.get(k)}
                log.append(f"LLM read code {code}: {j.get('why','')}")
            if code and code[0] == "C" and self.mode != "hybrid":
                fields_in = self._fields_from_text(text, code)
            if not code or code == "UNKNOWN":
                return self._out("ESCALATE", None, code, "free-text notice with no clear code; a human must read it", log, src)
        e = self.by_trace.get(trace)
        if not e:
            return self._out("ESCALATE", None, code, f"original trace {trace} not found in ledger", log, src)
        c = self.cust[e["customer_id"]]
        log.append(f"matched ledger entry {e['trace']} for {c['name']} acct ****{c['account'][-4:]}")
        if (trace, code) in processed:
            return self._out("NO_ACTION", c, code, "duplicate: this return was already processed", log, src)
        if code in RETURNS:
            if amount is not None and amount != e["amount_cents"]:
                return self._out("ESCALATE", c, code, f"returned amount {amount/100:.2f} differs from ledger {e['amount_cents']/100:.2f}", log, src)
            if code in FUNDS:
                if e["attempts"] - 1 >= MAX_RETRIES:
                    return self._out("ESCALATE", c, code, f"retry limit hit: already retried {e['attempts']-1} time(s)", log, src)
                return self._out("RETRY", c, code, f"{RETURNS[code]}; runbook allows one retry", log, src)
            if code in BAD_ACCOUNT:
                return self._out("BLOCK", c, code, f"{RETURNS[code]}; block debits and request new account details", log, src)
            if code in UNAUTHORIZED:
                return self._out("BLOCK", c, code, f"{RETURNS[code]}; never retry, new authorization required", log, src)
            if code in HUMAN:
                return self._out("ESCALATE", c, code, HUMAN[code], log, src)
        if code in NOCS:
            names = NOCS[code][1]
            fields = fields_in if fields_in is not None else self._noc_fields(code, corrected)
            fields = {k: v for k, v in (fields or {}).items() if k in names}
            if set(fields) != set(names):
                return self._out("ESCALATE", c, code, "corrected data missing or unreadable", log, src)
            if "routing" in fields and not aba_ok(fields["routing"]):
                return self._out("ESCALATE", c, code, "corrected routing number fails the ABA checksum", log, src)
            if "account" in fields and not (fields["account"].isdigit() and 4 <= len(fields["account"]) <= 17):
                return self._out("ESCALATE", c, code, "corrected account number is not valid", log, src)
            if all(c[k] == v for k, v in fields.items()):
                return self._out("NO_ACTION", c, code, "corrected data already matches what is on file", log, src)
            return self._out("UPDATE", c, code, f"{NOCS[code][0]}; update {', '.join(names)} before next entry", log, src, fields)
        return self._out("ESCALATE", c, code, f"code {code} is not in the runbook", log, src)

    def _noc_fields(self, code, cd):
        cd = cd or ""
        if code == "C01": return {"account": cd[:17].strip()}
        if code == "C02": return {"routing": cd[:9].strip()}
        if code == "C03": return {"routing": cd[:9].strip(), "account": cd[12:29].strip()}
        if code == "C05": return {"txn_code": cd[:2].strip()}
        if code == "C06": return {"account": cd[:17].strip(), "txn_code": cd[20:22].strip()}
        if code == "C07": return {"routing": cd[:9].strip(), "account": cd[9:26].strip(), "txn_code": cd[26:28].strip()}

    def _fields_from_text(self, t, code):
        return _text_fields(t)

    def _out(self, action, c, code, reason, log, src, fields=None):
        who = f"{c['name']} (acct ****{c['account'][-4:]})" if c else "unknown customer"
        verb = {"RETRY": "Retry the debit once", "BLOCK": "Block further debits on the account",
                "UPDATE": "Update account details on file", "ESCALATE": "Send to a human analyst",
                "NO_ACTION": "Take no action"}[action]
        draft = f"{verb} for {who}. Code {code or 'n/a'}. Reason: {reason}."
        if fields:
            draft += " New values: " + ", ".join(f"{k} ****{v[-4:]}" if k == "account" else f"{k} {v}" for k, v in fields.items()) + "."
        return {"action": action, "code": code, "fields": fields or {}, "needs_approval": action in MONEY_OR_DETAILS,
                "status": "WAITING_FOR_APPROVAL" if action in MONEY_OR_DETAILS else "DONE",
                "reason": reason, "draft": mask(draft), "log": [mask(x) for x in log], "source": src}
