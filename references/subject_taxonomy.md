---
schema_version: 1
description: Defines the five subject_class values used by P0_subject_class. Each subject under research resolves to exactly one primary class; the class then drives default data sources, freshness window, red-team focus, and output bias. Read this before P0_subject_class. Companion: references/data_source_registry.md (the registry of sources keyed off these classes).
---

# Subject Taxonomy — the five subject classes

Every run is a deep-dive on **one subject**. The subject is first resolved (name, project URL, canonical token if any), then classified into one of five **mutually exclusive primary classes** at `P0_subject_class`. The class is load-bearing — it picks default data sources, the default freshness window, the red-team profile, and the output emphasis. Cross-class nuance (e.g., a wallet that also operates a chain) is noted in the report body, not in the gate.

The five classes are derived from the a16z stablecoin-stack market map and adjacent agentic-payment infrastructure. They cover the surface that *value moves through* — issuer at the bottom, agentic-payment protocols at the top — without overlap.

```
┌─────────────────────────────────────────────────────┐
│ agentic_payment_layer   (x402, AP2, agent SDKs)     │  ← AI agents authorize + settle
├─────────────────────────────────────────────────────┤
│ wallet                  (Coinbase, Phantom, MM)     │  ← user-facing custody/UX
├─────────────────────────────────────────────────────┤
│ orchestrator            (Stripe, Bridge, BVNK)      │  ← cross-chain / cross-rail routing
├─────────────────────────────────────────────────────┤
│ stablecoin_issuer       (Circle, Tether, Sky)       │  ← unit of account, reserves
├─────────────────────────────────────────────────────┤
│ chain                   (Ethereum, Solana, Base)    │  ← settlement substrate
└─────────────────────────────────────────────────────┘
```

The vertical order is conceptual, not strict: a chain can host an issuer, an issuer can issue across chains, an orchestrator routes between issuers, a wallet sits in front of all of it, and an agentic-payment layer composes the rest. Classification is by **primary product / primary monetisation surface**, not by what the entity *also* touches.

---

## The five classes (summary)

| Class | What it is | Canonical examples | Default freshness | Default red-team focus |
|---|---|---|---|---|
| `stablecoin_issuer` | Mints + redeems a pegged digital token; holds reserves | Circle (USDC), Tether (USDT), Sky (USDS/DAI), Paxos (PYUSD/USDP), Ethena (USDe), Agora (AUSD) | `30d` | Reserve composition vs claim; attestation cadence; peg stability under stress; regulatory exposure |
| `orchestrator` | Routes value across chains / wallets / currencies; coordinates, does not custody at rest | Stripe (crypto rails), Bridge, Conduit, BVNK, Sphere, Squid | `30d` | On-chain volume vs marketing; partner concentration; regulatory licensing in claimed jurisdictions |
| `wallet` | Custodies users' assets at rest; user-facing send/receive/hold UX | Coinbase, Phantom, MetaMask, Trust Wallet, Argent, Rainbow, Robinhood Wallet | `30d` | Real MAU vs claimed; security record; key-management trust model; revenue model transparency |
| `chain` | Operates a blockchain or rollup as settlement substrate | Ethereum, Solana, Base, Arbitrum, Optimism, Tron, Polygon, Berachain | `7d` | Sequencer/validator centralisation; MEV capture; real activity vs incentive-driven TVL; censorship resistance |
| `agentic_payment_layer` | Software stack letting AI agents discover, authorize, and settle payments autonomously | x402 (Coinbase-led), AP2 (Google/Apple), CDP agent SDK, Crossmint Pay, Skyfire, Halliday | `since_TGE` | Real agent integrations vs marketing; settlement layer dependency; security model under agent compromise; protocol governance |

The five values are the **complete enum** for `P0_subject_class`. Anything not classifiable into one of these is a P0_subject_class violation — surface to the user with a `not_in_taxonomy` event and halt; do not invent a sixth class on the fly. Taxonomy extension is a deliberate change to this file, not a runtime decision.

---

## Class definitions

### 1. `stablecoin_issuer`

**Definition.** An entity whose primary product is a fiat-pegged or asset-pegged digital token. The token is issued against held reserves (cash, T-bills, crypto-collateral, or algorithmic). The issuer mints on deposit and redeems on withdrawal; the spread between reserve yield and issuance cost is the primary monetisation surface.

**Canonical examples.** Circle (USDC), Tether (USDT), Sky / formerly MakerDAO (USDS, DAI), Paxos (PYUSD, USDP, BUSD legacy), Ethena (USDe), Agora (AUSD), First Digital (FDUSD), Frax (frxUSD).

**Boundary cases.**
- A wallet that *co-distributes* an issuer's revenue (e.g., Coinbase shares USDC interest with Circle) → primary class is `wallet`, not `stablecoin_issuer`. The wallet does not mint or redeem.
- A chain that issues its own native gas token (ETH, SOL) → that token is *not* a stablecoin. Primary class is `chain`.
- A protocol that issues a tokenised T-bill (e.g., Ondo USDY, BlackRock BUIDL) → if pegged to a fiat unit with redeem-at-par semantics, classify as `stablecoin_issuer`; if it tracks NAV with yield accrual, classify as `stablecoin_issuer` and note "yield-bearing" in the report.

**Default data sources** (see `references/data_source_registry.md`):
- DefiLlama `stablecoins.llama.fi` — market cap, chain breakdown, peg deviation history.
- Issuer attestation page + RPC tier — direct reserve reads (`balanceOf` on issuer treasury wallets, `totalSupply` on the token contract).
- CoinGecko — peg deviation, 24h/7d/30d volume.

**Default red-team focus.** The numeric attacker scrutinises reserve composition vs claim (is the attestation's reserve mix consistent with on-chain treasury balances?), attestation cadence (monthly vs quarterly vs ad-hoc), and peg deviation under historical stress events (e.g., March 2023 USDC depeg, May 2022 UST). The narrative attacker scrutinises regulatory exposure (issuance jurisdiction, GENIUS Act / MiCA / Hong Kong regime), redemption mechanics under stress (who can redeem, what gates exist), and counterparty concentration in reserves (single bank, single custodian, single T-bill issuer).

---

### 2. `orchestrator`

**Definition.** An entity whose primary product is value *movement* — routing across chains, wallets, currencies, or rails. Orchestrators do **not** custody user funds at rest; they coordinate transactions between custodial parties. Monetisation is per-transaction (fee on volume, FX spread, or routing rebate).

**Canonical examples.** Stripe (crypto rails), Bridge (acquired by Stripe), Conduit, BVNK, Sphere, Squid (cross-chain), LI.FI, Socket, Wormhole (messaging + value transfer), Across Protocol.

**Boundary cases.**
- A bridge that custodies wrapped assets (e.g., wBTC custodian) → still primary `orchestrator`; the custody is incidental to the routing function.
- A wallet that *also* runs an orchestration backend (e.g., Coinbase Pay, MetaMask Bridge) → primary class is `wallet`; the orchestration is a feature of the wallet product.
- A stablecoin issuer that runs its own settlement network (e.g., Circle's Cross-Chain Transfer Protocol) → primary class is `stablecoin_issuer`; CCTP is infrastructure for issuance, not the product.

**Default data sources.**
- Dune dashboards — volume by route, fee revenue, partner integration counts.
- DefiLlama `bridges` — daily/weekly volume, TVL in bridge contracts.
- Public partnership announcements (`news_intel` agent) — claimed integrations.

**Default red-team focus.** Numeric attacker reconciles on-chain volume against marketing claims (does the Dune dashboard back the press-release number?). Narrative attacker scrutinises partner concentration (top-3 partner share), regulatory licensing in *each* claimed jurisdiction (MTL state-by-state in the US, EMI in the EU), and dependency on third-party rails (does the orchestrator actually own the rails or just resell?).

---

### 3. `wallet`

**Definition.** An entity whose primary product is end-user custody and UX — sending, receiving, holding crypto assets. Custodial (key held by entity) and non-custodial (key held by user) both qualify. Monetisation varies: trading fees, interest spread, payment-for-order-flow, staking commission, premium subscriptions.

**Canonical examples.** Coinbase (custodial), Phantom (non-custodial Solana-native), MetaMask (non-custodial EVM-native), Trust Wallet, Argent (smart-contract wallet), Rainbow, Zerion, Robinhood Wallet, Cash App (Bitcoin), Revolut (crypto tab).

**Boundary cases.**
- A wallet that runs an L2 or app-chain (e.g., Coinbase → Base) → primary class for *Coinbase* is `wallet`; for *Base* it is `chain`. The question is which entity is being researched.
- A wallet that offers staking-as-a-service or a yield product → still primary `wallet`; staking is a feature.
- A hardware wallet manufacturer (Ledger, Trezor) → primary `wallet` (the device is the UX), but the report should flag that monetisation is hardware-sales-led, not transaction-led.

**Default data sources.**
- Dune — active addresses (DAU/MAU), tx counts, fee revenue (where wallet runs its own infrastructure).
- App-store metrics (manual capture via `news_intel`) — downloads, ratings.
- CoinGecko — wallet's native token (if any) market data.

**Default red-team focus.** Numeric attacker challenges MAU/DAU claims against on-chain unique-address activity (a wallet's "MAU" should approximate Dune-observable distinct interacting addresses). Narrative attacker scrutinises security record (custody hacks, key-extraction CVEs, social-engineering incidents), key-management trust model (does non-custodial really mean non-custodial?), and revenue-model transparency (PFOF disclosure, staking-commission rate, hidden FX spread).

---

### 4. `chain`

**Definition.** An entity that operates a blockchain or rollup as a settlement substrate. Includes L1s, L2s, app-chains, and sovereign rollups. Monetisation is typically gas/fee capture (L1, L2 sequencer revenue, MEV capture) and/or native-token appreciation.

**Canonical examples.** Ethereum (community-operated), Solana (Solana Foundation + Anza + Jito), Base (Coinbase), Arbitrum (Offchain Labs / Arbitrum Foundation), Optimism (OP Labs), Tron (Tron Foundation), Polygon (Polygon Labs), Berachain, Sui, Aptos, Monad, MegaETH.

**Boundary cases.**
- An L2 operated by a wallet company (e.g., Coinbase → Base, Robinhood → forthcoming chain) → when researching the chain, primary class is `chain`; when researching the parent company, primary class is `wallet`. The subject decides.
- A "modular" stack offering shared sequencing or data availability (e.g., Celestia, EigenDA, Astria) → primary `chain` (these are infrastructure for chains, but their product *is* a chain-like settlement service).
- A bridge with a token but no chain (e.g., LayerZero) → primary `orchestrator`, not `chain`. The product is routing, not settlement.

**Default data sources.**
- DefiLlama `chains` — TVL, fees, daily active addresses.
- Dune — granular fee/MEV/transaction-type breakdowns.
- Native explorer (Etherscan, Solscan, etc.) — block stats, validator counts.
- RPC tier — block production timing, recent state diffs.
- CoinGecko — native-token price, market cap, volume.

**Default red-team focus.** Numeric attacker reconciles claimed TVL/MAU against the chain's own explorer + DefiLlama (do TVL spikes track airdrop campaigns rather than organic usage?). Narrative attacker scrutinises sequencer/validator centralisation (single-sequencer L2s, validator-set concentration on L1s), MEV-capture mechanics (who keeps the surplus), real economic activity vs incentive-driven (subtract airdrop farmers and the chain's own treasury swaps from the activity number), and censorship resistance under stress (OFAC compliance behaviour at the sequencer or validator layer).

---

### 5. `agentic_payment_layer`

**Definition.** A software stack — protocol, SDK, or service — whose primary product is enabling **AI agents** to discover, authorize, and settle payments autonomously. Distinct from human-facing payment infrastructure because the counterparty is non-human and the trust model differs (agent-attestation, scoped authorization, machine-readable payment intents). New category; most subjects are <24 months old.

**Canonical examples.** x402 (Coinbase-led revival of HTTP 402 for AI payments), AP2 (Agent Payments Protocol, Google/Apple/Stripe-adjacent), CDP agent SDK (Coinbase Developer Platform's agent toolkit), Crossmint Pay (agent-checkout), Skyfire (agent identity + payment), Halliday (agent workflow + payment), Payman, Catena Labs.

**Boundary cases.**
- A wallet that exposes an agent SDK as a feature (e.g., Coinbase Wallet's agent kit) → primary class is `wallet`; the agent SDK is incremental. Becomes `agentic_payment_layer` only when the project's *primary* product is the agent integration.
- A stablecoin issuer that adds agent-payment endpoints (e.g., Circle's CCTP-for-agents discussions) → primary `stablecoin_issuer`; the agent path is a distribution channel.
- A protocol that is *only* a payment specification (e.g., x402 the RFC vs x402 the production rollout) → primary `agentic_payment_layer`; classify the spec authors as the subject.

**Default data sources.**
- GitHub adoption metrics (manual via `news_intel`) — stars, forks, integrations.
- Dune — any on-chain settlement footprint (if the protocol uses an existing chain for settlement).
- `news_intel` — protocol launches, partner announcements, conference talks (this category is announcement-heavy and on-chain-light).
- RPC tier — settlement-contract reads if the protocol has deployed contracts.

**Default red-team focus.** Numeric attacker challenges integration counts (does "50+ integrations" match the GitHub fork/dependent count?) and on-chain settlement volume (most agentic-payment protocols claim more than they settle). Narrative attacker scrutinises settlement-layer dependency (an agentic-payment protocol that requires a specific chain or issuer inherits that party's risk), security model under agent compromise (what happens if the agent's key is exfiltrated; is there a per-transaction scope limit; is there a revocation path), and protocol governance (who controls the spec, how are breaking changes coordinated).

---

## Resolution policy (P0_subject_class)

The resolution gate works analogously to `P0_intent` in the inherited equity harness:

1. **Unambiguous → auto-resolve.** If the prompt names a subject whose primary class is unambiguous (e.g., "research Circle", "看看 Phantom", "deep-dive on Base"), the orchestrator resolves to `{subject, primary_class}` with `source: "prompt_unambiguous"` and proceeds. The agent records its reasoning trace (one sentence: *why* this primary class) to `meta/gates.json -> subject_class.rationale`.
2. **Ambiguous → ask once.** Ambiguity arises in three situations:
   - The subject spans multiple classes with no clear primary (e.g., "Coinbase" — wallet AND chain AND custody AND issuer-adjacent). Ask: *"For this run, which is the primary lens — wallet (Coinbase's app), chain (Base), or stablecoin distribution (USDC co-distribution)?"*
   - The subject is unfamiliar to the model and the prompt does not disambiguate (e.g., "research Foo" where Foo is plausible-but-unknown). Ask one clarifying question with the five classes listed.
   - The subject is named at the wrong granularity (e.g., "research Ethereum's stablecoins" — that is a sector run, not a single-subject run; P0_scope = single means the orchestrator must surface this and ask whether the user means *one* issuer on Ethereum).
3. **Out-of-taxonomy → halt.** If after the one clarifying question the subject still does not fit any of the five classes (e.g., "research Vitalik Buterin", "research the SEC's crypto enforcement record"), record `event: "not_in_taxonomy"` in `meta/run.jsonl` and halt with a message explaining the five classes and inviting a re-prompt. Do **not** invent a sixth class on the fly. Do **not** force-fit into the closest class. Taxonomy extension is a deliberate change to this file via human review, not a runtime decision.

The gate's allowed `source` values are exactly: `prompt_unambiguous`, `user_response`. There is no sticky in `USER.md` for subject_class — every run resolves freshly, because the subject changes every run.

---

## What changes per class (downstream contract)

The class is consumed downstream as follows. Each cell is the default; phase-level prompts may override with a recorded justification.

| Downstream surface | `stablecoin_issuer` | `orchestrator` | `wallet` | `chain` | `agentic_payment_layer` |
|---|---|---|---|---|---|
| Default `freshness` | `30d` | `30d` | `30d` | `7d` | `since_TGE` |
| Default data tier | DefiLlama stablecoins + RPC reserves + CoinGecko peg | Dune volume + DefiLlama bridges + news_intel partners | Dune active-addr + app-store + news_intel | DefiLlama chains + Dune fees + native explorer + RPC | GitHub + news_intel + Dune (if settled on-chain) + RPC (if deployed) |
| Numeric red-team emphasis | Reserve composition; peg deviation | On-chain vol vs claim | MAU vs on-chain unique addr | Real vs incentive-driven activity | Integration counts; settlement volume |
| Narrative red-team emphasis | Regulatory; redemption gates; counterparty | Partner concentration; jurisdictional licensing | Security record; key model; revenue transparency | Sequencer/validator centralisation; MEV; censorship | Settlement-layer dependency; agent-compromise model; governance |
| Output bias (report) | Reserve waterfall + jurisdictional map | Volume routes + partner concentration chart | Active-address trend + revenue stack | Fee/MEV breakdown + validator distribution | Integration list + settlement footprint |
| Output bias (thread) | Peg-stress narrative + reserve transparency score | Volume claim vs on-chain check | Security-track-record narrative + UX moat | Centralisation receipts + economic-activity teardown | Real-integration count + future-protocol-risk |

For the data source registry behind the "Default data tier" column, see `references/data_source_registry.md`. For the output format enum (`report` / `thread`) and its emitter rubrics, see the per-format spec in `agents/orchestrator.md` §P0_output_format and the inherited TD-001 thread rubric in `references/TODO.md`.

---

## Examples — fully resolved

| Prompt | Resolved subject | Primary class | Why |
|---|---|---|---|
| "research Circle" | Circle Internet Financial | `stablecoin_issuer` | Issues USDC; reserves + redemption is the product |
| "看看 Tether" | Tether Limited | `stablecoin_issuer` | Issues USDT |
| "deep-dive on Stripe's crypto" | Stripe Crypto (incl. Bridge) | `orchestrator` | Routes value across rails; does not custody at rest |
| "research Phantom" | Phantom (wallet) | `wallet` | Custody + UX is the product, even with Solana-native bias |
| "build cards for Coinbase" | Coinbase, Inc. | `wallet` | Wallet is the primary user-facing product (ask once to confirm vs Base) |
| "research Base" | Base | `chain` | L2 settlement substrate (separate from Coinbase the wallet) |
| "看看 Solana" | Solana | `chain` | L1 settlement substrate |
| "research x402" | x402 protocol | `agentic_payment_layer` | Primary product is the AI-agent payment specification |
| "deep-dive on AP2" | AP2 (Agent Payments Protocol) | `agentic_payment_layer` | Primary product is the agent-payment spec |
| "research Skyfire" | Skyfire | `agentic_payment_layer` | Primary product is agent identity + payment |
| "research Vitalik" | — | **out-of-taxonomy** | Person, not entity. Halt. |
| "research SEC crypto rules" | — | **out-of-taxonomy** | Regulatory regime, not entity. Halt. |

---

## Extending the taxonomy

When real runs surface a subject that genuinely doesn't fit any of the five classes (not "I'll squeeze it in" — *genuinely*), do not patch the gate. Instead:

1. Record the `not_in_taxonomy` event with the subject and the closest-but-not-quite class.
2. Open a `/log-incident`-style entry (or a TODO in `references/TODO.md`) capturing the new subject shape.
3. Propose a sixth class via a PR to this file, with: definition, three canonical examples, boundary rules, default data tier, default red-team focus, default freshness.
4. Once the new class is accepted, every downstream table in this file gets a new column, and the enum in `P0_subject_class` is updated.

The taxonomy is small on purpose. Five classes covers the crypto-payments stack as it exists today. A sixth should clear the same bar as a new `INCIDENTS.md` entry: *is this worth being read every session forever?*
