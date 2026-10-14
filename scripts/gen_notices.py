"""Step 2 of synthetic data: turn each messy_notice tuple into realistic bank text.
Dev and held-out use different channel styles so held-out phrasing is unseen."""
import json, sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from achagent.llm import chat
from achagent.codes import RETURNS, NOCS
STYLES = {"dev": ["a short email from a partner bank ops analyst", "a forwarded email thread with a one line note on top"],
          "stress": ["a rambling email from a partner bank analyst", "a support ticket summary", "notes from a phone call"],
          "heldout": ["a terse bank portal chat message", "an analyst's notes from a phone call with the bank", "a pasted SFTP exception report comment"]}
SYS = ("You write realistic, slightly messy operations messages for synthetic test data. Never use the NACHA code (like R01 or C02) "
       "and never use the official code title. Describe the situation in plain everyday words. Output only the message text.")
def main():
    for split in ["dev", "heldout", "stress"]:
        p = f"data/{split}_cases.jsonl"; rows = [json.loads(l) for l in open(p)]
        for i, r in enumerate(rows):
            if r["input"]["kind"] != "notice": continue
            s = r["input"]["note_spec"]; code = s["code"]
            meaning = RETURNS.get(code) or NOCS[code][0]
            tr = s["trace"]; tr_fmt = [tr, f"{tr[:8]}-{tr[8:]}", f"{tr[:4]} {tr[4:8]} {tr[8:]}"][i % 3]
            user = (f"Write {STYLES[split][i % len(STYLES[split])]} to a fintech's payment ops team about one ACH debit. "
                    f"Situation (do not quote this wording): {meaning}. Customer: {s['customer']}, account ending {s['last4']}, "
                    f"amount ${s['amount']:.2f}. Original trace number written as: {tr_fmt}. ")
            if "corrected" in s:
                user += "Include the corrected details exactly: " + ", ".join(f"{k}={v}" for k, v in s["corrected"].items()) + \
                        (" (txn_code 37 means savings debit). " if "txn_code" in s["corrected"] else ". ")
            if split == "stress":
                user += ("Make it genuinely tricky: include one misleading detail that names a different, ruled-out reason "
                         "(for example 'not a closed account' or 'the customer first thought it was fraud but then confirmed'), "
                         "and make clear which reason is the real one. ")
            user += "Under 70 words."
            for attempt in range(4):
                t = chat(SYS, user, temperature=0.9, tag=f"{r['id']}-{attempt}")
                bad = re.search(r"\b[RC]\d\d\b", t) or meaning.lower() in t.lower() or tr_fmt not in t
                if not bad: break
            r["input"]["text"] = t
        with open(p, "w") as f:
            for r in rows: f.write(json.dumps(r) + "\n")
        print(split, "done")
main()
