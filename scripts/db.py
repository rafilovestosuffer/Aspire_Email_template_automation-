"""Lazy Postgres / Supabase connection. psycopg2 is imported only when a live
connection is actually needed, so --dry-run works with no driver installed.

Set DATABASE_URL to the Supabase project's Postgres connection string, e.g.:
  export DATABASE_URL="postgresql://postgres:<pw>@db.<ref>.supabase.co:5432/postgres"
"""
import os


def connect(url=None):
    url = url or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit(
            "DATABASE_URL not set. Use the Supabase project's Postgres connection "
            "string, or pass --dry-run to run without a database."
        )
    try:
        import psycopg2  # lazy; see requirements.txt
    except ImportError:
        raise SystemExit("psycopg2 not installed. Run: pip install -r requirements.txt")
    return psycopg2.connect(url)
