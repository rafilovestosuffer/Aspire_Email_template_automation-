"""Translate + re-brand one email template into one target language.

Controls kept here:
  * {{placeholders}} (incl. recipient/link tokens) are MASKED before the model
    sees them and restored after - they are never translated or filled.
  * The model is instructed to preserve all HTML structure, attributes and URLs.
  * No key set -> a clearly-labelled MOCK result, so the UI works without secrets.
  * This produces template *content* only; nothing is ever sent from here.
"""
import os
import re
from collections import Counter
from html import escape
from html.parser import HTMLParser

from . import design as _design, mjml_engine as _mjml, htmlsafe as _htmlsafe


class Structure(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.events = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.events.append(('start', tag, attrs))

    def handle_startendtag(self, tag, attrs):
        self.events.append(('empty', tag, attrs))

    def handle_endtag(self, tag):
        self.events.append(('end', tag))


def validated_output(original, output, toks):
    output = _strip_fences(output)
    sentinel = re.compile(r'⦑PH\d+⦒')
    if Counter(sentinel.findall(original)) != Counter(sentinel.findall(output)):
        raise ValueError('Model changed frozen placeholders; output rejected.')
    if Structure(original).events != Structure(output).events:
        raise ValueError('Model changed HTML structure or attributes; output rejected.')
    restored = _unmask(output, toks)
    if Counter(MASK_RE.findall(restored)) != Counter(toks):
        raise ValueError('Model introduced or changed placeholders; output rejected.')
    return restored


def validated_variant(original, output, toks):
    """Validator for VARIANT output (a deliberate re-wording), not translation.

    A variant is meant to change the copy and HTML, so - unlike translation - it
    does NOT have to preserve structure or the exact per-occurrence placeholder
    count. The real control still holds: the closed-vocabulary / injection gate.
    The variant may only use placeholders that were already in the seed; it may
    drop some and change how many times each appears, but it may NOT invent a new
    {{token}} or a new sentinel. Placeholders are never resolved or filled.
    """
    output = _strip_fences(output)
    allowed_idx = set(range(len(toks)))
    seen_idx = {int(m) for m in re.findall(r'⦑PH(\d+)⦒', output)}
    if not seen_idx <= allowed_idx:
        raise ValueError('Model invented placeholder tokens; output rejected.')
    restored = _unmask(output, toks)
    allowed_tokens = set(toks)
    if any(tok not in allowed_tokens for tok in MASK_RE.findall(restored)):
        raise ValueError('Model introduced a new placeholder; output rejected.')
    return restored

MASK_RE = re.compile(r"\{\{\s*[.#/A-Za-z0-9_\-]+\s*\}\}")
_L, _R = "⦑", "⦒"          # rare bracket chars used as sentinels
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o-mini"
HUMANIZE_PROMPT_VERSION = "humanize-v1"

# Distinct human sender voices. Rotating one per variant makes the set read as if
# written by different real people - which is both more realistic (real phishing is
# human-written) and makes the variants genuinely different from each other.
PERSONAS = [
    "a busy internal IT-support engineer: terse, practical, a little informal",
    "an HR operations coordinator: polite but hurried, plain business English",
    "an account-security notice from a real company: factual, spare, no fluff",
    "a finance / billing clerk: formal, brief, slightly dry",
    "a SaaS product-team member: friendly, direct, lightly casual",
    "an office manager sending a quick all-staff note: warm, plain, to the point",
    "an external vendor's support rep: courteous, a bit boilerplate but human",
    "a team lead firing off a note between meetings: clipped and direct",
]


def _mask(text):
    toks = []

    def repl(m):
        toks.append(m.group(0))
        return f"{_L}PH{len(toks) - 1}{_R}"

    return MASK_RE.sub(repl, text), toks


def _unmask(text, toks):
    for i, tok in enumerate(toks):
        text = text.replace(f"{_L}PH{i}{_R}", tok)
    return text


def _strip_fences(s):
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s).strip()
    return s


def _prompt(company, lang_name):
    brand = f'Use "{company}" as the sender/brand name wherever a brand name appears.' if company \
        else "Keep any existing brand references as they are."
    return (
        "You are localizing an AUTHORIZED security-awareness-training (SAT) "
        "phishing-simulation email template for a defensive training platform. "
        f"Translate ALL human-visible text into {lang_name}.\n"
        "Rules:\n"
        f"1. Keep every HTML tag, attribute, inline style and URL EXACTLY as-is and in place. "
        "Do not add, remove, or reorder tags.\n"
        "2. The tokens shaped like " + _L + "PH0" + _R + ", " + _L + "PH1" + _R +
        " are frozen placeholders - copy them through unchanged, never translate them.\n"
        "3. Only translate visible copy, button labels and preheader; preserve alt attributes.\n"
        f"4. {brand}\n"
        "Return ONLY the resulting HTML. No explanation, no code fences."
    )


def _mock(masked_html, toks, company, lang_name):
    company, lang_name = escape(company), escape(lang_name)
    banner = (
        f'<div style="background:#fff3cd;border:1px solid #ffe69c;color:#664d03;'
        f'padding:8px 12px;font:13px system-ui;margin:0 0 8px">MOCK preview - '
        f'{lang_name}{(" / " + company) if company else ""}. '
        f'Set OPENROUTER_API_KEY for real translation.</div>'
    )
    return {"html": banner + _unmask(masked_html, toks), "mode": "mock", "model": None}


def translate_and_brand(template_html, company_name, lang_name, *, api_key=None, model=None):
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    model = model or os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    masked, toks = _mask(template_html or "")

    if not api_key:
        return _mock(masked, toks, company_name, lang_name)

    try:
        import requests
        resp = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": _prompt(company_name, lang_name)},
                    {"role": "user", "content": masked},
                ],
            },
            timeout=120,
        )
        resp.raise_for_status()
        out = resp.json()["choices"][0]["message"]["content"]
        return {"html": validated_output(masked, out, toks), "mode": "openrouter", "model": model}
    except Exception as e:
        # fail-safe: return the original (masked restored) with an error flag; never crash the UI
        return {"html": _unmask(masked, toks), "mode": "error", "model": model, "error": str(e)}


# --- variant generation (the "amount" control) -------------------------------

def _variant_prompt(company, index):
    brand = (f'Use "{company}" as the sender/brand name.' if company
             else "Keep any existing brand references as they are.")
    return (
        "You are producing a DISTINCT variant of an AUTHORIZED security-awareness-training "
        "(SAT) phishing-simulation email template, for HUMAN REVIEW on a defensive platform.\n"
        "Keep EXACTLY the same: the scenario, the difficulty, every HTML tag/attribute/style/URL, "
        f"and every frozen placeholder token shaped like {_L}PH0{_R}.\n"
        "Vary ONLY the surface wording - subject/preheader line, greeting, phrasing and pretext "
        "details (dates, reference numbers, urgency) - so it reads as a genuinely different "
        "message, not a reworded copy.\n"
        f"{brand}\n"
        f"This is variant #{index + 1}; make it clearly different from an obvious default.\n"
        "Return ONLY the resulting HTML. No explanation, no code fences."
    )


def make_variant(template_html, company_name, index, *, api_key=None, model=None, humanize=True):
    """Produce one distinct variant of the seed (same language). Placeholders preserved.
    The variant is DRAFT content for review - it is never marked approved here.
    When humanize=True and generation succeeds, a second pass rewrites the copy to read
    as natural human writing (see _humanize); that pass is fail-closed."""
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    model = model or os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    masked, toks = _mask(template_html or "")

    if not api_key:
        banner = (
            f'<div style="background:#fff3cd;border:1px solid #ffe69c;color:#664d03;'
            f'padding:8px 12px;font:13px system-ui;margin:0 0 8px">MOCK variant #{index + 1}'
            f'{(" / " + escape(company_name)) if company_name else ""}. Set OPENROUTER_API_KEY for real variants.</div>'
        )
        return {"html": banner + _unmask(masked, toks), "mode": "mock", "model": None, "humanized": False}

    try:
        import requests
        resp = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "temperature": 0.85,
                "messages": [
                    {"role": "system", "content": _variant_prompt(company_name, index)},
                    {"role": "user", "content": masked},
                ],
            },
            timeout=120,
        )
        resp.raise_for_status()
        out = resp.json()["choices"][0]["message"]["content"]
        variant_html = validated_variant(masked, out, toks)
        result = {"html": variant_html, "mode": "openrouter", "model": model, "humanized": False}
        if humanize:
            result.update(_humanize(variant_html, company_name, index, api_key=api_key, model=model))
        return result
    except Exception as e:
        return {"html": _unmask(masked, toks), "mode": "error", "model": model, "error": str(e), "humanized": False}


# --- humanization layer (make a generated variant read human-written) ---------
#
# A second, pinned pass that rewrites ONLY the visible wording of an already-generated
# variant so it reads like a real person wrote it. The goal is training realism, not
# defeating any detector. It reuses the exact same controls as variant generation:
# placeholders are masked before the model sees them and never resolved/filled, and the
# closed-vocabulary / injection gate (validated_variant) still runs. It is fail-closed:
# any error or validation failure returns the pre-humanized variant UNCHANGED, so the
# base variant is never broken and nothing is auto-approved.

def _humanize_prompt(company, persona):
    brand = (f'The sender/brand is "{company}".' if company
             else "Keep any existing brand references exactly as they are.")
    return (
        "You are a human copy editor on an AUTHORIZED security-awareness-training (SAT) "
        "platform. You are given the HTML of a phishing-SIMULATION email variant that reviewers "
        "will check and, only after human approval, use to train a client's own staff. Rewrite "
        "the visible wording so it reads like a REAL person actually wrote it - the point is "
        "realistic training, not getting past any detector.\n"
        f"Write in the voice of {persona}.\n"
        f"{brand}\n"
        "Keep these IDENTICAL: the scenario and intent, every fact / date / number already present, "
        "every link, every HTML tag / attribute / inline style, and every frozen token shaped like "
        f"{_L}PH0{_R} (copy those through unchanged - never translate, fill or drop them).\n"
        "Make it sound human:\n"
        "- Vary sentence length on purpose - mix short, blunt sentences with the odd longer one; "
        "avoid a block of same-length medium sentences.\n"
        "- Use natural contractions (you're, we've, don't, it's).\n"
        "- Cut AI / corporate tells and filler. Do NOT use: \"I hope this email finds you well\", "
        "\"please do not hesitate\", \"rest assured\", \"we value your\", \"leverage\", \"utilize\", "
        "\"robust\", \"delve\", \"furthermore\", \"moreover\", \"in conclusion\", \"kindly\", or "
        "trailing em-dash asides.\n"
        "- Commit to one clear ask; don't hedge or over-explain.\n"
        "- Keep it plain and specific, like a quick real work email, not marketing copy.\n"
        "Do not add new claims, content, URLs or placeholders. Return ONLY the resulting HTML. "
        "No explanation, no code fences."
    )


def _humanize(variant_html, company_name, index, *, api_key, model):
    """Rewrite a generated variant so it reads as natural human writing. Fail-closed:
    on any error or validation failure, return the input variant unchanged."""
    persona = PERSONAS[index % len(PERSONAS)]
    base = {"humanize_prompt_version": HUMANIZE_PROMPT_VERSION, "persona": persona}
    masked, toks = _mask(variant_html or "")
    try:
        import requests
        resp = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "temperature": 0.9,
                "messages": [
                    {"role": "system", "content": _humanize_prompt(company_name, persona)},
                    {"role": "user", "content": masked},
                ],
            },
            timeout=120,
        )
        resp.raise_for_status()
        out = resp.json()["choices"][0]["message"]["content"]
        html = validated_variant(masked, out, toks)
        return {"html": html, "humanized": True, "humanize_model": model, **base}
    except Exception as e:
        # Keep the pre-humanized variant; record why the layer was skipped.
        return {"html": variant_html, "humanized": False, "humanize_error": str(e), **base}


# --- redesign generation (curated archetypes + local MJML) -------------------
#
# A redesign keeps the source's scenario + content but RE-RENDERS it in one of our
# curated, perfectly-aligned archetypes (app/design.py), compiled by MJML
# (app/mjml_engine.py). The model never authors layout - it only extracts the copy
# into slots; we build OUR mjml, compile, restore the frozen {{tokens}}, then run the
# closed-vocabulary gate (validated_variant) + the HTML injection gate (app/htmlsafe.py)
# before returning. DRAFT only, never auto-approved; nothing is resolved or sent.

REDESIGN_PROMPT_VERSION = "redesign-extract-v1"
_LINK_TOKEN_NAMES = {"phishing_link", "training_url", "link", "url", "verification_link", "reset_link"}
_BRAND_TOKEN_NAMES = {"brand_name", "company", "customer", "product_name"}


def _token_name(tok):
    return tok.strip("{} ").strip().lower()


def _first_index(toks, names):
    for i, t in enumerate(toks):
        if _token_name(t) in names:
            return i
    return None


def _sentinel(i):
    return None if i is None else f"{_L}PH{i}{_R}"


def _detect_link_index(original_html, toks):
    """Index (in toks) of the source's primary action-link token, so it can be routed
    to the redesign's button href. Prefers phishing_link / training_url."""
    href_toks = re.findall(r'href\s*=\s*["\']\s*(\{\{[^}]*\}\})\s*["\']', original_html or "")
    href_names = [_token_name(t) for t in href_toks]
    for pref in ("phishing_link", "training_url", "verification_link", "reset_link", "link", "url"):
        if pref in href_names:
            idx = _first_index(toks, {pref})
            if idx is not None:
                return idx
    for nm in href_names:
        idx = _first_index(toks, {nm})
        if idx is not None:
            return idx
    return _first_index(toks, _LINK_TOKEN_NAMES)


class _Visible(HTMLParser):
    """Collect visible text lines from email HTML, preserving mask sentinels."""
    _BLOCK = {"p", "div", "br", "tr", "table", "h1", "h2", "h3", "h4", "li",
              "section", "header", "footer", "hr", "td"}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.buf = []
        self.feed(html or "")

    def handle_starttag(self, t, a):
        if t in self._BLOCK:
            self.buf.append("\n")

    def handle_startendtag(self, t, a):
        if t in ("br", "hr"):
            self.buf.append("\n")

    def handle_endtag(self, t):
        if t in self._BLOCK:
            self.buf.append("\n")

    def handle_data(self, d):
        self.buf.append(d)

    def lines(self):
        out = []
        for ln in "".join(self.buf).split("\n"):
            ln = re.sub(r"[ \t\r\f\v]+", " ", ln).strip()
            if ln:
                out.append(ln)
        return out


def _anchor_text(masked_html, link_idx):
    """Visible text of the <a> carrying the detected link sentinel, to reuse as the CTA label."""
    sent = _sentinel(link_idx)
    if not sent:
        return ""
    m = re.search(r'<a[^>]*href\s*=\s*["\']\s*' + re.escape(sent) + r'\s*["\'][^>]*>(.*?)</a>',
                  masked_html or "", re.I | re.S)
    if not m:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()[:60]


def _naive_content(masked_html, toks, company, link_idx):
    """Deterministic content extraction (mock mode + fail-closed fallback): no LLM."""
    lines = _Visible(masked_html).lines()
    brand_idx = _first_index(toks, _BRAND_TOKEN_NAMES)
    brand = _sentinel(brand_idx) or (company.strip() if company and company.strip() else "Your provider")
    brand_plain = (company or "").strip().lower()
    brand_sent = _sentinel(brand_idx)
    cta_label = _anchor_text(masked_html, link_idx)
    skip = {cta_label.strip().lower()} if cta_label else set()
    greeting, body = "", []
    for ln in lines:
        low = ln.lower()
        if (brand_plain and low == brand_plain) or (brand_sent and ln.strip() == brand_sent) or low in skip:
            continue                      # header/logo line or the CTA text - not body copy
        if not greeting and (low.startswith(("hi ", "hi,", "hello", "dear", "hey ")) or low in ("hi", "hello")):
            greeting = ln
        elif len(ln) >= 2:
            body.append(ln)
    if body and len(body[0]) <= 72:
        headline, body_blocks = body[0], body[1:7]
    else:
        headline, body_blocks = "A message about your account", body[:6]
    cta_href = _sentinel(link_idx)
    if cta_href and not cta_label:
        cta_label = "Open the secure link"
    return {
        "brand": brand,
        "preheader": (body_blocks[0] if body_blocks else headline)[:90],
        "headline": headline,
        "greeting": greeting,
        "body_blocks": body_blocks,
        "cta_label": cta_label if cta_href else "",
        "cta_href": cta_href,
        "footer_note": (f"Security-awareness training message prepared for {company.strip()}."
                        if company and company.strip()
                        else "Security-awareness training message - internal use only."),
    }


def _redesign_extract_prompt():
    return (
        "You extract the CONTENT of an AUTHORIZED security-awareness-training (SAT) "
        "phishing-SIMULATION email so it can be re-rendered in a cleaner, better-aligned "
        "layout. You are given the email's current HTML. Return STRICT JSON only, keys:\n"
        '  "preheader": short inbox-preview line (<=90 chars),\n'
        '  "headline": one short subject-like line,\n'
        '  "greeting": the salutation line (e.g. "Hi X,") or "",\n'
        '  "body_blocks": array of 1-4 short plain-text paragraphs,\n'
        '  "cta_label": the call-to-action button text (e.g. "Verify account") or "",\n'
        '  "footer_note": a short footer / sign-off line or "".\n'
        "Rules:\n"
        f"- Tokens shaped like {_L}PH0{_R}, {_L}PH1{_R} are FROZEN placeholders: copy any that "
        "belong in a field through verbatim and in place; NEVER translate, fill, or invent them.\n"
        "- Keep the scenario, facts, dates and numbers. Add no new claims, links or tokens.\n"
        "- Plain text only in every field (no HTML). Return ONLY the JSON object - no prose, no code fences."
    )


def _extract_llm(masked_html, api_key, model):
    import json
    import requests
    resp = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _redesign_extract_prompt()},
                {"role": "user", "content": masked_html},
            ],
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = json.loads(_strip_fences(resp.json()["choices"][0]["message"]["content"]))
    bb = data.get("body_blocks") or []
    if isinstance(bb, str):
        bb = [bb]
    return {
        "preheader": str(data.get("preheader", "") or "")[:120],
        "headline": str(data.get("headline", "") or ""),
        "greeting": str(data.get("greeting", "") or ""),
        "body_blocks": [str(x) for x in bb if str(x).strip()][:6],
        "cta_label": str(data.get("cta_label", "") or "")[:60],
        "footer_note": str(data.get("footer_note", "") or ""),
    }


def make_redesign(template_html, company_name, index, *, api_key=None, model=None, humanize=True):
    """One REDESIGN variant: same scenario/content, re-rendered in a curated aligned
    archetype (rotated by index). Placeholders are masked and never resolved; the
    compiled HTML must pass the closed-vocabulary + injection gates before return.
    DRAFT only, never auto-approved. Fail-closed: engine missing / bad extraction /
    unsafe output -> an 'error' result (source preserved), never unsafe stored HTML."""
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    model = model or os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    company_name = company_name or ""
    masked, toks = _mask(template_html or "")
    link_idx = _detect_link_index(template_html or "", toks)
    arch, pal = _design.select(index)
    meta = {"kind": "redesign", "archetype": arch["key"], "palette": pal["name"],
            "redesign_prompt_version": REDESIGN_PROMPT_VERSION, "mjml_engine": _mjml.engine_version()}

    if not _mjml.available():
        return {"html": _unmask(masked, toks), "mode": "error", "model": None,
                "error": "MJML engine not installed (pip install mjml-python).",
                "humanized": False, **meta}

    # 1) content extraction (LLM when keyed, else deterministic; fail-closed to deterministic)
    extraction = "mock"
    if not api_key:
        content = _naive_content(masked, toks, company_name, link_idx)
    else:
        try:
            content = _extract_llm(masked, api_key, model)
            content["cta_href"] = _sentinel(link_idx)
            content["brand"] = _sentinel(_first_index(toks, _BRAND_TOKEN_NAMES)) \
                or (company_name.strip() if company_name.strip() else "Your provider")
            extraction = "llm"
            if not content["body_blocks"] and not content["headline"]:
                content, extraction = _naive_content(masked, toks, company_name, link_idx), "fallback"
        except Exception:
            content, extraction = _naive_content(masked, toks, company_name, link_idx), "fallback"
    content.setdefault("cta_href", _sentinel(link_idx))
    if content.get("cta_href") and not (content.get("cta_label") or "").strip():
        content["cta_label"] = "Open the secure link"

    # 2) build OUR mjml -> compile -> restore tokens -> gates (fail-closed)
    try:
        mjml_src, _arch_key, _pal_name = _design.build_mjml(content, index)
        compiled = _mjml.compile_mjml(mjml_src)
        restored = validated_variant(masked, compiled, toks)   # closed-vocabulary gate; returns unmasked HTML
        _htmlsafe.assert_safe(restored)                        # injection gate on final HTML
        if link_idx is not None and toks[link_idx] not in MASK_RE.findall(restored):
            raise ValueError("redesign dropped the source's action-link token")
    except Exception as e:
        return {"html": _unmask(masked, toks), "mode": "error", "model": model if api_key else None,
                "error": f"redesign failed: {e}", "humanized": False, **meta}

    result = {"html": restored, "mjml": mjml_src, "extraction": extraction,
              "mode": "openrouter" if api_key else "mock", "model": model if api_key else None,
              "humanized": False, **meta}

    # 3) optional humanize pass on the copy (keyed only); re-gate; fail-closed
    if humanize and api_key:
        hz = _humanize(restored, company_name, index, api_key=api_key, model=model)
        if hz.get("humanized"):
            ok_safe = _htmlsafe.check(hz["html"])[0]
            keeps_link = link_idx is None or toks[link_idx] in MASK_RE.findall(hz["html"])
            if ok_safe and keeps_link:                 # else keep the safe, link-bearing pre-humanized redesign
                result.update(html=hz["html"], humanized=True,
                              humanize_model=hz.get("humanize_model"),
                              humanize_prompt_version=hz.get("humanize_prompt_version"),
                              persona=hz.get("persona"))
    return result
