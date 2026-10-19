"""Allow-list HTML safety gate for Redesign mode.

Redesign makes the pipeline produce *fresh* email HTML (our curated MJML compiled
to HTML). Unlike the faithful variant/translation paths - which reuse the source's
own HTML - this output must pass a hostile-render gate before it is ever stored,
exactly as Phase-0 Block 6 describes. The gate is fail-closed: any violation makes
the caller drop the redesign to an error draft; unsafe HTML is never saved.

What it enforces on the compiled, token-restored HTML:
  * only an allow-list of inert email tags (no <script>/<iframe>/<form>/<input>/...);
  * no event-handler attributes (on*);
  * URL attributes resolve only to https, mailto:, tel:, an in-page #anchor, or a
    controlled {{placeholder}} / mask sentinel - never javascript:/vbscript:/data:/http:;
  * a raw-string backstop for a few dangerous substrings, even inside comments.

Calibrated against mjml-python 1.4.1 output (meta/style/xmlns + MSO conditional
comments all pass). The model never authors this HTML; it only supplies text that
is HTML-escaped into slots - so injected markup cannot survive. This gate is the
second line of defense.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

# Inert tags MJML emits + common safe inline/table tags. Anything else is rejected.
ALLOWED_TAGS = {
    "html", "head", "title", "meta", "style", "body",
    "div", "span", "p", "br", "hr", "center", "font",
    "a", "img",
    "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption", "col", "colgroup",
    "b", "strong", "i", "em", "u", "small", "sup", "sub",
    "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "blockquote",
}

URL_ATTRS = {"href", "src", "background", "action", "formaction", "poster", "cite", "xlink:href"}

# Case-insensitive raw substrings rejected anywhere (belt-and-suspenders, incl. comments/CSS).
RAW_DENY = (
    "<script", "</script", "javascript:", "vbscript:", "<iframe", "<object",
    "<embed", "<form", "onerror=", "onload=", "onclick=", "onmouseover=", "expression(",
    "data:text/html",
)

_SENTINEL = re.compile(r"^⦑PH\d+⦒$")
_TOKEN = re.compile(r"^\{\{\s*[.#/A-Za-z0-9_\-]+\s*\}\}$")


class UnsafeHtml(ValueError):
    """Raised when the compiled HTML fails the safety gate."""


def _url_ok(value: str) -> bool:
    v = (value or "").strip()
    if v == "" or v.startswith("#"):
        return True
    if _TOKEN.match(v) or _SENTINEL.match(v):
        return True
    low = v.lower()
    return low.startswith(("https://", "mailto:", "tel:"))


class _Checker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.bad: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            self.bad.append(f"disallowed tag <{tag}>")
            return
        for k, v in attrs:
            kl = k.lower()
            if kl.startswith("on"):
                self.bad.append(f"event-handler attribute {k} on <{tag}>")
            if kl in URL_ATTRS and not _url_ok(v):
                self.bad.append(f"unsafe URL in {k} on <{tag}>: {(v or '')[:40]!r}")

    handle_startendtag = handle_starttag


def check(html: str):
    """Return (ok: bool, reasons: list[str]) without raising."""
    reasons: list[str] = []
    low = (html or "").lower()
    for bad in RAW_DENY:
        if bad in low:
            reasons.append(f"forbidden pattern {bad!r}")
    checker = _Checker()
    checker.feed(html or "")
    reasons.extend(checker.bad)
    return (not reasons), reasons


def assert_safe(html: str) -> str:
    """Return html unchanged if safe; raise UnsafeHtml(reason) otherwise."""
    ok, reasons = check(html)
    if not ok:
        raise UnsafeHtml("; ".join(reasons[:5]))
    return html
