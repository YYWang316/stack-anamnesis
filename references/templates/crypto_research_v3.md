# Crypto Research Report Template
**YYFoundry / NYU Blockchain Lab — Research SOP v3 (skeleton)**

> VERSION NOTE — v3 is a **separation-of-concerns** refactor of v2 (predecessor `crypto_research_v2.md`, still the live fallback). v2 did three jobs in one file: (1) the deliverable skeleton, (2) subject-type branching (For chain / For DeFi / For Stablecoin, Path A·B·C, the 5.1–5.5 fork forest, module-stacking), and (3) writer coaching (`> GUIDANCE` / `> TRAP` / `> ↳ Cap check`, interpretation logic, the §C confidence rules). v3 keeps ONLY job (1) — the universal deliverable spine + `<!-- MODULE: … -->` injection anchors. Jobs (2) and (3) move to the harness-side **`references/playbooks/analysis_playbook.md`**, which the writer consults at runtime. No analytical substance was removed; it was relocated. This file contains NO branching forest, NO `> GUIDANCE`/`> TRAP`, NO §C rules, NO interpretation bands, and NO metric values.

> ANCHOR CONVENTION — every `<!-- MODULE: name -->` line is a machine/writer **injection anchor**, not report body. At go-live (decision 2a) the orchestrator/filler renders the facts bundle into a generic facts table at `<!-- MODULE: metrics -->`, and the playbook-driven writer injects the selected base + stacked module sub-sections at the matching anchors. An anchor that is never consumed renders as literal escaped text in the HTML (fail-loud), so the filler MUST replace `<!-- MODULE: metrics -->` and the writer MUST consume the rest before render. The always-on spine (1.1 thesis · 1.4 evidence table · Part 7 filters · 9.5 bull/bear/thesis-breaker · 11.1 conviction) is unconditional and carries no anchor.

---

# REPORT BODY — the deliverable

## Part 0 — Meta

- **Title**:
- **Subject Type**:
- **Date**:
- **Time Horizon**: ☐ Tactical (<3mo)  ☐ Strategic (3–12mo)  ☐ Structural (>12mo)

### 0.1 Output Type & Depth

The chosen output type determines which sections are required and which may be omitted. The **deliverable keeps ONLY the selected output-type row** below (the other rows are the menu, not report body — drop them once a type is chosen):

| Output Type | Length | Must-have sections | Tone & Audience |
|-------------|--------|---------------------|------------------|
| Quick Take | ~500 words | 1.1, 1.2, 3, 6.2, 11.1 | Punchy, opinion-led / self + crypto-fluent reader |
| Public Post | ~1,500 words | 1, 3, 4 (light), 6, 7, 11 | Narrative + data balanced / YYFoundry public reader |
| Deep Dive | 3,000–5,000 | All | Comprehensive / sophisticated outside reader |
| Investment Memo | 2,000–3,000 | 1, 4.1, 4.3, 7, 8, 9 | Valuation & catalyst heavy / institutional capital allocator |
| BD / Partnership Brief | 1,500–2,500 | 1.1, 3, 4.4, 6, 7.5, 10 | Market pain + who pays / potential partner or employer |
| Academic Research Note | 5,000+ | All + reinforced methodology | Citation-heavy, hedged / academic peer |

- **Language**: en / zh / both.

---

## Part 1 — Thesis & Framing

### 1.1 One-sentence thesis

- One-sentence thesis:

### 1.2 Five-question framework

1. **Why this?**
2. **Why now?**
3. **Why will users / capital care?** (where is the real demand?)
4. **Why will value accrue?** (how is value captured — token / equity / ecosystem?)
5. **What can go wrong?** (the biggest failure path)

### 1.3 Industry stack positioning

- Primary layer:
- Layers depended on:
- Layers challenged / targeted for replacement:

### 1.4 Evidence Table

| # | Claim | Evidence | Disconfirming evidence sought | Source | Confidence |
|---|-------|----------|-------------------------------|--------|------------|
| 1 | | | | | H/M/L |
| 2 | | | | | H/M/L |

### 1.5 Data Availability

☐ **Strong** — multiple public dashboards, 6–12 months of data
☐ **Medium** — partial data, some assumptions required
☐ **Weak** — early-stage, mostly narrative / official claims

- What data is missing / what assumptions were made:

---

## Part 2 — News Hook `[Mode B only — comes BEFORE Part 1]`

### 2.1 What happened
Factual account: time, actor, event, relevant numbers.

### 2.2 Immediate reaction
Price reaction / on-chain reaction / media & KOL reaction / peer-project knock-on.

### 2.3 Why this isn't just noise
What trend does it reveal? Why does it warrant a research write-up rather than a single tweet?

---

## Part 3 — Sector Background

### 3.1 Sector classification

### 3.2 Sector size & trends
Market size / growth rate & capital flows / main drivers / main headwinds.

### 3.3 Why it matters now

---

## Part 4 — Subject Deep Dive

### 4.1 Project fundamentals
- Team & key people background
- Funding history & investors (which VCs, how many rounds, valuation)
- Current stage (whitepaper / devnet / testnet / mainnet)
- **Lineage effect**: parent-company / founder background (shapes distribution and BD capability)

### 4.2 Architecture / Mechanism

<!-- MODULE: mechanism -->

### 4.3 Tokenomics & Business Model
Total/circulating supply / allocation / unlock schedule / value-capture path / revenue model (who pays? paid to whom? how do holders share?) / FDV vs MC gap.

### 4.4 Ecosystem
Native app count & quality / TVL · activity concentration (what share do the top 3 hold?) / grants & partners / developer activity / wallet · infra · bridge support.

---

## Part 5 — Metrics

<!-- MODULE: metrics -->

<!-- MODULE: metrics-analysis -->

---

## Part 6 — Competitive Landscape

### 6.1 Comparable selection

### 6.2 Comparison matrix

<!-- MODULE: comparison-matrix -->

### 6.3 Differentiation analysis
The real moat (distribution / liquidity / compliance / tech / network effect); which "differentiators" are superficial; whether the gap to #2/#3 is qualitative or quantitative.

---

## Part 7 — Critical Filters

### 7.1 Narrative vs Data mismatch check
Strong narrative, weak data → speculative / early. Strong data, low attention → underrated. Both strong / both weak → state your position explicitly.

### 7.2 Real demand vs Incentive farming
For every usage metric ask: are users here for an airdrop/points? Is TVL mercenary capital? Is volume wash trading? Are fees subsidized? Bots vs humans in DAU?

### 7.3 Token value capture ≠ Project quality
Is protocol revenue shared with holders? Is the token governance-only? Is staking real yield or pure emission? Unlock pressure over the next 12 months? Is FDV already pricing in future growth?

### 7.4 Centralization & dependency check
Reliant on a single team / multisig? Reliant on the parent for distribution — what happens if the parent changes strategy? Where is the single point of failure (sequencer / oracle / bridge / DA / banking partner)?

### 7.5 Distribution vs Technology check
Does it win on better technology or stronger distribution? After the tech is copied, can distribution still form a moat? If distribution is strong but developers don't show up, does it become an empty chain?

---

## Part 8 — Valuation / Strategic Value

<!-- MODULE: valuation -->

---

## Part 9 — Catalysts & Risks

### 9.1 Catalysts (3–12 months)

| Catalyst | Expected Timing | Impact Direction | Likelihood |
|----------|-----------------|------------------|------------|

### 9.2 Risk matrix

Module-specific risk rows (below) **append as new rows to this single table** — do not start a second risk table.

| Risk Type | Specific Risk | Observable trigger / magnitude | Likelihood | Impact |
|-----------|--------------|--------------------------------|------------|--------|
| Market | | | | |
| Execution | | | | |
| Smart Contract | | | | |
| Regulatory | | | | |
| Centralization | | | | |
| Liquidity / Peg | | | | |
| Competitive | | | | |

<!-- MODULE: risk-rows -->

---

## Part 9.5 — Bull / Bear / Thesis-Breaker

### 9.5.1 Bull case — what would confirm the thesis
The concrete, observable developments that would validate the §1.1 thesis, each tied to the metric that would show it.

### 9.5.2 Bear case — what would break it
The developments that would falsify the §1.1 thesis, each tied to the metric that would show it.

### 9.5.3 Thesis-breakers — explicit observable triggers
Pre-commit to the triggers that flip the Position. Each is a **binary, observable** condition; when one fires, return to §1.1 and re-test whether the thesis still holds, then update §11.1 Position and §11.2 track list.

<!-- MODULE: thesis-breakers -->

---

## Part 10 — Second-Order Effects `[Mode B emphasis; Mode A optional]`

Who wins and who loses under success/failure · indirect beneficiaries · regulatory/policy knock-on · narrative-layer impact · cross-sector transmission (DeFi→CEX / RWA→traditional finance / payment→banks).

---

## Part 11 — Conclusion

### 11.1 Position
☐ Bullish ☐ Neutral ☐ Bearish — one-sentence rationale.

- **Conviction = f(evidence):** conviction is bound by (a) §1.5 Data Availability, (b) any active confidence caps (playbook §IV), and (c) the §9.5 thesis-breaker status (how many triggers are live) — the stated Position may not claim more conviction than these three jointly support.

### 11.2 Track list
KPIs to keep monitoring (1/2/3).

---

## Part 12 — Required Charts & Data

### Universal (if data exists)
- [ ] Time series: TVL / active addresses / fees / revenue (6–12mo)
- [ ] Competitive comparison table (see 6.2)
- [ ] Ecosystem / stakeholder map
- [ ] Timeline of major events (incl. future catalysts)

<!-- MODULE: charts -->

---

## Part 13 — Appendix
References & sources · Methodology notes (data range / calculation method / assumptions) · Disclaimer (required for external / institutional) · Open questions / items for follow-up research.
