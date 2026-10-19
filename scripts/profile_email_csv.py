"""Profile the exported Email Template CSV: real counts + distributions.
Usage: python -I scripts/profile_email_csv.py data/raw/email_template.csv
Read-only. No DB, no network."""
import sys, csv, re
from collections import Counter

path = sys.argv[1]

# allow very large HTML fields
mx = sys.maxsize
while True:
    try:
        csv.field_size_limit(mx); break
    except OverflowError:
        mx = int(mx / 10)

with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
    rows = list(csv.reader(f))

header = rows[0]
data = rows[1:]
# drop fully-empty trailing rows
data = [r for r in data if any((c or "").strip() for c in r)]

print("COLUMNS (%d):" % len(header))
for i, h in enumerate(header):
    print(f"  [{i}] {h!r}")
print("\nDATA ROWS (non-empty):", len(data))

def col(idx):
    return [ (r[idx] if idx < len(r) else "") for r in data ]

def dist(name, idx, top=25):
    vals = [ (v or "").strip() for v in col(idx) ]
    nonempty = [v for v in vals if v]
    c = Counter(nonempty)
    print(f"\n-- {name} [col {idx}] -- nonempty={len(nonempty)}/{len(vals)}, distinct={len(c)}")
    for v, n in c.most_common(top):
        vv = v if len(v) <= 48 else v[:45] + "..."
        print(f"   {n:5d}  {vv}")

# short columns worth a distribution
labels = {h: i for i, h in enumerate(header)}
for name in ["Landing Page Status","Status","Payload Type","Language","Difficulty",
             "Responsible","Modification status","Prod Status","Staging Status","Dev Status",
             "New Modified Templates/ Version 1"]:
    if name in labels:
        dist(name, labels[name])

# Template Name: distinct + dupes
if "Template Name" in labels:
    names = [ (v or "").strip() for v in col(labels["Template Name"]) ]
    nonempty = [n for n in names if n]
    c = Counter(nonempty)
    dupes = {k:v for k,v in c.items() if v > 1}
    print(f"\n-- Template Name -- nonempty={len(nonempty)}, distinct={len(c)}, duplicated_names={len(dupes)}")
    for k,v in sorted(dupes.items(), key=lambda x:-x[1])[:15]:
        print(f"   {v}x  {k[:50]}")

# Body stats + token + brand detection
body_idx = labels.get("Email body")
subj_idx = labels.get("Email Subject")
name_idx = labels.get("Template Name")
bodies = col(body_idx) if body_idx is not None else []
nonempty_bodies = [b for b in bodies if (b or "").strip()]
if nonempty_bodies:
    lens = [len(b) for b in nonempty_bodies]
    print(f"\n-- Email body -- nonempty={len(nonempty_bodies)}, avg_len={sum(lens)//len(lens)}, max_len={max(lens)}")

# {{token}} usage across bodies + subjects + names
tok_re = re.compile(r"\{\{\s*([.#/A-Za-z0-9_\-]+)\s*\}\}")
tokens = Counter()
upper = lower = dotted = 0
hay = "\n".join(nonempty_bodies) + "\n".join(col(subj_idx) if subj_idx is not None else [])
for m in tok_re.finditer(hay):
    t = m.group(1); tokens[t]+=1
    if t.startswith("."): dotted += 1
    elif t.isupper(): upper += 1
    elif t.islower(): lower += 1
print(f"\n-- {{{{tokens}}}} -- distinct={len(tokens)} | UPPER={upper} lower={lower} dotted(.X)={dotted}")
for t,n in tokens.most_common(30):
    print(f"   {n:5d}  {{{{{t}}}}}")

# brand detection (name + subject, case-insensitive)
brands = ["facebook","instagram","google","tiktok","microsoft","apple","amazon","netflix",
          "linkedin","paypal","whatsapp","twitter","yahoo","outlook","dropbox","adobe","zoom",
          "docusign","dhl","fedex","ups","gsa","bkash","nagad","rocket","upay","robi",
          "grameenphone","banglalink","teletalk","city bank","dutch-bangla","dbbl","brac"]
blob = "\n".join([(names if False else "")]) # placeholder
name_subj = []
if name_idx is not None: name_subj += col(name_idx)
if subj_idx is not None: name_subj += col(subj_idx)
ns = "\n".join(name_subj).lower()
bc = Counter()
for b in brands:
    n = ns.count(b)
    if n: bc[b] = n
print(f"\n-- brand mentions in Template Name + Subject --")
for b,n in bc.most_common():
    print(f"   {n:5d}  {b}")
