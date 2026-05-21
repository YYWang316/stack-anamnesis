---
schema_version: 1
description: Enforcement contract for the four P0 gates of the 4-gate harness
  (subject_confirm, sec_email, freshness, language). Read this when entering any
  P0 gate, when wiring the orchestrator's gate loop, or when reviewing
  meta/gates.json. Companions: references/research_dimensions.md §2 (per-gate
  spec), the four agent files under agents/ (implementations), workflow_meta.json
  (machine-readable phase config).
---

# P0 gates — enforcement contract

Stack Anamnesis resolves every research run through **four P0 gates**: three always-on and one conditional. They fire strictly in order before any data fetch happens. There is no sticky mechanism and no `USER.md`; every gate asks the user explicitly on every run, and nothing is remembered across runs.

This file is the **enforcement contract** — the rules the orchestrator must hold while running the gates. For the per-gate behavioral spec (inputs, verbatim prompts, output shapes) read `references/research_dimensions.md` §2. For the machine-readable phase order and dependency graph read `workflow_meta.json`. **If anything here disagrees with `workflow_meta.json`, the JSON wins** — the JSON is the phase source of truth and this file is its enforcement companion.

The previous gate sets are **retired**: the Phase A equity-era 7-gate framework, and the intermediate Gen-2 4-gate set (`subject_class` / `output_format` / `scope` / `freshness`). Any reference to `P0_subject_class`, `P0_output_format`, `P0_scope`, `P0_intent`, `P0_lang`, or `P0_palette` is residue (tracked in `references/TODO.md` TD-018), not a live gate.

---

## Section 1: The 4 gates at a glance

Mirrors `references/research_dimensions.md` §1.

| Order | Phase id | Gate | Trigger | Asks user | Persists to |
|---|---|---|---|---|---|
| 1 | `P0_subject_confirm` | subject_confirm | always (first gate) | confirm subject identity: `Y` / `N` / `skip_public_company` | `meta/gates.json → subject_confirm` |
| 2 | `P0_sec_email` | sec_email | **conditional** (see §2) | contact email, or `declined` | `meta/gates.json → sec_email` (token only — never the email) |
| 3 | `P0_freshness` | freshness | always | window: `7d` / `30d` / `90d` / `quarter` / `1 year` / `since_TGE` | `meta/gates.json → freshness` |
| 4 | `P0_language` | language | always (last gate) | output language: `en` / `zh` / `both` / `side_by_side` | `meta/gates.json → language` |

- **subject_confirm** resolves `subject_entity` (the analytical "I") and any `parent_or_issuer_entity` (context + the SEC trigger). Its `user_confirmed_action` is the authority that decides whether `sec_email` fires.
- **sec_email** is the *only* conditional gate. When its trigger is false it still runs — it writes `applies=false` and emits `phase_exit` — so the downstream chain never stalls.
- **freshness** and **language** are always-on closed-enum single-selects with no defaults.

Agent implementations: `agents/subject_confirm_gate.md`, `agents/sec_email_gate.md`, `agents/freshness_gate.md`, `agents/language_gate.md`.

---

## Section 2: Sequence enforcement

**Gates fire in strict order: 1 → 2 → 3 → 4.** `workflow_meta.json` encodes this as a linear `depends_on` chain (`P0_subject_confirm` ← `P0_sec_email` ← `P0_freshness` ← `P0_language`, rooted at `P_INCIDENT_PRECHECK`). The orchestrator must not reorder, parallelize, or batch the gates into a single combined prompt — each gate's user-facing ask is owned by its agent and surfaced on its own turn.

**`sec_email` is the only conditional gate.** Its trigger is read from Gate 1's output:

```
trigger = (subject_confirm.user_confirmed_action == "Y")
       AND (subject_confirm.parent_or_issuer_entity.listed == true)
```

- If the trigger is **true**, the gate asks the user for an email (or `declined`).
- If the trigger is **false**, the gate writes `sec_email.applies=false` with `source="applies_when_false"`, emits `sec_email_skipped` then `phase_exit`, and does **not** ask the user anything. This is the `always_exits` contract in `workflow_meta.json`: a conditional gate still produces a `phase_exit`, so Gate 3's `depends_on` resolves whether or not the email was collected.

**Downstream phases halt until gates resolve.** No phase past the gate block (`P0M_meta`, `P0_DB_PRECHECK`, `P1_*`, and everything after) may begin until all four gates have emitted `phase_exit` and `meta/gates.json` carries the four resolved blocks (`subject_confirm`, `sec_email`, `freshness`, `language`). A gate is "resolved" when it has a `phase_exit` event and its `meta/gates.json` block exists — for `P0_language`, additionally `writer_mode_confirmed=true`.

**A `user_reinput_requested` from Gate 1 aborts the run.** When `subject_confirm` emits `user_reinput_requested` (the user answered `N`), the orchestrator emits a `halt_for_reinput` state and stops cleanly. The user re-runs with a new prompt — a different prompt is a different run (`references/research_dimensions.md` §4). No partial gate state carries over; no default subject is applied.

**Resume.** On resume, trust a gate's `meta/gates.json` block only when its `phase_exit` event is present (and `writer_mode_confirmed=true` for language). `sec_email` with `value="email_provided"` is the exception: the email lives only in runtime memory, so after a process restart the gate must re-ask even though the persisted token confirms an email was once provided. There is no recovery path for the email itself.

---

## Section 3: User answer authority

**The `source` enum is closed.** Each resolved gate records a `source` in `meta/gates.json`. The only valid values are:

| Gate | Allowed `source` values |
|---|---|
| `subject_confirm` | `user_response`, `user_response_after_conflict` (Case B), `user_direct` (Case D path c) |
| `sec_email` | `user_response` (asked), `applies_when_false` (trigger false → skipped) |
| `freshness` | `user_response` |
| `language` | `user_response` |

**The agent never invents a `user_response` value.** Every enum answer (`Y`/`N`/`skip_public_company`; an email or `declined`; a freshness window; a language) must come from a real user reply parsed against the gate's accepted-forms table. The agent may normalize input (e.g. `一周` → `7d`, `decline` → `declined`) but may not synthesize an answer the user did not give.

**Forbidden `source` values** — any of these in `meta/gates.json` is a P0 violation: `auto_mode_default`, `assumed_from_chat_language`, `inferred_from_locale`, `inferred_from_prompt`, `prefilled_for_speed`, `USER.md sticky` (no sticky mechanism exists), or any other invented value. The gates exist precisely because the answer is not derivable from context — inventing one defeats the gate.

**Non-answers halt; they never default.** If a user does not answer after the gate's re-ask budget (subject_confirm: two re-asks; sec_email / freshness / language: one re-ask), the gate emits `gate_unanswered` and the run halts. The orchestrator never substitutes a default value for a non-answer.

Any missing or invalid `source`, or a gate block produced without a corresponding user reply, is a release-blocker caught at `P_INCIDENT_POSTCHECK` (gate-bypass via invented source — the I-001 pattern).

---

## Forbidden rules

These are absolute. Each is also enforced at the agent level (see the per-agent "Forbidden" sections) and audited at `P_INCIDENT_POSTCHECK`.

1. **NEVER fire a downstream phase before all required gates have `phase_exit`.** The gate block (`P0_subject_confirm` → `P0_sec_email` → `P0_freshness` → `P0_language`) is a hard floor. No fetcher, no DB precheck, no meta validation begins until all four gates have resolved and emitted `phase_exit`.

2. **NEVER skip `sec_email`'s trigger check.** Gate 1's `user_confirmed_action` is the authority. The email is asked **only** when `user_confirmed_action == "Y"` AND `parent_or_issuer_entity.listed == true`. Even if a user volunteered an email earlier, the trigger condition — not the user's eagerness — decides whether the gate asks. A `skip_public_company` or `N` action means the trigger is false and the gate is skipped (writes `applies=false`).

3. **NEVER cache or sticky gate answers across runs.** There is no `USER.md` and no sticky source. Every gate asks every run. The `sec_email` email additionally never persists even within a run — it lives only in process memory and is wiped on run termination (the I-003 contract; `tools/audit/user_agent_pii.py` is the leak detector).

4. **NEVER apply a default value on a user non-answer.** A `gate_unanswered` halts the run. No gate falls back to `en`, `30d`, `declined`, or any other "reasonable default" — the cost of guessing wrong (wrong subject, wrong window, wrong language, a PII default) is a full re-run or a privacy incident, so the gate halts instead.

---

## Section 4: Cross-references

| File | Use |
|---|---|
| `references/research_dimensions.md` §1 | The 4 gates at a glance (canonical) |
| `references/research_dimensions.md` §2 | Per-gate behavioral spec (inputs, verbatim prompts, outputs) — the contract source for this file |
| `references/research_dimensions.md` §3 | Data source dispatch after the four gates resolve |
| `references/research_dimensions.md` §4 | Core invariants (email never persisted, no sticky, single subject) |
| `references/research_dimensions.md` §5 | Subject identity contract (`subject_entity` vs `parent_or_issuer_entity`) |
| `agents/subject_confirm_gate.md` | Gate 1 implementation |
| `agents/sec_email_gate.md` | Gate 2 implementation (conditional; runtime-only UA) |
| `agents/freshness_gate.md` | Gate 3 implementation |
| `agents/language_gate.md` | Gate 4 implementation (writer dispatch modes) |
| `workflow_meta.json` | Machine-readable phase order, `depends_on` chain, conditional trigger, `always_exits` — the phase source of truth |
| `references/data_source_registry.md` §6 | SEC EDGAR consumer contract, two-UA model (consumes Gate 2's runtime `sec_user_agent`) |
| `references/equity_incidents_archive.md` | I-003 origin (Phase A user_agent leak) |
| `references/TODO.md` TD-018 | Gen 1/2 residue sweep (where retired gate names are tracked) |
