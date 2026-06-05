---
description: Forward-looking design notes deferred until the fork stabilizes. Each entry is a deliberate non-decision recorded so it does not get lost — not a generic backlog.
---

# stack-anamnesis — Deferred Design Notes

## TD-001 — X long-post delivery: quality rubric + red-team, not SHA-locked template

**Decision (2026-05-11):** The X (Twitter) long-post / thread emitter will NOT use the SHA256-pinned locked HTML template approach inherited from equity (I-002 lineage in `references/equity_incidents_archive.md`). Use instead:

- **Quality rubric** — checklist of required structural elements per post type (hook / claim / evidence / counter / CTA), enforced as a fail-closed validator analogous to the role `validate_report_html.py` plays for reports, but operating on prose structure rather than HTML SHA.
- **Red-team narrative attacker** — repurpose the existing `red_team_narrative.md` pattern to attack hooks, claims, and missing counter-evidence in the post draft.
- **Key-element post-check** — at delivery, verify each rubric element is present and non-degenerate (not a placeholder, not under length floor).

**Why:** SHA pinning fits HTML reports because the visual layout *is* the contract; for X posts the *content shape* is the contract, and a SHA pin would either be too rigid (every wording change breaks the pin) or meaningless (any text passes a SHA check on an outer wrapper). Rubric + narrative red-team + element post-check is the right shape for free-form prose with a strict structural skeleton.

**Revisit when:** the first X long-post phase is being designed.

## TD-002 — Sector / comparison scope expansion (Phase C)

**Status:** active (re-scoped 2026-05-20 during B.0 pre-Step-4 
cleanup audit; original P0_scope framing removed).

The 4-gate design supports single-subject research only. Sector 
research (e.g., "stablecoin issuer landscape") and comparison 
research (e.g., "compare USDC vs USDT") are deferred to Phase C.

**Required for Phase C:**
1. Extend the harness to accept multi-subject prompts (sector scope) 
   and explicit comparison prompts (comparison scope).
2. Update subject_confirm_gate.md (or successor) to detect sector / 
   comparison intent and route accordingly.
3. Add output dispatch for sector reports (one report covering a 
   group of subjects) and comparison reports (parallel analysis of 
   2+ subjects).
4. Determine whether sector/comparison reports reuse the deep-dive 
   template or get distinct templates.

**Why deferred:** Phase B scope was deliberately narrowed to 
single-subject research during the mid-flight restart from 7-gate 
to 4-gate. Multi-subject is a Phase C expansion, not a B-series 
patch.

**Original framing (preserved for audit):** opened during 7-gate 
era when P0_scope was an active gate enforcing single-subject 
ritual. P0_scope was eliminated in the 4-gate redesign; sector 
deferral logic moved to phase-level scope (Phase C handles it, 
no gate enforces it in Phase B).

**Revisit when:** Phase C begins.

## TD-004 — Add issuer attestation feeds to data_source_registry

**Decision (2026-05-12):** data_source_registry starts with four core APIs + RPC tier. Issuer attestation feeds (Circle transparency, Tether reserves, Paxos attestations) are deferred to a separate entry.

**Why deferred:** each issuer publishes attestations in inconsistent shapes (PDF reports, HTML pages, JSON APIs). Designing uniform fetching across them is non-trivial and shouldn't bottleneck Phase A.

**Workaround in the meantime:** agents can use web_fetch to grab issuer transparency pages on demand, with the URL noted in the report's source list. RPC tier covers the on-chain truth side (verifying reserve balances), so 80% of attestation research is already possible.

**Revisit when:**

- First stablecoin issuer research run produces an incident around "couldn't verify reserve composition", OR
- 3+ runs require manual transparency page parsing

## TD-005 — Add CEX APIs (Binance, Coinbase) when listing/flow research warrants it

**Decision (2026-05-12):** CEX APIs not included in v0 registry. Most exchange-related data (volume, listing status, price) is available from CoinGecko without API key complexity.

**Why deferred:** CEX APIs require API key management, auth rotation, and per-exchange rate-limit handling — significant engineering load for coverage that overlaps ~80% with CoinGecko.

**Revisit when:**

- Custody flow research (how much USDC sits on Coinbase vs in self-custody) becomes a recurring need, OR
- Proof-of-reserves analysis across multiple CEXes is required, OR
- An incident logs "CoinGecko data insufficient for [specific question]"

## TD-006 — Re-establish locked-skeleton HTML template discipline when crypto report skeleton is designed

**Decision (2026-05-12):** Removed the "Locked HTML template" Hard Rule from `MEMORY.md`. The deleted rule pinned `skills_repo/er/agents/report_writer_{cn,en}.md` to a SHA256-pinned skeleton and required P5 to extract via `tools/research/extract_template.py` and substitute `{{PLACEHOLDER}}` only. That contract is equity-domain-specific and has no live surface in this fork until a crypto-domain report template exists.

**Why:** "A rule that is not enforceable in code is not a rule, it is a wish" (`references/inherited_principles.md`). With no crypto report skeleton, no `extract_template.py` invocation, and no SHA pin to enforce, the inherited bullet was advisory text masquerading as a hard rule — exactly the kind of memory inflation the Anamnesis Pattern is designed to prevent. Keeping it in `MEMORY.md` would also bake "the equity report shape" into the harness's frozen prompt, biasing future crypto report design.

**Revisit when:**

- The first `output_format: report` run is designed and a crypto-tailored HTML skeleton lands in the repo, OR
- A red-team incident logs "writer hand-crafted HTML instead of filling the skeleton" — at which point this rule re-enters `MEMORY.md` with the crypto skeleton's SHA pin and the new `extract_template.py` invocation path

## TD-007 — Decide QC merge math + competitive framework (Porter or replacement) in Phase B

**Decision (2026-05-12):** Removed the `## QC scoring math (P3.6)` section (the `weighted = 0.34·draft + 0.33·peer_a + 0.33·peer_b` rule with `|delta| > 1.00` change-or-maintain semantics) and the `## Porter score orientation` section (threat-scale 1–5; intense rivalry = high red) from `MEMORY.md`. Both are equity-research artefacts. The QC math assumed the draft+two-peer triangle from `skills_repo/er/agents/qc_*`; Porter's five forces were the canonical equity competitive frame.

**Why:** Crypto subjects may not fit Porter cleanly — a chain's "rivalry" is not the same shape as a public company's; an `agentic_payment_layer`'s "supplier power" is barely meaningful. The right competitive frame for stack-position-defensibility research may be Porter as-is, a modified Porter with crypto-specific forces, a new stack-position-defensibility rubric, or no framework at all. Deciding this in Phase A would foreclose the Phase B design exercise; keeping the equity-era math in `MEMORY.md` would gravitationally pull any new frame toward equity shape.

**Revisit when:**

- Phase B picks a competitive-analysis frame for crypto subjects, AND
- The QC peer agents (or their replacements) are wired into that frame — at which point the chosen scoring math re-enters `MEMORY.md` alongside the framework

## TD-008 — Re-introduce card-pack hard rules as a block when card production returns

**Decision (2026-05-12):** Removed three card-pack Hard Rules from `MEMORY.md`:

- "Logo save order" (P7 must create the cards/ directory, save `logo_official.png`, set `logo_asset_path`, only then proceed).
- "Palette consistency" (all six cards in one run must use the same `--palette`; palette is **not** stored in `card_slots.json`).
- "No fallback copy generation in EP" (`card_slots.json` must be complete before render; missing keys abort at load time).

These belong to the inherited EP (Equity Photo) pipeline's P7..P11 phases. With `P0_palette` retired and the card pipeline dormant in Phase A (`output_format` enum is `{report, thread}` only; no `cards` value), these rules guard a surface that does not currently exist.

**Why:** Card production is deferred to Phase C — see the Phase-A `P0_output_format` decision to ship without `cards`. Hard rules that protect a dormant pipeline create memory clutter and confuse future-us about which guardrails are live. The rules themselves are correct and load-bearing *when* card production is live; they should re-enter `MEMORY.md` as a block at that time, not piecemeal.

**Revisit when:**

- `output_format` enum widens to include `cards` (or equivalent), AND
- The card-production pipeline is being re-implemented for the crypto subject classes — at which point all three rules return as a block, repalleted and renamed for the crypto card design

## TD-009 — Re-introduce secret-handling discipline (model on retired SEC EDGAR rule) when first secret-requiring crypto API is integrated

**Status:** **closed 2026-05-13** by B.0 #1.5 — pattern instantiated for SEC EDGAR in `references/data_source_registry.md` §6 (re-added as the sixth registered source with the I-003-style two-UA contract: `sec_user_agent` for `*.sec.gov` hosts only; `public_user_agent` PII-free for everything else). The MEMORY.md privacy-invariant bullet returns in B.0 #16 (MEMORY.md rewrite). Template preserved here as forward reference for the next secret-requiring source (Dune API key, Etherscan/Alchemy/Infura/QuickNode keys, Pro CoinGecko key) when those land in B.1.5+.

**Decision (2026-05-12):** Removed the SEC EDGAR email privacy bullet from `MEMORY.md`'s `## Privacy invariants` section. The deleted bullet stated: "SEC EDGAR email is **never** persisted. It lives only as a runtime arg to `tools/research/sec_edgar_fetch.py`." With `P0_sec_email` retired and SEC EDGAR not a crypto-domain data source, the rule has no live surface.

**Why:** The *shape* of the rule (never-persist, runtime-only, regex redaction guard with a `tests/test_db_pii.py` regression) is the right template for any future API key or credential the crypto harness needs — Dune API key, Alchemy/Infura/QuickNode keys, Etherscan family keys, Pro CoinGecko key, RPC bearer tokens (see `references/data_source_registry.md` for the full key inventory). But the SEC-specific instance does not apply. Removing it now and re-introducing the pattern when the first secret-requiring API is integrated keeps the harness from carrying a dead rule while preserving the template's existence as this TD.

**Revisit when:**

- ~~The first secret-requiring crypto API is integrated~~ — fulfilled by SEC EDGAR re-add in B.0 #1.5.
- The next non-SEC secret-requiring API is integrated (Dune, Etherscan, CoinGecko Pro, or any RPC tier) — re-open as TD-009b or a new TD for that key family. The shape of this entry is the template: per-source key file (`~/.config/anamnesis/<provider>.key`), per-source redaction guard, `tests/test_db_pii.py`-style regression.

## TD-010 — Phase B harmonization pass: stale MEMORY.md references in orchestrator.md §P1+ and HARNESS.md ownership table

**Decision (2026-05-12):** orchestrator.md:174 references "QC scoring math from MEMORY.md" (the equation deleted in Phase A per TD-007), and HARNESS.md:240 lists "Locked HTML template" in an ownership table (the hard rule deleted in Phase A per TD-006). Phase A's scope discipline (P0-only) left these untouched. Both will be resolved during Phase B's broader orchestrator §P1+ and HARNESS rewrites.

**Revisit when:** Phase B redesigns the P1+ pipeline (which will rewrite orchestrator §P1+ end-to-end) and the HARNESS overview (which will rebuild the ownership table for the crypto-shaped pipeline).

## TD-011 — Validate seed CIKs on first SEC EDGAR fetch

**Decision (2026-05-13):** Coinbase, Galaxy Digital, Marathon Digital, and Robinhood entries in `references/subject_relationships.yaml` were drafted in B.0 #2 from non-SEC public sources only (the path-(a) workflow restriction is strict: agent may not consult SEC EDGAR to verify SEC-listing facts because `P0_sec_email` has not yet fired). Their `sources:` URLs are investor-relations pages, not EDGAR filings. The CIKs are not yet recorded; the `note:` field on each entry flags this.

**Why:** Path (a)'s restriction (no SEC EDGAR) is load-bearing — it prevents a chicken-and-egg dependency where the table entry needed to fire the gate is itself fetched via the gate's downstream API. The honest state of the table is "drafted from public sources; SEC verification pending first run".

**Required action when the first SEC EDGAR fetcher invocation lands** for each entity in B.1+: verify the CIK against EDGAR, update the entry with `sources: + <SEC EDGAR URL with CIK>` (don't replace existing sources, append), and refresh `confirmed_at: <that run's date>` so `next_review_due` slides forward by 6 months. If the CIK lookup returns a name mismatch, surface as an incident (the entry's listed-claim is wrong and the gate fired on bad data).

Circle's CIK (`0001876042`) is already user-confirmed and does not need re-verification.

**Revisit when:** B.1's first SEC EDGAR fetcher lands and runs against any of (Coinbase, Galaxy Digital, Marathon Digital, Robinhood).

## TD-012 — Implement subject_relationships.yaml lint tool

**Decision (2026-05-13):** `tools/io/lint_subject_relationships.py` is referenced in `references/subject_relationships_design.md` as the pre-check lint surface but does not yet exist. Authoring it in B.0 is out of scope (B.0 is documentation + agent contracts, no new tooling); B.1's first SEC EDGAR fetcher is the natural pairing because that's when the table starts changing under real runs. Lints the data file `references/subject_relationships.yaml` (pure YAML; `yaml.safe_load` parse — no markdown parsing needed since the B.0 mid-flight split moved design rationale to a separate `_design.md` file).

**Required behaviour:**

- Validate `schema_version: 1`.
- For every entry, validate required fields are present and well-shaped: `subject_entity_type`, `listed` (bool), `confirmed_by` (`user` or `user_direct`), `confirmed_at` (ISO date), `next_review_due` (ISO date), `sources` (non-empty list of URLs), `relationship_to_subject` (string, defaults `self`).
- When `listed: true`, `ticker` and `exchange` must be non-null strings; when `listed: false`, both must be `null`.
- `next_review_due >= confirmed_at` and `next_review_due <= confirmed_at + (review_cadence_months OR 6) + 14d` drift tolerance. The optional `review_cadence_months` field overrides the default 6-month cadence — Stripe's seed entry sets `review_cadence_months: 3` due to active IPO speculation; the lint must read the structured field, not parse the prose `note:`.
- Every URL in `sources:` resolves via HEAD request (allow `200/301/302`; warn on `4xx/5xx/timeout`).
- `pending_fill[].name` does not collide with any `entries:` key.

**Run surfaces:**

- `P_INCIDENT_PRECHECK` at run start (warn on stale `next_review_due`, error on missing required fields).
- Commit-time hook (so edits to `subject_relationships.yaml` are linted before commit).
- Manual invocation: `python tools/io/lint_subject_relationships.py [--check-urls]`.

**Revisit when:** B.1 SEC EDGAR fetcher lands (paired implementation).

## TD-013 — Implement append_subject_entry.py atomic write tool

**Decision (2026-05-13):** `tools/io/append_subject_entry.py` — thin wrapper around `yaml.safe_load` / `yaml.safe_dump` on `references/subject_relationships.yaml`, with atomic write (temp file + `os.replace` rename). Adds an entry under `entries:`, preserves alphabetical key order, removes the corresponding `pending_fill[]` stub if one exists, and refuses to overwrite an existing entry without an explicit `--update` flag. B.1 paired with the first SEC EDGAR fetcher (entries start changing under real runs at that point).

**Why it is its own TD:** the write tool is called from `agents/subject_class_resolver.md` path (a) step 4 and path (c) step 3. Authoring it in B.0 is out of scope (B.0 = documentation + agent contracts, no new tooling).

**History:** Original TD-013 scope was a 9-step parser-based tool targeting a markdown+YAML hybrid format. Reduced mid-flight in B.0 when data and design were split into separate files (`subject_relationships.yaml` + `subject_relationships_design.md`), eliminating the parser need. See "B.0 #16 MEMORY.md staging — pending lessons" below for the design lesson that drove the split.

**Revisit when:** B.1 SEC EDGAR fetcher lands (paired implementation, alongside TD-012).

## TD-014 — Consolidated event vocabulary registry

**Status:** **close-as-unnecessary 2026-05-13** during B.0 mid-flight restart to 4-gate design.

Original premise: 7-gate framework introduced 11+ meta/run.jsonl event names across agents, raising drift and forgotten-consumer concerns. User identified that 7-gate design was over-engineering inherited from Phase A; simplified 4-gate design has far fewer events. The drift risk that motivated TD-014 is substantially reduced.

**Resolution:** 4-gate design's event vocabulary is small enough to maintain inline in each agent file's "Events" section without a separate registry. If event count grows to 15+ in future phases (B.5+ red team, B.6 validator), revisit.

**Preserve as audit trail because:** the consolidated registry pattern itself may be valuable when event count grows. Reopen with explicit new justification (e.g., "we now have 20+ events across 8 agents and drift is occurring") rather than silently revive.

**History:** opened 2026-05-13 during 7-gate framework design; closed same day during mid-flight restart to 4-gate design.

## TD-015 — Orchestrator support for restart-from-gate

**Status:** **closed-as-unnecessary 2026-05-13** during B.0 #6 review.

Original premise: `scope_gate` path (a) narrow needed an internal restart-from-gate mechanism to continue the same run with a narrowed prompt. User challenged this design as overengineered given that the sector pipeline is not implemented and the narrowed prompt is genuinely a different prompt, not the same one "fixed".

**Resolution:** path (a) was redesigned to abort the current run and ask the user to re-run with the new prompt as a fresh single-pipeline run. No orchestrator restart mechanism needed.

**Preserve as audit trail because:** if a future scenario genuinely needs restart-from-gate semantics (e.g., a writer agent discovers a Part 4.1 lineage gap and needs to revise `parent_or_issuer` mid-run), this TD documents the prior consideration and its negative resolution. Reopen with explicit new justification; do not silently revive.

**History:** original decision (2026-05-13) closed within the same session by a user mid-flight correction.

---

## TD-017 — Extend subject_relationships.yaml schema for token entries

**Status:** active 2026-05-13 (opened during B.0 Step 3c review).

Current subject_relationships.yaml schema is company-centric — all 6 seed entries (Circle, Coinbase, Stripe, Galaxy Digital, Marathon Digital, Robinhood) are subject_entity_type: company with fields {listed, ticker, exchange, parent}. No token entries; no tge_date field exists.

agents/freshness_gate.md Step 1 reads {Subject}.tge_date from the yaml to compute the since_TGE hint sentence ("USDC 的 TGE 是 2018-09-26, since_TGE 会拉 ~8 年完整历史."). With no tge_date in the schema, the hint silently omits — graceful degradation works, but the user-facing since_TGE option loses helpful context.

**Required:**

1. Add `tge_date: <ISO date>` field to entries of subject_entity_type: token (and asset/coin where applicable).
2. Optionally: add `token_symbol` field for tokens whose ticker differs from primary name (e.g., USDC issued by Circle).
3. Backfill tge_date for at least a few high-priority tokens (USDC, USDT, ETH, BTC, etc.) so freshness_gate's since_TGE hint becomes useful for common research subjects.
4. Update references/subject_relationships_design.md to document the extended schema (token entry shape).

**Why deferred:** B.0 scope is design + agent spec; no data file schema extensions. Extending the yaml schema would require updating multiple cross-referenced files (research_dimensions.md, subject_relationships_design.md) and is appropriately B.1 work.

**Revisit when:** B.1 first token-based research is attempted (USDC, USDT, etc.) — the missing tge_date hint will be immediately noticeable in user-facing prompts. Bundle the schema extension with that first fetcher work.

**History:** Surfaced during B.0 Step 3c review of agents/freshness_gate.md.

---

## TD-018 — Gen 1/2 residue sweep across SKILL/README/phase_contract/maintenance/workflow_diagram/incident_trigger

**Status:** active 2026-05-20 (opened during B.0 pre-Step-4 cleanup audit).

The mid-flight restart from 7-gate to 4-gate design deleted the in-progress 7-gate agent files (commit 7c2d42a) but left Phase A equity-era and Phase B 7-gate references in several files that were not part of the restart's deletion scope:

1. ~~**SKILL.md** — still references Gen 1 gates: P0_lang, P0_sec_email, P0_palette, USER.md sticky mechanism.~~ **DONE in B.1.0 (commit pending)** — Gen 1/2 residue swept: P0 section rewritten to the 4-gate flow (subject_confirm / sec_email / freshness / language), `USER.md` boot-order entry + sticky-source mechanism removed, retired `palette gate` dropped, ER/EP lazy-load note de-equitized. Added a data-sources subsection (13-source registry, 11 active per TD-021) and the I-003 two-UA invariant. Frontmatter + intro reframed equity → crypto domain. Residue grep (`P0_lang|P0_palette|P0_output_format|P0_scope|P0_intent|P0_subject_class|USER\.md|skills_repo`) is now clean. (Note: `db/equity_kb.sqlite` retained verbatim — it is the real DB filename, not a doc reference; rename is a separate code task.)
2. **references/phase_contract.md** — references Gen 2 gates: P0_output_format, P0_scope. (Scheduled for Step 5 rewrite; this TD overlaps but tracks the residue specifically.)
3. **references/maintenance.md** — equity locked-template / submodule discipline (Gen 1 framing).
4. **references/workflow_diagram.md** — Gen 1 interactive gates + USER.md references.
5. **tools/io/incident_trigger.py:75** — emits P0_lang / P0_sec_email / P0_palette in an incident message (Gen 1 phase names).
6. **README.md** — references `skills_repo/er/ep` submodule architecture and USER.md.template (both removed).
7. **workflow_meta.json P11_render constraint** — contains `"constraint": "palette must equal P0_palette"` referencing the deleted P0_palette gate. Part of the broader P7-P11 card pipeline question (whether crypto research needs card output at all). Defer until card pipeline scope decision is made for B.5+ or later. Surfaced during B.0 Step 5 Sub-task 5A review.

**Why deferred:** these files are each scheduled for rewrite in a later step or sub-phase. SKILL/README/HARNESS rewrites are appropriate for end-of-B.0 or B.1 start; phase_contract.md is Step 5; maintenance/workflow_diagram are pending rewrite alongside Phase B documentation pass. Touching them piecemeal during pre-Step-4 cleanup would mix concerns.

**Required:** during each file's scheduled rewrite, sweep Gen 1/2 residue identified above. Add a verification step to the rewrite checklist: grep the file for `P0_lang|P0_palette|P0_output_format|P0_scope|USER.md|skills_repo|equity` and confirm each hit is intentional (archive citation, history note) or fixed.

**Revisit when:** each file's scheduled rewrite step lands. For coordination, list affected files in the rewrite step's commit message.

**History:** Surfaced during B.0 pre-Step-4 cleanup audit (2026-05-20) when agent surveyed Phase A residue category. The 4-gate spec layer is internally clean; residue is in older layer files awaiting rewrite.

---

## TD-020 — B.1 verification of Medium-confidence data source entries

**Status:** active 2026-05-21 (opened during B.0 Step 4 review).

Three of the seven conditional non-core sources (§7-§13) were flagged Medium confidence during agent web research:

1. **§7 Artemis** — Domain inferred as api.artemisanalytics.com (incorrect; verified correct is artemis.ai during Step 4 review against artemis.ai/docs/welcome/overview). Product surface incomplete (only API mentioned; actually 5 products: Terminal, Sheets, API, Snowflake Share, Research). Specific data scope numbers inferred.

2. **§9 Allium / Nansen** — Enterprise pricing cited from secondary source; chain count cited because sources disagreed.

3. **§12 L2Beat** — Undocumented API endpoints from 2021-2023 forum thread; may be stale. Entry warns to validate per run.

**Required:** when B.1 writes each fetcher (agents/fetchers/artemis_fetcher.md, allium_fetcher.md, nansen_fetcher.md, l2beat_fetcher.md), the first action is:
1. Verify the registered domain resolves and returns valid data.
2. If incorrect, update data_source_registry.md §N inline as part of the fetcher commit (atomic correction).
3. Confirm rate limit and auth model against current official docs.

**Known Artemis corrections to fold into B.1:**
- Domain: artemis.ai (not artemisanalytics.com)
- Products: Terminal, Sheets, API, Snowflake Share, Research
- Customers include: McKinsey, T.Rowe, VanEck, Visa, Circle, Sequoia

**Why deferred to B.1:** B.1 fetcher writes naturally trigger API verification; bundling registry correction with fetcher write is one atomic edit. Rewriting registry now without fetcher context risks introducing different inaccuracies.

**History:** Surfaced when user verified §7 Artemis against artemis.ai/docs/welcome/overview during Step 4 pre-commit review.

---

## TD-021 — Archived paid-only data sources (Token Terminal, Allium/Nansen)

**Status:** active 2026-05-21 (opened during B.0→B.1 transition).

Three of the seven conditional data sources in `references/data_source_registry.md` §7-§13 are archived for B.1 due to paid-only access:

- **§8 Token Terminal** — paid API plan (free account = UI browsing only; programmatic access requires paid plan, price not public).
- **§9 Allium** — enterprise sales only (~$5k+/month, no self-serve free tier).
- **§9 Nansen** — credit-based pricing ($100+ minimum for meaningful usage).

**Why deferred:** the user's current research workflow operates under free-tier constraints. The 4 remaining conditional sources (Artemis Lite, Electric Capital, Messari free, L2Beat undocumented, CoinMarketCap Basic) cover the conditional surface needed for B.1's first research runs.

**Architectural impact for B.1:** fetchers will be written for the 6 core sources (§1-§6) plus 5 active conditional sources (§7 Artemis, §10 Electric Capital, §11 Messari, §12 L2Beat, §13 CoinMarketCap) — 11 active fetchers total. Token Terminal (§8), Allium and Nansen (§9) spec entries remain in data_source_registry.md untouched; their ARCHIVED status will be added to the registry entry inline at the time the corresponding fetcher would otherwise be written (atomic decision + registry update + TD-021 reference, one commit per affected source's deferral).

**To unarchive any of the three:**
1. Purchase the required access (API plan / credits / enterprise contract).
2. Update the `Status:` line in data_source_registry.md from ARCHIVED to ACTIVE with the purchase date.
3. Write the corresponding fetcher: `agents/fetchers/<source>_fetcher.md` + `tools/fetchers/<source>_fetch.py`.
4. Update TD-021 (this entry) to log which source was unarchived.

**Coverage gaps from archiving:**
- **Standardized financial metrics across protocols** (P/S, P/E ratios) — Token Terminal's specialty. Workaround: compute from DefiLlama revenue + market cap manually.
- **Wallet labels + Smart Money tracking** — Nansen's specialty. Workaround: Etherscan + RPC give raw addresses without labels.
- **Warehouse-scale on-chain data** — Allium's specialty. Workaround: Dune covers ~80% via SQL queries.

**Revisit when:** the user has budget for one of these, OR enters an enterprise context (e.g., a job at a fund that licenses these tools).

**History:** Decision made 2026-05-21 during B.0→B.1 transition when user verified the paid-vs-free split of conditional sources. Aligns with cost-aware research workflow constraint that motivated selecting open-source / free-tier sources where possible.

---

## TD-023 — Land "prefer-intent-over-literal-prompt" lesson in MEMORY.md

**Status:** CLOSED 2026-05-25. Landed in MEMORY.md as "Prefer reality 
over the literal prompt" (B.1 completion turn). Generalized beyond the 
original 3-instance scope to 8 applications across B.0 + B.1.0–B.1.7; 
5 of 8 caught data-correctness bugs. Historical body retained below.

**Status (historical):** active 2026-05-23 (opened during B.1.2 review).

The pattern has now surfaced three times in B-phase across different 
domains, each time a judgment-call deviation from a prompt's literal 
instruction produced a strictly better outcome:

1. **B.0 Step 3d (language_gate)** — agent preferred the sibling 
   pattern over a prompt deviation that read like a typo. Surfaced 
   the divergence explicitly rather than silently following the 
   prompt. (Existing MEMORY.md lesson #1: "prefer-pattern-over-prompt".)
2. **B.1.0 SKILL.md sweep (commit 031a506)** — prompt said "sweep 
   Gen 1/2 residue"; agent extended sweep to include the equity→crypto 
   frontmatter reframe, recognizing that domain residue at the skill 
   activation surface was the same category of residue at a different 
   conceptual layer.
3. **B.1.2 CoinGecko resolution (commit pending)** — prompt said 
   "pick top exact-symbol match"; following literally produced a 
   wrong result (meme coin matching the symbol "BITCOIN" beat real 
   Bitcoin). Agent changed to "match symbol or name, tie-break by 
   market_cap_rank" — the canonical intent. Added regression test.

**Why this needs to land:** instance 1 is already in MEMORY.md as 
the sibling-pattern lesson, but framed narrowly (markdown wrapping, 
prompt typos). Instances 2 and 3 generalize it: the principle applies 
to any layer where literal-prompt-following produces a result that 
contradicts the canonical contract, the user's clear intent, or the 
production behavior the user actually wants. The current lesson 
under-states this.

**Scope:** rewrite the existing "prefer-pattern-over-prompt" lesson 
in MEMORY.md to the generalized form, with the three instances cited 
as evidence. Frame the rule as: when a prompt's literal instruction 
would produce a result that contradicts (a) the canonical contract 
in references/, (b) the sibling pattern in the same file class, or 
(c) a production correctness test, prefer the intent and surface the 
deviation explicitly rather than silently choosing either path.

**Why deferred from B.1.2:** atomic commit principle — B.1.2 is 
"CoinGecko fetcher + symbol-collision fix", not "fetcher + methodology 
lesson update". MEMORY.md changes belong in their own commit.

**Bundle with:** before B.1.3, single commit that lands TD-023 + 
also addresses TD-022 (since resolved/removed) if I want to clear documentation drift first. 
Otherwise standalone.

**Architectural impact:** none for fetchers. Documentation / 
methodology only — but load-bearing because future agents/sessions 
will internalize this principle from MEMORY.md.

---

## TD-024 — Dune Analytics fetcher deferred (query_id discovery friction)

**Status:** active 2026-05-25 (opened during B.1.6 planning, deferring 
the originally-planned B.1.6 = Dune to a later phase).

**Why deferred:** Dune Analytics is fundamentally different from 
the other 10 sources in `references/data_source_registry.md`:

- **Other sources are封装 APIs** (REST or RPC): one endpoint returns 
  structured data immediately for any subject. The fetcher pattern 
  is simple — pass subject + freshness_window, get standardized data.
- **Dune is a SQL execution engine.** Useful data requires either 
  (a) writing custom SQL, or (b) referencing a `query_id` of an 
  existing Dune query authored by someone else.

The `query_id` discovery friction breaks Stack Anamnesis's automation 
goal:

- Public Dune `query_id`s can be deleted, changed to private, or 
  silently modified by their authors at any time.
- Each research run would require manual research on dune.com to 
  find a currently-working public query matching the analytical 
  need.
- No stable `subject_type → query_id` mapping survives — author 
  ownership is the breakage axis.
- Custom SQL authoring is real work, not a fetcher task.

The other 5 active fetchers cover ~80% of typical stablecoin / 
fintech research:
- TVL: DefiLlama (§1)
- Price + market cap: CoinGecko (§4), CoinMarketCap (§13)
- On-chain: Etherscan (§3), Alchemy RPC (§5)
- Filings: SEC EDGAR (§6)

Dune's unique strength — deep custom on-chain analytics (e.g. 
"top USDC holders," "stablecoin DEX vs bridge vs CEX flow split") — 
is currently outside Stack Anamnesis's research scope.

**B.1 active fetcher count now: 10** (was 11). Architectural impact: 
none on existing 5 shipped fetchers; B.1 plan continues with 
CoinMarketCap, Messari, L2Beat, Electric Capital, Artemis 
(pending student plan).

**To unarchive:**
1. The user has an actual research need requiring custom SQL or 
   Dune's enriched stablecoin/DEX tables (e.g. preparing a 
   YYFoundry episode that requires `stablecoin.transfers` 
   joined with `dex.trades`).
2. Build a separate query registry file at 
   `references/dune_query_registry.yaml` mapping research questions 
   to currently-verified query_ids.
3. Write `agents/fetchers/dune_fetcher.md` + 
   `tools/fetchers/dune_fetch.py` per the async execution pattern 
   (POST execute → poll status → GET results).
4. Update this TD with the unarchive date and the research run 
   that motivated it.

**Coverage gap:** lose access to deep DEX/bridge/CEX flow 
classification, Dune Spellbook enriched tables, and any 
on-chain analytics requiring SQL joins. Workarounds: Alchemy RPC 
for raw eth_call reads; Etherscan for top-level transfers; 
DefiLlama for aggregated TVL/volume.

**API key already stored** at ~/.config/anamnesis/dune.key — 
remains in place for the future unarchive (no cleanup needed).

**Related:** TD-021 (paid sources archived).

---

## TD-025 — Messari fetcher deferred (free-tier entitlement too narrow)

**Status:** active 2026-05-25 (opened during B.1.7 planning after attempting implementation and live-probing the API with the user's cheapest-tier key).

**Why deferred:** Messari restructured their API and pricing in 2024-2025. The free tier documented in registry §11 and public materials (messari.io/api claims "40K+ assets, 20 req/min") does not match the actual entitlement of a free-tier key in 2026.

Live probing with user's free-tier key (~/.config/anamnesis/messari.key) revealed the actual accessible surface:

| Endpoint | Status |
|---|---|
| `api/v1/assets/{slug}/metrics` (documented free) | 404 — route deprecated |
| `metrics/v1/assets/.../metrics` (current) | 401 "Enterprise membership required" |
| `asset/v1/assets/.../profile` | 403 "your team does not have access" |
| `token-unlocks/v1/...`, `intel/v1/...` | 403 no access |
| `metrics/v2/assets[/details]` | 200, but **BTC + ETH ONLY** (totalRows: 2) |

The only working endpoint returns exactly 2 assets — Bitcoin and Ethereum. All `slug=` and `symbol=` filter params are silently ignored. docs.messari.io/api-reference/permissions confirms: "Enterprise Users: Unlimited access to Market Data. All Users with an API Key: MessariAI chat completion only."

**Stack Anamnesis impact:** Messari's value for our stablecoin / fintech vertical was analyst-cleaned profiles for stablecoin issuers, token unlock schedules, and sector classification — exactly the surface gated to Enterprise. For BTC + ETH market data we already have CoinGecko (§4), CoinMarketCap (§13), and Alchemy RPC (§5) which fully cover that need.

**B.1 active fetcher count now: 7** (was 8 after deferring Dune):
- DefiLlama (§1) — TVL
- CoinGecko (§4) — price + market cap (primary)
- Etherscan (§3) — chain explorer
- SEC EDGAR (§6) — filings
- Alchemy RPC (§5) — raw chain state
- CoinMarketCap (§13) — price cross-check
- L2Beat (§12) — pending B.1.7 (shifts up to fill the slot Messari
  would have taken)

**Architectural impact:** none. Implementation files (3 drafts) were written during this turn but never committed; they are deleted after this TD lands.

**To unarchive:**
1. Acquire an Enterprise Messari key (paid subscription, or
   successful NYU Blockchain Lab academic outreach to
   api@messari.io — historically Messari has worked with academic
   researchers but no public student program exists as of 2026-05-25).
2. Re-verify the active endpoint surface (Messari's API structure
   may shift again).
3. Re-implement `agents/fetchers/messari_fetcher.md` +
   `tools/fetchers/messari_fetch.py` per the institutional spec
   (slug-based metrics + profile + token-unlocks).
4. Update this TD with the unarchive date.

**Coverage gap:** lose access to (a) analyst-cleaned qualitative profiles for non-BTC/ETH assets, (b) token unlock / vesting schedules, (c) fundraising data, (d) Messari research reports. Workarounds: SEC EDGAR for issuer financials, CoinGecko for asset metadata, manual research for token unlocks if needed for a specific YYFoundry episode.

**API key already stored** at ~/.config/anamnesis/messari.key — remains in place for the future unarchive (no cleanup needed).

**Related:** TD-024 (Dune deferred — also free-tier-shape mismatch).

---

## TD-030 — subject_ref resolver built; front-door disambiguation gate deferred

**Status:** active 2026-06-01 (opened during B.2.6a — first resolver in the analysis-layer trunk: extractor → resolver → aggregator → filler).

**What was built.** `analysis_layer/resolvers/subject_ref.py` with a pure `resolve_subject(name) -> Optional[SubjectRef]` and a `SubjectRef` frozen dataclass added to `analysis_layer/contract.py`. It resolves a canonical subject to the out-of-envelope bindings the extractors/fetchers need but cannot read from an envelope:

- **decimals** — the Alchemy/Etherscan supply-decode arg (USDC = 6), previously hard-coded by the caller.
- **per-source ids** — each source addresses the same subject by its own id: CoinGecko slug (`usd-coin`), CMC numeric id (`3408`, the key of `quotes_latest.data`), DefiLlama stablecoin id (`2`).
- **on-chain** — Ethereum-mainnet contract (`0xA0b8…eB48`) + chain (`ethereum`).
- **issuer / regulatory** — issuer name (Circle) + zero-padded CIK (`0001876042`).

Registry seeded with **USDC ONLY**, every binding harvested from and cross-checked against the real envelopes on disk (`meta/raw/<source>/`, TD-023 grounding). Adding a subject is a data edit. Pure lookup, case-insensitive, unknown → `None` (rule 1: never throws).

**Deferred follow-up (out of scope for B.2.6a):** the **front-door subject-confirm gate** + ambiguity disambiguation — e.g. "PayPal → PYPL (the equity) vs PYUSD (the stablecoin)". subject_ref is only the *lookup*; deciding *which* subject an ambiguous user prompt means belongs to the subject-confirm gate, which lands later. subject_ref deliberately does not branch on ambiguity.

**To advance:** Open tails now tracked as TD-045 (subject-confirm / disambiguation gate) and TD-046 (multi-subject registry).

---

## TD-031 — source_authority resolver built; reconciliation deferred to B.2.7 aggregator

**Status:** active 2026-06-01 (opened during B.2.6b — second resolver in the analysis-layer trunk: extractor → resolver → aggregator → filler).

**What was built.** `analysis_layer/resolvers/source_authority.py` with a pure `authority_for(metric, scope=None) -> Optional[MetricAuthority]` and a `MetricAuthority{metric, primary, scope, cross_checks}` frozen dataclass added to `analysis_layer/contract.py`. It answers, per metric, **which source is authoritative and the ordered cross-checks** — derived from `references/data_source_registry.md` + the README "Source authority" section, not invented. Source slugs match the extractors' `SOURCE` constants exactly, so the aggregator joins on `ExtractedValue.source` with no translation.

Per-metric table (scope noted):

| metric | scope | primary | cross-checks |
|---|---|---|---|
| price | — | coingecko | coinmarketcap |
| market_cap | — | coingecko | coinmarketcap |
| volume_24h | — | coingecko | coinmarketcap |
| market_cap_rank | — | coingecko | (sole) |
| total_supply | **single-chain** | alchemy | etherscan |
| total_supply | **multi_chain** | coingecko | coinmarketcap |
| circulating_supply | multi_chain | defillama | coinmarketcap |
| tvl | — | defillama | (sole) |
| revenue / assets | — | sec_edgar | (sole) |

**★ Scope split (README scope rule).** `total_supply` carries TWO authorities keyed by `scope` — single-chain on-chain truth (Alchemy primary, Etherscan cross-check) vs the multi-chain aggregate (CoinGecko primary, CMC cross-check). The scope strings match the extractors' `provenance["scope"]` tags verbatim (`"single-chain"` / `"multi_chain"`). `authority_for("total_supply")` with no scope returns `None` on purpose — the two scopes are never collapsed into one ranking.

**Lookup-only.** This resolver does NOT reconcile values, apply tolerance bands, or flag divergence. Pure table lookup; unknown (metric, scope) → `None`, never throws (rule 1).

**Deferred follow-up:** the **B.2.7 aggregator** is the consumer — it reads `authority_for(...)`, then applies the README tolerance bands (±0.5% currency / ~0.2% multi-chain aggregate / ~0.01–0.05% single-chain contemporaneous, accounting for the `as_of` gap) to reconcile a single best value + audit trail and flag divergence.

**To advance:**
1. Build the B.2.7 aggregator consuming this lookup.
2. Extend the table as new metrics/sources land (data edits; e.g. a real `tvl`-emitting DefiLlama extractor path, or additional XBRL concepts).

---

## TD-032 — aggregator (reconciliation / credibility layer) built; B.2.8 filler is the consumer

**Status:** active 2026-06-01 (built in B.2.7 — third stage of the analysis-layer trunk: extractor → resolver → aggregator → filler; consumes both resolvers, TD-030/TD-031).

**What was built.** `analysis_layer/aggregators/reconcile.py` with a pure `reconcile(values: list[ExtractedValue]) -> list[ReconciledValue]`, and a `ReconciledValue` frozen dataclass added to `analysis_layer/contract.py` (the shape the B.2.8 filler will consume). Four steps: (1) group by `(metric, scope)`; (2) pick the authority's value via `source_authority.authority_for(metric, scope)`, falling back down the cross-check order when the primary emitted nothing; (3) cross-check every other available source against the chosen value vs a scope-aware band; (4) label `agree` / `divergence` / `single_source`.

**★ Authority, NOT average (cardinal rule).** The reported `value` is ALWAYS a real source's actual number — never a blend/mean. Cross-source agreement is recorded only as a confidence signal (`agreement` + `audit`: per-cross-check delta/band/within, plus group `spread` = (max−min)/median and `median`). The median is RECORDED, never used as the value. On divergence the value still stays the authority's number — flagged, not dropped, not averaged.

**Scope never crossed.** `(metric, scope)` grouping keeps single-chain on-chain supply (~$52.6B Ethereum-only, value from Alchemy) and the multi-chain aggregate (~$76.4B, value from CoinGecko) as TWO separate `ReconciledValue`s. Bands are by metric **category**, not the raw scope tag: supply gets the tight single-chain / 0.2% multi-chain bands, while price/market_cap/volume use the ±0.5% general-currency band even though the CoinGecko/CMC extractors tag them `multi_chain` (the 0.2% band is for supply totals, not prices).

**★ as_of-gap drift rule + `DRIFT_RATE_PER_DAY`.** Single-chain on-chain reads reconcile at a tight ~0.05% band ONLY when contemporaneous (as_of within `CONTEMPORANEOUS_WINDOW_SEC` = 1h). Beyond that the band is widened to `BAND_SINGLE_CHAIN_SUPPLY + gap_days × DRIFT_RATE_PER_DAY`. `DRIFT_RATE_PER_DAY = 0.0015` (0.15%/day) is a documented, tunable module constant derived from the two real on-chain USDC envelopes (~0.26% over ~1.86 days ≈ 0.14%/day), set slightly above the observed rate so normal mint/burn drift reads as **agree**, not a false divergence. On the real envelopes the Alchemy-vs-Etherscan 0.261% delta over a 1.86d gap widens the band to ~0.329% → agree.

**Scope inference for Alchemy.** The Alchemy `total_supply` extractor emits no `provenance["scope"]`; rather than hardcode a source→scope map or touch the extractor, `reconcile` infers a missing scope from `source_authority` (the scope whose authority ranking names that source for that metric) — so Alchemy groups with Etherscan in `single-chain`. Stays correct if Alchemy later adds the tag (its tag would then win).

**Out of scope (deferred):** markdown rendering / template filling (B.2.8 filler — the consumer of `ReconciledValue`); web third-source + red-team checks (B.3); any averaging/blending. `reconcile` takes already-extracted values and does NOT import the extractors.

**To advance:**
1. Build the B.2.8 filler that consumes `ReconciledValue` (value + `agreement`/`audit` confidence signal) into the markdown template.
2. Tune `DRIFT_RATE_PER_DAY` / the bands if real runs surface false flags.

---

## TD-033 — filler (markdown template filler) built; orchestrator wiring + B.3 QC deferred

**Status:** active 2026-06-01 (built in B.2.8 — FINAL stage of the analysis-layer trunk: extractor → resolver → aggregator → filler; consumes `ReconciledValue` + `SubjectRef`). Produced the first real deliverable: a filled USDC research markdown (`meta/reports/usdc_b28_filled.md`, gitignored).

**What was built.** `analysis_layer/fillers/fill.py` with a pure `fill(template_text: str, reconciled: list[ReconciledValue], subject_ref: SubjectRef) -> str` (plus a thin I/O wrapper `fill_template_file`). It drops reconciled values into the template's `[AUTO]` slots, builds a data-layer Evidence Table (value · source · confidence), and leaves `[SEMI-AUTO]` / `[MANUAL]` slots flagged for a human. No YYFoundry brand voice (that is a separate layer, kept OUT of the objective deliverable). Does NOT import the extractors or aggregator — the caller/test wires the chain.

**★ Faithfulness rule (QC integrity).** ONLY `[AUTO]` slots are auto-filled, and only with a real reconciled value. `[SEMI-AUTO]` → a visibly-flagged "needs human review" placeholder (a drafted suggestion is allowed only if flagged, never final). `[MANUAL]` → placeholder left intact, flagged. An `[AUTO]` slot with NO matching value stays flagged (marker preserved, "UNFILLED" appended) — never a fabricated number/source/claim. A reconciled value with NO slot is NOT dropped silently — it lands in the Evidence Table with a "no matching [AUTO] template slot" note. Legend/format-definition markers (body still holds a `<placeholder>`) are skipped, not treated as slots.

**Slot mapping.** `[AUTO]` marker lines are mapped to `(metric, scope)` by a keyword-anchor `SLOT` registry (first spec whose keywords all appear in the line wins; most-specific first). The real v1.2 template has ONE combined "Stablecoin supply" `[AUTO]` line → it holds BOTH supply scopes + circulating supply as DISTINCT sub-bullets (single-chain Ethereum-only ~$52.6B from Alchemy AND cross-chain ~$76.4B from CoinGecko/DefiLlama), never merged into one number. The v1.2 template has NO `[AUTO]` price/market_cap/rank/volume slots, so those reconciled facts surface in the Evidence Table with the "no slot" note (mapping ambiguity surfaced, not guessed).

**★ Scope/unit rendering rules (carry-over from B.2.7).** (a) Scope label is shown ONLY on supply facts (the two real supply scopes); it is omitted on price/market_cap/volume/rank even though those carry a `multi_chain` tag internally — the Evidence Table shows `—` for their scope. (b) Each value renders with its OWN unit (`$76.39B` USD, `52.57B USDC` tokens, `$0.9997` price, `#6` rank); when a cross-check compared different units (DefiLlama `circulating_supply` is USD-peg vs CMC's tokens) the Evidence Table notes `[unit: USD vs tokens]`. Human-readable in slots; FULL PRECISION in the Evidence Table. Confidence maps the aggregator's `agreement`: agree → High, single_source → Medium/Unverified, divergence → Low/Flag.

**Purity.** `fill` is deterministic and does no I/O — the report Date is derived from the data's own latest `as_of`, never the wall clock. `SubjectRef` fills only deterministic identity slots (Title, Asset/Token checkbox, a `[AUTO subject_ref]` context block with issuer/contract/per-source ids) — identity bindings, not measured numbers.

**Out of scope (deferred):** the orchestrator / front-door gate (subject → fetchers → extractors → reconcile → fill wiring — the deferred ② step); web third-source / red-team checks (B.3 — TOP priority next); md→HTML render, 6-card pack, SQLite (B.4+).

**To advance:**
1. Build the orchestrator that wires subject → fetchers → extractors → resolvers → reconcile → fill end-to-end (currently the test wires the chain).
2. B.3 red-team / web third-source verification over the filled deliverable.
3. Extend the `SLOT` registry as new templates / subject types add `[AUTO]` slots (e.g. a token-centric template with explicit price/market_cap slots).

---

## TD-034 — module-aware section selection (filler renders only the sections that apply)

**Status:** active 2026-06-02 (built in B.2.8b — extends the B.2.8 filler, TD-033). The filler now turns the unified v1.4 master SOP into a CLEAN per-subject report instead of the full template with irrelevant sections flagged empty.

**What was built.** A pure `select_sections(template_text, subject_type, mode="subject_driven") -> (kept_text, info)` pass in `analysis_layer/fillers/fill.py`, run by `fill()` (new `mode` arg) FIRST whenever a `SubjectRef` is supplied. It splits the template into header-delimited sections (a section spans its header down to the next header of the same-or-higher level, so omitting a Part drops its sub-sections too) and keeps only those that apply; the existing `[AUTO]` slot-filling / Evidence Table / `[SEMI-AUTO]`/`[MANUAL]` flagging then runs on the KEPT sections only. Omitted sections vanish ENTIRELY (header + body) — they are NOT flagged-empty.

**★ Two INDEPENDENT tag axes (do not conflate).**
1. **SUBJECT-TYPE axis** — only on the type-specific modules: Part 5.1 `[Chain / L2 / DeFi]`, 5.2 `[Chain / L2]`, 5.3 `[Payment chain]`, 5.4 `[DeFi]`, 5.5 `[Stablecoin]`, Part 4.3 `[Crypto-native asset / token-bearing protocol]`, and Part 8 valuation Paths A (crypto-native) / B ("no token exists" infra) / C (stablecoin). A section carrying a subject-type tag is kept only when the run's `subject_type` is among the types it names. A section may name SEVERAL types (the **stackable / hybrid** case, e.g. a payment chain that issues its own stablecoin keeps 5.1+5.2+5.3+5.5) — designed for, even though USDC is single-type.
2. **MODE axis** — `[Both]` / `[Mode A …]` / `[Mode B …]`. **★ `[Both]` means both MODES (A subject-driven, B news-driven), NOT both subject types** — a `[Both]` (or untagged) section is subject-type-AGNOSTIC and is always kept, subject only to the mode filter. In Mode A (default `subject_driven`) the `[Mode B only]` sections (e.g. Part 2 News Hook) are dropped; a dual-mode tag (`[Mode A primary; Mode B …]`, `[Mode B emphasis; Mode A optional]`) is kept in both.

**Matching details.** subject_type values match `SubjectRef.subject_type` (`stablecoin` / `chain` / `l1` / `l2` / `defi_protocol` / `payment_chain` / `crypto_native_asset`). Subject tokens are matched LONGEST-FIRST and consumed, so "payment chain" never also counts as the generic "chain"; and subject-token detection is restricted to the `[...]` / `（...）` delimited tag groups so a plain title word ("On-**Chain** Metrics", "**Stablecoin** valuation") cannot trip a match. Part 8 Path B is caught by the literal "no token" phrase → no-token infra (`payment_chain`), so it omits for a stablecoin while Path C (untagged title) is kept agnostically.

**FAIL-SAFE.** An unknown/unmapped `subject_type` (or `None`) keeps EVERYTHING and records a note (`info["failsafe"]`, surfaced as an `[AUTO module-aware]` blockquote after Part 0) — the selector never silently drops a section it cannot reason about.

**★ Reality check (TD-023).** The B.2.8b prompt referenced `references/templates/stablecoin_research_template.md` (v1.4); no such file exists. The real unified template is `references/templates/crypto_research_v1.3.md` — its content header is "Research SOP **v1.4**" with exactly the Part 5.1–5.5 modules + Path A/B/C described. Used that file; the e2e test points `TEMPLATE_V14` at it.

**Verified.** Real USDC e2e (`test_real_usdc_module_aware_fill`): on-disk envelopes → pure extractors → reconcile() → fill() against the real v1.4 template, subject_type=stablecoin, mode A → OMITS Part 2 + 5.1/5.2/5.3/5.4 + 4.3 + Path A/B; KEEPS Part 5.5 + the `[Both]` sections (thesis, competitive, conclusion) + Path C; still fills the stablecoin supply `[AUTO]` slots (both scopes as distinct sub-bullets) and flags the rest. Output written to `meta/reports/usdc_b28b_module_aware.md` (gitignored). Full suite: same 4 pre-existing failures, no new ones.

**Out of scope (deferred):** INTRA-section subject-type branch selection (Part 4.2's inline "For chain / For DeFi / For Stablecoin" bullets are kept whole — the section header is untagged/agnostic, so branch-level pruning inside a kept section is a future refinement); dropping the non-deliverable YYFoundry Workshop block; a chain/l1 subject currently matches none of Path A/B/C (template's own valuation-path design gap — chains-with-token should resolve as `crypto_native_asset`).

---

## TD-035 — change layer (supply-momentum derivation); leg 1/3 of the stablecoin KEY SIGNAL

**Status:** active 2026-06-02 (built in B.2.9 — a NEW analysis-layer stage, `analysis_layer/derivations/`, alongside extractor → resolver → aggregator → filler). First "derivation": a secondary fact computed over already-extracted values rather than read from one envelope.

**What was built.** A pure `compute_supply_change(defillama_envelope, subject_ref, windows=(7,30,90), flat_band=0.0005) -> (list[ReconciledValue], list[str])` in `analysis_layer/derivations/supply_change.py`. For each window the DefiLlama historical supply series can cover: `now` = latest point, `then` = point NEAREST to `now − window`; emits one `ReconciledValue` (`metric="net_supply_change_{w}d"`, `value` = signed PERCENT POINTS, `unit="%"`, `scope` = series scope `multi_chain`, `source_used="defillama"`, `agreement="single_source"`, `inputs` = (then, now), `audit` carries BOTH `abs_change` (USD) and `pct_change` (fraction) + `then/now_date`, `actual_days`, `direction`). Real USDC envelope computed all three: 7d +0.24% / 30d −1.62% / 90d +1.52% (none skipped — the series spans 2018→now, daily).

**★ Single-source BY NATURE — why `ReconciledValue` directly, not `ExtractedValue → reconcile`.** Only DefiLlama carries a historical supply TIME SERIES; CoinGecko/CMC/on-chain give a single latest snapshot, no back-series. A window change therefore has nothing to cross-check — no authority contest for `reconcile` to resolve — so the derivation emits `ReconciledValue` with `agreement="single_source"` directly. **Refactor trigger:** IF a 2nd historical-series source ever appears, route both through the aggregator instead.

**★ Non-contemporaneous day-gap honesty** (mirrors the aggregator's drift handling): daily points rarely land exactly on `now − window`, so we take the NEAREST point and RECORD `actual_days` — a nominal "7d" computed over 6.4 real days is labelled as such, never silently presented as exactly 7d. A window whose target predates the series' oldest point (or whose `then` value is 0) is SKIPPED with a note in the returned `notes` list — never faked. (This is why the nominal `-> list[ReconciledValue]` signature is widened to `(values, notes)`: a skip must be visible.)

**★ Filler change — `[SEMI-AUTO]` is now FILLABLE.** `analysis_layer/fillers/fill.py`: `SlotSpec` gains a `computed: bool` flag; one new slot `net_supply_change` (computed=True, keyword anchor `"supply change"`, unique to the Part 5.5 A "Net 7d / 30d supply change `[SEMI-AUTO: DefiLlama historical]`" line) accepts the three `net_supply_change_*` metrics. A `[SEMI-AUTO]` slot WITH a matching computed value flips to `[SEMI-AUTO ✓ COMPUTED]` + window sub-bullets (abs + pct + actual-days, e.g. "+$180.93M (+0.24%) · up · over 7d (actual 7.0d, …)"); a `[SEMI-AUTO]` slot with NO computed value (or any non-computed slot) still flags for a human exactly as before — so a plain `[SEMI-AUTO]` line can never be auto-filled from an unrelated `[AUTO]` metric. Evidence Table: `single_source → Medium` (unchanged mapping); the 3 net-change facts surface as their own rows.

**★ Leg 1/3 of the KEY SIGNAL.** This supplies only the SUPPLY-DIRECTION number for Part 5.5's "Supply Momentum: organic vs mechanical" signal. The holder-count leg and real-usage leg are still pending; the CONFIRMATION/DIVERGENCE verdict is NOT auto-decided (the `☐ CONFIRMATION / ☐ DIVERGENCE` checkboxes are left untouched in the template).

**Verified.** Unit tests (`tests/analysis_layer/test_supply_change.py`, synthetic series — no network): clean abs/pct/direction for 7d/30d/90d, short-history skip-with-note, non-contemporaneous gap recorded, rising/flat/falling direction (5bps dead-band), degenerate input → note not value. Real e2e (`tests/analysis_layer/test_filler.py::test_real_usdc_supply_change_fills_5_5_a`): real DefiLlama envelope → `compute_supply_change` CONCATENATED with `reconcile(inputs)` → `fill()` against the real v1.4 template (stablecoin, Mode A) → 5.5 A net-change line flips flagged → `[SEMI-AUTO ✓ COMPUTED]` with the right signs at Medium; rest of the report body byte-identical (Evidence Table legitimately gains the 3 rows). Output `meta/reports/usdc_b29_supply_change.md` (gitignored). Full suite: same 4 pre-existing failures, no new ones.

**Out of scope (deferred):** the holder-count + real-usage legs (2/3, 3/3) and the KEY SIGNAL verdict — open tail now tracked as TD-043 (holder-count leg) + TD-044 (real-usage leg); routing through `reconcile` if a 2nd historical-series source appears; momentum windows beyond 7/30/90d.

---

## TD-036 — analysis orchestrator (the pipeline FRONT DOOR); half 1 of 2 (analysis), fetch front deferred to B.2.11

**Status:** active 2026-06-02 (built in B.2.10 — a NEW module `analysis_layer/orchestrate.py`, the entry point over the existing trunk: resolve → load envelopes → extract → reconcile → derive → fill → write).

**What was built.** `research(subject, *, subject_type=None, mode="subject_driven", template_path=<v1.4>, raw_dir="meta/raw", out_dir="meta/reports") -> Path` — PURE (no network, no env-key reads): resolves the subject_ref (clear `ValueError` if not in the registry), loads the NEWEST envelope per source, runs each source's extractor, `reconcile()`s, runs the supply-change derivation, module-aware `fill()`s, and writes `meta/reports/<slug>_<utc>.md`. Reusable building blocks exposed for the fetch front + tests: `load_and_extract(subject, raw_dir) -> list[ExtractedValue]`, `build_report(...)` (everything but the write), `SOURCE_EXTRACTORS` (the source→adapter map). Thin CLI: `python -m analysis_layer.orchestrate <subject> [--subject-type X] [--mode ...] [--template ...]` prints the report path + a one-line summary (subject, subject_type, sources loaded/skipped, reconciled facts, filled slots, derivations, skipped-window notes).

**★ Centralises the hand-wiring the tests duplicated.** Until now the full chain only existed inside `tests/analysis_layer/test_filler.py`'s `_build_usdc_reconciled` + the e2e tests. The orchestrator is that wiring, in one place. (DRY note for later: those test helpers COULD eventually call the orchestrator instead of re-deriving the chain — deferred to avoid touching the existing tests in this step.)

**★ Wires ALL SIX extractors incl. `sec_edgar`** — the hand-wired tests omitted it. The orchestrator pulls a fixed `_SEC_FACTS` set (Revenues FY2024, Assets/Liabilities FY2025, NetIncomeLoss/StockholdersEquity FY2024 — each grounded to a `frame` present in Circle's real envelope, TD-023) via `get_xbrl_value`; no `[AUTO]` slot maps to them so they land in the Evidence Table, surfacing the issuer's regulated financials (real numbers: Assets $78.7B, Revenues $1.68B, NetIncome $155.7M) alongside the on-chain metrics — a more complete report than the filler e2e makes.

**★ Best-effort missing-source tolerance.** A source with no envelope on disk (e.g. a DefiLlama fetch that failed that run) is simply SKIPPED — the report still builds and that section stays flagged exactly as the filler already handles. On-chain dirs (Alchemy/Etherscan) glob `*.json` and rely on the extractor to skip non-matching envelopes (mirrors the tests' `_first`); aggregator sources glob `<slug>_*.json`; SEC globs `*cik<cik>*.json`. Malformed/unreadable JSON is skipped, never crashes the build.

**★ Deterministic.** Given fixed envelopes the report CONTENT is byte-identical across runs (fixed source order + fixed SEC-fact order; no timestamp injected into the markdown — only the output FILENAME's UTC stamp differs).

**Verified.** `tests/analysis_layer/test_orchestrate.py` (5 tests, glob+skip if envelopes absent): real e2e `research("USDC")` → same clean stablecoin report the filler e2e proves (chain/DeFi modules + News Hook omitted, Part 5.5 + Path C kept, supply `[AUTO]` filled, 5.5 A net-change `[SEMI-AUTO ✓ COMPUTED]`, Evidence Table + faithfulness flags intact) AND now the sec_edgar Circle facts in the table; the source→extractor map names all 6; unresolvable subject → clear `ValueError`; determinism (two runs → byte-identical content); `load_and_extract` reaches all present sources incl. sec_edgar. CLI prints path + summary (6 sources loaded, 15 reconciled facts, derivation run). Full suite: same 4 pre-existing failures, no new ones.

**Out of scope (deferred to B.2.11 — the FETCH front, half 2 of 2):** running the B.1 fetchers to REFRESH the envelopes (network/keys/rate-limits) BEFORE calling `research()`. The DRY refactor (the test helpers calling the orchestrator). Multi-subject registry (only USDC is bound today — now tracked as TD-046).

---

## TD-037 — SEC issuer-financials period selection fixed (mixed/stale FY → latest-consistent FY)

**Status:** active 2026-06-02 (fixed in B.2.10b — a bug in the B.2.10 orchestrator's sec_edgar wiring, TD-036).

**The bug.** The orchestrator pulled a FIXED set of `(concept, fy, fp)` pairs through `get_xbrl_value` (which resolves them by SEC `frame`). The hardcoded years landed MIXED — Assets/Liabilities FY2025 but Revenues/NetIncome/StockholdersEquity FY2024 — and worse, surfaced FY2024's PROFIT (+$155.7M) and equity ($570.5M) when the latest full year FY2025 was a LOSS (−$69.5M) with equity $3.329B. The same envelope HELD the FY2025 figures (the 2026-05-27 manual draft used them); naming a fixed period silently froze a stale year and masked Circle's swing-to-loss.

**The fix — data-driven latest-annual selection.** New `analysis_layer/extractors/sec_edgar.py::latest_annual(envelope, concept_or_aliases, kind="duration"|"instant") -> AnnualFact | None` (+ `extract_annual_fact` wrapping it as an `ExtractedValue`). NO hardcoded frame/fy: it reads the concept's annual rows and picks the most recent. The orchestrator's `_SEC_FACTS` is now `(metric_label, concept-alias-priority, kind)` and calls the selector per fact, so all five come from the SAME latest fiscal year (FY2025 / 2025-12-31): Revenues $2.747B, NetIncomeLoss −$69.5M, Assets $78.71B, Liabilities $75.38B, StockholdersEquity $3.329B.

**★ Three gotchas the selector encodes (TD-023 — grounded against `meta/raw/sec_edgar/circle_*.json`):**
* **"Annual" = `fp == "FY"`, not a frame.** The 10-K's annual-period tag is the robust marker (independent of whether a `frame` string is present); the prior-year comparatives a 10-K restates also carry `fp=FY` — fine, we pick the most-recent period END.
* **Flow vs instant.** A FLOW (Revenues, NetIncomeLoss) is a ~1-year DURATION (`start`→`end`, span > 300d); a STOCK (Assets, Liabilities, StockholdersEquity) is an INSTANT at fiscal-year-end (`start` is None). `kind` selects which; asking the wrong kind finds no row → None.
* **Restatement tie-break.** A period END reported in multiple filings (original + restated, and the next year's 10-Q comparative) → pick latest `filed`, then `accn` (same authority rule as `get_xbrl_value`).
* **Concept-alias priority.** Issuers can move a metric between us-gaap concepts across years (revenue-concept-switch). The selector takes an ordered alias list; first alias WITH annual data wins. For Circle, `Revenues` carries both years → $2.747B; the alias list still guards future filings.

**Verified.** `tests/analysis_layer/test_sec_edgar_extractor.py` (synthetic companyfacts): latest_annual picks the newest year not an older comparative/quarter; flow-vs-instant (incl. wrong-kind → None); restatement tie → latest filed; concept-alias priority (first-with-data wins; falls through when absent); null-guards; `extract_annual_fact` wraps with `as_of` = period end + `fiscal_period` label; plus a real-envelope GROUND-TRUTH anchor (all 5 = FY2025 / 2025-12-31, NetIncome = the loss). `tests/analysis_layer/test_orchestrate.py`: the report's 5 SEC facts all dated 2025-12-31, the FY2025 numbers present (LOSS visible), the stale FY2024 values gone. `get_xbrl_value` and its tests untouched (left in place — it answers a NAMED-period query; `latest_annual` answers a latest-period query). Full suite: same 4 pre-existing failures, no new ones.

**Out of scope (deferred):** non-calendar fiscal-year filers (Circle is 12-31; a non-calendar issuer needs fy→calendar mapping); auto-pairing each flow with its prior-year value for a YoY delta (only the latest year is surfaced); a multi-year mini history.

---

## TD-038 — fetch front (zero→report); half 2 of 2 of the pipeline front door

**Status:** active 2026-06-02 (built in B.2.11 — a NEW module `analysis_layer/fetch_front.py` + a `--fetch` opt-in on the orchestrator. Completes the front door begun in TD-036: TD-036 was the PURE analysis half over existing envelopes; this is the IMPURE half that REFRESHES them first).

**What was built.** `fetch_subject(subject, *, subject_type=None, freshness_window="30d", timeout=120, runner=None) -> list[str]` — resolves the subject_ref (clear `ValueError` if unresolvable), looks up the subject_type's fetcher set, and runs each B.1 fetcher in its own isolated, timed subprocess; returns per-source notes. `orchestrate.research()`/`_run()` gain `fetch=False` (+ `freshness_window`); `--fetch`/`--window` on the CLI. `research(fetch=False)` stays the PURE default (the network module is imported lazily only when `fetch=True`, so the offline path never touches it). `python -m analysis_layer.orchestrate USDC --fetch` does the full subject→fetch→fresh envelopes→research→report.

**★ Data-driven subject_type→sources map + per-source identifier resolution from subject_ref.** `SOURCES_BY_TYPE["stablecoin"]` = the Part 11.5 set (DefiLlama, CoinGecko, CoinMarketCap, Etherscan, Alchemy, SEC EDGAR), each a `SourceSpec` carrying the fetcher file, the `--subject` value (pulled from the right `subject_ref` binding), the per-fetcher subject_type, and any extra args. On-chain sources (Etherscan/Alchemy) get the `eth_contract` address + `--chain-id` (from `eth_chain`); SEC gets the `issuer` name (the fetcher resolves the CIK).

**★ DEVIATION FROM THE MANDATE (deliberate, flagged) — market sources get the canonical NAME, not the slug/id.** The mandate said "coingecko→slug, cmc→id". Reality (TD-023, verified against the fetchers): (a) these fetchers resolve the subject by NAME internally (CoinGecko `/search`, CMC `/map` by slug-then-symbol, DefiLlama by stablecoins-list name) — CMC literally cannot resolve the numeric id `3408`; and (b) each NAMES ITS OUTPUT FILE after `--subject`, and `orchestrate` globs these sources as `<subject.lower()>_*.json`. So the fetch MUST pass `USDC` for the fresh envelope to be found by the analysis half — passing `usd-coin` would write `usd-coin_*.json` and the two halves would not compose. On-chain (address) + SEC (issuer) use the identifiers exactly as the mandate said.

**★ Per-fetcher subject_type is NOT always the orchestrator's.** The market sources + Etherscan accept `stablecoin`; Alchemy's token-contract read (`eth_call totalSupply`) and SEC both live under `stablecoin_issuer` (their CLIs' `SUBJECT_TYPES`). The map encodes this per source.

**★ Subprocess isolation + best-effort tolerance (no crash on a failed fetcher).** Each fetcher runs via `subprocess.run(..., timeout=)` with `cwd=ROOT`; a non-zero exit / network error / rate-limit / subject-not-found / timeout / a raising runner is captured as a `FAILED`/`SKIPPED` note and the run CONTINUES (the DefiLlama-failed-that-run lesson). `research()` then analyses whatever envelopes landed — a missing source just leaves its section flagged. The runner is injectable (`runner=`) so tests stub it (no real network in CI).

**★ I-003 secret handling.** This module never reads/logs/persists any API key — each fetcher reads its OWN key from `~/.config/anamnesis/<source>.key`. The one secret it handles is the SEC contact email: read from env var **`ANAMNESIS_SEC_EMAIL`** (a CHOSEN name — no pre-existing repo convention was found; flag for confirmation), passed to the SEC fetcher's `--sec-email` (process-memory only), and SCRUBBED from every returned note (defense in depth; a `TimeoutExpired` is reported without its `.cmd` so the email-bearing argv never leaks).

**Verified.** `tests/analysis_layer/test_fetch_front.py` (12 tests, runner STUBBED — no network): wiring (exactly the 6 sources; each invocation's `--subject`/`--subject-type`/`--chain-id`/`--sec-email` correct); best-effort tolerance (one fetcher failing / raising / timing out → noted, others still run, never raises); missing-email → only SEC skipped; no-secret-leak (a hostile stub that echoes the email → scrubbed to `<sec-email redacted>`); unknown subject_type → graceful skip note; `research(fetch=False)` invokes no fetcher. **★ LIVE zero→report demo** (`python -m analysis_layer.orchestrate USDC --fetch`): 5/6 fetchers wrote FRESH 2026-06-02 envelopes live (DefiLlama, CoinGecko, CoinMarketCap, Etherscan, Alchemy — keyless or key-on-disk); SEC best-effort SKIPPED (no `$ANAMNESIS_SEC_EMAIL` set) and the run still completed over the existing SEC envelope. Filenames composed with the analysis globs as designed. (The fresh envelopes were then REMOVED to keep the value-pinned real-data tests on their 5-27 baseline — meta/raw is gitignored.) Full suite: same 4 pre-existing failures, no new ones.

**Out of scope / remaining gaps:** multi-subject (only USDC is bound in the registry — now tracked as TD-046); the holder-count + real-usage KEY-SIGNAL legs (2/3, 3/3) still pending — now tracked as TD-043 + TD-044; non-stablecoin fetcher sets (chain/protocol rows for `SOURCES_BY_TYPE`); confirming the `ANAMNESIS_SEC_EMAIL` env-var name against any operator convention; parallelising the fetchers (currently sequential).

---

## TD-039 — inherited equity card / incident-loop tests parked behind skip-guards (not deleted)

**Status:** active 2026-06-02 (repo-cleanup pass). Three inherited tests asserted contracts that the crypto Lane-A pipeline does not yet exercise; rather than delete the inherited photo/incident infrastructure (kept as reusable method reference), they are now SKIPPED with explicit, self-documenting reasons so `python3 -m pytest -q` is green (`0 failed`, some `skipped`) without hiding what is parked.

**What was parked and why:**

- `tests/test_card_money_scale_validator.py` (2 tests) — import `skills_repo/ep/scripts/generate_social_cards.py`. The `ep` (Equity Photo) submodule is **not checked out** (`skills_repo/` is empty — no `.gitmodules` in this fork), so the 6-card photo pipeline is inactive. Guarded with `pytest.mark.skipif(not EP_SCRIPT.exists())`: the moment `ep` is checked out, the tests run again automatically. No deletion — the photo pipeline stays as inherited method reference.
- `tests/test_incident_loop.py::test_all_incidents_reachable_in_a_well_formed_payload` — asserts `INCIDENTS.md` contains ≥1 `I-NNN` entry. The committed `INCIDENTS.md` is an **empty scaffold** (no incidents logged yet for this fork; mature-domain examples archived to `references/equity_incidents_archive.md`, not enforced). The other incident-loop tests (schema validation, supersede graph, phase wiring, lint) all pass against the empty log and stay live. Only the "≥1 entry" coverage test is skipped, with a reason pointing here.

**Revisit when:** (a) the `ep` submodule is checked out / the crypto card pipeline (B.5) lands — the skipif clears itself; (b) the first real crypto failure is captured via `/log-incident`, populating `INCIDENTS.md` with `I-001` — drop the skip on the coverage test.

---

## TD-040 — markdown→HTML renderer (B.4); status/confidence badges; optional `--html`

**Status:** active 2026-06-02 (built in B.4 — a NEW pure module `analysis_layer/render/html.py` + `analysis_layer/render/__init__.py`, and an opt-in `html=` flag on the orchestrator).

> **★ Numbering note (flagged, deliberate deviation from the B.4 mandate).** The B.4 prompt said to capture this as "TD-039 (next free; fetch front was TD-038)". By the time B.4 ran, **TD-039 was already taken** — the repo-cleanup pass (README rewrite + parked inherited tests) had claimed it (and was committed as `a850b5f`). The genuinely-next-free id is **TD-040**, used here, to avoid a colliding duplicate. (Pattern: substance over a stale literal — surface the conflict, take the correct next id.)

**What was built.** `render_html(markdown_text, *, title=None) -> str` — converts a crypto research report (markdown) into ONE self-contained HTML file: inline `<style>` only, **no external `<link>` / `<script src>`** — fully portable. A focused converter for the constrained markdown the template emits (ATX headers → `h1`–`h6`; GFM pipe tables → styled `<table>`; `-`/`*` lists with 4-space nesting → nested `<ul>`; `>` → `<blockquote>`; `---` → `<hr>`; `**bold**` / `*italic*` / `` `code` `` inline). NOT a general markdown engine; NOT coupled to the inherited equity locked-template / `validate_report_html` machinery (a deliberately separate crypto renderer). PURE + deterministic — same markdown in → byte-identical HTML out (no clock, no network).

**★ The value-add over raw markdown — status becomes scannable.** Each marker the filler emits is turned into a coloured badge/chip so a reader sees data provenance at a glance:
- `[AUTO ✓ FILLED: …]` / `[SEMI-AUTO ✓ COMPUTED: …]` → green "machine-filled" badge;
- `⚠ NEEDS HUMAN REVIEW [SEMI-AUTO]` / `⚠ MANUAL` / `[MANUAL: …]` → amber "needs-human" badge;
- `⚠ UNFILLED [AUTO]` → amber (flagged, NOT fabricated);
- `[AUTO: …]` / `[SEMI-AUTO: …]` planned-but-unfilled tags → neutral grey badge;
- confidence `High` / `Medium` / `Low` → green / amber / grey chips (in running text *and* in the Evidence Table's Confidence column).

A small legend at the top of the document keys the colours.

**Orchestrator wiring.** `research(..., html=False)` / `_run(..., html=False)` and a `--html` CLI flag. Default stays `html=False`; the markdown remains the canonical artifact and the returned path is still the `.md`. When `True`, a self-contained `meta/reports/<slug>_<utc>.html` is written next to the `.md` (same stem). The renderer is imported lazily inside the `html` branch.

**Verified.** `tests/analysis_layer/test_render_html.py` (15 tests, no network): a synthetic report carrying every marker + an Evidence Table renders the table as `<table>`, headers as `<h*>`, each status marker as its badge, confidence chips present, output self-contained (no `http(s)://` / `<link` / `src=`), deterministic, title from first `# ` or override; plus an e2e (`research("USDC", html=True)` over on-disk envelopes writes BOTH `.md` and a valid `.html`; globs + skips if envelopes absent). Live CLI: `python -m analysis_layer.orchestrate USDC --html` → both files written, badges/table/chips render, zero external resources.

**No new dependency.** `markdown`/`bs4` were considered but the converter is stdlib-only (`re`), so `requirements.txt` is untouched — keeps the renderer pure and install-free.

**Still ahead:** **B.5** — the 6-card social pack (YYFoundry brand visuals; the inherited `ep`/photo pipeline is parked, see TD-039); **B.6** — SQLite crypto schema (cross-report query + incremental). B.4 is the markdown→HTML leg only; HTML→PNG cards and DB persistence remain.

---

## TD-041 — facts bundle (the LLM report-writer chain, step ①); pure `.facts.json`; optional `--bundle`

**Status:** active 2026-06-04 (built — a NEW pure module `analysis_layer/bundle.py` + an opt-in `bundle=` flag on the orchestrator).

**What was built.** `build_facts_bundle(subject_ref, reconciled, supply_change, *, sources_loaded) -> dict` — packs the orchestrator's DETERMINISTIC, provenance-carrying facts into one clean, self-contained "facts folder" (a JSON-serialisable dict) for a downstream report-writer LLM to read. **FACTS ONLY** — no analysis, no prose, no derived verdict (CONFIRMATION/DIVERGENCE stays the writer's call), no `[MANUAL]` placeholder text. Sections: `subject`/`subject_type`/`issuer`/`decimals`/`contract`/`chain`/`identifiers`; `metrics[]` (each reconciled spot fact with `value`/`unit`/`source`/`as_of`/`agreement`/`confidence`); `supply_momentum[]` (7d/30d/90d: `window`/`window_days`/`actual_days`/`net_change_pct`/`net_change_abs`/`direction`/`then_date`/`now_date` + provenance); `issuer_financials` (Circle: `revenues`/`net_income`/`assets`/`liabilities`/`equity`/`fiscal_year`, each with its own provenance, or `null`); `sources[]`. Stable snake_case field names + deterministic ordering (lists pre-sorted, `serialize_bundle` writes `sort_keys=True`). PURE + deterministic — same inputs → byte-identical JSON; the bundle content carries NO generation timestamp (only the on-disk filename does, mirroring the `.md`).

**Orchestrator wiring.** `build_report` now returns `reconciled` and `supply_change` SEPARATELY (the markdown still sees them merged; classification is a bundle-only concern). `research(..., bundle=False)` / `_run(..., bundle=False)` and a `--bundle` CLI flag. Default stays OFF; the `.md` remains the canonical artifact. When `True`, a `meta/reports/<slug>_<utc>.facts.json` is written next to the `.md` (same stem); the builder is imported lazily inside the `bundle` branch.

**Verified.** `tests/analysis_layer/test_bundle.py` (8 tests, no network, glob+skip): off the real USDC envelopes — reconciled metrics carry provenance, supply-momentum windows ascend with actual-day honesty, issuer financials map to snake_case with provenance, sources sorted, NO analysis/prose keys + no `[MANUAL]`/`UNFILLED` text in the blob, deterministic (built twice → equal bytes); e2e `research("USDC", bundle=True)` writes a valid `.facts.json` beside the `.md`, and the default writes none. Live CLI: `python -m analysis_layer.orchestrate USDC --bundle` → both files written.

**Still ahead in the report-writer chain:** **③** wire the bundle into a writer brief (aligns to the template's `[MANUAL]` sections — see the Part 5.5 section names below); **④/⑤ now tracked as TD-047 (④ renderer redesign) + TD-048 (⑤ no-fabrication + confidence-cap gate)** — ⑤ is the first piece of the broader B.3 QC layer (TD-049). (① facts bundle = this TD; render-html was TD-040; ③ landed in TD-042.)

The template's actual `[MANUAL]` section names (Part 5.5 Stablecoin module, for the ③ writer-brief alignment — printed verbatim, template unchanged):
- **C. Peg Stability & Market Microstructure** — Historical depeg events `[MANUAL: incident research]`; CEX depth ±0.5% bid/ask `[MANUAL: orderbook data, not in B.1]`
- **D. Reserve & Backing** — Reserve composition `[MANUAL: monthly attestation PDF]`; Attestation cadence `[MANUAL: issuer disclosure]`; Auditor `[MANUAL]`; Banking partners & 集中度 `[MANUAL]`; 1-day/7-day redemption capacity `[MANUAL: attestation PDF]`; Cash + overnight-repo share `[MANUAL: attestation PDF]`; T-bill maturity ladder `[MANUAL: attestation PDF]`; Banking-partner concentration `[MANUAL: attestation PDF]`
- **E. Issuer Economics** — Distribution partner revenue share `[MANUAL: contract disclosures]`
- **F. Regulatory Posture** — Licenses held `[MANUAL: issuer site]`; GENIUS Act / MiCA status `[MANUAL]`; Freeze / blacklist capability `[MANUAL: protocol design]`; Restricted jurisdictions `[MANUAL]`
- **G. Cross-chain Mechanics** — CCTP / native 支持的链 `[MANUAL: issuer docs]`; 接受度：哪些链把它当 primary quote/collateral asset `[MANUAL]`
- **H. Real-world Use Cases** — Payment volume `[MANUAL: Visa Onchain Analytics 等外部源]`; Remittance corridors `[MANUAL]`; B2B settlement adoption `[MANUAL]`; Treasury management `[MANUAL]`

---

## TD-042 — v2 template promoted to live + agent-driven report-writer wiring (chain step ③)

**Status:** active 2026-06-05 (landed as a follow-up commit — see note below).

**What changed.** The v2 template was promoted to live and the report-writer chain's ③ wiring was committed:
- **Template promoted:** `references/templates/crypto_research_v2.md` is now the live template (header "Research SOP v2", no "(DRAFT)"; clean top VERSION NOTE documenting the M1–M5 reorg + R1–R5 rigor pass). Predecessors `crypto_research_v1.3.md` (content header "SOP v1.4") and `crypto_research_v1.2.md` remain archived on disk.
- **Orchestrator repointed:** `analysis_layer/orchestrate.py` `DEFAULT_TEMPLATE` → `crypto_research_v2.md` (deterministic data layer otherwise untouched).
- **Writer brief aligned:** `.claude/agents/crypto-report-writer.md` — the old `Part 1.6` cross-references were migrated to **Front Matter §C** (matching M2); a new **"Deliverable language & the coaching channel (M5)"** section adds the strip-`GUIDANCE`/English-body rule that fixes the bilingual-mixing bug; **R1–R5 fill instructions** added (R1 Part 9.5 Bull/Bear/Thesis-Breaker, R2 §11.1 conviction binding, R4 §1.4 disconfirming-evidence column, R5 §9.2 observable-trigger column).
- **③ wiring committed:** the `crypto-report-writer` subagent + the `/research` command (`.claude/commands/research.md`) — deterministic `orchestrate --bundle` → subagent narrative → HTML render.

**Verified.** A clean `/research USDC` post-promotion confirms the v2 template + aligned brief are live end-to-end; `pytest tests/ -q` green (414 passed, 4 skipped).

**Note — interrupted first attempt.** A mid-run macOS FS-permission revocation killed the original Step 4 (the commit) mid-write; Steps 1–3 (the edits) had already been applied and survived intact (re-verified before this commit), so this landed as a **follow-up commit** rather than the original milestone commit.

**Minor follow-up (not in this commit):** the v2 back-matter changelog still labels its own entries `v2 (DRAFT) reorg` / `v2 (DRAFT) rigor pass` (stale now that v2 is live; the authoritative top VERSION NOTE is clean). Cosmetic.

---

## TD-043 — KEY SIGNAL leg 2/3: holder-count / holder-structure fetcher

**Status:** active 2026-06-05 (extracted from the deferred tails of TD-035 + TD-038 — a buried open item lifted into a trackable OPEN-TASK).

**What it is.** The SECOND of the three legs feeding Part 5.5's "Supply Momentum: organic vs mechanical" KEY SIGNAL. A holder-count / holder-structure fetcher + derivation: top-10 / top-100 concentration, CEX vs DeFi vs EOA split, and holder-count growth over the freshness windows. Source path: Etherscan / Alchemy holders endpoints + address labeling (raw addresses only under the free tier — no Nansen-style labels, TD-021; labeling is best-effort heuristic or `[MANUAL]`).

**Why it matters.** Leg 1/3 (supply-direction, TD-035) on its own leaves §5.5 supply-only and INCONCLUSIVE. Holder structure is the leg that lets the report-writer move past a supply-only read toward a real CONFIRMATION / DIVERGENCE verdict — concentration + holder-count growth distinguish organic adoption from a single mint inflating supply.

**Depends on / blocks.** Builds on the same on-chain fetchers as TD-035 (Etherscan §3 / Alchemy §5). Blocks (with TD-044) the §5.5 organic-vs-mechanical verdict. The verdict itself stays the report-writer's call (TD-041) — this leg only supplies the holder-structure facts into the bundle.

**Source tails:** TD-035 "the holder-count … leg (2/3)"; TD-038 "the holder-count … KEY-SIGNAL leg (2/3) still pending."

---

## TD-044 — KEY SIGNAL leg 3/3: real-usage signal

**Status:** active 2026-06-05 (extracted from the deferred tails of TD-035 + TD-038).

**What it is.** The THIRD leg of the Part 5.5 KEY SIGNAL: a real-usage signal — transfer / payment-volume + real-usage proxies that distinguish genuine economic activity from mechanical / idle supply. **Honesty note (TD-023):** much of this surface is `[MANUAL]` / external in the v2 template — de-noised payment volume, Visa Onchain Analytics, remittance corridors, B2B settlement (see TD-041's Part 5.5 H "Real-world Use Cases" `[MANUAL]` list). This TD must capture what is actually FETCHABLE on the free tier (raw transfer counts / volume via Etherscan / Alchemy) vs what STAYS `[MANUAL]` (de-noised payment volume, Visa Onchain Analytics, etc.) — do not over-promise an automated number where only a `[MANUAL]` slot is honest.

**Why it matters.** The third leg that, combined with legs 1/3 (TD-035) and 2/3 (TD-043), completes the organic-vs-mechanical picture the writer needs to call §5.5 CONFIRMATION / DIVERGENCE instead of INCONCLUSIVE.

**Depends on / blocks.** Pairs with TD-043; together they unblock the §5.5 verdict. Partly bounded by the free-tier coverage gaps (TD-021, TD-024 — no Dune flow classification, no Nansen labels), which is exactly why the `[MANUAL]` / fetchable split must be drawn honestly rather than faked.

**Source tails:** TD-035 "the … real-usage leg (3/3)"; TD-038 "the … real-usage KEY-SIGNAL leg (3/3) still pending."

---

## TD-045 — subject-confirm / disambiguation gate

**Status:** active 2026-06-05 (extracted from the deferred "To advance" tail of TD-030).

**What it is.** A front-door subject-confirm gate that confirms / disambiguates an ambiguous user subject BEFORE the run commits to resolving it — e.g. "PayPal → PYPL (the equity) vs PYUSD (the stablecoin)". `subject_ref.resolve_subject()` (TD-030) is only the LOOKUP; deciding WHICH subject an ambiguous prompt means is this gate's job. subject_ref deliberately does not branch on ambiguity, so today the binding is implicit (USDC only) with no disambiguation step.

**Why it matters.** Without it, an ambiguous prompt either silently resolves to the one bound subject or returns `None` — no confirmation that the run is about the subject the user actually meant. The gate is the safety check that the rest of the deterministic pipeline (extract → reconcile → fill) is operating on the right subject.

**Depends on / blocks.** Consumes `resolve_subject` (TD-030, built). Meaningful disambiguation needs MORE THAN ONE bound subject, so it is paired with TD-046 (multi-subject registry) — with only USDC bound there is nothing to disambiguate against. Relates to the original 4-gate `subject_confirm_gate` design (B.0); this is its analysis-layer counterpart at the resolver front door.

**Source tail:** TD-030 "Build the subject-confirm gate that consumes `resolve_subject` and handles the ambiguous-name case before the run commits to a subject" (+ its "Deferred follow-up" paragraph).

---

## TD-046 — multi-subject registry (expand bound subjects beyond USDC)

**Status:** active 2026-06-05 (extracted from the deferred tails of TD-030 + TD-036 + TD-038).

**What it is.** Expand the subjects bound in `analysis_layer/resolvers/subject_ref.py` + its registry beyond USDC — next stablecoins (USDT, DAI, PYUSD, …), then chains / tokens. Each addition is a DATA edit: every binding (decimals · per-source ids · contract + chain · issuer + CIK) harvested from and cross-checked against a real on-disk envelope (`meta/raw/<source>/`), per the TD-030 grounding rule.

**Why it matters.** Today the whole pipeline (fetch front, orchestrator, fillers, bundle) is provably end-to-end but only ever for USDC — "only USDC is bound" is the single most-repeated remaining gap across TD-030 / TD-036 / TD-038. Multi-subject is what turns the harness from a USDC demo into general coverage, and it is the precondition for TD-045 (disambiguation needs ≥2 subjects to choose between).

**Depends on / blocks.** Pure data edits on TD-030's registry; no new module. Blocks TD-045 (meaningful disambiguation). Also surfaces the non-stablecoin fetcher-set work (`SOURCES_BY_TYPE` chain / protocol rows, TD-038) and the token-schema gap (TD-017) once subjects beyond stablecoins are added.

**Source tails:** TD-030 "Populate the registry with the next subjects"; TD-036 "Multi-subject registry (only USDC is bound today)"; TD-038 "multi-subject (only USDC is bound in the registry)."

---

## TD-047 — ④ renderer redesign (report-writer chain step ④)

**Status:** active 2026-06-05 (next build — extracted from TD-041's "Still ahead" tail; the report-writer chain is ① facts bundle = TD-041, ② orchestrator wiring + ③ writer brief = TD-042, render-html (first cut) = TD-040).

**What it is.** Redesign the markdown→HTML renderer (TD-040's `analysis_layer/render/html.py` was the first, focused cut) into a **locked-design** HTML report: borrow the equity `report_writer` locked-template pattern (SHA-pinned skeleton + `{{PLACEHOLDER}}` substitution — see TD-006 for the dormant equity contract this revives, crypto-adapted), so the output is ready-to-read / portfolio-grade rather than a raw badge-annotated markdown dump. PLUS a **mechanical strip backstop** for the coaching channel: `> GUIDANCE` / `> TRAP` / `> ↳ Cap check` blockquotes are today stripped only by the writer (per the crypto-report-writer brief, M5 — see TD-042); the renderer should ENFORCE the strip too, defense-in-depth so coaching can never leak into the deliverable even if the writer misses one.

**Why it matters.** Two payoffs: (a) a locked design makes the report portfolio-grade and visually consistent run-to-run instead of dependent on the writer's markdown discipline; (b) the strip backstop GUARANTEES the internal coaching channel (`GUIDANCE`/`TRAP`/`Cap check`) never reaches the reader — a correctness/safety property, not a cosmetic one, that currently rests on a single layer.

**Depends on / blocks.** Builds on TD-040 (render-html first cut) and TD-042 (the writer brief that defines the coaching-channel markers it must strip). Revives the locked-template discipline parked in TD-006 (the crypto report skeleton + SHA pin TD-006 was waiting for). Independent of TD-048 (they are separate chain steps over the same written report — ④ renders it, ⑤ verifies it).

---

## TD-048 — ⑤ no-fabrication + confidence-cap gate (report-writer chain step ⑤)

**Status:** active 2026-06-05 (extracted from TD-041's "Still ahead" tail).

**What it is.** A programmatic gate over the written report that verifies two invariants: (1) **no fabrication** — every number in the prose traces back to the run's `.facts.json` (TD-041 bundle); the writer invented nothing and did NOT override a machine-filled number; and (2) **confidence-cap respect** — a claimed confidence never exceeds the Front-Matter §C caps, checked via a STANDARDIZED, language-agnostic confidence token so the gate works identically on en and zh reports (no NL parsing of "High"/"高").

**Why it matters.** The facts bundle is FACTS-ONLY by design (TD-041 — no prose, no verdict) and the writer is an LLM; ⑤ is the closing-the-loop check that the LLM's freedom to write prose did not let it drift from the deterministic data or over-claim certainty. It is the fail-closed gate that makes the agent-driven narrative auditable.

**Depends on / blocks.** Consumes the `.facts.json` (TD-041) + the §C confidence caps + the written report. Requires a standardized confidence token to exist (may need a small token convention added to the writer brief, TD-042). **★ ⑤ is the FIRST concrete piece of the broader B.3 QC layer (TD-049)** — it is the deterministic, in-house half of verification; the adversarial/red-team and external-third-source half lives in TD-049.

---

## TD-049 — B.3 QC / red-team / web-third-source verification layer (umbrella)

**Status:** deferred 2026-06-05 (phase-level — B.3; consolidates the "web third-source + red-team checks (B.3)" tails repeatedly deferred across TD-032, TD-033, TD-036, TD-037).

**What it is.** The umbrella verification phase over the filled deliverable, two halves: (a) **adversarial / red-team review** — attack the report's claims, thesis, and the §5.5 verdict for unsupported leaps (repurposing the inherited `red_team_narrative.md` pattern, cf. TD-001); and (b) **a web-sourced 3rd source** added to the reconciliation so a metric is no longer single-source — breaking the Rule-1 `single_source → capped MEDIUM` ceiling that EVERY USDC run currently hits (a metric with only one authority can never read better than MEDIUM, no matter how trustworthy, until a genuinely independent third source agrees).

**Why it matters.** Today's reports are honest but ceiling-bound: most facts cross-check only CoinGecko↔CMC or sit single-source, so confidence is structurally capped. B.3 is what lets a well-corroborated metric earn HIGH, and what red-teams the narrative the way the data layer is already reconciled — the qualitative QC the deterministic layers can't self-perform.

**Depends on / blocks.** Umbrella over TD-048 (⑤ is its first, in-house piece — the no-fabrication/cap gate). Distinct from ⑤ in that it adds EXTERNAL signal (a third web source) + adversarial review, where ⑤ is purely internal consistency. Would consume the aggregator's `single_source` flags (TD-032) and the source-authority table (TD-031, which it would extend with the third source). Sequenced after the chain ④/⑤ land.

---

## B.0 #16 MEMORY.md staging — pending lessons

Lessons surfaced during B.0 sub-phase work that should land in `MEMORY.md` when deliverable #16 (MEMORY.md rewrite for the 4-gate set) is executed. This is a recurring slot — append new lessons as they emerge.

### Lesson: "human readability" is not a default assumption

**Status: LANDED in MEMORY.md (B.0 Step 6, commit pending).**

When designing spec files in an LLM-agent workflow, ask "who directly reads this file, when?" before optimizing for human readability. Many agent-mediated workflows have users interact only via agent translation — direct file reads are rare. Optimizing for "human readability inline with data" in those cases may add complexity (e.g., needing a parser-based write tool for markdown-with-YAML) rather than reduce it.

**Origin:** B.0 #2 originally designed `references/subject_relationships.md` as a markdown+YAML hybrid. User challenged the "human readability" assumption mid-flight (B.0 mid-flight session, 2026-05-13); correct architecture was data (`.yaml`) + design (`.md`) split. TD-013 reduced from 9-step parser to 3-line pyyaml wrapper.

**Applies to:** future spec file design. Don't default to markdown+YAML hybrid without first justifying why a human directly reads the file. If the answer is "they don't, the agent translates", split data from design.

### Lesson: mid-flight course corrections are first-class moves

**Status: LANDED in MEMORY.md (B.0 Step 6, commit pending).**

When a foundational assumption is challenged mid-deliverable, pause the deliverable, steel-man the challenge, sanity-check the alternative architecture **before** editing files. The cost of a 10-step migration before deeper work depends on the wrong architecture is far smaller than the cost of unwinding the wrong architecture after it has propagated to 5+ files. Mid-flight corrections are not "thrash" — they are the cheapest point at which to catch a wrong design.

**Origin:** B.0 #2 markdown+YAML → split into `.yaml` + `_design.md`, mid-flight during B.0 deliverable sequencing, 2026-05-13. The pattern executed: user challenged the assumption in one sentence; agent steel-manned the challenge instead of defending the design; we paused and sanity-checked the split before any file changes; 10-step migration executed atomically; lesson staged for permanent capture in `MEMORY.md`. This is the Anamnesis Pattern working as designed — catch design errors early, write the lesson, don't pay the cost twice.

**Applies to:** any deliverable where a foundational assumption surfaces under challenge. The right move is to pause, not to defend. Pausing is cheaper than unwinding.

**Additional origin (2026-05-13, same day as #2 split):** B.0 mid-flight restart to 4-gate design. Discovered 7-gate framework was inherited from Phase A equity-era without challenging whether it served crypto research workflow. Restart cost: 7 agent files removed (~1600 lines of in-progress design work), ~5.5 session redo. Restart vs unwinding cost ratio: ~1:3 (mid-flight cheaper than post-completion correction).

The pattern reinforced: when foundational assumption is challenged, steel-man the challenge, restart cleanly, do not patch around it.

### Lesson candidate: "different prompt = different run"

**Status: LANDED in MEMORY.md (B.0 Step 6, commit pending).**

When a P0 gate's processing implies that the user's intent warrants a different prompt (e.g., narrowing a sector prompt to a single-subject prompt), the right architectural move is **abort + ask the user to re-run**, NOT internal restart-from-gate with prompt substitution. Two prompts means two runs; the audit trail of each run is cleaner if it corresponds to exactly one prompt. Internal restart mechanisms that splice two prompts into one run trade audit clarity for marginal UX savings (one extra command typed by the user vs. mangled audit history).

**Origin:** B.0 #6 (`agents/scope_gate.md`) initially designed path (a) sector narrow with internal restart-from-gate; user challenged the necessity 2026-05-13; correction made path (a) abort + user re-run; TD-015 (orchestrator restart capability) closed-as-unnecessary.

**Applies to:** future gate design when "user changed their mind / clarified intent" could be interpreted as "same run, patch state" vs. "different intent, new run". Default to "different intent = new run" unless there is explicit justification for in-run patching.

### Lesson candidate: over-engineering through inherited framework

**Status: LANDED in MEMORY.md (B.0 Step 6, commit pending).**

When forking a harness for a new domain, the inherited framework's shape (gate count, decision points, abstractions) must be challenged against the new domain's actual workflow — NOT silently adopted as default. Inherited frameworks carry assumptions about user behavior that may not transfer. The cost of detecting framework mismatch early (mid-design) is far smaller than detecting it late (mid-implementation).

**Origin:** Phase A inherited 7-gate framework from equity research era. Phase B silently extended it without asking "what does the crypto research workflow actually need?" Mid-flight at B.0 #9 (after 9 ship deliverables), user described a 4-step user-visible flow that exposed 3 gates as over-engineering. Restart cost was 5.5 session; unwinding after B.0 completion would have been 12+ session.

**Applies to:** any fork or domain extension. Before adopting inherited framework, walk through the new domain's actual user workflow end-to-end and verify each framework element earns its place. Default to fewer abstractions, not more.

**Detection signal:** if you can't immediately answer "what does GATE_X do for THIS user's workflow", that gate may be over-engineering. The answer should be specific to the new domain, not generic.

---

# B.0 Restart — Completion Declaration

**Status: COMPLETE 2026-05-21.** Steps 1-6 shipped; Step 7 deferred 
to B.5+ (template reconciliation deferred per TD-019, now superseded by TD-042 — v2 template promoted to live).

## Commits (12 total)

1. 7c2d42a + 50fbeb9 — Step 1: clean slate
2. f927c9d — Step 2: research_dimensions.md (canonical 4-gate contract)
3. bbf2589 — Step 3a: agents/subject_confirm_gate.md
4. 27581a2 — Step 3b: agents/sec_email_gate.md
5. b065055 — Step 3c: agents/freshness_gate.md (+ TD-017 opened)
6. 871b033 — TD-016 backfill (user_agent slug)
7. 0285778 — Step 3d: agents/language_gate.md
8. 5972d70 + 1428d63 — Pre-Step-4 cleanup (TD-002 re-scoped, TD-003 
   closed, TD-018/TD-019 opened, .gitignore deduped, palette_gate + 
   intent_resolver removed)
9. 3cabd18 — Step 4: data_source_registry.md §7-§13 (+ TD-020 opened)
10. cfe666b — Step 5: wire-up (workflow_meta.json + p0_gates.md + 
    phase_contract.md + TD-018 item 7)
11. d2d6544 — Step 6: MEMORY.md rewrite + INCIDENTS.md sweep + 4 
    lessons LANDED

## Final design state

- **4 canonical gates**: subject_confirm / sec_email (conditional) / 
  freshness / language
- **13 registered data sources**: 6 core (§1-§6) + 7 conditional 
  (§7-§13) — 11 active for B.1 implementation (3 archived pending 
  budget; see TD-021)
- **5 subject classes**: stablecoin_issuer, orchestrator, wallet, 
  chain, agentic_payment_layer (single-subject only; sector → Phase C)
- **2 writer modes**: monolingual (en/zh) + dual writer (both) + 
  bilingual writer (side_by_side)
- **I-003 two-UA invariant**: sec_user_agent (SEC EDGAR only) + 
  public_user_agent (all else)
- **No sticky, no USER.md, no defaults on non-answer**

## TD ledger handoff to B.1+

**Closed in B.0**:
- TD-003 (365d freshness — resolved by 4-gate enum)
- TD-009 (SEC EDGAR secret pattern — instantiated in B.0 #1.5)
- TD-014 (event vocabulary registry — unnecessary at current scale)
- TD-015 (orchestrator restart-from-gate — design moved to 
  abort+re-run)

**Active, transferred to B.1**:
- TD-001 (X long-post quality rubric — design at first thread run)
- TD-002 (sector / comparison expansion — Phase C)
- TD-004 (issuer attestation feeds)
- TD-005 (CEX APIs)
- TD-006 (locked-skeleton template — paired with crypto report 
  skeleton design)
- TD-007 (QC merge math + competitive framework — Phase B writer)
- TD-008 (card-pack rules — paired with card pipeline rebuild)
- TD-010 (orchestrator §P1+ + HARNESS rewrite — Phase B pipeline)
- TD-011 (validate seed CIKs — paired with first SEC EDGAR fetcher)
- TD-012 (lint_subject_relationships.py — B.1 paired)
- TD-013 (append_subject_entry.py — B.1 paired)
- TD-017 (yaml schema for tokens — B.1 first token research)
- TD-018 (Gen 1/2 residue sweep, 7 files — each file's rewrite step)
- TD-020 (B.1 verification of Medium-confidence sources)

**B.1 deliverables blocked by active TDs**: see TD-011, TD-012, 
TD-013 for B.1's first SEC EDGAR fetcher dependencies.

## Mid-flight lessons preserved (now in MEMORY.md)

The 4 design lessons from B.0 #16 staging are now in MEMORY.md 
under 'Design lessons (load-bearing methodology)' and frozen into 
the system prompt at session start. TODO.md retains the full lesson 
bodies + Origin sections as audit trail of what was migrated.

## What B.1 does NOT touch from B.0

- 4-gate design (frozen — any change requires explicit mid-flight 
  declaration per Lesson 4)
- research_dimensions.md (canonical contract — read by all phases)
- 4 gate agent files (referenced by orchestrator)
- p0_gates.md (enforcement contract)
- workflow_meta.json phase array order
- MEMORY.md invariants

B.1 reads these as fixed contracts. Changes to these files in B.1 
require either: (a) explicit user approval with rationale, OR 
(b) opening a new TD that documents the proposed change.
