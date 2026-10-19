"""Publish approved workspace content into the Supabase / Postgres schema (migration 0001).

Dry-run (default, or whenever DATABASE_URL is unset) computes the plan and writes
NOTHING. A live run writes templates + template_versions + translations in one
transaction, idempotently (re-publish is safe).

Control: nothing published is sendable. We only write masters/versions/translations,
never render_outputs, so the schema's `factory_never_sendable` CHECK stays in force.
"""
import hashlib
import os
import re

from . import store


def _slug(title, item_id):
    base = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")[:60] or "template"
    return f"{base}-{item_id[:8]}"


def _plan():
    """Approved sources + their approved, real (openrouter) translations -> publish rows."""
    items = store.all_items()
    by_parent = {}
    for i in items:
        if i["parent_id"]:
            by_parent.setdefault(i["parent_id"], []).append(i)
    plan = []
    for s in items:
        if s["parent_id"] or s["status"] != "approved":
            continue
        locs = [t for t in by_parent.get(s["id"], [])
                if t["status"] == "approved" and t["mode"] == "openrouter"]
        plan.append({
            "source_id": s["id"],
            "slug": _slug(s.get("title") or "", s["id"]),
            "company": s.get("company", ""),
            "body_hash": hashlib.sha256((s.get("html") or "").encode("utf-8", "replace")).hexdigest(),
            "locales": [{"code": t["code"], "name": t.get("name", t["code"])} for t in locs],
            "_source": s,
            "_locs": locs,
        })
    return plan


def summary(plan):
    return {
        "sendable": False,
        "templates": len(plan),
        "translations": sum(len(p["locales"]) for p in plan),
        "has_db": bool(os.environ.get("DATABASE_URL")),
        "plan": [{k: v for k, v in p.items() if not k.startswith("_")} for p in plan],
    }


def publish(dry=True):
    plan = _plan()
    if dry or not os.environ.get("DATABASE_URL"):
        return {"dry_run": True, **summary(plan)}

    import psycopg2
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    written = {"templates": 0, "versions": 0, "translations": 0}
    try:
        with conn, conn.cursor() as cur:
            for p in plan:
                s = p["_source"]
                cur.execute(
                    """insert into templates (slug, channel, status, canonical_locale, content_hash)
                       values (%s, 'email', 'active', 'en', %s)
                       on conflict (slug) do update set content_hash = excluded.content_hash
                       returning id""",
                    (p["slug"], p["body_hash"]),
                )
                template_id = cur.fetchone()[0]
                written["templates"] += 1
                cur.execute(
                    """insert into template_versions
                         (template_id, version_no, body, format, review_status, approved_by, is_current)
                       values (%s, 1, %s, 'html', 'approved', %s, true)
                       on conflict (template_id, version_no)
                         do update set body = excluded.body, review_status = 'approved',
                                       approved_by = excluded.approved_by
                       returning id""",
                    (template_id, s.get("html", ""), s.get("reviewed_by")),
                )
                version_id = cur.fetchone()[0]
                written["versions"] += 1
                for t in p["_locs"]:
                    cur.execute(
                        """insert into translations
                             (source_version_id, locale, body, source_version_hash, origin, status, approved_by)
                           values (%s, %s, %s, %s, 'mt_postedited', 'approved', %s)
                           on conflict (source_version_id, locale)
                             do update set body = excluded.body, status = 'approved',
                                           approved_by = excluded.approved_by""",
                        (version_id, t["code"], t["html"], p["body_hash"], t.get("reviewed_by")),
                    )
                    written["translations"] += 1
                cur.execute(
                    "insert into review_events (subject_type, subject_id, action, actor) "
                    "values ('template', %s, 'publish', %s)",
                    (template_id, "publish"),
                )
    finally:
        conn.close()
    return {"dry_run": False, "sendable": False, "written": written, "templates": len(plan)}
