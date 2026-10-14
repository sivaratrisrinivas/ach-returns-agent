"""Generate synthetic ledger + eval cases. Labels come from scenario intent (a table
in this file), not from the agent code. Messy bank notices are written by an LLM in a
separate step (scripts/gen_notices.py) per the two-step synthetic-data method."""
import json, random, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from achagent.nacha import aba_make, entry6, addenda99, addenda98

ODFI8 = "09100001"
FIRST = "Ava Ben Cara Dev Eli Fay Gus Hana Ivan Jo Kai Lena Mo Nia Omar Pia Quinn Ravi Sana Tao".split()
LAST = "Patel Ruiz Chen Okafor Smith Haddad Kim Novak Silva Ito".split()
CORP = ["Harbor Freight Co", "Blue Fern LLC", "Northwind Supply", "Kestrel Labs Inc", "Maple Dental PC", "Orbit Logistics"]

def build(split, seed):
    rnd = random.Random(seed)
    customers, ledger, cases = [], [], []
    def new_customer(corporate=False):
        cid = f"{split[0].upper()}C{len(customers)+1:03d}"
        c = {"id": cid, "name": rnd.choice(CORP) if corporate else f"{rnd.choice(FIRST)} {rnd.choice(LAST)}",
             "type": "corporate" if corporate else "consumer",
             "routing": aba_make(f"{rnd.randint(1,12):02d}{rnd.randint(0,999999):06d}"),
             "account": str(rnd.randint(10**9, 10**12)), "txn_code": "27", "status": "active"}
        customers.append(c); return c
    def new_entry(c, attempts=1):
        t = ODFI8 + f"{len(ledger)+1:07d}"
        e = {"trace": t, "customer_id": c["id"], "amount_cents": rnd.randint(500, 250000),
             "sec": "CCD" if c["type"] == "corporate" else rnd.choice(["PPD", "WEB"]),
             "attempts": attempts, "date": f"2026-10-{rnd.randint(1,12):02d}"}
        ledger.append(e); return e
    rt = [0]
    def ret_trace():
        rt[0] += 1; return "07100002" + f"{rt[0]:07d}"
    def ret_lines(c, e, code, orig=None, amount=None):
        return [entry6("26", c["routing"], c["account"], amount or e["amount_cents"], c["id"], c["name"], ret_trace()),
                addenda99(code, orig or e["trace"], c["routing"][:8], "", ret_trace())]
    def noc_lines(c, e, code, corrected):
        return [entry6("21", c["routing"], c["account"], 0, c["id"], c["name"], ret_trace()),
                addenda98(code, e["trace"], c["routing"][:8], corrected, ret_trace())]
    def add(cat, lines, exp, ctx=None, note=None):
        cases.append({"id": f"{split}-{len(cases)+1:03d}", "split": split, "category": cat,
                      "input": {"kind": "addenda", "lines": lines} if lines else {"kind": "notice", "note_spec": note},
                      "context": ctx or {"processed_returns": []}, "expected": exp})
    A = lambda act, fields=None: {"action": act, "fields": fields or {}}
    code_act = {"R01": "RETRY", "R09": "RETRY", "R02": "BLOCK", "R03": "BLOCK", "R04": "BLOCK", "R20": "BLOCK",
                "R05": "BLOCK", "R07": "BLOCK", "R10": "BLOCK", "R11": "BLOCK", "R29": "BLOCK",
                "R08": "ESCALATE", "R16": "ESCALATE"}
    for code, act in code_act.items():
        c = new_customer(corporate=code == "R29"); e = new_entry(c)
        add("return_code", ret_lines(c, e, code), A(act))
    def corrected_for(code, c):
        r = aba_make(f"{rnd.randint(1,12):02d}{rnd.randint(0,999999):06d}"); a = str(rnd.randint(10**9, 10**12))
        t = "37" if code in ("C05", "C06", "C07") else None
        m = {"C01": (a, {"account": a}), "C02": (r, {"routing": r}), "C03": (r + "   " + a, {"routing": r, "account": a}),
             "C05": ("37", {"txn_code": "37"}), "C06": (a.ljust(17) + "   37", {"account": a, "txn_code": "37"}),
             "C07": (r + a.ljust(17) + "37", {"routing": r, "account": a, "txn_code": "37"})}
        return m[code]
    for code in ["C01", "C02", "C03", "C05", "C06", "C07"]:
        c = new_customer(); e = new_entry(c); corr, f = corrected_for(code, c)
        add("noc_code", noc_lines(c, e, code, corr), A("UPDATE", f))
    for code in (["R10", "R10", "R07", "R05"] if split == "dev" else ["R10", "R10", "R11", "R29"]):
        c = new_customer(corporate=code == "R29"); e = new_entry(c, attempts=1)
        e["amount_cents"] = rnd.randint(100, 900)  # small, looks harmless to retry
        add("unauthorized_never_retry", ret_lines(c, e, code), A("BLOCK"))
    for code in ["R01", "R09", "R01"]:
        c = new_customer(); e = new_entry(c, attempts=2)
        add("retry_limit", ret_lines(c, e, code), A("ESCALATE"))
    for code in ["R01", "R03", "R10"]:
        c = new_customer(); e = new_entry(c)
        add("duplicate", ret_lines(c, e, code), A("NO_ACTION"), {"processed_returns": [[e["trace"], code]]})
    for code in ["R01", "R02", "C01"]:
        c = new_customer(); e = new_entry(c)
        bad = e["trace"][:-3] + e["trace"][-2] + e["trace"][-3] + e["trace"][-1]
        if bad == e["trace"]: bad = e["trace"][:-1] + str((int(e["trace"][-1]) + 1) % 10)
        bad = bad if bad not in [x["trace"] for x in ledger] else ODFI8 + "9999999"
        lines = ret_lines(c, e, code, orig=bad) if code[0] == "R" else noc_lines(c, {"trace": bad}, code, "123456789")
        add("unmatched_trace", lines, A("ESCALATE"))
    for code in ["R01", "R02"]:
        c = new_customer(); e = new_entry(c)
        add("amount_mismatch", ret_lines(c, e, code, amount=e["amount_cents"] + 10000), A("ESCALATE"))
    for code in (["R31", "C13"] if split == "dev" else ["R85", "C09"]):
        c = new_customer(); e = new_entry(c)
        add("unknown_code", ret_lines(c, e, code) if code[0] == "R" else noc_lines(c, e, code, "X"), A("ESCALATE"))
    for code, corr in [("C02", "123456781"), ("C01", "12AB34"), ("C03", "")]:
        c = new_customer(); e = new_entry(c)
        add("malformed_noc", noc_lines(c, e, code, corr), A("ESCALATE"))
    for code in ["C01", "C02"]:
        c = new_customer(); e = new_entry(c)
        add("noc_noop", noc_lines(c, e, code, c["account"] if code == "C01" else c["routing"]), A("NO_ACTION"))
    if split == "stress":
        cases.clear()
    notice_codes = ["R01", "R10", "R02", "R29", "R09", "R03", "R07", "R08", "C01", "C02", "R16", "R10", "R01", "C03", "R04", "R05"] if split == "stress" else ["R01", "R02", "R03", "R10", "R10", "R29", "R07", "R08", "R16", "R09", "C01", "C02", "C03", "R01", "R04"]
    for i, code in enumerate(notice_codes):
        c = new_customer(corporate=code == "R29"); e = new_entry(c, attempts=2 if (code == "R01" and i == 13 and split != "stress") else 1)
        exp_act = code_act.get(code, "UPDATE")
        if code == "R01" and i == 13 and split != "stress": exp_act = "ESCALATE"
        f = {}
        spec = {"code": code, "trace": e["trace"], "customer": c["name"], "amount": e["amount_cents"] / 100,
                "last4": c["account"][-4:]}
        if code[0] == "C":
            corr, f = corrected_for(code, c); spec["corrected"] = f
        add("messy_hard" if split == "stress" else "messy_notice", None, A(exp_act, f), note=spec)
    return customers, ledger, cases

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    for split, seed in [("dev", 7), ("heldout", 2026), ("stress", 99)]:
        cu, le, ca = build(split, seed)
        json.dump({"customers": cu, "ledger": le}, open(f"data/{split}_ledger.json", "w"), indent=1)
        with open(f"data/{split}_cases.jsonl", "w") as f:
            for c in ca: f.write(json.dumps(c) + "\n")
        print(split, len(ca))
