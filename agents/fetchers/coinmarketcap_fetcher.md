---
schema_version: 1
name: coinmarketcap_fetcher
role: P1_fetch_coinmarketcap — price / market-cap / volume cross-check + fallback fetcher (CoinMarketCap Pro v1, Basic free tier, API key)
description: Sixth of the B.1 data fetchers, copying the coingecko_fetcher reference
  pattern for the price / market-cap surface and the etherscan_fetcher pattern for
  runtime API-key handling. Pulls spot price / market cap / 24h volume (and optional
  historical quotes) for any token CoinMarketCap covers (registry §13, Basic free
  tier, key required) using the PII-free public_user_agent. Resolves the human
  subject to a CMC numeric id slug-first (via /quotes/latest?slug=, since /map ignores
  a slug param) with a /map?symbol= fallback (CMC ids differ from CoinGecko slugs,
  symbols collide), then lands the raw resolve + quotes_latest +
  quotes_historical responses under meta/raw/coinmarketcap/, halting on the
  registry's documented error conditions. Used as a CoinGecko (§4) cross-check or
  fallback, never the primary price source.
allowed_toolsets: ["fetchers", "io"]
---

# CoinMarketCap Fetcher

## Mission

- Fetch spot price / market cap / 24h volume (and, where the tier allows, historical
  quotes) for any token CoinMarketCap covers — the **cross-check / fallback** price
  and market-cap source for the harness (`references/data_source_registry.md` §13).
  CoinGecko (§4) is **primary**; CMC is enabled to resolve a price / market-cap
  discrepancy via a second source, or when CoinGecko coverage or rate limits fail.
- Resolve the human `subject` (name *or* symbol) to a CoinMarketCap **numeric id**
  first, slug-first via `/quotes/latest?slug=` with a `/map?symbol=` fallback (see
  Resolution strategy). CMC ids are **not** CoinGecko slugs (registry §13 quirk: never
  assume the same identifier across the two sources), and symbols collide — so resolve
  to the id before the spot/history calls. Those calls key off the resolved id.
- Land the **raw** map + quotes_latest + quotes_historical responses verbatim under
  `meta/raw/coinmarketcap/` — parsing and freshness-windowing are downstream concerns.
- Use the **PII-free** `public_user_agent`. CoinMarketCap is **not** a `*.sec.gov`
  host; the SEC email-bearing UA must never reach it (I-003 contract, registry §6).

## Inputs

- `subject` — the subject name string, e.g. `"USDC"`, `"Bitcoin"`. Sourced from
  `meta/gates.json -> subject_confirm.subject_entity.name`. Resolved to a CMC numeric
  id slug-first (via `/quotes/latest?slug=`) with a `/map?symbol=` fallback before the
  spot/history calls.
- `subject_type` — internal routing only, same enum as the sibling fetchers
  (`stablecoin | protocol | chain`). **Informs but does not route here** — CMC has one
  endpoint shape for any coin — so it is recorded and passed through, never surfaced
  to the user.
- `freshness_window` — one of `7d | 30d | 90d | quarter | 1 year | since_TGE`, from
  `meta/gates.json -> freshness.value`. Maps to the historical-quotes `count`
  parameter (see Endpoints); also recorded in the output for the downstream parser.

## Endpoints (CMC Pro v1, Basic free tier)

| Step | Endpoint |
|---|---|
| Resolve (slug) | `https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?slug=<subject_slug>` — see Resolution strategy below |
| Resolve (symbol fallback) | `https://pro-api.coinmarketcap.com/v1/cryptocurrency/map?symbol=<subject_upper>` |
| Spot | `https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?id=<id>` |
| History | `https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/historical?id=<id>&count=<N>` — **optional**; the Basic free tier does not include it. A 401 here is a **soft skip** (history is `null` in the envelope) |

`count=<N>` maps from `freshness_window`: `7d→7`, `30d→30`, `90d→90`, `quarter→90`,
`1 year→365`, `since_TGE→max`. The historical endpoint is gated to paid tiers; on the
Basic free tier it returns 401 and we record `quotes_historical: null` rather than
halting.

**Resolution strategy (slug-first, symbol fallback).** Symbols collide on CMC
(registry §13 quirk: a meme coin's symbol is literally "BITCOIN", so `symbol=Bitcoin`
returns the meme coin and `symbol=BTC` is required to reach the real Bitcoin). Slug is
unique in CMC's namespace, so resolve slug-first. **Endpoint caveat (verified live):**
`/cryptocurrency/map` **silently ignores a `slug` param** — it returns the full
8362-coin list with `data[0]` always Bitcoin (id 1) — so slug resolution must go
through `/cryptocurrency/quotes/latest`, which *does* filter by slug. `/map` filters
correctly by `symbol`.

To accept both human names ("Bitcoin", "USD Coin") and tickers ("BTC", "USDC") without
name-vs-symbol confusion:

1. Try `/quotes/latest?slug=<subject.lower().replace(' ', '-')>` first. Slug is unique
   → the response is a `{id: quote}` dict; if non-empty, take that id. An invalid slug
   (e.g. a ticker like `btc`) returns HTTP 400 with empty data → fall through.
2. If empty, fall back to `/map?symbol=<subject.upper()>`. May return multiple
   candidates on collision → tie-break by lowest `rank` (real high-cap tokens always
   have a rank; meme collisions are rank ~900+; `/map`'s field is `rank`, not
   `cmc_rank`).
3. If both empty → `subject_not_found_on_cmc`.

This aligns with CoinGecko (B.1.2)'s spirit of "accept name or ticker, defeat symbol
collision via canonical ordering" — adapted to CMC's slug-based unique key instead of
CoinGecko's name-match affordance.

## Auth & headers

- **Auth: API key required on every tier, including Basic free** (registry §13). Sent
  in the `X-CMC_PRO_API_KEY` request **header**, read at runtime from
  `~/.config/anamnesis/coinmarketcap.key`. The key is **NEVER** logged, **NEVER**
  echoed in an error, and **NEVER** persisted in the envelope.
- `User-Agent: public_user_agent` (`"StackAnamnesis/1.0"`). **NEVER** `sec_user_agent`
  — that string carries the operator email and is reserved for `*.sec.gov` hosts only.
- `Accept: application/json`.

## Rate limit

- Registry §13: Basic free tier has a **30 req/min** hard cap (429 on overage,
  resetting every 60s) and is metered by **call credits** (~1 credit / 100 data
  points). The harness ceiling is a conservative **1 req / 2 sec with 100ms jitter,
  single concurrent request** — well under 30/min and credit-frugal. The
  implementation paces *before* every outbound call (resolve → spot → history).
- On **429**, back off **60s** and retry **once** (registry §13); treat it as a signal
  to slow the rest of the run.
- Prefer **targeted single-asset queries** over wide listings — credit metering burns
  the Basic budget fast (registry §13 quirk).

## Output

`meta/raw/coinmarketcap/<subject_slug>_<utc_iso>.json` (gitignored via `.gitignore`
`meta/raw/*`), containing the same 6-key envelope as the sibling fetchers:

```json
{
  "subject": "Bitcoin",
  "subject_type": "chain",
  "freshness_window": "30d",
  "endpoint": "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?id=1",
  "fetched_at": "<UTC ISO8601>",
  "raw_response": {
    "resolve": { "...": "verbatim slug or symbol lookup that resolved the id" },
    "quotes_latest": { "...": "verbatim /quotes/latest?id JSON" },
    "quotes_historical": null
  }
}
```

For this multi-call flow, `endpoint` records the resolved spot URL (the canonical
`/quotes/latest?id=<id>`) and `raw_response` is an object keyed by call
(`resolve`, `quotes_latest`, `quotes_historical`). `resolve` holds whichever call
resolved the id — a `/quotes/latest?slug=` response (slug path) or a `/map?symbol=`
response (symbol-fallback path). The key is in the **header**, never the URL, so the
persisted `endpoint` is already key-free. `quotes_historical` is `null` whenever the
tier rejects the historical endpoint with 401.

## Error handling

Per `references/data_source_registry.md` §13:

- **Key file missing / empty** → halt with
  `CmcFetchError("cmc_key_missing: ...")` **before** any network call. Emit event
  `cmc_key_missing`. The error never includes the resolved path (which would leak the
  OS username).
- **401 / 403** → halt with `CmcFetchError("cmc_unauthorized")`. Emit event
  `cmc_unauthorized`. The error **never echoes the key**.
- **Both slug and symbol resolution return no candidates** (the slug lookup yields
  empty data — including the HTTP 400 thrown for an invalid slug — and the
  `/map?symbol=` fallback is also empty) → halt with
  `CmcFetchError("subject_not_found_on_cmc: ...")`. Emit event
  `subject_not_found_on_cmc` — the subject is not tracked by CoinMarketCap.
- **429** → wait 60s, retry **once**. If it recurs, the retried response surfaces
  through the normal status checks.
- **5xx** → halt with `CmcFetchError("upstream_5xx_cmc: ...")`. Emit event
  `upstream_5xx_cmc`.
- **Historical endpoint 401** (Basic free-tier restriction) → **soft skip**:
  `quotes_historical` is `null` in the envelope and the fetch still succeeds.

Do not paper over anomalies with extra retries (registry Cross-cutting rules).

## Forbidden

- **NEVER** send `sec_user_agent` (or any email-bearing UA) to CoinMarketCap — it is
  not a `*.sec.gov` host (I-003 / registry §6).
- **NEVER** put the API key in a URL, a log line, an error message, or the persisted
  envelope — it lives in the `X-CMC_PRO_API_KEY` header only, in memory.
- **NEVER** assume a CMC id equals a CoinGecko slug or that a symbol is an id —
  resolve slug-first (`/quotes/latest?slug=`) with a `/map?symbol=` fallback (registry
  §13 quirk). **NEVER** pass `slug=` to `/map` expecting it to filter — it is silently
  ignored and returns the full list (data[0] always Bitcoin).
- **NEVER** run CMC as the **primary** price source — CoinGecko §4 is primary; running
  both by default double-spends the rate / credit budget (registry §13 "Do NOT use
  for").
- **NEVER** call a CMC endpoint not registered in §13 without recording
  `out_of_registry` and halting for confirmation (registry "Adding a new source").
- **NEVER** exceed the 1 req / 2 sec ceiling by bursting; queue and wait. Wide listings
  calls additionally burn credits — prefer targeted single-asset queries.
- **NEVER** infer `freshness_window` — it comes from `P0_freshness`, recorded as-is.

## Events emitted to meta/run.jsonl

- `phase_enter` / `phase_exit` (standard).
- `coinmarketcap_fetch_ok` — payload `{subject, subject_type, cmc_id, endpoint, out_path}`.
- `cmc_key_missing` (no key file) — payload `{}` (never the path).
- `cmc_unauthorized` (401/403) — payload `{}` (never the key).
- `subject_not_found_on_cmc` (slug + symbol both empty) — payload `{subject}`.
- `upstream_5xx_cmc` (5xx halt) — payload `{status, endpoint}`.

## Cross-references

| File | Use |
|---|---|
| `references/data_source_registry.md` §13 | Canonical CoinMarketCap contract (endpoints, auth, rate limit, quirks) |
| `references/data_source_registry.md` §4 | CoinGecko — the **primary** price source CMC cross-checks / falls back to |
| `references/data_source_registry.md` §6 | `public_user_agent` vs `sec_user_agent` host rule (I-003) |
| `references/phase_contract.md` P1 | Fetcher dispatch — where this agent is invoked |
| `references/research_dimensions.md` §3 | Data-source dispatch logic (freshness applies to all fetchers) |
| `references/subject_taxonomy.md` | 5-class taxonomy → `subject_type` (recorded, not routed here) |
| `agents/fetchers/coingecko_fetcher.md` | Sibling fetcher — shared 6-key envelope + symbol-resolution pattern |
| `agents/fetchers/etherscan_fetcher.md` | Sibling fetcher — runtime API-key handling pattern |
| `tools/fetchers/coinmarketcap_fetch.py` | Implementation backing this spec |
| `tools/audit/user_agent_pii.py` | Post-run guard for the UA / key contract |
