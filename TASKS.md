# TASKS: ASAT Content Factory — Phase 0

Block-by-block. Build one block, verify, stop. Foundation first. Nothing here sends, localizes, or generates variants.

---

## Block 1: Export + count the workbook

**Goal:** Get the real library into a countable file and size the normalization job.

**Depends on:** Rafi exporting the workbook. **Blocked until the file is present.**

**Steps:**
1. Rafi exports the ASAT workbook to `data/raw/asat_library.xlsx` (all sheets).
2. `scripts/count_workbook.py` prints rows per sheet, and per `channel × payload_type × detected brand`.

**Acceptance criteria:**
- [ ] `data/raw/asat_library.xlsx` exists with all sheets.
- [ ] A printed count table: rows per channel, payload type, and distinct brand.
- [ ] The "~120+ vs 1,000" scale question (roadmap §3) is answered with a real number.

**Test:** `python scripts/count_workbook.py data/raw/asat_library.xlsx`

**Rollback:** none (read-only).

**Risk:** The export loses inline HTML/formatting — verify a sample row's body survived intact.

---

## Block 2: Apply the Phase 0 migration

**Goal:** Stand up the schema in a Supabase project.

**Steps:**
1. Rafi creates/points to a Supabase project and sets `DATABASE_URL` / links the CLI.
2. Apply `supabase/migrations/0001_phase0_schema.sql` (`supabase db push`, or `psql -f`).
3. Verify enums, tables, seeded `variables` (25 rows) and `categories` (7 rows), and the `factory_never_sendable` constraint.

**Acceptance criteria:**
- [ ] All tables + enums created; `select count(*) from variables` = 26; `categories` = 7.
- [ ] `insert into render_outputs(... sendable=true ...)` is **rejected** by the CHECK.
- [ ] `update review_events ...` is **rejected** by the append-only trigger.

**Test:** `supabase db push` then run `scripts/verify_schema.sql`.

**Rollback:** `drop schema` / restore from a fresh project; migration is the only writer.

**Risk:** Applying against the wrong project. Use a dedicated Phase-0 project.

---

## Block 3: Importer → `source_templates`

**Goal:** Load every workbook row verbatim as an immutable source.

**Files:** `scripts/import_workbook.py`

**Steps:**
1. Parse each sheet with openpyxl; map columns to `channel`, `raw_subject`, `raw_body`, `raw_meta` (all original columns).
2. Compute `source_hash = sha256(raw_body)`; skip rows already present (idempotent).
3. Insert into `source_templates`.

**Acceptance criteria:**
- [ ] Row count in `source_templates` matches the Block 1 count.
- [ ] Re-running the importer inserts 0 new rows.
- [ ] A spot-checked row's `raw_body` byte-matches the workbook cell.

**Test:** `python scripts/import_workbook.py data/raw/asat_library.xlsx` then compare counts.

**Rollback:** `truncate source_templates cascade` and re-run.

**Risk:** Column layout differs per sheet (email vs SMS vs landing) — map per sheet, not globally.

---

## Block 4: Reconcile the controlled lists against real data

**Goal:** Confirm the seeded vocabularies cover what the library actually uses.

**Files:** `docs/controlled-lists-and-variables.md`, a new migration if changes are needed.

**Steps:**
1. From `source_templates`, extract every `{{token}}` actually present and every payload-type / difficulty / status label used.
2. Diff against the seeded `variables`, enums, and `categories`.
3. Add any genuinely-missing variable/category **by a new migration** + an edit to the spec; rewrite `{{UPPER}}` tokens to `{{lower_snake}}` in the import mapping.

**Acceptance criteria:**
- [ ] Every token in the library maps to a known variable (or is added deliberately).
- [ ] Every difficulty/status/payload label maps to an enum value.
- [ ] The spec and the DB seed match exactly.

**Test:** `python scripts/audit_vocab.py` (reports unknown tokens / labels; must be empty).

**Rollback:** revert the new migration.

**Risk:** A "token" that is really hard-coded brand text — treat as Block 5, not a new variable.

---

## Block 5: Normalizer → draft masters + brands

**Goal:** Turn each source into a brand-neutral master, extracting brand values into `brands`.

**Files:** `scripts/normalize.py`, `prompts/normalize.md`

**Steps:**
1. For each source row, call OpenRouter (structured JSON) to propose brand/sender/locale spans, a cleaned body with `{{variables}}`, the detected brand (name/colors/logo/domain), and a diff.
2. Write a `templates` + `template_versions` (status `draft`) row and `template_variables`; upsert the detected brand into `brands` / `brand_assets`.
3. Pin `model` + `prompt_version`; keep the source immutable; store the diff for human review.

**Acceptance criteria:**
- [ ] Each draft master contains only controlled variables (no hard-coded brand string).
- [ ] The bKash/Nagad/Robi/GP/City Bank brands appear as `brands` rows.
- [ ] Re-running with the same model/prompt is idempotent (skips done).

**Test:** `python scripts/normalize.py --limit 30` then `scripts/audit_vocab.py` on the drafts.

**Rollback:** `delete from templates where status='draft'` (sources untouched); re-run.

**Risk:** The LLM "helpfully" rewrites copy — constrain the prompt to span-tagging only, not rewriting.

---

## Block 6: Linter + hostile-fixture render test

**Goal:** A fail-closed gate before any master leaves draft.

**Files:** `scripts/lint.py`

**Steps:**
1. Validate: only known variables, balanced tokens, correct output-context, no hard-coded brand.
2. Render each draft against hostile brand fixtures (`brand_name = "><script>…`, `brand_color = red;}body{…`, `brand_logo_url = javascript:…`) and assert no injected tag / broken attribute / non-https URL.
3. Set `lint_status = pass|fail`.

**Acceptance criteria:**
- [ ] Every `draft` master has a `lint_status`.
- [ ] A deliberately-malformed master is caught (`fail`).
- [ ] Hostile fixtures produce no injection in any passing master.

**Test:** `python scripts/lint.py` + a known-bad fixture returns `fail`.

**Rollback:** none (sets a status column only).

**Risk:** Email HTML edge cases — start with a tight allow-list, widen as real templates need it.

---

## Block 7: Human confirm + round-trip render (EXIT GATE)

**Goal:** A human confirms the extraction, and a sample renders back to the original.

**Files:** `scripts/review_queue.py`, `scripts/roundtrip_check.py`

**Steps:**
1. Export the drafts + diffs for human review (CSV/notebook); confirmed masters go `draft → active`.
2. For a sample, render `master + original brand` and diff against the immutable `source_templates.raw_body`.
3. When the gate is met, set `schema_meta.frozen = true`.

**Acceptance criteria:**
- [ ] 100% of sources are imported and every master is lint-clean.
- [ ] A sample round-trip render reproduces the original (brand re-injected).
- [ ] `schema_meta.frozen = true`.

**Test:** `python scripts/roundtrip_check.py --sample 20`

**Rollback:** keep masters in `draft`; do not freeze.

**Risk:** Round-trip reveals lossy extraction — fix the normalizer/prompt (Block 5), re-run; sources are safe.
