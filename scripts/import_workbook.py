"""Block 3 - Importer: a workbook sheet export (CSV) -> source_templates, VERBATIM.

This stores each row exactly as exported (the immutable source). It does NOT
canonicalize tokens or normalize brands - that is Block 5 (the normalizer),
which reads from here. Idempotent on (channel, source_ref).

  # validate against the real file, write nothing:
  python -I scripts/import_workbook.py data/raw/email_template.csv --channel email --dry-run

  # load into Supabase once migration 0001 is applied:
  DATABASE_URL=postgresql://... python -I scripts/import_workbook.py data/raw/email_template.csv --channel email
"""
import sys, os, csv, json, hashlib, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Per-channel map of our field -> the export's column header.
# Email is confirmed from the real export; SMS/Landing are stubs - confirm their
# headers from those exports before importing them.
COLUMN_MAPS = {
    "email":   {"subject": "Email Subject", "body": "Email body"},
    "sms":     {"subject": None,            "body": "SMS Message"},     # TODO confirm
    "landing": {"subject": "Page Name",     "body": "page HTML"},       # TODO confirm
}
EXCEL_CELL_LIMIT = 32767


def read_csv(path):
    mx = sys.maxsize
    while True:
        try:
            csv.field_size_limit(mx); break
        except OverflowError:
            mx = int(mx / 10)
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        rows = list(csv.reader(f))
    header = rows[0]
    data = [r for r in rows[1:] if any((c or "").strip() for c in r)]
    return header, data


def build_records(path, channel):
    if channel not in COLUMN_MAPS:
        raise SystemExit(f"unknown channel {channel!r}")
    header, data = read_csv(path)
    cmap = COLUMN_MAPS[channel]
    idx = {h: i for i, h in enumerate(header)}
    body_i = idx.get(cmap["body"])
    subj_i = idx.get(cmap["subject"]) if cmap["subject"] else None
    if body_i is None:
        raise SystemExit(f"body column {cmap['body']!r} not in header: {header}")

    def cell(r, i):
        return (r[i] if (i is not None and i < len(r)) else "") or ""

    recs = []
    for n, r in enumerate(data):
        body = cell(r, body_i)
        recs.append({
            "channel": channel,
            "source_ref": f"{channel}:row{n + 2}",      # +2: header is sheet row 1
            "raw_subject": cell(r, subj_i),
            "raw_body": body,
            "raw_meta": {h: (r[i] if i < len(r) else "") for i, h in enumerate(header)},
            "source_hash": hashlib.sha256(body.encode("utf-8", "replace")).hexdigest(),
            "truncated": len(body) >= EXCEL_CELL_LIMIT,
        })
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--channel", required=True, choices=list(COLUMN_MAPS))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    recs = build_records(a.csv, a.channel)
    if a.limit:
        recs = recs[:a.limit]

    n = len(recs)
    trunc = [x for x in recs if x["truncated"]]
    empty = sum(1 for x in recs if not x["raw_body"].strip())
    seen = {}
    for x in recs:
        seen[x["source_hash"]] = seen.get(x["source_hash"], 0) + 1
    dup_bodies = sum(1 for c in seen.values() if c > 1)
    print(f"channel={a.channel} rows={n} truncated(>={EXCEL_CELL_LIMIT})={len(trunc)} "
          f"empty_body={empty} identical_bodies={dup_bodies}")

    if a.dry_run:
        s = recs[0]
        print("\n[dry-run] nothing written. sample record:")
        print(f"  source_ref={s['source_ref']} hash={s['source_hash'][:12]} "
              f"body_len={len(s['raw_body'])} subject={s['raw_subject'][:50]!r}")
        if trunc:
            print(f"\n[WARNING] {len(trunc)} bodies hit Excel's {EXCEL_CELL_LIMIT}-char limit "
                  f"and are TRUNCATED - re-grab these before relying on them:")
            for x in trunc:
                print(f"    {x['source_ref']}  {x['raw_meta'].get('Template Name','')[:55]}")
        return

    import db
    conn = db.connect()
    ins = skip = 0
    with conn, conn.cursor() as cur:
        for x in recs:
            cur.execute(
                """insert into source_templates
                     (channel, source_ref, raw_subject, raw_body, raw_meta, source_hash)
                   values (%s, %s, %s, %s, %s::jsonb, %s)
                   on conflict (channel, source_ref) do nothing""",
                (x["channel"], x["source_ref"], x["raw_subject"], x["raw_body"],
                 json.dumps(x["raw_meta"]), x["source_hash"]),
            )
            if cur.rowcount == 1:
                ins += 1
            else:
                skip += 1
    print(f"inserted={ins} skipped_existing={skip}")


if __name__ == "__main__":
    main()
