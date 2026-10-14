"""Run the eval. Usage: python evals/run.py [--split dev|heldout|all] [--mode rules|rules_kw|hybrid|all] [--min PASS_RATE]"""
import json, sys, os, argparse, hashlib, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from achagent.agent import Agent
from evals.checks import CHECKS, pii_masked
ap = argparse.ArgumentParser(); ap.add_argument("--split", default="all"); ap.add_argument("--mode", default="all")
ap.add_argument("--json", default=None); ap.add_argument("--require", nargs="*", default=[])
a = ap.parse_args()
# held-out integrity: files must match the hash frozen before tuning
for line in open(os.path.join(ROOT, "evals/HELDOUT.sha256")):
    h, f = line.split()
    assert hashlib.sha256(open(os.path.join(ROOT, f), "rb").read()).hexdigest() == h, f"held-out file changed: {f}"
splits = ["dev", "heldout", "stress"] if a.split == "all" else [a.split]
modes = ["rules", "rules_kw", "hybrid"] if a.mode == "all" else [a.mode]
report = {}
for mode in modes:
    for sp in splits:
        led = json.load(open(os.path.join(ROOT, f"data/{sp}_ledger.json")))
        cases = [json.loads(l) for l in open(os.path.join(ROOT, f"data/{sp}_cases.jsonl"))]
        ag = Agent(led, mode); cat = collections.defaultdict(lambda: [0, 0]); fails = []; hard = 0
        for c in cases:
            o = ag.decide(c)
            res = [(f.__name__,) + f(c, o) for f in CHECKS] + [("pii_masked",) + pii_masked(c, o, led)]
            ok = all(r[1] for r in res)
            if not res[2][1] or not res[1][1]: hard += 1  # safety failures
            cat[c["category"]][0] += ok; cat[c["category"]][1] += 1
            if not ok: fails.append({"id": c["id"], "category": c["category"], "failed": [f"{r[0]}: {r[2]}" for r in res if not r[1]], "action": o["action"], "code": o["code"]})
        tot = sum(v[0] for v in cat.values()), len(cases)
        report[f"{mode}/{sp}"] = {"pass": tot[0], "n": tot[1], "safety_failures": hard, "by_category": dict(cat), "fails": fails}
        print(f"\n== {mode} / {sp}: {tot[0]}/{tot[1]} pass ({100*tot[0]/tot[1]:.0f}%), safety failures {hard}")
        for k, (p, n) in cat.items(): print(f"   {k:26s} {p}/{n}")
        for f in fails: print("   FAIL", f["id"], f["category"], f["code"], f["action"], "|", "; ".join(f["failed"]))
if a.json: json.dump(report, open(a.json, "w"), indent=1)
bad = []
for spec in a.require:  # e.g. hybrid/heldout=0.95 ; safety always zero
    k, v = spec.split("=")
    r = report[k]
    if r["pass"] / r["n"] < float(v): bad.append(f"{k} below {v}")
for k, r in report.items():
    if r["safety_failures"]: bad.append(f"{k} has safety failures")
if bad: print("\nGATE FAILED:", bad); sys.exit(1)
