---
schema_version: 1
description: Project-level invariants frozen into the system prompt at session start. Defines the 4-gate harness (subject_confirm, sec_email, freshness, language), the privacy invariants that protect the SEC contact email (I-003 lineage), reconciliation/DB/failure-cap rules, the incident loop, and the load-bearing design lessons from the B.0 restart. Do not violate without an explicit user instruction in the same turn.
---

# Stack Anamnesis — Project Memory

These rules are **load-bearing** and apply to every run. They are read once at session start and frozen verbatim into `meta/system_prompt.frozen.txt` (see `workflow_meta.json → memory_files`). `INCIDENTS.md` is loaded alongside this file at the same moment and into the same frozen prompt — it carries the project's institutional memory of past failure modes (one entry per incident, with the load-bearing rule that prevents recurrence). Read both. The contracts compose: anything in `INCIDENTS.md` overrides nothing here, and nothing here waives anything in `INCIDENTS.md`.

`references/equity_incidents_archive.md` (I-001..I-005, equity-research lineage) is **not** frozen and **not** enforced — it is reference material for what the pattern produces in a mature domain. This repo's `INCIDENTS.md` starts empty and accrues crypto-domain failures from I-001.

## P0 gates — the 4-gate harness (ordered, blocking, not skippable)

A run is fully specified by **four P0 gates** that fire strictly in order before any data fetch. Three are always-on; one (`sec_email`) is conditional. **There is no sticky mechanism and no `USER.md`** — every gate asks the user explicitly on every run, and nothing is remembered across runs.

1. **`P0_subject_confirm`** — always, the first gate. Resolves `subject_entity` (the analytical "I"), any `parent_or_issuer_entity` (context + the SEC trigger), and `user_confirmed_action ∈ {Y, N, skip_public_company}`. The agent queries `references/subject_relationships.yaml` and the web **in parallel** and presents a finding; it never asks "what subject_type is this?". `N` aborts the run cleanly (re-input → a new run; see Design lessons). SEC EDGAR is **forbidden** as a source here (chicken-and-egg: it needs the Gate 2 email).
2. **`P0_sec_email`** — the *only* conditional gate. Fires **only** when `user_confirmed_action == "Y"` AND `parent_or_issuer_entity.listed == true`; otherwise it writes `applies=false` (`source: applies_when_false`) and emits `phase_exit` so the chain never stalls — it does **not** ask. When triggered it asks for a contact email or `declined`. The email constructs a runtime-only `sec_user_agent`; see Privacy invariants.
3. **`P0_freshness`** — always. Window `∈ {7d, 30d, 90d, quarter, 1 year, since_TGE}`, single-select, no default. `since_TGE` = from the Token Generation Event date to today; `quarter` = current fiscal quarter (10-Q cadence).
4. **`P0_language`** — always, the last gate. `∈ {en, zh, both, side_by_side}`, single-select, no default. `both` → two parallel writers / two independent files (content may diverge by audience); `side_by_side` → one bilingual writer / one file (EN and CN semantically identical). Resolved only when `writer_mode_confirmed=true`. **Never** inferred from the chat language.

**Source authority.** Each resolved gate records a closed-enum `source` in `meta/gates.json` (`user_response` and the per-gate extras only). Forbidden values — `auto_mode_default`, `assumed_from_chat_language`, `inferred_from_prompt`, `inferred_from_locale`, `prefilled_for_speed`, `USER.md sticky`, or any invented string — are P0 violations caught at `P_INCIDENT_POSTCHECK` (the I-001 gate-bypass pattern). A non-answer after the gate's re-ask budget (subject_confirm: two; the others: one) emits `gate_unanswered` and **halts** — it never defaults to `en` / `30d` / `declined` / anything.

`workflow_meta.json` is the phase source of truth; **if anything here disagrees with the JSON, the JSON wins.** Per-gate behavioral spec: `references/research_dimensions.md` §2. Enforcement contract: `references/p0_gates.md`. The retired gate names — Phase A equity-era (`P0_intent` / `P0_lang` / `P0_sec_email` legacy / `P0_palette`) and the intermediate Gen-2 set (`P0_subject_class` / `P0_output_format` / `P0_scope`) — are residue, not live gates (tracked in `references/TODO.md` TD-018).

## Privacy invariants (load-bearing — I-003 lineage)

- **Two-User-Agent model.** `sec_user_agent` = `"StackAnamnesis/1.0 (<email>)"` is used for SEC EDGAR endpoints **only** (`*.sec.gov`, `data.sec.gov`, `efts.sec.gov`). **All** other outbound HTTP (DefiLlama, Dune, Etherscan family, CoinGecko, RPC tier, logos, news, IR pages) uses `public_user_agent`, which contains **no email and no PII**. Fetchers pick the UA by host; they never fall back to whichever is set. If `sec_email == "declined"`, `sec_user_agent` is null and SEC fetches are gated; `public_user_agent` is still used for everything else.
- **Email never persisted.** The contact email lives ONLY in process memory as `sec_user_agent` and is wiped on run termination. It never enters `meta/gates.json` (which stores only the `email_provided | declined` token), `meta/run.json`, logs, `USER.md`, or any git-tracked file. On resume, an `email_provided` token does **not** restore the email — the gate must re-ask. Each run requires fresh entry; no sticky, no cache.
- **DB email strip.** Before inserting any TEXT column, run `re.sub(r'\([^)]*@[^)]*\)', '()', value)` on `data_source` strings to strip embedded emails (User-Agent leak guard).
- **Enforced, not promised.** `tools/audit/user_agent_pii.py` (post-run) scans `meta/run.jsonl` and fetch logs and fails if the email appears alongside a non-SEC host or `public_user_agent` is missing/contains an email. `tests/test_db_pii.py` is a release-blocking regression: any TEXT column matching `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}` after a fixture run = test fails. See `references/data_source_registry.md` §6 and `references/equity_incidents_archive.md` I-003 for origin.

## Hard rules

- **Numerical reconciliation tolerance:**
  - margins / ratios / percentage points: ±0.5pp
  - currency amounts: ±0.5% relative
  - growth rates: ±0.5pp
  - prices, share counts, or any value tagged `"exact": true`: 0 tolerance

## Database write rules

- `P_DB_INDEX` runs only after `P12_final_audit` passes and `P_INCIDENT_POSTCHECK` reports `flagged: []`. Failed audits or flagged incident post-checks do not write to DB.
- All writes for one run are inside a single transaction; failure → rollback + `runs.run_status='failed'` + `db_export/index_error.json`.
- Append-only tables (`intelligence_signals`, `disclosure_quirks`) survive partial-run admission with an analyst note. (Equity-era table names; the crypto-domain schema may rename or supersede these — the *invariant* (append-only survives partial admission) is load-bearing, the *table names* are not.)
- Cross-validation queries (`db/queries.py`) filter on `runs.run_status='complete'` by default; partial rows exist for audit only.

## Failure caps

- Subagent timeouts: research 600s / photo 300s / QC 180s; first timeout retries at ×1.5; second timeout = phase failure.
- `P12` has no auto-retry — failures surface to the user with paths and a "which upstream phase to re-run" question.

## Incident loop (load-bearing)

- `P_INCIDENT_PRECHECK` runs **before** `P0_subject_confirm` (the first gate). It first runs `tools/io/lint_incidents.py` (exit 0 required), then reads `INCIDENTS.md` end-to-end and writes one `incident_precheck.acknowledged` event to `meta/run.jsonl` per active entry (`incident_precheck.skipped` for superseded entries).
- `P5_7_RED_TEAM` and `P10_7_RED_TEAM` run two adversarial agents in parallel (`agents/attackers/red_team_numeric.md`, `red_team_narrative.md`). They are **not** QC peers — QC peers vote, attackers try to falsify. Critical findings loop the writer once (cap = 1 per phase); a second critical halts the run.
- `P_INCIDENT_POSTCHECK` runs **after** `P12_final_audit` and **before** `P_DB_INDEX`. The orchestrator re-reads `INCIDENTS.md` and confirms each entry's detection signal is green for this run. A flagged post-check blocks DB write — a relapse on a known incident is a release-blocking event.
- New failure modes are captured by the user via the `/log-incident` slash command (spec at `.claude/commands/log-incident.md`, backend at `tools/io/log_incident.py`). The model drafts an `INCIDENTS.md` entry; the user confirms; only then is it appended. Append-only — never delete or rewrite past entries; supersede with a new entry if needed.

## Design lessons (load-bearing methodology)

These are the lessons the B.0 restart paid for. They are maintainer-facing design discipline, not per-run gates — read them before extending the harness. Each traces to a worked origin in `references/TODO.md`; the Anamnesis Pattern applied to the harness's own design.

- **Different prompt = different run.** When a gate's processing implies the user's intent warrants a different prompt (e.g. narrowing a sector ask to a single subject), the move is **abort + ask the user to re-run**, not an internal restart-from-gate with prompt substitution. One prompt = one run = one clean audit trail. This is why `P0_subject_confirm`'s `N` aborts rather than re-prompting in place (TD-015 closed as unnecessary).
- **Challenge the inherited framework.** When forking a harness for a new domain, the inherited framework's shape (gate count, abstractions) must be re-derived against the *new* domain's actual workflow, not silently adopted. The 7-gate framework was equity-era over-engineering; walking the crypto workflow end-to-end exposed 3 gates as dead weight and produced the 4-gate set. Detection signal: if you can't immediately say "what does GATE_X do for THIS user's workflow," it may be over-engineering.
- **"Human readability" is not a default assumption.** Before optimizing a spec file for human readability, ask "who reads this file directly, and when?" In agent-mediated workflows users interact via agent translation, so direct reads are rare. This is why `subject_relationships` was split into data (`.yaml`) + design (`.md`) instead of a markdown+YAML hybrid that would have needed a parser to write.
- **Mid-flight course corrections are first-class moves.** When a foundational assumption is challenged mid-deliverable, pause and steel-man the challenge *before* editing files. Catching a wrong design mid-flight (the 4-gate restart cost ~5.5 sessions) is far cheaper than unwinding it after it has propagated (~12+ sessions). Pausing is not thrash — it is the cheapest point to catch a wrong design.
- **Prefer reality over the literal prompt.** When a prompt asserts something about external reality — an API endpoint, an identifier like a CIK or slug, a response field name, a third-party tool's behavior, a "canonical sibling" to copy — that assertion is a starting *hypothesis*, not ground truth. Verify before building. Silent build-on-stale-info ships wrong data; live-verify-then-surface-divergence is the discipline. This is the generalization of the narrow B.0 "prefer the sibling pattern over a prompt typo" lesson (TD-023). The detail below has teeth because B.2 (orchestrator + analysis layer) is full of "the prompt says X, but reality is Y" moments — API endpoint changes, response-shape evolution, library-behavior shifts — and a vague lesson won't trigger on them.

  **When this applies:**
  - Any API endpoint URL, response shape, or field name a prompt names.
  - Any "known fact" about a third-party system (IDs, slugs, CIKs, contract addresses, blockchain block heights).
  - Any "do X like the canonical sibling" reference — verify the sibling actually exists / is current; the sibling file may have moved or been renamed.
  - Any "trust the top result" / "use `data[0]`" instruction — verify the list has *actual* collision protection, not just hopeful ranking.
  - Any "the rate limit is N req/sec" claim — verify with actual responses, not docs alone.

  **How to apply (priority order):**
  1. **Probe live before writing fetcher code.** A 30-second `requests.get` / `curl` is cheaper than a 1-hour build on a wrong assumption. If the endpoint is auth-gated, do a single auth'd probe to confirm shape before committing to it.
  2. **Cross-reference canonical sources in the repo** (registry, spec files, prior siblings). If the prompt and a canonical source disagree, the canonical source is *more likely* right but not definitely — verify against live reality if material to the build.
  3. **Web-search current API behavior** when probing isn't safe (paid tiers, destructive endpoints). Even one search result confirming the API moved is enough signal to surface and propose a fix.
  4. **Surface the divergence in the agent response.** Do NOT silently rewrite the envelope shape, the resolution logic, or the endpoint URL. Show prompt-said vs reality-says, then propose the fix. The surfacing is half the value: it updates the user's mental model.
  5. **Document the divergence in the shipped artifacts** — module docstrings, spec files, inline comments — so the next reader knows why the code disagrees with what a literal reading of the prompt would suggest.

  **What this is NOT:**
  - Not license to ignore the prompt's *intent*. The intent (e.g. "resolve subject slug-first to defeat symbol collision") is sacred; the *mechanism* (e.g. "via `/map?slug=`") is the falsifiable claim that may need correcting.
  - Not license to silently improve the prompt without surfacing. The surfacing makes the user aware their mental model needs updating; silently fixing it deprives them of that signal.
  - Not an invitation to question every prompt detail before building. Apply when (a) the detail is verifiable in <5 minutes, AND (b) shipping wrong would be expensive (silent wrong data, security issue, >30 minutes of rework). Routine details ("use lowercase variable names") don't trigger this.

  **Tactical heuristic:** if a verification step would take <5 minutes and the build step would take >30 minutes, verify first. Always.

  **Provenance (8 applications across B.0 + B.1):**
  1. **B.0 Step 3d language_gate** — prompt referenced a sibling file path that didn't exist; agent followed the *intent* (use the canonical sibling pattern), not the literal broken path.
  2. **B.1.0 SKILL.md sweep reframe** — prompt mentioned "Gen 1/Gen 2 residue cleanup"; the actual residue was the equity→crypto frontmatter reframe. Agent extended the cleanup to the right *semantic* boundary, not the literal Gen-numbering.
  3. **B.1.2 CoinGecko symbol collision** — prompt said "trust top `/search` result"; agent live-verified "Bitcoin" → meme coin `harrypotterobamasonic10in` (rank 900). Changed resolution to symbol-or-name with `market_cap_rank` tiebreak.
  4. **B.1.3 Etherscan invalid-key detection** — prompt said "check `message` field for invalid-key signal"; Etherscan actually puts the diagnostic in `result`, not `message` ("NOTOK" in `message` is generic). Fixed `_is_invalid_key` to scan both fields.
  5. **B.1.3 Etherscan address case normalization** — prompt didn't specify case; agent noticed the symbol-registry path returned checksum case but the 0x path lowercased. Unified to lowercase per registry §3.
  6. **B.1.4 SEC EDGAR Circle CIK** — prompt's mini-registry had Circle CIK = `0002000010` (which is BVAF REIT); registry §6 said `0001876042`. Agent verified against live SEC API and corrected all 3 source files. **Without this catch, every Circle research run would have shipped REIT data silently.**
  7. **B.1.6 CMC slug-first resolution (compound: 3 spec errors at once)** — accepted-fix prompt said `/map?slug=` resolves slug + tiebreak by `cmc_rank` + `data[0]["id"]`. Agent live-probed and found: (a) `/map` silently ignores `slug` (returns all 8362), (b) `/map`'s field is `rank` not `cmc_rank`, (c) `/quotes/latest?slug=` returns a dict `{id: coin}` not a list. Rewrote against verified reality.
  8. **B.1.7 L2Beat endpoints deprecated** — registry §12 documented `/api/tvl.json` + `/api/[project].json` (both 404'd live). Agent probed 4 candidate endpoints, found `/api/scaling/summary` as the live surface, redesigned the fetcher around it, documented the divergence in the `.py` docstring + `.md` spec.

  **Score:** 5 of 8 applications (#3, #4, #6, #7, #8) caught real bugs that would have shipped wrong data. The other 3 (#1, #2, #5) prevented ambiguity or maintenance debt. Hit rate high enough that this pattern is foundational, not incidental.

  **Cross-references:** `references/data_source_registry.md` (the canonical-source anchor); `INCIDENTS.md` (where wrong-data events would be recorded if not caught). Worked origin: `references/TODO.md` TD-023.

## What this project does NOT do

- No skill self-improvement / DSPy / GEPA optimizer. Auditability beats agility.
- No code-execution sandbox. Everything is a registered tool; LLM cannot exec arbitrary Python.
- No multi-tenant routing. Single-user, local SQLite, single process.
- No streaming UI. CLI in, files out.
- No sticky preferences and no `USER.md`. Every gate asks every run (see P0 gates).
