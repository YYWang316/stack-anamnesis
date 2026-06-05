---
description: Run one agent-driven crypto research pass on a subject — deterministic data layer (orchestrate --bundle), then the crypto-report-writer subagent writes the narrative, then render HTML. Produces a final .md + .html.
allowed-tools: Bash, Read, Write, Agent
argument-hint: <subject> (e.g. USDC)
---

# /research — data → agent writer → render

Subject for this run: `$ARGUMENTS`

The writer is a Claude **subagent** (`crypto-report-writer`), not an external API. The
deterministic data layer is pure Python and must NOT be touched here — this command
only adds the agent writing + wiring. Follow these steps in order.

## 1. Build the data layer (deterministic, pure)

Run:

```bash
python3 -m analysis_layer.orchestrate "$ARGUMENTS" --bundle
```

From the stdout, capture the two paths it prints:
- `report written to: <scaffold>.md` — the scaffold (Part 5 numbers filled, `[MANUAL]`
  slots flagged, `Auto Evidence Table` appended).
- `bundle written to: <bundle>.facts.json` — the facts bundle (the writer's ONLY
  source of numbers).

Resolve both to absolute paths (they print relative to the repo root). If the subject
is not in the registry the command exits non-zero — stop and report the error.

## 2. Hand off to the crypto-report-writer subagent

Spawn the **`crypto-report-writer`** agent (Agent tool). Give it the two absolute
paths and tell it to read both and return the WHOLE filled markdown. Do not paste the
file contents — the agent has Read and loads them itself.

Prompt to the subagent (fill in the paths):

> You are the crypto-report-writer. Read the facts bundle at `<abs bundle .facts.json>`
> and the scaffold report at `<abs scaffold .md>`. Following your brief, write the
> Tier-1 narrative (thesis, 1.3 stack positioning, 1.4 Evidence Table, 1.5 Data
> Availability, Part 3/4, the 5.5 KEY SIGNAL verdict + each subsection's 核心分析问题,
> Part 6 competitive, Part 7 filters, Part 8 Path C valuation, Part 9, Part 11.1
> Position + 11.2 track list) into the scaffold. Take every number ONLY from the facts
> bundle; leave the `[AUTO ✓ FILLED]` / `[SEMI-AUTO ✓ COMPUTED]` numbers untouched;
> leave every `[MANUAL]` / `UNFILLED [AUTO]` / `NEEDS HUMAN REVIEW` slot flagged; do
> not edit the Auto Evidence Table. Return ONLY the complete report markdown, no
> preamble and no code fences.

The agent's final message is the filled report markdown.

## 3. Save the final report

Take the markdown the subagent returned. Strip any accidental leading/trailing prose or
```` ``` ```` fences so it starts at `# Crypto Research Report Template`. Write it next
to the scaffold with a `.report.md` stem (keep the scaffold for audit):

- scaffold `meta/reports/<slug>_<utc>.md` → final `meta/reports/<slug>_<utc>.report.md`

Use the Write tool.

## 4. Render HTML (same renderer as orchestrate --html)

Render the FINAL markdown (not the scaffold) through the existing renderer:

```bash
python3 -c "import pathlib; from analysis_layer.render.html import render_html; p=pathlib.Path('<abs final .report.md>'); h=p.with_suffix('.html'); h.write_text(render_html(p.read_text(encoding='utf-8')), encoding='utf-8'); print('html written to:', h)"
```

## 5. Report the paths

Print the final `.report.md` and `.report.html` absolute paths. Note: the scaffold
`.md` and `.facts.json` remain on disk as the deterministic record.

## Guardrails

- Do NOT modify `analysis_layer/*` (extractors / aggregator / filler / orchestrate),
  the template, or any number. This command is wiring + agent writing only.
- The writer takes numbers ONLY from the `.facts.json`; the no-fabrication rule lives
  in its brief. If the returned markdown invented a number or filled a `[MANUAL]` slot,
  reject it and re-run step 2 once.
