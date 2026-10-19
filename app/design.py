"""Curated email DESIGN archetypes for Redesign mode.

The layouts here are OURS - fixed, safe, hand-tuned MJML that compiles (via
app/mjml_engine) to bulletproof, perfectly-aligned, cross-client HTML. The model
never authors layout; it only supplies the extracted CONTENT (see
translate.make_redesign), which we drop into these slots, HTML-escaped. We rotate
archetype + palette per variant so a set of redesigns reads as genuinely different
real-world emails, not one repeated template.

This module is pure presentation: it knows nothing about {{placeholders}} or
masking. Content strings may contain opaque mask sentinels; escaping leaves them
intact, and translate.make_redesign restores the real tokens AFTER compilation.
So nothing here resolves or fills a {{variable}}.

`content` keys (all strings unless noted):
  brand, preheader, headline, greeting, body_blocks (list[str]),
  cta_label, cta_href (a controlled link token/sentinel - inserted verbatim),
  footer_note.
"""
from __future__ import annotations

from html import escape

FONT = "Helvetica, Arial, sans-serif"
SERIF = "Georgia, 'Times New Roman', serif"

# Mature, accessible color sets (WCAG-reasonable text/background contrast).
PALETTES = [
    {"name": "indigo", "bg": "#eef1f7", "panel": "#ffffff", "ink": "#1b2a4a", "muted": "#5b6b82",
     "bar": "#1f3a6b", "barink": "#ffffff", "accent": "#2f6bff", "accentink": "#ffffff", "line": "#e4e9f2"},
    {"name": "slate", "bg": "#f1f3f5", "panel": "#ffffff", "ink": "#1f2937", "muted": "#616b78",
     "bar": "#111827", "barink": "#ffffff", "accent": "#334155", "accentink": "#ffffff", "line": "#e5e7eb"},
    {"name": "teal", "bg": "#eef5f4", "panel": "#ffffff", "ink": "#12343b", "muted": "#51696d",
     "bar": "#0f766e", "barink": "#ffffff", "accent": "#0d9488", "accentink": "#ffffff", "line": "#d9e6e4"},
    {"name": "maroon", "bg": "#f5f1f0", "panel": "#ffffff", "ink": "#2a1a1d", "muted": "#72615f",
     "bar": "#7c2d33", "barink": "#ffffff", "accent": "#9b2c2c", "accentink": "#ffffff", "line": "#ece2e1"},
]


# --- small slot helpers -------------------------------------------------------

def _head(content, palette, font=FONT):
    pre = escape(content.get("preheader", "") or "")
    return (
        "<mj-head>"
        f"<mj-preview>{pre}</mj-preview>"
        "<mj-attributes>"
        f'<mj-all font-family="{font}"/>'
        f'<mj-text font-size="15px" color="{palette["ink"]}" line-height="1.6"/>'
        "</mj-attributes>"
        "</mj-head>"
    )


def _paras(blocks, align="left"):
    out = []
    for b in (blocks or []):
        b = escape(b or "").strip()
        if b:
            out.append(f'<mj-text align="{align}" padding="0 0 14px">{b}</mj-text>')
    return "".join(out)


def _button(content, palette, *, radius="6px", align="left"):
    href, label = content.get("cta_href"), escape(content.get("cta_label", "") or "")
    if not href or not label:
        return ""
    return (
        f'<mj-button href="{href}" align="{align}" background-color="{palette["accent"]}" '
        f'color="{palette["accentink"]}" border-radius="{radius}" font-size="15px" '
        f'font-weight="600" inner-padding="13px 26px" padding="18px 0 6px">{label}</mj-button>'
    )


def _text_link(content, palette):
    href, label = content.get("cta_href"), escape(content.get("cta_label", "") or "")
    if not href or not label:
        return ""
    return (
        '<mj-text padding="16px 0 0">'
        f'<a href="{href}" style="color:{palette["accent"]};font-weight:600;text-decoration:underline">{label}</a>'
        "</mj-text>"
    )


# --- archetypes (each: (content, palette) -> mjml string) ---------------------

def _plain_memo(content, palette):
    """A minimal internal-looking note: no brand bar, plain text, an inline link."""
    headline = escape(content.get("headline", "") or "")
    greeting = escape(content.get("greeting", "") or "")
    footer = escape(content.get("footer_note", "") or "")
    return (
        "<mjml>" + _head(content, palette) +
        '<mj-body background-color="#ffffff" width="600px">'
        '<mj-section padding="26px 26px 4px"><mj-column>'
        + (f'<mj-text font-size="16px" font-weight="700" padding="0 0 12px">{headline}</mj-text>' if headline else "")
        + (f'<mj-text padding="0 0 12px">{greeting}</mj-text>' if greeting else "")
        + _paras(content.get("body_blocks"))
        + _text_link(content, palette)
        + "</mj-column></mj-section>"
        + (
            '<mj-section padding="4px 26px 26px"><mj-column>'
            f'<mj-divider border-width="1px" border-color="{palette["line"]}" padding="12px 0"/>'
            f'<mj-text font-size="12px" color="{palette["muted"]}">{footer}</mj-text>'
            "</mj-column></mj-section>"
            if footer else ""
        )
        + "</mj-body></mjml>"
    )


def _branded_notice(content, palette):
    """Classic transactional: colored brand bar, white card, headline, button, footer."""
    brand = escape(content.get("brand", "") or "")
    headline = escape(content.get("headline", "") or "")
    greeting = escape(content.get("greeting", "") or "")
    footer = escape(content.get("footer_note", "") or "")
    return (
        "<mjml>" + _head(content, palette) +
        f'<mj-body background-color="{palette["bg"]}" width="600px">'
        f'<mj-section background-color="{palette["bar"]}" padding="18px 24px"><mj-column>'
        f'<mj-text color="{palette["barink"]}" font-size="18px" font-weight="700">{brand}</mj-text>'
        "</mj-column></mj-section>"
        f'<mj-section background-color="{palette["panel"]}" padding="28px 24px"><mj-column>'
        + (f'<mj-text font-size="20px" font-weight="700" padding="0 0 14px">{headline}</mj-text>' if headline else "")
        + (f'<mj-text padding="0 0 12px">{greeting}</mj-text>' if greeting else "")
        + _paras(content.get("body_blocks"))
        + _button(content, palette)
        + "</mj-column></mj-section>"
        f'<mj-section padding="10px 24px 26px"><mj-column>'
        f'<mj-text font-size="12px" color="{palette["muted"]}" align="center">{footer}</mj-text>'
        "</mj-column></mj-section>"
        "</mj-body></mjml>"
    )


def _modern_card(content, palette):
    """Modern minimal: centered, spacious, uppercase brand kicker, pill button."""
    brand = escape(content.get("brand", "") or "")
    headline = escape(content.get("headline", "") or "")
    greeting = escape(content.get("greeting", "") or "")
    footer = escape(content.get("footer_note", "") or "")
    return (
        "<mjml>" + _head(content, palette) +
        f'<mj-body background-color="{palette["bg"]}" width="600px">'
        '<mj-section padding="26px 0 4px"><mj-column>'
        f'<mj-text align="center" color="{palette["muted"]}" font-size="12px" '
        f'letter-spacing="2px" text-transform="uppercase">{brand}</mj-text>'
        "</mj-column></mj-section>"
        f'<mj-section background-color="{palette["panel"]}" padding="34px 30px"><mj-column>'
        + (f'<mj-text align="center" font-size="23px" font-weight="700" padding="0 0 16px">{headline}</mj-text>' if headline else "")
        + (f'<mj-text align="center" padding="0 0 12px">{greeting}</mj-text>' if greeting else "")
        + _paras(content.get("body_blocks"), align="center")
        + _button(content, palette, radius="24px", align="center")
        + "</mj-column></mj-section>"
        f'<mj-section padding="14px 24px 28px"><mj-column>'
        f'<mj-text font-size="12px" color="{palette["muted"]}" align="center">{footer}</mj-text>'
        "</mj-column></mj-section>"
        "</mj-body></mjml>"
    )


def _corporate(content, palette):
    """Classic corporate: serif brand + headline, rule lines, formal footer."""
    brand = escape(content.get("brand", "") or "")
    headline = escape(content.get("headline", "") or "")
    greeting = escape(content.get("greeting", "") or "")
    footer = escape(content.get("footer_note", "") or "")
    return (
        "<mjml>" + _head(content, palette) +
        f'<mj-body background-color="{palette["bg"]}" width="600px">'
        f'<mj-section background-color="{palette["panel"]}" padding="26px 30px 4px"><mj-column>'
        f'<mj-text font-family="{SERIF}" font-size="20px" font-weight="700" color="{palette["bar"]}">{brand}</mj-text>'
        f'<mj-divider border-width="2px" border-color="{palette["bar"]}" padding="10px 0 16px"/>'
        + (f'<mj-text font-family="{SERIF}" font-size="18px" font-weight="700" padding="0 0 12px">{headline}</mj-text>' if headline else "")
        + (f'<mj-text padding="0 0 12px">{greeting}</mj-text>' if greeting else "")
        + _paras(content.get("body_blocks"))
        + _button(content, palette, radius="2px")
        + "</mj-column></mj-section>"
        f'<mj-section background-color="{palette["panel"]}" padding="4px 30px 26px"><mj-column>'
        f'<mj-divider border-width="1px" border-color="{palette["line"]}" padding="8px 0 12px"/>'
        f'<mj-text font-size="11px" color="{palette["muted"]}">{footer}</mj-text>'
        "</mj-column></mj-section>"
        "</mj-body></mjml>"
    )


ARCHETYPES = [
    {"key": "plain_memo", "label": "Plain internal memo", "build": _plain_memo},
    {"key": "branded_notice", "label": "Branded transactional notice", "build": _branded_notice},
    {"key": "modern_card", "label": "Modern minimal card", "build": _modern_card},
    {"key": "corporate", "label": "Classic corporate", "build": _corporate},
]


def select(index):
    """Deterministic archetype + palette for variant `index`. Palette shifts after
    one full pass through the archetypes so variants 5-8 differ from 1-4."""
    a = ARCHETYPES[index % len(ARCHETYPES)]
    p = PALETTES[(index + index // len(ARCHETYPES)) % len(PALETTES)]
    return a, p


def build_mjml(content, index):
    """Return (mjml_string, archetype_key, palette_name) for this variant."""
    a, p = select(index)
    return a["build"](content, p), a["key"], p["name"]


def archetype_labels():
    """[(key, label)] for UI/metadata."""
    return [(a["key"], a["label"]) for a in ARCHETYPES]
