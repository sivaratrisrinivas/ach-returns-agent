"""Write docs/data.js for the GitHub Pages demo from a real agent run (held-out + stress)."""
import json, sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from achagent.agent import Agent
rows = []
for sp in ["heldout", "stress"]:
    led = json.load(open(f"{ROOT}/data/{sp}_ledger.json")); ag = Agent(led, "hybrid"); kw = Agent(led, "rules_kw")
    for l in open(f"{ROOT}/data/{sp}_cases.jsonl"):
        c = json.loads(l); o = ag.decide(c); k = kw.decide(c)
        raw = "\n".join(c["input"]["lines"]) if c["input"]["kind"] == "addenda" else c["input"]["text"]
        rows.append({"id": c["id"], "cat": c["category"], "raw": raw if c["input"]["kind"] == "notice" else raw[:12] + "..." + raw[29:94] + "\n" + c["input"]["lines"][1],
                     "action": o["action"], "code": o["code"], "approval": o["needs_approval"], "draft": o["draft"],
                     "source": o["source"], "kw_action": k["action"], "expected": c["expected"]["action"]})
res = json.load(open(f"{ROOT}/evals/results.json"))
summary = {k: {"pass": v["pass"], "n": v["n"], "cat": v["by_category"]} for k, v in res.items()}
open(f"{ROOT}/docs/data.js", "w").write("window.ROWS=" + json.dumps(rows) + ";\nwindow.SUMMARY=" + json.dumps(summary) + ";\n")
print(len(rows))
