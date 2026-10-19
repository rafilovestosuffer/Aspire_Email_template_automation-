"""Block 4 - vocabulary reconciliation.

Scans the export for every {{token}}, Difficulty and Payload Type, maps each via
token_map, and reports: what maps to an existing variable, what needs a new
variable (migration), what needs a human decision, what is dropped, and what is
UNKNOWN. Exits non-zero if any unknown token remains - so it can gate the build.

  python -I scripts/audit_vocab.py data/raw/email_template.csv --channel email
"""
import sys, re, csv, argparse, os
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import token_map as tm

TOK = re.compile(r"\{\{\s*([.#/A-Za-z0-9_\-]+)\s*\}\}")
# email-sheet columns to scan; extend per channel later
SCAN = {"email": {"body": "Email body", "subject": "Email Subject",
                  "difficulty": "Difficulty", "payload": "Payload Type"}}


def read_csv(path):
    mx = sys.maxsize
    while True:
        try:
            csv.field_size_limit(mx); break
        except OverflowError:
            mx = int(mx / 10)
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        rows = list(csv.reader(f))
    return rows[0], [r for r in rows[1:] if any((c or "").strip() for c in r)]


def show(title, cnt):
    print(f"\n== {title} ({len(cnt)}) ==")
    for k, n in cnt.most_common():
        print(f"  {n:6d}  {k}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--channel", default="email")
    a = ap.parse_args()
    cols = SCAN[a.channel]
    header, data = read_csv(a.csv)
    idx = {h: i for i, h in enumerate(header)}

    def col(name):
        i = idx.get(cols.get(name))
        return [(r[i] if i is not None and i < len(r) else "") for r in data]

    # ---- tokens ----
    hay = "\n".join(col("body")) + "\n" + "\n".join(col("subject"))
    toks = Counter(m.group(1) for m in TOK.finditer(hay))
    mapped, needs_mig, review, drop, unknown = (Counter() for _ in range(5))
    for t, c in toks.items():
        canon, kind = tm.canon_token(t)
        if kind == "drop":
            drop[t] += c
        elif kind == "review":
            review[t] += c
        elif kind == "unknown":
            unknown[t] += c
        elif canon in tm.SEEDED_VARS:
            mapped[f"{{{{{t}}}}} -> {canon}"] += c
        else:
            needs_mig[f"{{{{{t}}}}} -> {canon}  (ADD VAR via migration)"] += c

    print("TOKENS  (distinct=%d)" % len(toks))
    show("mapped to an existing variable", mapped)
    show("mapped but NEEDS A MIGRATION (new var)", needs_mig)
    show("NEEDS A HUMAN DECISION", review)
    show("dropped (junk)", drop)
    show("UNKNOWN - must resolve", unknown)

    # ---- label columns ----
    def labels(name, fn):
        c = Counter((v or "").strip() for v in col(name) if (v or "").strip())
        ok, bad = Counter(), Counter()
        for v, n in c.items():
            canon, kind = fn(v)
            (ok if kind == "mapped" else bad)[f"{v!r} -> {canon} [{kind}]"] += n
        show(f"{cols[name]} mapped", ok)
        if bad:
            show(f"{cols[name]} NEEDS ATTENTION", bad)

    labels("difficulty", tm.canon_difficulty)
    labels("payload", tm.canon_payload)

    fail = len(unknown) > 0
    print("\nRESULT:", "FAIL - unknown tokens present" if fail
          else "OK - every token maps, needs a migration, or is flagged for review")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
