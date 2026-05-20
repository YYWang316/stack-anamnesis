---
schema_version: 1
name: freshness_gate
role: P0_freshness — interactive gate for data time window
description: Always-on gate. Single-select from a closed 6-value enum
  {7d, 30d, 90d, quarter, 1 year, since_TGE}. Determines the data
  time window applied to all fetcher dispatches downstream. Liberal
  reply parsing (English/Chinese/numeric) normalizes to canonical
  enum values.
allowed_toolsets: ["io", "yaml"]
---

# Freshness Gate

## Mission

- Resolve the data freshness window for the research run.
- Single-select from a closed 6-value enum — no defaults, no inference.
- Surface `tge_date` context when the user is considering `since_TGE`, so they know what time depth they are committing to.

## Inputs

- `meta/gates.json -> subject_confirm.subject_entity.name` — for the `{Subject}` placeholder in the verbatim ask.
- `references/subject_relationships.yaml` — for the `tge_date` lookup used in the `since_TGE` hint sentence.
- User input: enum choice via number, code, or natural phrase (English / Chinese / numeric).

## Outputs

`meta/gates.json -> freshness`:

```json
{
  "freshness": {
    "value": "7d" | "30d" | "90d" | "quarter" | "1 year" | "since_TGE",
    "source": "user_response",
    "asked_at": "<ISO timestamp>",
    "answered_at": "<ISO timestamp>"
  }
}
```

Closed enum. No defaults, no fallbacks. The downstream fetcher dispatch (B.1) reads this field and applies the window to all data source queries (`references/research_dimensions.md` §3).

## Procedure

### Step 1 — Resolve placeholders

Read:

- `{Subject}` ← `meta/gates.json -> subject_confirm.subject_entity.name`.
- `{tge_date}` ← `references/subject_relationships.yaml -> {Subject}.tge_date`, **if** `{Subject}` is in the yaml table.

Compute:

- `{n_years}` ← `(today - tge_date)` in years, rounded to 1 decimal.
- If `{tge_date}` is null or `{Subject}` is not in the yaml, omit the TGE hint sentence in Step 2 entirely.

### Step 2 — Ask the user (verbatim)

Print this prompt verbatim and stop. Substitute placeholders:

```
选择数据时间窗口:

  (1) 7d        - 最新动态, 适合反应类研究
  (2) 30d       - 标准月度趋势
  (3) 90d       - 季度趋势
  (4) quarter   - 当前财季 (匹配 SEC 10-Q 周期)
  (5) 1 year    - 年度视角
  (6) since_TGE - 从代币诞生到现在 (适合老项目深度分析)

{if tge_date available: {Subject} 的 TGE 是 {tge_date},
 since_TGE 会拉 ~{n_years} 年完整历史.}
```

If `tge_date` is unavailable, omit the last sentence (do **not** print `TGE 未知` or any substitute — silence is correct).

### Step 3 — Accept reply

Accept (case-insensitive, whitespace-tolerant):

| Reply maps to | Accepted forms |
|---|---|
| 7d | 7d, 7day, 7days, 1, 一周, 7天, week |
| 30d | 30d, 30day, 30days, 2, month, 一月, 30天, monthly |
| 90d | 90d, 90day, 3months, 3, 三月, quarterly_window |
| quarter | quarter, Q, 4, 当前季度, 财季, current_quarter |
| 1 year | 1 year, 1year, 1y, year, annual, 5, 一年, yearly |
| since_TGE | since_TGE, since_tge, sinceTGE, all, TGE, 6, 从头, 全部, full_history |

Note: `1 year` is stored canonically **with a space** (matches the §2.3 spec in `references/research_dimensions.md`). Accepted input forms include both spaced and unspaced variants.

If the reply does not match any accepted form:

- Re-ask once with the same prompt.
- Second non-match → emit `gate_unanswered`, halt the run.
- Do **NOT** fall back to a default.

On match:

- Write `meta/gates.json -> freshness` with `value=<canonical>`, `source="user_response"`, `asked_at` and `answered_at` timestamps.
- Emit `freshness_resolved` with payload `{value}`.

## Forbidden

- **NEVER** apply a default value if the user does not answer.
- **NEVER** infer freshness from `prompt_raw` (e.g., "research USDC last month" must NOT auto-resolve to `30d`; the user must explicitly answer the gate).
- **NEVER** accept a non-enum value (e.g., `60d` or `2 weeks` — re-ask with the same 6 options).
- **NEVER** cache or sticky freshness across runs.
- **NEVER** print `TGE 未知` or any placeholder substitute when `tge_date` is unavailable; silently omit the hint sentence.

## Events emitted to meta/run.jsonl

- `phase_enter` / `phase_exit` (standard).
- `freshness_resolved` (Step 3 success) — payload `{value}`.
- `freshness_invalid_input` (Step 3 re-ask trigger) — payload `{raw_input, attempt_n}`.
- `gate_unanswered` (no valid answer after re-ask).

## Resume semantics

If `meta/run.jsonl` has `phase_exit` for `P0_freshness` AND `meta/gates.json -> freshness` exists, trust the persistent state and skip. No mid-loop state to handle — this is a single-select gate with an atomic resolve.

## Cross-references

| File | Use |
|---|---|
| `references/research_dimensions.md` §2.3 | Canonical Gate 3 spec |
| `references/research_dimensions.md` §3 | Data source dispatch (freshness applies to all fetchers) |
| `references/subject_relationships.yaml` | `tge_date` lookup |
| `agents/subject_confirm_gate.md` | Upstream — Gate 1 (provides `subject_entity.name`) |
| `agents/sec_email_gate.md` | Upstream — Gate 2 |
| `agents/language_gate.md` | Downstream — Gate 4 (forthcoming in Step 3d) |
