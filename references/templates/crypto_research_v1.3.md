# Crypto Research Report Template
**YYFoundry / NYU Blockchain Lab — Research SOP v1.4**
 
> v1.4 changelog: 新增 Part 1.6 Confidence Downgrade Rules（HARD 上限规则，非建议；治理 Part 11 Conclusion + Quality Self-Check，B.3 QC/red-team 层将以代码强制执行）· Part 5.1/5.2/5.5 末尾加 "Confidence downgrade triggers" 指针 · Part 5.5 D 加 "Redemption stress / run resilience" 子块 · Part 5.5 E 把利率敏感性正式做成 3-scenario 表
>
> v1.3 changelog: subject_type 拆分 Asset/Token → Stablecoin + Crypto-native asset · Part 4.2 加 "For Stablecoin" 机制分支 · 新增 Part 5.5 Stablecoin module（与 5.1/5.2 并列，可叠加，每个子节自带分析问题）· ⭐ 新增 Supply Signal callout（organic vs mechanical，量价配合 vs 背离）· Part 6.2 加 Stablecoin 对比表 · Part 8 加 Path C（stablecoin issuer 估值）· Part 12 加 Stablecoin 图表组 · Part 11.5 fetcher 表加 Stablecoin 行
>
> v1.2 changelog: 移除 Sector/Thematic（暂延 Phase C）· 移除 Audience 字段（改为 Output Type 派生）· Mode 自动检测 · Part 11.5 数据获取 workflow · Part 5 metrics 加 [AUTO]/[SEMI-AUTO]/[MANUAL] 标签
>
> v1.1 changelog: Mode B 重排（先 news 后 thesis）· Output Type · 七层框架双版本 · Evidence Table · Data Availability · Distribution vs Technology filter · Valuation 拆分 · 个人品牌内容剥离到文末 workshop 区
 
---
 
## 使用说明 / How to Use
 
两种模式共享主框架，**进入顺序不同**：
 
**Mode A — Subject-Driven**（研究具体 chain/protocol/asset，prompt 不含明显新闻触发词）
`Part 0 → 1 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 11 → 12 → 13`
 
**Mode B — News-Driven**（由新闻/事件触发，prompt 含 "react to…"/"X 刚刚…"/"newsflash" 等关键词）
`Part 0 → 2 → 1 → 3 → 4(if needed) → 5(if applicable) → 6 → 7 → 9 → 10 → 11 → 12 → 13`
 
> Mode B 先讲 what happened（Part 2），再抽象成 thesis（Part 1）。Mode 由 agent 从 prompt 自动检测，user 不需显式选择。
> Mode × Scope 两个独立维度：Mode B × single 完全支持；Mode B × sector（新闻引发的横评）暂延，见 TD-002。
 
**Module 叠加原则（v1.3 重要）**：Part 5 的各 metrics module 是**可叠加、非互斥**的。研究 USDC → 只填 5.5，链指标段（5.1/5.2）正确留空。研究 Arc（发自己稳定币的 payment chain）→ 同时填 5.1/5.2（看链）+ 5.3（看支付）+ 5.5（看链上 native 稳定币）。
 
每个 section 标注 `[Both]` / `[Mode A]` / `[Mode B]`。
 
---
 
## Part 0 — Meta `[Both]`
 
- **Title**:
- **Subject Type**:
  - ☐ Chain  ☐ L2/Rollup  ☐ DeFi Protocol  ☐ News Reaction
  - ☐ **Asset/Token**（v1.3 拆两类，研究维度差异极大，必须二选一）：
    - ☐ **Stablecoin**（USDC, USDT, PYUSD, DAI, M^0）→ 走 Part 5.5 + Path C
    - ☐ **Crypto-native asset**（BTC, ETH, SOL, governance tokens）→ 走 Part 4.3 tokenomics + Path A
> Sector/Thematic 类暂不支持，见 references/TODO.md TD-002。跨多 subject 请拆成多次 single run 后手工合成。
 
- **Date**:
- **Time Horizon**: ☐ Tactical (<3mo)  ☐ Strategic (3–12mo)  ☐ Structural (>12mo)
### Output Type & Depth
选定 output 类型决定哪些 section 必填、哪些可省略：
 
| Output Type | Length | Must-have sections | Tone & Audience |
|-------------|--------|---------------------|------------------|
| Quick Take | ~500 words | 1.1, 1.2, 3, 6.2, 11.1 | Punchy, opinion-led / self + crypto-fluent reader |
| Public Post | ~1,500 words | 1, 3, 4 (light), 6, 7, 11 | Narrative + data balanced / YYFoundry public reader |
| Deep Dive | 3,000–5,000 | 全部 | Comprehensive / sophisticated outside reader |
| Investment Memo | 2,000–3,000 | 1, 4.1, 4.3, 7, 8, 9 | Valuation & catalyst heavy / institutional capital allocator |
| BD / Partnership Brief | 1,500–2,500 | 1.1, 3, 4.4, 6, 7.5, 10 | Market pain + who pays / potential partner or employer |
| Academic Research Note | 5,000+ | 全部 + methodology 强化 | Citation-heavy, hedged / academic peer |
 
**Workshop add-on**: 任何 output type 可勾选 +workshop，额外生成 YYFoundry 品牌内容策划工作台（不属于 deliverable，见文末）。
**Language**: 任何 output type 可选 en / zh / both。both 模式并行产出两份独立稿（非双语对照）。
 
---
 
## Part 1 — Thesis & Framing `[Both]`
 
### 1.1 One-sentence thesis
不写 "X 是一个 L1"，写 "X 是 Y 在 Z 方向的尝试，关键看 W"。
 
> Example: *Arc is Circle's attempt to build a stablecoin-native settlement layer. The core question is whether dedicated payment L1s can capture transaction volume from general-purpose chains.*
 
### 1.2 Five-question framework
1. **Why this?** — 为什么值得研究？
2. **Why now?** — 为什么现在是关键时间点？
3. **Why will users / capital care?** — 真实需求在哪？
4. **Why will value accrue?** — 价值如何被捕获（token / equity / ecosystem）？
5. **What can go wrong?** — 最大的失败路径是什么？
### 1.3 Industry stack positioning
按 subject 选更有解释力的版本（或同时用）：
 
**Option A — "From Atoms to Bits" 物理→数字栈**（矿业/硬件/能源/L1 infra）
 
| Layer | Description | Example |
|-------|-------------|---------|
| L0 | Energy / Materials | hydro, gas, quartz |
| L1 | Semiconductor / ASIC | TSMC, Bitmain |
| L2 | Mining / Validators | MARA, Riot, validator sets |
| L3 | Consensus / Protocol | Bitcoin, Ethereum, Solana |
| L4 | Settlement / Bridge | rollups, CCTP, bridges |
| L5 | Application / DeFi | Aave, Uniswap |
| L6 | Consumer / Interface | wallets, exchanges |
 
**Option B — Crypto-Fintech 金融基础设施栈**（stablecoin / payment / RWA / institutional infra）
 
| Layer | Description | Example |
|-------|-------------|---------|
| L0 | Regulatory / Banking Interface | licenses, KYC/AML, banking partners |
| L1 | Asset Issuance / Liquidity | USDC, USDT, PYUSD, M^0 |
| L2 | Settlement Infrastructure | Ethereum, Solana, **Arc, Tempo** |
| L3 | Execution / Routing / Bridge | L2s, CCTP, routers |
| L4 | Financial Primitives | DEX, lending, perps, RWA |
| L5 | Application Workflows | checkout, payout, remittance, payroll |
| L6 | Distribution / Interface | wallets, fintech apps, exchanges, merchants |
 
**填写**：Primary layer / 依赖哪几层 / 挑战或想取代哪几层。
 
> 示例（Arc, Option B）: Arc 不只是一条 chain。它是 Circle 从 **L1 (Asset Issuance) 向 L2 (Settlement) 甚至 L4-L5 (Workflows)** 的纵向整合，目标是把 USDC 从 "asset" 升级到 "rails"。
 
### 1.4 Evidence Table
所有非 trivial 的 claim 都列入。这是 report 和 opinion piece 的分水岭：
 
| # | Claim | Evidence | Source | Confidence |
|---|-------|----------|--------|------------|
| 1 | | | | H/M/L |
| 2 | | | | H/M/L |
 
### 1.5 Data Availability
☐ **Strong** — multiple public dashboards, 6–12 months data
☐ **Medium** — partial data, some assumptions required
☐ **Weak** — early-stage, mostly narrative / official claims
 
- 缺什么数据 / 做了哪些假设:
若 Weak，开篇加免责：*"This report is based on early-stage data. Current conclusions should be treated as preliminary until [mainnet usage / volume / dev activity] become observable."*
 
### 1.6 Confidence Downgrade Rules `[HARD rules — 非建议，是上限]`
以下是**强制规则**，不是 best-practice 建议。它们 **CAP**（封顶）报告结论可声称的 confidence，无论作者主观多有信心都不能突破。命中任一规则即按规则降级，并在 Part 1.4 Evidence Table 对应行与 Part 11 Conclusion 注明触发了哪条。
 
> **执行说明**：这些规则将由 **B.3 QC / red-team 层以代码强制执行**（自动扫描 report 触发条件并改写 confidence 上限）。在 B.3 落地前，它们是 report **必须人工遵守**的成文规则——Quality Self-Check 第 9 项即检查此点。
 
1. **三源规则**：某个**核心 metric**（直接支撑 thesis 或 Position 的 metric）的独立来源**少于 3 个** → 整篇结论 confidence **封顶为 MEDIUM**，不得声称 High。
2. **Pre-mainnet 规则**：subject **尚未上 mainnet**（仍在 whitepaper / devnet / testnet）→ usage / traction 数据**不得**作为 bullish evidence 使用。可描述设计意图，但任何"采用度/牵引力"论证在此阶段无效。
3. **Stablecoin mechanical-growth 规则**：supply **↑** 但 holder count **AND** real usage 同时走平/下降（即 Part 5.5 KEY SIGNAL 判定为 **DIVERGENCE**）→ **必须**将该增长降级标注为 **"mechanical growth risk"**，不得作为需求扩张的正面论据。（这是把 5.5 DIVERGENCE verdict 转成的硬上限。）
4. **L2 信任假设规则**：L2 **没有 fraud proof 或 validity proof**（或存在高 withdrawal / exit 风险）→ **不得**声称 "secured by Ethereum"。必须改为陈述**实际的信任假设**（例：依赖单一 sequencer 的诚实性 / 多签升级密钥 / 7 天挑战期内的活性假设）。
---
 
## Part 2 — News Hook `[Mode B only — comes BEFORE Part 1]`
 
### 2.1 What happened
事实陈述：时间、actor、事件、相关数字。
 
### 2.2 Immediate reaction
价格反应 / 链上反应 / 媒体·KOL反应 / 同类项目联动。
 
### 2.3 Why this isn't just noise
它揭示了什么趋势？为什么值得展开成 research 而不是一条推文？
 
---
 
## Part 3 — Sector Background `[Both]`
 
### 3.1 赛道归类
不要泛泛归类（Arc 不是 "L1"，是 "stablecoin-native settlement layer"）。
 
### 3.2 Sector size & trends
市场规模 / 增长率与资金流向 / 主要驱动力 / 主要逆风。
 
### 3.3 为什么现在重要
监管节点（GENIUS Act / MiCA）？技术成熟？市场结构变化？资金 rotation？
 
---
 
## Part 4 — Subject Deep Dive `[Mode A primary; Mode B if news has a central subject]`
 
### 4.1 Project fundamentals
- 团队 & 关键人物背景
- 融资历史 & 投资方（哪些 VC、几轮、valuation）
- 当前阶段（whitepaper / devnet / testnet / mainnet）
- **血统效应**：母公司/创始人背景（Arc-Circle、Tempo-Stripe、Codex 类尤其关键，影响 distribution 和 BD 能力）
### 4.2 Architecture / Mechanism
 
**For chain:** 共识机制 / TPS·finality·block time / VM 选型 / DA 层 / validator·sequencer 结构与去中心化 / 安全假设与升级机制。
 
**For DeFi protocol:** 核心机制（AMM 曲线 / 抵押-清算 / 资金费率）/ Oracle 依赖 / 升级治理路径 / 与底层 chain 耦合程度。
 
**For Stablecoin（v1.3 新增）:**
- Issuance mechanism（fiat-backed / crypto-backed / algorithmic / hybrid）
- Mint/redeem 流程（谁能直接 mint，min size，settlement window）
- Freeze/blacklist 能力 & 治理（中心化控制程度）
- Cross-chain mechanism（CCTP native burn-and-mint vs bridged vs wrapped）
- 主要 distribution partner（CEX / fintech / wallet integrations）
### 4.3 Tokenomics & Business Model `[Crypto-native asset / token-bearing protocol]`
Total/circulating supply / 分配比例 / unlock schedule / 价值捕获路径 / 收入模型（谁付费？付给谁？holder 如何分到？）/ FDV vs MC 缺口。
 
> ⚠️ Stablecoin 不走本节（没有投机性 tokenomics），走 Part 5.5 + Part 8 Path C。无 token 的 infra（Arc/Tempo）走 Part 8 Path B。
 
### 4.4 Ecosystem
原生应用数量与质量 / TVL·activity 集中度（前 3 名占多少）/ grants & partners / developer activity / wallet·infra·bridge support。
 
---
 
## Part 5 — On-Chain Metrics `[Mode A required; Mode B if applicable]`
 
> **Metric annotations:**
> - `[AUTO: <source>]` — analysis 层直接从 envelope 读字段，无需计算
> - `[SEMI-AUTO: <source> + <formula>]` — 通过固定公式或跨源聚合计算
> - `[MANUAL: <reason>]` — B.1 fetchers 不可得或需人工判断
> 见 Part 11.5 fetcher 调用与 envelope 形态。
 
### 5.1 通用指标 `[Chain / L2 / DeFi]`
- TVL over time `[AUTO: DefiLlama historical TVL series]`
- Daily / Monthly Active Addresses `[AUTO: Etherscan stats; SEMI-AUTO if cross-chain aggregation]`
- Transactions (count & volume) `[AUTO: Etherscan; Alchemy cross-validation]`
- Fees / Revenue `[AUTO: DefiLlama protocol fees endpoint]`
- User retention（cohort） `[MANUAL: needs Dune (TD-024) or custom Etherscan tx-history analysis]`
- Token incentives 占 TVL 比例 `[SEMI-AUTO: DefiLlama emission / TVL]`
### 5.2 Chain-specific `[Chain / L2]`
- Stablecoin supply（USDC/USDT/native breakdown） `[AUTO: DefiLlama stablecoins per chain]`
- Bridge inflow/outflow（net flow 方向） `[SEMI-AUTO: DefiLlama bridges; net = inflow - outflow]`
- DEX volume on chain `[AUTO: DefiLlama DEX volume]`
- Protocol count `[AUTO: DefiLlama protocols filter by chain]`
- Validator count / Nakamoto coefficient `[MANUAL: chain-specific interpretation]`
- Outage / reorg history `[MANUAL: chain status pages, post-mortems]`
> **Confidence downgrade triggers**（见 Part 1.6）：L2 无 fraud/validity proof 或高 exit 风险 → 不得声称 "secured by Ethereum"，须陈述实际信任假设（规则 4）；任一核心链上 metric 独立来源 < 3 → 结论封顶 MEDIUM（规则 1）；subject 未上 mainnet → usage/traction 不得作 bullish evidence（规则 2）。
 
### 5.3 Payment chain–specific 【关键：TVL 不是核心】`[Payment chain]`
- Stablecoin transfer volume & count `[SEMI-AUTO: Etherscan token transfers by contract]`
- Average transaction size（retail vs institutional） `[SEMI-AUTO: total_value / tx_count; split is MANUAL]`
- Median fee `[SEMI-AUTO: Etherscan; median gas-fee USD over window]`
- Finality time `[MANUAL: protocol spec lookup]`
- Failed transaction rate `[SEMI-AUTO: failed_tx / total_tx]`
- On/off-ramp partners `[MANUAL: project docs]`
- Merchant / fintech / bank adoption `[MANUAL: announcements; not on-chain]`
- Cross-border corridors `[MANUAL: business data]`
- Non-speculative usage share `[MANUAL: heuristics + judgment]`
- ⭐ **Transaction Volume / TVL ratio** — 比 TVL 本身有意义 `[SEMI-AUTO: Etherscan volume / DefiLlama TVL]`
### 5.4 DeFi protocol–specific `[DeFi]`
- Utilization rate（lending） `[SEMI-AUTO: borrowed / supplied]`
- Liquidation volume & bad debt `[SEMI-AUTO + MANUAL interpretation]`
- Open Interest（perp） `[AUTO: DefiLlama derivatives]`
- Slippage / liquidity depth（DEX） `[MANUAL: pool-depth simulation]`
- Insurance fund `[MANUAL: protocol fund address]`
- Depositors / borrowers count `[MANUAL: Dune (TD-024) or Etherscan event-log aggregation]`
- Real yield vs subsidized yield `[SEMI-AUTO: fee_revenue/TVL vs emission_value/TVL]`
---
 
### 5.5 Stablecoin module 【v1.3 新增 · 与 5.1/5.2 并列 · 可叠加】 `[Stablecoin]`
 
> 每个子节先给**核心分析问题**（你要读出什么判断），再列打标签的 metric。填的时候先回答问题，metric 是支撑论据，不是终点。
 
---
 
#### ⭐⭐ KEY SIGNAL — Supply Momentum：organic vs mechanical（量价配合 vs 背离）
 
> **这是稳定币分析里信噪比最高的单一信号，单独提出来强调。**
>
> 逻辑同构于技术分析的**量价配合 / 背离**：
> - **配合（organic / 真实需求）**：supply 增长 **AND** holder count 增长 **AND** 真实 usage（转账/支付/DeFi 抵押）增长 — 三者同向，是健康的、可持续的需求扩张。
> - **背离（mechanical / 可疑）**：supply 暴涨 **BUT** holder 数走平、且新增供应集中在一两个合约地址或单一协议的流动性挖矿池 — 这是 incentive farming / 单一巨鲸，不是真实采用，随激励结束会迅速回流。
>
> **填表强制项**：每次研究稳定币（或某条链上的稳定币供应变化）都必须明确判定本期是 **CONFIRMATION 还是 DIVERGENCE**，并说明依据。这个判定直接喂给 Part 7.2（real demand vs farming filter）。
>
> | 判定 | Supply trend | Holder trend | Usage trend | 结论 |
> |------|--------------|--------------|-------------|------|
> | ☐ CONFIRMATION | ↑ | ↑ | ↑ | 真实需求扩张 |
> | ☐ DIVERGENCE | ↑ | → / ↓ | → / ↓ | 警惕 farming / 巨鲸，标低 confidence |
> | ☐ CONTRACTION | ↓ | ↓ | ↓ | 资本离场，查原因（监管/脱锚/迁移） |
 
---
 
#### A. Supply & Distribution Dynamics
**核心分析问题：供应量的变化方向和速度，就是稳定币唯一的需求信号。** 普通 token 需求通过价格表达；稳定币价格钉在 $1，需求只能通过供应增减表达。永远先看 net change 的 slope，不是绝对值。
 
- Total supply / mint / burn / net flow `[AUTO: DefiLlama stablecoins]`
- Per-chain supply breakdown（哪些生态在拉动）`[AUTO: DefiLlama stablecoins by chain]`
- Native vs bridged supply（native = 发行方主动战略下注；bridged = 被动触达）`[SEMI-AUTO: DefiLlama + issuer docs]`
- Net 7d / 30d supply change `[SEMI-AUTO: DefiLlama historical]`
- Mint/redemption velocity（大额 mint 常领先 institutional onboarding 或市场异动）`[SEMI-AUTO: Etherscan event logs on issuance contract]`
> **Confidence downgrade triggers**（见 Part 1.6）：supply ↑ 但 holder count AND real usage 走平/下降（KEY SIGNAL = DIVERGENCE）→ 必须降级为 "mechanical growth risk"，不得作需求扩张正面论据（规则 3）；supply 核心数据独立来源 < 3 → 结论封顶 MEDIUM（规则 1）。
 
#### B. Holder Structure
**核心分析问题：这枚稳定币到底是"交易筹码"还是"钱"？** CEX/DeFi/EOA 三分揭示真实用途——高 CEX=交易结算抵押；高合约=DeFi 抵押赚息；高 EOA+P2P=真实支付/持有（Tron-USDT 特征）。
 
- Top 10 / 100 holder concentration `[AUTO: Etherscan/Alchemy token holders]`
- CEX vs DeFi(合约) vs EOA split `[SEMI-AUTO: Etherscan + address labeling]`
- Holder count growth（grassroots vs whale-driven） `[AUTO: Etherscan]`
> 陷阱：交易所 hot wallet 的大额持仓是托管 artifact，不是"机构信仰"，需 labeling 区分。
 
#### C. Peg Stability & Market Microstructure
**核心分析问题：它有没有做好唯一的工作——锚定 $1？** 看深度 vs 时长：短暂 ±0.3% 波动正常；持续大幅脱锚是存亡级（参考 2023.3 USDC-SVB 跌到 $0.87）。**恢复时间**比最大偏离更反映市场信心。
 
- Historical depeg events（深度 + 恢复时间）`[MANUAL: incident research]`
- Current price vs $1 `[AUTO: CoinGecko/CMC]`
- CEX depth ±0.5% bid/ask `[MANUAL: orderbook data, not in B.1]`
- Main DEX pool liquidity（Curve 3pool 余额 = 实时 peg 仪表盘）`[SEMI-AUTO: DefiLlama yields/pools]`
- 跨稳定币 swap volume（USDC↔USDT 流向揭示偏好转移）`[SEMI-AUTO]`
> 陷阱：脱锚归因要分层——USDC-SVB 是 banking partner 问题（D 节），不是机制问题。别混为一谈。
 
#### D. Reserve & Backing ⭐ 稳定币独有
**核心分析问题：这是一道信用分析题——backing 有多扎实？** 本质是对一个类货币市场基金做信用尽调。
 
- Reserve composition（cash / T-bills / repo / commercial paper；越短久期越高信用越安全）`[MANUAL: monthly attestation PDF]`
- Attestation cadence + 注意 attestation ≠ audit `[MANUAL: issuer disclosure]`
- Auditor（四大 vs 小所 = 信任梯度）`[MANUAL]`
- Reserve duration & yield（既是风险又是收入引擎）`[SEMI-AUTO: T-bill rate × composition]`
- Banking partners & 集中度（SVB 教训：单一银行敞口 = 存亡风险）`[MANUAL]`
**Redemption stress / run resilience** — 核心分析问题：**它能不能扛住一次赎回挤兑？** Reserve ratio 是静态的"够不够"，run resilience 是动态的"快不快、扛不扛得住同时赎回"。下面这几项才是脱锚事件真正的引爆点：
 
- 1-day / 7-day redemption capacity（即时与一周可兑付上限）`[MANUAL: attestation PDF]`
- Cash + overnight-repo share of reserves（瞬时可变现部分占比）`[MANUAL: attestation PDF]`
- T-bill maturity ladder（久期错配 = 挤兑风险：短期赎回压力 vs 长久期债券）`[MANUAL: attestation PDF]`
- Banking-partner concentration（the SVB lesson：钱压在一家银行，银行倒则稳定币倒）`[MANUAL: attestation PDF]`
> 陷阱：储备充足 ≠ 没风险。单一银行集中 + 久期错配照样出事——看 resilience，不只看 ratio。redemption stress 子块就是把这句话量化：100% 储备但只有 5% 是瞬时可变现、且 90% 久期错配，则一次中等规模挤兑就足以触发脱锚。
 
#### E. Issuer Economics ⭐ 稳定币独有
**核心分析问题：这是一门 float 生意——吃储备收益、对利率高度敏感。** supply × reserve yield 决定毛收入。$60B × ~5% ≈ $3B/yr，高利率环境暴利。
 
- Revenue model = supply × reserve yield `[SEMI-AUTO: supply × avg T-bill yield]`
- Distribution partner revenue share（Circle 把约 50% USDC 储备收入给 Coinbase — 最关键成本线兼战略依赖）`[MANUAL: contract disclosures]`
- 利率敏感性压力测试 — 3-scenario 表 `[SEMI-AUTO: supply × yield scenario]`：
| Scenario | Fed / T-bill yield | Supply assumption | Gross reserve income | Revenue-share cost | Est. operating margin |
|----------|--------------------|--------------------|----------------------|--------------------|------------------------|
| Bear | 2%   | declining |  |  |  |
| Base | 3.5% | stable    |  |  |  |
| Bull | 5%   | growing   |  |  |  |
 
> 这张表把 issuer 定性为一家**对利率敏感的金融公司**（收入随 Fed 路径摆动），而非一个 crypto narrative——直接喂给 Part 8 Path C 的 enterprise-value 估值。
 
- Issuer valuation `[AUTO if listed: SEC EDGAR for Circle (CIK 0001876042)]`
- Profitability / runway `[AUTO if listed: 10-Q]`
> 陷阱：别用 crypto 的 FDV/P-S 套 stablecoin issuer。它更像受监管金融公司，用 enterprise value / 可资本化 reserve income 估（见 Part 8 Path C）。
 
#### F. Regulatory Posture
**核心分析问题：监管地位既是护城河也是存亡风险——而且对不同客户是相反的卖点。**
 
- Licenses held（NYDFS Trust Charter / EMI / MAS = 机构准入）`[MANUAL: issuer site]`
- GENIUS Act / MiCA status（MiCA 已逼 USDT 从部分欧洲所下架）`[MANUAL]`
- Freeze / blacklist capability（机构**要**它合规，DeFi 纯粹主义者**恨**它）`[MANUAL: protocol design]`
- Restricted jurisdictions `[MANUAL]`
> 陷阱：同一特性（可冻结/KYC/持牌）对 institutional 加分、对 crypto-native 减分。先定 audience（Output Type）再判断正负。
 
#### G. Cross-chain Mechanics
**核心分析问题：跨链触达是分发网络，机制决定脆弱性。** native(CCTP) 最安全；bridged/wrapped 引入桥风险且可能与 native 脱锚。
 
- CCTP / native 支持的链 `[MANUAL: issuer docs]`
- Daily cross-chain volume `[SEMI-AUTO: DefiLlama bridges]`
- Top corridors `[SEMI-AUTO]`
- 接受度：哪些链把它当 primary quote/collateral asset（成为默认计价资产 = 极深网络效应）`[MANUAL]`
#### H. Real-world Use Cases
**核心分析问题：是"crypto 交易筹码"还是"真正的钱"？** 这是终局判断，也是最易被 narrative 夸大、最需去噪的一节。
 
- Payment volume（去 bot/MEV 噪）`[MANUAL: Visa Onchain Analytics 等外部源]`
- Remittance corridors `[MANUAL]`
- B2B settlement adoption `[MANUAL]`
- Treasury management（公司持稳定币当现金等价物）`[MANUAL]`
> 陷阱：本节几乎全 [MANUAL]，且大量"payment adoption"数字混了交易所搬砖。在 Evidence Table 诚实标低 confidence。
 
---
 
## Part 6 — Competitive Landscape `[Both, essential]`
 
### 6.1 Comparable selection
列 3–7 个**真正可比**的竞品。不要拿 stablecoin chain 比 general-purpose L1 的 TVL — 错误对比比没有对比更糟。
 
### 6.2 Comparison matrix
 
**Chain (general):**
 
| Chain | Backer | Core Use Case | Native Asset | Target Users | Key Advantage | Key Risk | Stage |
|-------|--------|---------------|--------------|--------------|--------------|----------|-------|
 
**Payment / stablecoin chain:**
 
| Chain | Stablecoin Focus | Compliance Posture | Finality | Distribution Edge | EVM Compatible | Status |
|-------|------------------|--------------------|----------|--------------------|----------------|--------|
 
**DeFi protocol:**
 
| Protocol | Chain | TVL | Volume | Fees | Revenue | Token Capture | Main Risk |
|----------|-------|-----|--------|------|---------|---------------|-----------|
 
**Stablecoin（v1.3 新增）:**
 
| Stablecoin | Backing Model | Reserve Composition | Attestation (cadence/auditor) | Freeze Capability | Native Chain Support | Distribution Partners | Regulatory Posture |
|------------|---------------|---------------------|-------------------------------|-------------------|----------------------|------------------------|---------------------|
 
### 6.3 Differentiation analysis
真正的 moat（distribution / liquidity / compliance / tech / network effect）；哪些"差异化"是表面的；与第二三名是 qualitative 还是 quantitative 差异。
 
---
 
## Part 7 — Critical Filters `[Both — 这一节决定 report 质量]`
 
### 7.1 Narrative vs Data 错位检查
Narrative 强数据弱→投机/早期；数据强 attention 低→underrated；都强/都弱→写明立场。
 
### 7.2 Real demand vs Incentive farming
对每个使用量指标问：用户是不是为空投/积分？TVL 是不是 mercenary capital？Volume 是不是 wash trading？Fees 是不是补贴出来的？Stablecoin transfer 是真支付还是 CEX 搬砖？DAU 里 bot vs human？
 
> ⭐ Stablecoin 研究：本节直接吃 Part 5.5 KEY SIGNAL 的 CONFIRMATION/DIVERGENCE 判定结论。
 
### 7.3 Token value capture ≠ Project quality
Protocol revenue 是否分给 holders？Token 是否仅 governance？Staking 是 real yield 还是 pure emission？未来 12 月 unlock 压力？FDV 是否已 price in 未来增长？（Stablecoin 不适用本节，价值在 issuer 不在 token。）
 
### 7.4 Centralization & dependency check
依赖 single team / multisig？依赖母公司分发（Arc→Circle / Base→Coinbase / Tempo→Stripe），母公司改策略会怎样？单点故障在哪（sequencer / oracle / bridge / DA / banking partner）？
 
### 7.5 Distribution vs Technology check `[payment/infra/stablecoin 必填]`
它赢是因为技术更好还是 distribution 更强？技术被复制后 distribution 还能形成 moat 吗？distribution 强但开发者不来会不会变空链？
 
> Arc：Circle 的 USDC 分发能否转化为链上 ecosystem？ Tempo：Stripe merchant network 能否转化为 crypto volume？ Base：Coinbase 入口能否转化为 on-chain retention？
 
---
 
## Part 8 — Valuation / Strategic Value
 
### Path A — If token exists（crypto-native asset / token-bearing protocol）
FDV / Annualized Revenue · MC / Fees（P/E equivalent）· unlock-adjusted valuation · relative vs comparables · Bull/Base/Bear 量化区间。
 
### Path B — If no token exists（Arc / Tempo / 私有 infra）
谁捕获价值？· strategic value to parent（Arc→Circle / Tempo→Stripe）· indirect beneficiaries（公开 token 或 protocol 间接受益）· potential monetization model · comparable business models（Visa/Stripe/SWIFT/Tron as USDT rail）。
 
### Path C — Stablecoin valuation（v1.3 新增）
**不估 token 价格（永远 ~$1），估的是发行方这门 float 生意：**
- 发行方 enterprise value（基于 reserve income capitalization：annualized reserve income × 适用 multiple）
- Market share trajectory（按 supply growth rate vs 同类，结合 Part 5.5 KEY SIGNAL 判定增长质量）
- Strategic moat（distribution + regulatory + integration 三者叠加）
- 利率情景敏感性（不同 Fed 路径下 issuer 收入区间）
- Comparables: Circle (公开市值/SEC filings)、Tether (传闻估值，supply×yield×margin 反推)、PayPal 稳定币业务单元、传统货币基金管理人
---
 
## Part 9 — Catalysts & Risks `[Both]`
 
### 9.1 Catalysts (3–12 months)
 
| Catalyst | Expected Timing | Impact Direction | Likelihood |
|----------|-----------------|------------------|------------|
 
可能：mainnet launch / fee switch / token unlock cliff / 新链 expansion / institutional product / regulatory clarification / 重要 integration / governance proposal / airdrop。Stablecoin 专属：新链 native 发行 / 大型 fintech 集成 / 监管牌照获批 / 储备透明度升级 / 大额机构 mint。
 
### 9.2 Risk matrix
 
| Risk Type | Specific Risk | Likelihood | Impact |
|-----------|--------------|------------|--------|
| Market | | | |
| Execution | | | |
| Smart Contract | | | |
| Regulatory | | | |
| Centralization | | | |
| Liquidity / Peg | | | |
| Competitive | | | |
| Token (unlock / inflation) | | | |
| Ecosystem concentration | | | |
| Reserve / Banking（stablecoin）| | | |
| Interest-rate（stablecoin issuer）| | | |
 
---
 
## Part 10 — Second-Order Effects `[Mode B emphasis; Mode A optional]`
 
成功/失败下谁赢谁输 · 间接受益者 · 监管政策连锁 · 叙事层面影响（catalyze new narrative？）· 跨 sector 传导（DeFi→CEX / RWA→传统金融 / payment→银行）。
 
---
 
## Part 11 — Conclusion `[Both]`
 
### 11.1 Position
☐ Bullish ☐ Neutral ☐ Bearish — 一句话理由。
 
> 写 Position 前先过 Part 1.6 Confidence Downgrade Rules：命中任一硬规则即按上限封顶 confidence，并注明触发了哪条（如"核心 metric 仅 2 源 → 结论封顶 MEDIUM，规则 1"）。
 
### 11.2 Track list
未来需持续监控的 KPI（1/2/3）。Stablecoin 至少含：net supply slope、CONFIRMATION/DIVERGENCE 状态、peg 偏离、reserve 披露更新。
 
---
 
## Part 11.5 — Data acquisition workflow `[Both]`
 
把 Stack Anamnesis fetchers（B.1）的原始数据接进 template 填写。
 
### Step 1: Identify required fetchers by subject_type
 
| Subject Type | Required Fetchers | Notes |
|--------------|-------------------|-------|
| **Chain (L1)** | DefiLlama, CoinGecko, Etherscan, Alchemy RPC | + CoinMarketCap 价格交叉验证 |
| **Chain (L2)** | DefiLlama, L2Beat, CoinGecko, Alchemy RPC, Etherscan | L2Beat = TVS + stage + risks |
| **DeFi Protocol** | DefiLlama, Etherscan, CoinGecko | Etherscan 做合约分析 |
| **Crypto-native asset** | CoinGecko, CoinMarketCap, Etherscan, Alchemy RPC | Alchemy 取 live totalSupply；CMC 交叉验证 |
| **Stablecoin（v1.3）** | DefiLlama (stablecoins endpoint), Etherscan (holder + transfer events), Alchemy (live totalSupply across chains), SEC EDGAR (if issuer listed), CoinGecko (peg price) | Reserve attestation = MANUAL PDF；CEX orderbook depth 不在 B.1 |
| **Payment Chain** | DefiLlama, Alchemy RPC, Etherscan, L2Beat (if L2) | 自定义分析 via Dune 暂延 (TD-024) |
| **News Reaction** | All applicable per central subject | 时间窗可含 7d 取事件后即时数据 |
 
### Step 2: Invoke each fetcher
```bash
python3 tools/fetchers/<source>_fetch.py \
  --subject <subject> --subject-type <subject_type> --freshness-window <window>
```
- `<source>` ∈ {defillama, coingecko, etherscan, sec_edgar, alchemy, coinmarketcap, l2beat}
- 链浏览器类（Etherscan/Alchemy）用合约地址（USDC = `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`）；SEC EDGAR 用发行方名（Circle）
- `<window>` ∈ {7d, 30d, 90d, quarter, 1 year, since_TGE}
SEC EDGAR 额外需 `--sec-email <research-email>`（process-memory only，never persisted，I-003 invariant）。
 
### Step 3: Raw envelopes 落在 `meta/raw/<source>/`
6-key envelope: `subject / subject_type / freshness_window / endpoint / fetched_at / raw_response`。
路径: `meta/raw/<source>/<subject_slug>_<utc_compressed>.json`。`meta/raw/*` gitignored。
 
### Step 4: Analysis 层读 envelopes → 填 template
当前 B.1→B.2 过渡为**手动**：`ls -la meta/raw/*/` → 对每个 section 打开相关 envelope 同步数据 → 按 [AUTO]/[SEMI-AUTO]/[MANUAL] 标签优先级决定自动化顺序。
 
### Step 5: 回到 Part 12
原始数据到手后，charts / Evidence Table 引用 / Quality Self-Check 正常进行。
 
---
 
## Part 12 — Required Charts & Data `[Both]`
 
**目标 5–8 张图，按 subject 可用性挑，不为补图而补图。**
 
### Universal (if data exists)
- [ ] Time series：TVL / active addresses / fees / revenue（6–12mo）
- [ ] Competitive comparison table（见 6.2）
- [ ] Ecosystem / stakeholder map
- [ ] Timeline of major events（含未来 catalyst）
### Token-related (only if token exists)
- [ ] Token allocation pie · Unlock schedule timeline · FDV vs MC over time · Emissions vs revenue
### Payment chain specific
- [ ] Stablecoin supply by chain · transfer volume by chain · Transaction Volume/TVL ratio · USDC vs USDT share · native vs bridged · corridor map
### DeFi protocol specific
- [ ] TVL market share · Revenue market share · price vs revenue · incentives vs organic fees · retention cohort · P/S vs comparables
### Stablecoin specific（v1.3 新增）
- [ ] ⭐ Supply momentum overlay：supply + holder count + usage 三线叠加（直接可视化 CONFIRMATION vs DIVERGENCE）
- [ ] Per-chain supply distribution (stacked area, 12mo)
- [ ] Supply net change (7d/30d bar)
- [ ] Reserve composition pie
- [ ] Holder concentration (top N curve)
- [ ] Peg deviation history
- [ ] vs competitors supply market share
- [ ] CCTP / cross-chain volume Sankey
### News-driven specific
- [ ] Event timeline · Bridge/cross-chain flow Sankey · Affected ecosystem map (winners/losers)
### Data sources
 
**Active in Stack Anamnesis B.1**：
 
| Source | Use | Registry § |
|--------|-----|-----------|
| DefiLlama | TVL, fees, stablecoins, cross-chain volume | §1 |
| CoinGecko | Price, market cap, 24h volume | §4 |
| Etherscan | Tx, contract verification, holder counts | §3 |
| SEC EDGAR | 10-K/10-Q for listed issuers (Circle, Coinbase, MARA) | §6 |
| Alchemy RPC | Raw chain state (live totalSupply, balance, contract reads) | §5 |
| CoinMarketCap | Price + MC cross-check | §13 |
| L2Beat | L2 TVS, stage, risk indicators | §12 |
 
**Deferred / Archived**（key 已存但 fetcher 未建，不要纳入工作流直到对应 TD unblock）：Artemis (pending student plan) · Dune (TD-024) · Messari (TD-025) · Token Terminal / Allium / Nansen (TD-021, paid) · Electric Capital (backlog)。
 
> Active 7 覆盖约 80% 典型 stablecoin/fintech 研究需求；剩余 20%（dev activity、深度自定义链上分析、cross-chain 统一指标、wallet 行为）目前需手动研究或 TD unblock。
 
---
 
## Part 13 — Appendix `[Both]`
References & sources · Methodology notes（数据范围/计算方式/假设）· Disclaimer（对外/institutional 必填）· Open questions / 待后续 research 项。
 
---
 
## Quality Self-Check（产出前过一遍）
 
1. ☐ thesis 是否在前 150 字内清楚表达？
2. ☐ 竞品对比表是否选了**真正可比**对象，而非泛泛 "L1"/"DeFi"/"stablecoin"？
3. ☐ 我是否区分了"使用量" vs "incentive-driven 使用量"？（Stablecoin：是否做了 CONFIRMATION/DIVERGENCE 判定？）
4. ☐ 我是否区分了"项目好" vs "token 好"？（无 token 用 Path B；stablecoin 用 Path C，不硬做 FDV）
5. ☐ Evidence Table 里所有非 trivial claim 是否都有 source？
6. ☐ Data Availability 标注是否诚实（不要把 Weak 写成 Medium）？
7. ☐ Stablecoin 专项：reserve/banking 集中风险与利率敏感性是否都进了 Part 9 risk matrix？
8. ☐ **Part 1.6 Confidence Downgrade Rules**：是否逐条核对四条硬规则？命中的是否已按上限封顶 confidence 并在 Evidence Table + Conclusion 注明？（三源 / pre-mainnet / stablecoin mechanical-growth / L2 信任假设）
9. ☐ 一个 institutional reader 读完能否回答"这值得我投入资金/时间吗？"
全 yes 可发；任一 no 回去补。
 
---
---
 
# 🔻 以下为 personal workshop 区域，**不属于 report deliverable** 🔻
 
---
 
## YYFoundry Content Workshop `[Personal brand, 不放进交付的 research]`
 
研究做完后单独问，决定是否产出公开内容：
 
**Content packaging**：能否拆成文章/视频/推文 thread？哪个 channel（Substack 长文 / X thread / YouTube / 中文双语）？读者画像（crypto-native vs traditional finance）？
 
**"From Atoms to Bits" narrative hook**：有没有能追溯到物理层的钩点（能源、芯片、地理、监管）？这是差异化核心。例：研究 USDC → 钩点可能是 Circle 储备里美债的久期策略 + banking partner 的物理金融基础设施。
 
**Visual asset planning**：是否值得做产业链图 / 七层栈图 / Sankey / supply momentum 三线叠加图？能否复用 YYFoundry 视觉识别（monospace + metal texture + electric blue）？是否做成可独立传播单图（X 引流回长文）？
 
**Series potential**：能否扩展成 mini-series？与现有 pipeline 衔接（Top 30 L1 whitepaper / Bitcoin Starts with Sand）？
 
**Bilingual angle**：中文版受众特殊视角（监管、出海、中文用户对 payment chain / stablecoin 的实际需求）？中→英编辑流程是否走通？