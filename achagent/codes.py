"""NACHA code meanings (public sources: Nacha Return Reason Code Guide summaries,
Modern Treasury ACH return code reference, Huntington and U.S. Bank developer docs)."""
RETURNS = {
    "R01": "Insufficient funds",
    "R02": "Account closed",
    "R03": "No account / unable to locate account",
    "R04": "Invalid account number structure",
    "R05": "Unauthorized debit to consumer account using corporate SEC code",
    "R07": "Authorization revoked by customer",
    "R08": "Payment stopped",
    "R09": "Uncollected funds",
    "R10": "Customer advises originator is not known and/or not authorized",
    "R11": "Customer advises entry not in accordance with authorization terms",
    "R16": "Account frozen / entry returned per OFAC instruction",
    "R20": "Non-transaction account",
    "R29": "Corporate customer advises not authorized",
}
NOCS = {
    "C01": ("Incorrect DFI account number", ["account"]),
    "C02": ("Incorrect routing number", ["routing"]),
    "C03": ("Incorrect routing number and DFI account number", ["routing", "account"]),
    "C05": ("Incorrect transaction code", ["txn_code"]),
    "C06": ("Incorrect DFI account number and transaction code", ["account", "txn_code"]),
    "C07": ("Incorrect routing number, DFI account number and transaction code", ["routing", "account", "txn_code"]),
}
