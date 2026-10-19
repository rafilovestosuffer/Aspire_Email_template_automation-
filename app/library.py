"""Read-only access to the available export. Never normalize the raw file."""
import csv
import io
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / 'data/raw/email_template.csv'


@lru_cache(maxsize=1)
def records():
    if not PATH.exists():
        return []
    csv.field_size_limit(10_000_000)
    raw = PATH.read_bytes()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('cp1252')
    with io.StringIO(text, newline='') as f:
        return [{'id': str(n), 'name': (row.get('Template Name') or '').strip() or f'Row {n}',
                 'subject': row.get('Email Subject') or '', 'html': row.get('Email body') or '',
                 'needs_recovery': len(row.get('Email body') or '') >= 32767}
                for n, row in enumerate(csv.DictReader(f), 2) if any(row.values())]
