"""Durable local review workspace; separate from the production Supabase schema."""
import json
import os
import sqlite3
from pathlib import Path
from uuid import uuid4
from contextlib import contextmanager
from datetime import datetime, timezone


@contextmanager
def connect():
    path = Path(os.environ.get('FACTORY_DB', Path(__file__).resolve().parents[1] / 'data/workspace.sqlite3'))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.executescript('''
      CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, parent_id TEXT, data TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS items_parent ON items(parent_id);
      CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, item_id TEXT NOT NULL,
        action TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
      CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
        BEGIN SELECT RAISE(ABORT, 'append-only'); END;
      CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
        BEGIN SELECT RAISE(ABORT, 'append-only'); END;
    ''')
    try:
        with db:
            yield db
    finally:
        db.close()


def save(item, parent_id=None):
    item = {**item, 'id': str(uuid4()), 'parent_id': parent_id, 'status': 'pending',
            'created_at': datetime.now(timezone.utc).isoformat()}
    with connect() as db:
        db.execute('INSERT INTO items VALUES (?,?,?)', (item['id'], parent_id, json.dumps(item)))
    return item


def get(item_id):
    with connect() as db:
        row = db.execute('SELECT data FROM items WHERE id=?', (item_id,)).fetchone()
    if not row:
        raise KeyError(item_id)
    return json.loads(row['data'])


def all_items():
    with connect() as db:
        return [json.loads(r['data']) for r in db.execute('SELECT data FROM items ORDER BY rowid')]


def review(item_id, status, actor):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT data FROM items WHERE id=?', (item_id,)).fetchone()
        if row is None:
            raise KeyError(item_id)
        item = json.loads(row['data'])
        if status == 'approved' and item['mode'] not in ('openrouter', 'source'):
            raise ValueError('Mock and failed outputs cannot be approved.')
        if status == 'approved' and item.get('parent_id'):
            parent = json.loads(db.execute('SELECT data FROM items WHERE id=?', (item['parent_id'],)).fetchone()['data'])
            if parent['status'] != 'approved':
                raise ValueError('The source must be approved first.')
        item.update(status=status, reviewed_by=actor, reviewed_at=datetime.now(timezone.utc).isoformat())
        db.execute('UPDATE items SET data=? WHERE id=?', (json.dumps(item), item_id))
        db.execute('INSERT INTO events(item_id,action,actor) VALUES (?,?,?)', (item_id, status, actor))
        # Revoking source approval also revokes all downstream approvals.
        if status != 'approved':
            for row in db.execute('SELECT id,data FROM items WHERE parent_id=?', (item_id,)).fetchall():
                child = json.loads(row['data'])
                child['status'] = 'pending'
                db.execute('UPDATE items SET data=? WHERE id=?', (json.dumps(child), row['id']))
                db.execute('INSERT INTO events(item_id,action,actor) VALUES (?,?,?)', (row['id'], 'source_review_revoked', actor))
    return item


def events(limit=100):
    with connect() as db:
        return [dict(row) for row in db.execute('SELECT * FROM events ORDER BY id DESC LIMIT ?', (limit,))]
