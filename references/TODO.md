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

## TD-002 — Add `sector` and `stack_position` scopes when pipelines exist

**Decision (2026-05-12):** P0_scope enum starts with `single` only. The multi-subject scopes (sector for horizontal comparison, stack_position for vertical dependency trace) are deferred until their pipelines exist.

**Why:** P0 gate values must route to real phase pipelines. Adding enum options without backing pipelines violates the "rule must be enforceable in code" principle inherited from references/inherited_principles.md.

**Revisit when:**

- 20+ single-scope runs accumulated, OR
- An incident logs "writer attempted comparison but no pipeline available", OR
- Manual sector/stack-trace work becomes a recurring pain

## TD-003 — Add 365d freshness window when mature subjects warrant it

**Decision (2026-05-12):** P0_freshness enum is `7d / 30d / 90d / since_TGE`. Skips 365d because current research subjects (crypto payments infra, agentic payments) are mostly < 2 years old, where 365d ≈ since_TGE provides no analytical difference.

**Revisit when:**

- We start covering protocols > 2 years old (Aave, Uniswap, Maker) and finding lifetime data too noisy
- A validator phase wants to compare "365d window vs lifetime" as a signal-quality check
- An incident logs "writer averaged across full history when only recent year was relevant"

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

**Decision (2026-05-12):** Removed the SEC EDGAR email privacy bullet from `MEMORY.md`'s `## Privacy invariants` section. The deleted bullet stated: "SEC EDGAR email is **never** persisted. It lives only as a runtime arg to `tools/research/sec_edgar_fetch.py`." With `P0_sec_email` retired and SEC EDGAR not a crypto-domain data source, the rule has no live surface.

**Why:** The *shape* of the rule (never-persist, runtime-only, regex redaction guard with a `tests/test_db_pii.py` regression) is the right template for any future API key or credential the crypto harness needs — Dune API key, Alchemy/Infura/QuickNode keys, Etherscan family keys, Pro CoinGecko key, RPC bearer tokens (see `references/data_source_registry.md` for the full key inventory). But the SEC-specific instance does not apply. Removing it now and re-introducing the pattern when the first secret-requiring API is integrated keeps the harness from carrying a dead rule while preserving the template's existence as this TD.

**Revisit when:**

- The first secret-requiring crypto API is integrated (likely Dune or Etherscan during the first `output_format: report` run), AND
- A `tests/test_db_pii.py`-style regression is wired for the new secret family — at which point the pattern returns to `MEMORY.md` with the new key family name in place of `sec_email`, the new redaction regex in place of the email regex, and the new key path (`~/.config/anamnesis/<provider>.key` per `references/data_source_registry.md`) replacing the SEC EDGAR runtime arg

## TD-010 — Phase B harmonization pass: stale MEMORY.md references in orchestrator.md §P1+ and HARNESS.md ownership table

**Decision (2026-05-12):** orchestrator.md:174 references "QC scoring math from MEMORY.md" (the equation deleted in Phase A per TD-007), and HARNESS.md:240 lists "Locked HTML template" in an ownership table (the hard rule deleted in Phase A per TD-006). Phase A's scope discipline (P0-only) left these untouched. Both will be resolved during Phase B's broader orchestrator §P1+ and HARNESS rewrites.

**Revisit when:** Phase B redesigns the P1+ pipeline (which will rewrite orchestrator §P1+ end-to-end) and the HARNESS overview (which will rebuild the ownership table for the crypto-shaped pipeline).
