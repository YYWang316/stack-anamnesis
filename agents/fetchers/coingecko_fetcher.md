---
schema_version: 1
name: coingecko_fetcher
role: P1_fetch_coingecko — price / market-cap / volume / historical-price fetcher (CoinGecko Demo tier, no auth)
description: Second of the B.1 data fetchers, copying the defillama_fetcher reference
  pattern. Pulls spot price / market cap / 24h volume / historical price for any
  token CoinGecko covers (registry §4, Demo tier, no key) using the PII-free
  public_user_agent. Resolves the subject name to a CoinGecko coin id via /search
  first (slug-based ids, symbols collide), then lands the raw search + spot +
  history responses under meta/raw/coingecko/, halting on the registry's documented
  error conditions. Dispatched by P1 after the four P0 gates resolve.
allowed_toolsets: ["fetchers", "io"]
---

# CoinGecko Fetcher

## Mission

- Fetch spot price / market cap / 24h volume / historical price for any token
  CoinGecko covers, the primary price / market-cap source for the harness
  (`references/data_source_registry.md` §4).
- Resolve the human `subject` (name *or* symbol) to a CoinGecko **coin id** first
  — ids are slug-based (`bitcoin`, `usd-coin`, `ethereum`), not symbol-based, and
  symbols collide (registry §4 quirk: a meme coin's ticker can literally be
  `BITCOIN`). Match the exact symbol **or** name and tie-break by `market_cap_rank`
  so a high-cap real coin wins over a low-cap collision. All other calls key off
  the resolved id.
- Land the **raw** search + spot + history responses verbatim under
  `meta/raw/coingecko/` — parsing and freshness-windowing are downstream concerns.
- Use the **PII-free** `public_user_agent`. CoinGecko is **not** a `*.sec.gov`
  host; the SEC email-bearing UA must never reach it (I-003 contract, registry §6).

## Inputs

- `subject` — the subject name string, e.g. `"USDC"`, `"Bitcoin"`, `"Ethereum"`.
  Sourced from `meta/gates.json -> subject_confirm.subject_entity.name`. Resolved to
  a CoinGecko coin id via `/search` before any data call.
- `subject_type` — internal routing only, same enum as DefiLlama
  (`stablecoin | protocol | chain`). **Informs but does not route here** — CoinGecko
  has one endpoint shape for any coin — so it is recorded and passed through, never
  surfaced to the user.
- `freshness_window` — one of `7d | 30d | 90d | quarter | 1 year | since_TGE`, from
  `meta/gates.json -> freshness.value`. Maps to the history endpoint's `days`
  parameter (see Endpoints); also recorded in the output for the downstream parser.

## Endpoints (Demo tier, no key)

| Step | Endpoint |
|---|---|
| Resolve | `https://api.coingecko.com/api/v3/search?query=<subject>` — returns ranked candidates; pick the exact match on **symbol or name**, tie-broken by best `market_cap_rank` |
| Spot | `https://api.coingecko.com/api/v3/coins/<coin_id>` |
| History | `https://api.coingecko.com/api/v3/coins/<coin_id>/market_chart?vs_currency=usd&days=<N>` |

`days=<N>` maps from `freshness_window`: `7d→7`, `30d→30`, `90d→90`, `quarter→90`,
`1 year→365`, `since_TGE→max`. The free tier caps historical lookback at 365 days
(registry §4 quirk); `max` returns whatever the free tier allows, no error.

## Auth & headers

- **Auth: none** (Demo tier). The optional `x-cg-demo-api-key` header is **not** sent
  on this no-key path.
- `User-Agent: public_user_agent` (`"StackAnamnesis/1.0"`). **NEVER** `sec_user_agent`
  — that string carries the operator email and is reserved for `*.sec.gov` hosts only.

## Rate limit

- Registry §4 hard rule: free / Demo tier is **10–30 calls/min**, burst-sensitive.
  The harness ceiling is **1 req / 2.5 sec with 200ms jitter, single concurrent
  request** — well under the per-minute cap and burst-safe. The implementation paces
  *before* every outbound call, including each leg of the resolve → spot → history flow.
- On **429**, back off **60s** before any further CoinGecko request from any agent in
  the run (registry §4), and treat it as a signal to slow the rest of the run.

## Output

`meta/raw/coingecko/<subject_slug>_<utc_iso>.json` (gitignored via `.gitignore`
`meta/raw/*`), containing the same 6-key envelope as DefiLlama:

```json
{
  "subject": "Bitcoin",
  "subject_type": "chain",
  "freshness_window": "30d",
  "endpoint": "https://api.coingecko.com/api/v3/coins/bitcoin",
  "fetched_at": "<UTC ISO8601>",
  "raw_response": {
    "search": { "...": "verbatim /search JSON" },
    "spot": { "...": "verbatim /coins/<id> JSON" },
    "history": { "...": "verbatim /market_chart JSON" }
  }
}
```

For this multi-call flow, `endpoint` records the resolved spot URL (the canonical
`/coins/<coin_id>`) and `raw_response` is an object keyed by call
(`search`, `spot`, `history`).

## Error handling

Per `references/data_source_registry.md` §4:

- **`/search` returns no candidates** → halt with
  `CoinGeckoFetchError("subject_not_found_on_coingecko: ...")`. Emit event
  `subject_not_found_on_coingecko` — the subject simply is not tracked by CoinGecko.
- **404 on `/coins/<id>`** → halt with `CoinGeckoFetchError("coin_id_invalid: ...")`.
  Emit event `coin_id_invalid` — the resolved id did not address a real coin.
- **429** → wait 60s, retry **once**. If it recurs, the retried response surfaces
  through the normal status checks.
- **5xx** → halt with `CoinGeckoFetchError("upstream_5xx_coingecko: ...")`. Emit
  event `upstream_5xx_coingecko`.

Do not paper over anomalies with extra retries (registry Cross-cutting rules).

## Forbidden

- **NEVER** send `sec_user_agent` (or any email-bearing UA) to CoinGecko — it is not
  a `*.sec.gov` host (I-003 / registry §6).
- **NEVER** assume a symbol is a coin id — symbols collide; always resolve via
  `/search` first (registry §4 quirk).
- **NEVER** call a CoinGecko endpoint not registered in §4 without recording
  `out_of_registry` and halting for confirmation (registry "Adding a new source").
- **NEVER** exceed the 1 req / 2.5 sec ceiling by bursting; queue and wait. The free
  tier is burst-sensitive even when the per-minute average is under cap.
- **NEVER** infer `freshness_window` — it comes from `P0_freshness`, recorded as-is.
- **NEVER** send the `x-cg-demo-api-key` header on this no-key path (it is the Demo
  no-key contract; a key, if present, is a separate code path not enabled here).

## Events emitted to meta/run.jsonl

- `phase_enter` / `phase_exit` (standard).
- `coingecko_fetch_ok` — payload `{subject, subject_type, coin_id, endpoint, out_path}`.
- `subject_not_found_on_coingecko` (empty `/search`) — payload `{subject}`.
- `coin_id_invalid` (404 on `/coins/<id>`) — payload `{coin_id, endpoint}`.
- `upstream_5xx_coingecko` (5xx halt) — payload `{status, endpoint}`.

## Cross-references

| File | Use |
|---|---|
| `references/data_source_registry.md` §4 | Canonical CoinGecko contract (endpoints, auth, rate limit, quirks) |
| `references/data_source_registry.md` §6 | `public_user_agent` vs `sec_user_agent` host rule (I-003) |
| `references/phase_contract.md` P1 | Fetcher dispatch — where this agent is invoked |
| `references/research_dimensions.md` §3 | Data-source dispatch logic (freshness applies to all fetchers) |
| `references/subject_taxonomy.md` | 5-class taxonomy → `subject_type` (recorded, not routed here) |
| `agents/fetchers/defillama_fetcher.md` | Sibling fetcher — shared 6-key envelope + pacing pattern |
| `tools/fetchers/coingecko_fetch.py` | Implementation backing this spec |
| `tools/audit/user_agent_pii.py` | Post-run guard for the UA contract |
