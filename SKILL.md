---
name: stack-anamnesis
description: >-
  Use this skill whenever the user asks for crypto / on-chain research, a token or protocol
  write-up, a chain or stablecoin-issuer deep dive, or one-shot coverage on a single crypto
  subject — including casual phrasings like "研究一下 USDC", "research Ethereum", "看看 Circle",
  "做个 Solana 的研报", "give me a writeup on Coinbase", "analyze Tether", or "one-pager on Base".
  Drives the full Stack Anamnesis pipeline (incident pre-check, the four P0 gates — subject
  confirm / SEC EDGAR email / freshness / language — multi-source on-chain + filings data fetch
  across the 13-source registry, multi-agent research, red-team review, multi-layer numerical/
  OCR/web/DB audit, post-run incident self-check, SQLite knowledge-base persistence). Always
  invoke this skill instead of answering with ad-hoc web search; the harness produces an
  auditable HTML report plus database rows that ad-hoc answers cannot.
---

# Stack Anamnesis

You are the orchestrator of a **Stack Anamnesis** run — a single-subject crypto / on-chain research pipeline built on the Anamnesis Pattern (cross-session institutional memory + scheduled adversarial review). The skill is thin; the harness is heavy. Your job is to enter the harness correctly, then follow its phase contract. (Originally codenamed `equiforge` in the equity-research era; CLI is now `anamnesis.py`. The pipeline is mid-migration from equity to crypto — the P0 gate and data-source layers are rebuilt for crypto; some P1+ analysis/report/card phases are still Phase-A-shaped and framed as residue in `references/phase_contract.md`.)

## Boot order — read in this order, every session

1. This file (`SKILL.md`)
2. `MEMORY.md` — project invariants + design lessons (load-bearing; frozen into `meta/system_prompt.frozen.txt`)
3. `INCIDENTS.md` — append-only log of past failure modes (load-bearing; frozen into the same `meta/system_prompt.frozen.txt`). Read end-to-end. Each entry encodes a real prior failure plus the load-bearing rule that prevents it; the rules apply to this run.
4. `workflow_meta.json` — machine-readable phase + gate contract (the phase source of truth)
5. `agents/orchestrator.md` — runtime brief; drives the rest of the run

Stop after #5. There is **no `USER.md`** — the per-user sticky mechanism is abolished (see P0 gates below). **Do not pre-load** downstream phase agents (fetchers, writers, QC peers, attackers) — open them lazily when you actually delegate, so token cost scales with the phase being executed.

## P0 gates — blocking, not skippable

**Four** gates run before any data fetch, in **strict order** (`P0_subject_confirm` → `P0_sec_email` → `P0_freshness` → `P0_language`). There is no sticky mechanism and no `USER.md`; every gate asks the user explicitly on every run, and nothing is remembered across runs. Three gates are always-on; `P0_sec_email` is the only conditional one.

1. `P0_subject_confirm` — **always** (first gate). Resolves `subject_entity` (the analytical "I") and any `parent_or_issuer_entity` by querying `references/subject_relationships.yaml` and the web **in parallel**, then presents a three-way `Y` / `N` / `skip_public_company` confirm. `user_confirmed_action` is the authority that decides whether `P0_sec_email` fires. `N` aborts the run cleanly — the user re-runs with a new prompt (different prompt = different run). The agent **never** asks "what subject type is this?" — type is internal-only.
2. `P0_sec_email` — **conditional**: fires ONLY when `subject_confirm.user_confirmed_action == "Y"` AND `parent_or_issuer_entity.listed == true`. Collects a contact email (or the canonical token `declined`) for SEC EDGAR's User-Agent. When the trigger is false it still runs, writes `applies=false`, and emits `phase_exit` — so the downstream chain never stalls.
3. `P0_freshness` — **always**. `freshness ∈ {7d, 30d, 90d, quarter, 1 year, since_TGE}` — closed enum, single select, no default, never inferred from the prompt.
4. `P0_language` — **always** (last gate). `language ∈ {en, zh, both, side_by_side}` — closed enum, no default, never inferred from chat language. Drives the P5 writer dispatch (`both` = two parallel writers; `side_by_side` = one bilingual writer).

The only allowed `meta/gates.json -> source` values are `user_response` (plus `user_response_after_conflict` / `user_direct` for `subject_confirm`, and `applies_when_false` for a skipped `sec_email`). There is **no `USER.md sticky` source** — inventing one, or any other value (`auto_mode_default`, `assumed_from_chat_language`, …), is a P0 violation caught at `P_INCIDENT_POSTCHECK`. Auto mode waives nothing; a non-answer halts the run (`gate_unanswered`) and never falls back to a default.

For per-gate rules, the closed source enum, and rejection criteria, read **`references/p0_gates.md`**; for the canonical behavioral spec (inputs, verbatim prompts, output shapes) read **`references/research_dimensions.md`** §1–§2.

## Data sources & the two-User-Agent invariant

After the gates resolve, P1 fetches across the **13 registered sources** in `references/data_source_registry.md`: **6 core** always-on (§1–§6 — DefiLlama, Dune, Etherscan family, CoinGecko, RPC tier, SEC EDGAR) + **7 conditional** non-core (§7–§13 — Artemis, Token Terminal, Allium/Nansen, Electric Capital, Messari, L2Beat, CoinMarketCap) enabled per subject hints. Three paid-only sources (Token Terminal §8, Allium + Nansen §9) are **archived** for B.1 (TD-021) → **11 active fetchers**. SEC EDGAR (§6) is gated on `P0_sec_email` — skipped when the email was `declined` or the gate did not apply. Every fetch applies the `P0_freshness` window. (The concrete fetcher agents are B.1 work; see `references/research_dimensions.md` §3 for dispatch logic.)

**Two User-Agent strings, never collapsed (I-003).** SEC EDGAR requires a contactable email in its `User-Agent` header; that `sec_user_agent` (`StackAnamnesis/1.0 (<email>)`) is built in runtime memory and used **only** for `*.sec.gov` hosts. Every other source uses `public_user_agent` (`StackAnamnesis/1.0`, PII-free). The SEC email is **never** persisted to disk, log, sticky, or DB — it lives only in process memory and is wiped on run termination. `tools/audit/user_agent_pii.py` is the post-run leak guard (P12 layer 5); fetchers pick the UA **by host**, never "the only UA they find" — that defaulting bug is the exact I-003 shape. See `references/data_source_registry.md` §6.

## Hard floor

- **Never skip `P_INCIDENT_PRECHECK`** — read `INCIDENTS.md` and acknowledge each entry into `meta/run.jsonl` before any phase work. A run that did not pre-check is not deliverable.
- **Never skip `P5_7_RED_TEAM` or `P10_7_RED_TEAM`.** The red-team attackers (`agents/attackers/red_team_numeric.md`, `red_team_narrative.md`) are distinct from QC peers — they exist to find defects, not to average. Critical findings loop back once; a second critical halts the run.
- **Never skip `P_INCIDENT_POSTCHECK`** before `P_DB_INDEX`. A flagged post-check on a known incident means the harness relapsed; do not write to DB.
- **Never skip P12** unless the user explicitly says so in the same turn. P12 is the paying-customer audit gate.
- **Never write to DB** if P12 failed. `P_DB_INDEX` runs only after `P12_final_audit` passes AND `P_INCIDENT_POSTCHECK` reports `flagged: []`.
- **Never bypass a P0 gate** by inventing a value or source. The gates exist precisely because the answer is not derivable from context; cost of guessing wrong = full re-run.
- **Never persist the SEC EDGAR email** to disk, log, or DB. It is a runtime-only User-Agent argument for `*.sec.gov` hosts; the I-003 two-UA invariant and `tools/audit/user_agent_pii.py` are non-negotiable.
- **Never edit the locked HTML template** during P5. Substitute `{{PLACEHOLDER}}` only — the SHA256 pin in the report tests will catch you.
- **Never accept a simplified HTML report.** After P5, run `tools/research/validate_report_html.py`; line-count/section/JS/template-marker failure means the writer did not use the locked template and P5 must be rerun before P6. There is **no** "institution-compatible" / "scope-limited" bypass for the locked template; gaps are labeled inline, never dropped.
- **Never invent a packaging profile.** `structure_conformance.json -> profile` must be one of the four whitelisted in `workflow_meta.json -> packaging_profiles`.
- **Never invent a status string.** `report_validation.txt`'s top-line status is `pass | warn | critical`, full stop. `pass_with_scope_limitations`, `not_applicable`, `partial_pass`, etc. are fabricated and will be rejected.

## Commands you will run

| When | Command |
|---|---|
| First-time setup | `python anamnesis.py init` (builds `db/equity_kb.sqlite` from `db/schema/` — legacy filename, retained until the crypto schema rename) |
| Pre-flight | `pytest -q` (must be green) and `python tools/research/validate_workflow_meta.py` (validates the root phase contract) |
| Bootstrap a run dir | `python tools/io/run_dir.py --company <slug> --date <YYYY-MM-DD> --run-id <hex>` |
| P3 Porter schema gate | `python tools/research/validate_porter_analysis.py --run-dir <path>` (must pass before P3.5; reruns at P5 entry — `INCIDENTS.md` I-004) |
| P5 HTML gate | `python tools/research/validate_report_html.py --run-dir <path> --lang <cn\|en>` (must pass before P6) |
| Index a finished run | `python tools/db/index_run.py --run-dir <path>` (only after P12 passes and `P_INCIDENT_POSTCHECK` has `flagged: []`) |

The full per-phase tool/agent inventory lives in `workflow_meta.json`.

## Where to read for full detail

Pull these in lazily — only when you need them.

| Topic | Reference |
|---|---|
| Canonical 4-gate design contract (gates, triggers, outputs, invariants) | `references/research_dimensions.md` |
| Per-gate enforcement (whitelisted `source` values, forbidden rules, rejections) | `references/p0_gates.md` |
| 13-source data registry (auth, rate limits, two-UA model, SEC §6) | `references/data_source_registry.md` |
| Phase-by-phase narrative (`P_INCIDENT_PRECHECK` … `P_DB_INDEX`) | `references/phase_contract.md` |
| Visual workflow diagram (mermaid) | `references/workflow_diagram.md` |
| Subagent toolset whitelist + concurrency caps + timeouts | `references/subagent_toolsets.md` |
| Run-dir layout (which subfolder gets which artifact) | `references/run_artifacts.md` |
| Cross-quarter / cross-subject DB reuse | `references/cross_quarter.md` |
| Maintenance (template SHA, schema, submodules) | `references/maintenance.md` |
| The Anamnesis Pattern (project's distinctive methodology) | `references/anamnesis_pattern.md` |
| Inherited harness/skill principles (Anthropic-derived foundations) | `references/inherited_principles.md` |
| Harness/CLI/tests/DB/audit/resume architecture | `HARNESS.md` |
| Past failures + the rules they encode | `INCIDENTS.md` |
| Adversarial reviewers (P5.7, P10.7) | `agents/attackers/red_team_numeric.md`, `red_team_narrative.md` |

For the runtime procedure, open **`agents/orchestrator.md`** next.
