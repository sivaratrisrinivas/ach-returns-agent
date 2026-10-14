"""Minimal NACHA fixed-width helpers (94-char records)."""
def aba_ok(r: str) -> bool:
    if len(r) != 9 or not r.isdigit():
        return False
    w = [3, 7, 1] * 3
    return sum(int(c) * k for c, k in zip(r, w)) % 10 == 0

def aba_make(prefix8: str) -> str:
    w = [3, 7, 1, 3, 7, 1, 3, 7]
    s = sum(int(c) * k for c, k in zip(prefix8, w))
    return prefix8 + str((10 - s % 10) % 10)

def entry6(txn, routing9, acct, amount_cents, ind_id, name, trace, addenda=1):
    s = ("6" + txn + routing9 + acct.ljust(17)[:17] + str(amount_cents).zfill(10)
         + ind_id.ljust(15)[:15] + name.ljust(22)[:22] + "  " + str(addenda) + trace)
    assert len(s) == 94, len(s)
    return s

def addenda99(code, orig_trace, rdfi8, info, trace):
    s = "799" + code + orig_trace + " " * 6 + rdfi8 + info.ljust(44)[:44] + trace
    assert len(s) == 94, len(s)
    return s

def addenda98(code, orig_trace, rdfi8, corrected, trace):
    s = "798" + code + orig_trace + " " * 6 + rdfi8 + corrected.ljust(29)[:29] + " " * 15 + trace
    assert len(s) == 94, len(s)
    return s

def parse(lines):
    """Parse a 6 record + 7 addenda pair. Returns dict."""
    e, a = lines[0], lines[1]
    out = {
        "txn_code": e[1:3], "rdfi_routing": e[3:12], "account": e[12:29].strip(),
        "amount_cents": int(e[29:39]), "ind_id": e[39:54].strip(), "name": e[54:76].strip(),
        "trace": e[79:94], "addenda_type": a[1:3], "code": a[3:6], "orig_trace": a[6:21],
    }
    if out["addenda_type"] == "98":
        out["corrected"] = a[35:64]
    return out
