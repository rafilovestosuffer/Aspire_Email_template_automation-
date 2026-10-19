# Project handoff — 2026-10-15

## Target agreed in the supplied chat and flow diagram

English email and landing-page library → company personalization → AI batch
localization into 30 languages → human review → approved database publication.
Optional variants precede localization. Preserve source bodies when variants are
not requested. This repository is a content factory, not a mail sender.

The pasted conversation is historical context, not proof of current behavior.
PRD.md, ARCHITECTURE.md and the original TASKS blocks document the earlier Phase 0
plan; the current user request and existing console extend beyond that scope.

## Verified inventory

- Local CSV: 1,162 nonempty email rows, no empty bodies, 23 repeated body hashes.
- CSV decoding: Windows-1252 fallback is required for this export. The library
  reader preserves these characters; older CLI scripts still use replacement
  decoding and should be updated before production import.
- 80 bodies reach 32,767 characters: potential spreadsheet truncation; recovery
  required before these sources can be selected through the library API.
- No full workbook or landing/SMS exports present.
- Supabase migration exists; deployment and population have not been verified.
- Importer is CSV-only and preserves raw content. Normalizer, roundtrip checker,
  and production lint/confirm scripts described by Phase 0 are not implemented.

## Implemented local increment

- Search/select the local email library without changing its raw file.
- Use original HTML directly or generate 1–8 variants.
- Durable SQLite drafts, reviews and append-only review events.
- Server-side approval gate before localization; separate translation approval.
- Revoking source approval resets child reviews and removes them from export.
- Mock/error outputs cannot be approved. Model output must preserve placeholder
  counts and HTML structure/attributes before being recorded as successful.
- Repeat localization reuses successful language results; newly selected
  languages can be added. Failed languages can be retried.
- Approved JSON review export, explicitly sendable=false. This is not a
  production database publish operation or a delivery-format integration.
- Sandboxed previews block external resources and scripts; RTL is applied
  inside the preview document. External logos therefore do not appear.

## Validation

Browser repair verified: the previously running backend returned 404 for both
`/api/library` and `/api/workspace` while serving the new static UI. Restarted
with the dependency-equipped Python environment and enabled development reload.
Verified in Brave: `facebook` returns 7 matches, selecting a result loads its
HTML, and a no-match query disables Load with a visible explanatory message.
Library errors now appear alongside the library controls. Seven automated tests
passed after the repair. Live AI generation was not invoked for this check.

`python -m unittest discover -s tests -v` covers review/localization/export,
revocation, persistence, mock rejection, invalid language input, legacy API
bypass and malformed model output. Tests mock the AI provider: they do not
establish live linguistic quality. Python compilation and JS syntax also checked.

## Remaining steps, in order

1. Recover the 80 incomplete email bodies and obtain landing-page exports.
   Resolve ambiguous source variables; keep originals immutable.
2. Normalize source brands with human-confirmed diffs and roundtrip validation.
   Add subject translation and typed brand records (name/logo/colors/domain).
   Currently company context goes to the model; frozen brand placeholders remain
   intact, so complete deterministic brand binding is still outstanding.
3. Add persisted batch jobs with bounded concurrency, rate-limit backoff,
   cancellation, cost estimates and crash recovery. Current calls are synchronous
   and suitable for small local batches, not thousands of templates.
4. Add reviewer authentication/roles and organization boundaries. Reviewer names
   today are self-entered labels; run on localhost only.
5. Map reviewed records into the existing Supabase schema with provenance,
   version hashes, idempotency, transactional publication and engagement checks.
   Supply/confirm the target database and delivery format before live publication.
6. End-to-end tests against staging plus human linguistic review of representative
   languages, email layouts and landing pages; only then mark production ready.

## Run

`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`

Local state: `data/workspace.sqlite3` (gitignored). Override with `FACTORY_DB`.
Keep the database file to retain drafts and review history. OpenRouter settings
remain in the environment / ignored .env; secrets were not printed or changed.
