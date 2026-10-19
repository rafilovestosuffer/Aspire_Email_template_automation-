# Architecture: ASAT Content Factory — Phase 0

## 1. System overview

Phase 0 builds the **data foundation only**: ingest the existing workbook library verbatim, normalize each item into a brand-neutral master with controlled variables, and lock the schema + vocabularies. No UI, no sending, no localization, no variant generation yet — those build on this frozen schema in later phases.

Controls live in the schema, not in convention: renders are engagement-bound, link/engagement variables are system-owned, recipient PII is never resolved in the factory, the audit log is append-only, and a hard `CHECK` makes it impossible for the factory to emit sendable content.

## 2. Data flow

```
Workbook export (.xlsx)
  → Importer (parse each sheet / row)
  → source_templates           (immutable, verbatim, hashed)
  → Normalizer (LLM via OpenRouter: classify brand/sender/locale spans, emit diff)
  → human confirm / correct    (Phase 0: CLI / notebook; the UI is Phase 1+)
  → templates + template_versions   (brand-neutral masters, status=draft)
     + brands / brand_assets         (extracted brand values -> rows)
     + template_variables            (lint join)
  → Lint + hostile-fixture render test
  → status draft -> active, schema frozen (exit gate)
```

## 3. Module breakdown

| Module | Responsibility | Files |
|---|---|---|
| **Importer** | One `source_templates` row per workbook row; all original columns in `raw_meta`; idempotent on `source_hash`. | `scripts/import_workbook.py` |
| **Normalizer** | Per source row, LLM classifies brand/sender/locale spans → cleaned body + variable list + detected brand + a diff. Writes **draft** masters; nothing auto-approves; source stays immutable. | `scripts/normalize.py`, `prompts/normalize.md` |
| **Confirm / correct** | Human reviews each diff and confirms before a master leaves draft (Phase 0: CSV/notebook round-trip). | `scripts/review_queue.py` |
| **Linter** | Controlled-vocabulary check, balanced tokens, output-context usage, no hard-coded brand, hostile-fixture render. | `scripts/lint.py` |
| **Schema + vocab** | The frozen contract. | `supabase/migrations/0001_phase0_schema.sql`, `docs/controlled-lists-and-variables.md` |

## 4. Tech stack decision

| Layer | Choice | Reason |
|---|---|---|
| Database | Supabase (Postgres) | stated stack; RLS + Auth needed in later phases |
| Import / normalize | Python scripts (openpyxl) | one-off resumable batch; no UI needed yet |
| AI | OpenRouter, structured JSON output | stated stack; pin `model` + `prompt_version` for reproducible re-runs |
| Orchestration (later) | n8n | Phase 2+ batch jobs; Phase 0 stays plain scripts |

## 5. Failure handling

- **Bad / unparseable LLM extraction** → the master stays `draft` with `lint_status = fail`; the immutable source is untouched and re-runnable.
- **Ambiguous brand span** → flagged for human confirm; never auto-applied.
- **Import re-run** → idempotent on `source_hash`; no duplicates.
- **Schema change needed** → a new migration (`0002_*`), never an edit to a frozen one.
- **No OpenRouter key / rate limit** → normalizer backs off and resumes; import and schema work do not depend on the LLM.

## 6. What Phase 0 deliberately does NOT do

No sending, no localization, no variant ("amount") generation, no credential-capturing anything, no live Supabase deploy by this agent. The `factory_never_sendable` CHECK stays in force until the downstream Release-Gate exists (roadmap §2, §10).
