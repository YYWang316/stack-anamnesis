---
schema_version: 1
name: sec_edgar_fetcher
role: P1_fetch_sec_edgar — filings-index + XBRL company-facts fetcher (SEC EDGAR, two-UA, email-gated)
description: Fourth of the B.1 data fetchers and the first email-PII handler, extending the
  etherscan_fetcher reference pattern (its runtime-secret handling generalised from an API
  key to a contact email). Fetches the SEC EDGAR submissions list (recent 10-K/10-Q/8-K +
  metadata) and the companyfacts XBRL JSON for any subject whose parent_or_issuer_entity is
  a SEC-registered listed company. The first fetcher to enforce the two-User-Agent invariant
  (the I-003 defense) and the only source in the registry that carries the operator email in
  the request header. The email is process-memory only — never persisted, never logged, never
  in the envelope. Conditional: dispatched by P1 only when the P0_sec_email gate resolved with
  a usable email (applies && not declined).
allowed_toolsets: ["fetchers", "io"]
---

# SEC EDGAR Fetcher

## Mission

- Fetch **filings-index** data — the `submissions` list (recent 10-K / 10-Q / 8-K plus
  company metadata) — and **structured financials** — the `companyfacts` XBRL JSON
  (machine-readable line items) — for a subject whose `parent_or_issuer_entity` is a
  SEC-registered **listed** company (`references/data_source_registry.md` §6).
- Resolve the human `subject` to a **zero-padded 10-digit CIK** first: a purely-numeric
  subject is taken as a CIK and zero-padded; otherwise a small in-fetcher CIK registry maps
  10 known parents (broader subject→CIK resolution is a future TD).
- Land the **raw** submissions + companyfacts responses verbatim under
  `meta/raw/sec_edgar/`; parsing, freshness-windowing, and the `recent`/`files` pagination
  walk are downstream concerns.
- This is the **first email-PII fetcher**, and the only source in the registry whose request
  header carries the operator's email. The email is read into runtime memory from one of two
  input modes (below) and is **never** logged, persisted, placed in the envelope, or echoed
  in an error message.

## Two-UA invariant (the I-003 defense)

This is the load-bearing rule of this fetcher. **Every** HTTP call selects its `User-Agent`
**by host**, through the single helper `_select_user_agent(url, sec_email)`:

- Host is exactly `sec.gov` **or** a `*.sec.gov` subdomain → `sec_user_agent`
  (`StackAnamnesis/1.0 (<email>)`, the email-bearing UA).
- Host is **anything else** → `public_user_agent` (`StackAnamnesis/1.0`, PII-free).
- A suffix lookalike such as `sec.gov.evil.com` matches **neither** branch → public UA.

`_select_user_agent` is the **only** place `SEC_UA_TEMPLATE` is ever formatted with the
email. No call may build the email-bearing UA itself or "reuse whichever UA is set" — that
"default to the only UA you can find" shape is exactly the **I-003** bug
(`references/equity_incidents_archive.md` I-003): in Phase A a SEC email-bearing UA was
reused on a non-SEC host (`investors.intuit.com`), leaking the user's email to that site's
logs. The `intuit` CIK is kept in the registry specifically so a regression test can assert
an `investors.intuit.com` URL selects the **public** UA. Getting this wrong is a P0 violation.

Both endpoints this fetcher calls are `data.sec.gov`, so both correctly receive the SEC UA —
but they still route through the helper, so any future code that calls in with a non-SEC URL
gets the public UA automatically. The post-run guard `tools/audit/user_agent_pii.py` is the
backstop: it fails if the email substring appears alongside a non-SEC URL.

## Inputs

- `subject` — a parent/issuer entity name (`"Circle"`, `"Coinbase Global"`) or a 10-digit
  CIK (`"0001876042"`). Sourced from `meta/gates.json -> subject_confirm` (the confirmed
  `parent_or_issuer_entity.name`).
- `subject_type` — the 5-class taxonomy enum (`stablecoin_issuer | orchestrator | wallet |
  chain | agentic_payment_layer`). Recorded in the envelope; it does **not** route here (the
  SEC gate is conditional on a *listed parent*, not on the class). If `subject` is purely a
  token (e.g. `"USDC"`), the **caller** must resolve it to the parent name (`"Circle"`)
  before dispatch — documented but not enforced (the orchestrator's job in B.2+).
- `freshness_window` — one of `7d | 30d | 90d | quarter | 1 year | since_TGE`, from
  `meta/gates.json -> freshness.value`. Passed through and recorded; drives the
  filing-recency filter applied downstream on the submissions list.
- `sec_email` — the contact email, **process-memory only**, obtained from exactly one of
  the two input modes below.

## Input modes (方案 C — exactly one)

The CLI exposes a **mutually-exclusive, required** pair (`argparse` enforces "exactly one"):

- `--sec-email <addr>` — **direct mode**. The caller passes the email. Used standalone in
  the B.1.4→B.2 era before the orchestrator exists. The email stays process-memory only.
- `--run-dir <path>` — **orchestrator-coupled mode**. Reads
  `<run_dir>/meta/gates.json -> gates.sec_email.value` (per `agents/sec_email_gate.md`).

| Condition | Halt |
|---|---|
| both `--sec-email` and `--run-dir` | `dual_mode_conflict` (rejected by argparse) |
| neither provided | `sec_email_required` (rejected by argparse) |
| `gates.json` missing / unparseable / malformed | `gates_file_unreadable` |
| `gates.sec_email.applies == false` | `sec_email_gate_skipped` (subject doesn't trigger SEC; should not have been dispatched) |
| `gates.sec_email.value == "declined"` | `sec_email_declined_by_user` (canonical Gate-2 decline) |
| `sec_email` fails format sanity (or is literally `"declined"`) | `sec_email_invalid` (no echo of the input) |

> **Interim deviation (run-dir mode).** The canonical `agents/sec_email_gate.md` keeps the
> real email in **process memory** and writes only the sentinel `"email_provided"` to
> `gates.json`. Until the B.2 orchestrator exists, this fetcher's run-dir mode reads the
> email directly from `gates.json`, which means the email is on disk for the run's duration.
> The direct `--sec-email` mode keeps the email process-memory-only and is preferred for now;
> closing this gap is a future TD when the orchestrator can hold the email in memory and hand
> it to fetchers without a disk round-trip.

## Endpoints (all `data.sec.gov` — sec_user_agent territory)

| Step | URL |
|---|---|
| Submissions | `https://data.sec.gov/submissions/CIK<10digit>.json` (e.g. Circle = `CIK0001876042`) |
| CompanyFacts | `https://data.sec.gov/api/xbrl/companyfacts/CIK<10digit>.json` |

No call in this fetcher hits a non-SEC host. **CIK must be zero-padded to 10 digits**
(registry §6 quirk) — unpadded CIKs 404.

## Auth & email handling

- **Auth: none (no API key).** SEC mandates a `User-Agent` header containing a contact email
  (a documented requirement, not a convention — requests without a compliant UA are throttled
  or denied).
- The email **NEVER** appears anywhere persisted or logged: not in `meta/run.jsonl`, not in
  any error message (not even on validation failure — say `sec_email_invalid`, never echo the
  bad value), not in `raw_response`, not as an envelope field, and not in the `endpoint` field.
  SEC carries the email in the **header**, not the URL, so the email is automatically absent
  from the persisted `endpoint` — a test asserts the test-email string appears nowhere in
  `json.dumps(payload)`.

## Rate limit

- Registry §6: SEC documents **10 req/sec per IP**. This harness uses a conservative ceiling
  of **0.5 req/sec (2s between calls) + 100ms jitter, single concurrent request** — far under
  the documented cap, polite to a shared public resource. Pace *before* every outbound call
  (submissions → companyfacts), sequentially, never bursted.
- On **403** → halt `rate_limited_by_sec`, **no auto-retry** (SEC takes rate limits
  seriously; auto-retrying a 403 risks a longer block).
- On **429** → wait **60s** and retry **once** (sibling-fetcher pattern).

## Output

`meta/raw/sec_edgar/<subject_slug>_cik<CIK>_<utc_iso>.json` (gitignored via `meta/raw/*`),
the same 6-key envelope as the sibling fetchers:

```json
{
  "subject": "Circle",
  "subject_type": "stablecoin_issuer",
  "freshness_window": "30d",
  "endpoint": "https://data.sec.gov",
  "fetched_at": "<UTC ISO8601>",
  "raw_response": {
    "submissions": { "...": "verbatim /submissions/CIK<10>.json" },
    "companyfacts": { "...": "verbatim /api/xbrl/companyfacts/CIK<10>.json, or null if 404" }
  }
}
```

`endpoint` records only the base `https://data.sec.gov` host pattern — **no email** (it is in
the header, never the URL). `raw_response` is keyed by call; a soft-skipped `companyfacts` is
recorded as `null`.

## Error handling

Per `references/data_source_registry.md` §6:

- **`submissions` 404** → halt `subject_not_found_on_sec_edgar`.
- **403** (rate-limit / UA rejection) → halt `rate_limited_by_sec`, no auto-retry.
- **429** → wait 60s, retry **once**.
- **5xx** → halt `upstream_5xx_sec`.
- **`companyfacts` 404** → **soft skip** (`companyfacts` is `null`), not an error — not every
  CIK has companyfacts (delayed XBRL pipeline, registry §6).
- **CIK resolution fails** (not numeric and not a known registry name) → halt
  `cik_resolution_failed`.
- **Email / gate-coupling failures** → per the input-modes table above.

Do not paper over anomalies with extra retries (registry Cross-cutting rules).

## Forbidden

- **NEVER** log, print, or persist `sec_email` — not in `run.jsonl`, error messages,
  `raw_response`, the `endpoint` field, or any envelope key. Even validation failures say only
  `sec_email_invalid`, never the rejected string.
- **NEVER** format `SEC_UA_TEMPLATE` outside `_select_user_agent`, and never select a UA by
  anything other than the request host — that is the I-003 bug shape.
- **NEVER** send the email-bearing UA to a non-`*.sec.gov` host (the `investors.intuit.com`
  regression case must select the public UA).
- **NEVER** put the real email in test fixtures, default values, or constants — use
  `testpii@example.com`-style fakes; the live smoke reads the real email only from
  `$SEC_EDGAR_TEST_EMAIL`.
- **NEVER** accept both input modes or neither — exactly one (argparse-enforced).
- **NEVER** exceed the 0.5 req/sec ceiling by bursting; queue and wait.
- **NEVER** auto-retry a 403 — halt `rate_limited_by_sec`.
- **NEVER** infer `freshness_window` or `subject_type` — they come from the gates / dispatch.

## Events emitted to meta/run.jsonl

- `phase_enter` / `phase_exit` (standard).
- `sec_edgar_fetch_ok` — payload `{subject, subject_type, cik, endpoint, out_path}`
  (`endpoint` is the base host; never the email).
- `subject_not_found_on_sec_edgar` (submissions 404) — payload `{cik}`.
- `rate_limited_by_sec` (403) — payload `{}`.
- `upstream_5xx_sec` (5xx halt) — payload `{status}`.
- `cik_resolution_failed` (unknown subject) — payload `{subject}`.
- `sec_email_invalid` / `gates_file_unreadable` / `sec_email_gate_skipped` /
  `sec_email_declined_by_user` (input-mode failures) — payload `{}` (NEVER the email value).

## Cross-references

| File | Use |
|---|---|
| `references/data_source_registry.md` §6 | Canonical SEC EDGAR contract (endpoints, two-UA model, rate limit, CIK padding, quirks) |
| `references/equity_incidents_archive.md` I-003 | Origin of the two-UA invariant (Phase A user_agent email leak) |
| `agents/sec_email_gate.md` | Canonical P0_sec_email gate — produces `gates.sec_email` and the runtime email |
| `references/phase_contract.md` P1 | Fetcher dispatch — where this agent is invoked (conditional on the gate) |
| `references/subject_taxonomy.md` | 5-class taxonomy → `subject_type` |
| `agents/fetchers/etherscan_fetcher.md` | Sibling fetcher — shared 6-key envelope + pacing + runtime-secret pattern |
| `tools/fetchers/sec_edgar_fetch.py` | Implementation backing this spec |
| `tools/audit/user_agent_pii.py` | Post-run guard for the two-UA contract |
