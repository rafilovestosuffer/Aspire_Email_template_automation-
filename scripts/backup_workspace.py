"""Create a consistent local workspace backup without changing the source."""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = Path(os.environ.get('FACTORY_DB', root / 'data/workspace.sqlite3'))
if not source.is_file():
    raise SystemExit('Workspace database does not exist yet.')
destination = root / 'data/backups' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3')
destination.parent.mkdir(parents=True, exist_ok=True)
src = sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)
dst = sqlite3.connect(destination)
try:
    src.backup(dst)
    if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise SystemExit('Backup integrity check failed.')
finally:
    dst.close()
    src.close()
print(f'Backup verified: {destination}')
