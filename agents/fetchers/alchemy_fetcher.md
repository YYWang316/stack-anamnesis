---
schema_version: 1
name: alchemy_fetcher
role: P1_fetch_alchemy — chain-side state fetcher via JSON-RPC (Alchemy, URL-embedded key)
description: Fifth of the B.1 data fetchers and the first JSON-RPC one, extending the
  etherscan_fetcher key-handling pattern. Reads chain-side state directly — latest block,
  gas price, native + token balances, contract code, raw eth_call — by POSTing JSON-RPC
  bodies to the Alchemy endpoint, using the PII-free public_user_agent. This is the "deep"
  on-chain layer that Etherscan's API tier does not cover (raw eth_call, eth_getStorageAt).
  Alchemy embeds the API key in the URL path (/v2/<key>), so the FULL URL is the secret:
  it is read at runtime from ~/.config/anamnesis/alchemy.key, never logged, and the
  persisted envelope records only the REDACTED form (/v2/<REDACTED>). Dispatched by P1
  after the four P0 gates resolve.
allowed_toolsets: ["fetchers", "io"]
---

# Alchemy RPC Fetcher

## Mission

- Fetch **chain-side state** via **JSON-RPC** — latest block number, gas price, native
  (ETH) balance, transaction count, ERC-20 token state (contract code, `totalSupply` via
  raw `eth_call`) — for the chain the configured Alchemy URL serves
  (`references/data_source_registry.md` §5).
- This is the **deep on-chain layer** that Etherscan's API tier does not cover: raw
  `eth_call` and `eth_getStorageAt` against a contract, read straight from node state
  rather than from a parsed API. It is the only way to **ground-truth** a token's
  `totalSupply` or a treasury's balance against the chain itself.
- Land the **raw** JSON-RPC responses verbatim under `meta/raw/alchemy/`, keyed by RPC
  method name — parsing and decoding are downstream concerns.
- This is the **first JSON-RPC fetcher** and a variant of the key-based pattern: Alchemy
  embeds the API key **in the URL path** (`/v2/<key>`), so the **entire URL is the
  secret**. It is read at runtime from `~/.config/anamnesis/alchemy.key`, **never** logged,
  **never** persisted unredacted, and **never** surfaced in an error message (see Auth).
- Use the **PII-free** `public_user_agent`. Alchemy is **not** a `*.sec.gov` host; the SEC
  email-bearing UA must never reach it (I-003 contract, registry §6 / Cross-cutting).

## Inputs

- `subject` — meaning depends on `subject_type`:
  - `stablecoin_issuer` / `orchestrator` → a contract address (`0x…`, 42 chars) for state
    reads (`eth_getCode`, `eth_call totalSupply`).
  - `wallet` → a wallet address (`0x…`, 42 chars) for balance queries.
  - `chain` → an empty / placeholder string; the fetcher returns chain-level stats
    (latest block, gas price) and ignores the subject value.
- `subject_type` — the 5-class taxonomy enum (`stablecoin_issuer | orchestrator | wallet |
  chain | agentic_payment_layer`), used here to **route** to a default set of JSON-RPC
  calls. `agentic_payment_layer` is **not supported** in B.1.5 (broader RPC coverage is a
  future TD) — halt with `subject_type_unsupported`.
- `freshness_window` — one of `7d | 30d | 90d | quarter | 1 year | since_TGE`, from
  `meta/gates.json -> freshness.value`. Informs the `blockTag` parameter: `since_TGE` maps
  to `"earliest"`; every other window maps to `"latest"`. Full historical RPC (state at
  arbitrary old blocks) is too expensive on the free tier — use The Graph for that.

## Endpoint

- **ONE endpoint**: the full URL read from `~/.config/anamnesis/alchemy.key` (e.g.
  `https://eth-mainnet.g.alchemy.com/v2/<32-char-key>`). All JSON-RPC calls **POST** to
  this single URL with a JSON body; the method is selected in the body, not the path.
- The URL itself **contains the key** in its `/v2/<key>` path segment. It must **never** be
  logged anywhere except as the **redacted** form
  `https://eth-mainnet.g.alchemy.com/v2/<REDACTED>`.

## Auth & key handling

- **Auth: URL-embedded key.** Unlike Etherscan (key in an `apikey=` query param), Alchemy
  puts the key in the URL path, so the stored secret is the whole URL. Read at runtime from
  `~/.config/anamnesis/alchemy.key` (mode 600, outside the repo; `.gitignore` excludes
  `~/.config/anamnesis/` as second-layer protection).
- **The URL NEVER appears unredacted anywhere persisted or logged**: not in `meta/run.jsonl`,
  not in any error message, not in `raw_response`, not in print statements, not in test
  output, and **not in the envelope's `endpoint` field**. Everything that records or logs
  the endpoint passes it through `_redact_url` first, which replaces the `/v2/<key>` segment
  with `/v2/<REDACTED>`. The persisted `endpoint` is the redacted URL.
- `User-Agent: public_user_agent` (`"StackAnamnesis/1.0"`). **NEVER** `sec_user_agent`.
  A `_select_user_agent` helper exists for consistency with the SEC fetcher's 2-UA pattern,
  but for Alchemy it always returns the public UA (no `*.sec.gov` overlap is possible).

## Rate limit

- Registry §5: Alchemy free tier is **300 compute units (CU) per second** — billing is by
  CU, not requests. Typical method costs: `eth_call` ~26 CU, `eth_getBalance` ~16 CU,
  `eth_blockNumber` ~10 CU.
- The harness ceiling is **0.5 req/sec (1 req / 2 sec) with 50ms jitter, single concurrent
  request** (~150 CU/sec for a typical mix — comfortably under the 300 CU/sec cap). The
  fetcher paces *before* every outbound JSON-RPC call; calls are made sequentially through
  the throttle, never bursted in parallel.
- On **429**, wait **60s** and retry **once** (sibling-fetcher pattern), then fall through
  to the error contract below.

## Output

`meta/raw/alchemy/<subject_slug>_chain<id>_<utc_iso>.json` (gitignored via `.gitignore`
`meta/raw/*`), the same 6-key envelope as the sibling fetchers:

```json
{
  "subject": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
  "subject_type": "stablecoin_issuer",
  "freshness_window": "30d",
  "endpoint": "https://eth-mainnet.g.alchemy.com/v2/<REDACTED>",
  "fetched_at": "<UTC ISO8601>",
  "raw_response": {
    "eth_getCode": { "...": "verbatim JSON-RPC response payload" },
    "eth_call": { "...": "verbatim JSON-RPC response payload" }
  }
}
```

`endpoint` is the **redacted** URL — the key never lands on disk. `raw_response` is an
object keyed by the JSON-RPC method name; each value is the verbatim response payload for
that call.

## Default RPC calls per subject_type

| subject_type | JSON-RPC calls |
|---|---|
| `chain` | `eth_blockNumber` `[]`, `eth_gasPrice` `[]` |
| `wallet` | `eth_getBalance` `[<address>, <blockTag>]`, `eth_getTransactionCount` `[<address>, <blockTag>]` |
| `stablecoin_issuer` / `orchestrator` | `eth_getCode` `[<address>, <blockTag>]`, `eth_call` `[{to:<address>, data:"0x18160ddd"}, <blockTag>]` |
| `agentic_payment_layer` | **unsupported** → halt `subject_type_unsupported` |

`0x18160ddd` is the function selector for `totalSupply()`. `<blockTag>` is `"earliest"` for
`since_TGE`, else `"latest"`. `<address>` is the resolved `0x…` subject.

## Error handling

Per `references/data_source_registry.md` §5:

- **Key file missing or empty** → halt with `AlchemyFetchError("alchemy_key_missing")`. The
  message never prints the attempted path (which would leak the OS username).
- **URL does not match the expected pattern** (no `https://…g.alchemy.com/v2/<key>` shape)
  → halt with `alchemy_url_malformed`. The malformed URL is **never** echoed (it may still
  be a real secret typed wrong).
- **JSON-RPC error response** (payload has an `"error"` field) → halt with
  `alchemy_rpc_error` carrying the error `code` + `message` — **never** the URL.
- **401 / 403** → halt with `alchemy_unauthorized` (key revoked or wrong network). The URL
  and key are **never** echoed.
- **429** → wait 60s and retry **once**.
- **5xx** → halt with `AlchemyFetchError("upstream_5xx_alchemy")` (status only; redacted URL).
- **`subject_type == "agentic_payment_layer"`** → halt with `subject_type_unsupported`.

Do not paper over anomalies with extra retries (registry Cross-cutting rules).

## Forbidden

- **NEVER** log, print, or persist the unredacted URL — not in `run.jsonl`, error messages,
  `raw_response`, or the `endpoint` field. Route every endpoint mention through `_redact_url`.
- **NEVER** print `Path.home()` or the resolved key path in any error path (leaks username).
- **NEVER** echo a malformed URL value — it may be a mistyped real key.
- **NEVER** put the real Alchemy URL in test fixtures, defaults, or constants — use
  `FAKE_URL = "https://eth-mainnet.g.alchemy.com/v2/FAKE_KEY_FOR_TESTS"`.
- **NEVER** send `sec_user_agent` (or any email-bearing UA) to Alchemy — not a `*.sec.gov`
  host (I-003 / registry §6).
- **NEVER** route a `subject_type == "agentic_payment_layer"` request here — halt
  `subject_type_unsupported`.
- **NEVER** exceed the 0.5 req/sec ceiling by bursting; queue and wait.
- **NEVER** call a JSON-RPC method not registered above without recording `out_of_registry`
  and halting for confirmation (registry "Adding a new source").
- **NEVER** infer `freshness_window` or `subject_type` — they come from the gates / dispatch.

## Events emitted to meta/run.jsonl

- `phase_enter` / `phase_exit` (standard).
- `alchemy_fetch_ok` — payload `{subject, subject_type, methods, endpoint, out_path}`
  (`endpoint` is the REDACTED URL; never the key).
- `alchemy_key_missing` (key file absent/empty) — payload `{}` (no path, no URL).
- `alchemy_url_malformed` (file does not match the URL pattern) — payload `{}` (no URL).
- `alchemy_rpc_error` (JSON-RPC error field) — payload `{method, code, message}` (no URL).
- `alchemy_unauthorized` (401/403) — payload `{status}` (no URL, no key).
- `subject_type_unsupported` (`agentic_payment_layer` routed here) — payload `{subject_type}`.
- `upstream_5xx_alchemy` (5xx halt) — payload `{status, endpoint}` (REDACTED URL).

## Cross-references

| File | Use |
|---|---|
| `references/data_source_registry.md` §5 | Canonical RPC-tier contract (Alchemy, auth, CU rate limit, JSON-RPC methods, quirks) |
| `references/data_source_registry.md` §6 / Cross-cutting | `public_user_agent` vs `sec_user_agent` host rule (I-003); keys never in code/logs |
| `agents/fetchers/etherscan_fetcher.md` | Sibling fetcher — key-handling pattern this one extends (query-param key → URL-path key) |
| `agents/fetchers/sec_edgar_fetcher.md` | 2-UA `_select_user_agent` pattern echoed here |
| `references/phase_contract.md` P1 | Fetcher dispatch — where this agent is invoked |
| `references/subject_taxonomy.md` | 5-class taxonomy → `subject_type` routing |
| `tools/fetchers/alchemy_fetch.py` | Implementation backing this spec |
| `tools/audit/user_agent_pii.py` | Post-run guard for the UA contract |
