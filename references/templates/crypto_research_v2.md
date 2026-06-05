# Crypto Research Report Template
**YYFoundry / NYU Blockchain Lab — Research SOP v2**

> VERSION NOTE — v2 is a structural **reorganization (M1–M5)** of the v1.4 content (predecessor: `crypto_research_v1.3.md`, content header "SOP v1.4", now archived) **plus a rigor pass (R1–R5)**. No analytical substance was removed. Reorg: M1 changelog→back matter · M2 Confidence Downgrade Rules→front matter §C (with one-line in-section `↳ Cap check` pointers) · M3 data-acquisition workflow→back matter · M4 unified "branch-by-subject (For X:)" sub-structure · M5 GUIDANCE/TRAP channel separating writer-coaching from the deliverable body. Rigor: R1 Part 9.5 Bull/Bear/Thesis-Breaker · R2 §11.1 conviction binding · R3 §5.5 propagation pointers · R4 §1.4 disconfirming-evidence column · R5 §9.2 observable-trigger column (all crypto-native; no DCF / P-E / Porter / equity frames; no number or metric-annotation marker touched). Language: report body + structural scaffolding = English; `> GUIDANCE` / `> TRAP` / `> ↳ Cap check` lines are writer-facing coaching — strippable, and they never appear in the deliverable.

> **Reading convention (M5):** anything inside a `> GUIDANCE` or `> TRAP` blockquote is coaching for the writer and **never appears in the deliverable**. Everything outside those blockquotes is report body. `> ↳ Cap check:` pointers are likewise writer-facing (non-deliverable) and reference the global Confidence Downgrade Rules in Front Matter §C.

---

# FRONT MATTER — operating instructions (read once; not part of the deliverable)

## A. How to Use

Both modes share the main framework; they differ only in **entry order**.

**Mode A — Subject-Driven** (researching a specific chain / protocol / asset; prompt has no obvious news trigger)
`Part 0 → 1 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 11 → 12 → 13`

**Mode B — News-Driven** (triggered by news / an event; prompt contains keywords like "react to…" / "X just…" / "newsflash")
`Part 0 → 2 → 1 → 3 → 4 (if needed) → 5 (if applicable) → 6 → 7 → 9 → 10 → 11 → 12 → 13`

> GUIDANCE: Mode B 先讲 what happened（Part 2），再抽象成 thesis（Part 1）。Mode 由 agent 从 prompt 自动检测，user 不需显式选择。Mode × Scope 两个独立维度：Mode B × single 完全支持；Mode B × sector（新闻引发的横评）暂延，见 TD-002。

**Module-stacking principle:** the metrics modules in Part 5 are **stackable, not mutually exclusive.**

> GUIDANCE（v1.3 重要）：研究 USDC → 只填 5.5，链指标段（5.1/5.2）正确留空。研究 Arc（发自己稳定币的 payment chain）→ 同时填 5.1/5.2（看链）+ 5.3（看支付）+ 5.5（看链上 native 稳定币）。

Each section is tagged `[Both]` / `[Mode A]` / `[Mode B]`.

## B. Metric Annotations (legend)

- `[AUTO: <source>]` — analysis layer reads the field straight from the envelope; no computation.
- `[SEMI-AUTO: <source> + <formula>]` — computed via a fixed formula or cross-source aggregation.
- `[MANUAL: <reason>]` — not available from B.1 fetchers, or requires human judgment.

> GUIDANCE: 见 Back Matter「Data Acquisition Workflow」了解 fetcher 调用与 envelope 形态。

## C. Confidence Downgrade Rules `[HARD rules — caps, not suggestions]`

These are **mandatory rules**, not best-practice suggestions. They **CAP** the confidence the report's conclusions may claim — no matter how subjectively confident the author is, this ceiling cannot be exceeded. If any rule is triggered, downgrade per the rule and note which rule fired in the corresponding Part 1.4 Evidence Table row and in the Part 11 Conclusion.

> GUIDANCE — 执行说明：这些规则将由 **B.3 QC / red-team 层以代码强制执行**（自动扫描 report 触发条件并改写 confidence 上限）。在 B.3 落地前，它们是 report **必须人工遵守**的成文规则——Quality Self-Check 第 9 项即检查此点。

1. **Three-source rule:** if a **core metric** (a metric directly supporting the thesis or Position) has **fewer than 3 independent sources** → the entire conclusion's confidence is **capped at MEDIUM**; High may not be claimed.
2. **Pre-mainnet rule:** if the subject is **not yet on mainnet** (still whitepaper / devnet / testnet) → usage / traction data **may not** be used as bullish evidence. Design intent may be described, but any "adoption / traction" argument is invalid at this stage.
3. **Stablecoin mechanical-growth rule:** if supply **↑** but holder count **AND** real usage are simultaneously flat / declining (i.e. the Part 5.5 KEY SIGNAL is judged **DIVERGENCE**) → that growth **must** be downgraded and labeled **"mechanical growth risk"**, and may not be used as positive evidence of demand expansion. (This is the 5.5 DIVERGENCE verdict converted into a hard cap.)
4. **L2 trust-assumption rule:** if an L2 has **no fraud proof or validity proof** (or has high withdrawal / exit risk) → it **may not** be claimed to be "secured by Ethereum." It must instead state the **actual trust assumption** (e.g. relies on a single sequencer's honesty / a multisig upgrade key / a liveness assumption within the 7-day challenge period).

---

# REPORT BODY — the deliverable

## Part 0 — Meta `[Both]`

- **Title**:
- **Subject Type**:
  - ☐ Chain  ☐ L2/Rollup  ☐ DeFi Protocol  ☐ News Reaction
  - ☐ **Asset/Token** (split into two in v1.3; research dimensions differ greatly — pick exactly one):
    - ☐ **Stablecoin** (USDC, USDT, PYUSD, DAI, M^0) → use Part 5.5 + Path C
    - ☐ **Crypto-native asset** (BTC, ETH, SOL, governance tokens) → use Part 4.3 tokenomics + Path A

> GUIDANCE: Sector/Thematic 类暂不支持，见 references/TODO.md TD-002。跨多 subject 请拆成多次 single run 后手工合成。

- **Date**:
- **Time Horizon**: ☐ Tactical (<3mo)  ☐ Strategic (3–12mo)  ☐ Structural (>12mo)

### 0.1 Output Type & Depth

The chosen output type determines which sections are required and which may be omitted:

| Output Type | Length | Must-have sections | Tone & Audience |
|-------------|--------|---------------------|------------------|
| Quick Take | ~500 words | 1.1, 1.2, 3, 6.2, 11.1 | Punchy, opinion-led / self + crypto-fluent reader |
| Public Post | ~1,500 words | 1, 3, 4 (light), 6, 7, 11 | Narrative + data balanced / YYFoundry public reader |
| Deep Dive | 3,000–5,000 | All | Comprehensive / sophisticated outside reader |
| Investment Memo | 2,000–3,000 | 1, 4.1, 4.3, 7, 8, 9 | Valuation & catalyst heavy / institutional capital allocator |
| BD / Partnership Brief | 1,500–2,500 | 1.1, 3, 4.4, 6, 7.5, 10 | Market pain + who pays / potential partner or employer |
| Academic Research Note | 5,000+ | All + reinforced methodology | Citation-heavy, hedged / academic peer |

- **Workshop add-on**: any output type may check `+workshop` to additionally generate the YYFoundry brand-content planning bench (not part of the deliverable; see Back Matter).
- **Language**: any output type may choose en / zh / both. `both` produces two independent drafts in parallel (not a bilingual side-by-side).

---

## Part 1 — Thesis & Framing `[Both]`

### 1.1 One-sentence thesis

> GUIDANCE: 不写 "X 是一个 L1"，写 "X 是 Y 在 Z 方向的尝试，关键看 W"。
> Example: *Arc is Circle's attempt to build a stablecoin-native settlement layer. The core question is whether dedicated payment L1s can capture transaction volume from general-purpose chains.*

- One-sentence thesis:

### 1.2 Five-question framework

1. **Why this?**
2. **Why now?**
3. **Why will users / capital care?** (where is the real demand?)
4. **Why will value accrue?** (how is value captured — token / equity / ecosystem?)
5. **What can go wrong?** (the biggest failure path)

### 1.3 Industry stack positioning

> GUIDANCE: 按 subject 选更有解释力的版本（或同时用）。**填写**：Primary layer / 依赖哪几层 / 挑战或想取代哪几层。

**Option A — "From Atoms to Bits" (physical → digital stack)** (mining / hardware / energy / L1 infra)

| Layer | Description | Example |
|-------|-------------|---------|
| L0 | Energy / Materials | hydro, gas, quartz |
| L1 | Semiconductor / ASIC | TSMC, Bitmain |
| L2 | Mining / Validators | MARA, Riot, validator sets |
| L3 | Consensus / Protocol | Bitcoin, Ethereum, Solana |
| L4 | Settlement / Bridge | rollups, CCTP, bridges |
| L5 | Application / DeFi | Aave, Uniswap |
| L6 | Consumer / Interface | wallets, exchanges |

**Option B — Crypto-Fintech (financial infrastructure stack)** (stablecoin / payment / RWA / institutional infra)

| Layer | Description | Example |
|-------|-------------|---------|
| L0 | Regulatory / Banking Interface | licenses, KYC/AML, banking partners |
| L1 | Asset Issuance / Liquidity | USDC, USDT, PYUSD, M^0 |
| L2 | Settlement Infrastructure | Ethereum, Solana, **Arc, Tempo** |
| L3 | Execution / Routing / Bridge | L2s, CCTP, routers |
| L4 | Financial Primitives | DEX, lending, perps, RWA |
| L5 | Application Workflows | checkout, payout, remittance, payroll |
| L6 | Distribution / Interface | wallets, fintech apps, exchanges, merchants |

> GUIDANCE — 示例（Arc, Option B）: Arc 不只是一条 chain。它是 Circle 从 **L1 (Asset Issuance) 向 L2 (Settlement) 甚至 L4-L5 (Workflows)** 的纵向整合，目标是把 USDC 从 "asset" 升级到 "rails"。

- Primary layer:
- Layers depended on:
- Layers challenged / targeted for replacement:

### 1.4 Evidence Table

> GUIDANCE: 所有非 trivial 的 claim 都列入。这是 report 和 opinion piece 的分水岭。
> GUIDANCE (R4): "Disconfirming evidence sought" 列填你为**证伪**该 claim 主动找了什么、结果如何（找了没找到反例 / 找到部分反例并据此降了 confidence）。留空 = 没做证伪检验，等于没做尽调。

| # | Claim | Evidence | Disconfirming evidence sought | Source | Confidence |
|---|-------|----------|-------------------------------|--------|------------|
| 1 | | | | | H/M/L |
| 2 | | | | | H/M/L |

### 1.5 Data Availability

☐ **Strong** — multiple public dashboards, 6–12 months of data
☐ **Medium** — partial data, some assumptions required
☐ **Weak** — early-stage, mostly narrative / official claims

- What data is missing / what assumptions were made:

> GUIDANCE: 若 Weak，开篇加免责：*"This report is based on early-stage data. Current conclusions should be treated as preliminary until [mainnet usage / volume / dev activity] become observable."*

> ↳ Cap check: the Confidence Downgrade Rules (Front Matter §C) cap claimable confidence — annotate the triggering rule in the relevant Evidence Table row.

---

## Part 2 — News Hook `[Mode B only — comes BEFORE Part 1]`

### 2.1 What happened
Factual account: time, actor, event, relevant numbers.

### 2.2 Immediate reaction
Price reaction / on-chain reaction / media & KOL reaction / peer-project knock-on.

### 2.3 Why this isn't just noise
What trend does it reveal? Why does it warrant a research write-up rather than a single tweet?

---

## Part 3 — Sector Background `[Both]`

### 3.1 Sector classification

> GUIDANCE: 不要泛泛归类（Arc 不是 "L1"，是 "stablecoin-native settlement layer"）。

### 3.2 Sector size & trends
Market size / growth rate & capital flows / main drivers / main headwinds.

### 3.3 Why it matters now

> GUIDANCE: 监管节点（GENIUS Act / MiCA）？技术成熟？市场结构变化？资金 rotation？

---

## Part 4 — Subject Deep Dive `[Mode A primary; Mode B if news has a central subject]`

### 4.1 Project fundamentals
- Team & key people background
- Funding history & investors (which VCs, how many rounds, valuation)
- Current stage (whitepaper / devnet / testnet / mainnet)
- **Lineage effect**: parent-company / founder background (Arc-Circle, Tempo-Stripe, Codex are especially important — it shapes distribution and BD capability)

### 4.2 Architecture / Mechanism

**For chain:** consensus mechanism / TPS · finality · block time / VM choice / DA layer / validator · sequencer structure & decentralization / security assumptions & upgrade mechanism.

> ↳ Cap check: Rule 4 (Front Matter §C) — for an L2 with no fraud/validity proof or high exit risk, do **not** claim "secured by Ethereum"; state the actual trust assumption.

**For DeFi protocol:** core mechanism (AMM curve / collateral-liquidation / funding rate) / oracle dependency / upgrade & governance path / degree of coupling to the underlying chain.

**For Stablecoin:**
- Issuance mechanism (fiat-backed / crypto-backed / algorithmic / hybrid)
- Mint/redeem flow (who can mint directly, min size, settlement window)
- Freeze/blacklist capability & governance (degree of centralized control)
- Cross-chain mechanism (CCTP native burn-and-mint vs bridged vs wrapped)
- Main distribution partners (CEX / fintech / wallet integrations)

### 4.3 Tokenomics & Business Model `[Crypto-native asset / token-bearing protocol]`
Total/circulating supply / allocation / unlock schedule / value-capture path / revenue model (who pays? paid to whom? how do holders share?) / FDV vs MC gap.

> GUIDANCE — ⚠️ Stablecoin 不走本节（没有投机性 tokenomics），走 Part 5.5 + Part 8 Path C。无 token 的 infra（Arc/Tempo）走 Part 8 Path B。

### 4.4 Ecosystem
Native app count & quality / TVL · activity concentration (what share do the top 3 hold?) / grants & partners / developer activity / wallet · infra · bridge support.

---

## Part 5 — On-Chain Metrics `[Mode A required; Mode B if applicable]`

> GUIDANCE: 各 metrics module 按 subject type 选填、可叠加。Metric 标签含义见 Front Matter §B。每个稳定币子节先回答 GUIDANCE 里的分析问题，metric 是支撑论据，不是终点。

### 5.1 Generic metrics `[Chain / L2 / DeFi]`
- TVL over time `[AUTO: DefiLlama historical TVL series]`
- Daily / Monthly Active Addresses `[AUTO: Etherscan stats; SEMI-AUTO if cross-chain aggregation]`
- Transactions (count & volume) `[AUTO: Etherscan; Alchemy cross-validation]`
- Fees / Revenue `[AUTO: DefiLlama protocol fees endpoint]`
- User retention (cohort) `[MANUAL: needs Dune (TD-024) or custom Etherscan tx-history analysis]`
- Token incentives as a share of TVL `[SEMI-AUTO: DefiLlama emission / TVL]`

### 5.2 Chain-specific `[Chain / L2]`
- Stablecoin supply (USDC/USDT/native breakdown) `[AUTO: DefiLlama stablecoins per chain]`
- Bridge inflow/outflow (net flow direction) `[SEMI-AUTO: DefiLlama bridges; net = inflow - outflow]`
- DEX volume on chain `[AUTO: DefiLlama DEX volume]`
- Protocol count `[AUTO: DefiLlama protocols filter by chain]`
- Validator count / Nakamoto coefficient `[MANUAL: chain-specific interpretation]`
- Outage / reorg history `[MANUAL: chain status pages, post-mortems]`

> ↳ Cap check: Rule 4 (L2 trust assumption), Rule 1 (any core on-chain metric with <3 independent sources → cap MEDIUM), Rule 2 (pre-mainnet → usage/traction not bullish evidence). See Front Matter §C.

### 5.3 Payment chain–specific `[Payment chain]`

> GUIDANCE — 【关键：TVL 不是核心】支付链看流量与单笔经济性，不是锁仓。

- Stablecoin transfer volume & count `[SEMI-AUTO: Etherscan token transfers by contract]`
- Average transaction size (retail vs institutional) `[SEMI-AUTO: total_value / tx_count; split is MANUAL]`
- Median fee `[SEMI-AUTO: Etherscan; median gas-fee USD over window]`
- Finality time `[MANUAL: protocol spec lookup]`
- Failed transaction rate `[SEMI-AUTO: failed_tx / total_tx]`
- On/off-ramp partners `[MANUAL: project docs]`
- Merchant / fintech / bank adoption `[MANUAL: announcements; not on-chain]`
- Cross-border corridors `[MANUAL: business data]`
- Non-speculative usage share `[MANUAL: heuristics + judgment]`
- ⭐ **Transaction Volume / TVL ratio** — more meaningful than TVL itself `[SEMI-AUTO: Etherscan volume / DefiLlama TVL]`

### 5.4 DeFi protocol–specific `[DeFi]`
- Utilization rate (lending) `[SEMI-AUTO: borrowed / supplied]`
- Liquidation volume & bad debt `[SEMI-AUTO + MANUAL interpretation]`
- Open Interest (perp) `[AUTO: DefiLlama derivatives]`
- Slippage / liquidity depth (DEX) `[MANUAL: pool-depth simulation]`
- Insurance fund `[MANUAL: protocol fund address]`
- Depositors / borrowers count `[MANUAL: Dune (TD-024) or Etherscan event-log aggregation]`
- Real yield vs subsidized yield `[SEMI-AUTO: fee_revenue/TVL vs emission_value/TVL]`

### 5.5 Stablecoin module `[Stablecoin]`

> GUIDANCE: 与 5.1/5.2 并列、可叠加。每个子节先给核心分析问题（你要读出什么判断），再列打标签的 metric。填的时候先回答问题，metric 是支撑论据，不是终点。

#### ⭐⭐ KEY SIGNAL — Supply Momentum: organic vs mechanical

> GUIDANCE — 这是稳定币分析里信噪比最高的单一信号，单独提出来强调。
> 逻辑同构于技术分析的**量价配合 / 背离**：
> - **配合（organic / 真实需求）**：supply 增长 **AND** holder count 增长 **AND** 真实 usage（转账/支付/DeFi 抵押）增长 — 三者同向，是健康的、可持续的需求扩张。
> - **背离（mechanical / 可疑）**：supply 暴涨 **BUT** holder 数走平、且新增供应集中在一两个合约地址或单一协议的流动性挖矿池 — 这是 incentive farming / 单一巨鲸，不是真实采用，随激励结束会迅速回流。
> **填表强制项**：每次研究稳定币（或某条链上的稳定币供应变化）都必须明确判定本期是 CONFIRMATION 还是 DIVERGENCE，并说明依据。这个判定直接喂给 Part 7.2（real demand vs farming filter）。

| Verdict | Supply trend | Holder trend | Usage trend | Read |
|---------|--------------|--------------|-------------|------|
| ☐ CONFIRMATION | ↑ | ↑ | ↑ | Genuine demand expansion |
| ☐ DIVERGENCE | ↑ | → / ↓ | → / ↓ | Watch farming / whale; mark low confidence |
| ☐ CONTRACTION | ↓ | ↓ | ↓ | Capital leaving; investigate cause (regulation / depeg / migration) |

> ↳ Cap check: Rule 3 (Front Matter §C) — a DIVERGENCE verdict forces the "mechanical growth risk" downgrade.
> ↳ Consumed by → §7.2 (real-demand vs incentive-farming filter) · §8 Path C (growth-quality input to issuer valuation) · §9.5 (thesis-breaker triggers) · §11.2 (track list).

#### A. Supply & Distribution Dynamics

> GUIDANCE — 核心分析问题：供应量的变化方向和速度，就是稳定币唯一的需求信号。普通 token 需求通过价格表达；稳定币价格钉在 $1，需求只能通过供应增减表达。永远先看 net change 的 slope，不是绝对值。

- Total supply / mint / burn / net flow `[AUTO: DefiLlama stablecoins]`
- Per-chain supply breakdown (which ecosystems are pulling growth) `[AUTO: DefiLlama stablecoins by chain]`
- Native vs bridged supply (native = issuer's active strategic bet; bridged = passive reach) `[SEMI-AUTO: DefiLlama + issuer docs]`
- Net 7d / 30d supply change `[SEMI-AUTO: DefiLlama historical]`
- Mint/redemption velocity (large mints often lead institutional onboarding or market moves) `[SEMI-AUTO: Etherscan event logs on issuance contract]`

> ↳ Cap check: Rule 3 (DIVERGENCE → "mechanical growth risk"), Rule 1 (supply core data <3 sources → cap MEDIUM). See Front Matter §C.

#### B. Holder Structure

> GUIDANCE — 核心分析问题：这枚稳定币到底是"交易筹码"还是"钱"？CEX/DeFi/EOA 三分揭示真实用途——高 CEX=交易结算抵押；高合约=DeFi 抵押赚息；高 EOA+P2P=真实支付/持有（Tron-USDT 特征）。
> TRAP: 交易所 hot wallet 的大额持仓是托管 artifact，不是"机构信仰"，需 labeling 区分。

- Top 10 / 100 holder concentration `[AUTO: Etherscan/Alchemy token holders]`
- CEX vs DeFi (contract) vs EOA split `[SEMI-AUTO: Etherscan + address labeling]`
- Holder count growth (grassroots vs whale-driven) `[AUTO: Etherscan]`

#### C. Peg Stability & Market Microstructure

> GUIDANCE — 核心分析问题：它有没有做好唯一的工作——锚定 $1？看深度 vs 时长：短暂 ±0.3% 波动正常；持续大幅脱锚是存亡级（参考 2023.3 USDC-SVB 跌到 $0.87）。恢复时间比最大偏离更反映市场信心。
> TRAP: 脱锚归因要分层——USDC-SVB 是 banking partner 问题（D 节），不是机制问题。别混为一谈。

- Historical depeg events (depth + recovery time) `[MANUAL: incident research]`
- Current price vs $1 `[AUTO: CoinGecko/CMC]`
- CEX depth ±0.5% bid/ask `[MANUAL: orderbook data, not in B.1]`
- Main DEX pool liquidity (Curve 3pool balance = real-time peg dashboard) `[SEMI-AUTO: DefiLlama yields/pools]`
- Cross-stablecoin swap volume (USDC↔USDT flow reveals preference shifts) `[SEMI-AUTO]`

#### D. Reserve & Backing ⭐ stablecoin-only

> GUIDANCE — 核心分析问题：这是一道信用分析题——backing 有多扎实？本质是对一个类货币市场基金做信用尽调。
> Redemption stress / run resilience 的核心分析问题：它能不能扛住一次赎回挤兑？Reserve ratio 是静态的"够不够"，run resilience 是动态的"快不快、扛不扛得住同时赎回"。下面 redemption 几项才是脱锚事件真正的引爆点。
> TRAP: 储备充足 ≠ 没风险。单一银行集中 + 久期错配照样出事——看 resilience，不只看 ratio。redemption stress 子块就是把这句话量化：100% 储备但只有 5% 是瞬时可变现、且 90% 久期错配，则一次中等规模挤兑就足以触发脱锚。

- Reserve composition (cash / T-bills / repo / commercial paper; shorter duration = higher credit = safer) `[MANUAL: monthly attestation PDF]`
- Attestation cadence + note attestation ≠ audit `[MANUAL: issuer disclosure]`
- Auditor (Big Four vs small firm = trust gradient) `[MANUAL]`
- Reserve duration & yield (both a risk and a revenue engine) `[SEMI-AUTO: T-bill rate × composition]`
- Banking partners & concentration (the SVB lesson: single-bank exposure = existential risk) `[MANUAL]`

*Redemption stress / run resilience:*
- 1-day / 7-day redemption capacity `[MANUAL: attestation PDF]`
- Cash + overnight-repo share of reserves (the instantly-liquid portion) `[MANUAL: attestation PDF]`
- T-bill maturity ladder (duration mismatch = run risk: short-term redemption pressure vs long-duration bonds) `[MANUAL: attestation PDF]`
- Banking-partner concentration (the SVB lesson: money parked at one bank — if the bank fails, the stablecoin fails) `[MANUAL: attestation PDF]`

#### E. Issuer Economics ⭐ stablecoin-only

> GUIDANCE — 核心分析问题：这是一门 float 生意——吃储备收益、对利率高度敏感。supply × reserve yield 决定毛收入。$60B × ~5% ≈ $3B/yr，高利率环境暴利。
> TRAP: 别用 crypto 的 FDV/P-S 套 stablecoin issuer。它更像受监管金融公司，用 enterprise value / 可资本化 reserve income 估（见 Part 8 Path C）。

- Revenue model = supply × reserve yield `[SEMI-AUTO: supply × avg T-bill yield]`
- Distribution partner revenue share (Circle gives ~50% of USDC reserve income to Coinbase — the most critical cost line and a strategic dependency) `[MANUAL: contract disclosures]`
- Interest-rate sensitivity stress test — 3-scenario table `[SEMI-AUTO: supply × yield scenario]`:

| Scenario | Fed / T-bill yield | Supply assumption | Gross reserve income | Revenue-share cost | Est. operating margin |
|----------|--------------------|--------------------|----------------------|--------------------|------------------------|
| Bear | 2%   | declining |  |  |  |
| Base | 3.5% | stable    |  |  |  |
| Bull | 5%   | growing   |  |  |  |

> GUIDANCE: 这张表把 issuer 定性为一家对利率敏感的金融公司（收入随 Fed 路径摆动），而非一个 crypto narrative——直接喂给 Part 8 Path C 的 enterprise-value 估值。

- Issuer valuation `[AUTO if listed: SEC EDGAR for Circle (CIK 0001876042)]`
- Profitability / runway `[AUTO if listed: 10-Q]`

#### F. Regulatory Posture

> GUIDANCE — 核心分析问题：监管地位既是护城河也是存亡风险——而且对不同客户是相反的卖点。
> TRAP: 同一特性（可冻结/KYC/持牌）对 institutional 加分、对 crypto-native 减分。先定 audience（Output Type）再判断正负。

- Licenses held (NYDFS Trust Charter / EMI / MAS = institutional access) `[MANUAL: issuer site]`
- GENIUS Act / MiCA status (MiCA has already forced USDT off some European exchanges) `[MANUAL]`
- Freeze / blacklist capability (institutions **want** it for compliance; DeFi purists **hate** it) `[MANUAL: protocol design]`
- Restricted jurisdictions `[MANUAL]`

#### G. Cross-chain Mechanics

> GUIDANCE — 核心分析问题：跨链触达是分发网络，机制决定脆弱性。native(CCTP) 最安全；bridged/wrapped 引入桥风险且可能与 native 脱锚。

- Chains supported via CCTP / native `[MANUAL: issuer docs]`
- Daily cross-chain volume `[SEMI-AUTO: DefiLlama bridges]`
- Top corridors `[SEMI-AUTO]`
- Acceptance: which chains treat it as the primary quote/collateral asset (becoming the default unit of account = very deep network effects) `[MANUAL]`

#### H. Real-world Use Cases

> GUIDANCE — 核心分析问题：是"crypto 交易筹码"还是"真正的钱"？这是终局判断，也是最易被 narrative 夸大、最需去噪的一节。
> TRAP: 本节几乎全 [MANUAL]，且大量"payment adoption"数字混了交易所搬砖。在 Evidence Table 诚实标低 confidence。

- Payment volume (de-noise bot/MEV) `[MANUAL: Visa Onchain Analytics and other external sources]`
- Remittance corridors `[MANUAL]`
- B2B settlement adoption `[MANUAL]`
- Treasury management (companies holding stablecoins as a cash equivalent) `[MANUAL]`

---

## Part 6 — Competitive Landscape `[Both, essential]`

### 6.1 Comparable selection

> GUIDANCE: 列 3–7 个真正可比的竞品。不要拿 stablecoin chain 比 general-purpose L1 的 TVL — 错误对比比没有对比更糟。

### 6.2 Comparison matrix

**For chain (general):**

| Chain | Backer | Core Use Case | Native Asset | Target Users | Key Advantage | Key Risk | Stage |
|-------|--------|---------------|--------------|--------------|--------------|----------|-------|

**For payment / stablecoin chain:**

| Chain | Stablecoin Focus | Compliance Posture | Finality | Distribution Edge | EVM Compatible | Status |
|-------|------------------|--------------------|----------|--------------------|----------------|--------|

**For DeFi protocol:**

| Protocol | Chain | TVL | Volume | Fees | Revenue | Token Capture | Main Risk |
|----------|-------|-----|--------|------|---------|---------------|-----------|

**For stablecoin:**

| Stablecoin | Backing Model | Reserve Composition | Attestation (cadence/auditor) | Freeze Capability | Native Chain Support | Distribution Partners | Regulatory Posture |
|------------|---------------|---------------------|-------------------------------|-------------------|----------------------|------------------------|---------------------|

### 6.3 Differentiation analysis
The real moat (distribution / liquidity / compliance / tech / network effect); which "differentiators" are superficial; whether the gap to #2/#3 is qualitative or quantitative.

---

## Part 7 — Critical Filters `[Both — this section determines report quality]`

### 7.1 Narrative vs Data mismatch check
Strong narrative, weak data → speculative / early. Strong data, low attention → underrated. Both strong / both weak → state your position explicitly.

### 7.2 Real demand vs Incentive farming
For every usage metric ask: are users here for an airdrop/points? Is TVL mercenary capital? Is volume wash trading? Are fees subsidized? Are stablecoin transfers real payments or CEX shuffling? Bots vs humans in DAU?

> GUIDANCE — ⭐ Stablecoin 研究：本节直接吃 Part 5.5 KEY SIGNAL 的 CONFIRMATION/DIVERGENCE 判定结论。

### 7.3 Token value capture ≠ Project quality
Is protocol revenue shared with holders? Is the token governance-only? Is staking real yield or pure emission? Unlock pressure over the next 12 months? Is FDV already pricing in future growth? (Not applicable to stablecoins — value is in the issuer, not the token.)

### 7.4 Centralization & dependency check
Reliant on a single team / multisig? Reliant on the parent for distribution (Arc→Circle / Base→Coinbase / Tempo→Stripe) — what happens if the parent changes strategy? Where is the single point of failure (sequencer / oracle / bridge / DA / banking partner)?

### 7.5 Distribution vs Technology check `[required for payment/infra/stablecoin]`
Does it win on better technology or stronger distribution? After the tech is copied, can distribution still form a moat? If distribution is strong but developers don't show up, does it become an empty chain?

> GUIDANCE: Arc：Circle 的 USDC 分发能否转化为链上 ecosystem？ Tempo：Stripe merchant network 能否转化为 crypto volume？ Base：Coinbase 入口能否转化为 on-chain retention？

---

## Part 8 — Valuation / Strategic Value

> GUIDANCE: 按 subject 选对应 Path（可叠加判断，但三条互不替代）。

### Path A — For token-bearing assets (crypto-native asset / token-bearing protocol)
FDV / Annualized Revenue · MC / Fees (P/E equivalent) · unlock-adjusted valuation · relative vs comparables · Bull/Base/Bear quantified ranges.

### Path B — For no-token infrastructure (Arc / Tempo / private infra)
Who captures value? · strategic value to parent (Arc→Circle / Tempo→Stripe) · indirect beneficiaries (public tokens or protocols that benefit indirectly) · potential monetization model · comparable business models (Visa/Stripe/SWIFT/Tron as USDT rail).

### Path C — For stablecoin issuers

> GUIDANCE: 不估 token 价格（永远 ~$1），估的是发行方这门 float 生意。

- Issuer enterprise value (based on reserve-income capitalization: annualized reserve income × applicable multiple)
- Market-share trajectory (by supply growth rate vs peers, combined with the Part 5.5 KEY SIGNAL verdict on growth quality)
- Strategic moat (distribution + regulatory + integration stacked together)
- Interest-rate scenario sensitivity (issuer revenue range under different Fed paths)
- Comparables: Circle (public market cap / SEC filings), Tether (rumored valuation, back-solved via supply×yield×margin), PayPal stablecoin business unit, traditional money-market-fund managers.

---

## Part 9 — Catalysts & Risks `[Both]`

### 9.1 Catalysts (3–12 months)

| Catalyst | Expected Timing | Impact Direction | Likelihood |
|----------|-----------------|------------------|------------|

> GUIDANCE: 可能：mainnet launch / fee switch / token unlock cliff / 新链 expansion / institutional product / regulatory clarification / 重要 integration / governance proposal / airdrop。Stablecoin 专属：新链 native 发行 / 大型 fintech 集成 / 监管牌照获批 / 储备透明度升级 / 大额机构 mint。

### 9.2 Risk matrix

| Risk Type | Specific Risk | Observable trigger / magnitude | Likelihood | Impact |
|-----------|--------------|--------------------------------|------------|--------|
| Market | | | | |
| Execution | | | | |
| Smart Contract | | | | |
| Regulatory | | | | |
| Centralization | | | | |
| Liquidity / Peg | | | | |
| Competitive | | | | |
| Token (unlock / inflation) | | | | |
| Ecosystem concentration | | | | |
| Reserve / Banking (stablecoin) | | | | |
| Interest-rate (stablecoin issuer) | | | | |

> GUIDANCE (R5): "Observable trigger / magnitude" 列填**这个风险正在兑现的具体可观测信号 + 量级**（例：30d 净流出 > $2B / 单一银行敞口 > 储备 30% / depeg 恢复 > 72h），不是泛泛的"如果出事"。命中的触发器应与 §9.5 thesis-breakers 对齐。

---

## Part 9.5 — Bull / Bear / Thesis-Breaker `[Both]`

> GUIDANCE: Bull/Bear 不是情绪，是把 §1.1 thesis 拆成"什么观察会**证实**它 / 什么观察会**证伪**它"。Thesis-breakers 必须是**可观测、有阈值、能被 §11.2 track list 监控**的触发器，不是泛泛的"如果监管变差"。每条 bull/bear 都绑定到一个会显示它的 metric。

### 9.5.1 Bull case — what would confirm the thesis
The concrete, observable developments that would validate the §1.1 thesis, each tied to the metric that would show it (e.g. supply slope re-accelerating **with** holder-count growth → organic demand confirmed via §5.5; a reserve-transparency / attestation upgrade; a major chain adopting it as the primary quote/collateral asset).

### 9.5.2 Bear case — what would break it
The developments that would falsify the §1.1 thesis, each tied to the metric that would show it (e.g. sustained supply contraction; supply-share loss to a competing issuer; a banking-partner or regulatory shock; peg instability that recovers slowly).

### 9.5.3 Thesis-breakers — explicit observable triggers
Pre-commit to the triggers that flip the Position. Each is a **binary, observable** condition (not a vibe); when one fires, return to §1.1 and re-test whether the thesis still holds, then update §11.1 Position and §11.2 track list.

- [ ] **Supply slope:** 30d supply slope turns negative for 2 consecutive months
- [ ] **KEY SIGNAL:** §5.5 reads DIVERGENCE on 2 consecutive readings
  > ↳ Cap check: Rule 3 (Front Matter §C) — a confirmed DIVERGENCE forces the "mechanical growth risk" downgrade.
- [ ] **Peg recovery:** a depeg event takes **>72h** to recover to peg
- [ ] **Attestation lapse:** a scheduled reserve attestation is missed or late
- [ ] **Single point of failure realized:** a sequencer / bridge / banking-partner failure actually occurs

> GUIDANCE: 这些触发器直接喂 §11.2 track list（作为监控项）和 §11.1 conviction（命中即下调）。命中 thesis-breaker ≠ "扣分"，而是"回到 §1.1 重新检验论点是否还成立"。与 §9.2 risk matrix 的 "Observable trigger / magnitude" 列保持一致。

---

## Part 10 — Second-Order Effects `[Mode B emphasis; Mode A optional]`

Who wins and who loses under success/failure · indirect beneficiaries · regulatory/policy knock-on · narrative-layer impact (does it catalyze a new narrative?) · cross-sector transmission (DeFi→CEX / RWA→traditional finance / payment→banks).

---

## Part 11 — Conclusion `[Both]`

### 11.1 Position
☐ Bullish ☐ Neutral ☐ Bearish — one-sentence rationale.

- **Conviction = f(evidence):** conviction is bound by (a) §1.5 Data Availability, (b) any active Front Matter §C confidence caps, and (c) the §9.5 thesis-breaker status (how many triggers are live) — the stated Position may not claim more conviction than these three jointly support.

> ↳ Cap check: before writing the Position, run the Confidence Downgrade Rules (Front Matter §C); if any hard rule fires, cap confidence at its ceiling and note which rule (e.g. "core metric has only 2 sources → conclusion capped at MEDIUM, Rule 1").

### 11.2 Track list
KPIs to keep monitoring (1/2/3). For a stablecoin, include at minimum: net supply slope, CONFIRMATION/DIVERGENCE state, peg deviation, reserve-disclosure updates.

---

## Part 12 — Required Charts & Data `[Both]`

> GUIDANCE: 目标 5–8 张图，按 subject 可用性挑，不为补图而补图。

### Universal (if data exists)
- [ ] Time series: TVL / active addresses / fees / revenue (6–12mo)
- [ ] Competitive comparison table (see 6.2)
- [ ] Ecosystem / stakeholder map
- [ ] Timeline of major events (incl. future catalysts)

### Token-related (only if token exists)
- [ ] Token allocation pie · Unlock schedule timeline · FDV vs MC over time · Emissions vs revenue

### Payment chain–specific
- [ ] Stablecoin supply by chain · transfer volume by chain · Transaction Volume/TVL ratio · USDC vs USDT share · native vs bridged · corridor map

### DeFi protocol–specific
- [ ] TVL market share · Revenue market share · price vs revenue · incentives vs organic fees · retention cohort · P/S vs comparables

### Stablecoin-specific
- [ ] ⭐ Supply momentum overlay: supply + holder count + usage three-line overlay (directly visualizes CONFIRMATION vs DIVERGENCE)
- [ ] Per-chain supply distribution (stacked area, 12mo)
- [ ] Supply net change (7d/30d bar)
- [ ] Reserve composition pie
- [ ] Holder concentration (top N curve)
- [ ] Peg deviation history
- [ ] vs competitors supply market share
- [ ] CCTP / cross-chain volume Sankey

### News-driven–specific
- [ ] Event timeline · Bridge/cross-chain flow Sankey · Affected ecosystem map (winners/losers)

---

## Part 13 — Appendix `[Both]`
References & sources · Methodology notes (data range / calculation method / assumptions) · Disclaimer (required for external / institutional) · Open questions / items for follow-up research.

---

# BACK MATTER — operating & process material (not part of the deliverable)

## Data Acquisition Workflow `[process, not a report section]`

Wires raw data from the Stack Anamnesis fetchers (B.1) into the template.

### Step 1: Identify required fetchers by subject_type

| Subject Type | Required Fetchers | Notes |
|--------------|-------------------|-------|
| **Chain (L1)** | DefiLlama, CoinGecko, Etherscan, Alchemy RPC | + CoinMarketCap price cross-check |
| **Chain (L2)** | DefiLlama, L2Beat, CoinGecko, Alchemy RPC, Etherscan | L2Beat = TVS + stage + risks |
| **DeFi Protocol** | DefiLlama, Etherscan, CoinGecko | Etherscan for contract analysis |
| **Crypto-native asset** | CoinGecko, CoinMarketCap, Etherscan, Alchemy RPC | Alchemy for live totalSupply; CMC cross-check |
| **Stablecoin** | DefiLlama (stablecoins endpoint), Etherscan (holder + transfer events), Alchemy (live totalSupply across chains), SEC EDGAR (if issuer listed), CoinGecko (peg price) | Reserve attestation = MANUAL PDF; CEX orderbook depth not in B.1 |
| **Payment Chain** | DefiLlama, Alchemy RPC, Etherscan, L2Beat (if L2) | Custom analysis via Dune deferred (TD-024) |
| **News Reaction** | All applicable per central subject | Time window may include 7d for post-event immediate data |

### Step 2: Invoke each fetcher
```bash
python3 tools/fetchers/<source>_fetch.py \
  --subject <subject> --subject-type <subject_type> --freshness-window <window>
```
- `<source>` ∈ {defillama, coingecko, etherscan, sec_edgar, alchemy, coinmarketcap, l2beat}
- Block-explorer types (Etherscan/Alchemy) use the contract address (USDC = `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`); SEC EDGAR uses the issuer name (Circle)
- `<window>` ∈ {7d, 30d, 90d, quarter, 1 year, since_TGE}
- SEC EDGAR additionally needs `--sec-email <research-email>` (process-memory only, never persisted, I-003 invariant).

### Step 3: Raw envelopes land in `meta/raw/<source>/`
6-key envelope: `subject / subject_type / freshness_window / endpoint / fetched_at / raw_response`.
Path: `meta/raw/<source>/<subject_slug>_<utc_compressed>.json`. `meta/raw/*` is gitignored.

### Step 4: Analysis layer reads envelopes → fills the template
The current B.1→B.2 handoff is **manual**: `ls -la meta/raw/*/` → for each section open the relevant envelope and sync the data → use the [AUTO]/[SEMI-AUTO]/[MANUAL] tags to prioritize automation order.

### Step 5: Return to Part 12
Once raw data is in hand, charts / Evidence Table references / Quality Self-Check proceed normally.

### Data sources

**Active in Stack Anamnesis B.1:**

| Source | Use | Registry § |
|--------|-----|-----------|
| DefiLlama | TVL, fees, stablecoins, cross-chain volume | §1 |
| CoinGecko | Price, market cap, 24h volume | §4 |
| Etherscan | Tx, contract verification, holder counts | §3 |
| SEC EDGAR | 10-K/10-Q for listed issuers (Circle, Coinbase, MARA) | §6 |
| Alchemy RPC | Raw chain state (live totalSupply, balance, contract reads) | §5 |
| CoinMarketCap | Price + MC cross-check | §13 |
| L2Beat | L2 TVS, stage, risk indicators | §12 |

**Deferred / Archived** (key stored but fetcher not built; do not include in the workflow until the corresponding TD unblocks): Artemis (pending student plan) · Dune (TD-024) · Messari (TD-025) · Token Terminal / Allium / Nansen (TD-021, paid) · Electric Capital (backlog).

> GUIDANCE: Active 7 覆盖约 80% 典型 stablecoin/fintech 研究需求；剩余 20%（dev activity、深度自定义链上分析、cross-chain 统一指标、wallet 行为）目前需手动研究或 TD unblock。

---

## Quality Self-Check (run before shipping)

1. ☐ Is the thesis clearly stated within the first ~150 words?
2. ☐ Does the competitor matrix pick **genuinely comparable** subjects, not a generic "L1"/"DeFi"/"stablecoin"?
3. ☐ Did I distinguish "usage" vs "incentive-driven usage"? (Stablecoin: did I make the CONFIRMATION/DIVERGENCE call?)
4. ☐ Did I distinguish "good project" vs "good token"? (No token → use Path B; stablecoin → use Path C, don't force an FDV.)
5. ☐ Does every non-trivial claim in the Evidence Table have a source?
6. ☐ Is the Data Availability label honest (don't write Weak as Medium)?
7. ☐ Stablecoin-specific: are reserve/banking concentration risk and interest-rate sensitivity both in the Part 9 risk matrix?
8. ☐ **Confidence Downgrade Rules (Front Matter §C):** did I check all four hard rules one by one? Where triggered, is confidence capped at the ceiling and noted in the Evidence Table + Conclusion? (three-source / pre-mainnet / stablecoin mechanical-growth / L2 trust-assumption)
9. ☐ Can an institutional reader finish and answer "is this worth my capital / time?"

All yes → ship. Any no → go back and fill.

---

## Changelog (moved from top of document — M1)

> v1.4 changelog: 新增 Part 1.6 Confidence Downgrade Rules（HARD 上限规则，非建议；治理 Part 11 Conclusion + Quality Self-Check，B.3 QC/red-team 层将以代码强制执行）· Part 5.1/5.2/5.5 末尾加 "Confidence downgrade triggers" 指针 · Part 5.5 D 加 "Redemption stress / run resilience" 子块 · Part 5.5 E 把利率敏感性正式做成 3-scenario 表

> v1.3 changelog: subject_type 拆分 Asset/Token → Stablecoin + Crypto-native asset · Part 4.2 加 "For Stablecoin" 机制分支 · 新增 Part 5.5 Stablecoin module（与 5.1/5.2 并列，可叠加，每个子节自带分析问题）· ⭐ 新增 Supply Signal callout（organic vs mechanical，量价配合 vs 背离）· Part 6.2 加 Stablecoin 对比表 · Part 8 加 Path C（stablecoin issuer 估值）· Part 12 加 Stablecoin 图表组 · Part 11.5 fetcher 表加 Stablecoin 行

> v1.2 changelog: 移除 Sector/Thematic（暂延 Phase C）· 移除 Audience 字段（改为 Output Type 派生）· Mode 自动检测 · Part 11.5 数据获取 workflow · Part 5 metrics 加 [AUTO]/[SEMI-AUTO]/[MANUAL] 标签

> v1.1 changelog: Mode B 重排（先 news 后 thesis）· Output Type · 七层框架双版本 · Evidence Table · Data Availability · Distribution vs Technology filter · Valuation 拆分 · 个人品牌内容剥离到文末 workshop 区

> v2 (DRAFT) reorg: M1 changelog 下沉 · M2 Confidence Downgrade Rules 升到 front matter（§C）、各 section 留一行 ↳ Cap check 指针、补 4.2 For-chain Rule 4 指针 · M3 数据获取 workflow 下沉到 back matter · M4 "branch-by-subject" 统一为 "For X:" 风格（含 Part 8 Path A/B/C）· M5 GUIDANCE/TRAP 通道把写作指导与报告正文物理分开 · 语言：正文+脚手架全英文，GUIDANCE/TRAP 保留中文。无 substance 增删。

> v2 (DRAFT) rigor pass R1–R5（crypto-native，无 DCF / P-E / Porter / equity 框架）：R1 新增 **Part 9.5 Bull / Bear / Thesis-Breaker**（置于 Part 9 与 Part 10 之间；5 个可观测 thesis-breaker 触发器；DIVERGENCE 处带 Rule 3 cap 指针）· R2 **Part 11.1** 加 "Conviction = f(evidence)" 绑定行（§1.5 Data Availability / §C caps / §9.5 thesis-breaker status）· R3 **§5.5 KEY SIGNAL** 加 "Consumed by →" 传播指针（§7.2 / §8 Path C / §9.5 / §11.2）· R4 **§1.4 Evidence Table** 加 "Disconfirming evidence sought" 列 · R5 **§9.2 risk matrix** 加 "Observable trigger / magnitude" 列。本 pass 新增分析脚手架，未触碰任何 number 或 metric-annotation 标记。

---
---

# 🔻 Below is the personal workshop area — **NOT part of the report deliverable** 🔻

---

## YYFoundry Content Workshop `[Personal brand; not part of the delivered research]`

> GUIDANCE: 研究做完后单独问，决定是否产出公开内容。

**Content packaging**: 能否拆成文章/视频/推文 thread？哪个 channel（Substack 长文 / X thread / YouTube / 中文双语）？读者画像（crypto-native vs traditional finance）？

**"From Atoms to Bits" narrative hook**: 有没有能追溯到物理层的钩点（能源、芯片、地理、监管）？这是差异化核心。例：研究 USDC → 钩点可能是 Circle 储备里美债的久期策略 + banking partner 的物理金融基础设施。

**Visual asset planning**: 是否值得做产业链图 / 七层栈图 / Sankey / supply momentum 三线叠加图？能否复用 YYFoundry 视觉识别（monospace + metal texture + electric blue）？是否做成可独立传播单图（X 引流回长文）？

**Series potential**: 能否扩展成 mini-series？与现有 pipeline 衔接（Top 30 L1 whitepaper / Bitcoin Starts with Sand）？

**Bilingual angle**: 中文版受众特殊视角（监管、出海、中文用户对 payment chain / stablecoin 的实际需求）？中→英编辑流程是否走通？
