# ASAT Content Studio

Authorized **security-awareness-training (SAT)** content studio for Aspire. It
produces phishing-simulation email templates for clients' *own* employees under
per-engagement authorization. The artifacts resemble a phishing kit; the control
layer (see [Safety invariants](#safety-invariants)) is what keeps it legitimate,
so those controls are load-bearing and must be preserved in any integration.

Current scope is a **single-worker localhost review studio**: paste or load a base
template → vary wording or redesign the layout → translate → human-review and
approve → export approved content. It does **not** send mail, resolve recipient
PII, or deploy itself.

## Requirements

- Python 3.10+
- Dependencies in `requirements.txt` (runtime) and `requirements-dev.txt` (tests)

## Setup & run

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000.

## Configuration

Copy `.env.example` to `.env` and fill in the values. All credentials are
**server-side only** — they are never returned by the API or sent to the browser.

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | OpenRouter key for translation/redesign. Unset → **MOCK mode** (pipeline runs, text is not actually translated). |
| `OPENROUTER_MODEL` | Default model (`openai/gpt-4.1-mini`). |
| `OPENROUTER_TRANSLATION_MODEL` / `OPENROUTER_DESIGN_MODEL` | Per-task overrides. |
| `DATABASE_URL` | Postgres/Supabase connection for the publish path. Unset → publish runs **dry-run** and writes nothing. |

Restart the server after changing configuration.

## Tests

```bash
python -m unittest discover -s tests -v   # 36 tests
python -m compileall -q app scripts
```

The suite covers placeholder integrity, immutable-HTML guarantees, layout/palette
combinations, provider-error fail-closed behavior, and the approval/audit workflow.

## HTTP API

All endpoints are under `/api/` (served by `app.main:app`):

| Method | Path | Purpose |
|---|---|---|
| GET  | `/api/health` | Liveness + provider mode (real vs mock). |
| GET  | `/api/languages` | Supported target languages. |
| POST | `/api/generate` | Translate a variant into selected languages. |
| POST | `/api/variants` | Create wording variants of a source. |
| POST | `/api/redesign` | Compile curated MJML redesigns (local, offline). |
| GET  | `/api/library`, `/api/library/{source_id}` | Browse the template library. |
| GET  | `/api/workspace` | Current review workspace state. |
| POST | `/api/seeds` | Seed workspace content. |
| POST | `/api/items/{item_id}/review` | Approve/reject an item (append-only audit). |
| GET  | `/api/activity` | Review activity history. |
| GET  | `/api/export` | Export approved-only content as JSON. |
| POST | `/api/publish` | Publish approved content to Postgres (dry-run unless `DATABASE_URL` set). |

## Project layout

```
app/                 FastAPI backend + static Content Studio UI
  main.py            app factory + routes
  translate.py       translation / wording / redesign orchestration
  design.py          curated MJML design archetypes (layout is ours, not the model's)
  mjml_engine.py     local MJML → bulletproof HTML compilation (no Node, no network)
  provider.py        server-only OpenRouter client (bounded, sanitized)
  text_slots.py      visible-text replacement that leaves HTML bytes intact
  store.py           durable local review workspace (SQLite)
  publish.py         publish approved content to the Supabase/Postgres schema
  library.py, languages.py, htmlsafe.py
scripts/             import / normalize / audit / backup tooling
tests/               unittest suite
supabase/migrations/ schema contract (0001_phase0_schema.sql)
```

## Integration notes

For merging into the company main repo, two options:

1. **Standalone service** — run `app.main:app` behind the main app and call the
   `/api/*` endpoints. Simplest; keeps the control boundary intact.
2. **Mounted sub-app** — import `app.main:app` and mount it on a path in the
   parent FastAPI/ASGI application.

Provision the database by applying `supabase/migrations/0001_phase0_schema.sql`.
Schema changes go in a **new** migration (`0002_*`), never by editing a frozen one.

## Safety invariants

These are enforced in the schema and code. **Do not relax them** when integrating:

1. **The factory never emits sendable content.** The `factory_never_sendable`
   database CHECK stays in force; nothing becomes sendable here.
2. **Recipient PII is never resolved or stored.** `first_name`, `email`, etc.
   remain placeholders, merged only by a downstream sender.
3. **Link/engagement variables are system-owned.** Authors cannot set
   `phishing_link`, `engagement_id`, `tracking_pixel`, or `training_url`.
4. **The audit log is append-only.** No UPDATE/DELETE on `review_events`;
   corrections are new rows.
5. **The immutable source is never edited.** Re-run normalization from source.
6. **Controlled vocabulary only.** New variables/categories arrive via a new
   migration, never ad hoc.
7. **No live credentials, deploy, or sending** are performed by this layer.

> Email-client fidelity (Gmail/Outlook/mobile) is **not** verified; compilation
> and HTML checks do not establish client rendering. Before any shared or public
> deployment, add authentication, tenant isolation, durable jobs, production
> secret management, HTTPS, and backups.
