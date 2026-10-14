"""v0: the first naive agent used for error analysis. Code to action only, no ledger or history."""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from achagent.nacha import parse
M = {"R01":"RETRY","R09":"RETRY","R02":"RETRY","R03":"BLOCK","R10":"RETRY","R29":"BLOCK"}
for l in open("data/dev_cases.jsonl"):
    c = json.loads(l)
    if c["input"]["kind"] != "addenda": act, code = "?", "text"
    else:
        p = parse(c["input"]["lines"]); code = p["code"]
        act = "UPDATE" if code[0] == "C" else M.get(code, "ESCALATE")
    e = c["expected"]["action"]
    print(("ok  " if act == e else "BAD ") + f"{c['id']} {c['category']:24s} {code:5s} got {act:9s} want {e}")
