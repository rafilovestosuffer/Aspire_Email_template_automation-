# CLAUDE.md — ASAT Content Factory

## Project context

The authorized SAT (security-awareness-training) content factory. This is **defensive security work**: it produces phishing-simulation content for Aspire's clients' own employees, under per-engagement authorization. The artifacts are identical to a phishing kit; only the control layer makes this legitimate — so controls come first, always.

Current work: **Phase 0** (foundation — import/normalize the library + lock the schema). Later phases add localization, variant generation, review UI, publish, and the downstream sender.

## Source of truth (read before implementing)

1. `PRD.md` — Phase 0 scope and acceptance.
2. `TASKS.md` — the block-by-block plan.
3. `ARCHITECTURE.md` — modules, data flow, schema reference.
4. `docs/controlled-lists-and-variables.md` — the controlled vocabulary + `{{variable}}` standard.
5. `supabase/migrations/0001_phase0_schema.sql` — the schema contract.
6. The roadmap doc (Claude Doc, this session) — the full strategy, §2 controls and §10 blockers.

If files conflict: user's latest instruction → `TASKS.md` → `PRD.md` → `CLAUDE.md`.

## Non-negotiable controls (never violate, in any block)

1. **The factory never emits sendable content.** Do not remove or relax the `factory_never_sendable` CHECK. Nothing becomes sendable until the downstream Release-Gate exists and passes its roster-enforcement test.
2. **Recipient PII is never resolved or stored in the factory.** `first_name`, `email`, etc. stay as placeholders; they are merged by the downstream sender only.
3. **Link/engagement variables are system-owned.** Authors cannot set `phishing_link`, `engagement_id`, `tracking_pixel`, `training_url`; they resolve only to engagement-approved hosts.
4. **The audit log is append-only.** No UPDATE/DELETE on `review_events`; corrections are new rows.
5. **The immutable source is never edited.** Re-run normalization from `source_templates`; never mutate it.
6. **Controlled vocabulary only.** No free-form `{{tokens}}`; a new variable/category is added by a new migration + the spec, never ad hoc.
7. **Schema changes go in a new migration** (`0002_*`), never by editing a frozen one.
8. **No real credentials, no live deploy, no sending, no actual lure-content generation** in Phase 0.

## Workflow (/block style)

1. Implement exactly **one** block from `TASKS.md`.
2. Do not implement future blocks or start later phases early.
3. Do not refactor unrelated files or change the stack without instruction.
4. Run the block's `Test`.
5. Report changed files, test result, risks, next step. Wait for the next command.

## Coding rules

- No secrets/keys in code — use environment variables (`DATABASE_URL`, `OPENROUTER_API_KEY`).
- LLM steps: pin `model` + `prompt_version`; structured JSON; fail-closed to a `draft` + `lint_status=fail`; never auto-approve.
- Prefer simple, resumable scripts; idempotent on content hash.
- Preserve existing working behavior; keep the immutable sources safe.
- Never commit unless explicitly asked.

## Testing

Run only what exists in the repo. Phase 0 is Python + SQL:

```bash
python -m compileall scripts
python scripts/verify_schema.sql   # via psql
pytest    # once tests exist
```

## Non-negotiable process rules

- Never implement multiple blocks unless asked.
- Never relax a control to make a block pass — fix the block.
- Never deploy to a live Supabase project on the user's behalf.
- Never generate, or help generate, actual phishing lure content in Phase 0.
