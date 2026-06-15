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
- `report written to: <scaffold>.md` — the v3 scaffold: the **2a filler has placed the
  machine facts table at `<!-- MODULE: metrics -->`**; the remaining `<!-- MODULE: … -->`
  anchors await the writer's narrative.
- `bundle written to: <bundle>.facts.json` — the facts bundle (the writer's ONLY
  source of numbers).

Resolve both to absolute paths (they print relative to the repo root). If the subject
is not in the registry the command exits non-zero — stop and report the error.

## 2. Hand off to the crypto-report-writer subagent

Spawn the **`crypto-report-writer`** agent (Agent tool). Give it the two absolute
paths and tell it to read both and return the WHOLE filled markdown. Do not paste the
file contents — the agent has Read and loads them itself.

Prompt to the subagent (fill in the paths):

> You are the crypto-report-writer. Read the facts bundle at `<abs bundle .facts.json>`,
> the v3 scaffold at `<abs scaffold .md>`, and your authority the analysis playbook at
> `references/playbooks/analysis_playbook.md`. Follow your brief's playbook-driven flow:
> read `subject_type` → classify (§I) → stack base + add-on modules (§II.0) → inject each
> at its matching `<!-- MODULE: … -->` anchor (dock the KEY SIGNAL verdict + A–H analysis
> at `<!-- MODULE: metrics-analysis -->`; leave `<!-- MODULE: charts -->` in place) → apply
> the §III primitives + §IV caps → strip coaching. The 2a filler has ALREADY placed every
> machine number in the Part 5 facts table — REFERENCE and interpret those figures, take
> every number ONLY from the facts bundle, never introduce a number absent from it, and
> leave every `[MANUAL]` slot flagged. With only the supply leg present, keep the KEY
> SIGNAL verdict PROVISIONAL and tick NO row. Return ONLY the complete report markdown, no
> preamble and no code fences.

The agent's final message is the filled report markdown.

## 3. Save the final report

Take the markdown the subagent returned. Strip any accidental leading/trailing prose or
```` ``` ```` fences so it starts at `# Crypto Research Report Template`. Write it next
to the scaffold with a `.report.md` stem (keep the scaffold for audit):

- scaffold `meta/reports/<slug>_<utc>.md` → final `meta/reports/<slug>_<utc>.report.md`

Use the Write tool.

## 4. Numbers-trace gate — FAIL-CLOSED (⑤.1, TD-048)

Before rendering, verify the writer did NOT silently alter or drop any
machine-produced number. Run the numbers-trace gate over the FINAL `.report.md`
against the `.facts.json` bundle:

```bash
python3 -m analysis_layer.qc.numbers '<abs final .report.md>' '<abs bundle .facts.json>'
```

This is the content-honesty floor (distinct from the ④.3 HTML-integrity gate). It
asserts every non-null bundle value (spot metrics, supply-momentum %/abs, issuer
SEC financials) survives into the report in a canonical form. **Fail-closed:** a
non-zero exit means a machine value is missing — STOP, do NOT render or ship.
Reject the writer's markdown and re-run step 2 once; if it still fails, report the
violations and stop.

> **★ TD-023 wiring note.** The gate is wired HERE, in the `/research` command,
> NOT in `analysis_layer/orchestrate.py`. The orchestrator only produces the
> deterministic *scaffold* — running the trace there is trivially true (the
> machine values are the only numbers present). The writer's narrative — the only
> place a number can be overridden — exists solely in this command's output, so
> this is the correct (and only) honest hook for ⑤.1.

## 5. Render HTML (same renderer as orchestrate --html)

Render the FINAL markdown through the renderer, **passing the facts bundle as `facts=`**
so the ④.2 inline-SVG charts AND the TD-051 provenance (source/as-of tooltips + the
Data Sources footer) render — same as `orchestrate --html`:

```bash
python3 -c "import json, pathlib; from analysis_layer.render.html import render_html; p=pathlib.Path('<abs final .report.md>'); facts=json.loads(pathlib.Path('<abs bundle .facts.json>').read_text(encoding='utf-8')); h=p.with_suffix('.html'); h.write_text(render_html(p.read_text(encoding='utf-8'), facts=facts), encoding='utf-8'); print('html written to:', h)"
```

Optionally run the ④.3 HTML-integrity gate over the output (fail-closed; the live path
is calibrated to pass):

```bash
python3 -c "import json, pathlib; from analysis_layer.render.html import render_html; from analysis_layer.render.validate import validate_report_html; p=pathlib.Path('<abs final .report.md>'); facts=json.loads(pathlib.Path('<abs bundle .facts.json>').read_text(encoding='utf-8')); v=validate_report_html(render_html(p.read_text(encoding='utf-8'), facts=facts), facts_present=True); print('④.3:', 'PASS' if not v else v)"
```

## 6. Report the paths

Print the final `.report.md` and `.report.html` absolute paths. Note: the scaffold
`.md` and `.facts.json` remain on disk as the deterministic record.

## Guardrails

- Do NOT modify `analysis_layer/*` (extractors / aggregator / filler / orchestrate),
  the template, or any number. This command is wiring + agent writing only.
- The writer takes numbers ONLY from the `.facts.json`; the no-fabrication rule lives
  in its brief. If the returned markdown invented a number or filled a `[MANUAL]` slot,
  reject it and re-run step 2 once.
