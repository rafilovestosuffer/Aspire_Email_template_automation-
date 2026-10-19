"""FastAPI backend for the Generate Console.
Run from the project root:  python -m uvicorn app.main:app --port 8000 --reload
"""
import os
from typing import List
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from threading import Lock
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal


def _load_dotenv():
    """Minimal .env loader (no dependency): populate os.environ from project-root .env."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass


_load_dotenv()

from . import languages, translate, store, library, publish, mjml_engine  # noqa: E402

app = FastAPI(title="ASAT Content Factory - Generate Console")

HERE = os.path.dirname(os.path.abspath(__file__))
generation_lock = Lock()


class GenerateRequest(BaseModel):
    variant_id: str
    languages: List[str] = Field(min_length=1, max_length=30)


@app.get("/api/languages")
def list_languages():
    return languages.LANGUAGES


@app.get("/api/health")
def health():
    return {"ok": True, "has_key": bool(os.environ.get("OPENROUTER_API_KEY")),
            "has_engine": mjml_engine.available(), "engine": mjml_engine.engine_version()}


@app.post("/api/generate")
def generate(req: GenerateRequest):
    # Local single-worker deployment: avoid overlapping billable requests.
    if not generation_lock.acquire(blocking=False):
        raise HTTPException(409, 'Another generation is running. Wait for it to finish and retry.')
    try:
        return generate_locales(req)
    finally:
        generation_lock.release()


def generate_locales(req):
    source = lookup(req.variant_id)
    if source['parent_id'] or source['status'] != 'approved':
        raise HTTPException(409, 'An approved source is required.')
    if any(code not in languages.BY_CODE for code in req.languages):
        raise HTTPException(422, 'Unsupported language code.')
    results = []
    existing = {i['code']: i for i in store.all_items() if i['parent_id'] == source['id'] and i['mode'] == 'openrouter' and i['status'] != 'rejected'}
    for code in dict.fromkeys(req.languages):
        if code in existing:
            results.append(existing[code])
            continue
        info = languages.BY_CODE[code]
        out = translate.translate_and_brand(source['html'], source['company'], info['name'])
        results.append(store.save({"code": code, "name": info['name'], "rtl": info['rtl'], **out}, source['id']))
    return {
        "company": source['company'],
        "count": len(results),
        "has_key": bool(os.environ.get("OPENROUTER_API_KEY")),
        "results": results,
    }


class VariantRequest(BaseModel):
    template_html: str = Field(min_length=1, max_length=200000)
    company_name: str = Field(default='', max_length=200)
    amount: int = Field(default=3, ge=1, le=8)
    title: str = Field(default='', max_length=200)
    humanize: bool = True                                   # second pass: read as human-written
    source_id: str = Field(default='', max_length=64)       # the saved source these variants belong to


@app.post("/api/variants")
def variants(req: VariantRequest):
    if not generation_lock.acquire(blocking=False):
        raise HTTPException(409, 'Another generation is running. Wait for it to finish and retry.')
    try:
        return generate_variants(req)
    finally:
        generation_lock.release()


def generate_variants(req):
    n = max(1, min(req.amount, 8))          # cap to keep cost/time bounded
    group = req.source_id or ('grp-' + uuid4().hex[:12])    # group these variants (+ their saved source) as one draft
    out = []
    for k in range(n):
        r = translate.make_variant(req.template_html, req.company_name, k, humanize=req.humanize)
        out.append(store.save({"index": k + 1, 'company': req.company_name, 'title': req.title,
                               'group_id': group, 'of_source': req.source_id or None, **r}))
    return {
        "count": len(out),
        "has_key": bool(os.environ.get("OPENROUTER_API_KEY")),
        "variants": out,
    }


@app.post("/api/redesign")
def redesign(req: VariantRequest):
    """Generate redesign variants: same scenario/content, re-rendered in curated,
    aligned archetypes (MJML). Same lock/draft shape as /api/variants; DRAFT only."""
    if not generation_lock.acquire(blocking=False):
        raise HTTPException(409, 'Another generation is running. Wait for it to finish and retry.')
    try:
        return generate_redesigns(req)
    finally:
        generation_lock.release()


def generate_redesigns(req):
    n = max(1, min(req.amount, 8))          # cap to keep cost/time bounded
    group = req.source_id or ('grp-' + uuid4().hex[:12])    # group redesigns (+ their saved source) as one draft
    out = []
    for k in range(n):
        r = translate.make_redesign(req.template_html, req.company_name, k, humanize=req.humanize)
        out.append(store.save({"index": k + 1, 'company': req.company_name, 'title': req.title,
                               'group_id': group, 'of_source': req.source_id or None, **r}))
    return {
        "count": len(out),
        "has_key": bool(os.environ.get("OPENROUTER_API_KEY")),
        "has_engine": mjml_engine.available(),
        "variants": out,
    }


def lookup(item_id):
    try:
        return store.get(item_id)
    except KeyError:
        raise HTTPException(404, 'Item not found.')


class ReviewRequest(BaseModel):
    status: Literal['approved', 'rejected']
    actor: str = Field(min_length=1, max_length=100, pattern=r'\S')


@app.post('/api/items/{item_id}/review')
def review(item_id: str, req: ReviewRequest):
    lookup(item_id)
    try:
        return store.review(item_id, req.status, req.actor.strip())
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.get('/api/workspace')
def workspace():
    items = store.all_items()
    children = {}
    for item in items:
        children.setdefault(item['parent_id'], []).append(item)
    return {'variants': [{**i, 'locales': children.get(i['id'], [])}
                         for i in items if not i['parent_id']]}


@app.post('/api/seeds')
def seed(req: VariantRequest):
    return store.save({'index': 1, 'company': req.company_name,
                       'html': req.template_html, 'mode': 'source', 'model': None, 'title': req.title})


@app.get('/api/export')
def export(source_ids: List[str] = Query(default=[])):
    items = store.all_items()
    approved_sources = {i['id'] for i in items if not i['parent_id'] and i['status'] == 'approved'
                        and (not source_ids or i['id'] in source_ids)}
    return {'format': 'asat-review-export-v1', 'sendable': False,
            'sources': [i for i in items if i['id'] in approved_sources],
            'items': [i for i in items if i['parent_id'] in approved_sources
                      and i['status'] == 'approved' and i['mode'] == 'openrouter']}


@app.get('/api/library')
def list_library(q: str = '', offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=100)):
    rows = library.records()
    matches = [r for r in rows if q.casefold() in (r['name'] + ' ' + r['subject']).casefold()]
    return {'total': len(rows), 'matched': len(matches), 'offset': offset, 'limit': limit,
            'needs_recovery': sum(r['needs_recovery'] for r in rows),
            'items': [{k:v for k,v in r.items() if k != 'html'} for r in matches[offset:offset+limit]]}


@app.get('/api/activity')
def activity():
    return {'events': store.events()}


@app.get('/api/library/{source_id}')
def library_item(source_id: str):
    for row in library.records():
        if row['id'] == source_id:
            if row['needs_recovery']:
                raise HTTPException(409, 'This source reached the spreadsheet cell limit. Recover the full HTML first.')
            return row
    raise HTTPException(404, 'Source not found.')


class PublishRequest(BaseModel):
    dry_run: bool = True


@app.post('/api/publish')
def publish_endpoint(req: PublishRequest):
    """Publish approved content to Supabase. dry_run=true (default) writes nothing;
    a live run needs DATABASE_URL set. Nothing published is sendable."""
    return publish.publish(dry=req.dry_run)


# serve the single-page UI (mounted last so /api/* routes win)
app.mount("/", StaticFiles(directory=os.path.join(HERE, "static"), html=True), name="ui")
# (publish endpoint wired above)
