---
schema_version: 1
description: Per-gate rules for the four P0 gates of the crypto-payments harness (subject_class, output_format, scope, freshness). Read this when entering any P0 gate or when reviewing meta/gates.json. Companion: references/subject_taxonomy.md (the five-class enum behind P0_subject_class).
---

# P0 gates — per-gate rules

Stack Anamnesis has **four P0 gates** — all blocking, none skippable — that resolve the four orthogonal axes of one research run before any data fetch happens. The four gates split into two kinds:

- **Resolution gate** — `P0_subject_class`. Resolves the subject (name + canonical identity) and the primary subject class from the user's prompt. Auto-resolution is allowed (and expected) when the prompt is unambiguous; the user is asked only on ambiguity.
- **Interactive gates** — `P0_output_format`, `P0_scope`, `P0_freshness`. Cannot be inferred from the prompt with any confidence. Each must be satisfied by either a real user reply or a sticky value in `USER.md`. Auto-mode does not waive them. The cost of guessing wrong (wrong deliverable shape, wrong analytical scope, wrong time window across the whole run) is a full re-run.

The four equity-era P0 gates (`P0_intent`, `P0_lang`, `P0_sec_email`, `P0_palette`) are **retired** for this harness:
- `P0_intent` is subsumed by `P0_subject_class` (which resolves identity *and* classifies in one step).
- `P0_lang` moves to `USER.md` as a sticky-only preference; there is no interactive language gate. (Rationale: research-output language is a settled per-user setting; the equity harness's interactive gate was a workaround for not having a sticky path, and that workaround is no longer needed.)
- `P0_sec_email` is not applicable — the SEC EDGAR User-Agent header is an SEC-specific requirement that does not transfer to DefiLlama / Dune / Etherscan / CoinGecko / RPC providers. The PII-free `public_user_agent` invariant is preserved as a global harness rule (see `references/data_source_registry.md`).
- `P0_palette` is dormant — it returns when the card pipeline (P7..P11 in the inherited workflow) is rebuilt for crypto. Until then there is no card output to palette, so the gate has no surface.

Each gate's answer is recorded in `meta/gates.json` with a `source` field. Only the values listed below are allowed per gate; anything else is a P0 violation and will be caught in `meta/gates.json` review.

---

## P0_subject_class (resolution gate)

- **Goal**: resolve the user's prompt to `{subject, primary_class, suggested_slug}` where `primary_class ∈ {stablecoin_issuer, orchestrator, wallet, chain, agentic_payment_layer}`.
- **Agent**: `agents/subject_class_resolver.md` (to be authored in Phase B; until then the orchestrator resolves inline, citing `references/subject_taxonomy.md`).
- **Taxonomy contract**: see `references/subject_taxonomy.md` end-to-end. The five enum values are the **complete** allowed set. There is no sixth on-the-fly class.
- **Interactive?** Only when confidence is low — ask **once**, then use the user's answer. Otherwise resolve from the prompt and proceed. (Same shape as the retired `P0_intent`.)
- **Allowed `source` values**: `prompt_unambiguous` (resolved from the prompt), `user_response` (asked because of ambiguity).
- **Sticky source**: none. Every run resolves freshly, because the subject changes every run.
- **Out-of-taxonomy**: if after one clarifying question the subject still does not fit any of the five classes, record `event: "not_in_taxonomy"` in `meta/run.jsonl` and **halt**. Do not invent a sixth class; do not force-fit into the closest class.
- **Recorded artifacts**: `meta/gates.json -> subject_class.{value, source, rationale}` (the `rationale` is one sentence on why this primary class — required for auditing forced cross-class calls).

## P0_output_format (interactive gate)

- **Goal**: `output_format ∈ {report, thread}`.
  - `report` — single bilingual-ready HTML deep-dive, produced via the locked-skeleton fill pattern (inherited from equity P5; the skeleton is crypto-tailored in Phase B).
  - `thread` — X (Twitter) long-post / thread, structured per the rubric in `references/TODO.md` TD-001 (quality rubric + red-team narrative attacker + key-element post-check; no SHA-locked template).
- **Agent**: `agents/output_format_gate.md` (to be authored in Phase B; until then the orchestrator asks inline).
- **Sticky source**: `USER.md:default_output_format`.
- **Inference policy**: no inference from the prompt. The same prompt can legitimately resolve to either format depending on what the user actually wants this run, and a wrong format is a full re-run.
- **Allowed `source` values**: `user_response`, `USER.md sticky`.
- **Halt** until you have one of the above.
- **Recorded artifacts**: `meta/gates.json -> output_format.{value, source}`.

## P0_scope (interactive gate)

- **Goal**: `scope ∈ {single}` (Phase A enum; `comparison` and `stack_position` are deferred to Phase B/C).
- **Agent**: `agents/scope_gate.md` (to be authored in Phase B; until then the orchestrator confirms inline).
- **Sticky source**: `USER.md:default_scope`.
- **Phase A constraint**: `single` is the only allowed value. The gate still runs and still requires an explicit user answer (or sticky) — this is deliberate; it teaches the harness to ask for scope as a routine, even when the enum has only one value. When the enum widens, the calling shape will not need to change.
- **Allowed `source` values**: `user_response`, `USER.md sticky`.
- **Halt** until you have one of the above.
- **Recorded artifacts**: `meta/gates.json -> scope.{value, source}`.

## P0_freshness (interactive gate)

- **Goal**: `freshness ∈ {7d, 30d, 90d, since_TGE}`.
  - `7d` — last 7 days only. For rapidly-moving subjects (chains, recent incidents).
  - `30d` — last 30 days. Default for most stablecoin/orchestrator/wallet runs.
  - `90d` — last 90 days. Quarter-equivalent; for trend-oriented runs.
  - `since_TGE` — since token-generation event (or company inception, for token-less subjects). Lifetime view.
- **Agent**: `agents/freshness_gate.md` (to be authored in Phase B; until then the orchestrator confirms inline).
- **Sticky source**: `USER.md:default_freshness`.
- **Inference policy**: the **subject_class default** (per `references/subject_taxonomy.md`) is a *suggestion*, not an inference. The orchestrator may surface the suggestion in the ask ("for a stablecoin issuer, 30d is the default — confirm or override?"), but the gate still requires an explicit answer or sticky.
- **Allowed `source` values**: `user_response`, `USER.md sticky`.
- **Halt** until you have one of the above.
- **Recorded artifacts**: `meta/gates.json -> freshness.{value, source, suggested_by_class}` — the third field records which class-default was offered, for auditing how often users accept vs override.

## What never counts as a valid source (interactive gates only)

`auto_mode_default`, `assumed_from_chat_language`, `inferred_from_locale`, `inferred_from_subject_class`, `prefilled_for_speed`, or any other invented value. The three interactive gates exist because the answer is not derivable from context — inventing one defeats the gate.

The resolution gate (`P0_subject_class`) is different: `prompt_unambiguous` *is* a valid source there, because identity often is derivable from the prompt. The line between the two is sharp on purpose.

## Why a 1-value enum still has a gate (P0_scope)

`P0_scope`'s Phase-A enum is exactly `{single}`. One might argue the gate is degenerate and should be deferred. It is not deferred, for two reasons:

1. **Ritual matters.** Every interactive gate teaches the harness — and the user — to expect a confirm step. Skipping the gate in Phase A and reintroducing it in Phase B creates two different harness shapes for the same operator to learn.
2. **It surfaces the "wrong granularity" failure mode early.** If a user prompts "research stablecoins" (a sector ask), the orchestrator at P0_scope cannot answer `single` honestly, and the failure is exposed at the right moment instead of buried in mid-run confusion.

When `comparison` and `stack_position` are added to the enum in Phase B/C, the gate's calling shape does not change — only the enum widens.

## Order and dependency

The gates fire in **strict order**: `P0_subject_class` first (resolution), then the three interactive gates in any sequence that is convenient to surface to the user. The orchestrator may **batch the three interactive gates into one user prompt** to reduce back-and-forth, but it may not skip any one of them, and it must record all three sources in `meta/gates.json` even when answered in a single turn.

After all four P0 gates are satisfied, the orchestrator records:

```json
{
  "schema_version": 1,
  "subject_class":   {"value": "stablecoin_issuer", "source": "prompt_unambiguous", "rationale": "Circle's primary product is USDC issuance."},
  "output_format":   {"value": "report", "source": "user_response"},
  "scope":           {"value": "single", "source": "USER.md sticky"},
  "freshness":       {"value": "30d", "source": "user_response", "suggested_by_class": "30d"}
}
```

Any missing or invalid `source` is a release-blocker caught at `P_INCIDENT_POSTCHECK` (post-fork incident I-001-equivalent: gate-bypass via invented source).
