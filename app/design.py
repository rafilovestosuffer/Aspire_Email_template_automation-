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
LAYOUT_VERSION = 'design-v3'

# Mature, accessible color sets (WCAG-reasonable text/background contrast).
PALETTES = [
    {"name": "indigo", "bg": "#eef1f7", "panel": "#ffffff", "ink": "#1b2a4a", "muted": "#5b6b82",
     "bar": "#1f3a6b", "barink": "#ffffff", "accent": "#2454d6", "accentink": "#ffffff", "line": "#e4e9f2"},
    {"name": "slate", "bg": "#f1f3f5", "panel": "#ffffff", "ink": "#1f2937", "muted": "#616b78",
     "bar": "#111827", "barink": "#ffffff", "accent": "#334155", "accentink": "#ffffff", "line": "#e5e7eb"},
    {"name": "teal", "bg": "#eef5f4", "panel": "#ffffff", "ink": "#12343b", "muted": "#51696d",
     "bar": "#0f766e", "barink": "#ffffff", "accent": "#0f766e", "accentink": "#ffffff", "line": "#d9e6e4"},
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
        f'font-weight="700" inner-padding="16px 30px" padding="16px 0 4px">{label}</mj-button>'
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
    """Contrast-led card: dark hero, inset summary, and a broad action button."""
    e = lambda key: escape(content.get(key, '') or '')
    blocks = content.get('body_blocks') or []
    lead = escape(blocks[0]) if blocks else ''
    return (
        '<mjml>' + _head(content, palette) +
        f'<mj-body background-color="{palette["bg"]}" width="600px">'
        '<mj-section padding="24px 16px 0"><mj-column>'
        f'<mj-text font-size="14px" font-weight="700" color="{palette["bar"]}" padding="0 8px 18px">{e("brand")}</mj-text>'
        '</mj-column></mj-section>'
        '<mj-wrapper padding="0 16px">'
        f'<mj-section background-color="{palette["bar"]}" border-radius="16px 16px 0 0" padding="32px 28px"><mj-column>'
        f'<mj-divider border-color="{palette["accent"]}" border-width="5px" width="44px" align="left" padding="0 0 22px"/>'
        f'<mj-text color="{palette["barink"]}" font-size="32px" font-weight="700" line-height="1.22" letter-spacing="-0.6px" padding="0">{e("headline")}</mj-text>'
        '</mj-column></mj-section>'
        f'<mj-section background-color="{palette["panel"]}" padding="28px 28px 8px"><mj-column>'
        f'<mj-text font-size="16px" font-weight="600" padding="0 0 20px">{e("greeting")}</mj-text>'
        '</mj-column></mj-section>'
        f'<mj-section background-color="{palette["panel"]}" padding="0 28px 22px">'
        f'<mj-column background-color="{palette["bg"]}" border-left="3px solid {palette["accent"]}" padding="18px 20px">'
        f'<mj-text font-size="16px" line-height="1.65" padding="0">{lead}</mj-text>'
        '</mj-column></mj-section>'
        f'<mj-section background-color="{palette["panel"]}" border-radius="0 0 16px 16px" padding="0 28px 28px"><mj-column>'
        + _paras(blocks[1:]) + _button(content, palette, radius='8px') +
        f'<mj-divider border-color="{palette["line"]}" border-width="1px" padding="24px 0 16px"/>'
        f'<mj-text font-size="12px" line-height="1.6" color="{palette["muted"]}" padding="0">{e("footer_note")}</mj-text>'
        '</mj-column></mj-section></mj-wrapper>'
        '<mj-section padding="12px"><mj-column><mj-spacer height="8px"/></mj-column></mj-section>'
        '</mj-body></mjml>'
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


def _editorial(content, palette):
    """An editorial letter with generous spacing and a restrained accent rule."""
    e = lambda key: escape(content.get(key, '') or '')
    return (
        '<mjml>' + _head(content, palette) +
        f'<mj-body background-color="{palette["bg"]}" width="600px">'
        '<mj-section padding="28px 28px 18px"><mj-column>'
        f'<mj-text color="{palette["bar"]}" font-size="18px" font-weight="700" padding="0">{e("brand")}</mj-text>'
        '</mj-column></mj-section>'
        f'<mj-section background-color="{palette["panel"]}" border-radius="12px" padding="32px 28px"><mj-column>'
        f'<mj-divider border-color="{palette["accent"]}" border-width="4px" width="48px" align="left" padding="0 0 24px"/>'
        f'<mj-text font-family="{SERIF}" font-size="30px" line-height="1.25" padding="0 0 24px">{e("headline")}</mj-text>'
        f'<mj-text padding="0 0 16px">{e("greeting")}</mj-text>'
        + _paras(content.get('body_blocks')) + _button(content, palette) +
        f'<mj-divider border-color="{palette["line"]}" border-width="1px" padding="26px 0 18px"/>'
        f'<mj-text font-size="12px" color="{palette["muted"]}" padding="0">{e("footer_note")}</mj-text>'
        '</mj-column></mj-section><mj-section padding="12px"><mj-column><mj-spacer height="8px"/></mj-column></mj-section>'
        '</mj-body></mjml>'
    )


def _spotlight(content, palette):
    """A strong brand header, large headline, and clear single-column body."""
    e = lambda key: escape(content.get(key, '') or '')
    return (
        '<mjml>' + _head(content, palette) +
        f'<mj-body background-color="{palette["bg"]}" width="600px">'
        '<mj-section padding="12px"><mj-column><mj-spacer height="8px"/></mj-column></mj-section>'
        f'<mj-section background-color="{palette["bar"]}" border-radius="12px 12px 0 0" padding="28px"><mj-column>'
        f'<mj-text color="{palette["barink"]}" font-size="14px" font-weight="700" letter-spacing="1px" padding="0 0 22px">{e("brand")}</mj-text>'
        f'<mj-text color="{palette["barink"]}" font-size="28px" font-weight="700" line-height="1.3" padding="0">{e("headline")}</mj-text>'
        '</mj-column></mj-section>'
        f'<mj-section background-color="{palette["panel"]}" border-radius="0 0 12px 12px" padding="28px"><mj-column>'
        f'<mj-text padding="0 0 16px">{e("greeting")}</mj-text>'
        + _paras(content.get('body_blocks')) + _button(content, palette, radius='8px') +
        '</mj-column></mj-section><mj-section padding="18px 28px 28px"><mj-column>'
        f'<mj-text color="{palette["muted"]}" font-size="12px" padding="0">{e("footer_note")}</mj-text>'
        '</mj-column></mj-section></mj-body></mjml>'
    )


ARCHETYPES = [
    {"key": "modern_card", "label": "Signature card · bold header", "build": _modern_card},
    {"key": "editorial", "label": "Editorial letter · serif typography", "build": _editorial},
    {"key": "spotlight", "label": "Brand spotlight · color block", "build": _spotlight},
    {"key": "branded_notice", "label": "Branded transactional notice", "build": _branded_notice},
    {"key": "plain_memo", "label": "Plain internal memo", "build": _plain_memo},
    {"key": "corporate", "label": "Classic corporate", "build": _corporate},
]


def select(index, style='auto', palette='auto'):
    """Deterministic archetype + palette for variant `index`. Palette shifts after
    one full pass through the archetypes so variants 5-8 differ from 1-4."""
    a = (ARCHETYPES[index % len(ARCHETYPES)] if style == 'auto'
         else next(a for a in ARCHETYPES if a['key'] == style))
    p = (PALETTES[(index + index // len(ARCHETYPES)) % len(PALETTES)] if palette == 'auto'
         else next(p for p in PALETTES if p['name'] == palette))
    return a, p


def build_mjml(content, index, style='auto', palette='auto'):
    """Return (mjml_string, archetype_key, palette_name) for this variant."""
    a, p = select(index, style, palette)
    return a["build"](content, p), a["key"], p["name"]


def archetype_labels():
    """[(key, label)] for UI/metadata."""
    return [(a["key"], a["label"]) for a in ARCHETYPES]
