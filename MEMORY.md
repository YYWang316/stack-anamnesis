---
schema_version: 1
description: Project-level invariants frozen into the system prompt at session start. Do not violate without an explicit user instruction in the same turn.
---

# Stack Anamnesis — Project Memory

These rules are **load-bearing** and apply to every run. They are read once at session start and frozen into `meta/system_prompt.frozen.txt`. `INCIDENTS.md` is loaded alongside this file at the same moment and into the same frozen prompt — it carries the project's institutional memory of past failure modes (one entry per incident, with the load-bearing rule that prevents recurrence). Read both. The contracts compose: anything in `INCIDENTS.md` overrides nothing here, and nothing here waives anything in `INCIDENTS.md`.

## P0 gates — ordered, blocking, not skippable

1. **`P0_subject_class`** — resolve the user's prompt to `{subject, primary_class}` where `primary_class ∈ {stablecoin_issuer, orchestrator, wallet, chain, agentic_payment_layer}`. Resolution gate; auto-resolves from the prompt with `source: prompt_unambiguous` when unambiguous. Ambiguous → ask **once**. Out-of-taxonomy (subject does not fit any of the five classes even after one clarifying question) → halt and record `event: not_in_taxonomy`; never invent a sixth class on the fly. See `references/subject_taxonomy.md` for class definitions, boundary rules, and the per-class downstream contract.
2. **`P0_output_format`** — `output_format ∈ {report, thread}`. Interactive; **halt and wait for the user's actual reply** unless `USER.md:default_output_format` is sticky. Do not pick a default to keep moving.
3. **`P0_scope`** — `scope ∈ {single}` (Phase A enum). Interactive even at 1-value enum, to surface wrong-granularity prompts (e.g. "research stablecoins" cannot honestly answer `single` and must be re-prompted). **Halt** unless `USER.md:default_scope` is sticky.
4. **`P0_freshness`** — `freshness ∈ {7d, 30d, 90d, since_TGE}`. Interactive; the subject-class default in `references/subject_taxonomy.md` is a *suggestion*, not an inference. **Halt** unless `USER.md:default_freshness` is sticky.

`USER.md` may pre-fill any of `default_output_format` / `default_scope` / `default_freshness` as sticky preferences. There is **no sticky** for `P0_subject_class` — every run resolves freshly because the subject changes every run. See `references/p0_gates.md` for the per-gate contract (allowed `source` values, halt-and-wait semantics, batched-prompt rules). The retired equity-era P0 gates (`P0_intent` / `P0_lang` / `P0_sec_email` / `P0_palette`) are documented in `references/p0_gates.md` for historical reference.

## Hard rules

- **Numerical reconciliation tolerance:**
  - margins / ratios / percentage points: ±0.5pp
  - currency amounts: ±0.5% relative
  - growth rates: ±0.5pp
  - prices, share counts, or any value tagged `"exact": true`: 0 tolerance

## Database write rules

- `P_DB_INDEX` runs only after `P12_final_audit` passes and `P_INCIDENT_POSTCHECK` reports `flagged: []`. Failed audits or flagged incident post-checks do not write to DB.
- All writes for one run are inside a single transaction; failure → rollback + `runs.run_status='failed'` + `db_export/index_error.json`.
- Append-only tables (`intelligence_signals`, `disclosure_quirks`) survive partial-run admission with an analyst note. (Equity-era table names; Phase B will define crypto-domain append-only tables and rename or supersede these — the *invariant* (append-only survives partial admission) is load-bearing, the *table names* are not.)
- Cross-validation queries (`db/queries.py`) filter on `runs.run_status='complete'` by default; partial rows exist for audit only.

## Privacy invariants

- Before inserting any TEXT column, run `re.sub(r'\([^)]*@[^)]*\)', '()', value)` on `data_source` strings to strip embedded emails (User-Agent leak guard).
- `tests/test_db_pii.py` is a regression: any TEXT column matching `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}` after a fixture run = test fails = release blocked.

## Failure caps

- Subagent timeouts: research 600s / photo 300s / QC 180s; first timeout retries at ×1.5; second timeout = phase failure.
- `P12` has no auto-retry — failures surface to the user with paths and a "which upstream phase to re-run" question.

## Incident loop (load-bearing)

- `P_INCIDENT_PRECHECK` runs **before** `P0_subject_class`. The orchestrator reads `INCIDENTS.md` end-to-end and writes one `incident_precheck.acknowledged` event to `meta/run.jsonl` per entry.
- `P5_7_RED_TEAM` and `P10_7_RED_TEAM` run two adversarial agents in parallel (`agents/attackers/red_team_numeric.md`, `red_team_narrative.md`). They are **not** QC peers — QC peers vote, attackers try to falsify. Critical findings loop the writer once (cap = 1 per phase); a second critical halts the run.
- `P_INCIDENT_POSTCHECK` runs **after** `P12_final_audit` and **before** `P_DB_INDEX`. The orchestrator re-reads `INCIDENTS.md` and confirms each entry's detection signal is green for this run. A flagged post-check blocks DB write — a relapse on a known incident is a release-blocking event.
- New failure modes are captured by the user via the `/log-incident` slash command (spec at `.claude/commands/log-incident.md`, backend at `tools/io/log_incident.py`). The model drafts an `INCIDENTS.md` entry; the user confirms; only then is it appended. Append-only — never delete or rewrite past entries; supersede with a new entry if needed.

## What this project does NOT do

- No skill self-improvement / DSPy / GEPA optimizer. Auditability beats agility.
- No code-execution sandbox. Everything is a registered tool; LLM cannot exec arbitrary Python.
- No multi-tenant routing. Single-user, local SQLite, single process.
- No streaming UI. CLI in, files out.
