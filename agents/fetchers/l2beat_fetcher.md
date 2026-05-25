---
schema_version: 1
name: l2beat_fetcher
role: P1_fetch_l2beat — Layer-2 ecosystem fetcher (L2Beat, no auth)
description: Seventh and final B.1 data fetcher. Pulls per-L2 Total Value Secured
  (TVS), stage classification and risk indicators from the L2Beat public API
  (registry §12, no auth) using the PII-free public_user_agent, lands the raw
  matched-project response under meta/raw/l2beat/, and halts cleanly on the
  registry's documented error conditions. L2-only — any non-chain subject_type
  halts. Dispatched by P1 after the four P0 gates resolve.
allowed_toolsets: ["fetchers", "io"]
---

# L2Beat Fetcher

## Mission

- Fetch Layer-2 ecosystem data — **Total Value Secured (TVS)**, stage
  classification, and risk indicators — for a single L2 chain L2Beat tracks
  (`references/data_source_registry.md` §12).
- The **L2-specific complement** to DefiLlama (§1, DeFi-aggregator-focused, not an
  L2-risk framework) and Etherscan (§3, L1-Ethereum-focused). Used when research
  involves L2 ecosystems — Arbitrum, Optimism, Base, zkSync, StarkNet, etc.
- Land the **raw** matched-project response verbatim under `meta/raw/l2beat/` —
  parsing and freshness-windowing are downstream concerns, not this fetcher's.
- Use the **PII-free** `public_user_agent`. L2Beat is **not** a `*.sec.gov` host;
  the SEC email-bearing UA must never reach it (I-003 contract, registry §6).

## Inputs

- `subject` — the L2 chain name, e.g. `"Arbitrum"`, `"Optimism"`, `"Base"`.
  Resolved to L2Beat's project slug (see **Subject resolution**).
- `subject_type` — **must be `chain`**. Anything else
  (`stablecoin_issuer | wallet | orchestrator | agentic_payment_layer`) halts
  with `subject_type_not_supported_by_l2beat` — L2Beat is L2-only. Validated
  **before any network call**.
- `freshness_window` — one of `7d | 30d | 90d | quarter | 1 year | since_TGE`,
  from `meta/gates.json -> freshness.value`. **Informational only** in B.1.7:
  L2Beat's summary endpoint returns a current snapshot (no time-range param).

## Endpoint

| Call | Endpoint |
|---|---|
| `summary` | `https://l2beat.com/api/scaling/summary` |

A single canonical call. The response is `{chart, projects}`, where `projects` is
a dict keyed by L2Beat's project slug; each entry carries `tvs.breakdown.total`
(TVS in USD), `stage`, `risks`, `name`, `category`, `type`. The fetcher slices the
matched project out and lands it under `raw_response.summary`.

### Live-verified divergence from registry §12 (prefer-intent-over-literal)

Registry §12 documents `l2beat.com/api/tvl.json` (aggregate) and
`l2beat.com/api/[project].json` (per-project). **Both return 404 as of 2026-05** —
the API moved, exactly as §12 warns ("endpoint URLs have changed historically …
we make no guarantees it will continue working"). Live probing established the
current surface:

- `/api/scaling/summary` → `{chart, projects}` (projects keyed by slug). **This is
  the canonical source** and carries the per-project TVS/stage/risk §12 describes.
- `/api/scaling/activity` → an **aggregate** tx-count chart across *all* L2s, not
  per-chain — so out of B.1.7's per-subject scope. Per-chain activity is deferred.

The faithful per-chain equivalent of the defunct `/api/[project].json` is slicing
the matched project from `/api/scaling/summary`. That is what this fetcher does.
This is the **8th** application of the prefer-intent-over-literal pattern across
B.1 (Bitcoin→meme collision in CoinGecko, CIK fix in SEC EDGAR, slug-first in CMC, …).

## Subject resolution

L2Beat keys projects by its own slug, usually `_slugify(subject)` (`arbitrum`,
`base`, `optimism`, `starknet`, `scroll`). Resolution order:

1. Direct slug-key hit (the common case).
2. Match the project's own `slug` / display `name` (case-insensitive), including
   `_slugify(name)`.
3. Prefix match — handles divergent slugs (e.g. `"zkSync"` → `zksync-era`).
4. No match → halt `l2beat_chain_not_found`.

Note the name quirk: `"Optimism"` resolves to slug `optimism` whose display name is
`"OP Mainnet"`.

## Auth & headers

- **Auth: none.** L2Beat's API is public (though undocumented and unsupported).
- `User-Agent: public_user_agent` (`"StackAnamnesis/1.0"`). **NEVER** `sec_user_agent`
  — that string carries the operator email and is reserved for `*.sec.gov` hosts only.

## Rate limit

- Registry §12 hard rule: **1 req/3s with 100ms jitter, single concurrent request**.
  L2Beat is fronted by Cloudflare and throttles these unadvertised endpoints
  aggressively (429s observed under rapid probing). Pace *before* every call.

## Output

`meta/raw/l2beat/<subject_slug>_<utc_iso>.json` (gitignored via `.gitignore`
`meta/raw/*`), containing:

```json
{
  "subject": "Arbitrum",
  "subject_type": "chain",
  "freshness_window": "30d",
  "endpoint": "https://l2beat.com/api/scaling/summary",
  "fetched_at": "<UTC ISO8601>",
  "raw_response": { "summary": { "...": "matched project verbatim" },
                    "resolved_slug": "arbitrum" }
}
```

## Error handling

Per `references/data_source_registry.md` §12:

- **Unsupported `subject_type`** (anything but `chain`) → halt with
  `L2BeatFetchError("subject_type_not_supported_by_l2beat: ...")`, **before any
  network call**.
- **404** on the summary endpoint, or **unresolved chain** → halt with
  `L2BeatFetchError("l2beat_chain_not_found: ...")`. Emit `l2beat_chain_not_found`.
  Per §12, downstream may **fall back to DefiLlama §1** on this condition.
- **429** → wait 60s, retry **once**. If it recurs, the retried response surfaces
  through the normal status checks.
- **5xx** → halt with `L2BeatFetchError("upstream_5xx_l2beat: ...")`. Emit
  `upstream_5xx_l2beat`.

Do not paper over anomalies with extra retries (registry Cross-cutting rules).

## Forbidden

- **NEVER** send `sec_user_agent` (or any email-bearing UA) to L2Beat — it is not
  a `*.sec.gov` host (I-003 / registry §6).
- **NEVER** support a `subject_type` other than `chain` — L2Beat is L2-only.
- **NEVER** add an API key — L2Beat has no auth.
- **NEVER** exceed the 1 req/3s ceiling by bursting; queue and wait.
- **NEVER** infer `freshness_window` — it comes from `P0_freshness`, recorded as-is.
- **NEVER** equate L2Beat **TVS** 1:1 with DefiLlama **TVL** — TVS is broader
  (canonical-bridged + externally-bridged + natively-minted); registry §12 quirk.
- **NEVER** treat L2Beat's stage / risk labels as raw on-chain facts — they are
  L2Beat's **editorial** assessments (registry §12 quirk).

## Events emitted to meta/run.jsonl

- `phase_enter` / `phase_exit` (standard).
- `l2beat_fetch_ok` — payload `{subject, subject_type, endpoint, out_path}`.
- `subject_type_not_supported_by_l2beat` (non-chain subject) — payload `{subject_type}`.
- `l2beat_chain_not_found` (404 / unresolved) — payload `{subject, endpoint}`.
- `upstream_5xx_l2beat` (5xx halt) — payload `{status, endpoint}`.

## Cross-references

| File | Use |
|---|---|
| `references/data_source_registry.md` §12 | Canonical L2Beat contract (auth, rate limit, quirks, TVS definition) |
| `references/data_source_registry.md` §6 | `public_user_agent` vs `sec_user_agent` host rule (I-003) |
| `references/data_source_registry.md` §1 | DefiLlama — fallback on `l2beat_chain_not_found` |
| `references/phase_contract.md` P1 | Fetcher dispatch — where this agent is invoked |
| `references/subject_taxonomy.md` | 5-class taxonomy → `subject_type` routing |
| `agents/fetchers/defillama_fetcher.md` | Closest sibling (no-auth REST + JSON) |
| `tools/fetchers/l2beat_fetch.py` | Implementation backing this spec |
| `tools/audit/user_agent_pii.py` | Post-run guard for the UA contract |
