---
schema_version: 1
description: Canonical registry of external data sources for Stack Anamnesis. Each entry covers endpoint, auth model, rate limit, coverage, documented quirks, and which subject_class values it is most relevant for. Companion: references/subject_taxonomy.md (the five classes that key into this registry). Read before authoring or modifying any data-collection agent.
---

# Data Source Registry

This file is the **canonical contract** for which external data sources Stack Anamnesis is allowed to call, what each one provides, and what its limits are. **Six core sources** (always considered) are registered, followed by **seven conditional non-core sources** (§7–§13) enabled per `subject_class`. The six core sources:

1. **DefiLlama** — protocol/chain TVL, stablecoin caps, yields. Free.
2. **Dune** — custom SQL across indexed chains. Mixed free/paid.
3. **Etherscan family** — raw EVM (and Solscan for Solana) tx data, contract source, contract reads. Free tier with API key.
4. **CoinGecko** — price, market cap, volume, coin metadata. Free tier rate-limited.
5. **RPC tier** — Alchemy / Infura / QuickNode JSON-RPC for direct contract reads. Per-provider tier.
6. **SEC EDGAR** — public-company filings (10-K, 10-Q, 8-K), XBRL company facts, insider transactions. Free; **conditional** consumer of the `P0_sec_email` gate (only fires when `subject_entity.listed` or `parent_or_issuer_entity.listed` per `references/subject_relationships.yaml`).

> **TD-009 closure.** SEC EDGAR re-entered the registry in Phase B.0 deliverable #1.5. Between Phase A and Phase B, the registry was a five-source set and the SEC-specific secret-handling pattern was held in `references/TODO.md` TD-009 as a deferred design note. The re-add restores the sixth source and the I-003-pattern secret-handling rule returns to `MEMORY.md`'s Privacy Invariants section in B.0 deliverable #16. TD-009's status in `references/TODO.md` should be flipped to closed in the same pass.

Any data-collection agent that wants to call something *not* in this registry must (a) record `event: "out_of_registry"` in `meta/run.jsonl` and (b) halt for human confirmation before the call. Adding a new source is a deliberate change to this file. Registry-drift incidents are exactly the shape that earns an `INCIDENTS.md` entry.

The registry is also keyed off `references/subject_taxonomy.md`. The **"relevant for"** column in each entry below maps to the five subject classes and is how the orchestrator selects which subset of this registry to consult for a given run.

---

## 1. DefiLlama

**Domain.** `api.llama.fi` (general), `stablecoins.llama.fi`, `yields.llama.fi`, `coins.llama.fi`, `bridges.llama.fi`. Documentation: `defillama.com/docs/api`.

**Auth.** None. Open API.

**Rate limit.** Undocumented; empirically ~300 requests / 5 minutes per IP across the `api.llama.fi` host. Per-endpoint quotas tighter on `coins.llama.fi` (historical price endpoints). **Hard rule for this harness**: cap at **1 req/sec** with a 100ms jitter, regardless of empirical headroom. The harness has no business burning DefiLlama's free hosting; respectful pacing keeps the source usable.

**What you get.**
- `/protocols`, `/protocol/{slug}` — TVL by protocol, with chain breakdown and historical daily TVL.
- `/stablecoins`, `/stablecoin/{id}` — circulating supply per stablecoin, per chain.
- `/chains` — TVL by chain, with breakdown by protocol category.
- `/yields/pools` — APY by pool with TVL and chain.
- `/bridges` — bridge volume and TVL.
- `/coins/prices/current/{coins}`, `/coins/prices/historical/{ts}/{coins}` — spot and historical prices by token (CoinGecko-style coin IDs).

**Documented quirks.**
- Chain naming inconsistent across endpoints — use the lowercase canonical form returned by `/chains` (e.g., `ethereum`, `base`, `arbitrum`, not `Ethereum` or `ETH`).
- Category overlap: a protocol can appear in multiple categories (DEX + lending). Sum across categories will double-count TVL.
- CORS-enabled for browser calls.
- Historical TVL series have occasional gaps after protocol incidents; treat null days as nulls, not zeros.

**Relevant for.** `stablecoin_issuer` (caps, chain split), `chain` (TVL, fees, category mix), `orchestrator` (bridge volume).

---

## 2. Dune

**Domain.** `dune.com` (web UI for queries and dashboards), `api.dune.com` (API). Documentation: `docs.dune.com`.

**Auth.** API key required for `api.dune.com`. Free tier requires sign-up; paid tiers via subscription.

**Rate limit / billing model.**
- **Free tier** ("Community Plan"): 10K rows/month included; 4 concurrent executions; "medium" engine only. Cached results are free.
- **Paid tiers** (Plus / Premium / Enterprise): higher row caps, more concurrency, "large" engine, longer cache TTLs.
- Costs accrue by **credits per query** (function of rows scanned + engine size), not requests. A cached read is 0 credits.

**Hard rule for this harness.** Free tier is the default. The orchestrator must prefer **cached** community queries (read by query ID) over fresh executions. Fresh executions are gated: the calling agent records the credit cost estimate before submission and the orchestrator caps total fresh-exec spend at **2000 credits / run** unless the user explicitly overrides per-run.

**What you get.**
- Custom SQL over indexed chain data: Ethereum + all major L2s (Arbitrum, Base, Optimism, Polygon, etc.) + Solana + a long tail of others.
- Tens of thousands of community-shared queries and dashboards.
- Real-time-ish data (latency varies by chain — typically minutes for Ethereum, longer for L2s after batches post).
- Webhook support for query-completion notifications (paid tiers).

**Documented quirks.**
- Query quality varies wildly across the community library. Pin to known-good queries by ID; treat all others as inputs to a sanity check, not as ground truth.
- The underlying chain decoders evolve. A query that worked yesterday can return nulls today if a decoded table got renamed. Validators must check for unexpected null rates.
- Solana data is later-arriving and noisier than EVM. Treat Solana-specific freshness with a longer tolerance.
- Public sharing of a query exposes the SQL but not the credit cost.

**Relevant for.** All five classes — Dune is the most cross-cutting source. Especially `chain` (fees, MEV, activity), `orchestrator` (bridge volume by route), `wallet` (active addresses), `agentic_payment_layer` (settlement footprint where on-chain).

---

## 3. Etherscan family (and Solscan)

**Domain.** Per chain:
- `etherscan.io` — Ethereum L1
- `basescan.org` — Base
- `arbiscan.io` — Arbitrum One + Nova
- `optimistic.etherscan.io` — Optimism
- `polygonscan.com` — Polygon PoS
- `bscscan.com` — BNB Chain
- `snowtrace.io` — Avalanche C-Chain
- `solscan.io` — Solana (not part of Etherscan, but the closest substitute and treated as a peer source here)
- (other Etherscan-family explorers exist for Linea, Scroll, etc. — same API shape, separate keys)

Documentation: `docs.etherscan.io` (with chain-specific addenda).

**Auth.** API key required, **one per chain** in the Etherscan family. Etherscan recently introduced a unified "Etherscan V2" key that covers most family chains with a single key — prefer that when available. Solscan has its own key.

**Rate limit.**
- Free tier: **5 req/sec**, 100,000 calls/day. Standard across the family.
- Paid tiers (Standard / Advanced / Pro): up to 30 req/sec, higher daily caps, priority endpoints. Per-chain billing.

**Hard rule for this harness.** Use 4 req/sec as the working ceiling (one below the documented limit, since burst behaviour is unforgiving). On 429, exponential backoff starting at 2s, max 5 retries per request. Key is read from `~/.config/anamnesis/etherscan.key` and never logged.

**What you get.**
- Raw transaction listings by address (normal, internal, token, NFT).
- Contract source code + ABI (when verified).
- Contract read functions via the proxy interface.
- Account balances at any block (free for recent blocks; archive-block reads gated to paid tiers on some chains).
- Gas oracle, block stats.
- Token transfer histories (ERC-20, ERC-721, ERC-1155).
- Verified-contract registry (useful for identifying issuer treasury contracts, bridge contracts, MEV bots).

**Documented quirks.**
- Each chain has its own daily quota — burning Ethereum's quota does not deplete Base's.
- Rate-limit windows can shift after suspected abuse (the "5 req/sec" becomes effectively lower for an hour or two).
- Address checksums are case-sensitive in some endpoints and case-insensitive in others — always lowercase before hashing/comparing.
- Solscan's API surface differs significantly from Etherscan's; treat as a separate adapter, not a drop-in.
- "Internal transactions" endpoints lag behind external by up to a few blocks.

**Relevant for.** `chain` (block stats, fee data), `stablecoin_issuer` (treasury-wallet reads, total-supply reads), `wallet` (address activity, token holdings — when address is known), `agentic_payment_layer` (settlement-contract reads).

---

## 4. CoinGecko

**Domain.** `api.coingecko.com` (free), `pro-api.coingecko.com` (paid / "Pro" tier). Documentation: `docs.coingecko.com`.

**Auth.**
- Free / "Demo" tier: optional `x-cg-demo-api-key` header. Without a key, slightly stricter limits; with a demo key, slightly looser.
- Pro tier: required `x-cg-pro-api-key` header. Different host (`pro-api.coingecko.com`).

**Rate limit.**
- Free / demo: **10–30 calls/minute** (undocumented exactly; observed). Burst-sensitive — slamming 10 in one second can trigger a temporary block even if the per-minute average is under cap.
- Pro tier: 500 calls/min and up depending on plan.

**Hard rule for this harness.** Free tier default. Cap at **1 req/2.5 sec** with 200ms jitter. Use the demo key when present. On 429, back off 60 seconds before any further CoinGecko request from any agent in the run.

**What you get.**
- Spot price, market cap, 24h/7d/30d/1y volume by coin.
- Coin metadata: description, GitHub repo, official links, exchange listings.
- Historical price/volume (limited window on free tier).
- DEX trade data (`/onchain` endpoints, GeckoTerminal-style; some are free, some Pro-only).
- Exchange data (volumes by pair).
- Stablecoin-specific endpoints: peg deviation, market dominance.

**Documented quirks.**
- Coin IDs are slug-based, not symbol-based. Symbols collide (e.g., multiple coins use `LINK`). Always resolve to the slug ID (e.g., `chainlink`) via `/coins/list` before any other query.
- Free tier rate-limit window is undocumented and varies in practice — assume it can shift down without warning, and treat 429s as a signal to slow down for the rest of the run.
- Some pages have a long cache TTL (e.g., metadata changes can take hours to propagate).
- The free tier's historical-range endpoints cap lookback at 365 days. Earlier data requires Pro.

**Relevant for.** `stablecoin_issuer` (peg deviation, dominance), `chain` (native token market data), `agentic_payment_layer` (token if any, market response to announcements), `wallet` (wallet's native token if any).

---

## 5. RPC tier — Alchemy / Infura / QuickNode

**Domain.** Per-provider URLs, **per-chain endpoints**:
- Alchemy: `<chain>-mainnet.g.alchemy.com/v2/<API_KEY>` (e.g., `eth-mainnet`, `base-mainnet`, `arb-mainnet`, `opt-mainnet`, `polygon-mainnet`, `solana-mainnet`).
- Infura: `<chain>-mainnet.infura.io/v3/<API_KEY>` (Ethereum + select chains).
- QuickNode: `<random-subdomain>.<chain>.quiknode.pro/<API_KEY>/` (per-endpoint provisioned).

Documentation: `docs.alchemy.com`, `docs.infura.io`, `www.quicknode.com/docs`.

**Auth.** API key per chain per provider, read from `~/.config/anamnesis/<provider>.key`. Never logged.

**Rate limit / billing model.**
- **Alchemy** free: 300 CU/sec (compute units, not requests; method-dependent), ~30M CU/month. Paid tiers higher CU/sec + archive methods.
- **Infura** free: 100K req/day, 25 req/sec across all chains combined. Paid tiers higher.
- **QuickNode** free trial: 25 req/sec, then per-endpoint paid plans.

**Hard rule for this harness.** Prefer Alchemy as default (most expressive free tier for archive-adjacent methods on Ethereum + L2s). Fall back to Infura on Alchemy 429. QuickNode only when a specific endpoint is provisioned for it. Per-run budget: **5M CU on Alchemy free** as a soft ceiling — if approached, escalate to user before continuing.

**What you get** (JSON-RPC standard methods, plus provider extensions):
- `eth_call` — direct contract reads (`balanceOf` on a treasury wallet, `totalSupply` on a token, custom view functions).
- `eth_getLogs` — event-log queries (token transfers, contract events).
- `eth_getBlockByNumber`, `eth_getTransactionByHash` — block and tx data.
- `eth_getBalance` — native-token balance at any block.
- Provider extensions: Alchemy's `alchemy_getAssetTransfers` (consolidated transfer history), `alchemy_getTokenBalances` (multi-token balance read), trace methods, etc.

**Documented quirks.**
- `eth_getLogs` has **block-range limits** per provider (typically 2,000 blocks on free tiers, more on paid). Splitting a long historical query across calls is mandatory.
- **Archive methods** (state at historical blocks older than ~128 blocks) require paid tier on most providers — Alchemy is the most permissive on free.
- Alchemy charges in **compute units**, not requests. An `eth_call` may be 26 CU; an `eth_getLogs` over a wide range can be 250+ CU. Always estimate before bulk runs.
- Per-chain endpoints are separate — burning Ethereum CU does not affect Base CU on Alchemy.
- Solana RPC methods differ entirely from EVM; treat as a separate adapter.

**Relevant for.** `stablecoin_issuer` (live reserve reads via `eth_call balanceOf` on issuer treasuries, `totalSupply` on the token contract — this is the only way to ground-truth the attestation page), `chain` (block timing, fee distribution), `wallet` (real-time balance on known addresses), `agentic_payment_layer` (settlement-contract reads if the protocol has deployed contracts).

---

## 6. SEC EDGAR

**Domain.** `data.sec.gov` (structured submissions + XBRL company facts), `www.sec.gov/cgi-bin/browse-edgar` (legacy filing index), `www.sec.gov/Archives/edgar/data/<CIK>/...` (raw filing documents). Documentation: `www.sec.gov/edgar/sec-api-documentation`.

**Auth.** No API key. **However**, every request **must** carry a `User-Agent` header containing a contactable email address — this is a documented SEC requirement, not a soft convention. Requests without a compliant User-Agent are throttled aggressively or denied outright. The **canonical format** (inherited from I-003 in `references/equity_incidents_archive.md`) is:

```
User-Agent: <ProjectSlug>/<Version> (<contact-email>)
```

e.g. `StackAnamnesis/1.0 (operator@example.com)`. The equity-era instance used `EquityResearchSkill/1.0 (<email>)`; the Stack Anamnesis fork uses the `StackAnamnesis/<version>` slug once `tools/audit/user_agent_pii.py`'s hardcoded `PUBLIC_USER_AGENT = "EquityResearchSkill/1.0"` is repointed (Phase B housekeeping — surfaced below, not done in B.0).

**Two User-Agent strings live in `meta/run.json`** (per the I-003 contract — never collapse them into one):

- `sec_user_agent` — contains the email; used **only** for hosts matching `sec.gov` or `*.sec.gov` (the live set includes `data.sec.gov`, `www.sec.gov`, `efts.sec.gov`).
- `public_user_agent` — **PII-free** (no email, no other PII); used for **all other** outbound HTTP — DefiLlama, Dune, Etherscan, CoinGecko, RPC, news, logos, peer pages, anything not on a `*.sec.gov` host.

Fetchers pick the right UA **by host**, not by whichever UA happens to be set in run state. A fetcher that defaults to "the only UA it finds" is the exact I-003 bug shape. `tools/audit/user_agent_pii.py` is the post-run guard: it fails when the email substring appears alongside a non-SEC URL, or when `public_user_agent` is missing or contains an email.

**Declined-email semantics.** If the user answers the `P0_sec_email` gate with the canonical token `declined` (also accepted: `skipped`, `none`, `n/a`, `no_email` — per the normaliser in `tools/audit/user_agent_pii.py`), `sec_user_agent` is `null`, SEC fetches are gated off for the run, and `public_user_agent` is still set and used for everything else.

This is the **only data source in the registry** that carries the operator's email in the request header; all five other sources use `public_user_agent`. The SEC-specific User-Agent is constructed at runtime from the `P0_sec_email` answer and **never** persisted to disk, logs, or the DB. See Privacy invariants in `MEMORY.md` and the I-003 cross-cutting guard (restated in §Cross-cutting rules below).

**Conditional gate consumer.** SEC EDGAR is the **only** source in the registry gated by `P0_sec_email`. The gate fires only when `subject_entity.listed == true OR parent_or_issuer_entity.listed == true` (per `references/subject_relationships.yaml`). If neither evaluates true, the gate auto-skips with `applies_when_false` and SEC EDGAR is **not called** for the run. When the user answers the gate with `declined`, SEC EDGAR is also not called, and the report writer notes the affected sections in the template Part 1.5 Data Availability annotation.

**Rate limit.** Documented: **10 requests/second per IP**. See `www.sec.gov/os/accessing-edgar-data`. **Hard rule for this harness**: 5 req/sec working ceiling with 100ms jitter — document fetches (10-K HTML can be several MB) are heavier than the rate-limit counter assumes, and slamming the documented cap has produced temporary blocks in practice. On 429 or 403, exponential backoff starting at 5s, max 4 retries, then surface to user.

**What you get.**
- `/submissions/CIK{padded10}.json` — recent filings + company metadata for a CIK (Central Index Key). Returns paginated `recent` plus a `files` array of older quarters; full history requires concatenating both.
- `/api/xbrl/companyfacts/CIK{padded10}.json` — structured XBRL facts (revenue, assets, share counts, etc.) across all filings for the entity.
- `/api/xbrl/companyconcept/CIK{padded10}/us-gaap/{concept}.json` — single-concept timeseries (e.g., `Revenues`, `OperatingIncomeLoss`).
- `/cgi-bin/browse-edgar?action=getcompany&CIK=...&type=10-K&dateb=&owner=include` — legacy filing index, useful when the `submissions` JSON lacks a specific older filing.
- Raw filings: 10-K (annual), 10-Q (quarterly), 8-K (material events), DEF 14A (proxy), 4 (insider transactions), S-1/S-3 (registration), 13F (institutional holdings). HTML + plaintext versions.

**Documented quirks.**
- **CIK must be zero-padded to 10 digits** in URL paths (e.g., Circle's CIK is `1876042` → URL uses `0001876042`). Unpadded CIKs return 404. Always normalise before constructing URLs.
- **XBRL companyfacts is delayed by 1–2 days** after a filing's `filedAt` date — the structured-data extraction is a separate pipeline. Treat same-day XBRL-misses as expected, not as a fetch failure.
- **The `submissions` endpoint paginates implicitly**: the `recent` block holds the most-recent ~1000 filings; older filings are in the `files` array as references to per-year JSON pages. Fetching only `recent` will silently miss anything older. Always check `files` when the lookback exceeds ~2 years for an active filer.
- **Filing URL subdirectories are unstable** — the per-filing folder under `/Archives/edgar/data/<CIK>/<accession-no-stripped>/` contains documents whose filenames are filer-controlled. Never guess document URLs; resolve them via the filing's `index.json` (e.g., `/Archives/edgar/data/<CIK>/<accession>/index.json`).
- **No CORS** on browser calls. Server-side fetch only; the harness already operates server-side, but this matters for any future thin-client surface.
- **Aggressive CDN caching**: the same URL within a short window can return cached bytes even after a re-filing. Respect 304s; do not assume freshness for filings within the last hour without re-querying the `submissions` index.
- **Form 4 (insider transactions) is high-volume noise** for large public companies — filter by reporting-person role and recent-date window before downstream processing.

**Relevant for.** All five `subject_class` values when the `P0_sec_email` `applies_when` triggers. Conditional in shape, not in coverage:
- `stablecoin_issuer` — primary use case. Circle (CRCL/NYSE) 10-Q for quarterly reserve composition, 10-K risk factors for redemption mechanics, 8-K for material attestation changes. Tether is private and is **not** in scope for SEC EDGAR.
- `wallet` — Coinbase (COIN/NASDAQ) segment revenue, custody risk disclosures in the 10-K, 8-K for outage post-mortems and SEC settlements. Robinhood (HOOD/NASDAQ) for the wallet-app retail side.
- `chain` — usually accessed via the parent company's filings when relevant: Marathon Digital (MARA/NASDAQ) for Bitcoin mining operating data, Galaxy Digital (GLXY/NASDAQ–TSX) for trading-desk volume disclosures. The chain itself is rarely listed; the parent is.
- `orchestrator` — most are private today (Stripe, Bridge, Conduit). The gate auto-skips for private-parent orchestrators. Future listings would activate the path without code change.
- `agentic_payment_layer` — most are private or pre-product. Same auto-skip behaviour as `orchestrator` until a parent goes public.

---

# Conditional non-core sources (§7–§13)

The following seven sources are **conditional**: enabled per-run only when the subject's `subject_class` (per `references/subject_taxonomy.md`) and the dispatch logic in `references/research_dimensions.md` §3 call for them. Unlike the six core sources above, none is always-on. All use `public_user_agent` — **none** carries the operator email (only SEC EDGAR §6 does). Each entry names its forward-referenced B.1 fetcher (not yet written). The trigger conditions below are **dispatch hints, not hard rules** — the dispatch logic in `research_dimensions.md` §3 is the authority.

---

## 7. Artemis

**Domain.** `app.artemisanalytics.com` / `api.artemisanalytics.com` (API). Documentation: `docs.artemis.xyz`. Homepage: `artemis.xyz`.

**Auth.** API key required. Free **"Lite"** tier to start; **Professional** and **Enterprise** paid tiers (Enterprise adds Snowflake data share + custom API).

**Rate limit.** Not published per-tier; the free Lite tier is metric- and volume-limited rather than documented as a req/sec cap. **Hard rule for this harness**: treat as 1 req/sec with 200ms jitter until a tier-specific limit is confirmed. *(Exact free-tier limits unconfirmed — see review flag.)*

**What you get.**
- Cross-chain comparison of revenue, fees, TVL, active addresses, and volumes across 12,000+ tokens and 50+ chains.
- Stablecoin analytics — supply by issuer and per-chain split, issuer transfer volumes.
- Cross-chain flow data and developer-activity series.
- Daily / weekly / monthly granularity with history.

**Trigger conditions (when to enable).**
- `stablecoin_issuer` — cross-chain supply split and issuer volume comparison.
- Multi-chain protocols where a cross-chain user/volume comparison is the question.

**Do NOT use for.**
- Raw single-chain transaction data (use Etherscan family §3 / RPC §5).
- Ground-truth reserve reads (use RPC `eth_call` §5).
- Primary price feed (use CoinGecko §4).

**Documented quirks.**
- Free Lite metric coverage is materially narrower than Professional — a missing metric on Lite is a tier limit, not a data gap.
- Cross-chain figures are **Artemis-normalised**; their TVL/revenue definitions differ from DefiLlama's — do not mix the two series as if identical.
- Per-tier rate limits are undocumented; pace conservatively.

**User-Agent.** `public_user_agent` (NOT `sec_user_agent`) — PII-free, identical across all runs.

**Relevant for.** `stablecoin_issuer` (cross-chain supply, issuer volumes), `chain` (cross-chain activity comparison), `orchestrator` (cross-chain volume by route).

**Forward reference.** B.1 fetcher to be written in `agents/fetchers/artemis_fetcher.md`.

---

## 8. Token Terminal

**Domain.** `api.tokenterminal.com` (API). Documentation: `docs.tokenterminal.com`. Homepage: `tokenterminal.com`.

**Auth.** API key required for programmatic access (paid **API plan**). A free account covers historical-data browsing in the web UI; building on the API requires the paid plan.

**Rate limit.** **1000 requests/minute** (documented). Read-only REST, JSON responses.

**What you get.**
- Standardised financial metrics across protocols: revenue, fees, expenses, earnings, **P/S** and **P/E** ratios.
- Financial statements per project, normalised so protocols are comparable.
- Market-sector groupings and 25+ endpoints (metrics / projects / financials).

**Trigger conditions (when to enable).**
- Protocols or chains with on-chain revenue (DeFi protocols, L1/L2 with fee revenue).
- Valuation-multiple analysis (P/S, P/E) is part of the thesis.

**Do NOT use for.**
- Wallet-level or raw-transaction data.
- Price feed (use CoinGecko §4) — TT is metrics, not a ticker.

**Documented quirks.**
- API access is **paid** — the free account only unlocks UI historical browsing, not programmatic pulls. Budget accordingly.
- Metrics are **TT-standardised**; their revenue/fee definitions can diverge from an issuer's own reporting — note the definition when citing.
- 1000 req/min is the documented ceiling; this harness will not approach it for single-subject runs.

**User-Agent.** `public_user_agent` (NOT `sec_user_agent`) — PII-free, identical across all runs.

**Relevant for.** `chain` (fee/revenue, valuation multiples), `stablecoin_issuer` (protocol financials where the issuer runs an on-chain protocol), `agentic_payment_layer` (protocol economics if on-chain).

**Forward reference.** B.1 fetcher to be written in `agents/fetchers/token_terminal_fetcher.md`.

---

## 9. Allium / Nansen

This section registers **two distinct platforms** bundled together because they serve the same role — labelled wallet behaviour and whale/smart-money analytics. Pick per need: **Nansen** for human-readable address labels and Smart Money tracking; **Allium** for raw + enriched warehouse-scale on-chain data.

**Domain.**
- **Nansen** — `nansen.ai`; API documentation `docs.nansen.ai`.
- **Allium** — `allium.so`; API documentation `docs.allium.so`.

**Auth.** Both require an API key.
- **Nansen** — **credit-based**: free credits to test core endpoints (no expiry pressure); Pro credits paid (e.g. $100 / 100K credits, $500 / 500K, $1000 / 1M; ~100K balance/pnl/txn checks **or** ~20K Smart Money calls per $100).
- **Allium** — **enterprise, quote-based**: no self-serve free tier; pricing starts in the high four figures/month.

**Rate limit.** Quota/credit-based rather than a strict req/sec ceiling. Nansen meters by credits (Smart Money calls are the most expensive). Allium is governed by an enterprise SLA (real-time API ~80ms response, 3–4s data freshness).

**What you get.**
- **Nansen** — Smart Money tracking, wallet profiling, token holder ("god mode") breakdowns, and proprietary labels on hundreds of millions of addresses across 18+ chains.
- **Allium** — indexed blockchain data across 80–130+ chains, 1000+ standardised schemas; Explorer (SQL queries) and Developer (fixed + enriched REST endpoints), real-time + warehouse.

**Trigger conditions (when to enable).**
- `wallet` — whale tracking, smart-money flow, holder concentration (primary use).
- `stablecoin_issuer` — holder distribution and treasury-flow labelling.
- Large protocols needing labelled-address analysis Dune/Etherscan can't cheaply label.

**Do NOT use for.**
- Budget or free runs — both are paid (Allium enterprise-only); prefer Dune §2 / Etherscan §3 for low-cost on-chain queries.
- Primary price or TVL (use CoinGecko §4 / DefiLlama §1).

**Documented quirks.**
- **Two platforms, one role** — they are not interchangeable: Nansen = labels/smart-money, Allium = raw warehouse breadth. Document which one a given figure came from.
- Nansen's credit model **burns fast** on Smart Money calls (~20K per $100) — estimate before bulk pulls.
- Allium has **no self-serve free tier** (sales quote required) — gate any Allium dispatch behind explicit budget approval.
- Labels are **proprietary and opaque** — treat them as strong hints, not ground truth; corroborate material claims on-chain.

**User-Agent.** `public_user_agent` (NOT `sec_user_agent`) — PII-free, identical across all runs.

**Relevant for.** `wallet` (primary — labels, smart-money flow), `stablecoin_issuer` (holder/treasury flows), `chain` (labelled activity).

**Forward reference.** B.1 fetchers to be written as two adapters under one registry section: `agents/fetchers/nansen_fetcher.md` and `agents/fetchers/allium_fetcher.md`.

---

## 10. Electric Capital

**Domain.** `developerreport.com` (the Developer Report), `electriccapital.com` (the firm). Open data: `github.com/electric-capital/developer-reports` and the `crypto-ecosystems` repo (published as a public good).

**Auth.** None. The report and underlying Open Dev Data are **public and downloadable** — there is **no real-time API**. GitHub raw access is subject to GitHub's own limits.

**Rate limit.** N/A — this is a periodic report plus an open dataset, not a rate-limited service. Pace GitHub fetches politely.

**What you get.**
- Annual **Developer Report** (published yearly since 2018; six editions through 2024) analysing open-source crypto developer activity.
- Full-time / part-time / total developer counts by ecosystem, with per-ecosystem trends.
- GitHub commit-activity analysis — the 2024 edition covers 902M commits across 1.7M repositories.

**Trigger conditions (when to enable).**
- `chain` ecosystems — developer mindshare / ecosystem health as a thesis input.
- Large protocols and ecosystem-comparison questions.

**Do NOT use for.**
- Real-time or intraday signals — the cadence is **annual**; data is stale between releases.
- Financial metrics, price, or TVL.

**Documented quirks.**
- **Annual cadence** — data can be 6–12 months stale; under a 7d/30d freshness gate (Gate 3) there will be nothing new. Respect the window and cite the edition year.
- Ecosystem attribution depends on the `crypto-ecosystems` taxonomy — a repo must be mapped to an ecosystem to be counted; unmapped repos are invisible.
- Bot/fork dedup and copy-paste fingerprinting are methodology-dependent; treat counts as Electric-Capital-defined.
- The **2024 report** is the latest reference edition.

**User-Agent.** `public_user_agent` (NOT `sec_user_agent`) — PII-free, identical across all runs.

**Relevant for.** `chain` (developer health), `agentic_payment_layer` (ecosystem maturity), `orchestrator` (ecosystem context, secondary).

**Forward reference.** B.1 fetcher to be written in `agents/fetchers/electric_capital_fetcher.md`.

---

## 11. Messari

**Domain.** `messari.io`; API documentation `docs.messari.io` (legacy `data.messari.io/docs`).

**Auth.** API key. **Free** tier (account-based); **Pro** and **Enterprise** paid tiers. Enterprise generates per-product keys (market data / metrics / asset profiles) from the dashboard.

**Rate limit.** Free tier: **20 requests/minute**. Pro / Enterprise: higher; Enterprise has unlimited Market Data endpoints. Bulk data access is Pro/Enterprise only.

**What you get.**
- 15+ API families: market data, on-chain metrics, news, signals, fundraising, research, token unlocks, stablecoins, protocols, AI — across 40K+ assets and 210+ exchanges.
- **Asset profiles** (qualitative entity descriptions) and **institutional research reports** (Enterprise reports ≥ weekly; free protocol reports on a rolling basis).

**Trigger conditions (when to enable).**
- Any subject needing institutional / narrative research context, asset profiles, fundraising history, or token-unlock schedules.
- `stablecoin_issuer` — Messari's stablecoin-specific endpoints.

**Do NOT use for.**
- High-frequency quantitative pulls on the free tier (20 req/min is tight).
- Assuming free access to deep research — the best reports are Enterprise-gated; cite, don't presume.
- Raw-transaction data.

**Documented quirks.**
- Strong for **narrative / qualitative** context and asset profiles; weaker as a quantitative primary — cross-check metrics against DefiLlama §1 or the on-chain source.
- Free tier's **20 req/min** caps throughput — queue requests.
- The most valuable research reports are **Enterprise-gated**; bulk data is Pro/Enterprise only.

**User-Agent.** `public_user_agent` (NOT `sec_user_agent`) — PII-free, identical across all runs.

**Relevant for.** All five `subject_class` values for research/profile context; especially `stablecoin_issuer` (stablecoin endpoints), `chain`, `agentic_payment_layer`.

**Forward reference.** B.1 fetcher to be written in `agents/fetchers/messari_fetcher.md`.

---

## 12. L2Beat

**Domain.** `l2beat.com`. **Undocumented internal API**: `l2beat.com/api/tvl.json` (aggregate) and `l2beat.com/api/[project].json` (per-project). Source + research: `github.com/l2beat/l2beat`.

**Auth.** None (no key). The API is **public but undocumented and explicitly unsupported**.

**Rate limit.** None documented. **Hard rule for this harness**: cap at 1 req/sec with 200ms jitter — these are unadvertised endpoints on free hosting; respectful pacing keeps them usable.

**What you get.**
- L2-specific metrics: **Total Value Secured (TVS)** = canonical-bridged + externally-bridged + natively-minted assets.
- TVL, activity (transaction counts), and per-project breakdowns.
- Risk assessments / stage classification and data-availability summaries.

**Trigger conditions (when to enable).**
- `chain` where the chain is an **L2** / rollup / scaling solution.
- L2 ecosystem mapping or cross-L2 comparison.

**Do NOT use for.**
- L1 data (out of scope — use DefiLlama §1) or non-L2 subjects.
- Price / market cap.
- Anything requiring guaranteed uptime — the API is unsupported.

**Documented quirks.**
- The API is **undocumented and explicitly unsupported** — L2BEAT states "we make no guarantees that it will continue working." Endpoint URLs have changed historically; validate the endpoint shape per run and **fall back to DefiLlama §1 on 404**.
- **"TVS" is L2BEAT's broader metric** — do not equate it 1:1 with DefiLlama TVL.
- Risk and stage labels are L2BEAT's **editorial** assessments, not raw on-chain facts.

**User-Agent.** `public_user_agent` (NOT `sec_user_agent`) — PII-free, identical across all runs.

**Relevant for.** `chain` (L2s specifically — TVS, txs, fees, risk/stage), `orchestrator` (L2 settlement context, secondary).

**Forward reference.** B.1 fetcher to be written in `agents/fetchers/l2beat_fetcher.md`.

---

## 13. CoinMarketCap (CMC)

**Domain.** `pro-api.coinmarketcap.com` (API). Documentation: `coinmarketcap.com/api/documentation` and `pro.coinmarketcap.com`. Homepage: `coinmarketcap.com`.

**Auth.** API key **required on every tier, including the free Basic plan**. Tiers: **Basic** (free), **Hobbyist** ($29/mo), **Startup** ($79/mo), **Standard** ($299/mo), **Professional** ($699/mo), **Enterprise** (custom).

**Rate limit.** Per-tier req/min ceiling, reset every 60 seconds (429 on overage); usage is **metered by call credits** — roughly 1 credit / 100 data points returned, not 1 credit / request. Basic is the lowest tier on both axes.

**What you get.**
- Price, market cap, 24h volume, rankings, listings.
- Coin and exchange metadata.
- Same data category as **CoinGecko (§4)** — price / market cap.

**Trigger conditions (when to enable).**
- **Sibling / fallback to CoinGecko (§4)** — CoinGecko is the **primary** price / market-cap source; enable CMC as a cross-check, or when CoinGecko coverage or rate limits fail.
- Resolving a price / market-cap discrepancy via a second source.

**Do NOT use for.**
- Primary price source — CoinGecko §4 is primary; running both by default double-spends the rate/credit budget.
- On-chain / transaction data or TVL.

**Documented quirks.**
- **Credit-based metering** (1 credit / 100 data points) — wide listings calls burn credits fast; prefer targeted single-asset queries.
- **Coin IDs differ from CoinGecko's slugs** — maintain a CMC-id ↔ CoinGecko-slug map; never assume the same identifier across the two. Symbols collide — resolve to the CMC id.
- The Basic tier still **requires a key** (unlike DefiLlama's fully open API §1).

**User-Agent.** `public_user_agent` (NOT `sec_user_agent`) — PII-free, identical across all runs.

**Relevant for.** Same surface as CoinGecko §4 — `stablecoin_issuer` (peg/dominance cross-check), `chain` (native-token market data), `agentic_payment_layer`, `wallet` (native token) — used as **fallback / cross-check**, not primary.

**Forward reference.** B.1 fetcher to be written in `agents/fetchers/coinmarketcap_fetcher.md`.

---

## Cross-cutting rules

- **Keys live on disk, never in code, never in logs.** Each provider's key path is fixed (`~/.config/anamnesis/<provider>.key`). The harness reads the key into memory at the start of the relevant agent's run and passes it via header or query string only.
- **All requests carry `public_user_agent`** (the PII-free string from `meta/run.json`). Never the operator's email. (This is the inherited I-003-style invariant — see `references/equity_incidents_archive.md` for the equity-era leak that established the rule.) **One exception:** SEC EDGAR requests carry the operator-supplied contact email in the `User-Agent` header (SEC's documented requirement; see §6 SEC EDGAR above). The email-bearing User-Agent is constructed at runtime for SEC requests only and never propagates to other sources; `tools/audit/user_agent_pii.py` is the post-run I-003 guard that detects leaks of the SEC email into non-SEC URLs.
- **Cache eagerly, refetch deliberately.** Every fetch lands as a file under `output/{run}/research/_raw/<source>/<request_hash>.json` before any processing. Re-runs and resumes consult the cache first. Cache invalidation is by hash of `(endpoint, params, freshness window)`.
- **Respect rate limits as a hard contract, not a guideline.** The per-source caps above are the harness ceiling; the provider's documented cap is *not* the ceiling. If a fetcher would exceed the harness ceiling, queue and wait, do not burst.
- **On any source returning anomalous data** (sudden null spike, malformed JSON, schema drift), the calling agent records the anomaly in `meta/run.jsonl` and the downstream validator decides whether to halt or warn. Do not paper over with retries.

## Adding a new source

If a real run surfaces a need for a source not in this registry (e.g., Token Terminal for protocol revenue, Artemis for cross-chain analytics, Nansen for wallet labelling), do **not** add the call inline. Instead:

1. Record `event: "out_of_registry"` in `meta/run.jsonl` and halt.
2. Open a PR to this file with a new entry following the same six-field shape: Domain / Auth / Rate limit / What you get / Documented quirks / Relevant for. (Conditional non-core sources additionally carry Trigger conditions / Do NOT use for / User-Agent / Forward reference fields — see §7–§13.)
3. Update any agent that needs the new source to reference it by registry name.
4. Re-run.

The core registry is small on purpose — six core sources (five always-available + one conditional via `P0_sec_email`) cover the baseline surface for the five subject classes, with seven conditional non-core sources (§7–§13) enabled per `subject_class`. Expansion beyond these thirteen is a deliberate, reviewed step, not an in-run patch.
