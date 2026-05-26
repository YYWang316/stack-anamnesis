# Crypto Research Report Template
**YYFoundry / NYU Blockchain Lab — Research SOP v1.2**

> v1.2 changelog: 移除 Sector/Thematic subject type（暂延 Phase C）· 
> 移除 Audience 字段（改为 Output Type 派生）· 
> Output Type 表加 Audience 列 + workshop/language 说明 · 
> Mode A/B 描述澄清自动检测 · 加 Asset/Token subject type · 
> Sources表 sync with B.1 ship (improvement #1) · 
> 加 Part 11.5 Data acquisition workflow (improvement #2) · 
> Part 5 metrics 加 [AUTO]/[SEMI-AUTO]/[MANUAL] tags (improvement #3)

> v1.1 changelog: Mode B重排（先news后thesis） · Output Type · 七层框架双版本（YYFoundry原版 + crypto-fintech mapping） · Evidence Table · Data Availability · Distribution vs Technology filter · Valuation拆分（有token / 无token） · Charts按token可用性分组 · 个人品牌内容剥离到文末workshop区

---

## 使用说明 / How to Use

两种模式共享主框架，**进入顺序不同**：

**Mode A — Subject-Driven**（研究具体 chain/protocol/asset，prompt 不含明显新闻触发词）
`Part 0 → 1 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 11 → 12 → 13`

**Mode B — News-Driven**（由新闻/事件触发的研究，prompt 含 "react to..."/"X 刚刚..."/"newsflash" 等关键词）
`Part 0 → 2 → 1 → 3 → 4(if needed) → 5(if applicable) → 6 → 7 → 9 → 10 → 11 → 12 → 13`

> 关键区别：Mode B 先讲 what happened（Part 2），再抽象成 thesis（Part 1）。否则读者还没搞清新闻是什么，就被thesis劈头盖脸砸过去。
> Mode 由 agent 从 prompt 自动检测，不需要 user 显式选择。
> Mode × Scope 是两个独立维度：Mode B × single（针对一个新闻主体研究）
> 完全支持；Mode B × sector（新闻引发的 sector 横评）暂时延期，参见 TD-002。

每个section标注 `[Both]` / `[Mode A]` / `[Mode B]` 说明适用范围。

---

## Part 0 — Meta `[Both]`

- **Title**:
- **Subject Type**: ☐ Chain ☐ L2/Rollup ☐ DeFi Protocol ☐ News Reaction ☐ Asset/Token
> Sector/Thematic 类暂不支持，参见 references/TODO.md TD-002。
> 如果你的研究跨多 subject，请拆成多次 single run 后手工合成，
> 或等 Phase C 开放 sector pipeline。
- **Date**:
- **Time Horizon**: ☐ Tactical (<3mo)  ☐ Strategic (3–12mo)  ☐ Structural (>12mo)
- **Audience**: ☐ Internal note ☐ Public post ☐ Lab research ☐ Institutional pitch / BD

### Output Type & Depth `[NEW v1.1]`
选定output类型决定哪些section必填、哪些可省略：

| Output Type | Length | Must-have sections | Tone & Audience |
|-------------|--------|---------------------|------------------|
| Quick Take | ~500 words | 1.1, 1.2, 3, 6.2, 11.1 | Punchy, opinion-led / self + crypto-fluent reader |
| Public Post | ~1,500 words | 1, 3, 4 (light), 6, 7, 11 | Narrative + data balanced / YYFoundry public reader |
| Deep Dive | 3,000–5,000 | 全部 | Comprehensive / sophisticated outside reader |
| Investment Memo | 2,000–3,000 | 1, 4.1, 4.3, 7, 8, 9 | Valuation & catalyst heavy / institutional capital allocator |
| BD / Partnership Brief | 1,500–2,500 | 1.1, 3, 4.4, 6, 7.5, 10 | Market pain + who pays / potential partner or employer |
| Academic Research Note | 5,000+ | 全部 + methodology强化 | Citation-heavy, hedged / academic peer |

**Workshop add-on**: 任何 output type 都可以勾选 +workshop 选项，
会额外生成一份 workshop.html（YYFoundry 品牌内容策划工作台，
不属于 deliverable）。详见模板末尾 personal workshop 区域。

**Language**: 任何 output type 都可以选 en / zh / both。
both 模式会并行产出两份独立 HTML（不是双语对照）。
---

## Part 1 — Thesis & Framing `[Both]`

### 1.1 One-sentence thesis
回答：你最核心的判断是什么？不写"X是一个L1"，写"X是Y在Z方向的尝试，关键看W"。

> Example: *Arc is Circle's attempt to build a stablecoin-native settlement layer. The core question is whether dedicated payment L1s can capture transaction volume from general-purpose chains.*

### 1.2 Five-question framework
每篇report都必须能回答这5个问题：

1. **Why this?** — 为什么这个项目/事件值得研究？
2. **Why now?** — 为什么现在是关键时间点？
3. **Why will users / capital care?** — 真实需求在哪？
4. **Why will value accrue?** — 价值如何被捕获（token / equity / ecosystem）？
5. **What can go wrong?** — 最大的失败路径是什么？

### 1.3 Industry stack positioning
有两种框架可选，按subject选择更解释力的版本（或同时用）：

**Option A — "From Atoms to Bits" 物理→数字栈**（适合矿业/硬件/能源/L1 infrastructure）

| Layer | Description | Example |
|-------|-------------|---------|
| L0 | Energy / Materials | hydro, gas, quartz |
| L1 | Semiconductor / ASIC | TSMC, Bitmain |
| L2 | Mining / Validators | MARA, Riot, validator sets |
| L3 | Consensus / Protocol | Bitcoin, Ethereum, Solana |
| L4 | Settlement / Bridge | rollups, CCTP, bridges |
| L5 | Application / DeFi | Aave, Uniswap |
| L6 | Consumer / Interface | wallets, exchanges |

**Option B — Crypto-Fintech 金融基础设施栈**（适合stablecoin chain / payment / RWA / institutional infra）

| Layer | Description | Example |
|-------|-------------|---------|
| L0 | Regulatory / Banking Interface | licenses, KYC/AML, banking partners |
| L1 | Asset Issuance / Liquidity | USDC, USDT, PYUSD, M^0 |
| L2 | Settlement Infrastructure | Ethereum, Solana, **Arc, Tempo** |
| L3 | Execution / Routing / Bridge | L2s, CCTP, routers |
| L4 | Financial Primitives | DEX, lending, perps, RWA |
| L5 | Application Workflows | checkout, payout, remittance, payroll |
| L6 | Distribution / Interface | wallets, fintech apps, exchanges, merchants |

**填写要求**：
- Primary layer:
- 依赖哪几层:
- 挑战/想取代哪几层:

> 示例（Arc, Option B）: Arc 不只是一条chain。它是Circle从 **L1 (Asset Issuance) 向 L2 (Settlement) 甚至 L4-L5 (Workflows)** 的纵向整合，目标是把USDC从 "asset" 升级到 "rails"。

### 1.4 Evidence Table `[NEW v1.1]`
所有非trivial的claim都要列入这张表。这是report和opinion piece的分水岭：

| # | Claim | Evidence | Source | Confidence |
|---|-------|----------|--------|------------|
| 1 | | | | H/M/L |
| 2 | | | | H/M/L |
| 3 | | | | H/M/L |

> 例：
> | 1 | Arc targets institutional stablecoin settlement | Official Circle announcement | Circle blog | High |
> | 2 | TVL is secondary metric for payment chains | Stablecoin transfer data shows Tron has high volume / low TVL | Artemis, Dune | Medium |
> | 3 | Ecosystem adoption still early | Protocol count <X, devs <Y | DeFiLlama, Electric Capital | Medium |

### 1.5 Data Availability `[NEW v1.1]`
明确标注数据成熟度，避免被narrative带飞：

☐ **Strong** — multiple public dashboards, 6–12 months data
☐ **Medium** — partial data, some assumptions required
☐ **Weak** — early-stage, mostly narrative / official claims

- 缺什么数据:
- 做了哪些假设:

若Weak，开篇加一句免责：*"This report is based on early-stage data. Current conclusions should be treated as preliminary until [mainnet usage / volume / dev activity] become observable."*

---

## Part 2 — News Hook `[Mode B only — comes BEFORE Part 1]`

### 2.1 What happened
一段事实陈述：时间、actor、事件、相关数字。

### 2.2 Immediate reaction
- 价格反应（相关tokens）:
- 链上反应（如有）:
- 媒体 / KOL反应:
- 同类项目联动:

### 2.3 Why this isn't just noise
它揭示了什么趋势？为什么值得展开成一篇research，而不是一条推文？

---

## Part 3 — Sector Background `[Both]`

### 3.1 赛道归类
不要泛泛归类（Arc不是"L1"，是"stablecoin-native settlement layer"）：

> L1 / L2 / Stablecoin chain / Payment infra / DEX / Perp DEX / Lending / CDP / Restaking / RWA / DePIN / Consumer / Wallet & AA / Bridge / Oracle / Data

### 3.2 Sector size & trends
- 市场规模（TVL / volume / user base）
- 增长率 & 资金流向
- 主要驱动力
- 主要逆风

### 3.3 为什么现在重要
监管节点（GENIUS Act / MiCA）？技术成熟？市场结构变化？资金rotation？

---

## Part 4 — Subject Deep Dive `[Mode A primary; Mode B if news has a central subject]`

### 4.1 Project fundamentals
- 团队 & 关键人物背景
- 融资历史 & 投资方（哪些VC、几轮、valuation）
- 当前阶段（whitepaper / devnet / testnet / mainnet）
- **血统效应**：母公司/创始人背景（Arc-Circle、Tempo-Stripe、Codex类尤其关键，影响distribution和BD能力）

### 4.2 Architecture / Mechanism

**For chain:**
- 共识机制
- Performance：TPS / finality / block time
- VM选型（EVM / Move / SVM / 自研）
- DA层方案
- Validator / Sequencer结构与去中心化程度
- 安全假设 & 升级机制

**For DeFi protocol:**
- 核心机制（AMM曲线 / 抵押-清算模型 / 资金费率）
- Oracle依赖
- 升级 / 治理路径
- 与底层chain的耦合程度

### 4.3 Tokenomics & Business Model
- Total / Circulating supply
- 分配比例（team / investors / community / treasury / foundation）
- Unlock schedule（cliff、vesting、未来12月解锁压力）
- 价值捕获路径：fee burn / buyback / staking yield / revenue share
- 收入模型：**谁付费？付给谁？token holder如何分到？**
- FDV vs MC缺口

> ⚠️ 如果subject没有token（Arc / Tempo / 私有infra），跳过本节，到 Part 8 "no token exists" 路径。

### 4.4 Ecosystem
- 原生应用数量与质量
- TVL / activity分布集中度（前3名占多少？）
- Grants & partner programs
- Developer activity（Electric Capital / Artemis数据）
- Wallet / infra / bridge support

---

## Part 5 — On-Chain Metrics `[Mode A required; Mode B if applicable]`

> **Metric annotations (NEW v1.2):**
> - `[AUTO: <source>]` — analysis layer reads field directly from envelope; no computation needed
> - `[SEMI-AUTO: <source> + <formula>]` — analysis layer computes via fixed formula or cross-source aggregation
> - `[MANUAL: <reason>]` — data unavailable in B.1 fetchers or requires human judgment; researcher fills manually
> See Part 11.5 for fetcher invocation and envelope shape; see `tools/fetchers/` for source modules.

### 5.1 通用指标
- TVL over time `[AUTO: DefiLlama historical TVL series]`
- Daily / Monthly Active Addresses `[AUTO: Etherscan stats; SEMI-AUTO if cross-chain aggregation needed]`
- Transactions (count & volume) `[AUTO: Etherscan; Alchemy for cross-validation]`
- Fees / Revenue `[AUTO: DefiLlama protocol fees endpoint]`
- User retention（cohort analysis） `[MANUAL: needs Dune (TD-024 deferred) or custom analysis on Etherscan tx history]`
- Token incentives占TVL的比例 `[SEMI-AUTO: DefiLlama emission data / DefiLlama TVL; ratio = emission_value_30d / current_tvl]`

### 5.2 Chain-specific
- Stablecoin supply（USDC / USDT / native breakdown） `[AUTO: DefiLlama stablecoins endpoint per chain]`
- Bridge inflow / outflow（net flow方向） `[SEMI-AUTO: DefiLlama bridges endpoint; net = inflow - outflow]`
- DEX volume on chain `[AUTO: DefiLlama DEX volume endpoint]`
- Protocol count `[AUTO: DefiLlama protocols filter by chain]`
- Validator count / Nakamoto coefficient `[MANUAL: chain-specific; Alchemy may surface validator set but Nakamoto coefficient is interpretation]`
- Outage / reorg history `[MANUAL: external sources (chain status pages, post-mortems); not in B.1 fetchers]`

### 5.3 Payment chain–specific 【关键：TVL不是核心】
对Arc / Tempo / Plasma / Codex这类，重点看：

- Stablecoin transfer volume & count `[SEMI-AUTO: Etherscan token transfers; aggregate by USDC contract address]`
- Average transaction size（retail vs institutional） `[SEMI-AUTO: Etherscan, avg = total_value / tx_count; retail vs institutional split is MANUAL]`
- Median fee `[SEMI-AUTO: Etherscan tx list; compute median of gas-fee USD over window]`
- Finality time `[MANUAL: chain protocol spec (not in fetchers); ~12 seconds Ethereum, ~2 seconds Solana — document by lookup]`
- Failed transaction rate `[SEMI-AUTO: Etherscan; failed_tx / total_tx]`
- On / off-ramp partners `[MANUAL: project documentation / web research; not in B.1 fetchers]`
- Merchant / fintech / bank adoption `[MANUAL: web research / project announcements; not quantifiable from on-chain data]`
- Cross-border corridors `[MANUAL: project-specific business data; requires HIFI / Stripe / Circle equivalents not in B.1]`
- Non-speculative usage share `[MANUAL: interpretation — distinguishing payment from speculation requires heuristics + judgment]`
- ⭐ **Transaction Volume / TVL ratio** — 比TVL本身有意义，payment chain不需要大量资产长期锁仓 `[SEMI-AUTO: Etherscan volume / DefiLlama TVL; cross-source ratio]`

### 5.4 DeFi protocol–specific
- Utilization rate（lending） `[SEMI-AUTO: DefiLlama protocol detail; utilization = borrowed / supplied]`
- Liquidation volume & bad debt（lending） `[SEMI-AUTO: DefiLlama liquidations endpoint; bad debt = MANUAL interpretation]`
- Open Interest（perp） `[AUTO: DefiLlama derivatives endpoint per protocol]`
- Slippage / liquidity depth（DEX） `[MANUAL: slippage requires pool-depth simulation; not directly in B.1 fetchers]`
- Insurance fund（perp / lending） `[MANUAL: protocol-specific fund address; read via Alchemy if address known, else project docs]`
- Depositors / borrowers count `[MANUAL: unique-address counts need Dune (TD-024 deferred) or Etherscan event-log aggregation]`
- Real yield vs subsidized yield `[SEMI-AUTO: DefiLlama fees + emissions; real = fee_revenue / TVL vs subsidized = emission_value / TVL]`

---

## Part 6 — Competitive Landscape `[Both, essential]`

### 6.1 Comparable selection
列出3–7个**真正可比**的竞品。**不要拿stablecoin chain去比general-purpose L1的TVL** — 错误的对比比没有对比更糟。

### 6.2 Comparison matrix
按subject type选table结构：

**Chain (general):**

| Chain | Backer | Core Use Case | Native Asset | Target Users | Key Advantage | Key Risk | Stage |
|-------|--------|---------------|--------------|--------------|--------------|----------|-------|

**Payment / stablecoin chain:**

| Chain | Stablecoin Focus | Compliance Posture | Finality | Distribution Edge | EVM Compatible | Status |
|-------|------------------|--------------------|----------|--------------------|----------------|--------|

**DeFi protocol:**

| Protocol | Chain | TVL | Volume | Fees | Revenue | Token Capture | Main Risk |
|----------|-------|-----|--------|------|---------|---------------|-----------|

### 6.3 Differentiation analysis
- 真正的moat在哪？（distribution / liquidity / compliance / tech / network effect）
- 哪些"差异化"其实是表面的？
- 与第二/三名比较，是qualitative差异还是quantitative差异？

---

## Part 7 — Critical Filters `[Both — 这一节决定report质量]`

### 7.1 Narrative vs Data 错位检查
- Narrative强但数据弱？→ 投机/早期
- 数据强但media attention低？→ underrated opportunity
- 都强 / 都弱？→ 写明立场

### 7.2 Real demand vs Incentive farming
对每个使用量指标问一遍：

- 用户是不是为了空投/积分？
- TVL是不是mercenary capital？
- Volume是不是wash trading？
- Fees是不是emission补贴出来的？
- Stablecoin transfer是真支付还是CEX套利搬砖？
- DAU里bot vs human占比？

### 7.3 Token value capture ≠ Project quality
区分"项目好"和"token好"：

- Protocol revenue是否分给holders？
- Token是否仅governance（no economic claim）？
- Staking yield是real yield还是pure emission？
- Unlock pressure在未来12月有多大？
- 当前FDV是否已经price in了未来增长？
- Token需求来自真实使用还是投机？

### 7.4 Centralization & dependency check
- 依赖single team / multisig控制？
- 依赖母公司分发（Arc→Circle / Base→Coinbase / Tempo→Stripe）？母公司如果改变策略会怎样？
- 单点故障在哪（sequencer / oracle / bridge / DA layer）？

### 7.5 Distribution vs Technology check `[NEW v1.1 — payment/infra项目必填]`
- 它赢是因为**技术更好**，还是**distribution更强**？
- 如果技术被复制，distribution还能形成moat吗？
- 如果distribution很强但开发者不来，会不会变成"空链"？

> 具体追问（payment chain）：
> - Arc：Circle的USDC分发能否转化为链上ecosystem？
> - Tempo：Stripe的merchant network能否转化为crypto transaction volume？
> - Base：Coinbase用户入口能否转化为on-chain retention？

---

## Part 8 — Valuation / Strategic Value `[updated v1.1]`

### Path A — If token exists
- FDV / Annualized Revenue
- MC / Fees（P/E equivalent）
- Unlock-adjusted valuation（按未来12月解锁压力折扣）
- Relative valuation vs comparables
- Bull / Base / Bear scenario（给出量化区间）

### Path B — If no token exists `[NEW v1.1]`
没有可交易token不代表不能valuation，只是换一套框架：

- **谁捕获价值？** 母公司股权 / ecosystem / future token?
- **Strategic value to parent**：Arc之于Circle / Tempo之于Stripe / Base之于Coinbase
- **Indirect beneficiaries**：哪些公开token或protocol会间接受益？（如Arc → USDC velocity增加 → 与CCTP深度集成的L2受益）
- **Potential monetization model**：sequencer revenue / future token / equity story / SaaS layer
- **Comparable business models**：Visa / Stripe / SWIFT / Tron (as USDT settlement rail)

> 示例（Arc无token时）：Arc的价值可能不直接体现在Arc token上，而是体现在Circle对USDC settlement、developer ecosystem、institutional stablecoin workflow的控制力增强 — 这反过来支撑Circle作为公司的估值（已上市），并间接利好与CCTP深度集成的项目。

---

## Part 9 — Catalysts & Risks `[Both]`

### 9.1 Catalysts (3–12 months)

| Catalyst | Expected Timing | Impact Direction | Likelihood |
|----------|-----------------|------------------|------------|

可能catalyst：mainnet launch / fee switch / token unlock cliff / 新chain expansion / institutional product launch / regulatory clarification / 重要integration / governance proposal / airdrop event。

### 9.2 Risk matrix

| Risk Type | Specific Risk | Likelihood | Impact |
|-----------|--------------|------------|--------|
| Market | | | |
| Execution | | | |
| Smart Contract | | | |
| Regulatory | | | |
| Centralization | | | |
| Liquidity | | | |
| Competitive | | | |
| Token (unlock / inflation) | | | |
| Ecosystem concentration | | | |

---

## Part 10 — Second-Order Effects `[Mode B emphasis; Mode A optional]`

新闻型research必须有这一节：

- 成功 / 失败下，谁是赢家？谁是输家？
- 间接受益者（infra / 上下游 / 被压制的竞品）
- 监管 / 政策连锁反应
- 叙事层面影响（catalyze一个new narrative？）
- 跨sector传导（DeFi → CEX / RWA → 传统金融 / payment → 银行）

---

## Part 11 — Conclusion `[Both]`

### 11.1 Position
☐ Bullish  ☐ Neutral  ☐ Bearish — 一句话理由

### 11.2 Track list
未来需要持续监控的KPI：

1.
2.
3.

---

## Part 11.5 — Data acquisition workflow `[Both, NEW v1.2]`

How to get raw data into the workflow before filling template sections. 
This bridges Stack Anamnesis fetchers (B.1 ship) with template fill.

### Step 1: Identify required fetchers by subject_type

| Subject Type | Required Fetchers | Notes |
|--------------|-------------------|-------|
| **Chain (L1)** | DefiLlama, CoinGecko, Etherscan, Alchemy RPC | Add CoinMarketCap for price cross-check |
| **Chain (L2)** | DefiLlama, L2Beat, CoinGecko, Alchemy RPC, Etherscan | L2Beat = TVS + stage + risks |
| **DeFi Protocol** | DefiLlama, Etherscan, CoinGecko | Etherscan for contract analysis |
| **Asset / Token** | CoinGecko, CoinMarketCap, Etherscan, Alchemy RPC | Alchemy for live `totalSupply`; CMC as cross-check |
| **Stablecoin Issuer** | All 7 (esp. SEC EDGAR if listed) | Circle = CIK 0001876042; Tether = not listed; PYUSD via PayPal listings |
| **Payment Chain** | DefiLlama, Alchemy RPC, Etherscan, L2Beat (if L2) | Custom analytics via Dune deferred (TD-024) |
| **News Reaction** | All applicable per the central subject | Time-window may include 7d for immediate post-event data |

### Step 2: Invoke each fetcher

Standard pattern (one fetcher at a time):

```bash
python3 tools/fetchers/<source>_fetch.py \
  --subject <subject> \
  --subject-type <subject_type> \
  --freshness-window <window>
```

**Where**:
- `<source>` ∈ `{defillama, coingecko, etherscan, sec_edgar, alchemy, coinmarketcap, l2beat}`
- `<subject>` — the canonical name (e.g. `USDC`, `Bitcoin`, `Arbitrum`); for chain-explorer fetchers (Etherscan, Alchemy) use the contract address (`0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` for USDC); for SEC EDGAR use the issuer name (`Circle`)
- `<subject_type>` ∈ `{stablecoin_issuer, orchestrator, wallet, chain, agentic_payment_layer}` (per `references/subject_taxonomy.md`)
- `<window>` ∈ `{7d, 30d, 90d, quarter, 1 year, since_TGE}` (per registry contract)

**SEC EDGAR adds a required flag** (when invoking):
```bash
python3 tools/fetchers/sec_edgar_fetch.py \
  --subject Circle --subject-type stablecoin_issuer --freshness-window 30d \
  --sec-email <your-research-email>
```

The email is process-memory only, never persisted (I-003 invariant; see `MEMORY.md` Privacy invariants).

### Step 3: Raw envelopes land at `meta/raw/<source>/`

Every fetcher writes a single JSON file with the 6-key envelope shape:

```json
{
  "subject": "<subject>",
  "subject_type": "<subject_type>",
  "freshness_window": "<window>",
  "endpoint": "<canonical URL where the data was fetched from>",
  "fetched_at": "<UTC ISO 8601 timestamp>",
  "raw_response": { /* verbatim API response, possibly nested by sub-call */ }
}
```

**File path pattern**:
````
meta/raw/<source>/<subject_slug>_<utc_compressed>.json
````

**Examples**:
- `meta/raw/defillama/usdc_20260526T143052Z.json`
- `meta/raw/sec_edgar/circle_cik0001876042_20260526T143415Z.json`
- `meta/raw/alchemy/0xa0b86991_chaineth_20260526T143521Z.json`

**Gitignored**: `meta/raw/*` is excluded from version control (raw data is time-sensitive, may be large, and not source code). Only `meta/raw/.gitkeep` is committed to preserve the empty directory structure.

### Step 4: Analysis layer reads envelopes → fills template fields

> **B.2 future**: An analysis layer (planned, not yet built) will read the latest envelope per source for a given subject, extract template-relevant fields, and produce a draft report. For now, this is **manual**: the researcher (or Claude Code agent) reads `meta/raw/<source>/<subject>_*.json` files and fills template sections by hand.

**Manual workflow (current B.1 → B.2 transition)**:
1. After fetchers complete, list outputs: `ls -la meta/raw/*/`
2. For each `Part 1`-`Part 11` section in this template, open the relevant envelope(s) and copy/synthesize the needed data
3. Use the `[AUTO]` / `[SEMI-AUTO]` / `[MANUAL]` tags (added in improvement #3, next turn) to prioritize which sections analysis layer should automate first

### Step 5: After fill — return to template Part 12

With raw data in hand, the rest of the template (charts, data sources cited in Evidence Table, Quality Self-Check) proceeds normally.

---

## Part 12 — Required Charts & Data `[Both, updated v1.1]`

**目标：5–8张图。按subject可用性挑选**，不要为补图而补图。

### Universal (if data exists)
- [ ] Time series：TVL / active addresses / fees / revenue（6–12个月）
- [ ] Competitive comparison table（见 Part 6.2）
- [ ] Ecosystem / stakeholder map
- [ ] Timeline of major events（含未来catalyst）

### Token-related (only if token exists) `[updated v1.1]`
- [ ] Token allocation pie chart
- [ ] Unlock schedule timeline
- [ ] FDV vs MC over time
- [ ] Emissions vs revenue（叠加图）

### Payment chain specific
- [ ] Stablecoin supply by chain
- [ ] Stablecoin transfer volume by chain
- [ ] Transaction Volume / TVL ratio comparison
- [ ] USDC vs USDT share
- [ ] Native vs bridged stablecoin supply
- [ ] Geographic corridor map（remittance / B2B flow）

### DeFi protocol specific
- [ ] TVL market share among competitors
- [ ] Revenue market share
- [ ] Token price vs protocol revenue
- [ ] Incentives vs organic fees（叠加图）
- [ ] User retention cohort heatmap
- [ ] P/S or FDV/Revenue vs comparables

### News-driven specific
- [ ] Event timeline（前置事件 → 当前 → 预期catalyst）
- [ ] Bridge / cross-chain flow Sankey（资金迁移）
- [ ] Affected ecosystem map（winners/losers）

### Data sources

**Active in Stack Anamnesis B.1** (fetchers shipped, ready to use):

| Source | Use | Registry § |
|--------|-----|-----------|
| DefiLlama | TVL, fees, stablecoins, cross-chain volume | §1 |
| CoinGecko | Price, market cap, 24h volume (primary aggregator) | §4 |
| Etherscan | Chain transactions, contract verification, holder counts | §3 |
| SEC EDGAR | 10-K / 10-Q filings for listed issuers (Circle, Coinbase, MARA, etc.) | §6 |
| Alchemy RPC | Raw chain state (live `totalSupply`, balance, contract reads) | §5 |
| CoinMarketCap | Price + market cap cross-check (sanity vs CoinGecko) | §13 |
| L2Beat | Layer-2 ecosystem TVS, stage classification, risk indicators | §12 |

**Deferred / Archived** (key already stored but fetcher not built):

| Source | Status | Why |
|--------|--------|-----|
| Artemis | Pending student plan | Cross-chain unified metrics — email Artemis sales pending |
| Dune | Deferred (TD-024) | SQL execution engine — query_id discovery friction breaks automation |
| Messari | Deferred (TD-025) | Free-tier entitlement narrowed to BTC+ETH only in 2026 |
| Token Terminal | Archived (TD-021) | Paid tier required for institutional metrics |
| Allium / Nansen | Archived (TD-021) | Paid tier required for wallet behavior + whale data |
| Electric Capital | Backlog | Developer-activity ecosystem health — fetcher not yet built (GitHub-clone pattern, not API) |

> **For deferred/archived sources**: do not include in research workflows 
> until the corresponding TD unblocks. The active 7 cover ~80% of typical 
> stablecoin/fintech research needs; the remaining 20% (developer activity, 
> deep custom on-chain analytics, cross-chain unified metrics, wallet 
> behavior) currently requires manual research or a TD unblock.

---

## Part 13 — Appendix `[Both]`

- References & sources（链接、报告、whitepaper）
- Methodology notes（数据范围、计算方式、假设）
- Disclaimer（对外发表 / institutional use时必填）
- Open questions / 待后续research项

---

## Quality Self-Check（产出前过一遍）

1. ☐ 我的thesis是否在前150字内就清楚表达？
2. ☐ 竞品对比表是否选了**真正可比**对象，而不是泛泛"L1"或"DeFi"？
3. ☐ 我是否区分了"使用量"vs "incentive-driven使用量"？
4. ☐ 我是否区分了"项目好"vs "token好"？（无token项目：是否用了Path B valuation？）
5. ☐ Evidence Table里所有非trivial claim是否都有source？
6. ☐ Data Availability标注是否诚实（不要把Weak写成Medium）？
7. ☐ 一个institutional reader读完，能否回答"这值得我投入资金/时间吗？"

7个全yes，可以发；任一no，回去补。

---
---

# 🔻 以下为personal workshop区域，**不属于report deliverable** 🔻

---

## YYFoundry Content Workshop `[Personal brand, 不放进交付的research]`

研究做完之后，单独问自己这几个问题，决定是否产出公开内容：

### Content packaging
- 是否可以拆成一篇文章 / 一集视频 / 一条推文thread？
- 适合哪个channel：Substack长文 / X thread / YouTube视频 / 中文双语版？
- 预估读者画像：crypto-native vs traditional finance audience？

### "From Atoms to Bits" narrative hook
- 这个subject有没有可以追溯到**物理层**的钩点（能源、芯片、地理、监管）？
- 这是YYFoundry内容的差异化核心 — 大部分crypto媒体不会去讲quartz、ASIC、hydropower这些
- 例：研究Arc → 钩点可能是Circle的银行牌照矩阵 + USDC backing reserve的固定收益策略

### Visual asset planning
- 是否值得制作产业链图 / 七层栈图 / Sankey / corridor map？
- 这些图能否复用到YYFoundry的视觉识别（monospace + metal texture + electric blue）？
- 是否需要做成可独立传播的单图（X上单独发，引流回长文）？

### Series potential
- 这个subject是否可以扩展成一个mini-series？
- 与现有内容pipeline的衔接（Top 30 L1 whitepaper / Bitcoin Starts with Sand / ...）

### Bilingual angle
- 中文版受众有什么特殊视角？（监管、出海、中文用户对payment chain的实际需求）
- 中→英编辑流程是否走通？
