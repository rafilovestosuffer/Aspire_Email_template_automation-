# PRD: ASAT Content Factory — Phase 0 (Foundation)

> Phase 0 is the first buildable increment of the authorized SAT content factory. The full, finalized strategy lives in the roadmap doc built this session; this PRD scopes only the foundation layer. It is infrastructure, not a demo app, so the demo-centric sections of the template are adapted.

## 0. Assumptions

- [Confirmed] Scope is Phase 0 only: import/normalize the library, lock the controlled lists + `{{variable}}` standard, stand up the Supabase schema.
- [Confirmed] This is authorized, defensive SAT work; the three controls (per-engagement authorization, credential-capture-impossible landing, roster-scoped sending) are requirements, carried into the schema even though their enforcement is later phases.
- [Confirmed] The agent produces migration-ready DDL; Rafi applies it (no live-deploy here, no credentials).
- [Assumed] Stack per the roadmap: Supabase (Postgres), Python scripts for the one-off import/normalize, OpenRouter for extraction. n8n orchestration is Phase 2+.
- [Assumed] The real library is ~hundreds of rows (to be confirmed by Block 1 export+count), not 1,000 finished templates.
- [Assumed] Variable case standard = lower `{{snake_case}}`.

## 1. One-line summary

Phase 0 helps the Aspire SAT team turn a messy, brand-hardcoded workbook library into a clean, versioned, brand-neutral master schema — by importing each item immutably and normalizing brand/sender/locale details into a controlled variable vocabulary — producing a frozen Supabase schema everything else builds on.

## 2. Target users

- **Primary:** the SAT content team (Rafi + Aisha + Lamia) who will author, review, and eventually generate from these masters.
- **Secondary:** the later-phase builders (localization, review UI, sender) who consume the frozen schema.
- **Pain today:** brands/logos hardcoded, inconsistent vocabularies, no IDs/versioning, English-only.
- **Alternative today:** hand-editing each template in a spreadsheet.
- **Why better:** one brand-neutral master serves any client in any language; changes are versioned and auditable.

## 3. Problem statement

The library can't be automated as-is: brand details are baked into each template, vocabularies are inconsistent, and there are no stable IDs or version history. Without a normalized, controlled schema, every later phase (localization, variants, review, publish) would multiply the mess. Now is the time because the strategy is locked and the first authorized engagement will pull on this foundation.

## 4. MVP scope (= Phase 0 exit gate)

The smallest version that unblocks everything else:
- **Input:** the exported workbook (.xlsx).
- **Processing:** immutable import → LLM-assisted normalization into brand-neutral masters → lint + hostile-fixture render → human confirm.
- **Output:** a frozen Supabase schema populated with `source_templates`, brand-neutral `templates`/`template_versions`, `brands`, and the seeded controlled vocabulary.
- **Must work:** 100% imported + lint-clean; schema frozen/versioned; a sample round-trip render reproduces the original.

## 5. Core flow

1. Rafi exports the workbook → `data/raw/asat_library.xlsx`.
2. Importer writes verbatim `source_templates`.
3. Normalizer proposes variables + diff per source (LLM).
4. Human confirms/corrects; masters go `draft → active`.
5. Linter + round-trip check gate the freeze.
States: empty (no file yet → Block 1 blocked), success (counts match, round-trip passes), error (lint `fail` → stays draft, source safe).

## 6. Must-have features

See `TASKS.md` for the block-by-block breakdown with acceptance criteria. Summary: (1) export+count, (2) apply migration, (3) importer, (4) reconcile controlled lists, (5) normalizer, (6) linter + hostile-fixture, (7) human confirm + round-trip (exit gate).

## 7. Nice-to-have (after Phase 0)

- High leverage: a minimal confirm UI (currently CSV/notebook).
- Medium: near-dedup (MinHash/SimHash) reporting across masters.
- Low: import of the Presentation-sheet campaign pairings as seed `campaign` rows.

## 8. Non-goals (do NOT build in Phase 0)

Sending; localization/translation; variant ("amount") generation; the admin UI; the safe-landing service; the downstream sender; any live-deploy by the agent. The `factory_never_sendable` CHECK stays in force.

## 9. System modules

See `ARCHITECTURE.md`. In brief: Importer, Normalizer, Confirm/correct, Linter (Python scripts) over the Supabase schema; OpenRouter for extraction only (pinned model + prompt version, structured JSON, fail-closed to a draft).

## 10. Data schema

The authoritative schema is `supabase/migrations/0001_phase0_schema.sql`; the vocabularies are `docs/controlled-lists-and-variables.md`. Core tables: `source_templates` (immutable), `templates`/`template_versions`, `translations`, `variables`/`template_variables`, `brands`/`brand_assets`, `engagements`, `render_outputs`, `review_events`, `categories`.

## 11. AI model contract (normalizer)

- **Role:** span-tagger, not copywriter. Given one template, return which spans are brand/sender/locale-specific and the cleaned body with `{{variables}}`.
- **Output:** strict JSON — `{cleaned_body, variables[], detected_brand{name,colors,logo,domain}, diff}`.
- **Guardrails:** never rewrite scenario or copy; never invent variables outside the controlled vocabulary; unknown → flag for human.
- **Failure:** unparseable/low-confidence → leave the master `draft`, `lint_status=fail`; source untouched; re-runnable.

## 12. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| LLM mis-tags or misses a hardcoded brand | wrong master | human confirm; linter blocks hardcoded brand; immutable source re-run |
| Export loses inline HTML | lossy masters | round-trip check vs source; spot-check a sample |
| Applying migration to wrong DB | data risk | dedicated Phase-0 Supabase project |
| Scope creep into later phases | delay | non-goals above; `factory_never_sendable` CHECK |

## 13. Acceptance checklist

- [ ] All workbook rows imported (count matches) and lint-clean.
- [ ] Controlled lists reconciled against real data (no unknown tokens/labels).
- [ ] Brands extracted to rows; masters brand-neutral.
- [ ] Sample round-trip render reproduces the original.
- [ ] `schema_meta.frozen = true`.
- [ ] No sendable content possible; recipient PII never resolved.
