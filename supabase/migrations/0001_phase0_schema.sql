-- =====================================================================
-- ASAT Content Factory - Phase 0 schema (migration 0001)
-- Postgres / Supabase. Foundation layer only:
--   immutable import -> normalized brand-neutral masters
--   + controlled variable vocabulary + brands + frozen downstream tables.
--
-- Controls baked into the data model (not convention):
--   * Every render is engagement-bound; the factory can never mark anything
--     sendable (hard CHECK below) until the downstream Release-Gate exists.
--   * Link/engagement/tracking variables are system-owned (authors can't set).
--   * Recipient-PII variables are never resolved or stored in the factory.
--   * The audit log is append-only.
--
-- Apply:  supabase db push    (or: psql "$DATABASE_URL" -f this_file.sql)
-- NOTE:   Do not hand-edit after the schema is frozen (schema_meta.frozen=true).
--         Change via a NEW migration (0002_*.sql).
-- =====================================================================

begin;

create extension if not exists pgcrypto;   -- gen_random_uuid()

-- ---------- Controlled lists (enums) ---------------------------------
create type channel            as enum ('email','landing','sms','voice');
create type payload_type       as enum ('website','link_url','data_entry','attachment','none');
create type difficulty_band    as enum ('easy','medium','hard');          -- NIST Phish Scale band, surfaced
create type template_status    as enum ('draft','staging','active','retired');
create type version_review      as enum ('pending','approved','rejected');
create type lint_state          as enum ('unchecked','pass','fail');
create type variable_category  as enum ('brand','sender','recipient','link','locale','system');
create type output_context     as enum ('html_text','html_attr','url','css_color','enum','opaque','plain');
create type translation_origin as enum ('machine','human','mt_postedited');
create type translation_status as enum ('draft','machine','in_review','approved','stale');
create type engagement_status  as enum ('pending_auth','authorized','active','suspended','expired','revoked');
create type render_status      as enum ('generated','approved_for_send','expired');
create type review_action      as enum ('submit','approve','reject','retire','publish');
create type review_subject     as enum ('source_template','template','template_version','translation','render_output','brand','engagement');

-- ---------- Category lookup (extensible controlled list) -------------
create table categories (
  id          text primary key,              -- slug, e.g. 'credential_harvest'
  label       text not null,
  description text
);

-- ---------- Immutable raw import ------------------------------------
create table source_templates (
  id          uuid primary key default gen_random_uuid(),
  channel     channel not null,
  source_ref  text not null,                 -- workbook sheet + row, e.g. 'Email Template!row42'
  raw_subject text,
  raw_body    text,                          -- original HTML / SMS text / script, verbatim
  raw_meta    jsonb not null default '{}',   -- every original column preserved as-is
  source_hash text not null,                 -- sha256 of raw_body (provenance / dedupe)
  imported_at timestamptz not null default now(),
  unique (channel, source_ref)                -- import idempotency key (ON CONFLICT target)
);
comment on table source_templates is 'Immutable verbatim import of each workbook row. Never edited; re-run normalization from here.';
create index source_templates_channel_idx on source_templates (channel);
create index source_templates_hash_idx    on source_templates (source_hash);

-- ---------- Normalized masters (brand-neutral) ----------------------
create table templates (
  id                uuid primary key default gen_random_uuid(),
  slug              text unique not null,
  channel           channel not null,
  category_id       text references categories(id),
  difficulty        difficulty_band,
  cue_count         int,                     -- NIST Phish Scale inputs
  premise_alignment text,                    -- weak | medium | strong
  canonical_locale  text not null default 'en',
  status            template_status not null default 'draft',
  content_hash      text,                    -- brand-stripped, normalized (dedupe)
  source_template_id uuid references source_templates(id),
  created_by        text,
  created_at        timestamptz not null default now()
);
comment on table templates is 'Brand-neutral master. Every brand reference is a {{variable}}; a master is invariant across brands.';
create index templates_channel_idx on templates (channel);
create index templates_hash_idx    on templates (content_hash);

create table template_versions (
  id            uuid primary key default gen_random_uuid(),
  template_id   uuid not null references templates(id) on delete cascade,
  version_no    int not null,
  subject       text,                        -- subject / page_title / sms_text; ssml for voice
  body          text not null,
  format        text not null default 'html',-- html | mjml | text | ssml
  lint_status   lint_state not null default 'unchecked',
  review_status version_review not null default 'pending',
  approved_by   text,
  approved_at   timestamptz,
  is_current    boolean not null default false,
  created_at    timestamptz not null default now(),
  unique (template_id, version_no)
);
comment on table template_versions is 'Immutable once approved; an edit creates a new version.';
create unique index one_current_version_per_template
  on template_versions (template_id) where is_current;

-- ---------- Controlled variable vocabulary --------------------------
create table variables (
  name             text primary key,         -- lower_snake_case, e.g. 'brand_name'
  category         variable_category not null,
  output_context   output_context not null,
  data_type        text not null default 'string',
  validation_regex text,
  is_system_owned  boolean not null default false,  -- authors cannot set
  is_recipient_pii boolean not null default false,  -- never resolved in factory
  default_value    text,
  description      text
);
comment on column variables.is_system_owned  is 'True = link/engagement/tracking vars; authors cannot set; resolve only to engagement-approved hosts.';
comment on column variables.is_recipient_pii is 'True = merged ONLY by the downstream sender; never resolved or stored in the factory.';

create table template_variables (
  template_version_id uuid not null references template_versions(id) on delete cascade,
  variable_name       text not null references variables(name),
  occurrences         int  not null default 1,
  primary key (template_version_id, variable_name)
);
comment on table template_variables is 'Lint join: asserts no unknown variable and that required system variables are present.';

-- ---------- Brands (applied at render; never baked into masters) ----
create table brands (
  id               uuid primary key default gen_random_uuid(),
  name             text not null,            -- internal label
  brand_name_value text not null,            -- the rendered {{brand_name}}
  brand_type       text,                     -- bank | telco | retailer | gov | saas
  brand_color      text,
  brand_color_2    text,
  brand_domain     text,
  support_email    text,
  support_phone    text,
  is_regional      boolean not null default false,
  region           text,
  status           text not null default 'active',
  created_at       timestamptz not null default now()
);
comment on table brands is 'Client/brand records merged at render time. The bKash/Nagad/Robi/GP/City Bank set are rows here.';

create table brand_assets (
  id           uuid primary key default gen_random_uuid(),
  brand_id     uuid not null references brands(id) on delete cascade,
  kind         text not null,                -- logo | icon
  url          text not null,                -- our CDN, https
  content_type text,
  checksum     text
);
alter table brands add column logo_asset_id uuid references brand_assets(id);

-- ---------- Translations (one per master version per locale) --------
create table translations (
  id                  uuid primary key default gen_random_uuid(),
  source_version_id   uuid not null references template_versions(id) on delete cascade,
  locale              text not null,         -- BCP-47
  subject             text,
  body                text not null,
  source_version_hash text not null,         -- pins the master version; mismatch => stale
  origin              translation_origin not null default 'machine',
  status              translation_status not null default 'draft',
  approved_by         text,
  approved_at         timestamptz,
  created_at          timestamptz not null default now(),
  unique (source_version_id, locale)
);

-- ---------- Engagements (the authorization spine) -------------------
create table engagements (
  id                     uuid primary key default gen_random_uuid(),
  client_org_name        text not null,
  authorization_ref      text,              -- MSA/SOW/pentest authorization id
  authorization_doc_url  text,
  authorization_doc_hash text,              -- sha256 of the executed PDF
  roster_ref             text,
  roster_scope_locked    boolean not null default false,
  allowed_recipient_domains text[]   not null default '{}',
  allowed_channels          channel[] not null default '{}',
  allowed_brands            uuid[]    not null default '{}',
  window_start           timestamptz,
  window_end             timestamptz,
  status                 engagement_status not null default 'pending_auth',
  authorized_by          text,
  authorized_at          timestamptz,
  created_at             timestamptz not null default now()
);
comment on table engagements is 'One row = one signed authorization. Only status=active permits render/approve/publish/send (enforced in app + later phases).';

-- ---------- Render outputs (brand resolved; recipient PII intact) ----
create table render_outputs (
  id                  uuid primary key default gen_random_uuid(),
  engagement_id       uuid not null references engagements(id),
  template_version_id uuid not null references template_versions(id),
  translation_id      uuid references translations(id),
  brand_id            uuid references brands(id),
  rendered_subject    text,
  rendered_body       text not null,         -- brand resolved; {{first_name}} etc. STILL placeholders
  render_hash         text,
  recipient_placeholders_intact boolean not null default true,
  status              render_status not null default 'generated',
  sendable            boolean not null default false,  -- the factory NEVER sets this true
  expires_at          timestamptz,
  created_at          timestamptz not null default now(),
  constraint recipient_pii_must_stay_placeholders check (recipient_placeholders_intact),
  constraint factory_never_sendable check (sendable = false)
);
comment on constraint factory_never_sendable on render_outputs is
  'Phase 0 hard guard: the factory cannot produce sendable content. Relaxed ONLY when the downstream Release-Gate is built and passes its roster-enforcement conformance test.';

-- ---------- Append-only audit ---------------------------------------
create table review_events (
  id            bigint generated always as identity primary key,
  subject_type  review_subject not null,
  subject_id    uuid,
  action        review_action  not null,
  actor         text,
  note          text,
  engagement_id uuid references engagements(id),
  created_at    timestamptz not null default now()
);
comment on table review_events is 'Append-only. UPDATE/DELETE blocked by trigger; corrections are new compensating rows.';

create or replace function no_mutate() returns trigger language plpgsql as $$
begin
  raise exception 'review_events is append-only (no UPDATE/DELETE)';
end $$;
create trigger review_events_append_only
  before update or delete on review_events
  for each row execute function no_mutate();

-- ---------- Row-Level Security --------------------------------------
-- Engagement-scoped data is RLS-protected now; the per-client-org policies
-- land with Auth + org membership in Phase 3. service_role bypasses RLS.
alter table engagements    enable row level security;
alter table render_outputs enable row level security;
-- (library tables - templates/translations/brands/variables - are shared-read.)

-- ---------- Schema version marker -----------------------------------
create table schema_meta (key text primary key, value text);
insert into schema_meta (key, value) values
  ('phase','0'), ('migration','0001'), ('frozen','false');

-- ---------- Seed: controlled variable vocabulary --------------------
insert into variables (name, category, output_context, is_system_owned, is_recipient_pii, default_value, validation_regex, description) values
  ('brand_name',     'brand',     'html_text', false, false, 'your provider', null,              'Client/bank display name'),
  ('brand_logo_url', 'brand',     'url',       false, false, null,            '^https://',       'Brand logo (https, allow-listed host)'),
  ('brand_color',    'brand',     'css_color', false, false, '#1a1a1a',       '^#[0-9A-Fa-f]{6}$','Primary brand color'),
  ('brand_color_2',  'brand',     'css_color', false, false, null,            '^#[0-9A-Fa-f]{6}$','Secondary brand color'),
  ('brand_domain',   'brand',     'html_text', false, false, null,            null,              'Brand domain shown in copy'),
  ('product_name',   'brand',     'html_text', false, false, 'your account',  null,              'Product/service name'),
  ('company_footer', 'brand',     'html_text', false, false, null,            null,              'Legal footer line'),
  ('cta_label',      'brand',     'html_text', false, false, 'Continue',      null,              'Call-to-action button label'),
  ('sender_name',    'sender',    'html_text', true,  false, null,            null,              'From display name (engagement identity)'),
  ('sender_email',   'sender',    'html_text', true,  false, null,            null,              'From address (engagement identity)'),
  ('support_phone',  'sender',    'html_text', false, false, null,            null,              'Support phone'),
  ('phishing_link',  'link',      'url',       true,  false, null,            '^https://',       'System-owned; resolves ONLY to the engagement safe-landing host'),
  ('tracking_domain','link',      'html_text', true,  false, null,            null,              'System-owned tracking domain'),
  ('rid',            'link',      'opaque',    true,  false, null,            null,              'Recipient id token; bound by the sender'),
  ('engagement_id',  'system',    'opaque',    true,  false, null,            null,              'System-owned; must resolve to an authorized engagement'),
  ('training_url',   'system',    'url',       true,  false, null,            '^https://',       'System-owned training/debrief URL'),
  ('tracking_pixel', 'system',    'html_attr', true,  false, null,            null,              'System-owned tracking-pixel endpoint'),
  ('first_name',     'recipient', 'html_text', false, true,  'there',         null,              'Recipient PII; merged by the sender ONLY'),
  ('last_name',      'recipient', 'html_text', false, true,  '',              null,              'Recipient PII; merged by the sender ONLY'),
  ('email',          'recipient', 'html_text', false, true,  '',              null,              'Recipient PII; merged by the sender ONLY'),
  ('job_title',      'recipient', 'html_text', false, true,  '',              null,              'Recipient PII; merged by the sender ONLY'),
  ('department',     'recipient', 'html_text', false, true,  '',              null,              'Recipient PII; merged by the sender ONLY'),
  ('date',           'locale',    'plain',     false, false, null,            null,              'Locale-rendered date'),
  ('currency',       'locale',    'plain',     false, false, null,            null,              'Locale currency symbol/code'),
  ('amount',         'locale',    'plain',     false, false, null,            null,              'Locale-rendered amount'),
  ('ticket_no',      'locale',    'plain',     false, false, null,            null,              'Reference/ticket number');

-- ---------- Seed: starter category list (extend via INSERT) ---------
insert into categories (id, label, description) values
  ('credential_harvest','Credential harvest','Login / verify lures'),
  ('account_alert',     'Account alert',     'Suspension / suspicious-activity notices'),
  ('password_reset',    'Password reset',    'Reset / expiry prompts'),
  ('payment_refund',    'Payment / refund',  'Payment, refund, invoice lures'),
  ('delivery_notice',   'Delivery notice',   'Parcel / shipping lures'),
  ('it_helpdesk',       'IT / helpdesk',     'Internal IT / security-update lures'),
  ('document_share',    'Document share',    'Shared file / document lures');

commit;

-- =====================================================================
-- Freeze step (run only after Phase 0 exit gate is met):
--   update schema_meta set value = 'true' where key = 'frozen';
-- =====================================================================
