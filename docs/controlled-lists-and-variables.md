# Controlled lists & the `{{variable}}` standard — Phase 0

The single source of truth for the fixed vocabularies the factory enforces. The database seeds (`supabase/migrations/0001_phase0_schema.sql`) must always match this file; if they diverge, this file wins and the migration is corrected.

---

## 1. Variable naming standard

- **Syntax:** `{{lower_snake_case}}`, Mustache/Handlebars style. One flat namespace.
  - *Reconciliation decision:* the source library uses both `{{PHISHING_LINK}}` (email) and `{{phishing_link}}` (SMS). **We standardise on lower `{{snake_case}}`** (matches the SMS sheet and the working plan). The upper-case forms are treated as deprecated aliases during import and rewritten.
- **Closed vocabulary.** Every placeholder must exist in the `variables` table. An unknown `{{token}}` **fails lint and fails render** — this is both a quality gate and an injection gate (no new sink can be smuggled in).
- **No logic in templates.** Brand/locale differences are *data* (a `brands` row, a `translations` row), never template branches.

### The two binding times (why the factory holds no PII)

| Bound **inside** the factory (reviewers see a real preview) | Bound by the **downstream sender**, per recipient |
|---|---|
| `brand`, `sender`, `locale` variables | `recipient` and `link` variables |
| e.g. `brand_name`, `brand_logo_url`, `date`, `amount` | e.g. `first_name`, `email`, `phishing_link`, `rid` |

Recipient variables carry `is_recipient_pii = true` and are **never resolved or stored** in the factory — a `render_output` keeps them as literal placeholders (enforced by `recipient_placeholders_intact`). Link/engagement variables carry `is_system_owned = true` — authors cannot set them, and they resolve only to the engagement-approved safe-landing host.

### Validation rules (every save)

A template version is **invalid** if it contains: an unknown `{{token}}`; an unbalanced `{{`/`}}` pair; a variable used outside its declared `output_context`; or a hard-coded brand string the extractor missed. Escaping is per `output_context`: `html_text` → entity-escape; `html_attr` → attribute-escape; `url` → scheme allow-list (https only, reject `javascript:`/`data:`); `css_color` → `^#[0-9A-Fa-f]{6}$`. A hostile-fixture render test (e.g. `brand_name = "><script>…`) gates publish.

---

## 2. Controlled variable vocabulary

System-owned = authors cannot set it. PII = merged by the sender only, never in the factory.

| Variable | Category | Context | System | PII | Default | Notes |
|---|---|---|:--:|:--:|---|---|
| `brand_name` | brand | html_text | — | — | `your provider` | Client/bank display name |
| `brand_logo_url` | brand | url | — | — | — | https + allow-listed host |
| `brand_color` | brand | css_color | — | — | `#1a1a1a` | `^#[0-9A-Fa-f]{6}$` |
| `brand_color_2` | brand | css_color | — | — | — | secondary |
| `brand_domain` | brand | html_text | — | — | — | domain shown in copy |
| `product_name` | brand | html_text | — | — | `your account` | product/service |
| `company_footer` | brand | html_text | — | — | — | legal footer line |
| `cta_label` | brand | html_text | — | — | `Continue` | button label |
| `sender_name` | sender | html_text | ✓ | — | — | engagement identity |
| `sender_email` | sender | html_text | ✓ | — | — | engagement identity |
| `support_phone` | sender | html_text | — | — | — | support phone |
| `phishing_link` | link | url | ✓ | — | — | resolves ONLY to engagement safe-landing host |
| `tracking_domain` | link | html_text | ✓ | — | — | system tracking domain |
| `rid` | link | opaque | ✓ | — | — | recipient id token; bound by sender |
| `engagement_id` | system | opaque | ✓ | — | — | must resolve to an authorized engagement |
| `training_url` | system | url | ✓ | — | — | training/debrief URL |
| `tracking_pixel` | system | html_attr | ✓ | — | — | tracking-pixel endpoint |
| `first_name` | recipient | html_text | — | ✓ | `there` | sender merges only |
| `last_name` | recipient | html_text | — | ✓ | `` | sender merges only |
| `email` | recipient | html_text | — | ✓ | `` | sender merges only |
| `job_title` | recipient | html_text | — | ✓ | `` | sender merges only |
| `department` | recipient | html_text | — | ✓ | `` | sender merges only |
| `date` | locale | plain | — | — | — | locale-rendered |
| `currency` | locale | plain | — | — | — | symbol/code |
| `amount` | locale | plain | — | — | — | locale-rendered |
| `ticket_no` | locale | plain | — | — | — | reference number |

New variables are added by migration + an entry here — never ad hoc in a template.

---

## 3. Controlled lists (enums)

| List | Values | Reconciliation notes |
|---|---|---|
| **channel** | `email`, `landing`, `sms`, `voice` | voice = planned (empty today) |
| **payload_type** | `website`, `link_url`, `data_entry`, `attachment`, `none` | maps the workbook's `Website` → `website`, `LinkUrl` → `link_url` |
| **difficulty_band** | `easy`, `medium`, `hard` | The reviewer-facing band. It is **derived** from the NIST Phish Scale (`cue_count` + `premise_alignment` columns), not hand-set. The SMS sheet's `Intermediate` → `medium`. |
| **template_status** | `draft`, `staging`, `active`, `retired` | `staging` captures the "Version 2 / identified→fixed→staging" workbook block |
| **version_review** | `pending`, `approved`, `rejected` | per `template_version` |
| **lint_state** | `unchecked`, `pass`, `fail` | render/lint gate |
| **variable_category** | `brand`, `sender`, `recipient`, `link`, `locale`, `system` | drives binding time + escaping |
| **output_context** | `html_text`, `html_attr`, `url`, `css_color`, `enum`, `opaque`, `plain` | drives escaping |
| **translation_status** | `draft`, `machine`, `in_review`, `approved`, `stale` | `stale` = master changed after translation |
| **engagement_status** | `pending_auth`, `authorized`, `active`, `suspended`, `expired`, `revoked` | only `active` permits render/approve/publish |
| **render_status** | `generated`, `approved_for_send`, `expired` | |
| **category** (lookup table, extensible) | `credential_harvest`, `account_alert`, `password_reset`, `payment_refund`, `delivery_notice`, `it_helpdesk`, `document_share` | starter set; extend by INSERT, not migration |

---

## 4. Measured from the real Email export (2026-10-15) + open items

**Scale:** the Email sheet has **1,162 templates** (all have bodies); 66 are curated (Status/Difficulty set), 1,096 are raw. **80 bodies are truncated at 32,767 chars** (Excel's cell limit) — they need a non-CSV re-grab before import. SMS + Landing sheets still to be counted. (The earlier "~120" estimate was wrong; "~1,000" was right for Email alone.)

**Token case — DECIDED: lower `{{snake_case}}` is canonical.** The Email library is overwhelmingly UPPER (`{{PHISHING_LINK}}` ×4,449, `{{FIRST_NAME}}` ×742, `{{EMAIL_ADDRESS}}` ×270 — 5,488 UPPER vs 163 lower), but the importer auto-rewrites UPPER → canonical lower; mechanical, no manual cost.

**Token mappings to apply on import (from the real data):**
- Recipient: `FIRST_NAME` / `learner_first` / `learner` / `leraner_first`(typo) → `first_name`; `LAST_NAME` / `learner_last` → `last_name`; `EMAIL_ADDRESS` / `EMAIL` / `learner_email` → `email`; `learner_department` → `department`; `PHONE_NUMBER` → `phone` (add as a recipient var).
- Other: `customer` / `Customer` → confirm (likely `brand_name`); `learner_manager_name` / `learner_manager_email` / `fb_datetime` / `learner_custom` → map or add.
- Drop: junk `{{12345}}`.

**Difficulty labels seen → canonical band:** Intermediate / intermediate → `medium`; Beginner / Begginer → `easy`; Advance → `hard`. "Spear Phishing" is a *type*, not a difficulty (store elsewhere).

**Payload types seen:** mostly `Website` (124); also Attachment, "Social Media", "Fake Update", "Info Request", "Fake Payment" → map to the enum / scenario category.

**Still open:** finalise the category list against the full library (all channels); confirm the NIST cue thresholds for easy/medium/hard.
