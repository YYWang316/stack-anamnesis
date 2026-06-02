<!--
keywords: Stack Anamnesis, crypto research pipeline, stablecoin research, on-chain data reconciliation, USDC analysis, source-authority reconciliation, supply momentum signal, module-aware template fill, Anamnesis Pattern, agent institutional memory, deterministic research pipeline
-->

# Stack Anamnesis

> **A deterministic crypto-research pipeline: one subject in, one reconciled, provenance-tracked markdown report out.** Built on (and disciplined by) the **Anamnesis Pattern** — cross-session institutional memory + adversarial review.

```bash
python -m analysis_layer.orchestrate USDC            # analyse on-disk envelopes → report
python -m analysis_layer.orchestrate USDC --fetch    # refresh from source APIs first, then analyse
```

That one command resolves the subject, gathers data from up to **seven source fetchers**, extracts typed facts, **reconciles them by source authority (never by averaging)**, derives the supply-momentum signal, fills a module-aware template, and writes a clean per-subject markdown report to `meta/reports/`.

---

## What this repo actually does today

The live, tested pipeline lives entirely under [`analysis_layer/`](analysis_layer/). It is a single-subject crypto research pipeline whose current bound subject is **USDC (issuer: Circle)**. Given a subject it produces a markdown research report by filling [`references/templates/crypto_research_v1.3.md`](references/templates/crypto_research_v1.3.md) (whose content header reads *Research SOP v1.4* — the unified master template with the Part 5.1–5.5 subject-type modules).

The data flow, end to end:

```
subject (e.g. USDC)
   │
   │  [--fetch only]  fetch_front.py → run the B.1 fetchers (isolated, timed, best-effort)
   ▼                  writing fresh envelopes to meta/raw/<source>/
meta/raw/<source>/*.json   (uniform JSON "envelopes")
   │
   ▼  extractors/      one pure fn per source: envelope dict → typed ExtractedValue | None
   │                   (alchemy, etherscan, coingecko, coinmarketcap, defillama, sec_edgar)
   ▼  resolvers/       subject_ref (subject → decimals / ids / issuer), source_authority
   │
   ▼  aggregators/     reconcile() — cross-source → single best value + audit trail,
   │                   chosen by per-metric SOURCE AUTHORITY, not by averaging
   ▼  derivations/     supply_change — net 7d / 30d / 90d supply momentum (KEY SIGNAL leg 1/3)
   │
   ▼  fillers/         fill() — MODULE-AWARE, TAG-AWARE template fill, keyed on subject_type
   │                   ([AUTO] / [SEMI-AUTO] / [MANUAL])
   ▼
meta/reports/<subject>_<UTC>.md   (clean, subject-typed markdown report)
```

[`orchestrate.py`](analysis_layer/orchestrate.py) is the front door — `research()` / `build_report()` plus a thin CLI. By default it is **pure**: it reads whatever envelopes already sit under `meta/raw/`, makes no network calls, reads no API keys, and is byte-deterministic for a fixed set of envelopes (only the output filename's UTC stamp changes). The `--fetch` flag turns on the one impure half ([`fetch_front.py`](analysis_layer/fetch_front.py)), which refreshes the envelopes first by shelling out to the fetchers in `tools/fetchers/`, then runs the same pure analysis over whatever landed.

### Design properties that are actually enforced in code

- **Authority, not averaging.** The aggregator reconciles competing values by a per-metric source-authority order (CoinGecko = price/market-cap, DefiLlama = TVL, on-chain Etherscan/Alchemy = supply truth, CMC = cross-check). It never silently averages two sources into a fake middle. Different *scopes* (cross-chain total vs Ethereum-only supply) are never reconciled against each other.
- **Best-effort, never crash.** A missing or malformed envelope, or a failed fetcher (missing key, rate-limit, timeout), is recorded as a note and skipped — the report still builds and the affected section stays flagged.
- **Flagged, not fabricated.** An `[AUTO]` slot with no reconciled value is rendered as `⚠ UNFILLED [AUTO]`; a `[SEMI-AUTO]` slot is rendered as `⚠ NEEDS HUMAN REVIEW`. Empty data is shown as empty, never invented.
- **Module-aware fill.** Only the template sections that apply to the subject's `subject_type` are rendered. For a stablecoin (USDC) the report fills Part 5.5 (stablecoin module) and the issuer-financials path; chain-only sections (5.1/5.2) are correctly omitted, not left as noise.
- **Provenance carried, not re-derived.** Every extracted fact travels with its `source`, `unit`, and `as_of` timestamp, so the aggregator reconciles without re-reading raw, and the `as_of` gap between two on-chain reads is accounted for rather than false-flagged as a discrepancy.
- **Secrets stay in process memory.** `fetch_front` never reads, logs, or persists an API key — each fetcher reads its own key from `~/.config/anamnesis/<source>.key`. The SEC contact email is read from `$ANAMNESIS_SEC_EMAIL`, passed to the SEC fetcher's `--sec-email`, and scrubbed from every returned note.

### Sources

Seven fetchers live in [`tools/fetchers/`](tools/fetchers/): `alchemy`, `coingecko`, `coinmarketcap`, `defillama`, `etherscan`, `l2beat`, `sec_edgar`. The stablecoin fetch set runs six of them (all but `l2beat`, which has no extractor mandate yet). Six extractors are wired in the orchestrator — including `sec_edgar`, so Circle's regulated SEC financials (latest-consistent fiscal year, per TD-037) flow into the report's Evidence Table alongside the on-chain metrics.

> **Scope today:** only `USDC` is bound in the subject_ref registry, and only the `stablecoin` subject_type has a defined fetcher set. Adding a new subject means adding its bindings in [`analysis_layer/resolvers/subject_ref.py`](analysis_layer/resolvers/subject_ref.py); adding a new subject_type means adding a row to `SOURCES_BY_TYPE`.

For the layer's full design and roadmap see [`analysis_layer/README.md`](analysis_layer/README.md); for the deferred design notes see [`references/TODO.md`](references/TODO.md).

---

## The Anamnesis Pattern — the discipline this repo is built under

The pipeline above is built and maintained under a methodology the maintainer carries across projects: the **Anamnesis Pattern** (Greek *ἀνάμνησις*, "recollection"). Most agent harnesses lose their scar tissue every time a new context window opens — every session starts as a junior on day one, blind to last quarter's near-miss. The Anamnesis Pattern is what an agent harness looks like when you refuse to lose it.

Its four beats — **Curate · Freeze · Read · Verify (CFRV)** — close the feedback loop most harnesses leave open:

1. **Curate** — a *human* (not an auto-logger) turns each real failure into one permanent rule via `/log-incident`. Curation is the throttle that keeps the memory from inflating into noise.
2. **Freeze** — the rule appends to `INCIDENTS.md` and is loaded verbatim into the next session's system prompt at boot, alongside `MEMORY.md`. The agent doesn't have to *decide* to look the rule up; it is already in front of it.
3. **Read** — a pre-check phase reads every rule before work starts.
4. **Verify** — a post-check phase re-checks every rule before delivery; a relapse blocks shipping.

Plus a fifth axis: at named gates, two adversarial reviewers (a numeric attacker and a narrative attacker) try to *falsify* the draft — distinct from QC peers, who vote on *agreement*.

This is the framework the maintainer keeps as discipline; see [`references/anamnesis_pattern.md`](references/anamnesis_pattern.md) for the full generalised methodology.

> **Honest status of the loop in this fork.** `INCIDENTS.md` is currently an **empty scaffold** — no incident has been logged for the crypto pipeline yet (mature-domain examples are archived in `references/equity_incidents_archive.md`, not enforced). The `/log-incident` command, the lint tool, and the schema/wiring tests around the loop are live and pass against the empty log; the first real crypto failure captured via `/log-incident` becomes `I-001`. The full multi-agent gate/red-team/post-check *runtime* described in `workflow_meta.json` is **not** the path the crypto pipeline runs (see Status below).

---

## The inherited equity harness — kept as method reference, not the live path

This repo was forked from an upstream equity-research harness (originally codenamed `equiforge`). A substantial amount of that harness is still in the tree — `anamnesis.py`, `workflow_meta.json`, `agents/`, `tools/research/`, `tools/photo/`, `tools/audit/`, `db/`, `HARNESS.md`, the equity-era `SKILL.md`, and the equity test suite. **It is retained deliberately as a reusable substrate and method reference**, not because the crypto pipeline runs through it.

The two are **decoupled at the code level**: `analysis_layer/` imports only the Python standard library and itself — **zero imports** from `anamnesis.py`, `workflow_meta.json`, `agents/`, or the `tools/research|photo|audit` packages. The only cross-boundary call is `fetch_front` shelling out to the crypto fetchers in `tools/fetchers/` as subprocesses. You can read, run, and reason about the crypto pipeline without touching the inherited harness at all.

If you came here for the equity harness's architecture, `HARNESS.md` still documents it. Just don't mistake it for what `python -m analysis_layer.orchestrate` does.

---

## Repository layout

```
stack-anamnesis/
├── analysis_layer/              # ★ the live crypto pipeline (stdlib-only; zero equity imports)
│   ├── orchestrate.py           #   front door — research() / build_report() + CLI (pure by default)
│   ├── fetch_front.py           #   the one impure half — --fetch refreshes envelopes (best-effort)
│   ├── contract.py              #   ExtractedValue / ReconciledValue / SubjectRef dataclasses
│   ├── extractors/              #   one pure fn per source: envelope → typed value | None
│   ├── resolvers/               #   subject_ref (subject → decimals/ids), source_authority
│   ├── aggregators/             #   reconcile() — authority-based cross-source reconciliation
│   ├── derivations/             #   supply_change — net 7d/30d/90d supply momentum
│   ├── fillers/                 #   fill() — module-aware, tag-aware template fill
│   └── README.md                #   the layer's persisted design + roadmap
│
├── tools/fetchers/              # 7 source fetchers (alchemy, coingecko, coinmarketcap,
│                                #   defillama, etherscan, l2beat, sec_edgar) — invoked by fetch_front
├── references/
│   ├── templates/crypto_research_v1.3.md   # the report template (content header: SOP v1.4)
│   ├── anamnesis_pattern.md     #   the methodology, generalised
│   ├── TODO.md                  #   deferred design notes (TD-NNN)
│   └── equity_incidents_archive.md         # archived equity-domain incidents (reference, not enforced)
├── meta/
│   ├── raw/<source>/*.json      #   fetched envelopes (gitignored runtime input)
│   └── reports/                 #   ★ generated reports land here
│
├── INCIDENTS.md                 # institutional-memory log (currently an empty scaffold)
├── MEMORY.md                    # project invariants — frozen into the system prompt at boot
├── SKILL.md / .claude/ / .agents/   # skill entry + host mounts (mounts mirror root frontmatter)
│
│  — inherited equity harness, retained as method reference (NOT the live path) —
├── anamnesis.py                 # equity-era deterministic-phase driver
├── workflow_meta.json           # equity-era phase/gate contract (stale residue, see TD-010)
├── HARNESS.md                   # equity harness architecture doc
├── agents/  tools/research/  tools/photo/  tools/audit/  db/
│
└── tests/                       # pytest suite (crypto pipeline + inherited equity tests)
```

`skills_repo/` is present but **empty** — there are no SHA-pinned `er`/`ep` submodules checked out and no `.gitmodules` in this fork. Tests that depend on the `ep` (Equity Photo) submodule skip themselves when it is absent.

---

## Tests

```bash
python3 -m pytest -q
```

The crypto pipeline (`tests/analysis_layer/`) and the inherited equity suite both run. A few inherited tests are guarded behind skips where their prerequisite is not present in this fork — the photo-card tests skip when the `ep` submodule is not checked out, and one incident-coverage test skips while `INCIDENTS.md` is an empty scaffold (see TD-039 in `references/TODO.md`). Everything else passes.

---

## License

Apache-2.0.
