"""Controlled-vocabulary reconciliation maps (Block 4), derived from the real
Email export (2026-10-15). Canonical token case = lower snake_case.

Used by audit_vocab.py now and by the normalizer (Block 5) later. Whenever this
changes, update the migration seed and docs/controlled-lists-and-variables.md too.
"""

# The variables seeded by migration 0001 (audit checks mapped names against this).
SEEDED_VARS = {
    "brand_name", "brand_logo_url", "brand_color", "brand_color_2", "brand_domain",
    "product_name", "company_footer", "cta_label",
    "sender_name", "sender_email", "support_phone",
    "phishing_link", "tracking_domain", "rid",
    "engagement_id", "training_url", "tracking_pixel",
    "first_name", "last_name", "email", "job_title", "department",
    "date", "currency", "amount", "ticket_no",
}

# alias (lowercased, no braces, leading '.' stripped) -> canonical variable name.
# Only CONFIDENT mappings go here; ambiguous ones go to TOKEN_REVIEW.
TOKEN_ALIASES = {
    # recipient PII (merged by the sender only)
    "first_name": "first_name", "firstname": "first_name",
    "learner_first": "first_name", "leraner_first": "first_name",  # 2nd is a source typo
    "last_name": "last_name", "learner_last": "last_name",
    "email_address": "email", "email": "email", "learner_email": "email",
    "department": "department", "learner_department": "department",
    "phone_number": "phone", "phone": "phone",          # 'phone' is NOT seeded -> audit flags ADD VAR
    "job_title": "job_title",
    # brand / sender
    "brand_name": "brand_name", "product_name": "product_name",
    "sender_name": "sender_name", "sender_email": "sender_email", "support_phone": "support_phone",
    "brand_logo_url": "brand_logo_url", "brand_color": "brand_color", "brand_color_2": "brand_color_2",
    "brand_domain": "brand_domain", "company_footer": "company_footer", "cta_label": "cta_label",
    # link / system (system-owned)
    "phishing_link": "phishing_link", "tracking_domain": "tracking_domain", "rid": "rid",
    "engagement_id": "engagement_id", "training_url": "training_url", "tracking_pixel": "tracking_pixel",
    # locale
    "date": "date", "currency": "currency", "amount": "amount", "ticket_no": "ticket_no",
}

# junk / test tokens dropped on import
TOKEN_DROP = {"12345"}

# seen in the data, ambiguous -> a human must decide the mapping (audit flags these)
TOKEN_REVIEW = {
    "customer",            # brand_name? or recipient company? confirm
    "learner", "learner_name",          # first name, or full name?
    "learner_manager_name", "learner_manager_email",
    "learner_custom", "fb_datetime",
}

# difficulty label (lowercased) -> canonical band
DIFFICULTY_MAP = {
    "easy": "easy", "beginner": "easy", "begginer": "easy",
    "medium": "medium", "intermediate": "medium",
    "hard": "hard", "advance": "hard", "advanced": "hard",
}
DIFFICULTY_NOT = {"spear phishing"}   # a TYPE, not a difficulty -> store on category

# payload label (lowercased) -> canonical enum (confirm the scenario-ish ones)
PAYLOAD_MAP = {
    "website": "website", "link_url": "link_url", "linkurl": "link_url",
    "data_entry": "data_entry", "attachment": "attachment", "none": "none",
    "social media": "website", "fake update": "website",
    "info request": "data_entry", "fake payment": "data_entry",
}


def canon_token(raw):
    """(canonical_name, kind) where kind in {mapped, drop, review, unknown}."""
    t = raw.strip().lstrip(".").lower()
    if t in TOKEN_DROP:    return (None, "drop")
    if t in TOKEN_ALIASES: return (TOKEN_ALIASES[t], "mapped")
    if t in TOKEN_REVIEW:  return (t, "review")
    return (t, "unknown")


def canon_difficulty(raw):
    t = (raw or "").strip().lower()
    if not t:               return (None, "empty")
    if t in DIFFICULTY_MAP: return (DIFFICULTY_MAP[t], "mapped")
    if t in DIFFICULTY_NOT: return (None, "not_a_difficulty")
    return (None, "unknown")


def canon_payload(raw):
    t = (raw or "").strip().lower()
    if not t:             return (None, "empty")
    if t in PAYLOAD_MAP:  return (PAYLOAD_MAP[t], "mapped")
    return (None, "unknown")
