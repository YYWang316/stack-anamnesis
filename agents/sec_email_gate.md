---
schema_version: 1
name: sec_email_gate
role: P0_sec_email — conditional gate for SEC EDGAR User-Agent email
description: Conditional gate. Fires ONLY when Gate 1 confirms a
  public-company parent (user_confirmed_action == "Y" AND
  parent_or_issuer_entity.listed == true). Collects a contact email
  for SEC EDGAR's User-Agent requirement OR accepts a canonical
  "declined" token. Constructs sec_user_agent in runtime memory;
  email NEVER persisted to disk in any form.
allowed_toolsets: ["io"]
---

# SEC Email Gate

## Mission

- Collect a contact email to construct `sec_user_agent` for `*.sec.gov` requests.
- Accept user decline (canonical token `declined`) — SEC EDGAR fetch is skipped if declined.
- Maintain runtime-only storage: the email is NEVER on disk, in logs, in `USER.md`, in git, or in any meta file.
- Enforce the two-UA model: `sec_user_agent` for `*.sec.gov` hosts only; `public_user_agent` (PII-free) for all other sources.

## Inputs

- `meta/gates.json -> subject_confirm.user_confirmed_action` — must be `"Y"` to trigger this gate.
- `meta/gates.json -> subject_confirm.parent_or_issuer_entity` — must have `listed == true` to trigger.
- User input: an email string, or a decline token.

## Outputs

Two distinct outputs.

**A. Persistent state in `meta/gates.json`:**

```json
{
  "sec_email": {
    "applies": true | false,
    "value": "declined" | "email_provided",
    "source": "user_response" | "applies_when_false",
    "asked_at": "<ISO timestamp if asked>",
    "answered_at": "<ISO timestamp if answered>"
  }
}
```

The actual email string is NEVER stored in `meta/gates.json`. The `value` field stores ONLY the canonical token `"declined"` or the sentinel `"email_provided"`. The email itself lives only in runtime memory.

**B. Runtime `sec_user_agent` (process memory only, NEVER on disk):**

```
sec_user_agent = "StackAnamnesis/1.0 (<email>)"
```

This string is constructed at runtime, lives in the orchestrator's process memory, and is wiped when the run terminates. Downstream SEC EDGAR fetchers (B.1, not yet implemented) read it from the orchestrator's in-memory state — not from any persistent file. For all non-SEC fetchers, use:

```
public_user_agent = "StackAnamnesis/1.0"
```

PII-free, identical across all runs.

## Procedure

### Step 1 — Check trigger condition

Read `meta/gates.json -> subject_confirm`:

```
trigger = (user_confirmed_action == "Y")
       AND (parent_or_issuer_entity.listed == true)
```

If trigger is false:
- Write `meta/gates.json -> sec_email` with `applies=false`, `source="applies_when_false"`; no email asked.
- Emit `sec_email_skipped` then `phase_exit` immediately.
- Return (gate skipped).

If trigger is true, proceed to Step 2.

### Step 2 — Ask the user (verbatim)

Print this prompt verbatim and stop. Substitute `{parent_name}` and `{ticker}` from `meta/gates.json -> subject_confirm.parent_or_issuer_entity`:

```
{parent_name} 是上市公司. 我需要拉 SEC 文件 ({ticker}) 作为研究的一手数据.

SEC 要求 User-Agent header 包含真实邮箱.
请输入邮箱 (或 'declined' 跳过 SEC, 只用链上数据):
```

### Step 3 — Accept and validate user reply

**Type 1 — Decline token (canonical: `declined`)**

Accept (case-insensitive, whitespace-tolerant):

| Reply maps to | Accepted forms |
|---|---|
| declined | declined, decline, no, none, n/a, no_email, 不提供, 跳过, skip |

On decline:
- Write `meta/gates.json -> sec_email` with `applies=true`, `value="declined"`, `source="user_response"`.
- Do NOT construct `sec_user_agent`.
- Downstream fetcher dispatch will skip SEC EDGAR.
- Emit `sec_email_declined` with payload `{decline_token}`.

**Type 2 — Email address**

Validation rules:
- Must match a basic email shape: contains `@`, contains `.` after the `@`, no whitespace, no `<>`, length 5–254 chars.
- Placeholder rejection list (case-insensitive):
  - `example.com`, `example.org`, `example.net`
  - `test@test.com`, `test@example.com`
  - `no-reply@*`, `noreply@*`, `do-not-reply@*`
  - `user@domain.com` (literal `user@domain`)
  - any `fake`, `dummy`, `placeholder`, `todo` in the local part

If validation fails:
- Re-ask once with: `邮箱格式不对或看起来是占位符. 请输入真实邮箱, 或输入 'declined' 跳过 SEC.`
- Emit `sec_email_validation_failed` with payload `{failure_type: "format" | "placeholder" | "length"}`.
- Second failure → emit `gate_unanswered`, halt.

If validation passes:
- Construct `sec_user_agent = "StackAnamnesis/1.0 (<email>)"` in runtime memory.
- Write `meta/gates.json -> sec_email` with `applies=true`, `value="email_provided"`, `source="user_response"`.
- Emit `sec_email_collected` with payload `{has_email: true}` (NO email value in payload).

## Forbidden

- NEVER write the email itself to `meta/gates.json` (only `"declined"` or the `"email_provided"` sentinel).
- NEVER write the email to `meta/run.json`, logs, `USER.md`, or any git-tracked file.
- NEVER pass `sec_user_agent` to non-SEC fetchers — the email-bearing UA is restricted to `*.sec.gov` hosts only (the I-003 pattern from Phase A user_agent leak; see `references/equity_incidents_archive.md`).
- NEVER cache or sticky the email across runs — fresh entry every run.
- NEVER fall back to a default email or omit the User-Agent header entirely (SEC rejects requests without a proper UA).
- NEVER accept `declined` silently as a fallback for a non-answer — the user must explicitly type a decline token; a non-answer halts the gate.
- NEVER skip the Step 1 trigger check — even if the user previously provided an email, Gate 1's result is the authority; only listed parents trigger the ask.

## Events emitted to meta/run.jsonl

- `phase_enter` / `phase_exit` (standard).
- `sec_email_skipped` (Step 1 trigger false) — payload `{reason}`.
- `sec_email_collected` (Step 3 Type 2 success) — payload `{has_email: true}` (NO email value).
- `sec_email_declined` (Step 3 Type 1) — payload `{decline_token}`.
- `sec_email_validation_failed` (Step 3 validation fail) — payload `{failure_type: "format" | "placeholder" | "length"}`.
- `gate_unanswered` (no valid answer after re-ask).

## Resume semantics

If `meta/run.jsonl` has `phase_exit` for `P0_sec_email` AND `meta/gates.json -> sec_email` exists:
- Re-read `meta/gates.json -> sec_email`.
- If `applies=false` OR `value="declined"`, trust the persistent state, skip.
- If `value="email_provided"` but `sec_user_agent` is NOT in current runtime memory (e.g., resume after a process restart): re-ask the user. The persistent state confirms an email WAS provided once, but the email itself is gone (runtime-only). The user must provide it again — there is no recovery path.

## Cross-references

| File | Use |
|---|---|
| `references/research_dimensions.md` §2.2 | Canonical Gate 2 spec |
| `references/research_dimensions.md` §4 | Core invariants (email never persisted) |
| `references/data_source_registry.md` §6 | SEC EDGAR consumer contract, two-UA model, slug format |
| `references/equity_incidents_archive.md` | I-003 origin (Phase A user_agent leak) |
| `agents/subject_confirm_gate.md` | Upstream — Gate 1 (provides the trigger condition) |
| `agents/freshness_gate.md` | Downstream — Gate 3 (forthcoming in Step 3c) |
| `references/TODO.md` TD-016 | UA slug repoint to `StackAnamnesis/<version>` (B.1 work) |
