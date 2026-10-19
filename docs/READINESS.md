# Content Studio readiness — 2026-10-15

## Verdict

Local desktop workflow: **GO WITH WARNINGS** for small, supervised batches.
Shared production deployment / 500–1,000-template runs: **NO-GO**.
This is a local content review workspace, not yet a complete production service.

## Completed in this increment

- Reorganized interface into source preparation, scoped translation, and review/export.
- Separate Sources, Translations, and Activity views. No interleaved English/Bangla previews.
- Explicit source and translation approval labels; per-language review remains mandatory.
- Named drafts, status/search filters, selected-source export, and workspace pagination.
- Paginated library access across all 1,162 source rows; recovery-needed rows remain blocked.
- One preview mounted at a time instead of rendering every email iframe at startup.
- Sequential per-language requests, progress, stop-after-current-language, saved partial results.
- Failed outputs are labeled as failed, never displayed as successful translated previews.
- Retry creates a fresh pending attempt for rejected translations, retaining the rejected history.
- Generation lock prevents overlapping provider calls within the supported single-worker server.
- Review timestamps, append-only activity API, indexed parent lookup, linear workspace assembly.

## Verification evidence

| Check | Result |
|---|---|
| `python -m unittest discover -s tests -v` | 11 tests passed |
| `node --check app/static/console.js` | Passed |
| `python -m compileall -q app` | Passed |
| Real desktop UI | Existing sources and Bangla translations rendered in separate tabs |
| Isolated browser workflow | Saved neutral HTML, approved source, requested Bangla/German fixtures, approved Bangla |
| Provider failure | Simulated German failure clearly displayed; no approval control |
| Export download | Actual downloaded JSON inspected: exactly one approved Bangla fixture, no failed output, sendable=false |
| Persistence | Fresh browser tab recovered the fixture source and review decisions |
| Live provider linguistic quality | Not retested; no paid API calls in this audit |
| Mobile breakpoint | CSS implemented; browser viewport override did not take effect, so NOT VERIFIED |
| 500–1,000 load test / crash recovery | NOT VERIFIED; current architecture is not the scale target |

The disposable browser server is `tests/serve_ui_fixture.py`, uses a temporary
database, mocks the provider, and binds to port 8001. It must never be deployed.

## Production blockers and required order

1. Complete the content contract: subject translation; typed brand/logo/color
   binding; normalized source provenance; canonical variables; recovered raw
   bodies. Company name currently supplies model context, not guaranteed brand
   replacement. Existing translations demonstrate that a model can retain a
   source brand, so human review is still required.
2. Implement authenticated users, reviewer roles, organization boundaries, and
   engagement authorization. Current reviewer names are self-asserted labels.
   Keep this server bound to localhost until these controls are enforced.
3. Move batch execution to persisted jobs and dedicated workers with leases,
   idempotency keys, retry/backoff, provider limits, budgets, cancellation, and
   crash recovery. Closing the current browser interrupts the client-side batch
   loop; completed records remain saved. The generation lock is process-local.
4. Add server-side workspace pagination and lazy body retrieval. Current cards
   are paginated visually but the full workspace payload is still downloaded.
5. Implement transactional, idempotent Supabase publication with the existing
   schema, content/version hashes, provenance, and approved-only constraints.
   Confirm the target project and the consumer's required delivery format.
6. Add deployment configuration, dependency lock, HTTPS/reverse proxy, secrets
   management, monitoring, recovery tests, CI and staging. Verify restore from
   backup and run a measured 1,000-source × target-language load test.

## Operating and recovery instructions

Install dependencies using the same Python interpreter used to launch the app.

```powershell
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
```

Run one worker locally. Development auto-reload is not a production deployment.
If routes return 404 after a code update, restart the server, then refresh the
browser. Never delete `data/workspace.sqlite3` to troubleshoot the interface.
Back it up with `python scripts/backup_workspace.py`; this uses SQLite's online
backup API and does not copy a potentially incomplete live database file.

Suggested workflow: load source → name draft → save → preview and approve source
→ select it → select languages → translate → open Translations → review each
language → select sources for export → download approved JSON.

No production-ready or scale-ready claim should be made until the blockers above
are implemented and independently verified. The next engineering priority is
the content contract, followed by authenticated review and durable batch jobs.
