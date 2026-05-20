---
schema_version: 1
name: language_gate
role: P0_language — interactive gate for output language
description: Always-on last gate. Single-select from a closed 4-value
  enum {en, zh, both, side_by_side}. The value determines the
  downstream writer dispatch mode: en/zh = single monolingual writer;
  both = two parallel writers producing two independent files (content
  may diverge by audience); side_by_side = one bilingual writer
  producing one file with parallel EN/CN content (semantically
  identical). The agent NEVER infers the report's language from the
  chat language; an explicit user answer is always required.
allowed_toolsets: ["io"]
---

# Language Gate

## Mission

- Resolve the output language for the research run.
- Single-select from a closed 4-value enum — no defaults, no inference.
- Determine the downstream writer dispatch mode: monolingual single, parallel dual, or bilingual single.
- Confirm `both` / `side_by_side` explicitly (cost-aware: more writers means a longer run and more compute).

## Inputs

- `meta/gates.json -> subject_confirm.subject_entity.name` — for the `{Subject}` placeholder in the Step 3 confirmation prompts.
- User input: enum choice via number, code, or natural phrase (English / Chinese).

## Outputs

`meta/gates.json -> language`:

```json
{
  "language": {
    "value": "en" | "zh" | "both" | "side_by_side",
    "source": "user_response",
    "asked_at": "<ISO timestamp>",
    "answered_at": "<ISO timestamp>",
    "writer_mode_confirmed": true | false
  }
}
```

`writer_mode_confirmed` is set `true` ONLY after the Step 3 confirmation succeeds (for `both` / `side_by_side`), or immediately on match for `en` / `zh` (monolingual needs no confirmation). Closed enum. No defaults, no fallbacks. The downstream P5 writer phase reads `value` to select the exact dispatch mode (`references/research_dimensions.md` §2.4).

## Procedure

### Step 1 — Ask the user (verbatim)

Print this prompt verbatim and stop:

```
报告语言:
  (1) English - 单语英文报告
  (2) 中文 - 单语中文报告
  (3) Both / 双语 - 两份独立报告 (EN + CN), 内容可侧重不同
  (4) Side-by-side / 双语对照 - 一份双语对照报告, 中英内容等价
```

### Step 2 — Accept reply

Accept (case-insensitive, whitespace-tolerant):

| Reply maps to | Accepted forms |
|---|---|
| en | en, EN, English, english, 英文, 1, monolingual_en |
| zh | zh, ZH, Chinese, chinese, 中文, 2, monolingual_zh |
| both | both, Both, BOTH, 3, 双语, dual, two_reports, independent_dual |
| side_by_side | side_by_side, side-by-side, sxs, SxS, 4, 双语对照, 对照, bilingual, parallel |

If the reply does not match any accepted form:

- Re-ask once with the same Step 1 prompt.
- Second non-match → emit `gate_unanswered`, halt the run.
- Do NOT default to any value.

On match for `en` or `zh`:

- Write `meta/gates.json -> language` with `value=<canonical>`, `source="user_response"`, `writer_mode_confirmed=true` (no confirmation needed for monolingual).
- Emit `language_resolved` with payload `{value}`.
- Skip Step 3.

On match for `both` or `side_by_side`:

- Proceed to Step 3 (confirmation prompt).

### Step 3 — Confirm both / side_by_side (verbatim)

Substitute `{Subject}` from `meta/gates.json -> subject_confirm.subject_entity.name`.

For `both`, print verbatim and stop:

```
确认: both - 两份独立报告. 将生成:
  - research/{Subject}_Research_EN.html
  - research/{Subject}_Research_CN.html

两份独立 — 共用研究数据但写作独立; 内容可能侧重不同
(例: 中文版可能侧重出海/跨境, 英文版可能侧重 GENIUS Act/监管).

继续? [Y/n]
```

For `side_by_side`, print verbatim and stop:

```
确认: side_by_side - 一份双语对照报告. 将生成:
  - research/{Subject}_Research_Bilingual.html

每段中英文并列, 内容语义等价 (翻译, 非分化).

继续? [Y/n]
```

On `Y` (case-insensitive: y, Y, yes, Yes, YES, 是, 继续, confirm):

- Write `meta/gates.json -> language` with `value=<canonical>`, `source="user_response"`, `writer_mode_confirmed=true`.
- For `both`: emit `language_dual_writers_dispatched` with payload `{value: "both"}`.
- For `side_by_side`: emit `language_bilingual_writer_dispatched` with payload `{value: "side_by_side"}`.
- Emit `language_resolved` with payload `{value}`.

On `n` (case-insensitive: n, N, no, No, 不, 否):

- Emit `language_confirm_rejected` with payload `{original_value}`.
- Return to Step 1 (re-ask the 4-option prompt). The user may pick a different value (e.g., explored `both`, then reconsidered to `en`).

On non-Y-non-n input: re-ask Step 3 once; second non-match → emit `gate_unanswered`, halt.

## Forbidden

- NEVER infer language from the chat language. A user writing in Chinese may want English output (e.g., for an English-speaking colleague); a user writing in English may want Chinese or `side_by_side`. The report's language is a deliberate, explicit choice — never inferred from the chat surface. (Phase A principle preserved.)
- NEVER infer language from `prompt_raw` keywords. Even an explicit phrase like "in Chinese please" must NOT auto-resolve; the gate must still ask explicitly.
- NEVER apply a default value if the user does not answer (no fallback to `en` or any other value).
- NEVER skip the Step 3 confirmation for `both` or `side_by_side`. The cost difference (one writer vs two writers vs one bilingual writer) warrants an explicit confirm.
- NEVER cache or sticky language across runs — fresh entry every run.
- NEVER conflate `both` and `side_by_side` semantically. They produce different writer dispatch modes; the downstream P5 phase must read the exact value, not just "user wants two languages".
- NEVER produce a single bilingual document for `value=both`. `both` means TWO separate files; if a single file is desired, the user must explicitly pick `side_by_side`.

## Events emitted to meta/run.jsonl

- `phase_enter` / `phase_exit` (standard).
- `language_resolved` (Step 2 or Step 3 success) — payload `{value}`.
- `language_dual_writers_dispatched` (`value=both`, after Step 3 confirm) — payload `{value: "both"}`; signals downstream P5 readiness for two-writer dispatch.
- `language_bilingual_writer_dispatched` (`value=side_by_side`, after Step 3 confirm) — payload `{value: "side_by_side"}`; signals downstream P5 readiness for the bilingual writer.
- `language_invalid_input` (Step 2 re-ask trigger) — payload `{raw_input, attempt_n}`.
- `language_confirm_rejected` (Step 3 user said `n`) — payload `{original_value}`; re-enters Step 1.
- `gate_unanswered` (no valid answer after re-ask).

## Resume semantics

If `meta/run.jsonl` has `phase_exit` for `P0_language` AND `meta/gates.json -> language` exists with `writer_mode_confirmed=true`, trust the persistent state and skip.

If `writer_mode_confirmed=false` (e.g., the user chose `both` but the Step 3 confirm was interrupted), re-enter Step 3 with the prior value. Do not re-ask Step 1.

If a `*_dispatched` event fired but no downstream P5 writer events follow, the gate completed but writer dispatch was interrupted — flag this as an orchestrator-level resume issue, NOT a `P0_language` issue. This gate's job is to decide and emit the dispatch event; actually running the writers is P5's responsibility.

## Cross-references

| File | Use |
|---|---|
| `references/research_dimensions.md` §2.4 | Canonical Gate 4 spec |
| `references/research_dimensions.md` §4 | Core invariants (no sticky, no inference) |
| `agents/subject_confirm_gate.md` | Upstream — Gate 1 (provides `subject_entity.name`) |
| `agents/sec_email_gate.md` | Upstream — Gate 2 |
| `agents/freshness_gate.md` | Upstream — Gate 3 |
| `agents/writers/` | Downstream — P5 writer dispatch (forthcoming in B.5) |
