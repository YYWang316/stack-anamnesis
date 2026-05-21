---
schema_version: 1
description: Prose explanation of the Stack Anamnesis pipeline — what each phase does, what blocks, what runs in parallel, where outputs land. Read this for the phase narrative; read workflow_meta.json for the machine-readable contract. The contract is bracketed by an incident pre-check before P0_subject_class and an incident post-check before P_DB_INDEX; report and card pipelines are each followed by a parallel red-team review.
---

# Phase contract

`workflow_meta.json` is the source of truth for phase IDs, tools, agents, parallelism, retry policies, and produced artifacts. **If anything in this prose disagrees with `workflow_meta.json`, the JSON wins.** This file is the prose companion: it explains *why* each phase exists and how it connects to the next.

For runtime procedure (the orchestrator's step-by-step), see `agents/orchestrator.md`. This file is for understanding the pipeline shape.

## Phase id index

The prose below uses dotted shorthand (P1.5, P3.6, P5.7) that maps to canonical phase ids in `workflow_meta.json`. `tools/research/validate_workflow_meta.py` cross-checks that every id below appears literally somewhere in this file; keep both columns in sync when adding or renaming a phase.

| Section narrative | Canonical id |
|---|---|
| Incident pre-check | `P_INCIDENT_PRECHECK` |
| P0 — subject confirm (always, first gate) | `P0_subject_confirm` |
| P0 — SEC email (conditional) | `P0_sec_email` |
| P0 — freshness (always) | `P0_freshness` |
| P0 — language (always, last gate) | `P0_language` |
| P0 — meta validation | `P0M_meta` |
| P0 — DB precheck | `P0_DB_PRECHECK` |
| P1 — parallel research | `P1_parallel_research` |
| P1.5 — edge insight | `P1_5_edge` |
| P2 — financial analysis | `P2_fin_analysis` |
| P2.5 — prediction waterfall | `P2_5_waterfall` |
| P2.6 — macro QC peers | `P2_6_qc_macro` |
| P3 — Porter analysis | `P3_porter` |
| P3.5 — Porter QC peers | `P3_5_qc_porter` |
| P3.6 — QC resolution merge | `P3_6_qc_merge` |
| P3.7 — cross-validation | `P3_7_X_VALIDATE` |
| P4 — Sankey injection | `P4_sankey` |
| P5 — HTML report writer | `P5_html` |
| P5_gate — HTML structural gate | `P5_html_gate` |
| P5.5 — final report data validator | `P5_5_data_val` |
| P5.7 — red team report | `P5_7_RED_TEAM` |
| P6 — packaging + report validator | `P6_pkg` |
| P7 — logo production | `P7_logo` |
| P8 — card content production | `P8_content` |
| P8.5 — hardcode/logic audit | `P8_5_hardcode` |
| P9 — layout fill | `P9_layout` |
| P10 — Validator 1 | `P10_validator1` |
| P10.5 — Validator 2 | `P10_5_validator2` |
| P10.7 — red team cards | `P10_7_RED_TEAM` |
| P11 — render six PNGs | `P11_render` |
| P12 — final audit (paying-customer gate) | `P12_final_audit` |
| Incident post-check | `P_INCIDENT_POSTCHECK` |
| DB index | `P_DB_INDEX` |

## The 33 phases at a glance

```
P_INCIDENT_PRECHECK ★
  → P0_subject_confirm → P0_sec_email (conditional) → P0_freshness → P0_language → P0M_meta → P0_DB_PRECHECK
  → P1 parallel research (financial / macro / news, 3 subagents)
  → P1.5 edge insight
  → P2 financial analysis
  → P2.5 prediction waterfall
  → P2.6 macro QC peer A/B (parallel)
  → P3 Porter analysis
  → P3.5 Porter QC peer A/B (parallel)
  → P3.6 QC resolution merge
  → P3.7 cross-validation (history / peer / macro drift)
  → P4 Sankey payload
  → P5 HTML report writer (locked SHA256-pinned template)
  → P5_gate validate_report_html.py (line/section/JS/marker hard gate)
  → P5.5 final data validator (CFA-level)
  → P5.7 RED TEAM ★ (numeric + narrative attackers, parallel; cap=1 loop)
  → P6 report validator + packaging profile
  → P7 logo production (≥840px wide; saved to output dir first)
  → P8 card content production
  → P8.5 hardcode/logic audit
  → P9 layout fill (char/pixel budgets)
  → P10 Validator 1 (tools/photo/validate_cards.py)
  → P10.5 Validator 2 (web fact-check; loops back to P10 ≤3×)
  → P10.7 RED TEAM ★ (numeric + narrative attackers, parallel; pre-render; cap=1 loop)
  → P11 render 6 PNGs (2160×2700)
  → P12 final audit: reconcile + OCR + web third + DB cross  ★ paying-customer gate
  → P_INCIDENT_POSTCHECK ★ (re-read INCIDENTS.md; flagged blocks DB write)
  → P_DB_INDEX writes everything into db/equity_kb.sqlite
```

★ = non-skippable phases added on top of the original research+card pipeline. They are the harness's institutional-memory loop (`P_INCIDENT_PRECHECK` / `P_INCIDENT_POSTCHECK`) and its adversarial-review fire (`P5_7_RED_TEAM` / `P10_7_RED_TEAM`).

## P_INCIDENT_PRECHECK — institutional memory, read first

Runs **before** `P0_subject_class`. The orchestrator reads `INCIDENTS.md` end-to-end and writes one event to `meta/run.jsonl` per entry:

```json
{"phase": "P_INCIDENT_PRECHECK", "event": "incident_precheck.acknowledged", "incident_id": "I-001", "ack": "<one-line acknowledgement>"}
```

If any incident's `Phase` field matches a phase the run will execute, the orchestrator raises the bar on that surface (e.g. private-fund target → I-002 applies → expect harder scrutiny on locked-template adherence). When the matching phase fires, log a `phase_enter.incident_aware` event with the incident id.

This phase is short, cheap, and non-skippable. A run that did not pre-check is not deliverable.

## P0 block — gates and bootstrap

The four P0 gates fire in **strict order** before any data fetch. Three are always-on; `P0_sec_email` is the only conditional gate. There is no sticky mechanism and no `USER.md` — every gate asks the user explicitly on every run. Canonical spec: `references/research_dimensions.md` §1–§2. Enforcement contract: `references/p0_gates.md` §1–§2.

| Phase | Purpose |
|---|---|
| `P0_subject_confirm` | Always (first gate). Resolve `subject_entity` (the analytical "I") and any `parent_or_issuer_entity` by querying `references/subject_relationships.yaml` and the web in parallel, then present a three-way `Y` / `N` / `skip_public_company` confirm. `user_confirmed_action` is the authority that decides whether `P0_sec_email` fires. Agent: `agents/subject_confirm_gate.md`. |
| `P0_sec_email` | **Conditional** — fires ONLY when `subject_confirm.user_confirmed_action == "Y"` AND `parent_or_issuer_entity.listed == true`. Collects a contact email (or canonical `declined`) for SEC EDGAR's User-Agent. Constructs `sec_user_agent` in runtime memory for `*.sec.gov` hosts only; the email is NEVER persisted (I-003). When the trigger is false the gate still runs, writes `applies=false`, and emits `phase_exit` — so the downstream chain never stalls. Agent: `agents/sec_email_gate.md`. |
| `P0_freshness` | Always. `freshness ∈ {7d, 30d, 90d, quarter, 1 year, since_TGE}` — closed enum, single select, no default, no inference from the prompt. Agent: `agents/freshness_gate.md`. |
| `P0_language` | Always (last gate). `language ∈ {en, zh, both, side_by_side}` — closed enum, no default, never inferred from chat language. Selects the P5 writer dispatch mode (see P4–P5.7 below). Agent: `agents/language_gate.md`. |
| `P0M_meta` | Validate `workflow_meta.json` schema (`tools/research/validate_workflow_meta.py`). |
| `P0_DB_PRECHECK` | Lookups for prior financials, peer companies, fresh macro snapshot. Never blocks. See `references/cross_quarter.md`. (Equity-era table shape; Phase B will redefine the precheck queries for the crypto taxonomy.) |

**Hard floor for all four gates:** the only allowed `meta/gates.json -> source` values are `user_response` (plus the gate-specific variants `user_response_after_conflict` / `user_direct` for `subject_confirm`, and `applies_when_false` for a skipped `sec_email`). There is **no** `USER.md sticky` source — the sticky mechanism is abolished. Auto mode does not waive any gate. A non-answer halts the run (`gate_unanswered`); no gate falls back to a default. See `references/p0_gates.md` §3 for the closed source-enum and the four forbidden rules.

## P1–P3.7 — research pipeline

**Crypto fetcher dispatch (forward reference to B.1).** After the four gates resolve, P1 dispatches data fetchers across the **13 registered sources** in `references/data_source_registry.md`: **6 core** always-on sources (§1–§6 — DefiLlama, Dune, Etherscan family, CoinGecko, RPC tier, SEC EDGAR) plus **7 conditional** non-core sources (§7–§13 — Artemis, Token Terminal, Allium/Nansen, Electric Capital, Messari, L2Beat, CoinMarketCap). SEC EDGAR (§6) is gated on `P0_sec_email` — skipped when the email was `declined` or the gate did not apply; the conditional non-core sources are enabled per subject hints. Every fetch applies the freshness window from `P0_freshness`. `references/research_dimensions.md` §3 documents the dispatch logic; the concrete fetcher agents are B.1 work and not yet built.

> **Residue note (TD-018 item 2):** the paragraph below describes the Phase A equity ER subagent pipeline (`financial_data_collector` / `macro_scanner` / `news_researcher` under `skills_repo/er/agents/`). It is retained for pipeline-shape continuity and will be replaced by the crypto fetcher dispatch above when B.1 lands.

Delegated to subagents under `skills_repo/er/agents/`. The orchestrator's job is to dispatch with the right inputs (e.g., pass `prior_financials_used.json` to `financial_data_collector` so it knows which periods are already covered).

- **P1** is parallel: `financial_data_collector` ‖ `macro_scanner` ‖ `news_researcher` (concurrency 3).
- **P2.6** and **P3.5** are parallel pairs of QC peer agents.
- **P3.6** merges QC verdicts. Apply the scoring math from `MEMORY.md` exactly: `weighted = 0.34·draft + 0.33·a + 0.33·b`; only change scores when `|weighted − draft| > 1.00`.
- **P3.7** is `agents/cross_validator.md` + `tools/audit/db_cross_validate.py`. CRITICAL findings (self-history YoY mismatch >5pp; sector_macro_identity in mode A) block the next phase.

## P4–P5.7 — report writing + adversarial review (ER)

- **P4**: inject Sankey payload into `financial_analysis.json`.
- **P5 writer dispatch** — driven by `P0_language` (`meta/gates.json -> language.value`); see the `P0_language.writer_dispatch` map in `workflow_meta.json` and `agents/language_gate.md` (§Outputs, Procedure Step 4):
  - `en` → single monolingual EN writer → one HTML at `research/{Subject}_Research_EN.html`.
  - `zh` → single monolingual CN writer → one HTML at `research/{Subject}_Research_CN.html`.
  - `both` → **two parallel writers** → two independent HTML files (EN + CN); same upstream research data, but content may diverge by audience (e.g. zh foregrounds 出海/cross-border, en foregrounds GENIUS-Act/regulatory framing). Emits `language_dual_writers_dispatched`. NOT a single merged document.
  - `side_by_side` → **one bilingual writer** → one HTML at `research/{Subject}_Research_Bilingual.html`; each section written twice (EN + CN) and arranged in parallel, semantically identical (translation, not divergence). Emits `language_bilingual_writer_dispatched`.
- **P5 mechanics**: extract the locked HTML skeleton via `tools/research/extract_template.py --lang <cn|en> --run-dir <run_dir> --sha256`. Delegate to the writer(s) selected above (`report_writer_{cn,en}.md` is the Phase A equity-era writer mechanism; the crypto writers under `agents/writers/` are forthcoming in B.5 per `agents/language_gate.md`). **Never edit structure** — substitute `{{PLACEHOLDER}}` only. **Never** hand-write a simplified report regardless of target type — see `INCIDENTS.md` I-002.
- **P5_gate**: run `tools/research/validate_report_html.py --run-dir <run_dir> --lang <cn|en>`. It blocks simplified hand-written HTML by checking locked-template markers, six required sections, chart JS variables, minimum size/line count, and unresolved placeholders. Failure → discard the HTML and rerun P5 from the extracted skeleton.
- **P5.5**: `final_report_data_validator.md`. CRITICAL → loop back to P5 (cap 2). 0 CRITICAL → proceed.
- **P5.7 RED TEAM** ★: in parallel, delegate to `agents/attackers/red_team_numeric.md` and `agents/attackers/red_team_narrative.md`. Inputs at `meta/red_team/P5_7_RED_TEAM.input.json` cover the locked-template HTML, all upstream `research/*.json`, `cross_validation.json`, and the P5.5 validator output. Outputs at `validation/red_team_numeric_P5_7_RED_TEAM.json` and `validation/red_team_narrative_P5_7_RED_TEAM.json`. **Loop rule**: `summary.critical > 0` from either attacker → loop back to `P5_html` once with both attackers' challenge lists combined into a single revision request. Red-team retry cap = 1 (separate from the P5.5 retry cap of 2). A second critical from the red team after the loop → halt and surface to user. `warn` findings flow into `validation/QA_REPORT.md` at P12 but do not block. Distinct from QC peer agents: peers vote on agreement, attackers try to falsify.
- **P6**: `tools/research/packaging_check.py` + `report_validator.md`. `packaging_check.py` repeats the P5 HTML gate and stores `html_template_gate` in `structure_conformance.json`. Selects packaging profile from `strict_18_full_qc_secapi`, `strict_17_full_qc_no_secapi`, `strict_13_fast_no_qc_secapi`, `strict_12_fast_no_qc_no_secapi`. **No fabricated profile names**, **no fabricated statuses** (`pass | warn | critical` only) — see `INCIDENTS.md` I-002.

## P7–P10.7 — card pipeline + adversarial review (EP)

- **P7 logo**: hard rule — create the per-run `cards/` directory **first**, save `logo_official.png` into it, set `logo_asset_path` to that absolute path, only then proceed. Order matters; see `MEMORY.md`.
- **P8 content**: produces `cards/{stem}.card_slots.json` with all 17 top-level keys.
- **P8.5 hardcode audit**: every sentence has a company-specific anchor; no boilerplate.
- **P9 layout**: compress to char/pixel budgets — do not invent facts.
- **P10 Validator 1**: `python tools/photo/validate_cards.py`. Exit 0 required.
- **P10.5 Validator 2**: web fact-check. Any change to `card_slots.json` → rerun P10. Loop cap 3.
- **P10.7 RED TEAM** ★: **fires before P11 render — cards do not yet exist as PNGs.** Inputs at `meta/red_team/P10_7_RED_TEAM.input.json` cover the six `card_slots.json` files, the source `research/*.json`, `cards/validator{1,2}_report.json`, and the upstream P5.7 red-team outputs. The attacker contracts at this phase are **pre-render only**:
  - **Numeric attacker** — checks source-chain integrity, basis/units, tolerance compliance against source JSONs, and *render-budget realizability* (will the value as written fit the card's pixel/char budget without truncation; will rounding shift change reader meaning). It does **not** OCR anything — there is nothing rendered to OCR yet.
  - **Narrative attacker** — checks Porter-score directionality, hidden assumptions, missing counter-evidence, cross-card narrative coherence, and locked-template integrity carry-over.

  Outputs at `validation/red_team_numeric_P10_7_RED_TEAM.json` and `validation/red_team_narrative_P10_7_RED_TEAM.json`. **Loop rule**: `summary.critical > 0` from either attacker → loop back once to `P9_layout` (or `P8_content` if the defect is content-level rather than layout-level). Red-team retry cap = 1. A second critical = halt. Actual PNG OCR remains P12 layer 2.
- **P11 render**: 6 PNGs at 2160×2700, palette = `P0_palette`.

## P12 — paying-customer audit ★

Layers in order, via `agents/post_card_auditor.md`:

| Layer | Tool | Fail blocks? |
|---|---|---|
| 1. Numerical reconciliation | `tools/audit/reconcile_numbers.py` | yes |
| 2. OCR over the 6 PNGs | `tools/audit/ocr_cards.py` | yes |
| 3. Web third-check (top-3 numbers) | `tools/audit/web_third_check.py` | yes |
| 4. DB cross-validate | `tools/audit/db_cross_validate.py` | no (cold-start OK) |
| 5. User-Agent PII guard | `tools/audit/user_agent_pii.py` | yes |

Output: `validation/post_card_audit.json`, `validation/user_agent_pii.json`, and human-readable `validation/QA_REPORT.md` (the QA report aggregates P12 findings *and* the `warn`-level findings from P5.7 / P10.7). Never skip P12 unless the user types "skip audit / 跳过审计" in the same turn — and even then, log a `phase_skipped` event.

## P_INCIDENT_POSTCHECK — relapse detector

Runs **after** `P12_final_audit` and **before** `P_DB_INDEX`. The orchestrator re-reads `INCIDENTS.md` and confirms each entry's detection signal is green for this run. Output: `validation/incident_postcheck.json`:

```json
{
  "schema_version": 1,
  "incidents": [
    {"id": "I-001", "status": "pass", "evidence": "meta/gates.json"},
    {"id": "I-002", "status": "pass", "evidence": "research/structure_conformance.json"}
  ],
  "flagged": []
}
```

Any `flagged` entry **blocks** `P_DB_INDEX`. A relapse on a known incident is a release-blocking event; surface to the user with the exact incident id, the file path that contradicts it, and the rule that was violated. Do not write to DB.

## P_DB_INDEX — persistence

Runs **only** after BOTH:
- `P12_final_audit` reports `status: pass` (or warn-only), AND
- `P_INCIDENT_POSTCHECK` reports `flagged: []`.

`workflow_meta.json` declares `runs_after: P_INCIDENT_POSTCHECK` plus `requires: [P12_final_audit, P_INCIDENT_POSTCHECK]` so any runner that follows the contract enforces both gates, not just P12.

`python tools/db/index_run.py --run-dir <run_dir>` — single transaction, rollback on failure. Append-only `intelligence_signals` and `disclosure_quirks` survive partial-run admission with an analyst note.

## Failure caps (from MEMORY.md)

| Loop | Cap |
|---|---|
| ER subagent retry (same prompt) | 2 |
| `P10.5_validator2` ↔ `P10_validator1` | 3 |
| `P5.5` → `P5` (data validation fail → rewrite) | 2 |
| `P5_7_RED_TEAM` → `P5_html` (red-team critical) | 1 |
| `P10_7_RED_TEAM` → `P9_layout` / `P8_content` (red-team critical) | 1 |
| Subagent timeout retry | 1 (×1.5 multiplier); second timeout = phase failure |
| `P12` auto-retry | 0 (surface to user with run-dir path) |
| `P_INCIDENT_POSTCHECK` flagged retry | 0 (surface to user; relapse is release-blocking) |

## Resume semantics

If `meta/run.jsonl` already exists at start, you are in a resume context. Find the last `phase_exit` event; restart from the next phase. Inputs that already exist on disk and are schema-valid are reused — do not re-call subagents whose outputs are already present.

`P_INCIDENT_PRECHECK` events are **not** considered "complete on resume" by virtue of having fired in a prior session — re-fire them at every fresh session start, since `INCIDENTS.md` may have been updated between sessions.
