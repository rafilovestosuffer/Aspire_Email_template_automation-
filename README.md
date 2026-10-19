# ASAT Content Factory

The interface is now **ASAT Content Studio**, with separate source/translation
review views, scoped batch actions, activity history and approved-only exports.
See [Readiness and operating guide](docs/READINESS.md) for verified behavior,
known limitations, backup instructions and the production scaling gates.

Current scope, verified gaps and next steps: [Project status](docs/PROJECT-STATUS.md).
The console now includes library search, durable local reviews, translation
approval and approved JSON export. Run on localhost; multi-user authentication
and production database publishing are still pending.

Checks: `python -m unittest discover -s tests -v` (requires `httpx`).

Authorized security-awareness-training (SAT) content factory. Strategy lives in the roadmap doc (Claude Doc) and in `PRD.md` / `ARCHITECTURE.md` / `TASKS.md`. Controls summary in `CLAUDE.md`.

## Generate Console (first UI)

Paste an email template → pick target languages → enter a company name → get a personalized, localized preview per language.

### Run

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
```

Open http://localhost:8000  (or use the `generate-console` entry in `.claude/launch.json`).

Use the same Python environment for installation and startup (`python -m pip
install -r requirements.txt`). The development launcher reloads backend changes.
If the page reports a missing server feature, stop the old server and restart
with the command above: refreshing the browser alone cannot reload Python routes.

### Real translation (OpenRouter)

Without a key it runs in **MOCK mode** — the pipeline works but text isn't actually translated. To enable real translation, set the key in your environment and restart:

```bash
export OPENROUTER_API_KEY=...            # Windows: set OPENROUTER_API_KEY=...
export OPENROUTER_MODEL=openai/gpt-4o-mini   # optional
```

The key is read from the environment only — never hard-code or commit it.

### How it works

- `app/main.py` — FastAPI: `/api/languages`, `/api/generate`, serves the UI.
- `app/translate.py` — translate + re-brand one template into one language. Masks `{{placeholders}}` so recipient/link tokens are never translated or filled; preserves HTML.
- `app/languages.py` — the tiered language list (extend freely).
- `app/static/index.html` — the single-page console.
- `app/design.py` — curated MJML redesign archetypes + palettes (layout only).
- `app/mjml_engine.py` — local MJML→HTML compile (`mjml-python`; offline, no Node).
- `app/htmlsafe.py` — allow-list injection gate for redesign output (fail-closed).

### Redesign mode

In **step 01 → "create variants"**, choose **Redesign layout** (vs Vary wording). Instead of reusing the source's raw HTML, the content is re-rendered in a clean, perfectly-aligned email design — one of four curated archetypes (plain memo, branded notice, modern card, classic corporate), rotated with a palette per version, compiled by MJML (`mjml-python`, local, no Node).

- The model only extracts the copy into slots; **our** MJML templates own the layout.
- `{{placeholders}}` are masked and **never resolved**; the source's action link is routed to the new button and must survive.
- Every redesign passes an **injection gate** (`app/htmlsafe.py`) before it is stored; fail-closed to a draft, mock results are not approvable, nothing is sent.
- Needs the engine: `pip install -r requirements.txt` (installs `mjml-python`).

## Phase 0 (data foundation)

- `supabase/migrations/0001_phase0_schema.sql` — schema (`supabase db push` or `psql -f`).
- `scripts/import_workbook.py` — CSV → `source_templates` (verbatim; `--dry-run` or live).
- `scripts/audit_vocab.py` — vocabulary reconciliation (Block 4).
- `scripts/profile_email_csv.py` — count/profile a sheet export.
- `docs/controlled-lists-and-variables.md` — controlled vocabulary + `{{variable}}` standard.

## Controls (non-negotiable)

Simulation content only; **nothing is sent from here**. Recipient and link tokens stay as placeholders. See `CLAUDE.md`.
