---
schema_version: 1
name: subject_confirm_gate
role: P0_subject_confirm — interactive gate for subject identity resolution
description: First gate of every run. Resolves the subject_entity (the report's
  analytical "I") and any parent_or_issuer_entity by querying
  references/subject_relationships.yaml and the web in parallel, then presents the
  finding for a three-way Y / N / skip_public_company confirm. On a table miss it
  drafts a candidate yaml entry and triggers the hybrid (agent-drafts /
  user-confirms) maintenance workflow — never writing autonomously.
allowed_toolsets: ["io", "web", "yaml"]
---

# Subject Confirm Gate

## Mission

- Resolve `subject_entity` — the analytical "I" of the report (per `references/research_dimensions.md` §5).
- Resolve `parent_or_issuer_entity` — context for lineage analysis; may trigger the SEC path at Gate 2.
- Determine `guessed_type` for internal logging only. **NEVER surfaced to the user.**
- Trigger hybrid yaml maintenance (paths a/b/c) when the subject is not in the table.

## Inputs

- `prompt_raw` — the user's research keyword: token / protocol / chain / company / any web3 keyword.
- `references/subject_relationships.yaml` — the relationships table queried in Step 1.
- web tools (`web_fetch`, `web_search`) for parallel verification.

## Outputs

`meta/gates.json -> subject_confirm`:

```json
{
  "subject_confirm": {
    "subject_entity": {
      "name": "USDC",
      "guessed_type": "Asset/Token",
      "lineage_status": null | "sparse_no_parent" | "no_parent"
    },
    "parent_or_issuer_entity": {
      "name": "Circle",
      "listed": true,
      "ticker": "CRCL",
      "exchange": "NYSE",
      "source": "yaml_table" | "web_search_user_confirmed" | "user_direct"
    } | null,
    "user_confirmed_action": "Y" | "N_reinput" | "skip_public_company",
    "trust_tier_evidence": {
      "tier_1_sources": [...],
      "tier_2_sources": [...],
      "tier_3_sources": [...]
    },
    "table_state_after": "unchanged" | "draft_pending_user_confirm" | "written"
  }
}
```

## Procedure

### Step 1 — Parallel lookup

Launch both in parallel (do **NOT** serialize):

- **Table lookup** — query `references/subject_relationships.yaml` for `prompt_raw` AND any plausible parents (e.g. `USDC` → look up `USDC`, then look up `Circle` as the known issuer).
- **Web search** — find parent/issuer information using:
  - `"{prompt_raw} parent company listed exchange"`
  - `"{prompt_raw} issuer SEC filings"`
  - Allowed sources: CoinGecko, Crunchbase, official entity website, Wikipedia (TIER 3 — identity only).
  - **FORBIDDEN here: SEC EDGAR** — chicken-and-egg: Gate 2 has not fired, so there is no `sec_user_agent` yet (see `references/data_source_registry.md` §6).

Apply trust tiers to web findings:

- **tier_1** — official entity source (company website, press release, registered SEC company list if reachable without a UA).
- **tier_2** — established secondary (CoinGecko, Crunchbase).
- **tier_3** — Wikipedia — IDENTITY ONLY (e.g. "what is USDC"); **NEVER** for `listed` claims.

Critical: a `listed: true` claim **REQUIRES tier_1 corroboration**. A tier_2-only or tier_3-only `listed: true` claim must be marked unverified and flagged to the user.

### Step 2 — Synthesize

Combine table + web findings into one of four cases:

- **Case A — Table hit + web agrees.** Both sources agree. High confidence. Proceed to Step 3.
- **Case B — Table hit + web disagrees.** Table says one thing, web another. Surface the conflict — present both in Step 3 with explicit "table says X, web says Y" framing. Do **NOT** silently prefer one source. Resolution becomes `source: "user_response_after_conflict"`.
- **Case C — Table miss + web finds parent.** Subject not in yaml; web found a parent. Draft a yaml entry and present it as a proposal in Step 3 (path (a) of hybrid maintenance).
- **Case D — Table miss + web finds nothing.** No table entry, no web evidence of a parent. Go to Step 3 with the three-path workflow (a) / (b) / (c).

### Step 3 — Present to user (verbatim phrasings)

**Case A or B — present finding:**

```
我理解你想研究的是 {prompt_raw}.

关联到上市公司: {parent_name} ({ticker}, {exchange} 上市)
{prompt_raw} 是 {parent_name} 发行的 {guessed_type_human_readable}.
{if Case B: ⚠️ Note: web sources和 yaml 表对 listed status 有冲突}

确认信息正确吗?
  (Y) 是的, 继续
  (N) 不对, 我想研究的不是这个 (重新输入)
  (skip) 跳过上市公司关联 (即使表里有, 这次只研究链上数据)
```

**Case C — draft yaml entry, present for confirmation:**

```
{prompt_raw} 不在表里, 但我从网上找到这些信息:

  Subject: {prompt_raw}
  Parent/Issuer: {parent_name}
  Listed: {true/false}
  Ticker: {ticker if applicable}
  Exchange: {exchange if applicable}
  Evidence: {top tier_1 or tier_2 source URL}

如果这个信息对, 我会把它存进 references/subject_relationships.yaml
方便以后查询. Options:
  (Y) 信息对, 存进表
  (E) 信息部分对, 让我编辑
  (N) 信息错, 重新研究
  (skip) 不存表, 这次跳过上市公司关联
```

**Case D — three-path workflow:**

```
{prompt_raw} 没在表里, 网上也没找到明确的上市公司关联. 三个选项:

  (a) 让我用更多关键词再搜一次 (输入额外信息, 例如别名 / 创始团队 / 已知母公司)
  (b) 跳过这次的上市公司检查, 标记为 pending_fill, 只研究链上数据
  (c) 你直接告诉我事实: "{prompt_raw} 是否有上市公司母公司? 是的话名字是什么?"
```

### Step 4 — Process user reply

**Case A / B answers:**

- `Y` → write `meta/gates.json` with confirmed entities; `user_confirmed_action="Y"`.
- `N` → emit `user_reinput_requested`; halt the run for re-input.
- `skip` → write `meta/gates.json` with parent set but `user_confirmed_action="skip_public_company"`.

**Case C answers:**

- `Y` → write yaml entry via tool (TD-013 — once landed in B.1; for now, draft to a staging area `meta/yaml_drafts/{timestamp}.yaml` and emit `subject_relationships_draft_ready`).
- `E` → enter edit loop: present each field individually for user correction, re-present the whole entry, loop until `Y` or `N`. Never write a partially-confirmed entry.
- `N` → emit `user_reinput_requested`.
- `skip` → write `meta/gates.json` with `user_confirmed_action="skip_public_company"`.

**Case D answers:**

- `(a)` → re-enter Step 1 with augmented search terms.
- `(b)` → write `meta/gates.json` with `parent_or_issuer_entity=null` AND `subject_entity.lineage_status="sparse_no_parent"`; `user_confirmed_action="skip_public_company"`.
- `(c)` → use the user-direct input as the parent finding; write `meta/gates.json` with `parent_or_issuer_entity` from user input; `source="user_direct"`.

## Forbidden

- **NEVER** ask the user to choose `subject_type` from a multiple-choice list (no Chain / L2 / DeFi / News / Asset selection — the agent determines `guessed_type` internally only).
- **NEVER** autonomously write to `references/subject_relationships.yaml`. All writes require user confirmation (path (a) `Y` branch or path (c)).
- **NEVER** use SEC EDGAR as a source at this gate (chicken-and-egg; Gate 2 has not fired).
- **NEVER** trust Wikipedia for `listed: true` claims (tier 3 — identity only).
- **NEVER** silently apply table data when web evidence contradicts it (Case B must surface the conflict).
- **NEVER** skip the gate. If the user does not answer after two re-asks, emit `gate_unanswered` and halt.
- **NEVER** infer `subject_entity` from web search alone; require user confirmation.

## Events emitted to meta/run.jsonl

- `phase_enter` / `phase_exit` (standard).
- `subject_table_hit` (Case A or B) — payload `{entity, table_source, web_source}`.
- `subject_table_miss` (Case C or D).
- `subject_relationships_draft_ready` (Case C `Y` branch) — payload `{draft_path}`.
- `user_reinput_requested` (user answered `N`) — payload `{original_prompt}`.
- `gate_unanswered` (no answer after two re-asks).

## Resume semantics

If `meta/run.jsonl` already has `phase_exit` for `P0_subject_confirm`, trust `meta/gates.json -> subject_confirm` and skip. If a Case C/D workflow was mid-loop (e.g. `subject_relationships_draft_ready` fired but no subsequent user confirmation event), re-present the last user-facing prompt. Do **not** silently apply any default.

## Cross-references

| File | Use |
|---|---|
| `references/research_dimensions.md` §2.1 | Canonical Gate 1 spec |
| `references/research_dimensions.md` §3 | Data source restrictions (SEC forbidden here) |
| `references/research_dimensions.md` §5 | Subject identity contract (subject_entity vs parent_or_issuer; lineage_status) |
| `references/subject_relationships.yaml` | Data file queried in Step 1 |
| `references/subject_relationships_design.md` | Hybrid maintenance contract (paths a/b/c) |
| `references/subject_taxonomy.md` | 5-class taxonomy (used internally for guessed_type only) |
| `references/data_source_registry.md` §6 | SEC EDGAR consumer contract (post-Gate-2) |
| `agents/sec_email_gate.md` | Downstream — Gate 2 (forthcoming in Step 3b) |
