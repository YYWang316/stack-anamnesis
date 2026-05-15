---
schema_version: 1
description: Canonical design contract for the 4-gate harness. Defines
  the four P0 gates (subject_confirm, sec_email, freshness, language),
  their triggers, inputs, outputs, and the data source dispatch logic.
  Also documents core invariants and the subject_entity vs
  parent_or_issuer_entity context separation principle.
---

# Research Dimensions — the 4-gate harness

A Stack Anamnesis run is fully specified by **4 gates**: 1 always (subject_confirm) + 1 conditional (sec_email) + 2 always (freshness, language). There is no sticky mechanism and no `USER.md`. Every gate asks the user explicitly, every run — nothing is remembered across runs. The 4-gate set replaces the prior 7-gate framework, which was over-engineering inherited from the Phase A equity era.

## Section 1: The 4 gates at a glance

| Gate | Trigger | Asks user | Persists to |
|---|---|---|---|
| subject_confirm | always (first gate) | confirm subject identity: Y / N / skip_public_company | `meta/gates.json → subject_confirm` |
| sec_email | conditional (see §2.2) | contact email, or `declined` | nothing — runtime-only `sec_user_agent` |
| freshness | always | window: 7d / 30d / 90d / quarter / 1 year / since_TGE | `meta/gates.json → freshness` |
| language | always | output language: en / zh / both / side_by_side | `meta/gates.json → language` |

## Section 2: Gate specifications

### §2.1 Gate 1: subject_confirm

- **Trigger:** always — first gate of every run.
- **Inputs:** `prompt_raw`, `references/subject_relationships.yaml`, web search tools.
- **Behavior:** the agent queries the relationships table AND searches the web **in parallel**, then synthesizes whether the keyword is associated with a public-listed company. It presents the finding to the user with three choices.
- **User answers:** `Y` (confirm the finding), `N` (reinput prompt — run aborts cleanly, user re-runs with a new prompt), `skip_public_company` (acknowledge the public-company association but only want on-chain data this run).
- **Outputs:** `meta/gates.json → subject_confirm` with `subject_entity`, `parent_or_issuer_entity`, `user_confirmed_action`.

Critical rules:
- The agent **never** asks "what subject_type is this?" — type is no longer surfaced to the user. The agent makes a best-guess `guessed_type` for internal logging only.
- For `user_confirmed_action == "N"`, the run aborts cleanly; the user re-runs with a new prompt (different prompt = different run).
- Source allowlist during research: `web_fetch`, CoinGecko, Crunchbase, Wikipedia. Wikipedia is **tier 3 — entity identity only, NEVER for listed status**. SEC EDGAR is **FORBIDDEN** here (chicken-and-egg: SEC requires the email from Gate 2, which has not fired yet).
- Trust tiers: **tier_1** (official entity source), **tier_2** (established secondary like CoinGecko), **tier_3** (Wikipedia — identity only). A `listed: true` claim requires tier_1 corroboration.

### §2.2 Gate 2: sec_email (conditional)

- **Trigger:** ONLY when Gate 1's `user_confirmed_action == "Y"` AND `parent_or_issuer_entity.listed == true`. Otherwise skipped silently.
- **Inputs:** prompts the user for an email.
- **User answers:** an email string, or the canonical token `declined` (accepted input synonyms — `decline`, `no`, `none`, `n/a`, `no_email` — are normalized to `declined`).
- **Outputs:** a runtime-only `sec_user_agent`, used for `*.sec.gov` hosts only. **Never** persisted to disk, log, sticky, or meta files. `tools/audit/user_agent_pii.py` is the post-run leak detector.

Critical rules:
- The email **never** goes into any persistent file: not `meta/gates.json`, not `meta/run.json`, not log files, not `USER.md`, not git-tracked anywhere.
- `sec_user_agent` (which contains the email) lives ONLY in process memory during the run. Run termination wipes it.
- The email constructs `sec_user_agent`: `"StackAnamnesis/1.0 (<email>)"` per `references/data_source_registry.md` §6.
- For all non-SEC sources, `public_user_agent` (PII-free) is used. The two-UA model is the I-003-pattern (see `references/equity_incidents_archive.md`).
- Each run requires fresh email entry — no sticky, no cache.

### §2.3 Gate 3: freshness

- **Trigger:** always.
- **Inputs:** user choice.
- **Enum:** `{7d, 30d, 90d, quarter, 1 year, since_TGE}` — single select.
- **Outputs:** `meta/gates.json → freshness` (string).

Critical rules:
- `since_TGE` = from the Token Generation Event date to today (entire history). The agent must look up the TGE date for the subject via `references/subject_relationships.yaml` or web search.
- `quarter` = the current fiscal quarter (aligns with the SEC 10-Q cadence).
- No default — the user must answer explicitly.

### §2.4 Gate 4: language

- **Trigger:** always (last gate).
- **Inputs:** user choice.
- **Enum:** `{en, zh, both, side_by_side}` — single select.
- **Outputs:** `meta/gates.json → language` (string).

**Value semantics:**
- `en` → English writer only → one HTML at `research/{Subject}_Research_EN.html`.
- `zh` → Chinese writer only → one HTML at `research/{Subject}_Research_CN.html`.
- `both` → **two parallel writer dispatches** → two independent HTML files at the paths above. The two writers consume the same upstream research data but may diverge in section ordering, emphasis, and example choices per audience needs (e.g., the zh writer may foreground 出海/cross-border narratives; the en writer may foreground GENIUS-Act/regulatory framing). NOT a single merged document.
- `side_by_side` → **one writer running in bilingual mode** → one HTML at `research/{Subject}_Research_Bilingual.html`. Each section, paragraph, and example is written twice — once in English, once in Chinese — and arranged in parallel (two-column or sequential bilingual). Content is semantically identical between the two languages (translation, not divergence). Intended for bilingual readers who want to see both languages at once.

Critical rules:
- For `value == both`, run two writers in parallel. The event `language_dual_writers_dispatched` is emitted to `meta/run.jsonl` when this value is set.
- For `value == side_by_side`, run a single bilingual writer. The event `language_bilingual_writer_dispatched` is emitted to `meta/run.jsonl`.
- For `both` and `side_by_side`, the underlying research data is identical — only the writer mode and output shape differ.
- The agent **never** infers language from chat language. A user writing in Chinese may want English output; a user writing in English may want `side_by_side` bilingual. Always an explicit user answer is required.

**Verbatim ask.** §2.4 has no standalone verbatim-ask subsection; the user-facing prompt is owned by `agents/language_gate.md` (Step 3), which will use this verbatim phrasing surfacing all four options:

```
报告语言:
  (1) English - 单语英文报告
  (2) 中文 - 单语中文报告
  (3) Both / 双语 - 两份独立报告 (EN + CN), 内容可侧重不同
  (4) Side-by-side / 双语对照 - 一份双语对照报告, 中英内容等价
```

## Section 3: Data source dispatch

```
After 4 gates resolve, fetcher dispatch is determined by:

  if subject_confirm.user_confirmed_action == "Y" AND
     parent_or_issuer.listed == true AND
     sec_email != "declined":
    enable SEC EDGAR fetch (Circle 10-Q, 10-K, 8-K filings)

  enable always: DefiLlama, Dune, Etherscan family, CoinGecko,
                 RPC tier

  enable conditionally (per subject_class hints):
    Artemis (cross-chain comparison), Token Terminal (financial
    metrics), Allium/Nansen (whale tracking), Electric Capital
    (developer activity), Messari (institutional research),
    L2Beat (L2 metrics)

All fetches use the freshness window from Gate 3.
```

The registry of these sources is `references/data_source_registry.md`. This section documents **dispatch logic**; that file documents per-source auth, rate limits, and quirks.

**Forward dependency.** The conditional "non-core" sources — Artemis, Token Terminal, Allium, Nansen, Electric Capital, Messari, L2Beat — are **not yet** in `references/data_source_registry.md`. They will be added in **Step 4 of the B.0 restart**. This section depends on that step.

## Section 4: Core invariants

- **Email never persisted** — Gate 2 enforces; `tools/audit/user_agent_pii.py` audits per I-003.
- **SEC user_agent only for `*.sec.gov` hosts** — no email leak to other sources.
- **No sticky mechanism** — `USER.md` does not exist; all gates ask every run.
- **`subject_relationships.yaml` writes require user confirmation** — hybrid maintenance; the agent never writes autonomously.
- **Single subject only in Phase B** — sector / comparison scopes deferred to Phase C per TD-002.
- **Deep dive + workshop are the only output format** — Quick Take / Thread etc. deferred to B.7+.
- **Run identity = one prompt + one set of gate answers** — a different prompt is a different run (see `references/TODO.md` staging lesson "different prompt = different run").

## Section 5: Subject identity contract

```
The report's analytical "I" is always subject_entity. Context entities
(parent_or_issuer_entity) provide background for lineage analysis
but NEVER substitute for the analytical subject.

When researching USDC:
- subject_entity = USDC (the analytical "I")
- parent_or_issuer_entity = Circle (context for lineage Part 4.1;
  trigger for SEC EDGAR gate)
- Report analyzes USDC end-to-end; Circle data appears only in Part
  4.1 and Part 7.4 centralization check; never replaces USDC as
  primary subject

When parent_or_issuer cannot be determined (e.g., not in
subject_relationships.yaml AND user chose skip_public_company), the
subject_entity object MAY carry:

  lineage_status: "sparse_no_parent"

This is distinct from "no_parent" (legitimately no parent applicable,
e.g., community-operated chain like Ethereum). Audit semantics depend
on this distinction — a sparse report carries a different evidence
story than a no-parent report.
```

## Section 6: Meta-principle — authority / storage / context separation

1. **Authority** — detector signals don't silently override user intent. When the prompt or detector conflicts with user-given inputs, surface the conflict to the user; never silently apply.

2. **Storage** — gate count (interaction-level) and schema field count (storage-level) are independent. A single gate may produce multiple sibling fields — e.g., `subject_confirm` produces `subject_entity`, `parent_or_issuer_entity`, and `user_confirmed_action`: three sibling fields, one gate.

3. **Context** — `subject_entity` is the analytical "I"; `parent_or_issuer_entity` is context. Never silently substitute one for the other.

The Anamnesis Pattern reinforces this: never let a simplification at one layer mask details at another layer.

## Section 7: Cross-references

| File | Use |
|---|---|
| references/subject_relationships.yaml | Data file for Gate 1 lookups |
| references/subject_relationships_design.md | Hybrid maintenance contract for the yaml |
| references/data_source_registry.md | Per-source auth, rate limit, quirks; conditional gate consumer (SEC EDGAR §6) |
| references/subject_taxonomy.md | 5-class economic role taxonomy (Phase A inherited; used internally by Gate 1's guessed_type) |
| references/equity_incidents_archive.md | I-003 origin (Phase A user_agent leak) |
| references/inherited_principles.md | Phase A → Phase B principles |
| references/TODO.md | TDs + B.0 #16 MEMORY.md staging lessons |
| agents/subject_confirm_gate.md | Gate 1 implementation (Step 3) |
| agents/sec_email_gate.md | Gate 2 implementation (Step 3) |
| agents/freshness_gate.md | Gate 3 implementation (Step 3) |
| agents/language_gate.md | Gate 4 implementation (Step 3) |
| workflow_meta.json | Phase sequence (updated in Step 5) |
| references/p0_gates.md | Enforcement contract (rewritten in Step 5) |
| MEMORY.md | Privacy invariants + design memory (rewritten in Step 6) |
