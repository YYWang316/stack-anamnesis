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

## TD-003 — 365d freshness window

**Status:** **closed-as-resolved-by-4-gate 2026-05-20** during 
B.0 pre-Step-4 cleanup audit.

**Resolution:** the 4-gate freshness enum (research_dimensions.md 
§2.3 + agents/freshness_gate.md) already includes `1 year` (= 365d) 
and `quarter` (= current fiscal quarter). The original request — 
"add a 365d freshness window" — is delivered by the `1 year` 
canonical value.

**History:** opened during equity-era 7-gate framework design when 
freshness enum was narrower; closed during B.0 mid-flight restart 
audit when 4-gate freshness enum was found to already cover the 
requested window.

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

## TD-016 — Repoint user_agent_pii.py PUBLIC_USER_AGENT to StackAnamnesis/<version>

**Status:** active 2026-05-13 (opened during B.0 #1.5 SEC EDGAR work; backfilled 2026-05-13).

tools/audit/user_agent_pii.py hardcodes:
```
PUBLIC_USER_AGENT = "EquityResearchSkill/1.0"
```

This was the equity-era slug. references/data_source_registry.md §6 (B.0 #1.5) established the new canonical:
```
PUBLIC_USER_AGENT = "StackAnamnesis/1.0"
```

And agents/sec_email_gate.md (B.0 Step 3b) emits sec_user_agent using "StackAnamnesis/1.0 (<email>)" per spec. Until tools/audit/user_agent_pii.py is repointed, P12 audit will fail on the slug mismatch.

**Required:** one-line edit in tools/audit/user_agent_pii.py to update the hardcoded slug from "EquityResearchSkill/1.0" to "StackAnamnesis/<version>". Consider parameterizing via env var or shared constant if multiple consumers need the slug.

**Why deferred:** B.0 scope is documentation + agent contracts, no new or modified tooling. The repoint is trivial (one-line edit) but belongs in B.1 alongside the first SEC EDGAR fetcher invocation when audit actually runs and the slug mismatch would surface.

**Revisit when:** B.1 first SEC EDGAR fetcher invocation OR P12 audit first runs in B.1 — whichever lands earlier.

**History:** Surfaced during B.0 #1.5 (SEC EDGAR consumer contract in data_source_registry.md) when canonical slug "StackAnamnesis/1.0" was established. Cross-referenced in agents/sec_email_gate.md (Step 3b) and agents/freshness_gate.md (Step 3c). Backfilled into TODO.md during Step 3c review when cross-reference was found dangling.

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

1. **SKILL.md** — still references Gen 1 gates: P0_lang, P0_sec_email, P0_palette, USER.md sticky mechanism.
2. **references/phase_contract.md** — references Gen 2 gates: P0_output_format, P0_scope. (Scheduled for Step 5 rewrite; this TD overlaps but tracks the residue specifically.)
3. **references/maintenance.md** — equity locked-template / submodule discipline (Gen 1 framing).
4. **references/workflow_diagram.md** — Gen 1 interactive gates + USER.md references.
5. **tools/io/incident_trigger.py:75** — emits P0_lang / P0_sec_email / P0_palette in an incident message (Gen 1 phase names).
6. **README.md** — references `skills_repo/er/ep` submodule architecture and USER.md.template (both removed).

**Why deferred:** these files are each scheduled for rewrite in a later step or sub-phase. SKILL/README/HARNESS rewrites are appropriate for end-of-B.0 or B.1 start; phase_contract.md is Step 5; maintenance/workflow_diagram are pending rewrite alongside Phase B documentation pass. Touching them piecemeal during pre-Step-4 cleanup would mix concerns.

**Required:** during each file's scheduled rewrite, sweep Gen 1/2 residue identified above. Add a verification step to the rewrite checklist: grep the file for `P0_lang|P0_palette|P0_output_format|P0_scope|USER.md|skills_repo|equity` and confirm each hit is intentional (archive citation, history note) or fixed.

**Revisit when:** each file's scheduled rewrite step lands. For coordination, list affected files in the rewrite step's commit message.

**History:** Surfaced during B.0 pre-Step-4 cleanup audit (2026-05-20) when agent surveyed Phase A residue category. The 4-gate spec layer is internally clean; residue is in older layer files awaiting rewrite.

---

## TD-019 — crypto_report_template.md 4-gate design reconciliation

**Status:** active 2026-05-20 (opened during B.0 pre-Step-4 cleanup audit).

crypto_report_template.md (currently untracked at repo root, v1.2, 513 lines, YYFoundry/NYU branded) predates the 4-gate design and contains content that contradicts the current spec:

1. **Lines 59-60 contradict the new language enum:** template states "both 模式会并行产出两份独立 HTML (不是双语对照)" — i.e., it explicitly excludes the side_by_side value that Gate 4 now defines. With side_by_side as a canonical enum value, this template language is wrong.

2. **Line 35 contradicts §2.1 subject_confirm spec:** template includes "Subject Type: □ Chain □ L2 □ DeFi □ News □ Asset/Token" as a user-facing input — but research_dimensions.md §2.1 explicitly forbids asking subject_type ("the agent never asks subject_type"). guessed_type is internal-only in the 4-gate design.

3. **Gen 1/Gen 2 concepts still present:** Mode A/B auto-detection (Gen 1), Scope/sector inputs (Gen 2 P0_scope), Output Type selection (Gen 2 P0_output_format). All eliminated in 4-gate redesign.

**Why deferred:** Step 7 of the B.0 restart was scheduled to MOVE this file from repo root into references/. The audit reveals the move alone is insufficient — the content needs reconciliation against the 4-gate design first. Moving a contradictory document into references/ would propagate the contradictions into the canonical reference layer.

**Required:** before (or as part of) Step 7's move:
1. Update language enum section (lines 59-60) to reflect 4 values (en/zh/both/side_by_side), with both vs side_by_side semantics distinguished per §2.4.
2. Remove the Subject Type checkbox (line 35) and any narrative that surfaces type-selection to the user.
3. Remove Mode A/B / Scope/sector / Output Type sections; replace with 4-gate flow if user-visible checkpoints are still desired.
4. Verify the YYFoundry brand content (workshop notes, "Bit != Coin" framing) survives the rewrite — those are unrelated to 4-gate semantics and should be preserved.

**Why both this and Step 7:** Step 7's scope was "trivial move". This TD captures the substantive design alignment work that the move surfaces. They can be combined into a single commit when both are ready, or executed separately (TD-019 first, then trivial Step 7 move). User's choice.

**Aligns with TD-006** which already notes that the locked-HTML template skeleton is pending design.

**History:** Surfaced during B.0 pre-Step-4 cleanup audit (2026-05-20) when agent compared crypto_report_template.md head + language/side_by_side scan against the 4-gate spec.

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

## B.0 #16 MEMORY.md staging — pending lessons

Lessons surfaced during B.0 sub-phase work that should land in `MEMORY.md` when deliverable #16 (MEMORY.md rewrite for the 4-gate set) is executed. This is a recurring slot — append new lessons as they emerge.

### Lesson: "human readability" is not a default assumption

When designing spec files in an LLM-agent workflow, ask "who directly reads this file, when?" before optimizing for human readability. Many agent-mediated workflows have users interact only via agent translation — direct file reads are rare. Optimizing for "human readability inline with data" in those cases may add complexity (e.g., needing a parser-based write tool for markdown-with-YAML) rather than reduce it.

**Origin:** B.0 #2 originally designed `references/subject_relationships.md` as a markdown+YAML hybrid. User challenged the "human readability" assumption mid-flight (B.0 mid-flight session, 2026-05-13); correct architecture was data (`.yaml`) + design (`.md`) split. TD-013 reduced from 9-step parser to 3-line pyyaml wrapper.

**Applies to:** future spec file design. Don't default to markdown+YAML hybrid without first justifying why a human directly reads the file. If the answer is "they don't, the agent translates", split data from design.

### Lesson: mid-flight course corrections are first-class moves

When a foundational assumption is challenged mid-deliverable, pause the deliverable, steel-man the challenge, sanity-check the alternative architecture **before** editing files. The cost of a 10-step migration before deeper work depends on the wrong architecture is far smaller than the cost of unwinding the wrong architecture after it has propagated to 5+ files. Mid-flight corrections are not "thrash" — they are the cheapest point at which to catch a wrong design.

**Origin:** B.0 #2 markdown+YAML → split into `.yaml` + `_design.md`, mid-flight during B.0 deliverable sequencing, 2026-05-13. The pattern executed: user challenged the assumption in one sentence; agent steel-manned the challenge instead of defending the design; we paused and sanity-checked the split before any file changes; 10-step migration executed atomically; lesson staged for permanent capture in `MEMORY.md`. This is the Anamnesis Pattern working as designed — catch design errors early, write the lesson, don't pay the cost twice.

**Applies to:** any deliverable where a foundational assumption surfaces under challenge. The right move is to pause, not to defend. Pausing is cheaper than unwinding.

**Additional origin (2026-05-13, same day as #2 split):** B.0 mid-flight restart to 4-gate design. Discovered 7-gate framework was inherited from Phase A equity-era without challenging whether it served crypto research workflow. Restart cost: 7 agent files removed (~1600 lines of in-progress design work), ~5.5 session redo. Restart vs unwinding cost ratio: ~1:3 (mid-flight cheaper than post-completion correction).

The pattern reinforced: when foundational assumption is challenged, steel-man the challenge, restart cleanly, do not patch around it.

### Lesson candidate: "different prompt = different run"

When a P0 gate's processing implies that the user's intent warrants a different prompt (e.g., narrowing a sector prompt to a single-subject prompt), the right architectural move is **abort + ask the user to re-run**, NOT internal restart-from-gate with prompt substitution. Two prompts means two runs; the audit trail of each run is cleaner if it corresponds to exactly one prompt. Internal restart mechanisms that splice two prompts into one run trade audit clarity for marginal UX savings (one extra command typed by the user vs. mangled audit history).

**Origin:** B.0 #6 (`agents/scope_gate.md`) initially designed path (a) sector narrow with internal restart-from-gate; user challenged the necessity 2026-05-13; correction made path (a) abort + user re-run; TD-015 (orchestrator restart capability) closed-as-unnecessary.

**Applies to:** future gate design when "user changed their mind / clarified intent" could be interpreted as "same run, patch state" vs. "different intent, new run". Default to "different intent = new run" unless there is explicit justification for in-run patching.

### Lesson candidate: over-engineering through inherited framework

When forking a harness for a new domain, the inherited framework's shape (gate count, decision points, abstractions) must be challenged against the new domain's actual workflow — NOT silently adopted as default. Inherited frameworks carry assumptions about user behavior that may not transfer. The cost of detecting framework mismatch early (mid-design) is far smaller than detecting it late (mid-implementation).

**Origin:** Phase A inherited 7-gate framework from equity research era. Phase B silently extended it without asking "what does the crypto research workflow actually need?" Mid-flight at B.0 #9 (after 9 ship deliverables), user described a 4-step user-visible flow that exposed 3 gates as over-engineering. Restart cost was 5.5 session; unwinding after B.0 completion would have been 12+ session.

**Applies to:** any fork or domain extension. Before adopting inherited framework, walk through the new domain's actual user workflow end-to-end and verify each framework element earns its place. Default to fewer abstractions, not more.

**Detection signal:** if you can't immediately answer "what does GATE_X do for THIS user's workflow", that gate may be over-engineering. The answer should be specific to the new domain, not generic.
