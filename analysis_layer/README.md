# Analysis Layer (Lane A)

Turns the uniform JSON envelopes that B.1 fetchers write to
`meta/raw/<source>/` into **typed, reconciled metrics** that fill the markdown
research template (`references/templates/crypto_research_v1.2.md`).

This README is the persisted design + roadmap. B.2.0 (this commit) scaffolds
the layer, fixes the extractor output contract, and ships **one** extractor
end-to-end (Alchemy) to prove the contract. Everything else is documented here
and built later.

## Architecture

```
analysis_layer/
  contract.py    # ExtractedValue — the shared extractor output contract
  extractors/    # one module per source; PURE fn: envelope dict -> ExtractedValue | None
  resolvers/     # source_authority (per-metric priority), subject_ref (subject -> decimals/ids)
  aggregators/   # cross-source reconciliation -> single best value + audit trail
  fillers/       # tag-aware markdown-template filler ([AUTO]/[SEMI-AUTO]/[MANUAL])
```

Data flow (Lane A):

```
meta/raw/<source>/*.json  -->  extractors  -->  resolvers  -->  aggregators  -->  fillers  -->  markdown report
       (envelopes)            (typed values)   (authority,     (reconciled,        (tag-aware
                                                 subject_ref)    provenanced)         fill)
```

## The extractor output contract

Defined in `contract.py` as a **frozen dataclass `ExtractedValue`**. Chosen
over a plain dict or `NamedTuple` because:

- It mirrors the existing `tools/audit/_numerics.NumericToken` pattern, so the
  codebase stays internally consistent.
- `frozen=True` makes an extracted fact immutable — an extractor states what
  the envelope says; nothing downstream should mutate it in place.
- Named, typed fields make rule 2 (carry units + provenance) structural rather
  than a convention someone can forget. The aggregator can rely on every value
  carrying `unit`, `source`, `subject`, `as_of`, and `provenance`.

Fields: `metric`, `value` (float | int | bool), `unit`, `source`, `subject`,
`as_of` (the envelope's `fetched_at`), `provenance` (free-form derivation
trail). Stays Python 3.9-clean via `from __future__ import annotations`.

**Success/failure convention:** an extractor returns an `ExtractedValue` on
success, or `None` when a required envelope sub-field is missing. `None` is the
single, uniform "no data" signal — never a partially-filled object, never an
exception (rule 1).

### The three rules every extractor MUST follow

1. **Null-guard** — missing sub-fields return `None`, never throw. Real
   envelopes carry nulls: a chain-level Alchemy envelope has no `eth_call`;
   CMC `quotes_historical` and Etherscan `tokeninfo` can be absent.
2. **Carry provenance + units** — every value travels with `source`, `unit`,
   and `as_of` timestamp so the aggregator can reconcile without re-reading raw.
3. **Pure function** — no I/O, no fetch. Envelope in, typed value out.

## Per-source extractor roadmap

| Source | Functions (planned) |
| --- | --- |
| **alchemy** ✅ | `decode_total_supply(envelope, decimals)`, `is_contract(envelope)` |
| sec_edgar | `get_xbrl_value(concept, fy, fp, form)`, `list_filings(form)` |
| coingecko | `extract_spot_metrics`, `extract_history_series` |
| etherscan | `extract_supply(decimals)`, `aggregate_transfers` (page-aware) |
| coinmarketcap | `extract_latest_quote` (null-guard historical) |
| defillama | `extract_stablecoin_supply_series` |

(An `l2beat` fetcher also exists in B.1 but has no extractor mandate yet.)

### Why `decimals` is passed in, not read

The Alchemy envelope does not carry a token's `decimals` (USDC = 6). The caller
supplies it today. This is exactly the job of the future **subject_ref**
resolver: map a subject (contract address) to its decimals / canonical ids, so
callers stop hard-coding `6`.

## Reconciliation rules (the aggregator will enforce these)

- **General currency rule (MEMORY.md hard rule):** currency amounts agree
  within **±0.5% relative**.
- **Supply-specific cross-source bands** (decided this session, tighter):
  - Multi-chain aggregator total (CoinGecko / CMC / DefiLlama): **~0.2%**.
  - Single-chain same-contract (Etherscan vs Alchemy): **~0.01–0.05%**, BUT
    only for **CONTEMPORANEOUS** reads. Our two on-chain envelopes are ~2 days
    apart (~0.26% drift = normal mint/burn). The aggregator must account for
    the `as_of` gap, not false-flag it.
- **Source authority** (per `references/data_source_registry.md`):
  - CoinGecko = primary price / market cap.
  - DefiLlama = primary TVL.
  - On-chain (Etherscan / Alchemy) = supply truth.
  - CMC = cross-check.
- **Scope rule:** cross-chain total (~$76.4B) vs Ethereum-only (~$52.6B) are
  **different metrics** — never reconcile across scopes.

## Phase roadmap

- **Lane A (now):** extractor → aggregator → filler → markdown report.
- Then, in priority order:
  - **B.3** red team + audit web-third-check (verification — TOP priority).
    Note: the reconcile/audit layer **is** the aggregator, already part of B.2.
  - **B.4** markdown → HTML render.
  - **B.5** 6-card pack (YYFoundry brand visuals).
  - **B.6** SQLite crypto schema (cross-report query + incremental).
  - **Incident loop:** not built standalone; fills organically.
- The inherited equity P1+ pipeline (`workflow_meta.json`) is stale residue
  (TD-010), **NOT** the Lane A target — do **not** wire into it.
