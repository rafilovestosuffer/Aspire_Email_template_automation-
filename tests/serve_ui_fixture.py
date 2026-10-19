"""Disposable browser QA server. No provider requests and no production data.

Run: python -m tests.serve_ui_fixture (or python tests/serve_ui_fixture.py).
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
scratch = tempfile.TemporaryDirectory(prefix='asat-ui-test-')
os.environ['FACTORY_DB'] = str(Path(scratch.name) / 'workspace.sqlite3')
os.environ['OPENROUTER_API_KEY'] = ''

from app.main import app
from app import translate


def fixture_translation(html, company, language):
    if language == 'German':
        return {'html': html, 'mode': 'error', 'model': 'TEST FIXTURE', 'error': 'Simulated provider failure'}
    return {'html': html.replace('Hello', 'হ্যালো'), 'mode': 'openrouter', 'model': 'TEST FIXTURE'}


translate.translate_and_brand = fixture_translation
translate.make_variant = lambda html, company, index: {'html': html, 'mode': 'mock', 'model': 'TEST FIXTURE'}

if __name__ == '__main__':
    import uvicorn
    try:
        uvicorn.run(app, host='127.0.0.1', port=8001)
    finally:
        scratch.cleanup()
