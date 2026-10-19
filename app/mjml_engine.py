"""Local MJML -> HTML compilation for Redesign mode (offline; no Node, no network).

Redesign compiles OUR curated MJML layout templates (see app/design.py) into
bulletproof, cross-client HTML. MJML is the engine that makes the output
"perfectly aligned" - it handles the Outlook/table quirks that break hand-written
email HTML.

Engine: `mjml-python` (Rust-backed; prebuilt wheels incl. Windows x86-64):
    from mjml import mjml2html   ->   mjml2html(src, disable_comments=True) -> "<html>..."
Documented fallback if that wheel ever fails to install on this machine: `mrml`
(wire it in _resolve() after confirming its API against its docs).

Control: if no engine imports, available() is False and callers
(translate.make_redesign) degrade to the existing mock/error path - a missing
engine never crashes the app and never produces an approvable result.
"""
from __future__ import annotations

_engine = None        # resolved engine name, or "unavailable"
_compile = None       # callable(str) -> str


def _resolve():
    global _engine, _compile
    if _engine is not None:
        return
    try:
        from mjml import mjml2html
    except Exception:
        _engine = "unavailable"
        return

    def _c(mjml_src: str) -> str:
        return mjml2html(mjml_src, disable_comments=True)

    _compile, _engine = _c, "mjml-python"


def available() -> bool:
    """True if a local MJML engine is importable."""
    _resolve()
    return _engine != "unavailable"


def engine_version() -> str:
    """Pinned-engine identity string, stored on each redesign for reproducibility."""
    _resolve()
    if _engine == "unavailable":
        return "unavailable"
    try:
        import importlib.metadata as md
        return f"{_engine}=={md.version('mjml-python')}"
    except Exception:
        return _engine


def compile_mjml(mjml_src: str) -> str:
    """Compile an MJML string to HTML.

    Raises if no engine is installed or the MJML is invalid; callers treat any
    exception as fail-closed (mock/error) and never crash the app.
    """
    _resolve()
    if _engine == "unavailable":
        raise RuntimeError("No local MJML engine installed (pip install mjml-python).")
    return _compile(mjml_src)
