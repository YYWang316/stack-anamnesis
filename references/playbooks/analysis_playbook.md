# Stack Anamnesis — Analysis Playbook
**Harness-side reasoning layer for the v3 skeleton (`references/templates/crypto_research_v3.md`)**

> NON-DELIVERABLE. This file is consulted by the report-writer at runtime and is **never rendered** into the report. It holds the three jobs the v3 skeleton deliberately dropped: (i) subject classification, (ii) the per-class MODULE library + deterministic stacking, (iii) the global writing primitives, and (iv) the hard confidence caps. All coaching here uses the existing `> GUIDANCE` convention so the renderer's `strip_coaching` backstop and the writer's own strip step both apply if any of it ever leaks into a draft. Examples use PLACEHOLDERS (`$X.XB`, `−Y%`) — never real subject numbers; the machine owns every real number (see DRAFT flow + decision 2a).

---

# DRAFT — Proposed Writer Runtime Flow `[block C — NOT YET LIVE]`

> GUIDANCE: This is the PROPOSED procedure for the `crypto-report-writer` agent under v3. It is a DRAFT for the go-live phase — do NOT treat it as the live brief yet. The live brief (`.claude/agents/crypto-report-writer.md`) and `orchestrate.DEFAULT_TEMPLATE` still point at v2 and are unchanged. At go-live this block becomes the writer brief's flow.

**Inputs:** the facts bundle `<slug>_<utc>.facts.json` (schema `stack_anamnesis.facts_bundle/v1`) and the v3 skeleton (with the machine-injected facts table already dropped at `<!-- MODULE: metrics -->`).

1. **Read `subject_type`** (+ `issuer`, `identifiers`, `issuer_financials` presence) from the bundle. These are the composite flags.
2. **Classify** via §I (A–H). `subject_type` maps deterministically to a class; an unknown/`null` type falls back to class **H (narrative)** — mirrors the filler's FAIL-SAFE (keep everything, drop nothing).
3. **Consult the stacking table (§II.0).** `subject_type` → ONE base module + zero-or-more deterministic add-ons. The LLM's only judgment is the small, enumerated "does this add-on trigger?" test stated in the table — never freeform module invention.
4. **Read the skeleton.** Locate the `<!-- MODULE: … -->` anchors.
5. **Inject** each selected module's sub-sections at its docking anchor (§II per-class library names the anchor). The base module + each add-on contribute their 命门指标 framing, specialized sub-questions, comparison-matrix columns, valuation anchor, and risk rows at the matching anchors. **Numbers come from the machine-injected facts table (decision 2a, invariant 1) — the writer references those figures and interprets them; it does not introduce a number absent from the bundle/table.**
6. **Apply the 4 global primitives (§III)** to all injected prose: Insight Contract, Interpretation Bands, Synthesis line, CT-Cards (the CT-Card disconfirmation result fills §1.4's "Disconfirming evidence sought" column).
7. **Apply the confidence caps (§IV)** as hard ceilings; state any realized cap in §1.4 and §11.1 (e.g. "capped at MEDIUM — Rule 1 (three-source)"). The cap RESULT appears in the body; the cap pointer/GUIDANCE does not.
8. **Strip the coaching channel** (`> GUIDANCE` / `> TRAP` / `> ↳ Cap check`) from the deliverable, and **return the whole report markdown** (no fences, English body).

> GUIDANCE: invariant — the writer never edits a machine-placed figure, never fills a `[MANUAL]`/`UNFILLED` flag with a fabricated value, and never duplicates a table (emit the §5.5 KEY SIGNAL verdict table exactly once when the stablecoin module is selected).

---

# §I — Classification (A–H) + the composite rule

> GUIDANCE: classes are keyed to the REAL `subject_type` taxonomy the bundle carries (`stablecoin`, `chain`, `l1`, `l2`, `defi_protocol`, `payment_chain`, `crypto_native_asset`) plus two overlays detected from bundle fields (`issuer` / `issuer_financials` present → listed-issuer overlay). Do not invent new `subject_type` strings.

| Class | Name | Primary `subject_type` trigger | Notes |
|-------|------|--------------------------------|-------|
| **A** | Stablecoin (coin-layer) | `stablecoin` | always composite — pairs with the issuer overlay (F) |
| **B** | L1 / general-purpose chain | `chain`, `l1` | the base for most chain work |
| **C** | L2 / Rollup | `l2` | always has an operator/parent overlay |
| **D** | DeFi protocol | `defi_protocol` | token add-on if it has a governance/fee token |
| **E** | Payments / no-token infra | `payment_chain` (and infra w/o a token) | flow-economics, not lock |
| **F** | Listed-co / regulated issuer (overlay) | `issuer` set + `issuer_financials` present (e.g. Circle CIK 0001876042, Coinbase, MARA) | stacks onto A / C / E / G; standalone for a pure listed co |
| **G** | CeFi / centralized venue (overlay) | exchange / custodian subject | usually resolves to F when SEC-listed |
| **H** | Narrative / thematic (fallback) | unknown / `null` `subject_type` | spine-only; FAIL-SAFE class |

**Composite (two-layer) rule.** A real subject is rarely one pure class. Every subject is **one base + its deterministic add-ons** (§II.0). The canonical two-layer cases: a **stablecoin = coin-layer (A) + issuer-layer (F)**; an **L2 = chain-layer (C) + parent-entity overlay (F/G)**; a **payment chain that issues its own stablecoin = chain (B) + payments (E) + stablecoin (A)**. The base is chosen by `subject_type`; the add-ons are switched on by the enumerated triggers — the LLM never freelances which modules apply.

---

# §II — Per-class MODULE library + stacking

## §II.0 — Deterministic stacking table `[subject_type → base + add-ons]`

> GUIDANCE: read `subject_type` from the bundle, take the ONE base row, then switch on each add-on ONLY when its stated trigger is true. This is the entire module-selection decision — narrow and deterministic.

| `subject_type` | Base module | Deterministic add-ons | Add-on trigger |
|----------------|-------------|-----------------------|----------------|
| `stablecoin` | **A** coin-layer | **+ F** issuer-layer | always (every stablecoin has an issuer) |
| | | **+ B + E** | only if the stablecoin is itself a chain (rare) |
| `chain` / `l1` | **B** L1 | **+ token-asset (4.3)** | native token has speculative tokenomics |
| `l2` | **C** L2 | **+ F/G** parent overlay | always (every L2 has an operator) |
| | | **+ token-asset (4.3)** | the L2 has a token |
| `defi_protocol` | **D** DeFi | **+ token-asset (4.3)** | protocol has a governance/fee token |
| `payment_chain` | **B** chain **+ E** payments | **+ A** stablecoin coin-layer | the chain issues / natively anchors its own stablecoin (e.g. Arc, Tempo) |
| | | **+ F** parent issuer | parent is a listed/regulated co (e.g. Arc→Circle) |
| `crypto_native_asset` | **token-asset (4.3)** | **+ B** L1 | the asset is a chain's native gas/stake asset (BTC/ETH/SOL) |
| `null` / unknown | **H** narrative | none | FAIL-SAFE — spine only, nothing dropped |

> GUIDANCE: "token-asset (4.3)" is the tokenomics sub-module that docks at Part 4.3 (supply/allocation/unlock/value-capture/FDV-vs-MC). It is an add-on, not a standalone class, because its analysis is identical wherever a speculative token appears.

## §II.A — Stablecoin (coin-layer)
- **命门指标:** net **supply slope** (organic vs mechanical). Peg is fixed at $1, so supply increase/decrease is the *only* demand signal — always read the slope of net change, never the absolute level.
- **Specialized sub-questions (old 5.5 A–H):**
  - **A Supply & distribution:** net 7d/30d slope · native vs bridged (native = issuer's active bet) · per-chain breakdown (which ecosystem pulls growth) · mint/redeem velocity.
  - **B Holder structure:** CEX vs DeFi-contract vs EOA split (is it a trading chip or money?) · top-10/100 concentration · grassroots vs whale growth.
  - **C Peg stability:** depeg depth **and recovery time** · Curve 3pool balance as a live peg gauge · cross-stablecoin swap flow.
  - **D Reserve & backing:** composition (cash / T-bill / repo; shorter duration = safer) · attestation cadence (attestation ≠ audit) · auditor tier · duration & yield · **banking-partner concentration** · redemption stress / run resilience (instantly-liquid share vs duration mismatch).
  - **E Issuer economics:** revenue = supply × reserve yield · distribution rev-share dependency · interest-rate 3-scenario sensitivity.
  - **F Regulatory posture:** licenses (NYDFS / EMI / MAS) · GENIUS Act / MiCA status · freeze/blacklist capability (a plus for institutions, a minus for crypto-natives — set audience first).
  - **G Cross-chain mechanics:** native/CCTP (safest) vs bridged/wrapped (bridge risk).
  - **H Real-world use:** real payment vs CEX shuffle; de-noise bot/MEV.
- **KEY SIGNAL verdict table** (emit ONCE; the renderer highlights the ☑ row):

  | Verdict | Supply | Holder | Usage | Read |
  |---------|--------|--------|-------|------|
  | ☐ CONFIRMATION | ↑ | ↑ | ↑ | Genuine demand expansion |
  | ☐ DIVERGENCE | ↑ | → / ↓ | → / ↓ | Mechanical growth risk — mark low confidence |
  | ☐ CONTRACTION | ↓ | ↓ | ↓ | Capital leaving — investigate cause |

  > GUIDANCE: holder + usage legs are often `[MANUAL]` this run; if you cannot confirm them, call the verdict supply-leg-only and provisional — do NOT overclaim CONFIRMATION. A DIVERGENCE verdict triggers §IV Rule 3.
- **Crypto-native valuation anchor:** NOT a token price (≈$1). Value the issuer float business — see module F (reserve-income capitalization). Market-share trajectory = supply growth rate vs peers, weighted by the KEY SIGNAL growth-quality verdict.
- **Fatal red flags:** DIVERGENCE (mechanical) supply growth used as demand · single-bank reserve concentration (the SVB lesson) · attestation missed/late · duration mismatch vs redemption capacity · depeg recovery > 72h.
- **Docks into:** mechanism (4.2) · metrics (5) · comparison-matrix (6.2) · valuation (8, via F) · risk-rows (9.2) · thesis-breakers (9.5.3).

## §II.B — L1 / general-purpose chain
- **命门指标:** **real fee revenue net of incentives** (REV / fees not paid for by emissions) + retained active addresses (retention, not raw DAU).
- **Specialized sub-questions:** consensus / finality / block-time / VM / DA · validator-set decentralization (Nakamoto coefficient) · outage & reorg history · TVL trend · stablecoin supply on chain · DEX volume · protocol count · bridge net flow.
- **Crypto-native valuation anchor:** P/F (market cap ÷ annualized fees) · REV multiple · FDV-vs-MC gap · unlock-adjusted. *No P/E, no DCF, no price target.*
- **Fatal red flags:** outage/reorg history · low Nakamoto coefficient · fees entirely emission-subsidized (no real demand) · TVL is mercenary capital.
- **Docks into:** mechanism (4.2) · metrics (5) · comparison-matrix (6.2) · valuation (8).

## §II.C — L2 / Rollup
- **命门指标:** **sequencer unit-economics** — sequencer margin = L2 fees collected − L1 DA/settlement cost — together with the **trust assumption** (proof system).
- **Specialized sub-questions:** proof system (fraud / validity / **none**) · sequencer decentralization & censorship resistance · DA layer (blobs / altDA) · withdrawal/exit risk & challenge-period liveness · L2Beat stage & risk rows · TVS · who operates/upgrades it.
- **Crypto-native valuation anchor:** capitalized sequencer margin · P/F on net sequencer revenue · strategic value to the parent.
- **Fatal red flags:** **no fraud/validity proof + single sequencer → may NOT be called "secured by Ethereum" (Rule 4)** · centralized upgrade key / multisig · high exit risk · negative (subsidized) sequencer margin.
- **Docks into:** mechanism (4.2) · metrics (5) · comparison-matrix (6.2) · valuation (8) · risk-rows (9.2).

## §II.D — DeFi protocol
- **命门指标:** **real yield vs subsidized yield** (fee_revenue/TVL vs emission_value/TVL) + **fee-switch status** (does revenue actually reach the token?).
- **Specialized sub-questions:** core mechanism (AMM curve / collateral-liquidation / funding rate) · oracle dependency · utilization (borrowed/supplied) · liquidation volume & bad debt · open interest (perp) · insurance fund · depositor/borrower count · fee-switch governance path.
- **Crypto-native valuation anchor:** P/F (MC ÷ annualized fees) · P/S · real-yield multiple · unlock-adjusted · token-value-capture check (revenue-to-holders vs governance-only).
- **Fatal red flags:** yield is pure emission (mercenary TVL) · oracle single point of failure · accrued bad debt · fee-switch "promised, not live" · governance capture.
- **Docks into:** mechanism (4.2) · metrics (5) · comparison-matrix (6.2) · valuation (8) · risk-rows (9.2).

## §II.E — Payments / no-token infra
- **命门指标:** **Transaction Volume / TVL ratio** (flow, not lock) + single-transaction economics (median fee · finality · failed-tx rate) + non-speculative usage share.
- **Specialized sub-questions:** stablecoin transfer volume & count · avg tx size (retail vs institutional) · median fee · finality · failed-tx rate · on/off-ramp partners · merchant/fintech/bank adoption · cross-border corridors.
- **Crypto-native valuation anchor:** Path B — who captures value? · strategic value to parent · indirect beneficiaries (public tokens/protocols) · comparable business models (Visa / Stripe / SWIFT / Tron-as-USDT-rail). *No token price.*
- **Fatal red flags:** volume is CEX shuffle, not real payment · distribution wholly dependent on the parent · empty chain (no developers) · TVL-obsession misreading a flow business.
- **Docks into:** mechanism (4.2) · metrics (5) · comparison-matrix (6.2) · valuation (8) · risk-rows (9.2).

## §II.F — Listed-co / regulated issuer (overlay; the issuer-layer of A)
- **命门指标:** operating-margin sensitivity to (rates × float) — i.e. reserve income; for a listed co, revenue / net income from the SEC `issuer_financials`.
- **Specialized sub-questions:** revenue model (supply × reserve yield) · distribution rev-share dependency (the most critical cost line and a strategic dependency) · interest-rate 3-scenario sensitivity · profitability / runway · licenses held.
- **Crypto-native valuation anchor:** enterprise value from **capitalized reserve income** (annualized reserve income × applicable multiple); comparables = the public issuer's SEC market cap, money-market-fund managers, payment networks as a *business-model* analogue. *Use the bundle's `issuer_financials` (revenues / net income / equity / fiscal_year); no DCF, no equity P/E target.*
- **Fatal red flags:** revenue concentrated in one distribution partner · a rate-down scenario that collapses margin · regulatory license loss.
- **Docks into:** valuation (8) · metrics (5, issuer financials) · risk-rows (9.2).

## §II.G — CeFi / centralized venue (overlay)
- **命门指标:** revenue mix & balance-sheet solvency (proof-of-reserves vs liabilities); for a listed venue, SEC financials (resolves to F).
- **Specialized sub-questions:** revenue mix (trading fees / custody / interest) · proof-of-reserves cadence · commingling / related-party exposure · regulatory standing.
- **Crypto-native valuation anchor:** enterprise value vs comparable regulated venues; SEC market cap if listed.
- **Fatal red flags:** related-party transactions · no proof-of-reserves · commingled customer funds · active regulatory enforcement.
- **Docks into:** valuation (8) · metrics (5) · risk-rows (9.2).

## §II.H — Narrative / thematic (FAIL-SAFE)
- **命门指标:** none singular — the thesis itself is the unit of analysis; treat as sector/Mode-B framing.
- **Specialized sub-questions:** what structural trend, who benefits/loses, is it real demand or attention.
- **Crypto-native valuation anchor:** N/A — strategic / indirect beneficiaries only.
- **Fatal red flags:** a narrative with no falsifiable metric · no on-chain subject to verify against.
- **Docks into:** spine only (no module anchors required); selected when `subject_type` is unknown/`null` so nothing is dropped.

---

# §III — Global writing primitives `[apply to all injected prose]`

> GUIDANCE: the v3 skeleton no longer carries GUIDANCE, so these four primitives are the single home of the writing discipline. Apply each one to every module's prose. Examples are PLACEHOLDERS — never real numbers.

**1. Insight Contract — NUMBER → SO-WHAT → SO-WHAT-NOW.**
> GUIDANCE: never state a figure bare. Chain it: the machine-placed NUMBER → what it MEANS (so-what) → what to DO/WATCH now (so-what-now). Example: "Net 30d supply `−Y%` (so-what: demand is contracting, not just flat) → (so-what-now: re-test the §1.1 thesis; this trips a thesis-breaker if it holds two months)."

**2. Interpretation Bands — number → meaning, per 命门指标.**
> GUIDANCE: for each class's make-or-break metric, give the reader the band that converts the machine number into a judgment. Example (placeholder): supply slope `> +X%/30d` = expansion · `±X%` = flat/watch · `< −X%/30d` = contraction. Peg deviation `< ±0.X%` = healthy · sustained `> ±0.X%` = stress. Bands are qualitative scaffolding; the number itself is machine-placed.

**3. Synthesis line — one-line net judgment per major Part.**
> GUIDANCE: close each major Part with a single net-judgment sentence written as `One-line conclusion: …` (the renderer promotes this to a callout). It is the Part's "so what" in one line, not a summary of the data.

**4. CT-Cards — active disconfirmation → §1.4.**
> GUIDANCE: for each non-trivial claim, run a counter-thesis card: state what observation would FALSIFY the claim, then go look for it. Write the result into §1.4's "Disconfirming evidence sought" column (found no counter-example / found a partial one and downgraded / the contradicting data is `[MANUAL]` this run). An empty column = no falsification check = no due diligence.

---

# §IV — Confidence Downgrade Rules `[HARD caps — relocated verbatim-in-substance from v2 §C]`

> GUIDANCE: these are mandatory CEILINGS, not suggestions. No matter how confident the author feels, claimed confidence may not exceed these caps. If a rule fires, downgrade and name the rule in the §1.4 Evidence Table row and in §11.1. (At go-live these are enforced by the B.3 QC / red-team layer; until then the writer must obey them manually.)

1. **Three-source rule.** If a **core metric** (one directly supporting the thesis or Position) has **fewer than 3 independent sources** → the entire conclusion's confidence is **capped at MEDIUM**; High may not be claimed. (Read each metric's `agreement` / `confidence` and count `sources[]`; a `single_source` figure can never back a High conclusion.)
2. **Pre-mainnet rule.** If the subject is **not yet on mainnet** (whitepaper / devnet / testnet) → usage / traction data **may not** be used as bullish evidence. Design intent may be described, but any "adoption / traction" argument is invalid at this stage.
3. **Stablecoin mechanical-growth rule.** If supply **↑** but holder count **AND** real usage are simultaneously flat/declining (the §II.A KEY SIGNAL verdict is **DIVERGENCE**) → that growth **must** be downgraded and labeled **"mechanical growth risk"**, and may not be used as positive evidence of demand expansion.
4. **L2 trust-assumption rule.** If an L2 has **no fraud proof or validity proof** (or high withdrawal/exit risk) → it **may not** be claimed to be "secured by Ethereum." State the **actual** trust assumption instead (single-sequencer honesty / multisig upgrade key / liveness within the challenge period).
