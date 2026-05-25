---
schema_version: 1
name: etherscan_fetcher
role: P1_fetch_etherscan — chain-side token supply / info / recent-transfer fetcher (Etherscan V2 unified API, key-based)
description: Third of the B.1 data fetchers and the first key-based one, extending the
  coingecko_fetcher reference pattern. Pulls chain-side data (token supply, token info,
  recent transfer stats) across the EVM chains the Etherscan family covers via the V2
  unified chainid-based API, using the PII-free public_user_agent. Resolves the subject
  to a contract address (0x passthrough or a small in-fetcher symbol registry), reads the
  API key at runtime from ~/.config/anamnesis/etherscan.key, and lands the raw
  tokensupply + tokeninfo + tokentx responses under meta/raw/etherscan/ — never persisting
  or logging the key. Dispatched by P1 after the four P0 gates resolve.
allowed_toolsets: ["fetchers", "io"]
---

# Etherscan Fetcher

## Mission

- Fetch **chain-side** data — token total supply, token info, and recent token-transfer
  stats — for any token the Etherscan family covers, across all the EVM chains it serves,
  via the **V2 unified API** (a single `chainid`-keyed endpoint rather than per-chain
  hosts) (`references/data_source_registry.md` §3).
- Resolve the human `subject` to a **contract address** first: a `0x…` address is taken
  verbatim (lowercased), otherwise a small in-fetcher symbol registry maps known tokens
  (USDC, USDT, DAI, WETH — **chain 1 only** for B.1.3; broader resolution is a future TD).
- Land the **raw** tokensupply + tokeninfo + tokentx responses verbatim under
  `meta/raw/etherscan/` — parsing and freshness-windowing are downstream concerns.
- This is the **first key-based fetcher**. The API key is read at runtime from
  `~/.config/anamnesis/etherscan.key` and **never** logged, never persisted in the
  envelope, and never surfaced in an error message (see Auth & key handling).
- Use the **PII-free** `public_user_agent`. Etherscan is **not** a `*.sec.gov` host; the
  SEC email-bearing UA must never reach it (I-003 contract, registry §6 / Cross-cutting).

## Inputs

- `subject` — the subject string: either a `0x…` contract address (42 chars) taken
  verbatim, or a known token symbol (`"USDC"`, `"USDT"`, `"DAI"`, `"WETH"`) resolved via
  the in-fetcher registry. Sourced from
  `meta/gates.json -> subject_confirm.subject_entity.name`.
- `subject_type` — same enum as the sibling fetchers (`stablecoin | protocol | chain`),
  used here to **route**:
  - `stablecoin` / `protocol` → resolve to a contract address, then tokensupply +
    tokeninfo + recent-transfer stats.
  - `chain` → **not supported** by this fetcher (chain-level RPC stats are the RPC
    fetcher's job in B.1.5). Halt with `subject_type_unsupported`.
- `chain_id` — int, default `1` (Ethereum mainnet). Common values: `137` Polygon,
  `56` BSC, `42161` Arbitrum, `10` Optimism, `8453` Base. Selects the V2 `chainid`.
- `freshness_window` — one of `7d | 30d | 90d | quarter | 1 year | since_TGE`, from
  `meta/gates.json -> freshness.value`. Passed through and recorded; the `tokentx`
  action supports `startblock`/`endblock` windowing for downstream window queries.

## Endpoints (V2 unified API)

All calls hit `https://api.etherscan.io/v2/api` with `chainid=<chain_id>` and
`apikey=<key>`:

| Step | Params |
|---|---|
| Token supply | `module=stats` `action=tokensupply` `contractaddress=<addr>` |
| Token info | `module=token` `action=tokeninfo` `contractaddress=<addr>` |
| Recent transfers | `module=account` `action=tokentx` `contractaddress=<addr>` `page=1` `offset=100` `sort=desc` (top 100 most recent token transfers) |

`tokeninfo` is a **legacy Pro endpoint** — it may `404` (or return `status=0` / `NOTOK`)
on the free tier. Treat that as a **soft skip**: record `null` for that sub-call and
continue; it is **not** an error.

## Auth & key handling

- **Auth: API key in the `apikey=<key>` query param.** The key is read at runtime from
  `~/.config/anamnesis/etherscan.key` (mode 600, outside the repo; `.gitignore` excludes
  `~/.config/anamnesis/` as second-layer protection).
- **The key NEVER appears anywhere persisted or logged**: not in `meta/run.jsonl`, not in
  any error message, not in `raw_response`, not in print statements, not in test output,
  and **not in the envelope's `endpoint` field**. The persisted `endpoint` is the base URL
  `https://api.etherscan.io/v2/api?chainid=<id>` with `apikey` stripped.
- `User-Agent: public_user_agent` (`"StackAnamnesis/1.0"`). **NEVER** `sec_user_agent`.

## Rate limit

- Registry §3: free tier is **5 req/sec** hard cap, 100,000 calls/day, per-chain quota.
- The harness ceiling is **1 req / 0.25 sec with 50ms jitter, single concurrent request**
  (~3 req/sec — conservative, one below the documented 5 and burst-safe). The fetcher
  paces *before* every outbound call (each of tokensupply → tokeninfo → tokentx). The
  three calls are made sequentially through the throttle, never bursted in parallel.
- On **429**, wait **60s** and retry **once** (sibling-fetcher pattern). The registry's
  §3 exponential-backoff note is the provider-level guidance; the harness uses the simpler
  conservative retry shared with the DefiLlama / CoinGecko fetchers.

## Output

`meta/raw/etherscan/<subject_slug>_chain<id>_<utc_iso>.json` (gitignored via `.gitignore`
`meta/raw/*`), the same 6-key envelope as the sibling fetchers:

```json
{
  "subject": "USDC",
  "subject_type": "stablecoin",
  "freshness_window": "30d",
  "endpoint": "https://api.etherscan.io/v2/api?chainid=1",
  "fetched_at": "<UTC ISO8601>",
  "raw_response": {
    "tokensupply": { "...": "verbatim stats/tokensupply JSON" },
    "tokeninfo": { "...": "verbatim token/tokeninfo JSON, or null if soft-skipped" },
    "tokentx": { "...": "verbatim account/tokentx JSON" }
  }
}
```

`endpoint` records the base URL with `chainid` but **without** `apikey`. `raw_response`
is an object keyed by action (`tokensupply`, `tokeninfo`, `tokentx`); a soft-skipped
sub-call is recorded as `null`.

## Error handling

Per `references/data_source_registry.md` §3:

- **Key file missing or empty** → halt with `EtherscanFetchError("etherscan_key_missing: ...")`.
  The message says only *"etherscan key required at the standard location, see registry §3"*
  — it never prints the attempted path (which would leak the OS username).
- **`status=0` with message `"Invalid API Key"`** on any call → halt with
  `etherscan_key_invalid`. The key value is **never** included in the error.
- **`subject_type == "chain"`** → halt with `subject_type_unsupported` (use the RPC fetcher).
- **Address resolution fails** (not a `0x…` address and not a known symbol on this chain)
  → halt with `address_resolution_failed`.
- **`tokeninfo` 404 / `status=0` NOTOK** → **soft skip** (record `null`), not an error.
- **429** → wait 60s, retry **once**.
- **5xx** → halt with `EtherscanFetchError("upstream_5xx_etherscan: ...")`.

Do not paper over anomalies with extra retries (registry Cross-cutting rules).

## Forbidden

- **NEVER** log, print, or persist the API key — not in `run.jsonl`, error messages,
  `raw_response`, or the `endpoint` field. Strip `apikey` before serializing.
- **NEVER** print `Path.home()` or the resolved key path in any error path (leaks username).
- **NEVER** put the real key in test fixtures — use a `FAKE_KEY_FOR_TESTS` constant.
- **NEVER** send `sec_user_agent` (or any email-bearing UA) to Etherscan — not a
  `*.sec.gov` host (I-003 / registry §6).
- **NEVER** route a `subject_type == "chain"` request here — halt `subject_type_unsupported`.
- **NEVER** exceed the 1 req / 0.25 sec ceiling by bursting; queue and wait.
- **NEVER** call an Etherscan action not registered in §3 without recording
  `out_of_registry` and halting for confirmation (registry "Adding a new source").
- **NEVER** infer `freshness_window` or `chain_id` — they come from the gates / dispatch.

## Events emitted to meta/run.jsonl

- `phase_enter` / `phase_exit` (standard).
- `etherscan_fetch_ok` — payload `{subject, subject_type, chain_id, address, endpoint, out_path}`
  (`endpoint` is the apikey-stripped base URL; never the key).
- `etherscan_key_missing` (key file absent/empty) — payload `{}` (no path, no key).
- `etherscan_key_invalid` (Invalid API Key) — payload `{chain_id}` (no key).
- `subject_type_unsupported` (`chain` routed here) — payload `{subject_type}`.
- `address_resolution_failed` (unknown symbol/address) — payload `{subject, chain_id}`.
- `upstream_5xx_etherscan` (5xx halt) — payload `{status, endpoint}` (apikey-stripped).

## Cross-references

| File | Use |
|---|---|
| `references/data_source_registry.md` §3 | Canonical Etherscan contract (V2 API, auth, rate limit, key path, quirks) |
| `references/data_source_registry.md` §6 / Cross-cutting | `public_user_agent` vs `sec_user_agent` host rule (I-003); keys never in code/logs |
| `references/phase_contract.md` P1 | Fetcher dispatch — where this agent is invoked |
| `references/research_dimensions.md` §3 | Data-source dispatch logic (freshness applies to all fetchers) |
| `references/subject_taxonomy.md` | 5-class taxonomy → `subject_type` (routes here; `chain` halts) |
| `agents/fetchers/coingecko_fetcher.md` | Sibling fetcher — shared 6-key envelope + pacing pattern |
| `tools/fetchers/etherscan_fetch.py` | Implementation backing this spec |
| `tools/audit/user_agent_pii.py` | Post-run guard for the UA contract |
